from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .catalog import ServiceCatalog, ServiceResult


@dataclass
class ProviderService:
    key: str
    name: str
    category: str
    credits: int = 1
    enabled: bool = False
    provider_env: str = ""

    async def execute(self, **kwargs: Any) -> ServiceResult:
        if not self.enabled:
            return ServiceResult(False, error="Service is disabled")
        if self.provider_env and not os.getenv(self.provider_env):
            return ServiceResult(False, error=f"Provider credential missing: {self.provider_env}")
        return ServiceResult(False, error="Provider adapter is not configured for this service")


def build_catalog() -> ServiceCatalog:
    catalog = ServiceCatalog()
    definitions = [
        ("text_to_video", "✍️ نص → فيديو", "video", "VIDEO_PROVIDER_API_KEY"),
        ("image_to_video", "🖼️ صور → فيديو", "video", "VIDEO_PROVIDER_API_KEY"),
        ("ai_image", "🤖 إنشاء صورة AI", "image", "IMAGE_PROVIDER_API_KEY"),
        ("image_upscale", "🔍 تكبير الصورة", "image", "IMAGE_PROVIDER_API_KEY"),
        ("text_to_speech", "📝 نص → صوت", "audio", "TTS_PROVIDER_API_KEY"),
        ("speech_to_text", "🎤 صوت → نص", "audio", "STT_PROVIDER_API_KEY"),
        ("ai_writer", "✍️ كتابة محتوى", "writer", "LLM_API_KEY"),
        ("ad_generator", "📢 مولد إعلانات", "marketing", "LLM_API_KEY"),
        ("shorts_maker", "🧠 AI Shorts Maker", "shorts", "VIDEO_AI_API_KEY"),
        ("translator", "🌍 AI Translator", "translate", "LLM_API_KEY"),
        ("content_factory", "🏭 Content Factory", "factory", "LLM_API_KEY"),
    ]
    for key, name, category, env in definitions:
        # Safe default: disabled until an administrator explicitly enables and configures it.
        catalog.register(ProviderService(key, name, category, 1, False, env))
    return catalog
