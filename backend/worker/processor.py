import asyncio
import gc
import logging

from app.config import get_settings
from app.services.enhancement_service import EnhancementService
from app.services.face_service import FaceService
from app.services.job_store import JobStore
from app.services.storage_service import StorageService


logger = logging.getLogger("face-swap-worker.processor")


class JobProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.face_service = None
        self.enhancement_service = EnhancementService(self.settings)
        self.storage_service = StorageService(self.settings)
        self.job_store = JobStore(self.settings)

    def _get_face_service(self) -> FaceService:
        if self.face_service is None:
            self.face_service = FaceService(self.settings)
        return self.face_service

    async def process(self, job_payload):
        job_id = job_payload["job_id"]
        await self.job_store.update_job(
            job_id,
            status="processing",
            stage="preparing_models",
            progress=18,
            status_message="Preparing models and runtime dependencies.",
            error=None,
        )

        try:
            logger.info(
                "Job %s starting face swap. Source=%s Target=%s enhance=%s",
                job_id,
                job_payload["source_path"],
                job_payload["target_path"],
                job_payload.get("enhance_face", False),
            )

            await self.job_store.update_job(
                job_id,
                stage="running_swap",
                progress=35,
                status_message="Detecting faces and extracting regions (optimized processing).",
            )

            output_path = self.storage_service.build_output_path(job_id)
            logger.info("Job %s: output_path=%s", job_id, output_path)

            # Run face swap in thread pool to avoid blocking
            logger.debug("Job %s: Running face swap inference in thread pool", job_id)
            final_output = await asyncio.to_thread(
                self._get_face_service().swap_faces,
                source_path=job_payload["source_path"],
                target_path=job_payload["target_path"],
                output_path=output_path,
            )
            logger.info("Job %s: Face swap completed", job_id)

            if job_payload.get("enhance_face", False):
                await self.job_store.update_job(
                    job_id,
                    stage="enhancing",
                    progress=75,
                    status_message="Enhancing facial detail with GFPGAN.",
                )
                logger.info("Job %s: Starting enhancement", job_id)
                final_output = await asyncio.to_thread(
                    self.enhancement_service.enhance_image,
                    input_path=final_output,
                    output_path=final_output,
                )
                logger.info("Job %s: Enhancement completed", job_id)
            else:
                logger.debug("Job %s: Skipping enhancement (not requested)", job_id)

            await self.job_store.update_job(
                job_id,
                status="completed",
                stage="completed",
                progress=100,
                status_message="Face swap complete. Output ready for download.",
                output_path=final_output,
                error=None,
            )
            logger.info("Job %s: COMPLETED successfully. Output=%s", job_id, final_output)

        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            logger.exception("Job %s: FAILED with error: %s", job_id, error_msg)
            await self.job_store.update_job(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                status_message=f"Face swap failed: {error_msg}",
                error=error_msg,
            )
            raise

        finally:
            logger.debug("Job %s: Running garbage collection", job_id)
            gc.collect()
