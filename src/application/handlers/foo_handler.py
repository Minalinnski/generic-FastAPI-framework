# src/application/handlers/foo_handler.py
import asyncio
from typing import Any, Dict, Optional
from src.application.handlers.handler_interface import BaseHandler
from src.application.services.foo_service import get_foo_service
from src.infrastructure.decorators.retry import simple_retry
from src.infrastructure.decorators.cache import short_cache


class FooHandler(BaseHandler[Dict[str, Any]]):
    """
    Foo处理器 - 专注业务流程编排
    
    职责：
    1. 请求参数验证和预处理
    2. 业务流程编排和错误处理
    3. 响应包装和后处理
    """
    
    def __init__(self):
        super().__init__()
        self.foo_service = get_foo_service()
    
    async def handle_async_processing(
        self, 
        data: Dict[str, Any], 
        processing_time: float = 2.0,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理异步数据处理请求
        
        业务流程：验证 -> 异步处理 -> 包装响应
        注意：参数验证失败不应该重试，所以验证逻辑在装饰器外部
        """
        self.logger.info("开始异步处理流程", extra={
            "data_keys": list(data.keys()) if data else [],
            "processing_time": processing_time,
            "has_callback": bool(callback_url)
        })
        
        # 1. 业务参数验证（不重试）
        if not data:
            self.logger.warning("异步处理失败：数据不能为空")
            raise ValueError("数据不能为空")
        
        if processing_time > 30:
            self.logger.warning(f"处理时间过长：{processing_time}s，调整为30s")
            processing_time = 30.0
        
        # 2. 调用实际处理方法（可能带重试）
        return await self._async_processing_with_error_handling(
            data, processing_time, callback_url
        )
    
    async def _async_processing_with_error_handling(
        self, 
        data: Dict[str, Any], 
        processing_time: float,
        callback_url: Optional[str]
    ) -> Dict[str, Any]:
        """实际的异步处理逻辑（带错误处理）"""
        try:
            # 调用服务层进行业务处理
            result = await self.foo_service.process_data_async(
                data=data,
                processing_time=processing_time,
                callback_url=callback_url
            )
            
            # Handler层的后处理（业务流程相关）
            enhanced_result = {
                **result,
                "handler": "FooHandler",
                "flow": "async_processing",
                "request_processed_at": asyncio.get_event_loop().time()
            }
            
            self.logger.info("异步处理流程完成", extra={
                "process_id": result.get("process_id"),
                "processing_time": processing_time
            })
            
            return enhanced_result
            
        except Exception as e:
            self.logger.error(f"异步处理流程失败: {str(e)}", exc_info=True)
            raise
    
    def handle_sync_processing(
        self, 
        data: Dict[str, Any], 
        processing_time: float = 0.5
    ) -> Dict[str, Any]:
        """
        处理同步数据处理请求
        
        业务流程：验证 -> 同步处理 -> 包装响应
        注意：参数验证失败不应该重试，所以验证逻辑在装饰器外部
        """
        self.logger.info("开始同步处理流程", extra={
            "data_keys": list(data.keys()) if data else [],
            "processing_time": processing_time
        })
        
        # 1. 业务参数验证（不重试）
        if not data:
            self.logger.warning("同步处理失败：数据不能为空")
            raise ValueError("数据不能为空")
        
        if processing_time > 5:
            self.logger.warning(f"同步处理时间过长：{processing_time}s，调整为5s")
            processing_time = 5.0
        
        # 2. 调用实际处理方法（带重试）
        return self._sync_processing_with_retry(data, processing_time)
    
    @simple_retry(attempts=2, delay=0.5)  # 只对实际处理进行重试
    def _sync_processing_with_retry(
        self, 
        data: Dict[str, Any], 
        processing_time: float
    ) -> Dict[str, Any]:
        """实际的同步处理逻辑（带重试）"""
        try:
            # 调用服务层
            result = self.foo_service.process_data_sync(
                data=data,
                processing_time=processing_time
            )
            
            # Handler层后处理
            enhanced_result = {
                **result,
                "handler": "FooHandler", 
                "flow": "sync_processing",
                "request_processed_at": asyncio.get_event_loop().time()
            }
            
            self.logger.info("同步处理流程完成", extra={
                "processing_time": processing_time
            })
            
            return enhanced_result
            
        except Exception as e:
            self.logger.error(f"同步处理流程失败: {str(e)}", exc_info=True)
            raise
    
    @short_cache(ttl=300)  # 缓存5分钟
    async def handle_status_check(self) -> Dict[str, Any]:
        """
        处理状态检查请求
        
        业务流程：获取服务状态 -> 系统状态 -> 组合响应
        """
        self.logger.debug("开始状态检查流程")
        
        try:
            # 1. 获取服务信息
            service_info = self.foo_service.get_service_info()
            
            # 2. 获取服务运行状态
            service_health = await self.foo_service.health_check()
            
            # 3. 组合状态信息
            status_info = {
                "service": service_info,
                "health": service_health,
                "handler": "FooHandler",
                "cached": True  # 标识这个响应可能来自缓存
            }
            
            self.logger.debug("状态检查完成", extra={"status": service_health["status"]})
            return status_info
            
        except Exception as e:
            self.logger.error(f"状态检查失败: {str(e)}", exc_info=True)
            raise
    
    async def handle_batch_processing(
        self, 
        items: list[Dict[str, Any]], 
        processing_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        处理批量处理请求
        
        业务流程：验证 -> 批量处理 -> 汇总结果
        """
        self.logger.info(f"开始批量处理流程，共{len(items)}项", extra={
            "batch_size": len(items),
            "processing_time": processing_time
        })
        
        # 1. 批量验证
        if not items:
            raise ValueError("批量处理项目不能为空")
        
        if len(items) > 100:
            self.logger.warning(f"批量大小过大：{len(items)}，限制为100")
            items = items[:100]
        
        # 2. 调用服务层批量处理
        try:
            results = await self.foo_service.process_batch_async(
                items=items,
                processing_time=processing_time
            )
            
            # 3. Handler层汇总结果
            summary = {
                "total_items": len(items),
                "successful_items": len([r for r in results if r.get("success")]),
                "failed_items": len([r for r in results if not r.get("success")]),
                "processing_time": processing_time,
                "handler": "FooHandler",
                "flow": "batch_processing",
                "results": results
            }
            
            self.logger.info("批量处理完成", extra={
                "total": summary["total_items"],
                "success": summary["successful_items"],
                "failed": summary["failed_items"]
            })
            
            return summary
            
        except Exception as e:
            self.logger.error(f"批量处理失败: {str(e)}", exc_info=True)
            raise
    
    async def _process_request(self, request_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        通用请求处理 - BaseHandler要求实现的方法
        """
        self.logger.debug("FooHandler通用请求处理", extra={"request_data": request_data})
        
        if not request_data:
            return await self.handle_status_check()
        
        # 根据请求类型路由到不同的处理方法
        action = request_data.get("action", "status")
        
        if action == "async":
            return await self.handle_async_processing(request_data.get("data", {}))
        elif action == "sync":
            return self.handle_sync_processing(request_data.get("data", {}))
        elif action == "batch":
            return await self.handle_batch_processing(request_data.get("items", []))
        else:
            return await self.handle_status_check()