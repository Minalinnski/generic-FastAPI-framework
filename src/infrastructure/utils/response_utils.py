# src/infrastructure/utils/response_utils.py
from typing import Any, Dict, List, Optional, TypeVar

from fastapi import status
from fastapi.responses import JSONResponse

from src.schemas.dtos.response.base_response import BaseResponse

T = TypeVar('T')


class ResponseHelper:
    """响应辅助工具类"""
    
    @staticmethod
    def success(
        data: Any = None, 
        message: str = "操作成功",
        status_code: int = status.HTTP_200_OK
    ) -> JSONResponse:
        """创建成功响应"""
        response = BaseResponse.success_response(data)
        
        return JSONResponse(
            status_code=status_code,
            content=response.dict()
        )
    
    @staticmethod
    def error(
        error: str,
        error_message: str = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """创建错误响应"""
        response = BaseResponse.error_response(error, error_message)
        
        return JSONResponse(
            status_code=status_code,
            content=response.dict()
        )
    
    @staticmethod
    def not_found(resource: str = "资源", resource_id: str = None) -> JSONResponse:
        """资源未找到响应"""
        error_message = f"{resource}未找到"
        if resource_id:
            error_message += f": {resource_id}"
        
        return ResponseHelper.error(
            error="NOT_FOUND",
            error_message=error_message,
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    @staticmethod
    def validation_error(
        field: str, 
        message: str, 
        value: Any = None
    ) -> JSONResponse:
        """验证错误响应"""
        details = {"field": field, "message": message}
        if value is not None:
            details["value"] = value
        
        return ResponseHelper.error(
            error="VALIDATION_ERROR",
            error_message=f"字段验证失败: {field}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )
    
    @staticmethod
    def paginated_response(
        items: List[T],
        total: int,
        page: int,
        size: int,
        message: str = "查询成功"
    ) -> JSONResponse:
        """分页响应"""
        pages = (total + size - 1) // size if size > 0 else 0
        
        data = {
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "size": size,
                "pages": pages,
                "has_next": page < pages,
                "has_prev": page > 1
            }
        }
        
        return ResponseHelper.success(data=data, message=message)


def create_error_detail(
    error_code: str,
    message: str,
    field: str = None,
    value: Any = None
) -> Dict[str, Any]:
    """创建错误详情"""
    detail = {
        "error_code": error_code,
        "message": message
    }
    
    if field:
        detail["field"] = field
    
    if value is not None:
        detail["value"] = value
    
    return detail