from __future__ import annotations

"""Authoritative ASCII art language and semantic terminal theme.

This module deliberately has no game-state dependency. A future graphical
glyph renderer can consume the same roles without inheriting terminal logic.
"""

from typing import Dict, List, Sequence, Tuple

from ascii_farmstead_support import C


GLYPH_LANGUAGE: Dict[str, Dict[str, object]] = {
    "terrain": {
        "glyphs": (".", ",", ";", "%", "l", "r", "x", "`", '"', "["),
        "purpose": "walkable ground and broad biome identity",
    },
    "water": {
        "glyphs": ("~", "\u2248"),
        "purpose": "water and navigable waterways",
    },
    "routes": {
        "glyphs": (":", "="),
        "purpose": "prepared paths, roads, bridges, and crossings",
    },
    "architecture": {
        "glyphs": ("#", "\u2500", "\u2502", "\u250c", "\u2510", "\u2514", "\u2518", "\u251c", "\u2524", "\u252c", "\u2534", "\u253c", "\u2501", "\u2503", "\u250f", "\u2513", "\u2517", "\u251b", "\u2550", "\u2551", "\u2554", "\u2557", "\u255a", "\u255d", "\u256d", "\u256e", "\u2570", "\u256f", "\u2591", "\u2592", "\u2593"),
        "purpose": "solid walls, cliffs, and impassable structure",
    },
    "doors": {
        "glyphs": ("D", "+", "_", "|"),
        "purpose": "entrances, room doors, and open/closed door states",
    },
    "vertical_travel": {
        "glyphs": ("<", ">"),
        "purpose": "stairs and vertical transitions",
    },
    "actors": {
        "glyphs": ("@", "&"),
        "purpose": "player, people, followers, and traveling groups",
    },
    "landmarks": {
        "glyphs": ("\u25c6", "\u2261", "R", "P", "K", "Q", "E"),
        "purpose": "major landscapes, docks, camps, ruins, overlooks, shelters, and field stations",
    },
    "services": {
        "glyphs": ("$", "P"),
        "purpose": "commerce and staffed public services",
    },
}


WEATHER_GLYPHS: Dict[str, Tuple[str, ...]] = {
    "Rainy": ("'", ".", ","),
    "Stormy": ("|", "/", "!"),
    "Snowy": ("*", ".", "+"),
    "Blizzard": ("*", "*", ".", "+"),
}


LANDMARK_SYMBOLS = frozenset({"A", "h", "j", "k", "q", "v", "g", "i", "E", "R", "P", "K", "Q", "?"})
TOWN_BUILDING_SYMBOLS = frozenset({"G", "X", "L", "U", "M", "I", "R", "Y", "C", "A", "H", "P", "h"})


