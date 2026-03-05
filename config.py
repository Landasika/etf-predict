"""
ETF预测系统配置
"""
import os

# 项目路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据库配置
DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'etf.db')
WATCHLIST_PATH = os.path.join(BASE_DIR, 'data', 'watchlist_etfs.json')
WEIGHTS_PATH = os.path.join(BASE_DIR, 'optimized_weights')

# API配置
API_HOST = '0.0.0.0'
API_PORT = 8000  # API服务端口
API_TITLE = 'ETF预测系统API'
API_VERSION = '1.0.0'

# Tushare配置（可选，用于数据更新）
TUSHARE_TOKEN = '5c778b0f7d4a69893ae98c6d3b6ef5637875125daee6205b435e9d20e9b4'

# Minishare配置（用于实时行情数据）
MINISHARE_TOKEN = os.getenv('MINISHARE_TOKEN', '4E5m137e34HjyNm2c3r8paa9BYe8e35wHt5T1QxSf98jpElbypp3Y0Fg0443a82a')

# 策略配置
STRATEGIES = {
    'macd_aggressive': 'MACD激进策略',
    'optimized_t_trading': '优化做T策略',
    'multifactor': '多因子量化策略'
}

def get_etf_list():
    """从自选列表JSON中读取ETF列表

    Returns:
        list: ETF代码列表，如 ['510330.SH', '159672.SZ', ...]
    """
    import json
    try:
        with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [etf['code'] for etf in data.get('etfs', [])]
    except Exception as e:
        print(f"⚠️  无法读取自选列表: {e}")
        return []

def get_all_etf_info():
    """从自选列表JSON中读取所有ETF信息

    Returns:
        list: ETF信息列表，每个元素包含code, name, sector等
    """
    import json
    try:
        with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('etfs', [])
    except Exception as e:
        print(f"⚠️  无法读取自选列表: {e}")
        return []

# 回测默认参数
DEFAULT_INITIAL_CAPITAL = 2000
DEFAULT_POSITIONS = 10
DEFAULT_START_DATE = '20240101'

# 支持的交易所
EXCHANGES = ['SH', 'SZ']
