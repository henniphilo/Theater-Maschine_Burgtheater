from app.director.outputs.eos_light import (
    eos_chan_full,
    eos_chan_level,
    eos_group_level,
    eos_key_out,
    expand_channels,
    light_intensity_to_percent,
    parse_eos_chan_address,
    parse_eos_chan_command,
    parse_eos_group_command,
)


def test_expand_channel_ranges_and_lists() -> None:
    assert expand_channels(["11-19"]) == list(range(11, 20))
    assert expand_channels(["92", "94", "96", "98"]) == [92, 94, 96, 98]
    assert expand_channels(["6"]) == [6]
    assert expand_channels(["40-46", "48"]) == list(range(40, 47)) + [48]


def test_eos_chan_full_format() -> None:
    address, args = eos_chan_full(6)
    assert address == "/eos/chan/6/full"
    assert args == []


def test_eos_chan_level_partial_and_full() -> None:
    address, args = eos_chan_level(71, 0.62)
    assert address == "/eos/chan/71"
    assert args == [62.0]

    address, args = eos_chan_level(6, 1.0)
    assert address == "/eos/chan/6/full"
    assert args == []

    address, args = eos_chan_level(6, 0.35)
    assert address == "/eos/chan/6"
    assert args == [35.0]


def test_light_intensity_to_percent() -> None:
    assert light_intensity_to_percent(0.0) == 0
    assert light_intensity_to_percent(0.456) == 46
    assert light_intensity_to_percent(1.0) == 100


def test_parse_eos_chan_address() -> None:
    assert parse_eos_chan_address("/eos/chan/6/full") == 6
    assert parse_eos_chan_address("/eos/chan/71") == 71
    assert parse_eos_chan_address("/eos/chan/6=full") is None


def test_parse_eos_chan_command() -> None:
    assert parse_eos_chan_command("/eos/chan/6/full") == (6, 1.0)
    assert parse_eos_chan_command("/eos/chan/71", [62]) == (71, 0.62)
    assert parse_eos_chan_command("/eos/chan/6/at", [75]) == (6, 0.75)

    address, args = eos_key_out()
    assert address == "/eos/key/out"
    assert args == []


def test_eos_group_level_partial() -> None:
    address, args = eos_group_level(2, 0.5)
    assert address == "/eos/group/2"
    assert args == [50.0]


def test_parse_eos_group_command() -> None:
    assert parse_eos_group_command("/eos/group/2/full") == (2, 1.0)
    assert parse_eos_group_command("/eos/group/2", [50]) == (2, 0.5)
    assert parse_eos_group_command("/eos/group/2/level", [50]) == (2, 0.5)
