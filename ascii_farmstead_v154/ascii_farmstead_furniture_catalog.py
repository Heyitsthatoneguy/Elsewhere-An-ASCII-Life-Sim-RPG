from __future__ import annotations

"""Expanded placeable furniture catalog.

One hundred distinct furniture forms are offered in three material collections. The
module is deliberately independent from the game loop and static-data module
so both the furniture renderer and item catalog can consume the same records.
"""

from typing import Dict, Iterable, List, Sequence, Tuple


FurnitureSpec = Dict[str, object]


def _spec(
    name: str,
    group: str,
    rows: Sequence[str],
    function: str,
    price: int,
    comfort: int,
    detail: str,
    *,
    seats: Iterable[Tuple[int, int]] = (),
    open_cells: Iterable[Tuple[int, int]] = (),
    component: str = "",
    container: str = "",
    capacity: int = 0,
    surface: str = "floor",
    layer: str = "solid",
    material: str = "wood",
    use_edges: Sequence[str] = (),
) -> FurnitureSpec:
    return {
        "name": name,
        "group": group,
        "rows": tuple(rows),
        "function": function,
        "price": price,
        "comfort": comfort,
        "detail": detail,
        "seats": tuple(seats),
        "open_cells": tuple(open_cells),
        "component": component,
        "container": container,
        "capacity": capacity,
        "surface": surface,
        "layer": layer,
        "material": material,
        "use_edges": tuple(use_edges),
    }


