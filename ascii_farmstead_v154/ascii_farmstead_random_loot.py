from __future__ import annotations

"""Persistent procedural equipment and bounded randomized reward helpers."""

import hashlib
import random
from typing import Dict, List, Optional, Tuple


GENERATED_EQUIPMENT_SCHEMA_VERSION = 1
GENERATED_EQUIPMENT_SLOTS = ("weapon", "armor", "accessory")
GENERATED_EQUIPMENT_RARITIES = ("Common", "Uncommon", "Rare", "Epic", "Legendary")
WORKSHOP_MAX_ENHANCEMENT = 6
WORKSHOP_SALVAGE_ITEM = "Tempering Shard"

RARITY_DATA: Dict[str, Dict[str, object]] = {
    "Common": {"rank": 0, "affixes": 0, "value": 1.00},
    "Uncommon": {"rank": 1, "affixes": 1, "value": 1.35},
    "Rare": {"rank": 2, "affixes": 2, "value": 1.85},
    "Epic": {"rank": 3, "affixes": 3, "value": 2.60},
    "Legendary": {"rank": 4, "affixes": 4, "value": 3.75},
}

WEAPON_BASES: Tuple[Dict[str, object], ...] = (
    {"name": "Blade", "attack": 3, "range_min": 1, "range_max": 1, "tags": ["blade"]},
    {"name": "Hammer", "attack": 2, "defense": 1, "range_min": 1, "range_max": 1, "tags": ["blunt"]},
    {"name": "Spear", "attack": 2, "range_min": 1, "range_max": 2, "tags": ["reach"]},
    {"name": "Bow", "attack": 2, "max_focus": 1, "range_min": 2, "range_max": 4, "tags": ["ranged"]},
    {"name": "Wand", "attack": 1, "max_focus": 3, "range_min": 2, "range_max": 4, "tags": ["ranged", "arcane"]},
)

ARMOR_BASES: Tuple[Dict[str, object], ...] = (
    {"name": "Jacket", "defense": 2, "max_hp": 4},
    {"name": "Mail", "defense": 3, "max_hp": 7},
    {"name": "Explorer Coat", "defense": 2, "max_hp": 5, "max_focus": 3},
    {"name": "Warden Vest", "defense": 2, "max_hp": 8},
    {"name": "Runed Cloak", "defense": 1, "max_hp": 3, "max_focus": 5},
)

ACCESSORY_BASES: Tuple[Dict[str, object], ...] = (
    {"name": "Ring", "defense": 1, "max_hp": 2},
    {"name": "Charm", "attack": 1, "max_focus": 2},
    {"name": "Band", "max_focus": 5},
    {"name": "Brooch", "defense": 1, "max_hp": 3, "max_focus": 2},
    {"name": "Talisman", "attack": 1, "defense": 1, "max_focus": 1},
)

SLOT_BASES = {
    "weapon": WEAPON_BASES,
    "armor": ARMOR_BASES,
    "accessory": ACCESSORY_BASES,
}

PREFIXES = (
    "Ashen", "Bright", "Deep", "Ember", "Frost", "Gilded", "Hollow",
    "Ironwood", "Moonlit", "River", "Storm", "Wayfarer's",
)
SUFFIXES = (
    "of Focus", "of Fortitude", "of the Delver", "of the Hearth",
    "of the Ranger", "of the Sentinel", "of Vigor", "of Warding",
)

AFFIX_DATA: Tuple[Tuple[str, str, Dict[str, int]], ...] = (
    ("Keen", "Keen", {"attack": 1}),
    ("Guarded", "Guarded", {"defense": 1}),
    ("Vital", "Vital", {"max_hp": 4}),
    ("Focused", "Focused", {"max_focus": 3}),
    ("Stalwart", "Stalwart", {"defense": 1, "max_hp": 2}),
    ("Channeling", "Channeling", {"attack": 1, "max_focus": 1}),
)
AFFIX_BONUS_BY_LABEL: Dict[str, Dict[str, int]] = {
    label: dict(bonuses)
    for _key, label, bonuses in AFFIX_DATA
}

