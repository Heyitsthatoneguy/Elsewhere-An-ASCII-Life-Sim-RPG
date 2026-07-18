from __future__ import annotations

"""Map-native, turn-based combat for persistent wilderness dungeons."""

from collections import deque
from dataclasses import replace
import random
from typing import Dict, List, Optional, Set, Tuple

from ascii_farmstead_combat import (
    farmstead_combat_profile,
    grant_combat_exp,
    mine_combat_exp_for_defeated,
    translated_battle_loot,
)
from ascii_farmstead_actors import shortest_path_step
from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_inventory import add_inventory_items, format_drops
from ascii_farmstead_support import C, colorize, movement_delta_for_key, normalize_key, read_key
from ascii_farmstead_ui import MenuItem
from ascii_battle_prototype.combat.classes import class_defs as tactical_class_defs
from ascii_battle_prototype.combat.loot import loot_profile_for_enemy
from ascii_battle_prototype.combat.models import Skill
from ascii_battle_prototype.combat.skills import create_default_skills


DUNGEON_ENEMY_ARCHETYPES: Dict[str, Dict[str, object]] = {
    "Dustling": {"hp": 11, "attack": 4, "defense": 0, "behavior": "skittish", "dodge": 0.08},
    "Ruin Bat": {"hp": 9, "attack": 4, "defense": 0, "behavior": "darting", "dodge": 0.18},
    "Moss Haunt": {"hp": 18, "attack": 5, "defense": 1, "behavior": "poisoner"},
    "Shardling": {"hp": 15, "attack": 6, "defense": 1, "behavior": "shard_caster", "range": 4},
    "Relic Archer": {"hp": 16, "attack": 6, "defense": 1, "behavior": "archer", "range": 6},
    "Hollow Sentinel": {"hp": 30, "attack": 7, "defense": 3, "behavior": "guardian", "slow": True},
    "Clockwork Beetle": {"hp": 24, "attack": 6, "defense": 3, "behavior": "patrol", "slow": True},
    "Wolf": {"hp": 20, "attack": 5, "defense": 0, "behavior": "darting", "dodge": 0.12},
    "Bandit": {"hp": 22, "attack": 5, "defense": 1, "behavior": "archer", "range": 5},
    "Shield Guard": {"hp": 30, "attack": 5, "defense": 3, "behavior": "guardian", "slow": True},
    "Sporeling": {"hp": 18, "attack": 4, "defense": 0, "behavior": "poisoner", "range": 3},
    "Rockback": {"hp": 42, "attack": 7, "defense": 4, "behavior": "guardian", "slow": True},
    "Marsh Toad": {"hp": 26, "attack": 5, "defense": 1, "behavior": "poisoner", "range": 3},
    "Razor Hare": {"hp": 16, "attack": 4, "defense": 0, "behavior": "darting", "dodge": 0.20},
    "Ember Imp": {"hp": 20, "attack": 5, "defense": 1, "behavior": "shard_caster", "range": 4},
    "Burrower": {"hp": 28, "attack": 6, "defense": 2, "behavior": "hunter"},
    "Thornback": {"hp": 32, "attack": 6, "defense": 3, "behavior": "guardian", "range": 2},
}


