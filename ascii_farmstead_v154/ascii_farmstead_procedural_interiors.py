from __future__ import annotations

"""Purpose-built architectural plans for generated settlement interiors.

The town runtime keeps a fixed 64x28 canvas because entrances can face any
cardinal direction.  The occupied footprint is intentionally much smaller:
rooms are arranged by one of four real circulation graphs and the surrounding
canvas remains empty.
"""

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ascii_farmstead_procedural_furnishing import (
    FurniturePlacement,
    ProceduralFurniturePlacer,
)


Position = Tuple[int, int]
Room = Dict[str, object]
RoomRequest = Dict[str, object]

TYPE_ORDER = (
    "home",
    "general_store",
    "market_stall",
    "inn",
    "clinic",
    "sheriff_office",
    "library",
    "carpenter",
    "workshop",
    "town_hall",
)


# Each topology has a different room graph, not merely a reflected footprint.
# The first slot is always the public entrance room.  Parent indices describe
# how later rooms connect to the plan.
TOPOLOGIES: Tuple[Tuple[Tuple[int, int, int, int], ...], ...] = (
    (
        (24, 19, 40, 26), (24, 11, 40, 17), (7, 16, 20, 24),
        (7, 7, 20, 13), (24, 3, 40, 9), (44, 7, 57, 14),
        (44, 17, 57, 24), (3, 2, 15, 5), (49, 2, 61, 5),
    ),
    (
        (25, 20, 39, 26), (8, 18, 22, 25), (6, 8, 20, 15),
        (23, 7, 38, 14), (42, 13, 58, 20), (43, 4, 57, 10),
        (23, 2, 37, 5), (3, 2, 17, 5), (48, 22, 60, 26),
    ),
    (
        (23, 19, 41, 26), (7, 14, 20, 23), (8, 4, 22, 11),
        (25, 10, 39, 17), (43, 4, 56, 11), (44, 14, 58, 23),
        (26, 3, 38, 7), (3, 24, 17, 26), (48, 24, 61, 26),
    ),
    (
        (19, 19, 45, 26), (5, 14, 16, 23), (8, 4, 25, 11),
        (27, 10, 37, 17), (39, 4, 56, 11), (48, 14, 59, 23),
        (27, 2, 37, 7), (2, 5, 6, 11), (58, 4, 62, 11),
    ),
)

TOPOLOGY_PARENTS: Tuple[Tuple[Optional[int], ...], ...] = (
    (None, 0, 0, 2, 1, 1, 0, 3, 5),
    (None, 0, 1, 1, 0, 4, 3, 2, 4),
    (None, 0, 1, 0, 3, 0, 3, 1, 5),
    (None, 0, 1, 0, 3, 0, 3, 2, 4),
)


ROOM_SIZE_LIMITS: Dict[str, Tuple[int, int]] = {
    "tiny": (7, 5),
    "small": (10, 7),
    "standard": (15, 9),
    "large": (20, 11),
    "grand": (30, 15),
}

ROOM_PRIVACY_LEVELS = {
    "public": 0,
    "semi_public": 1,
    "private": 2,
    "service": 2,
    "restricted": 3,
}

DIRECT_DEPENDENT_ROLES = {
    "en_suite": {"primary_bedroom", "bedroom"},
    "pantry": {"kitchen"},
    "stockroom": {"sales", "showroom", "service"},
    "archive": {"records", "stacks", "office"},
    "armory": {"office", "reception"},
    "storage": {
        "kitchen", "stockroom", "workshop", "woodshop", "materials", "pharmacy",
        "delivery", "records", "lumber",
    },
}

ADAPTIVE_ROOM_ROLES = {"bedroom", "nursery"}


def sanitize_procedural_room_overrides(value: object) -> Dict[str, str]:
    """Keep only safe, stable role changes for generated household rooms."""
    if not isinstance(value, dict):
        return {}
    clean: Dict[str, str] = {}
    for raw_key, raw_role in value.items():
        key = str(raw_key or "").strip()
        role = str(raw_role or "").strip().lower()
        parts = key.split(":", 2)
        if (
            len(parts) != 3
            or parts[0] != "floor"
            or not parts[1].isdigit()
            or not parts[2]
            or int(parts[1]) > 3
            or role not in ADAPTIVE_ROOM_ROLES
        ):
            continue
        clean[f"floor:{int(parts[1])}:{parts[2]}"] = role
    return clean


def _room(
    room_id: str,
    role: str,
    privacy: str,
    size: str,
    *,
    parent: str = "",
    connection: str = "hall",
    capacity: int = 0,
    occupancy_kind: str = "",
) -> RoomRequest:
    return {
        "id": room_id,
        "role": role,
        "privacy": privacy,
        "private": privacy in {"private", "restricted"},
        "size": size,
        "parent": parent,
        "connection": connection,
        "capacity": max(0, int(capacity)),
        "occupancy_kind": occupancy_kind,
    }


