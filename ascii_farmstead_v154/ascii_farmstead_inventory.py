from __future__ import annotations

"""Inventory and resource-drop helper functions for Elsewhere.

These helpers operate on inventory dictionaries and static item data. They do
not import FarmGame, UI code, or save/load code, which keeps them reusable by
future crafting, cooking, shops, and combat reward systems.
"""

import random
from typing import Dict, Mapping

from ascii_farmstead_data import CROP_DATA, FISH_DATA, FISH_ITEMS, QUALITY_ORDER
from ascii_farmstead_helpers import fish_sell_price
from ascii_farmstead_state import quality_item_name


class CapacityInventory(dict):
    """Inventory mapping that cannot silently grow past its carrying limit.

    Old saves are allowed to begin above the current limit. Reductions always
    work, while additions are held at the highest quantity that fits. Rejected
    additions are recorded so FarmGame can leave them in a recoverable pack at
    the player's feet instead of deleting rewards from older direct-write code.
    """

    def __init__(self, values: Mapping[str, int] | None = None, capacity: int = 200):
        super().__init__()
        self.capacity = max(1, int(capacity))
        self._rejected: Dict[str, int] = {}
        self._used_points = 0
        for item_name, qty in dict(values or {}).items():
            key = str(item_name)
            quantity = max(0, int(qty or 0))
            dict.__setitem__(self, key, quantity)
            self._used_points += quantity * self.item_weight_points(key)

    def used_slots(self) -> int:
        points = self.used_points()
        return (points + 3) // 4

    @staticmethod
    def item_weight_points(item_name: str) -> int:
        compact_materials = {
            "Wood", "Stone", "Fiber", "Sap", "Hardwood", "Clay", "Coal",
            "Copper Ore", "Iron Ore", "Gold Ore", "Copper Bar", "Iron Bar", "Gold Bar",
            "Quartz", "Amethyst", "Hay", "Animal Feed", "Bait",
        }
        return 1 if item_name in compact_materials or item_name.endswith(" Seeds") else 4

    def used_points(self) -> int:
        return max(0, int(self._used_points))

    def free_points(self) -> int:
        return max(0, self.capacity * 4 - self.used_points())

    def free_slots(self) -> int:
        return self.free_points() // 4

    def max_additional(self, item_name: str) -> int:
        return self.free_points() // self.item_weight_points(str(item_name))

    def set_capacity(self, capacity: int) -> None:
        self.capacity = max(1, int(capacity))

    def __setitem__(self, item_name, quantity) -> None:
        key = str(item_name)
        old_qty = max(0, int(dict.get(self, key, 0) or 0))
        new_qty = max(0, int(quantity or 0))
        if new_qty <= old_qty:
            dict.__setitem__(self, key, new_qty)
            self._used_points += (new_qty - old_qty) * self.item_weight_points(key)
            return
        free_quantity = self.max_additional(key)
        accepted_qty = old_qty + min(new_qty - old_qty, free_quantity)
        dict.__setitem__(self, key, accepted_qty)
        self._used_points += (accepted_qty - old_qty) * self.item_weight_points(key)
        rejected = new_qty - accepted_qty
        if rejected > 0:
            self._rejected[key] = self._rejected.get(key, 0) + rejected

    def take_rejected(self) -> Dict[str, int]:
        rejected = dict(self._rejected)
        self._rejected.clear()
        return rejected

    def update(self, values=(), **kwargs) -> None:
        incoming = dict(values, **kwargs)
        for item_name, quantity in incoming.items():
            self[item_name] = quantity

    def setdefault(self, item_name, default=0):
        key = str(item_name)
        if key not in self:
            self[key] = default
        return self.get(key)

    def __ior__(self, values):
        self.update(values)
        return self

    def __delitem__(self, item_name) -> None:
        key = str(item_name)
        old_qty = max(0, int(dict.get(self, key, 0) or 0))
        dict.__delitem__(self, key)
        self._used_points -= old_qty * self.item_weight_points(key)

    def pop(self, item_name, *default):
        key = str(item_name)
        if key not in self:
            if default:
                return default[0]
            raise KeyError(key)
        value = dict.get(self, key)
        self.__delitem__(key)
        return value

    def popitem(self):
        key, value = dict.popitem(self)
        self._used_points -= max(0, int(value or 0)) * self.item_weight_points(str(key))
        return key, value

    def clear(self) -> None:
        dict.clear(self)
        self._used_points = 0


def capacity_inventory(inventory: Mapping[str, int] | None, capacity: int) -> CapacityInventory:
    if isinstance(inventory, CapacityInventory):
        inventory.set_capacity(capacity)
        return inventory
    return CapacityInventory(inventory, capacity)


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
