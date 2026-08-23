from __future__ import annotations

"""Property-driven alchemy and its physical workstation.

The module deliberately keeps mixture generation deterministic.  A formula is
defined by its matrix, ingredients, and finish, so a discovered formula can be
brewed again and produces the same useful item on every save.
"""

import hashlib
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ascii_farmstead_data import (
    BIOME_IDENTITY_DATA,
    CROP_DATA,
    LEFT_PANEL_HEIGHT,
    LEFT_PANEL_WIDTH,
    MENU_BACK,
    WILDERNESS_FORAGE_DATA,
)
from ascii_farmstead_helpers import quantity_agreement, quantity_item_phrase


def MenuItem(*args, **kwargs):
    """Import the UI record lazily so save-state imports remain acyclic."""
    from ascii_farmstead_ui import MenuItem as _MenuItem
    return _MenuItem(*args, **kwargs)


ALCHEMY_SCHEMA_VERSION = 2
ALCHEMY_PROPERTIES: Tuple[str, ...] = (
    "vitality", "vigor", "focus", "force", "guard", "haste",
    "flame", "frost", "growth", "pigment", "fortune", "shadow",
    "insight", "purity",
)

TIMED_ALCHEMY_EFFECT_KEYS: Tuple[str, ...] = (
    "attack", "defense", "max_hp", "max_focus", "stamina_discount",
    "regeneration", "elemental_resistance", "luck", "loot_quality",
    "stealth", "critical_chance", "farming_speed", "movement_speed",
    "armor_pierce", "forage_yield", "poison_resistance",
)


ALCHEMY_MATRIX_DATA: Dict[str, Dict[str, object]] = {
    "Water Matrix": {
        "cost": {}, "capacity": 3, "stability": 7, "duration": 1.0,
        "affinities": {"vitality": 1.25, "vigor": 1.15, "growth": 1.2, "purity": 1.3},
        "description": "A clean, forgiving base suited to restorative mixtures and soil treatments.",
    },
    "Oil Matrix": {
        "cost": {"Sap": 1}, "capacity": 3, "stability": 8, "duration": 1.35,
        "affinities": {"force": 1.2, "guard": 1.25, "pigment": 1.35, "shadow": 1.15},
        "description": "A clinging base for equipment coatings and durable pigments.",
    },
    "Spirit Matrix": {
        "cost": {"Wild Honey": 1}, "capacity": 3, "stability": 6, "duration": 1.2,
        "affinities": {"focus": 1.3, "haste": 1.2, "flame": 1.1, "fortune": 1.25, "shadow": 1.2},
        "description": "A volatile sweet distillate that carries mental and energetic properties.",
    },
    "Tonic Matrix": {
        "cost": {"Wild Herbs": 1}, "capacity": 4, "stability": 9, "duration": 1.4,
        "affinities": {"vitality": 1.2, "vigor": 1.25, "growth": 1.3, "purity": 1.25, "insight": 1.15},
        "description": "A stable herbal base with room for complex restorative formulas.",
    },
    "Aether Matrix": {
        "cost": {"Crystal Shard": 1}, "capacity": 4, "stability": 5, "duration": 1.65,
        "affinities": {"focus": 1.3, "force": 1.25, "flame": 1.3, "frost": 1.3, "insight": 1.35, "shadow": 1.3},
        "description": "A crystalline suspension that greatly magnifies powerful, unstable properties.",
    },
    "Prismatic Matrix": {
        "cost": {"Ancient Fruit": 1, "Crystal Shard": 1},
        "capacity": 5, "stability": 7, "duration": 2.0,
        "affinities": {prop: 1.35 for prop in ALCHEMY_PROPERTIES},
        "description": "A rare adaptive matrix capable of carrying exceptionally strong mixtures.",
    },
}


def _ingredient(
    primary: str,
    potency: int,
    *,
    secondary: str = "",
    secondary_potency: int = 0,
    stability: int = 0,
    toxicity: int = 0,
    color: str = "Natural",
    note: str = "",
) -> Dict[str, object]:
    properties = {primary: int(potency)}
    if secondary and secondary_potency:
        properties[secondary] = int(secondary_potency)
    return {
        "properties": properties,
        "stability": int(stability),
        "toxicity": int(toxicity),
        "color": str(color),
        "description": str(note),
    }


ALCHEMY_INGREDIENT_DATA: Dict[str, Dict[str, object]] = {
    "Wild Herbs": _ingredient("vitality", 2, secondary="stability", secondary_potency=1, stability=2, note="Gentle restorative herbs that settle unruly mixtures."),
    "Cave Herbs": _ingredient("focus", 3, secondary="vitality", secondary_potency=1, stability=1, note="Mineral-fed herbs with a clear, cooling scent."),
    "Cave Mushroom": _ingredient("guard", 3, secondary="vitality", secondary_potency=1, toxicity=1, color="Walnut", note="Dense cave flesh that lends resilience."),
    "Strange Spores": _ingredient("focus", 4, secondary="growth", secondary_potency=2, toxicity=3, color="Royal", note="Powerful spores whose useful effects are difficult to stabilize."),
    "Wild Honey": _ingredient("vigor", 2, secondary="stability", secondary_potency=1, stability=2, color="Cherry", note="A binding sweetener that extends energetic effects."),
    "Watercress": _ingredient("vitality", 2, secondary="growth", secondary_potency=2, stability=1, color="Forest", note="Fresh waterside growth with balanced life properties."),
    "Wild Garlic": _ingredient("force", 2, secondary="guard", secondary_potency=1, stability=1, note="A sharp bulb used in bracing tonics."),
    "Marsh Reed": _ingredient("guard", 2, secondary="growth", secondary_potency=2, stability=2, color="Forest", note="Fibrous wetland material that reinforces a mixture."),
    "Pine Nuts": _ingredient("vigor", 3, secondary="guard", secondary_potency=1, stability=1, note="Concentrated woodland energy in a stable seed."),
    "Berries": _ingredient("vigor", 2, secondary="pigment", secondary_potency=2, color="Royal", note="Sweet fruit carrying energy and deep color."),
    "Wild Apple": _ingredient("vitality", 2, secondary="vigor", secondary_potency=2, stability=1, color="Cherry", note="A balanced restorative fruit."),
    "Wild Carrot": _ingredient("haste", 2, secondary="vigor", secondary_potency=1, stability=1, color="Cherry", note="A crisp root used for quickening draughts."),
    "Wildflowers": _ingredient("pigment", 3, secondary="focus", secondary_potency=1, color="Royal", note="Petals valued for both color and delicate mental effects."),
    "Wildflower": _ingredient("pigment", 3, secondary="focus", secondary_potency=1, color="Royal", note="Petals valued for both color and delicate mental effects."),
    "Sap": _ingredient("stability", 2, secondary="growth", secondary_potency=1, stability=3, color="Walnut", note="A strong natural binder."),
    "Bat Guano": _ingredient("growth", 5, secondary="force", secondary_potency=1, toxicity=4, color="Walnut", note="Extremely fertile cave material, unsuitable for careless drinking."),
    "Bat Wing": _ingredient("haste", 4, secondary="focus", secondary_potency=1, toxicity=2, color="Walnut", note="A light membrane associated with speed and awareness."),
    "Feather": _ingredient("haste", 2, secondary="focus", secondary_potency=1, stability=1, color="Whitewashed", note="A mild lightening agent."),
    "Antler": _ingredient("force", 4, secondary="guard", secondary_potency=2, stability=1, note="A hard natural material carrying strength and endurance."),
    "Quartz": _ingredient("focus", 3, secondary="stability", secondary_potency=1, stability=2, color="Whitewashed", note="A clean mineral lens for precise mixtures."),
    "Amethyst": _ingredient("focus", 5, secondary="guard", secondary_potency=1, stability=1, color="Royal", note="A rare mineral with strong concentration properties."),
    "Topaz": _ingredient("flame", 5, secondary="force", secondary_potency=2, stability=1, color="Cherry", note="A warm mineral that amplifies heat and force."),
    "Crystal Shard": _ingredient("frost", 4, secondary="focus", secondary_potency=2, toxicity=1, color="Ocean", note="A cold resonant shard useful in elemental compounds."),
    "Coal": _ingredient("flame", 3, secondary="pigment", secondary_potency=2, toxicity=2, color="Walnut", note="A smoky fuel and dark pigment source."),
    "Ancient Fruit": _ingredient("vitality", 7, secondary="growth", secondary_potency=5, stability=2, color="Royal", note="An exceptionally potent fruit carrying old, concentrated life."),
    "Ancient Seed": _ingredient("growth", 7, secondary="vitality", secondary_potency=3, stability=1, color="Forest", note="A rare seed with extraordinary growth potential."),
    "Dust Silk": _ingredient("haste", 5, secondary="guard", secondary_potency=2, stability=2, color="Whitewashed", note="Fine relic silk that makes mixtures light but cohesive."),
    "Relic Fragment": _ingredient("force", 5, secondary="focus", secondary_potency=3, toxicity=2, color="Royal", note="Old worked material holding a stubborn residual charge."),
}


