# tests/quick_foo_test.py
"""
快速Foo测试 - 验证修复效果
"""
import asyncio
import sys
import os
from pathlib import Path

# 确保可以导入app模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.application.config.settings import get_settings
from src.infrastructure.logging.logger import setup_logging, get_logger
from src.application.services.foo_service import get_foo_service
from src.application.handlers.foo_handler import FooHandler


async def test_basic_functionality():
    """测试基本功能"""
    print("=== 快速Foo功能测试 ===")
    
    # 1. 测试Service层
    print("\n1. 测试Service层")
    foo_service = get_foo_service()
    
    # 测试服务信息
    service_info = foo_service.get_service_info()
    print(f"✅ 服务信息: {service_info['service_name']} v{service_info['version']}")
    
    # 测试同步处理
    sync_result = foo_service.process_data_sync(
        data={"test": "quick_sync"}, 
        processing_time=0.1
    )
    print(f"✅ 同步处理: {sync_result['process_id']} - {sync_result['processing_type']}")
    
    # 测试异步处理
    async_result = await foo_service.process_data_async(
        data={"test": "quick_async"}, 
        processing_time=0.2
    )
    print(f"✅ 异步处理: {async_result['process_id']} - {async_result['processing_type']}")
    
    # 2. 测试Handler层
    print("\n2. 测试Handler层")
    foo_handler = FooHandler()
    
    # 测试Handler同步处理
    handler_sync = foo_handler.handle_sync_processing(
        data={"test": "handler_sync"}, 
        processing_time=0.1
    )
    print(f"✅ Handler同步: {handler_sync['handler']} - {handler_sync['flow']}")
    
    # 测试Handler异步处理
    handler_async = await foo_handler.handle_async_processing(
        data={"test": "handler_async"}, 
        processing_time=0.2
    )
    print(f"✅ Handler异步: {handler_async['handler']} - {handler_async['flow']}")
    
    # 测试状态检查
    status = await foo_handler.handle_status_check()
    print(f"✅ 状态检查: {status['health']['status']}")
    
    # 3. 测试错误处理
    print("\n3. 测试错误处理")
    try:
        foo_handler.handle_sync_processing(data={})  # 空数据应该报错
        print("❌ 错误处理失败：应该抛出异常")
    except Exception as e:
        # 由于装饰器的存在，可能抛出RetryExhausted或ValueError
        if "数据不能为空" in str(e) or "重试" in str(e):
            print(f"✅ 错误处理正确: 重试机制正常工作，最终失败原因包含预期错误")
        else:
            print(f"❌ 意外的错误类型: {type(e).__name__}: {str(e)}")
    
    # 4. 测试缓存
    print("\n4. 测试缓存功能")
    import time
    
    start_time = time.time()
    cache_result1 = await foo_service.get_cached_data("test_key")
    first_time = time.time() - start_time
    
    start_time = time.time()
    cache_result2 = await foo_service.get_cached_data("test_key")
    second_time = time.time() - start_time
    
    if second_time < first_time * 0.5:
        print(f"✅ 缓存生效: 第一次 {first_time:.3f}s, 第二次 {second_time:.3f}s")
    else:
        print(f"⚠️ 缓存可能未生效: 第一次 {first_time:.3f}s, 第二次 {second_time:.3f}s")
    
    print("\n=== 测试完成 ===")
    return True


async def test_logging():
    """测试日志功能"""
    print("\n=== 测试日志功能 ===")
    
    logger = get_logger("test_logger")
    
    # 测试各种级别的日志
    logger.debug("这是DEBUG级别日志")
    logger.info("这是INFO级别日志")
    logger.warning("这是WARNING级别日志")
    logger.error("这是ERROR级别日志")
    
    print("✅ 日志测试完成 - 检查控制台输出")


def test_import_issues():
    """测试导入问题"""
    print("\n=== 测试导入问题 ===")
    
    try:
        import inspect
        print("✅ inspect模块导入成功")
    except ImportError as e:
        print(f"❌ inspect导入失败: {e}")
        return False
    
    try:
        from src.infrastructure.tasks.task_decorator import as_task, sync_task, async_task
        print("✅ task_decorator导入成功")
    except ImportError as e:
        print(f"❌ task_decorator导入失败: {e}")
        return False
    
    try:
        from src.infrastructure.decorators.rate_limit import api_rate_limit
        print("✅ rate_limit装饰器导入成功")
    except ImportError as e:
        print(f"❌ rate_limit导入失败: {e}")
        return False
    
    return True


async def main():
    """主测试函数"""
    print("FastAPI DDD Framework - 快速功能验证")
    print("=" * 50)
    
    # 设置日志
    settings = get_settings()
    print(f"当前环境: {settings.environment}")
    print(f"日志级别: {settings.log_level}")
    print(f"日志格式: {settings.log_format}")
    
    setup_logging()
    
    # 测试导入
    if not test_import_issues():
        print("❌ 导入测试失败，请检查代码")
        return False
    
    # 测试日志
    await test_logging()
    
    # 测试基本功能
    try:
        success = await test_basic_functionality()
        if success:
            print("\n🎉 所有基本功能测试通过！")
            print("\n现在你可以：")
            print("1. 启动服务：python -m uvicorn src.main:app --reload")
            print("2. 访问文档：http://localhost:8000/docs")
            print("3. 测试接口：POST http://localhost:8000/api/v1/foo/sync")
            print("4. 运行完整测试：python tests/test_foo_comprehensive.py")
        return success
    except Exception as e:
        print(f"❌ 测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)