from __future__ import annotations

"""Save-sensitive state models and migration helpers for Elsewhere.

This module owns dataclasses that are serialized into save files and helpers
that normalize old saves before they become GameState instances. Keep this
module independent from FarmGame and UI code to avoid circular imports.
"""

from dataclasses import dataclass, fields
from typing import Dict, List, Optional

from ascii_farmstead_support import (
    LOADED_STATE_DEFAULTS,
    VALID_GAME_LOCATIONS,
    VALID_TOOL_TARGET_MODES,
    copy_default_value,
    default_tool_levels_for,
)
from ascii_farmstead_data import (
    CRAFTABLE_ITEMS,
    CROP_DATA,
    FARM_CLAIM_TYPE_DATA,
    FISH_DATA,
    FOOD_DATA,
    INFRASTRUCTURE_DATA,
    INITIAL_UNLOCKED_TOWN_BUILDINGS,
    LEGACY_CLAIM_TYPE_TO_FARM_TYPE,
    MINE_MAX_FLOOR,
    OPTIONAL_TOOL_ORDER,
    PLAYER_COLOR_OPTIONS,
    QUALITY_ORDER,
    QUALITY_PREFIXES,
    QUALITY_PRICE_MULTIPLIERS,
    RESOURCE_ITEMS,
    RESTORED_TOWN_BUILDINGS,
    SEASONS,
    TOOLS,
    TOWN_BUILDING_DATA,
    TOWN_BUILDING_ID_BY_LOCATION,
    TOWN_BUILDING_IDS,
    TOWN_DEVELOPMENT_STAGE_LABELS,
    TOWN_DOORS,
    TOWN_RESTORATION_PROJECT_DATA,
    VALID_PLAYER_SEXES,
)
from ascii_farmstead_helpers import (
    days_in_month,
    format_date,
    migrate_abstract_day_to_date,
    season_for_month,
    weekday_for_date,
)
from ascii_farmstead_combat import (
    COMBAT_ACCESSORY_DATA,
    COMBAT_ARMOR_DATA,
    COMBAT_WEAPON_DATA,
    DEFAULT_COMBAT_ACCESSORY,
    DEFAULT_COMBAT_ARMOR,
    DEFAULT_COMBAT_ATTACK,
    DEFAULT_COMBAT_DEFENSE,
    DEFAULT_COMBAT_EXP,
    DEFAULT_COMBAT_EXP_TO_NEXT,
    DEFAULT_COMBAT_LEVEL,
    DEFAULT_COMBAT_MAX_FOCUS,
    DEFAULT_COMBAT_MAX_HP,
    DEFAULT_COMBAT_SKILL_POINTS,
    DEFAULT_COMBAT_WEAPON,
    translated_battle_loot,
)
from ascii_farmstead_town_builder import sanitize_wilderness_settlements
from ascii_farmstead_npc_builder import sanitize_procedural_settlement_populations
from ascii_farmstead_civic_state import (
    sanitize_civic_profile,
    sanitize_player_businesses,
    sanitize_player_properties,
    sanitize_player_trade_routes,
)


def farm_claim_type_data(farm_type_id: Optional[str]) -> Dict[str, object]:
    return FARM_CLAIM_TYPE_DATA.get(str(farm_type_id or ""), FARM_CLAIM_TYPE_DATA["meadow"])

def claim_farm_type_id_for_record(record: Dict[str, object]) -> str:
    raw = str(record.get("farm_type_id") or record.get("plan_id") or "").strip()
    if raw in FARM_CLAIM_TYPE_DATA:
        return raw
    for field_name in ["farm_type", "type"]:
        value = str(record.get(field_name, "")).strip()
        for farm_type_id, data in FARM_CLAIM_TYPE_DATA.items():
            if value == str(data.get("name", "")):
                return farm_type_id
        if value in LEGACY_CLAIM_TYPE_TO_FARM_TYPE:
            return LEGACY_CLAIM_TYPE_TO_FARM_TYPE[value]
    return "meadow"

def quality_item_name(crop_name: str, quality: str) -> str:
    prefix = QUALITY_PREFIXES.get(quality, "")
    return f"{prefix}{crop_name}"

def parse_quality_item(item_name: str) -> tuple[Optional[str], Optional[str]]:
    """Return (crop_name, quality) if item_name is a shippable crop-quality item."""
    for crop_name in CROP_DATA:
        if item_name == crop_name:
            return crop_name, "Normal"
        if item_name == f"Silver {crop_name}":
            return crop_name, "Silver"
        if item_name == f"Gold {crop_name}":
            return crop_name, "Gold"
    return None, None

def quality_sell_price(crop_name: str, quality: str) -> int:
    base = CROP_DATA[crop_name]["sell_price"]
    return int(round(base * QUALITY_PRICE_MULTIPLIERS.get(quality, 1.0)))

@dataclass
class Crop:
    name: str
    age: int = 0
    watered: bool = False
    ready: bool = False
    care_days: int = 0
    missed_water_days: int = 0
    fertilized: bool = False

    def stage_index(self) -> int:
        """
        Return a visible growth stage:
        0 = fresh sprout
        1 = small shoot
        2 = immature crop
        3 = ready crop
        """
        data = CROP_DATA[self.name]
        growth_days = max(1, int(data["growth_days"]))

        if self.ready or self.age >= growth_days:
            return 3

        # Divide the pre-harvest lifespan into 3 visible stages.
        return min(2, int((self.age * 3) / growth_days))

    def projected_quality(self) -> str:
        """Estimate harvest quality from watering/care consistency and fertilizer."""
        data = CROP_DATA[self.name]
        growth_days = max(1, int(data["growth_days"]))
        care_ratio = self.care_days / growth_days

        if self.missed_water_days == 0 and care_ratio >= 0.85:
            quality = "Gold"
        elif self.missed_water_days <= 1 and care_ratio >= 0.60:
            quality = "Silver"
        else:
            quality = "Normal"

        if self.fertilized:
            if quality == "Normal":
                quality = "Silver"
            elif quality == "Silver":
                quality = "Gold"

        return quality

    def symbol(self) -> str:
        data = CROP_DATA[self.name]
        stage = self.stage_index()

        if stage == 0:
            return "'"
        if stage == 1:
            return "i"
        if stage == 2:
            return data["symbol_growing"]
        return data["symbol_ready"]

def ensure_inventory_catalog(inventory: Optional[Dict[str, int]], starter_turnip_seeds: int = 0) -> Dict[str, int]:
    if not isinstance(inventory, dict):
        inventory = {}

    for crop_name in CROP_DATA:
        inventory.setdefault(f"{crop_name} Seeds", 0)
        for quality in QUALITY_ORDER:
            inventory.setdefault(quality_item_name(crop_name, quality), 0)
    if starter_turnip_seeds:
        inventory["Turnip Seeds"] = starter_turnip_seeds

    for item_group in (RESOURCE_ITEMS, CRAFTABLE_ITEMS, INFRASTRUCTURE_DATA, FOOD_DATA, FISH_DATA):
        for item_name in item_group:
            inventory.setdefault(item_name, 0)
    for equipment_group in (COMBAT_WEAPON_DATA, COMBAT_ARMOR_DATA, COMBAT_ACCESSORY_DATA):
        for item_name in equipment_group:
            inventory.setdefault(item_name, 0)

    return inventory

def normalize_town_development_stage(stage: object) -> int:
    try:
        value = int(stage)
    except Exception:
        value = 0
    return max(0, min(3, value))

def town_stage_label(stage: object) -> str:
    return TOWN_DEVELOPMENT_STAGE_LABELS.get(normalize_town_development_stage(stage), "Struggling Village")

def initial_unlocked_town_buildings_for_new_game() -> List[str]:
    return list(INITIAL_UNLOCKED_TOWN_BUILDINGS)

def restored_unlocked_town_buildings() -> List[str]:
    return list(RESTORED_TOWN_BUILDINGS)

def unlocked_town_buildings_for_stage(stage: object) -> List[str]:
    normalized_stage = normalize_town_development_stage(stage)
    if normalized_stage <= 0:
        return initial_unlocked_town_buildings_for_new_game()
    if normalized_stage >= 3:
        return restored_unlocked_town_buildings()
    staged_buildings = [
        building_id
        for building_id, data in TOWN_BUILDING_DATA.items()
        if int(data.get("stage", 0)) <= normalized_stage
    ]
    return sorted(set(initial_unlocked_town_buildings_for_new_game() + staged_buildings), key=lambda building_id: list(TOWN_BUILDING_IDS).index(building_id))

def normalize_unlocked_town_buildings(buildings: object, stage: object = 0) -> List[str]:
    if buildings is None:
        return unlocked_town_buildings_for_stage(stage)
    if isinstance(buildings, str):
        raw_values = [buildings]
    elif isinstance(buildings, (list, tuple, set)):
        raw_values = list(buildings)
    else:
        raw_values = []
    allowed = set(TOWN_BUILDING_IDS)
    cleaned = [str(building_id) for building_id in raw_values if str(building_id) in allowed]
    if not cleaned:
        cleaned = unlocked_town_buildings_for_stage(stage)
    else:
        cleaned = list(set(cleaned).union(initial_unlocked_town_buildings_for_new_game()))
    return sorted(set(cleaned), key=lambda building_id: list(TOWN_BUILDING_IDS).index(building_id))

def is_town_building_unlocked(state: object, building_id: str) -> bool:
    building_id = str(building_id)
    if building_id not in TOWN_BUILDING_DATA:
        return True
    unlocked = getattr(state, "unlocked_town_buildings", []) if state is not None else []
    return building_id in set(normalize_unlocked_town_buildings(unlocked, getattr(state, "town_development_stage", 0)))

def unlock_town_building(state: object, building_id: str) -> bool:
    building_id = str(building_id)
    if state is None or building_id not in TOWN_BUILDING_DATA:
        return False
    unlocked = normalize_unlocked_town_buildings(getattr(state, "unlocked_town_buildings", []), getattr(state, "town_development_stage", 0))
    if building_id in unlocked:
        state.unlocked_town_buildings = unlocked
        return False
    unlocked.append(building_id)
    state.unlocked_town_buildings = sorted(set(unlocked), key=lambda item: list(TOWN_BUILDING_IDS).index(item))
    return True

