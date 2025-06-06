# app/infrastructure/tasks/storage/s3_store.py
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.external_services.s3_service import s3_service

logger = get_logger(__name__)


class S3Store:
    """
    S3存储后端 - 持久化任务结果
    
    功能：
    1. 任务结果持久化存储
    2. 结果检索和查询
    3. 生命周期管理
    4. 统计信息收集
    """
    
    def __init__(self):
        self.logger = logger
        self.s3_service = s3_service
        self.prefix = "task_results/"
        
        # 统计信息
        self.stats = {
            "stores": 0,
            "retrieves": 0,
            "deletes": 0,
            "errors": 0
        }
    
    async def store_result(self, task_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """存储任务结果到S3"""
        try:
            s3_key = f"{self.prefix}{task_id}.json"
            
            # 添加存储元数据
            enhanced_data = {
                **result_data,
                "s3_stored_at": datetime.utcnow().isoformat(),
                "storage_version": "1.0"
            }
            
            # 上传到S3
            upload_result = await self.s3_service.upload_file_async(
                file_content=json.dumps(enhanced_data, default=str).encode(),
                key=s3_key,
                content_type="application/json",
                metadata={
                    "task_id": task_id,
                    "stored_at": enhanced_data["s3_stored_at"],
                    "content_type": "task_result"
                }
            )
            
            if upload_result["success"]:
                self.stats["stores"] += 1
                self.logger.debug(f"任务结果已存储到S3: {task_id}")
                
                return {
                    "success": True,
                    "key": s3_key,
                    "url": upload_result["url"],
                    "size": upload_result["file_size"]
                }
            else:
                self.stats["errors"] += 1
                return {"success": False, "error": "S3上传失败"}
            
        except Exception as e:
            self.stats["errors"] += 1
            self.logger.error(f"S3存储失败: {task_id} - {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """从S3获取任务结果"""
        try:
            s3_key = f"{self.prefix}{task_id}.json"
            
            download_result = await self.s3_service.download_file_async(s3_key)
            
            if download_result["success"]:
                result_data = json.loads(download_result["content"].decode())
                self.stats["retrieves"] += 1
                self.logger.debug(f"从S3获取任务结果: {task_id}")
                return result_data
            else:
                return None
            
        except Exception as e:
            self.stats["errors"] += 1
            self.logger.warning(f"从S3获取失败: {task_id} - {str(e)}")
            return None
    
    async def delete_result(self, task_id: str) -> bool:
        """从S3删除任务结果"""
        try:
            s3_key = f"{self.prefix}{task_id}.json"
            
            success = self.s3_service.delete_file(s3_key)
            if success:
                self.stats["deletes"] += 1
                self.logger.debug(f"从S3删除任务结果: {task_id}")
            
            return success
            
        except Exception as e:
            self.stats["errors"] += 1
            self.logger.error(f"从S3删除失败: {task_id} - {str(e)}")
            return False
    
    async def get_recent_results(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的结果"""
        try:
            # 列出S3中的文件
            files = self.s3_service.list_files(prefix=self.prefix, max_keys=limit * 2)
            
            # 按修改时间排序
            files.sort(key=lambda x: x["last_modified"], reverse=True)
            
            results = []
            for file_info in files[:limit]:
                try:
                    # 从文件名提取task_id
                    filename = file_info["key"].replace(self.prefix, "").replace(".json", "")
                    
                    # 获取结果
                    result = await self.get_result(filename)
                    if result:
                        results.append(result)
                        
                except Exception as e:
                    self.logger.warning(f"获取S3文件失败: {file_info['key']} - {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"获取S3最近结果失败: {str(e)}")
            return []
    
    async def cleanup_old_results(self, max_age_days: int = 30) -> Dict[str, Any]:
        """清理旧结果"""
        cleanup_info = {
            "cleaned_count": 0,
            "errors": []
        }
        
        try:
            # 获取所有文件
            files = self.s3_service.list_files(prefix=self.prefix, max_keys=10000)
            
            cutoff_time = datetime.utcnow().timestamp() - (max_age_days * 24 * 3600)
            
            for file_info in files:
                try:
                    # 检查文件年龄
                    file_time = file_info["last_modified"].timestamp()
                    
                    if file_time < cutoff_time:
                        # 删除旧文件
                        success = self.s3_service.delete_file(file_info["key"])
                        if success:
                            cleanup_info["cleaned_count"] += 1
                        else:
                            cleanup_info["errors"].append(f"删除失败: {file_info['key']}")
                            
                except Exception as e:
                    cleanup_info["errors"].append(f"处理文件失败: {file_info['key']} - {str(e)}")
            
            self.logger.info(f"S3清理完成", extra=cleanup_info)
            return cleanup_info
            
        except Exception as e:
            self.logger.error(f"S3清理失败: {str(e)}")
            cleanup_info["errors"].append(str(e))
            return cleanup_info
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "enabled": True,
            "prefix": self.prefix,
            "statistics": self.stats.copy()
        }