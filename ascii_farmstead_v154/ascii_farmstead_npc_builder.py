from __future__ import annotations

"""Procedural settlement population foundations.

Generated residents remain isolated from the authored-town NPC roster. They
are deterministic, save-safe population records tied to completed wilderness
settlement buildings and can later be activated by a procedural town runtime.
"""

import copy
import random
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ascii_farmstead_town_builder import (
    SETTLEMENT_BUILDING_CATALOG,
    settlement_chunk_key,
)


PROCEDURAL_POPULATION_VERSION = 1
PROCEDURAL_AGE_GROUPS = ("Child", "Teen", "Adult", "Elder")
PROCEDURAL_SEXES = ("Female", "Male")
PROCEDURAL_ROUTINE_PHASES = (
    "wake",
    "work_morning",
    "lunch",
    "work_afternoon",
    "evening",
    "late",
    "bad_weather",
)
PROCEDURAL_PERSONALITY_TRAITS = (
    "Cheerful",
    "Reserved",
    "Practical",
    "Curious",
    "Patient",
    "Bold",
    "Gentle",
    "Wry",
    "Methodical",
    "Restless",
    "Hospitable",
    "Protective",
    "Calm",
)
PROCEDURAL_COLOR_NAMES = ("White", "Green", "Blue", "Yellow", "Purple", "Red", "Cyan")


FEMALE_GIVEN_NAMES = (
    "Ada", "Anya", "Bea", "Clara", "Della", "Elin", "Fern", "Greta",
    "Iris", "June", "Kaia", "Lena", "Mara", "Nell", "Opal", "Rhea",
    "Sora", "Talia", "Uma", "Vera", "Willa", "Yara", "Zoe", "Maeve",
)
MALE_GIVEN_NAMES = (
    "Alden", "Bram", "Cal", "Dorian", "Emmett", "Finnian", "Galen", "Hugh",
    "Ivo", "Jonas", "Kellan", "Leo", "Milo", "Noel", "Oren", "Perrin",
    "Reed", "Silas", "Tobin", "Ulric", "Vance", "Wes", "Yorin", "Zane",
)
SURNAMES = (
    "Ash", "Bell", "Briar", "Brook", "Cairn", "Dale", "Ember", "Fallow",
    "Grove", "Hearth", "Juniper", "Kestrel", "Lark", "Moss", "North", "Oak",
    "Pine", "Quill", "Reeve", "Stone", "Thorne", "Vale", "Ward", "Wren",
)


