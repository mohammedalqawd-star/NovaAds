from pathlib import Path


def test_upgraded_entrypoint_exists():
    assert Path("run_upgraded.py").is_file()


def test_advanced_tool_module_exists():
    assert Path("services/advanced_tools.py").is_file()
