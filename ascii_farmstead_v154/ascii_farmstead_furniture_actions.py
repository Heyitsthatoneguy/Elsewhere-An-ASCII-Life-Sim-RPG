from __future__ import annotations

"""Pure classification helpers for functional furniture interactions.

Furniture names and footprints are save data, so mechanics are derived without
renaming items or altering artwork. Every furniture record must resolve to one
of these concrete action families.
"""

from typing import Dict, Mapping


FURNITURE_ACTION_LABELS: Dict[str, str] = {
    "sleep": "sleep",
    "seat": "sit down",
    "cook": "cook",
    "work": "work or write",
    "read": "read or browse books",
    "storage": "open storage",
    "bath": "bathe",
    "mirror": "use mirror",
    "hearth": "use hearth",
    "table": "use table",
    "light": "turn light on or off",
    "plant": "care for plant",
    "art": "study artwork",
    "clock": "check clock",
    "rug": "use rug",
    "aquarium": "tend aquarium",
    "privacy": "fold or open divider",
    "calendar": "open calendar",
    "forecast": "watch television",
    "family": "use family furniture",
    "keepsake": "review keepsakes",
    "outfit": "change outfit or use storage",
    "game": "play game",
    "records": "read records",
    "service": "request service",
    "animal_care": "use animal-care station",
}


_GAME_NAMES = {
    "Blackjack Table", "Hold'em Table", "Hearts Table", "Solitaire Table",
    "Checkers Table", "Chess Table", "Mancala Board", "Royal Game of Ur Board",
}


def furniture_action_id(name: object, data: Mapping[str, object] | None = None) -> str:
    """Return the primary non-flavor mechanic for any furniture item."""
    item_name = str(name or "Furniture")
    lowered = item_name.lower()
    record = data if isinstance(data, Mapping) else {}
    function = str(record.get("furniture_function", "") or "").lower()
    group = str(record.get("furniture_group", "") or "").lower()

    if item_name in _GAME_NAMES:
        return "game"
    if "calendar" in lowered:
        return "calendar"
    if "television" in lowered:
        return "forecast"
    if "keepsake" in lowered:
        return "keepsake"
    if "fireplace" in lowered:
        return "hearth"
    if lowered == "hearth" or "hearth fixture" in lowered:
        return "hearth"
    if "mirror" in lowered:
        return "mirror"
    if any(word in lowered for word in ("crib", "child bed", "toy shelf")):
        return "family"
    if any(word in lowered for word in ("aquarium", "fish tank")):
        return "aquarium"
    if any(word in lowered for word in ("lamp", "chandelier", "candelabrum")):
        return "light"
    if any(word in lowered for word in ("planter", "flower stand", "flower vase", "house plant")):
        return "plant"
    if any(word in lowered for word in ("painting", "tapestry", "sculpture", "wall art")):
        return "art"
    if "clock" in lowered:
        return "clock"
    if any(word in lowered for word in ("rug", "carpet", "mat")):
        return "rug"
    if any(word in lowered for word in ("room divider", "dressing screen", "privacy screen")):
        return "privacy"
    if "tub screen" in lowered:
        return "privacy"
    if any(word in lowered for word in ("dresser", "wardrobe", "vanity")):
        return "outfit"
    if any(word in lowered for word in ("writing desk", "secretary desk", "study desk", "map table", "drafting table", "sewing table")):
        return "work"
    if any(word in lowered for word in ("workbench", "tool rack", "materials bench", "forge fixture")):
        return "work"
    if any(word in lowered for word in ("records board", "notice", "placard", "catalog")):
        return "records"
    if "service counter" in lowered:
        return "service"
    if "animal fixture" in lowered:
        return "animal_care"
    if "examination fixture" in lowered:
        return "bath"
    if any(word in lowered for word in ("stock display", "produce display")):
        return "storage"

    function_actions = {
        "sleep": "sleep",
        "rest": "seat",
        "cook": "cook",
        "prepare": "cook",
        "craft": "work",
        "bookshelf": "read",
        "storage": "storage",
        "display_storage": "storage",
        "bathe": "bath",
        "mirror": "mirror",
        "hearth": "hearth",
        "dining": "table",
        "family_meal": "table",
        "social": "table",
    }
    if function in function_actions:
        return function_actions[function]

    if group == "seating" or any(
        word in lowered
        for word in ("chair", "bench", "stool", "sofa", "loveseat", "daybed", "chaise", "recliner", "ottoman", "seat", "swing")
    ):
        return "seat"
    if group == "bedroom" or any(word in lowered for word in ("bed", "cradle", "cot")):
        return "sleep"
    if group == "kitchen" or any(word in lowered for word in ("stove", "oven", "kitchen", "sink", "butcher block")):
        return "cook"
    if group == "bath" or any(word in lowered for word in ("bath", "washstand", "basin", "shower", "towel")):
        return "bath"
    if group == "storage" or any(word in lowered for word in ("shelf", "cabinet", "chest", "hutch", "rack", "cupboard", "pantry", "press", "trunk", "nightstand")):
        return "storage"
    if group == "tables & work" or "table" in lowered or "desk" in lowered:
        return "table"
    if group == "lighting & decor":
        return "art"
    if group == "wall decor":
        return "art"
    if group == "rugs":
        return "rug"
    # No furniture is allowed to fall back to inert inspection. Unknown custom
    # pieces become usable surfaces for planning, writing, and small projects.
    return "work"


def furniture_action_label(name: object, data: Mapping[str, object] | None = None) -> str:
    action = furniture_action_id(name, data)
    return FURNITURE_ACTION_LABELS.get(action, "use furniture")


def furniture_action_coverage(
    records: Mapping[str, Mapping[str, object]],
) -> Dict[str, str]:
    """Return invalid furniture -> reason entries for automated audits."""
    errors: Dict[str, str] = {}
    for name, record in records.items():
        if str(record.get("category", "")) != "furniture":
            continue
        action = furniture_action_id(name, record)
        if action not in FURNITURE_ACTION_LABELS:
            errors[str(name)] = f"unknown action {action!r}"
    return errors


__all__ = [
    "FURNITURE_ACTION_LABELS",
    "furniture_action_coverage",
    "furniture_action_id",
    "furniture_action_label",
]
