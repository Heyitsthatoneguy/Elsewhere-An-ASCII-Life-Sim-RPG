from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import FISH_DATA, FOOD_DATA


COMBAT_WEAPON_DATA: Dict[str, Dict[str, object]] = {
    "Rusty Sword": {
        "id": "rusty_sword",
        "name": "Rusty Sword",
        "slot": "weapon",
        "attack": 2,
        "range_min": 1,
        "range_max": 1,
        "description": "A worn blade, better than a tool handle.",
        "cost": {"money": 0, "items": {}},
        "unlock": "starter",
    },
    "Stone Club": {
        "id": "stone_club",
        "name": "Stone Club",
        "slot": "weapon",
        "attack": 2,
        "defense": 1,
        "range_min": 1,
        "range_max": 1,
        "description": "A heavy early club that favors caution over speed.",
        "cost": {"money": 450, "items": {"Stone": 25, "Fiber": 5}},
        "unlock": "blacksmith",
        "tags": ["blunt"],
    },
    "Copper Sword": {
        "id": "copper_sword",
        "name": "Copper Sword",
        "slot": "weapon",
        "attack": 3,
        "range_min": 1,
        "range_max": 1,
        "description": "A reliable blade forged from town copper.",
        "cost": {"money": 800, "items": {"Copper Bar": 2, "Coal": 1}},
        "unlock": "blacksmith",
        "tags": ["blade"],
    },
    "Iron Sword": {
        "id": "iron_sword",
        "name": "Iron Sword",
        "slot": "weapon",
        "attack": 5,
        "range_min": 1,
        "range_max": 1,
        "description": "A plain iron blade with reliable balance.",
        "cost": {"money": 1600, "items": {"Iron Bar": 2, "Coal": 2}},
        "unlock": "iron",
        "tags": ["blade"],
    },
    "Copper Hammer": {
        "id": "copper_hammer",
        "name": "Copper Hammer",
        "slot": "weapon",
        "attack": 2,
        "defense": 1,
        "range_min": 1,
        "range_max": 1,
        "description": "A compact hammer that keeps you braced in close quarters.",
        "cost": {"money": 1000, "items": {"Copper Bar": 2, "Stone": 20}},
        "unlock": "blacksmith",
        "tags": ["blunt"],
    },
    "Iron Hammer": {
        "id": "iron_hammer",
        "name": "Iron Hammer",
        "slot": "weapon",
        "attack": 4,
        "defense": 1,
        "range_min": 1,
        "range_max": 1,
        "description": "A dense iron hammer made for enemies with hard shells.",
        "cost": {"money": 1800, "items": {"Iron Bar": 2, "Stone": 30}},
        "unlock": "iron",
        "tags": ["blunt"],
    },
    "Short Bow": {
        "id": "short_bow",
        "name": "Short Bow",
        "slot": "weapon",
        "attack": 3,
        "max_focus": 1,
        "range_min": 2,
        "range_max": 4,
        "description": "A simple bow for keeping a little space in cave fights.",
        "cost": {"money": 1100, "items": {"Wood": 20, "Fiber": 15, "Copper Bar": 1}},
        "unlock": "blacksmith",
        "tags": ["ranged"],
    },
    "Cave Saber": {
        "id": "cave_saber",
        "name": "Cave Saber",
        "slot": "weapon",
        "attack": 6,
        "range_min": 1,
        "range_max": 1,
        "description": "A heavier blade suited to mine work.",
        "cost": {"money": 2600, "items": {"Iron Bar": 3, "Crystal Shard": 2, "Coal": 2}},
        "unlock": "deep_mine",
        "tags": ["blade"],
    },
    "Fang Spear": {
        "id": "fang_spear",
        "name": "Fang Spear",
        "slot": "weapon",
        "attack": 4,
        "range_min": 1,
        "range_max": 2,
        "description": "A reach weapon tipped with hard monster fang for safer party formations.",
        "cost": {"money": 900, "items": {"Quartz": 2, "Wood": 15, "Soft Fiber": 3}},
        "unlock": "quartz",
        "tags": ["reach", "monster"],
    },
    "Shard Bow": {
        "id": "shard_bow",
        "name": "Shard Bow",
        "slot": "weapon",
        "attack": 5,
        "max_focus": 2,
        "range_min": 2,
        "range_max": 5,
        "description": "A bow reinforced with crystal shards that rewards careful positioning.",
        "cost": {"money": 1700, "items": {"Crystal Shard": 2, "Soft Fiber": 6, "Feather": 2}},
        "unlock": "deep_mine",
        "tags": ["ranged", "monster"],
    },
    "Relic Halberd": {
        "id": "relic_halberd",
        "name": "Relic Halberd",
        "slot": "weapon",
        "attack": 7,
        "defense": 1,
        "range_min": 1,
        "range_max": 2,
        "description": "A restored ruin polearm made from sentinel scrap and old mechanisms.",
        "cost": {"money": 3200, "items": {"Ruin Scrap": 4, "Ancient Cog": 1, "Iron Bar": 2, "Relic Fragment": 2}},
        "unlock": "deep_mine",
        "tags": ["reach", "ruin"],
    },
}


COMBAT_ARMOR_DATA: Dict[str, Dict[str, object]] = {
    "Work Clothes": {
        "id": "work_clothes",
        "name": "Work Clothes",
        "slot": "armor",
        "defense": 0,
        "max_hp": 0,
        "description": "Everyday clothes. Flexible, but not protective.",
        "cost": {"money": 0, "items": {}},
        "unlock": "starter",
    },
    "Padded Jacket": {
        "id": "padded_jacket",
        "name": "Padded Jacket",
        "slot": "armor",
        "defense": 2,
        "max_hp": 5,
        "description": "Better than farm clothes underground.",
        "cost": {"money": 700, "items": {"Fiber": 20, "Bat Guano": 2}},
        "unlock": "blacksmith",
    },
    "Explorer Coat": {
        "id": "explorer_coat",
        "name": "Explorer Coat",
        "slot": "armor",
        "defense": 2,
        "max_hp": 6,
        "max_focus": 4,
        "description": "A flexible coat with pockets for careful delving.",
        "cost": {"money": 1100, "items": {"Fiber": 25, "Cave Herbs": 2}},
        "unlock": "blacksmith",
    },
    "Copper Mail": {
        "id": "copper_mail",
        "name": "Copper Mail",
        "slot": "armor",
        "defense": 4,
        "max_hp": 8,
        "description": "Copper rings over padded cloth for early mine work.",
        "cost": {"money": 1400, "items": {"Copper Bar": 3, "Fiber": 10}},
        "unlock": "blacksmith",
    },
    "Iron Mail": {
        "id": "iron_mail",
        "name": "Iron Mail",
        "slot": "armor",
        "defense": 6,
        "max_hp": 12,
        "description": "A sturdy iron coat for deeper cave floors.",
        "cost": {"money": 2400, "items": {"Iron Bar": 3, "Coal": 2}},
        "unlock": "iron",
    },
    "Miner's Coat": {
        "id": "miners_coat",
        "name": "Miner's Coat",
        "slot": "armor",
        "defense": 3,
        "max_hp": 8,
        "description": "A reinforced coat made for cave scrapes and falling grit.",
        "cost": {"money": 1800, "items": {"Iron Bar": 1, "Fiber": 20, "Quartz": 1}},
        "unlock": "deep_mine",
    },
    "Quill Vest": {
        "id": "quill_vest",
        "name": "Quill Vest",
        "slot": "armor",
        "defense": 3,
        "max_hp": 10,
        "description": "A flexible vest backed with thorn plates and soft padding.",
        "cost": {"money": 1200, "items": {"Soft Fiber": 10, "Small Pelt": 2, "Fiber": 15}},
        "unlock": "blacksmith",
    },
    "Ruin Shell Coat": {
        "id": "ruin_shell_coat",
        "name": "Ruin Shell Coat",
        "slot": "armor",
        "defense": 7,
        "max_hp": 14,
        "max_focus": 2,
        "description": "A heavy coat lined with cleaned sentinel shell and ruin fasteners.",
        "cost": {"money": 3000, "items": {"Ruin Scrap": 5, "Stone Sigil": 1, "Iron Bar": 2}},
        "unlock": "deep_mine",
    },
}


COMBAT_ACCESSORY_DATA: Dict[str, Dict[str, object]] = {
    "None": {
        "id": "none",
        "name": "None",
        "slot": "accessory",
        "attack": 0,
        "defense": 0,
        "max_hp": 0,
        "max_focus": 0,
        "description": "No accessory equipped.",
        "cost": {"money": 0, "items": {}},
        "unlock": "starter",
    },
    "Miner's Charm": {
        "id": "miners_charm",
        "name": "Miner's Charm",
        "slot": "accessory",
        "attack": 0,
        "defense": 1,
        "max_hp": 0,
        "max_focus": 5,
        "description": "A charm worn by cautious miners.",
        "cost": {"money": 600, "items": {"Stone": 30, "Quartz": 1}},
        "unlock": "quartz",
    },
    "Bat Wing Charm": {
        "id": "bat_wing_charm",
        "name": "Bat Wing Charm",
        "slot": "accessory",
        "attack": 1,
        "defense": 0,
        "max_hp": 0,
        "max_focus": 3,
        "description": "Light, strange, and useful when reactions matter.",
        "cost": {"money": 750, "items": {"Bat Guano": 3, "Fiber": 10}},
        "unlock": "blacksmith",
    },
    "Stone Ring": {
        "id": "stone_ring",
        "name": "Stone Ring",
        "slot": "accessory",
        "attack": 0,
        "defense": 2,
        "max_hp": 3,
        "max_focus": 0,
        "description": "A heavy little ring that helps you hold your ground.",
        "cost": {"money": 800, "items": {"Stone": 40, "Copper Bar": 1}},
        "unlock": "blacksmith",
    },
    "Focus Band": {
        "id": "focus_band",
        "name": "Focus Band",
        "slot": "accessory",
        "attack": 0,
        "defense": 0,
        "max_hp": 0,
        "max_focus": 10,
        "description": "A wrapped band that steadies breath and attention.",
        "cost": {"money": 900, "items": {"Fiber": 15, "Honey": 1}},
        "unlock": "blacksmith",
    },
    "Lucky Button": {
        "id": "lucky_button",
        "name": "Lucky Button",
        "slot": "accessory",
        "attack": 1,
        "defense": 1,
        "max_hp": 2,
        "max_focus": 2,
        "description": "A polished old button that feels better than it should.",
        "cost": {"money": 1200, "items": {"Quartz": 1, "Strange Spores": 2}},
        "unlock": "deep_mine",
    },
    "Copper Charm": {
        "id": "copper_charm",
        "name": "Copper Charm",
        "slot": "accessory",
        "attack": 1,
        "defense": 0,
        "max_hp": 0,
        "max_focus": 1,
        "description": "A simple charm that steadies the hand.",
        "cost": {"money": 500, "items": {"Copper Bar": 1, "Quartz": 1}},
        "unlock": "blacksmith",
    },
    "Quartz Charm": {
        "id": "quartz_charm",
        "name": "Quartz Charm",
        "slot": "accessory",
        "attack": 0,
        "defense": 1,
        "max_hp": 2,
        "max_focus": 2,
        "description": "A pale charm that helps you keep calm under pressure.",
        "cost": {"money": 700, "items": {"Quartz": 2, "Copper Bar": 1}},
        "unlock": "quartz",
    },
    "Wisp Lantern": {
        "id": "wisp_lantern",
        "name": "Wisp Lantern",
        "slot": "accessory",
        "attack": 0,
        "defense": 1,
        "max_hp": 0,
        "max_focus": 8,
        "description": "A cold-glowing charm that helps a party keep focus in longer fights.",
        "cost": {"money": 1100, "items": {"Crystal Shard": 2, "Cave Herbs": 2}},
        "unlock": "deep_mine",
    },
    "Ancient Gear Charm": {
        "id": "ancient_gear_charm",
        "name": "Ancient Gear Charm",
        "slot": "accessory",
        "attack": 1,
        "defense": 1,
        "max_hp": 4,
        "max_focus": 4,
        "description": "A small restored mechanism that clicks warmly when danger gets close.",
        "cost": {"money": 1800, "items": {"Ancient Cog": 1, "Relic Fragment": 2, "Old Coin": 2}},
        "unlock": "deep_mine",
    },
}


