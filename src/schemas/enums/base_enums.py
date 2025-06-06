# src/schemas/enums/base_enums.py
from enum import Enum


class BaseEnum(str, Enum):
    """基础枚举类，继承str使其可以直接序列化为字符串"""
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def list_values(cls) -> list[str]:
        """获取所有枚举值列表"""
        return [item.value for item in cls]
    
    @classmethod
    def has_value(cls, value: str) -> bool:
        """检查值是否存在于枚举中"""
        return value in cls.list_values()


class TaskStatusEnum(BaseEnum):
    """任务状态枚举"""
    PENDING = "pending"         # 待执行
    RUNNING = "running"         # 执行中
    SUCCESS = "success"         # 执行成功
    FAILED = "failed"          # 执行失败
    CANCELLED = "cancelled"    # 已取消
    TIMEOUT = "timeout"        # 执行超时


class TaskTypeEnum(BaseEnum):
    """任务类型枚举"""
    SYNC = "sync"              # 同步任务
    ASYNC = "async"            # 异步任务


class LogLevelEnum(BaseEnum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCodeEnum(BaseEnum):
    """错误代码枚举"""
    # 通用错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    
    # 验证错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    
    # 业务错误
    DOMAIN_ERROR = "DOMAIN_ERROR"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    ENTITY_ALREADY_EXISTS = "ENTITY_ALREADY_EXISTS"
    INVALID_OPERATION = "INVALID_OPERATION"
    
    # 系统错误
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class EnvironmentEnum(BaseEnum):
    """环境枚举"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"