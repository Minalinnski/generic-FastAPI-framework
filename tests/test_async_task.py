# tests/async_task_test.py
"""
异步任务专项测试 - 调试任务执行问题
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
from src.infrastructure.tasks.task_manager import task_manager
from src.infrastructure.tasks.base_task import create_simple_task
from src.infrastructure.tasks.request_task import RequestTask
from src.application.handlers.foo_handler import FooHandler


async def test_simple_task():
    """测试简单任务"""
    print("\n=== 测试简单任务 ===")
    
    async def simple_test_func(message: str):
        """简单的测试函数"""
        await asyncio.sleep(0.1)
        return f"处理完成: {message}"
    
    # 创建简单任务
    task = create_simple_task(
        task_name="simple_test",
        task_func=simple_test_func,
        priority=1,
        timeout=30
    )
    
    # 设置任务参数 - 这是关键修复
    task.params = {"message": "测试消息"}
    
    print(f"创建任务: {task.task_name}")
    print(f"任务参数: {task.params}")
    
    # 提交任务
    task_id = await task_manager.submit_task(task)
    print(f"任务已提交: {task_id}")
    
    # 等待任务完成
    for i in range(10):  # 最多等待10秒
        await asyncio.sleep(1)
        status = await task_manager.get_task_status(task_id)
        if status:
            print(f"任务状态: {status['status']}")
            if status['status'] in ['success', 'failed', 'cancelled', 'timeout']:
                break
    
    # 获取最终状态
    final_status = await task_manager.get_task_status(task_id)
    if final_status:
        print(f"最终状态: {final_status['status']}")
        if final_status['status'] == 'success':
            print(f"任务结果: {final_status.get('result')}")
            return True
        else:
            print(f"任务失败: {final_status.get('error')}")
            return False
    else:
        print("无法获取任务状态")
        return False


async def test_request_task():
    """测试RequestTask"""
    print("\n=== 测试RequestTask ===")
    
    # 创建Handler实例
    foo_handler = FooHandler()
    
    # 模拟请求参数
    args = ()
    kwargs = {
        "data": {"test": "request_task"},
        "processing_time": 0.5
    }
    
    # 创建RequestTask
    task = RequestTask(
        handler_func=foo_handler.handle_async_processing,
        args=args,
        kwargs=kwargs,
        task_name="test_request_task",
        timeout=30,
        max_retries=1,
        request_id="test_request_123"
    )
    
    print(f"创建RequestTask: {task.task_name}")
    
    # 提交任务
    task_id = await task_manager.submit_task(task)
    print(f"RequestTask已提交: {task_id}")
    
    # 监控任务执行
    for i in range(15):  # 最多等待15秒
        await asyncio.sleep(1)
        status = await task_manager.get_task_status(task_id)
        if status:
            current_status = status['status']
            print(f"任务状态 ({i+1}s): {current_status}")
            
            if current_status == 'running':
                print(f"  - 工作者: {status.get('worker_id')}")
                print(f"  - 开始时间: {status.get('start_time')}")
            
            if current_status in ['success', 'failed', 'cancelled', 'timeout']:
                break
        else:
            print(f"无法获取状态 ({i+1}s)")
    
    # 获取最终状态
    final_status = await task_manager.get_task_status(task_id)
    if final_status:
        print(f"\n最终状态: {final_status['status']}")
        if final_status['status'] == 'success':
            print(f"任务结果: {final_status.get('result')}")
            return True
        else:
            print(f"任务失败: {final_status.get('error')}")
            if final_status.get('error_details'):
                print(f"错误详情: {final_status['error_details']}")
            return False
    else:
        print("无法获取最终任务状态")
        return False


async def test_task_system_components():
    """测试任务系统各组件"""
    print("\n=== 测试任务系统组件 ===")
    
    # 测试任务管理器状态
    if not task_manager._running:
        print("启动任务管理器...")
        await task_manager.start()
    
    # 获取工作者池状态
    worker_stats = task_manager.worker_pool.get_statistics()
    print(f"工作者池状态:")
    print(f"  - 总工作者: {worker_stats['current_state']['total_workers']}")
    print(f"  - 可用工作者: {worker_stats['current_state']['available_workers']}")
    print(f"  - 忙碌工作者: {worker_stats['current_state']['busy_workers']}")
    
    # 获取队列状态
    queue_info = task_manager.get_queue_info()
    print(f"队列状态:")
    print(f"  - 队列大小: {queue_info['queue_size']}")
    print(f"  - 运行中任务: {queue_info['running_tasks']}")
    
    # 获取统计信息
    stats = await task_manager.get_statistics()
    print(f"任务统计:")
    print(f"  - 总提交: {stats['runtime']['total_tasks']}")
    print(f"  - 已完成: {stats['runtime']['completed_tasks']}")
    print(f"  - 失败: {stats['runtime']['failed_tasks']}")
    
    return True


async def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    async def failing_func():
        """故意失败的函数"""
        await asyncio.sleep(0.1)
        raise ValueError("这是一个测试错误")
    
    # 创建会失败的任务
    task = create_simple_task(
        task_name="failing_test",
        task_func=failing_func,
        priority=1,
        timeout=30,
        max_retries=2
    )
    
    print(f"创建失败任务: {task.task_name} (重试次数: {task.max_retries})")
    
    # 提交任务
    task_id = await task_manager.submit_task(task)
    print(f"失败任务已提交: {task_id}")
    
    # 监控执行
    retry_count = 0
    for i in range(20):  # 最多等待20秒
        await asyncio.sleep(1)
        status = await task_manager.get_task_status(task_id)
        if status:
            current_status = status['status']
            current_retry = status.get('retry_count', 0)
            
            if current_retry > retry_count:
                retry_count = current_retry
                print(f"任务重试: 第{retry_count}次")
            
            print(f"状态 ({i+1}s): {current_status} (重试: {current_retry})")
            
            if current_status in ['failed', 'success', 'cancelled', 'timeout']:
                break
        else:
            print(f"无法获取状态 ({i+1}s)")
    
    # 检查最终结果
    final_status = await task_manager.get_task_status(task_id)
    if final_status:
        print(f"最终状态: {final_status['status']}")
        print(f"最终重试次数: {final_status.get('retry_count')}")
        print(f"错误信息: {final_status.get('error')}")
        
        # 应该失败并达到最大重试次数
        return (final_status['status'] == 'failed' and 
                final_status.get('retry_count') == 2)
    
    return False


async def main():
    """主测试函数"""
    print("异步任务系统专项测试")
    print("=" * 50)
    
    # 设置日志
    settings = get_settings()
    setup_logging()
    
    logger = get_logger(__name__)
    logger.info("开始异步任务测试")
    
    # 确保任务管理器启动
    if not task_manager._running:
        print("启动任务管理器...")
        await task_manager.start()
    
    test_results = []
    
    # 1. 测试系统组件
    try:
        result = await test_task_system_components()
        test_results.append(("系统组件", result))
    except Exception as e:
        print(f"系统组件测试失败: {e}")
        test_results.append(("系统组件", False))
    
    # 2. 测试简单任务
    try:
        result = await test_simple_task()
        test_results.append(("简单任务", result))
    except Exception as e:
        print(f"简单任务测试失败: {e}")
        test_results.append(("简单任务", False))
    
    # 3. 测试RequestTask
    try:
        result = await test_request_task()
        test_results.append(("RequestTask", result))
    except Exception as e:
        print(f"RequestTask测试失败: {e}")
        test_results.append(("RequestTask", False))
    
    # 4. 测试错误处理
    try:
        result = await test_error_handling()
        test_results.append(("错误处理", result))
    except Exception as e:
        print(f"错误处理测试失败: {e}")
        test_results.append(("错误处理", False))
    
    # 输出结果
    print("\n" + "=" * 50)
    print("测试结果:")
    all_passed = True
    for test_name, passed in test_results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有异步任务测试通过！")
    else:
        print("\n⚠️ 部分测试失败，检查日志获取详细信息")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)