ROOM_PROGRAMS: Dict[str, Tuple[RoomRequest, ...]] = {
    "home": (
        _room("living", "common", "semi_public", "large", connection="entrance"),
        _room("kitchen", "kitchen", "private", "standard", parent="living", connection="archway"),
        _room("primary", "primary_bedroom", "private", "standard", parent="living", capacity=2, occupancy_kind="resident"),
        _room("primary_bath", "en_suite", "private", "tiny", parent="primary", connection="direct"),
        _room("bedroom_2", "bedroom", "private", "small", parent="living", capacity=1, occupancy_kind="resident"),
        _room("study", "study", "private", "small", parent="bedroom_2", connection="direct"),
        _room("pantry", "pantry", "service", "tiny", parent="kitchen", connection="direct"),
    ),
    "general_store": (
        _room("sales", "sales", "public", "grand", connection="entrance"),
        _room("stock", "stockroom", "service", "standard", parent="sales", connection="archway"),
        _room("office", "office", "private", "small", parent="stock", connection="direct"),
        _room("delivery", "delivery", "service", "standard", parent="stock", connection="direct"),
        _room("display", "display", "public", "standard", parent="sales", connection="archway"),
    ),
    "market_stall": (
        _room("sales", "sales", "public", "large", connection="entrance"),
        _room("stock", "stockroom", "service", "small", parent="sales", connection="archway"),
        _room("produce", "produce", "public", "standard", parent="sales", connection="archway"),
        _room("office", "office", "private", "tiny", parent="stock", connection="direct"),
    ),
    "clinic": (
        _room("waiting", "waiting", "public", "large", connection="entrance"),
        _room("exam", "examination", "semi_public", "standard", parent="waiting"),
        _room("recovery_1", "clinic_ward", "private", "small", parent="exam"),
        _room("pharmacy", "pharmacy", "restricted", "small", parent="exam", connection="direct"),
        _room("office", "office", "private", "small", parent="waiting"),
        _room("medical_store", "storage", "restricted", "tiny", parent="pharmacy", connection="direct"),
    ),
    "sheriff_office": (
        _room("reception", "reception", "public", "large", connection="entrance"),
        _room("office", "office", "private", "standard", parent="reception"),
        _room("records", "records", "restricted", "small", parent="office", connection="direct"),
        _room("cell_1", "cell", "restricted", "small", parent="reception"),
        _room("cell_2", "cell", "restricted", "small", parent="reception"),
        _room("armory", "armory", "restricted", "tiny", parent="office", connection="direct"),
    ),
    "library": (
        _room("circulation", "circulation", "public", "large", connection="entrance"),
        _room("stacks", "stacks", "public", "grand", parent="circulation", connection="archway"),
        _room("reading", "reading", "public", "large", parent="stacks", connection="archway"),
        _room("archive", "archive", "restricted", "small", parent="stacks", connection="direct"),
        _room("study", "study", "semi_public", "small", parent="reading"),
        _room("records", "records", "restricted", "small", parent="archive", connection="direct"),
    ),
    "carpenter": (
        _room("showroom", "showroom", "public", "large", connection="entrance"),
        _room("woodshop", "woodshop", "service", "grand", parent="showroom"),
        _room("lumber", "lumber", "service", "standard", parent="woodshop", connection="direct"),
        _room("office", "office", "private", "small", parent="showroom"),
        _room("storage", "storage", "service", "small", parent="woodshop", connection="direct"),
    ),
    "workshop": (
        _room("service", "service", "public", "large", connection="entrance"),
        _room("forge", "forge", "service", "standard", parent="service"),
        _room("workshop", "workshop", "service", "grand", parent="service"),
        _room("materials", "materials", "service", "standard", parent="workshop", connection="direct"),
        _room("finishing", "finishing", "service", "standard", parent="workshop", connection="direct"),
    ),
    "town_hall": (
        _room("lobby", "lobby", "public", "grand", connection="entrance"),
        _room("council", "council", "public", "grand", parent="lobby", connection="archway"),
        _room("records", "records", "restricted", "small", parent="lobby"),
        _room("office", "office", "private", "standard", parent="lobby"),
        _room("meeting", "meeting", "semi_public", "large", parent="council"),
        _room("archive", "archive", "restricted", "tiny", parent="records", connection="direct"),
    ),
}

ROOM_PROGRAM_VARIANT_NAMES = ("Compact", "Standard", "Expanded")

# These are different architectural programs, not reordered copies. Compact
# buildings keep only their essential service chain; expanded buildings add
# purpose-specific rooms and secondary branches while remaining below the
# nine-room topology limit.
COMPACT_ROOM_PROGRAMS: Dict[str, Tuple[RoomRequest, ...]] = {
    "home": (
        _room("living", "common", "semi_public", "large", connection="entrance"),
        _room("kitchen", "kitchen", "private", "standard", parent="living", connection="archway"),
        _room("primary", "primary_bedroom", "private", "standard", parent="living", capacity=2, occupancy_kind="resident"),
        _room("bedroom_2", "bedroom", "private", "small", parent="living", capacity=1, occupancy_kind="resident"),
        _room("study", "study", "private", "small", parent="bedroom_2", connection="direct"),
        _room("pantry", "pantry", "service", "tiny", parent="kitchen", connection="direct"),
    ),
    "general_store": (
        _room("sales", "sales", "public", "grand", connection="entrance"),
        _room("stock", "stockroom", "service", "standard", parent="sales", connection="archway"),
        _room("office", "office", "private", "small", parent="stock", connection="direct"),
        _room("delivery", "delivery", "service", "small", parent="stock", connection="direct"),
    ),
    "market_stall": (
        _room("sales", "sales", "public", "large", connection="entrance"),
        _room("produce", "produce", "public", "standard", parent="sales", connection="archway"),
        _room("stock", "stockroom", "service", "small", parent="sales"),
    ),
    "clinic": (
        _room("waiting", "waiting", "public", "large", connection="entrance"),
        _room("exam", "examination", "semi_public", "standard", parent="waiting"),
        _room("pharmacy", "pharmacy", "restricted", "small", parent="exam", connection="direct"),
        _room("office", "office", "private", "small", parent="waiting"),
    ),
    "sheriff_office": (
        _room("reception", "reception", "public", "large", connection="entrance"),
        _room("office", "office", "private", "standard", parent="reception"),
        _room("records", "records", "restricted", "small", parent="office", connection="direct"),
        _room("cell_1", "cell", "restricted", "small", parent="reception"),
        _room("armory", "armory", "restricted", "tiny", parent="office", connection="direct"),
    ),
    "library": (
        _room("circulation", "circulation", "public", "large", connection="entrance"),
        _room("stacks", "stacks", "public", "grand", parent="circulation", connection="archway"),
        _room("reading", "reading", "public", "large", parent="stacks", connection="archway"),
        _room("archive", "archive", "restricted", "small", parent="stacks", connection="direct"),
    ),
    "carpenter": (
        _room("showroom", "showroom", "public", "large", connection="entrance"),
        _room("woodshop", "woodshop", "service", "grand", parent="showroom"),
        _room("lumber", "lumber", "service", "standard", parent="woodshop", connection="direct"),
        _room("storage", "storage", "service", "small", parent="woodshop", connection="direct"),
    ),
    "workshop": (
        _room("service", "service", "public", "large", connection="entrance"),
        _room("forge", "forge", "service", "standard", parent="service"),
        _room("workshop", "workshop", "service", "grand", parent="service"),
        _room("materials", "materials", "service", "standard", parent="workshop", connection="direct"),
    ),
    "town_hall": (
        _room("lobby", "lobby", "public", "grand", connection="entrance"),
        _room("council", "council", "public", "grand", parent="lobby", connection="archway"),
        _room("office", "office", "private", "standard", parent="lobby"),
        _room("records", "records", "restricted", "small", parent="office", connection="direct"),
    ),
}

