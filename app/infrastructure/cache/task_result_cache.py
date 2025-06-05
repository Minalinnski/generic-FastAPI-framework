# app/infrastructure/cache/task_result_cache.py
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from app.application.config.settings import get_settings
from app.infrastructure.logging.logger import get_logger
from app.schemas.enums.base_enums import TaskStatusEnum

settings = get_settings()
logger = get_logger(__name__)


class TaskResultCache:
    """
    任务结果专用LRU缓存
    
    功能：
    1. LRU策略自动清理老旧结果
    2. 基于任务状态的智能缓存
    3. 支持任务历史查询
    4. 内存使用监控
    """
    
    def __init__(
        self, 
        max_size: Optional[int] = None,
        default_ttl: Optional[int] = None
    ):
        self.max_size = max_size or settings.task_result_cache_size
        self.default_ttl = default_ttl or settings.task_result_cache_ttl
        self.logger = logger
        
        # 使用OrderedDict实现LRU
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._access_times: Dict[str, float] = {}
        self._task_stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_cached": 0
        }
    
    def put(self, task_id: str, task_result: Dict[str, Any]) -> None:
        """存储任务结果"""
        try:
            current_time = time.time()
            
            # 准备缓存数据
            cache_data = {
                "task_id": task_id,
                "result": task_result,
                "cached_at": current_time,
                "expires_at": current_time + self.default_ttl,
                "access_count": 0
            }
            
            # 如果已存在，先删除旧的
            if task_id in self._cache:
                del self._cache[task_id]
                del self._access_times[task_id]
            
            # 检查缓存大小，必要时清理
            self._evict_if_needed()
            
            # 存储新数据
            self._cache[task_id] = cache_data
            self._access_times[task_id] = current_time
            self._task_stats["total_cached"] += 1
            
            self.logger.debug(f"缓存任务结果: {task_id}", extra={
                "cache_size": len(self._cache),
                "max_size": self.max_size
            })
            
        except Exception as e:
            self.logger.error(f"缓存任务结果失败: {task_id} - {str(e)}")
    
    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务结果"""
        try:
            if task_id not in self._cache:
                self._task_stats["misses"] += 1
                return None
            
            cache_data = self._cache[task_id]
            current_time = time.time()
            
            # 检查是否过期
            if cache_data["expires_at"] < current_time:
                self._remove(task_id)
                self._task_stats["misses"] += 1
                return None
            
            # 更新访问信息
            self._cache.move_to_end(task_id)  # LRU更新
            self._access_times[task_id] = current_time
            cache_data["access_count"] += 1
            
            self._task_stats["hits"] += 1
            
            self.logger.debug(f"缓存命中: {task_id}")
            return cache_data["result"]
            
        except Exception as e:
            self.logger.error(f"获取缓存失败: {task_id} - {str(e)}")
            self._task_stats["misses"] += 1
            return None
    
    def remove(self, task_id: str) -> bool:
        """移除指定任务的缓存"""
        return self._remove(task_id)
    
    def _remove(self, task_id: str) -> bool:
        """内部移除方法"""
        if task_id in self._cache:
            del self._cache[task_id]
            del self._access_times[task_id]
            self.logger.debug(f"移除缓存: {task_id}")
            return True
        return False
    
    def _evict_if_needed(self) -> None:
        """根据需要清理缓存"""
        while len(self._cache) >= self.max_size:
            # 移除最久未访问的项目（LRU策略）
            oldest_task_id = next(iter(self._cache))
            self._remove(oldest_task_id)
            self._task_stats["evictions"] += 1
            
            self.logger.debug(f"LRU清理缓存: {oldest_task_id}")
    
    def cleanup_expired(self) -> int:
        """清理所有过期的缓存项"""
        current_time = time.time()
        expired_tasks = []
        
        for task_id, cache_data in self._cache.items():
            if cache_data["expires_at"] < current_time:
                expired_tasks.append(task_id)
        
        for task_id in expired_tasks:
            self._remove(task_id)
        
        if expired_tasks:
            self.logger.info(f"清理过期缓存: {len(expired_tasks)} 个任务")
        
        return len(expired_tasks)
    
    def get_by_status(self, status: TaskStatusEnum) -> List[Dict[str, Any]]:
        """根据状态获取任务结果列表"""
        results = []
        current_time = time.time()
        
        for cache_data in self._cache.values():
            # 检查是否过期
            if cache_data["expires_at"] < current_time:
                continue
            
            task_result = cache_data["result"]
            if task_result.get("status") == status.value:
                results.append(task_result)
        
        return results
    
    def get_recent_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的任务结果"""
        recent_tasks = []
        current_time = time.time()
        
        # 按缓存时间倒序排列
        sorted_cache = sorted(
            self._cache.items(),
            key=lambda x: x[1]["cached_at"],
            reverse=True
        )
        
        count = 0
        for task_id, cache_data in sorted_cache:
            if count >= limit:
                break
            
            # 检查是否过期
            if cache_data["expires_at"] < current_time:
                continue
            
            recent_tasks.append(cache_data["result"])
            count += 1
        
        return recent_tasks
    
    def search_tasks(
        self, 
        task_name: Optional[str] = None,
        status: Optional[TaskStatusEnum] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """搜索任务结果"""
        results = []
        current_time = time.time()
        
        for cache_data in self._cache.values():
            # 检查是否过期
            if cache_data["expires_at"] < current_time:
                continue
            
            task_result = cache_data["result"]
            
            # 过滤条件
            if task_name and task_result.get("task_name") != task_name:
                continue
            
            if status and task_result.get("status") != status.value:
                continue
            
            results.append(task_result)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        current_time = time.time()
        
        # 统计各状态任务数量
        status_counts = {}
        valid_count = 0
        expired_count = 0
        
        for cache_data in self._cache.values():
            if cache_data["expires_at"] < current_time:
                expired_count += 1
                continue
            
            valid_count += 1
            status = cache_data["result"].get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 计算命中率
        total_requests = self._task_stats["hits"] + self._task_stats["misses"]
        hit_rate = self._task_stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "total_cached": len(self._cache),
            "valid_cached": valid_count,
            "expired_cached": expired_count,
            "max_size": self.max_size,
            "memory_usage_percent": (len(self._cache) / self.max_size) * 100,
            "hit_rate": round(hit_rate, 3),
            "statistics": self._task_stats.copy(),
            "status_distribution": status_counts
        }
    
    def clear(self) -> int:
        """清空所有缓存"""
        count = len(self._cache)
        self._cache.clear()
        self._access_times.clear()
        
        self.logger.info(f"清空任务结果缓存: {count} 个任务")
        return count
    
    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存使用信息"""
        import sys
        
        cache_size = sys.getsizeof(self._cache)
        access_times_size = sys.getsizeof(self._access_times)
        
        # 估算数据大小
        total_data_size = 0
        for cache_data in self._cache.values():
            total_data_size += sys.getsizeof(cache_data)
        
        return {
            "cache_structure_bytes": cache_size,
            "access_times_bytes": access_times_size,
            "data_bytes": total_data_size,
            "total_bytes": cache_size + access_times_size + total_data_size,
            "total_mb": round((cache_size + access_times_size + total_data_size) / (1024 * 1024), 2),
            "item_count": len(self._cache)
        }


# 全局任务结果缓存实例
task_result_cache = TaskResultCache()