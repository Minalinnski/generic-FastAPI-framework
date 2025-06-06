# src/api/v1/routers/system/task_router.py (增强版)
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.handlers.system.task_handler import TaskHandler
from src.infrastructure.decorators.rate_limit import api_rate_limit
from src.schemas.dtos.response.base_response import BaseResponse

router = APIRouter(prefix="/tasks", tags=["Task Management"])


def get_task_handler() -> TaskHandler:
    return TaskHandler()


@router.get("/registry", summary="获取任务注册表信息")
async def get_task_registry(handler: TaskHandler = Depends(get_task_handler)):
    """获取任务注册表的完整信息"""
    try:
        result = await handler.task_service.get_task_registry_info()
        return BaseResponse.success_response(result)
    except Exception as e:
        return BaseResponse.error_response("REGISTRY_ERROR", str(e))


@router.get("/search", summary="搜索任务类型")
async def search_task_types(
    q: str = Query(..., description="搜索关键词"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """搜索已注册的任务类型"""
    try:
        results = await handler.task_service.search_task_types(q)
        return BaseResponse.success_response(results)
    except Exception as e:
        return BaseResponse.error_response("SEARCH_ERROR", str(e))


@router.get("/{task_id}/result", summary="获取任务结果")
async def get_task_result(
    task_id: str,
    handler: TaskHandler = Depends(get_task_handler)
):
    """获取任务结果（从缓存或S3）"""
    try:
        result = await handler.task_service.get_task_result(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="任务结果不存在")
        return BaseResponse.success_response(result)
    except HTTPException:
        raise
    except Exception as e:
        return BaseResponse.error_response("RESULT_ERROR", str(e))


@router.delete("/{task_id}/result", summary="删除任务结果")
async def delete_task_result(
    task_id: str,
    delete_from_s3: bool = Query(default=False, description="是否同时从S3删除"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """删除任务结果"""
    try:
        result = await handler.task_service.delete_task_result(task_id, delete_from_s3)
        return BaseResponse.success_response(result)
    except Exception as e:
        return BaseResponse.error_response("DELETE_ERROR", str(e))


@router.post("/{task_id}/kill", summary="强制终止任务")
@api_rate_limit(requests_per_minute=10)
async def force_kill_task(
    task_id: str,
    reason: str = Query(default="手动终止", description="终止原因"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """强制终止正在运行的任务"""
    try:
        result = await handler.task_service.force_kill_task(task_id, reason)
        return BaseResponse.success_response(result)
    except Exception as e:
        return BaseResponse.error_response("KILL_ERROR", str(e))


@router.get("/storage/stats", summary="获取存储统计")
async def get_storage_stats(handler: TaskHandler = Depends(get_task_handler)):
    """获取任务结果存储统计信息"""
    try:
        stats = await handler.task_service.get_storage_statistics()
        return BaseResponse.success_response(stats)
    except Exception as e:
        return BaseResponse.error_response("STORAGE_STATS_ERROR", str(e))


@router.post("/cleanup", summary="清理系统")
@api_rate_limit(requests_per_minute=5)
async def cleanup_system(
    max_age_hours: int = Query(default=24, ge=1, le=168, description="清理多少小时前的数据"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """清理旧的任务数据和结果"""
    try:
        result = await handler.task_service.cleanup_system(max_age_hours)
        return BaseResponse.success_response(result)
    except Exception as e:
        return BaseResponse.error_response("CLEANUP_ERROR", str(e))