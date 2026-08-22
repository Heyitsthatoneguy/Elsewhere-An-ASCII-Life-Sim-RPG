from __future__ import annotations

from typing import Iterable

from .models import Pos

def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def neighbors4(pos: Pos) -> Iterable[Pos]:
    x, y = pos
    yield x + 1, y
    yield x - 1, y
    yield x, y + 1
    yield x, y - 1


