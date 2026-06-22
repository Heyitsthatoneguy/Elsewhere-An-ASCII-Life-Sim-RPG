from __future__ import annotations

import re
import sys
import textwrap
from typing import List

from .constants import NO_ALT_SCREEN, NO_COLOR

class Style:
    RESET = "" if NO_COLOR else "\033[0m"
    BOLD = "" if NO_COLOR else "\033[1m"
    DIM = "" if NO_COLOR else "\033[2m"

    BLACK = "" if NO_COLOR else "\033[30m"
    RED = "" if NO_COLOR else "\033[31m"
    GREEN = "" if NO_COLOR else "\033[32m"
    YELLOW = "" if NO_COLOR else "\033[33m"
    BLUE = "" if NO_COLOR else "\033[34m"
    MAGENTA = "" if NO_COLOR else "\033[35m"
    CYAN = "" if NO_COLOR else "\033[36m"
    WHITE = "" if NO_COLOR else "\033[37m"

    BRIGHT_BLACK = "" if NO_COLOR else "\033[90m"
    BRIGHT_RED = "" if NO_COLOR else "\033[91m"
    BRIGHT_GREEN = "" if NO_COLOR else "\033[92m"
    BRIGHT_YELLOW = "" if NO_COLOR else "\033[93m"
    BRIGHT_BLUE = "" if NO_COLOR else "\033[94m"
    BRIGHT_MAGENTA = "" if NO_COLOR else "\033[95m"
    BRIGHT_CYAN = "" if NO_COLOR else "\033[96m"
    BRIGHT_WHITE = "" if NO_COLOR else "\033[97m"

    BG_DARK = "" if NO_COLOR else "\033[48;5;236m"
    BG_PANEL = "" if NO_COLOR else "\033[48;5;235m"
    BG_SELECT = "" if NO_COLOR else "\033[48;5;250m"
    BG_MOVE = "" if NO_COLOR else "\033[48;5;23m"
    BG_PATH = "" if NO_COLOR else "\033[48;5;28m"
    BG_DANGER = "" if NO_COLOR else "\033[48;5;52m"
    BG_ATTACK = "" if NO_COLOR else "\033[48;5;88m"
    BG_SKILL = "" if NO_COLOR else "\033[48;5;54m"
    BG_OVERWATCH = "" if NO_COLOR else "\033[48;5;25m"


def c(text: str, *styles: str) -> str:
    if NO_COLOR:
        return text
    return "".join(styles) + text + Style.RESET


def clear_screen(clear_scrollback: bool = False) -> None:
    # 2J clears the visible screen, H returns the cursor home.
    # 3J also clears scrollback in terminals that support it.
    if clear_scrollback and not NO_ALT_SCREEN:
        sys.stdout.write("\033[3J")
    elif clear_scrollback:
        sys.stdout.write("\033[3J")
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def enter_alt_screen() -> None:
    if not NO_ALT_SCREEN:
        # Alternate screen keeps redraw frames out of normal scrollback.
        sys.stdout.write("\033[?1049h")
        sys.stdout.flush()


def exit_alt_screen() -> None:
    if not NO_ALT_SCREEN:
        sys.stdout.write("\033[?1049l")
        sys.stdout.flush()


def hide_cursor() -> None:
    if not NO_COLOR:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()


def show_cursor() -> None:
    if not NO_COLOR:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


def strip_ansi_len(text: str) -> int:
    if NO_COLOR:
        return len(text)
    count = 0
    esc = False
    for ch in text:
        if ch == "\033":
            esc = True
            continue
        if esc:
            if ch.isalpha():
                esc = False
            continue
        count += 1
    return count


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - strip_ansi_len(text))


def clip(text: str, width: int) -> str:
    return clip_visible(str(text), width)


def clip_visible(text: str, width: int) -> str:
    """ANSI-aware visible-width clipping that never cuts inside escape codes."""
    raw = str(text)
    if width <= 0:
        return ""
    if strip_ansi_len(raw) <= width:
        return raw

    target = max(0, width - 1)
    result: List[str] = []
    visible = 0
    i = 0
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")

    while i < len(raw) and visible < target:
        if raw[i] == "\033":
            match = ansi_pattern.match(raw, i)
            if match:
                result.append(match.group(0))
                i = match.end()
                continue
            # Unknown escape/control sequence: drop it rather than showing
            # broken terminal bytes.
            i += 1
            continue
        result.append(raw[i])
        visible += 1
        i += 1

    clipped = "".join(result) + "…"
    if not NO_COLOR:
        clipped += Style.RESET
    return clipped

def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", str(text))


def wrap_plain(text: str, width: int, subsequent_indent: str = "") -> List[str]:
    """Wrap plain terminal text without letting a line exceed width."""
    if width <= 0:
        return [""]
    raw_lines = strip_ansi(str(text)).splitlines() or [""]
    wrapped: List[str] = []
    for raw_line in raw_lines:
        parts = textwrap.wrap(
            raw_line,
            width=width,
            subsequent_indent=subsequent_indent,
            replace_whitespace=False,
            drop_whitespace=True,
            break_long_words=True,
            break_on_hyphens=False,
        )
        wrapped.extend(parts or [""])
    return wrapped


def wrap_labeled(label: str, value: str, width: int) -> List[str]:
    prefix = str(label)
    lines = wrap_plain(str(value), max(8, width - len(prefix)))
    if not lines:
        return [prefix]
    out = [prefix + lines[0]]
    out.extend((" " * min(len(prefix), max(0, width - 8))) + line for line in lines[1:])
    return out

