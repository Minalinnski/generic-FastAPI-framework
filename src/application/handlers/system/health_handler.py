# handlers/health_handler.py
import asyncio
from datetime import datetime

from src.application.handlers.handler_interface import BaseHandler
from src.schemas.dtos.response.health_response import HealthData
from src.application.services.system.health_service import HealthService


class HealthHandler(BaseHandler[HealthData]):
    """健康检查控制器"""
    
    def __init__(self):
        super().__init__()
        self.health_service = HealthService()
    
    async def _process_request(self, request_data: dict = None) -> HealthData:
        """处理健康检查请求"""
        # 模拟异步检查过程
        await asyncio.sleep(0.05)
        
        # 调用服务层获取健康状态
        health_data = await self.health_service.check_health()
        
        return health_data
    
    def _process_sync_request(self, request_data: dict = None) -> HealthData:
        """处理同步健康检查请求"""
        import time
        time.sleep(0.01)
        
        # 调用服务层获取简单健康状态
        health_data = self.health_service.check_simple_health()
        
        return health_data