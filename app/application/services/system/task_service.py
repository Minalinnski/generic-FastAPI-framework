# app/application/services/system/task_service.py (更新)
from app.application.services.service_interface import BaseService
from app.infrastructure.tasks.task_manager import task_manager
from app.infrastructure.tasks.enhanced_task_registry import TaskRegistry
from app.infrastructure.tasks.result_storage import TaskResultStorage


class TaskService(BaseService):
    """任务管理服务 - 增强版"""
    
    def __init__(self):
        super().__init__()
        self.task_manager = task_manager
        self.task_registry = TaskRegistry()
        self.result_storage = TaskResultStorage()
    
    def get_service_info(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "description": "增强的任务管理和监控服务",
            "version": "2.0.0",
            "category": "system",
            "features": ["task_monitoring", "result_storage", "s3_persistence"]
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
        """获取任务结果（支持S3）"""
        return await self.result_storage.get_result(task_id)
    
    async def delete_task_result(self, task_id: str, delete_from_s3: bool = False) -> Dict[str, Any]:
        """删除任务结果"""
        return await self.result_storage.delete_result(task_id, delete_from_s3)
    
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
        return self.result_storage.get_storage_stats()
    
    async def cleanup_system(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """清理系统"""
        # 清理结果存储
        storage_cleanup = await self.result_storage.cleanup_old_results(max_age_hours)
        
        # 清理任务管理器历史
        manager_cleanup = self.task_manager.cleanup_completed_tasks(1000)
        
        return {
            "storage_cleanup": storage_cleanup,
            "manager_cleanup": manager_cleanup,
            "cleaned_at": datetime.utcnow().isoformat()
        }