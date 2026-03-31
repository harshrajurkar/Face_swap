import json
from collections.abc import Mapping
from typing import Any

import redis.asyncio as redis

from app.config import Settings


class QueueService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def enqueue(self, payload: Mapping[str, Any]) -> None:
        await self.redis.rpush(self.settings.queue_name, json.dumps(dict(payload)))

    async def dequeue(self, timeout: int = 5) -> dict[str, Any] | None:
        item = await self.redis.blpop(self.settings.queue_name, timeout=timeout)
        if not item:
            return None
        _, raw_payload = item
        return json.loads(raw_payload)

    async def ping(self) -> bool:
        return bool(await self.redis.ping())
