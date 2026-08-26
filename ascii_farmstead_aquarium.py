"""Native aquarium simulation and stable terminal presentation for Elsewhere.

The aquarium is deliberately a household hobby inside the main game.  It uses
Elsewhere fish, dates, inventory, and saves; it does not own another currency,
calendar, shop, or save system.  Rendering is composed off-screen and changed
terminal rows are written in one batch to avoid the flicker of the standalone
prototype.
"""

from __future__ import annotations

import random
import re
import shutil
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ascii_farmstead_helpers import quantity_agreement
from ascii_farmstead_support import C, colorize, get_color_enabled, normalize_key, read_key_timeout


AQUARIUM_SCHEMA_VERSION = 2
AQUARIUM_FRAME_SECONDS = 0.18
AQUARIUM_HABITATS = ("Freshwater", "Saltwater", "Underground")
AQUARIUM_VARIANTS = ("Normal", "Speckled", "Golden", "Pale")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _wrap_text(text: str, width: int, max_lines: int = 3) -> List[str]:
    """Word-wrap status/message text instead of silently truncating it."""
    text = str(text or "").strip()
    if not text or width <= 0:
        return []
    lines = textwrap.wrap(text, max(1, width)) or [text[:width]]
    return lines[:max_lines]

# Individual lifespans are selected deterministically within these broad,
# species-informed ranges. They are measured in real in-game years: an
# aquarium is a long household commitment, not a short neglect timer.
AQUARIUM_LIFESPAN_YEARS: Dict[str, Tuple[int, int]] = {
    "Pond Minnow": (2, 4), "Bluegill": (5, 10), "Catfish": (10, 20),
    "Carp": (15, 30), "Sunfish": (5, 10), "Trout": (3, 7),
    "Bass": (8, 16), "Night Eel": (10, 20), "Ice Perch": (5, 10),
    "Cave Carp": (10, 20), "Blind Minnow": (3, 6), "Crystal Eel": (12, 24),
    "River Chub": (3, 7), "Brook Trout": (3, 7), "Rain Pike": (7, 12),
    "Tide Sardine": (2, 4), "Mackerel": (8, 16), "Sea Bass": (8, 16),
    "Silver Salmon": (3, 6), "Storm Cod": (12, 20), "Moon Eel": (10, 20),
    "Coral Dart": (3, 6), "Parrotfish": (7, 12), "Reef Grouper": (12, 24),
    "Sunfin Tuna": (12, 20), "Lantern Angelfish": (8, 16), "Pale Koi": (15, 30),
    "Mosquitofish": (1, 3), "Golden Shiner": (4, 8), "Pumpkinseed": (5, 10),
    "Mud Loach": (4, 8), "Yellow Perch": (7, 12), "Walleye": (10, 20),
    "Lake Sturgeon": (25, 50), "Rainbow Smelt": (2, 5), "Muskellunge": (10, 20),
    "Dace": (3, 6), "Smallmouth Bass": (8, 16), "Rainbow Trout": (4, 8),
    "Longnose Gar": (15, 30), "Steelhead": (4, 8), "Anchovy": (2, 4),
    "Red Snapper": (10, 20), "Halibut": (20, 40), "Pufferfish": (8, 15),
    "Swordfish": (12, 20), "Blue Marlin": (15, 25),
    "Meadow Darter": (2, 4), "Golden Tench": (10, 20),
    "Birchstream Trout": (4, 8), "Silver Burbot": (12, 22),
    "Pinewater Char": (6, 12), "Deepwater Cisco": (4, 8),
    "Fern Perch": (6, 12), "Timber Catfish": (15, 28),
    "Prairie Shiner": (3, 6), "Plains Paddlefish": (25, 45),
    "Heather Grayling": (5, 10), "Mist Eel": (12, 24),
    "Bog Lamprey": (6, 12), "Peat Pike": (10, 20),
    "Reed Killifish": (2, 4), "River Buffalo": (15, 30),
    "Snowmelt Dace": (3, 6), "Alpine Char": (8, 16),
    "Stonefin Sculpin": (4, 8), "Canyon Trout": (5, 10),
    "Arroyo Pupfish": (2, 5), "Desert Sucker": (10, 20),
    "Dune Tilapia": (6, 12), "Sand Basin Gar": (15, 28),
    "Red Mesa Catfish": (12, 24), "Canyon Chub": (4, 8),
    "Oasis Cichlid": (7, 14), "Datefin Barb": (6, 12),
    "Spruce Trout": (4, 8), "Boreal Pike": (12, 24),
    "Icewater Smelt": (3, 6), "Glacier Char": (10, 20),
    "Mudflat Goby": (3, 6), "Shelf Skate": (15, 30),
    "Archerfish": (5, 10), "Mangrove Snapper": (12, 24),
    "Reef Butterflyfish": (6, 12), "Cobalt Jack": (12, 22),
    "Grotto Tetra": (3, 7), "Limestone Loach": (7, 14),
    "Abyssal Cavefish": (18, 35),
}


# Each entry is right-facing.  Left-facing art is produced carefully instead
# of reversing arbitrary strings, which would turn brackets and eyes inside out.
FISH_SPRITES: Dict[str, Tuple[str, str]] = {
    "Pond Minnow": ("><>", "<><"),
    "Bluegill": ("><))>", "<((><"),
    "Catfish": ("=><))>", "<((><="),
    "Carp": ("><(((°>", "<°)))><"),
    "Sunfish": ("(°)>", "<(°)"),
    "Trout": ("--<°>>", "<<°>--"),
    "Bass": ("><{{°>", "<°}}><"),
    "Night Eel": ("~~<°>>", "<<°>~~"),
    "Ice Perch": ("-<◇>>", "<<◇>-"),
    "Cave Carp": ("><((·>", "<·))><"),
    "Blind Minnow": ("--°>", "<°--"),
    "Crystal Eel": ("~<◇>>>", "<<<◇>~"),
    "River Chub": ("><)°>", "<°(><"),
    "Brook Trout": ("--<°}>", "<{°>--"),
    "Rain Pike": ("---<°>>", "<<°>---"),
    "Tide Sardine": ("><·>", "<·><"),
    "Mackerel": ("=><°>>", "<<°><="),
    "Sea Bass": ("><{°}>", "<{°}><"),
    "Silver Salmon": ("--<◇}>", "<{◇>--"),
    "Storm Cod": ("><[°]>", "<[°]><"),
    "Moon Eel": ("~~<☾>>", "<<☾>~~"),
    "Coral Dart": (">{·}>", "<{·}<"),
    "Parrotfish": ("><{o°>", "<°o}><"),
    "Reef Grouper": ("><{{o}>", "<{o}}><"),
    "Sunfin Tuna": ("--<★}>>", "<<{★>--"),
    "Lantern Angelfish": ("><{✦}>", "<{✦}><"),
    "Pale Koi": ("><{{○°>", "<°○}}><"),
    "Mosquitofish": ("><·>", "<·><"),
    "Golden Shiner": ("><◇>", "<◇><"),
    "Pumpkinseed": ("(●)>", "<(●)"),
    "Mud Loach": ("~~<·>", "<·>~~"),
    "Yellow Perch": ("-<|||>", "<|||>-"),
    "Walleye": ("><{◉}>", "<{◉}><"),
    "Lake Sturgeon": ("==<°}>>", "<<{°>=="),
    "Rainbow Smelt": ("><≋>", "<≋><"),
    "Muskellunge": ("---<◆>>", "<<◆>---"),
    "Dace": ("><·>>", "<<·><"),
    "Smallmouth Bass": ("><{°>>", "<<°}><"),
    "Rainbow Trout": ("--<≋}>", "<{≋>--"),
    "Longnose Gar": ("====<°>", "<°>===="),
    "Steelhead": ("--<◇>>", "<<◇>--"),
    "Anchovy": ("><•>", "<•><"),
    "Red Snapper": ("><{♦}>", "<{♦}><"),
    "Halibut": ("__<°}>", "<{°>__"),
    "Pufferfish": ("<(●)>", "<(●)>"),
    "Swordfish": ("──╼<°>>", "<<°>╾──"),
    "Blue Marlin": ("───<★>>", "<<★>───"),
    "Meadow Darter": ("><✿>", "<✿><"),
    "Golden Tench": ("><((●>", "<●))><"),
    "Birchstream Trout": ("--<○}>", "<{○>--"),
    "Silver Burbot": ("~~<□>>", "<<□>~~"),
    "Pinewater Char": ("--<▲}>", "<{▲>--"),
    "Deepwater Cisco": ("=><◇>", "<◇><="),
    "Fern Perch": ("-<❧|>", "<|❧>-"),
    "Timber Catfish": ("=><[●]>", "<[●]><="),
    "Prairie Shiner": ("><✦>", "<✦><"),
    "Plains Paddlefish": ("──<◉}>", "<{◉>──"),
    "Heather Grayling": ("--<◆}>", "<{◆>--"),
    "Mist Eel": ("~~<·>>", "<<·>~~"),
    "Bog Lamprey": ("~~~<○>", "<○>~~~"),
    "Peat Pike": ("---<■>>", "<<■>---"),
    "Reed Killifish": ("><│·>", "<·│><"),
    "River Buffalo": ("=><{{●>", "<●}}><="),
    "Snowmelt Dace": ("><❄>", "<❄><"),
    "Alpine Char": ("--<✧}>", "<{✧>--"),
    "Stonefin Sculpin": ("_<◆}>", "<{◆>_"),
    "Canyon Trout": ("--<▴>>", "<<▴>--"),
    "Arroyo Pupfish": (">{·}>", "<{·}<"),
    "Desert Sucker": ("==<○}>", "<{○>=="),
    "Dune Tilapia": ("><{☀}>", "<{☀}><"),
    "Sand Basin Gar": ("───<◇>", "<◇>───"),
    "Red Mesa Catfish": ("=><{♦}>", "<{♦}><="),
    "Canyon Chub": ("><▲>>", "<<▲><"),
    "Oasis Cichlid": ("><{◈}>", "<{◈}><"),
    "Datefin Barb": ("><♢>>", "<<♢><"),
    "Spruce Trout": ("--<♠}>", "<{♠>--"),
    "Boreal Pike": ("---<❄>>", "<<❄>---"),
    "Icewater Smelt": ("><✧>", "<✧><"),
    "Glacier Char": ("--<❆}>", "<{❆>--"),
    "Mudflat Goby": ("_<•}>", "<{•>_"),
    "Shelf Skate": ("__<◇}>>", "<<{◇>__"),
    "Archerfish": ("-<↟}>", "<{↟>-"),
    "Mangrove Snapper": ("><{♣}>", "<{♣}><"),
    "Reef Butterflyfish": ("<(☼)>", "<(☼)>"),
    "Cobalt Jack": ("--<●}>>", "<<{●>--"),
    "Grotto Tetra": ("><·◇>", "<◇·><"),
    "Limestone Loach": ("~~<□}>", "<{□>~~"),
    "Abyssal Cavefish": ("===<○>>", "<<○>==="),
}

