# app/application/services/task_service.py - 清理后的纯任务管理服务
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.application.services.base_service import BaseService
from app.infrastructure.cache.task_result_cache import task_result_cache
from app.infrastructure.tasks.task_manager import task_manager
from app.infrastructure.tasks.task_registry import task_registry
from app.schemas.enums.base_enums import TaskStatusEnum


class TaskService(BaseService):
    """
    任务业务服务 - 纯任务管理功能
    
    职责：
    1. 任务提交和管理
    2. 任务状态查询和监控
    3. 任务结果缓存管理
    4. 任务统计分析
    5. 任务生命周期管理
    """
    
    def __init__(self):
        super().__init__()
        self.task_manager = task_manager
        self.task_registry = task_registry
        self.result_cache = task_result_cache
    
    async def get_task_history(
        self, 
        task_name: Optional[str] = None,
        status: Optional[TaskStatusEnum] = None,
        limit: int = 50,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """获取任务历史"""
        self.logger.info("获取任务历史", extra={
            "task_name": task_name,
            "status": status.value if status else None,
            "limit": limit
        })
        
        # 从缓存获取任务历史
        if task_name or status:
            history = self.result_cache.search_tasks(
                task_name=task_name,
                status=status,
                limit=limit
            )
        else:
            history = self.result_cache.get_recent_tasks(limit)
        
        # 时间范围过滤
        if start_time or end_time:
            filtered_history = []
            for task_data in history:
                task_time = None
                if task_data.get("end_time"):
                    task_time = datetime.fromisoformat(task_data["end_time"].replace('Z', '+00:00'))
                elif task_data.get("start_time"):
                    task_time = datetime.fromisoformat(task_data["start_time"].replace('Z', '+00:00'))
                
                if task_time:
                    if start_time and task_time < start_time:
                        continue
                    if end_time and task_time > end_time:
                        continue
                
                filtered_history.append(task_data)
            
            history = filtered_history
        
        self.logger.info(f"获取到任务历史: {len(history)} 条记录")
        return history
    
    async def get_task_statistics(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        self.logger.info("获取任务统计信息")
        
        # 从任务管理器获取运行时统计
        manager_stats = self.task_manager.get_statistics()
        
        # 从缓存获取历史统计
        cache_stats = self.result_cache.get_statistics()
        
        # 获取性能指标
        performance_metrics = self.task_manager.get_performance_metrics()
        
        # 获取注册表统计
        registry_stats = self.task_registry.get_registry_stats()
        
        # 获取队列信息
        queue_info = self.task_manager.get_queue_info()
        
        # 获取执行器信息
        executor_info = self.task_manager.get_executor_info()
        
        # 组合统计信息
        combined_stats = {
            "runtime": manager_stats,
            "cache": cache_stats,
            "performance": performance_metrics,
            "registry": registry_stats,
            "queue": queue_info,
            "executors": executor_info,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return combined_stats
    
    async def get_task_analytics(
        self, 
        time_range: str = "24h"  # "1h", "24h", "7d", "30d"
    ) -> Dict[str, Any]:
        """获取任务分析数据"""
        self.logger.info(f"获取任务分析数据: {time_range}")
        
        # 计算时间范围
        now = datetime.utcnow()
        if time_range == "1h":
            start_time = now - timedelta(hours=1)
        elif time_range == "24h":
            start_time = now - timedelta(days=1)
        elif time_range == "7d":
            start_time = now - timedelta(days=7)
        elif time_range == "30d":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=1)
        
        # 获取时间范围内的任务
        tasks = await self.get_task_history(
            start_time=start_time,
            end_time=now,
            limit=1000
        )
        
        # 分析数据
        analytics = {
            "time_range": time_range,
            "start_time": start_time.isoformat(),
            "end_time": now.isoformat(),
            "total_tasks": len(tasks),
            "status_breakdown": {},
            "task_type_breakdown": {},
            "average_duration": 0,
            "success_rate": 0,
            "peak_hours": [],
            "slowest_tasks": [],
            "most_failed_tasks": []
        }
        
        if not tasks:
            return analytics
        
        # 状态分布
        status_counts = {}
        durations = []
        hourly_counts = {}
        task_type_counts = {}
        task_failures = {}
        
        for task in tasks:
            # 状态统计
            status = task.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # 任务类型统计
            task_name = task.get("task_name", "unknown")
            task_type_counts[task_name] = task_type_counts.get(task_name, 0) + 1
            
            # 失败任务统计
            if status == "failed":
                task_failures[task_name] = task_failures.get(task_name, 0) + 1
            
            # 时长统计
            if task.get("duration"):
                durations.append(task["duration"])
            
            # 小时分布统计
            if task.get("start_time"):
                try:
                    start_dt = datetime.fromisoformat(task["start_time"].replace('Z', '+00:00'))
                    hour = start_dt.hour
                    hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
                except:
                    pass
        
        # 计算指标
        analytics["status_breakdown"] = status_counts
        analytics["task_type_breakdown"] = task_type_counts
        
        if durations:
            analytics["average_duration"] = sum(durations) / len(durations)
        
        success_count = status_counts.get("success", 0)
        analytics["success_rate"] = success_count / len(tasks) if tasks else 0
        
        # 找出高峰时段
        if hourly_counts:
            sorted_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)
            analytics["peak_hours"] = sorted_hours[:3]
        
        # 最慢的任务类型
        task_avg_durations = {}
        for task in tasks:
            task_name = task.get("task_name")
            duration = task.get("duration")
            if task_name and duration:
                if task_name not in task_avg_durations:
                    task_avg_durations[task_name] = []
                task_avg_durations[task_name].append(duration)
        
        slowest_tasks = []
        for task_name, duration_list in task_avg_durations.items():
            avg_duration = sum(duration_list) / len(duration_list)
            slowest_tasks.append({"task_name": task_name, "avg_duration": avg_duration})
        
        analytics["slowest_tasks"] = sorted(slowest_tasks, key=lambda x: x["avg_duration"], reverse=True)[:5]
        
        # 失败最多的任务
        most_failed = [{"task_name": k, "failure_count": v} for k, v in task_failures.items()]
        analytics["most_failed_tasks"] = sorted(most_failed, key=lambda x: x["failure_count"], reverse=True)[:5]
        
        return analytics
    
    async def cleanup_old_results(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """清理旧的任务结果"""
        self.logger.info(f"开始清理超过 {max_age_hours} 小时的任务结果")
        
        # 清理过期缓存
        expired_count = self.result_cache.cleanup_expired()
        
        # 清理任务管理器中的历史
        cleaned_history = self.task_manager.cleanup_completed_tasks(max_history=1000)
        
        result = {
            "cleaned_cache_entries": expired_count,
            "cleaned_history_entries": cleaned_history,
            "cleanup_time": datetime.utcnow().isoformat(),
            "max_age_hours": max_age_hours
        }
        
        self.logger.info("任务结果清理完成", extra=result)
        return result
    
    async def bulk_cancel_tasks(self, task_ids: List[str], reason: str = "批量取消") -> Dict[str, Any]:
        """批量取消任务"""
        self.logger.info(f"批量取消任务: {len(task_ids)} 个任务")
        
        results = []
        successful = 0
        failed = 0
        
        for task_id in task_ids:
            try:
                success = self.task_manager.cancel_task(task_id, reason)
                if success:
                    successful += 1
                    results.append({"task_id": task_id, "success": True})
                else:
                    failed += 1
                    results.append({"task_id": task_id, "success": False, "error": "无法取消"})
            except Exception as e:
                failed += 1
                results.append({"task_id": task_id, "success": False, "error": str(e)})
        
        return {
            "total_requested": len(task_ids),
            "successful": successful,
            "failed": failed,
            "results": results
        }
    
    async def update_task_priority(self, task_id: str, new_priority: int) -> bool:
        """更新任务优先级"""
        from app.infrastructure.tasks.base_task import TaskPriority
        
        try:
            priority = TaskPriority.from_int(new_priority)
            success = self.task_manager.update_task_priority(task_id, priority)
            
            if success:
                self.logger.info(f"任务优先级已更新: {task_id} -> {priority.name}")
            
            return success
        except Exception as e:
            self.logger.error(f"更新任务优先级失败: {task_id} - {str(e)}")
            return False
    
    async def get_task_queue_status(self) -> Dict[str, Any]:
        """获取任务队列状态"""
        queue_info = self.task_manager.get_queue_info()
        executor_info = self.task_manager.get_executor_info()
        
        return {
            "queue": queue_info,
            "executors": executor_info,
            "system_status": "healthy" if queue_info["queue_size"] < 100 else "busy"
        }