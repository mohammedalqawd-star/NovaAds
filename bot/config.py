from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    admin_ids: tuple[int, ...]
    support_username: str
    payment_wallet: str
    database_url: str
    redis_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ConfigError("TELEGRAM_BOT_TOKEN is required")

        admin_raw = os.getenv("ADMIN_IDS", "")
        try:
            admin_ids = tuple(int(x.strip()) for x in admin_raw.split(",") if x.strip())
        except ValueError as exc:
            raise ConfigError("ADMIN_IDS must contain numeric Telegram IDs") from exc

        if not admin_ids:
            raise ConfigError("ADMIN_IDS must contain at least one administrator")

        return cls(
            telegram_token=token,
            admin_ids=admin_ids,
            support_username=os.getenv("SUPPORT_USERNAME", "NovaAdsSupport1"),
            payment_wallet=os.getenv("PAYMENT_WALLET", "783421319"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///novaads.db"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        )
