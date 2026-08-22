"""Shared tavern minigames, beginning with a complete blackjack table."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

from ascii_farmstead_data import (
    LEFT_PANEL_HEIGHT,
    LEFT_PANEL_WIDTH,
    MENU_BACK,
    MENU_CONFIRM_KEYS,
)
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
BLACKJACK_RANKS: Tuple[str, ...] = (
    "A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K",
)
BLACKJACK_SUITS: Tuple[str, ...] = ("S", "H", "D", "C")
BLACKJACK_CUT_CARD_REMAINING = 15
BLACKJACK_STAT_DEFAULTS: Dict[str, int] = {
    "rounds_played": 0,
    "hands_played": 0,
    "wins": 0,
    "losses": 0,
    "pushes": 0,
    "naturals": 0,
    "net_winnings": 0,
    "biggest_win": 0,
    "biggest_loss": 0,
    "current_streak": 0,
    "best_streak": 0,
}


def make_blackjack_deck(rng: Optional[random.Random] = None) -> List[Card]:
    deck = [(rank, suit) for suit in BLACKJACK_SUITS for rank in BLACKJACK_RANKS]
    (rng or random.Random()).shuffle(deck)
    return deck


def blackjack_rank_value(rank: str) -> int:
    if rank == "A":
        return 11
    if rank in {"J", "Q", "K"}:
        return 10
    return int(rank)


def blackjack_hand_value(cards: Sequence[Card]) -> Tuple[int, bool]:
    total = sum(blackjack_rank_value(str(rank)) for rank, _suit in cards)
    aces = sum(1 for rank, _suit in cards if rank == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    soft = aces > 0 and total <= 21
    return total, soft


def blackjack_is_natural(cards: Sequence[Card]) -> bool:
    return len(cards) == 2 and blackjack_hand_value(cards)[0] == 21


def blackjack_split_value(card: Card) -> int:
    return blackjack_rank_value(card[0])


class BlackjackShoe:
    """One physical deck shared by consecutive rounds at a table sitting."""

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        cut_card_remaining: int = BLACKJACK_CUT_CARD_REMAINING,
    ):
        self.rng = rng or random.Random()
        self.cut_card_remaining = max(8, min(24, int(cut_card_remaining)))
        self.deck: List[Card] = make_blackjack_deck(self.rng)
        self.discard: List[Card] = []
        self.shuffle_count = 1
        self.rounds_dealt = 0

    @property
    def cards_remaining(self) -> int:
        return len(self.deck)

    @property
    def cards_seen(self) -> int:
        return 52 - len(self.deck)

    @property
    def needs_shuffle(self) -> bool:
        return self.rounds_dealt > 0 and len(self.deck) <= self.cut_card_remaining

    def reshuffle(self) -> None:
        cards = list(self.deck) + list(self.discard)
        if len(cards) != 52:
            raise ValueError("A Blackjack shoe must contain exactly 52 cards between rounds.")
        self.rng.shuffle(cards)
        self.deck[:] = cards
        self.discard.clear()
        self.shuffle_count += 1

    def prepare_round(self) -> bool:
        reshuffled = self.needs_shuffle
        if reshuffled:
            self.reshuffle()
        return reshuffled

    def start_round(self) -> None:
        self.rounds_dealt += 1

    def draw(self) -> Card:
        if not self.deck:
            raise RuntimeError("The Blackjack shoe ran out of cards during a round.")
        return self.deck.pop(0)

    def finish_round(self, round_state: "BlackjackRound") -> None:
        if round_state.returned_to_shoe:
            return
        cards = list(round_state.dealer_cards)
        for hand in round_state.player_hands:
            cards.extend(hand["cards"])
        self.discard.extend(cards)
        round_state.returned_to_shoe = True
        if len(self.deck) + len(self.discard) != 52:
            raise ValueError("The Blackjack shoe lost or duplicated a card.")


class BlackjackRound:
    """UI-independent blackjack state used by the tavern table and regressions."""

    def __init__(
        self,
        wager: int,
        rng: Optional[random.Random] = None,
        deck: Optional[Sequence[Card]] = None,
        shoe: Optional[BlackjackShoe] = None,
    ):
        if deck is not None and shoe is not None:
            raise ValueError("Choose either an injected deck or a shared Blackjack shoe.")
        self.shoe = shoe
        self.deck: List[Card] = (
            shoe.deck if shoe is not None
            else list(deck) if deck is not None
            else make_blackjack_deck(rng)
        )
        self.dealer_cards: List[Card] = []
        self.player_hands: List[Dict[str, object]] = [{
            "cards": [],
            "wager": max(1, int(wager)),
            "finished": False,
            "split_hand": False,
            "doubled": False,
        }]
        self.dealer_revealed = False
        self.returned_to_shoe = False
        self._deal_opening_cards()

    def draw(self) -> Card:
        if self.shoe is not None:
            return self.shoe.draw()
        if not self.deck:
            self.deck = make_blackjack_deck()
        return self.deck.pop(0)

    @property
    def cards_remaining(self) -> int:
        return self.shoe.cards_remaining if self.shoe is not None else len(self.deck)

    def _deal_opening_cards(self) -> None:
        hand = self.player_hands[0]
        cards = hand["cards"]
        cards.append(self.draw())
        self.dealer_cards.append(self.draw())
        cards.append(self.draw())
        self.dealer_cards.append(self.draw())
        if blackjack_is_natural(cards) or blackjack_is_natural(self.dealer_cards):
            hand["finished"] = True

    def hand_cards(self, hand_index: int) -> List[Card]:
        return self.player_hands[hand_index]["cards"]

    def hand_value(self, hand_index: int) -> Tuple[int, bool]:
        return blackjack_hand_value(self.hand_cards(hand_index))

    def hand_active(self, hand_index: int) -> bool:
        return not bool(self.player_hands[hand_index].get("finished"))

    def can_double(self, hand_index: int) -> bool:
        hand = self.player_hands[hand_index]
        return self.hand_active(hand_index) and len(hand["cards"]) == 2

    def can_split(self, hand_index: int) -> bool:
        if len(self.player_hands) >= 4 or not self.hand_active(hand_index):
            return False
        cards = self.hand_cards(hand_index)
        return (
            len(cards) == 2
            and blackjack_split_value(cards[0]) == blackjack_split_value(cards[1])
        )

    def hit(self, hand_index: int) -> Card:
        if not self.hand_active(hand_index):
            raise ValueError("That blackjack hand is already finished.")
        card = self.draw()
        hand = self.player_hands[hand_index]
        hand["cards"].append(card)
        total, _soft = self.hand_value(hand_index)
        if total >= 21:
            hand["finished"] = True
        return card

    def stand(self, hand_index: int) -> None:
        self.player_hands[hand_index]["finished"] = True

    def double(self, hand_index: int) -> Card:
        if not self.can_double(hand_index):
            raise ValueError("This hand cannot double down.")
        hand = self.player_hands[hand_index]
        hand["wager"] = int(hand["wager"]) * 2
        hand["doubled"] = True
        card = self.draw()
        hand["cards"].append(card)
        hand["finished"] = True
        return card

    def split(self, hand_index: int) -> None:
        if not self.can_split(hand_index):
            raise ValueError("This hand cannot be split.")
        hand = self.player_hands[hand_index]
        cards = hand["cards"]
        second_card = cards.pop()
        original_wager = int(hand["wager"])
        hand["split_hand"] = True
        new_hand: Dict[str, object] = {
            "cards": [second_card],
            "wager": original_wager,
            "finished": False,
            "split_hand": True,
            "doubled": False,
        }
        cards.append(self.draw())
        new_hand["cards"].append(self.draw())
        self.player_hands.insert(hand_index + 1, new_hand)
        split_aces = cards[0][0] == "A" and new_hand["cards"][0][0] == "A"
        if split_aces:
            hand["finished"] = True
            new_hand["finished"] = True
        else:
            if blackjack_hand_value(cards)[0] >= 21:
                hand["finished"] = True
            if blackjack_hand_value(new_hand["cards"])[0] >= 21:
                new_hand["finished"] = True

    def all_player_hands_finished(self) -> bool:
        return all(bool(hand.get("finished")) for hand in self.player_hands)

    def dealer_play(self) -> None:
        self.dealer_revealed = True
        contestable_hands = [
            hand
            for hand in self.player_hands
            if blackjack_hand_value(hand["cards"])[0] <= 21
            and not (
                blackjack_is_natural(hand["cards"])
                and not bool(hand.get("split_hand"))
            )
        ]
        if not contestable_hands:
            return
        while True:
            total, _soft = blackjack_hand_value(self.dealer_cards)
            if total >= 17:
                return
            self.dealer_cards.append(self.draw())

    def settle(self) -> List[Dict[str, object]]:
        if not self.all_player_hands_finished():
            raise ValueError("Player action is not complete.")
        self.dealer_play()
        dealer_total, _dealer_soft = blackjack_hand_value(self.dealer_cards)
        dealer_natural = blackjack_is_natural(self.dealer_cards)
        results: List[Dict[str, object]] = []
        for hand in self.player_hands:
            cards = hand["cards"]
            total, _soft = blackjack_hand_value(cards)
            wager = int(hand["wager"])
            natural = blackjack_is_natural(cards) and not bool(hand.get("split_hand"))
            if total > 21:
                outcome, payout = "loss", 0
            elif dealer_natural:
                outcome, payout = ("push", wager) if natural else ("loss", 0)
            elif natural:
                outcome, payout = "blackjack", wager * 5 // 2
            elif dealer_total > 21 or total > dealer_total:
                outcome, payout = "win", wager * 2
            elif total < dealer_total:
                outcome, payout = "loss", 0
            else:
                outcome, payout = "push", wager
            results.append({
                "outcome": outcome,
                "wager": wager,
                "payout": payout,
                "profit": payout - wager,
                "player_total": total,
                "dealer_total": dealer_total,
                "natural": natural,
            })
        return results


class TavernGamesMixin:
    """Tavern-facing menus, rendering, persistence, and payouts."""

    BLACKJACK_MIN_WAGER = 10
    BLACKJACK_MAX_WAGER = 1000

    def ensure_tavern_game_state(self) -> None:
        stats = getattr(self.state, "tavern_blackjack_stats", None)
        if not isinstance(stats, dict):
            stats = {}
        cleaned: Dict[str, int] = {}
        for key, default in BLACKJACK_STAT_DEFAULTS.items():
            try:
                value = int(stats.get(key, default) or 0)
            except (TypeError, ValueError):
                value = default
            if key not in {"net_winnings"}:
                value = max(0, value)
            cleaned[key] = value
        self.state.tavern_blackjack_stats = cleaned

    def blackjack_stats_lines(self) -> List[str]:
        self.ensure_tavern_game_state()
        stats = self.state.tavern_blackjack_stats
        hands = int(stats["hands_played"])
        wins = int(stats["wins"])
        win_rate = (wins / hands * 100.0) if hands else 0.0
        return [
            "BLACKJACK RECORD",
            "",
            f"Rounds played: {stats['rounds_played']}",
            f"Hands settled: {hands}",
            f"Wins: {wins} | Losses: {stats['losses']} | Pushes: {stats['pushes']}",
            f"Natural blackjacks: {stats['naturals']}",
            f"Win rate: {win_rate:.1f}%",
            f"Net winnings: {int(stats['net_winnings']):+d}g",
            f"Biggest win: +{stats['biggest_win']}g",
            f"Biggest loss: -{stats['biggest_loss']}g",
            f"Best winning streak: {stats['best_streak']}",
            "",
            "Splitting can settle more than one hand during a single round.",
        ]

    @staticmethod
    def blackjack_rules_lines() -> List[str]:
        return [
            "TAVERN BLACKJACK",
            "",
            "- Reach 21 without going over. Number cards use their value; face cards are 10.",
            "- Aces count as 11 unless that would bust the hand, then they count as 1.",
            "- A natural blackjack is an Ace plus a ten-value card in the opening hand.",
            "- Ordinary wins pay 1:1. Natural blackjack pays 3:2, with fractional gold rounded down. Equal totals push.",
            "- The dealer draws to 16 and stands on every 17, including soft 17.",
            "- Double Down doubles the wager, deals exactly one card, and then stands.",
            "- Equal-value opening cards can be split, up to four hands. Each split costs another wager.",
            "- Split Aces receive one additional card each. A split 21 is an ordinary 21, not a natural.",
            "- Hearts and Diamonds are shown in red; Clubs and Spades are shown in white.",
            "- One shuffled 52-card deck persists for the entire table sitting. Consecutive rounds consume its remaining cards.",
            "- The wager menu and table show how many cards remain, allowing the exposed cards to be counted between rounds.",
            "- At 15 or fewer remaining cards, the dealer reshuffles before the next wager. Leaving the table also ends that shoe.",
            "- Choose actions with W/S or arrows, number keys, or H for Hit, D for Double, and P for Split.",
            "- B/X/Escape/Q/Tab during player action safely stands; it never abandons a wager.",
            "- Wagers use only in-game gold and are capped at 1,000g per initial hand.",
        ]

    @staticmethod
    def blackjack_card_text(card: Card) -> str:
        rank, suit = card
        return colorize(f"{rank}{card_suit_glyph(suit)}", card_color(card))

    def blackjack_cards_text(self, cards: Sequence[Card], hide_hole: bool = False) -> str:
        rendered: List[str] = []
        for index, card in enumerate(cards):
            if hide_hole and index == 1:
                rendered.append("[hidden]")
                continue
            text = self.blackjack_card_text(card)
            rendered.append(text)
        return " ".join(rendered)

    def _draw_blackjack_table(
        self,
        round_state: BlackjackRound,
        venue: str,
        hand_index: int,
        actions: Sequence[Tuple[str, str]],
        selected: int,
        note: str = "",
        reveal_dealer: bool = False,
    ) -> None:
        clear_screen()
        shoe_status = (
            f" | Single deck: {round_state.cards_remaining} cards remain"
            if round_state.shoe is not None
            else ""
        )
        minigame_title(
            f"{venue} - Blackjack",
            f"Gold {int(self.state.money)}g{shoe_status}",
        )
        dealer_cards = round_state.dealer_cards
        minigame_section("Dealer", "revealed" if reveal_dealer else "hole card hidden")
        print_card_rows(
            dealer_cards,
            hidden=[False, not reveal_dealer] + [False] * max(0, len(dealer_cards) - 2),
            max_per_row=7,
            indent="  ",
        )
        if reveal_dealer:
            dealer_total, dealer_soft = blackjack_hand_value(dealer_cards)
            print(f"  Total: {dealer_total}{' soft' if dealer_soft else ''}")
        else:
            print(f"  Showing: {blackjack_rank_value(dealer_cards[0][0])}")
        minigame_section("Your hands")
        for index, hand in enumerate(round_state.player_hands):
            cards = hand["cards"]
            total, soft = blackjack_hand_value(cards)
            marker = ">" if index == hand_index else " "
            status = "bust" if total > 21 else "stood" if hand.get("finished") else "playing"
            print(
                f"{marker} Hand {index + 1} ({int(hand['wager'])}g): "
                f"{total}{' soft' if soft else ''} [{status}]"
            )
            if index == hand_index:
                print_card_rows(cards, max_per_row=7, indent="  ")
            else:
                print(f"  {self.blackjack_cards_text(cards)}")
        minigame_notice(note or "Choose how to play the highlighted hand.")
        minigame_section("Actions")
        minigame_actions(actions, selected)
        minigame_controls(
            "W/S or arrows: choose",
            "1-4: direct action",
            "Z/Enter/Space: confirm",
            "H: hit",
            "D: double",
            "P: split",
            "B/X/Esc/Q/Tab: stand",
        )

    def _blackjack_player_action(
        self, round_state: BlackjackRound, hand_index: int, venue: str,
    ) -> None:
        selected = 0
        note = ""
        while round_state.hand_active(hand_index):
            hand = round_state.player_hands[hand_index]
            wager = int(hand["wager"])
            actions: List[Tuple[str, str]] = [("hit", "Hit"), ("stand", "Stand")]
            if round_state.can_double(hand_index) and int(self.state.money) >= wager:
                actions.append(("double", f"Double Down (+{wager}g)"))
            if round_state.can_split(hand_index) and int(self.state.money) >= wager:
                actions.append(("split", f"Split Hand (+{wager}g)"))
            selected = min(selected, len(actions) - 1)
            self._draw_blackjack_table(
                round_state, venue, hand_index, actions, selected, note=note,
            )
            key = normalize_key(read_key())
            if key in {"b", "x", "\x1b", "q", "\t"}:
                round_state.stand(hand_index)
                return
            shortcut = {"h": "hit", "d": "double", "p": "split"}.get(key)
            if shortcut and any(value == shortcut for value, _label in actions):
                action = shortcut
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

            if action == "hit":
                card = round_state.hit(hand_index)
                note = f"Drew {self.blackjack_card_text(card)}."
            elif action == "stand":
                round_state.stand(hand_index)
                return
            elif action == "double":
                self.state.money -= wager
                card = round_state.double(hand_index)
                note = f"Paid {wager}g to double and drew {self.blackjack_card_text(card)}."
                return
            elif action == "split":
                self.state.money -= wager
                round_state.split(hand_index)
                note = f"Paid {wager}g to split into two hands."

    def record_blackjack_results(self, results: Sequence[Dict[str, object]]) -> None:
        self.ensure_tavern_game_state()
        stats = self.state.tavern_blackjack_stats
        stats["rounds_played"] += 1
        for result in results:
            outcome = str(result.get("outcome", "loss"))
            profit = int(result.get("profit", 0) or 0)
            stats["hands_played"] += 1
            stats["net_winnings"] += profit
            if outcome in {"win", "blackjack"}:
                stats["wins"] += 1
                stats["current_streak"] += 1
                stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
                stats["biggest_win"] = max(stats["biggest_win"], profit)
                if outcome == "blackjack":
                    stats["naturals"] += 1
            elif outcome == "loss":
                stats["losses"] += 1
                stats["current_streak"] = 0
                stats["biggest_loss"] = max(stats["biggest_loss"], -profit)
            else:
                stats["pushes"] += 1

    def _show_blackjack_result(
        self,
        round_state: BlackjackRound,
        venue: str,
        results: Sequence[Dict[str, object]],
    ) -> None:
        clear_screen()
        print(colorize(f"{venue.upper()} - RESULTS", C.UI_TITLE))
        if round_state.shoe is not None:
            print(
                f"Single deck: {round_state.cards_remaining} cards remain | "
                f"{round_state.shoe.cards_seen} seen since the shuffle"
            )
        dealer_total, dealer_soft = blackjack_hand_value(round_state.dealer_cards)
        print("")
        print("Dealer:")
        print_card_rows(round_state.dealer_cards, max_per_row=7, indent="  ")
        print(f"Dealer total: {dealer_total}{' soft' if dealer_soft else ''}")
        print("")
        labels = {
            "blackjack": "Natural blackjack",
            "win": "Win",
            "loss": "Loss",
            "push": "Push",
        }
        for index, (hand, result) in enumerate(zip(round_state.player_hands, results)):
            cards = hand["cards"]
            outcome = str(result["outcome"])
            profit = int(result["profit"])
            print(f"Hand {index + 1}:")
            print_card_rows(cards, max_per_row=7, indent="  ")
            print(f"  Total: {result['player_total']}")
            print(
                f"  {labels.get(outcome, outcome.title())} | "
                f"Wager {result['wager']}g | {profit:+d}g"
            )
        print("")
        total_profit = sum(int(result["profit"]) for result in results)
        print(f"Round result: {total_profit:+d}g | Current gold: {int(self.state.money)}g")
        print("Press any key to return to the table.")
        read_key()

    def play_blackjack_round(
        self,
        wager: int,
        venue: str = "Tavern",
        round_state: Optional[BlackjackRound] = None,
        show_result: bool = True,
        shoe: Optional[BlackjackShoe] = None,
    ) -> Optional[List[Dict[str, object]]]:
        self.ensure_tavern_game_state()
        wager = int(wager)
        if wager < self.BLACKJACK_MIN_WAGER or wager > self.BLACKJACK_MAX_WAGER:
            self.set_message("Blackjack wagers must be between 10g and 1,000g.")
            return None
        if int(self.state.money) < wager:
            self.set_message(f"You need {wager}g to place that wager.")
            return None
        if round_state is not None and shoe is not None:
            self.set_message("That Blackjack round cannot replace the table's active shoe.")
            return None
        self.state.money -= wager
        if shoe is not None:
            shoe.start_round()
        game_round = round_state or BlackjackRound(wager, shoe=shoe)
        if int(game_round.player_hands[0]["wager"]) != wager:
            self.state.money += wager
            self.set_message("That blackjack table had an invalid wager.")
            return None

        hand_index = 0
        while hand_index < len(game_round.player_hands):
            if game_round.hand_active(hand_index):
                self._blackjack_player_action(game_round, hand_index, venue)
            hand_index += 1
        results = game_round.settle()
        if shoe is not None:
            shoe.finish_round(game_round)
        payout = sum(int(result["payout"]) for result in results)
        self.state.money += payout
        self.record_blackjack_results(results)
        self.advance_time(10 + max(0, len(results) - 1) * 2)
        if show_result:
            self._show_blackjack_result(game_round, venue, results)
        total_profit = sum(int(result["profit"]) for result in results)
        self.autosave_with_message(
            f"Finished blackjack at {venue}: {total_profit:+d}g across {len(results)} hand(s)."
        )
        return results

    def blackjack_wager_menu(
        self,
        venue: str,
        shoe: Optional[BlackjackShoe] = None,
        freshly_shuffled: bool = False,
    ) -> Optional[int]:
        presets = (10, 25, 50, 100, 250, 500, 1000)
        items: List[MenuItem] = []
        if shoe is not None:
            items.append(MenuItem(
                label=f"Single deck: {shoe.cards_remaining} cards remain",
                value="shoe_status",
                enabled=False,
                hint=(
                    "dealer just shuffled; the count reset"
                    if freshly_shuffled
                    else f"{shoe.cards_seen} cards exposed since the shuffle"
                ),
            ))
        items.extend([
            MenuItem(
                label=f"Wager {amount}g",
                value=str(amount),
                enabled=int(self.state.money) >= amount,
                hint="next hand from the current deck",
            )
            for amount in presets
        ])
        items.extend([
            MenuItem(
                label="Choose chip wager",
                value="custom",
                enabled=int(self.state.money) >= self.BLACKJACK_MIN_WAGER,
                hint="10g increments, up to 1,000g",
            ),
            MenuItem(label="Rules", value="rules", enabled=True),
            MenuItem(label="Playing record", value="stats", enabled=True),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ])
        while True:
            choice = self.vertical_panel_select(
                f"{venue} - Blackjack",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return None
            if choice.value == "rules":
                self.vertical_panel_view(
                    "Blackjack Rules",
                    self.blackjack_rules_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "stats":
                self.vertical_panel_view(
                    "Blackjack Record",
                    self.blackjack_stats_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "custom":
                max_chips = min(
                    self.BLACKJACK_MAX_WAGER // 10,
                    int(self.state.money) // 10,
                )
                quantity = self.vertical_quantity_select(
                    "Choose Blackjack Wager",
                    "10g chip",
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

    def blackjack_table_menu(self, venue: str = "Tavern") -> None:
        shoe = BlackjackShoe()
        freshly_shuffled = True
        while True:
            if shoe.prepare_round():
                freshly_shuffled = True
                self.set_message("The dealer gathered the discards and reshuffled the single deck.")
            wager = self.blackjack_wager_menu(
                venue,
                shoe=shoe,
                freshly_shuffled=freshly_shuffled,
            )
            if wager is None:
                self.set_message("Left the blackjack table.")
                return
            freshly_shuffled = False
            self.play_blackjack_round(wager, venue, shoe=shoe)
