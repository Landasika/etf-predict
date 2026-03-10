"""
ETF预测系统配置
从 config.json 文件读取所有配置
"""
import os
import json
import hashlib
from pathlib import Path

# 项目路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')


def load_config():
    """从 config.json 加载配置"""
    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        # 创建默认配置
        default_config = {
            "database": {"path": "data/etf.db"},
            "watchlist": {"path": "data/watchlist_etfs.json"},
            "weights": {"path": "optimized_weights"},
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "title": "ETF预测系统API",
                "version": "1.0.0"
            },
            "auth": {
                "session_secret_key": "change-this-in-production-please-use-random-key",
                "auth_key": "admin123",
                "max_login_attempts": 5,
                "login_attempt_window": 300,
                "lockout_duration": 900
            },
            "tushare": {"token": ""},
            "minishare": {
                "token": "4E5m137e34HjyNm2c3r8paa9BYe8e35wHt5T1QxSf98jpElbypp3Y0Fg0443a82a"
            },
            "strategies": {
                "macd_aggressive": "MACD激进策略",
                "optimized_t_trading": "优化做T策略",
                "multifactor": "多因子量化策略"
            }
        }

        # 保存默认配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)

        return default_config

    # 读取配置
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 加载配置
_config = load_config()

# ==================== 数据库配置 ====================
DATABASE_PATH = os.path.join(BASE_DIR, _config['database']['path'])
WATCHLIST_PATH = os.path.join(BASE_DIR, _config['watchlist']['path'])
WEIGHTS_PATH = os.path.join(BASE_DIR, _config['weights']['path'])

# ==================== API配置 ====================
API_HOST = _config['api']['host']
API_PORT = _config['api']['port']
API_TITLE = _config['api']['title']
API_VERSION = _config['api']['version']

# ==================== 认证配置 ====================
SESSION_SECRET_KEY = _config['auth']['session_secret_key']
AUTH_KEY = _config['auth']['auth_key']
AUTH_KEY_HASH = hashlib.sha256(AUTH_KEY.encode()).hexdigest()
MAX_LOGIN_ATTEMPTS = _config['auth']['max_login_attempts']
LOGIN_ATTEMPT_WINDOW = _config['auth']['login_attempt_window']
LOCKOUT_DURATION = _config['auth']['lockout_duration']

# 模板引擎（将在api/main.py中初始化）
templates = None

# ==================== Token配置 ====================
TUSHARE_TOKEN = _config['tushare']['token']
MINISHARE_TOKEN = _config['minishare']['token']

# ==================== 策略配置 ====================
STRATEGIES = _config['strategies']


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


def reload_config():
    """重新加载配置文件"""
    global _config
    _config = load_config()

    # 更新全局变量
    global DATABASE_PATH, WATCHLIST_PATH, WEIGHTS_PATH
    global API_HOST, API_PORT, API_TITLE, API_VERSION
    global SESSION_SECRET_KEY, AUTH_KEY, AUTH_KEY_HASH
    global MAX_LOGIN_ATTEMPTS, LOGIN_ATTEMPT_WINDOW, LOCKOUT_DURATION
    global TUSHARE_TOKEN, MINISHARE_TOKEN, STRATEGIES

    DATABASE_PATH = os.path.join(BASE_DIR, _config['database']['path'])
    WATCHLIST_PATH = os.path.join(BASE_DIR, _config['watchlist']['path'])
    WEIGHTS_PATH = os.path.join(BASE_DIR, _config['weights']['path'])

    API_HOST = _config['api']['host']
    API_PORT = _config['api']['port']
    API_TITLE = _config['api']['title']
    API_VERSION = _config['api']['version']

    SESSION_SECRET_KEY = _config['auth']['session_secret_key']
    AUTH_KEY = _config['auth']['auth_key']
    AUTH_KEY_HASH = hashlib.sha256(AUTH_KEY.encode()).hexdigest()
    MAX_LOGIN_ATTEMPTS = _config['auth']['max_login_attempts']
    LOGIN_ATTEMPT_WINDOW = _config['auth']['login_attempt_window']
    LOCKOUT_DURATION = _config['auth']['lockout_duration']

    TUSHARE_TOKEN = _config['tushare']['token']
    MINISHARE_TOKEN = _config['minishare']['token']
    STRATEGIES = _config['strategies']


def get_config():
    """获取完整配置字典"""
    return _config.copy()


def update_config(updates):
    """更新配置并保存到文件

    Args:
        updates: dict 包含要更新的配置项

    Returns:
        bool: 是否更新成功
    """
    global _config

    try:
        # 更新配置
        _config.update(updates)

        # 保存到文件
        config_path = Path(CONFIG_FILE)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(_config, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"❌ 更新配置失败: {e}")
        return False


# 回测默认参数
DEFAULT_INITIAL_CAPITAL = 2000
DEFAULT_POSITIONS = 10
DEFAULT_START_DATE = '20240101'

# 支持的交易所
EXCHANGES = ['SH', 'SZ']