FURNITURE_FORM_SPECS: Tuple[FurnitureSpec, ...] = (
    # Seating: ten different silhouettes and scales.
    _spec("Dining Chair", "Seating", ("h",), "rest", 90, 2, "a straight-backed dining chair", seats=((0, 0),)),
    _spec("Rocking Chair", "Seating", ("r",), "rest", 170, 4, "a gently curved rocking chair", seats=((0, 0),)),
    _spec("Reading Chair", "Seating", ("[a]",), "rest", 240, 5, "a deep chair with broad arms", seats=((1, 0),), material="fabric"),
    _spec("Entry Bench", "Seating", ("[==]",), "rest", 220, 4, "a compact bench for boots and visitors", seats=((1, 0), (2, 0))),
    _spec("Kitchen Stool", "Seating", ("o",), "rest", 75, 1, "a small round work stool", seats=((0, 0),)),
    _spec("Loveseat", "Seating", ("[##]",), "rest", 420, 6, "a close two-person upholstered seat", seats=((1, 0), (2, 0)), material="fabric"),
    _spec("Daybed", "Seating", ("o###", "===="), "rest", 560, 7, "a low daybed for reading or an afternoon nap", seats=((1, 0), (2, 0), (3, 0)), material="fabric"),
    _spec("Chaise Lounge", "Seating", ("[###]",), "rest", 510, 7, "a long reclining lounge", seats=((1, 0), (2, 0), (3, 0)), material="fabric"),
    _spec("Window Seat", "Seating", ("|###|",), "rest", 470, 6, "a cushioned seat shaped for a bright wall", seats=((1, 0), (2, 0), (3, 0)), material="fabric"),
    _spec("Conversation Sofa", "Seating", ("[##].[##]",), "rest", 760, 9, "a paired sofa arrangement with a central aisle", seats=((1, 0), (2, 0), (6, 0), (7, 0)), open_cells=((4, 0),), material="fabric"),

    # Tables and work surfaces.
    _spec("Side Table", "Tables & Work", ("[=]",), "dining", 120, 2, "a narrow occasional table"),
    _spec("Coffee Table", "Tables & Work", ("[---]",), "social", 230, 3, "a broad low table for a sitting room", component="social"),
    _spec("Dining Table", "Tables & Work", ("[=====]",), "dining", 390, 4, "a long household dining table", component="family_meal", use_edges=("top", "bottom")),
    _spec("Writing Desk", "Tables & Work", ("[___]",), "craft", 350, 4, "a tidy desk with a broad writing surface", material="paper", use_edges=("bottom",)),
    _spec("Study Table", "Tables & Work", ("[::]",), "craft", 280, 3, "a practical study and lesson table", material="paper"),
    _spec("Drafting Table", "Tables & Work", ("/___\\",), "craft", 480, 5, "an angled drafting surface for plans and maps", material="paper", use_edges=("bottom",)),
    _spec("Worktable", "Tables & Work", ("[T=T]",), "craft", 520, 5, "a reinforced table for household projects"),
    _spec("Tea Cart", "Tables & Work", ("o[=]o",), "social", 310, 4, "a wheeled cart for tea and shared visits", component="social"),

    # Storage and display furniture.
    _spec("Bookcase", "Storage", ("|LIL|", "|LIL|"), "bookshelf", 360, 4, "a two-tier bookcase", component="bookshelf", container="bookshelf", capacity=240, material="paper", use_edges=("bottom",)),
    _spec("Tall Cabinet", "Storage", ("[||]", "[||]"), "storage", 430, 4, "a tall enclosed household cabinet", component="storage", container="cabinet", capacity=360),
    _spec("Wardrobe", "Storage", ("[WW]", "[WW]"), "storage", 520, 5, "a full-height wardrobe", component="storage", container="wardrobe", capacity=480),
    _spec("Dresser", "Storage", ("[==]", "[__]"), "storage", 390, 4, "a two-level clothes dresser", component="storage", container="dresser", capacity=360),
    _spec("Display Shelf", "Storage", ("|*-*|", "|*-*|"), "display_storage", 450, 5, "an open shelf for collections and keepsakes", component="storage", container="display_case", capacity=300, material="accent"),
    _spec("Storage Trunk", "Storage", ("[===]",), "storage", 340, 3, "a sturdy lidded storage trunk", component="storage", container="storage_chest", capacity=600),
    _spec("Linen Press", "Storage", ("[LL]", "[LL]"), "storage", 470, 4, "a deep press for folded linens", component="storage", container="dresser", capacity=420),
    _spec("Corner Hutch", "Storage", ("/LL", "|__"), "storage", 410, 4, "a compact hutch shaped for a room corner", component="storage", container="cabinet", capacity=320),

    # Bedroom and nursery forms.
    _spec("Single Bed", "Bedroom", ("o###", "===="), "sleep", 420, 6, "a neatly made single bed", material="linen", use_edges=("left", "right", "bottom")),
    _spec("Double Bed", "Bedroom", ("oo####", "======"), "sleep", 680, 9, "a broad double bed", material="linen", use_edges=("left", "right", "bottom")),
    _spec("Canopy Bed", "Bedroom", ("+----+", "|o##o|", "T====T"), "sleep", 980, 12, "a tall bed enclosed by carved posts", material="linen", use_edges=("bottom",)),
    _spec("Bunk Bed", "Bedroom", ("o===o", "|---|", "o===o"), "sleep", 740, 8, "a space-saving pair of bunks", material="linen", use_edges=("left", "right")),
    _spec("Cradle", "Bedroom", ("(oo)",), "rest", 260, 4, "a gently curved infant cradle", material="linen"),
    _spec("Dressing Screen", "Bedroom", ("|/|", "|/|"), "mirror", 310, 3, "a folding privacy screen"),

    # Kitchen work and food storage.
    _spec("Kitchen Cupboard", "Kitchen", ("[PP]", "[PP]"), "storage", 460, 4, "a tall cupboard for staples and dishes", component="storage", container="pantry", capacity=420),
    _spec("Kitchen Island", "Kitchen", ("[====]",), "prepare", 610, 5, "a freestanding preparation island", component="prepare", use_edges=("top", "bottom")),
    _spec("Stove Range", "Kitchen", ("[F=F]",), "cook", 720, 6, "a substantial double-burner range", component="cook", material="stone", use_edges=("bottom",)),
    _spec("Sink Counter", "Kitchen", ("[=O=]",), "cook", 580, 5, "a counter centered on a deep wash basin", component="wash", material="stone", use_edges=("bottom",)),
    _spec("Baker Rack", "Kitchen", ("|ooo|", "|---|"), "storage", 390, 4, "an open rack for cooling bread and storing pans", component="storage", container="pantry", capacity=280),

    # Bathing and washroom furniture.
    _spec("Washstand", "Bath", ("[O]",), "bathe", 280, 4, "a compact basin and washstand", component="wash", material="water"),
    _spec("Bathtub", "Bath", ("[~~~]",), "bathe", 740, 8, "a full household bathing tub", material="water", use_edges=("top", "bottom")),
    _spec("Towel Rack", "Bath", ("|===|",), "storage", 180, 2, "a low rack for clean towels", component="storage", container="shelf", capacity=120, material="linen"),

    # Lighting and living decoration.
    _spec("Floor Lamp", "Lighting & Decor", ("*", "|"), "rest", 230, 3, "a tall standing lamp", material="accent"),
    _spec("Table Lamp", "Lighting & Decor", ("i",), "rest", 140, 2, "a small shaded table lamp", material="accent"),
    _spec("Indoor Planter", "Lighting & Decor", ("(f)",), "", 190, 3, "a broad planter with healthy greenery", material="accent"),
    _spec("Flower Stand", "Lighting & Decor", ("{*}",), "", 170, 3, "a raised stand for seasonal flowers", material="accent"),

    # Wall-mounted pieces stay one row tall so they work on perimeter walls.
    _spec("Framed Painting", "Wall Decor", ("[A]",), "", 260, 3, "a framed landscape for an open wall", surface="wall", material="accent"),
    _spec("Wall Clock", "Wall Decor", ("(o)",), "", 220, 2, "a clearly faced household clock", surface="wall", material="accent"),
    _spec("Wall Shelf", "Wall Decor", ("[L=]",), "bookshelf", 250, 3, "a mounted shelf for books and small objects", component="bookshelf", container="bookshelf", capacity=120, surface="wall", material="paper"),

    # Floor coverings use the independent walkable floor layer.
    _spec("Runner Rug", "Rugs", ("/---\\",), "", 190, 3, "a narrow runner for a hallway or bedside", layer="floor", material="fabric"),
    _spec("Round Rug", "Rugs", ("/-\\", "\\-/"), "", 240, 4, "a compact rounded room rug", layer="floor", material="fabric"),
    _spec("Grand Carpet", "Rugs", ("/-----\\", "|.....|", "\\-----/"), "", 620, 8, "a large patterned carpet for a formal room", layer="floor", material="fabric"),
)


