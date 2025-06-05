# app/infrastructure/tasks/result_storage.py
"""
任务结果存储 - 支持内存缓存和S3持久化
"""
import json
from datetime import datetime
from typing import Any, Dict, Optional
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.cache.task_result_cache import task_result_cache
from app.infrastructure.external_services.s3_service import s3_service
from app.application.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class TaskResultStorage:
    """
    任务结果存储管理器
    
    功能：
    1. 内存缓存（快速访问）
    2. S3持久化（长期保存）
    3. 自动清理策略
    4. 结果检索和查询
    """
    
    def __init__(self):
        self.logger = logger
        self.cache = task_result_cache
        self.s3_enabled = bool(settings.s3_bucket)
        self.s3_prefix = "task_results/"
    
    async def store_result(
        self, 
        task_id: str, 
        result_data: Dict[str, Any],
        persist_to_s3: bool = False
    ) -> Dict[str, Any]:
        """存储任务结果"""
        storage_info = {
            "task_id": task_id,
            "stored_at": datetime.utcnow().isoformat(),
            "storage_locations": []
        }
        
        try:
            # 1. 存储到内存缓存
            self.cache.put(task_id, result_data)
            storage_info["storage_locations"].append("memory_cache")
            
            # 2. 可选存储到S3
            if persist_to_s3 and self.s3_enabled:
                s3_key = f"{self.s3_prefix}{task_id}.json"
                
                s3_result = await s3_service.upload_file_async(
                    file_content=json.dumps(result_data, default=str).encode(),
                    key=s3_key,
                    content_type="application/json",
                    metadata={
                        "task_id": task_id,
                        "stored_at": storage_info["stored_at"],
                        "content_type": "task_result"
                    }
                )
                
                if s3_result["success"]:
                    storage_info["storage_locations"].append("s3")
                    storage_info["s3_key"] = s3_key
                    storage_info["s3_url"] = s3_result["url"]
            
            self.logger.info(f"任务结果已存储: {task_id}", extra=storage_info)
            return storage_info
            
        except Exception as e:
            self.logger.error(f"存储任务结果失败: {task_id} - {str(e)}")
            raise
    
    async def get_result(self, task_id: str, try_s3: bool = True) -> Optional[Dict[str, Any]]:
        """获取任务结果"""
        # 1. 先从内存缓存获取
        result = self.cache.get(task_id)
        if result:
            self.logger.debug(f"从缓存获取任务结果: {task_id}")
            return result
        
        # 2. 从S3获取（如果启用）
        if try_s3 and self.s3_enabled:
            try:
                s3_key = f"{self.s3_prefix}{task_id}.json"
                s3_result = await s3_service.download_file_async(s3_key)
                
                if s3_result["success"]:
                    result_data = json.loads(s3_result["content"].decode())
                    
                    # 重新缓存到内存
                    self.cache.put(task_id, result_data)
                    
                    self.logger.debug(f"从S3获取任务结果: {task_id}")
                    return result_data
                    
            except Exception as e:
                self.logger.warning(f"从S3获取任务结果失败: {task_id} - {str(e)}")
        
        return None
    
    async def delete_result(self, task_id: str, delete_from_s3: bool = False) -> Dict[str, Any]:
        """删除任务结果"""
        deletion_info = {
            "task_id": task_id,
            "deleted_from": [],
            "errors": []
        }
        
        # 1. 从缓存删除
        if self.cache.remove(task_id):
            deletion_info["deleted_from"].append("memory_cache")
        
        # 2. 从S3删除（如果需要）
        if delete_from_s3 and self.s3_enabled:
            try:
                s3_key = f"{self.s3_prefix}{task_id}.json"
                if s3_service.delete_file(s3_key):
                    deletion_info["deleted_from"].append("s3")
                else:
                    deletion_info["errors"].append("S3删除失败")
            except Exception as e:
                deletion_info["errors"].append(f"S3删除异常: {str(e)}")
        
        return deletion_info
    
    async def cleanup_old_results(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """清理旧结果"""
        cleanup_info = {
            "cleaned_from_cache": 0,
            "cleaned_from_s3": 0,
            "errors": []
        }
        
        # 清理内存缓存
        cleanup_info["cleaned_from_cache"] = self.cache.cleanup_expired()
        
        # TODO: 清理S3中的旧文件（需要列出文件并检查时间）
        # 这里可以实现S3清理逻辑
        
        return cleanup_info
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        cache_stats = self.cache.get_statistics()
        
        return {
            "cache": cache_stats,
            "s3_enabled": self.s3_enabled,
            "s3_bucket": settings.s3_bucket if self.s3_enabled else None,
            "s3_prefix": self.s3_prefix
        }