def _generated_ingredient_profile(name: str, category: str) -> Dict[str, object]:
    """Give every raw crop and wilderness material a useful, legible identity."""
    lower = str(name).lower()
    potency = 3 if category == "biome" else 2
    primary, secondary = "growth", "vitality"
    color = "Forest"
    toxicity = 0
    stability = 1 if category in {"crop", "animal"} else 0

    if any(word in lower for word in ("berry", "fruit", "date", "coconut", "cranberry", "grape", "melon")):
        primary, secondary, color = "fortune", "vigor", "Royal"
    elif (
        any(word in lower for word in ("flower", "petal", "bloom", "marigold", "buttercup", "hibiscus", "coneflower", "verbena"))
        and not any(word in lower for word in ("frost", "snow", "winter", "edelweiss"))
    ):
        primary, secondary, color = "pigment", "insight", "Royal"
    elif any(word in lower for word in ("mushroom", "morel", "lichen", "spore")):
        primary, secondary, color, toxicity = "shadow", "focus", "Walnut", 1
    elif any(word in lower for word in ("frost", "snow", "winter", "crystal", "saxifrage", "edelweiss")):
        primary, secondary, color = "frost", "purity", "Ocean"
    elif any(word in lower for word in ("mint", "thyme", "sage", "yarrow", "herb", "gentian", "juniper")):
        primary, secondary, color = "insight", "purity", "Forest"
    elif any(word in lower for word in ("aloe", "watercress", "algae", "eelgrass", "glasswort", "purslane", "cattail")):
        primary, secondary, color = "purity", "vitality", "Ocean"
    elif any(word in lower for word in ("pepper", "cactus", "agave", "saltbush", "greasewood", "garlic")):
        primary, secondary, color = "flame", "force", "Cherry"
    elif any(word in lower for word in ("root", "yam", "beet", "carrot", "turnip", "parsnip", "onion", "leek", "potato")):
        primary, secondary, color = "guard", "vitality", "Walnut"
    elif any(word in lower for word in ("bark", "burl", "fiber", "reed", "switch", "twig", "resin", "gum", "peat")):
        primary, secondary, color, stability = "guard", "growth", "Walnut", 2
    elif any(word in lower for word in ("grain", "wheat", "corn", "pea", "nut", "seed")):
        primary, secondary, color = "vigor", "growth", "Cherry"
    elif any(word in lower for word in ("milk", "egg", "honey")):
        primary, secondary, color, stability = "vitality", "vigor", "Whitewashed", 2
    elif any(word in lower for word in ("holly", "gorse", "heather")):
        primary, secondary, color = "shadow", "guard", "Royal"
    elif any(word in lower for word in ("vanilla", "clover")):
        primary, secondary, color = "fortune", "focus", "Whitewashed"

    return _ingredient(
        primary,
        potency,
        secondary=secondary,
        secondary_potency=max(1, potency - 1),
        stability=stability,
        toxicity=toxicity,
        color=color,
        note=f"A raw {category} ingredient carrying {primary} and {secondary} properties.",
    )


def _register_world_ingredients() -> None:
    crop_names = tuple(str(name) for name in CROP_DATA)
    forage_names = tuple(
        str(record.get("item", ""))
        for record in WILDERNESS_FORAGE_DATA.values()
        if isinstance(record, Mapping) and str(record.get("item", ""))
    )
    biome_names = tuple(
        str(name)
        for identity in BIOME_IDENTITY_DATA.values()
        if isinstance(identity, Mapping)
        for name in tuple(identity.get("gatherables", ()))
        if str(name)
    )
    raw_animal_products = (
        "Bird Egg", "Large Bird Egg", "Duck Egg", "Large Duck Egg",
        "Milk", "Large Milk", "Goat Milk", "Large Goat Milk", "Wool",
        "Honey", "Wild Honey",
    )
    for category, names in (
        ("crop", crop_names), ("forage", forage_names),
        ("biome", biome_names), ("animal", raw_animal_products),
    ):
        for name in names:
            ALCHEMY_INGREDIENT_DATA.setdefault(name, _generated_ingredient_profile(name, category))
            if category == "crop":
                base = ALCHEMY_INGREDIENT_DATA[name]
                for prefix, bonus in (("Silver", 1), ("Gold", 2)):
                    quality_name = f"{prefix} {name}"
                    quality_record = dict(base)
                    quality_record["properties"] = {
                        str(prop): int(amount) + bonus
                        for prop, amount in dict(base.get("properties", {})).items()
                    }
                    quality_record["description"] = (
                        f"A {prefix.lower()}-quality crop whose alchemical properties are more concentrated."
                    )
                    ALCHEMY_INGREDIENT_DATA.setdefault(quality_name, quality_record)


_register_world_ingredients()


ALCHEMY_FINISH_DATA: Dict[str, Dict[str, object]] = {
    "potion": {"label": "Bottle as potion", "noun": "Elixir", "matrices": tuple(ALCHEMY_MATRIX_DATA)},
    "oil": {"label": "Prepare equipment oil", "noun": "Tempering Oil", "matrices": ("Oil Matrix", "Spirit Matrix", "Aether Matrix", "Prismatic Matrix")},
    "bomb": {"label": "Seal as thrown flask", "noun": "Flask", "matrices": ("Oil Matrix", "Spirit Matrix", "Aether Matrix", "Prismatic Matrix")},
    "fertilizer": {"label": "Bind as soil treatment", "noun": "Soil Tonic", "matrices": ("Water Matrix", "Tonic Matrix", "Prismatic Matrix")},
    "pigment": {"label": "Set as furniture pigment", "noun": "Pigment", "matrices": ("Oil Matrix", "Spirit Matrix", "Aether Matrix", "Prismatic Matrix")},
}


