from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .constants import PASSABLE
from .results import BattleRequest, BattleResult, normalize_outcome


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    context: str = ""


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add(self, severity: str, code: str, message: str, context: str = "") -> None:
        self.issues.append(ValidationIssue(severity, code, message, context))

    def extend(self, other: "ValidationReport") -> None:
        self.issues.extend(other.issues)

    def grouped(self) -> Dict[str, List[ValidationIssue]]:
        grouped: Dict[str, List[ValidationIssue]] = {}
        for issue in self.issues:
            grouped.setdefault(issue.severity, []).append(issue)
        return grouped


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _positive_int(value: object) -> Tuple[int, bool]:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return 0, False
    return amount, amount > 0


def _map_lookup(game: object) -> Dict[str, Tuple[int, str, List[List[str]], Dict[str, Tuple[int, int]]]]:
    return {
        name: (index, name, grid, positions)
        for index, (name, grid, positions) in enumerate(getattr(game, "maps", []))
    }


def _tile_in_grid(grid: Sequence[Sequence[str]], pos: Tuple[int, int]) -> bool:
    x, y = pos
    return 0 <= y < len(grid) and 0 <= x < len(grid[y])


def _passable_tiles(grid: Sequence[Sequence[str]]) -> List[Tuple[int, int]]:
    tiles: List[Tuple[int, int]] = []
    for y, row in enumerate(grid):
        for x, tile in enumerate(row):
            if tile in PASSABLE:
                tiles.append((x, y))
    return tiles


def _validate_objective_geometry(
    report: ValidationReport,
    objective: str,
    params: Mapping[str, object],
    map_name: str,
    grid: Sequence[Sequence[str]],
) -> None:
    passable_count = len(_passable_tiles(grid))
    if objective in ("Escape", "Hold Zone") and passable_count < 1:
        report.add("error", "objective.no_passable_tiles", f"{objective} needs at least one passable tile.", map_name)
    if objective == "Destroy Objects":
        object_goal = _safe_int(params.get("object_goal"), 1)
        if passable_count < object_goal:
            report.add(
                "error",
                "objective.too_many_objects",
                f"Destroy Objects asks for {object_goal} objects but only {passable_count} passable tiles exist.",
                map_name,
            )


def validate_map_content(
    game: object,
    map_name: Optional[str] = None,
    objective: Optional[str] = None,
) -> ValidationReport:
    report = ValidationReport()
    records = _map_lookup(game)
    selected = [records[map_name]] if map_name in records else list(records.values())

    if map_name and map_name not in records:
        report.add("error", "map.unknown", f"Map '{map_name}' is not defined.", map_name)
        return report
    if not records:
        report.add("error", "map.none", "No maps are defined.")
        return report

    for _index, name, grid, positions in selected:
        if not grid:
            report.add("error", "map.empty", "Map has no rows.", name)
            continue
        if any(not row for row in grid):
            report.add("error", "map.empty_row", "Map contains an empty row.", name)

        widths = {len(row) for row in grid}
        if len(widths) > 1:
            report.add("warning", "map.ragged", "Map rows have different widths.", name)

        passable = _passable_tiles(grid)
        if not passable:
            report.add("error", "map.no_passable_tiles", "Map has no passable tiles.", name)

        hero_spawns = [spawn for spawn in ("Rook", "Mira", "Brom", "Aria") if spawn in positions]
        if not hero_spawns:
            report.add("error", "map.no_hero_spawn", "Map does not define a known hero spawn.", name)

        for label, pos in positions.items():
            if not isinstance(pos, tuple) or len(pos) != 2:
                report.add("error", "map.bad_spawn", f"Spawn '{label}' is not an (x, y) tuple.", name)
                continue
            if not _tile_in_grid(grid, pos):
                report.add("error", "map.spawn_oob", f"Spawn '{label}' is outside the map at {pos}.", name)
                continue
            x, y = pos
            if grid[y][x] not in PASSABLE:
                report.add("error", "map.spawn_blocked", f"Spawn '{label}' is on blocked tile '{grid[y][x]}'.", name)

        if objective:
            _validate_objective_geometry(report, objective, {}, name, grid)

    return report


