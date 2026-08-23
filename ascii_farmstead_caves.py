from __future__ import annotations

"""Persistent, biome-sensitive wilderness cave generation and interactions."""

import hashlib
import random
from collections import deque
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from ascii_farmstead_helpers import quantity_agreement, quantity_item_phrase
from ascii_farmstead_support import C, colorize
from ascii_farmstead_visuals import actor_style


CAVE_GENERATION_VERSION = 3

CAVE_PROFILES: Mapping[str, Mapping[str, object]] = {
    "limestone": {
        "name": "Limestone Cavern", "layout": "terraces", "size": (62, 27),
        "resources": ("o", "o", "q", "d", "h"),
        "features": ("echo_gallery", "calcite_shelf", "survey_station", "cache"),
    },
    "ore_gallery": {
        "name": "Ore Gallery", "layout": "branching", "size": (68, 29),
        "resources": ("o", "o", "q", "q", "c", "i", "g"),
        "features": ("assay_bench", "collapsed_seam", "miner_cache", "echo_gallery"),
    },
    "crystal_geode": {
        "name": "Crystal Geode", "layout": "radial", "size": (64, 29),
        "resources": ("o", "q", "A", "A", "C", "C", "g"),
        "features": ("geode_heart", "glowworm_wall", "survey_station", "cache"),
    },
    "fungal_grotto": {
        "name": "Fungal Grotto", "layout": "organic", "size": (66, 29),
        "resources": ("m", "m", "m", "h", "b", "o"),
        "features": ("fungal_nursery", "bat_roost", "root_well", "cache"),
    },
    "root_hollow": {
        "name": "Root Hollow", "layout": "maze", "size": (64, 29),
        "resources": ("h", "h", "m", "b", "o", "q"),
        "features": ("root_well", "fungal_nursery", "echo_gallery", "cache"),
    },
    "flooded_cavern": {
        "name": "Flooded Cavern", "layout": "river", "size": (70, 30),
        "resources": ("d", "d", "m", "h", "q", "o"),
        "features": ("tide_pool", "clay_bank", "survey_station", "cache"),
    },
    "sea_cave": {
        "name": "Sea Cave", "layout": "river", "size": (72, 30),
        "resources": ("d", "m", "h", "C", "o", "q"),
        "features": ("tide_pool", "glowworm_wall", "survey_station", "cache"),
    },
    "lava_tube": {
        "name": "Ancient Lava Tube", "layout": "tube", "size": (72, 27),
        "resources": ("o", "o", "q", "q", "i", "g"),
        "features": ("thermal_vent", "obsidian_seam", "collapsed_seam", "cache"),
    },
    "ice_cave": {
        "name": "Ice Cave", "layout": "tube", "size": (68, 28),
        "resources": ("o", "q", "C", "C", "A"),
        "features": ("ice_lens", "glowworm_wall", "survey_station", "cache"),
    },
    "fossil_beds": {
        "name": "Fossil Beds", "layout": "terraces", "size": (68, 29),
        "resources": ("d", "d", "o", "q", "c"),
        "features": ("fossil_bed", "fossil_bed", "survey_station", "cache"),
    },
    "clay_cavern": {
        "name": "Clay Cavern", "layout": "organic", "size": (62, 27),
        "resources": ("d", "d", "d", "m", "h", "o"),
        "features": ("clay_bank", "root_well", "fungal_nursery", "cache"),
    },
}

FEATURE_DATA: Mapping[str, Mapping[str, object]] = {
    "survey_station": {"glyph": "a", "name": "Survey Station", "tool": "", "walkable": False},
    "cache": {"glyph": "s", "name": "Explorer's Cache", "tool": "", "walkable": False},
    "miner_cache": {"glyph": "s", "name": "Miner's Cache", "tool": "", "walkable": False},
    "echo_gallery": {"glyph": "e", "name": "Echo Gallery", "tool": "", "walkable": False},
    "calcite_shelf": {"glyph": "K", "name": "Calcite Shelf", "tool": "Pickaxe", "walkable": False},
    "assay_bench": {"glyph": "a", "name": "Abandoned Assay Bench", "tool": "", "walkable": False},
    "collapsed_seam": {"glyph": "r", "name": "Collapsed Mineral Seam", "tool": "Pickaxe", "walkable": False},
    "geode_heart": {"glyph": "G", "name": "Geode Heart", "tool": "Pickaxe", "walkable": False},
    "glowworm_wall": {"glyph": "L", "name": "Glowworm Wall", "tool": "", "walkable": False},
    "fungal_nursery": {"glyph": "u", "name": "Fungal Nursery", "tool": "", "walkable": False},
    "bat_roost": {"glyph": "B", "name": "Bat Roost", "tool": "", "walkable": False},
    "root_well": {"glyph": "w", "name": "Root-Fed Spring", "tool": "", "walkable": False},
    "tide_pool": {"glyph": "t", "name": "Underground Fishing Pool", "tool": "Fishing Rod", "walkable": False},
    "clay_bank": {"glyph": "k", "name": "Deep Clay Bank", "tool": "Pickaxe", "walkable": False},
    "thermal_vent": {"glyph": "v", "name": "Warm Mineral Vent", "tool": "", "walkable": False},
    "obsidian_seam": {"glyph": "O", "name": "Obsidian Seam", "tool": "Pickaxe", "walkable": False},
    "ice_lens": {"glyph": "I", "name": "Ancient Ice Lens", "tool": "Pickaxe", "walkable": False},
    "fossil_bed": {"glyph": "F", "name": "Fossil Bed", "tool": "Shovel", "walkable": False},
}