ROLE_PREFERENCE_DATA: Dict[str, Dict[str, object]] = {
    "Mayor": {
        "traits": ("Practical", "Patient", "Protective"),
        "likes": ("Honey", "Large Milk", "Wildflower", "Ancient Preserves"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Turn a collection of buildings into a dependable community.",
    },
    "Clerk": {
        "traits": ("Methodical", "Reserved", "Curious"),
        "likes": ("Maple", "Cave Herbs", "Wildflower", "Honey"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Keep records clear enough that no resident disappears between ledgers.",
    },
    "Well Keeper": {
        "traits": ("Patient", "Practical", "Wry"),
        "likes": ("Watercress", "Stone", "Wood", "Berries"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Keep the settlement supplied with clean water through every season.",
    },
    "Shopkeeper": {
        "traits": ("Cheerful", "Methodical", "Hospitable"),
        "likes": ("Carrot", "Tomato", "Corn", "Wildflower"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Stock the things residents need before they know they need them.",
    },
    "Stockkeeper": {
        "traits": ("Practical", "Methodical", "Reserved"),
        "likes": ("Wood", "Fiber", "Mixed Seeds", "Berries"),
        "dislikes": ("Trash", "Fish Bones"),
        "goal": "Make storage and deliveries reliable enough to survive bad weather.",
    },
    "Carpenter": {
        "traits": ("Practical", "Patient", "Methodical"),
        "likes": ("Wood", "Hardwood", "Fiber", "Soft Fiber"),
        "dislikes": ("Trash", "Fish Bones"),
        "goal": "Give every household sound walls, clear paths, and room to grow.",
    },
    "Carpenter Apprentice": {
        "traits": ("Curious", "Practical", "Restless"),
        "likes": ("Wood", "Stone", "Copper Bar", "Fiber"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Learn enough craft to build something that outlasts its maker.",
    },
    "Doctor": {
        "traits": ("Calm", "Methodical", "Protective"),
        "likes": ("Cave Herbs", "Watercress", "Honey", "Milk"),
        "dislikes": ("Bat Guano", "Strange Spores"),
        "goal": "Build a clinic routine that catches trouble before it becomes a crisis.",
    },
    "Nurse": {
        "traits": ("Gentle", "Patient", "Protective"),
        "likes": ("Cave Herbs", "Honey", "Wildflower", "Milk"),
        "dislikes": ("Bat Guano", "Trash"),
        "goal": "Make recovery feel ordinary, practical, and possible.",
    },
    "Librarian": {
        "traits": ("Reserved", "Curious", "Methodical"),
        "likes": ("Maple", "Cave Herbs", "Wildflower", "Ancient Preserves"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Preserve local knowledge before memory starts editing the details.",
    },
    "Archivist": {
        "traits": ("Curious", "Methodical", "Patient"),
        "likes": ("Maple", "Quartz", "Cave Herbs", "Wildflower"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Turn resident stories, routes, and weather notes into a usable archive.",
    },
    "Innkeeper": {
        "traits": ("Hospitable", "Cheerful", "Wry"),
        "likes": ("Woodland Salad", "Berries", "Honey", "Bird Egg"),
        "dislikes": ("Ore", "Coal"),
        "goal": "Make the inn the place where strangers become familiar faces.",
    },
    "Cook": {
        "traits": ("Bold", "Hospitable", "Methodical"),
        "likes": ("Carrot", "Tomato", "Corn", "Large Milk"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Build a menu that tastes like the settlement rather than anywhere else.",
    },
    "Merchant": {
        "traits": ("Cheerful", "Restless", "Wry"),
        "likes": ("Wildflower", "Berries", "Honey", "Soft Fiber"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Make the market worth the journey even on quiet weeks.",
    },
    "Mechanic": {
        "traits": ("Curious", "Practical", "Bold"),
        "likes": ("Crystal Shard", "Copper Bar", "Iron Bar", "Coal"),
        "dislikes": ("Trash", "Fish Bones"),
        "goal": "Make every useful mechanism safer, quieter, and easier to repair.",
    },
    "Artisan": {
        "traits": ("Curious", "Reserved", "Practical"),
        "likes": ("Soft Fiber", "Wildflower", "Maple", "Honey"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Give the settlement objects that are useful enough to keep and beautiful enough to notice.",
    },
    "Gardener": {
        "traits": ("Gentle", "Patient", "Curious"),
        "likes": ("Wildflower", "Watercress", "Berries", "Honey"),
        "dislikes": ("Ore", "Coal"),
        "goal": "Make public ground feel cared for rather than merely unclaimed.",
    },
    "Settler": {
        "traits": ("Practical", "Patient", "Curious"),
        "likes": ("Berries", "Wildflower", "Wood", "Honey"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Build a stable life in a place that is still learning its own name.",
    },
    "Student": {
        "traits": ("Curious", "Restless", "Cheerful"),
        "likes": ("Berries", "Wildflower", "Jam Toast", "Maple"),
        "dislikes": ("Bat Guano", "Trash"),
        "goal": "Learn enough about the settlement to imagine a place in its future.",
    },
    "Retiree": {
        "traits": ("Patient", "Wry", "Reserved"),
        "likes": ("Jam Toast", "Milk", "Berries", "Honey"),
        "dislikes": ("Trash", "Bat Guano"),
        "goal": "Keep useful stories and hard-won habits from being lost.",
    },
}


BUILDING_PROFESSION_SLOTS: Dict[str, Tuple[Dict[str, object], ...]] = {
    "town_hall": (
        {"role": "Mayor", "slot": "mayor", "priority": 0},
        {"role": "Clerk", "slot": "clerk", "priority": 4},
    ),
    "well": (
        {"role": "Well Keeper", "slot": "keeper", "priority": 8},
    ),
    "general_store": (
        {"role": "Shopkeeper", "slot": "shopkeeper", "priority": 1},
        {"role": "Stockkeeper", "slot": "stockkeeper", "priority": 7},
    ),
    "carpenter": (
        {"role": "Carpenter", "slot": "carpenter", "priority": 1},
        {"role": "Carpenter Apprentice", "slot": "apprentice", "priority": 7},
    ),
    "clinic": (
        {"role": "Doctor", "slot": "doctor", "priority": 1},
        {"role": "Nurse", "slot": "nurse", "priority": 5},
    ),
    "library": (
        {"role": "Librarian", "slot": "librarian", "priority": 2},
        {"role": "Archivist", "slot": "archivist", "priority": 7},
    ),
    "inn": (
        {"role": "Innkeeper", "slot": "innkeeper", "priority": 2},
        {"role": "Cook", "slot": "cook", "priority": 5},
    ),
    "market_stall": (
        {"role": "Merchant", "slot": "merchant", "priority": 3},
    ),
    "workshop": (
        {"role": "Mechanic", "slot": "mechanic", "priority": 3},
        {"role": "Artisan", "slot": "artisan", "priority": 6},
    ),
    "park": (
        {"role": "Gardener", "slot": "gardener", "priority": 6},
    ),
}


def procedural_population_key(chunk_x: int, chunk_y: int) -> str:
    return settlement_chunk_key(chunk_x, chunk_y)


def procedural_slug(value: object) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "resident"


def stable_text_seed(text: object) -> int:
    total = 2166136261
    for char in str(text):
        total ^= ord(char)
        total = (total * 16777619) & 0xFFFFFFFF
    return total


def procedural_completed_buildings(plan: Dict[str, object]) -> List[Dict[str, object]]:
    return [
        building
        for building in plan.get("buildings", {}).values()
        if isinstance(building, dict) and int(building.get("phase_index", 0)) >= 3
    ]


def procedural_building_anchor(building: Dict[str, object]) -> Dict[str, object]:
    return {
        "kind": "building",
        "building_id": str(building.get("id", "")),
        "building_name": str(building.get("name", "Building")),
        "x": int(building.get("door_x", building.get("x", 0))),
        "y": int(building.get("door_y", building.get("y", 0))),
    }


def procedural_outdoor_anchor(
    anchor: str,
    x: int,
    y: int,
    activity: str = "",
) -> Dict[str, object]:
    record = {
        "kind": "outdoor",
        "anchor": str(anchor),
        "x": int(x),
        "y": int(y),
    }
    if activity:
        record["activity"] = str(activity)
    return record


def sanitize_procedural_request(value: object) -> Dict[str, object]:
    if not isinstance(value, dict):
        return {}
    request_id = str(value.get("id", "") or "").strip()
    item = str(value.get("item", "") or "").strip()
    if not request_id or not item:
        return {}
    status = str(value.get("status", "active") or "active")
    if status not in {"active", "completed"}:
        status = "active"
    try:
        quantity = max(1, min(99, int(value.get("quantity", 1))))
        money = max(0, min(99999, int(value.get("reward_money", 0))))
        relationship = max(0, min(25, int(value.get("reward_relationship", 0))))
    except Exception:
        return {}
    return {
        "id": request_id,
        "title": str(value.get("title", "Resident Request") or "Resident Request")[:80],
        "description": str(value.get("description", "") or "")[:300],
        "item": item,
        "quantity": quantity,
        "reward_money": money,
        "reward_relationship": relationship,
        "created_day": str(value.get("created_day", "") or ""),
        "status": status,
    }


def sanitize_procedural_settlement_populations(value: object) -> Dict[str, Dict[str, object]]:
    if not isinstance(value, dict):
        return {}
    clean: Dict[str, Dict[str, object]] = {}
    for raw_key, raw_population in value.items():
        if not isinstance(raw_population, dict):
            continue
        try:
            cx_text, cy_text = str(raw_key).split(",", 1)
            chunk_x, chunk_y = int(cx_text), int(cy_text)
        except Exception:
            try:
                chunk_x = int(raw_population.get("chunk_x", 0))
                chunk_y = int(raw_population.get("chunk_y", 0))
            except Exception:
                continue
        key = procedural_population_key(chunk_x, chunk_y)
        households: Dict[str, Dict[str, object]] = {}
        for raw_household_id, raw_household in (
            raw_population.get("households", {}).items()
            if isinstance(raw_population.get("households"), dict)
            else []
        ):
            if not isinstance(raw_household, dict):
                continue
            household_id = str(raw_household_id or "").strip()
            home_id = str(raw_household.get("home_building_id", "") or "")
            if not household_id or not home_id:
                continue
            households[household_id] = {
                "id": household_id,
                "name": str(raw_household.get("name", "Household")),
                "surname": str(raw_household.get("surname", "")),
                "home_building_id": home_id,
                "capacity": max(1, int(raw_household.get("capacity", 1))),
                "member_ids": list(dict.fromkeys(
                    str(member_id)
                    for member_id in (
                        raw_household.get("member_ids", [])
                        if isinstance(raw_household.get("member_ids"), list)
                        else []
                    )
                    if str(member_id or "").strip()
                )),
                "household_style": str(raw_household.get("household_style", "Independent") or "Independent"),
                "head_resident_id": str(raw_household.get("head_resident_id", "") or ""),
                "guardian_ids": [
                    str(resident_id)
                    for resident_id in (
                        raw_household.get("guardian_ids", [])
                        if isinstance(raw_household.get("guardian_ids"), list)
                        else []
                    )
                    if str(resident_id or "").strip()
                ][:2],
            }

        residents: Dict[str, Dict[str, object]] = {}
        for raw_resident_id, raw_resident in (
            raw_population.get("residents", {}).items()
            if isinstance(raw_population.get("residents"), dict)
            else []
        ):
            if not isinstance(raw_resident, dict):
                continue
            resident_id = str(raw_resident_id or "").strip()
            household_id = str(raw_resident.get("household_id", "") or "")
            home_id = str(raw_resident.get("home_building_id", "") or "")
            if not resident_id or household_id not in households or not home_id:
                continue
            age_group = str(raw_resident.get("age_group", "Adult") or "Adult")
            if age_group not in PROCEDURAL_AGE_GROUPS:
                age_group = "Adult"
            sex = str(raw_resident.get("sex", "Female") or "Female")
            if sex not in PROCEDURAL_SEXES:
                sex = "Female"
            schedule: Dict[str, Dict[str, object]] = {}
            raw_schedule = raw_resident.get("schedule", {})
            if isinstance(raw_schedule, dict):
                for phase in PROCEDURAL_ROUTINE_PHASES:
                    entry = raw_schedule.get(phase)
                    if not isinstance(entry, dict):
                        continue
                    kind = str(entry.get("kind", "building") or "building")
                    if kind == "building":
                        building_id = str(entry.get("building_id", "") or "")
                        if not building_id:
                            continue
                        clean_entry = {
                            "kind": "building",
                            "building_id": building_id,
                            "building_name": str(entry.get("building_name", "Building")),
                            "x": int(entry.get("x", 0)),
                            "y": int(entry.get("y", 0)),
                        }
                    else:
                        clean_entry = {
                            "kind": "outdoor",
                            "anchor": str(entry.get("anchor", "road")),
                            "x": int(entry.get("x", 0)),
                            "y": int(entry.get("y", 0)),
                        }
                    clean_entry["activity"] = str(entry.get("activity", "") or "")
                    schedule[phase] = clean_entry
            traits = list(dict.fromkeys(
                str(trait)
                for trait in (
                    raw_resident.get("personality_traits", [])
                    if isinstance(raw_resident.get("personality_traits"), list)
                    else []
                )
                if str(trait or "").strip()
            ))[:3]
            residents[resident_id] = {
                "id": resident_id,
                "origin_key": str(raw_resident.get("origin_key", resident_id)),
                "name": str(raw_resident.get("name", "Resident")),
                "given_name": str(raw_resident.get("given_name", "")),
                "surname": str(raw_resident.get("surname", "")),
                "symbol": "@",
                "color": str(raw_resident.get("color", "White")),
                "sex": sex,
                "age_group": age_group,
                "age_years": max(5, min(95, int(raw_resident.get("age_years", 30)))),
                "birthday_month": max(1, min(12, int(raw_resident.get("birthday_month", 3)))),
                "birthday_day": max(1, min(31, int(raw_resident.get("birthday_day", 1)))),
                "role": str(raw_resident.get("role", "Settler")),
                "profession_id": str(raw_resident.get("profession_id", "settler")),
                "household_id": household_id,
                "household_role": str(raw_resident.get("household_role", "Resident") or "Resident"),
                "home_building_id": home_id,
                "workplace_building_id": str(raw_resident.get("workplace_building_id", "") or ""),
                "family_member_ids": [
                    str(family_id)
                    for family_id in (
                        raw_resident.get("family_member_ids", [])
                        if isinstance(raw_resident.get("family_member_ids"), list)
                        else []
                    )
                    if str(family_id or "").strip()
                ],
                "guardian_ids": [
                    str(guardian_id)
                    for guardian_id in (
                        raw_resident.get("guardian_ids", [])
                        if isinstance(raw_resident.get("guardian_ids"), list)
                        else []
                    )
                    if str(guardian_id or "").strip()
                ][:2],
                "dependent_ids": [
                    str(dependent_id)
                    for dependent_id in (
                        raw_resident.get("dependent_ids", [])
                        if isinstance(raw_resident.get("dependent_ids"), list)
                        else []
                    )
                    if str(dependent_id or "").strip()
                ],
                "personality_traits": traits or ["Practical", "Patient"],
                "personality": str(raw_resident.get("personality", ", ".join(traits) or "Practical, Patient")),
                "goal": str(raw_resident.get("goal", "Build a stable life in the settlement.")),
                "rumor": str(raw_resident.get("rumor", "The settlement changes a little every week.")),
                "friend_secret": str(raw_resident.get("friend_secret", "They are still deciding what home means here.")),
                "likes": [
                    str(item)
                    for item in (
                        raw_resident.get("likes", [])
                        if isinstance(raw_resident.get("likes"), list)
                        else []
                    )
                    if str(item or "").strip()
                ][:6],
                "dislikes": [
                    str(item)
                    for item in (
                        raw_resident.get("dislikes", [])
                        if isinstance(raw_resident.get("dislikes"), list)
                        else []
                    )
                    if str(item or "").strip()
                ][:4],
                "dialogue_tags": [
                    str(tag)
                    for tag in (
                        raw_resident.get("dialogue_tags", [])
                        if isinstance(raw_resident.get("dialogue_tags"), list)
                        else []
                    )
                    if str(tag or "").strip()
                ][:8],
                "social_connections": copy.deepcopy(
                    raw_resident.get("social_connections", {})
                    if isinstance(raw_resident.get("social_connections"), dict)
                    else {}
                ),
                "social_opinion": str(raw_resident.get("social_opinion", "") or ""),
                "schedule": schedule,
                "relationship": max(-50, min(250, int(raw_resident.get("relationship", 0)))),
                "met": bool(raw_resident.get("met", False)),
                "dialogue_count": max(0, int(raw_resident.get("dialogue_count", 0))),
                "recent_dialogue_ids": [
                    str(line_id)
                    for line_id in (
                        raw_resident.get("recent_dialogue_ids", [])
                        if isinstance(raw_resident.get("recent_dialogue_ids"), list)
                        else []
                    )
                    if str(line_id or "").strip()
                ][-10:],
                "last_talk_day": str(raw_resident.get("last_talk_day", "") or ""),
                "last_dialogue_topic": str(raw_resident.get("last_dialogue_topic", "") or ""),
                "last_gift_day": str(raw_resident.get("last_gift_day", "") or ""),
                "recent_gifts": [
                    str(item)
                    for item in (
                        raw_resident.get("recent_gifts", [])
                        if isinstance(raw_resident.get("recent_gifts"), list)
                        else []
                    )
                    if str(item or "").strip()
                ][-8:],
                "conversation_flags": list(dict.fromkeys(
                    str(flag)
                    for flag in (
                        raw_resident.get("conversation_flags", [])
                        if isinstance(raw_resident.get("conversation_flags"), list)
                        else []
                    )
                    if str(flag or "").strip()
                ))[-40:],
                "memories": [
                    str(memory)
                    for memory in (
                        raw_resident.get("memories", [])
                        if isinstance(raw_resident.get("memories"), list)
                        else []
                    )
                    if str(memory or "").strip()
                ][-16:],
                "active_request": sanitize_procedural_request(
                    raw_resident.get("active_request", {})
                ),
                "completed_request_ids": list(dict.fromkeys(
                    str(request_id)
                    for request_id in (
                        raw_resident.get("completed_request_ids", [])
                        if isinstance(raw_resident.get("completed_request_ids"), list)
                        else []
                    )
                    if str(request_id or "").strip()
                ))[-20:],
                "last_request_day": str(raw_resident.get("last_request_day", "") or ""),
                "runtime_x": int(raw_resident.get("runtime_x", -1) or -1),
                "runtime_y": int(raw_resident.get("runtime_y", -1) or -1),
                "runtime_location": str(raw_resident.get("runtime_location", "") or ""),
                "runtime_phase": str(raw_resident.get("runtime_phase", "") or ""),
                "runtime_day_key": str(raw_resident.get("runtime_day_key", "") or ""),
                "runtime_weather": str(raw_resident.get("runtime_weather", "") or ""),
                "runtime_activity": str(raw_resident.get("runtime_activity", "") or ""),
                "runtime_facing": str(raw_resident.get("runtime_facing", "DOWN") or "DOWN"),
                "runtime_steps_today": max(0, int(raw_resident.get("runtime_steps_today", 0) or 0)),
                "romanceable": age_group in {"Adult", "Elder"},
                "active": bool(raw_resident.get("active", True)),
            }

        valid_resident_ids = set(residents)
        for household in households.values():
            household["member_ids"] = [
                member_id
                for member_id in household["member_ids"]
                if member_id in valid_resident_ids
            ]
            household["head_resident_id"] = (
                household["head_resident_id"]
                if household["head_resident_id"] in household["member_ids"]
                else (household["member_ids"][0] if household["member_ids"] else "")
            )
            household["guardian_ids"] = [
                resident_id
                for resident_id in household["guardian_ids"]
                if resident_id in household["member_ids"]
            ][:2]
        for resident in residents.values():
            household_members = set(
                households.get(resident["household_id"], {}).get("member_ids", [])
            )
            resident["family_member_ids"] = [
                resident_id
                for resident_id in resident["family_member_ids"]
                if resident_id in household_members and resident_id != resident["id"]
            ]
            resident["guardian_ids"] = [
                resident_id
                for resident_id in resident["guardian_ids"]
                if resident_id in household_members and resident_id != resident["id"]
            ][:2]
            resident["dependent_ids"] = [
                resident_id
                for resident_id in resident["dependent_ids"]
                if resident_id in household_members and resident_id != resident["id"]
            ]
        clean[key] = {
            "version": PROCEDURAL_POPULATION_VERSION,
            "id": str(raw_population.get("id", f"population:{key}")),
            "settlement_id": str(raw_population.get("settlement_id", f"settlement:{key}")),
            "settlement_name": str(raw_population.get("settlement_name", f"Settlement {key}")),
            "chunk_x": chunk_x,
            "chunk_y": chunk_y,
            "seed": int(raw_population.get("seed", 0)),
            "source_revision": max(0, int(raw_population.get("source_revision", 0))),
            "generation": max(1, int(raw_population.get("generation", 1))),
            "status": str(raw_population.get("status", "planned") or "planned"),
            "households": households,
            "residents": residents,
            "job_vacancies": [
                str(value)
                for value in (
                    raw_population.get("job_vacancies", [])
                    if isinstance(raw_population.get("job_vacancies"), list)
                    else []
                )
                if str(value or "").strip()
            ],
            "departed_resident_ids": list(dict.fromkeys(
                str(value)
                for value in (
                    raw_population.get("departed_resident_ids", [])
                    if isinstance(raw_population.get("departed_resident_ids"), list)
                    else []
                )
                if str(value or "").strip()
            ))[-80:],
            "notes": [
                str(value)
                for value in (
                    raw_population.get("notes", [])
                    if isinstance(raw_population.get("notes"), list)
                    else []
                )
                if str(value or "").strip()
            ][-20:],
        }
    return clean


class ProceduralNpcBuilder:
    """Generate and reconcile settlement residents from completed buildings."""

    def completed_building_map(self, plan: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        return {
            str(building["id"]): building
            for building in procedural_completed_buildings(plan)
        }

    def residence_buildings(self, plan: Dict[str, object]) -> List[Dict[str, object]]:
        residences = []
        for building in procedural_completed_buildings(plan):
            catalog = SETTLEMENT_BUILDING_CATALOG.get(str(building.get("type_id")), {})
            if int(catalog.get("capacity", 0)) > 0:
                residences.append(building)
        return sorted(residences, key=lambda row: (int(row.get("priority", 0)), str(row.get("id", ""))))

    def profession_slots(self, plan: Dict[str, object]) -> List[Dict[str, object]]:
        slots: List[Dict[str, object]] = []
        for building in procedural_completed_buildings(plan):
            building_id = str(building.get("id", ""))
            type_id = str(building.get("type_id", ""))
            for definition in BUILDING_PROFESSION_SLOTS.get(type_id, ()):
                slot_id = str(definition["slot"])
                slots.append({
                    "origin_key": f"job:{building_id}:{slot_id}",
                    "building_id": building_id,
                    "building_name": str(building.get("name", SETTLEMENT_BUILDING_CATALOG.get(type_id, {}).get("name", "Workplace"))),
                    "building_type": type_id,
                    "role": str(definition["role"]),
                    "profession_id": f"{type_id}:{slot_id}",
                    "priority": int(definition.get("priority", 5)),
                })
        return sorted(slots, key=lambda row: (int(row["priority"]), str(row["origin_key"])))

    def settlement_anchors(self, plan: Dict[str, object]) -> Dict[str, Tuple[int, int]]:
        entrance = plan.get("entrance", {})
        entrance_pos = (int(entrance.get("x", 1)), int(entrance.get("y", 1)))
        roads = []
        for value in plan.get("roads", []) if isinstance(plan.get("roads"), list) else []:
            try:
                x_text, y_text = str(value).split(",", 1)
                roads.append((int(x_text), int(y_text)))
            except Exception:
                continue
        if roads:
            center = (int(plan.get("width", 86)) // 2, int(plan.get("height", 38)) // 2)
            square = min(roads, key=lambda pos: abs(pos[0] - center[0]) + abs(pos[1] - center[1]))
        else:
            square = entrance_pos
        completed = self.completed_building_map(plan)
        green = next(
            (
                (int(building.get("door_x", square[0])), int(building.get("door_y", square[1])))
                for building in completed.values()
                if str(building.get("type_id")) == "park"
            ),
            square,
        )
        market = next(
            (
                (int(building.get("door_x", square[0])), int(building.get("door_y", square[1])))
                for building in completed.values()
                if str(building.get("type_id")) in {"market_stall", "general_store"}
            ),
            square,
        )
        well = next(
            (
                (int(building.get("door_x", square[0])), int(building.get("door_y", square[1])))
                for building in completed.values()
                if str(building.get("type_id")) == "well"
            ),
            square,
        )
        return {
            "entrance": entrance_pos,
            "town_square": square,
            "green": green,
            "market": market,
            "well": well,
        }

    def deterministic_rng(self, plan: Dict[str, object], origin_key: str) -> random.Random:
        return random.Random(int(plan.get("seed", 0)) + stable_text_seed(origin_key))

    def household_surname(self, plan: Dict[str, object], home_id: str) -> str:
        rng = self.deterministic_rng(plan, f"household:{home_id}")
        return str(SURNAMES[rng.randrange(len(SURNAMES))])

    def choose_given_name(self, plan: Dict[str, object], origin_key: str, sex: str) -> str:
        pool = FEMALE_GIVEN_NAMES if sex == "Female" else MALE_GIVEN_NAMES
        rng = self.deterministic_rng(plan, f"name:{origin_key}")
        return str(pool[rng.randrange(len(pool))])

    def choose_age(self, plan: Dict[str, object], origin_key: str, age_group: str) -> int:
        ranges = {
            "Child": (7, 12),
            "Teen": (13, 17),
            "Adult": (20, 62),
            "Elder": (63, 88),
        }
        low, high = ranges.get(age_group, ranges["Adult"])
        rng = self.deterministic_rng(plan, f"age:{origin_key}")
        return rng.randint(low, high)

    def choose_traits(self, plan: Dict[str, object], origin_key: str, role: str) -> List[str]:
        rng = self.deterministic_rng(plan, f"traits:{origin_key}")
        preferred = list(ROLE_PREFERENCE_DATA.get(role, ROLE_PREFERENCE_DATA["Settler"]).get("traits", ()))
        pool = list(dict.fromkeys(preferred + list(PROCEDURAL_PERSONALITY_TRAITS)))
        traits: List[str] = []
        while pool and len(traits) < 3:
            if preferred and len(traits) < 2:
                trait = preferred.pop(rng.randrange(len(preferred)))
                if trait in pool:
                    pool.remove(trait)
            else:
                trait = pool.pop(rng.randrange(len(pool)))
            if trait not in traits:
                traits.append(trait)
        return traits

    def resident_schedule(
        self,
        plan: Dict[str, object],
        resident: Dict[str, object],
        buildings: Dict[str, Dict[str, object]],
    ) -> Dict[str, Dict[str, object]]:
        home = buildings[str(resident["home_building_id"])]
        home_entry = procedural_building_anchor(home)
        home_entry["activity"] = "starting the day at home"
        workplace_id = str(resident.get("workplace_building_id", "") or "")
        workplace = buildings.get(workplace_id)
        work_entry = procedural_building_anchor(workplace) if workplace else copy.deepcopy(home_entry)
        role = str(resident.get("role", "Settler"))
        work_entry["activity"] = {
            "Mayor": "reviewing civic work and resident concerns",
            "Clerk": "updating permits, schedules, and settlement records",
            "Well Keeper": "checking the public well and water stores",
            "Shopkeeper": "opening the store and arranging daily stock",
            "Stockkeeper": "sorting deliveries and counting supplies",
            "Carpenter": "measuring repairs and preparing building work",
            "Carpenter Apprentice": "learning joinery and carrying project materials",
            "Doctor": "seeing patients and checking clinic supplies",
            "Nurse": "preparing remedies and monitoring recovery",
            "Librarian": "cataloguing books and helping readers",
            "Archivist": "recording routes, weather, and settlement history",
            "Innkeeper": "preparing rooms and listening for useful news",
            "Cook": "preparing meals from local ingredients",
            "Merchant": "setting out market goods and talking prices",
            "Mechanic": "repairing tools and testing mechanisms",
            "Artisan": "working on practical household crafts",
            "Gardener": "tending paths, shade, and public planting",
            "Student": "studying settlement routines and local skills",
            "Retiree": "keeping a patient eye on the settlement",
        }.get(role, "helping with the work that keeps the settlement running")
        anchors = self.settlement_anchors(plan)
        age_group = str(resident.get("age_group", "Adult"))
        if age_group in {"Child", "Teen"}:
            library = next(
                (building for building in buildings.values() if str(building.get("type_id")) == "library"),
                None,
            )
            if library:
                work_entry = procedural_building_anchor(library)
                work_entry["activity"] = "studying and helping with simple library tasks"
            else:
                work_entry = procedural_outdoor_anchor(
                    "town_square",
                    *anchors["town_square"],
                    activity="learning through errands and observation",
                )
        lunch_anchor = anchors["green"] if age_group in {"Child", "Teen"} else anchors["town_square"]
        evening_anchor = anchors["market"] if role in {"Merchant", "Shopkeeper", "Innkeeper", "Cook"} else anchors["green"]
        return {
            "wake": {
                **procedural_building_anchor(home),
                "activity": "waking up at home",
            },
            "work_morning": copy.deepcopy(work_entry),
            "lunch": procedural_outdoor_anchor(
                "green" if lunch_anchor == anchors["green"] else "town_square",
                *lunch_anchor,
                activity="taking a midday break and checking in with neighbors",
            ),
            "work_afternoon": copy.deepcopy(work_entry),
            "evening": procedural_outdoor_anchor(
                "market" if evening_anchor == anchors["market"] else "green",
                *evening_anchor,
                activity="spending the evening among familiar faces",
            ),
            "late": {
                **procedural_building_anchor(home),
                "activity": "sleeping at home",
            },
            "bad_weather": {
                **(procedural_building_anchor(workplace) if workplace else procedural_building_anchor(home)),
                "activity": "keeping to an indoor weather-safe routine",
            },
        }

    def create_resident(
        self,
        plan: Dict[str, object],
        origin_key: str,
        household_id: str,
        home: Dict[str, object],
        surname: str,
        role: str,
        profession_id: str,
        workplace: Optional[Dict[str, object]],
        age_group: str = "Adult",
    ) -> Dict[str, object]:
        rng = self.deterministic_rng(plan, f"resident:{origin_key}")
        sex = PROCEDURAL_SEXES[rng.randrange(len(PROCEDURAL_SEXES))]
        given_name = self.choose_given_name(plan, origin_key, sex)
        traits = self.choose_traits(plan, origin_key, role)
        preferences = ROLE_PREFERENCE_DATA.get(role, ROLE_PREFERENCE_DATA["Settler"])
        resident_id = f"proc:{settlement_chunk_key(int(plan['chunk_x']), int(plan['chunk_y']))}:{procedural_slug(origin_key)}"
        birthday_month = rng.randint(1, 12)
        birthday_day = rng.randint(1, 28)
        resident = {
            "id": resident_id,
            "origin_key": origin_key,
            "name": f"{given_name} {surname}",
            "given_name": given_name,
            "surname": surname,
            "symbol": "@",
            "color": PROCEDURAL_COLOR_NAMES[rng.randrange(len(PROCEDURAL_COLOR_NAMES))],
            "sex": sex,
            "age_group": age_group,
            "age_years": self.choose_age(plan, origin_key, age_group),
            "birthday_month": birthday_month,
            "birthday_day": birthday_day,
            "role": role,
            "profession_id": profession_id,
            "household_id": household_id,
            "household_role": "Resident",
            "home_building_id": str(home["id"]),
            "workplace_building_id": str(workplace["id"]) if workplace else "",
            "family_member_ids": [],
            "guardian_ids": [],
            "dependent_ids": [],
            "personality_traits": traits,
            "personality": ", ".join(traits),
            "goal": str(preferences.get("goal", ROLE_PREFERENCE_DATA["Settler"]["goal"])),
            "rumor": self.generated_rumor(plan, role, workplace),
            "friend_secret": self.generated_secret(role, traits),
            "likes": list(preferences.get("likes", ()))[:4],
            "dislikes": list(preferences.get("dislikes", ()))[:2],
            "dialogue_tags": list(dict.fromkeys([
                procedural_slug(role),
                procedural_slug(age_group),
                *[procedural_slug(trait) for trait in traits],
                procedural_slug(str(workplace.get("type_id", "home"))) if workplace else "home",
            ])),
            "social_connections": {},
            "social_opinion": "",
            "schedule": {},
            "relationship": 0,
            "met": False,
            "dialogue_count": 0,
            "recent_dialogue_ids": [],
            "last_talk_day": "",
            "last_dialogue_topic": "",
            "last_gift_day": "",
            "recent_gifts": [],
            "conversation_flags": [],
            "memories": [],
            "active_request": {},
            "completed_request_ids": [],
            "last_request_day": "",
            "runtime_x": -1,
            "runtime_y": -1,
            "runtime_location": "",
            "runtime_phase": "",
            "runtime_day_key": "",
            "runtime_weather": "",
            "runtime_activity": "",
            "runtime_facing": "DOWN",
            "runtime_steps_today": 0,
            "romanceable": age_group in {"Adult", "Elder"},
            "active": True,
        }
        return resident

    def ensure_unique_resident_name(
        self,
        resident: Dict[str, object],
        residents: Dict[str, Dict[str, object]],
        plan: Dict[str, object],
        origin_key: str,
    ) -> None:
        existing_names = {
            str(existing.get("name", "")).casefold()
            for existing in residents.values()
        }
        if str(resident.get("name", "")).casefold() not in existing_names:
            return
        pool = (
            FEMALE_GIVEN_NAMES
            if str(resident.get("sex", "Female")) == "Female"
            else MALE_GIVEN_NAMES
        )
        surname = str(resident.get("surname", ""))
        start = stable_text_seed(
            f"{plan.get('seed', 0)}:{origin_key}:unique-name"
        ) % len(pool)
        for offset in range(len(pool)):
            given_name = pool[(start + offset) % len(pool)]
            full_name = f"{given_name} {surname}"
            if full_name.casefold() in existing_names:
                continue
            resident["given_name"] = given_name
            resident["name"] = full_name
            return

    def generated_rumor(
        self,
        plan: Dict[str, object],
        role: str,
        workplace: Optional[Dict[str, object]],
    ) -> str:
        settlement_name = str(plan.get("name", "the settlement"))
        place = str(workplace.get("name", "the main road")) if workplace else "the main road"
        return {
            "Mayor": f"People say {settlement_name} will feel real once the first difficult winter is behind it.",
            "Doctor": f"The clinic keeps a list of supplies that {settlement_name} cannot produce reliably yet.",
            "Librarian": f"The earliest map of {settlement_name} already disagrees with the roads people actually use.",
            "Innkeeper": f"Travelers at {place} keep asking whether the road continues beyond the settlement.",
            "Merchant": f"Market prices shift whenever a wilderness route becomes safer or more dangerous.",
            "Carpenter": f"Several foundations in {settlement_name} were adjusted after the first heavy rain.",
        }.get(role, f"Someone near {place} has been talking about what {settlement_name} should build next.")

    def generated_secret(self, role: str, traits: Iterable[str]) -> str:
        trait_text = ", ".join(str(trait).lower() for trait in list(traits)[:2])
        return {
            "Mayor": "They worry that every new promise creates another resident who can be disappointed.",
            "Doctor": "They keep private notes about which remedies are running low.",
            "Innkeeper": "They can usually tell who plans to stay before the traveler admits it.",
            "Carpenter": "They have already sketched an expansion nobody has approved.",
            "Librarian": "They preserve discarded drafts because mistakes reveal how the settlement learned.",
        }.get(role, f"Beneath their {trait_text} manner, they are still deciding whether this place can become permanent.")

    def household_style(self, member_count: int, has_children: bool, is_inn: bool) -> str:
        if is_inn:
            return "Lodging"
        if has_children:
            return "Family"
        if member_count > 1:
            return "Shared Home"
        return "Independent"

    def create_population(
        self,
        plan: Dict[str, object],
        existing: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        key = settlement_chunk_key(int(plan["chunk_x"]), int(plan["chunk_y"]))
        buildings = self.completed_building_map(plan)
        residences = self.residence_buildings(plan)
        profession_slots = self.profession_slots(plan)
        population: Dict[str, object] = {
            "version": PROCEDURAL_POPULATION_VERSION,
            "id": f"population:{key}",
            "settlement_id": str(plan.get("id", f"settlement:{key}")),
            "settlement_name": str(plan.get("name", f"Settlement {key}")),
            "chunk_x": int(plan["chunk_x"]),
            "chunk_y": int(plan["chunk_y"]),
            "seed": int(plan.get("seed", 0)) + 700001,
            "source_revision": int(plan.get("revision", 0)),
            "generation": max(1, int((existing or {}).get("generation", 0)) + 1),
            "status": "planned" if residences else "awaiting_housing",
            "households": {},
            "residents": {},
            "job_vacancies": [],
            "departed_resident_ids": list((existing or {}).get("departed_resident_ids", []) or []),
            "notes": ["Population plan generated separately from the authored town NPC roster."],
        }
        if not residences:
            population["job_vacancies"] = [str(slot["origin_key"]) for slot in profession_slots]
            return population

        household_order: List[str] = []
        household_capacity: Dict[str, int] = {}
        for home in residences:
            home_id = str(home["id"])
            catalog = SETTLEMENT_BUILDING_CATALOG.get(str(home.get("type_id")), {})
            capacity = max(1, int(catalog.get("capacity", 1)))
            household_id = f"household:{key}:{procedural_slug(home_id)}"
            surname = self.household_surname(plan, home_id)
            population["households"][household_id] = {
                "id": household_id,
                "name": f"{surname} Household",
                "surname": surname,
                "home_building_id": home_id,
                "capacity": capacity,
                "member_ids": [],
                "household_style": "Independent",
                "head_resident_id": "",
                "guardian_ids": [],
            }
            household_order.append(household_id)
            household_capacity[household_id] = capacity

        assignments: List[Tuple[Dict[str, object], str]] = []
        household_index = 0
        for slot in profession_slots:
            checked = 0
            selected = ""
            while checked < len(household_order):
                household_id = household_order[household_index % len(household_order)]
                household_index += 1
                checked += 1
                if len(population["households"][household_id]["member_ids"]) < household_capacity[household_id]:
                    selected = household_id
                    break
            if not selected:
                population["job_vacancies"].append(str(slot["origin_key"]))
                continue
            assignments.append((slot, selected))
            population["households"][selected]["member_ids"].append("__reserved__")

        # Guarantee a founding adult in every completed residence.
        for household_id in household_order:
            household = population["households"][household_id]
            if not household["member_ids"]:
                slot = {
                    "origin_key": f"resident:{household['home_building_id']}:founder",
                    "building_id": "",
                    "role": "Settler",
                    "profession_id": "settler",
                }
                assignments.append((slot, household_id))
                household["member_ids"].append("__reserved__")

        for slot, household_id in assignments:
            household = population["households"][household_id]
            home = buildings[str(household["home_building_id"])]
            workplace = buildings.get(str(slot.get("building_id", "")))
            resident = self.create_resident(
                plan,
                str(slot["origin_key"]),
                household_id,
                home,
                str(household["surname"]),
                str(slot["role"]),
                str(slot.get("profession_id", procedural_slug(slot["role"]))),
                workplace,
                age_group="Adult",
            )
            self.ensure_unique_resident_name(
                resident,
                population["residents"],
                plan,
                str(slot["origin_key"]),
            )
            resident["schedule"] = self.resident_schedule(plan, resident, buildings)
            population["residents"][resident["id"]] = resident
            reserved_index = household["member_ids"].index("__reserved__")
            household["member_ids"][reserved_index] = resident["id"]

        # Fill a portion of spare housing with deterministic family members.
        # Reserve a small demographic cross-section when the settlement has room;
        # otherwise job-heavy starter layouts tend to become adults-only.
        dependent_targets: Dict[str, int] = {}
        total_spare_beds = 0
        for household_id in household_order:
            household = population["households"][household_id]
            home_id = str(household["home_building_id"])
            capacity = int(household["capacity"])
            current = len(household["member_ids"])
            total_spare_beds += max(0, capacity - current)
            if current >= capacity:
                dependent_targets[household_id] = current
                continue
            rng = self.deterministic_rng(plan, f"dependents:{home_id}")
            desired = min(capacity, current + rng.randint(0, min(2, capacity - current)))
            if current == 1 and capacity >= 2 and rng.random() < 0.7:
                desired = max(desired, 2)
            dependent_targets[household_id] = desired

        minimum_dependents = min(3, total_spare_beds)
        planned_dependents = sum(
            max(0, dependent_targets[household_id] - len(population["households"][household_id]["member_ids"]))
            for household_id in household_order
        )
        while planned_dependents < minimum_dependents:
            changed = False
            for household_id in household_order:
                household = population["households"][household_id]
                if dependent_targets[household_id] >= int(household["capacity"]):
                    continue
                dependent_targets[household_id] += 1
                planned_dependents += 1
                changed = True
                if planned_dependents >= minimum_dependents:
                    break
            if not changed:
                break

        demographic_cycle = ["Child", "Teen", "Elder"]
        demographic_rng = self.deterministic_rng(plan, "dependent-demographics")
        demographic_rng.shuffle(demographic_cycle)
        demographic_cycle.append("Adult")
        dependent_number = 0
        for household_id in household_order:
            household = population["households"][household_id]
            home_id = str(household["home_building_id"])
            home = buildings[home_id]
            current = len(household["member_ids"])
            desired = dependent_targets[household_id]
            for index in range(current, desired):
                age_group = demographic_cycle[dependent_number % len(demographic_cycle)]
                dependent_number += 1
                role = "Student" if age_group in {"Child", "Teen"} else (
                    "Retiree" if age_group == "Elder" else "Settler"
                )
                origin_key = f"resident:{home_id}:dependent:{index}"
                resident = self.create_resident(
                    plan,
                    origin_key,
                    household_id,
                    home,
                    str(household["surname"]),
                    role,
                    procedural_slug(role),
                    None,
                    age_group=age_group,
                )
                self.ensure_unique_resident_name(
                    resident,
                    population["residents"],
                    plan,
                    origin_key,
                )
                resident["schedule"] = self.resident_schedule(plan, resident, buildings)
                population["residents"][resident["id"]] = resident
                household["member_ids"].append(resident["id"])

        existing_clean = sanitize_procedural_settlement_populations(
            {key: existing}
        ).get(key) if existing else None
        if existing_clean:
            old_residents = existing_clean.get("residents", {})
            for resident_id, resident in population["residents"].items():
                old = old_residents.get(resident_id)
                if not isinstance(old, dict):
                    continue
                for field in (
                    "relationship",
                    "met",
                    "dialogue_count",
                    "recent_dialogue_ids",
                    "last_talk_day",
                    "last_dialogue_topic",
                    "last_gift_day",
                    "recent_gifts",
                    "conversation_flags",
                    "memories",
                    "active_request",
                    "completed_request_ids",
                    "last_request_day",
                    "runtime_x",
                    "runtime_y",
                    "runtime_location",
                    "runtime_phase",
                    "runtime_day_key",
                    "runtime_weather",
                    "runtime_activity",
                    "runtime_facing",
                    "runtime_steps_today",
                    "romanceable",
                    "social_connections",
                    "social_opinion",
                ):
                    resident[field] = copy.deepcopy(old.get(field, resident[field]))
            departed = [
                resident_id
                for resident_id in old_residents
                if resident_id not in population["residents"]
            ]
            population["departed_resident_ids"] = list(dict.fromkeys(
                list(existing_clean.get("departed_resident_ids", [])) + departed
            ))[-80:]

        for household in population["households"].values():
            members = [
                population["residents"][resident_id]
                for resident_id in household["member_ids"]
                if resident_id in population["residents"]
            ]
            has_young = any(
                member["age_group"] in {"Child", "Teen"}
                for member in members
            )
            household["household_style"] = self.household_style(
                len(members),
                has_young,
                str(buildings[household["home_building_id"]].get("type_id")) == "inn",
            )
            adults = [member for member in members if member["age_group"] == "Adult"]
            head = (adults or [member for member in members if member["age_group"] == "Elder"] or members)
            head_id = str(head[0]["id"]) if head else ""
            guardian_ids = [str(member["id"]) for member in adults[:2]] if has_young else []
            dependent_ids = [
                str(member["id"])
                for member in members
                if member["age_group"] in {"Child", "Teen"}
            ]
            household["head_resident_id"] = head_id
            household["guardian_ids"] = guardian_ids
            family_household = household["household_style"] == "Family"
            member_ids = [str(member["id"]) for member in members]
            partner_assigned = False
            for member in members:
                member_id = str(member["id"])
                age_group = str(member["age_group"])
                if member_id == head_id:
                    household_role = "Head"
                elif age_group == "Child":
                    household_role = "Child"
                elif age_group == "Teen":
                    household_role = "Teen"
                elif age_group == "Elder":
                    household_role = "Elder Relative" if family_household else "Housemate"
                elif family_household and not partner_assigned:
                    household_role = "Partner"
                    partner_assigned = True
                else:
                    household_role = "Adult Relative" if family_household else "Housemate"
                member["household_role"] = household_role
                member["family_member_ids"] = (
                    [other_id for other_id in member_ids if other_id != member_id]
                    if family_household
                    else []
                )
                member["guardian_ids"] = (
                    [guardian_id for guardian_id in guardian_ids if guardian_id != member_id]
                    if age_group in {"Child", "Teen"}
                    else []
                )
                member["dependent_ids"] = (
                    list(dependent_ids)
                    if member_id in guardian_ids
                    else []
                )
        population["status"] = "populated" if population["residents"] else "awaiting_residents"
        return population

    def validate(
        self,
        population: Dict[str, object],
        plan: Dict[str, object],
    ) -> Dict[str, List[str]]:
        errors: List[str] = []
        warnings: List[str] = []
        buildings = self.completed_building_map(plan)
        households = population.get("households", {})
        residents = population.get("residents", {})
        seen_members: Set[str] = set()
        names: Set[str] = set()
        for household_id, household in households.items():
            home_id = str(household.get("home_building_id", ""))
            if home_id not in buildings:
                errors.append(f"Household {household_id} references unavailable housing.")
                continue
            catalog = SETTLEMENT_BUILDING_CATALOG.get(str(buildings[home_id].get("type_id")), {})
            capacity = int(catalog.get("capacity", 0))
            member_ids = list(household.get("member_ids", []) or [])
            if len(member_ids) > capacity:
                errors.append(f"Household {household.get('name')} exceeds housing capacity.")
            head_id = str(household.get("head_resident_id", "") or "")
            if member_ids and head_id not in member_ids:
                errors.append(f"Household {household.get('name')} has no valid head resident.")
            for resident_id in member_ids:
                if resident_id in seen_members:
                    errors.append(f"Resident {resident_id} appears in multiple households.")
                seen_members.add(resident_id)
                if resident_id not in residents:
                    errors.append(f"Household {household.get('name')} references a missing resident.")
        for resident_id, resident in residents.items():
            if str(resident.get("household_id", "")) not in households:
                errors.append(f"Resident {resident_id} has no valid household.")
            if str(resident.get("home_building_id", "")) not in buildings:
                errors.append(f"Resident {resident_id} has no completed home.")
            workplace = str(resident.get("workplace_building_id", "") or "")
            if workplace and workplace not in buildings:
                errors.append(f"Resident {resident_id} references an unavailable workplace.")
            if resident_id not in seen_members:
                errors.append(f"Resident {resident_id} is missing from household membership.")
            name = str(resident.get("name", ""))
            if name in names:
                warnings.append(f"Duplicate generated name: {name}.")
            names.add(name)
            age_group = str(resident.get("age_group", "Adult"))
            if age_group in {"Child", "Teen"} and workplace:
                errors.append(f"Young resident {name} has an adult workplace assignment.")
            if int(resident.get("dialogue_count", 0) or 0) < 0:
                errors.append(f"Resident {name} has an invalid dialogue count.")
            recent_dialogue = list(resident.get("recent_dialogue_ids", []) or [])
            if len(recent_dialogue) > 10:
                errors.append(f"Resident {name} retains too many recent dialogue lines.")
            active_request = sanitize_procedural_request(
                resident.get("active_request", {})
            )
            if resident.get("active_request") and not active_request:
                errors.append(f"Resident {name} has a malformed active request.")
            if active_request and active_request.get("status") == "completed":
                if active_request["id"] not in set(
                    resident.get("completed_request_ids", []) or []
                ):
                    errors.append(
                        f"Resident {name}'s completed request is missing from request history."
                    )
            household_members = set(
                households.get(str(resident.get("household_id", "")), {}).get("member_ids", [])
            )
            for linked_id in (
                list(resident.get("family_member_ids", []) or [])
                + list(resident.get("guardian_ids", []) or [])
                + list(resident.get("dependent_ids", []) or [])
            ):
                if linked_id not in household_members or linked_id == resident_id:
                    errors.append(f"Resident {name} has an invalid household relationship link.")
            if age_group in {"Child", "Teen"} and not resident.get("guardian_ids"):
                warnings.append(f"Young resident {name} has no assigned guardian.")
            schedule = resident.get("schedule", {})
            for phase in PROCEDURAL_ROUTINE_PHASES:
                entry = schedule.get(phase) if isinstance(schedule, dict) else None
                if not isinstance(entry, dict):
                    errors.append(f"Resident {name} is missing the {phase} routine.")
                    continue
                if str(entry.get("kind", "")) == "building":
                    building_id = str(entry.get("building_id", ""))
                    if building_id not in buildings:
                        errors.append(f"Resident {name}'s {phase} routine references an unavailable building.")
        expected_jobs = {str(slot["origin_key"]) for slot in self.profession_slots(plan)}
        filled_jobs = {
            str(resident.get("origin_key", ""))
            for resident in residents.values()
            if str(resident.get("origin_key", "")).startswith("job:")
        }
        vacancies = set(str(value) for value in population.get("job_vacancies", []) or [])
        if expected_jobs != filled_jobs | vacancies:
            errors.append("Filled jobs and vacancy records do not match completed workplaces.")
        if not any(str(resident.get("role")) == "Mayor" for resident in residents.values()):
            if any(str(building.get("type_id")) == "town_hall" for building in buildings.values()):
                warnings.append("The completed Town Hall has no Mayor.")
        return {"errors": errors, "warnings": list(dict.fromkeys(warnings))}

    def summary(self, population: Dict[str, object]) -> Dict[str, object]:
        residents = list(population.get("residents", {}).values())
        roles: Dict[str, int] = {}
        age_groups: Dict[str, int] = {age_group: 0 for age_group in PROCEDURAL_AGE_GROUPS}
        for resident in residents:
            role = str(resident.get("role", "Settler"))
            roles[role] = roles.get(role, 0) + 1
            age_group = str(resident.get("age_group", "Adult"))
            age_groups[age_group] = age_groups.get(age_group, 0) + 1
        return {
            "population": len(residents),
            "households": len(population.get("households", {})),
            "employed": sum(1 for resident in residents if str(resident.get("workplace_building_id", ""))),
            "vacancies": len(population.get("job_vacancies", [])),
            "children": age_groups.get("Child", 0),
            "teens": age_groups.get("Teen", 0),
            "adults": age_groups.get("Adult", 0),
            "elders": age_groups.get("Elder", 0),
            "roles": roles,
        }

    def routine_for(
        self,
        resident: Dict[str, object],
        phase: str,
        bad_weather: bool = False,
    ) -> Dict[str, object]:
        schedule = resident.get("schedule", {})
        if not isinstance(schedule, dict):
            return {}
        key = "bad_weather" if bad_weather and phase != "late" else str(phase)
        entry = schedule.get(key) or schedule.get("evening") or schedule.get("wake") or {}
        return copy.deepcopy(entry) if isinstance(entry, dict) else {}


class ProceduralNpcBuilderMixin:
    """FarmGame helpers for dormant procedural settlement populations."""

    def procedural_npc_builder(self) -> ProceduralNpcBuilder:
        builder = getattr(self, "_procedural_npc_builder", None)
        if not isinstance(builder, ProceduralNpcBuilder):
            builder = ProceduralNpcBuilder()
            self._procedural_npc_builder = builder
        return builder

    def ensure_procedural_settlement_populations(self) -> Dict[str, Dict[str, object]]:
        populations = getattr(self.state, "procedural_settlement_populations", None)
        if not isinstance(populations, dict):
            populations = sanitize_procedural_settlement_populations(populations)
            self.state.procedural_settlement_populations = populations
        return populations

    def procedural_settlement_population(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Optional[Dict[str, object]]:
        return self.ensure_procedural_settlement_populations().get(
            procedural_population_key(chunk_x, chunk_y)
        )

    def generate_procedural_settlement_population(
        self,
        chunk_x: int,
        chunk_y: int,
        force: bool = False,
    ) -> Optional[Dict[str, object]]:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            return None
        populations = self.ensure_procedural_settlement_populations()
        key = procedural_population_key(chunk_x, chunk_y)
        existing = None if force else populations.get(key)
        population = self.procedural_npc_builder().create_population(plan, existing=existing)
        populations[key] = population
        return population

    def reconcile_procedural_settlement_population(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Optional[Dict[str, object]]:
        return self.generate_procedural_settlement_population(chunk_x, chunk_y, force=False)

    def procedural_settlement_residents(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> List[Dict[str, object]]:
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        if not population:
            return []
        return [
            copy.deepcopy(resident)
            for resident in population.get("residents", {}).values()
        ]

    def procedural_settlement_resident(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
    ) -> Optional[Dict[str, object]]:
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        if not population:
            return None
        resident = population.get("residents", {}).get(str(resident_id))
        return copy.deepcopy(resident) if isinstance(resident, dict) else None

    def procedural_settlement_population_validation(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Dict[str, List[str]]:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        if not plan:
            return {"errors": ["No settlement blueprint exists for this chunk."], "warnings": []}
        if not population:
            return {"errors": ["No procedural population exists for this settlement."], "warnings": []}
        return self.procedural_npc_builder().validate(population, plan)

    def procedural_settlement_population_report_lines(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> List[str]:
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        if not population:
            return ["No procedural population has been generated for this settlement."]
        summary = self.procedural_npc_builder().summary(population)
        validation = self.procedural_settlement_population_validation(chunk_x, chunk_y)
        lines = [
            "PROCEDURAL SETTLEMENT POPULATION",
            "",
            f"Settlement: {population.get('settlement_name')}",
            f"Chunk: {procedural_population_key(chunk_x, chunk_y)}",
            f"Status: {population.get('status')}",
            f"Population: {summary['population']}",
            f"Households: {summary['households']}",
            f"Employed: {summary['employed']}",
            f"Job vacancies: {summary['vacancies']}",
            (
                f"Ages: {summary['children']} child, {summary['teens']} teen, "
                f"{summary['adults']} adult, {summary['elders']} elder"
            ),
            "",
            "Residents:",
        ]
        for resident in sorted(
            population.get("residents", {}).values(),
            key=lambda row: (str(row.get("household_id", "")), str(row.get("name", ""))),
        ):
            workplace = str(resident.get("workplace_building_id", "") or "none")
            lines.append(
                f"- {resident.get('name')} — {resident.get('role')} "
                f"({resident.get('age_group')}; home {resident.get('home_building_id')}; work {workplace})"
            )
        if not population.get("residents"):
            lines.append("- No completed housing is available.")
        lines.extend(["", "Validation:"])
        lines.extend(f"- ERROR: {message}" for message in validation["errors"])
        lines.extend(f"- Warning: {message}" for message in validation["warnings"])
        if not validation["errors"] and not validation["warnings"]:
            lines.append("- Population records are structurally valid.")
        lines.extend([
            "",
            "Isolation:",
            "- These residents are not in the authored town NPC roster.",
            "- They have not been spawned into any live map.",
        ])
        return lines

    def show_procedural_settlement_population(self, chunk_x: int, chunk_y: int):
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        if not population:
            self.set_message("No procedural population has been generated for that settlement.")
            return None
        return self.vertical_panel_view(
            f"{population.get('settlement_name', 'Settlement')} Residents",
            self.procedural_settlement_population_report_lines(chunk_x, chunk_y),
            96,
            42,
        )


__all__ = [
    "BUILDING_PROFESSION_SLOTS",
    "PROCEDURAL_AGE_GROUPS",
    "PROCEDURAL_PERSONALITY_TRAITS",
    "PROCEDURAL_POPULATION_VERSION",
    "PROCEDURAL_ROUTINE_PHASES",
    "PROCEDURAL_SEXES",
    "ProceduralNpcBuilder",
    "ProceduralNpcBuilderMixin",
    "procedural_completed_buildings",
    "procedural_population_key",
    "sanitize_procedural_request",
    "sanitize_procedural_settlement_populations",
]
