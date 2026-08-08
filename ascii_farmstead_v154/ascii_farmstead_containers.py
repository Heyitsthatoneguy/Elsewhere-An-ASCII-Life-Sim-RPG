from __future__ import annotations

"""Persistent world containers, carrying capacity, and loot browsing."""

import hashlib
import random
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import (
    INFRASTRUCTURE_DATA,
    LEFT_PANEL_HEIGHT,
    LEFT_PANEL_WIDTH,
    MENU_BACK,
)
from ascii_farmstead_custom_extended import BUILDING_TEMPLATE_FURNISHING_DATA
from ascii_farmstead_excavation import EXCAVATION_FIND_DATA
from ascii_farmstead_inventory import CapacityInventory, capacity_inventory
from ascii_farmstead_random_loot import (
    add_random_reward_items,
    apply_equipment_enhancement,
    equipped_inventory_reserve,
    generated_equipment_record,
)
from ascii_farmstead_ui import MenuItem
from ascii_farmstead_game_tables import rare_recovered_game_table


BASE_BACKPACK_CAPACITY = 200
BACKPACK_UPGRADE_SIZE = 50

CONTAINER_ITEM_DATA: Dict[str, Dict[str, object]] = {
    "Tempering Shard": {
        "value": 32,
        "description": "A dense fragment recovered by dismantling singular gear. Blacksmiths use it for enhancement and reforging.",
    },
    "Dog-Eared Field Guide": {"value": 34, "description": "A practical guide full of penciled trail notes and pressed leaves."},
    "Water-Stained Journal": {"value": 42, "description": "Several pages are illegible, but the remaining entries describe a long river journey."},
    "Old Town Ledger": {"value": 55, "description": "A book of purchases, debts, and names from a settlement that no longer exists."},
    "Pressed Wildflowers": {"value": 24, "description": "A carefully preserved spray of flowers tucked between scraps of paper."},
    "Tarnished Locket": {"value": 85, "description": "The tiny portrait inside has faded almost completely."},
    "Carved Bone Token": {"value": 48, "description": "A smooth token marked with an unfamiliar trail symbol."},
    "Cracked Spyglass": {"value": 72, "description": "The lens is chipped, though a collector or navigator may still value it."},
    "Surveyor's Notes": {"value": 60, "description": "Measurements and route sketches for roads that may never have been built."},
    "Bundle of Old Letters": {"value": 30, "description": "Private correspondence tied with faded blue thread."},
    "Decorative Bottle": {"value": 18, "description": "Colored glass with no practical use beyond catching the light."},
    "Small Clay Idol": {"value": 68, "description": "A palm-sized figure recovered from an older layer of settlement."},
    "Brass Compass": {"value": 95, "description": "It points north reluctantly, but its engraved case is still handsome."},
    "Fossil Fragment": {"value": 76, "description": "A patterned piece of ancient stone suitable for a museum shelf."},
    "Foreign Coin": {"value": 40, "description": "A worn coin from a distant coast, no longer accepted as currency here."},
    "Miner's Token": {"value": 38, "description": "A stamped brass tally once exchanged at a mine storehouse."},
    "Sealed Spice Jar": {"value": 64, "description": "An aromatic jar whose wax seal has somehow survived."},
    "Hand-Painted Plate": {"value": 52, "description": "A decorative plate painted with a landscape of unfamiliar mountains."},
    "Ranger's Route Card": {"value": 46, "description": "A weathered card listing shelters, water sources, and safe crossings."},
    "Old Medical Text": {"value": 58, "description": "Outdated remedies share pages with surprisingly careful anatomical drawings."},
    "Silver Button": {"value": 32, "description": "One ornate button, polished smooth by years of use."},
    "Engraved Thimble": {"value": 44, "description": "A tiny silver thimble engraved with curling vines."},
    "Porcelain Songbird": {"value": 92, "description": "A delicate painted bird that survived its cabinet better than its owner did."},
    "Lacquered Puzzle Box": {"value": 118, "description": "A many-sided wooden box with a cleverly hidden latch and an empty velvet lining."},
    "Amber Bead Strand": {"value": 105, "description": "Warm amber beads threaded on surprisingly sturdy cord."},
    "Silver Candlestick": {"value": 126, "description": "A weighty old candlestick stamped with a nearly forgotten maker's mark."},
    "Clockwork Curio": {"value": 145, "description": "Brass gears turn inside a palm-sized case, though their original purpose is unclear."},
    "Ceremonial Key": {"value": 78, "description": "An ornate key made for display rather than any surviving lock."},
    "Field Bandage": {
        "value": 36, "description": "A clean field dressing that restores 20 HP.",
        "effect": "heal", "amount": 20,
    },
    "Focus Tonic": {
        "value": 52, "description": "A sharp herbal tonic that restores 12 focus.",
        "effect": "focus", "amount": 12,
    },
    "Restorative Salts": {
        "value": 30, "description": "A pungent travel remedy that restores 35 stamina.",
        "effect": "stamina", "amount": 35,
    },
    "Antidote Kit": {
        "value": 64, "description": "A compact kit that clears poison during map combat.",
        "effect": "cleanse", "amount": 1,
    },
    "Warding Chalk": {
        "value": 72, "description": "Prepared chalk that grants three guarded turns during map combat.",
        "effect": "guard", "amount": 3,
    },
    "Cartographer's Rubbing": {
        "value": 96, "description": "A charcoal rubbing that reveals the architecture of the current dungeon floor.",
        "effect": "dungeon_map", "amount": 1,
    },
    "Surveyor's Lens": {
        "value": 135, "description": "A fitted lens that improves passive trap discovery while it is carried.",
        "passive": "trap_scout", "amount": 0.12,
    },
    "Locksmith's Roll": {
        "value": 150, "description": "Fine picks and probes that improve trap disarming while they are carried.",
        "passive": "trap_disarm", "amount": 0.12,
    },
}

CONTAINER_ITEM_DATA.update({
    item_name: {
        "value": int(data.get("value", 0) or 0),
        "description": str(data.get("description", "A carefully recovered field specimen.")),
    }
    for item_name, data in EXCAVATION_FIND_DATA.items()
})

CONTAINER_PROFILES: Dict[str, Dict[str, object]] = {
    "bookshelf": {
        "name": "Bookshelf", "capacity": 120,
        "loot": ["Dog-Eared Field Guide", "Water-Stained Journal", "Old Town Ledger", "Pressed Wildflowers", "Bundle of Old Letters", "Old Medical Text"],
    },
    "shelf": {
        "name": "Shelf", "capacity": 160,
        "loot": ["Decorative Bottle", "Sealed Spice Jar", "Hand-Painted Plate", "Silver Button", "Ranger's Route Card"],
    },
    "cabinet": {
        "name": "Cabinet", "capacity": 180,
        "loot": ["Bundle of Old Letters", "Decorative Bottle", "Tarnished Locket", "Foreign Coin", "Silver Button"],
    },
    "wall_cabinet": {
        "name": "Wall Cabinet", "capacity": 140,
        "loot": ["Decorative Bottle", "Sealed Spice Jar", "Silver Button", "Bundle of Old Letters"],
    },
    "storage_chest": {
        "name": "Storage Chest", "capacity": 500,
        "loot": ["Bundle of Old Letters", "Decorative Bottle", "Hand-Painted Plate", "Miner's Token", "Foreign Coin"],
    },
    "nightstand": {
        "name": "Nightstand", "capacity": 80,
        "loot": ["Bundle of Old Letters", "Pressed Wildflowers", "Silver Button", "Tarnished Locket"],
    },
    "display_case": {
        "name": "Display Case", "capacity": 160,
        "loot": ["Hand-Painted Plate", "Porcelain Songbird", "Foreign Coin", "Carved Bone Token", "Tarnished Locket"],
    },
    "barrel": {
        "name": "Barrel", "capacity": 300,
        "loot": ["Sealed Spice Jar", "Decorative Bottle", "Field Snack", "Fiber", "Restorative Salts"],
    },
    "ruin_chest": {
        "name": "Ancient Chest", "capacity": 240,
        "loot": ["Carved Bone Token", "Cracked Spyglass", "Surveyor's Notes", "Small Clay Idol", "Brass Compass", "Fossil Fragment", "Foreign Coin", "Miner's Token"],
    },
    "crate": {
        "name": "Supply Crate", "capacity": 260,
        "loot": ["Ranger's Route Card", "Miner's Token", "Decorative Bottle", "Sealed Spice Jar", "Surveyor's Notes"],
    },
    "dresser": {
        "name": "Dresser", "capacity": 220,
        "loot": ["Bundle of Old Letters", "Silver Button", "Pressed Wildflowers", "Tarnished Locket"],
    },
    "wardrobe": {
        "name": "Wardrobe", "capacity": 320,
        "loot": ["Bundle of Old Letters", "Silver Button", "Pressed Wildflowers", "Carved Bone Token"],
    },
    "pantry": {
        "name": "Pantry", "capacity": 260,
        "loot": ["Sealed Spice Jar", "Decorative Bottle", "Hand-Painted Plate", "Old Town Ledger"],
    },
    "encounter_cache": {
        "name": "Recovered Cache", "capacity": 300,
        "loot": ["Ranger's Route Card", "Miner's Token", "Foreign Coin", "Sealed Spice Jar", "Surveyor's Notes", "Carved Bone Token"],
    },
    "store_seeds": {
        "name": "Seed Shelves", "capacity": 180,
        "loot": ["Turnip Seeds", "Potato Seeds", "Fiber", "Restorative Salts"],
    },
    "store_farm_supply": {
        "name": "Farm Supply Shelf", "capacity": 180,
        "loot": ["Fiber", "Wood", "Stone", "Field Snack", "Restorative Salts"],
    },
    "store_general_goods": {
        "name": "General Goods Display", "capacity": 180,
        "loot": ["Decorative Bottle", "Hand-Painted Plate", "Field Snack", "Engraved Thimble"],
    },
    "smith_crate": {
        "name": "Ore Crate", "capacity": 300,
        "loot": ["Coal", "Copper Ore", "Iron Ore", "Miner's Token", "Locksmith's Roll"],
    },
    "smith_coal": {
        "name": "Coal Bin", "capacity": 360,
        "loot": ["Coal", "Stone", "Miner's Token"],
    },
    "smith_tools": {
        "name": "Tool Rack", "capacity": 220,
        "loot": ["Ruin Scrap", "Miner's Token", "Locksmith's Roll", "Ceremonial Key"],
    },
    "civic_archive": {
        "name": "Records Archive", "capacity": 220,
        "loot": ["Old Town Ledger", "Surveyor's Notes", "Bundle of Old Letters", "Cartographer's Rubbing", "Ceremonial Key"],
    },
    "inn_pantry": {
        "name": "Inn Pantry", "capacity": 300,
        "loot": ["Field Snack", "Sealed Spice Jar", "Restorative Salts", "Decorative Bottle", "Hand-Painted Plate"],
    },
    "clinic_cabinet": {
        "name": "Medicine Cabinet", "capacity": 220,
        "loot": ["Field Bandage", "Focus Tonic", "Antidote Kit", "Potion", "Ether", "Old Medical Text"],
    },
    "clinic_supply": {
        "name": "Clinic Supply Shelf", "capacity": 260,
        "loot": ["Field Bandage", "Wild Herbs", "Fiber", "Restorative Salts", "Old Medical Text"],
    },
    "animal_feed": {
        "name": "Feed Bin", "capacity": 340,
        "loot": ["Hay", "Field Snack", "Fiber", "Sealed Spice Jar"],
    },
    "animal_medicine": {
        "name": "Animal Medicine Shelf", "capacity": 200,
        "loot": ["Wild Herbs", "Field Bandage", "Antidote Kit", "Fiber"],
    },
    "lumber_crate": {
        "name": "Lumber Rack", "capacity": 480,
        "loot": ["Wood", "Hardwood", "Fiber", "Surveyor's Notes"],
    },
    "market_produce": {
        "name": "Produce Crates", "capacity": 260,
        "loot": ["Turnip", "Potato", "Field Snack", "Sealed Spice Jar"],
    },
    "market_forage": {
        "name": "Forage Baskets", "capacity": 220,
        "loot": ["Wild Herbs", "Fiber", "Pressed Wildflowers", "Restorative Salts"],
    },
    "market_rare": {
        "name": "Rare Goods Case", "capacity": 160,
        "loot": ["Foreign Coin", "Amber Bead Strand", "Porcelain Songbird", "Clockwork Curio"],
    },
    "dungeon_archive": {
        "name": "Ruined Archive", "capacity": 180,
        "loot": [
            "Water-Stained Journal", "Old Town Ledger", "Old Medical Text",
            "Cartographer's Rubbing", "Focus Tonic", "Surveyor's Lens",
        ],
        "count_min": 1, "count_max": 3,
    },
    "dungeon_supply": {
        "name": "Abandoned Supply Crate", "capacity": 260,
        "loot": [
            "Field Bandage", "Restorative Salts", "Antidote Kit", "Warding Chalk",
            "Field Snack", "Coal", "Fiber", "Ruin Scrap", "Locksmith's Roll",
        ],
        "count_min": 2, "count_max": 4,
    },
    "dungeon_urn": {
        "name": "Funerary Urn", "capacity": 100,
        "loot": [
            "Foreign Coin", "Carved Bone Token", "Small Clay Idol", "Amber Bead Strand",
            "Silver Button", "Ceremonial Key", "Porcelain Songbird",
        ],
        "count_min": 1, "count_max": 2,
    },
}