# A second collection wave broadens the silhouettes and household purposes
# without replacing any of the original save-safe furniture identifiers.
FURNITURE_FORM_SPECS += (
    # Seating: formal, outdoor, compact, and recreational choices.
    _spec("Captain Chair", "Seating", ("[H]",), "rest", 210, 4, "a broad-backed chair with sturdy arms", seats=((1, 0),)),
    _spec("Folding Chair", "Seating", ("x",), "rest", 65, 1, "a light chair that folds flat when stored", seats=((0, 0),)),
    _spec("Garden Bench", "Seating", ("|====|",), "rest", 340, 4, "a weather-ready bench for a porch or garden", seats=((1, 0), (2, 0), (3, 0), (4, 0))),
    _spec("Piano Bench", "Seating", ("[==]",), "rest", 190, 3, "a slim padded bench for music practice", seats=((1, 0), (2, 0)), material="fabric"),
    _spec("Corner Sofa", "Seating", ("[##]", "[##]"), "rest", 690, 9, "a deep upholstered sofa arranged for a room corner", seats=((1, 0), (2, 0), (1, 1), (2, 1)), material="fabric"),
    _spec("Recliner", "Seating", ("[R=]",), "rest", 430, 7, "an adjustable chair with a raised footrest", seats=((1, 0), (2, 0)), material="fabric"),
    _spec("Ottoman", "Seating", ("[o]",), "rest", 180, 3, "a padded footstool that doubles as a low seat", seats=((1, 0),), material="fabric"),
    _spec("Gossip Bench", "Seating", ("h=h",), "social", 290, 4, "a paired seat made for unhurried conversation", seats=((0, 0), (2, 0)), component="social"),
    _spec("Porch Swing", "Seating", ("+----+", "|####|"), "rest", 580, 7, "a suspended bench that rocks gently on its frame", seats=((1, 1), (2, 1), (3, 1), (4, 1)), material="fabric"),
    _spec("Theater Seat", "Seating", ("{a}",), "rest", 250, 4, "a compact upholstered seat with curved sides", seats=((1, 0),), material="fabric"),

    # Tables and specialist work surfaces.
    _spec("Console Table", "Tables & Work", ("[----]",), "social", 260, 3, "a narrow display table for a hall or sitting room", component="social"),
    _spec("Breakfast Table", "Tables & Work", ("c[=]c",), "dining", 330, 4, "a small table arranged for two people", seats=((0, 0), (4, 0)), component="family_meal"),
    _spec("Sewing Table", "Tables & Work", ("[s__]",), "craft", 410, 5, "a dedicated sewing surface with room for patterns", component="craft", material="paper", use_edges=("bottom",)),
    _spec("Map Table", "Tables & Work", ("[MMMM]",), "craft", 470, 5, "a broad table for charts, routes, and survey notes", component="craft", material="paper", use_edges=("bottom",)),
    _spec("Secretary Desk", "Tables & Work", ("[LL]", "[__]"), "craft", 590, 6, "a writing desk with an enclosed upper book cabinet", component="craft", container="bookshelf", capacity=180, material="paper", use_edges=("bottom",)),
    _spec("Tool Cart", "Tables & Work", ("o[T]o",), "craft", 360, 4, "a wheeled cart that keeps tools close to a project", component="craft"),
    _spec("Pedestal Table", "Tables & Work", ("[=]", "-T-"), "dining", 280, 3, "a compact table balanced on a central pedestal", use_edges=("top", "bottom")),
    _spec("Banquet Table", "Tables & Work", ("c[=======]c",), "dining", 760, 7, "a long formal table for large household meals", seats=((0, 0), (10, 0)), component="family_meal", use_edges=("top", "bottom")),

    # Storage with more specialized container identities.
    _spec("Apothecary Cabinet", "Storage", ("|ooo|", "|ooo|"), "storage", 620, 5, "a many-drawered cabinet for remedies and ingredients", component="storage", container="cabinet", capacity=420),
    _spec("Curio Case", "Storage", ("|***|", "|***|"), "display_storage", 680, 6, "a glazed case for rare finds and treasured keepsakes", component="storage", container="display_case", capacity=360, material="accent"),
    _spec("Shoe Rack", "Storage", ("|___|",), "storage", 160, 2, "a low open rack for boots and shoes", component="storage", container="shelf", capacity=180),
    _spec("Coat Rack", "Storage", ("Y|Y", "-|-"), "storage", 230, 3, "a standing rack for coats, hats, and travel gear", component="storage", container="wardrobe", capacity=180),
    _spec("Record Cabinet", "Storage", ("[RR]", "[RR]"), "storage", 450, 4, "a divided cabinet for records and music", component="storage", container="cabinet", capacity=320),
    _spec("Blanket Chest", "Storage", ("[###]",), "storage", 370, 4, "a broad cedar chest for blankets and seasonal linens", component="storage", container="storage_chest", capacity=500, material="fabric"),
    _spec("Filing Cabinet", "Storage", ("[--]", "[--]"), "storage", 420, 3, "a pair of deep drawers for papers and accounts", component="storage", container="cabinet", capacity=320, material="paper"),
    _spec("Wine Rack", "Storage", ("|vov|", "|vov|"), "storage", 510, 4, "a stable rack with fitted spaces for bottles", component="storage", container="pantry", capacity=280),

    # Bedroom and nursery additions.
    _spec("Sleigh Bed", "Bedroom", ("(o###)", "======"), "sleep", 780, 10, "a curved bed shaped like a traditional sleigh", material="linen", use_edges=("left", "right", "bottom")),
    _spec("Trundle Bed", "Bedroom", ("o====", "[---]"), "sleep", 650, 8, "a bed with a second sleeping frame tucked underneath", material="linen", use_edges=("left", "right", "bottom")),
    _spec("Loft Bed", "Bedroom", ("o===o", "|...|", "|___|"), "sleep", 820, 8, "a raised bed with an open nook beneath it", open_cells=((1, 1), (2, 1), (3, 1)), material="linen", use_edges=("left", "right")),
    _spec("Vanity Bench", "Bedroom", ("[aa]",), "rest", 260, 4, "a short cushioned bench for a dressing table", seats=((1, 0), (2, 0)), material="fabric"),
    _spec("Changing Table", "Bedroom", ("[ooo]", "[___]"), "storage", 430, 4, "a nursery table with deep storage below", component="storage", container="dresser", capacity=260, material="linen"),
    _spec("Bedside Cabinet", "Bedroom", ("[n]", "[_]"), "storage", 240, 3, "a small bedside cabinet with a private drawer", component="storage", container="nightstand", capacity=140),

    # Kitchen fixtures and social food-preparation pieces.
    _spec("Hoosier Cabinet", "Kitchen", ("[PPPP]", "[=OO=]"), "storage", 720, 6, "a full kitchen cabinet with pantry storage and a work shelf", component="storage", container="pantry", capacity=500),
    _spec("Butcher Block", "Kitchen", ("[####]",), "prepare", 450, 5, "a thick freestanding block for serious food preparation", component="prepare", use_edges=("top", "bottom")),
    _spec("Dish Cabinet", "Kitchen", ("|ooo|", "|===|"), "storage", 480, 4, "an open-front cabinet for dishes and serving pieces", component="storage", container="pantry", capacity=300),
    _spec("Hearth Oven", "Kitchen", ("[FFF]",), "cook", 810, 7, "a heavy enclosed oven built around a warm hearth", component="cook", material="stone", use_edges=("bottom",)),
    _spec("Breakfast Bar", "Kitchen", ("c[====]c",), "dining", 520, 5, "a counter-height bar with a seat at either end", seats=((0, 0), (7, 0)), component="family_meal"),

    # Bath and utility fixtures.
    _spec("Shower Stall", "Bath", ("+--+", "|~~|", "+--+"), "bathe", 690, 7, "an enclosed standing shower with a drained floor", material="water", use_edges=("bottom",)),
    _spec("Laundry Basin", "Bath", ("[OO]",), "bathe", 360, 4, "a deep double basin for washing clothes and household goods", component="wash", material="water", use_edges=("bottom",)),
    _spec("Tub Screen", "Bath", ("|~|", "|~|"), "bathe", 410, 5, "a compact screened tub for a narrow washroom", material="water", use_edges=("bottom",)),

    # Larger lighting and decorative focal pieces.
    _spec("Candelabrum", "Lighting & Decor", ("***", "-|-"), "rest", 360, 4, "a branching candle stand that casts a warm glow", material="accent"),
    _spec("Chandelier", "Lighting & Decor", ("*-*-*",), "", 640, 6, "a suspended multi-light fixture for a prominent room", surface="wall", material="accent"),
    _spec("Aquarium", "Lighting & Decor", ("[~~~]", "[ooo]"), "rest", 780, 8, "a glass aquarium alive with plants and small fish", material="water"),
    _spec("Sculpture Pedestal", "Lighting & Decor", ("{A}", "[=]"), "", 520, 5, "a raised pedestal displaying a small sculpture", material="accent"),

    # Wall-mounted storage and decoration.
    _spec("Tapestry", "Wall Decor", ("[TTT]",), "", 390, 5, "a woven wall hanging with a bold repeating pattern", surface="wall", material="fabric"),
    _spec("Plate Rack", "Wall Decor", ("[ooo]",), "display_storage", 320, 3, "a mounted rack for decorative and everyday plates", component="storage", container="display_case", capacity=160, surface="wall", material="accent"),
    _spec("Medicine Cabinet", "Wall Decor", ("[+O+]",), "storage", 380, 4, "a mirrored wall cabinet for remedies and washroom supplies", component="storage", container="cabinet", capacity=180, surface="wall", material="water"),

    # Additional walkable floor coverings.
    _spec("Braided Mat", "Rugs", ("(===)",), "", 160, 3, "a tightly braided mat for a doorway or hearth", layer="floor", material="fabric"),
    _spec("Mosaic Rug", "Rugs", ("/-*-\\", "\\-*-/"), "", 410, 6, "a geometric rug assembled from contrasting woven panels", layer="floor", material="fabric"),
    _spec("Long Hall Carpet", "Rugs", ("/-------\\", "|.......|", "\\-------/"), "", 790, 9, "a long formal carpet made for a broad central hallway", layer="floor", material="fabric"),
)


