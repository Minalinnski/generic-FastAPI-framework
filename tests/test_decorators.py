# tests/test_decorators.py
import asyncio
import pytest
import time
import sys
import os
from pathlib import Path

# 确保可以导入app模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.decorators.rate_limit import (
    rate_limit, api_rate_limit, RateLimitExceeded, global_rate_limiter
)
from app.infrastructure.decorators.retry import (
    retry, simple_retry, network_retry, RetryExhausted
)
from app.infrastructure.decorators.cache import cache, short_cache


class TestRateLimiter:
    """测试限流功能"""
    
    def setup_method(self):
        """每个测试前清理状态"""
        global_rate_limiter.sliding_windows.clear()
        global_rate_limiter.token_buckets.clear()
    
    @pytest.mark.asyncio
    async def test_sliding_window_rate_limit(self):
        """测试滑动窗口限流"""
        
        @rate_limit(max_requests=3, window_seconds=2)
        async def test_function():
            return "success"
        
        # 前3次调用应该成功
        for i in range(3):
            result = await test_function()
            assert result == "success"
        
        # 第4次调用应该被限流
        with pytest.raises(RateLimitExceeded):
            await test_function()
        
        print("✅ 滑动窗口限流测试通过")
    
    @pytest.mark.asyncio
    async def test_token_bucket_rate_limit(self):
        """测试令牌桶限流"""
        
        @rate_limit(max_requests=5, window_seconds=2, algorithm="token_bucket")
        async def test_function():
            return "success"
        
        # 快速消耗所有令牌
        for i in range(5):
            result = await test_function()
            assert result == "success"
        
        # 下一次调用应该被限流
        with pytest.raises(RateLimitExceeded):
            await test_function()
        
        print("✅ 令牌桶限流测试通过")
    
    @pytest.mark.asyncio
    async def test_per_user_rate_limit(self):
        """测试用户级限流"""
        
        @rate_limit(max_requests=2, window_seconds=2, per="user")
        async def test_function(user_id=None):
            return f"success for {user_id}"
        
        # 用户1的调用
        result1 = await test_function(user_id="user1")
        result2 = await test_function(user_id="user1")
        assert result1 == "success for user1"
        assert result2 == "success for user1"
        
        # 用户1超出限制
        with pytest.raises(RateLimitExceeded):
            await test_function(user_id="user1")
        
        # 用户2不受影响
        result3 = await test_function(user_id="user2")
        assert result3 == "success for user2"
        
        print("✅ 用户级限流测试通过")


class TestRetryDecorator:
    """测试重试功能"""
    
    @pytest.mark.asyncio
    async def test_simple_retry_success(self):
        """测试重试成功场景"""
        call_count = 0
        
        @simple_retry(attempts=3, delay=0.1)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("模拟连接失败")
            return "success after retries"
        
        result = await flaky_function()
        assert result == "success after retries"
        assert call_count == 3
        print("✅ 重试成功场景测试通过")
    
    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """测试重试耗尽场景"""
        call_count = 0
        
        @simple_retry(attempts=3, delay=0.1)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("总是失败")
        
        with pytest.raises(RetryExhausted) as exc_info:
            await always_fail()
        
        assert call_count == 3
        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, ValueError)
        print("✅ 重试耗尽场景测试通过")
    
    @pytest.mark.asyncio
    async def test_network_retry_with_specific_exceptions(self):
        """测试网络重试特定异常"""
        call_count = 0
        
        @network_retry(attempts=3)
        async def network_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("网络错误")
            elif call_count == 2:
                raise TimeoutError("超时错误")
            return "网络调用成功"
        
        result = await network_call()
        assert result == "网络调用成功"
        assert call_count == 3
        print("✅ 网络重试特定异常测试通过")
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff(self):
        """测试重试退避机制"""
        start_time = time.time()
        call_count = 0
        
        @retry(max_attempts=3, delay=0.1, backoff=2.0)
        async def backoff_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("需要重试")
            return "success"
        
        result = await backoff_function()
        end_time = time.time()
        
        assert result == "success"
        assert call_count == 3
        # 检查退避时间：0.1 + 0.2 = 0.3秒（大致）
        assert end_time - start_time >= 0.25  # 允许一些误差
        print("✅ 重试退避机制测试通过")


class TestCacheDecorator:
    """测试缓存功能"""
    
    @pytest.mark.asyncio
    async def test_cache_hit_and_miss(self):
        """测试缓存命中和未命中"""
        call_count = 0
        
        @cache(ttl=2, key_prefix="test:")
        async def expensive_function(value):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)  # 模拟耗时操作
            return f"result_{value}"
        
        # 第一次调用
        result1 = await expensive_function("test")
        assert result1 == "result_test"
        assert call_count == 1
        
        # 第二次调用应该使用缓存
        result2 = await expensive_function("test")
        assert result2 == "result_test"
        assert call_count == 1  # 没有增加
        
        # 不同参数应该重新计算
        result3 = await expensive_function("different")
        assert result3 == "result_different"
        assert call_count == 2
        
        print("✅ 缓存命中和未命中测试通过")


class TestStressTest:
    """压力测试"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_stress(self):
        """限流器并发压力测试"""
        
        @rate_limit(max_requests=10, window_seconds=1)
        async def stress_function(request_id):
            return f"response_{request_id}"
        
        # 并发发送请求
        tasks = []
        for i in range(20):
            tasks.append(stress_function(i))
        
        # 统计成功和失败的请求
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        rate_limited_count = 0
        
        for result in results:
            if isinstance(result, RateLimitExceeded):
                rate_limited_count += 1
            elif isinstance(result, str):
                success_count += 1
        
        print(f"压力测试结果 - 成功: {success_count}, 限流: {rate_limited_count}")
        
        # 应该有一些成功，一些被限流
        assert success_count > 5
        assert rate_limited_count > 5
        assert success_count + rate_limited_count == 20
        print("✅ 限流器并发压力测试通过")
    
    @pytest.mark.asyncio
    async def test_retry_concurrent_stress(self):
        """重试并发压力测试"""
        success_count = 0
        
        @simple_retry(attempts=3, delay=0.01)
        async def unreliable_function(request_id):
            # 模拟50%成功率
            if request_id % 2 == 0:
                return f"success_{request_id}"
            else:
                raise Exception(f"failure_{request_id}")
        
        # 并发执行
        tasks = []
        for i in range(10):
            tasks.append(unreliable_function(i))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, str) and result.startswith("success_"):
                success_count += 1
        
        print(f"重试压力测试 - 成功操作: {success_count}/10")
        assert success_count >= 4  # 至少应该有一些成功
        print("✅ 重试并发压力测试通过")


# 简单的性能测试函数
def test_decorator_performance():
    """测试装饰器性能开销"""
    import time
    
    # 无装饰器的函数
    def plain_function(x):
        return x * 2
    
    # 有缓存装饰器的函数
    @cache(ttl=10)
    def cached_function(x):
        return x * 2
    
    # 测试普通函数性能
    start = time.time()
    for i in range(1000):
        plain_function(i)
    plain_time = time.time() - start
    
    # 测试缓存函数性能（第一次调用）
    start = time.time()
    for i in range(1000):
        cached_function(i)
    cached_time = time.time() - start
    
    print(f"普通函数时间: {plain_time:.4f}s")
    print(f"缓存函数时间: {cached_time:.4f}s")
    print(f"装饰器开销: {(cached_time - plain_time) / plain_time * 100:.1f}%")
    
    # 装饰器开销应该是可接受的
    assert cached_time < plain_time * 5  # 装饰器开销不应超过5倍
    print("✅ 装饰器性能测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])