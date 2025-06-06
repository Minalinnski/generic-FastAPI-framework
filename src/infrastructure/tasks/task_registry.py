# src/infrastructure/tasks/task_registry.py
"""
增强的任务注册表 - 支持请求任务的注册和监控
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict

from src.infrastructure.logging.logger import get_logger
from src.infrastructure.tasks.request_task import RequestTask

logger = get_logger(__name__)


class TaskRegistry:
    """
    任务注册表 - 管理所有类型的任务
    
    功能：
    1. 注册API请求任务类型
    2. 记录任务执行统计
    3. 提供任务搜索和查询
    4. 管理任务模板
    """
    
    def __init__(self):
        self.logger = logger
        
        # 任务类型注册
        self._task_types: Dict[str, Dict[str, Any]] = {}
        
        # 任务执行统计
        self._execution_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_executed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "total_timeout": 0,
            "avg_duration": 0.0,
            "last_executed": None
        })
        
        # 任务模板（用于创建相同类型的任务）
        self._task_templates: Dict[str, Dict[str, Any]] = {}
    
    def register_api_task_type(
        self, 
        task_name: str,
        route_path: str,
        method: str,
        handler_name: str,
        default_config: Optional[Dict[str, Any]] = None
    ) -> None:
        """注册API任务类型"""
        task_info = {
            "task_name": task_name,
            "type": "api_request",
            "route_path": route_path,
            "http_method": method,
            "handler_name": handler_name,
            "registered_at": datetime.utcnow().isoformat(),
            "default_config": default_config or {
                "timeout": 300,
                "priority": 0,
                "max_retries": 2
            }
        }
        
        self._task_types[task_name] = task_info
        
        self.logger.info(f"注册API任务类型: {task_name}", extra={
            "route": f"{method} {route_path}",
            "handler": handler_name
        })
    
    def update_execution_stats(self, task_name: str, duration: float, status: str) -> None:
        """更新任务执行统计"""
        stats = self._execution_stats[task_name]
        
        stats["total_executed"] += 1
        stats["last_executed"] = datetime.utcnow().isoformat()
        
        if status == "success":
            stats["total_success"] += 1
        elif status == "failed":
            stats["total_failed"] += 1
        elif status == "cancelled":
            stats["total_cancelled"] += 1
        elif status == "timeout":
            stats["total_timeout"] += 1
        
        # 更新平均执行时间
        total_success = stats["total_success"]
        if total_success > 0:
            old_avg = stats["avg_duration"]
            stats["avg_duration"] = (old_avg * (total_success - 1) + duration) / total_success
    
    def get_task_types(self) -> Dict[str, Any]:
        """获取所有注册的任务类型"""
        return self._task_types.copy()
    
    def get_task_stats(self, task_name: Optional[str] = None) -> Dict[str, Any]:
        """获取任务统计信息"""
        if task_name:
            return self._execution_stats.get(task_name, {})
        return dict(self._execution_stats)
    
    def search_tasks(self, query: str) -> List[Dict[str, Any]]:
        """搜索任务类型"""
        results = []
        query_lower = query.lower()
        
        for task_name, task_info in self._task_types.items():
            # 在任务名、路径、处理器中搜索
            searchable = f"{task_name} {task_info.get('route_path', '')} {task_info.get('handler_name', '')}".lower()
            
            if query_lower in searchable:
                result = task_info.copy()
                result["stats"] = self._execution_stats.get(task_name, {})
                results.append(result)
        
        return results
    
    def get_registry_summary(self) -> Dict[str, Any]:
        """获取注册表摘要"""
        total_types = len(self._task_types)
        total_executed = sum(stats["total_executed"] for stats in self._execution_stats.values())
        total_success = sum(stats["total_success"] for stats in self._execution_stats.values())
        
        return {
            "total_task_types": total_types,
            "total_executed": total_executed,
            "total_success": total_success,
            "success_rate": total_success / total_executed if total_executed > 0 else 0,
            "api_task_types": total_types  # 目前都是API任务
        }