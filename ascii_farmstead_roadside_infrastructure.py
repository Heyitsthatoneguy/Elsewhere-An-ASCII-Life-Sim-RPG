"""Large physical compounds for legacy wilderness roadside structures.

The old wilderness-structure API and type IDs remain save-compatible.  This
module replaces their tiny exterior facade with a road-connected property:
two enterable buildings, a working yard, storage, water, and type-specific
facilities that can be used directly in the world.
"""

from __future__ import annotations

import random
from typing import Dict, List, Mapping, Optional, Tuple

from ascii_farmstead_data import CROP_DATA, LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH
from ascii_farmstead_inventory import add_inventory_items
from ascii_farmstead_procedural_interiors import build_procedural_ground_floor


ROADSIDE_COMPOUND_VERSION = 5
ROADSIDE_AUX_LOCATION = "RoadsideAuxInterior"
ROADSIDE_AUX_DOOR = "d"
ROADSIDE_MAIN_DOOR = "h"


ROADSIDE_COMPOUND_TYPES: Dict[str, Dict[str, object]] = {
    "abandoned_cabin": {
        "main_size": (19, 9), "aux": ("woodshed", "Working Woodshed", "workshop", (15, 7)),
        "yard": "woodlot", "work": "Carpentry Bench", "worker": "Caretaker",
    },
    "watchtower": {
        "main_size": (13, 11), "aux": ("lookout_barracks", "Lookout Barracks", "sheriff_office", (17, 9)),
        "yard": "survey", "work": "Survey Table", "worker": "Lookout",
    },
    "wayside_shrine": {
        "main_size": (19, 9), "aux": ("route_office", "Route Office", "library", (15, 7)),
        "yard": "traveler_rest", "work": "Route Repair Bench", "worker": "Waykeeper",
    },
    "research_hut": {
        "main_size": (19, 9), "aux": ("map_archive", "Field Map Archive", "library", (17, 7)),
        "yard": "survey", "work": "Cartography Table", "worker": "Surveyor",
    },
    "hunting_lodge": {
        "main_size": (21, 9), "aux": ("smokehouse", "Lodge Smokehouse", "workshop", (15, 7)),
        "yard": "archery", "work": "Fletching Bench", "worker": "Trail Warden",
    },
    "roadside_inn": {
        "main_size": (23, 11), "aux": ("stable", "Roadside Stable", "animal_store", (17, 9)),
        "yard": "stable", "work": "Wagon Repair Bench", "worker": "Innkeeper",
    },
    "desert_caravanserai": {
        "main_size": (23, 11), "aux": ("caravan_stable", "Caravan Stable", "animal_store", (19, 9)),
        "yard": "caravan", "work": "Caravan Repair Bench", "worker": "Desert Host",
    },
    "tundra_wayhouse": {
        "main_size": (23, 11), "aux": ("fuel_house", "Fuel and Sled House", "workshop", (17, 9)),
        "yard": "winter", "work": "Sled Repair Bench", "worker": "Winter Keeper",
    },
    "coastal_ferry_house": {
        "main_size": (21, 9), "aux": ("boat_house", "Ferry Boat House", "workshop", (19, 9)),
        "yard": "boatyard", "work": "Boat Repair Bench", "worker": "Ferry Keeper",
    },
}