def farmstead_food_combat_effect(item_name: str, stamina: int) -> Tuple[str, int]:
    focus_terms = ("Honey", "Herb", "Tea", "Coffee")
    if any(term in str(item_name) for term in focus_terms):
        return "mp", max(3, min(18, int(stamina) // 4 + 2))
    return "heal", max(4, min(48, int(stamina) // 2 + 4))


BASE_COMBAT_CONSUMABLE_DATA: Dict[str, Dict[str, object]] = {
    "Potion": {
        "effect": "heal",
        "amount": 14,
        "description": "Combat medicine. Restore 14 HP.",
    },
    "Ether": {
        "effect": "mp",
        "amount": 6,
        "description": "Focus tonic. Restore 6 focus.",
    },
    "Cleanse Kit": {
        "effect": "cleanse",
        "amount": 0,
        "description": "Remove poison, root, and vulnerable in combat.",
    },
    "Guard Tonic": {
        "effect": "guard",
        "amount": 0,
        "description": "Put one ally into Guard in combat.",
    },
    "Throwing Knife": {
        "effect": "damage",
        "amount": 5,
        "description": "Quick ranged damage item for combat.",
    },
    "Fire Bomb": {
        "effect": "damage",
        "amount": 6,
        "description": "Small explosive combat item.",
    },
}


def build_farmstead_combat_item_data() -> Dict[str, Dict[str, object]]:
    items: Dict[str, Dict[str, object]] = dict(BASE_COMBAT_CONSUMABLE_DATA)
    for source in (FOOD_DATA, FISH_DATA):
        for item_name, data in source.items():
            try:
                stamina = int(data.get("stamina", 0) or 0)
            except Exception:
                stamina = 0
            if stamina <= 0:
                continue
            effect, amount = farmstead_food_combat_effect(str(item_name), stamina)
            unit = "focus" if effect == "mp" else "HP"
            items[str(item_name)] = {
                "effect": effect,
                "amount": amount,
                "description": f"Farmstead food. Restore {amount} {unit}.",
            }
    return items


FARMSTEAD_COMBAT_ITEM_DATA: Dict[str, Dict[str, object]] = build_farmstead_combat_item_data()


DEFAULT_COMBAT_LEVEL = 1
DEFAULT_COMBAT_EXP = 0
DEFAULT_COMBAT_EXP_TO_NEXT = 20
DEFAULT_COMBAT_MAX_HP = 34
DEFAULT_COMBAT_ATTACK = 3
DEFAULT_COMBAT_DEFENSE = 0
DEFAULT_COMBAT_MAX_FOCUS = 8
DEFAULT_COMBAT_SKILL_POINTS = 0
DEFAULT_COMBAT_WEAPON = "Rusty Sword"
DEFAULT_COMBAT_ARMOR = "Work Clothes"
DEFAULT_COMBAT_ACCESSORY = "None"


COMBAT_EQUIPMENT_SLOTS: Dict[str, Tuple[str, Dict[str, Dict[str, object]], str]] = {
    "weapon": ("equipped_weapon", COMBAT_WEAPON_DATA, DEFAULT_COMBAT_WEAPON),
    "armor": ("equipped_armor", COMBAT_ARMOR_DATA, DEFAULT_COMBAT_ARMOR),
    "accessory": ("equipped_accessory", COMBAT_ACCESSORY_DATA, DEFAULT_COMBAT_ACCESSORY),
}


FARMSTEAD_MAX_PARTY_MEMBERS = 4

FARMSTEAD_PARTY_TACTICS = ("Balanced", "Aggressive", "Cautious", "Support")


def normalized_farmstead_party_tactic(value: object) -> str:
    tactic = str(value or "Balanced")
    return tactic if tactic in FARMSTEAD_PARTY_TACTICS else "Balanced"


FARMSTEAD_COMPANION_DATA: Dict[str, Dict[str, object]] = {
    "brom_smith": {
        "id": "brom_smith",
        "npc_id": "brom_smith",
        "name": "Brom",
        "role": "Breaker",
        "class": "Vanguard",
        "subclass": "Earth",
        "color": "Yellow",
        "required_building": "blacksmith",
        "min_relationship": 60,
        "description": "A steady forge hand who holds the front and cracks armor with careful, heavy swings.",
        "first_select_message": "Brom agrees to join mine expeditions. He checks your weapon edge before saying yes.",
        "victory_line": "Brom studies the stone dust and nods. 'Cleaner than it could have been.'",
        "flee_line": "Brom keeps his shield high until the tunnel opens behind you.",
        "defeat_line": "Brom gets you moving before pride can argue with blood loss.",
        "max_hp": 42,
        "max_focus": 10,
        "attack": 6,
        "defense": 2,
        "move_range": 4,
        "weapon": "Guard Axe",
        "weapon_range_min": 1,
        "weapon_range_max": 1,
        "inventory": {"Potion": 1, "Guard Tonic": 1, "Throwing Knife": 1},
    },
    "dr_ivy": {
        "id": "dr_ivy",
        "npc_id": "dr_ivy",
        "name": "Dr. Ivy",
        "role": "Medic",
        "class": "Guardian",
        "subclass": "Light",
        "color": "White",
        "required_building": "clinic",
        "min_relationship": 60,
        "description": "A calm field medic who brings focus, healing supplies, and a very low tolerance for recklessness.",
        "first_select_message": "Dr. Ivy joins your expedition list and makes you promise to leave before exhaustion decides for you.",
        "victory_line": "Dr. Ivy checks everyone over before letting the celebration start.",
        "flee_line": "Dr. Ivy calls the retreat early and keeps the route clear.",
        "defeat_line": "Dr. Ivy gets you breathing steadily before the mine entrance comes back into view.",
        "max_hp": 34,
        "max_focus": 20,
        "attack": 3,
        "defense": 1,
        "move_range": 5,
        "weapon": "Sun Rod",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 1, "Cleanse Kit": 2},
    },
    "garrick_miner": {
        "id": "garrick_miner",
        "npc_id": "garrick_miner",
        "name": "Garrick",
        "role": "Vanguard",
        "class": "Guardian",
        "subclass": "Earth",
        "color": "Gray",
        "required_building": "blacksmith",
        "min_relationship": 40,
        "min_deepest_mine_floor": 3,
        "description": "A hard-nosed miner who knows how to take a hit and read a bad tunnel before it speaks up.",
        "first_select_message": "Garrick agrees to join after tapping the mine wall twice and deciding it approves.",
        "victory_line": "Garrick taps the wall and says the floor sounds safer now.",
        "flee_line": "Garrick takes the rear and refuses to hurry faster than the stone allows.",
        "defeat_line": "Garrick drags the route back into sense one step at a time.",
        "max_hp": 48,
        "max_focus": 8,
        "attack": 5,
        "defense": 3,
        "move_range": 4,
        "weapon": "Stone Hammer",
        "weapon_range_min": 1,
        "weapon_range_max": 1,
        "inventory": {"Potion": 2, "Guard Tonic": 1},
    },
    "poppy_rancher": {
        "id": "poppy_rancher",
        "npc_id": "poppy_rancher",
        "name": "Poppy",
        "role": "Handler",
        "class": "Guardian",
        "subclass": "Light",
        "color": "Green",
        "required_building": "animal_store",
        "min_relationship": 60,
        "description": "An animal handler with quick instincts, practical care supplies, and a protective streak.",
        "first_select_message": "Poppy joins your party roster and immediately starts packing extra bandages.",
        "victory_line": "Poppy grins, then checks the quiet corners before relaxing.",
        "flee_line": "Poppy keeps everyone moving with bright, firm instructions.",
        "defeat_line": "Poppy stays close and talks you back to steady ground.",
        "max_hp": 38,
        "max_focus": 16,
        "attack": 4,
        "defense": 1,
        "move_range": 5,
        "weapon": "Scout Bow",
        "weapon_range_min": 2,
        "weapon_range_max": 4,
        "inventory": {"Potion": 2, "Cleanse Kit": 1},
    },
    "tess_reader": {
        "id": "tess_reader",
        "npc_id": "tess_reader",
        "name": "Tess",
        "role": "Analyst",
        "class": "Ranger",
        "subclass": "Storm",
        "color": "Blue",
        "required_building": "library",
        "min_relationship": 60,
        "description": "A precise observer who fights from range and notices patterns before they become problems.",
        "first_select_message": "Tess adds mine expedition notes to her ledger and quietly asks where you want her to stand.",
        "victory_line": "Tess records the enemy's behavior while the details are still fresh.",
        "flee_line": "Tess marks the unsafe route in her notes without wasting a word.",
        "defeat_line": "Tess remembers the way out even when the fight goes wrong.",
        "max_hp": 30,
        "max_focus": 18,
        "attack": 4,
        "defense": 0,
        "move_range": 5,
        "weapon": "Scout Bow",
        "weapon_range_min": 2,
        "weapon_range_max": 5,
        "inventory": {"Potion": 1, "Ether": 1, "Throwing Knife": 1},
    },
    "hana_botanist": {
        "id": "hana_botanist",
        "npc_id": "hana_botanist",
        "name": "Hana",
        "role": "Botanist",
        "class": "Alchemist",
        "subclass": "Poison",
        "color": "Magenta",
        "required_building": "library",
        "min_relationship": 60,
        "description": "A cave-plant specialist who turns spores, roots, and field notes into careful battlefield control.",
        "first_select_message": "Hana joins your expedition list with a sample case, spare gloves, and badly hidden excitement.",
        "victory_line": "Hana gathers a careful sample and promises not to label it 'probably safe' yet.",
        "flee_line": "Hana snaps her sample case shut and follows before curiosity can betray her.",
        "defeat_line": "Hana keeps talking through observations until panic has less room to grow.",
        "max_hp": 32,
        "max_focus": 18,
        "attack": 3,
        "defense": 1,
        "move_range": 5,
        "weapon": "Light Wand",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 2, "Cleanse Kit": 1},
    },
    "mira_seed": {
        "id": "mira_seed",
        "npc_id": "mira_seed",
        "name": "Mira",
        "role": "Seed Scout",
        "class": "Ranger",
        "subclass": "Poison",
        "color": "Green",
        "required_building": "",
        "min_relationship": 50,
        "description": "A nimble seed seller who reads growth patterns and uses range, snares, and irritant seed packets.",
        "first_select_message": "Mira joins your expedition list with seed cases sorted by usefulness and danger.",
        "victory_line": "Mira checks which seed packets worked and which ones need less enthusiasm.",
        "flee_line": "Mira marks the retreat route with bright twine and keeps moving.",
        "defeat_line": "Mira steadies her breathing, then starts counting everyone twice.",
        "max_hp": 30,
        "max_focus": 18,
        "attack": 4,
        "defense": 0,
        "move_range": 5,
        "weapon": "Scout Bow",
        "weapon_range_min": 2,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 1, "Throwing Knife": 1},
    },
    "eli_carpenter": {
        "id": "eli_carpenter",
        "npc_id": "eli_carpenter",
        "name": "Eli",
        "role": "Builder",
        "class": "Guardian",
        "subclass": "Earth",
        "color": "Yellow",
        "required_building": "",
        "min_relationship": 60,
        "description": "A careful builder who braces allies, holds lines, and sees battlefield angles like floor plans.",
        "first_select_message": "Eli joins your expedition list after sketching where people should stand if trouble starts.",
        "victory_line": "Eli studies the room and notes how the fight changed its shape.",
        "flee_line": "Eli counts exits aloud and keeps the route practical.",
        "defeat_line": "Eli gets everyone back through the safest line he can find.",
        "max_hp": 40,
        "max_focus": 10,
        "attack": 5,
        "defense": 2,
        "move_range": 4,
        "weapon": "Stone Hammer",
        "weapon_range_min": 1,
        "weapon_range_max": 1,
        "inventory": {"Potion": 2, "Guard Tonic": 1},
    },
    "niko_traveler": {
        "id": "niko_traveler",
        "npc_id": "niko_traveler",
        "name": "Niko",
        "role": "Pathfinder",
        "class": "Duelist",
        "subclass": "Storm",
        "color": "Cyan",
        "required_building": "",
        "min_relationship": 40,
        "description": "A route-minded traveler who moves quickly, flanks cleanly, and never forgets the way out.",
        "first_select_message": "Niko joins your expedition list and immediately asks which route has the worst reputation.",
        "victory_line": "Niko grins and says the map just got a little more honest.",
        "flee_line": "Niko finds the gap before the fight can swallow the whole room.",
        "defeat_line": "Niko keeps the retreat from turning into a scatter.",
        "max_hp": 32,
        "max_focus": 14,
        "attack": 4,
        "defense": 0,
        "move_range": 6,
        "weapon": "Twin Daggers",
        "weapon_range_min": 1,
        "weapon_range_max": 1,
        "inventory": {"Potion": 1, "Throwing Knife": 2, "Guard Tonic": 1},
    },
    "mae_innkeeper": {
        "id": "mae_innkeeper",
        "npc_id": "mae_innkeeper",
        "name": "Mae",
        "role": "Quartermaster",
        "class": "Guardian",
        "subclass": "Light",
        "color": "White",
        "required_building": "",
        "min_relationship": 60,
        "description": "A practical innkeeper who keeps the party supplied, steady, and too well-fed to collapse politely.",
        "first_select_message": "Mae joins your expedition list with a packed bag and the expression of someone expecting nonsense.",
        "victory_line": "Mae checks the snack count before calling the fight handled.",
        "flee_line": "Mae herds the party out with brisk, unarguable directions.",
        "defeat_line": "Mae gets everyone sitting, breathing, and drinking something warm.",
        "max_hp": 36,
        "max_focus": 18,
        "attack": 3,
        "defense": 1,
        "move_range": 5,
        "weapon": "Sun Rod",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 2, "Ether": 1, "Cleanse Kit": 1},
    },
    "chef_basil": {
        "id": "chef_basil",
        "npc_id": "chef_basil",
        "name": "Basil",
        "role": "Cookfire",
        "class": "Alchemist",
        "subclass": "Fire",
        "color": "Red",
        "required_building": "",
        "min_relationship": 60,
        "description": "A dramatic chef who turns heat, timing, and emergency pantry logic into battlefield pressure.",
        "first_select_message": "Basil joins your expedition list and insists cave food is still cuisine if it has intention.",
        "victory_line": "Basil calls the fight acceptable, then starts improving the recipe.",
        "flee_line": "Basil retreats loudly enough that everyone follows the correct exit.",
        "defeat_line": "Basil blames the texture of the situation and helps everyone up.",
        "max_hp": 30,
        "max_focus": 18,
        "attack": 4,
        "defense": 0,
        "move_range": 5,
        "weapon": "Light Wand",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 1, "Throwing Knife": 1},
    },
    "vera_vendor": {
        "id": "vera_vendor",
        "npc_id": "vera_vendor",
        "name": "Vera",
        "role": "Skirmisher",
        "class": "Duelist",
        "subclass": "Shadow",
        "color": "Magenta",
        "required_building": "market_row",
        "min_relationship": 60,
        "description": "A market vendor with sharp eyes, sharper timing, and a gift for making bad trades expensive.",
        "first_select_message": "Vera joins your expedition list after deciding the mine has terrible margins and useful loot.",
        "victory_line": "Vera counts the salvage and says the risk was almost priced correctly.",
        "flee_line": "Vera cuts losses fast and makes the retreat sound like strategy.",
        "defeat_line": "Vera gets everyone out, then starts revising the deal.",
        "max_hp": 31,
        "max_focus": 14,
        "attack": 5,
        "defense": 0,
        "move_range": 6,
        "weapon": "Twin Daggers",
        "weapon_range_min": 1,
        "weapon_range_max": 1,
        "inventory": {"Potion": 1, "Throwing Knife": 2},
    },
    "finn_fisher": {
        "id": "finn_fisher",
        "npc_id": "finn_fisher",
        "name": "Finn",
        "role": "Marksman",
        "class": "Ranger",
        "subclass": "Frost",
        "color": "Blue",
        "required_building": "",
        "min_relationship": 50,
        "description": "A patient fisher who knows when to wait, when to pull, and when distance is the whole plan.",
        "first_select_message": "Finn joins your expedition list and says a cave fight is mostly fishing with worse bait.",
        "victory_line": "Finn loosens his grip and says rushing would have made that uglier.",
        "flee_line": "Finn backs away in measured steps, keeping the line from snapping.",
        "defeat_line": "Finn gets everyone out and says the mine hooked harder than expected.",
        "max_hp": 32,
        "max_focus": 14,
        "attack": 4,
        "defense": 1,
        "move_range": 5,
        "weapon": "Scout Bow",
        "weapon_range_min": 2,
        "weapon_range_max": 5,
        "inventory": {"Potion": 1, "Guard Tonic": 1, "Throwing Knife": 1},
    },
    "cora_courier": {
        "id": "cora_courier",
        "npc_id": "cora_courier",
        "name": "Cora",
        "role": "Runner",
        "class": "Duelist",
        "subclass": "Storm",
        "color": "Cyan",
        "required_building": "",
        "min_relationship": 50,
        "description": "A fast courier who turns footwork, signals, and clean routes into quick pressure.",
        "first_select_message": "Cora joins your expedition list and asks for the shortest way to the worst problem.",
        "victory_line": "Cora marks the room cleared and is already thinking about the next route.",
        "flee_line": "Cora calls the retreat like a delivery deadline nobody should miss.",
        "defeat_line": "Cora keeps everyone together until the route makes sense again.",
        "max_hp": 30,
        "max_focus": 14,
        "attack": 4,
        "defense": 0,
        "move_range": 7,
        "weapon": "Twin Daggers",
        "weapon_range_min": 1,
        "weapon_range_max": 1,
        "inventory": {"Potion": 1, "Throwing Knife": 2, "Guard Tonic": 1},
    },
    "penny_artist": {
        "id": "penny_artist",
        "npc_id": "penny_artist",
        "name": "Penny",
        "role": "Illuminator",
        "class": "Mystic",
        "subclass": "Light",
        "color": "Magenta",
        "required_building": "",
        "min_relationship": 70,
        "description": "An artist who marks safe routes, steadies fear with light, and notices shapes enemies leave behind.",
        "first_select_message": "Penny joins your expedition list with chalk, lantern paint, and a brave little smile.",
        "victory_line": "Penny sketches the room before the memory changes color.",
        "flee_line": "Penny keeps a bright mark ahead of the retreat.",
        "defeat_line": "Penny makes the way back visible when everything else feels confused.",
        "max_hp": 28,
        "max_focus": 20,
        "attack": 3,
        "defense": 0,
        "move_range": 5,
        "weapon": "Sun Rod",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 2, "Cleanse Kit": 1},
    },
    "silas_recluse": {
        "id": "silas_recluse",
        "npc_id": "silas_recluse",
        "name": "Silas",
        "role": "Watcher",
        "class": "Ranger",
        "subclass": "Shadow",
        "color": "Gray",
        "required_building": "",
        "min_relationship": 50,
        "min_deepest_mine_floor": 3,
        "description": "A wilderness watcher who keeps to the edge, reads quiet danger, and strikes without wasted movement.",
        "first_select_message": "Silas joins your expedition list after confirming you understand silence is useful.",
        "victory_line": "Silas watches the tunnel until he is sure nothing followed the noise.",
        "flee_line": "Silas disappears into the retreat path, then reappears where everyone should go.",
        "defeat_line": "Silas leads the way out without asking anyone to speak.",
        "max_hp": 34,
        "max_focus": 12,
        "attack": 5,
        "defense": 1,
        "move_range": 5,
        "weapon": "Scout Bow",
        "weapon_range_min": 2,
        "weapon_range_max": 5,
        "inventory": {"Potion": 1, "Throwing Knife": 2},
    },
    "rowan_orchard": {
        "id": "rowan_orchard",
        "npc_id": "rowan_orchard",
        "name": "Rowan",
        "role": "Warden",
        "class": "Guardian",
        "subclass": "Earth",
        "color": "Green",
        "required_building": "",
        "min_relationship": 60,
        "description": "A steady orchardist who roots the party in place and turns careful defense into stubborn survival.",
        "first_select_message": "Rowan joins your expedition list after packing salves and asking where people usually lose their footing.",
        "victory_line": "Rowan relaxes only after the room feels still again.",
        "flee_line": "Rowan takes slow, solid steps and keeps panic from setting the pace.",
        "defeat_line": "Rowan braces whoever needs it and walks everyone back to daylight.",
        "max_hp": 42,
        "max_focus": 12,
        "attack": 4,
        "defense": 2,
        "move_range": 4,
        "weapon": "Guard Axe",
        "weapon_range_min": 1,
        "weapon_range_max": 1,
        "inventory": {"Potion": 2, "Guard Tonic": 1},
    },
    "sable_tailor": {
        "id": "sable_tailor",
        "npc_id": "sable_tailor",
        "name": "Sable",
        "role": "Blade",
        "class": "Duelist",
        "subclass": "Shadow",
        "color": "Magenta",
        "required_building": "market_row",
        "min_relationship": 60,
        "description": "A precise tailor who fights with quiet footwork, clean cuts, and an excellent sense of loose threads.",
        "first_select_message": "Sable joins your expedition list and immediately alters her field wrap for better movement.",
        "victory_line": "Sable checks her cuffs and says the fight could have been cleaner, but it will do.",
        "flee_line": "Sable cuts a clear line through the mess and refuses to snag on panic.",
        "defeat_line": "Sable keeps her voice cool while helping everyone withdraw.",
        "max_hp": 30,
        "max_focus": 14,
        "attack": 5,
        "defense": 0,
        "move_range": 6,
        "weapon": "Twin Daggers",
        "weapon_range_min": 1,
        "weapon_range_max": 1,
        "inventory": {"Potion": 1, "Throwing Knife": 2},
    },
    "aria_musician": {
        "id": "aria_musician",
        "npc_id": "aria_musician",
        "name": "Aria",
        "role": "Rallier",
        "class": "Mystic",
        "subclass": "Storm",
        "color": "Blue",
        "required_building": "",
        "min_relationship": 60,
        "description": "A musician whose rhythm keeps allies moving together and makes hesitation easier to break.",
        "first_select_message": "Aria joins your expedition list and starts testing marching beats under her breath.",
        "victory_line": "Aria lets out a shaky laugh and says the ending needs a better chord.",
        "flee_line": "Aria sets a retreat rhythm everyone can follow.",
        "defeat_line": "Aria hums until breathing matches the tune again.",
        "max_hp": 28,
        "max_focus": 20,
        "attack": 3,
        "defense": 0,
        "move_range": 5,
        "weapon": "Light Wand",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 2, "Cleanse Kit": 1},
    },
    "theo_beekeeper": {
        "id": "theo_beekeeper",
        "npc_id": "theo_beekeeper",
        "name": "Theo",
        "role": "Keeper",
        "class": "Alchemist",
        "subclass": "Poison",
        "color": "Yellow",
        "required_building": "",
        "min_relationship": 60,
        "description": "A beekeeper who uses patience, smoke, and controlled pressure to keep enemies off balance.",
        "first_select_message": "Theo joins your expedition list with calm hands and a surprising number of sealed jars.",
        "victory_line": "Theo says the fight calmed down once everyone stopped swatting at fear.",
        "flee_line": "Theo keeps the retreat smooth, patient, and away from sharp corners.",
        "defeat_line": "Theo speaks gently until the party finds its breath again.",
        "max_hp": 34,
        "max_focus": 16,
        "attack": 3,
        "defense": 1,
        "move_range": 5,
        "weapon": "Light Wand",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 1, "Guard Tonic": 1},
    },
    "jules_mechanic": {
        "id": "jules_mechanic",
        "npc_id": "jules_mechanic",
        "name": "Jules",
        "role": "Tinkerer",
        "class": "Alchemist",
        "subclass": "Storm",
        "color": "Cyan",
        "required_building": "blacksmith",
        "min_relationship": 60,
        "description": "An inventive mechanic who brings unstable gadgets, useful timing, and only mostly-tested ideas.",
        "first_select_message": "Jules joins your expedition list with a tool roll that clicks even when nobody touches it.",
        "victory_line": "Jules writes down what failed, what worked, and what made the most interesting sound.",
        "flee_line": "Jules retreats while promising the device was not supposed to smoke that much.",
        "defeat_line": "Jules gets everyone out and calls the results extremely informative.",
        "max_hp": 30,
        "max_focus": 18,
        "attack": 4,
        "defense": 0,
        "move_range": 5,
        "weapon": "Light Wand",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 1, "Throwing Knife": 1},
    },
    "marisol_scholar": {
        "id": "marisol_scholar",
        "npc_id": "marisol_scholar",
        "name": "Marisol",
        "role": "Archivist",
        "class": "Mystic",
        "subclass": "Frost",
        "color": "White",
        "required_building": "",
        "min_relationship": 70,
        "min_deepest_mine_floor": 5,
        "description": "A composed scholar who turns records, ruins, and cold focus into careful battlefield control.",
        "first_select_message": "Marisol joins your expedition list after copying the route into her field notes twice.",
        "victory_line": "Marisol records the encounter with the satisfaction of a theory gaining teeth.",
        "flee_line": "Marisol preserves the evidence and the party, in that order.",
        "defeat_line": "Marisol insists survival is also data and helps everyone leave.",
        "max_hp": 29,
        "max_focus": 22,
        "attack": 3,
        "defense": 0,
        "move_range": 5,
        "weapon": "Sun Rod",
        "weapon_range_min": 1,
        "weapon_range_max": 4,
        "inventory": {"Potion": 1, "Ether": 2, "Cleanse Kit": 1},
    },
}


