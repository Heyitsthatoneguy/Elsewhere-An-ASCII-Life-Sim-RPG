from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ascii_battle_prototype.combat.models import Pos, Unit, Weapon


ENEMY_ARCHETYPES: Dict[str, Dict[str, object]] = {
    "Skirmisher": {"role": "skirmisher", "family": "Crow", "cooldowns": {"Evasive Hop": 0}},
    "Brute": {"role": "brute", "family": "Boar", "cooldowns": {"Brutal Charge": 1, "War Cry": 0}},
    "Controller": {"role": "controller", "family": "Vine", "cooldowns": {"Binding Roots": 1, "Toxic Burst": 2}},
    "Ranged": {"role": "ranged", "family": "Bandit", "cooldowns": {"Evasive Hop": 0}},
    "Pouncer": {"role": "pouncer", "family": "Razor Hare", "cooldowns": {"Needle Dash": 0, "Evasive Hop": 0}},
    "Guardian": {"role": "guardian", "family": "Shield Guard", "cooldowns": {"War Cry": 0, "Shield Wall": 1}},
    "Blighter": {"role": "blighter", "family": "Slime", "cooldowns": {"Poison Claw": 0, "Ooze Mire": 1}},
    "Boss": {"role": "boss", "family": "Old Briarthorn", "cooldowns": {"Binding Roots": 0, "Toxic Burst": 1, "War Cry": 0, "Briar Heart": 0}},
}
EQUIPMENT_SLOTS = ("weapon", "armor", "charm")
MAP_THEMES = ("Meadow", "Ruins", "River", "Fortress", "Cavern", "Wild")
DUNGEON_ROOM_THEMES = ("Any", "overgrown", "root", "sunken", "crystal", "quarry")
DUNGEON_ROOM_PATTERNS = ("Open", "Pillars", "Crossroads", "Pools", "Ruined Ring", "Split Hall")
BUILDING_TEMPLATE_TYPES = (
    "home",
    "general_store",
    "inn",
    "clinic",
    "library",
    "carpenter",
    "workshop",
    "town_hall",
)
BUILDING_TEMPLATE_TYPE_LABELS = {
    "home": "Home",
    "general_store": "General Store",
    "inn": "Inn",
    "clinic": "Clinic",
    "library": "Library",
    "carpenter": "Carpenter",
    "workshop": "Workshop",
    "town_hall": "Town Hall",
}
BUILDING_TEMPLATE_ZONE_KINDS = (
    "bedroom",
    "kitchen",
    "shopping_counter",
    "stockroom",
    "clinic_ward",
    "library_stacks",
    "workshop",
    "office",
    "dining",
    "storage",
    "public_hall",
)

# Rendering procedural interiors asks for the same filtered template pool
# several times per frame. Keep the sanitized, read-only records until the
# backing custom-content file changes instead of reparsing/deep-copying the
# complete library for every request.
_CUSTOM_BUILDING_TEMPLATE_RECORD_CACHE: Dict[
    Tuple[str, bool, object], Tuple[Dict[str, object], ...]
] = {}
BUILDING_TEMPLATE_ZONE_LABELS = {
    "bedroom": "Bedroom",
    "kitchen": "Kitchen",
    "shopping_counter": "Shopping Counter",
    "stockroom": "Stockroom",
    "clinic_ward": "Clinic Ward",
    "library_stacks": "Library Stacks",
    "workshop": "Workshop",
    "office": "Office",
    "dining": "Dining/Common Room",
    "storage": "Storage",
    "public_hall": "Public Hall",
}
BUILDING_TEMPLATE_WIDTH = 64
BUILDING_TEMPLATE_HEIGHT = 28
BUILDING_TEMPLATE_MAX_FLOORS = 4
BUILDING_TEMPLATE_ALLOWED_TILES = {
    " ", "#", "-", ".", ",", "D", "&", "$", "+", "l", "w", "x",
    "a", "b", "t", "c", "s", "f", "P", "d", "p", "<", "U", ">",
    "|", "_",
}
BUILDING_TEMPLATE_COLOR_KEYS = (
    "default",
    "white",
    "brown",
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "gray",
)
BUILDING_TEMPLATE_COLOR_LABELS = {
    "default": "Default",
    "white": "White",
    "brown": "Brown",
    "red": "Red",
    "orange": "Orange",
    "yellow": "Yellow",
    "green": "Green",
    "blue": "Blue",
    "purple": "Purple",
    "gray": "Gray",
}
BUILDING_TEMPLATE_MAX_COLOR_MARKS = 512
BUILDING_TEMPLATE_MAX_SPAWNS = 32
BUILDING_TEMPLATE_REQUIRED_TILES = {
    "home": ("&", "b", "f"),
    "general_store": ("&", "$", "s"),
    "inn": ("&", "$", "b", "f"),
    "clinic": ("&", "+", "b"),
    "library": ("&", "l", "P"),
    "carpenter": ("&", "w", "a", "x"),
    "workshop": ("&", "w", "a", "x"),
    "town_hall": ("&", "d", "P"),
}


def _clean_text(value: object, maximum: int) -> str:
    return " ".join(str(value or "").strip().split())[:maximum]


def _clean_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _clean_names(value: object, maximum: int = 8) -> List[str]:
    if not isinstance(value, (list, tuple)):
        return []
    clean: List[str] = []
    seen = set()
    for raw in value:
        name = _clean_text(raw, 32)
        key = name.casefold()
        if not name or key in seen:
            continue
        clean.append(name)
        seen.add(key)
        if len(clean) >= maximum:
            break
    return clean


def _clean_building_template_color(value: object) -> str:
    key = _clean_text(value, 16).casefold().replace(" ", "_")
    return key if key in BUILDING_TEMPLATE_COLOR_KEYS else "default"