def town_building_status_label(state: object, building_id: str) -> str:
    data = TOWN_BUILDING_DATA.get(str(building_id), {})
    if not data:
        return "Open"
    if is_town_building_unlocked(state, str(building_id)):
        return str(data.get("status", "Open"))
    return str(data.get("closed_status", "Needs Restoration"))

def locked_building_message(building_id: str) -> str:
    data = TOWN_BUILDING_DATA.get(str(building_id), {})
    return str(data.get("locked_message", "This building is closed and may be restored later."))

def town_building_id_for_location(location: str) -> str:
    return TOWN_BUILDING_ID_BY_LOCATION.get(str(location), "")

def town_project_unlocks_building(project_id: str) -> str:
    project = TOWN_RESTORATION_PROJECT_DATA.get(str(project_id), {})
    return str(project.get("target_building", ""))

def town_restoration_project_completed(state: object, project_id: str) -> bool:
    project_id = str(project_id)
    if project_id in set(getattr(state, "completed_town_restoration_project_ids", []) or []):
        return True
    building_id = town_project_unlocks_building(project_id)
    return bool(building_id and is_town_building_unlocked(state, building_id))

def town_restoration_project_locked_reasons(state: object, project_id: str) -> List[str]:
    project = TOWN_RESTORATION_PROJECT_DATA.get(str(project_id), {})
    if not project:
        return ["Unknown restoration project."]
    reasons: List[str] = []
    required_stage = int(project.get("required_stage", 0) or 0)
    if normalize_town_development_stage(getattr(state, "town_development_stage", 0)) < required_stage:
        reasons.append(f"Requires town stage {required_stage}: {town_stage_label(required_stage)}.")
    for building_id in project.get("requires_buildings", []) or []:
        if not is_town_building_unlocked(state, str(building_id)):
            label = TOWN_BUILDING_DATA.get(str(building_id), {}).get("label", str(building_id).replace("_", " ").title())
            reasons.append(f"Requires {label} to be open.")
    return reasons

def town_restoration_missing_requirements(state: object, project_id: str) -> Dict[str, object]:
    project = TOWN_RESTORATION_PROJECT_DATA.get(str(project_id), {})
    missing: Dict[str, object] = {"money": 0, "items": {}, "locked": []}
    if not project:
        missing["locked"] = ["Unknown restoration project."]
        return missing
    missing["locked"] = town_restoration_project_locked_reasons(state, project_id)
    if town_restoration_project_completed(state, project_id):
        return missing
    money_cost = int(project.get("money", 0) or 0)
    money_owned = int(getattr(state, "money", 0) or 0)
    missing["money"] = max(0, money_cost - money_owned)
    inventory = getattr(state, "inventory", {}) or {}
    item_missing: Dict[str, int] = {}
    for item_name, qty in (project.get("items", {}) or {}).items():
        needed = int(qty)
        owned = int(inventory.get(str(item_name), 0) or 0)
        if owned < needed:
            item_missing[str(item_name)] = needed - owned
    missing["items"] = item_missing
    return missing

def can_complete_town_restoration_project(state: object, project_id: str) -> bool:
    if town_restoration_project_completed(state, project_id):
        return False
    missing = town_restoration_missing_requirements(state, project_id)
    return not missing.get("locked") and int(missing.get("money", 0) or 0) <= 0 and not missing.get("items")

def available_town_restoration_projects(state: object) -> List[str]:
    return [
        project_id
        for project_id in TOWN_RESTORATION_PROJECT_DATA
        if not town_restoration_project_completed(state, project_id)
        and not town_restoration_project_locked_reasons(state, project_id)
    ]

def format_town_restoration_cost(project_id: str) -> str:
    project = TOWN_RESTORATION_PROJECT_DATA.get(str(project_id), {})
    if not project:
        return "Unknown cost"
    parts = []
    money = int(project.get("money", 0) or 0)
    if money:
        parts.append(f"${money}")
    for item_name, qty in (project.get("items", {}) or {}).items():
        parts.append(f"{qty} {item_name}")
    return ", ".join(parts) if parts else "No cost"

def recalculate_town_development_stage(state: object) -> int:
    unlocked = set(normalize_unlocked_town_buildings(getattr(state, "unlocked_town_buildings", []), getattr(state, "town_development_stage", 0)))
    if set(RESTORED_TOWN_BUILDINGS).issubset(unlocked):
        stage = 3
    else:
        initial_buildings = set(INITIAL_UNLOCKED_TOWN_BUILDINGS)
        completed_count = sum(
            1
            for project_id in TOWN_RESTORATION_PROJECT_DATA
            if town_restoration_project_completed(state, project_id)
            and town_project_unlocks_building(project_id) not in initial_buildings
        )
        if completed_count >= 4:
            stage = 2
        elif completed_count >= 1:
            stage = 1
        else:
            stage = 0
    if state is not None:
        state.town_development_stage = stage
    return stage

def normalize_mine_floor(value: object, default: int = 1) -> int:
    try:
        floor = int(value)
    except Exception:
        floor = int(default)
    return max(1, min(MINE_MAX_FLOOR, floor))

def normalize_mine_floor_list(values: object) -> List[int]:
    if values is None:
        raw_values = []
    elif isinstance(values, dict):
        raw_values = list(values.keys())
    elif isinstance(values, str):
        raw_values = [part.strip() for part in values.replace("[", "").replace("]", "").split(",")]
    elif isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    else:
        raw_values = []

    cleaned: List[int] = []
    for value in raw_values:
        try:
            floor = int(value)
        except Exception:
            continue
        if 1 <= floor <= MINE_MAX_FLOOR:
            cleaned.append(floor)
    return sorted(set(cleaned))

def is_mine_floor_cleared(state: object, floor: object) -> bool:
    if state is None:
        return False
    floor = normalize_mine_floor(floor)
    return floor in set(normalize_mine_floor_list(getattr(state, "cleared_mine_floors", [])))

def mark_mine_floor_cleared(state: object, floor: object) -> bool:
    if state is None:
        return False
    floor = normalize_mine_floor(floor)
    floors = normalize_mine_floor_list(getattr(state, "cleared_mine_floors", []))
    if floor in floors:
        state.cleared_mine_floors = floors
        return False
    floors.append(floor)
    state.cleared_mine_floors = sorted(set(floors))
    return True

def mine_floor_down_stairs_unlocked(state: object, floor: object) -> bool:
    if state is None:
        return False
    floor = normalize_mine_floor(floor)
    if floor >= MINE_MAX_FLOOR:
        return False
    return floor in set(normalize_mine_floor_list(getattr(state, "unlocked_mine_down_stairs", [])))

def unlock_mine_floor_down_stairs(state: object, floor: object) -> bool:
    if state is None:
        return False
    floor = normalize_mine_floor(floor)
    if floor >= MINE_MAX_FLOOR:
        state.unlocked_mine_down_stairs = normalize_mine_floor_list(getattr(state, "unlocked_mine_down_stairs", []))
        return False
    floors = normalize_mine_floor_list(getattr(state, "unlocked_mine_down_stairs", []))
    if floor in floors:
        state.unlocked_mine_down_stairs = floors
        return False
    floors.append(floor)
    state.unlocked_mine_down_stairs = sorted(set(floors))
    return True

def mine_floor_clear_reward_claimed(state: object, floor: object) -> bool:
    if state is None:
        return False
    floor = normalize_mine_floor(floor)
    return floor in set(normalize_mine_floor_list(getattr(state, "mine_floor_clear_rewards_claimed", [])))

def mark_mine_floor_clear_reward_claimed(state: object, floor: object) -> bool:
    if state is None:
        return False
    floor = normalize_mine_floor(floor)
    floors = normalize_mine_floor_list(getattr(state, "mine_floor_clear_rewards_claimed", []))
    if floor in floors:
        state.mine_floor_clear_rewards_claimed = floors
        return False
    floors.append(floor)
    state.mine_floor_clear_rewards_claimed = sorted(set(floors))
    return True

def normalize_mine_progress_state_data(state_data: Dict[str, object], legacy_progress_without_clear_state: bool = False):
    mine_floor = normalize_mine_floor(state_data.get("mine_floor", 1))
    deepest = max(normalize_mine_floor(state_data.get("deepest_mine_floor", mine_floor)), mine_floor)
    state_data["mine_floor"] = mine_floor
    state_data["deepest_mine_floor"] = deepest

    cleared = set(normalize_mine_floor_list(state_data.get("cleared_mine_floors", [])))
    unlocked = set(normalize_mine_floor_list(state_data.get("unlocked_mine_down_stairs", [])))
    rewards = set(normalize_mine_floor_list(state_data.get("mine_floor_clear_rewards_claimed", [])))

    if legacy_progress_without_clear_state and deepest > 1:
        progressed_floors = set(range(1, deepest))
        cleared.update(progressed_floors)
        unlocked.update(progressed_floors)
        rewards.update(progressed_floors)

    state_data["cleared_mine_floors"] = sorted(cleared)
    state_data["unlocked_mine_down_stairs"] = sorted(floor for floor in unlocked if floor < MINE_MAX_FLOOR)
    state_data["mine_floor_clear_rewards_claimed"] = sorted(rewards)

