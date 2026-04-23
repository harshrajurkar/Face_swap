import asyncio
import logging
from collections.abc import Mapping

from app.config import get_settings
from app.services.queue_service import QueueService
from worker.processor import JobProcessor


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("face-swap-worker")


def _build_retry_payload(job: Mapping[str, object], retry_count: int) -> dict[str, object]:
    payload = dict(job)
    payload["retry_count"] = retry_count
    return payload


async def run_worker() -> None:
    print("\n=== WORKER STARTING ===")
    settings = get_settings()
    print(f"[DEBUG] Settings loaded: queue_name={settings.queue_name}")
    queue = QueueService(settings)
    print("[DEBUG] QueueService initialized")
    processor = JobProcessor()
    print("[DEBUG] JobProcessor initialized")
    await processor.preload_models()
    print("[DEBUG] Model warmup step finished")
    concurrency = max(1, settings.worker_concurrency)

    logger.info(
        "Worker started on queue '%s' with concurrency=%s timeout=%ss max_retries=%s.",
        settings.queue_name,
        concurrency,
        settings.worker_job_timeout_seconds,
        settings.worker_max_retries,
    )
    print(f"[INFO] Worker configuration: concurrency={concurrency}, timeout={settings.worker_job_timeout_seconds}s")
    if concurrency != 1:
        logger.warning("This worker image is optimized for one job at a time. For scale-out, run more worker containers.")
        print("[WARNING] Concurrency != 1")

    while True:
        print(f"[DEBUG] Polling for jobs (timeout=5s)...")
        job = await queue.dequeue(timeout=5)
        if not job:
            print(f"[DEBUG] No job received, sleeping for {settings.worker_poll_interval_seconds}s")
            await asyncio.sleep(settings.worker_poll_interval_seconds)
            continue

        retry_count = int(job.get("retry_count", 0))
        job_id = job.get("job_id")
        print(f"\n[INFO] ====== JOB DEQUEUED: {job_id} (attempt {retry_count + 1}/{settings.worker_max_retries + 1}) ======")
        logger.info("Processing job %s (attempt %s/%s)", job_id, retry_count + 1, settings.worker_max_retries + 1)
        try:
            await asyncio.wait_for(
                processor.process(job),
                timeout=settings.worker_job_timeout_seconds,
            )
            logger.info("Completed job %s", job.get("job_id"))
        except asyncio.TimeoutError:
            logger.exception("Job %s timed out after %s seconds.", job.get("job_id"), settings.worker_job_timeout_seconds)
            if retry_count < settings.worker_max_retries:
                await processor.job_store.update_job(
                    str(job.get("job_id")),
                    status="queued",
                    stage="retrying",
                    progress=10,
                    status_message=f"Retrying after timeout ({retry_count + 1}/{settings.worker_max_retries}).",
                    error=None,
                )
                await queue.requeue(_build_retry_payload(job, retry_count + 1))
                logger.info("Requeued timed out job %s for retry %s.", job.get("job_id"), retry_count + 1)
            else:
                await processor.job_store.update_job(
                    str(job.get("job_id")),
                    status="failed",
                    stage="failed",
                    progress=100,
                    status_message="Face swap failed after exhausting retries.",
                    error=f"Timed out after {settings.worker_job_timeout_seconds} seconds.",
                )
        except Exception:  # noqa: BLE001
            logger.exception("Worker failed while processing job %s", job.get("job_id"))
            if retry_count < settings.worker_max_retries:
                await processor.job_store.update_job(
                    str(job.get("job_id")),
                    status="queued",
                    stage="retrying",
                    progress=10,
                    status_message=f"Retrying after failure ({retry_count + 1}/{settings.worker_max_retries}).",
                    error=None,
                )
                await queue.requeue(_build_retry_payload(job, retry_count + 1))
                logger.info("Requeued failed job %s for retry %s.", job.get("job_id"), retry_count + 1)


if __name__ == "__main__":
    asyncio.run(run_worker())