MINE_ENEMY_PROFILES: Dict[str, Dict[str, object]] = {
    "Slime": {
        "symbol": "s",
        "color": "WATER",
        "description": "A slick cave slime pulses across the stone.",
        "weight_by_tier": [10, 7, 3, 1, 0, 0],
        "exp_reward": 8,
    },
    "Sporeling": {
        "symbol": "p",
        "color": "CROP_READY",
        "description": "A little fungal creature trails pale spores behind it.",
        "weight_by_tier": [0, 4, 5, 3, 1, 1],
        "exp_reward": 10,
    },
    "Wisp": {
        "symbol": "w",
        "color": "SNOW",
        "description": "A cold light flickers in the dark like a thinking lantern.",
        "weight_by_tier": [0, 1, 4, 5, 4, 5],
        "exp_reward": 13,
    },
    "Rockback": {
        "symbol": "k",
        "color": "STONE",
        "description": "A squat stone-backed beast grinds pebbles under its claws.",
        "weight_by_tier": [0, 3, 5, 4, 5, 4],
        "exp_reward": 14,
    },
    "Razor Hare": {
        "symbol": "h",
        "color": "HOSTILE",
        "description": "A quick cave hare darts in, kicks, and vanishes behind loose stone.",
        "weight_by_tier": [0, 3, 4, 2, 1, 0],
        "exp_reward": 11,
    },
    "Marsh Toad": {
        "symbol": "t",
        "color": "WATER",
        "description": "A damp toad snaps from puddles and leaves slick poison behind.",
        "weight_by_tier": [0, 1, 3, 4, 2, 1],
        "exp_reward": 13,
    },
    "Burrower": {
        "symbol": "u",
        "color": "SOIL_DRY",
        "description": "A burrower noses through cracks in the floor.",
        "weight_by_tier": [0, 0, 4, 4, 5, 4],
        "exp_reward": 16,
    },
    "Thornback": {
        "symbol": "q",
        "color": "WOOD",
        "description": "A thornback scrapes its quills against the cave wall.",
        "weight_by_tier": [0, 0, 1, 4, 5, 5],
        "exp_reward": 17,
    },
    "Ember Imp": {
        "symbol": "e",
        "color": "LAMP",
        "description": "A tiny ember-eyed imp leaves warm prints on cold stone.",
        "weight_by_tier": [0, 0, 0, 2, 5, 4],
        "exp_reward": 18,
    },
    "Frost Moth": {
        "symbol": "f",
        "color": "WATER",
        "description": "A frost moth beats silent wings dusted with cave ice.",
        "weight_by_tier": [0, 0, 1, 4, 3, 5],
        "exp_reward": 18,
    },
    "Crystal Spider": {
        "symbol": "c",
        "color": "CROP_READY",
        "description": "A glass-legged spider skitters over crystal seams and strikes from odd angles.",
        "weight_by_tier": [0, 0, 0, 2, 4, 5],
        "exp_reward": 19,
    },
    "Cave Lynx": {
        "symbol": "l",
        "color": "HOSTILE",
        "description": "A lean cave lynx waits just outside lantern light, patient and fast.",
        "weight_by_tier": [0, 0, 2, 4, 4, 3],
        "exp_reward": 17,
    },
    "Gloomcap": {
        "symbol": "g",
        "color": "GRASS",
        "description": "A walking mushroom cap breathes spores across the floor in slow clouds.",
        "weight_by_tier": [0, 0, 2, 3, 5, 4],
        "exp_reward": 16,
    },
    "Wolf": {
        "symbol": "w",
        "color": "HOSTILE",
        "description": "A lean wilderness wolf circles for an opening.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 12,
    },
    "Bandit": {
        "symbol": "r",
        "color": "HOSTILE",
        "description": "A hard-eyed raider guards the stronghold approach.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 14,
    },
    "Shield Guard": {
        "symbol": "g",
        "color": "HOSTILE",
        "description": "A shield-bearing guard holds the line with practiced patience.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 16,
    },
    "Dustling": {
        "symbol": "d",
        "color": "DIM",
        "description": "A fist-sized knot of dust and cloth skitters through ruined halls.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 9,
    },
    "Ruin Bat": {
        "symbol": "a",
        "color": "WOOD",
        "description": "A pale bat darts between broken doorways with sharp, nervous turns.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 11,
    },
    "Moss Haunt": {
        "symbol": "m",
        "color": "GRASS",
        "description": "A mossy shape clings to old stones and moves when you stop looking.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 13,
    },
    "Shardling": {
        "symbol": "j",
        "color": "CROP_READY",
        "description": "A glass-bright creature clicks across the floor on splintered crystal legs.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 15,
    },
    "Hollow Sentinel": {
        "symbol": "n",
        "color": "STONE",
        "description": "An old guardian shell patrols by habit, empty but still obeying orders.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 19,
    },
    "Clockwork Beetle": {
        "symbol": "b",
        "color": "STONE",
        "description": "A ticking beetle made from ruin plates and stubborn little gears.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 16,
    },
    "Relic Archer": {
        "symbol": "r",
        "color": "CROP_READY",
        "description": "A broken old archer shell draws crystal string with impossible quiet.",
        "weight_by_tier": [0, 0, 0, 0, 0, 0],
        "exp_reward": 18,
    },
}


