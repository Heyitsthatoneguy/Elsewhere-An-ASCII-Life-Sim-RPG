from __future__ import annotations

"""Modular public interiors and legacy residences for the starting town."""

import copy
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ascii_farmstead_procedural_interiors import (
    build_procedural_ground_floor,
    procedural_interior_room_plan,
)
from ascii_farmstead_procedural_furnishing import FurniturePlacement


Room = Tuple[int, int, int, int]
Opening = Tuple[int, int, str]
Fixture = Tuple[int, int, str]


# Public starting-town interiors now use the modular architecture system.  The
# old blueprints below remain readable for legacy editor records and migration,
# but they are no longer the runtime source of these buildings.
AUTHORED_MODULAR_LAYOUTS: Dict[str, Tuple[str, int, int]] = {
    "general_store": ("general_store", 0, 2),
    "blacksmith": ("workshop", 1, 2),
    "library": ("library", 2, 2),
    "museum": ("library", 3, 2),
    "mayor_house": ("home", 1, 2),
    "inn": ("inn", 2, 2),
    "furniture_store": ("general_store", 3, 2),
    "carpenter": ("carpenter", 0, 2),
    "animal_store": ("general_store", 2, 2),
    "clinic": ("clinic", 2, 2),
    "town_hall": ("town_hall", 3, 2),
    "market_row": ("market_stall", 0, 2),
}

AUTHORED_REQUIRED_FIXTURES: Dict[str, Tuple[str, ...]] = {
    "general_store": ("P", "s", "f", "b", "t"),
    "blacksmith": ("P", "a", "f", "o", "q", "w", "t"),
    "library": ("P", "A", "l", "t"),
    "museum": ("d", "P", "C", "F", "G", "M", "A", "E", "S"),
    "mayor_house": ("P", "F", "d", "B"),
    "inn": ("P", "B", "k", "p", "1", "3", "5"),
    "furniture_store": ("P", "C", "m", "A"),
    "carpenter": ("P", "b", "w", "t"),
    "animal_store": ("P", "m", "c", "p", "h", "f"),
    "clinic": ("P", "e", "m", "b", "s"),
    "town_hall": ("P", "p", "r", "m", "n"),
    "market_row": ("P", "v", "f", "r", "t", "m"),
}

_AUTHORED_MODULAR_CACHE: Dict[
    str, Tuple[Tuple[str, ...], Tuple[FurniturePlacement, ...]]
] = {}


def _authored_reachable_floor(
    grid: List[List[str]],
    catalog_walkable: Set[Tuple[int, int]],
) -> Set[Tuple[int, int]]:
    passable = {
        (x, y)
        for y, row in enumerate(grid)
        for x, glyph in enumerate(row)
        if glyph in {".", ",", "D", "|", "_"} or (x, y) in catalog_walkable
    }
    doors = [
        (x, y)
        for y, row in enumerate(grid)
        for x, glyph in enumerate(row)
        if glyph == "D"
    ]
    if not doors:
        return set()
    door_x, door_y = doors[0]
    adjacent = [
        (door_x + dx, door_y + dy)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        if (door_x + dx, door_y + dy) in passable
        and grid[door_y + dy][door_x + dx] != "D"
    ]
    if not adjacent:
        return set()
    reached = {adjacent[0]}
    frontier = [adjacent[0]]
    while frontier:
        x, y = frontier.pop()
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if neighbor in passable and neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return reached


