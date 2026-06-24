"""
WebSocket Manager for AutoGen Financial Analysis System
Real-time updates and notifications
"""

import json
import asyncio
import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import redis


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.task_subscribers: Dict[str, Set[str]] = {}  # task_id -> connection_ids
        self.channel_subscribers: Dict[str, Set[str]] = {}  # channel -> connection_ids
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self._pubsub = None

    async def connect(self, websocket: WebSocket, connection_id: Optional[str] = None) -> str:
        """接受WebSocket连接"""
        await websocket.accept()

        if connection_id is None:
            connection_id = f"conn_{datetime.now().timestamp()}"

        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "connected_at": datetime.now(),
            "last_activity": datetime.now(),
            "subscriptions": set(),
            "user_agent": websocket.headers.get("user-agent", "unknown")
        }

        self.logger.info(f"WebSocket连接建立: {connection_id}")
        return connection_id

    async def disconnect(self, connection_id: str):
        """断开WebSocket连接"""
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].close()
            except:
                pass
            del self.active_connections[connection_id]

        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]

        # 从所有订阅中移除
        self._remove_from_all_subscriptions(connection_id)

        self.logger.info(f"WebSocket连接断开: {connection_id}")

    def _remove_from_all_subscriptions(self, connection_id: str):
        """从所有订阅中移除连接"""
        # 从任务订阅中移除
        for task_id, connections in self.task_subscribers.items():
            if connection_id in connections:
                connections.remove(connection_id)

        # 从频道订阅中移除
        for channel, connections in self.channel_subscribers.items():
            if connection_id in connections:
                connections.remove(connection_id)

    async def subscribe_to_task(self, connection_id: str, task_id: str):
        """订阅任务状态更新"""
        if connection_id not in self.active_connections:
            return False

        if task_id not in self.task_subscribers:
            self.task_subscribers[task_id] = set()

        self.task_subscribers[task_id].add(connection_id)

        # 更新连接元数据
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["subscriptions"].add(f"task:{task_id}")

        self.logger.info(f"连接 {connection_id} 订阅任务 {task_id}")
        return True

    async def unsubscribe_from_task(self, connection_id: str, task_id: str):
        """取消订阅任务状态更新"""
        if task_id in self.task_subscribers and connection_id in self.task_subscribers[task_id]:
            self.task_subscribers[task_id].remove(connection_id)

        # 更新连接元数据
        if connection_id in self.connection_metadata:
            subscriptions = self.connection_metadata[connection_id]["subscriptions"]
            subscriptions.discard(f"task:{task_id}")

        self.logger.info(f"连接 {connection_id} 取消订阅任务 {task_id}")

    async def subscribe_to_channel(self, connection_id: str, channel: str):
        """订阅频道更新"""
        if connection_id not in self.active_connections:
            return False

        if channel not in self.channel_subscribers:
            self.channel_subscribers[channel] = set()

        self.channel_subscribers[channel].add(connection_id)

        # 更新连接元数据
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["subscriptions"].add(f"channel:{channel}")

        self.logger.info(f"连接 {connection_id} 订阅频道 {channel}")
        return True

    async def unsubscribe_from_channel(self, connection_id: str, channel: str):
        """取消订阅频道更新"""
        if channel in self.channel_subscribers and connection_id in self.channel_subscribers[channel]:
            self.channel_subscribers[channel].remove(connection_id)

        # 更新连接元数据
        if connection_id in self.connection_metadata:
            subscriptions = self.connection_metadata[connection_id]["subscriptions"]
            subscriptions.discard(f"channel:{channel}")

        self.logger.info(f"连接 {connection_id} 取消订阅频道 {channel}")

    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]):
        """发送消息到特定连接"""
        if connection_id not in self.active_connections:
            return False

        try:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(json.dumps(message))

            # 更新活动时间
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]["last_activity"] = datetime.now()

            return True

        except Exception as e:
            self.logger.error(f"发送消息失败 {connection_id}: {str(e)}")
            await self.disconnect(connection_id)
            return False

    async def broadcast_to_task(self, task_id: str, message: Dict[str, Any]):
        """广播消息到任务订阅者"""
        if task_id not in self.task_subscribers:
            return

        failed_connections = []
        for connection_id in self.task_subscribers[task_id]:
            if not await self.send_to_connection(connection_id, message):
                failed_connections.append(connection_id)

        # 清理失败的连接
        for connection_id in failed_connections:
            await self.disconnect(connection_id)

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """广播消息到频道订阅者"""
        if channel not in self.channel_subscribers:
            return

        failed_connections = []
        for connection_id in self.channel_subscribers[channel]:
            if not await self.send_to_connection(connection_id, message):
                failed_connections.append(connection_id)

        # 清理失败的连接
        for connection_id in failed_connections:
            await self.disconnect(connection_id)

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """广播消息到所有连接"""
        failed_connections = []
        for connection_id in self.active_connections.keys():
            if not await self.send_to_connection(connection_id, message):
                failed_connections.append(connection_id)

        # 清理失败的连接
        for connection_id in failed_connections:
            await self.disconnect(connection_id)

    async def send_task_update(self, task_id: str, update_data: Dict[str, Any]):
        """发送任务更新"""
        message = {
            "type": "task_update",
            "task_id": task_id,
            "data": update_data,
            "timestamp": datetime.now().isoformat()
        }

        await self.broadcast_to_task(task_id, message)

        # 如果有Redis，也发布到Redis频道
        if self.redis_client:
            try:
                self.redis_client.publish(f"task_updates:{task_id}", json.dumps(message))
            except Exception as e:
                self.logger.error(f"发布到Redis失败: {str(e)}")

    async def send_system_notification(self, notification_type: str, data: Dict[str, Any]):
        """发送系统通知"""
        message = {
            "type": "system_notification",
            "notification_type": notification_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

        await self.broadcast_to_channel("system", message)

    async def send_error_notification(self, connection_id: str, error_message: str, error_code: str = "ERROR"):
        """发送错误通知"""
        message = {
            "type": "error",
            "error_code": error_code,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        }

        await self.send_to_connection(connection_id, message)

    async def handle_message(self, connection_id: str, message: Dict[str, Any]):
        """处理WebSocket消息"""
        try:
            message_type = message.get("type")

            if message_type == "ping":
                # 心跳响应
                await self.send_to_connection(connection_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })

            elif message_type == "subscribe_task":
                # 订阅任务
                task_id = message.get("task_id")
                if task_id:
                    success = await self.subscribe_to_task(connection_id, task_id)
                    await self.send_to_connection(connection_id, {
                        "type": "subscription_result",
                        "success": success,
                        "subscription_type": "task",
                        "task_id": task_id
                    })

            elif message_type == "unsubscribe_task":
                # 取消订阅任务
                task_id = message.get("task_id")
                if task_id:
                    await self.unsubscribe_from_task(connection_id, task_id)
                    await self.send_to_connection(connection_id, {
                        "type": "unsubscription_result",
                        "subscription_type": "task",
                        "task_id": task_id
                    })

            elif message_type == "subscribe_channel":
                # 订阅频道
                channel = message.get("channel")
                if channel:
                    success = await self.subscribe_to_channel(connection_id, channel)
                    await self.send_to_connection(connection_id, {
                        "type": "subscription_result",
                        "success": success,
                        "subscription_type": "channel",
                        "channel": channel
                    })

            elif message_type == "unsubscribe_channel":
                # 取消订阅频道
                channel = message.get("channel")
                if channel:
                    await self.unsubscribe_from_channel(connection_id, channel)
                    await self.send_to_connection(connection_id, {
                        "type": "unsubscription_result",
                        "subscription_type": "channel",
                        "channel": channel
                    })

            elif message_type == "get_subscriptions":
                # 获取订阅列表
                subscriptions = self.connection_metadata.get(connection_id, {}).get("subscriptions", set())
                await self.send_to_connection(connection_id, {
                    "type": "subscriptions",
                    "subscriptions": list(subscriptions)
                })

            else:
                # 未知消息类型
                await self.send_error_notification(connection_id, f"未知消息类型: {message_type}", "UNKNOWN_MESSAGE_TYPE")

        except Exception as e:
            self.logger.error(f"处理WebSocket消息失败: {str(e)}")
            await self.send_error_notification(connection_id, "消息处理失败", "MESSAGE_PROCESSING_ERROR")

    async def start_heartbeat_monitor(self):
        """启动心跳监控"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次

                current_time = datetime.now()
                inactive_connections = []

                for connection_id, metadata in self.connection_metadata.items():
                    last_activity = metadata["last_activity"]
                    # 如果超过5分钟没有活动，断开连接
                    if (current_time - last_activity).total_seconds() > 300:
                        inactive_connections.append(connection_id)

                # 断开不活跃的连接
                for connection_id in inactive_connections:
                    self.logger.info(f"断开不活跃的连接: {connection_id}")
                    await self.disconnect(connection_id)

            except Exception as e:
                self.logger.error(f"心跳监控失败: {str(e)}")

    async def start_redis_listener(self):
        """启动Redis监听器"""
        if not self.redis_client:
            return

        try:
            self._pubsub = self.redis_client.pubsub()
            self._pubsub.psubscribe("task_updates:*")

            async for message in self._pubsub.listen():
                if message["type"] == "pmessage":
                    try:
                        channel = message["channel"]
                        data = json.loads(message["data"])

                        # 提取task_id
                        task_id = channel.split(":", 1)[1]
                        await self.broadcast_to_task(task_id, data)

                    except Exception as e:
                        self.logger.error(f"处理Redis消息失败: {str(e)}")

        except Exception as e:
            self.logger.error(f"Redis监听器失败: {str(e)}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        return {
            "total_connections": len(self.active_connections),
            "active_connections": len([c for c in self.active_connections.values() if not c.client_state.disconnected]),
            "task_subscriptions": {task_id: len(connections) for task_id, connections in self.task_subscribers.items()},
            "channel_subscriptions": {channel: len(connections) for channel, connections in self.channel_subscribers.items()},
            "timestamp": datetime.now().isoformat()
        }

    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """获取连接信息"""
        if connection_id in self.connection_metadata:
            metadata = self.connection_metadata[connection_id].copy()
            metadata["connection_id"] = connection_id
            metadata["is_active"] = connection_id in self.active_connections
            return metadata
        return None

    async def close(self):
        """关闭所有连接"""
        for connection_id in list(self.active_connections.keys()):
            await self.disconnect(connection_id)

        if self._pubsub:
            await self._pubsub.close()

        self.active_connections.clear()
        self.connection_metadata.clear()
        self.task_subscribers.clear()
        self.channel_subscribers.clear()


# WebSocket消息路由处理器
class WebSocketRouter:
    """WebSocket消息路由处理器"""

    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.message_handlers = {
            "ping": self._handle_ping,
            "subscribe": self._handle_subscribe,
            "unsubscribe": self._handle_unsubscribe,
            "get_info": self._handle_get_info,
            "get_stats": self._handle_get_stats
        }

    async def route_message(self, connection_id: str, message: Dict[str, Any]):
        """路由消息到相应的处理器"""
        try:
            message_type = message.get("type")
            handler = self.message_handlers.get(message_type)

            if handler:
                await handler(connection_id, message)
            else:
                await self.websocket_manager.send_error_notification(
                    connection_id, f"未知的消息类型: {message_type}", "UNKNOWN_MESSAGE_TYPE"
                )

        except Exception as e:
            await self.websocket_manager.send_error_notification(
                connection_id, f"消息处理失败: {str(e)}", "MESSAGE_PROCESSING_ERROR"
            )

    async def _handle_ping(self, connection_id: str, message: Dict[str, Any]):
        """处理心跳消息"""
        await self.websocket_manager.send_to_connection(connection_id, {
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })

    async def _handle_subscribe(self, connection_id: str, message: Dict[str, Any]):
        """处理订阅消息"""
        subscription_type = message.get("subscription_type")
        target = message.get("target")

        if subscription_type == "task":
            await self.websocket_manager.subscribe_to_task(connection_id, target)
        elif subscription_type == "channel":
            await self.websocket_manager.subscribe_to_channel(connection_id, target)
        else:
            await self.websocket_manager.send_error_notification(
                connection_id, f"未知的订阅类型: {subscription_type}", "UNKNOWN_SUBSCRIPTION_TYPE"
            )

    async def _handle_unsubscribe(self, connection_id: str, message: Dict[str, Any]):
        """处理取消订阅消息"""
        subscription_type = message.get("subscription_type")
        target = message.get("target")

        if subscription_type == "task":
            await self.websocket_manager.unsubscribe_from_task(connection_id, target)
        elif subscription_type == "channel":
            await self.websocket_manager.unsubscribe_from_channel(connection_id, target)
        else:
            await self.websocket_manager.send_error_notification(
                connection_id, f"未知的订阅类型: {subscription_type}", "UNKNOWN_SUBSCRIPTION_TYPE"
            )

    async def _handle_get_info(self, connection_id: str, message: Dict[str, Any]):
        """处理获取信息消息"""
        info = self.websocket_manager.get_connection_info(connection_id)
        await self.websocket_manager.send_to_connection(connection_id, {
            "type": "connection_info",
            "info": info
        })

    async def _handle_get_stats(self, connection_id: str, message: Dict[str, Any]):
        """处理获取统计消息"""
        stats = self.websocket_manager.get_connection_stats()
        await self.websocket_manager.send_to_connection(connection_id, {
            "type": "connection_stats",
            "stats": stats
        })