import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image
from starlette.datastructures import UploadFile

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.services.storage_service import StorageService


class StorageServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            uploads_dir=root / 'uploads',
            outputs_dir=root / 'outputs',
            insightface_model_dir=root / 'models',
            gfpgan_model_path=root / 'models' / 'GFPGANv1.3.pth',
            max_upload_size_bytes=1024 * 1024,
        )
        self.settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.service = StorageService(self.settings)

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_save_upload_rejects_invalid_image(self) -> None:
        upload = UploadFile(filename='bad.png', file=BytesIO(b'not-an-image'))
        with self.assertRaises(ValueError):
            await self.service.save_upload('job1', 'source', upload)

    async def test_save_upload_persists_valid_image(self) -> None:
        image_bytes = BytesIO()
        Image.new('RGB', (32, 32), color='white').save(image_bytes, format='PNG')
        image_bytes.seek(0)
        upload = UploadFile(filename='good.png', file=image_bytes)

        saved_path = await self.service.save_upload('job2', 'source', upload)

        self.assertTrue(Path(saved_path).exists())
        self.assertEqual(self.service.build_asset_url('job2.png'), '/outputs/job2.png')


if __name__ == '__main__':
    unittest.main()
