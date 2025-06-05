# app/infrastructure/tasks/generic_task.py
import asyncio
from typing import Any, Callable, Dict, Optional

from app.infrastructure.tasks.base_task import BaseTask, TaskPriority


class ServiceTask(BaseTask):
    """
    服务任务执行器
    
    这是Task系统和Service层的桥梁：
    - Task系统负责：调度、排队、状态管理、重试、超时
    - Service负责：具体业务逻辑
    """
    
    def __init__(
        self, 
        service_func: Callable,
        task_name: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[int] = None,
        max_retries: int = 0,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            task_name=task_name,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            tags=tags,
            metadata=metadata
        )
        self.service_func = service_func
        self.is_async_func = asyncio.iscoroutinefunction(service_func)
        
        # 添加函数信息到元数据
        self.metadata.update({
            "service_function": service_func.__name__,
            "service_module": service_func.__module__,
            "is_async": self.is_async_func,
            "function_doc": service_func.__doc__ or "无文档"
        })
    
    async def execute(self, **kwargs) -> Any:
        """执行服务函数"""
        try:
            self.logger.info(f"开始执行服务函数: {self.service_func.__name__}", extra={
                "task_id": self.task_id,
                "function": self.service_func.__name__,
                "kwargs_keys": list(kwargs.keys())
            })
            
            if self.is_async_func:
                result = await self.service_func(**kwargs)
            else:
                # 在线程池中执行同步函数，避免阻塞事件循环
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: self.service_func(**kwargs))
            
            self.logger.info(f"服务函数执行成功: {self.service_func.__name__}", extra={
                "task_id": self.task_id,
                "result_type": type(result).__name__
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"服务函数执行失败: {self.service_func.__name__}", extra={
                "task_id": self.task_id,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise


class TaskFactory:
    """任务工厂 - 简化任务创建"""
    
    @staticmethod
    def create_service_task(
        service_func: Callable,
        task_name: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[int] = None,
        max_retries: int = 0,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ServiceTask:
        """创建服务任务"""
        if not task_name:
            task_name = f"{service_func.__module__.split('.')[-1]}.{service_func.__name__}"
        
        return ServiceTask(
            service_func=service_func,
            task_name=task_name,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            tags=tags,
            metadata=metadata
        )
    
    @staticmethod
    def create_high_priority_task(
        service_func: Callable,
        task_name: Optional[str] = None,
        timeout: Optional[int] = 60,
        **kwargs
    ) -> ServiceTask:
        """创建高优先级任务"""
        return TaskFactory.create_service_task(
            service_func=service_func,
            task_name=task_name,
            priority=TaskPriority.HIGH,
            timeout=timeout,
            **kwargs
        )
    
    @staticmethod
    def create_urgent_task(
        service_func: Callable,
        task_name: Optional[str] = None,
        timeout: Optional[int] = 30,
        **kwargs
    ) -> ServiceTask:
        """创建紧急任务"""
        return TaskFactory.create_service_task(
            service_func=service_func,
            task_name=task_name,
            priority=TaskPriority.URGENT,
            timeout=timeout,
            **kwargs
        )
    
    @staticmethod
    def create_retry_task(
        service_func: Callable,
        task_name: Optional[str] = None,
        max_retries: int = 3,
        timeout: Optional[int] = 300,
        **kwargs
    ) -> ServiceTask:
        """创建带重试的任务"""
        return TaskFactory.create_service_task(
            service_func=service_func,
            task_name=task_name,
            max_retries=max_retries,
            timeout=timeout,
            **kwargs
        )
    
    @staticmethod
    def create_background_task(
        service_func: Callable,
        task_name: Optional[str] = None,
        **kwargs
    ) -> ServiceTask:
        """创建后台任务（低优先级，长超时）"""
        return TaskFactory.create_service_task(
            service_func=service_func,
            task_name=task_name,
            priority=TaskPriority.LOW,
            timeout=3600,  # 1小时超时
            **kwargs
        )