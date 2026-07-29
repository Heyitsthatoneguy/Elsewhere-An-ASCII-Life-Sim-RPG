from __future__ import annotations

"""Physical access data and deterministic distribution for card and board games."""

import hashlib
import random
from typing import Dict, Iterable, Tuple


GAME_TABLE_DATA: Dict[str, Dict[str, object]] = {
    "blackjack": {
        "name": "Blackjack Table",
        "glyph": "1",
        "category": "card",
        "price": 850,
        "description": "A felt-topped blackjack table with a countable single-deck shoe.",
    },
    "holdem": {
        "name": "Hold'em Table",
        "glyph": "2",
        "category": "card",
        "price": 1100,
        "description": "A broad poker table arranged for four-seat Texas Hold'em.",
    },
    "hearts": {
        "name": "Hearts Table",
        "glyph": "3",
        "category": "card",
        "price": 720,
        "description": "A compact card table prepared for a four-player game of Hearts.",
    },
    "solitaire": {
        "name": "Solitaire Table",
        "glyph": "4",
        "category": "card",
        "price": 540,
        "description": "A quiet card table with enough room for a full Klondike layout.",
    },
    "checkers": {
        "name": "Checkers Table",
        "glyph": "5",
        "category": "board",
        "price": 620,
        "description": "A sturdy table with a permanent checkered board and carved pieces.",
    },
    "chess": {
        "name": "Chess Table",
        "glyph": "6",
        "category": "board",
        "price": 900,
        "description": "A weighted chess set built into a dark-and-light playing table.",
    },
    "mancala": {
        "name": "Mancala Board",
        "glyph": "7",
        "category": "board",
        "price": 680,
        "description": "A long carved mancala board with smooth counting stones.",
    },
    "ur": {
        "name": "Royal Game of Ur Board",
        "glyph": "8",
        "category": "board",
        "price": 1250,
        "description": "A decorated race board modeled after the ancient Royal Game of Ur.",
    },
}

GAME_TABLE_BY_FURNITURE = {
    str(data["name"]): game_id for game_id, data in GAME_TABLE_DATA.items()
}
GAME_TABLE_BY_GLYPH = {
    str(data["glyph"]): game_id for game_id, data in GAME_TABLE_DATA.items()
}
CARD_GAME_IDS = tuple(
    game_id
    for game_id, data in GAME_TABLE_DATA.items()
    if data["category"] == "card"
)
BOARD_GAME_IDS = tuple(
    game_id
    for game_id, data in GAME_TABLE_DATA.items()
    if data["category"] == "board"
)


def stable_game_seed(key: object) -> int:
    digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def normalized_game_ids(game_ids: Iterable[object]) -> Tuple[str, ...]:
    seen = set()
    result = []
    for raw_game_id in game_ids:
        game_id = str(raw_game_id)
        if game_id in GAME_TABLE_DATA and game_id not in seen:
            seen.add(game_id)
            result.append(game_id)
    return tuple(result)


def venue_game_ids(
    venue_key: object,
    venue_kind: str = "inn",
    count: int = 3,
) -> Tuple[str, ...]:
    """Return a stable, varied collection with both cards and boards when possible."""
    kind = str(venue_kind or "inn").lower()
    if kind == "maes_inn":
        return ("blackjack", "hearts", "checkers")
    if kind in {"caravanserai", "desert_caravanserai"}:
        return ("holdem", "mancala", "ur")
    if kind in {"tundra_wayhouse", "wayhouse"}:
        return ("hearts", "chess")
    count = max(1, min(len(GAME_TABLE_DATA), int(count)))
    rng = random.Random(stable_game_seed(f"{kind}:{venue_key}"))
    cards = list(CARD_GAME_IDS)
    boards = list(BOARD_GAME_IDS)
    rng.shuffle(cards)
    rng.shuffle(boards)
    selected = []
    if count >= 2:
        selected.extend((cards.pop(), boards.pop()))
    else:
        selected.append((cards + boards)[rng.randrange(len(cards) + len(boards))])
    remaining = cards + boards
    rng.shuffle(remaining)
    selected.extend(remaining[: max(0, count - len(selected))])
    return normalized_game_ids(selected)


def rotating_game_furniture(rotation_key: object, count: int = 2) -> Tuple[str, ...]:
    rng = random.Random(stable_game_seed(f"furniture-stock:{rotation_key}"))
    names = list(GAME_TABLE_BY_FURNITURE)
    rng.shuffle(names)
    return tuple(names[: max(0, min(len(names), int(count)))])


def rare_recovered_game_table(loot_key: object, chance: float) -> str:
    rng = random.Random(stable_game_seed(f"recovered-table:{loot_key}"))
    if rng.random() >= max(0.0, min(1.0, float(chance))):
        return ""
    names = list(GAME_TABLE_BY_FURNITURE)
    return names[rng.randrange(len(names))]
