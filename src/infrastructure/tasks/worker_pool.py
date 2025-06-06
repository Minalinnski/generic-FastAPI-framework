# src/infrastructure/tasks/worker_pool.py
import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from src.infrastructure.logging.logger import get_logger
from src.application.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class Worker:
    """工作者"""
    worker_id: str
    is_busy: bool = False
    current_task_id: Optional[str] = None
    created_at: datetime = None
    last_used_at: Optional[datetime] = None
    tasks_completed: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class WorkerPool:
    """
    工作线程池 - 管理任务执行的工作者
    
    功能：
    1. 工作者生命周期管理
    2. 任务分配和负载均衡
    3. 工作者健康监控
    4. 性能统计
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        # 从配置获取工作者数量
        self.max_workers = max_workers or settings.task_max_workers
        self.logger = logger
        
        # 工作者管理
        self.workers: Dict[str, Worker] = {}
        self.available_workers: Set[str] = set()
        self.busy_workers: Set[str] = set()
        
        # 任务到工作者的映射
        self.task_to_worker: Dict[str, str] = {}
        
        # 统计信息
        self.stats = {
            "workers_created": 0,
            "tasks_executed": 0,
            "tasks_failed": 0,
            "total_execution_time": 0.0
        }
        
        self._running = False
    
    async def start(self) -> None:
        """启动工作线程池"""
        if self._running:
            return
        
        self._running = True
        
        # 创建初始工作者
        for i in range(self.max_workers):
            await self._create_worker()
        
        self.logger.info(f"工作线程池已启动", extra={
            "max_workers": self.max_workers,
            "config_source": "settings.task_max_workers"
        })
    
    async def shutdown(self) -> None:
        """关闭工作线程池"""
        self._running = False
        
        # 等待所有忙碌的工作者完成
        timeout = 30  # 30秒超时
        start_time = datetime.utcnow()
        
        while self.busy_workers:
            if (datetime.utcnow() - start_time).total_seconds() > timeout:
                self.logger.warning(f"工作线程池关闭超时，强制终止 {len(self.busy_workers)} 个工作者")
                break
            await asyncio.sleep(0.1)
        
        self.workers.clear()
        self.available_workers.clear()
        self.busy_workers.clear()
        self.task_to_worker.clear()
        
        self.logger.info("工作线程池已关闭")
    
    def has_available_worker(self) -> bool:
        """检查是否有可用工作者"""
        return len(self.available_workers) > 0
    
    async def get_worker(self) -> Optional[Worker]:
        """获取可用工作者"""
        if not self.available_workers:
            self.logger.debug("没有可用工作者")
            return None
        
        worker_id = self.available_workers.pop()
        worker = self.workers[worker_id]
        
        # 标记为忙碌
        worker.is_busy = True
        worker.last_used_at = datetime.utcnow()
        self.busy_workers.add(worker_id)
        
        self.logger.debug(f"分配工作者: {worker_id}")
        return worker
    
    async def release_worker(self, worker: Worker) -> None:
        """释放工作者"""
        worker_id = worker.worker_id
        
        if worker_id in self.workers:
            # 重置状态
            worker.is_busy = False
            worker.current_task_id = None
            worker.tasks_completed += 1
            
            # 更新集合
            self.busy_workers.discard(worker_id)
            self.available_workers.add(worker_id)
            
            # 清理任务映射
            task_id_to_remove = None
            for task_id, w_id in self.task_to_worker.items():
                if w_id == worker_id:
                    task_id_to_remove = task_id
                    break
            
            if task_id_to_remove:
                del self.task_to_worker[task_id_to_remove]
            
            self.logger.debug(f"释放工作者: {worker_id}")
    
    def get_worker_by_task(self, task_id: str) -> Optional[Worker]:
        """根据任务ID获取工作者"""
        worker_id = self.task_to_worker.get(task_id)
        if worker_id:
            return self.workers.get(worker_id)
        return None
    
    async def execute_task(self, task, worker: Worker) -> Any:
        """通过工作者执行任务"""
        return await self._execute_task_internal(task, worker)
    
    async def _execute_task_internal(self, task, worker: Worker) -> Any:
        """执行任务内部实现"""
        task_id = task.task_id
        worker.current_task_id = task_id
        self.task_to_worker[task_id] = worker.worker_id
        
        start_time = datetime.utcnow()
        
        self.logger.info(f"工作者 {worker.worker_id} 开始执行任务 {task_id}", extra={
            "worker_id": worker.worker_id,
            "task_id": task_id,
            "task_name": getattr(task, 'task_name', 'unknown'),
            "task_type": type(task).__name__
        })
        
        try:
            # 直接执行任务的execute方法
            result = await task.execute()
            
            # 更新统计
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.stats["tasks_executed"] += 1
            self.stats["total_execution_time"] += execution_time
            
            self.logger.info(f"工作者 {worker.worker_id} 完成任务 {task_id}", extra={
                "worker_id": worker.worker_id,
                "task_id": task_id,
                "execution_time": execution_time,
                "result_type": type(result).__name__ if result is not None else "None"
            })
            
            return result
            
        except Exception as e:
            self.stats["tasks_failed"] += 1
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.error(f"工作者 {worker.worker_id} 执行任务 {task_id} 失败", extra={
                "worker_id": worker.worker_id,
                "task_id": task_id,
                "execution_time": execution_time,
                "error": str(e),
                "error_type": type(e).__name__
            }, exc_info=True)
            raise
    
    async def _create_worker(self) -> Worker:
        """创建新工作者"""
        worker_id = f"worker_{uuid.uuid4().hex[:8]}"
        worker = Worker(worker_id=worker_id)
        
        self.workers[worker_id] = worker
        self.available_workers.add(worker_id)
        self.stats["workers_created"] += 1
        
        self.logger.debug(f"创建工作者: {worker_id}")
        return worker
    
    def get_utilization(self) -> float:
        """获取工作者利用率"""
        if not self.workers:
            return 0.0
        
        return len(self.busy_workers) / len(self.workers)
    
    async def scale_workers(self, target_count: int) -> Dict[str, Any]:
        """动态调整工作者数量"""
        current_count = len(self.workers)
        
        if target_count == current_count:
            return {"action": "no_change", "current": current_count}
        
        if target_count > current_count:
            # 扩容
            added = 0
            for i in range(target_count - current_count):
                await self._create_worker()
                added += 1
            
            self.logger.info(f"工作者扩容: {current_count} -> {len(self.workers)}")
            return {"action": "scale_up", "added": added, "total": len(self.workers)}
        
        else:
            # 缩容 - 只移除空闲工作者
            to_remove = current_count - target_count
            removed = 0
            
            available_list = list(self.available_workers)
            for worker_id in available_list[:to_remove]:
                self.available_workers.remove(worker_id)
                del self.workers[worker_id]
                removed += 1
            
            self.logger.info(f"工作者缩容: {current_count} -> {len(self.workers)}")
            return {"action": "scale_down", "removed": removed, "total": len(self.workers)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_execution_time = 0.0
        if self.stats["tasks_executed"] > 0:
            avg_execution_time = self.stats["total_execution_time"] / self.stats["tasks_executed"]
        
        return {
            "configuration": {
                "max_workers": self.max_workers,
                "config_source": "settings.task_max_workers"
            },
            "current_state": {
                "total_workers": len(self.workers),
                "available_workers": len(self.available_workers),
                "busy_workers": len(self.busy_workers),
                "utilization": self.get_utilization()
            },
            "performance": {
                "avg_execution_time": avg_execution_time,
                "tasks_executed": self.stats["tasks_executed"],
                "tasks_failed": self.stats["tasks_failed"],
                "success_rate": (
                    self.stats["tasks_executed"] / 
                    (self.stats["tasks_executed"] + self.stats["tasks_failed"])
                ) if (self.stats["tasks_executed"] + self.stats["tasks_failed"]) > 0 else 0
            },
            "worker_details": [
                {
                    "worker_id": worker.worker_id,
                    "is_busy": worker.is_busy,
                    "current_task_id": worker.current_task_id,
                    "tasks_completed": worker.tasks_completed,
                    "created_at": worker.created_at.isoformat(),
                    "last_used_at": worker.last_used_at.isoformat() if worker.last_used_at else None
                }
                for worker in self.workers.values()
            ]
        }