import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from typing import Optional, Tuple, List
from shared.config.settings import get_settings


class RedisClient:
    """
    Клиент для работы с Redis Streams.
    Поддерживает автоматическое переподключение и keepalive.
    """

    def __init__(self):
        self._settings = get_settings()
        self.client = self._make_client()

    def _make_client(self) -> redis.Redis:
        s = self._settings.redis_settings
        return redis.Redis(
            host=s.redis_host,
            port=s.redis_port,
            decode_responses=True,
            # TCP keepalive — детектит мёртвые соединения без ожидания таймаута
            socket_keepalive=True,
            # Таймауты на операции — не висеть вечно
            socket_timeout=5,
            socket_connect_timeout=5,
            # Периодический PING — держит соединение живым через NAT/фаерволы
            health_check_interval=15,
            # Автоповтор при временных сетевых ошибках
            retry=Retry(ExponentialBackoff(cap=2, base=0.1), retries=3),
            retry_on_timeout=True,
        )

    async def reconnect(self) -> None:
        """Пересоздаёт клиент после потери соединения."""
        try:
            await self.client.aclose()
        except Exception:
            pass
        self.client = self._make_client()
        print("[REDIS] Клиент пересоздан")

    async def create_consumer_group(
        self,
        stream_name: str,
        group_name: str,
        start_from_beginning: bool = True,
    ) -> None:
        start_id = "0" if start_from_beginning else "$"
        try:
            await self.client.xgroup_create(
                name=stream_name,
                groupname=group_name,
                id=start_id,
                mkstream=True,
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def push_message(
        self,
        stream_name: str,
        message: dict,
        maxlen: int = 10000,
    ):
        return await self.client.xadd(
            stream_name, message, maxlen=maxlen, approximate=True
        )

    async def read_messages(
        self,
        stream_name: str,
        last_id: str = "0",
        count: int = 10,
        block_ms: int = 2000,
    ) -> Optional[List[Tuple[str, dict]]]:
        """
        Читает сообщения из потока.
        block_ms > 0 — блокирующий XREAD: ждёт до block_ms мс появления новых данных.
        Возвращает None если сообщений нет.
        """
        result = await self.client.xread(
            {stream_name: last_id},
            count=count,
            block=block_ms,
        )
        if not result:
            return None
        return result[0][1]

    async def delete_message(self, stream_name: str, message_id: str) -> None:
        await self.client.xdel(stream_name, message_id)

    async def claim_message(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 1,
        block_ms: int = 5000,
    ) -> Optional[Tuple[str, dict]]:
        result = await self.client.xreadgroup(
            groupname=group_name,
            consumername=consumer_name,
            streams={stream_name: ">"},
            count=count,
            block=block_ms,
        )
        if not result or not result[0][1]:
            return None
        msg_id, data = result[0][1][0]
        return msg_id, data

    async def complete_message(
        self, stream_name: str, group_name: str, message_id: str
    ) -> None:
        await self.client.xack(stream_name, group_name, message_id)
        await self.client.xdel(stream_name, message_id)

    async def claim_pending_messages(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        min_idle_time_ms: int = 60000,
        count: int = 10,
    ) -> List[Tuple[str, dict]]:
        pending = await self.client.xpending_range(
            stream_name, group_name, min="-", max="+", count=count
        )
        pending_ids = [
            item["message_id"]
            for item in pending
            if item["time_since_delivered"] >= min_idle_time_ms
        ]
        if not pending_ids:
            return []
        claimed = await self.client.xclaim(
            stream_name, group_name, consumer_name,
            min_idle_time=min_idle_time_ms,
            message_ids=pending_ids,
        )
        return [(msg_id, data) for msg_id, data in claimed.items()]

    async def get_stream_length(self, stream_name: str) -> int:
        return await self.client.xlen(stream_name)

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
