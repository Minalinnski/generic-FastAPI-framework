# src/application/config/settings.py (更新版)
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类 - 支持环境变量、YAML配置文件和默认值"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore"
    )
    
    # === 核心应用设置 ===
    app_name: str = Field(default="FastAPI DDD Framework")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")
    
    # === 服务器设置 ===
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    reload: bool = Field(default=False)
    
    # === API设置 ===
    api_prefix: str = Field(default="/api/v1")
    docs_url: Optional[str] = Field(default="/docs")
    redoc_url: Optional[str] = Field(default="/redoc")
    
    # === CORS设置 ===
    allowed_origins: List[str] = Field(default=["*"])
    allow_credentials: bool = Field(default=True)
    allow_methods: List[str] = Field(default=["*"])
    allow_headers: List[str] = Field(default=["*"])
    
    # === 日志设置 ===
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console")  # json or console
    log_sql: bool = Field(default=False)
    
    # === 安全设置 ===
    jwt_secret_key: Optional[str] = Field(default=None)
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=30)
    
    # === AWS设置 ===
    aws_region: Optional[str] = Field(default=None)
    aws_access_key_id: Optional[str] = Field(default=None)
    aws_secret_access_key: Optional[str] = Field(default=None)
    s3_bucket: Optional[str] = Field(default=None)
    
    # === 数据库设置 ===
    database_url: Optional[str] = Field(default=None)
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)
    database_pool_timeout: int = Field(default=30)
    database_pool_recycle: int = Field(default=3600)
    
    # === Redis设置 ===
    redis_url: Optional[str] = Field(default=None)
    redis_host: Optional[str] = Field(default="localhost")
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_db: int = Field(default=0, ge=0, le=15)
    redis_password: Optional[str] = Field(default=None)
    
    # === 通用缓存设置 ===
    cache_default_ttl: int = Field(default=3600, ge=0)
    cache_key_prefix: str = Field(default="app:")
    cache_max_size: int = Field(default=10000, ge=1)
    
    # === 任务系统设置 ===
    task_max_workers: int = Field(default=4, ge=1, le=100)
    task_retry_attempts: int = Field(default=3, ge=0, le=10)
    task_retry_delay: int = Field(default=5, ge=1)
    
    # === 任务存储设置 ===
    task_result_cache_size: int = Field(default=1000, ge=1)
    task_result_cache_ttl: int = Field(default=7200, ge=0)
    task_enable_s3_storage: bool = Field(default=True)  # 新增：S3存储开关
    task_s3_persist_threshold_kb: int = Field(default=10, ge=1)  # 新增：S3持久化阈值
    task_s3_persist_long_tasks: bool = Field(default=True)  # 新增：长时间任务自动持久化
    
    # === 任务调度设置 ===
    task_scheduler_interval: float = Field(default=0.1, ge=0.01, le=1.0)  # 新增：调度间隔
    task_cleanup_interval: int = Field(default=3600, ge=60)  # 新增：清理间隔
    task_max_history_hours: int = Field(default=168, ge=1)  # 新增：历史保留时间（7天）
    
    # === 限流设置 ===
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=100, ge=1)
    rate_limit_burst_size: int = Field(default=20, ge=1)
    
    # === 服务配置 ===
    health_check_timeout: int = Field(default=5, ge=1)
    health_dependencies: List[str] = Field(default=["cache"])
    
    # === 监控设置 ===
    enable_metrics: bool = Field(default=True)
    enable_tracing: bool = Field(default=True)
    tracing_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # === 通知设置 ===
    slack_webhook_url: Optional[str] = Field(default=None)
    slack_channel: Optional[str] = Field(default=None)
    slack_enabled: bool = Field(default=False)

    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    @validator("log_format")
    def validate_log_format(cls, v: str) -> str:
        valid_formats = ["json", "console"]
        if v.lower() not in valid_formats:
            raise ValueError(f"log_format must be one of {valid_formats}")
        return v.lower()

    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        valid_envs = ["development", "testing", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        return v.lower()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_config_files()

    def _load_config_files(self) -> None:
        """加载YAML配置文件"""
        config_dir = Path(__file__).parent
        
        # 加载核心配置
        core_config_path = config_dir / "core_config.yaml"
        if core_config_path.exists():
            with open(core_config_path, "r", encoding="utf-8") as f:
                core_config = yaml.safe_load(f)
                self._update_from_nested_dict(core_config)
        
        # 加载业务配置
        service_config_path = config_dir / "service_config.yaml"
        if service_config_path.exists():
            with open(service_config_path, "r", encoding="utf-8") as f:
                service_config = yaml.safe_load(f)
                self._update_from_nested_dict(service_config)

    def _update_from_nested_dict(self, config_dict: Dict[str, Any], prefix: str = "") -> None:
        """从嵌套字典更新配置"""
        for key, value in config_dict.items():
            if isinstance(value, dict):
                # 递归处理嵌套字典
                new_prefix = f"{prefix}{key}_" if prefix else f"{key}_"
                self._update_from_nested_dict(value, new_prefix)
            else:
                # 将配置键转换为属性名
                attr_name = f"{prefix}{key}".lower()
                
                # 处理特殊的映射关系
                attr_mapping = {
                    "framework_name": "app_name",
                    "framework_version": "app_version",
                    "framework_debug": "debug",
                    "server_host": "host",
                    "server_port": "port", 
                    "server_reload": "reload",
                    "infrastructure_cache_default_ttl": "cache_default_ttl",
                    "infrastructure_cache_key_prefix": "cache_key_prefix",
                    "infrastructure_cache_max_size": "cache_max_size",
                    "infrastructure_tasks_max_workers": "task_max_workers",
                    "infrastructure_tasks_retry_attempts": "task_retry_attempts",
                    "infrastructure_tasks_retry_delay": "task_retry_delay",
                    "infrastructure_tasks_result_cache_size": "task_result_cache_size",
                    "infrastructure_tasks_result_cache_ttl": "task_result_cache_ttl",
                    "infrastructure_tasks_enable_s3_storage": "task_enable_s3_storage",  # 新增
                    "infrastructure_tasks_scheduler_interval": "task_scheduler_interval",  # 新增
                    "infrastructure_tasks_cleanup_interval": "task_cleanup_interval",  # 新增
                    "infrastructure_rate_limiting_enabled": "rate_limit_enabled",
                    "infrastructure_rate_limiting_requests_per_minute": "rate_limit_requests_per_minute",
                    "infrastructure_rate_limiting_burst_size": "rate_limit_burst_size",
                    "services_health_check_timeout": "health_check_timeout",
                    "services_health_dependencies": "health_dependencies",
                    "aws_region": "aws_region",
                    "aws_s3_bucket_prefix": "s3_bucket",
                    "monitoring_enable_metrics": "enable_metrics",
                    "monitoring_enable_tracing": "enable_tracing",
                    "monitoring_sample_rate": "tracing_sample_rate",
                    "notifications_slack_enabled": "slack_enabled",
                }
                
                # 使用映射的属性名或原属性名
                final_attr = attr_mapping.get(attr_name, attr_name)
                
                # 只有当属性存在时才设置
                if hasattr(self, final_attr):
                    current_value = getattr(self, final_attr)
                    # 如果当前值是默认值，则用配置文件的值替换
                    if (isinstance(current_value, list) and not current_value) or \
                       (not isinstance(current_value, list) and current_value in [None, "", 0, False]):
                        setattr(self, final_attr, value)

    @property
    def redis_dsn(self) -> Optional[str]:
        """构建Redis连接字符串"""
        if self.redis_url:
            return self.redis_url
        
        if self.redis_host:
            auth = f":{self.redis_password}@" if self.redis_password else ""
            return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
        
        return None

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment == "development"
    
    @property
    def task_storage_config(self) -> Dict[str, Any]:
        """任务存储配置"""
        return {
            "memory_cache_size": self.task_result_cache_size,
            "memory_cache_ttl": self.task_result_cache_ttl,
            "enable_s3_storage": self.task_enable_s3_storage and bool(self.s3_bucket),
            "s3_persist_threshold_kb": self.task_s3_persist_threshold_kb,
            "s3_persist_long_tasks": self.task_s3_persist_long_tasks,
            "cleanup_interval": self.task_cleanup_interval,
            "max_history_hours": self.task_max_history_hours
        }

    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """获取特定服务的配置"""
        service_configs = {
            "health": {
                "timeout": self.health_check_timeout,
                "dependencies": self.health_dependencies,
            },
            "task": {
                "max_workers": self.task_max_workers,
                "retry_attempts": self.task_retry_attempts,
                "retry_delay": self.task_retry_delay,
                "scheduler_interval": self.task_scheduler_interval,
                "storage": self.task_storage_config
            },
            "cache": {
                "default_ttl": self.cache_default_ttl,
                "key_prefix": self.cache_key_prefix,
                "max_size": self.cache_max_size,
            },
            "rate_limit": {
                "enabled": self.rate_limit_enabled,
                "requests_per_minute": self.rate_limit_requests_per_minute,
                "burst_size": self.rate_limit_burst_size,
            }
        }
        
        return service_configs.get(service_name, {})


@lru_cache()
def get_settings() -> Settings:
    """获取缓存的配置实例"""
    return Settings()


# 便捷函数
def get_service_config(service_name: str) -> Dict[str, Any]:
    """获取服务配置"""
    return get_settings().get_service_config(service_name)


def is_production() -> bool:
    """是否为生产环境"""
    return get_settings().is_production