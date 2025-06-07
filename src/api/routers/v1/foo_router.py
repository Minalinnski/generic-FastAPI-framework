# src/api/v1/routers/foo_router.py
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.application.handlers.foo_handler import FooHandler
from src.infrastructure.decorators.rate_limit import api_rate_limit, user_rate_limit
from src.infrastructure.decorators.retry import simple_retry
from src.infrastructure.tasks.task_decorator import async_task, sync_task
from src.schemas.dtos.response.base_response import BaseResponse

router = APIRouter(prefix="/foo", tags=["Foo Service Demo"])


# === DTO 定义 ===
class FooDataRequest(BaseModel):
    """Foo数据处理请求"""
    data: Dict[str, Any] = Field(..., description="要处理的数据")
    processing_time: float = Field(default=1.0, ge=0.1, le=30.0, description="处理时间(秒)")
    callback_url: Optional[str] = Field(None, description="回调URL")


class FooBatchRequest(BaseModel):
    """Foo批量处理请求"""
    items: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100, description="批量处理项目")
    processing_time: float = Field(default=2.0, ge=0.1, le=10.0, description="每项处理时间(秒)")


class FooCacheRequest(BaseModel):
    """Foo缓存请求"""
    key: str = Field(..., min_length=1, max_length=50, description="缓存键")


class FooExternalRequest(BaseModel):
    """Foo外部服务请求"""
    endpoint: str = Field(..., description="外部服务端点")
    data: Dict[str, Any] = Field(default_factory=dict, description="发送的数据")


def get_foo_handler() -> FooHandler:
    """依赖注入：获取Foo处理器"""
    return FooHandler()


# === 状态检查接口 ===
@router.get("/status", summary="获取Foo服务状态")
async def get_foo_status(handler: FooHandler = Depends(get_foo_handler)):
    """
    服务状态检查 - 直接执行，不使用Task系统
    
    这个接口用于快速检查服务状态，不需要限流和重试
    """
    try:
        result = await handler.handle_status_check()
        return BaseResponse.success_response(result)
    except Exception as e:
        return BaseResponse.error_response("STATUS_CHECK_ERROR", str(e))


