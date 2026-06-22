from __future__ import annotations

import sys
from typing import Dict, Optional

from .game import Game
from .models import Unit, Weapon
from .rendering import clear_screen, show_cursor
from .results import BattleRequest, BattleResult, battle_result_from_game
from .validation import format_validation_report, validate_all_content


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _farmstead_player_profile(request: BattleRequest) -> dict:
    if request.source != "ascii_farmstead":
        return {}
    context = request.return_context if isinstance(request.return_context, dict) else {}
    profile = context.get("farm_player", {})
    return dict(profile) if isinstance(profile, dict) else {}


def _farmstead_party_limit(request: BattleRequest) -> int:
    if request.source != "ascii_farmstead":
        return 4
    context = request.return_context if isinstance(request.return_context, dict) else {}
    return max(1, min(4, _safe_int(context.get("farm_party_limit", 4), 4)))


def _farmstead_party_tactic(request: BattleRequest) -> str:
    if request.source != "ascii_farmstead":
        return "Balanced"
    context = request.return_context if isinstance(request.return_context, dict) else {}
    tactic = str(context.get("farm_party_tactic", "Balanced") or "Balanced")
    return tactic if tactic in {"Balanced", "Aggressive", "Cautious", "Support"} else "Balanced"


def _farmstead_context(request: BattleRequest) -> dict:
    if request.source != "ascii_farmstead":
        return {}
    context = request.return_context if isinstance(request.return_context, dict) else {}
    return dict(context)


def _farmstead_frame_delay(request: BattleRequest) -> float:
    """Use a snappier animation cadence for combat launched from the farm game."""
    if request.source != "ascii_farmstead":
        return 0.10
    context = _farmstead_context(request)
    requested_delay = _safe_float(context.get("farm_combat_frame_delay", 0.025), 0.025)
    return max(0.0, min(0.10, requested_delay))


def _clean_int_dict(value: object) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    clean: Dict[str, int] = {}
    for key, raw_amount in value.items():
        name = str(key or "").strip()
        if not name:
            continue
        amount = max(0, _safe_int(raw_amount, 0))
        if amount:
            clean[name] = amount
    return clean


