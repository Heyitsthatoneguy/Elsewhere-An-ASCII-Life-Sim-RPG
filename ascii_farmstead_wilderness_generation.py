"""Versioned wilderness vocabulary, biome contracts, and generation audits.

This module is deliberately independent from ``FarmGame``.  The live world may
store one-character terrain cells for compact saves, but biome identity and tile
meaning should not be inferred from scattered string comparisons forever.
"""

from __future__ import annotations

import random

from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


WILDERNESS_GENERATION_VERSION = 2

# Three visually distinct, walkable plant markers. Their slot selects the
# corresponding plant/gatherable pair in a biome identity record.
BIOME_PLANT_SYMBOLS: Tuple[str, str, str] = ("✿", "❧", "♧")


CLIMATE_COMPASS_AXES: Tuple[Tuple[int, int], ...] = (
    (1, 0), (1, 1), (0, 1), (-1, 1),
    (-1, 0), (-1, -1), (0, -1), (1, -1),
)


def reachable_climate_axes(seed: int) -> Mapping[str, Tuple[int, int]]:
    """Return stable, well-separated directions for reachable major climates."""
    rng = random.Random(int(seed) ^ 0x5EEDC11A)
    ocean_index = rng.randrange(len(CLIMATE_COMPASS_AXES))
    # Keep the three headline climates in different broad directions.  Small
    # seeded offsets prevent every world from sharing one compass layout.
    offset = rng.choice((2, 3))
    desert_index = (ocean_index + offset) % len(CLIMATE_COMPASS_AXES)
    tundra_index = (ocean_index - rng.choice((2, 3))) % len(CLIMATE_COMPASS_AXES)
    if tundra_index == desert_index:
        tundra_index = (tundra_index - 1) % len(CLIMATE_COMPASS_AXES)
    return {
        "ocean": CLIMATE_COMPASS_AXES[ocean_index],
        "desert": CLIMATE_COMPASS_AXES[desert_index],
        "tundra": CLIMATE_COMPASS_AXES[tundra_index],
    }


def climate_axis_coordinates(wx: int, wy: int, axis: Tuple[int, int]) -> Tuple[float, float]:
    """Return forward and lateral distance relative to a compass climate axis."""
    dx, dy = int(axis[0]), int(axis[1])
    normalizer = 1.41421356237 if dx and dy else 1.0
    forward = (int(wx) * dx + int(wy) * dy) / normalizer
    lateral = abs(-int(wx) * dy + int(wy) * dx) / normalizer
    return forward, lateral


# Internal identifiers remain stable for old saves.  These are the secular names
# and descriptions that may be shown to the player.
SECULAR_STRUCTURE_PRESENTATION: Mapping[str, Mapping[str, str]] = {
    "wayside_shrine": {
        "name": "Wayside Rest",
        "role": "Waykeeper",
        "benefit": "A sheltered place for recovery, route records, and traveler news.",
        "activity": "Maintain the traveler rest",
        "fixture": "Heritage marker",
    },
    "dungeon_shrine": {
        "name": "Recovery Cache",
        "spent": "This recovery cache has already been used.",
    },
    "deep_shrine_floor_40": {
        "name": "Deep Vault",
        "reward": "vault reward",
    },
    "wilderness_shrine_venue": {
        "name": "Wayside Pavilion",
    },
}


