from __future__ import annotations

from typing import Dict


_EQUIPMENT_DEFS_CACHE = None


def invalidate_equipment_defs_cache() -> None:
    global _EQUIPMENT_DEFS_CACHE
    _EQUIPMENT_DEFS_CACHE = None


def equipment_defs() -> Dict[str, Dict[str, Dict[str, object]]]:
    global _EQUIPMENT_DEFS_CACHE
    if _EQUIPMENT_DEFS_CACHE is not None:
        return _EQUIPMENT_DEFS_CACHE
    definitions = {
        "weapon": {
            # Rook
            "Iron Saber": {"heroes": ["Rook"], "cost": {}, "desc": "Balanced starter blade.", "dmg": 0},
            "Heavy Saber": {"heroes": ["Rook"], "cost": {"Coin": 18, "Stone": 1}, "desc": "Heavy blade. +2 damage, -1 move.", "dmg": 2, "move": -1},
            "Command Blade": {"heroes": ["Rook"], "cost": {"Coin": 14, "Shard": 2}, "desc": "Tactical blade. +1 damage, +3 MP.", "dmg": 1, "mp": 3},
            "Guard Blade": {"heroes": ["Rook"], "cost": {"Coin": 14, "Hide": 2}, "desc": "Defensive blade. +1 damage, +5 HP.", "dmg": 1, "hp": 5},
            "Crystal Skewer": {"heroes": ["Rook"], "cost": {"Coin": 18, "Crystal Fang": 1, "Spider Silk": 1}, "desc": "Reach blade from cave predator loot. +1 damage, +1 range, +1 MP.", "dmg": 1, "range_max": 1, "mp": 1},
            "Relic Saber": {"heroes": ["Rook"], "cost": {"Coin": 24, "Relic Fragment": 2, "Ancient Cog": 1}, "desc": "Restored ruin blade. +2 damage, +2 MP.", "dmg": 2, "mp": 2},

            # Mira
            "Scout Bow": {"heroes": ["Mira"], "cost": {}, "desc": "Balanced starter bow.", "dmg": 0},
            "Longbow": {"heroes": ["Mira"], "cost": {"Coin": 16, "Fang": 1, "Crow Feather": 1}, "desc": "Long range. +1 damage, +1 range, -1 move.", "dmg": 1, "range_max": 1, "move": -1},
            "Quick Bow": {"heroes": ["Mira"], "cost": {"Coin": 14, "Hide": 1, "Fang": 1}, "desc": "Skirmisher bow. +1 damage, +1 move.", "dmg": 1, "move": 1},
            "Venom Bow": {"heroes": ["Mira"], "cost": {"Coin": 12, "Spore Cap": 1, "Slime Core": 1}, "desc": "Status bow. +1 damage, +2 MP.", "dmg": 1, "mp": 2},
            "Silkstring Bow": {"heroes": ["Mira"], "cost": {"Coin": 18, "Spider Silk": 2, "Crow Feather": 1}, "desc": "Responsive bow. +1 damage, +1 move, +2 MP.", "dmg": 1, "move": 1, "mp": 2},
            "Relic Longbow": {"heroes": ["Mira"], "cost": {"Coin": 22, "Relic Arrowhead": 2, "Shard": 1}, "desc": "Ruin longbow. +2 damage, +1 range.", "dmg": 2, "range_max": 1},

            # Brom
            "Guard Axe": {"heroes": ["Brom"], "cost": {}, "desc": "Balanced starter axe.", "dmg": 0},
            "War Maul": {"heroes": ["Brom"], "cost": {"Coin": 18, "Stone": 2}, "desc": "Slow crusher. +3 damage, -1 move.", "dmg": 3, "move": -1},
            "Tower Axe": {"heroes": ["Brom"], "cost": {"Coin": 16, "Hide": 2, "Stone": 1}, "desc": "Tank axe. +1 damage, +7 HP.", "dmg": 1, "hp": 7},
            "Hook Axe": {"heroes": ["Brom"], "cost": {"Coin": 14, "Fang": 1, "Stone": 1}, "desc": "Reach axe. +1 damage, +1 range.", "dmg": 1, "range_max": 1},
            "Lynx Hook Axe": {"heroes": ["Brom"], "cost": {"Coin": 18, "Lynx Claw": 2, "Hide": 1}, "desc": "Hooked monster axe. +2 damage, +1 range.", "dmg": 2, "range_max": 1},

            # Aria
            "Light Wand": {"heroes": ["Aria"], "cost": {}, "desc": "Balanced starter wand.", "dmg": 0},
            "Spark Wand": {"heroes": ["Aria"], "cost": {"Coin": 12, "Shard": 1, "Wisp Spark": 1}, "desc": "Glass-cannon wand. +2 damage, -3 HP.", "dmg": 2, "hp": -3},
            "Bloom Staff": {"heroes": ["Aria"], "cost": {"Coin": 12, "Tonic": 1, "Root Fiber": 1}, "desc": "Support staff. +4 HP, +2 MP.", "hp": 4, "mp": 2},
            "Channel Wand": {"heroes": ["Aria"], "cost": {"Coin": 14, "Shard": 2, "Tonic": 1}, "desc": "Caster wand. +1 damage, +5 MP.", "dmg": 1, "mp": 5},
            "Gloom Staff": {"heroes": ["Aria"], "cost": {"Coin": 16, "Gloom Spores": 2, "Tonic": 1}, "desc": "Control staff. +1 damage, +6 MP, -2 HP.", "dmg": 1, "mp": 6, "hp": -2},

            # Nia
            "Twin Daggers": {"heroes": ["Nia"], "cost": {}, "desc": "Fast starter daggers.", "dmg": 0},
            "Duelist Foil": {"heroes": ["Nia"], "cost": {"Coin": 12, "Fang": 1, "Hide": 1}, "desc": "Mobile duelist weapon. +1 damage, +1 move.", "dmg": 1, "move": 1},
            "Throwing Daggers": {"heroes": ["Nia"], "cost": {"Coin": 14, "Fang": 2}, "desc": "Flexible throwing kit. +1 damage, +1 range.", "dmg": 1, "range_max": 1},
            "Shadow Daggers": {"heroes": ["Nia"], "cost": {"Coin": 16, "Spore Cap": 1, "Fang": 1}, "desc": "Combo blades. +1 damage, +3 MP.", "dmg": 1, "mp": 3},
            "Crystal Needles": {"heroes": ["Nia"], "cost": {"Coin": 18, "Crystal Fang": 1, "Hare Needle": 1}, "desc": "Fast glass daggers. +1 damage, +1 move, +1 range.", "dmg": 1, "move": 1, "range_max": 1},

            # Dax
            "Stone Hammer": {"heroes": ["Dax"], "cost": {}, "desc": "Heavy starter hammer.", "dmg": 0},
            "Breaker Hammer": {"heroes": ["Dax"], "cost": {"Coin": 18, "Stone": 2}, "desc": "Armor breaker. +3 damage, -1 move.", "dmg": 3, "move": -1},
            "Bulwark Hammer": {"heroes": ["Dax"], "cost": {"Coin": 14, "Hide": 2, "Stone": 1}, "desc": "Frontline hammer. +1 damage, +8 HP.", "dmg": 1, "hp": 8},
            "Tremor Hammer": {"heroes": ["Dax"], "cost": {"Coin": 16, "Shard": 1, "Stone": 1}, "desc": "Control hammer. +1 damage, +2 MP.", "dmg": 1, "mp": 2},
            "Clockwork Maul": {"heroes": ["Dax"], "cost": {"Coin": 22, "Clockwork Carapace": 2, "Ancient Cog": 1}, "desc": "Mechanical hammer. +2 damage, +5 HP.", "dmg": 2, "hp": 5},

            # Luma
            "Sun Rod": {"heroes": ["Luma"], "cost": {}, "desc": "Warm starter rod.", "dmg": 0},
            "Mercy Rod": {"heroes": ["Luma"], "cost": {"Coin": 12, "Tonic": 2}, "desc": "Support rod. +5 HP, +3 MP.", "hp": 5, "mp": 3},
            "Star Rod": {"heroes": ["Luma"], "cost": {"Coin": 14, "Shard": 2}, "desc": "Caster rod. +1 damage, +5 MP.", "dmg": 1, "mp": 5},
            "Beacon Rod": {"heroes": ["Luma"], "cost": {"Coin": 12, "Hide": 1, "Shard": 1}, "desc": "Safe support rod. +3 HP, +1 range.", "hp": 3, "range_max": 1},
            "Sigil Rod": {"heroes": ["Luma"], "cost": {"Coin": 22, "Stone Sigil": 1, "Relic Fragment": 1}, "desc": "Protective relic rod. +1 damage, +4 HP, +4 MP.", "dmg": 1, "hp": 4, "mp": 4},
        },
        "armor": {
            "Traveler Clothes": {"heroes": "all", "cost": {}, "desc": "No bonuses. Light and flexible."},
            "Leather Coat": {"heroes": "all", "cost": {"Coin": 8, "Hide": 1}, "desc": "+4 HP.", "hp": 4},
            "Reinforced Coat": {"heroes": "all", "cost": {"Coin": 12, "Hide": 2, "Stone": 1}, "desc": "+8 HP, -1 move.", "hp": 8, "move": -1},
            "Focus Robe": {"heroes": "all", "cost": {"Coin": 10, "Tonic": 2}, "desc": "+2 HP, +4 MP.", "hp": 2, "mp": 4},
            "Silkguard Coat": {"heroes": "all", "cost": {"Coin": 16, "Spider Silk": 2, "Hide": 1}, "desc": "+6 HP, +2 MP.", "hp": 6, "mp": 2},
            "Ruin Plate Coat": {"heroes": "all", "cost": {"Coin": 24, "Clockwork Carapace": 2, "Stone Sigil": 1}, "desc": "+11 HP, +1 damage, -1 move.", "hp": 11, "dmg": 1, "move": -1},
        },
        "charm": {
            "Plain Charm": {"heroes": "all", "cost": {}, "desc": "No bonuses."},
            "Swift Charm": {"heroes": "all", "cost": {"Coin": 10, "Hare Needle": 1}, "desc": "+1 move.", "move": 1},
            "Focus Charm": {"heroes": "all", "cost": {"Coin": 10, "Shard": 1}, "desc": "+4 MP.", "mp": 4},
            "Guard Charm": {"heroes": "all", "cost": {"Coin": 10, "Shield Fragment": 1}, "desc": "+5 HP.", "hp": 5},
            "Combo Charm": {"heroes": "all", "cost": {"Coin": 14, "Shard": 1, "Fang": 1}, "desc": "+1 damage, +2 MP.", "dmg": 1, "mp": 2},
            "Gloom Charm": {"heroes": "all", "cost": {"Coin": 14, "Gloom Spores": 1, "Tonic": 1}, "desc": "+1 damage, +3 MP." , "dmg": 1, "mp": 3},
            "Cog Charm": {"heroes": "all", "cost": {"Coin": 18, "Ancient Cog": 1, "Old Coin": 2}, "desc": "+4 HP, +3 MP.", "hp": 4, "mp": 3},
        },
    }
    try:
        from ascii_farmstead_custom_extended import custom_equipment_defs

        additions = custom_equipment_defs({
            slot: values.keys()
            for slot, values in definitions.items()
        })
        for slot, values in additions.items():
            definitions.setdefault(slot, {}).update(values)
    except (ImportError, OSError, TypeError, ValueError):
        pass
    _EQUIPMENT_DEFS_CACHE = definitions
    return definitions