def _farmstead_runtime_progress(value: object):
    if isinstance(value, dict):
        return {str(key): _farmstead_runtime_progress(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_farmstead_runtime_progress(item) for item in value]
    return value


def _farmstead_progression_payload(profile: dict) -> dict:
    payload = profile.get("progression", {}) if isinstance(profile, dict) else {}
    return _farmstead_runtime_progress(payload) if isinstance(payload, dict) else {}


def _normalize_farmstead_progress_sets(progress: dict) -> None:
    for field_name in ("class_unlocks", "unlocked_gear"):
        buckets = progress.get(field_name, {})
        if not isinstance(buckets, dict):
            progress[field_name] = {}
            continue
        for key, values in list(buckets.items()):
            if isinstance(values, set):
                continue
            if isinstance(values, (list, tuple)):
                buckets[key] = set(values)
            elif values:
                buckets[key] = {values}
            else:
                buckets[key] = set()


def _merge_farmstead_progression(progress: dict, profile: dict) -> None:
    payload = _farmstead_progression_payload(profile)
    if not payload:
        _normalize_farmstead_progress_sets(progress)
        return
    for key, value in payload.items():
        if key in {"custom_base_stats", "custom_inventory", "custom_base_weapon"}:
            continue
        progress[str(key)] = value
    _normalize_farmstead_progress_sets(progress)


def _apply_farmstead_campaign_state(game: Game, request: BattleRequest) -> None:
    context = _farmstead_context(request)
    if not context:
        return
    game.campaign_inventory.update(_clean_int_dict(context.get("farm_combat_campaign_inventory", {})))
    game.item_loadout_bonus.update(_clean_int_dict(context.get("farm_combat_item_loadout_bonus", {})))


def _farmstead_companion_profiles(request: BattleRequest) -> list:
    if request.source != "ascii_farmstead":
        return []
    context = request.return_context if isinstance(request.return_context, dict) else {}
    companions = context.get("farm_companions", [])
    if not isinstance(companions, list):
        return []
    clean = []
    seen = set()
    for profile in companions:
        if not isinstance(profile, dict):
            continue
        item = dict(profile)
        name = _clean_farmstead_name(item.get("battle_id") or item.get("name") or "")
        if not name or name in seen:
            continue
        item["name"] = name
        item["battle_id"] = name
        clean.append(item)
        seen.add(name)
    return clean[: max(0, _farmstead_party_limit(request) - 1)]


def _clean_farmstead_name(value: object) -> str:
    cleaned = " ".join(str(value or "Farmer").strip().split())
    return cleaned[:16] or "Farmer"


def _apply_farmstead_player_to_game(game: Game, request: BattleRequest) -> str:
    profile = _farmstead_player_profile(request)
    if not profile:
        return ""

    player_name = _clean_farmstead_name(profile.get("name", "Farmer"))
    hero = next((unit for unit in game.heroes if unit.name == player_name), None)
    if hero is None:
        hero = next((unit for unit in game.heroes if unit.name == "Rook"), game.heroes[0])

    old_name = hero.name
    if old_name != player_name:
        old_progress = game.party_progress.pop(old_name, {}) if isinstance(getattr(game, "party_progress", {}), dict) else {}
        hero.name = player_name
        game.party_progress[player_name] = old_progress if isinstance(old_progress, dict) else {}

    game.farmstead_player_name = player_name
    game.party_limit = _farmstead_party_limit(request)
    game.active_party_names = {player_name}
    game.manual_companion_names = {player_name}
    hero.ai_controlled = False
    hero.glyph = "@"
    hero.role = "farmstead"

    max_hp = max(1, _safe_int(profile.get("base_max_hp", profile.get("max_hp")), 34))
    max_focus = max(0, _safe_int(profile.get("base_max_focus", profile.get("max_focus")), 8))
    attack = max(1, _safe_int(profile.get("base_attack", profile.get("attack")), 5))
    hp_ceiling = max(max_hp, _safe_int(profile.get("max_hp"), max_hp))
    focus_ceiling = max(max_focus, _safe_int(profile.get("max_focus"), max_focus))
    hp = max(1, min(hp_ceiling, _safe_int(profile.get("current_hp"), hp_ceiling)))
    focus = max(0, min(focus_ceiling, _safe_int(profile.get("focus"), focus_ceiling)))
    defense = max(0, _safe_int(profile.get("defense"), 0))
    weapon_name = str(profile.get("weapon", "Rusty Sword") or "Rusty Sword")
    range_min = max(1, _safe_int(profile.get("weapon_range_min"), 1))
    range_max = max(range_min, _safe_int(profile.get("weapon_range_max"), range_min))
    level = max(1, _safe_int(profile.get("level"), 1))
    exp = max(0, _safe_int(profile.get("exp"), 0))
    items = profile.get("combat_items", {})
    inventory = {str(k): max(0, _safe_int(v, 0)) for k, v in items.items()} if isinstance(items, dict) else {}

    progress = game.party_progress.setdefault(player_name, {})
    requested_class = str(profile.get("starting_class", "Vanguard") or "Vanguard")
    if requested_class not in game.class_names():
        requested_class = "Vanguard"
    progress.update({
        "level": level,
        "xp": exp,
        "hp_bonus": _safe_int(progress.get("hp_bonus"), 0),
        "mp_bonus": _safe_int(progress.get("mp_bonus"), 0),
        "damage_bonus": _safe_int(progress.get("damage_bonus"), 0),
        "skill_points": max(0, _safe_int(profile.get("skill_points"), 0)),
        "class": requested_class,
        "subclass": "Fire",
        "color": str(profile.get("color", "White") or "White"),
        "custom_base_weapon": weapon_name,
        "custom_base_stats": {
            "max_hp": max_hp,
            "max_mp": max_focus,
            "weapon_damage": attack,
            "move_range": 5,
        },
        "custom_inventory": dict(inventory),
        "equipped_gear": {"weapon": weapon_name, "armor": "Traveler Clothes", "charm": "Plain Charm"},
        "unlocked_gear": {"weapon": {weapon_name}, "armor": {"Traveler Clothes"}, "charm": {"Plain Charm"}},
    })
    _merge_farmstead_progression(progress, profile)
    if str(progress.get("class", "")) not in game.class_names():
        progress["class"] = requested_class
    progress.update({
        "level": level,
        "xp": exp,
        "color": str(profile.get("color", "White") or "White"),
        "custom_base_weapon": weapon_name,
        "custom_base_stats": {
            "max_hp": max_hp,
            "max_mp": max_focus,
            "weapon_damage": attack,
            "move_range": 5,
        },
        "custom_inventory": dict(inventory),
    })
    progress.setdefault("equipped_gear", {"weapon": weapon_name, "armor": "Traveler Clothes", "charm": "Plain Charm"})
    progress.setdefault("unlocked_gear", {"weapon": {weapon_name}, "armor": {"Traveler Clothes"}, "charm": {"Plain Charm"}})
    _normalize_farmstead_progress_sets(progress)

    hp_bonus = _safe_int(progress.get("hp_bonus"), 0)
    mp_bonus = _safe_int(progress.get("mp_bonus"), 0)
    damage_bonus = _safe_int(progress.get("damage_bonus"), 0)
    hero.level = level
    hero.xp = exp
    hero.max_hp = max(1, max_hp + hp_bonus)
    hero.hp = max(0, min(hero.max_hp, hp))
    hero.max_mp = max(0, max_focus + mp_bonus)
    hero.mp = max(0, min(hero.max_mp, focus))
    hero.defense = defense
    hero.move_range = 5
    hero.weapon = Weapon(weapon_name, max(1, attack + damage_bonus), range_min, range_max)
    hero.inventory = inventory
    game.apply_equipment_to_hero(hero)
    hero.hp = max(0, min(hero.max_hp, hp))
    hero.mp = max(0, min(hero.max_mp, focus))
    return player_name


def _farmstead_companion_inventory(profile: dict) -> dict:
    items = profile.get("inventory", profile.get("combat_items", {}))
    return {str(k): max(0, _safe_int(v, 0)) for k, v in items.items()} if isinstance(items, dict) else {}


def _farmstead_find_or_create_companion(game: Game, name: str, reserved_names: set) -> Unit:
    existing = next((unit for unit in game.heroes if unit.name == name), None)
    if existing is not None:
        return existing

    fallback = next(
        (
            unit for unit in game.heroes
            if unit.team == "hero" and unit.name not in reserved_names and unit.name not in game.active_party_names
        ),
        None,
    )
    if fallback is None:
        fallback = next((unit for unit in game.heroes if unit.team == "hero" and unit.name not in reserved_names), None)
    if fallback is None:
        start = game.start_positions.get("Rook", (2, 2))
        fallback = Unit(name, "@", start, 34, 34, 10, 10, 5, Weapon("Iron Saber", 4), "hero", ai_controlled=True)
        game.heroes.append(fallback)
        game.party_progress[name] = {}
        return fallback

    old_name = fallback.name
    old_progress = game.party_progress.pop(old_name, {}) if isinstance(getattr(game, "party_progress", {}), dict) else {}
    game.active_party_names.discard(old_name)
    game.manual_companion_names.discard(old_name)
    game.custom_companion_names.discard(old_name)
    fallback.name = name
    game.party_progress[name] = old_progress if isinstance(old_progress, dict) else {}
    return fallback


def _apply_farmstead_companion_to_unit(game: Game, hero: Unit, profile: dict) -> str:
    name = _clean_farmstead_name(profile.get("battle_id") or profile.get("name") or hero.name)
    hero.name = name
    game.custom_companion_names.add(name)

    max_hp = max(1, _safe_int(profile.get("max_hp"), 34))
    hp = max(1, min(max_hp, _safe_int(profile.get("current_hp"), max_hp)))
    max_focus = max(0, _safe_int(profile.get("max_focus"), 10))
    focus = max(0, min(max_focus, _safe_int(profile.get("focus"), max_focus)))
    attack = max(1, _safe_int(profile.get("attack"), 4))
    defense = max(0, _safe_int(profile.get("defense"), 0))
    move_range = max(1, _safe_int(profile.get("move_range"), 5))
    weapon_name = str(profile.get("weapon", "Iron Saber") or "Iron Saber")
    range_min = max(1, _safe_int(profile.get("weapon_range_min"), 1))
    range_max = max(range_min, _safe_int(profile.get("weapon_range_max"), range_min))
    level = max(1, _safe_int(profile.get("level"), 1))
    inventory = _farmstead_companion_inventory(profile)

    progress = game.party_progress.setdefault(name, {})
    progress.update({
        "level": level,
        "xp": _safe_int(progress.get("xp"), 0),
        "hp_bonus": _safe_int(progress.get("hp_bonus"), 0),
        "mp_bonus": _safe_int(progress.get("mp_bonus"), 0),
        "damage_bonus": _safe_int(progress.get("damage_bonus"), 0),
        "skill_points": max(2, _safe_int(progress.get("skill_points"), 2)),
        "class": str(profile.get("class", "Vanguard") or "Vanguard"),
        "subclass": str(profile.get("subclass", "Fire") or "Fire"),
        "color": str(profile.get("color", "Cyan") or "Cyan"),
        "custom_base_weapon": weapon_name,
        "custom_base_stats": {
            "max_hp": max_hp,
            "max_mp": max_focus,
            "weapon_damage": attack,
            "move_range": move_range,
        },
        "custom_inventory": dict(inventory),
        "equipped_gear": {"weapon": weapon_name, "armor": "Traveler Clothes", "charm": "Plain Charm"},
        "unlocked_gear": {"weapon": {weapon_name}, "armor": {"Traveler Clothes"}, "charm": {"Plain Charm"}},
    })
    _merge_farmstead_progression(progress, profile)
    progress.update({
        "custom_base_weapon": weapon_name,
        "custom_base_stats": {
            "max_hp": max_hp,
            "max_mp": max_focus,
            "weapon_damage": attack,
            "move_range": move_range,
        },
        "custom_inventory": dict(inventory),
    })
    progress.setdefault("equipped_gear", {"weapon": weapon_name, "armor": "Traveler Clothes", "charm": "Plain Charm"})
    progress.setdefault("unlocked_gear", {"weapon": {weapon_name}, "armor": {"Traveler Clothes"}, "charm": {"Plain Charm"}})
    _normalize_farmstead_progress_sets(progress)

    progress_level = max(level, _safe_int(progress.get("level"), level))
    progress_xp = max(0, _safe_int(progress.get("xp"), 0))
    hp_bonus = _safe_int(progress.get("hp_bonus"), 0)
    mp_bonus = _safe_int(progress.get("mp_bonus"), 0)
    damage_bonus = _safe_int(progress.get("damage_bonus"), 0)

    hero.glyph = "@"
    hero.team = "hero"
    hero.role = str(profile.get("role", "farmstead_companion") or "farmstead_companion")
    hero.ai_controlled = not bool(profile.get("manual_control", False))
    hero.active = True
    hero.level = progress_level
    hero.xp = progress_xp
    hero.max_hp = max(1, max_hp + hp_bonus)
    hero.hp = max(0, min(hero.max_hp, hp))
    hero.max_mp = max(0, max_focus + mp_bonus)
    hero.mp = max(0, min(hero.max_mp, focus))
    hero.defense = defense
    hero.move_range = move_range
    hero.weapon = Weapon(weapon_name, max(1, attack + damage_bonus), range_min, range_max)
    hero.inventory = inventory
    game.apply_equipment_to_hero(hero)
    hero.hp = max(0, min(hero.max_hp, hp))
    hero.mp = max(0, min(hero.max_mp, focus))
    return name


def _apply_farmstead_companions_to_game(game: Game, request: BattleRequest, player_name: str) -> list:
    profiles = _farmstead_companion_profiles(request)
    if request.source != "ascii_farmstead":
        return []
    game.party_limit = _farmstead_party_limit(request)
    game.follower_tactic = _farmstead_party_tactic(request)
    names = []
    manual_names = {player_name} if player_name else set()
    reserved = {player_name} if player_name else set()
    for profile in profiles:
        companion_name = _clean_farmstead_name(profile.get("battle_id") or profile.get("name") or "")
        if not companion_name or companion_name == player_name or companion_name in names:
            continue
        hero = _farmstead_find_or_create_companion(game, companion_name, reserved | set(names))
        name = _apply_farmstead_companion_to_unit(game, hero, profile)
        names.append(name)
        game.active_party_names.add(name)
        if bool(profile.get("manual_control", False)):
            manual_names.add(name)
    if player_name:
        game.active_party_names.add(player_name)
        game.manual_companion_names = manual_names
    game.enforce_party_limit()
    return names


def configure_game_from_request(game: Game, request: BattleRequest) -> Game:
    """Apply an overworld-style BattleRequest to a Game instance.

    This maps request fields onto existing setup state without changing combat
    rules. Player-facing request battles do not expose developer arena resets.
    """

    game.current_battle_request = request
    game.battle_request_id = request.request_id
    game.battle_source = request.source
    game.frame_delay = _farmstead_frame_delay(request)
    game.battle_return_context = dict(request.return_context)
    game.battle_world_flags = dict(request.world_flags)
    game.allow_battle_map_selection = bool(request.is_debug)
    game.current_mission_id = str(request.mission_id or "")
    _apply_farmstead_campaign_state(game, request)

    if request.map_name:
        for index, (name, _grid, _positions) in enumerate(game.maps):
            if name == request.map_name:
                game.map_index = index
                game.main_menu_index = index
                break
    elif request.map_id is not None and game.maps:
        requested_map_id = _safe_int(request.map_id, game.map_index)
        game.map_index = max(0, min(requested_map_id, len(game.maps) - 1))
        game.main_menu_index = game.map_index

    game.map_name, game.map, game.start_positions = game.maps[game.map_index]
    farmstead_player_name = _apply_farmstead_player_to_game(game, request)
    _apply_farmstead_companions_to_game(game, request, farmstead_player_name)

    requested_party = list(request.party_ids or request.party_members)
    if requested_party:
        valid_party_names = {hero.name for hero in game.heroes}
        mapped_party = [
            farmstead_player_name if farmstead_player_name and str(name) == "Rook" else str(name)
            for name in requested_party
        ]
        game.active_party_names = {name for name in mapped_party if name in valid_party_names}
        game.enforce_party_limit()

    enemy_names = request.requested_enemy_names()
    if enemy_names:
        game.set_custom_counts_from_enemy_names(enemy_names)
        selected_enemies = game.selected_custom_enemy_names()
        if selected_enemies:
            game.custom_encounter_enabled = True
            game.active_enemy_names = set(selected_enemies)

    requested_objective = request.objective or "Defeat All"
    game.objective_mode = requested_objective if requested_objective in game.objective_modes() else "Defeat All"
    params = request.objective_params if isinstance(request.objective_params, dict) else {}
    game.objective_round_goal = max(1, _safe_int(params.get("round_goal"), game.objective_round_goal))
    game.objective_hold_goal = max(1, _safe_int(params.get("hold_goal"), game.objective_hold_goal))
    game.objective_object_goal = max(1, _safe_int(params.get("object_goal"), game.objective_object_goal))
    game.current_mission_name = str(request.mission_name or "")
    game.current_mission_reward_theme = str(request.reward_theme or "")
    game.reset_battle_positions()
    if farmstead_player_name:
        _apply_farmstead_player_to_game(game, request)
        _apply_farmstead_companions_to_game(game, request, farmstead_player_name)
        game.apply_companion_control_settings()
        game.cursor = game.selected_hero.pos
    briefing = str(request.return_context.get("encounter_briefing", "") or "")
    if briefing:
        game.messages = [briefing, f"Objective: {game.objective_mode} on {game.map_name}."]
        game.combat_log = []
        game.combat_log_scroll = 0
        game.add_combat_log_entry(briefing, category="BATTLE")
    return game


def create_game(request: Optional[BattleRequest] = None) -> Game:
    game = Game()
    if request is not None:
        configure_game_from_request(game, request)
    return game


def run_battle_request(request: Optional[BattleRequest] = None) -> BattleResult:
    game = create_game(request)
    game.in_main_menu = request is None
    game.run()
    result = game.game_over() or ("fled" if game.should_quit else "fled")
    return battle_result_from_game(game, result, request)


def main() -> None:
    if "--validate-content" in sys.argv:
        report = validate_all_content(Game())
        print(format_validation_report(report))
        raise SystemExit(0 if report.ok else 1)

    try:
        Game().run()
    except KeyboardInterrupt:
        show_cursor()
        clear_screen()
        print("Exited combat prototype.")
