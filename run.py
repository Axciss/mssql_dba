from app import create_app

app = create_app()

if __name__ == '__main__':
    # 啟動開發伺服器
    app.run(host='0.0.0.0', port=5000, debug=True)