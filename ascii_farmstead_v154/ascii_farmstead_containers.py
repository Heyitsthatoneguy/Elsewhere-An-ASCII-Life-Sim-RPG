from __future__ import annotations

"""Persistent world containers, carrying capacity, and loot browsing."""

import hashlib
import random
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK
from ascii_farmstead_inventory import CapacityInventory, capacity_inventory
from ascii_farmstead_ui import MenuItem


BASE_BACKPACK_CAPACITY = 200
BACKPACK_UPGRADE_SIZE = 50

CONTAINER_ITEM_DATA: Dict[str, Dict[str, object]] = {
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
}

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
    "ruin_chest": {
        "name": "Ancient Chest", "capacity": 240,
        "loot": ["Carved Bone Token", "Cracked Spyglass", "Surveyor's Notes", "Small Clay Idol", "Brass Compass", "Fossil Fragment", "Foreign Coin", "Miner's Token"],
    },
    "crate": {
        "name": "Supply Crate", "capacity": 260,
        "loot": ["Ranger's Route Card", "Miner's Token", "Decorative Bottle", "Sealed Spice Jar", "Surveyor's Notes"],
    },
}

PLAYER_CONTAINER_DATA: Dict[str, Tuple[str, int, str]] = {
    "Chest": ("Storage Chest", 500, "chest"),
    "Storage Shed": ("Storage Shed", 4000, "shed"),
    "Bookshelf": ("Bookshelf", 120, "bookshelf"),
    "Shelf": ("Shelf", 160, "shelf"),
    "Dresser": ("Dresser", 220, "dresser"),
    "Wardrobe": ("Wardrobe", 320, "wardrobe"),
    "Pantry": ("Pantry", 260, "pantry"),
    "Keepsake Chest": ("Keepsake Chest", 120, "keepsake"),
}


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
        count = rng.randint(1, min(4, len(choices)))
        contents: Dict[str, int] = {}
        for item_name in rng.sample(choices, count):
            contents[str(item_name)] = rng.randint(1, 2 if profile in {"shelf", "crate"} else 1)
        if profile in {"ruin_chest", "crate"}:
            materials = rng.choice([
                {"Stone": rng.randint(2, 6)},
                {"Wood": rng.randint(2, 5), "Fiber": rng.randint(1, 3)},
                {"Coal": rng.randint(1, 3)},
            ])
            for item_name, qty in materials.items():
                contents[item_name] = contents.get(item_name, 0) + qty
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

    def player_container_record(self, x: int, y: int, object_name: str) -> Dict[str, object]:
        label, capacity, profile = PLAYER_CONTAINER_DATA[object_name]
        key = self.container_record_key(x, y, f"player:{object_name}")
        record = self.state.world_containers.get(key)
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
            extra = "guides" if object_name in {"Bookshelf", "Shelf"} else ("keepsakes" if object_name == "Keepsake Chest" else "")
            record = self.create_container_record(
                key, x, y, profile, name=label, take_policy="player", allow_deposit=True,
                capacity=capacity, contents={}, owner="Player", extra_action=extra,
            )
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

    def static_container_profile_at(self, x: int, y: int) -> Optional[Tuple[str, str, bool, str]]:
        if not getattr(self, "in_active_bounds", lambda _x, _y: False)(x, y):
            return None
        tile = self.active_map()[y][x]
        location = str(getattr(self.state, "location", ""))
        if getattr(self, "on_wilderness_dungeon", lambda: False)() and tile == "$":
            return "ruin_chest", "free", False, ""
        if getattr(self, "on_wilderness_structure", lambda: False)() and tile in {"$", "l", "L", "s", "c"}:
            return ("ruin_chest" if tile == "$" else "bookshelf" if tile in {"l", "L"} else "cabinet"), "free", False, ""
        if getattr(self, "on_wilderness_outpost", lambda: False)() and tile in {"l", "L"}:
            return "bookshelf", "display", False, "Ranger service"
        commercial_active = any(
            getattr(self, method, lambda: False)()
            for method in (
                "on_general_store", "on_blacksmith_interior", "on_furniture_store",
                "on_carpenter_store", "on_animal_store", "on_clinic", "on_museum", "on_market_row",
            )
        )
        if commercial_active and tile in {"l", "L", "s"}:
            return ("bookshelf" if tile in {"l", "L"} else "shelf"), "display", False, "Shop stock"
        if getattr(self, "on_library_interior", lambda: False)() and tile in {"l", "L", "s"}:
            return "bookshelf", "display", False, "Town library"
        if getattr(self, "on_procedural_town_interior", lambda: False)() and tile in {"l", "L", "s", "c"}:
            building = str(getattr(self.state, "current_procedural_building_id", "")).lower()
            is_business = any(word in building for word in ("shop", "store", "clinic", "inn", "hall", "station", "library"))
            policy = "display" if is_business else "theft"
            owner = "Business stock" if is_business else "Local resident"
            profile = "bookshelf" if tile in {"l", "L"} else ("cabinet" if tile == "c" else "shelf")
            return profile, policy, False, owner
        if location in {"MayorHouseInterior", "InnInterior", "TownResidenceInterior"} and tile in {"l", "L", "s", "c"}:
            profile = "bookshelf" if tile in {"l", "L"} else ("cabinet" if tile == "c" else "shelf")
            return profile, "display", False, "Resident property"
        return None

    def container_display_stock(self) -> Dict[str, int]:
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

        placed = None
        if getattr(self, "on_farm_work_land", lambda: False)() or getattr(self, "on_house", lambda: False)() or getattr(self, "on_player_owned_procedural_residence", lambda: False)():
            _key, placed, ax, ay = self.placed_object_at(x, y)
            if placed in PLAYER_CONTAINER_DATA and ax is not None and ay is not None:
                return self.player_container_record(int(ax), int(ay), str(placed))

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
        stock = self.container_display_stock() if policy == "display" else None
        return self.create_container_record(
            key, x, y, profile, take_policy=policy, allow_deposit=allow_deposit,
            owner=owner, contents=stock if stock else None,
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
        data = CONTAINER_ITEM_DATA.get(item_name)
        if data:
            return str(data.get("description", "A recovered object."))
        if item_name.endswith(" Seeds"):
            return "A packet of plantable seeds."
        return "A useful material or object that can be carried, stored, used, or sold."

    def container_item_sell_price(self, item_name: str) -> int:
        return max(0, int(CONTAINER_ITEM_DATA.get(item_name, {}).get("value", 0) or 0))

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
        quantity = min(available, max(0, int(quantity)), self.backpack_fit_quantity(item_name))
        if quantity <= 0:
            self.set_message("Your backpack is full." if self.backpack_free() <= 0 else "There is nothing left to take.")
            return 0
        before = int(self.state.inventory.get(item_name, 0) or 0)
        self.state.inventory[item_name] = before + quantity
        accepted = max(0, int(self.state.inventory.get(item_name, 0) or 0) - before)
        contents[item_name] = available - accepted
        self.container_apply_theft(record, accepted)
        if autosave:
            verb = "Stole" if policy == "theft" else "Took"
            self.autosave_with_message(f"{verb} {accepted} {item_name}. Backpack {self.backpack_used()}/{self.backpack_capacity()}.")
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
        if autosave:
            self.autosave_with_message(f"Took {money}g.")
        return money

    def remove_empty_loot_pile(self, record: Dict[str, object]) -> None:
        pile = record.get("_loot_pile")
        if not isinstance(pile, dict):
            return
        contents = dict(pile.get("items", {}) or {})
        if int(pile.get("money", 0) or 0) <= 0 and not any(int(qty or 0) > 0 for qty in contents.values()):
            floor_loot = self.dungeon_floor_loot()
            if pile in floor_loot:
                floor_loot.remove(pile)

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
        free = max(0, capacity - self.container_used(contents))
        carried = [(name, int(qty)) for name, qty in sorted(self.state.inventory.items()) if int(qty or 0) > 0]
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

    def inspect_container_item(self, item_name: str, quantity: int, record: Dict[str, object]) -> None:
        value = self.container_item_sell_price(item_name)
        rows = [
            self.container_item_description(item_name), "", f"Quantity here: {quantity}",
            f"Shipping value: ${value} each" if value else "Shipping value: depends on its ordinary use",
            f"Owner: {record.get('owner') or 'unclaimed'}",
        ]
        self.vertical_panel_view(item_name, rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)

    def container_item_menu(self, record: Dict[str, object], item_name: str) -> None:
        contents, _capacity, policy = self.normalize_container_record(record)
        while int(contents.get(item_name, 0) or 0) > 0:
            quantity = int(contents.get(item_name, 0) or 0)
            take_label = "Steal" if policy == "theft" else "Take"
            items = [MenuItem(label="Inspect", value="inspect", enabled=True, hint=self.container_item_description(item_name))]
            if policy != "display":
                items.extend([
                    MenuItem(label=f"{take_label} one", value="one", enabled=self.backpack_fit_quantity(item_name) > 0, hint=f"backpack {self.backpack_used()}/{self.backpack_capacity()}"),
                    MenuItem(label=f"{take_label} quantity", value="quantity", enabled=self.backpack_fit_quantity(item_name) > 0, hint=f"x{quantity} here"),
                ])
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(item_name, items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "inspect":
                self.inspect_container_item(item_name, quantity, record)
            elif choice.value == "one":
                self.take_from_container(record, item_name, 1)
            elif choice.value == "quantity":
                maximum = min(quantity, self.backpack_fit_quantity(item_name))
                selected = self.vertical_quantity_select(
                    take_label, item_name, 0, max_qty=maximum, start_qty=maximum,
                    panel_width=LEFT_PANEL_WIDTH, panel_height=LEFT_PANEL_HEIGHT, return_back=True,
                )
                if selected != MENU_BACK and selected is not None and int(selected) > 0:
                    self.take_from_container(record, item_name, int(selected))

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
            if money:
                items.append(MenuItem(label=f"Coins x{money}", value="__money__", enabled=policy != "display", hint="currency"))
            for item_name, quantity in sorted(contents.items()):
                if int(quantity or 0) > 0:
                    value = self.container_item_sell_price(str(item_name))
                    hint = f"x{int(quantity)}"
                    if value:
                        hint += f" | ${value} each"
                    items.append(MenuItem(label=str(item_name), value=f"item:{item_name}", enabled=True, hint=hint))
            if bool(record.get("allow_deposit", False)):
                items.append(MenuItem(label="Store carried item", value="__deposit__", enabled=used < capacity and self.backpack_used() > 0, hint=f"{used}/{capacity} stored"))
            if record.get("extra_action") == "guides":
                items.append(MenuItem(label="Read household guides", value="__guides__", enabled=True))
            if record.get("extra_action") == "keepsakes":
                items.append(MenuItem(label="Review family keepsakes", value="__keepsakes__", enabled=True))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(
                title, items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
                hotkeys={"r": "__take_all__"}, hotkey_footer="R take all",
            )
            if choice is None or choice.value == MENU_BACK:
                self.remove_empty_loot_pile(record)
                self.set_message(f"Closed {title.lower()}.")
                return
            if choice.value == "__take_all__":
                self.take_all_from_container(record)
            elif choice.value == "__money__":
                self.take_container_money(record)
            elif choice.value == "__deposit__":
                self.deposit_into_container(record)
            elif choice.value == "__guides__":
                self.show_bookshelf_menu()
            elif choice.value == "__keepsakes__":
                self.vertical_panel_view("Keepsake Chest", self.family_event_log_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif str(choice.value).startswith("item:"):
                self.container_item_menu(record, str(choice.value)[5:])

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
        self.show_world_container(records[int(choice.value)])
        return "opened"
