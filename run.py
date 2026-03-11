"""
ETF预测系统启动脚本
"""
import uvicorn
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.main import app
import config

if __name__ == '__main__':
    print("📅 调度器将在应用启动时按 config.json 自动恢复")

    print(f"""
=====================================
ETF预测系统启动中...
=====================================
API地址: http://{config.API_HOST}:{config.API_PORT}
文档地址: http://{config.API_HOST}:{config.API_PORT}/docs
=====================================
    """)
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level='info'
    )
