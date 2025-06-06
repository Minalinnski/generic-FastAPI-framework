# src/main.py (更新版)
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.error_handler import ErrorHandlerMiddleware
from src.api.middleware.logging_middleware import LoggingMiddleware
from src.api.v1.main_router import api_router
from src.application.config.settings import get_settings
from src.infrastructure.logging.logger import setup_logging, get_logger
from src.infrastructure.tasks.task_manager import task_manager

# 初始化日志
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    
    # 启动时初始化
    logger.info("应用启动中...", extra={
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "task_storage_s3_enabled": settings.task_enable_s3_storage and bool(settings.s3_bucket)
    })
    
    try:
        # 启动任务管理器
        logger.info("启动任务管理器...")
        await task_manager.start()
        
        # 设置应用状态
        app.state.task_manager = task_manager
        app.state.settings = settings
        
        # 记录任务系统配置
        task_config = settings.get_service_config("task")
        logger.info("任务系统配置", extra=task_config)
        
        logger.info("应用启动完成")
        
    except Exception as e:
        logger.error(f"应用启动失败: {str(e)}", exc_info=True)
        raise
    
    yield
    
    # 关闭时清理
    logger.info("应用关闭中...")
    
    try:
        # 关闭任务管理器
        await task_manager.shutdown()
        
        # 获取最终统计信息
        storage_stats = task_manager.storage.get_storage_statistics()
        worker_stats = task_manager.worker_pool.get_statistics()
        
        logger.info("任务系统关闭完成", extra={
            "storage_stats": storage_stats,
            "worker_stats": worker_stats["current_state"]
        })
        
        logger.info("应用关闭完成")
        
    except Exception as e:
        logger.error(f"应用关闭时出错: {str(e)}", exc_info=True)


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    settings = get_settings()
    
    # 创建应用实例
    app = FastAPI(
        title=settings.app_name,
        description="A scalable FastAPI framework following DDD principles with advanced task management",
        version=settings.app_version,
        docs_url=settings.docs_url if not settings.is_production else None,
        redoc_url=settings.redoc_url if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=settings.allow_methods,
        allow_headers=settings.allow_headers,
    )
    
    # 添加自定义中间件
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(LoggingMiddleware)
    
    # 注册路由
    app.include_router(api_router, prefix=settings.api_prefix)
    
    # 根路径处理
    @app.get("/", tags=["root"])
    async def root():
        """API根路径"""
        task_config = settings.task_storage_config
        
        return {
            "message": f"欢迎使用 {settings.app_name}",
            "version": settings.app_version,
            "environment": settings.environment,
            "docs": f"{settings.api_prefix}/docs" if settings.docs_url else None,
            "health": f"{settings.api_prefix}/health",
            "features": {
                "task_system": "enabled",
                "s3_storage": task_config["enable_s3_storage"],
                "callback_support": "per_service",
                "worker_scaling": "dynamic"
            }
        }
    
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    # 运行配置
    uvicorn_config = {
        "host": settings.host,
        "port": settings.port,
        "reload": settings.reload and settings.is_development,
        "log_config": None,  # 使用自定义日志配置
        "access_log": False,  # 禁用默认访问日志，使用自定义中间件
    }
    
    logger.info("启动服务器", extra=uvicorn_config)
    
    uvicorn.run("app.main:app", **uvicorn_config)