class DungeonRoguelikeCombatMixin:
    """Map-native combat shared by wilderness dungeons and the overworld."""

    def wilderness_field_combat_record(self) -> Dict[str, object]:
        combat = getattr(self.state, "wilderness_field_combat", None)
        if not isinstance(combat, dict):
            combat = {}
            self.state.wilderness_field_combat = combat
        combat.setdefault("active", False)
        combat.setdefault("turn", 0)
        combat.setdefault("guard_turns", 0)
        combat.setdefault("poison_turns", 0)
        combat.setdefault("guardian_guard", 0)
        combat.setdefault("companion_cooldowns", {})
        combat.setdefault("companion_states", {})
        combat.setdefault("skill_zones", [])
        combat.setdefault("combat_log", [])
        return combat

    def wilderness_field_combat_active(self) -> bool:
        if not self.on_wilderness():
            return False
        combat = self.wilderness_field_combat_record()
        return bool(
            combat.get("active", False)
            and int(combat.get("chunk_x", 999999)) == int(self.state.wilderness_chunk_x)
            and int(combat.get("chunk_y", 999999)) == int(self.state.wilderness_chunk_y)
        )

    def map_native_combat_active(self) -> bool:
        return bool(self.on_wilderness_dungeon() or self.wilderness_field_combat_active())

    def wilderness_field_combat_enemies(self) -> List[Dict[str, object]]:
        if not self.on_wilderness():
            return []
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        enemies: List[Dict[str, object]] = []
        for enemy in self.get_wilderness_stronghold_enemies(cx, cy, create=False):
            if isinstance(enemy, dict) and not bool(enemy.get("defeated", False)):
                enemy.setdefault("field_combat_kind", "stronghold")
                enemies.append(enemy)
        for enemy in self.get_bounty_targets_for_chunk(cx, cy, create=False):
            if isinstance(enemy, dict) and not bool(enemy.get("target_defeated", False)):
                enemy = self.bounty_record_as_enemy(enemy)
                enemy.setdefault("field_combat_kind", "bounty")
                enemies.append(enemy)
        encounter_getter = getattr(self, "get_wilderness_random_combat_enemies", None)
        if callable(encounter_getter):
            for enemy in encounter_getter(cx, cy, create=False):
                if isinstance(enemy, dict) and not bool(enemy.get("defeated", False)):
                    enemy.setdefault("field_combat_kind", "encounter")
                    enemies.append(enemy)
        return enemies

    def map_combat_enemies(self) -> List[Dict[str, object]]:
        if self.on_wilderness():
            return self.wilderness_field_combat_enemies()
        return self.get_wilderness_dungeon_enemies()

    def map_combat_enemy_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if self.on_wilderness():
            for enemy in self.wilderness_field_combat_enemies():
                if (int(enemy.get("x", -1)), int(enemy.get("y", -1))) == (int(x), int(y)):
                    return enemy
            return None
        return self.wilderness_dungeon_enemy_at(x, y)

    def map_combat_remove_enemy(self, enemy: Dict[str, object]) -> None:
        kind = str(enemy.get("field_combat_kind", ""))
        if kind == "stronghold":
            self.remove_wilderness_stronghold_enemy(enemy)
        elif kind == "bounty":
            self.mark_bounty_target_defeated(enemy)
        elif kind == "encounter":
            remover = getattr(self, "remove_wilderness_random_combat_enemy", None)
            if callable(remover):
                remover(enemy)
        else:
            self.remove_wilderness_dungeon_enemy(enemy)

    def map_combat_floor(self) -> int:
        return 0 if self.on_wilderness() else int(self.state.current_dungeon_floor)

    def begin_wilderness_field_combat(self, enemy: Dict[str, object], reason: str = "nearby") -> bool:
        if not self.on_wilderness() or not isinstance(enemy, dict):
            return False
        combat = self.wilderness_field_combat_record()
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        if not self.wilderness_field_combat_active():
            combat.clear()
            combat.update({
                "active": True,
                "chunk_x": cx,
                "chunk_y": cy,
                "turn": 0,
                "guard_turns": 0,
                "poison_turns": 0,
                "guardian_guard": 0,
                "companion_cooldowns": {},
                "companion_states": {},
                "skill_zones": [],
                "combat_log": [],
                "started_x": int(self.state.player_x),
                "started_y": int(self.state.player_y),
            })
        enemy = self.ensure_dungeon_roguelike_enemy(enemy)
        enemy["alert"] = True
        enemy["heard_x"], enemy["heard_y"] = int(self.state.player_x), int(self.state.player_y)
        enemy["search_turns"] = max(4, int(enemy.get("search_turns", 0)))
        label = str(enemy.get("species", "Hostile"))
        self._dungeon_turn_messages = [
            f"{label} engages you on the wilderness map. Combat is now turn-based."
        ]
        self.dungeon_emit_noise(int(self.state.player_x), int(self.state.player_y), 7, label=reason)
        self.set_message(self._dungeon_turn_messages[0])
        self.invalidate_draw_cache()
        return True

    def end_wilderness_field_combat(self, message: str = "The immediate danger has passed.") -> None:
        combat = self.wilderness_field_combat_record()
        combat["active"] = False
        combat["skill_zones"] = []
        combat["companion_states"] = {}
        for enemy in self.wilderness_field_combat_enemies():
            enemy["intent"] = {}
        self.set_message(message)
        self.invalidate_draw_cache()

    def check_wilderness_field_combat_end(self) -> bool:
        if not self.wilderness_field_combat_active():
            return False
        enemies = self.wilderness_field_combat_enemies()
        alerted = [enemy for enemy in enemies if bool(enemy.get("alert", False))]
        if not alerted:
            self.end_wilderness_field_combat("You slip away; the wilderness returns to its ordinary rhythm.")
            return True
        px, py = int(self.state.player_x), int(self.state.player_y)
        if all(self.dungeon_distance((px, py), (int(enemy.get("x", 0)), int(enemy.get("y", 0)))) > 16 for enemy in alerted):
            for enemy in alerted:
                enemy["alert"] = False
                enemy["intent"] = {}
            self.state.mine_combat_flees += 1
            self.end_wilderness_field_combat("You put enough distance between yourself and the hostile group to escape.")
            return True
        return False

    def dungeon_roguelike_record(self) -> Dict[str, object]:
        if self.on_wilderness():
            return self.wilderness_field_combat_record()
        record = self.dungeon_record(str(self.state.current_dungeon_key))
        combat = record.setdefault("roguelike_combat", {})
        if not isinstance(combat, dict):
            combat = {}
            record["roguelike_combat"] = combat
        combat.setdefault("turn", 0)
        combat.setdefault("guard_turns", 0)
        combat.setdefault("poison_turns", 0)
        combat.setdefault("guardian_guard", 0)
        combat.setdefault("companion_cooldowns", {})
        combat.setdefault("door_states", {})
        combat.setdefault("revealed_traps", [])
        combat.setdefault("disarmed_traps", [])
        combat.setdefault("companion_states", {})
        combat.setdefault("skill_zones", [])
        combat.setdefault("combat_log", [])
        return combat

    def dungeon_feature_key(self, x: int, y: int, floor: Optional[int] = None) -> str:
        floor_num = max(1, int(floor if floor is not None else self.state.current_dungeon_floor))
        return f"F{floor_num}:{int(x)},{int(y)}"

    def dungeon_door_states(self) -> Dict[str, bool]:
        states = self.dungeon_roguelike_record().setdefault("door_states", {})
        if not isinstance(states, dict):
            states = {}
            self.dungeon_roguelike_record()["door_states"] = states
        return states

    def dungeon_door_closed(self, x: int, y: int) -> bool:
        if self.dungeon_terrain_tile(x, y) != "+":
            return False
        key = self.dungeon_feature_key(x, y)
        states = self.dungeon_door_states()
        if key not in states:
            seed = (
                int(getattr(self.state, "wilderness_seed", 0))
                + sum(ord(ch) for ch in str(self.state.current_dungeon_key)) * 17
                + int(self.state.current_dungeon_floor) * 101
                + int(x) * 37 + int(y) * 53
            )
            states[key] = seed % 4 == 0
        return bool(states[key])

    def dungeon_door_occupied(self, x: int, y: int) -> bool:
        return bool(
            (int(self.state.player_x), int(self.state.player_y)) == (int(x), int(y))
            or self.travel_follower_at(x, y)
            or self.map_combat_enemy_at(x, y)
        )

    def dungeon_set_door_closed(self, x: int, y: int, closed: bool) -> bool:
        if self.dungeon_terrain_tile(x, y) != "+":
            return False
        if closed and self.dungeon_door_occupied(x, y):
            self.set_message("The doorway is occupied and cannot be closed.")
            return False
        self.dungeon_door_states()[self.dungeon_feature_key(x, y)] = bool(closed)
        return True

    def dungeon_use_door(self, x: int, y: int, *, actor: str = "You") -> bool:
        if self.dungeon_terrain_tile(x, y) != "+":
            return False
        was_closed = self.dungeon_door_closed(x, y)
        if not self.dungeon_set_door_closed(x, y, not was_closed):
            return False
        action = "open" if was_closed else "close"
        owner = "You" if actor == "You" else actor
        self._dungeon_turn_messages = [f"{owner} {action}{'s' if actor != 'You' else ''} the old door."]
        self.dungeon_emit_noise(x, y, 4, label=f"door {action}ing")
        return self.advance_dungeon_roguelike_turn(f"{action} door")

    def render_dungeon_door(self, x: int, y: int) -> str:
        return colorize("+" if self.dungeon_door_closed(x, y) else "/", C.DOOR + C.BOLD)

    def dungeon_trap_revealed(self, x: int, y: int) -> bool:
        key = self.dungeon_feature_key(x, y)
        revealed = self.dungeon_roguelike_record().setdefault("revealed_traps", [])
        return key in revealed

    def dungeon_trap_disarmed(self, x: int, y: int) -> bool:
        key = self.dungeon_feature_key(x, y)
        disarmed = self.dungeon_roguelike_record().setdefault("disarmed_traps", [])
        return key in disarmed

    def render_dungeon_trap(self, x: int, y: int) -> str:
        if self.dungeon_trap_disarmed(x, y):
            return colorize(":", C.PATH)
        if self.dungeon_trap_revealed(x, y):
            return colorize("!", C.HOSTILE)
        return colorize(".", C.DUNGEON_FLOOR)

    def dungeon_scout_bonus(self) -> float:
        return 0.22 if any(
            str(profile.get("expedition_role", "")) == "Scout"
            for profile in self.active_farmstead_companion_profiles()
        ) else 0.0

    def dungeon_reveal_nearby_traps(self, radius: int = 1, guaranteed: bool = False) -> int:
        px, py = int(self.state.player_x), int(self.state.player_y)
        grid = self.active_map()
        combat = self.dungeon_roguelike_record()
        revealed = combat.setdefault("revealed_traps", [])
        profile = farmstead_combat_profile(self.state)
        chance = min(0.90, 0.20 + int(profile.get("level", 1)) * 0.025 + self.dungeon_scout_bonus())
        found = 0
        for y in range(max(0, py - radius), min(len(grid), py + radius + 1)):
            for x in range(max(0, px - radius), min(len(grid[y]), px + radius + 1)):
                if self.dungeon_distance((px, py), (x, y)) > radius or grid[y][x] != "!":
                    continue
                key = self.dungeon_feature_key(x, y)
                if key in revealed or self.dungeon_trap_disarmed(x, y):
                    continue
                if guaranteed or random.random() < chance:
                    revealed.append(key)
                    found += 1
        if found:
            self.dungeon_combat_note(f"You notice {found} old trap plate{'s' if found != 1 else ''}.")
        return found

    def dungeon_disarm_trap(self, x: int, y: int) -> bool:
        if self.dungeon_terrain_tile(x, y) != "!" or self.dungeon_trap_disarmed(x, y):
            self.set_message("There is no active trap to disarm there.")
            return False
        if not self.dungeon_trap_revealed(x, y):
            self.set_message("You have not spotted a trap there.")
            return False
        profile = farmstead_combat_profile(self.state)
        chance = min(0.92, 0.48 + int(profile.get("level", 1)) * 0.025 + self.dungeon_scout_bonus())
        self._dungeon_turn_messages = []
        if random.random() <= chance:
            key = self.dungeon_feature_key(x, y)
            combat = self.dungeon_roguelike_record()
            combat.setdefault("disarmed_traps", []).append(key)
            record = self.dungeon_record(str(self.state.current_dungeon_key))
            triggered = record.setdefault("triggered_traps", [])
            if key not in triggered:
                triggered.append(key)
            self.active_map()[y][x] = ":"
            self.dungeon_combat_note("You wedge the old trap mechanism safely open.")
            self.advance_dungeon_roguelike_turn("disarm trap")
            return True
        self.trigger_wilderness_dungeon_trap(x, y)
        self.dungeon_combat_note(str(self.state.message))
        self.advance_dungeon_roguelike_turn("failed disarm")
        return False

    def dungeon_enemy_trigger_trap(self, enemy: Dict[str, object]) -> bool:
        if self.wilderness_field_combat_active():
            return False
        x, y = int(enemy.get("x", -1)), int(enemy.get("y", -1))
        if self.dungeon_terrain_tile(x, y) != "!" or self.dungeon_trap_disarmed(x, y):
            return False
        enemy = self.ensure_dungeon_roguelike_enemy(enemy)
        key = self.dungeon_feature_key(x, y)
        damage = 5 + self.dungeon_tier_for_key(str(self.state.current_dungeon_key)) * 2
        enemy["hp"] = max(0, int(enemy["hp"]) - damage)
        record = self.dungeon_record(str(self.state.current_dungeon_key))
        if key not in record.setdefault("triggered_traps", []):
            record["triggered_traps"].append(key)
        if key not in self.dungeon_roguelike_record().setdefault("revealed_traps", []):
            self.dungeon_roguelike_record()["revealed_traps"].append(key)
        self.active_map()[y][x] = ":"
        self.dungeon_combat_note(
            f"{enemy.get('species')} springs a floor trap for {damage} damage "
            f"({enemy['hp']}/{enemy['max_hp']} HP)."
        )
        if int(enemy["hp"]) <= 0:
            self.dungeon_defeat_enemy(enemy, "The trap")
        return True

    def dungeon_companion_key(self, companion: Dict[str, object]) -> str:
        return str(
            companion.get("id") or companion.get("npc_id") or companion.get("name") or "companion"
        )

    def dungeon_companion_runtime(self, companion: Dict[str, object]) -> Dict[str, object]:
        states = self.dungeon_roguelike_record().setdefault("companion_states", {})
        key = self.dungeon_companion_key(companion)
        maximum = max(1, int(companion.get("max_hp", companion.get("current_hp", 20)) or 20))
        state = states.setdefault(key, {"hp": maximum, "max_hp": maximum, "knocked_out": False})
        state["max_hp"] = maximum
        state["hp"] = max(0, min(maximum, int(state.get("hp", maximum))))
        state["knocked_out"] = bool(state.get("knocked_out", False) or int(state["hp"]) <= 0)
        return state

    def dungeon_physical_companion_targets(self) -> List[Dict[str, object]]:
        targets = []
        for companion in self.active_farmstead_companion_profiles():
            follower_id = str(companion.get("id", ""))
            position = self.travel_follower_position(follower_id) if follower_id else None
            runtime = self.dungeon_companion_runtime(companion)
            if position is None or int(runtime.get("hp", 0)) <= 0:
                continue
            targets.append({
                "kind": "companion",
                "id": self.dungeon_companion_key(companion),
                "follower_id": follower_id,
                "name": str(companion.get("name", "Companion")),
                "position": (int(position[0]), int(position[1])),
                "profile": companion,
                "runtime": runtime,
            })
        return targets

    def dungeon_target_by_identity(self, kind: str, target_id: str = "") -> Optional[Dict[str, object]]:
        if kind != "companion":
            return {
                "kind": "player", "id": "player", "name": "you",
                "position": (int(self.state.player_x), int(self.state.player_y)),
            }
        return next(
            (target for target in self.dungeon_physical_companion_targets() if target["id"] == str(target_id)),
            None,
        )

    def dungeon_enemy_visible_target(self, enemy: Dict[str, object], perception: int) -> Optional[Dict[str, object]]:
        origin = (int(enemy.get("x", 0)), int(enemy.get("y", 0)))
        targets = [self.dungeon_target_by_identity("player")] + self.dungeon_physical_companion_targets()
        visible = []
        for target in targets:
            if not target:
                continue
            position = target["position"]
            distance = self.dungeon_distance(origin, position)
            if distance > int(perception) or not self.dungeon_has_line_of_sight(origin, position):
                continue
            role = str(target.get("profile", {}).get("expedition_role", ""))
            aggro = -2 if role == "Guardian" else (1 if role == "Support" else 0)
            visible.append((distance + aggro, distance, str(target.get("id", "")), target))
        return min(visible, default=(0, 0, "", None))[3]

    def dungeon_enemy_attack_companion(
        self, enemy: Dict[str, object], target: Dict[str, object], *, ranged: bool = False,
        multiplier: float = 1.0, attack_name: str = "",
    ) -> None:
        companion = dict(target.get("profile", {}) or {})
        runtime = target.get("runtime") or self.dungeon_companion_runtime(companion)
        guarded = int(runtime.get("guard_turns", 0)) > 0
        defense = max(0, int(companion.get("defense", 0))) + (3 if guarded else 0)
        if ranged:
            cover = self.dungeon_terrain_cover(*target["position"])
            if random.random() > max(0.45, 0.90 - cover):
                self.dungeon_combat_note(
                    f"{enemy.get('species')}'s {attack_name or 'shot'} misses {target.get('name')} in cover."
                )
                return
        damage = max(
            1,
            int((int(enemy.get("attack", 4)) + random.randint(-1, 1)) * float(multiplier)) - defense,
        )
        if ranged:
            damage = max(1, damage - 1)
        runtime["hp"] = max(0, int(runtime.get("hp", 1)) - damage)
        self.dungeon_combat_note(
            f"{enemy.get('species')}'s {attack_name or ('shot' if ranged else 'attack')} deals {damage} to "
            f"{target.get('name')} ({runtime['hp']}/{runtime['max_hp']} HP)."
        )
        if int(runtime["hp"]) <= 0:
            runtime["knocked_out"] = True
            follower_id = str(target.get("follower_id", ""))
            if follower_id:
                record = self.travel_follower_record(follower_id)
                record["x"], record["y"] = -1, -1
                record["activity"] = "recovering from a dungeon knockout"
            self.dungeon_combat_note(f"{target.get('name')} is knocked out and withdraws from the fight.")

    def dungeon_enemy_attack_target(
        self, enemy: Dict[str, object], target: Dict[str, object], *, ranged: bool = False,
        multiplier: float = 1.0, attack_name: str = "",
    ) -> None:
        if str(target.get("kind", "player")) == "companion":
            self.dungeon_enemy_attack_companion(
                enemy, target, ranged=ranged, multiplier=multiplier, attack_name=attack_name,
            )
        else:
            self.dungeon_enemy_attack_player(
                enemy, ranged=ranged, multiplier=multiplier, attack_name=attack_name,
            )

    def reset_dungeon_companions_after_exit(self) -> None:
        self.dungeon_roguelike_record()["companion_states"] = {}

    def dungeon_enemy_base_species(self, enemy: Dict[str, object]) -> str:
        return str(enemy.get("species", "Dustling")).replace("Elite ", "").strip()

    def ensure_dungeon_roguelike_enemy(self, enemy: Dict[str, object]) -> Dict[str, object]:
        base = self.dungeon_enemy_base_species(enemy)
        archetype = dict(DUNGEON_ENEMY_ARCHETYPES.get(base, DUNGEON_ENEMY_ARCHETYPES["Dustling"]))
        depth = max(1, int(enemy.get("floor", 1) or 1))
        scale = max(0, depth // 6)
        boss = bool(enemy.get("boss", False))
        max_hp = int(archetype.get("hp", 12)) + scale * 3
        attack = int(archetype.get("attack", 4)) + depth // 9
        defense = int(archetype.get("defense", 0)) + depth // 18
        if boss:
            max_hp = int(max_hp * 1.8) + 8
            attack += 2
            defense += 1
        enemy.setdefault("max_hp", max_hp)
        enemy.setdefault("hp", int(enemy.get("max_hp", max_hp)))
        enemy.setdefault("attack", attack)
        enemy.setdefault("defense", defense)
        enemy.setdefault("behavior", str(archetype.get("behavior", "hunter")))
        enemy.setdefault("attack_range", int(archetype.get("range", 1)))
        enemy.setdefault("dodge", float(archetype.get("dodge", 0.0)))
        enemy.setdefault("slow", bool(archetype.get("slow", False)))
        enemy.setdefault("statuses", {})
        enemy.setdefault("intent", {})
        enemy.setdefault("heard_x", None)
        enemy.setdefault("heard_y", None)
        enemy.setdefault("search_turns", 0)
        enemy["max_hp"] = max(1, int(enemy.get("max_hp", max_hp)))
        enemy["hp"] = max(0, min(enemy["max_hp"], int(enemy.get("hp", enemy["max_hp"]))))
        return enemy

    def dungeon_terrain_tile(self, x: int, y: int) -> str:
        grid = self.active_map()
        if y < 0 or y >= len(grid) or x < 0 or x >= len(grid[y]):
            return "#"
        return str(grid[y][x])

    def dungeon_terrain_name(self, x: int, y: int) -> str:
        if self.wilderness_field_combat_active():
            return {
                "'": "grass", '"': "brush", ":": "road", ",": "trail",
                "~": "water", "=": "current", "T": "trees", "#": "wall",
            }.get(self.dungeon_terrain_tile(x, y), "open ground")
        return {
            "'": "tangled roots", '"': "dry brush", ":": "broken paving",
            "~": "shallow water", ";": "crystal debris", "+": "doorway",
        }.get(self.dungeon_terrain_tile(x, y), "open floor")

    def dungeon_terrain_cover(self, x: int, y: int) -> float:
        if self.wilderness_field_combat_active():
            visual_getter = getattr(self, "wilderness_random_combat_visual_at", None)
            visual = visual_getter(x, y) if callable(visual_getter) else None
            if visual:
                return 0.28 if bool(visual.get("blocking", False)) else 0.14
            return {
                "'": 0.06, '"': 0.14, ",": 0.04, ":": 0.02,
                "T": 0.30, "o": 0.22, "*": 0.18,
            }.get(self.dungeon_terrain_tile(x, y), 0.0)
        return {"'": 0.12, '"': 0.16, "+": 0.10, ";": 0.06}.get(
            self.dungeon_terrain_tile(x, y), 0.0
        )

    def dungeon_terrain_noise_radius(self, x: int, y: int) -> int:
        return {"'": 1, '"': 2, ":": 3, "~": 4, ";": 4, "+": 3}.get(
            self.dungeon_terrain_tile(x, y), 2
        )

    def dungeon_player_move_cost(self, x: int, y: int) -> int:
        if self.wilderness_field_combat_active():
            return 2 if self.dungeon_terrain_tile(x, y) in {"'", '"', "~", "="} else 1
        return 2 if self.dungeon_terrain_tile(x, y) in {"'", '"', "~"} else 1

    def map_combat_enemy_passable_tile(self, x: int, y: int, ignore_enemy_id: str = "") -> bool:
        if self.wilderness_field_combat_active():
            if not self.in_active_bounds(x, y):
                return False
            if (int(x), int(y)) == (int(self.state.player_x), int(self.state.player_y)):
                return False
            if self.travel_follower_at(x, y):
                return False
            return bool(self.passable(x, y))
        return self.dungeon_enemy_passable_tile(x, y, ignore_enemy_id=ignore_enemy_id)

    def dungeon_terrain_blocks_sight(self, x: int, y: int) -> bool:
        tile = self.dungeon_terrain_tile(x, y)
        if self.wilderness_field_combat_active():
            visual_getter = getattr(self, "wilderness_random_combat_visual_at", None)
            visual = visual_getter(x, y) if callable(visual_getter) else None
            if visual and bool(visual.get("blocking", False)):
                return True
            return tile in {
                "#", " ", "T", "o", "*", "R", "J", "P", "K", "Q", "Y",
                "u", "W", "N", "F", "O", "L", "e", "p", "M", "G", "Z",
            }
        return tile in {"#", " "} or self.dungeon_door_closed(x, y)

    def dungeon_emit_noise(self, x: int, y: int, radius: int, label: str = "noise") -> int:
        alerted = 0
        for enemy in self.map_combat_enemies():
            enemy = self.ensure_dungeon_roguelike_enemy(enemy)
            if self.dungeon_distance((x, y), (int(enemy.get("x", 0)), int(enemy.get("y", 0)))) > int(radius):
                continue
            was_alert = bool(enemy.get("alert"))
            enemy["alert"] = True
            enemy["heard_x"], enemy["heard_y"] = int(x), int(y)
            enemy["search_turns"] = max(2, int(enemy.get("search_turns", 0)))
            enemy["alert_reason"] = str(label)
            alerted += 0 if was_alert else 1
        if alerted:
            self.dungeon_combat_note(f"The {label} alerts {alerted} nearby foe{'s' if alerted != 1 else ''}.")
        return alerted

    def render_dungeon_roguelike_enemy(self, enemy: Dict[str, object]) -> str:
        enemy = self.ensure_dungeon_roguelike_enemy(enemy)
        if enemy.get("intent"):
            return colorize("!", C.LAMP)
        return self.render_mine_enemy(enemy)

    def dungeon_combat_status_line(self) -> str:
        profile = farmstead_combat_profile(self.state)
        combat = self.dungeon_roguelike_record()
        alerted = sum(1 for enemy in self.map_combat_enemies() if enemy.get("alert"))
        companions = self.active_farmstead_companion_profiles()
        runtime_states = combat.setdefault("companion_states", {})
        companion_keys = {self.dungeon_companion_key(companion) for companion in companions}
        for companion in companions:
            self.dungeon_companion_runtime(companion)
        all_companion_keys = companion_keys | set(runtime_states)
        standing = sum(1 for key in all_companion_keys if int(runtime_states.get(key, {}).get("hp", 1)) > 0)
        conditions = []
        if int(combat.get("guard_turns", 0)) > 0:
            conditions.append("Guarded")
        if int(combat.get("poison_turns", 0)) > 0:
            conditions.append("Poisoned")
        active_zones = sum(
            1 for zone in self.dungeon_skill_zones()
            if int(zone.get("floor", 0)) == self.map_combat_floor()
            and int(zone.get("duration", 0)) > 0
        )
        if active_zones:
            conditions.append(f"Fields {active_zones}")
        condition_text = f" | {', '.join(conditions)}" if conditions else ""
        return (
            f"{'Field' if self.wilderness_field_combat_active() else 'Dungeon'} turn {int(combat.get('turn', 0))} | "
            f"HP {int(self.state.combat_current_hp)}/{int(profile['max_hp'])} | "
            f"MP {int(self.state.combat_focus)}/{int(profile['max_focus'])} | "
            f"Allies {standing}/{len(all_companion_keys)} | Alerted {alerted}{condition_text}"
        )

    def dungeon_combat_note(self, text: object) -> None:
        text = str(text or "").strip()
        if not text:
            return
        messages = getattr(self, "_dungeon_turn_messages", None)
        if not isinstance(messages, list):
            messages = []
            self._dungeon_turn_messages = messages
        messages.append(text)

    def dungeon_distance(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))

    def dungeon_line_points(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        x0, y0 = int(start[0]), int(start[1])
        x1, y1 = int(end[0]), int(end[1])
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        points = []
        while True:
            points.append((x0, y0))
            if (x0, y0) == (x1, y1):
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy
        return points

    def dungeon_has_line_of_sight(self, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
        grid = self.active_map()
        for x, y in self.dungeon_line_points(start, end)[1:-1]:
            if y < 0 or y >= len(grid) or x < 0 or x >= len(grid[0]):
                return False
            if self.dungeon_terrain_blocks_sight(x, y):
                return False
        return True

    def dungeon_skill_catalog(self) -> Dict[str, Skill]:
        """Return the same built-in and custom skill records used by tactical combat."""
        return {skill.name: skill for skill in create_default_skills()}

    def dungeon_class_mastered(self, progress: Dict[str, object], class_name: str) -> bool:
        class_data = tactical_class_defs().get(str(class_name), {})
        tree = list(class_data.get("tree", []) or [])
        if not tree:
            return False
        defaults = set(class_data.get("default", []) or [])
        unlocks_by_class = progress.get("class_unlocks", {})
        unlocks = set(unlocks_by_class.get(class_name, []) if isinstance(unlocks_by_class, dict) else [])
        ranks_by_class = progress.get("skill_ranks", {})
        ranks = ranks_by_class.get(class_name, {}) if isinstance(ranks_by_class, dict) else {}
        for skill_name, _cost, _description in tree:
            if skill_name not in defaults and skill_name not in unlocks:
                return False
            if int(ranks.get(skill_name, 1) if isinstance(ranks, dict) else 1) < 3:
                return False
        return True

    def dungeon_known_skill_names(self) -> List[str]:
        """Resolve the player's active classes, unlocks, mastery arts, and element."""
        progress = self.combat_progress_for_key("player")
        focus_class = str(progress.get("class", "Vanguard"))
        active_classes = progress.get("active_classes", [focus_class])
        if not isinstance(active_classes, list):
            active_classes = [focus_class]
        ordered_classes = []
        for class_name in [focus_class] + [str(value) for value in active_classes]:
            if class_name in tactical_class_defs() and class_name not in ordered_classes:
                ordered_classes.append(class_name)
        known: Set[str] = set()
        unlocks_by_class = progress.get("class_unlocks", {})
        for class_name in ordered_classes:
            class_data = tactical_class_defs().get(class_name, {})
            known.update(str(name) for name in class_data.get("default", []) or [])
            if isinstance(unlocks_by_class, dict):
                known.update(str(name) for name in unlocks_by_class.get(class_name, []) or [])
            mastery = str(class_data.get("mastery", "") or "")
            if mastery and self.dungeon_class_mastered(progress, class_name):
                known.add(mastery)
        known.update({
            "Fire": ("Ignite Field", "Flame Fan"),
            "Frost": ("Glacial Patch", "Frost Shards"),
            "Storm": ("Static Field", "Chain Lightning"),
            "Earth": ("Quake Field", "Seismic Wave"),
            "Poison": ("Venom Pool", "Toxic Bloom"),
            "Light": ("Radiant Seal", "Solar Flare"),
            "Shadow": ("Umbral Mire", "Umbral Barrage"),
        }.get(str(progress.get("subclass", "Fire")), ("Ignite Field", "Flame Fan")))
        catalog = self.dungeon_skill_catalog()
        ordered = [name for name in catalog if name in known]
        return ordered or (["Spark Shot"] if "Spark Shot" in catalog else list(catalog)[:1])

    def dungeon_skill_rank(self, skill_name: str) -> int:
        progress = self.combat_progress_for_key("player")
        active_classes = progress.get("active_classes", [progress.get("class", "Vanguard")])
        if not isinstance(active_classes, list):
            active_classes = [str(progress.get("class", "Vanguard"))]
        ranks_by_class = progress.get("skill_ranks", {})
        unlocks_by_class = progress.get("class_unlocks", {})
        best = 1
        for class_name in active_classes:
            class_name = str(class_name)
            class_data = tactical_class_defs().get(class_name, {})
            defaults = set(class_data.get("default", []) or [])
            unlocks = set(unlocks_by_class.get(class_name, []) if isinstance(unlocks_by_class, dict) else [])
            if skill_name not in defaults and skill_name not in unlocks:
                continue
            ranks = ranks_by_class.get(class_name, {}) if isinstance(ranks_by_class, dict) else {}
            maximum = 3 if any(str(entry[0]) == str(skill_name) for entry in class_data.get("tree", []) or []) else 1
            best = max(best, min(maximum, max(1, int(ranks.get(skill_name, 1) if isinstance(ranks, dict) else 1))))
        return best

    def dungeon_build_synergy_tier(self, class_name: str, subclass: str) -> int:
        class_data = tactical_class_defs().get(str(class_name), {})
        recommendations = class_data.get("recommended_elements", [])
        if not isinstance(recommendations, (list, tuple)) or not recommendations:
            recommendations = {
                "Vanguard": ("Fire", "Earth", "Light"),
                "Ranger": ("Poison", "Shadow", "Storm", "Frost"),
                "Guardian": ("Earth", "Light", "Frost"),
                "Mystic": ("Fire", "Frost", "Storm", "Poison"),
                "Duelist": ("Storm", "Shadow", "Fire"),
                "Alchemist": ("Poison", "Frost", "Light", "Earth"),
            }.get(str(class_name), ())
        recommendations = [str(value) for value in recommendations]
        if not recommendations:
            return 0
        if str(subclass) == recommendations[0]:
            return 3
        if str(subclass) in recommendations:
            return 2
        flexible = {
            "Vanguard": ("Storm",),
            "Ranger": ("Fire",),
            "Guardian": ("Poison",),
            "Mystic": ("Light", "Shadow"),
            "Duelist": ("Poison",),
            "Alchemist": ("Fire", "Shadow"),
        }
        return 1 if str(subclass) in flexible.get(str(class_name), ()) else 0

    def dungeon_effective_skill(self, skill: Skill) -> Skill:
        """Apply the shared rank and elemental bonuses without creating a battle instance."""
        rank = self.dungeon_skill_rank(skill.name)
        bonus = max(0, rank - 1)
        damage = int(skill.damage)
        heal_amount = int(skill.heal_amount)
        mp_amount = int(skill.mp_amount)
        status_duration = int(skill.status_duration)
        mp_cost = int(skill.mp_cost)
        combo_damage_bonus = int(skill.combo_damage_bonus)
        combo_heal_bonus = int(skill.combo_heal_bonus)
        combo_ap_gain = int(skill.combo_ap_gain)
        combo_mp_gain = int(skill.combo_mp_gain)
        zone_duration = int(skill.zone_duration)
        zone_damage = int(skill.zone_damage)
        zone_status_duration = int(skill.zone_status_duration)
        if skill.effect == "damage":
            damage += bonus * 2
            status_duration += bonus if skill.status else 0
            combo_damage_bonus += bonus if combo_damage_bonus else 0
            combo_ap_gain += 1 if combo_ap_gain and rank >= 3 else 0
            combo_mp_gain += bonus if combo_mp_gain else 0
        elif skill.effect == "heal":
            heal_amount += bonus * 4
            combo_heal_bonus += bonus * 2 if combo_heal_bonus else 0
        elif skill.effect == "restore_mp":
            mp_amount += bonus * 3
        subclass = str(self.combat_progress_for_key("player").get("subclass", "Fire"))
        lowered = skill.name.lower()
        if subclass == "Fire" and (skill.zone_type == "fire" or any(word in lowered for word in ("fire", "flame", "cinder", "ignite", "inferno"))):
            damage += 1
            zone_damage += 1 if zone_duration else 0
        elif subclass == "Frost" and (skill.status == "root" or skill.zone_status == "root" or skill.zone_type == "frost" or any(word in lowered for word in ("frost", "ice", "glacial"))):
            status_duration += 1 if skill.status == "root" else 0
            zone_status_duration += 1 if skill.zone_status == "root" else 0
        elif subclass == "Storm" and (skill.status == "vulnerable" or skill.zone_type == "storm" or any(word in lowered for word in ("storm", "static", "shock", "thunder"))):
            damage += 1 if skill.effect == "damage" else 0
        elif subclass == "Earth" and (skill.status == "root" or skill.zone_type == "earth" or skill.effect == "guard"):
            mp_cost = max(0, mp_cost - 1)
            zone_status_duration += 1 if skill.zone_status == "root" else 0
        elif subclass == "Poison" and (skill.status == "poison" or skill.zone_status == "poison" or skill.zone_type == "poison" or any(word in lowered for word in ("poison", "venom", "toxic", "spore"))):
            status_duration += 1 if skill.status == "poison" else 0
            zone_status_duration += 1 if skill.zone_status == "poison" else 0
            zone_duration += 1 if skill.zone_type == "poison" else 0
        elif subclass == "Light":
            heal_amount += 3 if skill.effect == "heal" else 0
            if skill.effect == "damage" and any(word in lowered for word in ("light", "radiant", "solar", "sun")):
                damage += 1
            if skill.effect in {"cleanse", "guard"} or skill.zone_type == "light" or any(word in lowered for word in ("light", "radiant", "solar", "sun")):
                mp_cost = max(0, mp_cost - 1)
        elif subclass == "Shadow" and (skill.status == "vulnerable" or skill.zone_status == "vulnerable" or skill.zone_type == "shadow" or "shadow" in lowered or "umbral" in lowered):
            damage += 2 if skill.effect == "damage" else 0

        class_name = str(self.combat_progress_for_key("player").get("class", "Vanguard"))
        synergy = self.dungeon_build_synergy_tier(class_name, subclass)
        if synergy >= 2:
            if class_name == "Vanguard":
                if skill.effect == "guard":
                    mp_cost = max(0, mp_cost - 1)
                if skill.effect == "damage" and (skill.status in {"vulnerable", "root"} or combo_ap_gain or "Command" in skill.name or "Breaker" in skill.name):
                    damage += 1
            elif class_name == "Ranger":
                if skill.effect == "damage" and (skill.status or skill.shape == "multishot" or "Shot" in skill.name or "Trap" in skill.name):
                    damage += 1
                status_duration += 1 if skill.status in {"poison", "root", "vulnerable"} else 0
            elif class_name == "Guardian":
                heal_amount += 2 if skill.effect == "heal" else 0
                if skill.effect in {"heal", "guard", "cleanse"} and mp_cost > 0:
                    mp_cost -= 1
                zone_status_duration += 1 if skill.zone_status == "root" else 0
            elif class_name == "Mystic":
                if skill.zone_type:
                    zone_duration += 1
                    zone_damage += 1 if zone_damage else 0
                damage += 1 if skill.effect == "damage" and (skill.status or skill.zone_type) else 0
            elif class_name == "Duelist":
                if skill.effect == "damage" and (skill.shape in {"point", "multishot"} or skill.combo_any_status or skill.combo_guarded):
                    damage += 1
                combo_damage_bonus += 1 if combo_damage_bonus else 0
            elif class_name == "Alchemist":
                zone_duration += 1 if skill.zone_type else 0
                status_duration += 1 if skill.status in {"poison", "root", "vulnerable"} else 0
                zone_status_duration += 1 if skill.zone_status else 0
            elif bool(tactical_class_defs().get(class_name, {}).get("custom", False)):
                damage += 1 if skill.effect == "damage" else 0
                heal_amount += 2 if skill.effect == "heal" else 0
                if skill.effect in {"guard", "cleanse", "restore_mp"} and mp_cost > 0:
                    mp_cost -= 1
        elif synergy == 1 and skill.effect == "damage" and (skill.status or skill.zone_type):
            damage += 1
        if rank >= 3 and mp_cost > 0:
            mp_cost -= 1
        return replace(
            skill,
            damage=damage,
            heal_amount=heal_amount,
            mp_amount=mp_amount,
            status_duration=status_duration,
            mp_cost=mp_cost,
            combo_damage_bonus=combo_damage_bonus,
            combo_heal_bonus=combo_heal_bonus,
            combo_ap_gain=combo_ap_gain,
            combo_mp_gain=combo_mp_gain,
            zone_duration=zone_duration,
            zone_damage=zone_damage,
            zone_status_duration=zone_status_duration,
        )

    def dungeon_available_skills(self) -> List[Skill]:
        catalog = self.dungeon_skill_catalog()
        return [self.dungeon_effective_skill(catalog[name]) for name in self.dungeon_known_skill_names() if name in catalog]

    def dungeon_skill_shape_label(self, skill: Skill) -> str:
        if skill.shape == "support":
            return "support"
        if skill.shape == "burst":
            return f"burst r{skill.aoe_radius}"
        if skill.shape == "multishot":
            return f"{skill.shots}-shot"
        if skill.shape == "cone":
            return f"cone w{skill.width}"
        if skill.shape == "custom":
            anchor = "caster" if skill.pattern_anchor == "caster" else "target"
            return f"drawn {len(skill.custom_pattern)}-tile/{anchor}"
        return str(skill.shape)

    def dungeon_skill_special_label(self, skill: Skill) -> str:
        parts = []
        if int(skill.armor_pierce) > 0:
            parts.append(f"pierce {skill.armor_pierce}")
        if int(skill.displacement) > 0:
            parts.append(f"push {skill.displacement}")
        elif int(skill.displacement) < 0:
            parts.append(f"pull {abs(skill.displacement)}")
        if int(skill.life_steal) > 0:
            parts.append(f"drain {skill.life_steal}")
        if skill.combo_status:
            parts.append(f"combo on {skill.combo_status}")
        elif skill.combo_any_status:
            parts.append("combo on any status")
        elif skill.combo_guarded:
            parts.append("combo while guarded")
        return ", ".join(parts)

    def dungeon_cardinal_direction(self, origin: Tuple[int, int], target: Tuple[int, int]) -> Tuple[int, int]:
        dx, dy = int(target[0]) - int(origin[0]), int(target[1]) - int(origin[1])
        if abs(dx) >= abs(dy) and dx:
            return (1 if dx > 0 else -1, 0)
        if dy:
            return (0, 1 if dy > 0 else -1)
        return (0, -1)

    def dungeon_skill_affected_tiles(
        self, origin: Tuple[int, int], target: Tuple[int, int], skill: Skill,
    ) -> Set[Tuple[int, int]]:
        if self.dungeon_distance(origin, target) > max(1, int(skill.range_max)):
            return set()
        shape = str(skill.shape)
        tiles: Set[Tuple[int, int]] = set()
        if shape == "custom" and skill.custom_pattern:
            direction = self.dungeon_cardinal_direction(origin, target)
            base = origin if skill.pattern_anchor == "caster" else target
            for raw_dx, raw_dy in skill.custom_pattern:
                dx, dy = int(raw_dx), int(raw_dy)
                if skill.pattern_rotate:
                    if direction == (0, 1):
                        dx, dy = -dy, dx
                    elif direction == (-1, 0):
                        dx, dy = -dx, -dy
                    elif direction == (0, -1):
                        dx, dy = dy, -dx
                tiles.add((base[0] + dx, base[1] + dy))
        elif shape == "point":
            tiles = {target}
        elif shape == "burst":
            radius = max(0, int(skill.aoe_radius))
            tiles = {
                (target[0] + dx, target[1] + dy)
                for dx in range(-radius, radius + 1)
                for dy in range(-radius, radius + 1)
                if abs(dx) + abs(dy) <= radius
            }
        elif shape == "cross":
            tiles = {origin}
            for distance in range(1, max(1, int(skill.range_max)) + 1):
                tiles.update((origin[0] + dx * distance, origin[1] + dy * distance) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        elif shape in {"strip", "cone"}:
            direction = self.dungeon_cardinal_direction(origin, target)
            perpendicular = (-direction[1], direction[0])
            for step in range(1, max(1, int(skill.range_max)) + 1):
                spread = max(0, int(skill.width) // 2) if shape == "strip" else min(step, max(1, int(skill.width)))
                for offset in range(-spread, spread + 1):
                    tiles.add((
                        origin[0] + direction[0] * step + perpendicular[0] * offset,
                        origin[1] + direction[1] * step + perpendicular[1] * offset,
                    ))
        elif shape == "multishot":
            tiles = {
                (target[0] + dx, target[1] + dy)
                for dx in range(-2, 3)
                for dy in range(-2, 3)
                if abs(dx) + abs(dy) <= 2
            }
        else:
            tiles = {target}
        return {
            (x, y) for x, y in tiles
            if self.in_active_bounds(x, y)
            and not self.dungeon_terrain_blocks_sight(x, y)
            and not self.dungeon_door_closed(x, y)
            and self.dungeon_has_line_of_sight(origin, (x, y))
        }

    def dungeon_skill_targets(
        self, origin: Tuple[int, int], target: Tuple[int, int], skill: Skill,
    ) -> List[Dict[str, object]]:
        tiles = self.dungeon_skill_affected_tiles(origin, target, skill)
        candidates = [
            self.ensure_dungeon_roguelike_enemy(enemy)
            for enemy in self.map_combat_enemies()
            if (int(enemy.get("x", -99)), int(enemy.get("y", -99))) in tiles
        ]
        if skill.shape == "multishot":
            candidates = [
                enemy for enemy in candidates
                if self.dungeon_distance(origin, (int(enemy.get("x", 0)), int(enemy.get("y", 0)))) <= int(skill.range_max)
            ]
            candidates.sort(key=lambda enemy: (
                int(enemy.get("hp", 1)) > int(skill.damage),
                int(enemy.get("hp", 1)),
                self.dungeon_distance(target, (int(enemy.get("x", 0)), int(enemy.get("y", 0)))),
            ))
            return candidates[: max(1, int(skill.shots))]
        return candidates

    def dungeon_apply_skill_displacement(self, enemy: Dict[str, object], distance: int) -> int:
        distance = int(distance)
        if distance == 0 or int(enemy.get("hp", 0)) <= 0:
            return 0
        origin = (int(self.state.player_x), int(self.state.player_y))
        position = (int(enemy.get("x", 0)), int(enemy.get("y", 0)))
        direction = self.dungeon_cardinal_direction(origin, position)
        if distance < 0:
            direction = (-direction[0], -direction[1])
        moved = 0
        for _step in range(abs(distance)):
            destination = (int(enemy.get("x", 0)) + direction[0], int(enemy.get("y", 0)) + direction[1])
            if not self.map_combat_enemy_passable_tile(
                destination[0], destination[1], ignore_enemy_id=str(enemy.get("id", "")),
            ):
                break
            enemy["x"], enemy["y"] = destination
            moved += 1
        return moved

    def dungeon_skill_zones(self) -> List[Dict[str, object]]:
        zones = self.dungeon_roguelike_record().setdefault("skill_zones", [])
        if not isinstance(zones, list):
            zones = []
            self.dungeon_roguelike_record()["skill_zones"] = zones
        return zones

    def dungeon_skill_zone_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        floor = self.map_combat_floor()
        for zone in reversed(self.dungeon_skill_zones()):
            if int(zone.get("floor", 0)) != floor or int(zone.get("duration", 0)) <= 0:
                continue
            if any(
                isinstance(tile, (list, tuple)) and len(tile) == 2
                and (int(tile[0]), int(tile[1])) == (int(x), int(y))
                for tile in zone.get("tiles", [])
            ):
                return zone
        return None

    def render_dungeon_skill_zone(self, x: int, y: int) -> Optional[str]:
        zone = self.dungeon_skill_zone_at(x, y)
        if not zone:
            return None
        glyph, color = {
            "fire": ("f", C.PLACEMENT),
            "frost": ("i", C.WATER),
            "storm": ("s", C.LAMP),
            "earth": ("e", C.CROP_READY),
            "poison": ("p", C.CROP_READY),
            "light": ("l", C.LIT),
            "shadow": ("d", C.PLACEMENT),
        }.get(str(zone.get("kind", "")), ("z", C.PLACEMENT))
        return colorize(glyph, color)

    def dungeon_floor_loot(self, floor: Optional[int] = None) -> List[Dict[str, object]]:
        if self.on_wilderness():
            loot_by_chunk = getattr(self.state, "wilderness_field_loot", None)
            if not isinstance(loot_by_chunk, dict):
                loot_by_chunk = {}
                self.state.wilderness_field_loot = loot_by_chunk
            chunk_key = f"{int(self.state.wilderness_chunk_x)},{int(self.state.wilderness_chunk_y)}"
            piles = loot_by_chunk.setdefault(chunk_key, [])
            if not isinstance(piles, list):
                piles = []
                loot_by_chunk[chunk_key] = piles
            return piles
        record = self.dungeon_record(str(self.state.current_dungeon_key))
        floors = record.setdefault("floor_loot", {})
        if not isinstance(floors, dict):
            floors = {}
            record["floor_loot"] = floors
        floor_key = str(max(1, int(floor if floor is not None else self.state.current_dungeon_floor)))
        piles = floors.setdefault(floor_key, [])
        if not isinstance(piles, list):
            piles = []
            floors[floor_key] = piles
        return piles

    def dungeon_floor_loot_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        for pile in self.dungeon_floor_loot():
            if int(pile.get("x", -1)) == int(x) and int(pile.get("y", -1)) == int(y):
                return pile
        return None

    def dungeon_drop_loot(self, x: int, y: int, species: str, boss: bool = False) -> Dict[str, object]:
        base = str(species).replace("Elite ", "").strip()
        profile = loot_profile_for_enemy(base)
        raw = dict(profile.get("common", {}) or {})
        roll = random.random()
        if roll < 0.32:
            for item, qty in (profile.get("uncommon", {}) or {}).items():
                raw[str(item)] = raw.get(str(item), 0) + int(qty)
                break
        if roll < 0.08:
            for item, qty in (profile.get("rare", {}) or {}).items():
                raw[str(item)] = raw.get(str(item), 0) + int(qty)
                break
        money, items = translated_battle_loot(raw)
        if not raw:
            items = {"Ruin Scrap": 1}
        pile = {
            "x": int(x), "y": int(y), "source": str(species),
            "money": int(money), "items": {str(k): int(v) for k, v in items.items() if int(v) > 0},
            "boss": bool(boss),
        }
        self.dungeon_floor_loot().append(pile)
        return pile

    def collect_dungeon_loot_at(self, x: int, y: int, announce: bool = True) -> bool:
        pile = self.dungeon_floor_loot_at(x, y)
        if not pile:
            return False
        money = max(0, int(pile.get("money", 0)))
        items = dict(pile.get("items", {}) or {})
        self.state.money += money
        pile["money"] = 0
        collected_items: Dict[str, int] = {}
        remaining_items: Dict[str, int] = {}
        for item_name, quantity in items.items():
            quantity = max(0, int(quantity or 0))
            fit = min(quantity, max(0, int(self.backpack_fit_quantity(item_name)))) if hasattr(self, "backpack_fit_quantity") else quantity
            before = int(self.state.inventory.get(item_name, 0) or 0)
            self.state.inventory[item_name] = before + fit
            accepted = max(0, int(self.state.inventory.get(item_name, 0) or 0) - before)
            if accepted:
                collected_items[item_name] = accepted
            if quantity > accepted:
                remaining_items[item_name] = quantity - accepted
        pile["items"] = remaining_items
        if not remaining_items:
            self.dungeon_floor_loot().remove(pile)
        parts = []
        if money:
            parts.append(f"{money}g")
        if collected_items:
            parts.append(format_drops(collected_items))
        message = f"Collected {', '.join(parts) or 'the remains'} from {pile.get('source', 'an enemy')}."
        if remaining_items:
            message += " Your backpack is full; the rest remains on the body."
        if announce:
            self.autosave_with_message(message)
        else:
            self.dungeon_combat_note(message)
        return True

    def wilderness_field_defeat_enemy(self, enemy: Dict[str, object], attacker: str = "You") -> None:
        species = str(enemy.get("species", "enemy"))
        x, y = int(enemy.get("x", 0)), int(enemy.get("y", 0))
        depth = max(1, int(enemy.get("floor", 1) or 1))
        boss = bool(enemy.get("boss", False))
        kind = str(enemy.get("field_combat_kind", "encounter"))
        self.map_combat_remove_enemy(enemy)
        pile = self.dungeon_drop_loot(x, y, species, boss)
        exp_gain = mine_combat_exp_for_defeated([species], depth)
        if boss:
            exp_gain += 10 + min(20, depth // 2)
        _amount, level_lines = grant_combat_exp(self.state, exp_gain)
        self.state.mine_combat_victories += 1
        self.state.mine_enemies_defeated += 1
        self.dungeon_combat_note(
            f"{attacker} defeated {species}; its loot remains on the ground (+{exp_gain} EXP)."
        )
        for line in level_lines:
            self.dungeon_combat_note(line)

        completion_lines: List[str] = []
        if kind == "stronghold":
            completion_lines.extend(self.clear_wilderness_stronghold_if_empty(
                int(enemy.get("chunk_x", self.state.wilderness_chunk_x)),
                int(enemy.get("chunk_y", self.state.wilderness_chunk_y)),
            ))
        elif kind == "bounty":
            completion_lines.append("The bounty is defeated. Return to a bounty board to claim the posted reward.")
        elif kind == "encounter":
            resolver = getattr(self, "resolve_wilderness_random_combat_encounter_if_clear", None)
            if callable(resolver):
                completion_lines.extend(resolver(enemy))
        for line in completion_lines:
            self.dungeon_combat_note(line)

        remaining_alerted = [
            current for current in self.wilderness_field_combat_enemies()
            if bool(current.get("alert", False))
        ]
        if not remaining_alerted:
            relationship_lines = self.grant_party_relationship_after_battle("victory")
            relationship_lines.extend(self.companion_after_battle_lines("victory"))
            for line in relationship_lines:
                self.dungeon_combat_note(line)
            messages = list(getattr(self, "_dungeon_turn_messages", []) or [])
            self.end_wilderness_field_combat(" ".join(messages[-5:]) or "The hostile group is defeated.")

    def dungeon_defeat_enemy(self, enemy: Dict[str, object], attacker: str = "You") -> None:
        if self.wilderness_field_combat_active():
            self.wilderness_field_defeat_enemy(enemy, attacker)
            return
        species = str(enemy.get("species", "enemy"))
        x, y = int(enemy.get("x", 0)), int(enemy.get("y", 0))
        key = str(enemy.get("dungeon_key", self.state.current_dungeon_key))
        floor = max(1, int(enemy.get("dungeon_floor", self.state.current_dungeon_floor)))
        depth = max(1, int(enemy.get("floor", self.dungeon_combat_depth(key, floor))))
        boss = bool(enemy.get("boss", False))
        self.remove_wilderness_dungeon_enemy(enemy)
        pile = self.dungeon_drop_loot(x, y, species, boss)
        exp_gain = mine_combat_exp_for_defeated([species], depth) + (18 + self.dungeon_tier_for_key(key) * 4 if boss else 0)
        _amount, level_lines = grant_combat_exp(self.state, exp_gain)
        self.state.mine_combat_victories += 1
        self.state.mine_enemies_defeated += 1
        self.dungeon_combat_note(f"{attacker} defeated {species}; its loot remains on the floor (+{exp_gain} EXP).")
        for line in level_lines:
            self.dungeon_combat_note(line)
        if boss:
            boss_money, boss_items = self.wilderness_dungeon_boss_reward(key, floor)
            pile["money"] = int(pile.get("money", 0)) + boss_money
            merged = dict(pile.get("items", {}) or {})
            for item, qty in boss_items.items():
                merged[item] = int(merged.get(item, 0)) + int(qty)
            pile["items"] = merged
            record = self.dungeon_record(key)
            final_boss = bool(enemy.get("final_boss", floor >= self.dungeon_max_floor_for_key(key)))
            if final_boss:
                record["boss_defeated"] = True
                record["cleared"] = True
                for clear_floor in range(1, self.dungeon_max_floor_for_key(key) + 1):
                    self.wilderness_dungeon_enemies[self.dungeon_enemy_floor_key(key, clear_floor)] = []
                self.dungeon_combat_note(f"The final guardian falls. {self.dungeon_name_for_key(key)} is now cleared.")
            else:
                guardians = {
                    int(value)
                    for value in record.get("defeated_guardians", [])
                    if str(value).isdigit()
                }
                guardians.add(floor)
                record["defeated_guardians"] = sorted(guardians)
                self.dungeon_combat_note(
                    f"The stratum guardian falls. The route to floor {floor + 1} is secure."
                )

    def dungeon_resolve_player_attack(
        self,
        enemy: Dict[str, object],
        *,
        multiplier: float = 1.0,
        ranged: bool = False,
        armor_pierce: int = 0,
        label: str = "attack",
        attacker_name: str = "You",
        attack_value: Optional[int] = None,
        advance_turn: bool = True,
    ) -> bool:
        if not enemy or enemy.get("defeated"):
            return False
        enemy = self.ensure_dungeon_roguelike_enemy(enemy)
        profile = farmstead_combat_profile(self.state)
        attack = max(1, int(profile["attack"]) if attack_value is None else int(attack_value))
        origin = (int(self.state.player_x), int(self.state.player_y))
        if attacker_name != "You":
            follower_id = str(enemy.get("_attacker_follower_id", ""))
            follower_position = self.travel_follower_position(follower_id) if follower_id else None
            if follower_position:
                origin = follower_position
        distance = self.dungeon_distance(origin, (int(enemy["x"]), int(enemy["y"])))
        cover = self.dungeon_terrain_cover(int(enemy["x"]), int(enemy["y"])) if ranged else 0.0
        hit_chance = 0.95 - float(enemy.get("dodge", 0.0)) - cover - (max(0, distance - 2) * 0.025 if ranged else 0.0)
        if random.random() > max(0.55, hit_chance):
            owner = "Your" if attacker_name == "You" else f"{attacker_name}'s"
            self.dungeon_combat_note(f"{owner} {label} misses {enemy.get('species', 'the enemy')}.")
        else:
            critical = random.random() < 0.10
            if label == "Arc Bolt" and self.dungeon_terrain_tile(int(enemy["x"]), int(enemy["y"])) == ";":
                multiplier += 0.25
                armor_pierce += 1
                self.dungeon_combat_note("Crystal debris amplifies the Arc Bolt.")
            defense = max(0, int(enemy.get("defense", 0)) - int(armor_pierce))
            vulnerable = int(enemy.setdefault("statuses", {}).get("vulnerable", 0)) > 0
            damage = max(1, int((attack + random.randint(-1, 2)) * float(multiplier)) - defense + (1 if vulnerable else 0))
            if critical:
                damage = max(damage + 1, int(damage * 1.5))
            enemy["hp"] = max(0, int(enemy["hp"]) - damage)
            enemy["alert"] = True
            suffix = " critical" if critical else ""
            owner = "Your" if attacker_name == "You" else f"{attacker_name}'s"
            self.dungeon_combat_note(
                f"{owner}{suffix} {label} deals {damage} to {enemy.get('species')} "
                f"({enemy['hp']}/{enemy['max_hp']} HP)."
            )
            if int(enemy["hp"]) <= 0:
                self.dungeon_defeat_enemy(enemy, attacker_name)
        noise_radius = 8 if ranged else 5
        self.dungeon_emit_noise(origin[0], origin[1], noise_radius, label=label)
        if advance_turn and self.map_native_combat_active():
            self.advance_dungeon_roguelike_turn(label)
        return True

    def dungeon_player_melee_attack(self, enemy: Dict[str, object], *, multiplier: float = 1.0, label: str = "melee attack", armor_pierce: int = 0) -> bool:
        self._dungeon_turn_messages = []
        return self.dungeon_resolve_player_attack(
            enemy, multiplier=multiplier, label=label, armor_pierce=armor_pierce, advance_turn=True
        )

    def dungeon_nearest_enemy(self, origin: Tuple[int, int], max_range: int = 99, alerted_only: bool = False) -> Optional[Dict[str, object]]:
        candidates = []
        for enemy in self.map_combat_enemies():
            if alerted_only and not enemy.get("alert"):
                continue
            distance = self.dungeon_distance(origin, (int(enemy.get("x", -99)), int(enemy.get("y", -99))))
            if distance <= int(max_range):
                candidates.append((distance, 0 if enemy.get("alert") else 1, str(enemy.get("id", "")), enemy))
        return min(candidates, default=(0, 0, "", None))[3]

    def dungeon_companion_turns(self) -> None:
        enemies = self.map_combat_enemies()
        if not enemies:
            return
        combat = self.dungeon_roguelike_record()
        combat["guardian_guard"] = 0
        cooldowns = combat.setdefault("companion_cooldowns", {})
        for companion in self.active_farmstead_companion_profiles():
            if not enemies:
                break
            runtime = self.dungeon_companion_runtime(companion)
            if int(runtime.get("hp", 0)) <= 0:
                continue
            name = str(companion.get("name", "Companion"))
            attack = max(2, int(companion.get("attack", 3)))
            max_range = max(1, int(companion.get("weapon_range_max", 1)))
            follower_id = str(companion.get("id", ""))
            cooldown_key = follower_id or str(companion.get("npc_id", name))
            origin = self.travel_follower_position(follower_id) or (
                int(self.state.player_x), int(self.state.player_y)
            )
            role = str(companion.get("expedition_role", "Balanced"))
            if role == "Guardian" and self.dungeon_distance(origin, (self.state.player_x, self.state.player_y)) <= 1:
                combat["guardian_guard"] = max(2, int(combat.get("guardian_guard", 0)))
            if role == "Support" and int(cooldowns.get(cooldown_key, -99)) + 6 <= int(combat.get("turn", 0)):
                profile = farmstead_combat_profile(self.state)
                if int(self.state.combat_current_hp) <= int(profile["max_hp"]) * 0.55:
                    before = int(self.state.combat_current_hp)
                    self.state.combat_current_hp = min(int(profile["max_hp"]), before + 4)
                    cooldowns[cooldown_key] = int(combat.get("turn", 0))
                    self.dungeon_combat_note(f"{name} steadies you, restoring {self.state.combat_current_hp - before} HP.")
                    continue
            effective_range = max_range + (1 if role == "Scout" and max_range > 1 else 0)
            target = self.dungeon_nearest_enemy(origin, max(1, effective_range), alerted_only=True)
            if not target:
                self.dungeon_reposition_companion(follower_id, companion, origin)
                continue
            tx, ty = int(target.get("x", 0)), int(target.get("y", 0))
            if effective_range > 1 and not self.dungeon_has_line_of_sight(origin, (tx, ty)):
                self.dungeon_reposition_companion(follower_id, companion, origin)
                continue
            target["_attacker_follower_id"] = follower_id
            self.dungeon_resolve_player_attack(
                target,
                multiplier=0.82 if role == "Scout" else 0.72,
                ranged=effective_range > 1,
                armor_pierce=1 if role == "Gatherer" else 0,
                label="support shot" if max_range > 1 else "support strike",
                attacker_name=name,
                attack_value=attack,
                advance_turn=False,
            )
            target.pop("_attacker_follower_id", None)
            enemies = self.map_combat_enemies()

    def dungeon_reposition_companion(
        self, follower_id: str, companion: Dict[str, object], origin: Tuple[int, int]
    ) -> bool:
        if not follower_id or self.travel_follower_position(follower_id) is None:
            return False
        target = self.dungeon_nearest_enemy(origin, 99, alerted_only=True)
        if not target:
            return False
        max_range = max(1, int(companion.get("weapon_range_max", 1)))
        role = str(companion.get("expedition_role", "Balanced"))
        effective_range = max_range + (1 if role == "Scout" and max_range > 1 else 0)
        desired = min(3, effective_range) if effective_range > 1 else 1
        tx, ty = int(target["x"]), int(target["y"])
        occupied = self.travel_follower_occupied_positions(follower_id)

        def available(x: int, y: int) -> bool:
            return (
                self.travel_follower_tile_available(
                    follower_id,
                    x,
                    y,
                    occupied_positions=occupied,
                )
                and self.dungeon_terrain_tile(x, y) != "!"
            )

        candidates = []
        radius = max(7, effective_range + 3)
        for ny in range(max(0, ty - radius), min(self.active_map_height(), ty + radius + 1)):
            for nx in range(max(0, tx - radius), min(self.active_map_width(), tx + radius + 1)):
                if not available(nx, ny):
                    continue
                enemy_distance = self.dungeon_distance((nx, ny), (tx, ty))
                if effective_range <= 1:
                    if enemy_distance != 1:
                        continue
                elif not (2 <= enemy_distance <= effective_range):
                    continue
                if effective_range > 1 and not self.dungeon_has_line_of_sight((nx, ny), (tx, ty)):
                    continue
                player_distance = self.dungeon_distance(
                    (nx, ny), (self.state.player_x, self.state.player_y)
                )
                tile = self.dungeon_terrain_tile(nx, ny)
                cover_bonus = -3 if effective_range > 1 and self.dungeon_terrain_cover(nx, ny) else 0
                terrain_penalty = 3 if tile in {"~", "'", '"'} else 0
                role_bias = max(0, player_distance - 2) if role in {"Guardian", "Support"} else 0
                score = (
                    abs(enemy_distance - desired) * 3
                    + terrain_penalty
                    + role_bias
                    + cover_bonus
                )
                candidates.append((score, player_distance, ny, nx))
        if not candidates:
            return False
        candidates.sort()
        goals = [(nx, ny) for _score, _player_distance, ny, nx in candidates[:12]]
        step = shortest_path_step(
            origin,
            goals,
            available,
            max_nodes=max(512, self.active_map_width() * self.active_map_height()),
        )
        if step is None:
            return False
        record = self.travel_follower_record(follower_id)
        record["x"], record["y"] = int(step[0]), int(step[1])
        record["activity"] = (
            "moving into cover"
            if effective_range > 1 and self.dungeon_terrain_cover(*step)
            else "taking a tactical position"
        )
        return True

    def dungeon_enemy_attack_player(
        self, enemy: Dict[str, object], ranged: bool = False, multiplier: float = 1.0,
        attack_name: str = "",
    ) -> None:
        enemy = self.ensure_dungeon_roguelike_enemy(enemy)
        profile = farmstead_combat_profile(self.state)
        combat = self.dungeon_roguelike_record()
        guard = int(combat.get("guard_turns", 0)) > 0
        guardian_guard = max(0, int(combat.get("guardian_guard", 0)))
        defense = int(profile["defense"]) + (3 if guard else 0) + guardian_guard
        species = str(enemy.get("species", "Enemy"))
        if ranged:
            cover = self.dungeon_terrain_cover(int(self.state.player_x), int(self.state.player_y))
            hit_chance = max(0.45, 0.90 - cover)
            if random.random() > hit_chance:
                self.dungeon_combat_note(f"{species}'s {attack_name or 'shot'} is lost in your cover.")
                return
        damage = max(1, int((int(enemy.get("attack", 4)) + random.randint(-1, 1)) * multiplier) - defense)
        if ranged:
            damage = max(1, damage - 1)
        self.state.combat_current_hp = max(0, int(self.state.combat_current_hp) - damage)
        action = attack_name or ("shot" if ranged else "attack")
        self.dungeon_combat_note(f"{species}'s {action} deals {damage} ({self.state.combat_current_hp}/{profile['max_hp']} HP).")
        if str(enemy.get("behavior", "")) == "poisoner" and random.random() < 0.28:
            combat["poison_turns"] = max(int(combat.get("poison_turns", 0)), 3)
            self.dungeon_combat_note("Poison clings to you for 3 turns.")

    def dungeon_enemy_next_step(
        self, enemy: Dict[str, object], target: Optional[Tuple[int, int]] = None,
        adjacent: bool = True,
    ) -> Optional[Tuple[int, int]]:
        start = (int(enemy.get("x", 0)), int(enemy.get("y", 0)))
        target = target or (int(self.state.player_x), int(self.state.player_y))
        goals = (
            {(target[0] + dx, target[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
            if adjacent else {target}
        )
        queue = deque([start])
        previous: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
        found = None
        while queue and len(previous) < 360:
            point = queue.popleft()
            if point in goals:
                found = point
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (point[0] + dx, point[1] + dy)
                if nxt in previous:
                    continue
                if not self.dungeon_enemy_navigation_passable(enemy, nxt[0], nxt[1]):
                    continue
                previous[nxt] = point
                queue.append(nxt)
        if found is None:
            return None
        while previous.get(found) not in {None, start}:
            found = previous[found]
        return found if previous.get(found) == start else None

    def dungeon_enemy_navigation_passable(self, enemy: Dict[str, object], x: int, y: int) -> bool:
        if self.dungeon_door_closed(x, y):
            if (x, y) == (int(self.state.player_x), int(self.state.player_y)):
                return False
            if self.travel_follower_at(x, y):
                return False
            occupant = self.map_combat_enemy_at(x, y)
            return not occupant or str(occupant.get("id", "")) == str(enemy.get("id", ""))
        return self.map_combat_enemy_passable_tile(
            x, y, ignore_enemy_id=str(enemy.get("id", ""))
        )

    def dungeon_enemy_apply_step(self, enemy: Dict[str, object], step: Tuple[int, int]) -> bool:
        if self.dungeon_door_closed(*step):
            self.dungeon_set_door_closed(step[0], step[1], False)
            self.dungeon_combat_note(f"{enemy.get('species')} forces the door open.")
            self.dungeon_emit_noise(step[0], step[1], 4, label="a forced door")
            return False
        enemy["x"], enemy["y"] = int(step[0]), int(step[1])
        self.dungeon_enemy_trigger_trap(enemy)
        return True

    def dungeon_enemy_take_turn(self, enemy: Dict[str, object], turn: int) -> None:
        if not self.map_native_combat_active() or enemy not in self.map_combat_enemies():
            return
        enemy = self.ensure_dungeon_roguelike_enemy(enemy)
        statuses = enemy.setdefault("statuses", {})
        rooted = max(0, int(statuses.get("root", 0)))
        if rooted:
            statuses["root"] = rooted - 1
        vulnerable = max(0, int(statuses.get("vulnerable", 0)))
        if vulnerable:
            statuses["vulnerable"] = vulnerable - 1
        poison = max(0, int(statuses.get("poison", 0)))
        if poison:
            statuses["poison"] = poison - 1
            enemy["hp"] = max(0, int(enemy["hp"]) - 1)
            self.dungeon_combat_note(
                f"Poison deals 1 to {enemy.get('species')} ({enemy['hp']}/{enemy['max_hp']} HP)."
            )
            if int(enemy["hp"]) <= 0:
                self.dungeon_defeat_enemy(enemy, "Poison")
                return
        if int(statuses.get("stunned", 0)) > 0:
            statuses["stunned"] = int(statuses["stunned"]) - 1
            self.dungeon_combat_note(f"{enemy.get('species')} is stunned.")
            return
        ex, ey = int(enemy["x"]), int(enemy["y"])
        intent = enemy.get("intent", {}) if isinstance(enemy.get("intent"), dict) else {}
        if intent:
            intent_type = str(intent.get("type", ""))
            marked_position = (int(intent.get("x", -99)), int(intent.get("y", -99)))
            intended_actor = self.dungeon_target_by_identity(
                str(intent.get("target_kind", "player")), str(intent.get("target_id", ""))
            )
            current_position = intended_actor.get("position") if intended_actor else None
            if intent_type == "shot":
                if intended_actor and current_position == marked_position and self.dungeon_has_line_of_sight((ex, ey), current_position):
                    self.dungeon_enemy_attack_target(
                        enemy, intended_actor, ranged=True,
                        attack_name=str(intent.get("name", "aimed shot")),
                    )
                else:
                    self.dungeon_combat_note(f"{enemy.get('species')}'s aimed attack strikes empty ground.")
            elif intent_type == "heavy":
                if intended_actor and current_position == marked_position and self.dungeon_distance((ex, ey), current_position) == 1:
                    self.dungeon_enemy_attack_target(
                        enemy, intended_actor, multiplier=1.65, attack_name="heavy blow",
                    )
                else:
                    self.dungeon_combat_note(f"{enemy.get('species')}'s heavy blow misses its marked tile.")
            elif intent_type == "spores":
                if intended_actor and current_position == marked_position and self.dungeon_distance((ex, ey), current_position) <= 1:
                    self.dungeon_enemy_attack_target(
                        enemy, intended_actor, multiplier=0.75, attack_name="spore burst",
                    )
                    if str(intended_actor.get("kind", "player")) == "player":
                        self.dungeon_roguelike_record()["poison_turns"] = max(
                            3, int(self.dungeon_roguelike_record().get("poison_turns", 0))
                        )
                else:
                    self.dungeon_combat_note("The spore cloud blooms over an empty tile.")
            enemy["intent"] = {}
            return
        if enemy.get("slow") and turn % 2 == 0:
            return
        perception = 10 if enemy.get("boss") else 7
        visible_target = self.dungeon_enemy_visible_target(enemy, perception)
        if visible_target:
            target_position = visible_target["position"]
            enemy["alert"] = True
            enemy["heard_x"], enemy["heard_y"] = target_position
            enemy["search_turns"] = max(2, int(enemy.get("search_turns", 0)))
            enemy["target_kind"] = str(visible_target.get("kind", "player"))
            enemy["target_id"] = str(visible_target.get("id", "player"))
        if not enemy.get("alert"):
            if random.random() < 0.18:
                options = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                random.shuffle(options)
                for dx, dy in options:
                    if self.map_combat_enemy_passable_tile(ex + dx, ey + dy, ignore_enemy_id=str(enemy.get("id", ""))):
                        self.dungeon_enemy_apply_step(enemy, (ex + dx, ey + dy))
                        break
            return
        behavior = str(enemy.get("behavior", "hunter"))
        attack_range = max(1, int(enemy.get("attack_range", 1)))
        heard = (enemy.get("heard_x"), enemy.get("heard_y"))
        target_position = visible_target["position"] if visible_target else (
            (int(heard[0]), int(heard[1])) if heard[0] is not None and heard[1] is not None
            else (int(self.state.player_x), int(self.state.player_y))
        )
        distance = self.dungeon_distance((ex, ey), target_position)
        if distance == 1:
            if not visible_target:
                visible_target = self.dungeon_target_by_identity(
                    str(enemy.get("target_kind", "player")), str(enemy.get("target_id", ""))
                )
                if not visible_target or visible_target["position"] != target_position:
                    visible_target = None
            if not visible_target:
                enemy["search_turns"] = max(0, int(enemy.get("search_turns", 0)) - 1)
                return
            if behavior == "guardian":
                enemy["intent"] = {
                    "type": "heavy", "x": target_position[0], "y": target_position[1],
                    "target_kind": visible_target["kind"], "target_id": visible_target["id"],
                }
                self.dungeon_combat_note(f"{enemy.get('species')} raises its weapon for a heavy blow (!).")
                return
            if behavior == "poisoner" and random.random() < 0.45:
                enemy["intent"] = {
                    "type": "spores", "x": target_position[0], "y": target_position[1],
                    "target_kind": visible_target["kind"], "target_id": visible_target["id"],
                }
                self.dungeon_combat_note(f"{enemy.get('species')} swells with a poisonous spore cloud (!).")
                return
            self.dungeon_enemy_attack_target(enemy, visible_target, ranged=False)
            return
        if visible_target and behavior in {"archer", "shard_caster"} and 2 <= distance <= attack_range:
            name = "shard volley" if behavior == "shard_caster" else "aimed shot"
            enemy["intent"] = {
                "type": "shot", "x": target_position[0], "y": target_position[1], "name": name,
                "target_kind": visible_target["kind"], "target_id": visible_target["id"],
            }
            self.dungeon_combat_note(
                f"{enemy.get('species')} marks {visible_target.get('name', 'your position')} for an {name} (!)."
            )
            return
        if behavior == "skittish" and int(enemy["hp"]) <= max(2, int(enemy["max_hp"]) // 3):
            options = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            options.sort(key=lambda step: self.dungeon_distance((ex + step[0], ey + step[1]), target_position), reverse=True)
            for dx, dy in options:
                if self.map_combat_enemy_passable_tile(ex + dx, ey + dy, ignore_enemy_id=str(enemy.get("id", ""))):
                    self.dungeon_enemy_apply_step(enemy, (ex + dx, ey + dy))
                    self.dungeon_combat_note(f"{enemy.get('species')} retreats.")
                    return
        visible = visible_target is not None
        if rooted:
            self.dungeon_combat_note(f"{enemy.get('species')} is rooted and cannot move.")
            return
        step = self.dungeon_enemy_next_step(enemy, target=target_position, adjacent=visible)
        if step:
            moved = self.dungeon_enemy_apply_step(enemy, step)
            if moved and enemy in self.map_combat_enemies() and behavior == "darting" and turn % 3 == 0:
                second = self.dungeon_enemy_next_step(enemy, target=target_position, adjacent=visible)
                if second:
                    self.dungeon_enemy_apply_step(enemy, second)
        elif not visible:
            enemy["search_turns"] = max(0, int(enemy.get("search_turns", 0)) - 1)
            if int(enemy["search_turns"]) <= 0 and not enemy.get("boss"):
                enemy["alert"] = False
                enemy["heard_x"], enemy["heard_y"] = None, None

    def dungeon_player_defeated(self) -> None:
        self.state.mine_combat_defeats += 1
        self.state.combat_current_hp = 1
        self.advance_time(60)
        party_lines = self.companion_after_battle_lines("defeat")
        party_text = " " + " ".join(party_lines) if party_lines else ""
        if self.wilderness_field_combat_active():
            self.wilderness_field_combat_record()["active"] = False
            self.return_from_wilderness_to_town(emergency=True)
            self.autosave_with_message(
                "You collapse during the wilderness fight and wake in town with 1 HP. "
                "Surviving hostiles remain where you encountered them." + party_text
            )
            return
        self.return_from_wilderness_dungeon(
            "You collapse under the dungeon assault and wake outside with 1 HP. "
            "The surviving enemies and dropped loot remain inside." + party_text
        )

    def advance_dungeon_roguelike_turn(
        self, reason: str = "action", *, enemy_phases: int = 1,
    ) -> bool:
        if not self.map_native_combat_active():
            return False
        combat = self.dungeon_roguelike_record()
        start_turn = max(0, int(combat.get("turn", 0)))
        if not isinstance(getattr(self, "_dungeon_turn_messages", None), list):
            self._dungeon_turn_messages = []
        incidental_noise = {
            "open chest": 5,
            "inspect doorway": 3,
            "use shrine": 3,
            "read inscription": 2,
            "trigger trap": 6,
            "failed disarm": 6,
            "disarm trap": 2,
            "collect loot": 2,
        }.get(str(reason), 0)
        if incidental_noise:
            self.dungeon_emit_noise(
                int(self.state.player_x), int(self.state.player_y), incidental_noise,
                label=str(reason),
            )
        poison = max(0, int(combat.get("poison_turns", 0)))
        if poison:
            self.state.combat_current_hp = max(0, int(self.state.combat_current_hp) - 1)
            combat["poison_turns"] = poison - 1
            self.dungeon_combat_note(f"Poison deals 1 damage ({self.state.combat_current_hp} HP).")
        if int(self.state.combat_current_hp) <= 0:
            self.dungeon_player_defeated()
            return True
        self.dungeon_companion_turns()
        for phase in range(max(1, int(enemy_phases))):
            combat["turn"] = start_turn + phase + 1
            turn = int(combat["turn"])
            self.dungeon_tick_skill_zones()
            for enemy in list(self.map_combat_enemies()):
                self.dungeon_enemy_take_turn(enemy, turn)
                if int(self.state.combat_current_hp) <= 0:
                    self.dungeon_player_defeated()
                    return True
            if phase == 0 and int(enemy_phases) > 1:
                self.dungeon_combat_note("Difficult terrain gives nearby enemies time to act again.")
        turn = int(combat.get("turn", start_turn + 1))
        if int(combat.get("guard_turns", 0)) > 0:
            combat["guard_turns"] = int(combat["guard_turns"]) - 1
        for runtime in combat.setdefault("companion_states", {}).values():
            if isinstance(runtime, dict) and int(runtime.get("guard_turns", 0)) > 0:
                runtime["guard_turns"] = int(runtime["guard_turns"]) - 1
        if self.on_wilderness_dungeon():
            self.dungeon_reveal_nearby_traps(radius=1, guaranteed=False)
        if turn % 10 == 0:
            self.advance_time(1)
        messages = list(getattr(self, "_dungeon_turn_messages", []) or [])
        log = combat.setdefault("combat_log", [])
        if messages:
            log.extend(messages)
            combat["combat_log"] = log[-30:]
            self.set_message(" ".join(messages[-4:]))
        else:
            place = "Field" if self.wilderness_field_combat_active() else "Dungeon"
            self.set_message(f"{place} turn {turn}: {reason}.")
        self._dungeon_turn_messages = []
        if self.wilderness_field_combat_active():
            self.check_wilderness_field_combat_end()
        return True

    def dungeon_wait_turn(self) -> bool:
        if not self.map_native_combat_active():
            return False
        self._dungeon_turn_messages = ["You wait and listen."]
        return self.advance_dungeon_roguelike_turn("wait")

    def dungeon_quick_potion(self) -> bool:
        if not self.map_native_combat_active():
            return False
        profile = farmstead_combat_profile(self.state)
        if int(self.state.combat_current_hp) >= int(profile["max_hp"]):
            self.set_message("You are already at full HP.")
            return False
        potion = next((name for name in ("Potion", "Health Potion", "Field Snack") if int(self.state.inventory.get(name, 0)) > 0), "")
        if not potion:
            self.set_message("You have no Potion, Health Potion, or Field Snack ready.")
            return False
        self.state.inventory[potion] = max(0, int(self.state.inventory[potion]) - 1)
        heal = 18 if potion != "Field Snack" else 10
        before = int(self.state.combat_current_hp)
        self.state.combat_current_hp = min(int(profile["max_hp"]), before + heal)
        self._dungeon_turn_messages = [f"You use {potion} and recover {self.state.combat_current_hp - before} HP."]
        return self.advance_dungeon_roguelike_turn("use item")

    def dungeon_aim_attack(
        self,
        *,
        max_range: int,
        multiplier: float = 1.0,
        focus_cost: int = 0,
        label: str = "ranged attack",
        armor_pierce: int = 0,
    ) -> bool:
        if not self.map_native_combat_active():
            return False
        origin = (int(self.state.player_x), int(self.state.player_y))
        nearest = self.dungeon_nearest_enemy(origin, max_range)
        cursor_x, cursor_y = (
            (int(nearest["x"]), int(nearest["y"])) if nearest else self.target_tile_pos()
        )
        while True:
            self.set_message(
                f"Aim {label}: move cursor within {max_range} tiles; Z/Enter fire; B/X/Esc/Q/F cancel."
            )
            self.draw_with_look_cursor(cursor_x, cursor_y)
            key = normalize_key(read_key())
            if len(key) == 1 and key.isalpha():
                key = key.lower()
            if key in {"b", "x", "q", "f", "\t", "\x1b"}:
                self.set_message("Aiming cancelled.")
                self.invalidate_draw_cache()
                return False
            movement = movement_delta_for_key(key)
            if movement:
                dx, dy = movement
                candidate = (cursor_x + dx, cursor_y + dy)
                if self.in_active_bounds(*candidate) and self.dungeon_distance(origin, candidate) <= max_range:
                    cursor_x, cursor_y = candidate
                continue
            if key in MENU_CONFIRM_KEYS:
                enemy = self.map_combat_enemy_at(cursor_x, cursor_y)
                if not enemy:
                    self.set_message("There is no enemy on that tile.")
                    continue
                if self.dungeon_distance(origin, (cursor_x, cursor_y)) > max_range:
                    self.set_message("That target is out of range.")
                    continue
                if not self.dungeon_has_line_of_sight(origin, (cursor_x, cursor_y)):
                    self.set_message("Walls block the shot.")
                    continue
                if int(self.state.combat_focus) < int(focus_cost):
                    self.set_message(f"{label.title()} needs {focus_cost} MP.")
                    return False
                self.state.combat_focus = max(0, int(self.state.combat_focus) - int(focus_cost))
                self._dungeon_turn_messages = []
                self.invalidate_draw_cache()
                return self.dungeon_resolve_player_attack(
                    enemy, multiplier=multiplier, ranged=True, armor_pierce=armor_pierce,
                    label=label, advance_turn=True,
                )

    def dungeon_basic_ranged_attack(self) -> bool:
        profile = farmstead_combat_profile(self.state)
        max_range = max(1, int(profile.get("weapon_range_max", 1)))
        if max_range <= 1:
            self.set_message(
                f"Your {profile.get('weapon', 'weapon')} has no ranged reach. Press V for combat skills."
            )
            return False
        return self.dungeon_aim_attack(max_range=max_range, label=str(profile.get("weapon", "ranged weapon")))

    def dungeon_search_action(self) -> bool:
        if not self.map_native_combat_active():
            return False
        self._dungeon_turn_messages = []
        found = self.dungeon_reveal_nearby_traps(radius=3, guaranteed=True)
        if not found:
            self.dungeon_combat_note("You search the nearby floor but find no new traps.")
        return self.advance_dungeon_roguelike_turn("search")

    def dungeon_aim_noise_lure(self, max_range: int = 6) -> bool:
        if not self.map_native_combat_active():
            return False
        if int(self.state.inventory.get("Stone", 0)) <= 0:
            self.set_message("You need a Stone to create a distant distraction.")
            return False
        origin = (int(self.state.player_x), int(self.state.player_y))
        cursor_x, cursor_y = self.target_tile_pos()
        while True:
            self.set_message(
                f"Throw Stone: move cursor within {max_range} tiles; Z/Enter throw; B/X/Esc/Q cancel."
            )
            self.draw_with_look_cursor(cursor_x, cursor_y)
            key = normalize_key(read_key())
            if len(key) == 1 and key.isalpha():
                key = key.lower()
            if key in {"b", "x", "q", "\t", "\x1b"}:
                self.set_message("Stone throw cancelled.")
                self.invalidate_draw_cache()
                return False
            movement = movement_delta_for_key(key)
            if movement:
                dx, dy = movement
                candidate = (cursor_x + dx, cursor_y + dy)
                if self.in_active_bounds(*candidate) and self.dungeon_distance(origin, candidate) <= max_range:
                    cursor_x, cursor_y = candidate
                continue
            if key in MENU_CONFIRM_KEYS:
                if not self.dungeon_has_line_of_sight(origin, (cursor_x, cursor_y)):
                    self.set_message("A wall or closed door blocks that throw.")
                    continue
                self.state.inventory["Stone"] = max(0, int(self.state.inventory.get("Stone", 0)) - 1)
                self._dungeon_turn_messages = [
                    f"You throw a Stone to {cursor_x},{cursor_y}; it clatters through the ruins."
                ]
                self.dungeon_emit_noise(cursor_x, cursor_y, 7, label="a thrown stone")
                self.invalidate_draw_cache()
                return self.advance_dungeon_roguelike_turn("throw stone")

    def dungeon_skill_combo_triggered(self, skill: Skill, enemy: Dict[str, object]) -> bool:
        statuses = enemy.get("statuses", {}) if isinstance(enemy.get("statuses"), dict) else {}
        has_status = any(int(statuses.get(name, 0)) > 0 for name in ("poison", "root", "vulnerable"))
        return bool(
            (skill.combo_any_status and has_status)
            or (skill.combo_status and int(statuses.get(skill.combo_status, 0)) > 0)
            or (skill.combo_guarded and int(self.dungeon_roguelike_record().get("guard_turns", 0)) > 0)
        )

    def dungeon_apply_skill_status(self, enemy: Dict[str, object], skill: Skill) -> None:
        if not skill.status or int(skill.status_duration) <= 0:
            return
        statuses = enemy.setdefault("statuses", {})
        before = int(statuses.get(skill.status, 0))
        statuses[skill.status] = max(before, int(skill.status_duration))
        if int(statuses[skill.status]) > before:
            status_label = {
                "poison": "poisoned",
                "root": "rooted",
                "vulnerable": "made vulnerable",
            }.get(str(skill.status), f"affected by {skill.status}")
            self.dungeon_combat_note(
                f"{enemy.get('species')} is {status_label} for {statuses[skill.status]} turn"
                f"{'s' if int(statuses[skill.status]) != 1 else ''}."
            )

    def dungeon_create_skill_zone(self, skill: Skill, tiles: Set[Tuple[int, int]]) -> None:
        if not skill.zone_type or int(skill.zone_duration) <= 0 or not tiles:
            return
        zone = {
            "name": skill.name,
            "kind": str(skill.zone_type),
            "floor": self.map_combat_floor(),
            "tiles": [[int(x), int(y)] for x, y in sorted(tiles)],
            "duration": int(skill.zone_duration),
            "damage": max(0, int(skill.zone_damage)),
            "status": str(skill.zone_status),
            "status_duration": max(0, int(skill.zone_status_duration)),
        }
        self.dungeon_skill_zones().append(zone)
        self.dungeon_combat_note(
            f"{skill.name} leaves a {skill.zone_type} field for {skill.zone_duration} turns."
        )

    def dungeon_tick_skill_zones(self) -> None:
        zones = self.dungeon_skill_zones()
        floor = self.map_combat_floor()
        for zone in list(zones):
            if int(zone.get("floor", 0)) != floor or int(zone.get("duration", 0)) <= 0:
                continue
            tile_set = {
                (int(tile[0]), int(tile[1]))
                for tile in zone.get("tiles", [])
                if isinstance(tile, (list, tuple)) and len(tile) == 2
            }
            for enemy in list(self.map_combat_enemies()):
                position = (int(enemy.get("x", -99)), int(enemy.get("y", -99)))
                if position not in tile_set:
                    continue
                enemy = self.ensure_dungeon_roguelike_enemy(enemy)
                damage = max(0, int(zone.get("damage", 0)))
                if damage:
                    vulnerable = int(enemy.setdefault("statuses", {}).get("vulnerable", 0)) > 0
                    dealt = max(1, damage + (1 if vulnerable else 0) - max(0, int(enemy.get("defense", 0))))
                    enemy["hp"] = max(0, int(enemy["hp"]) - dealt)
                    self.dungeon_combat_note(
                        f"The {zone.get('kind')} field deals {dealt} to {enemy.get('species')} "
                        f"({enemy['hp']}/{enemy['max_hp']} HP)."
                    )
                status = str(zone.get("status", ""))
                status_duration = max(0, int(zone.get("status_duration", 0)))
                if status and status_duration and int(enemy.get("hp", 0)) > 0:
                    statuses = enemy.setdefault("statuses", {})
                    statuses[status] = max(int(statuses.get(status, 0)), status_duration)
                if int(enemy.get("hp", 0)) <= 0 and enemy in self.map_combat_enemies():
                    self.dungeon_defeat_enemy(enemy, f"The {zone.get('kind')} field")
            zone["duration"] = int(zone.get("duration", 0)) - 1
        zones[:] = [zone for zone in zones if int(zone.get("duration", 0)) > 0]

    def dungeon_cast_skill_at(self, skill_name: str, target: Tuple[int, int]) -> bool:
        catalog = {skill.name: skill for skill in self.dungeon_available_skills()}
        skill = catalog.get(str(skill_name))
        if not skill or skill.effect != "damage":
            self.set_message("That combat skill is not available in your current loadout.")
            return False
        if int(self.state.combat_focus) < int(skill.mp_cost):
            self.set_message(f"{skill.name} needs {skill.mp_cost} MP.")
            return False
        origin = (int(self.state.player_x), int(self.state.player_y))
        if self.dungeon_distance(origin, target) > max(1, int(skill.range_max)):
            self.set_message(f"{skill.name} only reaches {skill.range_max} tiles.")
            return False
        if skill.shape != "cross" and not self.dungeon_has_line_of_sight(origin, target):
            self.set_message("A wall or closed door blocks that skill.")
            return False
        targets = self.dungeon_skill_targets(origin, target, skill)
        if not targets:
            self.set_message(f"{skill.name} would hit no enemies there.")
            return False
        self.state.combat_focus = max(0, int(self.state.combat_focus) - int(skill.mp_cost))
        self._dungeon_turn_messages = []
        combo_triggers = 0
        total_damage = 0
        for enemy in list(targets):
            if enemy not in self.map_combat_enemies():
                continue
            triggered = self.dungeon_skill_combo_triggered(skill, enemy)
            combo_triggers += int(triggered)
            statuses = enemy.setdefault("statuses", {})
            vulnerable_bonus = 1 if int(statuses.get("vulnerable", 0)) > 0 else 0
            raw_damage = max(0, int(skill.damage)) + (int(skill.combo_damage_bonus) if triggered else 0)
            defense = max(0, int(enemy.get("defense", 0)) - max(0, int(skill.armor_pierce)))
            damage = max(1, raw_damage + vulnerable_bonus - defense)
            total_damage += damage
            enemy["hp"] = max(0, int(enemy["hp"]) - damage)
            enemy["alert"] = True
            combo_text = " combo" if triggered and int(skill.combo_damage_bonus) else ""
            self.dungeon_combat_note(
                f"{skill.name} deals {damage}{combo_text} damage to {enemy.get('species')} "
                f"({enemy['hp']}/{enemy['max_hp']} HP)."
            )
            if int(enemy["hp"]) <= 0:
                self.dungeon_defeat_enemy(enemy)
            else:
                self.dungeon_apply_skill_status(enemy, skill)
                displaced = self.dungeon_apply_skill_displacement(enemy, int(skill.displacement))
                if displaced:
                    self.dungeon_combat_note(
                        f"{enemy.get('species')} is {'pushed' if skill.displacement > 0 else 'pulled'} {displaced} tile"
                        f"{'s' if displaced != 1 else ''}."
                    )
        if total_damage and int(skill.life_steal) > 0:
            profile = farmstead_combat_profile(self.state)
            before_hp = int(self.state.combat_current_hp)
            drained = min(int(skill.life_steal), total_damage, int(profile["max_hp"]) - before_hp)
            if drained > 0:
                self.state.combat_current_hp = before_hp + drained
                self.dungeon_combat_note(f"{skill.name} drains {drained} HP back to you.")
        tiles = self.dungeon_skill_affected_tiles(origin, target, skill)
        self.dungeon_create_skill_zone(skill, tiles)
        if combo_triggers and int(skill.combo_mp_gain) > 0:
            profile = farmstead_combat_profile(self.state)
            before = int(self.state.combat_focus)
            self.state.combat_focus = min(int(profile["max_focus"]), before + int(skill.combo_mp_gain))
            if int(self.state.combat_focus) > before:
                self.dungeon_combat_note(
                    f"{skill.name}'s combo restores {self.state.combat_focus - before} MP."
                )
        self.dungeon_emit_noise(origin[0], origin[1], 7 if int(skill.range_max) > 2 else 5, label=skill.name)
        self.invalidate_draw_cache()
        if combo_triggers and int(skill.combo_ap_gain) > 0:
            self.dungeon_combat_note("The combo refunds your action; enemies do not advance.")
            messages = list(self._dungeon_turn_messages)
            log = self.dungeon_roguelike_record().setdefault("combat_log", [])
            log.extend(messages)
            self.dungeon_roguelike_record()["combat_log"] = log[-30:]
            self.set_message(" ".join(messages[-4:]))
            self._dungeon_turn_messages = []
            return True
        return self.advance_dungeon_roguelike_turn(skill.name)

    def dungeon_aim_skill(self, skill: Skill) -> bool:
        origin = (int(self.state.player_x), int(self.state.player_y))
        nearest = self.dungeon_nearest_enemy(origin, int(skill.range_max))
        cursor_x, cursor_y = (
            (int(nearest["x"]), int(nearest["y"])) if nearest else self.target_tile_pos()
        )
        while True:
            target_count = len(self.dungeon_skill_targets(origin, (cursor_x, cursor_y), skill))
            self.set_message(
                f"{skill.name}: {skill.damage} damage, {skill.mp_cost} MP, {self.dungeon_skill_shape_label(skill)}, "
                f"range {skill.range_max}"
                f"{'; ' + self.dungeon_skill_special_label(skill) if self.dungeon_skill_special_label(skill) else ''}; "
                f"{target_count} target{'s' if target_count != 1 else ''}. "
                "Move cursor; Z/Enter cast; B/X/Esc/Q/F cancel."
            )
            self.draw_with_look_cursor(cursor_x, cursor_y)
            key = normalize_key(read_key())
            if len(key) == 1 and key.isalpha():
                key = key.lower()
            if key in {"b", "x", "q", "f", "\t", "\x1b"}:
                self.set_message("Skill targeting cancelled; no MP spent.")
                self.invalidate_draw_cache()
                return False
            movement = movement_delta_for_key(key)
            if movement:
                candidate = (cursor_x + movement[0], cursor_y + movement[1])
                if self.in_active_bounds(*candidate) and self.dungeon_distance(origin, candidate) <= int(skill.range_max):
                    cursor_x, cursor_y = candidate
                continue
            if key in MENU_CONFIRM_KEYS:
                return self.dungeon_cast_skill_at(skill.name, (cursor_x, cursor_y))

    def dungeon_support_candidates(self, skill: Skill) -> List[Dict[str, object]]:
        candidates = [{
            "id": "player",
            "name": str(getattr(self.state, "player_name", "You") or "You"),
            "kind": "player",
        }]
        if skill.effect != "restore_mp":
            candidates.extend(self.dungeon_physical_companion_targets())
        if skill.effect == "transfer_ap":
            candidates = [candidate for candidate in candidates if candidate.get("kind") == "companion"]
        return candidates

    def dungeon_cast_support_skill(self, skill_name: str, target_id: str = "player") -> bool:
        catalog = {skill.name: skill for skill in self.dungeon_available_skills()}
        skill = catalog.get(str(skill_name))
        if not skill or skill.effect == "damage":
            self.set_message("That support skill is not available in your current loadout.")
            return False
        candidates = self.dungeon_support_candidates(skill)
        target = next((candidate for candidate in candidates if str(candidate.get("id")) == str(target_id)), None)
        if not target:
            self.set_message(f"{skill.name} has no valid dungeon target.")
            return False
        if int(self.state.combat_focus) < int(skill.mp_cost):
            self.set_message(f"{skill.name} needs {skill.mp_cost} MP.")
            return False
        profile = farmstead_combat_profile(self.state)
        is_player = str(target.get("kind", "player")) == "player"
        runtime = None if is_player else target.get("runtime")
        combat = self.dungeon_roguelike_record()
        if skill.effect == "heal":
            current = int(self.state.combat_current_hp) if is_player else int(runtime.get("hp", 0))
            maximum = int(profile["max_hp"]) if is_player else int(runtime.get("max_hp", 1))
            if current >= maximum:
                self.set_message(f"{target.get('name')} is already at full HP.")
                return False
        elif skill.effect == "restore_mp" and int(self.state.combat_focus) >= int(profile["max_focus"]):
            self.set_message("Your MP is already full.")
            return False
        elif skill.effect == "cleanse":
            conditions = combat if is_player else runtime.setdefault("statuses", {})
            if not any(int(conditions.get(name, 0)) > 0 for name in ("poison_turns", "poison", "root", "vulnerable")):
                self.set_message(f"{target.get('name')} has no harmful status to cleanse.")
                return False
        self.state.combat_focus = max(0, int(self.state.combat_focus) - int(skill.mp_cost))
        self._dungeon_turn_messages = []
        target_name = "you" if is_player else str(target.get("name", "your companion"))
        if skill.effect == "heal":
            guarded = int(combat.get("guard_turns", 0)) > 0 if is_player else int(runtime.get("guard_turns", 0)) > 0
            amount = int(skill.heal_amount) + (int(skill.combo_heal_bonus) if guarded and skill.combo_target_guarded else 0)
            if is_player:
                before = int(self.state.combat_current_hp)
                self.state.combat_current_hp = min(int(profile["max_hp"]), before + amount)
                gained = int(self.state.combat_current_hp) - before
            else:
                before = int(runtime.get("hp", 0))
                runtime["hp"] = min(int(runtime.get("max_hp", 1)), before + amount)
                gained = int(runtime["hp"]) - before
            self.dungeon_combat_note(f"{skill.name} restores {gained} HP to {target_name}.")
        elif skill.effect == "restore_mp":
            before = int(self.state.combat_focus)
            self.state.combat_focus = min(int(profile["max_focus"]), before + int(skill.mp_amount))
            self.dungeon_combat_note(f"{skill.name} restores {self.state.combat_focus - before} MP.")
        elif skill.effect == "cleanse":
            if is_player:
                combat["poison_turns"] = 0
            else:
                runtime["statuses"] = {}
            self.dungeon_combat_note(f"{skill.name} removes harmful conditions from {target_name}.")
        elif skill.effect == "guard":
            if is_player:
                combat["guard_turns"] = max(2, int(combat.get("guard_turns", 0)))
            else:
                runtime["guard_turns"] = max(2, int(runtime.get("guard_turns", 0)))
            self.dungeon_combat_note(f"{skill.name} places {target_name} under Guard.")
        elif skill.effect == "transfer_ap":
            self.dungeon_combat_note(f"{skill.name} coordinates an immediate companion action.")
            self.dungeon_companion_turns()
        else:
            self.set_message(f"{skill.name} has no dungeon effect.")
            return False
        return self.advance_dungeon_roguelike_turn(skill.name)

    def dungeon_choose_support_target(self, skill: Skill) -> bool:
        candidates = self.dungeon_support_candidates(skill)
        if not candidates:
            self.set_message(f"{skill.name} needs a standing companion in this fight.")
            return False
        if len(candidates) == 1:
            return self.dungeon_cast_support_skill(skill.name, str(candidates[0].get("id", "player")))
        choice = self.vertical_panel_select(
            f"{skill.name} Target",
            [
                MenuItem(
                    str(candidate.get("name", "Ally")),
                    value=str(candidate.get("id", "player")),
                    enabled=True,
                    hint="Choose who receives this support skill.",
                )
                for candidate in candidates
            ],
            LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
        )
        if not choice or choice.value == MENU_BACK:
            self.set_message("Support targeting cancelled; no MP spent.")
            return False
        return self.dungeon_cast_support_skill(skill.name, str(choice.value))

    def dungeon_combat_ability_menu(self):
        if not self.map_native_combat_active():
            return MENU_BACK
        focus = int(self.state.combat_focus)
        skills = self.dungeon_available_skills()
        items = []
        for skill in skills:
            rank = self.dungeon_skill_rank(skill.name)
            if skill.effect == "damage":
                effect = f"{skill.damage} damage | Rng {skill.range_max} | {self.dungeon_skill_shape_label(skill)}"
                special = self.dungeon_skill_special_label(skill)
                if special:
                    effect += f" | {special}"
            elif skill.effect == "heal":
                effect = f"Heal {skill.heal_amount}"
            elif skill.effect == "restore_mp":
                effect = f"Restore {skill.mp_amount} MP"
            else:
                effect = str(skill.effect).replace("_", " ").title()
            target_available = skill.effect != "transfer_ap" or bool(self.dungeon_physical_companion_targets())
            items.append(MenuItem(
                f"{skill.name} [R{rank}] - {skill.mp_cost} MP",
                value=f"skill:{skill.name}",
                enabled=focus >= int(skill.mp_cost) and target_available,
                hint=f"{effect}. {skill.description}",
            ))
        if self.on_wilderness_dungeon():
            items.append(MenuItem("Search nearby floor", value="search", enabled=True, hint="Spend a turn revealing concealed traps within 3 tiles."))
        items.extend([
            MenuItem("Throw Stone", value="lure", enabled=int(self.state.inventory.get("Stone", 0)) > 0, hint="Throw a Stone to lure enemies toward its sound."),
            MenuItem("Review combat log", value="log", enabled=True, hint="Review the latest map-combat actions without spending a turn."),
        ])
        place = "Wilderness" if self.wilderness_field_combat_active() else "Dungeon"
        choice = self.vertical_panel_select(
            f"{place} Skills & Actions",
            items,
            LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
        )
        if not choice or choice.value == MENU_BACK:
            self.set_message("Combat skill menu closed.")
            return MENU_BACK
        if str(choice.value).startswith("skill:"):
            name = str(choice.value).split(":", 1)[1]
            skill = next((candidate for candidate in skills if candidate.name == name), None)
            if not skill:
                self.set_message("That skill is no longer available.")
                return False
            if skill.effect == "damage":
                return self.dungeon_aim_skill(skill)
            return self.dungeon_choose_support_target(skill)
        if choice.value == "search":
            return self.dungeon_search_action()
        if choice.value == "lure":
            return self.dungeon_aim_noise_lure()
        if choice.value == "log":
            rows = list(self.dungeon_roguelike_record().get("combat_log", []) or [])
            self.vertical_panel_view(f"{place} Combat Log", rows[-30:] or ["No combat actions recorded yet."], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return MENU_BACK
        return False


__all__ = ["DUNGEON_ENEMY_ARCHETYPES", "DungeonRoguelikeCombatMixin"]
