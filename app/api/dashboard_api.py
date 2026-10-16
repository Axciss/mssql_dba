from flask import Blueprint, request, jsonify
from app.utils.mssql_connector import MSSQLConnector

dashboard_bp = Blueprint('dashboard_api', __name__, url_prefix='/api/v1/dashboard')

@dashboard_bp.route('/metrics', methods=['GET'])
def get_metrics():
    server_key = request.args.get('server_key', 'PROD-DB01')
    try:
        metrics = MSSQLConnector.get_dashboard_metrics(server_key)
        db_sizes = MSSQLConnector.get_database_sizes(server_key)
        return jsonify({
            "status": "success",
            "data": {
                "metrics": metrics,
                "databases": db_sizes
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500