class RoadsideInfrastructureMixin:
    """Physical compound generation and interaction for roadside services."""

    @staticmethod
    def _roadside_feature(
        features: List[Dict[str, object]], x: int, y: int,
        kind: str, name: str, glyph: str, **extra: object,
    ) -> None:
        features.append({
            "x": int(x), "y": int(y), "kind": str(kind),
            "name": str(name), "glyph": str(glyph)[:1], **extra,
        })

    @staticmethod
    def _roadside_disruption_score(
        grid: List[List[str]], left: int, top: int, width: int, height: int,
    ) -> int:
        weights = {
            "~": 12, "=": 6, ":": 3, "#": 4, "S": 100, "X": 100,
            "!": 100, "A": 70, "E": 70, "h": 40, "j": 40, "k": 40,
            "q": 40, "R": 50, "J": 50, "P": 50, "K": 50, "Q": 50,
            "Y": 50, "G": 50, "Z": 50,
        }
        return sum(
            weights.get(grid[y][x], 0)
            for y in range(top, top + height)
            for x in range(left, left + width)
        )

    def place_roadside_infrastructure_compound(
        self, grid: List[List[str]], chunk_x: int, chunk_y: int,
    ) -> bool:
        if not self.wilderness_chunk_has_structure(chunk_x, chunk_y):
            return False
        if self.procedural_town_plan(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return False
        record = self.wilderness_structure_record(chunk_x, chunk_y)
        repaired = bool(record.get("repaired", False))
        if (
            int(record.get("compound_version", 0)) >= ROADSIDE_COMPOUND_VERSION
            and bool(record.get("compound_repaired", False)) == repaired
            and record.get("compound_parcel")
            and record.get("compound_main_door")
            and record.get("compound_aux_door")
        ):
            doors = (record["compound_main_door"], record["compound_aux_door"])
            expected = (ROADSIDE_MAIN_DOOR, ROADSIDE_AUX_DOOR)
            if all(
                0 <= int(door["y"]) < len(grid)
                and 0 <= int(door["x"]) < len(grid[0])
                and grid[int(door["y"])][int(door["x"])] == marker
                for door, marker in zip(doors, expected)
            ):
                return True

        type_id = str(record.get("type_id", "abandoned_cabin"))
        profile = ROADSIDE_COMPOUND_TYPES.get(type_id, ROADSIDE_COMPOUND_TYPES["abandoned_cabin"])
        width, height = (56, 25) if type_id in {"roadside_inn", "desert_caravanserai", "tundra_wayhouse"} else (50, 23)
        saved_parcel = list(record.get("compound_parcel", ()) or ())
        if len(saved_parcel) == 4:
            left, top, saved_right, saved_bottom = map(int, saved_parcel)
            width, height = saved_right - left + 1, saved_bottom - top + 1
        else:
            positions = [
                (left, top)
                for top in range(3, len(grid) - height - 2)
                for left in range(4, len(grid[0]) - width - 3)
            ]
            if not positions:
                return False
            scored = [
                (self._roadside_disruption_score(grid, left, top, width, height), left, top)
                for left, top in positions
            ]
            best = min(score for score, _left, _top in scored)
            candidates = [(left, top) for score, left, top in scored if score <= best + max(8, best // 20)]
            rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 68110)
            left, top = candidates[rng.randrange(len(candidates))]
        right, bottom = left + width - 1, top + height - 1
        original_roads = [
            (x, y) for y, row in enumerate(grid) for x, tile in enumerate(row)
            if tile in {":", "="}
        ]
        road_targets = [
            (x, y) for y, row in enumerate(grid) for x, tile in enumerate(row)
            if tile in {":", "="} and not (left <= x <= right and top <= y <= bottom)
        ]
        ground = self.wilderness_world_biome_tile(
            *self.wilderness_world_coords(chunk_x, chunk_y, left + width // 2, top + height // 2)
        )
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                grid[y][x] = ground
        for x in range(left, right + 1):
            grid[top][x] = grid[bottom][x] = "#"
        for y in range(top, bottom + 1):
            grid[y][left] = grid[y][right] = "#"

        gate_x = left + width // 2
        for x in range(gate_x - 1, gate_x + 2):
            grid[bottom][x] = "|"
        for y in range(top + 1, bottom):
            grid[y][gate_x] = ":"
        approach_y = min(len(grid) - 1, bottom + 1)
        grid[approach_y][gate_x] = ":"
        if not self.connect_wilderness_site_to_regional_road(grid, (gate_x, approach_y), road_targets):
            for y in range(approach_y, len(grid)):
                grid[y][gate_x] = "="

        main_center = (left + 14, top + 6)
        aux_center = (right - 11, top + 6)
        main_x, main_y, main_out_x, main_out_y = self.stamp_wilderness_building_exterior(
            grid, main_center, tuple(profile["main_size"]), "south", ROADSIDE_MAIN_DOOR, ground,
        )
        aux_id, aux_name, aux_type, aux_size = tuple(profile["aux"])
        aux_x, aux_y, aux_out_x, aux_out_y = self.stamp_wilderness_building_exterior(
            grid, aux_center, tuple(aux_size), "south", ROADSIDE_AUX_DOOR, ground,
        )
        mid_y = max(main_out_y, aux_out_y) + 2
        for outside_x, outside_y in ((main_out_x, main_out_y), (aux_out_x, aux_out_y)):
            for y in range(outside_y, mid_y + 1):
                grid[y][outside_x] = ":"
            lo, hi = sorted((outside_x, gate_x))
            for x in range(lo, hi + 1):
                grid[mid_y][x] = ":"

        features: List[Dict[str, object]] = []
        self._roadside_feature(features, gate_x - 3, bottom - 1, "directory", str(record.get("name", "Roadside Site")), "n")
        self._roadside_feature(features, gate_x + 4, mid_y - 1, "well", "Working Water Point", "O")
        self._roadside_feature(features, left + 3, mid_y, "container", "Roadside Supply Locker", "s", profile="crate")
        self._roadside_feature(features, right - 3, mid_y, "workbench", str(profile["work"]), "w")
        yard_left, yard_top = left + 3, mid_y + 2
        yard_right, yard_bottom = right - 3, bottom - 2
        for x in range(yard_left, yard_right + 1):
            grid[yard_top][x] = grid[yard_bottom][x] = "#"
        for y in range(yard_top, yard_bottom + 1):
            grid[y][yard_left] = grid[y][yard_right] = "#"
        grid[yard_top][gate_x] = "|"
        yard = str(profile.get("yard", "woodlot"))
        if yard == "woodlot":
            for x in range(yard_left + 3, yard_right - 1, 6):
                self._roadside_feature(features, x, yard_top + 2, "material", "Split Wood Stack", "≡", item="Wood")
        elif yard in {"stable", "caravan"}:
            self._roadside_feature(features, yard_left + 3, yard_top + 2, "trough", "Stable Water Trough", "t")
            self._roadside_feature(features, yard_left + 8, yard_top + 2, "animal", "Road Horse", "H")
            self._roadside_feature(features, yard_right - 6, yard_top + 2, "wagon", "Service Wagon", "W")
        elif yard == "archery":
            for x in range(yard_left + 5, yard_right - 2, 10):
                self._roadside_feature(features, x, yard_top + 2, "target", "Practice Target", "◎")
        elif yard == "survey":
            for x in range(yard_left + 5, yard_right - 2, 11):
                self._roadside_feature(features, x, yard_top + 2, "survey_marker", "Survey Instrument", "⌖")
        elif yard == "traveler_rest":
            for x in (yard_left + 6, yard_right - 8):
                self._roadside_feature(features, x, yard_top + 2, "bench", "Sheltered Road Bench", "B")
        elif yard == "winter":
            self._roadside_feature(features, yard_left + 5, yard_top + 2, "material", "Dry Fuel Stack", "≡", item="Wood")
            self._roadside_feature(features, yard_right - 8, yard_top + 2, "sled", "Freight Sled", "W")
        elif yard == "boatyard":
            self._roadside_feature(features, yard_left + 5, yard_top + 2, "material", "Coiled Ferry Rope", "§", item="Fiber")
            self._roadside_feature(features, yard_right - 8, yard_top + 2, "boat", "Ferry Skiff on Blocks", "U")

        for feature in features:
            grid[int(feature["y"])][int(feature["x"])] = str(feature["glyph"])
        self.preserve_wilderness_roads_around_parcel(
            grid, (left, top, right, bottom), original_roads,
            (gate_x, approach_y),
        )
        record.update({
            "compound_version": ROADSIDE_COMPOUND_VERSION,
            "compound_repaired": repaired,
            "compound_parcel": [left, top, right, bottom],
            "compound_gate": [gate_x, bottom],
            "compound_main_door": {"x": main_x, "y": main_y, "outside_x": main_out_x, "outside_y": main_out_y},
            "compound_aux_door": {
                "x": aux_x, "y": aux_y, "outside_x": aux_out_x, "outside_y": aux_out_y,
                "building_id": aux_id, "name": aux_name, "interior_type": aux_type,
            },
            "compound_features": features,
        })
        return True

    def roadside_compound_feature_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness":
            return None
        if not self.wilderness_chunk_has_structure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((
            feature for feature in self.wilderness_structure_record().get("compound_features", ())
            if int(feature.get("x", -1)) == int(x) and int(feature.get("y", -1)) == int(y)
        ), None)

    def roadside_aux_door_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness":
            return None
        if not self.wilderness_chunk_has_structure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        door = self.wilderness_structure_record().get("compound_aux_door", {})
        return dict(door) if door and (int(door.get("x", -1)), int(door.get("y", -1))) == (int(x), int(y)) else None

    def enter_roadside_aux_building(self, door: Mapping[str, object]) -> bool:
        self.state.current_roadside_site_key = self.wilderness_chunk_key()
        self.state.current_roadside_building_id = str(door.get("building_id", "workshop"))
        self.state.roadside_interior_return_x = int(door.get("outside_x", door.get("x", 1)))
        self.state.roadside_interior_return_y = int(door.get("outside_y", door.get("y", 1)))
        self.state.location = ROADSIDE_AUX_LOCATION
        grid = self.roadside_aux_interior_map()
        self.state.player_x, self.state.player_y = self.wilderness_interior_entry_landing(grid, "south")
        self.state.facing = "UP"
        self.set_message(f"Entered {door.get('name', 'the roadside building')}.")
        return True

    def exit_roadside_aux_building(self) -> None:
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        self.state.player_x, self.state.player_y = self.nearest_active_passable_tile(
            int(self.state.roadside_interior_return_x), int(self.state.roadside_interior_return_y)
        )
        self.state.facing = "DOWN"
        self.set_message("Stepped back into the roadside compound.")

    def roadside_aux_building(self) -> Dict[str, object]:
        door = self.wilderness_structure_record().get("compound_aux_door", {})
        return dict(door) if isinstance(door, dict) else {}

    def roadside_aux_interior_map(self) -> List[List[str]]:
        building = self.roadside_aux_building()
        key = (str(self.state.current_roadside_site_key), str(building.get("building_id", "workshop")))
        cache = getattr(self, "_roadside_aux_map_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._roadside_aux_map_cache = cache
        if key in cache:
            return cache[key]
        seed = sum((i + 1) * ord(ch) for i, ch in enumerate(":".join(key)))
        rng = random.Random(seed)
        placements: List[Dict[str, object]] = []
        grid = build_procedural_ground_floor(
            str(building.get("interior_type", "workshop")), rng.randrange(4),
            rng.randrange(12), 1, program_variant=rng.randrange(3),
            furniture_placements=placements,
        )
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        for placement in placements:
            common = {field: placement.get(field) for field in ("name", "collection", "form", "room_id", "room_role", "rotation", "width", "height")}
            for cell in placement.get("cells", ()) or ():
                row = dict(common); row.update(cell)
                lookup[(int(cell.get("x", 0)), int(cell.get("y", 0)))] = row
        catalog = getattr(self, "_roadside_aux_catalog_cache", None)
        if not isinstance(catalog, dict):
            catalog = {}
            self._roadside_aux_catalog_cache = catalog
        catalog[key] = lookup
        cache[key] = grid
        return grid

    def roadside_aux_catalog_furniture_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != ROADSIDE_AUX_LOCATION:
            return None
        self.roadside_aux_interior_map()
        key = (str(self.state.current_roadside_site_key), str(self.state.current_roadside_building_id))
        return getattr(self, "_roadside_aux_catalog_cache", {}).get(key, {}).get((int(x), int(y)))

    def roadside_compound_container(self, feature: Mapping[str, object]) -> Dict[str, object]:
        key = f"roadside:{self.wilderness_chunk_key()}:{feature.get('x')},{feature.get('y')}"
        existing = self.state.world_containers.get(key)
        if isinstance(existing, dict):
            return existing
        return self.create_container_record(
            key, int(feature["x"]), int(feature["y"]), str(feature.get("profile", "crate")),
            name=str(feature.get("name", "Roadside Supplies")), take_policy="free",
            allow_deposit=False,
        )

    def roadside_work_target_keys(self) -> List[str]:
        record = self.wilderness_structure_record()
        type_id = str(record.get("type_id", "abandoned_cabin"))
        yard = str(ROADSIDE_COMPOUND_TYPES.get(type_id, ROADSIDE_COMPOUND_TYPES["abandoned_cabin"]).get("yard", "woodlot"))
        accepted = {
            "woodlot": {"material", "workbench"},
            "survey": {"survey_marker", "workbench"},
            "traveler_rest": {"bench", "workbench"},
            "archery": {"target", "workbench"},
            "stable": {"trough", "wagon", "workbench"},
            "caravan": {"trough", "wagon", "workbench"},
            "winter": {"material", "sled", "workbench"},
            "boatyard": {"material", "boat", "workbench"},
        }.get(yard, {"workbench"})
        return [
            f"{feature.get('x')},{feature.get('y')}"
            for feature in record.get("compound_features", ())
            if str(feature.get("kind", "")) in accepted
        ]

    def perform_wilderness_structure_work(self) -> bool:
        """Begin a job that is completed at the compound's physical fixtures."""
        record = self.wilderness_structure_record()
        if not record.get("repaired"):
            self.set_message("Restore and staff this property before taking on its work.")
            return False
        week = self.stronghold_cache_week_key()
        if record.get("activity_week") == week:
            self.set_message("This property's work is already complete for the week.")
            return False
        if record.get("physical_work_active") and record.get("physical_work_week") == week:
            remaining = len(
                set(self.roadside_work_target_keys())
                - set(record.get("physical_work_done", ()))
            )
            self.set_message(f"This assignment is already underway; {remaining} station(s) remain outside.")
            return False
        targets = self.roadside_work_target_keys()
        if not targets:
            self.set_message("This property has no accessible work fixtures.")
            return False
        if record.get("physical_work_week") != week:
            record["physical_work_week"] = week
            record["physical_work_done"] = []
        remaining = len(set(targets) - set(record.get("physical_work_done", ())))
        record["physical_work_active"] = True
        self.set_message(
            f"Work started at {record.get('name')}. Use the marked yard fixtures and repair bench; {remaining} station(s) remain."
        )
        return True

    def register_roadside_physical_work(self, feature: Mapping[str, object]) -> bool:
        record = self.wilderness_structure_record()
        week = self.stronghold_cache_week_key()
        if not record.get("physical_work_active") or record.get("physical_work_week") != week:
            return False
        key = f"{feature.get('x')},{feature.get('y')}"
        targets = set(self.roadside_work_target_keys())
        if key not in targets:
            return False
        done = set(str(value) for value in record.get("physical_work_done", ()))
        if key in done:
            return False
        if not self.spend_stamina(1):
            return True
        self.advance_time(5)
        done.add(key)
        record["physical_work_done"] = sorted(done)
        remaining = len(targets - done)
        if remaining:
            self.set_message(f"Completed this work station. {remaining} station(s) remain around the compound.")
            return True
        rewards = {
            "abandoned_cabin": ({"Fiber": 2, "Wood": 2}, 55),
            "watchtower": ({"Fiber": 1, "Field Snack": 1}, 75),
            "wayside_shrine": ({"Wild Herbs": 2, "Wildflower": 1}, 55),
            "research_hut": ({"Fiber": 2, "Stone": 1}, 90),
            "hunting_lodge": ({"Fiber": 2, "Field Snack": 2}, 70),
            "roadside_inn": ({"Field Snack": 2}, 90),
            "desert_caravanserai": ({"Clay": 2, "Wild Herbs": 1}, 100),
            "tundra_wayhouse": ({"Fiber": 2, "Winter Root": 1}, 100),
            "coastal_ferry_house": ({"Wood": 2, "Marsh Reed": 2}, 95),
        }
        drops, money = rewards.get(str(record.get("type_id")), ({"Field Snack": 1}, 50))
        add_inventory_items(self.state.inventory, drops)
        self.state.money += int(money)
        record["activity_week"] = week
        record["physical_work_active"] = False
        record["activities_completed"] = int(record.get("activities_completed", 0)) + 1
        self.add_wilderness_region_vitality(
            self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 2,
            f"worked at {record.get('name')}",
        )
        self.autosave_with_message(
            f"Finished the full property job: +{money}g and practical supplies."
        )
        return True

    def claim_wilderness_structure_service(self) -> bool:
        """Stock support in the physical locker instead of teleporting loot."""
        record = self.wilderness_structure_record()
        if not record.get("repaired"):
            self.set_message("Restore this property before requesting supplies.")
            return False
        week = self.stronghold_cache_week_key()
        if record.get("service_week") == week:
            self.set_message("This week's support is already in the roadside supply locker.")
            return False
        feature = next((
            row for row in record.get("compound_features", ())
            if str(row.get("kind", "")) == "container"
        ), None)
        if not feature:
            # Older saves and several background systems can repair a roadside
            # property before its exterior chunk has ever been rendered.  Build
            # (or migrate) that chunk now so support always has a real locker.
            chunk_x = int(self.state.wilderness_chunk_x)
            chunk_y = int(self.state.wilderness_chunk_y)
            grid = self.get_wilderness_chunk_map(chunk_x, chunk_y)
            self.place_roadside_infrastructure_compound(grid, chunk_x, chunk_y)
            record = self.wilderness_structure_record(chunk_x, chunk_y)
            feature = next((
                row for row in record.get("compound_features", ())
                if str(row.get("kind", "")) == "container"
            ), None)
        if not feature:
            self.set_message("The compound supply locker is not accessible.")
            return False
        drops = {
            "abandoned_cabin": {"Wood": 2, "Field Snack": 1},
            "watchtower": {"Field Snack": 1, "Fiber": 2},
            "wayside_shrine": {"Wild Herbs": 2},
            "research_hut": {"Regional Chart": 1},
            "hunting_lodge": {"Field Snack": 2, "Fiber": 1},
            "roadside_inn": {"Field Snack": 2},
            "desert_caravanserai": {"Field Snack": 2, "Clay": 2},
            "tundra_wayhouse": {"Field Snack": 2, "Fiber": 2, "Winter Root": 1},
            "coastal_ferry_house": {"Wood": 2, "Fiber": 2, "Marsh Reed": 1},
        }.get(str(record.get("type_id")), {"Field Snack": 1})
        locker = self.roadside_compound_container(feature)
        contents = locker.setdefault("contents", {})
        for item, qty in drops.items():
            contents[item] = int(contents.get(item, 0)) + int(qty)
        record["service_week"] = week
        prepared = (
            str(record.get("type_id")) in {"desert_caravanserai", "tundra_wayhouse"}
            and self.set_wilderness_climate_prepared(str(record.get("name", "the roadside station")))
        )
        self.add_wilderness_region_vitality(
            self.state.wilderness_chunk_x,
            self.state.wilderness_chunk_y,
            2,
            f"visited {record.get('name', 'a roadside station')}",
        )
        suffix = " The caretaker also prepared the local frontier route." if prepared else ""
        self.autosave_with_message(
            "The caretaker stocked this week's support in the physical supply locker outside."
            + suffix
        )
        return True

    def use_roadside_compound_feature(self, feature: Mapping[str, object]) -> bool:
        kind = str(feature.get("kind", ""))
        record = self.wilderness_structure_record()
        if self.register_roadside_physical_work(feature):
            return True
        if kind == "directory":
            aux = record.get("compound_aux_door", {})
            self.vertical_panel_view(str(record.get("name", "Roadside Site")), [
                str(record.get("name", "Roadside Site")).upper(), "",
                f"Status: {'restored and staffed' if record.get('repaired') else 'abandoned and repairable'}",
                "", "Physical facilities:", f"- {record.get('name')}",
                f"- {aux.get('name', 'Service building')}", "- Enclosed working yard",
                "- Water point, supply locker, and repair station",
            ], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return True
        if kind == "container":
            self.show_world_container(self.roadside_compound_container(feature)); return True
        if kind == "well":
            day = self.errand_day_key()
            if record.get("compound_well_day") == day:
                self.set_message("You already drew water here today."); return True
            restored = self.restore_stamina(10 if record.get("repaired") else 5)
            record["compound_well_day"] = day; self.advance_time(5)
            self.autosave_with_message(f"Drew water and recovered {restored} stamina."); return True
        if kind == "resident":
            npc = {
                "id": f"roadside:{self.wilderness_chunk_key()}:worker", "name": str(feature.get("name", "Caretaker")),
                "role": str(feature.get("name", "Caretaker")), "activity": f"working at {record.get('name')}",
                "origin": str(record.get("name", "this roadside property")),
                "bond": int(record.get("caretaker_bond", 0)), "conversations": int(record.get("caretaker_conversations", 0)),
            }
            result = self.run_unified_npc_conversation(npc, kind="roadside worker", first_meeting=npc["conversations"] <= 0)
            if result.get("completed") or result.get("transcript"):
                record["caretaker_conversations"] = npc["conversations"] + 1
            return True
        if kind == "workbench":
            self.safe_menu(self.show_crafting_menu, "Workbench closed."); return True
        if kind == "material":
            week = self.stronghold_cache_week_key(); key = f"{feature.get('x')},{feature.get('y')}"
            taken = record.setdefault("compound_material_week", {})
            if taken.get(key) == week:
                self.set_message("This working supply has already been collected this week."); return True
            item = str(feature.get("item", "Wood")); add_inventory_items(self.state.inventory, {item: 1})
            taken[key] = week; self.advance_time(4); self.autosave_with_message(f"Collected 1 {item} from the work yard."); return True
        if kind == "target":
            record["target_practice_count"] = int(record.get("target_practice_count", 0)) + 1
            self.advance_time(10); self.restore_stamina(2)
            self.set_message("You practice distance and timing across the full marked range."); return True
        if kind == "survey_marker":
            mapped = self.map_nearby_wilderness_chunks(1); self.advance_time(8)
            self.set_message(f"Used the survey instrument to chart {mapped} nearby area(s)."); return True
        if kind == "bench":
            restored = self.restore_stamina(6); self.advance_time(10)
            self.set_message(f"Rested beside the road. Stamina +{restored}."); return True
        if kind in {"trough", "animal", "wagon", "sled", "boat"}:
            self.set_message({
                "trough": "A maintained water trough serving animals and passing teams.",
                "animal": "A working road horse housed in the fenced stable yard.",
                "wagon": "A service wagon used for deliveries and roadside assistance.",
                "sled": "A freight sled ready for winter route work.",
                "boat": "A working ferry skiff raised for hull maintenance.",
            }[kind]); return True
        return False

    def roadside_compound_description_at(self, x: int, y: int) -> str:
        door = self.roadside_aux_door_at(x, y)
        if door:
            return f"Door to {door.get('name', 'the service building')}: walk into it to enter"
        feature = self.roadside_compound_feature_at(x, y)
        if feature:
            return f"{feature.get('name', 'Roadside facility')}: use Z/Enter"
        return ""

    def use_roadside_aux_action(self, x: int, y: int) -> bool:
        tile = self.active_map()[y][x]
        if tile == "D": self.exit_roadside_aux_building(); return True
        if tile == "_": self.active_map()[y][x] = "|"; self.set_message("Opened the room door."); return True
        if tile == "|": self.active_map()[y][x] = "_"; self.set_message("Closed the room door."); return True
        if self.use_catalog_furniture_action_at(x, y): return True
        self.set_message("Nothing here needs direct interaction."); return False


__all__ = [
    "ROADSIDE_AUX_DOOR", "ROADSIDE_AUX_LOCATION", "ROADSIDE_MAIN_DOOR", "ROADSIDE_COMPOUND_TYPES",
    "ROADSIDE_COMPOUND_VERSION", "RoadsideInfrastructureMixin",
]
