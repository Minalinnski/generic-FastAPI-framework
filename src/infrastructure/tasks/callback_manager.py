# src/infrastructure/tasks/callback_manager.py
import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class CallbackType(str, Enum):
    """回调类型"""
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRY = "retry"
    PROGRESS = "progress"


class CallbackTrigger(str, Enum):
    """回调触发方式"""
    IMMEDIATE = "immediate"  # 立即执行
    ASYNC = "async"         # 异步执行
    WEBHOOK = "webhook"     # HTTP回调
    MESSAGE = "message"     # 消息队列


@dataclass
class Callback:
    """回调定义"""
    callback_id: str
    task_id: str
    callback_type: CallbackType
    trigger: CallbackTrigger
    target: Union[Callable, str]  # 函数或URL
    params: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3
    retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_attempted_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "callback_id": self.callback_id,
            "task_id": self.task_id,
            "callback_type": self.callback_type.value,
            "trigger": self.trigger.value,
            "target": str(self.target),
            "params": self.params,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "last_attempted_at": self.last_attempted_at.isoformat() if self.last_attempted_at else None
        }


class CallbackManager:
    """
    回调管理器 - 处理任务完成后的回调逻辑
    
    功能：
    1. 回调注册和管理
    2. 多种回调触发方式
    3. 回调重试机制
    4. 回调链支持
    5. 异步服务回调支持
    """
    
    def __init__(self):
        self.logger = logger
        
        # 回调存储
        self.callbacks: Dict[str, List[Callback]] = {}  # task_id -> callbacks
        self.pending_callbacks: List[Callback] = []
        
        # HTTP客户端（用于webhook）
        self._http_client = None
        
        # 消息客户端（用于消息回调）
        self._message_client = None
        
        # 管理状态
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.stats = {
            "callbacks_registered": 0,
            "callbacks_executed": 0,
            "callbacks_failed": 0,
            "webhooks_sent": 0,
            "retries_attempted": 0
        }
    
    async def start(self) -> None:
        """启动回调管理器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动HTTP客户端
        await self._init_http_client()
        
        # 启动回调处理器
        self._processor_task = asyncio.create_task(self._callback_processor())
        
        self.logger.info("回调管理器已启动")
    
    async def shutdown(self) -> None:
        """关闭回调管理器"""
        self._running = False
        
        # 停止处理器
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # 关闭HTTP客户端
        if self._http_client:
            await self._http_client.aclose()
        
        self.logger.info("回调管理器已关闭")
    
    def register_callback(
        self,
        task_id: str,
        callback_type: CallbackType,
        trigger: CallbackTrigger,
        target: Union[Callable, str],
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> str:
        """注册回调"""
        import uuid
        
        callback_id = str(uuid.uuid4())
        callback = Callback(
            callback_id=callback_id,
            task_id=task_id,
            callback_type=callback_type,
            trigger=trigger,
            target=target,
            params=params or {},
            max_retries=max_retries
        )
        
        if task_id not in self.callbacks:
            self.callbacks[task_id] = []
        
        self.callbacks[task_id].append(callback)
        self.stats["callbacks_registered"] += 1
        
        self.logger.info(f"注册回调: {callback_id}", extra={
            "task_id": task_id,
            "type": callback_type.value,
            "trigger": trigger.value
        })
        
        return callback_id
    
    async def trigger_callbacks(self, task, event_type: str) -> None:
        """触发回调"""
        task_id = task.task_id
        
        if task_id not in self.callbacks:
            return
        
        callbacks = self.callbacks[task_id]
        matching_callbacks = [
            cb for cb in callbacks 
            if cb.callback_type.value == event_type
        ]
        
        for callback in matching_callbacks:
            await self._execute_callback(callback, task)
    
    async def _execute_callback(self, callback: Callback, task) -> None:
        """执行单个回调"""
        callback.last_attempted_at = datetime.utcnow()
        
        try:
            if callback.trigger == CallbackTrigger.IMMEDIATE:
                await self._execute_immediate_callback(callback, task)
            elif callback.trigger == CallbackTrigger.ASYNC:
                self.pending_callbacks.append(callback)
            elif callback.trigger == CallbackTrigger.WEBHOOK:
                await self._execute_webhook_callback(callback, task)
            elif callback.trigger == CallbackTrigger.MESSAGE:
                await self._execute_message_callback(callback, task)
            
            self.stats["callbacks_executed"] += 1
            
        except Exception as e:
            self.logger.error(f"回调执行失败: {callback.callback_id} - {str(e)}")
            await self._handle_callback_failure(callback, e)
    
    async def _execute_immediate_callback(self, callback: Callback, task) -> None:
        """执行立即回调"""
        if callable(callback.target):
            await callback.target(task, **callback.params)
        else:
            raise ValueError("立即回调目标必须是可调用对象")
    
    async def _execute_webhook_callback(self, callback: Callback, task) -> None:
        """执行Webhook回调"""
        if not isinstance(callback.target, str):
            raise ValueError("Webhook目标必须是URL字符串")
        
        payload = {
            "task_id": task.task_id,
            "task_name": task.task_name,
            "status": task.status.value,
            "result": task.result,
            "error": task.error,
            "duration": task.duration,
            "callback_params": callback.params,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._http_client.post(
            callback.target,
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        self.stats["webhooks_sent"] += 1
        
        self.logger.info(f"Webhook发送成功: {callback.callback_id}")
    
    async def _execute_message_callback(self, callback: Callback, task) -> None:
        """执行消息回调"""
        # TODO: 实现消息队列回调
        self.logger.warning("消息回调暂未实现")
    
    async def _handle_callback_failure(self, callback: Callback, error: Exception) -> None:
        """处理回调失败"""
        callback.retry_count += 1
        self.stats["callbacks_failed"] += 1
        
        if callback.retry_count < callback.max_retries:
            # 重试
            self.pending_callbacks.append(callback)
            self.stats["retries_attempted"] += 1
            self.logger.warning(f"回调重试: {callback.callback_id} ({callback.retry_count}/{callback.max_retries})")
        else:
            self.logger.error(f"回调最终失败: {callback.callback_id}")
    
    async def _callback_processor(self) -> None:
        """回调处理器主循环"""
        while self._running:
            try:
                if self.pending_callbacks:
                    callback = self.pending_callbacks.pop(0)
                    # TODO: 获取对应的task信息
                    # await self._execute_callback(callback, task)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"回调处理器错误: {str(e)}")
                await asyncio.sleep(5)
    
    async def _init_http_client(self) -> None:
        """初始化HTTP客户端"""
        try:
            import httpx
            self._http_client = httpx.AsyncClient()
        except ImportError:
            self.logger.warning("httpx未安装，Webhook回调不可用")
    
    def remove_callbacks(self, task_id: str) -> int:
        """移除任务的所有回调"""
        if task_id in self.callbacks:
            count = len(self.callbacks[task_id])
            del self.callbacks[task_id]
            self.logger.debug(f"移除任务回调: {task_id} ({count}个)")
            return count
        return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_callbacks": sum(len(cbs) for cbs in self.callbacks.values()),
            "pending_callbacks": len(self.pending_callbacks),
            "statistics": self.stats.copy()
        }
    
    # 便捷方法
    def on_success(self, task_id: str, callback_func: Callable, **params) -> str:
        """注册成功回调"""
        return self.register_callback(
            task_id, CallbackType.SUCCESS, CallbackTrigger.IMMEDIATE, 
            callback_func, params
        )
    
    def on_failure(self, task_id: str, callback_func: Callable, **params) -> str:
        """注册失败回调"""
        return self.register_callback(
            task_id, CallbackType.FAILED, CallbackTrigger.IMMEDIATE,
            callback_func, params
        )
    
    def webhook_on_completion(self, task_id: str, webhook_url: str, **params) -> str:
        """注册完成时的Webhook回调"""
        return self.register_callback(
            task_id, CallbackType.SUCCESS, CallbackTrigger.WEBHOOK,
            webhook_url, params
        )