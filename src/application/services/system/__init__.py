# src/application/services/system/__init__.py
"""
系统服务模块

包含框架核心的系统级服务：
- HealthService: 健康检查
- TaskService: 任务管理
"""

from src.application.services.system.health_service import HealthService
from src.application.services.system.task_service import TaskService

__all__ = ['HealthService', 'TaskService']