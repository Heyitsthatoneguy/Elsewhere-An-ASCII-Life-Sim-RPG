from __future__ import annotations

"""Shared multi-cell artwork and functional metadata for placed furniture."""

from typing import Dict, Iterable, Optional, Tuple

from ascii_farmstead_furniture_catalog import (
    FURNITURE_CATALOG_ART,
    FURNITURE_CATALOG_COMPONENT_ZONES,
    FURNITURE_CATALOG_DATA,
    FURNITURE_CATALOG_WALKABLE_ZONES,
)


FurnitureCell = Tuple[str, str]


# The catalog deliberately stores compact ASCII silhouettes because those
# characters are also used by placement, rotation, collision, and old saves.
# Presentation is upgraded separately so detailed mode can draw the same
# footprint as single-cell-width Unicode art without changing map data.
_FURNITURE_UNICODE_GLYPHS: Dict[str, str] = {
    "+": "┼",
    "-": "─",
    "=": "═",
    "_": "━",
    "|": "│",
    "/": "╱",
    "\\": "╲",
    "[": "╭",
    "]": "╮",
    "(": "╰",
    ")": "╯",
    "{": "‹",
    "}": "›",
    ".": "·",
    ":": "▪",
    "#": "░",
    "~": "≈",
    "*": "✦",
    "o": "○",
    "O": "◉",
    "h": "╥",
    "H": "╫",
    "r": "◒",
    "R": "◒",
    "a": "▣",
    "c": "╥",
    "x": "╳",
    "T": "┬",
    "L": "▥",
    "I": "▌",
    "W": "▤",
    "P": "▦",
    "F": "♨",
    "A": "◇",
    "f": "♣",
    "i": "◉",
    "M": "≋",
    "s": "≈",
    "n": "▣",
    "Y": "Ψ",
    "v": "◊",
}


