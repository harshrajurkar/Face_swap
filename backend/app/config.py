from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Face Swap"
    api_prefix: str = "/api"
    host: str = "0.0.0.0"
    port: int = 8000
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "face_swap_jobs"
    uploads_dir: Path = Path("uploads")
    outputs_dir: Path = Path("outputs")
    output_url_prefix: str = "/outputs"
    insightface_model_name: str = "buffalo_l"
    insightface_model_dir: Path = Path("models")
    inswapper_model_path: Path = Path("models/inswapper_128.onnx")
    inswapper_model_url: str = "https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx"
    gfpgan_model_path: Path = Path("models/GFPGANv1.3.pth")
    gfpgan_model_url: str = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth"
    execution_provider: str = "CPUExecutionProvider"
    job_status_ttl_seconds: int = 60 * 60 * 24
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.insightface_model_dir.mkdir(parents=True, exist_ok=True)
    settings.gfpgan_model_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
