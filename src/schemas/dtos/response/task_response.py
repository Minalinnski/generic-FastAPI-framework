# src/schemas/dtos/response/task_response.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from src.schemas.base_schema import BaseSchema, TimestampMixin
from src.schemas.enums.base_enums import TaskStatusEnum, TaskTypeEnum


class TaskResponse(BaseSchema, TimestampMixin):
    """任务响应DTO"""
    
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    task_type: TaskTypeEnum = Field(..., description="任务类型")
    status: TaskStatusEnum = Field(..., description="任务状态")
    priority: int = Field(default=0, description="任务优先级")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="任务进度(0-100)")
    result: Optional[Any] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")
    error_details: Optional[Dict[str, Any]] = Field(None, description="详细错误信息")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    duration: Optional[float] = Field(None, description="执行时长(秒)")
    timeout: int = Field(default=300, description="任务超时时间")
    retry_count: int = Field(default=0, description="已重试次数")
    max_retries: int = Field(default=0, description="最大重试次数")
    tags: Optional[list[str]] = Field(None, description="任务标签")
    worker_id: Optional[str] = Field(None, description="执行工作者ID")
    queue_position: Optional[int] = Field(None, description="队列位置")
    estimated_completion: Optional[datetime] = Field(None, description="预计完成时间")
    
    class Config(BaseSchema.Config):
        schema_extra = {
            "example": {
                "task_id": "task_123456789",
                "task_name": "file_process_task",
                "task_type": "async",
                "status": "success",
                "priority": 1,
                "progress": 100.0,
                "result": {"processed": True, "output_path": "/results/output.txt"},
                "error": None,
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T10:05:00Z",
                "duration": 300.0,
                "timeout": 300,
                "retry_count": 0,
                "max_retries": 2,
                "tags": ["file_processing"],
                "created_at": "2024-01-01T09:59:00Z"
            }
        }


class TaskSubmitResponse(BaseSchema):
    """任务提交响应DTO"""
    
    task_id: str = Field(..., description="任务ID")
    status: TaskStatusEnum = Field(..., description="提交后状态")
    queue_position: Optional[int] = Field(None, description="队列位置")
    estimated_start_time: Optional[datetime] = Field(None, description="预计开始时间")
    estimated_completion_time: Optional[datetime] = Field(None, description="预计完成时间")
    
    class Config(BaseSchema.Config):
        schema_extra = {
            "example": {
                "task_id": "task_123456789",
                "status": "pending",
                "queue_position": 3,
                "estimated_start_time": "2024-01-01T10:02:00Z",
                "estimated_completion_time": "2024-01-01T10:07:00Z"
            }
        }


class TaskListResponse(BaseSchema):
    """任务列表响应DTO"""
    
    tasks: List[TaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总任务数")
    page: int = Field(..., description="当前页")
    size: int = Field(..., description="页大小")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")
    
    class Config(BaseSchema.Config):
        schema_extra = {
            "example": {
                "tasks": [
                    {
                        "task_id": "task_123",
                        "task_name": "file_process_task",
                        "task_type": "async",
                        "status": "success",
                        "priority": 1
                    }
                ],
                "total": 100,
                "page": 1,
                "size": 50,
                "has_next": True,
                "has_prev": False
            }
        }


class TaskStatisticsResponse(BaseSchema):
    """任务统计响应DTO"""
    
    total_tasks: int = Field(..., description="总任务数")
    running_tasks: int = Field(..., description="运行中任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    failed_tasks: int = Field(..., description="失败任务数")
    pending_tasks: int = Field(..., description="等待中任务数")
    cancelled_tasks: int = Field(..., description="已取消任务数")
    
    # 性能指标
    average_duration: float = Field(..., description="平均执行时长(秒)")
    median_duration: float = Field(..., description="中位执行时长(秒)")
    success_rate: float = Field(..., description="成功率(0-1)")
    failure_rate: float = Field(..., description="失败率(0-1)")
    
    # 资源使用
    worker_utilization: float = Field(..., description="工作者利用率(0-1)")
    queue_size: int = Field(..., description="当前队列大小")
    max_queue_size: int = Field(..., description="最大队列大小")
    
    # 时间统计
    last_24h_completed: int = Field(..., description="24小时内完成任务数")
    last_24h_failed: int = Field(..., description="24小时内失败任务数")
    
    # 按状态分组
    status_distribution: Dict[str, int] = Field(..., description="状态分布")
    
    # 按优先级分组
    priority_distribution: Dict[str, int] = Field(..., description="优先级分布")
    
    class Config(BaseSchema.Config):
        schema_extra = {
            "example": {
                "total_tasks": 1000,
                "running_tasks": 5,
                "completed_tasks": 850,
                "failed_tasks": 45,
                "pending_tasks": 100,
                "cancelled_tasks": 0,
                "average_duration": 120.5,
                "median_duration": 95.0,
                "success_rate": 0.85,
                "failure_rate": 0.045,
                "worker_utilization": 0.8,
                "queue_size": 15,
                "max_queue_size": 1000,
                "last_24h_completed": 200,
                "last_24h_failed": 5,
                "status_distribution": {
                    "success": 850,
                    "failed": 45,
                    "running": 5,
                    "pending": 100
                },
                "priority_distribution": {
                    "low": 200,
                    "normal": 700,
                    "high": 90,
                    "urgent": 10
                }
            }
        }


class TaskTypesResponse(BaseSchema):
    """任务类型响应DTO"""
    
    sync_tasks: List[str] = Field(..., description="同步任务列表")
    async_tasks: List[str] = Field(..., description="异步任务列表")
    total_registered: int = Field(..., description="已注册任务总数")
    task_categories: Dict[str, List[str]] = Field(default_factory=dict, description="任务分类")
    
    class Config(BaseSchema.Config):
        schema_extra = {
            "example": {
                "sync_tasks": ["quick_calculation"],
                "async_tasks": ["file_process_task", "data_analysis_task"],
                "total_registered": 3,
                "task_categories": {
                    "file_processing": ["file_process_task"],
                    "data_analysis": ["data_analysis_task"],
                    "utilities": ["quick_calculation"]
                }
            }
        }


class TaskBulkOperationResponse(BaseSchema):
    """批量任务操作响应DTO"""
    
    operation: str = Field(..., description="操作类型")
    total_requested: int = Field(..., description="请求处理的任务总数")
    successful: int = Field(..., description="成功处理的任务数")
    failed: int = Field(..., description="处理失败的任务数")
    results: List[Dict[str, Any]] = Field(..., description="详细结果")
    
    class Config(BaseSchema.Config):
        schema_extra = {
            "example": {
                "operation": "cancel",
                "total_requested": 5,
                "successful": 4,
                "failed": 1,
                "results": [
                    {"task_id": "task_1", "success": True},
                    {"task_id": "task_2", "success": True},
                    {"task_id": "task_3", "success": False, "error": "Task already completed"}
                ]
            }
        }