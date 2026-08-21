from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    user_id: int
    service: str
    credits: int
    id: str = ""
    status: JobStatus = JobStatus.QUEUED
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid4().hex

    def start(self) -> None:
        if self.status is not JobStatus.QUEUED:
            raise ValueError("Only queued jobs can start")
        self.status = JobStatus.PROCESSING

    def complete(self) -> None:
        if self.status is not JobStatus.PROCESSING:
            raise ValueError("Only processing jobs can complete")
        self.status = JobStatus.COMPLETED

    def fail(self, error: str) -> None:
        if self.status not in (JobStatus.QUEUED, JobStatus.PROCESSING):
            raise ValueError("Job is already finalized")
        self.status = JobStatus.FAILED
        self.error = error