# One authoritative meaning for persistent wilderness cells.  Context-specific
# actors and temporary overlays are deliberately kept outside the terrain grid.
WILDERNESS_TILE_SEMANTICS: Mapping[str, Mapping[str, object]] = {
    ".": {"id": "open_ground", "category": "ground", "walkable": True},
    ",": {"id": "soft_ground", "category": "ground", "walkable": True},
    ";": {"id": "meadow_ground", "category": "biome_ground", "walkable": True},
    "%": {"id": "woodland_ground", "category": "biome_ground", "walkable": True},
    "l": {"id": "hollow_ground", "category": "biome_ground", "walkable": True},
    "r": {"id": "wet_ground", "category": "biome_ground", "walkable": True},
    "x": {"id": "rocky_ground", "category": "biome_ground", "walkable": True},
    "`": {"id": "dry_ground", "category": "biome_ground", "walkable": True},
    '"': {"id": "cold_ground", "category": "biome_ground", "walkable": True},
    "[": {"id": "coastal_ground", "category": "biome_ground", "walkable": True},
    ":": {"id": "road", "category": "infrastructure", "walkable": True},
    "=": {"id": "bridge", "category": "infrastructure", "walkable": True},
    "~": {"id": "water", "category": "water", "walkable": False, "seasonal_walkable": True},
    "#": {"id": "constructed_barrier", "category": "barrier", "walkable": False},
    "T": {"id": "tree", "category": "natural_obstacle", "walkable": False},
    "o": {"id": "boulder", "category": "natural_obstacle", "walkable": False},
    "*": {"id": "stump_or_deadfall", "category": "natural_obstacle", "walkable": False},
    "^": {"id": "low_vegetation", "category": "decoration", "walkable": True},
    "✿": {"id": "biome_plant_flower", "category": "biome_gatherable", "walkable": True},
    "❧": {"id": "biome_plant_leaf", "category": "biome_gatherable", "walkable": True},
    "♧": {"id": "biome_plant_special", "category": "biome_gatherable", "walkable": True},
}


