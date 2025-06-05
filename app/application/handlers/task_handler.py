# app/application/handlers/task_handler.py - 修复后的任务处理器
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.application.handlers.base_handler import BaseHandler
from app.application.services.task_service import TaskService
from app.infrastructure.tasks.task_manager import task_manager
from app.infrastructure.tasks.task_registry import task_registry
from app.schemas.dtos.request.task_request import TaskCreateRequest
from app.schemas.dtos.response.task_response import (
    TaskResponse, TaskListResponse, TaskStatisticsResponse, 
    TaskTypesResponse, TaskSubmitResponse
)
from app.schemas.enums.base_enums import TaskStatusEnum
from app.infrastructure.utils.datetime_utils import parse_datetime


class TaskHandler(BaseHandler[Dict[str, Any]]):
    """任务管理处理器"""
    
    def __init__(self):
        super().__init__()
        self.task_service = TaskService()
        self.task_manager = task_manager
        self.task_registry = task_registry
    
    async def submit_task(self, request: TaskCreateRequest) -> TaskSubmitResponse:
        """提交任务"""
        try:
            self.logger.info(f"提交任务: {request.task_name}", extra={
                "task_type": request.task_type,
                "priority": request.priority
            })
            
            # 验证任务参数
            validated_params = self.task_registry.validate_task_params(
                request.task_name, request.params
            )
            
            # 从注册表创建任务
            task = self.task_registry.create_task(
                request.task_name,
                task_options={
                    "priority": self._convert_priority(request.priority),
                    "timeout": request.timeout,
                    "max_retries": request.max_retries,
                    "tags": request.tags
                }
            )
            
            if not task:
                raise ValueError(f"未注册的任务类型: {request.task_name}")
            
            # 提交任务到管理器
            task_id = await self.task_manager.submit_task(task, **validated_params)
            
            return TaskSubmitResponse(
                task_id=task_id,
                status=TaskStatusEnum.PENDING,
                queue_position=self._get_queue_position(task_id),
                estimated_start_time=self._estimate_start_time(),
                estimated_completion_time=self._estimate_completion_time(request.timeout)
            )
            
        except Exception as e:
            self.logger.error(f"提交任务失败: {str(e)}")
            raise
    
    def _convert_priority(self, priority_int: int):
        """转换优先级整数为枚举"""
        from app.infrastructure.tasks.base_task import TaskPriority
        return TaskPriority.from_int(priority_int)
    
    def _get_queue_position(self, task_id: str) -> Optional[int]:
        """获取队列位置（简化实现）"""
        queue_info = self.task_manager.get_queue_info()
        return queue_info.get("queue_size", 0) + 1
    
    def _estimate_start_time(self) -> Optional[datetime]:
        """估算开始时间（简化实现）"""
        return None  # 可以根据队列情况计算
    
    def _estimate_completion_time(self, timeout: int) -> Optional[datetime]:
        """估算完成时间（简化实现）"""
        return None  # 可以根据开始时间+超时计算
    
    async def get_task_status(self, task_id: str) -> TaskResponse:
        """获取任务状态"""
        try:
            # 先从任务管理器获取
            status_info = self.task_manager.get_task_status(task_id)
            
            if not status_info:
                # 尝试从缓存获取历史任务
                cached_result = self.task_service.result_cache.get(task_id)
                if cached_result:
                    status_info = cached_result
                else:
                    raise ValueError("任务不存在")
            
            return self._convert_to_task_response(status_info)
            
        except Exception as e:
            self.logger.error(f"获取任务状态失败: {str(e)}")
            raise
    
    async def get_task_list(self, limit: int = 50, offset: int = 0) -> TaskListResponse:
        """获取任务列表"""
        try:
            # 获取活跃任务
            active_tasks = self.task_manager.get_all_tasks()
            
            # 获取历史任务
            historical_tasks = await self.task_service.get_task_history(limit=limit*2)
            
            # 合并并去重
            all_tasks_dict = {}
            
            # 活跃任务优先
            for task_data in active_tasks:
                all_tasks_dict[task_data["task_id"]] = task_data
            
            # 添加历史任务（不覆盖活跃任务）
            for task_data in historical_tasks:
                task_id = task_data.get("task_id")
                if task_id and task_id not in all_tasks_dict:
                    all_tasks_dict[task_id] = task_data
            
            # 转换为列表并分页
            all_tasks = list(all_tasks_dict.values())
            total = len(all_tasks)
            
            # 按时间排序（最新的在前）
            all_tasks.sort(
                key=lambda x: x.get("created_at") or x.get("start_time") or "", 
                reverse=True
            )
            
            paginated_tasks = all_tasks[offset:offset + limit]
            
            # 转换为TaskResponse格式
            task_responses = [
                self._convert_to_task_response(task_data)
                for task_data in paginated_tasks
            ]
            
            return TaskListResponse(
                tasks=task_responses,
                total=total,
                page=(offset // limit) + 1 if limit > 0 else 1,
                size=len(task_responses),
                has_next=offset + limit < total,
                has_prev=offset > 0
            )
            
        except Exception as e:
            self.logger.error(f"获取任务列表失败: {str(e)}")
            raise
    
    async def get_registered_tasks(self) -> TaskTypesResponse:
        """获取已注册的任务类型"""
        try:
            registered_tasks = self.task_registry.get_registered_tasks()
            registry_stats = self.task_registry.get_registry_stats()
            categories = self.task_registry.get_all_categories()
            
            sync_tasks = []
            async_tasks = []
            
            for name, task_type in registered_tasks.items():
                task_info = self.task_registry.get_task_info(name)
                if task_info:
                    if task_info.get("is_async", True):
                        async_tasks.append(name)
                    else:
                        sync_tasks.append(name)
                else:
                    # 默认异步
                    async_tasks.append(name)
            
            return TaskTypesResponse(
                sync_tasks=sync_tasks,
                async_tasks=async_tasks,
                total_registered=len(registered_tasks),
                task_categories=categories
            )
            
        except Exception as e:
            self.logger.error(f"获取任务类型失败: {str(e)}")
            raise
    
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """取消任务"""
        try:
            success = self.task_manager.cancel_task(task_id, "用户取消")
            
            if not success:
                raise ValueError("任务不存在或无法取消")
            
            return {"cancelled": True, "task_id": task_id, "reason": "用户取消"}
            
        except Exception as e:
            self.logger.error(f"取消任务失败: {str(e)}")
            raise
    
    async def get_task_statistics(self) -> TaskStatisticsResponse:
        """获取任务统计信息"""
        try:
            stats = await self.task_service.get_task_statistics()
            runtime_stats = stats["runtime"]
            performance_stats = stats["performance"]
            
            return TaskStatisticsResponse(
                total_tasks=runtime_stats["total_tasks"],
                running_tasks=runtime_stats["running_tasks"],
                completed_tasks=runtime_stats["completed_tasks"],
                failed_tasks=runtime_stats["failed_tasks"],
                pending_tasks=runtime_stats["pending_tasks"],
                cancelled_tasks=runtime_stats.get("cancelled_tasks", 0),
                average_duration=performance_stats.get("avg_execution_time", 0.0),
                median_duration=performance_stats.get("median_execution_time", 0.0),
                success_rate=runtime_stats.get("success_rate", 0.0),
                failure_rate=1.0 - runtime_stats.get("success_rate", 0.0),
                worker_utilization=runtime_stats.get("worker_utilization", 0.0),
                queue_size=runtime_stats.get("queue_size", 0),
                max_queue_size=1000,  # 从配置获取
                last_24h_completed=0,  # TODO: 实现24小时统计
                last_24h_failed=0,
                status_distribution=self._extract_status_distribution(runtime_stats),
                priority_distribution=self._extract_priority_distribution(runtime_stats)
            )
            
        except Exception as e:
            self.logger.error(f"获取任务统计失败: {str(e)}")
            raise
    
    def _extract_status_distribution(self, stats: Dict[str, Any]) -> Dict[str, int]:
        """提取状态分布"""
        return {
            "pending": stats.get("pending_tasks", 0),
            "running": stats.get("running_tasks", 0),
            "completed": stats.get("completed_tasks", 0),
            "failed": stats.get("failed_tasks", 0),
            "cancelled": stats.get("cancelled_tasks", 0)
        }
    
    def _extract_priority_distribution(self, stats: Dict[str, Any]) -> Dict[str, int]:
        """提取优先级分布"""
        # TODO: 从任务管理器获取真实的优先级分布
        return {
            "urgent": 0,
            "high": 0,
            "normal": 0,
            "low": 0
        }
    
    async def cleanup_completed_tasks(self, max_history: int = 1000) -> Dict[str, Any]:
        """清理已完成的任务历史"""
        try:
            result = await self.task_service.cleanup_old_results()
            result["max_history"] = max_history
            return result
            
        except Exception as e:
            self.logger.error(f"清理任务失败: {str(e)}")
            raise
    
    def _convert_to_task_response(self, task_data: Dict[str, Any]) -> TaskResponse:
        """转换任务数据为TaskResponse格式"""
        start_time = None
        end_time = None
        
        # 安全的时间解析
        if task_data.get("start_time"):
            try:
                if isinstance(task_data["start_time"], str):
                    start_time = parse_datetime(task_data["start_time"])
                else:
                    start_time = task_data["start_time"]
            except:
                start_time = None
        
        if task_data.get("end_time"):
            try:
                if isinstance(task_data["end_time"], str):
                    end_time = parse_datetime(task_data["end_time"])
                else:
                    end_time = task_data["end_time"]
            except:
                end_time = None
        
        # 确定任务类型
        task_type = task_data.get("task_type", "async")
        if "metadata" in task_data and "task_type" in task_data["metadata"]:
            task_type = task_data["metadata"]["task_type"]
        
        return TaskResponse(
            task_id=task_data["task_id"],
            task_name=task_data.get("task_name", "unknown"),
            task_type=task_type,
            status=TaskStatusEnum(task_data.get("status", "pending")),
            priority=task_data.get("priority", 0),
            progress=task_data.get("progress", 0.0),
            result=task_data.get("result"),
            error=task_data.get("error"),
            error_details=task_data.get("error_details"),
            start_time=start_time,
            end_time=end_time,
            duration=task_data.get("duration"),
            timeout=task_data.get("timeout", 300),
            retry_count=task_data.get("retry_count", 0),
            max_retries=task_data.get("max_retries", 0),
            tags=task_data.get("tags"),
            worker_id=task_data.get("worker_id"),
            queue_position=None,  # TODO: 实现队列位置查询
            estimated_completion=None  # TODO: 实现完成时间估算
        )
    
    async def _process_request(self, request_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理任务相关请求的通用方法"""
        if not request_data:
            return {"message": "TaskHandler就绪，任务管理系统正常运行"}
        
        action = request_data.get("action", "status")
        
        if action == "statistics":
            stats = await self.get_task_statistics()
            return stats.dict()
        else:
            return {"message": f"TaskHandler处理中: {action}"}