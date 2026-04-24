from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from app.config import get_settings
from app.routes.job import router as job_router
from app.services.storage_service import StorageService


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(job_router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/outputs/{filename}", tags=["outputs"])
async def get_output_file(filename: str):
    storage_service = StorageService(settings)
    safe_filename = Path(filename).name

    if storage_service._use_s3():
        return RedirectResponse(url=storage_service.build_presigned_output_url(safe_filename))

    output_path = settings.outputs_dir / safe_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found.")
    return FileResponse(output_path)


@app.get("/", include_in_schema=False)
async def root():
    return {"status": "ok"}
