# schemas/dtos/response/health_response.py
from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class HealthData(BaseModel):
    """健康检查数据"""
    status: str = Field(..., description="服务状态")
    timestamp: datetime = Field(..., description="检查时间")
    version: str = Field(..., description="服务版本")
    uptime: Optional[float] = Field(None, description="运行时间（秒）")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="依赖服务状态")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-01T00:00:00Z",
                "version": "1.0.0",
                "uptime": 3600.0,
                "dependencies": {
                    "database": "healthy",
                    "cache": "healthy",
                    "s3": "healthy"
                }
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应DTO"""
    data: HealthData
    error: Optional[str] = None
    error_message: Optional[str] = None
    success: bool = True