# app/main.py
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.api.middleware.logging_middleware import LoggingMiddleware
from app.api.v1.main_router import api_router
from app.application.config.settings import get_settings
from app.infrastructure.logging.logger import setup_logging, get_logger
from app.infrastructure.cache.task_result_cache import task_result_cache
from app.infrastructure.tasks.task_manager import task_manager

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
        "environment": settings.environment
    })
    
    try:
        # 初始化任务管理器
        logger.info("初始化任务管理器...")
        # task_manager 已经是全局实例，这里可以做额外的初始化
        
        # 初始化任务结果缓存
        logger.info("初始化任务结果缓存...")
        # task_result_cache 已经是全局实例
        
        # 设置应用状态
        app.state.task_manager = task_manager
        app.state.task_result_cache = task_result_cache
        app.state.settings = settings
        
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
        
        # 清理缓存统计
        cache_stats = task_result_cache.get_statistics()
        logger.info("任务结果缓存统计", extra=cache_stats)
        
        logger.info("应用关闭完成")
        
    except Exception as e:
        logger.error(f"应用关闭时出错: {str(e)}", exc_info=True)


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    settings = get_settings()
    
    # 创建应用实例
    app = FastAPI(
        title=settings.app_name,
        description="A scalable FastAPI framework following DDD principles",
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
        return {
            "message": f"欢迎使用 {settings.app_name}",
            "version": settings.app_version,
            "environment": settings.environment,
            "docs": f"{settings.api_prefix}/docs" if settings.docs_url else None,
            "health": f"{settings.api_prefix}/health"
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