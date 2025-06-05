# app/application/services/foo_service.py (简化版)
import asyncio
import random
from datetime import datetime
from typing import Any, Dict, List

from app.application.services.service_interface import BaseService


class FooService(BaseService):
    """Foo服务 - 专注业务逻辑"""
    
    def get_service_info(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "description": "Foo演示服务",
            "version": "1.0.0",
            "category": "demo"
        }
    
    async def process_data_async(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """异步数据处理"""
        self.logger.info("开始异步数据处理")
        
        # 模拟复杂处理
        await asyncio.sleep(random.uniform(2, 5))
        
        # 模拟偶发失败
        if random.random() < 0.1:
            raise Exception("模拟处理失败")
        
        return {
            "processed": True,
            "original_data": data,
            "processed_at": datetime.utcnow().isoformat(),
            "processing_type": "async"
        }
    
    def process_data_sync(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """同步数据处理"""
        self.logger.info("开始同步数据处理")
        
        # 模拟快速处理
        import time
        time.sleep(random.uniform(0.1, 0.5))
        
        return {
            "processed": True,
            "original_data": data,
            "processed_at": datetime.utcnow().isoformat(),
            "processing_type": "sync"
        }


# 懒加载
_foo_service = None

def get_foo_service() -> FooService:
    global _foo_service
    if _foo_service is None:
        _foo_service = FooService()
    return _foo_service
