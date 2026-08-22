"""Persistent wagered Kalah-style mancala for tavern game tables."""

from __future__ import annotations

import random
import textwrap
from typing import Dict, List, Optional, Sequence, Tuple

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_minigame_ui import minigame_controls, minigame_notice, minigame_section, minigame_title
from ascii_farmstead_support import C, clear_screen, colorize, movement_delta_for_key, normalize_key, read_key
from ascii_farmstead_ui import MenuItem


Board = List[int]
MoveResult = Dict[str, object]
MANCALA_TOTAL_STONES = 48
MANCALA_MIN_WAGER = 10
MANCALA_MAX_WAGER = 1000
MANCALA_PAYOUT_RATIOS = {
    "Friendly": (1, 1),
    "Practiced": (3, 2),
    "Expert": (2, 1),
}
MANCALA_STATS_DEFAULTS = {
    "games_played": 0,
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "stones_captured": 0,
    "extra_turns": 0,
    "total_wagered": 0,
    "net_winnings": 0,
    "biggest_win": 0,
    "biggest_loss": 0,
    "current_streak": 0,
    "best_streak": 0,
}


def new_mancala_board(stones_per_pit: int = 4) -> Board:
    stones = max(1, int(stones_per_pit))
    return [stones] * 6 + [0] + [stones] * 6 + [0]


def mancala_side_pits(side: str) -> range:
    return range(0, 6) if side == "player" else range(7, 13)


def mancala_store(side: str) -> int:
    return 6 if side == "player" else 13


def mancala_opponent(side: str) -> str:
    return "ai" if side == "player" else "player"


def mancala_legal_pits(board: Board, side: str) -> List[int]:
    return [pit for pit in mancala_side_pits(side) if int(board[pit]) > 0]


def mancala_sow_path(board: Board, side: str, pit: int) -> List[int]:
    if pit not in mancala_side_pits(side) or int(board[pit]) <= 0:
        return []
    path: List[int] = []
    cursor = int(pit)
    opponent_store = mancala_store(mancala_opponent(side))
    stones = int(board[pit])
    while len(path) < stones:
        cursor = (cursor + 1) % 14
        if cursor == opponent_store:
            continue
        path.append(cursor)
    return path


def mancala_game_over(board: Board) -> bool:
    return not any(int(board[pit]) for pit in range(0, 6)) or not any(
        int(board[pit]) for pit in range(7, 13)
    )


def mancala_final_scores(board: Board) -> Tuple[int, int]:
    player = int(board[6]) + sum(int(board[pit]) for pit in range(0, 6))
    ai = int(board[13]) + sum(int(board[pit]) for pit in range(7, 13))
    return player, ai


def mancala_board_outcome(board: Board) -> str:
    if not mancala_game_over(board):
        return ""
    player, ai = mancala_final_scores(board)
    if player > ai:
        return "win"
    if ai > player:
        return "loss"
    return "draw"


def _mancala_sweep(board: Board) -> None:
    if not mancala_game_over(board):
        return
    for side in ("player", "ai"):
        store = mancala_store(side)
        for pit in mancala_side_pits(side):
            board[store] += int(board[pit])
            board[pit] = 0


def apply_mancala_move(board: Board, side: str, pit: int) -> MoveResult:
    if len(board) != 14 or pit not in mancala_side_pits(side) or int(board[pit]) <= 0:
        raise ValueError("Invalid mancala move.")
    path = mancala_sow_path(board, side, pit)
    stones = int(board[pit])
    board[pit] = 0
    for target in path:
        board[target] += 1
    landing = path[-1]
    captured = 0
    own_pits = mancala_side_pits(side)
    if landing in own_pits and int(board[landing]) == 1:
        opposite = 12 - landing
        if int(board[opposite]) > 0:
            captured = int(board[opposite]) + 1
            board[mancala_store(side)] += captured
            board[landing] = 0
            board[opposite] = 0
    game_over = mancala_game_over(board)
    if game_over:
        _mancala_sweep(board)
    extra_turn = landing == mancala_store(side) and not game_over
    return {
        "side": side,
        "pit": int(pit),
        "stones": stones,
        "path": path,
        "landing": landing,
        "captured": captured,
        "extra_turn": extra_turn,
        "game_over": game_over,
    }


