# src/application/services/foo_service.py
import asyncio
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.application.services.service_interface import BaseService
from src.infrastructure.decorators.retry import network_retry, simple_retry
from src.infrastructure.decorators.cache import api_cache


class FooService(BaseService):
    """
    Foo服务 - 专注具体业务逻辑实现
    
    职责：
    1. 具体的业务逻辑处理
    2. 外部依赖调用（模拟）
    3. 数据转换和计算
    """
    
    def __init__(self):
        super().__init__()
        self._processing_count = 0
    
    def get_service_info(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "description": "Foo演示服务 - DDD架构示例",
            "version": "2.0.0",
            "category": "demo",
            "features": [
                "sync_processing", 
                "async_processing", 
                "batch_processing",
                "retry_mechanism",
                "caching_support"
            ],
            "processing_count": self._processing_count
        }
    
    async def process_data_async(
        self, 
        data: Dict[str, Any], 
        processing_time: float = 2.0,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        异步数据处理 - 模拟复杂的异步业务逻辑
        """
        process_id = f"async_{self._processing_count:04d}"
        self._processing_count += 1
        
        self.logger.info(f"开始异步数据处理: {process_id}", extra={
            "process_id": process_id,
            "data_size": len(str(data)),
            "processing_time": processing_time,
            "has_callback": bool(callback_url)
        })
        
        try:
            # 模拟复杂处理
            await asyncio.sleep(processing_time)
            
            # 模拟偶发失败（5%概率）
            if random.random() < 0.05:
                raise Exception(f"模拟处理失败: {process_id}")
            
            # 模拟数据处理结果
            processed_data = {
                **data,
                "processed": True,
                "process_id": process_id,
                "processing_time": processing_time,
                "processed_at": datetime.utcnow().isoformat(),
                "processing_type": "async",
                "data_size": len(str(data)),
                "enhancement": f"enhanced_value_{random.randint(1000, 9999)}"
            }
            
            # 如果有回调URL，模拟回调注册
            if callback_url:
                processed_data["callback_registered"] = True
                processed_data["callback_url"] = callback_url
            
            self.logger.info(f"异步数据处理完成: {process_id}", extra={
                "process_id": process_id,
                "success": True
            })
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"异步数据处理失败: {process_id} - {str(e)}")
            raise
    
    @simple_retry(attempts=2, delay=0.1)  # Service层重试外部调用
    def process_data_sync(
        self, 
        data: Dict[str, Any], 
        processing_time: float = 0.5
    ) -> Dict[str, Any]:
        """
        同步数据处理 - 模拟快速的同步业务逻辑
        """
        process_id = f"sync_{self._processing_count:04d}"
        self._processing_count += 1
        
        self.logger.info(f"开始同步数据处理: {process_id}", extra={
            "process_id": process_id,
            "processing_time": processing_time
        })
        
        try:
            # 模拟处理时间
            time.sleep(processing_time)
            
            # 模拟偶发失败（2%概率，比异步低）
            if random.random() < 0.02:
                raise Exception(f"模拟同步处理失败: {process_id}")
            
            processed_data = {
                **data,
                "processed": True,
                "process_id": process_id,
                "processing_time": processing_time,
                "processed_at": datetime.utcnow().isoformat(),
                "processing_type": "sync",
                "data_size": len(str(data)),
                "quick_result": f"quick_{random.randint(100, 999)}"
            }
            
            self.logger.info(f"同步数据处理完成: {process_id}")
            return processed_data
            
        except Exception as e:
            self.logger.error(f"同步数据处理失败: {process_id} - {str(e)}")
            raise
    
    async def process_batch_async(
        self, 
        items: List[Dict[str, Any]], 
        processing_time: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        批量异步处理 - 模拟批量业务逻辑
        """
        batch_id = f"batch_{self._processing_count:04d}"
        self._processing_count += 1
        
        self.logger.info(f"开始批量处理: {batch_id}", extra={
            "batch_id": batch_id,
            "batch_size": len(items),
            "processing_time": processing_time
        })
        
        results = []
        
        for i, item in enumerate(items):
            try:
                # 模拟每个项目的处理时间
                await asyncio.sleep(processing_time / len(items))
                
                # 模拟部分失败（10%概率）
                if random.random() < 0.1:
                    raise Exception(f"批量项目 {i} 处理失败")
                
                result = {
                    **item,
                    "success": True,
                    "batch_id": batch_id,
                    "item_index": i,
                    "processed_at": datetime.utcnow().isoformat(),
                    "batch_result": f"batch_item_{i}_{random.randint(10, 99)}"
                }
                
                results.append(result)
                
            except Exception as e:
                self.logger.warning(f"批量项目 {i} 处理失败: {str(e)}")
                results.append({
                    **item,
                    "success": False,
                    "error": str(e),
                    "batch_id": batch_id,
                    "item_index": i
                })
        
        successful_count = len([r for r in results if r.get("success")])
        self.logger.info(f"批量处理完成: {batch_id}", extra={
            "successful": successful_count,
            "total": len(items)
        })
        
        return results
    
    @network_retry(attempts=3)  # 网络调用重试
    async def call_external_service(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用外部服务 - 模拟外部依赖调用
        """
        self.logger.info(f"调用外部服务: {endpoint}")
        
        # 模拟网络延迟
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # 模拟网络失败（20%概率）
        if random.random() < 0.2:
            raise ConnectionError(f"外部服务调用失败: {endpoint}")
        
        # 模拟成功响应
        response = {
            "external_service": endpoint,
            "request_data": data,
            "response_id": f"ext_{random.randint(10000, 99999)}",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success"
        }
        
        self.logger.info(f"外部服务调用成功: {endpoint}")
        return response
    
    @api_cache(ttl=600)  # 缓存10分钟
    async def get_cached_data(self, key: str) -> Dict[str, Any]:
        """
        获取缓存数据 - 模拟缓存机制
        """
        self.logger.debug(f"获取缓存数据: {key}")
        
        # 模拟数据库或外部API调用
        await asyncio.sleep(0.5)
        
        cached_data = {
            "key": key,
            "data": f"cached_value_{random.randint(1000, 9999)}",
            "generated_at": datetime.utcnow().isoformat(),
            "cache_ttl": 600
        }
        
        self.logger.debug(f"缓存数据生成: {key}")
        return cached_data
    
    async def health_check(self) -> Dict[str, Any]:
        """服务健康检查"""
        try:
            # 模拟健康检查逻辑
            await asyncio.sleep(0.01)
            
            # 检查服务状态
            is_healthy = self._processing_count >= 0  # 简单检查
            
            return {
                "service": self.service_name,
                "status": "healthy" if is_healthy else "unhealthy",
                "processing_count": self._processing_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {str(e)}")
            return {
                "service": self.service_name,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def reset_counters(self) -> Dict[str, Any]:
        """重置计数器 - 用于测试"""
        old_count = self._processing_count
        self._processing_count = 0
        
        self.logger.info(f"计数器已重置: {old_count} -> 0")
        return {
            "old_count": old_count,
            "new_count": self._processing_count,
            "reset_at": datetime.utcnow().isoformat()
        }


# 懒加载
_foo_service = None

def get_foo_service() -> FooService:
    """获取Foo服务实例"""
    global _foo_service
    if _foo_service is None:
        _foo_service = FooService()
    return _foo_service