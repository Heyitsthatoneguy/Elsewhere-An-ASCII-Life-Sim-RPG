from __future__ import annotations

from typing import List

from .models import Item

try:
    from ascii_farmstead_combat import FARMSTEAD_COMBAT_ITEM_DATA
except Exception:
    FARMSTEAD_COMBAT_ITEM_DATA = {}


def create_default_items() -> List[Item]:
    items = [
        Item("Potion", effect="heal", target_team="ally", amount=14, description="Restore 14 HP to one ally."),
        Item("Ether", effect="mp", target_team="ally", amount=6, description="Restore 6 MP to one ally."),
        Item("Cleanse Kit", effect="cleanse", target_team="ally", description="Remove poison, root, and vulnerable."),
        Item("Guard Tonic", effect="guard", target_team="ally", description="Put one ally into Guard without spending their AP."),
        Item("Throwing Knife", effect="damage", target_team="enemy", amount=5, range_max=5, description="Quick ranged damage to one enemy."),
        Item("Fire Bomb", effect="damage", target_team="enemy", amount=6, range_max=4, aoe_radius=1, description="Small explosive burst around target tile."),
    ]
    seen = {item.name for item in items}
    for item_name, data in sorted(FARMSTEAD_COMBAT_ITEM_DATA.items()):
        if item_name in seen:
            continue
        items.append(
            Item(
                item_name,
                effect=str(data.get("effect", "heal")),
                target_team="ally",
                amount=int(data.get("amount", 0) or 0),
                description=str(data.get("description", "Farmstead food.")),
            )
        )
    return items
