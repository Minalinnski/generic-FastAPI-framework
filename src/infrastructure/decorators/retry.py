# src/infrastructure/decorators/retry.py
import asyncio
import functools
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union

from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RetryExhausted(Exception):
    """重试次数耗尽异常"""
    
    def __init__(self, message: str, last_exception: Exception, attempts: int):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


def retry(
    max_attempts: int = 3,
    delay: Union[int, float] = 1.0,
    backoff: Union[int, float] = 1.0,
    jitter: bool = False,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    max_delay: Optional[float] = None
):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避倍数，每次重试延迟时间乘以此值
        jitter: 是否添加随机抖动
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
        max_delay: 最大延迟时间
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            return _async_retry_wrapper(
                func, max_attempts, delay, backoff, jitter, exceptions, on_retry, max_delay
            )
        else:
            return _sync_retry_wrapper(
                func, max_attempts, delay, backoff, jitter, exceptions, on_retry, max_delay
            )
    
    return decorator


def _async_retry_wrapper(
    func: Callable,
    max_attempts: int,
    delay: Union[int, float],
    backoff: Union[int, float],
    jitter: bool,
    exceptions: Tuple[Type[Exception], ...],
    on_retry: Optional[Callable[[int, Exception], None]],
    max_delay: Optional[float]
) -> Callable:
    """异步重试包装器"""
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        last_exception = None
        current_delay = delay
        
        for attempt in range(max_attempts):
            try:
                result = await func(*args, **kwargs)
                
                # 如果不是第一次尝试，记录成功日志
                if attempt > 0:
                    logger.info(
                        f"函数 {func.__name__} 在第 {attempt + 1} 次尝试后成功",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts,
                            "total_delay": sum(
                                delay * (backoff ** i) for i in range(attempt)
                            )
                        }
                    )
                
                return result
                
            except exceptions as e:
                last_exception = e
                
                # 如果是最后一次尝试，不再重试
                if attempt == max_attempts - 1:
                    logger.error(
                        f"函数 {func.__name__} 在 {max_attempts} 次尝试后仍然失败",
                        extra={
                            "function": func.__name__,
                            "attempts": max_attempts,
                            "final_error": str(e),
                            "error_type": type(e).__name__
                        }
                    )
                    break
                
                # 计算延迟时间
                actual_delay = current_delay
                if jitter:
                    actual_delay *= (0.5 + random.random())
                
                if max_delay:
                    actual_delay = min(actual_delay, max_delay)
                
                # 记录重试日志
                logger.warning(
                    f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败，将在 {actual_delay:.2f}s 后重试",
                    extra={
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "retry_delay": actual_delay
                    }
                )
                
                # 调用重试回调
                if on_retry:
                    try:
                        if asyncio.iscoroutinefunction(on_retry):
                            await on_retry(attempt + 1, e)
                        else:
                            on_retry(attempt + 1, e)
                    except Exception as callback_error:
                        logger.error(f"重试回调函数执行失败: {callback_error}")
                
                # 等待
                await asyncio.sleep(actual_delay)
                
                # 更新下次延迟时间
                current_delay *= backoff
        
        # 抛出重试耗尽异常
        if last_exception:
            raise RetryExhausted(
                f"函数 {func.__name__} 重试 {max_attempts} 次后仍然失败",
                last_exception,
                max_attempts
            ) from last_exception
    
    return wrapper


