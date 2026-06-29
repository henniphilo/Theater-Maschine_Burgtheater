from app.director.media.database import MediaDatabase
from app.director.media.selector import MediaSelector


def test_media_selector_returns_available_video() -> None:
    db = MediaDatabase()
    video_ids = {v.id for v in db.videos}
    selector = MediaSelector(db, history_size=3)

    first = selector.select_video(["clyde"], "neutral", 0.5)
    assert first is not None
    assert first.id in video_ids


def test_get_sound_by_tags_respects_intensity() -> None:
    db = MediaDatabase()
    sound = db.get_sound_by_tags(["glitch"], mood="spannung", intensity=0.9)
    assert sound is not None
    assert sound.id == "erinnerungsglitch"


def test_get_light_scene_rotates_through_candidates() -> None:
    db = MediaDatabase()
    first = db.get_light_scene("spannung", 0.8)
    second = db.get_light_scene("spannung", 0.8, exclude_ids=[first.id] if first else [])
    assert first is not None
    assert second is not None
    assert first.id != second.id


def test_get_light_scene_spreads_unknown_moods_across_pool() -> None:
    db = MediaDatabase()
    picks = {
        db.get_light_scene(f"mood_{index}", 0.7).id
        for index in range(12)
    }
    assert len(picks) >= 3


def test_select_light_varies_across_calls() -> None:
    db = MediaDatabase()
    selector = MediaSelector(db, history_size=3)
    picks = {selector.select_light("spannung", 0.75).id for _ in range(6)}
    assert len(picks) >= 2
