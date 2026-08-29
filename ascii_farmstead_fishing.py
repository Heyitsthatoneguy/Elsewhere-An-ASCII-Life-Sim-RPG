from __future__ import annotations

"""Pure fishing helpers shared by casting, rendering, and fish selection."""

import math
import random
from typing import Callable, Dict, Iterable, List, Sequence, Tuple


FISHING_DEPTH_ORDER = ("Shallow", "Normal", "Deep")


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """Return every grid cell from the origin through the destination."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    points: List[Tuple[int, int]] = []
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return points
        twice_error = 2 * error
        if twice_error >= dy:
            error += dy
            x0 += sx
        if twice_error <= dx:
            error += dx
            y0 += sy


def fishing_line_glyph(
    previous: Tuple[int, int],
    current: Tuple[int, int],
    following: Tuple[int, int],
    detailed: bool = True,
) -> str:
    if not detailed:
        return "."
    x0, y0 = previous
    x1, y1 = current
    x2, y2 = following
    if y0 == y1 == y2:
        return "─"
    if x0 == x1 == x2:
        return "│"
    slope_a = (x1 - x0) * (y1 - y0)
    slope_b = (x2 - x1) * (y2 - y1)
    if slope_a > 0 and slope_b > 0:
        return "╲"
    if slope_a < 0 and slope_b < 0:
        return "╱"
    return "·"


def classify_water_depth(
    x: int,
    y: int,
    habitat: str,
    is_water: Callable[[int, int], bool],
    max_radius: int = 5,
) -> str:
    """Classify depth from distance to the nearest bank around a water tile."""
    if not is_water(int(x), int(y)):
        return ""
    bank_distance = max_radius + 1
    for radius in range(1, max(2, int(max_radius) + 1)):
        found_bank = False
        for check_y in range(int(y) - radius, int(y) + radius + 1):
            for check_x in range(int(x) - radius, int(x) + radius + 1):
                if max(abs(check_x - int(x)), abs(check_y - int(y))) != radius:
                    continue
                if not is_water(check_x, check_y):
                    found_bank = True
                    break
            if found_bank:
                break
        if found_bank:
            bank_distance = radius
            break

    habitat = str(habitat or "")
    if bank_distance <= 1:
        return "Shallow"
    if habitat == "Ocean":
        return "Normal" if bank_distance <= 3 else "Deep"
    if habitat in {"Lake", "Underground"}:
        return "Normal" if bank_distance <= 3 else "Deep"
    if habitat == "Pond":
        return "Normal" if bank_distance <= 4 else "Deep"
    # Rivers remain mostly shallow/normal unless generation produces a truly
    # broad channel.
    return "Deep" if bank_distance >= 5 else "Normal"


def fish_depth_preferences(fish_name: str, data: Dict[str, object]) -> Tuple[str, ...]:
    explicit = tuple(str(value) for value in data.get("depths", []) or [])
    if explicit:
        return explicit
    name = str(fish_name)
    if bool(data.get("junk")):
        return FISHING_DEPTH_ORDER
    deep_names = {
        "Mud Loach", "Catfish", "Carp", "Night Eel", "Walleye", "Lake Sturgeon",
        "Muskellunge", "Longnose Gar", "Steelhead", "Storm Cod", "Moon Eel",
        "Reef Grouper", "Sunfin Tuna", "Halibut", "Swordfish", "Blue Marlin",
        "Cave Carp", "Crystal Eel", "Pale Koi",
    }
    shallow_names = {
        "Pond Minnow", "Mosquitofish", "Golden Shiner", "Pumpkinseed", "Bluegill",
        "Sunfish", "River Chub", "Dace", "Brook Trout", "Coral Dart", "Parrotfish",
        "Pufferfish", "Blind Minnow",
    }
    if name in deep_names:
        return ("Normal", "Deep")
    if name in shallow_names:
        return ("Shallow", "Normal")
    habitats = {str(value) for value in data.get("habitats", []) or []}
    if "Ocean" in habitats:
        return ("Normal", "Deep")
    return FISHING_DEPTH_ORDER


def fish_tackle_traits(fish_name: str, data: Dict[str, object]) -> Dict[str, Tuple[str, ...]]:
    name = str(fish_name)
    habitats = tuple(str(value) for value in data.get("habitats", []) or [])
    features = tuple(str(value) for value in data.get("water_features", []) or [])
    small = any(word in name for word in ("Minnow", "Dace", "Shiner", "Sardine", "Anchovy", "Smelt"))
    predators = any(word in name for word in (
        "Bass", "Trout", "Pike", "Gar", "Salmon", "Walleye", "Muskellunge",
        "Tuna", "Swordfish", "Marlin", "Snapper", "Grouper",
    ))
    bottom = any(word in name for word in ("Carp", "Catfish", "Loach", "Sturgeon", "Halibut", "Cod"))
    nocturnal = str(data.get("time", "Any")) == "Night" or any(word in name for word in ("Eel", "Lantern", "Crystal", "Pale"))

    lures: List[str] = []
    baits: List[str] = []
    if any(habitat in {"Pond", "Lake", "River"} for habitat in habitats):
        baits.extend(["Insect Bait" if small else "Worm Bait"])
        lures.append("Surface Popper" if small else "Spinner Lure")
    if predators:
        lures.extend(["Spinner Lure", "Bright Spoon"])
        baits.append("Minnow Bait")
    if bottom:
        baits.append("Shellfish Bait" if "Ocean" in habitats else "Worm Bait")
        lures.append("Bright Spoon")
    if "Ocean" in habitats:
        baits.append("Shellfish Bait")
        lures.append("Reef Jig" if "Reef" in features else "Bright Spoon")
    if "Underground" in habitats:
        baits.append("Cave Grub")
        lures.append("Glow Lure")
    if nocturnal:
        lures.append("Glow Lure")

    def unique(values: Iterable[str]) -> Tuple[str, ...]:
        return tuple(dict.fromkeys(str(value) for value in values if value))

    return {"lures": unique(lures), "baits": unique(baits)}


def tackle_weight_multiplier(
    fish_name: str,
    data: Dict[str, object],
    lure: str,
    bait: str,
) -> float:
    traits = fish_tackle_traits(fish_name, data)
    multiplier = 1.0
    if lure and lure != "None":
        multiplier *= 2.75 if lure in traits["lures"] else 0.72
    if bait and bait != "None":
        multiplier *= 2.25 if bait in traits["baits"] else 0.78
    return multiplier


FISHING_DRAG_LABELS = ("Loose", "Balanced", "Firm")
# Fraction of rod reel power recovered per second in the rest window. This is
# the main dial on fight length: a typical catch should land inside roughly
# 20-45 seconds, so lowering it lengthens every fight at once.
#
# It also has to clear the fish's pull by more than the surge-to-rest ratio, or
# a long run takes back more line than the rest that follows can recover. The
# weakest pairing in the game -- the starter rod against a Powerful fish -- is
# the one that sets this floor.
FISHING_REST_RETRIEVAL = 0.72
# How far a strong fish starts out. Powerful fish are long fights mainly because
# they begin farther away, so this keeps a trophy feeling big without letting it
# outstay that window. Scaling distance rather than retrieval matters: slowing a
# strong fish's retrieval drives its net progress per cycle toward zero, and the
# fight length then swings wildly on small changes.
FISHING_POWER_REACH = 0.4
# How much line a fight spans. Distance has to scale with phase length: at the
# old ~1.5s cycles a fish sat close enough that a single rest could not reel it
# home, but a 7s rest recovers several times that, and the fight ended inside
# the first pause before the fish ever ran twice. This sets how many runs a
# catch actually takes.
FISHING_LINE_SCALE = 1.5
# How much of the rod's reel power bites back while the fish is running. The
# floor beside it means a surge always takes some line no matter what, so this
# only sets how much a well-timed pull claws back.
FISHING_SURGE_REEL_OPPOSE = 0.34
# Guaranteed tension relief per second for giving line during a run. Without a
# floor, a firm drag on a light line raises tension even when the player lets
# go, which leaves no recovery path at the only drag that gains line -- and
# makes the in-game advice to release during a surge untrue.
FISHING_SLACK_RELIEF_FLOOR = 6.0


def fish_fight_behavior(fish_name: str, fish_data: Dict[str, object]) -> str:
    name = str(fish_name)
    if bool(fish_data.get("junk")):
        return "Inert"
    if any(word in name for word in (
        "Muskellunge", "Steelhead", "Tuna", "Swordfish", "Marlin",
    )):
        return "Powerful"
    if any(word in name for word in (
        "Minnow", "Dace", "Shiner", "Smelt", "Sardine", "Anchovy", "Trout",
        "Salmon", "Mackerel", "Tuna", "Swordfish", "Marlin", "Dart",
    )):
        return "Darting"
    if any(word in name for word in (
        "Carp", "Catfish", "Loach", "Sturgeon", "Halibut", "Grouper", "Cod",
    )):
        return "Stubborn"
    if any(word in name for word in (
        "Eel", "Pike", "Muskellunge", "Gar", "Pufferfish",
    )):
        return "Erratic"
    return "Steady"


def fish_fight_profile(
    fish_name: str,
    fish_data: Dict[str, object],
    size_factor: float = 1.0,
) -> Dict[str, float]:
    """Build fight-only traits without reusing the fish's food recovery value."""
    behavior = fish_fight_behavior(fish_name, fish_data)
    # Burst and rest set the fight's duty cycle. A surge can only take line, so
    # the rest window is the player's entire opportunity to gain it back.
    #
    # Seconds per phase. At the ~1.5s these used to be, a quarter of the window
    # was gone to human reaction time before the player could start reeling,
    # which made the fight feel like mashing rather than playing. Each phase now
    # lands somewhere in 3-6 seconds once jitter is applied.
    #
    # Size deliberately does NOT appear here. A big fish is not one with longer
    # runs, it is one that has to be brought further, so it runs more times --
    # size scales the line to recover instead (see build_fishing_fight_state).
    profiles = {
        "Darting": {"power": 0.95, "burst": 4.20, "rest": 4.60, "speed": 1.28, "strain": 1.05},
        "Powerful": {"power": 1.55, "burst": 4.90, "rest": 4.50, "speed": 1.18, "strain": 1.34},
        "Stubborn": {"power": 1.24, "burst": 4.80, "rest": 4.70, "speed": 0.90, "strain": 1.18},
        "Erratic": {"power": 1.12, "burst": 4.40, "rest": 4.30, "speed": 1.12, "strain": 1.24},
        "Steady": {"power": 1.00, "burst": 4.60, "rest": 4.70, "speed": 1.00, "strain": 1.00},
        "Inert": {"power": 0.32, "burst": 3.20, "rest": 5.40, "speed": 0.35, "strain": 0.45},
    }
    base = dict(profiles.get(behavior, profiles["Steady"]))
    price = max(1, int(fish_data.get("price", 1) or 1))
    rarity = min(0.18, price / 3500.0)
    size_factor = max(0.75, min(1.30, float(size_factor)))
    power = base["power"] * (0.82 + size_factor * 0.25 + rarity)
    return {
        "power": min(2.8, max(0.28, float(fish_data.get("fight_power", power) or power))),
        # Size stretches both halves of the cycle equally, so a big fish is a
        # longer fight rather than a tighter one. Scaling only the run would
        # quietly skew the duty cycle against the player on exactly the biggest
        # fish, which is where a light rod can least afford it.
        "burst_seconds": max(3.00, float(fish_data.get("burst_seconds", base["burst"]) or 4.60)),
        "rest_seconds": max(3.00, float(fish_data.get("rest_seconds", base["rest"]) or 4.60)),
        "speed": base["speed"],
        "strain": base["strain"],
    }


