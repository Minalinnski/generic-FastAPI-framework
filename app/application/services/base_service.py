
# app/application/services/base_service.py
from abc import ABC
from typing import Any, Dict, Optional

from app.application.config.settings import get_settings
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.cache.cache_interface import CacheInterface, InMemoryCache

settings = get_settings()


class BaseService(ABC):
    """基础服务类，提供通用的服务功能"""
    
    def __init__(self, cache: Optional[CacheInterface] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.settings = settings
        self.cache = cache or InMemoryCache()
    
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