from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from .advanced_tools import ToolError, ToolResult, _check_input, _check_output


async def video_volume(src: Path, factor: float = 1.5) -> ToolResult:
    """Change video audio volume while preserving the video track."""
    _check_input(src)
    if not 0.25 <= factor <= 3:
        raise ToolError("مستوى الصوت يجب أن يكون بين 0.25x و3x.")

    work = Path(tempfile.mkdtemp(prefix="novabiz_video_volume_"))
    out = work / "video_volume.mp4"
    args = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-af", f"volume={factor:g}",
        "-movflags", "+faststart", str(out),
    ]
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, err = await proc.communicate()
    if proc.returncode:
        raise ToolError(err.decode(errors="ignore").strip()[-2000:] or "FFmpeg failed")
    _check_output(out)
    return ToolResult(out, work)
