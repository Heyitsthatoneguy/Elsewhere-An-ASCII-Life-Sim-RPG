from __future__ import annotations

from typing import Dict, List, Tuple

from .models import Pos, Unit, Weapon


def create_default_heroes(start_positions: Dict[str, Pos]) -> List[Unit]:
    return [
        # Rook is sturdy and reliable. He should survive a few mistakes.
        Unit("Rook", "@", start_positions["Rook"], 42, 42, 12, 12, 5, Weapon("Iron Saber", 6), "hero", ai_controlled=False, inventory={"Potion": 2, "Ether": 1, "Cleanse Kit": 1, "Guard Tonic": 1, "Throwing Knife": 2, "Fire Bomb": 1}),
        # Mira is useful but not meant to win the fight by herself.
        Unit("Mira", "@", start_positions["Mira"], 30, 30, 16, 16, 4, Weapon("Scout Bow", 4, 2, 4), "hero", ai_controlled=True, inventory={"Potion": 1, "Ether": 1, "Throwing Knife": 1}),
        # Brom is a sturdy melee companion who can hold lanes and use guard/overwatch.
        Unit("Brom", "@", start_positions["Brom"], 38, 38, 10, 10, 4, Weapon("Guard Axe", 5), "hero", ai_controlled=True, inventory={"Potion": 1, "Guard Tonic": 1, "Throwing Knife": 1}),
        # Aria is a fragile support/ranged companion with enough MP to use control skills.
        Unit("Aria", "@", start_positions["Aria"], 26, 26, 18, 18, 5, Weapon("Light Wand", 3, 1, 4), "hero", ai_controlled=True, inventory={"Potion": 1, "Ether": 1, "Cleanse Kit": 1}),

        # Reserve companions. They are selectable from Party Management, but the active party is capped at 4 total.
        Unit("Nia", "@", start_positions.get("Nia", start_positions["Mira"]), 32, 32, 14, 14, 6, Weapon("Twin Daggers", 4), "hero", ai_controlled=True, inventory={"Potion": 1, "Throwing Knife": 2, "Guard Tonic": 1}),
        Unit("Dax", "@", start_positions.get("Dax", start_positions["Brom"]), 44, 44, 8, 8, 4, Weapon("Stone Hammer", 6), "hero", ai_controlled=True, inventory={"Potion": 2, "Guard Tonic": 1}),
        Unit("Luma", "@", start_positions.get("Luma", start_positions["Aria"]), 28, 28, 20, 20, 5, Weapon("Sun Rod", 3, 1, 4), "hero", ai_controlled=True, inventory={"Potion": 1, "Ether": 2, "Cleanse Kit": 1}),
    ]


def companion_name_presets() -> List[str]:
    return [
        "Ash", "Fern", "Rowan", "Iris", "Clover", "Sable", "Orin", "Pip",
        "Juniper", "Hale", "Moss", "Briar", "Vale", "Wren", "Nox", "Ember",
    ]


def companion_glyphs() -> List[str]:
    # Retained for compatibility with older saves/tests; map display now uses @ for all heroes.
    return ["@"]


def companion_archetypes() -> List[Tuple[str, Dict[str, int], Dict[str, int]]]:
    return [
        ("Balanced", {"max_hp": 34, "max_mp": 12, "weapon_damage": 5, "move_range": 5}, {"Potion": 1, "Ether": 1}),
        ("Bulky", {"max_hp": 42, "max_mp": 8, "weapon_damage": 5, "move_range": 4}, {"Potion": 2, "Guard Tonic": 1}),
        ("Agile", {"max_hp": 30, "max_mp": 12, "weapon_damage": 4, "move_range": 6}, {"Potion": 1, "Throwing Knife": 2}),
        ("Caster", {"max_hp": 26, "max_mp": 20, "weapon_damage": 3, "move_range": 5}, {"Potion": 1, "Ether": 2, "Cleanse Kit": 1}),
        ("Support", {"max_hp": 30, "max_mp": 18, "weapon_damage": 3, "move_range": 5}, {"Potion": 1, "Ether": 1, "Cleanse Kit": 2}),
        ("Bruiser", {"max_hp": 38, "max_mp": 10, "weapon_damage": 6, "move_range": 4}, {"Potion": 2, "Throwing Knife": 1}),
        ("Scout", {"max_hp": 28, "max_mp": 14, "weapon_damage": 4, "move_range": 7}, {"Potion": 1, "Throwing Knife": 2, "Guard Tonic": 1}),
    ]

