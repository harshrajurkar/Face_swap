import asyncio
import gc
import logging
import asyncio

from app.config import get_settings
from app.services.enhancement_service import EnhancementService
from app.services.face_service import FaceService
from app.services.job_store import JobStore
from app.services.storage_service import StorageService


logger = logging.getLogger("face-swap-worker.processor")


class JobProcessor:
    def __init__(self) -> None:
        print("[DEBUG] JobProcessor.__init__() starting")
        self.settings = get_settings()
        print(f"[DEBUG] Settings loaded: execution_provider={self.settings.execution_provider}")
        self.face_service = None
        print("[DEBUG] Initializing EnhancementService...")
        self.enhancement_service = EnhancementService(self.settings)
        print("[DEBUG] EnhancementService initialized")
        print("[DEBUG] Initializing StorageService...")
        self.storage_service = StorageService(self.settings)
        print("[DEBUG] StorageService initialized")
        print("[DEBUG] Initializing JobStore...")
        self.job_store = JobStore(self.settings)
        print("[DEBUG] JobStore initialized")
        print("[DEBUG] JobProcessor.__init__() complete\n")

    def _get_face_service(self) -> FaceService:
        if self.face_service is None:
            print("[DEBUG] Lazy-loading FaceService (first time)...")
            self.face_service = FaceService(self.settings)
            print("[DEBUG] FaceService loaded successfully")
        return self.face_service

    async def process(self, job_payload):
        job_id = job_payload["job_id"]
        print(f"\n[DEBUG] process() called for job_id={job_id}")
        print(f"[DEBUG] Job payload keys: {list(job_payload.keys())}")
        
        await self.job_store.update_job(
            job_id,
            status="processing",
            stage="preparing_models",
            progress=18,
            status_message="Preparing models and runtime dependencies.",
            error=None,
        )
        print(f"[DEBUG] Job status updated to 'processing'")

        try:
            source_path = job_payload["source_path"]
            target_path = job_payload["target_path"]
            enhance_face = job_payload.get("enhance_face", False)
            print(f"[DEBUG] Job details:")
            print(f"  - source_path: {source_path}")
            print(f"  - target_path: {target_path}")
            print(f"  - enhance_face: {enhance_face}")
            
            logger.info(
                "Job %s starting face swap. Source=%s Target=%s enhance=%s",
                job_id,
                source_path,
                target_path,
                enhance_face,
            )

            await self.job_store.update_job(
                job_id,
                stage="running_swap",
                progress=35,
                status_message="Detecting faces and extracting regions (optimized processing).",
            )

            output_path = self.storage_service.build_output_path(job_id)
            print(f"[DEBUG] Output path: {output_path}")
            logger.info("Job %s: output_path=%s", job_id, output_path)

            # Run face swap in thread pool to avoid blocking
            print(f"[DEBUG] Loading FaceService...")
            face_service = self._get_face_service()
            print(f"[DEBUG] Running face swap inference in thread pool")
            logger.debug("Job %s: Running face swap inference in thread pool", job_id)
            
            final_output = await asyncio.to_thread(
                face_service.swap_faces,
                source_path,
                target_path,
                output_path,
        )
            print(f"[SUCCESS] ✓ Face swap completed")
            logger.info("Job %s: Face swap completed", job_id)

            if enhance_face:
                print(f"[DEBUG] Enhancement requested - starting GFPGAN enhancement")
                await self.job_store.update_job(
                    job_id,
                    stage="enhancing",
                    progress=75,
                    status_message="Enhancing facial detail with GFPGAN.",
                )
                print(f"[DEBUG] Job status updated to 'enhancing'")
                logger.info("Job %s: Starting enhancement", job_id)
                
                print(f"[DEBUG] Running enhancement in thread pool")
                final_output = await asyncio.to_thread(
                    self.enhancement_service.enhance_image,
                    input_path=final_output,
                    output_path=final_output,
                )
                print(f"[SUCCESS] ✓ Enhancement completed")
                logger.info("Job %s: Enhancement completed", job_id)
            else:
                print(f"[DEBUG] Enhancement skipped (not requested)")
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
            print(f"[ERROR] ✗ Job {job_id} FAILED with exception:")
            print(f"  Exception type: {type(exc).__name__}")
            print(f"  Message: {error_msg}")
            import traceback
            print(f"  Traceback:\n{traceback.format_exc()}")
            logger.exception("Job %s: FAILED with error: %s", job_id, error_msg)
            await self.job_store.update_job(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                status_message=f"Face swap failed: {error_msg}",
                error=error_msg,
            )
            print(f"[DEBUG] Job marked as failed in database")
            raise

        finally:
            print(f"[DEBUG] Running garbage collection")
            logger.debug("Job %s: Running garbage collection", job_id)
            gc.collect()
            print(f"[DEBUG] Garbage collection complete")