# Catalog art is stored as compact ASCII for saves, collision, and editing.
# These render-only silhouettes deliberately use much less ink than the old
# character-for-character substitution.  Each form has a recognizable outline
# and only the functional detail needed to distinguish it at a glance.
_FURNITURE_FORM_DISPLAY_ROWS: Dict[str, Tuple[str, ...]] = {
    # Seating.
    "Dining Chair": ("╥",),
    "Rocking Chair": ("◒",),
    "Reading Chair": ("╭░╮",),
    "Entry Bench": ("╰──╯",),
    "Kitchen Stool": ("○",),
    "Loveseat": ("╭░░╮",),
    "Daybed": ("╭○░╮", "╰──╯"),
    "Chaise Lounge": ("╭░░░╮",),
    "Window Seat": ("│░░░│",),
    "Conversation Sofa": ("╭░░╮·╭░░╮",),
    "Captain Chair": ("╭╫╮",),
    "Folding Chair": ("╳",),
    "Garden Bench": ("│────│",),
    "Piano Bench": ("╰──╯",),
    "Corner Sofa": ("╭░░╮", "╰░░╯"),
    "Recliner": ("╭◒─╮",),
    "Ottoman": ("╰░╯",),
    "Gossip Bench": ("╥─╥",),
    "Porch Swing": ("┌────┐", "│░░░░│"),
    "Theater Seat": ("╭░╮",),
    # Tables and work surfaces.
    "Side Table": ("╾═╼",),
    "Coffee Table": ("╾───╼",),
    "Dining Table": ("╾═════╼",),
    "Writing Desk": ("╾▤▤▤╼",),
    "Study Table": ("╾··╼",),
    "Drafting Table": ("╱▤▤▤╲",),
    "Worktable": ("╾◇═◇╼",),
    "Tea Cart": ("○╾═╼○",),
    "Console Table": ("╾────╼",),
    "Breakfast Table": ("╥╾═╼╥",),
    "Sewing Table": ("╾◌▤▤╼",),
    "Map Table": ("╾≋≋≋≋╼",),
    "Secretary Desk": ("┌▥▥┐", "╰▤▤╯"),
    "Tool Cart": ("○╾◇╼○",),
    "Pedestal Table": ("╭═╮", " ╥ "),
    "Banquet Table": ("╥╾═══════╼╥",),
    # Storage and display.
    "Bookcase": ("┌▥▤▥┐", "└▥▤▥┘"),
    "Tall Cabinet": ("┌┬┬┐", "└┴┴┘"),
    "Wardrobe": ("┌╫╫┐", "└╫╫┘"),
    "Dresser": ("┌──┐", "└••┘"),
    "Display Shelf": ("│◇·◇│", "│·◇·│"),
    "Storage Trunk": ("╰═══╯",),
    "Linen Press": ("┌▤▤┐", "└▤▤┘"),
    "Corner Hutch": ("╱▥▥", "│▤▤"),
    "Apothecary Cabinet": ("│○○○│", "│···│"),
    "Curio Case": ("│◇·◇│", "│·◇·│"),
    "Shoe Rack": ("│▁▁▁│",),
    "Coat Rack": ("╲│╱", "─┼─"),
    "Record Cabinet": ("┌▥▥┐", "└▥▥┘"),
    "Blanket Chest": ("╰░░░╯",),
    "Filing Cabinet": ("┌──┐", "└──┘"),
    "Wine Rack": ("│▽○▽│", "│○▽○│"),
    # Bedroom and nursery.
    "Single Bed": ("╭○░╮", "╰──╯"),
    "Double Bed": ("╭○○░░╮", "╰────╯"),
    "Canopy Bed": ("┌────┐", "│○░░○│", "└────┘"),
    "Bunk Bed": ("╭○░░╮", "├───┤", "╰○░░╯"),
    "Cradle": ("╭○○╮",),
    "Dressing Screen": ("│╱│", "│╱│"),
    "Sleigh Bed": ("╭○░░░╮", "╰────╯"),
    "Trundle Bed": ("╭○░░╮", "╰───╯"),
    "Loft Bed": ("╭○░░╮", "├───┤", "│···│"),
    "Vanity Bench": ("╰░░╯",),
    "Changing Table": ("╭○○○╮", "╰▤▤▤╯"),
    "Bedside Cabinet": ("┌▣┐", "└•┘"),
    # Kitchen.
    "Kitchen Cupboard": ("┌▣▣┐", "└▣▣┘"),
    "Kitchen Island": ("╾════╼",),
    "Stove Range": ("╭♨─♨╮",),
    "Sink Counter": ("╭─○─╮",),
    "Baker Rack": ("│○○○│", "│───│"),
    "Hoosier Cabinet": ("┌▣▣▣▣┐", "└─○○─┘"),
    "Butcher Block": ("╾░░░░╼",),
    "Dish Cabinet": ("│○○○│", "│───│"),
    "Hearth Oven": ("╭♨♨♨╮",),
    "Breakfast Bar": ("╥╾════╼╥",),
    # Bath.
    "Washstand": ("╭○╮",),
    "Bathtub": ("╭≈≈≈╮",),
    "Towel Rack": ("│▤▤▤│",),
    "Shower Stall": ("┌──┐", "│≈≈│", "└──┘"),
    "Laundry Basin": ("╭○○╮",),
    "Tub Screen": ("│≈│", "│≈│"),
    # Lighting and decor.
    "Floor Lamp": ("✦", "│"),
    "Table Lamp": ("◉",),
    "Indoor Planter": ("╰♣╯",),
    "Flower Stand": ("‹✦›",),
    "Candelabrum": ("✦✦✦", "─┼─"),
    "Chandelier": ("✦─✦─✦",),
    "Aquarium": ("┌≈≈≈┐", "└○○○┘"),
    "Sculpture Pedestal": ("╭◇╮", "╰═╯"),
    # Wall decor.
    "Framed Painting": ("╭◇╮",),
    "Wall Clock": ("╭◷╮",),
    "Wall Shelf": ("╾▥═╼",),
    "Tapestry": ("╭░░░╮",),
    "Plate Rack": ("╭○○○╮",),
    "Medicine Cabinet": ("╭┼○┼╮",),
    # Rugs remain visually quiet because they are walkable floor layers.
    "Runner Rug": ("╴···╶",),
    "Round Rug": ("╭·╮", "╰·╯"),
    "Grand Carpet": ("╭─────╮", "│·◇·◇·│", "╰─────╯"),
    "Braided Mat": ("╰···╯",),
    "Mosaic Rug": ("╭·◇·╮", "╰·◇·╯"),
    "Long Hall Carpet": ("╭───────╮", "│·◇·◇·◇·│", "╰───────╯"),
}


def _furniture_catalog_form(name: object) -> str:
    item_name = str(name or "")
    for collection in ("Hearthwood", "Coastal", "Manor"):
        prefix = f"{collection} "
        if item_name.startswith(prefix):
            return item_name[len(prefix):]
    return item_name