EXPANDED_ROOM_PROGRAMS: Dict[str, Tuple[RoomRequest, ...]] = {
    "home": (
        _room("living", "common", "semi_public", "grand", connection="entrance"),
        _room("kitchen", "kitchen", "private", "standard", parent="living", connection="archway"),
        _room("dining", "common", "semi_public", "large", parent="kitchen", connection="archway"),
        _room("primary", "primary_bedroom", "private", "standard", parent="living", capacity=2, occupancy_kind="resident"),
        _room("primary_bath", "en_suite", "private", "tiny", parent="primary", connection="direct"),
        _room("bedroom_2", "bedroom", "private", "standard", parent="living", capacity=1, occupancy_kind="resident"),
        _room("study", "study", "private", "small", parent="bedroom_2", connection="direct"),
        _room("pantry", "pantry", "service", "tiny", parent="kitchen", connection="direct"),
        _room("mudroom", "storage", "service", "tiny", parent="kitchen"),
    ),
    "general_store": (
        _room("sales", "sales", "public", "grand", connection="entrance"),
        _room("display", "display", "public", "large", parent="sales", connection="archway"),
        _room("stock", "stockroom", "service", "grand", parent="sales", connection="archway"),
        _room("delivery", "delivery", "service", "standard", parent="stock", connection="direct"),
        _room("office", "office", "private", "standard", parent="stock", connection="direct"),
        _room("records", "records", "restricted", "small", parent="office", connection="direct"),
        _room("overflow", "storage", "service", "small", parent="delivery", connection="direct"),
    ),
    "market_stall": (
        _room("sales", "sales", "public", "large", connection="entrance"),
        _room("produce", "produce", "public", "large", parent="sales", connection="archway"),
        _room("display", "display", "public", "standard", parent="sales", connection="archway"),
        _room("stock", "stockroom", "service", "standard", parent="produce"),
        _room("delivery", "delivery", "service", "small", parent="stock", connection="direct"),
        _room("office", "office", "private", "small", parent="sales"),
    ),
    "clinic": (
        _room("waiting", "waiting", "public", "large", connection="entrance"),
        _room("reception", "reception", "public", "standard", parent="waiting", connection="archway"),
        _room("exam_1", "examination", "semi_public", "standard", parent="reception"),
        _room("exam_2", "examination", "semi_public", "standard", parent="reception"),
        _room("recovery", "clinic_ward", "private", "large", parent="exam_1"),
        _room("pharmacy", "pharmacy", "restricted", "standard", parent="reception"),
        _room("office", "office", "private", "small", parent="waiting"),
        _room("medical_store", "storage", "restricted", "tiny", parent="pharmacy", connection="direct"),
    ),
    "sheriff_office": (
        _room("reception", "reception", "public", "large", connection="entrance"),
        _room("office", "office", "private", "standard", parent="reception"),
        _room("interview", "meeting", "semi_public", "standard", parent="reception"),
        _room("records", "records", "restricted", "small", parent="office", connection="direct"),
        _room("evidence", "storage", "restricted", "small", parent="records", connection="direct"),
        _room("cell_1", "cell", "restricted", "small", parent="reception"),
        _room("cell_2", "cell", "restricted", "small", parent="cell_1"),
        _room("armory", "armory", "restricted", "tiny", parent="office", connection="direct"),
    ),
    "library": (
        _room("circulation", "circulation", "public", "large", connection="entrance"),
        _room("stacks", "stacks", "public", "grand", parent="circulation", connection="archway"),
        _room("reading", "reading", "public", "grand", parent="stacks", connection="archway"),
        _room("study_1", "study", "semi_public", "small", parent="reading"),
        _room("study_2", "study", "semi_public", "small", parent="reading"),
        _room("meeting", "meeting", "semi_public", "standard", parent="circulation"),
        _room("archive", "archive", "restricted", "standard", parent="stacks", connection="direct"),
        _room("records", "records", "restricted", "tiny", parent="archive", connection="direct"),
    ),
    "carpenter": (
        _room("showroom", "showroom", "public", "large", connection="entrance"),
        _room("woodshop", "woodshop", "service", "grand", parent="showroom"),
        _room("assembly", "workshop", "service", "large", parent="woodshop", connection="archway"),
        _room("finishing", "finishing", "service", "standard", parent="assembly", connection="direct"),
        _room("lumber", "lumber", "service", "standard", parent="woodshop", connection="direct"),
        _room("storage", "storage", "service", "small", parent="lumber", connection="direct"),
        _room("office", "office", "private", "small", parent="showroom"),
        _room("delivery", "delivery", "service", "tiny", parent="assembly"),
    ),
    "workshop": (
        _room("service", "service", "public", "large", connection="entrance"),
        _room("forge", "forge", "service", "large", parent="service"),
        _room("workshop", "workshop", "service", "grand", parent="service", connection="archway"),
        _room("assembly", "workshop", "service", "large", parent="workshop", connection="archway"),
        _room("materials", "materials", "service", "standard", parent="workshop", connection="direct"),
        _room("finishing", "finishing", "service", "standard", parent="assembly", connection="direct"),
        _room("storage", "storage", "service", "small", parent="materials", connection="direct"),
        _room("office", "office", "private", "tiny", parent="service"),
    ),
    "town_hall": (
        _room("lobby", "lobby", "public", "grand", connection="entrance"),
        _room("council", "council", "public", "grand", parent="lobby", connection="archway"),
        _room("public_meeting", "meeting", "public", "large", parent="council", connection="archway"),
        _room("mayor_office", "office", "private", "standard", parent="lobby"),
        _room("clerk_office", "office", "private", "small", parent="lobby"),
        _room("records", "records", "restricted", "standard", parent="clerk_office", connection="direct"),
        _room("archive", "archive", "restricted", "small", parent="records", connection="direct"),
        _room("committee", "meeting", "semi_public", "tiny", parent="council"),
    ),
}

ROOM_PROGRAM_VARIANTS: Dict[str, Tuple[Tuple[RoomRequest, ...], ...]] = {
    type_id: (
        COMPACT_ROOM_PROGRAMS[type_id],
        ROOM_PROGRAMS[type_id],
        EXPANDED_ROOM_PROGRAMS[type_id],
    )
    for type_id in ROOM_PROGRAMS
}


def _inn_program(floor_count: int, program_variant: int = 1) -> Tuple[RoomRequest, ...]:
    variant = max(0, min(2, int(program_variant)))
    bedroom_count = (
        3 if floor_count > 1 else 5
    ) if variant == 0 else (
        4 if floor_count > 1 else 6
    ) if variant == 1 else (4 if floor_count > 1 else 5)
    rooms: List[RoomRequest] = [
        _room("lobby", "lobby", "public", "large", connection="entrance"),
        _room("common", "common_room", "public", "grand", parent="lobby", connection="archway"),
        _room("kitchen", "kitchen", "service", "standard", parent="common"),
    ]
    if variant == 2:
        rooms.append(_room("dining", "common_room", "public", "large", parent="common", connection="archway"))
    for index in range(bedroom_count):
        rooms.append(
            _room(
                f"guest_{index + 1}",
                "guest_room",
                "private",
                "tiny" if variant == 2 and index >= 3 else "small" if index % 2 else "standard",
                parent="common",
                capacity=1,
                occupancy_kind="guest",
            )
        )
    while len(rooms) < (7 if variant == 0 else 9):
        rooms.append(
            _room(
                f"storage_{len(rooms)}",
                "storage",
                "service",
                "tiny",
                parent="kitchen",
                connection="direct",
            )
        )
    return tuple(rooms)


