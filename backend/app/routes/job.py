import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.schemas.job import CreateJobResponse, JobResponse
from app.services.job_store import JobStore
from app.services.queue_service import QueueService
from app.services.storage_service import StorageService


router = APIRouter(tags=['jobs'])
logger = logging.getLogger(__name__)


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    return StorageService(settings)


def get_job_store(settings: Settings = Depends(get_settings)) -> JobStore:
    return JobStore(settings)


def get_queue_service(settings: Settings = Depends(get_settings)) -> QueueService:
    return QueueService(settings)


@router.post('/create-job', status_code=status.HTTP_202_ACCEPTED, response_model=CreateJobResponse)
async def create_job(
    source_image: UploadFile = File(...),
    target_image: UploadFile = File(...),
    prompt: str | None = Form(default=None),
    enhance_face: bool = Form(default=True),
    is_video: bool = Form(default=False),
    storage_service: StorageService = Depends(get_storage_service),
    job_store: JobStore = Depends(get_job_store),
    queue_service: QueueService = Depends(get_queue_service),
):
    if not source_image.content_type or not source_image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='Source file must be an image.')

    if is_video:
        if not target_image.content_type or not target_image.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail='Target file must be a video when is_video=true.')
    elif not target_image.content_type or not target_image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='Target file must be an image.')

    job_id = str(uuid.uuid4())
    normalized_prompt = (prompt or '').strip() or None
    source_path = None
    target_path = None
    job_type = 'video_swap' if is_video else 'swap'

    try:
        source_path = await storage_service.save_image_upload(job_id=job_id, kind='source', upload=source_image)
        if is_video:
            target_path = await storage_service.save_video_upload(job_id=job_id, kind='target', upload=target_image)
        else:
            target_path = await storage_service.save_image_upload(job_id=job_id, kind='target', upload=target_image)
    except ValueError as exc:
        storage_service.cleanup_job_files(source_path, target_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception('Failed to save upload for job %s', job_id)
        storage_service.cleanup_job_files(source_path, target_path)
        raise HTTPException(status_code=500, detail='Unable to save uploaded files.') from exc

    await job_store.create_job(
        job_id=job_id,
        source_path=source_path,
        target_path=target_path,
        prompt=normalized_prompt,
        enhance_face=enhance_face,
        job_type=job_type,
        is_video=is_video,
    )

    try:
        await queue_service.enqueue(
            {
                'job_id': job_id,
                'job_type': job_type,
                'source_path': source_path,
                'target_path': target_path,
                'prompt': normalized_prompt or '',
                'enhance_face': enhance_face,
                'is_video': is_video,
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('Failed to enqueue job %s', job_id)
        storage_service.cleanup_job_files(source_path, target_path)
        await job_store.update_job(job_id, status='failed', stage='failed', progress=100, error='Queue unavailable.')
        raise HTTPException(status_code=503, detail='Job queue is unavailable. Try again in a moment.') from exc

    return {
        'job_id': job_id,
        'job_type': job_type,
        'status': 'queued',
        'stage': 'queued',
        'progress': 5,
        'prompt': normalized_prompt,
        'enhance_face': enhance_face,
        'is_video': is_video,
    }


@router.get('/job/{job_id}', response_model=JobResponse)
async def get_job(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
):
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found.')
    return job