AUTHORED_INTERIOR_BLUEPRINTS: Dict[str, Dict[str, object]] = {
    "general_store": {
        "size": (29, 12),
        "rooms": ((7, 4, 21, 11), (0, 2, 7, 11), (21, 0, 28, 5), (21, 5, 28, 11)),
        "openings": ((7, 8, "."), (21, 4, "_"), (21, 8, "_")),
        "fixtures": ((11, 5, "$"), (12, 5, "-"), (13, 5, "&"), (14, 5, "-"), (15, 5, "$"),
                     (2, 4, "s"), (4, 4, "f"), (4, 6, "b"), (2, 7, "z"), (4, 9, "X"), (24, 2, "B"), (26, 2, "N"),
                     (24, 7, "d"), (26, 7, "H"), (25, 9, "P"), (10, 9, "t")),
        "exit": (14, 11),
    },
    "blacksmith": {
        "size": (37, 14),
        "rooms": ((9, 8, 27, 13), (0, 4, 9, 13), (9, 1, 23, 8), (23, 0, 36, 10)),
        "openings": ((9, 10, "."), (17, 8, "."), (23, 6, "."), (27, 9, ".")),
        "fixtures": ((13, 6, "$"), (14, 6, "-"), (15, 6, "&"), (16, 6, "-"), (17, 6, "$"),
                     (3, 6, "a"), (6, 8, "o"), (3, 10, "X"), (28, 3, "f"), (32, 3, "q"),
                     (28, 6, "w"), (32, 7, "x"), (20, 3, "P"), (18, 11, "t")),
        "exit": (18, 13),
    },
    "library": {
        "size": (39, 14),
        "rooms": ((11, 8, 28, 13), (0, 1, 11, 11), (11, 0, 28, 8), (28, 3, 38, 11)),
        "openings": ((11, 9, "."), (19, 8, "."), (28, 9, "."), (28, 5, "_")),
        "fixtures": ((3, 3, "H"), (7, 3, "H"), (3, 6, "l"), (7, 8, "i"),
                     (14, 2, "l"), (19, 2, "l"), (24, 2, "l"), (15, 5, "c"), (17, 5, "t"),
                     (21, 5, "t"), (23, 5, "c"), (31, 5, "A"), (34, 5, "g"), (33, 8, "P"),
                     (16, 10, "-"), (17, 10, "&"), (18, 10, "-"), (23, 11, "t")),
        "exit": (20, 13),
    },
    "museum": {
        "size": (41, 15),
        "rooms": ((13, 9, 28, 14), (0, 5, 13, 12), (4, 0, 18, 5), (18, 0, 36, 6), (28, 6, 40, 13)),
        "openings": ((13, 10, "."), (10, 5, "."), (18, 4, "."), (28, 10, "."), (28, 6, "_")),
        "fixtures": ((3, 7, "C"), (8, 7, "G"), (6, 10, "V"), (7, 2, "A"), (13, 2, "S"),
                     (22, 2, "F"), (28, 2, "M"), (33, 3, "E"), (32, 8, "d"), (36, 8, "P"),
                     (18, 10, "$"), (19, 10, "-"), (20, 10, "&"), (21, 10, "-"), (22, 10, "$")),
        "exit": (20, 14),
    },
    "mayor_house": {
        "size": (35, 14),
        "rooms": ((10, 8, 25, 13), (0, 3, 10, 12), (10, 1, 22, 8), (22, 0, 34, 10)),
        "openings": ((10, 9, "_"), (16, 8, "."), (22, 6, "."), (25, 9, ".")),
        "fixtures": ((3, 5, "B"), (7, 5, "u"), (4, 9, "N"), (13, 3, "k"), (19, 3, "p"),
                     (15, 6, "t"), (14, 6, "c"), (27, 3, "d"), (31, 3, "P"), (29, 6, "F"),
                     (27, 8, "&"), (14, 10, "c"), (17, 10, "t"), (20, 10, "c")),
        "exit": (18, 13),
    },
    "inn": {
        "size": (43, 15),
        "rooms": ((14, 4, 28, 14), (14, 0, 28, 4),
                  (0, 0, 7, 5), (7, 0, 14, 5), (0, 5, 7, 10), (7, 5, 14, 10),
                  (28, 0, 35, 5), (35, 0, 42, 5), (28, 5, 35, 10), (35, 5, 42, 10)),
        "openings": ((18, 4, "."), (3, 5, "_"), (10, 5, "_"), (7, 7, "_"), (14, 7, "_"),
                     (31, 5, "_"), (38, 5, "_"), (28, 7, "_"), (35, 7, "_")),
        "fixtures": ((2, 2, "B"), (9, 2, "B"), (2, 7, "B"), (9, 7, "B"),
                     (30, 2, "B"), (37, 2, "B"), (30, 7, "B"), (37, 7, "B"),
                     (17, 2, "k"), (25, 2, "p"), (18, 6, "$"), (19, 6, "-"), (20, 6, "&"),
                     (21, 6, "-"), (22, 6, "$"), (25, 6, "P"), (18, 10, "c"), (20, 10, "t"),
                     (22, 10, "c"), (17, 12, "1"), (21, 12, "3"), (25, 12, "5")),
        "exit": (21, 14),
    },
    "furniture_store": {
        "size": (37, 13),
        "rooms": ((0, 3, 27, 12), (27, 0, 36, 7), (27, 7, 36, 12), (8, 0, 21, 3)),
        "openings": ((27, 5, "."), (27, 9, "_"), (14, 3, ".")),
        "fixtures": ((4, 5, "Q"), (8, 5, "R"), (6, 7, "t"), (12, 7, "T"), (17, 5, "C"),
                     (21, 5, "L"), (4, 10, "m"), (9, 10, "A"), (15, 10, "U"), (21, 10, "!"),
                     (11, 1, "$"), (12, 1, "-"), (13, 1, "&"), (14, 1, "-"), (15, 1, "$"),
                     (30, 2, "z"), (33, 3, "y"), (30, 9, "d"), (33, 9, "P")),
        "exit": (14, 12),
    },
    "carpenter": {
        "size": (39, 14),
        "rooms": ((12, 8, 29, 13), (0, 2, 12, 13), (12, 1, 26, 8), (26, 0, 38, 10)),
        "openings": ((12, 10, "."), (19, 8, "."), (26, 6, "."), (29, 9, ".")),
        "fixtures": ((3, 4, "w"), (8, 4, "a"), (3, 8, "x"), (8, 10, "X"),
                     (15, 3, "$"), (16, 3, "-"), (17, 3, "&"), (18, 3, "-"), (19, 3, "$"),
                     (22, 5, "P"), (30, 3, "H"), (34, 3, "z"), (31, 7, "t"), (35, 7, "s"),
                     (18, 10, "b"), (23, 11, "c")),
        "exit": (21, 13),
    },
    "animal_store": {
        "size": (37, 14),
        "rooms": ((9, 8, 27, 13), (0, 3, 9, 12), (9, 1, 23, 8), (23, 2, 36, 11)),
        "openings": ((9, 10, "."), (16, 8, "."), (23, 6, "."), (27, 9, ".")),
        "fixtures": ((3, 5, "h"), (6, 8, "c"), (3, 10, "f"), (12, 3, "$"), (13, 3, "-"),
                     (14, 3, "&"), (15, 3, "-"), (16, 3, "$"), (20, 5, "P"),
                     (27, 4, "p"), (32, 4, "X"), (27, 8, "m"), (32, 8, "z")),
        "exit": (18, 13),
    },
    "clinic": {
        "size": (39, 14),
        "rooms": ((12, 8, 27, 13), (0, 3, 12, 12), (12, 1, 26, 8), (26, 1, 38, 8), (27, 8, 38, 13)),
        "openings": ((12, 10, "_"), (18, 8, "."), (26, 5, "_"), (27, 10, ".")),
        "fixtures": ((3, 5, "b"), (8, 5, "e"), (3, 9, "+"), (8, 9, "m"),
                     (15, 3, "$"), (16, 3, "-"), (17, 3, "&"), (18, 3, "-"), (19, 3, "$"),
                     (23, 5, "P"), (29, 3, "s"), (34, 3, "g"), (30, 10, "c"), (34, 10, "c")),
        "exit": (20, 13),
    },
    "town_hall": {
        "size": (41, 15),
        "rooms": ((12, 9, 29, 14), (8, 2, 33, 9), (0, 4, 8, 12), (33, 2, 40, 9), (29, 9, 40, 14)),
        "openings": ((20, 9, "."), (8, 7, "_"), (33, 6, "_"), (29, 11, ".")),
        "fixtures": ((12, 4, "c"), (16, 4, "c"), (20, 4, "T"), (24, 4, "c"), (28, 4, "c"),
                     (17, 7, "$"), (18, 7, "-"), (19, 7, "&"), (20, 7, "-"), (21, 7, "$"),
                     (3, 6, "r"), (5, 9, "n"), (35, 4, "d"), (37, 7, "P"),
                     (32, 11, "p"), (36, 11, "m"), (17, 11, "c"), (23, 11, "c")),
        "exit": (20, 14),
    },
    "market_row": {
        "size": (43, 14),
        "rooms": ((8, 8, 35, 13), (0, 1, 10, 10), (10, 0, 22, 8), (22, 0, 34, 8), (35, 2, 42, 11)),
        "openings": ((8, 9, "."), (16, 8, "."), (28, 8, "."), (35, 9, ".")),
        "fixtures": ((3, 3, "v"), (7, 3, "z"), (3, 7, "f"), (13, 2, "m"), (18, 2, "r"),
                     (13, 5, "$"), (14, 5, "-"), (15, 5, "&"), (16, 5, "-"),
                     (25, 2, "v"), (30, 2, "f"), (26, 5, "t"), (37, 4, "s"), (39, 7, "P"),
                     (14, 10, "c"), (18, 10, "t"), (22, 10, "c"), (28, 10, "T")),
        "exit": (22, 13),
    },
}


