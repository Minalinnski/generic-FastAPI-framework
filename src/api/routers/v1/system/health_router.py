# src/api/v1/routers/health_router.py
from fastapi import APIRouter, Depends

from src.application.handlers.system.health_handler import HealthHandler
from src.schemas.dtos.response.base_response import BaseResponse
from src.schemas.dtos.response.health_response import HealthData

router = APIRouter(prefix="/health", tags=["Health"])


def get_health_handler() -> HealthHandler:
    """获取健康检查处理器"""
    return HealthHandler()


@router.get("/", response_model=BaseResponse[HealthData], summary="异步健康检查")
async def health_check(handler: HealthHandler = Depends(get_health_handler)):
    """
    异步健康检查接口
    
    检查服务及其依赖的健康状态：
    - 服务运行状态
    - 缓存连接状态
    - 数据库连接状态（如果配置）
    - S3连接状态（如果配置）
    """
    return await handler.handle_request()


@router.get("/sync", response_model=BaseResponse[HealthData], summary="同步健康检查")
def health_check_sync(handler: HealthHandler = Depends(get_health_handler)):
    """
    同步健康检查接口
    
    快速检查服务基本运行状态，不检查外部依赖
    """
    return handler.handle_sync_request()


@router.get("/ping", summary="简单ping检查")
def ping():
    """
    简单的ping检查，用于负载均衡器健康检查
    """
    return {"status": "ok", "message": "pong"}