"""Substantial human infrastructure embedded in the seamless wilderness.

These sites are compounds rather than marker POIs.  A site occupies most of a
chunk, connects to a real regional road, contains several enterable buildings,
and exposes physical fields, pens, containers, wells, work areas, and residents.
"""

from __future__ import annotations

import random
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from ascii_farmstead_data import CROP_DATA, LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK
from ascii_farmstead_helpers import quantity_item_phrase
from ascii_farmstead_inventory import add_inventory_items, format_drops
from ascii_farmstead_procedural_interiors import build_procedural_ground_floor
from ascii_farmstead_ui import MenuItem


RURAL_INFRASTRUCTURE_VERSION = 6
RURAL_INFRASTRUCTURE_LOCATION = "RuralInfrastructureInterior"
RURAL_INFRASTRUCTURE_DOOR = "d"


RURAL_SITE_TYPES: Dict[str, Dict[str, object]] = {
    "family_farm": {
        "name": "Family Farmstead", "resident": "Farmer", "crop": "Potato",
        "land_use": "crop_field", "livestock": "Chicken",
        "buildings": (("farmhouse", "Farmhouse", "home", (19, 9)), ("barn", "Working Barn", "animal_store", (17, 9))),
        "description": "A working family holding with crop strips, a barnyard, storage, and a farmhouse.",
    },
    "cattle_ranch": {
        "name": "Open-Range Ranch", "resident": "Rancher", "crop": "Corn",
        "land_use": "feed_field", "livestock": "Cattle",
        "buildings": (("ranch_house", "Ranch House", "home", (19, 9)), ("stable", "Ranch Stable", "animal_store", (19, 9))),
        "description": "A fenced ranch parcel with broad pens, a stable, feed stores, and a family residence.",
    },
    "orchard_homestead": {
        "name": "Orchard Homestead", "resident": "Orchardist", "crop": "Wild Apple",
        "land_use": "orchard", "livestock": "Goat",
        "buildings": (("orchard_house", "Orchard House", "home", (19, 9)), ("packing_shed", "Packing Shed", "workshop", (15, 7))),
        "description": "An orchard property arranged around fruit rows, a packing shed, well, and home.",
    },
    "lumber_camp": {
        "name": "Woodland Lumber Camp", "resident": "Forester", "crop": "Wood",
        "land_use": "timber_yard", "livestock": "Mule",
        "buildings": (("bunkhouse", "Logging Bunkhouse", "inn", (19, 9)), ("sawmill", "Sawmill Workshop", "workshop", (19, 9))),
        "description": "A practical woodland camp with a bunkhouse, sawmill floor, stacked timber, and firebreak lanes.",
    },
    "frontier_homestead": {
        "name": "Frontier Homestead", "resident": "Homesteader", "crop": "Turnip",
        "land_use": "crop_field", "livestock": "Goat",
        "buildings": (("homestead", "Homestead House", "home", (19, 9)), ("work_shed", "Utility Shed", "workshop", (13, 7))),
        "description": "A self-reliant household enclosed by a modest fence, kitchen plot, shed, and animal pen.",
    },
    "roadside_market": {
        "name": "Crossroads Market", "resident": "Shopkeeper", "crop": "Carrot",
        "land_use": "market_garden", "livestock": "Horse",
        "buildings": (("market_house", "Market House", "general_store", (21, 9)), ("storehouse", "Goods Storehouse", "workshop", (15, 7))),
        "description": "A roadside family business with a proper shop, storehouse, wagon yard, and produce garden.",
    },
    "fortified_manor": {
        "name": "Old Fortified Manor", "resident": "Steward", "crop": "Kale",
        "land_use": "kitchen_garden", "livestock": "Horse",
        "buildings": (("manor", "Fortified Manor", "home", (23, 11)), ("gatehouse", "Manor Gatehouse", "sheriff_office", (15, 9))),
        "description": "A surviving rural manor enclosed by stonework, with a gatehouse, kitchen garden, and working yard.",
    },
    "coastal_smallholding": {
        "name": "Coastal Smallholding", "resident": "Fisher-Farmer", "crop": "Cabbage",
        "land_use": "coastal_garden", "livestock": "Goat",
        "buildings": (("coastal_house", "Coastal House", "home", (19, 9)), ("net_shed", "Net and Boat Shed", "workshop", (17, 7))),
        "description": "A windbreak-fenced coastal holding with garden rows, drying racks, boat stores, and a family home.",
    },
}


