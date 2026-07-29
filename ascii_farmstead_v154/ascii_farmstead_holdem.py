"""Texas Hold'em table with hand evaluation, limit betting, AI, and records."""

from __future__ import annotations

import itertools
import random
from typing import Dict, List, Optional, Sequence, Tuple

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_support import C, clear_screen, colorize, normalize_key, read_key
from ascii_farmstead_ui import MenuItem
from ascii_farmstead_cards import card_color, card_suit_glyph, print_card_rows
from ascii_farmstead_minigame_ui import (
    minigame_actions,
    minigame_controls,
    minigame_notice,
    minigame_section,
    minigame_title,
)


Card = Tuple[str, str]
POKER_RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
POKER_SUITS = ("S", "H", "D", "C")
POKER_RANK_VALUE = {rank: index + 2 for index, rank in enumerate(POKER_RANKS)}
POKER_CATEGORY_NAMES = (
    "High Card", "One Pair", "Two Pair", "Three of a Kind", "Straight",
    "Flush", "Full House", "Four of a Kind", "Straight Flush",
)
HOLDEM_STATS_DEFAULTS = {
    "hands_played": 0, "wins": 0, "losses": 0, "ties": 0, "folds": 0,
    "showdowns": 0, "pots_won": 0, "total_buyins": 0, "net_winnings": 0,
    "biggest_pot": 0, "best_hand_category": 0, "current_streak": 0, "best_streak": 0,
}


def make_poker_deck(rng: Optional[random.Random] = None) -> List[Card]:
    deck = [(rank, suit) for suit in POKER_SUITS for rank in POKER_RANKS]
    (rng or random.Random()).shuffle(deck)
    return deck


def poker_five_card_rank(cards: Sequence[Card]) -> Tuple[int, ...]:
    if len(cards) != 5:
        raise ValueError("Poker ranks require exactly five cards.")
    values = sorted((POKER_RANK_VALUE[rank] for rank, _suit in cards), reverse=True)
    counts: Dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    groups = sorted(((count, value) for value, count in counts.items()), reverse=True)
    flush = len({suit for _rank, suit in cards}) == 1
    unique = sorted(set(values), reverse=True)
    straight_high = 5 if unique == [14, 5, 4, 3, 2] else (
        unique[0] if len(unique) == 5 and unique[0] - unique[-1] == 4 else 0
    )
    if flush and straight_high:
        return (8, straight_high)
    if groups[0][0] == 4:
        four = groups[0][1]
        kicker = max(value for value in values if value != four)
        return (7, four, kicker)
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *values)
    if straight_high:
        return (4, straight_high)
    if groups[0][0] == 3:
        trips = groups[0][1]
        kickers = sorted((value for value in values if value != trips), reverse=True)
        return (3, trips, *kickers)
    pairs = sorted((value for count, value in groups if count == 2), reverse=True)
    if len(pairs) >= 2:
        kicker = max(value for value in values if value not in pairs[:2])
        return (2, pairs[0], pairs[1], kicker)
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((value for value in values if value != pair), reverse=True)
        return (1, pair, *kickers)
    return (0, *values)


def poker_best_rank(cards: Sequence[Card]) -> Tuple[int, ...]:
    if len(cards) < 5:
        raise ValueError("At least five cards are required.")
    return max(poker_five_card_rank(combo) for combo in itertools.combinations(cards, 5))


def poker_rank_name(rank: Sequence[int]) -> str:
    return POKER_CATEGORY_NAMES[int(rank[0])]


def holdem_preflop_strength(cards: Sequence[Card]) -> int:
    first, second = cards
    a, b = POKER_RANK_VALUE[first[0]], POKER_RANK_VALUE[second[0]]
    high, low = max(a, b), min(a, b)
    score = high * 4 + low
    if a == b:
        score += 45 + high * 2
    if first[1] == second[1]:
        score += 8
    if abs(a - b) == 1:
        score += 7
    if high == 14:
        score += 8
    return score


