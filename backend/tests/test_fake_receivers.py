"""Tests for fake OSC receiver harness."""

from app.director.testing.fake_osc_receiver import FakeOscReceiver


def test_fake_receiver_binds_ephemeral_port() -> None:
    receiver = FakeOscReceiver()
    try:
        receiver.start()
        assert receiver.port > 0
    finally:
        receiver.stop()