MINE_COMBAT_LOOT_ALIASES: Dict[str, Optional[str]] = {
    "Coin": None,
    "Shard": "Crystal Shard",
    "Crow Feather": "Feather",
    "Hide": "Small Pelt",
    "Boar Tusk": "Antler",
    "Gel": "Sap",
    "Slime Core": "Quartz",
    "Fang": "Quartz",
    "Wolf Pelt": "Small Pelt",
    "Bandit Token": "Copper Ore",
    "Throwing Knife": "Iron Ore",
    "Shield Fragment": "Iron Ore",
    "Root Fiber": "Fiber",
    "Spore Cap": "Strange Spores",
    "Wisp Spark": "Crystal Shard",
    "Frost Wing": "Crystal Shard",
    "Rock Shell": "Stone",
    "Toad Oil": "Sap",
    "Hare Needle": "Soft Fiber",
    "Spider Silk": "Soft Fiber",
    "Crystal Fang": "Crystal Shard",
    "Lynx Claw": "Quartz",
    "Gloom Spores": "Strange Spores",
    "Ember Cinder": "Coal",
    "Burrow Claw": "Iron Ore",
    "Quill Plate": "Soft Fiber",
    "Briar Heart": "Ancient Seed",
    "Relic Cache": "Gold Ore",
    "Supply Cache": "Mixed Seeds",
    "Tonic": "Cave Herbs",
    "Guard Tonic": "Cave Herbs",
    "Potion": "Field Snack",
    "Ether": "Honey",
    "Cleanse Kit": "Cave Herbs",
    "Old Coin": "Old Coin",
    "Ruin Scrap": "Ruin Scrap",
    "Relic Fragment": "Relic Fragment",
    "Dust Silk": "Dust Silk",
    "Stone Sigil": "Stone Sigil",
    "Ancient Cog": "Ancient Cog",
    "Bat Wing": "Bat Wing",
    "Clockwork Carapace": "Ruin Scrap",
    "Relic Arrowhead": "Relic Fragment",
}


