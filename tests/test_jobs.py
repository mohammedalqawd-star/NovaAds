from bot.services.jobs import Job, JobStatus


def test_job_lifecycle():
    job = Job(user_id=1, service="ai_writer", credits=1)
    assert job.status is JobStatus.QUEUED
    job.start()
    assert job.status is JobStatus.PROCESSING
    job.complete()
    assert job.status is JobStatus.COMPLETED


def test_failed_job_keeps_failure_reason():
    job = Job(user_id=1, service="text_to_video", credits=1)
    job.start()
    job.fail("provider unavailable")
    assert job.status is JobStatus.FAILED
    assert job.error == "provider unavailable"