# The standalone aquarium prototype used a broad color cycle. Keep that lively
# look in the integrated game with a stable color per species, then apply a few
# name-based art-direction overrides so recognizable fish retain the colors
# their names and markings imply. These bright foregrounds remain legible over
# all three water-depth colors.
FISH_COLOR_PALETTE: Tuple[str, ...] = (
    "\033[38;5;208;1m",  # orange
    "\033[38;5;220;1m",  # gold
    "\033[38;5;44;1m",   # teal
    "\033[38;5;141;1m",  # violet
    "\033[38;5;213;1m",  # pink
    "\033[38;5;118;1m",  # lime
    "\033[38;5;250;1m",  # silver
    "\033[38;5;203;1m",  # coral red
    "\033[38;5;75;1m",   # bright blue
    "\033[38;5;51;1m",   # cyan
)
FISH_SPECIES_COLORS: Dict[str, str] = {
    species: FISH_COLOR_PALETTE[index % len(FISH_COLOR_PALETTE)]
    for index, species in enumerate(FISH_SPRITES)
}

for _fish_name in FISH_SPRITES:
    _lower_name = _fish_name.lower()
    if any(word in _lower_name for word in ("gold", "sun", "yellow", "datefin")):
        FISH_SPECIES_COLORS[_fish_name] = FISH_COLOR_PALETTE[1]
    elif any(word in _lower_name for word in ("red", "coral", "snapper")):
        FISH_SPECIES_COLORS[_fish_name] = FISH_COLOR_PALETTE[7]
    elif any(word in _lower_name for word in ("cobalt", "blue", "deepwater", "storm")):
        FISH_SPECIES_COLORS[_fish_name] = FISH_COLOR_PALETTE[8]
    elif any(word in _lower_name for word in ("ice", "snow", "glacier", "silver", "pale", "blind")):
        FISH_SPECIES_COLORS[_fish_name] = FISH_COLOR_PALETTE[6]
    elif any(word in _lower_name for word in ("moon", "mist", "crystal", "grotto", "abyssal")):
        FISH_SPECIES_COLORS[_fish_name] = FISH_COLOR_PALETTE[3]
    elif any(word in _lower_name for word in ("fern", "reed", "bog", "meadow", "prairie")):
        FISH_SPECIES_COLORS[_fish_name] = FISH_COLOR_PALETTE[5]
    elif any(word in _lower_name for word in ("desert", "dune", "sand", "arroyo", "oasis")):
        FISH_SPECIES_COLORS[_fish_name] = FISH_COLOR_PALETTE[0]


def fish_species_color(species: str, variant: str = "Normal", lights_on: bool = True) -> str:
    """Return the shared vivid display color for a species and aquarium variant."""
    if not lights_on:
        return C.UI_MUTED
    variant = str(variant or "Normal")
    if variant == "Golden":
        return FISH_COLOR_PALETTE[1]
    if variant == "Pale":
        return FISH_COLOR_PALETTE[6]
    return FISH_SPECIES_COLORS.get(str(species), C.ACTOR_WILDLIFE)


def fish_species_sprite(species: str, direction: int = 1) -> str:
    """Return the shared right- or left-facing art for a fish species."""
    right, left = FISH_SPRITES.get(str(species), ("><>", "<><"))
    return right if int(direction) >= 0 else left


DECORATION_SPRITES: Dict[str, Sequence[str]] = {
    "Plant": ("╲│╱", " │ ", "╱│╲"),
    "Kelp": ("╲│", "│╱", "│ ", "╱ "),
    "Rock": ("▂▄▂",),
    "Driftwood": ("╱▔▔╲", "▔  ▔"),
    "Cave": ("╭──╮", "╰  ╯"),
    "Bubbler": (" ° ", "·o·", "═══"),
    "Filter": ("┌──┐", "│≈≈│", "└──┘"),
    "Glowstone": (" ✧ ", "◈◈◈"),
    "Coral Fan": ("╱╲╱╲", "╲╱╲╱"),
    "Shell Cluster": ("◠◡◠",),
    "Stone Arch": ("╭──╮", "│  │"),
    "Sand Patch": ("░░░░",),
}

# What each decoration actually does. Anything absent is purely decorative, and
# that is a deliberate option rather than an oversight.
#   "aeration"  slows how quickly the water fouls
#   "cover"     retreat target for shy fish and bottom dwellers
#   "shelter"   retreat target for cave-seeking (hiding) species
#   "breeding"  improves the chance a pair spawns
#   "light"     fish keep normal behaviour while the lights are off
DECORATION_EFFECTS: Dict[str, Dict[str, object]] = {
    "Bubbler": {"aeration": 1},
    "Filter": {"aeration": 2},
    "Plant": {"cover": True, "breeding": 1},
    "Kelp": {"cover": True, "breeding": 1},
    "Rock": {"cover": True},
    "Driftwood": {"cover": True, "shelter": True},
    "Cave": {"shelter": True},
    "Glowstone": {"light": True},
}


def decoration_effect_total(state: Dict[str, object], effect: str) -> int:
    """Summed strength of one effect across every placed decoration."""
    total = 0
    for decoration in state.get("decorations", []) or []:
        if not isinstance(decoration, dict):
            continue
        value = DECORATION_EFFECTS.get(str(decoration.get("kind", "")), {}).get(effect, 0)
        total += int(value) if not isinstance(value, bool) else int(bool(value))
    return total


def decorations_with_effect(state: Dict[str, object], effect: str) -> List[Dict[str, object]]:
    """Placed decorations providing one effect, for movement targets."""
    return [
        decoration
        for decoration in state.get("decorations", []) or []
        if isinstance(decoration, dict)
        and DECORATION_EFFECTS.get(str(decoration.get("kind", "")), {}).get(effect)
    ]


PERSONALITIES = (
    "calm", "curious", "sleepy", "social", "shy", "nocturnal", "playful",
)

SCHOOLING_SPECIES = {
    "Pond Minnow", "Blind Minnow", "Tide Sardine", "Mackerel", "Coral Dart",
    "Mosquitofish", "Golden Shiner", "Rainbow Smelt", "Dace", "Anchovy",
    "Meadow Darter", "Deepwater Cisco", "Prairie Shiner", "Reed Killifish",
    "Snowmelt Dace", "Icewater Smelt", "Grotto Tetra",
}
BOTTOM_SPECIES = {
    "Catfish", "Carp", "Cave Carp", "River Chub", "Reef Grouper",
    "Mud Loach", "Lake Sturgeon", "Halibut",
    "Golden Tench", "Silver Burbot", "Timber Catfish", "Plains Paddlefish",
    "Bog Lamprey", "River Buffalo", "Stonefin Sculpin", "Desert Sucker",
    "Red Mesa Catfish", "Mudflat Goby", "Shelf Skate", "Limestone Loach",
    "Abyssal Cavefish",
}
HIDING_SPECIES = {
    "Night Eel", "Crystal Eel", "Moon Eel", "Lantern Angelfish",
    "Walleye",
    "Mist Eel", "Bog Lamprey",
}
FAST_SPECIES = {
    "Trout", "Brook Trout", "Rain Pike", "Silver Salmon", "Sunfin Tuna",
    "Muskellunge", "Smallmouth Bass", "Rainbow Trout", "Longnose Gar",
    "Steelhead", "Swordfish", "Blue Marlin",
    "Birchstream Trout", "Pinewater Char", "Heather Grayling", "Peat Pike",
    "Alpine Char", "Canyon Trout", "Sand Basin Gar", "Spruce Trout",
    "Boreal Pike", "Glacier Char", "Mangrove Snapper", "Cobalt Jack",
}


