# src/infrastructure/tasks/base_task.py (更新版)
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    URGENT = 3
    HIGH = 2
    NORMAL = 1
    LOW = 0
    
    @classmethod
    def from_int(cls, value: int) -> "TaskPriority":
        """从整数转换为优先级"""
        mapping = {
            3: cls.URGENT,
            2: cls.HIGH,
            1: cls.NORMAL,
            0: cls.LOW
        }
        return mapping.get(value, cls.NORMAL)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class BaseTask(ABC):
    """
    基础任务类 - 所有任务的抽象基类
    
    这个类定义了任务系统的核心接口，所有具体任务都必须继承这个类。
    包含任务的基本属性、状态管理和执行接口。
    """
    
    def __init__(
        self,
        task_name: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[int] = None,
        max_retries: int = 0,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        # 任务标识
        self.task_id: Optional[str] = None  # 由TaskManager分配
        self.task_name = task_name
        
        # 执行配置
        self.priority = priority
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_count = 0
        
        # 标签和元数据
        self.tags = tags or []
        self.metadata = metadata or {}
        
        # 执行状态
        self.status = TaskStatus.PENDING
        self.created_at: Optional[datetime] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.duration: Optional[float] = None
        
        # 执行结果
        self.result: Any = None
        self.error: Optional[str] = None
        self.error_details: Optional[Dict[str, Any]] = None
        
        # 执行环境
        self.worker_id: Optional[str] = None
        self.params: Dict[str, Any] = {}
        
        # 日志
        self.logger = get_logger(f"{self.__class__.__name__}")
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        执行任务的抽象方法
        
        子类必须实现这个方法来定义具体的任务逻辑。
        
        Returns:
            Any: 任务执行结果
            
        Raises:
            Exception: 任务执行过程中的任何异常
        """
        pass
    
    def add_tag(self, tag: str) -> None:
        """添加标签"""
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """移除标签"""
        if tag in self.tags:
            self.tags.remove(tag)
    
    def has_tag(self, tag: str) -> bool:
        """检查是否有指定标签"""
        return tag in self.tags
    
    def set_metadata(self, key: str, value: Any) -> None:
        """设置元数据"""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self.metadata.get(key, default)
    
    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self) -> None:
        """增加重试次数"""
        self.retry_count += 1
    
    def is_completed(self) -> bool:
        """检查任务是否已完成"""
        return self.status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT]
    
    def is_successful(self) -> bool:
        """检查任务是否成功"""
        return self.status == TaskStatus.SUCCESS
    
    def is_failed(self) -> bool:
        """检查任务是否失败"""
        return self.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "task_type": self.__class__.__name__,
            "priority": self.priority.value if self.priority else 1,
            "status": self.status.value,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "result": self.result,
            "error": self.error,
            "error_details": self.error_details,
            "worker_id": self.worker_id,
            "params": self.params
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(task_id={self.task_id}, name={self.task_name}, status={self.status.value})"


class SimpleTask(BaseTask):
    """
    简单任务类 - 基于函数的任务实现
    
    这是BaseTask的一个简单实现，允许直接传入一个函数作为任务逻辑。
    适用于简单的、不需要复杂状态管理的任务。
    """
    
    def __init__(
        self,
        task_name: str,
        task_func: callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[int] = None,
        max_retries: int = 0,
        **kwargs
    ):
        super().__init__(
            task_name=task_name,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            **kwargs
        )
        self.task_func = task_func
    
    async def execute(self, **kwargs) -> Any:
        """执行函数任务"""
        try:
            # 合并参数：任务创建时的params + 执行时的kwargs
            all_params = {**self.params, **kwargs}
            
            self.logger.debug(f"执行简单任务: {self.task_name}", extra={
                "task_name": self.task_name,
                "func_name": getattr(self.task_func, '__name__', 'unknown'),
                "params": all_params
            })
            
            # 检查函数是否是异步的
            import asyncio
            import inspect
            
            if inspect.iscoroutinefunction(self.task_func):
                result = await self.task_func(**all_params)
            else:
                result = self.task_func(**all_params)
            
            self.logger.info(f"简单任务执行成功: {self.task_name}", extra={
                "task_name": self.task_name,
                "result_type": type(result).__name__
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"简单任务执行失败: {self.task_name} - {str(e)}", extra={
                "task_name": self.task_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "params": self.params
            }, exc_info=True)
            raise


class ServiceTask(BaseTask):
    """
    服务任务类 - 基于服务方法的任务实现
    
    这个类用于包装服务层的方法调用，将业务逻辑转换为可调度的任务。
    通常用于异步处理复杂的业务流程。
    """
    
    def __init__(
        self,
        task_name: str,
        service_instance: Any,
        method_name: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[int] = None,
        max_retries: int = 0,
        **kwargs
    ):
        super().__init__(
            task_name=task_name,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            **kwargs
        )
        self.service_instance = service_instance
        self.method_name = method_name
    
    async def execute(self, **kwargs) -> Any:
        """执行服务方法"""
        try:
            # 获取服务方法
            if not hasattr(self.service_instance, self.method_name):
                raise AttributeError(f"服务 {self.service_instance.__class__.__name__} 没有方法 {self.method_name}")
            
            method = getattr(self.service_instance, self.method_name)
            
            # 合并参数
            all_params = {**self.params, **kwargs}
            
            # 执行方法
            import asyncio
            import inspect
            
            if inspect.iscoroutinefunction(method):
                result = await method(**all_params)
            else:
                result = method(**all_params)
            
            return result
            
        except Exception as e:
            self.logger.error(f"服务任务执行失败: {self.task_name} - {str(e)}")
            raise


def create_simple_task(
    task_name: str,
    task_func: callable,
    priority: int = 1,
    timeout: Optional[int] = None,
    max_retries: int = 0,
    params: Optional[Dict[str, Any]] = None,
    **kwargs
) -> SimpleTask:
    """
    创建简单任务的便捷函数
    
    Args:
        task_name: 任务名称
        task_func: 任务函数
        priority: 优先级(0-3)
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        params: 任务参数字典
        **kwargs: 其他任务参数
    
    Returns:
        SimpleTask: 简单任务实例
    """
    task = SimpleTask(
        task_name=task_name,
        task_func=task_func,
        priority=TaskPriority.from_int(priority),
        timeout=timeout,
        max_retries=max_retries,
        **kwargs
    )
    
    # 设置任务参数
    if params:
        task.params = params
    
    return task


def create_service_task(
    task_name: str,
    service_instance: Any,
    method_name: str,
    priority: int = 1,
    timeout: Optional[int] = None,
    max_retries: int = 0,
    params: Optional[Dict[str, Any]] = None,
    **kwargs
) -> ServiceTask:
    """
    创建服务任务的便捷函数
    
    Args:
        task_name: 任务名称
        service_instance: 服务实例
        method_name: 方法名称
        priority: 优先级(0-3)
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        params: 任务参数字典
        **kwargs: 其他任务参数
    
    Returns:
        ServiceTask: 服务任务实例
    """
    task = ServiceTask(
        task_name=task_name,
        service_instance=service_instance,
        method_name=method_name,
        priority=TaskPriority.from_int(priority),
        timeout=timeout,
        max_retries=max_retries,
        **kwargs
    )
    
    # 设置任务参数
    if params:
        task.params = params
    
    return task