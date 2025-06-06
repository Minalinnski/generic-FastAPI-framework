# tests/debug_worker_issue.py
"""
调试Worker执行问题
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
from src.infrastructure.tasks.worker_pool import WorkerPool, Worker
from src.infrastructure.tasks.base_task import create_simple_task


async def test_worker_execution():
    """直接测试Worker执行"""
    print("=== 直接测试Worker执行 ===")
    
    # 设置日志
    setup_logging()
    logger = get_logger(__name__)
    
    # 创建工作者池
    worker_pool = WorkerPool(max_workers=2)
    await worker_pool.start()
    
    # 创建简单任务
    async def test_func(message: str):
        await asyncio.sleep(0.1)
        return f"处理: {message}"
    
    task = create_simple_task(
        task_name="direct_test",
        task_func=test_func,
        priority=1,
        timeout=30
    )
    task.task_id = "direct_test_123"
    task.params = {"message": "直接测试"}
    
    print(f"创建任务: {task.task_name}")
    print(f"任务ID: {task.task_id}")
    print(f"任务类型: {type(task).__name__}")
    
    # 获取工作者
    worker = await worker_pool.get_worker()
    if not worker:
        print("❌ 无法获取工作者")
        return False
    
    print(f"获得工作者: {worker.worker_id}")
    
    try:
        # 直接调用execute_task
        print("开始执行任务...")
        result = await worker_pool.execute_task(task, worker)
        print(f"✅ 任务执行成功: {result}")
        return True
        
    except Exception as e:
        print(f"❌ 任务执行失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await worker_pool.release_worker(worker)
        await worker_pool.shutdown()


async def test_task_execute_method():
    """测试任务的execute方法"""
    print("\n=== 测试任务execute方法 ===")
    
    async def test_func(message: str):
        print(f"执行测试函数: {message}")
        await asyncio.sleep(0.1)
        return f"结果: {message}"
    
    task = create_simple_task(
        task_name="execute_test",
        task_func=test_func,
        priority=1,
        timeout=30
    )
    task.task_id = "execute_test_123"
    task.params = {"message": "execute测试"}
    
    print(f"任务类型: {type(task).__name__}")
    print(f"任务是否有execute方法: {hasattr(task, 'execute')}")
    
    if hasattr(task, 'execute'):
        try:
            print("直接调用task.execute()...")
            result = await task.execute()
            print(f"✅ task.execute()成功: {result}")
            return True
        except Exception as e:
            print(f"❌ task.execute()失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("❌ 任务没有execute方法")
        return False


async def test_worker_pool_method():
    """测试WorkerPool的execute_task方法"""
    print("\n=== 测试WorkerPool.execute_task方法 ===")
    
    # 创建工作者池
    worker_pool = WorkerPool(max_workers=1)
    await worker_pool.start()
    
    # 检查方法是否存在
    print(f"WorkerPool是否有execute_task方法: {hasattr(worker_pool, 'execute_task')}")
    
    # 列出WorkerPool的所有方法
    methods = [method for method in dir(worker_pool) if callable(getattr(worker_pool, method)) and not method.startswith('_')]
    print(f"WorkerPool的公共方法: {methods}")
    
    await worker_pool.shutdown()
    return True


async def main():
    """主函数"""
    print("调试Worker执行问题")
    print("=" * 40)
    
    # 测试1: 任务execute方法
    result1 = await test_task_execute_method()
    
    # 测试2: WorkerPool方法
    result2 = await test_worker_pool_method()
    
    # 测试3: 直接Worker执行
    result3 = await test_worker_execution()
    
    print("\n" + "=" * 40)
    print("测试结果:")
    print(f"任务execute方法: {'✅' if result1 else '❌'}")
    print(f"WorkerPool方法检查: {'✅' if result2 else '❌'}")
    print(f"Worker直接执行: {'✅' if result3 else '❌'}")
    
    return all([result1, result2, result3])


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)