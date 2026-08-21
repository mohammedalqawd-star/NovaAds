from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp


class DownloadError(Exception):
    """خطأ متوقع أثناء تحليل أو تنزيل الوسائط."""


def _extract_info(url: str) -> dict[str, Any]:
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        raise DownloadError(str(exc)) from exc


async def get_media_info(url: str) -> dict[str, Any]:
    """تحليل الرابط وإرجاع معلومات الوسائط."""
    if not url or not url.startswith(("http://", "https://")):
        raise DownloadError("الرابط غير صالح.")

    return await asyncio.to_thread(_extract_info, url)


def available_video_formats(info: dict[str, Any]) -> list[dict[str, Any]]:
    """إرجاع الجودات الفيديو المتاحة."""
    formats = []

    for fmt in info.get("formats", []):
        if fmt.get("vcodec") in (None, "none"):
            continue

        height = fmt.get("height")
        if not height:
            continue

        formats.append(
            {
                "format_id": fmt.get("format_id"),
                "height": height,
                "ext": fmt.get("ext"),
                "filesize": fmt.get("filesize"),
            }
        )

    unique = {}
    for item in formats:
        key = item["height"]
        current = unique.get(key)

        if current is None or (
            item.get("filesize") or 0
        ) > (current.get("filesize") or 0):
            unique[key] = item

    return sorted(unique.values(), key=lambda x: x["height"])


def _download(
    url: str,
    output_dir: Path,
    format_id: str | None = None,
    audio_only: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    if audio_only:
        fmt = "bestaudio/best"
        options = {
            "format": fmt,
            "outtmpl": str(output_dir / "%(title).80s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
    else:
        fmt = format_id or "bestvideo+bestaudio/best"
        options = {
            "format": fmt,
            "outtmpl": str(output_dir / "%(title).80s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
        }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise DownloadError(str(exc)) from exc

    files = [
        p for p in output_dir.iterdir()
        if p.is_file()
    ]

    if not files:
        raise DownloadError("لم يتم إنشاء الملف.")

    return max(files, key=lambda p: p.stat().st_mtime)


async def download_media(
    url: str,
    format_id: str | None = None,
    audio_only: bool = False,
) -> tuple[Path, Path]:
    """تنزيل الوسائط وإرجاع الملف ومجلد العمل المؤقت."""
    workdir = Path(tempfile.mkdtemp(prefix="novabiz_media_"))

    try:
        result = await asyncio.to_thread(
            _download,
            url,
            workdir,
            format_id,
            audio_only,
        )
        return result, workdir
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def cleanup(workdir: Path) -> None:
    """حذف الملفات المؤقتة."""
    shutil.rmtree(workdir, ignore_errors=True)
