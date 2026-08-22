from __future__ import annotations

"""Optional finite-run contracts, progress evaluation, and permanent victories."""

import hashlib
import random
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH
from ascii_farmstead_helpers import days_in_month, format_date


VICTORY_CONTRACT_SCHEMA = 1
VICTORY_MODE_OPEN = "Open-Ended"
VICTORY_MODE_FINITE = "Finite Challenge"
VICTORY_MODES = (VICTORY_MODE_OPEN, VICTORY_MODE_FINITE)

VICTORY_MODE_DESCRIPTIONS = {
    VICTORY_MODE_OPEN: "No formal ending. Continue the farm, family, and world for as long as you like.",
    VICTORY_MODE_FINITE: "Receive five randomized hard objectives. Completing all five permanently ends the save in victory.",
}

OBJECTIVE_POOLS: Dict[str, Tuple[Dict[str, object], ...]] = {
    "Economy": (
        {
            "metric": "wealth",
            "title": "Secure Fortune",
            "description": "Hold a substantial cash reserve at one time.",
            "targets": (30000, 45000, 60000),
            "unit": "g",
        },
        {
            "metric": "enterprise_income",
            "title": "Regional Revenue",
            "description": "Earn lifetime passive income from properties, businesses, and trade.",
            "targets": (10000, 16000, 24000),
            "unit": "g",
        },
        {
            "metric": "enterprise_assets",
            "title": "Working Portfolio",
            "description": "Own a combined portfolio of properties, businesses, and trade routes.",
            "targets": (3, 4, 5),
            "unit": "assets",
        },
    ),
    "Exploration": (
        {
            "metric": "explored_chunks",
            "title": "Chart the Wilds",
            "description": "Personally explore persistent wilderness regions.",
            "targets": (80, 110, 140),
            "unit": "regions",
        },
        {
            "metric": "discovered_towns",
            "title": "Settlements Beyond",
            "description": "Discover distinct wilderness towns.",
            "targets": (2, 3, 4),
            "unit": "towns",
        },
        {
            "metric": "museum_records",
            "title": "A Living Archive",
            "description": "Donate distinct records to the Museum.",
            "targets": (15, 22, 30),
            "unit": "records",
        },
    ),
    "Mastery": (
        {
            "metric": "combat_level",
            "title": "Seasoned Adventurer",
            "description": "Reach a high player combat level.",
            "targets": (10, 13, 16),
            "unit": "level",
        },
        {
            "metric": "enemies_defeated",
            "title": "Proven Defender",
            "description": "Defeat hostile enemies across mines, dungeons, and the wilderness.",
            "targets": (50, 80, 110),
            "unit": "enemies",
        },
        {
            "metric": "mine_depth",
            "title": "Depth Without Fear",
            "description": "Reach a demanding depth in the main mine.",
            "targets": (18, 26, 34),
            "unit": "floor",
        },
    ),
    "Community": (
        {
            "metric": "town_stage",
            "title": "Restore the Town",
            "description": "Raise the starting town to its final development stage.",
            "targets": (3,),
            "unit": "stage",
        },
        {
            "metric": "completed_obligations",
            "title": "Known by Deeds",
            "description": "Complete resident requests, companion quests, missions, and bounties.",
            "targets": (8, 12, 16),
            "unit": "completed",
        },
        {
            "metric": "trusted_friends",
            "title": "Circle of Trust",
            "description": "Build strong relationships with several residents.",
            "targets": (3, 4, 5),
            "thresholds": (100, 125, 150),
            "unit": "friends",
        },
    ),
    "Legacy": (
        {
            "metric": "regional_assets",
            "title": "Roots Across the Region",
            "description": "Own claims, homes, businesses, and routes beyond the original farm.",
            "targets": (5, 7, 9),
            "unit": "holdings",
        },
        {
            "metric": "restored_projects",
            "title": "Builder's Legacy",
            "description": "Complete town restoration and development projects.",
            "targets": (5, 7, 9),
            "unit": "projects",
        },
        {
            "metric": "gear_enhancement",
            "title": "Masterwork Arsenal",
            "description": "Accumulate enhancement ranks across owned combat equipment.",
            "targets": (5, 8, 11),
            "unit": "ranks",
        },
    ),
}