def fish_vertical_preference(fish_name: str, fish_data: Dict[str, object], depth: str) -> float:
    """Return a normalized underwater depth preference for fight rendering."""
    name = str(fish_name)
    if any(word in name for word in (
        "Carp", "Catfish", "Loach", "Sturgeon", "Halibut", "Grouper", "Cod",
        "Burbot", "Sculpin", "Skate", "Sucker", "Lamprey",
    )):
        return 0.76
    if any(word in name for word in (
        "Minnow", "Dace", "Shiner", "Sardine", "Anchovy", "Darter", "Archerfish",
    )):
        return 0.30
    return {"Shallow": 0.40, "Normal": 0.52, "Deep": 0.65}.get(str(depth), 0.52)


def fishing_surge_maneuver(behavior: str, pulse: float) -> str:
    """Choose a readable maneuver from one deterministic frame pulse."""
    pulse = max(0.0, min(1.0, float(pulse)))
    thresholds = {
        "Darting": ((0.30, "turn"), (0.57, "rise"), (0.84, "run"), (1.01, "shake")),
        "Powerful": ((0.38, "dive"), (0.82, "run"), (1.01, "shake")),
        "Stubborn": ((0.46, "dive"), (0.72, "shake"), (1.01, "run")),
        "Erratic": ((0.27, "turn"), (0.52, "dive"), (0.76, "rise"), (1.01, "shake")),
        "Steady": ((0.22, "dive"), (0.40, "rise"), (0.82, "run"), (1.01, "turn")),
        "Inert": ((1.01, "drift"),),
    }.get(str(behavior), ((1.01, "run"),))
    for limit, maneuver in thresholds:
        if pulse < limit:
            return maneuver
    return "run"


