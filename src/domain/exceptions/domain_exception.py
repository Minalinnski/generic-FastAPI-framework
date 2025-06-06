# domain/exceptions/domain_exceptions.py
from typing import Any, Dict, Optional

from src.domain.exceptions.base_exception import DomainException
from src.schemas.enums.base_enums import ErrorCodeEnum


class EntityNotFoundException(DomainException):
    """实体未找到异常"""
    
    def __init__(
        self, 
        entity_type: str, 
        entity_id: str, 
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"{entity_type} with ID '{entity_id}' not found"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.ENTITY_NOT_FOUND,
            details={
                **(details or {}), 
                "entity_type": entity_type, 
                "entity_id": entity_id
            }
        )


class EntityAlreadyExistsException(DomainException):
    """实体已存在异常"""
    
    def __init__(
        self, 
        entity_type: str, 
        identifier: str, 
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"{entity_type} with identifier '{identifier}' already exists"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.ENTITY_ALREADY_EXISTS,
            details={
                **(details or {}), 
                "entity_type": entity_type, 
                "identifier": identifier
            }
        )


class BusinessRuleViolationException(DomainException):
    """业务规则违反异常"""
    
    def __init__(
        self, 
        rule_name: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.BUSINESS_RULE_VIOLATION,
            details={
                **(details or {}), 
                "rule_name": rule_name
            }
        )


class InvalidOperationException(DomainException):
    """无效操作异常"""
    
    def __init__(
        self, 
        operation: str, 
        reason: str, 
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Invalid operation '{operation}': {reason}"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.INVALID_OPERATION,
            details={
                **(details or {}), 
                "operation": operation, 
                "reason": reason
            }
        )


class DomainValidationException(DomainException):
    """领域验证异常"""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any, 
        validation_rule: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Validation failed for field '{field_name}': {validation_rule}"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.VALIDATION_ERROR,
            details={
                **(details or {}),
                "field_name": field_name,
                "field_value": field_value,
                "validation_rule": validation_rule
            }
        )


class ConcurrencyException(DomainException):
    """并发控制异常"""
    
    def __init__(
        self, 
        entity_type: str, 
        entity_id: str, 
        expected_version: int, 
        actual_version: int,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Concurrency conflict for {entity_type} '{entity_id}': expected version {expected_version}, but was {actual_version}"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.CONFLICT,
            details={
                **(details or {}),
                "entity_type": entity_type,
                "entity_id": entity_id,
                "expected_version": expected_version,
                "actual_version": actual_version
            }
        )


class InvariantViolationException(DomainException):
    """不变量违反异常"""
    
    def __init__(
        self, 
        invariant_name: str, 
        description: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Invariant violation '{invariant_name}': {description}"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.BUSINESS_RULE_VIOLATION,
            details={
                **(details or {}),
                "invariant_name": invariant_name,
                "description": description
            }
        )


class AggregateNotFoundException(EntityNotFoundException):
    """聚合根未找到异常"""
    
    def __init__(
        self, 
        aggregate_type: str, 
        aggregate_id: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            entity_type=f"{aggregate_type} Aggregate",
            entity_id=aggregate_id,
            details=details
        )


class DomainEventException(DomainException):
    """领域事件异常"""
    
    def __init__(
        self, 
        event_type: str, 
        event_id: str, 
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Domain event '{event_type}' (ID: {event_id}) failed: {reason}"
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.INVALID_OPERATION,
            details={
                **(details or {}),
                "event_type": event_type,
                "event_id": event_id,
                "reason": reason
            }
        )