FURNITURE_COLLECTIONS = (
    ("Hearthwood", 1.00, 0, "warm timber, practical joinery, and homespun cloth"),
    ("Coastal", 1.15, 1, "pale boards, cool fabric, and salt-washed detailing"),
    ("Manor", 1.40, 2, "carved edges, formal upholstery, and polished fittings"),
)


def _styled_rows(rows: Sequence[str], style_index: int) -> Tuple[str, ...]:
    replacements = (
        {},
        {"#": "~", "=": "-", "*": "o", ":": "."},
        {"-": "=", ".": ":", "o": "O", "h": "H", "r": "R"},
    )[style_index]
    return tuple("".join(replacements.get(char, char) for char in row) for row in rows)


def _art_roles(rows: Sequence[str], primary: str) -> Dict[str, str]:
    roles: Dict[str, str] = {}
    for char in "".join(rows):
        if char in {"L", "I", "_"}:
            role = "paper"
        elif char == "F":
            role = "fire"
        elif char in {"O", "~"}:
            role = "water" if primary in {"water", "stone"} else primary
        elif char in {"#", ":"}:
            role = "fabric" if primary not in {"linen", "water"} else primary
        elif char in {"*", "A", "f", "i"}:
            role = "accent"
        elif char == "o" and primary not in {"wood", "stone"}:
            role = primary
        else:
            role = primary
        roles[char] = role
    return roles


