# domain/exceptions/base_exception.py
from typing import Any, Dict, Optional

from src.schemas.enums.base_enums import ErrorCodeEnum

class DomainException(Exception):
    """领域异常基类"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = ErrorCodeEnum.DOMAIN_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }
    
    def __str__(self) -> str:
        return f"{self.error_code}: {self.message}"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(error_code='{self.error_code}', message='{self.message}')"


class BusinessRuleViolationException(DomainException):
    """业务规则违反异常"""
    
    def __init__(self, message: str, rule_name: str = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.BUSINESS_RULE_VIOLATION,
            details={**(details or {}), "rule_name": rule_name}
        )


class EntityNotFoundException(DomainException):
    """实体未找到异常"""
    
    def __init__(self, entity_type: str, entity_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"{entity_type} with ID '{entity_id}' not found"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.ENTITY_NOT_FOUND,
            details={**(details or {}), "entity_type": entity_type, "entity_id": entity_id}
        )


class EntityAlreadyExistsException(DomainException):
    """实体已存在异常"""
    
    def __init__(self, entity_type: str, identifier: str, details: Optional[Dict[str, Any]] = None):
        message = f"{entity_type} with identifier '{identifier}' already exists"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.ENTITY_ALREADY_EXISTS,
            details={**(details or {}), "entity_type": entity_type, "identifier": identifier}
        )


class InvalidOperationException(DomainException):
    """无效操作异常"""
    
    def __init__(self, operation: str, reason: str, details: Optional[Dict[str, Any]] = None):
        message = f"Invalid operation '{operation}': {reason}"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.INVALID_OPERATION,
            details={**(details or {}), "operation": operation, "reason": reason}
        )