def furniture_display_material_role(
    name: object,
    glyph: object,
    material_role: object = "",
) -> str:
    """Return the visual material of one catalog cell, separate from its save art."""
    item_name = str(name or "")
    data = FURNITURE_CATALOG_DATA.get(item_name)
    role = str(material_role or "wood").strip().lower() or "wood"
    if not isinstance(data, dict):
        return role
    source = str(glyph or " ")[:1]
    group = str(data.get("furniture_group", ""))
    form = _furniture_catalog_form(item_name)
    structural = source in {"[", "]", "(", ")", "{", "}", "+", "-", "=", "_", "|", "/", "\\", "T", "c"}
    if group == "Rugs":
        return "accent" if source == "*" else "fabric"
    if group == "Bath":
        return "water" if source in {"~", "O", "o"} else "stone"
    if group == "Bedroom":
        return "wood" if structural else "linen"
    if group == "Seating":
        return "fabric" if source in {"#", "~", "a", "H", "R", "A"} else "wood"
    if group == "Tables & Work":
        return "paper" if source in {"_", ":", "M", "s", "L"} else "wood"
    if group == "Storage":
        if source in {"L", "I", "R"}:
            return "paper"
        if source in {"*", "o", "v"}:
            return "accent"
        if source == "#":
            return "fabric"
        return "wood"
    if group == "Kitchen":
        if source == "F":
            return "fire"
        if source == "O":
            return "water"
        if form in {"Stove Range", "Sink Counter", "Butcher Block", "Hearth Oven"}:
            return "stone"
        return "wood"
    if group == "Lighting & Decor":
        if source == "f":
            return "plant"
        if form == "Aquarium" and source in {"~", "o", "O"}:
            return "water"
        return "accent" if source in {"*", "i", "A"} else "wood"
    if group == "Wall Decor":
        if source == "T":
            return "fabric"
        if source in {"L", "_"}:
            return "paper"
        if form == "Medicine Cabinet" and source == "O":
            return "water"
        return "wood" if structural else "accent"
    return role


def furniture_display_glyph(
    glyph: object,
    material_role: object = "",
    detailed: bool = True,
) -> str:
    """Return a save-safe, one-column display glyph for catalog artwork."""
    source = str(glyph or " ")[:1]
    if not detailed or source == " ":
        return source
    role = str(material_role or "").strip().lower()
    if role == "fire" and source in {"F", ".", ":", "*"}:
        return "♨" if source == "F" else "░"
    if role == "water" and source in {"~", "O", "o", ".", ":"}:
        return "≈" if source in {"~", ".", ":"} else "◉"
    return _FURNITURE_UNICODE_GLYPHS.get(source, source)


FURNITURE_FINISHES: Dict[str, Dict[str, str]] = {
    "Natural": {"description": "The original materials and upholstery."},
    "Whitewashed": {"description": "Pale wood and warm cream fabric."},
    "Walnut": {"description": "Dark practical timber with neutral cloth."},
    "Cherry": {"description": "Red-toned wood and rich upholstery."},
    "Forest": {"description": "Green-stained wood and woodland fabric."},
    "Ocean": {"description": "Blue paint with cool coastal upholstery."},
    "Royal": {"description": "Purple accents and formal decorative cloth."},
}


FURNITURE_COMPONENT_ZONES: Dict[str, Tuple[Dict[str, object], ...]] = {
    "Dining Set": (
        {"component": "rest", "cells": tuple((x, y) for y in range(3) for x in (0, 8))},
        {"component": "family_meal", "cells": tuple((x, y) for y in range(3) for x in range(1, 8))},
    ),
    "Kitchen Suite": (
        {"component": "cook", "cells": ((1, 1), (2, 1))},
        {"component": "wash", "cells": ((4, 1),)},
        {"component": "prepare", "cells": ((5, 1), (6, 1), (7, 1))},
    ),
    "Workshop Bench": (
        {"component": "craft", "cells": ((1, 1), (2, 1), (4, 1), (5, 1), (6, 1))},
        {"component": "gear", "cells": ((3, 1),)},
    ),
    "Dressing Vanity": (
        {"component": "mirror", "cells": tuple((x, y) for y in (0, 1) for x in range(8))},
        {"component": "storage", "cells": tuple((x, 2) for x in range(8))},
    ),
    "Storage Hutch": (
        {"component": "bookshelf", "cells": tuple((x, y) for y in (0, 1) for x in range(7))},
        {"component": "storage", "cells": tuple((x, 2) for x in range(7))},
    ),
    "Reading Nook": (
        {"component": "bookshelf", "cells": tuple((x, y) for y in range(3) for x in range(5))},
        {"component": "rest", "cells": tuple((x, y) for y in range(3) for x in range(5, 9))},
    ),
    "Parlor Set": (
        {"component": "rest", "cells": tuple((x, y) for y in range(3) for x in (*range(4), *range(5, 9)))},
        {"component": "social", "cells": ((4, 0), (4, 1), (4, 2))},
    ),
}
FURNITURE_COMPONENT_ZONES.update(FURNITURE_CATALOG_COMPONENT_ZONES)


# Cells listed here remain part of the reserved placement footprint and keep
# rendering their furniture art, but actors may occupy them. `seat` cells are
# also preferred by household routines and standing interaction; `open` cells
# are intentional negative space within a coordinated furniture arrangement.
FURNITURE_WALKABLE_ZONES: Dict[str, Tuple[Dict[str, object], ...]] = {
    "Wooden Chair": (
        {"kind": "seat", "cells": ((0, 0),)},
    ),
    "Armchair": (
        {"kind": "seat", "cells": ((0, 0),)},
    ),
    "Couch": (
        {"kind": "seat", "cells": ((1, 0),)},
    ),
    "Dining Set": (
        {"kind": "seat", "cells": tuple((x, y) for y in range(3) for x in (0, 8))},
    ),
    "Sectional Couch": (
        {"kind": "seat", "cells": tuple((x, 1) for x in range(1, 7))},
    ),
    "Reading Nook": (
        {"kind": "seat", "cells": ((6, 1), (7, 1))},
    ),
    "Parlor Set": (
        {"kind": "seat", "cells": ((1, 1), (2, 1), (6, 1), (7, 1))},
        {"kind": "open", "cells": ((4, 0), (4, 2))},
    ),
}
FURNITURE_WALKABLE_ZONES.update(FURNITURE_CATALOG_WALKABLE_ZONES)


