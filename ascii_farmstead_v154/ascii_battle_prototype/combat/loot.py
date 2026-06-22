from __future__ import annotations

from typing import Dict


def loot_profile_for_enemy(base: str) -> Dict[str, Dict[str, int]]:
    profiles: Dict[str, Dict[str, Dict[str, int]]] = {
        "Training Dummy": {
            "common": {"Coin": 1},
            "uncommon": {},
            "rare": {},
        },
        "Crow": {
            "common": {"Coin": 4, "Crow Feather": 1},
            "uncommon": {"Shard": 1},
            "rare": {"Wisp Spark": 1},
        },
        "Boar": {
            "common": {"Coin": 8, "Hide": 1},
            "uncommon": {"Boar Tusk": 1},
            "rare": {"Guard Tonic": 1},
        },
        "Vine": {
            "common": {"Coin": 5, "Root Fiber": 1},
            "uncommon": {"Tonic": 1},
            "rare": {"Ancient Seed": 1},
        },
        "Slime": {
            "common": {"Coin": 3, "Gel": 1},
            "uncommon": {"Slime Core": 1},
            "rare": {"Tonic": 1},
        },
        "Wolf": {
            "common": {"Coin": 5, "Fang": 1},
            "uncommon": {"Wolf Pelt": 1},
            "rare": {"Hare Needle": 1},
        },
        "Bandit": {
            "common": {"Coin": 7, "Bandit Token": 1},
            "uncommon": {"Throwing Knife": 1},
            "rare": {"Supply Cache": 1},
        },
        "Shield Guard": {
            "common": {"Coin": 8, "Shield Fragment": 1},
            "uncommon": {"Guard Tonic": 1, "Hide": 1},
            "rare": {"Relic Cache": 1},
        },
        "Sporeling": {
            "common": {"Coin": 4, "Spore Cap": 1},
            "uncommon": {"Tonic": 1},
            "rare": {"Ancient Seed": 1},
        },
        "Wisp": {
            "common": {"Coin": 5, "Wisp Spark": 1},
            "uncommon": {"Shard": 1},
            "rare": {"Frost Wing": 1},
        },
        "Rockback": {
            "common": {"Coin": 9, "Stone": 2},
            "uncommon": {"Rock Shell": 1, "Shard": 1},
            "rare": {"Relic Cache": 1},
        },
        "Marsh Toad": {
            "common": {"Coin": 5, "Toad Oil": 1},
            "uncommon": {"Tonic": 1},
            "rare": {"Slime Core": 1},
        },
        "Razor Hare": {
            "common": {"Coin": 5, "Hare Needle": 1},
            "uncommon": {"Fang": 1},
            "rare": {"Crow Feather": 1},
        },
        "Ember Imp": {
            "common": {"Coin": 6, "Ember Cinder": 1},
            "uncommon": {"Shard": 1, "Gel": 1},
            "rare": {"Relic Cache": 1},
        },
        "Frost Moth": {
            "common": {"Coin": 6, "Frost Wing": 1},
            "uncommon": {"Wisp Spark": 1, "Tonic": 1},
            "rare": {"Shard": 2},
        },
        "Crystal Spider": {
            "common": {"Coin": 7, "Spider Silk": 1},
            "uncommon": {"Crystal Fang": 1, "Shard": 1},
            "rare": {"Relic Fragment": 1},
        },
        "Cave Lynx": {
            "common": {"Coin": 7, "Lynx Claw": 1},
            "uncommon": {"Hide": 1, "Fang": 1},
            "rare": {"Crystal Fang": 1},
        },
        "Gloomcap": {
            "common": {"Coin": 6, "Gloom Spores": 1},
            "uncommon": {"Spore Cap": 1, "Tonic": 1},
            "rare": {"Ancient Seed": 1},
        },
        "Burrower": {
            "common": {"Coin": 8, "Burrow Claw": 1},
            "uncommon": {"Stone": 2},
            "rare": {"Rock Shell": 1},
        },
        "Thornback": {
            "common": {"Coin": 8, "Quill Plate": 1},
            "uncommon": {"Hide": 1, "Spore Cap": 1},
            "rare": {"Shield Fragment": 1},
        },
        "Dustling": {
            "common": {"Coin": 3, "Dust Silk": 1},
            "uncommon": {"Old Coin": 1},
            "rare": {"Relic Fragment": 1},
        },
        "Ruin Bat": {
            "common": {"Coin": 4, "Bat Wing": 1},
            "uncommon": {"Dust Silk": 1},
            "rare": {"Old Coin": 2},
        },
        "Moss Haunt": {
            "common": {"Coin": 5, "Ruin Scrap": 1},
            "uncommon": {"Dust Silk": 1, "Tonic": 1},
            "rare": {"Ancient Seed": 1},
        },
        "Shardling": {
            "common": {"Coin": 6, "Relic Fragment": 1},
            "uncommon": {"Shard": 1},
            "rare": {"Stone Sigil": 1},
        },
        "Clockwork Beetle": {
            "common": {"Coin": 7, "Clockwork Carapace": 1},
            "uncommon": {"Ancient Cog": 1},
            "rare": {"Stone Sigil": 1},
        },
        "Relic Archer": {
            "common": {"Coin": 8, "Relic Arrowhead": 1},
            "uncommon": {"Dust Silk": 1, "Shard": 1},
            "rare": {"Ancient Cog": 1},
        },
        "Hollow Sentinel": {
            "common": {"Coin": 10, "Ruin Scrap": 2},
            "uncommon": {"Ancient Cog": 1, "Relic Fragment": 1},
            "rare": {"Stone Sigil": 1, "Relic Cache": 1},
        },
        "Old Briarthorn": {
            "common": {"Coin": 28, "Briar Heart": 1, "Ancient Seed": 1},
            "uncommon": {"Stone": 2, "Shard": 3, "Spore Cap": 2, "Tonic": 2},
            "rare": {"Relic Cache": 2, "Root Fiber": 2},
        },
    }
    return profiles.get(base, {"common": {"Coin": 3}, "uncommon": {}, "rare": {}})

