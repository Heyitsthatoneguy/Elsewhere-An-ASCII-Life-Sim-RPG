"""Substantial abandoned sites that can be explored and physically restored."""

from __future__ import annotations

import random
from typing import Dict, List, Mapping, Optional, Tuple

from ascii_farmstead_helpers import quantity_item_phrase
from ascii_farmstead_inventory import add_inventory_items
from ascii_farmstead_procedural_interiors import build_procedural_ground_floor


ROUTE_HERITAGE_VERSION = 2
ROUTE_HERITAGE_LOCATION = "RouteHeritageInterior"
ROUTE_HERITAGE_DOOR = "d"
NO_HERITAGE = (10**8, 10**8)


ROUTE_HERITAGE_TYPES: Dict[str, Dict[str, object]] = {
    "abandoned_hamlet": {
        "title": "Abandoned Hamlet", "description": "A deserted road village whose homes and public buildings still form a complete street.",
        "buildings": (("hall", "Old Hamlet Hall", "town_hall"), ("store", "Shuttered General Store", "general_store"), ("workshop", "Village Workshop", "workshop"), ("home_a", "North Cottage", "home"), ("home_b", "South Cottage", "home")),
        "benefit": "waystation", "service_name": "Restored Waystation",
    },
    "ruined_manor": {
        "title": "Ruined Manor Estate", "description": "A walled country estate with a damaged manor, gatehouse, and overgrown conservatory.",
        "buildings": (("manor", "Old Manor House", "home"), ("gatehouse", "Estate Gatehouse", "home"), ("conservatory", "Broken Conservatory", "library")),
        "benefit": "hospitality", "service_name": "Estate Guest Register",
    },
    "fallen_keep": {
        "title": "Fallen Keep", "description": "A small secular hill fort with a keep, barracks, gatehouse, and intact central court.",
        "buildings": (("keep", "Old Keep", "town_hall"), ("barracks", "Empty Barracks", "inn"), ("gatehouse", "Keep Gatehouse", "sheriff_office")),
        "benefit": "lookout", "service_name": "Restored Lookout Table",
    },
    "deserted_farmstead": {
        "title": "Deserted Farmstead", "description": "A broad former holding with a farmhouse, barn, mill shed, yards, and surviving field walls.",
        "buildings": (("farmhouse", "Deserted Farmhouse", "home"), ("barn", "Old Barn", "workshop"), ("mill", "Farm Mill Shed", "carpenter")),
        "benefit": "produce", "service_name": "Restored Produce Store",
    },
    "industrial_ruin": {
        "title": "Old Works", "description": "A disused regional works with a production hall, office, warehouse, and freight court.",
        "buildings": (("works", "Old Production Hall", "workshop"), ("office", "Works Office", "town_hall"), ("warehouse", "Freight Warehouse", "general_store")),
        "benefit": "materials", "service_name": "Recovered Materials Store",
    },
    "abandoned_school": {
        "title": "Abandoned Country School", "description": "A closed rural school campus with classrooms, a boarding house, archive, and assembly yard.",
        "buildings": (("school", "Old Schoolhouse", "library"), ("boarding", "Empty Boarding House", "inn"), ("archive", "School Archive", "town_hall")),
        "benefit": "study", "service_name": "Restored Reading Room",
    },
}

HERITAGE_GIVEN_NAMES = ("Anya", "Bram", "Celia", "Devon", "Etta", "Flynn", "Gwen", "Hector", "Ida", "Joel", "Kira", "Lucian", "Mina", "Nico", "Opal", "Reese", "Sonia", "Tobin", "Una", "Wes")
HERITAGE_SURNAMES = ("Arden", "Blythe", "Crowe", "Dunn", "Eaton", "Frost", "Grant", "Hawke", "Ingram", "Kerr", "Lowell", "Mann", "Noble", "Pryce", "Rook", "Stone", "Trent", "Voss", "Wren", "York")
HERITAGE_PREFIXES = ("Alder", "Ashen", "Bell", "Briar", "Coldwater", "Dun", "East", "Gray", "Harrow", "Long", "Morrow", "North", "Oak", "Raven", "Red", "West", "Willow")
HERITAGE_SUFFIXES = ("Court", "Crossing", "Estate", "Fields", "Gate", "Hall", "Keep", "Row", "Works", "Yard")