AUTHORED_RESIDENCE_BLUEPRINTS: Dict[str, Dict[str, object]] = {
    "meadow_cottage": {"size": (29, 12), "rooms": ((8, 6, 21, 11), (0, 1, 8, 10), (8, 0, 21, 6), (21, 2, 28, 10)), "openings": ((8, 8, "_"), (14, 6, "."), (21, 7, ".")), "fixtures": ((2, 3, "B"), (2, 7, "B"), (5, 3, "u"), (11, 2, "k"), (18, 2, "p"), (13, 4, "t"), (12, 4, "c"), (24, 4, "B"), (24, 8, "B"), (25, 8, "s"), (12, 8, "r")), "exit": (15, 11)},
    "forge_house": {"size": (31, 13), "rooms": ((9, 7, 22, 12), (0, 2, 9, 11), (9, 0, 22, 7), (22, 3, 30, 12)), "openings": ((9, 9, "_"), (15, 7, "."), (22, 9, ".")), "fixtures": ((2, 4, "B"), (2, 8, "B"), (6, 8, "u"), (12, 2, "k"), (18, 2, "p"), (14, 5, "t"), (25, 5, "B"), (25, 9, "B"), (27, 9, "s"), (13, 9, "r")), "exit": (16, 12)},
    "canal_house": {"size": (33, 12), "rooms": ((11, 6, 24, 11), (0, 3, 11, 11), (11, 0, 24, 6), (24, 1, 32, 9)), "openings": ((11, 8, "_"), (17, 6, "."), (24, 5, ".")), "fixtures": ((3, 5, "B"), (3, 8, "B"), (7, 8, "u"), (13, 2, "k"), (21, 2, "p"), (17, 4, "t"), (27, 3, "B"), (28, 7, "s"), (16, 8, "r")), "exit": (18, 11)},
    "cedar_house": {"size": (30, 13), "rooms": ((7, 7, 22, 12), (0, 0, 10, 7), (10, 1, 22, 7), (22, 4, 29, 12)), "openings": ((8, 7, "_"), (10, 5, "."), (16, 7, "."), (22, 9, ".")), "fixtures": ((2, 2, "B"), (6, 5, "u"), (12, 3, "k"), (19, 3, "p"), (15, 5, "t"), (25, 6, "B"), (25, 10, "B"), (26, 10, "s"), (14, 9, "r")), "exit": (15, 12)},
    "market_house": {"size": (34, 12), "rooms": ((10, 6, 25, 11), (0, 1, 10, 10), (10, 0, 25, 6), (25, 2, 33, 10)), "openings": ((10, 8, "_"), (17, 6, "."), (25, 7, "_")), "fixtures": ((3, 3, "B"), (7, 7, "s"), (13, 2, "k"), (21, 2, "p"), (17, 4, "t"), (28, 4, "B"), (28, 8, "B"), (30, 8, "u"), (15, 8, "r")), "exit": (18, 11)},
    "scholar_house": {"size": (32, 13), "rooms": ((9, 7, 23, 12), (0, 1, 9, 11), (9, 0, 23, 7), (23, 1, 31, 11)), "openings": ((9, 9, "_"), (16, 7, "."), (23, 8, "_")), "fixtures": ((2, 3, "B"), (2, 8, "B"), (6, 6, "l"), (12, 2, "k"), (19, 2, "p"), (15, 5, "t"), (26, 3, "B"), (26, 8, "B"), (28, 7, "l"), (14, 9, "r")), "exit": (16, 12)},
}


