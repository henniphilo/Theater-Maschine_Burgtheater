from app.services.video_scope import _clip_ids_for_scope, build_video_catalog, osc_availability_by_clip


def test_part1_excludes_narrator_avatar_clips() -> None:
    part1_ids = _clip_ids_for_scope("part1")
    part2_ids = _clip_ids_for_scope("part2")

    assert "clyde" in part1_ids
    assert "inge" not in part1_ids
    assert "sebastian" not in part1_ids
    assert "musiker" not in part1_ids

    assert "inge" in part2_ids
    assert "clyde" in part2_ids


def test_part2_marks_avatar_clips() -> None:
    catalog = build_video_catalog("part2")
    by_id = {clip.id: clip for clip in catalog.clips}
    assert by_id["inge"].video_type == "avatar"
    assert by_id["clyde"].video_type == "atmosphere"


def test_part1_clyde_on_all_projectors() -> None:
    availability = osc_availability_by_clip("part1")
    assert availability["clyde"] == {"rz21", "adam", "eva", "led"}


def test_part2_inge_on_all_beamers_in_avatar_list() -> None:
    availability = osc_availability_by_clip("part2")
    assert availability["inge"] == {"rz21", "adam", "eva", "led"}
