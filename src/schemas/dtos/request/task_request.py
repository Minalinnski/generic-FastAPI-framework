# src/schemas/dtos/request/task_request.py
from typing import Any, Dict, Optional

from pydantic import Field, validator

from src.schemas.dtos.request.base_request import BaseRequest
from src.schemas.enums.base_enums import TaskTypeEnum


class TaskCreateRequest(BaseRequest):
    """创建任务请求DTO"""
    
    task_name: str = Field(..., description="任务名称", min_length=1, max_length=100)
    task_type: TaskTypeEnum = Field(default=TaskTypeEnum.ASYNC, description="任务类型")
    params: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    priority: int = Field(default=0, ge=-10, le=10, description="任务优先级(-10到10，数值越大优先级越高)")
    timeout: int = Field(default=300, gt=0, le=3600, description="任务超时时间(秒)")
    max_retries: int = Field(default=0, ge=0, le=5, description="最大重试次数")
    tags: Optional[list[str]] = Field(default=None, description="任务标签")
    
    @validator('task_name')
    def validate_task_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("任务名称不能为空")
        # 检查任务名称格式（字母、数字、下划线）
        import re
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', v.strip()):
            raise ValueError("任务名称只能包含字母、数字和下划线，且必须以字母开头")
        return v.strip()
    
    @validator('params')
    def validate_params(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        # 确保参数可序列化
        import json
        try:
            json.dumps(v, default=str)
        except (TypeError, ValueError) as e:
            raise ValueError(f"任务参数必须可JSON序列化: {str(e)}")
        return v
    
    class Config(BaseRequest.Config):
        schema_extra = {
            "example": {
                "task_name": "file_process_task",
                "task_type": "async",
                "params": {
                    "file_path": "/uploads/document.pdf",
                    "options": {"format": "text"}
                },
                "priority": 1,
                "timeout": 300,
                "max_retries": 2,
                "tags": ["file_processing", "pdf"],
                "request_id": "req_task_123"
            }
        }


class TaskQueryRequest(BaseRequest):
    """任务查询请求DTO"""
    
    task_id: str = Field(..., description="任务ID")
    include_result: bool = Field(default=True, description="是否包含任务结果")
    include_logs: bool = Field(default=False, description="是否包含任务日志")
    include_metadata: bool = Field(default=True, description="是否包含元数据")
    
    @validator('task_id')
    def validate_task_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("任务ID不能为空")
        return v.strip()


class TaskCancelRequest(BaseRequest):
    """取消任务请求DTO"""
    
    task_id: str = Field(..., description="任务ID")
    force: bool = Field(default=False, description="是否强制取消")
    reason: str = Field(default="", max_length=500, description="取消原因")
    
    @validator('task_id')
    def validate_task_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("任务ID不能为空")
        return v.strip()


class TaskListRequest(BaseRequest):
    """任务列表请求DTO"""
    
    status_filter: Optional[str] = Field(default=None, description="状态过滤")
    task_name_filter: Optional[str] = Field(default=None, description="任务名称过滤")
    priority_min: Optional[int] = Field(default=None, ge=-10, le=10, description="最小优先级")
    priority_max: Optional[int] = Field(default=None, ge=-10, le=10, description="最大优先级")
    tags_filter: Optional[list[str]] = Field(default=None, description="标签过滤")
    limit: int = Field(default=50, ge=1, le=200, description="返回数量限制")
    offset: int = Field(default=0, ge=0, description="偏移量")
    sort_by: str = Field(default="created_at", description="排序字段")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="排序方向")


class TaskBulkOperationRequest(BaseRequest):
    """批量任务操作请求DTO"""
    
    task_ids: list[str] = Field(..., min_items=1, max_items=100, description="任务ID列表")
    operation: str = Field(..., description="操作类型: cancel, retry, delete")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="操作参数")
    
    @validator('task_ids')
    def validate_task_ids(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("任务ID列表不能为空")
        # 去重并验证
        unique_ids = list(set(v))
        for task_id in unique_ids:
            if not task_id or not task_id.strip():
                raise ValueError("任务ID不能为空")
        return unique_ids
    
    @validator('operation')
    def validate_operation(cls, v: str) -> str:
        valid_operations = ['cancel', 'retry', 'delete', 'pause', 'resume']
        if v not in valid_operations:
            raise ValueError(f"无效的操作类型: {v}，支持的操作: {valid_operations}")
        return v