import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.services.face_service import FaceService, FaceSwapError
from app.services.job_store import JobStore
from app.services.queue_service import QueueService
from app.services.storage_service import StorageService


router = APIRouter(tags=['jobs'])


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    return StorageService(settings)


def get_job_store(settings: Settings = Depends(get_settings)) -> JobStore:
    return JobStore(settings)


def get_queue_service(settings: Settings = Depends(get_settings)) -> QueueService:
    return QueueService(settings)


@lru_cache(maxsize=1)
def _cached_face_service() -> FaceService:
    return FaceService(get_settings())


def get_face_service(_: Settings = Depends(get_settings)) -> FaceService:
    return _cached_face_service()


@router.post('/create-job', status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    source_image: UploadFile = File(...),
    target_image: UploadFile = File(...),
    prompt: str | None = Form(default=None),
    enhance_face: bool = Form(default=True),
    response_base_url: str | None = Form(default=None),
    storage_service: StorageService = Depends(get_storage_service),
    job_store: JobStore = Depends(get_job_store),
    queue_service: QueueService = Depends(get_queue_service),
    face_service: FaceService = Depends(get_face_service),
):
    if not source_image.content_type or not source_image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='Source file must be an image.')
    if not target_image.content_type or not target_image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='Target file must be an image.')

    job_id = str(uuid.uuid4())
    normalized_prompt = (prompt or '').strip() or None

    try:
        source_path = await storage_service.save_upload(job_id=job_id, kind='source', upload=source_image)
        target_path = await storage_service.save_upload(job_id=job_id, kind='target', upload=target_image)
        analysis = face_service.analyze_pair(source_path=source_path, target_path=target_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FaceSwapError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await job_store.create_job(
        job_id=job_id,
        source_path=source_path,
        target_path=target_path,
        prompt=normalized_prompt,
        enhance_face=enhance_face,
        response_base_url=response_base_url,
        similarity_percent=analysis['similarity_percent'],
        similarity_score=analysis['similarity_score'],
    )
    await queue_service.enqueue(
        {
            'job_id': job_id,
            'job_type': 'swap',
            'source_path': source_path,
            'target_path': target_path,
            'prompt': normalized_prompt or '',
            'enhance_face': enhance_face,
            'response_base_url': response_base_url or '',
        }
    )

    return {
        'job_id': job_id,
        'status': 'queued',
        'prompt': normalized_prompt,
        'enhance_face': enhance_face,
        'similarity_percent': analysis['similarity_percent'],
    }


@router.get('/job/{job_id}')
async def get_job(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
):
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found.')
    return job
