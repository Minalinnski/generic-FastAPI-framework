# app/infrastructure/tasks/task_decorator.py
"""
任务装饰器 - 在Router层自动包装请求为Task
"""
import asyncio
from functools import wraps
from typing import Callable, Optional
from fastapi import Request
from app.infrastructure.tasks.request_task import RequestTask
from app.infrastructure.tasks.task_manager import task_manager
from app.infrastructure.tasks.base_task import TaskPriority
from app.schemas.dtos.response.base_response import BaseResponse


def as_task(
    task_name: Optional[str] = None,
    priority: int = 0,
    timeout: Optional[int] = None,
    max_retries: int = 0,
    sync: bool = False
):
    """
    任务装饰器 - 将API函数包装成Task
    
    Args:
        task_name: 任务名称，默认使用函数名
        priority: 任务优先级
        timeout: 超时时间
        max_retries: 最大重试次数
        sync: 是否同步执行（不使用Task系统）
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 如果是同步模式，直接执行
            if sync:
                return await _execute_directly(func, args, kwargs)
            
            # 异步模式，提交到Task系统
            return await _execute_as_task(func, args, kwargs, {
                'task_name': task_name or func.__name__,
                'priority': priority,
                'timeout': timeout,
                'max_retries': max_retries
            })
        
        return wrapper
    return decorator


async def _execute_directly(func: Callable, args: tuple, kwargs: dict) -> Any:
    """直接执行函数"""
    try:
        if inspect.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)
        
        # 如果结果已经是BaseResponse，直接返回
        if isinstance(result, BaseResponse):
            return result
        
        # 否则包装成成功响应
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("EXECUTION_ERROR", str(e))


async def _execute_as_task(func: Callable, args: tuple, kwargs: dict, task_config: dict) -> BaseResponse:
    """作为Task执行函数"""
    try:
        # 提取request_id（如果存在）
        request_id = None
        for arg in args:
            if hasattr(arg, 'state') and hasattr(arg.state, 'request_id'):
                request_id = arg.state.request_id
                break
        
        # 创建请求任务
        task = RequestTask(
            handler_func=func,
            args=args,
            kwargs=kwargs,
            task_name=task_config['task_name'],
            priority=TaskPriority.from_int(task_config['priority']),
            timeout=task_config['timeout'],
            max_retries=task_config['max_retries'],
            request_id=request_id
        )
        
        # 提交任务
        task_id = await task_manager.submit_task(task)
        
        # 返回任务信息
        return BaseResponse.success_response({
            "task_id": task_id,
            "status": "submitted",
            "message": f"任务已提交: {task_config['task_name']}"
        })
        
    except Exception as e:
        return BaseResponse.error_response("TASK_SUBMIT_ERROR", str(e))


# 便捷装饰器
def sync_task(timeout: int = 30):
    """同步任务装饰器"""
    return as_task(sync=True, timeout=timeout)


def async_task(priority: int = 0, timeout: int = 300, max_retries: int = 2):
    """异步任务装饰器"""
    return as_task(
        priority=priority, 
        timeout=timeout, 
        max_retries=max_retries, 
        sync=False
    )


def high_priority_task(timeout: int = 60):
    """高优先级任务装饰器"""
    return as_task(priority=1, timeout=timeout, sync=False)