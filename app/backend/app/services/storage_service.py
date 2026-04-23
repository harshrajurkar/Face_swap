from pathlib import Path
from urllib.parse import quote

import aiofiles
import boto3
from fastapi import UploadFile

from app.config import Settings


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.s3_client = boto3.client("s3") if self._use_s3() else None

    def _use_s3(self) -> bool:
        return self.settings.storage_mode.lower() == "s3" and bool(self.settings.s3_bucket_name)

    def is_s3_enabled(self) -> bool:
        return self._use_s3()

    def _uploads_key(self, filename: str) -> str:
        return f"{self.settings.s3_uploads_prefix.strip('/')}/{filename}"

    def _outputs_key(self, filename: str) -> str:
        return f"{self.settings.s3_outputs_prefix.strip('/')}/{filename}"

    def _upload_file_to_s3(self, local_path: str, key: str, content_type: str | None = None) -> None:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        with open(local_path, "rb") as file_handle:
            if extra_args:
                self.s3_client.upload_fileobj(
                    file_handle,
                    self.settings.s3_bucket_name,
                    key,
                    ExtraArgs=extra_args,
                )
            else:
                self.s3_client.upload_fileobj(
                    file_handle,
                    self.settings.s3_bucket_name,
                    key,
                )

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

        if self._use_s3():
            await self._upload_to_s3_async(
                resolved_path,
                self._uploads_key(destination.name),
                upload.content_type,
            )

        return resolved_path

    def build_output_path(self, job_id: str) -> str:
        return str((self.settings.outputs_dir / f"{job_id}.png").resolve())

    def build_output_url(self, job_id: str, response_base_url: str | None = None) -> str:
        relative = f"{self.settings.output_url_prefix}/{job_id}.png"
        if response_base_url:
            return f"{response_base_url.rstrip('/')}{relative}"
        return relative

    async def publish_output(self, job_id: str, output_path: str) -> None:
        if not self._use_s3():
            return

        await self._upload_to_s3_async(
            output_path,
            self._outputs_key(f"{job_id}.png"),
            "image/png",
        )

    async def _upload_to_s3_async(self, local_path: str, key: str, content_type: str | None = None) -> None:
        import asyncio

        await asyncio.to_thread(self._upload_file_to_s3, local_path, key, content_type)

    def build_presigned_output_url(self, filename: str, expires_in: int = 3600) -> str:
        if not self._use_s3():
            raise ValueError("S3 storage is not enabled.")

        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.settings.s3_bucket_name,
                "Key": self._outputs_key(filename),
                "ResponseContentType": "image/png",
                "ResponseContentDisposition": f'inline; filename="{quote(filename)}"',
            },
            ExpiresIn=expires_in,
        )
