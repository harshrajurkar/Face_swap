import asyncio
import json
from collections.abc import Mapping
from typing import Any

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.config import Settings


class QueueService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def _with_retry(self, operation):
        last_error = None
        for attempt in range(3):
            try:
                return await operation()
            except (OSError, RedisConnectionError, RedisTimeoutError) as exc:
                last_error = exc
                if attempt == 2:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
        raise last_error

    async def enqueue(self, payload: Mapping[str, Any]) -> None:
        await self._with_retry(lambda: self.redis.rpush(self.settings.queue_name, json.dumps(dict(payload))))

    async def requeue(self, payload: Mapping[str, Any]) -> None:
        await self.enqueue(payload)

    async def dequeue(self, timeout: int = 5) -> dict[str, Any] | None:
        item = await self._with_retry(lambda: self.redis.blpop(self.settings.queue_name, timeout=timeout))
        if not item:
            return None
        _, raw_payload = item
        return json.loads(raw_payload)
