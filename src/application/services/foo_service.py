# src/application/services/foo_service.py (支持回调的更新版)
import asyncio
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from src.application.services.service_interface import BaseService
from src.infrastructure.tasks.callback_manager import CallbackManager, CallbackType, CallbackTrigger


class FooService(BaseService):
    """Foo服务 - 支持回调功能的演示服务"""
    
    def __init__(self):
        super().__init__()
        # 每个服务可以选择是否启用回调管理器
        self.callback_manager = CallbackManager()
        self.enable_callbacks = True  # 服务级开关
    
    def get_service_info(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "description": "Foo演示服务 - 支持异步回调",
            "version": "1.1.0",
            "category": "demo",
            "features": ["async_processing", "callback_support", "webhook_notifications"]
        }
    
    async def process_data_async(
        self, 
        data: Dict[str, Any], 
        callback_url: Optional[str] = None,
        on_success: Optional[Callable] = None,
        on_failure: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """异步数据处理 - 支持回调"""
        self.logger.info("开始异步数据处理")
        
        # 生成处理ID用于回调跟踪
        process_id = f"process_{random.randint(10000, 99999)}"
        
        # 注册回调（如果启用）
        if self.enable_callbacks:
            await self._register_callbacks(process_id, callback_url, on_success, on_failure)
        
        try:
            # 模拟复杂处理
            processing_time = random.uniform(2, 5)
            await asyncio.sleep(processing_time)
            
            # 模拟偶发失败
            if random.random() < 0.1:
                raise Exception("模拟处理失败")
            
            result = {
                "processed": True,
                "process_id": process_id,
                "original_data": data,
                "processed_at": datetime.utcnow().isoformat(),
                "processing_type": "async",
                "processing_time": processing_time
            }
            
            # 触发成功回调
            if self.enable_callbacks:
                await self._trigger_success_callbacks(process_id, result)
            
            return result
            
        except Exception as e:
            error_result = {
                "processed": False,
                "process_id": process_id,
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat()
            }
            
            # 触发失败回调
            if self.enable_callbacks:
                await self._trigger_failure_callbacks(process_id, error_result)
            
            raise
    
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
    
    async def process_with_external_api(
        self, 
        data: Dict[str, Any], 
        external_callback_url: str
    ) -> Dict[str, Any]:
        """
        调用外部API并支持回调链
        
        演示场景：
        1. 处理数据
        2. 调用外部异步API
        3. 等待外部API回调
        4. 触发最终回调
        """
        process_id = f"external_process_{random.randint(10000, 99999)}"
        
        self.logger.info(f"开始外部API处理: {process_id}")
        
        # Step 1: 本地预处理
        preprocessed_data = {
            **data,
            "preprocessed_at": datetime.utcnow().isoformat(),
            "process_id": process_id
        }
        
        # Step 2: 注册外部API完成后的回调
        if self.enable_callbacks:
            await self.callback_manager.webhook_on_completion(
                process_id,
                external_callback_url,
                auth_token="service_token_123",
                process_data=preprocessed_data
            )
        
        # Step 3: 模拟调用外部异步API
        external_response = await self._call_external_async_api(preprocessed_data)
        
        return {
            "process_id": process_id,
            "status": "submitted_to_external_api",
            "external_tracking_id": external_response.get("tracking_id"),
            "callback_registered": self.enable_callbacks,
            "message": "处理已提交到外部API，将通过回调通知结果"
        }
    
    async def handle_external_callback(
        self, 
        process_id: str, 
        external_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理外部API的回调"""
        self.logger.info(f"收到外部API回调: {process_id}")
        
        try:
            # 处理外部API结果
            final_result = {
                "process_id": process_id,
                "external_result": external_result,
                "final_processed_at": datetime.utcnow().isoformat(),
                "status": "completed"
            }
            
            # 这里可以触发后续的业务逻辑或通知
            self.logger.info(f"外部API处理完成: {process_id}")
            return final_result
            
        except Exception as e:
            self.logger.error(f"处理外部API回调失败: {process_id} - {str(e)}")
            raise
    
    async def _register_callbacks(
        self, 
        process_id: str, 
        callback_url: Optional[str] = None,
        on_success: Optional[Callable] = None,
        on_failure: Optional[Callable] = None
    ) -> None:
        """注册回调"""
        # 启动回调管理器（如果未启动）
        if not self.callback_manager._running:
            await self.callback_manager.start()
        
        # 注册Webhook回调
        if callback_url:
            self.callback_manager.webhook_on_completion(
                process_id, callback_url, 
                service="FooService", timestamp=datetime.utcnow().isoformat()
            )
        
        # 注册函数回调
        if on_success:
            self.callback_manager.on_success(process_id, on_success)
        
        if on_failure:
            self.callback_manager.on_failure(process_id, on_failure)
    
    async def _trigger_success_callbacks(
        self, 
        process_id: str, 
        result: Dict[str, Any]
    ) -> None:
        """触发成功回调"""
        # 创建一个模拟的task对象用于回调
        class MockTask:
            def __init__(self, task_id: str, result: Any):
                self.task_id = task_id
                self.task_name = "foo_async_processing"
                self.status = "success"
                self.result = result
                self.error = None
                self.duration = result.get("processing_time", 0)
        
        mock_task = MockTask(process_id, result)
        await self.callback_manager.trigger_callbacks(mock_task, "success")
    
    async def _trigger_failure_callbacks(
        self, 
        process_id: str, 
        error_result: Dict[str, Any]
    ) -> None:
        """触发失败回调"""
        class MockTask:
            def __init__(self, task_id: str, error_result: Dict[str, Any]):
                self.task_id = task_id
                self.task_name = "foo_async_processing"
                self.status = "failed"
                self.result = None
                self.error = error_result.get("error")
                self.duration = 0
        
        mock_task = MockTask(process_id, error_result)
        await self.callback_manager.trigger_callbacks(mock_task, "failed")
    
    async def _call_external_async_api(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """模拟调用外部异步API"""
        await asyncio.sleep(0.1)  # 模拟API调用时间
        
        return {
            "tracking_id": f"ext_{random.randint(10000, 99999)}",
            "status": "accepted",
            "estimated_completion": "5-10 minutes"
        }
    
    async def enable_callback_system(self) -> None:
        """启用回调系统"""
        self.enable_callbacks = True
        if not self.callback_manager._running:
            await self.callback_manager.start()
        self.logger.info("回调系统已启用")
    
    async def disable_callback_system(self) -> None:
        """禁用回调系统"""
        self.enable_callbacks = False
        if self.callback_manager._running:
            await self.callback_manager.shutdown()
        self.logger.info("回调系统已禁用")
    
    def get_callback_statistics(self) -> Dict[str, Any]:
        """获取回调统计信息"""
        if not self.enable_callbacks:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "statistics": self.callback_manager.get_statistics()
        }


# 懒加载
_foo_service = None

def get_foo_service() -> FooService:
    global _foo_service
    if _foo_service is None:
        _foo_service = FooService()
    return _foo_service