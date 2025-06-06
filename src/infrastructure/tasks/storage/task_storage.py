# src/infrastructure/tasks/storage/task_storage.py
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import OrderedDict

from src.infrastructure.logging.logger import get_logger
from src.infrastructure.tasks.storage.memory_store import MemoryStore
from src.infrastructure.tasks.storage.s3_store import S3Store
from src.application.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class TaskStorage:
    """
    任务存储系统 - 统一管理内存缓存和持久化存储
    
    功能：
    1. 多层存储：内存 -> S3
    2. 自动清理和垃圾回收
    3. 结果检索和查询
    4. 统计信息收集
    """
    
    def __init__(self):
        self.logger = logger
        
        # 存储后端
        self.memory_store = MemoryStore(
            max_size=settings.task_result_cache_size,
            default_ttl=settings.task_result_cache_ttl
        )
        
        self.s3_store = S3Store() if settings.s3_bucket else None
        
        # 配置
        self.enable_s3_persistence = bool(self.s3_store)
        self.s3_persist_threshold = 86400  # 24小时后持久化到S3
        
        # 性能统计
        self.stats = {
            "total_stored": 0,
            "memory_hits": 0,
            "s3_hits": 0,
            "cache_misses": 0,
            "s3_persists": 0,
            "cleanups": 0
        }
    
    async def store_task(self, task) -> bool:
        """存储任务元数据（仅内存）"""
        task_data = {
            "task_id": task.task_id,
            "task_name": task.task_name,
            "status": task.status.value,
            "priority": task.priority.value,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "timeout": task.timeout,
            "max_retries": task.max_retries,
            "tags": task.tags,
            "metadata": task.metadata
        }
        
        return await self.memory_store.set(f"task:{task.task_id}", task_data, ttl=3600)
    
    async def store_result(self, task_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """存储任务结果"""
        storage_info = {
            "task_id": task_id,
            "stored_at": datetime.utcnow().isoformat(),
            "storage_locations": []
        }
        
        try:
            # 1. 存储到内存
            memory_success = await self.memory_store.set(f"result:{task_id}", result_data)
            if memory_success:
                storage_info["storage_locations"].append("memory")
            
            # 2. 决定是否需要S3持久化
            should_persist = self._should_persist_to_s3(result_data)
            
            if should_persist and self.s3_store:
                s3_result = await self.s3_store.store_result(task_id, result_data)
                if s3_result["success"]:
                    storage_info["storage_locations"].append("s3")
                    storage_info["s3_key"] = s3_result["key"]
                    self.stats["s3_persists"] += 1
            
            self.stats["total_stored"] += 1
            
            self.logger.debug(f"任务结果已存储: {task_id}", extra=storage_info)
            return storage_info
            
        except Exception as e:
            self.logger.error(f"存储任务结果失败: {task_id} - {str(e)}")
            raise
    
    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务结果"""
        # 1. 先从内存获取
        memory_result = await self.memory_store.get(f"result:{task_id}")
        if memory_result:
            self.stats["memory_hits"] += 1
            self.logger.debug(f"内存命中: {task_id}")
            return memory_result
        
        # 2. 从S3获取
        if self.s3_store:
            s3_result = await self.s3_store.get_result(task_id)
            if s3_result:
                # 重新缓存到内存
                await self.memory_store.set(f"result:{task_id}", s3_result, ttl=1800)
                self.stats["s3_hits"] += 1
                self.logger.debug(f"S3命中: {task_id}")
                return s3_result
        
        self.stats["cache_misses"] += 1
        return None
    
    async def delete_result(self, task_id: str, delete_from_s3: bool = False) -> Dict[str, Any]:
        """删除任务结果"""
        deletion_info = {
            "task_id": task_id,
            "deleted_from": [],
            "errors": []
        }
        
        # 从内存删除
        memory_deleted = await self.memory_store.delete(f"result:{task_id}")
        if memory_deleted:
            deletion_info["deleted_from"].append("memory")
        
        # 从S3删除
        if delete_from_s3 and self.s3_store:
            try:
                s3_deleted = await self.s3_store.delete_result(task_id)
                if s3_deleted:
                    deletion_info["deleted_from"].append("s3")
                else:
                    deletion_info["errors"].append("S3删除失败")
            except Exception as e:
                deletion_info["errors"].append(f"S3删除异常: {str(e)}")
        
        return deletion_info
    
    async def search_results(
        self, 
        task_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """搜索任务结果"""
        # 主要从内存搜索
        memory_results = await self.memory_store.search_pattern("result:*", limit=limit)
        
        # 过滤条件
        filtered_results = []
        for result in memory_results:
            if self._matches_search_criteria(result, task_name, status):
                filtered_results.append(result)
        
        return filtered_results[:limit]
    
    async def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取任务历史"""
        # 从内存获取最近的任务
        memory_results = await self.memory_store.get_recent_items("result:*", limit)
        
        # 如果内存中数据不足且有S3，尝试从S3补充
        if len(memory_results) < limit and self.s3_store:
            try:
                s3_results = await self.s3_store.get_recent_results(limit - len(memory_results))
                memory_results.extend(s3_results)
            except Exception as e:
                self.logger.warning(f"从S3获取历史数据失败: {str(e)}")
        
        return memory_results
    
    async def cleanup_old_results(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """清理旧结果"""
        cleanup_info = {
            "memory_cleaned": 0,
            "s3_cleaned": 0,
            "s3_persisted": 0,
            "errors": []
        }
        
        try:
            # 内存清理（包括过期清理）
            memory_cleaned = await self.memory_store.cleanup_expired()
            cleanup_info["memory_cleaned"] = memory_cleaned
            
            # S3持久化逻辑
            if self.s3_store:
                # 获取需要持久化的任务
                old_results = await self.memory_store.get_old_items(hours=max_age_hours)
                
                for result in old_results:
                    try:
                        task_id = self._extract_task_id_from_result(result)
                        if task_id and self._should_persist_to_s3(result):
                            s3_result = await self.s3_store.store_result(task_id, result)
                            if s3_result["success"]:
                                cleanup_info["s3_persisted"] += 1
                                # 从内存中删除已持久化的结果
                                await self.memory_store.delete(f"result:{task_id}")
                    except Exception as e:
                        cleanup_info["errors"].append(f"持久化失败: {str(e)}")
            
            self.stats["cleanups"] += 1
            
            self.logger.info("清理任务完成", extra=cleanup_info)
            return cleanup_info
            
        except Exception as e:
            self.logger.error(f"清理任务失败: {str(e)}")
            cleanup_info["errors"].append(str(e))
            return cleanup_info
    
    async def get_average_execution_time(self) -> float:
        """获取平均执行时间"""
        return await self.memory_store.calculate_average_metric("duration")
    
    async def get_median_execution_time(self) -> float:
        """获取中位执行时间"""
        return await self.memory_store.calculate_median_metric("duration")
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """获取存储统计"""
        memory_stats = self.memory_store.get_statistics()
        
        storage_stats = {
            "memory": memory_stats,
            "s3_enabled": self.enable_s3_persistence,
            "performance": self.stats.copy()
        }
        
        if self.s3_store:
            storage_stats["s3"] = self.s3_store.get_statistics()
        
        return storage_stats
    
    def _should_persist_to_s3(self, result_data: Dict[str, Any]) -> bool:
        """判断是否应该持久化到S3"""
        if not self.enable_s3_persistence:
            return False
        
        # 基于任务类型和结果大小决定
        task_name = result_data.get("task_name", "")
        result_size = len(json.dumps(result_data, default=str))
        
        # 大结果或重要任务类型
        if result_size > 10240:  # > 10KB
            return True
        
        if any(keyword in task_name.lower() for keyword in ["critical", "important", "backup"]):
            return True
        
        # 成功的长时间任务
        if (result_data.get("status") == "success" and 
            result_data.get("duration", 0) > 300):  # > 5分钟
            return True
        
        return False
    
    def _matches_search_criteria(
        self, 
        result: Dict[str, Any], 
        task_name: Optional[str], 
        status: Optional[str]
    ) -> bool:
        """检查结果是否匹配搜索条件"""
        if task_name and result.get("task_name") != task_name:
            return False
        
        if status and result.get("status") != status:
            return False
        
        return True
    
    def _extract_task_id_from_result(self, result: Dict[str, Any]) -> Optional[str]:
        """从结果中提取task_id"""
        return result.get("task_id")