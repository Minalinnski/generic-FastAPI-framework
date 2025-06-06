# src/infrastructure/external_services/s3_service.py
import asyncio
import time
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config

from src.application.config.settings import get_settings
from src.infrastructure.logging.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class S3Service:
    """
    S3文件服务
    
    功能：
    1. 文件上传/下载
    2. 预签名URL生成
    3. 文件元数据管理
    4. 批量操作
    5. 生命周期管理
    """
    
    def __init__(self):
        self.logger = logger
        self.bucket_name = settings.s3_bucket
        self.region = settings.aws_region
        self._client = None
        self._async_client = None
        
        # S3配置
        self.config = Config(
            region_name=self.region,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            }
        )
    
    @property
    def client(self):
        """懒加载S3客户端"""
        if self._client is None:
            try:
                self._client = boto3.client(
                    's3',
                    region_name=self.region,
                    config=self.config
                )
                
                # 测试连接
                self._client.head_bucket(Bucket=self.bucket_name)
                
            except NoCredentialsError:
                self.logger.error("AWS凭证未配置")
                raise
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchBucket':
                    self.logger.error(f"S3存储桶不存在: {self.bucket_name}")
                else:
                    self.logger.error(f"S3连接失败: {str(e)}")
                raise
        
        return self._client
    
    async def get_async_client(self):
        """获取异步S3客户端"""
        if self._async_client is None:
            try:
                import aioboto3
                
                session = aioboto3.Session()
                self._async_client = session.client(
                    's3',
                    region_name=self.region,
                    config=self.config
                )
                
            except ImportError:
                self.logger.warning("aioboto3未安装，使用同步客户端的异步包装")
                # 使用同步客户端的异步包装
                return self.client
        
        return self._async_client
    
    def generate_key(self, file_name: str, prefix: Optional[str] = None) -> str:
        """生成S3对象键"""
        # 清理文件名
        safe_name = self._sanitize_filename(file_name)
        
        # 添加时间戳避免冲突
        timestamp = int(time.time())
        name_parts = safe_name.rsplit('.', 1)
        
        if len(name_parts) == 2:
            base_name, ext = name_parts
            safe_name = f"{base_name}_{timestamp}.{ext}"
        else:
            safe_name = f"{safe_name}_{timestamp}"
        
        # 添加前缀
        if prefix:
            return f"{prefix.strip('/')}/{safe_name}"
        
        return safe_name
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        # 移除危险字符
        import re
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        safe_name = re.sub(r'\s+', '_', safe_name)
        
        # 限制长度
        if len(safe_name) > 200:
            name_parts = safe_name.rsplit('.', 1)
            if len(name_parts) == 2:
                base_name, ext = name_parts
                max_base_len = 200 - len(ext) - 1
                safe_name = f"{base_name[:max_base_len]}.{ext}"
            else:
                safe_name = safe_name[:200]
        
        return safe_name
    
    async def upload_file_async(
        self,
        file_content: Union[bytes, BytesIO, str, Path],
        key: Optional[str] = None,
        file_name: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        prefix: Optional[str] = None,
        acl: str = 'private'
    ) -> Dict[str, str]:
        """异步上传文件到S3"""
        try:
            # 处理文件内容
            if isinstance(file_content, (str, Path)):
                file_path = Path(file_content)
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                file_name = file_name or file_path.name
            elif isinstance(file_content, BytesIO):
                file_data = file_content.getvalue()
            else:
                file_data = file_content
            
            # 生成键
            if not key:
                if not file_name:
                    raise ValueError("必须提供key或file_name")
                key = self.generate_key(file_name, prefix)
            
            # 自动检测内容类型
            if not content_type:
                content_type = self._detect_content_type(file_name or key)
            
            self.logger.info(f"开始异步上传文件到S3: {key}", extra={
                "file_size": len(file_data),
                "content_type": content_type
            })
            
            # 准备上传参数
            upload_args = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': file_data,
                'ContentType': content_type or 'application/octet-stream',
                'ACL': acl
            }
            
            if metadata:
                upload_args['Metadata'] = metadata
            
            # 执行异步上传
            async_client = await self.get_async_client()
            
            if hasattr(async_client, 'put_object'):
                # 真正的异步客户端
                await async_client.put_object(**upload_args)
            else:
                # 同步客户端的异步包装
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.client.put_object, **upload_args)
            
            file_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"
            
            self.logger.info(f"文件异步上传成功: {key}", extra={
                "url": file_url,
                "file_size": len(file_data)
            })
            
            return {
                "success": True,
                "key": key,
                "url": file_url,
                "bucket": self.bucket_name,
                "file_size": len(file_data),
                "content_type": content_type
            }
            
        except Exception as e:
            error_msg = f"S3异步上传失败: {str(e)}"
            self.logger.error(error_msg, extra={
                "key": key,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise Exception(error_msg)
    
    def upload_file_sync(
        self,
        file_content: Union[bytes, BytesIO, str, Path],
        key: Optional[str] = None,
        file_name: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        prefix: Optional[str] = None,
        acl: str = 'private'
    ) -> Dict[str, str]:
        """同步上传文件到S3"""
        try:
            # 处理文件内容
            if isinstance(file_content, (str, Path)):
                file_path = Path(file_content)
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                file_name = file_name or file_path.name
            elif isinstance(file_content, BytesIO):
                file_data = file_content.getvalue()
            else:
                file_data = file_content
            
            # 生成键
            if not key:
                if not file_name:
                    raise ValueError("必须提供key或file_name")
                key = self.generate_key(file_name, prefix)
            
            # 自动检测内容类型
            if not content_type:
                content_type = self._detect_content_type(file_name or key)
            
            self.logger.info(f"开始同步上传文件到S3: {key}")
            
            # 准备上传参数
            upload_args = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': file_data,
                'ContentType': content_type or 'application/octet-stream',
                'ACL': acl
            }
            
            if metadata:
                upload_args['Metadata'] = metadata
            
            # 执行上传
            self.client.put_object(**upload_args)
            
            file_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"
            
            self.logger.info(f"文件同步上传成功: {key}", extra={"url": file_url})
            
            return {
                "success": True,
                "key": key,
                "url": file_url,
                "bucket": self.bucket_name,
                "file_size": len(file_data),
                "content_type": content_type
            }
            
        except Exception as e:
            error_msg = f"S3同步上传失败: {str(e)}"
            self.logger.error(error_msg, extra={"key": key, "error": str(e)})
            raise Exception(error_msg)
    
    async def download_file_async(self, key: str) -> Dict[str, Union[bytes, str]]:
        """异步从S3下载文件"""
        try:
            self.logger.info(f"开始异步下载文件: {key}")
            
            async_client = await self.get_async_client()
            
            if hasattr(async_client, 'get_object'):
                # 真正的异步客户端
                response = await async_client.get_object(Bucket=self.bucket_name, Key=key)
                content = await response['Body'].read()
            else:
                # 同步客户端的异步包装
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    self.client.get_object,
                    self.bucket_name,
                    key
                )
                content = response['Body'].read()
            
            self.logger.info(f"文件异步下载成功: {key}")
            
            return {
                "success": True,
                "key": key,
                "content": content,
                "content_length": len(content),
                "content_type": response.get('ContentType', 'application/octet-stream'),
                "metadata": response.get('Metadata', {}),
                "last_modified": response.get('LastModified')
            }
            
        except Exception as e:
            error_msg = f"S3异步下载失败: {str(e)}"
            self.logger.error(error_msg, extra={"key": key, "error": str(e)})
            raise Exception(error_msg)
    
    def download_file_sync(self, key: str) -> Dict[str, Union[bytes, str]]:
        """同步从S3下载文件"""
        try:
            self.logger.info(f"开始同步下载文件: {key}")
            
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            content = response['Body'].read()
            
            self.logger.info(f"文件同步下载成功: {key}")
            
            return {
                "success": True,
                "key": key,
                "content": content,
                "content_length": len(content),
                "content_type": response.get('ContentType', 'application/octet-stream'),
                "metadata": response.get('Metadata', {}),
                "last_modified": response.get('LastModified')
            }
            
        except Exception as e:
            error_msg = f"S3同步下载失败: {str(e)}"
            self.logger.error(error_msg, extra={"key": key, "error": str(e)})
            raise Exception(error_msg)
    
    def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        http_method: str = 'GET'
    ) -> str:
        """生成预签名URL"""
        try:
            url = self.client.generate_presigned_url(
                f'{http_method.lower()}_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            
            self.logger.info(f"生成预签名URL成功: {key}", extra={
                "expiration": expiration,
                "method": http_method
            })
            return url
            
        except Exception as e:
            error_msg = f"生成预签名URL失败: {str(e)}"
            self.logger.error(error_msg, extra={"key": key, "error": str(e)})
            raise Exception(error_msg)
    
    def delete_file(self, key: str) -> bool:
        """删除文件"""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            self.logger.info(f"删除文件成功: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除文件失败: {key} - {str(e)}")
            return False
    
    def list_files(
        self,
        prefix: Optional[str] = None,
        max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        """列出文件"""
        try:
            params = {
                'Bucket': self.bucket_name,
                'MaxKeys': max_keys
            }
            
            if prefix:
                params['Prefix'] = prefix
            
            response = self.client.list_objects_v2(**params)
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"')
                })
            
            return files
            
        except Exception as e:
            self.logger.error(f"列出文件失败: {str(e)}")
            return []
    
    def get_file_info(self, key: str) -> Optional[Dict[str, Any]]:
        """获取文件信息"""
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)
            
            return {
                'key': key,
                'size': response['ContentLength'],
                'content_type': response.get('ContentType'),
                'last_modified': response['LastModified'],
                'etag': response['ETag'].strip('"'),
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            raise
    
    def _detect_content_type(self, filename: str) -> str:
        """检测文件内容类型"""
        import mimetypes
        
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or 'application/octet-stream'
    
    async def batch_upload(
        self,
        files: List[Dict[str, Any]],
        prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """批量上传文件"""
        results = []
        
        for file_info in files:
            try:
                result = await self.upload_file_async(
                    file_content=file_info['content'],
                    file_name=file_info.get('name'),
                    key=file_info.get('key'),
                    content_type=file_info.get('content_type'),
                    metadata=file_info.get('metadata'),
                    prefix=prefix
                )
                results.append(result)
                
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e),
                    "file_name": file_info.get('name', 'unknown')
                })
        
        return results


# 全局S3服务实例
s3_service = S3Service()