def validate_enemy_content(game: object, referenced_enemies: Optional[Iterable[str]] = None) -> ValidationReport:
    report = ValidationReport()
    names = list(referenced_enemies if referenced_enemies is not None else getattr(game, "enemy_roster_names")())
    if not names:
        report.add("error", "enemy.none", "No enemies are defined.")
        return report

    seen = set()
    for raw_name in names:
        name = str(raw_name)
        if not name or name in seen:
            continue
        seen.add(name)
        enemy = getattr(game, "enemy_by_name")(name)
        if not enemy:
            report.add("error", "enemy.unknown", f"Enemy '{name}' is not defined.", name)
            continue
        base_name = getattr(game, "enemy_base_name")(name)
        if getattr(game, "enemy_is_elite_name")(name) and base_name in getattr(game, "boss_enemy_names", set()):
            report.add("error", "enemy.elite_boss", f"Boss enemy '{base_name}' cannot also be requested as elite.", name)
        if int(getattr(enemy, "max_hp", 0)) < 1:
            report.add("error", "enemy.bad_hp", f"Enemy '{name}' has non-positive max HP.", name)
        weapon = getattr(enemy, "weapon", None)
        if weapon is None:
            report.add("error", "enemy.no_weapon", f"Enemy '{name}' has no weapon.", name)
        else:
            if int(getattr(weapon, "damage", 0)) < 0:
                report.add("error", "enemy.bad_damage", f"Enemy '{name}' has negative weapon damage.", name)
            if int(getattr(weapon, "range_min", 0)) < 0:
                report.add("error", "enemy.bad_range", f"Enemy '{name}' has a negative minimum range.", name)
            if int(getattr(weapon, "range_max", 0)) < int(getattr(weapon, "range_min", 0)):
                report.add("error", "enemy.bad_range", f"Enemy '{name}' max range is below min range.", name)
        if int(getattr(enemy, "move_range", 0)) < 0:
            report.add("error", "enemy.bad_move", f"Enemy '{name}' has negative move range.", name)
        if not str(getattr(enemy, "role", "")):
            report.add("warning", "enemy.no_role", f"Enemy '{name}' has no role tag.", name)

    return report


def validate_objective_content(
    game: object,
    objective: str,
    params: Optional[Mapping[str, object]] = None,
    map_name: Optional[str] = None,
) -> ValidationReport:
    report = ValidationReport()
    objective = str(objective or "Defeat All")
    if params is None:
        params = {}
    elif not isinstance(params, Mapping):
        report.add("error", "objective.bad_params", "Objective params must be a dictionary.", objective)
        params = {}
    modes = getattr(game, "objective_modes")()
    if objective not in modes:
        report.add("error", "objective.unknown", f"Objective '{objective}' is not supported.", objective)
        return report

    required_params = {
        "Survive": "round_goal",
        "Hold Zone": "hold_goal",
        "Destroy Objects": "object_goal",
    }
    key = required_params.get(objective)
    if key:
        value, valid = _positive_int(params.get(key))
        if key not in params:
            report.add("error", "objective.missing_param", f"{objective} needs '{key}'.", objective)
        elif not valid:
            report.add("error", "objective.bad_param", f"{objective} has invalid '{key}' value {params.get(key)!r}.", objective)
        elif objective == "Survive" and value < 2:
            report.add("warning", "objective.short_survive", "Survive is usually at least 2 rounds.", objective)

    records = _map_lookup(game)
    selected_map = map_name or str(getattr(game, "map_name", ""))
    if selected_map in records:
        _index, name, grid, _positions = records[selected_map]
        _validate_objective_geometry(report, objective, params, name, grid)
    elif selected_map:
        report.add("error", "objective.unknown_map", f"Objective references unknown map '{selected_map}'.", objective)

    return report


