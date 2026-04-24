import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.services.job_store import JobStore
from app.services.queue_service import QueueService
from app.services.storage_service import StorageService


router = APIRouter(tags=["jobs"])


def get_storage_service(settings: Settings = Depends(get_settings)) -> StorageService:
    return StorageService(settings)


def get_job_store(settings: Settings = Depends(get_settings)) -> JobStore:
    return JobStore(settings)


def get_queue_service(settings: Settings = Depends(get_settings)) -> QueueService:
    return QueueService(settings)


@router.post("/create-job", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    source_image: UploadFile = File(...),
    target_image: UploadFile = File(...),
    prompt: str | None = Form(default=None),
    enhance_face: bool = Form(default=False),
    response_base_url: str | None = Form(default=None),
    storage_service: StorageService = Depends(get_storage_service),
    job_store: JobStore = Depends(get_job_store),
    queue_service: QueueService = Depends(get_queue_service),
):
    print(f"\n[DEBUG] create_job() endpoint called")
    print(f"[DEBUG] source_image: {source_image.filename}, target_image: {target_image.filename}")
    print(f"[DEBUG] enhance_face: {enhance_face}, response_base_url: {response_base_url}")
    
    if not source_image.content_type or not source_image.content_type.startswith("image/"):
        print(f"[ERROR] Invalid source image content type: {source_image.content_type}")
        raise HTTPException(status_code=400, detail="Source file must be an image.")
    if not target_image.content_type or not target_image.content_type.startswith("image/"):
        print(f"[ERROR] Invalid target image content type: {target_image.content_type}")
        raise HTTPException(status_code=400, detail="Target file must be an image.")

    job_id = str(uuid.uuid4())
    print(f"[DEBUG] Generated job_id: {job_id}")
    
    normalized_prompt = (prompt or "").strip() or None
    print(f"[DEBUG] Normalized prompt: {normalized_prompt}")
    
    try:
        print(f"[DEBUG] Saving source image...")
        source_path = await storage_service.save_upload(job_id=job_id, kind="source", upload=source_image)
        print(f"[DEBUG] Source saved: {source_path}")
        
        print(f"[DEBUG] Saving target image...")
        target_path = await storage_service.save_upload(job_id=job_id, kind="target", upload=target_image)
        print(f"[DEBUG] Target saved: {target_path}")
    except ValueError as exc:
        print(f"[ERROR] Save upload failed: {str(exc)}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    print(f"[DEBUG] Creating job in store...")
    await job_store.create_job(
        job_id=job_id,
        source_path=source_path,
        target_path=target_path,
        prompt=normalized_prompt,
        enhance_face=enhance_face,
        response_base_url=response_base_url,
    )
    print(f"[DEBUG] Job created in store")
    
    print(f"[DEBUG] Enqueueing job...")
    await queue_service.enqueue(
        {
            "job_id": job_id,
            "source_path": source_path,
            "target_path": target_path,
            "prompt": normalized_prompt or "",
            "enhance_face": enhance_face,
            "response_base_url": response_base_url or "",
        }
    )
    print(f"[SUCCESS] ✓ Job {job_id} created and queued")

    return {"job_id": job_id, "status": "queued", "prompt": normalized_prompt, "enhance_face": enhance_face}


@router.get("/job/{job_id}")
async def get_job(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
):
    print(f"[DEBUG] get_job() endpoint called for job_id={job_id}")
    job = await job_store.get_job(job_id)
    if not job:
        print(f"[ERROR] Job not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found.")
    print(f"[DEBUG] Job status: {job.get('status')}, progress: {job.get('progress')}%")
    return job
