from datetime import datetime

from pydantic import BaseModel, Field


class CreateJobResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int = Field(ge=0, le=100)
    prompt: str | None = None
    enhance_face: bool


class JobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    stage: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    source_path: str
    target_path: str
    output_path: str | None = None
    output_url: str | None = None
    error: str | None = None
    prompt: str | None = None
    enhance_face: bool
    similarity_percent: float | None = None
    similarity_score: float | None = None
    source_face_size: float | None = None
    target_face_size: float | None = None
    recommendations: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
