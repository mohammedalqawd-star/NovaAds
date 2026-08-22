from pathlib import Path

import pytest

from services.advanced_tools import ToolError, _check_input


def test_check_input_rejects_missing_file(tmp_path: Path):
    with pytest.raises(ToolError, match="غير موجود"):
        _check_input(tmp_path / "missing.bin")


def test_check_input_rejects_empty_file(tmp_path: Path):
    path = tmp_path / "empty.bin"
    path.touch()
    with pytest.raises(ToolError, match="فارغ"):
        _check_input(path)