def _build_blueprint(spec: Dict[str, object], width: int, height: int) -> List[List[str]]:
    local_width, local_height = spec["size"]
    local = [[" " for _ in range(int(local_width))] for _ in range(int(local_height))]
    for x1, y1, x2, y2 in spec.get("rooms", ()):  # type: ignore[assignment]
        for y in range(int(y1), int(y2) + 1):
            for x in range(int(x1), int(x2) + 1):
                local[y][x] = "#" if x in {x1, x2} or y in {y1, y2} else "."
    for x, y, glyph in spec.get("openings", ()):  # type: ignore[assignment]
        local[int(y)][int(x)] = str(glyph)[:1]
    for x, y, glyph in spec.get("fixtures", ()):  # type: ignore[assignment]
        if local[int(y)][int(x)] in {".", ",", ":"}:
            local[int(y)][int(x)] = str(glyph)[:1]
    exit_x, exit_y = spec["exit"]
    local[int(exit_y)][int(exit_x)] = "D"
    grid = [[" " for _ in range(width)] for _ in range(height)]
    offset_x = max(0, (width - int(local_width)) // 2)
    offset_y = max(0, (height - int(local_height)) // 2)
    for y, row in enumerate(local[:height]):
        for x, glyph in enumerate(row[:width]):
            grid[offset_y + y][offset_x + x] = glyph
    return grid


def _place_authored_fixture(
    grid: List[List[str]],
    room_plan: Dict[str, object],
    glyph: str,
    variant: int,
    reserved: Set[Tuple[int, int]],
    catalog_walkable: Set[Tuple[int, int]],
) -> bool:
    rooms = [room for room in room_plan.get("rooms", ()) if isinstance(room, dict)]
    if not rooms:
        return False
    # Service/private rooms receive specialized displays first; public rooms
    # remain visually clean around the entrance and counter.
    rooms.sort(key=lambda room: (
        0 if str(room.get("privacy", "")) in {"service", "restricted", "private"} else 1,
        str(room.get("id", "")),
    ))
    baseline_reached = _authored_reachable_floor(grid, catalog_walkable)
    for room_index, room in enumerate(rooms):
        x1, y1, x2, y2 = (int(value) for value in room.get("rect", (0, 0, 0, 0)))
        candidates = [
            (x, y)
            for y in range(y1 + 1, y2)
            for x in range(x1 + 1, x2)
            if grid[y][x] == "."
            and (x, y) not in reserved
            and (x, y) != ((x1 + x2) // 2, (y1 + y2) // 2)
            and any(
                0 <= y + dy < len(grid)
                and 0 <= x + dx < len(grid[y + dy])
                and grid[y + dy][x + dx] in {".", ","}
                and (x + dx, y + dy) not in reserved
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
        ]
        candidates.sort(key=lambda cell: (
            min(cell[0] - x1, x2 - cell[0], cell[1] - y1, y2 - cell[1]),
            cell[1],
            cell[0],
        ))
        if (variant + room_index) % 2:
            candidates.reverse()
        for x, y in candidates:
            grid[y][x] = str(glyph)[:1]
            reached = _authored_reachable_floor(grid, catalog_walkable)
            interaction = next(
                (
                    (x + dx, y + dy)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if 0 <= y + dy < len(grid)
                    and 0 <= x + dx < len(grid[y + dy])
                    and grid[y + dy][x + dx] in {".", ","}
                    and (x + dx, y + dy) not in reserved
                    and (x + dx, y + dy) in reached
                ),
                None,
            )
            if interaction is not None and (baseline_reached - {(x, y)}) <= reached:
                reserved.add((x, y))
                reserved.add(interaction)
                return True
            grid[y][x] = "."
    return False


def build_authored_interior(
    layout_id: str,
    width: int,
    height: int,
    furniture_placements: Optional[List[FurniturePlacement]] = None,
) -> List[List[str]]:
    """Build a modular public interior while preserving authored mechanics."""
    layout_id = str(layout_id)
    modular = AUTHORED_MODULAR_LAYOUTS.get(layout_id)
    if modular is None:
        return _build_blueprint(AUTHORED_INTERIOR_BLUEPRINTS[layout_id], width, height)
    cached = _AUTHORED_MODULAR_CACHE.get(layout_id)
    if cached is not None:
        cached_rows, cached_placements = cached
        if furniture_placements is not None:
            # Runtime flattens these records into its own per-cell dictionaries
            # and never mutates the cached placement plans.
            furniture_placements.extend(cached_placements)
        return [list(row) for row in cached_rows]
    type_id, layout_variant, program_variant = modular
    floor_count = 1
    placements = furniture_placements if furniture_placements is not None else []
    grid = build_procedural_ground_floor(
        type_id,
        layout_variant,
        layout_variant,
        floor_count,
        game_table_glyphs=("1", "3", "5") if layout_id == "inn" else (),
        program_variant=program_variant,
        furniture_placements=placements,
    )
    room_plan = procedural_interior_room_plan(
        type_id,
        layout_variant,
        floor_count,
        0,
        None,
        program_variant,
    )
    if layout_id in {"inn", "mayor_house"}:
        # Authored NPC routines use B as the sleeping-room anchor. Preserve one
        # distinct anchor per physical bedroom while the catalog layer renders
        # the actual bed artwork.
        for room in room_plan.get("rooms", ()):
            if not isinstance(room, dict) or str(room.get("occupancy_kind", "")) not in {"resident", "guest"}:
                continue
            x1, y1, x2, y2 = (int(value) for value in room.get("rect", (0, 0, 0, 0)))
            bed = next(
                (
                    (x, y)
                    for y in range(y1 + 1, y2)
                    for x in range(x1 + 1, x2)
                    if grid[y][x] == "b"
                ),
                None,
            )
            if bed is not None:
                grid[bed[1]][bed[0]] = "B"
    reserved = {
        (int(cell.get("x", 0)), int(cell.get("y", 0)))
        for placement in placements
        for cell in placement.get("cells", ()) or ()
        if isinstance(cell, dict)
    }
    reserved.update(
        (int(placement["interaction_x"]), int(placement["interaction_y"]))
        for placement in placements
        if placement.get("interaction_x") is not None
        and placement.get("interaction_y") is not None
    )
    catalog_walkable = {
        (int(cell.get("x", 0)), int(cell.get("y", 0)))
        for placement in placements
        for cell in placement.get("cells", ()) or ()
        if isinstance(cell, dict) and str(cell.get("walkable_kind", ""))
    }
    symbols = set("".join("".join(row) for row in grid))
    for fixture_index, glyph in enumerate(AUTHORED_REQUIRED_FIXTURES.get(layout_id, ())):
        if glyph in symbols:
            continue
        if _place_authored_fixture(
            grid,
            room_plan,
            glyph,
            layout_variant + fixture_index,
            reserved,
            catalog_walkable,
        ):
            symbols.add(glyph)
    _AUTHORED_MODULAR_CACHE[layout_id] = (
        tuple("".join(row) for row in grid),
        tuple(copy.deepcopy(placements)),
    )
    return grid


def build_authored_residence(residence_id: str, width: int, height: int) -> List[List[str]]:
    spec = AUTHORED_RESIDENCE_BLUEPRINTS.get(str(residence_id), AUTHORED_RESIDENCE_BLUEPRINTS["meadow_cottage"])
    return _build_blueprint(spec, width, height)
