# app/api/v1/routers/task_router.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.application.handlers.task_handler import TaskHandler
from app.infrastructure.decorators.rate_limit import api_rate_limit
from app.schemas.dtos.request.task_request import TaskCreateRequest
from app.schemas.dtos.response.base_response import BaseResponse
from app.schemas.dtos.response.task_response import (
    TaskResponse, TaskListResponse, TaskStatisticsResponse, 
    TaskTypesResponse, TaskSubmitResponse
)
from app.schemas.enums.base_enums import TaskStatusEnum

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_task_handler() -> TaskHandler:
    """获取任务处理器"""
    return TaskHandler()


@router.post("/submit", response_model=BaseResponse[TaskSubmitResponse], summary="提交任务")
@api_rate_limit(requests_per_minute=30)
async def submit_task(
    request: TaskCreateRequest,
    handler: TaskHandler = Depends(get_task_handler)
):
    """
    提交任务到任务队列
    
    任务将根据优先级和提交时间进行调度执行
    支持超时控制和重试机制
    
    支持的任务类型：
    - sample_task: 示例任务
    - file_process_task: 文件处理任务
    """
    try:
        result = await handler.submit_task(request)
        return BaseResponse.success_response(result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return BaseResponse.error_response("TASK_SUBMIT_ERROR", str(e))


@router.get("/{task_id}/status", response_model=BaseResponse[TaskResponse], summary="获取任务状态")
async def get_task_status(
    task_id: str,
    handler: TaskHandler = Depends(get_task_handler)
):
    """获取指定任务的执行状态和结果"""
    try:
        result = await handler.get_task_status(task_id)
        return BaseResponse.success_response(result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return BaseResponse.error_response("TASK_STATUS_ERROR", str(e))


@router.get("/", response_model=BaseResponse[TaskListResponse], summary="获取任务列表")
async def get_all_tasks(
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """获取所有任务的状态列表（支持分页）"""
    try:
        result = await handler.get_task_list(limit, offset)
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_LIST_ERROR", str(e))


@router.get("/registry", response_model=BaseResponse[TaskTypesResponse], summary="获取已注册的任务类型")
async def get_registered_tasks(handler: TaskHandler = Depends(get_task_handler)):
    """获取系统中已注册的所有任务类型"""
    try:
        result = await handler.get_registered_tasks()
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_REGISTRY_ERROR", str(e))


@router.delete("/{task_id}", summary="取消任务")
async def cancel_task(
    task_id: str,
    handler: TaskHandler = Depends(get_task_handler)
):
    """取消指定的任务（如果任务还未开始执行）"""
    try:
        result = await handler.cancel_task(task_id)
        return BaseResponse.success_response(result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return BaseResponse.error_response("TASK_CANCEL_ERROR", str(e))


@router.get("/statistics", response_model=BaseResponse[TaskStatisticsResponse], summary="获取任务统计信息")
async def get_task_statistics(handler: TaskHandler = Depends(get_task_handler)):
    """获取任务系统的统计信息和性能指标"""
    try:
        result = await handler.get_task_statistics()
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_STATS_ERROR", str(e))


@router.post("/cleanup", summary="清理已完成的任务历史")
async def cleanup_completed_tasks(
    max_history: int = Query(1000, ge=100, le=10000, description="保留的历史任务数量"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """清理已完成的任务历史记录"""
    try:
        result = await handler.cleanup_completed_tasks(max_history)
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_CLEANUP_ERROR", str(e))


@router.get("/history", response_model=BaseResponse[TaskListResponse], summary="获取任务历史")
async def get_task_history(
    task_name: Optional[str] = Query(None, description="按任务名称过滤"),
    status: Optional[TaskStatusEnum] = Query(None, description="按状态过滤"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    handler: TaskHandler = Depends(get_task_handler)
):
    """
    获取任务执行历史
    
    支持按任务名称和状态过滤
    """
    try:
        # 这里调用TaskService的get_task_history方法
        history_tasks = await handler.task_service.get_task_history(
            task_name=task_name,
            status=status,
            limit=limit
        )
        
        # 转换为TaskResponse格式
        task_responses = [
            handler._convert_to_task_response(task_data)
            for task_data in history_tasks
        ]
        
        result = TaskListResponse(
            tasks=task_responses,
            total=len(task_responses),
            page=1,
            size=len(task_responses)
        )
        
        return BaseResponse.success_response(result)
        
    except Exception as e:
        return BaseResponse.error_response("TASK_HISTORY_ERROR", str(e))