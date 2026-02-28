"""
系统设置管理模块

管理用户可配置的系统参数，包括：
- Tushare Token
- Minishare Token
- 数据更新方法选择
- API配置
- 更新时间设置
"""
import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SettingsManager:
    """系统设置管理器"""

    def __init__(self, settings_file: str = None):
        if settings_file is None:
            from config import BASE_DIR
            settings_file = os.path.join(BASE_DIR, 'data', 'system_settings.json')

        self.settings_file = settings_file
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载设置失败: {e}")
                return self._get_default_settings()
        else:
            return self._get_default_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        """获取默认设置"""
        return {
            "tushare": {
                "enabled": True,
                "token": "",
                "note": "用于历史数据下载（fund_daily接口）"
            },
            "minishare": {
                "enabled": True,
                "token": "6xH3v19jLi9AZ4N2m7Qsn98hur2Mle9ock6RT9Dnt7Ys3GAPMf00H0gl3d5355fd",
                "note": "用于实时数据获取（rt_etf_k_ms接口）"
            },
            "data_source": {
                "priority": ["minishare", "tushare"],  # 优先级顺序
                "note": "数据获取优先级：先尝试Minishare，失败则用Tushare"
            },
            "update_schedule": {
                "enabled": True,
                "time": "15:05",
                "auto_update": True,
                "note": "交易日收盘后自动更新"
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "title": "ETF预测系统API"
            },
            "strategy": {
                "default_strategy": "macd_aggressive",
                "default_initial_capital": 2000,
                "default_positions": 10
            }
        }

    def get_settings(self) -> Dict[str, Any]:
        """获取所有设置"""
        # 从config.py读取一些值，确保设置是最新的
        import config

        self.settings['api']['host'] = config.API_HOST
        self.settings['api']['port'] = config.API_PORT

        # 隐藏敏感信息
        safe_settings = self.settings.copy()
        if safe_settings.get('tushare', {}).get('token'):
            safe_settings['tushare']['token'] = self._mask_token(safe_settings['tushare']['token'])
        if safe_settings.get('minishare', {}).get('token'):
            safe_settings['minishare']['token'] = self._mask_token(safe_settings['minishare']['token'])

        return safe_settings

    def _mask_token(self, token: str) -> str:
        """隐藏Token（只显示前8位）"""
        if not token:
            return ""
        if len(token) <= 8:
            return token
        return token[:8] + "..."

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新设置"""
        try:
            # 合并更新
            self._deep_update(self.settings, updates)

            # 保存到文件
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)

            logger.info("✅ 设置已保存")
            return {'success': True, 'message': '设置已保存'}
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            return {'success': False, 'message': f'保存失败: {str(e)}'}

    def _deep_update(self, base_dict: Dict, updates: Dict):
        """深度合并字典"""
        for key, value in updates.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def update_tokens(self, tushare_token: str = None, minishare_token: str = None) -> Dict[str, Any]:
        """更新Token"""
        updates = {}

        if tushare_token is not None:
            updates['tushare'] = {
                'enabled': bool(tushare_token),
                'token': tushare_token.strip()
            }

        if minishare_token is not None:
            updates['minishare'] = {
                'enabled': bool(minishare_token),
                'token': minishare_token.strip()
            }

        return self.update_settings(updates)

    def get_active_data_source(self) -> str:
        """获取当前激活的数据源"""
        priority = self.settings.get('data_source', {}).get('priority', ['minishare', 'tushare'])

        # 按优先级检查哪个数据源可用
        for source in priority:
            if source == 'minishare' and self.settings.get('minishare', {}).get('enabled', True):
                return 'minishare'
            elif source == 'tushare' and self.settings.get('tushare', {}).get('enabled', True):
                return 'tushare'

        return 'tushare'  # 默认


# 全局实例
_settings_manager = None

def get_settings_manager() -> SettingsManager:
    """获取设置管理器实例"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
