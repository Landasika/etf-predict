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
    # 启动数据更新调度器
    try:
        from core.data_update_scheduler import get_scheduler
        scheduler = get_scheduler()

        # 设置默认更新时间
        scheduler.set_update_time("15:05")

        print("📅 数据更新调度器已加载（可通过前端界面启用）")
    except Exception as e:
        print(f"⚠️  调度器加载失败: {e}")

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