def sanitize_custom_enemy(raw: object) -> Optional[Dict[str, object]]:
    if not isinstance(raw, dict):
        return None
    name = _clean_text(raw.get("name"), 28)
    if not name:
        return None
    archetype = str(raw.get("archetype", "Skirmisher") or "Skirmisher")
    if archetype not in ENEMY_ARCHETYPES:
        archetype = "Skirmisher"
    glyph = str(raw.get("glyph", "?") or "?").strip()[:1]
    if not glyph or not glyph.isprintable() or glyph.isspace():
        glyph = "?"
    boss = archetype == "Boss"
    range_max = _clean_int(raw.get("range_max"), 1, 1, 7)
    range_min = _clean_int(raw.get("range_min"), 1, 1, min(4, range_max))
    return {
        "name": name,
        "description": _clean_text(raw.get("description"), 180) or "A custom tactical enemy.",
        "glyph": glyph,
        "archetype": archetype,
        "max_hp": _clean_int(raw.get("max_hp"), 24, 8, 120 if boss else 70),
        "move_range": _clean_int(raw.get("move_range"), 4, 1, 8),
        "weapon_name": _clean_text(raw.get("weapon_name"), 28) or "Custom Attack",
        "damage": _clean_int(raw.get("damage"), 4, 1, 12 if boss else 9),
        "range_min": range_min,
        "range_max": range_max,
        "defense": _clean_int(raw.get("defense"), 0, 0, 4),
        "boss": boss,
    }


def custom_enemy_threat(record: Dict[str, object]) -> int:
    enemy = sanitize_custom_enemy(record)
    if enemy is None:
        return 0
    score = int(enemy["max_hp"]) // 5 + int(enemy["damage"]) * 2
    score += int(enemy["move_range"]) + int(enemy["range_max"]) + int(enemy["defense"]) * 3
    if enemy["boss"]:
        score += 18
    return score


def custom_enemy_summary(record: Dict[str, object]) -> List[str]:
    enemy = sanitize_custom_enemy(record)
    if enemy is None:
        return ["Invalid custom enemy."]
    return [
        str(enemy["name"]).upper(),
        "",
        str(enemy["description"]),
        "",
        f"Glyph: {enemy['glyph']} | Archetype: {enemy['archetype']}",
        f"HP: {enemy['max_hp']} | Defense: {enemy['defense']} | Move: {enemy['move_range']}",
        f"Attack: {enemy['weapon_name']} | Damage {enemy['damage']} | Range {enemy['range_min']}-{enemy['range_max']}",
        f"Estimated threat: {custom_enemy_threat(enemy)}",
        "",
        "The archetype supplies tested AI priorities and special actions.",
    ]


def custom_enemy_records() -> List[Dict[str, object]]:
    from ascii_farmstead_custom_content import load_custom_content

    content, _warnings = load_custom_content()
    return [dict(record) for record in content.get("enemies", []) if isinstance(record, dict)]


def create_custom_enemy_templates(
    start_positions: Dict[str, Pos],
    existing_names: Iterable[str] = (),
) -> List[Unit]:
    reserved = {str(name).casefold() for name in existing_names}
    templates: List[Unit] = []
    for raw in custom_enemy_records():
        enemy = sanitize_custom_enemy(raw)
        if enemy is None or str(enemy["name"]).casefold() in reserved:
            continue
        archetype = ENEMY_ARCHETYPES[str(enemy["archetype"])]
        name = str(enemy["name"])
        templates.append(Unit(
            name,
            str(enemy["glyph"]),
            start_positions.get(name, (16, 5)),
            int(enemy["max_hp"]),
            int(enemy["max_hp"]),
            0,
            0,
            int(enemy["move_range"]),
            Weapon(
                str(enemy["weapon_name"]),
                int(enemy["damage"]),
                int(enemy["range_min"]),
                max(int(enemy["range_min"]), int(enemy["range_max"])),
            ),
            "enemy",
            role=str(archetype["role"]),
            cooldowns=dict(archetype["cooldowns"]),
            boss=bool(enemy["boss"]),
            defense=int(enemy["defense"]),
        ))
        reserved.add(name.casefold())
    return templates


def custom_enemy_behavior_family(enemy_name: object) -> str:
    base = str(enemy_name or "")
    if base.startswith("Elite "):
        base = base[6:]
    parts = base.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        base = parts[0]
    for raw in custom_enemy_records():
        enemy = sanitize_custom_enemy(raw)
        if enemy and str(enemy["name"]) == base:
            return str(ENEMY_ARCHETYPES[str(enemy["archetype"])]["family"])
    return base


def sanitize_custom_equipment(raw: object) -> Optional[Dict[str, object]]:
    if not isinstance(raw, dict):
        return None
    name = _clean_text(raw.get("name"), 28)
    if not name:
        return None
    slot = str(raw.get("slot", "weapon") or "weapon")
    if slot not in EQUIPMENT_SLOTS:
        slot = "weapon"
    return {
        "name": name,
        "slot": slot,
        "description": _clean_text(raw.get("description"), 180) or "Custom tactical equipment.",
        "dmg": _clean_int(raw.get("dmg"), 0, -2, 4),
        "hp": _clean_int(raw.get("hp"), 0, -8, 14),
        "mp": _clean_int(raw.get("mp"), 0, -5, 8),
        "move": _clean_int(raw.get("move"), 0, -2, 2),
        "range_max": _clean_int(raw.get("range_max"), 0, 0, 2) if slot == "weapon" else 0,
        "coin_cost": _clean_int(raw.get("coin_cost"), 18, 1, 99),
        "material": _clean_text(raw.get("material"), 24),
        "material_cost": _clean_int(raw.get("material_cost"), 0, 0, 5),
    }


