# schemas/dtos/response/base_response.py
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar('T')


class BaseResponse(BaseModel, Generic[T]):
    """通用响应DTO，包装所有API响应"""
    
    data: Optional[T] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误代码")
    error_message: Optional[str] = Field(None, description="错误详细信息")
    success: bool = Field(True, description="请求是否成功")
    
    @classmethod
    def success_response(cls, data: T = None) -> "BaseResponse[T]":
        """创建成功响应"""
        return cls(
            data=data,
            error=None,
            error_message=None,
            success=True
        )
    
    @classmethod
    def error_response(cls, error: str, error_message: str = None) -> "BaseResponse[None]":
        """创建错误响应"""
        return cls(
            data=None,
            error=error,
            error_message=error_message or error,
            success=False
        )
    
    class Config:
        schema_extra = {
            "example": {
                "data": {},
                "error": None,
                "error_message": None,
                "success": True
            }
        }