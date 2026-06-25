from app.schemas.part1_selection import MediaSelectionLists
from app.services.catalog_media_resolver import CatalogMediaMatcher, normalize_media_lists


def test_invented_growl_maps_to_tier_sound() -> None:
    matcher = CatalogMediaMatcher.load()
    resolved = matcher.resolve_invented(
        "animal_growl",
        "Hervorragend für das Tierische im Ökonomischen, knurrend",
        medium_hint="sound",
    )
    assert resolved is not None
    media_id, medium = resolved
    assert medium == "sound"
    assert media_id == "tierstimme_verzerrt"


def test_invented_drone_maps_to_grundader() -> None:
    matcher = CatalogMediaMatcher.load()
    resolved = matcher.resolve_invented(
        "drone_low",
        "Perfekt für die maschinelle Verdrängung, kühl",
        medium_hint="sound",
    )
    assert resolved is not None
    assert resolved[0] == "maschinen_grundader"


def test_normalize_media_lists_replaces_unknown_sounds() -> None:
    lists = MediaSelectionLists(
        sounds=[
            "drone_low",
            "office_hum",
            "animal_growl",
            "ticker_click",
            "crowd_murmur",
            "static_noise",
        ],
        music=["ambient_cold"],
        videos=["clyde", "macbook", "inge", "ipad", "sebastian", "kaefer"],
        lights=["cold_low", "flicker_sporadic", "narrow_beam", "isolated_spot", "fade_to_black", "tension_pulse"],
    )
    normalized = normalize_media_lists(lists)
    catalog = CatalogMediaMatcher.load()
    play_ids = {s.id for s in catalog.sound_play}
    assert all(s in play_ids for s in normalized.sounds)
    assert all(m in play_ids for m in normalized.music)
    assert len(normalized.sounds) >= 4
