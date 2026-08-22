"""Rare, physical leisure destinations connected to wilderness roads."""

from __future__ import annotations

import random
from typing import Dict, List, Mapping, Optional, Tuple

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK
from ascii_farmstead_game_tables import GAME_TABLE_DATA
from ascii_farmstead_inventory import add_inventory_items
from ascii_farmstead_procedural_interiors import build_procedural_ground_floor
from ascii_farmstead_route_hamlets import NO_HAMLET
from ascii_farmstead_ui import MenuItem


ROUTE_LEISURE_VERSION = 2
ROUTE_LEISURE_LOCATION = "RouteLeisureInterior"
ROUTE_LEISURE_DOOR = "d"
NO_LEISURE = (10**8, 10**8)


ROUTE_LEISURE_TYPES: Dict[str, Dict[str, object]] = {
    "coaching_house": {
        "title": "Coaching House",
        "description": "A road lodge with private rooms, a dining room, a games parlor, and a working coach yard.",
        "buildings": (
            ("lodge", "Coaching House", "inn", "Innkeeper", "lodging"),
            ("parlor", "Travelers' Games Parlor", "inn", "Games Host", "games"),
            ("stable", "Coach Stable", "workshop", "Hostler", "stable"),
        ),
        "activities": (
            ("coach_register", "Coach Route Register", "P"),
            ("practice_post", "Travel Practice Post", "t"),
            ("courtyard_fire", "Courtyard Fire", "f"),
        ),
        "games": ("blackjack", "checkers", "hearts"),
    },
    "bathhouse": {
        "title": "Country Bathhouse",
        "description": "A hot-spring retreat with a staffed bathhouse, tea room, changing house, and open-air pools.",
        "buildings": (
            ("baths", "Public Bathhouse", "clinic", "Bath Attendant", "bath"),
            ("tea", "Bathhouse Tea Room", "inn", "Tea Steward", "dining"),
            ("changing", "Changing House", "home", "Caretaker", "changing"),
        ),
        "activities": (
            ("hot_pool", "Open-Air Hot Pool", "O"),
            ("cold_pool", "Cold Plunge", "O"),
            ("quiet_deck", "Quiet Deck", "b"),
        ),
        "games": (),
    },
    "angling_lodge": {
        "title": "Angling Lodge",
        "description": "A waterside lodge with a tackle counter, sheltered pond, casting piers, and fish-cleaning station.",
        "buildings": (
            ("lodge", "Anglers' Lodge", "inn", "Lodge Keeper", "lodging"),
            ("tackle", "Tackle and Supply House", "general_store", "Tackle Merchant", "tackle"),
            ("shed", "Boat and Net Shed", "workshop", "Boatwright", "stable"),
        ),
        "activities": (
            ("casting_mark", "Casting Practice Mark", "t"),
            ("fish_table", "Fish-Cleaning Table", "T"),
            ("waterside_bench", "Waterside Bench", "b"),
        ),
        "games": ("mancala",),
    },
    "fairground": {
        "title": "Traveling Fairground",
        "description": "A bright roadside fair with a hall, refreshment stand, games yard, seating, and prize counter.",
        "buildings": (
            ("hall", "Fair Assembly Hall", "town_hall", "Fair Manager", "fair"),
            ("refreshments", "Refreshment House", "general_store", "Vendor", "dining"),
            ("prizes", "Prize and Equipment Shed", "workshop", "Games Keeper", "prizes"),
        ),
        "activities": (
            ("ring_toss", "Ring Toss", "r"),
            ("target_toss", "Target Toss", "t"),
            ("strength_test", "Strength Tester", "!"),
        ),
        "games": ("ur", "mancala"),
    },
    "arts_hall": {
        "title": "Regional Arts Hall",
        "description": "A public arts campus with a performance hall, studio, cafe, gallery walk, and outdoor stage.",
        "buildings": (
            ("hall", "Performance Hall", "town_hall", "Stage Manager", "performance"),
            ("studio", "Public Arts Studio", "library", "Art Instructor", "studio"),
            ("cafe", "Arts Hall Cafe", "inn", "Cafe Keeper", "dining"),
        ),
        "activities": (
            ("outdoor_stage", "Outdoor Performance Stage", "S"),
            ("gallery_wall", "Open-Air Gallery", "p"),
            ("music_stand", "Public Music Stand", "M"),
        ),
        "games": ("chess", "solitaire"),
    },
    "public_gardens": {
        "title": "Regional Public Gardens",
        "description": "A maintained public garden with a conservatory, picnic pavilion, gardener's house, and walking circuit.",
        "buildings": (
            ("conservatory", "Public Conservatory", "library", "Head Gardener", "garden"),
            ("pavilion", "Garden Pavilion", "inn", "Pavilion Keeper", "dining"),
            ("grounds", "Grounds Workshop", "carpenter", "Groundskeeper", "stable"),
        ),
        "activities": (
            ("rose_walk", "Rose Walk", "⚘"),
            ("pond_walk", "Garden Pond Walk", "O"),
            ("orchard_walk", "Orchard Walk", "♣"),
        ),
        "games": ("chess",),
    },
}


