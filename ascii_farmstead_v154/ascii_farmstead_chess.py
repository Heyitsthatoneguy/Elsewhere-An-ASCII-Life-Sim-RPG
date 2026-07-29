"""Persistent tavern chess with complete legal move handling."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

from ascii_farmstead_board_visuals import board_tile
from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_minigame_ui import minigame_controls, minigame_notice, minigame_section, minigame_title
from ascii_farmstead_support import C, clear_screen, colorize, movement_delta_for_key, normalize_key, read_key
from ascii_farmstead_ui import MenuItem


Board = List[List[str]]
Point = Tuple[int, int]
Move = Dict[str, object]
CHESS_EMPTY = "."
CHESS_PIECES = set("PNBRQKpnbrqk")
CHESS_VALUES = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}
CHESS_STATS_DEFAULTS = {
    "games_played": 0,
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "checkmates": 0,
    "pieces_captured": 0,
    "promotions": 0,
    "current_streak": 0,
    "best_streak": 0,
}


def new_chess_board() -> Board:
    return [
        list("rnbqkbnr"),
        list("pppppppp"),
        [CHESS_EMPTY] * 8,
        [CHESS_EMPTY] * 8,
        [CHESS_EMPTY] * 8,
        [CHESS_EMPTY] * 8,
        list("PPPPPPPP"),
        list("RNBQKBNR"),
    ]


def copy_chess_board(board: Board) -> Board:
    return [list(row) for row in board]


def chess_owner(piece: str) -> str:
    if piece in "PNBRQK":
        return "player"
    if piece in "pnbrqk":
        return "ai"
    return ""


def chess_opponent(side: str) -> str:
    return "ai" if side == "player" else "player"


def chess_position_key(match: Dict[str, object]) -> str:
    board_text = "/".join("".join(row) for row in match["board"])
    ep = match.get("en_passant")
    ep_text = f"{ep[0]},{ep[1]}" if isinstance(ep, (list, tuple)) and len(ep) == 2 else "-"
    return f"{board_text}|{match.get('turn', 'player')}|{match.get('castling', '')}|{ep_text}"


def chess_square_attacked(board: Board, x: int, y: int, by_side: str) -> bool:
    pawn = "P" if by_side == "player" else "p"
    pawn_source_dy = 1 if by_side == "player" else -1
    for dx in (-1, 1):
        sx, sy = x + dx, y + pawn_source_dy
        if 0 <= sx < 8 and 0 <= sy < 8 and board[sy][sx] == pawn:
            return True
    knight = "N" if by_side == "player" else "n"
    for dx, dy in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
        sx, sy = x + dx, y + dy
        if 0 <= sx < 8 and 0 <= sy < 8 and board[sy][sx] == knight:
            return True
    king = "K" if by_side == "player" else "k"
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == dy == 0:
                continue
            sx, sy = x + dx, y + dy
            if 0 <= sx < 8 and 0 <= sy < 8 and board[sy][sx] == king:
                return True
    rookers = {"R", "Q"} if by_side == "player" else {"r", "q"}
    bishops = {"B", "Q"} if by_side == "player" else {"b", "q"}
    for dx, dy, attackers in (
        (1, 0, rookers), (-1, 0, rookers), (0, 1, rookers), (0, -1, rookers),
        (1, 1, bishops), (1, -1, bishops), (-1, 1, bishops), (-1, -1, bishops),
    ):
        sx, sy = x + dx, y + dy
        while 0 <= sx < 8 and 0 <= sy < 8:
            piece = board[sy][sx]
            if piece != CHESS_EMPTY:
                if piece in attackers:
                    return True
                break
            sx += dx
            sy += dy
    return False


def chess_king_point(board: Board, side: str) -> Optional[Point]:
    king = "K" if side == "player" else "k"
    for y, row in enumerate(board):
        for x, piece in enumerate(row):
            if piece == king:
                return x, y
    return None


def chess_in_check(board: Board, side: str) -> bool:
    point = chess_king_point(board, side)
    return point is None or chess_square_attacked(board, point[0], point[1], chess_opponent(side))


def _chess_add_pawn_move(moves: List[Move], source: Point, target: Point, capture: Optional[Point] = None) -> None:
    _tx, ty = target
    if ty in {0, 7}:
        for promotion in ("Q", "R", "B", "N"):
            moves.append({"from": source, "to": target, "capture": capture, "promotion": promotion})
    else:
        moves.append({"from": source, "to": target, "capture": capture})


def chess_pseudo_moves(match: Dict[str, object], x: int, y: int) -> List[Move]:
    board = match["board"]
    if not (0 <= x < 8 and 0 <= y < 8):
        return []
    piece = board[y][x]
    side = chess_owner(piece)
    if not side:
        return []
    enemy = chess_opponent(side)
    moves: List[Move] = []
    upper = piece.upper()
    if upper == "P":
        dy = -1 if side == "player" else 1
        start_y = 6 if side == "player" else 1
        ny = y + dy
        if 0 <= ny < 8 and board[ny][x] == CHESS_EMPTY:
            _chess_add_pawn_move(moves, (x, y), (x, ny))
            ny2 = y + dy * 2
            if y == start_y and board[ny2][x] == CHESS_EMPTY:
                moves.append({"from": (x, y), "to": (x, ny2), "capture": None, "double_pawn": True})
        ep = match.get("en_passant")
        ep_point = tuple(ep) if isinstance(ep, (list, tuple)) and len(ep) == 2 else None
        for dx in (-1, 1):
            tx, ty = x + dx, y + dy
            if not (0 <= tx < 8 and 0 <= ty < 8):
                continue
            if chess_owner(board[ty][tx]) == enemy:
                _chess_add_pawn_move(moves, (x, y), (tx, ty), (tx, ty))
            elif ep_point == (tx, ty):
                capture_point = (tx, y)
                if board[y][tx].upper() == "P" and chess_owner(board[y][tx]) == enemy:
                    moves.append({
                        "from": (x, y), "to": (tx, ty), "capture": capture_point, "en_passant": True,
                    })
    elif upper == "N":
        for dx, dy in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
            tx, ty = x + dx, y + dy
            if 0 <= tx < 8 and 0 <= ty < 8 and chess_owner(board[ty][tx]) != side:
                moves.append({
                    "from": (x, y), "to": (tx, ty),
                    "capture": (tx, ty) if chess_owner(board[ty][tx]) == enemy else None,
                })
    elif upper in {"B", "R", "Q"}:
        directions = []
        if upper in {"B", "Q"}:
            directions.extend(((1, 1), (1, -1), (-1, 1), (-1, -1)))
        if upper in {"R", "Q"}:
            directions.extend(((1, 0), (-1, 0), (0, 1), (0, -1)))
        for dx, dy in directions:
            tx, ty = x + dx, y + dy
            while 0 <= tx < 8 and 0 <= ty < 8:
                target_owner = chess_owner(board[ty][tx])
                if target_owner == side:
                    break
                moves.append({
                    "from": (x, y), "to": (tx, ty),
                    "capture": (tx, ty) if target_owner == enemy else None,
                })
                if target_owner == enemy:
                    break
                tx += dx
                ty += dy
    elif upper == "K":
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                tx, ty = x + dx, y + dy
                if 0 <= tx < 8 and 0 <= ty < 8 and chess_owner(board[ty][tx]) != side:
                    moves.append({
                        "from": (x, y), "to": (tx, ty),
                        "capture": (tx, ty) if chess_owner(board[ty][tx]) == enemy else None,
                    })
        rights = str(match.get("castling", ""))
        home_y = 7 if side == "player" else 0
        king_right = "K" if side == "player" else "k"
        queen_right = "Q" if side == "player" else "q"
        rook = "R" if side == "player" else "r"
        if (x, y) == (4, home_y) and not chess_in_check(board, side):
            if (
                king_right in rights and board[home_y][7] == rook
                and board[home_y][5] == board[home_y][6] == CHESS_EMPTY
                and not chess_square_attacked(board, 5, home_y, enemy)
                and not chess_square_attacked(board, 6, home_y, enemy)
            ):
                moves.append({"from": (x, y), "to": (6, home_y), "capture": None, "castle": "king"})
            if (
                queen_right in rights and board[home_y][0] == rook
                and board[home_y][1] == board[home_y][2] == board[home_y][3] == CHESS_EMPTY
                and not chess_square_attacked(board, 3, home_y, enemy)
                and not chess_square_attacked(board, 2, home_y, enemy)
            ):
                moves.append({"from": (x, y), "to": (2, home_y), "capture": None, "castle": "queen"})
    return moves


def clone_chess_match(match: Dict[str, object]) -> Dict[str, object]:
    clone = dict(match)
    clone["board"] = copy_chess_board(match["board"])
    clone["move_history"] = list(match.get("move_history", []))
    clone["position_counts"] = dict(match.get("position_counts", {}))
    clone["captured"] = list(match.get("captured", []))
    ep = match.get("en_passant")
    clone["en_passant"] = list(ep) if isinstance(ep, (list, tuple)) else None
    return clone


def chess_move_notation(move: Move, piece: str, captured: str = "") -> str:
    if move.get("castle") == "king":
        return "O-O"
    if move.get("castle") == "queen":
        return "O-O-O"
    fx, fy = move["from"]
    tx, ty = move["to"]
    source = f"{chr(97 + fx)}{8 - fy}"
    target = f"{chr(97 + tx)}{8 - ty}"
    marker = "x" if captured else "-"
    promotion = f"={str(move.get('promotion', '')).upper()}" if move.get("promotion") else ""
    return f"{piece.upper() if piece.upper() != 'P' else ''}{source}{marker}{target}{promotion}"


def apply_chess_move(match: Dict[str, object], move: Move, record: bool = True) -> Dict[str, object]:
    board = match["board"]
    fx, fy = move["from"]
    tx, ty = move["to"]
    piece = board[fy][fx]
    side = chess_owner(piece)
    if not side or board[ty][tx] != CHESS_EMPTY and chess_owner(board[ty][tx]) == side:
        raise ValueError("Invalid chess move.")
    capture = move.get("capture")
    captured_piece = ""
    if capture is not None:
        cx, cy = capture
        captured_piece = board[cy][cx]
        board[cy][cx] = CHESS_EMPTY
    board[fy][fx] = CHESS_EMPTY
    board[ty][tx] = piece
    if move.get("castle"):
        if move["castle"] == "king":
            board[ty][5], board[ty][7] = board[ty][7], CHESS_EMPTY
        else:
            board[ty][3], board[ty][0] = board[ty][0], CHESS_EMPTY
    promoted = False
    if move.get("promotion"):
        promoted_piece = str(move["promotion"]).upper()
        board[ty][tx] = promoted_piece if side == "player" else promoted_piece.lower()
        promoted = True

    rights = str(match.get("castling", ""))
    if piece == "K":
        rights = rights.replace("K", "").replace("Q", "")
    elif piece == "k":
        rights = rights.replace("k", "").replace("q", "")
    rook_rights = {
        (0, 7): "Q", (7, 7): "K", (0, 0): "q", (7, 0): "k",
    }
    if piece.upper() == "R" and (fx, fy) in rook_rights:
        rights = rights.replace(rook_rights[(fx, fy)], "")
    if captured_piece.upper() == "R" and capture in rook_rights:
        rights = rights.replace(rook_rights[capture], "")
    match["castling"] = rights
    match["en_passant"] = [fx, (fy + ty) // 2] if piece.upper() == "P" and abs(ty - fy) == 2 else None
    match["halfmove_clock"] = 0 if piece.upper() == "P" or captured_piece else int(match.get("halfmove_clock", 0)) + 1
    if side == "ai":
        match["fullmove_number"] = int(match.get("fullmove_number", 1)) + 1
    match["turn"] = chess_opponent(side)
    if record:
        if captured_piece:
            match.setdefault("captured", []).append(captured_piece)
        match.setdefault("move_history", []).append(chess_move_notation(move, piece, captured_piece))
        match["move_history"] = match["move_history"][-120:]
        key = chess_position_key(match)
        counts = match.setdefault("position_counts", {})
        counts[key] = int(counts.get(key, 0)) + 1
    return {"captured_piece": captured_piece, "promoted": promoted, "side": side}


def chess_legal_moves(match: Dict[str, object], side: str, only_from: Optional[Point] = None) -> List[Move]:
    board = match["board"]
    sources = [only_from] if only_from else [
        (x, y) for y in range(8) for x in range(8) if chess_owner(board[y][x]) == side
    ]
    legal: List[Move] = []
    for source in sources:
        if source is None:
            continue
        for move in chess_pseudo_moves(match, source[0], source[1]):
            simulated = clone_chess_match(match)
            apply_chess_move(simulated, move, record=False)
            if not chess_in_check(simulated["board"], side):
                legal.append(move)
    return legal


def chess_insufficient_material(board: Board) -> bool:
    pieces = [(piece, x, y) for y, row in enumerate(board) for x, piece in enumerate(row) if piece != CHESS_EMPTY and piece.upper() != "K"]
    if not pieces:
        return True
    if len(pieces) == 1 and pieces[0][0].upper() in {"B", "N"}:
        return True
    if pieces and all(piece.upper() == "B" for piece, _x, _y in pieces):
        colors = {(x + y) % 2 for _piece, x, y in pieces}
        return len(colors) == 1
    return False


def chess_match_outcome(match: Dict[str, object]) -> str:
    board = match["board"]
    turn = str(match.get("turn", "player"))
    if chess_king_point(board, "player") is None:
        return "loss"
    if chess_king_point(board, "ai") is None:
        return "win"
    if int(match.get("halfmove_clock", 0)) >= 100:
        return "draw_fifty"
    if int((match.get("position_counts", {}) or {}).get(chess_position_key(match), 0)) >= 3:
        return "draw_repetition"
    if chess_insufficient_material(board):
        return "draw_material"
    moves = chess_legal_moves(match, turn)
    if moves:
        return ""
    if chess_in_check(board, turn):
        return "loss_checkmate" if turn == "player" else "win_checkmate"
    return "draw_stalemate"


def chess_evaluate(board: Board, side: str) -> int:
    total = 0
    for y, row in enumerate(board):
        for x, piece in enumerate(row):
            owner = chess_owner(piece)
            if not owner:
                continue
            value = CHESS_VALUES[piece.upper()]
            center = max(0, 6 - int(abs(3.5 - x) + abs(3.5 - y)))
            total += (value + center) * (1 if owner == side else -1)
    return total


def choose_chess_ai_move(match: Dict[str, object], difficulty: str, rng: random.Random) -> Move:
    moves = chess_legal_moves(match, "ai")
    if not moves:
        raise ValueError("No legal chess move.")
    if difficulty == "Friendly":
        captures = [move for move in moves if move.get("capture")]
        pool = captures + list(moves) if captures else list(moves)
        return dict(rng.choice(pool))
    scored: List[Tuple[int, float, Move]] = []
    for move in moves:
        simulated = clone_chess_match(match)
        apply_chess_move(simulated, move)
        outcome = chess_match_outcome(simulated)
        if outcome == "win_checkmate":
            score = 1_000_000
        else:
            score = chess_evaluate(simulated["board"], "ai")
            if chess_in_check(simulated["board"], "player"):
                score += 35
            if difficulty == "Expert":
                replies = chess_legal_moves(simulated, "player")
                if replies:
                    reply_scores = []
                    for reply in replies:
                        answered = clone_chess_match(simulated)
                        apply_chess_move(answered, reply)
                        reply_scores.append(chess_evaluate(answered["board"], "ai"))
                    score = min(reply_scores)
        scored.append((score, rng.random(), move))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    if difficulty == "Practiced" and len(scored) > 1 and rng.random() < 0.25:
        return dict(rng.choice(scored[: min(3, len(scored))])[2])
    return dict(scored[0][2])


class ChessMixin:
    """Tavern-facing chess state, AI, rendering, and menus."""

    def ensure_chess_state(self) -> None:
        stats = getattr(self.state, "tavern_chess_stats", None)
        if not isinstance(stats, dict):
            stats = {}
        cleaned = {}
        for key, default in CHESS_STATS_DEFAULTS.items():
            try:
                cleaned[key] = max(0, int(stats.get(key, default) or 0))
            except (TypeError, ValueError):
                cleaned[key] = default
        self.state.tavern_chess_stats = cleaned
        if not self.valid_chess_match(getattr(self.state, "tavern_chess_match", None)):
            self.state.tavern_chess_match = {}

    @staticmethod
    def valid_chess_match(match: object) -> bool:
        if not isinstance(match, dict) or not match:
            return False
        board = match.get("board")
        return (
            isinstance(board, list) and len(board) == 8
            and all(isinstance(row, list) and len(row) == 8 and all(str(piece) in CHESS_PIECES | {CHESS_EMPTY} for piece in row) for row in board)
            and str(match.get("turn", "")) in {"player", "ai"}
            and chess_king_point(board, "player") is not None
            and chess_king_point(board, "ai") is not None
        )

    def new_chess_match(self, difficulty: str, venue: str) -> Dict[str, object]:
        difficulty = difficulty if difficulty in {"Friendly", "Practiced", "Expert"} else "Practiced"
        match = {
            "board": new_chess_board(), "turn": "player", "difficulty": difficulty,
            "venue": str(venue), "castling": "KQkq", "en_passant": None,
            "halfmove_clock": 0, "fullmove_number": 1, "move_history": [],
            "position_counts": {}, "captured": [], "pending_minutes": 0,
            "player_captures": 0, "ai_captures": 0, "player_promotions": 0,
            "note": "You are White. Select a piece, then a highlighted destination.",
        }
        match["position_counts"][chess_position_key(match)] = 1
        self.state.tavern_chess_match = match
        return match

    def chess_stats_lines(self) -> List[str]:
        self.ensure_chess_state()
        stats = self.state.tavern_chess_stats
        games = int(stats["games_played"])
        match = self.state.tavern_chess_match
        return [
            "CHESS RECORD", "",
            f"Games: {games}",
            f"Wins: {stats['wins']} | Losses: {stats['losses']} | Draws: {stats['draws']}",
            f"Checkmates delivered: {stats['checkmates']}",
            f"Pieces captured: {stats['pieces_captured']}",
            f"Pawns promoted: {stats['promotions']}",
            f"Best winning streak: {stats['best_streak']}",
            "",
            (
                f"Paused match: {match.get('difficulty')} at {match.get('venue')} "
                f"on move {match.get('fullmove_number', 1)}."
                if match else "Paused match: none."
            ),
        ]

    @staticmethod
    def chess_rules_lines() -> List[str]:
        return [
            "TAVERN CHESS", "",
            "- You play White and move first. Uppercase pieces are yours; lowercase pieces belong to the opponent.",
            "- Pawns move forward, capture diagonally, may advance two squares initially, and promote on the far rank.",
            "- Knights jump in an L shape. Bishops move diagonally; Rooks move straight; Queens use both.",
            "- Kings move one square and may castle if the path, check status, and castling rights permit it.",
            "- En passant is available immediately after an opposing pawn advances two squares past your pawn.",
            "- A move is illegal if it leaves your King in check.",
            "- Checkmate wins. Stalemate, threefold repetition, insufficient material, and fifty moves per side without pawn movement or capture draw.",
            "- White and dark-grey tiles form the board; brackets mark the cursor, angles mark selection, and parentheses mark destinations.",
            "- Move with WASD, arrows, or numpad. N jumps to the next movable piece; Z/Enter selects and moves.",
            "- X/Escape clears selection, then pauses.",
            "- Friendly, Practiced, and Expert opponents use bounded increasingly careful evaluation.",
        ]

    def _draw_chess_board(self, match: Dict[str, object], cursor: Point, selected: Optional[Point], destinations: Sequence[Point]) -> None:
        clear_screen()
        status = "CHECK" if chess_in_check(match["board"], "player") else "Your turn"
        minigame_title(
            f"{str(match.get('venue', 'Tavern'))} - Chess",
            f"Opponent: {match.get('difficulty')} | Move: {match.get('fullmove_number')} | {status}",
        )
        minigame_section("Board", "Uppercase: you | lowercase: opponent")
        print("    a  b  c  d  e  f  g  h")
        destination_set = set(destinations)
        for y, row in enumerate(match["board"]):
            cells = []
            for x, piece in enumerate(row):
                if (x, y) == selected:
                    cell = f"<{piece}>"
                    role = "selected"
                elif (x, y) == cursor:
                    cell = f"[{piece if piece != CHESS_EMPTY else ' '}]"
                    role = "cursor"
                elif (x, y) in destination_set:
                    cell = f"({piece if piece != CHESS_EMPTY else '.'})"
                    role = "destination"
                else:
                    cell = f" {piece if piece != CHESS_EMPTY else ('.' if (x + y) % 2 else ' ')} "
                    role = (
                        "pale_piece" if chess_owner(piece) == "player"
                        else "red_piece" if chess_owner(piece) == "ai"
                        else "empty"
                    )
                cells.append(board_tile(cell, x, y, role))
            print(f" {8-y} " + "".join(cells))
        captured = "".join(str(piece) for piece in match.get("captured", [])[-16:]) or "none"
        history = " ".join(str(move) for move in match.get("move_history", [])[-6:]) or "none"
        piece = match["board"][cursor[1]][cursor[0]]
        square_name = f"{chr(ord('a') + cursor[0])}{8 - cursor[1]}"
        minigame_notice(
            f"{square_name} | {piece if piece != CHESS_EMPTY else 'empty'} | "
            f"{len(destinations)} destination(s)",
            prefix="CURSOR",
        )
        minigame_notice(match.get("note", ""))
        print(f"Captured: {captured} | Recent: {history}")
        minigame_controls(
            "WASD/arrows/numpad: move",
            "N: next movable piece",
            "Z/Enter/Space: select/move",
            "H: rules",
            "X/Esc/Q: clear/pause",
        )

    def _choose_chess_promotion(self, moves: Sequence[Move]) -> Move:
        if len(moves) == 1:
            return dict(moves[0])
        names = {"Q": "Queen", "R": "Rook", "B": "Bishop", "N": "Knight"}
        items = [
            MenuItem(label=f"Promote to {names[str(move['promotion'])]}", value=str(move["promotion"]), enabled=True)
            for move in moves
        ]
        choice = self.vertical_panel_select(
            "Pawn Promotion", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=False,
        )
        selected = str(choice.value) if choice else "Q"
        return dict(next((move for move in moves if move.get("promotion") == selected), moves[0]))

    def _apply_live_chess_move(self, match: Dict[str, object], move: Move) -> None:
        side = str(match.get("turn", "player"))
        result = apply_chess_move(match, move)
        if result["captured_piece"]:
            key = "player_captures" if side == "player" else "ai_captures"
            match[key] = int(match.get(key, 0)) + 1
        if result["promoted"] and side == "player":
            match["player_promotions"] = int(match.get("player_promotions", 0)) + 1
        match["pending_minutes"] = int(match.get("pending_minutes", 0)) + 1
        next_side = str(match.get("turn"))
        match["note"] = (
            "Check." if chess_in_check(match["board"], next_side)
            else "Your turn." if next_side == "player"
            else "The opponent is considering the position."
        )

    def _chess_ai_turn(self, match: Dict[str, object]) -> None:
        rng = random.Random(
            int(getattr(self.state, "wilderness_seed", 0))
            + int(match.get("fullmove_number", 1)) * 104729
            + sum(ord(ch) for ch in str(match.get("venue", "")))
        )
        move = choose_chess_ai_move(match, str(match.get("difficulty", "Practiced")), rng)
        self._apply_live_chess_move(match, move)

    def _record_chess_outcome(self, outcome: str, match: Dict[str, object]) -> None:
        self.ensure_chess_state()
        stats = self.state.tavern_chess_stats
        stats["games_played"] += 1
        stats["pieces_captured"] += int(match.get("player_captures", 0))
        stats["promotions"] += int(match.get("player_promotions", 0))
        if outcome.startswith("win"):
            stats["wins"] += 1
            stats["current_streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
            if outcome == "win_checkmate":
                stats["checkmates"] += 1
        elif outcome.startswith("loss"):
            stats["losses"] += 1
            stats["current_streak"] = 0
        else:
            stats["draws"] += 1

    def finish_chess_match(self, outcome: str, resigned: bool = False) -> None:
        match = self.state.tavern_chess_match
        if not self.valid_chess_match(match):
            return
        self._record_chess_outcome(outcome, match)
        minutes = max(15, int(match.get("pending_minutes", 0)) + 12)
        venue = str(match.get("venue", "the tavern"))
        self.state.tavern_chess_match = {}
        self.advance_time(minutes)
        if outcome.startswith("win"):
            result = "You won the chess match."
        elif outcome.startswith("loss"):
            result = "You resigned the chess match." if resigned else "You lost the chess match."
        else:
            result = "The chess match ended in a draw."
        self.autosave_with_message(f"{result} Played at {venue}.")

    def pause_chess_match(self) -> None:
        match = self.state.tavern_chess_match
        elapsed = max(0, int(match.get("pending_minutes", 0)))
        match["pending_minutes"] = 0
        if elapsed:
            self.advance_time(elapsed)
        self.autosave_with_message("Paused the chess match. It can be resumed from any tavern.")

    def play_chess_match(self) -> None:
        self.ensure_chess_state()
        match = self.state.tavern_chess_match
        if not match:
            self.set_message("There is no chess match to play.")
            return
        cursor: Point = (4, 6)
        selected: Optional[Point] = None
        while True:
            outcome = chess_match_outcome(match)
            if outcome:
                self.finish_chess_match(outcome)
                return
            if str(match.get("turn")) == "ai":
                self._chess_ai_turn(match)
                continue
            all_moves = chess_legal_moves(match, "player")
            source_moves = [move for move in all_moves if selected is not None and tuple(move["from"]) == selected]
            destinations = [tuple(move["to"]) for move in source_moves]
            self._draw_chess_board(match, cursor, selected, destinations)
            key = normalize_key(read_key())
            delta = movement_delta_for_key(key)
            if delta:
                cursor = (max(0, min(7, cursor[0] + delta[0])), max(0, min(7, cursor[1] + delta[1])))
                continue
            if key == "h":
                self.vertical_panel_view("Chess Rules", self.chess_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if key == "n":
                sources = sorted({tuple(move["from"]) for move in all_moves}, key=lambda point: (point[1], point[0]))
                if sources:
                    after = [point for point in sources if (point[1], point[0]) > (cursor[1], cursor[0])]
                    cursor = after[0] if after else sources[0]
                    selected = None
                    match["note"] = "Moved to the next piece with a legal move."
                continue
            if key in {"x", "\x1b", "q"}:
                if selected is not None:
                    selected = None
                    match["note"] = "Selection cleared."
                    continue
                self.pause_chess_match()
                return
            if key not in MENU_CONFIRM_KEYS:
                continue
            if selected is None:
                sources = {tuple(move["from"]) for move in all_moves}
                if cursor in sources:
                    selected = cursor
                    match["note"] = "Choose a highlighted destination."
                else:
                    match["note"] = "Choose one of your White pieces with a legal move."
                continue
            candidates = [move for move in source_moves if tuple(move["to"]) == cursor]
            if candidates:
                self._apply_live_chess_move(match, self._choose_chess_promotion(candidates))
                selected = None
            elif cursor in {tuple(move["from"]) for move in all_moves}:
                selected = cursor
                match["note"] = "Selected a different piece."
            else:
                match["note"] = "That is not a legal destination."

    def chess_menu(self, venue: str = "Tavern") -> None:
        while True:
            self.ensure_chess_state()
            match = self.state.tavern_chess_match
            items: List[MenuItem] = []
            if match:
                items.extend([
                    MenuItem(label="Resume paused match", value="resume", enabled=True, hint=f"{match.get('difficulty')} | move {match.get('fullmove_number')}"),
                    MenuItem(label="Resign paused match", value="resign", enabled=True, hint="records a loss"),
                ])
            else:
                for difficulty, hint in (
                    ("Friendly", "casual opponent"), ("Practiced", "balanced opponent"), ("Expert", "two-ply tactical opponent"),
                ):
                    items.append(MenuItem(label=f"New match: {difficulty}", value=f"new:{difficulty}", enabled=True, hint=hint))
            items.extend([
                MenuItem(label="Rules", value="rules", enabled=True),
                MenuItem(label="Playing record", value="stats", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(f"{venue} - Chess", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                self.set_message("Left the chess table.")
                return
            if choice.value == "rules":
                self.vertical_panel_view("Chess Rules", self.chess_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "stats":
                self.vertical_panel_view("Chess Record", self.chess_stats_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "resign":
                self.finish_chess_match("loss", resigned=True)
                continue
            if str(choice.value).startswith("new:"):
                self.new_chess_match(str(choice.value).split(":", 1)[1], venue)
            self.play_chess_match()
