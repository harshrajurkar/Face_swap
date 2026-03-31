import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.services.job_store import JobStore


class JobStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            uploads_dir=root / 'uploads',
            outputs_dir=root / 'outputs',
            insightface_model_dir=root / 'models',
            gfpgan_model_path=root / 'models' / 'GFPGANv1.3.pth',
        )
        self.store = JobStore(self.settings)
        self.store.redis = AsyncMock()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_update_job_builds_output_url(self) -> None:
        payload = {
            'job_id': 'job-123',
            'job_type': 'swap',
            'status': 'processing',
            'stage': 'swapping',
            'progress': 55,
            'source_path': 'source.png',
            'target_path': 'target.png',
            'output_path': None,
            'output_url': None,
            'error': None,
            'prompt': None,
            'enhance_face': True,
            'similarity_percent': None,
            'similarity_score': None,
            'source_face_size': None,
            'target_face_size': None,
            'recommendations': [],
            'created_at': '2026-01-01T00:00:00+00:00',
            'updated_at': '2026-01-01T00:00:00+00:00',
        }
        self.store.redis.get.return_value = json.dumps(payload)

        await self.store.update_job('job-123', status='completed', output_path='C:/tmp/job-123.png')

        self.store.redis.set.assert_awaited()
        stored_payload = json.loads(self.store.redis.set.await_args.args[1])
        self.assertEqual(stored_payload['output_url'], '/outputs/job-123.png')
        self.assertEqual(stored_payload['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
