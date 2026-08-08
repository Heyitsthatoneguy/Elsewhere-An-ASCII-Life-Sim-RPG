from __future__ import annotations

"""Catalog-backed furnishing kits for generated settlement rooms.

The generated map keeps semantic fixture glyphs for legacy interaction and
pathfinding.  This module adds a deterministic visual/object layer made from
the same multi-cell furniture catalog used by player homes.
"""

from typing import Dict, List, MutableSequence, Optional, Sequence, Set, Tuple

from ascii_farmstead_furniture import (
    furniture_art_cell,
    furniture_art_rows,
    furniture_component_at,
    furniture_walkable_kind,
)


Position = Tuple[int, int]
Room = Dict[str, object]
FurniturePlacement = Dict[str, object]


BUILDING_COLLECTION = {
    "home": 0,
    "inn": 0,
    "carpenter": 0,
    "workshop": 0,
    "market_stall": 1,
    "clinic": 1,
    "library": 1,
    "general_store": 2,
    "sheriff_office": 2,
    "town_hall": 2,
}
COLLECTIONS = ("Hearthwood", "Coastal", "Manor")


# Entries are (catalog form, semantic fixture glyph).  Semantic glyphs retain
# the established service/container meaning beneath the richer artwork.
ROLE_KITS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "common": (("Breakfast Table", "t"), ("Reading Chair", "c"), ("Indoor Planter", "P")),
    "common_room": (("Dining Table", "t"), ("Dining Chair", "c"), ("Entry Bench", "c"), ("Indoor Planter", "P")),
    "kitchen": (("Stove Range", "f"), ("Kitchen Cupboard", "P"), ("Breakfast Table", "t")),
    "primary_bedroom": (("Double Bed", "b"), ("Bedside Cabinet", "d"), ("Table Lamp", "l")),
    "bedroom": (("Single Bed", "b"), ("Bedside Cabinet", "d"), ("Table Lamp", "l")),
    "nursery": (("Cradle", "b"), ("Changing Table", "P"), ("Table Lamp", "l")),
    "guest_room": (("Single Bed", "b"), ("Bedside Cabinet", "d"), ("Table Lamp", "l")),
    "en_suite": (("Washstand", "u"), ("Towel Rack", "P")),
    "pantry": (("Kitchen Cupboard", "s"), ("Baker Rack", "P")),
    "study": (("Writing Desk", "d"), ("Dining Chair", "c"), ("Bookcase", "P")),
    "storage": (("Tall Cabinet", "s"), ("Storage Trunk", "P")),
    "sales": (("Display Shelf", "s"), ("Curio Case", "$")),
    "stockroom": (("Tall Cabinet", "s"), ("Storage Trunk", "$"), ("Filing Cabinet", "P")),
    "office": (("Writing Desk", "d"), ("Dining Chair", "c"), ("Filing Cabinet", "P")),
    "delivery": (("Storage Trunk", "s"), ("Tool Cart", "x")),
    "display": (("Display Shelf", "$"), ("Curio Case", "s")),
    "produce": (("Display Shelf", "$"), ("Storage Trunk", "s")),
    "waiting": (("Entry Bench", "c"), ("Side Table", "t"), ("Indoor Planter", "P")),
    "examination": (("Daybed", "b"), ("Medicine Cabinet", "+"), ("Writing Desk", "d")),
    "clinic_ward": (("Single Bed", "b"), ("Medicine Cabinet", "+"), ("Bedside Cabinet", "d")),
    "pharmacy": (("Apothecary Cabinet", "+"), ("Tall Cabinet", "s")),
    "reception": (("Writing Desk", "P"), ("Dining Chair", "c")),
    "records": (("Filing Cabinet", "P"), ("Writing Desk", "d"), ("Record Cabinet", "s")),
    "cell": (("Single Bed", "b"), ("Storage Trunk", "P")),
    "armory": (("Tall Cabinet", "x"), ("Storage Trunk", "s")),
    "circulation": (("Entry Bench", "c"), ("Indoor Planter", "P")),
    "stacks": (("Bookcase", "l"), ("Wall Shelf", "l")),
    "reading": (("Study Table", "t"), ("Reading Chair", "c"), ("Bookcase", "l")),
    "archive": (("Record Cabinet", "P"), ("Filing Cabinet", "l"), ("Writing Desk", "d")),
    "showroom": (("Worktable", "w"), ("Display Shelf", "a"), ("Tool Cart", "x")),
    "woodshop": (("Worktable", "w"), ("Tool Cart", "a"), ("Storage Trunk", "x")),
    "lumber": (("Storage Trunk", "w"), ("Tall Cabinet", "s")),
    "service": (("Worktable", "w"), ("Tool Cart", "a")),
    "forge": (("Worktable", "a"), ("Tool Cart", "x"), ("Tall Cabinet", "w")),
    "workshop": (("Worktable", "w"), ("Tool Cart", "a"), ("Tall Cabinet", "s")),
    "materials": (("Tall Cabinet", "s"), ("Storage Trunk", "x")),
    "finishing": (("Worktable", "w"), ("Display Shelf", "P"), ("Tool Cart", "a")),
    "lobby": (("Entry Bench", "c"), ("Side Table", "t"), ("Indoor Planter", "P")),
    "council": (("Banquet Table", "t"), ("Captain Chair", "c"), ("Filing Cabinet", "P")),
    "meeting": (("Dining Table", "t"), ("Dining Chair", "c"), ("Record Cabinet", "P")),
    "landing": (("Entry Bench", "c"), ("Long Hall Carpet", ",")),
    "upper_lounge": (("Coffee Table", "t"), ("Loveseat", "c"), ("Floor Lamp", "l")),
}


