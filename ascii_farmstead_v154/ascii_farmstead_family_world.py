from __future__ import annotations

"""Seamless-world marriage, household schedules, and family planning.

This mixin deliberately builds on the mature relationship and child systems in
``NpcMixin``.  It gives those records a world-facing layer without duplicating
birth, aging, inheritance, dialogue, or relationship ownership.
"""

from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import (
    INFRASTRUCTURE_DATA,
    LEFT_PANEL_HEIGHT,
    LEFT_PANEL_WIDTH,
    MENU_BACK,
)
from ascii_farmstead_furniture import furniture_component_at, furniture_walkable_kind
from ascii_farmstead_helpers import format_date
from ascii_farmstead_ui import MenuItem


FAMILY_WORLD_VERSION = 1

FAMILY_PRIORITIES: Dict[str, Dict[str, str]] = {
    "Togetherness": {
        "summary": "Shared meals, conversation, and time at home come first.",
        "benefit": "Weekly check-ins and outings build additional household bond.",
    },
    "Prosperity": {
        "summary": "The household coordinates work, errands, and practical goals.",
        "benefit": "Household help is more likely to focus on useful supplies.",
    },
    "Learning": {
        "summary": "Library visits, lessons, and each child's interests come first.",
        "benefit": "Family outings provide additional learning progress.",
    },
    "Adventure": {
        "summary": "The family makes room for travel, fishing, and exploration.",
        "benefit": "Outdoor outings create stronger memories and child confidence.",
    },
    "Rest": {
        "summary": "A calmer schedule protects recovery and unstructured time.",
        "benefit": "Living with family provides one additional sleep stamina point.",
    },
}

FAMILY_OUTINGS: Dict[str, Dict[str, object]] = {
    "Town Picnic": {
        "destination": "Town green",
        "cost": 0,
        "minutes": 120,
        "bond": 8,
        "topic": "Community",
        "minimum_stage": "Toddler",
    },
    "Fishing Afternoon": {
        "destination": "Farm pond",
        "cost": 0,
        "minutes": 150,
        "bond": 9,
        "topic": "Nature",
        "minimum_stage": "Young Child",
    },
    "Library Visit": {
        "destination": "Library",
        "cost": 0,
        "minutes": 90,
        "bond": 6,
        "topic": "Study",
        "minimum_stage": "Toddler",
    },
    "Farm Workday": {
        "destination": "Family farm",
        "cost": 0,
        "minutes": 150,
        "bond": 7,
        "topic": "Farming",
        "minimum_stage": "Young Child",
    },
    "Wilderness Walk": {
        "destination": "The safe regional trail",
        "cost": 25,
        "minutes": 180,
        "bond": 10,
        "topic": "Nature",
        "minimum_stage": "Child",
    },
    "Festival Trip": {
        "destination": "Town festival grounds",
        "cost": 75,
        "minutes": 180,
        "bond": 11,
        "topic": "Community",
        "minimum_stage": "Toddler",
    },
    "Mine Expedition": {
        "destination": "The upper mine",
        "cost": 40,
        "minutes": 180,
        "bond": 12,
        "topic": "Combat",
        "minimum_stage": "Teen",
    },
}

FAMILY_STAGE_ORDER = {
    "Newborn": 0,
    "Infant": 1,
    "Toddler": 2,
    "Young Child": 3,
    "Child": 4,
    "Teen": 5,
    "Young Adult": 6,
}


