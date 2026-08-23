"""Small civic settlements embedded in the seamless wilderness road network."""

from __future__ import annotations

import random
from typing import Dict, List, Mapping, Optional, Tuple

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK
from ascii_farmstead_helpers import quantity_agreement, quantity_item_phrase
from ascii_farmstead_inventory import add_inventory_items
from ascii_farmstead_procedural_interiors import build_procedural_ground_floor
from ascii_farmstead_ui import MenuItem


ROUTE_HAMLET_VERSION = 2
ROUTE_HAMLET_LOCATION = "RouteHamletInterior"
ROUTE_HAMLET_DOOR = "d"
NO_HAMLET = (10**8, 10**8)


ROUTE_HAMLET_TYPES: Dict[str, Dict[str, object]] = {
    "crossroads": {
        "title": "Crossroads Hamlet", "description": "A compact road settlement centered on trade, lodging, health, and local administration.",
        "buildings": (("store", "Crossroads General Store", "general_store", "Shopkeeper"), ("inn", "Travelers' Inn", "inn", "Innkeeper"), ("clinic", "Road Clinic", "clinic", "Doctor"), ("hall", "Hamlet Hall", "town_hall", "Clerk"), ("home_a", "North Household", "home", "Resident"), ("home_b", "South Household", "home", "Resident")),
        "stock": (("Field Snack", 35), ("Wood", 12), ("Stone", 10), ("Trade Parcel", 145)),
    },
    "woodland": {
        "title": "Woodland Village", "description": "A sheltered timber village with a carpenter, inn, clinic, schoolhouse, and family homes.",
        "buildings": (("carpenter", "Village Carpenter", "carpenter", "Carpenter"), ("inn", "Woodland Inn", "inn", "Innkeeper"), ("clinic", "Woodland Clinic", "clinic", "Doctor"), ("school", "Village Schoolhouse", "library", "Teacher"), ("home_a", "Forester Household", "home", "Forester"), ("home_b", "Craft Household", "home", "Resident")),
        "stock": (("Wood", 10), ("Hardwood", 32), ("Wagon Parts", 125), ("Field Snack", 35)),
    },
    "farming": {
        "title": "Fieldside Village", "description": "A farming village with produce trade, a public house, clinic, schoolhouse, and occupied homes.",
        "buildings": (("market", "Fieldside Market", "general_store", "Grocer"), ("inn", "Fieldside Public House", "inn", "Innkeeper"), ("clinic", "Fieldside Clinic", "clinic", "Doctor"), ("school", "Fieldside Schoolhouse", "library", "Teacher"), ("home_a", "Farm Family Home", "home", "Farmer"), ("home_b", "Village Household", "home", "Resident")),
        "stock": (("Flour Sack", 75), ("Animal Feed", 12), ("Mixed Seeds", 8), ("Field Snack", 35)),
    },
    "mining": {
        "title": "Stonefoot Village", "description": "A durable work village supporting quarry crews, metalworkers, travelers, and their households.",
        "buildings": (("works", "Stonefoot Workshop", "workshop", "Smith"), ("store", "Stonefoot Supply Store", "general_store", "Shopkeeper"), ("clinic", "Stonefoot Clinic", "clinic", "Doctor"), ("sheriff", "Stonefoot Sheriff Post", "sheriff_office", "Sheriff"), ("home_a", "Quarry Household", "home", "Quarry Worker"), ("home_b", "Smith Household", "home", "Resident")),
        "stock": (("Cut Stone", 60), ("Coal", 20), ("Metal Fittings", 180), ("Field Snack", 35)),
    },
    "coastal": {
        "title": "Shoreline Village", "description": "A salt-air village with a chandlery, boarding house, clinic, schoolhouse, and fishing households.",
        "buildings": (("chandlery", "Village Chandlery", "general_store", "Chandler"), ("inn", "Shoreline Boarding House", "inn", "Innkeeper"), ("clinic", "Shoreline Clinic", "clinic", "Doctor"), ("school", "Shoreline Schoolhouse", "library", "Teacher"), ("home_a", "Fishing Household", "home", "Fisher"), ("home_b", "Boat Family Home", "home", "Resident")),
        "stock": (("Smoked Fish", 105), ("Marsh Reed", 18), ("Fiber", 4), ("Explorer Raft", 290)),
    },
    "highland": {
        "title": "Highland Hamlet", "description": "A weather-hardened hill settlement with supplies, lodging, medicine, public safety, and occupied homes.",
        "buildings": (("store", "Highland Supply", "general_store", "Shopkeeper"), ("inn", "Highland Wayhouse", "inn", "Innkeeper"), ("clinic", "Highland Clinic", "clinic", "Doctor"), ("sheriff", "Highland Sheriff Post", "sheriff_office", "Sheriff"), ("home_a", "Hill Household", "home", "Prospector"), ("home_b", "Village Household", "home", "Resident")),
        "stock": (("Stone", 10), ("Coal", 20), ("Cloth Bolt", 105), ("Field Snack", 35)),
    },
}


