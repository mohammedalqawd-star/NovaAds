from services.mega_tools import (
    audio_m4a, audio_volume, audio_wav, grayscale_video, image_blur,
    image_grayscale, image_jpg, image_resize, image_sharpen, image_webp,
    mirror_video, resize_video, sharpen_video, speed_video, video_snapshot,
)


def test_mega_tools_are_available():
    tools = [
        resize_video, speed_video, mirror_video, grayscale_video, sharpen_video,
        video_snapshot, image_resize, image_jpg, image_webp, image_grayscale,
        image_sharpen, image_blur, audio_volume, audio_wav, audio_m4a,
    ]
    assert len(tools) == 15
    assert all(callable(tool) for tool in tools)