# Biome records are design contracts used by generation, rendering, wildlife,
# loot, and encounter work.  Roster entries are intentionally exclusive.
BIOME_IDENTITY_DATA: Mapping[str, Mapping[str, object]] = {
    "meadow": {
        "name": "Green Meadow", "base_tile": ";", "palette": "fresh green and yellow",
        "plants": ("White Clover", "Buttercup", "Meadow Yarrow"),
        "gatherables": ("Clover Sprig", "Buttercup Petal", "Yarrow Bundle"),
        "wildlife": ("Cottontail", "Meadowlark", "Field Mouse"),
        "fantasy_wildlife": ("Dewback",),
        "enemies": ("Briar Boar", "Pollen Mote", "Grassblade Lurker"),
    },
    "birch_grove": {
        "name": "Birch Grove", "base_tile": "%", "palette": "pale bark and light green",
        "plants": ("Silver Birch", "Wood Sorrel", "Red Raspberry"),
        "gatherables": ("Birch Bark", "Birch Sap", "Raspberry Cluster"),
        "wildlife": ("Snowshoe Hare", "Downy Woodpecker", "Roe Deer"),
        "fantasy_wildlife": ("Glimmer Moth",),
        "enemies": ("Pale Stalker", "Thornroot", "Whitebark Mauler"),
    },
    "pine_forest": {
        "name": "Pine Forest", "base_tile": "%", "palette": "deep evergreen and russet",
        "plants": ("Red Pine", "Common Juniper", "Pine Mushroom"),
        "gatherables": ("Pine Resin", "Juniper Berry", "Pine Mushroom Cap"),
        "wildlife": ("Red Squirrel", "Pine Marten", "Great Horned Owl"),
        "fantasy_wildlife": ("Ember Fox",),
        "enemies": ("Barkmaw", "Needleback", "Cinder Wasp"),
    },
    "old_growth": {
        "name": "Old-Growth Woodland", "base_tile": "%", "palette": "dark canopy and fern green",
        "plants": ("Ancient Oak", "Sword Fern", "Chanterelle"),
        "gatherables": ("Hardwood Burl", "Fern Fiddlehead", "Chanterelle Cluster"),
        "wildlife": ("Wild Boar", "Pine Grosbeak", "Dormouse"),
        "fantasy_wildlife": ("Mossback Tortoise",),
        "enemies": ("Hollow Trunk", "Vinejaw", "Canopy Prowler"),
    },
    "prairie": {
        "name": "Tallgrass Prairie", "base_tile": ";", "palette": "gold grass and open blue",
        "plants": ("Big Bluestem", "Purple Coneflower", "Wild Rye"),
        "gatherables": ("Bluestem Fiber", "Coneflower Head", "Wild Rye Grain"),
        "wildlife": ("Prairie Dog", "Pronghorn", "Greater Prairie-Chicken"),
        "fantasy_wildlife": ("Wind Hare",),
        "enemies": ("Razor Hopper", "Burrowfang", "Windstalker"),
    },
    "moorland": {
        "name": "Heather Moor", "base_tile": ";", "palette": "purple heather and slate",
        "plants": ("Bell Heather", "Dwarf Gorse", "Cloudberry"),
        "gatherables": ("Heather Bundle", "Gorse Fiber", "Cloudberry Cup"),
        "wildlife": ("Red Grouse", "Moor Pony", "Short-Eared Owl"),
        "fantasy_wildlife": ("Mist Hound",),
        "enemies": ("Mire Runner", "Lantern Wisp", "Heather Lurker"),
    },
    "bog": {
        "name": "Moss Bog", "base_tile": "r", "palette": "dark peat and acid green",
        "plants": ("Sphagnum Moss", "Pitcher Plant", "Bog Cranberry"),
        "gatherables": ("Peat Brick", "Pitcher Nectar", "Cranberry Handful"),
        "wildlife": ("Bog Turtle", "Marsh Newt", "American Bittern"),
        "fantasy_wildlife": ("Lantern Toad",),
        "enemies": ("Giant Leech", "Spore Toad", "Mud Lurker"),
    },
    "floodplain": {
        "name": "River Floodplain", "base_tile": "r", "palette": "willow green and river blue",
        "plants": ("Black Willow", "Broadleaf Cattail", "Watercress"),
        "gatherables": ("Willow Switch", "Cattail Reed", "Watercress Bunch"),
        "wildlife": ("River Otter", "Beaver", "Green Heron"),
        "fantasy_wildlife": ("River Drake",),
        "enemies": ("Reed Ambusher", "River Serpent", "Shellback"),
    },
    "alpine_meadow": {
        "name": "Alpine Meadow", "base_tile": "x", "palette": "bright flowers and grey peaks",
        "plants": ("Alpine Gentian", "Edelweiss", "Mountain Thyme"),
        "gatherables": ("Gentian Root", "Edelweiss Bloom", "Thyme Bundle"),
        "wildlife": ("Alpine Marmot", "Mountain Goat", "Golden Eagle"),
        "fantasy_wildlife": ("Frost Elk",),
        "enemies": ("Cliff Raptor", "Scree Crawler", "Storm Ram"),
    },
    "rocky_valley": {
        "name": "Rocky Valley", "base_tile": "x", "palette": "granite grey and mineral blue",
        "plants": ("Purple Saxifrage", "Cliff Stonecrop", "Rock Lichen"),
        "gatherables": ("Saxifrage Tuft", "Stonecrop Cutting", "Lichen Sheet"),
        "wildlife": ("Pika", "Rock Wren", "Bighorn Sheep"),
        "fantasy_wildlife": ("Crystal Beetle",),
        "enemies": ("Stonehide", "Shard Mite", "Ravine Hunter"),
    },
    "scrubland": {
        "name": "Dry Scrubland", "base_tile": "`", "palette": "sage green and dusty tan",
        "plants": ("Big Sagebrush", "Banana Yucca", "Rubber Rabbitbrush"),
        "gatherables": ("Sage Bundle", "Yucca Fiber", "Rabbitbrush Resin"),
        "wildlife": ("Black-Tailed Jackrabbit", "Gambel Quail", "Kit Fox"),
        "fantasy_wildlife": ("Glasswing Beetle",),
        "enemies": ("Spineback", "Dust Coyote", "Needle Drake"),
    },
    "dune_desert": {
        "name": "Dune Desert", "base_tile": "`", "palette": "warm sand and cactus green",
        "plants": ("Saguaro", "Century Agave", "Dune Verbena"),
        "gatherables": ("Cactus Fruit", "Agave Heart", "Verbena Petal"),
        "wildlife": ("Fennec", "Sandgrouse", "Fringe-Toed Lizard"),
        "fantasy_wildlife": ("Sunscale Drake",),
        "enemies": ("Sandlurker", "Glass Scorpion", "Sun Viper"),
    },
    "badlands": {
        "name": "Red Badlands", "base_tile": "`", "palette": "red clay and black stone",
        "plants": ("Fourwing Saltbush", "Greasewood", "Desert Marigold"),
        "gatherables": ("Saltbush Seed", "Greasewood Twig", "Marigold Head"),
        "wildlife": ("Roadrunner", "Collared Lizard", "Desert Bighorn"),
        "fantasy_wildlife": ("Canyon Glider",),
        "enemies": ("Bonejaw", "Redstone Beetle", "Canyon Stalker"),
    },
    "oasis": {
        "name": "Desert Oasis", "base_tile": "r", "palette": "palm green and clear cyan",
        "plants": ("Date Palm", "Cape Aloe", "Oasis Mint"),
        "gatherables": ("Fresh Date", "Aloe Gel", "Mint Sprig"),
        "wildlife": ("White Ibis", "Dorcas Gazelle", "Nile Monitor"),
        "fantasy_wildlife": ("Water Finder",),
        "enemies": ("Palm Creeper", "Well Wyrm", "Mirage Cat"),
    },
    "taiga": {
        "name": "Snowy Taiga", "base_tile": '"', "palette": "spruce green and snow white",
        "plants": ("Black Spruce", "Reindeer Lichen", "Lingonberry"),
        "gatherables": ("Spruce Gum", "Reindeer Lichen Mat", "Lingonberry Cup"),
        "wildlife": ("Moose", "Canada Lynx", "Boreal Chickadee"),
        "fantasy_wildlife": ("Frost Moth",),
        "enemies": ("Ice Prowler", "Snow Burrower", "Rime Wasp"),
    },
    "glacier": {
        "name": "Glacier Field", "base_tile": '"', "palette": "ice blue and exposed black rock",
        "plants": ("Snow Algae", "Map Lichen", "Frost Flower"),
        "gatherables": ("Algae Film", "Map Lichen Flake", "Frost Flower Crystal"),
        "wildlife": ("Snow Petrel", "Arctic Hare", "Rock Ptarmigan"),
        "fantasy_wildlife": ("Icewing",),
        "enemies": ("Rime Construct", "Crevasse Maw", "White Drake"),
    },
    "tidal_flat": {
        "name": "Tidal Flat", "base_tile": "[", "palette": "wet sand and sea green",
        "plants": ("Eelgrass", "Glasswort", "Bladderwrack"),
        "gatherables": ("Eelgrass Strand", "Glasswort Tip", "Bladderwrack Frond"),
        "wildlife": ("Fiddler Crab", "Sanderling", "Harbor Seal"),
        "fantasy_wildlife": ("Tide Skimmer",),
        "enemies": ("Brine Crawler", "Mud Crab", "Tide Lurker"),
    },
    "mangrove": {
        "name": "Mangrove Coast", "base_tile": "[", "palette": "root brown and brackish green",
        "plants": ("Red Mangrove", "Sea Purslane", "Brackish Fern"),
        "gatherables": ("Mangrove Bark", "Purslane Leaf", "Brackish Fern Curl"),
        "wildlife": ("Mudskipper", "Roseate Spoonbill", "Mangrove Cuckoo"),
        "fantasy_wildlife": ("Root Glider",),
        "enemies": ("Root Serpent", "Swamp Midge", "Mirecat"),
    },
    "tropical_isle": {
        "name": "Tropical Isle", "base_tile": "[", "palette": "bright green and turquoise",
        "plants": ("Coconut Palm", "Red Hibiscus", "Vanilla Orchid"),
        "gatherables": ("Coconut", "Hibiscus Flower", "Vanilla Pod"),
        "wildlife": ("Rainbow Lorikeet", "Marine Iguana", "Flying Fox"),
        "fantasy_wildlife": ("Cloudfin Lizard",),
        "enemies": ("Venom Frill", "Razor Crab", "Canopy Hunter"),
    },
}