LEISURE_NAME_PREFIXES = (
    "Amber", "Bluebell", "Cedar", "Clearwater", "Foxglove", "Golden", "Greenbank",
    "Hearthside", "Juniper", "Lakesong", "Meadow", "Moonrise", "Redleaf", "Silver",
    "Starling", "Sunfield", "Willow",
)
LEISURE_NAME_SUFFIXES = (
    "Court", "Gardens", "Grounds", "Hall", "House", "Landing", "Lodge", "Pavilion", "Retreat", "Yard",
)
LEISURE_GIVEN_NAMES = (
    "Ada", "Basil", "Cora", "Dorian", "Elise", "Frederick", "Gia", "Harper", "Imogen", "Jules",
    "Kellan", "Lydia", "Micah", "Nadia", "Owen", "Priya", "Rowan", "Selene", "Theo", "Vera",
)
LEISURE_SURNAMES = (
    "Alder", "Bell", "Cairn", "Dale", "Everett", "Farrow", "Glass", "Hart", "Ives", "Joyce",
    "Kemp", "Lane", "Mercer", "Nash", "Page", "Quill", "Rose", "Shaw", "Tanner", "West",
)


class RouteLeisureMixin:
    """Allocation, architecture, staff, and activities for leisure destinations."""

    def route_leisure_region_site_chunk(self, chunk_x: int, chunk_y: int) -> Tuple[int, int]:
        anchor = self.wilderness_region_coords(chunk_x, chunk_y)
        cache = getattr(self, "_route_leisure_site_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._route_leisure_site_cache = cache
        settlements = tuple(sorted(str(key) for key in (getattr(self.state, "wilderness_settlements", {}) or {})))
        claims = tuple(sorted(str(key) for key in (getattr(self.state, "owned_wilderness_claims", {}) or {})))
        key = (int(self.state.wilderness_seed), int(getattr(self.state, "wilderness_generation_version", 0) or 0), int(anchor[0]), int(anchor[1]), settlements, claims)
        if key in cache:
            return tuple(cache[key])
        if anchor == self.wilderness_region_coords(0, 0):
            cache[key] = NO_LEISURE
            return NO_LEISURE
        if self.route_hamlet_region_site_chunk(*anchor) != NO_HAMLET:
            cache[key] = NO_LEISURE
            return NO_LEISURE
        if self.wilderness_hash01(anchor[0], anchor[1], 85200) >= 0.065:
            cache[key] = NO_LEISURE
            return NO_LEISURE
        excluded = {
            tuple(self.wilderness_region_structure_chunk(*anchor)),
            tuple(self.wilderness_region_outpost_chunk(*anchor)),
            tuple(self.rural_region_site_chunk(*anchor)),
            tuple(self.corridor_region_site_chunk(*anchor)),
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
        result = NO_LEISURE if not candidates else candidates[random.Random(self.wilderness_chunk_seed(*anchor) + 85201).randrange(len(candidates))]
        cache[key] = result
        return result

    def wilderness_chunk_has_route_leisure(self, chunk_x: int, chunk_y: int) -> bool:
        return (int(chunk_x), int(chunk_y)) == self.route_leisure_region_site_chunk(chunk_x, chunk_y)

    def route_leisure_type(self, chunk_x: int, chunk_y: int) -> str:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        biome_id = str(profile.get("biome_id", ""))
        biome = str(profile.get("biome", ";"))
        if biome == "[" or biome_id in {"tidal_flat", "mangrove", "tropical_isle", "floodplain", "wet_meadow"}:
            return "angling_lodge"
        if biome_id in {"rocky_valley", "badlands", "alpine_meadow", "glacier", "tundra"}:
            return "bathhouse" if self.wilderness_hash01(chunk_x, chunk_y, 85202) < 0.42 else "coaching_house"
        choices = ("coaching_house", "bathhouse", "fairground", "arts_hall", "public_gardens")
        return choices[int(self.wilderness_hash01(chunk_x, chunk_y, 85203) * len(choices)) % len(choices)]

    def route_leisure_name(self, chunk_x: int, chunk_y: int) -> str:
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 85204)
        return f"{rng.choice(LEISURE_NAME_PREFIXES)} {rng.choice(LEISURE_NAME_SUFFIXES)}"

    def route_leisure_record(self, chunk_x: Optional[int] = None, chunk_y: Optional[int] = None) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        self.ensure_wilderness_poi_state()
        record = self.state.wilderness_poi_state.setdefault(f"leisure:{cx},{cy}", {})
        record.setdefault("kind", "route_leisure")
        record.setdefault("type_id", self.route_leisure_type(cx, cy))
        record.setdefault("name", self.route_leisure_name(cx, cy))
        record.setdefault("version", 0)
        record.setdefault("activity_days", {})
        record.setdefault("circuit_days", {})
        return record

    @staticmethod
    def _leisure_feature(features: List[Dict[str, object]], x: int, y: int, kind: str, name: str, glyph: str, **extra: object) -> None:
        features.append({"x": int(x), "y": int(y), "kind": str(kind), "name": str(name), "glyph": str(glyph)[:1], **extra})

    @staticmethod
    def _leisure_disruption_score(grid: List[List[str]], left: int, top: int, width: int, height: int) -> int:
        weights = {"~": 14, "=": 7, ":": 4, "#": 5, "S": 100, "X": 100, "!": 100, "A": 70, "E": 70, "h": 50, "j": 40, "k": 40, "q": 40, "R": 50, "J": 50, "P": 50, "K": 50, "Q": 50, "Y": 50, "G": 50, "Z": 50}
        return sum(weights.get(grid[y][x], 0) for y in range(top, top + height) for x in range(left, left + width))

    def place_route_leisure(self, grid: List[List[str]], chunk_x: int, chunk_y: int) -> bool:
        if not self.wilderness_chunk_has_route_leisure(chunk_x, chunk_y):
            return False
        if self.procedural_town_plan(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return False
        record = self.route_leisure_record(chunk_x, chunk_y)
        saved_doors = list(record.get("doors", ()) or ())
        if int(record.get("version", 0)) >= ROUTE_LEISURE_VERSION and saved_doors and all(
            0 <= int(door.get("y", -1)) < len(grid) and 0 <= int(door.get("x", -1)) < len(grid[0])
            and grid[int(door["y"])][int(door["x"])] == ROUTE_LEISURE_DOOR for door in saved_doors
        ):
            return True
        width, height = 68, 30
        saved_parcel = list(record.get("parcel", ()) or ())
        if len(saved_parcel) == 4:
            left, top, old_right, old_bottom = map(int, saved_parcel)
            width, height = old_right - left + 1, old_bottom - top + 1
        else:
            scored = [
                (self._leisure_disruption_score(grid, left, top, width, height), left, top)
                for top in range(2, len(grid) - height - 1)
                for left in range(3, len(grid[0]) - width - 2)
            ]
            if not scored:
                return False
            best = min(score for score, _left, _top in scored)
            choices = [(left, top) for score, left, top in scored if score <= best + max(10, best // 20)]
            left, top = choices[random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 85205).randrange(len(choices))]
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
        center_x, avenue_y = left + width // 2, top + height // 2
        for x in range(left, right + 1):
            grid[top][x] = grid[bottom][x] = "#"
        for y in range(top, bottom + 1):
            grid[y][left] = grid[y][right] = "#"
        for x in range(left + 1, right):
            grid[avenue_y][x] = ":"
        for y in range(avenue_y, bottom + 1):
            for x in range(center_x - 1, center_x + 2):
                grid[y][x] = ":"
        for x in range(center_x - 1, center_x + 2):
            grid[bottom][x] = "|"
        if not self.connect_wilderness_site_to_regional_road(grid, (center_x, bottom + 1), roads):
            for y in range(bottom + 1, len(grid)):
                grid[y][center_x] = "="

        profile = ROUTE_LEISURE_TYPES[str(record["type_id"])]
        centers = ((left + 13, top + 7), (center_x, top + 7), (right - 13, top + 7))
        doors: List[Dict[str, object]] = []
        for index, (building_id, name, interior_type, role, service) in enumerate(tuple(profile["buildings"])):
            size = (19, 10) if index == 0 else (17, 9)
            door_x, door_y, outside_x, outside_y = self.stamp_wilderness_building_exterior(
                grid, centers[index], size, "south", ROUTE_LEISURE_DOOR, ground,
            )
            doors.append({
                "x": door_x, "y": door_y, "outside_x": outside_x, "outside_y": outside_y,
                "side": "south", "building_id": building_id, "name": name,
                "interior_type": interior_type, "role": role, "service": service,
            })
            for y in range(outside_y, avenue_y + 1):
                grid[y][outside_x] = ":"

        features: List[Dict[str, object]] = []
        self._leisure_feature(features, center_x - 6, avenue_y - 1, "directory", f"{record['name']} Directory", "n")
        self._leisure_feature(features, center_x + 6, avenue_y - 1, "parcel_locker", "Visitor Locker", "s", profile="crate")
        activity_xs = (left + 12, center_x, right - 12)
        for index, (kind, name, glyph) in enumerate(tuple(profile["activities"])):
            self._leisure_feature(features, activity_xs[index], avenue_y + 6, kind, name, glyph, activity=True)
        self._leisure_feature(features, center_x - 8, avenue_y + 2, "bench", "Visitor Bench", "b")
        self._leisure_feature(features, center_x + 8, avenue_y + 2, "bench", "Visitor Bench", "b")

        if str(record["type_id"]) == "angling_lodge":
            pond_left, pond_right = left + 5, left + 24
            pond_top, pond_bottom = avenue_y + 3, bottom - 2
            for y in range(pond_top, pond_bottom + 1):
                for x in range(pond_left, pond_right + 1):
                    grid[y][x] = "~"
            pier_y = pond_top + 2
            for x in range(pond_right - 5, pond_right + 3):
                grid[pier_y][x] = "="
            self._leisure_feature(features, pond_right + 2, pier_y, "fishing_pier", "Sheltered Fishing Pier", "=", activity=True)
        elif str(record["type_id"]) == "public_gardens":
            flower_glyph = "⚘" if bool(getattr(self.state, "detailed_glyphs_enabled", True)) else "y"
            for base_x in (left + 8, center_x - 4, right - 16):
                for y in range(avenue_y + 9, min(bottom - 1, avenue_y + 12)):
                    for x in range(base_x, min(right, base_x + 7)):
                        if (x + y) % 2 == 0:
                            grid[y][x] = flower_glyph

        for feature in features:
            grid[int(feature["y"])][int(feature["x"])] = str(feature["glyph"])

        self.preserve_wilderness_roads_around_parcel(
            grid, (left, top, right, bottom), original_roads,
            (center_x, bottom + 1),
        )

        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 85206)
        staff = []
        for index, door in enumerate(doors):
            staff.append({
                "id": f"leisure:{chunk_x},{chunk_y}:staff:{index}",
                "name": f"{rng.choice(LEISURE_GIVEN_NAMES)} {rng.choice(LEISURE_SURNAMES)}",
                "role": str(door["role"]), "building_id": str(door["building_id"]),
                "bond": 0, "conversations": 0,
            })
        record.update({
            "version": ROUTE_LEISURE_VERSION, "parcel": [left, top, right, bottom],
            "gate": [center_x, bottom], "doors": doors, "features": features,
            "staff": staff, "plaza": [center_x, avenue_y],
        })
        return True

    def route_leisure_feature_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_leisure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((feature for feature in self.route_leisure_record().get("features", ()) if (int(feature.get("x", -1)), int(feature.get("y", -1))) == (int(x), int(y))), None)

    def route_leisure_door_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_leisure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        return next((door for door in self.route_leisure_record().get("doors", ()) if (int(door.get("x", -1)), int(door.get("y", -1))) == (int(x), int(y))), None)

    def route_leisure_staff_position(self, staff: Mapping[str, object], chunk_x: Optional[int] = None, chunk_y: Optional[int] = None) -> Tuple[int, int, str]:
        record = self.route_leisure_record(chunk_x, chunk_y)
        doors = {str(door.get("building_id")): door for door in record.get("doors", ())}
        door = doors.get(str(staff.get("building_id")), {})
        hour = int(getattr(self.state, "hour", 8))
        index = int(str(staff.get("id", "0")).rsplit(":", 1)[-1] or 0)
        if 8 <= hour < 20:
            return int(door.get("outside_x", 1)), int(door.get("outside_y", 1)), f"welcoming visitors at {door.get('name', 'the grounds')}"
        plaza_x, plaza_y = map(int, record.get("plaza", (43, 19)))
        return plaza_x + (index - 1) * 3, plaza_y + 2, "closing the grounds for the evening"

    def route_leisure_staff_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not self.wilderness_chunk_has_route_leisure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return None
        for staff in self.route_leisure_record().get("staff", ()):
            sx, sy, activity = self.route_leisure_staff_position(staff)
            if (sx, sy) == (int(x), int(y)):
                result = dict(staff)
                result.update({"x": sx, "y": sy, "activity": activity})
                return result
        return None

    def talk_to_route_leisure_staff(self, staff: Mapping[str, object]) -> bool:
        record = self.route_leisure_record()
        stored = next((row for row in record.get("staff", ()) if str(row.get("id")) == str(staff.get("id"))), None)
        if not isinstance(stored, dict):
            return False
        actor = {
            "id": str(stored["id"]), "name": str(stored["name"]), "role": str(stored["role"]),
            "activity": str(staff.get("activity", "looking after visitors")), "origin": str(record["name"]),
            "bond": int(stored.get("bond", 0)), "conversations": int(stored.get("conversations", 0)),
        }
        result = self.run_unified_npc_conversation(
            actor, kind="venue staff", first_meeting=actor["conversations"] <= 0,
            agenda_override=f"I work as the {actor['role'].lower()} at {record['name']}. I can tell you which buildings and activities are open today.",
        )
        if result.get("completed") or result.get("transcript"):
            stored["conversations"] = actor["conversations"] + 1
            stored["bond"] = actor["bond"] + 1
        return True

    def enter_route_leisure_building(self, door: Mapping[str, object]) -> bool:
        self.state.current_leisure_site_key = f"{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}"
        self.state.current_leisure_building_id = str(door.get("building_id", "lodge"))
        self.state.leisure_interior_return_x = int(door.get("outside_x", door.get("x", 1)))
        self.state.leisure_interior_return_y = int(door.get("outside_y", door.get("y", 1)))
        self.state.location = ROUTE_LEISURE_LOCATION
        grid = self.route_leisure_interior_map()
        self.state.player_x, self.state.player_y = self.wilderness_interior_entry_landing(grid, str(door.get("side", "south")))
        self.state.facing = "UP"
        self.set_message(f"Entered {door.get('name', 'the visitor building')}.")
        return True

    def exit_route_leisure_building(self) -> None:
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        self.state.player_x, self.state.player_y = self.nearest_active_passable_tile(int(self.state.leisure_interior_return_x), int(self.state.leisure_interior_return_y))
        self.set_message("Stepped back onto the visitor grounds.")

    def current_route_leisure_building(self) -> Dict[str, object]:
        building_id = str(getattr(self.state, "current_leisure_building_id", ""))
        return next((dict(door) for door in self.route_leisure_record().get("doors", ()) if str(door.get("building_id")) == building_id), {})

    @staticmethod
    def _leisure_table_cells(grid: List[List[str]], count: int) -> List[Tuple[int, int]]:
        candidates = []
        for y in range(2, len(grid) - 2):
            for x in range(2, len(grid[0]) - 2):
                if grid[y][x] != ".":
                    continue
                if sum(grid[y + dy][x + dx] == "." for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) >= 3:
                    candidates.append((x, y))
        if not candidates or count <= 0:
            return []
        step = max(1, len(candidates) // (count + 1))
        return [candidates[min(len(candidates) - 1, step * (index + 1))] for index in range(count)]

    def route_leisure_interior_map(self) -> List[List[str]]:
        site_key = str(getattr(self.state, "current_leisure_site_key", self.wilderness_chunk_key()))
        building = self.current_route_leisure_building()
        building_id = str(building.get("building_id", "lodge"))
        cache_key = (site_key, building_id)
        cache = getattr(self, "_route_leisure_interior_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._route_leisure_interior_cache = cache
        if cache_key in cache:
            return cache[cache_key]
        seed = sum((index + 1) * ord(ch) for index, ch in enumerate(f"{site_key}:{building_id}:leisure"))
        rng = random.Random(seed)
        placements: List[Dict[str, object]] = []
        raw_grid = build_procedural_ground_floor(
            str(building.get("interior_type", "inn")), rng.randrange(4), rng.randrange(12), 1,
            program_variant=rng.randrange(3), furniture_placements=placements,
        )
        grid = self.orient_south_door_interior(raw_grid, str(building.get("side", "south")))
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        for placement in placements:
            common = {key: placement.get(key) for key in ("name", "collection", "form", "room_id", "room_role", "rotation", "width", "height")}
            for cell in placement.get("cells", ()) or ():
                item = dict(common)
                item.update(cell)
                lookup[(int(cell.get("x", 0)), int(cell.get("y", 0)))] = item
        profile = ROUTE_LEISURE_TYPES[str(self.route_leisure_record()["type_id"])]
        game_ids = tuple(profile.get("games", ())) if str(building.get("service")) in {"games", "lodging", "fair", "performance"} else ()
        for (x, y), game_id in zip(self._leisure_table_cells(grid, len(game_ids)), game_ids):
            grid[y][x] = str(GAME_TABLE_DATA[str(game_id)]["glyph"])
            lookup.pop((x, y), None)
        catalog = getattr(self, "_route_leisure_catalog_cache", None)
        if not isinstance(catalog, dict):
            catalog = {}
            self._route_leisure_catalog_cache = catalog
        catalog[cache_key] = lookup
        cache[cache_key] = grid
        return grid

    def route_leisure_catalog_furniture_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) != ROUTE_LEISURE_LOCATION:
            return None
        self.route_leisure_interior_map()
        key = (str(self.state.current_leisure_site_key), str(self.state.current_leisure_building_id))
        return getattr(self, "_route_leisure_catalog_cache", {}).get(key, {}).get((int(x), int(y)))

    def route_leisure_container(self, feature: Mapping[str, object]) -> Dict[str, object]:
        key = f"leisure:{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}:{feature.get('x')},{feature.get('y')}:locker"
        existing = self.state.world_containers.get(key)
        if isinstance(existing, dict):
            return existing
        return self.create_container_record(key, int(feature["x"]), int(feature["y"]), "crate", name=str(feature.get("name", "Visitor Locker")), take_policy="player", allow_deposit=True, contents={})

    def route_leisure_directory_lines(self) -> List[str]:
        record = self.route_leisure_record()
        profile = ROUTE_LEISURE_TYPES[str(record["type_id"])]
        return [
            str(record["name"]).upper(), str(profile["title"]), "", str(profile["description"]), "",
            "Buildings:", *[f"- {door.get('name')} ({door.get('role')})" for door in record.get("doors", ())],
            "", "Grounds:", *[f"- {feature.get('name')}" for feature in record.get("features", ()) if feature.get("activity")],
            "", "Use each attraction directly. Completing three different attractions in one day earns the venue's visitor reward.",
        ]

    def route_leisure_complete_activity(self, kind: str, message: str, stamina: int = 0, minutes: int = 15) -> None:
        record = self.route_leisure_record()
        day = self.errand_day_key()
        activity_days = record.setdefault("activity_days", {})
        first_today = str(activity_days.get(kind, "")) != day
        activity_days[kind] = day
        if stamina > 0:
            self.restore_stamina(stamina)
        elif stamina < 0:
            self.state.stamina = max(0, int(self.state.stamina) + int(stamina))
        self.advance_time(minutes)
        todays = {activity for activity, activity_day in activity_days.items() if activity_day == day}
        reward = ""
        if len(todays) >= 3 and record.setdefault("circuit_days", {}).get(day) is not True:
            record["circuit_days"][day] = True
            add_inventory_items(self.state.inventory, {"Trade Parcel": 1, "Field Snack": 1})
            reward = " Visitor circuit complete: received 1 Trade Parcel and 1 Field Snack."
        repeat = "" if first_today else " You have already counted this stop toward today's circuit."
        self.autosave_with_message(f"{message}{repeat}{reward}")

    def route_leisure_activity_is_new_today(self, kind: str) -> bool:
        record = self.route_leisure_record()
        return str(record.setdefault("activity_days", {}).get(str(kind), "")) != self.errand_day_key()

    def use_route_leisure_feature(self, feature: Mapping[str, object]) -> bool:
        kind = str(feature.get("kind", ""))
        record = self.route_leisure_record()
        if kind == "directory":
            self.vertical_panel_view(str(record["name"]), self.route_leisure_directory_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return True
        if kind == "parcel_locker":
            self.show_world_container(self.route_leisure_container(feature))
            return True
        if kind == "bench":
            restored = self.restore_stamina(7)
            self.advance_time(10)
            self.set_message(f"Rested on the visitor grounds. Stamina +{restored}.")
            return True
        if kind in {"hot_pool", "cold_pool", "quiet_deck"}:
            first_today = self.route_leisure_activity_is_new_today(kind)
            maximum = int(getattr(self.state, "combat_max_hp", 1))
            before = int(getattr(self.state, "combat_current_hp", maximum))
            if first_today:
                self.state.combat_current_hp = min(maximum, before + max(2, maximum // 10))
            self.route_leisure_complete_activity(kind, f"Used the {feature.get('name')}. Health +{self.state.combat_current_hp - before}.", stamina=18 if first_today else 0, minutes=30)
            return True
        if kind in {"ring_toss", "target_toss", "strength_test", "practice_post", "casting_mark"}:
            first_today = self.route_leisure_activity_is_new_today(kind)
            seed = self.wilderness_chunk_seed(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y) + sum(ord(ch) for ch in f"{kind}:{self.errand_day_key()}")
            score = random.Random(seed).randrange(4, 13) + min(6, int(getattr(self.state, "combat_level", 1)) // 2)
            winnings = 8 * score if first_today and score >= 11 else 0
            self.state.money += winnings
            self.route_leisure_complete_activity(kind, f"Tried the {feature.get('name')} and scored {score}." + (f" Won {winnings}g." if winnings else ""), stamina=-3, minutes=15)
            return True
        if kind in {"outdoor_stage", "gallery_wall", "music_stand"}:
            earnings = 20 if self.route_leisure_activity_is_new_today(kind) else 0
            self.state.money += earnings
            self.route_leisure_complete_activity(kind, f"Took part at the {feature.get('name')}." + (f" Visitors contributed {earnings}g." if earnings else ""), stamina=-4, minutes=25)
            return True
        if kind in {"rose_walk", "pond_walk", "orchard_walk"}:
            self.route_leisure_complete_activity(kind, f"Completed the {feature.get('name')} section of the garden circuit.", stamina=5, minutes=15)
            return True
        if kind in {"coach_register", "courtyard_fire", "fish_table", "waterside_bench", "fishing_pier"}:
            if kind == "fishing_pier":
                self.set_message("The sheltered pier reaches fishable water. Equip the Fishing Rod and target the water beside it.")
                return True
            self.route_leisure_complete_activity(kind, f"Used the {feature.get('name')}.", stamina=5, minutes=15)
            return True
        return False

    def route_leisure_service_menu(self, service: str) -> bool:
        record = self.route_leisure_record()
        if service in {"lodging", "dining"}:
            items = [
                MenuItem(label="Buy a visitor meal - 55g", value="meal", enabled=self.state.money >= 55, hint="Recover 30 stamina; 20 minutes"),
            ]
            if service == "lodging":
                items.append(MenuItem(label="Rent a private room - 110g", value="room", enabled=self.state.money >= 110, hint="Recover 65 stamina and health; 90 minutes"))
            items.append(MenuItem(label="Leave", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(str(record["name"]), items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return True
            cost = 55 if choice.value == "meal" else 110
            self.state.money -= cost
            restored = self.restore_stamina(30 if choice.value == "meal" else 65)
            if choice.value == "room":
                maximum = int(getattr(self.state, "combat_max_hp", 1))
                self.state.combat_current_hp = min(maximum, int(getattr(self.state, "combat_current_hp", maximum)) + max(4, maximum // 4))
            self.advance_time(20 if choice.value == "meal" else 90)
            self.autosave_with_message(f"Used the visitor {choice.value} service. Stamina +{restored}.")
            return True
        if service == "bath":
            first_today = self.route_leisure_activity_is_new_today("indoor_bath")
            self.route_leisure_complete_activity("indoor_bath", "Took a restorative indoor bath.", stamina=35 if first_today else 0, minutes=40)
            return True
        if service == "tackle":
            items = [
                MenuItem(label="Buy Field Snack - 35g", value=("Field Snack", 35), enabled=self.state.money >= 35),
                MenuItem(label="Buy Fiber - 6g", value=("Fiber", 6), enabled=self.state.money >= 6),
                MenuItem(label="Buy Explorer Raft - 290g", value=("Explorer Raft", 290), enabled=self.state.money >= 290),
                MenuItem(label="Leave", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select("Tackle Counter", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice and choice.value != MENU_BACK:
                item, price = choice.value
                self.state.money -= int(price)
                add_inventory_items(self.state.inventory, {str(item): 1})
                self.autosave_with_message(f"Bought 1 {item} for {price}g.")
            return True
        if service in {"games", "fair", "performance", "studio", "garden", "prizes", "stable", "changing"}:
            lines = self.route_leisure_directory_lines()
            self.vertical_panel_view(str(record["name"]), lines, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return True
        return False

    def route_leisure_description_at(self, x: int, y: int) -> str:
        if not self.wilderness_chunk_has_route_leisure(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
            return ""
        staff = self.route_leisure_staff_at(x, y)
        if staff:
            return f"{staff['name']} ({staff['role']}): {staff['activity']}. Use Z/Enter to talk"
        door = self.route_leisure_door_at(x, y)
        if door:
            return f"Door to {door.get('name', 'a visitor building')}: walk into it to enter"
        feature = self.route_leisure_feature_at(x, y)
        if feature:
            return f"{feature.get('name', 'Visitor attraction')}: use Z/Enter"
        parcel = self.route_leisure_record().get("parcel", ())
        if len(parcel) == 4 and int(parcel[0]) <= int(x) <= int(parcel[2]) and int(parcel[1]) <= int(y) <= int(parcel[3]):
            return f"Public grounds of {self.route_leisure_record()['name']}"
        return ""

    def use_route_leisure_interior_action(self, x: int, y: int) -> bool:
        tile = self.active_map()[y][x]
        building = self.current_route_leisure_building()
        if tile == "D":
            self.exit_route_leisure_building()
            return True
        if tile == "_":
            self.active_map()[y][x] = "|"
            self.set_message("Opened the room door.")
            return True
        if tile == "|":
            self.active_map()[y][x] = "_"
            self.set_message("Closed the room door.")
            return True
        game_id = self.game_table_fixture_id(tile)
        if game_id:
            self.open_physical_game_table(game_id, str(self.route_leisure_record()["name"]))
            return True
        if tile in {"$", "&", "P", "x", "w", "a"} and self.route_leisure_service_menu(str(building.get("service", ""))):
            return True
        if self.use_catalog_furniture_action_at(x, y):
            return True
        self.set_message("Nothing here needs direct interaction. Press I to inspect it.")
        return False


__all__ = [
    "NO_LEISURE", "ROUTE_LEISURE_DOOR", "ROUTE_LEISURE_LOCATION", "ROUTE_LEISURE_TYPES",
    "ROUTE_LEISURE_VERSION", "RouteLeisureMixin",
]
