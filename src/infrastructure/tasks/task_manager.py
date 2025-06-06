# src/infrastructure/tasks/task_manager.py
import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from collections import deque
from contextlib import asynccontextmanager

from src.infrastructure.logging.logger import get_logger
from src.infrastructure.tasks.base_task import BaseTask, TaskPriority, TaskStatus
from src.infrastructure.tasks.storage import TaskStorage
from src.infrastructure.tasks.worker_pool import WorkerPool
from src.infrastructure.tasks.callback_manager import CallbackManager
from src.application.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class TaskManager:
    """
    任务管理器 - 核心调度和执行引擎
    
    功能：
    1. 任务调度和优先级管理
    2. 工作线程池管理
    3. 任务状态跟踪
    4. 结果存储和缓存
    5. 回调处理
    """
    
    def __init__(self):
        self.logger = logger
        
        # 核心组件
        self.storage = TaskStorage()
        self.worker_pool = WorkerPool(max_workers=settings.task_max_workers)
        self.callback_manager = CallbackManager()
        
        # 任务队列 - 按优先级分层
        self.priority_queues = {
            TaskPriority.URGENT: deque(),
            TaskPriority.HIGH: deque(),
            TaskPriority.NORMAL: deque(),
            TaskPriority.LOW: deque()
        }
        
        # 状态跟踪
        self.running_tasks: Dict[str, BaseTask] = {}
        self.task_futures: Dict[str, asyncio.Future] = {}
        
        # 管理状态
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "start_time": time.time()
        }
    
    async def start(self) -> None:
        """启动任务管理器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动核心组件
        await self.worker_pool.start()
        await self.callback_manager.start()
        
        # 启动调度器
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("任务管理器已启动", extra={
            "max_workers": settings.task_max_workers,
            "priority_levels": len(self.priority_queues)
        })
    
    async def shutdown(self) -> None:
        """关闭任务管理器"""
        self._running = False
        
        # 停止调度器
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有运行中的任务
        for task_id in list(self.running_tasks.keys()):
            await self.cancel_task(task_id, "系统关闭")
        
        # 关闭核心组件
        await self.worker_pool.shutdown()
        await self.callback_manager.shutdown()
        
        self.logger.info("任务管理器已关闭")
    
    async def submit_task(self, task: BaseTask, **params) -> str:
        """提交任务"""
        task_id = str(uuid.uuid4())
        task.task_id = task_id
        task.params = params
        task.status = TaskStatus.PENDING
        task.created_at = datetime.utcnow()
        
        # 存储任务
        await self.storage.store_task(task)
        
        # 加入优先级队列
        self.priority_queues[task.priority].append(task)
        
        # 更新统计
        self.stats["total_submitted"] += 1
        
        self.logger.info(f"任务已提交: {task_id}", extra={
            "task_name": task.task_name,
            "priority": task.priority.value,
            "queue_size": self._get_total_queue_size()
        })
        
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        # 先查运行中的任务
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            return task.to_dict()
        
        # 查存储
        return await self.storage.get_task_result(task_id)
    
    async def cancel_task(self, task_id: str, reason: str = "用户取消") -> bool:
        """取消任务"""
        # 如果任务正在运行
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            
            # 标记为取消
            task.status = TaskStatus.CANCELLED
            task.error = reason
            task.end_time = datetime.utcnow()
            
            # 取消Future
            if task_id in self.task_futures:
                self.task_futures[task_id].cancel()
            
            # 存储结果
            await self.storage.store_result(task_id, task.to_dict())
            
            # 清理
            self._cleanup_task_references(task_id)
            
            self.stats["total_cancelled"] += 1
            self.logger.info(f"任务已取消: {task_id}", extra={"reason": reason})
            return True
        
        # 如果任务在队列中
        for queue in self.priority_queues.values():
            for i, task in enumerate(queue):
                if task.task_id == task_id:
                    task.status = TaskStatus.CANCELLED
                    task.error = reason
                    await self.storage.store_result(task_id, task.to_dict())
                    queue.remove(task)
                    self.stats["total_cancelled"] += 1
                    return True
        
        return False
    
    def force_kill_task(self, task_id: str, reason: str = "强制终止") -> bool:
        """强制终止任务"""
        if task_id not in self.running_tasks:
            return False
        
        task = self.running_tasks[task_id]
        task.status = TaskStatus.CANCELLED
        task.error = f"强制终止: {reason}"
        task.end_time = datetime.utcnow()
        
        # 立即取消Future
        if task_id in self.task_futures:
            future = self.task_futures[task_id]
            future.cancel()
        
        self._cleanup_task_references(task_id)
        self.logger.warning(f"任务被强制终止: {task_id}", extra={"reason": reason})
        return True
    
    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息"""
        return {
            "queue_size": self._get_total_queue_size(),
            "running_tasks": len(self.running_tasks),
            "priority_distribution": {
                priority.value: len(queue) 
                for priority, queue in self.priority_queues.items()
            },
            "worker_utilization": self.worker_pool.get_utilization()
        }
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有活跃任务"""
        tasks = []
        
        # 运行中的任务
        for task in self.running_tasks.values():
            tasks.append(task.to_dict())
        
        # 队列中的任务
        for queue in self.priority_queues.values():
            for task in queue:
                tasks.append(task.to_dict())
        
        return tasks
    
    async def _scheduler_loop(self) -> None:
        """调度器主循环"""
        while self._running:
            try:
                await self._schedule_next_task()
                await asyncio.sleep(0.1)  # 避免CPU密集
            except Exception as e:
                self.logger.error(f"调度器错误: {str(e)}")
                await asyncio.sleep(1)
    
    async def _schedule_next_task(self) -> None:
        """调度下一个任务"""
        if not self.worker_pool.has_available_worker():
            return
        
        # 按优先级获取任务
        task = self._get_next_task()
        if not task:
            return
        
        # 分配工作者
        worker = await self.worker_pool.get_worker()
        if not worker:
            # 重新放回队列
            self.priority_queues[task.priority].appendleft(task)
            return
        
        # 执行任务
        await self._execute_task(task, worker)
    
    def _get_next_task(self) -> Optional[BaseTask]:
        """按优先级获取下一个任务"""
        for priority in [TaskPriority.URGENT, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
            queue = self.priority_queues[priority]
            if queue:
                return queue.popleft()
        return None
    
    async def _execute_task(self, task: BaseTask, worker) -> None:
        """执行任务"""
        task_id = task.task_id
        
        # 更新状态
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.utcnow()
        task.worker_id = worker.worker_id
        
        # 记录运行状态
        self.running_tasks[task_id] = task
        
        self.logger.info(f"开始执行任务: {task_id}", extra={
            "task_id": task_id,
            "task_name": task.task_name,
            "task_type": type(task).__name__,
            "worker_id": worker.worker_id,
            "priority": task.priority.value,
            "timeout": task.timeout
        })
        
        # 创建执行Future
        future = asyncio.create_task(self._run_task_with_timeout(task, worker))
        self.task_futures[task_id] = future
        
        # 异步处理结果
        asyncio.create_task(self._handle_task_completion(task, future))
    
    async def _run_task_with_timeout(self, task: BaseTask, worker) -> Any:
        """带超时的任务执行"""
        try:
            self.logger.debug(f"任务开始执行: {task.task_id}", extra={
                "task_id": task.task_id,
                "worker_id": worker.worker_id,
                "has_timeout": bool(task.timeout)
            })
            
            if task.timeout:
                result = await asyncio.wait_for(
                    self.worker_pool.execute_task(task, worker),
                    timeout=task.timeout
                )
            else:
                result = await self.worker_pool.execute_task(task, worker)
            
            self.logger.debug(f"任务执行成功: {task.task_id}", extra={
                "task_id": task.task_id,
                "result_type": type(result).__name__ if result is not None else "None"
            })
            
            return result
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
            self.logger.warning(f"任务执行超时: {task.task_id}", extra={
                "task_id": task.task_id,
                "timeout": task.timeout
            })
            raise
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            self.logger.error(f"任务执行失败: {task.task_id}", extra={
                "task_id": task.task_id,
                "error": str(e),
                "error_type": type(e).__name__
            }, exc_info=True)
            raise
    
    async def _handle_task_completion(self, task: BaseTask, future: asyncio.Future) -> None:
        """处理任务完成"""
        task_id = task.task_id
        
        try:
            result = await future
            
            # 成功完成
            task.status = TaskStatus.SUCCESS
            task.result = result
            task.end_time = datetime.utcnow()
            task.duration = (task.end_time - task.start_time).total_seconds()
            
            self.stats["total_completed"] += 1
            
            self.logger.info(f"任务完成: {task_id}", extra={
                "task_id": task_id,
                "task_name": task.task_name,
                "status": task.status.value,
                "duration": task.duration,
                "worker_id": task.worker_id
            })
            
            # 处理回调
            await self.callback_manager.trigger_callbacks(task, "success")
            
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.end_time = datetime.utcnow()
            if task.start_time:
                task.duration = (task.end_time - task.start_time).total_seconds()
            
            self.logger.info(f"任务被取消: {task_id}", extra={
                "task_id": task_id,
                "task_name": task.task_name
            })
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.end_time = datetime.utcnow()
            if task.start_time:
                task.duration = (task.end_time - task.start_time).total_seconds()
            
            self.stats["total_failed"] += 1
            
            self.logger.error(f"任务失败: {task_id}", extra={
                "task_id": task_id,
                "task_name": task.task_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries
            })
            
            # 重试逻辑
            if task.retry_count < task.max_retries:
                self.logger.info(f"准备重试任务: {task_id}", extra={
                    "task_id": task_id,
                    "retry_count": task.retry_count + 1,
                    "max_retries": task.max_retries
                })
                await self._retry_task(task)
                return
            
            # 处理失败回调
            await self.callback_manager.trigger_callbacks(task, "failed")
        
        finally:
            # 存储结果
            try:
                await self.storage.store_result(task_id, task.to_dict())
                self.logger.debug(f"任务结果已存储: {task_id}")
            except Exception as storage_error:
                self.logger.error(f"存储任务结果失败: {task_id}", extra={
                    "storage_error": str(storage_error)
                })
            
            # 释放工作者
            worker = self.worker_pool.get_worker_by_task(task_id)
            if worker:
                await self.worker_pool.release_worker(worker)
                self.logger.debug(f"工作者已释放: {worker.worker_id}")
            
            # 清理引用
            self._cleanup_task_references(task_id)
    
    async def _retry_task(self, task: BaseTask) -> None:
        """重试任务"""
        task.retry_count += 1
        task.status = TaskStatus.PENDING
        task.start_time = None
        task.end_time = None
        task.worker_id = None
        task.error = None
        
        # 清理当前执行状态
        self._cleanup_task_references(task.task_id)
        
        # 重新加入队列
        self.priority_queues[task.priority].appendleft(task)
        
        self.logger.info(f"任务重试: {task.task_id}", extra={
            "task_id": task.task_id,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "queue_size": len(self.priority_queues[task.priority])
        })
    
    def _cleanup_task_references(self, task_id: str) -> None:
        """清理任务引用"""
        self.running_tasks.pop(task_id, None)
        self.task_futures.pop(task_id, None)
    
    async def _cleanup_loop(self) -> None:
        """清理循环"""
        while self._running:
            try:
                await self.storage.cleanup_old_results()
                await asyncio.sleep(3600)  # 每小时清理一次
            except Exception as e:
                self.logger.error(f"清理任务错误: {str(e)}")
                await asyncio.sleep(60)
    
    def _get_total_queue_size(self) -> int:
        """获取总队列大小"""
        return sum(len(queue) for queue in self.priority_queues.values())
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self.stats["start_time"]
        total_processed = self.stats["total_completed"] + self.stats["total_failed"]
        
        return {
            "runtime": {
                "uptime_seconds": uptime,
                "total_tasks": self.stats["total_submitted"],
                "pending_tasks": self._get_total_queue_size(),
                "running_tasks": len(self.running_tasks),
                "completed_tasks": self.stats["total_completed"],
                "failed_tasks": self.stats["total_failed"],
                "cancelled_tasks": self.stats["total_cancelled"],
                "success_rate": self.stats["total_completed"] / total_processed if total_processed > 0 else 0,
                "queue_size": self._get_total_queue_size(),
                "worker_utilization": self.worker_pool.get_utilization()
            },
            "performance": {
                "avg_execution_time": await self.storage.get_average_execution_time(),
                "median_execution_time": await self.storage.get_median_execution_time(),
                "throughput_per_hour": (total_processed / uptime * 3600) if uptime > 0 else 0
            }
        }


# 全局任务管理器实例
task_manager = TaskManager()