def mancala_evaluate(board: Board) -> int:
    outcome = mancala_board_outcome(board)
    if outcome == "loss":
        return 100000
    if outcome == "win":
        return -100000
    if outcome == "draw":
        return 0
    ai_store = int(board[13])
    player_store = int(board[6])
    ai_pits = sum(int(board[pit]) for pit in range(7, 13))
    player_pits = sum(int(board[pit]) for pit in range(0, 6))
    return (ai_store - player_store) * 18 + (ai_pits - player_pits)


def _mancala_minimax(
    board: Board,
    turn: str,
    depth: int,
    alpha: int,
    beta: int,
) -> int:
    if depth <= 0 or mancala_game_over(board):
        return mancala_evaluate(board)
    pits = mancala_legal_pits(board, turn)
    if not pits:
        return mancala_evaluate(board)
    maximizing = turn == "ai"
    best = -10**9 if maximizing else 10**9
    for pit in pits:
        simulated = list(board)
        result = apply_mancala_move(simulated, turn, pit)
        next_turn = turn if result["extra_turn"] else mancala_opponent(turn)
        score = _mancala_minimax(simulated, next_turn, depth - 1, alpha, beta)
        if maximizing:
            best = max(best, score)
            alpha = max(alpha, best)
        else:
            best = min(best, score)
            beta = min(beta, best)
        if beta <= alpha:
            break
    return best


def choose_mancala_ai_pit(
    board: Board,
    difficulty: str,
    rng: random.Random,
) -> int:
    legal = mancala_legal_pits(board, "ai")
    if not legal:
        raise ValueError("No legal mancala move.")
    previews: List[Tuple[int, MoveResult, Board]] = []
    for pit in legal:
        simulated = list(board)
        result = apply_mancala_move(simulated, "ai", pit)
        previews.append((pit, result, simulated))
    if difficulty == "Friendly":
        pool: List[int] = []
        for pit, result, _simulated in previews:
            pool.append(pit)
            if result["captured"]:
                pool.append(pit)
            if result["extra_turn"]:
                pool.append(pit)
        return int(rng.choice(pool))
    scored: List[Tuple[int, float, int]] = []
    for pit, result, simulated in previews:
        if difficulty == "Expert":
            next_turn = "ai" if result["extra_turn"] else "player"
            score = _mancala_minimax(simulated, next_turn, 4, -10**9, 10**9)
        else:
            score = mancala_evaluate(simulated)
            score += int(result["captured"]) * 8
            score += 30 if result["extra_turn"] else 0
        scored.append((score, rng.random(), pit))
    scored.sort(reverse=True)
    if difficulty == "Practiced" and len(scored) > 1 and rng.random() < 0.2:
        return int(rng.choice(scored[: min(3, len(scored))])[2])
    return int(scored[0][2])


def mancala_profit_for_win(wager: int, difficulty: str) -> int:
    wager = max(0, int(wager))
    numerator, denominator = MANCALA_PAYOUT_RATIOS.get(difficulty, (1, 1))
    return wager * numerator // denominator