def aquarium_day_number(year: int, month: int, day: int) -> int:
    """Return a stable monotonic approximation used only for aquarium elapsed days."""
    return max(0, int(year) - 1) * 372 + max(0, int(month) - 1) * 31 + max(1, int(day))


def species_habitat(species: str, fish_data: Dict[str, Dict[str, object]]) -> str:
    record = fish_data.get(str(species), {})
    habitats = {str(v) for v in record.get("habitats", []) or []}
    if habitats == {"Ocean"}:
        return "Saltwater"
    if habitats == {"Underground"}:
        return "Underground"
    locations = set(str(v) for v in record.get("locations", []))
    if "Coast" in locations and not locations.intersection({"Farm", "Wilderness", "Mine"}):
        return "Saltwater"
    if "Mine" in locations and not locations.intersection({"Farm", "Wilderness", "Coast"}):
        return "Underground"
    return "Freshwater"


def species_lifespan_days(species: str, seed: int) -> int:
    low_years, high_years = AQUARIUM_LIFESPAN_YEARS.get(str(species), (5, 12))
    identity = sum((index + 1) * ord(ch) for index, ch in enumerate(str(species)))
    rng = random.Random(int(seed) ^ identity ^ 0xA91F)
    return rng.randint(int(low_years) * 365, int(high_years) * 365)


def fish_stage(age_days: int, lifespan_days: int = 0) -> str:
    if int(age_days) < 3:
        return "Fry"
    if int(age_days) < 12:
        return "Young"
    if int(lifespan_days) > 0 and int(age_days) >= int(lifespan_days) * 4 // 5:
        return "Elder"
    return "Adult"


def fish_behavior_label(species: str, personality: str) -> str:
    if species in SCHOOLING_SPECIES:
        return "schooling"
    if species in BOTTOM_SPECIES:
        return "bottom-dwelling"
    if species in HIDING_SPECIES:
        return "cave-seeking"
    if species in FAST_SPECIES:
        return "swift"
    return str(personality or "calm")


