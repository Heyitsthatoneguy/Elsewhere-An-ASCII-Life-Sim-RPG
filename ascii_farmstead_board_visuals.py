"""Shared high-contrast tile styling for Elsewhere's grid board games."""

from __future__ import annotations

from ascii_farmstead_support import colorize


BOARD_LIGHT_BG = "\033[48;5;255m"
BOARD_DARK_BG = "\033[48;5;240m"

_LIGHT_TILE_INK = {
    "empty": "\033[38;5;238m",
    "pale_piece": "\033[38;5;235;1m",
    "red_piece": "\033[38;5;88;1m",
    "cursor": "\033[38;5;24;1m",
    "selected": "\033[38;5;94;1m",
    "destination": "\033[38;5;22;1m",
}
_DARK_TILE_INK = {
    "empty": "\033[38;5;255m",
    "pale_piece": "\033[38;5;255;1m",
    "red_piece": "\033[38;5;210;1m",
    "cursor": "\033[38;5;117;1m",
    "selected": "\033[38;5;220;1m",
    "destination": "\033[38;5;120;1m",
}


def board_tile_is_light(x: int, y: int) -> bool:
    return (int(x) + int(y)) % 2 == 0


def board_tile_background(x: int, y: int) -> str:
    return BOARD_LIGHT_BG if board_tile_is_light(x, y) else BOARD_DARK_BG


def board_tile(text: str, x: int, y: int, role: str = "empty") -> str:
    """Color one complete fixed-width tile without changing its geometry."""
    light = board_tile_is_light(x, y)
    inks = _LIGHT_TILE_INK if light else _DARK_TILE_INK
    ink = inks.get(str(role), inks["empty"])
    return colorize(str(text), board_tile_background(x, y) + ink)


__all__ = [
    "BOARD_DARK_BG",
    "BOARD_LIGHT_BG",
    "board_tile",
    "board_tile_background",
    "board_tile_is_light",
]
