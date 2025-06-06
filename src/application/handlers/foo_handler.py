# src/application/handlers/foo_handler.py (简化版)
from typing import Any, Dict
from src.application.handlers.base_handler import BaseHandler
from src.application.services.foo_service import get_foo_service


class FooHandler(BaseHandler[Dict[str, Any]]):
    """Foo处理器 - 专注业务流程串流"""
    
    def __init__(self):
        super().__init__()
        self.foo_service = get_foo_service()
    
    async def handle_async_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理异步数据处理请求"""
        # 业务流程：验证 -> 处理 -> 记录
        if not data:
            raise ValueError("数据不能为空")
        
        result = await self.foo_service.process_data_async(data)
        
        # 可以添加额外的业务逻辑
        result["handler"] = "FooHandler"
        result["request_processed_at"] = "..."
        
        return result
    
    def handle_sync_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理同步数据处理请求"""
        if not data:
            raise ValueError("数据不能为空")
        
        result = self.foo_service.process_data_sync(data)
        result["handler"] = "FooHandler"
        
        return result
    
    async def _process_request(self, request_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """通用请求处理"""
        return {"message": "FooHandler就绪"}