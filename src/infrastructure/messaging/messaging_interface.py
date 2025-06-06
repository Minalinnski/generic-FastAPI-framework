# src/infrastructure/messaging/messaging_interface.py
import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Message:
    """消息数据类"""
    id: str
    topic: str
    payload: Dict[str, Any]
    headers: Dict[str, str]
    created_at: float
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息"""
        return cls(**data)


class MessageHandler(ABC):
    """消息处理器接口"""
    
    @abstractmethod
    async def handle(self, message: Message) -> bool:
        """处理消息，返回是否成功"""
        pass
    
    @abstractmethod
    def can_handle(self, message: Message) -> bool:
        """检查是否能处理此消息"""
        pass


class PublisherInterface(ABC):
    """消息发布者接口"""
    
    @abstractmethod
    async def publish(self, topic: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
        """发布消息，返回消息ID"""
        pass
    
    @abstractmethod
    async def publish_batch(self, messages: List[Dict[str, Any]]) -> List[str]:
        """批量发布消息"""
        pass


class SubscriberInterface(ABC):
    """消息订阅者接口"""
    
    @abstractmethod
    async def subscribe(self, topic: str, handler: MessageHandler) -> str:
        """订阅主题，返回订阅ID"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        pass


class MessageBrokerInterface(ABC):
    """消息代理接口"""
    
    @abstractmethod
    async def create_topic(self, topic: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """创建主题"""
        pass
    
    @abstractmethod
    async def delete_topic(self, topic: str) -> bool:
        """删除主题"""
        pass
    
    @abstractmethod
    async def list_topics(self) -> List[str]:
        """列出所有主题"""
        pass
    
    @abstractmethod
    async def get_topic_info(self, topic: str) -> Optional[Dict[str, Any]]:
        """获取主题信息"""
        pass


class InMemoryMessageBroker(MessageBrokerInterface, PublisherInterface, SubscriberInterface):
    """内存消息代理实现（用于开发和测试）"""
    
    def __init__(self):
        self.logger = logger
        
        # 主题和订阅管理
        self._topics: Dict[str, Dict[str, Any]] = {}
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, List[MessageHandler]] = {}
        
        # 消息队列
        self._message_queues: Dict[str, List[Message]] = {}
        
        # 统计信息
        self._stats = {
            "messages_published": 0,
            "messages_processed": 0,
            "messages_failed": 0
        }
        
        # 处理任务
        self._processing_tasks: Dict[str, asyncio.Task] = {}
        self._is_running = False
    
    async def start(self) -> None:
        """启动消息代理"""
        self._is_running = True
        self.logger.info("内存消息代理已启动")
    
    async def stop(self) -> None:
        """停止消息代理"""
        self._is_running = False
        
        # 取消所有处理任务
        for task in self._processing_tasks.values():
            task.cancel()
        
        # 等待任务完成
        if self._processing_tasks:
            await asyncio.gather(*self._processing_tasks.values(), return_exceptions=True)
        
        self.logger.info("内存消息代理已停止")
    
    async def create_topic(self, topic: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """创建主题"""
        if topic not in self._topics:
            self._topics[topic] = {
                "name": topic,
                "created_at": time.time(),
                "config": config or {},
                "message_count": 0,
                "subscriber_count": 0
            }
            
            self._message_queues[topic] = []
            self._handlers[topic] = []
            
            # 启动消息处理任务
            self._processing_tasks[topic] = asyncio.create_task(
                self._process_topic_messages(topic)
            )
            
            self.logger.info(f"创建主题: {topic}")
            return True
        
        return False
    
    async def delete_topic(self, topic: str) -> bool:
        """删除主题"""
        if topic in self._topics:
            # 停止处理任务
            if topic in self._processing_tasks:
                self._processing_tasks[topic].cancel()
                del self._processing_tasks[topic]
            
            # 清理数据
            del self._topics[topic]
            del self._message_queues[topic]
            del self._handlers[topic]
            
            # 清理相关订阅
            to_remove = [
                sub_id for sub_id, sub_info in self._subscriptions.items()
                if sub_info['topic'] == topic
            ]
            for sub_id in to_remove:
                del self._subscriptions[sub_id]
            
            self.logger.info(f"删除主题: {topic}")
            return True
        
        return False
    
    async def list_topics(self) -> List[str]:
        """列出所有主题"""
        return list(self._topics.keys())
    
    async def get_topic_info(self, topic: str) -> Optional[Dict[str, Any]]:
        """获取主题信息"""
        if topic in self._topics:
            info = self._topics[topic].copy()
            info.update({
                "queue_size": len(self._message_queues.get(topic, [])),
                "handler_count": len(self._handlers.get(topic, [])),
                "subscriber_count": len([
                    s for s in self._subscriptions.values()
                    if s['topic'] == topic
                ])
            })
            return info
        return None
    
    async def publish(self, topic: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
        """发布消息"""
        if topic not in self._topics:
            await self.create_topic(topic)
        
        # 创建消息
        message = Message(
            id=str(uuid.uuid4()),
            topic=topic,
            payload=payload,
            headers=headers or {},
            created_at=time.time()
        )
        
        # 添加到队列
        self._message_queues[topic].append(message)
        
        # 更新统计
        self._topics[topic]["message_count"] += 1
        self._stats["messages_published"] += 1
        
        self.logger.debug(f"发布消息到主题 {topic}: {message.id}")
        return message.id
    
    async def publish_batch(self, messages: List[Dict[str, Any]]) -> List[str]:
        """批量发布消息"""
        message_ids = []
        
        for msg_info in messages:
            message_id = await self.publish(
                topic=msg_info["topic"],
                payload=msg_info["payload"],
                headers=msg_info.get("headers")
            )
            message_ids.append(message_id)
        
        return message_ids
    
    async def subscribe(self, topic: str, handler: MessageHandler) -> str:
        """订阅主题"""
        if topic not in self._topics:
            await self.create_topic(topic)
        
        subscription_id = str(uuid.uuid4())
        
        # 添加处理器
        self._handlers[topic].append(handler)
        
        # 记录订阅
        self._subscriptions[subscription_id] = {
            'topic': topic,
            'handler': handler,
            'created_at': time.time()
        }
        
        # 更新统计
        self._topics[topic]["subscriber_count"] += 1
        
        self.logger.info(f"订阅主题 {topic}: {subscription_id}")
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        if subscription_id in self._subscriptions:
            sub_info = self._subscriptions[subscription_id]
            topic = sub_info['topic']
            handler = sub_info['handler']
            
            # 移除处理器
            if topic in self._handlers and handler in self._handlers[topic]:
                self._handlers[topic].remove(handler)
            
            # 删除订阅记录
            del self._subscriptions[subscription_id]
            
            # 更新统计
            if topic in self._topics:
                self._topics[topic]["subscriber_count"] -= 1
            
            self.logger.info(f"取消订阅: {subscription_id}")
            return True
        
        return False
    
    async def _process_topic_messages(self, topic: str) -> None:
        """处理主题消息"""
        while self._is_running and topic in self._topics:
            try:
                # 检查是否有消息需要处理
                if not self._message_queues[topic]:
                    await asyncio.sleep(0.1)
                    continue
                
                # 获取消息
                message = self._message_queues[topic].pop(0)
                
                # 获取处理器
                handlers = self._handlers.get(topic, [])
                
                if not handlers:
                    self.logger.warning(f"主题 {topic} 没有处理器，丢弃消息: {message.id}")
                    continue
                
                # 并发处理消息
                handler_tasks = []
                for handler in handlers:
                    if handler.can_handle(message):
                        handler_tasks.append(
                            asyncio.create_task(self._handle_message(handler, message))
                        )
                
                if handler_tasks:
                    results = await asyncio.gather(*handler_tasks, return_exceptions=True)
                    
                    # 统计处理结果
                    success_count = sum(1 for result in results if result is True)
                    if success_count > 0:
                        self._stats["messages_processed"] += 1
                    else:
                        self._stats["messages_failed"] += 1
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"处理主题 {topic} 消息时出错: {str(e)}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, handler: MessageHandler, message: Message) -> bool:
        """处理单个消息"""
        try:
            return await handler.handle(message)
        except Exception as e:
            self.logger.error(f"消息处理器处理消息失败: {str(e)}", extra={
                "message_id": message.id,
                "handler": handler.__class__.__name__
            })
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "topics_count": len(self._topics),
            "subscriptions_count": len(self._subscriptions),
            "total_queue_size": sum(len(queue) for queue in self._message_queues.values()),
            "statistics": self._stats.copy(),
            "topics": list(self._topics.keys())
        }
    
    def clear_all_queues(self) -> None:
        """清空所有消息队列"""
        for topic in self._message_queues:
            self._message_queues[topic].clear()
        
        self.logger.info("已清空所有消息队列")


# 全局消息代理实例
message_broker = InMemoryMessageBroker()