def town_building_surface(
    tile_map: Sequence[Sequence[str]],
    x: int,
    y: int,
    detailed: bool = True,
    visual_key: int = 0,
    high_contrast: bool = False,
) -> Tuple[str, str] | None:
    """Turn authored-town footprint letters into a render-only building mass."""
    tile = _grid_tile(tile_map, int(x), int(y))
    if tile not in TOWN_BUILDING_SYMBOLS:
        return None

    def connected(dx: int, dy: int) -> bool:
        neighbor = _grid_tile(tile_map, int(x) + dx, int(y) + dy)
        return neighbor == tile or neighbor in {"D", "Q"}

    north, east, south, west = connected(0, -1), connected(1, 0), connected(0, 1), connected(-1, 0)
    if not any((north, east, south, west)):
        return None
    profile_color = {
        "G": C.ROOF_GREEN,
        "X": C.ROOF_FORGE,
        "L": C.ROOF_BLUE,
        "U": C.ROOF_PURPLE,
        "M": C.ROOF_CREAM,
        "I": C.ROOF_RED,
        "R": C.ROOF_CIVIC,
        "Y": C.ROOF_COPPER,
        "C": C.ROOF_CEDAR,
        "A": C.ROOF_GREEN,
        "H": C.ROOF_CLINIC,
        "P": C.SERVICE,
        "h": (C.ROOF_RED, C.ROOF_BLUE, C.ROOF_CEDAR, C.ROOF_GREEN, C.ROOF_CREAM, C.ROOF_PURPLE)[(int(x) // 16) % 6],
    }.get(tile, C.ROOF_CIVIC)
    if not detailed:
        return tile, C.PLAYER if high_contrast else profile_color

    if tile in {"R", "U"}:
        horizontal, vertical, top_left, top_right, bottom_left, bottom_right = "\u2550", "\u2551", "\u2554", "\u2557", "\u255a", "\u255d"
    elif tile in {"X", "C"}:
        horizontal, vertical, top_left, top_right, bottom_left, bottom_right = "\u2501", "\u2503", "\u250f", "\u2513", "\u2517", "\u251b"
    else:
        horizontal, vertical, top_left, top_right, bottom_left, bottom_right = "\u2500", "\u2502", "\u250c", "\u2510", "\u2514", "\u2518"
    if not north and not west:
        glyph = top_left
    elif not north and not east:
        glyph = top_right
    elif not south and not west:
        glyph = bottom_left
    elif not south and not east:
        glyph = bottom_right
    elif not north or not south:
        glyph = horizontal
    elif not west or not east:
        glyph = vertical
    else:
        two_south = _grid_tile(tile_map, int(x), int(y) + 2)
        lower_facade = two_south not in {tile, "D", "Q"}
        if lower_facade and abs(int(visual_key)) % 4 == 0:
            return "o", C.LIT
        fill_pair = {
            "G": ("\u2591", "\u2592"), "X": ("\u2592", "\u2593"),
            "L": ("\u00b7", "\u2591"), "U": ("\u25c6", "\u2591"),
            "M": ("\u2591", "\u2591"), "I": ("^", "\u2591"),
            "R": ("\u2592", "\u2591"), "Y": ("/", "\u2591"),
            "C": ("/", "\u2592"), "A": (";", "\u2591"),
            "H": ("\u00b7", "\u2591"), "P": ("=", "\u2591"),
            "h": ("^", "\u2591"),
        }.get(tile, ("\u2591", "\u2592"))
        glyph = fill_pair[0] if lower_facade else fill_pair[(int(x) + int(y)) % 2]
    edge_glyphs = {horizontal, vertical, top_left, top_right, bottom_left, bottom_right}
    color = C.PLAYER if high_contrast else (profile_color + C.BOLD if glyph in edge_glyphs else profile_color)
    return glyph, color


def farmhouse_surface(
    tile_map: Sequence[Sequence[str]],
    x: int,
    y: int,
    detailed: bool = True,
    visual_key: int = 0,
    high_contrast: bool = False,
    deluxe: bool = False,
) -> Tuple[str, str] | None:
    """Render the fixed farmhouse footprint as a warm, readable home."""
    surface = town_building_surface(tile_map, x, y, detailed, visual_key, high_contrast)
    if not surface:
        return None
    glyph, prior_color = surface
    if not detailed:
        return glyph, C.PLAYER if high_contrast else (C.ROOF_BLUE if deluxe else C.ROOF_RED)
    if glyph == "\u00b7":
        glyph = "^"
    roof_color = C.PLAYER if high_contrast else (C.ROOF_BLUE if deluxe else C.ROOF_RED)
    if glyph == "o":
        return glyph, C.LIT
    return glyph, roof_color + (C.BOLD if C.BOLD in prior_color else "")


def farm_structure_surface(
    name: str,
    width: int,
    height: int,
    offset_x: int,
    offset_y: int,
    detailed: bool = True,
    visual_phase: int = 0,
    visual_key: int = 0,
    high_contrast: bool = False,
) -> Tuple[str, str] | None:
    """Render a placed farm building as one coherent multi-cell object."""
    name = str(name or "")
    symbols = {
        "Storage Shed": "S", "Well": "W", "Chicken Coop": "C",
        "Animal Pen": "A", "Tool Shed": "T", "Fish Pond": "P",
    }
    if name not in symbols or not (0 <= int(offset_x) < int(width) and 0 <= int(offset_y) < int(height)):
        return None
    if not detailed:
        return symbols[name], C.PLAYER if high_contrast else C.INFRA
    patterns = {
        "Storage Shed": ["\u250c\u2500\u2500\u2500\u2510", "\u2502^o^\u2502", "\u2502\u2591S\u2591\u2502", "\u2514\u2500\u2500\u2500\u2518"],
        "Well": ["\u256d\u256e", "\u2570\u256f"],
        "Chicken Coop": ["\u250c\u2500\u2500\u2510", "\u2502cC\u2502", "\u2514\u2500\u2500\u2518"],
        "Animal Pen": ["\u250c\u2500\u2500\u2500\u2510", "\u2502;a;\u2502", "\u2502;A;\u2502", "\u2514\u2500\u2500\u2500\u2518"],
        "Tool Shed": ["\u250f\u2501\u2501\u2513", "\u2503Tt\u2503", "\u2517\u2501\u2501\u251b"],
        "Fish Pond": ["\u256d~~\u256e", "\u2502\u2248P\u2502", "\u2570~~\u256f"],
    }
    pattern = patterns[name]
    if len(pattern) != int(height) or any(len(row) != int(width) for row in pattern):
        return None
    glyph = pattern[int(offset_y)][int(offset_x)]
    colors = {
        "Storage Shed": C.ROOF_CEDAR,
        "Well": C.STONE,
        "Chicken Coop": C.ROOF_RED,
        "Animal Pen": C.WOOD,
        "Tool Shed": C.ROOF_FORGE,
        "Fish Pond": C.WATER,
    }
    color = C.PLAYER if high_contrast else colors[name]
    if name == "Storage Shed" and glyph == "o":
        color = C.LIT if (int(visual_phase) + int(visual_key)) % 2 else C.FLOOR_WARM
    if glyph in {"S", "C", "A", "T", "P", "W"}:
        color = C.SERVICE if high_contrast else color + C.BOLD
    return glyph, color


def connected_network_glyph(
    north: bool,
    east: bool,
    south: bool,
    west: bool,
    detailed: bool = True,
    isolated: str = "\u00b7",
) -> str:
    """Shape a player-built one-cell path, fence, or pipe network."""
    if not detailed:
        return str(isolated or ".")[:1]
    mask = (1 if north else 0) | (2 if east else 0) | (4 if south else 0) | (8 if west else 0)
    return {
        1: "\u2502", 2: "\u2500", 3: "\u2514", 4: "\u2502", 5: "\u2502",
        6: "\u250c", 7: "\u251c", 8: "\u2500", 9: "\u2518", 10: "\u2500",
        11: "\u2534", 12: "\u2510", 13: "\u2524", 14: "\u252c", 15: "\u253c",
    }.get(mask, str(isolated or "\u00b7")[:1])


def actor_style(
    kind: str,
    symbol: str = "@",
    role: str = "",
    base_color: str = "",
    elite: bool = False,
    bounty: bool = False,
    detailed: bool = True,
    high_contrast: bool = False,
) -> Tuple[str, str]:
    """Return a one-cell actor silhouette and semantic foreground role."""
    kind = str(kind or "npc").lower()
    role_text = str(role or "").lower()
    glyph = str(symbol or "@")[:1]
    color = base_color or C.ACTOR_NPC
    if kind == "follower":
        if role_text == "companion" and detailed:
            glyph = "&"
        color = C.ACTOR_FAMILY if role_text in {"spouse", "child"} else C.ACTOR_FOLLOWER
    elif kind in {"visitor", "traveler"}:
        if "merchant" in role_text:
            glyph, color = "&", C.SERVICE + C.BOLD
        elif any(value in role_text for value in ("ranger", "warden", "guide", "woodward")):
            color = C.ACTOR_RANGER
        elif "prospector" in role_text:
            color = C.HIGHLAND + C.BOLD
        elif any(value in role_text for value in ("herbalist", "naturalist", "mycologist", "research")):
            color = C.FUNGAL + C.BOLD
        else:
            color = C.ACTOR_TRAVELER
    elif kind == "npc":
        color = (base_color or C.ACTOR_NPC) + C.BOLD
    elif kind in {"wildlife", "farm_animal"}:
        color = C.ACTOR_WILDLIFE if high_contrast else (base_color or C.ACTOR_WILDLIFE)
    elif kind == "hostile":
        if detailed and (elite or bounty):
            glyph = glyph.upper()
        color = C.ACTOR_BOUNTY if bounty else C.HOSTILE
    if high_contrast and kind in {"npc", "visitor", "traveler", "follower"}:
        color = C.ACTOR_FOLLOWER if kind == "follower" else C.PLAYER
    return glyph, color


def wilderness_landmark_style(
    tile: str,
    landscape_kind: str = "",
    detailed: bool = True,
    high_contrast: bool = False,
) -> Tuple[str, str] | None:
    """Present physical wilderness anchors by player-facing meaning."""
    tile = str(tile or " ")[:1]
    if tile not in LANDMARK_SYMBOLS:
        return None
    display = {
        "A": "D", "h": "D", "j": "\u25c6" if detailed else "j",
        "k": "\u2261" if detailed else "k", "q": "H" if detailed else "q",
        "v": "V" if detailed else "v", "g": "G" if detailed else "g",
        "i": "I" if detailed else "i",
    }.get(tile, tile)
    landscape_kind = str(landscape_kind or "")
    if tile == "j":
        if landscape_kind in {"large_lake", "floodplain", "waterfall", "hot_springs", "archipelago"}:
            color = C.LANDMARK_NATURAL
        elif landscape_kind in {"pine_forest", "birch_grove", "flower_field", "moorland"}:
            color = C.FOREST + C.BOLD
        elif landscape_kind in {"snowy_highlands", "tundra_plain"}:
            color = C.TUNDRA + C.BOLD
        elif landscape_kind == "desert_dunes":
            color = C.DESERT + C.BOLD
        else:
            color = C.HIGHLAND + C.BOLD
    else:
        color = {
            "A": C.LANDMARK_SHELTER, "h": C.LANDMARK_SHELTER,
            "k": C.COAST + C.BOLD, "q": C.SERVICE + C.BOLD,
            "v": C.FOREST + C.BOLD, "g": C.LANDMARK_RESEARCH,
            "i": C.LANDMARK_ACTIVE, "E": C.LANDMARK_RESEARCH,
            "R": C.ACTOR_RANGER, "P": C.STONE + C.BOLD,
            "K": C.COAST + C.BOLD, "Q": C.LANDMARK_SHELTER,
            "?": C.LANDMARK_ACTIVE,
        }.get(tile, C.LANDMARK_ACTIVE)
    if high_contrast:
        color = C.LANDMARK_ACTIVE
    return display, color


def weather_overlay_allowed(tile: str) -> bool:
    """Keep precipitation off architecture and useful world anchors."""
    tile = str(tile or " ")[:1]
    protected = LANDMARK_SYMBOLS | TOWN_BUILDING_SYMBOLS | frozenset({"#", "$", "B", "D", "+", "_", "|", "<", ">", "S", "V", "!"})
    return tile not in protected


def weather_overlay_style(weather: str, symbol_index: int, depth_roll: float) -> Tuple[str, str]:
    """Give precipitation a readable near/far layer without background fill."""
    symbols = weather_glyphs(weather)
    glyph = symbols[int(symbol_index) % len(symbols)]
    base = C.STORM if weather == "Stormy" else (C.SNOW if weather in {"Snowy", "Blizzard"} else C.RAIN)
    depth = max(0.0, min(1.0, float(depth_roll)))
    return (glyph, base) if depth < 0.34 else (glyph, C.DIM + base)


def visual_style_issues() -> List[str]:
    """Return structural problems in the canonical glyph guide."""
    issues: List[str] = []
    for group, record in GLYPH_LANGUAGE.items():
        glyphs = tuple(record.get("glyphs", ()))
        if not glyphs:
            issues.append(f"{group} has no glyphs")
        if any(len(str(glyph)) != 1 for glyph in glyphs):
            issues.append(f"{group} contains a non-cell glyph")
        if not str(record.get("purpose", "")).strip():
            issues.append(f"{group} has no purpose")
    return issues


def weather_glyphs(weather: str) -> Tuple[str, ...]:
    return WEATHER_GLYPHS.get(str(weather), ("",))


def _grid_tile(tile_map: Sequence[Sequence[str]], x: int, y: int) -> str:
    if y < 0 or y >= len(tile_map):
        return ""
    row = tile_map[y]
    if x < 0 or x >= len(row):
        return ""
    return str(row[x] or " ")[:1]


def architectural_wall_glyph(
    tile_map: Sequence[Sequence[str]],
    x: int,
    y: int,
    detailed: bool = True,
) -> str:
    """Shape a stored # wall for display without changing map semantics."""
    if _grid_tile(tile_map, int(x), int(y)) != "#" or not detailed:
        return _grid_tile(tile_map, int(x), int(y)) or " "
    mask = 0
    for bit, dx, dy in ((1, 0, -1), (2, 1, 0), (4, 0, 1), (8, -1, 0)):
        if _grid_tile(tile_map, int(x) + dx, int(y) + dy) == "#":
            mask |= bit
    return {
        1: "\u2502", 2: "\u2500", 3: "\u2514", 4: "\u2502", 5: "\u2502",
        6: "\u250c", 7: "\u251c", 8: "\u2500", 9: "\u2518", 10: "\u2500",
        11: "\u2534", 12: "\u2510", 13: "\u2524", 14: "\u252c", 15: "\u253c",
    }.get(mask, "#")


def exterior_window_at(
    tile_map: Sequence[Sequence[str]],
    x: int,
    y: int,
    visual_key: int = 0,
    detailed: bool = True,
) -> bool:
    """Return whether a straight exterior wall segment displays a window."""
    if not detailed or _grid_tile(tile_map, int(x), int(y)) != "#":
        return False
    north = _grid_tile(tile_map, int(x), int(y) - 1) == "#"
    east = _grid_tile(tile_map, int(x) + 1, int(y)) == "#"
    south = _grid_tile(tile_map, int(x), int(y) + 1) == "#"
    west = _grid_tile(tile_map, int(x) - 1, int(y)) == "#"
    horizontal = east and west and not north and not south
    vertical = north and south and not east and not west
    bounded = (
        horizontal
        and _grid_tile(tile_map, int(x), int(y) - 1) != ""
        and _grid_tile(tile_map, int(x), int(y) + 1) != ""
    ) or (
        vertical
        and _grid_tile(tile_map, int(x) - 1, int(y)) != ""
        and _grid_tile(tile_map, int(x) + 1, int(y)) != ""
    )
    exposed = any(
        _grid_tile(tile_map, int(x) + dx, int(y) + dy) not in {"#", ""}
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
    )
    return bool(bounded and exposed and abs(int(visual_key)) % 11 == 0)


def wilderness_display_glyph(
    tile: str,
    visual_phase: int = 0,
    visual_key: int = 0,
    ambient: bool = True,
    detailed: bool = True,
) -> str:
    """Add sparse, deterministic texture while preserving the stored tile."""
    tile = str(tile or " ")[:1]
    if not detailed:
        return tile
    key = abs(int(visual_key))
    phase = int(visual_phase)
    if tile == "~" and ambient and (key + phase) % 7 == 0:
        return "\u2248"
    if tile == "." and key % 17 == 0:
        return "\u00b7"
    if tile == ";" and key % 13 == 0:
        return "'"
    if tile == "r" and key % 19 == 0:
        return ","
    return tile


def cartography_symbol_style(
    symbol: str,
    kind: str = "",
    detailed: bool = True,
    high_contrast: bool = False,
) -> Tuple[str, str]:
    """Return a display-only glyph and semantic color for the overworld map.

    ``kind`` disambiguates legacy symbols that intentionally overlap (most
    notably ``d`` for surveys and river deltas). Stored world data is never
    changed by this presentation helper.
    """
    symbol = str(symbol or " ")[:1]
    kind = str(kind or "").strip().lower()
    inferred_kinds = {
        "_": "unknown", "T": "home", "t": "town", "*": "visited",
        ":": "road", "s": "source", "b": "basin", "~": "water",
        "V": "cave", "X": "dungeon", "?": "objective", "!": "danger",
        "D": "claim", ";": "meadow", "%": "woods", "l": "fungal",
        "r": "wetland", "x": "ridge", "`": "desert", '"': "tundra",
        "[": "coast", "h": "hinterland",
    }
    kind = kind or inferred_kinds.get(symbol, "terrain")

    detailed_glyphs = {
        "unknown": "░", "home": "⌂", "town": "▣", "visited": "•",
        "road": "─", "source": "↑", "delta": "≋", "basin": "○",
        "water": "≈", "port": "≡", "cave": "V", "dungeon": "X",
        "objective": "?", "danger": "!", "reclaimed": "!",
        "claim": "◆", "survey": "◇", "meadow": "·", "woods": "♣",
        "fungal": "*", "wetland": "≈", "ridge": "▲", "desert": "`",
        "tundra": "*", "coast": "≈", "hinterland": "h",
    }
    simple_glyphs = {
        "port": "P", "delta": "d", "survey": "d",
    }
    glyph = detailed_glyphs.get(kind, symbol) if detailed else simple_glyphs.get(kind, symbol)

    colors = {
        "unknown": C.UI_MUTED + C.DIM,
        "home": C.LANDMARK_SHELTER,
        "town": C.SERVICE,
        "visited": C.CROP_READY,
        "road": C.ROAD,
        "source": C.WATER,
        "delta": C.WATER,
        "basin": C.WATER_DEEP,
        "water": C.WATER,
        "port": C.SERVICE,
        "cave": C.UNDERGROUND_EXIT,
        "dungeon": C.STONE,
        "objective": C.LANDMARK_ACTIVE,
        "danger": C.HOSTILE,
        "reclaimed": C.CROP_READY,
        "claim": C.BIN,
        "survey": C.UI_MUTED,
        "meadow": C.SPRING_GRASS,
        "woods": C.FOREST,
        "fungal": C.FUNGAL,
        "wetland": C.WETLAND,
        "ridge": C.HIGHLAND,
        "desert": C.DESERT,
        "tundra": C.TUNDRA,
        "coast": C.COAST,
        "hinterland": C.CROP_READY,
        "terrain": C.UI_MUTED,
    }
    color = colors.get(kind, C.UI_MUTED)
    if high_contrast:
        if kind in {"unknown", "road", "survey"}:
            color = C.UI_MUTED
        elif kind in {"source", "delta", "basin", "water", "coast", "wetland"}:
            color = C.WATER + C.BOLD
        elif kind in {"danger"}:
            color = C.HOSTILE
        elif kind in {"home", "town", "port", "objective", "claim"}:
            color = C.SERVICE + C.BOLD
        else:
            color = C.PLAYER
    return glyph, color


def interior_light_color(
    tile_map: Sequence[Sequence[str]],
    x: int,
    y: int,
    tile: str,
    base_color: str,
    hour: int,
    ambient: bool = True,
    high_contrast: bool = False,
    radius: int = 4,
) -> str:
    """Warm nighttime floor cells near fixtures without altering visibility."""
    if not ambient or high_contrast or str(tile) not in {".", ":", ","}:
        return base_color
    hour = int(hour) % 24
    if 7 <= hour < 19:
        return base_color
    return C.LIT if (int(x), int(y)) in interior_light_positions(tile_map, radius) else base_color


def interior_light_positions(
    tile_map: Sequence[Sequence[str]],
    radius: int = 4,
) -> set[Tuple[int, int]]:
    """Return floor cells reached by interior lamps; suitable for frame caching."""
    radius = max(1, int(radius))
    lit: set[Tuple[int, int]] = set()
    sources = [
        (x, y)
        for y, row in enumerate(tile_map)
        for x, tile in enumerate(row)
        if str(tile or " ")[:1] in {"f", "!"}
    ]
    for source_x, source_y in sources:
        for dy in range(-radius, radius + 1):
            span = radius - abs(dy)
            yy = source_y + dy
            if yy < 0 or yy >= len(tile_map):
                continue
            for xx in range(max(0, source_x - span), min(len(tile_map[yy]), source_x + span + 1)):
                if _grid_tile(tile_map, xx, yy) in {".", ":", ","}:
                    lit.add((xx, yy))
    return lit


def underground_tile_style(
    tile_map: Sequence[Sequence[str]],
    x: int,
    y: int,
    context: str = "mine",
    detailed: bool = True,
    visual_phase: int = 0,
    visual_key: int = 0,
    ambient: bool = True,
    high_contrast: bool = False,
) -> Tuple[str, str]:
    """Render mines, natural caves, and built ruins as distinct environments."""
    x, y = int(x), int(y)
    tile = _grid_tile(tile_map, x, y) or " "
    context = str(context or "mine").lower()
    key = abs(int(visual_key))

    if context == "dungeon":
        colors = {
            ".": C.DUNGEON_FLOOR,
            "#": C.DUNGEON_WALL,
            " ": C.CAVE_WALL,
            "<": C.UNDERGROUND_EXIT,
            "U": C.UNDERGROUND_EXIT,
            ">": C.SERVICE + C.BOLD,
            "+": C.DOOR + C.BOLD,
            "$": C.ORE_GOLD,
            "P": C.UNDERGROUND_RELIC,
            "!": C.HOSTILE,
            "S": C.UNDERGROUND_RELIC,
            "?": C.UNDERGROUND_GLOW,
            "'": C.FOREST,
            '"': C.WOOD,
            ":": C.FLOOR_SHADOW,
            "~": C.WATER_DEEP,
            ";": C.CRYSTAL,
        }
    elif context == "cave":
        colors = {
            ".": C.CAVE_FLOOR,
            "#": C.CAVE_WALL,
            " ": C.CAVE_WALL,
            "<": C.UNDERGROUND_EXIT,
            "U": C.UNDERGROUND_EXIT,
            "m": C.FUNGAL,
            "h": C.CROP_MID,
            "b": C.WOOD,
            "o": C.STONE,
            "q": C.ORE_COAL,
            "d": C.SOIL_WET,
            "c": C.ORE_COPPER,
            "i": C.ORE_IRON,
            "g": C.ORE_GOLD,
            "A": C.GEM,
            "C": C.CRYSTAL,
            "~": C.WATER_DEEP,
        }
    else:
        colors = {
            ".": C.MINE_FLOOR,
            "#": C.CAVE_WALL,
            " ": C.CAVE_WALL,
            "N": C.UNDERGROUND_EXIT,
            "<": C.UNDERGROUND_EXIT,
            "U": C.UNDERGROUND_EXIT,
            ">": C.SERVICE + C.BOLD,
            "A": C.INFRA,
            "P": C.UNDERGROUND_RELIC,
            "S": C.UNDERGROUND_RELIC,
            "?": C.UNDERGROUND_GLOW,
            "r": C.STONE,
            "O": C.ORE_COPPER,
            "I": C.ORE_IRON,
            "G": C.ORE_GOLD,
            "M": C.GEM,
            "q": C.ORE_COAL,
            "c": C.CRYSTAL,
            "g": C.GEM,
            "B": C.WOOD,
            "m": C.FUNGAL,
            "~": C.WATER_DEEP,
        }

    glyph = tile
    if detailed:
        if tile == "#":
            if context == "dungeon":
                glyph = architectural_wall_glyph(tile_map, x, y, True)
            else:
                # Natural rock remains irregular instead of reading as masonry.
                exposed = any(
                    _grid_tile(tile_map, x + dx, y + dy) not in {"#", " ", ""}
                    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
                )
                glyph = "▓" if exposed else ("▒" if key % 13 == 0 else "#")
        elif tile == "." and key % (19 if context == "dungeon" else 17) == 0:
            glyph = "·"
        elif tile == "~" and ambient and (key + int(visual_phase)) % 7 == 0:
            glyph = "≈"
        elif tile == "P":
            glyph = "◆"
        elif context == "cave" and tile in {"A", "C"}:
            glyph = "♦"

    color = colors.get(tile, C.STONE)

    # Crystals, shrines, and final chambers cast a small, stable hint of light.
    if ambient and not high_contrast and tile in {".", ":"}:
        light_symbols = {"S", "P"}
        if context in {"mine", "cave"}:
            light_symbols |= {"c", "g", "A", "C"}
        for dy in range(-2, 3):
            for dx in range(-2 + abs(dy), 3 - abs(dy)):
                if _grid_tile(tile_map, x + dx, y + dy) in light_symbols:
                    color = C.UNDERGROUND_GLOW
                    break
            if color == C.UNDERGROUND_GLOW:
                break

    if high_contrast:
        if tile in {".", ":", "'", '"'}:
            color = C.FLOOR
        elif tile in {"#", " "}:
            color = C.WALL + C.BOLD
        elif tile in {"<", "U", "N", ">", "+", "$", "P", "S", "?"}:
            color = C.SERVICE + C.BOLD
        elif tile == "!":
            color = C.HOSTILE
    return glyph, color


def _seasonal_ground_color(season: str) -> str:
    return {
        "Spring": C.SPRING_GRASS,
        "Summer": C.SUMMER_GRASS,
        "Fall": C.FALL_GRASS,
        "Winter": C.WINTER_GRASS,
    }.get(str(season), C.GRASS)


def wilderness_tile_color(
    tile: str,
    season: str,
    visual_phase: int = 0,
    visual_key: int = 0,
    ambient: bool = True,
    high_contrast: bool = False,
    weather: str = "",
) -> str:
    """Color a wilderness cell by meaning, not by whichever system made it."""
    tile = str(tile or " ")[:1]
    season = str(season or "Spring")
    weather = str(weather or "")
    meadow_color = {
        "Spring": C.SPRING_GRASS,
        "Summer": C.SUMMER_GRASS,
        "Fall": C.FALL_GRASS,
        "Winter": C.TUNDRA,
    }.get(season, C.GRASS)
    woods_color = {
        "Spring": C.FOREST,
        "Summer": C.FOREST,
        "Fall": C.FALL_GRASS,
        "Winter": C.TUNDRA,
    }.get(season, C.FOREST)
    wetland_color = C.TUNDRA if season == "Winter" else (C.WATER_DEEP if season == "Fall" else C.WETLAND)
    fungal_color = C.UI_MUTED if season == "Winter" else C.FUNGAL
    colors = {
        ".": _seasonal_ground_color(season),
        ",": meadow_color,
        ";": meadow_color,
        "%": woods_color,
        "l": fungal_color,
        "r": wetland_color,
        "x": C.TUNDRA if season == "Winter" else C.HIGHLAND,
        "`": C.DESERT,
        '"': C.TUNDRA,
        "[": C.UI_MUTED if season == "Winter" else C.COAST,
        "~": C.WATER,
        "=": C.ROAD,
        ":": C.PATH,
        "#": C.WALL,
        "T": woods_color,
        "o": C.STONE,
        "*": C.WOOD,
        "^": meadow_color,
        "V": C.STONE,
        "X": C.STONE,
        "D": C.DOOR,
        "+": C.DOOR,
        "_": C.DOOR,
        "|": C.DOOR,
        "R": C.WOOD,
        "H": C.LAMP,
        "B": C.BIN,
        "S": C.SERVICE,
        "?": C.SERVICE,
        "!": C.HOSTILE,
        "W": C.WATER if season != "Winter" else C.TUNDRA,
        "p": wetland_color,
        "M": C.STONE,
        "J": C.STONE,
        "K": C.CROP_READY,
        "Q": C.WOOD,
        " ": C.WALL,
    }
    color = colors.get(tile, C.CROP_READY)
    snow_cover = weather in {"Snowy", "Blizzard"}
    if snow_cover and tile in {".", ",", ";", "%", "l", "r", "x", "`", "T", "^", "p"}:
        color = C.TUNDRA
    elif weather in {"Rainy", "Stormy"} and tile in {".", ",", ";", "r", "p"}:
        color = C.WETLAND
    if ambient and tile == "~" and (int(visual_phase) + int(visual_key)) % 3 == 0:
        color = C.WATER_DEEP
    if ambient and tile in {"H", "!"} and (int(visual_phase) + int(visual_key)) % 2:
        color = C.LIT if tile == "H" else color
    if high_contrast:
        if tile in {".", ",", ";", "%", "T", "^"}:
            return C.TUNDRA if snow_cover or season == "Winter" else C.SPRING_GRASS
        if tile in {"~", "r", "[", "W", "p"}:
            return C.WATER
        if tile in {":", "=", "D", "+", "_", "|"}:
            return C.SERVICE
        if tile in {"#", "x", "V", "X", "M", "J", " "}:
            return C.PLAYER
    return color


def interior_tile_color(
    tile: str,
    context: str = "public",
    visual_phase: int = 0,
    visual_key: int = 0,
    ambient: bool = True,
    high_contrast: bool = False,
) -> str:
    """Shared readable palette for homes, shops, outposts, and structures."""
    tile = str(tile or " ")[:1]
    colors = {
        ".": C.FLOOR_WARM if context == "home" else C.FLOOR,
        ":": C.FLOOR_SHADOW,
        ",": C.RUG,
        "#": C.WALL,
        " ": C.WALL,
        "D": C.DOOR,
        "+": C.DOOR,
        "_": C.DOOR,
        "|": C.DOOR,
        "-": C.STONE,
        "$": C.SERVICE,
        "&": C.SERVICE,
        "P": C.SERVICE,
        "g": C.SERVICE,
        "n": C.SERVICE,
        "f": C.LAMP,
        "!": C.LAMP,
        "b": C.FLOOR_WARM,
        "B": C.FLOOR_WARM,
        "l": C.FLOOR,
        "L": C.FLOOR,
        "t": C.WOOD,
        "c": C.WOOD,
        "s": C.STONE,
        "w": C.WOOD,
        "a": C.WOOD,
        "d": C.WOOD,
        "T": C.WOOD,
        "h": C.WOOD,
        "r": C.RUG,
        "p": C.GRASS,
        "v": C.CROP_MID,
        "x": C.STONE,
        "o": C.STONE,
        "q": C.UI_MUTED,
        "m": C.WATER,
        "C": C.WATER,
        "F": C.WATER,
        "A": C.PLACEMENT,
        "<": C.LAMP,
        ">": C.LAMP,
        "U": C.LAMP,
    }
    color = colors.get(tile, C.WOOD)
    if context == "outpost" and tile == "n":
        color = C.ACTOR_RANGER
    if ambient and tile in {"f", "!"} and (int(visual_phase) + int(visual_key)) % 2:
        color = C.LIT
    if high_contrast:
        if tile in {".", ":", ","}:
            return C.PLAYER
        if tile in {"#", " "}:
            return C.WALL + C.BOLD
        if tile in {"D", "+", "_", "|", "$", "&", "P"}:
            return C.SERVICE
    return color


def outdoor_time_color(
    base_color: str,
    hour: int,
    lit: bool = False,
    ambient: bool = True,
) -> str:
    """Apply restrained time-of-day tint while retaining semantic hue."""
    if not ambient or lit:
        return C.LAMP if lit else base_color
    hour = int(hour) % 24
    if hour >= 21 or hour < 5:
        return C.DIM + base_color
    if hour >= 19 or hour < 7:
        return C.DIM + base_color
    return base_color
