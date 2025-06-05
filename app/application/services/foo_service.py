# app/application/services/foo_service.py - 示例业务服务（包含模拟任务）
import asyncio
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.application.services.base_service import BaseService
from app.infrastructure.decorators.cache import cache, short_cache
from app.infrastructure.decorators.retry import network_retry, simple_retry
from app.infrastructure.tasks.task_registry import register_service_as_task


class FooService(BaseService):
    """
    示例业务服务 - 包含各种示例任务和业务逻辑
    
    这个服务展示了如何：
    1. 使用装饰器进行重试和缓存
    2. 注册服务函数为任务
    3. 实现同步和异步业务逻辑
    """
    
    def __init__(self):
        super().__init__()
        self.processing_data = {}
    
    @register_service_as_task(
        task_name="sample_data_processing",
        category="demo",
        description="示例数据处理任务",
        tags=["demo", "processing"]
    )
    @simple_retry(attempts=2, delay=1.0)
    async def process_sample_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理示例数据的任务"""
        self.logger.info("开始处理示例数据", extra={"data_keys": list(data.keys())})
        
        # 模拟数据处理
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # 随机失败模拟（用于测试重试）
        if random.random() < 0.1:  # 10%失败率
            raise Exception("模拟处理失败")
        
        result = {
            "processed": True,
            "input_data": data,
            "processed_at": datetime.utcnow().isoformat(),
            "processing_time": random.uniform(0.5, 2.0),
            "result_size": len(str(data)),
            "message": "数据处理完成"
        }
        
        self.logger.info("示例数据处理完成")
        return result
    
    @register_service_as_task(
        task_name="file_processing_simulation",
        category="demo",
        description="文件处理模拟任务",
        tags=["demo", "file", "simulation"]
    )
    async def simulate_file_processing(
        self, 
        file_path: str, 
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """模拟文件处理任务"""
        options = options or {}
        
        self.logger.info(f"开始模拟文件处理: {file_path}", extra={"options": options})
        
        # 模拟文件处理时间（根据"文件大小"）
        file_size = options.get("file_size", random.randint(1000, 10000))
        processing_time = file_size / 1000  # 模拟处理时间
        
        await asyncio.sleep(min(processing_time, 5.0))  # 最多5秒
        
        result = {
            "file_path": file_path,
            "original_size": file_size,
            "processed_size": file_size + random.randint(100, 500),
            "format": options.get("format", "processed"),
            "processing_time": processing_time,
            "output_path": f"processed_{file_path}",
            "metadata": {
                "processor": "FooService",
                "version": "1.0",
                "processed_at": datetime.utcnow().isoformat()
            }
        }
        
        self.logger.info(f"文件处理模拟完成: {file_path}")
        return result
    
    @register_service_as_task(
        task_name="data_analysis_task",
        category="demo",
        description="数据分析任务",
        tags=["demo", "analysis", "statistics"]
    )
    @cache(ttl=1800, key_prefix="analysis:")  # 缓存30分钟
    async def analyze_data(self, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """数据分析任务"""
        self.logger.info(f"开始数据分析: {len(dataset)} 条记录")
        
        # 模拟数据分析
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        # 计算一些统计信息
        if not dataset:
            return {"error": "数据集为空"}
        
        # 提取数值字段进行分析
        numeric_fields = []
        for record in dataset:
            for key, value in record.items():
                if isinstance(value, (int, float)):
                    numeric_fields.append(value)
        
        analysis_result = {
            "record_count": len(dataset),
            "numeric_field_count": len(numeric_fields),
            "statistics": {
                "mean": sum(numeric_fields) / len(numeric_fields) if numeric_fields else 0,
                "min": min(numeric_fields) if numeric_fields else 0,
                "max": max(numeric_fields) if numeric_fields else 0,
                "sum": sum(numeric_fields) if numeric_fields else 0
            },
            "analysis_time": datetime.utcnow().isoformat(),
            "sample_data": dataset[:3] if len(dataset) > 3 else dataset
        }
        
        self.logger.info("数据分析完成")
        return analysis_result
    
    @register_service_as_task(
        task_name="external_api_simulation",
        category="demo",
        description="外部API调用模拟",
        tags=["demo", "external", "api"]
    )
    @network_retry(attempts=3)
    async def simulate_external_api_call(
        self, 
        api_endpoint: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """模拟外部API调用"""
        params = params or {}
        
        self.logger.info(f"模拟外部API调用: {api_endpoint}")
        
        # 模拟网络延迟
        await asyncio.sleep(random.uniform(0.2, 1.0))
        
        # 模拟网络错误（用于测试重试）
        if random.random() < 0.15:  # 15%失败率
            raise ConnectionError("模拟网络连接失败")
        
        # 模拟API响应
        response = {
            "status": "success",
            "endpoint": api_endpoint,
            "params": params,
            "response_time": random.uniform(0.1, 0.5),
            "data": {
                "id": random.randint(1000, 9999),
                "timestamp": datetime.utcnow().isoformat(),
                "result": f"API调用成功: {api_endpoint}"
            }
        }
        
        self.logger.info(f"外部API调用完成: {api_endpoint}")
        return response
    
    @short_cache(ttl=300)  # 缓存5分钟
    async def get_cached_config(self, config_type: str) -> Dict[str, Any]:
        """获取缓存的配置信息"""
        self.logger.info(f"获取配置: {config_type}")
        
        # 模拟从数据库或外部服务获取配置
        await asyncio.sleep(0.1)
        
        configs = {
            "app": {"version": "1.0.0", "debug": False, "features": ["task_system", "caching"]},
            "database": {"host": "localhost", "port": 5432, "pool_size": 10},
            "cache": {"ttl": 3600, "max_size": 10000}
        }
        
        return configs.get(config_type, {})
    
    async def batch_process_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量处理项目（不注册为任务，直接使用）"""
        self.logger.info(f"批量处理 {len(items)} 个项目")
        
        results = []
        for item in items:
            # 模拟处理每个项目
            await asyncio.sleep(0.1)
            
            processed_item = {
                **item,
                "processed": True,
                "processed_at": datetime.utcnow().isoformat(),
                "processing_id": random.randint(1000, 9999)
            }
            results.append(processed_item)
        
        self.logger.info("批量处理完成")
        return results
    
    def sync_calculation(self, numbers: List[float]) -> Dict[str, float]:
        """同步计算任务（演示同步任务）"""
        self.logger.info(f"执行同步计算: {len(numbers)} 个数字")
        
        if not numbers:
            return {"error": "数字列表为空"}
        
        result = {
            "count": len(numbers),
            "sum": sum(numbers),
            "mean": sum(numbers) / len(numbers),
            "min": min(numbers),
            "max": max(numbers),
            "range": max(numbers) - min(numbers)
        }
        
        self.logger.info("同步计算完成")
        return result
    
    async def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "service_name": "FooService",
            "status": "healthy",
            "registered_tasks": [
                "sample_data_processing",
                "file_processing_simulation", 
                "data_analysis_task",
                "external_api_simulation"
            ],
            "cache_status": "enabled",
            "retry_enabled": True,
            "processing_data_count": len(self.processing_data)
        }


# 注册同步任务（不使用装饰器的方式）
from app.infrastructure.tasks.task_registry import task_registry

# 为同步计算创建一个包装函数
def sync_calculation_wrapper(numbers: List[float]) -> Dict[str, float]:
    """同步计算的包装器"""
    service = FooService()
    return service.sync_calculation(numbers)

# 手动注册同步任务
task_registry.register_service_function(
    task_name="sync_calculation_task",
    service_func=sync_calculation_wrapper,
    category="demo",
    description="同步数学计算任务",
    tags=["demo", "sync", "math"]
)