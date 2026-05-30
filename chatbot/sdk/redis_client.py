import redis.asyncio as redis
from typing import Optional, Tuple, List
from shared.config.settings import get_settings


class RedisClient:
    """
    Клиент для работы с Redis Streams.
    Каждый тип задач имеет свой поток и свою группу потребителей.
    """

    def __init__(self):
        settings = get_settings()
        self.client = redis.Redis(
            host=settings.redis_settings.redis_host,
            port=settings.redis_settings.redis_port,
            decode_responses=True
        )

    async def create_consumer_group(
            self,
            stream_name: str,
            group_name: str,
            start_from_beginning: bool = True
    ) -> None:
        """
        Создаёт группу потребителей для потока.

        Args:
            stream_name: Имя потока (например, "tasks:summarize")
            group_name: Имя группы (например, "summarize_workers")
            start_from_beginning: Если True - читать все сообщения с начала
        """
        start_id = "0" if start_from_beginning else "$"

        try:
            await self.client.xgroup_create(
                name=stream_name,
                groupname=group_name,
                id=start_id,
                mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def push_message(
            self,
            stream_name: str,
            message: dict,
            maxlen: int = 10000
    ):
        """
        Добавляет сообщение в конкретный поток.

        Args:
            stream_name: Имя потока (определяет тип задачи)
            message: Словарь с данными
            maxlen: Максимальная длина потока (автоочистка)
        """
        return await self.client.xadd(
            stream_name,
            message,
            maxlen=maxlen,
            approximate=True
        )

    async def read_messages(
            self,
            stream_name: str,
            last_id: str = "0",
            count: int = 10,
            block_ms: int = 0
    ) -> Optional[List[Tuple[str, dict]]]:
        """
        Простое чтение сообщений из потока (без групп).

        Args:
            stream_name: Имя потока
            last_id: ID последнего прочитанного сообщения ("0" - всё сначала, "$" - только новые)
            count: Количество сообщений
            block_ms: Время ожидания в миллисекундах (0 - не ждать, вернуть сразу)

        Returns:
            Список кортежей (message_id, data) или None, если сообщений нет
        """
        result = await self.client.xread(
            {stream_name: last_id},
            count=count,
            block=block_ms
        )

        if not result:
            return None

        return result[0][1]  # Возвращаем [(msg_id, data), ...]

    async def claim_message(
            self,
            stream_name: str,
            group_name: str,
            consumer_name: str,
            count: int = 1,
            block_ms: int = 5000
    ) -> Optional[Tuple[str, dict]]:
        """
        Забирает сообщение из потока используя группу потребителей.
        Все сообщения в этом потоке подходят воркеру, фильтрация не нужна.
        """
        result = await self.client.xreadgroup(
            groupname=group_name,
            consumername=consumer_name,
            streams={stream_name: ">"},
            count=count,
            block=block_ms
        )

        if not result or not result[0][1]:
            return None

        msg_id, data = result[0][1][0]
        return msg_id, data

    async def complete_message(
            self,
            stream_name: str,
            group_name: str,
            message_id: str
    ) -> None:
        """Подтверждает и удаляет обработанное сообщение."""
        await self.client.xack(stream_name, group_name, message_id)
        await self.client.xdel(stream_name, message_id)

    async def delete_message(
            self,
            stream_name: str,
            message_id: str
    ) -> None:
        """Удаляет сообщение из потока (без подтверждения группы)."""
        await self.client.xdel(stream_name, message_id)

    async def claim_pending_messages(
            self,
            stream_name: str,
            group_name: str,
            consumer_name: str,
            min_idle_time_ms: int = 60000,
            count: int = 10
    ) -> List[Tuple[str, dict]]:
        """Забирает зависшие сообщения (воркеры упали)."""
        pending_ids = []
        pending = await self.client.xpending_range(
            stream_name, group_name, min="-", max="+", count=count
        )

        for item in pending:
            if item['time_since_delivered'] >= min_idle_time_ms:
                pending_ids.append(item['message_id'])

        if not pending_ids:
            return []

        claimed = await self.client.xclaim(
            stream_name, group_name, consumer_name,
            min_idle_time=min_idle_time_ms,
            message_ids=pending_ids
        )

        return [(msg_id, data) for msg_id, data in claimed.items()]

    async def get_stream_length(self, stream_name: str) -> int:
        """Возвращает количество сообщений в потоке."""
        return await self.client.xlen(stream_name)

    async def close(self):
        await self.client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()