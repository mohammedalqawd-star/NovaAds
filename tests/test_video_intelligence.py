from pathlib import Path

import pytest

from services.video_intelligence import VideoIntelligenceError, _image_data


def test_missing_video_is_rejected(tmp_path: Path):
    from services.video_intelligence import analyze_video
    with pytest.raises(VideoIntelligenceError, match="غير موجود"):
        import asyncio
        asyncio.run(analyze_video(tmp_path / "missing.mp4"))


def test_image_data_is_data_url(tmp_path: Path):
    path = tmp_path / "frame.jpg"
    path.write_bytes(b"jpeg")
    assert _image_data(path).startswith("data:image/jpeg;base64,")
