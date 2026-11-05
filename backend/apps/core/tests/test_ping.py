import logging

from apps.core.tasks import ping


def test_ping_logs_pong(caplog):
    with caplog.at_level(logging.INFO):
        ping()

    assert "pong" in caplog.messages
