from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.config import Settings


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def save_upload(self, job_id: str, kind: str, upload: UploadFile) -> str:
        print(f"[DEBUG] Saving {kind} upload for job {job_id}")
        print(f"[DEBUG] Upload filename: {upload.filename}, content_type: {upload.content_type}")
        
        extension = Path(upload.filename or "").suffix.lower()
        print(f"[DEBUG] File extension: {extension}")
        
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            print(f"[ERROR] Invalid file extension: {extension}")
            raise ValueError("Only .jpg, .jpeg, .png, and .webp images are supported.")

        destination = self.settings.uploads_dir / f"{job_id}_{kind}{extension}"
        print(f"[DEBUG] Saving to: {destination}")
        
        async with aiofiles.open(destination, "wb") as file_handle:
            bytes_written = 0
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                await file_handle.write(chunk)
                bytes_written += len(chunk)
                print(f"[DEBUG] Written {bytes_written} bytes...")
        
        await upload.close()
        resolved_path = str(destination.resolve())
        print(f"[DEBUG] Upload complete: {resolved_path}")
        return resolved_path

    def build_output_path(self, job_id: str) -> str:
        return str((self.settings.outputs_dir / f"{job_id}.png").resolve())

    def build_output_url(self, job_id: str, response_base_url: str | None = None) -> str:
        relative = f"{self.settings.output_url_prefix}/{job_id}.png"
        if response_base_url:
            return f"{response_base_url.rstrip('/')}{relative}"
        return relative
