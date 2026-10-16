```
mssql_dba_system/
├── config.py                     # 多伺服器連線配置 & 系統設定
├── run.py                        # Flask 進入點
└── app/
    ├── __init__.py               # App Factory & 藍圖註冊
    ├── utils/
    │   ├── mssql_connector.py    # 核心 T-SQL DMV 查詢與動態連線池
    │   └── response.py           # 統一 API 回傳 JSON 格式化工具
    └── api/
        ├── dashboard_api.py      # /api/v1/dashboard/ (概況、CPU/Memory 圖表、DB空間)
        ├── activity_api.py       # /api/v1/activity/ (Sessions, Blocked, Kill SPID)
        ├── performance_api.py    # /api/v1/performance/ (Slow Queries, Top CPU/IO)
        ├── maintenance_api.py    # /api/v1/maintenance/ (索引碎片、REBUILD/REORG)
        └── logs_api.py           # /api/v1/logs/ (xp_readerrorlog 讀取)
```