VALID_METRICS = {
    str(template["metric"])
    for pool in OBJECTIVE_POOLS.values()
    for template in pool
}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stable_seed(text: str) -> int:
    digest = hashlib.sha256(str(text).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def victory_date_ordinal(month: int, day: int, year: int) -> int:
    year = max(1, int(year))
    month = max(1, min(12, int(month)))
    day = max(1, min(days_in_month(month, year), int(day)))
    total = 0
    for prior_year in range(1, year):
        total += sum(days_in_month(m, prior_year) for m in range(1, 13))
    total += sum(days_in_month(m, year) for m in range(1, month))
    return total + day


def build_victory_contract(
    *,
    player_name: str,
    birth_year: int,
    starting_class: str,
    wilderness_seed: int,
    start_month: int,
    start_day: int,
    start_year: int,
) -> Dict[str, object]:
    seed_text = (
        f"{player_name.casefold()}:{birth_year}:{starting_class}:"
        f"{wilderness_seed}:{start_month}:{start_day}:{start_year}:victory"
    )
    seed = _stable_seed(seed_text)
    rng = random.Random(seed)
    objectives: List[Dict[str, object]] = []
    for category in ("Economy", "Exploration", "Mastery", "Community", "Legacy"):
        template = dict(rng.choice(OBJECTIVE_POOLS[category]))
        targets = tuple(int(value) for value in template.pop("targets", (1,)))
        target_index = rng.randrange(len(targets))
        objective = {
            "id": f"{category.casefold()}:{template['metric']}",
            "category": category,
            "metric": str(template["metric"]),
            "title": str(template["title"]),
            "description": str(template["description"]),
            "target": targets[target_index],
            "unit": str(template.get("unit", "")),
        }
        thresholds = tuple(int(value) for value in template.get("thresholds", ()))
        if thresholds:
            objective["threshold"] = thresholds[min(target_index, len(thresholds) - 1)]
        objectives.append(objective)
    adjectives = ("Enduring", "Far-Reaching", "Hard-Won", "Storied", "Unbounded")
    nouns = ("Legacy", "Life", "Settlement", "Stewardship", "Venture")
    contract_id = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:12]
    return {
        "schema": VICTORY_CONTRACT_SCHEMA,
        "id": contract_id,
        "title": f"The {rng.choice(adjectives)} {rng.choice(nouns)}",
        "seed": seed,
        "created_month": int(start_month),
        "created_day": int(start_day),
        "created_year": int(start_year),
        "created_ordinal": victory_date_ordinal(start_month, start_day, start_year),
        "objectives": objectives,
        "completed": False,
    }


def sanitize_victory_contract(value: object) -> Dict[str, object]:
    if not isinstance(value, dict):
        return {}
    raw_objectives = value.get("objectives", [])
    objectives: List[Dict[str, object]] = []
    if isinstance(raw_objectives, list):
        for raw in raw_objectives[:8]:
            if not isinstance(raw, dict):
                continue
            metric = str(raw.get("metric", ""))
            if metric not in VALID_METRICS:
                continue
            target = max(1, min(1_000_000, _safe_int(raw.get("target", 1), 1)))
            objective = {
                "id": str(raw.get("id", metric))[:80],
                "category": str(raw.get("category", "Challenge"))[:40],
                "metric": metric,
                "title": str(raw.get("title", metric.replace("_", " ").title()))[:80],
                "description": str(raw.get("description", ""))[:240],
                "target": target,
                "unit": str(raw.get("unit", ""))[:24],
            }
            if metric == "trusted_friends":
                objective["threshold"] = max(1, min(250, _safe_int(raw.get("threshold", 100), 100)))
            objectives.append(objective)
    required_categories = {"Economy", "Exploration", "Mastery", "Community", "Legacy"}
    categories = [str(objective.get("category", "")) for objective in objectives]
    metrics = [str(objective.get("metric", "")) for objective in objectives]
    if (
        len(objectives) != len(required_categories)
        or set(categories) != required_categories
        or len(set(metrics)) != len(metrics)
    ):
        return {}
    month = max(1, min(12, _safe_int(value.get("created_month", 3), 3)))
    year = max(1, _safe_int(value.get("created_year", 1), 1))
    day = max(1, min(days_in_month(month, year), _safe_int(value.get("created_day", 1), 1)))
    return {
        "schema": VICTORY_CONTRACT_SCHEMA,
        "id": str(value.get("id", "legacy-contract"))[:40],
        "title": str(value.get("title", "Finite Challenge"))[:100],
        "seed": max(0, _safe_int(value.get("seed", 0))),
        "created_month": month,
        "created_day": day,
        "created_year": year,
        "created_ordinal": max(
            1,
            _safe_int(value.get("created_ordinal", victory_date_ordinal(month, day, year)), 1),
        ),
        "objectives": objectives,
        "completed": bool(value.get("completed", False)),
    }


