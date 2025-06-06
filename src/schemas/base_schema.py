# src/schemas/base_schema.py
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    """基础Schema类"""
    
    class Config:
        use_enum_values = True
        validate_assignment = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TimestampMixin(BaseModel):
    """时间戳混入"""
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class MetadataMixin(BaseModel):
    """元数据混入"""
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")