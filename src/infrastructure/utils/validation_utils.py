# src/infrastructure/utils/validation_utils.py  
import re
import uuid
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse


class ValidationUtils:
    """验证工具类"""
    
    # 正则表达式模式
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^\+?1?[0-9]{10,15}$')
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    
    @staticmethod
    def is_email(email: str) -> bool:
        """验证邮箱格式"""
        if not email or not isinstance(email, str):
            return False
        return bool(ValidationUtils.EMAIL_PATTERN.match(email.strip()))
    
    @staticmethod
    def is_uuid(value: str) -> bool:
        """验证UUID格式"""
        if not value or not isinstance(value, str):
            return False
        return bool(ValidationUtils.UUID_PATTERN.match(value))
    
    @staticmethod
    def is_not_empty(value: Any) -> bool:
        """验证值不为空"""
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, dict, tuple)):
            return len(value) > 0
        return True
    
    @staticmethod
    def is_length_valid(value: str, min_length: int = None, max_length: int = None) -> bool:
        """验证字符串长度"""
        if not isinstance(value, str):
            return False
        
        length = len(value)
        if min_length is not None and length < min_length:
            return False
        if max_length is not None and length > max_length:
            return False
        return True
    
    @staticmethod
    def is_numeric(value: Any) -> bool:
        """验证是否为数字"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_in_range(value: Union[int, float], min_value: Union[int, float] = None, max_value: Union[int, float] = None) -> bool:
        """验证数值是否在范围内"""
        try:
            num_value = float(value)
            if min_value is not None and num_value < min_value:
                return False
            if max_value is not None and num_value > max_value:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名"""
        if not filename:
            return "unnamed_file"
        
        # 替换危险字符
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # 移除控制字符
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # 限制长度
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            filename = name[:max_name_length] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def validate_json_schema(data: Dict[str, Any], required_fields: List[str] = None, optional_fields: List[str] = None) -> Dict[str, List[str]]:
        """验证JSON数据结构"""
        errors = {"missing": [], "unexpected": []}
        
        if required_fields:
            for field in required_fields:
                if field not in data:
                    errors["missing"].append(field)
        
        if optional_fields is not None:
            allowed_fields = set((required_fields or []) + optional_fields)
            for field in data.keys():
                if field not in allowed_fields:
                    errors["unexpected"].append(field)
        
        return errors


class ValidatorChain:
    """验证器链"""
    
    def __init__(self):
        self.validators = []
        self.errors = []
    
    def add_validator(self, validator_func, error_message: str, *args, **kwargs):
        """添加验证器"""
        self.validators.append((validator_func, error_message, args, kwargs))
        return self
    
    def validate(self, value: Any) -> bool:
        """执行验证"""
        self.errors = []
        for validator_func, error_message, args, kwargs in self.validators:
            if not validator_func(value, *args, **kwargs):
                self.errors.append(error_message)
        
        return len(self.errors) == 0
    
    def get_errors(self) -> List[str]:
        """获取错误列表"""
        return self.errors
