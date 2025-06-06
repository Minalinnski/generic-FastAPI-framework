# src/application/services/service_interface.py (更新)
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from functools import lru_cache

from src.application.config.settings import get_settings
from src.infrastructure.logging.logger import get_logger
from src.infrastructure.cache.cache_interface import CacheInterface, InMemoryCache

settings = get_settings()


class BaseService(ABC):
    """
    基础服务接口 - 专注业务逻辑，不关心Task管理
    """
    
    def __init__(self, cache: Optional[CacheInterface] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.settings = settings
        self.cache = cache or InMemoryCache()
        self.service_name = self.__class__.__name__
    
    @abstractmethod
    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息 - 子类必须实现"""
        pass
    
    async def _cache_get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            return await self.cache.get(key)
        except Exception as e:
            self.logger.warning(f"缓存获取失败: {key} - {str(e)}")
            return None
    
    async def _cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存"""
        try:
            return await self.cache.set(key, value, ttl)
        except Exception as e:
            self.logger.warning(f"缓存设置失败: {key} - {str(e)}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """服务健康检查"""
        return {
            "service": self.service_name,
            "status": "healthy"
        }
    
    # Task相关的便捷方法（可选使用）
    def get_task_config(self) -> Dict[str, Any]:
        """获取服务的默认Task配置"""
        return {
            "default_timeout": 300,
            "default_priority": 0,
            "default_max_retries": 2
        }


@lru_cache()
def get_service_dependencies() -> dict:
    """获取服务层依赖"""
    return {
        "settings": settings,
        "cache": InMemoryCache(
            max_size=settings.cache_max_size,
            default_ttl=settings.cache_default_ttl
        )
    }
