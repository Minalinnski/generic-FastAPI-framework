# tests/test_foo_comprehensive.py
"""
Foo服务综合测试 - 测试DDD架构、装饰器和任务系统
"""
import asyncio
import pytest
import time
import sys
import os
from pathlib import Path

# 确保可以导入app模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.application.services.foo_service import get_foo_service
from src.application.handlers.foo_handler import FooHandler
from src.infrastructure.decorators.rate_limit import (
    rate_limit, api_rate_limit, RateLimitExceeded, global_rate_limiter
)
from src.infrastructure.decorators.retry import simple_retry, RetryExhausted
from src.infrastructure.decorators.cache import short_cache


class TestFooService:
    """测试Foo服务层"""
    
    def setup_method(self):
        """每个测试前重置状态"""
        self.foo_service = get_foo_service()
        self.foo_service.reset_counters()
    
    async def test_sync_processing(self):
        """测试同步处理"""
        test_data = {"test": "sync_data", "value": 123}
        
        result = self.foo_service.process_data_sync(
            data=test_data,
            processing_time=0.1
        )
        
        assert result["processed"] is True
        assert result["processing_type"] == "sync"
        assert result["process_id"].startswith("sync_")
        assert "quick_result" in result
        assert result["data_size"] > 0
        
        print("✅ 同步处理测试通过")
    
    async def test_async_processing(self):
        """测试异步处理"""
        test_data = {"test": "async_data", "items": [1, 2, 3]}
        
        result = await self.foo_service.process_data_async(
            data=test_data,
            processing_time=0.2
        )
        
        assert result["processed"] is True
        assert result["processing_type"] == "async"
        assert result["process_id"].startswith("async_")
        assert "enhancement" in result
        assert result["processing_time"] == 0.2
        
        print("✅ 异步处理测试通过")
    
    async def test_batch_processing(self):
        """测试批量处理"""
        test_items = [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"},
            {"id": 3, "name": "item3"}
        ]
        
        results = await self.foo_service.process_batch_async(
            items=test_items,
            processing_time=0.3
        )
        
        assert len(results) == 3
        successful_count = sum(1 for r in results if r.get("success"))
        assert successful_count >= 2  # 允许一些随机失败
        
        for i, result in enumerate(results):
            assert result["item_index"] == i
            assert "batch_id" in result
        
        print(f"✅ 批量处理测试通过: {successful_count}/3 成功")
    
    async def test_external_service_call(self):
        """测试外部服务调用（带重试）"""
        test_endpoint = "https://api.example.com/test"
        test_data = {"request": "test"}
        
        # 可能需要重试几次才能成功
        max_attempts = 5
        success = False
        
        for attempt in range(max_attempts):
            try:
                result = await self.foo_service.call_external_service(
                    endpoint=test_endpoint,
                    data=test_data
                )
                
                assert result["external_service"] == test_endpoint
                assert result["status"] == "success"
                assert "response_id" in result
                
                success = True
                break
                
            except ConnectionError:
                if attempt == max_attempts - 1:
                    pytest.fail("外部服务调用在所有重试后仍然失败")
                continue
        
        assert success
        print("✅ 外部服务调用测试通过")
    
    async def test_cached_data(self):
        """测试缓存功能"""
        test_key = "test_cache_key"
        
        # 第一次调用
        start_time = time.time()
        result1 = await self.foo_service.get_cached_data(test_key)
        first_call_time = time.time() - start_time
        
        # 第二次调用（应该使用缓存）
        start_time = time.time()
        result2 = await self.foo_service.get_cached_data(test_key)
        second_call_time = time.time() - start_time
        
        # 验证结果一致
        assert result1["key"] == test_key
        assert result2["key"] == test_key
        assert result1["data"] == result2["data"]  # 缓存应该返回相同数据
        
        # 验证缓存效果（第二次调用应该更快）
        assert second_call_time < first_call_time * 0.5
        
        print(f"✅ 缓存功能测试通过: 第一次 {first_call_time:.3f}s, 第二次 {second_call_time:.3f}s")
    
    async def test_health_check(self):
        """测试健康检查"""
        health_result = await self.foo_service.health_check()
        
        assert health_result["service"] == "FooService"
        assert health_result["status"] == "healthy"
        assert "processing_count" in health_result
        assert "timestamp" in health_result
        
        print("✅ 健康检查测试通过")


