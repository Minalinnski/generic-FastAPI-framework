# app/api/v1/routers/foo_router.py
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.application.handlers.task_handler import TaskHandler
from app.application.services.foo_service import FooService
from app.infrastructure.decorators.rate_limit import api_rate_limit, user_rate_limit
from app.schemas.dtos.request.task_request import TaskCreateRequest
from app.schemas.dtos.response.base_response import BaseResponse
from app.schemas.enums.base_enums import TaskTypeEnum

router = APIRouter(prefix="/foo", tags=["Test"])


# 请求响应模型
class FooDataRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="要处理的数据")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="处理选项")


class FooFileRequest(BaseModel):
    file_path: str = Field(..., description="文件路径")
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    format: Optional[str] = Field(default="processed", description="处理格式")


class FooAnalysisRequest(BaseModel):
    dataset: List[Dict[str, Any]] = Field(..., description="数据集")


class FooApiRequest(BaseModel):
    api_endpoint: str = Field(..., description="API端点")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="API参数")


class FooCalculationRequest(BaseModel):
    numbers: List[float] = Field(..., description="数字列表")


def get_foo_service() -> FooService:
    """获取Foo服务"""
    return FooService()


def get_task_handler() -> TaskHandler:
    """获取任务处理器"""
    return TaskHandler()


@router.get("/status", summary="获取Foo服务状态")
async def get_foo_status(service: FooService = Depends(get_foo_service)):
    """获取Foo服务状态"""
    status = await service.get_service_status()
    return BaseResponse.success_response(status)


@router.post("/tasks/data-processing", summary="提交数据处理任务")
@api_rate_limit(requests_per_minute=50)
async def submit_data_processing_task(
    request: FooDataRequest,
    priority: int = Query(default=0, ge=-10, le=10, description="任务优先级"),
    timeout: int = Query(default=60, gt=0, le=300, description="超时时间(秒)"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """提交数据处理任务到队列"""
    try:
        task_request = TaskCreateRequest(
            task_name="sample_data_processing",
            task_type=TaskTypeEnum.ASYNC,
            params={
                "data": request.data,
                **request.options
            },
            priority=priority,
            timeout=timeout,
            max_retries=2
        )
        
        result = await handler.submit_task(task_request)
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_SUBMIT_ERROR", str(e))


@router.post("/tasks/file-processing", summary="提交文件处理任务")
@api_rate_limit(requests_per_minute=30)
async def submit_file_processing_task(
    request: FooFileRequest,
    priority: int = Query(default=0, ge=-10, le=10, description="任务优先级"),
    timeout: int = Query(default=120, gt=0, le=600, description="超时时间(秒)"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """提交文件处理任务到队列"""
    try:
        task_request = TaskCreateRequest(
            task_name="file_processing_simulation",
            task_type=TaskTypeEnum.ASYNC,
            params={
                "file_path": request.file_path,
                "options": {
                    "file_size": request.file_size,
                    "format": request.format
                }
            },
            priority=priority,
            timeout=timeout,
            max_retries=1
        )
        
        result = await handler.submit_task(task_request)
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_SUBMIT_ERROR", str(e))


@router.post("/tasks/data-analysis", summary="提交数据分析任务")
@user_rate_limit(requests_per_minute=20)
async def submit_data_analysis_task(
    request: FooAnalysisRequest,
    priority: int = Query(default=1, ge=-10, le=10, description="任务优先级"),
    timeout: int = Query(default=180, gt=0, le=600, description="超时时间(秒)"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """提交数据分析任务到队列"""
    try:
        task_request = TaskCreateRequest(
            task_name="data_analysis_task",
            task_type=TaskTypeEnum.ASYNC,
            params={
                "dataset": request.dataset
            },
            priority=priority,
            timeout=timeout,
            max_retries=1
        )
        
        result = await handler.submit_task(task_request)
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_SUBMIT_ERROR", str(e))


@router.post("/tasks/external-api", summary="提交外部API调用任务")
@api_rate_limit(requests_per_minute=40)
async def submit_external_api_task(
    request: FooApiRequest,
    priority: int = Query(default=0, ge=-10, le=10, description="任务优先级"),
    timeout: int = Query(default=30, gt=0, le=120, description="超时时间(秒)"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """提交外部API调用任务到队列"""
    try:
        task_request = TaskCreateRequest(
            task_name="external_api_simulation",
            task_type=TaskTypeEnum.ASYNC,
            params={
                "api_endpoint": request.api_endpoint,
                "params": request.params
            },
            priority=priority,
            timeout=timeout,
            max_retries=3  # 外部API多重试几次
        )
        
        result = await handler.submit_task(task_request)
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_SUBMIT_ERROR", str(e))


@router.post("/tasks/sync-calculation", summary="提交同步计算任务")
@api_rate_limit(requests_per_minute=60)
async def submit_sync_calculation_task(
    request: FooCalculationRequest,
    priority: int = Query(default=-1, ge=-10, le=10, description="任务优先级"),
    timeout: int = Query(default=30, gt=0, le=120, description="超时时间(秒)"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """提交同步计算任务到队列"""
    try:
        task_request = TaskCreateRequest(
            task_name="sync_calculation_task",
            task_type=TaskTypeEnum.SYNC,
            params={
                "numbers": request.numbers
            },
            priority=priority,
            timeout=timeout,
            max_retries=0  # 同步计算一般不需要重试
        )
        
        result = await handler.submit_task(task_request)
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_SUBMIT_ERROR", str(e))


@router.post("/direct/batch-process", summary="直接批量处理（不通过任务队列）")
@api_rate_limit(requests_per_minute=20)
async def direct_batch_process(
    items: List[Dict[str, Any]],
    service: FooService = Depends(get_foo_service)
):
    """直接调用服务进行批量处理，不通过任务队列"""
    try:
        result = await service.batch_process_items(items)
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("PROCESSING_ERROR", str(e))


@router.get("/config/{config_type}", summary="获取缓存配置")
async def get_cached_config(
    config_type: str,
    service: FooService = Depends(get_foo_service)
):
    """获取缓存的配置信息（演示缓存功能）"""
    try:
        config = await service.get_cached_config(config_type)
        return BaseResponse.success_response(config)
        
    except Exception as e:
        return BaseResponse.error_response("CONFIG_ERROR", str(e))