def custom_equipment_summary(record: Dict[str, object]) -> List[str]:
    gear = sanitize_custom_equipment(record)
    if gear is None:
        return ["Invalid custom equipment."]
    mods = []
    for key, label in (("dmg", "DMG"), ("hp", "HP"), ("mp", "MP"), ("move", "MV"), ("range_max", "RNG")):
        value = int(gear[key])
        if value:
            mods.append(f"{label}{value:+d}")
    cost = f"{gear['coin_cost']} Coin"
    if gear["material"] and int(gear["material_cost"]) > 0:
        cost += f", {gear['material_cost']} {gear['material']}"
    return [
        str(gear["name"]).upper(),
        "",
        str(gear["description"]),
        "",
        f"Slot: {str(gear['slot']).title()}",
        f"Bonuses: {', '.join(mods) or 'none'}",
        f"Crafting cost: {cost}",
        "",
        "Available to all tactical party members through the normal loadout menus.",
    ]


def custom_equipment_records() -> List[Dict[str, object]]:
    from ascii_farmstead_custom_content import load_custom_content

    content, _warnings = load_custom_content()
    return [dict(record) for record in content.get("equipment", []) if isinstance(record, dict)]


def custom_equipment_defs(
    existing_names: Optional[Dict[str, Iterable[str]]] = None,
) -> Dict[str, Dict[str, Dict[str, object]]]:
    existing_names = existing_names or {}
    reserved = {
        slot: {str(name).casefold() for name in names}
        for slot, names in existing_names.items()
    }
    result: Dict[str, Dict[str, Dict[str, object]]] = {slot: {} for slot in EQUIPMENT_SLOTS}
    for raw in custom_equipment_records():
        gear = sanitize_custom_equipment(raw)
        if gear is None:
            continue
        slot = str(gear["slot"])
        name = str(gear["name"])
        if name.casefold() in reserved.setdefault(slot, set()):
            continue
        cost = {"Coin": int(gear["coin_cost"])}
        if gear["material"] and int(gear["material_cost"]) > 0:
            cost[str(gear["material"])] = int(gear["material_cost"])
        result[slot][name] = {
            "heroes": "all",
            "cost": cost,
            "desc": str(gear["description"]),
            "dmg": int(gear["dmg"]),
            "hp": int(gear["hp"]),
            "mp": int(gear["mp"]),
            "move": int(gear["move"]),
            "range_max": int(gear["range_max"]),
            "custom": True,
        }
        reserved[slot].add(name.casefold())
    return result


def sanitize_custom_map(raw: object) -> Optional[Dict[str, object]]:
    if not isinstance(raw, dict):
        return None
    name = _clean_text(raw.get("name"), 32)
    if not name:
        return None
    theme = str(raw.get("theme", "Meadow") or "Meadow")
    if theme not in MAP_THEMES:
        theme = "Meadow"
    record = {
        "name": name,
        "description": _clean_text(raw.get("description"), 180) or "A custom tactical arena.",
        "theme": theme,
        "width": _clean_int(raw.get("width"), 24, 16, 36),
        "height": _clean_int(raw.get("height"), 14, 10, 20),
        "cover_density": _clean_int(raw.get("cover_density"), 2, 0, 4),
        "hazard_density": _clean_int(raw.get("hazard_density"), 1, 0, 4),
        "seed": _clean_int(raw.get("seed"), 1, 0, 999999999),
        "enemy_names": _clean_names(raw.get("enemy_names"), 6),
        "objective": str(raw.get("objective", "Defeat All") or "Defeat All"),
    }
    if record["objective"] not in {"Defeat All", "Survive", "Hold Zone", "Destroy Objects"}:
        record["objective"] = "Defeat All"
    rows, positions = generate_custom_map_layout(record)
    record["rows"] = rows
    record["positions"] = {key: [int(pos[0]), int(pos[1])] for key, pos in positions.items()}
    return record