class TestFooHandler:
    """测试Foo处理器层"""
    
    def setup_method(self):
        """每个测试前重置状态"""
        self.foo_handler = FooHandler()
    
    async def test_handler_async_processing(self):
        """测试Handler异步处理"""
        test_data = {"handler_test": True, "value": 456}
        
        result = await self.foo_handler.handle_async_processing(
            data=test_data,
            processing_time=0.1
        )
        
        # 验证Handler层的增强
        assert result["handler"] == "FooHandler"
        assert result["flow"] == "async_processing"
        assert "request_processed_at" in result
        
        # 验证Service层的处理
        assert result["processed"] is True
        assert result["processing_type"] == "async"
        
        print("✅ Handler异步处理测试通过")
    
    def test_handler_sync_processing(self):
        """测试Handler同步处理"""
        test_data = {"handler_test": True, "value": 789}
        
        result = self.foo_handler.handle_sync_processing(
            data=test_data,
            processing_time=0.1
        )
        
        # 验证Handler层的增强
        assert result["handler"] == "FooHandler"
        assert result["flow"] == "sync_processing"
        
        # 验证Service层的处理
        assert result["processed"] is True
        assert result["processing_type"] == "sync"
        
        print("✅ Handler同步处理测试通过")
    
    async def test_handler_status_check(self):
        """测试Handler状态检查"""
        result = await self.foo_handler.handle_status_check()
        
        assert "service" in result
        assert "health" in result
        assert result["handler"] == "FooHandler"
        assert result["cached"] is True  # 标识可能来自缓存
        
        print("✅ Handler状态检查测试通过")
    
    async def test_handler_batch_processing(self):
        """测试Handler批量处理"""
        test_items = [
            {"id": 1, "data": "test1"},
            {"id": 2, "data": "test2"}
        ]
        
        result = await self.foo_handler.handle_batch_processing(
            items=test_items,
            processing_time=0.2
        )
        
        # 验证Handler层的汇总
        assert result["total_items"] == 2
        assert result["handler"] == "FooHandler"
        assert result["flow"] == "batch_processing"
        assert "successful_items" in result
        assert "failed_items" in result
        assert "results" in result
        
        print("✅ Handler批量处理测试通过")
    
    async def test_handler_validation(self):
        """测试Handler参数验证"""
        # 测试空数据验证
        with pytest.raises(ValueError, match="数据不能为空"):
            await self.foo_handler.handle_async_processing(data={})
        
        with pytest.raises(ValueError, match="数据不能为空"):
            self.foo_handler.handle_sync_processing(data={})
        
        # 测试处理时间限制
        result = await self.foo_handler.handle_async_processing(
            data={"test": "validation"},
            processing_time=50.0  # 超过限制
        )
        # 应该被调整为30秒
        assert result["processing_time"] <= 30.0
        
        print("✅ Handler参数验证测试通过")


class TestFooDecorators:
    """测试Foo相关装饰器"""
    
    def setup_method(self):
        """清理全局限流器状态"""
        global_rate_limiter.sliding_windows.clear()
        global_rate_limiter.token_buckets.clear()
    
    async def test_service_retry_decorator(self):
        """测试Service层重试装饰器"""
        foo_service = get_foo_service()
        
        # 重试机制在外部服务调用中，可能需要多次尝试
        success_count = 0
        attempt_count = 10
        
        for i in range(attempt_count):
            try:
                result = await foo_service.call_external_service(
                    endpoint="https://test.retry.com",
                    data={"attempt": i}
                )
                success_count += 1
            except ConnectionError:
                pass  # 预期的失败
        
        # 重试机制应该提高成功率
        success_rate = success_count / attempt_count
        assert success_rate > 0.5  # 应该有超过50%的成功率
        
        print(f"✅ Service重试装饰器测试通过: 成功率 {success_rate:.1%}")
    
    async def test_handler_retry_decorator(self):
        """测试Handler层重试装饰器"""
        foo_handler = FooHandler()
        
        # Handler的同步处理有重试装饰器
        success_count = 0
        attempt_count = 10
        
        for i in range(attempt_count):
            try:
                result = foo_handler.handle_sync_processing(
                    data={"retry_test": i},
                    processing_time=0.1
                )
                success_count += 1
            except Exception:
                pass  # 可能的失败
        
        # Handler重试应该有很高的成功率
        success_rate = success_count / attempt_count
        assert success_rate > 0.8  # 应该有超过80%的成功率
        
        print(f"✅ Handler重试装饰器测试通过: 成功率 {success_rate:.1%}")
    
    async def test_cache_decorator(self):
        """测试缓存装饰器"""
        foo_handler = FooHandler()
        
        # 测试状态检查的缓存
        start_time = time.time()
        result1 = await foo_handler.handle_status_check()
        first_time = time.time() - start_time
        
        start_time = time.time()
        result2 = await foo_handler.handle_status_check()
        second_time = time.time() - start_time
        
        # 第二次应该更快（缓存）
        assert second_time < first_time * 0.5
        assert result1["cached"] == result2["cached"]
        
        print(f"✅ 缓存装饰器测试通过: 缓存加速 {first_time/second_time:.1f}x")


