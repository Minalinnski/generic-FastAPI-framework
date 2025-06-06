# tests/simple_validation_test.py
"""
简单验证测试 - 确保修复正确
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


async def test_basic_functions():
    """测试基本功能"""
    print("=== 基本功能测试 ===")
    
    # 1. 测试正常功能
    print("\n1. 测试正常功能")
    foo_service = get_foo_service()
    foo_handler = FooHandler()
    
    # 正常的同步处理
    sync_result = foo_handler.handle_sync_processing(
        data={"test": "normal_sync"},
        processing_time=0.1
    )
    print(f"✅ 同步处理正常: {sync_result['process_id']}")
    
    # 正常的异步处理
    async_result = await foo_handler.handle_async_processing(
        data={"test": "normal_async"},
        processing_time=0.1
    )
    print(f"✅ 异步处理正常: {async_result['process_id']}")
    
    # 2. 测试参数验证
    print("\n2. 测试参数验证")
    
    # 测试异步处理的参数验证
    try:
        await foo_handler.handle_async_processing(data={})
        print("❌ 异步处理应该抛出ValueError")
        return False
    except ValueError as e:
        if "数据不能为空" in str(e):
            print("✅ 异步处理参数验证正确")
        else:
            print(f"❌ 异步处理错误消息不正确: {e}")
            return False
    except Exception as e:
        print(f"❌ 异步处理抛出了意外异常: {type(e).__name__}: {e}")
        return False
    
    # 测试同步处理的参数验证
    try:
        foo_handler.handle_sync_processing(data={})
        print("❌ 同步处理应该抛出ValueError")
        return False
    except ValueError as e:
        if "数据不能为空" in str(e):
            print("✅ 同步处理参数验证正确")
        else:
            print(f"❌ 同步处理错误消息不正确: {e}")
            return False
    except Exception as e:
        print(f"❌ 同步处理抛出了意外异常: {type(e).__name__}: {e}")
        return False
    
    # 3. 测试日志输出
    print("\n3. 测试日志输出")
    logger = get_logger("test")
    logger.debug("这是一条DEBUG日志")
    logger.info("这是一条INFO日志")
    logger.warning("这是一条WARNING日志")
    logger.error("这是一条ERROR日志")
    print("✅ 日志测试完成 - 检查上面是否有DEBUG日志输出")
    
    return True


def test_imports():
    """测试关键导入"""
    print("\n=== 导入测试 ===")
    
    try:
        import inspect
        print("✅ inspect导入成功")
    except ImportError:
        print("❌ inspect导入失败")
        return False
    
    try:
        from src.infrastructure.tasks.task_decorator import sync_task, async_task
        print("✅ task_decorator导入成功")
    except ImportError as e:
        print(f"❌ task_decorator导入失败: {e}")
        return False
    
    try:
        from src.infrastructure.decorators.rate_limit import api_rate_limit
        print("✅ rate_limit导入成功")
    except ImportError as e:
        print(f"❌ rate_limit导入失败: {e}")
        return False
    
    return True


async def main():
    """主函数"""
    print("FastAPI DDD Framework - 简单验证测试")
    print("=" * 50)
    
    # 设置日志
    settings = get_settings()
    setup_logging()
    
    logger = get_logger(__name__)
    logger.info(f"测试开始 - 环境: {settings.environment}, 日志级别: {settings.log_level}")
    
    # 测试导入
    if not test_imports():
        return False
    
    # 测试基本功能
    if not await test_basic_functions():
        return False
    
    print("\n" + "=" * 50)
    print("🎉 所有测试通过！现在你可以：")
    print("1. 启动服务: python -m uvicorn src.main:app --reload")
    print("2. 测试API: curl -X POST http://localhost:8000/api/v1/foo/sync \\")
    print("            -H 'Content-Type: application/json' \\")
    print("            -d '{\"data\": {\"test\": \"hello\"}, \"processing_time\": 1.0}'")
    print("3. 查看文档: http://localhost:8000/docs")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)