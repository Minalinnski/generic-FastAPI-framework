# src/infrastructure/cache/cache_interface.py
import asyncio
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Union

from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class CacheInterface(ABC):
    """缓存接口抽象类"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """异步获取缓存值"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """异步设置缓存值"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """异步删除缓存值"""
        pass
    
    @abstractmethod
    async def clear_pattern(self, pattern: str) -> int:
        """异步清理匹配模式的缓存"""
        pass
    
    @abstractmethod
    def get_sync(self, key: str) -> Optional[Any]:
        """同步获取缓存值"""
        pass
    
    @abstractmethod
    def set_sync(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """同步设置缓存值"""
        pass
    
    @abstractmethod
    def delete_sync(self, key: str) -> bool:
        """同步删除缓存值"""
        pass


class InMemoryCache(CacheInterface):
    """内存缓存实现（LRU策略）"""
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.logger = logger
        
        # 使用OrderedDict实现LRU
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        
        # 统计信息
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """异步获取缓存值"""
        async with self._lock:
            return self._get_internal(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """异步设置缓存值"""
        async with self._lock:
            return self._set_internal(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """异步删除缓存值"""
        async with self._lock:
            return self._delete_internal(key)
    
    async def clear_pattern(self, pattern: str) -> int:
        """异步清理匹配模式的缓存"""
        async with self._lock:
            return self._clear_pattern_internal(pattern)
    
    def get_sync(self, key: str) -> Optional[Any]:
        """同步获取缓存值"""
        return self._get_internal(key)
    
    def set_sync(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """同步设置缓存值"""
        return self._set_internal(key, value, ttl)
    
    def delete_sync(self, key: str) -> bool:
        """同步删除缓存值"""
        return self._delete_internal(key)
    
    def _get_internal(self, key: str) -> Optional[Any]:
        """内部获取方法"""
        if key not in self._cache:
            self._stats["misses"] += 1
            return None
        
        cache_item = self._cache[key]
        current_time = time.time()
        
        # 检查是否过期
        if cache_item["expires_at"] < current_time:
            del self._cache[key]
            self._stats["misses"] += 1
            return None
        
        # 更新LRU顺序
        self._cache.move_to_end(key)
        self._stats["hits"] += 1
        
        return cache_item["value"]
    
    def _set_internal(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """内部设置方法"""
        try:
            expires_at = time.time() + (ttl or self.default_ttl)
            
            # 如果key已存在，先删除
            if key in self._cache:
                del self._cache[key]
            
            # 检查是否需要清理空间
            self._evict_if_needed()
            
            # 存储新值
            self._cache[key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": expires_at
            }
            
            self._stats["sets"] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"设置缓存失败: {key} - {str(e)}")
            return False
    
    def _delete_internal(self, key: str) -> bool:
        """内部删除方法"""
        if key in self._cache:
            del self._cache[key]
            self._stats["deletes"] += 1
            return True
        return False
    
    def _clear_pattern_internal(self, pattern: str) -> int:
        """内部模式清理方法"""
        import fnmatch
        
        keys_to_delete = [
            key for key in self._cache.keys() 
            if fnmatch.fnmatch(key, pattern)
        ]
        
        for key in keys_to_delete:
            del self._cache[key]
        
        return len(keys_to_delete)
    
    def _evict_if_needed(self) -> None:
        """LRU清理"""
        while len(self._cache) >= self.max_size:
            # 删除最久未使用的项
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._stats["evictions"] += 1
    
    def cleanup_expired(self) -> int:
        """清理过期项"""
        current_time = time.time()
        expired_keys = [
            key for key, item in self._cache.items()
            if item["expires_at"] < current_time
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "memory_usage_percent": (len(self._cache) / self.max_size) * 100,
            "hit_rate": round(hit_rate, 3),
            "statistics": self._stats.copy()
        }
    
    def clear_all(self) -> int:
        """清空所有缓存"""
        count = len(self._cache)
        self._cache.clear()
        return count


class RedisCache(CacheInterface):
    """Redis缓存实现（需要redis依赖）"""
    
    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.logger = logger
        self._redis = None
    
    async def _get_redis(self):
        """获取Redis连接"""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url)
            except ImportError:
                self.logger.error("Redis library not installed. Use: pip install redis")
                raise
        return self._redis
    
    async def get(self, key: str) -> Optional[Any]:
        """异步获取缓存值"""
        try:
            redis_client = await self._get_redis()
            value = await redis_client.get(key)
            
            if value is None:
                return None
            
            # 反序列化（这里简化，实际可能需要更复杂的序列化）
            import json
            return json.loads(value)
            
        except Exception as e:
            self.logger.error(f"Redis获取失败: {key} - {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """异步设置缓存值"""
        try:
            redis_client = await self._get_redis()
            
            # 序列化（这里简化，实际可能需要更复杂的序列化）
            import json
            serialized_value = json.dumps(value, default=str)
            
            await redis_client.set(key, serialized_value, ex=ttl or self.default_ttl)
            return True
            
        except Exception as e:
            self.logger.error(f"Redis设置失败: {key} - {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """异步删除缓存值"""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.delete(key)
            return result > 0
            
        except Exception as e:
            self.logger.error(f"Redis删除失败: {key} - {str(e)}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """异步清理匹配模式的缓存"""
        try:
            redis_client = await self._get_redis()
            keys = await redis_client.keys(pattern)
            
            if keys:
                deleted = await redis_client.delete(*keys)
                return deleted
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Redis模式清理失败: {pattern} - {str(e)}")
            return 0
    
    def get_sync(self, key: str) -> Optional[Any]:
        """同步获取缓存值"""
        # 对于Redis，建议使用异步版本
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get(key))
    
    def set_sync(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """同步设置缓存值"""
        # 对于Redis，建议使用异步版本
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.set(key, value, ttl))
    
    def delete_sync(self, key: str) -> bool:
        """同步删除缓存值"""
        # 对于Redis，建议使用异步版本
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.delete(key))