# === 同步处理接口 ===
@router.post("/sync", summary="同步数据处理")
@api_rate_limit(requests_per_minute=60)  # 3. API层限流
@simple_retry(attempts=2, delay=0.5)     # 2. 网络层重试
@sync_task(timeout=30)                   # 1. 任务包装（同步执行）
async def sync_data_process(
    request: FooDataRequest,
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    同步处理 - 演示装饰器协作
    
    装饰器执行顺序：
    1. sync_task: 任务包装但同步执行
    2. simple_retry: 失败时重试
    3. api_rate_limit: 请求频率限制
    
    适用场景：快速处理，需要立即返回结果
    """
    return handler.handle_sync_processing(
        data=request.data,
        processing_time=request.processing_time
    )


# === 异步处理接口 ===
@router.post("/async", summary="异步数据处理")
@user_rate_limit(requests_per_minute=30)     # 3. 用户级限流
@simple_retry(attempts=3, delay=1.0)         # 2. 重试机制
@async_task(priority=1, timeout=300, max_retries=2)  # 1. 异步任务
async def async_data_process(
    request: FooDataRequest,
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    异步处理 - 提交到Task队列
    
    装饰器执行顺序：
    1. async_task: 提交到任务队列
    2. simple_retry: 提交失败时重试
    3. user_rate_limit: 用户级限流
    
    适用场景：耗时处理，立即返回task_id
    """
    return await handler.handle_async_processing(
        data=request.data,
        processing_time=request.processing_time,
        callback_url=request.callback_url
    )


# === 批量处理接口 ===
@router.post("/batch", summary="批量数据处理")
@api_rate_limit(requests_per_minute=10)      # 3. 严格限流（批量操作）
@simple_retry(attempts=2, delay=2.0)         # 2. 重试间隔更长
@async_task(priority=2, timeout=600, max_retries=1)  # 1. 高优先级异步任务
async def batch_data_process(
    request: FooBatchRequest,
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    批量处理 - 高优先级异步任务
    
    装饰器配置说明：
    1. 高优先级（priority=2）：批量任务优先执行
    2. 严格限流（10/分钟）：防止系统过载
    3. 更长超时（600秒）：批量任务需要更多时间
    
    适用场景：大批量数据处理
    """
    return await handler.handle_batch_processing(
        items=request.items,
        processing_time=request.processing_time
    )


# === 缓存测试接口 ===
@router.get("/cache/{key}", summary="获取缓存数据")
@api_rate_limit(requests_per_minute=120)  # 缓存接口可以更高频率
async def get_cached_data(
    key: str,
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    缓存数据获取 - 测试缓存装饰器
    
    这个接口在Service层使用了@api_cache装饰器
    第一次调用会生成数据，后续调用返回缓存
    """
    try:
        service = handler.foo_service
        result = await service.get_cached_data(key)
        return BaseResponse.success_response(result)
    except Exception as e:
        return BaseResponse.error_response("CACHE_ERROR", str(e))


# === 外部服务调用接口 ===
@router.post("/external", summary="调用外部服务")
@api_rate_limit(requests_per_minute=20)      # 3. 限制外部调用频率
@simple_retry(attempts=3, delay=1.0)         # 2. 外部调用重试
@sync_task(timeout=60)                       # 1. 同步任务（需要立即响应）
async def call_external_service(
    request: FooExternalRequest,
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    外部服务调用 - 演示网络重试
    
    Service层使用了@network_retry装饰器
    模拟外部服务调用失败和重试机制
    """
    service = handler.foo_service
    result = await service.call_external_service(
        endpoint=request.endpoint,
        data=request.data
    )
    return BaseResponse.success_response(result)


# === 管理接口 ===
@router.post("/reset", summary="重置服务计数器")
@api_rate_limit(requests_per_minute=5)  # 管理接口严格限流
async def reset_service_counters(
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    重置服务计数器 - 管理接口
    
    用于测试和调试，重置服务内部计数器
    """
    try:
        service = handler.foo_service
        result = service.reset_counters()
        return BaseResponse.success_response(result)
    except Exception as e:
        return BaseResponse.error_response("RESET_ERROR", str(e))


# === 健康检查接口 ===
@router.get("/health", summary="Foo服务健康检查")
async def foo_health_check(
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    Foo服务专用健康检查
    
    不使用装饰器，直接调用服务层健康检查
    """
    try:
        service = handler.foo_service
        result = await service.health_check()
        return BaseResponse.success_response(result)
    except Exception as e:
        return BaseResponse.error_response("HEALTH_CHECK_ERROR", str(e))


# === 测试接口（开发用） ===
@router.post("/test/decorators", summary="测试装饰器组合")
@api_rate_limit(requests_per_minute=5)       # 4. 最外层：API限流
@simple_retry(attempts=2, delay=1.0)         # 3. 重试机制
@async_task(priority=0, timeout=120, max_retries=1)  # 2. 任务包装
async def test_decorators(
    fail_rate: float = Query(default=0.2, ge=0.0, le=1.0, description="失败率"),
    processing_time: float = Query(default=2.0, ge=0.1, le=10.0, description="处理时间"),
    handler: FooHandler = Depends(get_foo_handler)
):
    """
    测试装饰器组合 - 开发和调试用
    
    可以调整失败率和处理时间来测试：
    1. 重试机制是否正常工作
    2. 限流是否有效
    3. 任务系统是否稳定
    4. 异常处理是否正确
    """
    import random
    
    # 模拟随机失败
    if random.random() < fail_rate:
        raise Exception(f"模拟失败（失败率: {fail_rate}）")
    
    # 调用实际的业务逻辑
    test_data = {
        "test": True,
        "fail_rate": fail_rate,
        "processing_time": processing_time,
        "random_value": random.randint(1000, 9999)
    }
    
    return await handler.handle_async_processing(
        data=test_data,
        processing_time=processing_time
    )