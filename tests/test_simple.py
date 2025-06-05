# tests/test_simple.py
"""
简化的测试文件，用于快速验证核心功能
"""
import asyncio
import time
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_rate_limiter():
    """测试限流器"""
    print("测试限流器...")
    
    from app.infrastructure.decorators.rate_limit import rate_limit, RateLimitExceeded
    
    @rate_limit(max_requests=3, window_seconds=2)
    async def limited_function():
        return "ok"
    
    # 前3次应该成功
    for i in range(3):
        result = await limited_function()
        assert result == "ok"
        print(f"  请求 {i+1}: 成功")
    
    # 第4次应该被限流
    try:
        await limited_function()
        print("  ❌ 第4次请求应该被限流但没有")
        return False
    except RateLimitExceeded:
        print("  ✅ 第4次请求被正确限流")
        return True


async def test_retry():
    """测试重试机制"""
    print("测试重试机制...")
    
    from app.infrastructure.decorators.retry import simple_retry
    
    call_count = 0
    
    @simple_retry(attempts=3, delay=0.1)
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        print(f"  尝试第 {call_count} 次")
        if call_count < 3:
            raise Exception("模拟失败")
        return "成功"
    
    result = await flaky_function()
    assert result == "成功"
    assert call_count == 3
    print("  ✅ 重试机制正常工作")
    return True


async def test_cache():
    """测试缓存"""
    print("测试缓存...")
    
    from app.infrastructure.decorators.cache import cache
    
    call_count = 0
    
    @cache(ttl=5, key_prefix="test:")
    async def cached_function(value):
        nonlocal call_count
        call_count += 1
        print(f"  实际执行第 {call_count} 次")
        return f"result_{value}"
    
    # 第一次调用
    result1 = await cached_function("test")
    assert result1 == "result_test"
    assert call_count == 1
    
    # 第二次调用应该使用缓存
    result2 = await cached_function("test")
    assert result2 == "result_test"
    assert call_count == 1  # 没有增加
    
    print("  ✅ 缓存机制正常工作")
    return True


async def test_task_registry():
    """测试任务注册表"""
    print("测试任务注册表...")
    
    from app.infrastructure.tasks.task_registry import task_registry
    
    # 注册一个简单任务
    async def simple_task(message: str):
        return f"处理: {message}"
    
    task_registry.register_service_function("simple_test_task", simple_task)
    
    # 创建任务
    task = task_registry.create_task("simple_test_task")
    assert task is not None
    
    # 执行任务
    result = await task.execute(message="测试消息")
    assert result == "处理: 测试消息"
    
    print("  ✅ 任务注册和执行正常")
    return True


async def main():
    """运行所有简单测试"""
    print("=" * 50)
    print("FastAPI DDD Framework 核心功能测试")
    print("=" * 50)
    
    tests = [
        test_rate_limiter,
        test_retry,
        test_cache,
        test_task_registry,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = await test_func()
            results.append(result)
            print()
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            results.append(False)
            print()
    
    success_count = sum(results)
    total_count = len(results)
    
    print("=" * 50)
    print(f"测试结果: {success_count}/{total_count} 通过")
    
    if success_count == total_count:
        print("🎉 所有核心功能测试通过!")
        return True
    else:
        print("❌ 部分测试失败")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)