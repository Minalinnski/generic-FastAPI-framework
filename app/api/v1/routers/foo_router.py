# app/api/v1/routers/foo_router.py (最终版)
from typing import Any, Dict
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.application.handlers.foo_handler import FooHandler
from app.infrastructure.decorators.rate_limit import api_rate_limit
from app.infrastructure.decorators.retry import simple_retry
from app.infrastructure.tasks.task_decorator import async_task, sync_task
from app.schemas.dtos.response.base_response import BaseResponse

router = APIRouter(prefix="/foo", tags=["Foo Service"])


class FooDataRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="要处理的数据")


def get_foo_handler() -> FooHandler:
    return FooHandler()


@router.get("/status", summary="获取Foo服务状态")
async def get_foo_status(handler: FooHandler = Depends(get_foo_handler)):
    """服务状态检查 - 直接执行，不使用Task"""
    info = handler.foo_service.get_service_info()
    return BaseResponse.success_response(info)


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
    return await handler.handle_async_processing(request.data)