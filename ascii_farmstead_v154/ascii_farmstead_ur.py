"""Persistent Royal Game of Ur with tetrahedral dice, captures, AI, and wagers."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_minigame_ui import (
    minigame_controls,
    minigame_notice,
    minigame_section,
    minigame_title,
)
from ascii_farmstead_support import C, clear_screen, colorize, normalize_key, read_key
from ascii_farmstead_ui import MenuItem


UR_HOME = -1
UR_FINISHED = 14
UR_SHARED = set(range(4, 12))
UR_ROSETTES = {3, 7, 13}
UR_SAFE_ROSETTE = 7
UR_PAYOUT_RATIOS = {"Friendly": (1, 1), "Practiced": (3, 2), "Expert": (2, 1)}
UR_PRIVATE_ENTRY_COLUMNS = {0: 3, 1: 2, 2: 1, 3: 0}
UR_PRIVATE_EXIT_COLUMNS = {12: 7, 13: 6}
UR_SHARED_COLUMNS = {position: position - 4 for position in range(4, 12)}
UR_STATS_DEFAULTS = {
    "games_played": 0, "wins": 0, "losses": 0, "captures": 0,
    "rosettes": 0, "pieces_finished": 0, "rolls": 0, "total_wagered": 0,
    "net_winnings": 0, "biggest_win": 0, "biggest_loss": 0,
    "current_streak": 0, "best_streak": 0,
}


def roll_ur_dice(rng: random.Random) -> List[int]:
    return [rng.randint(0, 1) for _ in range(4)]


def ur_roll_total(dice: Sequence[int]) -> int:
    return sum(1 if int(value) else 0 for value in dice)


def ur_opponent(side: str) -> str:
    return "ai" if side == "player" else "player"


def ur_target(position: int, roll: int) -> int:
    return roll - 1 if position == UR_HOME else position + roll


def ur_board_coordinate(side: str, position: int) -> Optional[tuple[int, int]]:
    """Map a route position to the historical three-row Ur board."""
    position = int(position)
    if position in UR_SHARED_COLUMNS:
        return UR_SHARED_COLUMNS[position], 1
    row = 2 if side == "player" else 0
    if position in UR_PRIVATE_ENTRY_COLUMNS:
        return UR_PRIVATE_ENTRY_COLUMNS[position], row
    if position in UR_PRIVATE_EXIT_COLUMNS:
        return UR_PRIVATE_EXIT_COLUMNS[position], row
    return None


def _ur_glyph_for_coordinate(
    match: Dict[str, object],
    x: int,
    y: int,
    legal_targets: set[int],
    selected_target: Optional[int],
) -> str:
    positions = match["positions"]
    route_position: Optional[int] = None
    route_side: Optional[str] = None
    if y == 1:
        route_position = 4 + x
    elif x <= 3:
        route_position = 3 - x
        route_side = "ai" if y == 0 else "player"
    elif x >= 6:
        route_position = 19 - x
        route_side = "ai" if y == 0 else "player"
    if route_position is None:
        return " "

    player_here = (
        route_position in positions["player"]
        and (route_side in {None, "player"})
    )
    ai_here = (
        route_position in positions["ai"]
        and (route_side in {None, "ai"})
    )
    legal_here = route_position in legal_targets and route_side in {None, "player"}
    if legal_here and ai_here and route_position in UR_SHARED:
        glyph, shade = "×", C.ROOF_RED
    elif legal_here and route_position not in UR_ROSETTES:
        glyph, shade = "·", C.LANDMARK_ACTIVE
    elif player_here:
        glyph, shade = "@", C.LIT
    elif ai_here:
        glyph, shade = "o", C.ROOF_RED
    elif route_position in UR_ROSETTES:
        glyph, shade = "✦", C.UI_SELECTED if legal_here else C.SERVICE
    else:
        glyph, shade = " ", C.UI_MUTED
    if legal_here and route_position == selected_target:
        shade = C.UI_SELECTED
    return colorize(glyph, shade)


def render_ur_board_lines(
    match: Dict[str, object],
    legal: Sequence[int],
    selected: int,
) -> List[str]:
    roll = int(match.get("roll", 0) or 0)
    player_positions = match["positions"]["player"]
    legal_targets = {
        ur_target(int(player_positions[piece]), roll)
        for piece in legal
    }
    selected_target = (
        ur_target(int(player_positions[legal[selected]]), roll)
        if legal and 0 <= selected < len(legal)
        else None
    )
    cells: Dict[tuple[int, int], str] = {}
    for y in range(3):
        for x in range(8):
            if y != 1 and x in {4, 5}:
                continue
            cells[(x, y)] = _ur_glyph_for_coordinate(
                match, x, y, legal_targets, selected_target,
            )

    def row_cells(y: int, columns: Sequence[int]) -> str:
        return "│" + "│".join(f" {cells[(x, y)]} " for x in columns) + "│"

    return [
        "┌───┬───┬───┬───┐       ┌───┬───┐",
        row_cells(0, range(0, 4)) + "       " + row_cells(0, range(6, 8)),
        "├───┼───┼───┼───┼───┬───┼───┼───┤",
        row_cells(1, range(0, 8)),
        "├───┼───┼───┼───┼───┴───┼───┼───┤",
        row_cells(2, range(0, 4)) + "       " + row_cells(2, range(6, 8)),
        "└───┴───┴───┴───┘       └───┴───┘",
    ]


def ur_legal_pieces(match: Dict[str, object], side: str, roll: int) -> List[int]:
    if roll <= 0:
        return []
    positions = match["positions"][side]
    enemy_positions = match["positions"][ur_opponent(side)]
    legal: List[int] = []
    for piece, position in enumerate(positions):
        position = int(position)
        if position == UR_FINISHED:
            continue
        target = ur_target(position, roll)
        if target > UR_FINISHED:
            continue
        if target < UR_FINISHED and target in positions:
            continue
        if target == UR_SAFE_ROSETTE and target in enemy_positions:
            continue
        legal.append(piece)
    return legal


def apply_ur_move(match: Dict[str, object], side: str, piece: int, roll: int) -> Dict[str, object]:
    if piece not in ur_legal_pieces(match, side, roll):
        raise ValueError("That Royal Game of Ur move is not legal.")
    positions = match["positions"][side]
    enemy_side = ur_opponent(side)
    enemy_positions = match["positions"][enemy_side]
    source = int(positions[piece])
    target = ur_target(source, roll)
    captured = None
    if target in UR_SHARED and target != UR_SAFE_ROSETTE and target in enemy_positions:
        captured = enemy_positions.index(target)
        enemy_positions[captured] = UR_HOME
    positions[piece] = target
    extra_turn = target in UR_ROSETTES and target != UR_FINISHED
    return {
        "side": side, "piece": piece, "source": source, "target": target,
        "captured_piece": captured, "extra_turn": extra_turn,
        "finished": target == UR_FINISHED,
        "won": all(int(position) == UR_FINISHED for position in positions),
    }


def ur_move_score(match: Dict[str, object], side: str, piece: int, roll: int) -> int:
    source = int(match["positions"][side][piece])
    target = ur_target(source, roll)
    enemy_positions = match["positions"][ur_opponent(side)]
    score = target * 2
    if target == UR_FINISHED:
        score += 120
    if target in UR_ROSETTES:
        score += 42
    if target in UR_SHARED and target != UR_SAFE_ROSETTE and target in enemy_positions:
        score += 75
    if source == UR_HOME:
        score += 8
    if target in UR_SHARED and target != UR_SAFE_ROSETTE:
        for enemy in enemy_positions:
            distance = target - int(enemy)
            if 1 <= distance <= 4:
                score -= 8
    return score


def choose_ur_ai_piece(
    match: Dict[str, object], difficulty: str, roll: int, rng: random.Random,
) -> int:
    legal = ur_legal_pieces(match, "ai", roll)
    if not legal:
        raise ValueError("No legal Royal Game of Ur move.")
    if difficulty == "Friendly":
        return int(rng.choice(legal))
    scored = [(ur_move_score(match, "ai", piece, roll), rng.random(), piece) for piece in legal]
    scored.sort(reverse=True)
    if difficulty == "Practiced" and len(scored) > 1 and rng.random() < 0.25:
        return int(rng.choice(scored[: min(3, len(scored))])[2])
    return int(scored[0][2])


def ur_profit_for_win(wager: int, difficulty: str) -> int:
    numerator, denominator = UR_PAYOUT_RATIOS.get(difficulty, (1, 1))
    return max(0, int(wager)) * numerator // denominator


class UrMixin:
    UR_MIN_WAGER = 10
    UR_MAX_WAGER = 1000

    def ensure_ur_state(self) -> None:
        stats = getattr(self.state, "tavern_ur_stats", None)
        if not isinstance(stats, dict):
            stats = {}
        cleaned = {}
        for key, default in UR_STATS_DEFAULTS.items():
            try:
                value = int(stats.get(key, default) or 0)
            except (TypeError, ValueError):
                value = default
            cleaned[key] = value if key == "net_winnings" else max(0, value)
        self.state.tavern_ur_stats = cleaned
        if not self.valid_ur_match(getattr(self.state, "tavern_ur_match", None)):
            self.state.tavern_ur_match = {}

    @staticmethod
    def valid_ur_match(match: object) -> bool:
        if not isinstance(match, dict) or not match:
            return False
        try:
            positions = match.get("positions")
            valid_positions = (
                isinstance(positions, dict)
                and all(
                    isinstance(positions.get(side), list)
                    and len(positions[side]) == 7
                    and all(isinstance(value, int) and UR_HOME <= value <= UR_FINISHED for value in positions[side])
                    and len([value for value in positions[side] if value not in {UR_HOME, UR_FINISHED}])
                    == len(set(value for value in positions[side] if value not in {UR_HOME, UR_FINISHED}))
                    for side in ("player", "ai")
                )
            )
            roll = match.get("roll")
            return (
                valid_positions
                and str(match.get("turn")) in {"player", "ai"}
                and str(match.get("difficulty")) in UR_PAYOUT_RATIOS
                and (roll is None or int(roll) in range(5))
            )
        except (TypeError, ValueError):
            return False

    def new_ur_match(self, difficulty: str, venue: str, wager: int = 0) -> Dict[str, object]:
        self.ensure_ur_state()
        if self.state.tavern_ur_match:
            return {}
        difficulty = difficulty if difficulty in UR_PAYOUT_RATIOS else "Practiced"
        wager = max(0, int(wager))
        if wager and not self.UR_MIN_WAGER <= wager <= self.UR_MAX_WAGER:
            self.set_message("Royal Game of Ur wagers must be between 10g and 1,000g.")
            return {}
        if int(self.state.money) < wager:
            self.set_message(f"You need {wager}g for that wager.")
            return {}
        self.state.money -= wager
        match = {
            "venue": str(venue), "difficulty": difficulty, "wager": wager,
            "positions": {"player": [UR_HOME] * 7, "ai": [UR_HOME] * 7},
            "turn": "player", "roll": None, "dice": [], "move_count": 0,
            "pending_minutes": 0, "player_captures": 0, "ai_captures": 0,
            "player_rosettes": 0, "ai_rosettes": 0, "player_rolls": 0,
            "history": [], "note": "Roll the four marked dice, then choose a legal piece.",
        }
        self.state.tavern_ur_match = match
        return match

    @staticmethod
    def ur_rules_lines() -> List[str]:
        return [
            "THE ROYAL GAME OF UR", "",
            "- Each side races seven pieces along a fourteen-space route and must bear every piece off exactly.",
            "- Four binary tetrahedral dice produce a roll from 0 to 4. A zero loses the turn.",
            "- A piece at home enters according to the roll. A move may not land on another friendly piece.",
            "- The central eight spaces are shared. Landing on an opposing piece there sends it home.",
            "- The central rosette is safe and cannot be captured or entered while occupied by an opponent.",
            "- Landing on any rosette grants another roll.",
            "- The first player to bear off all seven pieces wins.",
            "- Friendly, Practiced, and Expert opponents make increasingly careful choices.",
            "- Free games are available. Wagered wins earn 1x, 1.5x, or 2x profit by difficulty; draws are impossible.",
            "- R or confirm rolls. W/S, A/D, or arrows choose a move; number keys jump to listed legal moves.",
            "- Confirm moves. B/X/Escape/Q/Tab pauses with the current roll saved.",
        ]

    def ur_stats_lines(self) -> List[str]:
        self.ensure_ur_state()
        stats = self.state.tavern_ur_stats
        match = self.state.tavern_ur_match
        return [
            "ROYAL GAME OF UR RECORD", "",
            f"Games: {stats['games_played']}",
            f"Wins: {stats['wins']} | Losses: {stats['losses']}",
            f"Captures: {stats['captures']} | Rosettes: {stats['rosettes']}",
            f"Pieces borne off: {stats['pieces_finished']} | Rolls: {stats['rolls']}",
            f"Gold wagered: {stats['total_wagered']}g",
            f"Net winnings: {int(stats['net_winnings']):+d}g",
            f"Biggest win: +{stats['biggest_win']}g | Biggest loss: -{stats['biggest_loss']}g",
            f"Best winning streak: {stats['best_streak']}", "",
            (
                f"Paused game: {match.get('difficulty')} at {match.get('venue')} for {match.get('wager', 0)}g."
                if match else "Paused game: none."
            ),
        ]

    @staticmethod
    def _ur_position_label(position: int) -> str:
        if position == UR_HOME:
            return "home"
        if position == UR_FINISHED:
            return "finished"
        if position in UR_ROSETTES:
            return f"space {position + 1} (rosette)"
        return f"space {position + 1}"

    def _draw_ur_board(self, match: Dict[str, object], legal: Sequence[int], selected: int) -> None:
        clear_screen()
        wager = int(match.get("wager", 0))
        profit = ur_profit_for_win(wager, str(match.get("difficulty")))
        minigame_title(
            "Royal Game of Ur",
            f"Opponent: {match.get('difficulty')} | Gold: {int(self.state.money)}g | "
            + (f"Wager {wager}g | Win profit +{profit}g" if wager else "Free game"),
        )
        player_positions = match["positions"]["player"]
        ai_positions = match["positions"]["ai"]
        print("")
        print(
            "You:  "
            + colorize("@ @ @ @ @ @ @", C.LIT)
            + f"    Home: {player_positions.count(UR_FINISHED)}"
        )
        print(
            "CPU:  "
            + colorize("o o o o o o o", C.ROOF_RED)
            + f"    Home: {ai_positions.count(UR_FINISHED)}"
        )
        roll = match.get("roll")
        print("")
        print(f"Roll: {roll if roll is not None else '-'}")
        print(
            "Select a piece to move."
            if legal
            else "Roll the dice with R, Z, Enter, or Space."
        )
        print("")
        for line in render_ur_board_lines(match, legal, selected):
            print(line)
        print("")
        print("Legend: @ you, o opponent, ✦ rosette, · legal move, × capture")
        if legal:
            minigame_section("Movable pieces")
            roll_value = int(match.get("roll", 0))
            for index, piece in enumerate(legal):
                source = int(player_positions[piece])
                target = ur_target(source, roll_value)
                line = (
                    f"{'>' if index == selected else ' '} {index + 1}. Piece {piece + 1}: "
                    f"{self._ur_position_label(source)} -> {self._ur_position_label(target)}"
                )
                print(colorize(line, C.UI_SELECTED) if index == selected else line)
        minigame_notice(match.get("note", ""))
        history = " | ".join(str(value) for value in match.get("history", [])[-3:]) or "No moves yet."
        minigame_notice(history, prefix="RECENT")
        minigame_controls(
            "R or Z/Enter/Space: roll",
            "W/S or A/D: choose move",
            "1-7: jump to option",
            "Z/Enter/Space: move",
            "H: rules",
            "B/X/Esc/Q/Tab: pause",
        )

    def _ur_rng(self, match: Dict[str, object]) -> random.Random:
        return random.Random(
            int(getattr(self.state, "wilderness_seed", 0))
            + int(match.get("move_count", 0)) * 99991
            + int(match.get("player_rolls", 0)) * 7919
            + sum(ord(ch) for ch in str(match.get("venue", "")))
        )

    def _roll_ur_turn(self, match: Dict[str, object], side: str) -> None:
        dice = roll_ur_dice(self._ur_rng(match))
        roll = ur_roll_total(dice)
        match["dice"] = dice
        match["roll"] = roll
        key = "player_rolls" if side == "player" else "ai_rolls"
        match[key] = int(match.get(key, 0)) + 1
        actor = "You" if side == "player" else "Opponent"
        if roll == 0:
            match.setdefault("history", []).append(f"{actor} rolled zero and lost the turn.")
            match["turn"] = ur_opponent(side)
            match["roll"] = None
            match["dice"] = []
        elif not ur_legal_pieces(match, side, roll):
            match.setdefault("history", []).append(f"{actor} rolled {roll} but had no legal move.")
            match["turn"] = ur_opponent(side)
            match["roll"] = None
            match["dice"] = []
        else:
            match["note"] = f"{actor} rolled {roll}."

    def _complete_ur_move(self, match: Dict[str, object], side: str, piece: int) -> Dict[str, object]:
        roll = int(match.get("roll", 0))
        result = apply_ur_move(match, side, piece, roll)
        match["move_count"] = int(match.get("move_count", 0)) + 1
        match["pending_minutes"] = int(match.get("pending_minutes", 0)) + 1
        actor = "You" if side == "player" else "Opponent"
        detail = f"{actor} moved piece {piece + 1} by {roll}"
        if result["captured_piece"] is not None:
            key = "player_captures" if side == "player" else "ai_captures"
            match[key] = int(match.get(key, 0)) + 1
            detail += " and made a capture"
        if result["target"] in UR_ROSETTES:
            key = "player_rosettes" if side == "player" else "ai_rosettes"
            match[key] = int(match.get(key, 0)) + 1
            detail += " onto a rosette"
        match.setdefault("history", []).append(detail + ".")
        match["history"] = match["history"][-20:]
        match["roll"] = None
        match["dice"] = []
        match["turn"] = side if result["extra_turn"] else ur_opponent(side)
        match["note"] = (
            "You earned another roll." if side == "player" and result["extra_turn"]
            else "The opponent earned another roll." if result["extra_turn"]
            else "Your turn." if side == "ai" else "The opponent's turn."
        )
        return result

    def _advance_ur_ai(self, match: Dict[str, object]) -> None:
        while str(match.get("turn")) == "ai":
            if match.get("roll") is None:
                self._roll_ur_turn(match, "ai")
                if str(match.get("turn")) != "ai":
                    return
            roll = int(match.get("roll", 0))
            piece = choose_ur_ai_piece(
                match, str(match.get("difficulty", "Practiced")), roll, self._ur_rng(match),
            )
            result = self._complete_ur_move(match, "ai", piece)
            if result["won"]:
                return

    def play_ur_match(self) -> None:
        self.ensure_ur_state()
        match = self.state.tavern_ur_match
        selected = 0
        while match:
            if all(position == UR_FINISHED for position in match["positions"]["player"]):
                self.finish_ur_match("win")
                return
            if all(position == UR_FINISHED for position in match["positions"]["ai"]):
                self.finish_ur_match("loss")
                return
            if str(match.get("turn")) == "ai":
                self._advance_ur_ai(match)
                continue
            roll = match.get("roll")
            legal = ur_legal_pieces(match, "player", int(roll)) if roll is not None else []
            selected = min(selected, max(0, len(legal) - 1))
            self._draw_ur_board(match, legal, selected)
            key = normalize_key(read_key())
            if key in {"b", "x", "\x1b", "q", "\t"}:
                self.pause_ur_match()
                return
            if key == "h":
                self.vertical_panel_view("Royal Game of Ur Rules", self.ur_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if roll is None and (key == "r" or key in MENU_CONFIRM_KEYS):
                self._roll_ur_turn(match, "player")
                selected = 0
                continue
            if key in {"w", "a", "UP", "LEFT"} and legal:
                selected = (selected - 1) % len(legal)
            elif key in {"s", "d", "DOWN", "RIGHT"} and legal:
                selected = (selected + 1) % len(legal)
            elif key.isdigit() and 1 <= int(key) <= len(legal):
                selected = int(key) - 1
            elif key in MENU_CONFIRM_KEYS and legal:
                self._complete_ur_move(match, "player", legal[selected])

    def pause_ur_match(self) -> None:
        match = self.state.tavern_ur_match
        elapsed = max(0, int(match.get("pending_minutes", 0)))
        match["pending_minutes"] = 0
        if elapsed:
            self.advance_time(elapsed)
        self.autosave_with_message("Paused the Royal Game of Ur. Its roll, pieces, and wager were saved.")

    def finish_ur_match(self, outcome: str, resigned: bool = False) -> None:
        match = self.state.tavern_ur_match
        if not self.valid_ur_match(match):
            return
        wager = int(match.get("wager", 0))
        profit = ur_profit_for_win(wager, str(match.get("difficulty"))) if outcome == "win" else -wager
        payout = wager + profit if outcome == "win" else 0
        self.state.money += payout
        stats = self.state.tavern_ur_stats
        stats["games_played"] += 1
        stats["captures"] += int(match.get("player_captures", 0))
        stats["rosettes"] += int(match.get("player_rosettes", 0))
        stats["pieces_finished"] += match["positions"]["player"].count(UR_FINISHED)
        stats["rolls"] += int(match.get("player_rolls", 0))
        stats["total_wagered"] += wager
        stats["net_winnings"] += profit
        if outcome == "win":
            stats["wins"] += 1
            stats["biggest_win"] = max(stats["biggest_win"], profit)
            stats["current_streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
        else:
            stats["losses"] += 1
            stats["biggest_loss"] = max(stats["biggest_loss"], wager)
            stats["current_streak"] = 0
        self.state.tavern_ur_match = {}
        self.advance_time(max(10, int(match.get("pending_minutes", 0)) + 8))
        message = (
            f"You won the Royal Game of Ur and earned {profit}g."
            if outcome == "win"
            else "You resigned and forfeited the Ur wager." if resigned and wager
            else "You resigned from the Royal Game of Ur." if resigned
            else "You lost the Royal Game of Ur."
        )
        self.autosave_with_message(message)

    def ur_wager_menu(self, venue: str, difficulty: str) -> Optional[int]:
        presets = (0, 10, 25, 50, 100, 250, 500, 1000)
        items = [
            MenuItem(
                label="Free game" if amount == 0 else f"Wager {amount}g",
                value=str(amount),
                enabled=amount == 0 or int(self.state.money) >= amount,
                hint="practice" if amount == 0 else f"win +{ur_profit_for_win(amount, difficulty)}g",
            )
            for amount in presets
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(
            f"{venue} - {difficulty} Ur", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
        )
        return None if not choice or choice.value == MENU_BACK else int(choice.value)

    def ur_menu(self, venue: str = "Tavern") -> None:
        while True:
            self.ensure_ur_state()
            match = self.state.tavern_ur_match
            items = (
                [
                    MenuItem(label="Resume game", value="resume", enabled=True, hint=f"{match.get('difficulty')} | {match.get('wager', 0)}g"),
                    MenuItem(label="Resign game", value="resign", enabled=True, hint="forfeits wager"),
                ]
                if match else [
                    MenuItem(label=f"New game: {difficulty}", value=f"new:{difficulty}", enabled=True, hint=hint)
                    for difficulty, hint in (
                        ("Friendly", "1x wager profit"), ("Practiced", "1.5x wager profit"), ("Expert", "2x wager profit"),
                    )
                ]
            )
            items.extend([
                MenuItem(label="Rules", value="rules", enabled=True),
                MenuItem(label="Playing record", value="stats", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(f"{venue} - Royal Game of Ur", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "rules":
                self.vertical_panel_view("Royal Game of Ur Rules", self.ur_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "stats":
                self.vertical_panel_view("Royal Game of Ur Record", self.ur_stats_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "resign":
                self.finish_ur_match("loss", resigned=True)
            else:
                if str(choice.value).startswith("new:"):
                    difficulty = str(choice.value).split(":", 1)[1]
                    wager = self.ur_wager_menu(venue, difficulty)
                    if wager is None or not self.new_ur_match(difficulty, venue, wager):
                        continue
                    self.autosave_with_message(f"Started a Royal Game of Ur at {venue}.")
                self.play_ur_match()
