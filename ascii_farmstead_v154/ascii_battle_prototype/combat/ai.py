from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from .models import Pos, Unit
from .utils import manhattan

ENDING_ACTIONS = {
    "attack", "barrel", "poison", "charge", "intimidate", "root", "spore",
    "pack_pounce", "harry", "spore_patch", "briar_bloom", "elite_drive",
    "needle_dash", "cinder_toss", "frost_cloud", "burrow_ambush",
    "quill_volley", "ooze_mire", "shield_wall", "phase_shot", "briar_heart",
}

FULL_AP_ACTIONS = {
    "charge", "spore", "spore_patch", "briar_bloom", "elite_drive", "harry",
    "needle_dash", "cinder_toss", "frost_cloud", "burrow_ambush",
    "quill_volley", "ooze_mire", "shield_wall", "phase_shot", "briar_heart",
}


def enemy_ap_budget(enemy: Unit) -> int:
    if enemy.role in {"skirmisher", "controller", "ranged", "pouncer", "blighter", "boss"}:
        return 2
    if enemy.role in {"brute", "guardian"}:
        return 1
    return 1


def enemy_action_ends_sequence(kind: str) -> bool:
    return kind in ENDING_ACTIONS


def enemy_action_cost(enemy: Unit, kind: str) -> int:
    if kind in FULL_AP_ACTIONS:
        return max(1, enemy.action_points)
    return 1


def nearby_ally_count(hero: Unit, heroes: Iterable[Unit], radius: int) -> int:
    return sum(1 for ally in heroes if ally is not hero and manhattan(ally.pos, hero.pos) <= radius)


def enemy_target_score(enemy: Unit, hero: Unit, heroes: Iterable[Unit], estimated_damage: int) -> int:
    heroes = list(heroes)
    distance = manhattan(enemy.pos, hero.pos)
    hp_missing = hero.max_hp - hero.hp
    score = 0

    score += hp_missing
    score += 35 if hero.hp <= estimated_damage else 0
    score += 22 if hero.hp <= hero.max_hp * 0.35 else 0
    score += 12 if hero.vulnerable > 0 else 0
    score -= 7 if hero.guard else 0
    score -= distance * 2

    if not hero.ai_controlled:
        score += 4
    elif hero.hp <= hero.max_hp * 0.5:
        score += 8

    if enemy.role == "skirmisher":
        score += 18 if hero.poison <= 0 else -8
        score += 10 if hero.ai_controlled else 0
        score -= 8 if distance <= 1 else 0
    elif enemy.role == "brute":
        score += 16 if hero.vulnerable > 0 else 0
        score += 8 if not hero.ai_controlled else 0
        score -= 4 if distance > 4 else 0
    elif enemy.role == "controller":
        score += hero.action_points * 5
        score += 18 if hero.rooted <= 0 else -10
        score += nearby_ally_count(hero, heroes, 2) * 8
    elif enemy.role == "ranged":
        score += 12 if hero.hp <= hero.max_hp * 0.5 else 0
        score -= 10 if distance <= 1 else 0
    elif enemy.role == "pouncer":
        score += 14 if hero.hp <= hero.max_hp * 0.55 else 0
        score -= nearby_ally_count(hero, heroes, 1) * 6
    elif enemy.role == "guardian":
        score += 10 if not hero.ai_controlled else 0
        score += 10 if hero.vulnerable <= 0 else 0
    elif enemy.role == "blighter":
        score += 16 if hero.poison <= 0 else -6
        score += nearby_ally_count(hero, heroes, 2) * 6
    elif enemy.role == "boss":
        score += 18 if hero.rooted <= 0 else 0
        score += 16 if hero.vulnerable <= 0 else 0
        score += nearby_ally_count(hero, heroes, 2) * 10

    return score


def choose_best_enemy_move(
    enemy: Unit,
    target: Optional[Unit],
    reachable: List[Pos],
    heroes: List[Unit],
    watched_tiles: Set[Pos],
    enemy_best_target: Callable[[Unit], Optional[Unit]],
    enemy_target_score_fn: Callable[[Unit, Unit], int],
    terrain_score_for_unit: Callable[[Unit, Pos, bool], int],
    movement_cost: Callable[[Pos], int],
    ally_spacing_score: Callable[[Unit, Pos], int],
    congestion_escape_bonus: Callable[[Unit, Pos], int],
    progress_to_attack_band: Callable[[Unit, Pos, Optional[Unit], Optional[int], Optional[int]], int],
    movement_progress_bonus: Callable[[Unit, Pos, Optional[Unit], Optional[int], Optional[int]], int],
    preferred_min: Optional[int] = None,
    preferred_max: Optional[int] = None,
    cautious: bool = True,
) -> Pos:
    if not reachable:
        return enemy.pos

    preferred_min = enemy.weapon.range_min if preferred_min is None else preferred_min
    preferred_max = enemy.weapon.range_max if preferred_max is None else preferred_max
    risk_cache: Dict[Pos, int] = {}
    primary_target = target or enemy_best_target(enemy)
    current_progress = (
        progress_to_attack_band(enemy, enemy.pos, primary_target, preferred_min, preferred_max)
        if primary_target else 0
    )

    def cheap_overwatch_risk(pos: Pos) -> int:
        if not watched_tiles:
            return 0
        if pos in risk_cache:
            return risk_cache[pos]
        risk = 1 if pos in watched_tiles else 0
        risk_cache[pos] = risk
        return risk

    def attack_score_from(pos: Pos) -> int:
        best = 0
        for hero in heroes:
            d = manhattan(pos, hero.pos)
            if preferred_min <= d <= preferred_max:
                damage = enemy.weapon.damage + (1 if hero.vulnerable > 0 else 0)
                value = damage * 4 + enemy_target_score_fn(enemy, hero)
                if hero.hp <= damage:
                    value += 40
                best = max(best, value)
        return best

    def score(pos: Pos) -> Tuple[int, int, int, int, int, int, int]:
        nearest_target = primary_target or enemy_best_target(enemy)
        target_dist = manhattan(pos, nearest_target.pos) if nearest_target else 0
        in_preferred = preferred_min <= target_dist <= preferred_max if nearest_target else False
        risk = cheap_overwatch_risk(pos)
        risk_penalty = risk * (45 if cautious else 16)
        terrain = terrain_score_for_unit(enemy, pos, cautious)
        progress = movement_progress_bonus(enemy, pos, nearest_target, preferred_min, preferred_max) if nearest_target else 0
        return (
            attack_score_from(pos),
            28 if in_preferred else 0,
            progress,
            terrain - movement_cost(pos),
            ally_spacing_score(enemy, pos),
            congestion_escape_bonus(enemy, pos),
            -risk_penalty - target_dist,
        )

    best = max(reachable, key=score)
    if best == enemy.pos and primary_target and current_progress > 0:
        alternatives = [p for p in reachable if p != enemy.pos]
        if alternatives:
            best_alt = max(alternatives, key=score)
            if (
                progress_to_attack_band(enemy, best_alt, primary_target, preferred_min, preferred_max) < current_progress
                or score(best_alt)[2] > -10
            ):
                best = best_alt
    return best
