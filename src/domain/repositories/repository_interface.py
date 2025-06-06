# domain/repositories/repository_interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar

from src.domain.entities.base_entity import BaseEntity

# 泛型类型变量
T = TypeVar('T', bound=BaseEntity)


class RepositoryInterface(ABC, Generic[T]):
    """仓储接口，定义数据访问的抽象"""
    
    @abstractmethod
    async def save(self, entity: T) -> T:
        """保存实体"""
        pass
    
    @abstractmethod
    async def find_by_id(self, entity_id: str) -> Optional[T]:
        """根据ID查找实体"""
        pass
    
    @abstractmethod
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """查找所有实体"""
        pass
    
    @abstractmethod
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """根据条件查找实体"""
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> T:
        """更新实体"""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """删除实体"""
        pass
    
    @abstractmethod
    async def exists(self, entity_id: str) -> bool:
        """检查实体是否存在"""
        pass
    
    @abstractmethod
    async def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """统计实体数量"""
        pass
    
    # 同步版本的方法
    @abstractmethod
    def save_sync(self, entity: T) -> T:
        """同步保存实体"""
        pass
    
    @abstractmethod
    def find_by_id_sync(self, entity_id: str) -> Optional[T]:
        """同步根据ID查找实体"""
        pass
    
    @abstractmethod
    def find_all_sync(self, limit: int = 100, offset: int = 0) -> List[T]:
        """同步查找所有实体"""
        pass
    
    @abstractmethod
    def update_sync(self, entity: T) -> T:
        """同步更新实体"""
        pass
    
    @abstractmethod
    def delete_sync(self, entity_id: str) -> bool:
        """同步删除实体"""
        pass