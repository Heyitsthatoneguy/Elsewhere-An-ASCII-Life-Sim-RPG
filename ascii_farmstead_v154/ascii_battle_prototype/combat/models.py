from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple

Pos = Tuple[int, int]

@dataclass
class Weapon:
    name: str
    damage: int
    range_min: int = 1
    range_max: int = 1
    aoe_radius: int = 0
    shape: str = "point"  # point, burst, strip, cone, cross, multishot
    damage_type: str = "physical"
    status: str = ""
    status_duration: int = 0
    width: int = 1
    shots: int = 1
    trait: str = ""


@dataclass
class Skill:
    name: str
    mp_cost: int
    damage: int
    range_max: int
    aoe_radius: int = 0
    shape: str = "burst"  # point, burst, strip, cone, cross, multishot
    width: int = 1
    shots: int = 1
    status: str = ""
    status_duration: int = 0
    description: str = ""
    effect: str = "damage"  # damage, heal, transfer_ap, cleanse, guard, restore_mp
    heal_amount: int = 0
    mp_amount: int = 0
    ap_amount: int = 0
    target_team: str = "enemy"  # enemy or ally
    combo_status: str = ""  # bonus if target has this status: poison/root/vulnerable
    combo_any_status: bool = False
    combo_guarded: bool = False  # bonus if caster is guarding
    combo_target_guarded: bool = False  # bonus if ally target is guarding
    combo_damage_bonus: int = 0
    combo_heal_bonus: int = 0
    combo_ap_gain: int = 0
    combo_mp_gain: int = 0
    combo_note: str = ""
    zone_type: str = ""  # fire, frost, storm, earth, poison, light, shadow
    zone_duration: int = 0
    zone_damage: int = 0
    zone_status: str = ""
    zone_status_duration: int = 0


@dataclass
class Item:
    name: str
    effect: str  # heal, mp, cleanse, guard, damage
    target_team: str = "ally"  # ally or enemy
    amount: int = 0
    range_max: int = 0
    aoe_radius: int = 0
    status: str = ""
    status_duration: int = 0
    description: str = ""


@dataclass
class Zone:
    name: str
    tiles: Set[Pos]
    kind: str
    duration: int
    damage: int = 0
    status: str = ""
    status_duration: int = 0
    owner_team: str = "hero"

    @property
    def center(self) -> Pos:
        """Return a stable representative center for compatibility callers."""
        if not self.tiles:
            return (0, 0)
        count = len(self.tiles)
        return (
            int(round(sum(pos[0] for pos in self.tiles) / count)),
            int(round(sum(pos[1] for pos in self.tiles) / count)),
        )


@dataclass
class Unit:
    name: str
    glyph: str
    pos: Pos
    max_hp: int
    hp: int
    max_mp: int
    mp: int
    move_range: int
    weapon: Weapon
    team: str
    ai_controlled: bool = False
    level: int = 1
    xp: int = 0
    guard: bool = False
    action_points: int = 0
    inventory: Dict[str, int] = field(default_factory=lambda: {"Potion": 1})
    role: str = ""
    cooldowns: Dict[str, int] = field(default_factory=dict)
    poison: int = 0
    rooted: int = 0
    vulnerable: int = 0
    active: bool = True
    elite: bool = False
    boss: bool = False
    defense: int = 0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        if self.vulnerable > 0:
            amount += 1
        if self.defense > 0:
            amount = max(1, amount - self.defense)
        if self.guard:
            amount = max(1, amount // 2)
        self.hp = max(0, self.hp - amount)
        return amount


@dataclass
class OverwatchAction:
    owner: Unit
    kind: str  # weapon or skill
    name: str
    target: Pos
    tiles: Set[Pos]
    skill_index: Optional[int] = None


# ---------------------------------------------------------------------------
