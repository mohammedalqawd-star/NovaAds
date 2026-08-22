from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class VideoIntelligenceError(RuntimeError):
    """Expected error while analyzing a video."""


def _probe(video: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size,format_name",
            "-show_streams", "-of", "json", str(video),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise VideoIntelligenceError(proc.stderr.strip()[-1500:] or "تعذر قراءة الفيديو")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise VideoIntelligenceError("تعذر قراءة معلومات الفيديو") from exc


def _frames(video: Path, count: int = 6) -> list[Path]:
    workdir = Path(tempfile.mkdtemp(prefix="novabiz_vi_"))
    pattern = workdir / "frame_%02d.jpg"
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video),
            "-vf", f"fps=1/{max(1, count)},scale=768:-2:force_original_aspect_ratio=decrease",
            "-frames:v", str(count), "-q:v", "3", str(pattern),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)
        raise VideoIntelligenceError(proc.stderr.strip()[-1500:] or "تعذر استخراج لقطات الفيديو")
    frames = sorted(workdir.glob("frame_*.jpg"))
    if not frames:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)
        raise VideoIntelligenceError("لم يتم استخراج لقطات قابلة للتحليل")
    return frames


def _image_data(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _call_vision_api(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("VISION_API_KEY", "").strip()
    api_url = os.getenv("VISION_API_URL", "https://api.openai.com/v1/chat/completions").strip()
    model = os.getenv("VISION_MODEL", "gpt-4.1-mini").strip()
    if not api_key:
        raise VideoIntelligenceError(
            "خدمة فهم الفيديو تحتاج VISION_API_KEY. أضف مفتاح مزود الرؤية في .env ثم أعد التشغيل."
        )

    body = {
        "model": model,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "حلل لقطات الفيديو بدقة. أعد JSON فقط بالمفاتيح: "
                    "summary, topic, audience, tone, caption, bio, hashtags, hook, cta. "
                    "hashtags يجب أن تكون قائمة من 5 هاشتاقات عربية أو إنجليزية مناسبة للمحتوى، "
                    "بدون هاشتاقات عامة غير مرتبطة. caption وbio بالعربية الواضحة."
                ),
            },
            {"role": "user", "content": payload["content"]},
        ],
    }
    request = Request(
        api_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise VideoIntelligenceError(f"مزود الذكاء الاصطناعي رفض الطلب: {detail[-1000:]}") from exc
    except URLError as exc:
        raise VideoIntelligenceError(f"تعذر الاتصال بمزود الذكاء الاصطناعي: {exc.reason}") from exc

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise VideoIntelligenceError("استجابة مزود الذكاء الاصطناعي غير صالحة") from exc


async def analyze_video(video: Path, frame_count: int = 6) -> tuple[dict[str, Any], list[Path], Path]:
    """Analyze sampled video frames and return AI content plus temporary frames."""
    if not video.exists() or video.stat().st_size <= 0:
        raise VideoIntelligenceError("ملف الفيديو غير موجود أو فارغ")

    probe = await asyncio.to_thread(_probe, video)
    frames = await asyncio.to_thread(_frames, video, frame_count)
    stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    duration = probe.get("format", {}).get("duration", "0")
    width = stream.get("width", "?")
    height = stream.get("height", "?")

    prompt_parts = [
        "هذه لقطات متتابعة مأخوذة من فيديو واحد.",
        f"مدة الفيديو: {duration} ثانية. الدقة: {width}x{height}.",
        "افهم المشاهد والعناصر والموضوع والسياق التسويقي، ثم جهز محتوى قابل للنشر.",
    ]
    content: list[dict[str, Any]] = [{"type": "text", "text": "\n".join(prompt_parts)}]
    for frame in frames:
        content.append({"type": "image_url", "image_url": {"url": _image_data(frame), "detail": "low"}})

    try:
        result = await asyncio.to_thread(_call_vision_api, {"content": content})
    except Exception:
        import shutil
        shutil.rmtree(frames[0].parent, ignore_errors=True)
        raise

    result.setdefault("hashtags", [])
    if not isinstance(result["hashtags"], list):
        result["hashtags"] = [str(result["hashtags"])]
    result["hashtags"] = result["hashtags"][:5]
    result["duration"] = str(duration)
    result["resolution"] = f"{width}x{height}"
    return result, frames, frames[0].parent
