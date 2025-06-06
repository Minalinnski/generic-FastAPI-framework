# src/api/v1/routers/foo_router.py (支持回调的更新版)
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from src.application.handlers.foo_handler import FooHandler
from src.infrastructure.decorators.rate_limit import api_rate_limit
from src.infrastructure.decorators.retry import simple_retry
from src.infrastructure.tasks.task_decorator import async_task, sync_task
from src.schemas.dtos.response.base_response import BaseResponse

router = APIRouter(prefix="/foo", tags=["Foo Service"])


class FooDataRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="要处理的数据")
    callback_url: Optional[str] = Field(None, description="回调URL")


class ExternalApiRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="要处理的数据")
    external_callback_url: str = Field(..., description="外部API回调URL")


class CallbackRequest(BaseModel):
    process_id: str = Field(..., description="处理ID")
    external_result: Dict[str, Any] = Field(..., description="外部API结果")


def get_foo_handler() -> FooHandler:
    return FooHandler()


@router.get("/status", summary="获取Foo服务状态")
async def get_foo_status(handler: FooHandler = Depends(get_foo_handler)):
    """服务状态检查 - 直接执行，不使用Task"""
    info = handler.foo_service.get_service_info()
    callback_stats = handler.foo_service.get_callback_statistics()
    
    return BaseResponse.success_response({
        "service_info": info,
        "callback_system": callback_stats
    })


@router.post("/sync", summary="同步数据处理")
@api_rate_limit(requests_per_minute=60)
@simple_retry(attempts=2)
@sync_task(timeout=30)
async def sync_data_process(
    request: FooDataRequest,
    handler: FooHandler = Depends(get_foo_handler)
):
    """同步处理 - 装饰器控制rate limit和retry，Task系统控制并发"""
    return handler.handle_sync_processing(request.data)


@router.post("/async", summary="异步数据处理")
@api_rate_limit(requests_per_minute=30)
@simple_retry(attempts=3)
@async_task(priority=1, timeout=300, max_retries=2)
async def async_data_process(
    request: FooDataRequest,
    handler: FooHandler = Depends(get_foo_handler)
):
    """异步处理 - 提交到Task队列，返回task_id"""
    return await handler.handle_async_processing(
        request.data, 
        callback_url=request.callback_url
    )


@router.post("/external-api", summary="调用外部异步API")
@api_rate_limit(requests_per_minute=20)
@async_task(priority=2, timeout=600)
async def process_with_external_api(
    request: ExternalApiRequest,
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    调用外部异步API处理
    
    演示场景：
    1. 本地预处理
    2. 调用外部异步API
    3. 注册回调等待结果
    """
    result = await handler.foo_service.process_with_external_api(
        request.data,
        request.external_callback_url
    )
    return BaseResponse.success_response(result)


@router.post("/callback/external", summary="外部API回调接收")
async def receive_external_callback(
    request: CallbackRequest,
    background_tasks: BackgroundTasks,
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    接收外部API的回调
    
    这个端点会被外部服务调用，用于通知异步操作的完成
    """
    # 使用后台任务处理回调，避免阻塞响应
    background_tasks.add_task(
        handler.foo_service.handle_external_callback,
        request.process_id,
        request.external_result
    )
    
    return BaseResponse.success_response({
        "message": "回调已接收",
        "process_id": request.process_id,
        "status": "processing"
    })


@router.post("/callbacks/enable", summary="启用回调系统")
async def enable_callbacks(handler: FooHandler = Depends(get_foo_handler)):
    """启用服务的回调系统"""
    await handler.foo_service.enable_callback_system()
    return BaseResponse.success_response({"message": "回调系统已启用"})


@router.post("/callbacks/disable", summary="禁用回调系统")
async def disable_callbacks(handler: FooHandler = Depends(get_foo_handler)):
    """禁用服务的回调系统"""
    await handler.foo_service.disable_callback_system()
    return BaseResponse.success_response({"message": "回调系统已禁用"})


@router.get("/callbacks/stats", summary="获取回调统计")
async def get_callback_stats(handler: FooHandler = Depends(get_foo_handler)):
    """获取回调系统统计信息"""
    stats = handler.foo_service.get_callback_statistics()
    return BaseResponse.success_response(stats)