import asyncio
import json
from datetime import UTC, datetime

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.config import Settings
from app.services.storage_service import StorageService


class JobStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.storage = StorageService(settings)

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

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

    async def create_job(
        self,
        job_id: str,
        source_path: str,
        target_path: str,
        prompt: str | None = None,
        enhance_face: bool = False,
        response_base_url: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        payload = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "progress": 5,
            "status_message": "Files uploaded and waiting for the worker.",
            "source_path": source_path,
            "target_path": target_path,
            "output_path": None,
            "output_url": None,
            "error": None,
            "prompt": prompt,
            "enhance_face": enhance_face,
            "created_at": now,
            "updated_at": now,
            "response_base_url": response_base_url,
        }
        await self._with_retry(
            lambda: self.redis.set(self._key(job_id), json.dumps(payload), ex=self.settings.job_status_ttl_seconds)
        )

    async def update_job(
        self,
        job_id: str,
        status: str | None = None,
        output_path: str | None = None,
        error: str | None = None,
        stage: str | None = None,
        progress: int | None = None,
        status_message: str | None = None,
    ) -> None:
        existing = await self.get_job(job_id)
        if not existing:
            return

        if status is not None:
            existing["status"] = status
        if stage is not None:
            existing["stage"] = stage
        if progress is not None:
            existing["progress"] = progress
        if status_message is not None:
            existing["status_message"] = status_message
        if output_path is not None:
            await self.storage.publish_output(job_id, output_path)
            if self.storage.is_s3_enabled():
                existing["output_path"] = self.storage.build_output_object_reference(job_id)
                # Keep downloads on the ALB origin; the backend streams S3 objects from /outputs.
                existing["output_url"] = self.storage.build_output_url(job_id, existing.get("response_base_url"))
            else:
                existing["output_path"] = output_path
                existing["output_url"] = self.storage.build_output_url(job_id, existing.get("response_base_url"))
        if error is not None or status == "failed":
            existing["error"] = error
        existing["updated_at"] = datetime.now(UTC).isoformat()

        await self._with_retry(
            lambda: self.redis.set(self._key(job_id), json.dumps(existing), ex=self.settings.job_status_ttl_seconds)
        )

    async def get_job(self, job_id: str):
        payload = await self._with_retry(lambda: self.redis.get(self._key(job_id)))
        if not payload:
            return None
        return json.loads(payload)
