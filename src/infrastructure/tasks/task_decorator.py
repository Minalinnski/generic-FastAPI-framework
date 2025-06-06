# src/infrastructure/tasks/task_decorator.py
"""
任务装饰器 - 在Router层自动包装请求为Task
"""
import asyncio
import inspect
from functools import wraps
from typing import Callable, Optional, Any
from fastapi import HTTPException

from src.infrastructure.tasks.request_task import RequestTask
from src.infrastructure.tasks.task_manager import task_manager
from src.infrastructure.tasks.base_task import TaskPriority
from src.schemas.dtos.response.base_response import BaseResponse
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


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
        priority: 任务优先级 (0=低, 1=普通, 2=高, 3=紧急)
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        sync: 是否同步执行（不使用Task系统）
    
    Example:
        @as_task(priority=1, timeout=300, max_retries=2)
        async def my_api_function():
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 确定任务名称
            actual_task_name = task_name or func.__name__
            
            if sync:
                # 同步模式：直接执行，不使用Task系统
                return await _execute_directly(func, args, kwargs, actual_task_name)
            else:
                # 异步模式：提交到Task系统
                return await _execute_as_task(func, args, kwargs, {
                    'task_name': actual_task_name,
                    'priority': priority,
                    'timeout': timeout,
                    'max_retries': max_retries
                })
        
        return wrapper
    return decorator


async def _execute_directly(func: Callable, args: tuple, kwargs: dict, task_name: str) -> Any:
    """
    直接执行函数（同步模式）
    
    在这种模式下，函数直接执行，不进入Task队列，但仍然包装响应格式
    """
    logger.debug(f"直接执行函数: {task_name}", extra={
        "task_name": task_name,
        "func_name": func.__name__,
        "execution_mode": "direct"
    })
    
    try:
        # 执行函数
        if inspect.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)
        
        logger.debug(f"函数执行成功: {task_name}", extra={
            "task_name": task_name,
            "result_type": type(result).__name__
        })
        
        # 如果结果已经是BaseResponse，直接返回
        if isinstance(result, BaseResponse):
            return result
        
        # 否则包装成成功响应
        return BaseResponse.success_response(result)
        
    except Exception as e:
        logger.error(f"函数执行失败: {task_name}", extra={
            "task_name": task_name,
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        
        # 抛出HTTP异常，让FastAPI处理状态码
        raise HTTPException(status_code=500, detail=str(e))


async def _execute_as_task(func: Callable, args: tuple, kwargs: dict, task_config: dict) -> BaseResponse:
    """
    作为Task执行函数（异步模式）
    
    在这种模式下，函数调用被包装成RequestTask并提交到任务队列
    """
    task_name = task_config['task_name']
    
    logger.info(f"提交任务到队列: {task_name}", extra={
        "task_name": task_name,
        "priority": task_config['priority'],
        "timeout": task_config['timeout'],
        "max_retries": task_config['max_retries'],
        "func_name": func.__name__,
        "execution_mode": "async_task"
    })
    
    try:
        # 提取request_id（如果存在）
        request_id = None
        for arg in args:
            if hasattr(arg, 'state') and hasattr(arg.state, 'request_id'):
                request_id = arg.state.request_id
                logger.debug(f"提取到request_id: {request_id}")
                break
        
        # 创建请求任务
        task = RequestTask(
            handler_func=func,
            args=args,
            kwargs=kwargs,
            task_name=task_name,
            priority=TaskPriority.from_int(task_config['priority']),
            timeout=task_config['timeout'],
            max_retries=task_config['max_retries'],
            request_id=request_id
        )
        
        # 提交任务到管理器
        task_id = await task_manager.submit_task(task)
        
        logger.info(f"任务提交成功: {task_id}", extra={
            "task_id": task_id,
            "task_name": task_name
        })
        
        # 返回任务提交成功的响应
        return BaseResponse.success_response({
            "task_id": task_id,
            "status": "submitted",
            "task_name": task_name,
            "priority": task_config['priority'],
            "message": f"任务已提交到队列: {task_name}"
        })
        
    except Exception as e:
        logger.error(f"任务提交失败: {task_name}", extra={
            "task_name": task_name,
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        
        # 抛出HTTP异常
        raise HTTPException(
            status_code=500, 
            detail=f"任务提交失败: {str(e)}"
        )


# === 便捷装饰器 ===

def sync_task(timeout: int = 30):
    """
    同步任务装饰器
    
    函数直接执行，不进入任务队列，适合快速操作
    
    Args:
        timeout: 超时时间(秒)
    
    Example:
        @sync_task(timeout=10)
        async def quick_operation():
            pass
    """
    return as_task(sync=True, timeout=timeout)


def async_task(priority: int = 1, timeout: int = 300, max_retries: int = 2):
    """
    异步任务装饰器
    
    函数调用被提交到任务队列，立即返回task_id
    
    Args:
        priority: 任务优先级 (0=低, 1=普通, 2=高, 3=紧急)
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
    
    Example:
        @async_task(priority=2, timeout=600, max_retries=3)
        async def long_running_operation():
            pass
    """
    return as_task(
        priority=priority, 
        timeout=timeout, 
        max_retries=max_retries, 
        sync=False
    )


def high_priority_task(timeout: int = 60, max_retries: int = 1):
    """
    高优先级任务装饰器
    
    适合重要的、需要优先处理的操作
    
    Args:
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
    
    Example:
        @high_priority_task(timeout=120)
        async def critical_operation():
            pass
    """
    return as_task(priority=2, timeout=timeout, max_retries=max_retries, sync=False)


def urgent_task(timeout: int = 30, max_retries: int = 0):
    """
    紧急任务装饰器
    
    最高优先级，适合关键系统操作
    
    Args:
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
    
    Example:
        @urgent_task()
        async def system_critical_operation():
            pass
    """
    return as_task(priority=3, timeout=timeout, max_retries=max_retries, sync=False)


def background_task(timeout: int = 3600, max_retries: int = 3):
    """
    后台任务装饰器
    
    低优先级，适合不紧急的后台处理
    
    Args:
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
    
    Example:
        @background_task(timeout=7200)
        async def data_cleanup():
            pass
    """
    return as_task(priority=0, timeout=timeout, max_retries=max_retries, sync=False)