RANDOM_CONSUMABLES = (
    "Field Bandage", "Focus Tonic", "Restorative Salts", "Antidote Kit",
    "Warding Chalk",
)
RANDOM_VALUABLES = (
    "Foreign Coin", "Tarnished Locket", "Carved Bone Token", "Brass Compass",
    "Ceremonial Key", "Amber Bead Strand", "Silver Candlestick",
)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stable_seed(source_key: str) -> int:
    digest = hashlib.sha256(str(source_key).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def generated_equipment_store(state: object) -> Dict[str, Dict[str, object]]:
    if state is None:
        return {}
    store = getattr(state, "generated_equipment", None)
    if not isinstance(store, dict):
        store = {}
        setattr(state, "generated_equipment", store)
    return store


def equipment_workshop_store(state: object) -> Dict[str, Dict[str, int]]:
    if state is None:
        return {}
    store = getattr(state, "equipment_workshop", None)
    if not isinstance(store, dict):
        store = {}
        setattr(state, "equipment_workshop", store)
    return store


def sanitize_equipment_workshop(value: object) -> Dict[str, Dict[str, int]]:
    clean: Dict[str, Dict[str, int]] = {}
    if not isinstance(value, dict):
        return clean
    for raw_name, raw_record in value.items():
        name = str(raw_name or "").strip()[:96]
        if not name:
            continue
        record = raw_record if isinstance(raw_record, dict) else {}
        enhancement = max(0, min(WORKSHOP_MAX_ENHANCEMENT, _safe_int(record.get("enhancement", 0))))
        reforge_count = max(0, min(99, _safe_int(record.get("reforge_count", 0))))
        if enhancement or reforge_count:
            clean[name] = {
                "enhancement": enhancement,
                "reforge_count": reforge_count,
            }
    return clean


def sanitize_generated_equipment_store(value: object) -> Dict[str, Dict[str, object]]:
    clean: Dict[str, Dict[str, object]] = {}
    if not isinstance(value, dict):
        return clean
    for raw_name, raw_record in value.items():
        if not isinstance(raw_record, dict):
            continue
        name = str(raw_record.get("name", raw_name) or raw_name).strip()[:96]
        slot = str(raw_record.get("slot", "")).lower()
        rarity = str(raw_record.get("rarity", "Common")).title()
        if not name or slot not in GENERATED_EQUIPMENT_SLOTS:
            continue
        if rarity not in GENERATED_EQUIPMENT_RARITIES:
            rarity = "Common"
        range_min = max(1, min(6, _safe_int(raw_record.get("range_min", 1), 1)))
        range_max = max(range_min, min(6, _safe_int(raw_record.get("range_max", range_min), range_min)))
        clean[name] = {
            "schema": GENERATED_EQUIPMENT_SCHEMA_VERSION,
            "id": str(raw_record.get("id", f"generated:{_stable_seed(name):016x}"))[:96],
            "name": name,
            "slot": slot,
            "rarity": rarity,
            "item_level": max(1, min(99, _safe_int(raw_record.get("item_level", 1), 1))),
            "base_type": str(raw_record.get("base_type", slot.title()))[:48],
            "attack": max(0, min(20, _safe_int(raw_record.get("attack", 0)))),
            "defense": max(0, min(20, _safe_int(raw_record.get("defense", 0)))),
            "max_hp": max(0, min(60, _safe_int(raw_record.get("max_hp", 0)))),
            "max_focus": max(0, min(40, _safe_int(raw_record.get("max_focus", 0)))),
            "range_min": range_min,
            "range_max": range_max,
            "description": str(raw_record.get("description", "A singular piece of recovered equipment."))[:240],
            "value": max(10, min(10000, _safe_int(raw_record.get("value", 10), 10))),
            "source": str(raw_record.get("source", "Unknown find"))[:120],
            "source_key": str(raw_record.get("source_key", ""))[:180],
            "affixes": [
                str(affix)[:32]
                for affix in (raw_record.get("affixes", []) if isinstance(raw_record.get("affixes"), list) else [])
                if str(affix).strip()
            ][:4],
            "generated": True,
        }
    return clean


def generated_equipment_record(state: object, item_name: object) -> Optional[Dict[str, object]]:
    record = generated_equipment_store(state).get(str(item_name))
    if not isinstance(record, dict):
        return None
    slot = str(record.get("slot", ""))
    return record if slot in GENERATED_EQUIPMENT_SLOTS else None


def equipment_enhancement_cap(state: object, item_name: object) -> int:
    record = generated_equipment_record(state, item_name)
    if not record:
        return 3
    rarity = str(record.get("rarity", "Common"))
    return {
        "Common": 2,
        "Uncommon": 3,
        "Rare": 4,
        "Epic": 5,
        "Legendary": 6,
    }.get(rarity, 2)


def equipment_enhancement_level(state: object, item_name: object) -> int:
    record = equipment_workshop_store(state).get(str(item_name), {})
    if not isinstance(record, dict):
        return 0
    return max(
        0,
        min(
            equipment_enhancement_cap(state, item_name),
            _safe_int(record.get("enhancement", 0)),
        ),
    )


def equipment_enhancement_bonus(slot: str, level: int) -> Dict[str, int]:
    level = max(0, min(WORKSHOP_MAX_ENHANCEMENT, int(level or 0)))
    bonus = {"attack": 0, "defense": 0, "max_hp": 0, "max_focus": 0}
    if slot == "weapon":
        bonus["attack"] = level
        bonus["max_focus"] = level // 3
    elif slot == "armor":
        bonus["defense"] = level
        bonus["max_hp"] = level * 2
        bonus["max_focus"] = level // 3
    elif slot == "accessory":
        bonus["max_focus"] = level
        bonus["defense"] = level // 2
        bonus["attack"] = level // 3
    return bonus


def apply_equipment_enhancement(
    state: object,
    slot: str,
    item_name: object,
    record: Dict[str, object],
    *,
    level_override: Optional[int] = None,
) -> Dict[str, object]:
    enhanced = dict(record or {})
    level = (
        equipment_enhancement_level(state, item_name)
        if level_override is None
        else max(0, min(equipment_enhancement_cap(state, item_name), int(level_override)))
    )
    bonus = equipment_enhancement_bonus(str(slot), level)
    for stat, amount in bonus.items():
        enhanced[stat] = max(0, _safe_int(enhanced.get(stat, 0)) + amount)
    enhanced["enhancement"] = level
    enhanced["enhancement_cap"] = equipment_enhancement_cap(state, item_name)
    enhanced["workshop_bonus"] = bonus
    if level:
        base_value = max(0, _safe_int(enhanced.get("value", 0)))
        enhanced["value"] = min(12500, base_value + level * (180 + 70 * level))
    return enhanced


def equipped_inventory_reserve(state: object, item_name: object) -> int:
    """Keep one carried copy of equipped gear out of shipping/storage transfers."""
    name = str(item_name or "")
    if not name:
        return 0
    equipped = {
        str(getattr(state, "equipped_weapon", "") or ""),
        str(getattr(state, "equipped_armor", "") or ""),
        str(getattr(state, "equipped_accessory", "") or ""),
    }
    quantity = _safe_int(getattr(state, "inventory", {}).get(name, 0), 0)
    return 1 if quantity > 0 and name in equipped else 0


def combat_equipment_data_for(
    state: object,
    slot: str,
    item_name: object,
    static_data: Optional[Dict[str, Dict[str, object]]] = None,
) -> Optional[Dict[str, object]]:
    name = str(item_name or "")
    if static_data and name in static_data:
        return apply_equipment_enhancement(state, slot, name, static_data[name])
    record = generated_equipment_record(state, name)
    if record and str(record.get("slot", "")) == str(slot):
        return apply_equipment_enhancement(state, slot, name, record)
    return None


def equipment_item_level(state: object, item_name: object) -> int:
    record = generated_equipment_record(state, item_name)
    return max(1, min(40, _safe_int(record.get("item_level", 1), 1))) if record else 1


def equipment_enhancement_cost(
    state: object,
    item_name: object,
) -> Tuple[int, Dict[str, int]]:
    current = equipment_enhancement_level(state, item_name)
    next_level = current + 1
    if next_level > equipment_enhancement_cap(state, item_name):
        return 0, {}
    generated = generated_equipment_record(state, item_name)
    rarity_rank = int(RARITY_DATA.get(str((generated or {}).get("rarity", "Common")), {}).get("rank", 0) or 0)
    item_level = equipment_item_level(state, item_name)
    money = 250 + next_level * 300 + item_level * 18 + rarity_rank * 120
    material_steps = {
        1: {"Copper Bar": 1, "Coal": 1},
        2: {"Iron Bar": 1, "Coal": 2, WORKSHOP_SALVAGE_ITEM: 1},
        3: {"Iron Bar": 2, "Crystal Shard": 1, WORKSHOP_SALVAGE_ITEM: 1},
        4: {"Gold Bar": 1, "Crystal Shard": 2, WORKSHOP_SALVAGE_ITEM: 2},
        5: {"Gold Bar": 2, "Relic Fragment": 1, WORKSHOP_SALVAGE_ITEM: 3},
        6: {"Gold Bar": 3, "Relic Fragment": 2, WORKSHOP_SALVAGE_ITEM: 4},
    }
    return money, dict(material_steps[next_level])


def equipment_reforge_cost(state: object, item_name: object) -> Tuple[int, Dict[str, int]]:
    workshop = equipment_workshop_store(state).get(str(item_name), {})
    count = max(0, _safe_int((workshop if isinstance(workshop, dict) else {}).get("reforge_count", 0)))
    item_level = equipment_item_level(state, item_name)
    money = 450 + item_level * 28 + count * 375
    return money, {
        "Crystal Shard": 1 + count // 2,
        WORKSHOP_SALVAGE_ITEM: 1 + count,
    }


def workshop_cost_text(cost: Tuple[int, Dict[str, int]]) -> str:
    money, items = cost
    parts = [f"${int(money)}"] if int(money) > 0 else []
    parts.extend(f"{int(qty)} {name}" for name, qty in items.items() if int(qty) > 0)
    return ", ".join(parts) if parts else "No cost"


def can_afford_workshop_cost(state: object, cost: Tuple[int, Dict[str, int]]) -> bool:
    money, items = cost
    inventory = getattr(state, "inventory", {}) or {}
    return (
        _safe_int(getattr(state, "money", 0)) >= int(money)
        and all(_safe_int(inventory.get(name, 0)) >= int(qty) for name, qty in items.items())
    )


def spend_workshop_cost(state: object, cost: Tuple[int, Dict[str, int]]) -> None:
    money, items = cost
    state.money = max(0, _safe_int(getattr(state, "money", 0)) - int(money))
    inventory = getattr(state, "inventory", {})
    for name, qty in items.items():
        inventory[name] = max(0, _safe_int(inventory.get(name, 0)) - int(qty))


def enhance_equipment(state: object, item_name: object) -> bool:
    name = str(item_name or "")
    inventory = getattr(state, "inventory", {}) or {}
    generated = generated_equipment_record(state, name)
    if generated and _safe_int(inventory.get(name, 0)) <= 0:
        return False
    if (
        not generated
        and name not in {"Rusty Sword", "Work Clothes"}
        and _safe_int(inventory.get(name, 0)) <= 0
        and name not in {
            str(getattr(state, "equipped_weapon", "") or ""),
            str(getattr(state, "equipped_armor", "") or ""),
            str(getattr(state, "equipped_accessory", "") or ""),
        }
    ):
        return False
    current = equipment_enhancement_level(state, name)
    if current >= equipment_enhancement_cap(state, name):
        return False
    cost = equipment_enhancement_cost(state, name)
    if not can_afford_workshop_cost(state, cost):
        return False
    spend_workshop_cost(state, cost)
    record = equipment_workshop_store(state).setdefault(name, {})
    record["enhancement"] = current + 1
    record["reforge_count"] = max(0, _safe_int(record.get("reforge_count", 0)))
    return True


def generated_equipment_salvage_yield(state: object, item_name: object) -> Dict[str, int]:
    record = generated_equipment_record(state, item_name)
    if not record:
        return {}
    rank = int(RARITY_DATA.get(str(record.get("rarity", "Common")), {}).get("rank", 0) or 0)
    item_level = equipment_item_level(state, item_name)
    results = {
        WORKSHOP_SALVAGE_ITEM: 1 + rank + item_level // 12,
        "Ruin Scrap": 1 + rank // 2,
    }
    if item_level >= 28:
        results["Gold Ore"] = 1
    elif item_level >= 16:
        results["Iron Ore"] = 1
    elif item_level >= 7:
        results["Copper Ore"] = 1
    return results


def salvage_generated_equipment(state: object, item_name: object) -> Dict[str, int]:
    name = str(item_name or "")
    inventory = getattr(state, "inventory", {})
    if not generated_equipment_record(state, name) or _safe_int(inventory.get(name, 0)) <= 0:
        return {}
    if equipped_inventory_reserve(state, name):
        return {}
    results = generated_equipment_salvage_yield(state, name)
    if not results:
        return {}
    inventory[name] = max(0, _safe_int(inventory.get(name, 0)) - 1)
    for material, quantity in results.items():
        inventory[material] = _safe_int(inventory.get(material, 0)) + int(quantity)
    return results


def preview_reforge_affix(state: object, item_name: object, old_affix: object) -> str:
    record = generated_equipment_record(state, item_name)
    old_label = str(old_affix or "")
    if not record or old_label not in list(record.get("affixes", []) or []):
        return ""
    current = {str(label) for label in (record.get("affixes", []) or [])}
    choices = sorted(label for label in AFFIX_BONUS_BY_LABEL if label not in current)
    if not choices:
        return ""
    workshop = equipment_workshop_store(state).get(str(item_name), {})
    count = max(0, _safe_int((workshop if isinstance(workshop, dict) else {}).get("reforge_count", 0)))
    seed = _stable_seed(f"reforge:{record.get('id', item_name)}:{count}:{old_label}")
    return choices[seed % len(choices)]


def reforge_generated_equipment(state: object, item_name: object, old_affix: object) -> str:
    name = str(item_name or "")
    old_label = str(old_affix or "")
    record = generated_equipment_record(state, name)
    replacement = preview_reforge_affix(state, name, old_label)
    if (
        not record
        or not replacement
        or _safe_int((getattr(state, "inventory", {}) or {}).get(name, 0)) <= 0
    ):
        return ""
    cost = equipment_reforge_cost(state, name)
    if not can_afford_workshop_cost(state, cost):
        return ""
    spend_workshop_cost(state, cost)
    for stat, amount in AFFIX_BONUS_BY_LABEL.get(old_label, {}).items():
        record[stat] = max(0, _safe_int(record.get(stat, 0)) - int(amount))
    for stat, amount in AFFIX_BONUS_BY_LABEL.get(replacement, {}).items():
        record[stat] = max(0, _safe_int(record.get(stat, 0)) + int(amount))
    affixes = [str(label) for label in (record.get("affixes", []) or [])]
    affixes[affixes.index(old_label)] = replacement
    record["affixes"] = affixes
    workshop = equipment_workshop_store(state).setdefault(name, {})
    workshop["enhancement"] = equipment_enhancement_level(state, name)
    workshop["reforge_count"] = max(0, _safe_int(workshop.get("reforge_count", 0))) + 1
    return replacement


def _rarity_for_roll(rng: random.Random, quality_bonus: int = 0) -> str:
    roll = max(0.0, rng.random() - min(0.20, max(0, int(quality_bonus)) * 0.025))
    if roll < 0.007:
        return "Legendary"
    if roll < 0.040:
        return "Epic"
    if roll < 0.130:
        return "Rare"
    if roll < 0.380:
        return "Uncommon"
    return "Common"


def _unique_generated_name(store: Dict[str, Dict[str, object]], base_name: str) -> str:
    if base_name not in store:
        return base_name
    number = 2
    while f"{base_name} {number}" in store:
        number += 1
    return f"{base_name} {number}"


def generate_random_equipment(
    state: object,
    source_key: str,
    item_level: int = 1,
    quality_bonus: int = 0,
    slot: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> str:
    """Create, persist, and return one unique equipment inventory name."""
    store = generated_equipment_store(state)
    for existing_name, existing_record in store.items():
        if (
            isinstance(existing_record, dict)
            and str(existing_record.get("source_key", ""))
            and str(existing_record.get("source_key", "")) == str(source_key)
        ):
            return str(existing_name)
    rng = rng or random.Random(_stable_seed(source_key))
    level = max(1, min(40, int(item_level or 1)))
    chosen_slot = str(slot or rng.choice(GENERATED_EQUIPMENT_SLOTS))
    if chosen_slot not in GENERATED_EQUIPMENT_SLOTS:
        chosen_slot = "weapon"
    rarity = _rarity_for_roll(rng, quality_bonus)
    rarity_rank = int(RARITY_DATA[rarity]["rank"])
    base = dict(rng.choice(SLOT_BASES[chosen_slot]))
    base_type = str(base.pop("name"))

    stats = {
        "attack": max(0, int(base.get("attack", 0) or 0)),
        "defense": max(0, int(base.get("defense", 0) or 0)),
        "max_hp": max(0, int(base.get("max_hp", 0) or 0)),
        "max_focus": max(0, int(base.get("max_focus", 0) or 0)),
    }
    if chosen_slot == "weapon":
        stats["attack"] += min(6, level // 6)
    elif chosen_slot == "armor":
        stats["defense"] += min(5, level // 8)
        stats["max_hp"] += min(12, level // 3)
    else:
        stats["max_focus"] += min(8, level // 5)

    affix_count = int(RARITY_DATA[rarity]["affixes"])
    affixes: List[str] = []
    for _key, label, bonuses in rng.sample(AFFIX_DATA, min(affix_count, len(AFFIX_DATA))):
        affixes.append(label)
        for stat, amount in bonuses.items():
            stats[stat] += int(amount)

    prefix = rng.choice(PREFIXES)
    suffix = rng.choice(SUFFIXES)
    if rarity == "Common":
        display_base = f"{prefix} {base_type}"
    elif rarity == "Uncommon":
        display_base = f"{prefix} {base_type} {suffix}"
    else:
        display_base = f"{rarity} {prefix} {base_type} {suffix}"
    name = _unique_generated_name(store, display_base)
    value_base = 120 + level * 32 + sum(stats.values()) * 24
    value = min(10000, int(value_base * float(RARITY_DATA[rarity]["value"])))
    source_label = str(source_key).replace(":", " ").replace("_", " ").strip()
    record = {
        "schema": GENERATED_EQUIPMENT_SCHEMA_VERSION,
        "id": f"generated:{_stable_seed(source_key + '|' + name):016x}",
        "name": name,
        "slot": chosen_slot,
        "rarity": rarity,
        "item_level": level,
        "base_type": base_type,
        **stats,
        "range_min": max(1, int(base.get("range_min", 1) or 1)),
        "range_max": max(1, int(base.get("range_max", base.get("range_min", 1)) or 1)),
        "description": (
            f"A {rarity.lower()} level-{level} {base_type.lower()} recovered from "
            f"{source_label or 'the wilderness'}."
        ),
        "value": max(10, value),
        "source": source_label or "Wilderness find",
        "source_key": str(source_key)[:180],
        "affixes": affixes,
        "generated": True,
    }
    store[name] = record
    return name


def add_random_reward_items(
    state: object,
    items: Dict[str, int],
    source_key: str,
    item_level: int,
    *,
    gear_chance: float,
    consumable_chance: float,
    valuable_chance: float,
    quality_bonus: int = 0,
    rng: Optional[random.Random] = None,
) -> Dict[str, int]:
    """Augment a reward once; callers persist the returned item dictionary."""
    rng = rng or random.Random(_stable_seed(source_key))
    rewards = {str(name): max(0, int(qty or 0)) for name, qty in dict(items or {}).items()}
    if rng.random() < max(0.0, min(1.0, float(gear_chance))):
        gear_name = generate_random_equipment(
            state,
            f"{source_key}:gear",
            item_level=item_level,
            quality_bonus=quality_bonus,
            rng=rng,
        )
        rewards[gear_name] = 1
    if rng.random() < max(0.0, min(1.0, float(consumable_chance))):
        item_name = rng.choice(RANDOM_CONSUMABLES)
        rewards[item_name] = rewards.get(item_name, 0) + 1
    if rng.random() < max(0.0, min(1.0, float(valuable_chance))):
        item_name = rng.choice(RANDOM_VALUABLES)
        rewards[item_name] = rewards.get(item_name, 0) + 1
    return {name: qty for name, qty in rewards.items() if qty > 0}
