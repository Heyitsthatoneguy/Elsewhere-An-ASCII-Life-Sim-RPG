from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import uuid4


def _new_request_id() -> str:
    return "battle-" + uuid4().hex[:12]


def normalize_outcome(outcome: str) -> str:
    raw = str(outcome or "").lower()
    if "victory" in raw:
        return "victory"
    if "defeat" in raw or "wipe" in raw:
        return "defeat"
    if "fled" in raw or "flee" in raw:
        return "fled"
    if "abandon" in raw:
        return "abandoned"
    return raw or "abandoned"


@dataclass
class BattleRequest:
    """Structured overworld-to-combat payload.

    Keeps a few legacy aliases (`enemy_group`, `party_members`, `world_flags`)
    so older prototype helpers still work while the farming game can use the
    clearer fields.
    """

    request_id: str = ""
    source: str = "debug"
    map_id: Optional[int] = None
    map_name: str = ""
    enemy_counts: Dict[str, int] = field(default_factory=dict)
    objective: str = "Defeat All"
    objective_params: Dict[str, object] = field(default_factory=dict)
    party_ids: List[str] = field(default_factory=list)
    mission_id: Optional[str] = None
    mission_name: Optional[str] = None
    reward_theme: Optional[str] = None
    difficulty_hint: Optional[str] = None
    return_context: Dict[str, object] = field(default_factory=dict)
    world_flags_on_victory: List[str] = field(default_factory=list)
    world_flags_on_defeat: List[str] = field(default_factory=list)
    allow_flee: bool = True
    is_debug: bool = False

    # Backward-compatible aliases from the first handoff seam.
    enemy_group: List[str] = field(default_factory=list)
    party_members: List[str] = field(default_factory=list)
    world_flags: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id:
            self.request_id = _new_request_id()
        if not self.party_ids and self.party_members:
            self.party_ids = list(self.party_members)
        if not self.party_members and self.party_ids:
            self.party_members = list(self.party_ids)
        if self.mission_name is None:
            self.mission_name = ""
        if self.reward_theme is None:
            self.reward_theme = ""

    def requested_enemy_names(self) -> List[str]:
        names: List[str] = []
        for name, count in self.enemy_counts.items():
            try:
                amount = max(0, int(count))
            except (TypeError, ValueError):
                amount = 0
            names.extend([str(name)] * amount)
        if names:
            return names
        return [str(name) for name in self.enemy_group if str(name)]


@dataclass
class BattleResult:
    """Structured combat-to-overworld result payload."""

    request_id: str
    outcome: str
    source: str = "debug"
    map_id: Optional[int] = None
    map_name: str = ""
    mission_id: Optional[str] = None
    mission_name: Optional[str] = None
    objective: str = ""
    objective_success: bool = False
    defeated_enemies: List[str] = field(default_factory=list)
    surviving_enemies: List[str] = field(default_factory=list)
    party_status: Dict[str, object] = field(default_factory=dict)
    xp_awards: Dict[str, int] = field(default_factory=dict)
    class_progress: Dict[str, object] = field(default_factory=dict)
    loot: Dict[str, int] = field(default_factory=dict)
    injuries: List[Dict[str, object]] = field(default_factory=list)
    relationship_events: List[Dict[str, object]] = field(default_factory=list)
    world_flags: List[str] = field(default_factory=list)
    return_context: Dict[str, object] = field(default_factory=dict)
    summary: str = ""

    # Compatibility fields for earlier callers.
    objective_result: str = ""
    cleared_flags: Dict[str, object] = field(default_factory=dict)
    party_progression: Dict[str, Dict[str, object]] = field(default_factory=dict)

    @property
    def result(self) -> str:
        return self.outcome

    @property
    def xp(self) -> Dict[str, int]:
        return self.xp_awards


