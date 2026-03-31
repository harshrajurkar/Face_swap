from pathlib import Path

import aiofiles
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import Settings


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def save_upload(self, job_id: str, kind: str, upload: UploadFile) -> str:
        extension = Path(upload.filename or '').suffix.lower()
        if extension not in {'.jpg', '.jpeg', '.png', '.webp'}:
            raise ValueError('Only .jpg, .jpeg, .png, and .webp images are supported.')

        destination = self.settings.uploads_dir / f'{job_id}_{kind}{extension}'
        total_bytes = 0

        try:
            async with aiofiles.open(destination, 'wb') as file_handle:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break

                    total_bytes += len(chunk)
                    if total_bytes > self.settings.max_upload_size_bytes:
                        raise ValueError(
                            f'Image exceeds the upload limit of {self.settings.max_upload_size_bytes // (1024 * 1024)} MB.'
                        )

                    await file_handle.write(chunk)

            self.validate_saved_image(destination)
            return str(destination.resolve())
        except Exception:
            self.remove_file(destination)
            raise
        finally:
            await upload.close()

    def build_output_path(self, job_id: str) -> str:
        return str((self.settings.outputs_dir / f'{job_id}.png').resolve())

    def build_debug_path(self, debug_id: str, kind: str) -> str:
        return str((self.settings.outputs_dir / 'debug' / f'{debug_id}_{kind}.png').resolve())

    def build_edited_output_path(self, job_id: str) -> str:
        return str((self.settings.outputs_dir / f'{job_id}_edited.png').resolve())

    def build_output_url(self, job_id: str, response_base_url: str | None = None) -> str:
        return self.build_asset_url(f'{job_id}.png', response_base_url)

    def build_asset_url(self, relative_output_path: str, response_base_url: str | None = None) -> str:
        normalized = relative_output_path.replace('\\', '/').lstrip('/')
        relative = f"{self.settings.output_url_prefix}/{normalized}"
        if response_base_url:
            return f"{response_base_url.rstrip('/')}{relative}"
        return relative

    @staticmethod
    def validate_saved_image(path: Path) -> None:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError('Uploaded file is not a valid supported image.') from exc

    @staticmethod
    def remove_file(path: str | Path) -> None:
        candidate = Path(path)
        if candidate.exists():
            candidate.unlink(missing_ok=True)

    def cleanup_job_files(self, *paths: str | Path | None) -> None:
        for path in paths:
            if path:
                self.remove_file(path)
