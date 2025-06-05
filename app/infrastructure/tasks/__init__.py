# tasks/__init__.py
"""
Tasks module - 任务管理系统

提供纯粹的任务调度、排队、状态管理功能
不包含具体业务逻辑
"""

from app.infrastructure.tasks.task_manager import TaskManager, task_manager
from app.infrastructure.tasks.task_registry import TaskRegistry, task_registry, register_service_as_task
from app.infrastructure.tasks.base_task import BaseTask, TaskPriority, TaskResult
from app.infrastructure.tasks.generic_task import ServiceTask, TaskFactory
from app.schemas.enums.base_enums import TaskStatusEnum

# 导出主要组件
__all__ = [
    'TaskManager',
    'TaskRegistry', 
    'BaseTask',
    'ServiceTask',
    'TaskFactory',
    'TaskPriority',
    'TaskResult',
    'TaskStatusEnum',
    'task_registry',
    'task_manager',
    'register_service_as_task'
]