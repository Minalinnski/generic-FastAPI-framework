# src/infrastructure/tasks/request_task.py
"""
请求任务包装器 - 将API请求自动包装成Task
"""
import inspect
from typing import Any, Callable, Dict, Optional
from src.infrastructure.tasks.base_task import BaseTask, TaskPriority


class RequestTask(BaseTask):
    """
    请求任务 - 包装API处理流程
    
    将 Router -> Handler -> Service 的完整流程包装成一个Task
    """
    
    def __init__(
        self,
        handler_func: Callable,
        args: tuple,
        kwargs: dict,
        task_name: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[int] = None,
        max_retries: int = 0,
        request_id: Optional[str] = None,
        **metadata
    ):
        super().__init__(
            task_name=task_name,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            metadata=metadata
        )
        
        self.handler_func = handler_func
        self.args = args
        self.kwargs = kwargs
        self.request_id = request_id
        
        # 记录请求信息
        self.add_tag("request_task")
        if request_id:
            self.add_tag(f"request:{request_id}")
    
    async def execute(self, **execution_metadata) -> Any:
        """执行请求处理流程"""
        self.logger.info(f"执行请求任务: {self.task_name}", extra={
            "request_id": self.request_id,
            "handler_func": self.handler_func.__name__,
            "args_count": len(self.args),
            "kwargs_keys": list(self.kwargs.keys())
        })
        
        try:
            # 执行Handler方法
            if inspect.iscoroutinefunction(self.handler_func):
                result = await self.handler_func(*self.args, **self.kwargs)
            else:
                result = self.handler_func(*self.args, **self.kwargs)
            
            self.logger.info(f"请求处理成功: {self.task_name}", extra={
                "request_id": self.request_id,
                "result_type": type(result).__name__
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"请求处理失败: {self.task_name}", extra={
                "request_id": self.request_id,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise