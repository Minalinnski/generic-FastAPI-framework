# src/infrastructure/utils/string_utils.py
import hashlib
import random
import string
import uuid
from typing import List, Optional


class StringUtils:
    """字符串工具类"""
    
    @staticmethod
    def generate_random_string(length: int = 8, chars: str = None) -> str:
        """生成随机字符串"""
        if chars is None:
            chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    @staticmethod
    def generate_uuid() -> str:
        """生成UUID"""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_short_id(length: int = 8) -> str:
        """生成短ID"""
        chars = string.ascii_lowercase + string.digits
        return StringUtils.generate_random_string(length, chars)
    
    @staticmethod
    def hash_string(text: str, algorithm: str = "md5") -> str:
        """字符串哈希"""
        if algorithm == "md5":
            return hashlib.md5(text.encode()).hexdigest()
        elif algorithm == "sha256":
            return hashlib.sha256(text.encode()).hexdigest()
        elif algorithm == "sha1":
            return hashlib.sha1(text.encode()).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = "...") -> str:
        """截断字符串"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def camel_to_snake(name: str) -> str:
        """驼峰转下划线"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    @staticmethod
    def snake_to_camel(name: str) -> str:
        """下划线转驼峰"""
        components = name.split('_')
        return components[0] + ''.join(x.capitalize() for x in components[1:])
    
    @staticmethod
    def mask_sensitive_data(text: str, mask_char: str = "*", visible_chars: int = 4) -> str:
        """掩码敏感数据"""
        if len(text) <= visible_chars:
            return mask_char * len(text)
        
        visible_start = visible_chars // 2
        visible_end = visible_chars - visible_start
        
        masked_middle = mask_char * (len(text) - visible_chars)
        return text[:visible_start] + masked_middle + text[-visible_end:] if visible_end > 0 else text[:visible_start] + masked_middle
    
    @staticmethod
    def extract_numbers(text: str) -> List[float]:
        """提取字符串中的数字"""
        import re
        numbers = re.findall(r'-?\d+\.?\d*', text)
        return [float(num) for num in numbers if num]
    
    @staticmethod
    def is_json(text: str) -> bool:
        """检查字符串是否为有效JSON"""
        import json
        try:
            json.loads(text)
            return True
        except (ValueError, TypeError):
            return False