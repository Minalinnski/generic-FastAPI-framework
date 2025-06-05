# app/infrastructure/tasks/task_registry.py
import asyncio
import inspect
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.tasks.base_task import BaseTask
from app.infrastructure.tasks.generic_task import TaskFactory, ServiceTask

logger = get_logger(__name__)


class TaskRegistry:
    """
    任务注册表
    
    功能：
    1. 注册和管理任务类型
    2. 支持自定义任务类和服务函数
    3. 提供任务创建的工厂方法
    4. 任务元数据管理
    5. 任务分类和搜索
    """
    
    def __init__(self):
        self.logger = logger
        
        # 注册的自定义任务类
        self._custom_tasks: Dict[str, Type[BaseTask]] = {}
        
        # 注册的服务函数
        self._service_functions: Dict[str, Callable] = {}
        
        # 任务元数据
        self._task_metadata: Dict[str, Dict[str, Any]] = {}
        
        # 任务分类
        self._task_categories: Dict[str, List[str]] = {}
    
    def register_custom_task(
        self, 
        task_name: str, 
        task_class: Type[BaseTask],
        category: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """注册自定义任务类"""
        if not issubclass(task_class, BaseTask):
            raise ValueError(f"任务类 {task_class} 必须继承自 BaseTask")
        
        if task_name in self._custom_tasks or task_name in self._service_functions:
            raise ValueError(f"任务名称 '{task_name}' 已存在")
        
        self._custom_tasks[task_name] = task_class
        
        # 保存元数据
        self._task_metadata[task_name] = {
            "type": "custom_class",
            "class_name": task_class.__name__,
            "module": task_class.__module__,
            "description": description or task_class.__doc__ or "无描述",
            "category": category or "custom",
            "tags": tags or [],
            "registered_at": datetime.utcnow().isoformat()
        }
        
        # 添加到分类
        category = category or "custom"
        if category not in self._task_categories:
            self._task_categories[category] = []
        self._task_categories[category].append(task_name)
        
        self.logger.info(f"已注册自定义任务类: {task_name}", extra={
            "task_name": task_name,
            "class_name": task_class.__name__,
            "category": category
        })
    
    def register_service_function(
        self, 
        task_name: str, 
        service_func: Callable,
        category: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """注册服务函数为任务"""
        if task_name in self._custom_tasks or task_name in self._service_functions:
            raise ValueError(f"任务名称 '{task_name}' 已存在")
        
        self._service_functions[task_name] = service_func
        
        # 获取函数签名信息
        sig = inspect.signature(service_func)
        params_info = {}
        for param_name, param in sig.parameters.items():
            params_info[param_name] = {
                "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                "default": str(param.default) if param.default != inspect.Parameter.empty else None,
                "required": param.default == inspect.Parameter.empty
            }
        
        # 保存元数据
        self._task_metadata[task_name] = {
            "type": "service_function",
            "function_name": service_func.__name__,
            "module": service_func.__module__,
            "description": description or service_func.__doc__ or "无描述",
            "category": category or "service",
            "tags": tags or [],
            "is_async": asyncio.iscoroutinefunction(service_func),
            "parameters": params_info,
            "return_annotation": str(sig.return_annotation) if sig.return_annotation != inspect.Parameter.empty else "Any",
            "registered_at": datetime.utcnow().isoformat()
        }
        
        # 添加到分类
        category = category or "service"
        if category not in self._task_categories:
            self._task_categories[category] = []
        self._task_categories[category].append(task_name)
        
        self.logger.info(f"已注册服务函数任务: {task_name}", extra={
            "task_name": task_name,
            "function_name": service_func.__name__,
            "category": category,
            "is_async": asyncio.iscoroutinefunction(service_func)
        })
    
    def create_task(
        self, 
        task_name: str, 
        task_options: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Optional[BaseTask]:
        """创建任务实例"""
        task_options = task_options or {}
        
        # 优先检查自定义任务类
        if task_name in self._custom_tasks:
            task_class = self._custom_tasks[task_name]
            try:
                return task_class(**task_options, **kwargs)
            except Exception as e:
                self.logger.error(f"创建自定义任务失败: {task_name}", extra={
                    "error": str(e),
                    "task_class": task_class.__name__
                })
                raise
        
        # 检查服务函数任务
        if task_name in self._service_functions:
            service_func = self._service_functions[task_name]
            try:
                return TaskFactory.create_service_task(
                    service_func=service_func,
                    task_name=task_name,
                    **task_options,
                    **kwargs
                )
            except Exception as e:
                self.logger.error(f"创建服务函数任务失败: {task_name}", extra={
                    "error": str(e),
                    "function_name": service_func.__name__
                })
                raise
        
        self.logger.warning(f"未找到任务: {task_name}")
        return None
    
    def get_registered_tasks(self) -> Dict[str, str]:
        """获取已注册的任务列表"""
        tasks = {}
        
        # 自定义任务类
        for name, task_class in self._custom_tasks.items():
            tasks[name] = f"custom_class:{task_class.__name__}"
        
        # 服务函数任务
        for name, func in self._service_functions.items():
            tasks[name] = f"service_function:{func.__name__}"
        
        return tasks
    
    def get_task_info(self, task_name: str) -> Optional[Dict[str, Any]]:
        """获取任务详细信息"""
        return self._task_metadata.get(task_name)
    
    def get_tasks_by_category(self, category: str) -> List[str]:
        """根据分类获取任务列表"""
        return self._task_categories.get(category, [])
    
    def get_all_categories(self) -> Dict[str, List[str]]:
        """获取所有分类"""
        return self._task_categories.copy()
    
    def search_tasks(
        self, 
        query: str, 
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """搜索任务"""
        results = []
        
        for task_name, metadata in self._task_metadata.items():
            # 分类过滤
            if category and metadata.get("category") != category:
                continue
            
            # 标签过滤
            if tags:
                task_tags = metadata.get("tags", [])
                if not any(tag in task_tags for tag in tags):
                    continue
            
            # 文本搜索
            searchable_text = f"{task_name} {metadata.get('description', '')} {metadata.get('function_name', '')}".lower()
            if query.lower() in searchable_text:
                results.append({
                    "task_name": task_name,
                    **metadata
                })
        
        return results
    
    def unregister_task(self, task_name: str) -> bool:
        """注销任务"""
        removed = False
        
        if task_name in self._custom_tasks:
            del self._custom_tasks[task_name]
            removed = True
        
        if task_name in self._service_functions:
            del self._service_functions[task_name]
            removed = True
        
        if task_name in self._task_metadata:
            metadata = self._task_metadata[task_name]
            category = metadata.get("category")
            if category and category in self._task_categories:
                if task_name in self._task_categories[category]:
                    self._task_categories[category].remove(task_name)
                # 如果分类为空，删除分类
                if not self._task_categories[category]:
                    del self._task_categories[category]
            
            del self._task_metadata[task_name]
        
        if removed:
            self.logger.info(f"已注销任务: {task_name}")
        else:
            self.logger.warning(f"未找到要注销的任务: {task_name}")
        
        return removed
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        total_tasks = len(self._custom_tasks) + len(self._service_functions)
        
        # 按类型统计
        type_stats = {
            "custom_classes": len(self._custom_tasks),
            "service_functions": len(self._service_functions)
        }
        
        # 按分类统计
        category_stats = {
            category: len(tasks) 
            for category, tasks in self._task_categories.items()
        }
        
        # 按是否异步统计
        async_count = 0
        sync_count = 0
        for metadata in self._task_metadata.values():
            if metadata.get("is_async", False):
                async_count += 1
            else:
                sync_count += 1
        
        return {
            "total_tasks": total_tasks,
            "types": type_stats,
            "categories": category_stats,
            "async_tasks": async_count,
            "sync_tasks": sync_count,
            "category_count": len(self._task_categories)
        }
    
    def list_task_names(self) -> List[str]:
        """列出所有任务名称"""
        return list(self._custom_tasks.keys()) + list(self._service_functions.keys())
    
    def validate_task_params(self, task_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """验证任务参数"""
        metadata = self.get_task_info(task_name)
        if not metadata:
            raise ValueError(f"任务 '{task_name}' 不存在")
        
        # 对于服务函数，验证参数
        if metadata["type"] == "service_function":
            function_params = metadata.get("parameters", {})
            validated_params = {}
            missing_required = []
            
            # 检查必需参数
            for param_name, param_info in function_params.items():
                if param_info["required"] and param_name not in params:
                    missing_required.append(param_name)
                elif param_name in params:
                    validated_params[param_name] = params[param_name]
            
            if missing_required:
                raise ValueError(f"缺少必需参数: {missing_required}")
            
            # 添加额外参数（允许额外参数用于灵活性）
            for param_name, param_value in params.items():
                if param_name not in validated_params:
                    validated_params[param_name] = param_value
            
            return validated_params
        
        # 对于自定义任务类，直接返回参数
        return params
    
    def get_task_usage_stats(self, task_name: str) -> Dict[str, Any]:
        """获取任务使用统计（需要结合任务管理器）"""
        # 这里返回基础信息，具体使用统计需要任务管理器提供
        metadata = self.get_task_info(task_name)
        if not metadata:
            return {}
        
        return {
            "task_name": task_name,
            "registered_at": metadata.get("registered_at"),
            "category": metadata.get("category"),
            "type": metadata.get("type"),
            "description": metadata.get("description")
        }
    
    def export_registry(self) -> Dict[str, Any]:
        """导出注册表配置（用于备份或迁移）"""
        return {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "custom_tasks": {
                name: {
                    "class_name": task_class.__name__,
                    "module": task_class.__module__,
                    "metadata": self._task_metadata.get(name, {})
                }
                for name, task_class in self._custom_tasks.items()
            },
            "service_functions": {
                name: {
                    "function_name": func.__name__,
                    "module": func.__module__,
                    "metadata": self._task_metadata.get(name, {})
                }
                for name, func in self._service_functions.items()
            },
            "categories": self._task_categories,
            "stats": self.get_registry_stats()
        }
    
    def clear_registry(self) -> None:
        """清空注册表（谨慎使用）"""
        self.logger.warning("清空任务注册表")
        self._custom_tasks.clear()
        self._service_functions.clear()
        self._task_metadata.clear()
        self._task_categories.clear()


# 便捷装饰器
def register_service_as_task(
    task_name: str,
    category: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None
):
    """装饰器：将服务方法注册为任务"""
    def decorator(service_func: Callable):
        task_registry.register_service_function(
            task_name=task_name,
            service_func=service_func,
            category=category,
            description=description,
            tags=tags
        )
        return service_func
    return decorator


def register_custom_task_class(
    task_name: str,
    category: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None
):
    """装饰器：注册自定义任务类"""
    def decorator(task_class: Type[BaseTask]):
        task_registry.register_custom_task(
            task_name=task_name,
            task_class=task_class,
            category=category,
            description=description,
            tags=tags
        )
        return task_class
    return decorator


# 全局任务注册表实例
task_registry = TaskRegistry()