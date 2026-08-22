from pathlib import Path

ROOT = Path(__file__).parents[1]
RUN = ROOT / "run_options.py"
ENGINE = ROOT / "services" / "options_engine.py"


def test_every_service_has_option_buttons():
    text = RUN.read_text(encoding="utf-8")
    assert 'callback_data=f"choice:{service}:{value}"' in text
    for key in [
        "compress", "convert", "resize", "speed", "volume", "mirror", "gray",
        "sharpen", "snapshot", "gif", "thumbnail", "frames", "rotate", "audio",
        "normalize", "imageresize", "jpg", "webp", "imagegray", "imagesharp",
        "imageblur", "info", "video_ai",
    ]:
        assert f'"{key}"' in text


def test_volume_keeps_video_track():
    text = ENGINE.read_text(encoding="utf-8")
    assert "async def volume_video" in text
    assert '"-map", "0:v:0"' in text
    assert '"-map", "0:a:0?"' in text
    assert '"-af", f"volume={factor:g}"' in text
    assert 'out = work / "volume.mp4"' in text


def test_ai_video_has_caption_bio_and_five_hashtags():
    text = RUN.read_text(encoding="utf-8")
    assert "analyze_video(src, frame_count=6)" in text
    assert "data.get('caption'" in text
    assert "data.get('bio'" in text
    assert "[:5]" in text
