from unittest.mock import MagicMock

from app.director.cues.cue_models import LightCue
from app.director.light_desk_test import LightDeskTestManager


def test_send_scene_passes_intensity_to_lighting() -> None:
    pipeline = MagicMock()
    manager = LightDeskTestManager(pipeline)
    manager._require_tcp_connected = MagicMock()  # type: ignore[method-assign]
    manager.stop_hold = MagicMock()  # type: ignore[method-assign]

    status = manager.send_scene("vorbuehnenzug", intensity=0.62)

    pipeline.lighting.send_scene.assert_called_once()
    cue = pipeline.lighting.send_scene.call_args.args[0]
    assert isinstance(cue, LightCue)
    assert cue.scene_id == "vorbuehnenzug"
    assert cue.intensity == 0.62
    assert status.intensity == 0.62


def test_send_scene_without_intensity_uses_full() -> None:
    pipeline = MagicMock()
    manager = LightDeskTestManager(pipeline)
    manager._require_tcp_connected = MagicMock()  # type: ignore[method-assign]
    manager.stop_hold = MagicMock()  # type: ignore[method-assign]

    status = manager.send_scene("vorbuehnenzug")

    cue = pipeline.lighting.send_scene.call_args.args[0]
    assert cue.intensity is None
    assert status.intensity is None
