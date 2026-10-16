from flask import Flask, render_template, jsonify
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 註冊 RESTful API 藍圖
    from app.api.dashboard_api import dashboard_bp
    from app.api.activity_api import activity_bp
    from app.api.performance_api import performance_bp
    from app.api.maintenance_api import maintenance_bp
    from app.api.logs_api import logs_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(performance_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(logs_bp)

    # 伺服器列表 API
    @app.route('/api/v1/servers', methods=['GET'])
    def get_servers():
        servers = [{"key": k, "name": v["name"]} for k, v in Config.SERVERS.items()]
        return jsonify({"status": "success", "data": servers})

    # 首頁 (渲染前端一體化頁面)
    @app.route('/')
    def index():
        return render_template('index.html')

    return app