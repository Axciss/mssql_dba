from flask import Blueprint, request, jsonify
from app.utils.mssql_connector import MSSQLConnector

maintenance_bp = Blueprint('maintenance_api', __name__, url_prefix='/api/v1/maintenance')

@maintenance_bp.route('/indexes', methods=['GET'])
def get_indexes():
    server_key = request.args.get('server_key', 'PROD-DB01')
    db_name = request.args.get('db_name', 'master')
    try:
        indexes = MSSQLConnector.get_index_fragmentation(server_key, db_name)
        return jsonify({"status": "success", "data": indexes})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@maintenance_bp.route('/index-action', methods=['POST'])
def execute_index_action():
    data = request.json or {}
    server_key = data.get('server_key')
    db_name = data.get('db_name')
    table_name = data.get('table_name')
    index_name = data.get('index_name')
    action = data.get('action') # REBUILD or REORGANIZE
    
    if action not in ['REBUILD', 'REORGANIZE']:
        return jsonify({"status": "error", "message": "無效的維護動作"}), 400
        
    try:
        sql = f"USE [{db_name}]; ALTER INDEX [{index_name}] ON [{table_name}] {action};"
        MSSQLConnector.execute_non_query(server_key, sql, database=db_name)
        return jsonify({"status": "success", "message": f"索引 [{index_name}] {action} 完成"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500