def wilderness_tile_semantics(symbol: str) -> Mapping[str, object]:
    """Return stable terrain meaning without guessing from presentation."""
    return WILDERNESS_TILE_SEMANTICS.get(
        str(symbol), {"id": "unregistered", "category": "unknown", "walkable": False}
    )


def biome_base_tile(biome_id: str) -> str:
    record = BIOME_IDENTITY_DATA.get(str(biome_id), BIOME_IDENTITY_DATA["meadow"])
    return str(record["base_tile"])


def validate_biome_identity_data() -> List[str]:
    """Return contract errors, including cross-biome roster reuse."""
    errors: List[str] = []
    required = {"name", "base_tile", "palette", "plants", "gatherables", "wildlife", "fantasy_wildlife", "enemies"}
    exclusive_fields = ("plants", "gatherables", "wildlife", "fantasy_wildlife", "enemies")
    seen: Dict[str, Dict[str, str]] = {field: {} for field in exclusive_fields}
    for biome_id, record in BIOME_IDENTITY_DATA.items():
        missing = required - set(record)
        if missing:
            errors.append(f"{biome_id}: missing {', '.join(sorted(missing))}")
        if str(record.get("base_tile", "")) not in WILDERNESS_TILE_SEMANTICS:
            errors.append(f"{biome_id}: unregistered base tile {record.get('base_tile')!r}")
        for field in exclusive_fields:
            values = tuple(str(value).strip() for value in record.get(field, ()) if str(value).strip())
            if not values:
                errors.append(f"{biome_id}: empty {field}")
            if len(values) != len(set(values)):
                errors.append(f"{biome_id}: duplicate value inside {field}")
            for value in values:
                folded = value.casefold()
                previous = seen[field].get(folded)
                if previous and previous != biome_id:
                    errors.append(f"{field}: {value!r} reused by {previous} and {biome_id}")
                seen[field][folded] = biome_id
    return errors


