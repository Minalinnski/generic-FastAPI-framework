# src/infrastructure/decorators/cache.py
import asyncio
import functools
import hashlib
import json
import pickle
import time
from typing import Any, Callable, Optional, Union

from src.infrastructure.logging.logger import get_logger
from src.infrastructure.cache.cache_interface import CacheInterface, InMemoryCache

logger = get_logger(__name__)


def cache(
    ttl: Optional[int] = 3600,
    key_prefix: str = "cache:",
    cache_instance: Optional[CacheInterface] = None,
    serialize_method: str = "json",  # "json" or "pickle"
    key_func: Optional[Callable] = None,
    condition: Optional[Callable] = None
):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存过期时间（秒），None表示永不过期
        key_prefix: 缓存键前缀
        cache_instance: 缓存实例，None则使用默认内存缓存
        serialize_method: 序列化方法，"json"或"pickle"
        key_func: 自定义键生成函数
        condition: 缓存条件函数，返回True才缓存
    """
    def decorator(func: Callable) -> Callable:
        # 如果没有提供缓存实例，使用默认的内存缓存
        cache_backend = cache_instance or InMemoryCache()
        
        def _generate_cache_key(*args, **kwargs) -> str:
            """生成缓存键"""
            if key_func:
                return f"{key_prefix}{key_func(*args, **kwargs)}"
            
            # 创建基于函数名和参数的键
            key_data = {
                'func': f"{func.__module__}.{func.__name__}",
                'args': args,
                'kwargs': sorted(kwargs.items())
            }
            
            # 将数据序列化为字符串
            key_string = json.dumps(key_data, sort_keys=True, default=str)
            
            # 生成MD5哈希
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            
            return f"{key_prefix}{key_hash}"
        
        def _serialize_value(value: Any) -> Any:
            """序列化值"""
            if serialize_method == "pickle":
                return pickle.dumps(value)
            else:
                try:
                    return json.dumps(value, default=str)
                except (TypeError, ValueError):
                    # 如果JSON序列化失败，回退到pickle
                    logger.warning(f"JSON序列化失败，使用pickle: {func.__name__}")
                    return pickle.dumps(value)
        
        def _deserialize_value(value: Any) -> Any:
            """反序列化值"""
            if serialize_method == "pickle" or isinstance(value, bytes):
                return pickle.loads(value)
            else:
                return json.loads(value)
        
        def _should_cache(result: Any, *args, **kwargs) -> bool:
            """检查是否应该缓存"""
            if condition:
                return condition(result, *args, **kwargs)
            
            # 默认不缓存None值
            return result is not None
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                cache_key = _generate_cache_key(*args, **kwargs)
                
                try:
                    # 尝试从缓存获取
                    cached_value = await cache_backend.get(cache_key)
                    if cached_value is not None:
                        logger.debug(f"缓存命中: {cache_key}")
                        return _deserialize_value(cached_value)
                    
                    # 缓存未命中，执行函数
                    logger.debug(f"缓存未命中: {cache_key}")
                    result = await func(*args, **kwargs)
                    
                    # 检查是否应该缓存
                    if _should_cache(result, *args, **kwargs):
                        serialized_result = _serialize_value(result)
                        await cache_backend.set(cache_key, serialized_result, ttl)
                        logger.debug(f"缓存已保存: {cache_key}")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"缓存操作失败: {str(e)}")
                    # 缓存失败时直接执行函数
                    return await func(*args, **kwargs)
            
            return async_wrapper
        
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                cache_key = _generate_cache_key(*args, **kwargs)
                
                try:
                    # 尝试从缓存获取
                    cached_value = cache_backend.get_sync(cache_key)
                    if cached_value is not None:
                        logger.debug(f"缓存命中: {cache_key}")
                        return _deserialize_value(cached_value)
                    
                    # 缓存未命中，执行函数
                    logger.debug(f"缓存未命中: {cache_key}")
                    result = func(*args, **kwargs)
                    
                    # 检查是否应该缓存
                    if _should_cache(result, *args, **kwargs):
                        serialized_result = _serialize_value(result)
                        cache_backend.set_sync(cache_key, serialized_result, ttl)
                        logger.debug(f"缓存已保存: {cache_key}")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"缓存操作失败: {str(e)}")
                    # 缓存失败时直接执行函数
                    return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def cache_invalidate(
    key_pattern: Optional[str] = None,
    cache_instance: Optional[CacheInterface] = None,
    key_func: Optional[Callable] = None
):
    """
    缓存失效装饰器
    """
    def decorator(func: Callable) -> Callable:
        cache_backend = cache_instance or InMemoryCache()
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                result = await func(*args, **kwargs)
                
                try:
                    if key_func:
                        # 使用自定义键函数
                        cache_key = key_func(*args, **kwargs)
                        await cache_backend.delete(cache_key)
                        logger.info(f"清除缓存键: {cache_key}")
                    elif key_pattern:
                        # 使用模式匹配
                        cleared_count = await cache_backend.clear_pattern(key_pattern)
                        logger.info(f"清除缓存 {cleared_count} 个键，模式: {key_pattern}")
                except Exception as e:
                    logger.error(f"清除缓存失败: {str(e)}")
                
                return result
            
            return async_wrapper
        
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                result = func(*args, **kwargs)
                
                try:
                    if key_func:
                        # 使用自定义键函数
                        cache_key = key_func(*args, **kwargs)
                        cache_backend.delete_sync(cache_key)
                        logger.info(f"清除缓存键: {cache_key}")
                    elif key_pattern:
                        # 使用模式匹配（需要缓存实现支持）
                        logger.info(f"清除缓存模式: {key_pattern}")
                except Exception as e:
                    logger.error(f"清除缓存失败: {str(e)}")
                
                return result
            
            return sync_wrapper
    
    return decorator


def memoize(maxsize: int = 128):
    """
    记忆化装饰器（基于LRU缓存）
    """
    def decorator(func: Callable) -> Callable:
        cache_dict = {}
        access_times = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 生成缓存键
            key = (args, tuple(sorted(kwargs.items())))
            current_time = time.time()
            
            # 检查缓存
            if key in cache_dict:
                access_times[key] = current_time
                logger.debug(f"记忆化缓存命中: {func.__name__}")
                return cache_dict[key]
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 如果缓存已满，移除最久未访问的项
            if len(cache_dict) >= maxsize:
                oldest_key = min(access_times.keys(), key=lambda k: access_times[k])
                del cache_dict[oldest_key]
                del access_times[oldest_key]
                logger.debug(f"记忆化缓存清理: {func.__name__}")
            
            # 添加到缓存
            cache_dict[key] = result
            access_times[key] = current_time
            logger.debug(f"记忆化缓存保存: {func.__name__}")
            
            return result
        
        # 添加缓存管理方法
        wrapper.cache_info = lambda: {
            'currsize': len(cache_dict),
            'maxsize': maxsize
        }
        wrapper.cache_clear = lambda: (cache_dict.clear(), access_times.clear())
        
        return wrapper
    
    return decorator


# 便捷的缓存装饰器
def short_cache(func: Callable = None, *, ttl: int = 300):
    """短期缓存（5分钟）"""
    if func is None:
        return lambda f: cache(ttl=ttl)(f)
    return cache(ttl=ttl)(func)


def long_cache(func: Callable = None, *, ttl: int = 3600):
    """长期缓存（1小时）"""
    if func is None:
        return lambda f: cache(ttl=ttl)(f)
    return cache(ttl=ttl)(func)


def permanent_cache(func: Callable = None):
    """永久缓存"""
    if func is None:
        return lambda f: cache(ttl=None)(f)
    return cache(ttl=None)(func)


def api_cache(ttl: int = 600):
    """API缓存"""
    return cache(
        ttl=ttl,
        key_prefix="api_cache:",
        serialize_method="json"
    )


def user_cache(ttl: int = 1800):
    """用户数据缓存"""
    def key_func(*args, **kwargs):
        user_id = kwargs.get('user_id') or (args[0] if args else 'anonymous')
        return f"user:{user_id}"
    
    return cache(
        ttl=ttl,
        key_prefix="user_cache:",
        key_func=key_func
    )


def conditional_cache(condition_func: Callable, ttl: int = 3600):
    """条件缓存"""
    return cache(
        ttl=ttl,
        condition=condition_func
    )