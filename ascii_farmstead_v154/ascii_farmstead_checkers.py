"""Persistent American checkers for tavern game tables."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

from ascii_farmstead_board_visuals import board_tile
from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_game_tables import (
    GAME_TABLE_BY_FURNITURE,
    GAME_TABLE_BY_GLYPH,
    GAME_TABLE_DATA,
    normalized_game_ids,
    venue_game_ids,
)
from ascii_farmstead_minigame_ui import minigame_controls, minigame_notice, minigame_section, minigame_title
from ascii_farmstead_support import C, clear_screen, colorize, movement_delta_for_key, normalize_key, read_key
from ascii_farmstead_ui import MenuItem


Board = List[List[str]]
Point = Tuple[int, int]
Move = Dict[str, object]
CHECKERS_EMPTY = "."
CHECKERS_PIECES = {"r", "R", "b", "B"}
CHECKERS_STATS_DEFAULTS = {
    "games_played": 0,
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "pieces_captured": 0,
    "kings_made": 0,
    "current_streak": 0,
    "best_streak": 0,
}


def new_checkers_board() -> Board:
    board = [[CHECKERS_EMPTY for _x in range(8)] for _y in range(8)]
    for y in range(3):
        for x in range(8):
            if (x + y) % 2 == 1:
                board[y][x] = "b"
    for y in range(5, 8):
        for x in range(8):
            if (x + y) % 2 == 1:
                board[y][x] = "r"
    return board


def copy_checkers_board(board: Board) -> Board:
    return [list(row) for row in board]


def checkers_owner(piece: str) -> str:
    if piece in {"r", "R"}:
        return "player"
    if piece in {"b", "B"}:
        return "ai"
    return ""


def checkers_directions(piece: str) -> Sequence[Tuple[int, int]]:
    if piece == "r":
        return ((-1, -1), (1, -1))
    if piece == "b":
        return ((-1, 1), (1, 1))
    return ((-1, -1), (1, -1), (-1, 1), (1, 1))


def checkers_piece_moves(board: Board, x: int, y: int, captures_only: bool = False) -> List[Move]:
    if not (0 <= x < 8 and 0 <= y < 8):
        return []
    piece = board[y][x]
    owner = checkers_owner(piece)
    if not owner:
        return []
    moves: List[Move] = []
    for dx, dy in checkers_directions(piece):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < 8 and 0 <= ny < 8):
            continue
        if board[ny][nx] == CHECKERS_EMPTY and not captures_only:
            moves.append({"from": (x, y), "to": (nx, ny), "capture": None})
            continue
        if checkers_owner(board[ny][nx]) in {"player", "ai"} - {owner}:
            jx, jy = x + dx * 2, y + dy * 2
            if 0 <= jx < 8 and 0 <= jy < 8 and board[jy][jx] == CHECKERS_EMPTY:
                moves.append({"from": (x, y), "to": (jx, jy), "capture": (nx, ny)})
    return [move for move in moves if move["capture"] is not None] if captures_only else moves


def checkers_legal_moves(board: Board, side: str, only_from: Optional[Point] = None) -> List[Move]:
    sources = [only_from] if only_from is not None else [
        (x, y)
        for y in range(8)
        for x in range(8)
        if checkers_owner(board[y][x]) == side
    ]
    captures: List[Move] = []
    ordinary: List[Move] = []
    for source in sources:
        if source is None:
            continue
        x, y = source
        if not (0 <= x < 8 and 0 <= y < 8) or checkers_owner(board[y][x]) != side:
            continue
        piece_moves = checkers_piece_moves(board, x, y)
        captures.extend(move for move in piece_moves if move["capture"] is not None)
        ordinary.extend(move for move in piece_moves if move["capture"] is None)
    return captures if captures else ([] if only_from is not None else ordinary)


def apply_checkers_move(board: Board, move: Move) -> Dict[str, object]:
    fx, fy = move["from"]
    tx, ty = move["to"]
    piece = board[fy][fx]
    if piece not in CHECKERS_PIECES or board[ty][tx] != CHECKERS_EMPTY:
        raise ValueError("Invalid checkers move.")
    board[fy][fx] = CHECKERS_EMPTY
    board[ty][tx] = piece
    captured_piece = ""
    capture = move.get("capture")
    if capture is not None:
        cx, cy = capture
        captured_piece = board[cy][cx]
        board[cy][cx] = CHECKERS_EMPTY
    promoted = False
    if piece == "r" and ty == 0:
        board[ty][tx] = "R"
        promoted = True
    elif piece == "b" and ty == 7:
        board[ty][tx] = "B"
        promoted = True
    return {
        "captured": bool(captured_piece),
        "captured_piece": captured_piece,
        "promoted": promoted,
        "to": (tx, ty),
    }


def checkers_material_score(board: Board, side: str) -> int:
    values = {"r": 100, "R": 175, "b": 100, "B": 175}
    own = sum(values.get(piece, 0) for row in board for piece in row if checkers_owner(piece) == side)
    other = sum(values.get(piece, 0) for row in board for piece in row if checkers_owner(piece) not in {"", side})
    return own - other


def checkers_move_score(board: Board, move: Move, side: str) -> int:
    simulated = copy_checkers_board(board)
    captured = move.get("capture")
    captured_piece = simulated[captured[1]][captured[0]] if captured is not None else ""
    result = apply_checkers_move(simulated, move)
    tx, ty = move["to"]
    score = 0
    if captured:
        score += 130 if captured_piece.isupper() else 90
    if result["promoted"]:
        score += 80
    score += 12 - int(abs(3.5 - tx) * 3)
    score += (7 - ty) * 2 if side == "player" else ty * 2
    enemy = "ai" if side == "player" else "player"
    enemy_captures = [candidate for candidate in checkers_legal_moves(simulated, enemy) if candidate.get("capture")]
    if any(candidate.get("capture") == (tx, ty) for candidate in enemy_captures):
        score -= 75
    score += checkers_material_score(simulated, side) // 20
    return score


def choose_checkers_ai_move(
    board: Board,
    moves: Sequence[Move],
    difficulty: str,
    rng: random.Random,
) -> Move:
    if not moves:
        raise ValueError("No legal checkers move.")
    if difficulty == "Friendly":
        return dict(rng.choice(list(moves)))
    scored = sorted(
        ((checkers_move_score(board, move, "ai"), rng.random(), move) for move in moves),
        key=lambda row: (row[0], row[1]),
        reverse=True,
    )
    if difficulty == "Practiced" and len(scored) > 1 and rng.random() < 0.35:
        return dict(rng.choice(scored[: min(3, len(scored))])[2])
    return dict(scored[0][2])


class CheckersMixin:
    """Rules, AI, persistence, and cursor UI for tavern checkers."""

    def ensure_checkers_state(self) -> None:
        stats = getattr(self.state, "tavern_checkers_stats", None)
        if not isinstance(stats, dict):
            stats = {}
        cleaned = {}
        for key, default in CHECKERS_STATS_DEFAULTS.items():
            try:
                cleaned[key] = max(0, int(stats.get(key, default) or 0))
            except (TypeError, ValueError):
                cleaned[key] = default
        self.state.tavern_checkers_stats = cleaned
        match = getattr(self.state, "tavern_checkers_match", None)
        if not self.valid_checkers_match(match):
            self.state.tavern_checkers_match = {}

    @staticmethod
    def valid_checkers_match(match: object) -> bool:
        if not isinstance(match, dict) or not match:
            return False
        board = match.get("board")
        return (
            isinstance(board, list)
            and len(board) == 8
            and all(
                isinstance(row, list)
                and len(row) == 8
                and all(str(piece) in CHECKERS_PIECES | {CHECKERS_EMPTY} for piece in row)
                for row in board
            )
            and str(match.get("turn", "")) in {"player", "ai"}
        )

    def new_checkers_match(self, difficulty: str, venue: str) -> Dict[str, object]:
        difficulty = difficulty if difficulty in {"Friendly", "Practiced", "Expert"} else "Practiced"
        match = {
            "board": new_checkers_board(),
            "turn": "player",
            "difficulty": difficulty,
            "venue": str(venue),
            "move_count": 0,
            "quiet_moves": 0,
            "pending_minutes": 0,
            "forced_piece": None,
            "player_captures": 0,
            "ai_captures": 0,
            "player_kings": 0,
            "ai_kings": 0,
            "note": "Your red pieces move toward the top of the board.",
        }
        self.state.tavern_checkers_match = match
        return match

    def checkers_match_outcome(self, match: Dict[str, object]) -> str:
        board = match["board"]
        player_pieces = sum(checkers_owner(piece) == "player" for row in board for piece in row)
        ai_pieces = sum(checkers_owner(piece) == "ai" for row in board for piece in row)
        if player_pieces == 0:
            return "loss"
        if ai_pieces == 0:
            return "win"
        if int(match.get("quiet_moves", 0) or 0) >= 80:
            return "draw"
        turn = str(match.get("turn", "player"))
        forced = match.get("forced_piece")
        only_from = tuple(forced) if isinstance(forced, (list, tuple)) and len(forced) == 2 else None
        if not checkers_legal_moves(board, turn, only_from=only_from):
            return "loss" if turn == "player" else "win"
        return ""

    def checkers_stats_lines(self) -> List[str]:
        self.ensure_checkers_state()
        stats = self.state.tavern_checkers_stats
        games = int(stats["games_played"])
        rate = (int(stats["wins"]) / games * 100.0) if games else 0.0
        match = self.state.tavern_checkers_match
        return [
            "CHECKERS RECORD",
            "",
            f"Games: {games}",
            f"Wins: {stats['wins']} | Losses: {stats['losses']} | Draws: {stats['draws']}",
            f"Win rate: {rate:.1f}%",
            f"Pieces captured: {stats['pieces_captured']}",
            f"Kings crowned: {stats['kings_made']}",
            f"Best winning streak: {stats['best_streak']}",
            "",
            (
                f"Paused match: {match.get('difficulty')} at {match.get('venue')} "
                f"after {match.get('move_count', 0)} move(s)."
                if match
                else "Paused match: none."
            ),
        ]

    @staticmethod
    def checkers_rules_lines() -> List[str]:
        return [
            "TAVERN CHECKERS",
            "",
            "- You control the red pieces and move diagonally toward the top of the board.",
            "- Ordinary pieces move one dark square forward. Kings move forward or backward.",
            "- Jump an opposing piece into an empty square to capture it.",
            "- Captures are mandatory. If another jump is available after landing, the same piece must continue.",
            "- Reaching the far edge crowns a King. Crowning ends that move, even after a jump.",
            "- Win by capturing every opposing piece or leaving the opponent without a legal move.",
            "- Eighty quiet moves without a capture or crowning produce a draw.",
            "- Move with WASD, arrows, or numpad. N jumps to the next movable piece; Z/Enter selects and moves.",
            "- The board uses white and dark-grey tiles; brackets mark the cursor, angles mark selection, and parentheses mark destinations.",
            "- X/Escape clears a selection; press it again to pause and save the match.",
            "- Friendly, Practiced, and Expert opponents use increasingly careful move selection.",
        ]

    def _checkers_piece_glyph(self, piece: str) -> str:
        glyphs = {"r": "r", "R": "R", "b": "b", "B": "B", CHECKERS_EMPTY: "."}
        return glyphs.get(piece, ".")

    def _draw_checkers_board(
        self,
        match: Dict[str, object],
        cursor: Point,
        selected: Optional[Point],
        legal_destinations: Sequence[Point],
    ) -> None:
        clear_screen()
        venue = str(match.get("venue", "Tavern"))
        minigame_title(
            f"{venue} - Checkers",
            f"Opponent: {match.get('difficulty', 'Practiced')} | "
            f"Moves: {match.get('move_count', 0)} | "
            f"Captured: {match.get('player_captures', 0)}-{match.get('ai_captures', 0)}",
        )
        minigame_section("Board", "Red: you | Pale: opponent | uppercase: King")
        print("    0  1  2  3  4  5  6  7")
        board = match["board"]
        destinations = set(legal_destinations)
        for y in range(8):
            cells: List[str] = []
            for x in range(8):
                piece = board[y][x]
                glyph = self._checkers_piece_glyph(piece)
                if (x, y) == selected:
                    cell = f"<{glyph}>"
                    role = "selected"
                elif (x, y) == cursor:
                    cell = f"[{glyph if piece != CHECKERS_EMPTY else ' '}]"
                    role = "cursor"
                elif (x, y) in destinations:
                    cell = "(.)"
                    role = "destination"
                else:
                    empty_glyph = "." if (x + y) % 2 else " "
                    cell = f" {glyph if piece != CHECKERS_EMPTY else empty_glyph} "
                    role = (
                        "red_piece" if piece in {"r", "R"}
                        else "pale_piece" if piece in {"b", "B"}
                        else "empty"
                    )
                cells.append(board_tile(cell, x, y, role))
            print(f" {y} " + "".join(cells))
        cursor_piece = board[cursor[1]][cursor[0]]
        square_detail = (
            f"Square {cursor[0]},{cursor[1]} | "
            + (f"Piece {cursor_piece}" if cursor_piece != CHECKERS_EMPTY else "Empty square")
            + f" | {len(destinations)} destination(s)"
        )
        minigame_notice(square_detail, prefix="CURSOR")
        minigame_notice(match.get("note", ""))
        minigame_controls(
            "WASD/arrows/numpad: move",
            "N: next movable piece",
            "Z/Enter/Space: select/move",
            "H: rules",
            "X/Esc/Q: clear/pause",
        )

    def _checkers_complete_turn(
        self, match: Dict[str, object], side: str, move: Move,
    ) -> bool:
        board = match["board"]
        result = apply_checkers_move(board, move)
        match["move_count"] = int(match.get("move_count", 0)) + 1
        match["pending_minutes"] = int(match.get("pending_minutes", 0)) + 1
        if result["captured"]:
            match["quiet_moves"] = 0
            key = "player_captures" if side == "player" else "ai_captures"
            match[key] = int(match.get(key, 0)) + 1
        elif result["promoted"]:
            match["quiet_moves"] = 0
        else:
            match["quiet_moves"] = int(match.get("quiet_moves", 0)) + 1
        if result["promoted"]:
            key = "player_kings" if side == "player" else "ai_kings"
            match[key] = int(match.get(key, 0)) + 1

        tx, ty = result["to"]
        extra = []
        if result["captured"] and not result["promoted"]:
            extra = checkers_legal_moves(board, side, only_from=(tx, ty))
        if extra:
            match["forced_piece"] = [tx, ty]
            match["turn"] = side
            match["note"] = "Another capture is mandatory with the same piece."
            return False
        match["forced_piece"] = None
        match["turn"] = "ai" if side == "player" else "player"
        match["note"] = "Your turn." if side == "ai" else "The opponent is considering the board."
        return True

    def _checkers_ai_turn(self, match: Dict[str, object]) -> None:
        seed = (
            int(getattr(self.state, "wilderness_seed", 0))
            + int(match.get("move_count", 0)) * 7919
            + sum(ord(ch) for ch in str(match.get("venue", "")))
        )
        rng = random.Random(seed)
        while str(match.get("turn")) == "ai" and not self.checkers_match_outcome(match):
            forced = match.get("forced_piece")
            only_from = tuple(forced) if isinstance(forced, list) and len(forced) == 2 else None
            moves = checkers_legal_moves(match["board"], "ai", only_from=only_from)
            if not moves:
                return
            move = choose_checkers_ai_move(
                match["board"], moves, str(match.get("difficulty", "Practiced")), rng,
            )
            self._checkers_complete_turn(match, "ai", move)

    def _record_checkers_outcome(self, outcome: str, match: Dict[str, object]) -> None:
        self.ensure_checkers_state()
        stats = self.state.tavern_checkers_stats
        stats["games_played"] += 1
        stats["pieces_captured"] += int(match.get("player_captures", 0))
        stats["kings_made"] += int(match.get("player_kings", 0))
        if outcome == "win":
            stats["wins"] += 1
            stats["current_streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
        elif outcome == "loss":
            stats["losses"] += 1
            stats["current_streak"] = 0
        else:
            stats["draws"] += 1

    def finish_checkers_match(self, outcome: str, resigned: bool = False) -> None:
        match = self.state.tavern_checkers_match
        if not self.valid_checkers_match(match):
            return
        self._record_checkers_outcome(outcome, match)
        minutes = max(10, int(match.get("pending_minutes", 0)) + 10)
        venue = str(match.get("venue", "the tavern"))
        self.state.tavern_checkers_match = {}
        self.advance_time(minutes)
        labels = {
            "win": "You won the checkers match.",
            "loss": "You resigned the checkers match." if resigned else "You lost the checkers match.",
            "draw": "The checkers match ended in a draw.",
        }
        self.autosave_with_message(f"{labels.get(outcome, 'The match ended')} Played at {venue}.")

    def pause_checkers_match(self) -> None:
        match = self.state.tavern_checkers_match
        elapsed = max(0, int(match.get("pending_minutes", 0)))
        match["pending_minutes"] = 0
        if elapsed:
            self.advance_time(elapsed)
        self.autosave_with_message("Paused the checkers match. It can be resumed from any tavern table.")

    def play_checkers_match(self) -> None:
        self.ensure_checkers_state()
        match = self.state.tavern_checkers_match
        if not match:
            self.set_message("There is no checkers match to play.")
            return
        cursor: Point = (0, 5)
        selected: Optional[Point] = None
        while True:
            outcome = self.checkers_match_outcome(match)
            if outcome:
                self.finish_checkers_match(outcome)
                return
            if str(match.get("turn")) == "ai":
                self._checkers_ai_turn(match)
                continue

            forced = match.get("forced_piece")
            forced_point = tuple(forced) if isinstance(forced, list) and len(forced) == 2 else None
            if forced_point:
                selected = forced_point
                cursor = forced_point
            all_moves = checkers_legal_moves(match["board"], "player", only_from=forced_point)
            source_moves = [
                move for move in all_moves
                if selected is not None and tuple(move["from"]) == selected
            ]
            destinations = [tuple(move["to"]) for move in source_moves]
            self._draw_checkers_board(match, cursor, selected, destinations)
            key = normalize_key(read_key())
            delta = movement_delta_for_key(key)
            if delta:
                cursor = (
                    max(0, min(7, cursor[0] + delta[0])),
                    max(0, min(7, cursor[1] + delta[1])),
                )
                continue
            if key == "h":
                self.vertical_panel_view(
                    "Checkers Rules", self.checkers_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
                )
                continue
            if key == "n":
                sources = sorted({tuple(move["from"]) for move in all_moves}, key=lambda point: (point[1], point[0]))
                if sources:
                    after = [point for point in sources if (point[1], point[0]) > (cursor[1], cursor[0])]
                    cursor = after[0] if after else sources[0]
                    if not forced_point:
                        selected = None
                    match["note"] = "Moved to the next piece with a legal move."
                continue
            if key in {"x", "\x1b", "q"}:
                if selected is not None and not forced_point:
                    selected = None
                    match["note"] = "Selection cleared."
                    continue
                self.pause_checkers_match()
                return
            if key not in MENU_CONFIRM_KEYS:
                continue

            if selected is None:
                available_sources = {tuple(move["from"]) for move in all_moves}
                if cursor in available_sources:
                    selected = cursor
                    match["note"] = "Choose a highlighted destination."
                else:
                    match["note"] = (
                        "A capture is mandatory; choose a piece that can jump."
                        if any(move.get("capture") for move in all_moves)
                        else "Choose one of your red pieces with a legal move."
                    )
                continue

            chosen = next((move for move in source_moves if tuple(move["to"]) == cursor), None)
            if chosen:
                self._checkers_complete_turn(match, "player", chosen)
                selected = tuple(match["forced_piece"]) if match.get("forced_piece") else None
                if selected:
                    cursor = selected
                continue
            if not forced_point and cursor in {tuple(move["from"]) for move in all_moves}:
                selected = cursor
                match["note"] = "Selected a different piece."
            else:
                match["note"] = "That is not a legal destination."

    def checkers_menu(self, venue: str = "Tavern") -> None:
        while True:
            self.ensure_checkers_state()
            match = self.state.tavern_checkers_match
            items: List[MenuItem] = []
            if match:
                items.extend([
                    MenuItem(
                        label="Resume paused match",
                        value="resume",
                        enabled=True,
                        hint=f"{match.get('difficulty')} | {match.get('move_count', 0)} moves",
                    ),
                    MenuItem(label="Resign paused match", value="resign", enabled=True, hint="records a loss"),
                ])
            else:
                for difficulty, hint in (
                    ("Friendly", "casual opponent"),
                    ("Practiced", "balanced opponent"),
                    ("Expert", "careful opponent"),
                ):
                    items.append(MenuItem(
                        label=f"New match: {difficulty}",
                        value=f"new:{difficulty}",
                        enabled=True,
                        hint=hint,
                    ))
            items.extend([
                MenuItem(label="Rules", value="rules", enabled=True),
                MenuItem(label="Playing record", value="stats", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(
                f"{venue} - Checkers", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                self.set_message("Left the checkers table.")
                return
            if choice.value == "rules":
                self.vertical_panel_view(
                    "Checkers Rules", self.checkers_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "stats":
                self.vertical_panel_view(
                    "Checkers Record", self.checkers_stats_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "resign":
                self.finish_checkers_match("loss", resigned=True)
                continue
            if str(choice.value).startswith("new:"):
                self.new_checkers_match(str(choice.value).split(":", 1)[1], venue)
            self.play_checkers_match()

    def tavern_card_games_menu(self, venue: str = "Tavern") -> None:
        while True:
            items = [
                MenuItem(
                    label="Play blackjack",
                    value="blackjack",
                    enabled=int(getattr(self.state, "money", 0)) >= 10,
                    hint="10-1,000g wagers",
                ),
                MenuItem(
                    label="Play Texas Hold'em",
                    value="holdem",
                    enabled=hasattr(self, "holdem_menu") and int(getattr(self.state, "money", 0)) >= 20,
                    hint="four seats | table-stakes buy-ins",
                ),
                MenuItem(
                    label="Play Hearts",
                    value="hearts",
                    enabled=hasattr(self, "hearts_menu"),
                    hint=(
                        "resume saved match"
                        if getattr(self.state, "tavern_hearts_match", {})
                        else "four-player trick-taking"
                    ),
                ),
                MenuItem(
                    label="Play Solitaire",
                    value="solitaire",
                    enabled=hasattr(self, "solitaire_menu"),
                    hint=(
                        "resume saved deal"
                        if getattr(self.state, "tavern_solitaire_match", {})
                        else "draw-one Klondike"
                    ),
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                f"{venue} - Card Games", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "blackjack":
                self.blackjack_table_menu(venue)
            elif choice.value == "holdem":
                self.holdem_menu(venue)
            elif choice.value == "hearts":
                self.hearts_menu(venue)
            elif choice.value == "solitaire":
                self.solitaire_menu(venue)

    def tavern_board_games_menu(self, venue: str = "Tavern") -> None:
        while True:
            self.ensure_checkers_state()
            match = self.state.tavern_checkers_match
            items = [
                MenuItem(
                    label="Play checkers",
                    value="checkers",
                    enabled=True,
                    hint=f"resume {match.get('difficulty')} match" if match else "free board game",
                ),
                MenuItem(
                    label="Play chess",
                    value="chess",
                    enabled=hasattr(self, "chess_menu"),
                    hint=(
                        f"resume {(getattr(self.state, 'tavern_chess_match', {}) or {}).get('difficulty')} match"
                        if getattr(self.state, "tavern_chess_match", {})
                        else "free strategy game"
                    ),
                ),
                MenuItem(
                    label="Play mancala",
                    value="mancala",
                    enabled=hasattr(self, "mancala_menu"),
                    hint=(
                        f"resume {(getattr(self.state, 'tavern_mancala_match', {}) or {}).get('difficulty')} match"
                        if getattr(self.state, "tavern_mancala_match", {})
                        else "free play or wagers"
                    ),
                ),
                MenuItem(
                    label="Play Royal Game of Ur",
                    value="ur",
                    enabled=hasattr(self, "ur_menu"),
                    hint=(
                        "resume saved game"
                        if getattr(self.state, "tavern_ur_match", {})
                        else "ancient race | free or wagers"
                    ),
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                f"{venue} - Board Games", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "checkers":
                self.checkers_menu(venue)
            elif choice.value == "chess":
                self.chess_menu(venue)
            elif choice.value == "mancala":
                self.mancala_menu(venue)
            elif choice.value == "ur":
                self.ur_menu(venue)

    def tavern_games_menu(self, venue: str = "Tavern") -> None:
        venue_kind = (
            "maes_inn"
            if str(venue) == "Mae's Inn"
            else "caravanserai"
            if "caravan" in str(venue).lower()
            else "wayhouse"
            if "wayhouse" in str(venue).lower()
            else "inn"
        )
        self.distributed_game_tables_menu(
            venue,
            venue_game_ids(venue, venue_kind, count=3),
        )

    def game_table_fixture_id(self, glyph: object) -> str:
        return str(GAME_TABLE_BY_GLYPH.get(str(glyph), ""))

    def game_table_furniture_id(self, furniture_name: object) -> str:
        return str(GAME_TABLE_BY_FURNITURE.get(str(furniture_name), ""))

    def discover_game_tables(self, game_ids: Sequence[str]) -> int:
        discoveries = getattr(self.state, "tavern_game_discoveries", None)
        if not isinstance(discoveries, list):
            discoveries = []
            self.state.tavern_game_discoveries = discoveries
        before = len(discoveries)
        for game_id in normalized_game_ids(game_ids):
            if game_id not in discoveries:
                discoveries.append(game_id)
        discoveries[:] = normalized_game_ids(discoveries)
        return len(discoveries) - before

    def open_physical_game_table(
        self,
        game_id: str,
        venue: str = "Game Table",
    ) -> bool:
        game_id = str(game_id)
        self.discover_game_tables((game_id,))
        methods = {
            "blackjack": "blackjack_table_menu",
            "holdem": "holdem_menu",
            "hearts": "hearts_menu",
            "solitaire": "solitaire_menu",
            "checkers": "checkers_menu",
            "chess": "chess_menu",
            "mancala": "mancala_menu",
            "ur": "ur_menu",
        }
        method_name = methods.get(game_id, "")
        method = getattr(self, method_name, None)
        if not callable(method):
            self.set_message("That game table is not available right now.")
            return False
        method(str(venue))
        return True

    def use_game_table_furniture(
        self,
        furniture_name: str,
        venue: str = "Home Game Room",
    ) -> bool:
        game_id = self.game_table_furniture_id(furniture_name)
        if not game_id:
            return False
        return self.open_physical_game_table(game_id, venue)

    def distributed_game_tables_menu(
        self,
        venue: str,
        game_ids: Sequence[str],
    ) -> None:
        available = normalized_game_ids(game_ids)
        self.discover_game_tables(available)
        while True:
            items = []
            for game_id in available:
                table = GAME_TABLE_DATA[game_id]
                category = str(table["category"])
                hint = "card table" if category == "card" else "board table"
                if game_id in {"blackjack", "holdem", "mancala", "ur"}:
                    hint += " | wagers available"
                items.append(
                    MenuItem(
                        label=f"Play {str(table['name']).replace(' Table', '').replace(' Board', '')}",
                        value=game_id,
                        enabled=True,
                        hint=hint,
                    )
                )
            items.extend([
                MenuItem(
                    label="Playing records",
                    value="records",
                    enabled=True,
                    hint=f"{len(getattr(self.state, 'tavern_game_discoveries', []) or [])}/8 games discovered",
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(
                f"{venue} - Available Games",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "records":
                self.vertical_panel_view(
                    "Tavern Game Records", self.tavern_game_record_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
                )
            else:
                self.open_physical_game_table(str(choice.value), venue)

    def tavern_game_record_lines(self) -> List[str]:
        lines = [
            *self.blackjack_stats_lines(),
            "",
            "-" * 18,
            "",
            *self.checkers_stats_lines(),
        ]
        if hasattr(self, "chess_stats_lines"):
            lines.extend(["", "-" * 18, "", *self.chess_stats_lines()])
        if hasattr(self, "mancala_stats_lines"):
            lines.extend(["", "-" * 18, "", *self.mancala_stats_lines()])
        for method_name in (
            "holdem_stats_lines", "hearts_stats_lines", "solitaire_stats_lines", "ur_stats_lines",
        ):
            if hasattr(self, method_name):
                lines.extend(["", "-" * 18, "", *getattr(self, method_name)()])
        return lines
