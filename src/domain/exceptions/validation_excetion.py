# domain/exceptions/validation_exceptions.py
from typing import Any, Dict, List, Optional

from src.domain.exceptions.base_exception import DomainException
from src.schemas.enums.base_enums import ErrorCodeEnum


class ValidationException(DomainException):
    """验证异常基类"""
    
    def __init__(
        self, 
        message: str,
        field_name: str = None,
        field_value: Any = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.VALIDATION_ERROR,
            details={
                **(details or {}),
                "field_name": field_name,
                "field_value": field_value
            }
        )


class RequiredFieldException(ValidationException):
    """必填字段异常"""
    
    def __init__(self, field_name: str, details: Optional[Dict[str, Any]] = None):
        message = f"Required field '{field_name}' is missing"
        super().__init__(
            message=message,
            field_name=field_name,
            field_value=None,
            details=details
        )


class InvalidFormatException(ValidationException):
    """格式无效异常"""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any, 
        expected_format: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Field '{field_name}' has invalid format. Expected: {expected_format}"
        super().__init__(
            message=message,
            field_name=field_name,
            field_value=field_value,
            details={**(details or {}), "expected_format": expected_format}
        )


class ValueOutOfRangeException(ValidationException):
    """值超出范围异常"""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any, 
        min_value: Any = None, 
        max_value: Any = None,
        details: Optional[Dict[str, Any]] = None
    ):
        range_str = ""
        if min_value is not None and max_value is not None:
            range_str = f"between {min_value} and {max_value}"
        elif min_value is not None:
            range_str = f"greater than or equal to {min_value}"
        elif max_value is not None:
            range_str = f"less than or equal to {max_value}"
        
        message = f"Field '{field_name}' value '{field_value}' is out of range. Expected: {range_str}"
        super().__init__(
            message=message,
            field_name=field_name,
            field_value=field_value,
            details={
                **(details or {}), 
                "min_value": min_value, 
                "max_value": max_value
            }
        )


class InvalidLengthException(ValidationException):
    """长度无效异常"""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any, 
        actual_length: int,
        min_length: int = None, 
        max_length: int = None,
        details: Optional[Dict[str, Any]] = None
    ):
        length_str = ""
        if min_length is not None and max_length is not None:
            length_str = f"between {min_length} and {max_length}"
        elif min_length is not None:
            length_str = f"at least {min_length}"
        elif max_length is not None:
            length_str = f"at most {max_length}"
        
        message = f"Field '{field_name}' length {actual_length} is invalid. Expected: {length_str}"
        super().__init__(
            message=message,
            field_name=field_name,
            field_value=field_value,
            details={
                **(details or {}),
                "actual_length": actual_length,
                "min_length": min_length,
                "max_length": max_length
            }
        )


class InvalidChoiceException(ValidationException):
    """选择无效异常"""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any, 
        valid_choices: List[Any],
        details: Optional[Dict[str, Any]] = None
    ):
        choices_str = ", ".join(str(choice) for choice in valid_choices)
        message = f"Field '{field_name}' value '{field_value}' is not a valid choice. Valid choices: {choices_str}"
        super().__init__(
            message=message,
            field_name=field_name,
            field_value=field_value,
            details={**(details or {}), "valid_choices": valid_choices}
        )


class DuplicateValueException(ValidationException):
    """重复值异常"""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Field '{field_name}' value '{field_value}' already exists"
        super().__init__(
            message=message,
            field_name=field_name,
            field_value=field_value,
            details=details
        )


class MultipleValidationException(DomainException):
    """多重验证异常"""
    
    def __init__(
        self, 
        validation_errors: List[ValidationException],
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Multiple validation errors occurred: {len(validation_errors)} errors"
        
        error_details = []
        for error in validation_errors:
            error_details.append({
                "field_name": error.details.get("field_name"),
                "message": error.message,
                "field_value": error.details.get("field_value")
            })
        
        super().__init__(
            message=message,
            error_code=ErrorCodeEnum.VALIDATION_ERROR,
            details={
                **(details or {}),
                "validation_errors": error_details,
                "error_count": len(validation_errors)
            }
        )
        
        self.validation_errors = validation_errors
    
    def get_field_errors(self) -> Dict[str, str]:
        """获取字段错误映射"""
        field_errors = {}
        for error in self.validation_errors:
            field_name = error.details.get("field_name")
            if field_name:
                field_errors[field_name] = error.message
        return field_errors


class ConditionalValidationException(ValidationException):
    """条件验证异常"""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any, 
        condition: str, 
        dependent_field: str = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Field '{field_name}' validation failed under condition: {condition}"
        if dependent_field:
            message += f" (depends on field '{dependent_field}')"
        
        super().__init__(
            message=message,
            field_name=field_name,
            field_value=field_value,
            details={
                **(details or {}),
                "condition": condition,
                "dependent_field": dependent_field
            }
        )