from __future__ import annotations

"""Reusable map-actor navigation and farm-animal routines.

ActorNavigationMixin expects a FarmGame-like object that provides map bounds,
placed-object/crop queries, animal care menus, and persistent GameState data.
The generic path helpers are intentionally independent so future followers and
generated residents can reuse the same movement foundation.
"""

from collections import deque
import random
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from ascii_farmstead_state import quality_item_name
from ascii_farmstead_support import C, colorize


Position = Tuple[int, int]
CARDINAL_STEPS: Tuple[Position, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))


def manhattan_distance(first: Position, second: Position) -> int:
    return abs(int(first[0]) - int(second[0])) + abs(int(first[1]) - int(second[1]))


def shortest_path_step(
    start: Position,
    goals: Iterable[Position],
    passable: Callable[[int, int], bool],
    blocked: Optional[Iterable[Position]] = None,
    max_nodes: int = 2048,
) -> Optional[Position]:
    """Return the first cardinal step on a shortest route to any goal."""
    start = (int(start[0]), int(start[1]))
    goal_set = {(int(x), int(y)) for x, y in goals}
    if not goal_set or start in goal_set:
        return None
    blocked_set = {(int(x), int(y)) for x, y in (blocked or [])}
    blocked_set.discard(start)
    queue = deque([start])
    previous: Dict[Position, Optional[Position]] = {start: None}
    reached: Optional[Position] = None

    while queue and len(previous) <= max(1, int(max_nodes)):
        current = queue.popleft()
        for dx, dy in CARDINAL_STEPS:
            candidate = (current[0] + dx, current[1] + dy)
            if candidate in previous or candidate in blocked_set:
                continue
            if not passable(candidate[0], candidate[1]):
                continue
            previous[candidate] = current
            if candidate in goal_set:
                reached = candidate
                queue.clear()
                break
            queue.append(candidate)

    if reached is None:
        return None
    step = reached
    while previous.get(step) not in (None, start):
        step = previous[step]  # type: ignore[index]
    return step


def choose_wander_step(
    start: Position,
    passable: Callable[[int, int], bool],
    rng: random.Random,
    preferred: Optional[Position] = None,
) -> Optional[Position]:
    """Choose a passable cardinal step, optionally favoring a direction."""
    candidates: List[Tuple[int, Position]] = []
    for dx, dy in CARDINAL_STEPS:
        x, y = start[0] + dx, start[1] + dy
        if not passable(x, y):
            continue
        score = rng.randint(0, 5)
        if preferred:
            score += dx * int(preferred[0]) + dy * int(preferred[1])
        candidates.append((score, (x, y)))
    if not candidates:
        return None
    best = max(score for score, _position in candidates)
    return rng.choice([position for score, position in candidates if score == best])


