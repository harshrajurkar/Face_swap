import asyncio
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote, urlparse

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

    def _to_s3_uri(self, key: str) -> str:
        return f"s3://{self.settings.s3_bucket_name}/{key.lstrip('/')}"

    def _parse_s3_reference(self, reference: str) -> tuple[str, str]:
        parsed = urlparse(reference)
        if parsed.scheme == "s3":
            return parsed.netloc, parsed.path.lstrip("/")

        if not self.settings.s3_bucket_name:
            raise ValueError("S3 bucket is required when storage_mode is s3.")
        return self.settings.s3_bucket_name, reference.lstrip("/")

    def _upload_file_to_s3(self, local_path: str, key: str, content_type: str | None = None) -> None:
        extra_args = {"ContentType": content_type} if content_type else None
        with open(local_path, "rb") as file_handle:
            self.s3_client.upload_fileobj(
                file_handle,
                self.settings.s3_bucket_name,
                key,
                ExtraArgs=extra_args or {},
            )

    def _upload_fileobj_to_s3(self, file_obj: BinaryIO, key: str, content_type: str | None = None) -> None:
        file_obj.seek(0)
        extra_args = {"ContentType": content_type} if content_type else None
        self.s3_client.upload_fileobj(
            file_obj,
            self.settings.s3_bucket_name,
            key,
            ExtraArgs=extra_args or {},
        )

    def _download_file_from_s3(self, bucket: str, key: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as file_handle:
            self.s3_client.download_fileobj(bucket, key, file_handle)

    async def save_upload(self, job_id: str, kind: str, upload: UploadFile) -> str:
        extension = Path(upload.filename or "").suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("Only .jpg, .jpeg, .png, and .webp images are supported.")

        filename = f"{job_id}_{kind}{extension}"
        if self._use_s3():
            key = self._uploads_key(filename)
            await asyncio.to_thread(self._upload_fileobj_to_s3, upload.file, key, upload.content_type)
            await upload.close()
            return self._to_s3_uri(key)

        destination = self.settings.uploads_dir / filename
        async with aiofiles.open(destination, "wb") as file_handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                await file_handle.write(chunk)
        await upload.close()
        return str(destination.resolve())

    async def materialize_input(self, job_id: str, kind: str, reference: str) -> str:
        if not self._use_s3():
            return reference

        bucket, key = self._parse_s3_reference(reference)
        extension = Path(key).suffix or ".bin"
        destination = self.settings.uploads_dir / f"{job_id}_{kind}_input{extension}"
        await asyncio.to_thread(self._download_file_from_s3, bucket, key, destination)
        return str(destination.resolve())

    def build_output_path(self, job_id: str) -> str:
        return str((self.settings.outputs_dir / f"{job_id}.png").resolve())

    def build_output_url(self, job_id: str, response_base_url: str | None = None) -> str:
        relative = f"{self.settings.output_url_prefix}/{job_id}.png"
        if response_base_url:
            return f"{response_base_url.rstrip('/')}{relative}"
        return relative

    def build_output_object_reference(self, job_id: str) -> str:
        if not self._use_s3():
            return self.build_output_path(job_id)
        return self._to_s3_uri(self._outputs_key(f"{job_id}.png"))

    async def publish_output(self, job_id: str, output_path: str) -> None:
        if not self._use_s3():
            return

        await asyncio.to_thread(
            self._upload_file_to_s3,
            output_path,
            self._outputs_key(f"{job_id}.png"),
            "image/png",
        )

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

    def get_output_object(self, filename: str):
        if not self._use_s3():
            raise ValueError("S3 storage is not enabled.")

        return self.s3_client.get_object(
            Bucket=self.settings.s3_bucket_name,
            Key=self._outputs_key(filename),
        )
