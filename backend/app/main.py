from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes.job import router as job_router
from app.services.queue_service import QueueService


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(job_router, prefix=settings.api_prefix)
app.mount('/outputs', StaticFiles(directory=str(settings.outputs_dir)), name='outputs')


@app.get('/health', tags=['health'])
async def health_check() -> dict[str, object]:
    queue = QueueService(settings)
    redis_ok = False
    try:
        redis_ok = await queue.ping()
    except Exception:  # noqa: BLE001
        redis_ok = False

    models = {
        'inswapper': settings.inswapper_model_path.exists(),
        'gfpgan': settings.gfpgan_model_path.exists(),
    }
    status_label = 'ok' if redis_ok else 'degraded'
    return {'status': status_label, 'redis': redis_ok, 'models': models}
