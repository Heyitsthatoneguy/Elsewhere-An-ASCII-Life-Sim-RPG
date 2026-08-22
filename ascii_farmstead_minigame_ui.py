"""Compact shared presentation helpers for Elsewhere's playable minigames."""

from __future__ import annotations

import textwrap
from typing import List, Sequence, Tuple

from ascii_farmstead_support import C, colorize


MINIGAME_WIDTH = 100


def minigame_title(title: str, status: str = "") -> None:
    print(colorize(str(title).upper(), C.UI_TITLE))
    if status:
        print(colorize(str(status), C.UI_MUTED))


def minigame_section(label: str, detail: str = "", width: int = MINIGAME_WIDTH) -> None:
    heading = f" {str(label).upper()} "
    if detail:
        heading += f"{detail} "
    rule = heading + "-" * max(2, min(int(width), 100) - len(heading))
    print(colorize(rule, C.UI_BORDER))


def minigame_meter(
    label: str,
    value: int,
    maximum: int,
    *,
    width: int = 20,
    shade: str = C.UI_SELECTED,
) -> str:
    maximum = max(1, int(maximum))
    value = max(0, min(maximum, int(value)))
    width = max(4, int(width))
    filled = round(width * value / maximum)
    bar = colorize("#" * filled, shade) + colorize("-" * (width - filled), C.UI_MUTED)
    return f"{label}: [{bar}] {value}/{maximum}"


def minigame_notice(text: object, *, prefix: str = "STATUS") -> None:
    message = str(text or "").strip()
    if not message:
        return
    wrapped = textwrap.wrap(message, width=MINIGAME_WIDTH - len(prefix) - 3) or [message]
    print(colorize(f"{prefix}: ", C.UI_SELECTED) + wrapped[0])
    for line in wrapped[1:]:
        print(" " * (len(prefix) + 2) + line)


def minigame_controls(*groups: str) -> None:
    entries = [str(group).strip() for group in groups if str(group).strip()]
    if not entries:
        return
    prefix = colorize("CONTROLS ", C.UI_BORDER)
    continuation = " " * len("CONTROLS ")
    current = prefix
    current_width = len("CONTROLS ")
    for entry in entries:
        separator = "" if current_width == len("CONTROLS ") else " | "
        added_width = len(separator) + len(entry)
        if current_width + added_width > MINIGAME_WIDTH and current_width > len("CONTROLS "):
            print(current)
            current = continuation + entry
            current_width = len("CONTROLS ") + len(entry)
        else:
            current += separator + entry
            current_width += added_width
    print(current)


def minigame_actions(
    actions: Sequence[Tuple[str, str]],
    selected: int,
    *,
    columns: int = 2,
) -> None:
    """Render selectable actions with stable numeric shortcuts."""
    if not actions:
        return
    columns = max(1, int(columns))
    cell_width = max(18, min(46, (MINIGAME_WIDTH - columns + 1) // columns))
    rendered: List[str] = []
    for index, (_value, label) in enumerate(actions):
        marker = ">" if index == selected else " "
        text = f"{marker} {index + 1}. {label}"
        if index == selected:
            text = colorize(text, C.UI_SELECTED)
        rendered.append(text)
    for start in range(0, len(rendered), columns):
        row = rendered[start:start + columns]
        print(" ".join(
            text + " " * max(1, cell_width - _visible_len(text))
            for text in row
        ).rstrip())


def minigame_tool_strip(labels: Sequence[str], selected: int) -> None:
    pieces: List[str] = []
    for index, label in enumerate(labels):
        text = f"{index + 1}:{label}"
        if index == selected:
            text = colorize(f"[{text}]", C.UI_SELECTED)
        else:
            text = f" {text} "
        pieces.append(text)
    print("  ".join(pieces))


def _visible_len(text: str) -> int:
    from ascii_farmstead_ui import visible_text_len

    return visible_text_len(text)


__all__ = [
    "MINIGAME_WIDTH",
    "minigame_actions",
    "minigame_controls",
    "minigame_meter",
    "minigame_notice",
    "minigame_section",
    "minigame_title",
    "minigame_tool_strip",
]