class ActorNavigationMixin:
    FARM_ANIMAL_SYMBOLS = {
        "Chicken": "c",
        "Duck": "d",
        "Rabbit": "r",
        "Sheep": "s",
        "Cow": "C",
    }
    FARM_ANIMAL_COLORS = {
        "Chicken": C.CROP_READY,
        "Duck": C.WATER,
        "Rabbit": C.SNOW,
        "Sheep": C.SNOW,
        "Cow": C.HOUSE,
    }
    TRAVEL_FOLLOWER_SAFE_LOCATIONS = {
        "Farm",
        "Town",
        "HouseInterior",
        "GeneralStoreInterior",
        "BlacksmithInterior",
        "LibraryInterior",
        "MayorHouseInterior",
        "InnInterior",
        "FurnitureStoreInterior",
        "CarpenterStoreInterior",
        "AnimalStoreInterior",
        "ClinicInterior",
        "TownHallInterior",
        "MarketRowInterior",
        "MuseumInterior",
    }
    TRAVEL_FOLLOWER_ADVENTURE_LOCATIONS = {
        "Mine",
        "Wilderness",
        "WildernessCave",
        "WildernessDungeon",
    }
    TRAVEL_FOLLOWER_TASKS = {
        "water_crops": "Water crops",
        "harvest_crops": "Harvest ripe crops",
        "animal_care": "Care for animals",
        "gather_forage": "Gather forage",
    }
    TRAVEL_FOLLOWER_EXPEDITION_ROLES = {
        "Balanced": "No strong emphasis; stays adaptable.",
        "Scout": "Moves farther in battle and earns one extra outing bond each day.",
        "Gatherer": "Finds one useful field item during the first outing each day.",
        "Guardian": "Gains extra health and defense in tactical combat.",
        "Support": "Gains extra focus and carries an additional recovery item.",
    }

    def farm_animal_actor_position(self, animal: Dict[str, object]) -> Optional[Position]:
        if not bool(animal.get("outside", False)):
            return None
        try:
            x, y = int(animal.get("x", -1)), int(animal.get("y", -1))
        except Exception:
            return None
        if not (0 <= y < len(self.base_map) and 0 <= x < len(self.base_map[y])):
            return None
        return x, y

    def farm_animal_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if not self.on_farm():
            return None
        for animal in self.state.farm_animals:
            position = self.farm_animal_actor_position(animal)
            if position == (int(x), int(y)):
                return animal
        return None

    def render_farm_animal(self, animal: Dict[str, object]) -> str:
        species = str(animal.get("species", "Chicken"))
        symbol = self.FARM_ANIMAL_SYMBOLS.get(species, "a")
        color = self.FARM_ANIMAL_COLORS.get(species, C.CROP_READY)
        if animal.get("sick") or int(animal.get("health", 100) or 100) < 35:
            color = C.DIM
        return colorize(symbol, color)

    def farm_animal_actor_description(self, animal: Dict[str, object]) -> str:
        name = str(animal.get("name", "Animal"))
        species = str(animal.get("species", "Animal"))
        activity = str(animal.get("activity", "resting"))
        trait = str(animal.get("trait", "Gentle"))
        mood = self.animal_mood(animal)
        return f"{name} the {species} [{trait}] is {activity}. Mood: {mood}."

    def farm_animal_home_anchor(self, animal: Dict[str, object]) -> Optional[Tuple[str, int, int]]:
        building_key = str(animal.get("building_key", "") or "")
        parsed = self.parse_object_key(building_key)
        if not parsed or parsed[0] != "Farm":
            return None
        if building_key not in self.state.placed_objects:
            return None
        return building_key, int(parsed[1]), int(parsed[2])

    def farm_animal_static_tile_passable(self, x: int, y: int) -> bool:
        if not (0 <= y < len(self.base_map) and 0 <= x < len(self.base_map[y])):
            return False
        if self.scoped_object_at("Farm", x, y):
            return False
        if self.crop_for_scope("Farm", x, y):
            return False
        return self.base_map[y][x] in [".", ",", "w"]

    def farm_animal_home_tiles(self, animal: Dict[str, object]) -> List[Position]:
        anchor = self.farm_animal_home_anchor(animal)
        if not anchor:
            return []
        building_key, ax, ay = anchor
        building_name = str(self.state.placed_objects.get(building_key, ""))
        width, height = self.object_footprint_size(building_name)
        candidates: List[Position] = []
        for x in range(ax - 1, ax + width + 1):
            candidates.extend([(x, ay - 1), (x, ay + height)])
        for y in range(ay, ay + height):
            candidates.extend([(ax - 1, y), (ax + width, y)])
        unique: List[Position] = []
        seen: Set[Position] = set()
        for position in candidates:
            if position in seen:
                continue
            seen.add(position)
            if self.farm_animal_static_tile_passable(*position):
                unique.append(position)
        return unique

    def farm_animal_occupied_positions(self, exclude: Optional[Dict[str, object]] = None) -> Set[Position]:
        occupied: Set[Position] = set()
        for animal in self.state.farm_animals:
            if animal is exclude:
                continue
            position = self.farm_animal_actor_position(animal)
            if position:
                occupied.add(position)
        return occupied

    def farm_animal_tile_available(self, animal: Dict[str, object], x: int, y: int) -> bool:
        if not self.farm_animal_static_tile_passable(x, y):
            return False
        if (x, y) == (int(self.state.player_x), int(self.state.player_y)) and self.on_farm():
            return False
        return (x, y) not in self.farm_animal_occupied_positions(exclude=animal)

    def farm_animal_weather_allows_outside(self, animal: Dict[str, object]) -> bool:
        weather = str(self.state.weather)
        species = str(animal.get("species", "Chicken"))
        if weather in ["Storm", "Stormy", "Snow", "Snowy", "Blizzard"]:
            return False
        if weather in ["Rain", "Rainy"]:
            return species == "Duck"
        return True

    def farm_animal_should_be_outside(self, animal: Dict[str, object]) -> bool:
        if animal.get("sick") or int(animal.get("health", 100) or 100) < 25:
            return False
        return 7 <= int(self.state.hour) < 18 and self.farm_animal_weather_allows_outside(animal)

    def farm_animal_roam_radius(self, animal: Dict[str, object]) -> int:
        return {
            "Chicken": 7,
            "Duck": 9,
            "Rabbit": 7,
            "Sheep": 10,
            "Cow": 11,
        }.get(str(animal.get("species", "Chicken")), 8)

    def set_farm_animal_inside(self, animal: Dict[str, object], activity: str = "resting indoors"):
        animal["outside"] = False
        animal["x"] = -1
        animal["y"] = -1
        animal["activity"] = activity

    def spawn_farm_animal_outside(self, animal: Dict[str, object]) -> bool:
        candidates = [
            position
            for position in self.farm_animal_home_tiles(animal)
            if self.farm_animal_tile_available(animal, *position)
        ]
        if not candidates:
            self.set_farm_animal_inside(animal, "waiting for a clear doorway")
            return False
        player = (int(self.state.player_x), int(self.state.player_y))
        position = max(candidates, key=lambda candidate: manhattan_distance(candidate, player))
        animal["outside"] = True
        animal["x"], animal["y"] = position
        animal["activity"] = "stepping outside"
        return True

    def farm_animal_apply_grazing(
        self,
        animal: Dict[str, object],
        rng: Optional[random.Random] = None,
        force: bool = False,
    ) -> bool:
        position = self.farm_animal_actor_position(animal)
        if not position or self.base_map[position[1]][position[0]] != ".":
            return False
        today = self.farm_animal_day_key()
        if str(animal.get("last_grazed_day", "")) == today:
            return False
        rng = rng or random.Random()
        if not force and rng.random() >= 0.28:
            return False
        animal["last_grazed_day"] = today
        animal["fed"] = True
        animal["happiness"] = min(100, int(animal.get("happiness", 50)) + 3)
        animal["health"] = min(100, int(animal.get("health", 100)) + 1)
        animal["activity"] = "grazing"
        return True

    def farm_animal_step_toward_home(self, animal: Dict[str, object]) -> bool:
        position = self.farm_animal_actor_position(animal)
        goals = self.farm_animal_home_tiles(animal)
        if not position or not goals:
            self.set_farm_animal_inside(animal)
            return True
        if position in goals:
            self.set_farm_animal_inside(animal)
            return True
        occupied = self.farm_animal_occupied_positions(exclude=animal)
        step = shortest_path_step(
            position,
            goals,
            lambda x, y: self.farm_animal_tile_available(animal, x, y),
            blocked=occupied,
            max_nodes=max(512, self.farm_width() * self.farm_height()),
        )
        if step:
            animal["x"], animal["y"] = step
            animal["activity"] = "heading home"
            if step in goals:
                self.set_farm_animal_inside(animal)
            return True
        if int(self.state.hour) >= 21 or self.town_weather_is_severe_for_routines():
            self.set_farm_animal_inside(animal, "sheltering indoors")
            return True
        animal["activity"] = "looking for the way home"
        return False

    def startle_farm_animal(self, animal: Dict[str, object]) -> bool:
        position = self.farm_animal_actor_position(animal)
        if not position:
            return False
        player = (int(self.state.player_x), int(self.state.player_y))
        preferred = (position[0] - player[0], position[1] - player[1])
        serial = int(getattr(self, "_farm_animal_step_serial", 0)) + 1
        self._farm_animal_step_serial = serial
        rng = random.Random(int(animal.get("id", 0)) * 1009 + serial * 31)
        step = choose_wander_step(
            position,
            lambda x, y: self.farm_animal_tile_available(animal, x, y),
            rng,
            preferred=preferred,
        )
        if step:
            animal["x"], animal["y"] = step
            animal["activity"] = "startled"
            return True
        animal["activity"] = "watching you"
        return False

    def update_farm_animal_actor(self, animal: Dict[str, object], rng: random.Random, force: bool = False):
        anchor = self.farm_animal_home_anchor(animal)
        if not anchor:
            self.set_farm_animal_inside(animal, "without assigned housing")
            return
        should_be_outside = self.farm_animal_should_be_outside(animal)
        position = self.farm_animal_actor_position(animal)

        if not should_be_outside:
            if position:
                self.farm_animal_step_toward_home(animal)
            else:
                self.set_farm_animal_inside(
                    animal,
                    "resting indoors" if not self.town_weather_is_bad_for_routines() else "sheltering from the weather",
                )
            return

        if not position:
            self.spawn_farm_animal_outside(animal)
            return

        _building_key, ax, ay = anchor
        home_center = (ax, ay)
        if manhattan_distance(position, home_center) > self.farm_animal_roam_radius(animal):
            self.farm_animal_step_toward_home(animal)
            return

        trait = str(animal.get("trait", "Gentle"))
        player = (int(self.state.player_x), int(self.state.player_y))
        if self.on_farm() and trait == "Skittish" and manhattan_distance(position, player) <= 2:
            self.startle_farm_animal(animal)
            return

        if self.farm_animal_apply_grazing(animal, rng=rng):
            return

        move_chance = {
            "Playful": 0.85,
            "Curious": 0.78,
            "Skittish": 0.72,
            "Stubborn": 0.38,
            "Sleepy": 0.28,
            "Calm": 0.48,
        }.get(trait, 0.58)
        if not force and rng.random() > move_chance:
            animal["activity"] = "resting in the pasture"
            return

        preferred: Optional[Position] = None
        if trait == "Curious" and self.on_farm():
            preferred = (player[0] - position[0], player[1] - position[1])
        elif trait == "Skittish" and self.on_farm():
            preferred = (position[0] - player[0], position[1] - player[1])
        else:
            preferred = (ax - position[0], ay - position[1]) if rng.random() < 0.18 else None

        step = choose_wander_step(
            position,
            lambda x, y: (
                self.farm_animal_tile_available(animal, x, y)
                and manhattan_distance((x, y), home_center) <= self.farm_animal_roam_radius(animal)
            ),
            rng,
            preferred=preferred,
        )
        if step:
            animal["x"], animal["y"] = step
            animal["activity"] = "wandering" if trait != "Playful" else "trotting around"
            self.farm_animal_apply_grazing(animal, rng=rng)
        else:
            animal["activity"] = "resting in the pasture"

    def update_farm_animal_actors(self, force: bool = False):
        """Advance visible livestock routines on a ten-minute actor clock."""
        self.normalize_farm_animals()
        clock = (
            int(self.state.year) * 600000
            + int(self.state.month) * 50000
            + int(self.state.day) * 1500
            + int(self.state.hour) * 6
            + int(self.state.minute) // 10
        )
        if not force and int(getattr(self, "_farm_animal_actor_tick", -1)) == clock:
            return
        self._farm_animal_actor_tick = clock
        serial = int(getattr(self, "_farm_animal_step_serial", 0)) + 1
        self._farm_animal_step_serial = serial
        for animal in self.state.farm_animals:
            seed = (
                int(animal.get("id", 0)) * 10007
                + clock * 97
                + serial * 17
                + int(self.state.wilderness_seed)
            )
            self.update_farm_animal_actor(animal, random.Random(seed), force=force)

    # ------------------------------------------------------------------
    # Travel followers

    def travel_follower_identity_kind(self, follower_id: str) -> Tuple[str, str]:
        follower_id = str(follower_id or "")
        if ":" not in follower_id:
            return "", follower_id
        kind, source_id = follower_id.split(":", 1)
        return kind, source_id

    def travel_follower_child(self, follower_id: str) -> Optional[Dict[str, object]]:
        kind, source_id = self.travel_follower_identity_kind(follower_id)
        if kind != "child":
            return None
        for child in getattr(self.state, "children", []) or []:
            if str(child.get("id", "")) == source_id:
                return child
        return None

    def travel_follower_data(self, follower_id: str) -> Dict[str, object]:
        kind, source_id = self.travel_follower_identity_kind(follower_id)
        if kind == "companion":
            data = self.party_companion_data(source_id)
            if not data:
                return {}
            return {
                "id": follower_id,
                "source_id": source_id,
                "npc_id": str(data.get("npc_id", source_id)),
                "name": str(data.get("name", source_id)),
                "role": str(data.get("role", "Companion")),
                "kind": "companion",
                "symbol": "@",
                "color": C.WATER,
            }
        if kind == "spouse":
            if source_id != str(getattr(self.state, "spouse_npc_id", "") or ""):
                return {}
            return {
                "id": follower_id,
                "source_id": source_id,
                "npc_id": source_id,
                "name": self.town_npc_name(source_id),
                "role": "Spouse",
                "kind": "spouse",
                "symbol": "@",
                "color": C.CROP_READY,
            }
        if kind == "child":
            child = self.travel_follower_child(follower_id)
            if not child:
                return {}
            child = self.ensure_child_profile_fields(child)
            stage = self.household_child_stage(child)
            return {
                "id": follower_id,
                "source_id": source_id,
                "npc_id": f"household_child:{source_id}",
                "name": str(child.get("name", f"Child {source_id}")),
                "role": stage,
                "kind": "child",
                "symbol": "@",
                "color": C.PLAYER,
            }
        return {}

    def travel_follower_candidate_ids(self) -> List[str]:
        candidates: List[str] = []
        spouse_id = str(getattr(self.state, "spouse_npc_id", "") or "")
        unlocked = {
            str(member_id)
            for member_id in (getattr(self.state, "unlocked_party_member_ids", []) or [])
            if str(member_id or "").strip()
        }
        for companion_id in self.party_known_companion_ids():
            data = self.party_companion_data(companion_id)
            npc_id = str(data.get("npc_id", companion_id))
            if companion_id in unlocked and npc_id != spouse_id:
                candidates.append(f"companion:{companion_id}")
        if spouse_id and bool(getattr(self.state, "spouse_moved_to_farm", False)):
            candidates.append(f"spouse:{spouse_id}")
        for child in getattr(self.state, "children", []) or []:
            try:
                child_id = int(child.get("id", 0))
            except Exception:
                continue
            if child_id > 0 and self.household_child_stage(child) in {
                "Young Child",
                "Child",
                "Teen",
                "Young Adult",
            }:
                candidates.append(f"child:{child_id}")
        return candidates

    def travel_follower_is_eligible(self, follower_id: str) -> bool:
        kind, source_id = self.travel_follower_identity_kind(follower_id)
        if kind == "companion":
            return (
                source_id in set(getattr(self.state, "unlocked_party_member_ids", []) or [])
                and self.party_companion_is_eligible(source_id)
            )
        if kind == "spouse":
            return (
                source_id == str(getattr(self.state, "spouse_npc_id", "") or "")
                and bool(getattr(self.state, "spouse_moved_to_farm", False))
            )
        if kind == "child":
            child = self.travel_follower_child(follower_id)
            return bool(
                child
                and self.household_child_stage(child)
                in {"Young Child", "Child", "Teen", "Young Adult"}
            )
        return False

    def travel_follower_allowed_locations(self, follower_id: str) -> Set[str]:
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        if kind != "child":
            return set(self.TRAVEL_FOLLOWER_SAFE_LOCATIONS | self.TRAVEL_FOLLOWER_ADVENTURE_LOCATIONS)
        child = self.travel_follower_child(follower_id)
        if not child:
            return set()
        stage = self.household_child_stage(child)
        if stage in {"Young Child", "Child"}:
            return set(self.TRAVEL_FOLLOWER_SAFE_LOCATIONS)
        if stage == "Teen":
            return set(self.TRAVEL_FOLLOWER_SAFE_LOCATIONS | {"Wilderness", "WildernessCave"})
        if stage == "Young Adult":
            return set(self.TRAVEL_FOLLOWER_SAFE_LOCATIONS | self.TRAVEL_FOLLOWER_ADVENTURE_LOCATIONS)
        return set()

    def travel_follower_can_enter_location(self, follower_id: str, location: Optional[str] = None) -> bool:
        location = str(location or self.state.location)
        return location in self.travel_follower_allowed_locations(follower_id)

    def travel_follower_combat_eligible(self, follower_id: str) -> bool:
        kind, source_id = self.travel_follower_identity_kind(follower_id)
        if kind == "companion":
            return self.travel_follower_is_eligible(follower_id)
        if kind == "spouse":
            return self.travel_follower_is_eligible(follower_id)
        if kind == "child":
            child = self.travel_follower_child(follower_id)
            return bool(child and self.household_child_stage(child) == "Young Adult")
        return False

    def normalize_travel_followers(self) -> List[str]:
        limit = 3
        self.state.max_travel_followers = limit
        if not isinstance(getattr(self.state, "travel_follower_states", None), dict):
            self.state.travel_follower_states = {}
        if not isinstance(getattr(self.state, "travel_follower_ids", None), list):
            self.state.travel_follower_ids = []

        clean: List[str] = []
        seen = set()
        for raw_id in self.state.travel_follower_ids:
            follower_id = str(raw_id or "").strip()
            if (
                follower_id
                and follower_id not in seen
                and self.travel_follower_is_eligible(follower_id)
            ):
                clean.append(follower_id)
                seen.add(follower_id)
            if len(clean) >= limit:
                break
        self.state.travel_follower_ids = clean

        for follower_id in list(self.state.travel_follower_states):
            if not self.travel_follower_data(follower_id):
                self.state.travel_follower_states.pop(follower_id, None)
        for follower_id in self.travel_follower_candidate_ids():
            record = self.state.travel_follower_states.setdefault(follower_id, {})
            mode = str(record.get("mode", "home") or "home").lower()
            task = str(record.get("task", "") or "")
            if task not in self.TRAVEL_FOLLOWER_TASKS:
                task = ""
            if mode not in {"follow", "wait", "work", "home"}:
                mode = "home"
            if mode == "work" and not task:
                mode = "home"
            try:
                x, y = int(record.get("x", -1)), int(record.get("y", -1))
            except Exception:
                x, y = -1, -1
            try:
                work_units = max(0, int(record.get("work_units", 0)))
            except Exception:
                work_units = 0
            try:
                bond_points = max(0, min(999, int(record.get("bond_points", 0))))
            except Exception:
                bond_points = 0
            try:
                outing_bond_count = max(0, int(record.get("outing_bond_count", 0)))
            except Exception:
                outing_bond_count = 0
            raw_task_xp = record.get("task_xp", {})
            task_xp = {}
            if isinstance(raw_task_xp, dict):
                for task_id, value in raw_task_xp.items():
                    if str(task_id) not in self.TRAVEL_FOLLOWER_TASKS:
                        continue
                    try:
                        task_xp[str(task_id)] = max(0, int(value))
                    except Exception:
                        continue
            raw_work_totals = record.get("work_totals", {})
            work_totals = {}
            if isinstance(raw_work_totals, dict):
                for task_id, value in raw_work_totals.items():
                    if str(task_id) not in self.TRAVEL_FOLLOWER_TASKS:
                        continue
                    try:
                        work_totals[str(task_id)] = max(0, int(value))
                    except Exception:
                        continue
            memories = [
                str(value)
                for value in (record.get("memories", []) if isinstance(record.get("memories"), list) else [])
                if str(value or "").strip()
            ][-16:]
            work_log = [
                str(value)
                for value in (record.get("work_log", []) if isinstance(record.get("work_log"), list) else [])
                if str(value or "").strip()
            ][-12:]
            memory_flags = list(dict.fromkeys(
                str(value)
                for value in (
                    record.get("memory_flags", [])
                    if isinstance(record.get("memory_flags"), list)
                    else []
                )
                if str(value or "").strip()
            ))
            outing_locations = list(dict.fromkeys(
                str(value)
                for value in (
                    record.get("outing_locations", [])
                    if isinstance(record.get("outing_locations"), list)
                    else []
                )
                if str(value or "").strip()
            ))
            expedition_role = str(record.get("expedition_role", "Balanced") or "Balanced")
            if expedition_role not in self.TRAVEL_FOLLOWER_EXPEDITION_ROLES:
                expedition_role = "Balanced"
            bond_milestones = [
                str(value)
                for value in (
                    record.get("bond_milestones", [])
                    if isinstance(record.get("bond_milestones"), list)
                    else []
                )
                if str(value) in {"Familiar", "Trusted", "Close", "Kindred"}
            ]
            bond_milestones = list(dict.fromkeys(bond_milestones))
            record.update({
                "location": str(record.get("location", "Home") or "Home"),
                "x": x,
                "y": y,
                "mode": mode if follower_id in clean else "home",
                "activity": str(record.get("activity", "at home") or "at home"),
                "task": task if follower_id in clean else "",
                "work_day": str(record.get("work_day", "") or ""),
                "work_units": work_units,
                "last_work_tick": str(record.get("last_work_tick", "") or ""),
                "task_xp": task_xp,
                "work_totals": work_totals,
                "work_log": work_log,
                "bond_points": bond_points,
                "checkin_day": str(record.get("checkin_day", "") or ""),
                "shared_moment_day": str(record.get("shared_moment_day", "") or ""),
                "outing_day": str(record.get("outing_day", "") or ""),
                "outing_locations": outing_locations,
                "outing_bond_count": outing_bond_count,
                "memory_flags": memory_flags,
                "memories": memories,
                "expedition_role": expedition_role,
                "bond_milestones": bond_milestones,
                "forage_find_day": str(record.get("forage_find_day", "") or ""),
            })
        return clean

    def active_travel_follower_ids(self) -> List[str]:
        return list(self.normalize_travel_followers())

    def travel_follower_record(self, follower_id: str) -> Dict[str, object]:
        self.normalize_travel_followers()
        return self.state.travel_follower_states.setdefault(str(follower_id), {
            "location": "Home",
            "x": -1,
            "y": -1,
            "mode": "home",
            "activity": "at home",
            "task": "",
            "work_day": "",
            "work_units": 0,
            "last_work_tick": "",
            "task_xp": {},
            "work_totals": {},
            "work_log": [],
            "bond_points": 0,
            "checkin_day": "",
            "shared_moment_day": "",
            "outing_day": "",
            "outing_locations": [],
            "outing_bond_count": 0,
            "memory_flags": [],
            "memories": [],
            "expedition_role": "Balanced",
            "bond_milestones": [],
            "forage_find_day": "",
        })

    def travel_follower_position(self, follower_id: str) -> Optional[Position]:
        follower_id = str(follower_id)
        if follower_id not in self.active_travel_follower_ids():
            return None
        record = self.travel_follower_record(follower_id)
        if str(record.get("location", "")) != str(self.state.location):
            return None
        if str(record.get("mode", "home")) == "home":
            return None
        try:
            x, y = int(record.get("x", -1)), int(record.get("y", -1))
        except Exception:
            return None
        if not self.in_active_bounds(x, y):
            return None
        return x, y

    def travel_follower_at(self, x: int, y: int) -> Optional[str]:
        for follower_id in self.active_travel_follower_ids():
            if self.travel_follower_position(follower_id) == (int(x), int(y)):
                return follower_id
        return None

    def travel_follower_position_lookup(
        self,
        map_width: Optional[int] = None,
        map_height: Optional[int] = None,
    ) -> Dict[Position, str]:
        """Build one render-frame lookup without normalizing once per tile."""
        follower_ids = self.active_travel_follower_ids()
        width = self.active_map_width() if map_width is None else int(map_width)
        height = self.active_map_height() if map_height is None else int(map_height)
        lookup: Dict[Position, str] = {}
        for follower_id in follower_ids:
            record = self.state.travel_follower_states.get(str(follower_id), {})
            if str(record.get("location", "")) != str(self.state.location):
                continue
            if str(record.get("mode", "home")) == "home":
                continue
            try:
                position = (
                    int(record.get("x", -1)),
                    int(record.get("y", -1)),
                )
            except Exception:
                continue
            if (
                0 <= position[0] < width
                and 0 <= position[1] < height
                and position not in lookup
            ):
                lookup[position] = str(follower_id)
        return lookup

    def travel_follower_identity_for_npc_id(self, npc_id: str) -> str:
        npc_id = str(npc_id or "")
        for follower_id in self.active_travel_follower_ids():
            data = self.travel_follower_data(follower_id)
            if str(data.get("npc_id", "")) == npc_id:
                return follower_id
        return ""

    def render_travel_follower(self, follower_id: str) -> str:
        data = self.travel_follower_data(follower_id)
        return colorize(str(data.get("symbol", "@"))[:1], str(data.get("color", C.WATER)))

    def travel_follower_description(self, follower_id: str) -> str:
        data = self.travel_follower_data(follower_id)
        record = self.travel_follower_record(follower_id)
        mode = str(record.get("mode", "home")).title()
        activity = str(record.get("activity", "traveling with you"))
        combat = "battle-ready" if self.travel_follower_combat_eligible(follower_id) else "non-combat"
        return (
            f"{data.get('name', follower_id)} ({data.get('role', 'Follower')}) "
            f"is {activity}. Mode: {mode}; {combat}."
        )

    def travel_follower_task_label(self, task_id: str) -> str:
        return str(self.TRAVEL_FOLLOWER_TASKS.get(str(task_id), "No task"))

    def travel_follower_bond_points(self, follower_id: str) -> int:
        record = self.travel_follower_record(follower_id)
        try:
            return max(0, min(999, int(record.get("bond_points", 0))))
        except Exception:
            return 0

    def travel_follower_bond_rank(self, follower_id: str) -> str:
        points = self.travel_follower_bond_points(follower_id)
        if points >= 120:
            return "Kindred"
        if points >= 65:
            return "Close"
        if points >= 30:
            return "Trusted"
        if points >= 10:
            return "Familiar"
        return "New Companion"

    def adjust_travel_follower_bond(self, follower_id: str, amount: int) -> int:
        record = self.travel_follower_record(follower_id)
        before = self.travel_follower_bond_points(follower_id)
        after = max(0, min(999, before + int(amount)))
        record["bond_points"] = after
        if after > before:
            self.process_travel_follower_bond_milestones(follower_id)
        return after - before

    def travel_follower_tactical_key(self, follower_id: str) -> str:
        kind, source_id = self.travel_follower_identity_kind(follower_id)
        if kind == "companion":
            return source_id
        if kind == "spouse" and self.party_companion_data(source_id):
            return source_id
        return str(follower_id)

    def travel_follower_expedition_role(self, follower_id: str) -> str:
        record = self.travel_follower_record(follower_id)
        role = str(record.get("expedition_role", "Balanced") or "Balanced")
        if role not in self.TRAVEL_FOLLOWER_EXPEDITION_ROLES:
            role = "Balanced"
            record["expedition_role"] = role
        return role

    def travel_follower_expedition_role_options(self, follower_id: str) -> List[str]:
        points = self.travel_follower_bond_points(follower_id)
        roles = ["Balanced"]
        if points >= 10:
            roles.extend(["Scout", "Gatherer"])
        if points >= 30:
            roles.extend(["Guardian", "Support"])
        return roles

    def set_travel_follower_expedition_role(self, follower_id: str, role: str) -> bool:
        role = str(role)
        if role not in self.travel_follower_expedition_role_options(follower_id):
            self.set_message("That expedition role has not been unlocked by this bond yet.")
            return False
        record = self.travel_follower_record(follower_id)
        record["expedition_role"] = role
        name = str(self.travel_follower_data(follower_id).get("name", follower_id))
        self.autosave_with_message(f"{name}'s expedition role is now {role}.")
        return True

    def travel_follower_bond_milestone_text(self, follower_id: str, milestone: str) -> str:
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        name = str(self.travel_follower_data(follower_id).get("name", "Your follower"))
        family_text = {
            "Familiar": f"{name} begins suggesting small detours and shared routines without hesitation.",
            "Trusted": f"You and {name} have learned when to lead, when to follow, and when to simply stay close.",
            "Close": f"{name} speaks honestly about hopes for the road ahead, trusting you with the unfinished parts.",
            "Kindred": f"You and {name} no longer need to explain why you will show up for one another.",
        }
        companion_text = {
            "Familiar": f"{name} starts treating your plans as a shared problem instead of someone else's orders.",
            "Trusted": f"You and {name} move with the confidence of people who have solved hard days together.",
            "Close": f"{name} shares the private reason this work matters and asks you to remember it.",
            "Kindred": f"You and {name} have become the sort of team that changes what each believes is possible.",
        }
        return (family_text if kind in {"spouse", "child"} else companion_text).get(milestone, "")

    def process_travel_follower_bond_milestones(self, follower_id: str) -> List[str]:
        gained: List[str] = []
        points = self.travel_follower_bond_points(follower_id)
        for threshold, milestone in [(10, "Familiar"), (30, "Trusted"), (65, "Close"), (120, "Kindred")]:
            record = self.travel_follower_record(follower_id)
            claimed = record.setdefault("bond_milestones", [])
            if points < threshold or milestone in claimed:
                continue
            claimed.append(milestone)
            record["bond_milestones"] = list(dict.fromkeys(str(value) for value in claimed))
            gained.append(milestone)
            text = self.travel_follower_bond_milestone_text(follower_id, milestone)
            self.record_travel_follower_memory(
                follower_id,
                f"Bond milestone - {milestone}: {text}",
                flag=f"bond:{milestone}",
            )
            kind, _source_id = self.travel_follower_identity_kind(follower_id)
            if kind in {"spouse", "child"}:
                self.adjust_family_bond(2 if milestone in {"Familiar", "Trusted"} else 3)
                self.record_family_event(f"{milestone} Bond", text)
            if milestone in {"Close", "Kindred"} and self.travel_follower_combat_eligible(follower_id):
                tactical_key = self.travel_follower_tactical_key(follower_id)
                progress = self.combat_progress_for_key(tactical_key)
                progress["skill_points"] = max(0, int(progress.get("skill_points", 0))) + 1
                self.save_combat_progress_for_key(tactical_key, progress, autosave=False)
        return gained

    def apply_travel_follower_expedition_role(
        self,
        follower_id: str,
        profile: Dict[str, object],
    ) -> Dict[str, object]:
        if not profile:
            return profile
        role = self.travel_follower_expedition_role(follower_id)
        profile = dict(profile)
        profile["expedition_role"] = role
        if role == "Scout":
            profile["move_range"] = max(1, int(profile.get("move_range", 5))) + 1
        elif role == "Guardian":
            profile["max_hp"] = max(1, int(profile.get("max_hp", 1))) + 3
            profile["current_hp"] = max(1, int(profile.get("current_hp", 1))) + 3
            profile["defense"] = max(0, int(profile.get("defense", 0))) + 1
        elif role == "Support":
            profile["max_focus"] = max(0, int(profile.get("max_focus", 0))) + 3
            profile["focus"] = max(0, int(profile.get("focus", 0))) + 3
            inventory = dict(profile.get("inventory", {}) or {})
            inventory["Potion"] = int(inventory.get("Potion", 0)) + 1
            profile["inventory"] = inventory
        return profile

    def travel_follower_personality_label(self, follower_id: str) -> str:
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        if kind == "child":
            child = self.travel_follower_child(follower_id)
            if child:
                return str(self.ensure_child_profile_fields(child).get("personality_trait", "Curious"))
        if kind == "spouse":
            return f"{self.spouse_support_mode()} partner"
        data = self.travel_follower_data(follower_id)
        return str(data.get("role", "Companion"))

    def travel_follower_preferred_task(self, follower_id: str) -> str:
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        if kind == "child":
            child = self.travel_follower_child(follower_id)
            trait = str(
                self.ensure_child_profile_fields(child).get("personality_trait", "Curious")
                if child
                else "Curious"
            )
            return {
                "Gentle": "animal_care",
                "Outdoorsy": "gather_forage",
                "Practical": "harvest_crops",
                "Bold": "harvest_crops",
                "Tinkering": "harvest_crops",
                "Curious": "water_crops",
                "Studious": "water_crops",
                "Musical": "water_crops",
            }.get(trait, "water_crops")
        if kind == "spouse":
            return {
                "Farm": "water_crops",
                "Forage": "gather_forage",
                "Meals": "animal_care",
                "Rest": "animal_care",
                "Balanced": "water_crops",
            }.get(self.spouse_support_mode(), "water_crops")
        role = str(self.travel_follower_data(follower_id).get("role", "")).lower()
        if any(word in role for word in ("handler", "medic", "healer", "caretaker")):
            return "animal_care"
        if any(word in role for word in ("botanist", "forager", "pathfinder", "scout")):
            return "gather_forage"
        if any(word in role for word in ("breaker", "vanguard", "builder")):
            return "harvest_crops"
        return "water_crops"

    def travel_follower_task_experience_label(self, follower_id: str, task_id: str) -> str:
        record = self.travel_follower_record(follower_id)
        points = int((record.get("task_xp", {}) or {}).get(str(task_id), 0))
        if points >= 36:
            return "Expert"
        if points >= 20:
            return "Skilled"
        if points >= 8:
            return "Steady"
        return "Learning"

    def record_travel_follower_memory(
        self,
        follower_id: str,
        text: str,
        flag: str = "",
    ) -> bool:
        record = self.travel_follower_record(follower_id)
        flags = record.setdefault("memory_flags", [])
        flag = str(flag or "").strip()
        if flag and flag in flags:
            return False
        if flag:
            flags.append(flag)
        memories = record.setdefault("memories", [])
        memories.append(str(text))
        record["memories"] = [str(value) for value in memories if str(value or "").strip()][-16:]
        return True

    def travel_follower_location_theme(self, location: Optional[str] = None) -> Tuple[str, str, str]:
        location = str(location or self.state.location)
        if location == "Farm":
            return "Farm", "the farm", "Set out across the home fields together."
        if location == "HouseInterior":
            return "Home", "home", "Made time for one another at home."
        if location == "Town" or location.endswith("Interior"):
            return "Town", "town", "Wandered through town together."
        if location == "Mine":
            return "Mine", "the mine", "Descended into the mine together."
        if location == "Wilderness":
            return "Wilderness", "the wilderness", "Explored the wilderness together."
        if location == "WildernessCave":
            return "WildernessCave", "a wilderness cave", "Investigated a hidden wilderness cave together."
        if location == "WildernessDungeon":
            return "WildernessDungeon", "the old ruins", "Ventured into the old ruins together."
        return location, location.lower(), f"Traveled through {location} together."

    def record_travel_follower_outing(self, follower_id: str) -> bool:
        record = self.travel_follower_record(follower_id)
        if str(record.get("mode", "")) != "follow":
            return False
        today = self.travel_follower_work_day_key()
        if str(record.get("outing_day", "")) != today:
            record["outing_day"] = today
            record["outing_locations"] = []
            record["outing_bond_count"] = 0
        theme, place, memory = self.travel_follower_location_theme()
        visited_today = record.setdefault("outing_locations", [])
        if theme in visited_today:
            return False
        visited_today.append(theme)
        daily_bond_limit = 3 if self.travel_follower_expedition_role(follower_id) == "Scout" else 2
        if int(record.get("outing_bond_count", 0)) < daily_bond_limit:
            self.adjust_travel_follower_bond(follower_id, 1)
            record["outing_bond_count"] = int(record.get("outing_bond_count", 0)) + 1
        new_memory = self.record_travel_follower_memory(
            follower_id,
            f"{today} - {memory}",
            flag=f"visited:{theme}",
        )
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        if new_memory and kind in {"spouse", "child"}:
            name = str(self.travel_follower_data(follower_id).get("name", "A family member"))
            self.adjust_family_bond(1)
            self.record_family_event("Family Outing", f"{name}: {memory}")
        if (
            self.travel_follower_expedition_role(follower_id) == "Gatherer"
            and str(record.get("forage_find_day", "")) != today
        ):
            item = self.travel_follower_outing_find(follower_id, theme)
            if item:
                self.state.inventory[item] = self.state.inventory.get(item, 0) + 1
                record["forage_find_day"] = today
                record["activity"] = f"found 1 {item} along the way"
                self.record_travel_follower_memory(
                    follower_id,
                    f"{today} - Found {item} while traveling through {place}.",
                )
        return True

    def travel_follower_outing_find(self, follower_id: str, theme: str) -> str:
        season = str(getattr(self.state, "season", "Spring"))
        if theme in {"Mine", "WildernessCave", "WildernessDungeon"}:
            pool = ["Stone", "Coal", "Cave Herbs"]
        elif theme == "Farm":
            pool = ["Mixed Seeds", "Wildflower", "Berries"]
        elif theme == "Town":
            pool = ["Berries", "Wildflower", "Soft Fiber"]
        else:
            seasonal = {
                "Spring": ["Wildflower", "Watercress", "Berries"],
                "Summer": ["Berries", "Wildflower", "Soft Fiber"],
                "Fall": ["Cave Mushroom", "Berries", "Pine Nuts"],
                "Winter": ["Cave Herbs", "Pine Nuts", "Soft Fiber"],
            }
            pool = seasonal.get(season, ["Berries", "Wildflower", "Soft Fiber"])
        seed = (
            sum(ord(char) for char in str(follower_id))
            + int(self.state.year) * 97
            + int(self.state.month) * 31
            + int(self.state.day) * 7
            + sum(ord(char) for char in str(theme))
        )
        return str(pool[seed % len(pool)])

    def travel_follower_context_line(self, follower_id: str) -> str:
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        _theme, place, _memory = self.travel_follower_location_theme()
        weather = str(getattr(self.state, "weather", "Clear"))
        hour = int(getattr(self.state, "hour", 12))
        rank = self.travel_follower_bond_rank(follower_id)
        if kind == "child":
            pools = {
                "Farm": [
                    "I like seeing which parts of the farm change while we are busy.",
                    "Can I choose the next row we check?",
                    "The farm feels bigger when we walk it together.",
                ],
                "Town": [
                    "Everyone in town seems to know a different piece of the story.",
                    "Can we take the long way back?",
                    "I keep noticing places I want to visit again.",
                ],
                "Wilderness": [
                    "I am trying to remember every trail marker.",
                    "The wild sounds different when we stop talking.",
                    "Do you think this path has always been here?",
                ],
            }
            lines = pools.get(
                self.travel_follower_location_theme()[0],
                [
                    f"There is a lot to notice around {place}.",
                    "I am glad you brought me along.",
                    "I will remember this part.",
                ],
            )
        elif kind == "spouse":
            lines = [
                f"It is good to be beside you out here in {place}.",
                "We should make room for days like this more often.",
                "The work feels lighter when we share the road.",
            ]
        else:
            lines = [
                f"I am watching the route through {place}.",
                "We make a capable team when we keep each other informed.",
                "Say the word if you want me to change pace or priorities.",
            ]
        seed_text = (
            f"{follower_id}|{self.travel_follower_work_day_key()}|{self.state.location}|"
            f"{weather}|{hour}|{rank}"
        )
        line = lines[sum(ord(char) for char in seed_text) % len(lines)]
        if weather in {"Storm", "Stormy", "Blizzard"}:
            line += " We should keep an eye on the weather and know when to turn back."
        elif weather in {"Rain", "Rainy", "Snow", "Snowy"}:
            line += " The weather makes everything feel a little different today."
        elif hour >= 19:
            line += " We should not let the road steal the whole evening."
        elif hour < 9:
            line += " It feels like the whole day is still ahead of us."
        if rank in {"Close", "Kindred"}:
            line += " I know your rhythm well enough now that silence is comfortable too."
        personality = self.travel_follower_personality_label(follower_id)
        personality_notes = {
            "Curious": " I have at least three questions, but I am deciding which one matters most.",
            "Outdoorsy": " I want to remember the air, the tracks, and which way the wind was moving.",
            "Studious": " I should write down what we noticed before the details blur.",
            "Practical": " I keep spotting small things we could repair or improve.",
            "Gentle": " I hope we have not rushed past anyone who needed patience.",
            "Bold": " If the road gets difficult, I would rather meet it with you than avoid it.",
            "Musical": " Our footsteps have a rhythm today.",
            "Tinkering": " Every gate, hinge, and old mechanism out here is trying to tell a story.",
            "Farm partner": " I keep seeing tomorrow's farm work hiding inside today's details.",
            "Forage partner": " I have been watching the edges of the path for anything useful.",
            "Meals partner": " We should bring something good home and make an evening of it.",
            "Rest partner": " Let us leave enough energy for ourselves when the work is done.",
            "Balanced partner": " A steady day together is enough; it does not need to become a contest.",
        }
        line += personality_notes.get(personality, "")
        return line

    def check_in_with_travel_follower(self, follower_id: str) -> Tuple[str, int]:
        line = self.travel_follower_context_line(follower_id)
        record = self.travel_follower_record(follower_id)
        today = self.travel_follower_work_day_key()
        gained = 0
        if str(record.get("checkin_day", "")) != today:
            record["checkin_day"] = today
            gained = self.adjust_travel_follower_bond(follower_id, 1)
            kind, source_id = self.travel_follower_identity_kind(follower_id)
            if kind == "child":
                child = self.travel_follower_child(follower_id)
                if child:
                    self.adjust_child_affection(child, 1)
            else:
                npc_id = str(self.travel_follower_data(follower_id).get("npc_id", source_id))
                if npc_id:
                    self.adjust_town_npc_relationship(npc_id, 1)
                if kind == "spouse":
                    self.adjust_family_bond(1)
            name = str(self.travel_follower_data(follower_id).get("name", "Your follower"))
            self.autosave_with_message(f"You took a moment to check in with {name}.")
        return line, gained

    def travel_follower_shared_moment_label(self, follower_id: str) -> str:
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        if kind == "spouse":
            return "Share a quiet moment"
        if kind == "child":
            child = self.travel_follower_child(follower_id)
            stage = self.household_child_stage(child) if child else "Child"
            if stage == "Young Child":
                return "Play together"
            if stage in {"Child", "Teen"}:
                return "Explore together"
            return "Catch up together"
        return "Review the day together"

    def travel_follower_child_learning_topic(self) -> str:
        theme, _place, _memory = self.travel_follower_location_theme()
        if theme == "Farm":
            return "Farming"
        if theme == "Wilderness":
            return "Foraging"
        if theme in {"Mine", "WildernessCave", "WildernessDungeon"}:
            return "Mining"
        if theme == "Town":
            return "Reading"
        return "Care"

    def share_travel_follower_moment(self, follower_id: str) -> Tuple[bool, str]:
        if follower_id not in self.active_travel_follower_ids():
            return False, "They need to be accompanying you first."
        record = self.travel_follower_record(follower_id)
        today = self.travel_follower_work_day_key()
        if str(record.get("shared_moment_day", "")) == today:
            return False, "You already made time for a shared moment today."
        record["shared_moment_day"] = today
        self.adjust_travel_follower_bond(follower_id, 4)
        kind, source_id = self.travel_follower_identity_kind(follower_id)
        data = self.travel_follower_data(follower_id)
        name = str(data.get("name", "Your follower"))
        theme, place, _memory = self.travel_follower_location_theme()
        if kind == "spouse":
            detail = f"You and {name} let the noise of {place} fall away for a while."
            self.adjust_town_npc_relationship(str(data.get("npc_id", source_id)), 2)
            self.adjust_family_bond(2)
        elif kind == "child":
            detail = f"You let {name} set the pace and turn {place} into a small adventure."
            child = self.travel_follower_child(follower_id)
            if child:
                self.adjust_child_affection(child, 4)
                topic = self.travel_follower_child_learning_topic()
                learning = self.child_learning_map(child)
                learning[topic] = int(learning.get(topic, 0)) + 1
                self.update_child_apprentice_path_from_learning(child)
                detail += f" {name} learned a little about {topic.lower()}."
            self.adjust_family_bond(2)
        else:
            detail = f"You and {name} compared notes, traded observations, and found an easier rhythm."
            npc_id = str(data.get("npc_id", source_id))
            if npc_id:
                self.adjust_town_npc_relationship(npc_id, 1)
        self.record_travel_follower_memory(follower_id, f"{today} - {detail}")
        first_here_flag = f"shared:{theme}"
        flags = record.setdefault("memory_flags", [])
        first_here = first_here_flag not in flags
        if first_here:
            flags.append(first_here_flag)
        if first_here and kind in {"spouse", "child"}:
            self.record_family_event("Shared Time", detail)
        self.advance_time(20)
        self.autosave_with_message(f"Spent a little unhurried time with {name}.")
        return True, detail

    def travel_follower_bond_lines(self, follower_id: str) -> List[str]:
        data = self.travel_follower_data(follower_id)
        record = self.travel_follower_record(follower_id)
        memories = list(record.get("memories", []) or [])
        lines = [
            "BOND & MEMORIES",
            "",
            f"{data.get('name', follower_id)}",
            f"Bond: {self.travel_follower_bond_rank(follower_id)} ({self.travel_follower_bond_points(follower_id)}/999)",
            f"Personality: {self.travel_follower_personality_label(follower_id)}",
            f"Expedition role: {self.travel_follower_expedition_role(follower_id)}",
        ]
        kind, source_id = self.travel_follower_identity_kind(follower_id)
        if kind == "spouse":
            npc_id = str(data.get("npc_id", source_id))
            relationship = self.town_npc_relationship(npc_id)
            lines.extend([
                f"Marriage relationship: {self.town_npc_friendship_label(relationship)} ({relationship})",
                f"Household: {self.family_bond_rank()} ({self.family_bond_score()}/999)",
            ])
        elif kind == "child":
            child = self.travel_follower_child(follower_id)
            if child:
                topic, points = self.child_top_learning_topic(child)
                lines.append(
                    f"Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)}/999)"
                )
                lines.append(f"Growing path: {child.get('apprentice_path', 'Undecided')}")
                if topic:
                    lines.append(f"Strongest interest: {topic} ({points})")
        else:
            npc_id = str(data.get("npc_id", source_id))
            relationship = self.town_npc_relationship(npc_id)
            lines.append(f"Friendship: {self.town_npc_friendship_label(relationship)} ({relationship})")
        milestones = list(record.get("bond_milestones", []) or [])
        lines.extend([
            "",
            "Bond milestones: " + (", ".join(milestones) if milestones else "none yet"),
            "Familiar unlocks Scout and Gatherer roles.",
            "Trusted unlocks Guardian and Support roles.",
            "Close and Kindred grant a tactical skill point to battle-ready followers.",
            "",
            "Recent shared memories:",
        ])
        if memories:
            lines.extend(f"- {memory}" for memory in memories[-8:])
        else:
            lines.append("- No shared memories yet. Travel and make time together.")
        return lines

    def travel_follower_work_report_lines(self, follower_id: str) -> List[str]:
        data = self.travel_follower_data(follower_id)
        record = self.travel_follower_record(follower_id)
        task = str(record.get("task", "") or "")
        preferred = self.travel_follower_preferred_task(follower_id)
        totals = record.get("work_totals", {}) or {}
        log = list(record.get("work_log", []) or [])
        lines = [
            "HELPER REPORT",
            "",
            f"{data.get('name', follower_id)}",
            f"Current assignment: {self.travel_follower_task_label(task)}",
            f"Today: {int(record.get('work_units', 0))}/{self.travel_follower_work_limit(follower_id)} actions",
            f"Natural strength: {self.travel_follower_task_label(preferred)}",
            "",
            "Experience:",
        ]
        for task_id, label in self.TRAVEL_FOLLOWER_TASKS.items():
            xp = int((record.get("task_xp", {}) or {}).get(task_id, 0))
            total = int(totals.get(task_id, 0))
            marker = "*" if task_id == preferred else "-"
            lines.append(
                f"{marker} {label}: {self.travel_follower_task_experience_label(follower_id, task_id)} "
                f"({xp} xp; {total} completed)"
            )
        lines.extend(["", "Recent work:"])
        if log:
            lines.extend(f"- {entry}" for entry in log[-6:])
        else:
            lines.append("- No completed helper work recorded yet.")
        return lines

    def travel_follower_task_options(self, follower_id: str) -> List[str]:
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        if kind != "child":
            return list(self.TRAVEL_FOLLOWER_TASKS)
        child = self.travel_follower_child(follower_id)
        if not child:
            return []
        stage = self.household_child_stage(child)
        if stage == "Young Child":
            return ["animal_care"]
        if stage == "Child":
            return ["water_crops", "animal_care"]
        if stage in {"Teen", "Young Adult"}:
            return list(self.TRAVEL_FOLLOWER_TASKS)
        return []

    def travel_follower_work_day_key(self) -> str:
        return f"{self.state.year}-{self.state.month}-{self.state.day}"

    def travel_follower_work_limit(self, follower_id: str) -> int:
        kind, _source_id = self.travel_follower_identity_kind(follower_id)
        base = 6
        if kind == "child":
            child = self.travel_follower_child(follower_id)
            stage = self.household_child_stage(child) if child else ""
            base = {
                "Young Child": 2,
                "Child": 4,
                "Teen": 5,
                "Young Adult": 6,
            }.get(stage, 0)
        record = self.travel_follower_record(follower_id)
        task = str(record.get("task", "") or "")
        xp = int((record.get("task_xp", {}) or {}).get(task, 0))
        proficiency_bonus = min(2, xp // 12)
        bond = self.travel_follower_bond_points(follower_id)
        bond_bonus = 2 if bond >= 80 else (1 if bond >= 30 else 0)
        preference_bonus = 1 if task and task == self.travel_follower_preferred_task(follower_id) else 0
        return max(0, base + proficiency_bonus + bond_bonus + preference_bonus)

    def reset_travel_follower_work_day(self) -> None:
        today = self.travel_follower_work_day_key()
        for follower_id in self.active_travel_follower_ids():
            record = self.travel_follower_record(follower_id)
            if str(record.get("work_day", "")) == today:
                continue
            record["work_day"] = today
            record["work_units"] = 0
            record["last_work_tick"] = ""
            if str(record.get("mode", "")) == "work":
                task = str(record.get("task", "") or "")
                record["activity"] = f"ready to {self.travel_follower_task_label(task).lower()}"

    def assign_travel_follower_task(self, follower_id: str, task_id: str) -> bool:
        follower_id = str(follower_id)
        task_id = str(task_id)
        if follower_id not in self.active_travel_follower_ids():
            self.set_message("That follower must be accompanying you before receiving a task.")
            return False
        if task_id not in self.travel_follower_task_options(follower_id):
            self.set_message("That farm task is not appropriate for this follower.")
            return False
        record = self.travel_follower_record(follower_id)
        record.update({
            "location": "Farm",
            "x": int(record.get("x", -1)) if str(record.get("location", "")) == "Farm" else -1,
            "y": int(record.get("y", -1)) if str(record.get("location", "")) == "Farm" else -1,
            "mode": "work",
            "task": task_id,
            "activity": f"assigned to {self.travel_follower_task_label(task_id).lower()}",
        })
        self.reset_travel_follower_work_day()
        data = self.travel_follower_data(follower_id)
        self.autosave_with_message(
            f"{data.get('name', follower_id)} will {self.travel_follower_task_label(task_id).lower()} during the day."
        )
        return True

    def set_travel_follower_work_position(self, follower_id: str, x: int, y: int) -> None:
        record = self.travel_follower_record(follower_id)
        candidates = [(int(x), int(y))]
        candidates.extend((int(x) + dx, int(y) + dy) for dx, dy in CARDINAL_STEPS)
        if self.on_farm():
            available = [
                position
                for position in candidates
                if self.travel_follower_tile_available(follower_id, *position)
            ]
            if available:
                x, y = available[0]
        else:
            for candidate_x, candidate_y in candidates[1:] + candidates[:1]:
                if not (0 <= candidate_y < len(self.base_map) and 0 <= candidate_x < len(self.base_map[candidate_y])):
                    continue
                if self.base_map[candidate_y][candidate_x] in {"#", "~", "H", "B"}:
                    continue
                x, y = candidate_x, candidate_y
                break
        record["location"] = "Farm"
        record["x"] = int(x)
        record["y"] = int(y)

    def travel_follower_water_one_crop(self, follower_id: str) -> bool:
        land_map = self.base_map
        for y, row in enumerate(land_map):
            for x, tile in enumerate(row):
                crop = self.crop_for_scope("Farm", x, y)
                if not crop or crop.ready or crop.watered:
                    continue
                crop.watered = True
                if tile == ",":
                    land_map[y][x] = "w"
                elif tile == "f":
                    land_map[y][x] = "F"
                self.set_travel_follower_work_position(follower_id, x, y)
                record = self.travel_follower_record(follower_id)
                record["activity"] = f"watering {crop.name} at {x},{y}"
                return True
        self.travel_follower_record(follower_id)["activity"] = "finished watering crops for today"
        return False

    def travel_follower_harvest_one_crop(self, follower_id: str) -> bool:
        land_map = self.base_map
        for y, row in enumerate(land_map):
            for x, _tile in enumerate(row):
                crop = self.crop_for_scope("Farm", x, y)
                if not crop or not crop.ready:
                    continue
                quality = crop.projected_quality()
                item_name = quality_item_name(crop.name, quality)
                self.state.inventory[item_name] = self.state.inventory.get(item_name, 0) + 1
                self.remove_crop_for_scope("Farm", x, y)
                land_map[y][x] = ","
                self.set_travel_follower_work_position(follower_id, x, y)
                self.travel_follower_record(follower_id)["activity"] = f"harvested 1 {item_name}"
                return True
        self.travel_follower_record(follower_id)["activity"] = "finished harvesting for today"
        return False

    def travel_follower_care_for_one_animal(self, follower_id: str) -> bool:
        self.normalize_farm_animals()
        feed_available = self.state.inventory.get("Mixed Seeds", 0) > 0
        for animal in self.state.farm_animals:
            needs_pet = not bool(animal.get("petted_today"))
            needs_feed = not bool(animal.get("fed"))
            if not needs_pet and not (needs_feed and feed_available):
                continue
            actions: List[str] = []
            if needs_feed and feed_available:
                self.state.inventory["Mixed Seeds"] -= 1
                animal["fed"] = True
                animal["happiness"] = min(100, int(animal.get("happiness", 50)) + 8)
                animal["health"] = min(100, int(animal.get("health", 100)) + 2)
                feed_available = self.state.inventory.get("Mixed Seeds", 0) > 0
                actions.append("fed")
            if needs_pet:
                trait = str(animal.get("trait", "Gentle"))
                animal["petted_today"] = True
                animal["happiness"] = min(
                    100,
                    int(animal.get("happiness", 50)) + (7 if trait in {"Gentle", "Playful"} else 5),
                )
                animal["affection"] = min(
                    100,
                    int(animal.get("affection", 0)) + (5 if trait in {"Gentle", "Curious", "Playful"} else 3),
                )
                actions.append("petted")
            x = int(animal.get("x", 8))
            y = int(animal.get("y", 8))
            self.set_travel_follower_work_position(follower_id, x, y)
            self.travel_follower_record(follower_id)["activity"] = (
                f"{' and '.join(actions)} {animal.get('name', 'an animal')}"
            )
            return True
        record = self.travel_follower_record(follower_id)
        if any(not bool(animal.get("fed")) for animal in self.state.farm_animals) and not feed_available:
            record["activity"] = "waiting for Mixed Seeds to feed the animals"
        else:
            record["activity"] = "finished caring for the animals today"
        return False

    def travel_follower_gather_one_forage(self, follower_id: str) -> bool:
        record = self.travel_follower_record(follower_id)
        item = self.travel_follower_outing_find(follower_id, "Wilderness")
        self.state.inventory[item] = self.state.inventory.get(item, 0) + 1
        record["location"] = "Farm"
        record["x"] = -1
        record["y"] = -1
        record["activity"] = f"gathered 1 {item} from nearby paths"
        return True

    def perform_travel_follower_work(self, follower_id: str) -> bool:
        record = self.travel_follower_record(follower_id)
        task = str(record.get("task", "") or "")
        if task == "water_crops":
            return self.travel_follower_water_one_crop(follower_id)
        if task == "harvest_crops":
            return self.travel_follower_harvest_one_crop(follower_id)
        if task == "animal_care":
            return self.travel_follower_care_for_one_animal(follower_id)
        if task == "gather_forage":
            return self.travel_follower_gather_one_forage(follower_id)
        return False

    def process_travel_follower_work_hour(self) -> None:
        hour = int(self.state.hour)
        if hour < 7 or hour >= 19:
            return
        self.reset_travel_follower_work_day()
        tick = f"{self.travel_follower_work_day_key()}-{hour}"
        severe_weather = bool(self.town_weather_is_severe_for_routines())
        for follower_id in self.active_travel_follower_ids():
            record = self.travel_follower_record(follower_id)
            if str(record.get("mode", "")) != "work":
                continue
            if str(record.get("last_work_tick", "")) == tick:
                continue
            record["last_work_tick"] = tick
            if severe_weather:
                record["activity"] = "sheltering from the severe weather"
                continue
            limit = self.travel_follower_work_limit(follower_id)
            if int(record.get("work_units", 0)) >= limit:
                record["activity"] = "resting after finishing today's chores"
                continue
            if not self.perform_travel_follower_work(follower_id):
                continue
            record["work_units"] = int(record.get("work_units", 0)) + 1
            task = str(record.get("task", "") or "")
            task_xp = record.setdefault("task_xp", {})
            preferred = task == self.travel_follower_preferred_task(follower_id)
            task_xp[task] = int(task_xp.get(task, 0)) + (2 if preferred else 1)
            work_totals = record.setdefault("work_totals", {})
            work_totals[task] = int(work_totals.get(task, 0)) + 1
            work_log = record.setdefault("work_log", [])
            activity = str(record.get("activity", self.travel_follower_task_label(task).lower()))
            work_log.append(f"{self.travel_follower_work_day_key()}, {hour:02d}:00 - {activity}")
            record["work_log"] = [str(entry) for entry in work_log if str(entry or "").strip()][-12:]
            if int(work_totals[task]) % 5 == 0:
                self.adjust_travel_follower_bond(follower_id, 1)
            kind, _source_id = self.travel_follower_identity_kind(follower_id)
            if kind == "child" and int(work_totals[task]) % 4 == 0:
                child = self.travel_follower_child(follower_id)
                if child:
                    topic = {
                        "animal_care": "Care",
                        "gather_forage": "Foraging",
                    }.get(task, "Farming")
                    learning = self.child_learning_map(child)
                    learning[topic] = int(learning.get(topic, 0)) + 1
                    self.update_child_apprentice_path_from_learning(child)

    def travel_follower_tile_available(
        self,
        follower_id: str,
        x: int,
        y: int,
        allow_player: bool = False,
    ) -> bool:
        if not self.in_active_bounds(x, y):
            return False
        if not allow_player and (x, y) == (int(self.state.player_x), int(self.state.player_y)):
            return False
        occupying_follower = self.travel_follower_at(x, y)
        if occupying_follower and occupying_follower != follower_id:
            return False
        if self.town_npc_at(x, y):
            return False
        return bool(self.passable(x, y, ignore_travel_follower_id=follower_id))

    def travel_follower_formation_index(self, follower_id: str) -> int:
        try:
            return self.active_travel_follower_ids().index(str(follower_id))
        except ValueError:
            return -1

    def travel_follower_formation_label(self, follower_id: str) -> str:
        index = self.travel_follower_formation_index(follower_id)
        return {
            0: "Rear guard",
            1: "Left flank",
            2: "Right flank",
        }.get(index, "Unassigned")

    def travel_follower_formation_offset(
        self,
        follower_id: str,
        facing: Optional[str] = None,
    ) -> Position:
        index = max(0, self.travel_follower_formation_index(follower_id))
        facing = str(facing or getattr(self.state, "facing", "DOWN"))
        formations = {
            "UP": ((0, 1), (-1, 0), (1, 0)),
            "DOWN": ((0, -1), (1, 0), (-1, 0)),
            "LEFT": ((1, 0), (0, 1), (0, -1)),
            "RIGHT": ((-1, 0), (0, -1), (0, 1)),
        }
        offsets = formations.get(facing, formations["DOWN"])
        return offsets[min(index, len(offsets) - 1)]

    def travel_follower_formation_target(self, follower_id: str) -> Position:
        player = (int(self.state.player_x), int(self.state.player_y))
        dx, dy = self.travel_follower_formation_offset(follower_id)
        return player[0] + dx, player[1] + dy

    def reform_travel_follower_formation(self) -> None:
        following = []
        for follower_id in self.active_travel_follower_ids():
            record = self.travel_follower_record(follower_id)
            if str(record.get("mode", "")) == "follow":
                following.append(follower_id)
                record["x"] = -1
                record["y"] = -1
        for follower_id in following:
            self.recover_travel_follower(follower_id)

    def set_travel_follower_formation_slot(self, follower_id: str, slot: int) -> bool:
        follower_id = str(follower_id)
        active = self.active_travel_follower_ids()
        if follower_id not in active:
            self.set_message("That follower is not in your traveling group.")
            return False
        slot = max(0, min(len(active) - 1, int(slot)))
        current = active.index(follower_id)
        if current == slot:
            self.set_message(
                f"{self.travel_follower_data(follower_id).get('name', follower_id)} "
                f"is already in the {self.travel_follower_formation_label(follower_id).lower()} position."
            )
            return False
        active.pop(current)
        active.insert(slot, follower_id)
        self.state.travel_follower_ids = active
        self.reform_travel_follower_formation()
        data = self.travel_follower_data(follower_id)
        self.autosave_with_message(
            f"{data.get('name', follower_id)} moved to the "
            f"{self.travel_follower_formation_label(follower_id).lower()} position."
        )
        return True

    def nearest_travel_follower_position(self, follower_id: str) -> Optional[Position]:
        player = (int(self.state.player_x), int(self.state.player_y))
        preferred = self.travel_follower_formation_target(follower_id)
        if self.travel_follower_tile_available(follower_id, *preferred):
            return preferred
        for radius in range(1, 7):
            candidates: List[Position] = []
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) != radius:
                        continue
                    position = (player[0] + dx, player[1] + dy)
                    if self.travel_follower_tile_available(follower_id, *position):
                        candidates.append(position)
            if candidates:
                candidates.sort(key=lambda pos: (manhattan_distance(pos, preferred), pos[1], pos[0]))
                return candidates[0]
        return None

    def recover_travel_follower(self, follower_id: str) -> bool:
        record = self.travel_follower_record(follower_id)
        if str(record.get("mode", "home")) != "follow":
            return False
        if not self.travel_follower_can_enter_location(follower_id):
            record.update({
                "location": "Home",
                "x": -1,
                "y": -1,
                "activity": "waiting safely at home",
            })
            return False
        position = self.nearest_travel_follower_position(follower_id)
        if position is None:
            record.update({
                "location": str(self.state.location),
                "x": -1,
                "y": -1,
                "activity": "catching up nearby",
            })
            return False
        record.update({
            "location": str(self.state.location),
            "x": int(position[0]),
            "y": int(position[1]),
            "activity": "following you",
        })
        return True

    def sync_travel_followers(self) -> None:
        for follower_id in self.active_travel_follower_ids():
            record = self.travel_follower_record(follower_id)
            if str(record.get("mode", "home")) != "follow":
                continue
            position = self.travel_follower_position(follower_id)
            if (
                str(record.get("location", "")) != str(self.state.location)
                or position is None
                or manhattan_distance(
                    position,
                    (int(self.state.player_x), int(self.state.player_y)),
                ) > 10
            ):
                self.recover_travel_follower(follower_id)
            if (
                str(record.get("mode", "")) == "follow"
                and str(record.get("location", "")) == str(self.state.location)
            ):
                self.record_travel_follower_outing(follower_id)

    def update_travel_followers_after_player_move(self) -> None:
        self.sync_travel_followers()
        player = (int(self.state.player_x), int(self.state.player_y))
        for follower_id in self.active_travel_follower_ids():
            record = self.travel_follower_record(follower_id)
            if str(record.get("mode", "home")) != "follow":
                continue
            position = self.travel_follower_position(follower_id)
            if position is None:
                continue
            distance = manhattan_distance(position, player)
            preferred = self.travel_follower_formation_target(follower_id)
            if position == preferred:
                record["activity"] = f"holding the {self.travel_follower_formation_label(follower_id).lower()}"
                continue
            if self.travel_follower_tile_available(follower_id, *preferred):
                goals = [preferred]
            else:
                goals = []
                for dx, dy in CARDINAL_STEPS:
                    goal = (player[0] + dx, player[1] + dy)
                    if self.travel_follower_tile_available(follower_id, *goal):
                        goals.append(goal)
            if distance <= 1 and not goals:
                record["activity"] = "keeping pace beside you"
                continue
            step = shortest_path_step(
                position,
                goals,
                lambda x, y: self.travel_follower_tile_available(follower_id, x, y),
                max_nodes=max(512, self.active_map_width() * self.active_map_height()),
            )
            if step:
                record["x"], record["y"] = int(step[0]), int(step[1])
                record["activity"] = "following you"
            elif distance > 6:
                self.recover_travel_follower(follower_id)
            else:
                record["activity"] = "finding a path to you"

    def regroup_travel_followers(self) -> bool:
        active = self.active_travel_follower_ids()
        if not active:
            self.set_message("No followers are currently in your traveling group.")
            return False
        for follower_id in active:
            record = self.travel_follower_record(follower_id)
            record["mode"] = "follow"
            record["task"] = ""
        self.reform_travel_follower_formation()
        available = sum(
            1
            for follower_id in active
            if self.travel_follower_position(follower_id) is not None
        )
        if available == len(active):
            message = f"Your traveling group reforms around you ({available}/{len(active)} ready)."
        else:
            message = (
                f"Your group reforms where it is safe ({available}/{len(active)} nearby; "
                "others are waiting safely at home)."
            )
        self.autosave_with_message(message)
        return True

    def send_all_travel_followers_home(self) -> bool:
        active = self.active_travel_follower_ids()
        if not active:
            self.set_message("No followers are currently in your traveling group.")
            return False
        for follower_id in active:
            record = self.travel_follower_record(follower_id)
            record.update({
                "location": "Home",
                "x": -1,
                "y": -1,
                "mode": "home",
                "activity": "at home",
                "task": "",
            })
        self.state.travel_follower_ids = []
        self.autosave_with_message(f"Your traveling group returned home ({len(active)} followers).")
        return True

    def set_travel_follower(self, follower_id: str) -> bool:
        follower_id = str(follower_id)
        if not self.travel_follower_is_eligible(follower_id):
            self.set_message("That person is not available to accompany you.")
            return False
        if not self.travel_follower_can_enter_location(follower_id):
            data = self.travel_follower_data(follower_id)
            self.set_message(f"{data.get('name', 'They')} cannot safely accompany you here.")
            return False
        active = self.active_travel_follower_ids()
        if follower_id not in active:
            if len(active) >= int(self.state.max_travel_followers):
                self.set_message("Your traveling group is full. Send someone home before inviting another follower.")
                return False
            active.append(follower_id)
            self.state.travel_follower_ids = active
        record = self.travel_follower_record(follower_id)
        record["mode"] = "follow"
        record["task"] = ""
        self.recover_travel_follower(follower_id)
        data = self.travel_follower_data(follower_id)
        self.autosave_with_message(
            f"{data.get('name', follower_id)} joined your traveling group "
            f"({len(self.active_travel_follower_ids())}/{self.state.max_travel_followers})."
        )
        return True

    def set_travel_follower_mode(self, follower_id: str, mode: str) -> bool:
        follower_id = str(follower_id)
        mode = str(mode or "").lower()
        if follower_id not in self.active_travel_follower_ids():
            self.set_message("That follower is not currently traveling with you.")
            return False
        record = self.travel_follower_record(follower_id)
        data = self.travel_follower_data(follower_id)
        name = str(data.get("name", follower_id))
        if mode == "follow":
            if not self.travel_follower_can_enter_location(follower_id):
                self.set_message(f"{name} cannot safely accompany you here.")
                return False
            record["mode"] = "follow"
            record["task"] = ""
            self.recover_travel_follower(follower_id)
            self.autosave_with_message(f"{name} will follow you.")
            return True
        if mode == "wait":
            record["mode"] = "wait"
            record["task"] = ""
            record["activity"] = "waiting here"
            self.autosave_with_message(f"{name} will wait here.")
            return True
        if mode == "home":
            record.update({
                "location": "Home",
                "x": -1,
                "y": -1,
                "mode": "home",
                "activity": "at home",
                "task": "",
            })
            self.state.travel_follower_ids = [
                current_id
                for current_id in self.state.travel_follower_ids
                if current_id != follower_id
            ]
            self.reform_travel_follower_formation()
            self.autosave_with_message(f"{name} returned home.")
            return True
        self.set_message("Unknown follower mode.")
        return False

    def pet_single_farm_animal(self, animal: Dict[str, object]) -> bool:
        if animal.get("petted_today"):
            self.set_message(f"{animal.get('name', 'The animal')} has already had plenty of attention today.")
            return False
        trait = str(animal.get("trait", "Gentle"))
        animal["petted_today"] = True
        animal["happiness"] = min(100, int(animal.get("happiness", 50)) + (8 if trait in ["Gentle", "Playful"] else 5))
        animal["affection"] = min(100, int(animal.get("affection", 0)) + (6 if trait in ["Gentle", "Curious", "Playful"] else 3))
        animal["activity"] = "enjoying your attention"
        self.autosave_with_message(f"Pet {animal.get('name')} the {animal.get('species')}.")
        return True

    def interact_with_farm_animal(self, animal: Dict[str, object]):
        self.single_farm_animal_menu(animal)
