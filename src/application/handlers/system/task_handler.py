# src/application/handlers/system/task_handler.py (完整版)
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.application.handlers.handler_interface import BaseHandler
from src.application.services.system.task_service import TaskService
from src.infrastructure.tasks.task_manager import task_manager
from src.infrastructure.tasks.task_registry import TaskRegistry
from src.infrastructure.tasks.base_task import create_simple_task, create_service_task, TaskPriority
from src.schemas.dtos.request.task_request import (
    TaskCreateRequest, TaskQueryRequest, TaskCancelRequest, 
    TaskListRequest, TaskBulkOperationRequest
)
from src.schemas.dtos.response.task_response import (
    TaskResponse, TaskListResponse, TaskStatisticsResponse, 
    TaskTypesResponse, TaskSubmitResponse, TaskBulkOperationResponse
)
from src.schemas.enums.base_enums import TaskStatusEnum, TaskTypeEnum
from src.infrastructure.utils.datetime_utils import parse_datetime


class TaskHandler(BaseHandler[Dict[str, Any]]):
    """任务管理处理器 - 完整实现"""
    
    def __init__(self):
        super().__init__()
        self.task_service = TaskService()
        self.task_manager = task_manager
        self.task_registry = TaskRegistry()
    
    async def submit_task(self, request: TaskCreateRequest) -> TaskSubmitResponse:
        """提交任务"""
        try:
            self.logger.info(f"提交任务: {request.task_name}", extra={
                "task_type": request.task_type,
                "priority": request.priority,
                "timeout": request.timeout
            })
            
            # 检查任务是否已注册
            if not self._is_task_registered(request.task_name):
                raise ValueError(f"未注册的任务类型: {request.task_name}")
            
            # 创建任务实例
            task = await self._create_task_from_request(request)
            
            if not task:
                raise ValueError(f"无法创建任务: {request.task_name}")
            
            # 提交任务到管理器
            task_id = await self.task_manager.submit_task(task, **request.params)
            
            # 获取队列信息
            queue_info = self.task_manager.get_queue_info()
            
            return TaskSubmitResponse(
                task_id=task_id,
                status=TaskStatusEnum.PENDING,
                queue_position=queue_info.get("queue_size", 0),
                estimated_start_time=self._estimate_start_time(queue_info),
                estimated_completion_time=self._estimate_completion_time(request.timeout, queue_info)
            )
            
        except Exception as e:
            self.logger.error(f"提交任务失败: {request.task_name} - {str(e)}")
            raise
    
    async def get_task_status(self, request: TaskQueryRequest) -> TaskResponse:
        """获取任务状态"""
        try:
            task_id = request.task_id
            
            # 先从任务管理器获取活跃任务
            status_info = await self.task_manager.get_task_status(task_id)
            
            if not status_info:
                # 从存储中获取历史任务
                status_info = await self.task_manager.storage.get_task_result(task_id)
                
                if not status_info:
                    raise ValueError(f"任务不存在: {task_id}")
            
            # 根据请求参数过滤返回数据
            if not request.include_result:
                status_info.pop("result", None)
            
            if not request.include_metadata:
                status_info.pop("metadata", None)
            
            return self._convert_to_task_response(status_info)
            
        except Exception as e:
            self.logger.error(f"获取任务状态失败: {request.task_id} - {str(e)}")
            raise
    
    async def cancel_task(self, request: TaskCancelRequest) -> Dict[str, Any]:
        """取消任务"""
        try:
            task_id = request.task_id
            reason = request.reason or "用户取消"
            
            if request.force:
                # 强制终止
                success = self.task_manager.force_kill_task(task_id, f"强制取消: {reason}")
            else:
                # 正常取消
                success = await self.task_manager.cancel_task(task_id, reason)
            
            if not success:
                raise ValueError(f"任务不存在或无法取消: {task_id}")
            
            return {
                "task_id": task_id,
                "cancelled": True,
                "reason": reason,
                "force": request.force,
                "cancelled_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"取消任务失败: {request.task_id} - {str(e)}")
            raise
    
    async def get_task_list(self, request: TaskListRequest) -> TaskListResponse:
        """获取任务列表"""
        try:
            # 获取活跃任务
            active_tasks = self.task_manager.get_all_tasks()
            
            # 获取历史任务
            historical_tasks = await self.task_service.get_task_history(limit=request.limit * 2)
            
            # 合并任务数据
            all_tasks = self._merge_task_data(active_tasks, historical_tasks)
            
            # 应用过滤条件
            filtered_tasks = self._filter_tasks(all_tasks, request)
            
            # 排序
            sorted_tasks = self._sort_tasks(filtered_tasks, request.sort_by, request.sort_order)
            
            # 分页
            total = len(sorted_tasks)
            start_idx = request.offset
            end_idx = start_idx + request.limit
            paginated_tasks = sorted_tasks[start_idx:end_idx]
            
            # 转换为响应格式
            task_responses = [
                self._convert_to_task_response(task_data)
                for task_data in paginated_tasks
            ]
            
            page = (request.offset // request.limit) + 1 if request.limit > 0 else 1
            
            return TaskListResponse(
                tasks=task_responses,
                total=total,
                page=page,
                size=len(task_responses),
                has_next=end_idx < total,
                has_prev=request.offset > 0
            )
            
        except Exception as e:
            self.logger.error(f"获取任务列表失败: {str(e)}")
            raise
    
    async def get_task_statistics(self) -> TaskStatisticsResponse:
        """获取任务统计信息"""
        try:
            # 获取核心统计
            stats = await self.task_manager.get_statistics()
            runtime_stats = stats["runtime"]
            performance_stats = stats["performance"]
            
            # 获取详细状态分布
            all_tasks = self.task_manager.get_all_tasks()
            status_distribution = self._calculate_status_distribution(all_tasks)
            priority_distribution = self._calculate_priority_distribution(all_tasks)
            
            # 计算24小时统计
            recent_stats = await self._calculate_recent_stats()
            
            return TaskStatisticsResponse(
                total_tasks=runtime_stats["total_tasks"],
                running_tasks=runtime_stats["running_tasks"],
                completed_tasks=runtime_stats["completed_tasks"],
                failed_tasks=runtime_stats["failed_tasks"],
                pending_tasks=runtime_stats["pending_tasks"],
                cancelled_tasks=runtime_stats["cancelled_tasks"],
                average_duration=performance_stats.get("avg_execution_time", 0.0),
                median_duration=performance_stats.get("median_execution_time", 0.0),
                success_rate=runtime_stats.get("success_rate", 0.0),
                failure_rate=1.0 - runtime_stats.get("success_rate", 0.0),
                worker_utilization=runtime_stats.get("worker_utilization", 0.0),
                queue_size=runtime_stats.get("queue_size", 0),
                max_queue_size=10000,  # 可配置
                last_24h_completed=recent_stats["completed"],
                last_24h_failed=recent_stats["failed"],
                status_distribution=status_distribution,
                priority_distribution=priority_distribution
            )
            
        except Exception as e:
            self.logger.error(f"获取任务统计失败: {str(e)}")
            raise
    
    async def get_registered_tasks(self) -> TaskTypesResponse:
        """获取已注册的任务类型"""
        try:
            # 获取注册信息
            registered_tasks = self.task_registry.get_task_types()
            
            # 分类任务类型
            sync_tasks = []
            async_tasks = []
            task_categories = {}
            
            for task_name, task_info in registered_tasks.items():
                task_type = task_info.get("type", "async")
                category = task_info.get("category", "general")
                
                if task_type == "sync":
                    sync_tasks.append(task_name)
                else:
                    async_tasks.append(task_name)
                
                if category not in task_categories:
                    task_categories[category] = []
                task_categories[category].append(task_name)
            
            return TaskTypesResponse(
                sync_tasks=sync_tasks,
                async_tasks=async_tasks,
                total_registered=len(registered_tasks),
                task_categories=task_categories
            )
            
        except Exception as e:
            self.logger.error(f"获取任务类型失败: {str(e)}")
            raise
    
    async def bulk_operation(self, request: TaskBulkOperationRequest) -> TaskBulkOperationResponse:
        """批量任务操作"""
        try:
            operation = request.operation
            task_ids = request.task_ids
            params = request.params
            
            results = []
            successful = 0
            failed = 0
            
            for task_id in task_ids:
                try:
                    if operation == "cancel":
                        force = params.get("force", False)
                        reason = params.get("reason", "批量取消")
                        
                        if force:
                            success = self.task_manager.force_kill_task(task_id, reason)
                        else:
                            success = await self.task_manager.cancel_task(task_id, reason)
                        
                        if success:
                            successful += 1
                            results.append({"task_id": task_id, "success": True})
                        else:
                            failed += 1
                            results.append({"task_id": task_id, "success": False, "error": "任务不存在或无法取消"})
                    
                    elif operation == "delete":
                        delete_from_s3 = params.get("delete_from_s3", False)
                        deletion_result = await self.task_manager.storage.delete_result(task_id, delete_from_s3)
                        
                        if deletion_result["deleted_from"]:
                            successful += 1
                            results.append({"task_id": task_id, "success": True, "deleted_from": deletion_result["deleted_from"]})
                        else:
                            failed += 1
                            results.append({"task_id": task_id, "success": False, "error": "任务结果不存在"})
                    
                    else:
                        failed += 1
                        results.append({"task_id": task_id, "success": False, "error": f"不支持的操作: {operation}"})
                
                except Exception as e:
                    failed += 1
                    results.append({"task_id": task_id, "success": False, "error": str(e)})
            
            return TaskBulkOperationResponse(
                operation=operation,
                total_requested=len(task_ids),
                successful=successful,
                failed=failed,
                results=results
            )
            
        except Exception as e:
            self.logger.error(f"批量操作失败: {str(e)}")
            raise
    
    async def cleanup_completed_tasks(self, max_history: int = 1000) -> Dict[str, Any]:
        """清理已完成的任务"""
        try:
            cleanup_result = await self.task_service.cleanup_old_results()
            cleanup_result["max_history"] = max_history
            cleanup_result["cleaned_at"] = datetime.utcnow().isoformat()
            
            return cleanup_result
            
        except Exception as e:
            self.logger.error(f"清理任务失败: {str(e)}")
            raise
    
    def _is_task_registered(self, task_name: str) -> bool:
        """检查任务是否已注册"""
        registered_tasks = self.task_registry.get_task_types()
        return task_name in registered_tasks
    
    async def _create_task_from_request(self, request: TaskCreateRequest):
        """从请求创建任务实例"""
        try:
            task_name = request.task_name
            priority = TaskPriority.from_int(request.priority)
            
            # 这里可以根据任务名称创建不同类型的任务
            # 简化实现：创建一个通用的服务任务
            
            # 获取任务信息
            registered_tasks = self.task_registry.get_task_types()
            task_info = registered_tasks.get(task_name)
            
            if not task_info:
                return None
            
            # 根据任务类型创建任务实例
            if task_info.get("type") == "service":
                # 服务任务
                service_name = task_info.get("service_name")
                method_name = task_info.get("method_name")
                
                # 这里应该从依赖注入容器获取服务实例
                # 简化实现
                return create_service_task(
                    task_name=task_name,
                    service_instance=self.task_service,  # 示例
                    method_name=method_name or "execute_task",
                    priority=priority.value,
                    timeout=request.timeout,
                    max_retries=request.max_retries
                )
            else:
                # 函数任务
                task_func = task_info.get("function")
                if task_func:
                    return create_simple_task(
                        task_name=task_name,
                        task_func=task_func,
                        priority=priority.value,
                        timeout=request.timeout,
                        max_retries=request.max_retries
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"创建任务失败: {request.task_name} - {str(e)}")
            return None
    
    def _merge_task_data(self, active_tasks: List[Dict], historical_tasks: List[Dict]) -> List[Dict]:
        """合并活跃任务和历史任务"""
        task_dict = {}
        
        # 活跃任务优先
        for task_data in active_tasks:
            task_id = task_data.get("task_id")
            if task_id:
                task_dict[task_id] = task_data
        
        # 添加历史任务（不覆盖活跃任务）
        for task_data in historical_tasks:
            task_id = task_data.get("task_id")
            if task_id and task_id not in task_dict:
                task_dict[task_id] = task_data
        
        return list(task_dict.values())
    
    def _filter_tasks(self, tasks: List[Dict], request: TaskListRequest) -> List[Dict]:
        """根据请求参数过滤任务"""
        filtered = tasks
        
        if request.status_filter:
            filtered = [t for t in filtered if t.get("status") == request.status_filter]
        
        if request.task_name_filter:
            filtered = [t for t in filtered if t.get("task_name") == request.task_name_filter]
        
        if request.priority_min is not None:
            filtered = [t for t in filtered if t.get("priority", 0) >= request.priority_min]
        
        if request.priority_max is not None:
            filtered = [t for t in filtered if t.get("priority", 0) <= request.priority_max]
        
        if request.tags_filter:
            filtered = [
                t for t in filtered 
                if any(tag in t.get("tags", []) for tag in request.tags_filter)
            ]
        
        return filtered
    
    def _sort_tasks(self, tasks: List[Dict], sort_by: str, sort_order: str) -> List[Dict]:
        """排序任务"""
        reverse = sort_order.lower() == "desc"
        
        try:
            if sort_by == "created_at":
                return sorted(tasks, key=lambda x: x.get("created_at") or "", reverse=reverse)
            elif sort_by == "priority":
                return sorted(tasks, key=lambda x: x.get("priority", 0), reverse=reverse)
            elif sort_by == "status":
                return sorted(tasks, key=lambda x: x.get("status", ""), reverse=reverse)
            elif sort_by == "duration":
                return sorted(tasks, key=lambda x: x.get("duration", 0), reverse=reverse)
            else:
                # 默认按创建时间排序
                return sorted(tasks, key=lambda x: x.get("created_at") or "", reverse=True)
        except Exception:
            # 排序失败时返回原列表
            return tasks
    
    def _calculate_status_distribution(self, tasks: List[Dict]) -> Dict[str, int]:
        """计算状态分布"""
        distribution = {}
        for task in tasks:
            status = task.get("status", "unknown")
            distribution[status] = distribution.get(status, 0) + 1
        return distribution
    
    def _calculate_priority_distribution(self, tasks: List[Dict]) -> Dict[str, int]:
        """计算优先级分布"""
        priority_names = {0: "low", 1: "normal", 2: "high", 3: "urgent"}
        distribution = {"low": 0, "normal": 0, "high": 0, "urgent": 0}
        
        for task in tasks:
            priority = task.get("priority", 1)
            priority_name = priority_names.get(priority, "normal")
            distribution[priority_name] += 1
        
        return distribution
    
    async def _calculate_recent_stats(self) -> Dict[str, int]:
        """计算最近24小时统计"""
        # 简化实现，实际应该从存储中查询24小时内的任务
        cutoff_time = datetime.utcnow().timestamp() - 86400  # 24小时前
        
        # 这里应该实现实际的时间范围查询
        return {
            "completed": 0,
            "failed": 0
        }
    
    def _estimate_start_time(self, queue_info: Dict) -> Optional[datetime]:
        """估算开始时间"""
        queue_size = queue_info.get("queue_size", 0)
        if queue_size == 0:
            return datetime.utcnow()
        
        # 简单估算：假设每个任务平均1分钟
        estimated_delay = queue_size * 60
        return datetime.utcnow().timestamp() + estimated_delay
    
    def _estimate_completion_time(self, timeout: Optional[int], queue_info: Dict) -> Optional[datetime]:
        """估算完成时间"""
        start_time = self._estimate_start_time(queue_info)
        if start_time and timeout:
            return start_time + timeout
        return None
    
    def _convert_to_task_response(self, task_data: Dict[str, Any]) -> TaskResponse:
        """转换任务数据为TaskResponse格式"""
        # 安全的时间解析
        def safe_parse_datetime(dt_str):
            if not dt_str:
                return None
            try:
                if isinstance(dt_str, str):
                    return parse_datetime(dt_str)
                elif isinstance(dt_str, datetime):
                    return dt_str
                else:
                    return None
            except:
                return None
        
        start_time = safe_parse_datetime(task_data.get("start_time"))
        end_time = safe_parse_datetime(task_data.get("end_time"))
        created_at = safe_parse_datetime(task_data.get("created_at"))
        
        # 确定任务类型
        task_type_str = task_data.get("task_type", "async")
        if task_type_str == "sync":
            task_type = TaskTypeEnum.SYNC
        else:
            task_type = TaskTypeEnum.ASYNC
        
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
            queue_position=None,  # 实时计算较复杂，暂时为None
            estimated_completion=None,  # 同上
            created_at=created_at,
            updated_at=end_time or start_time or created_at
        )
    
    async def _process_request(self, request_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理任务相关请求的通用方法"""
        if not request_data:
            # 返回任务系统状态概览
            stats = await self.get_task_statistics()
            queue_info = self.task_manager.get_queue_info()
            storage_stats = self.task_manager.storage.get_storage_statistics()
            
            return {
                "message": "TaskHandler就绪，任务管理系统正常运行",
                "system_overview": {
                    "total_tasks": stats.total_tasks,
                    "running_tasks": stats.running_tasks,
                    "queue_size": queue_info["queue_size"],
                    "worker_utilization": queue_info["worker_utilization"],
                    "storage_enabled": storage_stats.get("s3_enabled", False)
                }
            }
        
        action = request_data.get("action", "status")
        
        if action == "statistics":
            stats = await self.get_task_statistics()
            return stats.dict()
        elif action == "queue_info":
            return self.task_manager.get_queue_info()
        elif action == "storage_stats":
            return self.task_manager.storage.get_storage_statistics()
        else:
            return {"message": f"TaskHandler处理中: {action}", "data": request_data}