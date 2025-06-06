# src/infrastructure/tasks/storage/memory_store.py
import time
import fnmatch
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import OrderedDict

from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class MemoryStore:
    """
    内存存储后端 - LRU缓存实现
    
    功能：
    1. LRU策略的内存缓存
    2. TTL过期管理
    3. 模式匹配搜索
    4. 统计信息收集
    """
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.logger = logger
        
        # LRU缓存
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        
        # 统计信息
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "expired_cleanups": 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self._cache:
            self._stats["misses"] += 1
            return None
        
        cache_item = self._cache[key]
        current_time = time.time()
        
        # 检查过期
        if cache_item["expires_at"] < current_time:
            del self._cache[key]
            self._stats["misses"] += 1
            return None
        
        # LRU更新
        self._cache.move_to_end(key)
        self._stats["hits"] += 1
        
        return cache_item["value"]
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            expires_at = time.time() + (ttl or self.default_ttl)
            
            # 如果键已存在，先删除
            if key in self._cache:
                del self._cache[key]
            
            # 检查容量
            self._evict_if_needed()
            
            # 存储新值
            self._cache[key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": expires_at,
                "access_count": 0
            }
            
            self._stats["sets"] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"设置缓存失败: {key} - {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        if key in self._cache:
            del self._cache[key]
            self._stats["deletes"] += 1
            return True
        return False
    
    async def search_pattern(self, pattern: str, limit: int = 100) -> List[Dict[str, Any]]:
        """按模式搜索"""
        results = []
        current_time = time.time()
        
        for key, cache_item in self._cache.items():
            if len(results) >= limit:
                break
            
            # 检查过期
            if cache_item["expires_at"] < current_time:
                continue
            
            # 模式匹配
            if fnmatch.fnmatch(key, pattern):
                results.append(cache_item["value"])
        
        return results
    
    async def get_recent_items(self, pattern: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的项目"""
        items = []
        current_time = time.time()
        
        # 按创建时间排序
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1]["created_at"],
            reverse=True
        )
        
        for key, cache_item in sorted_items:
            if len(items) >= limit:
                break
            
            # 检查过期
            if cache_item["expires_at"] < current_time:
                continue
            
            # 模式匹配
            if fnmatch.fnmatch(key, pattern):
                items.append(cache_item["value"])
        
        return items
    
    async def get_old_items(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取旧项目"""
        items = []
        cutoff_time = time.time() - (hours * 3600)
        current_time = time.time()
        
        for cache_item in self._cache.values():
            # 检查是否过期
            if cache_item["expires_at"] < current_time:
                continue
            
            # 检查是否足够老
            if cache_item["created_at"] < cutoff_time:
                items.append(cache_item["value"])
        
        return items
    
    async def cleanup_expired(self) -> int:
        """清理过期项"""
        current_time = time.time()
        expired_keys = []
        
        for key, cache_item in self._cache.items():
            if cache_item["expires_at"] < current_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._stats["expired_cleanups"] += len(expired_keys)
            self.logger.debug(f"清理过期项: {len(expired_keys)}")
        
        return len(expired_keys)
    
    async def calculate_average_metric(self, metric_name: str) -> float:
        """计算平均指标"""
        values = []
        current_time = time.time()
        
        for cache_item in self._cache.values():
            if cache_item["expires_at"] < current_time:
                continue
            
            value = cache_item["value"]
            if isinstance(value, dict) and metric_name in value:
                metric_value = value[metric_name]
                if isinstance(metric_value, (int, float)):
                    values.append(metric_value)
        
        return statistics.mean(values) if values else 0.0
    
    async def calculate_median_metric(self, metric_name: str) -> float:
        """计算中位指标"""
        values = []
        current_time = time.time()
        
        for cache_item in self._cache.values():
            if cache_item["expires_at"] < current_time:
                continue
            
            value = cache_item["value"]
            if isinstance(value, dict) and metric_name in value:
                metric_value = value[metric_name]
                if isinstance(metric_value, (int, float)):
                    values.append(metric_value)
        
        return statistics.median(values) if values else 0.0
    
    def _evict_if_needed(self) -> None:
        """LRU清理"""
        while len(self._cache) >= self.max_size:
            # 删除最久未使用的项
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._stats["evictions"] += 1
    
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