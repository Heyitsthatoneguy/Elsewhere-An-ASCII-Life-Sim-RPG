"""Persistent four-seat Hearts with passing, trick AI, and full match scoring."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_support import C, clear_screen, colorize, normalize_key, read_key
from ascii_farmstead_ui import MenuItem
from ascii_farmstead_cards import card_color, card_suit_glyph, print_card_rows
from ascii_farmstead_minigame_ui import minigame_controls, minigame_notice, minigame_section, minigame_title


HEARTS_RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
HEARTS_SUITS = ("C", "D", "S", "H")
HEARTS_VALUE = {rank: index + 2 for index, rank in enumerate(HEARTS_RANKS)}
HEARTS_NAMES = ("You", "Mara", "Rowan", "Silas")
HEARTS_PASS_DIRECTIONS = ("left", "right", "across", "hold")
HEARTS_STATS_DEFAULTS = {
    "matches_played": 0, "wins": 0, "losses": 0, "ties": 0,
    "rounds_played": 0, "tricks_won": 0, "penalty_points": 0,
    "moons_shot": 0, "best_score": 0, "current_streak": 0, "best_streak": 0,
}


def hearts_card(rank: str, suit: str) -> str:
    return f"{rank}{suit}"


def hearts_rank(card: str) -> str:
    return str(card)[:-1]


def hearts_suit(card: str) -> str:
    return str(card)[-1:]


def hearts_card_value(card: str) -> int:
    return HEARTS_VALUE[hearts_rank(card)]


def hearts_sort_key(card: str):
    return HEARTS_SUITS.index(hearts_suit(card)), hearts_card_value(card)


def make_hearts_deck(rng: Optional[random.Random] = None) -> List[str]:
    deck = [hearts_card(rank, suit) for suit in HEARTS_SUITS for rank in HEARTS_RANKS]
    (rng or random.Random()).shuffle(deck)
    return deck


def hearts_legal_cards(
    hand: Sequence[str],
    trick: Sequence[Dict[str, object]],
    hearts_broken: bool,
    first_trick: bool,
) -> List[str]:
    cards = list(hand)
    if not cards:
        return []
    if not trick:
        if first_trick and "2C" in cards:
            return ["2C"]
        if not hearts_broken:
            non_hearts = [card for card in cards if hearts_suit(card) != "H"]
            if non_hearts:
                return non_hearts
        return cards
    led_suit = hearts_suit(str(trick[0]["card"]))
    following = [card for card in cards if hearts_suit(card) == led_suit]
    if following:
        return following
    if first_trick:
        safe = [card for card in cards if hearts_suit(card) != "H" and card != "QS"]
        if safe:
            return safe
    return cards


def hearts_trick_winner(trick: Sequence[Dict[str, object]]) -> int:
    if len(trick) != 4:
        raise ValueError("A Hearts trick requires four cards.")
    led = hearts_suit(str(trick[0]["card"]))
    eligible = [play for play in trick if hearts_suit(str(play["card"])) == led]
    return int(max(eligible, key=lambda play: hearts_card_value(str(play["card"])))["seat"])


def hearts_trick_points(trick: Sequence[Dict[str, object]]) -> int:
    return sum(
        1 if hearts_suit(str(play["card"])) == "H" else 13 if str(play["card"]) == "QS" else 0
        for play in trick
    )


def hearts_round_scores(points: Sequence[int]) -> List[int]:
    values = [int(value) for value in points]
    if 26 in values:
        shooter = values.index(26)
        return [0 if seat == shooter else 26 for seat in range(4)]
    return values


def hearts_pass_target(seat: int, direction: str) -> int:
    if direction == "left":
        return (seat + 1) % 4
    if direction == "right":
        return (seat - 1) % 4
    if direction == "across":
        return (seat + 2) % 4
    return seat


def choose_hearts_pass(hand: Sequence[str]) -> List[str]:
    def danger(card: str) -> int:
        value = hearts_card_value(card)
        if card == "QS":
            return 1000
        if hearts_suit(card) == "S" and value >= 13:
            return 600 + value
        if hearts_suit(card) == "H":
            return 400 + value
        return value
    return sorted(hand, key=danger, reverse=True)[:3]


def choose_hearts_ai_card(
    hand: Sequence[str],
    trick: Sequence[Dict[str, object]],
    hearts_broken: bool,
    first_trick: bool,
    rng: random.Random,
) -> str:
    legal = hearts_legal_cards(hand, trick, hearts_broken, first_trick)
    if not trick:
        non_points = [card for card in legal if hearts_suit(card) != "H" and card != "QS"]
        pool = non_points or legal
        return min(pool, key=lambda card: (hearts_card_value(card), rng.random()))
    led = hearts_suit(str(trick[0]["card"]))
    following = [card for card in legal if hearts_suit(card) == led]
    if not following:
        if "QS" in legal:
            return "QS"
        hearts = [card for card in legal if hearts_suit(card) == "H"]
        if hearts:
            return max(hearts, key=hearts_card_value)
        return max(legal, key=hearts_card_value)
    current_high = max(
        hearts_card_value(str(play["card"]))
        for play in trick if hearts_suit(str(play["card"])) == led
    )
    below = [card for card in following if hearts_card_value(card) < current_high]
    if below:
        return max(below, key=hearts_card_value)
    return min(following, key=hearts_card_value)


def deal_hearts_round(match: Dict[str, object], rng: random.Random) -> None:
    deck = make_hearts_deck(rng)
    hands = [sorted(deck[seat::4], key=hearts_sort_key) for seat in range(4)]
    round_index = int(match.get("round_index", 0))
    direction = HEARTS_PASS_DIRECTIONS[round_index % 4]
    match.update({
        "hands": hands,
        "trick": [],
        "leader": next(seat for seat, hand in enumerate(hands) if "2C" in hand),
        "turn": next(seat for seat, hand in enumerate(hands) if "2C" in hand),
        "hearts_broken": False,
        "trick_number": 0,
        "round_points": [0, 0, 0, 0],
        "pass_direction": direction,
        "phase": "play" if direction == "hold" else "pass",
        "selected_pass": [],
        "note": (
            "No passing this round. The holder of 2C leads."
            if direction == "hold"
            else f"Choose three cards to pass {direction}."
        ),
    })


def apply_hearts_passes(match: Dict[str, object], player_cards: Sequence[str]) -> None:
    direction = str(match.get("pass_direction", "hold"))
    if direction == "hold":
        match["phase"] = "play"
        return
    hands: List[List[str]] = match["hands"]
    if len(player_cards) != 3 or any(card not in hands[0] for card in player_cards):
        raise ValueError("Choose three distinct cards to pass.")
    passing = [list(player_cards)]
    for seat in range(1, 4):
        passing.append(choose_hearts_pass(hands[seat]))
    for seat in range(4):
        for card in passing[seat]:
            hands[seat].remove(card)
    for seat in range(4):
        target = hearts_pass_target(seat, direction)
        hands[target].extend(passing[seat])
    for hand in hands:
        hand.sort(key=hearts_sort_key)
    holder = next(seat for seat, hand in enumerate(hands) if "2C" in hand)
    match.update({
        "phase": "play", "leader": holder, "turn": holder,
        "selected_pass": [], "note": "Passing is complete. The holder of 2C leads.",
    })


def play_hearts_card(match: Dict[str, object], seat: int, card: str) -> Dict[str, object]:
    if str(match.get("phase")) != "play" or int(match.get("turn", -1)) != seat:
        raise ValueError("It is not that player's turn.")
    hands: List[List[str]] = match["hands"]
    trick: List[Dict[str, object]] = match["trick"]
    first = int(match.get("trick_number", 0)) == 0
    legal = hearts_legal_cards(hands[seat], trick, bool(match.get("hearts_broken")), first)
    if card not in legal:
        raise ValueError("That Hearts card is not legal.")
    hands[seat].remove(card)
    trick.append({"seat": seat, "card": card})
    if hearts_suit(card) == "H":
        match["hearts_broken"] = True
    if len(trick) < 4:
        match["turn"] = (seat + 1) % 4
        return {"trick_complete": False, "round_complete": False}
    winner = hearts_trick_winner(trick)
    points = hearts_trick_points(trick)
    match["round_points"][winner] += points
    match["trick_number"] = int(match.get("trick_number", 0)) + 1
    match["last_trick"] = list(trick)
    match["last_trick_winner"] = winner
    match["trick"] = []
    match["leader"] = winner
    match["turn"] = winner
    round_complete = not any(hands)
    return {
        "trick_complete": True, "round_complete": round_complete,
        "winner": winner, "points": points,
    }


class HeartsMixin:
    def ensure_hearts_state(self) -> None:
        stats = getattr(self.state, "tavern_hearts_stats", None)
        if not isinstance(stats, dict):
            stats = {}
        self.state.tavern_hearts_stats = {
            key: max(0, int(stats.get(key, default) or 0))
            if str(stats.get(key, default) or "0").lstrip("-").isdigit() else default
            for key, default in HEARTS_STATS_DEFAULTS.items()
        }
        if not self.valid_hearts_match(getattr(self.state, "tavern_hearts_match", None)):
            self.state.tavern_hearts_match = {}

    @staticmethod
    def valid_hearts_match(match: object) -> bool:
        if not isinstance(match, dict) or not match:
            return False
        hands = match.get("hands")
        trick = match.get("trick")
        return (
            isinstance(hands, list) and len(hands) == 4
            and all(isinstance(hand, list) for hand in hands)
            and isinstance(trick, list)
            and isinstance(match.get("scores"), list) and len(match["scores"]) == 4
            and str(match.get("phase")) in {"pass", "play"}
            and int(match.get("turn", -1)) in range(4)
        )

    def _hearts_round_rng(self, round_index: int) -> random.Random:
        return random.Random(
            int(getattr(self.state, "wilderness_seed", 0))
            + int(getattr(self.state, "absolute_day", 0)) * 4099
            + int(round_index) * 104729
        )

    def new_hearts_match(self, venue: str) -> Dict[str, object]:
        match = {
            "scores": [0, 0, 0, 0], "round_index": 0, "venue": str(venue),
            "pending_minutes": 0, "player_tricks": 0, "player_moons": 0,
            "history": [],
        }
        deal_hearts_round(match, self._hearts_round_rng(0))
        self.state.tavern_hearts_match = match
        return match

    @staticmethod
    def hearts_rules_lines() -> List[str]:
        return [
            "HEARTS", "",
            "- Four players receive thirteen cards. Pass three cards left, right, across, then hold on successive rounds.",
            "- The holder of 2C leads the first trick. Follow the led suit whenever possible.",
            "- Hearts cannot be led until a Heart has been discarded, unless a player holds only Hearts.",
            "- Hearts and QS cannot be discarded on the first trick unless no alternative exists.",
            "- The highest card of the led suit wins the trick and leads next.",
            "- Every Heart is 1 penalty point; QS is 13. The lowest total score wins.",
            "- Taking all 26 points shoots the moon: everyone else receives 26 instead.",
            "- A match ends after a round raises any total to 100 or more. Lowest score wins.",
            "- Hearts and Diamonds are red; Clubs and Spades are white. Numbered markers identify your hand.",
            "- Choose with A/D, W/S, arrows, or number keys 1-9. Confirm plays or toggles; P passes three selected cards.",
            "- X/Escape/Q pauses safely during passing or card selection.",
        ]

    def hearts_stats_lines(self) -> List[str]:
        self.ensure_hearts_state()
        stats = self.state.tavern_hearts_stats
        match = self.state.tavern_hearts_match
        return [
            "HEARTS RECORD", "",
            f"Matches: {stats['matches_played']}",
            f"Wins: {stats['wins']} | Losses: {stats['losses']} | Ties: {stats['ties']}",
            f"Rounds: {stats['rounds_played']} | Tricks won: {stats['tricks_won']}",
            f"Penalty points taken: {stats['penalty_points']}",
            f"Moons shot: {stats['moons_shot']}",
            f"Best winning score: {stats['best_score']}",
            f"Best streak: {stats['best_streak']}", "",
            (
                f"Paused match: round {int(match.get('round_index', 0)) + 1} at {match.get('venue')}."
                if match else "Paused match: none."
            ),
        ]

    @staticmethod
    def _hearts_card_text(card: str) -> str:
        return colorize(
            f"{hearts_rank(card)}{card_suit_glyph(hearts_suit(card))}",
            card_color(card),
        )

    def _draw_hearts_hand(self, match: Dict[str, object], cursor: int, selected: Sequence[str], passing: bool) -> None:
        clear_screen()
        scores = match["scores"]
        minigame_title(
            f"{str(match.get('venue', 'Tavern'))} - Hearts",
            "Scores: " + " | ".join(f"{HEARTS_NAMES[i]} {scores[i]}" for i in range(4)),
        )
        minigame_section(
            f"Round {int(match.get('round_index', 0)) + 1}",
            f"Pass: {match.get('pass_direction')} | "
            f"Hearts {'broken' if match.get('hearts_broken') else 'unbroken'}",
        )
        trick = match.get("trick", [])
        minigame_section("Current trick")
        if trick:
            print_card_rows([str(play["card"]) for play in trick], max_per_row=4, indent="  ")
            print("  " + " | ".join(
                f"{index + 1}: {HEARTS_NAMES[int(play['seat'])]}"
                for index, play in enumerate(trick)
            ))
        else:
            print("  No cards played yet.")
        hand = match["hands"][0]
        legal = set(hand if passing else hearts_legal_cards(
            hand, trick, bool(match.get("hearts_broken")), int(match.get("trick_number", 0)) == 0,
        ))
        selected_indices = [index for index, card in enumerate(hand) if card in selected]
        minigame_section(
            "Your hand",
            f"{len(selected)}/3 selected" if passing else f"{len(legal)} of {len(hand)} playable",
        )
        print_card_rows(
            hand,
            max_per_row=7,
            cursor=cursor,
            selected=selected_indices,
            show_numbers=True,
            indent="  ",
        )
        if not passing:
            print("Playable: " + ", ".join(str(index + 1) for index, card in enumerate(hand) if card in legal))
        minigame_notice(match.get("note", ""))
        minigame_controls(
            "A/D or W/S: choose",
            "1-9: jump to card",
            "Z/Enter/Space: toggle" if passing else "Z/Enter/Space: play",
            "P: pass three" if passing else "",
            "X/Esc/Q: pause",
        )

    def _hearts_player_pass(self, match: Dict[str, object]) -> bool:
        cursor = 0
        selected = list(match.get("selected_pass", []))
        while True:
            hand = match["hands"][0]
            cursor = min(cursor, len(hand) - 1)
            self._draw_hearts_hand(match, cursor, selected, True)
            key = normalize_key(read_key())
            if key in {"x", "\x1b", "q"}:
                match["selected_pass"] = selected
                self.pause_hearts_match()
                return False
            if key in {"w", "a", "UP", "LEFT"}:
                cursor = (cursor - 1) % len(hand)
            elif key in {"s", "d", "DOWN", "RIGHT"}:
                cursor = (cursor + 1) % len(hand)
            elif key.isdigit() and 1 <= int(key) <= min(9, len(hand)):
                cursor = int(key) - 1
            elif key in MENU_CONFIRM_KEYS:
                card = hand[cursor]
                if card in selected:
                    selected.remove(card)
                elif len(selected) < 3:
                    selected.append(card)
            elif key == "p" and len(selected) == 3:
                apply_hearts_passes(match, selected)
                return True

    def _hearts_player_card(self, match: Dict[str, object]) -> bool:
        cursor = 0
        while True:
            hand = match["hands"][0]
            legal = hearts_legal_cards(
                hand, match["trick"], bool(match.get("hearts_broken")),
                int(match.get("trick_number", 0)) == 0,
            )
            legal_indices = [index for index, card in enumerate(hand) if card in legal]
            if cursor not in legal_indices:
                cursor = legal_indices[0]
            self._draw_hearts_hand(match, cursor, [], False)
            key = normalize_key(read_key())
            if key in {"x", "\x1b", "q"}:
                self.pause_hearts_match()
                return False
            if key in {"w", "a", "UP", "LEFT"}:
                position = legal_indices.index(cursor)
                cursor = legal_indices[(position - 1) % len(legal_indices)]
            elif key in {"s", "d", "DOWN", "RIGHT"}:
                position = legal_indices.index(cursor)
                cursor = legal_indices[(position + 1) % len(legal_indices)]
            elif key.isdigit() and 1 <= int(key) <= min(9, len(hand)) and int(key) - 1 in legal_indices:
                cursor = int(key) - 1
            elif key in MENU_CONFIRM_KEYS and hand[cursor] in legal:
                result = play_hearts_card(match, 0, hand[cursor])
                match["pending_minutes"] = int(match.get("pending_minutes", 0)) + 1
                self._after_hearts_play(match, result)
                return True

    def _after_hearts_play(self, match: Dict[str, object], result: Dict[str, object]) -> None:
        if result.get("trick_complete"):
            winner = int(result["winner"])
            points = int(result["points"])
            match.setdefault("history", []).append(
                f"{HEARTS_NAMES[winner]} won a {points}-point trick."
            )
            if winner == 0:
                match["player_tricks"] = int(match.get("player_tricks", 0)) + 1
        if not result.get("round_complete"):
            return
        raw = list(match["round_points"])
        scored = hearts_round_scores(raw)
        if raw[0] == 26:
            match["player_moons"] = int(match.get("player_moons", 0)) + 1
        match["scores"] = [int(match["scores"][seat]) + scored[seat] for seat in range(4)]
        match["last_round_points"] = raw
        match["round_complete"] = True

    def _advance_hearts_ai(self, match: Dict[str, object]) -> None:
        rng = self._hearts_round_rng(int(match.get("round_index", 0)) * 100 + int(match.get("trick_number", 0)))
        while str(match.get("phase")) == "play" and int(match.get("turn", 0)) != 0 and not match.get("round_complete"):
            seat = int(match["turn"])
            card = choose_hearts_ai_card(
                match["hands"][seat], match["trick"], bool(match.get("hearts_broken")),
                int(match.get("trick_number", 0)) == 0, rng,
            )
            result = play_hearts_card(match, seat, card)
            self._after_hearts_play(match, result)

    def _continue_or_finish_hearts_round(self, match: Dict[str, object]) -> bool:
        if not match.get("round_complete"):
            return False
        self.state.tavern_hearts_stats["rounds_played"] += 1
        self.state.tavern_hearts_stats["penalty_points"] += int(match["last_round_points"][0])
        if max(int(score) for score in match["scores"]) >= 100:
            lowest = min(int(score) for score in match["scores"])
            winners = [seat for seat, score in enumerate(match["scores"]) if int(score) == lowest]
            outcome = "win" if winners == [0] else "tie" if 0 in winners else "loss"
            self.finish_hearts_match(outcome)
            return True
        match["round_index"] = int(match.get("round_index", 0)) + 1
        match["round_complete"] = False
        deal_hearts_round(match, self._hearts_round_rng(int(match["round_index"])))
        return False

    def play_hearts_match(self) -> None:
        self.ensure_hearts_state()
        match = self.state.tavern_hearts_match
        if not match:
            return
        while True:
            if self._continue_or_finish_hearts_round(match):
                return
            if str(match.get("phase")) == "pass":
                if not self._hearts_player_pass(match):
                    return
            self._advance_hearts_ai(match)
            if self._continue_or_finish_hearts_round(match):
                return
            if int(match.get("turn", -1)) == 0 and not self._hearts_player_card(match):
                return

    def pause_hearts_match(self) -> None:
        match = self.state.tavern_hearts_match
        elapsed = max(0, int(match.get("pending_minutes", 0)))
        match["pending_minutes"] = 0
        if elapsed:
            self.advance_time(elapsed)
        self.autosave_with_message("Paused Hearts. The hands, trick, passing choices, and scores were saved.")

    def finish_hearts_match(self, outcome: str, resigned: bool = False) -> None:
        match = self.state.tavern_hearts_match
        if not self.valid_hearts_match(match):
            return
        stats = self.state.tavern_hearts_stats
        stats["matches_played"] += 1
        stats["tricks_won"] += int(match.get("player_tricks", 0))
        stats["moons_shot"] += int(match.get("player_moons", 0))
        if outcome == "win":
            stats["wins"] += 1
            score = int(match["scores"][0])
            stats["best_score"] = score if not stats["best_score"] else min(stats["best_score"], score)
            stats["current_streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
        elif outcome == "tie":
            stats["ties"] += 1
        else:
            stats["losses"] += 1
            stats["current_streak"] = 0
        self.state.tavern_hearts_match = {}
        self.advance_time(max(15, int(match.get("pending_minutes", 0)) + 10))
        label = "won" if outcome == "win" else "tied" if outcome == "tie" else "resigned from" if resigned else "lost"
        self.autosave_with_message(f"You {label} the Hearts match at {match.get('venue')}.")

    def hearts_menu(self, venue: str = "Tavern") -> None:
        while True:
            self.ensure_hearts_state()
            match = self.state.tavern_hearts_match
            items = (
                [
                    MenuItem(label="Resume match", value="resume", enabled=True, hint=f"round {int(match.get('round_index', 0)) + 1}"),
                    MenuItem(label="Resign match", value="resign", enabled=True),
                ]
                if match else [MenuItem(label="New match", value="new", enabled=True, hint="first to 100 ends the match")]
            )
            items.extend([
                MenuItem(label="Rules", value="rules", enabled=True),
                MenuItem(label="Playing record", value="stats", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(f"{venue} - Hearts", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "rules":
                self.vertical_panel_view("Hearts Rules", self.hearts_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "stats":
                self.vertical_panel_view("Hearts Record", self.hearts_stats_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "resign":
                self.finish_hearts_match("loss", resigned=True)
            else:
                if choice.value == "new":
                    self.new_hearts_match(venue)
                self.play_hearts_match()
