from __future__ import annotations

"""Inventory and resource-drop helper functions for Elsewhere.

These helpers operate on inventory dictionaries and static item data. They do
not import FarmGame, UI code, or save/load code, which keeps them reusable by
future crafting, cooking, shops, and combat reward systems.
"""

import random
from typing import Dict

from ascii_farmstead_data import CROP_DATA, FISH_DATA, FISH_ITEMS, QUALITY_ORDER
from ascii_farmstead_helpers import fish_sell_price
from ascii_farmstead_state import quality_item_name


def inventory_crop_quantity(inventory: Dict[str, int], crop_name: str) -> int:
    total = 0
    for quality in QUALITY_ORDER:
        item_name = quality_item_name(crop_name, quality)
        total += inventory.get(item_name, 0)
    return total

def inventory_fish_quantity(inventory: Dict[str, int]) -> int:
    return sum(qty for item_name, qty in inventory.items() if item_name in FISH_ITEMS and qty > 0 and not FISH_DATA[item_name].get("junk", False))

def inventory_ingredient_quantity(inventory: Dict[str, int], ingredient_name: str) -> int:
    if ingredient_name == "Any Fish":
        return inventory_fish_quantity(inventory)
    if ingredient_name in CROP_DATA:
        return inventory_crop_quantity(inventory, ingredient_name)
    return inventory.get(ingredient_name, 0)

def consume_crop_ingredient(inventory: Dict[str, int], crop_name: str, qty: int) -> int:
    consumed = 0
    for quality in QUALITY_ORDER:
        item_name = quality_item_name(crop_name, quality)
        available = inventory.get(item_name, 0)
        if available <= 0:
            continue
        take = min(available, qty - consumed)
        inventory[item_name] = available - take
        consumed += take
        if consumed >= qty:
            break
    return consumed

def consume_fish_ingredient(inventory: Dict[str, int], qty: int) -> int:
    consumed = 0
    # Consume low-value fish first.
    fish_names = sorted(
        [name for name in FISH_ITEMS if inventory.get(name, 0) > 0 and not FISH_DATA[name].get("junk", False)],
        key=lambda name: fish_sell_price(name),
    )
    for fish_name in fish_names:
        available = inventory.get(fish_name, 0)
        take = min(available, qty - consumed)
        inventory[fish_name] = available - take
        consumed += take
        if consumed >= qty:
            break
    return consumed

def consume_ingredient(inventory: Dict[str, int], ingredient_name: str, qty: int) -> int:
    if ingredient_name == "Any Fish":
        return consume_fish_ingredient(inventory, qty)
    if ingredient_name in CROP_DATA:
        return consume_crop_ingredient(inventory, ingredient_name, qty)
    available = inventory.get(ingredient_name, 0)
    take = min(available, qty)
    inventory[ingredient_name] = available - take
    return take

def add_inventory_items(inventory: Dict[str, int], drops: Dict[str, int]):
    for item_name, qty in drops.items():
        if qty > 0:
            inventory[item_name] = inventory.get(item_name, 0) + qty

def format_drops(drops: Dict[str, int]) -> str:
    parts = [f"{qty} {name}" for name, qty in drops.items() if qty > 0]
    return ", ".join(parts) if parts else "nothing"

def roll_weed_drops(count: int = 1) -> Dict[str, int]:
    drops: Dict[str, int] = {}
    for _ in range(count):
        drops["Fiber"] = drops.get("Fiber", 0) + 1
        if random.random() < 0.25:
            drops["Mixed Seeds"] = drops.get("Mixed Seeds", 0) + 1
        if random.random() < 0.10:
            drops["Wild Herbs"] = drops.get("Wild Herbs", 0) + 1
    return drops

def roll_stone_drops(count: int = 1, pickaxe_level: int = 1) -> Dict[str, int]:
    drops: Dict[str, int] = {}
    for _ in range(count):
        drops["Stone"] = drops.get("Stone", 0) + 1
        if random.random() < 0.15 + 0.05 * max(0, pickaxe_level - 1):
            drops["Coal"] = drops.get("Coal", 0) + 1
        if random.random() < 0.10 + 0.05 * max(0, pickaxe_level - 1):
            drops["Copper Ore"] = drops.get("Copper Ore", 0) + 1
        if pickaxe_level >= 2 and random.random() < 0.08 + 0.04 * max(0, pickaxe_level - 2):
            drops["Iron Ore"] = drops.get("Iron Ore", 0) + 1
    return drops

def roll_wood_drops(count: int = 1, axe_level: int = 1) -> Dict[str, int]:
    drops: Dict[str, int] = {}
    for _ in range(count):
        drops["Wood"] = drops.get("Wood", 0) + 1
        if random.random() < 0.20:
            drops["Sap"] = drops.get("Sap", 0) + 1
        if axe_level >= 2 and random.random() < 0.15 + 0.05 * max(0, axe_level - 2):
            drops["Hardwood"] = drops.get("Hardwood", 0) + 1
    return drops



__all__ = [
    'inventory_crop_quantity',
    'inventory_fish_quantity',
    'inventory_ingredient_quantity',
    'consume_crop_ingredient',
    'consume_fish_ingredient',
    'consume_ingredient',
    'add_inventory_items',
    'format_drops',
    'roll_weed_drops',
    'roll_stone_drops',
    'roll_wood_drops'
]
