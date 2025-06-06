# src/application/services/system/task_service.py (更新版)
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.application.services.service_interface import BaseService
from src.infrastructure.tasks.task_manager import task_manager
from src.infrastructure.tasks.task_registry import TaskRegistry


class TaskService(BaseService):
    """任务管理服务 - 使用新的存储系统"""
    
    def __init__(self):
        super().__init__()
        self.task_manager = task_manager
        self.task_registry = TaskRegistry()
    
    def get_service_info(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "description": "任务管理和监控服务",
            "version": "2.0.0",
            "category": "system",
            "features": ["task_monitoring", "unified_storage", "callback_support"]
        }
    
    async def get_task_registry_info(self) -> Dict[str, Any]:
        """获取任务注册表信息"""
        return {
            "task_types": self.task_registry.get_task_types(),
            "execution_stats": self.task_registry.get_task_stats(),
            "summary": self.task_registry.get_registry_summary()
        }
    
    async def search_task_types(self, query: str) -> List[Dict[str, Any]]:
        """搜索任务类型"""
        return self.task_registry.search_tasks(query)
    
    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务结果（统一存储）"""
        return await self.task_manager.storage.get_task_result(task_id)
    
    async def delete_task_result(self, task_id: str, delete_from_s3: bool = False) -> Dict[str, Any]:
        """删除任务结果"""
        return await self.task_manager.storage.delete_result(task_id, delete_from_s3)
    
    async def force_kill_task(self, task_id: str, reason: str = "手动终止") -> Dict[str, Any]:
        """强制终止任务"""
        success = self.task_manager.force_kill_task(task_id, reason)
        
        return {
            "task_id": task_id,
            "killed": success,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_storage_statistics(self) -> Dict[str, Any]:
        """获取存储统计"""
        return self.task_manager.storage.get_storage_statistics()
    
    async def cleanup_old_results(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """清理旧结果"""
        return await self.task_manager.storage.cleanup_old_results(max_age_hours)
    
    async def get_task_statistics(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        return await self.task_manager.get_statistics()
    
    async def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取任务历史"""
        return await self.task_manager.storage.get_task_history(limit)
    
    async def scale_workers(self, target_count: int) -> Dict[str, Any]:
        """动态调整工作者数量"""
        return await self.task_manager.worker_pool.scale_workers(target_count)