PROPERTY_NAMES = {
    "vitality": "Mending", "vigor": "Vigor", "focus": "Clarity",
    "force": "Fury", "guard": "Ironbark", "haste": "Quickstep",
    "flame": "Ember", "frost": "Rime", "growth": "Verdant",
    "pigment": "Chromatic", "fortune": "Fortune", "shadow": "Veiled",
    "insight": "Keeneye", "purity": "Purewell",
}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def formula_signature(matrix: object, ingredients: Sequence[object], kind: object) -> str:
    source = "|".join((str(matrix), str(kind), *sorted(str(item) for item in ingredients)))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def available_finish_ids(matrix: object) -> List[str]:
    name = str(matrix)
    return [
        finish_id for finish_id, record in ALCHEMY_FINISH_DATA.items()
        if name in tuple(record.get("matrices", ()))
    ]


def matrix_cost_text(matrix: object) -> str:
    cost = ALCHEMY_MATRIX_DATA.get(str(matrix), {}).get("cost", {})
    if not isinstance(cost, Mapping) or not cost:
        return "water supplied at the table"
    return ", ".join(quantity_item_phrase(name, qty) for name, qty in cost.items())


def can_pay_cost(inventory: Mapping[str, int], cost: Mapping[str, int]) -> bool:
    return all(_safe_int(inventory.get(str(name), 0)) >= max(0, _safe_int(qty)) for name, qty in cost.items())


def _consume_inventory_item(inventory: Dict[str, int], item_name: str, quantity: int) -> int:
    available = max(0, _safe_int(inventory.get(str(item_name), 0)))
    taken = min(available, max(0, _safe_int(quantity)))
    inventory[str(item_name)] = available - taken
    return taken