_CLOCKWISE_GLYPHS = {
    "─": "│", "│": "─", "═": "║", "║": "═",
    "┌": "┐", "┐": "┘", "┘": "└", "└": "┌",
    "╭": "╮", "╮": "╯", "╯": "╰", "╰": "╭",
    "╔": "╗", "╗": "╝", "╝": "╚", "╚": "╔",
    "┬": "┤", "┤": "┴", "┴": "├", "├": "┬",
    "╤": "╢", "╢": "╧", "╧": "╟", "╟": "╤",
    "╾": "╿", "╿": "╼", "╼": "╽", "╽": "╾",
    "╴": "╷", "╷": "╶", "╶": "╵", "╵": "╴",
    "╱": "╲", "╲": "╱",
    "/": "\\", "\\": "/",
    "-": "|", "|": "-",
}


def normalize_furniture_rotation(rotation: object) -> int:
    """Return a save-safe clockwise quarter-turn value in the 0..3 range."""
    try:
        return int(rotation) % 4
    except (TypeError, ValueError):
        return 0


def _rotate_rows_clockwise(rows: Iterable[str]) -> Tuple[str, ...]:
    source = tuple(str(row) for row in rows)
    if not source:
        return ()
    height = len(source)
    width = len(source[0])
    return tuple(
        "".join(_CLOCKWISE_GLYPHS.get(source[height - 1 - x][y], source[height - 1 - x][y]) for x in range(height))
        for y in range(width)
    )


