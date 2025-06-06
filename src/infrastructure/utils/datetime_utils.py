# src/infrastructure/utils/datetime_utils.py
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import pytz


class DateTimeUtils:
    """时间工具类"""
    
    # 常用时区
    UTC = timezone.utc
    BEIJING = pytz.timezone('Asia/Shanghai')
    TOKYO = pytz.timezone('Asia/Tokyo')
    NEW_YORK = pytz.timezone('America/New_York')
    LONDON = pytz.timezone('Europe/London')
    
    # 常用格式
    ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"
    ISO_FORMAT_WITH_TZ = "%Y-%m-%dT%H:%M:%S%z"
    DATE_FORMAT = "%Y-%m-%d"
    TIME_FORMAT = "%H:%M:%S"
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    FILENAME_FORMAT = "%Y%m%d_%H%M%S"
    
    @staticmethod
    def now(tz: Optional[timezone] = None) -> datetime:
        """获取当前时间"""
        return datetime.now(tz or DateTimeUtils.UTC)
    
    @staticmethod
    def utc_now() -> datetime:
        """获取UTC当前时间"""
        return datetime.now(DateTimeUtils.UTC)
    
    @staticmethod
    def timestamp() -> float:
        """获取当前时间戳"""
        return time.time()
    
    @staticmethod
    def timestamp_ms() -> int:
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)
    
    @staticmethod
    def from_timestamp(timestamp: Union[int, float], tz: Optional[timezone] = None) -> datetime:
        """从时间戳创建datetime"""
        return datetime.fromtimestamp(timestamp, tz or DateTimeUtils.UTC)
    
    @staticmethod
    def to_timestamp(dt: datetime) -> float:
        """datetime转时间戳"""
        return dt.timestamp()
    
    @staticmethod
    def format_datetime(dt: datetime, fmt: str = None) -> str:
        """格式化datetime"""
        return dt.strftime(fmt or DateTimeUtils.ISO_FORMAT)
    
    @staticmethod
    def parse_datetime(date_string: str, fmt: str = None) -> datetime:
        """解析datetime字符串"""
        if fmt:
            return datetime.strptime(date_string, fmt)
        
        # 尝试多种格式
        formats = [
            DateTimeUtils.ISO_FORMAT_WITH_TZ,
            DateTimeUtils.ISO_FORMAT,
            DateTimeUtils.DATETIME_FORMAT,
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ]
        
        for fmt_try in formats:
            try:
                return datetime.strptime(date_string, fmt_try)
            except ValueError:
                continue
        
        # 最后尝试ISO格式解析
        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Unable to parse datetime string: {date_string}")
    
    @staticmethod
    def to_iso_string(dt: datetime) -> str:
        """转换为ISO格式字符串"""
        return dt.isoformat()
    
    @staticmethod
    def from_iso_string(iso_string: str) -> datetime:
        """从ISO格式字符串解析"""
        return datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    
    @staticmethod
    def time_ago(dt: datetime, now: Optional[datetime] = None) -> str:
        """计算相对时间描述"""
        if now is None:
            now = DateTimeUtils.utc_now()
        
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=DateTimeUtils.UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=DateTimeUtils.UTC)
        
        diff = now - dt
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "just now"
    
    @staticmethod
    def duration_string(seconds: Union[int, float]) -> str:
        """将秒数转换为可读的时长字符串"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.1f}h"
        else:
            days = seconds / 86400
            return f"{days:.1f}d"
    
    @staticmethod
    def get_filename_timestamp() -> str:
        """获取适合文件名的时间戳"""
        return DateTimeUtils.now().strftime(DateTimeUtils.FILENAME_FORMAT)


# 便捷函数
def now(tz: Optional[timezone] = None) -> datetime:
    """获取当前时间"""
    return DateTimeUtils.now(tz)


def utc_now() -> datetime:
    """获取UTC当前时间"""
    return DateTimeUtils.utc_now()


def timestamp() -> float:
    """获取当前时间戳"""
    return DateTimeUtils.timestamp()


def parse_datetime(date_string: str, fmt: str = None) -> datetime:
    """解析datetime字符串"""
    return DateTimeUtils.parse_datetime(date_string, fmt)


def time_ago(dt: datetime, now: Optional[datetime] = None) -> str:
    """计算相对时间描述"""
    return DateTimeUtils.time_ago(dt, now)

