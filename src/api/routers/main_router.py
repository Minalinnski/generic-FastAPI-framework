# src/api/v1/main_router.py
from fastapi import APIRouter

from src.api.routers.v1.system.health_router import router as health_router
from src.api.routers.v1.system.task_router import router as task_router
from src.api.routers.v1.foo_router import router as foo_router

# 创建API v1主路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(health_router)
api_router.include_router(task_router)
api_router.include_router(foo_router)

