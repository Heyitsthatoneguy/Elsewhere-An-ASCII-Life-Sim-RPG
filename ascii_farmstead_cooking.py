from __future__ import annotations

"""Pure cooking progression helpers shared by runtime and smoke checks."""

from math import ceil
from typing import Dict, Sequence, Tuple


# One source of truth per track: the entry threshold, the label, and what the
# tier grants. Both the public *_THRESHOLDS tuples and the profile lookups below
# are derived from these, so retuning a number cannot leave them disagreeing.
_RECIPE_MASTERY_TIERS: Tuple[Tuple[int, str, int, int], ...] = (
    # threshold, label, buff_bonus, bonus_interval
    (0, "Learning", 0, 0),
    (3, "Familiar", 1, 0),
    (8, "Skilled", 2, 4),
    (16, "Mastered", 3, 2),
)
_COOKING_LEVEL_TIERS: Tuple[Tuple[int, str, int], ...] = (
    # threshold, label, time_reduction
    (0, "Beginner", 0),
    (10, "Home Cook", 1),
    (30, "Seasoned Cook", 2),
    (75, "Expert Cook", 3),
    (150, "Master Chef", 4),
)

RECIPE_MASTERY_THRESHOLDS = tuple(tier[0] for tier in _RECIPE_MASTERY_TIERS)
COOKING_LEVEL_THRESHOLDS = tuple(tier[0] for tier in _COOKING_LEVEL_TIERS)


def _tier_index(value: int, tiers: Sequence[Sequence[object]]) -> int:
    """Index of the highest tier whose threshold ``value`` has reached."""
    index = 0
    for position, tier in enumerate(tiers):
        if value >= int(tier[0]):
            index = position
    return index


def recipe_mastery_profile(times_cooked: object) -> Dict[str, object]:
    count = max(0, int(times_cooked or 0))
    index = _tier_index(count, _RECIPE_MASTERY_TIERS)
    _, label, buff_bonus, bonus_interval = _RECIPE_MASTERY_TIERS[index]
    following = index + 1
    return {
        "label": label,
        "tier": index,
        "count": count,
        "next_count": (
            _RECIPE_MASTERY_TIERS[following][0]
            if following < len(_RECIPE_MASTERY_TIERS)
            else None
        ),
        "buff_bonus": buff_bonus,
        "bonus_interval": bonus_interval,
    }


def cooking_level_profile(total_batches: object) -> Dict[str, object]:
    total = max(0, int(total_batches or 0))
    index = _tier_index(total, _COOKING_LEVEL_TIERS)
    _, label, time_reduction = _COOKING_LEVEL_TIERS[index]
    following = index + 1
    return {
        "label": label,
        "level": index,
        "total": total,
        "next_count": (
            _COOKING_LEVEL_TIERS[following][0]
            if following < len(_COOKING_LEVEL_TIERS)
            else None
        ),
        "time_reduction": time_reduction,
    }


def cooking_time_minutes(
    batch_count: object,
    *,
    kitchen_required: bool,
    station_bonus: object = 0,
    total_batches: object = 0,
) -> int:
    batches = max(1, int(batch_count or 1))
    base_minutes = 15 if kitchen_required else 5
    minimum = 3 if kitchen_required else 2
    station_reduction = max(0, int(station_bonus or 0))
    skill_reduction = int(cooking_level_profile(total_batches)["time_reduction"])
    first_batch = max(minimum, base_minutes - station_reduction - skill_reduction)
    additional_batch = max(1, int(ceil(first_batch * 0.60)))
    return first_batch + additional_batch * (batches - 1)


def mastery_bonus_servings(previous_count: object, batch_count: object) -> int:
    """Award predictable bonus servings as a recipe becomes well practiced."""
    previous = max(0, int(previous_count or 0))
    batches = max(0, int(batch_count or 0))
    extras = 0
    for completed_count in range(previous + 1, previous + batches + 1):
        profile = recipe_mastery_profile(completed_count)
        interval = int(profile["bonus_interval"])
        if interval > 0 and completed_count % interval == 0:
            extras += 1
    return extras


__all__ = [
    "COOKING_LEVEL_THRESHOLDS",
    "RECIPE_MASTERY_THRESHOLDS",
    "cooking_level_profile",
    "cooking_time_minutes",
    "mastery_bonus_servings",
    "recipe_mastery_profile",
]
