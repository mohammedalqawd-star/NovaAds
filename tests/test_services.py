import pytest

from bot.services.jobs import Job, JobStatus
from bot.services.catalog import ServiceCatalog


class FakeService:
    key = "demo"
    name = "Demo"
    category = "tools"
    credits = 1
    enabled = True

    async def execute(self, **kwargs):
        raise NotImplementedError


def test_job_lifecycle():
    job = Job(user_id=1, service="demo", credits=1)
    assert job.status is JobStatus.QUEUED
    job.start()
    assert job.status is JobStatus.PROCESSING
    job.complete()
    assert job.status is JobStatus.COMPLETED


def test_failed_job_records_error():
    job = Job(user_id=1, service="demo", credits=1)
    job.start()
    job.fail("boom")
    assert job.status is JobStatus.FAILED
    assert job.error == "boom"


def test_catalog_only_exposes_enabled_services():
    catalog = ServiceCatalog()
    catalog.register(FakeService())
    assert [s.key for s in catalog.enabled_by_category("tools")] == ["demo"]


@pytest.mark.asyncio
async def test_disabled_service_is_not_returned():
    class Disabled(FakeService):
        key = "disabled"
        enabled = False

    catalog = ServiceCatalog()
    catalog.register(Disabled())
    assert catalog.get("disabled") is None