FURNITURE_CATALOG_DATA: Dict[str, Dict[str, object]] = {}
FURNITURE_CATALOG_ART: Dict[str, Dict[str, object]] = {}
FURNITURE_CATALOG_COMPONENT_ZONES: Dict[str, Tuple[Dict[str, object], ...]] = {}
FURNITURE_CATALOG_WALKABLE_ZONES: Dict[str, Tuple[Dict[str, object], ...]] = {}

for collection_name, price_multiplier, style_index, collection_detail in FURNITURE_COLLECTIONS:
    for form in FURNITURE_FORM_SPECS:
        item_name = f"{collection_name} {form['name']}"
        rows = _styled_rows(form["rows"], style_index)
        width = len(rows[0])
        height = len(rows)
        layer = str(form["layer"])
        data: Dict[str, object] = {
            "symbol": next((char for char in rows[0] if char.isalnum()), "f"),
            "price": max(25, int(round(int(form["price"]) * price_multiplier / 5.0)) * 5),
            "description": (
                f"{str(form['detail']).capitalize()}, made with {collection_detail}."
            ),
            "radius": None,
            "category": "furniture",
            "furniture_group": str(form["group"]),
            "catalog_collection": collection_name,
            "catalog_item": True,
            "place_locations": ["HouseInterior"],
            "footprint": [width, height],
            "comfort": int(form["comfort"]) + style_index,
        }
        function = str(form["function"])
        if function:
            data["furniture_function"] = function
        if form["use_edges"]:
            data["use_edges"] = list(form["use_edges"])
        if str(form["surface"]) == "wall":
            data["placement_surface"] = "wall"
        if layer == "floor":
            data["placement_layer"] = "floor"
            data["walkable"] = True
        container = str(form["container"])
        if container:
            data["container_profile"] = container
            data["container_capacity"] = int(form["capacity"])
        FURNITURE_CATALOG_DATA[item_name] = data
        FURNITURE_CATALOG_ART[item_name] = {
            "rows": rows,
            "roles": _art_roles(rows, str(form["material"])),
        }
        component = str(form["component"])
        if component:
            FURNITURE_CATALOG_COMPONENT_ZONES[item_name] = ({
                "component": component,
                "cells": tuple((x, y) for y in range(height) for x in range(width)),
            },)
        walkable = []
        if form["seats"]:
            walkable.append({"kind": "seat", "cells": tuple(form["seats"])})
        if form["open_cells"]:
            walkable.append({"kind": "open", "cells": tuple(form["open_cells"])})
        if walkable:
            FURNITURE_CATALOG_WALKABLE_ZONES[item_name] = tuple(walkable)


