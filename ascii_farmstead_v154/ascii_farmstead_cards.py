"""Shared authored playing-card visuals for Elsewhere's card games."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from ascii_farmstead_support import C, colorize
from ascii_farmstead_ui import visible_text_len


CardLike = Union[str, Tuple[str, str], List[str]]
CARD_RENDER_WIDTH = 12
CARD_RENDER_HEIGHT = 7
CARD_SUITS = {
    "H": "♥",
    "D": "♦",
    "C": "♣",
    "S": "♠",
}
RED_SUITS = {"H", "D"}
WHITE_SUITS = {"C", "S"}


def card_rank_suit(card: CardLike) -> Tuple[str, str]:
    if isinstance(card, (tuple, list)) and len(card) == 2:
        return str(card[0]), str(card[1]).upper()
    text = str(card)
    if len(text) < 2:
        raise ValueError("A playing card requires a rank and suit.")
    return text[:-1], text[-1].upper()


def card_suit_glyph(suit: str) -> str:
    return CARD_SUITS.get(str(suit).upper(), str(suit).upper())


def _pad_card_line(line: str) -> str:
    return str(line) + " " * max(0, CARD_RENDER_WIDTH - len(str(line)))


def plain_card_lines(card: CardLike, hidden: bool = False) -> List[str]:
    """Return the user-authored templates before terminal color is applied."""
    if hidden:
        return [
            _pad_card_line("+-----+"),
            _pad_card_line("|     |"),
            _pad_card_line("|     |"),
            _pad_card_line("|  ?  |"),
            _pad_card_line("|     |"),
            _pad_card_line("|     |"),
            _pad_card_line("+-----+"),
        ]
    rank, suit = card_rank_suit(card)
    glyph = card_suit_glyph(suit)
    if rank == "10":
        lines = [
            "+-----+",
            "|10   |",
            "|     |",
           f"|  {glyph}  |",
            "|     |",
            "|   10|",
            "+-----+",
        ]
    else:
        lines = [
            "+-----+",
           f"|{rank}    |",
            "|     |",
           f"|  {glyph}  |",
            "|     |",
           f"|    {rank}|",
            "+-----+",
        ]
    return [_pad_card_line(line) for line in lines]


def card_color(card: CardLike) -> str:
    _rank, suit = card_rank_suit(card)
    return C.ROOF_RED if suit in RED_SUITS else C.TUNDRA


def rendered_card_lines(card: CardLike, hidden: bool = False) -> List[str]:
    lines = plain_card_lines(card, hidden=hidden)
    if hidden:
        return lines
    rank, suit = card_rank_suit(card)
    glyph = card_suit_glyph(suit)
    shade = card_color(card)
    rendered: List[str] = []
    for line in lines:
        colored = line.replace(rank, colorize(rank, shade))
        colored = colored.replace(glyph, colorize(glyph, shade))
        rendered.append(colored)
    return rendered


def card_corner_line(card: CardLike, hidden: bool = False) -> str:
    """Return the rank-bearing slice used by overlapping Solitaire columns."""
    return rendered_card_lines(card, hidden=hidden)[1]


def _join_blocks(blocks: Sequence[Sequence[str]], gap: int = 1) -> List[str]:
    if not blocks:
        return []
    spacer = " " * max(0, int(gap))
    height = max(len(block) for block in blocks)
    rows: List[str] = []
    for row in range(height):
        pieces = [
            block[row] if row < len(block) else " " * CARD_RENDER_WIDTH
            for block in blocks
        ]
        rows.append(spacer.join(pieces).rstrip())
    return rows


def rendered_card_rows(
    cards: Sequence[CardLike],
    *,
    hidden: Optional[Sequence[bool]] = None,
    max_per_row: int = 7,
    cursor: Optional[int] = None,
    selected: Optional[Sequence[int]] = None,
    show_numbers: bool = False,
) -> List[str]:
    """Compose full cards into wrapped terminal rows with external markers."""
    if not cards:
        return ["(none)"]
    max_per_row = max(1, int(max_per_row))
    hidden_flags = list(hidden or [])
    selected_set = {int(value) for value in (selected or [])}
    output: List[str] = []
    for start in range(0, len(cards), max_per_row):
        group = list(cards[start:start + max_per_row])
        blocks = [
            rendered_card_lines(
                card,
                hidden=bool(hidden_flags[start + offset]) if start + offset < len(hidden_flags) else False,
            )
            for offset, card in enumerate(group)
        ]
        output.extend(_join_blocks(blocks))
        markers: List[str] = []
        for offset, _card in enumerate(group):
            index = start + offset
            if cursor == index and index in selected_set:
                label = "^SELECTED^"
            elif cursor == index:
                label = "^^^^"
            elif index in selected_set:
                label = "SELECTED"
            elif show_numbers:
                label = str(index + 1)
            else:
                label = ""
            left = max(0, (CARD_RENDER_WIDTH - visible_text_len(label)) // 2)
            markers.append((" " * left + label).ljust(CARD_RENDER_WIDTH))
        if any(marker.strip() for marker in markers):
            output.append((" ".join(markers)).rstrip())
        if start + max_per_row < len(cards):
            output.append("")
    return output


def print_card_rows(*args, indent: str = "", **kwargs) -> None:
    for line in rendered_card_rows(*args, **kwargs):
        print(f"{indent}{line}")


__all__ = [
    "CARD_RENDER_HEIGHT",
    "CARD_RENDER_WIDTH",
    "CARD_SUITS",
    "RED_SUITS",
    "WHITE_SUITS",
    "card_color",
    "card_corner_line",
    "card_rank_suit",
    "card_suit_glyph",
    "plain_card_lines",
    "print_card_rows",
    "rendered_card_lines",
    "rendered_card_rows",
]