FURNITURE_ART: Dict[str, Dict[str, object]] = {
    # Original farmhouse furniture. These silhouettes deliberately stay inside
    # the historical collision footprints so old saves retain their layouts,
    # while detailed mode gets the same clear Unicode visual language as the
    # expanded catalog and large-format collections.
    "Wooden Chair": {
        "rows": ("╥",), "simple_rows": ("h",),
        "roles": {"╥": "wood", "h": "wood"},
    },
    "Armchair": {
        "rows": ("▰",), "simple_rows": ("a",),
        "roles": {"▰": "fabric", "a": "fabric"},
    },
    "Bed": {
        "rows": ("○▓▓", "╚═╝"),
        "simple_rows": ("o##", "+=+"),
        "roles": {
            "○": "linen", "▓": "fabric", "╚": "wood", "═": "wood", "╝": "wood",
            "o": "linen", "#": "fabric", "+": "wood", "=": "wood",
        },
    },
    "Wooden Table": {
        "rows": ("╾╼",), "simple_rows": ("[]",),
        "roles": {"╾": "wood", "╼": "wood", "[": "wood", "]": "wood"},
    },
    "Bookshelf": {
        "rows": ("▥", "▤"), "simple_rows": ("L", "L"),
        "roles": {"▥": "paper", "▤": "paper", "L": "paper"},
    },
    "Decorative Rug": {
        "rows": ("╭◆╮", "╰◇╯"), "simple_rows": ("+*+", "+.+"),
        "roles": {
            "╭": "fabric", "╮": "fabric", "╰": "fabric", "╯": "fabric",
            "◆": "accent", "◇": "fabric", "+": "fabric", "*": "accent", ".": "fabric",
        },
    },
    "House Plant": {
        "rows": ("♣",), "simple_rows": ("f",),
        "roles": {"♣": "accent", "f": "accent"},
    },
    "Wall Calendar": {
        "rows": ("▧",), "simple_rows": ("K",),
        "roles": {"▧": "paper", "K": "paper"},
    },
    "Wall Mirror": {
        "rows": ("◉",), "simple_rows": ("m",),
        "roles": {"◉": "water", "m": "water"},
    },
    "Wall Art": {
        "rows": ("◇",), "simple_rows": ("A",),
        "roles": {"◇": "accent", "A": "accent"},
    },
    "Dresser": {
        "rows": ("▤▤",), "simple_rows": ("UU",),
        "roles": {"▤": "wood", "U": "wood"},
    },
    "Television": {
        "rows": ("▣",), "simple_rows": ("V",),
        "roles": {"▣": "water", "V": "water"},
    },
    "Shelf": {
        "rows": ("▥▤",), "simple_rows": ("SL",),
        "roles": {"▥": "paper", "▤": "accent", "S": "wood", "L": "paper"},
    },
    "Kitchen Counter": {
        "rows": ("╾○▤╼",), "simple_rows": ("[o=]",),
        "roles": {
            "╾": "stone", "○": "water", "▤": "stone", "╼": "stone",
            "[": "stone", "o": "water", "=": "stone", "]": "stone",
        },
    },
    "Couch": {
        "rows": ("╭▓╮",), "simple_rows": ("[#]",),
        "roles": {"╭": "wood", "▓": "fabric", "╮": "wood", "[": "wood", "#": "fabric", "]": "wood"},
    },
    "Large Rug": {
        "rows": ("╭───╮", "│◆◇◆│", "╰───╯"),
        "simple_rows": ("+---+", "|*.*|", "+---+"),
        "roles": {
            "╭": "fabric", "─": "fabric", "╮": "fabric", "│": "fabric",
            "◆": "accent", "◇": "fabric", "╰": "fabric", "╯": "fabric",
            "+": "fabric", "-": "fabric", "|": "fabric", "*": "accent", ".": "fabric",
        },
    },
    "Nightstand": {
        "rows": ("▤",), "simple_rows": ("n",),
        "roles": {"▤": "wood", "n": "wood"},
    },
    "Wash Basin": {
        "rows": ("◉◉",), "simple_rows": ("()",),
        "roles": {"◉": "water", "(": "stone", ")": "stone"},
    },
    "Pantry": {
        "rows": ("▦▦",), "simple_rows": ("PP",),
        "roles": {"▦": "wood", "P": "wood"},
    },
    "Fireplace": {
        "rows": ("╭♨╮",), "simple_rows": ("[F]",),
        "roles": {"╭": "stone", "♨": "fire", "╮": "stone", "[": "stone", "F": "fire", "]": "stone"},
    },
    "Writing Desk": {
        "rows": ("╾▤",), "simple_rows": ("D_",),
        "roles": {"╾": "wood", "▤": "paper", "D": "wood", "_": "paper"},
    },
    "Tea Table": {
        "rows": ("●",), "simple_rows": ("o",),
        "roles": {"●": "wood", "o": "wood"},
    },
    "Standing Lamp": {
        "rows": ("✦",), "simple_rows": ("!",),
        "roles": {"✦": "accent", "!": "accent"},
    },
    "Flower Vase": {
        "rows": ("⚘",), "simple_rows": ("y",),
        "roles": {"⚘": "accent", "y": "accent"},
    },
    "Wardrobe": {
        "rows": ("▥▥",), "simple_rows": ("WW",),
        "roles": {"▥": "wood", "W": "wood"},
    },
    "Room Divider": {
        "rows": ("│", "│"), "simple_rows": ("|", "|"),
        "roles": {"│": "wood", "|": "wood"},
    },
    "Crib": {
        "rows": ("╫╫",), "simple_rows": ("qq",),
        "roles": {"╫": "wood", "q": "wood"},
    },
    "Child Bed": {
        "rows": ("○▓",), "simple_rows": ("o=",),
        "roles": {"○": "linen", "▓": "fabric", "o": "linen", "=": "fabric"},
    },
    "Toy Shelf": {
        "rows": ("▦",), "simple_rows": ("j",),
        "roles": {"▦": "accent", "j": "accent"},
    },
    "Study Desk": {
        "rows": ("╾▧",), "simple_rows": ("z_",),
        "roles": {"╾": "wood", "▧": "paper", "z": "wood", "_": "paper"},
    },
    "Family Table": {
        "rows": ("╾◆╼",), "simple_rows": ("[+]",),
        "roles": {"╾": "wood", "◆": "accent", "╼": "wood", "[": "wood", "+": "accent", "]": "wood"},
    },
    "Keepsake Chest": {
        "rows": ("▰◆",), "simple_rows": ("[]",),
        "roles": {"▰": "wood", "◆": "accent", "[": "wood", "]": "accent"},
    },
    "Blackjack Table": {"rows": ("[1]",), "roles": {"[": "wood", "1": "accent", "]": "wood"}},
    "Hold'em Table": {"rows": ("[2]",), "roles": {"[": "wood", "2": "accent", "]": "wood"}},
    "Hearts Table": {"rows": ("[3]",), "roles": {"[": "wood", "3": "accent", "]": "wood"}},
    "Solitaire Table": {"rows": ("[4]",), "roles": {"[": "wood", "4": "accent", "]": "wood"}},
    "Checkers Table": {"rows": ("[5]",), "roles": {"[": "wood", "5": "paper", "]": "wood"}},
    "Chess Table": {"rows": ("[6]",), "roles": {"[": "wood", "6": "paper", "]": "wood"}},
    "Mancala Board": {"rows": ("[7]",), "roles": {"[": "wood", "7": "wood", "]": "wood"}},
    "Royal Game of Ur Board": {"rows": ("[8]",), "roles": {"[": "wood", "8": "accent", "]": "wood"}},

    # First large-format furniture collection. Every row is exactly the
    # collision footprint width, so every visible cell belongs to one object.
    "Four-Poster Bed": {
        "rows": (
            "╔═════╗",
            "║○▓▓▓○║",
            "╚╤═══╤╝",
        ),
        "simple_rows": (
            "+-----+",
            "|o###o|",
            "+T---T+",
        ),
        "roles": {
            "╔": "wood", "═": "wood", "╗": "wood", "║": "wood",
            "╚": "wood", "╤": "wood", "╝": "wood", "○": "linen",
            "▓": "fabric", "+": "wood", "-": "wood", "|": "wood",
            "o": "linen", "#": "fabric", "T": "wood",
        },
    },
    "Dining Set": {
        "rows": (
            "c┌─────┐c",
            "c│═════│c",
            "c└─────┘c",
        ),
        "simple_rows": (
            "c+-----+c",
            "c|=====|c",
            "c+-----+c",
        ),
        "roles": {"c": "wood", "┌": "wood", "─": "wood", "┐": "wood", "│": "wood", "═": "wood", "└": "wood", "┘": "wood", "+": "wood", "-": "wood", "|": "wood", "=": "wood"},
    },
    "Library Bookcase": {
        "rows": (
            "╔═══════╗",
            "║▥▤▥▤▥▤▥║",
        ),
        "simple_rows": (
            "+-------+",
            "|LILILIL|",
        ),
        "roles": {"╔": "wood", "═": "wood", "╗": "wood", "║": "wood", "▥": "paper", "▤": "accent", "+": "wood", "-": "wood", "|": "wood", "L": "paper", "I": "accent"},
    },
    "Sectional Couch": {
        "rows": (
            "┌──────┐",
            "└▓▓▓▓▓▓┘",
        ),
        "simple_rows": (
            "+------+",
            "+######+",
        ),
        "roles": {"┌": "wood", "─": "fabric", "┐": "wood", "└": "wood", "▓": "fabric", "┘": "wood", "+": "wood", "-": "fabric", "#": "fabric"},
    },
    "Kitchen Suite": {
        "rows": (
            "┌──┬────┐",
            "│▦░│□░○░│",
        ),
        "simple_rows": (
            "+--+----+",
            "|#.+O.o.|",
        ),
        "roles": {"┌": "stone", "─": "stone", "┬": "stone", "┐": "stone", "│": "stone", "▦": "fire", "░": "stone", "□": "water", "○": "stone", "+": "stone", "-": "stone", "|": "stone", "#": "fire", ".": "stone", "O": "water", "o": "stone"},
    },
    "Display Counter": {
        "rows": (
            "┌───────┐",
            "└─$─$─$─┘",
        ),
        "simple_rows": (
            "+-------+",
            "+-$-$-$-+",
        ),
        "roles": {"┌": "wood", "─": "wood", "┐": "wood", "└": "wood", "┘": "wood", "$": "shop", "+": "wood", "-": "wood"},
    },
    "Workshop Bench": {
        "rows": ("┌──────┐", "│⚒□◇○░░│"),
        "simple_rows": ("+------+", "|T[]o..|"),
        "roles": {"┌": "wood", "─": "wood", "┐": "wood", "│": "wood", "⚒": "stone", "□": "stone", "◇": "accent", "○": "stone", "░": "wood", "+": "wood", "-": "wood", "|": "wood", "T": "stone", "[": "stone", "]": "stone", "o": "accent", ".": "wood"},
    },
    "Bathing Tub": {
        "rows": ("┌─────┐", "│░≋≋≋░│", "└─────┘"),
        "simple_rows": ("+-----+", "|.~~~.|", "+-----+"),
        "roles": {"┌": "stone", "─": "stone", "┐": "stone", "│": "stone", "░": "water", "≋": "water", "└": "stone", "┘": "stone", "+": "stone", "-": "stone", "|": "stone", ".": "water", "~": "water"},
    },
    "Dressing Vanity": {
        "rows": ("┌──○───┐", "│░░║░░░│", "└──┴───┘"),
        "simple_rows": ("+--o---+", "|..|...|", "+--T---+"),
        "roles": {"┌": "wood", "─": "wood", "○": "water", "┐": "wood", "│": "wood", "░": "wood", "║": "water", "└": "wood", "┴": "wood", "┘": "wood", "+": "wood", "-": "wood", "o": "water", "|": "wood", ".": "wood", "T": "wood"},
    },
    "Storage Hutch": {
        "rows": ("╔═════╗", "║▥▤▥▤▥║", "╟─□─□─╢"),
        "simple_rows": ("+-----+", "|LILIL|", "+-o-o-+"),
        "roles": {"╔": "wood", "═": "wood", "╗": "wood", "║": "wood", "▥": "paper", "▤": "accent", "╟": "wood", "─": "wood", "□": "stone", "╢": "wood", "+": "wood", "-": "wood", "|": "wood", "L": "paper", "I": "accent", "o": "stone"},
    },
    "Stone Hearth": {
        "rows": ("╔═════╗", "║░░F░░║", "╚═╤═╤═╝"),
        "simple_rows": ("+-----+", "|..F..|", "+-T-T-+"),
        "roles": {"╔": "stone", "═": "stone", "╗": "stone", "║": "stone", "░": "fire", "F": "fire", "╚": "stone", "╤": "stone", "╝": "stone", "+": "stone", "-": "stone", "|": "stone", ".": "fire", "T": "stone"},
    },
    "Reading Nook": {
        "rows": ("╔═══╗┌──┐", "║▥▤▥║│▓▓│", "╚═══╝└──┘"),
        "simple_rows": ("+---++--+", "|LIL||##|", "+---++--+"),
        "roles": {"╔": "wood", "═": "wood", "╗": "wood", "┌": "wood", "─": "fabric", "┐": "wood", "║": "wood", "▥": "paper", "▤": "accent", "│": "wood", "▓": "fabric", "╚": "wood", "╝": "wood", "└": "wood", "┘": "wood", "+": "wood", "-": "wood", "|": "wood", "L": "paper", "I": "accent", "#": "fabric"},
    },
    "Parlor Set": {
        "rows": ("┌──┐·┌──┐", "│▓▓│T│▓▓│", "└──┘·└──┘"),
        "simple_rows": ("+--+.+--+", "|##|T|##|", "+--+.+--+"),
        "roles": {"┌": "wood", "─": "fabric", "┐": "wood", "│": "wood", "▓": "fabric", "T": "wood", "└": "wood", "┘": "wood", "·": "fabric", "+": "wood", "-": "fabric", "|": "wood", "#": "fabric", ".": "fabric"},
    },
}
FURNITURE_ART.update(FURNITURE_CATALOG_ART)