RURAL_RESIDENT_NAMES = (
    "Alden Mercer", "Briar Sutton", "Clara Whitlock", "Dorian Hale",
    "Eliza Marlow", "Felix Warren", "Greta Calder", "Hugh Bellamy",
    "Iris Fenwick", "Jonas Pike", "Mara Ellison", "Nolan Avery",
)


class RuralInfrastructureMixin:
    """Generation, persistence, interiors, and physical use of rural sites."""

    def rural_region_site_chunk(self, chunk_x: int, chunk_y: int) -> Tuple[int, int]:
        rx, ry = self.wilderness_region_coords(chunk_x, chunk_y)
        settlement_keys = tuple(sorted(str(key) for key in (getattr(self.state, "wilderness_settlements", {}) or {})))
        claim_keys = tuple(sorted(str(key) for key in (getattr(self.state, "owned_wilderness_claims", {}) or {})))
        road_signature = self.wilderness_road_state_signature() if hasattr(self, "wilderness_road_state_signature") else ()
        cache_key = (
            int(getattr(self.state, "wilderness_seed", 0)),
            int(getattr(self.state, "wilderness_generation_version", 0) or 0),
            int(rx), int(ry), settlement_keys, claim_keys, road_signature,
        )
        cache = getattr(self, "_rural_region_site_chunk_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._rural_region_site_chunk_cache = cache
        if cache_key in cache:
            return tuple(cache[cache_key])
        candidates = []
        structure_chunk = self.wilderness_region_structure_chunk(chunk_x, chunk_y)
        outpost_chunk = self.wilderness_region_outpost_chunk(chunk_x, chunk_y)
        for cx, cy in self.wilderness_region_chunks(chunk_x, chunk_y):
            point = (int(cx), int(cy))
            if point in {tuple(structure_chunk), tuple(outpost_chunk)}:
                continue
            if self.home_world_chunk_is_authored(cx, cy):
                continue
            if self.procedural_town_plan(cx, cy) or self.wilderness_chunk_has_stronghold(cx, cy):
                continue
            if self.wilderness_chunk_has_dungeon_site(cx, cy):
                continue
            if self.is_claimable_wilderness_chunk(cx, cy) or self.owned_wilderness_claim(cx, cy):
                continue
            candidates.append(point)
        if not candidates:
            cache[cache_key] = (10**8, 10**8)
            return (10**8, 10**8)
        rng = random.Random(self.wilderness_chunk_seed(rx, ry) + 47621)
        result = candidates[rng.randrange(len(candidates))]
        cache[cache_key] = result
        return result

    def wilderness_chunk_has_rural_infrastructure(self, chunk_x: int, chunk_y: int) -> bool:
        return (int(chunk_x), int(chunk_y)) == self.rural_region_site_chunk(chunk_x, chunk_y)

    def rural_site_type(self, chunk_x: int, chunk_y: int) -> str:
        biome_id = str(self.wilderness_region_profile(chunk_x, chunk_y).get("biome_id", ""))
        biome_tile = str(self.wilderness_region_profile(chunk_x, chunk_y).get("biome", ";"))
        if biome_id in {"tidal_flat", "mangrove", "tropical_isle"} or biome_tile == "[":
            return "coastal_smallholding"
        if biome_id in {"pine_forest", "old_growth", "birch_grove"}:
            return "lumber_camp" if biome_id != "birch_grove" else "orchard_homestead"
        if biome_id in {"prairie", "scrubland", "badlands"}:
            return "cattle_ranch"
        if biome_id in {"rocky_valley", "alpine_meadow"}:
            return "fortified_manor"
        if biome_id in {"moorland", "taiga", "glacier", "dune_desert"}:
            return "frontier_homestead"
        choices = ("family_farm", "frontier_homestead", "roadside_market", "orchard_homestead")
        return choices[int(self.wilderness_hash01(chunk_x, chunk_y, 47622) * len(choices)) % len(choices)]

    def rural_site_record(self, chunk_x: Optional[int] = None, chunk_y: Optional[int] = None) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        self.ensure_wilderness_poi_state()
        key = f"rural:{cx},{cy}"
        type_id = self.rural_site_type(cx, cy)
        profile = RURAL_SITE_TYPES[type_id]
        record = self.state.wilderness_poi_state.setdefault(key, {})
        record.setdefault("kind", "rural_infrastructure")
        record.setdefault("type_id", type_id)
        record.setdefault("name", profile["name"])
        name_index = int(self.wilderness_hash01(cx, cy, 47623) * len(RURAL_RESIDENT_NAMES)) % len(RURAL_RESIDENT_NAMES)
        record.setdefault("resident_name", RURAL_RESIDENT_NAMES[name_index])
        record.setdefault("resident_role", profile["resident"])
        record.setdefault("version", 0)
        return record

    @staticmethod
    def _rural_rect_clear(grid: List[List[str]], left: int, top: int, width: int, height: int) -> bool:
        protected = {
            "~", "=", "S", "V", "X", "!", "A", "E", "h", "j", "k", "q",
            "?", "R", "J", "P", "K", "Q", "Y", "G", "Z",
        }
        if top < 2 or left < 2 or top + height >= len(grid) - 2 or left + width >= len(grid[0]) - 2:
            return False
        return not any(
            grid[y][x] in protected
            for y in range(top, top + height)
            for x in range(left, left + width)
        )

    @staticmethod
    def _rural_rect_disruption_score(
        grid: List[List[str]], left: int, top: int, width: int, height: int,
    ) -> int:
        """Prefer open land while still guaranteeing a designated holding exists."""
        weights = {
            "~": 12, "=": 8, ":": 5, "#": 5,
            "S": 80, "X": 100, "!": 100, "A": 60, "E": 60,
            "h": 35, "j": 35, "k": 35, "q": 35, "?": 30,
            "R": 40, "J": 40, "P": 40, "K": 40, "Q": 40,
            "Y": 40, "G": 40, "Z": 40, "V": 30,
        }
        return sum(
            weights.get(grid[y][x], 0)
            for y in range(top, top + height)
            for x in range(left, left + width)
        )

    @staticmethod
    def _rural_feature(features: List[Dict[str, object]], x: int, y: int, kind: str, name: str, glyph: str, **extra: object) -> None:
        features.append({"x": int(x), "y": int(y), "kind": str(kind), "name": str(name), "glyph": str(glyph)[:1], **extra})

    def place_rural_infrastructure(self, grid: List[List[str]], chunk_x: int, chunk_y: int) -> bool:
        if not self.wilderness_chunk_has_rural_infrastructure(chunk_x, chunk_y):
            return False
        if self.procedural_town_plan(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return False
        record = self.rural_site_record(chunk_x, chunk_y)
        saved_doors = list(record.get("doors", ()) or ())
        if (
            int(record.get("version", 0)) >= RURAL_INFRASTRUCTURE_VERSION
            and saved_doors
            and all(
                0 <= int(door.get("y", -1)) < len(grid)
                and 0 <= int(door.get("x", -1)) < len(grid[0])
                and grid[int(door["y"])][int(door["x"])] == RURAL_INFRASTRUCTURE_DOOR
                for door in saved_doors
            )
        ):
            return True
        road_targets = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile in {":", "="}]
        width, height = 62, 28
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 47624)
        candidates = [
            (left, top)
            for top in range(3, len(grid) - height - 2)
            for left in range(4, len(grid[0]) - width - 3)
            if self._rural_rect_clear(grid, left, top, width, height)
        ]
        if not candidates:
            width, height = 54, 24
            candidates = [
                (left, top)
                for top in range(3, len(grid) - height - 2)
                for left in range(4, len(grid[0]) - width - 3)
                if self._rural_rect_clear(grid, left, top, width, height)
            ]
        if not candidates:
            # Some biomes are too wet or landmark-heavy for a perfectly clear
            # parcel.  A designated site must still be physically present, so
            # choose the least disruptive viable parcel instead of silently
            # degrading into no infrastructure at all.
            width, height = 50, 23
            scored = [
                (self._rural_rect_disruption_score(grid, left, top, width, height), left, top)
                for top in range(3, len(grid) - height - 2)
                for left in range(4, len(grid[0]) - width - 3)
            ]
            if not scored:
                return False
            best_score = min(score for score, _left, _top in scored)
            candidates = [
                (left, top) for score, left, top in scored
                if score <= best_score + max(8, best_score // 20)
            ]
        left, top = candidates[rng.randrange(len(candidates))]
        right, bottom = left + width - 1, top + height - 1
        ground = self.wilderness_world_biome_tile(*self.wilderness_world_coords(chunk_x, chunk_y, left + width // 2, top + height // 2))

        # Clear the parcel deliberately; open ground is part of the composition.
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
        outside_roads = [
            (x, y) for x, y in road_targets
            if not (left <= x <= right and top <= y <= bottom)
        ]
        approach_y = min(len(grid) - 1, bottom + 1)
        grid[approach_y][gate_x] = ":"
        connected = self.connect_wilderness_site_to_regional_road(
            grid, (gate_x, approach_y), outside_roads,
        )
        if not connected:
            # A few remote chunks have no surviving regional-road tile outside
            # the large parcel.  Continue the frontage lane to the nearest map
            # edge so the property remains physically approached in the
            # seamless world rather than ending in scrub.
            distances = {
                "south": len(grid) - 1 - approach_y,
                "west": gate_x,
                "east": len(grid[0]) - 1 - gate_x,
            }
            side = min(distances, key=distances.get)
            if side == "south":
                for y in range(approach_y, len(grid)):
                    grid[y][gate_x] = "="
            else:
                target_x = 0 if side == "west" else len(grid[0]) - 1
                step = -1 if side == "west" else 1
                for x in range(gate_x, target_x + step, step):
                    grid[approach_y][x] = "="

        profile = RURAL_SITE_TYPES[str(record["type_id"])]
        doors: List[Dict[str, object]] = []
        building_specs = tuple(profile.get("buildings", ()))
        centers = ((left + 14, top + 6), (right - 13, top + 6))
        for index, spec in enumerate(building_specs[:2]):
            building_id, building_name, interior_type, size = spec
            door_x, door_y, outside_x, outside_y = self.stamp_wilderness_building_exterior(
                grid, centers[index], tuple(size), "south", RURAL_INFRASTRUCTURE_DOOR, ground
            )
            doors.append({
                "x": door_x, "y": door_y, "outside_x": outside_x, "outside_y": outside_y,
                "building_id": building_id, "name": building_name, "interior_type": interior_type,
            })
            for y in range(outside_y, min(bottom, top + height // 2 + 2) + 1):
                grid[y][outside_x] = ":"

        features: List[Dict[str, object]] = []
        self._rural_feature(features, gate_x - 3, bottom - 1, "directory", str(record["name"]), "n")
        self._rural_feature(features, gate_x + 4, top + height // 2, "well", "Stone Well", "O")
        self._rural_feature(features, left + 3, top + height // 2, "container", "Shared Supply Crate", "s", profile="crate")
        self._rural_feature(features, right - 3, top + height // 2, "workbench", "Outdoor Workbench", "w")
        self._rural_feature(features, gate_x + 2, top + height // 2 - 1, "resident", str(record["resident_name"]), "@", role=str(record["resident_role"]))

        # The western enclosure reflects the work actually performed here.
        field_left, field_top = left + 3, top + height // 2 + 3
        field_right, field_bottom = gate_x - 4, bottom - 3
        for x in range(field_left, field_right + 1):
            grid[field_top][x] = grid[field_bottom][x] = "#"
        for y in range(field_top, field_bottom + 1):
            grid[y][field_left] = grid[y][field_right] = "#"
        grid[(field_top + field_bottom) // 2][field_right] = "|"
        crop_name = str(profile.get("crop", "Turnip"))
        land_use = str(profile.get("land_use", "crop_field"))
        for y in range(field_top + 2, field_bottom, 2):
            for x in range(field_left + 2, field_right - 1, 3):
                if land_use == "orchard":
                    self._rural_feature(features, x, y, "orchard_tree", "Fruit Tree", "♣", item=crop_name)
                elif land_use == "timber_yard":
                    self._rural_feature(features, x, y, "timber_stack", "Seasoned Timber Stack", "≡", item="Wood")
                else:
                    self._rural_feature(features, x, y, "crop", crop_name, ";", item=crop_name)
        if land_use == "market_garden":
            self._rural_feature(features, field_left + 2, field_top - 2, "market_stall", "Roadside Produce Stall", "m")
        elif land_use == "coastal_garden":
            self._rural_feature(features, field_left + 2, field_top - 2, "drying_rack", "Fish Drying Rack", "≡", item="Fish")

        # The opposite side is a real yard/pen with gates, trough, and livestock.
        pen_left, pen_top = gate_x + 4, top + height // 2 + 3
        pen_right, pen_bottom = right - 3, bottom - 3
        for x in range(pen_left, pen_right + 1):
            grid[pen_top][x] = grid[pen_bottom][x] = "#"
        for y in range(pen_top, pen_bottom + 1):
            grid[y][pen_left] = grid[y][pen_right] = "#"
        grid[(pen_top + pen_bottom) // 2][pen_left] = "|"
        self._rural_feature(features, pen_left + 2, pen_top + 2, "trough", "Water Trough", "t")
        species = str(profile.get("livestock", "Goat"))
        for index, (ax, ay) in enumerate(((pen_left + 5, pen_top + 2), (pen_right - 4, pen_bottom - 2))):
            animal_glyph = {"Cattle": "c", "Chicken": "h", "Horse": "H", "Mule": "M"}.get(species, "g")
            self._rural_feature(features, ax, ay, "livestock", f"{species} {index + 1}", animal_glyph, species=species)

        for feature in features:
            grid[int(feature["y"])][int(feature["x"])] = str(feature["glyph"])
        self.preserve_wilderness_roads_around_parcel(
            grid, (left, top, right, bottom), road_targets,
            (gate_x, approach_y),
        )
        record.update({
            "version": RURAL_INFRASTRUCTURE_VERSION,
            "parcel": [left, top, right, bottom], "gate": [gate_x, bottom],
            "doors": doors, "features": features,
        })
        return True

    def rural_site_feature_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness":
            return None
        if not self.wilderness_chunk_has_rural_infrastructure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        record = self.rural_site_record()
        return next((feature for feature in record.get("features", ()) if int(feature.get("x", -1)) == int(x) and int(feature.get("y", -1)) == int(y)), None)

    def rural_site_door_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness":
            return None
        if not self.wilderness_chunk_has_rural_infrastructure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        record = self.rural_site_record()
        return next((door for door in record.get("doors", ()) if int(door.get("x", -1)) == int(x) and int(door.get("y", -1)) == int(y)), None)

    def rural_site_zone_at(self, x: int, y: int) -> str:
        record = self.rural_site_record()
        parcel = record.get("parcel", ())
        if len(parcel) != 4:
            return ""
        left, top, right, bottom = map(int, parcel)
        if not (left <= int(x) <= right and top <= int(y) <= bottom):
            return ""
        gate_x = int(record.get("gate", [left + (right - left) // 2, bottom])[0])
        return "field" if x < gate_x and y > top + (bottom - top) // 2 else "animal yard" if x > gate_x and y > top + (bottom - top) // 2 else "farmyard"

    def enter_rural_site_building(self, door: Mapping[str, object]) -> bool:
        self.state.current_rural_site_key = f"{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}"
        self.state.current_rural_building_id = str(door.get("building_id", "farmhouse"))
        self.state.rural_interior_return_x = int(door.get("outside_x", door.get("x", 1)))
        self.state.rural_interior_return_y = int(door.get("outside_y", door.get("y", 1)))
        self.state.location = RURAL_INFRASTRUCTURE_LOCATION
        grid = self.rural_site_interior_map()
        self.state.player_x, self.state.player_y = self.wilderness_interior_entry_landing(grid, "south")
        self.state.facing = "UP"
        self.set_message(f"Entered {door.get('name', 'the rural building')}.")
        return True

    def exit_rural_site_building(self) -> None:
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        self.state.player_x, self.state.player_y = self.nearest_active_passable_tile(
            int(self.state.rural_interior_return_x), int(self.state.rural_interior_return_y)
        )
        self.state.facing = "DOWN"
        self.set_message("Stepped back into the rural compound.")

    def current_rural_building(self) -> Dict[str, object]:
        record = self.rural_site_record()
        building_id = str(getattr(self.state, "current_rural_building_id", ""))
        return next((dict(door) for door in record.get("doors", ()) if str(door.get("building_id")) == building_id), {})

    def rural_site_interior_map(self) -> List[List[str]]:
        site_key = str(getattr(self.state, "current_rural_site_key", self.wilderness_chunk_key()))
        building = self.current_rural_building()
        building_id = str(building.get("building_id", "farmhouse"))
        cache_key = (site_key, building_id)
        cache = getattr(self, "_rural_interior_map_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._rural_interior_map_cache = cache
        if cache_key in cache:
            return cache[cache_key]
        seed = sum((index + 1) * ord(ch) for index, ch in enumerate(f"{site_key}:{building_id}"))
        rng = random.Random(seed)
        placements: List[Dict[str, object]] = []
        grid = build_procedural_ground_floor(
            str(building.get("interior_type", "home")), rng.randrange(4), rng.randrange(12), 1,
            program_variant=rng.randrange(3), furniture_placements=placements,
        )
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        for placement in placements:
            common = {key: placement.get(key) for key in ("name", "collection", "form", "room_id", "room_role", "rotation", "width", "height")}
            for cell in placement.get("cells", ()) or ():
                cell_record = dict(common)
                cell_record.update(cell)
                lookup[(int(cell.get("x", 0)), int(cell.get("y", 0)))] = cell_record
        catalog = getattr(self, "_rural_interior_catalog_cache", None)
        if not isinstance(catalog, dict):
            catalog = {}
            self._rural_interior_catalog_cache = catalog
        catalog[cache_key] = lookup
        cache[cache_key] = grid
        return grid

    def rural_interior_catalog_furniture_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != RURAL_INFRASTRUCTURE_LOCATION:
            return None
        self.rural_site_interior_map()
        key = (str(self.state.current_rural_site_key), str(self.state.current_rural_building_id))
        return getattr(self, "_rural_interior_catalog_cache", {}).get(key, {}).get((int(x), int(y)))

    def rural_site_container(self, feature: Mapping[str, object]) -> Dict[str, object]:
        key = f"rural:{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}:{feature.get('x')},{feature.get('y')}:crate"
        existing = self.state.world_containers.get(key)
        if isinstance(existing, dict):
            return existing
        return self.create_container_record(
            key, int(feature["x"]), int(feature["y"]), str(feature.get("profile", "crate")),
            name=str(feature.get("name", "Supply Crate")), take_policy="owned",
            allow_deposit=False, owner=str(self.rural_site_record().get("resident_name", "the household")),
        )

    def rural_market_stall_menu(self, record: Optional[Mapping[str, object]] = None) -> None:
        """A real remote shop with stock, prices, quantities, and purchases."""
        record = record or self.rural_site_record()
        seasonal = [
            (name, data) for name, data in CROP_DATA.items()
            if str(data.get("season", "")) == str(self.state.season)
            and int(data.get("seed_price", 0)) > 0
        ]
        if not seasonal:
            seasonal = [
                (name, data) for name, data in CROP_DATA.items()
                if int(data.get("seed_price", 0)) > 0
            ][:4]
        seed = self.wilderness_chunk_seed(
            self.state.wilderness_chunk_x, self.state.wilderness_chunk_y
        ) + int(getattr(self.state, "day", 1)) * 37
        rng = random.Random(seed)
        rng.shuffle(seasonal)
        stock = []
        for name, data in seasonal[:5]:
            base_price = int(data.get("seed_price", 1))
            stock.append((f"{name} Seeds", max(1, int(round(base_price * 1.10))), "seed"))
        local_crop = str(RURAL_SITE_TYPES[str(record.get("type_id", "roadside_market"))].get("crop", "Carrot"))
        if local_crop in CROP_DATA:
            stock.append((local_crop, max(8, int(CROP_DATA[local_crop].get("sell_price", 40) * 0.75)), "produce"))
        stock.extend((("Potion", 105, "medicine"), ("Wood", 18, "material")))

        while True:
            entries = [
                MenuItem(
                    label=f"Buy {item}", value=(item, price),
                    enabled=int(self.state.money) >= price,
                    hint=f"${price} | {kind}",
                )
                for item, price, kind in stock
            ]
            entries.append(MenuItem(label="Leave the counter", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(
                str(record.get("name", "Roadside Market")), entries,
                LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                self.set_message("You step away from the staffed market counter.")
                return
            item, price = choice.value
            max_qty = int(self.state.money) // int(price)
            qty = self.vertical_quantity_select(
                "Roadside Purchase", str(item), int(price), max_qty=max_qty,
                start_qty=min(5, max_qty), panel_width=LEFT_PANEL_WIDTH,
                panel_height=LEFT_PANEL_HEIGHT, return_back=True,
            )
            if qty in {None, MENU_BACK} or int(qty) <= 0:
                continue
            qty = int(qty)
            total = qty * int(price)
            self.state.money -= total
            add_inventory_items(self.state.inventory, {str(item): qty})
            self.autosave_with_message(
                f"Bought {quantity_item_phrase(item, qty)} from {record.get('resident_name', 'the shopkeeper')} for ${total}."
            )
            return

    def use_rural_interior_service(self, tile: str) -> bool:
        building = self.current_rural_building()
        interior_type = str(building.get("interior_type", "home"))
        record = self.rural_site_record()
        if tile == "&":
            if interior_type == "general_store":
                self.rural_market_stall_menu(record)
                return True
            return self.use_rural_site_feature({
                "kind": "resident", "name": record.get("resident_name", "Resident"),
                "role": record.get("resident_role", "Resident"),
            })
        if tile == "$" and interior_type == "general_store":
            self.rural_market_stall_menu(record)
            return True
        if tile in {"$", "x", "w"} and interior_type == "workshop":
            self.safe_menu(self.show_crafting_menu, "Workshop closed.")
            return True
        if tile == "$" and interior_type == "animal_store":
            self.set_message("The barn counter holds feed records and care schedules; livestock are handled in the fenced yard outside.")
            return True
        if tile == "$" and interior_type == "inn":
            restored = self.restore_stamina(8)
            self.advance_time(20)
            self.autosave_with_message(f"Rested in the working bunkhouse. Stamina +{restored}.")
            return True
        if tile == "$" and interior_type == "sheriff_office":
            self.set_message("The gatehouse desk records travelers, property boundaries, and trouble reported along the road.")
            return True
        return False

    def use_rural_site_feature(self, feature: Mapping[str, object]) -> bool:
        kind = str(feature.get("kind", ""))
        record = self.rural_site_record()
        if kind == "directory":
            buildings = [str(door.get("name")) for door in record.get("doors", ())]
            self.vertical_panel_view(
                str(record.get("name", "Rural Holding")),
                [str(record.get("name", "Rural Holding")).upper(), "", str(RURAL_SITE_TYPES[str(record["type_id"])]["description"]), "", "Buildings:", *[f"- {name}" for name in buildings], "", "The gates, field rows, animal yard, well, containers, work areas, and both buildings are physically usable."],
                LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
            )
            return True
        if kind == "container":
            self.show_world_container(self.rural_site_container(feature))
            return True
        if kind == "well":
            day = self.errand_day_key()
            if record.get("well_day") == day:
                self.set_message("You already drew and drank clean water here today.")
                return True
            restored = self.restore_stamina(12)
            record["well_day"] = day
            self.advance_time(5)
            self.autosave_with_message(f"Drew water from the stone well and recovered {restored} stamina.")
            return True
        if kind in {"crop", "orchard_tree", "timber_stack", "drying_rack"}:
            week = self.stronghold_cache_week_key()
            harvested = record.setdefault("harvested_crop_tiles", {})
            tile_key = f"{feature.get('x')},{feature.get('y')}"
            if harvested.get(tile_key) == week:
                self.set_message("This plant has already been harvested this week.")
                return True
            item = str(feature.get("item", feature.get("name", "Turnip")))
            add_inventory_items(self.state.inventory, {item: 1})
            harvested[tile_key] = week
            self.advance_time(3)
            action = {
                "crop": "Harvested", "orchard_tree": "Picked",
                "timber_stack": "Collected", "drying_rack": "Took",
            }.get(kind, "Collected")
            self.autosave_with_message(f"{action} 1 {item} from the working property.")
            return True
        if kind == "market_stall":
            if hasattr(self, "rural_market_stall_menu"):
                self.rural_market_stall_menu(record)
            else:
                self.set_message("The produce stall is stocked and staffed from the nearby market house.")
            return True
        if kind == "resident":
            npc = {
                "id": f"rural:{self.state.wilderness_chunk_x}:{self.state.wilderness_chunk_y}:resident",
                "name": str(feature.get("name", record.get("resident_name", "Resident"))),
                "role": str(feature.get("role", record.get("resident_role", "Homesteader"))),
                "activity": f"working around {record.get('name', 'the holding')}",
                "origin": str(record.get("name", "this region")),
                "bond": int(record.get("resident_bond", 0)),
                "conversations": int(record.get("resident_conversations", 0)),
            }
            result = self.run_unified_npc_conversation(npc, kind="rural resident", first_meeting=npc["conversations"] <= 0, agenda_override=f"I live and work here at {record.get('name')}. The buildings, fields, animals, road, and stores all need daily attention.")
            if result.get("completed") or result.get("transcript"):
                record["resident_conversations"] = npc["conversations"] + 1
                record["resident_bond"] = npc["bond"] + 1
            return True
        if kind == "workbench":
            if hasattr(self, "crafting_menu"):
                self.crafting_menu()
            else:
                self.set_message("A maintained outdoor bench suitable for ordinary crafting and repair.")
            return True
        if kind == "trough":
            self.set_message("A filled livestock trough. The animals use it throughout the day.")
            return True
        if kind == "livestock":
            self.set_message(f"{feature.get('name', 'The animal')} is healthy and belongs to this household. It shifts calmly within the fenced pen.")
            return True
        return False

    def rural_site_description_at(self, x: int, y: int) -> str:
        if not self.wilderness_chunk_has_rural_infrastructure(
            self.state.wilderness_chunk_x, self.state.wilderness_chunk_y
        ):
            return ""
        door = self.rural_site_door_at(x, y)
        if door:
            return f"Door to {door.get('name', 'a rural building')}: walk into it to enter"
        feature = self.rural_site_feature_at(x, y)
        if feature:
            actions = {
                "directory": "read the property directory", "container": "open the real container",
                "well": "draw water", "crop": "harvest this individual plant",
                "orchard_tree": "pick fruit", "timber_stack": "collect usable timber",
                "drying_rack": "take prepared fish", "market_stall": "shop",
                "resident": "talk", "workbench": "craft or repair", "trough": "inspect",
                "livestock": "interact with the household animal",
            }
            return f"{feature.get('name', 'Rural feature')}: {actions.get(str(feature.get('kind')), 'interact')}"
        zone = self.rural_site_zone_at(x, y)
        return f"{self.rural_site_record().get('name', 'Rural holding')} {zone}" if zone else ""

    def use_rural_interior_action(self, x: int, y: int) -> bool:
        tile = self.active_map()[y][x]
        if tile == "D":
            self.exit_rural_site_building()
            return True
        if tile == "_":
            self.active_map()[y][x] = "|"
            self.set_message("Opened the room door.")
            return True
        if tile == "|":
            self.active_map()[y][x] = "_"
            self.set_message("Closed the room door.")
            return True
        if self.use_rural_interior_service(tile):
            return True
        if self.use_catalog_furniture_action_at(x, y):
            return True
        self.set_message("Nothing here needs direct interaction. Press I to inspect it.")
        return False


__all__ = [
    "RURAL_INFRASTRUCTURE_DOOR", "RURAL_INFRASTRUCTURE_LOCATION",
    "RURAL_INFRASTRUCTURE_VERSION", "RURAL_SITE_TYPES", "RuralInfrastructureMixin",
]