MINE_COMBAT_MAP_POOLS = [
    ("Moonlit Quarry", "Broken Gate Ruins", "Stonewater Crossing"),
    ("Broken Gate Ruins", "Moonlit Quarry", "Flooded Causeway"),
    ("Stonewater Crossing", "Moonlit Quarry", "Briarfall Basin"),
    ("Briarfall Basin", "Flooded Causeway", "Snowmelt Terrace"),
    ("Emberglass Works", "Rampart Arsenal", "Gatehouse Bastion"),
    ("Frostwall Redoubt", "Emberglass Works", "Floodgate Citadel"),
]
MINE_COMBAT_MAPS = [pool[0] for pool in MINE_COMBAT_MAP_POOLS]

MINE_ENEMY_COMBAT_ROLES: Dict[str, str] = {
    "Slime": "blighter",
    "Sporeling": "controller",
    "Wisp": "ranged",
    "Rockback": "brute",
    "Razor Hare": "pouncer",
    "Marsh Toad": "blighter",
    "Burrower": "brute",
    "Thornback": "guardian",
    "Ember Imp": "ranged",
    "Frost Moth": "controller",
    "Crystal Spider": "pouncer",
    "Cave Lynx": "skirmisher",
    "Gloomcap": "blighter",
}

# Mirrors the tactical engine's relative threat scale closely enough for
# overworld encounter construction without importing the combat package and
# creating an item-definition import cycle.
MINE_ENEMY_THREAT: Dict[str, int] = {
    "Slime": 37,
    "Sporeling": 39,
    "Wisp": 45,
    "Rockback": 56,
    "Razor Hare": 42,
    "Marsh Toad": 41,
    "Burrower": 57,
    "Thornback": 53,
    "Ember Imp": 43,
    "Frost Moth": 44,
    "Crystal Spider": 40,
    "Cave Lynx": 42,
    "Gloomcap": 36,
}

MINE_ENCOUNTER_THEMES: Dict[str, Dict[str, object]] = {
    "Balanced Patrol": {
        "roles": (),
        "maps": ("Moonlit Quarry", "Stonewater Crossing", "Broken Gate Ruins"),
        "trait": "mixed roles",
    },
    "Fast Pack": {
        "roles": ("pouncer", "skirmisher"),
        "maps": ("Stonewater Crossing", "Snowmelt Terrace", "Broken Gate Ruins"),
        "trait": "high mobility",
    },
    "Stonewall": {
        "roles": ("brute", "guardian"),
        "maps": ("Moonlit Quarry", "Broken Gate Ruins", "Gatehouse Bastion"),
        "trait": "durable frontline",
    },
    "Spore Hazard": {
        "roles": ("controller", "blighter"),
        "maps": ("Briarfall Basin", "Flooded Causeway", "Snowmelt Terrace"),
        "trait": "area control",
    },
    "Crossfire": {
        "roles": ("ranged", "guardian", "brute"),
        "maps": ("Emberglass Works", "Floodgate Citadel", "Frostwall Redoubt"),
        "trait": "ranged pressure",
    },
}


def mine_enemy_base_name(name: object) -> str:
    raw = str(name or "").strip()
    if raw.startswith("Elite "):
        raw = raw[6:]
    parts = raw.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        raw = parts[0]
    return raw


def mine_enemy_role(name: object) -> str:
    return MINE_ENEMY_COMBAT_ROLES.get(mine_enemy_base_name(name), "skirmisher")


