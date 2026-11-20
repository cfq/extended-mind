import json
import os
import subprocess
import sys

import pytest

SECURE = ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_HSTS_SECONDS")


def settings_with(debug: str) -> dict:
    """The security settings as loaded with DEBUG=debug, in a fresh process."""
    code = (
        "import json; from config import settings as s; "
        f"print(json.dumps({{k: getattr(s, k, None) for k in {SECURE!r}}}))"
    )
    env = {**os.environ, "DEBUG": debug}
    out = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


@pytest.mark.parametrize("debug", ["False", "false", "0"])
def test_secure_when_debug_off(debug):
    assert settings_with(debug) == {
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "SECURE_HSTS_SECONDS": 31_536_000,
    }


def test_plain_when_debug_on():
    loaded = settings_with("True")

    assert not loaded["SESSION_COOKIE_SECURE"]
    assert not loaded["CSRF_COOKIE_SECURE"]
    assert not loaded["SECURE_HSTS_SECONDS"]
