from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class ToolError(RuntimeError):
    """Expected error raised by an advanced media tool."""


@dataclass(frozen=True)
class ToolResult:
    path: Path
    workdir: Path


async def _ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = stderr.decode(errors="ignore").strip()
        raise ToolError(detail[-2000:] or "FFmpeg failed")


def _new_workdir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"novabiz_{prefix}_"))


def _check_input(src: Path) -> None:
    if not src.exists() or not src.is_file():
        raise ToolError("ملف الإدخال غير موجود.")
    if src.stat().st_size <= 0:
        raise ToolError("ملف الإدخال فارغ.")


def cleanup(result: ToolResult | Path) -> None:
    workdir = result.workdir if isinstance(result, ToolResult) else result
    shutil.rmtree(workdir, ignore_errors=True)


async def compress_video(src: Path, crf: int = 26) -> ToolResult:
    _check_input(src)
    if not 18 <= crf <= 35:
        raise ToolError("قيمة الضغط غير صالحة.")
    workdir = _new_workdir("compress")
    out = workdir / "compressed.mp4"
    await _ffmpeg([
        "-i", str(src),
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(out),
    ])
    return ToolResult(out, workdir)


async def make_gif(src: Path, fps: int = 12, width: int = 480) -> ToolResult:
    _check_input(src)
    if not 1 <= fps <= 30 or not 160 <= width <= 1280:
        raise ToolError("إعدادات GIF غير صالحة.")
    workdir = _new_workdir("gif")
    palette = workdir / "palette.png"
    out = workdir / "output.gif"
    vf = f"fps={fps},scale={width}:-1:flags=lanczos,palettegen"
    await _ffmpeg(["-i", str(src), "-vf", vf, str(palette)])
    vf2 = f"fps={fps},scale={width}:-1:flags=lanczos[x];[x][1:v]paletteuse"
    await _ffmpeg([
        "-i", str(src), "-i", str(palette),
        "-filter_complex", vf2,
        "-loop", "0", str(out),
    ])
    return ToolResult(out, workdir)


async def make_thumbnail(src: Path, width: int = 1280) -> ToolResult:
    _check_input(src)
    if not 320 <= width <= 1920:
        raise ToolError("عرض الصورة غير صالح.")
    workdir = _new_workdir("thumb")
    out = workdir / "thumbnail.jpg"
    vf = f"scale={width}:-2:force_original_aspect_ratio=decrease"
    await _ffmpeg([
        "-ss", "00:00:01", "-i", str(src),
        "-frames:v", "1", "-vf", vf, "-q:v", "2", str(out),
    ])
    return ToolResult(out, workdir)


async def extract_frames(src: Path, count: int = 9) -> ToolResult:
    _check_input(src)
    if not 1 <= count <= 30:
        raise ToolError("عدد اللقطات يجب أن يكون بين 1 و30.")
    workdir = _new_workdir("frames")
    pattern = workdir / "frame_%02d.jpg"
    await _ffmpeg([
        "-i", str(src), "-vf", f"thumbnail={count}", "-frames:v", str(count),
        "-q:v", "2", str(pattern),
    ])
    frames = sorted(workdir.glob("frame_*.jpg"))
    if not frames:
        cleanup(workdir)
        raise ToolError("لم يتم استخراج أي لقطة.")
    return ToolResult(workdir / "frame_%02d.jpg", workdir)


async def normalize_audio(src: Path) -> ToolResult:
    _check_input(src)
    workdir = _new_workdir("audio")
    out = workdir / "normalized.mp3"
    await _ffmpeg([
        "-i", str(src), "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "libmp3lame", "-b:a", "192k", str(out),
    ])
    return ToolResult(out, workdir)


def media_info(src: Path) -> dict[str, str]:
    _check_input(src)
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,size,format_name", "-of", "default=noprint_wrappers=1",
            str(src),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ToolError(proc.stderr.strip()[-1500:] or "ffprobe failed")
    result: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result