BIOME_CAVE_WEIGHTS: Mapping[str, Sequence[str]] = {
    "meadow": ("limestone", "limestone", "fossil_beds", "clay_cavern"),
    "birch_grove": ("root_hollow", "fungal_grotto", "limestone"),
    "pine_forest": ("root_hollow", "fungal_grotto", "ore_gallery"),
    "old_growth": ("root_hollow", "root_hollow", "fungal_grotto"),
    "prairie": ("limestone", "fossil_beds", "clay_cavern"),
    "moorland": ("limestone", "flooded_cavern", "ore_gallery"),
    "bog": ("flooded_cavern", "clay_cavern", "fungal_grotto"),
    "floodplain": ("flooded_cavern", "clay_cavern", "limestone"),
    "alpine_meadow": ("crystal_geode", "ore_gallery", "ice_cave"),
    "rocky_valley": ("ore_gallery", "crystal_geode", "limestone"),
    "scrubland": ("lava_tube", "fossil_beds", "ore_gallery"),
    "dune_desert": ("fossil_beds", "lava_tube", "limestone"),
    "badlands": ("fossil_beds", "fossil_beds", "lava_tube"),
    "oasis": ("flooded_cavern", "limestone", "fossil_beds"),
    "taiga": ("ice_cave", "root_hollow", "ore_gallery"),
    "glacier": ("ice_cave", "ice_cave", "crystal_geode"),
    "tidal_flat": ("sea_cave", "flooded_cavern", "limestone"),
    "mangrove": ("sea_cave", "flooded_cavern", "root_hollow"),
    "tropical_isle": ("sea_cave", "lava_tube", "crystal_geode"),
}

CAVE_HOSTILES: Mapping[str, Sequence[str]] = {
    "limestone": ("Stonehide", "Burrowfang", "Cave Lurker"),
    "ore_gallery": ("Shard Mite", "Rockback", "Tunnel Crawler"),
    "crystal_geode": ("Shardling", "Crystal Beetle", "Prism Moth"),
    "fungal_grotto": ("Spore Toad", "Thornroot", "Mycelial Crawler"),
    "root_hollow": ("Burrower", "Root Maw", "Vinejaw"),
    "flooded_cavern": ("Marsh Toad", "Giant Leech", "Cave Eel"),
    "sea_cave": ("Brine Crawler", "Tide Lurker", "Razor Crab"),
    "lava_tube": ("Ember Imp", "Cinder Wasp", "Cinder Crawler"),
    "ice_cave": ("Frost Moth", "Rime Wasp", "Ice Prowler"),
    "fossil_beds": ("Bonejaw", "Burrower", "Fossil Scarab"),
    "clay_cavern": ("Mud Lurker", "Marsh Toad", "Clayback"),
}

CAVE_WILDLIFE: Mapping[str, Sequence[Tuple[str, str]]] = {
    "limestone": (("Pale Salamander", "s"), ("Cave Swift", "w")),
    "ore_gallery": (("Tunnel Cricket", "c"), ("Roosting Bat", "b")),
    "crystal_geode": (("Glow Moth", "m"), ("Crystal Snail", "s")),
    "fungal_grotto": (("Fungus Beetle", "b"), ("Cave Newt", "n")),
    "root_hollow": (("Root Mouse", "m"), ("Cave Swift", "w")),
    "flooded_cavern": (("Blind Cavefish", "f"), ("Cave Newt", "n")),
    "sea_cave": (("Tide Crab", "c"), ("Cave Swift", "w")),
    "lava_tube": (("Ash Cricket", "c"), ("Ember Moth", "m")),
    "ice_cave": (("Ice Moth", "m"), ("Pale Salamander", "s")),
    "fossil_beds": (("Cave Swift", "w"), ("Tunnel Cricket", "c")),
    "clay_cavern": (("Cave Newt", "n"), ("Root Mouse", "m")),
}