def furnishing_collection(type_id: str, variant: int, fixture_variant: int) -> str:
    base = BUILDING_COLLECTION.get(str(type_id), 0)
    # Layout families influence local taste while every floor of one building
    # remains coherent. fixture_variant is accepted for API stability only.
    _ = fixture_variant
    return COLLECTIONS[(base + int(variant)) % len(COLLECTIONS)]


class ProceduralFurniturePlacer:
    def __init__(
        self,
        grid: MutableSequence[MutableSequence[str]],
        protected: Set[Position],
        type_id: str,
        variant: int,
        fixture_variant: int,
        placements: List[FurniturePlacement],
    ) -> None:
        self.grid = grid
        self.protected = protected
        self.type_id = str(type_id)
        self.variant = int(variant)
        self.fixture_variant = int(fixture_variant)
        self.collection = furnishing_collection(type_id, variant, fixture_variant)
        self.placements = placements
        self.occupied: Set[Position] = set()

    def _room_floor_connected(self, room: Room) -> bool:
        x1, y1, x2, y2 = (int(value) for value in room["rect"])
        walkable_furniture = {
            (int(cell.get("x", 0)), int(cell.get("y", 0)))
            for placement in self.placements
            if str(placement.get("room_id", "")) == str(room.get("id", "room"))
            for cell in placement.get("cells", ()) or ()
            if isinstance(cell, dict) and str(cell.get("walkable_kind", ""))
        }
        passable = {
            (x, y)
            for y in range(y1 + 1, y2)
            for x in range(x1 + 1, x2)
            if self.grid[y][x] in {".", ","} or (x, y) in walkable_furniture
        }
        if not passable:
            return False
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        start = center if center in passable else min(
            passable,
            key=lambda cell: abs(cell[0] - center[0]) + abs(cell[1] - center[1]),
        )
        reached = {start}
        frontier = [start]
        while frontier:
            x, y = frontier.pop()
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor in passable and neighbor not in reached:
                    reached.add(neighbor)
                    frontier.append(neighbor)
        return reached == passable

    def _candidate_anchors(self, room: Room, width: int, height: int) -> List[Position]:
        x1, y1, x2, y2 = (int(value) for value in room["rect"])
        candidates: List[Position] = []
        # Edge-first placement leaves the room center and its circulation spine
        # visually open, even for large multi-cell furniture.
        for y in range(y1 + 1, y2):
            for x in range(x1 + 1, x2):
                edge_distance = min(x - x1, x2 - x, y - y1, y2 - y)
                candidates.append((x, y))
        room_id = str(room.get("id", "room"))
        existing = {
            (int(cell.get("x", 0)), int(cell.get("y", 0)))
            for placement in self.placements
            if str(placement.get("room_id", "")) == room_id
            for cell in placement.get("cells", ()) or ()
            if isinstance(cell, dict)
        }

        def candidate_key(cell: Position) -> Tuple[int, int, int, int]:
            x, y = cell
            footprint = (
                (x + offset_x, y + offset_y)
                for offset_y in range(height)
                for offset_x in range(width)
            )
            adjacency_distance = (
                min(
                    abs(candidate_x - existing_x) + abs(candidate_y - existing_y)
                    for candidate_x, candidate_y in footprint
                    for existing_x, existing_y in existing
                )
                if existing
                else 1
            )
            return (
                abs(adjacency_distance - 1),
                min(x - x1, x2 - x, y - y1, y2 - y),
                y,
                x,
            )

        candidates.sort(key=candidate_key)
        if not existing and (self.variant + self.fixture_variant) % 2:
            candidates.reverse()
        return candidates

    def place(self, room: Room, form: str, semantic: str) -> bool:
        name = f"{self.collection} {form}"
        x1, y1, x2, y2 = (int(value) for value in room["rect"])
        rotation_order = [0, 2, 1, 3]
        shift = (self.variant + self.fixture_variant + len(self.placements)) % 4
        rotation_order = rotation_order[shift:] + rotation_order[:shift]
        for rotation in rotation_order:
            rows = furniture_art_rows(name, True, rotation)
            if not rows:
                continue
            width, height = len(rows[0]), len(rows)
            for anchor_x, anchor_y in self._candidate_anchors(room, width, height):
                cells = [
                    (anchor_x + offset_x, anchor_y + offset_y, offset_x, offset_y)
                    for offset_y in range(height)
                    for offset_x in range(width)
                ]
                if not all(
                    x1 < x < x2
                    and y1 < y < y2
                    and self.grid[y][x] in {".", ","}
                    and (x, y) not in self.protected
                    and (x, y) not in self.occupied
                    for x, y, _offset_x, _offset_y in cells
                ):
                    continue
                footprint_positions = {(x, y) for x, y, _offset_x, _offset_y in cells}
                solid_positions: List[Position] = []
                for x, y, offset_x, offset_y in cells:
                    walkable_kind = furniture_walkable_kind(name, offset_x, offset_y, rotation)
                    if not walkable_kind and not (form.endswith("Rug") or form.endswith("Carpet")):
                        solid_positions.append((x, y))
                semantic_position: Optional[Position] = None
                interaction_position: Optional[Position] = None
                for solid_x, solid_y in solid_positions:
                    exposed = [
                        (solid_x + dx, solid_y + dy)
                        for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1))
                        if (solid_x + dx, solid_y + dy) not in footprint_positions
                        and x1 < solid_x + dx < x2
                        and y1 < solid_y + dy < y2
                        and self.grid[solid_y + dy][solid_x + dx] in {".", ","}
                        and (solid_x + dx, solid_y + dy) not in self.protected
                        and (solid_x + dx, solid_y + dy) not in self.occupied
                    ]
                    if exposed:
                        semantic_position = (solid_x, solid_y)
                        interaction_position = exposed[0]
                        break
                if semantic_position is None and solid_positions:
                    semantic_position = solid_positions[0]
                placement_cells: List[Dict[str, object]] = []
                old_glyphs = {(x, y): self.grid[y][x] for x, y, _ox, _oy in cells}
                for x, y, offset_x, offset_y in cells:
                    art_cell = furniture_art_cell(name, offset_x, offset_y, True, rotation)
                    if not art_cell:
                        continue
                    glyph, material_role = art_cell
                    walkable_kind = furniture_walkable_kind(name, offset_x, offset_y, rotation)
                    component = furniture_component_at(name, offset_x, offset_y, rotation)
                    if form.endswith("Rug") or form.endswith("Carpet"):
                        map_glyph = ","
                        walkable_kind = walkable_kind or "open"
                    elif walkable_kind == "seat":
                        map_glyph = "c"
                    elif walkable_kind == "open":
                        map_glyph = "."
                    else:
                        map_glyph = (
                            str(semantic)[:1] or "P"
                            if (x, y) == semantic_position
                            else "P"
                        )
                    self.grid[y][x] = map_glyph
                    self.protected.add((x, y))
                    self.occupied.add((x, y))
                    placement_cells.append({
                        "x": x,
                        "y": y,
                        "offset_x": offset_x,
                        "offset_y": offset_y,
                        "glyph": glyph,
                        "material_role": material_role,
                        "walkable_kind": walkable_kind,
                        "component": component,
                        "semantic": map_glyph,
                    })
                placement = {
                    "name": name,
                    "collection": self.collection,
                    "form": form,
                    "room_id": str(room.get("id", "room")),
                    "room_role": str(room.get("role", "room")),
                    "anchor_x": anchor_x,
                    "anchor_y": anchor_y,
                    "rotation": rotation,
                    "width": width,
                    "height": height,
                    "interaction_x": interaction_position[0] if interaction_position else None,
                    "interaction_y": interaction_position[1] if interaction_position else None,
                    "cells": tuple(placement_cells),
                }
                self.placements.append(placement)
                if interaction_position is not None:
                    self.protected.add(interaction_position)
                if not self._room_floor_connected(room):
                    self.placements.pop()
                    if interaction_position is not None:
                        self.protected.discard(interaction_position)
                    for (x, y), old_glyph in old_glyphs.items():
                        self.grid[y][x] = old_glyph
                        self.protected.discard((x, y))
                        self.occupied.discard((x, y))
                    continue
                return True
        return False

    def furnish_room(self, room: Room) -> int:
        kit = ROLE_KITS.get(str(room.get("role", "")), ())
        if not kit:
            return 0
        x1, y1, x2, y2 = (int(value) for value in room["rect"])
        grid_snapshot = {
            (x, y): self.grid[y][x]
            for y in range(y1 + 1, y2)
            for x in range(x1 + 1, x2)
        }
        protected_snapshot = set(self.protected)
        occupied_snapshot = set(self.occupied)
        placement_count = len(self.placements)

        def rollback() -> int:
            for (x, y), glyph in grid_snapshot.items():
                self.grid[y][x] = glyph
            self.protected.clear()
            self.protected.update(protected_snapshot)
            self.occupied.clear()
            self.occupied.update(occupied_snapshot)
            del self.placements[placement_count:]
            return 0

        placed = 0
        for index, (form, semantic) in enumerate(kit):
            if self.place(room, form, semantic):
                placed += 1
            elif index == 0:
                # The first entry defines the room (bed, desk, table, work
                # surface).  If it cannot fit, leave the room to the proven
                # compact symbolic fallback instead of adding stray decor.
                return rollback()

        def semantic_cells(glyph: str) -> List[Position]:
            return [
                (x, y)
                for y in range(y1 + 1, y2)
                for x in range(x1 + 1, x2)
                if self.grid[y][x] == glyph
            ]

        def adjacent(first: Sequence[Position], second: Sequence[Position]) -> bool:
            return any(
                abs(first_x - second_x) + abs(first_y - second_y) == 1
                for first_x, first_y in first
                for second_x, second_y in second
            )

        role = str(room.get("role", ""))
        if str(room.get("occupancy_kind", "")) in {"resident", "guest"} and not semantic_cells("b"):
            return rollback()
        if role == "kitchen" and not semantic_cells("f"):
            return rollback()
        if role in {"common", "common_room", "reading", "council", "meeting"}:
            if not adjacent(semantic_cells("t"), semantic_cells("c")):
                return rollback()
        if role in {"study", "office"}:
            if not adjacent(semantic_cells("d"), semantic_cells("c")):
                return rollback()
        return placed


def validate_furnishing_kits() -> Tuple[str, ...]:
    problems: List[str] = []
    for role, entries in ROLE_KITS.items():
        if not entries:
            problems.append(f"{role}: empty furnishing kit")
            continue
        for form, _semantic in entries:
            for collection in COLLECTIONS:
                if not furniture_art_rows(f"{collection} {form}"):
                    problems.append(f"{role}: missing {collection} {form}")
    return tuple(problems)


__all__ = [
    "COLLECTIONS",
    "FurniturePlacement",
    "ProceduralFurniturePlacer",
    "ROLE_KITS",
    "furnishing_collection",
    "validate_furnishing_kits",
]
