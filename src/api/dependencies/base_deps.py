# src/api/dependencies/base_deps.py
from typing import Generator, Optional

from fastapi import Depends, HTTPException, Request, status

from src.application.config.settings import get_settings
from src.infrastructure.cache.cache_interface import CacheInterface, InMemoryCache

settings = get_settings()


def get_request_id(request: Request) -> str:
    """获取请求ID"""
    return getattr(request.state, "request_id", "unknown")


def get_cache() -> Generator[CacheInterface, None, None]:
    """获取缓存实例"""
    cache = InMemoryCache(
        max_size=settings.cache_max_size,
        default_ttl=settings.cache_default_ttl
    )
    try:
        yield cache
    finally:
        # 这里可以添加清理逻辑
        pass


def get_current_user_id(request: Request) -> str:
    """获取当前用户ID（示例实现）"""
    # 这里应该从JWT token或session中获取用户ID
    # 目前只是示例实现
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        return "anonymous"
    return user_id


def verify_api_key(request: Request) -> bool:
    """验证API密钥（示例实现）"""
    # 如果在生产环境且没有配置认证，跳过验证
    if settings.is_production and not settings.jwt_secret_key:
        return True
    
    api_key = request.headers.get("X-API-Key")
    if not api_key and not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required"
        )
    
    # 开发环境允许无API密钥访问
    if settings.is_development and not api_key:
        return True
    
    # TODO: 实现真实的API密钥验证逻辑
    valid_api_keys = ["demo-api-key-123", "test-api-key-456"]
    if api_key not in valid_api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return True


def get_pagination_params(
    page: int = 1,
    size: int = 20,
    max_size: Optional[int] = None
) -> dict:
    """获取分页参数"""
    max_page_size = max_size or 100
    
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be greater than 0"
        )
    
    if size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Size must be greater than 0"
        )
    
    if size > max_page_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Size must not exceed {max_page_size}"
        )
    
    offset = (page - 1) * size
    return {
        "page": page,
        "size": size,
        "offset": offset,
        "limit": size
    }


class CommonDependencies:
    """常用依赖注入的封装类"""
    
    def __init__(
        self,
        request_id: str = Depends(get_request_id),
        cache: CacheInterface = Depends(get_cache),
        user_id: str = Depends(get_current_user_id),
        pagination: dict = Depends(get_pagination_params)
    ):
        self.request_id = request_id
        self.cache = cache
        self.user_id = user_id
        self.pagination = pagination


def get_service_dependencies() -> dict:
    """获取服务层依赖"""
    return {
        "settings": settings,
        "cache": InMemoryCache(
            max_size=settings.cache_max_size,
            default_ttl=settings.cache_default_ttl
        )
    }