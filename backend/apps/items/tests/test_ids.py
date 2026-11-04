import uuid

import pytest

from apps.items import ids


def test_round_trip():
    u = uuid.uuid7()

    assert ids.decode(ids.encode(u)) == u


@pytest.mark.parametrize("u", [uuid.UUID(int=0), uuid.UUID(int=2**128 - 1)])
def test_fixed_length(u):
    encoded = ids.encode(u)

    assert len(encoded) == 22
    assert ids.decode(encoded) == u


@pytest.mark.parametrize(
    "s",
    ["", "short", "0" * 23, "!" * 22, "z" * 22],
    ids=["empty", "short", "long", "bad-chars", "overflow"],
)
def test_decode_invalid(s):
    assert ids.decode(s) is None