CONTAINER_PROFILES.update({
    "household_dresser": {
        "name": "Household Dresser", "capacity": 180,
        "loot": ["Bundle of Old Letters", "Silver Button", "Pressed Wildflowers", "Tarnished Locket"],
        "count_min": 1, "count_max": 3,
    },
    "nursery_cabinet": {
        "name": "Nursery Cabinet", "capacity": 120,
        "loot": ["Pressed Wildflowers", "Silver Button", "Hand-Painted Plate", "Bundle of Old Letters"],
        "count_min": 1, "count_max": 2,
    },
    "guest_nightstand": {
        "name": "Guest Nightstand", "capacity": 80,
        "loot": ["Bundle of Old Letters", "Foreign Coin", "Ranger's Route Card", "Restorative Salts"],
        "count_min": 1, "count_max": 2,
    },
    "kitchen_cupboard": {
        "name": "Kitchen Cupboard", "capacity": 180,
        "loot": ["Sealed Spice Jar", "Hand-Painted Plate", "Field Snack", "Decorative Bottle"],
        "count_min": 1, "count_max": 3,
    },
    "office_desk": {
        "name": "Desk Drawers", "capacity": 100,
        "loot": ["Old Town Ledger", "Surveyor's Notes", "Bundle of Old Letters", "Ceremonial Key"],
        "count_min": 1, "count_max": 2,
    },
    "evidence_locker": {
        "name": "Evidence Locker", "capacity": 180,
        "loot": ["Foreign Coin", "Carved Bone Token", "Tarnished Locket", "Locksmith's Roll", "Ceremonial Key"],
        "count_min": 1, "count_max": 3,
    },
    "library_shelf": {
        "name": "Library Shelf", "capacity": 180,
        "loot": ["Dog-Eared Field Guide", "Old Town Ledger", "Old Medical Text", "Water-Stained Journal"],
        "count_min": 2, "count_max": 3,
    },
    "workshop_parts": {
        "name": "Workshop Parts Bin", "capacity": 240,
        "loot": ["Ruin Scrap", "Miner's Token", "Locksmith's Roll", "Coal", "Fiber"],
        "count_min": 1, "count_max": 3,
    },
    "linen_cupboard": {
        "name": "Linen Cupboard", "capacity": 220,
        "loot": ["Fiber", "Restorative Salts", "Pressed Wildflowers", "Bundle of Old Letters"],
        "count_min": 1, "count_max": 3,
    },
})


AUTHORED_CONTAINER_FIXTURES: Dict[str, Dict[str, Tuple[str, str, bool, str]]] = {
    "GeneralStoreInterior": {
        "s": ("store_seeds", "display", False, "General Store"),
        "f": ("store_farm_supply", "display", False, "General Store"),
        "b": ("store_general_goods", "display", False, "General Store"),
    },
    "BlacksmithInterior": {
        "o": ("smith_crate", "display", False, "Blacksmith"),
        "q": ("smith_coal", "display", False, "Blacksmith"),
        "t": ("smith_tools", "display", False, "Blacksmith"),
    },
    "LibraryInterior": {
        "l": ("civic_archive", "display", False, "Town library"),
    },
    "MayorHouseInterior": {
        "s": ("civic_archive", "display", False, "Mayor's office"),
    },
    "InnInterior": {
        "p": ("inn_pantry", "display", False, "Town inn"),
    },
    "FurnitureStoreInterior": {
        "L": ("bookshelf", "display", False, "Furniture Store"),
        "l": ("shelf", "display", False, "Furniture Store"),
        "U": ("dresser", "display", False, "Furniture Store"),
        "u": ("dresser", "display", False, "Furniture Store"),
    },
    "CarpenterStoreInterior": {
        "l": ("lumber_crate", "display", False, "Carpenter"),
    },
    "AnimalStoreInterior": {
        "f": ("animal_feed", "display", False, "Animal Store"),
        "m": ("animal_medicine", "display", False, "Animal Store"),
    },
    "ClinicInterior": {
        "m": ("clinic_cabinet", "display", False, "Town clinic"),
        "s": ("clinic_supply", "display", False, "Town clinic"),
    },
    "TownHallInterior": {
        "r": ("civic_archive", "display", False, "Town Hall"),
    },
    "MarketRowInterior": {
        "v": ("market_produce", "display", False, "Market vendor"),
        "f": ("market_forage", "display", False, "Market vendor"),
        "r": ("market_rare", "display", False, "Market vendor"),
    },
    "TownResidenceInterior": {
        "l": ("bookshelf", "display", False, "Local resident"),
        "s": ("cabinet", "display", False, "Local resident"),
        "u": ("dresser", "display", False, "Local resident"),
        "p": ("pantry", "display", False, "Local resident"),
    },
}

PLAYER_CONTAINER_DATA: Dict[str, Tuple[str, int, str]] = {
    "Chest": ("Storage Chest", 500, "chest"),
    "Storage Shed": ("Storage Shed", 4000, "shed"),
    "Bookshelf": ("Bookshelf", 120, "bookshelf"),
    "Library Bookcase": ("Library Bookcase", 360, "bookshelf"),
    "Shelf": ("Shelf", 160, "shelf"),
    "Nightstand": ("Nightstand", 80, "nightstand"),
    "Toy Shelf": ("Toy Shelf", 120, "shelf"),
    "Dresser": ("Dresser", 220, "dresser"),
    "Wardrobe": ("Wardrobe", 320, "wardrobe"),
    "Pantry": ("Pantry", 260, "pantry"),
    "Keepsake Chest": ("Keepsake Chest", 120, "keepsake"),
    "Display Counter": ("Display Counter", 500, "display_case"),
    "Storage Hutch": ("Storage Hutch", 600, "dresser"),
    "Reading Nook": ("Reading Nook", 320, "bookshelf"),
    "Dressing Vanity": ("Dressing Vanity", 240, "dresser"),
}
PLAYER_CONTAINER_DATA.update({
    item_name: (
        item_name,
        max(1, int(item_data.get("container_capacity", 200) or 200)),
        str(item_data.get("container_profile", "cabinet")),
    )
    for item_name, item_data in INFRASTRUCTURE_DATA.items()
    if item_data.get("container_profile")
})


