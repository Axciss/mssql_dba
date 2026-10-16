from flask import Blueprint, request, jsonify
from app.utils.mssql_connector import MSSQLConnector

performance_bp = Blueprint('performance_api', __name__, url_prefix='/api/v1/performance')

@performance_bp.route('/slow-queries', methods=['GET'])
def slow_queries():
    server_key = request.args.get('server_key', 'PROD-DB01')
    try:
        queries = MSSQLConnector.get_slow_queries(server_key, top=15)
        return jsonify({"status": "success", "data": queries})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500