def furniture_art_rows(
    name: str,
    detailed: bool = True,
    rotation: int = 0,
) -> Tuple[str, ...]:
    record = FURNITURE_ART.get(str(name), {})
    key = "rows" if detailed or not record.get("simple_rows") else "simple_rows"
    rows = record.get(key, ())
    result = tuple(str(row) for row in rows) if isinstance(rows, (list, tuple)) else ()
    for _ in range(normalize_furniture_rotation(rotation)):
        result = _rotate_rows_clockwise(result)
    return result


def furniture_art_size(name: str, rotation: int = 0) -> Optional[Tuple[int, int]]:
    rows = furniture_art_rows(name, True, rotation)
    if not rows:
        return None
    return max(len(row) for row in rows), len(rows)


def furniture_is_rotatable(name: str) -> bool:
    size = furniture_art_size(name)
    return bool(size and size != (1, 1))


def furniture_has_art(name: str) -> bool:
    return bool(furniture_art_rows(name))


def normalize_furniture_finish(finish: object) -> str:
    value = str(finish or "Natural").strip().title()
    return value if value in FURNITURE_FINISHES else "Natural"


def furniture_art_cell(
    name: str,
    offset_x: int,
    offset_y: int,
    detailed: bool = True,
    rotation: int = 0,
) -> Optional[FurnitureCell]:
    record = FURNITURE_ART.get(str(name), {})
    rows = furniture_art_rows(name, detailed, rotation)
    if not (0 <= int(offset_y) < len(rows)):
        return None
    row = rows[int(offset_y)]
    if not (0 <= int(offset_x) < len(row)):
        return None
    glyph = row[int(offset_x)]
    roles = record.get("roles", {})
    role = "default"
    if isinstance(roles, dict):
        source_glyph = glyph
        for _ in range((4 - normalize_furniture_rotation(rotation)) % 4):
            source_glyph = _CLOCKWISE_GLYPHS.get(source_glyph, source_glyph)
        role = str(roles.get(glyph, roles.get(source_glyph, "default")))
    return glyph, role


