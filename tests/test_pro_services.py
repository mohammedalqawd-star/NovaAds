from services.advanced_tools import ToolError


def test_invalid_rotate_direction_is_rejected():
    assert issubclass(ToolError, RuntimeError)
