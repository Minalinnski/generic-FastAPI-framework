# src/infrastructure/utils/file_utils.py
import os
import shutil
from pathlib import Path
from typing import List, Optional, Union


class FileUtils:
    """文件工具类"""
    
    @staticmethod
    def ensure_dir(path: Union[str, Path]) -> Path:
        """确保目录存在"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_file_size(path: Union[str, Path]) -> int:
        """获取文件大小（字节）"""
        return Path(path).stat().st_size
    
    @staticmethod
    def get_file_extension(path: Union[str, Path]) -> str:
        """获取文件扩展名"""
        return Path(path).suffix.lower()
    
    @staticmethod
    def is_file_type(path: Union[str, Path], extensions: List[str]) -> bool:
        """检查文件类型"""
        ext = FileUtils.get_file_extension(path)
        return ext in [e.lower() if e.startswith('.') else f'.{e.lower()}' for e in extensions]
    
    @staticmethod
    def safe_filename(filename: str) -> str:
        """创建安全的文件名"""
        from src.infrastructure.utils.validation_utils import ValidationUtils
        return ValidationUtils.sanitize_filename(filename)
    
    @staticmethod
    def copy_file(src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """复制文件"""
        src_path = Path(src)
        dst_path = Path(dst)
        
        # 确保目标目录存在
        FileUtils.ensure_dir(dst_path.parent)
        
        shutil.copy2(src_path, dst_path)
        return dst_path
    
    @staticmethod
    def move_file(src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """移动文件"""
        src_path = Path(src)
        dst_path = Path(dst)
        
        # 确保目标目录存在
        FileUtils.ensure_dir(dst_path.parent)
        
        shutil.move(str(src_path), str(dst_path))
        return dst_path
    
    @staticmethod
    def delete_file(path: Union[str, Path]) -> bool:
        """删除文件"""
        try:
            Path(path).unlink()
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def list_files(directory: Union[str, Path], pattern: str = "*", recursive: bool = False) -> List[Path]:
        """列出文件"""
        dir_path = Path(directory)
        
        if recursive:
            return list(dir_path.rglob(pattern))
        else:
            return list(dir_path.glob(pattern))
    
    @staticmethod
    def read_text_file(path: Union[str, Path], encoding: str = "utf-8") -> str:
        """读取文本文件"""
        return Path(path).read_text(encoding=encoding)
    
    @staticmethod
    def write_text_file(path: Union[str, Path], content: str, encoding: str = "utf-8") -> None:
        """写入文本文件"""
        file_path = Path(path)
        FileUtils.ensure_dir(file_path.parent)
        file_path.write_text(content, encoding=encoding)