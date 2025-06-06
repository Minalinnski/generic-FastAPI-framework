# api/middleware/error_handler.py
import traceback
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.infrastructure.logging.logger import get_logger
from src.schemas.dtos.response.base_response import BaseResponse

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except ValueError as e:
            # 参数验证错误
            logger.warning(f"参数验证错误: {str(e)}", extra={
                "url": str(request.url),
                "method": request.method,
                "error": str(e)
            })
            error_response = BaseResponse.error_response(
                error="VALIDATION_ERROR",
                error_message=str(e)
            )
            return JSONResponse(
                status_code=400,
                content=error_response.dict()
            )
            
        except PermissionError as e:
            # 权限错误
            logger.warning(f"权限错误: {str(e)}", extra={
                "url": str(request.url),
                "method": request.method,
                "error": str(e)
            })
            error_response = BaseResponse.error_response(
                error="PERMISSION_ERROR",
                error_message="没有访问权限"
            )
            return JSONResponse(
                status_code=403,
                content=error_response.dict()
            )
            
        except FileNotFoundError as e:
            # 资源未找到错误
            logger.warning(f"资源未找到: {str(e)}", extra={
                "url": str(request.url),
                "method": request.method,
                "error": str(e)
            })
            error_response = BaseResponse.error_response(
                error="NOT_FOUND_ERROR",
                error_message="请求的资源不存在"
            )
            return JSONResponse(
                status_code=404,
                content=error_response.dict()
            )
            
        except Exception as e:
            # 其他未处理的异常
            logger.error(f"未处理的异常: {str(e)}", extra={
                "url": str(request.url),
                "method": request.method,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            error_response = BaseResponse.error_response(
                error="INTERNAL_SERVER_ERROR",
                error_message="服务器内部错误"
            )
            return JSONResponse(
                status_code=500,
                content=error_response.dict()
            )