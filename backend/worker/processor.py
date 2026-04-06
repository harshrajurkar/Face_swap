import logging
from pathlib import Path

from app.config import get_settings
from app.services.enhancement_service import EnhancementService
from app.services.face_service import FaceService
from app.services.job_store import JobStore
from app.services.storage_service import StorageService
from app.services.video_service import VideoProcessingError, VideoService


logger = logging.getLogger(__name__)


class JobProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.face_service = FaceService(self.settings)
        self.enhancement_service = EnhancementService(self.settings)
        self.storage_service = StorageService(self.settings)
        self.job_store = JobStore(self.settings)
        self.video_service = VideoService(
            self.settings,
            self.face_service,
            self.enhancement_service,
            self.storage_service,
        )

    async def process(self, job_payload):
        job_type = job_payload.get('job_type', 'swap')
        if job_type == 'video_swap':
            await self._process_video_job(job_payload)
            return

        await self._process_image_job(job_payload)

    async def _process_image_job(self, job_payload) -> None:
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

    async def _process_video_job(self, job_payload) -> None:
        job_id = job_payload['job_id']
        _, frames_dir, processed_dir = self.video_service.prepare_job_directories(job_id)

        try:
            await self.job_store.update_job(job_id, status='extracting_frames', stage='extracting_frames', progress=10, error=None)
            metadata = self.video_service.extract_frames(job_payload['target_path'], frames_dir)
            first_frame = next(iter(sorted(Path(frames_dir).glob('frame_*.png'))), None)
            analysis = None
            if first_frame is not None:
                analysis = self.face_service.analyze_pair(job_payload['source_path'], str(first_frame))

            await self.job_store.update_job(
                job_id,
                status='processing_frames',
                stage='processing_frames',
                progress=35,
                frame_count=metadata['frame_count'],
                processed_frame_count=0,
                skipped_frame_count=0,
                similarity_percent=analysis['similarity_percent'] if analysis else None,
                similarity_score=analysis['similarity_score'] if analysis else None,
                source_face_size=analysis['source_face_size'] if analysis else None,
                target_face_size=analysis['target_face_size'] if analysis else None,
                recommendations=analysis['recommendations'] if analysis else [],
            )

            async def update_frame_progress(processed_frames: int, total_frames: int, skipped_frames: int) -> None:
                processed_ratio = processed_frames / max(total_frames, 1)
                progress = min(84, 35 + int(processed_ratio * 49))
                await self.job_store.update_job(
                    job_id,
                    status='processing_frames',
                    stage='processing_frames',
                    progress=progress,
                    frame_count=total_frames,
                    processed_frame_count=processed_frames,
                    skipped_frame_count=skipped_frames,
                )

            frame_summary = await self.video_service.process_frames(
                job_id,
                job_payload['source_path'],
                frames_dir,
                processed_dir,
                enhance_face=job_payload.get('enhance_face', True),
                progress_callback=update_frame_progress,
            )

            await self.job_store.update_job(
                job_id,
                status='rebuilding_video',
                stage='rebuilding_video',
                progress=88,
                processed_frame_count=frame_summary['processed_frame_count'],
                skipped_frame_count=frame_summary['skipped_frame_count'],
            )

            output_path = self.storage_service.build_video_output_path(job_id)
            final_output = self.video_service.rebuild_video(
                processed_dir,
                output_path,
                framerate=int(metadata['fps']),
                source_video_path=job_payload['target_path'],
            )

            await self.job_store.update_job(
                job_id,
                status='completed',
                stage='completed',
                progress=100,
                output_path=final_output,
                error=None,
            )
        except (VideoProcessingError, Exception) as exc:  # noqa: BLE001
            logger.exception('Video job %s failed', job_id)
            await self.job_store.update_job(job_id, status='failed', stage='failed', progress=100, error=str(exc))
        finally:
            self.video_service.cleanup_job(job_id)
