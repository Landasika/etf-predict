"""
ETF预测系统配置
支持从环境变量和 config.json 文件读取配置
环境变量优先级高于配置文件
"""
import os
import json
import hashlib
from copy import deepcopy
from pathlib import Path

# 项目路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')


def _get_env(key, default=None):
    """获取环境变量，支持 None 值"""
    value = os.environ.get(key, default)
    if value == 'None':
        return None
    return value


def _get_env_bool(key, default=False):
    """获取布尔型环境变量"""
    value = os.environ.get(key, '')
    if not value:
        return default
    return value.lower() in ('true', '1', 'yes', 'on')

DEFAULT_UPDATE_TIME = "15:05"
DEFAULT_FEISHU_NOTIFICATION_TIMES = ["09:40", "10:40", "11:40", "13:40", "14:40"]
DEFAULT_FEISHU_NOTIFICATION_TIMES_TEXT = ",".join(DEFAULT_FEISHU_NOTIFICATION_TIMES)
DEFAULT_REALTIME_UPDATER_START_TIME = "09:25"
DEFAULT_REALTIME_UPDATER_END_TIME = "15:05"
DEFAULT_REALTIME_UPDATER_INTERVAL = 60
DEFAULT_CONFIG = {
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
    "tinyshare": {"token": ""},
    "tushare": {"token": ""},
    "minishare": {
        "token": "4E5m137e34HjyNm2c3r8paa9BYe8e35wHt5T1QxSf98jpElbypp3Y0Fg0443a82a"
    },
    "update_schedule": {
        "enabled": False,
        "time": DEFAULT_UPDATE_TIME
    },
    "feishu_notification_schedule": {
        "enabled": False,
        "times": DEFAULT_FEISHU_NOTIFICATION_TIMES_TEXT
    },
    "realtime_updater_schedule": {
        "enabled": False,
        "start_time": DEFAULT_REALTIME_UPDATER_START_TIME,
        "end_time": DEFAULT_REALTIME_UPDATER_END_TIME,
        "update_interval": DEFAULT_REALTIME_UPDATER_INTERVAL
    },
    "strategies": {
        "macd_aggressive": "MACD激进策略",
        "optimized_t_trading": "优化做T策略",
        "multifactor": "多因子量化策略"
    }
}


def _merge_defaults(user_config, default_config):
    """递归补齐缺失配置，不覆盖用户已有值"""
    merged = deepcopy(default_config)

    for key, value in user_config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_defaults(value, merged[key])
        else:
            merged[key] = value

    return merged


def load_config():
    """从 config.json 加载配置，并应用环境变量覆盖"""
    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        # 保存默认配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)

        config = deepcopy(DEFAULT_CONFIG)
    else:
        # 读取配置
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
        config = _merge_defaults(user_config, DEFAULT_CONFIG)

    # 应用环境变量覆盖
    return _apply_env_overrides(config)


def _apply_env_overrides(config):
    """应用环境变量覆盖配置文件"""
    # API 配置
    if _get_env('API_HOST'):
        config['api']['host'] = _get_env('API_HOST')
    if _get_env('API_PORT'):
        config['api']['port'] = int(_get_env('API_PORT'))

    # 认证配置
    if _get_env('AUTH_KEY'):
        config['auth']['auth_key'] = _get_env('AUTH_KEY')
    if _get_env('SESSION_SECRET_KEY'):
        config['auth']['session_secret_key'] = _get_env('SESSION_SECRET_KEY')

    # 数据源配置
    if _get_env('TUSHARE_TOKEN'):
        config.setdefault('tushare', {})['token'] = _get_env('TUSHARE_TOKEN')
    if _get_env('TUSHARE_PROXY_URL'):
        config.setdefault('tushare', {})['proxy_url'] = _get_env('TUSHARE_PROXY_URL')
    if _get_env('TINYSHARE_TOKEN'):
        config.setdefault('tinyshare', {})['token'] = _get_env('TINYSHARE_TOKEN')
    if _get_env('MINISHARE_TOKEN'):
        config.setdefault('minishare', {})['token'] = _get_env('MINISHARE_TOKEN')

    # 调度配置
    if _get_env('UPDATE_SCHEDULE_ENABLED') is not None:
        config['update_schedule']['enabled'] = _get_env_bool('UPDATE_SCHEDULE_ENABLED')
    if _get_env('UPDATE_SCHEDULE_TIME'):
        config['update_schedule']['time'] = _get_env('UPDATE_SCHEDULE_TIME')

    # 飞书通知配置
    if _get_env('FEISHU_SCHEDULE_ENABLED') is not None:
        config['feishu_notification_schedule']['enabled'] = _get_env_bool('FEISHU_SCHEDULE_ENABLED')
    if _get_env('FEISHU_NOTIFICATION_TIMES'):
        config['feishu_notification_schedule']['times'] = _get_env('FEISHU_NOTIFICATION_TIMES')

    # 实时数据更新器配置
    if _get_env('REALTIME_UPDATER_ENABLED') is not None:
        config.setdefault('realtime_updater_schedule', {})['enabled'] = _get_env_bool('REALTIME_UPDATER_ENABLED')
    if _get_env('REALTIME_UPDATER_START_TIME'):
        config.setdefault('realtime_updater_schedule', {})['start_time'] = _get_env('REALTIME_UPDATER_START_TIME')
    if _get_env('REALTIME_UPDATER_END_TIME'):
        config.setdefault('realtime_updater_schedule', {})['end_time'] = _get_env('REALTIME_UPDATER_END_TIME')
    if _get_env('REALTIME_UPDATER_INTERVAL'):
        config.setdefault('realtime_updater_schedule', {})['update_interval'] = int(_get_env('REALTIME_UPDATER_INTERVAL'))

    return config


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

def _get_provider_token(config_data, provider_name):
    """从配置中安全读取数据源 token"""
    provider_config = config_data.get(provider_name, {})
    if not isinstance(provider_config, dict):
        return ""
    return provider_config.get('token', '')


def _get_provider_proxy_url(config_data, provider_name):
    """从配置中安全读取数据源代理 URL"""
    provider_config = config_data.get(provider_name, {})
    if not isinstance(provider_config, dict):
        return ""
    return provider_config.get('proxy_url', '')


# ==================== Token配置 ====================
TINYSHARE_TOKEN = _get_provider_token(_config, 'tinyshare') or _get_provider_token(_config, 'tushare')
TUSHARE_TOKEN = _get_provider_token(_config, 'tushare')
TUSHARE_PROXY_URL = _get_provider_proxy_url(_config, 'tushare')
MINISHARE_TOKEN = _get_provider_token(_config, 'minishare')

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
    global TINYSHARE_TOKEN, TUSHARE_TOKEN, MINISHARE_TOKEN, STRATEGIES

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

    TINYSHARE_TOKEN = _get_provider_token(_config, 'tinyshare') or _get_provider_token(_config, 'tushare')
    TUSHARE_TOKEN = _get_provider_token(_config, 'tushare')
    TUSHARE_PROXY_URL = _get_provider_proxy_url(_config, 'tushare')
    MINISHARE_TOKEN = _get_provider_token(_config, 'minishare')
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
DEFAULT_START_DATE = '20250101'

# 实时更新器默认参数
DEFAULT_REALTIME_UPDATER_START_TIME = "09:25"
DEFAULT_REALTIME_UPDATER_END_TIME = "15:05"
DEFAULT_REALTIME_UPDATER_INTERVAL = 60

# 支持的交易所
EXCHANGES = ['SH', 'SZ']