def _stable_seed(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


class ExpandedCaveMixin:
    """Generation and direct world interactions for persistent wilderness caves."""

    def ensure_expanded_cave_state(self) -> None:
        if not isinstance(getattr(self.state, "wilderness_cave_state", None), dict):
            self.state.wilderness_cave_state = {}

    def expanded_cave_profile_id(self, cave_key: str) -> str:
        self.ensure_expanded_cave_state()
        saved = self.state.wilderness_cave_state.get(str(cave_key), {})
        if isinstance(saved, dict) and str(saved.get("profile", "")) in CAVE_PROFILES:
            return str(saved["profile"])
        cx, cy, _ex, _ey = self.cave_context_from_key(cave_key)
        try:
            biome_id = str(self.wilderness_region_profile(cx, cy).get("biome_id", "meadow"))
        except Exception:
            biome_id = "meadow"
        choices = BIOME_CAVE_WEIGHTS.get(biome_id, BIOME_CAVE_WEIGHTS["meadow"])
        return str(choices[_stable_seed(self.state.wilderness_seed, cave_key, "profile") % len(choices)])

    def expanded_cave_name(self, cave_key: str) -> str:
        profile_id = self.expanded_cave_profile_id(cave_key)
        return str(CAVE_PROFILES[profile_id]["name"])

    def expanded_cave_resources(self, cave_type: str) -> List[str]:
        profile = CAVE_PROFILES.get(str(cave_type))
        if profile:
            return list(profile["resources"])
        legacy = {
            "ore": "ore_gallery", "crystal": "crystal_geode", "mushroom": "fungal_grotto",
            "damp": "clay_cavern", "root": "root_hollow", "shallow": "limestone",
        }.get(str(cave_type), "limestone")
        return list(CAVE_PROFILES[legacy]["resources"])

    @staticmethod
    def _carve_ellipse(grid: List[List[str]], cx: int, cy: int, rx: int, ry: int, rng: random.Random) -> None:
        height, width = len(grid), len(grid[0])
        for y in range(max(1, cy - ry - 1), min(height - 1, cy + ry + 2)):
            for x in range(max(1, cx - rx - 1), min(width - 1, cx + rx + 2)):
                distance = ((x - cx) ** 2) / max(1, rx * rx) + ((y - cy) ** 2) / max(1, ry * ry)
                if distance <= 1.0 + rng.random() * 0.12:
                    grid[y][x] = "."

    @staticmethod
    def _carve_corridor(grid: List[List[str]], start: Tuple[int, int], end: Tuple[int, int], rng: random.Random, width: int = 1) -> None:
        height, map_width = len(grid), len(grid[0])
        x, y = start
        ex, ey = end
        while (x, y) != (ex, ey):
            for yy in range(max(1, y - width), min(height - 1, y + width + 1)):
                for xx in range(max(1, x - width), min(map_width - 1, x + width + 1)):
                    grid[yy][xx] = "."
            horizontal = x != ex and (y == ey or rng.random() < 0.56)
            if horizontal:
                x += 1 if x < ex else -1
            elif y != ey:
                y += 1 if y < ey else -1

    def _expanded_cave_rooms(self, layout: str, width: int, height: int, rng: random.Random) -> List[Tuple[int, int, int, int]]:
        cx = width // 2
        if layout == "radial":
            return [(cx, height // 2, 8, 5), (cx, 5, 7, 3), (10, height // 2, 7, 4),
                    (width - 11, height // 2, 7, 4), (16, 7, 6, 3), (width - 17, 7, 6, 3),
                    (cx, height - 6, 8, 3)]
        if layout == "terraces":
            return [(cx, height - 6, 10, 3), (15, height - 12, 10, 3),
                    (width - 16, height - 17, 10, 3), (cx, 6, 13, 4)]
        if layout == "branching":
            return [(cx, height - 6, 8, 3), (cx, height // 2, 7, 4), (cx, 5, 8, 3),
                    (13, height // 2 + 2, 9, 3), (width - 14, height // 2 - 2, 9, 3),
                    (16, 6, 7, 3), (width - 17, 7, 7, 3)]
        if layout == "maze":
            return [(cx, height - 5, 8, 3), (14, height - 9, 8, 4),
                    (width - 15, height - 10, 8, 4), (cx, height // 2, 7, 4),
                    (15, 6, 8, 3), (width - 16, 6, 8, 3)]
        if layout == "tube":
            points = [(cx, height - 5, 8, 3)]
            x = cx
            for y in range(height - 11, 4, -5):
                x = max(10, min(width - 11, x + rng.choice((-13, -9, 9, 13))))
                points.append((x, y, rng.randint(7, 10), 3))
            return points
        if layout == "river":
            return [(cx, height - 5, 10, 3), (15, height - 10, 10, 4),
                    (width - 16, height - 12, 10, 4), (cx, height // 2, 12, 5),
                    (16, 6, 10, 3), (width - 17, 6, 10, 3)]
        return [(cx, height - 5, 10, 3), (14, height // 2, 10, 5),
                (width - 15, height // 2, 10, 5), (cx, 6, 13, 4),
                (cx, height // 2, 8, 5)]

    def generate_expanded_cave_map(self, cave_key: str) -> List[List[str]]:
        self.ensure_expanded_cave_state()
        profile_id = self.expanded_cave_profile_id(cave_key)
        profile = CAVE_PROFILES[profile_id]
        width, height = tuple(profile["size"])
        rng = random.Random(_stable_seed(self.state.wilderness_seed, cave_key, profile_id, CAVE_GENERATION_VERSION))
        grid = [["#" for _ in range(int(width))] for _ in range(int(height))]
        rooms = self._expanded_cave_rooms(str(profile["layout"]), int(width), int(height), rng)
        for room in rooms:
            self._carve_ellipse(grid, *room, rng)

        layout = str(profile["layout"])
        if layout == "radial":
            hub = (rooms[0][0], rooms[0][1])
            for room in rooms[1:]:
                self._carve_corridor(grid, hub, (room[0], room[1]), rng, 1)
        elif layout == "branching":
            spine = rooms[:3]
            for left, right in zip(spine, spine[1:]):
                self._carve_corridor(grid, (left[0], left[1]), (right[0], right[1]), rng, 1)
            for room in rooms[3:]:
                anchor = min(spine, key=lambda item: abs(item[1] - room[1]))
                self._carve_corridor(grid, (anchor[0], anchor[1]), (room[0], room[1]), rng, 1)
        else:
            for left, right in zip(rooms, rooms[1:]):
                self._carve_corridor(grid, (left[0], left[1]), (right[0], right[1]), rng, 1)
            if layout in {"maze", "organic"} and len(rooms) > 4:
                self._carve_corridor(grid, (rooms[1][0], rooms[1][1]), (rooms[-1][0], rooms[-1][1]), rng, 0)

        entrance_x = int(width) // 2
        self._carve_corridor(grid, (entrance_x, int(height) - 2), (rooms[0][0], rooms[0][1]), rng, 1)

        # Flooded and sea caves have a real underground channel with two usable crossings.
        if layout == "river":
            river_y = int(height) // 2
            drift = 0
            bridge_xs = {int(width) // 3, (int(width) * 2) // 3}
            for x in range(2, int(width) - 2):
                if x % 7 == 0:
                    drift = max(-2, min(2, drift + rng.choice((-1, 0, 1))))
                for dy in (-1, 0, 1):
                    yy = max(2, min(int(height) - 3, river_y + drift + dy))
                    if grid[yy][x] != "#":
                        grid[yy][x] = "~"
                if any(abs(x - bx) <= 1 for bx in bridge_xs):
                    for dy in (-2, -1, 0, 1, 2):
                        yy = max(1, min(int(height) - 2, river_y + drift + dy))
                        grid[yy][x] = "="

        # Reserve a clear arrival apron before deposits/features are placed.
        for y in range(int(height) - 4, int(height) - 1):
            for x in range(entrance_x - 3, entrance_x + 4):
                grid[y][x] = "."
        grid[int(height) - 2][entrance_x] = "<"

        floor_tiles = [(x, y) for y in range(2, int(height) - 3) for x in range(2, int(width) - 2)
                       if grid[y][x] == "." and abs(x - entrance_x) + abs(y - (int(height) - 2)) > 8]
        rng.shuffle(floor_tiles)
        resources = list(profile["resources"])
        resource_count = min(46, max(18, len(floor_tiles) // 12))
        for x, y in floor_tiles[:resource_count]:
            grid[y][x] = rng.choice(resources)

        record: Dict[str, object] = {
            "generation_version": CAVE_GENERATION_VERSION,
            "profile": profile_id,
            "features": [],
            "discoveries": [],
            "completion_rewarded": False,
        }
        self.state.wilderness_cave_state[str(cave_key)] = record
        self._place_expanded_cave_features(cave_key, grid, list(profile["features"]), record)
        self._ensure_expanded_cave_access(grid, record)
        self._populate_expanded_cave_creatures(cave_key, grid, record)
        return grid

    def _place_expanded_cave_features(
        self,
        cave_key: str,
        grid: List[List[str]],
        kinds: Sequence[str],
        record: Dict[str, object],
    ) -> None:
        rng = random.Random(_stable_seed(self.state.wilderness_seed, cave_key, "features"))
        height, width = len(grid), len(grid[0])
        candidates = []
        for y in range(3, height - 4):
            for x in range(3, width - 3):
                if grid[y][x] != ".":
                    continue
                adjacent_wall = any(grid[y + dy][x + dx] == "#" for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
                candidates.append((x, y, 1 if adjacent_wall else 0))
        rng.shuffle(candidates)
        candidates.sort(key=lambda item: -item[2])
        placed: List[Tuple[int, int]] = []
        specs: List[Dict[str, object]] = []
        for index, kind in enumerate(kinds):
            choice: Optional[Tuple[int, int, int]] = None
            for candidate in candidates:
                x, y, _score = candidate
                if all(abs(x - px) + abs(y - py) >= 10 for px, py in placed):
                    choice = candidate
                    break
            if choice is None:
                continue
            candidates.remove(choice)
            x, y, _score = choice
            data = FEATURE_DATA[kind]
            grid[y][x] = str(data["glyph"])
            placed.append((x, y))
            specs.append({
                "id": f"{kind}:{index}", "kind": kind, "name": str(data["name"]),
                "glyph": str(data["glyph"]), "x": x, "y": y, "depleted": False,
                "last_day": "", "last_week": "",
            })
        record["features"] = specs

    @staticmethod
    def _ensure_expanded_cave_access(grid: List[List[str]], record: Dict[str, object]) -> None:
        """Keep every feature reachable even when deposits occupy narrow passages."""
        height, width = len(grid), len(grid[0])
        start = (width // 2, height - 2)
        # Saved cave resources are real world objects, not disposable corridor
        # paint, so routing prefers to go around them. Plain wall rock is not
        # precious: a feature sealed behind it may be tunnelled to rather than
        # left permanently unreachable.
        resource_glyphs = {"o", "q", "m", "c", "i", "g", "A", "C", "h", "b", "d"}
        feature_cells = {
            (int(feature.get("x", -1)), int(feature.get("y", -1)))
            for feature in record.get("features", [])
            if isinstance(feature, dict)
        }

        def search(
            goals: Set[Tuple[int, int]], blocked: Set[str],
        ) -> Tuple[Optional[Tuple[int, int]], Dict[Tuple[int, int], Optional[Tuple[int, int]]]]:
            queue = deque([start])
            previous: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
            while queue:
                current = queue.popleft()
                if current in goals:
                    return current, previous
                x, y = current
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nxt = (x + dx, y + dy)
                    nx, ny = nxt
                    if not (0 < nx < width - 1 and 0 < ny < height - 1):
                        continue
                    if (
                        nxt in previous
                        or (grid[ny][nx] in blocked and nxt not in goals)
                        or (nxt in feature_cells and nxt not in goals)
                    ):
                        continue
                    previous[nxt] = current
                    queue.append(nxt)
            return None, previous

        for feature in record.get("features", []):
            if not isinstance(feature, dict):
                continue
            fx, fy = int(feature.get("x", -1)), int(feature.get("y", -1))
            neighbours = [
                (fx + dx, fy + dy)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                if 0 < fx + dx < width - 1 and 0 < fy + dy < height - 1
            ]
            if not neighbours:
                continue
            # A cell holding another resource cannot be stood on, so it never
            # makes a feature usable; prefer genuinely open approach cells.
            open_goals = {
                (nx, ny) for nx, ny in neighbours
                if grid[ny][nx] not in resource_glyphs and (nx, ny) not in feature_cells
            }
            rock_goals = {(nx, ny) for nx, ny in neighbours if grid[ny][nx] == "#"}
            attempts = (
                (open_goals - rock_goals, {"#"} | resource_glyphs),
                (open_goals | rock_goals, resource_glyphs),
            )
            reached: Optional[Tuple[int, int]] = None
            previous: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {}
            for goals, blocked in attempts:
                if not goals:
                    continue
                reached, previous = search(goals, blocked)
                if reached is not None:
                    break
            if reached is None:
                continue
            current: Optional[Tuple[int, int]] = reached
            while current is not None:
                x, y = current
                if (x, y) not in feature_cells and grid[y][x] not in {".", "<", "U", "="}:
                    grid[y][x] = "=" if grid[y][x] == "~" else "."
                current = previous[current]

    def upgrade_expanded_cave_map(self, cave_key: str, grid: List[List[str]]) -> List[List[str]]:
        """Add interaction records to legacy caves without restoring mined cells."""
        self.ensure_expanded_cave_state()
        record = self.state.wilderness_cave_state.get(str(cave_key))
        if isinstance(record, dict) and int(record.get("generation_version", 0) or 0) >= CAVE_GENERATION_VERSION:
            return grid
        if isinstance(record, dict) and int(record.get("generation_version", 0) or 0) == 2:
            record["generation_version"] = CAVE_GENERATION_VERSION
            if not isinstance(record.get("enemies"), list) or not isinstance(record.get("wildlife"), list):
                self._populate_expanded_cave_creatures(cave_key, grid, record)
            return grid
        profile_id = self.expanded_cave_profile_id(cave_key)
        record = {
            "generation_version": CAVE_GENERATION_VERSION,
            "profile": profile_id,
            "features": [], "discoveries": [], "completion_rewarded": False,
            "legacy_layout": True,
        }
        self.state.wilderness_cave_state[str(cave_key)] = record
        features = list(CAVE_PROFILES[profile_id]["features"])
        self._place_expanded_cave_features(cave_key, grid, features[:3], record)
        self._ensure_expanded_cave_access(grid, record)
        self._populate_expanded_cave_creatures(cave_key, grid, record)
        return grid

    def expanded_cave_record(self, cave_key: Optional[str] = None) -> Dict[str, object]:
        self.ensure_expanded_cave_state()
        key = str(cave_key or getattr(self.state, "current_cave_key", "") or "0,0:0,0")
        record = self.state.wilderness_cave_state.get(key)
        if not isinstance(record, dict):
            record = {"generation_version": 0, "profile": self.expanded_cave_profile_id(key), "features": [], "discoveries": []}
            self.state.wilderness_cave_state[key] = record
        return record

    def expanded_cave_feature_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        record = self.expanded_cave_record()
        for feature in record.get("features", []):
            if isinstance(feature, dict) and int(feature.get("x", -1)) == int(x) and int(feature.get("y", -1)) == int(y):
                return feature
        return None

    def _populate_expanded_cave_creatures(
        self, cave_key: str, grid: List[List[str]], record: Dict[str, object],
    ) -> None:
        profile_id = str(record.get("profile", "limestone"))
        rng = random.Random(_stable_seed(self.state.wilderness_seed, cave_key, "creatures"))
        height, width = len(grid), len(grid[0])
        feature_cells = {
            (int(feature.get("x", -1)), int(feature.get("y", -1)))
            for feature in record.get("features", []) if isinstance(feature, dict)
        }
        candidates = [
            (x, y) for y in range(2, height - 3) for x in range(2, width - 2)
            if grid[y][x] in {".", "="}
            and (x, y) not in feature_cells
            and abs(x - width // 2) + abs(y - (height - 2)) >= 14
        ]
        rng.shuffle(candidates)
        hostiles: List[Dict[str, object]] = []
        hostile_count = 0 if rng.random() < 0.18 else rng.randint(1, 3)
        species_pool = tuple(CAVE_HOSTILES.get(profile_id, CAVE_HOSTILES["limestone"]))
        for index in range(min(hostile_count, len(candidates))):
            x, y = candidates.pop()
            species = str(rng.choice(species_pool))
            hostile_glyph = (
                "m" if any(word in species for word in ("Moth", "Wasp"))
                else "b" if any(word in species for word in ("Beetle", "Scarab"))
                else "t" if "Toad" in species
                else "e" if "Eel" in species
                else "c" if any(word in species for word in ("Crawler", "Crab", "Leech"))
                else "r" if any(word in species for word in ("Rock", "Stone", "Clay"))
                else "l"
            )
            hostiles.append({
                "id": f"cave:{cave_key}:enemy:{index}", "species": species,
                "x": x, "y": y, "floor": max(1, int(getattr(self.state, "combat_level", 1))),
                "field_combat_kind": "cave", "cave_key": str(cave_key),
                "ecology_symbol": hostile_glyph,
                "alert": False, "defeated": False,
            })
        wildlife: List[Dict[str, object]] = []
        wildlife_pool = tuple(CAVE_WILDLIFE.get(profile_id, CAVE_WILDLIFE["limestone"]))
        for index in range(min(rng.randint(2, 4), len(candidates))):
            species, glyph = rng.choice(wildlife_pool)
            aquatic_candidates = [
                (x, y) for y in range(1, height - 1) for x in range(1, width - 1)
                if grid[y][x] == "~"
                and any(grid[y + dy][x + dx] in {".", "="} for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
                and all((int(animal["x"]), int(animal["y"])) != (x, y) for animal in wildlife)
            ]
            if species == "Blind Cavefish" and aquatic_candidates:
                x, y = rng.choice(aquatic_candidates)
            else:
                x, y = candidates.pop()
            wildlife.append({
                "id": f"cave:{cave_key}:wildlife:{index}", "species": str(species),
                "glyph": str(glyph), "x": x, "y": y, "observed": False,
            })
        record["enemies"] = hostiles
        record["wildlife"] = wildlife

    def expanded_cave_enemies(self) -> List[Dict[str, object]]:
        enemies = self.expanded_cave_record().setdefault("enemies", [])
        if not isinstance(enemies, list):
            enemies = []
            self.expanded_cave_record()["enemies"] = enemies
        return [enemy for enemy in enemies if isinstance(enemy, dict) and not bool(enemy.get("defeated", False))]

    def expanded_cave_enemy_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        for enemy in self.expanded_cave_enemies():
            if (int(enemy.get("x", -1)), int(enemy.get("y", -1))) == (int(x), int(y)):
                return enemy
        return None

    def remove_expanded_cave_enemy(self, enemy: Dict[str, object]) -> None:
        enemy_id = str(enemy.get("id", ""))
        record = self.expanded_cave_record(str(enemy.get("cave_key", "") or self.state.current_cave_key))
        record["enemies"] = [
            current for current in record.get("enemies", [])
            if isinstance(current, dict) and str(current.get("id", "")) != enemy_id
        ]

    def expanded_cave_wildlife(self) -> List[Dict[str, object]]:
        wildlife = self.expanded_cave_record().setdefault("wildlife", [])
        if not isinstance(wildlife, list):
            wildlife = []
            self.expanded_cave_record()["wildlife"] = wildlife
        return [animal for animal in wildlife if isinstance(animal, dict)]

    def expanded_cave_wildlife_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        for animal in self.expanded_cave_wildlife():
            if (int(animal.get("x", -1)), int(animal.get("y", -1))) == (int(x), int(y)):
                return animal
        return None

    def expanded_cave_enemy_passable_tile(self, x: int, y: int, ignore_enemy_id: str = "") -> bool:
        if not self.in_active_bounds(x, y):
            return False
        if (int(x), int(y)) == (int(self.state.player_x), int(self.state.player_y)):
            return False
        tile = str(self.active_map()[y][x])
        if tile in {"#", " ", "~", "o", "q", "m", "c", "i", "g", "A", "C", "h", "b", "d"}:
            return False
        if self.expanded_cave_feature_blocks(x, y):
            return False
        for enemy in self.expanded_cave_enemies():
            if str(enemy.get("id", "")) == str(ignore_enemy_id):
                continue
            if (int(enemy.get("x", -1)), int(enemy.get("y", -1))) == (int(x), int(y)):
                return False
        return not bool(self.travel_follower_at(x, y))

    def expanded_cave_wildlife_passable_tile(
        self, animal: Dict[str, object], x: int, y: int,
    ) -> bool:
        if not self.in_active_bounds(x, y):
            return False
        species = str(animal.get("species", ""))
        tile = str(self.active_map()[y][x])
        if species == "Blind Cavefish":
            if tile != "~":
                return False
        elif species == "Tide Crab":
            if tile not in {".", "=", "~"}:
                return False
        elif not self.expanded_cave_enemy_passable_tile(x, y):
            return False
        if (int(x), int(y)) == (int(self.state.player_x), int(self.state.player_y)):
            return False
        if self.expanded_cave_enemy_at(x, y) or self.travel_follower_at(x, y):
            return False
        return not any(
            str(other.get("id", "")) != str(animal.get("id", ""))
            and (int(other.get("x", -1)), int(other.get("y", -1))) == (int(x), int(y))
            for other in self.expanded_cave_wildlife()
        )

    def nearest_engaging_expanded_cave_enemy(self) -> Optional[Dict[str, object]]:
        if not self.on_wilderness_cave():
            return None
        px, py = int(self.state.player_x), int(self.state.player_y)
        nearby = [
            (abs(int(enemy.get("x", 0)) - px) + abs(int(enemy.get("y", 0)) - py), enemy)
            for enemy in self.expanded_cave_enemies()
            if max(abs(int(enemy.get("x", 0)) - px), abs(int(enemy.get("y", 0)) - py)) <= 1
        ]
        return min(nearby, default=(0, None), key=lambda pair: pair[0])[1]

    def start_expanded_cave_combat(self, enemy: Dict[str, object], reason: str = "nearby") -> bool:
        enemy["field_combat_kind"] = "cave"
        if not self.begin_wilderness_field_combat(enemy, reason=reason):
            return False
        if reason in {"bump", "interact", "tool"}:
            self.dungeon_player_melee_attack(enemy)
        else:
            self.advance_dungeon_roguelike_turn("hostile engagement")
        return True

    def check_expanded_cave_enemy_engagement(self, reason: str = "nearby") -> bool:
        enemy = self.nearest_engaging_expanded_cave_enemy()
        return bool(enemy and self.start_expanded_cave_combat(enemy, reason))

    def update_expanded_cave_creatures(self) -> None:
        if not self.on_wilderness_cave() or self.wilderness_field_combat_active():
            return
        px, py = int(self.state.player_x), int(self.state.player_y)
        for enemy in self.expanded_cave_enemies():
            if random.random() > 0.48:
                continue
            ex, ey = int(enemy.get("x", 0)), int(enemy.get("y", 0))
            options = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            if abs(ex - px) + abs(ey - py) <= 7:
                options.sort(key=lambda step: abs(ex + step[0] - px) + abs(ey + step[1] - py))
            else:
                random.shuffle(options)
            for dx, dy in options:
                if self.expanded_cave_enemy_passable_tile(ex + dx, ey + dy, str(enemy.get("id", ""))):
                    enemy["x"], enemy["y"] = ex + dx, ey + dy
                    break
        occupied = {
            (int(enemy.get("x", -1)), int(enemy.get("y", -1))) for enemy in self.expanded_cave_enemies()
        }
        for animal in self.expanded_cave_wildlife():
            if random.random() > 0.28:
                continue
            ax, ay = int(animal.get("x", 0)), int(animal.get("y", 0))
            options = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            random.shuffle(options)
            for dx, dy in options:
                nx, ny = ax + dx, ay + dy
                if (nx, ny) in occupied or (nx, ny) == (px, py):
                    continue
                if self.expanded_cave_wildlife_passable_tile(animal, nx, ny):
                    animal["x"], animal["y"] = nx, ny
                    break

    def observe_expanded_cave_wildlife(self, animal: Dict[str, object]) -> bool:
        species = str(animal.get("species", "cave animal"))
        if bool(animal.get("observed", False)):
            self.set_message(f"The {species.lower()} continues its ordinary cave behavior, wary of your movement.")
            return True
        animal["observed"] = True
        observed = getattr(self.state, "wilderness_cave_species_observed", None)
        if not isinstance(observed, list):
            observed = []
            self.state.wilderness_cave_species_observed = observed
        first_species_record = species not in observed
        milestone = False
        if first_species_record:
            observed.append(species)
            self.state.money += 20
            milestone = len(observed) % 5 == 0
            if milestone:
                self.state.inventory["Surveyor's Notes"] = self.state.inventory.get("Surveyor's Notes", 0) + 1
        self.autosave_with_message(
            (
                f"You add the {species.lower()} to your cave wildlife record: +20g."
                + (" Five species recorded; you compile Surveyor's Notes." if milestone else "")
            )
            if first_species_record
            else f"You quietly record this {species.lower()}'s local habitat; the species is already in your field record."
        )
        return True

    def expanded_cave_wildlife_description(self, animal: Dict[str, object]) -> str:
        species = str(animal.get("species", "Cave animal"))
        details = {
            "Blind Cavefish": "It follows tiny currents through the dark water.",
            "Roosting Bat": "It shifts along the stone, listening for movement.",
            "Glow Moth": "Its dim abdomen pulses against the mineral wall.",
            "Pale Salamander": "It keeps to cool cracks and damp stone.",
            "Crystal Snail": "Mineral dust clings to its slow-moving shell.",
        }
        return f"{species}: {details.get(species, 'It uses the sheltered cave as a natural habitat.')} Use Z/Enter to observe quietly."

    def render_expanded_cave_wildlife(self, animal: Dict[str, object]) -> str:
        species = str(animal.get("species", "Cave animal"))
        base_color = (
            C.WATER if any(word in species for word in ("Cavefish", "Newt", "Crab"))
            else C.UNDERGROUND_GLOW if any(word in species for word in ("Glow", "Ember", "Ice Moth"))
            else C.WOOD if any(word in species for word in ("Bat", "Mouse", "Swift"))
            else C.FUNGAL
        )
        glyph, color = actor_style(
            "wildlife", str(animal.get("glyph", "a"))[:1] or "a",
            role=species, base_color=base_color,
            high_contrast=bool(getattr(self.state, "high_contrast_enabled", False)),
        )
        return colorize(glyph, color)

    def expanded_cave_enemy_description(self, enemy: Dict[str, object]) -> str:
        species = str(enemy.get("species", "Cave creature"))
        descriptions = {
            "Cave Lurker": "A low predator uses ledges and mineral shadows to approach unseen.",
            "Tunnel Crawler": "A plated scavenger braces itself in narrow passages.",
            "Crystal Beetle": "Its mineral-coated shell scatters light as it patrols the geode.",
            "Prism Moth": "Its wings flash before releasing sharp mineral dust at range.",
            "Mycelial Crawler": "Fungal growth across its body sheds irritating spores.",
            "Root Maw": "A root-bound ambusher snaps from cracks in the cave floor.",
            "Cave Eel": "It darts between flooded shelves and strikes from the waterline.",
            "Cinder Crawler": "Heat radiates from the seams of its dark shell.",
            "Fossil Scarab": "Its stone-hard carapace resembles the fossil bed around it.",
            "Clayback": "Wet clay has hardened into heavy armor across its back.",
        }
        return descriptions.get(species, f"A hostile {species.lower()} adapted to this cave's geology.")

    def expanded_cave_feature_blocks(self, x: int, y: int) -> bool:
        feature = self.expanded_cave_feature_at(x, y)
        if not feature:
            return False
        if bool(feature.get("depleted", False)):
            return False
        return not bool(FEATURE_DATA.get(str(feature.get("kind", "")), {}).get("walkable", False))

    def expanded_cave_feature_description(self, x: int, y: int) -> str:
        feature = self.expanded_cave_feature_at(x, y)
        if not feature:
            return ""
        kind, name = str(feature.get("kind", "")), str(feature.get("name", "Cave feature"))
        if bool(feature.get("depleted", False)):
            return f"Worked-out {name.lower()}: the passage is clear"
        tool = str(FEATURE_DATA.get(kind, {}).get("tool", ""))
        if tool:
            return f"{name}: use F with {tool}"
        descriptions = {
            "survey_station": "use Z/Enter to chart nearby surface routes",
            "assay_bench": "use Z/Enter to sort a weekly mineral sample",
            "cache": "use Z/Enter to open the recovered cache",
            "miner_cache": "use Z/Enter to open the recovered mining cache",
            "echo_gallery": "use Z/Enter to examine the chamber's acoustics",
            "glowworm_wall": "use Z/Enter to study the living light",
            "fungal_nursery": "use Z/Enter to gather its weekly growth",
            "bat_roost": "use Z/Enter to observe or collect fallen guano",
            "root_well": "use Z/Enter to drink and recover once per day",
            "tide_pool": "use F with Fishing Rod to fish underground",
            "thermal_vent": "use Z/Enter to rest in the mineral warmth once per day",
        }
        return f"{name}: {descriptions.get(kind, 'use Z/Enter to examine it')}"

    def _record_expanded_cave_discovery(self, feature: Dict[str, object]) -> str:
        record = self.expanded_cave_record()
        discoveries = record.setdefault("discoveries", [])
        feature_id = str(feature.get("id", ""))
        new = feature_id not in discoveries
        if new:
            discoveries.append(feature_id)
        reward_text = ""
        if len(discoveries) >= 3 and not bool(record.get("completion_rewarded", False)):
            record["completion_rewarded"] = True
            self.state.money += 120
            self.state.inventory["Surveyor's Notes"] = self.state.inventory.get("Surveyor's Notes", 0) + 1
            reward_text = " You completed the cave survey: +120g and Surveyor's Notes."
        return (" New cave feature recorded." if new else "") + reward_text

    def _cave_day_key(self) -> str:
        return f"{int(self.state.year)}-{int(self.state.month)}-{int(self.state.day)}"

    def use_expanded_cave_feature(self, x: int, y: int) -> bool:
        feature = self.expanded_cave_feature_at(x, y)
        if not feature:
            return False
        kind = str(feature.get("kind", ""))
        name = str(feature.get("name", "Cave feature"))
        if bool(feature.get("depleted", False)):
            return False
        if str(FEATURE_DATA.get(kind, {}).get("tool", "")):
            self.set_message(self.expanded_cave_feature_description(x, y))
            return True
        if kind in {"cache", "miner_cache"}:
            profile = "ruin_chest" if kind == "cache" else "crate"
            key = self.container_record_key(x, y, f"cave_{profile}")
            container = self.state.world_containers.get(key)
            if not isinstance(container, dict):
                container = self.create_container_record(key, x, y, profile, name=name)
            self._record_expanded_cave_discovery(feature)
            self.show_world_container(container)
            return True

        discovery = self._record_expanded_cave_discovery(feature)
        day_key, week_key = self._cave_day_key(), self.stronghold_cache_week_key()
        if kind == "survey_station":
            if feature.get("last_week") == week_key:
                self.set_message(f"The survey station has already been used this week.{discovery}")
                return True
            cx, cy, _ex, _ey = self.cave_context_from_key(self.state.current_cave_key)
            revealed = 0
            for mx, my in ((cx, cy), (cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                region = self.wilderness_region_record(mx, my)
                mapped = region.setdefault("mapped_chunks", [])
                map_key = f"{mx},{my}"
                if map_key not in mapped:
                    mapped.append(map_key)
                    revealed += 1
            feature["last_week"] = week_key
            self.autosave_with_message(
                f"Charted {quantity_agreement(revealed, 'nearby surface area')} from the survey station.{discovery}"
            )
            return True
        if kind == "assay_bench":
            if feature.get("last_week") == week_key:
                self.set_message(f"You already sorted this week's loose mineral sample.{discovery}")
                return True
            rng = random.Random(_stable_seed(self.state.wilderness_seed, self.state.current_cave_key, week_key, kind))
            drops = rng.choice(({"Coal": 2}, {"Copper Ore": 1, "Stone": 2}, {"Quartz": 1}, {"Iron Ore": 1}))
            for item, quantity in drops.items():
                self.state.inventory[item] = self.state.inventory.get(item, 0) + quantity
            feature["last_week"] = week_key
            found = ", ".join(quantity_item_phrase(item, qty) for item, qty in drops.items())
            self.autosave_with_message(f"Sorted the assay trays and recovered {found}.{discovery}")
            return True
        if kind in {"fungal_nursery", "bat_roost"}:
            if feature.get("last_week") == week_key:
                self.set_message(f"The {name.lower()} needs time to recover.{discovery}")
                return True
            drops = {"Cave Mushroom": 2, "Cave Herbs": 1} if kind == "fungal_nursery" else {"Bat Guano": 2}
            for item, quantity in drops.items():
                self.state.inventory[item] = self.state.inventory.get(item, 0) + quantity
            feature["last_week"] = week_key
            self.autosave_with_message(f"Gathered from the {name.lower()}.{discovery}")
            return True
        if kind in {"root_well", "thermal_vent"}:
            if feature.get("last_day") == day_key:
                self.set_message(f"You have already recovered here today.{discovery}")
                return True
            before_stamina = int(self.state.stamina)
            self.state.stamina = min(self.max_stamina(), before_stamina + 30)
            try:
                from ascii_farmstead_combat import build_player_combat_profile
                profile = build_player_combat_profile(self.state)
                before_hp = int(self.state.combat_current_hp)
                self.state.combat_current_hp = min(int(profile["max_hp"]), before_hp + max(6, int(profile["max_hp"]) // 8))
                hp = int(self.state.combat_current_hp) - before_hp
            except Exception:
                hp = 0
            feature["last_day"] = day_key
            self.advance_time(20)
            self.autosave_with_message(
                f"Rested at the {name.lower()}: stamina +{int(self.state.stamina) - before_stamina}, health +{hp}.{discovery}"
            )
            return True
        if kind == "tide_pool":
            self.set_message("Equip the Fishing Rod and press F while facing the pool.")
            return True
        messages = {
            "echo_gallery": "You test the chamber and identify a clear route by the returning echoes.",
            "glowworm_wall": "The glowworms brighten in slow waves, marking clean air and flowing water nearby.",
        }
        self.autosave_with_message(f"{messages.get(kind, f'Examined the {name.lower()}.')}{discovery}")
        return True

    def use_expanded_cave_feature_tool(self, tool: str, x: int, y: int) -> bool:
        feature = self.expanded_cave_feature_at(x, y)
        if not feature:
            return False
        kind = str(feature.get("kind", ""))
        required = str(FEATURE_DATA.get(kind, {}).get("tool", ""))
        if kind == "tide_pool" and tool == "Fishing Rod":
            if not self.owns_tool("Fishing Rod"):
                self.set_message("You need a Fishing Rod to fish the underground pool.")
                return True
            self.start_fishing_cast(x, y)
            return True
        if not required:
            return False
        if tool != required:
            self.set_message(f"Use {required} on the {str(feature.get('name', 'cave feature')).lower()}.")
            return True
        if required == "Shovel":
            if not self.owns_tool("Shovel"):
                self.set_message("You need a Shovel to excavate the fossil bed.")
                return True
            self._record_expanded_cave_discovery(feature)
            self.launch_excavation_minigame("paleontology", x, y, f"cave:{self.state.current_cave_key}:{feature.get('id', '')}")
            return True
        if not self.owns_tool("Pickaxe"):
            self.set_message("You need a Pickaxe to work this cave feature.")
            return True
        if bool(feature.get("depleted", False)):
            self.set_message(f"The {str(feature.get('name', 'feature')).lower()} has already been worked out.")
            return True
        if not self.spend_stamina(7 if self.tool_level("Pickaxe") <= 1 else 4):
            return True
        rewards = {
            "calcite_shelf": {"Quartz": 2, "Stone": 1},
            "collapsed_seam": {"Coal": 2, "Copper Ore": 1, "Stone": 2},
            "geode_heart": {"Crystal Shard": 3, "Amethyst": 1, "Quartz": 2},
            "clay_bank": {"Clay": 5},
            "obsidian_seam": {"Coal": 3, "Crystal Shard": 1, "Stone": 2},
            "ice_lens": {"Crystal Shard": 2, "Quartz": 1},
        }.get(kind, {"Stone": 2})
        for item, quantity in rewards.items():
            self.state.inventory[item] = self.state.inventory.get(item, 0) + quantity
        feature["depleted"] = True
        self.active_map()[y][x] = "."
        discovery = self._record_expanded_cave_discovery(feature)
        found = ", ".join(quantity_item_phrase(item, qty) for item, qty in rewards.items())
        self.autosave_with_message(f"Worked the {str(feature.get('name', 'feature')).lower()} and recovered {found}.{discovery}")
        return True
