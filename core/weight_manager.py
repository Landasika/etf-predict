"""
权重自动管理模块

功能：
1. 检查权重文件是否存在
2. 检查权重文件是否过期
3. 自动优化权重（如果需要）
4. 加载权重并缓存
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta


class WeightManager:
    """权重自动管理器"""

    # 权重缓存（避免重复加载）
    _weight_cache = {}

    # 权重过期时间（天）
    WEIGHT_EXPIRE_DAYS = 30

    # 权重文件路径模式
    WEIGHT_PATH_PATTERN = "optimized_weights/{etf_code}/best_weights.json"

    @classmethod
    def get_weights(cls, etf_code: str, auto_optimize: bool = True) -> tuple[bool, Optional[Dict], str]:
        """
        获取ETF的权重

        Args:
            etf_code: ETF代码
            auto_optimize: 是否自动优化（如果权重不存在或过期）

        Returns:
            (success, weights, message)
            - success: 是否成功获取权重
            - weights: 权重字典（失败时为None）
            - message: 状态消息
        """
        # 1. 检查缓存
        if etf_code in cls._weight_cache:
            cached = cls._weight_cache[etf_code]
            if not cls._is_expired(cached.get('timestamp')):
                return True, cached['weights'], '使用缓存权重'

        # 2. 构建权重文件路径
        weights_file = Path(cls.WEIGHT_PATH_PATTERN.format(etf_code=etf_code))

        # 3. 检查文件是否存在
        if not weights_file.exists():
            if not auto_optimize:
                return False, None, f'权重文件不存在: {weights_file}'

            # 自动优化
            return cls._auto_optimize(etf_code, weights_file)

        # 4. 检查是否过期
        if cls._is_file_expired(weights_file):
            if not auto_optimize:
                return False, None, f'权重文件已过期（超过{cls.WEIGHT_EXPIRE_DAYS}天）'

            # 后台重新优化（不阻塞）
            cls._background_optimize(etf_code, weights_file)

            # 仍然使用旧权重
            try:
                with open(weights_file, 'r') as f:
                    weights = json.load(f)

                # 缓存权重
                cls._weight_cache[etf_code] = {
                    'weights': weights,
                    'timestamp': time.time()
                }

                return True, weights, '使用旧权重（后台重新优化中...）'
            except Exception as e:
                return False, None, f'加载权重文件失败: {e}'

        # 5. 加载权重
        try:
            with open(weights_file, 'r') as f:
                weights = json.load(f)

            # 验证权重格式
            if not isinstance(weights, dict) or len(weights) == 0:
                return False, None, '权重文件格式错误'

            # 缓存权重
            cls._weight_cache[etf_code] = {
                'weights': weights,
                'timestamp': time.time()
            }

            return True, weights, '成功加载权重'

        except Exception as e:
            return False, None, f'加载权重文件失败: {e}'

    @classmethod
    def _is_file_expired(cls, weights_file: Path) -> bool:
        """检查文件是否过期"""
        try:
            # 检查文件修改时间
            mtime = weights_file.stat().st_mtime
            file_date = datetime.fromtimestamp(mtime)
            expire_date = datetime.now() - timedelta(days=cls.WEIGHT_EXPIRE_DAYS)

            return file_date < expire_date
        except:
            return True

    @classmethod
    def _is_expired(cls, timestamp: Optional[float]) -> bool:
        """检查时间戳是否过期"""
        if timestamp is None:
            return True

        expire_time = timestamp + (cls.WEIGHT_EXPIRE_DAYS * 24 * 3600)
        return time.time() > expire_time

    @classmethod
    def _auto_optimize(cls, etf_code: str, weights_file: Path) -> tuple[bool, Optional[Dict], str]:
        """
        自动优化权重（同步，阻塞式）

        使用快速参数，2-5分钟完成
        """
        print(f"\n{'='*70}")
        print(f"[权重管理] {etf_code} 权重文件不存在，开始自动优化...")
        print(f"{'='*70}")
        print(f"目标文件: {weights_file}")
        print(f"使用快速参数（预计2-5分钟）\n")

        try:
            # 导入优化器
            import sys
            sys.path.append('/home/landasika/etf')
            from optimize_etf_advanced import AdvancedETFOptimizer

            # 创建优化器（使用快速参数）
            optimizer = AdvancedETFOptimizer(
                etf_code=etf_code,
                start_date='20240101',  # 只用1年数据
                end_date=None,
                cv_folds=2,              # 2折交叉验证
                test_size=0.2
            )

            # 运行优化（使用小参数）
            result = optimizer.run_optimization()

            if result is None:
                return False, None, '自动优化失败'

            # 从优化结果中提取权重
            weights = result['optimization']['best_weights']

            # 权重已经由优化器保存到文件了
            print(f"\n✅ {etf_code} 权重优化完成！")

            # 缓存权重
            cls._weight_cache[etf_code] = {
                'weights': weights,
                'timestamp': time.time()
            }

            return True, weights, '权重优化完成'

        except Exception as e:
            print(f"\n❌ 自动优化失败: {e}")
            import traceback
            traceback.print_exc()
            return False, None, f'自动优化失败: {e}'

    @classmethod
    def _background_optimize(cls, etf_code: str, weights_file: Path):
        """
        后台优化权重（异步，非阻塞）

        启动后台进程重新优化，不影响当前请求
        """
        import subprocess

        print(f"\n[权重管理] {etf_code} 权重已过期，启动后台优化...")

        try:
            # 创建优化脚本
            script_content = f'''#!/usr/bin/env python3
import sys
sys.path.append('/home/landasika/etf')

from optimize_etf_advanced import AdvancedETFOptimizer

optimizer = AdvancedETFOptimizer(
    etf_code='{etf_code}',
    start_date='20240101',
    end_date=None,
    cv_folds=2,
    test_size=0.2
)

result = optimizer.run_optimization()

if result:
    print(f"\\n✅ {{etf_code}} 后台优化完成")
else:
    print(f"\\n❌ {{etf_code}} 后台优化失败")
'''

            # 写入临时脚本
            script_file = Path(f'/tmp/optimize_{etf_code.replace(".", "_")}.py')
            script_file.write_text(script_content)

            # 后台运行
            subprocess.Popen(
                ['python3', str(script_file)],
                stdout=open(f'/tmp/optimize_{etf_code.replace(".", "_")}.log', 'w'),
                stderr=subprocess.STDOUT
            )

            print(f"后台优化进程已启动: {etf_code}")
            print(f"日志文件: /tmp/optimize_{etf_code.replace('.', '_')}.log")

        except Exception as e:
            print(f"启动后台优化失败: {e}")

    @classmethod
    def get_weight_status(cls, etf_code: str) -> Dict:
        """
        获取权重状态信息

        Returns:
            {
                'exists': bool,           # 文件是否存在
                'expired': bool,          # 是否过期
                'age_days': int,          # 文件年龄（天）
                'file_path': str,         # 文件路径
                'file_size': int,         # 文件大小（字节）
                'cached': bool            # 是否在缓存中
            }
        """
        weights_file = Path(cls.WEIGHT_PATH_PATTERN.format(etf_code=etf_code))

        status = {
            'exists': weights_file.exists(),
            'expired': False,
            'age_days': 0,
            'file_path': str(weights_file),
            'file_size': 0,
            'cached': etf_code in cls._weight_cache
        }

        if status['exists']:
            try:
                stat = weights_file.stat()
                status['file_size'] = stat.st_size

                mtime = stat.st_mtime
                file_date = datetime.fromtimestamp(mtime)
                age = datetime.now() - file_date
                status['age_days'] = age.days

                status['expired'] = cls._is_file_expired(weights_file)
            except:
                pass

        return status

    @classmethod
    def clear_cache(cls, etf_code: str = None):
        """清除缓存"""
        if etf_code:
            cls._weight_cache.pop(etf_code, None)
        else:
            cls._weight_cache.clear()


def get_etf_weights(etf_code: str, auto_optimize: bool = True) -> tuple[bool, Optional[Dict], str]:
    """
    便捷函数：获取ETF权重

    Args:
        etf_code: ETF代码
        auto_optimize: 是否自动优化

    Returns:
        (success, weights, message)
    """
    return WeightManager.get_weights(etf_code, auto_optimize)


def check_weight_status(etf_code: str) -> Dict:
    """
    便捷函数：检查权重状态

    Args:
        etf_code: ETF代码

    Returns:
        权重状态字典
    """
    return WeightManager.get_weight_status(etf_code)
