import json
from datetime import UTC, datetime
from pathlib import Path

import redis.asyncio as redis

from app.config import Settings
from app.services.storage_service import StorageService


class JobStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.storage = StorageService(settings)

    def _key(self, job_id: str) -> str:
        return f'job:{job_id}'

    async def create_job(
        self,
        job_id: str,
        source_path: str,
        target_path: str,
        prompt: str | None = None,
        enhance_face: bool = False,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        payload = {
            'job_id': job_id,
            'job_type': 'swap',
            'status': 'queued',
            'stage': 'queued',
            'progress': 5,
            'source_path': source_path,
            'target_path': target_path,
            'output_path': None,
            'output_url': None,
            'error': None,
            'prompt': prompt,
            'enhance_face': enhance_face,
            'similarity_percent': None,
            'similarity_score': None,
            'source_face_size': None,
            'target_face_size': None,
            'recommendations': [],
            'created_at': now,
            'updated_at': now,
        }
        await self.redis.set(self._key(job_id), json.dumps(payload), ex=self.settings.job_status_ttl_seconds)

    async def update_job(self, job_id: str, **changes) -> None:
        existing = await self.get_job(job_id)
        if not existing:
            return

        existing.update(changes)

        output_path = existing.get('output_path')
        if output_path:
            existing['output_url'] = self.storage.build_asset_url(Path(output_path).name)
        elif 'output_path' in changes:
            existing['output_url'] = None

        existing['updated_at'] = datetime.now(UTC).isoformat()

        await self.redis.set(self._key(job_id), json.dumps(existing), ex=self.settings.job_status_ttl_seconds)

    async def get_job(self, job_id: str):
        payload = await self.redis.get(self._key(job_id))
        if not payload:
            return None
        return json.loads(payload)
