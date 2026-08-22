from pathlib import Path


SOURCE = Path(__file__).parents[1] / "run_upgraded.py"


def test_option_menu_contains_real_volume_controls():
    text = SOURCE.read_text(encoding="utf-8")
    assert 'proopt:{service}:{value}' in text
    assert '("🔉 خفض قوي 0.5×", "0.5")' in text
    assert '("🚀 رفع أقصى 3×", "3.0")' in text


def test_option_menu_contains_real_video_controls():
    text = SOURCE.read_text(encoding="utf-8")
    assert '1080x1920' in text
    assert '1920x1080' in text
    assert 'service == "rotate"' in text
    assert 'service == "speed"' in text


def test_selected_option_reaches_backend():
    text = SOURCE.read_text(encoding="utf-8")
    assert 'option = data.get("pro_option")' in text
    assert 'run_service(service, src, option)' in text
    assert 'audio_volume(src, float(option or 1.5))' in text
