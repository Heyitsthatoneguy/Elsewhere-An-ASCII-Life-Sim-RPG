"""Working commercial and industrial properties along wilderness roads.

Corridor sites are physical destinations rather than menu POIs.  Each site has
two enterable buildings, a legible production yard, workers, staffed trade,
persistent containers, and an ordered hands-on shift that produces real goods.
"""

from __future__ import annotations

import random
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK
from ascii_farmstead_helpers import quantity_item_phrase
from ascii_farmstead_inventory import add_inventory_items
from ascii_farmstead_procedural_interiors import build_procedural_ground_floor
from ascii_farmstead_ui import MenuItem


CORRIDOR_INFRASTRUCTURE_VERSION = 2
CORRIDOR_INFRASTRUCTURE_LOCATION = "CorridorInfrastructureInterior"
CORRIDOR_INFRASTRUCTURE_DOOR = "d"


CORRIDOR_SITE_TYPES: Dict[str, Dict[str, object]] = {
    "grain_mill": {
        "name": "Roadside Grain Mill", "role": "Miller", "product": "Flour Sack",
        "product_qty": 2, "wage": 85, "yard": "mill",
        "description": "A working mill, granary, loading court, and grain-processing line.",
        "buildings": (("mill_house", "Mill House", "workshop", (23, 11)), ("granary", "Granary Store", "general_store", (17, 9))),
        "stations": (("hopper", "Grain Receiving Hopper", "g"), ("millstone", "Drive Millstone", "O"), ("bagging", "Flour Bagging Table", "b")),
        "stock": (("Flour Sack", 75), ("Field Snack", 35), ("Fiber", 4)),
    },
    "wagonworks": {
        "name": "Crossroad Wagonworks", "role": "Wheelwright", "product": "Wagon Parts",
        "product_qty": 2, "wage": 100, "yard": "wagon",
        "description": "A wheelwright's shop with timber racks, an assembly court, and a parts office.",
        "buildings": (("wheelwright", "Wheelwright Shop", "carpenter", (23, 11)), ("parts_office", "Parts and Dispatch Office", "general_store", (17, 9))),
        "stations": (("timber_rack", "Select Seasoned Timber", "l"), ("wagon_frame", "Wagon Assembly Frame", "W"), ("finishing", "Finish and Fit Parts", "p")),
        "stock": (("Wagon Parts", 125), ("Wood", 12), ("Hardwood", 35), ("Fiber", 4)),
    },
    "textile_works": {
        "name": "Riverside Textile Works", "role": "Weaver", "product": "Cloth Bolt",
        "product_qty": 2, "wage": 90, "yard": "textile",
        "description": "A compact textile yard with washing vats, looms, drying lines, and a cloth shop.",
        "buildings": (("weaving_hall", "Weaving Hall", "workshop", (23, 11)), ("cloth_shop", "Cloth Shop", "general_store", (17, 9))),
        "stations": (("wash_vat", "Wash and Card Fiber", "u"), ("loom", "Working Loom", "L"), ("drying_line", "Cloth Drying Line", "y")),
        "stock": (("Cloth Bolt", 105), ("Fiber", 4), ("Soft Fiber", 125)),
    },
    "stoneworks": {
        "name": "Regional Stoneworks", "role": "Stonecutter", "product": "Cut Stone",
        "product_qty": 3, "wage": 105, "yard": "stone",
        "description": "A stonecutting property with a receiving bay, cutting floor, and masonry store.",
        "buildings": (("cutting_hall", "Stonecutting Hall", "workshop", (23, 11)), ("masonry_store", "Masonry Store", "general_store", (17, 9))),
        "stations": (("stone_pile", "Select Sound Stone", "o"), ("stone_saw", "Stone Cutting Bed", "c"), ("stone_pallet", "Finished Stone Pallet", "p")),
        "stock": (("Cut Stone", 60), ("Stone", 8), ("Stone Path", 18)),
    },
    "brickworks": {
        "name": "Clayfield Brickworks", "role": "Brickmaker", "product": "Fired Brick",
        "product_qty": 3, "wage": 95, "yard": "brick",
        "description": "An open brick yard with clay bins, molding tables, drying rows, and a firing kiln.",
        "buildings": (("kiln_house", "Kiln House", "workshop", (21, 11)), ("brick_office", "Brick Office and Store", "general_store", (17, 9))),
        "stations": (("clay_bin", "Prepared Clay Bin", "c"), ("brick_molds", "Brick Molding Table", "m"), ("kiln", "Working Brick Kiln", "K")),
        "stock": (("Fired Brick", 65), ("Clay", 22), ("Coal", 20)),
    },
    "metalworks": {
        "name": "Frontier Metalworks", "role": "Metalsmith", "product": "Metal Fittings",
        "product_qty": 1, "wage": 130, "yard": "metal",
        "description": "A practical forge complex supplying fittings, repairs, and hardware to the road network.",
        "buildings": (("forge_hall", "Forge Hall", "workshop", (23, 11)), ("hardware_store", "Hardware Store", "general_store", (17, 9))),
        "stations": (("ore_bin", "Sorted Ore and Scrap", "o"), ("furnace", "Working Furnace", "F"), ("anvil", "Fitting Anvil", "a")),
        "stock": (("Metal Fittings", 180), ("Coal", 20), ("Copper Bar", 95), ("Iron Bar", 180)),
    },
    "fishworks": {
        "name": "Coastal Fishworks", "role": "Fish Processor", "product": "Smoked Fish",
        "product_qty": 2, "wage": 95, "yard": "fish",
        "description": "A waterside processing yard with wash tables, smoke racks, packing space, and a chandlery.",
        "buildings": (("smokehouse", "Fish Smokehouse", "workshop", (21, 11)), ("chandlery", "Fishworks Chandlery", "general_store", (17, 9))),
        "stations": (("wash_table", "Fish Washing Table", "u"), ("smoke_rack", "Working Smoke Rack", "r"), ("packing_table", "Packing Table", "p")),
        "stock": (("Smoked Fish", 105), ("Marsh Reed", 18), ("Fiber", 4), ("Wood", 12)),
    },
    "trade_depot": {
        "name": "Regional Trade Depot", "role": "Factor", "product": "Trade Parcel",
        "product_qty": 2, "wage": 110, "yard": "trade",
        "description": "A staffed freight depot where regional goods are weighed, sorted, stored, and dispatched.",
        "buildings": (("freight_house", "Freight House", "workshop", (23, 11)), ("factor_office", "Factor's Office and Store", "general_store", (19, 9))),
        "stations": (("receiving", "Freight Receiving Bay", "r"), ("scale", "Freight Scale", "S"), ("loading", "Loading Platform", "W")),
        "stock": (("Trade Parcel", 145), ("Field Snack", 35), ("Wood", 12), ("Stone", 10)),
    },
}


