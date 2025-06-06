# schemas/dtos/request/base_request.py
from typing import Any, Dict, Optional

from pydantic import Field, validator

from src.schemas.base_schema import BaseSchema


class BaseRequest(BaseSchema):
    """基础请求DTO"""
    
    request_id: Optional[str] = Field(None, description="请求ID")
    client_info: Optional[Dict[str, Any]] = Field(None, description="客户端信息")
    
    class Config(BaseSchema.Config):
        schema_extra = {
            "example": {
                "request_id": "req_123456789",
                "client_info": {
                    "version": "1.0.0",
                    "platform": "web"
                }
            }
        }


class CreateRequest(BaseRequest):
    """创建资源的基础请求"""
    
    class Config(BaseRequest.Config):
        schema_extra = {
            "example": {
                "request_id": "req_create_123",
                "client_info": {"version": "1.0.0"}
            }
        }


class UpdateRequest(BaseRequest):
    """更新资源的基础请求"""
    
    id: str = Field(..., description="资源ID")
    version: Optional[int] = Field(None, description="资源版本号（乐观锁）")
    
    class Config(BaseRequest.Config):
        schema_extra = {
            "example": {
                "id": "resource_123",
                "version": 1,
                "request_id": "req_update_123",
                "client_info": {"version": "1.0.0"}
            }
        }


class DeleteRequest(BaseRequest):
    """删除资源的基础请求"""
    
    id: str = Field(..., description="资源ID")
    force: bool = Field(False, description="是否强制删除")
    
    class Config(BaseRequest.Config):
        schema_extra = {
            "example": {
                "id": "resource_123",
                "force": False,
                "request_id": "req_delete_123"
            }
        }


class QueryRequest(BaseRequest):
    """查询资源的基础请求"""
    
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页大小")
    sort_by: Optional[str] = Field(None, description="排序字段")
    sort_order: str = Field("asc", pattern="^(asc|desc)$", description="排序方向")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    search: Optional[str] = Field(None, min_length=2, description="搜索关键词")
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        return v.lower()
    
    @validator('search')
    def validate_search(cls, v):
        return v.strip() if v else None
    
    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.size
    
    class Config(BaseRequest.Config):
        schema_extra = {
            "example": {
                "page": 1,
                "size": 20,
                "sort_by": "created_at",
                "sort_order": "desc",
                "search": "keyword",
                "filters": {"status": "active"},
                "request_id": "req_query_123"
            }
        }


class BulkRequest(BaseRequest):
    """批量操作的基础请求"""
    
    ids: list[str] = Field(..., min_items=1, max_items=100, description="资源ID列表")
    operation: str = Field(..., description="操作类型")
    params: Optional[Dict[str, Any]] = Field(None, description="操作参数")
    
    @validator('ids')
    def validate_ids(cls, v):
        if not v:
            raise ValueError("IDs list cannot be empty")
        return list(set(v))  # 去重
    
    class Config(BaseRequest.Config):
        schema_extra = {
            "example": {
                "ids": ["id1", "id2", "id3"],
                "operation": "update_status",
                "params": {"status": "inactive"},
                "request_id": "req_bulk_123"
            }
        }


class FileUploadRequest(BaseRequest):
    """文件上传的基础请求"""
    
    file_name: str = Field(..., description="文件名")
    file_size: int = Field(..., ge=1, description="文件大小（字节）")
    content_type: str = Field(..., description="文件类型")
    description: Optional[str] = Field(None, max_length=500, description="文件描述")
    tags: Optional[list[str]] = Field(None, description="文件标签")
    
    @validator('file_name')
    def validate_file_name(cls, v):
        if not v or not v.strip():
            raise ValueError("File name is required")
        # 简单的文件名验证
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in v for char in invalid_chars):
            raise ValueError("File name contains invalid characters")
        return v.strip()
    
    @validator('content_type')
    def validate_content_type(cls, v):
        if not v or '/' not in v:
            raise ValueError("Invalid content type")
        return v.lower()
    
    class Config(BaseRequest.Config):
        schema_extra = {
            "example": {
                "file_name": "document.pdf",
                "file_size": 1048576,
                "content_type": "application/pdf",
                "description": "Important document",
                "tags": ["document", "important"],
                "request_id": "req_upload_123"
            }
        }