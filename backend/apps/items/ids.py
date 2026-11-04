"""UUIDs as 22-char base62 strings for URLs."""

import uuid

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
LENGTH = 22


def encode(u: uuid.UUID) -> str:
    n, s = u.int, ""
    while n:
        n, r = divmod(n, 62)
        s = ALPHABET[r] + s
    return s.rjust(LENGTH, "0")


def decode(s: str) -> uuid.UUID | None:
    if len(s) != LENGTH:
        return None
    n = 0
    for c in s:
        i = ALPHABET.find(c)
        if i < 0:
            return None
        n = n * 62 + i
    if n >= 1 << 128:
        return None
    return uuid.UUID(int=n)
