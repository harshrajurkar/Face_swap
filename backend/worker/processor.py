import logging

from app.config import get_settings
from app.services.enhancement_service import EnhancementService
from app.services.face_service import FaceService
from app.services.job_store import JobStore
from app.services.storage_service import StorageService


logger = logging.getLogger(__name__)


class JobProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.face_service = FaceService(self.settings)
        self.enhancement_service = EnhancementService(self.settings)
        self.storage_service = StorageService(self.settings)
        self.job_store = JobStore(self.settings)

    async def process(self, job_payload):
        job_id = job_payload['job_id']
        await self.job_store.update_job(job_id, status='processing', stage='analyzing', progress=20, error=None)

        try:
            analysis = self.face_service.analyze_pair(
                source_path=job_payload['source_path'],
                target_path=job_payload['target_path'],
            )
            await self.job_store.update_job(
                job_id,
                similarity_percent=analysis['similarity_percent'],
                similarity_score=analysis['similarity_score'],
                source_face_size=analysis['source_face_size'],
                target_face_size=analysis['target_face_size'],
                recommendations=analysis['recommendations'],
                stage='swapping',
                progress=55,
            )

            output_path = self.storage_service.build_output_path(job_id)
            final_output = self.face_service.swap_faces(
                source_path=job_payload['source_path'],
                target_path=job_payload['target_path'],
                output_path=output_path,
            )

            if job_payload.get('enhance_face', True):
                await self.job_store.update_job(job_id, stage='enhancing', progress=82)
                final_output = self.enhancement_service.enhance_image(final_output, final_output)

            await self.job_store.update_job(
                job_id,
                status='completed',
                stage='completed',
                progress=100,
                output_path=final_output,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception('Job %s failed', job_id)
            await self.job_store.update_job(job_id, status='failed', stage='failed', progress=100, error=str(exc))
