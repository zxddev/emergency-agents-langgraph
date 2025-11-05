"""
Redis缓存客户端

功能：
- 单例模式的Redis连接池
- 自动序列化/反序列化JSON数据
- 安全的错误处理（Redis不可用时降级）
- 支持TTL过期时间
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional
from redis import Redis, ConnectionPool, RedisError
import structlog

logger = structlog.get_logger(__name__)


class RedisClient:
    """Redis缓存客户端（单例模式）"""

    _instance: Optional["RedisClient"] = None
    _pool: Optional[ConnectionPool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化Redis连接池"""
        if self._pool is not None:
            return  # 已经初始化过

        # 从环境变量读取配置
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_password = os.getenv("REDIS_PASSWORD")
        max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
        socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
        socket_connect_timeout = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))

        try:
            self._pool = ConnectionPool.from_url(
                redis_url,
                password=redis_password if redis_password else None,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                decode_responses=True,  # 自动解码为字符串
                health_check_interval=30  # 健康检查间隔30秒
            )

            # 测试连接
            client = Redis(connection_pool=self._pool)
            client.ping()
            logger.info("Redis连接成功", redis_url=redis_url)

        except Exception as e:
            logger.warning(
                "Redis连接失败，缓存功能将降级",
                error=str(e),
                redis_url=redis_url
            )
            self._pool = None

    def get_client(self) -> Optional[Redis]:
        """获取Redis客户端"""
        if self._pool is None:
            return None
        return Redis(connection_pool=self._pool)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        prefix: str = "emergency:"
    ) -> bool:
        """
        设置缓存

        参数：
            key: 缓存键
            value: 缓存值（会自动序列化为JSON）
            ttl: 过期时间（秒），None表示不过期
            prefix: 键前缀，默认"emergency:"

        返回：
            是否成功
        """
        client = self.get_client()
        if client is None:
            logger.debug("Redis不可用，跳过缓存设置", key=key)
            return False

        try:
            full_key = f"{prefix}{key}"
            serialized = json.dumps(value, ensure_ascii=False)

            if ttl is not None:
                client.setex(full_key, ttl, serialized)
            else:
                client.set(full_key, serialized)

            logger.debug(
                "Redis缓存设置成功",
                key=full_key,
                ttl=ttl,
                size_bytes=len(serialized)
            )
            return True

        except (RedisError, TypeError, ValueError) as e:
            logger.warning("Redis设置失败", key=key, error=str(e))
            return False

    def get(
        self,
        key: str,
        prefix: str = "emergency:"
    ) -> Optional[Any]:
        """
        获取缓存

        参数：
            key: 缓存键
            prefix: 键前缀，默认"emergency:"

        返回：
            缓存值（自动反序列化），不存在或出错返回None
        """
        client = self.get_client()
        if client is None:
            logger.debug("Redis不可用，跳过缓存读取", key=key)
            return None

        try:
            full_key = f"{prefix}{key}"
            value = client.get(full_key)

            if value is None:
                logger.debug("Redis缓存未命中", key=full_key)
                return None

            deserialized = json.loads(value)
            logger.debug("Redis缓存命中", key=full_key)
            return deserialized

        except (RedisError, json.JSONDecodeError) as e:
            logger.warning("Redis获取失败", key=key, error=str(e))
            return None

    def delete(
        self,
        key: str,
        prefix: str = "emergency:"
    ) -> bool:
        """
        删除缓存

        参数：
            key: 缓存键
            prefix: 键前缀，默认"emergency:"

        返回：
            是否成功
        """
        client = self.get_client()
        if client is None:
            return False

        try:
            full_key = f"{prefix}{key}"
            client.delete(full_key)
            logger.debug("Redis缓存删除成功", key=full_key)
            return True

        except RedisError as e:
            logger.warning("Redis删除失败", key=key, error=str(e))
            return False

    def exists(
        self,
        key: str,
        prefix: str = "emergency:"
    ) -> bool:
        """
        检查缓存是否存在

        参数：
            key: 缓存键
            prefix: 键前缀，默认"emergency:"

        返回：
            是否存在
        """
        client = self.get_client()
        if client is None:
            return False

        try:
            full_key = f"{prefix}{key}"
            return client.exists(full_key) > 0

        except RedisError as e:
            logger.warning("Redis检查失败", key=key, error=str(e))
            return False

    def get_ttl(
        self,
        key: str,
        prefix: str = "emergency:"
    ) -> Optional[int]:
        """
        获取缓存剩余TTL

        参数：
            key: 缓存键
            prefix: 键前缀，默认"emergency:"

        返回：
            剩余秒数，-1表示永不过期，-2表示不存在，None表示错误
        """
        client = self.get_client()
        if client is None:
            return None

        try:
            full_key = f"{prefix}{key}"
            return client.ttl(full_key)

        except RedisError as e:
            logger.warning("Redis TTL查询失败", key=key, error=str(e))
            return None


# 导出单例实例
redis_client = RedisClient()