def mine_enemy_threat(name: object) -> int:
    raw = str(name or "")
    base = mine_enemy_base_name(raw)
    threat = int(MINE_ENEMY_THREAT.get(base, 40))
    if raw.startswith("Elite "):
        threat += max(18, threat // 2)
    return threat


def mine_encounter_threat_budget(floor: int, party_size: int) -> int:
    floor = max(1, int(floor))
    party_size = max(1, min(FARMSTEAD_MAX_PARTY_MEMBERS, int(party_size)))
    return 45 + floor * 2 + (party_size - 1) * 38


def mine_encounter_signature(counts: Dict[str, int]) -> str:
    return "|".join(
        f"{name}:{max(0, _safe_int(amount, 0))}"
        for name, amount in sorted((counts or {}).items())
        if _safe_int(amount, 0) > 0
    )


def mine_recent_history(state: object, attr: str, limit: int) -> List[str]:
    value = getattr(state, attr, [])
    if not isinstance(value, list):
        return []
    return [str(entry) for entry in value if str(entry).strip()][-limit:]


def record_mine_encounter_history(state: object, context: object) -> None:
    if not isinstance(context, dict):
        return
    for attr, key, limit in [
        ("mine_recent_combat_maps", "encounter_map", 6),
        ("mine_recent_combat_signatures", "encounter_signature", 8),
    ]:
        entry = str(context.get(key, "") or "").strip()
        if not entry:
            continue
        history = mine_recent_history(state, attr, limit)
        history.append(entry[:160])
        setattr(state, attr, history[-limit:])


def mine_enemy_pool_for_floor(floor: int, primary: str) -> List[str]:
    tier = mine_enemy_tier(floor)
    pool = {mine_enemy_base_name(primary)}
    pool.update(mine_support_enemy_pool(floor, mine_enemy_base_name(primary)))
    for name, profile in MINE_ENEMY_PROFILES.items():
        weights = profile.get("weight_by_tier", [])
        if isinstance(weights, list) and tier < len(weights) and int(weights[tier]) > 0:
            pool.add(name)
    return sorted(name for name in pool if name in MINE_ENEMY_THREAT)


def mine_theme_for_encounter(floor: int, pool: List[str], rng: random.Random) -> str:
    available_roles = {mine_enemy_role(name) for name in pool}
    choices = ["Balanced Patrol"]
    for name, data in MINE_ENCOUNTER_THEMES.items():
        if name == "Balanced Patrol":
            continue
        desired = set(data.get("roles", ()))
        if desired & available_roles:
            choices.append(name)
    if floor < 6:
        choices = [name for name in choices if name in {"Balanced Patrol", "Fast Pack"}]
    return rng.choice(choices or ["Balanced Patrol"])


def mine_directed_map(
    floor: int,
    archetype: str,
    rng: random.Random,
    recent_maps: List[str],
) -> str:
    tier = mine_enemy_tier(floor)
    pool = list(MINE_COMBAT_MAP_POOLS[min(tier, len(MINE_COMBAT_MAP_POOLS) - 1)])
    preferred = set(MINE_ENCOUNTER_THEMES.get(archetype, {}).get("maps", ()))
    scored: List[Tuple[float, str]] = []
    for map_name in pool:
        score = rng.random() * 8
        if map_name in preferred:
            score += 12
        if recent_maps and map_name == recent_maps[-1]:
            score -= 80
        elif map_name in recent_maps[-2:]:
            score -= 28
        elif map_name in recent_maps:
            score -= 8
        scored.append((score, map_name))
    return max(scored)[1]


def mine_group_counts(names: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    return counts


def mine_directed_group(
    primary: str,
    floor: int,
    party_size: int,
    archetype: str,
    special: str,
    rng: random.Random,
    recent_signatures: List[str],
) -> Tuple[Dict[str, int], int, int]:
    primary = mine_enemy_base_name(primary)
    pool = mine_enemy_pool_for_floor(floor, primary)
    budget = mine_encounter_threat_budget(floor, party_size)
    max_count = {
        1: 1 if floor < 8 else 2,
        2: 3,
        3: 4,
        4: 6 if floor >= 24 else 5,
    }[party_size]
    primary_name = f"Elite {primary}" if special in {"elite", "miniboss"} else primary
    if special == "miniboss" and party_size == 1:
        max_count = 1
    desired_roles = set(MINE_ENCOUNTER_THEMES.get(archetype, {}).get("roles", ()))
    frontline_roles = {"brute", "guardian", "blighter"}
    control_roles = {"controller", "blighter"}
    best: Optional[Tuple[float, Dict[str, int], int]] = None

    for _attempt in range(32):
        group = [primary_name]
        while len(group) < max_count:
            threat = sum(mine_enemy_threat(name) for name in group)
            if threat >= int(budget * 0.90) and rng.random() < 0.75:
                break
            role_counts: Dict[str, int] = {}
            base_counts: Dict[str, int] = {}
            for name in group:
                role = mine_enemy_role(name)
                base = mine_enemy_base_name(name)
                role_counts[role] = role_counts.get(role, 0) + 1
                base_counts[base] = base_counts.get(base, 0) + 1
            weighted: List[Tuple[str, float]] = []
            for name in pool:
                role = mine_enemy_role(name)
                if base_counts.get(name, 0) >= 2:
                    continue
                if party_size == 1 and role in control_roles and sum(role_counts.get(r, 0) for r in control_roles) >= 1:
                    continue
                projected = threat + mine_enemy_threat(name)
                if projected > budget + max(12, int(budget * 0.12)):
                    continue
                profile = MINE_ENEMY_PROFILES.get(name, {})
                weights = profile.get("weight_by_tier", [])
                tier = mine_enemy_tier(floor)
                weight = float(weights[tier]) if isinstance(weights, list) and tier < len(weights) else 1.0
                weight = max(1.0, weight)
                if role in desired_roles:
                    weight *= 3.0
                if role not in role_counts:
                    weight *= 1.8
                if not (frontline_roles & set(role_counts)) and role in frontline_roles:
                    weight *= 2.2
                weighted.append((name, weight))
            if not weighted:
                break
            names, weights = zip(*weighted)
            group.append(rng.choices(list(names), weights=list(weights), k=1)[0])

        counts = mine_group_counts(group)
        signature = mine_encounter_signature(counts)
        threat = sum(mine_enemy_threat(name) * amount for name, amount in counts.items())
        roles = {mine_enemy_role(name) for name in group}
        score = -abs(threat - budget)
        score += len(roles) * 7
        if len(group) >= 3:
            score += 10 if roles & frontline_roles else -25
        if party_size <= 2 and sum(1 for name in group if mine_enemy_role(name) in control_roles) > 1:
            score -= 30
        if signature in recent_signatures:
            score -= 90 + (len(recent_signatures) - recent_signatures.index(signature)) * 5
        if best is None or score > best[0]:
            best = (score, counts, threat)

    if best is None:
        counts = {primary_name: 1}
        return counts, mine_enemy_threat(primary_name), budget
    return best[1], best[2], budget


def mine_encounter_danger_label(threat: int, budget: int) -> str:
    ratio = float(threat) / max(1, int(budget))
    if ratio <= 0.82:
        return "Favorable"
    if ratio <= 1.05:
        return "Even"
    if ratio <= 1.18:
        return "Dangerous"
    return "Severe"


def mine_resolved_archetype(requested: str, special: str, counts: Dict[str, int]) -> str:
    if special == "miniboss":
        return "Miniboss"
    if special == "elite":
        return "Elite Patrol"
    total = sum(max(0, _safe_int(amount, 0)) for amount in counts.values())
    if total <= 1:
        return "Lone Prowler"
    roles = {mine_enemy_role(name) for name in counts}
    desired = set(MINE_ENCOUNTER_THEMES.get(requested, {}).get("roles", ()))
    if desired and not roles.intersection(desired):
        return "Balanced Patrol"
    return requested


def direct_mine_encounter(
    floor: int,
    enemy_name: str,
    enemy_id: str,
    state: object,
    party_size: int,
    seed: int,
) -> Dict[str, object]:
    floor = max(1, int(floor))
    party_size = max(1, min(FARMSTEAD_MAX_PARTY_MEMBERS, int(party_size)))
    rng = random.Random(seed)
    pool = mine_enemy_pool_for_floor(floor, enemy_name)
    archetype = mine_theme_for_encounter(floor, pool, rng)
    special = ""
    first_floor_actor = f":{floor}:0:" in str(enemy_id)
    elite_primary_fits = (
        mine_enemy_threat(f"Elite {mine_enemy_base_name(enemy_name)}")
        <= mine_encounter_threat_budget(floor, party_size) * 1.18
    )
    if floor >= 10 and floor % 10 == 0 and first_floor_actor and elite_primary_fits:
        special = "miniboss"
        archetype = "Miniboss"
    elif floor >= 18 and party_size >= 2 and rng.random() < min(0.24, 0.08 + floor / 250.0):
        special = "elite"
        archetype = "Elite Patrol"
    recent_signatures = mine_recent_history(state, "mine_recent_combat_signatures", 8)
    counts, threat, budget = mine_directed_group(
        enemy_name,
        floor,
        party_size,
        archetype if archetype in MINE_ENCOUNTER_THEMES else "Balanced Patrol",
        special,
        rng,
        recent_signatures,
    )
    archetype = mine_resolved_archetype(archetype, special, counts)
    recent_maps = mine_recent_history(state, "mine_recent_combat_maps", 6)
    map_archetype = archetype if archetype in MINE_ENCOUNTER_THEMES else "Balanced Patrol"
    map_name = mine_directed_map(floor, map_archetype, rng, recent_maps)
    signature = mine_encounter_signature(counts)
    danger = mine_encounter_danger_label(threat, budget)
    roles = sorted({mine_enemy_role(name) for name in counts})
    traits = [str(MINE_ENCOUNTER_THEMES.get(map_archetype, {}).get("trait", "mixed roles"))]
    if roles:
        traits.append("roles: " + ", ".join(roles))
    if special == "miniboss":
        traits.append("elite floor guardian")
    elif special == "elite":
        traits.append("elite leader")
    briefing = f"{archetype} | {danger} | Threat {threat}/{budget} | " + "; ".join(traits)
    return {
        "map_name": map_name,
        "enemy_counts": counts,
        "archetype": archetype,
        "special": special,
        "threat": threat,
        "budget": budget,
        "danger": danger,
        "traits": traits,
        "signature": signature,
        "briefing": briefing,
    }


def mine_enemy_tier(floor: int) -> int:
    floor = max(1, int(floor))
    if floor >= 36:
        return 5
    if floor >= 28:
        return 4
    if floor >= 20:
        return 3
    if floor >= 12:
        return 2
    if floor >= 6:
        return 1
    return 0


def mine_enemy_profile(name: str) -> Dict[str, object]:
    return MINE_ENEMY_PROFILES.get(str(name), MINE_ENEMY_PROFILES["Slime"])


def weighted_mine_enemy_name(floor: int, rng: random.Random) -> str:
    tier = mine_enemy_tier(floor)
    weighted: List[str] = []
    for name, profile in MINE_ENEMY_PROFILES.items():
        weights = profile.get("weight_by_tier", [])
        weight = int(weights[tier]) if isinstance(weights, list) and tier < len(weights) else 0
        weighted.extend([name] * max(0, weight))
    return rng.choice(weighted or ["Slime"])


def mine_enemy_count_for_floor(floor: int) -> int:
    floor = max(1, int(floor))
    return max(1, min(5, 1 + floor // 8))


def farmstead_companion_ids() -> List[str]:
    return list(FARMSTEAD_COMPANION_DATA.keys())


def farmstead_companion_data(companion_id: object) -> Dict[str, object]:
    data = FARMSTEAD_COMPANION_DATA.get(str(companion_id), {})
    return dict(data) if isinstance(data, dict) else {}


def clean_companion_profiles(companion_profiles: object, party_limit: int = FARMSTEAD_MAX_PARTY_MEMBERS) -> List[Dict[str, object]]:
    try:
        limit = max(0, min(FARMSTEAD_MAX_PARTY_MEMBERS - 1, int(party_limit) - 1))
    except Exception:
        limit = FARMSTEAD_MAX_PARTY_MEMBERS - 1
    if not isinstance(companion_profiles, list):
        return []
    profiles: List[Dict[str, object]] = []
    seen_names = {"Rook"}
    for profile in companion_profiles:
        if not isinstance(profile, dict):
            continue
        clean = dict(profile)
        name = " ".join(str(clean.get("name", "")).strip().split())[:16]
        if not name or name in seen_names:
            continue
        clean["name"] = name
        clean["battle_id"] = name
        seen_names.add(name)
        profiles.append(clean)
        if len(profiles) >= limit:
            break
    return profiles


def mine_combat_party_for_floor(floor: int, companion_profiles: object = None, party_limit: int = FARMSTEAD_MAX_PARTY_MEMBERS) -> List[str]:
    profiles = clean_companion_profiles(companion_profiles, party_limit)
    return ["Rook"] + [str(profile["battle_id"]) for profile in profiles]


def mine_combat_map_for_floor(floor: int, rng: Optional[random.Random] = None) -> str:
    tier = mine_enemy_tier(floor)
    pool = MINE_COMBAT_MAP_POOLS[min(tier, len(MINE_COMBAT_MAP_POOLS) - 1)]
    if rng is not None:
        return rng.choice(pool)
    return pool[(max(1, int(floor)) - 1) % len(pool)]


def mine_support_enemy_pool(floor: int, primary: str) -> List[str]:
    floor = max(1, int(floor))
    if floor < 6:
        pool = ["Slime", "Razor Hare"]
    elif floor < 12:
        pool = ["Slime", "Sporeling", "Razor Hare", "Marsh Toad"]
    elif floor < 20:
        pool = ["Sporeling", "Rockback", "Marsh Toad", "Cave Lynx", "Gloomcap"]
    elif floor < 28:
        pool = ["Wisp", "Burrower", "Thornback", "Cave Lynx", "Gloomcap"]
    elif floor < 36:
        pool = ["Wisp", "Frost Moth", "Ember Imp", "Crystal Spider", "Thornback"]
    else:
        pool = ["Frost Moth", "Ember Imp", "Crystal Spider", "Burrower", "Thornback"]
    return [name for name in pool if name != primary] or ["Slime"]


def mine_encounter_counts(enemy_name: str, floor: int, rng: random.Random, party_size: int = 1) -> Dict[str, int]:
    floor = max(1, int(floor))
    party_size = max(1, min(FARMSTEAD_MAX_PARTY_MEMBERS, int(party_size)))
    counts: Dict[str, int] = {str(enemy_name): 1}
    if floor < 10 and rng.random() < 0.60:
        support = rng.choice(mine_support_enemy_pool(floor, str(enemy_name)))
        counts[support] = counts.get(support, 0) + 1
    if floor >= 10 and rng.random() < 0.35:
        support = rng.choice(mine_support_enemy_pool(floor, str(enemy_name)))
        counts[support] = counts.get(support, 0) + 1
    if floor >= 24 and rng.random() < 0.25:
        counts[str(enemy_name)] = counts.get(str(enemy_name), 0) + 1
    if floor >= 34 and rng.random() < 0.20:
        support = rng.choice(mine_support_enemy_pool(floor, str(enemy_name)))
        counts[support] = counts.get(support, 0) + 1
    if party_size >= 2 and floor >= 6:
        support = rng.choice(mine_support_enemy_pool(floor, str(enemy_name)))
        counts[support] = counts.get(support, 0) + 1
    if party_size >= 3 and floor >= 12:
        support = rng.choice(mine_support_enemy_pool(floor + 4, str(enemy_name)))
        counts[support] = counts.get(support, 0) + 1
    if party_size >= 4 and floor >= 18:
        if floor >= 28 and rng.random() < 0.35:
            counts[f"Elite {enemy_name}"] = counts.get(f"Elite {enemy_name}", 0) + 1
        else:
            support = rng.choice(mine_support_enemy_pool(floor + 8, str(enemy_name)))
            counts[support] = counts.get(support, 0) + 1
    cap = 2 if party_size == 1 else min(6, 2 + party_size)
    trimmed: Dict[str, int] = {}
    total = 0
    for name, amount in counts.items():
        if total >= cap:
            break
        keep = min(int(amount), cap - total)
        if keep > 0:
            trimmed[name] = keep
            total += keep
    return trimmed


def mine_objective_for_encounter(floor: int, enemy_name: str, counts: Dict[str, int]) -> Tuple[str, Dict[str, int]]:
    floor = max(1, int(floor))
    enemy_name = str(enemy_name)
    total_enemies = sum(max(0, _safe_int(value, 0)) for value in (counts or {}).values())
    if floor >= 30 and enemy_name in {"Wisp", "Frost Moth", "Ember Imp"}:
        return "Survive", {"round_goal": 4 + min(2, total_enemies)}
    if floor >= 24 and floor % 6 == 0:
        return "Hold Zone", {"hold_goal": 2 + min(2, floor // 18)}
    if floor >= 12 and enemy_name in {"Rockback", "Burrower", "Thornback", "Sporeling"}:
        return "Destroy Objects", {"object_goal": 2 + (1 if floor >= 28 else 0)}
    return "Defeat All", {}


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalized_combat_equipment_name(slot: str, name: object) -> str:
    info = COMBAT_EQUIPMENT_SLOTS.get(str(slot))
    if not info:
        return str(name or "")
    _field_name, data, default = info
    raw = str(name or default)
    return raw if raw in data else default


def normalized_combat_equipment_names(state: object) -> Dict[str, str]:
    names: Dict[str, str] = {}
    for slot, (field_name, _data, default) in COMBAT_EQUIPMENT_SLOTS.items():
        names[slot] = normalized_combat_equipment_name(slot, getattr(state, field_name, default))
    return names


def sanitize_combat_equipment(state: object) -> List[str]:
    """Repair invalid equipped gear fields in-place and report what changed."""
    messages: List[str] = []
    if state is None:
        return messages
    for slot, (field_name, data, default) in COMBAT_EQUIPMENT_SLOTS.items():
        current = str(getattr(state, field_name, default) or default)
        if current not in data:
            setattr(state, field_name, default)
            messages.append(f"{slot.title()} reset to {default}.")
    return messages


def combat_equipment_mods(state: object) -> Dict[str, int]:
    names = normalized_combat_equipment_names(state)
    weapon = COMBAT_WEAPON_DATA[names["weapon"]]
    armor = COMBAT_ARMOR_DATA[names["armor"]]
    accessory = COMBAT_ACCESSORY_DATA[names["accessory"]]
    pieces = [weapon, armor, accessory]
    return {
        "attack": sum(int(piece.get("attack", 0) or 0) for piece in pieces),
        "defense": sum(int(piece.get("defense", 0) or 0) for piece in pieces),
        "max_hp": sum(int(piece.get("max_hp", 0) or 0) for piece in pieces),
        "max_focus": sum(int(piece.get("max_focus", 0) or 0) for piece in pieces),
    }


def farmstead_combat_items(inventory: Dict[str, int]) -> Dict[str, int]:
    items: Dict[str, int] = {}
    for item_name in FARMSTEAD_COMBAT_ITEM_DATA:
        qty = _safe_int((inventory or {}).get(item_name, 0), 0)
        if qty > 0:
            items[item_name] = min(qty, 9)
    return items


def player_tactical_stat_bonuses(state: object) -> Dict[str, int]:
    progress_store = getattr(state, "combat_party_progress", {}) or {}
    player_progress = progress_store.get("player", {}) if isinstance(progress_store, dict) else {}
    if not isinstance(player_progress, dict):
        player_progress = {}
    return {
        "hp_bonus": max(0, _safe_int(player_progress.get("hp_bonus", 0), 0)),
        "mp_bonus": max(0, _safe_int(player_progress.get("mp_bonus", 0), 0)),
        "damage_bonus": max(0, _safe_int(player_progress.get("damage_bonus", 0), 0)),
    }


def farmstead_combat_profile(state: object) -> Dict[str, object]:
    mods = combat_equipment_mods(state)
    base_max_hp = max(1, _safe_int(getattr(state, "combat_max_hp", DEFAULT_COMBAT_MAX_HP), DEFAULT_COMBAT_MAX_HP))
    base_effective_max_hp = max(1, base_max_hp + mods["max_hp"])
    base_max_focus = max(0, _safe_int(getattr(state, "combat_max_focus", DEFAULT_COMBAT_MAX_FOCUS), DEFAULT_COMBAT_MAX_FOCUS))
    base_effective_max_focus = max(0, base_max_focus + mods["max_focus"])
    equipment_names = normalized_combat_equipment_names(state)
    weapon_name = equipment_names["weapon"]
    weapon = COMBAT_WEAPON_DATA[weapon_name]
    progress_store = getattr(state, "combat_party_progress", {}) or {}
    player_progress = progress_store.get("player", {}) if isinstance(progress_store, dict) else {}
    tactical_mods = player_tactical_stat_bonuses(state)
    effective_max_hp = max(1, base_effective_max_hp + tactical_mods["hp_bonus"])
    effective_max_focus = max(0, base_effective_max_focus + tactical_mods["mp_bonus"])
    base_attack = max(1, _safe_int(getattr(state, "combat_attack", DEFAULT_COMBAT_ATTACK), DEFAULT_COMBAT_ATTACK) + mods["attack"])
    current_hp = _safe_int(getattr(state, "combat_current_hp", effective_max_hp), effective_max_hp)
    current_focus = _safe_int(getattr(state, "combat_focus", effective_max_focus), effective_max_focus)
    return {
        "progression_id": "player",
        "name": str(getattr(state, "player_name", "Farmer") or "Farmer"),
        "color": str(getattr(state, "player_color", "White") or "White"),
        "level": max(1, _safe_int(getattr(state, "combat_level", DEFAULT_COMBAT_LEVEL), DEFAULT_COMBAT_LEVEL)),
        "exp": max(0, _safe_int(getattr(state, "combat_exp", DEFAULT_COMBAT_EXP), DEFAULT_COMBAT_EXP)),
        "exp_to_next": max(1, _safe_int(getattr(state, "combat_exp_to_next", DEFAULT_COMBAT_EXP_TO_NEXT), DEFAULT_COMBAT_EXP_TO_NEXT)),
        "base_max_hp": base_effective_max_hp,
        "max_hp": effective_max_hp,
        "current_hp": max(1, min(effective_max_hp, current_hp)),
        "base_attack": base_attack,
        "attack": max(1, base_attack + tactical_mods["damage_bonus"]),
        "defense": max(0, _safe_int(getattr(state, "combat_defense", DEFAULT_COMBAT_DEFENSE), DEFAULT_COMBAT_DEFENSE) + mods["defense"]),
        "base_max_focus": base_effective_max_focus,
        "max_focus": effective_max_focus,
        "focus": max(0, min(effective_max_focus, current_focus)),
        "skill_points": max(0, _safe_int(getattr(state, "combat_skill_points", DEFAULT_COMBAT_SKILL_POINTS), DEFAULT_COMBAT_SKILL_POINTS)),
        "weapon": weapon_name,
        "weapon_range_min": int(weapon.get("range_min", 1)),
        "weapon_range_max": int(weapon.get("range_max", 1)),
        "armor": equipment_names["armor"],
        "accessory": equipment_names["accessory"],
        "tactical_hp_bonus": tactical_mods["hp_bonus"],
        "tactical_focus_bonus": tactical_mods["mp_bonus"],
        "tactical_damage_bonus": tactical_mods["damage_bonus"],
        "combat_items": farmstead_combat_items(getattr(state, "inventory", {}) or {}),
        "progression": dict(player_progress) if isinstance(player_progress, dict) else {},
        "starting_class": str(getattr(state, "player_starting_class", "Vanguard") or "Vanguard"),
    }


def build_player_combat_profile(state: object) -> Dict[str, object]:
    """Named wrapper for UI callers; battle launch uses the same profile."""
    return farmstead_combat_profile(state)


def restore_combat_state_after_sleep(state: object) -> None:
    profile = farmstead_combat_profile(state)
    state.combat_current_hp = int(profile["max_hp"])
    state.combat_focus = int(profile["max_focus"])


def mine_combat_exp_for_defeated(defeated_enemies: List[str], floor: int) -> int:
    floor_bonus = max(0, int(floor) // 6)
    total = 0
    for raw_name in defeated_enemies or []:
        name = str(raw_name)
        base = name.replace("Elite ", "").strip()
        profile = mine_enemy_profile(base)
        total += int(profile.get("exp_reward", 6)) + floor_bonus
    return total


def grant_combat_exp(state: object, amount: int) -> Tuple[int, List[str]]:
    amount = max(0, int(amount))
    if amount <= 0:
        return 0, []
    state.combat_exp = max(0, _safe_int(getattr(state, "combat_exp", 0), 0)) + amount
    state.combat_exp_to_next = max(1, _safe_int(getattr(state, "combat_exp_to_next", DEFAULT_COMBAT_EXP_TO_NEXT), DEFAULT_COMBAT_EXP_TO_NEXT))
    state.combat_level = max(1, _safe_int(getattr(state, "combat_level", DEFAULT_COMBAT_LEVEL), DEFAULT_COMBAT_LEVEL))
    messages: List[str] = []
    while state.combat_exp >= state.combat_exp_to_next:
        state.combat_exp -= state.combat_exp_to_next
        state.combat_level += 1
        state.stamina = max(
            0,
            _safe_int(getattr(state, "stamina", 100), 100) + 5,
        )
        hp_gain = 4 if state.combat_level % 2 else 5
        state.combat_max_hp = max(DEFAULT_COMBAT_MAX_HP, _safe_int(getattr(state, "combat_max_hp", DEFAULT_COMBAT_MAX_HP), DEFAULT_COMBAT_MAX_HP)) + hp_gain
        state.combat_current_hp = min(state.combat_max_hp, _safe_int(getattr(state, "combat_current_hp", state.combat_max_hp), state.combat_max_hp) + hp_gain)
        state.combat_attack = max(DEFAULT_COMBAT_ATTACK, _safe_int(getattr(state, "combat_attack", DEFAULT_COMBAT_ATTACK), DEFAULT_COMBAT_ATTACK)) + 1
        if state.combat_level % 3 == 0:
            state.combat_defense = max(0, _safe_int(getattr(state, "combat_defense", DEFAULT_COMBAT_DEFENSE), DEFAULT_COMBAT_DEFENSE)) + 1
        if state.combat_level % 2 == 0:
            state.combat_max_focus = max(DEFAULT_COMBAT_MAX_FOCUS, _safe_int(getattr(state, "combat_max_focus", DEFAULT_COMBAT_MAX_FOCUS), DEFAULT_COMBAT_MAX_FOCUS)) + 1
            state.combat_focus = min(state.combat_max_focus, _safe_int(getattr(state, "combat_focus", state.combat_max_focus), state.combat_max_focus) + 1)
        state.combat_skill_points = max(0, _safe_int(getattr(state, "combat_skill_points", 0), 0)) + 1
        state.combat_exp_to_next = int(state.combat_exp_to_next * 1.35) + 8
        messages.append(
            f"Combat Level Up! Level {state.combat_level}. "
            "Maximum stamina +5."
        )
    return amount, messages


def apply_party_status_to_combat_state(state: object, result: object) -> Dict[str, int]:
    profile = farmstead_combat_profile(state)
    player_name = str(profile["name"])
    party_status = getattr(result, "party_status", {}) or {}
    status = party_status.get(player_name)
    if status is None and party_status:
        status = next(iter(party_status.values()))
    if not isinstance(status, dict):
        return {}
    max_hp = max(1, _safe_int(status.get("max_hp", profile["max_hp"]), int(profile["max_hp"])))
    # Tactical combat may end with the player knocked out at 0 HP while
    # companions finish the fight. The overworld has no unconscious state, so
    # persist the same post-battle stabilization used after a full-party defeat.
    hp = max(1, min(max_hp, _safe_int(status.get("hp", profile["current_hp"]), int(profile["current_hp"]))))
    max_focus = max(0, _safe_int(status.get("max_mp", profile["max_focus"]), int(profile["max_focus"])))
    focus = max(0, min(max_focus, _safe_int(status.get("mp", profile["focus"]), int(profile["focus"]))))
    state.combat_current_hp = hp
    state.combat_focus = focus
    inventory = status.get("inventory", {})
    return {str(k): max(0, _safe_int(v, 0)) for k, v in inventory.items()} if isinstance(inventory, dict) else {}


def consumed_combat_items(starting_items: Dict[str, int], remaining_items: Dict[str, int]) -> Dict[str, int]:
    consumed: Dict[str, int] = {}
    for item_name, start_qty in (starting_items or {}).items():
        start = max(0, _safe_int(start_qty, 0))
        remaining = max(0, _safe_int((remaining_items or {}).get(item_name, 0), 0))
        used = max(0, start - remaining)
        if used:
            consumed[str(item_name)] = used
    return consumed


def mine_battle_request_for_enemy(
    floor: int,
    enemy: Dict[str, object],
    state: object,
    companion_profiles: object = None,
    party_limit: Optional[int] = None,
    encounter_kind: str = "mine",
):
    from ascii_battle_prototype.combat.results import BattleRequest

    enemy_name = str(enemy.get("species", "Slime"))
    enemy_id = str(enemy.get("id", "mine-enemy"))
    player_profile = farmstead_combat_profile(state)
    if party_limit is None:
        party_limit = _safe_int(getattr(state, "max_party_members", FARMSTEAD_MAX_PARTY_MEMBERS), FARMSTEAD_MAX_PARTY_MEMBERS)
    party_limit = max(1, min(FARMSTEAD_MAX_PARTY_MEMBERS, int(party_limit)))
    party_tactic = normalized_farmstead_party_tactic(getattr(state, "party_tactic", "Balanced"))
    companions = clean_companion_profiles(companion_profiles, party_limit)
    progression_keys = {str(player_profile["name"]): "player"}
    for companion in companions:
        companion_id = str(companion.get("id", companion.get("npc_id", companion.get("name", ""))) or "")
        companion_name = str(companion.get("battle_id", companion.get("name", "")) or "")
        if companion_id and companion_name:
            progression_keys[companion_name] = companion_id
    encounter_cycle = (
        _safe_int(getattr(state, "mine_combat_victories", 0), 0)
        + _safe_int(getattr(state, "mine_combat_flees", 0), 0)
        + _safe_int(getattr(state, "mine_combat_defeats", 0), 0)
    )
    seed_text = "|".join([
        enemy_id,
        str(int(floor)),
        enemy_name,
        str(_safe_int(getattr(state, "mine_seed", 4242), 4242)),
        str(_safe_int(getattr(state, "year", 1), 1)),
        str(_safe_int(getattr(state, "month", 1), 1)),
        str(_safe_int(getattr(state, "day", 1), 1)),
        str(encounter_cycle),
    ])
    seed = sum((index + 1) * ord(ch) for index, ch in enumerate(seed_text)) & 0xFFFFFFFF
    party_size = 1 + len(companions)
    if encounter_kind == "mine":
        directed = direct_mine_encounter(floor, enemy_name, enemy_id, state, party_size, seed)
        counts = dict(directed["enemy_counts"])
        map_name = str(directed["map_name"])
    else:
        count_rng = random.Random(seed ^ 0x5A17)
        map_rng = random.Random(seed ^ 0xA53C)
        counts = mine_encounter_counts(enemy_name, floor, count_rng, party_size=party_size)
        map_name = mine_combat_map_for_floor(floor, map_rng)
        directed = {
            "archetype": "Hostile Group",
            "special": "",
            "threat": sum(mine_enemy_threat(name) * amount for name, amount in counts.items()),
            "budget": mine_encounter_threat_budget(floor, party_size),
            "danger": "",
            "traits": [],
            "signature": mine_encounter_signature(counts),
            "briefing": "",
        }
    objective, objective_params = mine_objective_for_encounter(floor, enemy_name, counts)
    return BattleRequest(
        source="ascii_farmstead",
        map_name=map_name,
        enemy_counts=counts,
        objective=objective,
        objective_params=objective_params,
        party_ids=mine_combat_party_for_floor(floor, companions, party_limit),
        mission_id=f"mine-floor-{int(floor)}",
        mission_name=f"Mine Floor {int(floor)}: {directed['archetype']}",
        reward_theme="mine",
        difficulty_hint=f"{directed['danger'] or 'Encounter'} threat:{directed['threat']}/{directed['budget']}",
        return_context={
            "location": "Mine",
            "floor": int(floor),
            "enemy_id": enemy_id,
            "enemy_name": enemy_name,
            "encounter_variant": seed,
            "encounter_kind": encounter_kind,
            "encounter_map": map_name,
            "encounter_archetype": directed["archetype"],
            "encounter_special": directed["special"],
            "encounter_threat": directed["threat"],
            "encounter_budget": directed["budget"],
            "encounter_danger": directed["danger"],
            "encounter_traits": list(directed["traits"]),
            "encounter_signature": directed["signature"],
            "encounter_briefing": directed["briefing"],
            "farm_player": player_profile,
            "farm_player_name": str(player_profile["name"]),
            "farm_player_items": dict(player_profile.get("combat_items", {})),
            "farm_companions": companions,
            "farm_party_limit": party_limit,
            "farm_party_tactic": party_tactic,
            "farm_progression_keys": progression_keys,
            "farm_combat_campaign_inventory": {},
            "farm_combat_item_loadout_bonus": dict(getattr(state, "combat_item_loadout_bonus", {}) or {}),
        },
        world_flags_on_victory=[f"mine:floor:{int(floor)}:enemy_defeated"],
        world_flags_on_defeat=[f"mine:floor:{int(floor)}:party_defeated"],
        allow_flee=True,
        is_debug=False,
    )


def run_mine_battle(request):
    from ascii_battle_prototype.combat.main import run_battle_request

    return run_battle_request(request)


def translated_battle_loot(loot: Dict[str, int]) -> Tuple[int, Dict[str, int]]:
    money = 0
    items: Dict[str, int] = {}
    for raw_name, raw_amount in (loot or {}).items():
        try:
            amount = max(0, int(raw_amount))
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            continue
        name = str(raw_name)
        if name == "Coin":
            money += amount * 5
            continue
        translated = MINE_COMBAT_LOOT_ALIASES.get(name, name)
        if translated:
            items[translated] = items.get(translated, 0) + amount
    return money, items


def combat_result_outcome(result: object) -> str:
    return str(getattr(result, "outcome", "") or getattr(result, "result", "") or "abandoned").lower()
