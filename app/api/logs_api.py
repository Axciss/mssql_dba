from flask import Blueprint, request, jsonify
from app.utils.mssql_connector import MSSQLConnector

logs_bp = Blueprint('logs_api', __name__, url_prefix='/api/v1/logs')

@logs_bp.route('/errorlog', methods=['GET'])
def get_error_logs():
    server_key = request.args.get('server_key', 'PROD-DB01')
    try:
        logs = MSSQLConnector.get_error_logs(server_key)
        return jsonify({"status": "success", "data": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500