def fishing_maneuver_notice(maneuver: str, direction: int) -> str:
    side = "right" if int(direction) >= 0 else "left"
    return {
        "dive": "The fish dives hard and pulls line into deeper water!",
        "rise": "The fish rises and darts toward the surface!",
        "turn": f"The fish turns sharply and runs {side}!",
        "shake": "The fish thrashes against the hook—protect the line!",
        "drift": "The hooked weight drifts through the water.",
        "run": f"The fish powers away to the {side}!",
    }.get(str(maneuver), "The fish surges and takes line!")


def build_fishing_fight_state(
    fish_name: str,
    fish_data: Dict[str, object],
    rod_name: str,
    rod_data: Dict[str, object],
    depth: str,
    cast_distance: int,
    lure: str = "None",
    bait: str = "None",
    seed: int = 0,
    habitat: str = "",
) -> Dict[str, object]:
    """Build a deterministic, transient fight for an advanced fishing rod."""
    rng = random.Random(int(seed))
    behavior = fish_fight_behavior(fish_name, fish_data)
    size_factor = rng.uniform(0.88, 1.16)
    fight_profile = fish_fight_profile(fish_name, fish_data, size_factor)
    affinity = 0
    traits = fish_tackle_traits(fish_name, fish_data)
    if lure and lure != "None" and lure in traits["lures"]:
        affinity += 1
    if bait and bait != "None" and bait in traits["baits"]:
        affinity += 1

    fish_power = float(fight_profile["power"]) * (1.0 - affinity * 0.04)
    burst_energy_max = 100.0 * size_factor
    burst_seconds = float(fight_profile["burst_seconds"]) * (1.0 - affinity * 0.03)
    rest_seconds = float(fight_profile["rest_seconds"]) * (1.0 + affinity * 0.06)
    initial_burst_seconds = burst_seconds * rng.uniform(0.70, 1.30)
    depth_bonus = {"Shallow": 0.0, "Normal": 2.0, "Deep": 4.0}.get(str(depth), 1.0)
    # Size lands here rather than on phase length: a larger fish sits further out,
    # so bringing it in costs more runs. The exponent widens a narrow size roll
    # (0.88-1.16) into a visible spread in how many times the fish breaks away.
    starting_distance = (
        6.5 + max(1, int(cast_distance)) * 0.65 + depth_bonus + fish_power * FISHING_POWER_REACH
    ) * FISHING_LINE_SCALE * (size_factor ** 2.5)
    rod_range = max(1, int(rod_data.get("range", 4) or 4))
    line_strength = max(0.7, float(rod_data.get("line_strength", 1.0) or 1.0))
    spool_limit = starting_distance + (
        10.0 + rod_range * 1.35 + line_strength * 3.5
    ) * FISHING_LINE_SCALE
    size_label = (
        "small" if size_factor < 0.95
        else "large" if size_factor > 1.08
        else "average-sized"
    )
    habitats = [str(value) for value in fish_data.get("habitats", []) or []]
    habitat = str(habitat or (habitats[0] if habitats else "Lake"))
    fish_direction = -1 if rng.random() < 0.5 else 1
    depth_preference = fish_vertical_preference(fish_name, fish_data, depth)
    fish_depth = max(0.16, min(0.84, depth_preference + rng.uniform(-0.08, 0.08)))
    initial_maneuver = fishing_surge_maneuver(behavior, rng.random())
    bubbles = [
        {
            "x": rng.uniform(-20.0, 20.0),
            "depth": rng.uniform(0.12, 0.90),
            "speed": rng.uniform(0.10, 0.24),
            "glyph": "°" if index % 3 == 0 else "·",
        }
        for index in range(12)
    ]
    return {
        "fish_name": str(fish_name),
        "rod_name": str(rod_name),
        "depth": str(depth or "Open"),
        "lure": str(lure or "None"),
        "bait": str(bait or "None"),
        "fish_power": fish_power,
        # Vigor aliases are retained for old extensions, but the fight now uses
        # renewable burst energy rather than permanent exhaustion.
        "burst_energy": burst_energy_max,
        "burst_energy_max": burst_energy_max,
        "vigor": burst_energy_max,
        "vigor_max": burst_energy_max,
        "burst_seconds": burst_seconds,
        "rest_seconds": rest_seconds,
        "burst_drain_rate": burst_energy_max / max(0.1, initial_burst_seconds),
        "burst_recovery_rate": burst_energy_max / max(0.1, rest_seconds),
        "fight_speed": float(fight_profile["speed"]),
        "fight_strain": float(fight_profile["strain"]),
        "distance": starting_distance,
        "starting_distance": starting_distance,
        "spool_limit": spool_limit,
        "tension": max(8.0, 23.0 - affinity * 3.0),
        "mode": "surge",
        "mode_time": initial_burst_seconds,
        "maneuver_time": rng.uniform(0.48, 0.88),
        "cycle_count": 0,
        "elapsed": 0.0,
        "result": "active",
        "notice": (
            f"{'An' if size_label[0].lower() in 'aeiou' else 'A'} {size_label} {fish_name} takes the hook. "
            f"{fishing_maneuver_notice(initial_maneuver, fish_direction)}"
        ),
        "mode_changed": True,
        "size_label": size_label,
        "affinity": affinity,
        "behavior": behavior,
        "reeling": False,
        "continuous_reel_time": 0.0,
        "drag": 1,
        "habitat": habitat,
        "maneuver": initial_maneuver,
        "fish_direction": fish_direction,
        "fish_world_x": 0.0,
        "fish_depth": fish_depth,
        "fish_depth_target": fish_depth,
        "depth_preference": depth_preference,
        "camera_x": 0.0,
        "line_delta": 0.0,
        "pull_rate": 0.0,
        "reel_rate": 0.0,
        "current_strength": rng.uniform(-0.24, 0.24) if habitat in {"River", "Ocean"} else rng.uniform(-0.08, 0.08),
        "bottom_seed": rng.randrange(1, 1_000_000),
        "bubbles": bubbles,
    }