def _sync_retry_wrapper(
    func: Callable,
    max_attempts: int,
    delay: Union[int, float],
    backoff: Union[int, float],
    jitter: bool,
    exceptions: Tuple[Type[Exception], ...],
    on_retry: Optional[Callable[[int, Exception], None]],
    max_delay: Optional[float]
) -> Callable:
    """同步重试包装器"""
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        last_exception = None
        current_delay = delay
        
        for attempt in range(max_attempts):
            try:
                result = func(*args, **kwargs)
                
                # 如果不是第一次尝试，记录成功日志
                if attempt > 0:
                    logger.info(
                        f"函数 {func.__name__} 在第 {attempt + 1} 次尝试后成功",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts
                        }
                    )
                
                return result
                
            except exceptions as e:
                last_exception = e
                
                # 如果是最后一次尝试，不再重试
                if attempt == max_attempts - 1:
                    logger.error(
                        f"函数 {func.__name__} 在 {max_attempts} 次尝试后仍然失败",
                        extra={
                            "function": func.__name__,
                            "attempts": max_attempts,
                            "final_error": str(e),
                            "error_type": type(e).__name__
                        }
                    )
                    break
                
                # 计算延迟时间
                actual_delay = current_delay
                if jitter:
                    actual_delay *= (0.5 + random.random())
                
                if max_delay:
                    actual_delay = min(actual_delay, max_delay)
                
                # 记录重试日志
                logger.warning(
                    f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败，将在 {actual_delay:.2f}s 后重试",
                    extra={
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "retry_delay": actual_delay
                    }
                )
                
                # 调用重试回调
                if on_retry:
                    try:
                        on_retry(attempt + 1, e)
                    except Exception as callback_error:
                        logger.error(f"重试回调函数执行失败: {callback_error}")
                
                # 等待
                time.sleep(actual_delay)
                
                # 更新下次延迟时间
                current_delay *= backoff
        
        # 抛出重试耗尽异常
        if last_exception:
            raise RetryExhausted(
                f"函数 {func.__name__} 重试 {max_attempts} 次后仍然失败",
                last_exception,
                max_attempts
            ) from last_exception
    
    return wrapper


def exponential_backoff(
    max_attempts: int = 5,
    base_delay: Union[int, float] = 1.0,
    max_delay: Union[int, float] = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    指数退避重试装饰器
    """
    return retry(
        max_attempts=max_attempts,
        delay=base_delay,
        backoff=2.0,
        jitter=jitter,
        exceptions=exceptions,
        max_delay=max_delay
    )


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: Union[int, float] = 60.0,
    expected_exception: Type[Exception] = Exception
):
    """
    断路器装饰器
    """
    def decorator(func: Callable) -> Callable:
        state = {
            'failure_count': 0,
            'last_failure_time': None,
            'state': 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        }
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            current_time = time.time()
            
            # 检查断路器状态
            if state['state'] == 'OPEN':
                if state['last_failure_time'] and current_time - state['last_failure_time'] > recovery_timeout:
                    state['state'] = 'HALF_OPEN'
                    logger.info(f"断路器半开: {func.__name__}")
                else:
                    raise Exception(f"断路器开启: {func.__name__} 暂时不可用")
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 成功时重置状态
                if state['state'] in ['HALF_OPEN', 'OPEN']:
                    state['state'] = 'CLOSED'
                    state['failure_count'] = 0
                    logger.info(f"断路器关闭: {func.__name__} 恢复正常")
                
                return result
                
            except expected_exception as e:
                state['failure_count'] += 1
                state['last_failure_time'] = current_time
                
                if state['failure_count'] >= failure_threshold:
                    state['state'] = 'OPEN'
                    logger.error(f"断路器开启: {func.__name__} 失败次数达到阈值 {failure_threshold}")
                
                raise e
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 便捷的重试装饰器
def simple_retry(attempts: int = 3, delay: float = 1.0):
    """简单重试装饰器"""
    return retry(max_attempts=attempts, delay=delay)


def network_retry(attempts: int = 3):
    """网络请求重试装饰器"""
    return retry(
        max_attempts=attempts,
        delay=1.0,
        backoff=2.0,
        jitter=True,
        exceptions=(ConnectionError, TimeoutError, OSError),
        max_delay=30.0
    )


def database_retry(attempts: int = 3):
    """数据库操作重试装饰器"""
    return retry(
        max_attempts=attempts,
        delay=0.5,
        backoff=1.5,
        exceptions=(Exception,),  # 根据具体数据库异常类型调整
        max_delay=10.0
    )


def external_api_retry(attempts: int = 5):
    """外部API调用重试装饰器"""
    return retry(
        max_attempts=attempts,
        delay=2.0,
        backoff=2.0,
        jitter=True,
        exceptions=(ConnectionError, TimeoutError, Exception),
        max_delay=60.0
    )