class ContainerSystemMixin:
    def backpack_capacity(self) -> int:
        upgrades = max(0, int(getattr(self.state, "backpack_upgrades", 0) or 0))
        return BASE_BACKPACK_CAPACITY + upgrades * BACKPACK_UPGRADE_SIZE

    def backpack_used(self) -> int:
        inventory = self.state.inventory
        if isinstance(inventory, CapacityInventory):
            return inventory.used_slots()
        return sum(max(0, int(qty or 0)) for qty in inventory.values())

    def backpack_free(self) -> int:
        return max(0, self.backpack_capacity() - self.backpack_used())

    def backpack_fit_quantity(self, item_name: str) -> int:
        inventory = self.state.inventory
        if isinstance(inventory, CapacityInventory):
            return inventory.max_additional(item_name)
        return self.backpack_free()

    def backpack_upgrade_price(self) -> int:
        level = max(0, int(getattr(self.state, "backpack_upgrades", 0) or 0)) + 1
        return 500 * level * level

    def ensure_container_state(self) -> None:
        if not isinstance(getattr(self.state, "world_containers", None), dict):
            self.state.world_containers = {}
        self.state.backpack_upgrades = max(0, int(getattr(self.state, "backpack_upgrades", 0) or 0))
        self.state.inventory = capacity_inventory(self.state.inventory, self.backpack_capacity())

    def purchase_backpack_upgrade(self) -> bool:
        price = self.backpack_upgrade_price()
        if int(self.state.money) < price:
            self.set_message(f"A backpack expansion costs ${price}. You need ${price - int(self.state.money)} more.")
            return False
        self.state.money -= price
        self.state.backpack_upgrades += 1
        if isinstance(self.state.inventory, CapacityInventory):
            self.state.inventory.set_capacity(self.backpack_capacity())
        self.autosave_with_message(
            f"The shopkeeper fitted a larger pack frame. Capacity is now {self.backpack_capacity()} items."
        )
        return True

    def container_scope_key(self) -> str:
        location = str(getattr(self.state, "location", "Unknown") or "Unknown")
        if getattr(self, "on_wilderness_dungeon", lambda: False)():
            return f"dungeon:{self.state.current_dungeon_key}:floor:{self.state.current_dungeon_floor}"
        if getattr(self, "on_wilderness", lambda: False)():
            return f"wilderness:{self.state.wilderness_chunk_x},{self.state.wilderness_chunk_y}"
        if getattr(self, "on_procedural_town_interior", lambda: False)():
            return (
                f"procedural:{self.state.current_procedural_settlement_key}:"
                f"{self.state.current_procedural_building_id}:floor:{self.state.current_procedural_building_floor}"
            )
        if getattr(self, "on_wilderness_structure", lambda: False)():
            return f"structure:{self.state.current_wilderness_structure_key}"
        if getattr(self, "on_wilderness_outpost", lambda: False)():
            return f"outpost:{self.state.current_wilderness_outpost_key}"
        return f"location:{location}"

    def container_record_key(self, x: int, y: int, profile: str = "container") -> str:
        return f"{self.container_scope_key()}:{int(x)},{int(y)}:{profile}"

    def deterministic_container_contents(self, key: str, profile: str) -> Dict[str, int]:
        data = CONTAINER_PROFILES.get(profile, CONTAINER_PROFILES["shelf"])
        choices = list(data.get("loot", []))
        if not choices:
            return {}
        seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)
        rng = random.Random(seed)
        count_min = max(1, min(len(choices), int(data.get("count_min", 1) or 1)))
        count_max = max(
            count_min,
            min(len(choices), int(data.get("count_max", min(4, len(choices))) or min(4, len(choices)))),
        )
        max_quantity = max(1, int(data.get("max_quantity", 1) or 1))
        count = rng.randint(count_min, count_max)
        contents: Dict[str, int] = {}
        for item_name in rng.sample(choices, count):
            contents[str(item_name)] = rng.randint(1, max_quantity)
        if profile in {"ruin_chest", "crate"}:
            materials = rng.choice([
                {"Stone": rng.randint(2, 6)},
                {"Wood": rng.randint(2, 5), "Fiber": rng.randint(1, 3)},
                {"Coal": rng.randint(1, 3)},
            ])
            for item_name, qty in materials.items():
                contents[item_name] = contents.get(item_name, 0) + qty
        if profile in {"ruin_chest", "encounter_cache"}:
            level = max(1, int(getattr(self.state, "combat_level", 1) or 1))
            contents = add_random_reward_items(
                self.state,
                contents,
                f"world_container:{key}",
                level,
                gear_chance=0.11 if profile == "ruin_chest" else 0.07,
                consumable_chance=0.34,
                valuable_chance=0.52 if profile == "ruin_chest" else 0.30,
                quality_bonus=1 if profile == "ruin_chest" else 0,
                rng=rng,
            )
        recovered_table = rare_recovered_game_table(
            key,
            0.045
            if profile == "ruin_chest"
            else 0.012
            if profile in {"encounter_cache", "crate"}
            else 0.0,
        )
        if recovered_table:
            contents[recovered_table] = contents.get(recovered_table, 0) + 1
        return contents

    def create_container_record(
        self,
        key: str,
        x: int,
        y: int,
        profile: str,
        *,
        name: Optional[str] = None,
        take_policy: str = "free",
        allow_deposit: bool = False,
        capacity: Optional[int] = None,
        contents: Optional[Dict[str, int]] = None,
        owner: str = "",
        extra_action: str = "",
    ) -> Dict[str, object]:
        profile_data = CONTAINER_PROFILES.get(profile, CONTAINER_PROFILES["shelf"])
        record: Dict[str, object] = {
            "key": key,
            "scope": self.container_scope_key(),
            "x": int(x),
            "y": int(y),
            "profile": profile,
            "name": str(name or profile_data.get("name", "Container")),
            "capacity": max(1, int(capacity or profile_data.get("capacity", 200))),
            "contents": dict(contents if contents is not None else self.deterministic_container_contents(key, profile)),
            "take_policy": str(take_policy),
            "allow_deposit": bool(allow_deposit),
            "owner": str(owner),
            "opened": False,
            "extra_action": str(extra_action),
        }
        self.state.world_containers[key] = record
        return record

    def player_container_record(
        self,
        x: int,
        y: int,
        object_name: str,
        object_key: Optional[str] = None,
    ) -> Dict[str, object]:
        label, capacity, profile = PLAYER_CONTAINER_DATA[object_name]
        key = self.container_record_key(x, y, f"player:{object_name}")
        record = self.state.world_containers.get(key)
        if not isinstance(record, dict) and object_key:
            record = next(
                (
                    candidate
                    for candidate in self.state.world_containers.values()
                    if isinstance(candidate, dict)
                    and str(candidate.get("object_key", "")) == str(object_key)
                    and str(candidate.get("name", "")) == label
                ),
                None,
            )
        if not isinstance(record, dict):
            # Furniture movement changes its coordinate key. Reattach the first
            # matching orphaned record so moving a full chest never empties it.
            for old_key, candidate in list(self.state.world_containers.items()):
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("scope") != self.container_scope_key() or candidate.get("name") != label:
                    continue
                old_x, old_y = int(candidate.get("x", -1)), int(candidate.get("y", -1))
                _placed_key, old_object, _ax, _ay = self.placed_object_at(old_x, old_y)
                if old_object != object_name:
                    self.state.world_containers.pop(old_key, None)
                    candidate.update({"key": key, "x": int(x), "y": int(y)})
                    self.state.world_containers[key] = candidate
                    record = candidate
                    break
        if not isinstance(record, dict):
            extra = (
                "guides" if object_name in {"Bookshelf", "Shelf"}
                else "keepsakes" if object_name == "Keepsake Chest"
                else "outfit" if object_name in {"Dresser", "Wardrobe"}
                else "pantry" if object_name == "Pantry"
                else ""
            )
            record = self.create_container_record(
                key, x, y, profile, name=label, take_policy="player", allow_deposit=True,
                capacity=capacity, contents={}, owner="Player", extra_action=extra,
            )
        if object_key:
            record["object_key"] = str(object_key)
        if not bool(getattr(self.state, "container_storage_migrated", False)):
            legacy = getattr(self.state, "storage_inventory", {})
            if isinstance(legacy, dict) and any(int(qty or 0) > 0 for qty in legacy.values()):
                stored = record.setdefault("contents", {})
                for item_name, qty in legacy.items():
                    if int(qty or 0) > 0:
                        stored[str(item_name)] = int(stored.get(str(item_name), 0) or 0) + int(qty)
                self.state.storage_inventory = {}
            self.state.container_storage_migrated = True
        return record

    def player_container_record_for_object_key(
        self,
        object_key: str,
        object_name: str,
    ) -> Optional[Dict[str, object]]:
        if object_name not in PLAYER_CONTAINER_DATA:
            return None
        label = PLAYER_CONTAINER_DATA[object_name][0]
        records = getattr(self.state, "world_containers", {})
        if not isinstance(records, dict):
            return None
        tagged = next(
            (
                record
                for record in records.values()
                if isinstance(record, dict)
                and str(record.get("object_key", "")) == str(object_key)
                and str(record.get("name", "")) == label
            ),
            None,
        )
        if isinstance(tagged, dict):
            return tagged
        parsed = getattr(self, "parse_object_key", lambda _key: None)(str(object_key))
        if not parsed:
            return None
        _scope, x, y = parsed
        candidates = [
            record
            for record in records.values()
            if isinstance(record, dict)
            and str(record.get("take_policy", "")) == "player"
            and str(record.get("name", "")) == label
            and (int(record.get("x", -1)), int(record.get("y", -1))) == (int(x), int(y))
        ]
        if len(candidates) == 1:
            candidates[0]["object_key"] = str(object_key)
            return candidates[0]
        return None

    def placed_container_has_contents(self, object_key: str, object_name: str) -> bool:
        record = self.player_container_record_for_object_key(object_key, object_name)
        if not record:
            return False
        contents, _capacity, _policy = self.normalize_container_record(record)
        return any(int(quantity or 0) > 0 for quantity in contents.values()) or int(record.get("money", 0) or 0) > 0

    def placed_container_store_block_reason(self, object_key: str, object_name: str) -> str:
        if self.placed_container_has_contents(object_key, object_name):
            return "empty this storage container first, or move it instead"
        return ""

    def clear_placed_container_state(self, object_key: str, object_name: str) -> None:
        record = self.player_container_record_for_object_key(object_key, object_name)
        if not record:
            return
        for key, candidate in list(self.state.world_containers.items()):
            if candidate is record:
                self.state.world_containers.pop(key, None)

    def rekey_placed_container_state(
        self,
        old_object_key: str,
        new_object_key: str,
        object_name: str,
    ) -> None:
        record = self.player_container_record_for_object_key(old_object_key, object_name)
        if not record:
            return
        record["object_key"] = str(new_object_key)
        parsed = getattr(self, "parse_object_key", lambda _key: None)(str(new_object_key))
        if parsed:
            _scope, x, y = parsed
            record["x"], record["y"] = int(x), int(y)

    @staticmethod
    def procedural_room_container_profile(
        building_type: str,
        room_role: str,
        room_id: str,
        tile: str,
    ) -> str:
        """Map a generated fixture through its room purpose before its glyph."""
        building_type = str(building_type or "").lower()
        room_role = str(room_role or "").lower()
        room_id = str(room_id or "").lower()
        tile = str(tile or "")
        if room_role in {"primary_bedroom", "bedroom"} and tile == "d":
            return "household_dresser"
        if room_role == "nursery" and tile == "P":
            return "nursery_cabinet"
        if room_role == "guest_room" and tile == "d":
            return "guest_nightstand"
        if room_role == "kitchen" and tile == "P":
            return "inn_pantry" if building_type == "inn" else "kitchen_cupboard"
        if room_role == "pantry" and tile in {"s", "P"}:
            return "inn_pantry" if building_type == "inn" else "pantry"
        if room_role in {"study", "office"} and tile == "d":
            return "office_desk"
        if room_role in {"stacks", "reading", "circulation"} and tile in {"l", "L"}:
            return "library_shelf"
        if room_role in {"archive", "records"} and tile in {"l", "L", "d", "P", "s"}:
            return "civic_archive"
        if building_type == "sheriff_office" and (
            "evidence" in room_id or room_role in {"armory", "storage"}
        ) and tile in {"s", "P", "x"}:
            return "evidence_locker"
        if room_role in {"examination", "clinic_ward", "pharmacy"} and tile in {"+", "s", "P"}:
            return "clinic_cabinet"
        if building_type == "clinic" and room_role == "storage" and tile in {"s", "P"}:
            return "clinic_supply"
        if building_type == "inn" and room_role == "storage" and tile in {"s", "P"}:
            return "linen_cupboard"
        if building_type in {"carpenter"} and room_role in {
            "woodshop", "lumber", "workshop", "finishing", "storage", "delivery"
        } and tile in {"s", "x", "a"}:
            return "lumber_crate"
        if building_type in {"workshop", "blacksmith"} and room_role in {
            "forge", "workshop", "materials", "finishing", "storage", "delivery"
        } and tile in {"s", "x", "a"}:
            return "workshop_parts"
        if room_role in {"sales", "display", "stockroom", "delivery"} and tile in {"$", "s", "P"}:
            return {
                "general_store": "store_general_goods",
                "market_stall": "market_produce",
            }.get(building_type, "shelf")
        if room_role == "produce" and tile in {"$", "s", "P"}:
            return "market_produce"
        if room_role == "storage" and tile in {"s", "P"}:
            return "cabinet"
        return ""

    def static_container_profile_at(self, x: int, y: int) -> Optional[Tuple[str, str, bool, str]]:
        if not getattr(self, "in_active_bounds", lambda _x, _y: False)(x, y):
            return None
        tile = self.active_map()[y][x]
        location = str(getattr(self.state, "location", ""))
        catalog_furniture = getattr(self, "catalog_furniture_at", lambda _x, _y: None)(x, y)
        if isinstance(catalog_furniture, dict):
            furniture_name = str(catalog_furniture.get("name", ""))
            furniture_data = INFRASTRUCTURE_DATA.get(furniture_name, {})
            profile = str(furniture_data.get("container_profile", ""))
            if profile:
                player_owned = bool(
                    getattr(self, "on_house", lambda: False)()
                    or getattr(self, "on_player_owned_procedural_residence", lambda: False)()
                )
                room_role = str(catalog_furniture.get("room_role", "")).lower()
                public_roles = {
                    "sales", "display", "produce", "showroom", "circulation",
                    "stacks", "reading", "public_hall", "dining", "lobby",
                }
                if player_owned:
                    return profile, "player", True, "Player"
                if getattr(self, "on_town_interior", lambda: False)() or room_role in public_roles:
                    return profile, "display", False, getattr(self, "location_label", lambda: "Public building")()
                return profile, "theft", False, getattr(self, "location_label", lambda: "Local resident")()
        if getattr(self, "on_wilderness_dungeon", lambda: False)():
            dungeon_profiles = {
                "$": "ruin_chest",
                "l": "dungeon_archive",
                "L": "dungeon_archive",
                "s": "dungeon_supply",
                "u": "dungeon_urn",
            }
            profile = dungeon_profiles.get(tile)
            return (profile, "free", False, "") if profile else None
        if getattr(self, "on_wilderness_structure", lambda: False)() and tile in {"$", "l", "L", "s"}:
            return ("ruin_chest" if tile == "$" else "bookshelf" if tile in {"l", "L"} else "crate"), "free", False, ""
        if getattr(self, "on_wilderness_outpost", lambda: False)() and tile in {"l", "L"}:
            return "bookshelf", "display", False, "Ranger service"
        authored = AUTHORED_CONTAINER_FIXTURES.get(location, {}).get(tile)
        if authored:
            return authored
        custom_container_profile = str(
            BUILDING_TEMPLATE_FURNISHING_DATA.get(str(tile), {}).get("container_profile", "")
        )
        procedural_interior = getattr(self, "on_procedural_town_interior", lambda: False)()
        authored_interior = getattr(self, "on_town_interior", lambda: False)()
        procedural_building_record = (
            getattr(self, "current_procedural_town_building", lambda: None)() or {}
            if procedural_interior
            else {}
        )
        procedural_room = (
            getattr(self, "procedural_town_room_at_position", lambda *_args, **_kwargs: None)(
                x,
                y,
                procedural_building_record,
            )
            if procedural_interior
            else None
        )
        procedural_building_type = str(
            procedural_building_record.get(
                "type_id",
                getattr(self.state, "current_procedural_building_id", ""),
            )
        ).lower()
        procedural_room_role = str(
            procedural_room.get("role", "") if isinstance(procedural_room, dict) else ""
        ).lower()
        procedural_room_id = str(
            procedural_room.get("source_id", procedural_room.get("id", ""))
            if isinstance(procedural_room, dict)
            else ""
        )
        procedural_room_profile = self.procedural_room_container_profile(
            procedural_building_type,
            procedural_room_role,
            procedural_room_id,
            str(tile),
        ) if procedural_interior else ""
        if (
            (procedural_interior or authored_interior)
            and (
                (procedural_interior and tile in {"l", "L", "s", "u", "p"})
                or custom_container_profile
                or procedural_room_profile
            )
        ):
            building_record = procedural_building_record
            authored_types = {
                "GeneralStoreInterior": "general_store",
                "BlacksmithInterior": "blacksmith",
                "LibraryInterior": "library",
                "MayorHouseInterior": "home",
                "InnInterior": "inn",
                "FurnitureStoreInterior": "furniture_store",
                "CarpenterStoreInterior": "carpenter",
                "AnimalStoreInterior": "animal_store",
                "ClinicInterior": "clinic",
                "TownHallInterior": "town_hall",
                "MarketRowInterior": "market_stall",
                "MuseumInterior": "library",
                "TownResidenceInterior": "home",
            }
            building_type = (
                procedural_building_type
                if procedural_interior
                else authored_types.get(location, "home")
            )
            is_business = building_type in {
                "general_store", "blacksmith", "clinic", "inn", "town_hall",
                "sheriff_office", "library", "furniture_store", "carpenter",
                "animal_store", "market", "market_stall", "workshop",
            }
            player_owned = bool(
                procedural_interior
                and getattr(self, "on_player_owned_procedural_residence", lambda: False)()
            )
            public_room_roles = {
                "sales", "display", "produce", "showroom", "circulation", "stacks",
            }
            if player_owned:
                policy = "player"
                owner = "Player"
            elif procedural_room_profile:
                policy = "display" if procedural_room_role in public_room_roles else "theft"
                room_label = procedural_room_role.replace("_", " ").title() or "Private room"
                owner = f"{building_record.get('name', 'Local property')} - {room_label}"
            else:
                policy = "display" if is_business else "theft"
                owner = "Business stock" if is_business else "Local resident"
            business_profiles = {
                "general_store": {
                    "s": "store_general_goods", "l": "store_general_goods", "L": "store_general_goods",
                    "H": "store_general_goods", "i": "store_general_goods", "j": "store_general_goods",
                    "g": "store_general_goods", "W": "store_general_goods", "y": "store_general_goods",
                    "z": "store_general_goods", "V": "store_general_goods", "X": "store_general_goods",
                },
                "blacksmith": {
                    "s": "smith_crate", "l": "smith_tools", "L": "smith_tools",
                    "j": "smith_tools", "g": "smith_tools", "W": "smith_tools",
                    "y": "smith_crate", "z": "smith_crate", "X": "smith_coal",
                },
                "workshop": {
                    "s": "smith_crate", "j": "smith_tools", "g": "smith_tools",
                    "W": "smith_tools", "y": "smith_crate", "z": "smith_crate", "X": "smith_coal",
                },
                "clinic": {
                    "s": "clinic_supply", "u": "clinic_cabinet", "j": "clinic_supply",
                    "z": "clinic_supply", "y": "clinic_supply", "g": "clinic_cabinet",
                    "W": "clinic_cabinet", "N": "clinic_cabinet",
                },
                "inn": {
                    "p": "inn_pantry", "s": "inn_pantry", "j": "inn_pantry",
                    "g": "inn_pantry", "W": "inn_pantry", "z": "inn_pantry",
                    "X": "inn_pantry", "Z": "inn_pantry",
                },
                "library": {
                    "l": "civic_archive", "L": "civic_archive", "s": "civic_archive",
                    "H": "civic_archive", "i": "civic_archive", "j": "civic_archive",
                    "g": "civic_archive", "W": "civic_archive", "V": "civic_archive",
                },
                "town_hall": {
                    "l": "civic_archive", "L": "civic_archive", "s": "civic_archive",
                    "H": "civic_archive", "i": "civic_archive", "j": "civic_archive",
                    "g": "civic_archive", "W": "civic_archive", "y": "civic_archive",
                },
                "sheriff_office": {
                    "l": "civic_archive", "L": "civic_archive", "s": "smith_tools",
                    "H": "civic_archive", "i": "civic_archive", "j": "civic_archive",
                    "g": "civic_archive", "W": "civic_archive", "y": "smith_tools",
                },
                "carpenter": {
                    "s": "lumber_crate", "l": "lumber_crate", "L": "lumber_crate",
                    "j": "lumber_crate", "g": "lumber_crate", "W": "lumber_crate",
                    "y": "lumber_crate", "z": "lumber_crate", "X": "lumber_crate",
                },
                "animal_store": {
                    "s": "animal_feed", "p": "animal_feed", "u": "animal_medicine",
                    "j": "animal_feed", "z": "animal_feed", "X": "animal_feed",
                    "g": "animal_medicine", "W": "animal_medicine",
                },
                "market": {
                    "s": "market_produce", "l": "market_rare", "L": "market_rare",
                    "j": "market_produce", "z": "market_produce", "X": "market_produce",
                    "H": "market_rare", "i": "market_rare", "V": "market_rare",
                },
                "market_stall": {
                    "s": "market_produce", "j": "market_produce", "z": "market_produce",
                    "X": "market_produce", "H": "market_rare", "i": "market_rare",
                    "V": "market_rare",
                },
            }
            profile = procedural_room_profile or business_profiles.get(building_type, {}).get(tile)
            if not profile:
                profile = custom_container_profile or (
                    "bookshelf" if tile in {"l", "L"}
                    else "dresser" if tile == "u"
                    else "pantry" if tile == "p"
                    else "shelf"
                )
            return profile, policy, player_owned, owner
        return None

    def wilderness_encounter_container_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if not getattr(self, "on_wilderness", lambda: False)():
            return None
        visual = getattr(self, "wilderness_random_combat_visual_at", lambda _x, _y: None)(x, y)
        if not isinstance(visual, dict):
            return None
        name = str(visual.get("name", "Encounter cache"))
        lowered = name.lower()
        if not any(word in lowered for word in ("crate", "cargo", "cart", "remains", "nest", "den", "carapace")):
            return None
        record = visual.get("container")
        if isinstance(record, dict):
            return record
        encounter = getattr(self, "wilderness_random_combat_record", lambda *_args, **_kwargs: {})(
            self.state.wilderness_chunk_x,
            self.state.wilderness_chunk_y,
            create=False,
        )
        encounter_id = str(encounter.get("id", "encounter"))
        key = f"{self.container_scope_key()}:encounter:{encounter_id}:{int(x)},{int(y)}"
        contents = self.deterministic_container_contents(key, "encounter_cache")
        if "crate" in lowered or "cargo" in lowered or "cart" in lowered:
            contents["Wood"] = int(contents.get("Wood", 0) or 0) + 2
        elif "nest" in lowered or "den" in lowered:
            contents["Fiber"] = int(contents.get("Fiber", 0) or 0) + 2
        record = {
            "key": key,
            "scope": self.container_scope_key(),
            "x": int(x),
            "y": int(y),
            "profile": "encounter_cache",
            "name": name,
            "capacity": 300,
            "contents": contents,
            "take_policy": "free",
            "allow_deposit": False,
            "owner": "",
            "opened": False,
            "extra_action": "",
        }
        visual["container"] = record
        return record

    def outpost_supply_container_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if not getattr(self, "on_wilderness_outpost", lambda: False)():
            return None
        if not getattr(self, "in_active_bounds", lambda _x, _y: False)(x, y):
            return None
        if self.active_map()[y][x] != "s":
            return None
        key = self.container_record_key(x, y, "outpost_supplies")
        record = self.state.world_containers.get(key)
        if not isinstance(record, dict):
            record = self.create_container_record(
                key,
                x,
                y,
                "crate",
                name="Outpost Supply Locker",
                take_policy="free",
                allow_deposit=False,
                capacity=500,
                contents={},
                owner="Regional ranger service",
            )
            record["profile"] = "outpost_supplies"
        week = str(getattr(self, "stronghold_cache_week_key", lambda: "")())
        if str(record.get("last_restock_week", "")) != week:
            cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
            region = getattr(self, "wilderness_region_record", lambda *_args: {})(cx, cy)
            already_claimed = (
                not record.get("last_restock_week")
                and isinstance(region, dict)
                and str(region.get("outpost_last_supply_week", "")) == week
            )
            if not already_claimed:
                level = int(getattr(self, "wilderness_region_project_level", lambda *_args: 0)(cx, cy) or 0)
                refill = {"Field Snack": 1, "Wood": 1 + level, "Fiber": 1 + level}
                contents, capacity, _policy = self.normalize_container_record(record)
                free = max(0, capacity - self.container_used(contents))
                for item_name, quantity in refill.items():
                    accepted = min(max(0, int(quantity)), free)
                    if accepted <= 0:
                        continue
                    contents[item_name] = int(contents.get(item_name, 0) or 0) + accepted
                    free -= accepted
            record["last_restock_week"] = week
        return record

    def dungeon_chest_container_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if not getattr(self, "on_wilderness_dungeon", lambda: False)():
            return None
        if not getattr(self, "in_active_bounds", lambda _x, _y: False)(x, y):
            return None
        if self.active_map()[y][x] != "$":
            return None
        key = self.container_record_key(x, y, "ruin_chest")
        record = self.state.world_containers.get(key)
        if isinstance(record, dict):
            return record
        dungeon_key = str(getattr(self.state, "current_dungeon_key", ""))
        floor = max(1, int(getattr(self.state, "current_dungeon_floor", 1) or 1))
        feature_id = str(
            getattr(self, "wilderness_dungeon_feature_id", lambda px, py, level=1: f"F{level}:{px},{py}")(
                x, y, floor
            )
        )
        dungeon_record = getattr(self, "dungeon_record", lambda _key: {})(dungeon_key)
        opened = {
            str(value)
            for value in dungeon_record.get("opened_chests", [])
        } if isinstance(dungeon_record, dict) else set()
        if feature_id in opened:
            money, contents = 0, {}
        elif hasattr(self, "wilderness_dungeon_chest_loot"):
            money, contents = self.wilderness_dungeon_chest_loot(
                dungeon_key, floor, x, y
            )
        else:
            money, contents = 0, self.deterministic_container_contents(key, "ruin_chest")
        record = self.create_container_record(
            key,
            x,
            y,
            "ruin_chest",
            name="Dungeon Chest",
            take_policy="free",
            allow_deposit=False,
            capacity=500,
            contents=contents,
            owner="",
        )
        record["money"] = max(0, int(money or 0))
        record["dungeon_chest_id"] = feature_id
        record["dungeon_key"] = dungeon_key
        return record

    def container_display_stock(self, profile: str = "") -> Dict[str, int]:
        profile_stock = {
            "store_seeds": {"Turnip Seeds": 12, "Potato Seeds": 8},
            "store_farm_supply": {"Fiber": 10, "Wood": 8, "Stone": 8, "Restorative Salts": 2},
            "store_general_goods": {"Potion": 4, "Field Snack": 5, "Decorative Bottle": 2},
            "smith_crate": {"Copper Ore": 10, "Iron Ore": 6, "Stone": 12},
            "smith_coal": {"Coal": 12},
            "smith_tools": {"Copper Bar": 3, "Ruin Scrap": 4, "Locksmith's Roll": 1},
            "civic_archive": {"Dog-Eared Field Guide": 2, "Old Town Ledger": 1, "Surveyor's Notes": 2},
            "inn_pantry": {"Field Snack": 8, "Sealed Spice Jar": 2, "Restorative Salts": 3},
            "clinic_cabinet": {"Potion": 8, "Ether": 5, "Field Bandage": 5, "Antidote Kit": 2},
            "clinic_supply": {"Wild Herbs": 6, "Fiber": 8, "Field Bandage": 4},
            "animal_feed": {"Hay": 20, "Fiber": 8, "Field Snack": 4},
            "animal_medicine": {"Wild Herbs": 6, "Field Bandage": 3, "Antidote Kit": 2},
            "lumber_crate": {"Wood": 20, "Stone": 12, "Hardwood": 5, "Fiber": 8},
            "market_produce": {"Turnip": 6, "Potato": 6, "Field Snack": 4},
            "market_forage": {"Wild Herbs": 6, "Fiber": 8, "Pressed Wildflowers": 2},
            "market_rare": {"Foreign Coin": 2, "Amber Bead Strand": 1, "Porcelain Songbird": 1},
        }
        if profile in profile_stock:
            return dict(profile_stock[profile])
        if getattr(self, "on_general_store", lambda: False)():
            return {"Turnip Seeds": 12, "Potato Seeds": 8, "Potion": 4, "Fiber": 10}
        if getattr(self, "on_blacksmith_interior", lambda: False)():
            return {"Coal": 8, "Copper Ore": 10, "Iron Ore": 6, "Copper Bar": 3}
        if getattr(self, "on_carpenter_store", lambda: False)():
            return {"Wood": 20, "Stone": 12, "Hardwood": 5, "Fiber": 8}
        if getattr(self, "on_clinic", lambda: False)():
            return {"Potion": 8, "Ether": 5, "Wild Herbs": 6, "Old Medical Text": 1}
        if getattr(self, "on_animal_store", lambda: False)():
            return {"Hay": 20, "Milk": 4, "Bird Egg": 6, "Fiber": 8}
        if getattr(self, "on_library_interior", lambda: False)():
            return {"Dog-Eared Field Guide": 2, "Old Town Ledger": 1, "Old Medical Text": 2, "Bundle of Old Letters": 1}
        if getattr(self, "on_furniture_store", lambda: False)():
            return {"Decorative Bottle": 3, "Hand-Painted Plate": 2, "Pressed Wildflowers": 2}
        return {}

    def world_container_at(self, x: int, y: int, create: bool = True) -> Optional[Dict[str, object]]:
        self.ensure_container_state()
        pile = None
        if (getattr(self, "on_wilderness", lambda: False)() or getattr(self, "on_wilderness_dungeon", lambda: False)()):
            pile = getattr(self, "dungeon_floor_loot_at", lambda _x, _y: None)(x, y)
        if isinstance(pile, dict):
            return {"_loot_pile": pile, "name": f"Remains of {pile.get('source', 'an enemy')}"}

        dropped = self.dropped_pack_at(x, y)
        if dropped:
            return dropped

        encounter_container = self.wilderness_encounter_container_at(x, y)
        if encounter_container:
            return encounter_container

        outpost_supplies = self.outpost_supply_container_at(x, y)
        if outpost_supplies:
            return outpost_supplies

        dungeon_chest = self.dungeon_chest_container_at(x, y)
        if dungeon_chest:
            return dungeon_chest

        placed = None
        if getattr(self, "on_farm_work_land", lambda: False)() or getattr(self, "on_house", lambda: False)() or getattr(self, "on_player_owned_procedural_residence", lambda: False)():
            placed_key, placed, ax, ay = self.placed_object_at(x, y)
            if placed in PLAYER_CONTAINER_DATA and ax is not None and ay is not None:
                return self.player_container_record(int(ax), int(ay), str(placed), object_key=placed_key)

        catalog_furniture = getattr(self, "catalog_furniture_at", lambda _x, _y: None)(x, y)
        if isinstance(catalog_furniture, dict):
            furniture_name = str(catalog_furniture.get("name", ""))
            profile = str(INFRASTRUCTURE_DATA.get(furniture_name, {}).get("container_profile", ""))
            static = self.static_container_profile_at(x, y) if profile else None
            if static:
                profile, policy, allow_deposit, owner = static
                furniture_key = getattr(self, "furniture_state_key", lambda *_args, **_kwargs: f"{x},{y}")(
                    furniture_name, x, y, catalog_furniture,
                )
                key = f"{self.container_scope_key()}:catalog-furniture:{furniture_key}:{profile}"
                record = self.state.world_containers.get(key)
                if isinstance(record, dict):
                    if not record.get("extra_action"):
                        record["extra_action"] = (
                            "outfit" if any(word in furniture_name.lower() for word in ("dresser", "wardrobe", "vanity"))
                            else "guides" if profile in {"bookshelf", "civic_archive"}
                            else "keepsakes" if "keepsake" in furniture_name.lower()
                            else "pantry" if profile in {"pantry", "inn_pantry"}
                            else ""
                        )
                    return record
                if not create:
                    return None
                stock = self.container_display_stock(profile) if policy == "display" else None
                extra_action = (
                    "outfit" if any(word in furniture_name.lower() for word in ("dresser", "wardrobe", "vanity"))
                    else "guides" if profile in {"bookshelf", "civic_archive"}
                    else "keepsakes" if "keepsake" in furniture_name.lower()
                    else "pantry" if profile in {"pantry", "inn_pantry"}
                    else ""
                )
                return self.create_container_record(
                    key, x, y, profile, name=furniture_name,
                    take_policy=policy, allow_deposit=allow_deposit, owner=owner,
                    contents={} if policy == "player" else (stock if stock else None),
                    extra_action=extra_action,
                )

        static = self.static_container_profile_at(x, y)
        if not static:
            return None
        profile, policy, allow_deposit, owner = static
        key = self.container_record_key(x, y, profile)
        record = self.state.world_containers.get(key)
        if isinstance(record, dict):
            return record
        if not create:
            return None
        stock = self.container_display_stock(profile) if policy == "display" else None
        initial_contents = {} if policy == "player" else (stock if stock else None)
        return self.create_container_record(
            key, x, y, profile, take_policy=policy, allow_deposit=allow_deposit,
            owner=owner, contents=initial_contents,
        )

    def dropped_pack_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        containers = getattr(self.state, "world_containers", {})
        if not isinstance(containers, dict):
            return None
        record = containers.get(self.container_record_key(x, y, "dropped_pack"))
        if (
            isinstance(record, dict)
            and record.get("profile") == "dropped_pack"
            and any(int(qty or 0) > 0 for qty in dict(record.get("contents", {})).values())
        ):
            return record
        return None

    def open_world_container_at(self, x: int, y: int) -> bool:
        record = self.world_container_at(x, y)
        if not record:
            return False
        self.show_world_container(record)
        return True

    def container_interaction_hint_at(self, x: int, y: int) -> str:
        static = self.static_container_profile_at(x, y)
        if not static:
            return ""
        profile, policy, _allow_deposit, owner = static
        name = str(CONTAINER_PROFILES.get(profile, {}).get("name", "container"))
        if policy == "display":
            return f"Z/Enter: browse {name.lower()}"
        if policy == "theft":
            return f"Z/Enter: search {owner.lower() if owner else 'owned'} {name.lower()}"
        return f"Z/Enter: open {name.lower()}"

    def normalize_container_record(self, record: Dict[str, object]) -> Tuple[Dict[str, int], int, str]:
        pile = record.get("_loot_pile")
        if isinstance(pile, dict):
            contents = pile.setdefault("items", {})
            return contents, 10_000, "free"
        contents = record.setdefault("contents", {})
        if not isinstance(contents, dict):
            contents = {}
            record["contents"] = contents
        return contents, max(1, int(record.get("capacity", 200) or 200)), str(record.get("take_policy", "free"))

    def container_item_description(self, item_name: str) -> str:
        generated = generated_equipment_record(self.state, item_name)
        if generated:
            return str(generated.get("description", "A singular piece of recovered equipment."))
        data = CONTAINER_ITEM_DATA.get(item_name)
        if data:
            return str(data.get("description", "A recovered object."))
        infrastructure = INFRASTRUCTURE_DATA.get(item_name)
        if infrastructure:
            return str(infrastructure.get("description", "A placeable object."))
        if item_name.endswith(" Seeds"):
            return "A packet of plantable seeds."
        return "A useful material or object that can be carried, stored, used, or sold."

    def container_item_sell_price(self, item_name: str) -> int:
        generated = generated_equipment_record(self.state, item_name)
        if generated:
            enhanced = apply_equipment_enhancement(
                self.state, str(generated.get("slot", "")), item_name, generated
            )
            return max(0, int(enhanced.get("value", 0) or 0))
        return max(0, int(CONTAINER_ITEM_DATA.get(item_name, {}).get("value", 0) or 0))

    def container_item_is_usable(self, item_name: str) -> bool:
        return str(CONTAINER_ITEM_DATA.get(item_name, {}).get("effect", "")) in {
            "heal", "focus", "stamina", "cleanse", "guard", "dungeon_map",
        }

    def container_item_use_hint(self, item_name: str) -> str:
        data = CONTAINER_ITEM_DATA.get(item_name, {})
        effect = str(data.get("effect", ""))
        amount = max(0, int(data.get("amount", 0) or 0))
        return {
            "heal": f"+{amount} HP",
            "focus": f"+{amount} focus",
            "stamina": f"+{amount} stamina",
            "cleanse": "clears poison in map combat",
            "guard": f"{amount} guarded map-combat turns",
            "dungeon_map": "reveals the current dungeon floor",
        }.get(effect, "")

    def container_item_detail_lines(self, item_name: str) -> List[str]:
        generated = generated_equipment_record(self.state, item_name)
        if generated:
            generated = apply_equipment_enhancement(
                self.state, str(generated.get("slot", "")), item_name, generated
            )
            affixes = [str(value) for value in generated.get("affixes", []) if str(value)]
            stats = []
            for key, label in (
                ("attack", "Attack"),
                ("defense", "Defense"),
                ("max_hp", "Max HP"),
                ("max_focus", "Max Focus"),
            ):
                amount = int(generated.get(key, 0) or 0)
                if amount:
                    stats.append(f"+{amount} {label}")
            if str(generated.get("slot", "")) == "weapon":
                range_min = max(1, int(generated.get("range_min", 1) or 1))
                range_max = max(range_min, int(generated.get("range_max", range_min) or range_min))
                stats.append(f"Range {range_min}-{range_max}")
            lines = [
                str(generated.get("description", "A singular piece of recovered equipment.")),
                f"Rarity: {generated.get('rarity', 'Common')} | Item level: {generated.get('item_level', 1)}",
                f"Slot: {str(generated.get('slot', '')).title()} | Value: ${int(generated.get('value', 0) or 0)}",
            ]
            if int(generated.get("enhancement", 0) or 0):
                lines.append(
                    f"Enhancement: +{generated.get('enhancement')} / +{generated.get('enhancement_cap')}"
                )
            if stats:
                lines.append(f"Equipment: {', '.join(stats)}")
            if affixes:
                lines.append(f"Traits: {', '.join(affixes)}")
            return lines
        data = CONTAINER_ITEM_DATA.get(item_name)
        if not data:
            return []
        lines = [str(data.get("description", "A recovered object."))]
        usable = self.container_item_use_hint(item_name)
        if usable:
            lines.append(f"Use: {usable}.")
        passive = str(data.get("passive", ""))
        amount = float(data.get("amount", 0.0) or 0.0)
        if passive == "trap_scout":
            lines.append(f"Carried benefit: +{int(round(amount * 100))}% trap discovery chance.")
        elif passive == "trap_disarm":
            lines.append(f"Carried benefit: +{int(round(amount * 100))}% trap disarm chance.")
        return lines

    def container_passive_bonus(self, passive: str) -> float:
        total = 0.0
        inventory = getattr(self.state, "inventory", {})
        for item_name, quantity in inventory.items():
            if int(quantity or 0) <= 0:
                continue
            data = CONTAINER_ITEM_DATA.get(str(item_name), {})
            if str(data.get("passive", "")) == str(passive):
                total += float(data.get("amount", 0.0) or 0.0)
        return min(0.30, max(0.0, total))

    def container_item_can_help_now(self, item_name: str) -> bool:
        data = CONTAINER_ITEM_DATA.get(item_name, {})
        effect = str(data.get("effect", ""))
        amount = max(0, int(data.get("amount", 0) or 0))
        if effect == "stamina":
            return int(getattr(self.state, "stamina", 0)) < int(getattr(self, "max_stamina", lambda: 0)())
        if effect in {"heal", "focus"}:
            from ascii_farmstead_combat import build_player_combat_profile

            profile = build_player_combat_profile(self.state)
            current_key = "current_hp" if effect == "heal" else "focus"
            maximum_key = "max_hp" if effect == "heal" else "max_focus"
            return int(profile.get(current_key, 0) or 0) < int(profile.get(maximum_key, 0) or 0)
        if effect == "cleanse":
            if not bool(getattr(self, "map_native_combat_active", lambda: False)()):
                return False
            combat = getattr(self, "dungeon_roguelike_record", lambda: {})()
            return int(combat.get("poison_turns", 0) or 0) > 0
        if effect == "guard":
            return bool(getattr(self, "map_native_combat_active", lambda: False)()) and amount > 0
        if effect == "dungeon_map":
            if not bool(getattr(self, "on_wilderness_dungeon", lambda: False)()):
                return False
            grid = self.active_map()
            explored = getattr(self, "dungeon_explored_tiles", lambda: set())()
            return any(
                tile not in {"#", " "} and (x, y) not in explored
                for y, row in enumerate(grid)
                for x, tile in enumerate(row)
            )
        return False

    def use_container_item(self, item_name: str) -> bool:
        if int(getattr(self.state, "inventory", {}).get(item_name, 0) or 0) <= 0:
            self.set_message(f"You do not have any {item_name}.")
            return False
        if not self.container_item_is_usable(item_name):
            self.set_message(f"{item_name} is not usable from inventory.")
            return False
        if not self.container_item_can_help_now(item_name):
            self.set_message(f"{item_name} would not help you right now.")
            return False

        from ascii_farmstead_combat import build_player_combat_profile

        data = CONTAINER_ITEM_DATA[item_name]
        effect = str(data.get("effect", ""))
        amount = max(0, int(data.get("amount", 0) or 0))
        result = ""
        if effect == "heal":
            profile = build_player_combat_profile(self.state)
            before = int(profile.get("current_hp", 0) or 0)
            maximum = max(1, int(profile.get("max_hp", before) or before or 1))
            self.state.combat_current_hp = min(maximum, before + amount)
            result = f"restored {int(self.state.combat_current_hp) - before} HP"
        elif effect == "focus":
            profile = build_player_combat_profile(self.state)
            before = int(profile.get("focus", 0) or 0)
            maximum = max(0, int(profile.get("max_focus", before) or before or 0))
            self.state.combat_focus = min(maximum, before + amount)
            result = f"restored {int(self.state.combat_focus) - before} focus"
        elif effect == "stamina":
            restored = int(getattr(self, "restore_stamina", lambda _amount: 0)(amount) or 0)
            result = f"restored {restored} stamina"
        elif effect == "cleanse":
            combat = self.dungeon_roguelike_record()
            combat["poison_turns"] = 0
            result = "cleared the poison"
        elif effect == "guard":
            combat = self.dungeon_roguelike_record()
            combat["guard_turns"] = max(amount, int(combat.get("guard_turns", 0) or 0))
            result = f"granted {amount} guarded turns"
        elif effect == "dungeon_map":
            grid = self.active_map()
            combat = self.dungeon_roguelike_record()
            explored = set(getattr(self, "dungeon_explored_tiles", lambda: set())())
            explored.update(
                (x, y)
                for y, row in enumerate(grid)
                for x, tile in enumerate(row)
                if tile not in {"#", " "}
            )
            combat["explored_tiles"] = [
                self.dungeon_feature_key(x, y)
                for x, y in sorted(explored, key=lambda point: (point[1], point[0]))
            ]
            _regions, room_lookup = self.dungeon_room_regions()
            combat["revealed_rooms"] = sorted(set(room_lookup.values()))
            self._dungeon_explored_cache_signature = None
            self._dungeon_visibility_cache_signature = None
            result = "revealed the current dungeon floor"

        self.state.inventory[item_name] = int(self.state.inventory.get(item_name, 0) or 0) - 1
        self.autosave_with_message(f"Used {item_name}: {result}.")
        return True

    def container_used(self, contents: Dict[str, int]) -> int:
        return sum(max(0, int(qty or 0)) for qty in contents.values())

    def container_apply_theft(self, record: Dict[str, object], quantity: int) -> None:
        if str(record.get("take_policy", "")) != "theft" or quantity <= 0:
            return
        day_key = f"{getattr(self.state, 'year', 1)}:{getattr(self.state, 'season', '')}:{getattr(self.state, 'day', 1)}"
        if record.get("last_theft_day") == day_key:
            return
        record["last_theft_day"] = day_key
        if getattr(self, "current_procedural_town_plan", lambda: None)() and hasattr(self, "adjust_procedural_town_reputation"):
            self.adjust_procedural_town_reputation(-3, "Took property without permission")

    def take_from_container(self, record: Dict[str, object], item_name: str, quantity: int, autosave: bool = True) -> int:
        contents, _capacity, policy = self.normalize_container_record(record)
        if policy == "display":
            self.set_message("Those goods belong here. Speak to the responsible shopkeeper or resident instead.")
            return 0
        available = max(0, int(contents.get(item_name, 0) or 0))
        requested = min(available, max(0, int(quantity)))
        quantity = min(requested, self.backpack_fit_quantity(item_name))
        if quantity <= 0:
            self.set_message("Your backpack is full." if self.backpack_free() <= 0 else "There is nothing left to take.")
            return 0
        before = int(self.state.inventory.get(item_name, 0) or 0)
        self.state.inventory[item_name] = before + quantity
        accepted = max(0, int(self.state.inventory.get(item_name, 0) or 0) - before)
        contents[item_name] = available - accepted
        self.container_apply_theft(record, accepted)
        if accepted and hasattr(self, "record_quest_event"):
            profile = str(record.get("profile", record.get("container_profile", "container")) or "container")
            self.record_quest_event(
                "loot", target_name=item_name, target_id=item_name,
                target_tags=["item", profile], amount=accepted,
                location=str(getattr(self.state, "location", "")),
                note=f"Recovered {accepted} {item_name} from {record.get('name', 'a container')}.",
            )
        if autosave:
            verb = "Stole" if policy == "theft" else "Took"
            remaining = max(0, available - accepted)
            remainder = f" {remaining} remain here." if remaining > 0 and accepted < requested else ""
            self.autosave_with_message(
                f"{verb} {accepted} {item_name}.{remainder} "
                f"Backpack {self.backpack_used()}/{self.backpack_capacity()}."
            )
        return accepted

    def take_container_money(self, record: Dict[str, object], autosave: bool = True) -> int:
        pile = record.get("_loot_pile")
        source = pile if isinstance(pile, dict) else record
        money = max(0, int(source.get("money", 0) or 0))
        if money <= 0:
            return 0
        if str(record.get("take_policy", "free")) == "display":
            return 0
        self.state.money += money
        source["money"] = 0
        self.container_apply_theft(record, money)
        if hasattr(self, "record_quest_event"):
            self.record_quest_event(
                "loot", target_name="Money", target_id="money", target_tags=["money", "currency"],
                amount=money, location=str(getattr(self.state, "location", "")),
                note=f"Recovered {money}g from {record.get('name', 'a container')}.",
            )
        if autosave:
            verb = "Stole" if str(record.get("take_policy", "")) == "theft" else "Took"
            self.autosave_with_message(f"{verb} {money}g.")
        return money

    def remove_empty_loot_pile(self, record: Dict[str, object]) -> None:
        pile = record.get("_loot_pile")
        if isinstance(pile, dict):
            contents = dict(pile.get("items", {}) or {})
            if int(pile.get("money", 0) or 0) <= 0 and not any(int(qty or 0) > 0 for qty in contents.values()):
                floor_loot = self.dungeon_floor_loot()
                if pile in floor_loot:
                    floor_loot.remove(pile)
            return
        chest_id = str(record.get("dungeon_chest_id", ""))
        dungeon_key = str(record.get("dungeon_key", ""))
        if not chest_id or not dungeon_key:
            return
        contents, _capacity, _policy = self.normalize_container_record(record)
        if int(record.get("money", 0) or 0) > 0 or any(
            int(quantity or 0) > 0 for quantity in contents.values()
        ):
            return
        dungeon_record = getattr(self, "dungeon_record", lambda _key: {})(dungeon_key)
        if not isinstance(dungeon_record, dict):
            return
        opened = [str(value) for value in dungeon_record.get("opened_chests", [])]
        if chest_id not in opened:
            opened.append(chest_id)
            dungeon_record["opened_chests"] = opened

    def take_all_from_container(self, record: Dict[str, object]) -> int:
        contents, _capacity, policy = self.normalize_container_record(record)
        if policy == "display":
            self.set_message("This is display stock. Purchase it from the person responsible for the building.")
            return 0
        money = self.take_container_money(record, autosave=False)
        taken = 0
        for item_name in sorted(contents):
            if self.backpack_fit_quantity(item_name) <= 0:
                continue
            taken += self.take_from_container(record, item_name, int(contents.get(item_name, 0) or 0), autosave=False)
        self.remove_empty_loot_pile(record)
        if taken or money:
            bits = []
            if money:
                bits.append(f"{money}g")
            if taken:
                bits.append(f"{taken} item(s)")
            suffix = " Your backpack is full." if self.backpack_free() <= 0 else ""
            self.autosave_with_message(f"Took {', '.join(bits)}.{suffix}")
        else:
            self.set_message("There is nothing you can take.")
        return taken

    def deposit_into_container(self, record: Dict[str, object]) -> bool:
        contents, capacity, _policy = self.normalize_container_record(record)
        if not bool(record.get("allow_deposit", False)):
            self.set_message("You cannot store your belongings in this container.")
            return False
        free = max(0, capacity - self.container_used(contents))
        carried = [
            (name, max(0, int(qty) - equipped_inventory_reserve(self.state, name)))
            for name, qty in sorted(self.state.inventory.items())
            if int(qty or 0) - equipped_inventory_reserve(self.state, name) > 0
        ]
        items = [MenuItem(label=name, value=name, enabled=free > 0, hint=f"x{qty}") for name, qty in carried]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select("Store Item", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if choice is None or choice.value == MENU_BACK:
            return False
        item_name = str(choice.value)
        maximum = min(free, int(self.state.inventory.get(item_name, 0) or 0))
        quantity = self.vertical_quantity_select(
            "Store Quantity", item_name, 0, max_qty=maximum, start_qty=maximum,
            panel_width=LEFT_PANEL_WIDTH, panel_height=LEFT_PANEL_HEIGHT, return_back=True,
        )
        if quantity == MENU_BACK or quantity is None or int(quantity) <= 0:
            return False
        quantity = int(quantity)
        self.state.inventory[item_name] -= quantity
        contents[item_name] = int(contents.get(item_name, 0) or 0) + quantity
        self.autosave_with_message(f"Stored {quantity} {item_name} in {record.get('name', 'the container')}.")
        return True

    def deposit_all_into_container(self, record: Dict[str, object]) -> int:
        contents, capacity, _policy = self.normalize_container_record(record)
        if not bool(record.get("allow_deposit", False)):
            self.set_message("You cannot store your belongings in this container.")
            return 0
        free = max(0, capacity - self.container_used(contents))
        stored = 0
        for item_name, carried in sorted(self.state.inventory.items()):
            carried = max(
                0,
                int(carried or 0) - equipped_inventory_reserve(self.state, item_name),
            )
            if carried <= 0 or free <= 0:
                continue
            quantity = min(carried, free)
            self.state.inventory[item_name] = carried - quantity
            contents[item_name] = int(contents.get(item_name, 0) or 0) + quantity
            stored += quantity
            free -= quantity
        if stored:
            suffix = " The container is full." if free <= 0 else ""
            self.autosave_with_message(
                f"Stored {stored} carried item(s) in {record.get('name', 'the container')}.{suffix}"
            )
        else:
            self.set_message("There is nothing that can be stored here.")
        return stored

    def inspect_container_item(self, item_name: str, quantity: int, record: Dict[str, object]) -> None:
        value = self.container_item_sell_price(item_name)
        rows = [
            self.container_item_description(item_name), "", f"Quantity here: {quantity}",
            f"Shipping value: ${value} each" if value else "Shipping value: depends on its ordinary use",
            f"Owner: {record.get('owner') or 'unclaimed'}",
        ]
        self.vertical_panel_view(item_name, rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)

    def inspect_container_money(self, quantity: int, record: Dict[str, object]) -> None:
        self.vertical_panel_view(
            "Coins",
            [
                "Currency kept in this container.",
                "",
                f"Quantity here: {max(0, int(quantity))}g",
                f"Owner: {record.get('owner') or 'unclaimed'}",
            ],
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )

    def take_container_items_menu(self, record: Dict[str, object]) -> None:
        """Continuously collect whole stacks without per-item quantity prompts."""
        while True:
            contents, _capacity, policy = self.normalize_container_record(record)
            if policy == "display":
                self.set_message("This is display stock. Purchase it from the person responsible for the building.")
                return
            pile = record.get("_loot_pile")
            money_source = pile if isinstance(pile, dict) else record
            money = max(0, int(money_source.get("money", 0) or 0))
            take_label = "Steal" if policy == "theft" else ("Withdraw" if policy == "player" else "Take")
            items: List[MenuItem] = []
            if money:
                items.append(
                    MenuItem(
                        label=f"Coins x{money}",
                        value="__money__",
                        enabled=True,
                        hint=f"{take_label.lower()} entire stack",
                    )
                )
            for item_name, quantity in sorted(contents.items()):
                quantity = max(0, int(quantity or 0))
                if quantity <= 0:
                    continue
                fit = self.backpack_fit_quantity(str(item_name))
                hint = f"x{quantity} | {take_label.lower()} entire stack"
                if fit < quantity:
                    hint = f"x{quantity} | room for {max(0, fit)}"
                items.append(
                    MenuItem(
                        label=str(item_name),
                        value=f"item:{item_name}",
                        enabled=fit > 0,
                        hint=hint,
                    )
                )
            if not items:
                self.remove_empty_loot_pile(record)
                self.set_message("There is nothing left to take.")
                return
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(
                f"{take_label} Items",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
                hotkeys={"r": "__take_all__"},
                hotkey_footer="Select: take full stack | R take all",
            )
            if choice is None or choice.value == MENU_BACK:
                self.remove_empty_loot_pile(record)
                return
            if choice.value == "__take_all__":
                self.take_all_from_container(record)
            elif choice.value == "__money__":
                self.take_container_money(record)
            elif str(choice.value).startswith("item:"):
                item_name = str(choice.value)[5:]
                self.take_from_container(
                    record,
                    item_name,
                    int(contents.get(item_name, 0) or 0),
                )

    def inspect_container_contents_menu(self, record: Dict[str, object]) -> None:
        """Inspect any number of stacks while remaining in the contents browser."""
        while True:
            contents, _capacity, _policy = self.normalize_container_record(record)
            pile = record.get("_loot_pile")
            money_source = pile if isinstance(pile, dict) else record
            money = max(0, int(money_source.get("money", 0) or 0))
            items: List[MenuItem] = []
            if money:
                items.append(MenuItem(label=f"Coins x{money}", value="__money__", enabled=True, hint="inspect currency"))
            for item_name, quantity in sorted(contents.items()):
                quantity = max(0, int(quantity or 0))
                if quantity <= 0:
                    continue
                value = self.container_item_sell_price(str(item_name))
                hint = f"x{quantity}"
                if value:
                    hint += f" | ${value} each"
                items.append(MenuItem(label=str(item_name), value=f"item:{item_name}", enabled=True, hint=hint))
            if not items:
                self.set_message("The container is empty.")
                return
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(
                "Inspect Contents",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
                hotkey_footer="Select an item to inspect",
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "__money__":
                self.inspect_container_money(money, record)
            elif str(choice.value).startswith("item:"):
                item_name = str(choice.value)[5:]
                self.inspect_container_item(
                    item_name,
                    int(contents.get(item_name, 0) or 0),
                    record,
                )

    def container_item_menu(self, record: Dict[str, object], item_name: str) -> None:
        """Legacy extension hook: inspect one named stack without nested actions."""
        contents, _capacity, _policy = self.normalize_container_record(record)
        quantity = max(0, int(contents.get(item_name, 0) or 0))
        if quantity > 0:
            self.inspect_container_item(item_name, quantity, record)

    def show_world_container(self, record: Dict[str, object]) -> None:
        record["opened"] = True
        while True:
            contents, capacity, policy = self.normalize_container_record(record)
            pile = record.get("_loot_pile")
            money_source = pile if isinstance(pile, dict) else record
            money = max(0, int(money_source.get("money", 0) or 0))
            used = self.container_used(contents)
            title = str(record.get("name", "Container"))
            items: List[MenuItem] = []
            stack_count = sum(1 for quantity in contents.values() if int(quantity or 0) > 0)
            available = stack_count + (1 if money else 0)
            if policy != "display":
                action_label = "Steal items" if policy == "theft" else ("Withdraw items" if policy == "player" else "Take items")
                items.append(
                    MenuItem(
                        label=action_label,
                        value="__take__",
                        enabled=available > 0,
                        hint=f"{available} stack(s) | select to take full stacks",
                    )
                )
            items.append(
                MenuItem(
                    label="Inspect contents",
                    value="__inspect__",
                    enabled=available > 0,
                    hint=f"{available} stack(s)" if available else "empty",
                )
            )
            if bool(record.get("allow_deposit", False)):
                items.append(MenuItem(label="Store carried item", value="__deposit__", enabled=used < capacity and self.backpack_used() > 0, hint=f"{used}/{capacity} stored"))
                items.append(MenuItem(label="Store all carried items", value="__deposit_all__", enabled=used < capacity and self.backpack_used() > 0, hint="fill available space"))
            if record.get("extra_action") == "guides":
                items.append(MenuItem(label="Read household guides", value="__guides__", enabled=True))
            if record.get("extra_action") == "keepsakes":
                items.append(MenuItem(label="Review family keepsakes", value="__keepsakes__", enabled=True))
            if record.get("extra_action") == "outfit":
                items.append(MenuItem(label="Arrange clothes", value="__outfit__", enabled=True))
            if record.get("extra_action") == "pantry":
                items.append(MenuItem(label="Review pantry", value="__pantry__", enabled=True))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            hotkeys = {}
            footer_parts = []
            if policy != "display" and available > 0:
                hotkeys["r"] = "__take_all__"
                footer_parts.append("R take all")
            if bool(record.get("allow_deposit", False)):
                hotkeys["t"] = "__deposit_all__"
                footer_parts.append("T store all")
            hotkey_footer = " | ".join(footer_parts) if footer_parts else "Select a section"
            choice = self.vertical_panel_select(
                title, items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
                hotkeys=hotkeys, hotkey_footer=hotkey_footer,
            )
            if choice is None or choice.value == MENU_BACK:
                self.remove_empty_loot_pile(record)
                self.set_message(f"Closed {title.lower()}.")
                return
            if choice.value == "__take_all__":
                self.take_all_from_container(record)
            elif choice.value == "__take__":
                self.take_container_items_menu(record)
            elif choice.value == "__inspect__":
                self.inspect_container_contents_menu(record)
            elif choice.value == "__deposit__":
                self.deposit_into_container(record)
            elif choice.value == "__deposit_all__":
                self.deposit_all_into_container(record)
            elif choice.value == "__guides__":
                self.show_bookshelf_menu()
            elif choice.value == "__keepsakes__":
                self.vertical_panel_view("Keepsake Chest", self.family_event_log_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "__outfit__":
                if hasattr(self, "show_player_color_mirror_menu"):
                    self.show_player_color_mirror_menu()
                else:
                    self.set_message("You sort coats, boots, and work clothes into something presentable.")
            elif choice.value == "__pantry__":
                self.set_message("The pantry labels make it easier to plan meals and supplies for a long trip.")

    def drop_rejected_inventory_near_player(self) -> Dict[str, int]:
        inventory = self.state.inventory
        if not isinstance(inventory, CapacityInventory):
            return {}
        rejected = inventory.take_rejected()
        if not rejected:
            return {}
        x, y = int(self.state.player_x), int(self.state.player_y)
        key = self.container_record_key(x, y, "dropped_pack")
        record = self.state.world_containers.get(key)
        if not isinstance(record, dict):
            record = self.create_container_record(
                key, x, y, "shelf", name="Dropped Pack", take_policy="free", allow_deposit=False,
                capacity=100_000, contents={}, owner="Player",
            )
            record["profile"] = "dropped_pack"
        contents = record.setdefault("contents", {})
        for item_name, qty in rejected.items():
            contents[item_name] = int(contents.get(item_name, 0) or 0) + int(qty)
        return rejected

    def player_storage_records(self) -> List[Dict[str, object]]:
        self.ensure_container_state()
        records = [
            record for record in self.state.world_containers.values()
            if isinstance(record, dict) and str(record.get("take_policy", "")) == "player"
        ]
        return sorted(records, key=lambda record: (str(record.get("scope", "")), str(record.get("name", "")), int(record.get("x", 0)), int(record.get("y", 0))))

    def show_player_storage_index(self):
        records = self.player_storage_records()
        if not records:
            self.set_message("Interact with a placed chest, shelf, wardrobe, pantry, or Storage Shed to establish storage.")
            return MENU_BACK
        items = []
        for index, record in enumerate(records):
            contents, capacity, _policy = self.normalize_container_record(record)
            used = self.container_used(contents)
            scope = str(record.get("scope", "")).replace("location:", "")
            items.append(MenuItem(label=f"{record.get('name', 'Storage')} - {scope}", value=index, enabled=True, hint=f"{used}/{capacity}"))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select("Owned Storage", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if choice is None or choice.value == MENU_BACK:
            return MENU_BACK
        record = records[int(choice.value)]
        contents, capacity, _policy = self.normalize_container_record(record)
        rows = [
            f"Location: {str(record.get('scope', 'unknown')).replace('location:', '')}",
            f"Stored: {self.container_used(contents)}/{capacity}",
            "",
            "Contents:",
        ]
        rows.extend(
            f"- {item_name} x{int(quantity)}"
            for item_name, quantity in sorted(contents.items())
            if int(quantity or 0) > 0
        )
        if len(rows) == 4:
            rows.append("- Empty")
        rows.extend([
            "",
            "This is an index only. Travel to the property and interact with the physical container to transfer items.",
        ])
        self.vertical_panel_view(
            str(record.get("name", "Owned Storage")),
            rows,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )
        self.set_message("Reviewed owned storage. Physical containers must be accessed in person.")
        return "viewed"