def furniture_display_rows(
    name: str,
    detailed: bool = True,
    rotation: int = 0,
) -> Tuple[str, ...]:
    """Return clean render-only artwork while preserving the source footprint."""
    if not detailed or name not in FURNITURE_CATALOG_DATA:
        return furniture_art_rows(name, detailed, rotation)
    form = _furniture_catalog_form(name)
    rows = _FURNITURE_FORM_DISPLAY_ROWS.get(form)
    source_rows = furniture_art_rows(name, True, 0)
    if (
        not rows
        or len(rows) != len(source_rows)
        or any(len(display) != len(source) for display, source in zip(rows, source_rows))
    ):
        rows = tuple(
            "".join(furniture_display_glyph(glyph, "", True) for glyph in row)
            for row in source_rows
        )
    for _ in range(normalize_furniture_rotation(rotation)):
        rows = _rotate_rows_clockwise(rows)
    return rows


def furniture_display_cell(
    name: str,
    offset_x: int,
    offset_y: int,
    detailed: bool = True,
    rotation: int = 0,
) -> Optional[str]:
    """Return one cell from the render-only visual for a furniture item."""
    rows = furniture_display_rows(name, detailed, rotation)
    y, x = int(offset_y), int(offset_x)
    if not (0 <= y < len(rows)):
        return None
    if not (0 <= x < len(rows[y])):
        return None
    return rows[y][x]