def _center(rect: Tuple[int, int, int, int]) -> Position:
    x1, y1, x2, y2 = rect
    return (x1 + x2) // 2, (y1 + y2) // 2


def _orthogonal_path(start: Position, end: Position, horizontal_first: bool) -> List[Position]:
    x, y = start
    ex, ey = end
    result = [(x, y)]
    axes = ("x", "y") if horizontal_first else ("y", "x")
    for axis in axes:
        if axis == "x":
            while x != ex:
                x += 1 if ex > x else -1
                result.append((x, y))
        else:
            while y != ey:
                y += 1 if ey > y else -1
                result.append((x, y))
    return result


def _adjusted_rect(
    rect: Tuple[int, int, int, int],
    type_index: int,
    slot_index: int,
    variant: int,
    size: str = "standard",
) -> Tuple[int, int, int, int]:
    """Give every building role its own size and silhouette without overlap."""
    x1, y1, x2, y2 = rect
    if slot_index == 0:
        trim = type_index % 3
        x1 += int(trim == 2)
        x2 -= int(trim == 1)
    elif x2 - x1 >= 8 and (type_index + slot_index + variant) % 3 == 0:
        x2 -= 1
    if y2 - y1 >= 6 and (type_index * 2 + slot_index + variant) % 4 == 0:
        y1 += 1
    if x2 - x1 >= 10 and (type_index + slot_index * 2) % 5 == 0:
        x1 += 1
    limit_width, limit_height = ROOM_SIZE_LIMITS.get(size, ROOM_SIZE_LIMITS["standard"])
    current_width = x2 - x1 + 1
    current_height = y2 - y1 + 1
    if current_width > limit_width:
        trim = current_width - limit_width
        x1 += trim // 2
        x2 -= trim - trim // 2
    if current_height > limit_height:
        trim = current_height - limit_height
        y1 += trim // 2
        y2 -= trim - trim // 2
    return x1, y1, x2, y2


def _room_size_class(rect: Tuple[int, int, int, int]) -> str:
    x1, y1, x2, y2 = rect
    area = max(0, x2 - x1 - 1) * max(0, y2 - y1 - 1)
    if area <= 15:
        return "tiny"
    if area <= 45:
        return "small"
    if area <= 70:
        return "standard"
    if area <= 120:
        return "large"
    return "grand"


def _build_shell(
    type_id: str,
    layout_variant: int,
    program: Sequence[RoomRequest],
    *,
    exterior_door: bool,
) -> Tuple[List[List[str]], List[Room], Set[Position], Set[Position]]:
    width, height = 64, 28
    grid = [[" " for _ in range(width)] for _ in range(height)]
    floor_cells: Set[Position] = set()
    hall_cells: Set[Position] = set()
    door_cells: Set[Position] = set()
    variant = layout_variant % 4
    type_index = TYPE_ORDER.index(type_id) if type_id in TYPE_ORDER else 0
    slots = TOPOLOGIES[variant]
    parents = TOPOLOGY_PARENTS[variant]
    rooms: List[Room] = []

    for index, request in enumerate(program[: len(slots)]):
        role = str(request.get("role", "room"))
        private = bool(request.get("private", False))
        desired_size = str(request.get("size", "standard"))
        rect = _adjusted_rect(slots[index], type_index, index, variant, desired_size)
        x1, y1, x2, y2 = rect
        room: Room = dict(request)
        room.update({
            "role": role,
            "private": private,
            "rect": rect,
            "actual_size": _room_size_class(rect),
            "slot": index,
        })
        occupancy_kind = str(room.get("occupancy_kind", ""))
        if occupancy_kind == "guest":
            # Inns deliberately keep one person per private guest room.
            room["capacity"] = 1
        elif occupancy_kind == "resident":
            requested_capacity = max(1, int(room.get("capacity", 1) or 1))
            room["capacity"] = (
                2
                if str(room.get("role", "")) == "primary_bedroom"
                and str(room["actual_size"]) in {"standard", "large", "grand"}
                else requested_capacity
            )
        rooms.append(room)
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                if x in {x1, x2} or y in {y1, y2}:
                    grid[y][x] = "#"
                else:
                    grid[y][x] = "."
                    floor_cells.add((x, y))

    for child_index in range(1, len(rooms)):
        requested_parent = str(rooms[child_index].get("parent", ""))
        parent_index = next(
            (
                index
                for index, room in enumerate(rooms[:child_index])
                if str(room.get("id", "")) == requested_parent
            ),
            parents[child_index],
        )
        if parent_index is None or parent_index >= len(rooms):
            parent_index = 0
        rooms[child_index]["parent_index"] = parent_index
        rooms[child_index]["parent"] = str(rooms[parent_index].get("id", ""))
        parent_rect = rooms[parent_index]["rect"]
        child_rect = rooms[child_index]["rect"]
        path = _orthogonal_path(
            _center(parent_rect),
            _center(child_rect),
            horizontal_first=(variant + child_index) % 2 == 0,
        )
        for x, y in path:
            if 0 < x < width - 1 and 0 < y < height - 1:
                grid[y][x] = "."
                floor_cells.add((x, y))
                hall_cells.add((x, y))
        connection = str(rooms[child_index].get("connection", "hall"))
        if connection != "archway":
            x1, y1, x2, y2 = child_rect
            child_boundary = [
                (x, y)
                for x, y in path
                if x in {x1, x2} or y in {y1, y2}
                if x1 <= x <= x2 and y1 <= y <= y2
            ]
            if child_boundary:
                door_cells.add(child_boundary[0])
            if connection == "direct":
                px1, py1, px2, py2 = parent_rect
                parent_boundary = [
                    (x, y)
                    for x, y in path[1:]
                    if x in {px1, px2} or y in {py1, py2}
                    if px1 <= x <= px2 and py1 <= y <= py2
                ]
                if parent_boundary:
                    door_cells.add(parent_boundary[0])

    entrance_center = _center(rooms[0]["rect"])
    if exterior_door:
        entrance_path = _orthogonal_path((32, 27), entrance_center, horizontal_first=False)
        for x, y in entrance_path[1:]:
            if 0 < x < width - 1 and 0 < y < height:
                grid[y][x] = "."
                floor_cells.add((x, y))
                hall_cells.add((x, y))
        grid[27][32] = "D"

    for x, y in list(floor_cells):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] == " ":
                grid[ny][nx] = "#"
    for x, y in door_cells:
        grid[y][x] = "_"
    if exterior_door:
        grid[27][32] = "D"
    return grid, rooms, hall_cells, door_cells


