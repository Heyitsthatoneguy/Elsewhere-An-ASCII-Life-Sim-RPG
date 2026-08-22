from __future__ import annotations

from typing import Dict, List


def mission_builtin_presets() -> List[Dict[str, object]]:
    return [
        {
            "name": "Farm Pest Trouble",
            "map": "Spring Bloomfield",
            "enemies": ["Slime", "Crow", "Razor Hare", "Sporeling"],
            "objective": "Destroy Objects",
            "object_goal": 3,
            "theme": "farm pests / crop protection",
            "flavor": "Pests are tearing through a spring field. Clear them out and smash the damaged nests.",
        },
        {
            "name": "Mine Cleanup",
            "map": "Moonlit Quarry",
            "enemies": ["Rockback", "Burrower", "Wisp", "Crystal Spider"],
            "objective": "Defeat All",
            "theme": "stone, ore, and mine safety",
            "flavor": "A work crew cannot reach the lower quarry while monsters hold the lantern path.",
        },
        {
            "name": "Wilderness Rescue",
            "map": "Twinlane Grove",
            "enemies": ["Cave Lynx", "Boar", "Vine", "Razor Hare"],
            "objective": "Protect Ally",
            "theme": "rescue / foraging route",
            "flavor": "A villager is pinned down near the old grove. Protect the party while clearing a route out.",
        },
        {
            "name": "Supply Recovery",
            "map": "Amber Harvest",
            "enemies": ["Bandit", "Wolf", "Thornback", "Razor Hare"],
            "objective": "Destroy Objects",
            "object_goal": 2,
            "theme": "lost supplies and harvest salvage",
            "flavor": "Bandits left supply crates scattered through the field. Break the marked caches and drive them off.",
        },
        {
            "name": "Stronghold Breach",
            "map": "Gatehouse Bastion",
            "enemies": ["Shield Guard", "Bandit", "Ember Imp", "Thornback", "Burrower"],
            "objective": "Hold Zone",
            "hold_goal": 3,
            "theme": "reclaim gate / fortified encounter",
            "flavor": "Take the breach and hold it long enough for the town crew to secure the gate.",
        },
        {
            "name": "Frostpine Escort",
            "map": "Frostpine Crossing",
            "enemies": ["Wisp", "Frost Moth", "Wolf", "Rockback"],
            "objective": "Escape",
            "theme": "winter escort / safe passage",
            "flavor": "Guide the party across the frozen crossing before the cold creatures collapse the route.",
        },
        {
            "name": "Swamp Bloom Trouble",
            "map": "Briarfall Basin",
            "enemies": ["Marsh Toad", "Gloomcap", "Vine", "Thornback"],
            "objective": "Survive",
            "round_goal": 4,
            "theme": "poison plants and marsh cleanup",
            "flavor": "Hold out while the marsh bloom weakens, then finish the cleanup or retreat safely.",
        },
        {
            "name": "Arsenal Recovery",
            "map": "Rampart Arsenal",
            "enemies": ["Bandit", "Ember Imp", "Shield Guard", "Clockwork Beetle", "Elite Bandit"],
            "objective": "Destroy Objects",
            "object_goal": 3,
            "theme": "stronghold supplies / weapon salvage",
            "flavor": "Recover the arsenal by breaking marked weapon caches and clearing the raiders.",
        },
        {
            "name": "Relic Arrow Nest",
            "map": "Frostwall Redoubt",
            "enemies": ["Relic Archer", "Clockwork Beetle", "Shardling", "Crystal Spider"],
            "objective": "Hold Zone",
            "hold_goal": 3,
            "theme": "ruin archers / relic salvage",
            "flavor": "Old mechanisms have claimed a ridge room. Hold the approach while the party breaks their firing line.",
        },
    ]