HERITAGE_HAZARDS = {
    "rubble": {"name": "Collapsed Masonry", "glyph": "o", "tool": "Pickaxe", "salvage": {"Stone": 2}},
    "timber": {"name": "Fallen Timbers", "glyph": "*", "tool": "Axe", "salvage": {"Wood": 2}},
    "bracing": {"name": "Unsafe Wall Bracing", "glyph": "B", "tool": "Hammer", "salvage": {"Wood": 1, "Ruin Scrap": 1}},
}

HERITAGE_REPAIRS = (
    ("masonry", "Rebuild the Masonry", "Pickaxe", {"Stone": 10}, "m"),
    ("timber", "Replace the Roof Timbers", "Axe", {"Wood": 10}, "t"),
    ("fittings", "Secure Doors and Fittings", "Hammer", {"Metal Fittings": 1, "Wood": 4}, "f"),
)


class RouteHeritageMixin:
    """Generation, salvage, restoration, and reuse for abandoned sites."""

    def route_heritage_region_site_chunk(self, chunk_x: int, chunk_y: int) -> Tuple[int, int]:
        anchor = self.wilderness_region_coords(chunk_x, chunk_y)
        cache = getattr(self, "_route_heritage_site_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._route_heritage_site_cache = cache
        settlements = tuple(sorted(str(key) for key in (getattr(self.state, "wilderness_settlements", {}) or {})))
        claims = tuple(sorted(str(key) for key in (getattr(self.state, "owned_wilderness_claims", {}) or {})))
        key = (int(self.state.wilderness_seed), int(getattr(self.state, "wilderness_generation_version", 0) or 0), int(anchor[0]), int(anchor[1]), settlements, claims)
        if key in cache:
            return tuple(cache[key])
        unavailable = (10**8, 10**8)
        if anchor == self.wilderness_region_coords(0, 0):
            cache[key] = NO_HERITAGE
            return NO_HERITAGE
        if self.route_hamlet_region_site_chunk(*anchor) != unavailable or self.route_leisure_region_site_chunk(*anchor) != unavailable:
            cache[key] = NO_HERITAGE
            return NO_HERITAGE
        if self.wilderness_hash01(anchor[0], anchor[1], 86300) >= 0.085:
            cache[key] = NO_HERITAGE
            return NO_HERITAGE
        excluded = {
            tuple(self.wilderness_region_structure_chunk(*anchor)), tuple(self.wilderness_region_outpost_chunk(*anchor)),
            tuple(self.rural_region_site_chunk(*anchor)), tuple(self.corridor_region_site_chunk(*anchor)),
        }
        candidates: List[Tuple[int, int]] = []
        for cx, cy in self.wilderness_region_chunks(*anchor):
            point = (int(cx), int(cy))
            if point in excluded or self.home_world_chunk_is_authored(cx, cy):
                continue
            if self.procedural_town_plan(cx, cy) or self.wilderness_chunk_has_stronghold(cx, cy):
                continue
            if self.wilderness_chunk_has_dungeon_site(cx, cy) or self.is_claimable_wilderness_chunk(cx, cy) or self.owned_wilderness_claim(cx, cy):
                continue
            candidates.append(point)
        result = NO_HERITAGE if not candidates else candidates[random.Random(self.wilderness_chunk_seed(*anchor) + 86301).randrange(len(candidates))]
        cache[key] = result
        return result

    def wilderness_chunk_has_route_heritage(self, chunk_x: int, chunk_y: int) -> bool:
        return (int(chunk_x), int(chunk_y)) == self.route_heritage_region_site_chunk(chunk_x, chunk_y)

    def route_heritage_type(self, chunk_x: int, chunk_y: int) -> str:
        biome_id = str(self.wilderness_region_profile(chunk_x, chunk_y).get("biome_id", ""))
        if biome_id in {"prairie", "meadow", "floodplain", "wet_meadow"}:
            choices = ("deserted_farmstead", "abandoned_hamlet", "ruined_manor")
        elif biome_id in {"rocky_valley", "badlands", "alpine_meadow", "glacier"}:
            choices = ("fallen_keep", "industrial_ruin", "abandoned_school")
        elif biome_id in {"pine_forest", "old_growth", "birch_grove", "taiga"}:
            choices = ("ruined_manor", "abandoned_hamlet", "abandoned_school")
        else:
            choices = tuple(ROUTE_HERITAGE_TYPES)
        return choices[int(self.wilderness_hash01(chunk_x, chunk_y, 86302) * len(choices)) % len(choices)]

    def route_heritage_name(self, chunk_x: int, chunk_y: int) -> str:
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 86303)
        return f"{rng.choice(HERITAGE_PREFIXES)} {rng.choice(HERITAGE_SUFFIXES)}"

    def route_heritage_record(self, chunk_x: Optional[int] = None, chunk_y: Optional[int] = None) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        self.ensure_wilderness_poi_state()
        record = self.state.wilderness_poi_state.setdefault(f"heritage:{cx},{cy}", {})
        record.setdefault("kind", "route_heritage")
        record.setdefault("type_id", self.route_heritage_type(cx, cy))
        record.setdefault("name", self.route_heritage_name(cx, cy))
        record.setdefault("version", 0)
        record.setdefault("cleared_hazards", [])
        record.setdefault("completed_repairs", [])
        record.setdefault("restored", False)
        record.setdefault("benefit_weeks", {})
        return record

    @staticmethod
    def _heritage_feature(features: List[Dict[str, object]], x: int, y: int, kind: str, name: str, glyph: str, **extra: object) -> None:
        features.append({"x": int(x), "y": int(y), "kind": str(kind), "name": str(name), "glyph": str(glyph)[:1], **extra})

    @staticmethod
    def _heritage_disruption_score(grid: List[List[str]], left: int, top: int, width: int, height: int) -> int:
        weights = {"~": 14, "=": 7, ":": 4, "#": 5, "S": 100, "X": 100, "!": 100, "A": 70, "E": 70, "h": 50, "j": 40, "k": 40, "q": 40, "R": 50, "J": 50, "P": 50, "K": 50, "Q": 50, "Y": 50, "G": 50, "Z": 50}
        return sum(weights.get(grid[y][x], 0) for y in range(top, top + height) for x in range(left, left + width))

    def place_route_heritage(self, grid: List[List[str]], chunk_x: int, chunk_y: int) -> bool:
        if not self.wilderness_chunk_has_route_heritage(chunk_x, chunk_y) or self.procedural_town_plan(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return False
        record = self.route_heritage_record(chunk_x, chunk_y)
        saved_doors = list(record.get("doors", ()) or ())
        if int(record.get("version", 0)) >= ROUTE_HERITAGE_VERSION and saved_doors and all(
            0 <= int(door.get("y", -1)) < len(grid) and 0 <= int(door.get("x", -1)) < len(grid[0])
            and grid[int(door["y"])][int(door["x"])] == ROUTE_HERITAGE_DOOR for door in saved_doors
        ):
            return True
        width, height = 70, 31
        saved_parcel = list(record.get("parcel", ()) or ())
        if len(saved_parcel) == 4:
            left, top, old_right, old_bottom = map(int, saved_parcel)
            width, height = old_right - left + 1, old_bottom - top + 1
        else:
            scored = [(self._heritage_disruption_score(grid, left, top, width, height), left, top) for top in range(2, len(grid) - height - 1) for left in range(3, len(grid[0]) - width - 2)]
            if not scored:
                return False
            best = min(score for score, _left, _top in scored)
            choices = [(left, top) for score, left, top in scored if score <= best + max(10, best // 20)]
            left, top = choices[random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 86304).randrange(len(choices))]
        right, bottom = left + width - 1, top + height - 1
        original_roads = [
            (x, y) for y, row in enumerate(grid) for x, tile in enumerate(row)
            if tile in {":", "="}
        ]
        roads = [
            (x, y) for x, y in original_roads
            if not (left <= x <= right and top <= y <= bottom)
        ]
        ground = self.wilderness_world_biome_tile(*self.wilderness_world_coords(chunk_x, chunk_y, left + width // 2, top + height // 2))
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                grid[y][x] = ground
        center_x, court_y = left + width // 2, top + height // 2
        restored = bool(record.get("restored"))
        for x in range(left, right + 1):
            grid[top][x] = grid[bottom][x] = "#"
        for y in range(top, bottom + 1):
            grid[y][left] = grid[y][right] = "#"
        for x in range(left + 1, right):
            grid[court_y][x] = ":" if restored else "."
        for y in range(court_y, bottom + 1):
            for x in range(center_x - 1, center_x + 2):
                grid[y][x] = ":" if restored else "."
        for x in range(center_x - 1, center_x + 2):
            grid[bottom][x] = "|"
        if not self.connect_wilderness_site_to_regional_road(grid, (center_x, bottom + 1), roads):
            for y in range(bottom + 1, len(grid)):
                grid[y][center_x] = ":"
        profile = ROUTE_HERITAGE_TYPES[str(record["type_id"])]
        buildings = tuple(profile["buildings"])
        centers = ((left + 12, top + 7), (center_x, top + 7), (right - 12, top + 7), (left + 18, bottom - 6), (right - 18, bottom - 6))
        doors: List[Dict[str, object]] = []
        for index, (building_id, name, interior_type) in enumerate(buildings):
            side = "south" if index < 3 else "north"
            size = (18, 9) if index else (20, 10)
            door_x, door_y, outside_x, outside_y = self.stamp_wilderness_building_exterior(grid, centers[index], size, side, ROUTE_HERITAGE_DOOR, ground)
            doors.append({"x": door_x, "y": door_y, "outside_x": outside_x, "outside_y": outside_y, "side": side, "building_id": building_id, "name": name, "interior_type": interior_type})
            for y in range(min(outside_y, court_y), max(outside_y, court_y) + 1):
                grid[y][outside_x] = ":" if restored else "."
        features: List[Dict[str, object]] = []
        self._heritage_feature(features, center_x - 7, court_y - 1, "directory", f"{record['name']} Survey Board", "n")
        repair_xs = (left + 15, center_x, right - 15)
        completed = set(str(value) for value in record.get("completed_repairs", ()))
        for index, (repair_id, name, tool, materials, glyph) in enumerate(HERITAGE_REPAIRS):
            self._heritage_feature(features, repair_xs[index], court_y + 5, "repair", name, glyph.upper() if repair_id in completed else glyph, repair_id=repair_id, tool=tool, materials=dict(materials))
        self._heritage_feature(features, center_x, court_y + 9, "benefit", str(profile["service_name"]), "S" if restored else "s")
        self._heritage_feature(features, center_x + 8, court_y - 1, "salvage_locker", "Recovered-Goods Locker", "c", profile="ruin_chest")
        for feature in features:
            grid[int(feature["y"])][int(feature["x"])] = str(feature["glyph"])
        self.preserve_wilderness_roads_around_parcel(
            grid, (left, top, right, bottom), original_roads,
            (center_x, bottom + 1),
        )
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 86305)
        caretakers = []
        if restored:
            for index in range(2):
                caretakers.append({"id": f"heritage:{chunk_x},{chunk_y}:caretaker:{index}", "name": f"{rng.choice(HERITAGE_GIVEN_NAMES)} {rng.choice(HERITAGE_SURNAMES)}", "role": "Site Steward" if index == 0 else "Restoration Worker", "bond": 0, "conversations": 0})
        record.update({"version": ROUTE_HERITAGE_VERSION, "parcel": [left, top, right, bottom], "gate": [center_x, bottom], "doors": doors, "features": features, "caretakers": caretakers, "court": [center_x, court_y]})
        return True

    def route_heritage_feature_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_heritage(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((feature for feature in self.route_heritage_record().get("features", ()) if (int(feature.get("x", -1)), int(feature.get("y", -1))) == (int(x), int(y))), None)

    def route_heritage_door_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_heritage(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((door for door in self.route_heritage_record().get("doors", ()) if (int(door.get("x", -1)), int(door.get("y", -1))) == (int(x), int(y))), None)

    def route_heritage_caretaker_position(self, caretaker: Mapping[str, object], chunk_x: Optional[int] = None, chunk_y: Optional[int] = None) -> Tuple[int, int, str]:
        record = self.route_heritage_record(chunk_x, chunk_y)
        court_x, court_y = map(int, record.get("court", (43, 19)))
        index = int(str(caretaker.get("id", "0")).rsplit(":", 1)[-1] or 0)
        hour = int(getattr(self.state, "hour", 8))
        if 8 <= hour < 18:
            return court_x + (-5 if index == 0 else 5), court_y + 1, "maintaining the restored grounds"
        first_door = list(record.get("doors", ({})))[index % max(1, len(record.get("doors", ())))]
        return int(first_door.get("outside_x", court_x)), int(first_door.get("outside_y", court_y)), "closing the restored buildings"

    def route_heritage_caretaker_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_heritage(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        for caretaker in self.route_heritage_record().get("caretakers", ()):
            cx, cy, activity = self.route_heritage_caretaker_position(caretaker)
            if (cx, cy) == (int(x), int(y)):
                result = dict(caretaker); result.update({"x": cx, "y": cy, "activity": activity}); return result
        return None

    def talk_to_route_heritage_caretaker(self, caretaker: Mapping[str, object]) -> bool:
        record = self.route_heritage_record()
        stored = next((row for row in record.get("caretakers", ()) if str(row.get("id")) == str(caretaker.get("id"))), None)
        if not isinstance(stored, dict):
            return False
        actor = {"id": str(stored["id"]), "name": str(stored["name"]), "role": str(stored["role"]), "activity": str(caretaker.get("activity", "maintaining the site")), "origin": str(record["name"]), "bond": int(stored.get("bond", 0)), "conversations": int(stored.get("conversations", 0))}
        result = self.run_unified_npc_conversation(actor, kind="heritage site worker", first_meeting=actor["conversations"] <= 0, agenda_override=f"I help maintain {record['name']} now that its buildings are safe again. The site has a practical public use as well as its old architecture.")
        if result.get("completed") or result.get("transcript"):
            stored["conversations"] = actor["conversations"] + 1; stored["bond"] = actor["bond"] + 1
        return True

    def enter_route_heritage_building(self, door: Mapping[str, object]) -> bool:
        self.state.current_heritage_site_key = f"{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}"
        self.state.current_heritage_building_id = str(door.get("building_id", "hall"))
        self.state.heritage_interior_return_x = int(door.get("outside_x", door.get("x", 1)))
        self.state.heritage_interior_return_y = int(door.get("outside_y", door.get("y", 1)))
        self.state.location = ROUTE_HERITAGE_LOCATION
        grid = self.route_heritage_interior_map()
        self.state.player_x, self.state.player_y = self.wilderness_interior_entry_landing(grid, str(door.get("side", "south")))
        self.state.facing = "UP" if door.get("side") == "south" else "DOWN"
        self.set_message(f"Entered {door.get('name', 'the abandoned building')}.")
        return True

    def exit_route_heritage_building(self) -> None:
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        self.state.player_x, self.state.player_y = self.nearest_active_passable_tile(int(self.state.heritage_interior_return_x), int(self.state.heritage_interior_return_y))
        self.set_message("Stepped back into the old courtyard.")

    def current_route_heritage_building(self) -> Dict[str, object]:
        building_id = str(getattr(self.state, "current_heritage_building_id", ""))
        return next((dict(door) for door in self.route_heritage_record().get("doors", ()) if str(door.get("building_id")) == building_id), {})

    @staticmethod
    def _heritage_open_floor_cells(grid: List[List[str]]) -> List[Tuple[int, int]]:
        return [(x, y) for y in range(2, len(grid) - 2) for x in range(2, len(grid[0]) - 2) if grid[y][x] == "." and sum(grid[y + dy][x + dx] == "." for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) >= 3]

    def route_heritage_interior_map(self) -> List[List[str]]:
        site_key = str(getattr(self.state, "current_heritage_site_key", self.wilderness_chunk_key()))
        building = self.current_route_heritage_building(); building_id = str(building.get("building_id", "hall")); cache_key = (site_key, building_id)
        cache = getattr(self, "_route_heritage_interior_cache", None)
        if not isinstance(cache, dict): cache = {}; self._route_heritage_interior_cache = cache
        if cache_key in cache: return cache[cache_key]
        seed = sum((index + 1) * ord(ch) for index, ch in enumerate(f"{site_key}:{building_id}:heritage")); rng = random.Random(seed)
        placements: List[Dict[str, object]] = []
        raw_grid = build_procedural_ground_floor(str(building.get("interior_type", "home")), rng.randrange(4), rng.randrange(12), 1, program_variant=rng.randrange(3), furniture_placements=placements)
        side = str(building.get("side", "south")); grid = self.orient_south_door_interior(raw_grid, side)
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        for placement in placements:
            common = {key: placement.get(key) for key in ("name", "collection", "form", "room_id", "room_role", "rotation", "width", "height")}
            for cell in placement.get("cells", ()) or ():
                item = dict(common); item.update(cell); cell_x, cell_y = int(cell.get("x", 0)), int(cell.get("y", 0))
                if side == "north": cell_y = len(raw_grid) - 1 - cell_y
                lookup[(cell_x, cell_y)] = item
        floors = self._heritage_open_floor_cells(grid); rng.shuffle(floors)
        hazard_specs, container_specs = [], []
        cleared = set(str(value) for value in self.route_heritage_record().get("cleared_hazards", ()))
        for index, hazard_id in enumerate(("rubble", "timber", "bracing")):
            if index >= len(floors): break
            x, y = floors[index]; key = f"{building_id}:{x},{y}"; spec = {"x": x, "y": y, "key": key, "hazard_id": hazard_id, **HERITAGE_HAZARDS[hazard_id]}; hazard_specs.append(spec)
            if key not in cleared: grid[y][x] = str(spec["glyph"])
            lookup.pop((x, y), None)
        for index, profile in enumerate(("ruin_chest", "bookshelf")):
            floor_index = 4 + index * max(1, len(floors) // 4)
            if floor_index >= len(floors): continue
            x, y = floors[floor_index]
            if any((int(spec["x"]), int(spec["y"])) == (x, y) for spec in hazard_specs): continue
            container_specs.append({"x": x, "y": y, "profile": profile, "name": "Recovered Site Chest" if profile == "ruin_chest" else "Dusty Records Shelf"}); grid[y][x] = "c" if profile == "ruin_chest" else "s"; lookup.pop((x, y), None)
        catalogs = getattr(self, "_route_heritage_catalog_cache", None)
        if not isinstance(catalogs, dict): catalogs = {}; self._route_heritage_catalog_cache = catalogs
        catalogs[cache_key] = lookup
        specs = getattr(self, "_route_heritage_interior_spec_cache", None)
        if not isinstance(specs, dict): specs = {}; self._route_heritage_interior_spec_cache = specs
        specs[cache_key] = {"hazards": hazard_specs, "containers": container_specs}
        cache[cache_key] = grid; return grid

    def route_heritage_interior_specs(self) -> Dict[str, object]:
        self.route_heritage_interior_map(); key = (str(self.state.current_heritage_site_key), str(self.state.current_heritage_building_id)); return getattr(self, "_route_heritage_interior_spec_cache", {}).get(key, {})

    def route_heritage_hazard_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != ROUTE_HERITAGE_LOCATION: return None
        cleared = set(str(value) for value in self.route_heritage_record().get("cleared_hazards", ()))
        return next((dict(spec) for spec in self.route_heritage_interior_specs().get("hazards", ()) if (int(spec["x"]), int(spec["y"])) == (int(x), int(y)) and str(spec["key"]) not in cleared), None)

    def route_heritage_container_spec_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != ROUTE_HERITAGE_LOCATION: return None
        return next((dict(spec) for spec in self.route_heritage_interior_specs().get("containers", ()) if (int(spec["x"]), int(spec["y"])) == (int(x), int(y))), None)

    def route_heritage_catalog_furniture_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != ROUTE_HERITAGE_LOCATION: return None
        self.route_heritage_interior_map(); key = (str(self.state.current_heritage_site_key), str(self.state.current_heritage_building_id)); return getattr(self, "_route_heritage_catalog_cache", {}).get(key, {}).get((int(x), int(y)))

    def route_heritage_container(self, x: int, y: int, spec: Mapping[str, object]) -> Dict[str, object]:
        key = f"heritage:{self.state.current_heritage_site_key}:{self.state.current_heritage_building_id}:{int(x)},{int(y)}:{spec.get('profile', 'ruin_chest')}"
        existing = self.state.world_containers.get(key)
        if isinstance(existing, dict): return existing
        return self.create_container_record(key, int(x), int(y), str(spec.get("profile", "ruin_chest")), name=str(spec.get("name", "Recovered Container")), take_policy="free", allow_deposit=False)

    def route_heritage_locker(self, feature: Mapping[str, object]) -> Dict[str, object]:
        key = f"heritage:{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}:locker"
        existing = self.state.world_containers.get(key)
        if isinstance(existing, dict): return existing
        return self.create_container_record(key, int(feature["x"]), int(feature["y"]), "ruin_chest", name=str(feature.get("name", "Recovered-Goods Locker")), take_policy="player", allow_deposit=True, contents={})

    def route_heritage_total_hazards(self) -> int:
        record = self.route_heritage_record(); previous_site = getattr(self.state, "current_heritage_site_key", ""); previous_building = getattr(self.state, "current_heritage_building_id", "")
        self.state.current_heritage_site_key = f"{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}"
        total = 0
        for door in record.get("doors", ()):
            self.state.current_heritage_building_id = str(door.get("building_id", "")); self.route_heritage_interior_map(); total += len(self.route_heritage_interior_specs().get("hazards", ()))
        self.state.current_heritage_site_key, self.state.current_heritage_building_id = previous_site, previous_building
        return total

    def use_route_heritage_hazard_tool(self, tool: str, x: int, y: int) -> bool:
        hazard = self.route_heritage_hazard_at(x, y)
        if not hazard: return False
        required = str(hazard["tool"])
        if str(tool) != required:
            self.set_message(f"{hazard['name']} requires the {required}."); return True
        if not self.owns_tool(required):
            self.set_message(f"You need to own a {required} to clear this hazard."); return True
        if not self.spend_stamina(4): return True
        self.advance_time(10); record = self.route_heritage_record(); record.setdefault("cleared_hazards", []).append(str(hazard["key"])); self.active_map()[int(y)][int(x)] = "."; add_inventory_items(self.state.inventory, dict(hazard["salvage"]))
        self.autosave_with_message(f"Cleared {str(hazard['name']).lower()} with the {required}. Recovered {', '.join(quantity_item_phrase(item, qty) for item, qty in hazard['salvage'].items())}."); return True

    def route_heritage_missing_materials(self, feature: Mapping[str, object]) -> Dict[str, int]:
        return {str(item): int(qty) - int(self.state.inventory.get(str(item), 0)) for item, qty in dict(feature.get("materials", {})).items() if int(self.state.inventory.get(str(item), 0)) < int(qty)}

    def use_route_heritage_repair_tool(self, tool: str, feature: Mapping[str, object]) -> bool:
        if str(feature.get("kind")) != "repair": return False
        record = self.route_heritage_record(); repair_id = str(feature.get("repair_id", "")); completed = record.setdefault("completed_repairs", [])
        if repair_id in completed:
            self.set_message(f"{feature.get('name')} is already complete."); return True
        remaining = max(0, self.route_heritage_total_hazards() - len(set(str(value) for value in record.get("cleared_hazards", ()))))
        if remaining:
            self.set_message(f"Clear the {remaining} remaining interior hazard(s) before structural restoration."); return True
        required = str(feature.get("tool", "Hammer"))
        if str(tool) != required:
            self.set_message(f"{feature.get('name')} requires the {required}."); return True
        if not self.owns_tool(required):
            self.set_message(f"You need to own a {required} to complete this repair."); return True
        missing = self.route_heritage_missing_materials(feature)
        if missing:
            self.set_message("Missing " + ", ".join(quantity_item_phrase(item, qty) for item, qty in missing.items()) + "."); return True
        if not self.spend_stamina(8): return True
        for item, qty in dict(feature.get("materials", {})).items(): self.state.inventory[str(item)] -= int(qty)
        self.advance_time(60); completed.append(repair_id)
        if len(set(completed)) >= len(HERITAGE_REPAIRS):
            record["restored"] = True; self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 6, f"restored {record['name']}"); self._route_heritage_rebuild_current_site(record)
            self.autosave_with_message(f"Completed {feature.get('name')}. {record['name']} is restored, staffed, and open for public use."); return True
        self._route_heritage_rebuild_current_site(record); self.autosave_with_message(f"Completed {feature.get('name')}. {len(completed)}/{len(HERITAGE_REPAIRS)} site repairs finished."); return True

    def _route_heritage_rebuild_current_site(self, record: Dict[str, object]) -> None:
        record["version"] = 0; key = self.wilderness_chunk_key(); grid = self.wilderness_maps.get(key)
        if not grid:
            # The streaming window evicts chunk maps that are not currently
            # visible. Without this the rebuild silently did nothing, leaving a
            # restored site permanently without its caretakers or restored
            # fixtures until something else happened to regenerate the chunk.
            try:
                grid = self.get_wilderness_chunk_map(
                    int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
                )
            except Exception:
                grid = None
        if grid:
            self.place_route_heritage(grid, self.state.wilderness_chunk_x, self.state.wilderness_chunk_y); self.wilderness_map = grid
        self.invalidate_wilderness_road_network()

    def use_route_heritage_benefit(self) -> bool:
        record = self.route_heritage_record(); profile = ROUTE_HERITAGE_TYPES[str(record["type_id"])]
        if not record.get("restored"):
            self.set_message("The site must be made safe and restored before this facility can operate."); return True
        week = self.stronghold_cache_week_key(); benefit = str(profile["benefit"])
        if record.setdefault("benefit_weeks", {}).get(benefit) == week:
            self.set_message("You already used this restored facility this week."); return True
        record["benefit_weeks"][benefit] = week; message = ""
        if benefit == "waystation": self.restore_stamina(40); message = "Rested and resupplied at the restored waystation."
        elif benefit == "hospitality": self.restore_stamina(30); self.state.money += 90; message = "Helped host travelers at the restored estate and earned 90g."
        elif benefit == "lookout": added = self.map_nearby_wilderness_chunks(3); message = f"Surveyed from the restored lookout and mapped {added} nearby area(s)."
        elif benefit == "produce": add_inventory_items(self.state.inventory, {"Field Snack": 3, "Mixed Seeds": 4}); message = "Collected the farmstead's weekly produce and seed allotment."
        elif benefit == "materials": add_inventory_items(self.state.inventory, {"Metal Fittings": 1, "Ruin Scrap": 2, "Coal": 2}); message = "Collected reusable materials prepared at the restored works."
        else: added = self.map_nearby_wilderness_chunks(2); add_inventory_items(self.state.inventory, {"Old Town Ledger": 1}); message = f"Studied the restored archive, mapped {added} area(s), and copied an Old Town Ledger."
        self.advance_time(45); self.autosave_with_message(message); return True

    def route_heritage_directory_lines(self) -> List[str]:
        record = self.route_heritage_record(); profile = ROUTE_HERITAGE_TYPES[str(record["type_id"])]
        total = self.route_heritage_total_hazards(); cleared = len(set(str(value) for value in record.get("cleared_hazards", ())))
        return [str(record["name"]).upper(), str(profile["title"]), "", str(profile["description"]), "", f"Interior hazards cleared: {cleared}/{total}", f"Structural repairs: {len(set(record.get('completed_repairs', ())))}/{len(HERITAGE_REPAIRS)}", f"Status: {'Restored and staffed' if record.get('restored') else 'Abandoned'}", "", "Buildings:", *[f"- {door.get('name')}" for door in record.get("doors", ())], "", "Clear interior hazards with the tool named by inspection. Once every building is safe, repair the three physical work stations in the courtyard."]

    def use_route_heritage_feature(self, feature: Mapping[str, object]) -> bool:
        kind = str(feature.get("kind", ""))
        if kind == "directory": self.vertical_panel_view(str(self.route_heritage_record()["name"]), self.route_heritage_directory_lines(), 52, 22); return True
        if kind == "salvage_locker": self.show_world_container(self.route_heritage_locker(feature)); return True
        if kind == "benefit": return self.use_route_heritage_benefit()
        if kind == "repair":
            required = str(feature.get("tool", "Hammer")); missing = self.route_heritage_missing_materials(feature); suffix = "" if not missing else " Missing " + ", ".join(quantity_item_phrase(item, qty) for item, qty in missing.items()) + "."
            self.set_message(f"Select the {required} and press F to {str(feature.get('name', 'repair this')).lower()}.{suffix}"); return True
        return False

    def route_heritage_description_at(self, x: int, y: int) -> str:
        if not self.wilderness_chunk_has_route_heritage(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y): return ""
        caretaker = self.route_heritage_caretaker_at(x, y)
        if caretaker: return f"{caretaker['name']} ({caretaker['role']}): {caretaker['activity']}. Use Z/Enter to talk"
        door = self.route_heritage_door_at(x, y)
        if door: return f"Door to {door.get('name', 'an abandoned building')}: walk into it to enter"
        feature = self.route_heritage_feature_at(x, y)
        if feature:
            if feature.get("kind") == "repair": return f"{feature.get('name')}: {feature.get('tool')} required; use F with the tool selected"
            return f"{feature.get('name', 'Heritage-site fixture')}: use Z/Enter"
        parcel = self.route_heritage_record().get("parcel", ())
        if len(parcel) == 4 and int(parcel[0]) <= int(x) <= int(parcel[2]) and int(parcel[1]) <= int(y) <= int(parcel[3]): return f"Grounds of {self.route_heritage_record()['name']}"
        return ""

    def use_route_heritage_interior_action(self, x: int, y: int) -> bool:
        tile = self.active_map()[y][x]
        if tile == "D": self.exit_route_heritage_building(); return True
        if tile == "_": self.active_map()[y][x] = "|"; self.set_message("Opened the room door."); return True
        if tile == "|": self.active_map()[y][x] = "_"; self.set_message("Closed the room door."); return True
        hazard = self.route_heritage_hazard_at(x, y)
        if hazard: self.set_message(f"{hazard['name']}: select the {hazard['tool']} and press F to clear it."); return True
        container = self.route_heritage_container_spec_at(x, y)
        if container: self.show_world_container(self.route_heritage_container(x, y, container)); return True
        if self.use_catalog_furniture_action_at(x, y): return True
        self.set_message("Nothing here needs direct interaction. Press I to inspect it."); return False


__all__ = ["NO_HERITAGE", "ROUTE_HERITAGE_DOOR", "ROUTE_HERITAGE_LOCATION", "ROUTE_HERITAGE_TYPES", "ROUTE_HERITAGE_VERSION", "RouteHeritageMixin"]