def mixture_preview(matrix: object, ingredients: Sequence[object], kind: object) -> Dict[str, object]:
    matrix_name = str(matrix)
    finish_id = str(kind)
    matrix_data = ALCHEMY_MATRIX_DATA.get(matrix_name, ALCHEMY_MATRIX_DATA["Water Matrix"])
    affinity = matrix_data.get("affinities", {}) if isinstance(matrix_data.get("affinities"), Mapping) else {}
    totals = {prop: 0.0 for prop in ALCHEMY_PROPERTIES}
    stability = _safe_int(matrix_data.get("stability", 5), 5)
    toxicity = 0
    colors: List[str] = []
    valid_ingredients: List[str] = []
    for raw_name in sorted(str(item) for item in ingredients):
        name = str(raw_name)
        ingredient = ALCHEMY_INGREDIENT_DATA.get(name)
        if not ingredient:
            continue
        valid_ingredients.append(name)
        props = ingredient.get("properties", {})
        if isinstance(props, Mapping):
            for prop, amount in props.items():
                if prop == "stability":
                    stability += _safe_int(amount)
                elif prop in totals:
                    totals[prop] += float(amount) * float(affinity.get(prop, 1.0))
        stability += _safe_int(ingredient.get("stability", 0))
        toxicity += _safe_int(ingredient.get("toxicity", 0))
        color = str(ingredient.get("color", "Natural"))
        if color != "Natural":
            colors.append(color)

    complexity = max(0, len(valid_ingredients) - 2)
    stability -= complexity
    if totals["flame"] and totals["frost"]:
        stability -= 3
    toxicity = max(0, toxicity - max(0, stability // 5))
    rounded = {prop: max(0, int(round(value))) for prop, value in totals.items()}
    ranked = sorted(rounded.items(), key=lambda pair: (-pair[1], ALCHEMY_PROPERTIES.index(pair[0])))
    dominant = ranked[0][0] if ranked and ranked[0][1] > 0 else "vitality"
    potency = max(1, ranked[0][1] if ranked else 1)
    duration = max(30, int((45 + sum(rounded.values()) * 8) * float(matrix_data.get("duration", 1.0))))
    grade = "Crude"
    if potency >= 13:
        grade = "Prismatic"
    elif potency >= 10:
        grade = "Grand"
    elif potency >= 7:
        grade = "Potent"
    elif potency >= 4:
        grade = "Balanced"
    color = colors[-1] if colors else {
        "flame": "Cherry", "frost": "Ocean", "growth": "Forest",
        "focus": "Royal", "guard": "Walnut",
    }.get(dominant, "Whitewashed")
    noun = str(ALCHEMY_FINISH_DATA.get(finish_id, ALCHEMY_FINISH_DATA["potion"])["noun"])
    signature = formula_signature(matrix_name, valid_ingredients, finish_id)
    name = f"{grade} {PROPERTY_NAMES.get(dominant, dominant.title())} {noun}"
    effects = {
        "heal": rounded["vitality"] * 4 + rounded["growth"],
        "stamina": rounded["vigor"] * 5 + rounded["haste"] * 2,
        "focus_restore": rounded["focus"] * 3,
        "attack": max(0, rounded["force"] // 2 + rounded["flame"] // 3),
        "defense": max(0, rounded["guard"] // 2 + rounded["frost"] // 3),
        "max_hp": max(0, rounded["vitality"] // 2),
        "max_focus": max(0, rounded["focus"] // 2),
        "stamina_discount": max(0, min(4, (rounded["haste"] + rounded["vigor"] // 2) // 3)),
        "regeneration": max(0, min(6, (rounded["vitality"] + rounded["growth"] + rounded["purity"]) // 4)),
        "elemental_resistance": max(0, min(12, (rounded["guard"] + rounded["frost"] + rounded["flame"] + rounded["purity"]) // 4)),
        "poison_resistance": max(0, min(80, (rounded["purity"] * 8 + rounded["guard"] * 3))),
        "luck": max(0, min(20, (rounded["fortune"] * 2 + rounded["insight"]) // 2)),
        "loot_quality": max(0, min(5, (rounded["fortune"] + rounded["insight"]) // 4)),
        "stealth": max(0, min(6, (rounded["shadow"] * 2 + rounded["haste"]) // 3)),
        "critical_chance": max(0, min(25, (rounded["insight"] * 2 + rounded["force"] + rounded["fortune"]) // 3)),
        "farming_speed": max(0, min(3, (rounded["growth"] + rounded["haste"] + rounded["insight"]) // 4)),
        "movement_speed": max(0, min(3, (rounded["haste"] + rounded["shadow"] + rounded["vigor"]) // 4)),
        "armor_pierce": max(0, min(4, (rounded["force"] + rounded["insight"]) // 5)),
        "forage_yield": max(0, min(2, (rounded["growth"] + rounded["fortune"]) // 5)),
        "bomb_damage": max(1, rounded["force"] * 2 + rounded["flame"] * 2 + rounded["frost"] * 2 + potency),
        "fertilizer_strength": max(1, min(4, (rounded["growth"] + rounded["vitality"] // 2 + 2) // 3)),
    }
    value = max(20, min(5000, 20 + sum(rounded.values()) * 12 + len(valid_ingredients) * 15 + (120 if matrix_name in {"Aether Matrix", "Prismatic Matrix"} else 0)))
    instability = max(0, toxicity - stability)
    return {
        "schema": ALCHEMY_SCHEMA_VERSION,
        "id": f"alchemy:{signature}", "signature": signature, "name": name,
        "kind": finish_id, "matrix": matrix_name, "ingredients": valid_ingredients,
        "properties": rounded, "effects": effects, "dominant": dominant,
        "potency": potency, "duration": duration, "stability": max(0, stability),
        "toxicity": toxicity, "instability": instability, "grade": grade,
        "color": color, "value": value,
        "description": mixture_description(finish_id, dominant, effects, duration, instability),
    }


def mixture_description(kind: str, dominant: str, effects: Mapping[str, int], duration: int, instability: int) -> str:
    if kind == "potion":
        text = "A drinkable mixture"
    elif kind == "oil":
        text = "A temporary coating for one equipped weapon, armor piece, or accessory"
    elif kind == "bomb":
        text = "A thrown compound that damages nearby hostile creatures and alters exposed terrain"
    elif kind == "fertilizer":
        text = "A concentrated soil treatment that improves crop care and quality"
    else:
        text = "A durable pigment for recoloring player-owned furniture"
    warning = f" It is unstable enough to cause {instability} backlash." if instability else ""
    return f"{text}, led by {PROPERTY_NAMES.get(dominant, dominant)} properties. Effective for about {duration} minutes where applicable.{warning}"


def product_effect_lines(product: Mapping[str, object]) -> List[str]:
    effects = product.get("effects", {}) if isinstance(product.get("effects"), Mapping) else {}
    kind = str(product.get("kind", "potion"))
    rows = [
        f"Form: {kind.title()} | Grade: {product.get('grade', 'Crude')}",
        f"Matrix: {product.get('matrix', 'Water Matrix')}",
        "Ingredients: " + ", ".join(str(item) for item in product.get("ingredients", []) or []),
        f"Potency {product.get('potency', 1)} | Stability {product.get('stability', 0)} | Toxicity {product.get('toxicity', 0)}",
    ]
    if kind == "potion":
        labels = (("heal", "HP"), ("stamina", "stamina"), ("focus_restore", "focus"))
        recovery = [f"+{_safe_int(effects.get(key))} {label}" for key, label in labels if _safe_int(effects.get(key)) > 0]
        buffs = [f"{key.replace('_', ' ')} +{_safe_int(effects.get(key))}" for key in ("attack", "defense", "max_hp", "max_focus") if _safe_int(effects.get(key)) > 0]
        if _safe_int(effects.get("stamina_discount")) > 0:
            buffs.append(f"stamina costs -{_safe_int(effects.get('stamina_discount'))}")
        effect_labels = (
            ("regeneration", "regeneration"),
            ("elemental_resistance", "elemental resistance"),
            ("poison_resistance", "poison resistance %"),
            ("luck", "luck %"),
            ("loot_quality", "loot quality"),
            ("stealth", "concealment"),
            ("critical_chance", "critical chance %"),
            ("farming_speed", "farming efficiency"),
            ("movement_speed", "movement speed"),
            ("armor_pierce", "armor penetration"),
            ("forage_yield", "bonus forage"),
        )
        buffs.extend(
            f"{label} +{_safe_int(effects.get(key))}"
            for key, label in effect_labels
            if _safe_int(effects.get(key)) > 0
        )
        if recovery:
            rows.append("Immediate: " + ", ".join(recovery))
        if buffs:
            rows.append(f"For {product.get('duration', 30)} minutes: " + ", ".join(buffs))
    elif kind == "oil":
        oil_bits = [
            f"attack +{_safe_int(effects.get('attack'))}",
            f"defense +{_safe_int(effects.get('defense'))}",
            f"focus +{_safe_int(effects.get('max_focus'))}",
        ]
        for key, label in (
            ("elemental_resistance", "elemental resistance"),
            ("critical_chance", "critical chance %"),
            ("armor_pierce", "armor penetration"),
        ):
            if _safe_int(effects.get(key)) > 0:
                oil_bits.append(f"{label} +{_safe_int(effects.get(key))}")
        rows.append(
            f"Equipment bonus for {product.get('duration', 30)} minutes: "
            + ", ".join(oil_bits) + "."
        )
    elif kind == "bomb":
        rows.append(f"Blast damage: {_safe_int(effects.get('bomb_damage'), 1)} | Element: {product.get('dominant', 'force')}")
    elif kind == "fertilizer":
        rows.append(f"Soil strength: {_safe_int(effects.get('fertilizer_strength'), 1)}")
    elif kind == "pigment":
        rows.append(f"Furniture finish: {product.get('color', 'Natural')}")
    if _safe_int(product.get("instability")) > 0:
        rows.append(f"Backlash on use: {_safe_int(product.get('instability'))}")
    rows.extend(["", str(product.get("description", "An alchemical mixture."))])
    return rows


def sanitize_alchemy_products(value: object) -> Dict[str, Dict[str, object]]:
    clean: Dict[str, Dict[str, object]] = {}
    if not isinstance(value, Mapping):
        return clean
    for raw_name, raw_record in value.items():
        if not isinstance(raw_record, Mapping):
            continue
        matrix = str(raw_record.get("matrix", ""))
        kind = str(raw_record.get("kind", ""))
        ingredients = [str(item) for item in raw_record.get("ingredients", []) or [] if str(item) in ALCHEMY_INGREDIENT_DATA]
        if matrix not in ALCHEMY_MATRIX_DATA or kind not in ALCHEMY_FINISH_DATA or not ingredients:
            continue
        rebuilt = mixture_preview(matrix, ingredients, kind)
        name = str(raw_name or rebuilt["name"]).strip()[:96]
        rebuilt["name"] = name
        clean[name] = rebuilt
    return clean


def sanitize_alchemy_formulas(value: object) -> Dict[str, Dict[str, object]]:
    clean: Dict[str, Dict[str, object]] = {}
    if not isinstance(value, Mapping):
        return clean
    for _raw_key, raw_record in value.items():
        if not isinstance(raw_record, Mapping):
            continue
        matrix = str(raw_record.get("matrix", ""))
        kind = str(raw_record.get("kind", ""))
        ingredients = [str(item) for item in raw_record.get("ingredients", []) or [] if str(item) in ALCHEMY_INGREDIENT_DATA]
        if matrix not in ALCHEMY_MATRIX_DATA or kind not in ALCHEMY_FINISH_DATA or not ingredients:
            continue
        product = mixture_preview(matrix, ingredients, kind)
        signature = str(product["signature"])
        clean[signature] = {
            "signature": signature, "matrix": matrix, "ingredients": ingredients,
            "kind": kind, "name": str(raw_record.get("name", product["name"]))[:96],
            "times_brewed": max(1, min(9999, _safe_int(raw_record.get("times_brewed", 1), 1))),
        }
    return clean


def sanitize_active_alchemy_effects(value: object) -> Dict[str, Dict[str, object]]:
    clean: Dict[str, Dict[str, object]] = {}
    if not isinstance(value, Mapping):
        return clean
    for raw_key, raw_record in value.items():
        if not isinstance(raw_record, Mapping):
            continue
        remaining = max(0, min(10080, _safe_int(raw_record.get("remaining_minutes", 0))))
        effects = raw_record.get("effects", {})
        if remaining <= 0 or not isinstance(effects, Mapping):
            continue
        clean[str(raw_key)[:96]] = {
            "name": str(raw_record.get("name", raw_key))[:96],
            "remaining_minutes": remaining,
            "effects": {
                key: max(0, min(99, _safe_int(effects.get(key, 0))))
                for key in TIMED_ALCHEMY_EFFECT_KEYS
            },
        }
    return clean


def sanitize_equipment_oils(value: object) -> Dict[str, Dict[str, object]]:
    clean = sanitize_active_alchemy_effects(value)
    for item_name, record in clean.items():
        record["equipment"] = str((value.get(item_name, {}) if isinstance(value, Mapping) else {}).get("equipment", item_name))[:96]
    return clean


def alchemy_combat_bonuses(state: object) -> Dict[str, int]:
    result = {
        "attack": 0, "defense": 0, "max_hp": 0, "max_focus": 0,
        "elemental_resistance": 0, "poison_resistance": 0,
        "critical_chance": 0, "armor_pierce": 0,
    }
    effects = sanitize_active_alchemy_effects(getattr(state, "active_alchemy_effects", {}))
    for record in effects.values():
        bonuses = record.get("effects", {})
        for key in result:
            result[key] += _safe_int(bonuses.get(key, 0))
    equipped = {
        str(getattr(state, "equipped_weapon", "")),
        str(getattr(state, "equipped_armor", "")),
        str(getattr(state, "equipped_accessory", "")),
    }
    oils = sanitize_equipment_oils(getattr(state, "equipment_oils", {}))
    for record in oils.values():
        if str(record.get("equipment", "")) not in equipped:
            continue
        bonuses = record.get("effects", {})
        for key in result:
            result[key] += _safe_int(bonuses.get(key, 0))
    caps = {
        "attack": 30, "defense": 30, "max_hp": 80, "max_focus": 80,
        "elemental_resistance": 20, "poison_resistance": 90,
        "critical_chance": 35, "armor_pierce": 6,
    }
    return {key: min(caps.get(key, 99), value) for key, value in result.items()}


def alchemy_effect_value(state: object, effect_name: object) -> int:
    """Return the stacked value of one currently active potion effect."""
    key = str(effect_name)
    if key not in TIMED_ALCHEMY_EFFECT_KEYS:
        return 0
    total = 0
    effects = getattr(state, "active_alchemy_effects", {})
    if not isinstance(effects, Mapping):
        return 0
    for record in effects.values():
        if not isinstance(record, Mapping) or _safe_int(record.get("remaining_minutes")) <= 0:
            continue
        values = record.get("effects", {})
        if isinstance(values, Mapping):
            total += max(0, _safe_int(values.get(key, 0)))
    caps = {
        "stamina_discount": 4, "regeneration": 8, "elemental_resistance": 20,
        "poison_resistance": 90, "luck": 30, "loot_quality": 8,
        "stealth": 8, "critical_chance": 35, "farming_speed": 4,
        "movement_speed": 3, "armor_pierce": 6, "forage_yield": 3,
    }
    return min(caps.get(key, 99), total)


def break_alchemy_stealth(state: object) -> bool:
    """Remove concealment when the player takes an overtly hostile action."""
    changed = False
    store = getattr(state, "active_alchemy_effects", {})
    if not isinstance(store, dict):
        return False
    for record in store.values():
        effects = record.get("effects", {}) if isinstance(record, dict) else {}
        if isinstance(effects, dict) and _safe_int(effects.get("stealth")) > 0:
            effects["stealth"] = 0
            changed = True
    return changed


class AlchemyMixin:
    """FarmGame-facing menus and concrete uses for generated mixtures."""

    def ensure_alchemy_state(self) -> None:
        if not isinstance(getattr(self.state, "alchemy_products", None), dict):
            self.state.alchemy_products = {}
        if not isinstance(getattr(self.state, "alchemy_formulas", None), dict):
            self.state.alchemy_formulas = {}
        if not isinstance(getattr(self.state, "active_alchemy_effects", None), dict):
            self.state.active_alchemy_effects = {}
        if not isinstance(getattr(self.state, "equipment_oils", None), dict):
            self.state.equipment_oils = {}
        if not isinstance(getattr(self.state, "alchemy_discovered_ingredients", None), list):
            self.state.alchemy_discovered_ingredients = []
        self.state.alchemy_discovered_ingredients = [
            name for name in dict.fromkeys(str(item) for item in self.state.alchemy_discovered_ingredients)
            if name in ALCHEMY_INGREDIENT_DATA
        ]
        self.state.alchemy_brew_count = max(0, _safe_int(getattr(self.state, "alchemy_brew_count", 0)))

    def alchemy_product(self, item_name: object) -> Optional[Dict[str, object]]:
        if not isinstance(getattr(self.state, "alchemy_products", None), dict):
            self.ensure_alchemy_state()
        record = self.state.alchemy_products.get(str(item_name))
        return record if isinstance(record, dict) else None

    def alchemy_product_value(self, item_name: object) -> int:
        product = self.alchemy_product(item_name)
        return max(0, _safe_int(product.get("value", 0))) if product else 0

    def alchemy_product_lines(self, item_name: object) -> List[str]:
        product = self.alchemy_product(item_name)
        return product_effect_lines(product) if product else []

    def alchemy_product_hint(self, item_name: object) -> str:
        product = self.alchemy_product(item_name)
        if not product:
            return ""
        kind = str(product.get("kind", "potion"))
        effects = product.get("effects", {})
        if kind == "potion":
            bits = []
            for key, label in (("heal", "HP"), ("stamina", "stamina"), ("focus_restore", "focus")):
                if _safe_int(effects.get(key)):
                    bits.append(f"+{_safe_int(effects.get(key))} {label}")
            if any(_safe_int(effects.get(key)) for key in TIMED_ALCHEMY_EFFECT_KEYS):
                bits.append("timed buff")
            return ", ".join(bits) or "drink"
        if kind == "oil":
            return f"coat gear for {product.get('duration', 30)} min"
        if kind == "bomb":
            return f"face target, {_safe_int(effects.get('bomb_damage'), 1)} blast damage"
        if kind == "fertilizer":
            return f"face crop or soil, strength {_safe_int(effects.get('fertilizer_strength'), 1)}"
        return f"face owned furniture, {product.get('color', 'Natural')} finish"

    def alchemy_formula_cost(self, matrix: str, ingredients: Sequence[str]) -> Dict[str, int]:
        cost: Dict[str, int] = {}
        matrix_cost = ALCHEMY_MATRIX_DATA.get(matrix, {}).get("cost", {})
        if isinstance(matrix_cost, Mapping):
            for item, qty in matrix_cost.items():
                cost[str(item)] = cost.get(str(item), 0) + _safe_int(qty)
        for ingredient in ingredients:
            cost[str(ingredient)] = cost.get(str(ingredient), 0) + 1
        return cost

    def alchemy_can_brew(self, matrix: str, ingredients: Sequence[str]) -> Tuple[bool, str]:
        if matrix not in ALCHEMY_MATRIX_DATA:
            return False, "unknown matrix"
        if not ingredients:
            return False, "add at least one ingredient"
        capacity = _safe_int(ALCHEMY_MATRIX_DATA[matrix].get("capacity", 3), 3)
        if len(ingredients) > capacity:
            return False, f"matrix holds {capacity} ingredients"
        cost = self.alchemy_formula_cost(matrix, ingredients)
        missing = [quantity_item_phrase(item, qty - _safe_int(self.state.inventory.get(item, 0))) for item, qty in cost.items() if _safe_int(self.state.inventory.get(item, 0)) < qty]
        return (False, "missing " + ", ".join(missing)) if missing else (True, "ready")

    def alchemy_unique_product_name(self, product: Mapping[str, object]) -> str:
        base = str(product.get("name", "Alchemical Mixture"))[:86]
        existing = self.state.alchemy_products.get(base)
        if not isinstance(existing, Mapping) or str(existing.get("signature", "")) == str(product.get("signature", "")):
            return base
        return f"{base} [{str(product.get('signature', 'mix'))[:4]}]"

    def brew_alchemy_formula(self, matrix: str, ingredients: Sequence[str], kind: str) -> bool:
        self.ensure_alchemy_state()
        if kind not in available_finish_ids(matrix):
            self.set_message("That matrix cannot hold the selected finish.")
            return False
        ok, reason = self.alchemy_can_brew(matrix, ingredients)
        if not ok:
            self.set_message(f"Cannot brew: {reason}.")
            return False
        product = mixture_preview(matrix, ingredients, kind)
        item_name = self.alchemy_unique_product_name(product)
        product["name"] = item_name
        cost = self.alchemy_formula_cost(matrix, ingredients)
        for ingredient, qty in cost.items():
            if _consume_inventory_item(self.state.inventory, ingredient, qty) < qty:
                self.set_message("The ingredients changed before the batch could be finished.")
                return False
        self.state.alchemy_products[item_name] = dict(product)
        self.state.inventory[item_name] = _safe_int(self.state.inventory.get(item_name, 0)) + 1
        signature = str(product["signature"])
        old = self.state.alchemy_formulas.get(signature, {})
        self.state.alchemy_formulas[signature] = {
            "signature": signature, "matrix": matrix, "ingredients": list(ingredients),
            "kind": kind, "name": item_name,
            "times_brewed": max(0, _safe_int(old.get("times_brewed", 0))) + 1,
        }
        for ingredient in ingredients:
            if ingredient not in self.state.alchemy_discovered_ingredients:
                self.state.alchemy_discovered_ingredients.append(ingredient)
        self.state.alchemy_brew_count += 1
        minutes = 20 + len(ingredients) * 10 + (10 if matrix in {"Aether Matrix", "Prismatic Matrix"} else 0)
        self.advance_time(minutes)
        self.autosave_with_message(f"Brewed {item_name} in {minutes} minutes. The formula was recorded.")
        return True

    def alchemy_select_matrix(self) -> object:
        items = []
        for name, data in ALCHEMY_MATRIX_DATA.items():
            cost = data.get("cost", {}) if isinstance(data.get("cost"), Mapping) else {}
            ready = can_pay_cost(self.state.inventory, cost)
            items.append(MenuItem(label=name, value=name, enabled=ready, hint=f"{matrix_cost_text(name)} | {data.get('capacity', 3)} ingredients"))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select("Choose Liquid Matrix", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        return MENU_BACK if choice is None else choice.value

    def alchemy_select_ingredients(self, matrix: str) -> object:
        selected: List[str] = []
        capacity = _safe_int(ALCHEMY_MATRIX_DATA[matrix].get("capacity", 3), 3)
        while True:
            candidates = [name for name in ALCHEMY_INGREDIENT_DATA if _safe_int(self.state.inventory.get(name, 0)) > selected.count(name)]
            items = [
                MenuItem(label=name, value=name, enabled=len(selected) < capacity, hint=f"x{self.state.inventory.get(name, 0)} | {', '.join(f'{prop} {amount:+d}' for prop, amount in ALCHEMY_INGREDIENT_DATA[name]['properties'].items())}")
                for name in candidates
            ]
            if selected:
                items.insert(0, MenuItem(label="Finish ingredient selection", value="__DONE__", enabled=True, hint=f"{len(selected)}/{capacity}: {', '.join(selected)}"))
                items.insert(1, MenuItem(label="Remove last ingredient", value="__REMOVE__", enabled=True, hint=selected[-1]))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(f"Ingredients ({len(selected)}/{capacity})", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                return MENU_BACK
            if choice.value == "__DONE__":
                return selected
            if choice.value == "__REMOVE__":
                selected.pop()
                continue
            if len(selected) < capacity:
                selected.append(str(choice.value))

    def alchemy_select_finish(self, matrix: str) -> object:
        items = [MenuItem(label=str(ALCHEMY_FINISH_DATA[kind]["label"]), value=kind, enabled=True) for kind in available_finish_ids(matrix)]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select("Finish the Mixture", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        return MENU_BACK if choice is None else choice.value

    def show_alchemy_preview(self, matrix: str, ingredients: Sequence[str], kind: str) -> bool:
        product = mixture_preview(matrix, ingredients, kind)
        cost = self.alchemy_formula_cost(matrix, ingredients)
        lines = [str(product["name"]), "", *product_effect_lines(product), "", "Consumed:", *[f"- {quantity_item_phrase(name, qty)}" for name, qty in cost.items()]]
        choice = self.vertical_panel_select(
            "Mixture Preview",
            [
                MenuItem(label="Brew this mixture", value="brew", enabled=True, hint=f"value ${product.get('value', 0)}"),
                MenuItem(label="View full analysis", value="details", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return False
        if choice.value == "details":
            self.vertical_panel_view("Mixture Analysis", lines, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return self.show_alchemy_preview(matrix, ingredients, kind)
        return self.brew_alchemy_formula(matrix, ingredients, kind)

    def show_alchemy_brew_menu(self) -> object:
        matrix = self.alchemy_select_matrix()
        if matrix == MENU_BACK:
            return MENU_BACK
        ingredients = self.alchemy_select_ingredients(str(matrix))
        if ingredients == MENU_BACK:
            return MENU_BACK
        kind = self.alchemy_select_finish(str(matrix))
        if kind == MENU_BACK:
            return MENU_BACK
        return "brewed" if self.show_alchemy_preview(str(matrix), list(ingredients), str(kind)) else MENU_BACK

    def show_alchemy_formula_book(self) -> None:
        self.ensure_alchemy_state()
        while True:
            formulas = sorted(self.state.alchemy_formulas.values(), key=lambda row: str(row.get("name", "")))
            items = [MenuItem(label=str(row.get("name", "Formula")), value=str(row.get("signature", "")), enabled=True, hint=f"brewed {row.get('times_brewed', 1)}x") for row in formulas]
            if not items:
                items.append(MenuItem(label="No formulas recorded", value="none", enabled=False, hint="brew at the table"))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Alchemy Formula Book", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                return
            formula = self.state.alchemy_formulas.get(str(choice.value), {})
            if not formula:
                continue
            matrix = str(formula.get("matrix", "Water Matrix"))
            ingredients = [str(item) for item in formula.get("ingredients", []) or []]
            kind = str(formula.get("kind", "potion"))
            product = mixture_preview(matrix, ingredients, kind)
            ok, reason = self.alchemy_can_brew(matrix, ingredients)
            action = self.vertical_panel_select(
                str(formula.get("name", "Formula")),
                [
                    MenuItem(label="Brew again", value="brew", enabled=ok, hint="ready" if ok else reason),
                    MenuItem(label="Review formula", value="details", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if action and action.value == "brew":
                self.brew_alchemy_formula(matrix, ingredients, kind)
                return
            if action and action.value == "details":
                self.vertical_panel_view("Formula", product_effect_lines(product), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)

    def show_alchemy_ingredient_notes(self) -> None:
        rows = ["INGREDIENT PROPERTIES", ""]
        owned_or_known = [name for name in ALCHEMY_INGREDIENT_DATA if _safe_int(self.state.inventory.get(name, 0)) > 0 or name in self.state.alchemy_discovered_ingredients]
        if not owned_or_known:
            rows.append("No alchemical ingredients identified yet. Gather herbs, forage, cave materials, and minerals.")
        for name in owned_or_known:
            data = ALCHEMY_INGREDIENT_DATA[name]
            properties = ", ".join(f"{prop} {amount:+d}" for prop, amount in data.get("properties", {}).items())
            rows.extend([f"{name} x{self.state.inventory.get(name, 0)} — {properties}", f"  {data.get('description', '')}"])
        self.vertical_panel_view("Ingredient Notes", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)

    def alchemy_active_effect_lines(self) -> List[str]:
        self.ensure_alchemy_state()
        rows = ["ACTIVE ALCHEMY", ""]
        for record in self.state.active_alchemy_effects.values():
            effects = record.get("effects", {}) if isinstance(record, Mapping) else {}
            strongest = sorted(
                (
                    (str(key).replace("_", " "), _safe_int(value))
                    for key, value in dict(effects).items()
                    if _safe_int(value) > 0
                ),
                key=lambda pair: (-pair[1], pair[0]),
            )[:4]
            detail = ", ".join(f"{name} +{value}" for name, value in strongest)
            rows.append(f"{record.get('name')}: {record.get('remaining_minutes')} minutes")
            if detail:
                rows.append(f"  {detail}")
        for record in self.state.equipment_oils.values():
            rows.append(f"{record.get('name')} on {record.get('equipment')}: {record.get('remaining_minutes')} minutes")
        if len(rows) == 2:
            rows.append("No active potion effects or equipment oils.")
        return rows

    def show_alchemy_table_menu(self) -> None:
        self.ensure_alchemy_state()
        while True:
            ingredient_count = sum(1 for name in ALCHEMY_INGREDIENT_DATA if _safe_int(self.state.inventory.get(name, 0)) > 0)
            choice = self.vertical_panel_select(
                "Alchemy Table",
                [
                    MenuItem(label="Brew a mixture", value="brew", enabled=ingredient_count > 0, hint=f"{ingredient_count} ingredient types carried" if ingredient_count else "gather ingredients"),
                    MenuItem(label="Formula book", value="formulas", enabled=bool(self.state.alchemy_formulas), hint=f"{len(self.state.alchemy_formulas)} discovered"),
                    MenuItem(label="Ingredient notes", value="ingredients", enabled=True, hint="properties and carried amounts"),
                    MenuItem(label="Active effects", value="effects", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                self.set_message("You step away from the alchemy table.")
                return
            if choice.value == "brew":
                if self.show_alchemy_brew_menu() == "brewed":
                    return
            elif choice.value == "formulas":
                self.show_alchemy_formula_book()
            elif choice.value == "ingredients":
                self.show_alchemy_ingredient_notes()
            elif choice.value == "effects":
                self.vertical_panel_view("Active Alchemy", self.alchemy_active_effect_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)

    def advance_alchemy_effects(self, minutes: int) -> None:
        self.ensure_alchemy_state()
        elapsed = max(0, _safe_int(minutes))
        if not elapsed:
            return
        for store_name in ("active_alchemy_effects", "equipment_oils"):
            store = getattr(self.state, store_name)
            expired = []
            for key, record in store.items():
                record["remaining_minutes"] = max(0, _safe_int(record.get("remaining_minutes")) - elapsed)
                if record["remaining_minutes"] <= 0:
                    expired.append(key)
            for key in expired:
                store.pop(key, None)

    def alchemy_stamina_discount(self) -> int:
        self.ensure_alchemy_state()
        return alchemy_effect_value(self.state, "stamina_discount")

    def alchemy_effect_value(self, effect_name: object) -> int:
        self.ensure_alchemy_state()
        return alchemy_effect_value(self.state, effect_name)

    def break_alchemy_stealth(self) -> bool:
        self.ensure_alchemy_state()
        return break_alchemy_stealth(self.state)

    def alchemy_effect_summary(self) -> str:
        self.ensure_alchemy_state()
        bits = [f"{record.get('name')} {record.get('remaining_minutes')}m" for record in self.state.active_alchemy_effects.values()]
        bits.extend(f"Oil:{record.get('equipment')} {record.get('remaining_minutes')}m" for record in self.state.equipment_oils.values())
        return ", ".join(bits[:3])

    def alchemy_apply_backlash(self, product: Mapping[str, object]) -> str:
        backlash = max(0, _safe_int(product.get("instability", 0)))
        if backlash <= 0:
            return ""
        hp_loss = min(max(0, _safe_int(self.state.combat_current_hp) - 1), backlash * 2)
        stamina_loss = min(max(0, _safe_int(self.state.stamina)), backlash * 3)
        self.state.combat_current_hp -= hp_loss
        self.state.stamina -= stamina_loss
        return f" Instability caused {hp_loss} HP and {stamina_loss} stamina backlash."

    def alchemy_use_potion(self, item_name: str, product: Mapping[str, object]) -> bool:
        effects = product.get("effects", {}) if isinstance(product.get("effects"), Mapping) else {}
        before_hp = _safe_int(self.state.combat_current_hp)
        before_stamina = _safe_int(self.state.stamina)
        before_focus = _safe_int(self.state.combat_focus)
        bonuses = alchemy_combat_bonuses(self.state)
        max_hp = max(before_hp, _safe_int(self.state.combat_max_hp) + _safe_int(bonuses.get("max_hp")))
        max_focus = max(before_focus, _safe_int(self.state.combat_max_focus) + _safe_int(bonuses.get("max_focus")))
        self.state.combat_current_hp = min(max_hp, before_hp + _safe_int(effects.get("heal")))
        self.restore_stamina(_safe_int(effects.get("stamina")))
        self.state.combat_focus = min(max_focus, before_focus + _safe_int(effects.get("focus_restore")))
        timed = {key: _safe_int(effects.get(key)) for key in TIMED_ALCHEMY_EFFECT_KEYS}
        if any(timed.values()):
            self.state.active_alchemy_effects[str(product.get("signature", item_name))] = {
                "name": item_name, "remaining_minutes": _safe_int(product.get("duration", 30), 30), "effects": timed,
            }
        self.state.inventory[item_name] -= 1
        backlash = self.alchemy_apply_backlash(product)
        recovered = []
        if self.state.combat_current_hp > before_hp:
            recovered.append(f"{self.state.combat_current_hp - before_hp} HP")
        if self.state.stamina > before_stamina:
            recovered.append(f"{self.state.stamina - before_stamina} stamina")
        if self.state.combat_focus > before_focus:
            recovered.append(f"{self.state.combat_focus - before_focus} focus")
        text = f"Drank {item_name}." + (f" Restored {', '.join(recovered)}." if recovered else "")
        if any(timed.values()):
            text += f" Its effects last {_safe_int(product.get('duration', 30))} minutes."
        self.autosave_with_message(text + backlash)
        return True

    def alchemy_use_oil(self, item_name: str, product: Mapping[str, object]) -> bool:
        equipment = [
            ("Weapon", str(self.state.equipped_weapon)),
            ("Armor", str(self.state.equipped_armor)),
            ("Accessory", str(self.state.equipped_accessory)),
        ]
        choice = self.vertical_panel_select(
            "Apply Equipment Oil",
            [*(MenuItem(label=f"{slot}: {name}", value=name, enabled=bool(name)) for slot, name in equipment), MenuItem(label="Back", value=MENU_BACK, enabled=True)],
            LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Kept the equipment oil.")
            return False
        target = str(choice.value)
        effects = product.get("effects", {}) if isinstance(product.get("effects"), Mapping) else {}
        bonuses = {
            key: _safe_int(effects.get(key))
            for key in (
                "attack", "defense", "max_hp", "max_focus",
                "elemental_resistance", "critical_chance", "armor_pierce",
            )
        }
        self.state.equipment_oils[target] = {
            "name": item_name, "equipment": target,
            "remaining_minutes": _safe_int(product.get("duration", 30), 30), "effects": bonuses,
        }
        self.state.inventory[item_name] -= 1
        self.autosave_with_message(f"Coated {target} with {item_name}; the bonuses last {product.get('duration', 30)} minutes." + self.alchemy_apply_backlash(product))
        return True

    def alchemy_use_bomb(self, item_name: str, product: Mapping[str, object]) -> bool:
        x, y = self.target_tile_pos()
        if not self.in_active_bounds(x, y):
            self.set_message("Face a visible target before throwing the flask.")
            return False
        effects = product.get("effects", {}) if isinstance(product.get("effects"), Mapping) else {}
        damage = max(1, _safe_int(effects.get("bomb_damage", 1), 1))
        radius = 1 if _safe_int(product.get("potency", 1)) >= 7 else 0
        hits = 0
        defeated = 0
        terrain_changed = 0
        dominant = str(product.get("dominant", "force"))
        for ty in range(y - radius, y + radius + 1):
            for tx in range(x - radius, x + radius + 1):
                if abs(tx - x) + abs(ty - y) > radius or not self.in_active_bounds(tx, ty):
                    continue
                enemy = self.map_combat_enemy_at(tx, ty) if hasattr(self, "map_combat_enemy_at") else None
                if enemy:
                    enemy = self.ensure_dungeon_roguelike_enemy(enemy)
                    enemy["hp"] = max(0, _safe_int(enemy.get("hp", 1), 1) - damage)
                    hits += 1
                    if enemy["hp"] <= 0:
                        self.wilderness_field_defeat_enemy(enemy, attacker=item_name)
                        defeated += 1
                if hasattr(self, "world_magic_tile_context") and self.world_magic_tile_context(tx, ty) is not None and not self.world_magic_tile_protected(tx, ty):
                    tile = str(self.active_map()[ty][tx])
                    if dominant == "flame" and tile != "~":
                        self.world_magic_set_effect(tx, ty, "fire", 60 + damage * 3, item_name, original_tile=tile)
                        terrain_changed += 1
                    elif dominant == "frost" and tile == "~":
                        self.world_magic_set_effect(tx, ty, "ice", 90 + damage * 3, item_name, original_tile=tile)
                        terrain_changed += 1
                    elif dominant in {"vitality", "growth"}:
                        self.world_magic_set_effect(tx, ty, "growth", 90 + damage * 2, item_name, original_tile=tile)
                        terrain_changed += 1
        if not hits and not terrain_changed:
            self.set_message("There is nothing there for this flask to affect.")
            return False
        break_alchemy_stealth(self.state)
        self.state.inventory[item_name] -= 1
        self.advance_time(1)
        result = f"Threw {item_name}: {quantity_agreement(hits, 'hostile target')} hit"
        if defeated:
            result += f", {defeated} defeated"
        if terrain_changed:
            result += f", {quantity_agreement(terrain_changed, 'terrain tile')} changed"
        self.autosave_with_message(result + "." + self.alchemy_apply_backlash(product))
        return True

    def alchemy_use_fertilizer(self, item_name: str, product: Mapping[str, object]) -> bool:
        if not self.on_farm_work_land():
            self.set_message("Soil treatment can only be used on owned farm land.")
            return False
        x, y = self.target_tile_pos()
        if not self.in_active_bounds(x, y):
            self.set_message("Face a crop or tilled soil.")
            return False
        strength = max(1, _safe_int(product.get("effects", {}).get("fertilizer_strength", 1), 1))
        crop = self.get_crop(x, y)
        tile = self.farm_work_tile_at(x, y)
        if crop:
            if crop.fertilized and strength <= 1:
                self.set_message(f"{crop.name} is already fertilized.")
                return False
            crop.fertilized = True
            crop.care_days += max(0, strength - 1)
            if strength >= 3:
                crop.watered = True
        elif tile in {",", "w"}:
            if self.is_tile_fertilized(x, y):
                self.set_message("This soil is already fertilized.")
                return False
            self.set_tile_fertilized(x, y, True)
        else:
            self.set_message("Soil treatment needs tilled soil or a growing crop.")
            return False
        self.state.inventory[item_name] -= 1
        self.autosave_with_message(f"Applied {item_name}; soil strength {strength}." + self.alchemy_apply_backlash(product))
        return True

    def alchemy_use_pigment(self, item_name: str, product: Mapping[str, object]) -> bool:
        x, y = self.target_tile_pos()
        key, obj_name, _ax, _ay = self.placed_object_at(x, y)
        if not key or not obj_name:
            self.set_message("Face a player-placed piece of furniture before using pigment.")
            return False
        finish = str(product.get("color", "Natural"))
        self.set_object_finish_for_key(str(key), str(obj_name), finish)
        if self.object_finish_for_key(str(key), str(obj_name)) != finish:
            self.set_message("That object cannot hold a furniture pigment.")
            return False
        self.state.inventory[item_name] -= 1
        self.invalidate_draw_cache()
        self.autosave_with_message(f"Finished {obj_name} with {item_name}; its new color is {finish}." + self.alchemy_apply_backlash(product))
        return True

    def use_alchemy_product(self, item_name: str) -> bool:
        product = self.alchemy_product(item_name)
        if not product or _safe_int(self.state.inventory.get(item_name, 0)) <= 0:
            return False
        kind = str(product.get("kind", "potion"))
        if kind == "potion":
            return self.alchemy_use_potion(item_name, product)
        if kind == "oil":
            return self.alchemy_use_oil(item_name, product)
        if kind == "bomb":
            return self.alchemy_use_bomb(item_name, product)
        if kind == "fertilizer":
            return self.alchemy_use_fertilizer(item_name, product)
        if kind == "pigment":
            return self.alchemy_use_pigment(item_name, product)
        return False

    def strongest_alchemy_fertilizer(self) -> Optional[Tuple[str, Dict[str, object]]]:
        candidates = []
        for item_name, qty in self.state.inventory.items():
            product = self.alchemy_product(item_name)
            if qty > 0 and product and product.get("kind") == "fertilizer":
                strength = _safe_int(product.get("effects", {}).get("fertilizer_strength", 1), 1)
                candidates.append((strength, item_name, product))
        if not candidates:
            return None
        _strength, name, product = max(candidates, key=lambda row: (row[0], row[1]))
        return name, product


__all__ = [
    "ALCHEMY_FINISH_DATA", "ALCHEMY_INGREDIENT_DATA", "ALCHEMY_MATRIX_DATA",
    "AlchemyMixin", "alchemy_combat_bonuses", "alchemy_effect_value",
    "available_finish_ids", "break_alchemy_stealth",
    "formula_signature", "matrix_cost_text", "mixture_preview",
    "product_effect_lines", "sanitize_active_alchemy_effects",
    "sanitize_alchemy_formulas", "sanitize_alchemy_products",
    "sanitize_equipment_oils",
]
