import pyodbc
from config import Config

class MSSQLConnector:
    @staticmethod
    def get_connection(server_key, database="master"):
        """依據 server_key 動態取得 MSSQL 連線"""
        server_cfg = Config.SERVERS.get(server_key)
        if not server_cfg:
            raise ValueError(f"找不到伺服器配置: {server_key}")
            
        conn_str = (
            f"DRIVER={server_cfg['driver']};"
            f"SERVER={server_cfg['host']};"
            f"DATABASE={database};"
            f"UID={server_cfg['user']};"
            f"PWD={server_cfg['password']};"
            f"Connection Timeout=5;"
            f"Encrypt=yes;"
            f"TrustServerCertificate=yes;"
        )
        return pyodbc.connect(conn_str)

    @classmethod
    def execute_query(cls, server_key, sql, params=None, database="master"):
        """執行 SELECT 查詢並回傳 Dict 列表"""
        conn = cls.get_connection(server_key, database)
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            if not cursor.description:
                return []
                
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    @classmethod
    def execute_non_query(cls, server_key, sql, params=None, database="master"):
        """執行 命令 (如 KILL SPID 或 REBUILD INDEX)"""
        conn = cls.get_connection(server_key, database)
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()

    # ==================== T-SQL DMV 專業查詢方法 ==================== #

    @classmethod
    def get_dashboard_metrics(cls, server_key):
        """1. 取得儀表板即時數據 (CPU, Memory, 連線數)"""
        # 從 Ring Buffer 獲取最新 MSSQL CPU 使用率
        cpu_sql = """
        SELECT TOP 1 
            100 - record.value('(./Record/SchedulerMonitorEvent/SystemHealth/SystemIdle)[1]', 'int') AS system_idle,
            record.value('(./Record/SchedulerMonitorEvent/SystemHealth/ProcessUtilization)[1]', 'int') AS sql_cpu
        FROM (
            SELECT CAST(record AS xml) AS record
            FROM sys.dm_os_ring_buffers
            WHERE ring_buffer_type = N'RING_BUFFER_SCHEDULER_MONITOR'
            AND record LIKE '%<SystemHealth>%'
        ) AS x
        ORDER BY record.value('(./Record/@id)[1]', 'bigint') DESC;
        """
        
        # 獲取記憶體與連線概況
        overview_sql = """
        SELECT 
            (SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process = 1) AS active_connections,
            (SELECT physical_memory_in_use_kb / 1024 FROM sys.dm_os_process_memory) AS memory_used_mb,
            (SELECT COUNT(*) FROM sys.databases WHERE state = 0) AS total_databases;
        """
        
        cpu_res = cls.execute_query(server_key, cpu_sql)
        overview_res = cls.execute_query(server_key, overview_sql)
        
        sql_cpu = cpu_res[0]['sql_cpu'] if cpu_res else 0
        overview = overview_res[0] if overview_res else {}
        
        return {
            "sql_cpu": sql_cpu,
            "memory_used_mb": overview.get("memory_used_mb", 0),
            "active_connections": overview.get("active_connections", 0),
            "total_databases": overview.get("total_databases", 0)
        }

    @classmethod
    def get_database_sizes(cls, server_key):
        """2. 取得所有 Database 空間佔用"""
        sql = """
        SELECT 
            d.name AS db_name,
            CAST(SUM(CASE WHEN f.type = 0 THEN f.size END) * 8.0 / 1024 AS DECIMAL(10,1)) AS data_size_mb,
            CAST(SUM(CASE WHEN f.type = 1 THEN f.size END) * 8.0 / 1024 AS DECIMAL(10,1)) AS log_size_mb,
            d.state_desc AS status
        FROM sys.databases d
        JOIN sys.master_files f ON d.database_id = f.database_id
        GROUP BY d.name, d.state_desc
        ORDER BY data_size_mb DESC;
        """
        return cls.execute_query(server_key, sql)

    @classmethod
    def get_active_sessions(cls, server_key, blocked_only=False):
        """3. 取得 Activity Sessions (含 Blocking 偵測)"""
        sql = """
        SELECT 
            r.session_id AS spid,
            s.login_name,
            s.host_name,
            DB_NAME(r.database_id) AS db_name,
            r.status,
            ISNULL(r.blocking_session_id, 0) AS blocked_by,
            r.wait_type,
            r.cpu_time,
            r.total_elapsed_time / 1000.0 AS elapsed_seconds,
            SUBSTRING(st.text, (r.statement_start_offset/2)+1,
                ((CASE r.statement_end_offset
                    WHEN -1 THEN DATALENGTH(st.text)
                    ELSE r.statement_end_offset
                END - r.statement_start_offset)/2) + 1) AS sql_text
        FROM sys.dm_exec_requests r
        INNER JOIN sys.dm_exec_sessions s ON r.session_id = s.session_id
        CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) st
        WHERE s.is_user_process = 1 AND r.session_id <> @@SPID
        """
        if blocked_only:
            sql += " AND r.blocking_session_id > 0"
        sql += " ORDER BY r.total_elapsed_time DESC;"
        
        return cls.execute_query(server_key, sql)

    @classmethod
    def get_slow_queries(cls, server_key, top=10):
        """4. 取得 Top 慢速查詢 (分析 sys.dm_exec_query_stats)"""
        sql = f"""
        SELECT TOP ({top})
            qs.execution_count,
            (qs.total_worker_time / qs.execution_count) / 1000.0 AS avg_cpu_ms,
            (qs.total_elapsed_time / qs.execution_count) / 1000.0 AS avg_elapsed_ms,
            (qs.total_logical_reads / qs.execution_count) AS avg_logical_reads,
            qs.last_execution_time,
            SUBSTRING(qt.text, (qs.statement_start_offset/2)+1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset)/2) + 1) AS sql_text
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
        ORDER BY qs.total_worker_time DESC;
        """
        return cls.execute_query(server_key, sql)

    @classmethod
    def get_index_fragmentation(cls, server_key, db_name):
        """5. 取得索引碎片率 (>10%)"""
        sql = f"""
        USE [{db_name}];
        SELECT 
            OBJECT_NAME(ips.object_id) AS table_name,
            i.name AS index_name,
            ips.avg_fragmentation_in_percent AS fragmentation_percent,
            ips.page_count,
            CASE 
                WHEN ips.avg_fragmentation_in_percent > 30 THEN 'REBUILD'
                WHEN ips.avg_fragmentation_in_percent >= 10 THEN 'REORGANIZE'
                ELSE 'NONE'
            END AS recommended_action
        FROM sys.dm_db_index_physical_stats(DB_ID('{db_name}'), NULL, NULL, NULL, 'LIMITED') ips
        JOIN sys.indexes i ON ips.object_id = i.object_id AND ips.index_id = i.index_id
        WHERE ips.avg_fragmentation_in_percent >= 10 AND i.name IS NOT NULL
        ORDER BY ips.avg_fragmentation_in_percent DESC;
        """
        return cls.execute_query(server_key, sql, database=db_name)

    @classmethod
    def get_error_logs(cls, server_key):
        """6. 讀取 SQL Server Error Log"""
        sql = "EXEC sys.xp_readerrorlog 0, 1, NULL, NULL;"
        rows = cls.execute_query(server_key, sql)
        # 格式化輸出
        logs = []
        for r in rows[:50]: # 回傳最新 50 條
            logs.append({
                "log_date": str(r.get("LogDate", "")),
                "process_info": r.get("ProcessInfo", ""),
                "text": r.get("Text", "")
            })
        return logs