class MancalaMixin:
    """Rules, AI, wagers, persistence, and cursor UI for tavern mancala."""

    def ensure_mancala_state(self) -> None:
        stats = getattr(self.state, "tavern_mancala_stats", None)
        if not isinstance(stats, dict):
            stats = {}
        cleaned: Dict[str, int] = {}
        for key, default in MANCALA_STATS_DEFAULTS.items():
            try:
                value = int(stats.get(key, default) or 0)
            except (TypeError, ValueError):
                value = default
            cleaned[key] = value if key == "net_winnings" else max(0, value)
        self.state.tavern_mancala_stats = cleaned
        if not self.valid_mancala_match(getattr(self.state, "tavern_mancala_match", None)):
            self.state.tavern_mancala_match = {}

    @staticmethod
    def valid_mancala_match(match: object) -> bool:
        if not isinstance(match, dict) or not match:
            return False
        board = match.get("board")
        if not (
            isinstance(board, list)
            and len(board) == 14
            and all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in board)
            and sum(board) == MANCALA_TOTAL_STONES
        ):
            return False
        try:
            wager = int(match.get("wager", 0) or 0)
        except (TypeError, ValueError):
            return False
        return (
            str(match.get("turn", "")) in {"player", "ai"}
            and str(match.get("difficulty", "")) in MANCALA_PAYOUT_RATIOS
            and 0 <= wager <= MANCALA_MAX_WAGER
        )

    def new_mancala_match(
        self,
        difficulty: str,
        venue: str,
        wager: int = 0,
    ) -> Dict[str, object]:
        self.ensure_mancala_state()
        if self.state.tavern_mancala_match:
            self.set_message("Finish or resign the paused mancala match first.")
            return {}
        difficulty = difficulty if difficulty in MANCALA_PAYOUT_RATIOS else "Practiced"
        wager = max(0, int(wager))
        if wager and not MANCALA_MIN_WAGER <= wager <= MANCALA_MAX_WAGER:
            self.set_message("Mancala wagers must be between 10g and 1,000g.")
            return {}
        if int(self.state.money) < wager:
            self.set_message(f"You need {wager}g to place that wager.")
            return {}
        self.state.money -= wager
        match = {
            "board": new_mancala_board(),
            "turn": "player",
            "difficulty": difficulty,
            "venue": str(venue),
            "wager": wager,
            "move_count": 0,
            "pending_minutes": 0,
            "player_captured": 0,
            "ai_captured": 0,
            "player_extra_turns": 0,
            "ai_extra_turns": 0,
            "history": [],
            "last_path": [],
            "last_landing": None,
            "note": "Choose one of your six lower pits. The highlighted cups show its sowing path.",
        }
        self.state.tavern_mancala_match = match
        return match

    def mancala_stats_lines(self) -> List[str]:
        self.ensure_mancala_state()
        stats = self.state.tavern_mancala_stats
        games = int(stats["games_played"])
        rate = (int(stats["wins"]) / games * 100.0) if games else 0.0
        match = self.state.tavern_mancala_match
        return [
            "MANCALA RECORD",
            "",
            f"Games: {games}",
            f"Wins: {stats['wins']} | Losses: {stats['losses']} | Draws: {stats['draws']}",
            f"Win rate: {rate:.1f}%",
            f"Stones captured: {stats['stones_captured']}",
            f"Extra turns earned: {stats['extra_turns']}",
            f"Gold wagered: {stats['total_wagered']}g",
            f"Net winnings: {int(stats['net_winnings']):+d}g",
            f"Biggest win: +{stats['biggest_win']}g",
            f"Biggest loss: -{stats['biggest_loss']}g",
            f"Best winning streak: {stats['best_streak']}",
            "",
            (
                f"Paused match: {match.get('difficulty')} at {match.get('venue')} "
                f"for {match.get('wager', 0)}g."
                if match else "Paused match: none."
            ),
        ]

    @staticmethod
    def mancala_rules_lines() -> List[str]:
        return [
            "TAVERN MANCALA (KALAH)",
            "",
            "- You control the six lower pits. Each game begins with four stones in every small pit.",
            "- Choose a pit to sow all of its stones counterclockwise, one stone into each following cup.",
            "- Your sowing skips the opponent's store. The opponent similarly skips your store.",
            "- If your last stone lands in your store, you immediately take another turn.",
            "- If your last stone lands in an empty pit on your side, capture it and every stone opposite it.",
            "- When either side empties all six pits, the other side moves its remaining stones into its store.",
            "- The player with the most stones in their store wins. Equal stores produce a draw.",
            "- Move with A/D, arrows, or numpad; number keys 1-6 jump directly to a nonempty pit.",
            "- Z/Enter/Space sows the highlighted pit.",
            "- Highlighted cups preview the sowing path; the final landing cup is shown separately.",
            "- B/X/Escape/Q/Tab pauses the match. A wager remains committed while that match is paused.",
            "- Draws refund the wager. Wins earn profit equal to 1x the wager on Friendly, 1.5x on Practiced, or 2x on Expert.",
            "- Free practice matches are always available and count toward playing records.",
        ]

    @staticmethod
    def _mancala_pit_name(index: int) -> str:
        if index == 6:
            return "your store"
        if index == 13:
            return "opponent store"
        if 0 <= index <= 5:
            return f"your pit {index + 1}"
        return f"opponent pit {13 - index}"

    def _mancala_cell(
        self,
        board: Board,
        index: int,
        cursor: Optional[int],
        preview: Sequence[int],
        landing: Optional[int],
    ) -> str:
        value = int(board[index])
        if index == cursor:
            text = f"< {value:02d} >"
        elif index == landing:
            text = f"{{ {value:02d} }}"
        elif index in preview:
            text = f"( {value:02d} )"
        else:
            text = f"[ {value:02d} ]"
        if index in range(0, 7):
            return colorize(text, C.LIT)
        return colorize(text, C.ROOF_RED)

    @staticmethod
    def _mancala_stones(value: int) -> str:
        value = max(0, int(value))
        if value <= 4:
            return ("●" * value).center(6)
        return f"●x{value:02d}".center(6)

    def _draw_mancala_board(
        self,
        match: Dict[str, object],
        cursor: int,
        preview: Sequence[int],
    ) -> None:
        clear_screen()
        board = match["board"]
        landing = preview[-1] if preview else None
        wager = int(match.get("wager", 0))
        profit = mancala_profit_for_win(wager, str(match.get("difficulty", "Practiced")))
        minigame_title(
            f"{str(match.get('venue', 'Tavern'))} - Mancala",
            f"Opponent: {match.get('difficulty')} | Gold: {int(self.state.money)}g | "
            + (f"Wager: {wager}g | Win profit: +{profit}g" if wager else "Free practice"),
        )
        minigame_section("Board", "< > selected | ( ) path | { } landing")
        top_pits = list(range(12, 6, -1))
        player_pits = list(range(0, 6))
        indent = "          "
        print(indent + " ".join(f"{number:^6}" for number in range(6, 0, -1)))
        print(indent + " ".join(self._mancala_cell(board, pit, None, preview, landing) for pit in top_pits))
        print(indent + " ".join(colorize(self._mancala_stones(board[pit]), C.ROOF_RED) for pit in top_pits))
        print(
            "  AI " + self._mancala_cell(board, 13, None, preview, landing)
            + " " * 31
            + self._mancala_cell(board, 6, None, preview, landing) + " YOU"
        )
        print(indent + " ".join(colorize(self._mancala_stones(board[pit]), C.LIT) for pit in player_pits))
        print(indent + " ".join(self._mancala_cell(board, pit, cursor, preview, landing) for pit in player_pits))
        print(indent + " ".join(f"{number:^6}" for number in range(1, 7)))
        if preview:
            route = " -> ".join(self._mancala_pit_name(index) for index in preview)
            minigame_notice(
                f"{board[cursor]} stones from pit {cursor + 1}; landing in {self._mancala_pit_name(landing)}.",
                prefix="PREVIEW",
            )
            for line in textwrap.wrap(
                f"Route: {route}",
                width=100,
                subsequent_indent="  ",
            ):
                print(line)
        minigame_notice(match.get("note", ""))
        history = " | ".join(str(value) for value in match.get("history", [])[-3:]) or "No moves yet."
        minigame_notice(history, prefix="RECENT")
        minigame_controls(
            "A/D or arrows/numpad: choose pit",
            "1-6: jump to pit",
            "Z/Enter/Space: sow",
            "H: rules",
            "B/X/Esc/Q/Tab: pause",
        )

    def _mancala_complete_move(
        self,
        match: Dict[str, object],
        side: str,
        pit: int,
    ) -> MoveResult:
        result = apply_mancala_move(match["board"], side, pit)
        match["move_count"] = int(match.get("move_count", 0)) + 1
        match["pending_minutes"] = int(match.get("pending_minutes", 0)) + 1
        match["last_path"] = list(result["path"])
        match["last_landing"] = int(result["landing"])
        captured = int(result["captured"])
        if captured:
            key = "player_captured" if side == "player" else "ai_captured"
            match[key] = int(match.get(key, 0)) + captured
        if result["extra_turn"]:
            key = "player_extra_turns" if side == "player" else "ai_extra_turns"
            match[key] = int(match.get(key, 0)) + 1
        actor = "You" if side == "player" else "Opponent"
        detail = f"{actor} sowed pit {pit + 1 if side == 'player' else 13 - pit}"
        if captured:
            detail += f" and captured {captured}"
        if result["extra_turn"]:
            detail += " for an extra turn"
        match.setdefault("history", []).append(detail + ".")
        match["history"] = match["history"][-20:]
        if result["game_over"]:
            match["note"] = "The final stones have been swept into the stores."
        elif result["extra_turn"]:
            match["turn"] = side
            match["note"] = "You earned another turn." if side == "player" else "The opponent earned another turn."
        else:
            match["turn"] = mancala_opponent(side)
            match["note"] = "Your turn." if side == "ai" else "The opponent is considering the pits."
        return result

    def _mancala_ai_turn(self, match: Dict[str, object]) -> None:
        rng = random.Random(
            int(getattr(self.state, "wilderness_seed", 0))
            + int(match.get("move_count", 0)) * 65537
            + sum(ord(ch) for ch in str(match.get("venue", "")))
        )
        while str(match.get("turn")) == "ai" and not mancala_board_outcome(match["board"]):
            pit = choose_mancala_ai_pit(
                match["board"], str(match.get("difficulty", "Practiced")), rng,
            )
            self._mancala_complete_move(match, "ai", pit)

    def _record_mancala_outcome(
        self,
        outcome: str,
        match: Dict[str, object],
        profit: int,
    ) -> None:
        self.ensure_mancala_state()
        stats = self.state.tavern_mancala_stats
        wager = int(match.get("wager", 0))
        stats["games_played"] += 1
        stats["stones_captured"] += int(match.get("player_captured", 0))
        stats["extra_turns"] += int(match.get("player_extra_turns", 0))
        stats["total_wagered"] += wager
        stats["net_winnings"] += int(profit)
        if outcome == "win":
            stats["wins"] += 1
            stats["current_streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
            stats["biggest_win"] = max(stats["biggest_win"], int(profit))
        elif outcome == "loss":
            stats["losses"] += 1
            stats["current_streak"] = 0
            stats["biggest_loss"] = max(stats["biggest_loss"], max(0, -int(profit)))
        else:
            stats["draws"] += 1

    def finish_mancala_match(self, outcome: str, resigned: bool = False) -> None:
        match = self.state.tavern_mancala_match
        if not self.valid_mancala_match(match):
            return
        wager = int(match.get("wager", 0))
        if outcome == "win":
            profit = mancala_profit_for_win(wager, str(match.get("difficulty", "Practiced")))
            payout = wager + profit
        elif outcome == "draw":
            profit = 0
            payout = wager
        else:
            profit = -wager
            payout = 0
        self.state.money += payout
        self._record_mancala_outcome(outcome, match, profit)
        minutes = max(10, int(match.get("pending_minutes", 0)) + 8)
        venue = str(match.get("venue", "the tavern"))
        self.state.tavern_mancala_match = {}
        self.advance_time(minutes)
        if outcome == "win":
            result = f"You won the mancala match and earned {profit}g."
        elif outcome == "loss":
            result = "You resigned and forfeited the mancala wager." if resigned and wager else (
                "You resigned the mancala match." if resigned else "You lost the mancala match."
            )
        else:
            result = f"The mancala match was a draw; your {wager}g wager was returned." if wager else "The mancala match was a draw."
        self.autosave_with_message(f"{result} Played at {venue}.")

    def pause_mancala_match(self) -> None:
        match = self.state.tavern_mancala_match
        elapsed = max(0, int(match.get("pending_minutes", 0)))
        match["pending_minutes"] = 0
        if elapsed:
            self.advance_time(elapsed)
        self.autosave_with_message("Paused the mancala match. Its wager and board remain at the tavern tables.")

    def play_mancala_match(self) -> None:
        self.ensure_mancala_state()
        match = self.state.tavern_mancala_match
        if not match:
            self.set_message("There is no mancala match to play.")
            return
        cursor = 0
        while True:
            outcome = mancala_board_outcome(match["board"])
            if outcome:
                self.finish_mancala_match(outcome)
                return
            if str(match.get("turn")) == "ai":
                self._mancala_ai_turn(match)
                continue
            legal = mancala_legal_pits(match["board"], "player")
            if cursor not in legal:
                cursor = legal[0]
            preview = mancala_sow_path(match["board"], "player", cursor)
            self._draw_mancala_board(match, cursor, preview)
            key = normalize_key(read_key())
            if key == "h":
                self.vertical_panel_view(
                    "Mancala Rules", self.mancala_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
                )
                continue
            if key in {"b", "x", "\x1b", "q", "\t"}:
                self.pause_mancala_match()
                return
            delta = movement_delta_for_key(key)
            if delta and delta[0]:
                position = legal.index(cursor)
                cursor = legal[(position + (1 if delta[0] > 0 else -1)) % len(legal)]
                continue
            if key in {"1", "2", "3", "4", "5", "6"}:
                requested = int(key) - 1
                if requested in legal:
                    cursor = requested
                else:
                    match["note"] = f"Pit {key} is empty and cannot be sown."
                continue
            if key in MENU_CONFIRM_KEYS:
                self._mancala_complete_move(match, "player", cursor)

    def mancala_wager_menu(self, venue: str, difficulty: str) -> Optional[int]:
        numerator, denominator = MANCALA_PAYOUT_RATIOS[difficulty]
        multiplier = f"{numerator / denominator:g}x profit"
        presets = (10, 25, 50, 100, 250, 500, 1000)
        while True:
            items = [
                MenuItem(label="Free practice", value="0", enabled=True, hint="records count | no payout"),
            ]
            items.extend(
                MenuItem(
                    label=f"Wager {amount}g",
                    value=str(amount),
                    enabled=int(self.state.money) >= amount,
                    hint=f"win +{mancala_profit_for_win(amount, difficulty)}g",
                )
                for amount in presets
            )
            items.extend([
                MenuItem(
                    label="Choose stone wager",
                    value="custom",
                    enabled=int(self.state.money) >= MANCALA_MIN_WAGER,
                    hint=f"10g increments | {multiplier}",
                ),
                MenuItem(label="Rules and payouts", value="rules", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(
                f"{venue} - {difficulty} Mancala",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return None
            if choice.value == "rules":
                self.vertical_panel_view(
                    "Mancala Rules", self.mancala_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "custom":
                max_chips = min(MANCALA_MAX_WAGER // 10, int(self.state.money) // 10)
                quantity = self.vertical_quantity_select(
                    "Choose Mancala Wager",
                    "10g stone",
                    10,
                    max_qty=max_chips,
                    start_qty=min(5, max_chips),
                    panel_width=LEFT_PANEL_WIDTH,
                    panel_height=LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if quantity in {None, MENU_BACK} or int(quantity) <= 0:
                    continue
                return int(quantity) * 10
            return int(choice.value)

    def mancala_menu(self, venue: str = "Tavern") -> None:
        while True:
            self.ensure_mancala_state()
            match = self.state.tavern_mancala_match
            items: List[MenuItem] = []
            if match:
                items.extend([
                    MenuItem(
                        label="Resume paused match",
                        value="resume",
                        enabled=True,
                        hint=f"{match.get('difficulty')} | {match.get('wager', 0)}g committed",
                    ),
                    MenuItem(
                        label="Resign paused match",
                        value="resign",
                        enabled=True,
                        hint="forfeits the wager",
                    ),
                ])
            else:
                for difficulty, hint in (
                    ("Friendly", "win profit: 1x wager"),
                    ("Practiced", "win profit: 1.5x wager"),
                    ("Expert", "win profit: 2x wager"),
                ):
                    items.append(
                        MenuItem(
                            label=f"New match: {difficulty}",
                            value=f"new:{difficulty}",
                            enabled=True,
                            hint=hint,
                        )
                    )
            items.extend([
                MenuItem(label="Rules and payouts", value="rules", enabled=True),
                MenuItem(label="Playing record", value="stats", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(
                f"{venue} - Mancala", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                self.set_message("Left the mancala table.")
                return
            if choice.value == "rules":
                self.vertical_panel_view(
                    "Mancala Rules", self.mancala_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "stats":
                self.vertical_panel_view(
                    "Mancala Record", self.mancala_stats_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "resign":
                self.finish_mancala_match("loss", resigned=True)
                continue
            if choice.value == "resume":
                self.play_mancala_match()
                continue
            difficulty = str(choice.value).split(":", 1)[1]
            wager = self.mancala_wager_menu(venue, difficulty)
            if wager is None:
                continue
            new_match = self.new_mancala_match(difficulty, venue, wager)
            if not new_match:
                continue
            self.autosave_with_message(
                f"Started {difficulty} mancala at {venue}"
                + (f" with a {wager}g wager." if wager else " as free practice.")
            )
            self.play_mancala_match()