def _known_reward_themes(game: object) -> set:
    themes = {str(preset.get("theme", "")) for preset in getattr(game, "mission_presets")()}
    themes.update(str(theme[0]) for theme in getattr(game, "mission_enemy_themes")())
    return {theme for theme in themes if theme}


def validate_reward_content(
    game: object,
    reward_theme: Optional[str] = None,
    rewards: Optional[Mapping[str, object]] = None,
) -> ValidationReport:
    report = ValidationReport()
    known_keys = set(getattr(game, "loot_keys", []))
    known_keys.update(getattr(game, "item_loadout_bonus", {}).keys())
    known_keys.update(item.name for item in getattr(game, "items", []))

    if reward_theme:
        known_themes = _known_reward_themes(game)
        if reward_theme not in known_themes:
            report.add("warning", "reward.unknown_theme", f"Reward theme '{reward_theme}' is not one of the built-in themes.", reward_theme)

    for key, raw_amount in (rewards or {}).items():
        amount = _safe_int(raw_amount, -1)
        if amount < 0:
            report.add("error", "reward.bad_amount", f"Reward '{key}' has invalid amount {raw_amount!r}.", str(key))
        if str(key) not in known_keys:
            report.add("warning", "reward.unknown_key", f"Reward key '{key}' is not in the built-in loot/item list.", str(key))

    return report


def validate_mission_preset(game: object, preset: Mapping[str, object]) -> ValidationReport:
    report = ValidationReport()
    name = str(preset.get("name", ""))
    if not name:
        report.add("error", "mission.no_name", "Mission preset is missing a name.")

    map_name = str(preset.get("map", ""))
    if not map_name:
        report.add("error", "mission.no_map", "Mission preset is missing a map.", name)
    else:
        report.extend(validate_map_content(game, map_name))

    enemies = list(preset.get("enemies", []))
    if not enemies:
        report.add("error", "mission.no_enemies", "Mission preset has no enemies.", name)
    else:
        report.extend(validate_enemy_content(game, enemies))

    objective = str(preset.get("objective", "Defeat All"))
    params = {key: preset[key] for key in ("round_goal", "hold_goal", "object_goal") if key in preset}
    report.extend(validate_objective_content(game, objective, params, map_name))
    report.extend(validate_reward_content(game, str(preset.get("theme", "")) or None))
    return report


def validate_battle_request(game: object, request: BattleRequest) -> ValidationReport:
    report = ValidationReport()
    debug_like = bool(request.is_debug or request.source == "debug")
    records = _map_lookup(game)

    if request.map_name:
        if request.map_name not in records:
            report.add("error", "request.unknown_map", f"Request references unknown map '{request.map_name}'.", request.request_id)
    elif request.map_id is not None:
        map_id = _safe_int(request.map_id, -1)
        if map_id < 0 or map_id >= len(records):
            report.add("error", "request.bad_map_id", f"Request map_id {request.map_id!r} is out of range.", request.request_id)
    elif not debug_like:
        report.add("error", "request.no_map", "Non-debug request must specify map_name or map_id.", request.request_id)

    party = list(request.party_ids or request.party_members)
    hero_names = {hero.name for hero in getattr(game, "heroes", [])}
    if not party and not debug_like:
        report.add("error", "request.no_party", "Non-debug request must include at least one party id.", request.request_id)
    if len(party) > int(getattr(game, "party_limit", 4)):
        report.add("error", "request.party_too_large", "Request party exceeds the active party limit.", request.request_id)
    for name in party:
        if name not in hero_names:
            report.add("error", "request.unknown_party", f"Request references unknown party member '{name}'.", request.request_id)

    for name, count in request.enemy_counts.items():
        amount, valid = _positive_int(count)
        if not valid:
            report.add("error", "request.bad_enemy_count", f"Enemy count for '{name}' must be positive; got {count!r}.", request.request_id)
        elif amount > int(getattr(game, "custom_enemy_total_cap", amount)):
            report.add("warning", "request.high_enemy_count", f"Enemy count for '{name}' exceeds the encounter cap.", request.request_id)

    requested_enemies = request.requested_enemy_names()
    if not requested_enemies and not debug_like:
        report.add("error", "request.no_enemies", "Non-debug request must include at least one enemy.", request.request_id)
    if requested_enemies:
        report.extend(validate_enemy_content(game, requested_enemies))

    objective_map = request.map_name
    if not objective_map and request.map_id is not None:
        map_id = _safe_int(request.map_id, -1)
        if 0 <= map_id < len(getattr(game, "maps", [])):
            objective_map = getattr(game, "maps")[map_id][0]
    report.extend(validate_objective_content(game, request.objective, request.objective_params, objective_map or None))

    if not isinstance(request.return_context, dict):
        report.add("error", "request.bad_context", "return_context must be a dictionary.", request.request_id)
    if not isinstance(request.world_flags_on_victory, list) or not isinstance(request.world_flags_on_defeat, list):
        report.add("error", "request.bad_flags", "world flag hooks must be lists.", request.request_id)

    return report


