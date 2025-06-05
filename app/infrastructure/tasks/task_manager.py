# app/infrastructure/tasks/task_manager.py
import asyncio
import heapq
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from app.application.config.settings import get_settings
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.cache.task_result_cache import task_result_cache
from app.infrastructure.tasks.base_task import BaseTask, TaskPriority, TaskResult
from app.schemas.enums.base_enums import TaskStatusEnum

settings = get_settings()
logger = get_logger(__name__)


class TaskExecutor:
    """任务执行器 - 负责具体的任务执行"""
    
    def __init__(self, executor_id: str, task_manager: "TaskManager"):
        self.executor_id = executor_id
        self.task_manager = task_manager
        self.logger = logger
        self.current_task: Optional[BaseTask] = None
        self.is_busy = False
        self.start_time = datetime.utcnow()
        self.completed_tasks = 0
        
    async def execute_task(self, task: BaseTask) -> None:
        """执行单个任务"""
        self.current_task = task
        self.is_busy = True
        
        try:
            # 开始执行
            task.start_execution(worker_id=self.executor_id)
            
            self.logger.info(f"开始执行任务: {task.task_name}", extra={
                "task_id": task.task_id,
                "executor_id": self.executor_id,
                "priority": task.priority.name
            })
            
            # 执行任务（带超时控制）
            if task.timeout:
                result = await asyncio.wait_for(
                    task.execute(**task.metadata), 
                    timeout=task.timeout
                )
            else:
                result = await task.execute(**task.metadata)
            
            # 设置结果
            task.set_result(result)
            task.finish_execution()
            
            # 缓存结果
            task_result_cache.put(task.task_id, task.get_status_info())
            
            # 更新统计
            self.completed_tasks += 1
            
            self.logger.info(f"任务执行成功: {task.task_name}", extra={
                "task_id": task.task_id,
                "duration": task.duration,
                "executor_id": self.executor_id
            })
            
        except asyncio.TimeoutError:
            task.timeout()
            task_result_cache.put(task.task_id, task.get_status_info())
            
            self.logger.error(f"任务执行超时: {task.task_name}", extra={
                "task_id": task.task_id,
                "timeout": task.timeout,
                "executor_id": self.executor_id
            })
            
        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_module": type(e).__module__,
                "executor_id": self.executor_id
            }
            
            task.set_error(str(e), error_details)
            task.finish_execution()
            task_result_cache.put(task.task_id, task.get_status_info())
            
            self.logger.error(f"任务执行失败: {task.task_name}", extra={
                "task_id": task.task_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "executor_id": self.executor_id
            })
            
        finally:
            # 通知任务管理器任务完成
            await self.task_manager._on_task_completed(task)
            self.current_task = None
            self.is_busy = False
    
    def cancel_current_task(self, reason: str = "执行器关闭") -> bool:
        """取消当前执行的任务"""
        if self.current_task and self.is_busy:
            return self.current_task.cancel(reason)
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取执行器统计信息"""
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        return {
            "executor_id": self.executor_id,
            "is_busy": self.is_busy,
            "current_task": self.current_task.task_id if self.current_task else None,
            "completed_tasks": self.completed_tasks,
            "uptime_seconds": uptime,
            "tasks_per_hour": (self.completed_tasks / uptime * 3600) if uptime > 0 else 0
        }


class TaskManager:
    """
    任务管理器
    
    核心功能：
    1. 任务排队（优先级队列）
    2. 并发控制和负载均衡
    3. 状态追踪和监控
    4. 超时处理和自动重试
    5. 任务生命周期管理
    6. 性能监控和统计
    """
    
    def __init__(self):
        self.logger = logger
        self.max_workers = settings.task_max_workers
        self.result_cache = task_result_cache
        
        # 任务存储
        self.active_tasks: Dict[str, BaseTask] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        
        # 任务队列（优先级队列）
        self.task_queue: List[BaseTask] = []
        self.queue_lock = asyncio.Lock()
        
        # 执行器管理
        self.executors: Dict[str, TaskExecutor] = {}
        self.executor_tasks: Dict[str, asyncio.Task] = {}
        
        # 控制标志
        self.is_running = False
        self.is_shutting_down = False
        
        # 监控和统计
        self.stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "total_timeout": 0,
            "total_retried": 0
        }
        
        # 任务类型统计
        self.task_type_stats: Dict[str, Dict[str, int]] = {}
        
        # 重试队列
        self.retry_queue: List[BaseTask] = []
        
        # 监控任务
        self.monitor_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # 初始化执行器
        self._initialize_executors()
    
    def _initialize_executors(self) -> None:
        """初始化任务执行器"""
        for i in range(self.max_workers):
            executor_id = f"executor_{i}"
            self.executors[executor_id] = TaskExecutor(executor_id, self)
        
        self.logger.info(f"初始化 {self.max_workers} 个任务执行器")
    
    async def start(self) -> None:
        """启动任务管理器"""
        if self.is_running:
            self.logger.warning("任务管理器已在运行")
            return
        
        self.is_running = True
        self.is_shutting_down = False
        
        # 启动监控任务
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("任务管理器已启动", extra={
            "max_workers": self.max_workers,
            "executor_count": len(self.executors)
        })
    
    async def stop(self) -> None:
        """停止任务管理器"""
        if not self.is_running:
            return
        
        self.logger.info("正在停止任务管理器...")
        self.is_shutting_down = True
        
        # 取消所有正在执行的任务
        for executor in self.executors.values():
            executor.cancel_current_task("系统关闭")
        
        # 等待执行器任务完成
        if self.executor_tasks:
            await asyncio.gather(*self.executor_tasks.values(), return_exceptions=True)
        
        # 停止监控任务
        if self.monitor_task:
            self.monitor_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        self.is_running = False
        self.logger.info("任务管理器已停止")
    
    async def submit_task(self, task: BaseTask, **kwargs) -> str:
        """提交任务到队列"""
        if self.is_shutting_down:
            raise RuntimeError("任务管理器正在关闭，无法接受新任务")
        
        try:
            # 更新任务元数据
            task.metadata.update(kwargs)
            
            # 记录提交统计
            self.stats["total_submitted"] += 1
            self._update_task_type_stats(task.task_name, "submitted")
            
            # 添加到队列
            async with self.queue_lock:
                heapq.heappush(self.task_queue, task)
            
            # 保存任务引用
            self.active_tasks[task.task_id] = task
            
            self.logger.info(f"任务已提交: {task.task_name}", extra={
                "task_id": task.task_id,
                "priority": task.priority.name,
                "queue_size": len(self.task_queue)
            })
            
            # 触发任务处理
            asyncio.create_task(self._process_queue())
            
            return task.task_id
            
        except Exception as e:
            self.logger.error(f"提交任务失败: {str(e)}", extra={
                "task_name": task.task_name,
                "error": str(e)
            })
            raise
    
    async def _process_queue(self) -> None:
        """处理任务队列"""
        if self.is_shutting_down:
            return
        
        # 检查是否有可用的执行器
        available_executors = [
            executor for executor in self.executors.values() 
            if not executor.is_busy
        ]
        
        if not available_executors:
            return
        
        # 处理队列中的任务
        tasks_to_process = []
        
        async with self.queue_lock:
            while self.task_queue and len(tasks_to_process) < len(available_executors):
                task = heapq.heappop(self.task_queue)
                
                # 检查任务是否已被取消
                if task.status == TaskStatusEnum.CANCELLED:
                    continue
                
                tasks_to_process.append(task)
        
        # 分配任务给执行器
        for task, executor in zip(tasks_to_process, available_executors):
            executor_task = asyncio.create_task(executor.execute_task(task))
            self.executor_tasks[task.task_id] = executor_task
    
    async def _on_task_completed(self, task: BaseTask) -> None:
        """任务完成回调"""
        # 从执行器任务中移除
        if task.task_id in self.executor_tasks:
            del self.executor_tasks[task.task_id]
        
        # 从活跃任务中移除
        if task.task_id in self.active_tasks:
            del self.active_tasks[task.task_id]
        
        # 更新统计
        if task.status == TaskStatusEnum.SUCCESS:
            self.stats["total_completed"] += 1
            self._update_task_type_stats(task.task_name, "completed")
        elif task.status == TaskStatusEnum.FAILED:
            self.stats["total_failed"] += 1
            self._update_task_type_stats(task.task_name, "failed")
            
            # 检查是否需要重试
            if task.can_retry():
                await self._schedule_retry(task)
        elif task.status == TaskStatusEnum.CANCELLED:
            self.stats["total_cancelled"] += 1
            self._update_task_type_stats(task.task_name, "cancelled")
        elif task.status == TaskStatusEnum.TIMEOUT:
            self.stats["total_timeout"] += 1
            self._update_task_type_stats(task.task_name, "timeout")
        
        # 保存到完成任务
        task_result = task.to_result()
        self.completed_tasks[task.task_id] = task_result
        
        # 继续处理队列
        asyncio.create_task(self._process_queue())
    
    async def _schedule_retry(self, task: BaseTask) -> None:
        """安排任务重试"""
        task.increment_retry()
        task.set_status(TaskStatusEnum.PENDING)
        
        # 计算重试延迟（指数退避）
        delay = min(2 ** task.retry_count, 60)  # 最大60秒
        
        self.logger.info(f"安排任务重试: {task.task_name}", extra={
            "task_id": task.task_id,
            "retry_count": task.retry_count,
            "delay": delay
        })
        
        # 延迟后重新提交
        async def delayed_retry():
            await asyncio.sleep(delay)
            if not self.is_shutting_down:
                async with self.queue_lock:
                    heapq.heappush(self.task_queue, task)
                self.active_tasks[task.task_id] = task
                asyncio.create_task(self._process_queue())
        
        asyncio.create_task(delayed_retry())
        self.stats["total_retried"] += 1
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        # 检查活跃任务
        if task_id in self.active_tasks:
            return self.active_tasks[task_id].get_status_info()
        
        # 检查完成任务
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id].to_dict()
        
        # 检查缓存
        cached_result = self.result_cache.get(task_id)
        if cached_result:
            return cached_result
        
        return None
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务状态"""
        all_tasks = []
        
        # 添加活跃任务
        for task in self.active_tasks.values():
            all_tasks.append(task.get_status_info())
        
        # 添加完成任务
        for result in self.completed_tasks.values():
            all_tasks.append(result.to_dict())
        
        return all_tasks
    
    def cancel_task(self, task_id: str, reason: str = "用户取消") -> bool:
        """取消任务"""
        # 检查活跃任务
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            
            if task.status == TaskStatusEnum.PENDING:
                # 从队列中移除
                async def _remove_from_queue():
                    async with self.queue_lock:
                        self.task_queue = [t for t in self.task_queue if t.task_id != task_id]
                        heapq.heapify(self.task_queue)
                
                asyncio.create_task(_remove_from_queue())
                
                # 取消任务
                success = task.cancel(reason)
                if success:
                    asyncio.create_task(self._on_task_completed(task))
                
                return success
                
            elif task.status == TaskStatusEnum.RUNNING:
                # 正在运行的任务标记为取消
                success = task.cancel(reason)
                self.logger.warning(f"运行中任务标记为取消: {task.task_name}", extra={
                    "task_id": task_id,
                    "reason": reason
                })
                return success
        
        return False
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务（仅对队列中的任务有效）"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task.status == TaskStatusEnum.PENDING:
                # 添加暂停标记
                task.update_metadata("paused", True)
                task.add_tag("paused")
                return True
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task.metadata.get("paused"):
                task.update_metadata("paused", False)
                task.remove_tag("paused")
                # 重新加入队列处理
                asyncio.create_task(self._process_queue())
                return True
        return False
    
    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息"""
        priority_counts = {}
        status_counts = {}
        
        # 统计队列中的任务
        for task in self.task_queue:
            priority_counts[task.priority.name] = priority_counts.get(task.priority.name, 0) + 1
        
        # 统计活跃任务状态
        for task in self.active_tasks.values():
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1
        
        return {
            "queue_size": len(self.task_queue),
            "active_tasks": len(self.active_tasks),
            "priority_distribution": priority_counts,
            "status_distribution": status_counts,
            "next_task": self.task_queue[0].task_name if self.task_queue else None
        }
    
    def get_executor_info(self) -> List[Dict[str, Any]]:
        """获取执行器信息"""
        return [executor.get_stats() for executor in self.executors.values()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 实时统计
        pending_count = len([t for t in self.active_tasks.values() 
                           if t.status == TaskStatusEnum.PENDING])
        running_count = len([t for t in self.active_tasks.values() 
                           if t.status == TaskStatusEnum.RUNNING])
        
        queue_size = len(self.task_queue)
        
        # 计算成功率
        total_finished = self.stats["total_completed"] + self.stats["total_failed"]
        success_rate = self.stats["total_completed"] / total_finished if total_finished > 0 else 0
        
        # 计算工作者利用率
        busy_executors = len([e for e in self.executors.values() if e.is_busy])
        worker_utilization = busy_executors / self.max_workers if self.max_workers > 0 else 0
        
        return {
            "total_tasks": self.stats["total_submitted"],
            "running_tasks": running_count,
            "pending_tasks": pending_count,
            "completed_tasks": self.stats["total_completed"],
            "failed_tasks": self.stats["total_failed"],
            "cancelled_tasks": self.stats["total_cancelled"],
            "timeout_tasks": self.stats["total_timeout"],
            "retried_tasks": self.stats["total_retried"],
            "queue_size": queue_size,
            "active_tasks": len(self.active_tasks),
            "max_workers": self.max_workers,
            "busy_workers": busy_executors,
            "worker_utilization": worker_utilization,
            "success_rate": success_rate,
            "task_type_stats": self.task_type_stats
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        # 计算平均执行时间
        completed_tasks = [t for t in self.completed_tasks.values() 
                         if t.duration is not None]
        
        if completed_tasks:
            durations = [t.duration for t in completed_tasks]
            avg_duration = sum(durations) / len(durations)
            median_duration = sorted(durations)[len(durations) // 2]
            max_duration = max(durations)
            min_duration = min(durations)
        else:
            avg_duration = median_duration = max_duration = min_duration = 0
        
        # 计算任务吞吐量
        total_completed = len(completed_tasks)
        if completed_tasks:
            earliest_completion = min(t.end_time for t in completed_tasks if t.end_time)
            latest_completion = max(t.end_time for t in completed_tasks if t.end_time)
            if earliest_completion and latest_completion:
                time_span = (latest_completion - earliest_completion).total_seconds()
                throughput = total_completed / time_span if time_span > 0 else 0
            else:
                throughput = 0
        else:
            throughput = 0
        
        return {
            "avg_execution_time": avg_duration,
            "median_execution_time": median_duration,
            "max_execution_time": max_duration,
            "min_execution_time": min_duration,
            "throughput_tasks_per_second": throughput,
            "total_completed_tasks": total_completed
        }
    
    def cleanup_completed_tasks(self, max_history: int = 1000) -> int:
        """清理已完成的任务历史"""
        if len(self.completed_tasks) <= max_history:
            return 0
        
        # 按完成时间排序，保留最近的
        sorted_tasks = sorted(
            self.completed_tasks.items(),
            key=lambda x: x[1].end_time or x[1].start_time or datetime.min,
            reverse=True
        )
        
        # 保留最近的任务
        tasks_to_keep = dict(sorted_tasks[:max_history])
        cleaned_count = len(self.completed_tasks) - len(tasks_to_keep)
        
        self.completed_tasks = tasks_to_keep
        
        self.logger.info(f"清理任务历史，删除 {cleaned_count} 个任务，保留 {len(tasks_to_keep)} 个任务")
        return cleaned_count
    
    def force_kill_task(self, task_id: str, reason: str = "强制终止") -> bool:
        """强制终止任务（危险操作）"""
        if task_id in self.executor_tasks:
            executor_task = self.executor_tasks[task_id]
            executor_task.cancel()
            
            # 标记任务为已取消
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task.cancel(reason)
                asyncio.create_task(self._on_task_completed(task))
            
            self.logger.warning(f"强制终止任务: {task_id}", extra={
                "reason": reason
            })
            return True
        
        return False
    
    def update_task_priority(self, task_id: str, new_priority: TaskPriority) -> bool:
        """更新任务优先级（仅对队列中的任务有效）"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task.status == TaskStatusEnum.PENDING:
                task.priority = new_priority
                
                # 重新整理队列
                async def _reorder_queue():
                    async with self.queue_lock:
                        heapq.heapify(self.task_queue)
                
                asyncio.create_task(_reorder_queue())
                return True
        
        return False
    
    async def _monitor_loop(self) -> None:
        """监控循环 - 定期检查任务状态"""
        while self.is_running and not self.is_shutting_down:
            try:
                # 检查超时任务
                await self._check_timeout_tasks()
                
                # 检查队列中暂停的任务
                await self._process_paused_tasks()
                
                # 记录监控日志
                if len(self.active_tasks) > 0 or len(self.task_queue) > 0:
                    self.logger.debug("任务管理器状态", extra={
                        "active_tasks": len(self.active_tasks),
                        "queue_size": len(self.task_queue),
                        "busy_executors": len([e for e in self.executors.values() if e.is_busy])
                    })
                
                await asyncio.sleep(30)  # 每30秒检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"监控循环异常: {str(e)}")
                await asyncio.sleep(60)  # 发生异常时等待更长时间
    
    async def _cleanup_loop(self) -> None:
        """清理循环 - 定期清理过期数据"""
        while self.is_running and not self.is_shutting_down:
            try:
                # 清理缓存
                expired_count = self.result_cache.cleanup_expired()
                if expired_count > 0:
                    self.logger.info(f"清理过期缓存: {expired_count} 个任务")
                
                # 清理完成任务历史
                if len(self.completed_tasks) > 2000:  # 超过2000个时清理
                    self.cleanup_completed_tasks(1000)
                
                await asyncio.sleep(3600)  # 每小时清理一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"清理循环异常: {str(e)}")
                await asyncio.sleep(3600)
    
    async def _check_timeout_tasks(self) -> None:
        """检查超时任务"""
        timeout_tasks = []
        
        for task in self.active_tasks.values():
            if task.status == TaskStatusEnum.RUNNING and task.should_timeout():
                timeout_tasks.append(task)
        
        for task in timeout_tasks:
            self.logger.warning(f"检测到超时任务: {task.task_name}", extra={
                "task_id": task.task_id,
                "timeout": task.timeout,
                "duration": task.duration
            })
            
            # 强制终止超时任务
            self.force_kill_task(task.task_id, "任务执行超时")
    
    async def _process_paused_tasks(self) -> None:
        """处理暂停的任务"""
        # 从队列中移除暂停的任务
        async with self.queue_lock:
            paused_tasks = []
            remaining_tasks = []
            
            for task in self.task_queue:
                if task.metadata.get("paused"):
                    paused_tasks.append(task)
                else:
                    remaining_tasks.append(task)
            
            if paused_tasks:
                self.task_queue = remaining_tasks
                heapq.heapify(self.task_queue)
                
                self.logger.debug(f"暂停 {len(paused_tasks)} 个任务")
    
    def _update_task_type_stats(self, task_name: str, stat_type: str) -> None:
        """更新任务类型统计"""
        if task_name not in self.task_type_stats:
            self.task_type_stats[task_name] = {
                "submitted": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "timeout": 0
            }
        
        if stat_type in self.task_type_stats[task_name]:
            self.task_type_stats[task_name][stat_type] += 1
    
    async def shutdown(self) -> None:
        """优雅关闭任务管理器"""
        await self.stop()


# 全局任务管理器实例
task_manager = TaskManager()