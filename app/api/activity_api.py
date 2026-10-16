from flask import Blueprint, request, jsonify
from app.utils.mssql_connector import MSSQLConnector

activity_bp = Blueprint('activity_api', __name__, url_prefix='/api/v1/activity')

@activity_bp.route('/sessions', methods=['GET'])
def get_sessions():
    server_key = request.args.get('server_key', 'PROD-DB01')
    blocked_only = request.args.get('blocked_only', 'false').lower() == 'true'
    try:
        sessions = MSSQLConnector.get_active_sessions(server_key, blocked_only)
        return jsonify({"status": "success", "data": sessions})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@activity_bp.route('/kill', methods=['POST'])
def kill_spid():
    data = request.json or {}
    server_key = data.get('server_key')
    spid = data.get('spid')
    reason = data.get('reason', '無填寫原因')
    
    if not server_key or not spid:
        return jsonify({"status": "error", "message": "缺少必要參數"}), 400
        
    try:
        # 防呆檢查，不允許 KILL 系統神聖 SPID (1-50)
        if int(spid) <= 50:
            return jsonify({"status": "error", "message": "禁止中斷系統級 Session (SPID <= 50)"}), 403
            
        sql = f"KILL {int(spid)};"
        MSSQLConnector.execute_non_query(server_key, sql)
        
        # [可擴充] 在此處將 {spid}, {reason}, DBA User 寫入本地審計日誌 (Audit Log)
        print(f"[AUDIT LOG] Server: {server_key} | Killed SPID: {spid} | Reason: {reason}")
        
        return jsonify({"status": "success", "message": f"已成功中斷 Session SPID {spid}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"KILL 失敗: {str(e)}"}), 500