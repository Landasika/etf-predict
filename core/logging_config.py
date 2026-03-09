"""
统一的日志配置模块
支持日志轮转，避免日志文件过大
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(
    name: str,
    log_file: Path,
    level=logging.INFO,
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5,  # 保留5个备份
    also_console=True
) -> logging.Logger:
    """
    设置日志记录器，支持文件轮转

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        level: 日志级别
        max_bytes: 单个日志文件最大大小（字节），默认10MB
        backup_count: 保留的备份文件数量，默认5个
        also_console: 是否同时输出到控制台

    Returns:
        配置好的 Logger 实例
    """
    # 确保日志目录存在
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 文件处理器（使用轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台处理器
    if also_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str, log_file: Path = None) -> logging.Logger:
    """
    获取日志记录器（快捷方式）

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径（可选，默认使用logs目录）

    Returns:
        Logger 实例
    """
    if log_file is None:
        # 默认日志目录
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f'{name}.log'

    return setup_logger(name, log_file)