def battle_result_from_game(game: object, outcome: str, request: Optional[BattleRequest] = None) -> BattleResult:
    """Build a BattleResult from the current Game state without owning UI flow."""

    outcome = normalize_outcome(outcome)
    resolver = getattr(game, "resolve_battle_result", None)
    if outcome in {"victory", "defeat"} and callable(resolver) and not bool(getattr(game, "battle_result_processed", False)):
        resolver("Victory" if outcome == "victory" else "Defeat")

    request = request or getattr(game, "current_battle_request", None)
    request_id = request.request_id if request else str(getattr(game, "battle_request_id", ""))
    source = request.source if request else str(getattr(game, "battle_source", "debug"))
    map_name = str(getattr(game, "map_name", ""))
    map_id = int(getattr(game, "map_index", 0)) if hasattr(game, "map_index") else None
    mission_id = request.mission_id if request else None
    mission_name = request.mission_name if request and request.mission_name else str(getattr(game, "current_mission_name", ""))
    objective = str(getattr(game, "objective_mode", ""))

    heroes = list(getattr(game, "heroes", []))
    active_heroes = [hero for hero in heroes if getattr(hero, "active", False)]
    party_status = {
        hero.name: {
            "hp": int(getattr(hero, "hp", 0)),
            "max_hp": int(getattr(hero, "max_hp", 0)),
            "mp": int(getattr(hero, "mp", 0)),
            "max_mp": int(getattr(hero, "max_mp", 0)),
            "alive": bool(getattr(hero, "alive", False)),
            "class": getattr(game, "hero_class", lambda _hero: "")(hero),
            "defense": int(getattr(hero, "defense", 0)),
            "inventory": dict(getattr(hero, "inventory", {}) or {}),
        }
        for hero in active_heroes
    }
    xp_awards = {hero.name: int(getattr(hero, "xp", 0)) for hero in active_heroes}
    injuries = [
        {
            "party_id": hero.name,
            "kind": "ko",
            "severity": "moderate",
            "hp": int(getattr(hero, "hp", 0)),
        }
        for hero in active_heroes
        if not getattr(hero, "alive", False)
    ]
    progression = dict(getattr(game, "party_progress", {}))
    defeated = list(getattr(game, "combat_stats", {}).get("defeated", []))
    enemies = list(getattr(game, "enemies", []))
    surviving = [enemy.name for enemy in enemies if getattr(enemy, "active", False) and getattr(enemy, "alive", False)]
    objective_fn = getattr(game, "objective_text", None)
    objective_result = str(objective_fn()) if callable(objective_fn) else objective
    objective_success = outcome == "victory"

    request_context = dict(getattr(game, "battle_return_context", {}))
    legacy_world_flags = dict(getattr(game, "battle_world_flags", {}))
    world_flags: List[str] = []
    if request:
        world_flags.extend(request.world_flags_on_victory if outcome == "victory" else request.world_flags_on_defeat)
        request_context.update(dict(request.return_context))
        legacy_world_flags.update(dict(request.world_flags))
    world_flags.extend(str(flag) for flag in legacy_world_flags)
    world_flags = list(dict.fromkeys(flag for flag in world_flags if flag))

    if source == "ascii_farmstead":
        request_context["combat_campaign_inventory"] = dict(getattr(game, "campaign_inventory", {}) or {})
        request_context["combat_item_loadout_bonus"] = dict(getattr(game, "item_loadout_bonus", {}) or {})
        stats = getattr(game, "combat_stats", {}) or {}
        request_context["combat_stats"] = dict(stats) if isinstance(stats, dict) else {}
        grade_fn = getattr(game, "performance_grade", None)
        if callable(grade_fn):
            request_context["combat_performance_grade"] = str(grade_fn())
        report_lines = getattr(game, "last_result_lines", []) or []
        if isinstance(report_lines, list):
            request_context["combat_report_lines"] = [str(line) for line in report_lines[:18]]

    cleared_flags = dict(getattr(game, "battle_cleared_flags", {}))
    cleared_flags["battle_result"] = outcome
    if outcome == "victory" and map_name:
        cleared_flags[f"cleared:{map_name}"] = True

    summary = f"{outcome.title()} on {map_name or 'unknown map'}"
    if mission_name:
        summary += f" ({mission_name})"
    if defeated:
        summary += f"; defeated {len(defeated)}"

    return BattleResult(
        request_id=request_id or _new_request_id(),
        outcome=outcome,
        source=source,
        map_id=map_id,
        map_name=map_name,
        mission_id=mission_id,
        mission_name=mission_name,
        objective=objective,
        objective_success=objective_success,
        defeated_enemies=defeated,
        surviving_enemies=surviving,
        party_status=party_status,
        xp_awards=xp_awards,
        class_progress=progression,
        loot=dict(getattr(game, "rewards", {})),
        injuries=injuries,
        relationship_events=[],
        world_flags=world_flags,
        return_context=request_context,
        summary=summary,
        objective_result=objective_result,
        cleared_flags=cleared_flags,
        party_progression=progression,
    )
