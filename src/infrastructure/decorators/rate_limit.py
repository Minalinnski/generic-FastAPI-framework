# src/infrastructure/decorators/rate_limit.py
import asyncio
import functools
import time
from collections import defaultdict, deque
from typing import Any, Callable, Dict, Optional, Union

from src.infrastructure.logging.logger import get_logger
from src.schemas.enums.base_enums import ErrorCodeEnum

logger = get_logger(__name__)


class RateLimitExceeded(Exception):
    """限流异常"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class TokenBucket:
    """令牌桶算法实现"""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """异步消费令牌"""
        async with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def consume_sync(self, tokens: int = 1) -> bool:
        """同步消费令牌"""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    def get_available_tokens(self) -> int:
        """获取可用令牌数"""
        self._refill()
        return int(self.tokens)


class SlidingWindow:
    """滑动窗口算法实现"""
    
    def __init__(self, window_size: int, max_requests: int):
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests = deque()
        self._lock = asyncio.Lock()
    
    async def is_allowed(self) -> bool:
        """异步检查是否允许请求"""
        async with self._lock:
            return self._check_and_add()
    
    def is_allowed_sync(self) -> bool:
        """同步检查是否允许请求"""
        return self._check_and_add()
    
    def _check_and_add(self) -> bool:
        """检查并添加请求"""
        now = time.time()
        
        # 移除窗口外的请求
        while self.requests and self.requests[0] <= now - self.window_size:
            self.requests.popleft()
        
        # 检查是否超过限制
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False
    
    def get_retry_after(self) -> int:
        """获取重试等待时间"""
        if not self.requests:
            return 0
        
        oldest_request = self.requests[0]
        return max(0, int(self.window_size - (time.time() - oldest_request)) + 1)
    
    def get_current_count(self) -> int:
        """获取当前窗口内请求数"""
        now = time.time()
        # 清理过期请求
        while self.requests and self.requests[0] <= now - self.window_size:
            self.requests.popleft()
        return len(self.requests)


class RateLimiter:
    """通用限流器"""
    
    def __init__(self):
        self.sliding_windows: Dict[str, SlidingWindow] = defaultdict(lambda: None)
        self.token_buckets: Dict[str, TokenBucket] = defaultdict(lambda: None)
    
    def get_sliding_window(self, key: str, window_seconds: int, max_requests: int) -> SlidingWindow:
        """获取滑动窗口"""
        if self.sliding_windows[key] is None:
            self.sliding_windows[key] = SlidingWindow(window_seconds, max_requests)
        return self.sliding_windows[key]
    
    def get_token_bucket(self, key: str, capacity: int, refill_rate: float) -> TokenBucket:
        """获取令牌桶"""
        if self.token_buckets[key] is None:
            self.token_buckets[key] = TokenBucket(capacity, refill_rate)
        return self.token_buckets[key]
    
    def cleanup_expired(self, max_age: int = 3600) -> int:
        """清理过期的限流器"""
        cleaned = 0
        current_time = time.time()
        
        # 清理滑动窗口
        expired_windows = []
        for key, window in self.sliding_windows.items():
            if window and not window.requests:
                expired_windows.append(key)
            elif window and window.requests and current_time - window.requests[-1] > max_age:
                expired_windows.append(key)
        
        for key in expired_windows:
            del self.sliding_windows[key]
            cleaned += 1
        
        # 清理令牌桶
        expired_buckets = []
        for key, bucket in self.token_buckets.items():
            if bucket and current_time - bucket.last_refill > max_age:
                expired_buckets.append(key)
        
        for key in expired_buckets:
            del self.token_buckets[key]
            cleaned += 1
        
        return cleaned


# 全局限流器实例
global_rate_limiter = RateLimiter()


def rate_limit(
    max_requests: int,
    window_seconds: int,
    per: str = "function",  # "function", "user", "ip", "custom"
    key_func: Optional[Callable] = None,
    error_message: str = "Rate limit exceeded",
    algorithm: str = "sliding_window"  # "sliding_window" or "token_bucket"
):
    """
    限流装饰器
    
    Args:
        max_requests: 窗口内最大请求数
        window_seconds: 时间窗口（秒）
        per: 限流维度
        key_func: 自定义键函数
        error_message: 错误信息
        algorithm: 限流算法
    """
    def decorator(func: Callable) -> Callable:
        
        def _get_rate_limit_key(*args, **kwargs) -> str:
            """获取限流键"""
            if key_func:
                return str(key_func(*args, **kwargs))
            
            if per == "function":
                return f"{func.__module__}.{func.__name__}"
            elif per == "user":
                # 从kwargs或request中获取用户ID
                user_id = kwargs.get("user_id") or kwargs.get("current_user_id", "anonymous")
                return f"user:{user_id}:{func.__name__}"
            elif per == "ip":
                # 从kwargs或request中获取IP
                client_ip = kwargs.get("client_ip") or kwargs.get("request", {}).get("client", {}).get("host", "unknown")
                return f"ip:{client_ip}:{func.__name__}"
            else:
                return f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                rate_limit_key = _get_rate_limit_key(*args, **kwargs)
                
                if algorithm == "token_bucket":
                    # 令牌桶算法
                    refill_rate = max_requests / window_seconds
                    bucket = global_rate_limiter.get_token_bucket(rate_limit_key, max_requests, refill_rate)
                    
                    if not await bucket.consume():
                        logger.warning(f"令牌桶限流触发: {func.__name__}", extra={
                            "key": rate_limit_key,
                            "available_tokens": bucket.get_available_tokens()
                        })
                        raise RateLimitExceeded(error_message)
                
                else:
                    # 滑动窗口算法
                    window = global_rate_limiter.get_sliding_window(rate_limit_key, window_seconds, max_requests)
                    
                    if not await window.is_allowed():
                        retry_after = window.get_retry_after()
                        logger.warning(f"滑动窗口限流触发: {func.__name__}", extra={
                            "key": rate_limit_key,
                            "current_count": window.get_current_count(),
                            "max_requests": max_requests,
                            "retry_after": retry_after
                        })
                        raise RateLimitExceeded(error_message, retry_after)
                
                return await func(*args, **kwargs)
            
            return async_wrapper
        
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                rate_limit_key = _get_rate_limit_key(*args, **kwargs)
                
                if algorithm == "token_bucket":
                    # 令牌桶算法
                    refill_rate = max_requests / window_seconds
                    bucket = global_rate_limiter.get_token_bucket(rate_limit_key, max_requests, refill_rate)
                    
                    if not bucket.consume_sync():
                        logger.warning(f"令牌桶限流触发: {func.__name__}", extra={
                            "key": rate_limit_key,
                            "available_tokens": bucket.get_available_tokens()
                        })
                        raise RateLimitExceeded(error_message)
                
                else:
                    # 滑动窗口算法
                    window = global_rate_limiter.get_sliding_window(rate_limit_key, window_seconds, max_requests)
                    
                    if not window.is_allowed_sync():
                        retry_after = window.get_retry_after()
                        logger.warning(f"滑动窗口限流触发: {func.__name__}", extra={
                            "key": rate_limit_key,
                            "current_count": window.get_current_count(),
                            "max_requests": max_requests,
                            "retry_after": retry_after
                        })
                        raise RateLimitExceeded(error_message, retry_after)
                
                return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def debounce(wait_seconds: float):
    """
    防抖装饰器
    """
    def decorator(func: Callable) -> Callable:
        last_called = [0.0]
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                now = time.time()
                
                if now - last_called[0] < wait_seconds:
                    logger.debug(f"防抖跳过: {func.__name__}")
                    return None
                
                last_called[0] = now
                return await func(*args, **kwargs)
            
            return async_wrapper
        
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                now = time.time()
                
                if now - last_called[0] < wait_seconds:
                    logger.debug(f"防抖跳过: {func.__name__}")
                    return None
                
                last_called[0] = now
                return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def throttle(calls_per_second: float):
    """
    节流装饰器
    """
    min_interval = 1.0 / calls_per_second
    
    def decorator(func: Callable) -> Callable:
        last_called = [0.0]
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                now = time.time()
                elapsed = now - last_called[0]
                
                if elapsed < min_interval:
                    sleep_time = min_interval - elapsed
                    logger.debug(f"节流等待: {func.__name__}, 等待 {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                
                last_called[0] = time.time()
                return await func(*args, **kwargs)
            
            return async_wrapper
        
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                now = time.time()
                elapsed = now - last_called[0]
                
                if elapsed < min_interval:
                    sleep_time = min_interval - elapsed
                    logger.debug(f"节流等待: {func.__name__}, 等待 {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                
                last_called[0] = time.time()
                return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


# 便捷的限流装饰器
def api_rate_limit(requests_per_minute: int = 60):
    """API限流"""
    return rate_limit(
        max_requests=requests_per_minute,
        window_seconds=60,
        per="function",
        algorithm="sliding_window"
    )


def user_rate_limit(requests_per_minute: int = 30):
    """用户级限流"""
    return rate_limit(
        max_requests=requests_per_minute,
        window_seconds=60,
        per="user",
        algorithm="sliding_window"
    )


def ip_rate_limit(requests_per_minute: int = 100):
    """IP级限流"""
    return rate_limit(
        max_requests=requests_per_minute,
        window_seconds=60,
        per="ip",
        algorithm="sliding_window"
    )


def burst_rate_limit(burst_size: int = 10, sustained_rate: float = 2.0):
    """突发限流（令牌桶）"""
    return rate_limit(
        max_requests=burst_size,
        window_seconds=int(burst_size / sustained_rate),
        per="function",
        algorithm="token_bucket"
    )