from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path


class StudioToolError(RuntimeError):
    """Expected failure from a Studio tool."""


def _workdir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"novabiz_{prefix}_"))


def _check(src: Path) -> None:
    if not src.is_file() or src.stat().st_size <= 0:
        raise StudioToolError("ملف الإدخال غير موجود أو فارغ.")


def _check_out(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size <= 0:
        raise StudioToolError("لم يتم إنشاء ملف الناتج.")
    return path


async def _ffmpeg(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode:
        raise StudioToolError(err.decode(errors="ignore")[-1800:] or "FFmpeg failed")


async def audio_volume(src: Path, percent: int) -> tuple[Path, Path]:
    _check(src)
    if not 10 <= percent <= 300:
        raise StudioToolError("مستوى الصوت يجب أن يكون بين 10% و300%.")
    work = _workdir("audio_volume")
    out = work / "volume.mp3"
    gain = percent / 100
    await _ffmpeg("-i", str(src), "-vn", "-af", f"volume={gain}", "-c:a", "libmp3lame", "-b:a", "192k", str(out))
    return _check_out(out), work


async def audio_trim(src: Path, start: float, end: float) -> tuple[Path, Path]:
    _check(src)
    if start < 0 or end <= start:
        raise StudioToolError("بداية ونهاية القص غير صالحتين.")
    work = _workdir("audio_trim")
    out = work / "trimmed.mp3"
    await _ffmpeg("-ss", str(start), "-to", str(end), "-i", str(src), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(out))
    return _check_out(out), work


async def audio_mute(src: Path) -> tuple[Path, Path]:
    _check(src)
    work = _workdir("audio_mute")
    out = work / "muted.mp3"
    await _ffmpeg("-i", str(src), "-af", "volume=0", "-c:a", "libmp3lame", "-b:a", "128k", str(out))
    return _check_out(out), work


async def video_volume(src: Path, percent: int) -> tuple[Path, Path]:
    _check(src)
    if not 10 <= percent <= 300:
        raise StudioToolError("مستوى الصوت يجب أن يكون بين 10% و300%.")
    work = _workdir("video_volume")
    out = work / "video_volume.mp4"
    gain = percent / 100
    await _ffmpeg("-i", str(src), "-vf", "format=yuv420p", "-af", f"volume={gain}", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out))
    return _check_out(out), work


async def video_trim(src: Path, start: float, end: float) -> tuple[Path, Path]:
    _check(src)
    if start < 0 or end <= start:
        raise StudioToolError("بداية ونهاية القص غير صالحتين.")
    work = _workdir("video_trim")
    out = work / "trimmed.mp4"
    await _ffmpeg("-ss", str(start), "-to", str(end), "-i", str(src), "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-movflags", "+faststart", str(out))
    return _check_out(out), work


async def video_mute(src: Path) -> tuple[Path, Path]:
    _check(src)
    work = _workdir("video_mute")
    out = work / "muted.mp4"
    await _ffmpeg("-i", str(src), "-map", "0:v:0", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-an", "-movflags", "+faststart", str(out))
    return _check_out(out), work


async def video_enhance(src: Path, strength: str = "medium") -> tuple[Path, Path]:
    _check(src)
    filters = {
        "light": "eq=contrast=1.04:saturation=1.03,unsharp=5:5:0.35:5:5:0",
        "medium": "eq=contrast=1.08:saturation=1.06,unsharp=5:5:0.55:5:5:0",
        "strong": "eq=contrast=1.12:saturation=1.09,unsharp=7:7:0.75:7:7:0",
    }
    if strength not in filters:
        raise StudioToolError("مستوى التحسين غير صالح.")
    work = _workdir("video_enhance")
    out = work / "enhanced.mp4"
    await _ffmpeg("-i", str(src), "-vf", filters[strength] + ",format=yuv420p", "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out))
    return _check_out(out), work


async def video_text(src: Path, text: str, position: str = "bottom") -> tuple[Path, Path]:
    _check(src)
    text = text.strip()
    if not text or len(text) > 180:
        raise StudioToolError("النص مطلوب وبحد أقصى 180 حرفاً.")
    positions = {
        "top": "x=(w-text_w)/2:y=40",
        "center": "x=(w-text_w)/2:y=(h-text_h)/2",
        "bottom": "x=(w-text_w)/2:y=h-text_h-50",
    }
    if position not in positions:
        raise StudioToolError("موضع النص غير صالح.")
    escaped = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    vf = f"drawtext=text='{escaped}':fontcolor=white:fontsize=48:borderw=3:bordercolor=black@0.8:{positions[position]}"
    work = _workdir("video_text")
    out = work / "text.mp4"
    await _ffmpeg("-i", str(src), "-vf", vf + ",format=yuv420p", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-movflags", "+faststart", str(out))
    return _check_out(out), work


async def image_compress(src: Path, quality: int = 82) -> tuple[Path, Path]:
    _check(src)
    if not 20 <= quality <= 95:
        raise StudioToolError("جودة الضغط يجب أن تكون بين 20 و95.")
    work = _workdir("image_compress")
    out = work / "compressed.jpg"
    await _ffmpeg("-i", str(src), "-frames:v", "1", "-q:v", str(max(2, min(31, round((100-quality)/3.2)))), str(out))
    return _check_out(out), work


async def image_sharpen(src: Path) -> tuple[Path, Path]:
    _check(src)
    work = _workdir("image_sharpen")
    out = work / "sharpened.jpg"
    await _ffmpeg("-i", str(src), "-vf", "unsharp=5:5:0.7:5:5:0", "-frames:v", "1", "-q:v", "2", str(out))
    return _check_out(out), work


async def image_grayscale(src: Path) -> tuple[Path, Path]:
    _check(src)
    work = _workdir("image_gray")
    out = work / "grayscale.jpg"
    await _ffmpeg("-i", str(src), "-vf", "format=gray", "-frames:v", "1", "-q:v", "2", str(out))
    return _check_out(out), work


async def image_blur(src: Path) -> tuple[Path, Path]:
    _check(src)
    work = _workdir("image_blur")
    out = work / "blur.jpg"
    await _ffmpeg("-i", str(src), "-vf", "gblur=sigma=2.5", "-frames:v", "1", "-q:v", "3", str(out))
    return _check_out(out), work


def media_probe(src: Path) -> dict[str, str]:
    _check(src)
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size,format_name,bit_rate", "-of", "default=noprint_wrappers=1", str(src)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        raise StudioToolError(proc.stderr.strip()[-1500:] or "ffprobe failed")
    return dict(line.split("=", 1) for line in proc.stdout.splitlines() if "=" in line)


def cleanup(workdir: Path) -> None:
    shutil.rmtree(workdir, ignore_errors=True)


AUDIO_TOOLS = {
    "audio_volume": "رفع/خفض الصوت",
    "audio_trim": "قص الصوت",
    "audio_mute": "كتم الصوت",
    "convert_audio": "تحويل الصوت",
    "normalize_audio": "تطبيع الصوت",
}

VIDEO_TOOLS = {
    "video_volume": "رفع/خفض صوت الفيديو",
    "video_trim": "قص الفيديو",
    "video_mute": "حذف صوت الفيديو",
    "video_enhance": "تحسين الفيديو",
    "video_text": "إضافة نص للفيديو",
    "compress_video": "ضغط الفيديو",
    "convert_video": "تحويل الفيديو",
    "resize_video": "تغيير مقاس الفيديو",
    "extract_audio": "استخراج الصوت",
    "extract_frames": "استخراج اللقطات",
    "make_gif": "تحويل الفيديو إلى GIF",
    "make_thumbnail": "صورة مصغرة",
}

IMAGE_TOOLS = {
    "image_compress": "ضغط الصورة",
    "image_sharpen": "حدة الصورة",
    "image_grayscale": "أبيض وأسود",
    "image_blur": "طمس الصورة",
    "resize_image": "تغيير المقاس",
    "convert_image": "تحويل الصيغة",
    "enhance_image": "تحسين الصورة",
}