def generate_custom_map_layout(record: Dict[str, object]) -> Tuple[List[str], Dict[str, Pos]]:
    width = int(record["width"])
    height = int(record["height"])
    rng = random.Random(int(record["seed"]) ^ sum((i + 1) * ord(ch) for i, ch in enumerate(str(record["name"]))))
    grid = [["." for _ in range(width)] for _ in range(height)]
    theme = str(record["theme"])
    cover_tiles = {
        "Meadow": ['"', "T", "^", "C"],
        "Ruins": ["#", "^", "C", "B"],
        "River": ['"', "^", "C", "~"],
        "Fortress": ["#", "C", "B", "^"],
        "Cavern": ["#", "^", "m", "C"],
        "Wild": ["T", '"', "*", "^"],
    }[theme]
    hazard_tiles = {
        "Meadow": [":", "*", "+"],
        "Ruins": ["B", "*", "m"],
        "River": ["~", ":", "=", "+"],
        "Fortress": ["B", "*", ":"],
        "Cavern": ["_", "m", "*", ":"],
        "Wild": ["*", ":", "~", "+"],
    }[theme]

    cover_count = int(record["cover_density"]) * max(2, width * height // 35)
    hazard_count = int(record["hazard_density"]) * max(1, width * height // 55)
    protected = set()
    mid = height // 2
    for x in range(width):
        protected.add((x, mid))
    for y in range(max(0, mid - 1), min(height, mid + 2)):
        for x in range(0, 7):
            protected.add((x, y))
        for x in range(max(0, width - 7), width):
            protected.add((x, y))
    candidates = [(x, y) for y in range(height) for x in range(width) if (x, y) not in protected]
    rng.shuffle(candidates)
    for x, y in candidates[:cover_count]:
        grid[y][x] = rng.choice(cover_tiles)
    remaining = [(x, y) for x, y in candidates[cover_count:] if grid[y][x] == "."]
    rng.shuffle(remaining)
    for x, y in remaining[:hazard_count]:
        grid[y][x] = rng.choice(hazard_tiles)
    if theme in {"River", "Cavern"}:
        river_x = width // 2
        for y in range(height):
            if y in {mid - 1, mid, mid + 1}:
                grid[y][river_x] = "="
            elif (river_x, y) not in protected:
                grid[y][river_x] = "~"
    if theme == "Fortress":
        for x in range(width):
            grid[0][x] = "#"
            grid[height - 1][x] = "#"
        for y in range(height):
            grid[y][0] = "#"
            grid[y][width - 1] = "#"
        for x in range(width // 2 - 1, width // 2 + 2):
            grid[0][x] = "."
            grid[height - 1][x] = "."
    for x in range(width):
        grid[mid][x] = "."
    if str(record.get("objective", "")) == "Destroy Objects":
        object_positions = [
            (width // 2 - 3, max(1, mid - 3)),
            (width // 2 + 2, min(height - 2, mid + 3)),
            (width - 7, mid),
        ]
        for index, (x, y) in enumerate(object_positions):
            if 0 <= y < height and 0 <= x < width:
                grid[y][x] = "B" if index % 2 == 0 else "C"

    positions: Dict[str, Pos] = {
        "Rook": (2, mid),
        "Mira": (2, min(height - 2, mid + 2)),
        "Brom": (3, min(height - 2, mid + 1)),
        "Aria": (3, max(1, mid - 1)),
        "Nia": (2, max(1, mid - 2)),
        "Dax": (4, min(height - 2, mid + 2)),
        "Luma": (4, max(1, mid - 2)),
    }
    enemy_names = list(record.get("enemy_names", [])) or ["Slime", "Wolf", "Bandit"]
    for index, name in enumerate(enemy_names):
        x = width - 3 - (index % 2)
        y = max(1, min(height - 2, mid - 2 + index * 2))
        positions[str(name)] = (x, y)
        grid[y][x] = "."
    for x, y in positions.values():
        if 0 <= y < height and 0 <= x < width:
            grid[y][x] = "."
    return ["".join(row) for row in grid], positions


def custom_map_summary(record: Dict[str, object]) -> List[str]:
    arena = sanitize_custom_map(record)
    if arena is None:
        return ["Invalid custom map."]
    rows = [str(row) for row in arena["rows"]]
    preview_rows = rows if len(rows) <= 12 else rows[::2]
    preview_note = "" if len(preview_rows) == len(rows) else "Preview shows every other map row."
    return [
        str(arena["name"]).upper(),
        "",
        str(arena["description"]),
        f"Theme: {arena['theme']} | Size: {arena['width']}x{arena['height']} | Seed: {arena['seed']}",
        f"Cover: {arena['cover_density']}/4 | Hazards: {arena['hazard_density']}/4",
        f"Objective: {arena['objective']}",
        f"Default enemies: {', '.join(arena['enemy_names']) or 'Slime, Wolf, Bandit'}",
        preview_note,
        "",
        *preview_rows,
    ]


def custom_map_records() -> List[Dict[str, object]]:
    from ascii_farmstead_custom_content import load_custom_content

    content, _warnings = load_custom_content()
    return [dict(record) for record in content.get("maps", []) if isinstance(record, dict)]


def custom_combat_maps(existing_names: Iterable[str] = ()) -> List[Tuple[str, List[List[str]], Dict[str, Pos]]]:
    from ascii_battle_prototype.combat.constants import TILE_TREE

    reserved = {str(name).casefold() for name in existing_names}
    arenas = []
    for raw in custom_map_records():
        arena = sanitize_custom_map(raw)
        if arena is None or str(arena["name"]).casefold() in reserved:
            continue
        grid = [list(str(row).replace("T", TILE_TREE)) for row in arena["rows"]]
        positions = {
            str(name): (int(value[0]), int(value[1]))
            for name, value in arena["positions"].items()
            if isinstance(value, (list, tuple)) and len(value) == 2
        }
        arenas.append((str(arena["name"]), grid, positions))
        reserved.add(str(arena["name"]).casefold())
    return arenas


def custom_map_loadout(map_name: str) -> List[str]:
    for raw in custom_map_records():
        arena = sanitize_custom_map(raw)
        if arena and str(arena["name"]) == str(map_name):
            return list(arena["enemy_names"]) or ["Slime", "Wolf", "Bandit"]
    return []


def custom_mission_presets() -> List[Dict[str, object]]:
    presets = []
    for raw in custom_map_records():
        arena = sanitize_custom_map(raw)
        if arena is None:
            continue
        presets.append({
            "name": f"Custom: {arena['name']}",
            "map": str(arena["name"]),
            "enemies": list(arena["enemy_names"]) or ["Slime", "Wolf", "Bandit"],
            "objective": str(arena["objective"]),
            "theme": "custom",
            "flavor": str(arena["description"]),
            "custom": True,
        })
    return presets


def sanitize_custom_dungeon_room(raw: object) -> Optional[Dict[str, object]]:
    if not isinstance(raw, dict):
        return None
    name = _clean_text(raw.get("name"), 28)
    if not name:
        return None
    theme = str(raw.get("theme", "Any") or "Any")
    if theme not in DUNGEON_ROOM_THEMES:
        theme = "Any"
    pattern = str(raw.get("pattern", "Open") or "Open")
    if pattern not in DUNGEON_ROOM_PATTERNS:
        pattern = "Open"
    record = {
        "name": name,
        "description": _clean_text(raw.get("description"), 180) or "A custom dungeon-room template.",
        "theme": theme,
        "pattern": pattern,
        "density": _clean_int(raw.get("density"), 2, 0, 4),
        "seed": _clean_int(raw.get("seed"), 1, 0, 999999999),
        "enabled": bool(raw.get("enabled", False)),
    }
    record["rows"] = generate_custom_dungeon_room_rows(record)
    return record


def generate_custom_dungeon_room_rows(record: Dict[str, object]) -> List[str]:
    width, height = 9, 7
    grid = [["." for _ in range(width)] for _ in range(height)]
    rng = random.Random(int(record["seed"]) ^ sum(ord(ch) for ch in str(record["name"])))
    pattern = str(record["pattern"])
    density = int(record["density"])
    obstacles = {
        "Any": ["#", "'", '"', ":", ";"],
        "overgrown": ["#", "'", '"'],
        "root": ["#", "'", '"'],
        "sunken": ["#", "~", ":"],
        "crystal": ["#", ";", ":"],
        "quarry": ["#", ":", ";"],
    }[str(record["theme"])]
    placements: List[Tuple[int, int]] = []
    if pattern == "Pillars":
        placements = [(2, 2), (6, 2), (2, 4), (6, 4)]
    elif pattern == "Crossroads":
        placements = [(2, 1), (6, 1), (2, 5), (6, 5)]
    elif pattern == "Pools":
        placements = [(2, 2), (3, 2), (5, 4), (6, 4)]
        obstacles = ["~", ":", "'"]
    elif pattern == "Ruined Ring":
        placements = [(2, 1), (4, 1), (6, 1), (2, 5), (4, 5), (6, 5), (1, 3), (7, 3)]
    elif pattern == "Split Hall":
        placements = [(2, y) for y in range(1, 6)] + [(6, y) for y in range(1, 6)]
    else:
        placements = [(x, y) for y in range(1, 6) for x in range(1, 8)]
        rng.shuffle(placements)
        placements = placements[:density * 2]
    count = min(len(placements), max(0, density * 3))
    for x, y in placements[:count]:
        grid[y][x] = rng.choice(obstacles)
    # The permanent center cross guarantees every stamp leaves traversable
    # horizontal and vertical routes through the room.
    for x in range(width):
        grid[height // 2][x] = "."
    for y in range(height):
        grid[y][width // 2] = "."
    return ["".join(row) for row in grid]


def custom_dungeon_room_summary(record: Dict[str, object]) -> List[str]:
    room = sanitize_custom_dungeon_room(record)
    if room is None:
        return ["Invalid custom dungeon room."]
    return [
        str(room["name"]).upper(),
        "",
        str(room["description"]),
        f"Theme: {room['theme']} | Pattern: {room['pattern']} | Density: {room['density']}/4",
        f"Status: {'enabled' if room['enabled'] else 'disabled'}",
        "",
        *[str(row) for row in room["rows"]],
        "",
        "The center row and column are always kept walkable.",
    ]


def custom_dungeon_room_records(enabled_only: bool = False, theme: str = "") -> List[Dict[str, object]]:
    from ascii_farmstead_custom_content import load_custom_content

    content, _warnings = load_custom_content()
    rooms = []
    for raw in content.get("dungeon_rooms", []):
        room = sanitize_custom_dungeon_room(raw)
        if room is None or (enabled_only and not room["enabled"]):
            continue
        if theme and room["theme"] not in {"Any", theme}:
            continue
        rooms.append(room)
    return rooms


def default_custom_building_template_rows(building_type: str = "home", floor_index: int = 0) -> List[str]:
    width, height = BUILDING_TEMPLATE_WIDTH, BUILDING_TEMPLATE_HEIGHT
    grid = [[" " for _ in range(width)] for _ in range(height)]
    if int(floor_index or 0) > 0:
        x1, y1, x2, y2 = 10, 4, width - 11, height - 4
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                grid[y][x] = "#" if y in {y1, y2} or x in {x1, x2} else "."
        stair_x = (x1 + x2) // 2
        stair_y = y2 - 1
        grid[stair_y][stair_x] = ">"
        for y in range(6, y2):
            if y not in {10, 17}:
                grid[y][stair_x - 8] = "-"
                grid[y][stair_x + 8] = "-"
        for x in range(x1 + 2, x2 - 1):
            if x not in range(stair_x - 1, stair_x + 2) and x % 2 == 1:
                grid[10][x] = "-"
        type_id = building_type if building_type in BUILDING_TEMPLATE_TYPES else "home"
        upstairs_tiles = {
            "home": [(14, 8, "b"), (18, 19, "t"), (47, 8, "P"), (48, 19, "s")],
            "general_store": [(14, 8, "s"), (47, 8, "$"), (18, 19, "d"), (48, 19, "s")],
            "inn": [(14, 8, "b"), (47, 8, "b"), (14, 19, "b"), (47, 19, "b")],
            "clinic": [(14, 8, "b"), (47, 8, "+"), (18, 19, "s"), (48, 19, "d")],
            "library": [(14, 8, "l"), (47, 8, "l"), (18, 19, "P"), (48, 19, "d")],
            "carpenter": [(14, 8, "w"), (47, 8, "a"), (18, 19, "x"), (48, 19, "s")],
            "workshop": [(14, 8, "w"), (47, 8, "a"), (18, 19, "x"), (48, 19, "s")],
            "town_hall": [(14, 8, "d"), (47, 8, "P"), (18, 19, "s"), (48, 19, "d")],
        }
        for x, y, ch in upstairs_tiles.get(type_id, upstairs_tiles["home"]):
            if 0 <= y < height and 0 <= x < width and grid[y][x] == ".":
                grid[y][x] = ch
        return ["".join(row) for row in grid]

    x1, y1, x2, y2 = 8, 4, width - 9, height - 2
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            grid[y][x] = "#" if y in {y1, y2} or x in {x1, x2} else "."
    door_x = (x1 + x2) // 2
    grid[y2][door_x] = "D"
    for y in range(12, y2):
        grid[y][door_x] = "."
    for y in range(5, y2 - 1):
        if y in {9, 16}:
            continue
        grid[y][door_x - 7] = "-"
        grid[y][door_x + 7] = "-"
    for x in range(x1 + 2, x2 - 1):
        if x in range(door_x - 1, door_x + 2):
            continue
        if x % 2 == 0:
            grid[9][x] = "-"
    type_id = building_type if building_type in BUILDING_TEMPLATE_TYPES else "home"
    starter_tiles = {
        "home": [(door_x + 4, 21, "&"), (14, 8, "b"), (13, 17, "f"), (48, 8, "s")],
        "general_store": [(door_x + 4, 21, "&"), (14, 8, "$"), (48, 8, "s"), (48, 20, "$")],
        "inn": [(door_x + 4, 21, "&"), (14, 8, "b"), (48, 8, "b"), (13, 17, "f"), (48, 21, "$")],
        "clinic": [(door_x + 4, 21, "&"), (14, 8, "+"), (48, 8, "b"), (48, 20, "s")],
        "library": [(door_x + 4, 21, "&"), (14, 8, "l"), (48, 8, "l"), (31, 8, "P")],
        "carpenter": [(door_x + 4, 21, "&"), (14, 8, "w"), (48, 8, "a"), (31, 8, "x")],
        "workshop": [(door_x + 4, 21, "&"), (14, 8, "w"), (48, 8, "a"), (31, 8, "x")],
        "town_hall": [(door_x + 4, 21, "&"), (14, 8, "d"), (48, 8, "P"), (48, 20, "s")],
    }
    for x, y, ch in starter_tiles.get(type_id, starter_tiles["home"]):
        if 0 <= y < height and 0 <= x < width and grid[y][x] == ".":
            grid[y][x] = ch
    return ["".join(row) for row in grid]


def _normalized_building_rows(
    raw_rows: object,
    building_type: str,
    *,
    floor_index: int = 0,
    require_door: bool = True,
) -> List[List[str]]:
    default_rows = default_custom_building_template_rows(building_type, floor_index)
    source_rows = raw_rows if isinstance(raw_rows, list) else default_rows
    rows: List[List[str]] = []
    for y in range(BUILDING_TEMPLATE_HEIGHT):
        raw_row = str(source_rows[y]) if y < len(source_rows) else ""
        clean_row = []
        for x in range(BUILDING_TEMPLATE_WIDTH):
            ch = raw_row[x] if x < len(raw_row) else " "
            clean_row.append(ch if ch in BUILDING_TEMPLATE_ALLOWED_TILES else ".")
        rows.append(clean_row)
    if not any(ch == "." or ch == "D" for row in rows for ch in row):
        rows = [list(row) for row in default_rows]
    door_positions = [
        (x, y)
        for y, row in enumerate(rows)
        for x, ch in enumerate(row)
        if ch == "D"
    ]
    if require_door and not door_positions:
        floor_positions = [
            (x, y)
            for y, row in enumerate(rows)
            for x, ch in enumerate(row)
            if ch not in {" ", "#", "-", "_", "D", "<", "U", ">"}
        ]
        if floor_positions:
            min_x = min(x for x, _y in floor_positions)
            max_x = max(x for x, _y in floor_positions)
            max_y = max(y for _x, y in floor_positions)
            door_x = (min_x + max_x) // 2
            rows[max_y][door_x] = "D"
            if max_y > 0 and rows[max_y - 1][door_x] in {"#", "-", " "}:
                rows[max_y - 1][door_x] = "."
        else:
            rows = [list(row) for row in default_rows]
    if not require_door:
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "D":
                    rows[y][x] = "."
    return rows


def _custom_building_floor_positions(rows: List[List[str]]) -> List[Tuple[int, int]]:
    blocking = {" ", "#", "-", "D", "<", "U", ">", "_"}
    return [
        (x, y)
        for y, row in enumerate(rows)
        for x, ch in enumerate(row)
        if ch not in blocking
    ]


def _place_required_custom_building_tiles(
    rows: List[List[str]],
    building_type: str,
    zones: List[Dict[str, object]],
    floor_index: int = 0,
) -> None:
    # Zones are schedule/room metadata. They must not auto-place furniture;
    # otherwise simply designating a room mutates the player's drawn template.
    _ = zones
    if int(floor_index) != 0:
        return
    required = BUILDING_TEMPLATE_REQUIRED_TILES.get(building_type, ("&",))
    floor_positions = _custom_building_floor_positions(rows)
    if not floor_positions:
        return
    preferred = [
        (36, 21), (28, 21), (12, 8), (50, 8), (12, 20), (50, 20),
        (30, 8), (30, 23), (18, 14), (46, 14),
    ]
    for tile in required:
        if any(ch == tile for row in rows for ch in row):
            continue
        placed = False
        for x, y in preferred + floor_positions:
            if 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] == ".":
                rows[y][x] = tile
                placed = True
                break
        if not placed:
            x, y = floor_positions[0]
            rows[y][x] = tile


def _building_template_floor_name(raw_name: object, floor_index: int) -> str:
    fallback = "Ground Floor" if floor_index == 0 else f"Floor {floor_index + 1}"
    return _clean_text(raw_name, 28) or fallback


def _normalized_building_floors(raw: Dict[str, object], building_type: str) -> List[Dict[str, object]]:
    raw_floors = raw.get("floors")
    source_floors: List[Dict[str, object]] = []
    if isinstance(raw_floors, list):
        for _index, raw_floor in enumerate(raw_floors[:BUILDING_TEMPLATE_MAX_FLOORS]):
            if isinstance(raw_floor, dict):
                source_floors.append({
                    "name": raw_floor.get("name"),
                    "rows": raw_floor.get("rows"),
                })
            elif isinstance(raw_floor, list):
                source_floors.append({"name": None, "rows": raw_floor})
    if not source_floors:
        source_floors = [{"name": "Ground Floor", "rows": raw.get("rows")}]

    floors: List[Dict[str, object]] = []
    for floor_index, raw_floor in enumerate(source_floors):
        rows = _normalized_building_rows(
            raw_floor.get("rows"),
            building_type,
            floor_index=floor_index,
            require_door=floor_index == 0,
        )
        floors.append({
            "name": _building_template_floor_name(raw_floor.get("name"), floor_index),
            "rows": rows,
        })
    if not floors:
        floors.append({
            "name": "Ground Floor",
            "rows": _normalized_building_rows(
                None,
                building_type,
                floor_index=0,
                require_door=True,
            ),
        })
    return floors


def _place_custom_building_stair_if_missing(
    rows: List[List[str]],
    symbol: str,
    preferred: Sequence[Tuple[int, int]],
) -> None:
    if any(ch == symbol for row in rows for ch in row):
        return
    floor_positions = _custom_building_floor_positions(rows)
    for x, y in list(preferred) + floor_positions:
        if 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] == ".":
            rows[y][x] = symbol
            return


def _ensure_custom_building_floor_stairs(floors: List[Dict[str, object]]) -> None:
    if len(floors) <= 1:
        return
    up_preferences = [(35, 20), (31, 20), (35, 17), (31, 17), (42, 20), (24, 20)]
    down_preferences = [(31, 22), (35, 22), (31, 19), (35, 19), (24, 22), (42, 22)]
    for floor_index, floor in enumerate(floors):
        rows = floor.get("rows")
        if not isinstance(rows, list):
            continue
        if floor_index < len(floors) - 1:
            _place_custom_building_stair_if_missing(rows, "<", up_preferences)
        if floor_index > 0:
            _place_custom_building_stair_if_missing(rows, ">", down_preferences)


def sanitize_custom_building_template(raw: object) -> Optional[Dict[str, object]]:
    if not isinstance(raw, dict):
        return None
    name = _clean_text(raw.get("name"), 32)
    if not name:
        return None
    building_type = str(raw.get("building_type", "home") or "home")
    if building_type not in BUILDING_TEMPLATE_TYPES:
        building_type = "home"
    floors = _normalized_building_floors(raw, building_type)
    max_zone_floor = max(0, len(floors) - 1)
    zones: List[Dict[str, object]] = []
    raw_zones = raw.get("zones", [])
    for raw_zone in raw_zones if isinstance(raw_zones, list) else []:
        if not isinstance(raw_zone, dict):
            continue
        kind = str(raw_zone.get("kind", ""))
        if kind not in BUILDING_TEMPLATE_ZONE_KINDS:
            continue
        x1 = _clean_int(raw_zone.get("x1"), 0, 0, BUILDING_TEMPLATE_WIDTH - 1)
        y1 = _clean_int(raw_zone.get("y1"), 0, 0, BUILDING_TEMPLATE_HEIGHT - 1)
        x2 = _clean_int(raw_zone.get("x2"), x1, 0, BUILDING_TEMPLATE_WIDTH - 1)
        y2 = _clean_int(raw_zone.get("y2"), y1, 0, BUILDING_TEMPLATE_HEIGHT - 1)
        floor = _clean_int(raw_zone.get("floor"), 0, 0, max_zone_floor)
        zones.append({
            "kind": kind,
            "floor": floor,
            "x1": min(x1, x2),
            "y1": min(y1, y2),
            "x2": max(x1, x2),
            "y2": max(y1, y2),
        })
        if len(zones) >= 16:
            break
    spawns: List[Dict[str, object]] = []
    raw_spawns = raw.get("spawns", [])
    for raw_spawn in raw_spawns if isinstance(raw_spawns, list) else []:
        if not isinstance(raw_spawn, dict):
            continue
        floor = _clean_int(raw_spawn.get("floor"), 0, 0, max_zone_floor)
        spawns.append({
            "floor": floor,
            "x": _clean_int(raw_spawn.get("x"), BUILDING_TEMPLATE_WIDTH // 2, 0, BUILDING_TEMPLATE_WIDTH - 1),
            "y": _clean_int(raw_spawn.get("y"), BUILDING_TEMPLATE_HEIGHT // 2, 0, BUILDING_TEMPLATE_HEIGHT - 1),
        })
        if len(spawns) >= BUILDING_TEMPLATE_MAX_SPAWNS:
            break
    color_map: Dict[Tuple[int, int, int], str] = {}
    raw_colors = raw.get("colors", [])
    for raw_color in raw_colors if isinstance(raw_colors, list) else []:
        if not isinstance(raw_color, dict):
            continue
        color = _clean_building_template_color(raw_color.get("color"))
        floor = _clean_int(raw_color.get("floor"), 0, 0, max_zone_floor)
        x = _clean_int(raw_color.get("x"), 0, 0, BUILDING_TEMPLATE_WIDTH - 1)
        y = _clean_int(raw_color.get("y"), 0, 0, BUILDING_TEMPLATE_HEIGHT - 1)
        key = (floor, x, y)
        if color == "default":
            color_map.pop(key, None)
        else:
            color_map[key] = color
        if len(color_map) >= BUILDING_TEMPLATE_MAX_COLOR_MARKS:
            break
    colors = [
        {"floor": floor, "x": x, "y": y, "color": color}
        for (floor, x, y), color in sorted(color_map.items())
    ]
    for floor_index, floor in enumerate(floors):
        rows = floor.get("rows")
        if isinstance(rows, list):
            _place_required_custom_building_tiles(rows, building_type, zones, floor_index)
    _ensure_custom_building_floor_stairs(floors)
    floor_records = [
        {
            "name": str(floor["name"]),
            "rows": ["".join(row) for row in floor["rows"]],
        }
        for floor in floors
    ]
    rows = list(floor_records[0]["rows"])
    return {
        "name": name,
        "description": _clean_text(raw.get("description"), 220) or "A custom procedural-town building template.",
        "building_type": building_type,
        "max_occupancy": _clean_int(raw.get("max_occupancy"), 4 if building_type == "home" else 0, 0, 24),
        "enabled": bool(raw.get("enabled", True)),
        "rows": rows,
        "floors": floor_records,
        "zones": zones,
        "spawns": spawns,
        "colors": colors,
    }


def custom_building_template_summary(record: Dict[str, object]) -> List[str]:
    template = sanitize_custom_building_template(record)
    if template is None:
        return ["Invalid custom building template."]
    zone_lines = [
        (
            f"- F{int(zone.get('floor', 0)) + 1} {BUILDING_TEMPLATE_ZONE_LABELS.get(str(zone['kind']), str(zone['kind']))}: "
            f"{zone['x1']},{zone['y1']} to {zone['x2']},{zone['y2']}"
        )
        for zone in template["zones"]
    ]
    floor_lines: List[str] = []
    for index, floor in enumerate(template.get("floors", []) or []):
        floor_lines.append(f"F{index + 1}: {floor.get('name', 'Floor')}")
    return [
        str(template["name"]).upper(),
        "",
        str(template["description"]),
        (
            f"Type: {BUILDING_TEMPLATE_TYPE_LABELS.get(str(template['building_type']), template['building_type'])} | "
            f"Max occupancy: {template['max_occupancy']} | "
            f"Status: {'enabled' if template['enabled'] else 'disabled'}"
        ),
        (
            f"Floors: {len(template.get('floors', []) or [template['rows']])} | "
            f"Zones: {len(template['zones'])} | "
            f"Paint: {len(template.get('colors', []) or [])} | "
            f"NPC spawns: {len(template.get('spawns', []) or [])}"
        ),
        *(floor_lines[:BUILDING_TEMPLATE_MAX_FLOORS] or ["F1: Ground Floor"]),
        "",
        *(zone_lines[:8] or ["- No functional zones designated."]),
        "",
        "Ground floor preview:",
        *template["rows"],
        "",
        "Enabled templates join the procedural pool for their building type. Stairs: < up, > down.",
    ]


def custom_building_template_signature(record: Dict[str, object]) -> str:
    template = sanitize_custom_building_template(record)
    if template is None:
        return ""
    total = 2166136261
    signature_text = "|".join([
        str(template["name"]),
        str(template["building_type"]),
        str(template["max_occupancy"]),
        str(template["enabled"]),
        *[
            f"F{index}:{floor.get('name', '')}:{row}"
            for index, floor in enumerate(template.get("floors", []) or [])
            for row in floor.get("rows", [])
        ],
        *[
            f"{zone['kind']}:{zone.get('floor', 0)}:{zone['x1']}:{zone['y1']}:{zone['x2']}:{zone['y2']}"
            for zone in template["zones"]
        ],
        *[
            f"S{spawn.get('floor', 0)}:{spawn.get('x', 0)}:{spawn.get('y', 0)}"
            for spawn in template.get("spawns", []) or []
        ],
        *[
            f"C{color.get('floor', 0)}:{color.get('x', 0)}:{color.get('y', 0)}:{color.get('color', '')}"
            for color in template.get("colors", []) or []
        ],
    ])
    for char in signature_text:
        total ^= ord(char)
        total = (total * 16777619) & 0xFFFFFFFF
    return f"{template['building_type']}:{template['name']}:{total:08x}"


def custom_building_template_records(
    building_type: str = "",
    enabled_only: bool = False,
) -> List[Dict[str, object]]:
    from ascii_farmstead_custom_content import (
        custom_content_file_signature,
        load_custom_content,
    )

    signature = custom_content_file_signature()
    cache_key = (str(building_type), bool(enabled_only), signature)
    cached = _CUSTOM_BUILDING_TEMPLATE_RECORD_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)

    content, _warnings = load_custom_content()
    templates = []
    for raw in content.get("building_templates", []):
        template = sanitize_custom_building_template(raw)
        if template is None:
            continue
        if building_type and str(template["building_type"]) != str(building_type):
            continue
        if enabled_only and not template["enabled"]:
            continue
        templates.append(template)
    # File signatures make old entries unreachable after an editor save. Keep
    # this tiny cache bounded during repeated custom-content edits.
    if len(_CUSTOM_BUILDING_TEMPLATE_RECORD_CACHE) >= 24:
        _CUSTOM_BUILDING_TEMPLATE_RECORD_CACHE.clear()
    _CUSTOM_BUILDING_TEMPLATE_RECORD_CACHE[cache_key] = tuple(templates)
    return list(templates)


def stamp_custom_building_template(template: Dict[str, object], floor: int = 0) -> Optional[List[List[str]]]:
    clean = sanitize_custom_building_template(template)
    if clean is None or not clean["enabled"]:
        return None
    floors = clean.get("floors", []) if isinstance(clean.get("floors"), list) else []
    floor_index = max(0, min(len(floors) - 1, int(floor or 0))) if floors else 0
    floor_record = floors[floor_index] if floors else {"rows": clean["rows"]}
    return [list(str(row)) for row in floor_record.get("rows", clean["rows"])]


def stamp_custom_dungeon_room(
    grid: List[List[str]],
    room_bounds: Tuple[int, int, int, int],
    template: Dict[str, object],
) -> bool:
    room = sanitize_custom_dungeon_room(template)
    if room is None or not room["enabled"]:
        return False
    rx, ry, rw, rh = room_bounds
    rows = list(room["rows"])
    stamp_h = min(len(rows), max(0, rh - 2))
    stamp_w = min(max((len(row) for row in rows), default=0), max(0, rw - 2))
    if stamp_w < 3 or stamp_h < 3:
        return False
    start_x = rx + max(1, (rw - stamp_w) // 2)
    start_y = ry + max(1, (rh - stamp_h) // 2)
    allowed = {".", "#", "'", '"', "~", ";", ":"}
    for local_y in range(stamp_h):
        for local_x in range(stamp_w):
            tile = rows[local_y][local_x] if local_x < len(rows[local_y]) else "."
            if tile not in allowed:
                tile = "."
            gx, gy = start_x + local_x, start_y + local_y
            if 0 < gy < len(grid) - 1 and 0 < gx < len(grid[gy]) - 1:
                grid[gy][gx] = tile
    cx, cy = rx + rw // 2, ry + rh // 2
    for x in range(rx, rx + rw):
        if 0 < cy < len(grid) - 1 and 0 < x < len(grid[cy]) - 1:
            grid[cy][x] = "."
    for y in range(ry, ry + rh):
        if 0 < y < len(grid) - 1 and 0 < cx < len(grid[y]) - 1:
            grid[y][cx] = "."
    return True
