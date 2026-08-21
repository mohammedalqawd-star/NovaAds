from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ServiceResult:
    ok: bool
    output: object | None = None
    error: str | None = None


class ServicePlugin(Protocol):
    key: str
    name: str
    category: str
    credits: int
    enabled: bool

    async def execute(self, **kwargs: object) -> ServiceResult: ...


@dataclass
class ServiceCatalog:
    _services: dict[str, ServicePlugin] = field(default_factory=dict)

    def register(self, service: ServicePlugin) -> None:
        if service.key in self._services:
            raise ValueError(f"Service already registered: {service.key}")
        self._services[service.key] = service

    def enabled_by_category(self, category: str) -> list[ServicePlugin]:
        return [
            service
            for service in self._services.values()
            if service.category == category and service.enabled
        ]

    def get(self, key: str) -> ServicePlugin | None:
        service = self._services.get(key)
        return service if service and service.enabled else None
