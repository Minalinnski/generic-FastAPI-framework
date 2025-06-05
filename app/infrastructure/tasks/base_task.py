# app/infrastructure/tasks/base_task.py
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.infrastructure.logging.logger import get_logger
from app.schemas.enums.base_enums import TaskStatusEnum

logger = get_logger(__name__)


class TaskPriority(Enum):
    """任务优先级枚举"""
    URGENT = 2      # 紧急任务
    HIGH = 1        # 高优先级
    NORMAL = 0      # 普通优先级
    LOW = -1        # 低优先级
    
    @classmethod
    def from_int(cls, value: int) -> "TaskPriority":
        """从整数值创建优先级"""
        priority_map = {
            2: cls.URGENT,
            1: cls.HIGH,
            0: cls.NORMAL,
            -1: cls.LOW
        }
        return priority_map.get(value, cls.NORMAL)


class TaskResult:
    """任务结果封装"""
    
    def __init__(
        self,
        task_id: str,
        status: TaskStatusEnum,
        result: Any = None,
        error: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress: float = 0.0
    ):
        self.task_id = task_id
        self.status = status
        self.result = result
        self.error = error
        self.error_details = error_details or {}
        self.start_time = start_time
        self.end_time = end_time
        self.metadata = metadata or {}
        self.progress = progress
    
    @property
    def duration(self) -> Optional[float]:
        """任务执行时长（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def is_completed(self) -> bool:
        """是否已完成（成功或失败）"""
        return self.status in [TaskStatusEnum.SUCCESS, TaskStatusEnum.FAILED, TaskStatusEnum.CANCELLED]
    
    @property
    def is_successful(self) -> bool:
        """是否成功完成"""
        return self.status == TaskStatusEnum.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "error_details": self.error_details,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "metadata": self.metadata,
            "progress": self.progress
        }


class BaseTask(ABC):
    """
    基础任务抽象类
    
    职责：
    1. 任务状态管理
    2. 优先级和队列管理
    3. 重试和超时控制
    4. 进度追踪
    5. 元数据管理
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
        self.task_id = str(uuid.uuid4())
        self.task_name = task_name
        self.priority = priority
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_count = 0
        self.tags = tags or []
        
        # 状态管理
        self.status = TaskStatusEnum.PENDING
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.error_details: Dict[str, Any] = {}
        self.progress: float = 0.0
        self.metadata: Dict[str, Any] = metadata or {}
        
        # 执行上下文
        self.worker_id: Optional[str] = None
        self.submitted_at = datetime.utcnow()
        
        # 日志
        self.logger = logger
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行任务 - 子类必须实现"""
        pass
    
    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return (
            self.retry_count < self.max_retries and 
            self.status in [TaskStatusEnum.FAILED, TaskStatusEnum.TIMEOUT]
        )
    
    def should_timeout(self) -> bool:
        """检查是否应该超时"""
        if not self.timeout or not self.start_time:
            return False
        
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        return elapsed > self.timeout
    
    def increment_retry(self) -> None:
        """增加重试计数"""
        self.retry_count += 1
        self.logger.info(f"任务重试: {self.task_name}", extra={
            "task_id": self.task_id,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        })
    
    def set_result(self, result: Any) -> None:
        """设置任务结果"""
        self.result = result
        self.set_status(TaskStatusEnum.SUCCESS)
        self.set_progress(100.0)
        
        self.logger.info(f"任务执行成功: {self.task_name}", extra={
            "task_id": self.task_id,
            "duration": self.duration
        })
    
    def set_error(self, error: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """设置任务错误"""
        self.error = error
        self.error_details = error_details or {}
        self.set_status(TaskStatusEnum.FAILED)
        
        self.logger.error(f"任务执行失败: {self.task_name}", extra={
            "task_id": self.task_id,
            "error": error,
            "error_details": self.error_details
        })
    
    def start_execution(self, worker_id: Optional[str] = None) -> None:
        """开始执行"""
        self.start_time = datetime.utcnow()
        self.worker_id = worker_id
        self.set_status(TaskStatusEnum.RUNNING)
        
        self.logger.info(f"任务开始执行: {self.task_name}", extra={
            "task_id": self.task_id,
            "worker_id": worker_id,
            "priority": self.priority.name
        })
    
    def finish_execution(self) -> None:
        """完成执行"""
        self.end_time = datetime.utcnow()
        
        if self.status == TaskStatusEnum.RUNNING:
            # 如果还在运行状态，标记为成功
            self.set_status(TaskStatusEnum.SUCCESS)
    
    def cancel(self, reason: str = "用户取消") -> bool:
        """取消任务"""
        if self.status in [TaskStatusEnum.PENDING, TaskStatusEnum.RUNNING]:
            self.set_status(TaskStatusEnum.CANCELLED)
            self.error = reason
            self.finish_execution()
            
            self.logger.info(f"任务已取消: {self.task_name}", extra={
                "task_id": self.task_id,
                "reason": reason
            })
            return True
        
        return False
    
    def timeout(self) -> None:
        """任务超时"""
        self.set_status(TaskStatusEnum.TIMEOUT)
        self.error = f"任务执行超时 ({self.timeout}秒)"
        self.finish_execution()
        
        self.logger.warning(f"任务执行超时: {self.task_name}", extra={
            "task_id": self.task_id,
            "timeout": self.timeout
        })
    
    def get_status_info(self) -> Dict[str, Any]:
        """获取任务状态信息"""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.progress,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "result": self.result,
            "error": self.error,
            "error_details": self.error_details,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "tags": self.tags,
            "worker_id": self.worker_id,
            "submitted_at": self.submitted_at.isoformat(),
            "metadata": self.metadata
        }
    
    def to_result(self) -> TaskResult:
        """转换为TaskResult对象"""
        return TaskResult(
            task_id=self.task_id,
            status=self.status,
            result=self.result,
            error=self.error,
            error_details=self.error_details,
            start_time=self.start_time,
            end_time=self.end_time,
            metadata=self.metadata,
            progress=self.progress
        )
    
    @property
    def duration(self) -> Optional[float]:
        """任务执行时长（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        elif self.start_time:
            return (datetime.utcnow() - self.start_time).total_seconds()
        return None
    
    @property
    def queue_time(self) -> float:
        """任务排队时长（秒）"""
        start_time = self.start_time or datetime.utcnow()
        return (start_time - self.submitted_at).total_seconds()
    
    @property
    def estimated_completion(self) -> Optional[datetime]:
        """预计完成时间"""
        if not self.start_time or not self.timeout:
            return None
        
        from datetime import timedelta
        return self.start_time + timedelta(seconds=self.timeout)
    
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
    
    def update_metadata(self, key: str, value: Any) -> None:
        """更新元数据"""
        self.metadata[key] = value
    
    def __lt__(self, other) -> bool:
        """优先级比较（用于优先队列）"""
        if isinstance(other, BaseTask):
            # 优先级数值越大优先级越高
            if self.priority.value != other.priority.value:
                return self.priority.value < other.priority.value
            # 优先级相同时，提交时间早的优先
            return self.submitted_at > other.submitted_at
        return NotImplemented
    
    def __str__(self) -> str:
        return f"Task({self.task_name}:{self.task_id[:8]})"
    
    def __repr__(self) -> str:
        return (f"BaseTask(id={self.task_id}, name={self.task_name}, "
                f"status={self.status.value}, priority={self.priority.name})")