def validate_furniture_catalog() -> Tuple[str, ...]:
    problems: List[str] = []
    expected = len(FURNITURE_FORM_SPECS) * len(FURNITURE_COLLECTIONS)
    if expected != 300 or len(FURNITURE_CATALOG_DATA) != 300:
        problems.append(
            f"expanded furniture catalog has {len(FURNITURE_CATALOG_DATA)} items; expected 300"
        )
    for name, data in FURNITURE_CATALOG_DATA.items():
        rows = tuple(FURNITURE_CATALOG_ART.get(name, {}).get("rows", ()))
        if not rows or len({len(row) for row in rows}) != 1:
            problems.append(f"{name}: artwork is missing or non-rectangular")
            continue
        if tuple(data.get("footprint", ())) != (len(rows[0]), len(rows)):
            problems.append(f"{name}: footprint does not match artwork")
        if int(data.get("price", 0)) <= 0:
            problems.append(f"{name}: price must be positive")
        if not str(data.get("furniture_group", "")):
            problems.append(f"{name}: catalog group is missing")
    return tuple(problems)


__all__ = [
    "FURNITURE_CATALOG_ART",
    "FURNITURE_CATALOG_COMPONENT_ZONES",
    "FURNITURE_CATALOG_DATA",
    "FURNITURE_CATALOG_WALKABLE_ZONES",
    "FURNITURE_COLLECTIONS",
    "FURNITURE_FORM_SPECS",
    "validate_furniture_catalog",
]