_VERTICAL_FLIP_GLYPHS = {
    "┌": "└", "└": "┌", "┐": "┘", "┘": "┐",
    "╭": "╰", "╰": "╭", "╮": "╯", "╯": "╮",
    "┬": "┴", "┴": "┬", "├": "├", "┤": "┤",
    "╥": "╨", "╨": "╥", "╿": "╽", "╽": "╿",
    "╷": "╵", "╵": "╷", "╱": "╲", "╲": "╱",
}


def furniture_orient_display_glyph(glyph: object, side: object = "south") -> str:
    """Orient a visual cell exactly as a procedural building's grid is oriented."""
    result = str(glyph or " ")[:1]
    direction = str(side or "south")
    if direction == "north":
        return _VERTICAL_FLIP_GLYPHS.get(result, result)
    turns = {"west": 1, "east": 3}.get(direction, 0)
    for _ in range(turns):
        result = _CLOCKWISE_GLYPHS.get(result, result)
    return result


def furniture_source_offset(
    name: str, offset_x: int, offset_y: int, rotation: int = 0,
) -> Optional[Tuple[int, int]]:
    size = furniture_art_size(name)
    if not size:
        return None
    width, height = size
    x, y = int(offset_x), int(offset_y)
    turn = normalize_furniture_rotation(rotation)
    rotated_size = furniture_art_size(name, turn)
    if not rotated_size or not (0 <= x < rotated_size[0] and 0 <= y < rotated_size[1]):
        return None
    if turn == 0:
        return x, y
    if turn == 1:
        return y, height - 1 - x
    if turn == 2:
        return width - 1 - x, height - 1 - y
    return width - 1 - y, x


def furniture_component_at(
    name: str, offset_x: int, offset_y: int, rotation: int = 0,
) -> str:
    source = furniture_source_offset(name, offset_x, offset_y, rotation)
    if source is None:
        return ""
    for zone in FURNITURE_COMPONENT_ZONES.get(str(name), ()):
        cells = zone.get("cells", ())
        if source in cells:
            return str(zone.get("component", ""))
    return ""


def furniture_walkable_kind(
    name: str, offset_x: int, offset_y: int, rotation: int = 0,
) -> str:
    """Return `seat`, `open`, or an empty string for a furniture cell."""
    source = furniture_source_offset(name, offset_x, offset_y, rotation)
    if source is None:
        return ""
    for zone in FURNITURE_WALKABLE_ZONES.get(str(name), ()):
        if source in zone.get("cells", ()):
            return str(zone.get("kind", ""))
    return ""


def validate_furniture_art() -> Tuple[str, ...]:
    problems = []
    for name, record in FURNITURE_ART.items():
        detailed = furniture_art_rows(name, True)
        simple = furniture_art_rows(name, False)
        if not detailed or len({len(row) for row in detailed}) != 1:
            problems.append(f"{name}: detailed artwork is not rectangular")
            continue
        if simple and (
            len(simple) != len(detailed)
            or any(len(simple_row) != len(detailed_row) for simple_row, detailed_row in zip(simple, detailed))
        ):
            problems.append(f"{name}: simple artwork dimensions differ")
    for name, zones in FURNITURE_WALKABLE_ZONES.items():
        size = furniture_art_size(name)
        if not size:
            problems.append(f"{name}: walkable cells require registered artwork")
            continue
        width, height = size
        seen = set()
        for zone in zones:
            kind = str(zone.get("kind", ""))
            if kind not in {"seat", "open"}:
                problems.append(f"{name}: unknown walkable cell kind {kind!r}")
            for cell in zone.get("cells", ()):
                if cell in seen:
                    problems.append(f"{name}: duplicate walkable cell {cell}")
                seen.add(cell)
                if not (
                    isinstance(cell, tuple) and len(cell) == 2
                    and 0 <= int(cell[0]) < width and 0 <= int(cell[1]) < height
                ):
                    problems.append(f"{name}: walkable cell {cell} is outside {width}x{height} art")
    return tuple(problems)


__all__ = [
    "FURNITURE_ART",
    "FURNITURE_FINISHES",
    "FURNITURE_COMPONENT_ZONES",
    "FURNITURE_WALKABLE_ZONES",
    "furniture_art_cell",
    "furniture_art_rows",
    "furniture_art_size",
    "furniture_component_at",
    "furniture_has_art",
    "furniture_is_rotatable",
    "furniture_walkable_kind",
    "normalize_furniture_rotation",
    "normalize_furniture_finish",
    "furniture_source_offset",
    "validate_furniture_art",
]
