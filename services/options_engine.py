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
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode:
        raise ToolError(err.decode(errors="ignore").strip()[-2000:] or "FFmpeg failed")


def _result(work: Path, out: Path) -> ToolResult:
    _check_output(out)
    return ToolResult(out, work)


async def compress(src: Path, crf: int) -> ToolResult:
    _check_input(src)
    if not 18 <= crf <= 35: raise ToolError("CRF غير صالح")
    work = _work("compress_opt"); out = work / "compressed.mp4"
    await _ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def convert(src: Path, preset: str, crf: int) -> ToolResult:
    _check_input(src)
    if preset not in {"fast", "balanced", "quality"}: raise ToolError("وضع التحويل غير صالح")
    work = _work("convert_opt"); out = work / "converted.mp4"
    await _ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", preset if preset != "quality" else "slow", "-crf", str(crf), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def resize(src: Path, width: int, height: int) -> ToolResult:
    _check_input(src)
    if not 144 <= width <= 3840 or not 144 <= height <= 3840: raise ToolError("المقاس غير صالح")
    work = _work("resize_opt"); out = work / "resized.mp4"
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def speed(src: Path, factor: float) -> ToolResult:
    _check_input(src)
    if factor not in {0.5, 0.75, 1.25, 1.5, 2.0}: raise ToolError("السرعة غير صالحة")
    work = _work("speed_opt"); out = work / "speed.mp4"
    audio = factor
    af: list[str] = []
    while audio < 0.5: af.append("atempo=0.5"); audio *= 2
    while audio > 2: af.append("atempo=2.0"); audio /= 2
    af.append(f"atempo={audio:g}")
    await _ffmpeg(["-i", str(src), "-filter_complex", f"[0:v]setpts=PTS/{factor}[v];[0:a:0]?{',' .join(af)}[a]" if False else f"[0:v]setpts=PTS/{factor}[v];[0:a]" + ",".join(af) + "[a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def mirror(src: Path, mode: str) -> ToolResult:
    _check_input(src); vf = {"horizontal": "hflip", "vertical": "vflip"}.get(mode)
    if not vf: raise ToolError("نوع الانعكاس غير صالح")
    work = _work("mirror_opt"); out = work / "mirror.mp4"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def grayscale(src: Path, strength: str = "full") -> ToolResult:
    _check_input(src); sat = {"light": "0.35", "medium": "0", "full": "0"}.get(strength)
    if sat is None: raise ToolError("قوة الأبيض والأسود غير صالحة")
    work = _work("gray_opt"); out = work / "grayscale.mp4"
    vf = "format=gray" if strength != "light" else "eq=saturation=0.35"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def sharpen(src: Path, level: str) -> ToolResult:
    _check_input(src); amount = {"light": "0.35", "medium": "0.65", "strong": "1.0"}.get(level)
    if amount is None: raise ToolError("مستوى الحدة غير صالح")
    work = _work("sharp_opt"); out = work / "sharpened.mp4"
    await _ffmpeg(["-i", str(src), "-vf", f"unsharp=5:5:{amount}:5:5:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def snapshot(src: Path, seconds: float) -> ToolResult:
    _check_input(src)
    work = _work("snapshot_opt"); out = work / "snapshot.jpg"
    await _ffmpeg(["-ss", str(max(0, seconds)), "-i", str(src), "-frames:v", "1", "-q:v", "2", str(out)])
    return _result(work, out)


async def gif(src: Path, fps: int, width: int) -> ToolResult:
    _check_input(src)
    if not 1 <= fps <= 30 or not 160 <= width <= 1280: raise ToolError("إعداد GIF غير صالح")
    work = _work("gif_opt"); palette = work / "palette.png"; out = work / "output.gif"
    await _ffmpeg(["-i", str(src), "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,palettegen", str(palette)])
    await _ffmpeg(["-i", str(src), "-i", str(palette), "-filter_complex", f"[0:v]fps={fps},scale={width}:-1:flags=lanczos[x];[x][1:v]paletteuse", "-loop", "0", str(out)])
    return _result(work, out)


async def thumbnail(src: Path, width: int) -> ToolResult:
    _check_input(src); work = _work("thumb_opt"); out = work / "thumbnail.jpg"
    await _ffmpeg(["-ss", "1", "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2:force_original_aspect_ratio=decrease", "-q:v", "2", str(out)])
    return _result(work, out)


async def frames(src: Path, count: int) -> ToolResult:
    _check_input(src)
    if not 1 <= count <= 30: raise ToolError("عدد اللقطات غير صالح")
    work = _work("frames_opt"); pattern = work / "frame_%02d.jpg"
    await _ffmpeg(["-i", str(src), "-vf", "thumbnail=300", "-frames:v", str(count), "-q:v", "2", str(pattern)])
    if not list(work.glob("frame_*.jpg")): raise ToolError("لم يتم استخراج لقطات")
    return ToolResult(pattern, work)


async def rotate(src: Path, direction: str) -> ToolResult:
    _check_input(src); vf = {"right": "transpose=1", "left": "transpose=2", "180": "hflip,vflip"}.get(direction)
    if not vf: raise ToolError("اتجاه التدوير غير صالح")
    work = _work("rotate_opt"); out = work / "rotated.mp4"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def volume_video(src: Path, factor: float) -> ToolResult:
    _check_input(src)
    if not 0.25 <= factor <= 3: raise ToolError("مستوى الصوت يجب أن يكون بين 0.25x و3x")
    work = _work("volume_opt"); out = work / "volume.mp4"
    await _ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-af", f"volume={factor:g}", "-movflags", "+faststart", str(out)])
    return _result(work, out)


async def audio_convert(src: Path, fmt: str, bitrate: str) -> ToolResult:
    _check_input(src)
    ext = {"mp3": "mp3", "m4a": "m4a", "wav": "wav"}.get(fmt)
    if not ext: raise ToolError("الصيغة غير صالحة")
    work = _work("audio_convert_opt"); out = work / f"audio.{ext}"
    codec = "libmp3lame" if ext == "mp3" else ("aac" if ext == "m4a" else "pcm_s16le")
    args = ["-i", str(src), "-vn", "-c:a", codec]
    if ext != "wav": args += ["-b:a", bitrate]
    args += [str(out)]
    await _ffmpeg(args)
    return _result(work, out)


async def normalize(src: Path, target: str) -> ToolResult:
    _check_input(src); work = _work("normalize_opt"); out = work / "normalized.mp3"
    await _ffmpeg(["-i", str(src), "-vn", "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11", "-c:a", "libmp3lame", "-b:a", "192k", str(out)])
    return _result(work, out)


async def image_resize(src: Path, width: int, height: int) -> ToolResult:
    _check_input(src); work = _work("image_resize_opt"); out = work / "image.png"
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    await _ffmpeg(["-i", str(src), "-vf", vf, "-frames:v", "1", str(out)])
    return _result(work, out)


async def image_convert(src: Path, fmt: str, quality: int) -> ToolResult:
    _check_input(src); ext = "jpg" if fmt == "jpg" else "webp"; work = _work("image_convert_opt"); out = work / f"image.{ext}"
    args = ["-i", str(src), "-frames:v", "1"]
    if ext == "jpg": args += ["-q:v", str(max(2, min(31, 32 - quality)))]
    else: args += ["-c:v", "libwebp", "-q:v", str(quality)]
    await _ffmpeg(args + [str(out)])
    return _result(work, out)


async def image_filter(src: Path, mode: str, strength: str) -> ToolResult:
    _check_input(src); work = _work(f"image_{mode}_opt"); out = work / f"image_{mode}.png"
    if mode == "gray": vf = "format=gray"
    elif mode == "sharp": vf = f"unsharp=5:5:{ {'light':'0.35','medium':'0.65','strong':'1.0'}[strength] }:5:5:0"
    elif mode == "blur": vf = f"gblur=sigma={ {'light':'2','medium':'4','strong':'7'}[strength] }"
    else: raise ToolError("فلتر الصورة غير صالح")
    await _ffmpeg(["-i", str(src), "-vf", vf, "-frames:v", "1", str(out)])
    return _result(work, out)


def info(src: Path) -> dict[str, str]:
    _check_input(src)
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size,format_name,bit_rate", "-of", "default=noprint_wrappers=1", str(src)], capture_output=True, text=True, check=False)
    if proc.returncode: raise ToolError(proc.stderr.strip()[-1500:] or "ffprobe failed")
    return dict(line.split("=", 1) for line in proc.stdout.splitlines() if "=" in line)


def cleanup(result: ToolResult) -> None:
    shutil.rmtree(result.workdir, ignore_errors=True)