@dataclass
class GameState:
    month: int = 3
    day: int = 1
    year: int = 1
    hour: int = 6
    minute: int = 0
    stamina: int = 100
    money: int = 0
    player_name: str = "Farmer"
    player_sex: str = "Female"
    player_color: str = "White"
    player_birthday_month: int = 3
    player_birthday_day: int = 1
    player_birth_year: int = -19
    player_generation: int = 1
    player_lifespan_age: int = 90
    player_background: str = "First-Generation Farmer"
    player_starting_class: str = "Vanguard"
    designated_heir_child_id: int = 0
    dynasty_name: str = ""
    dynasty_history: List[Dict[str, object]] = None
    dynasty_elders: List[Dict[str, object]] = None
    dynasty_kin: List[Dict[str, object]] = None
    dynasty_heirlooms: List[Dict[str, object]] = None
    dynasty_transition_log: List[str] = None
    dynasty_last_health_warning_year: int = 0
    dynasty_last_family_update_year: int = 0
    player_x: int = 8
    player_y: int = 9
    location: str = "Farm"
    facing: str = "DOWN"
    tool_target_mode: str = "FRONT"
    live_time_enabled: bool = True
    aging_and_death_enabled: bool = True
    player_frozen_age: int = 0
    selected_tool_index: int = 0
    selected_seed: str = "Turnip"
    inventory: Dict[str, int] = None
    storage_inventory: Dict[str, int] = None
    placed_objects: Dict[str, str] = None
    fertilized_tiles: Dict[str, bool] = None
    owned_tools: List[str] = None
    tool_levels: Dict[str, int] = None
    farm_expansions: List[str] = None
    house_upgrades: List[str] = None
    held_object: Optional[str] = None
    wilderness_seed: int = 1337
    wilderness_chunk_x: int = 0
    wilderness_chunk_y: int = 0
    wilderness_chunks_visited: int = 1
    wilderness_animals_seen: int = 0
    owned_wilderness_claims: Dict[str, Dict[str, object]] = None
    wilderness_settlements: Dict[str, Dict[str, object]] = None
    procedural_settlement_populations: Dict[str, Dict[str, object]] = None
    current_procedural_settlement_key: str = ""
    current_procedural_building_id: str = ""
    procedural_settlement_return_x: int = 0
    procedural_settlement_return_y: int = 0
    player_properties: Dict[str, Dict[str, object]] = None
    player_businesses: Dict[str, Dict[str, object]] = None
    player_trade_routes: Dict[str, Dict[str, object]] = None
    primary_residence_id: str = "farmhouse"
    civic_profile: Dict[str, object] = None
    civic_income_log: List[str] = None
    farm_building_harvest_days: Dict[str, str] = None
    farm_building_boosts: Dict[str, str] = None
    farm_animals: List[Dict[str, object]] = None
    next_farm_animal_id: int = 1
    town_npcs: List[Dict[str, object]] = None
    town_npc_dialogue_counts: Dict[str, int] = None
    town_npc_relationships: Dict[str, int] = None
    town_npc_last_talk_day: Dict[str, str] = None
    town_npc_last_gift_day: Dict[str, str] = None
    town_npc_last_gift_reactions: Dict[str, Dict[str, object]] = None
    town_npc_recent_gifts: Dict[str, List[Dict[str, object]]] = None
    town_npc_last_court_day: Dict[str, str] = None
    town_npc_courtship_counts: Dict[str, int] = None
    town_npc_relationship_milestones: Dict[str, List[str]] = None
    town_npc_recent_dialogue_ids: Dict[str, List[str]] = None
    town_npc_last_proposal_day: Dict[str, str] = None
    dating_npc_ids: List[str] = None
    engaged_npc_id: str = ""
    engagement_month: int = 0
    engagement_day: int = 0
    engagement_year: int = 0
    wedding_month: int = 0
    wedding_day: int = 0
    wedding_year: int = 0
    spouse_npc_id: str = ""
    spouse_moved_to_farm: bool = False
    marriage_month: int = 0
    marriage_day: int = 0
    marriage_year: int = 0
    spouse_birth_year: int = 0
    spouse_lifespan_age: int = 0
    spouse_frozen_age: int = 0
    marriage_history: List[Dict[str, object]] = None
    deceased_spouse_npc_ids: List[str] = None
    family_event_log: List[str] = None
    family_event_flags: List[str] = None
    family_planning_last_discussion_day: str = ""
    pregnancy_checkup_months_seen: List[str] = None
    child_milestone_flags: List[str] = None
    family_help_enabled: bool = True
    family_last_help_day: str = ""
    family_bond: int = 0
    family_meal_last_day: str = ""
    family_last_meal: str = ""
    spouse_support_mode: str = "Balanced"
    child_affection: Dict[str, int] = None
    child_last_gift_day: Dict[str, str] = None
    child_last_lesson_day: Dict[str, str] = None
    child_learning_points: Dict[str, Dict[str, int]] = None
    child_chore_assignments: Dict[str, str] = None
    unlocked_party_member_ids: List[str] = None
    active_party_member_ids: List[str] = None
    max_party_members: int = 4
    party_tactic: str = "Balanced"
    manual_party_member_ids: List[str] = None
    travel_follower_ids: List[str] = None
    max_travel_followers: int = 3
    travel_follower_states: Dict[str, Dict[str, object]] = None
    combat_party_progress: Dict[str, Dict[str, object]] = None
    combat_campaign_inventory: Dict[str, int] = None
    combat_item_loadout_bonus: Dict[str, int] = None
    combat_bestiary_seen: List[str] = None
    combat_bestiary_defeated: Dict[str, int] = None
    completed_combat_mission_ids: List[str] = None
    last_combat_report: List[str] = None
    party_member_hp: Dict[str, int] = None
    party_member_focus: Dict[str, int] = None
    party_member_last_relationship_gain_day: Dict[str, str] = None
    pregnancy_active: bool = False
    pregnancy_parent_npc_id: str = ""
    pregnancy_gestational_parent: str = ""
    pregnancy_start_month: int = 0
    pregnancy_start_day: int = 0
    pregnancy_start_year: int = 0
    pregnancy_due_month: int = 0
    pregnancy_due_day: int = 0
    pregnancy_due_year: int = 0
    children: List[Dict[str, object]] = None
    next_child_id: int = 1
    mail_read_ids: List[str] = None
    mail_claimed_ids: List[str] = None
    market_purchase_counts: Dict[str, int] = None
    completed_errand_ids: List[str] = None
    completed_resident_request_ids: List[str] = None
    completed_companion_quest_ids: List[str] = None
    learned_recipe_ids: List[str] = None
    library_research_ids: List[str] = None
    museum_donated_record_ids: List[str] = None
    museum_donation_counts: Dict[str, int] = None
    museum_reward_claims: List[str] = None
    museum_exhibit_unlocks: List[str] = None
    town_development_stage: int = 0
    unlocked_town_buildings: List[str] = None
    completed_town_project_ids: List[str] = None
    completed_town_restoration_project_ids: List[str] = None
    completed_mine_special_ids: List[str] = None
    attended_festival_ids: List[str] = None
    completed_bulletin_job_ids: List[str] = None
    completed_scene_ids: List[str] = None
    seen_scene_ids: List[str] = None
    scene_flags: List[str] = None
    active_scene_id: str = ""
    active_scene_step_index: int = 0
    active_food_buffs: Dict[str, Dict[str, int]] = None
    fish_ponds: Dict[str, Dict[str, object]] = None
    artisan_processors: Dict[str, Dict[str, object]] = None
    overworld_cursor_chunk_x: int = 0
    overworld_cursor_chunk_y: int = 0
    overworld_return_chunk_x: int = 0
    overworld_return_chunk_y: int = 0
    overworld_return_x: int = 0
    overworld_return_y: int = 0
    cave_return_location: str = "Wilderness"
    cave_return_chunk_x: int = 0
    cave_return_chunk_y: int = 0
    cave_return_x: int = 0
    cave_return_y: int = 0
    current_cave_key: str = ""
    wilderness_caves_discovered: int = 0
    current_dungeon_key: str = ""
    current_dungeon_floor: int = 1
    wilderness_dungeons_discovered: int = 0
    wilderness_dungeon_state: Dict[str, Dict[str, object]] = None
    wilderness_strongholds_cleared: int = 0
    wilderness_stronghold_state: Dict[str, Dict[str, object]] = None
    mine_floor: int = 1
    deepest_mine_floor: int = 1
    unlocked_mine_elevators: List[int] = None
    cleared_mine_floors: List[int] = None
    unlocked_mine_down_stairs: List[int] = None
    mine_floor_clear_rewards_claimed: List[int] = None
    mine_seed: int = 4242
    mine_combat_victories: int = 0
    mine_combat_defeats: int = 0
    mine_combat_flees: int = 0
    mine_enemies_defeated: int = 0
    mine_recent_combat_maps: List[str] = None
    mine_recent_combat_signatures: List[str] = None
    combat_level: int = DEFAULT_COMBAT_LEVEL
    combat_exp: int = DEFAULT_COMBAT_EXP
    combat_exp_to_next: int = DEFAULT_COMBAT_EXP_TO_NEXT
    combat_max_hp: int = DEFAULT_COMBAT_MAX_HP
    combat_current_hp: int = DEFAULT_COMBAT_MAX_HP
    combat_attack: int = DEFAULT_COMBAT_ATTACK
    combat_defense: int = DEFAULT_COMBAT_DEFENSE
    combat_focus: int = DEFAULT_COMBAT_MAX_FOCUS
    combat_max_focus: int = DEFAULT_COMBAT_MAX_FOCUS
    combat_skill_points: int = DEFAULT_COMBAT_SKILL_POINTS
    equipped_weapon: str = DEFAULT_COMBAT_WEAPON
    equipped_armor: str = DEFAULT_COMBAT_ARMOR
    equipped_accessory: str = DEFAULT_COMBAT_ACCESSORY
    shipped_today: int = 0
    shipped_today_items: Dict[str, int] = None
    last_shipping_report: List[str] = None
    last_automation_report: List[str] = None
    automation_machines: Dict[str, Dict[str, object]] = None
    fishing_active: bool = False
    fishing_target_x: int = 0
    fishing_target_y: int = 0
    fishing_elapsed: float = 0.0
    fishing_bite_at: float = 0.0
    fishing_end_at: float = 0.0
    fishing_will_bite: bool = True
    fishing_pool: List[str] = None
    weather: str = "Sunny"
    message: str = "Welcome to Elsewhere. Press H for help or K for calendar."
    color_enabled: bool = True
    shop_auto_open_enabled: bool = True
    shop_menu_suppressed_until_exit: bool = False
    bin_auto_open_enabled: bool = True
    bin_menu_suppressed_until_exit: bool = False
    show_target_info: bool = True
    show_control_hints: bool = True

    def __post_init__(self):
        def list_values(value: object) -> List[object]:
            return list(value) if isinstance(value, (list, tuple, set)) else []

        def clean_string_list(value: object) -> List[str]:
            return [str(item) for item in list_values(value) if item is not None]

        try:
            self.year = max(1, int(self.year))
        except (TypeError, ValueError):
            self.year = 1
        try:
            self.month = max(1, min(12, int(self.month)))
        except (TypeError, ValueError):
            self.month = 3
        try:
            self.day = max(1, min(days_in_month(self.month, self.year), int(self.day)))
        except (TypeError, ValueError):
            self.day = 1
        try:
            self.hour = max(0, min(23, int(self.hour)))
        except (TypeError, ValueError):
            self.hour = 6
        try:
            self.minute = max(0, min(59, int(self.minute)))
        except (TypeError, ValueError):
            self.minute = 0
        try:
            self.stamina = max(0, int(self.stamina))
        except (TypeError, ValueError):
            self.stamina = 100
        try:
            self.money = max(0, int(self.money))
        except (TypeError, ValueError):
            self.money = 0
        try:
            self.player_x = int(self.player_x)
        except (TypeError, ValueError):
            self.player_x = 8
        try:
            self.player_y = int(self.player_y)
        except (TypeError, ValueError):
            self.player_y = 9
        self.location = str(self.location or "Farm")
        if self.location not in VALID_GAME_LOCATIONS:
            self.location = "Farm"
        self.facing = str(self.facing or "DOWN").upper()
        if self.facing not in {"UP", "DOWN", "LEFT", "RIGHT"}:
            self.facing = "DOWN"
        try:
            self.selected_tool_index = max(0, int(self.selected_tool_index))
        except (TypeError, ValueError):
            self.selected_tool_index = 0
        self.selected_seed = str(self.selected_seed or "Turnip")
        if self.selected_seed not in CROP_DATA:
            self.selected_seed = "Turnip"
        self.inventory = ensure_inventory_catalog(
            self.inventory,
            starter_turnip_seeds=5 if self.inventory is None else 0,
        )
        if self.storage_inventory is None:
            self.storage_inventory = {}
        if self.placed_objects is None:
            self.placed_objects = {}
        if self.fertilized_tiles is None:
            self.fertilized_tiles = {}
        if self.farm_building_harvest_days is None:
            self.farm_building_harvest_days = {}
        if self.farm_building_boosts is None:
            self.farm_building_boosts = {}
        if self.farm_animals is None:
            self.farm_animals = []
        if not isinstance(self.next_farm_animal_id, int) or self.next_farm_animal_id < 1:
            self.next_farm_animal_id = 1
        if self.town_npcs is None:
            self.town_npcs = []
        if self.town_npc_dialogue_counts is None:
            self.town_npc_dialogue_counts = {}
        if self.town_npc_relationships is None:
            self.town_npc_relationships = {}
        if self.town_npc_last_talk_day is None:
            self.town_npc_last_talk_day = {}
        if self.town_npc_last_gift_day is None:
            self.town_npc_last_gift_day = {}
        if not isinstance(self.town_npc_last_gift_day, dict):
            self.town_npc_last_gift_day = {}
        if self.town_npc_last_gift_reactions is None:
            self.town_npc_last_gift_reactions = {}
        if not isinstance(self.town_npc_last_gift_reactions, dict):
            self.town_npc_last_gift_reactions = {}
        if self.town_npc_recent_gifts is None:
            self.town_npc_recent_gifts = {}
        if not isinstance(self.town_npc_recent_gifts, dict):
            self.town_npc_recent_gifts = {}
        if self.town_npc_last_court_day is None:
            self.town_npc_last_court_day = {}
        if not isinstance(self.town_npc_last_court_day, dict):
            self.town_npc_last_court_day = {}
        if self.town_npc_courtship_counts is None:
            self.town_npc_courtship_counts = {}
        if not isinstance(self.town_npc_courtship_counts, dict):
            self.town_npc_courtship_counts = {}
        if self.town_npc_relationship_milestones is None:
            self.town_npc_relationship_milestones = {}
        if not isinstance(self.town_npc_relationship_milestones, dict):
            self.town_npc_relationship_milestones = {}
        if self.town_npc_recent_dialogue_ids is None:
            self.town_npc_recent_dialogue_ids = {}
        if not isinstance(self.town_npc_recent_dialogue_ids, dict):
            self.town_npc_recent_dialogue_ids = {}
        if self.town_npc_last_proposal_day is None:
            self.town_npc_last_proposal_day = {}
        if not isinstance(self.town_npc_last_proposal_day, dict):
            self.town_npc_last_proposal_day = {}
        self.dating_npc_ids = clean_string_list(self.dating_npc_ids)
        self.engaged_npc_id = str(self.engaged_npc_id or "")
        self.spouse_npc_id = str(self.spouse_npc_id or "")
        for field_name in [
            "engagement_month",
            "engagement_day",
            "engagement_year",
            "wedding_month",
            "wedding_day",
            "wedding_year",
            "marriage_month",
            "marriage_day",
            "marriage_year",
            "spouse_lifespan_age",
            "spouse_frozen_age",
        ]:
            try:
                setattr(self, field_name, max(0, int(getattr(self, field_name, 0))))
            except Exception:
                setattr(self, field_name, 0)
        try:
            self.spouse_birth_year = int(self.spouse_birth_year)
        except Exception:
            self.spouse_birth_year = 0
        if self.spouse_lifespan_age:
            self.spouse_lifespan_age = max(
                70,
                min(115, self.spouse_lifespan_age),
            )
        if not isinstance(self.marriage_history, list):
            self.marriage_history = []
        self.marriage_history = [
            dict(record)
            for record in self.marriage_history
            if isinstance(record, dict)
        ][-12:]
        if not isinstance(self.deceased_spouse_npc_ids, list):
            self.deceased_spouse_npc_ids = []
        self.deceased_spouse_npc_ids = list(dict.fromkeys(
            str(npc_id)
            for npc_id in self.deceased_spouse_npc_ids
            if str(npc_id or "").strip()
        ))
        if self.family_event_log is None or not isinstance(self.family_event_log, list):
            self.family_event_log = []
        self.family_event_log = [str(line) for line in self.family_event_log if line is not None][-30:]
        if self.family_event_flags is None or not isinstance(self.family_event_flags, list):
            self.family_event_flags = []
        self.family_event_flags = sorted({str(flag) for flag in self.family_event_flags if str(flag or "").strip()})
        self.family_planning_last_discussion_day = str(self.family_planning_last_discussion_day or "")
        if self.pregnancy_checkup_months_seen is None or not isinstance(self.pregnancy_checkup_months_seen, list):
            self.pregnancy_checkup_months_seen = []
        self.pregnancy_checkup_months_seen = sorted({str(flag) for flag in self.pregnancy_checkup_months_seen if str(flag or "").strip()})
        if self.child_milestone_flags is None or not isinstance(self.child_milestone_flags, list):
            self.child_milestone_flags = []
        self.child_milestone_flags = sorted({str(flag) for flag in self.child_milestone_flags if str(flag or "").strip()})
        def clean_family_points(values: object) -> Dict[str, int]:
            if not isinstance(values, dict):
                return {}
            clean: Dict[str, int] = {}
            for key, value in values.items():
                family_id = str(key or "").strip()
                if not family_id:
                    continue
                try:
                    clean[family_id] = max(0, int(value))
                except Exception:
                    continue
            return clean

        self.family_help_enabled = bool(self.family_help_enabled)
        self.family_last_help_day = str(self.family_last_help_day or "")
        try:
            self.family_bond = max(0, min(999, int(self.family_bond)))
        except Exception:
            self.family_bond = 0
        self.family_meal_last_day = str(self.family_meal_last_day or "")
        self.family_last_meal = str(self.family_last_meal or "")
        valid_spouse_modes = {"Balanced", "Meals", "Farm", "Forage", "Rest"}
        self.spouse_support_mode = str(self.spouse_support_mode or "Balanced")
        if self.spouse_support_mode not in valid_spouse_modes:
            self.spouse_support_mode = "Balanced"

        self.child_affection = clean_family_points(self.child_affection)
        if not isinstance(self.child_last_gift_day, dict):
            self.child_last_gift_day = {}
        self.child_last_gift_day = {str(key): str(value) for key, value in self.child_last_gift_day.items() if str(key or "").strip()}
        if not isinstance(self.child_last_lesson_day, dict):
            self.child_last_lesson_day = {}
        self.child_last_lesson_day = {str(key): str(value) for key, value in self.child_last_lesson_day.items() if str(key or "").strip()}
        if not isinstance(self.child_chore_assignments, dict):
            self.child_chore_assignments = {}
        self.child_chore_assignments = {
            str(key): str(value)
            for key, value in self.child_chore_assignments.items()
            if str(key or "").strip() and str(value or "").strip()
        }
        if not isinstance(self.child_learning_points, dict):
            self.child_learning_points = {}
        cleaned_learning: Dict[str, Dict[str, int]] = {}
        for child_id, topics in self.child_learning_points.items():
            child_key = str(child_id or "").strip()
            if not child_key or not isinstance(topics, dict):
                continue
            cleaned_learning[child_key] = {}
            for topic, points in topics.items():
                topic_key = str(topic or "").strip()
                if not topic_key:
                    continue
                try:
                    cleaned_learning[child_key][topic_key] = max(0, int(points))
                except Exception:
                    continue
        self.child_learning_points = cleaned_learning
        try:
            self.max_party_members = max(1, min(4, int(self.max_party_members)))
        except Exception:
            self.max_party_members = 4

        def clean_party_ids(values: object) -> List[str]:
            if not isinstance(values, list):
                values = []
            clean: List[str] = []
            seen = set()
            for value in values:
                member_id = str(value or "").strip()
                if not member_id or member_id in seen:
                    continue
                clean.append(member_id)
                seen.add(member_id)
            return clean

        self.unlocked_party_member_ids = clean_party_ids(self.unlocked_party_member_ids)
        self.active_party_member_ids = clean_party_ids(self.active_party_member_ids)[: max(0, self.max_party_members - 1)]
        valid_party_tactics = {"Balanced", "Aggressive", "Cautious", "Support"}
        self.party_tactic = str(self.party_tactic or "Balanced")
        if self.party_tactic not in valid_party_tactics:
            self.party_tactic = "Balanced"
        self.manual_party_member_ids = clean_party_ids(self.manual_party_member_ids)
        self.max_travel_followers = 3
        self.travel_follower_ids = clean_party_ids(self.travel_follower_ids)[: self.max_travel_followers]
        if not isinstance(self.travel_follower_states, dict):
            self.travel_follower_states = {}
        cleaned_follower_states: Dict[str, Dict[str, object]] = {}
        for raw_id, raw_record in self.travel_follower_states.items():
            follower_id = str(raw_id or "").strip()
            if not follower_id or not isinstance(raw_record, dict):
                continue
            mode = str(raw_record.get("mode", "home") or "home").lower()
            task = str(raw_record.get("task", "") or "")
            valid_tasks = {"water_crops", "harvest_crops", "animal_care", "gather_forage"}
            if task not in valid_tasks:
                task = ""
            if mode not in {"follow", "wait", "work", "home"}:
                mode = "home"
            if mode == "work" and not task:
                mode = "home"
            try:
                x = int(raw_record.get("x", -1))
                y = int(raw_record.get("y", -1))
            except Exception:
                x, y = -1, -1
            try:
                work_units = max(0, int(raw_record.get("work_units", 0)))
            except Exception:
                work_units = 0
            try:
                bond_points = max(0, min(999, int(raw_record.get("bond_points", 0))))
            except Exception:
                bond_points = 0
            try:
                outing_bond_count = max(0, int(raw_record.get("outing_bond_count", 0)))
            except Exception:
                outing_bond_count = 0
            task_xp: Dict[str, int] = {}
            raw_task_xp = raw_record.get("task_xp", {})
            if isinstance(raw_task_xp, dict):
                for raw_task, raw_value in raw_task_xp.items():
                    task_id = str(raw_task)
                    if task_id not in valid_tasks:
                        continue
                    try:
                        task_xp[task_id] = max(0, int(raw_value))
                    except Exception:
                        continue
            work_totals: Dict[str, int] = {}
            raw_work_totals = raw_record.get("work_totals", {})
            if isinstance(raw_work_totals, dict):
                for raw_task, raw_value in raw_work_totals.items():
                    task_id = str(raw_task)
                    if task_id not in valid_tasks:
                        continue
                    try:
                        work_totals[task_id] = max(0, int(raw_value))
                    except Exception:
                        continue
            memories = [
                str(value)
                for value in (raw_record.get("memories", []) if isinstance(raw_record.get("memories"), list) else [])
                if str(value or "").strip()
            ][-16:]
            work_log = [
                str(value)
                for value in (raw_record.get("work_log", []) if isinstance(raw_record.get("work_log"), list) else [])
                if str(value or "").strip()
            ][-12:]
            memory_flags = list(dict.fromkeys(
                str(value)
                for value in (
                    raw_record.get("memory_flags", [])
                    if isinstance(raw_record.get("memory_flags"), list)
                    else []
                )
                if str(value or "").strip()
            ))
            outing_locations = list(dict.fromkeys(
                str(value)
                for value in (
                    raw_record.get("outing_locations", [])
                    if isinstance(raw_record.get("outing_locations"), list)
                    else []
                )
                if str(value or "").strip()
            ))
            valid_expedition_roles = {"Balanced", "Scout", "Gatherer", "Guardian", "Support"}
            expedition_role = str(raw_record.get("expedition_role", "Balanced") or "Balanced")
            if expedition_role not in valid_expedition_roles:
                expedition_role = "Balanced"
            bond_milestones = [
                str(value)
                for value in (
                    raw_record.get("bond_milestones", [])
                    if isinstance(raw_record.get("bond_milestones"), list)
                    else []
                )
                if str(value) in {"Familiar", "Trusted", "Close", "Kindred"}
            ]
            bond_milestones = list(dict.fromkeys(bond_milestones))
            cleaned_follower_states[follower_id] = {
                "location": str(raw_record.get("location", "Home") or "Home"),
                "x": x,
                "y": y,
                "mode": mode,
                "activity": str(raw_record.get("activity", "at home") or "at home"),
                "task": task,
                "work_day": str(raw_record.get("work_day", "") or ""),
                "work_units": work_units,
                "last_work_tick": str(raw_record.get("last_work_tick", "") or ""),
                "task_xp": task_xp,
                "work_totals": work_totals,
                "work_log": work_log,
                "bond_points": bond_points,
                "checkin_day": str(raw_record.get("checkin_day", "") or ""),
                "shared_moment_day": str(raw_record.get("shared_moment_day", "") or ""),
                "outing_day": str(raw_record.get("outing_day", "") or ""),
                "outing_locations": outing_locations,
                "outing_bond_count": outing_bond_count,
                "memory_flags": memory_flags,
                "memories": memories,
                "expedition_role": expedition_role,
                "bond_milestones": bond_milestones,
                "forage_find_day": str(raw_record.get("forage_find_day", "") or ""),
            }
        self.travel_follower_states = cleaned_follower_states

        def clean_party_points(values: object) -> Dict[str, int]:
            if not isinstance(values, dict):
                return {}
            clean: Dict[str, int] = {}
            for key, value in values.items():
                member_id = str(key or "").strip()
                if not member_id:
                    continue
                try:
                    clean[member_id] = max(0, int(value))
                except Exception:
                    continue
            return clean

        if self.combat_party_progress is None or not isinstance(self.combat_party_progress, dict):
            self.combat_party_progress = {}

        def json_safe_progress(value: object):
            if isinstance(value, dict):
                return {str(k): json_safe_progress(v) for k, v in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [json_safe_progress(v) for v in value]
            if isinstance(value, (str, int, float, bool)) or value is None:
                return value
            return str(value)

        cleaned_progress: Dict[str, Dict[str, object]] = {}
        for key, value in self.combat_party_progress.items():
            progress_key = str(key or "").strip()
            if not progress_key or not isinstance(value, dict):
                continue
            cleaned_progress[progress_key] = json_safe_progress(value)
        self.combat_party_progress = cleaned_progress

        self.combat_campaign_inventory = clean_party_points(self.combat_campaign_inventory)
        legacy_combat_money, legacy_combat_items = translated_battle_loot(self.combat_campaign_inventory)
        if legacy_combat_money or legacy_combat_items:
            self.money = max(0, int(self.money or 0)) + legacy_combat_money
            for item_name, qty in legacy_combat_items.items():
                self.inventory[item_name] = int(self.inventory.get(item_name, 0) or 0) + int(qty)
            self.combat_campaign_inventory = {}
        self.combat_item_loadout_bonus = clean_party_points(self.combat_item_loadout_bonus)
        self.combat_bestiary_seen = clean_party_ids(self.combat_bestiary_seen)
        self.combat_bestiary_defeated = clean_party_points(self.combat_bestiary_defeated)
        self.completed_combat_mission_ids = clean_party_ids(self.completed_combat_mission_ids)
        if not isinstance(self.last_combat_report, list):
            self.last_combat_report = []
        self.last_combat_report = [str(line) for line in self.last_combat_report if line is not None][-16:]

        self.party_member_hp = clean_party_points(self.party_member_hp)
        self.party_member_focus = clean_party_points(self.party_member_focus)
        if not isinstance(self.party_member_last_relationship_gain_day, dict):
            self.party_member_last_relationship_gain_day = {}
        self.party_member_last_relationship_gain_day = {
            str(key): str(value)
            for key, value in self.party_member_last_relationship_gain_day.items()
            if str(key or "").strip() and str(value or "").strip()
        }
        self.player_name = self.clean_player_name(self.player_name)
        self.player_sex = self.player_sex if self.player_sex in VALID_PLAYER_SEXES else "Female"
        valid_colors = {name for name, _color in PLAYER_COLOR_OPTIONS}
        self.player_color = (
            self.player_color
            if isinstance(self.player_color, str) and self.player_color in valid_colors
            else "White"
        )
        try:
            self.player_birthday_month = max(1, min(12, int(self.player_birthday_month)))
        except Exception:
            self.player_birthday_month = 3
        try:
            self.player_birthday_day = max(1, min(days_in_month(self.player_birthday_month, 1), int(self.player_birthday_day)))
        except Exception:
            self.player_birthday_day = 1
        try:
            self.player_birth_year = int(self.player_birth_year)
        except Exception:
            self.player_birth_year = int(self.year) - 20
        try:
            self.player_generation = max(1, int(self.player_generation))
        except Exception:
            self.player_generation = 1
        try:
            self.player_lifespan_age = max(70, min(115, int(self.player_lifespan_age)))
        except Exception:
            self.player_lifespan_age = 90
        self.aging_and_death_enabled = bool(self.aging_and_death_enabled)
        try:
            self.player_frozen_age = max(0, int(self.player_frozen_age))
        except Exception:
            self.player_frozen_age = 0
        self.player_background = str(
            self.player_background or "First-Generation Farmer"
        )
        self.player_starting_class = str(
            self.player_starting_class or "Vanguard"
        )
        try:
            self.designated_heir_child_id = max(
                0,
                int(self.designated_heir_child_id),
            )
        except Exception:
            self.designated_heir_child_id = 0
        self.dynasty_name = self.clean_player_name(
            self.dynasty_name or f"{self.player_name} Family"
        )
        if not isinstance(self.dynasty_history, list):
            self.dynasty_history = []
        self.dynasty_history = [
            dict(record)
            for record in self.dynasty_history
            if isinstance(record, dict)
        ][-40:]
        if not isinstance(self.dynasty_elders, list):
            self.dynasty_elders = []
        self.dynasty_elders = [
            dict(record)
            for record in self.dynasty_elders
            if isinstance(record, dict)
            and str(record.get("name", "")).strip()
        ][-12:]
        if not isinstance(self.dynasty_kin, list):
            self.dynasty_kin = []
        self.dynasty_kin = [
            dict(record)
            for record in self.dynasty_kin
            if isinstance(record, dict)
            and str(record.get("id", "")).strip()
            and str(record.get("name", "")).strip()
        ][-40:]
        if not isinstance(self.dynasty_heirlooms, list):
            self.dynasty_heirlooms = []
        self.dynasty_heirlooms = [
            dict(record)
            for record in self.dynasty_heirlooms
            if isinstance(record, dict)
            and str(record.get("id", "")).strip()
            and str(record.get("type", "")).strip()
        ][-20:]
        if not isinstance(self.dynasty_transition_log, list):
            self.dynasty_transition_log = []
        self.dynasty_transition_log = [
            str(line)
            for line in self.dynasty_transition_log
            if str(line or "").strip()
        ][-40:]
        try:
            self.dynasty_last_health_warning_year = max(
                0,
                int(self.dynasty_last_health_warning_year),
            )
        except Exception:
            self.dynasty_last_health_warning_year = 0
        try:
            self.dynasty_last_family_update_year = max(
                0,
                int(self.dynasty_last_family_update_year),
            )
        except Exception:
            self.dynasty_last_family_update_year = 0
        self.spouse_moved_to_farm = bool(self.spouse_moved_to_farm)
        self.pregnancy_active = bool(self.pregnancy_active)
        self.pregnancy_parent_npc_id = str(self.pregnancy_parent_npc_id or "")
        self.pregnancy_gestational_parent = str(self.pregnancy_gestational_parent or "")
        for field_name in [
            "pregnancy_start_month", "pregnancy_start_day", "pregnancy_start_year",
            "pregnancy_due_month", "pregnancy_due_day", "pregnancy_due_year",
        ]:
            try:
                setattr(self, field_name, max(0, int(getattr(self, field_name, 0))))
            except Exception:
                setattr(self, field_name, 0)
        if self.children is None:
            self.children = []
        if not isinstance(self.children, list):
            self.children = []
        cleaned_children: List[Dict[str, object]] = []
        max_child_id = 0
        for index, child in enumerate(self.children):
            if not isinstance(child, dict):
                continue
            try:
                child_id = max(1, int(child.get("id", index + 1)))
            except Exception:
                child_id = index + 1
            max_child_id = max(max_child_id, child_id)
            sex = str(child.get("sex", "Female"))
            if sex not in VALID_PLAYER_SEXES:
                sex = "Female" if child_id % 2 else "Male"
            try:
                birth_month = max(1, min(12, int(child.get("birth_month", self.month))))
            except Exception:
                birth_month = self.month
            try:
                birth_year = max(1, int(child.get("birth_year", self.year)))
            except Exception:
                birth_year = self.year
            try:
                birth_day = max(1, min(days_in_month(birth_month, birth_year), int(child.get("birth_day", self.day))))
            except Exception:
                birth_day = self.day
            cleaned_children.append({
                "id": child_id,
                "name": self.clean_player_name(str(child.get("name", f"Child {child_id}"))),
                "sex": sex,
                "birth_month": birth_month,
                "birth_day": birth_day,
                "birth_year": birth_year,
                "parent_npc_id": str(child.get("parent_npc_id", self.spouse_npc_id)),
                "personality_seed": int(child.get("personality_seed", child_id * 97)) if str(child.get("personality_seed", child_id * 97)).lstrip("-").isdigit() else child_id * 97,
                "personality_trait": str(child.get("personality_trait", "") or ""),
                "favorite_gift": str(child.get("favorite_gift", "") or ""),
                "apprentice_path": str(child.get("apprentice_path", "") or ""),
                "starting_class": str(child.get("starting_class", "") or ""),
            })
        self.children = cleaned_children
        try:
            self.next_child_id = max(int(self.next_child_id), max_child_id + 1, 1)
        except Exception:
            self.next_child_id = max(max_child_id + 1, 1)
        if self.pregnancy_active and not (
            1 <= self.pregnancy_due_month <= 12
            and self.pregnancy_due_day >= 1
            and self.pregnancy_due_year >= 1
            and self.pregnancy_parent_npc_id
        ):
            self.pregnancy_active = False
        if self.mail_read_ids is None:
            self.mail_read_ids = []
        if self.mail_claimed_ids is None:
            self.mail_claimed_ids = []
        if self.market_purchase_counts is None:
            self.market_purchase_counts = {}
        if self.completed_errand_ids is None:
            self.completed_errand_ids = []
        if self.completed_resident_request_ids is None:
            self.completed_resident_request_ids = []
        if self.completed_companion_quest_ids is None:
            self.completed_companion_quest_ids = []
        if self.learned_recipe_ids is None:
            self.learned_recipe_ids = []
        if self.library_research_ids is None:
            self.library_research_ids = []
        if self.museum_donated_record_ids is None:
            self.museum_donated_record_ids = []
        if self.museum_donation_counts is None:
            self.museum_donation_counts = {}
        if self.museum_reward_claims is None:
            self.museum_reward_claims = []
        if self.museum_exhibit_unlocks is None:
            self.museum_exhibit_unlocks = []
        self.town_development_stage = normalize_town_development_stage(self.town_development_stage)
        self.unlocked_town_buildings = normalize_unlocked_town_buildings(self.unlocked_town_buildings, self.town_development_stage)
        if self.completed_town_project_ids is None:
            self.completed_town_project_ids = []
        if self.completed_town_restoration_project_ids is None:
            self.completed_town_restoration_project_ids = []
        if self.completed_mine_special_ids is None:
            self.completed_mine_special_ids = []
        if self.attended_festival_ids is None:
            self.attended_festival_ids = []
        if self.completed_bulletin_job_ids is None:
            self.completed_bulletin_job_ids = []
        if self.completed_scene_ids is None:
            self.completed_scene_ids = []
        if self.seen_scene_ids is None:
            self.seen_scene_ids = []
        if self.scene_flags is None:
            self.scene_flags = []
        self.active_scene_id = str(self.active_scene_id or "")
        try:
            self.active_scene_step_index = max(0, int(self.active_scene_step_index))
        except Exception:
            self.active_scene_step_index = 0
        if self.active_food_buffs is None:
            self.active_food_buffs = {}
        if not isinstance(self.active_food_buffs, dict):
            self.active_food_buffs = {}
        if self.fish_ponds is None:
            self.fish_ponds = {}
        if not isinstance(self.fish_ponds, dict):
            self.fish_ponds = {}
        if self.artisan_processors is None:
            self.artisan_processors = {}
        if not isinstance(self.artisan_processors, dict):
            self.artisan_processors = {}
        self.completed_errand_ids = clean_string_list(self.completed_errand_ids)
        self.completed_resident_request_ids = clean_string_list(self.completed_resident_request_ids)
        self.completed_companion_quest_ids = clean_string_list(self.completed_companion_quest_ids)
        self.learned_recipe_ids = clean_string_list(self.learned_recipe_ids)
        self.library_research_ids = clean_string_list(self.library_research_ids)
        self.museum_donated_record_ids = sorted({value for value in clean_string_list(self.museum_donated_record_ids) if value.strip()})
        if not isinstance(self.museum_donation_counts, dict):
            self.museum_donation_counts = {}
        cleaned_museum_counts: Dict[str, int] = {}
        for key, value in self.museum_donation_counts.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            try:
                cleaned_museum_counts[clean_key] = max(0, int(value))
            except Exception:
                continue
        self.museum_donation_counts = cleaned_museum_counts
        self.museum_reward_claims = sorted({value for value in clean_string_list(self.museum_reward_claims) if value.strip()})
        self.museum_exhibit_unlocks = sorted({value for value in clean_string_list(self.museum_exhibit_unlocks) if value.strip()})
        self.completed_town_project_ids = clean_string_list(self.completed_town_project_ids)
        self.completed_town_restoration_project_ids = [
            value
            for value in clean_string_list(self.completed_town_restoration_project_ids)
            if value in TOWN_RESTORATION_PROJECT_DATA
        ]
        recalculate_town_development_stage(self)
        self.completed_mine_special_ids = clean_string_list(self.completed_mine_special_ids)
        self.attended_festival_ids = clean_string_list(self.attended_festival_ids)
        self.completed_bulletin_job_ids = clean_string_list(self.completed_bulletin_job_ids)
        self.completed_scene_ids = clean_string_list(self.completed_scene_ids)
        self.seen_scene_ids = clean_string_list(self.seen_scene_ids)
        self.scene_flags = clean_string_list(self.scene_flags)
        cleaned_buffs: Dict[str, Dict[str, int]] = {}
        for buff_name, buff_data in (self.active_food_buffs or {}).items():
            if not isinstance(buff_data, dict):
                continue
            try:
                charges = max(0, int(buff_data.get("charges", 0)))
                discount = max(0, int(buff_data.get("discount", 0)))
            except Exception:
                continue
            if charges > 0 and discount > 0:
                cleaned_buffs[str(buff_name)] = {"charges": charges, "discount": discount}
        self.active_food_buffs = cleaned_buffs
        cleaned_ponds: Dict[str, Dict[str, object]] = {}
        for pond_key, pond_data in (self.fish_ponds or {}).items():
            if not isinstance(pond_data, dict):
                continue
            fish = str(pond_data.get("fish", ""))
            if fish and fish not in FISH_DATA:
                continue
            try:
                count = max(0, int(pond_data.get("count", 0)))
                days = max(0, int(pond_data.get("days", 0)))
                ready = max(0, int(pond_data.get("ready", 0)))
            except Exception:
                continue
            cleaned_ponds[str(pond_key)] = {"fish": fish, "count": count, "days": days, "ready": ready}
        self.fish_ponds = cleaned_ponds
        cleaned_processors: Dict[str, Dict[str, object]] = {}
        for proc_key, proc_data in (self.artisan_processors or {}).items():
            if not isinstance(proc_data, dict):
                continue
            try:
                days_left = max(0, int(proc_data.get("days_left", 0)))
                qty = max(0, int(proc_data.get("qty", 0)))
            except Exception:
                continue
            input_item = str(proc_data.get("input", ""))
            output_item = str(proc_data.get("output", ""))
            if output_item and qty > 0:
                cleaned_processors[str(proc_key)] = {"input": input_item, "output": output_item, "qty": qty, "days_left": days_left}
        self.artisan_processors = cleaned_processors
        self.mail_read_ids = clean_string_list(self.mail_read_ids)
        self.mail_claimed_ids = clean_string_list(self.mail_claimed_ids)
        self.owned_tools = clean_string_list(self.owned_tools)
        if not isinstance(self.tool_levels, dict):
            self.tool_levels = default_tool_levels_for(self.owned_tools)
        if self.farm_expansions is None:
            self.farm_expansions = []
        if self.house_upgrades is None:
            self.house_upgrades = []
        if not self.held_object:
            self.held_object = None
        if not isinstance(self.wilderness_seed, int):
            self.wilderness_seed = 1337
        try:
            self.wilderness_chunk_x = int(self.wilderness_chunk_x)
        except Exception:
            self.wilderness_chunk_x = 0
        try:
            self.wilderness_chunk_y = int(self.wilderness_chunk_y)
        except Exception:
            self.wilderness_chunk_y = 0
        try:
            self.wilderness_chunks_visited = max(1, int(self.wilderness_chunks_visited))
        except Exception:
            self.wilderness_chunks_visited = 1
        try:
            self.wilderness_animals_seen = max(0, int(self.wilderness_animals_seen))
        except Exception:
            self.wilderness_animals_seen = 0
        if self.owned_wilderness_claims is None:
            self.owned_wilderness_claims = {}
        if not isinstance(self.owned_wilderness_claims, dict):
            self.owned_wilderness_claims = {}
        cleaned_claims: Dict[str, Dict[str, object]] = {}
        for claim_key, claim in (self.owned_wilderness_claims or {}).items():
            if not isinstance(claim, dict):
                continue
            key = str(claim_key)
            try:
                cx, cy = [int(part) for part in key.split(",", 1)]
            except Exception:
                try:
                    cx = int(claim.get("chunk_x", 0))
                    cy = int(claim.get("chunk_y", 0))
                    key = f"{cx},{cy}"
                except Exception:
                    continue
            record = dict(claim)
            record["chunk_x"] = cx
            record["chunk_y"] = cy
            farm_type_id = claim_farm_type_id_for_record(record)
            farm_type = farm_claim_type_data(farm_type_id)
            record["farm_type_id"] = farm_type_id
            record["farm_type"] = str(farm_type.get("name", "Meadow Farm"))
            record["type"] = str(record.get("farm_type") or farm_type.get("name", "Meadow Farm"))
            record["traits"] = str(record.get("traits") or farm_type.get("focus", "raw land"))
            record["development_stage"] = str(record.get("development_stage") or "Raw")
            record["name"] = str(record.get("name") or f"{record['farm_type']} ({cx},{cy})")
            record["marker_x"] = int(record.get("marker_x", 0) or 0)
            record["marker_y"] = int(record.get("marker_y", 0) or 0)
            record["shipping_x"] = int(record.get("shipping_x", 0) or 0)
            record["shipping_y"] = int(record.get("shipping_y", 0) or 0)
            cleaned_claims[key] = record
        self.owned_wilderness_claims = cleaned_claims
        self.wilderness_settlements = sanitize_wilderness_settlements(self.wilderness_settlements)
        self.procedural_settlement_populations = sanitize_procedural_settlement_populations(
            self.procedural_settlement_populations
        )
        self.player_properties = sanitize_player_properties(self.player_properties)
        self.player_businesses = sanitize_player_businesses(self.player_businesses)
        self.player_trade_routes = sanitize_player_trade_routes(
            self.player_trade_routes
        )
        self.primary_residence_id = str(self.primary_residence_id or "farmhouse")
        if (
            self.primary_residence_id != "farmhouse"
            and self.primary_residence_id not in self.player_properties
        ):
            self.primary_residence_id = "farmhouse"
        self.civic_profile = sanitize_civic_profile(self.civic_profile)
        if not isinstance(self.civic_income_log, list):
            self.civic_income_log = []
        self.civic_income_log = [
            str(line)
            for line in self.civic_income_log
            if str(line or "").strip()
        ][-30:]
        self.current_procedural_settlement_key = str(
            self.current_procedural_settlement_key or ""
        )
        self.current_procedural_building_id = str(
            self.current_procedural_building_id or ""
        )
        try:
            self.procedural_settlement_return_x = int(
                self.procedural_settlement_return_x or 0
            )
            self.procedural_settlement_return_y = int(
                self.procedural_settlement_return_y or 0
            )
        except Exception:
            self.procedural_settlement_return_x = 0
            self.procedural_settlement_return_y = 0
        for attr in [
            "overworld_cursor_chunk_x",
            "overworld_cursor_chunk_y",
            "overworld_return_chunk_x",
            "overworld_return_chunk_y",
            "overworld_return_x",
            "overworld_return_y",
        ]:
            try:
                setattr(self, attr, int(getattr(self, attr)))
            except Exception:
                setattr(self, attr, 0)
        self.cave_return_location = self.cave_return_location if self.cave_return_location else "Wilderness"
        try:
            self.cave_return_chunk_x = int(self.cave_return_chunk_x)
        except Exception:
            self.cave_return_chunk_x = 0
        try:
            self.cave_return_chunk_y = int(self.cave_return_chunk_y)
        except Exception:
            self.cave_return_chunk_y = 0
        try:
            self.cave_return_x = int(self.cave_return_x)
            self.cave_return_y = int(self.cave_return_y)
        except Exception:
            self.cave_return_x = 0
            self.cave_return_y = 0
        self.current_cave_key = str(self.current_cave_key or "")
        try:
            self.wilderness_caves_discovered = max(0, int(self.wilderness_caves_discovered))
        except Exception:
            self.wilderness_caves_discovered = 0
        self.current_dungeon_key = str(self.current_dungeon_key or "")
        self.current_dungeon_floor = 1
        try:
            self.wilderness_dungeons_discovered = max(0, int(self.wilderness_dungeons_discovered))
        except Exception:
            self.wilderness_dungeons_discovered = 0
        if not isinstance(self.wilderness_dungeon_state, dict):
            self.wilderness_dungeon_state = {}
        else:
            cleaned_dungeon_state: Dict[str, Dict[str, object]] = {}
            for dungeon_key, record in self.wilderness_dungeon_state.items():
                if isinstance(record, dict):
                    cleaned_dungeon_state[str(dungeon_key)] = dict(record)
            self.wilderness_dungeon_state = cleaned_dungeon_state
        try:
            self.wilderness_strongholds_cleared = max(0, int(self.wilderness_strongholds_cleared))
        except Exception:
            self.wilderness_strongholds_cleared = 0
        if not isinstance(self.wilderness_stronghold_state, dict):
            self.wilderness_stronghold_state = {}
        else:
            cleaned_stronghold_state: Dict[str, Dict[str, object]] = {}
            for stronghold_key, record in self.wilderness_stronghold_state.items():
                if isinstance(record, dict):
                    cleaned_stronghold_state[str(stronghold_key)] = dict(record)
            self.wilderness_stronghold_state = cleaned_stronghold_state
        self.mine_floor = normalize_mine_floor(self.mine_floor)
        self.deepest_mine_floor = max(normalize_mine_floor(self.deepest_mine_floor), self.mine_floor)
        self.unlocked_mine_elevators = sorted(
            set([1] + normalize_mine_floor_list(self.unlocked_mine_elevators))
        )
        self.cleared_mine_floors = normalize_mine_floor_list(self.cleared_mine_floors)
        self.unlocked_mine_down_stairs = [
            floor for floor in normalize_mine_floor_list(self.unlocked_mine_down_stairs)
            if floor < MINE_MAX_FLOOR
        ]
        self.mine_floor_clear_rewards_claimed = normalize_mine_floor_list(self.mine_floor_clear_rewards_claimed)
        if not isinstance(self.mine_seed, int):
            self.mine_seed = 4242
        for attr in ["mine_combat_victories", "mine_combat_defeats", "mine_combat_flees", "mine_enemies_defeated"]:
            try:
                setattr(self, attr, max(0, int(getattr(self, attr, 0))))
            except Exception:
                setattr(self, attr, 0)
        for attr, limit in [("mine_recent_combat_maps", 6), ("mine_recent_combat_signatures", 8)]:
            value = getattr(self, attr, None)
            if not isinstance(value, list):
                value = []
            setattr(self, attr, [str(entry)[:160] for entry in value if str(entry).strip()][-limit:])
        combat_defaults = {
            "combat_level": DEFAULT_COMBAT_LEVEL,
            "combat_exp": DEFAULT_COMBAT_EXP,
            "combat_exp_to_next": DEFAULT_COMBAT_EXP_TO_NEXT,
            "combat_max_hp": DEFAULT_COMBAT_MAX_HP,
            "combat_current_hp": DEFAULT_COMBAT_MAX_HP,
            "combat_attack": DEFAULT_COMBAT_ATTACK,
            "combat_defense": DEFAULT_COMBAT_DEFENSE,
            "combat_focus": DEFAULT_COMBAT_MAX_FOCUS,
            "combat_max_focus": DEFAULT_COMBAT_MAX_FOCUS,
            "combat_skill_points": DEFAULT_COMBAT_SKILL_POINTS,
        }
        for attr, default in combat_defaults.items():
            try:
                value = int(getattr(self, attr, default))
            except Exception:
                value = default
            if attr in ["combat_level", "combat_exp_to_next", "combat_max_hp", "combat_attack"]:
                value = max(1, value)
            else:
                value = max(0, value)
            setattr(self, attr, value)
        self.combat_current_hp = max(0, int(self.combat_current_hp))
        self.combat_focus = max(0, int(self.combat_focus))
        self.equipped_weapon = str(self.equipped_weapon or DEFAULT_COMBAT_WEAPON)
        if self.equipped_weapon not in COMBAT_WEAPON_DATA:
            self.equipped_weapon = DEFAULT_COMBAT_WEAPON
        self.equipped_armor = str(self.equipped_armor or DEFAULT_COMBAT_ARMOR)
        if self.equipped_armor not in COMBAT_ARMOR_DATA:
            self.equipped_armor = DEFAULT_COMBAT_ARMOR
        self.equipped_accessory = str(self.equipped_accessory or DEFAULT_COMBAT_ACCESSORY)
        if self.equipped_accessory not in COMBAT_ACCESSORY_DATA:
            self.equipped_accessory = DEFAULT_COMBAT_ACCESSORY
        weapon = COMBAT_WEAPON_DATA.get(self.equipped_weapon, {})
        armor = COMBAT_ARMOR_DATA.get(self.equipped_armor, {})
        accessory = COMBAT_ACCESSORY_DATA.get(self.equipped_accessory, {})
        player_progress = self.combat_party_progress.get("player", {}) if isinstance(self.combat_party_progress, dict) else {}
        if not isinstance(player_progress, dict):
            player_progress = {}
        try:
            tactical_hp_bonus = max(0, int(player_progress.get("hp_bonus", 0) or 0))
        except Exception:
            tactical_hp_bonus = 0
        try:
            tactical_focus_bonus = max(0, int(player_progress.get("mp_bonus", 0) or 0))
        except Exception:
            tactical_focus_bonus = 0
        effective_max_hp = (
            int(self.combat_max_hp)
            + int(weapon.get("max_hp", 0))
            + int(armor.get("max_hp", 0))
            + int(accessory.get("max_hp", 0))
            + tactical_hp_bonus
        )
        effective_max_focus = (
            int(self.combat_max_focus)
            + int(weapon.get("max_focus", 0))
            + int(armor.get("max_focus", 0))
            + int(accessory.get("max_focus", 0))
            + tactical_focus_bonus
        )
        self.combat_current_hp = max(0, min(int(self.combat_current_hp), max(1, effective_max_hp)))
        self.combat_focus = max(0, min(int(self.combat_focus), max(0, effective_max_focus)))
        if self.shipped_today_items is None:
            self.shipped_today_items = {}
        if self.last_shipping_report is None:
            self.last_shipping_report = []
        if not isinstance(self.last_automation_report, list):
            self.last_automation_report = []
        self.last_automation_report = [str(line) for line in self.last_automation_report if line is not None][-24:]
        if not isinstance(self.automation_machines, dict):
            self.automation_machines = {}
        cleaned_machines: Dict[str, Dict[str, object]] = {}
        for machine_key, machine_data in self.automation_machines.items():
            if not isinstance(machine_data, dict):
                continue
            clean_key = str(machine_key or "").strip()
            if not clean_key:
                continue
            seed_crop = str(machine_data.get("seed_crop", "") or "")
            if seed_crop and seed_crop not in CROP_DATA:
                seed_crop = ""
            try:
                seed_qty = max(0, int(machine_data.get("seed_qty", 0)))
            except Exception:
                seed_qty = 0
            last_message = str(machine_data.get("last_message", "") or "")[:120]
            cleaned_machines[clean_key] = {
                "seed_crop": seed_crop,
                "seed_qty": seed_qty,
                "last_message": last_message,
            }
        self.automation_machines = cleaned_machines
        if self.fishing_pool is None:
            self.fishing_pool = []
        for tool_name, level in default_tool_levels_for(self.owned_tools).items():
            self.tool_levels.setdefault(tool_name, level)

    @property
    def season(self) -> str:
        return season_for_month(self.month)

    @property
    def weekday(self) -> str:
        return weekday_for_date(self.month, self.day, self.year)

    @property
    def date_label(self) -> str:
        return format_date(self.month, self.day, self.year)

    @staticmethod
    def clean_player_name(value: object) -> str:
        cleaned = "".join(ch for ch in str(value or "Farmer").strip() if ch.isprintable())
        cleaned = " ".join(cleaned.split())
        return cleaned[:16] or "Farmer"

    @property
    def available_tools(self) -> List[str]:
        tools = list(TOOLS)
        for tool_name in OPTIONAL_TOOL_ORDER:
            if tool_name in (self.owned_tools or []):
                tools.append(tool_name)
        return tools

    @property
    def selected_tool(self) -> str:
        tools = self.available_tools
        if not tools:
            return "Hoe"
        self.selected_tool_index %= len(tools)
        return tools[self.selected_tool_index]

def migrate_legacy_calendar_state(state_data: Dict[str, object]):
    """Translate pre-calendar saves that stored an abstract season/day."""
    if "month" not in state_data:
        try:
            old_day = max(1, int(state_data.get("day", 1)))
        except (TypeError, ValueError):
            old_day = 1
        try:
            old_year = max(1, int(state_data.get("year", 1)))
        except (TypeError, ValueError):
            old_year = 1
        old_season_name = "Spring"
        if "season_index" in state_data:
            try:
                old_season_name = SEASONS[int(state_data.get("season_index", 0))]
            except Exception:
                old_season_name = "Spring"
        old_season_name = state_data.get("season", old_season_name)
        month, day, year = migrate_abstract_day_to_date(old_day, old_year, old_season_name)
        state_data["month"] = month
        state_data["day"] = day
        state_data["year"] = year

    state_data.pop("season_index", None)
    state_data.pop("season", None)

def apply_loaded_state_defaults(state_data: Dict[str, object]):
    for key, default_value in LOADED_STATE_DEFAULTS.items():
        if key not in state_data:
            state_data[key] = copy_default_value(default_value)
        elif isinstance(default_value, dict) and not isinstance(state_data.get(key), dict):
            state_data[key] = copy_default_value(default_value)
        elif isinstance(default_value, list):
            value = state_data.get(key)
            state_data[key] = list(value) if isinstance(value, (list, tuple, set)) else copy_default_value(default_value)

    if "tool_levels" not in state_data:
        owned_tools = state_data.get("owned_tools", [])
        if not isinstance(owned_tools, (list, tuple, set)):
            owned_tools = []
        state_data["tool_levels"] = default_tool_levels_for(owned_tools)

def prepare_loaded_state_data(state_data: Dict[str, object]) -> Dict[str, object]:
    state_data = dict(state_data)
    legacy_town_access = "town_development_stage" not in state_data and "unlocked_town_buildings" not in state_data
    legacy_mine_progress_without_clear_state = not any(
        key in state_data
        for key in ["cleared_mine_floors", "unlocked_mine_down_stairs", "mine_floor_clear_rewards_claimed"]
    )
    migrate_legacy_calendar_state(state_data)
    apply_loaded_state_defaults(state_data)
    try:
        state_data["year"] = max(1, int(state_data.get("year", 1)))
    except (TypeError, ValueError):
        state_data["year"] = 1
    try:
        state_data["month"] = max(1, min(12, int(state_data.get("month", 3))))
    except (TypeError, ValueError):
        state_data["month"] = 3
    try:
        state_data["day"] = max(
            1,
            min(
                days_in_month(state_data["month"], state_data["year"]),
                int(state_data.get("day", 1)),
            ),
        )
    except (TypeError, ValueError):
        state_data["day"] = 1

    if legacy_town_access:
        state_data["town_development_stage"] = 3
        state_data["unlocked_town_buildings"] = restored_unlocked_town_buildings()
    else:
        state_data["town_development_stage"] = normalize_town_development_stage(state_data.get("town_development_stage", 0))
        state_data["unlocked_town_buildings"] = normalize_unlocked_town_buildings(
            state_data.get("unlocked_town_buildings"),
            state_data["town_development_stage"],
        )

    # Never resume a half-cast fishing action from a save file.
    state_data["fishing_active"] = False

    if state_data.get("location") not in VALID_GAME_LOCATIONS:
        state_data["location"] = "Farm"
    location_building_id = town_building_id_for_location(str(state_data.get("location", "")))
    if location_building_id and location_building_id not in set(state_data.get("unlocked_town_buildings", [])):
        door = TOWN_DOORS.get(location_building_id, (41, 20))
        state_data["location"] = "Town"
        state_data["player_x"] = int(door[0])
        state_data["player_y"] = int(door[1]) + 1
        state_data["facing"] = "DOWN"
    if state_data.get("tool_target_mode") not in VALID_TOOL_TARGET_MODES:
        state_data["tool_target_mode"] = "FRONT"
    state_data["player_name"] = GameState.clean_player_name(state_data.get("player_name", "Farmer"))
    if state_data.get("player_sex") not in VALID_PLAYER_SEXES:
        state_data["player_sex"] = "Female"
    if (
        not isinstance(state_data.get("player_color"), str)
        or state_data.get("player_color") not in {name for name, _color in PLAYER_COLOR_OPTIONS}
    ):
        state_data["player_color"] = "White"
    normalize_mine_progress_state_data(state_data, legacy_mine_progress_without_clear_state)
    try:
        birthday_month = max(1, min(12, int(state_data.get("player_birthday_month", 3))))
    except Exception:
        birthday_month = 3
    try:
        birthday_day = max(1, min(days_in_month(birthday_month, 1), int(state_data.get("player_birthday_day", 1))))
    except Exception:
        birthday_day = 1
    state_data["player_birthday_month"] = birthday_month
    state_data["player_birthday_day"] = birthday_day
    try:
        state_data["player_birth_year"] = int(
            state_data.get(
                "player_birth_year",
                int(state_data.get("year", 1)) - 20,
            )
        )
    except Exception:
        state_data["player_birth_year"] = int(state_data.get("year", 1)) - 20
    try:
        state_data["player_generation"] = max(
            1,
            int(state_data.get("player_generation", 1)),
        )
    except Exception:
        state_data["player_generation"] = 1
    try:
        state_data["player_lifespan_age"] = max(
            70,
            min(115, int(state_data.get("player_lifespan_age", 90))),
        )
    except Exception:
        state_data["player_lifespan_age"] = 90
    state_data["dynasty_name"] = GameState.clean_player_name(
        state_data.get(
            "dynasty_name",
            f"{state_data['player_name']} Family",
        )
    )
    state_data["spouse_moved_to_farm"] = bool(state_data.get("spouse_moved_to_farm", False))

    try:
        selected_tool_index = int(state_data.get("selected_tool_index", 0))
    except Exception:
        selected_tool_index = 0
    if selected_tool_index >= len(TOOLS):
        selected_tool_index = 0
    state_data["selected_tool_index"] = selected_tool_index

    valid_state_fields = {field.name for field in fields(GameState)}
    return {key: value for key, value in state_data.items() if key in valid_state_fields}



__all__ = [
    'farm_claim_type_data',
    'claim_farm_type_id_for_record',
    'quality_item_name',
    'parse_quality_item',
    'quality_sell_price',
    'normalize_town_development_stage',
    'town_stage_label',
    'initial_unlocked_town_buildings_for_new_game',
    'restored_unlocked_town_buildings',
    'unlocked_town_buildings_for_stage',
    'normalize_unlocked_town_buildings',
    'is_town_building_unlocked',
    'unlock_town_building',
    'town_building_status_label',
    'locked_building_message',
    'town_building_id_for_location',
    'town_project_unlocks_building',
    'town_restoration_project_completed',
    'town_restoration_project_locked_reasons',
    'available_town_restoration_projects',
    'can_complete_town_restoration_project',
    'town_restoration_missing_requirements',
    'format_town_restoration_cost',
    'recalculate_town_development_stage',
    'normalize_mine_floor',
    'normalize_mine_floor_list',
    'is_mine_floor_cleared',
    'mark_mine_floor_cleared',
    'mine_floor_down_stairs_unlocked',
    'unlock_mine_floor_down_stairs',
    'mine_floor_clear_reward_claimed',
    'mark_mine_floor_clear_reward_claimed',
    'normalize_mine_progress_state_data',
    'Crop',
    'ensure_inventory_catalog',
    'GameState',
    'migrate_legacy_calendar_state',
    'apply_loaded_state_defaults',
    'prepare_loaded_state_data'
]