class TestFooIntegration:
    """Foo服务集成测试"""
    
    async def test_full_async_flow(self):
        """测试完整异步流程"""
        foo_handler = FooHandler()
        
        # 模拟完整的异步处理流程
        test_data = {
            "integration_test": True,
            "complex_data": {
                "nested": {"value": 123},
                "array": [1, 2, 3, 4, 5],
                "metadata": {"type": "integration"}
            }
        }
        
        result = await foo_handler.handle_async_processing(
            data=test_data,
            processing_time=1.0,
            callback_url="https://example.com/callback"
        )
        
        # 验证完整流程
        assert result["processed"] is True
        assert result["handler"] == "FooHandler"
        assert result["flow"] == "async_processing"
        assert result["processing_type"] == "async"
        assert result["callback_registered"] is True
        
        print("✅ 完整异步流程测试通过")
    
    async def test_error_handling_flow(self):
        """测试错误处理流程"""
        foo_handler = FooHandler()
        
        # 测试各种错误情况
        error_cases = [
            ({}, "空数据"),
            (None, "None数据")
        ]
        
        for test_data, case_name in error_cases:
            with pytest.raises(ValueError, match="数据不能为空"):
                await foo_handler.handle_async_processing(data=test_data)
                
            with pytest.raises(ValueError, match="数据不能为空"):
                foo_handler.handle_sync_processing(data=test_data)
                
            print(f"✅ 错误处理测试通过: {case_name}")
    
    async def test_concurrent_processing(self):
        """测试并发处理"""
        foo_handler = FooHandler()
        
        # 创建并发任务
        tasks = []
        for i in range(5):
            task = foo_handler.handle_async_processing(
                data={"concurrent_test": i, "value": f"test_{i}"},
                processing_time=0.5
            )
            tasks.append(task)
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证结果
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 4  # 至少4个成功
        
        for result in successful_results:
            assert result["processed"] is True
            assert result["handler"] == "FooHandler"
        
        print(f"✅ 并发处理测试通过: {len(successful_results)}/5 成功")


async def run_foo_tests():
    """运行所有Foo测试"""
    print("=" * 60)
    print("Foo服务综合测试 - DDD架构 + 装饰器 + 任务系统")
    print("=" * 60)
    
    test_classes = [
        TestFooService(),
        TestFooHandler(),
        TestFooDecorators(),
        TestFooIntegration()
    ]
    
    all_passed = True
    
    for test_instance in test_classes:
        test_class_name = test_instance.__class__.__name__
        print(f"\n--- {test_class_name} ---")
        
        # 获取所有测试方法
        test_methods = [
            method for method in dir(test_instance)
            if method.startswith('test_') and callable(getattr(test_instance, method))
        ]
        
        for method_name in test_methods:
            try:
                test_method = getattr(test_instance, method_name)
                
                # 运行setup
                if hasattr(test_instance, 'setup_method'):
                    test_instance.setup_method()
                
                # 运行测试
                if asyncio.iscoroutinefunction(test_method):
                    await test_method()
                else:
                    test_method()
                
            except Exception as e:
                print(f"❌ {method_name} 失败: {str(e)}")
                all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有Foo测试通过！")
    else:
        print("❌ 部分测试失败")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_foo_tests())
    exit(0 if success else 1)