class HoldemRound:
    """A four-seat fixed-limit table-stakes Hold'em hand."""

    names = ("You", "Mara", "Rowan", "Silas")

    def __init__(self, buy_in: int, rng: Optional[random.Random] = None, deck: Optional[Sequence[Card]] = None):
        self.buy_in = max(20, int(buy_in))
        self.rng = rng or random.Random()
        self.deck = list(deck) if deck is not None else make_poker_deck(self.rng)
        self.holes: List[List[Card]] = [[] for _ in range(4)]
        for _ in range(2):
            for seat in range(4):
                self.holes[seat].append(self.deck.pop(0))
        self.board: List[Card] = []
        self.stacks = [self.buy_in] * 4
        self.folded = [False] * 4
        self.contributions = [0] * 4
        self.street_contributions = [0] * 4
        self.pot = 0
        self.street = "Pre-flop"
        self.bet_size = max(2, self.buy_in // 10)
        self.current_bet = 0
        self.history: List[str] = []
        ante = max(1, self.buy_in // 20)
        for seat in range(4):
            self.commit(seat, ante)
        self.history.append(f"Everyone anted {ante}g.")

    def active_seats(self) -> List[int]:
        return [seat for seat in range(4) if not self.folded[seat]]

    def commit(self, seat: int, amount: int) -> int:
        paid = min(max(0, int(amount)), int(self.stacks[seat]))
        self.stacks[seat] -= paid
        self.contributions[seat] += paid
        self.street_contributions[seat] += paid
        self.pot += paid
        return paid

    def call_cost(self, seat: int) -> int:
        return min(self.stacks[seat], max(0, self.current_bet - self.street_contributions[seat]))

    def confidence(self, seat: int) -> int:
        if len(self.board) >= 3:
            rank = poker_best_rank(self.holes[seat] + self.board)
            return int(rank[0]) * 35 + sum(int(value) for value in rank[1:3])
        return holdem_preflop_strength(self.holes[seat])

    def reveal_next_street(self) -> None:
        if not self.board:
            self.deck.pop(0)
            self.board.extend([self.deck.pop(0) for _ in range(3)])
            self.street = "Flop"
        elif len(self.board) == 3:
            self.deck.pop(0)
            self.board.append(self.deck.pop(0))
            self.street = "Turn"
        elif len(self.board) == 4:
            self.deck.pop(0)
            self.board.append(self.deck.pop(0))
            self.street = "River"
        self.street_contributions = [0] * 4
        self.current_bet = 0

    def ai_open_betting(self, difficulty: str) -> None:
        caution = {"Friendly": 15, "Practiced": 25, "Expert": 35}.get(difficulty, 25)
        for seat in range(1, 4):
            if self.folded[seat] or self.stacks[seat] <= 0:
                continue
            confidence = self.confidence(seat) + self.rng.randint(-caution, caution)
            call = self.call_cost(seat)
            if call and confidence < 45 + len(self.board) * 8:
                self.folded[seat] = True
                self.history.append(f"{self.names[seat]} folded.")
                continue
            if call:
                paid = self.commit(seat, call)
                self.history.append(f"{self.names[seat]} called {paid}g.")
            player_to_new_bet = self.current_bet + self.bet_size - self.street_contributions[0]
            if (
                confidence > 78 + len(self.board) * 10
                and self.stacks[seat] >= self.bet_size
                and self.stacks[0] >= player_to_new_bet
            ):
                target = self.current_bet + self.bet_size
                paid = self.commit(seat, target - self.street_contributions[seat])
                self.current_bet = self.street_contributions[seat]
                self.history.append(f"{self.names[seat]} raised {paid}g.")

    def ai_respond_to_raise(self, difficulty: str) -> None:
        caution = {"Friendly": 24, "Practiced": 15, "Expert": 8}.get(difficulty, 15)
        for seat in range(1, 4):
            if self.folded[seat] or self.stacks[seat] <= 0:
                continue
            call = self.call_cost(seat)
            if not call:
                continue
            confidence = self.confidence(seat) + self.rng.randint(-caution, caution)
            if confidence < 52 + len(self.board) * 8:
                self.folded[seat] = True
                self.history.append(f"{self.names[seat]} folded to the raise.")
            else:
                paid = self.commit(seat, call)
                self.history.append(f"{self.names[seat]} called {paid}g.")

    def player_fold(self) -> None:
        self.folded[0] = True
        self.history.append("You folded.")

    def player_call(self) -> int:
        paid = self.commit(0, self.call_cost(0))
        self.history.append(f"You {'called ' + str(paid) + 'g' if paid else 'checked'}.")
        return paid

    def player_raise(self) -> int:
        target = self.current_bet + self.bet_size
        paid = self.commit(0, target - self.street_contributions[0])
        self.current_bet = self.street_contributions[0]
        self.history.append(f"You raised {paid}g.")
        return paid

    def showdown(self) -> Dict[str, object]:
        active = self.active_seats()
        if len(active) == 1:
            winners = active
            ranks: Dict[int, Tuple[int, ...]] = {}
        else:
            ranks = {seat: poker_best_rank(self.holes[seat] + self.board) for seat in active}
            best = max(ranks.values())
            winners = [seat for seat in active if ranks[seat] == best]
        shares = {seat: 0 for seat in range(4)}
        share, remainder = divmod(self.pot, len(winners))
        for seat in winners:
            shares[seat] = share
        shares[winners[0]] += remainder
        return {"winners": winners, "ranks": ranks, "shares": shares, "pot": self.pot}


class HoldemMixin:
    HOLDEM_MIN_BUYIN = 20
    HOLDEM_MAX_BUYIN = 1000

    def ensure_holdem_state(self) -> None:
        stats = getattr(self.state, "tavern_holdem_stats", None)
        if not isinstance(stats, dict):
            stats = {}
        cleaned = {}
        for key, default in HOLDEM_STATS_DEFAULTS.items():
            try:
                value = int(stats.get(key, default) or 0)
            except (TypeError, ValueError):
                value = default
            cleaned[key] = value if key == "net_winnings" else max(0, value)
        self.state.tavern_holdem_stats = cleaned

    @staticmethod
    def holdem_card_text(card: Card) -> str:
        return colorize(f"{card[0]}{card_suit_glyph(card[1])}", card_color(card))

    def holdem_cards_text(self, cards: Sequence[Card]) -> str:
        return " ".join(self.holdem_card_text(card) for card in cards) or "(none)"

    @staticmethod
    def holdem_rules_lines() -> List[str]:
        return [
            "TEXAS HOLD'EM", "",
            "- Four players receive two private hole cards. Five community cards are revealed across the flop, turn, and river.",
            "- Make the strongest five-card poker hand from any combination of your hole cards and the community cards.",
            "- Hands rank: High Card, Pair, Two Pair, Three of a Kind, Straight, Flush, Full House, Four of a Kind, Straight Flush.",
            "- Every seat antes. Betting uses a fixed limit based on the selected table buy-in.",
            "- Check when nothing is owed, call the current bet, raise by the table limit, or fold.",
            "- The selected buy-in is your maximum possible loss. Chips not committed to the pot return after the hand.",
            "- A winner receives the pot; exact ties split it. X/Escape safely folds.",
            "- Friendly, Practiced, and Expert tables change how accurately opponents value and defend their hands.",
            "- Hearts and Diamonds are red; Clubs and Spades are white. Hidden opponent cards use face-down cards.",
            "- Choose with W/S, arrows, or number keys. F folds, C checks/calls, and R raises when available.",
        ]

    def holdem_stats_lines(self) -> List[str]:
        self.ensure_holdem_state()
        stats = self.state.tavern_holdem_stats
        hands = int(stats["hands_played"])
        return [
            "TEXAS HOLD'EM RECORD", "",
            f"Hands: {hands}",
            f"Wins: {stats['wins']} | Losses: {stats['losses']} | Ties: {stats['ties']}",
            f"Showdowns: {stats['showdowns']} | Folds: {stats['folds']}",
            f"Total buy-ins: {stats['total_buyins']}g",
            f"Net winnings: {int(stats['net_winnings']):+d}g",
            f"Biggest pot won: {stats['biggest_pot']}g",
            f"Best made hand: {POKER_CATEGORY_NAMES[min(8, int(stats['best_hand_category']))]}",
            f"Best winning streak: {stats['best_streak']}",
        ]

    def _draw_holdem_table(self, game: HoldemRound, difficulty: str, selected: int, actions: Sequence[Tuple[str, str]]) -> None:
        clear_screen()
        minigame_title(
            f"Texas Hold'em - {game.street}",
            f"{difficulty} table | Pot {game.pot}g | Your chips {game.stacks[0]}g",
        )
        minigame_section("Community cards")
        print_card_rows(game.board, max_per_row=5, indent="  ")
        minigame_section("Your hand")
        print_card_rows(game.holes[0], max_per_row=2, indent="  ")
        if len(game.board) >= 3:
            rank = poker_best_rank(game.holes[0] + game.board)
            print(f"Current hand: {poker_rank_name(rank)}")
        minigame_section("Opponents", "Mara | Rowan | Silas")
        opponent_cards = [card for seat in range(1, 4) for card in game.holes[seat]]
        print_card_rows(
            opponent_cards,
            hidden=[True] * len(opponent_cards),
            max_per_row=6,
            indent="  ",
        )
        for seat in range(1, 4):
            status = "folded" if game.folded[seat] else f"{game.stacks[seat]} chips"
            print(f"{game.names[seat]}: {status} | committed {game.contributions[seat]}g")
        minigame_section("Betting actions")
        minigame_actions(actions, selected)
        minigame_notice(
            " | ".join(game.history[-4:]) if game.history else "Choose a betting action.",
            prefix="RECENT",
        )
        minigame_controls(
            "W/S or arrows: choose",
            "1-3: direct action",
            "Z/Enter/Space: confirm",
            "F: fold",
            "C: check/call",
            "R: raise",
            "X/Esc: fold",
        )

    def _holdem_player_bet(self, game: HoldemRound, difficulty: str) -> None:
        selected = 0
        while not game.folded[0]:
            call = game.call_cost(0)
            actions: List[Tuple[str, str]] = [("fold", "Fold")]
            actions.append(("call", f"Call {call}g" if call else "Check"))
            raise_cost = call + game.bet_size
            if game.stacks[0] >= raise_cost:
                actions.append(("raise", f"Raise to {game.current_bet + game.bet_size}g"))
            selected = min(selected, len(actions) - 1)
            self._draw_holdem_table(game, difficulty, selected, actions)
            key = normalize_key(read_key())
            if key in {"x", "\x1b", "q"}:
                action = "fold"
            elif key == "f":
                action = "fold"
            elif key == "c":
                action = "call"
            elif key == "r" and any(value == "raise" for value, _label in actions):
                action = "raise"
            elif key in {"w", "UP", "LEFT"}:
                selected = (selected - 1) % len(actions)
                continue
            elif key in {"s", "DOWN", "RIGHT"}:
                selected = (selected + 1) % len(actions)
                continue
            elif key.isdigit() and 1 <= int(key) <= len(actions):
                action = actions[int(key) - 1][0]
            elif key in MENU_CONFIRM_KEYS:
                action = actions[selected][0]
            else:
                continue
            if action == "fold":
                game.player_fold()
            elif action == "call":
                game.player_call()
                game.ai_respond_to_raise(difficulty)
            else:
                game.player_raise()
                game.ai_respond_to_raise(difficulty)
            return

    def _record_holdem_result(self, buy_in: int, payout: int, result: Dict[str, object], game: HoldemRound) -> None:
        self.ensure_holdem_state()
        stats = self.state.tavern_holdem_stats
        profit = int(payout) - int(buy_in)
        stats["hands_played"] += 1
        stats["total_buyins"] += int(buy_in)
        stats["net_winnings"] += profit
        if game.folded[0]:
            stats["folds"] += 1
        else:
            stats["showdowns"] += 1
            if len(game.board) >= 3:
                rank = poker_best_rank(game.holes[0] + game.board)
                stats["best_hand_category"] = max(stats["best_hand_category"], int(rank[0]))
        winners = result["winners"]
        if 0 in winners and len(winners) == 1:
            stats["wins"] += 1
            stats["pots_won"] += 1
            stats["biggest_pot"] = max(stats["biggest_pot"], int(result["pot"]))
            stats["current_streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
        elif 0 in winners:
            stats["ties"] += 1
        else:
            stats["losses"] += 1
            stats["current_streak"] = 0

    def _show_holdem_result(self, game: HoldemRound, result: Dict[str, object], payout: int, buy_in: int) -> None:
        clear_screen()
        print(colorize("TEXAS HOLD'EM - SHOWDOWN", C.UI_TITLE))
        print("Community cards:")
        print_card_rows(game.board, max_per_row=5, indent="  ")
        print("")
        for seat in result["winners"] if len(result["winners"]) == 1 else game.active_seats():
            rank = result["ranks"].get(seat)
            label = poker_rank_name(rank) if rank else "Last player standing"
            print(f"{game.names[seat]}: {label}")
            print_card_rows(game.holes[seat], max_per_row=2, indent="  ")
        winners = ", ".join(game.names[seat] for seat in result["winners"])
        print(f"\nPot: {result['pot']}g | Winner(s): {winners}")
        print(f"Returned chips and winnings: {payout}g | Hand result: {payout - buy_in:+d}g")
        print("Press any key to leave the table.")
        read_key()

    def play_holdem_hand(self, buy_in: int, difficulty: str, venue: str = "Tavern", show_result: bool = True) -> Optional[Dict[str, object]]:
        self.ensure_holdem_state()
        buy_in = int(buy_in)
        if not self.HOLDEM_MIN_BUYIN <= buy_in <= self.HOLDEM_MAX_BUYIN or int(self.state.money) < buy_in:
            self.set_message("That Texas Hold'em buy-in is unavailable.")
            return None
        self.state.money -= buy_in
        rng = random.Random(
            int(getattr(self.state, "wilderness_seed", 0))
            + int(getattr(self.state, "absolute_day", 0)) * 8191
            + int(getattr(self.state, "hour", 0)) * 131
            + buy_in
        )
        game = HoldemRound(buy_in, rng)
        difficulty = difficulty if difficulty in {"Friendly", "Practiced", "Expert"} else "Practiced"
        for street_index in range(4):
            game.ai_open_betting(difficulty)
            if 0 not in game.active_seats() or len(game.active_seats()) == 1:
                break
            if game.stacks[0] > 0:
                self._holdem_player_bet(game, difficulty)
            if game.folded[0] or len(game.active_seats()) == 1:
                break
            if game.stacks[0] <= 0:
                break
            if street_index < 3:
                game.reveal_next_street()
        while len(game.board) < 5 and len(game.active_seats()) > 1:
            game.reveal_next_street()
        result = game.showdown()
        payout = int(game.stacks[0]) + int(result["shares"].get(0, 0))
        self.state.money += payout
        self._record_holdem_result(buy_in, payout, result, game)
        self.advance_time(15)
        if show_result:
            self._show_holdem_result(game, result, payout, buy_in)
        self.autosave_with_message(
            f"Finished Texas Hold'em at {venue}: {payout - buy_in:+d}g."
        )
        return {"game": game, "result": result, "payout": payout, "profit": payout - buy_in}

    def holdem_buyin_menu(self, venue: str, difficulty: str) -> Optional[int]:
        presets = (20, 50, 100, 250, 500, 1000)
        while True:
            items = [
                MenuItem(label=f"Buy in for {amount}g", value=str(amount), enabled=int(self.state.money) >= amount)
                for amount in presets
            ]
            items.extend([
                MenuItem(label="Rules", value="rules", enabled=True),
                MenuItem(label="Playing record", value="stats", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(
                f"{venue} - {difficulty} Hold'em", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return None
            if choice.value == "rules":
                self.vertical_panel_view("Texas Hold'em Rules", self.holdem_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "stats":
                self.vertical_panel_view("Texas Hold'em Record", self.holdem_stats_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            return int(choice.value)

    def holdem_menu(self, venue: str = "Tavern") -> None:
        while True:
            items = [
                MenuItem(label="Friendly table", value="Friendly", enabled=True, hint="loose, unpredictable opponents"),
                MenuItem(label="Practiced table", value="Practiced", enabled=True, hint="balanced opponents"),
                MenuItem(label="Expert table", value="Expert", enabled=True, hint="careful hand valuation"),
                MenuItem(label="Rules", value="rules", enabled=True),
                MenuItem(label="Playing record", value="stats", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                f"{venue} - Texas Hold'em", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                self.set_message("Left the Texas Hold'em table.")
                return
            if choice.value == "rules":
                self.vertical_panel_view("Texas Hold'em Rules", self.holdem_rules_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "stats":
                self.vertical_panel_view("Texas Hold'em Record", self.holdem_stats_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            buy_in = self.holdem_buyin_menu(venue, str(choice.value))
            if buy_in is not None:
                self.play_holdem_hand(buy_in, str(choice.value), venue)
