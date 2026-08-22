from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class ToolError(RuntimeError):
    """Expected error raised by a media tool."""


@dataclass(frozen=True)
class ToolResult:
    path: Path
    workdir: Path


def _new_workdir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"novabiz_{prefix}_"))


def _check_input(src: Path) -> None:
    if not src.exists() or not src.is_file():
        raise ToolError("ملف الإدخال غير موجود.")
    if src.stat().st_size <= 0:
        raise ToolError("ملف الإدخال فارغ.")


async def _ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = stderr.decode(errors="ignore").strip()
        raise ToolError(detail[-2000:] or "FFmpeg failed")


def _check_output(path: Path) -> None:
    if not path.exists() or path.stat().st_size <= 0:
        raise ToolError("لم يتم إنشاء ملف الناتج.")


def cleanup(result: ToolResult | Path) -> None:
    workdir = result.workdir if isinstance(result, ToolResult) else result
    shutil.rmtree(workdir, ignore_errors=True)


async def compress_video(src: Path, crf: int = 26) -> ToolResult:
    _check_input(src)
    if not 18 <= crf <= 35:
        raise ToolError("قيمة الضغط غير صالحة.")
    workdir = _new_workdir("compress")
    out = workdir / "compressed.mp4"
    await _ffmpeg(["-i", str(src), "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def convert_video(src: Path) -> ToolResult:
    _check_input(src)
    workdir = _new_workdir("convert")
    out = workdir / "converted.mp4"
    await _ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def make_gif(src: Path, fps: int = 12, width: int = 480) -> ToolResult:
    _check_input(src)
    if not 1 <= fps <= 30 or not 160 <= width <= 1280:
        raise ToolError("إعدادات GIF غير صالحة.")
    workdir = _new_workdir("gif")
    palette = workdir / "palette.png"
    out = workdir / "output.gif"
    await _ffmpeg(["-i", str(src), "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,palettegen", str(palette)])
    await _ffmpeg(["-i", str(src), "-i", str(palette), "-filter_complex", f"[0:v]fps={fps},scale={width}:-1:flags=lanczos[x];[x][1:v]paletteuse", "-loop", "0", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def make_thumbnail(src: Path, width: int = 1280) -> ToolResult:
    _check_input(src)
    if not 320 <= width <= 1920:
        raise ToolError("عرض الصورة غير صالح.")
    workdir = _new_workdir("thumb")
    out = workdir / "thumbnail.jpg"
    await _ffmpeg(["-ss", "00:00:01", "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2:force_original_aspect_ratio=decrease", "-q:v", "2", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def extract_frames(src: Path, count: int = 9) -> ToolResult:
    _check_input(src)
    if not 1 <= count <= 30:
        raise ToolError("عدد اللقطات يجب أن يكون بين 1 و30.")
    workdir = _new_workdir("frames")
    pattern = workdir / "frame_%02d.jpg"
    await _ffmpeg(["-i", str(src), "-vf", "thumbnail=300", "-frames:v", str(count), "-q:v", "2", str(pattern)])
    if not list(workdir.glob("frame_*.jpg")):
        cleanup(workdir)
        raise ToolError("لم يتم استخراج أي لقطة.")
    return ToolResult(pattern, workdir)


async def extract_audio(src: Path) -> ToolResult:
    _check_input(src)
    workdir = _new_workdir("extract_audio")
    out = workdir / "audio.mp3"
    await _ffmpeg(["-i", str(src), "-vn", "-c:a", "libmp3lame", "-b:a", "192k", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def normalize_audio(src: Path) -> ToolResult:
    _check_input(src)
    workdir = _new_workdir("normalize")
    out = workdir / "normalized.mp3"
    await _ffmpeg(["-i", str(src), "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "libmp3lame", "-b:a", "192k", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def convert_audio(src: Path) -> ToolResult:
    _check_input(src)
    workdir = _new_workdir("convert_audio")
    out = workdir / "audio.mp3"
    await _ffmpeg(["-i", str(src), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def mute_video(src: Path) -> ToolResult:
    _check_input(src)
    workdir = _new_workdir("mute")
    out = workdir / "muted.mp4"
    await _ffmpeg(["-i", str(src), "-map", "0:v:0", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-an", "-movflags", "+faststart", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def web_optimize(src: Path) -> ToolResult:
    _check_input(src)
    workdir = _new_workdir("web")
    out = workdir / "web_ready.mp4"
    await _ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


async def rotate_video(src: Path, direction: str = "right") -> ToolResult:
    _check_input(src)
    if direction not in {"right", "left", "180"}:
        raise ToolError("اتجاه التدوير غير صالح.")
    transpose = {"right": "1", "left": "2", "180": None}[direction]
    workdir = _new_workdir("rotate")
    out = workdir / "rotated.mp4"
    vf = f"transpose={transpose}" if transpose else "hflip,vflip"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    _check_output(out)
    return ToolResult(out, workdir)


def media_info(src: Path) -> dict[str, str]:
    _check_input(src)
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size,format_name,bit_rate", "-of", "default=noprint_wrappers=1", str(src)], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ToolError(proc.stderr.strip()[-1500:] or "ffprobe failed")
    result: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result
