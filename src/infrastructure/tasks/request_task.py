# src/infrastructure/tasks/request_task.py
"""
请求任务包装器 - 将API请求自动包装成Task
"""
import inspect
import traceback
from typing import Any, Callable, Dict, Optional
from src.infrastructure.tasks.base_task import BaseTask, TaskPriority
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


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
        
        self.logger.debug(f"创建RequestTask: {task_name}", extra={
            "task_name": task_name,
            "handler_func": handler_func.__name__,
            "args_count": len(args),
            "kwargs_keys": list(kwargs.keys()),
            "request_id": request_id,
            "priority": priority.value
        })
    
    async def execute(self, **execution_metadata) -> Any:
        """执行请求处理流程"""
        self.logger.info(f"开始执行RequestTask: {self.task_name}", extra={
            "task_id": self.task_id,
            "task_name": self.task_name,
            "request_id": self.request_id,
            "handler_func": self.handler_func.__name__,
            "args_count": len(self.args),
            "kwargs_keys": list(self.kwargs.keys()),
            "execution_metadata": execution_metadata
        })
        
        try:
            # 合并执行时的参数
            merged_kwargs = {**self.kwargs, **execution_metadata}
            
            # 检查函数类型并执行
            if inspect.iscoroutinefunction(self.handler_func):
                self.logger.debug(f"执行异步Handler函数: {self.handler_func.__name__}")
                result = await self.handler_func(*self.args, **merged_kwargs)
            else:
                self.logger.debug(f"执行同步Handler函数: {self.handler_func.__name__}")
                result = self.handler_func(*self.args, **merged_kwargs)
            
            self.logger.info(f"RequestTask执行成功: {self.task_name}", extra={
                "task_id": self.task_id,
                "request_id": self.request_id,
                "result_type": type(result).__name__,
                "result_size": len(str(result)) if result else 0
            })
            
            return result
            
        except Exception as e:
            # 获取详细的错误信息
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
                "handler_func": self.handler_func.__name__,
                "task_name": self.task_name,
                "request_id": self.request_id
            }
            
            self.logger.error(f"RequestTask执行失败: {self.task_name}", extra={
                "task_id": self.task_id,
                "request_id": self.request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "handler_func": self.handler_func.__name__
            }, exc_info=True)
            
            # 设置错误详情到任务中
            self.error_details = error_details
            
            # 重新抛出异常让TaskManager处理
            raise