def _room_candidates(room: Room, variant: int) -> List[Position]:
    x1, y1, x2, y2 = room["rect"]
    candidates: List[Position] = []
    for y in (y1 + 1, y2 - 1, y1 + 2, y2 - 2):
        for x in range(x1 + 1, x2):
            candidates.append((x, y))
    for x in (x1 + 1, x2 - 1, x1 + 2, x2 - 2):
        for y in range(y1 + 2, y2 - 1):
            candidates.append((x, y))
    unique = list(dict.fromkeys(candidates))
    if variant % 2:
        unique.reverse()
    return unique


def _furnish(
    grid: List[List[str]],
    rooms: Sequence[Room],
    hall_cells: Set[Position],
    door_cells: Set[Position],
    type_id: str,
    variant: int,
    fixture_variant: int,
    floor_count: int,
    game_table_glyphs: Sequence[str],
    business_upgrade: int,
    story_completed: bool,
    include_service: bool = True,
    player_owned: bool = False,
    furniture_placements: Optional[List[FurniturePlacement]] = None,
) -> None:
    protected = set(hall_cells) | set(door_cells)
    for x, y in list(door_cells):
        protected.update({(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)})
    catalog_placer = ProceduralFurniturePlacer(
        grid,
        protected,
        type_id,
        variant,
        fixture_variant,
        furniture_placements if furniture_placements is not None else [],
    )

    def put(room: Room, glyphs: Iterable[str]) -> List[Position]:
        placed: List[Position] = []
        candidates = _room_candidates(room, variant + fixture_variant)
        for glyph in glyphs:
            destination = next(
                (
                    (x, y)
                    for x, y in candidates
                    if grid[y][x] in {".", ","} and (x, y) not in protected
                ),
                None,
            )
            if destination is None:
                continue
            x, y = destination
            grid[y][x] = glyph
            placed.append(destination)
            protected.add(destination)
        return placed

    def put_cluster(
        room: Room,
        pattern: Sequence[Tuple[int, int, str]],
    ) -> List[Position]:
        """Place a coherent furniture group without crossing circulation."""
        x1, y1, x2, y2 = room["rect"]
        candidates = _room_candidates(room, variant + fixture_variant)
        candidates.extend(
            (x, y)
            for y in range(y1 + 1, y2)
            for x in range(x1 + 1, x2)
        )
        candidates = list(dict.fromkeys(candidates))
        transforms = (
            lambda dx, dy: (dx, dy),
            lambda dx, dy: (-dx, -dy),
            lambda dx, dy: (dy, -dx),
            lambda dx, dy: (-dy, dx),
        )
        transform_order = list(range(len(transforms)))
        shift = (variant + fixture_variant) % len(transform_order)
        transform_order = transform_order[shift:] + transform_order[:shift]
        for transform_index in transform_order:
            transform = transforms[transform_index]
            for anchor_x, anchor_y in candidates:
                cells: List[Tuple[int, int, str]] = []
                for dx, dy, glyph in pattern:
                    offset_x, offset_y = transform(dx, dy)
                    cells.append((anchor_x + offset_x, anchor_y + offset_y, glyph))
                if not all(
                    x1 < x < x2
                    and y1 < y < y2
                    and grid[y][x] in {".", ","}
                    and (x, y) not in protected
                    for x, y, _glyph in cells
                ):
                    continue
                placed: List[Position] = []
                for x, y, glyph in cells:
                    grid[y][x] = glyph
                    protected.add((x, y))
                    placed.append((x, y))
                return placed
        return []

    def table_ensemble(room: Room, chairs: int = 2) -> List[Position]:
        pattern: List[Tuple[int, int, str]] = [
            (0, 0, "t"),
            (-1, 0, "c"),
            (1, 0, "c"),
        ]
        if chairs >= 3:
            pattern.append((0, 1, "c"))
        if chairs >= 4:
            pattern.append((0, -1, "c"))
        return put_cluster(room, pattern)

    def line_ensemble(room: Room, glyphs: Sequence[str]) -> List[Position]:
        pattern = [(index, 0, str(glyph)) for index, glyph in enumerate(glyphs)]
        return put_cluster(room, pattern)

    def service_counter(room: Room, stocked: bool) -> None:
        x1, y1, x2, y2 = room["rect"]
        rows = (y1 + 2, y2 - 2, y1 + 1, y2 - 1)
        patterns = (("$", "-", "-", "&", "-", "-"), ("-", "-", "&", "-", "-"))
        pattern = patterns[0 if stocked else 1]
        for y in rows:
            starts = (x1 + 2, x2 - len(pattern) - 1)
            if (variant + fixture_variant) % 2:
                starts = tuple(reversed(starts))
            for start in starts:
                cells = [(start + offset, y) for offset in range(len(pattern))]
                if all(grid[cy][cx] == "." and (cx, cy) not in protected for cx, cy in cells):
                    clerk_position: Optional[Position] = None
                    for (cx, cy), glyph in zip(cells, pattern):
                        grid[cy][cx] = glyph
                        protected.add((cx, cy))
                        if glyph == "&":
                            clerk_position = (cx, cy)
                    if clerk_position is not None:
                        clerk_x, clerk_y = clerk_position
                        protected.update(
                            (clerk_x + dx, clerk_y + dy)
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                            if grid[clerk_y + dy][clerk_x + dx] in {".", ","}
                        )
                    return
        fallback = put(room, ("$", "&") if stocked else ("&",))
        if fallback:
            clerk_x, clerk_y = fallback[-1]
            protected.update(
                (clerk_x + dx, clerk_y + dy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if grid[clerk_y + dy][clerk_x + dx] in {".", ","}
            )

    # A small amount of floor color makes room purposes legible without clutter.
    for room in rooms:
        if str(room["role"]) in {"common", "common_room", "reading", "waiting", "lobby", "council"}:
            x1, y1, x2, y2 = room["rect"]
            for y in range(y1 + 2, y2 - 1):
                for x in range(x1 + 2, x2 - 1):
                    if grid[y][x] == "." and (x, y) not in protected:
                        grid[y][x] = ","

    first_room = rooms[0]
    if include_service:
        if type_id == "home":
            if not player_owned:
                if not table_ensemble(first_room, 2):
                    put(first_room, ("t", "c", "c"))
                put(first_room, ("&",))
        else:
            service_counter(first_room, type_id in {"general_store", "market_stall", "inn"})
    else:
        if not table_ensemble(first_room, 2):
            put(first_room, ("t", "c", "c"))
        put(first_room, ("P",))

    role_glyphs = {
        "common": ("t", "c", "c", "P"),
        "common_room": ("t", "c", "c", "t", "c", "c"),
        "kitchen": ("f", "P", "t", "c", "c"),
        "primary_bedroom": ("b", "l", "d", "c"),
        "bedroom": ("b", "l", "d"),
        "nursery": ("b", "l", "P"),
        "guest_room": ("b", "l", "d"),
        "en_suite": ("u", "P"),
        "pantry": ("s", "P"),
        "study": ("d", "P", "t", "c"),
        "storage": ("s", "P"),
        "sales": ("s", "$", "s"),
        "stockroom": ("s", "$", "P", "s"),
        "office": ("d", "P", "t", "c"),
        "delivery": ("s", "$", "x"),
        "display": ("$", "s", "P"),
        "produce": ("$", "$", "s"),
        "waiting": ("c", "c", "t", "P"),
        "examination": ("+", "b", "d"),
        "clinic_ward": ("b", "+", "d"),
        "pharmacy": ("+", "s", "P", "+"),
        "reception": ("P", "c"),
        "records": ("P", "d", "s"),
        "cell": ("b", "P"),
        "armory": ("x", "s", "P"),
        "circulation": ("P", "l"),
        "stacks": ("l", "l", "l", "P"),
        "reading": ("t", "c", "c", "l"),
        "archive": ("P", "l", "d"),
        "showroom": ("w", "a", "x"),
        "woodshop": ("w", "a", "x", "w"),
        "lumber": ("w", "w", "s"),
        "service": ("w", "a"),
        "forge": ("a", "x", "w"),
        "workshop": ("w", "a", "x", "s"),
        "materials": ("s", "x", "$"),
        "finishing": ("w", "P", "a"),
        "lobby": ("P", "c", "c"),
        "council": ("t", "c", "c", "c", "P"),
        "meeting": ("t", "c", "c", "P"),
    }
    def furnish_room(room: Room) -> None:
        role = str(room["role"])
        glyphs = role_glyphs.get(role, ("P",))
        if catalog_placer.furnish_room(room):
            return
        if role in {"common", "reading", "council", "meeting"}:
            if not table_ensemble(room, 3):
                put(room, glyphs)
            else:
                put(room, tuple(glyph for glyph in glyphs if glyph not in {"t", "c"}))
            return
        if role == "common_room":
            if not table_ensemble(room, 3):
                put(room, glyphs)
                return
            table_ensemble(room, 2)
            return
        if role == "kitchen":
            if not line_ensemble(room, ("f", "P", "P")):
                put(room, ("f", "P"))
            if not table_ensemble(room, 2):
                put(room, ("t", "c", "c"))
            return
        if role in {"primary_bedroom", "bedroom", "nursery", "guest_room"}:
            if not line_ensemble(room, glyphs[:3]):
                put(room, glyphs)
            elif len(glyphs) > 3:
                put(room, glyphs[3:])
            return
        if role in {"study", "office", "archive", "records"}:
            ordered = ("d", "c") + tuple(
                glyph for glyph in glyphs if glyph not in {"d", "c"}
            )
            if not line_ensemble(room, ordered[:3]):
                if not line_ensemble(room, ordered[:2]):
                    put(room, glyphs)
                else:
                    put(room, ordered[2:])
            else:
                put(room, ordered[3:])
            return
        if role in {"waiting", "lobby", "reception"}:
            if not line_ensemble(room, ("c", "t", "c")):
                put(room, glyphs)
            else:
                put(room, tuple(glyph for glyph in glyphs if glyph not in {"t", "c"}))
            return
        if role in {"examination", "clinic_ward", "cell"}:
            if not line_ensemble(room, glyphs):
                put(room, glyphs)
            return
        if not line_ensemble(room, glyphs):
            put(room, glyphs)

    if include_service and type_id != "home":
        furnish_room(first_room)
    if not (type_id == "home" and player_owned):
        for room in rooms[1:]:
            furnish_room(room)

    if type_id == "inn":
        common = next((room for room in rooms if room["role"] == "common_room"), first_room)
        put(common, tuple(game_table_glyphs[:2]))

    if floor_count > 1 and type_id in {"home", "inn"}:
        stair_cells = put(first_room, ("<",))
        if stair_cells:
            protected.add(stair_cells[0])

    if business_upgrade > 0:
        target = next((room for room in rooms if room["role"] in {"stockroom", "storage"}), first_room)
        put(target, tuple(("$", "s", "P")[: min(3, business_upgrade)]))
    if story_completed and type_id == "town_hall":
        put(first_room, ("f",))


def _upper_floor_program(type_id: str, program_variant: int = 1) -> Tuple[RoomRequest, ...]:
    variant = max(0, min(2, int(program_variant)))
    if type_id == "inn":
        guest_count = (4, 6, 6)[variant]
        rooms: List[RoomRequest] = [
            _room("landing", "landing", "semi_public", "large", connection="entrance"),
        ]
        if variant == 2:
            rooms.append(_room("upper_lounge", "common_room", "semi_public", "standard", parent="landing", connection="archway"))
        rooms.extend(
            _room(
                f"guest_{index + 1}",
                "guest_room",
                "private",
                "tiny" if variant == 2 and index == guest_count - 1 else "small" if index % 2 else "standard",
                parent="landing",
                capacity=1,
                occupancy_kind="guest",
            )
            for index in range(guest_count)
        )
        if len(rooms) < 9:
            rooms.append(_room("linen", "storage", "service", "tiny", parent="landing"))
        return tuple(rooms)
    if variant == 0:
        return (
            _room("landing", "landing", "semi_public", "large", connection="entrance"),
            _room("primary", "primary_bedroom", "private", "standard", parent="landing", capacity=2, occupancy_kind="resident"),
            _room("bedroom_2", "bedroom", "private", "small", parent="landing", capacity=1, occupancy_kind="resident"),
            _room("study", "study", "private", "small", parent="bedroom_2", connection="direct"),
            _room("storage", "storage", "service", "tiny", parent="landing"),
        )
    if variant == 2:
        return (
            _room("landing", "landing", "semi_public", "large", connection="entrance"),
            _room("upper_sitting", "common", "private", "standard", parent="landing", connection="archway"),
            _room("primary", "primary_bedroom", "private", "standard", parent="upper_sitting", capacity=2, occupancy_kind="resident"),
            _room("primary_bath", "en_suite", "private", "tiny", parent="primary", connection="direct"),
            _room("bedroom_2", "bedroom", "private", "standard", parent="upper_sitting", capacity=1, occupancy_kind="resident"),
            _room("bedroom_3", "bedroom", "private", "small", parent="upper_sitting", capacity=1, occupancy_kind="resident"),
            _room("study", "study", "private", "small", parent="bedroom_3", connection="direct"),
            _room("storage", "storage", "service", "tiny", parent="landing"),
        )
    return (
        _room("landing", "landing", "semi_public", "large", connection="entrance"),
        _room("primary", "primary_bedroom", "private", "standard", parent="landing", capacity=2, occupancy_kind="resident"),
        _room("bedroom_2", "bedroom", "private", "small", parent="landing", capacity=1, occupancy_kind="resident"),
        _room("primary_bath", "en_suite", "private", "tiny", parent="primary", connection="direct"),
        _room("study", "study", "private", "small", parent="bedroom_2", connection="direct"),
        _room("storage", "storage", "service", "tiny", parent="landing"),
    )


def procedural_room_program(
    type_id: str,
    floor_count: int = 1,
    floor_index: int = 0,
    room_overrides: Optional[Dict[str, str]] = None,
    program_variant: int = 1,
) -> Tuple[RoomRequest, ...]:
    type_id = type_id if type_id in TYPE_ORDER else "home"
    variant = max(0, min(2, int(program_variant)))
    if floor_index > 0:
        program = _upper_floor_program(type_id, variant)
    else:
        program = (
            _inn_program(floor_count, variant)
            if type_id == "inn"
            else ROOM_PROGRAM_VARIANTS[type_id][variant]
        )
    overrides = sanitize_procedural_room_overrides(room_overrides)
    if type_id != "home" or not overrides:
        return program
    adapted: List[RoomRequest] = []
    for request in program:
        room = dict(request)
        override_role = overrides.get(f"floor:{max(0, int(floor_index))}:{room.get('id', '')}")
        # Studies are deliberately flexible rooms. Other service rooms remain
        # intact so household growth cannot erase the only kitchen or pantry.
        if override_role and str(room.get("role", "")) == "study":
            room["adapted_from"] = "study"
            room["role"] = override_role
            room["privacy"] = "private"
            room["private"] = True
            room["capacity"] = 1
            room["occupancy_kind"] = "resident"
        adapted.append(room)
    return tuple(adapted)


def validate_modular_room_plan(
    grid: Sequence[Sequence[str]],
    rooms: Sequence[Room],
    hall_cells: Set[Position],
    door_cells: Set[Position],
    type_id: str,
    *,
    exterior_door: bool,
) -> Tuple[str, ...]:
    """Validate graph relationships and physical access for a modular plan."""
    problems: List[str] = []
    room_by_id = {str(room.get("id", "")): room for room in rooms}
    if len(room_by_id) != len(rooms) or "" in room_by_id:
        problems.append("room identifiers must be present and unique")
    roots = [room for room in rooms if not str(room.get("parent", ""))]
    if len(roots) != 1:
        problems.append(f"room graph has {len(roots)} entrance roots; expected one")

    for room in rooms:
        room_id = str(room.get("id", "room"))
        parent_id = str(room.get("parent", ""))
        connection = str(room.get("connection", "hall"))
        if connection not in {"entrance", "hall", "archway", "direct"}:
            problems.append(f"{room_id}: unsupported connection {connection}")
        if parent_id and parent_id not in room_by_id:
            problems.append(f"{room_id}: parent room {parent_id} is missing")
        if not parent_id and connection != "entrance":
            problems.append(f"{room_id}: root room is not marked as the entrance")
        x1, y1, x2, y2 = room.get("rect", (0, 0, 0, 0))
        minimum_span = 2 if str(room.get("size", "")) == "tiny" else 3
        if x2 - x1 < minimum_span or y2 - y1 < minimum_span:
            problems.append(f"{room_id}: room is too small to furnish and navigate")
        capacity = int(room.get("capacity", 0) or 0)
        occupancy_kind = str(room.get("occupancy_kind", ""))
        if capacity > 0 and occupancy_kind not in {"resident", "guest"}:
            problems.append(f"{room_id}: occupied room has no residential purpose")
        if type_id == "inn" and occupancy_kind == "guest" and capacity != 1:
            problems.append(f"{room_id}: inn guest rooms must house exactly one guest")
        if connection == "direct" and parent_id in room_by_id:
            allowed_parents = DIRECT_DEPENDENT_ROLES.get(str(room.get("role", "")))
            parent_role = str(room_by_id[parent_id].get("role", ""))
            if allowed_parents and parent_role not in allowed_parents:
                problems.append(
                    f"{room_id}: {room.get('role')} cannot depend on {parent_role}"
                )

    if rooms:
        visited_ids: Set[str] = set()
        pending = [str(rooms[0].get("id", ""))]
        while pending:
            room_id = pending.pop()
            if room_id in visited_ids:
                continue
            visited_ids.add(room_id)
            pending.extend(
                str(room.get("id", ""))
                for room in rooms
                if str(room.get("parent", "")) == room_id
            )
        if len(visited_ids) != len(rooms):
            problems.append("room graph contains a disconnected branch")

    if grid and grid[0]:
        start: Optional[Position] = None
        if exterior_door:
            start = next(
                ((x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == "D"),
                None,
            )
        elif rooms:
            start = _center(rooms[0]["rect"])
        passable = {".", ",", "D", "_", "|"}
        reachable: Set[Position] = set()
        if start is not None:
            pending_positions = [start]
            while pending_positions:
                x, y = pending_positions.pop()
                if (x, y) in reachable:
                    continue
                if not (0 <= y < len(grid) and 0 <= x < len(grid[y])):
                    continue
                if str(grid[y][x]) not in passable:
                    continue
                reachable.add((x, y))
                pending_positions.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
        for room in rooms:
            center = _center(room["rect"])
            if center not in reachable:
                problems.append(f"{room.get('id', 'room')}: center is unreachable from the entrance")
    if exterior_door and sum(str(tile) == "D" for row in grid for tile in row) != 1:
        problems.append("ground floor must have exactly one exterior entrance")
    if len(door_cells) > len(rooms) * 2:
        problems.append("room graph generated too many doors")
    if not hall_cells and len(rooms) > 1:
        problems.append("multi-room plan has no circulation cells")
    return tuple(problems)


def procedural_interior_room_plan(
    type_id: str,
    layout_variant: int,
    floor_count: int = 1,
    floor_index: int = 0,
    room_overrides: Optional[Dict[str, str]] = None,
    program_variant: int = 1,
) -> Dict[str, object]:
    """Return stable room metadata shared by generation, NPCs, and inspection."""
    type_id = type_id if type_id in TYPE_ORDER else "home"
    program = procedural_room_program(
        type_id,
        floor_count,
        floor_index,
        room_overrides,
        program_variant,
    )
    exterior_door = floor_index == 0
    grid, rooms, halls, doors = _build_shell(
        type_id,
        layout_variant,
        program,
        exterior_door=exterior_door,
    )
    capacities: Dict[str, int] = {"resident": 0, "guest": 0}
    for room in rooms:
        kind = str(room.get("occupancy_kind", ""))
        if kind in capacities:
            capacities[kind] += int(room.get("capacity", 0) or 0)
    connections = tuple(
        {
            "from": str(room.get("parent", "")),
            "to": str(room.get("id", "")),
            "kind": str(room.get("connection", "hall")),
        }
        for room in rooms
        if str(room.get("parent", ""))
    )
    return {
        "type_id": type_id,
        "floor": max(0, int(floor_index)),
        "program_variant": max(0, min(2, int(program_variant))),
        "program_name": ROOM_PROGRAM_VARIANT_NAMES[max(0, min(2, int(program_variant)))],
        "rooms": tuple(dict(room) for room in rooms),
        "connections": connections,
        "resident_capacity": capacities["resident"],
        "guest_capacity": capacities["guest"],
        "validation": validate_modular_room_plan(
            grid,
            rooms,
            halls,
            doors,
            type_id,
            exterior_door=exterior_door,
        ),
    }


def procedural_building_room_capacity(
    type_id: str,
    layout_variant: int = 0,
    floor_count: int = 1,
    room_overrides: Optional[Dict[str, str]] = None,
    program_variant: int = 1,
) -> int:
    """Derive capacity from physical bedrooms rather than a catalog constant."""
    capacity = 0
    for floor_index in range(max(1, int(floor_count))):
        plan = procedural_interior_room_plan(
            type_id,
            layout_variant,
            max(1, int(floor_count)),
            floor_index,
            room_overrides,
            program_variant,
        )
        if type_id == "inn":
            capacity += int(plan["guest_capacity"])
        else:
            capacity += int(plan["resident_capacity"])
    return max(0, capacity)


def build_procedural_ground_floor(
    type_id: str,
    layout_variant: int,
    fixture_variant: int,
    floor_count: int,
    *,
    game_table_glyphs: Sequence[str] = (),
    business_upgrade: int = 0,
    story_completed: bool = False,
    player_owned: bool = False,
    room_overrides: Optional[Dict[str, str]] = None,
    program_variant: int = 1,
    furniture_placements: Optional[List[FurniturePlacement]] = None,
) -> List[List[str]]:
    type_id = type_id if type_id in TYPE_ORDER else "home"
    program = procedural_room_program(
        type_id,
        floor_count,
        0,
        room_overrides,
        program_variant,
    )
    grid, rooms, halls, doors = _build_shell(
        type_id,
        layout_variant,
        program,
        exterior_door=True,
    )
    _furnish(
        grid,
        rooms,
        halls,
        doors,
        type_id,
        layout_variant,
        fixture_variant,
        floor_count,
        game_table_glyphs,
        max(0, int(business_upgrade)),
        bool(story_completed),
        True,
        bool(player_owned),
        furniture_placements,
    )
    return grid


def build_procedural_upper_floor(
    type_id: str,
    layout_variant: int,
    floor_index: int,
    floor_count: int,
    room_overrides: Optional[Dict[str, str]] = None,
    program_variant: int = 1,
    furniture_placements: Optional[List[FurniturePlacement]] = None,
) -> List[List[str]]:
    type_id = type_id if type_id in TYPE_ORDER else "home"
    program = procedural_room_program(
        type_id,
        floor_count,
        floor_index,
        room_overrides,
        program_variant,
    )
    grid, rooms, halls, doors = _build_shell(
        type_id,
        layout_variant,
        program,
        exterior_door=False,
    )
    _furnish(
        grid,
        rooms,
        halls,
        doors,
        type_id,
        layout_variant,
        floor_index,
        1,
        (),
        0,
        False,
        False,
        False,
        furniture_placements,
    )
    # Upper floors are private living space; the first room is a stair landing.
    landing = rooms[0]
    candidates = _room_candidates(landing, layout_variant + floor_index)
    stair = next(((x, y) for x, y in candidates if grid[y][x] in {".", ","} and (x, y) not in halls), None)
    if stair is None:
        stair = _center(landing["rect"])
    grid[stair[1]][stair[0]] = ">"
    if floor_index < floor_count - 1:
        next_stair = next(
            ((x, y) for x, y in reversed(candidates) if grid[y][x] in {".", ","}),
            None,
        )
        if next_stair:
            grid[next_stair[1]][next_stair[0]] = "<"
    return grid


def procedural_residence_furnishing_candidates(
    layout_variant: int,
) -> Dict[str, List[Position]]:
    """Return navigation-safe source positions grouped by household room."""
    grid, rooms, halls, doors = _build_shell(
        "home",
        layout_variant,
        ROOM_PROGRAMS["home"],
        exterior_door=True,
    )
    protected = set(halls) | set(doors)
    for x, y in doors:
        protected.update({(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)})
    grouped: Dict[str, List[Position]] = {}
    for room in rooms:
        role = str(room["role"])
        group_role = {
            "primary_bedroom": "bedroom",
            "guest_room": "bedroom",
            "en_suite": "bath",
            "pantry": "storage",
        }.get(role, role)
        grouped.setdefault(group_role, []).extend(
            (x, y)
            for x, y in _room_candidates(room, layout_variant)
            if grid[y][x] == "." and (x, y) not in protected
        )
    grouped["any"] = [
        (x, y)
        for role in ("common", "bedroom", "kitchen", "study", "storage")
        for x, y in grouped.get(role, ())
    ]
    return grouped


__all__ = [
    "ROOM_PROGRAM_VARIANT_NAMES",
    "ROOM_PROGRAM_VARIANTS",
    "build_procedural_ground_floor",
    "build_procedural_upper_floor",
    "procedural_building_room_capacity",
    "procedural_interior_room_plan",
    "procedural_residence_furnishing_candidates",
    "procedural_room_program",
    "sanitize_procedural_room_overrides",
    "validate_modular_room_plan",
]
