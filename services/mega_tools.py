from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from .advanced_tools import ToolError, ToolResult, _check_input, _check_output


def _work(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"novabiz_{prefix}_"))


async def _ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode:
        raise ToolError(err.decode(errors="ignore").strip()[-2000:] or "FFmpeg failed")


def _result(work: Path, out: Path) -> ToolResult:
    _check_output(out)
    return ToolResult(out, work)


async def resize_video(src: Path, width: int, height: int) -> ToolResult:
    _check_input(src)
    if not 144 <= width <= 3840 or not 144 <= height <= 3840:
        raise ToolError("المقاس غير صالح.")
    work = _work("resize")
    out = work / "resized.mp4"
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def speed_video(src: Path, factor: float) -> ToolResult:
    _check_input(src)
    if factor not in {0.5, 0.75, 1.25, 1.5, 2.0}:
        raise ToolError("السرعة المتاحة: 0.5x، 0.75x، 1.25x، 1.5x، 2x.")
    work = _work("speed")
    out = work / "speed.mp4"
    atempo = factor
    audio_filters = []
    while atempo < 0.5:
        audio_filters.append("atempo=0.5")
        atempo *= 2
    while atempo > 2:
        audio_filters.append("atempo=2.0")
        atempo /= 2
    audio_filters.append(f"atempo={atempo:g}")
    await _ffmpeg(["-i", str(src), "-filter_complex", f"[0:v]setpts=PTS/{factor}[v];[0:a]" + ",".join(audio_filters) + "[a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def mirror_video(src: Path, mode: str = "horizontal") -> ToolResult:
    _check_input(src)
    if mode not in {"horizontal", "vertical"}:
        raise ToolError("نوع الانعكاس غير صالح.")
    work = _work("mirror")
    out = work / "mirror.mp4"
    vf = "hflip" if mode == "horizontal" else "vflip"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def grayscale_video(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("gray")
    out = work / "grayscale.mp4"
    await _ffmpeg(["-i", str(src), "-vf", "format=gray", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def sharpen_video(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("sharpen")
    out = work / "sharpened.mp4"
    await _ffmpeg(["-i", str(src), "-vf", "unsharp=5:5:0.8:5:5:0.0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def video_snapshot(src: Path, seconds: float = 1.0) -> ToolResult:
    _check_input(src)
    if seconds < 0:
        raise ToolError("الزمن غير صالح.")
    work = _work("snapshot")
    out = work / "snapshot.jpg"
    await _ffmpeg(["-ss", str(seconds), "-i", str(src), "-frames:v", "1", "-q:v", "2", str(out)])
    return _result(work, out)


async def image_resize(src: Path, width: int, height: int) -> ToolResult:
    _check_input(src)
    work = _work("image_resize")
    out = work / "image.png"
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-frames:v", "1", str(out)])
    return _result(work, out)


async def image_jpg(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("image_jpg")
    out = work / "image.jpg"
    await _ffmpeg(["-i", str(src), "-frames:v", "1", "-q:v", "2", str(out)])
    return _result(work, out)


async def image_webp(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("image_webp")
    out = work / "image.webp"
    await _ffmpeg(["-i", str(src), "-frames:v", "1", "-c:v", "libwebp", "-q:v", "90", str(out)])
    return _result(work, out)


async def image_grayscale(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("image_gray")
    out = work / "grayscale.png"
    await _ffmpeg(["-i", str(src), "-vf", "format=gray", "-frames:v", "1", str(out)])
    return _result(work, out)


async def image_sharpen(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("image_sharp")
    out = work / "sharpened.png"
    await _ffmpeg(["-i", str(src), "-vf", "unsharp=5:5:1.0:5:5:0", "-frames:v", "1", str(out)])
    return _result(work, out)


async def image_blur(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("image_blur")
    out = work / "blurred.png"
    await _ffmpeg(["-i", str(src), "-vf", "gblur=sigma=4", "-frames:v", "1", str(out)])
    return _result(work, out)


async def audio_volume(src: Path, factor: float = 1.5) -> ToolResult:
    _check_input(src)
    if not 0.25 <= factor <= 3:
        raise ToolError("مستوى الصوت يجب أن يكون بين 0.25x و3x.")
    work = _work("volume")
    out = work / "volume.mp3"
    await _ffmpeg(["-i", str(src), "-vn", "-af", f"volume={factor:g}", "-c:a", "libmp3lame", "-q:a", "2", str(out)])
    return _result(work, out)


async def audio_wav(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("wav")
    out = work / "audio.wav"
    await _ffmpeg(["-i", str(src), "-vn", "-c:a", "pcm_s16le", str(out)])
    return _result(work, out)


async def audio_m4a(src: Path) -> ToolResult:
    _check_input(src)
    work = _work("m4a")
    out = work / "audio.m4a"
    await _ffmpeg(["-i", str(src), "-vn", "-c:a", "aac", "-b:a", "192k", str(out)])
    return _result(work, out)
