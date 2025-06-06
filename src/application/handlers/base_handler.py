# src/application/handlers/base_handler.py
import asyncio
from typing import Any, Dict, Generic, TypeVar

from src.infrastructure.logging.logger import get_logger
from src.schemas.dtos.response.base_response import BaseResponse

T = TypeVar('T')


class BaseHandler(Generic[T]):
    """基础处理器类，提供通用的业务流程编排功能"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    async def handle_request(self, request_data: Dict[str, Any] = None) -> BaseResponse[T]:
        """处理请求的通用模板方法"""
        try:
            self.logger.info("开始处理请求", extra={"request_data": request_data})
            
            # 调用具体的处理逻辑
            result = await self._process_request(request_data)
            
            self.logger.info("请求处理成功")
            return BaseResponse.success_response(result)
            
        except Exception as e:
            self.logger.error(f"请求处理失败: {str(e)}", exc_info=True)
            return BaseResponse.error_response(
                error="HANDLER_ERROR",
                error_message=f"处理请求时发生错误: {str(e)}"
            )
    
    async def _process_request(self, request_data: Dict[str, Any] = None) -> T:
        """子类需要实现的具体处理逻辑"""
        raise NotImplementedError("子类必须实现 _process_request 方法")
    
    def handle_sync_request(self, request_data: Dict[str, Any] = None) -> BaseResponse[T]:
        """处理同步请求"""
        try:
            self.logger.info("开始处理同步请求", extra={"request_data": request_data})
            
            result = self._process_sync_request(request_data)
            
            self.logger.info("同步请求处理成功")
            return BaseResponse.success_response(result)
            
        except Exception as e:
            self.logger.error(f"同步请求处理失败: {str(e)}", exc_info=True)
            return BaseResponse.error_response(
                error="SYNC_HANDLER_ERROR",
                error_message=f"处理同步请求时发生错误: {str(e)}"
            )
    
    def _process_sync_request(self, request_data: Dict[str, Any] = None) -> T:
        """子类需要实现的同步处理逻辑"""
        raise NotImplementedError("子类必须实现 _process_sync_request 方法")