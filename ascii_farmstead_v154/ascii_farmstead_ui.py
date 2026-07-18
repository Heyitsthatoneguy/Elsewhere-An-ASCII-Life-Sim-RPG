from __future__ import annotations

"""Terminal UI helpers for Elsewhere.

This module contains standalone menu, panel, and text-fitting helpers. It may
accept a game-like object for compact overlays, but it does not import FarmGame
or gameplay systems, keeping UI utilities reusable and low-risk.
"""

import shutil
import textwrap
from dataclasses import dataclass
from typing import List, Optional

from ascii_farmstead_support import (
    ANSI_RE,
    C,
    clear_screen,
    colorize,
    normalize_key,
    pad_visual,
    read_key,
)
from ascii_farmstead_data import (
    GUTTER_WIDTH,
    LEFT_PANEL_WIDTH,
    MAP_LINE_WIDTH,
    MENU_CONFIRM_KEYS,
)
from ascii_farmstead_state import GameState


def terminal_width() -> int:
    try:
        return shutil.get_terminal_size((100, 30)).columns
    except Exception:
        return 100

def terminal_height() -> int:
    try:
        return shutil.get_terminal_size((100, 30)).lines
    except Exception:
        return 30

def left_margin(content_width: int) -> str:
    cols = terminal_width()
    return " " * max(0, (cols - content_width) // 2)

def pad_to(text: str, width: int) -> str:
    """Pad text by visible length, ignoring ANSI color codes."""
    visible_len = len(strip_ansi(text))
    return text + " " * max(0, width - visible_len)

def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", str(text))

def visible_text_len(text: str) -> int:
    return len(strip_ansi(str(text)))


def meter_text(
    value: int,
    maximum: int,
    width: int = 8,
    detailed: bool = True,
) -> str:
    """Return a fixed-width, color-agnostic meter suitable for HUD chips."""
    width = max(3, int(width))
    maximum = max(1, int(maximum))
    value = max(0, min(maximum, int(value)))
    filled = int(round(width * value / maximum))
    full, empty = ("█", "░") if detailed else ("#", "-")
    return full * filled + empty * (width - filled)


def status_chip(text: object, style: str = "") -> str:
    """Render one compact status value with boundaries visible without color."""
    chip = f"[{str(text).strip()}]"
    return colorize(chip, style) if style else chip


def wrap_status_chips(chips: List[str], width: int) -> List[str]:
    """Wrap complete ANSI-aware chips without splitting their contents."""
    width = max(16, int(width))
    lines: List[str] = []
    current: List[str] = []
    current_width = 0
    for chip in [str(chip) for chip in chips if str(chip).strip()]:
        chip_width = visible_text_len(chip)
        if chip_width > width:
            chip = fit_text(chip, width)
            chip_width = visible_text_len(chip)
        added = chip_width + (1 if current else 0)
        if current and current_width + added > width:
            lines.append(" ".join(current))
            current = []
            current_width = 0
            added = chip_width
        current.append(chip)
        current_width += added
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def style_labeled_row(row: object) -> str:
    """Color a HUD row label while keeping its explanatory text neutral."""
    text = str(row)
    styles = {
        "MESSAGE |": C.UI_TITLE,
        "STATUS |": C.UI_SELECTED,
        "TARGET |": C.LANDMARK_ACTIVE,
        "TOOL |": C.INFRA,
        "ACTION |": C.SERVICE,
        "CONTROLS |": C.UI_MUTED,
    }
    for prefix, style in styles.items():
        if text.startswith(prefix):
            return colorize(prefix, style) + text[len(prefix):]
    return text

def fit_text(text: str, width: int) -> str:
    """Trim text by visible length when it cannot fit."""
    text = str(text)
    if visible_text_len(text) <= width:
        return text
    plain = strip_ansi(text)
    if width <= 1:
        return plain[:max(0, width)]
    marker = "..." if width >= 3 else "." * width
    return plain[:max(0, width - len(marker))] + marker

def wrap_panel_row(row: object, width: int) -> List[str]:
    """Wrap one panel row to visible width, preserving simple indentation."""
    text = strip_ansi(str(row))
    if not text:
        return [""]

    leading_len = len(text) - len(text.lstrip(" "))
    leading = text[:min(leading_len, max(0, width - 8))]
    body = text[leading_len:]
    first_prefix = leading
    next_prefix = leading + ("  " if leading_len < 2 else "")
    first_width = max(8, width - visible_text_len(first_prefix))
    next_width = max(8, width - visible_text_len(next_prefix))

    wrapped = textwrap.wrap(
        body,
        width=first_width,
        subsequent_indent="",
        break_long_words=True,
        break_on_hyphens=False,
        replace_whitespace=True,
        drop_whitespace=True,
    )
    if not wrapped:
        return [fit_text(first_prefix, width)]

    lines = [first_prefix + wrapped[0]]
    if len(wrapped) > 1:
        for part in textwrap.wrap(
            " ".join(wrapped[1:]),
            width=next_width,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=True,
            drop_whitespace=True,
        ):
            lines.append(next_prefix + part)
    return [fit_text(line, width) for line in lines]

def wrap_panel_rows(rows: List[object], width: int) -> List[str]:
    wrapped: List[str] = []
    for row in rows:
        wrapped.extend(wrap_panel_row(row, width))
    return wrapped

def dynamic_panel_width_for_text(lines: List[str], base_width: int = LEFT_PANEL_WIDTH) -> int:
    """Pick a panel width that fits visible text when possible."""
    longest = max([visible_text_len(line) for line in lines] + [base_width - 2])
    needed = min(longest + 2, 48)
    side_by_side_cap = terminal_width() - GUTTER_WIDTH - MAP_LINE_WIDTH
    terminal_cap = max(base_width, min(48, side_by_side_cap))
    return max(base_width, min(needed, terminal_cap))

@dataclass
class MenuItem:
    label: str
    value: object = None
    enabled: bool = True
    hint: str = ""

def menu_context_lines(
    selected_hint: str = "",
    footer: str = "",
    width: Optional[int] = None,
) -> List[str]:
    """Wrap changing menu guidance outside the selectable option area."""
    context_width = max(
        24,
        int(width if width is not None else terminal_width() - 2),
    )
    lines: List[str] = []
    if str(selected_hint or "").strip():
        lines.extend(
            wrap_panel_row(
                f"Selected: {str(selected_hint).strip()}",
                context_width,
            )
        )
    if str(footer or "").strip():
        lines.extend(wrap_panel_row(str(footer).strip(), context_width))
    return lines


def framed_row(content: object, width: int, style: str = "") -> str:
    """Return one padded box row, preserving ANSI-aware visible width."""
    width = max(24, int(width))
    inner = width - 4
    fitted = fit_text(str(content), inner)
    padded = fitted + " " * max(0, inner - visible_text_len(fitted))
    body = colorize(padded, style) if style else padded
    return colorize("│ ", C.UI_BORDER) + body + colorize(" │", C.UI_BORDER)


def menu_render_lines(
    title: str,
    items: List[MenuItem],
    selected: int,
    footer: str = "",
    extra_lines: Optional[List[str]] = None,
    width: Optional[int] = None,
    item_offset: int = 0,
    max_visible_items: Optional[int] = None,
) -> List[str]:
    """Compose a complete width-safe menu frame for printing or testing."""
    available = max(24, terminal_width() - 2)
    frame_width = max(24, min(int(width or 60), available))
    title_text = fit_text(f" {title} ", frame_width - 4)
    top_fill = max(0, frame_width - visible_text_len(title_text) - 2)
    lines = [colorize("┌" + title_text + "─" * top_fill + "┐", C.UI_BORDER + C.BOLD)]

    if extra_lines:
        for raw in extra_lines:
            for row in wrap_panel_row(raw, frame_width - 4):
                lines.append(framed_row(row, frame_width, C.UI_MUTED))
        lines.append(colorize("├" + "─" * (frame_width - 2) + "┤", C.UI_BORDER))

    item_offset = max(0, min(int(item_offset), max(0, len(items) - 1)))
    if max_visible_items is None:
        visible_items = list(enumerate(items))
    else:
        visible_count = max(1, int(max_visible_items))
        visible_items = list(enumerate(items[item_offset:item_offset + visible_count], start=item_offset))
        if item_offset > 0:
            lines.append(framed_row(f"  ↑ {item_offset} more", frame_width, C.UI_MUTED))

    for index, item in visible_items:
        is_selected = index == selected
        cursor = ">" if is_selected else " "
        status = " [unavailable]" if not item.enabled else ""
        content = f"{cursor} {item.label}{status}"
        style = (
            C.UI_SELECTED
            if is_selected and item.enabled
            else C.DIM
            if not item.enabled
            else ""
        )
        lines.append(framed_row(content, frame_width, style))
    if max_visible_items is not None:
        remaining = max(0, len(items) - (item_offset + len(visible_items)))
        if remaining:
            lines.append(framed_row(f"  ↓ {remaining} more", frame_width, C.UI_MUTED))

    selected_hint = items[selected].hint if 0 <= selected < len(items) else ""
    if footer or selected_hint:
        lines.append(colorize("├" + "─" * (frame_width - 2) + "┤", C.UI_BORDER))
        for row in menu_context_lines(selected_hint, footer, frame_width - 4):
            lines.append(framed_row(row, frame_width, C.UI_MUTED))
    lines.append(colorize("└" + "─" * (frame_width - 2) + "┘", C.UI_BORDER))
    return lines

def draw_menu(
    title: str,
    items: List[MenuItem],
    selected: int,
    footer: str = "",
    extra_lines: Optional[List[str]] = None,
    item_offset: int = 0,
    max_visible_items: Optional[int] = None,
):
    clear_screen()
    print("\n".join(menu_render_lines(
        title,
        items,
        selected,
        footer,
        extra_lines,
        item_offset=item_offset,
        max_visible_items=max_visible_items,
    )))

def menu_select(title: str, items: List[MenuItem], footer: str = "", extra_lines: Optional[List[str]] = None) -> Optional[MenuItem]:
    """Arrow-key controlled menu. Returns selected MenuItem or None if cancelled."""
    if not items:
        return None

    selected = 0
    # Prefer first enabled item, but allow every item to be highlighted so
    # unavailable choices can explain their requirements in the hint line.
    for i, item in enumerate(items):
        if item.enabled:
            selected = i
            break

    extra_height = len(wrap_panel_rows(list(extra_lines or []), 56)) if extra_lines else 0
    max_visible = max(4, min(14, terminal_height() - extra_height - 10))
    item_offset = max(0, min(selected, max(0, len(items) - max_visible)))

    while True:
        if selected < item_offset:
            item_offset = selected
        elif selected >= item_offset + max_visible:
            item_offset = selected - max_visible + 1
        controls = "W/S or ↑/↓ move | A/D or ←/→ page | Z/Enter select | B/X/Esc/Q cancel"
        context_footer = f"{footer} | {controls}" if footer else controls
        draw_menu(
            title,
            items,
            selected,
            context_footer,
            extra_lines,
            item_offset=item_offset,
            max_visible_items=max_visible,
        )
        key = normalize_key(read_key())

        if key in ["\t", "\x1b", "q", "x", "b"]:
            return None

        if key in ["w", "UP"]:
            selected = (selected - 1) % len(items)
        elif key in ["s", "DOWN"]:
            selected = (selected + 1) % len(items)
        elif key in ["a", "LEFT", "PGUP"]:
            selected = max(0, selected - max_visible)
        elif key in ["d", "RIGHT", "PGDN"]:
            selected = min(len(items) - 1, selected + max_visible)
        elif key == "HOME":
            selected = 0
        elif key == "END":
            selected = len(items) - 1
        elif key in MENU_CONFIRM_KEYS:
            if items[selected].enabled:
                return items[selected]

def clean_text_entry(value: object, default: str = "", max_length: int = 16) -> str:
    cleaned = "".join(ch for ch in str(value or "").strip() if ch.isprintable())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        cleaned = "".join(ch for ch in str(default or "").strip() if ch.isprintable())
        cleaned = " ".join(cleaned.split())
    return cleaned[:max(1, int(max_length))]


def text_entry_menu(title: str, prompt: str, default: str = "", max_length: int = 16) -> Optional[str]:
    """Simple single-line text entry used by startup character creation."""
    value = str(default or "")
    while True:
        clear_screen()
        print(title)
        print("=" * max(40, len(title)))
        print(prompt)
        print()
        print(f"> {value}")
        print()
        print("Type to edit | Backspace delete | Enter accept | Esc cancel")

        key = read_key()
        if key in ["\x1b"]:
            return None
        if key in ["\r", "\n"]:
            return clean_text_entry(value, default, max_length)
        if key in ["\b", "\x7f"]:
            value = value[:-1]
            continue
        if len(key) == 1 and key.isprintable() and len(value) < max_length:
            value += key

def quantity_menu(title: str, unit_label: str, unit_price: int, max_qty: int, start_qty: int = 1) -> int:
    """Arrow-key quantity picker. Returns selected quantity, or 0 if cancelled."""
    if max_qty <= 0:
        return 0

    qty = max(1, min(start_qty, max_qty))

    while True:
        total = qty * unit_price
        clear_screen()
        print(title)
        print("=" * max(40, len(title)))
        print(f"Item: {unit_label}")
        print(f"Unit price: ${unit_price}")
        print()
        print(f"Quantity: {qty}")
        print(f"Total:    ${total}")
        print()
        print("Left/Right or A/D: -/+ 1")
        print("Up/Down or W/S:    +/- 5")
        print("Z/Enter/Space:       Confirm")
        print("X/Esc/Q:           Cancel")

        key = normalize_key(read_key())
        if key in ["\t", "\x1b", "q", "x"]:
            return 0
        if key in ["a", "LEFT"]:
            qty = max(1, qty - 1)
        elif key in ["d", "RIGHT"]:
            qty = min(max_qty, qty + 1)
        elif key in ["w", "UP"]:
            qty = min(max_qty, qty + 5)
        elif key in ["s", "DOWN"]:
            qty = max(1, qty - 5)
        elif key in MENU_CONFIRM_KEYS:
            return qty
        elif key in ["\x1b", "q", "x"]:
            return 0

def compact_menu_select(game, title: str, items: List[MenuItem], footer: str = "") -> Optional[MenuItem]:
    """
    Smaller in-game submenu: redraws the farm, then shows a compact option list
    underneath instead of sending the player to a separate full-screen page.
    """
    if not items:
        return None

    selected = 0
    for i, item in enumerate(items):
        if item.enabled:
            selected = i
            break
    max_visible = max(4, min(8, terminal_height() - 22))
    item_offset = max(0, min(selected, max(0, len(items) - max_visible)))

    while True:
        if selected < item_offset:
            item_offset = selected
        elif selected >= item_offset + max_visible:
            item_offset = selected - max_visible + 1
        game.draw()
        print()
        context_footer = (
            f"{footer} | Arrow keys/WASD move | Z/Enter select | B/X/Esc/Q cancel"
            if footer
            else "Arrow keys/WASD move | Z/Enter select | B/X/Esc/Q cancel"
        )
        print("\n".join(menu_render_lines(
            title,
            items,
            selected,
            context_footer,
            width=min(60, max(24, terminal_width() - 2)),
            item_offset=item_offset,
            max_visible_items=max_visible,
        )))

        key = normalize_key(read_key())
        if key in ["\t", "\x1b", "q", "x", "b"]:
            return None
        if key in ["w", "UP"]:
            selected = (selected - 1) % len(items)
        elif key in ["s", "DOWN"]:
            selected = (selected + 1) % len(items)
        elif key in ["a", "LEFT", "PGUP"]:
            selected = max(0, selected - max_visible)
        elif key in ["d", "RIGHT", "PGDN"]:
            selected = min(len(items) - 1, selected + max_visible)
        elif key in MENU_CONFIRM_KEYS:
            if items[selected].enabled:
                return items[selected]

def compact_quantity_menu(game, title: str, unit_label: str, unit_price: int, max_qty: int, start_qty: int = 1) -> int:
    """Compact overlay quantity picker. Returns quantity, or 0 if cancelled."""
    if max_qty <= 0:
        return 0

    qty = max(1, min(start_qty, max_qty))

    while True:
        game.draw()
        print()
        print(f"+- {title} " + "-" * max(1, 54 - len(title)))
        print(f"| Item:      {unit_label}")
        print(f"| Unit:      ${unit_price}")
        print(f"| Quantity:  {qty}")
        print(f"| Total:     ${qty * unit_price}")
        print("+" + "-" * 60)
        print("Left/Right or A/D: -/+1 | Up/Down or W/S: +/-5 | Z/Enter: confirm | X/Esc/Q: cancel")

        key = normalize_key(read_key())
        if key in ["\t", "\x1b", "q", "x"]:
            return 0
        if key in ["a", "LEFT"]:
            qty = max(1, qty - 1)
        elif key in ["d", "RIGHT"]:
            qty = min(max_qty, qty + 1)
        elif key in ["w", "UP"]:
            qty = min(max_qty, qty + 5)
        elif key in ["s", "DOWN"]:
            qty = max(1, qty - 5)
        elif key in MENU_CONFIRM_KEYS:
            return qty
        elif key in ["\x1b", "q", "x"]:
            return 0



__all__ = [
    'terminal_width',
    'left_margin',
    'pad_to',
    'strip_ansi',
    'visible_text_len',
    'meter_text',
    'status_chip',
    'wrap_status_chips',
    'style_labeled_row',
    'fit_text',
    'wrap_panel_row',
    'wrap_panel_rows',
    'dynamic_panel_width_for_text',
    'MenuItem',
    'draw_menu',
    'framed_row',
    'menu_render_lines',
    'menu_context_lines',
    'menu_select',
    'text_entry_menu',
    'quantity_menu',
    'compact_menu_select',
    'clean_text_entry',
    'compact_quantity_menu'
]
