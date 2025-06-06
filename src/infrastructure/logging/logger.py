# src/infrastructure/logging/logger.py
import logging
import sys
from functools import lru_cache
from typing import Optional

from src.application.config.settings import get_settings

settings = get_settings()


def setup_logging():
    """Configure application logging based on settings."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # 根据配置选择格式
    if settings.log_format == "json":
        # 简单的JSON格式
        log_format = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    else:
        # 传统格式，添加更多信息
        log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True  # 覆盖已有配置
    )
    
    # 确保我们的应用日志级别正确
    app_logger = logging.getLogger("src")
    app_logger.setLevel(log_level)
    
    # Set lower level for noisy libraries
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {settings.log_level}, format: {settings.log_format}")


@lru_cache()
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a named logger.
    
    Args:
        name: Logger name, typically __name__ of the module
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name or __name__)


# 兼容性：保留一些简单的辅助函数
class LoggerMixin:
    """日志混入类，为其他类提供日志功能"""
    
    @property
    def logger(self) -> logging.Logger:
        return get_logger(self.__class__.__name__)


def log_exception(exc: Exception, context: dict = None, logger_name: str = None):
    """记录异常日志"""
    logger = get_logger(logger_name)
    logger.error(f"Exception occurred: {exc.__class__.__name__}: {str(exc)}", 
                extra={"context": context or {}}, exc_info=True)