def advance_fishing_fight(
    state: Dict[str, object],
    elapsed_seconds: float,
    reeling: bool,
    drag: int,
    random_value: float = 0.5,
    rod_data: Dict[str, object] | None = None,
) -> Dict[str, object]:
    """Advance one frame of the fish fight and return the mutated state."""
    if str(state.get("result", "active")) != "active":
        return state
    dt = max(0.0, min(0.25, float(elapsed_seconds)))
    drag = max(0, min(2, int(drag)))
    pulse = max(0.0, min(1.0, float(random_value)))
    rod = dict(rod_data or {})
    line_strength = max(0.7, float(rod.get("line_strength", 1.0) or 1.0))
    reel_power = max(3.0, float(rod.get("reel_power", 4.8) or 4.8))
    control = max(0.7, float(rod.get("control", 1.0) or 1.0))
    reel_factors = (0.76, 1.0, 1.24)
    tension_factors = (0.68, 1.0, 1.34)
    behavior = str(state.get("behavior", "Steady"))
    behavior_profile = {
        "speed": max(0.3, float(state.get("fight_speed", 1.0) or 1.0)),
        "strain": max(0.4, float(state.get("fight_strain", 1.0) or 1.0)),
    }

    state["reeling"] = bool(reeling)
    state["drag"] = drag
    state["elapsed"] = float(state.get("elapsed", 0.0) or 0.0) + dt
    state["mode_changed"] = False
    state["maneuver_changed"] = False
    mode = str(state.get("mode", "surge"))
    maneuver = str(state.get("maneuver", "run"))
    burst_energy = max(0.0, float(state.get("burst_energy", state.get("vigor", 100.0)) or 0.0))
    burst_energy_max = max(1.0, float(state.get("burst_energy_max", state.get("vigor_max", 100.0)) or 100.0))
    burst_seconds = max(3.00, float(state.get("burst_seconds", 5.00) or 5.00))
    rest_seconds = max(3.00, float(state.get("rest_seconds", 5.00) or 5.00))
    burst_drain_rate = max(1.0, float(state.get("burst_drain_rate", burst_energy_max / burst_seconds) or 1.0))
    burst_recovery_rate = max(1.0, float(state.get("burst_recovery_rate", burst_energy_max / rest_seconds) or 1.0))
    power = max(0.5, float(state.get("fish_power", 1.0) or 1.0))
    distance = max(0.0, float(state.get("distance", 0.0) or 0.0))
    previous_distance = distance
    tension = max(0.0, float(state.get("tension", 0.0) or 0.0))
    fish_direction = -1 if int(state.get("fish_direction", 1) or 1) < 0 else 1
    fish_world_x = float(state.get("fish_world_x", 0.0) or 0.0)
    depth_preference = max(0.12, min(0.88, float(state.get("depth_preference", 0.52) or 0.52)))
    fish_depth = max(0.10, min(0.92, float(state.get("fish_depth", depth_preference) or depth_preference)))
    fish_depth_target = max(0.10, min(0.92, float(state.get("fish_depth_target", depth_preference) or depth_preference)))
    continuous_reel_time = max(
        0.0, float(state.get("continuous_reel_time", 0.0) or 0.0)
    )
    if reeling:
        continuous_reel_time += dt
    else:
        # Releasing during a surge is how the player clears accumulated strain.
        continuous_reel_time = max(0.0, continuous_reel_time - dt * 4.0)

    if mode == "surge":
        fish_direction = 1
        burst_energy = max(
            0.0,
            burst_energy - dt * burst_drain_rate * (1.0 + drag * 0.025 + (0.04 if reeling else 0.0)),
        )
        energy_ratio = burst_energy / burst_energy_max
        maneuver_pull = {"dive": 1.25, "run": 1.12, "turn": 0.92, "rise": 0.86, "shake": 0.62, "drift": 0.30}.get(maneuver, 1.0)
        outward_speed = power * (1.24 - drag * 0.08) * (0.88 + energy_ratio * 0.12) * behavior_profile["speed"] * maneuver_pull
        if reeling:
            # A live surge always gains at least a little line. Reeling opposes
            # the run, but cannot make an actively pulling fish glide shoreward.
            line_take = max(
                power * 0.28,
                outward_speed - reel_power * reel_factors[drag] * FISHING_SURGE_REEL_OPPOSE,
            )
            distance += dt * line_take
            # Reeling into a run is a mistake, not an execution. The player needs
            # long enough to read the SURGING warning and let go; only holding on
            # well past that point should threaten the line.
            sustained_strain = (
                max(0.0, continuous_reel_time - 1.25)
                * (11.0 + power * 3.0)
                / line_strength
            )
            tension += dt * (
                ((12.0 + power * 11.0) * tension_factors[drag] * behavior_profile["strain"] / line_strength)
                - control * 2.5
                + sustained_strain
            )
        else:
            distance += dt * outward_speed
            # Giving line always buys tension back. The drag still eats into how
            # much relief you get, but never reverses it.
            relief = (
                10.0 * control
                - drag * (3.0 + power * 2.0) * behavior_profile["strain"] / line_strength
            )
            tension -= dt * max(FISHING_SLACK_RELIEF_FLOOR * control, relief)
        # Giving line is the whole answer to a thrashing fish, so a released reel
        # takes much less of the hit. Charging full strain regardless of what the
        # player did made long fights unsurvivable no matter how well they were
        # played, which capped how long a fight could safely run.
        slack_relief = 1.0 if reeling else 0.45
        if maneuver == "shake":
            tension += dt * (9.0 + power * 4.0) * slack_relief / line_strength
        elif maneuver == "dive":
            tension += dt * (3.0 + power * 2.5) * slack_relief / line_strength
        swim_speed = (1.8 + power * 1.3) * behavior_profile["speed"] * (0.82 + energy_ratio * 0.18)
        fish_world_x += swim_speed * dt
        if maneuver == "dive":
            fish_depth_target = min(0.90, depth_preference + 0.22)
        elif maneuver == "rise":
            fish_depth_target = max(0.12, depth_preference - 0.26)
        elif maneuver == "shake":
            fish_depth_target = max(0.14, min(0.88, depth_preference + (0.12 if pulse > 0.5 else -0.12)))
    else:
        fish_direction = -1
        burst_energy = min(burst_energy_max, burst_energy + dt * burst_recovery_rate)
        if reeling:
            distance -= dt * reel_power * reel_factors[drag] * FISHING_REST_RETRIEVAL
            tension += dt * (2.8 * tension_factors[drag] / line_strength)
        else:
            tension -= dt * 18.0 * control
        # A resting fish turns toward the line but holds its ground. It never
        # swims shoreward and cannot reduce catch distance on the player's behalf.
        fish_depth_target = depth_preference

    mode_time = float(state.get("mode_time", 0.0) or 0.0) - dt
    maneuver_time = float(state.get("maneuver_time", 0.0) or 0.0) - dt
    if mode == "surge" and maneuver_time <= 0.0 and burst_energy > 0.0:
        maneuver = fishing_surge_maneuver(behavior, pulse)
        maneuver_time = 0.45 + pulse * 0.48
        state["maneuver_changed"] = True
        state["notice"] = fishing_maneuver_notice(maneuver, fish_direction)

    if mode == "surge" and (burst_energy <= 0.0 or mode_time <= 0.0):
        state["mode_changed"] = True
        mode = "rest"
        burst_energy = 0.0
        mode_time = rest_seconds * (0.70 + pulse * 0.60)
        burst_recovery_rate = burst_energy_max / max(0.1, mode_time)
        maneuver = "rest"
        maneuver_time = mode_time
        fish_direction = -1
        state["notice"] = "The fish stops to recover—reel now before it starts another run!"
    elif mode == "rest" and mode_time <= 0.0:
        state["mode_changed"] = True
        mode = "surge"
        burst_energy = burst_energy_max
        mode_time = burst_seconds * (0.70 + pulse * 0.60)
        burst_drain_rate = burst_energy_max / max(0.1, mode_time)
        maneuver = fishing_surge_maneuver(behavior, pulse)
        maneuver_time = min(mode_time, 0.45 + pulse * 0.48)
        fish_direction = 1
        continuous_reel_time = min(0.35, continuous_reel_time)
        state["cycle_count"] = int(state.get("cycle_count", 0) or 0) + 1
        state["notice"] = fishing_maneuver_notice(maneuver, fish_direction)

    if behavior == "Erratic" and mode == "surge":
        fish_depth_target += math.sin(float(state.get("elapsed", 0.0)) * 5.0) * 0.08
    depth_step = min(1.0, dt * (2.0 if mode == "surge" else 1.2))
    fish_depth += (max(0.10, min(0.92, fish_depth_target)) - fish_depth) * depth_step
    camera_x = float(state.get("camera_x", fish_world_x) or 0.0)
    camera_x += (fish_world_x - camera_x) * min(1.0, dt * 2.8)

    bubbles = state.get("bubbles", [])
    if isinstance(bubbles, list):
        current = float(state.get("current_strength", 0.0) or 0.0)
        elapsed = float(state.get("elapsed", 0.0) or 0.0)
        for index, bubble in enumerate(bubbles):
            if not isinstance(bubble, dict):
                continue
            bubble["depth"] = float(bubble.get("depth", 0.5) or 0.5) - dt * float(bubble.get("speed", 0.16) or 0.16)
            bubble["x"] = float(bubble.get("x", 0.0) or 0.0) + current * dt
            if float(bubble["depth"]) < 0.04:
                bubble["depth"] = 0.88 + ((index * 7 + int(elapsed * 10)) % 8) * 0.01
                bubble["x"] = camera_x + (((index * 17 + int(elapsed * 3)) % 41) - 20)

    state["mode"] = mode
    state["maneuver"] = maneuver
    state["mode_time"] = mode_time
    state["maneuver_time"] = maneuver_time
    state["burst_energy"] = burst_energy
    state["burst_energy_max"] = burst_energy_max
    state["burst_drain_rate"] = burst_drain_rate
    state["burst_recovery_rate"] = burst_recovery_rate
    state["vigor"] = burst_energy
    state["vigor_max"] = burst_energy_max
    state["distance"] = max(0.0, distance)
    state["tension"] = max(5.0, tension)
    state["continuous_reel_time"] = continuous_reel_time
    state["fish_direction"] = fish_direction
    state["fish_world_x"] = fish_world_x
    state["fish_depth"] = max(0.10, min(0.92, fish_depth))
    state["fish_depth_target"] = max(0.10, min(0.92, fish_depth_target))
    state["camera_x"] = camera_x
    line_delta = (float(state["distance"]) - previous_distance) / dt if dt > 0.0 else 0.0
    state["line_delta"] = line_delta
    state["pull_rate"] = max(0.0, line_delta)
    state["reel_rate"] = max(0.0, -line_delta)

    if float(state["tension"]) >= 100.0:
        state["tension"] = 100.0
        state["result"] = "line_broke"
        state["notice"] = "The line snaps under the strain."
    elif float(state["distance"]) >= float(state.get("spool_limit", 30.0) or 30.0):
        state["distance"] = float(state.get("spool_limit", 30.0) or 30.0)
        state["result"] = "spooled"
        state["notice"] = "The fish reaches the end of the line and tears free."
    elif float(state["distance"]) <= 0.0:
        state["distance"] = 0.0
        state["result"] = "landed"
        state["notice"] = f"You land the {state.get('fish_name', 'fish')}!"
    return state


__all__ = [
    "FISHING_DRAG_LABELS",
    "FISHING_DEPTH_ORDER",
    "advance_fishing_fight",
    "bresenham_line",
    "build_fishing_fight_state",
    "fish_fight_behavior",
    "fish_fight_profile",
    "fish_vertical_preference",
    "fishing_maneuver_notice",
    "fishing_surge_maneuver",
    "fishing_line_glyph",
    "classify_water_depth",
    "fish_depth_preferences",
    "fish_tackle_traits",
    "tackle_weight_multiplier",
]
