from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import (
    AUTHORED_TOWN_RESIDENCE_ID_BY_DOOR,
    TOWN_DOORS,
)


HOME_WORLD_VERSION = 2
HOME_CHUNK_WIDTH = 86
HOME_CHUNK_HEIGHT = 38

# The authored maps retain their original scale but are physically separated.
# The town's east boulevard ends at world x=-33, then a 32-tile ravine passage
# crosses open world land before reaching the farm's west lane at world x=0.
LEGACY_HOME_TOWN_ORIGIN_V1 = (-112, -10)
HOME_TOWN_ORIGIN = (-144, -10)
HOME_TOWN_SIZE = (112, 50)
HOME_FARM_ORIGIN = (0, 0)
HOME_FARM_SIZE = (54, 22)
HOME_MINE_DOOR_WORLD = (27, -2)

# This overlay exists only in the newly created gap. It never cuts into either
# authored source map.
HOME_RAVINE_X_RANGE = (-32, -1)
HOME_RAVINE_Y_RANGE = (6, 14)


class SeamlessHomeWorldMixin:
    """Embed the authored town and farm into canonical wilderness coordinates."""

    def home_world_chunk_from_world(self, world_x: int, world_y: int) -> Tuple[int, int, int, int]:
        chunk_x, local_x = divmod(int(world_x), HOME_CHUNK_WIDTH)
        chunk_y, local_y = divmod(int(world_y), HOME_CHUNK_HEIGHT)
        return chunk_x, chunk_y, local_x, local_y

    def home_world_current_world_position(self, x: Optional[int] = None, y: Optional[int] = None) -> Tuple[int, int]:
        local_x = int(self.state.player_x if x is None else x)
        local_y = int(self.state.player_y if y is None else y)
        return self.wilderness_world_coords(
            int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
            local_x, local_y,
        )

    def home_world_source_at_world(self, world_x: int, world_y: int) -> Tuple[str, int, int]:
        town_x = int(world_x) - HOME_TOWN_ORIGIN[0]
        town_y = int(world_y) - HOME_TOWN_ORIGIN[1]
        if 0 <= town_x < HOME_TOWN_SIZE[0] and 0 <= town_y < HOME_TOWN_SIZE[1]:
            return "town", town_x, town_y
        farm_x = int(world_x) - HOME_FARM_ORIGIN[0]
        farm_y = int(world_y) - HOME_FARM_ORIGIN[1]
        farm_height = len(getattr(self, "base_map", []) or [])
        farm_width = len(self.base_map[0]) if farm_height and self.base_map[0] else HOME_FARM_SIZE[0]
        if 0 <= farm_x < farm_width and 0 <= farm_y < farm_height:
            return "farm", farm_x, farm_y
        if 20 <= int(world_x) <= 34 and -11 <= int(world_y) <= 0:
            return "mine", int(world_x) - 20, int(world_y) + 11
        return "", -1, -1

    def legacy_v1_town_source_at_world(self, world_x: int, world_y: int) -> Optional[Tuple[int, int]]:
        source_x = int(world_x) - LEGACY_HOME_TOWN_ORIGIN_V1[0]
        source_y = int(world_y) - LEGACY_HOME_TOWN_ORIGIN_V1[1]
        if 0 <= source_x < HOME_TOWN_SIZE[0] and 0 <= source_y < HOME_TOWN_SIZE[1]:
            return source_x, source_y
        return None

    def home_world_source_at(
        self,
        x: int,
        y: int,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> Tuple[str, int, int]:
        if self.state.location != "Wilderness":
            return "", -1, -1
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        world_x, world_y = self.wilderness_world_coords(cx, cy, int(x), int(y))
        return self.home_world_source_at_world(world_x, world_y)

    def in_seamless_farm_district(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        if self.state.location != "Wilderness":
            return False
        kind, _source_x, _source_y = self.home_world_source_at(
            self.state.player_x if x is None else x,
            self.state.player_y if y is None else y,
        )
        return kind == "farm"

    def in_seamless_town_district(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        if self.state.location != "Wilderness":
            return False
        kind, _source_x, _source_y = self.home_world_source_at(
            self.state.player_x if x is None else x,
            self.state.player_y if y is None else y,
        )
        return kind == "town"

    def home_world_town_source_position(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        kind, source_x, source_y = self.home_world_source_at(x, y)
        return (source_x, source_y) if kind == "town" else None

    def home_world_farm_source_position(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        kind, source_x, source_y = self.home_world_source_at(x, y)
        return (source_x, source_y) if kind == "farm" else None

    def home_world_world_for_town_position(self, x: int, y: int) -> Tuple[int, int]:
        return HOME_TOWN_ORIGIN[0] + int(x), HOME_TOWN_ORIGIN[1] + int(y)

    def home_world_world_for_farm_position(self, x: int, y: int) -> Tuple[int, int]:
        return HOME_FARM_ORIGIN[0] + int(x), HOME_FARM_ORIGIN[1] + int(y)

    def home_world_ravine_tile_at_world(self, world_x: int, world_y: int) -> str:
        """Return the authored town/farm approach surface, or an empty string."""
        wx, wy = int(world_x), int(world_y)
        if not (
            HOME_RAVINE_X_RANGE[0] <= wx <= HOME_RAVINE_X_RANGE[1]
            and HOME_RAVINE_Y_RANGE[0] <= wy <= HOME_RAVINE_Y_RANGE[1]
        ):
            return ""
        distance = abs(wy - 10)
        if distance <= 2:
            return ":"
        if distance == 3:
            return ","
        return "#"

    def home_world_ravine_tile_at(
        self,
        x: int,
        y: int,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> str:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        world_x, world_y = self.wilderness_world_coords(cx, cy, int(x), int(y))
        return self.home_world_ravine_tile_at_world(world_x, world_y)

    def home_world_destination_world_positions(self) -> Dict[str, Tuple[int, int]]:
        """Canonical road arrivals, expressed in global world coordinates."""
        return {
            "town": self.home_world_world_for_town_position(58, 1),
            "farm": self.home_world_world_for_farm_position(1, 10),
            "mine": (HOME_MINE_DOOR_WORLD[0], HOME_MINE_DOOR_WORLD[1] + 1),
        }

    def home_world_town_door_at(self, x: int, y: int) -> str:
        position = self.home_world_town_source_position(x, y)
        if position is None:
            return ""
        for building_id, door in TOWN_DOORS.items():
            if tuple(door) == position:
                return str(building_id)
        if position in AUTHORED_TOWN_RESIDENCE_ID_BY_DOOR:
            return f"residence:{AUTHORED_TOWN_RESIDENCE_ID_BY_DOOR[position]}"
        return ""

    def enter_seamless_home_world_door(self, x: int, y: int) -> bool:
        if self.home_world_is_farmhouse_door(x, y):
            self.transition_to_house()
            return True
        if self.home_world_is_mine_door(x, y):
            self.transition_to_mine(return_location="WildernessOrigin")
            return True
        building_id = self.home_world_town_door_at(x, y)
        if not building_id:
            return False
        if building_id.startswith("residence:"):
            return bool(self.enter_authored_town_residence(building_id.split(":", 1)[1]))
        method_name = {
            "general_store": "transition_to_general_store",
            "blacksmith": "transition_to_blacksmith_interior",
            "library": "transition_to_library_interior",
            "mayor_house": "transition_to_mayor_house",
            "inn": "transition_to_inn_interior",
            "furniture_store": "transition_to_furniture_store",
            "carpenter": "transition_to_carpenter_store",
            "animal_store": "transition_to_animal_store",
            "clinic": "transition_to_clinic",
            "town_hall": "transition_to_town_hall",
            "market_row": "transition_to_market_row",
            "museum": "transition_to_museum",
        }.get(building_id, "")
        if not method_name:
            return False
        getattr(self, method_name)()
        return True

    def home_world_is_farmhouse_door(self, x: int, y: int) -> bool:
        return self.home_world_farm_source_position(x, y) == (5, 5)

    def home_world_is_mine_door(self, x: int, y: int) -> bool:
        world_x, world_y = self.home_world_current_world_position(x, y)
        return (world_x, world_y) == HOME_MINE_DOOR_WORLD

    def home_world_open_perimeter_at(
        self, kind: str, source_x: int, source_y: int
    ) -> bool:
        """Identify obsolete authored-map edge walls removed by the seamless world."""
        sx, sy = int(source_x), int(source_y)
        if kind == "town":
            height = len(self.town_map)
            width = len(self.town_map[sy]) if 0 <= sy < height else 0
            return bool(
                width
                and (sx in {0, width - 1} or sy in {0, height - 1})
                and self.town_map[sy][sx] == "#"
            )
        if kind == "farm":
            height = len(self.base_map)
            width = len(self.base_map[sy]) if 0 <= sy < height else 0
            return bool(
                width
                and (sx in {0, width - 1} or sy in {0, height - 1})
                and self.base_map[sy][sx] == "#"
            )
        return False

    def home_world_natural_underlay_tile(self, world_x: int, world_y: int) -> str:
        """Return deterministic wilderness terrain beneath an obsolete edge wall."""
        wx, wy = int(world_x), int(world_y)
        if self.wilderness_world_water_tile(wx, wy):
            return "~"
        return self.wilderness_world_biome_tile(wx, wy)

    def home_world_chunk_is_authored(self, chunk_x: int, chunk_y: int) -> bool:
        chunk_left = int(chunk_x) * HOME_CHUNK_WIDTH
        chunk_top = int(chunk_y) * HOME_CHUNK_HEIGHT
        chunk_right = chunk_left + HOME_CHUNK_WIDTH - 1
        chunk_bottom = chunk_top + HOME_CHUNK_HEIGHT - 1
        farm_height = len(getattr(self, "base_map", []) or [])
        farm_width = len(self.base_map[0]) if farm_height and self.base_map[0] else HOME_FARM_SIZE[0]
        authored_rectangles = (
            (HOME_TOWN_ORIGIN[0], HOME_TOWN_ORIGIN[1],
             HOME_TOWN_ORIGIN[0] + HOME_TOWN_SIZE[0] - 1,
             HOME_TOWN_ORIGIN[1] + HOME_TOWN_SIZE[1] - 1),
            (HOME_FARM_ORIGIN[0], HOME_FARM_ORIGIN[1],
             HOME_FARM_ORIGIN[0] + farm_width - 1,
             HOME_FARM_ORIGIN[1] + farm_height - 1),
            (20, -11, 34, 0),
        )
        return any(
            chunk_left <= right and chunk_right >= left
            and chunk_top <= bottom and chunk_bottom >= top
            for left, top, right, bottom in authored_rectangles
        )

    def home_world_authored_chunks(self) -> List[Tuple[int, int]]:
        farm_height = len(getattr(self, "base_map", []) or [])
        farm_width = len(self.base_map[0]) if farm_height and self.base_map[0] else HOME_FARM_SIZE[0]
        min_world_x = min(HOME_TOWN_ORIGIN[0], HOME_FARM_ORIGIN[0], 20)
        min_world_y = min(HOME_TOWN_ORIGIN[1], HOME_FARM_ORIGIN[1], -10)
        max_world_x = max(
            HOME_TOWN_ORIGIN[0] + HOME_TOWN_SIZE[0] - 1,
            HOME_FARM_ORIGIN[0] + farm_width - 1,
            34,
        )
        max_world_y = max(
            HOME_TOWN_ORIGIN[1] + HOME_TOWN_SIZE[1] - 1,
            HOME_FARM_ORIGIN[1] + farm_height - 1,
            0,
        )
        min_chunk_x = min_world_x // HOME_CHUNK_WIDTH
        max_chunk_x = max_world_x // HOME_CHUNK_WIDTH
        min_chunk_y = min_world_y // HOME_CHUNK_HEIGHT
        max_chunk_y = max_world_y // HOME_CHUNK_HEIGHT
        return [
            (chunk_x, chunk_y)
            for chunk_y in range(min_chunk_y, max_chunk_y + 1)
            for chunk_x in range(min_chunk_x, max_chunk_x + 1)
            if self.home_world_chunk_is_authored(chunk_x, chunk_y)
        ]

    def _stamp_home_world_tile(
        self, grid: List[List[str]], chunk_x: int, chunk_y: int,
        world_x: int, world_y: int, tile: str,
    ) -> None:
        local_x = int(world_x) - int(chunk_x) * HOME_CHUNK_WIDTH
        local_y = int(world_y) - int(chunk_y) * HOME_CHUNK_HEIGHT
        if 0 <= local_y < len(grid) and grid and 0 <= local_x < len(grid[0]):
            grid[local_y][local_x] = str(tile)[:1]

    def apply_seamless_home_world_chunk(
        self,
        grid: List[List[str]],
        chunk_x: int,
        chunk_y: int,
        *,
        include_farm: bool = True,
    ) -> None:
        if not grid or not self.home_world_chunk_is_authored(chunk_x, chunk_y):
            return

        # Replace obsolete rectangular map-edge walls with the natural terrain
        # beneath them. This is explicit rather than transparent so old saved
        # chunks lose the wall too.
        for source_y, row in enumerate(self.town_map):
            for source_x, raw_tile in enumerate(row):
                tile = str(raw_tile)[:1]
                world_x, world_y = self.home_world_world_for_town_position(source_x, source_y)
                if self.home_world_open_perimeter_at("town", source_x, source_y):
                    tile = self.home_world_natural_underlay_tile(world_x, world_y)
                self._stamp_home_world_tile(grid, chunk_x, chunk_y, world_x, world_y, tile)

        if include_farm:
            for source_y, row in enumerate(self.base_map):
                for source_x, raw_tile in enumerate(row):
                    tile = str(raw_tile)[:1]
                    # The obsolete direct mine transition becomes an ordinary
                    # path to the mine building immediately north of the fence.
                    if source_y == 0 and 25 <= source_x <= 29:
                        tile = ":"
                    world_x, world_y = self.home_world_world_for_farm_position(source_x, source_y)
                    if self.home_world_open_perimeter_at("farm", source_x, source_y):
                        tile = self.home_world_natural_underlay_tile(world_x, world_y)
                    self._stamp_home_world_tile(grid, chunk_x, chunk_y, world_x, world_y, tile)

        # A broad, uncluttered ravine road crosses only the physical gap between
        # the two districts. Neither authored source map is modified by it.
        for world_y in range(HOME_RAVINE_Y_RANGE[0], HOME_RAVINE_Y_RANGE[1] + 1):
            for world_x in range(HOME_RAVINE_X_RANGE[0], HOME_RAVINE_X_RANGE[1] + 1):
                tile = self.home_world_ravine_tile_at_world(world_x, world_y)
                if tile:
                    self._stamp_home_world_tile(grid, chunk_x, chunk_y, world_x, world_y, tile)

        # Full physical mine entrance and forecourt. Only its door transitions
        # underground; every exterior approach is normal world movement.
        for world_y in range(-10, -1):
            for world_x in range(21, 34):
                edge = world_x in {21, 33} or world_y in {-10, -2}
                tile = "#" if edge else "H"
                self._stamp_home_world_tile(grid, chunk_x, chunk_y, world_x, world_y, tile)
        for world_y in range(-2, 2):
            self._stamp_home_world_tile(grid, chunk_x, chunk_y, 27, world_y, ":")
        self._stamp_home_world_tile(
            grid, chunk_x, chunk_y,
            HOME_MINE_DOOR_WORLD[0], HOME_MINE_DOOR_WORLD[1], "V",
        )

    def refresh_seamless_town_layer(self) -> None:
        if not isinstance(getattr(self, "wilderness_maps", None), dict):
            return
        for chunk_x, chunk_y in self.home_world_authored_chunks():
            grid = self.wilderness_maps.get(self.wilderness_chunk_key(chunk_x, chunk_y))
            if grid:
                self.apply_seamless_home_world_chunk(
                    grid, chunk_x, chunk_y, include_farm=False,
                )

    def sync_seamless_farm_to_base_map(self) -> None:
        if int(getattr(self.state, "seamless_home_world_version", 0) or 0) < 1:
            return
        for farm_y, row in enumerate(self.base_map):
            for farm_x in range(len(row)):
                world_x, world_y = self.home_world_world_for_farm_position(farm_x, farm_y)
                chunk_x, chunk_y, local_x, local_y = self.home_world_chunk_from_world(world_x, world_y)
                grid = (getattr(self, "wilderness_maps", {}) or {}).get(
                    self.wilderness_chunk_key(chunk_x, chunk_y)
                )
                if grid and 0 <= local_y < len(grid) and 0 <= local_x < len(grid[local_y]):
                    tile = str(grid[local_y][local_x])[:1]
                    if farm_y == 0 and 25 <= farm_x <= 29 and tile == ":":
                        tile = "<"
                    self.base_map[farm_y][farm_x] = tile

    def refresh_seamless_farm_layer(self) -> None:
        if not isinstance(getattr(self, "wilderness_maps", None), dict):
            return
        for chunk_x, chunk_y in self.home_world_authored_chunks():
            key = self.wilderness_chunk_key(chunk_x, chunk_y)
            grid = self.wilderness_maps.get(key)
            if grid is None:
                continue
            self.apply_seamless_home_world_chunk(
                grid, chunk_x, chunk_y, include_farm=True,
            )

    def set_player_home_world_position(
        self, world_x: int, world_y: int, *, facing: str = "DOWN",
    ) -> None:
        chunk_x, chunk_y, local_x, local_y = self.home_world_chunk_from_world(world_x, world_y)
        self.state.location = "Wilderness"
        self.state.wilderness_chunk_x = chunk_x
        self.state.wilderness_chunk_y = chunk_y
        self.wilderness_map = self.get_wilderness_chunk_map(chunk_x, chunk_y)
        self.state.player_x = local_x
        self.state.player_y = local_y
        self.state.facing = str(facing)
        self.discover_wilderness_chunk(chunk_x, chunk_y)
        self.invalidate_draw_cache()

    def return_to_seamless_town(self, source_x: int, source_y: int, *, facing: str = "DOWN") -> None:
        world_x, world_y = self.home_world_world_for_town_position(source_x, source_y)
        self.set_player_home_world_position(world_x, world_y, facing=facing)

    def return_to_seamless_farm(self, source_x: int, source_y: int, *, facing: str = "DOWN") -> None:
        world_x, world_y = self.home_world_world_for_farm_position(source_x, source_y)
        self.set_player_home_world_position(world_x, world_y, facing=facing)
        self.update_farm_animal_actors(force=True)

    def ensure_seamless_home_world(self) -> None:
        if not isinstance(getattr(self, "wilderness_maps", None), dict):
            self.wilderness_maps = {}
        old_version = int(getattr(self.state, "seamless_home_world_version", 0) or 0)
        rebuilding = old_version < HOME_WORLD_VERSION

        old_location = str(self.state.location)
        old_x, old_y = int(self.state.player_x), int(self.state.player_y)
        old_chunk_x = int(getattr(self.state, "wilderness_chunk_x", 0))
        old_chunk_y = int(getattr(self.state, "wilderness_chunk_y", 0))
        legacy_town_source = None
        if old_version == 1 and old_location == "Wilderness":
            old_world_x, old_world_y = self.wilderness_world_coords(
                old_chunk_x, old_chunk_y, old_x, old_y,
            )
            legacy_town_source = self.legacy_v1_town_source_at_world(
                old_world_x, old_world_y,
            )
        authored_chunks = set(self.home_world_authored_chunks())
        chunks_to_prepare = {
            point for point in authored_chunks
            if self.wilderness_chunk_key(*point) in self.wilderness_maps
        }
        if old_location == "Farm":
            migration_world = self.home_world_world_for_farm_position(old_x, old_y)
            chunks_to_prepare.add(self.home_world_chunk_from_world(*migration_world)[:2])
        elif old_location == "Town":
            migration_world = self.home_world_world_for_town_position(old_x, old_y)
            chunks_to_prepare.add(self.home_world_chunk_from_world(*migration_world)[:2])
        elif old_location == "Wilderness":
            current_chunk = (
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
            )
            if current_chunk in authored_chunks:
                chunks_to_prepare.add(current_chunk)
            if legacy_town_source is not None:
                migration_world = self.home_world_world_for_town_position(*legacy_town_source)
                chunks_to_prepare.add(self.home_world_chunk_from_world(*migration_world)[:2])

        for chunk_x, chunk_y in sorted(chunks_to_prepare):
            key = self.wilderness_chunk_key(chunk_x, chunk_y)
            if rebuilding or key not in self.wilderness_maps:
                self.wilderness_maps[key] = self.make_wilderness_chunk(chunk_x, chunk_y)
            self.apply_seamless_home_world_chunk(
                self.wilderness_maps[key], chunk_x, chunk_y,
                include_farm=rebuilding,
            )

        self.state.seamless_home_world_version = HOME_WORLD_VERSION
        if old_location == "Farm":
            world_x, world_y = self.home_world_world_for_farm_position(old_x, old_y)
            self.set_player_home_world_position(world_x, world_y, facing=str(self.state.facing))
        elif old_location == "Town":
            world_x, world_y = self.home_world_world_for_town_position(old_x, old_y)
            self.set_player_home_world_position(world_x, world_y, facing=str(self.state.facing))
        elif old_location == "Wilderness" and legacy_town_source is not None:
            world_x, world_y = self.home_world_world_for_town_position(*legacy_town_source)
            self.set_player_home_world_position(world_x, world_y, facing=str(self.state.facing))
        elif self.state.location == "Wilderness":
            key = self.wilderness_chunk_key()
            self.wilderness_map = self.wilderness_maps.get(key) or self.get_wilderness_chunk_map()

        if old_location in {"Farm", "Town"}:
            for record in (getattr(self.state, "travel_follower_states", {}) or {}).values():
                if not isinstance(record, dict) or str(record.get("location", "")) != old_location:
                    continue
                try:
                    follower_x, follower_y = int(record.get("x", -1)), int(record.get("y", -1))
                except (TypeError, ValueError):
                    follower_x, follower_y = -1, -1
                record["location"] = "Wilderness"
                if follower_x < 0 or follower_y < 0:
                    continue
                follower_world = (
                    self.home_world_world_for_farm_position(follower_x, follower_y)
                    if old_location == "Farm"
                    else self.home_world_world_for_town_position(follower_x, follower_y)
                )
                follower_chunk_x, follower_chunk_y, local_x, local_y = self.home_world_chunk_from_world(
                    *follower_world,
                )
                if (follower_chunk_x, follower_chunk_y) == (
                    int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
                ):
                    record["x"], record["y"] = local_x, local_y
                else:
                    record["x"], record["y"] = -1, -1
                    if str(record.get("mode", "")) == "follow":
                        record["activity"] = "catching up nearby"
        elif old_location == "Wilderness" and legacy_town_source is not None:
            for record in (getattr(self.state, "travel_follower_states", {}) or {}).values():
                if not isinstance(record, dict) or str(record.get("location", "")) != "Wilderness":
                    continue
                try:
                    follower_x, follower_y = int(record.get("x", -1)), int(record.get("y", -1))
                except (TypeError, ValueError):
                    follower_x, follower_y = -1, -1
                if follower_x < 0 or follower_y < 0:
                    continue
                follower_world = self.wilderness_world_coords(
                    old_chunk_x, old_chunk_y, follower_x, follower_y,
                )
                follower_source = self.legacy_v1_town_source_at_world(*follower_world)
                if follower_source is not None:
                    follower_world = self.home_world_world_for_town_position(*follower_source)
                follower_chunk_x, follower_chunk_y, local_x, local_y = self.home_world_chunk_from_world(
                    *follower_world,
                )
                if (follower_chunk_x, follower_chunk_y) == (
                    int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
                ):
                    record["x"], record["y"] = local_x, local_y
                else:
                    record["x"], record["y"] = -1, -1
                    if str(record.get("mode", "")) == "follow":
                        record["activity"] = "catching up nearby"

        self.ensure_wilderness_chunk_runtime_caches()
        for chunk_x, chunk_y in chunks_to_prepare:
            key = self.wilderness_chunk_key(chunk_x, chunk_y)
            self.wilderness_static_checked_chunks.add(key)
            self.wilderness_balanced_chunks.add(key)
            self.wilderness_procedural_town_checked_chunks.add(key)
            self.repaired_wilderness_chunks.add(key)

    def seamless_home_world_summary(self) -> Dict[str, object]:
        return {
            "version": int(getattr(self.state, "seamless_home_world_version", 0) or 0),
            "town_origin": HOME_TOWN_ORIGIN,
            "town_size": HOME_TOWN_SIZE,
            "farm_origin": HOME_FARM_ORIGIN,
            "farm_size": (self.farm_width(), self.farm_height()),
            "mine_door": HOME_MINE_DOOR_WORLD,
            "ravine_passage": (HOME_RAVINE_X_RANGE, HOME_RAVINE_Y_RANGE),
            "chunks": self.home_world_authored_chunks(),
        }
