# src/infrastructure/utils/dict_utils.py
from typing import Any, Dict, List, Optional, Union


class DictUtils:
    """字典工具类"""
    
    @staticmethod
    def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并字典"""
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = DictUtils.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def get_nested_value(data: Dict[str, Any], key_path: str, default: Any = None, separator: str = ".") -> Any:
        """获取嵌套字典的值"""
        keys = key_path.split(separator)
        current = data
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    @staticmethod
    def set_nested_value(data: Dict[str, Any], key_path: str, value: Any, separator: str = ".") -> None:
        """设置嵌套字典的值"""
        keys = key_path.split(separator)
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    @staticmethod
    def flatten_dict(data: Dict[str, Any], separator: str = ".", prefix: str = "") -> Dict[str, Any]:
        """扁平化字典"""
        result = {}
        
        for key, value in data.items():
            new_key = f"{prefix}{separator}{key}" if prefix else key
            
            if isinstance(value, dict):
                result.update(DictUtils.flatten_dict(value, separator, new_key))
            else:
                result[new_key] = value
        
        return result
    
    @staticmethod
    def unflatten_dict(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
        """反扁平化字典"""
        result = {}
        
        for key, value in data.items():
            DictUtils.set_nested_value(result, key, value, separator)
        
        return result
    
    @staticmethod
    def filter_dict(data: Dict[str, Any], keys: List[str], include: bool = True) -> Dict[str, Any]:
        """过滤字典"""
        if include:
            return {k: v for k, v in data.items() if k in keys}
        else:
            return {k: v for k, v in data.items() if k not in keys}
    
    @staticmethod
    def clean_dict(data: Dict[str, Any], remove_none: bool = True, remove_empty: bool = False) -> Dict[str, Any]:
        """清理字典"""
        result = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                cleaned_value = DictUtils.clean_dict(value, remove_none, remove_empty)
                if cleaned_value or not remove_empty:
                    result[key] = cleaned_value
            else:
                if remove_none and value is None:
                    continue
                if remove_empty and not value and value != 0 and value != False:
                    continue
                result[key] = value
        
        return result