class VictoryRunMixin:
    """Run-mode setup, measurable objective progress, and terminal victory."""

    def victory_mode(self) -> str:
        mode = str(getattr(self.state, "victory_mode", VICTORY_MODE_OPEN) or VICTORY_MODE_OPEN)
        return mode if mode in VICTORY_MODES else VICTORY_MODE_OPEN

    def finite_victory_active(self) -> bool:
        return (
            self.victory_mode() == VICTORY_MODE_FINITE
            and bool(getattr(self.state, "victory_contract", {}) or {})
            and not bool(getattr(self.state, "player_run_ended", False))
        )

    def build_victory_contract_for_identity(
        self,
        player_name: str,
        birth_year: int,
        starting_class: str,
    ) -> Dict[str, object]:
        return build_victory_contract(
            player_name=str(player_name),
            birth_year=int(birth_year),
            starting_class=str(starting_class),
            wilderness_seed=int(getattr(self.state, "wilderness_seed", 1337) or 1337),
            start_month=int(self.state.month),
            start_day=int(self.state.day),
            start_year=int(self.state.year),
        )

    def configure_victory_mode(
        self,
        mode: str,
        contract: Optional[Dict[str, object]] = None,
    ) -> None:
        mode = str(mode)
        if mode not in VICTORY_MODES:
            mode = VICTORY_MODE_OPEN
        self.state.victory_mode = mode
        self.state.victory_contract = (
            sanitize_victory_contract(contract)
            if mode == VICTORY_MODE_FINITE
            else {}
        )
        self.state.victory_record = {}
        self.state.player_run_outcome = ""

    def victory_metric_value(self, objective: Dict[str, object]) -> int:
        metric = str(objective.get("metric", ""))
        state = self.state
        if metric == "wealth":
            return max(0, int(state.money))
        if metric == "enterprise_income":
            profile = getattr(state, "civic_profile", {}) or {}
            return sum(
                max(0, _safe_int(profile.get(key, 0)))
                for key in (
                    "lifetime_property_income",
                    "lifetime_business_income",
                    "lifetime_trade_income",
                )
            )
        if metric == "enterprise_assets":
            return (
                len(getattr(state, "player_properties", {}) or {})
                + len(getattr(state, "player_businesses", {}) or {})
                + len(getattr(state, "player_trade_routes", {}) or {})
            )
        if metric == "explored_chunks":
            return max(0, _safe_int(getattr(state, "wilderness_chunks_visited", 0)))
        if metric == "discovered_towns":
            try:
                return len(self.discovered_procedural_town_plans())
            except Exception:
                return 0
        if metric == "museum_records":
            return len(getattr(state, "museum_donated_record_ids", []) or [])
        if metric == "combat_level":
            return max(1, _safe_int(getattr(state, "combat_level", 1), 1))
        if metric == "enemies_defeated":
            return max(0, _safe_int(getattr(state, "mine_enemies_defeated", 0)))
        if metric == "mine_depth":
            return max(1, _safe_int(getattr(state, "deepest_mine_floor", 1), 1))
        if metric == "town_stage":
            return max(0, _safe_int(getattr(state, "town_development_stage", 0)))
        if metric == "completed_obligations":
            return sum(
                len(getattr(state, field, []) or [])
                for field in (
                    "completed_resident_request_ids",
                    "completed_companion_quest_ids",
                    "completed_combat_mission_ids",
                    "completed_bounty_log",
                    "completed_bulletin_job_ids",
                )
            )
        if metric == "trusted_friends":
            threshold = max(1, _safe_int(objective.get("threshold", 100), 100))
            return sum(
                1
                for points in (getattr(state, "town_npc_relationships", {}) or {}).values()
                if _safe_int(points) >= threshold
            )
        if metric == "regional_assets":
            return (
                len(getattr(state, "owned_wilderness_claims", {}) or {})
                + len(getattr(state, "player_properties", {}) or {})
                + len(getattr(state, "player_businesses", {}) or {})
                + len(getattr(state, "player_trade_routes", {}) or {})
            )
        if metric == "restored_projects":
            return len(set(
                list(getattr(state, "completed_town_project_ids", []) or [])
                + list(getattr(state, "completed_town_restoration_project_ids", []) or [])
            ))
        if metric == "gear_enhancement":
            inventory = getattr(state, "inventory", {}) or {}
            equipped = {
                str(getattr(state, "equipped_weapon", "") or ""),
                str(getattr(state, "equipped_armor", "") or ""),
                str(getattr(state, "equipped_accessory", "") or ""),
            }
            total = 0
            for item_name, record in (getattr(state, "equipment_workshop", {}) or {}).items():
                if not isinstance(record, dict):
                    continue
                if _safe_int(inventory.get(item_name, 0)) > 0 or str(item_name) in equipped:
                    total += max(0, _safe_int(record.get("enhancement", 0)))
            return total
        return 0

    def victory_objective_progress(
        self,
        objective: Dict[str, object],
    ) -> Tuple[int, int, bool]:
        value = max(0, self.victory_metric_value(objective))
        target = max(1, _safe_int(objective.get("target", 1), 1))
        return value, target, value >= target

    def victory_completed_objective_count(self) -> int:
        contract = getattr(self.state, "victory_contract", {}) or {}
        return sum(
            1
            for objective in contract.get("objectives", []) or []
            if isinstance(objective, dict) and self.victory_objective_progress(objective)[2]
        )

    def victory_status_hint(self) -> str:
        if self.victory_mode() != VICTORY_MODE_FINITE:
            return "open-ended"
        objectives = list((getattr(self.state, "victory_contract", {}) or {}).get("objectives", []) or [])
        return f"{self.victory_completed_objective_count()}/{len(objectives)} complete"

    def victory_contract_lines(
        self,
        contract: Optional[Dict[str, object]] = None,
    ) -> List[str]:
        contract = contract or getattr(self.state, "victory_contract", {}) or {}
        if not contract:
            return [
                "OPEN-ENDED GAME",
                "",
                VICTORY_MODE_DESCRIPTIONS[VICTORY_MODE_OPEN],
            ]
        lines = [
            str(contract.get("title", "Finite Challenge")).upper(),
            "",
            "Complete every objective. The instant all are complete, this save ends permanently in victory.",
            "",
        ]
        for objective in contract.get("objectives", []) or []:
            if not isinstance(objective, dict):
                continue
            value, target, done = self.victory_objective_progress(objective)
            marker = "[X]" if done else "[ ]"
            threshold_text = ""
            if objective.get("metric") == "trusted_friends":
                threshold_text = f" at {objective.get('threshold')}+ friendship"
            unit = str(objective.get("unit", "") or "")
            progress = f"{value}/{target}"
            if unit == "g":
                progress = f"{value}g/{target}g"
            lines.extend([
                f"{marker} {objective.get('category')}: {objective.get('title')}",
                f"    {objective.get('description')}",
                f"    Progress: {progress} {unit if unit not in {'g'} else ''}{threshold_text}".rstrip(),
            ])
        lines.extend([
            "",
            f"Overall: {self.victory_completed_objective_count()}/{len(contract.get('objectives', []) or [])} complete",
            "This contract cannot be rerolled or disabled after the run begins.",
        ])
        return lines

    def victory_all_objectives_complete(self) -> bool:
        if not self.finite_victory_active():
            return False
        objectives = list((self.state.victory_contract or {}).get("objectives", []) or [])
        return bool(objectives) and all(
            isinstance(objective, dict) and self.victory_objective_progress(objective)[2]
            for objective in objectives
        )

    def victory_elapsed_days(self, contract: Dict[str, object]) -> int:
        start = max(1, _safe_int(contract.get("created_ordinal", 1), 1))
        end = victory_date_ordinal(self.state.month, self.state.day, self.state.year)
        return max(1, end - start + 1)

    def build_victory_record(self) -> Dict[str, object]:
        contract = dict(getattr(self.state, "victory_contract", {}) or {})
        objectives = []
        for objective in contract.get("objectives", []) or []:
            if not isinstance(objective, dict):
                continue
            value, target, done = self.victory_objective_progress(objective)
            objectives.append({
                "category": str(objective.get("category", "Challenge")),
                "title": str(objective.get("title", "Objective")),
                "value": value,
                "target": target,
                "completed": done,
            })
        relationships = list((getattr(self.state, "town_npc_relationships", {}) or {}).values())
        discovered_towns = self.victory_metric_value({"metric": "discovered_towns"})
        elapsed_days = self.victory_elapsed_days(contract)
        score = max(
            1,
            100000
            + int(self.state.money)
            + int(getattr(self.state, "mine_enemies_defeated", 0) or 0) * 25
            + len(getattr(self.state, "museum_donated_record_ids", []) or []) * 150
            - elapsed_days * 10,
        )
        return {
            "outcome": "victory",
            "contract_id": str(contract.get("id", "")),
            "contract_title": str(contract.get("title", "Finite Challenge")),
            "name": str(self.state.player_name),
            "dynasty_name": str(getattr(self.state, "dynasty_name", "")),
            "generation": int(getattr(self.state, "player_generation", 1) or 1),
            "end_month": int(self.state.month),
            "end_day": int(self.state.day),
            "end_year": int(self.state.year),
            "elapsed_days": elapsed_days,
            "objectives": objectives,
            "score": score,
            "money": int(self.state.money),
            "combat_level": int(getattr(self.state, "combat_level", 1) or 1),
            "enemies_defeated": int(getattr(self.state, "mine_enemies_defeated", 0) or 0),
            "deepest_mine_floor": int(getattr(self.state, "deepest_mine_floor", 1) or 1),
            "regions_explored": int(getattr(self.state, "wilderness_chunks_visited", 0) or 0),
            "towns_discovered": discovered_towns,
            "museum_records": len(getattr(self.state, "museum_donated_record_ids", []) or []),
            "properties": len(getattr(self.state, "player_properties", {}) or {}),
            "businesses": len(getattr(self.state, "player_businesses", {}) or {}),
            "trade_routes": len(getattr(self.state, "player_trade_routes", {}) or {}),
            "claims": len(getattr(self.state, "owned_wilderness_claims", {}) or {}),
            "children": len(getattr(self.state, "children", []) or []),
            "married": bool(getattr(self.state, "spouse_npc_id", "")),
            "strong_relationships": sum(1 for value in relationships if _safe_int(value) >= 100),
            "mortality_mode": str(getattr(self.state, "mortality_mode", "")),
        }

    def victory_summary_lines(
        self,
        record: Optional[Dict[str, object]] = None,
    ) -> List[str]:
        record = record or getattr(self.state, "victory_record", {}) or {}
        if not record:
            return ["No completed victory is recorded for this save."]
        lines = [
            "VICTORY",
            "",
            str(record.get("contract_title", "Finite Challenge")).upper(),
            f"{record.get('name', 'Farmer')} completed the run.",
            f"Finished: {format_date(record.get('end_month', 1), record.get('end_day', 1), record.get('end_year', 1))}",
            f"Duration: {record.get('elapsed_days', 1)} in-game day(s)",
            f"Generation: {record.get('generation', 1)}",
            f"Final score: {record.get('score', 0):,}",
            "",
            "Completed objectives:",
        ]
        for objective in record.get("objectives", []) or []:
            if isinstance(objective, dict):
                lines.append(
                    f"- {objective.get('category')}: {objective.get('title')} "
                    f"({objective.get('value')}/{objective.get('target')})"
                )
        lines.extend([
            "",
            "Final statistics:",
            f"- Money held: {record.get('money', 0)}g",
            f"- Combat level: {record.get('combat_level', 1)}",
            f"- Enemies defeated: {record.get('enemies_defeated', 0)}",
            f"- Deepest mine floor: {record.get('deepest_mine_floor', 1)}",
            f"- Regions explored: {record.get('regions_explored', 0)}",
            f"- Wilderness towns discovered: {record.get('towns_discovered', 0)}",
            f"- Museum records: {record.get('museum_records', 0)}",
            (
                f"- Holdings: {record.get('claims', 0)} claims, "
                f"{record.get('properties', 0)} properties, "
                f"{record.get('businesses', 0)} businesses, "
                f"{record.get('trade_routes', 0)} routes"
            ),
            f"- Strong relationships: {record.get('strong_relationships', 0)}",
            f"- Children: {record.get('children', 0)}",
            "",
            "This finite run is complete. The save is permanently read-only.",
        ])
        return lines

    def show_victory_screen(self) -> None:
        self.vertical_panel_view(
            "Victory",
            self.victory_summary_lines(),
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )

    def finalize_victory_run(self, interactive: bool = True) -> bool:
        if not self.victory_all_objectives_complete():
            return False
        self._victory_finalizing = True
        try:
            record = self.build_victory_record()
            self.state.victory_record = record
            self.state.victory_contract["completed"] = True
            self.state.player_run_ended = True
            self.state.player_run_outcome = "victory"
            if hasattr(self, "save"):
                self.save(quiet=True)
            self.state.message = (
                f"Victory: {record.get('contract_title')} completed. "
                "This finite run has ended permanently."
            )
            if interactive:
                self.show_victory_screen()
                self.running = False
            return True
        finally:
            self._victory_finalizing = False

    def check_victory_completion(self, interactive: bool = True) -> bool:
        if bool(getattr(self, "_victory_finalizing", False)):
            return False
        if not self.victory_all_objectives_complete():
            return False
        return self.finalize_victory_run(interactive=interactive)