_BIOME_ENEMY_INDEX: Dict[str, Tuple[str, int]] = {
    str(enemy): (str(biome_id), int(index))
    for biome_id, record in BIOME_IDENTITY_DATA.items()
    for index, enemy in enumerate(record.get("enemies", ()))
}


def biome_enemy_ecology(species: str) -> Dict[str, object]:
    """Return the map-combat identity for one detailed-biome enemy."""
    base = str(species or "").replace("Elite ", "").strip()
    indexed = _BIOME_ENEMY_INDEX.get(base)
    if indexed is None:
        return {}
    biome_id, slot = indexed
    identity = BIOME_IDENTITY_DATA[biome_id]
    role_profiles = (
        {"role": "hunter", "behavior": "hunter", "hp": 18, "attack": 5, "defense": 0, "range": 1, "dodge": 0.05},
        {"role": "skirmisher", "behavior": "darting", "hp": 15, "attack": 5, "defense": 0, "range": 1, "dodge": 0.16},
        {"role": "warden", "behavior": "guardian", "hp": 25, "attack": 6, "defense": 2, "range": 1, "dodge": 0.02, "slow": True},
    )
    profile = dict(role_profiles[slot])
    wet_biomes = {"bog", "floodplain", "oasis", "mangrove", "tidal_flat"}
    ranged_biomes = {"alpine_meadow", "rocky_valley", "badlands", "glacier", "dune_desert"}
    if slot == 2 and biome_id in wet_biomes:
        profile.update({"role": "controller", "behavior": "poisoner", "range": 3, "slow": False})
    elif slot == 2 and biome_id in ranged_biomes:
        profile.update({"role": "caster", "behavior": "shard_caster", "range": 4, "defense": 1, "slow": False})
    symbol = next((character.lower() for character in base if character.isalpha()), "e")
    profile.update({
        "species": base,
        "biome_id": biome_id,
        "biome_name": str(identity.get("name", biome_id.replace("_", " ").title())),
        "slot": slot,
        "symbol": symbol,
        "reward_item": str(tuple(identity.get("gatherables", ("Ruin Scrap",)))[slot]),
        "exp_reward": 10 + slot * 3,
        "description": (
            f"A {profile['role']} native to {identity.get('name', biome_id)}; "
            f"it uses the terrain as part of its attack."
        ),
    })
    return profile


def wilderness_grid_metrics(grid: Sequence[Sequence[str]]) -> Dict[str, float]:
    """Small deterministic readability metrics for generation tests and logs."""
    total = sum(len(row) for row in grid)
    counts = {
        "walkable": 0,
        "ground": 0,
        "infrastructure": 0,
        "water": 0,
        "natural_obstacle": 0,
        "unknown": 0,
    }
    for row in grid:
        for symbol in row:
            semantics = wilderness_tile_semantics(str(symbol))
            category = str(semantics.get("category", "unknown"))
            if bool(semantics.get("walkable", False)):
                counts["walkable"] += 1
            if category in counts:
                counts[category] += 1
            elif category == "biome_ground":
                counts["ground"] += 1
    result: Dict[str, float] = {key: float(value) for key, value in counts.items()}
    result["tiles"] = float(total)
    result["walkable_ratio"] = counts["walkable"] / max(1, total)
    result["obstacle_ratio"] = counts["natural_obstacle"] / max(1, total)
    return result
