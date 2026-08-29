"""Mega-dungeon skill books and the abilities preserved inside them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Mapping, Tuple

if TYPE_CHECKING:
    from ascii_battle_prototype.combat.models import Skill


MEGA_DUNGEON_SKILL_BOOKS: Dict[str, Dict[str, object]] = {
    "Codex of Falling Stars": {
        "skill": "Meteor Break",
        "themes": ("crystal",),
        "description": "A prismatic combat codex describing a controlled field of falling fire.",
    },
    "Glacier-Walker's Manual": {
        "skill": "Glacial Path",
        "themes": ("sunken", "crystal"),
        "description": "A water-stained manual for driving a freezing path through a defended lane.",
    },
    "Storm Conductor's Folio": {
        "skill": "Chain Current",
        "themes": ("crystal", "sunken"),
        "description": "Copper-edged pages teaching a current to leap between several targets.",
    },
    "Faultbreak Treatise": {
        "skill": "Seismic Break",
        "themes": ("quarry", "root"),
        "description": "Dense diagrams explaining how to drive a widening rupture through stone and armor.",
    },
    "Tidebinder's Ledger": {
        "skill": "Tidal Grasp",
        "themes": ("sunken",),
        "description": "A sealed ledger whose flowing notation teaches a crushing inward current.",
    },
    "Manual of the Phantom Step": {
        "skill": "Phantom Step",
        "themes": ("quarry", "crystal"),
        "description": "A duelist's manual for disappearing into motion before an enemy can answer.",
    },
    "Iron Resolve Primer": {
        "skill": "Iron Resolve",
        "themes": ("quarry", "root"),
        "description": "A battered primer on surviving the moment when a battle should already be lost.",
    },
    "Field Guide to Wild Communion": {
        "skill": "Wild Communion",
        "themes": ("overgrown", "root"),
        "description": "Careful observations connecting restorative fieldcraft, animals, and living terrain.",
    },
    "Arcane Workshop Notes": {
        "skill": "Arcane Workshop",
        "themes": ("crystal", "quarry"),
        "description": "An engineer's annotated notes on recovering and redirecting magical energy.",
    },
    "Living Vines Grimoire": {
        "skill": "Living Vines",
        "themes": ("overgrown", "root"),
        "description": "Pressed leaves and shifting diagrams teach vines to hold an entire formation.",
    },
    "The Patient Hunter": {
        "skill": "Hunter's Mark",
        "themes": ("overgrown", "quarry"),
        "description": "A practical hunting text about exposing one dangerous target to the whole party.",
    },
    "Grand Restoration Compendium": {
        "skill": "Grand Restoration",
        "themes": ("sunken", "overgrown"),
        "description": "A complete restorative discipline recovered intact from the dungeon's deepest archive.",
    },
}


MEGA_DUNGEON_THEME_BOOKS: Dict[str, Tuple[str, ...]] = {
    theme: tuple(
        book_name
        for book_name, record in MEGA_DUNGEON_SKILL_BOOKS.items()
        if theme in tuple(record.get("themes", ()))
    )
    for theme in ("overgrown", "root", "sunken", "quarry", "crystal")
}


def create_mega_dungeon_skills() -> List[Skill]:
    """Return late-game abilities compatible with both tactical combat engines."""
    from ascii_battle_prototype.combat.models import Skill

    return [
        Skill(
            "Meteor Break", mp_cost=11, damage=12, range_max=7, aoe_radius=2,
            shape="burst", zone_type="fire", zone_duration=3, zone_damage=3,
            description="Call several controlled impacts across a wide area and leave the ground burning.",
        ),
        Skill(
            "Glacial Path", mp_cost=8, damage=6, range_max=7, shape="strip", width=1,
            status="root", status_duration=2, zone_type="frost", zone_duration=3,
            zone_damage=1, zone_status="root", zone_status_duration=1,
            description="Freeze a long corridor, pinning enemies and creating a persistent path of ice.",
        ),
        Skill(
            "Chain Current", mp_cost=9, damage=5, range_max=7, shape="multishot",
            shots=6, status="vulnerable", status_duration=1,
            zone_type="storm", zone_duration=2, zone_damage=1,
            description="Send a powerful electrical current through as many as six nearby enemies.",
        ),
        Skill(
            "Seismic Break", mp_cost=9, damage=9, range_max=6, shape="cone", width=3,
            status="root", status_duration=1, armor_pierce=3, displacement=2,
            zone_type="earth", zone_duration=2, zone_damage=2,
            description="Drive a widening rupture forward, breaking armor and forcing enemies back.",
        ),
        Skill(
            "Tidal Grasp", mp_cost=8, damage=6, range_max=6, aoe_radius=2,
            shape="burst", displacement=-2, status="vulnerable", status_duration=1,
            description="Collapse a broad current inward, pulling enemies together and exposing them.",
        ),
        Skill(
            "Phantom Step", mp_cost=5, damage=0, range_max=99, shape="support",
            effect="guard", target_team="ally",
            description="Disappear into an evasive step that places an ally under Guard before the next exchange.",
        ),
        Skill(
            "Iron Resolve", mp_cost=7, damage=0, range_max=99, shape="support",
            effect="heal", heal_amount=8, target_team="ally",
            combo_target_guarded=True, combo_heal_bonus=12,
            description="Restore a battered ally; one who is already guarding receives a much stronger recovery.",
        ),
        Skill(
            "Wild Communion", mp_cost=7, damage=0, range_max=99, shape="support",
            effect="heal", heal_amount=12, target_team="ally",
            description="Draw on the living world to restore an ally and encourage natural growth in the field.",
        ),
        Skill(
            "Arcane Workshop", mp_cost=5, damage=0, range_max=99, shape="support",
            effect="restore_mp", mp_amount=12, target_team="ally",
            description="Reconfigure spent magical energy and return a substantial amount of MP to an ally.",
        ),
        Skill(
            "Living Vines", mp_cost=8, damage=5, range_max=6, shape="cross",
            status="root", status_duration=2, zone_type="earth", zone_duration=3,
            zone_damage=1, zone_status="root", zone_status_duration=2,
            description="Grow grasping vines through a broad formation and hold survivors in place.",
        ),
        Skill(
            "Hunter's Mark", mp_cost=6, damage=5, range_max=8, shape="point",
            status="vulnerable", status_duration=4, armor_pierce=2,
            combo_status="vulnerable", combo_damage_bonus=5,
            description="Expose a distant priority target; marking it again delivers a punishing follow-up.",
        ),
        Skill(
            "Grand Restoration", mp_cost=10, damage=0, range_max=99, shape="support",
            effect="heal", heal_amount=20, target_team="ally",
            description="Apply the deepest restorative discipline to return a gravely wounded ally to the fight.",
        ),
    ]


def mega_dungeon_book_record(book_name: str) -> Dict[str, object]:
    return dict(MEGA_DUNGEON_SKILL_BOOKS.get(str(book_name), {}))


def mega_dungeon_book_for_theme(theme: str, selector: int) -> str:
    pool = MEGA_DUNGEON_THEME_BOOKS.get(str(theme), ())
    if not pool:
        pool = tuple(MEGA_DUNGEON_SKILL_BOOKS)
    return pool[max(0, int(selector)) % len(pool)]


def mega_dungeon_skill_catalog() -> Dict[str, "Skill"]:
    return {skill.name: skill for skill in create_mega_dungeon_skills()}


def mega_dungeon_skill_names() -> Tuple[str, ...]:
    return tuple(record["skill"] for record in MEGA_DUNGEON_SKILL_BOOKS.values())


def clean_mega_skill_ranks(values: object) -> Dict[str, int]:
    if not isinstance(values, Mapping):
        return {}
    allowed = set(mega_dungeon_skill_names())
    cleaned: Dict[str, int] = {}
    for name, rank in values.items():
        name = str(name)
        if name not in allowed:
            continue
        try:
            cleaned[name] = max(1, min(3, int(rank)))
        except (TypeError, ValueError):
            continue
    return cleaned


__all__ = [
    "MEGA_DUNGEON_SKILL_BOOKS",
    "MEGA_DUNGEON_THEME_BOOKS",
    "clean_mega_skill_ranks",
    "create_mega_dungeon_skills",
    "mega_dungeon_book_for_theme",
    "mega_dungeon_book_record",
    "mega_dungeon_skill_catalog",
    "mega_dungeon_skill_names",
]
