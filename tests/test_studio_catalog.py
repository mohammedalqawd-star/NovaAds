from pathlib import Path
import ast

from services.studio_catalog import STUDIO_CATEGORIES


def test_studio_has_grouped_categories():
    assert {"audio", "video", "image", "ai"} <= set(STUDIO_CATEGORIES)
    for category in STUDIO_CATEGORIES.values():
        assert category["tools"]
        for label, options in category["tools"].values():
            assert label
            assert options


def test_studio_launcher_is_valid_python():
    source = Path("studio_bot.py").read_text(encoding="utf-8")
    ast.parse(source)