HAMLET_GIVEN_NAMES = ("Avery", "Bennett", "Clara", "Della", "Emery", "Felix", "Greta", "Hollis", "Iris", "Jonas", "Keira", "Linden", "Mara", "Nolan", "Orla", "Perry", "Quinn", "Rosa", "Silas", "Tessa")
HAMLET_SURNAMES = ("Abbott", "Barlow", "Calder", "Dawes", "Ellis", "Fenwick", "Grove", "Hale", "Irwin", "Jarrett", "Keene", "Larkin", "Morrow", "North", "Orton", "Pike", "Reeve", "Sutton", "Thorne", "Vale")
HAMLET_NAME_PREFIXES = ("Ash", "Brook", "Cedar", "Dun", "Elm", "Fair", "Glen", "Hazel", "Juniper", "Kestrel", "Lark", "Moss", "Oak", "Pine", "Reed", "Stone", "Willow")
HAMLET_NAME_SUFFIXES = ("bridge", "cross", "field", "ford", "gate", "hollow", "mere", "ridge", "stead", "wick")


class RouteHamletMixin:
    """Allocation, architecture, services, and scheduled residents for hamlets."""

    def route_hamlet_region_site_chunk(self, chunk_x: int, chunk_y: int) -> Tuple[int, int]:
        anchor = self.wilderness_region_coords(chunk_x, chunk_y)
        cache = getattr(self, "_route_hamlet_site_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._route_hamlet_site_cache = cache
        settlement_keys = tuple(sorted(str(key) for key in (getattr(self.state, "wilderness_settlements", {}) or {})))
        claim_keys = tuple(sorted(str(key) for key in (getattr(self.state, "owned_wilderness_claims", {}) or {})))
        key = (int(self.state.wilderness_seed), int(getattr(self.state, "wilderness_generation_version", 0) or 0), int(anchor[0]), int(anchor[1]), settlement_keys, claim_keys)
        if key in cache:
            return tuple(cache[key])
        if anchor == self.wilderness_region_coords(0, 0):
            cache[key] = NO_HAMLET
            return NO_HAMLET
        has_saved_town = any(
            self.wilderness_region_coords(int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))) == anchor
            for plan in (getattr(self.state, "wilderness_settlements", {}) or {}).values()
            if isinstance(plan, dict)
        )
        if has_saved_town or self.wilderness_hash01(anchor[0], anchor[1], 33000) < 0.17:
            cache[key] = NO_HAMLET
            return NO_HAMLET
        if self.wilderness_hash01(anchor[0], anchor[1], 84100) >= 0.12:
            cache[key] = NO_HAMLET
            return NO_HAMLET
        excluded = {
            tuple(self.wilderness_region_structure_chunk(*anchor)), tuple(self.wilderness_region_outpost_chunk(*anchor)),
            tuple(self.rural_region_site_chunk(*anchor)), tuple(self.corridor_region_site_chunk(*anchor)),
        }
        candidates = []
        for cx, cy in self.wilderness_region_chunks(*anchor):
            point = (int(cx), int(cy))
            if point in excluded or self.home_world_chunk_is_authored(cx, cy):
                continue
            if self.procedural_town_plan(cx, cy) or self.wilderness_chunk_has_stronghold(cx, cy):
                continue
            if self.wilderness_chunk_has_dungeon_site(cx, cy) or self.is_claimable_wilderness_chunk(cx, cy) or self.owned_wilderness_claim(cx, cy):
                continue
            candidates.append(point)
        result = NO_HAMLET if not candidates else candidates[random.Random(self.wilderness_chunk_seed(*anchor) + 84101).randrange(len(candidates))]
        cache[key] = result
        return result

    def wilderness_chunk_has_route_hamlet(self, chunk_x: int, chunk_y: int) -> bool:
        return (int(chunk_x), int(chunk_y)) == self.route_hamlet_region_site_chunk(chunk_x, chunk_y)

    def route_hamlet_type(self, chunk_x: int, chunk_y: int) -> str:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        biome_id, biome = str(profile.get("biome_id", "")), str(profile.get("biome", ";"))
        if biome == "[" or biome_id in {"tidal_flat", "mangrove", "tropical_isle"}:
            return "coastal"
        if biome_id in {"rocky_valley", "badlands", "alpine_meadow", "glacier"}:
            return "mining" if self.wilderness_hash01(chunk_x, chunk_y, 84102) < 0.55 else "highland"
        if biome_id in {"pine_forest", "old_growth", "birch_grove", "taiga"}:
            return "woodland"
        if biome_id in {"prairie", "floodplain", "wet_meadow", "meadow"} or biome == ";":
            return "farming"
        return "crossroads"

    def route_hamlet_name(self, chunk_x: int, chunk_y: int) -> str:
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 84103)
        return f"{rng.choice(HAMLET_NAME_PREFIXES)}{rng.choice(HAMLET_NAME_SUFFIXES)}"

    def route_hamlet_record(self, chunk_x: Optional[int] = None, chunk_y: Optional[int] = None) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        self.ensure_wilderness_poi_state()
        type_id = self.route_hamlet_type(cx, cy)
        record = self.state.wilderness_poi_state.setdefault(f"hamlet:{cx},{cy}", {})
        record.setdefault("kind", "route_hamlet")
        record.setdefault("type_id", type_id)
        record.setdefault("name", self.route_hamlet_name(cx, cy))
        record.setdefault("version", 0)
        return record

    @staticmethod
    def _hamlet_feature(features: List[Dict[str, object]], x: int, y: int, kind: str, name: str, glyph: str, **extra: object) -> None:
        features.append({"x": int(x), "y": int(y), "kind": str(kind), "name": str(name), "glyph": str(glyph)[:1], **extra})

    @staticmethod
    def _hamlet_disruption_score(grid: List[List[str]], left: int, top: int, width: int, height: int) -> int:
        weights = {"~": 14, "=": 7, ":": 4, "#": 5, "S": 100, "X": 100, "!": 100, "A": 70, "E": 70, "h": 50, "j": 40, "k": 40, "q": 40, "R": 50, "J": 50, "P": 50, "K": 50, "Q": 50, "Y": 50, "G": 50, "Z": 50}
        return sum(weights.get(grid[y][x], 0) for y in range(top, top + height) for x in range(left, left + width))

    def place_route_hamlet(self, grid: List[List[str]], chunk_x: int, chunk_y: int) -> bool:
        if not self.wilderness_chunk_has_route_hamlet(chunk_x, chunk_y):
            return False
        if self.procedural_town_plan(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return False
        record = self.route_hamlet_record(chunk_x, chunk_y)
        saved_doors = list(record.get("doors", ()) or ())
        if int(record.get("version", 0)) >= ROUTE_HAMLET_VERSION and saved_doors and all(
            0 <= int(door.get("y", -1)) < len(grid) and 0 <= int(door.get("x", -1)) < len(grid[0])
            and grid[int(door["y"])][int(door["x"])] == ROUTE_HAMLET_DOOR for door in saved_doors
        ):
            return True
        width, height = 74, 32
        saved_parcel = list(record.get("parcel", ()) or ())
        if len(saved_parcel) == 4:
            left, top, old_right, old_bottom = map(int, saved_parcel)
            width, height = old_right - left + 1, old_bottom - top + 1
        else:
            scored = [(self._hamlet_disruption_score(grid, left, top, width, height), left, top) for top in range(2, len(grid) - height - 1) for left in range(3, len(grid[0]) - width - 2)]
            if not scored:
                return False
            best = min(score for score, _left, _top in scored)
            choices = [(left, top) for score, left, top in scored if score <= best + max(10, best // 20)]
            left, top = choices[random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 84104).randrange(len(choices))]
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
        center_x, street_y = left + width // 2, top + height // 2
        for x in range(left, right + 1):
            grid[top][x] = grid[bottom][x] = "#"
        for y in range(top, bottom + 1):
            grid[y][left] = grid[y][right] = "#"
        for y in range(top + 1, bottom):
            grid[y][center_x] = ":"
        for x in range(left + 1, right):
            grid[street_y][x] = ":"
        for x in range(center_x - 1, center_x + 2):
            grid[top][x] = grid[bottom][x] = "|"
        if not self.connect_wilderness_site_to_regional_road(grid, (center_x, bottom + 1), roads):
            for y in range(bottom + 1, len(grid)):
                grid[y][center_x] = "="
        profile = ROUTE_HAMLET_TYPES[str(record["type_id"])]
        centers = ((left + 12, top + 6), (center_x, top + 6), (right - 12, top + 6), (left + 12, bottom - 6), (center_x, bottom - 6), (right - 12, bottom - 6))
        doors: List[Dict[str, object]] = []
        for index, (building_id, name, interior_type, role) in enumerate(tuple(profile["buildings"])):
            side = "south" if index < 3 else "north"
            size = (17, 9) if interior_type != "town_hall" else (19, 9)
            door_x, door_y, outside_x, outside_y = self.stamp_wilderness_building_exterior(grid, centers[index], size, side, ROUTE_HAMLET_DOOR, ground)
            doors.append({"x": door_x, "y": door_y, "outside_x": outside_x, "outside_y": outside_y, "side": side, "building_id": building_id, "name": name, "interior_type": interior_type, "role": role})
            for y in range(min(outside_y, street_y), max(outside_y, street_y) + 1):
                grid[y][outside_x] = ":"
        features: List[Dict[str, object]] = []
        self._hamlet_feature(features, center_x - 4, street_y - 1, "directory", f"{record['name']} Directory", "n")
        self._hamlet_feature(features, center_x + 4, street_y - 1, "notice_board", "Community Notice Board", "N")
        self._hamlet_feature(features, center_x, street_y - 3, "well", "Village Well", "O")
        self._hamlet_feature(features, center_x - 7, street_y + 1, "bench", "Public Bench", "b")
        self._hamlet_feature(features, center_x + 7, street_y + 1, "bench", "Public Bench", "b")
        self._hamlet_feature(features, left + 3, street_y, "market_stall", "Weekly Produce Stall", "m")
        self._hamlet_feature(features, right - 3, street_y, "parcel_locker", "Public Parcel Locker", "s", profile="crate")
        for feature in features:
            grid[int(feature["y"])][int(feature["x"])] = str(feature["glyph"])
        self.preserve_wilderness_roads_around_parcel(
            grid, (left, top, right, bottom), original_roads,
            (center_x, bottom + 1),
        )
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 84105)
        residents = []
        home_ids = [door["building_id"] for door in doors if door["interior_type"] == "home"]
        for index, door in enumerate(doors):
            residents.append({
                "id": f"hamlet:{chunk_x},{chunk_y}:resident:{index}",
                "name": f"{rng.choice(HAMLET_GIVEN_NAMES)} {rng.choice(HAMLET_SURNAMES)}",
                "role": str(door["role"]), "work_building_id": str(door["building_id"]),
                "home_building_id": str(home_ids[index % len(home_ids)]), "bond": 0, "conversations": 0,
            })
        record.update({"version": ROUTE_HAMLET_VERSION, "parcel": [left, top, right, bottom], "gate": [center_x, bottom], "doors": doors, "features": features, "residents": residents, "plaza": [center_x, street_y]})
        return True

    def route_hamlet_feature_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_hamlet(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((feature for feature in self.route_hamlet_record().get("features", ()) if (int(feature.get("x", -1)), int(feature.get("y", -1))) == (int(x), int(y))), None)

    def route_hamlet_door_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_hamlet(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((door for door in self.route_hamlet_record().get("doors", ()) if (int(door.get("x", -1)), int(door.get("y", -1))) == (int(x), int(y))), None)

    def route_hamlet_resident_position(self, resident: Mapping[str, object], chunk_x: Optional[int] = None, chunk_y: Optional[int] = None) -> Tuple[int, int, str]:
        record = self.route_hamlet_record(chunk_x, chunk_y)
        doors = {str(door.get("building_id")): door for door in record.get("doors", ())}
        hour = int(getattr(self.state, "hour", 8))
        index = int(str(resident.get("id", "0")).rsplit(":", 1)[-1] or 0)
        if 8 <= hour < 12 or 13 <= hour < 18:
            door = doors.get(str(resident.get("work_building_id")), {})
            activity = f"working at {door.get('name', 'a village building')}"
            return int(door.get("outside_x", 1)), int(door.get("outside_y", 1)), activity
        if hour == 12 or 18 <= hour < 20:
            plaza_x, plaza_y = map(int, record.get("plaza", (43, 19)))
            offsets = ((-6, 1), (-3, 2), (3, 2), (6, 1), (-8, -1), (8, -1))
            dx, dy = offsets[index % len(offsets)]
            return plaza_x + dx, plaza_y + dy, "spending time in the village square"
        door = doors.get(str(resident.get("home_building_id")), {})
        return int(door.get("outside_x", 1)) + (index % 3) - 1, int(door.get("outside_y", 1)), "at home for the day"

    def route_hamlet_resident_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_hamlet(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        record = self.route_hamlet_record()
        for resident in record.get("residents", ()):
            rx, ry, activity = self.route_hamlet_resident_position(resident)
            if (rx, ry) == (int(x), int(y)):
                result = dict(resident)
                result.update({"x": rx, "y": ry, "activity": activity})
                return result
        return None

    def talk_to_route_hamlet_resident(self, resident: Mapping[str, object]) -> bool:
        record = self.route_hamlet_record()
        stored = next((row for row in record.get("residents", ()) if str(row.get("id")) == str(resident.get("id"))), None)
        if not isinstance(stored, dict):
            return False
        actor = {
            "id": str(stored["id"]), "name": str(stored["name"]), "role": str(stored["role"]),
            "activity": str(resident.get("activity", "going about village life")), "origin": str(record["name"]),
            "bond": int(stored.get("bond", 0)), "conversations": int(stored.get("conversations", 0)),
        }
        result = self.run_unified_npc_conversation(
            actor, kind="hamlet resident", first_meeting=actor["conversations"] <= 0,
            agenda_override=f"I live in {record['name']} and spend my days {actor['activity']}. The road, households, and public buildings keep this place connected.",
        )
        if result.get("completed") or result.get("transcript"):
            stored["conversations"] = actor["conversations"] + 1
            stored["bond"] = actor["bond"] + 1
        return True

    def enter_route_hamlet_building(self, door: Mapping[str, object]) -> bool:
        self.state.current_hamlet_site_key = f"{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}"
        self.state.current_hamlet_building_id = str(door.get("building_id", "store"))
        self.state.hamlet_interior_return_x = int(door.get("outside_x", door.get("x", 1)))
        self.state.hamlet_interior_return_y = int(door.get("outside_y", door.get("y", 1)))
        self.state.location = ROUTE_HAMLET_LOCATION
        grid = self.route_hamlet_interior_map()
        self.state.player_x, self.state.player_y = self.wilderness_interior_entry_landing(grid, str(door.get("side", "south")))
        self.state.facing = "UP" if door.get("side") == "south" else "DOWN"
        self.set_message(f"Entered {door.get('name', 'the village building')}.")
        return True

    def exit_route_hamlet_building(self) -> None:
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        self.state.player_x, self.state.player_y = self.nearest_active_passable_tile(int(self.state.hamlet_interior_return_x), int(self.state.hamlet_interior_return_y))
        self.set_message("Stepped back onto the village street.")

    def current_route_hamlet_building(self) -> Dict[str, object]:
        building_id = str(getattr(self.state, "current_hamlet_building_id", ""))
        return next((dict(door) for door in self.route_hamlet_record().get("doors", ()) if str(door.get("building_id")) == building_id), {})

    def route_hamlet_interior_map(self) -> List[List[str]]:
        site_key = str(getattr(self.state, "current_hamlet_site_key", self.wilderness_chunk_key()))
        building = self.current_route_hamlet_building()
        building_id = str(building.get("building_id", "store"))
        cache_key = (site_key, building_id)
        cache = getattr(self, "_route_hamlet_interior_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._route_hamlet_interior_cache = cache
        if cache_key in cache:
            return cache[cache_key]
        seed = sum((index + 1) * ord(ch) for index, ch in enumerate(f"{site_key}:{building_id}"))
        rng = random.Random(seed)
        placements: List[Dict[str, object]] = []
        raw_grid = build_procedural_ground_floor(str(building.get("interior_type", "home")), rng.randrange(4), rng.randrange(12), 1, program_variant=rng.randrange(3), furniture_placements=placements)
        side = str(building.get("side", "south"))
        grid = self.orient_south_door_interior(raw_grid, side)
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        for placement in placements:
            common = {key: placement.get(key) for key in ("name", "collection", "form", "room_id", "room_role", "rotation", "width", "height")}
            for cell in placement.get("cells", ()) or ():
                item = dict(common); item.update(cell)
                cell_x, cell_y = int(cell.get("x", 0)), int(cell.get("y", 0))
                if side == "north":
                    cell_y = len(raw_grid) - 1 - cell_y
                lookup[(cell_x, cell_y)] = item
        catalog = getattr(self, "_route_hamlet_catalog_cache", None)
        if not isinstance(catalog, dict):
            catalog = {}
            self._route_hamlet_catalog_cache = catalog
        catalog[cache_key] = lookup
        cache[cache_key] = grid
        return grid

    def route_hamlet_catalog_furniture_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != ROUTE_HAMLET_LOCATION:
            return None
        self.route_hamlet_interior_map()
        key = (str(self.state.current_hamlet_site_key), str(self.state.current_hamlet_building_id))
        return getattr(self, "_route_hamlet_catalog_cache", {}).get(key, {}).get((int(x), int(y)))

    def route_hamlet_container(self, feature: Mapping[str, object]) -> Dict[str, object]:
        key = f"hamlet:{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}:{feature.get('x')},{feature.get('y')}:parcel"
        existing = self.state.world_containers.get(key)
        if isinstance(existing, dict):
            return existing
        return self.create_container_record(key, int(feature["x"]), int(feature["y"]), "crate", name=str(feature.get("name", "Public Parcel Locker")), take_policy="player", allow_deposit=True, contents={})

    def route_hamlet_shop_menu(self) -> None:
        record = self.route_hamlet_record()
        profile = ROUTE_HAMLET_TYPES[str(record["type_id"])]
        entries = [MenuItem(label=f"Buy {item}", value=(item, int(price)), enabled=int(self.state.money) >= int(price), hint=f"{price}g each") for item, price in profile.get("stock", ())]
        entries.append(MenuItem(label="Leave the counter", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(f"{record['name']} Shop", entries, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if not choice or choice.value == MENU_BACK:
            self.set_message("You step away from the village counter.")
            return
        item, price = choice.value
        maximum = int(self.state.money) // int(price)
        quantity = self.vertical_quantity_select("Village Purchase", str(item), int(price), max_qty=maximum, start_qty=min(5, maximum), panel_width=LEFT_PANEL_WIDTH, panel_height=LEFT_PANEL_HEIGHT, return_back=True)
        if quantity in {None, MENU_BACK} or int(quantity) <= 0:
            return
        quantity = int(quantity); total = quantity * int(price)
        self.state.money -= total
        add_inventory_items(self.state.inventory, {str(item): quantity})
        self.autosave_with_message(f"Bought {quantity_item_phrase(item, quantity)} in {record['name']} for {total}g.")

    def route_hamlet_inn_menu(self) -> None:
        items = [
            MenuItem(label="Buy a hot meal - 45g", value="meal", enabled=self.state.money >= 45, hint="Recover 24 stamina; 20 minutes"),
            MenuItem(label="Rest in a private room - 90g", value="room", enabled=self.state.money >= 90, hint="Recover 55 stamina and 20% health; 90 minutes"),
            MenuItem(label="Leave", value=MENU_BACK, enabled=True),
        ]
        choice = self.vertical_panel_select("Village Inn", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if not choice or choice.value == MENU_BACK:
            return
        if choice.value == "meal":
            self.state.money -= 45; restored = self.restore_stamina(24); self.advance_time(20)
            self.autosave_with_message(f"Ate a hot village meal. Stamina +{restored}.")
        else:
            self.state.money -= 90; stamina = self.restore_stamina(55)
            maximum = int(getattr(self.state, "combat_max_hp", 1)); before = int(getattr(self.state, "combat_current_hp", maximum))
            self.state.combat_current_hp = min(maximum, before + max(1, maximum // 5)); self.advance_time(90)
            self.autosave_with_message(f"Rested in a private room. Stamina +{stamina}, health +{self.state.combat_current_hp - before}.")

    def route_hamlet_clinic_menu(self) -> None:
        maximum = int(getattr(self.state, "combat_max_hp", 1)); current = int(getattr(self.state, "combat_current_hp", maximum))
        items = [
            MenuItem(label="Basic treatment - 70g", value="basic", enabled=self.state.money >= 70 and current < maximum, hint="Recover one third of maximum health"),
            MenuItem(label="Full treatment - 150g", value="full", enabled=self.state.money >= 150 and current < maximum, hint="Restore health completely"),
            MenuItem(label="Buy Animal Medicine - 120g", value="medicine", enabled=self.state.money >= 120, hint="One bottle"),
            MenuItem(label="Leave", value=MENU_BACK, enabled=True),
        ]
        choice = self.vertical_panel_select("Village Clinic", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if not choice or choice.value == MENU_BACK:
            return
        if choice.value == "medicine":
            self.state.money -= 120; add_inventory_items(self.state.inventory, {"Animal Medicine": 1}); self.autosave_with_message("Bought 1 Animal Medicine."); return
        cost = 70 if choice.value == "basic" else 150
        self.state.money -= cost
        healed = maximum - current if choice.value == "full" else min(maximum - current, max(8, maximum // 3))
        self.state.combat_current_hp = current + healed; self.advance_time(25 if choice.value == "basic" else 50)
        self.autosave_with_message(f"Received village medical treatment. Health +{healed}.")

    def route_hamlet_schoolhouse_menu(self) -> None:
        record = self.route_hamlet_record()
        day = self.errand_day_key()
        items = [
            MenuItem(label="Read regional histories", value="history", enabled=record.get("study_day") != day, hint="Map one nearby unknown chunk; 35 minutes"),
            MenuItem(label="Study a practical handbook", value="handbook", enabled=record.get("study_day") != day, hint="Receive a useful field supply; 35 minutes"),
            MenuItem(label="Review the village register", value="register", enabled=True, hint="Residents, roles, buildings, and roads"),
            MenuItem(label="Leave", value=MENU_BACK, enabled=True),
        ]
        choice = self.vertical_panel_select("Village Schoolhouse", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if not choice or choice.value == MENU_BACK:
            return
        if choice.value == "register":
            self.vertical_panel_view("Village Register", self.route_hamlet_directory_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT); return
        record["study_day"] = day; self.advance_time(35)
        if choice.value == "history":
            mapped = self.map_nearby_wilderness_chunks(1)
            self.autosave_with_message(
                f"Studied regional histories and mapped {quantity_agreement(mapped, 'nearby area')}."
            )
        else:
            item = {"coastal": "Marsh Reed", "mining": "Coal", "highland": "Fiber", "woodland": "Wood"}.get(str(record["type_id"]), "Field Snack")
            add_inventory_items(self.state.inventory, {item: 1})
            self.autosave_with_message(f"Studied a practical handbook and prepared 1 {item} for field use.")

    def route_hamlet_public_service(self, interior_type: str) -> bool:
        if interior_type == "general_store":
            self.route_hamlet_shop_menu(); return True
        if interior_type == "inn":
            self.route_hamlet_inn_menu(); return True
        if interior_type == "clinic":
            self.route_hamlet_clinic_menu(); return True
        if interior_type == "library":
            self.route_hamlet_schoolhouse_menu(); return True
        if interior_type in {"workshop", "carpenter"}:
            self.safe_menu(self.show_crafting_menu, "Village workshop closed."); return True
        if interior_type == "sheriff_office":
            self.safe_menu(self.show_active_bounties_menu, "Sheriff records closed."); return True
        if interior_type == "town_hall":
            record = self.route_hamlet_record()
            self.vertical_panel_view(f"{record['name']} Hamlet Hall", self.route_hamlet_directory_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT); return True
        return False

    def route_hamlet_directory_lines(self) -> List[str]:
        record = self.route_hamlet_record(); profile = ROUTE_HAMLET_TYPES[str(record["type_id"])]
        return [str(record["name"]).upper(), str(profile["title"]), "", str(profile["description"]), "", "Buildings:", *[f"- {door.get('name')} ({door.get('role')})" for door in record.get("doors", ())], "", f"Residents: {len(record.get('residents', ())) }", "The central street, homes, public services, parcel locker, well, benches, and shops are all physically present."]

    def use_route_hamlet_feature(self, feature: Mapping[str, object]) -> bool:
        kind = str(feature.get("kind", "")); record = self.route_hamlet_record()
        if kind == "directory":
            self.vertical_panel_view(str(record["name"]), self.route_hamlet_directory_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT); return True
        if kind == "notice_board":
            self.vertical_panel_view("Community Notice Board", ["COMMUNITY NOTICE BOARD", "", "Public services are available inside the marked buildings.", "Residents follow daily home, work, meal, and evening routines.", "The parcel locker can hold goods you want available on this route.", "", "Current road connections:", *[f"- {name}" for name in self.wilderness_chunk_road_names(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)]], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT); return True
        if kind == "well":
            day = self.errand_day_key()
            if record.get("well_day") == day:
                self.set_message("You already drew drinking water here today."); return True
            restored = self.restore_stamina(10); record["well_day"] = day; self.advance_time(5); self.autosave_with_message(f"Drew water at the village well. Stamina +{restored}."); return True
        if kind == "bench":
            restored = self.restore_stamina(6); self.advance_time(10); self.set_message(f"Rested in the village square. Stamina +{restored}."); return True
        if kind == "market_stall":
            self.route_hamlet_shop_menu(); return True
        if kind == "parcel_locker":
            self.show_world_container(self.route_hamlet_container(feature)); return True
        return False

    def route_hamlet_description_at(self, x: int, y: int) -> str:
        if not self.wilderness_chunk_has_route_hamlet(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return ""
        resident = self.route_hamlet_resident_at(x, y)
        if resident:
            return f"{resident['name']} ({resident['role']}): {resident['activity']}. Use Z/Enter to talk"
        door = self.route_hamlet_door_at(x, y)
        if door:
            return f"Door to {door.get('name', 'a village building')}: walk into it to enter"
        feature = self.route_hamlet_feature_at(x, y)
        if feature:
            return f"{feature.get('name', 'Village fixture')}: use Z/Enter"
        parcel = self.route_hamlet_record().get("parcel", ())
        if len(parcel) == 4 and int(parcel[0]) <= int(x) <= int(parcel[2]) and int(parcel[1]) <= int(y) <= int(parcel[3]):
            return f"Street and grounds of {self.route_hamlet_record()['name']}"
        return ""

    def use_route_hamlet_interior_action(self, x: int, y: int) -> bool:
        tile = self.active_map()[y][x]; building = self.current_route_hamlet_building(); interior_type = str(building.get("interior_type", "home"))
        if tile == "D": self.exit_route_hamlet_building(); return True
        if tile == "_": self.active_map()[y][x] = "|"; self.set_message("Opened the room door."); return True
        if tile == "|": self.active_map()[y][x] = "_"; self.set_message("Closed the room door."); return True
        if tile in {"$", "&", "P", "x", "w", "a"} and self.route_hamlet_public_service(interior_type): return True
        if self.use_catalog_furniture_action_at(x, y): return True
        self.set_message("Nothing here needs direct interaction. Press I to inspect it."); return False


__all__ = ["NO_HAMLET", "ROUTE_HAMLET_DOOR", "ROUTE_HAMLET_LOCATION", "ROUTE_HAMLET_TYPES", "ROUTE_HAMLET_VERSION", "RouteHamletMixin"]