def validate_battle_result(result: BattleResult) -> ValidationReport:
    report = ValidationReport()
    outcome = normalize_outcome(result.outcome)
    if outcome not in {"victory", "defeat", "fled", "abandoned"}:
        report.add("error", "result.bad_outcome", f"Unsupported battle result outcome '{result.outcome}'.", result.request_id)
    if not result.request_id:
        report.add("error", "result.no_request_id", "BattleResult is missing request_id.")
    if not isinstance(result.party_status, dict):
        report.add("error", "result.bad_party_status", "party_status must be a dictionary.", result.request_id)
    if not isinstance(result.world_flags, list):
        report.add("error", "result.bad_world_flags", "world_flags must be a list.", result.request_id)
    for key, amount in result.loot.items():
        if _safe_int(amount, -1) < 0:
            report.add("error", "result.bad_loot", f"Loot '{key}' has invalid amount {amount!r}.", result.request_id)
    return report


def validate_all_content(game: Optional[object] = None) -> ValidationReport:
    if game is None:
        from .game import Game

        game = Game()

    report = ValidationReport()
    report.extend(validate_map_content(game))
    report.extend(validate_enemy_content(game))
    report.extend(validate_reward_content(game))
    for preset in getattr(game, "mission_presets")():
        report.extend(validate_mission_preset(game, preset))

    for builder_name in (
        "create_battle_request_from_selected_setup",
        "create_battle_request_from_mission",
        "create_battle_request_from_encounter_builder",
    ):
        builder = getattr(game, builder_name, None)
        if not callable(builder):
            continue
        if builder_name == "create_battle_request_from_mission":
            presets = getattr(game, "mission_presets")()
            if presets:
                report.extend(validate_battle_request(game, builder(presets[0])))
        elif builder_name == "create_battle_request_from_encounter_builder":
            names = getattr(game, "enemy_roster_names")()
            if names:
                getattr(game, "increase_custom_enemy_by_name")(names[0])
                report.extend(validate_battle_request(game, builder()))
        else:
            report.extend(validate_battle_request(game, builder()))

    return report


def format_validation_report(report: ValidationReport) -> str:
    lines = ["Content validation: OK" if report.ok else "Content validation: issues found"]
    if not report.issues:
        lines.append("No issues found.")
        return "\n".join(lines)

    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues = sorted(report.issues, key=lambda issue: (severity_order.get(issue.severity, 99), issue.code, issue.context))
    for issue in issues:
        context = f" [{issue.context}]" if issue.context else ""
        lines.append(f"{issue.severity.upper()} {issue.code}{context}: {issue.message}")
    return "\n".join(lines)
