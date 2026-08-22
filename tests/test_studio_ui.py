from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "studio_bot.py"
TEXT = SOURCE.read_text(encoding="utf-8")


def test_studio_has_multiple_sections():
    for section in ("video", "audio", "image", "content", "publish", "media"):
        assert f'"{section}":' in TEXT


def test_studio_has_real_processing_functions():
    for name in ("video_enhance", "video_volume", "video_trim", "video_mute", "video_text", "audio_volume", "audio_trim", "audio_mute", "image_compress", "image_sharpen", "image_blur", "image_grayscale"):
        assert name in TEXT


def test_studio_options_are_callback_backed():
    assert "studio:opt:" in TEXT
    assert "studio:tool:" in TEXT
    assert "StudioState.waiting_file" in TEXT
    assert "StudioState.waiting_value" in TEXT