CORRIDOR_WORKER_NAMES = (
    "Ada Barlow", "Beckett Crane", "Celia Dyer", "Damon Foster",
    "Esme Gable", "Ford Hollis", "Gia Irwin", "Harvey Keene",
    "June Larkin", "Kit Mercer", "Lena North", "Micah Orton",
    "Nell Porter", "Owen Quill", "Pia Rowan", "Rafe Sawyer",
)


class CorridorInfrastructureMixin:
    """Placement, interiors, production, trade, and interaction for road industry."""

    def corridor_region_site_chunk(self, chunk_x: int, chunk_y: int) -> Tuple[int, int]:
        anchor = self.wilderness_region_coords(chunk_x, chunk_y)
        cache = getattr(self, "_corridor_region_site_chunk_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._corridor_region_site_chunk_cache = cache
        cache_key = (
            int(getattr(self.state, "wilderness_seed", 0)),
            int(getattr(self.state, "wilderness_generation_version", 0) or 0),
            int(anchor[0]), int(anchor[1]), self.wilderness_road_state_signature(),
        )
        if cache_key in cache:
            return tuple(cache[cache_key])
        excluded = {
            tuple(self.wilderness_region_structure_chunk(*anchor)),
            tuple(self.wilderness_region_outpost_chunk(*anchor)),
            tuple(self.rural_region_site_chunk(*anchor)),
        }
        candidates = []
        for cx, cy in self.wilderness_region_chunks(*anchor):
            point = (int(cx), int(cy))
            if point in excluded or self.home_world_chunk_is_authored(cx, cy):
                continue
            if self.procedural_town_plan(cx, cy) or self.wilderness_chunk_has_stronghold(cx, cy):
                continue
            if self.wilderness_chunk_has_dungeon_site(cx, cy):
                continue
            if self.is_claimable_wilderness_chunk(cx, cy) or self.owned_wilderness_claim(cx, cy):
                continue
            candidates.append(point)
        if not candidates:
            result = (10**8, 10**8)
        else:
            rng = random.Random(self.wilderness_chunk_seed(*anchor) + 73201)
            result = candidates[rng.randrange(len(candidates))]
        cache[cache_key] = result
        return result

    def wilderness_chunk_has_corridor_infrastructure(self, chunk_x: int, chunk_y: int) -> bool:
        return (int(chunk_x), int(chunk_y)) == self.corridor_region_site_chunk(chunk_x, chunk_y)

    def corridor_site_type(self, chunk_x: int, chunk_y: int) -> str:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        biome_id = str(profile.get("biome_id", ""))
        biome_tile = str(profile.get("biome", ";"))
        if biome_tile == "[" or biome_id in {"tidal_flat", "mangrove", "tropical_isle"}:
            return "fishworks"
        if biome_id in {"rocky_valley", "badlands", "alpine_meadow", "glacier"}:
            return "stoneworks"
        if biome_id in {"floodplain", "wet_meadow", "marsh", "dune_desert"}:
            return "brickworks"
        if biome_id in {"pine_forest", "old_growth", "scrubland"}:
            return "wagonworks"
        if biome_id in {"birch_grove", "moorland", "taiga"}:
            return "textile_works"
        choices = ("grain_mill", "trade_depot", "metalworks")
        index = int(self.wilderness_hash01(chunk_x, chunk_y, 73202) * len(choices)) % len(choices)
        return choices[index]

    def corridor_site_record(self, chunk_x: Optional[int] = None, chunk_y: Optional[int] = None) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        self.ensure_wilderness_poi_state()
        type_id = self.corridor_site_type(cx, cy)
        profile = CORRIDOR_SITE_TYPES[type_id]
        record = self.state.wilderness_poi_state.setdefault(f"corridor:{cx},{cy}", {})
        record.setdefault("kind", "corridor_infrastructure")
        record.setdefault("type_id", type_id)
        record.setdefault("name", profile["name"])
        name_index = int(self.wilderness_hash01(cx, cy, 73203) * len(CORRIDOR_WORKER_NAMES)) % len(CORRIDOR_WORKER_NAMES)
        record.setdefault("manager_name", CORRIDOR_WORKER_NAMES[name_index])
        record.setdefault("manager_role", profile["role"])
        record.setdefault("version", 0)
        return record

    @staticmethod
    def _corridor_feature(features: List[Dict[str, object]], x: int, y: int, kind: str, name: str, glyph: str, **extra: object) -> None:
        features.append({"x": int(x), "y": int(y), "kind": str(kind), "name": str(name), "glyph": str(glyph)[:1], **extra})

    @staticmethod
    def _corridor_disruption_score(grid: List[List[str]], left: int, top: int, width: int, height: int) -> int:
        weights = {"~": 12, "=": 7, ":": 4, "#": 5, "S": 100, "X": 100, "!": 100, "A": 70, "E": 70, "h": 50, "j": 40, "k": 40, "q": 40, "R": 50, "J": 50, "P": 50, "K": 50, "Q": 50, "Y": 50, "G": 50, "Z": 50}
        return sum(weights.get(grid[y][x], 0) for y in range(top, top + height) for x in range(left, left + width))

    def place_corridor_infrastructure(self, grid: List[List[str]], chunk_x: int, chunk_y: int) -> bool:
        if not self.wilderness_chunk_has_corridor_infrastructure(chunk_x, chunk_y):
            return False
        if self.procedural_town_plan(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return False
        record = self.corridor_site_record(chunk_x, chunk_y)
        saved_parcel = list(record.get("parcel", ()) or ())
        saved_doors = list(record.get("doors", ()) or ())
        if int(record.get("version", 0)) >= CORRIDOR_INFRASTRUCTURE_VERSION and saved_doors and all(
            0 <= int(door.get("y", -1)) < len(grid)
            and 0 <= int(door.get("x", -1)) < len(grid[0])
            and grid[int(door["y"])][int(door["x"])] == CORRIDOR_INFRASTRUCTURE_DOOR
            for door in saved_doors
        ):
            return True
        width, height = 58, 25
        if len(saved_parcel) == 4:
            left, top, saved_right, saved_bottom = map(int, saved_parcel)
            width, height = saved_right - left + 1, saved_bottom - top + 1
        else:
            scored = [
                (self._corridor_disruption_score(grid, left, top, width, height), left, top)
                for top in range(3, len(grid) - height - 2)
                for left in range(4, len(grid[0]) - width - 3)
            ]
            if not scored:
                return False
            best = min(score for score, _left, _top in scored)
            candidates = [(left, top) for score, left, top in scored if score <= best + max(8, best // 20)]
            rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 73204)
            left, top = candidates[rng.randrange(len(candidates))]
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
        for x in range(left, right + 1):
            grid[top][x] = grid[bottom][x] = "#"
        for y in range(top, bottom + 1):
            grid[y][left] = grid[y][right] = "#"
        gate_x = left + width // 2
        for x in range(gate_x - 1, gate_x + 2):
            grid[bottom][x] = "|"
        approach_y = min(len(grid) - 1, bottom + 1)
        for y in range(top + 1, approach_y + 1):
            grid[y][gate_x] = ":"
        if not self.connect_wilderness_site_to_regional_road(grid, (gate_x, approach_y), roads):
            for y in range(approach_y, len(grid)):
                grid[y][gate_x] = "="

        profile = CORRIDOR_SITE_TYPES[str(record["type_id"])]
        doors: List[Dict[str, object]] = []
        centers = ((left + 15, top + 6), (right - 13, top + 6))
        for index, spec in enumerate(tuple(profile["buildings"])[:2]):
            building_id, name, interior_type, size = spec
            door_x, door_y, outside_x, outside_y = self.stamp_wilderness_building_exterior(
                grid, centers[index], tuple(size), "south", CORRIDOR_INFRASTRUCTURE_DOOR, ground,
            )
            doors.append({"x": door_x, "y": door_y, "outside_x": outside_x, "outside_y": outside_y, "building_id": building_id, "name": name, "interior_type": interior_type})
            for y in range(outside_y, top + 14):
                grid[y][outside_x] = ":"
            lo, hi = sorted((outside_x, gate_x))
            for x in range(lo, hi + 1):
                grid[top + 13][x] = ":"

        features: List[Dict[str, object]] = []
        self._corridor_feature(features, gate_x - 3, bottom - 1, "directory", str(record["name"]), "n")
        self._corridor_feature(features, gate_x + 4, top + 13, "shift_board", "Production Shift Board", "q")
        self._corridor_feature(features, left + 3, top + 13, "supply_container", "Materials Store", "s", profile="crate")
        self._corridor_feature(features, right - 3, top + 13, "output_container", "Finished Goods Collection", "s", profile="crate")
        self._corridor_feature(features, gate_x + 2, top + 12, "worker", str(record["manager_name"]), "@", role=str(record["manager_role"]))
        self._corridor_feature(features, gate_x - 2, top + 12, "trade_counter", "Staffed Trade Counter", "$")

        yard_left, yard_top, yard_right, yard_bottom = left + 4, top + 15, right - 4, bottom - 3
        for x in range(yard_left, yard_right + 1):
            grid[yard_top][x] = grid[yard_bottom][x] = "#"
        for y in range(yard_top, yard_bottom + 1):
            grid[y][yard_left] = grid[y][yard_right] = "#"
        grid[yard_top][gate_x] = "|"
        stations = tuple(profile["stations"])
        station_xs = (yard_left + 7, gate_x, yard_right - 7)
        station_y = yard_top + 3
        for order, ((kind, name, glyph), x) in enumerate(zip(stations, station_xs)):
            self._corridor_feature(features, x, station_y, kind, name, glyph, order=order)
        # Low, readable support objects reinforce each yard's use without clutter.
        support = {
            "mill": ((yard_left + 3, station_y, "grain_sack", "Stacked Grain Sacks", "g"),),
            "wagon": ((yard_left + 3, station_y, "wheel_rack", "Wheel Rack", "O"), (yard_right - 3, station_y, "wagon", "Delivery Wagon", "W")),
            "textile": ((yard_left + 3, station_y, "fiber_bale", "Fiber Bale", "f"),),
            "stone": ((yard_left + 3, station_y, "stone_stack", "Stone Stack", "o"),),
            "brick": ((yard_left + 3, station_y, "drying_row", "Drying Brick Row", "="),),
            "metal": ((yard_left + 3, station_y, "coal_bin", "Covered Coal Bin", "c"),),
            "fish": ((yard_left + 3, station_y, "barrel", "Salt Barrel", "B"),),
            "trade": ((yard_left + 3, station_y, "freight", "Incoming Freight", "B"), (yard_right - 3, station_y, "wagon", "Freight Wagon", "W")),
        }.get(str(profile["yard"]), ())
        for x, y, kind, name, glyph in support:
            self._corridor_feature(features, x, y, kind, name, glyph)
        for feature in features:
            grid[int(feature["y"])][int(feature["x"])] = str(feature["glyph"])
        self.preserve_wilderness_roads_around_parcel(
            grid, (left, top, right, bottom), original_roads,
            (gate_x, approach_y),
        )
        record.update({"version": CORRIDOR_INFRASTRUCTURE_VERSION, "parcel": [left, top, right, bottom], "gate": [gate_x, bottom], "doors": doors, "features": features})
        return True

    def corridor_site_feature_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness":
            return None
        if not self.wilderness_chunk_has_corridor_infrastructure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((feature for feature in self.corridor_site_record().get("features", ()) if (int(feature.get("x", -1)), int(feature.get("y", -1))) == (int(x), int(y))), None)

    def corridor_site_door_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness":
            return None
        if not self.wilderness_chunk_has_corridor_infrastructure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((door for door in self.corridor_site_record().get("doors", ()) if (int(door.get("x", -1)), int(door.get("y", -1))) == (int(x), int(y))), None)

    def corridor_site_zone_at(self, x: int, y: int) -> str:
        parcel = self.corridor_site_record().get("parcel", ())
        if len(parcel) != 4:
            return ""
        left, top, right, bottom = map(int, parcel)
        if not (left <= int(x) <= right and top <= int(y) <= bottom):
            return ""
        return "production yard" if int(y) >= top + 15 else "service court"

    def enter_corridor_site_building(self, door: Mapping[str, object]) -> bool:
        self.state.current_corridor_site_key = f"{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}"
        self.state.current_corridor_building_id = str(door.get("building_id", "workshop"))
        self.state.corridor_interior_return_x = int(door.get("outside_x", door.get("x", 1)))
        self.state.corridor_interior_return_y = int(door.get("outside_y", door.get("y", 1)))
        self.state.location = CORRIDOR_INFRASTRUCTURE_LOCATION
        grid = self.corridor_site_interior_map()
        self.state.player_x, self.state.player_y = self.wilderness_interior_entry_landing(grid, "south")
        self.state.facing = "UP"
        self.set_message(f"Entered {door.get('name', 'the corridor business')}.")
        return True

    def exit_corridor_site_building(self) -> None:
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        self.state.player_x, self.state.player_y = self.nearest_active_passable_tile(
            int(self.state.corridor_interior_return_x), int(self.state.corridor_interior_return_y),
        )
        self.state.facing = "DOWN"
        self.set_message("Stepped back into the working property.")

    def current_corridor_building(self) -> Dict[str, object]:
        building_id = str(getattr(self.state, "current_corridor_building_id", ""))
        return next((dict(door) for door in self.corridor_site_record().get("doors", ()) if str(door.get("building_id")) == building_id), {})

    def corridor_site_interior_map(self) -> List[List[str]]:
        site_key = str(getattr(self.state, "current_corridor_site_key", self.wilderness_chunk_key()))
        building = self.current_corridor_building()
        building_id = str(building.get("building_id", "workshop"))
        cache_key = (site_key, building_id)
        cache = getattr(self, "_corridor_interior_map_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._corridor_interior_map_cache = cache
        if cache_key in cache:
            return cache[cache_key]
        seed = sum((index + 1) * ord(ch) for index, ch in enumerate(f"{site_key}:{building_id}"))
        rng = random.Random(seed)
        placements: List[Dict[str, object]] = []
        grid = build_procedural_ground_floor(
            str(building.get("interior_type", "workshop")), rng.randrange(4), rng.randrange(12), 1,
            program_variant=rng.randrange(3), furniture_placements=placements,
        )
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        for placement in placements:
            common = {key: placement.get(key) for key in ("name", "collection", "form", "room_id", "room_role", "rotation", "width", "height")}
            for cell in placement.get("cells", ()) or ():
                cell_record = dict(common)
                cell_record.update(cell)
                lookup[(int(cell.get("x", 0)), int(cell.get("y", 0)))] = cell_record
        catalog = getattr(self, "_corridor_interior_catalog_cache", None)
        if not isinstance(catalog, dict):
            catalog = {}
            self._corridor_interior_catalog_cache = catalog
        catalog[cache_key] = lookup
        cache[cache_key] = grid
        return grid

    def corridor_interior_catalog_furniture_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != CORRIDOR_INFRASTRUCTURE_LOCATION:
            return None
        self.corridor_site_interior_map()
        key = (str(self.state.current_corridor_site_key), str(self.state.current_corridor_building_id))
        return getattr(self, "_corridor_interior_catalog_cache", {}).get(key, {}).get((int(x), int(y)))

    def corridor_site_container(self, feature: Mapping[str, object]) -> Dict[str, object]:
        kind = str(feature.get("kind", "supply_container"))
        key = f"corridor:{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}:{feature.get('x')},{feature.get('y')}:{kind}"
        existing = self.state.world_containers.get(key)
        if isinstance(existing, dict):
            return existing
        if kind == "output_container":
            return self.create_container_record(
                key, int(feature["x"]), int(feature["y"]), "crate",
                name=str(feature.get("name", "Finished Goods Collection")), take_policy="player",
                allow_deposit=False, contents={}, owner="player earnings",
            )
        return self.create_container_record(
            key, int(feature["x"]), int(feature["y"]), "crate",
            name=str(feature.get("name", "Materials Store")), take_policy="display",
            allow_deposit=False, owner=str(self.corridor_site_record().get("name", "the business")),
        )

    def corridor_trade_menu(self) -> None:
        record = self.corridor_site_record()
        profile = CORRIDOR_SITE_TYPES[str(record["type_id"])]
        while True:
            entries = [
                MenuItem(label=f"Buy {item}", value=(item, int(price)), enabled=int(self.state.money) >= int(price), hint=f"{price}g each | stocked by {profile['name']}")
                for item, price in tuple(profile.get("stock", ()))
            ]
            entries.append(MenuItem(label="Leave the counter", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(str(profile["name"]), entries, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                self.set_message("You step away from the staffed trade counter.")
                return
            item, price = choice.value
            max_qty = int(self.state.money) // int(price)
            quantity = self.vertical_quantity_select(
                "Purchase Goods", str(item), int(price), max_qty=max_qty,
                start_qty=min(5, max_qty), panel_width=LEFT_PANEL_WIDTH,
                panel_height=LEFT_PANEL_HEIGHT, return_back=True,
            )
            if quantity in {None, MENU_BACK} or int(quantity) <= 0:
                continue
            quantity = int(quantity)
            total = quantity * int(price)
            self.state.money -= total
            add_inventory_items(self.state.inventory, {str(item): quantity})
            self.autosave_with_message(f"Bought {quantity_item_phrase(item, quantity)} for {total}g at {record['name']}.")
            return

    def corridor_work_station_features(self) -> List[Dict[str, object]]:
        return sorted(
            (dict(feature) for feature in self.corridor_site_record().get("features", ()) if "order" in feature),
            key=lambda feature: int(feature.get("order", 0)),
        )

    def start_corridor_production_shift(self) -> bool:
        record = self.corridor_site_record()
        week = self.stronghold_cache_week_key()
        if record.get("production_week") == week:
            self.set_message("This property's production shift is already complete for the week.")
            return False
        if record.get("shift_active") and record.get("shift_week") == week:
            stations = self.corridor_work_station_features()
            index = int(record.get("shift_station_index", 0))
            next_name = stations[index]["name"] if index < len(stations) else "the final station"
            self.set_message(f"Your shift is underway. Next: {next_name}.")
            return False
        record["shift_active"] = True
        record["shift_week"] = week
        record["shift_station_index"] = 0
        first = self.corridor_work_station_features()[0]
        self.set_message(f"Shift started. Work the yard in order, beginning with {first['name']}.")
        return True

    def register_corridor_production_station(self, feature: Mapping[str, object]) -> bool:
        record = self.corridor_site_record()
        week = self.stronghold_cache_week_key()
        if not record.get("shift_active") or record.get("shift_week") != week:
            return False
        stations = self.corridor_work_station_features()
        index = int(record.get("shift_station_index", 0))
        if index >= len(stations):
            return False
        expected = stations[index]
        if (int(feature.get("x", -1)), int(feature.get("y", -1))) != (int(expected["x"]), int(expected["y"])):
            if "order" in feature:
                self.set_message(f"The production line is out of order. Next use {expected['name']}.")
                return True
            return False
        if not self.spend_stamina(2):
            return True
        self.advance_time(10)
        index += 1
        record["shift_station_index"] = index
        if index < len(stations):
            self.set_message(f"Station complete. Next use {stations[index]['name']}.")
            return True
        profile = CORRIDOR_SITE_TYPES[str(record["type_id"])]
        output_feature = next(feature for feature in record.get("features", ()) if feature.get("kind") == "output_container")
        container = self.corridor_site_container(output_feature)
        contents = container.setdefault("contents", {})
        product = str(profile["product"])
        quantity = int(profile.get("product_qty", 1))
        contents[product] = int(contents.get(product, 0)) + quantity
        wage = int(profile.get("wage", 80))
        self.state.money += wage
        record["production_week"] = week
        record["shift_active"] = False
        record["production_shifts"] = int(record.get("production_shifts", 0)) + 1
        self.add_wilderness_region_vitality(
            self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 2,
            f"completed a shift at {record['name']}",
        )
        self.autosave_with_message(
            f"Shift complete: +{wage}g. {quantity_item_phrase(product, quantity)} placed in Finished Goods Collection."
        )
        return True

    def use_corridor_site_feature(self, feature: Mapping[str, object]) -> bool:
        kind = str(feature.get("kind", ""))
        record = self.corridor_site_record()
        if self.register_corridor_production_station(feature):
            return True
        if kind == "directory":
            profile = CORRIDOR_SITE_TYPES[str(record["type_id"])]
            buildings = [str(door.get("name")) for door in record.get("doors", ())]
            stations = [str(station.get("name")) for station in self.corridor_work_station_features()]
            self.vertical_panel_view(
                str(record["name"]),
                [str(record["name"]).upper(), "", str(profile["description"]), "", "Buildings:", *[f"- {name}" for name in buildings], "", "Production line:", *[f"{index + 1}. {name}" for index, name in enumerate(stations)], "", f"Finished product: {profile['product']}", "Use the shift board, then operate each physical station in order."],
                LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT,
            )
            return True
        if kind == "shift_board":
            self.start_corridor_production_shift()
            return True
        if kind in {"supply_container", "output_container"}:
            self.show_world_container(self.corridor_site_container(feature))
            return True
        if kind == "trade_counter":
            self.corridor_trade_menu()
            return True
        if kind == "worker":
            npc = {
                "id": f"corridor:{self.state.wilderness_chunk_x}:{self.state.wilderness_chunk_y}:manager",
                "name": str(feature.get("name", record.get("manager_name", "Manager"))),
                "role": str(feature.get("role", record.get("manager_role", "Manager"))),
                "activity": f"managing production at {record['name']}",
                "origin": str(record["name"]),
                "bond": int(record.get("manager_bond", 0)),
                "conversations": int(record.get("manager_conversations", 0)),
            }
            result = self.run_unified_npc_conversation(
                npc, kind="road worker", first_meeting=npc["conversations"] <= 0,
                agenda_override=f"I manage {record['name']}. We receive raw materials, work the production line, and send finished goods along the road.",
            )
            if result.get("completed") or result.get("transcript"):
                record["manager_conversations"] = npc["conversations"] + 1
                record["manager_bond"] = npc["bond"] + 1
            return True
        if "order" in feature:
            self.set_message("Start a production shift at the shift board before using this station.")
            return True
        support_messages = {
            "grain_sack": "Incoming grain is kept dry beside the receiving hopper.",
            "wheel_rack": "Finished wheels are sorted by diameter for repair and new assembly.",
            "wagon": "A working freight wagon connects this property to nearby settlements.",
            "fiber_bale": "Clean fiber bales wait for carding and weaving.",
            "stone_stack": "Raw stone is spaced for safe lifting and inspection.",
            "drying_row": "Freshly molded bricks dry here before firing.",
            "coal_bin": "A covered coal supply keeps the forge operating in bad weather.",
            "barrel": "Salt and clean packing supplies are stored in this sealed barrel.",
            "freight": "Labeled regional freight awaits weighing and dispatch.",
        }
        if kind in support_messages:
            self.set_message(support_messages[kind])
            return True
        return False

    def corridor_site_description_at(self, x: int, y: int) -> str:
        if not self.wilderness_chunk_has_corridor_infrastructure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return ""
        door = self.corridor_site_door_at(x, y)
        if door:
            return f"Door to {door.get('name', 'a working building')}: walk into it to enter"
        feature = self.corridor_site_feature_at(x, y)
        if feature:
            actions = {
                "directory": "review the complete property", "shift_board": "start or review a production shift",
                "supply_container": "inspect display materials", "output_container": "collect earned finished goods",
                "trade_counter": "buy locally produced goods", "worker": "talk to the manager",
            }
            action = actions.get(str(feature.get("kind")), "operate this production station" if "order" in feature else "inspect this working fixture")
            return f"{feature.get('name', 'Working facility')}: {action}"
        zone = self.corridor_site_zone_at(x, y)
        return f"{self.corridor_site_record().get('name', 'Corridor business')} {zone}" if zone else ""

    def use_corridor_interior_service(self, tile: str) -> bool:
        building = self.current_corridor_building()
        interior_type = str(building.get("interior_type", "workshop"))
        if tile == "$" and interior_type == "general_store":
            self.corridor_trade_menu()
            return True
        if tile == "&":
            record = self.corridor_site_record()
            return self.use_corridor_site_feature({"kind": "worker", "name": record.get("manager_name"), "role": record.get("manager_role")})
        if tile in {"x", "w", "a", "$"} and interior_type in {"workshop", "carpenter"}:
            self.safe_menu(self.show_crafting_menu, "Workshop closed.")
            return True
        return False

    def use_corridor_interior_action(self, x: int, y: int) -> bool:
        tile = self.active_map()[y][x]
        if tile == "D":
            self.exit_corridor_site_building()
            return True
        if tile == "_":
            self.active_map()[y][x] = "|"
            self.set_message("Opened the room door.")
            return True
        if tile == "|":
            self.active_map()[y][x] = "_"
            self.set_message("Closed the room door.")
            return True
        if self.use_corridor_interior_service(tile):
            return True
        if self.use_catalog_furniture_action_at(x, y):
            return True
        self.set_message("Nothing here needs direct interaction. Press I to inspect it.")
        return False


__all__ = [
    "CORRIDOR_INFRASTRUCTURE_DOOR", "CORRIDOR_INFRASTRUCTURE_LOCATION",
    "CORRIDOR_INFRASTRUCTURE_VERSION", "CORRIDOR_SITE_TYPES",
    "CorridorInfrastructureMixin",
]
