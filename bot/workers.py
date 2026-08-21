from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from .services.catalog import ServiceCatalog
from .services.jobs import Job

log = logging.getLogger(__name__)


@dataclass
class JobRequest:
    job: Job
    payload: dict


class WorkerPool:
    def __init__(self, catalog: ServiceCatalog, workers: int = 3):
        self.catalog = catalog
        self.queue: asyncio.Queue[JobRequest] = asyncio.Queue()
        self.workers = workers
        self.tasks: list[asyncio.Task] = []

    async def start(self):
        self.tasks = [asyncio.create_task(self._worker(i)) for i in range(self.workers)]

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

    async def submit(self, request: JobRequest):
        await self.queue.put(request)

    async def _worker(self, worker_id: int):
        while True:
            request = await self.queue.get()
            try:
                request.job.start()
                service = self.catalog.get(request.job.service)
                if service is None:
                    raise RuntimeError("Service is disabled or unavailable")
                result = await service.execute(**request.payload)
                if not result.ok:
                    raise RuntimeError(result.error or "Service failed")
                request.job.complete()
            except Exception as exc:
                request.job.fail(str(exc))
                log.exception("Worker %s failed Job %s", worker_id, request.job.id)
            finally:
                self.queue.task_done()