def aquarium_capacity(furniture_name: str, comfort: int = 4) -> int:
    lowered = str(furniture_name).lower()
    if any(word in lowered for word in ("grand", "large", "wall")):
        return 12
    if any(word in lowered for word in ("small", "tabletop")):
        return 4
    return max(6, min(10, 6 + max(0, int(comfort) - 4) // 2))


def _clean_individual(raw: object, valid_species: set, index: int) -> Optional[Dict[str, object]]:
    if not isinstance(raw, dict):
        return None
    species = str(raw.get("species", ""))
    if species not in valid_species or species == "Old Boot":
        return None
    fish_id = str(raw.get("id", "")).strip() or f"fish-{index + 1}"
    lifespan = max(0, int(raw.get("lifespan_days", 0) or 0))
    if lifespan <= 0:
        lifespan = species_lifespan_days(species, sum((i + 11) * ord(ch) for i, ch in enumerate(fish_id)))
    return {
        "id": fish_id,
        "species": species,
        "name": str(raw.get("name", "")).strip()[:24] or species,
        "variant": str(raw.get("variant", "Normal")) if str(raw.get("variant", "Normal")) in AQUARIUM_VARIANTS else "Normal",
        "personality": str(raw.get("personality", "calm")) if str(raw.get("personality", "calm")) in PERSONALITIES else "calm",
        "age_days": max(0, int(raw.get("age_days", 12) or 0)),
        "lifespan_days": lifespan,
        "elder_announced": bool(raw.get("elder_announced", False)),
        "generation": max(0, int(raw.get("generation", 0) or 0)),
        "parents": [str(v) for v in raw.get("parents", []) if str(v).strip()][:2] if isinstance(raw.get("parents"), list) else [],
        "x": max(2, int(raw.get("x", 4 + index * 5) or 2)),
        "y": max(2, int(raw.get("y", 4 + index % 5) or 2)),
        "direction": -1 if int(raw.get("direction", 1) or 1) < 0 else 1,
        "phase": max(0, int(raw.get("phase", index * 7) or 0)),
    }


def _aggregate_fish(individuals: Iterable[Dict[str, object]]) -> Dict[str, int]:
    counts = Counter(str(fish.get("species", "")) for fish in individuals if str(fish.get("species", "")))
    return {species: int(count) for species, count in sorted(counts.items()) if count > 0}


def _new_fish(
    state: Dict[str, object], species: str, seed: int, *, age_days: int = 12,
    variant: str = "Normal", parents: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    next_id = max(1, int(state.get("next_fish_id", 1) or 1))
    state["next_fish_id"] = next_id + 1
    rng = random.Random(int(seed) ^ (next_id * 104729) ^ sum(ord(ch) for ch in species))
    existing = sum(1 for fish in state.get("individuals", []) if fish.get("species") == species)
    return {
        "id": f"fish-{next_id}",
        "species": str(species),
        "name": str(species) if existing == 0 else f"{species} {existing + 1}",
        "variant": variant if variant in AQUARIUM_VARIANTS else "Normal",
        "personality": rng.choice(PERSONALITIES),
        "age_days": max(0, int(age_days)),
        "lifespan_days": species_lifespan_days(species, int(seed) ^ next_id),
        "elder_announced": False,
        "generation": 0,
        "parents": [str(v) for v in (parents or []) if str(v).strip()][:2],
        "x": rng.randint(5, 55),
        "y": rng.randint(3, 13),
        "direction": rng.choice((-1, 1)),
        "phase": rng.randint(0, 1000),
    }


def normalize_aquarium_state(
    record: Dict[str, object], fish_data: Dict[str, Dict[str, object]],
    day_key: str, day_number: int, seed: int, *, mortality_enabled: bool = True,
) -> Dict[str, object]:
    """Normalize state and migrate legacy ``record['fish']`` species counts."""
    valid_species = set(str(name) for name in fish_data)
    raw_state = record.get("aquarium")
    state = dict(raw_state) if isinstance(raw_state, dict) else {}
    raw_individuals = state.get("individuals", [])
    individuals = []
    if isinstance(raw_individuals, list):
        for index, raw in enumerate(raw_individuals):
            fish = _clean_individual(raw, valid_species, index)
            if fish:
                individuals.append(fish)

    legacy_counts = record.get("fish", {})
    clean_legacy = {
        str(species): max(0, int(quantity or 0))
        for species, quantity in dict(legacy_counts or {}).items()
        if str(species) in valid_species and str(species) != "Old Boot" and int(quantity or 0) > 0
    } if isinstance(legacy_counts, dict) else {}
    current_counts = _aggregate_fish(individuals)
    # External legacy code and old saves are authoritative when the aggregate
    # differs.  Rebuild individuals without silently losing stocked fish.
    if "fish" in record and clean_legacy != current_counts:
        rebuilt: List[Dict[str, object]] = []
        state["individuals"] = rebuilt
        state["next_fish_id"] = 1
        for species, quantity in sorted(clean_legacy.items()):
            for offset in range(quantity):
                rebuilt.append(_new_fish(state, species, seed + len(rebuilt), age_days=12 + offset))
        individuals = rebuilt

    habitat = str(state.get("habitat", ""))
    if habitat not in AQUARIUM_HABITATS:
        habitats = {species_habitat(str(f.get("species", "")), fish_data) for f in individuals}
        habitat = next(iter(habitats)) if len(habitats) == 1 else "Freshwater"

    decorations = []
    for raw in state.get("decorations", []) if isinstance(state.get("decorations"), list) else []:
        if not isinstance(raw, dict) or str(raw.get("kind", "")) not in DECORATION_SPRITES:
            continue
        decorations.append({
            "kind": str(raw.get("kind")),
            "x": max(2, int(raw.get("x", 8) or 2)),
            "y": max(2, int(raw.get("y", 10) or 2)),
        })
    if not decorations:
        decorations = [
            {"kind": "Plant", "x": 8, "y": 11},
            {"kind": "Rock", "x": 28, "y": 14},
        ]

    state.update({
        "version": AQUARIUM_SCHEMA_VERSION,
        "tank_id": str(
            state.get("tank_id", record.get("aquarium_id", "")) or ""
        )[:160],
        "display_name": str(
            state.get(
                "display_name",
                record.get("aquarium_display_name", record.get("name", "Aquarium")),
            )
            or "Aquarium"
        )[:32],
        "habitat": habitat,
        "individuals": individuals,
        "decorations": decorations[:16],
        "condition": max(0, min(2, int(state.get("condition", 2) or 0))),
        "lights_on": bool(state.get("lights_on", True)),
        "last_sync_day": max(0, int(state.get("last_sync_day", day_number) or day_number)),
        "last_fed_day": str(state.get("last_fed_day", record.get("fed_day", ""))),
        "last_cleaned_day": str(state.get("last_cleaned_day", "")),
        "last_fed_ordinal": max(0, int(state.get("last_fed_ordinal", day_number - 1) or 0)),
        "last_cleaned_ordinal": max(0, int(state.get("last_cleaned_ordinal", day_number) or 0)),
        # Keep the legacy mirror authoritative when older code or a migrated
        # save explicitly supplies it.  Native actions synchronize both fields.
        "feedings": max(0, int(record.get("feedings", state.get("feedings", 0)) or 0)),
        "next_fish_id": max(1, int(state.get("next_fish_id", len(individuals) + 1) or 1)),
        "events": [str(v)[:90] for v in state.get("events", [])[-8:]] if isinstance(state.get("events"), list) else [],
        "notices": [str(v)[:120] for v in state.get("notices", [])[-8:]] if isinstance(state.get("notices"), list) else [],
        "memorials": [
            dict(v) for v in state.get("memorials", [])[-40:] if isinstance(v, dict)
        ] if isinstance(state.get("memorials"), list) else [],
        "last_household_care_ordinal": max(0, int(state.get("last_household_care_ordinal", 0) or 0)),
        "known_species": sorted({
            str(v) for v in state.get("known_species", []) if str(v).strip()
        } | {
            str(fish.get("species", "")) for fish in individuals
            if str(fish.get("species", "")).strip()
        } | {
            str(memorial.get("species", ""))
            for memorial in state.get("memorials", []) if isinstance(memorial, dict)
            and str(memorial.get("species", "")).strip()
        }),
        "known_variants": sorted({
            str(v) for v in state.get("known_variants", []) if str(v).strip()
        } | {
            str(fish.get("variant", "Normal")) for fish in individuals
            if str(fish.get("variant", "Normal")).strip()
        } | {
            str(memorial.get("variant", "Normal"))
            for memorial in state.get("memorials", []) if isinstance(memorial, dict)
            and str(memorial.get("variant", "Normal")).strip()
        }),
    })
    record["aquarium_id"] = str(state.get("tank_id", ""))
    record["aquarium_display_name"] = str(state.get("display_name", "Aquarium"))
    record["aquarium"] = state
    sync_aquarium_legacy_fields(record)
    advance_aquarium_days(
        record, fish_data, day_key, day_number, seed,
        mortality_enabled=mortality_enabled,
    )
    return state


def sync_aquarium_legacy_fields(record: Dict[str, object]) -> None:
    state = record.get("aquarium", {})
    if not isinstance(state, dict):
        return
    record["fish"] = _aggregate_fish(state.get("individuals", []))
    record["feedings"] = max(0, int(state.get("feedings", 0) or 0))
    if state.get("last_fed_day"):
        record["fed_day"] = str(state.get("last_fed_day"))
    if state.get("tank_id"):
        record["aquarium_id"] = str(state.get("tank_id"))
    if state.get("display_name"):
        record["aquarium_display_name"] = str(state.get("display_name"))
    known_species = {
        str(v) for v in state.get("known_species", []) if str(v).strip()
    }
    known_variants = {
        str(v) for v in state.get("known_variants", []) if str(v).strip()
    }
    for fish in state.get("individuals", []):
        if str(fish.get("species", "")).strip():
            known_species.add(str(fish.get("species")))
        if str(fish.get("variant", "Normal")).strip():
            known_variants.add(str(fish.get("variant", "Normal")))
    for memorial in state.get("memorials", []):
        if not isinstance(memorial, dict):
            continue
        if str(memorial.get("species", "")).strip():
            known_species.add(str(memorial.get("species")))
        if str(memorial.get("variant", "Normal")).strip():
            known_variants.add(str(memorial.get("variant", "Normal")))
    state["known_species"] = sorted(known_species)
    state["known_variants"] = sorted(known_variants)


def _log_event(state: Dict[str, object], message: str) -> None:
    events = state.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        state["events"] = events
    message = str(message)[:90]
    if not events or events[-1] != message:
        events.append(message)
    del events[:-8]


def advance_aquarium_days(
    record: Dict[str, object], fish_data: Dict[str, Dict[str, object]],
    day_key: str, day_number: int, seed: int, *, mortality_enabled: bool = True,
) -> List[str]:
    state = record.get("aquarium")
    if not isinstance(state, dict):
        return []
    previous = max(0, int(state.get("last_sync_day", day_number) or day_number))
    elapsed = max(0, min(36500, int(day_number) - previous))
    if elapsed <= 0:
        return []
    messages: List[str] = []
    survivors: List[Dict[str, object]] = []
    for fish in state.get("individuals", []):
        old_age = max(0, int(fish.get("age_days", 0) or 0))
        new_age = old_age + elapsed
        lifespan = max(365, int(fish.get("lifespan_days", 0) or 0))
        fish["age_days"] = new_age
        elder_age = lifespan * 4 // 5
        fish_name = str(fish.get("name", fish.get("species", "A fish")))
        if mortality_enabled and new_age >= lifespan:
            memorial = {
                "name": fish_name,
                "species": str(fish.get("species", "Fish")),
                "variant": str(fish.get("variant", "Normal")),
                "age_days": new_age,
                "day_number": int(day_number),
                "parents": list(fish.get("parents", []))[:2],
            }
            state.setdefault("memorials", []).append(memorial)
            del state["memorials"][:-40]
            message = f"{fish_name} reached the end of a long life in the aquarium."
            _log_event(state, message)
            messages.append(message)
            continue
        if old_age < elder_age <= new_age and not bool(fish.get("elder_announced", False)):
            fish["elder_announced"] = True
            message = f"{fish_name} has grown into an elder fish."
            _log_event(state, message)
            messages.append(message)
        survivors.append(fish)
    state["individuals"] = survivors
    # A crowded tank fouls faster than a sparse one, and aeration slows it down.
    # Effective days are scaled rather than the thresholds so a filtered, lightly
    # stocked tank is genuinely low maintenance.
    since_cleaning = max(0, int(day_number) - int(state.get("last_cleaned_ordinal", previous) or previous))
    capacity = max(1, int(record.get("aquarium_capacity", 0) or 0) or max(1, len(survivors)))
    density = len(survivors) / float(capacity)
    load = 1.0 + max(0.0, density - 0.5)
    load /= 1.0 + 0.35 * max(0, decoration_effect_total(state, "aeration"))
    effective_days = since_cleaning * max(0.35, load)
    state["condition"] = 2 if effective_days <= 2 else 1 if effective_days <= 6 else 0
    state["last_sync_day"] = int(day_number)
    if elapsed > 1:
        _log_event(state, f"The aquarium changed quietly over {elapsed} days.")
    if messages:
        notices = state.setdefault("notices", [])
        notices.extend(messages)
        del notices[:-8]
    sync_aquarium_legacy_fields(record)
    return messages


def apply_household_aquarium_care(
    record: Dict[str, object], fish_data: Dict[str, Dict[str, object]],
    day_key: str, day_number: int, seed: int,
    caretakers: Sequence[Dict[str, object]], capacity: int,
) -> List[str]:
    """Let one available household member safely tend a tank once per day."""
    state = record.get("aquarium")
    if not isinstance(state, dict) or not state.get("individuals") or not caretakers:
        return []
    if int(state.get("last_household_care_ordinal", 0) or 0) >= int(day_number):
        return []
    state["last_household_care_ordinal"] = int(day_number)

    eligible = [dict(person) for person in caretakers if str(person.get("name", "")).strip()]
    if not eligible:
        return []
    assigned = [person for person in eligible if bool(person.get("assigned", False))]
    rng = random.Random(int(seed) ^ (int(day_number) * 32452843) ^ len(eligible) * 49999)
    care_chance = 1.0 if assigned else min(0.82, 0.38 + 0.16 * len(eligible))
    if rng.random() >= care_chance:
        return []
    caretaker = dict(rng.choice(assigned or eligible))
    name = str(caretaker.get("name", "A family member"))

    if int(state.get("condition", 2) or 0) < 2 and bool(caretaker.get("can_clean", False)):
        state["condition"] = 2
        state["last_cleaned_day"] = str(day_key)
        state["last_cleaned_ordinal"] = int(day_number)
        tank_name = str(state.get("display_name", "the aquarium") or "the aquarium")
        message = f"{name} cleaned {tank_name} before starting the day."
    elif int(state.get("last_fed_ordinal", 0) or 0) < int(day_number):
        state["last_fed_day"] = str(day_key)
        state["last_fed_ordinal"] = int(day_number)
        state["feedings"] = max(0, int(state.get("feedings", 0) or 0)) + 1
        baby = None
        if int(state["feedings"]) % 4 == 0:
            baby = breed_aquarium_fish(record, fish_data, capacity, int(seed) + int(day_number))
        tank_name = str(state.get("display_name", "the aquarium") or "the aquarium")
        message = f"{name} fed {tank_name} before starting the day."
        if baby:
            message += f" A new {baby.get('species', 'fish')} fry appeared."
    else:
        tank_name = str(state.get("display_name", "the aquarium") or "the aquarium")
        message = f"{name} checked {tank_name}'s light and filter."

    _log_event(state, message)
    sync_aquarium_legacy_fields(record)
    return [message]


def can_stock_species(
    state: Dict[str, object], species: str, fish_data: Dict[str, Dict[str, object]], capacity: int,
) -> Tuple[bool, str]:
    if len(state.get("individuals", [])) >= max(1, int(capacity)):
        return False, "The aquarium is at capacity."
    habitat = species_habitat(species, fish_data)
    if habitat != state.get("habitat", "Freshwater"):
        return False, f"{species} requires a {habitat.lower()} aquarium."
    return True, ""


def add_aquarium_fish(
    record: Dict[str, object], species: str, fish_data: Dict[str, Dict[str, object]],
    capacity: int, seed: int,
) -> Tuple[bool, str, Optional[Dict[str, object]]]:
    state = record.get("aquarium", {})
    allowed, reason = can_stock_species(state, species, fish_data, capacity)
    if not allowed:
        return False, reason, None
    fish = _new_fish(state, species, seed)
    state.setdefault("individuals", []).append(fish)
    _log_event(state, f"{fish['name']} joined the aquarium.")
    sync_aquarium_legacy_fields(record)
    return True, f"Added {species} to the aquarium.", fish


def remove_aquarium_fish(record: Dict[str, object], fish_id: str) -> Optional[Dict[str, object]]:
    state = record.get("aquarium", {})
    individuals = state.get("individuals", []) if isinstance(state, dict) else []
    for fish in list(individuals):
        if str(fish.get("id")) == str(fish_id):
            individuals.remove(fish)
            _log_event(state, f"{fish.get('name', fish.get('species', 'A fish'))} left the aquarium.")
            sync_aquarium_legacy_fields(record)
            return fish
    return None


def rename_aquarium_fish(record: Dict[str, object], fish_id: str, name: str) -> bool:
    state = record.get("aquarium", {})
    for fish in state.get("individuals", []) if isinstance(state, dict) else []:
        if str(fish.get("id")) == str(fish_id):
            old = str(fish.get("name", fish.get("species", "Fish")))
            fish["name"] = str(name).strip()[:24] or old
            _log_event(state, f"{old} is now named {fish['name']}.")
            return True
    return False


def transfer_aquarium_fish(
    source_record: Dict[str, object], target_record: Dict[str, object], fish_id: str,
    fish_data: Dict[str, Dict[str, object]], target_capacity: int, seed: int,
) -> Tuple[bool, str, Optional[Dict[str, object]]]:
    """Move one living fish between tanks without erasing its history."""
    source = source_record.get("aquarium", {})
    target = target_record.get("aquarium", {})
    if not isinstance(source, dict) or not isinstance(target, dict):
        return False, "Both aquariums must be prepared before moving a fish.", None
    fish = next(
        (
            entry for entry in source.get("individuals", [])
            if str(entry.get("id", "")) == str(fish_id)
        ),
        None,
    )
    if not isinstance(fish, dict):
        return False, "That fish is no longer in the source aquarium.", None
    species = str(fish.get("species", ""))
    allowed, reason = can_stock_species(target, species, fish_data, target_capacity)
    if not allowed:
        return False, reason, None

    source_individuals = source.setdefault("individuals", [])
    target_individuals = target.setdefault("individuals", [])
    source_individuals.remove(fish)

    used_ids = {str(entry.get("id", "")) for entry in target_individuals}
    if str(fish.get("id", "")) in used_ids:
        next_id = max(1, int(target.get("next_fish_id", 1) or 1))
        while f"fish-{next_id}" in used_ids:
            next_id += 1
        fish["id"] = f"fish-{next_id}"
        target["next_fish_id"] = next_id + 1
    rng = random.Random(int(seed) ^ len(target_individuals) * 65537)
    fish["x"] = rng.randint(5, 55)
    fish["y"] = rng.randint(3, 13)
    fish["direction"] = rng.choice((-1, 1))
    fish["phase"] = rng.randint(0, 1000)
    target_individuals.append(fish)

    fish_name = str(fish.get("name", species or "The fish"))
    source_name = str(source.get("display_name", "the source aquarium"))
    target_name = str(target.get("display_name", "the destination aquarium"))
    _log_event(source, f"{fish_name} moved from {source_name} to {target_name}.")
    _log_event(target, f"{fish_name} arrived from {source_name}.")
    sync_aquarium_legacy_fields(source_record)
    sync_aquarium_legacy_fields(target_record)
    return True, f"Moved {fish_name} from {source_name} to {target_name}.", fish


def breed_aquarium_fish(
    record: Dict[str, object], fish_data: Dict[str, Dict[str, object]], capacity: int, seed: int,
) -> Optional[Dict[str, object]]:
    state = record.get("aquarium", {})
    if not isinstance(state, dict) or int(state.get("condition", 0)) <= 0:
        return None
    individuals = state.get("individuals", [])
    if len(individuals) >= capacity:
        return None
    adults_by_species: Dict[str, List[Dict[str, object]]] = {}
    for fish in individuals:
        if fish_stage(
            int(fish.get("age_days", 0)), int(fish.get("lifespan_days", 0))
        ) == "Adult":
            adults_by_species.setdefault(str(fish.get("species", "")), []).append(fish)
    candidates = [(species, fish) for species, fish in adults_by_species.items() if len(fish) >= 2]
    if not candidates:
        return None
    rng = random.Random(int(seed) ^ int(state.get("feedings", 0)) * 65537)
    species, parents = rng.choice(candidates)
    mother, father = parents[0], parents[1]
    mother_variant = str(mother.get("variant", "Normal"))
    father_variant = str(father.get("variant", "Normal"))
    roll = rng.random()
    # Offspring take after their parents, so a line bred toward a rare variant
    # keeps it instead of rerolling from scratch every spawn. Mutation still
    # allows a rare colour to appear (or disappear) on its own.
    if roll < 0.08:
        variant = "Golden" if rng.random() < 0.25 else rng.choice(("Pale", "Speckled", "Normal"))
    elif mother_variant == father_variant:
        variant = mother_variant
    else:
        variant = mother_variant if rng.random() < 0.5 else father_variant
    if variant not in AQUARIUM_VARIANTS:
        variant = "Normal"
    baby = _new_fish(
        state, species, seed + 73, age_days=0, variant=variant,
        parents=[str(mother.get("id")), str(father.get("id"))],
    )
    baby["generation"] = 1 + max(
        int(mother.get("generation", 0) or 0), int(father.get("generation", 0) or 0),
    )
    state.setdefault("individuals", []).append(baby)
    variant_text = "" if variant == "Normal" else f" {variant.lower()}"
    _log_event(state, f"A{variant_text} {species} fry appeared in the plants.")
    sync_aquarium_legacy_fields(record)
    return baby


@dataclass
class AquariumResult:
    action: str = "exit"
    fish_id: str = ""
    changed: bool = False
    minutes: int = 0
    message: str = ""


class StableAquariumWriter:
    """Line-diff terminal writer: no per-frame clears and no per-line prints."""

    def __init__(self) -> None:
        self.previous: List[str] = []
        self.prepared = False

    def draw(self, lines: Sequence[str]) -> None:
        clean = [str(line) for line in lines]
        writes: List[str] = []
        if not self.prepared:
            writes.append("\033[?25l\033[H\033[J")
            self.prepared = True
        elif self.previous and len(clean) != len(self.previous):
            # A terminal-height change is rare and deserves one clean rebuild;
            # addressing rows that disappeared could otherwise make the
            # terminal scroll and reintroduce visible flicker.
            writes.append("\033[H\033[J")
            self.previous = []
        maximum = max(len(clean), len(self.previous))
        for index in range(maximum):
            line = clean[index] if index < len(clean) else ""
            old = self.previous[index] if index < len(self.previous) else None
            if line != old:
                writes.append(f"\033[{index + 1};1H\033[2K{line}")
        if writes:
            sys.stdout.write("".join(writes))
            sys.stdout.flush()
        self.previous = clean

    def finish(self) -> None:
        if self.prepared:
            try:
                sys.stdout.write("\033[?25h")
                sys.stdout.flush()
            except Exception:
                pass


class AquariumViewer:
    """Interactive native aquarium screen operating directly on furniture state."""

    def __init__(
        self, name: str, record: Dict[str, object], fish_data: Dict[str, Dict[str, object]],
        day_key: str, day_number: int, capacity: int, seed: int,
    ) -> None:
        self.name = str(name)
        self.record = record
        self.state = record["aquarium"]
        self.fish_data = fish_data
        self.day_key = str(day_key)
        self.day_number = int(day_number)
        self.capacity = max(1, int(capacity))
        self.seed = int(seed)
        self.tick = 0
        self.mode = "watch"
        self.cursor_x = 12
        self.cursor_y = 6
        self.selected_index = 0
        self.memorial_index = 0
        self.decor_index = 0
        self.food_left = 0
        self.food: List[Dict[str, int]] = []
        self.algae: List[Tuple[int, int]] = []
        events = self.state.get("events", [])
        self.message = str(events[-1]) if isinstance(events, list) and events else "The aquarium hums quietly."
        self.changed = False
        self.minutes = 0
        self.writer = StableAquariumWriter()
        self.tank_width = 64
        self.tank_height = 18

    @property
    def individuals(self) -> List[Dict[str, object]]:
        return self.state.setdefault("individuals", [])

    def selected_fish(self) -> Optional[Dict[str, object]]:
        if not self.individuals:
            self.selected_index = 0
            return None
        self.selected_index %= len(self.individuals)
        return self.individuals[self.selected_index]

    def _configure_dimensions(self) -> None:
        terminal = shutil.get_terminal_size((112, 34))
        side = 34 if terminal.columns >= 90 else 0
        reserved_rows = 3 if side else 8
        self.tank_width = max(34, min(78, terminal.columns - side - 3))
        self.tank_height = max(10, min(24, terminal.lines - reserved_rows))
        self.cursor_x = max(2, min(self.tank_width - 3, self.cursor_x))
        self.cursor_y = max(2, min(self.tank_height - 3, self.cursor_y))

    def _condition_label(self) -> str:
        return ("Dirty", "Cloudy", "Clean")[max(0, min(2, int(self.state.get("condition", 2))))]

    def _fish_sprite(self, fish: Dict[str, object]) -> str:
        sprite = fish_species_sprite(
            str(fish.get("species", "")), int(fish.get("direction", 1)),
        )
        variant = str(fish.get("variant", "Normal"))
        if variant == "Speckled" and len(sprite) > 3:
            middle = len(sprite) // 2
            sprite = sprite[:middle] + "·" + sprite[middle + 1:]
        elif variant == "Golden":
            sprite = sprite.replace("°", "★", 1)
        elif variant == "Pale":
            sprite = sprite.replace("°", "○", 1)
        return sprite

    def _fish_color(self, fish: Dict[str, object]) -> str:
        return fish_species_color(
            str(fish.get("species", "")),
            str(fish.get("variant", "Normal")),
            bool(self.state.get("lights_on", True)),
        )

    @staticmethod
    def _put(grid, colors, x: int, y: int, text: str, role: str) -> None:
        if not (0 <= y < len(grid)):
            return
        for offset, ch in enumerate(str(text)):
            draw_x = int(x) + offset
            if 0 <= draw_x < len(grid[y]):
                grid[y][draw_x] = ch
                colors[y][draw_x] = role

    def _tank_lines(self) -> List[str]:
        width, height = self.tank_width, self.tank_height
        grid = [[" " for _ in range(width)] for _ in range(height)]
        colors = [[C.WATER for _ in range(width)] for _ in range(height)]
        border = C.UI_BORDER
        self._put(grid, colors, 0, 0, "+" + "-" * (width - 2) + "+", border)
        self._put(grid, colors, 0, height - 1, "+" + "-" * (width - 2) + "+", border)
        for y in range(1, height - 1):
            self._put(grid, colors, 0, y, "|", border)
            self._put(grid, colors, width - 1, y, "|", border)
        title = f" {self.name} · {self.state.get('habitat', 'Freshwater')} · {self._condition_label()} "
        self._put(grid, colors, 2, 0, title[: width - 4], C.UI_TITLE)

        # Stable water: phase shifts a short wave instead of randomizing the
        # entire background on every frame.
        wave = "~  ~   ~ "
        offset = (self.tick // 3) % len(wave)
        for x in range(2, width - 2):
            ch = wave[(x + offset) % len(wave)]
            if ch != " ":
                self._put(grid, colors, x, 1, ch, C.WATER)
        if not bool(self.state.get("lights_on", True)):
            for y in range(2, height - 2, 3):
                for x in range(3, width - 3, 8):
                    self._put(grid, colors, x, y, "·", C.UI_MUTED)

        floor_y = height - 2
        self._put(grid, colors, 1, floor_y, "·" * (width - 2), C.FLOOR_SHADOW)
        for decoration in self.state.get("decorations", []):
            kind = str(decoration.get("kind", "Rock"))
            sprite = DECORATION_SPRITES.get(kind, DECORATION_SPRITES["Rock"])
            base_x = max(2, min(width - max(len(row) for row in sprite) - 1, int(decoration.get("x", 5))))
            base_y = max(2, min(floor_y - len(sprite), int(decoration.get("y", floor_y - len(sprite)))))
            role = C.CROP_SPROUT if kind == "Plant" else C.WATER if kind == "Bubbler" else C.STONE
            for row_index, row in enumerate(sprite):
                self._put(grid, colors, base_x, base_y + row_index, row, role)
            decoration["x"], decoration["y"] = base_x, base_y

        for x, y in self.algae:
            self._put(grid, colors, x, y, "░", C.FUNGAL)
        for pellet in self.food:
            self._put(grid, colors, pellet["x"], pellet["y"], "·", C.UI_SELECTED)

        for fish in self.individuals:
            sprite = self._fish_sprite(fish)
            x = max(2, min(width - len(sprite) - 2, int(fish.get("x", 4))))
            y = max(2, min(height - 3, int(fish.get("y", 4))))
            fish["x"], fish["y"] = x, y
            self._put(grid, colors, x, y, sprite, self._fish_color(fish))

        if self.mode in {"feed", "clean", "decorate"}:
            marker = "×" if self.mode == "feed" else "□" if self.mode == "clean" else "+"
            self._put(grid, colors, self.cursor_x, self.cursor_y, marker, C.PLACEMENT)
            if self.mode == "decorate":
                kind = tuple(DECORATION_SPRITES)[self.decor_index % len(DECORATION_SPRITES)]
                self._put(grid, colors, max(2, self.cursor_x - 1), max(2, self.cursor_y - 1), kind[:3], C.UI_SELECTED)

        enabled = get_color_enabled()
        lines: List[str] = []
        for y in range(height):
            if not enabled:
                lines.append("".join(grid[y]))
                continue
            parts: List[str] = []
            start = 0
            while start < width:
                role = colors[y][start]
                end = start + 1
                while end < width and colors[y][end] == role:
                    end += 1
                parts.append(colorize("".join(grid[y][start:end]), role))
                start = end
            lines.append("".join(parts))
        return lines

    def _panel_lines(self, height: int, width: int = 34) -> List[str]:
        inner = width - 2
        selected = self.selected_fish()
        fed = str(self.state.get("last_fed_day", "")) == self.day_key
        message_lines = [f" {line}" for line in _wrap_text(self.message, inner - 1)] or [""]
        rows = [
            " AQUARIUM",
            f" Fish: {len(self.individuals)}/{self.capacity}",
            f" Habitat: {self.state.get('habitat', 'Freshwater')}",
            f" Condition: {self._condition_label()}",
            f" Fed today: {'yes' if fed else 'no'}",
            f" Lights: {'on' if self.state.get('lights_on', True) else 'off'}",
            f" Remembered fish: {len(self.state.get('memorials', []))}",
            "",
            *message_lines,
            "",
        ]
        if selected:
            age_days = max(0, int(selected.get("age_days", 0) or 0))
            lifespan = max(0, int(selected.get("lifespan_days", 0) or 0))
            age_text = f"{age_days // 365}y {age_days % 365}d" if age_days >= 365 else f"{age_days}d"
            rows.extend([
                f" {selected.get('name', 'Fish')}",
                f" {selected.get('variant', 'Normal')} {selected.get('species', 'fish')}",
                f" {fish_stage(age_days, lifespan)} · age {age_text}",
                f" {fish_behavior_label(str(selected.get('species', '')), str(selected.get('personality', 'calm')))}",
            ])
        else:
            rows.extend([" No fish stocked.", " Catch a compatible fish", " and press S to add it."])
        rows.extend([
            "", " [ / ] select fish", " F feed · C clean", " D decorate · L lights",
            " H habitat (empty tank)", " S stock · R remove · N fish",
            " T transfer · K tank name", " V collection · A caretaker",
            " M recall memorials", " B/X/Esc/Q/Tab return",
        ])
        result = ["+" + "-" * inner + "+"]
        for row in rows[: max(0, height - 2)]:
            plain = str(row)[:inner]
            result.append("|" + plain.ljust(inner) + "|")
        while len(result) < height - 1:
            result.append("|" + " " * inner + "|")
        result.append("+" + "-" * inner + "+")
        return result[:height]

    def render_lines(self) -> List[str]:
        tank = self._tank_lines()
        terminal = shutil.get_terminal_size((112, 34))
        if terminal.columns >= self.tank_width + 37:
            panel = self._panel_lines(len(tank), 34)
            return [tank[i] + "  " + panel[i] for i in range(len(tank))]
        width = self.tank_width
        inner = max(8, width - 2)
        selected = self.selected_fish()
        selected_text = (
            f"{selected.get('name', 'Fish')} · {selected.get('variant', 'Normal')} {selected.get('species', 'fish')}"
            if selected else "No fish stocked"
        )
        message_lines = _wrap_text(self.message, inner - 1) or [""]
        compact = [
            "+" + "-" * inner + "+",
            "|" + f" {selected_text}"[:inner].ljust(inner) + "|",
            "|" + f" Fish {len(self.individuals)}/{self.capacity} · {self._condition_label()} · lights {'on' if self.state.get('lights_on', True) else 'off'}"[:inner].ljust(inner) + "|",
            "|" + " [/] fish · F feed · C clean · D decorate · L light"[:inner].ljust(inner) + "|",
            "|" + " S stock · R remove · N fish · T transfer"[:inner].ljust(inner) + "|",
            "|" + " K tank name · V collection · A caretaker · B back"[:inner].ljust(inner) + "|",
            *(f"|{' ' + line:<{inner}}|" for line in message_lines),
            "+" + "-" * inner + "+",
        ]
        return tank + compact

    def _move_cursor(self, key: str) -> None:
        delta = {
            "UP": (0, -1), "w": (0, -1), "NUM8": (0, -1),
            "DOWN": (0, 1), "s": (0, 1), "NUM2": (0, 1),
            "LEFT": (-1, 0), "a": (-1, 0), "NUM4": (-1, 0),
            "RIGHT": (1, 0), "d": (1, 0), "NUM6": (1, 0),
        }.get(key)
        if delta:
            self.cursor_x = max(2, min(self.tank_width - 3, self.cursor_x + delta[0]))
            self.cursor_y = max(2, min(self.tank_height - 3, self.cursor_y + delta[1]))

    def _start_cleaning(self) -> None:
        rng = random.Random(self.seed ^ self.day_number * 8191)
        count = 3 if int(self.state.get("condition", 2)) >= 2 else 5 if int(self.state.get("condition", 2)) == 1 else 7
        self.algae = sorted({
            (rng.randint(3, self.tank_width - 4), rng.randint(3, self.tank_height - 4))
            for _ in range(count * 3)
        })[:count]
        self.mode = "clean"
        self.message = "Move the scraper and press Z on each algae patch."

    def _finish_feeding(self) -> None:
        self.state["last_fed_day"] = self.day_key
        self.state["last_fed_ordinal"] = self.day_number
        self.state["feedings"] = max(0, int(self.state.get("feedings", 0))) + 1
        baby = None
        # Planted tanks give fry somewhere to shelter, so pairs spawn more often.
        interval = max(2, 4 - decoration_effect_total(self.state, "breeding"))
        if int(self.state["feedings"]) % interval == 0:
            baby = breed_aquarium_fish(self.record, self.fish_data, self.capacity, self.seed + self.day_number)
        self.mode = "watch"
        self.changed = True
        self.minutes += 5
        self.message = "The fish chase the last of the food." if not baby else f"A new {baby['species']} fry appears!"
        _log_event(self.state, self.message)
        sync_aquarium_legacy_fields(self.record)

    def _update_animation(self) -> None:
        self.tick += 1
        width, height = self.tank_width, self.tank_height
        for pellet in self.food:
            if self.tick % 2 == 0:
                pellet["y"] = min(height - 3, pellet["y"] + 1)
        for index, fish in enumerate(self.individuals):
            phase = int(fish.get("phase", index * 7))
            personality = str(fish.get("personality", "calm"))
            species = str(fish.get("species", ""))
            period = 5 if personality == "sleepy" else 2 if personality in {"curious", "playful"} or species in FAST_SPECIES else 3
            if fish_stage(int(fish.get("age_days", 0)), int(fish.get("lifespan_days", 0))) == "Elder":
                period += 2
            # A glowstone gives the tank its own soft light, so shy cave species
            # stay active with the main lights switched off.
            lit = bool(self.state.get("lights_on", True)) or bool(
                decoration_effect_total(self.state, "light")
            )
            if species in HIDING_SPECIES and lit:
                period += 2
            if (self.tick + phase) % period:
                continue
            target = None
            if self.food:
                target = min(self.food, key=lambda p: abs(int(fish.get("x", 3)) - p["x"]) + abs(int(fish.get("y", 3)) - p["y"]))
            elif species in SCHOOLING_SPECIES:
                same_species = [v for v in self.individuals if v is not fish and v.get("species") == species]
                if same_species:
                    target_fish = min(same_species, key=lambda v: abs(int(fish.get("x", 3)) - int(v.get("x", 3))))
                    # Close the distance from far away, but once already near the
                    # school let the fish keep roaming instead of freezing in
                    # place forever the moment it catches up.
                    if abs(int(fish.get("x", 3)) - int(target_fish.get("x", 3))) > 3:
                        target = {"x": int(target_fish.get("x", 3)), "y": int(target_fish.get("y", 3))}
            elif personality == "social" and len(self.individuals) > 1:
                others = [v for v in self.individuals if v is not fish]
                target_fish = min(others, key=lambda v: abs(int(fish.get("x", 3)) - int(v.get("x", 3))))
                if abs(int(fish.get("x", 3)) - int(target_fish.get("x", 3))) > 3:
                    target = {"x": int(target_fish.get("x", 3)), "y": int(target_fish.get("y", 3))}
            elif species in HIDING_SPECIES:
                shelters = decorations_with_effect(self.state, "shelter")
                if shelters:
                    shelter = min(shelters, key=lambda d: abs(int(fish.get("x", 3)) - int(d.get("x", 3))))
                    shelter_target = {
                        "x": int(shelter.get("x", 3)) + 1,
                        "y": int(shelter.get("y", height - 4)) + 1,
                    }
                    # Shelter is a home range, not a permanent parking spot.
                    # Once a hiding fish is safely nearby it should resume a
                    # short patrol instead of targeting the exact same cell on
                    # every update and becoming motionless forever.
                    if (
                        abs(int(fish.get("x", 3)) - shelter_target["x"])
                        + abs(int(fish.get("y", 3)) - shelter_target["y"])
                    ) > 2:
                        target = shelter_target
            elif personality == "shy":
                covers = decorations_with_effect(self.state, "cover")
                if covers:
                    cover = min(covers, key=lambda d: abs(int(fish.get("x", 3)) - int(d.get("x", 3))))
                    cover_target = {
                        "x": int(cover.get("x", 3)) + 1,
                        "y": int(cover.get("y", height - 4)),
                    }
                    if (
                        abs(int(fish.get("x", 3)) - cover_target["x"])
                        + abs(int(fish.get("y", 3)) - cover_target["y"])
                    ) > 2:
                        target = cover_target
            if species in BOTTOM_SPECIES and target is None:
                # Bottom dwellers settle beside cover when any is available
                # instead of only patrolling the floor.
                covers = decorations_with_effect(self.state, "cover")
                if covers:
                    cover = min(covers, key=lambda d: abs(int(fish.get("x", 3)) - int(d.get("x", 3))))
                    cover_target = {"x": int(cover.get("x", 3)) + 1, "y": height - 3}
                    if abs(int(fish.get("x", 3)) - cover_target["x"]) > 2:
                        target = cover_target
                    else:
                        target = {
                            "x": int(fish.get("x", 3)) + int(fish.get("direction", 1)) * 4,
                            "y": height - 3,
                        }
                else:
                    target = {"x": int(fish.get("x", 3)) + int(fish.get("direction", 1)) * 4, "y": height - 3}
            if target:
                dx = 1 if target["x"] > int(fish.get("x", 3)) else -1 if target["x"] < int(fish.get("x", 3)) else 0
                dy = 1 if target["y"] > int(fish.get("y", 3)) else -1 if target["y"] < int(fish.get("y", 3)) else 0
                fish["direction"] = dx or int(fish.get("direction", 1))
                fish["x"] = int(fish.get("x", 3)) + dx
                if (self.tick + phase) % 4 == 0:
                    fish["y"] = int(fish.get("y", 3)) + dy
                # Target-driven fish used to skip the ordinary patrol branch's
                # edge handling. Bottom dwellers without cover continually set
                # a target four cells ahead, so they could swim permanently out
                # of the visible tank. Clamp every targeted move to the same
                # drawable bounds and turn the fish back at a horizontal edge.
                sprite_len = len(self._fish_sprite(fish))
                min_x = 2
                max_x = max(min_x, width - sprite_len - 2)
                unclamped_x = int(fish["x"])
                fish["x"] = max(min_x, min(max_x, unclamped_x))
                fish["y"] = max(2, min(height - 3, int(fish.get("y", 3))))
                if int(fish["x"]) != unclamped_x:
                    fish["direction"] = -1 if unclamped_x > max_x else 1
                if self.food and abs(int(fish["x"]) - target["x"]) <= 1 and abs(int(fish["y"]) - target["y"]) <= 1:
                    if target in self.food:
                        self.food.remove(target)
                continue
            direction = int(fish.get("direction", 1))
            fish["x"] = int(fish.get("x", 3)) + direction
            sprite_len = len(self._fish_sprite(fish))
            if int(fish["x"]) <= 2 or int(fish["x"]) >= width - sprite_len - 2:
                fish["direction"] = -direction
                fish["x"] = max(2, min(width - sprite_len - 2, int(fish["x"])))
            if (self.tick + phase) % 11 == 0 and personality != "sleepy":
                # Do not derive vertical direction from the same tick modulus
                # that schedules movement. For three- and five-tick swimmers,
                # those congruences repeatedly selected the same direction,
                # so a fish drawn down by food could remain pinned to the tank
                # floor. Alternating by completed vertical cycles guarantees a
                # gentle rise-and-fall patrol for every movement period.
                vertical_cycle = (self.tick + phase) // 11
                vertical_step = -1 if (vertical_cycle + phase + index) % 2 == 0 else 1
                fish["y"] = max(
                    2,
                    min(height - 3, int(fish.get("y", 4)) + vertical_step),
                )

    def _handle_key(self, key: str) -> Optional[AquariumResult]:
        key = normalize_key(key)
        if key in {"\x1b", "q", "x", "b", "\t"}:
            if self.mode != "watch":
                self.mode = "watch"
                self.message = "Action cancelled."
                return None
            return AquariumResult("exit", changed=self.changed, minutes=self.minutes, message="You step away from the aquarium.")
        if self.mode in {"feed", "clean", "decorate"}:
            self._move_cursor(key)
            if self.mode == "decorate" and key in {"[", "]"}:
                self.decor_index = (self.decor_index + (-1 if key == "[" else 1)) % len(DECORATION_SPRITES)
            elif self.mode == "decorate" and key == "r":
                decorations = self.state.get("decorations", [])
                nearby = [d for d in decorations if abs(int(d.get("x", 0)) - self.cursor_x) <= 3 and abs(int(d.get("y", 0)) - self.cursor_y) <= 2]
                if nearby:
                    decorations.remove(nearby[0]); self.changed = True; self.message = "Decoration removed."
            elif key in {"z", "\r", "\n", " "}:
                if self.mode == "feed":
                    self.food.append({"x": self.cursor_x, "y": self.cursor_y})
                    self.food_left -= 1
                    if self.food_left <= 0:
                        self._finish_feeding()
                    else:
                        self.message = (
                            f"Drop {self.food_left} "
                            f"{quantity_agreement(self.food_left, 'more food portion', 'more food portions')}."
                        )
                elif self.mode == "clean":
                    removed = [spot for spot in self.algae if abs(spot[0] - self.cursor_x) <= 1 and abs(spot[1] - self.cursor_y) <= 1]
                    self.algae = [spot for spot in self.algae if spot not in removed]
                    self.message = (
                        "Scrub closer to an algae patch."
                        if not removed else f"Cleaned {quantity_agreement(len(removed), 'patch')}."
                    )
                    if not self.algae:
                        self.state["condition"] = 2
                        self.state["last_cleaned_day"] = self.day_key
                        self.state["last_cleaned_ordinal"] = self.day_number
                        self.mode = "watch"; self.changed = True; self.minutes += 10
                        self.message = "The glass and water are clear again."
                        _log_event(self.state, self.message)
                else:
                    if len(self.state.get("decorations", [])) >= 16:
                        self.message = "The tank has no room for more decorations."
                    else:
                        kind = tuple(DECORATION_SPRITES)[self.decor_index % len(DECORATION_SPRITES)]
                        self.state.setdefault("decorations", []).append({"kind": kind, "x": self.cursor_x, "y": self.cursor_y})
                        self.changed = True; self.minutes += 1; self.message = f"Placed {kind.lower()}."
            return None

        if key == "[" and self.individuals:
            self.selected_index = (self.selected_index - 1) % len(self.individuals)
        elif key == "]" and self.individuals:
            self.selected_index = (self.selected_index + 1) % len(self.individuals)
        elif key == "f":
            if not self.individuals:
                self.message = "There are no fish to feed."
            elif str(self.state.get("last_fed_day", "")) == self.day_key:
                self.message = "The fish have already been fed today."
            else:
                self.mode = "feed"; self.food_left = 3
                self.cursor_x, self.cursor_y = self.tank_width // 2, 3
                self.message = "Move the food marker and press Z three times."
        elif key == "c":
            self._start_cleaning()
        elif key == "d":
            self.mode = "decorate"; self.cursor_x, self.cursor_y = self.tank_width // 2, self.tank_height - 4
            self.message = "Move, [/] choose, Z place, R remove, B finish."
        elif key == "l":
            self.state["lights_on"] = not bool(self.state.get("lights_on", True))
            self.changed = True; self.message = f"Aquarium lights {'on' if self.state['lights_on'] else 'off'}."
        elif key == "h":
            if self.individuals:
                self.message = "Remove the fish before changing the tank habitat."
            else:
                current = AQUARIUM_HABITATS.index(str(self.state.get("habitat", "Freshwater")))
                self.state["habitat"] = AQUARIUM_HABITATS[(current + 1) % len(AQUARIUM_HABITATS)]
                self.changed = True; self.message = f"Configured for {self.state['habitat'].lower()} fish."
        elif key == "s":
            return AquariumResult("stock", changed=self.changed, minutes=self.minutes)
        elif key == "r":
            selected = self.selected_fish()
            if selected:
                return AquariumResult("take", str(selected.get("id", "")), self.changed, self.minutes)
            self.message = "There are no fish to remove."
        elif key == "n":
            selected = self.selected_fish()
            if selected:
                return AquariumResult("name", str(selected.get("id", "")), self.changed, self.minutes)
            self.message = "There are no fish to name."
        elif key == "t":
            selected = self.selected_fish()
            if selected:
                return AquariumResult("transfer", str(selected.get("id", "")), self.changed, self.minutes)
            self.message = "There are no fish to transfer."
        elif key == "k":
            return AquariumResult("tank_name", changed=self.changed, minutes=self.minutes)
        elif key == "v":
            return AquariumResult("collection", changed=self.changed, minutes=self.minutes)
        elif key == "a":
            return AquariumResult("caretaker", changed=self.changed, minutes=self.minutes)
        elif key == "m":
            memorials = list(reversed(self.state.get("memorials", [])))
            if not memorials:
                self.message = "No fish are recorded in the aquarium memorial yet."
            else:
                memorial = memorials[self.memorial_index % len(memorials)]
                self.memorial_index = (self.memorial_index + 1) % len(memorials)
                age_days = max(0, int(memorial.get("age_days", 0) or 0))
                age_text = f"{age_days // 365}y {age_days % 365}d"
                self.message = (
                    f"Remembering {memorial.get('name', 'a fish')}, "
                    f"a {memorial.get('species', 'fish')} who lived {age_text}."
                )
        return None

    def run(self) -> AquariumResult:
        if not bool(getattr(sys.stdin, "isatty", lambda: False)()):
            return AquariumResult("exit")
        self._configure_dimensions()
        try:
            while True:
                self._configure_dimensions()
                self._update_animation()
                self.writer.draw(self.render_lines())
                key = read_key_timeout(AQUARIUM_FRAME_SECONDS)
                if key:
                    result = self._handle_key(key)
                    if result is not None:
                        sync_aquarium_legacy_fields(self.record)
                        return result
        finally:
            self.writer.finish()


__all__ = [
    "AQUARIUM_HABITATS",
    "AQUARIUM_SCHEMA_VERSION",
    "AquariumResult",
    "AquariumViewer",
    "add_aquarium_fish",
    "apply_household_aquarium_care",
    "advance_aquarium_days",
    "aquarium_capacity",
    "aquarium_day_number",
    "breed_aquarium_fish",
    "can_stock_species",
    "FISH_COLOR_PALETTE",
    "FISH_SPECIES_COLORS",
    "fish_species_color",
    "fish_species_sprite",
    "normalize_aquarium_state",
    "remove_aquarium_fish",
    "rename_aquarium_fish",
    "species_habitat",
    "species_lifespan_days",
    "sync_aquarium_legacy_fields",
    "transfer_aquarium_fish",
]
