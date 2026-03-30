import asyncio
import logging

from app.config import get_settings
from app.services.queue_service import QueueService
from worker.processor import JobProcessor


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("face-swap-worker")


async def run_worker() -> None:
    settings = get_settings()
    queue = QueueService(settings)
    processor = JobProcessor()

    logger.info("Worker started and listening on queue '%s'.", settings.queue_name)

    while True:
        job = await queue.dequeue(timeout=5)
        if not job:
            await asyncio.sleep(1)
            continue

        logger.info("Processing job %s", job.get("job_id"))
        await processor.process(job)


if __name__ == "__main__":
    asyncio.run(run_worker())