class FamilyWorldMixin:
    """World-presence and shared-planning layer for the player's household."""

    def ensure_family_world_state(self) -> Dict[str, object]:
        state = getattr(self.state, "family_world_state", None)
        if not isinstance(state, dict):
            state = {}
            self.state.family_world_state = state
        state["version"] = FAMILY_WORLD_VERSION
        priority = str(state.get("weekly_priority", "Togetherness"))
        state["weekly_priority"] = priority if priority in FAMILY_PRIORITIES else "Togetherness"
        state["priority_week"] = str(state.get("priority_week", ""))
        state["last_checkin_week"] = str(state.get("last_checkin_week", ""))
        state["last_schedule_day"] = str(state.get("last_schedule_day", ""))
        state["member_schedules"] = (
            state.get("member_schedules")
            if isinstance(state.get("member_schedules"), dict)
            else {}
        )
        outing = state.get("planned_outing")
        state["planned_outing"] = outing if isinstance(outing, dict) else {}
        history = state.get("outing_history")
        state["outing_history"] = [dict(row) for row in history if isinstance(row, dict)][-20:] if isinstance(history, list) else []
        wedding = state.get("wedding_plan")
        if not isinstance(wedding, dict):
            wedding = {}
        wedding.setdefault("venue", "Town Hall")
        wedding.setdefault("style", "Community")
        wedding.setdefault("guest_focus", "Friends and family")
        state["wedding_plan"] = wedding
        return state

    def family_world_week_key(self) -> str:
        week = max(0, (int(self.absolute_game_day()) - 1) // 7)
        return f"{int(self.state.year)}:{week}"

    def family_weekly_priority(self) -> str:
        return str(self.ensure_family_world_state().get("weekly_priority", "Togetherness"))

    def family_household_home_label(self) -> str:
        if hasattr(self, "household_residence_label"):
            return str(self.household_residence_label())
        return "the farmhouse"

    def family_household_uses_farmhouse(self) -> bool:
        if not hasattr(self, "household_residence_property"):
            return True
        return self.household_residence_property() is None

    def family_world_day_index(self) -> int:
        return (int(self.absolute_game_day()) - 1) % 7

    def family_world_schedule_phase(self) -> str:
        return str(self.town_routine_phase())

    def family_world_bad_weather(self) -> bool:
        return bool(self.town_weather_is_bad_for_routines())

    def family_world_outing_ready(self) -> bool:
        outing = self.ensure_family_world_state().get("planned_outing", {})
        return bool(outing and int(outing.get("due_ordinal", 10 ** 9)) <= int(self.absolute_game_day()))

    def family_world_outing_destination(self) -> str:
        outing = self.ensure_family_world_state().get("planned_outing", {})
        return str(outing.get("destination", "")) if self.family_world_outing_ready() else ""

    def family_world_schedule_cache_signature(self) -> Tuple[object, ...]:
        state = self.ensure_family_world_state()
        outing = state.get("planned_outing", {})
        property_record = self.household_residence_property() if hasattr(self, "household_residence_property") else None
        return (
            int(self.state.year), int(self.state.month), int(self.state.day),
            self.family_world_schedule_phase(), str(self.state.weather),
            str(getattr(self.state, "spouse_npc_id", "")),
            bool(getattr(self.state, "spouse_moved_to_farm", False)),
            self.spouse_support_mode(),
            str(property_record.get("id", property_record.get("building_id", ""))) if property_record else "farmhouse",
            str(outing.get("type", "")), int(outing.get("due_ordinal", 0) or 0),
        )

    def family_world_schedule_cache(self) -> Dict[Tuple[object, ...], Dict[str, object]]:
        signature = self.family_world_schedule_cache_signature()
        if getattr(self, "_family_world_schedule_cache_signature", None) != signature:
            self._family_world_schedule_cache_signature = signature
            self._family_world_schedule_cache = {}
        cache = getattr(self, "_family_world_schedule_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._family_world_schedule_cache = cache
        return cache

    def family_child_destination(self, child: Dict[str, object]) -> Dict[str, object]:
        child_key = (
            "child", int(child.get("id", 0) or 0), self.household_child_stage(child),
            str(child.get("apprentice_path", "")),
        )
        cache = self.family_world_schedule_cache()
        if child_key not in cache:
            cache[child_key] = self._compute_family_child_destination(child)
        return cache[child_key]

    def _compute_family_child_destination(self, child: Dict[str, object]) -> Dict[str, object]:
        stage = self.household_child_stage(child)
        phase = self.family_world_schedule_phase()
        day_index = self.family_world_day_index()
        outing_destination = self.family_world_outing_destination()
        if outing_destination:
            outing = self.ensure_family_world_state().get("planned_outing", {})
            minimum = str(FAMILY_OUTINGS.get(str(outing.get("type", "")), {}).get("minimum_stage", "Toddler"))
            if FAMILY_STAGE_ORDER.get(stage, 0) >= FAMILY_STAGE_ORDER.get(minimum, 0):
                if outing_destination == "Library":
                    return {"location": "LibraryInterior", "label": "the Library", "activity": "waiting for the family outing"}
                if outing_destination in {"Family farm", "Farm pond"}:
                    return {"location": "Farm", "label": outing_destination.lower(), "activity": "getting ready for the family outing"}
                return {"location": "Town", "label": outing_destination.lower(), "activity": "waiting for the family outing"}
        if stage in {"Newborn", "Infant", "Toddler"}:
            return {"location": "Home", "label": self.family_household_home_label(), "activity": self.household_child_activity_label(child)}
        if phase in {"wake", "late", "evening"} or self.family_world_bad_weather() and stage == "Young Child":
            return {"location": "Home", "label": self.family_household_home_label(), "activity": self.household_child_activity_label(child)}
        if phase == "lunch":
            return {"location": "Town", "label": "the town green", "activity": "meeting family and neighbors around midday"}
        if stage == "Young Child":
            if day_index in {0, 2, 4} and phase == "work_morning":
                return {"location": "LibraryInterior", "label": "the Library", "activity": "attending a supervised reading lesson"}
            return {"location": "Farm", "label": "the family farm", "activity": "playing and helping in the safe farmyard"}
        if stage == "Child":
            if phase == "work_morning":
                return {"location": "LibraryInterior", "label": "the Library", "activity": "studying with the town's learning group"}
            return {"location": "Farm" if day_index % 2 == 0 else "Town", "label": "the family farm" if day_index % 2 == 0 else "the market lane", "activity": "practicing a chore beyond the house"}
        if stage == "Teen":
            if phase == "work_morning" and day_index in {1, 3}:
                return {"location": "LibraryInterior", "label": "the Library", "activity": "pursuing independent study"}
            if phase == "work_afternoon" and day_index in {0, 2, 4}:
                return {"location": "MarketRowInterior", "label": "Market Row", "activity": "running a household errand"}
            return {"location": "Town", "label": "the town streets", "activity": "spending independent time around town"}
        path = str(child.get("apprentice_path", "Helper"))
        apprentice_locations = {
            "Scholar": ("LibraryInterior", "the Library", "continuing an apprenticeship in study"),
            "Healer": ("ClinicInterior", "the Clinic", "learning practical care"),
            "Artisan": ("BlacksmithInterior", "the Blacksmith", "learning an artisan trade"),
            "Ranger": ("Town", "the north road", "preparing for ranger work"),
            "Merchant": ("MarketRowInterior", "Market Row", "learning the rhythms of trade"),
            "Farmer": ("Farm", "the family farm", "developing an independent farm specialty"),
        }
        location, label, activity = apprentice_locations.get(path, ("Town", "the town center", "building an independent routine"))
        return {"location": location, "label": label, "activity": activity}

    def family_spouse_destination(self, npc: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        npc = npc or self.npc_record_by_id(str(getattr(self.state, "spouse_npc_id", "")))
        spouse_key = ("spouse", str(npc.get("id", "")) if npc else "")
        cache = self.family_world_schedule_cache()
        if spouse_key not in cache:
            cache[spouse_key] = self._compute_family_spouse_destination(npc)
        return cache[spouse_key]

    def _compute_family_spouse_destination(self, npc: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        npc = npc or self.npc_record_by_id(str(getattr(self.state, "spouse_npc_id", "")))
        phase = self.family_world_schedule_phase()
        home = self.family_household_home_label()
        if not npc or not self.spouse_lives_on_farm():
            return {"location": "Original", "label": "their own home", "activity": "following their established routine"}
        outing_destination = self.family_world_outing_destination()
        if outing_destination:
            if outing_destination == "Library":
                return {"location": "LibraryInterior", "label": "the Library", "activity": "waiting for the family outing"}
            if outing_destination in {"Family farm", "Farm pond"}:
                return {"location": "Farm", "label": outing_destination.lower(), "activity": "getting ready for the family outing"}
            return {"location": "Town", "label": outing_destination.lower(), "activity": "waiting for the family outing"}
        if not self.family_household_uses_farmhouse():
            if phase in {"wake", "evening", "late", "bad_weather"}:
                return {"location": "ProceduralHome", "label": home, "activity": "following the household routine at home"}
            return {"location": "ProceduralTown", "label": "the local town", "activity": "keeping their career and errands connected to the household"}
        if phase in {"wake", "evening", "late", "bad_weather"}:
            return {"location": "HouseInterior", "label": home, "activity": self.spouse_household_activity_label(npc)}
        if phase == "lunch":
            return {"location": "Town", "label": "the town green", "activity": "taking a midday break among neighbors"}
        mode = self.spouse_support_mode()
        if phase == "work_afternoon" and mode in {"Farm", "Balanced"}:
            return {"location": "Farm", "label": "the family farm", "activity": "handling visible household work around the farm"}
        if phase == "work_afternoon" and mode == "Forage":
            return {"location": "RegionalTravel", "label": "the nearby fields", "activity": "foraging along a familiar safe route"}
        if phase == "work_afternoon" and mode == "Meals":
            return {"location": "MarketRowInterior", "label": "Market Row", "activity": "shopping and planning the household meal"}
        if mode == "Rest" and phase == "work_afternoon":
            return {"location": "HouseInterior", "label": home, "activity": "protecting an unhurried afternoon at home"}
        return {"location": "Original", "label": "their former workplace", "activity": "continuing the work and relationships they had before marriage"}

    def town_npc_schedule_raw_value(self, npc: Dict[str, object]):
        if str(npc.get("id", "")) != str(getattr(self.state, "spouse_npc_id", "")) or not self.spouse_lives_on_farm():
            return super().town_npc_schedule_raw_value(npc)
        public_entry = self.town_npc_public_schedule_entry(npc)
        if public_entry:
            return public_entry
        destination = self.family_spouse_destination(npc)
        location = str(destination.get("location", "Original"))
        activity = str(destination.get("activity", "following the household routine"))
        if location == "Original":
            plan = super().town_npc_routine_plan_without_phase_check(npc)
            phase = self.family_world_schedule_phase()
            return plan.get(phase) or plan.get("work_morning") or {"inside": "Farmhouse", "activity": activity}
        if location == "HouseInterior":
            return {"inside": "Farmhouse", "activity": activity}
        if location == "Town":
            return {"at": (43, 24), "activity": activity}
        if location in {"LibraryInterior", "MarketRowInterior"}:
            labels = {"LibraryInterior": "Library", "MarketRowInterior": "Market Row"}
            return {"inside": labels[location], "activity": activity}
        return {"away": str(destination.get("label", "the regional roads")), "activity": activity}

    def family_child_actor(self, child: Dict[str, object], destination: Dict[str, object]) -> Dict[str, object]:
        child_id = int(child.get("id", 0) or 0)
        return {
            "id": f"household_child:{child_id}",
            "name": str(child.get("name", f"Child {child_id}")),
            "symbol": "@",
            "sex": str(child.get("sex", "Unknown")),
            "role": self.household_child_stage(child),
            "home": self.family_household_home_label(),
            "facing": "DOWN",
            "activity": str(destination.get("activity", self.household_child_activity_label(child))),
            "runtime_activity": str(destination.get("activity", self.household_child_activity_label(child))),
            "family_world_actor": True,
        }

    def family_furniture_assigned_actor(self, object_key: str, obj_name: str) -> str:
        furniture_states = getattr(self.state, "furniture_states", {})
        if not isinstance(furniture_states, dict):
            return ""
        record = furniture_states.get(f"placed:{object_key}:{obj_name}", {})
        return str(record.get("assigned_actor_id", "")) if isinstance(record, dict) else ""

    def family_furniture_activity_cache(self) -> Dict[str, str]:
        placed_signature = tuple(
            sorted(
                (
                    str(key), str(name),
                    int(self.object_rotation_for_key(str(key))),
                    self.family_furniture_assigned_actor(str(key), str(name)),
                )
                for key, name in self.state.placed_objects.items()
                if str(key).startswith("HouseInterior:")
            )
        )
        context = (
            int(self.state.year), int(self.state.month), int(self.state.day),
            self.family_world_schedule_phase(), placed_signature,
        )
        if getattr(self, "_family_furniture_activity_context", None) != context:
            self._family_furniture_activity_context = context
            self._family_furniture_activity_labels = {}
        cache = getattr(self, "_family_furniture_activity_labels", None)
        if not isinstance(cache, dict):
            cache = {}
            self._family_furniture_activity_labels = cache
        return cache

    def family_house_furniture_records(self) -> List[Dict[str, object]]:
        records: List[Dict[str, object]] = []
        for key, obj_name in self.state.placed_objects.items():
            parsed = self.parse_object_key(str(key))
            if not parsed or parsed[0] != "HouseInterior":
                continue
            _scope, x, y = parsed
            rotation = self.object_rotation_for_key(str(key))
            width, height = self.object_footprint_size(str(obj_name), rotation)
            state_key = f"placed:{key}:{obj_name}"
            furniture_state = dict(getattr(self.state, "furniture_states", {}) or {}).get(
                state_key, {}
            )
            records.append({
                "key": str(key), "name": str(obj_name),
                "state_key": state_key,
                "assigned_actor_id": str(
                    furniture_state.get("assigned_actor_id", "")
                    if isinstance(furniture_state, dict) else ""
                ),
                "function": str(INFRASTRUCTURE_DATA.get(str(obj_name), {}).get("furniture_function", "")),
                "x": int(x), "y": int(y), "rotation": int(rotation),
                "width": int(width), "height": int(height),
            })
        records.sort(key=lambda record: (str(record["name"]), str(record["key"])))
        return records

    def family_furniture_activity_preferences(
        self, actor_kind: str, child: Optional[Dict[str, object]] = None,
    ) -> Tuple[str, ...]:
        phase = self.family_world_schedule_phase()
        if phase == "late":
            return ("Crib", "Child Bed", "sleep") if child else ("sleep",)
        if phase == "wake":
            return ("family_meal", "rest", "bookshelf") if child else ("cook", "prepare", "wash", "family_meal")
        if phase == "lunch":
            return ("family_meal", "Dining Set", "Family Table")
        if phase in {"evening", "bad_weather"}:
            if child and self.family_weekly_priority() == "Learning":
                return ("bookshelf", "Study Desk", "rest", "social")
            return ("social", "rest", "hearth", "bookshelf", "family_meal")
        if child:
            stage = self.household_child_stage(child)
            if stage in {"Newborn", "Infant", "Toddler"}:
                return ("Crib", "Toy Shelf", "rest", "family_meal")
            if self.family_weekly_priority() == "Learning":
                return ("bookshelf", "Study Desk", "craft", "rest")
            return ("Study Desk", "bookshelf", "craft", "rest")
        mode = self.spouse_support_mode()
        if mode == "Meals":
            return ("cook", "prepare", "family_meal", "storage")
        if mode == "Rest":
            return ("rest", "hearth", "bookshelf", "social")
        return ("craft", "bookshelf", "rest", "family_meal")

    def family_furniture_activity_label(self, token: str, obj_name: str) -> str:
        return {
            "sleep": f"settling in beside the {obj_name.lower()}",
            "Crib": "resting beside the crib",
            "Child Bed": "settling into their own bed",
            "cook": "cooking at the household stove",
            "prepare": "preparing food at the kitchen worktop",
            "wash": "washing up at the kitchen sink",
            "family_meal": "gathering around the household table",
            "social": "sharing an unhurried conversation in the parlor",
            "rest": f"relaxing beside the {obj_name.lower()}",
            "hearth": "warming up beside the hearth",
            "bookshelf": f"reading at the {obj_name.lower()}",
            "craft": "working on a small project at the bench",
            "gear": "organizing household equipment",
            "storage": f"putting the {obj_name.lower()} in order",
            "Study Desk": "working through a lesson at the study desk",
            "Toy Shelf": "playing beside the toy shelf",
        }.get(str(token), f"using the {obj_name.lower()}")

    def family_record_furniture_use(
        self, actor_id: str, state_key: str, obj_name: str, token: str,
    ) -> None:
        furniture_states = getattr(self.state, "furniture_states", {})
        if not isinstance(furniture_states, dict) or not state_key:
            return
        record = furniture_states.setdefault(str(state_key), {})
        if not isinstance(record, dict):
            record = {}
            furniture_states[str(state_key)] = record
        today = self.town_npc_day_key()
        household_days = record.get("household_use_days", {})
        if not isinstance(household_days, dict):
            household_days = {}
        if str(household_days.get(str(actor_id), "")) == today:
            return
        household_days[str(actor_id)] = today
        record["household_use_days"] = household_days
        record["name"] = str(obj_name)
        record["uses"] = max(0, int(record.get("uses", 0) or 0)) + 1
        record["household_uses"] = max(0, int(record.get("household_uses", 0) or 0)) + 1
        record["last_household_user"] = str(actor_id)
        record["last_action"] = str(token or "household")
        record["last_used_day"] = today
        if (
            str(record.get("assigned_actor_id", "")) == str(actor_id)
            and str(record.get("assigned_bond_day", "")) != today
        ):
            record["assigned_bond_day"] = today
            self.adjust_family_bond(1)

    def family_furniture_activity_position(
        self, actor_id: str, preferences: Tuple[str, ...], occupied: set,
    ) -> Optional[Tuple[int, int]]:
        candidates: List[Tuple[int, str, str, str, Tuple[int, int], str]] = []
        for record in self.family_house_furniture_records():
            name = str(record["name"])
            function = str(record["function"])
            x, y = int(record["x"]), int(record["y"])
            width, height = int(record["width"]), int(record["height"])
            rotation = int(record["rotation"])
            assigned_actor_id = str(record.get("assigned_actor_id", ""))
            if assigned_actor_id and assigned_actor_id != str(actor_id):
                continue
            assignment_bias = -20 if assigned_actor_id == str(actor_id) else 0
            for offset_y in range(height):
                for offset_x in range(width):
                    if furniture_walkable_kind(name, offset_x, offset_y, rotation) != "seat":
                        continue
                    stand_x, stand_y = x + offset_x, y + offset_y
                    if (stand_x, stand_y) in occupied or not self.in_house_bounds_for_npc(stand_x, stand_y):
                        continue
                    component = furniture_component_at(name, offset_x, offset_y, rotation)
                    tokens = {name, function, component}
                    for priority, preference in enumerate(preferences):
                        if preference in tokens:
                            candidates.append((
                                priority * 2 + assignment_bias, f"0:{record['key']}:{offset_y},{offset_x}",
                                name, component or function or name, (stand_x, stand_y),
                                str(record.get("state_key", "")),
                            ))
                            break
            edges = tuple(self.rotated_furniture_use_edges(name, rotation)) or (
                "north", "east", "south", "west",
            )
            edge_targets: List[Tuple[int, int, int, int]] = []
            if "north" in edges:
                edge_targets.extend((x + dx, y, x + dx, y - 1) for dx in range(width))
            if "south" in edges:
                edge_targets.extend((x + dx, y + height - 1, x + dx, y + height) for dx in range(width))
            if "west" in edges:
                edge_targets.extend((x, y + dy, x - 1, y + dy) for dy in range(height))
            if "east" in edges:
                edge_targets.extend((x + width - 1, y + dy, x + width, y + dy) for dy in range(height))
            for target_x, target_y, stand_x, stand_y in edge_targets:
                if (stand_x, stand_y) in occupied or not self.in_house_bounds_for_npc(stand_x, stand_y):
                    continue
                component = furniture_component_at(
                    name, target_x - x, target_y - y, rotation,
                )
                tokens = {name, function, component}
                for priority, preference in enumerate(preferences):
                    if preference in tokens:
                        candidates.append(
                            (
                                priority * 2 + 1 + assignment_bias, f"1:{record['key']}:{stand_y},{stand_x}",
                                name, component or function or name, (stand_x, stand_y),
                                str(record.get("state_key", "")),
                            )
                        )
                        break
        if not candidates:
            self.family_furniture_activity_cache().pop(str(actor_id), None)
            return None
        candidates.sort(key=lambda entry: (entry[0], entry[1], entry[4][1], entry[4][0]))
        best_priority = candidates[0][0]
        best = [entry for entry in candidates if entry[0] == best_priority]
        stable_index = sum(ord(char) for char in str(actor_id)) % len(best)
        _priority, _sort_key, obj_name, token, position, state_key = best[stable_index]
        self.family_furniture_activity_cache()[str(actor_id)] = self.family_furniture_activity_label(token, obj_name)
        self.family_record_furniture_use(actor_id, state_key, obj_name, token)
        return position

    def family_procedural_furniture_activity_position(
        self, actor_id: str, preferences: Tuple[str, ...], occupied: set,
    ) -> Optional[Tuple[int, int]]:
        grid = self.active_map()
        scope = self.current_object_location_key()
        placed_signature = tuple(
            sorted(
                (
                    str(record["key"]), str(record["name"]),
                    int(record.get("rotation", 0)),
                    self.family_furniture_assigned_actor(
                        str(record["key"]), str(record["name"]),
                    ),
                )
                for record in self.placed_objects_for_scope(scope)
            )
        )
        cache_key = (id(grid), scope, placed_signature)
        candidate_cache = getattr(self, "_family_procedural_furniture_candidate_cache", None)
        if not isinstance(candidate_cache, dict):
            candidate_cache = {}
            self._family_procedural_furniture_candidate_cache = candidate_cache
        candidates = candidate_cache.get(cache_key)
        if candidates is None:
            candidates = []
            object_lookup = self.build_frame_placed_object_lookup()
            directions = (
                (0, -1, "north"), (1, 0, "east"),
                (0, 1, "south"), (-1, 0, "west"),
            )
            for (target_x, target_y), (key, name, anchor_x, anchor_y) in object_lookup.items():
                data = INFRASTRUCTURE_DATA.get(name, {})
                if data.get("placement_layer") == "floor":
                    continue
                rotation = self.object_rotation_for_key(key, name)
                component = furniture_component_at(
                    name, int(target_x) - int(anchor_x), int(target_y) - int(anchor_y), rotation,
                )
                function = str(data.get("furniture_function", ""))
                allowed = tuple(self.rotated_furniture_use_edges(name, rotation))
                tokens = {str(name), function, component}
                walkable_kind = furniture_walkable_kind(
                    name, int(target_x) - int(anchor_x), int(target_y) - int(anchor_y), rotation,
                )
                state_key = f"placed:{key}:{name}"
                furniture_state = dict(getattr(self.state, "furniture_states", {}) or {}).get(
                    state_key, {}
                )
                assigned_actor_id = str(
                    furniture_state.get("assigned_actor_id", "")
                    if isinstance(furniture_state, dict) else ""
                )
                if walkable_kind:
                    if walkable_kind == "seat":
                        candidates.append((
                            f"0:{key}:{target_y},{target_x}", str(name),
                            component or function or str(name), tokens,
                            (int(target_x), int(target_y)), state_key, assigned_actor_id,
                        ))
                    continue
                for dx, dy, approach in directions:
                    if allowed and approach not in allowed:
                        continue
                    stand_x, stand_y = int(target_x) + dx, int(target_y) + dy
                    if not (0 <= stand_y < len(grid) and 0 <= stand_x < len(grid[stand_y])):
                        continue
                    if not self.procedural_town_interior_tile_passable(grid[stand_y][stand_x]):
                        continue
                    if (stand_x, stand_y) in object_lookup:
                        continue
                    candidates.append((
                        f"1:{key}:{stand_y},{stand_x}", str(name),
                        component or function or str(name), tokens, (stand_x, stand_y),
                        state_key, assigned_actor_id,
                    ))
            candidate_cache.clear()
            candidate_cache[cache_key] = candidates

        matches = []
        for key, name, token, tokens, position, state_key, assigned_actor_id in candidates:
            if position in occupied:
                continue
            if assigned_actor_id and assigned_actor_id != str(actor_id):
                continue
            assignment_bias = -20 if assigned_actor_id == str(actor_id) else 0
            for priority, preference in enumerate(preferences):
                if preference in tokens:
                    candidate_rank = 0 if str(key).startswith("0:") else 1
                    matches.append((
                        priority * 2 + candidate_rank + assignment_bias,
                        key, name, token, position, state_key,
                    ))
                    break
        if not matches:
            self.family_furniture_activity_cache().pop(str(actor_id), None)
            return None
        matches.sort(key=lambda entry: (entry[0], entry[1], entry[4][1], entry[4][0]))
        best_priority = matches[0][0]
        best = [entry for entry in matches if entry[0] == best_priority]
        selected = best[sum(ord(char) for char in str(actor_id)) % len(best)]
        _priority, _key, name, token, position, state_key = selected
        self.family_furniture_activity_cache()[str(actor_id)] = self.family_furniture_activity_label(token, name)
        self.family_record_furniture_use(actor_id, state_key, name, token)
        return position

    def spouse_farmhouse_position(self) -> Tuple[int, int]:
        spouse = self.npc_record_by_id(str(getattr(self.state, "spouse_npc_id", "")))
        if spouse and str(self.family_spouse_destination(spouse).get("location", "")) != "HouseInterior":
            return super().spouse_farmhouse_position()
        actor_id = f"spouse:{spouse.get('id', '')}" if spouse else "spouse"
        occupied = {(int(self.state.player_x), int(self.state.player_y))}
        position = self.family_furniture_activity_position(
            actor_id, self.family_furniture_activity_preferences("spouse"), occupied,
        )
        if position is not None:
            if spouse:
                activity = self.family_furniture_activity_cache().get(actor_id, "following the household routine")
                spouse["activity"] = activity
                spouse["runtime_activity"] = activity
            return position
        return super().spouse_farmhouse_position()

    def household_child_positions(self) -> Dict[int, Tuple[int, int]]:
        fallback = super().household_child_positions()
        occupied = {(int(self.state.player_x), int(self.state.player_y))}
        if self.spouse_lives_on_farm():
            occupied.add(self.spouse_farmhouse_position())
        positions: Dict[int, Tuple[int, int]] = {}
        for child in self.state.children:
            child_id = int(child.get("id", 0) or 0)
            if str(self.family_child_destination(child).get("location", "")) != "Home":
                positions[child_id] = fallback.get(child_id, (1, 1))
                continue
            actor_id = f"household_child:{child_id}"
            position = self.family_furniture_activity_position(
                actor_id,
                self.family_furniture_activity_preferences("child", child),
                occupied,
            )
            if position is None:
                position = fallback.get(child_id, (1, 1))
            if position in occupied:
                min_x, min_y, max_x, max_y = self.house_floor_bounds()
                replacement = next(
                    (
                        (x, y)
                        for y in range(min_y, max_y + 1)
                        for x in range(min_x, max_x + 1)
                        if (x, y) not in occupied and self.in_house_bounds_for_npc(x, y)
                    ),
                    position,
                )
                position = replacement
            positions[child_id] = position
            occupied.add(position)
        return positions

    def household_child_npcs(self) -> List[Dict[str, object]]:
        actors = super().household_child_npcs()
        if not self.on_house():
            return actors
        home_ids = {
            int(child.get("id", 0) or 0)
            for child in self.state.children
            if str(self.family_child_destination(child).get("location")) == "Home"
        }
        actors = [
            actor for actor in actors
            if int(str(actor.get("id", "0")).split(":")[-1] or 0) in home_ids
        ]
        activity_cache = self.family_furniture_activity_cache()
        for actor in actors:
            activity = activity_cache.get(str(actor.get("id", "")))
            if activity:
                actor["activity"] = activity
                actor["runtime_activity"] = activity
        return actors

    def authored_town_exterior_npc_positions(self, *, normalize: bool = True) -> Dict[Tuple[int, int], Dict[str, object]]:
        lookup = super().authored_town_exterior_npc_positions(normalize=normalize)
        occupied = set(lookup)
        anchors = [(43, 24), (48, 22), (35, 25), (52, 28), (39, 18)]
        for child in self.state.children:
            destination = self.family_child_destination(child)
            if str(destination.get("location")) != "Town":
                continue
            actor = self.family_child_actor(child, destination)
            anchor = anchors[int(child.get("id", 0) or 0) % len(anchors)]
            position = self.town_npc_nearest_town_route_tile(anchor[0], anchor[1], str(actor["id"]))
            while position in occupied:
                position = self.town_npc_nearest_town_route_tile(position[0] + 1, position[1], str(actor["id"]))
            actor["x"], actor["y"] = position
            lookup[position] = actor
            occupied.add(position)
        return lookup

    def home_region_destination_npc_positions(self) -> Dict[Tuple[int, int], Dict[str, object]]:
        lookup = super().home_region_destination_npc_positions()
        if not (self.on_farm() or (hasattr(self, "in_seamless_farm_district") and self.in_seamless_farm_district())):
            return lookup
        occupied = set(lookup)
        spouse = self.npc_record_by_id(str(getattr(self.state, "spouse_npc_id", "")))
        if spouse and str(self.family_spouse_destination(spouse).get("location")) == "Farm":
            position = self.home_region_destination_position("family_spouse", occupied)
            spouse["runtime_activity"] = str(self.family_spouse_destination(spouse).get("activity", "helping around the farm"))
            spouse["activity"] = spouse["runtime_activity"]
            lookup[position] = spouse
            occupied.add(position)
        for child in self.state.children:
            destination = self.family_child_destination(child)
            if str(destination.get("location")) != "Farm":
                continue
            actor = self.family_child_actor(child, destination)
            position = self.home_region_destination_position(str(actor["id"]), occupied)
            actor["x"], actor["y"] = position
            lookup[position] = actor
            occupied.add(position)
        return lookup

    def family_interior_actor_position(self, location: str, actor: Dict[str, object], occupied: set) -> Tuple[int, int]:
        grid = self.authored_town_interior_grid(location)
        cache_key = (str(location), id(grid))
        anchor_cache = getattr(self, "_family_interior_anchor_cache", None)
        if not isinstance(anchor_cache, dict):
            anchor_cache = {}
            self._family_interior_anchor_cache = anchor_cache
        anchors = anchor_cache.get(cache_key)
        if anchors is None:
            anchors = self.town_npc_fixture_approaches(location, {"t", "c", "l", "B", "&"})
            anchors.extend([(27, 18), (26, 18), (28, 18), (27, 16)])
            anchor_cache.clear()
            anchor_cache[cache_key] = list(anchors)
        for anchor in anchors:
            position = self.town_npc_nearest_interior_tile(location, anchor[0], anchor[1], occupied)
            if position not in occupied:
                return position
        return self.town_npc_nearest_interior_tile(location, 27, 18, occupied)

    def family_procedural_home_actors(self, lookup: Dict[Tuple[int, int], Dict[str, object]]) -> None:
        if not (hasattr(self, "on_player_owned_procedural_residence") and self.on_player_owned_procedural_residence()):
            return
        property_record = self.household_residence_property() if hasattr(self, "household_residence_property") else None
        building = self.current_procedural_town_building() if hasattr(self, "current_procedural_town_building") else None
        if not property_record or not building or str(property_record.get("building_id", "")) != str(building.get("id", "")):
            return
        phase = self.family_world_schedule_phase()
        if phase not in {"wake", "evening", "late", "bad_weather"}:
            return
        grid = self.active_map()
        occupied = set(lookup) | {(int(self.state.player_x), int(self.state.player_y))}
        candidate_key = (
            id(grid), len(grid), len(grid[0]) if grid else 0,
            str(getattr(self.state, "current_procedural_building_id", "")),
            int(getattr(self.state, "current_procedural_building_floor", 0) or 0),
        )
        candidate_cache = getattr(self, "_family_procedural_floor_candidate_cache", None)
        if not isinstance(candidate_cache, dict):
            candidate_cache = {}
            self._family_procedural_floor_candidate_cache = candidate_cache
        candidates = candidate_cache.get(candidate_key)
        if candidates is None:
            candidates = []
            for y, row in enumerate(grid):
                for x, tile in enumerate(row):
                    if self.procedural_town_interior_tile_passable(tile):
                        candidates.append((x, y))
            candidates.sort(key=lambda point: (abs(point[0] - 27) + abs(point[1] - 18), point[1], point[0]))
            candidate_cache.clear()
            candidate_cache[candidate_key] = list(candidates)
        members: List[Dict[str, object]] = []
        spouse = self.npc_record_by_id(str(getattr(self.state, "spouse_npc_id", "")))
        if spouse and self.spouse_lives_on_farm():
            members.append(spouse)
        members.extend(self.family_child_actor(child, self.family_child_destination(child)) for child in self.state.children)
        for member in members:
            child = self.child_record_from_npc(member) if self.is_household_child_npc(member) else None
            actor_id = str(member.get("id", "household_member"))
            preferences = self.family_furniture_activity_preferences(
                "child" if child else "spouse", child,
            )
            position = self.family_procedural_furniture_activity_position(
                actor_id, preferences, occupied,
            )
            if position is None:
                position = next((point for point in candidates if point not in occupied), None)
            if position is None:
                break
            activity = self.family_furniture_activity_cache().get(actor_id)
            if activity:
                member["activity"] = activity
                member["runtime_activity"] = activity
            lookup[position] = member
            occupied.add(position)

    def town_npc_position_lookup(self) -> Dict[Tuple[int, int], Dict[str, object]]:
        lookup = super().town_npc_position_lookup()
        if self.on_house():
            spouse_id = str(getattr(self.state, "spouse_npc_id", ""))
            spouse = self.npc_record_by_id(spouse_id)
            spouse_home = bool(
                spouse
                and str(self.family_spouse_destination(spouse).get("location", "")) == "HouseInterior"
            )
            if not spouse_home:
                lookup = {
                    position: actor
                    for position, actor in lookup.items()
                    if str(actor.get("id", "")) != spouse_id
                }
        if self.on_town_interior():
            location = self.town_npc_observed_runtime_location()
            occupied = set(lookup) | {(int(self.state.player_x), int(self.state.player_y))}
            for child in self.state.children:
                destination = self.family_child_destination(child)
                if str(destination.get("location")) != location:
                    continue
                actor = self.family_child_actor(child, destination)
                position = self.family_interior_actor_position(location, actor, occupied)
                lookup[position] = actor
                occupied.add(position)
        if self.on_procedural_town_interior():
            self.family_procedural_home_actors(lookup)
        return lookup

    def family_member_schedule_lines(self) -> List[str]:
        lines = ["HOUSEHOLD WHEREABOUTS", ""]
        if self.on_house():
            if self.spouse_lives_on_farm():
                self.spouse_farmhouse_position()
            self.household_child_positions()
        activity_cache = self.family_furniture_activity_cache()
        spouse = self.npc_record_by_id(str(getattr(self.state, "spouse_npc_id", "")))
        if spouse:
            destination = self.family_spouse_destination(spouse)
            activity = activity_cache.get(
                f"spouse:{spouse.get('id', '')}", str(destination.get("activity", "at home")),
            )
            lines.append(f"- {spouse.get('name', 'Spouse')}: {activity} ({destination.get('label')})")
        for child in self.state.children:
            destination = self.family_child_destination(child)
            activity = activity_cache.get(
                f"household_child:{int(child.get('id', 0) or 0)}",
                str(destination.get("activity", "at home")),
            )
            lines.append(f"- {child.get('name', 'Child')}: {activity} ({destination.get('label')})")
        if not spouse and not self.state.children:
            lines.append("- No spouse or children are part of the household yet.")
        lines.extend(["", "Schedules change with age, weather, weekday, household priorities, and planned outings."])
        return lines

    def family_today_lines(self) -> List[str]:
        lines = list(super().family_today_lines())
        lines.extend(["", f"Weekly priority: {self.family_weekly_priority()}"])
        lines.extend(self.family_member_schedule_lines()[2:])
        outing = self.ensure_family_world_state().get("planned_outing", {})
        if outing:
            status = "ready now" if self.family_world_outing_ready() else str(outing.get("date_label", "scheduled"))
            lines.extend(["", f"Planned outing: {outing.get('type')} ({status})"])
        return lines

    def family_status_lines(self) -> List[str]:
        home = self.family_household_home_label()
        lines = [line.replace("the farmhouse", home).replace("at the farmhouse", f"at {home}") for line in super().family_status_lines()]
        lines.extend(["", f"Household priority: {self.family_weekly_priority()}", *self.family_member_schedule_lines()])
        return lines

    def marriage_status_lines(self) -> List[str]:
        home = self.family_household_home_label()
        return [line.replace("the farmhouse", home).replace("at the farmhouse", f"at {home}") for line in super().marriage_status_lines()]

    def family_sleep_bonus(self) -> int:
        bonus = int(super().family_sleep_bonus())
        if self.family_weekly_priority() == "Rest" and self.family_member_count() > 1:
            bonus += 1
        return bonus

    def set_family_weekly_priority(self, priority: str) -> bool:
        if priority not in FAMILY_PRIORITIES:
            return False
        state = self.ensure_family_world_state()
        state["weekly_priority"] = priority
        state["priority_week"] = self.family_world_week_key()
        self.record_family_event("Household Priority", f"The household chose {priority.lower()} for the week.")
        self.autosave_with_message(f"Household priority set to {priority}.")
        return True

    def family_priority_menu(self):
        items = [
            MenuItem(label=name, value=name, enabled=True, hint=str(data["summary"]))
            for name, data in FAMILY_PRIORITIES.items()
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select("Weekly Household Priority", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if not choice or choice.value == MENU_BACK:
            return MENU_BACK
        self.set_family_weekly_priority(str(choice.value))
        return "changed"

    def family_partnership_checkin_available(self) -> Tuple[bool, str]:
        if not getattr(self.state, "spouse_npc_id", ""):
            return False, "A partnership check-in requires a spouse."
        state = self.ensure_family_world_state()
        if str(state.get("last_checkin_week", "")) == self.family_world_week_key():
            return False, "Already completed this week's check-in."
        return True, "Talk through work, home, children, and the coming week."

    def complete_family_partnership_checkin(self) -> bool:
        available, reason = self.family_partnership_checkin_available()
        if not available:
            self.set_message(reason)
            return False
        state = self.ensure_family_world_state()
        priority = self.family_weekly_priority()
        gain = 8 if priority == "Togetherness" else 6
        state["last_checkin_week"] = self.family_world_week_key()
        self.adjust_family_bond(gain)
        self.adjust_town_npc_relationship(str(self.state.spouse_npc_id), 3)
        self.record_family_event("Partnership Check-In", f"You agreed to center the week on {priority.lower()}.")
        spouse_id = str(self.state.spouse_npc_id)
        spouse_name = self.town_npc_name(spouse_id)
        if hasattr(self, "play_world_event_scene"):
            self.play_world_event_scene(
                f"partnership_checkin:{spouse_id}:{self.family_world_week_key()}",
                "A Household Check-In",
                [
                    {
                        "type": "narration",
                        "text": "You both make room for an honest household conversation where you actually live, comparing schedules before the week carries either of you away.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "npc_id": spouse_id,
                        "text": f"Let us center this week on {priority.lower()}. We can name what matters now, and let the rest wait.",
                    },
                    {
                        "type": "narration",
                        "text": f"{FAMILY_PRIORITIES[priority]['summary']} Household bond rises by {gain}, and your relationship with {spouse_name} rises by 3.",
                    },
                ],
                f"Completed the weekly partnership check-in. Household bond +{gain}.",
            )
        else:
            self.vertical_panel_view(
                "Partnership Check-In",
                [
                    "You make room for an honest household conversation.",
                    "",
                    f"Weekly priority: {priority}",
                    str(FAMILY_PRIORITIES[priority]["summary"]),
                    "",
                    "You compare schedules, name one worry each, and decide what can wait.",
                    f"Household bond +{gain}; spouse relationship +3.",
                ],
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
            )
        self.autosave_with_message(f"Completed the weekly partnership check-in. Household bond +{gain}.")
        return True

    def family_outing_eligible_children(self, outing_type: str) -> List[Dict[str, object]]:
        minimum = str(FAMILY_OUTINGS[outing_type].get("minimum_stage", "Toddler"))
        required = FAMILY_STAGE_ORDER.get(minimum, 0)
        return [
            child for child in self.state.children
            if FAMILY_STAGE_ORDER.get(self.household_child_stage(child), 0) >= required
        ]

    def schedule_family_outing(self, outing_type: str, days_ahead: int) -> bool:
        if outing_type not in FAMILY_OUTINGS:
            return False
        if self.family_member_count() <= 1:
            self.set_message("A family outing requires a spouse or eligible child.")
            return False
        data = FAMILY_OUTINGS[outing_type]
        eligible_children = self.family_outing_eligible_children(outing_type)
        if not getattr(self.state, "spouse_npc_id", "") and not eligible_children:
            self.set_message(f"No child is old enough for {outing_type.lower()} yet.")
            return False
        month, day, year = self.date_after_days(max(1, int(days_ahead)))
        state = self.ensure_family_world_state()
        state["planned_outing"] = {
            "type": outing_type,
            "destination": str(data["destination"]),
            "due_ordinal": int(self.absolute_game_day()) + max(1, int(days_ahead)),
            "month": month,
            "day": day,
            "year": year,
            "date_label": format_date(month, day, year),
            "participants": [str(child.get("id")) for child in eligible_children],
        }
        self.record_family_event("Outing Planned", f"{outing_type} scheduled for {format_date(month, day, year)}.")
        self.autosave_with_message(f"Planned {outing_type} for {format_date(month, day, year)}.")
        return True

    def family_outing_scene_lines(self, outing_type: str, children: List[Dict[str, object]]) -> List[str]:
        data = FAMILY_OUTINGS[outing_type]
        season = str(self.state.season)
        weather = str(self.state.weather)
        names = [str(child.get("name", "your child")) for child in children]
        personality_notes = []
        for child in children[:4]:
            trait = str(self.ensure_child_profile_fields(child).get("personality_trait", "Curious"))
            reactions = {
                "Curious": "keeps finding questions hidden inside ordinary details",
                "Outdoorsy": "ranges ahead, then doubles back to report every discovery",
                "Studious": "quietly records what seems worth remembering",
                "Practical": "notices what the group packed well and what it forgot",
                "Gentle": "makes sure nobody is left outside the conversation",
                "Bold": "turns the safest challenge into a personal expedition",
                "Musical": "finds a rhythm in the road, water, and voices",
                "Tinkering": "studies how every tool, gate, and fixture was made",
            }
            personality_notes.append(f"- {child.get('name')}: {reactions.get(trait, 'finds their own reason to remember the day') }.")
        rows = [
            outing_type,
            "",
            f"Destination: {data['destination']}",
            f"Conditions: {season}, {weather.lower()}",
            f"Participants: {', '.join(names) if names else 'you and your spouse'}",
            "",
            "The outing unfolds as shared time rather than another invisible household reward.",
        ]
        rows.extend(personality_notes or ["- You and your spouse have time to talk without a chore waiting in the next room."])
        rows.extend(["", "What everyone notices becomes part of the family record and the children's upbringing."])
        return rows

    def complete_planned_family_outing(self) -> bool:
        state = self.ensure_family_world_state()
        outing = state.get("planned_outing", {})
        if not outing:
            self.set_message("No family outing is planned.")
            return False
        if not self.family_world_outing_ready():
            self.set_message(f"The outing is scheduled for {outing.get('date_label', 'a later date')}.")
            return False
        outing_type = str(outing.get("type", ""))
        if outing_type not in FAMILY_OUTINGS:
            state["planned_outing"] = {}
            return False
        data = FAMILY_OUTINGS[outing_type]
        cost = int(data.get("cost", 0))
        if int(self.state.money) < cost:
            self.set_message(f"{outing_type} needs {cost}g for supplies and travel.")
            return False
        participant_ids = {str(value) for value in outing.get("participants", [])}
        children = [child for child in self.state.children if str(child.get("id")) in participant_ids]
        priority = self.family_weekly_priority()
        bond_gain = int(data.get("bond", 6)) + (2 if priority in {"Togetherness", "Adventure"} else 0)
        learning_gain = 3 if priority == "Learning" else 2
        topic = str(data.get("topic", "Community"))
        self.state.money -= cost
        state["planned_outing"] = {}
        self.adjust_family_bond(bond_gain)
        if getattr(self.state, "spouse_npc_id", ""):
            self.adjust_town_npc_relationship(str(self.state.spouse_npc_id), 4)
        for child in children:
            self.adjust_child_affection(child, 5)
            learning = self.child_learning_map(child)
            learning[topic] = int(learning.get(topic, 0)) + learning_gain
            self.update_child_apprentice_path_from_learning(child)
        record = {
            "type": outing_type,
            "date": format_date(self.state.month, self.state.day, self.state.year),
            "destination": str(data["destination"]),
            "participants": [str(child.get("name", "Child")) for child in children],
        }
        state["outing_history"].append(record)
        state["outing_history"] = state["outing_history"][-20:]
        self.record_family_event(
            outing_type,
            f"Visited {data['destination']} with {', '.join(record['participants']) if record['participants'] else 'your spouse'}. Household bond +{bond_gain}.",
        )
        if hasattr(self, "play_world_event_scene"):
            steps: List[Dict[str, object]] = [{
                "type": "narration",
                "text": f"The family travels to {data['destination']} in {str(self.state.season).lower()} {str(self.state.weather).lower()} conditions. The road, weather, and destination remain visible around the time you share.",
            }]
            if getattr(self.state, "spouse_npc_id", ""):
                spouse_id = str(self.state.spouse_npc_id)
                steps.append({
                    "type": "dialogue", "speaker": self.town_npc_name(spouse_id), "npc_id": spouse_id,
                    "text": "I am glad we made this a real day together instead of another good intention left on the calendar.",
                })
            reactions = {
                "Curious": "How many stories can one place have before nobody remembers the first one?",
                "Outdoorsy": "I found a route ahead, but I came back because it is better when everyone sees it.",
                "Studious": "I wrote down the part I want to remember. The weather belongs in the record too.",
                "Practical": "Next time we should pack one more meal and half as many things nobody used.",
                "Gentle": "Can we wait a moment? I want everyone to be here before we move on.",
                "Bold": "That safe path looks good, but I want to see where the harder one goes someday.",
                "Musical": "The road and water keep almost the same rhythm if you listen long enough.",
                "Tinkering": "I want to know who built that, and why they chose to make it that way.",
            }
            for child in children[:4]:
                trait = str(self.ensure_child_profile_fields(child).get("personality_trait", "Curious"))
                steps.append({
                    "type": "dialogue", "speaker": str(child.get("name", "Child")),
                    "text": reactions.get(trait, "I think I will remember this place differently when I am older."),
                })
            steps.append({
                "type": "narration",
                "text": f"The outing becomes part of the household record: bond +{bond_gain}, affection +5 for each participating child, and {topic} learning +{learning_gain}.",
            })
            self.play_world_event_scene(
                f"family_outing:{outing_type}:{self.state.year}:{self.state.month}:{self.state.day}:{len(state['outing_history'])}",
                outing_type, steps, f"Completed {outing_type}. Household bond +{bond_gain}.",
            )
        self.advance_time(int(data.get("minutes", 120)))
        self.autosave_with_message(f"Completed {outing_type}. Household bond +{bond_gain}.")
        return True

    def family_outing_menu(self):
        state = self.ensure_family_world_state()
        existing = state.get("planned_outing", {})
        if existing:
            items = [
                MenuItem(label="Begin planned outing", value="begin", enabled=self.family_world_outing_ready(), hint="ready" if self.family_world_outing_ready() else str(existing.get("date_label", "scheduled"))),
                MenuItem(label="Cancel planned outing", value="cancel", enabled=True, hint=str(existing.get("type", "outing"))),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select("Planned Family Outing", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return MENU_BACK
            if choice.value == "begin":
                return "changed" if self.complete_planned_family_outing() else MENU_BACK
            state["planned_outing"] = {}
            self.autosave_with_message("Canceled the planned family outing.")
            return "changed"
        outing_items = []
        for name, data in FAMILY_OUTINGS.items():
            participants = len(self.family_outing_eligible_children(name)) + (1 if self.state.spouse_npc_id else 0)
            outing_items.append(MenuItem(label=name, value=name, enabled=participants > 0, hint=f"{data['destination']} | {data['cost']}g | {participants} participant(s)"))
        outing_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select("Choose Family Outing", outing_items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if not choice or choice.value == MENU_BACK:
            return MENU_BACK
        date_items = [
            MenuItem(label="Tomorrow", value=1, enabled=True),
            MenuItem(label="In three days", value=3, enabled=True),
            MenuItem(label="Next week", value=7, enabled=True),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ]
        date_choice = self.vertical_panel_select("Choose Outing Date", date_items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if not date_choice or date_choice.value == MENU_BACK:
            return MENU_BACK
        return "changed" if self.schedule_family_outing(str(choice.value), int(date_choice.value)) else MENU_BACK

    def family_wedding_plan_lines(self) -> List[str]:
        plan = self.ensure_family_world_state()["wedding_plan"]
        return [
            "WEDDING PLAN",
            "",
            f"Partner: {self.town_npc_name(str(getattr(self.state, 'engaged_npc_id', '') or getattr(self.state, 'spouse_npc_id', '')))}",
            f"Date: {self.wedding_date_label()}",
            f"Venue: {plan.get('venue')}",
            f"Style: {plan.get('style')}",
            f"Guests: {plan.get('guest_focus')}",
            "",
            "The choices change the ceremony scene and the memory recorded in the family ledger.",
        ]

    def family_wedding_planning_menu(self):
        if not getattr(self.state, "engaged_npc_id", ""):
            self.vertical_panel_view("Wedding Plan", self.family_wedding_plan_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return MENU_BACK
        state = self.ensure_family_world_state()
        while True:
            plan = state["wedding_plan"]
            items = [
                MenuItem(label="Review plan", value="review", enabled=True),
                MenuItem(label="Choose venue", value="venue", enabled=True, hint=str(plan.get("venue"))),
                MenuItem(label="Choose style", value="style", enabled=True, hint=str(plan.get("style"))),
                MenuItem(label="Choose guests", value="guests", enabled=True, hint=str(plan.get("guest_focus"))),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select("Wedding Planning", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return MENU_BACK
            if choice.value == "review":
                self.vertical_panel_view("Wedding Plan", self.family_wedding_plan_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            options = {
                "venue": ["Town Hall", "Farm Meadow", "Lakeside", "Wilderness Shrine"],
                "style": ["Intimate", "Community", "Adventurous"],
                "guests": ["Friends and family", "Whole town", "Immediate household"],
            }[str(choice.value)]
            selection = self.vertical_panel_select(
                "Wedding Choice",
                [MenuItem(label=value, value=value, enabled=True) for value in options] + [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not selection or selection.value == MENU_BACK:
                continue
            key = "guest_focus" if choice.value == "guests" else str(choice.value)
            plan[key] = str(selection.value)
            self.autosave_with_message(f"Wedding {key.replace('_', ' ')} set to {selection.value}.")

    def wedding_ceremony_lines(self, npc: Dict[str, object]) -> List[str]:
        name = str(npc.get("name", "your partner"))
        plan = self.ensure_family_world_state()["wedding_plan"]
        venue = str(plan.get("venue", "Town Hall"))
        style = str(plan.get("style", "Community"))
        guest_focus = str(plan.get("guest_focus", "Friends and family"))
        weather = str(self.state.weather)
        vow = str(self.romance_data_for_npc(npc).get("vow", f"{name} promises to build a life beside you."))
        setting = {
            "Town Hall": "The ceremony fills the Town Hall, with its doors open toward the streets you both know.",
            "Farm Meadow": "A clear aisle crosses the farm meadow, bordered by crops, lanterns, and familiar tools.",
            "Lakeside": "The ceremony gathers at the lakeside, where moving water carries every pause in the vows.",
            "Wilderness Shrine": "A restored wilderness shrine becomes a quiet threshold between your separate lives and shared road.",
        }.get(venue, "The household gathers in a place chosen together.")
        weather_line = f"The {weather.lower()} weather becomes part of the day rather than being ignored by an indoor script."
        return [
            f"Wedding of {self.state.player_name} and {name}",
            "",
            f"Venue: {venue} | Style: {style}",
            f"Guests: {guest_focus}",
            setting,
            weather_line,
            "",
            "Each of you speaks about the work, home, roads, and family you are choosing to share.",
            vow,
            "",
            "You exchange rings, vows, and a place in one another's household record.",
            f"Marriage recorded: {format_date(self.state.month, self.state.day, self.state.year)}",
        ]

    def family_world_dashboard_lines(self) -> List[str]:
        state = self.ensure_family_world_state()
        priority = self.family_weekly_priority()
        lines = [
            "HOUSEHOLD DASHBOARD",
            "",
            f"Home: {self.family_household_home_label()}",
            f"Household bond: {self.family_bond_rank()} ({self.family_bond_score()})",
            f"Weekly priority: {priority}",
            f"Priority effect: {FAMILY_PRIORITIES[priority]['benefit']}",
            "",
            *self.family_member_schedule_lines(),
        ]
        outing = state.get("planned_outing", {})
        lines.extend(["", "UPCOMING"])
        if getattr(self.state, "engaged_npc_id", ""):
            lines.append(f"- Wedding with {self.town_npc_name(self.state.engaged_npc_id)}: {self.wedding_date_label()}")
        if self.state.pregnancy_active:
            lines.append(f"- Pregnancy: month {self.pregnancy_month_number()} of 9; due {self.pregnancy_due_date_label()}")
        if outing:
            lines.append(f"- {outing.get('type')}: {'ready now' if self.family_world_outing_ready() else outing.get('date_label')}")
        if not getattr(self.state, "engaged_npc_id", "") and not self.state.pregnancy_active and not outing:
            lines.append("- No wedding, birth, or outing currently scheduled.")
        return lines

    def family_world_dashboard_menu(self):
        while True:
            checkin_ok, checkin_reason = self.family_partnership_checkin_available()
            outing = self.ensure_family_world_state().get("planned_outing", {})
            items = [
                MenuItem(label="Overview", value="overview", enabled=True, hint=self.family_bond_rank()),
                MenuItem(label="Where everyone is", value="schedules", enabled=True, hint=self.family_world_schedule_phase()),
                MenuItem(label="Weekly priority", value="priority", enabled=True, hint=self.family_weekly_priority()),
                MenuItem(label="Partnership check-in", value="checkin", enabled=checkin_ok, hint=checkin_reason),
                MenuItem(label="Family outing", value="outing", enabled=self.family_member_count() > 1, hint=str(outing.get("type", "plan an outing"))),
                MenuItem(label="Wedding plans", value="wedding", enabled=bool(getattr(self.state, "engaged_npc_id", "")), hint=self.wedding_date_label() if getattr(self.state, "engaged_npc_id", "") else "not engaged"),
                MenuItem(label="Family memories", value="memories", enabled=True, hint=f"{len(self.state.family_event_log or [])} logged"),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select("Household Dashboard", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return MENU_BACK
            if choice.value == "overview":
                self.vertical_panel_view("Household Dashboard", self.family_world_dashboard_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "schedules":
                self.vertical_panel_view("Household Whereabouts", self.family_member_schedule_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "priority":
                if self.family_priority_menu() == "changed":
                    return "changed"
            elif choice.value == "checkin":
                if self.complete_family_partnership_checkin():
                    return "changed"
            elif choice.value == "outing":
                if self.family_outing_menu() == "changed":
                    return "changed"
            elif choice.value == "wedding":
                self.family_wedding_planning_menu()
            elif choice.value == "memories":
                self.vertical_panel_view("Family Memories", self.family_event_log_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)

    def process_family_world_overnight(self) -> str:
        state = self.ensure_family_world_state()
        state["last_schedule_day"] = self.town_npc_day_key()
        outing = state.get("planned_outing", {})
        if outing and self.family_world_outing_ready() and not bool(outing.get("ready_announced", False)):
            outing["ready_announced"] = True
            return f" The planned {outing.get('type', 'family outing')} is ready from the household dashboard."
        return ""

    def update_family_overnight(self, interactive: bool = False) -> str:
        return str(super().update_family_overnight(interactive=interactive)) + self.process_family_world_overnight()


__all__ = ["FamilyWorldMixin", "FAMILY_OUTINGS", "FAMILY_PRIORITIES", "FAMILY_WORLD_VERSION"]
