"""Persistent draw-one Klondike Solitaire with a cursor-controlled ASCII table."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from ascii_farmstead_cards import (
    CARD_RENDER_WIDTH,
    card_color,
    card_corner_line,
    card_suit_glyph,
    rendered_card_lines,
)
from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_minigame_ui import minigame_controls, minigame_notice, minigame_section, minigame_title
from ascii_farmstead_support import C, clear_screen, colorize, movement_delta_for_key, normalize_key, read_key
from ascii_farmstead_ui import MenuItem


SOLITAIRE_RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SOLITAIRE_SUITS = ("S", "H", "D", "C")
SOLITAIRE_VALUE = {rank: index + 1 for index, rank in enumerate(SOLITAIRE_RANKS)}
SOLITAIRE_STATS_DEFAULTS = {
    "games_started": 0, "wins": 0, "abandons": 0, "moves": 0,
    "cards_to_foundation": 0, "stock_recycles": 0, "best_moves": 0,
    "current_streak": 0, "best_streak": 0,
}


def solitaire_rank(card: str) -> str:
    return str(card)[:-1]


def solitaire_suit(card: str) -> str:
    return str(card)[-1:]


def solitaire_value(card: str) -> int:
    return SOLITAIRE_VALUE[solitaire_rank(card)]


def solitaire_color(card: str) -> str:
    return "red" if solitaire_suit(card) in {"H", "D"} else "black"


def make_solitaire_deck(rng: Optional[random.Random] = None) -> List[str]:
    deck = [f"{rank}{suit}" for suit in SOLITAIRE_SUITS for rank in SOLITAIRE_RANKS]
    (rng or random.Random()).shuffle(deck)
    return deck


def new_solitaire_match(rng: random.Random, venue: str) -> Dict[str, object]:
    deck = make_solitaire_deck(rng)
    tableau: List[List[Dict[str, object]]] = [[] for _ in range(7)]
    for row in range(7):
        for pile in range(row, 7):
            tableau[pile].append({"card": deck.pop(), "up": pile == row})
    return {
        "venue": str(venue), "stock": deck, "waste": [],
        "foundations": {suit: [] for suit in SOLITAIRE_SUITS},
        "tableau": tableau, "moves": 0, "recycles": 0,
        "foundation_moves": 0, "pending_minutes": 0,
        "note": "Draw from the stock or select a face-up card sequence.",
    }


def solitaire_can_tableau(moving_card: str, destination_card: Optional[str]) -> bool:
    if destination_card is None:
        return solitaire_rank(moving_card) == "K"
    return (
        solitaire_color(moving_card) != solitaire_color(destination_card)
        and solitaire_value(destination_card) == solitaire_value(moving_card) + 1
    )


def solitaire_can_foundation(card: str, foundation: Sequence[str]) -> bool:
    if not foundation:
        return solitaire_rank(card) == "A"
    return (
        solitaire_suit(card) == solitaire_suit(foundation[-1])
        and solitaire_value(card) == solitaire_value(foundation[-1]) + 1
    )


def solitaire_tableau_sequence_valid(entries: Sequence[Dict[str, object]]) -> bool:
    if not entries or not all(bool(entry.get("up")) for entry in entries):
        return False
    for first, second in zip(entries, entries[1:]):
        if not solitaire_can_tableau(str(second["card"]), str(first["card"])):
            return False
    return True


def solitaire_flip_exposed(match: Dict[str, object], pile_index: int) -> bool:
    pile = match["tableau"][pile_index]
    if pile and not bool(pile[-1].get("up")):
        pile[-1]["up"] = True
        return True
    return False


def solitaire_draw_stock(match: Dict[str, object]) -> str:
    stock: List[str] = match["stock"]
    waste: List[str] = match["waste"]
    if stock:
        card = stock.pop()
        waste.append(card)
        match["moves"] = int(match.get("moves", 0)) + 1
        match["note"] = f"Drew {card} from the stock."
        return "draw"
    if waste:
        match["stock"] = list(reversed(waste))
        match["waste"] = []
        match["recycles"] = int(match.get("recycles", 0)) + 1
        match["moves"] = int(match.get("moves", 0)) + 1
        match["note"] = "Recycled the waste into the stock."
        return "recycle"
    match["note"] = "The stock and waste are empty."
    return ""


def solitaire_move_waste_to_tableau(match: Dict[str, object], destination: int) -> bool:
    if not match["waste"]:
        return False
    card = str(match["waste"][-1])
    pile = match["tableau"][destination]
    top = str(pile[-1]["card"]) if pile else None
    if not solitaire_can_tableau(card, top):
        return False
    match["waste"].pop()
    pile.append({"card": card, "up": True})
    match["moves"] += 1
    match["note"] = f"Moved {card} from waste to column {destination + 1}."
    return True


def solitaire_move_waste_to_foundation(match: Dict[str, object], suit: str) -> bool:
    if not match["waste"]:
        return False
    card = str(match["waste"][-1])
    foundation = match["foundations"][suit]
    if solitaire_suit(card) != suit or not solitaire_can_foundation(card, foundation):
        return False
    match["waste"].pop()
    foundation.append(card)
    match["moves"] += 1
    match["foundation_moves"] += 1
    match["note"] = f"Moved {card} to its foundation."
    return True


def solitaire_move_tableau_to_tableau(
    match: Dict[str, object], source: int, start: int, destination: int,
) -> bool:
    if source == destination:
        return False
    source_pile = match["tableau"][source]
    if not 0 <= start < len(source_pile):
        return False
    moving = source_pile[start:]
    if not solitaire_tableau_sequence_valid(moving):
        return False
    destination_pile = match["tableau"][destination]
    top = str(destination_pile[-1]["card"]) if destination_pile else None
    if not solitaire_can_tableau(str(moving[0]["card"]), top):
        return False
    del source_pile[start:]
    destination_pile.extend(moving)
    flipped = solitaire_flip_exposed(match, source)
    match["moves"] += 1
    match["note"] = (
        f"Moved {len(moving)} card(s) to column {destination + 1}"
        + (" and revealed a card." if flipped else ".")
    )
    return True


def solitaire_move_tableau_to_foundation(match: Dict[str, object], source: int, suit: str) -> bool:
    pile = match["tableau"][source]
    if not pile or not bool(pile[-1].get("up")):
        return False
    card = str(pile[-1]["card"])
    foundation = match["foundations"][suit]
    if solitaire_suit(card) != suit or not solitaire_can_foundation(card, foundation):
        return False
    pile.pop()
    foundation.append(card)
    flipped = solitaire_flip_exposed(match, source)
    match["moves"] += 1
    match["foundation_moves"] += 1
    match["note"] = f"Moved {card} to its foundation" + (" and revealed a card." if flipped else ".")
    return True


def solitaire_move_foundation_to_tableau(match: Dict[str, object], suit: str, destination: int) -> bool:
    foundation = match["foundations"][suit]
    if not foundation:
        return False
    card = str(foundation[-1])
    pile = match["tableau"][destination]
    top = str(pile[-1]["card"]) if pile else None
    if not solitaire_can_tableau(card, top):
        return False
    foundation.pop()
    pile.append({"card": card, "up": True})
    match["moves"] += 1
    match["note"] = f"Returned {card} from its foundation to column {destination + 1}."
    return True


def solitaire_won(match: Dict[str, object]) -> bool:
    return all(len(match["foundations"][suit]) == 13 for suit in SOLITAIRE_SUITS)


def solitaire_hint(match: Dict[str, object]) -> str:
    if match["waste"]:
        card = str(match["waste"][-1])
        suit = solitaire_suit(card)
        if solitaire_can_foundation(card, match["foundations"][suit]):
            return f"Move waste card {card} to its foundation."
        for destination, pile in enumerate(match["tableau"]):
            top = str(pile[-1]["card"]) if pile else None
            if solitaire_can_tableau(card, top):
                return f"Move waste card {card} to column {destination + 1}."
    for source, pile in enumerate(match["tableau"]):
        if pile and bool(pile[-1].get("up")):
            card = str(pile[-1]["card"])
            suit = solitaire_suit(card)
            if solitaire_can_foundation(card, match["foundations"][suit]):
                return f"Move {card} from column {source + 1} to its foundation."
        for start, entry in enumerate(pile):
            if not bool(entry.get("up")):
                continue
            moving = pile[start:]
            if not solitaire_tableau_sequence_valid(moving):
                continue
            card = str(entry["card"])
            for destination, target in enumerate(match["tableau"]):
                if source == destination:
                    continue
                top = str(target[-1]["card"]) if target else None
                if solitaire_can_tableau(card, top):
                    return f"Move {card} and its sequence from column {source + 1} to {destination + 1}."
    if match["stock"] or match["waste"]:
        return "Draw or recycle the stock."
    return "No obvious move is available; the deal may be blocked."


class SolitaireMixin:
    def ensure_solitaire_state(self) -> None:
        stats = getattr(self.state, "tavern_solitaire_stats", None)
        if not isinstance(stats, dict):
            stats = {}
        cleaned = {}
        for key, default in SOLITAIRE_STATS_DEFAULTS.items():
            try:
                cleaned[key] = max(0, int(stats.get(key, default) or 0))
            except (TypeError, ValueError):
                cleaned[key] = default
        self.state.tavern_solitaire_stats = cleaned
        if not self.valid_solitaire_match(getattr(self.state, "tavern_solitaire_match", None)):
            self.state.tavern_solitaire_match = {}

    @staticmethod
    def valid_solitaire_match(match: object) -> bool:
        if not isinstance(match, dict) or not match:
            return False
        try:
            cards: List[str] = list(match.get("stock", [])) + list(match.get("waste", []))
            foundations = match.get("foundations", {})
            tableau = match.get("tableau", [])
            if not isinstance(foundations, dict) or set(foundations) != set(SOLITAIRE_SUITS):
                return False
            for suit in SOLITAIRE_SUITS:
                cards.extend(foundations[suit])
            if not isinstance(tableau, list) or len(tableau) != 7:
                return False
            for pile in tableau:
                if not isinstance(pile, list):
                    return False
                cards.extend(str(entry["card"]) for entry in pile if isinstance(entry, dict))
            expected = {f"{rank}{suit}" for suit in SOLITAIRE_SUITS for rank in SOLITAIRE_RANKS}
            return len(cards) == 52 and set(cards) == expected
        except (KeyError, TypeError, ValueError):
            return False

    def new_solitaire_game(self, venue: str) -> Dict[str, object]:
        rng = random.Random(
            int(getattr(self.state, "wilderness_seed", 0))
            + int(getattr(self.state, "absolute_day", 0)) * 32771
            + int(getattr(self.state, "hour", 0)) * 257
            + int(self.state.tavern_solitaire_stats.get("games_started", 0)) * 65537
        )
        match = new_solitaire_match(rng, venue)
        self.state.tavern_solitaire_match = match
        self.state.tavern_solitaire_stats["games_started"] += 1
        return match

    @staticmethod
    def solitaire_rules_lines() -> List[str]:
        return [
            "KLONDIKE SOLITAIRE", "",
            "- Build four foundations upward from Ace to King, one foundation per suit.",
            "- Tableau columns build downward in alternating colors. Only Kings may enter empty columns.",
            "- Any complete face-up descending alternating sequence may move between tableau columns.",
            "- Turn the stock one card at a time. When it empties, recycle the waste without a limit.",
            "- Exposed face-down tableau cards turn face up automatically.",
            "- Hearts and Diamonds are red; Clubs and Spades are white. Covered cards display a face-down slice.",
            "- Select stock, waste, foundation, or tableau with A/D. Use W/S to choose a deeper face-up sequence.",
            "- Number keys 1-7 jump to tableau columns; R draws the stock immediately.",
            "- Z/Enter selects a source or confirms a destination. F sends an eligible top card to its foundation.",
            "- H gives a legal-move hint. B/X/Escape/Q/Tab clears selection, then pauses the saved deal.",
        ]

    def solitaire_stats_lines(self) -> List[str]:
        self.ensure_solitaire_state()
        stats = self.state.tavern_solitaire_stats
        match = self.state.tavern_solitaire_match
        return [
            "SOLITAIRE RECORD", "",
            f"Deals started: {stats['games_started']}",
            f"Wins: {stats['wins']} | Abandoned: {stats['abandons']}",
            f"Lifetime moves: {stats['moves']}",
            f"Cards sent to foundations: {stats['cards_to_foundation']}",
            f"Stock recycles: {stats['stock_recycles']}",
            f"Best winning deal: {stats['best_moves']} moves" if stats["best_moves"] else "Best winning deal: none",
            f"Best streak: {stats['best_streak']}", "",
            f"Paused deal: {match.get('moves', 0)} moves at {match.get('venue')}." if match else "Paused deal: none.",
        ]

    @staticmethod
    def _solitaire_card_text(card: Optional[str], hidden: bool = False) -> str:
        if hidden:
            return "[hidden]"
        if not card:
            return "[empty]"
        return colorize(
            f"{solitaire_rank(card)}{card_suit_glyph(solitaire_suit(card))}",
            card_color(card),
        )

    @staticmethod
    def _solitaire_empty_slot() -> List[str]:
        width = CARD_RENDER_WIDTH
        return [
            " " * width,
            " " * width,
            "(empty)".center(width),
            " " * width,
            " " * width,
            " " * width,
            " " * width,
        ]

    @staticmethod
    def _solitaire_top_block(card: Optional[str], hidden: bool = False) -> List[str]:
        if hidden:
            return rendered_card_lines("AS", hidden=True)
        if card:
            return rendered_card_lines(card)
        return SolitaireMixin._solitaire_empty_slot()

    @staticmethod
    def _solitaire_join_columns(columns: Sequence[Sequence[str]], gap: int = 1) -> List[str]:
        height = max((len(column) for column in columns), default=0)
        spacer = " " * max(0, int(gap))
        rows: List[str] = []
        for row in range(height):
            pieces = [
                column[row] if row < len(column) else " " * (CARD_RENDER_WIDTH + 1)
                for column in columns
            ]
            rows.append(spacer.join(pieces).rstrip())
        return rows

    @staticmethod
    def _solitaire_tableau_column(
        pile: Sequence[Dict[str, object]],
        pile_index: int,
        cursor: int,
        cursor_start: int,
        selected_pile: int,
        selected_start: int,
    ) -> List[str]:
        if not pile:
            marker = ">" if cursor == 6 + pile_index else " "
            return [marker + line for line in SolitaireMixin._solitaire_empty_slot()]

        lines: List[str] = []
        last_index = len(pile) - 1
        for entry_index, entry in enumerate(pile):
            is_selected = pile_index == selected_pile and entry_index >= selected_start
            is_cursor = cursor == 6 + pile_index and entry_index == cursor_start
            marker = "*" if is_selected else ">" if is_cursor else " "
            card = str(entry["card"])
            hidden = not bool(entry.get("up"))
            if entry_index < last_index:
                lines.append(marker + card_corner_line(card, hidden=hidden))
                continue
            full_card = rendered_card_lines(card, hidden=hidden)
            for card_row, card_line in enumerate(full_card):
                lines.append((marker if card_row == 1 else " ") + card_line)
        return lines

    def _draw_solitaire_table(
        self, match: Dict[str, object], cursor: int, depth: int, selected: Optional[Dict[str, object]],
    ) -> None:
        clear_screen()
        minigame_title(
            f"{str(match.get('venue', 'Quiet Table'))} - Solitaire",
            f"Moves {match.get('moves', 0)} | Recycles {match.get('recycles', 0)} | "
            f"Foundations {sum(len(match['foundations'][suit]) for suit in SOLITAIRE_SUITS)}/52",
        )
        waste_card = str(match["waste"][-1]) if match["waste"] else None
        selected_source = selected or {}
        top_labels = ["Stock", "Waste"] + [
            f"{card_suit_glyph(suit)} Foundation" for suit in SOLITAIRE_SUITS
        ]
        top_selected = [
            selected_source.get("type") == "stock",
            selected_source.get("type") == "waste",
            *[
                selected_source.get("type") == "foundation" and selected_source.get("suit") == suit
                for suit in SOLITAIRE_SUITS
            ],
        ]
        minigame_section("Stock, waste, and foundations")
        print(" ".join(
            (
                ("*" if top_selected[index] else ">" if cursor == index else " ")
                + label.center(CARD_RENDER_WIDTH)
            )
            for index, label in enumerate(top_labels)
        ))
        top_cards: List[List[str]] = [
            self._solitaire_top_block(None, hidden=bool(match["stock"])),
            self._solitaire_top_block(waste_card),
        ]
        top_cards.extend(
            self._solitaire_top_block(
                str(match["foundations"][suit][-1]) if match["foundations"][suit] else None
            )
            for suit in SOLITAIRE_SUITS
        )
        for line in self._solitaire_join_columns(
            [[" " + card_line for card_line in card] for card in top_cards]
        ):
            print(line)
        tableau = match["tableau"]
        selected_pile = int(selected_source.get("pile", -1)) if selected_source.get("type") == "tableau" else -1
        selected_start = int(selected_source.get("start", -1))
        cursor_start = -1
        if cursor >= 6 and tableau[cursor - 6]:
            face_up = [index for index, entry in enumerate(tableau[cursor - 6]) if bool(entry.get("up"))]
            if face_up:
                cursor_start = face_up[max(0, len(face_up) - 1 - min(depth, len(face_up) - 1))]
        minigame_section("Tableau")
        print(" ".join(
            (">" if cursor == 6 + pile else " ") + f"Column {pile + 1}".center(CARD_RENDER_WIDTH)
            for pile in range(7)
        ))
        columns = [
            self._solitaire_tableau_column(
                pile,
                pile_index,
                cursor,
                cursor_start if cursor == 6 + pile_index else -1,
                selected_pile,
                selected_start,
            )
            for pile_index, pile in enumerate(tableau)
        ]
        for line in self._solitaire_join_columns(columns):
            print(line)
        if selected:
            minigame_notice(
                f"{selected.get('label', selected.get('type'))}. Choose a tableau or matching foundation.",
                prefix="SELECTED",
            )
        minigame_notice(match.get("note", ""))
        minigame_controls(
            "A/D: area",
            "1-7: jump to column",
            "W/S: sequence depth",
            "Z/Enter/Space: select/move",
            "R: draw stock",
            "F: foundation",
            "H: hint",
            "B/X/Esc/Q/Tab: clear/pause",
        )

    @staticmethod
    def _solitaire_selected_card(match: Dict[str, object], selected: Dict[str, object]) -> Optional[str]:
        source = str(selected.get("type"))
        if source == "waste" and match["waste"]:
            return str(match["waste"][-1])
        if source == "foundation":
            foundation = match["foundations"][str(selected["suit"])]
            return str(foundation[-1]) if foundation else None
        if source == "tableau":
            pile = match["tableau"][int(selected["pile"])]
            start = int(selected["start"])
            return str(pile[start]["card"]) if 0 <= start < len(pile) else None
        return None

    def _solitaire_try_foundation(self, match: Dict[str, object], selected: Dict[str, object]) -> bool:
        card = self._solitaire_selected_card(match, selected)
        if not card:
            return False
        suit = solitaire_suit(card)
        if selected["type"] == "waste":
            return solitaire_move_waste_to_foundation(match, suit)
        if selected["type"] == "tableau":
            pile = match["tableau"][int(selected["pile"])]
            if int(selected["start"]) != len(pile) - 1:
                return False
            return solitaire_move_tableau_to_foundation(match, int(selected["pile"]), suit)
        return False

    def _solitaire_try_destination(
        self, match: Dict[str, object], selected: Dict[str, object], cursor: int,
    ) -> bool:
        if cursor in range(2, 6):
            card = self._solitaire_selected_card(match, selected)
            suit = SOLITAIRE_SUITS[cursor - 2]
            return bool(card and solitaire_suit(card) == suit and self._solitaire_try_foundation(match, selected))
        if cursor not in range(6, 13):
            return False
        destination = cursor - 6
        if selected["type"] == "waste":
            return solitaire_move_waste_to_tableau(match, destination)
        if selected["type"] == "foundation":
            return solitaire_move_foundation_to_tableau(match, str(selected["suit"]), destination)
        if selected["type"] == "tableau":
            return solitaire_move_tableau_to_tableau(
                match, int(selected["pile"]), int(selected["start"]), destination,
            )
        return False

    def play_solitaire_game(self) -> None:
        self.ensure_solitaire_state()
        match = self.state.tavern_solitaire_match
        if not match:
            return
        cursor, depth, selected = 0, 0, None
        while True:
            if solitaire_won(match):
                self.finish_solitaire_game(True)
                return
            self._draw_solitaire_table(match, cursor, depth, selected)
            key = normalize_key(read_key())
            if key in {"b", "x", "\x1b", "q", "\t"}:
                if selected:
                    selected = None
                    match["note"] = "Selection cleared."
                else:
                    self.pause_solitaire_game()
                    return
                continue
            if key == "h":
                match["note"] = solitaire_hint(match)
                continue
            if key == "r":
                selected = None
                depth = 0
                cursor = 0
                action = solitaire_draw_stock(match)
                if action:
                    match["pending_minutes"] += 1
                continue
            if key in {"1", "2", "3", "4", "5", "6", "7"}:
                cursor = 5 + int(key)
                depth = 0
                continue
            if key == "f":
                if selected and self._solitaire_try_foundation(match, selected):
                    selected = None
                    match["pending_minutes"] += 1
                else:
                    match["note"] = "The selected card cannot move to a foundation."
                continue
            delta = movement_delta_for_key(key)
            if delta:
                if delta[0]:
                    cursor = (cursor + (1 if delta[0] > 0 else -1)) % 13
                    depth = 0
                elif cursor >= 6:
                    pile = match["tableau"][cursor - 6]
                    count = sum(bool(entry.get("up")) for entry in pile)
                    if count:
                        depth = max(0, min(count - 1, depth + (-1 if delta[1] > 0 else 1)))
                continue
            if key not in MENU_CONFIRM_KEYS:
                continue
            if selected:
                if self._solitaire_try_destination(match, selected, cursor):
                    selected = None
                    depth = 0
                    match["pending_minutes"] += 1
                else:
                    match["note"] = "That destination cannot accept the selected card."
                continue
            if cursor == 0:
                action = solitaire_draw_stock(match)
                if action:
                    match["pending_minutes"] += 1
                continue
            if cursor == 1 and match["waste"]:
                selected = {"type": "waste", "label": f"waste {match['waste'][-1]}"}
                continue
            if cursor in range(2, 6):
                suit = SOLITAIRE_SUITS[cursor - 2]
                if match["foundations"][suit]:
                    selected = {"type": "foundation", "suit": suit, "label": f"{suit} foundation"}
                continue
            pile_index = cursor - 6
            pile = match["tableau"][pile_index]
            face_up = [index for index, entry in enumerate(pile) if bool(entry.get("up"))]
            if face_up:
                start = face_up[max(0, len(face_up) - 1 - min(depth, len(face_up) - 1))]
                if solitaire_tableau_sequence_valid(pile[start:]):
                    selected = {
                        "type": "tableau", "pile": pile_index, "start": start,
                        "label": f"{pile[start]['card']} from column {pile_index + 1}",
                    }

    def pause_solitaire_game(self) -> None:
        match = self.state.tavern_solitaire_match
        elapsed = max(0, int(match.get("pending_minutes", 0)))
        match["pending_minutes"] = 0
        if elapsed:
            self.advance_time(elapsed)
        self.autosave_with_message("Paused Solitaire. The complete deal was saved.")

    def finish_solitaire_game(self, won: bool, abandoned: bool = False) -> None:
        match = self.state.tavern_solitaire_match
        if not self.valid_solitaire_match(match):
            return
        stats = self.state.tavern_solitaire_stats
        moves = int(match.get("moves", 0))
        stats["moves"] += moves
        stats["cards_to_foundation"] += int(match.get("foundation_moves", 0))
        stats["stock_recycles"] += int(match.get("recycles", 0))
        if won:
            stats["wins"] += 1
            stats["best_moves"] = moves if not stats["best_moves"] else min(stats["best_moves"], moves)
            stats["current_streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
        elif abandoned:
            stats["abandons"] += 1
            stats["current_streak"] = 0
        self.state.tavern_solitaire_match = {}
        self.advance_time(max(5, int(match.get("pending_minutes", 0))))
        self.autosave_with_message(
            f"Solved Solitaire in {moves} moves." if won else "Put away the unfinished Solitaire deal."
        )

    def solitaire_menu(self, venue: str = "Tavern") -> None:
        while True:
            self.ensure_solitaire_state()
            match = self.state.tavern_solitaire_match
            items = (
                [
                    MenuItem(label="Resume deal", value="resume", enabled=True, hint=f"{match.get('moves', 0)} moves"),
                    MenuItem(label="Abandon deal", value="abandon", enabled=True),
                ]
                if match else [MenuItem(label="New deal", value="new", enabled=True, hint="draw-one Klondike")]
            )
            items.extend([
                MenuItem(label="Rules", value="rules", enabled=True),
                MenuItem(label="Playing record", value="stats", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(f"{venue} - Solitaire", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "rules":
                self.vertical_panel_view("Solitaire Rules", self.solitaire_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "stats":
                self.vertical_panel_view("Solitaire Record", self.solitaire_stats_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "abandon":
                self.finish_solitaire_game(False, abandoned=True)
            else:
                if choice.value == "new":
                    self.new_solitaire_game(venue)
                self.play_solitaire_game()
