from pathlib import Path

import aiofiles
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import Settings


class StorageService:
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.webm'}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def save_upload(self, job_id: str, kind: str, upload: UploadFile) -> str:
        return await self.save_image_upload(job_id=job_id, kind=kind, upload=upload)

    async def save_image_upload(self, job_id: str, kind: str, upload: UploadFile) -> str:
        destination = await self._save_binary_upload(
            job_id=job_id,
            kind=kind,
            upload=upload,
            allowed_extensions=self.IMAGE_EXTENSIONS,
            size_limit=self.settings.max_upload_size_bytes,
            invalid_message='Only .jpg, .jpeg, .png, and .webp images are supported.',
        )
        self.validate_saved_image(destination)
        return str(destination.resolve())

    async def save_video_upload(self, job_id: str, kind: str, upload: UploadFile) -> str:
        destination = await self._save_binary_upload(
            job_id=job_id,
            kind=kind,
            upload=upload,
            allowed_extensions=self.VIDEO_EXTENSIONS,
            size_limit=self.settings.max_video_upload_size_bytes,
            invalid_message='Only .mp4, .mov, .mkv, .avi, and .webm videos are supported.',
        )
        return str(destination.resolve())

    async def _save_binary_upload(
        self,
        job_id: str,
        kind: str,
        upload: UploadFile,
        *,
        allowed_extensions: set[str],
        size_limit: int,
        invalid_message: str,
    ) -> Path:
        extension = Path(upload.filename or '').suffix.lower()
        if extension not in allowed_extensions:
            raise ValueError(invalid_message)

        destination = self.settings.uploads_dir / f'{job_id}_{kind}{extension}'
        total_bytes = 0

        try:
            async with aiofiles.open(destination, 'wb') as file_handle:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break

                    total_bytes += len(chunk)
                    if total_bytes > size_limit:
                        raise ValueError(f'Upload exceeds the limit of {size_limit // (1024 * 1024)} MB.')

                    await file_handle.write(chunk)

            return destination
        except Exception:
            self.remove_file(destination)
            raise
        finally:
            await upload.close()

    def build_output_path(self, job_id: str) -> str:
        return str((self.settings.outputs_dir / f'{job_id}.png').resolve())

    def build_video_output_path(self, job_id: str) -> str:
        return str((self.settings.outputs_dir / f'{job_id}.mp4').resolve())

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

    def build_temp_job_directories(self, job_id: str) -> tuple[Path, Path, Path]:
        root = self.settings.temp_frames_dir / job_id
        frames_dir = root / 'frames'
        processed_dir = root / 'processed'
        frames_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)
        return root, frames_dir, processed_dir

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

    @staticmethod
    def remove_directory(path: str | Path) -> None:
        directory = Path(path)
        if directory.exists():
            for candidate in sorted(directory.rglob('*'), reverse=True):
                if candidate.is_file():
                    candidate.unlink(missing_ok=True)
                else:
                    candidate.rmdir()
            directory.rmdir()
