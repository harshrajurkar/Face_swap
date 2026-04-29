from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator

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

# Expose app-level HTTP metrics for Prometheus scraping.
Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(
    app,
    include_in_schema=False,
    endpoint="/metrics",
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/outputs/{filename}", tags=["outputs"])
async def get_output_file(filename: str, download: bool = Query(default=False)):
    storage_service = StorageService(settings)
    safe_filename = Path(filename).name

    if storage_service._use_s3():
        try:
            output_object = storage_service.get_output_object(safe_filename)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=404, detail="Output file not found.") from exc

        disposition = "attachment" if download else "inline"
        return StreamingResponse(
            output_object["Body"].iter_chunks(),
            media_type=output_object.get("ContentType") or "image/png",
            headers={
                "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
                "Cache-Control": "private, max-age=300",
            },
        )

    output_path = settings.outputs_dir / safe_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found.")
    return FileResponse(
        output_path,
        media_type="image/png",
        filename=safe_filename if download else None,
        content_disposition_type="attachment" if download else "inline",
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"status": "ok"}
