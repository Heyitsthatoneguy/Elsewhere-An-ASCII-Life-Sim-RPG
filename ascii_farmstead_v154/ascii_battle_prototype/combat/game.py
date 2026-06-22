#!/usr/bin/env python3
"""ASCII Tactical Combat Prototype v113 runtime.

The runtime Game class still owns live battle state, while v113 moves reusable
models, terminal helpers, content definitions, and integration payloads into the
combat package so future farming/life-sim hooks have a stable backend seam.
"""

from __future__ import annotations

import re
import shutil
import sys
import time
import textwrap
from dataclasses import replace
from typing import Dict, Iterable, List, Optional, Set, Tuple

from . import ai as ai_helpers
from . import dev_menus as dev_menu_helpers
from . import pathfinding as pathfinding_helpers
from . import turns as turn_helpers
from .classes import class_defs as data_class_defs
from .companions import (
    companion_archetypes as data_companion_archetypes,
    companion_glyphs as data_companion_glyphs,
    companion_name_presets as data_companion_name_presets,
    create_default_heroes,
)
from .constants import *
from .enemies import create_enemy_templates, enemy_loadout_for_map as data_enemy_loadout_for_map, expand_enemy_roster
from .equipment import equipment_defs as data_equipment_defs
from .input import KeyReader
from .items import create_default_items
from .loot import loot_profile_for_enemy as data_loot_profile_for_enemy
from .maps import build_maps as data_build_maps
from .models import Item, OverwatchAction, Pos, Skill, Unit, Weapon, Zone
from .missions import mission_builtin_presets as data_mission_builtin_presets
from .rendering import (
    Style,
    c,
    clear_screen,
    clip,
    clip_visible,
    enter_alt_screen,
    exit_alt_screen,
    hide_cursor,
    pad,
    show_cursor,
    strip_ansi,
    strip_ansi_len,
    wrap_labeled,
    wrap_plain,
)
from .results import BattleRequest, BattleResult, battle_result_from_game
from .skills import create_default_skills
from .utils import clamp, manhattan, neighbors4


class Game:
    MAIN_MENU = ["Inspect", "Enemy View", "Move", "Attack", "Skills", "Item", "Party", "Map", "End Turn"]
    SKILL_GROUP_MENU = ["Cast Skill", "Overwatch", "Guard"]
    PARTY_GROUP_MENU = ["Hero", "Tactics", "Control"]

    def __init__(self) -> None:
        self.maps = self.build_maps()
        self.map_index = 0
        self.map_name, self.map, self.start_positions = self.maps[self.map_index]

        self.heroes = create_default_heroes(self.start_positions)
        self.enemy_max_count = 5
        self.custom_enemy_total_cap = 8
        base_enemies = create_enemy_templates(self.start_positions)
        self.base_enemy_names = [enemy.name for enemy in base_enemies]
        self.boss_enemy_names = {enemy.name for enemy in base_enemies if enemy.role == "boss" or enemy.boss}
        self.enemies = expand_enemy_roster(base_enemies, self.enemy_max_count, self.boss_enemy_names)

        self.skills: List[Skill] = create_default_skills()

        self.items: List[Item] = create_default_items()

        self.selected_hero_idx = 0
        self.cursor: Pos = self.selected_hero.pos
        self.enemy_view_index = 0
        self.enemy_view_sort_index = 0
        self.bestiary_enemy_index = 0
        self.bestiary_filter_index = 0

        # state:
        # command = main right-side menu
        # skill_group_menu / skill_menu / support_target_menu / item_menu / item_target_menu / party_group_menu / control_menu / tactics_menu / hero_menu / map_menu = right-side submenus
        # target_move / target_attack / target_skill / target_item / target_overwatch = map cursor targeting
        self.state = "command"
        self.menu_index = 0
        self.skill_index = 0
        self.skill_group_index = 0
        self.party_group_index = 0
        self.item_index = 0
        self.item_target_index = 0
        self.support_target_index = 0
        self.hero_menu_index = 0
        self.tactics_index = 0
        self.follower_tactic = 'Balanced'
        self.manual_companion_names: Set[str] = set()
        self.manual_teammates = False
        self.control_menu_index = 0
        self.overwatch_menu_index = 0
        self.pending_overwatch_option: Optional[Dict[str, object]] = None
        self.overwatch_return_state = "command"
        self.overwatch_actions: List[OverwatchAction] = []
        self.map_menu_index = 0
        self.allow_battle_map_selection = True
        self.in_main_menu = True
        self.main_menu_index = 0
        self.home_menu_index = 0
        self.map_detail_open = False
        self.main_menu_mode = "home"
        self.tutorial_active = False
        self.tutorial_mode = "basic"
        self.tutorial_flags: Set[str] = set()
        self.tutorial_menu_index = 0
        self.party_menu_index = 0
        self.party_limit = 4
        self.active_party_names: Set[str] = {"Rook", "Mira", "Brom", "Aria"}
        self.active_enemy_names: Set[str] = set(self.enemy_loadout_for_map(self.map_name))
        self.custom_companion_names: Set[str] = set()
        self.companion_editor_field_index = 0
        self.companion_editor_name_index = 0
        self.companion_editor_custom_name = ""
        self.companion_editor_glyph_index = 0
        self.companion_editor_color_index = 0
        self.companion_editor_archetype_index = 0
        self.companion_editor_class_index = 0
        self.companion_editor_subclass_index = 0
        self.companion_editor_weapon_index = 0
        self.companion_editor_add_to_party = True
        self.companion_editor_manual_control = False
        self.objective_menu_index = 0
        self.objective_mode = "Defeat All"
        self.objective_round_goal = 5
        self.objective_hold_goal = 3
        self.objective_object_goal = 3
        self.objective_hold_progress = 0
        self.objective_destroyed = 0
        self.objective_exit_tile: Optional[Pos] = None
        self.objective_hold_tiles: Set[Pos] = set()
        self.objective_object_tiles: Set[Pos] = set()
        self.objective_protect_name = "Rook"
        self.objective_last_tick_round = 0
        self.mission_menu_index = 0
        self.mission_page_index = 0  # 0 preset list, 1 builder
        self.mission_builder_field_index = 0
        self.mission_builder_name_index = 0
        self.mission_builder_custom_name = ""
        self.mission_builder_map_index = 6
        self.mission_builder_theme_index = 0
        self.mission_builder_objective_index = 0
        self.mission_builder_parameter = 3
        self.user_mission_presets: List[Dict[str, object]] = []
        self.pending_mission_preset: Optional[Dict[str, object]] = None
        self.current_mission_name = ""
        self.current_mission_id = ""
        self.current_mission_flavor = ""
        self.current_mission_reward_theme = ""
        self.text_entry_target: Optional[str] = None
        self.text_entry_buffer = ""

        self.loot_keys = [
            "Coin", "Hide", "Shard", "Tonic", "Gel", "Fang", "Spore Cap", "Stone", "Throwing Knife", "Guard Tonic",
            "Crow Feather", "Boar Tusk", "Root Fiber", "Slime Core", "Wolf Pelt", "Bandit Token", "Shield Fragment",
            "Wisp Spark", "Rock Shell", "Toad Oil", "Hare Needle", "Ember Cinder", "Frost Wing", "Burrow Claw",
            "Quill Plate", "Briar Heart", "Ancient Seed", "Supply Cache", "Relic Cache",
            "Old Coin", "Ruin Scrap", "Relic Fragment", "Dust Silk", "Stone Sigil", "Ancient Cog", "Bat Wing",
        ]
        self.campaign_inventory: Dict[str, int] = {key: 0 for key in self.loot_keys}
        self.item_loadout_bonus: Dict[str, int] = {
            "Potion": 0,
            "Ether": 0,
            "Cleanse Kit": 0,
            "Guard Tonic": 0,
            "Throwing Knife": 0,
            "Fire Bomb": 0,
        }
        self.loadout_menu_index = 0
        self.loadout_hero_index = 0
        self.loadout_slot_index = 0
        self.class_menu_hero_index = 0
        self.class_menu_class_index = 0
        self.class_screen_depth = 0  # 0 character list, 1 class list, 2 ability list
        self.class_skill_index = 0
        self.encounter_enemy_index = 0
        self.custom_enemy_counts: Dict[str, int] = self.counts_from_names(self.enemy_loadout_for_map(self.map_name))
        self.custom_elite_counts: Dict[str, int] = {name: 0 for name in self.enemy_roster_names()}
        self.custom_encounter_enabled = False
        self.party_progress: Dict[str, Dict[str, object]] = {
            h.name: {"level": h.level, "xp": h.xp, "hp_bonus": 0, "mp_bonus": 0, "damage_bonus": 0}
            for h in self.heroes
        }
        for h in self.heroes:
            self.ensure_progress_entry(h)
            self.apply_equipment_to_hero(h)
            h.hp = min(h.hp, h.max_hp)
            h.mp = min(h.mp, h.max_mp)
        self.battle_result_processed = False
        self.current_battle_request: Optional[BattleRequest] = None
        self.battle_request_id = ""
        self.battle_source = "debug"
        self.battle_return_context: Dict[str, object] = {}
        self.battle_world_flags: Dict[str, object] = {}
        self.battle_cleared_flags: Dict[str, object] = {}
        self.last_result_lines: List[str] = []
        self.result_section_index = 0

        self.turn = "hero"
        self.round_no = 1
        self.messages = ["Command menu active. Rook is player-controlled. Use Party > Control to set each companion Manual or AI."]
        self.combat_log: List[str] = []
        self.combat_log_scroll = 0
        self.combat_log_view = "combatants"
        self.combat_log_return_state = "command"
        self.add_combat_log_entry(self.messages[0], category="SYSTEM")
        self.visual_effects: Dict[Pos, str] = {}
        self._reachable_tiles_cache: Dict[Tuple[object, ...], Dict[Pos, int]] = {}
        self._path_cache: Dict[Tuple[object, ...], List[Pos]] = {}
        self._ui_intent_cache: Dict[Tuple[object, ...], str] = {}
        self._ui_priority_cache: Dict[Tuple[object, ...], int] = {}
        self._ui_intent_preview_cache: Dict[Tuple[object, ...], Tuple[Set[Pos], Set[Pos]]] = {}
        self.zones: List[Zone] = []
        self.clean_ui = True
        self.combat_stats = self.initial_combat_stats()
        self.rewards: Dict[str, int] = {key: 0 for key in self.loot_keys}
        self.should_quit = False
        self.frame_delay = 0.10

        for h in self.heroes:
            h.action_points = 2

    @staticmethod
    def build_maps() -> List[Tuple[str, List[List[str]], Dict[str, Pos]]]:
        return data_build_maps()

    def enemy_loadout_for_map(self, map_name: str) -> List[str]:
        return data_enemy_loadout_for_map(map_name)

    def map_width_tiles(self) -> int:
        return max((len(row) for row in self.map), default=MAP_W)

    def map_height_tiles(self) -> int:
        return len(self.map) if self.map else MAP_H

    def default_enemy_spawn_slots(self) -> List[Pos]:
        """Fallback right-side deployment slots for maps without named spawns."""
        width = self.map_width_tiles()
        height = self.map_height_tiles()
        right = max(1, width - 3)
        preferred = [
            (right, 1), (right - 1, 2), (right + 1, 3), (right - 2, 4), (right, 5), (right - 3, 6),
            (right - 1, 7), (right + 1, 8), (right - 2, 9), (right - 4, 3), (right - 5, 6), (right - 3, 9),
        ]
        generated = [(x, y) for x in range(width - 2, max(7, width // 2), -1) for y in range(1, height - 1)]
        slots: List[Pos] = []
        for pos in preferred + generated:
            if pos not in slots:
                slots.append(pos)
        return slots

    def place_active_enemies(self) -> None:
        """Place active enemies safely without requiring every map to define every enemy."""
        used: Set[Pos] = {h.pos for h in self.heroes if h.active}
        slots = [p for p in self.default_enemy_spawn_slots() if self.in_bounds(p) and self.tile_at(p) in PASSABLE]

        for enemy in self.enemies:
            if not enemy.active:
                continue

            preferred = self.start_positions.get(enemy.name)
            if preferred and self.in_bounds(preferred) and self.tile_at(preferred) in PASSABLE and preferred not in used:
                enemy.pos = preferred
            else:
                for slot in slots:
                    if slot not in used:
                        enemy.pos = slot
                        break
                else:
                    enemy.pos = enemy.pos if self.in_bounds(enemy.pos) and self.tile_at(enemy.pos) in PASSABLE else (max(1, self.map_width_tiles() - 2), 1)

            used.add(enemy.pos)

    # ----- queries -----

    @property
    def selected_hero(self) -> Unit:
        controllable = self.controllable_heroes_alive()
        if not controllable:
            return self.heroes[0]
        self.selected_hero_idx %= len(self.heroes)
        h = self.heroes[self.selected_hero_idx]
        if h.active and h.alive and not h.ai_controlled:
            return h
        self.next_hero()
        return self.heroes[self.selected_hero_idx]

    @property
    def all_units(self) -> List[Unit]:
        active_heroes = [h for h in self.heroes if h.active and h.alive]
        active_enemies = [e for e in self.enemies if e.active and e.alive]
        return active_heroes + active_enemies

    def heroes_alive(self) -> List[Unit]:
        return [h for h in self.heroes if h.active and h.alive]

    def controllable_heroes_alive(self) -> List[Unit]:
        return [h for h in self.heroes if h.active and h.alive and not h.ai_controlled]

    def followers_alive(self) -> List[Unit]:
        return [h for h in self.heroes if h.active and h.alive and h.ai_controlled]

    def enemies_alive(self) -> List[Unit]:
        if self.custom_encounter_enabled:
            order = {name: i for i, name in enumerate(self.ordered_enemy_names(self.active_enemy_names))}
        else:
            order = {name: i for i, name in enumerate(self.enemy_loadout_for_map(self.map_name))}
        return sorted(
            [e for e in self.enemies if e.active and e.alive],
            key=lambda e: order.get(e.name, 99),
        )

    def required_leader_name(self) -> str:
        return str(getattr(self, "farmstead_player_name", "") or "Rook")

    def is_required_leader(self, hero_or_name: object) -> bool:
        name = getattr(hero_or_name, "name", hero_or_name)
        return str(name) == self.required_leader_name()

    def tile_at(self, pos: Pos) -> str:
        if not self.in_bounds(pos):
            return TILE_WALL
        x, y = pos
        return self.map[y][x]

    def set_tile(self, pos: Pos, tile: str) -> None:
        if not self.in_bounds(pos):
            return
        x, y = pos
        self.map[y][x] = tile

    def unit_at(self, pos: Pos) -> Optional[Unit]:
        # Inactive reserve/template units share placeholder positions with
        # active combatants. Treat only active, living units as occupying the
        # map; otherwise pathfinding thinks invisible roster entries are walls.
        for u in self.all_units:
            if u.active and u.alive and u.pos == pos:
                return u
        return None

    def in_bounds(self, pos: Pos) -> bool:
        x, y = pos
        return 0 <= y < self.map_height_tiles() and 0 <= x < len(self.map[y])

    def is_passable(self, pos: Pos) -> bool:
        return self.in_bounds(pos) and self.tile_at(pos) in PASSABLE

    def is_walkable(self, pos: Pos, ignore: Optional[Unit] = None) -> bool:
        if not self.is_passable(pos):
            return False
        unit = self.unit_at(pos)
        return unit is None or unit is ignore

    # ----- pathing/ranges -----

    def movement_cost(self, pos: Pos) -> int:
        return 2 if self.tile_at(pos) == TILE_MUD else 1

    def ice_slide_destination(self, unit: Unit, start: Pos, previous: Pos) -> Pos:
        if self.tile_at(start) != TILE_ICE:
            return start
        dx = start[0] - previous[0]
        dy = start[1] - previous[1]
        if abs(dx) + abs(dy) != 1:
            return start
        cur = start
        for _ in range(4):
            nxt = (cur[0] + dx, cur[1] + dy)
            if not self.in_bounds(nxt) or not self.is_passable(nxt) or self.unit_at(nxt) is not None:
                break
            cur = nxt
            if self.tile_at(cur) != TILE_ICE:
                break
        return cur

    def apply_entry_terrain(self, unit: Unit, pos: Pos, events: Optional[List[str]] = None) -> List[str]:
        messages: List[str] = []
        if self.tile_at(pos) == TILE_THORNS and unit.alive:
            self.flash_effect([pos], "thorn")
            dmg = 1
            unit.hp = max(0, unit.hp - dmg)
            if unit.team == "hero":
                self.combat_stats["enemy_damage"] += dmg
                self.record_damage_taken(unit, dmg)
            elif unit.team == "enemy":
                self.combat_stats["player_damage"] += dmg
            self.combat_stats["terrain_damage"] = self.combat_stats.get("terrain_damage", 0) + dmg
            messages.append(f"{unit.name} takes {dmg} thorn damage")
        self.apply_zone_effects(unit, messages, reason="enters")
        if events is not None:
            events.extend(messages)
        return messages

    def apply_start_tile_effects(self, unit: Unit, events: List[str]) -> None:
        if not unit.alive:
            return
        tile = self.tile_at(unit.pos)
        if tile == TILE_SPRING and unit.hp < unit.max_hp:
            self.flash_effect([unit.pos], "spring")
            heal = min(2, unit.max_hp - unit.hp)
            unit.hp += heal
            self.combat_stats["terrain_heal"] = self.combat_stats.get("terrain_heal", 0) + heal
            events.append(f"{unit.name} spring +{heal} HP")
        elif tile == TILE_CRYSTAL and unit.max_mp > 0 and unit.mp < unit.max_mp:
            self.flash_effect([unit.pos], "crystal")
            gain = min(2, unit.max_mp - unit.mp)
            unit.mp += gain
            self.combat_stats["terrain_mp"] = self.combat_stats.get("terrain_mp", 0) + gain
            events.append(f"{unit.name} crystal +{gain} MP")
        self.apply_zone_effects(unit, events, reason="starts in")

    def barrel_tiles_in(self, tiles: Iterable[Pos]) -> List[Pos]:
        return [pos for pos in tiles if self.in_bounds(pos) and self.tile_at(pos) == TILE_BARREL]

    def explode_barrel(self, pos: Pos, source: Optional[Unit] = None) -> str:
        if not self.in_bounds(pos) or self.tile_at(pos) != TILE_BARREL:
            return ""
        blast_tiles = self.aoe_tiles(pos, 1)
        self.flash_effect(blast_tiles, "explosion", frames=2)
        self.set_tile(pos, TILE_FLOOR)
        self.combat_stats["barrels_detonated"] = self.combat_stats.get("barrels_detonated", 0) + 1
        affected_units = [u for u in self.all_units if u.alive and u.pos in blast_tiles]
        parts = []
        for unit in affected_units:
            dmg = unit.take_damage(8)
            if source and source.team == "hero" and unit.team == "enemy":
                self.combat_stats["player_damage"] += dmg
                self.record_actor_damage(source, dmg)
            elif unit.team == "hero":
                self.combat_stats["enemy_damage"] += dmg
                self.record_damage_taken(unit, dmg)
            label = f"{unit.name} {dmg}"
            if source and source.team == "hero" and unit.team == "enemy" and not unit.alive:
                label += " KO"
                self.award_xp(source, unit)
            parts.append(label)
        if parts:
            return f"Barrel explodes: {', '.join(parts)}"
        return "Barrel explodes."

    def nearby_barrel_count(self, pos: Pos) -> int:
        return sum(1 for p in self.aoe_tiles(pos, 1) if self.in_bounds(p) and self.tile_at(p) == TILE_BARREL)

    def terrain_score_for_unit(self, unit: Unit, pos: Pos, cautious: bool = True) -> int:
        """Positive means the tile is attractive, negative means tactically risky."""
        if not self.in_bounds(pos):
            return -999
        tile = self.tile_at(pos)
        score = 0

        # General terrain value.
        if tile == TILE_GRASS:
            score += 9
        elif tile == TILE_STONE:
            score += 7
        elif tile == TILE_MUD:
            score -= 10 if cautious else 5
        elif tile == TILE_THORNS:
            score -= 45 if unit.hp <= 3 else 24
        elif tile == TILE_ICE:
            score -= 16 if cautious else 8
            if unit.role in ("pouncer", "skirmisher"):
                score += 4
        elif tile == TILE_SPRING:
            missing = unit.max_hp - unit.hp
            score += min(26, missing * 2)
        elif tile == TILE_CRYSTAL:
            missing_mp = unit.max_mp - unit.mp
            score += min(24, missing_mp * 3)

        # Adjacent cover is useful, but direct cover tiles such as grass/stone
        # already get a small explicit bonus above.
        score += self.cover_score_for_enemy_tile(pos)

        # Barrels are useful to shoot, but bad places to stand next to.
        barrel_risk = self.nearby_barrel_count(pos)
        if barrel_risk:
            score -= barrel_risk * (22 if cautious else 12)

        return score

    def path_terrain_penalty(self, unit: Unit, destination: Pos, cautious: bool = True) -> int:
        path = self.find_path(unit, destination)
        if not path:
            return 0
        penalty = 0
        for step in path[1:]:
            tile = self.tile_at(step)
            if tile == TILE_THORNS:
                penalty += 28 if cautious else 16
            elif tile == TILE_MUD:
                penalty += 6
            elif tile == TILE_ICE:
                penalty += 10 if cautious else 5
            penalty += self.nearby_barrel_count(step) * (12 if cautious else 6)
        return penalty

    def barrel_blast_score(self, attacker: Unit, barrel_pos: Pos, target_team: str) -> Tuple[int, List[Unit], List[Unit]]:
        if not self.in_bounds(barrel_pos) or self.tile_at(barrel_pos) != TILE_BARREL:
            return (-999, [], [])
        if barrel_pos not in self.weapon_area(attacker.pos, attacker.weapon):
            return (-999, [], [])

        affected = [u for u in self.all_units if u.alive and u.pos in self.aoe_tiles(barrel_pos, 1)]
        targets = [u for u in affected if u.team == target_team]
        allies = [u for u in affected if u.team == attacker.team]

        score = 0
        for target in targets:
            score += min(8, target.hp) * 6
            if target.hp <= 8:
                score += 40
            if target.vulnerable > 0:
                score += 4

        for ally in allies:
            score -= min(8, ally.hp) * 9
            if ally.hp <= 8:
                score -= 50
            if ally is attacker:
                score -= 20

        # Small bonus for detonating a barrel before the other side can use it.
        if targets:
            score += 8
        return score, targets, allies

    def best_barrel_attack(self, attacker: Unit, target_team: str, threshold: int = 25):
        best = None
        for pos in self.weapon_area(attacker.pos, attacker.weapon):
            if not self.in_bounds(pos) or self.tile_at(pos) != TILE_BARREL:
                continue
            score, targets, allies = self.barrel_blast_score(attacker, pos, target_team)
            if score < threshold:
                continue
            candidate = ("barrel", pos, targets, allies, score)
            if best is None or score > best[4]:
                best = candidate
        return best

    def follower_attack_barrel(self, follower: Unit, barrel_pos: Pos, events: List[str]) -> None:
        self.clear_overwatch_for_unit(follower)
        follower.guard = False
        follower.action_points -= 1
        result = self.explode_barrel(barrel_pos, follower)
        events.append(f"{follower.name} detonates barrel. {result}")
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)

    def enemy_attack_barrel(self, enemy: Unit, barrel_pos: Pos, events: List[str]) -> None:
        result = self.explode_barrel(barrel_pos, enemy)
        events.append(f"{enemy.name} detonates barrel. {result}")
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)

    def active_blocker_key(self, ignore: Unit) -> Tuple[Tuple[str, Pos], ...]:
        return tuple(sorted(
            (unit.name, unit.pos)
            for unit in self.all_units
            if unit is not ignore and unit.active and unit.alive
        ))

    def map_layout_key(self) -> Tuple[str, ...]:
        return tuple("".join(row) for row in self.map)

    def movement_state_key(self, unit: Unit) -> Tuple[object, ...]:
        return (
            self.map_name,
            unit.name,
            unit.pos,
            unit.move_range,
            self.map_layout_key(),
            self.active_blocker_key(unit),
        )

    def trim_small_cache(self, cache: Dict[Tuple[object, ...], object], limit: int = 96) -> None:
        overflow = len(cache) - max(0, limit)
        if overflow <= 0:
            return
        for key in list(cache)[:overflow]:
            cache.pop(key, None)

    def reachable_tiles(self, unit: Unit) -> Dict[Pos, int]:
        key = self.movement_state_key(unit)
        cache = self._reachable_tiles_cache
        if key in cache:
            return cache[key]
        reachable = pathfinding_helpers.reachable_tiles(
            unit,
            lambda pos: self.is_walkable(pos, ignore=unit),
            self.movement_cost,
        )
        cache[key] = reachable
        self.trim_small_cache(cache)
        return reachable

    def path_cost(self, path: List[Pos]) -> int:
        return pathfinding_helpers.path_cost(path, self.movement_cost)


    def path_from_reachable(self, unit: Unit, goal: Pos, reachable: Dict[Pos, int]) -> List[Pos]:
        if goal not in reachable:
            return []
        if goal == unit.pos:
            return [unit.pos]

        path: List[Pos] = [goal]
        cur = goal
        guard = 0
        while cur != unit.pos:
            cur_cost = reachable.get(cur)
            candidates = [
                prev
                for prev in neighbors4(cur)
                if prev in reachable and reachable[prev] + self.movement_cost(cur) == cur_cost
            ]
            if not candidates:
                return pathfinding_helpers.find_path(unit, goal, reachable, self.movement_cost)
            cur = min(candidates, key=lambda pos: (reachable[pos], manhattan(pos, unit.pos), pos[1], pos[0]))
            path.append(cur)
            guard += 1
            if guard > len(reachable):
                return pathfinding_helpers.find_path(unit, goal, reachable, self.movement_cost)
        return list(reversed(path))

    def find_path(self, unit: Unit, goal: Pos) -> List[Pos]:
        movement_key = self.movement_state_key(unit)
        path_key = movement_key + (goal,)
        cache = self._path_cache
        if path_key in cache:
            return list(cache[path_key])
        reachable = self.reachable_tiles(unit)
        path = self.path_from_reachable(unit, goal, reachable)
        cache[path_key] = path
        self.trim_small_cache(cache, limit=192)
        return list(path)


    def weapon_profile_for_name(self, name: str) -> Dict[str, object]:
        profiles: Dict[str, Dict[str, object]] = {
            # Rook
            "Iron Saber": {"shape": "point", "type": "physical", "trait": "Reliable single-target melee."},
            "Heavy Saber": {"shape": "cone", "width": 1, "type": "physical", "trait": "Sweeping cleave that can hit clustered adjacent enemies."},
            "Command Blade": {"shape": "strip", "range_min": 1, "range_max": 2, "type": "storm", "status": "vulnerable", "status_duration": 1, "trait": "Short command lane that exposes enemies."},
            "Guard Blade": {"shape": "cross", "range_min": 1, "range_max": 1, "type": "earth", "status": "root", "status_duration": 1, "trait": "Defensive cross slash that can root nearby enemies."},

            # Mira
            "Scout Bow": {"shape": "point", "range_min": 2, "range_max": 4, "type": "physical", "trait": "Reliable ranged shot."},
            "Longbow": {"shape": "strip", "range_min": 2, "range_max": 6, "type": "pierce", "trait": "Piercing line shot that ignores cover."},
            "Quick Bow": {"shape": "multishot", "range_min": 2, "range_max": 4, "shots": 2, "type": "physical", "trait": "Fast double-shot against nearby targets."},
            "Venom Bow": {"shape": "point", "range_min": 2, "range_max": 4, "type": "poison", "status": "poison", "status_duration": 2, "trait": "Poison shot for attrition setups."},

            # Brom
            "Guard Axe": {"shape": "point", "type": "physical", "trait": "Reliable axe strike."},
            "War Maul": {"shape": "cross", "range_min": 1, "range_max": 1, "type": "earth", "status": "root", "status_duration": 1, "trait": "Heavy quake hit around Brom."},
            "Tower Axe": {"shape": "cone", "width": 1, "type": "earth", "trait": "Defensive sweeping arc; benefits from guarded brawls."},
            "Hook Axe": {"shape": "strip", "range_min": 1, "range_max": 2, "type": "pierce", "status": "vulnerable", "status_duration": 1, "trait": "Reach attack that hooks a lane and exposes targets."},

            # Aria
            "Light Wand": {"shape": "point", "range_min": 1, "range_max": 4, "type": "light", "trait": "Reliable radiant bolt."},
            "Spark Wand": {"shape": "multishot", "range_min": 1, "range_max": 4, "shots": 2, "type": "storm", "status": "vulnerable", "status_duration": 1, "trait": "Arcing shot that can expose multiple enemies."},
            "Bloom Staff": {"shape": "burst", "range_min": 1, "range_max": 4, "aoe_radius": 1, "type": "light", "trait": "Small radiant burst for clustered enemies."},
            "Channel Wand": {"shape": "strip", "range_min": 1, "range_max": 5, "type": "storm", "status": "vulnerable", "status_duration": 1, "trait": "Long focused beam that exposes a lane."},

            # Nia
            "Twin Daggers": {"shape": "multishot", "range_min": 1, "range_max": 1, "shots": 2, "type": "physical", "trait": "Twin close strikes against nearby enemies."},
            "Duelist Foil": {"shape": "point", "range_min": 1, "range_max": 2, "type": "pierce", "status": "vulnerable", "status_duration": 1, "trait": "Precise thrust that exposes targets."},
            "Throwing Daggers": {"shape": "multishot", "range_min": 1, "range_max": 3, "shots": 3, "type": "pierce", "trait": "Fan of thrown blades."},
            "Shadow Daggers": {"shape": "cone", "range_min": 1, "range_max": 2, "width": 1, "type": "shadow", "status": "vulnerable", "status_duration": 1, "trait": "Shadow fan that exposes nearby enemies."},

            # Dax
            "Stone Hammer": {"shape": "point", "type": "earth", "trait": "Reliable crushing blow."},
            "Breaker Hammer": {"shape": "cone", "range_min": 1, "range_max": 1, "width": 1, "type": "earth", "trait": "Huge front arc that smashes clusters."},
            "Bulwark Hammer": {"shape": "cross", "range_min": 1, "range_max": 1, "type": "earth", "status": "root", "status_duration": 1, "trait": "Ground slam that roots adjacent enemies."},
            "Tremor Hammer": {"shape": "burst", "range_min": 1, "range_max": 2, "aoe_radius": 1, "type": "earth", "status": "root", "status_duration": 1, "trait": "Tremor burst that controls a small area."},

            # Luma
            "Sun Rod": {"shape": "point", "range_min": 1, "range_max": 4, "type": "light", "trait": "Reliable sun bolt."},
            "Mercy Rod": {"shape": "point", "range_min": 1, "range_max": 4, "type": "light", "status": "vulnerable", "status_duration": 1, "trait": "Gentle beam that exposes foes for allies."},
            "Star Rod": {"shape": "burst", "range_min": 1, "range_max": 5, "aoe_radius": 1, "type": "light", "status": "vulnerable", "status_duration": 1, "trait": "Star burst that marks clustered enemies."},
            "Beacon Rod": {"shape": "strip", "range_min": 1, "range_max": 5, "type": "light", "trait": "Long beacon beam for safe support fire."},
        }
        return profiles.get(name, {"shape": "point", "type": "physical", "trait": "Standard attack."})

    def weapon_profile_label(self, weapon: Weapon) -> str:
        status = f", +{weapon.status} {weapon.status_duration}t" if weapon.status and weapon.status_duration else ""
        area = weapon.shape
        if weapon.shape == "burst":
            area += f" r{weapon.aoe_radius}"
        elif weapon.shape == "cone":
            area += f" w{weapon.width}"
        elif weapon.shape == "multishot":
            area += f" x{weapon.shots}"
        return f"{weapon.damage_type} {area} R{weapon.range_min}-{weapon.range_max}{status}; {weapon.trait}"

    def weapon_effect_kind(self, weapon: Weapon) -> str:
        kind = weapon.damage_type
        if kind == "physical" or kind == "pierce":
            return "hit"
        if kind == "storm":
            return "vulnerable"
        if kind == "frost":
            return "ice"
        if kind == "earth":
            return "root"
        if kind == "poison":
            return "poison"
        if kind == "fire":
            return "fire"
        if kind == "light":
            return "heal"
        if kind == "shadow":
            return "vulnerable"
        return "hit"

    def weapon_affected_tiles(self, origin: Pos, target: Pos, weapon: Weapon) -> Set[Pos]:
        if target not in self.weapon_area(origin, weapon):
            return set()

        shape = getattr(weapon, "shape", "point")
        if shape == "point":
            return {target}
        if shape == "burst":
            return self.aoe_tiles(target, weapon.aoe_radius)
        if shape == "cross":
            tiles = {origin}
            max_len = max(1, weapon.range_max)
            for distance in range(1, max_len + 1):
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    p = (origin[0] + dx * distance, origin[1] + dy * distance)
                    if self.in_bounds(p):
                        tiles.add(p)
            return tiles
        if shape == "strip":
            direction = self.direction_from_to(origin, target)
            perp = self.perpendicular(direction)
            half = max(0, int(weapon.width) // 2)
            tiles: Set[Pos] = set()
            for step in range(1, weapon.range_max + 1):
                center = (origin[0] + direction[0] * step, origin[1] + direction[1] * step)
                if not self.in_bounds(center):
                    continue
                for offset in range(-half, half + 1):
                    p = (center[0] + perp[0] * offset, center[1] + perp[1] * offset)
                    if self.in_bounds(p):
                        tiles.add(p)
            return tiles
        if shape == "cone":
            direction = self.direction_from_to(origin, target)
            perp = self.perpendicular(direction)
            tiles: Set[Pos] = set()
            for step in range(1, weapon.range_max + 1):
                spread = min(step, max(1, int(weapon.width)))
                for offset in range(-spread, spread + 1):
                    p = (
                        origin[0] + direction[0] * step + perp[0] * offset,
                        origin[1] + direction[1] * step + perp[1] * offset,
                    )
                    if self.in_bounds(p):
                        tiles.add(p)
            return tiles
        if shape == "multishot":
            return self.aoe_tiles(target, 2)
        return {target}

    def weapon_targets(self, attacker: Unit, target: Pos, weapon: Optional[Weapon] = None) -> List[Unit]:
        weapon = weapon or attacker.weapon
        if target not in self.weapon_area(attacker.pos, weapon):
            return []
        if getattr(weapon, "shape", "point") == "multishot":
            candidates = [
                enemy for enemy in self.enemies_alive()
                if manhattan(enemy.pos, target) <= 2 and manhattan(attacker.pos, enemy.pos) <= weapon.range_max
            ]
            candidates.sort(key=lambda e: (e.hp > self.weapon_damage_against(attacker, e, weapon), e.hp, manhattan(target, e.pos)))
            return candidates[: max(1, int(weapon.shots))]
        tiles = self.weapon_affected_tiles(attacker.pos, target, weapon)
        return [enemy for enemy in self.enemies_alive() if enemy.pos in tiles]

    def weapon_barrel_tiles(self, attacker: Unit, target: Pos, weapon: Optional[Weapon] = None) -> List[Pos]:
        weapon = weapon or attacker.weapon
        tiles = self.weapon_affected_tiles(attacker.pos, target, weapon)
        return [pos for pos in tiles if self.in_bounds(pos) and self.tile_at(pos) == TILE_BARREL]

    def weapon_damage_against(self, attacker: Unit, target: Unit, weapon: Optional[Weapon] = None) -> int:
        weapon = weapon or attacker.weapon
        damage = int(weapon.damage)
        dtype = getattr(weapon, "damage_type", "physical")
        if dtype != "pierce":
            damage = self.apply_cover_reduction(attacker.pos, target, damage)
        if target.vulnerable > 0:
            damage += 2
        if dtype == "fire" and (target.poison > 0 or target.rooted > 0):
            damage += 1
        elif dtype == "storm" and (target.vulnerable > 0 or target.rooted > 0):
            damage += 1
        elif dtype == "shadow" and target.vulnerable > 0:
            damage += 2
        elif dtype == "earth" and target.guard:
            damage += 2
        elif dtype == "poison" and target.poison > 0:
            damage += 1
        elif dtype == "light" and (target.poison > 0 or target.vulnerable > 0):
            damage += 1
        if target.guard and dtype != "pierce":
            damage = max(1, damage // 2)
        return max(1, damage)

    def apply_weapon_status(self, target: Unit, weapon: Weapon) -> str:
        if not weapon.status or weapon.status_duration <= 0:
            return ""
        before = (target.poison, target.rooted, target.vulnerable)
        if weapon.status == "poison":
            target.poison = max(target.poison, weapon.status_duration)
        elif weapon.status == "root":
            target.rooted = max(target.rooted, weapon.status_duration)
        elif weapon.status == "vulnerable":
            target.vulnerable = max(target.vulnerable, weapon.status_duration)
        after = (target.poison, target.rooted, target.vulnerable)
        if after != before:
            self.combat_stats["status_applications"] = self.combat_stats.get("status_applications", 0) + 1
            return f" +{weapon.status}"
        return f" +{weapon.status}"

    def tile_path_distance(self, start: Pos, goals: Set[Pos], max_search: int = 80, ignore_units: bool = True) -> int:
        """Shortest map distance from start to any goal.

        AI scoring uses this as a progress estimate. By default it ignores
        temporary unit blockers, so a unit stuck behind an ally/enemy still
        understands which direction makes progress instead of treating the
        current safe tile as best. Actual movement still uses real walkability.
        """
        return pathfinding_helpers.tile_path_distance(
            start,
            goals,
            self.is_passable,
            self.is_walkable,
            max_search=max_search,
            ignore_units=ignore_units,
        )

    def attack_goal_tiles_for_unit(self, unit: Unit, target: Unit, preferred_min: Optional[int] = None, preferred_max: Optional[int] = None) -> Set[Pos]:
        return pathfinding_helpers.attack_goal_tiles_for_unit(self.map, self.is_passable, unit, target, preferred_min, preferred_max)

    def ai_progress_to_attack_band(self, unit: Unit, pos: Pos, target: Optional[Unit], preferred_min: Optional[int] = None, preferred_max: Optional[int] = None) -> int:
        return pathfinding_helpers.progress_to_attack_band(
            self.map,
            self.is_passable,
            self.is_walkable,
            unit,
            pos,
            target,
            preferred_min,
            preferred_max,
        )

    def ai_movement_progress_bonus(
        self,
        unit: Unit,
        pos: Pos,
        target: Optional[Unit],
        preferred_min: Optional[int] = None,
        preferred_max: Optional[int] = None,
    ) -> int:
        return pathfinding_helpers.movement_progress_bonus(
            self.map,
            self.is_passable,
            self.is_walkable,
            unit,
            pos,
            target,
            preferred_min,
            preferred_max,
        )

    def congestion_escape_bonus(self, unit: Unit, pos: Pos) -> int:
        if pos == unit.pos:
            return 0
        current_blockers = sum(1 for n in neighbors4(unit.pos) if self.unit_at(n) is not None and self.unit_at(n) is not unit)
        next_blockers = sum(1 for n in neighbors4(pos) if self.unit_at(n) is not None and self.unit_at(n) is not unit)
        return (current_blockers - next_blockers) * 8

    def best_reachable_progress_tile(
        self,
        unit: Unit,
        target: Optional[Unit],
        preferred_min: Optional[int] = None,
        preferred_max: Optional[int] = None,
    ) -> Pos:
        reachable = list(self.reachable_tiles(unit).keys())
        if not reachable or not target:
            return unit.pos
        preferred_min = unit.weapon.range_min if preferred_min is None else preferred_min
        preferred_max = unit.weapon.range_max if preferred_max is None else preferred_max
        current_dist = self.ai_progress_to_attack_band(unit, unit.pos, target, preferred_min, preferred_max)

        def score(pos: Pos) -> Tuple[int, int, int, int]:
            progress = self.ai_movement_progress_bonus(unit, pos, target, preferred_min, preferred_max)
            in_band = preferred_min <= manhattan(pos, target.pos) <= preferred_max
            return (progress, 20 if in_band else 0, self.congestion_escape_bonus(unit, pos), -self.movement_cost(pos))

        best = max(reachable, key=score)
        if best == unit.pos and current_dist > 0:
            alternatives = [p for p in reachable if p != unit.pos]
            if alternatives:
                best_alt = max(alternatives, key=score)
                if score(best_alt)[0] >= -12 or self.ai_progress_to_attack_band(unit, best_alt, target, preferred_min, preferred_max) < current_dist:
                    return best_alt
        return best

    def weapon_area(self, origin: Pos, weapon: Weapon) -> Set[Pos]:
        # Local scan instead of full-map scan. This matters on larger arenas
        # because danger/preview AI calls this many times per turn.
        rmax = max(0, int(weapon.range_max))
        rmin = max(0, int(weapon.range_min))
        tiles: Set[Pos] = set()
        ox, oy = origin
        for y in range(oy - rmax, oy + rmax + 1):
            for x in range(ox - rmax, ox + rmax + 1):
                pos = (x, y)
                dist = manhattan(origin, pos)
                if rmin <= dist <= rmax and self.in_bounds(pos):
                    tiles.add(pos)
        return tiles


    def skill_range(self, origin: Pos, skill: Skill) -> Set[Pos]:
        rmax = max(0, int(skill.range_max))
        tiles: Set[Pos] = set()
        ox, oy = origin
        for y in range(oy - rmax, oy + rmax + 1):
            for x in range(ox - rmax, ox + rmax + 1):
                pos = (x, y)
                if manhattan(origin, pos) <= rmax and self.in_bounds(pos):
                    tiles.add(pos)
        return tiles

    def aoe_tiles(self, center: Pos, radius: int) -> Set[Pos]:
        radius = max(0, int(radius))
        tiles: Set[Pos] = set()
        cx, cy = center
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                pos = (x, y)
                if manhattan(center, pos) <= radius and self.in_bounds(pos):
                    tiles.add(pos)
        return tiles

    def line_between(self, start: Pos, end: Pos) -> List[Pos]:
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy))
        if steps == 0:
            return [start]
        points: List[Pos] = []
        for i in range(steps + 1):
            p = (round(x1 + dx * i / steps), round(y1 + dy * i / steps))
            if self.in_bounds(p) and p not in points:
                points.append(p)
        return points

    def direction_from_to(self, origin: Pos, target: Pos) -> Pos:
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        if dx == 0 and dy == 0:
            return (1, 0)
        if abs(dx) >= abs(dy):
            return (1 if dx >= 0 else -1, 0)
        return (0, 1 if dy >= 0 else -1)

    def perpendicular(self, direction: Pos) -> Pos:
        dx, dy = direction
        return (-dy, dx)

    def skill_power_label(self, skill: Skill) -> str:
        if skill.effect == "heal":
            return f"Heal {skill.heal_amount}"
        if skill.effect == "restore_mp":
            return f"MP+{skill.mp_amount}"
        if skill.effect == "cleanse":
            return "Cleanse"
        if skill.effect == "guard":
            return "Guard"
        if skill.effect == "transfer_ap":
            return "AP transfer"
        zone = f" Z:{skill.zone_duration}t" if skill.zone_duration else ""
        return f"{skill.damage}d{zone}"

    def unit_status_count(self, unit: Unit) -> int:
        return int(unit.poison > 0) + int(unit.rooted > 0) + int(unit.vulnerable > 0)

    def unit_has_status(self, unit: Unit, status: str) -> bool:
        if status == "poison":
            return unit.poison > 0
        if status == "root":
            return unit.rooted > 0
        if status == "vulnerable":
            return unit.vulnerable > 0
        return False

    def skill_combo_triggered(self, caster: Unit, target: Unit, skill: Skill) -> bool:
        if skill.combo_any_status and self.unit_status_count(target) > 0:
            return True
        if skill.combo_status and self.unit_has_status(target, skill.combo_status):
            return True
        if skill.combo_guarded and caster.guard:
            return True
        if skill.combo_target_guarded and target.guard:
            return True
        return False

    def skill_combo_damage_bonus(self, caster: Unit, target: Unit, skill: Skill) -> int:
        return skill.combo_damage_bonus if self.skill_combo_triggered(caster, target, skill) else 0

    def skill_combo_heal_bonus(self, caster: Unit, target: Unit, skill: Skill) -> int:
        return skill.combo_heal_bonus if self.skill_combo_triggered(caster, target, skill) else 0

    def skill_combo_label(self, skill: Skill) -> str:
        parts: List[str] = []
        if skill.combo_status:
            parts.append(skill.combo_status)
        if skill.combo_any_status:
            parts.append("any status")
        if skill.combo_guarded:
            parts.append("caster guarding")
        if skill.combo_target_guarded:
            parts.append("target guarding")
        rewards: List[str] = []
        if skill.combo_damage_bonus:
            rewards.append(f"+{skill.combo_damage_bonus}d")
        if skill.combo_heal_bonus:
            rewards.append(f"+{skill.combo_heal_bonus} heal")
        if skill.combo_ap_gain:
            rewards.append(f"+{skill.combo_ap_gain} AP")
        if skill.combo_mp_gain:
            rewards.append(f"+{skill.combo_mp_gain} MP")
        if not parts and not rewards:
            return ""
        return f"Combo: {', '.join(parts)} -> {', '.join(rewards)}"

    def apply_skill_combo_rewards(self, caster: Unit, skill: Skill, triggered_count: int) -> str:
        if triggered_count <= 0:
            return ""
        self.combat_stats["combo_triggers"] = self.combat_stats.get("combo_triggers", 0) + triggered_count
        parts: List[str] = []
        if skill.combo_ap_gain:
            gain = skill.combo_ap_gain
            before_ap = caster.action_points
            # This is a refund, not a new bonus action generator. Do not
            # reduce unusual transferred AP, but do not raise normal turns above 2.
            ap_cap = max(2, before_ap)
            caster.action_points = min(before_ap + gain, ap_cap)
            actual_gain = caster.action_points - before_ap
            if actual_gain > 0:
                self.combat_stats["combo_ap_refunded"] = self.combat_stats.get("combo_ap_refunded", 0) + actual_gain
                parts.append(f"{caster.name} +{actual_gain} AP")
        if skill.combo_mp_gain and caster.max_mp > 0:
            gain = min(skill.combo_mp_gain, caster.max_mp - caster.mp)
            if gain > 0:
                caster.mp += gain
                self.combat_stats["combo_mp_refunded"] = self.combat_stats.get("combo_mp_refunded", 0) + gain
                parts.append(f"{caster.name} +{gain} MP")
        if parts:
            return "Combo: " + ", ".join(parts)
        return "Combo triggered"

    def status_rider_label(self, skill: Skill) -> str:
        if not skill.status:
            return ""
        duration = f"{skill.status_duration}" if skill.status_duration > 0 else ""
        short = {
            "poison": "Poison",
            "root": "Root",
            "vulnerable": "Vuln",
        }.get(skill.status, skill.status.title())
        return f"+{short}{duration}"

    def skill_shape_label(self, skill: Skill) -> str:
        if skill.shape == "support":
            return "Ally list"
        if skill.shape == "point":
            return f"Point, range {skill.range_max}"
        if skill.shape == "burst":
            return f"Burst radius {skill.aoe_radius}, range {skill.range_max}"
        if skill.shape == "strip":
            return f"Long strip, range {skill.range_max}"
        if skill.shape == "cone":
            return f"Cone, length {skill.range_max}"
        if skill.shape == "cross":
            return f"Cross sweep, reach {skill.range_max}"
        if skill.shape == "multishot":
            return f"{skill.shots} shots, range {skill.range_max}"
        return f"{skill.shape}, range {skill.range_max}"

    def skill_targeting_hint(self, skill: Skill) -> str:
        if skill.effect == "heal":
            return "Choose one ally from the list; restores HP."
        if skill.effect == "restore_mp":
            return "Choose one ally from the list; restores MP."
        if skill.effect == "cleanse":
            return "Choose one ally from the list; removes harmful status effects."
        if skill.effect == "guard":
            return "Choose one ally from the list; grants Guard."
        if skill.effect == "transfer_ap":
            return "Choose one ally; transfer all remaining AP and end this unit's turn."
        if skill.shape == "point":
            return f"Hits one enemy/tile up to {skill.range_max} tiles away."
        if skill.shape == "burst":
            return f"Target within {skill.range_max}; hits radius {skill.aoe_radius} around cursor."
        if skill.shape == "strip":
            return f"Fires a straight lane up to {skill.range_max} tiles from caster."
        if skill.shape == "cone":
            return f"Projects a cone up to {skill.range_max} tiles toward cursor."
        if skill.shape == "cross":
            return f"Hits a cross centered on caster, reaching {skill.range_max} tiles."
        if skill.shape == "multishot":
            base = f"Marks up to {skill.shots} enemies within {skill.range_max} tiles."
        else:
            base = f"Range {skill.range_max}."
        combo = self.skill_combo_label(skill)
        return base + (f" {combo}." if combo else "")


    def skill_target_label(self, skill: Skill) -> str:
        return "Ally" if skill.target_team == "ally" else "Enemy"

    def valid_skill_targets(self, caster: Unit, skill: Skill) -> List[Unit]:
        if skill.target_team == "ally":
            targets = self.heroes_alive()
            if skill.effect == "transfer_ap":
                targets = [h for h in targets if h is not caster]
            return targets
        return self.enemies_alive()

    def skill_target_validity_message(self, caster: Unit, target: Optional[Unit], skill: Skill) -> Optional[str]:
        if not target:
            return "Select an ally." if skill.target_team == "ally" else "Select an enemy."
        if target not in self.valid_skill_targets(caster, skill):
            return "That skill targets allies." if skill.target_team == "ally" else "That skill targets enemies."
        if skill.target_team != "ally" and manhattan(caster.pos, target.pos) > skill.range_max:
            return "Target is out of skill range."
        if skill.effect == "heal" and target.hp >= target.max_hp:
            return f"{target.name} is already full HP."
        if skill.effect == "restore_mp" and target.mp >= target.max_mp:
            return f"{target.name} is already full MP."
        if skill.effect == "cleanse" and not (target.poison > 0 or target.rooted > 0 or target.vulnerable > 0):
            return f"{target.name} has no status effects to cleanse."
        if skill.effect == "guard" and target.guard:
            return f"{target.name} is already guarding."
        if skill.effect == "transfer_ap":
            if target is caster:
                return "Coordinate cannot target self."
            if caster.action_points <= 0:
                return f"{caster.name} has no AP to transfer."
        return None

    def skill_affected_tiles(self, origin: Pos, target: Pos, skill: Skill) -> Set[Pos]:
        if skill.shape == "support":
            return set()
        if target not in self.skill_range(origin, skill):
            return set()

        if skill.shape == "point":
            return {target}

        if skill.shape == "burst":
            return self.aoe_tiles(target, skill.aoe_radius)

        if skill.shape == "cross":
            tiles = {origin}
            max_len = max(1, skill.range_max)
            for distance in range(1, max_len + 1):
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    p = (origin[0] + dx * distance, origin[1] + dy * distance)
                    if self.in_bounds(p):
                        tiles.add(p)
            return tiles

        if skill.shape == "strip":
            direction = self.direction_from_to(origin, target)
            perp = self.perpendicular(direction)
            half = max(0, skill.width // 2)
            tiles: Set[Pos] = set()
            for step in range(1, skill.range_max + 1):
                center = (origin[0] + direction[0] * step, origin[1] + direction[1] * step)
                if not self.in_bounds(center):
                    continue
                for offset in range(-half, half + 1):
                    p = (center[0] + perp[0] * offset, center[1] + perp[1] * offset)
                    if self.in_bounds(p):
                        tiles.add(p)
            return tiles

        if skill.shape == "cone":
            direction = self.direction_from_to(origin, target)
            perp = self.perpendicular(direction)
            tiles: Set[Pos] = set()
            for step in range(1, skill.range_max + 1):
                spread = min(step, max(1, skill.width))
                for offset in range(-spread, spread + 1):
                    p = (
                        origin[0] + direction[0] * step + perp[0] * offset,
                        origin[1] + direction[1] * step + perp[1] * offset,
                    )
                    if self.in_bounds(p):
                        tiles.add(p)
            return tiles

        if skill.shape == "multishot":
            return self.aoe_tiles(target, 2)

        return self.aoe_tiles(target, skill.aoe_radius)

    def skill_targets(self, caster: Unit, target: Pos, skill: Skill) -> List[Unit]:
        if target not in self.skill_range(caster.pos, skill):
            return []

        if skill.target_team == "ally":
            candidates = self.valid_skill_targets(caster, skill)
            if skill.shape in ("point", "support"):
                return [ally for ally in candidates if ally.pos == target]
            tiles = self.skill_affected_tiles(caster.pos, target, skill)
            return [ally for ally in candidates if ally.pos in tiles]

        if skill.shape == "multishot":
            candidates = [
                e for e in self.enemies_alive()
                if manhattan(e.pos, target) <= 2 and manhattan(caster.pos, e.pos) <= skill.range_max
            ]
            candidates.sort(key=lambda e: (e.hp > skill.damage, e.hp, manhattan(target, e.pos)))
            return candidates[: skill.shots]

        tiles = self.skill_affected_tiles(caster.pos, target, skill)
        return [e for e in self.enemies_alive() if e.pos in tiles]

    def apply_skill_status(self, target: Unit, skill: Skill) -> None:
        if not skill.status or skill.status_duration <= 0:
            return
        applied = False
        if skill.status == "root":
            before = target.rooted
            target.rooted = max(target.rooted, skill.status_duration)
            applied = target.rooted > before
        elif skill.status == "vulnerable":
            before = target.vulnerable
            target.vulnerable = max(target.vulnerable, skill.status_duration)
            applied = target.vulnerable > before
        elif skill.status == "poison":
            before = target.poison
            target.poison = max(target.poison, skill.status_duration)
            applied = target.poison > before
        if applied:
            self.combat_stats["status_applications"] = self.combat_stats.get("status_applications", 0) + 1

    def zone_at(self, pos: Pos) -> Optional[Zone]:
        for zone in reversed(self.zones):
            if pos in zone.tiles and zone.duration > 0:
                return zone
        return None

    def zone_glyph(self, zone: Zone) -> str:
        return {
            "fire": "F",
            "frost": "I",
            "storm": "S",
            "earth": "E",
            "poison": "P",
            "light": "L",
            "shadow": "D",
        }.get(zone.kind, "Z")

    def zone_style(self, zone: Zone) -> Tuple[str, str]:
        return {
            "fire": (Style.BRIGHT_RED, Style.BG_ATTACK),
            "frost": (Style.BRIGHT_CYAN, Style.BG_OVERWATCH),
            "storm": (Style.BRIGHT_YELLOW, Style.BG_SKILL),
            "earth": (Style.BRIGHT_GREEN, Style.BG_MOVE),
            "poison": (Style.BRIGHT_GREEN, Style.BG_DANGER),
            "light": (Style.BRIGHT_WHITE, Style.BG_SKILL),
            "shadow": (Style.BRIGHT_MAGENTA, Style.BG_DANGER),
        }.get(zone.kind, (Style.BRIGHT_MAGENTA, Style.BG_SKILL))

    def create_skill_zone(self, caster: Unit, skill: Skill, center: Pos, tiles: Optional[Set[Pos]] = None) -> Optional[Zone]:
        if not skill.zone_type or skill.zone_duration <= 0:
            return None
        tiles = set(tiles or self.skill_affected_tiles(caster.pos, center, skill))
        tiles = {p for p in tiles if self.in_bounds(p) and self.tile_at(p) in PASSABLE}
        if not tiles:
            return None
        zone = Zone(
            name=skill.name,
            tiles=tiles,
            kind=skill.zone_type,
            duration=skill.zone_duration,
            damage=skill.zone_damage,
            status=skill.zone_status,
            status_duration=skill.zone_status_duration,
            owner_team=caster.team,
        )
        self.zones.append(zone)
        self.combat_stats["zones_created"] = self.combat_stats.get("zones_created", 0) + 1
        key = "zone_" + zone.kind
        self.combat_stats[key] = self.combat_stats.get(key, 0) + 1
        return zone

    def apply_zone_status(self, unit: Unit, zone: Zone) -> str:
        applied = False
        if zone.status == "root":
            before = unit.rooted
            unit.rooted = max(unit.rooted, zone.status_duration)
            applied = unit.rooted > before
            text = "+root"
        elif zone.status == "vulnerable":
            before = unit.vulnerable
            unit.vulnerable = max(unit.vulnerable, zone.status_duration)
            applied = unit.vulnerable > before
            text = "+vuln"
        elif zone.status == "poison":
            before = unit.poison
            unit.poison = max(unit.poison, zone.status_duration)
            applied = unit.poison > before
            text = "+poison"
        else:
            return ""
        if applied:
            self.combat_stats["zone_status_applications"] = self.combat_stats.get("zone_status_applications", 0) + 1
        return text

    def apply_zone_effects(self, unit: Unit, events: Optional[List[str]] = None, reason: str = "zone") -> List[str]:
        messages: List[str] = []
        if not unit.alive:
            return messages
        for zone in list(self.zones):
            if zone.duration <= 0 or unit.team == zone.owner_team or unit.pos not in zone.tiles:
                continue
            parts = []
            if zone.damage > 0:
                dmg = unit.take_damage(zone.damage)
                if unit.team == "hero":
                    self.combat_stats["enemy_damage"] += dmg
                    self.record_damage_taken(unit, dmg)
                else:
                    self.combat_stats["player_damage"] += dmg
                self.combat_stats["zone_damage"] = self.combat_stats.get("zone_damage", 0) + dmg
                parts.append(f"{dmg} {zone.kind}")
            status_text = self.apply_zone_status(unit, zone)
            if status_text:
                parts.append(status_text)
            if parts:
                messages.append(f"{unit.name} {reason} {zone.name}: " + " ".join(parts))
            if not unit.alive:
                messages.append(f"{unit.name} falls in {zone.name}")
                break
        if events is not None:
            events.extend(messages)
        return messages

    def tick_zones(self, events: Optional[List[str]] = None) -> None:
        expired: List[str] = []
        for zone in self.zones:
            zone.duration -= 1
            if zone.duration <= 0:
                expired.append(zone.name)
        self.zones = [zone for zone in self.zones if zone.duration > 0]
        if events is not None and expired:
            unique = []
            for name in expired:
                if name not in unique:
                    unique.append(name)
            events.append("Zones expire: " + ", ".join(unique[:3]) + ("..." if len(unique) > 3 else ""))

    # ----- overwatch helpers -----

    def master_skill_index(self, skill: Skill) -> int:
        return next((i for i, base in enumerate(self.skills) if base.name == skill.name), 0)

    def overwatch_options(self, hero: Optional[Unit] = None) -> List[Dict[str, object]]:
        hero = hero or self.selected_hero
        options: List[Dict[str, object]] = [
            {
                "kind": "weapon",
                "label": hero.weapon.name,
                "name": hero.weapon.name,
                "damage": hero.weapon.damage,
                "mp_cost": 0,
                "range": hero.weapon.range_max,
                "detail": f"{hero.weapon.damage}d {hero.weapon.damage_type} {hero.weapon.shape} R{hero.weapon.range_min}-{hero.weapon.range_max}",
            }
        ]
        for skill in self.available_skills(hero):
            # Point/support skills are immediate actions, not watched areas.
            # Overwatch is kept for weapon lanes and shaped/area damage/control skills only.
            if skill.shape in ("point", "support") or skill.target_team != "enemy" or skill.effect != "damage":
                continue
            options.append(
                {
                    "kind": "skill",
                    "label": skill.name,
                    "name": skill.name,
                    "skill": skill,
                    "skill_index": self.master_skill_index(skill),
                    "damage": skill.damage,
                    "mp_cost": skill.mp_cost,
                    "range": skill.range_max,
                    "detail": f"{skill.mp_cost}MP {skill.damage}d{self.status_rider_label(skill)} {skill.shape[:6]}",
                }
            )
        return options


    def selected_overwatch_option(self) -> Dict[str, object]:
        options = self.overwatch_options(self.selected_hero)
        if not options:
            return {}
        self.overwatch_menu_index %= len(options)
        return options[self.overwatch_menu_index]

    def skill_from_overwatch_option(self, option: Dict[str, object]) -> Optional[Skill]:
        skill = option.get("skill")
        if isinstance(skill, Skill):
            return skill
        if "name" in option:
            return self.skill_by_name(str(option.get("name")))
        if "skill_index" in option:
            try:
                return self.skills[int(option.get("skill_index", 0))]
            except Exception:
                return None
        return None

    def overwatch_option_enabled(self, option: Dict[str, object], hero: Optional[Unit] = None) -> bool:
        hero = hero or self.selected_hero
        if not option:
            return False
        if hero.action_points <= 0:
            return False
        if option.get("kind") == "skill":
            skill = self.skill_from_overwatch_option(option)
            return bool(skill and hero.mp >= skill.mp_cost)
        return True

    def weapon_overwatch_tiles(self, origin: Pos, target: Pos, weapon: Weapon) -> Set[Pos]:
        """Straight watched line for weapon overwatch.

        The cursor chooses the direction. Solid terrain blocks the line, and the
        weapon's min/max range decide which tiles can actually trigger.
        """
        direction = self.direction_from_to(origin, target)
        tiles: Set[Pos] = set()
        for step in range(1, weapon.range_max + 1):
            p = (origin[0] + direction[0] * step, origin[1] + direction[1] * step)
            if not self.in_bounds(p):
                break
            if not self.is_passable(p):
                break
            if step >= weapon.range_min:
                tiles.add(p)
        return tiles

    def overwatch_tiles_for_option(self, hero: Unit, option: Dict[str, object], target: Pos) -> Set[Pos]:
        if not option:
            return set()
        if option.get("kind") == "skill":
            skill = self.skill_from_overwatch_option(option)
            return self.skill_affected_tiles(hero.pos, target, skill)
        return self.weapon_overwatch_tiles(hero.pos, target, hero.weapon)

    def overwatch_target_names_for_option(self, hero: Unit, option: Dict[str, object], target: Pos) -> List[str]:
        if not option:
            return []
        if option.get("kind") == "skill":
            skill = self.skill_from_overwatch_option(option)
            return [e.name for e in self.skill_targets(hero, target, skill)]
        tiles = self.overwatch_tiles_for_option(hero, option, target)
        return [e.name for e in self.enemies_alive() if e.pos in tiles]

    def default_overwatch_cursor(self, hero: Unit, option: Dict[str, object]) -> Pos:
        if option.get("kind") == "skill":
            skill = self.skill_from_overwatch_option(option)
            return self.default_skill_cursor(hero, skill)
        if self.enemies_alive():
            return min(self.enemies_alive(), key=lambda e: manhattan(hero.pos, e.pos)).pos
        return hero.pos

    def predicted_enemy_path(self, enemy: Unit) -> List[Pos]:
        """Approximate where an enemy is likely to move next.

        This is intentionally predictive rather than perfect. It gives companion
        Overwatch enough map awareness to cover bridges, lanes, and approaches
        without making enemies use or counter-avoid Overwatch.
        """
        if not enemy.alive:
            return []
        target = self.enemy_best_target(enemy)
        if not target:
            return [enemy.pos]

        # If the enemy can already attack, it probably will not move.
        if self.can_attack(enemy, target):
            return [enemy.pos]

        destination: Optional[Pos]
        if enemy.role == "brute" and enemy.cooldowns.get("Brutal Charge", 0) <= 0:
            destination = self.best_charge_destination(enemy, target)
        elif enemy.role == "controller":
            destination = self.best_controller_move(enemy, target)
        else:
            destination = self.best_enemy_move(enemy, target)

        if not destination or destination == enemy.pos:
            return [enemy.pos]
        path = self.find_path(enemy, destination)
        return path if path else [enemy.pos, destination]

    def overwatch_score_for_option(self, follower: Unit, option: Dict[str, object], target: Pos, danger: Optional[Set[Pos]] = None, predicted_paths: Optional[Dict[str, List[Pos]]] = None) -> Tuple[int, List[Unit], Set[Pos]]:
        tiles = self.overwatch_tiles_for_option(follower, option, target)
        if not tiles:
            return (0, [], set())

        predicted_hits: List[Unit] = []
        earliest_steps: List[int] = []
        enemies_to_check = self.enemies_alive()
        if predicted_paths is not None:
            enemies_to_check = [enemy for enemy in enemies_to_check if enemy.name in predicted_paths]
        for enemy in enemies_to_check:
            path = predicted_paths.get(enemy.name) if predicted_paths is not None else self.predicted_enemy_path(enemy)
            for step_index, step in enumerate(path[1:], start=1):
                if step in tiles:
                    predicted_hits.append(enemy)
                    earliest_steps.append(step_index)
                    break

        # Bugfix v23:
        # Do NOT score enemies merely standing in the watched area. Overwatch
        # triggers on future movement into/through watched tiles, not on passive
        # occupancy. The UI may still show "covered now" for player clarity, but
        # companion AI should not spend AP on lanes that are unlikely to trigger.
        if not predicted_hits:
            return (0, [], tiles)

        if option.get("kind") == "skill":
            skill = self.skill_from_overwatch_option(option)
            base_damage = skill.damage
            mp_penalty = skill.mp_cost * (4 if self.follower_tactic in ("Cautious", "Support") else 3)
            status_bonus = {"root": 16, "vulnerable": 14, "poison": 18}.get(skill.status, 0)
            shape_bonus = {"cone": 8, "strip": 8, "multishot": 6, "burst": 4, "point": 0, "cross": 3}.get(skill.shape, 0)
            damage_score = sum(min(base_damage, enemy.hp) for enemy in predicted_hits)
            ko_score = sum(1 for enemy in predicted_hits if enemy.hp <= base_damage) * 35
            count_score = len(predicted_hits) * 12
            timing_bonus = max(0, 8 - min(earliest_steps or [8]))
            score = damage_score * 5 + ko_score + count_score + status_bonus + shape_bonus + timing_bonus - mp_penalty
        else:
            # Weapon overwatch only fires once, so score the best predicted target.
            best_enemy = max(predicted_hits, key=lambda e: (e.hp <= follower.weapon.damage, min(follower.weapon.damage, e.hp), -e.hp))
            damage_score = min(follower.weapon.damage, best_enemy.hp)
            ko_score = 35 if best_enemy.hp <= follower.weapon.damage else 0
            timing_bonus = max(0, 8 - min(earliest_steps or [8]))
            score = damage_score * 8 + ko_score + timing_bonus + len(predicted_hits) * 4

        # Prefer not to stand in obvious danger while watching a lane.
        if danger is None:
            danger = self.enemy_danger_tiles()
        if follower.pos in danger:
            score -= 18 if self.follower_tactic in ("Cautious", "Support") else 8

        return (score, predicted_hits, tiles)

    def best_follower_overwatch_action(self, follower: Unit):
        if follower.action_points <= 0:
            return None
        options = [option for option in self.overwatch_options(follower) if self.overwatch_option_enabled(option, follower)]
        if not options:
            return None

        active_enemies = self.enemies_alive()
        # v72: larger fortress maps can make speculative overwatch scoring expensive.
        # Score the most relevant threats and cache their predicted paths.
        if self.map_width_tiles() * self.map_height_tiles() > 500 and len(active_enemies) > 6:
            active_enemies = sorted(
                active_enemies,
                key=lambda e: (self.enemy_intent_priority(e), self.enemy_threat_value(e.name), -manhattan(follower.pos, e.pos)),
                reverse=True,
            )[:6]

        predicted_paths: Dict[str, List[Pos]] = {enemy.name: self.predicted_enemy_path(enemy) for enemy in active_enemies}

        candidate_targets: Set[Pos] = set()
        max_range = max(1, int(max(option.get("range", 1) for option in options)))
        for enemy in active_enemies:
            candidate_targets.add(enemy.pos)
            for step in predicted_paths.get(enemy.name, [enemy.pos])[1:]:
                candidate_targets.add(step)
            # Also consider cardinal sightlines that point toward each enemy.
            direction = self.direction_from_to(follower.pos, enemy.pos)
            candidate_targets.add((follower.pos[0] + direction[0] * max_range, follower.pos[1] + direction[1] * max_range))

        candidate_targets = {p for p in candidate_targets if self.in_bounds(p)}
        if not candidate_targets:
            return None
        if self.map_width_tiles() * self.map_height_tiles() > 500 and len(candidate_targets) > 18:
            candidate_targets = set(sorted(candidate_targets, key=lambda p: manhattan(follower.pos, p))[:18])

        best = None
        danger = self.enemy_danger_tiles()
        for option in options:
            # Keep the follower from burning expensive finishers on speculative overwatch.
            if option.get("kind") == "skill":
                skill = self.skill_from_overwatch_option(option)
                if not skill or skill.shape == "point" or skill.target_team != "enemy" or skill.effect != "damage":
                    continue
                if skill.name in ("Meteor Volley", "Stonebreak"):
                    continue
                if self.follower_tactic in ("Cautious", "Support") and skill.mp_cost > max(5, follower.mp // 2 + 2):
                    continue

            for target in candidate_targets:
                score, predicted_targets, tiles = self.overwatch_score_for_option(follower, option, target, danger, predicted_paths)
                if score <= 0 or not tiles:
                    continue
                candidate = ("overwatch", option, target, tiles, predicted_targets, score)
                if best is None or score > best[5]:
                    best = candidate
        return best

    def active_overwatch_tiles(self) -> Set[Pos]:
        tiles: Set[Pos] = set()
        for action in self.overwatch_actions:
            if action.owner.alive:
                tiles |= set(action.tiles)
        return tiles

    def clear_overwatch_for_unit(self, unit: Unit) -> int:
        before = len(self.overwatch_actions)
        self.overwatch_actions = [a for a in self.overwatch_actions if a.owner is not unit]
        return before - len(self.overwatch_actions)

    def clear_all_overwatch(self) -> int:
        count = len(self.overwatch_actions)
        self.overwatch_actions = []
        return count

    def resolve_overwatch_action(self, action: OverwatchAction, enemy: Unit, events: List[str]) -> None:
        owner = action.owner
        if not owner.alive or not enemy.alive:
            return

        if action.kind == "skill" and action.skill_index is not None:
            base_skill = self.skills[action.skill_index]
            skill = self.effective_skill(owner, base_skill)
            if owner.mp < skill.mp_cost:
                events.append(f"{owner.name}'s overwatch fizzles: no MP")
                return
            targets = self.skill_targets(owner, action.target, skill)
            if not targets:
                events.append(f"{owner.name}'s overwatch finds no target")
                return

            owner.mp -= skill.mp_cost
            self.combat_stats["skills_used"] += 1
            self.record_skill_use(owner, skill)
            self.combat_stats["overwatch_hits"] = self.combat_stats.get("overwatch_hits", 0) + 1
            self.flash_effect(action.tiles, "overwatch")
            self.flash_effect(self.skill_affected_tiles(owner.pos, action.target, skill), self.skill_effect_kind(skill))
            parts: List[str] = []
            combo_triggers = 0
            for target in list(targets):
                if not target.alive:
                    continue
                combo_bonus = self.skill_combo_damage_bonus(owner, target, skill)
                triggered = combo_bonus > 0 or (self.skill_combo_triggered(owner, target, skill) and (skill.combo_ap_gain or skill.combo_mp_gain))
                if triggered:
                    combo_triggers += 1
                dmg = target.take_damage(skill.damage + combo_bonus)
                self.apply_skill_status(target, skill)
                if owner.ai_controlled:
                    self.combat_stats["follower_damage"] += dmg
                else:
                    self.combat_stats["player_damage"] += dmg
                self.record_actor_damage(owner, dmg)
                part = f"{target.name} {dmg}"
                if combo_bonus:
                    part += " combo"
                if skill.status:
                    part += f" +{skill.status}"
                if not target.alive:
                    part += " KO"
                    self.award_xp(owner, target)
                parts.append(part)

            combo_result = self.apply_skill_combo_rewards(owner, skill, combo_triggers)
            if combo_result:
                parts.append(combo_result)
            events.append(f"{owner.name} overwatch uses {skill.name}: " + ", ".join(parts))
            return

        self.flash_effect([enemy.pos], "overwatch")
        raw_damage = self.weapon_damage_against(owner, enemy, owner.weapon)
        dmg = enemy.take_damage(raw_damage)
        status_text = self.apply_weapon_status(enemy, owner.weapon)
        if owner.ai_controlled:
            self.combat_stats["follower_damage"] += dmg
        else:
            self.combat_stats["player_damage"] += dmg
        self.record_actor_damage(owner, dmg)
        self.combat_stats["overwatch_hits"] = self.combat_stats.get("overwatch_hits", 0) + 1
        msg = f"{owner.name} overwatch hits {enemy.name} {dmg}{status_text}"
        if not enemy.alive:
            msg += " KO"
            self.award_xp(owner, enemy)
        events.append(msg)


    def trigger_overwatch_for_enemy(self, enemy: Unit, events: List[str]) -> bool:
        if not enemy.alive:
            return False
        triggered = False
        for action in list(self.overwatch_actions):
            if not action.owner.alive:
                self.overwatch_actions.remove(action)
                continue
            if enemy.pos in action.tiles:
                self.overwatch_actions.remove(action)
                events.append(f"{enemy.name} enters {action.owner.name}'s overwatch")
                self.resolve_overwatch_action(action, enemy, events)
                triggered = True
                if not enemy.alive:
                    break
        if triggered:
            self.render()
            if self.frame_delay > 0:
                time.sleep(self.frame_delay)
        return triggered

    def move_enemy_to(self, enemy: Unit, destination: Pos, events: List[str]) -> bool:
        if destination == enemy.pos:
            return enemy.alive
        path = self.find_path(enemy, destination)
        if not path:
            events.append(f"{enemy.name} is blocked")
            return enemy.alive
        for step in path[1:]:
            if not self.is_walkable(step, ignore=enemy):
                events.append(f"{enemy.name} is blocked")
                break
            old = enemy.pos
            if self.enemy_family(enemy) == "Slime" and self.tile_at(old) in (TILE_FLOOR, TILE_GRASS):
                self.set_tile(old, TILE_MUD)
                if f"{enemy.name} oozes mud" not in events:
                    events.append(f"{enemy.name} oozes mud")
            enemy.pos = step
            slide_to = self.ice_slide_destination(enemy, enemy.pos, old)
            if slide_to != enemy.pos:
                enemy.pos = slide_to
                events.append(f"{enemy.name} slides")
                self.apply_entry_terrain(enemy, enemy.pos, events)
                self.trigger_overwatch_for_enemy(enemy, events)
                self.render()
                if self.frame_delay > 0:
                    time.sleep(self.frame_delay)
                break
            self.apply_entry_terrain(enemy, enemy.pos, events)
            self.trigger_overwatch_for_enemy(enemy, events)
            self.render()
            if self.frame_delay > 0:
                time.sleep(self.frame_delay)
            if not enemy.alive:
                events.append(f"{enemy.name} is stopped")
                return False
        return enemy.alive


    def enemy_danger_tiles(self) -> Set[Pos]:
        danger: Set[Pos] = set()
        for enemy in self.enemies_alive():
            for tile in self.reachable_tiles(enemy):
                danger |= self.weapon_area(tile, enemy.weapon)
        return danger

    def action_preview_tiles(self, enemy: Unit, action) -> Tuple[Set[Pos], Set[Pos], str]:
        """Return likely movement tiles, threat tiles, and a compact action label.

        This is deliberately narrower than enemy_danger_tiles(): it previews the
        current AI plan instead of every theoretically reachable attack tile.
        """
        movement: Set[Pos] = set()
        threats: Set[Pos] = set()
        if not action:
            return movement, threats, "guard"

        kind = action[0]
        if kind == "move":
            destination = action[1]
            path = self.find_path(enemy, destination)
            if not path:
                path = [enemy.pos, destination]
            movement |= set(path[1:])
            return movement, threats, "move"

        if kind == "retreat":
            destination = action[1]
            path = self.find_path(enemy, destination)
            if not path:
                path = [enemy.pos, destination]
            movement |= set(path[1:])
            return movement, threats, "retreat"

        if kind == "charge":
            _kind, target, destination = action
            path = self.find_path(enemy, destination)
            if not path:
                path = [enemy.pos, destination]
            movement |= set(path[1:])
            threats.add(target.pos)
            return movement, threats, f"charge {target.name}"

        if kind == "spore":
            _kind, center, _targets = action
            threats |= self.aoe_tiles(center, 1)
            return movement, threats, "toxic burst"

        if kind == "needle_dash":
            _kind, target, destination, _damage = action
            path = self.find_path(enemy, destination) or [enemy.pos, destination]
            movement |= set(path[1:])
            threats.add(target.pos)
            return movement, threats, f"dash {target.name}"

        if kind == "burrow_ambush":
            _kind, target, destination, _damage = action
            movement.add(destination)
            threats.add(target.pos)
            return movement, threats, f"burrow {target.name}"

        if kind in ("cinder_toss", "frost_cloud", "quill_volley"):
            center = action[1]
            threats |= self.aoe_tiles(center, 1)
            labels = {
                "cinder_toss": "cinder toss",
                "frost_cloud": "frost cloud",
                "quill_volley": "quill volley",
            }
            return movement, threats, labels.get(kind, kind)

        if kind in ("spore_patch", "briar_bloom"):
            center = action[1]
            threats |= self.aoe_tiles(center, 1)
            return movement, threats, kind.replace("_", " ")

        if kind in ("attack", "poison", "intimidate", "root"):
            target = action[1]
            threats.add(target.pos)
            labels = {
                "attack": f"attack {target.name}",
                "poison": f"poison {target.name}",
                "intimidate": f"war cry {target.name}",
                "root": f"root {target.name}",
            }
            return movement, threats, labels.get(kind, kind)

        return movement, threats, kind

    def enemy_likely_plan_preview(self, enemy: Unit) -> Tuple[Set[Pos], Set[Pos], List[str]]:
        """Predict this enemy's current turn plan without mutating combat state."""
        movement: Set[Pos] = set()
        threats: Set[Pos] = set()
        labels: List[str] = []

        if not enemy.alive:
            return movement, threats, labels

        original_pos = enemy.pos
        original_ap = enemy.action_points
        ap = self.enemy_ap_budget(enemy)
        steps = 0

        try:
            enemy.action_points = ap
            while enemy.alive and ap > 0 and self.heroes_alive() and steps < 3:
                steps += 1
                action = self.choose_enemy_action(enemy)
                move_tiles, threat_tiles, label = self.action_preview_tiles(enemy, action)
                if label:
                    labels.append(label)
                movement |= move_tiles
                threats |= threat_tiles

                if not action:
                    break

                kind = action[0]
                spent = self.enemy_action_cost(enemy, kind)

                if kind in ("move", "retreat"):
                    destination = action[1]
                    if destination == enemy.pos:
                        break
                    enemy.pos = destination
                    ap = max(0, ap - spent)
                    enemy.action_points = ap
                    # Movement may be followed by one action if AP remains.
                    continue

                # Charge already includes movement plus attack/control. Other
                # offensive/control actions end the sequence by design.
                break
        finally:
            enemy.pos = original_pos
            enemy.action_points = original_ap

        return movement, threats, labels

    def enemy_intent_preview_tiles(self) -> Tuple[Set[Pos], Set[Pos]]:
        key = ("preview", self.tactical_preview_cache_key())
        cache = self._ui_intent_preview_cache
        if key in cache:
            movement, threats = cache[key]
            return set(movement), set(threats)
        movement: Set[Pos] = set()
        threats: Set[Pos] = set()
        for enemy in self.enemies_alive():
            move_tiles, threat_tiles, _labels = self.enemy_likely_plan_preview(enemy)
            movement |= move_tiles
            threats |= threat_tiles
        cache[key] = (set(movement), set(threats))
        self.trim_small_cache(cache, limit=32)
        return movement, threats

    def enemy_intent_summary(self, enemy: Unit) -> str:
        _movement, _threats, labels = self.enemy_likely_plan_preview(enemy)
        if not labels:
            return "guard"
        # Collapse repeats while keeping order, then show move -> act sequences.
        compact: List[str] = []
        for label in labels:
            if not compact or compact[-1] != label:
                compact.append(label)
        return " -> ".join(compact[:3])

    def clear_ui_intent_cache(self) -> None:
        self._ui_intent_cache = {}
        self._ui_priority_cache = {}
        self._ui_intent_preview_cache = {}

    def tactical_preview_cache_key(self) -> Tuple[object, ...]:
        units = tuple(sorted(
            (
                unit.name,
                unit.team,
                unit.pos,
                unit.hp,
                unit.mp,
                unit.action_points,
                unit.alive,
                unit.active,
                unit.guard,
                unit.poison,
                unit.rooted,
                unit.vulnerable,
                tuple(sorted(unit.cooldowns.items())),
            )
            for unit in self.all_units
            if unit.active
        ))
        zones = tuple(sorted(
            (
                zone.name,
                zone.kind,
                tuple(sorted(zone.tiles)),
                zone.duration,
                zone.damage,
                zone.status,
                zone.status_duration,
                zone.owner_team,
            )
            for zone in self.zones
        ))
        return (
            self.map_name,
            self.round_no,
            self.turn,
            self.objective_mode,
            self.map_layout_key(),
            units,
            zones,
        )

    def ui_enemy_intent_summary(self, enemy: Unit) -> str:
        # Intent previews are planning information for the player's turn. During
        # animated AI phases, recalculating a full future plan after every tile
        # of movement is both misleading and extremely expensive on large maps.
        if self.turn != "hero":
            return "acting" if self.turn == "enemy" else "waiting"
        cache = getattr(self, "_ui_intent_cache", None)
        if cache is None:
            cache = {}
            self._ui_intent_cache = cache
        key = ("summary", enemy.name, self.tactical_preview_cache_key())
        if key not in cache:
            cache[key] = self.enemy_intent_summary(enemy)
            self.trim_small_cache(cache)
        return cache[key]

    def ui_enemy_intent_priority(self, enemy: Unit) -> int:
        if self.turn != "hero":
            return (30 if enemy.boss else 0) + (20 if enemy.elite else 0)
        cache = getattr(self, "_ui_priority_cache", None)
        if cache is None:
            cache = {}
            self._ui_priority_cache = cache
        key = ("priority", enemy.name, self.tactical_preview_cache_key())
        if key not in cache:
            cache[key] = self.enemy_intent_priority(enemy)
            self.trim_small_cache(cache)
        return cache[key]

    # ----- rendering -----

    def push(self, msg: str) -> None:
        full_msg = str(msg)
        self.add_combat_log_entry(full_msg)
        self.messages.append(clip(full_msg, 78))
        self.messages = self.messages[-4:]

    def add_combat_log_entry(self, msg: str, category: str = "LOG") -> None:
        if not hasattr(self, "combat_log"):
            return
        raw = str(msg).replace("\r", " ").strip()
        if not raw:
            return
        turn = str(getattr(self, "turn", "?")).upper()
        round_no = int(getattr(self, "round_no", 0) or 0)
        prefix = f"[R{round_no} {turn} {category}]"
        for part in raw.split("\n"):
            part = part.strip()
            if part:
                self.combat_log.append(f"{prefix} {part}")
        self.combat_log = self.combat_log[-600:]
        self.combat_log_scroll = 0

    def log_existing_messages(self, category: str = "LOG") -> None:
        for msg in getattr(self, "messages", []):
            self.add_combat_log_entry(msg, category=category)

    def box_wrap(self, text: str, width: Optional[int] = None, indent: str = "  ") -> List[str]:
        inner = width if width is not None else PANEL_W - 2
        return wrap_plain(str(text), max(1, inner), subsequent_indent=indent)

    def wrapped_combat_log_lines(self, width: int) -> List[str]:
        usable = max(24, width)
        indent = "    "
        wrap_width = max(20, usable - len(indent))
        if not getattr(self, "combat_log", []):
            return ["No combat log entries yet."]
        lines: List[str] = []
        for entry in self.combat_log:
            wrapped = textwrap.wrap(
                entry,
                width=wrap_width,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            )
            if not wrapped:
                lines.append("")
            else:
                lines.append(wrapped[0])
                for continuation in wrapped[1:]:
                    lines.append(indent + continuation.lstrip())
        return lines

    def log_line_box(self, text: str, width: int) -> str:
        inner = max(10, width - 2)
        return c("│", Style.BRIGHT_BLACK) + pad(clip_visible(str(text), inner), inner) + c("│", Style.BRIGHT_BLACK)


    def combat_log_health_bar(self, unit: Unit, width: int = 10) -> str:
        current = max(0, int(unit.hp))
        maximum = max(1, int(unit.max_hp))
        filled = max(0, min(width, int(round(width * current / maximum))))
        if ASCII_MODE:
            raw = "#" * filled + "-" * (width - filled)
        else:
            raw = "█" * filled + "░" * (width - filled)
        if current <= 0:
            return c(raw, Style.BRIGHT_BLACK)
        if current * 3 <= maximum:
            return c(raw, Style.BRIGHT_RED)
        if current * 2 <= maximum:
            return c(raw, Style.BRIGHT_YELLOW)
        return c(raw, Style.BRIGHT_GREEN)

    def combatant_status_line(self, unit: Unit, width: int, selected: bool = False) -> str:
        name_width = 14 if width >= 78 else 10
        bar_width = 12 if width >= 78 else 8
        marker = ">" if selected else " "
        team = "ALLY" if unit.team == "hero" else "ENMY"
        glyph = self.hero_map_glyph(unit) if unit.team == "hero" else unit.glyph
        name = clip(unit.name, name_width)
        hp_text = f"{max(0, unit.hp)}/{unit.max_hp}"
        badges = self.status_badges(unit)
        if unit.team == "hero":
            mode = "MAN" if not unit.ai_controlled else "AI "
            extra = f"MP {unit.mp}/{unit.max_mp} AP{unit.action_points} {mode}"
        else:
            role = clip(unit.role or "enemy", 8)
            extra = f"AP{unit.action_points} {role}"
        badges = "" if badges == "OK" else " " + badges
        state = "DOWN" if not unit.alive else ""
        colored_bar = self.combat_log_health_bar(unit, bar_width)
        line = f"{marker} {team} {glyph} {name:<{name_width}} HP [{colored_bar}] {hp_text:<7} {extra}{badges} {state}".rstrip()
        return clip_visible(line, width)

    def combatant_status_rows(self, width: int, max_rows: int) -> List[str]:
        rows: List[str] = []
        heroes = [h for h in self.heroes if h.active]
        enemies = [e for e in self.enemies if e.active]
        enemies = sorted(enemies, key=lambda e: (not e.alive, self.enemy_threat_value(e.name), e.name))
        rows.append(c("ALLIES", Style.BOLD, Style.BRIGHT_CYAN))
        for hero in heroes:
            rows.append(self.combatant_status_line(hero, width, selected=(hero is self.selected_hero)))
        rows.append("")
        rows.append(c("ENEMIES", Style.BOLD, Style.BRIGHT_RED))
        if enemies:
            for enemy in enemies:
                rows.append(self.combatant_status_line(enemy, width, selected=(self.cursor == enemy.pos)))
        else:
            rows.append("  none")
        if len(rows) > max_rows:
            hidden = len(rows) - max_rows + 1
            rows = rows[: max(0, max_rows - 1)] + [f"... {hidden} more combatants hidden; enlarge window for full list."]
        return [clip_visible(row, width) for row in rows]

    def recent_combat_log_lines(self, width: int, limit: int) -> List[str]:
        if not getattr(self, "combat_log", []):
            return ["No combat log entries yet."]
        raw = self.combat_log[-max(1, limit):]
        lines: List[str] = []
        for entry in raw:
            lines.extend(wrap_plain(entry, width, subsequent_indent="  "))
        if len(lines) > limit:
            lines = lines[-limit:]
        return lines or ["No combat log entries yet."]

    def toggle_combat_log_view(self) -> None:
        self.combat_log_view = "events" if getattr(self, "combat_log_view", "combatants") == "combatants" else "combatants"
        self.combat_log_scroll = 0

    def start_combat_log(self) -> None:
        self.combat_log_return_state = self.state if self.state != "combat_log" else getattr(self, "combat_log_return_state", "command")
        self.state = "combat_log"
        self.combat_log_view = "combatants"
        self.combat_log_scroll = 0

    def close_combat_log(self) -> None:
        destination = getattr(self, "combat_log_return_state", "command")
        if destination == "combat_log":
            destination = "command"
        self.state = destination
        if not self.state_uses_map_cursor():
            self.cursor = self.selected_hero.pos

    def handle_combat_log_key(self, key: str) -> None:
        if key in ("ESC", "c", "x", "l", "ENTER", "SPACE", "z"):
            self.close_combat_log()
            return
        if key in ("TAB", "v"):
            self.toggle_combat_log_view()
            return
        if getattr(self, "combat_log_view", "combatants") != "events":
            if key in ("UP", "DOWN", "LEFT", "RIGHT", "w", "a", "s", "d", "HOME", "END"):
                return
            return

        terminal_size = shutil.get_terminal_size(fallback=(100, 30))
        body_height = max(5, terminal_size.lines - 7)
        total_lines = len(self.wrapped_combat_log_lines(max(30, terminal_size.columns - 4)))
        max_scroll = max(0, total_lines - body_height)
        if key in ("UP", "w"):
            self.combat_log_scroll = min(max_scroll, self.combat_log_scroll + 1)
            return
        if key in ("DOWN", "s"):
            self.combat_log_scroll = max(0, self.combat_log_scroll - 1)
            return
        if key in ("LEFT", "a"):
            self.combat_log_scroll = min(max_scroll, self.combat_log_scroll + body_height)
            return
        if key in ("RIGHT", "d"):
            self.combat_log_scroll = max(0, self.combat_log_scroll - body_height)
            return
        if key == "HOME":
            self.combat_log_scroll = max_scroll
            return
        if key == "END":
            self.combat_log_scroll = 0
            return


    def render_combat_log(self) -> None:
        terminal_size = shutil.get_terminal_size(fallback=(100, 30))
        width = max(60, terminal_size.columns)
        height = max(12, terminal_size.lines)
        inner = width - 2
        view = getattr(self, "combat_log_view", "combatants")

        if view == "events":
            body_height = max(5, height - 7)
            all_lines = self.wrapped_combat_log_lines(max(30, inner - 2))
            max_scroll = max(0, len(all_lines) - body_height)
            self.combat_log_scroll = max(0, min(self.combat_log_scroll, max_scroll))
            start = max(0, len(all_lines) - body_height - self.combat_log_scroll)
            end = min(len(all_lines), start + body_height)
            visible = all_lines[start:end]

            rows: List[str] = []
            rows.append(c("┌" + "─" * inner + "┐", Style.BRIGHT_BLACK))
            title = f" EVENT LOG — {self.map_name} | Round {self.round_no} | entries {len(self.combat_log)} "
            rows.append(self.log_line_box(c(title, Style.BOLD, Style.BRIGHT_WHITE), width))
            rows.append(self.log_line_box(f"Showing {start + 1 if all_lines else 0}-{end} of {len(all_lines)} | Scroll {self.combat_log_scroll}/{max_scroll} | Tab/V combatants", width))
            rows.append(c("├" + "─" * inner + "┤", Style.BRIGHT_BLACK))
            for line in visible:
                rows.append(self.log_line_box(line, width))
            while len(rows) < height - 2:
                rows.append(self.log_line_box("", width))
            rows.append(c("├" + "─" * inner + "┤", Style.BRIGHT_BLACK))
            rows.append(self.log_line_box("Up/Down line | Left/Right page | Home oldest | End newest | Tab/V combatants | X/Esc close", width))
            rows.append(c("└" + "─" * inner + "┘", Style.BRIGHT_BLACK))
            clear_screen()
            sys.stdout.write("\n".join(rows[:height]))
            sys.stdout.flush()
            return

        rows: List[str] = []
        rows.append(c("┌" + "─" * inner + "┐", Style.BRIGHT_BLACK))
        title = f" COMBATANTS — {self.map_name} | Round {self.round_no} | {self.turn.upper()} turn "
        rows.append(self.log_line_box(c(title, Style.BOLD, Style.BRIGHT_WHITE), width))
        rows.append(self.log_line_box("Tab/V Events | X/Esc/C/L/Z/Enter close", width))
        rows.append(c("├" + "─" * inner + "┤", Style.BRIGHT_BLACK))

        reserved = 7
        status_space = max(7, height - reserved)
        status_rows = self.combatant_status_rows(inner - 2, status_space)
        for line in status_rows:
            rows.append(self.log_line_box(line, width))
        rows.append(c("├" + "─" * inner + "┤", Style.BRIGHT_BLACK))
        rows.append(self.log_line_box(c("RECENT EVENTS", Style.BOLD, Style.BRIGHT_WHITE), width))
        recent_space = max(1, height - len(rows) - 2)
        for line in self.recent_combat_log_lines(inner - 2, recent_space):
            rows.append(self.log_line_box(line, width))
        while len(rows) < height - 2:
            rows.append(self.log_line_box("", width))
        rows.append(c("├" + "─" * inner + "┤", Style.BRIGHT_BLACK))
        rows.append(self.log_line_box("Tab/V Events | X/Esc/C/L/Z/Enter close", width))
        rows.append(c("└" + "─" * inner + "┘", Style.BRIGHT_BLACK))
        clear_screen()
        sys.stdout.write("\n".join(rows[:height]))
        sys.stdout.flush()


    def bar(self, value: int, maximum: int, width: int = 8) -> str:
        if maximum <= 0:
            return "-" * width
        filled = int(width * value / maximum)
        if ASCII_MODE:
            return "#" * filled + "-" * (width - filled)
        return "█" * filled + "░" * (width - filled)

    def panel_rule(self) -> str:
        return c("├" + "─" * (PANEL_W - 2) + "┤", Style.BRIGHT_BLACK)

    def section_header(self, title: str, *styles: str) -> str:
        label = f" {title} "
        return self.line_box(c(label, *(styles or (Style.BOLD,))))

    def state_label(self) -> str:
        labels = {
            "command": "COMMAND MENU",
            "inspect": "INSPECT",
            "enemy_view": "ENEMY VIEW",
            "target_move": "MOVE TARGET",
            "target_attack": "ATTACK TARGET",
            "skill_group_menu": "SKILLS",
            "skill_menu": "CAST SKILL",
            "target_skill": "SKILL TARGET",
            "support_target_menu": "ALLY TARGET",
            "overwatch_menu": "OVERWATCH",
            "target_overwatch": "OVERWATCH TARGET",
            "item_menu": "ITEM MENU",
            "item_target_menu": "ITEM TARGET",
            "target_item": "ITEM TARGET",
            "party_group_menu": "PARTY",
            "control_menu": "CONTROL",
            "tactics_menu": "TACTICS",
            "hero_menu": "HERO MENU",
            "map_menu": "MAP SELECT",
            "ally_ai": "FOLLOWER TURN",
            "enemy": "ENEMY TURN",
            "combat_log": "COMBAT LOG",
        }
        return labels.get(self.state, self.state.upper())

    def state_uses_map_cursor(self) -> bool:
        return self.state in ("inspect", "target_move", "target_attack", "target_skill", "target_item", "target_overwatch")

    def fx_symbol(self, kind: str) -> str:
        if ASCII_MODE:
            return {
                "hit": "*", "skill": "*", "fire": "X", "ice": ">", "poison": "p",
                "root": "r", "vulnerable": "v", "heal": "+", "mp": "m",
                "cleanse": "c", "guard": "G", "explosion": "X", "thorn": "*",
                "spring": "+", "crystal": "m", "overwatch": "W", "combo": "!",
            }.get(kind, "*")
        return {
            "hit": "✦", "skill": "◆", "fire": "✹", "ice": "❄", "poison": "☠",
            "root": "⌁", "vulnerable": "◇", "heal": "+", "mp": "✧",
            "cleanse": "✓", "guard": "▣", "explosion": "✹", "thorn": "✶",
            "spring": "+", "crystal": "✧", "overwatch": "W", "combo": "!",
        }.get(kind, "✦")

    def fx_cell(self, kind: str) -> str:
        glyph = self.fx_symbol(kind)
        if kind == "fire" or kind == "explosion":
            return c(f" {glyph} ", Style.BRIGHT_YELLOW, Style.BG_ATTACK, Style.BOLD)
        if kind == "hit":
            return c(f" {glyph} ", Style.BRIGHT_RED, Style.BG_ATTACK, Style.BOLD)
        if kind == "skill":
            return c(f" {glyph} ", Style.BRIGHT_MAGENTA, Style.BG_SKILL, Style.BOLD)
        if kind == "ice":
            return c(f" {glyph} ", Style.BRIGHT_CYAN, Style.BG_OVERWATCH, Style.BOLD)
        if kind == "poison":
            return c(f" {glyph} ", Style.BRIGHT_GREEN, Style.BG_DARK, Style.BOLD)
        if kind == "root" or kind == "thorn":
            return c(f" {glyph} ", Style.BRIGHT_RED, Style.BG_DANGER, Style.BOLD)
        if kind == "vulnerable" or kind == "combo":
            return c(f" {glyph} ", Style.BLACK, Style.BG_SELECT, Style.BOLD)
        if kind == "heal" or kind == "spring" or kind == "cleanse":
            return c(f" {glyph} ", Style.BRIGHT_GREEN, Style.BG_DARK, Style.BOLD)
        if kind == "mp" or kind == "crystal":
            return c(f" {glyph} ", Style.BRIGHT_BLUE, Style.BG_DARK, Style.BOLD)
        if kind == "guard":
            return c(f" {glyph} ", Style.BRIGHT_WHITE, Style.BG_OVERWATCH, Style.BOLD)
        if kind == "overwatch":
            return c(f" {glyph} ", Style.BRIGHT_CYAN, Style.BG_OVERWATCH, Style.BOLD)
        return c(f" {glyph} ", Style.BRIGHT_MAGENTA, Style.BG_SKILL, Style.BOLD)

    def flash_effect(self, tiles: Iterable[Pos], kind: str = "skill", frames: int = 1) -> None:
        valid_tiles = [pos for pos in tiles if self.in_bounds(pos)]
        if self.frame_delay <= 0:
            return
        if not valid_tiles:
            return
        previous = dict(getattr(self, "visual_effects", {}))
        for _ in range(max(1, frames)):
            self.visual_effects = {pos: kind for pos in valid_tiles}
            self.render()
            time.sleep(max(0.008, self.frame_delay * 0.45))
        self.visual_effects = previous
        self.render()

    def flash_unit_effect(self, units: Iterable[Unit], kind: str = "hit", frames: int = 1) -> None:
        self.flash_effect([unit.pos for unit in units if unit.alive or self.in_bounds(unit.pos)], kind, frames)

    def skill_effect_kind(self, skill: Skill) -> str:
        name = skill.name.lower()
        if skill.effect == "heal":
            return "heal"
        if skill.effect == "restore_mp":
            return "mp"
        if skill.effect == "cleanse":
            return "cleanse"
        if skill.effect == "guard":
            return "guard"
        if skill.zone_type:
            return skill.zone_type
        if "flame" in name or "cinder" in name or "fire" in name or "meteor" in name or "ignite" in name:
            return "fire"
        if "frost" in name or "ice" in name:
            return "ice"
        if "venom" in name or "toxic" in name or skill.status == "poison":
            return "poison"
        if "root" in name or "snare" in name or "thorn" in name or skill.status == "root":
            return "root"
        if skill.status == "vulnerable" or "mark" in name or "shock" in name:
            return "vulnerable"
        if skill.combo_note or skill.combo_damage_bonus or skill.combo_ap_gain or skill.combo_mp_gain:
            return "combo"
        return "skill"

    def base_tile(self, tile: str) -> str:
        if tile == TILE_FLOOR:
            return c(" . ", Style.BRIGHT_BLACK)
        if tile == TILE_DIRT:
            return c(" , ", Style.YELLOW)
        if tile == TILE_GRASS:
            return c(" \" ", Style.GREEN)
        if tile == TILE_MUD:
            return c(" : ", Style.BRIGHT_BLACK)
        if tile == TILE_BRIDGE:
            return c(" = ", Style.BRIGHT_YELLOW)
        if tile == TILE_STONE:
            return c(" ^ ", Style.BRIGHT_WHITE)
        if tile == TILE_THORNS:
            return c(" * ", Style.BRIGHT_RED)
        if tile == TILE_SPRING:
            return c(" + ", Style.BRIGHT_GREEN, Style.BG_DARK)
        if tile == TILE_CRYSTAL:
            return c(" m ", Style.BRIGHT_BLUE, Style.BG_DARK)
        if tile == TILE_ICE:
            return c(" _ ", Style.BRIGHT_CYAN)
        if tile == TILE_BARREL:
            return c(" B ", Style.BRIGHT_YELLOW, Style.BG_ATTACK)
        if tile == TILE_CRATE:
            return c(" C ", Style.YELLOW, Style.BG_DARK)
        if tile == TILE_WALL:
            return c(" # ", Style.BRIGHT_WHITE, Style.BG_DARK)
        if tile == TILE_TREE:
            return c(f" {TILE_TREE} ", Style.BRIGHT_GREEN)
        if tile == TILE_WATER:
            return c(" ~ ", Style.BRIGHT_CYAN, Style.BG_DARK)
        return f" {tile} "

    def cell(
        self,
        pos: Pos,
        reachable: Set[Pos],
        path: Set[Pos],
        danger: Set[Pos],
        attack: Set[Pos],
        skill_r: Set[Pos],
        aoe: Set[Pos],
        overwatch_tiles: Set[Pos] = set(),
        overwatch_hit_positions: Set[Pos] = set(),
        skill_hit_positions: Set[Pos] = set(),
        enemy_path: Set[Pos] = set(),
    ) -> str:
        tile = self.tile_at(pos)
        unit = self.unit_at(pos)

        if pos in getattr(self, "visual_effects", {}):
            return self.fx_cell(self.visual_effects[pos])

        if unit:
            fg = self.hero_color_style(unit) if unit.team == "hero" else Style.BRIGHT_RED
            glyph = self.hero_map_glyph(unit)
            text = c(f" {glyph} ", Style.BOLD, fg)
        else:
            marker = self.objective_marker_at(pos)
            if marker:
                text = self.objective_marker_cell(marker)
            else:
                zone = self.zone_at(pos)
                if zone:
                    fg, bg = self.zone_style(zone)
                    text = c(f" {self.zone_glyph(zone)} ", fg, bg, Style.BOLD)
                else:
                    text = self.base_tile(tile)

        if not unit:
            if pos in enemy_path and tile in PASSABLE:
                text = c(" ? ", Style.BRIGHT_YELLOW, Style.BG_DANGER)
            if pos in danger and tile in PASSABLE:
                text = c(" ! ", Style.BRIGHT_RED, Style.BG_DANGER)
            if pos in reachable and tile in PASSABLE:
                text = c(" + ", Style.BRIGHT_CYAN, Style.BG_MOVE)
            if pos in path and tile in PASSABLE:
                text = c(" * ", Style.BRIGHT_GREEN, Style.BG_PATH)
            if pos in attack:
                text = c(" x ", Style.BRIGHT_YELLOW, Style.BG_ATTACK)
            if pos in skill_r:
                text = c(" o ", Style.BRIGHT_MAGENTA)
            if pos in aoe:
                text = c(" O ", Style.BRIGHT_MAGENTA, Style.BG_SKILL)
            if pos in overwatch_tiles:
                text = c(" W ", Style.BRIGHT_CYAN, Style.BG_OVERWATCH)

        if unit and unit.team == "hero" and pos in danger:
            text = c(f"!{self.hero_map_glyph(unit)}!", Style.BLACK, Style.BG_DANGER, Style.BOLD)

        if unit and pos in overwatch_hit_positions:
            glyph = self.hero_map_glyph(unit) if unit.team == "hero" else unit.glyph
            text = c(f"!{glyph}!", Style.BLACK, Style.BG_OVERWATCH, Style.BOLD)

        if unit and pos in skill_hit_positions:
            # Explicit "will be hit" marker. This is intentionally stronger
            # than the area overlay because units otherwise hide the AoE tile.
            glyph = self.hero_map_glyph(unit) if unit.team == "hero" else unit.glyph
            text = c(f"<{glyph}>", Style.BLACK, Style.BG_SKILL, Style.BOLD)

        if pos == self.cursor:
            glyph = (self.hero_map_glyph(unit) if unit.team == "hero" else unit.glyph) if unit else {
                TILE_FLOOR: ".",
                TILE_DIRT: ",",
                TILE_GRASS: '"',
                TILE_MUD: ":",
                TILE_BRIDGE: "=",
                TILE_STONE: "^",
                TILE_THORNS: "*",
                TILE_SPRING: "+",
                TILE_CRYSTAL: "m",
                TILE_ICE: "_",
                TILE_BARREL: "B",
                TILE_CRATE: "X" if self.objective_marker_at(pos) == "object" else "C",
                TILE_WALL: "#",
                TILE_TREE: TILE_TREE,
                TILE_WATER: "~",
            }.get(tile, tile)

            if self.state_uses_map_cursor():
                text = c(f"[{glyph}]", Style.BLACK, Style.BG_SELECT, Style.BOLD)
            else:
                # Passive cursor marker: shows current/selected unit, but does not imply free cursor control.
                text = c(f" {glyph} ", Style.BOLD, Style.BRIGHT_WHITE, Style.BG_DARK)

        return text

    def ui_status_label(self) -> str:
        return "Clean" if self.clean_ui else "Full"

    def toggle_ui_mode(self) -> None:
        self.clean_ui = not self.clean_ui
        self.push(f"UI mode: {self.ui_status_label()}.")

    def compact_unit_line(self, unit: Unit, selected: bool = False) -> str:
        marker = "*" if selected else " "
        mode = "M" if unit.team == "hero" and not unit.ai_controlled else ("AI" if unit.team == "hero" else unit.role[:2])
        badges = self.status_badges(unit)
        status_part = "" if badges == "OK" else f" [{badges}]"
        if unit.team == "hero":
            return clip(f"{marker}{unit.name:<5} {mode:<2} HP {unit.hp}/{unit.max_hp} MP {unit.mp}/{unit.max_mp} AP {unit.action_points}{status_part}", PANEL_W - 2)
        return clip(f"{marker}{unit.name:<14} HP {unit.hp}/{unit.max_hp} {unit.role[:8]}{status_part}", PANEL_W - 2)

    def active_party_dashboard(self) -> str:
        parts: List[str] = []
        for hero in self.heroes:
            if hero.active:
                mark = "*" if hero is self.selected_hero else ""
                mode = "M" if not hero.ai_controlled else "A"
                badges = self.status_badges(hero)
                suffix = "" if badges == "OK" else f"[{badges}]"
                parts.append(f"{mark}{hero.name}:{hero.hp}/{hero.max_hp} AP{hero.action_points}{mode}{suffix}")
        return "Party " + " | ".join(parts)

    def top_enemy_dashboard(self, limit: int = 4) -> str:
        enemies = sorted(self.enemies_alive(), key=lambda e: (self.ui_enemy_intent_priority(e), self.enemy_threat_value(e.name), e.hp), reverse=True)
        if not enemies:
            return "Enemies none"
        parts: List[str] = []
        for enemy in enemies[:limit]:
            danger = "!" if self.ui_enemy_intent_priority(enemy) >= 70 else ""
            badges = self.status_badges(enemy)
            status = "" if badges == "OK" else f"[{badges}]"
            parts.append(f"{danger}{enemy.name}:{enemy.hp}/{enemy.max_hp}{status}")
        if len(enemies) > limit:
            parts.append(f"+{len(enemies)-limit}")
        return "Enemies " + " | ".join(parts)

    def battle_footer_lines(self, map_width: int, compact: bool) -> List[str]:
        lines: List[str] = []
        selected_line = self.cursor_context_line(map_width)

        if self.clean_ui:
            lines.append(clip(selected_line, map_width))
            lines.append(clip(self.battlefield_pressure_line(map_width), map_width))
            lines.append(clip(self.active_party_dashboard(), map_width))
            lines.append(clip(self.top_enemy_dashboard(), map_width))
            log_count = 1 if compact else 2
            if self.messages:
                lines.append(c("Log ", Style.BOLD, Style.BRIGHT_WHITE) + clip(" / ".join(self.messages[-log_count:]), max(8, map_width - 4)))
            return lines

        lines.append(c("SELECTED ", Style.BOLD) + clip(selected_line.replace("Selected ", ""), max(8, map_width - 9)))
        enemy_text = " | ".join(self.enemy_summary(e) for e in self.enemies)
        lines.append(c("ENEMIES  ", Style.BOLD, Style.BRIGHT_RED) + clip(enemy_text, map_width - 9))
        lines.append("")
        lines.append(c("LOG", Style.BOLD, Style.BRIGHT_WHITE))
        log_count = 2 if compact else 4
        for msg in self.messages[-log_count:]:
            lines.append("  " + clip(msg, map_width - 2))
        return lines

    def clean_controls_line(self) -> str:
        if self.state == "combat_log":
            return "Tab/V events | X/Esc/C/L close"
        if self.state in ("target_move", "target_attack", "target_skill", "target_item", "target_overwatch", "inspect"):
                return "Move cursor | Z/Enter confirm | X/Esc/C back | L log | H help"
        if self.state == "enemy_view":
            return f"Up/Down enemy | S sort {self.current_enemy_view_sort()} | Z/Enter focus | X/Esc/C"
        return "Navigate | Z/Enter confirm | X/Esc/C back | H help"

    def line_box(self, text: str = "") -> str:
        inner = PANEL_W - 2
        safe = clip_visible(str(text), inner)
        return c("│", Style.BRIGHT_BLACK) + pad(safe, inner) + c("│", Style.BRIGHT_BLACK)

    def line_boxes(self, text: str = "", style: Optional[str] = None, limit: Optional[int] = None) -> List[str]:
        inner = PANEL_W - 2
        raw_lines = self.box_wrap(text, inner, indent="  ")
        if limit is not None and len(raw_lines) > limit:
            raw_lines = raw_lines[: max(1, limit)]
            raw_lines[-1] = clip(raw_lines[-1] + " …", inner)
        if style:
            return [self.line_box(c(line, style)) for line in raw_lines]
        return [self.line_box(line) for line in raw_lines]

    def menu_line(self, label: str, index: int, detail: str = "", enabled: bool = True) -> str:
        selected = self.state == "command" and self.menu_index == index
        prefix = ">" if selected else " "
        text = f"{prefix} {label:<9}"
        if detail:
            text += f" {detail}"
        text = clip(text, PANEL_W - 2)
        if not enabled:
            return c(text, Style.BRIGHT_BLACK)
        if selected:
            return c(text, Style.BLACK, Style.BG_SELECT, Style.BOLD)
        return c(text, Style.BRIGHT_WHITE)

    def sub_line(self, label: str, selected: bool, enabled: bool = True) -> str:
        prefix = ">" if selected else " "
        text = clip(f"{prefix} {label}", PANEL_W - 2)
        if not enabled:
            return c(text, Style.BRIGHT_BLACK)
        if selected:
            return c(text, Style.BLACK, Style.BG_SELECT, Style.BOLD)
        return c(text, Style.BRIGHT_WHITE)

    def has_cover_from(self, attacker_pos: Pos, target: Unit) -> bool:
        """Simple readable cover rule.

        If any tree, wall, or stone is orthogonally adjacent to the target and roughly
        between attacker and target, ranged/special damage is softened. This is a
        prototype readability rule rather than strict line-of-sight.
        """
        if manhattan(attacker_pos, target.pos) <= 1:
            return False
        tx, ty = target.pos
        ax, ay = attacker_pos
        for cx, cy in neighbors4(target.pos):
            if not self.in_bounds((cx, cy)):
                continue
            if self.tile_at((cx, cy)) not in COVER_TILES:
                continue
            # Cover matters most when it is on the attacker's side of the target.
            if (ax < tx and cx < tx) or (ax > tx and cx > tx) or (ay < ty and cy < ty) or (ay > ty and cy > ty):
                return True
        return False

    def apply_cover_reduction(self, attacker_pos: Pos, target: Unit, damage: int) -> int:
        if self.has_cover_from(attacker_pos, target):
            return max(1, damage - 1)
        return damage

    def status_text(self, unit: Unit) -> str:
        effects = []
        if unit.poison > 0:
            effects.append(f"Poison {unit.poison}")
        if unit.rooted > 0:
            effects.append(f"Root {unit.rooted}")
        if unit.vulnerable > 0:
            effects.append(f"Vuln {unit.vulnerable}")
        if unit.guard:
            effects.append("Guard")
        return " | ".join(effects)

    def status_badges(self, unit: Unit) -> str:
        badges: List[str] = []
        if unit.guard:
            badges.append("G")
        if unit.poison > 0:
            badges.append(f"P{unit.poison}")
        if unit.rooted > 0:
            badges.append(f"R{unit.rooted}")
        if unit.vulnerable > 0:
            badges.append(f"V{unit.vulnerable}")
        if not unit.alive:
            badges.append("DOWN")
        return " ".join(badges) if badges else "OK"

    def companion_color_names(self) -> List[str]:
        return ["Cyan", "Green", "Yellow", "Magenta", "Blue", "Red", "White", "Gray"]

    def companion_color_style(self, color_name: str) -> str:
        return {
            "Cyan": Style.BRIGHT_CYAN,
            "Green": Style.BRIGHT_GREEN,
            "Yellow": Style.BRIGHT_YELLOW,
            "Magenta": Style.BRIGHT_MAGENTA,
            "Blue": Style.BRIGHT_BLUE,
            "Red": Style.BRIGHT_RED,
            "White": Style.BRIGHT_WHITE,
            "Gray": Style.BRIGHT_BLACK,
        }.get(color_name, Style.BRIGHT_CYAN)

    def default_hero_color_name(self, hero_name: str) -> str:
        defaults = {
            "Rook": "Cyan",
            "Mira": "Green",
            "Brom": "Yellow",
            "Aria": "Magenta",
            "Nia": "Blue",
            "Dax": "Red",
            "Luma": "White",
        }
        if hero_name in getattr(self, "custom_companion_names", set()):
            return "Cyan"
        return defaults.get(hero_name, "Cyan")

    def hero_color_name(self, hero: Unit) -> str:
        if hero.team != "hero":
            return ""
        progress = self.ensure_progress_entry(hero)
        color = str(progress.get("color", self.default_hero_color_name(hero.name)))
        if color not in self.companion_color_names():
            color = self.default_hero_color_name(hero.name)
            progress["color"] = color
        return color

    def hero_color_style(self, hero: Unit) -> str:
        return self.companion_color_style(self.hero_color_name(hero))

    def hero_map_glyph(self, hero: Unit) -> str:
        # All player-side companions/followers intentionally share the @ map symbol.
        return "@" if hero.team == "hero" else hero.glyph

    def hero_color_preview(self, hero: Unit) -> str:
        if hero.team != "hero":
            return ""
        color_name = self.hero_color_name(hero)
        return c("@", self.hero_color_style(hero), Style.BOLD) + f" {color_name}"

    def cycle_hero_color(self, hero: Unit, direction: int = 1) -> None:
        if hero.team != "hero":
            return
        colors = self.companion_color_names()
        progress = self.ensure_progress_entry(hero)
        current = str(progress.get("color", self.default_hero_color_name(hero.name)))
        idx = colors.index(current) if current in colors else 0
        progress["color"] = colors[(idx + direction) % len(colors)]
        self.messages = [f"{hero.name} color changed to {progress['color']}."]

    def unit_vitals_chip(self, unit: Unit, width: int = 34) -> str:
        hp = f"{unit.hp}/{unit.max_hp}"
        mp = f" MP{unit.mp}/{unit.max_mp}" if unit.team == "hero" else ""
        ap = f" AP{unit.action_points}" if unit.alive else " DOWN"
        badges = self.status_badges(unit)
        return clip(f"{unit.name} HP{hp}{mp}{ap} [{badges}]", width)

    def cursor_context_line(self, limit: int = 80) -> str:
        inspected = self.unit_at(self.cursor)
        zone = self.zone_at(self.cursor)
        if inspected:
            team = "ALLY" if inspected.team == "hero" else "FOE"
            intent = ""
            if inspected.team == "enemy" and inspected.alive:
                intent = " | Intent: " + self.ui_enemy_intent_summary(inspected)
            return clip(f"Cursor: {team} {self.unit_vitals_chip(inspected, 42)}{intent}", limit)
        terrain = self.terrain_description(self.cursor)
        zone_text = ""
        if zone:
            zone_text = f" | Zone {zone.name}:{zone.kind} {zone.duration}t"
        return clip(f"Cursor: {terrain}{zone_text}", limit)

    def battlefield_pressure_line(self, limit: int = 80) -> str:
        enemies = self.enemies_alive()
        if not enemies:
            return "Pressure: no enemies remain"
        top = max(enemies, key=lambda e: (self.ui_enemy_intent_priority(e), self.enemy_threat_value(e.name), e.hp))
        dangerous = sum(1 for e in enemies if self.ui_enemy_intent_priority(e) >= 70)
        zone_bits = f" | Zones {len(self.zones)}" if self.zones else ""
        ow_bits = f" | OW {len(self.overwatch_actions)}" if self.overwatch_actions else ""
        return clip(f"Pressure: {dangerous} high-threat | Top: {top.name} ({self.ui_enemy_intent_summary(top)}){zone_bits}{ow_bits}", limit)

    def action_recommendation(self, hero: Unit) -> str:
        if hero.action_points <= 0:
            return "No AP: end turn or switch heroes."
        if hero.hp <= max(3, hero.max_hp // 4):
            if any(hero.inventory.get(item.name, 0) > 0 and item.effect == "heal" for item in self.items):
                return "Low HP: consider Item or Guard."
            return "Low HP: consider Guard or safer movement."
        kills = []
        for enemy in self.enemies_alive():
            if enemy.pos in self.weapon_area(hero.pos, hero.weapon):
                if enemy.hp <= self.weapon_damage_against(hero, enemy, hero.weapon):
                    kills.append(enemy.name)
        if kills:
            return "Attack can KO: " + ", ".join(kills[:2])
        usable_skills = [s for s in self.available_skills(hero) if hero.mp >= s.mp_cost and s.effect == "damage"]
        for skill in usable_skills:
            for tile in self.skill_range(hero.pos, skill):
                targets = self.skill_targets(hero, tile, skill)
                if len(targets) >= 2:
                    return f"{skill.name} can hit {len(targets)} enemies."
        if hero.action_points >= 2 and self.enemies_alive():
            return "Set up: Move, Overwatch, or apply status."
        return "Use final AP carefully; Guard is often safe."

    def combat_legend_line(self) -> str:
        if self.state == "target_move":
            return "+ move | * path | ! danger | ? enemy path"
        if self.state == "target_attack":
            return "x weapon reach | <unit> affected | B barrels"
        if self.state == "target_skill":
            return "o skill range | O area | <unit> hit"
        if self.state == "target_item":
            return "O item area | <unit> hit"
        if self.state == "target_overwatch":
            return "W watched tiles | !unit! covered"
        if self.state == "enemy_view":
            return "Enemy View: sort/read intent/counterplay"
        return "+ move | x attack | O area | W overwatch | E/H/X optional objectives | F/I/S/E/P/L/D zones"

    def hero_roster_chip(self, hero: Unit) -> str:
        if not hero.active:
            return f"{hero.name}:reserve"
        if not hero.alive:
            return f"{hero.name}:DOWN"
        role = "P" if not hero.ai_controlled else "AI"
        status = self.status_text(hero)
        suffix = f" {status}" if status else ""
        return f"{hero.name}:{role} HP{hero.hp}/{hero.max_hp} AP{hero.action_points}{suffix}"

    def active_party_summary(self, limit: int = 80) -> str:
        chips = [self.hero_roster_chip(h) for h in self.heroes if h.active]
        return clip(" | ".join(chips), limit)

    def main_menu_message(self) -> str:
        return self.messages[-1] if self.messages else "Choose a map or manage your party."

    def map_flavor_text(self, name: str) -> str:
        flavor = {
            "Training Yard": "Optional tutorial arena with a harmless training dummy, one slime, open lanes, and safe cover.",
            "Advanced Training Yard": "Advanced tutorial arena with chokepoints, terrain hazards, support pressure, and mixed enemy roles.",
            "Riverwatch Ford": "Balanced training ground with river lanes and bridge pressure.",
            "Stonewater Crossing": "Bridge/canal map with tight crossings and cover pockets.",
            "Broken Gate Ruins": "Ruined chokepoints, stone cover, and awkward lines of sight.",
            "Twinlane Grove": "Orchard lanes, trees, and split approaches.",
            "Spring Bloomfield": "Soft cover and bloom lanes around a narrow ford.",
            "Highsummer Channel": "Open summer banks with long water-channel approaches.",
            "Amber Harvest": "Autumn lanes with staggered walls and harvest-field cover.",
            "Frostpine Crossing": "Winter cover, icy-looking stone, and a guarded crossing.",
            "Moonlit Quarry": "Large quarry with rock cover, side pockets, and long flanking lanes.",
            "Flooded Causeway": "Wide waterworks battlefield with bridge control and muddy approaches.",
            "Briarfall Basin": "Large thorn basin with soft cover, split lanes, and control-heavy terrain.",
            "Emberglass Works": "Volatile forge ruins with barrels, bridges, and explosive cover play.",
            "Snowmelt Terrace": "Icy terrace map with long lanes, bridges, and slippery control zones.",
            "Gatehouse Bastion": "Fortified gatehouse with twin towers, a central gate lane, and side pressure.",
            "Inner Bailey Keep": "Courtyard fight inside a keep with side structures and a guarded center.",
            "Rampart Arsenal": "Fortress arsenal packed with barrels, crates, and volatile sightlines.",
            "Floodgate Citadel": "Citadel waterworks with flood channels, bridges, mud, and control rooms.",
            "Frostwall Redoubt": "Frozen redoubt with inner walls, ice lanes, and heavy defensive cover.",
        }
        return flavor.get(name, "Prototype arena.")

    def map_grid_for_name(self, name: str) -> List[List[str]]:
        for map_name, grid, _positions in self.maps:
            if map_name == name:
                return grid
        return self.map if getattr(self, "map_name", "") == name else []

    def map_tile_counts(self, name: str) -> Dict[str, int]:
        grid = self.map_grid_for_name(name)
        counts: Dict[str, int] = {}
        for row in grid:
            for tile in row:
                counts[tile] = counts.get(tile, 0) + 1
        return counts

    def map_trait_tags(self, name: str) -> List[str]:
        explicit = {
            "Training Yard": ["tutorial", "guided", "low threat"],
            "Advanced Training Yard": ["advanced tutorial", "chokepoints", "mixed roles"],
            "Riverwatch Ford": ["bridges", "balanced", "training"],
            "Stonewater Crossing": ["bridges", "cover", "canal"],
            "Broken Gate Ruins": ["ruins", "chokepoints", "cover"],
            "Twinlane Grove": ["split lanes", "trees", "flanking"],
            "Spring Bloomfield": ["soft cover", "river", "seasonal"],
            "Highsummer Channel": ["open lanes", "water", "seasonal"],
            "Amber Harvest": ["lanes", "cover", "seasonal"],
            "Frostpine Crossing": ["ice", "cover", "seasonal"],
            "Moonlit Quarry": ["large", "rock cover", "flanks"],
            "Flooded Causeway": ["large", "bridges", "mud"],
            "Briarfall Basin": ["large", "thorns", "control"],
            "Emberglass Works": ["large", "barrels", "forge"],
            "Snowmelt Terrace": ["large", "ice", "bridges"],
            "Gatehouse Bastion": ["stronghold", "gate lane", "towers"],
            "Inner Bailey Keep": ["stronghold", "courtyard", "side rooms"],
            "Rampart Arsenal": ["stronghold", "barrels", "rooms"],
            "Floodgate Citadel": ["stronghold", "waterworks", "bridges"],
            "Frostwall Redoubt": ["stronghold", "ice", "inner wall"],
        }
        if name in explicit:
            return explicit[name]

        counts = self.map_tile_counts(name)
        tags: List[str] = []
        if counts.get(TILE_WATER, 0) > 10 or counts.get(TILE_BRIDGE, 0) > 5:
            tags.append("bridges")
        if counts.get(TILE_WALL, 0) > 40:
            tags.append("walls")
        if counts.get(TILE_BARREL, 0) >= 3:
            tags.append("barrels")
        if counts.get(TILE_THORNS, 0) > 3:
            tags.append("thorns")
        if counts.get(TILE_ICE, 0) > 3:
            tags.append("ice")
        return tags or ["standard"]

    def map_trait_summary(self, name: str) -> str:
        return ", ".join(self.map_trait_tags(name)[:3])

    def terrain_profile_line(self, name: str) -> str:
        counts = self.map_tile_counts(name)
        pairs = [
            ("water", counts.get(TILE_WATER, 0)),
            ("bridges", counts.get(TILE_BRIDGE, 0)),
            ("walls", counts.get(TILE_WALL, 0)),
            ("cover", sum(counts.get(t, 0) for t in COVER_TILES)),
            ("barrels", counts.get(TILE_BARREL, 0)),
            ("crates", counts.get(TILE_CRATE, 0)),
            ("thorns", counts.get(TILE_THORNS, 0)),
            ("ice", counts.get(TILE_ICE, 0)),
            ("mud", counts.get(TILE_MUD, 0)),
        ]
        shown = [f"{label} {amount}" for label, amount in pairs if amount > 0]
        return ", ".join(shown[:7]) if shown else "open terrain"

    def map_tactical_advice(self, name: str) -> List[str]:
        tags = set(self.map_trait_tags(name))
        advice: List[str] = []
        if "advanced tutorial" in tags:
            advice.append("Use Enemy View sorting before moving; the mixed enemy roles punish blind advances.")
            advice.append("Practice guard lines, overwatch lanes, support recovery, and focus fire through chokepoints.")
        if "tutorial" in tags:
            advice.append("Practice on the Training Dummy first, then finish the Slime when you are ready.")
            advice.append("Follow the sidebar lesson: it gives the next action, controls, and reason.")
        if "stronghold" in tags:
            advice.append("Bring at least one ranged/control option; fortress rooms create hard approach lanes.")
        if "gate lane" in tags or "chokepoints" in tags:
            advice.append("Overwatch, cones, and guard skills are valuable in narrow approaches.")
        if "courtyard" in tags:
            advice.append("Avoid fighting from the open center unless your frontline is already guarding.")
        if "side rooms" in tags or "rooms" in tags:
            advice.append("Check side rooms before overcommitting; flankers and Burrowers can punish isolation.")
        if "barrels" in tags or "forge" in tags:
            advice.append("Watch barrel chains; fire effects and Ember Imps can turn cover into a hazard.")
        if "bridges" in tags or "waterworks" in tags or "water" in tags:
            advice.append("Control bridges early; forced movement and roots are stronger near water lanes.")
        if "ice" in tags:
            advice.append("Plan movement carefully on ice; roots and Frost Moths become more dangerous.")
        if "thorns" in tags:
            advice.append("Avoid long thorn paths unless you can heal or end the fight quickly.")
        if "flanking" in tags or "flanks" in tags or "split lanes" in tags:
            advice.append("Do not split too thin; fast enemies punish isolated party members.")
        if "open lanes" in tags:
            advice.append("Use cover or pressure ranged enemies before crossing open sightlines.")
        if not advice:
            advice.append("Balanced map: use Enemy View and terrain preview to choose the first engagement.")
        return advice[:3]

    def map_briefing_lines(self, name: str) -> List[str]:
        threat = self.map_default_threat_value(name)
        return [
            f"Traits: {self.map_trait_summary(name)}",
            f"Terrain: {self.terrain_profile_line(name)}",
            f"Threat: {threat} {self.threat_difficulty_name(threat)}",
            *("Advice: " + line for line in self.map_tactical_advice(name)),
        ]

    def initial_combat_stats(self) -> Dict[str, object]:
        return {
            "rounds": 1,
            "player_damage": 0,
            "follower_damage": 0,
            "enemy_damage": 0,
            "kills": 0,
            "skills_used": 0,
            "potions_used": 0,
            "items_used": 0,
            "xp_earned": 0,
            "party_xp_bonus": 0,
            "level_ups": 0,
            "defeated": [],
            "loot_log": [],
            "rare_loot_found": 0,
            "cache_rewards": 0,
            "actor_damage": {},
            "actor_kos": {},
            "damage_taken": {},
            "skill_usage": {},
            "skill_user_usage": {},
            "item_usage": {},
            "combo_triggers": 0,
            "combo_ap_refunded": 0,
            "combo_mp_refunded": 0,
            "ap_transferred": 0,
            "overwatch_hits": 0,
            "barrels_detonated": 0,
            "terrain_damage": 0,
            "terrain_heal": 0,
            "terrain_mp": 0,
            "zones_created": 0,
            "zone_damage": 0,
            "status_applications": 0,
            "zone_status_applications": 0,
            "build_synergy_uses": 0,
            "encounter_threat": 0,
            "map_traits": [],
            "map_profile": "",
            "balance_notes": [],
        }

    def bump_stat_dict(self, key: str, name: str, amount: int = 1) -> None:
        bucket = self.combat_stats.setdefault(key, {})
        if isinstance(bucket, dict):
            bucket[name] = int(bucket.get(name, 0)) + amount

    def record_actor_damage(self, actor: Optional[Unit], amount: int) -> None:
        if actor is None or amount <= 0:
            return
        self.bump_stat_dict("actor_damage", actor.name, amount)

    def record_damage_taken(self, unit: Optional[Unit], amount: int) -> None:
        if unit is None or amount <= 0:
            return
        self.bump_stat_dict("damage_taken", unit.name, amount)

    def record_skill_use(self, actor: Optional[Unit], skill: Skill) -> None:
        self.bump_stat_dict("skill_usage", skill.name, 1)
        if actor is not None:
            self.bump_stat_dict("skill_user_usage", f"{actor.name}:{skill.name}", 1)

    def record_item_use(self, actor: Optional[Unit], item: Item) -> None:
        self.bump_stat_dict("item_usage", item.name, 1)

    def record_ko(self, actor: Optional[Unit], enemy: Unit) -> None:
        if actor is not None:
            self.bump_stat_dict("actor_kos", actor.name, 1)

    def record_starting_threat(self) -> None:
        self.combat_stats["encounter_threat"] = sum(self.enemy_threat_value(e.name) for e in self.enemies if e.active)
        self.combat_stats["map_traits"] = self.map_trait_tags(self.map_name)
        self.combat_stats["map_profile"] = self.terrain_profile_line(self.map_name)

    def map_default_threat_value(self, map_name: str) -> int:
        return self.encounter_threat_value(self.enemy_loadout_for_map(map_name))

    def threat_difficulty_name(self, value: int) -> str:
        if value < 70:
            return "Low"
        if value < 120:
            return "Moderate"
        if value < 180:
            return "High"
        return "Extreme"

    def tactical_mvp(self) -> str:
        scores: Dict[str, int] = {}
        damage = self.combat_stats.get("actor_damage", {})
        kos = self.combat_stats.get("actor_kos", {})
        skill_users = self.combat_stats.get("skill_user_usage", {})
        if isinstance(damage, dict):
            for name, amount in damage.items():
                scores[name] = scores.get(name, 0) + int(amount)
        if isinstance(kos, dict):
            for name, amount in kos.items():
                scores[name] = scores.get(name, 0) + int(amount) * 20
        if isinstance(skill_users, dict):
            for key, amount in skill_users.items():
                name = str(key).split(":", 1)[0]
                scores[name] = scores.get(name, 0) + int(amount) * 3
        for hero in self.heroes:
            if hero.active and hero.alive:
                scores.setdefault(hero.name, 0)
        if not scores:
            return "None"
        name, score = max(scores.items(), key=lambda item: (item[1], item[0]))
        return f"{name} ({score} impact)"

    def most_used_from(self, key: str) -> str:
        bucket = self.combat_stats.get(key, {})
        if not isinstance(bucket, dict) or not bucket:
            return "None"
        name, count = max(bucket.items(), key=lambda item: (int(item[1]), str(item[0])))
        return f"{name} x{count}"

    def compact_stat_dict(self, key: str, limit: int = 4) -> str:
        bucket = self.combat_stats.get(key, {})
        if not isinstance(bucket, dict) or not bucket:
            return "None"
        items = sorted(bucket.items(), key=lambda item: int(item[1]), reverse=True)[:limit]
        return ", ".join(f"{name} {amount}" for name, amount in items)

    def balance_note_lines(self, result: str) -> List[str]:
        notes: List[str] = []
        rounds = int(self.combat_stats.get("rounds", self.round_no))
        dealt = int(self.combat_stats.get("player_damage", 0)) + int(self.combat_stats.get("follower_damage", 0))
        taken = int(self.combat_stats.get("enemy_damage", 0))
        threat = int(self.combat_stats.get("encounter_threat", 0))
        grade = self.performance_grade()

        if result.startswith("Victory"):
            if rounds <= 3 and taken <= 10:
                notes.append("Possibly too easy: fast clear with little damage taken.")
            elif taken > dealt * 0.75 and rounds >= 7:
                notes.append("Tense fight: high incoming damage and long duration.")
            elif rounds >= 9:
                notes.append("Long fight: consider lowering enemy HP or improving player damage options.")
            if grade in ("S", "A") and threat >= 150:
                notes.append("High-threat fight cleared efficiently; player tools may be strong.")
        else:
            if threat >= 150:
                notes.append("Defeat against high threat is expected; mark as boss/high-risk tuning.")
            else:
                notes.append("Defeat at this threat may indicate overtuned enemies or unclear tactics.")

        if int(self.combat_stats.get("skills_used", 0)) == 0:
            notes.append("No skills used; skill incentives or UI discoverability may need work.")
        if int(self.combat_stats.get("items_used", 0)) >= 4:
            notes.append("High item use; encounter may be attrition-heavy.")
        if int(self.combat_stats.get("combo_triggers", 0)) == 0 and int(self.combat_stats.get("skills_used", 0)) >= 3:
            notes.append("Skills used but no combos triggered; synergy setup may be too hard to notice/use.")
        if not notes:
            notes.append("No obvious tuning red flags from this run.")
        return notes

    def tactical_report_lines(self, result: str) -> List[str]:
        dealt = int(self.combat_stats.get("player_damage", 0)) + int(self.combat_stats.get("follower_damage", 0))
        taken = int(self.combat_stats.get("enemy_damage", 0))
        threat = int(self.combat_stats.get("encounter_threat", 0))
        lines: List[str] = []
        lines.append(f"Threat: {threat} {self.threat_difficulty_name(threat)} | Grade: {self.performance_grade()} | Rounds: {self.combat_stats.get('rounds', self.round_no)}")
        lines.append(f"Damage: dealt {dealt}, taken {taken} | KOs {self.combat_stats.get('kills', 0)} | MVP {self.tactical_mvp()}")
        lines.append(f"Skills {self.combat_stats.get('skills_used', 0)} | Items {self.combat_stats.get('items_used', 0)} | Overwatch hits {self.combat_stats.get('overwatch_hits', 0)}")
        lines.append(f"Terrain: dmg/heal/MP {self.combat_stats.get('terrain_damage', 0)}/{self.combat_stats.get('terrain_heal', 0)}/{self.combat_stats.get('terrain_mp', 0)} | Barrels {self.combat_stats.get('barrels_detonated', 0)}")
        lines.append(f"Zones: {self.combat_stats.get('zones_created', 0)} created, {self.combat_stats.get('zone_damage', 0)} dmg, {self.combat_stats.get('zone_status_applications', 0)} statuses")
        notes = self.balance_note_lines(result)
        if notes:
            lines.append("Note: " + notes[0])
        return lines


    def performance_grade(self) -> str:
        if self.game_over() == "Defeat. Your party was wiped out.":
            return "F"
        rounds = self.round_no
        downed = sum(1 for h in self.heroes if h.active and not h.alive)
        potions = self.combat_stats.get("potions_used", 0)
        if rounds <= 4 and downed == 0 and potions == 0:
            return "S"
        if rounds <= 6 and downed == 0:
            return "A"
        if rounds <= 8 and downed <= 1:
            return "B"
        return "C"

    def tactic_description(self) -> str:
        descriptions = {
            "Balanced": "Mira weighs damage, MP, safety, KOs, and Overwatch lanes evenly.",
            "Aggressive": "Mira chases damage first and uses Overwatch only when no clean hit exists.",
            "Cautious": "Mira avoids danger and favors safe Overwatch lanes over risky movement.",
            "Support": "Mira prioritizes survival, control skills, and protective Overwatch.",
        }
        return descriptions.get(self.follower_tactic, "Standard behavior.")

    def action_enabled(self, label: str) -> bool:
        hero = self.selected_hero

        if label == "Map" and not self.allow_battle_map_selection:
            return False
        if label == "Skills":
            return any(self.action_enabled(opt) for opt in self.SKILL_GROUP_MENU)
        if label == "Party":
            return True
        if label == "Enemy View":
            return bool(self.enemy_view_targets())

        if label == "Cast Skill":
            label = "Skill"

        if label in ("Move", "Attack", "Skill", "Item", "Guard", "Overwatch") and hero.action_points <= 0:
            return False
        if label == "Skill" and not any(hero.mp >= s.mp_cost for s in self.available_skills(hero)):
            return False
        if label == "Item" and not self.usable_items(hero):
            return False
        if label == "Overwatch" and not self.overwatch_options(hero):
            return False
        return True


    def terrain_description(self, pos: Pos) -> str:
        tile = self.tile_at(pos)
        names = {
            TILE_FLOOR: "Open ground",
            TILE_DIRT: "Dirt path",
            TILE_GRASS: "Tall grass: light cover",
            TILE_MUD: "Mud: costs 2 movement",
            TILE_BRIDGE: "Bridge",
            TILE_STONE: "Stone cover",
            TILE_THORNS: "Thorns: 1 damage when entered",
            TILE_SPRING: "Healing spring: +2 HP at turn start",
            TILE_CRYSTAL: "Mana crystal: +2 MP at turn start",
            TILE_ICE: "Ice: slide when stopping on it",
            TILE_BARREL: "Explosive barrel: attack/AoE to detonate",
            TILE_CRATE: "Crate: blocks movement and grants cover",
            TILE_WALL: "Fence/wall",
            TILE_TREE: "Wooded cover",
            TILE_WATER: "Water",
        }
        marker = self.objective_marker_at(pos)
        zone_text = ""
        if marker == "exit":
            zone_text += " | Objective exit"
        elif marker == "hold":
            zone_text += " | Objective hold zone"
        elif marker == "object":
            zone_text += " | Objective object"
        zone = self.zone_at(pos)
        if zone:
            bits = []
            if zone.damage:
                bits.append(f"{zone.damage} dmg")
            if zone.status:
                bits.append(f"+{zone.status}")
            zone_text += f" | {zone.name} zone ({zone.kind}, {zone.duration}t, {'/'.join(bits) if bits else 'effect'})"
        if tile in PASSABLE:
            return names.get(tile, "Ground") + zone_text
        return names.get(tile, "Blocked") + zone_text


    def preview_lines(self) -> List[str]:
        """Small context-sensitive tactical hint for the right panel."""
        hero = self.selected_hero
        lines: List[str] = []

        if self.state == "command":
            option = self.current_menu_option()
            if option == "Inspect":
                lines.append("Examine tiles and units")
                lines.append("No AP cost")
            elif option == "Enemy View":
                lines.append(f"Active enemies: {len(self.enemy_view_targets())}")
                if self.enemies_alive():
                    lines.append("Intent / roles / signatures")
                lines.append("No AP cost")
            elif option == "Move":
                danger = self.enemy_danger_tiles()
                safe_tiles = [p for p in self.reachable_tiles(hero) if p not in danger]
                lines.append(f"Reachable: {len(self.reachable_tiles(hero))}")
                lines.append(f"Safer tiles: {len(safe_tiles)}")
            elif option == "Attack":
                targets = [e.name for e in self.enemies_alive() if e.pos in self.weapon_area(hero.pos, hero.weapon)]
                lines.append(f"{hero.weapon.name}: {hero.weapon.shape} / {hero.weapon.damage_type}")
                lines.append("Targets: " + (", ".join(targets[:3]) if targets else "none"))
            elif option == "Skills":
                usable = [s.name for s in self.available_skills(hero) if hero.mp >= s.mp_cost]
                lines.append("Cast Skill / Overwatch / Guard")
                lines.append("Skills: " + (", ".join(usable[:2]) if usable else "none"))
                if len(usable) > 2:
                    lines.append(f"+{len(usable)-2} more")
            elif option == "Item":
                usable = [f"{item.name} x{hero.inventory.get(item.name, 0)}" for item in self.items if hero.inventory.get(item.name, 0) > 0]
                lines.append("Items: " + (", ".join(usable[:2]) if usable else "none"))
                if len(usable) > 2:
                    lines.append(f"+{len(usable)-2} more")
            elif option == "Party":
                manual = self.active_manual_companion_names()
                ai = self.active_ai_companion_names()
                lines.append("Hero / Tactics / Control")
                lines.append("Manual comps: " + (", ".join(manual) if manual else "none"))
                lines.append("AI comps: " + (", ".join(ai) if ai else "none"))
            elif option == "Map":
                lines.append(self.map_name)
                lines.append("Choose current map to reset")
            elif option == "End Turn":
                ai_count = len(self.followers_alive())
                lines.append(f"AI followers: {ai_count}")
                lines.append("Then enemies act")
            return lines

        if self.state == "skill_group_menu":
            option = self.current_skill_group_option()
            if option == "Cast Skill":
                usable = [s.name for s in self.available_skills(hero) if hero.mp >= s.mp_cost]
                lines.append("Open the full skill list")
                lines.append("Usable: " + (", ".join(usable[:2]) if usable else "none"))
            elif option == "Overwatch":
                lines.append("Pick attack/skill, watch area")
                lines.append("Triggers on enemy movement")
            elif option == "Guard":
                lines.append("Halves incoming damage")
                lines.append("Uses 1 AP")
            return lines

        if self.state == "party_group_menu":
            option = self.current_party_group_option()
            if option == "Hero":
                manual = [h.name for h in self.controllable_heroes_alive()]
                lines.append("Select manual hero")
                lines.append("Manual: " + (", ".join(manual) if manual else "none"))
            elif option == "Tactics":
                lines.append(f"AI tactic: {self.follower_tactic}")
                lines.append("Only affects AI companions")
            elif option == "Control":
                lines.append("Set each companion")
                lines.append("Manual: " + (", ".join(self.active_manual_companion_names()) if self.active_manual_companion_names() else "none"))
                lines.append("AI: " + (", ".join(self.active_ai_companion_names()) if self.active_ai_companion_names() else "none"))
            return lines

        if self.state == "control_menu":
            selected = self.heroes[self.control_menu_index % len(self.heroes)]
            lines.append("Toggle companion Manual/AI")
            lines.append(f"Selected: {selected.name}")
            lines.append(self.companion_control_label(selected))
            return lines

        if self.state == "inspect":
            lines.append(self.terrain_description(self.cursor))
            inspected = self.unit_at(self.cursor)
            if inspected:
                lines.append(self.status_text(inspected) or "No status")
            return lines

        if self.state == "enemy_view":
            enemy = self.selected_enemy_view_target()
            if enemy:
                lines.append(f"Sort: {self.current_enemy_view_sort()}")
                lines.extend(self.enemy_inspection_lines(enemy)[:5])
            else:
                lines.append("No enemy selected.")
            return lines

        if self.state == "target_move":
            danger = self.enemy_danger_tiles()
            valid = self.cursor in self.reachable_tiles(hero)
            safe = self.cursor not in danger
            lines.append(self.terrain_description(self.cursor))
            if hero.rooted > 0:
                lines.append("Rooted: move will break roots")
            lines.append("Destination valid" if valid else "Invalid destination")
            lines.append("Safe tile" if safe else "In enemy danger")
            return lines

        if self.state == "target_attack":
            weapon = hero.weapon
            targets = self.weapon_targets(hero, self.cursor, weapon)
            barrels = self.weapon_barrel_tiles(hero, self.cursor, weapon)
            lines.append(f"{weapon.name}: {self.weapon_profile_label(weapon)}")
            if targets:
                total = sum(self.weapon_damage_against(hero, target, weapon) for target in targets)
                kos = sum(1 for target in targets if target.hp <= self.weapon_damage_against(hero, target, weapon))
                lines.append(f"Targets: {len(targets)} | Total dmg {total} | KOs {kos}")
                lines.append("Affects: " + ", ".join(t.name for t in targets[:3]))
            elif barrels:
                lines.append(f"Barrels hit: {len(barrels)}")
            else:
                lines.append("No target in pattern")
            return lines

        if self.state == "target_skill":
            skill = self.selected_skill(hero)
            affected = self.skill_targets(hero, self.cursor, skill)
            lines.append(f"{skill.name}: {self.skill_target_label(skill)} | MP {skill.mp_cost}")
            lines.append("Affects: " + (", ".join(e.name for e in affected[:3]) if affected else "none"))
            target_unit = self.unit_at(self.cursor)
            invalid = self.skill_target_validity_message(hero, target_unit, skill)
            if invalid and self.cursor in self.skill_range(hero.pos, skill):
                lines.append(c(invalid, Style.BRIGHT_YELLOW))
            elif hero.mp < skill.mp_cost:
                lines.append(c("Not enough MP", Style.BRIGHT_RED))
            elif skill.effect == "damage":
                kills = sum(1 for e in affected if e.hp <= skill.damage)
                lines.append(f"Damage {skill.damage} | KOs {kills}")
            elif skill.effect == "heal":
                lines.append(f"Heals {skill.heal_amount} HP")
            elif skill.status:
                lines.append(f"Applies {skill.status}")
            else:
                lines.append(self.skill_rank_label(hero, skill.name))
            return lines

        if self.state == "support_target_menu":
            skill = self.selected_skill(hero)
            target = self.selected_support_target()
            lines.append(self.skill_targeting_hint(skill))
            if target:
                lines.append(f"Selected: {target.name}")
                invalid = self.skill_target_validity_message(hero, target, skill)
                if invalid:
                    lines.append(c(invalid, Style.BRIGHT_YELLOW))
                elif skill.effect == "heal":
                    heal = min(skill.heal_amount, target.max_hp - target.hp)
                    lines.append(f"Heal preview: +{heal} HP")
                elif skill.effect == "restore_mp":
                    gain = min(skill.mp_amount, target.max_mp - target.mp)
                    lines.append(f"MP preview: +{gain} MP")
                elif skill.effect == "cleanse":
                    lines.append("Removes poison/root/vulnerable")
                elif skill.effect == "guard":
                    lines.append("Target gains Guard")
                elif skill.effect == "transfer_ap":
                    lines.append(f"Transfer preview: {hero.action_points} AP")
                    lines.append(f"{target.name} AP after: {target.action_points + hero.action_points}")
            return lines

        if self.state == "item_target_menu":
            item = self.selected_item()
            target = self.selected_item_target()
            lines.append(self.item_targeting_hint(item))
            if target:
                lines.append(f"Selected: {target.name}")
                invalid = self.item_target_validity_message(hero, item, target=target)
                if invalid:
                    lines.append(c(invalid, Style.BRIGHT_YELLOW))
                elif item.effect == "heal":
                    lines.append(f"Heal preview: +{min(item.amount, target.max_hp - target.hp)} HP")
                elif item.effect == "mp":
                    lines.append(f"MP preview: +{min(item.amount, target.max_mp - target.mp)} MP")
                elif item.effect == "cleanse":
                    lines.append("Removes current status effects")
                elif item.effect == "guard":
                    lines.append("Target gains Guard")
            return lines

        if self.state == "target_item":
            item = self.selected_item()
            targets = self.item_enemy_targets(hero, item, self.cursor)
            lines.append(self.item_targeting_hint(item))
            lines.append("Hits: " + (", ".join(e.name for e in targets) if targets else "none"))
            invalid = self.item_target_validity_message(hero, item, target_pos=self.cursor)
            if invalid:
                lines.append(c(invalid, Style.BRIGHT_YELLOW))
            else:
                kills = sum(1 for e in targets if e.hp <= item.amount)
                if kills:
                    lines.append(f"Potential KOs: {kills}")
            return lines

        if self.state == "target_overwatch":
            option = self.pending_overwatch_option or self.selected_overwatch_option()
            tiles = self.overwatch_tiles_for_option(hero, option, self.cursor)
            targets = self.overwatch_target_names_for_option(hero, option, self.cursor)
            lines.append(f"Watching tiles: {len(tiles)}")
            lines.append("Covered now: " + (", ".join(targets) if targets else "none"))
            if option.get("kind") == "skill":
                skill = self.skill_from_overwatch_option(option)
                lines.append(f"MP spent on trigger: {skill.mp_cost}")
            else:
                lines.append("Basic weapon attack")
            return lines

        return lines

    def role_description(self, role: str) -> str:
        return {
            "skirmisher": "mobile harasser; avoids fair trades",
            "brute": "frontline charger; punishes exposed targets",
            "controller": "roots, spores, and reshapes the map",
            "ranged": "keeps distance and pressures weak targets",
            "pouncer": "fast flanker; punishes isolation",
            "guardian": "durable setup enemy; protects pressure lines",
            "blighter": "poison/status pressure and attrition",
            "boss": "multi-pattern battlefield control",
            "dummy": "safe practice target; does not threaten the party",
        }.get(role, "general enemy")

    def enemy_signature_lines_for_name(self, name: str) -> List[str]:
        base = self.enemy_base_name(name)
        lines: List[str] = []
        if base == "Training Dummy":
            lines.append("Practice Target: stationary, harmless, and built for trying attacks safely.")
        elif base == "Wolf":
            lines.append("Pack Pounce: bonus damage vs isolated/statused targets; stronger near wolves.")
        elif base == "Crow":
            lines.append("Harrier Dive: hits, applies vulnerable, then hops away.")
        elif base == "Slime":
            lines.append("Ooze Mire: creates poisonous mud zones that punish clustering.")
        elif base == "Sporeling":
            lines.append("Spore Patch: poisons/vulnerables clusters and muddies terrain.")
        elif base == "Old Briarthorn":
            lines.append("Briar Bloom: creates thorn patches, damages, and roots clustered heroes.")
            lines.append("Briar Heart: when wounded, heals, guards, and creates a thorn zone once.")
        elif base == "Boar":
            lines.append("Brutal Charge: rushes an adjacent landing tile and applies vulnerable.")
            lines.append("War Cry: marks sturdy targets vulnerable before a follow-up.")
        elif base in ("Vine",):
            lines.append("Binding Roots: roots high-value targets from range.")
            lines.append("Toxic Burst: punishes clustered heroes.")
        elif base in ("Marsh Toad",):
            lines.append("Ooze Mire / poison pressure: creates toxic zones and attrition.")
        elif base in ("Shield Guard", "Rockback"):
            lines.append("Shield Wall / War Cry: guards nearby enemies and marks frontliners vulnerable.")
        elif base == "Wisp":
            lines.append("Phase Shot: blinks to a safer lane and fires a rooting frost shot.")
        elif base == "Bandit":
            lines.append("Ranged pressure: prefers distance and weakened targets.")
        elif base == "Razor Hare":
            lines.append("Needle Dash: fast adjacent dash that roots exposed targets.")
        elif base == "Ember Imp":
            lines.append("Cinder Toss: small fire burst that applies vulnerable and can detonate barrels.")
        elif base == "Frost Moth":
            lines.append("Frost Cloud: creates ice, a frost zone, and roots clustered heroes.")
        elif base == "Burrower":
            lines.append("Burrow Ambush: ignores lanes to emerge beside a wounded target.")
        elif base == "Thornback":
            lines.append("Quill Volley: ranged burst that makes clustered heroes vulnerable.")
        if name.startswith("Elite "):
            lines.append("Elite Drive: when pressured, clears bad status, heals, and guards.")
        return lines or ["No special signature behavior."]

    def enemy_status_detail(self, enemy: Unit) -> str:
        parts: List[str] = []
        status = self.status_text(enemy)
        if status:
            parts.append(status)
        cooldowns = [f"{name}:{value}" for name, value in enemy.cooldowns.items() if value > 0]
        if cooldowns:
            parts.append("CD " + ",".join(cooldowns))
        if enemy.guard:
            parts.append("Guard")
        if enemy.elite:
            parts.append("Elite")
        if enemy.boss:
            parts.append("Boss")
        return " | ".join(parts) if parts else "No status/cooldowns"

    def enemy_target_preference_line(self, enemy: Unit) -> str:
        target = self.enemy_best_target(enemy) if self.heroes_alive() and enemy.active and enemy.alive else None
        if not target:
            return "Target preference: none"
        score = self.enemy_target_score(enemy, target)
        return f"Target preference: {target.name} (score {score})"

    def enemy_view_targets(self) -> List[Unit]:
        targets = self.enemies_alive()
        if targets:
            return targets
        return [e for e in self.enemies if e.active]

    def enemy_view_sort_modes(self) -> List[str]:
        return ["List", "Threat", "Low HP", "Nearest", "Intent"]

    def current_enemy_view_sort(self) -> str:
        modes = self.enemy_view_sort_modes()
        self.enemy_view_sort_index %= len(modes)
        return modes[self.enemy_view_sort_index]

    def enemy_intent_priority(self, enemy: Unit) -> int:
        intent = (
            self.ui_enemy_intent_summary(enemy)
            if self.turn == "hero"
            else self.enemy_intent_summary(enemy)
        ).lower() if enemy.active and enemy.alive else ""
        score = 0
        if "briar" in intent or "spore" in intent or "charge" in intent or "cinder" in intent or "frost" in intent or "burrow" in intent:
            score += 80
        if "pack" in intent or "harry" in intent or "elite" in intent or "dash" in intent or "quill" in intent:
            score += 70
        if "attack" in intent or "poison" in intent or "root" in intent:
            score += 50
        if "move" in intent:
            score += 20
        if enemy.boss:
            score += 30
        if enemy.elite:
            score += 20
        return score

    def sorted_enemy_view_targets(self) -> List[Unit]:
        targets = self.enemy_view_targets()
        mode = self.current_enemy_view_sort()
        if mode == "Threat":
            return sorted(targets, key=lambda e: (self.enemy_threat_value(e.name), e.hp, e.name), reverse=True)
        if mode == "Low HP":
            return sorted(targets, key=lambda e: (e.hp / max(1, e.max_hp), e.hp, e.name))
        if mode == "Nearest":
            hero = self.selected_hero
            return sorted(targets, key=lambda e: (manhattan(hero.pos, e.pos), -self.enemy_threat_value(e.name), e.name))
        if mode == "Intent":
            return sorted(targets, key=lambda e: (self.enemy_intent_priority(e), self.enemy_threat_value(e.name), e.name), reverse=True)
        return targets

    def cycle_enemy_view_sort(self, delta: int = 1) -> None:
        self.enemy_view_sort_index = (self.enemy_view_sort_index + delta) % len(self.enemy_view_sort_modes())
        self.enemy_view_index = 0
        target = self.selected_enemy_view_target()
        if target:
            self.cursor = target.pos
        self.push(f"Enemy View sort: {self.current_enemy_view_sort()}.")

    def bestiary_filter_modes(self) -> List[str]:
        return ["All", "Melee", "Ranged", "Control", "High Threat", "Boss"]

    def current_bestiary_filter(self) -> str:
        modes = self.bestiary_filter_modes()
        self.bestiary_filter_index %= len(modes)
        return modes[self.bestiary_filter_index]

    def bestiary_filtered_roster(self) -> List[str]:
        mode = self.current_bestiary_filter()
        roster = self.enemy_roster_names()
        if mode == "All":
            return roster
        if mode == "Melee":
            return [name for name in roster if (self.enemy_by_name(name) and self.enemy_by_name(name).role in ("brute", "pouncer", "guardian", "skirmisher"))]
        if mode == "Ranged":
            return [name for name in roster if (self.enemy_by_name(name) and self.enemy_by_name(name).role in ("ranged", "skirmisher"))]
        if mode == "Control":
            return [name for name in roster if (self.enemy_by_name(name) and self.enemy_by_name(name).role in ("controller", "blighter", "boss"))]
        if mode == "High Threat":
            return [name for name in roster if self.enemy_threat_value(name) >= 55]
        if mode == "Boss":
            return [name for name in roster if self.enemy_is_boss_name(name)]
        return roster

    def cycle_bestiary_filter(self, delta: int = 1) -> None:
        self.bestiary_filter_index = (self.bestiary_filter_index + delta) % len(self.bestiary_filter_modes())
        self.bestiary_enemy_index = 0

    def enemy_counterplay_lines_for_name(self, name: str) -> List[str]:
        base = self.enemy_base_name(name)
        role = self.enemy_by_name(name).role if self.enemy_by_name(name) else ""
        notes = {
            "Wolf": ["Stay grouped; isolated heroes invite Pack Pounce.", "Root, guard, or overwatch lanes before wolves close."],
            "Crow": ["Use ranged attacks/Overwatch; chasing wastes AP.", "Guard low-HP targets so Harrier Dive is less punishing."],
            "Slime": ["Do not cluster near it; Ooze Mire creates poisonous mud zones.", "Kill early if toxic mud would clog chokepoints."],
            "Sporeling": ["Do not cluster; Spore Patch punishes tight groups.", "Cleanse poison before attrition snowballs."],
            "Old Briarthorn": ["Spread out before it is injured.", "Expect Briar Heart below half HP; save burst for after it guards.", "Bring root cleanse, ranged pressure, and thorn-safe paths."],
            "Boar": ["Avoid straight open lanes; bait charges into bad terrain.", "Vulnerable frontliners should guard or retreat."],
            "Vine": ["High-AP heroes should avoid ending in root range.", "Use ranged burst before roots control the tempo."],
            "Marsh Toad": ["Cleanse poison and avoid standing together in its mire radius."],
            "Shield Guard": ["Bait Shield Wall before committing burst.", "Use vulnerable effects after its guard cooldown is spent."],
            "Rockback": ["Treat it as a slow wall; kite or debuff before trading."],
            "Wisp": ["Expect Phase Shot if you get close.", "Root, overwatch, or pressure it before it blinks lanes."],
            "Bandit": ["Cover and focus fire prevent ranged chip from adding up."],
            "Training Dummy": ["Use it to test movement, attacks, skill shapes, and item targeting safely."],
            "Razor Hare": ["Keep allies adjacent; Needle Dash punishes loose formations.", "Root or overwatch dash lanes before it reaches your backline."],
            "Ember Imp": ["Do not stand near barrels or cluster around cover.", "Pressure it quickly; Cinder Toss makes follow-up hits worse."],
            "Frost Moth": ["Avoid tight groups on narrow bridges/ice lanes.", "Cleanse root and avoid giving it time to ice over key paths or frost zones."],
            "Burrower": ["Do not leave weak allies isolated; it can bypass normal lanes.", "Guard wounded targets before its Burrow Ambush is ready."],
            "Thornback": ["Spread out before Quill Volley.", "Bait Shield Wall before burst; vulnerable heroes should guard or reposition."],
        }.get(base, [])
        if not notes:
            if role in ("controller", "blighter"):
                notes = ["Spread out and cleanse status before it compounds."]
            elif role in ("ranged", "skirmisher"):
                notes = ["Use cover, range pressure, or overwatch to limit harassment."]
            elif role in ("brute", "guardian", "pouncer"):
                notes = ["Control movement and avoid exposed low-HP targets."]
            else:
                notes = ["Focus fire and watch its intent preview."]
        if name.startswith("Elite "):
            notes.append("Elite Drive can erase vulnerable/root once; bait it before committing.")
        return notes

    def enemy_status_advice(self, enemy: Unit) -> str:
        if not enemy.alive:
            return "Downed enemy."
        if enemy.vulnerable > 0:
            return "Counterplay: focus now; vulnerable bonus is active."
        if enemy.rooted > 0:
            return "Counterplay: reposition or use ranged pressure while rooted."
        if enemy.poison > 0:
            return "Counterplay: poison is ticking; avoid overcommitting resources."
        ready = [name for name, value in enemy.cooldowns.items() if value <= 0]
        if enemy.boss and "Briar Bloom" in ready:
            return "Warning: Briar Bloom may be ready; spread out."
        if self.enemy_family(enemy) == "Sporeling" and "Spore Patch" in ready:
            return "Warning: Spore Patch ready; avoid clusters."
        if self.enemy_family(enemy) == "Wolf" and "Pack Pounce" in ready:
            return "Warning: Pack Pounce ready; keep allies near each other."
        if self.enemy_family(enemy) == "Razor Hare" and "Needle Dash" in ready:
            return "Warning: Needle Dash ready; protect isolated allies."
        if self.enemy_family(enemy) == "Ember Imp" and "Cinder Toss" in ready:
            return "Warning: Cinder Toss ready; avoid barrels and clusters."
        if self.enemy_family(enemy) == "Frost Moth" and "Frost Cloud" in ready:
            return "Warning: Frost Cloud ready; spread out and avoid ice lanes."
        if self.enemy_family(enemy) == "Burrower" and "Burrow Ambush" in ready:
            return "Warning: Burrow Ambush ready; guard wounded allies."
        if self.enemy_family(enemy) == "Thornback" and "Quill Volley" in ready:
            return "Warning: Quill Volley ready; spread out."
        return "No immediate status exploit."

    def enemy_live_threat_lines(self, enemy: Unit) -> List[str]:
        lines: List[str] = []
        hero = self.selected_hero
        dist = manhattan(hero.pos, enemy.pos)
        in_weapon = hero.pos in self.weapon_area(enemy.pos, enemy.weapon)
        can_reach_attack = any(hero.pos in self.weapon_area(pos, enemy.weapon) for pos in self.reachable_tiles(enemy))
        estimated = self.estimated_attack_damage(enemy, hero)
        lines.append(f"Vs {hero.name}: dist {dist}, hit now {'yes' if in_weapon else 'no'}, reach+hit {'yes' if can_reach_attack else 'no'}, est {estimated} dmg")
        lines.append(self.enemy_target_preference_line(enemy))
        lines.append("Status advice: " + self.enemy_status_advice(enemy))
        return lines

    def enemy_map_appearance_lines(self, name: str) -> List[str]:
        maps = [map_name for map_name, _m, _pos in self.maps if name in self.enemy_loadout_for_map(map_name)]
        if not maps:
            return ["Appears in: custom encounters"]
        shown = ", ".join(maps[:3])
        if len(maps) > 3:
            shown += f", +{len(maps)-3} more"
        return ["Appears in: " + shown]

    def selected_enemy_view_target(self) -> Optional[Unit]:
        targets = self.sorted_enemy_view_targets()
        if not targets:
            return None
        self.enemy_view_index %= len(targets)
        return targets[self.enemy_view_index]

    def bestiary_selected_enemy(self) -> Optional[Unit]:
        roster = self.enemy_roster_names()
        if not roster:
            return None
        self.bestiary_enemy_index %= len(roster)
        return self.enemy_by_name(roster[self.bestiary_enemy_index])

    def enemy_inspection_lines(self, enemy: Unit, include_live: bool = True) -> List[str]:
        base = self.enemy_base_name(enemy.name)
        lines: List[str] = []
        label = enemy.name
        if enemy.elite and not label.startswith("Elite "):
            label = "Elite " + label
        lines.append(f"{label} [{enemy.role or 'enemy'}] threat {self.enemy_threat_value(enemy.name)}")
        lines.append(self.role_description(enemy.role))
        if include_live:
            lines.append(f"HP {enemy.hp}/{enemy.max_hp}  AP {enemy.action_points}  MV {enemy.move_range}  Pos {enemy.pos}")
            lines.append(self.enemy_status_detail(enemy))
            if enemy.active and enemy.alive:
                lines.append("Intent: " + self.ui_enemy_intent_summary(enemy))
                lines.extend(self.enemy_live_threat_lines(enemy))
        else:
            lines.append(f"Base HP {enemy.max_hp}  MV {enemy.move_range}  Threat {self.enemy_threat_value(base)}")
            lines.extend(self.enemy_map_appearance_lines(base))
        lines.append(f"Weapon: {enemy.weapon.name} {enemy.weapon.damage}d R{enemy.weapon.range_min}-{enemy.weapon.range_max}")
        for sig in self.enemy_signature_lines_for_name(enemy.name):
            lines.append(sig)
        for note in self.enemy_counterplay_lines_for_name(enemy.name):
            lines.append("Counter: " + note)
        return lines

    def start_enemy_view(self) -> None:
        targets = self.sorted_enemy_view_targets()
        if not targets:
            self.push("No enemies to inspect.")
            return
        self.enemy_view_index %= len(targets)
        selected = targets[self.enemy_view_index]
        self.cursor = selected.pos
        self.state = "enemy_view"
        self.record_tutorial_event("enemy_view")
        self.push("Enemy View opened. Up/Down chooses enemy; Z/Enter focuses cursor.")

    def enemy_intent_lines(self) -> List[str]:
        """Show likely enemy plans, including multi-AP move -> act sequences."""
        intents: List[str] = []
        for enemy in self.enemies_alive():
            summary = self.ui_enemy_intent_summary(enemy)
            intents.append(f"{enemy.name}: {summary}")
        return intents[:4]

    def make_compact_panel(self) -> List[str]:
        hero = self.selected_hero
        inner = PANEL_W - 2
        lines: List[str] = []
        lines.append(c("┌" + "─" * inner + "┐", Style.BRIGHT_BLACK))
        lines.append(self.line_box(c(self.state_label(), Style.BOLD, Style.BRIGHT_YELLOW)))
        lines.append(self.line_box(c(hero.name, Style.BOLD, Style.BRIGHT_CYAN) + f" HP {hero.hp}/{hero.max_hp} MP {hero.mp}/{hero.max_mp} AP {hero.action_points} [{self.status_badges(hero)}]"))

        if self.state == "command":
            for i, label in enumerate(self.command_menu_options()):
                enabled = self.action_enabled(label)
                lines.append(self.line_box(self.menu_line(label, i, "", enabled)))
        elif self.state == "skill_group_menu":
            for i, label in enumerate(self.SKILL_GROUP_MENU):
                enabled = self.action_enabled(label)
                detail = {"Cast Skill": "list", "Overwatch": "watch", "Guard": "defend"}.get(label, "")
                lines.append(self.line_box(self.sub_line(f"{label} {detail}", self.skill_group_index == i, enabled)))
        elif self.state == "party_group_menu":
            details = {
                "Hero": f"{len(self.controllable_heroes_alive())} manual",
                "Tactics": self.follower_tactic,
                "Control": f"{len(self.active_manual_companion_names())} manual",
            }
            for i, label in enumerate(self.PARTY_GROUP_MENU):
                lines.append(self.line_box(self.sub_line(f"{label} {details[label]}", self.party_group_index == i, True)))
        elif self.state == "enemy_view":
            enemy = self.selected_enemy_view_target()
            lines.append(self.line_box(c(f"Enemy View {self.current_enemy_view_sort()}", Style.BOLD, Style.BRIGHT_RED)))
            if enemy:
                lines.append(self.line_box(f"{enemy.name} {enemy.hp}/{enemy.max_hp}"))
                lines.append(self.line_box(enemy.role + " | " + self.role_description(enemy.role)[:16]))
                lines.append(self.line_box("Intent: " + clip(self.ui_enemy_intent_summary(enemy), 18)))
                lines.append(self.line_box("S sort | Z/Enter focus"))
        elif self.state == "skill_menu":
            for i, s in enumerate(self.available_skills(hero)):
                enabled = hero.mp >= s.mp_cost and hero.action_points > 0
                shape = s.shape if s.shape != "multishot" else f"{s.shots}shot"
                rider = self.status_rider_label(s)
                rank = self.skill_rank_label(hero, s.name)
                lines.append(self.line_box(self.sub_line(f"{s.name} {rank} {s.mp_cost}MP {self.skill_power_label(s)}{rider} {shape[:6]}", self.skill_index == i, enabled)))
        elif self.state == "overwatch_menu":
            for i, opt in enumerate(self.overwatch_options(hero)):
                enabled = self.overwatch_option_enabled(opt, hero)
                lines.append(self.line_box(self.sub_line(f"{opt['label']} {opt['detail']}", self.overwatch_menu_index == i, enabled)))
        elif self.state == "support_target_menu":
            skill = self.selected_skill(hero)
            for i, ally in enumerate(self.support_targets_for_skill(hero, skill)):
                invalid = self.skill_target_validity_message(hero, ally, skill)
                detail = f"HP {ally.hp}/{ally.max_hp} AP {ally.action_points}"
                lines.append(self.line_box(self.sub_line(f"{ally.name} {detail}", self.support_target_index == i, invalid is None)))
        elif self.state == "control_menu":
            for i, h in enumerate(self.heroes):
                if self.is_required_leader(h):
                    label = f"{h.name} Manual leader"
                    enabled = False
                else:
                    label = f"{h.name} {self.companion_control_label(h)}"
                    enabled = h.active
                lines.append(self.line_box(self.sub_line(label, self.control_menu_index == i, enabled)))
        elif self.state == "tactics_menu":
            tactics = ["Balanced", "Aggressive", "Cautious", "Support"]
            for i, name in enumerate(tactics):
                lines.append(self.line_box(self.sub_line(name, self.tactics_index == i, True)))
        elif self.state == "map_menu":
            for i, (name, _map, _pos) in enumerate(self.maps):
                suffix = "*" if i == self.map_index else " "
                lines.append(self.line_box(self.sub_line(f"{suffix} {name}", self.map_menu_index == i, True)))
        elif self.state in ("target_move", "target_attack", "target_skill", "target_item", "target_overwatch", "inspect"):
            for line in self.preview_lines()[:5]:
                lines.append(self.line_box(clip(line, inner)))
            lines.append(self.line_box("Z/Enter confirm | X/Esc/C back"))
        elif self.state == "item_menu":
            entries, hidden_above, hidden_below = self.item_menu_window(hero, max_entries=4)
            if hidden_above:
                lines.append(self.line_box(f"^ {hidden_above} more item(s)"))
            for i, item in entries:
                count = hero.inventory.get(item.name, 0)
                label = f"{item.name} x{count} {self.item_power_label(item)}"
                lines.append(self.line_box(self.sub_line(label, self.item_index == i, True)))
            if hidden_below:
                lines.append(self.line_box(f"v {hidden_below} more item(s)"))
        elif self.state == "item_target_menu":
            item = self.selected_item()
            for i, ally in enumerate(self.item_ally_targets(hero, item)):
                invalid = self.item_target_validity_message(hero, item, target=ally)
                detail = f"HP {ally.hp}/{ally.max_hp} MP {ally.mp}/{ally.max_mp}"
                lines.append(self.line_box(self.sub_line(f"{ally.name} {detail}", self.item_target_index == i, invalid is None)))
        elif self.state == "hero_menu":
            for i, h in enumerate(self.heroes):
                role = "Reserve" if not h.active else ("AI" if h.ai_controlled else "Player")
                enabled = h.active and h.alive and not h.ai_controlled
                hp_text = f"{h.hp}/{h.max_hp}" if h.active else "not deployed"
                lines.append(self.line_box(self.sub_line(f"{h.name} {role} {hp_text}", self.hero_menu_index == i, enabled)))

        lines.append(c("└" + "─" * inner + "┘", Style.BRIGHT_BLACK))
        return lines

    def make_panel(self) -> List[str]:
        hero = self.selected_hero
        skill = self.selected_skill(hero)
        inner = PANEL_W - 2
        lines: List[str] = []

        lines.append(c("┌" + "─" * inner + "┐", Style.BRIGHT_BLACK))
        title = f"{self.state_label()}"
        lines.append(self.line_box(c(title, Style.BOLD, Style.BRIGHT_YELLOW)))
        lines.append(self.panel_rule())

        hp_style = Style.BRIGHT_GREEN if hero.hp > hero.max_hp * 0.4 else Style.BRIGHT_RED
        hp = c(self.bar(hero.hp, hero.max_hp, 10), hp_style)
        mp = c(self.bar(hero.mp, hero.max_mp, 10), Style.BRIGHT_BLUE)
        role_text = "Player" if not hero.ai_controlled else "AI"
        lines.append(self.section_header("Active Unit", Style.BRIGHT_CYAN))
        class_line = f"{self.hero_class(hero)} / {self.hero_subclass(hero)}"
        lines.append(self.line_box(c(hero.name, Style.BOLD, Style.BRIGHT_CYAN) + f"  {role_text}  Lv{hero.level}  {clip(class_line, 16)}"))
        lines.append(self.line_box(f"AP {hero.action_points}   {self.build_synergy_rating(self.hero_class(hero), self.hero_subclass(hero))} build"))
        lines.append(self.line_box(f"HP {hp} {hero.hp:>2}/{hero.max_hp:<2}"))
        lines.append(self.line_box(f"MP {mp} {hero.mp:>2}/{hero.max_mp:<2}"))
        lines.append(self.line_box(f"Weapon: {clip(hero.weapon.name, 20)}"))
        lines.append(self.line_box(clip(self.weapon_profile_label(hero.weapon), inner)))
        hero_status = self.status_badges(hero)
        if hero_status != "OK":
            lines.append(self.line_box(c("Status: " + hero_status, Style.BRIGHT_YELLOW)))
        lines.append(self.line_box(c(f"Grade: {self.performance_grade()}  Map: {clip(self.map_name, 16)}", Style.BRIGHT_WHITE)))
        if self.tutorial_active:
            lines.append(self.panel_rule())
            lines.append(self.section_header("Tutorial", Style.BRIGHT_GREEN))
            for line in self.tutorial_current_hint_lines():
                lines.append(self.line_box(clip(line, inner)))
            for line in self.tutorial_progress_lines(limit=5):
                lines.append(self.line_box(clip(line, inner)))
        lines.append(self.panel_rule())
        if self.clean_ui:
            lines.append(self.section_header("Party", Style.BRIGHT_CYAN))
            for ally in [u for u in self.heroes if u.active][:4]:
                lines.append(self.line_box(self.compact_unit_line(ally, ally is hero)))
        else:
            lines.append(self.section_header("Party", Style.BRIGHT_CYAN))
            for ally in self.heroes:
                if not ally.active:
                    continue
                marker = "*" if ally is hero else " "
                mode = "M" if not ally.ai_controlled else "AI"
                status = self.status_text(ally)
                line = f"{marker}{ally.name:<5} {mode:<2} HP {ally.hp:>2}/{ally.max_hp:<2} AP {ally.action_points}"
                if status:
                    line += " " + status
                lines.append(self.line_box(clip(line, inner)))

        lines.append(self.panel_rule())
        lines.append(self.section_header("Situation", Style.BRIGHT_WHITE))
        lines.append(self.line_box(clip(self.cursor_context_line(inner), inner)))
        lines.append(self.line_box(clip(self.battlefield_pressure_line(inner), inner)))
        encounter_briefing = str(self.battle_return_context.get("encounter_briefing", "") or "")
        if encounter_briefing:
            lines.append(self.line_box(clip(encounter_briefing, inner)))
        if self.state == "command":
            lines.append(self.line_box(c("Tip: ", Style.BOLD) + clip(self.action_recommendation(hero), inner - 5)))
        else:
            lines.append(self.line_box(clip(self.combat_legend_line(), inner)))
        lines.append(self.panel_rule())

        if self.state == "command":
            lines.append(self.section_header("Commands", Style.BRIGHT_WHITE))
            details = {
                "Inspect": "look",
                "Enemy View": f"{len(self.enemy_view_targets())} foes",
                "Move": f"MV {hero.move_range}",
                "Attack": f"{hero.weapon.shape}/{hero.weapon.damage_type}",
                "Skills": f"{len(self.available_skills(hero))} skills",
                "Item": f"{sum(hero.inventory.values())} items",
                "Party": "hero/tactics",
                "Map": self.map_name[:12],
                "End Turn": "finish turn",
            }

            for i, label in enumerate(self.command_menu_options()):
                enabled = self.action_enabled(label)
                lines.append(self.line_box(self.menu_line(label, i, details[label], enabled)))

        elif self.state == "skill_group_menu":
            lines.append(self.section_header("Skills", Style.BRIGHT_MAGENTA))
            details = {
                "Cast Skill": f"{len(self.available_skills(hero))} known",
                "Overwatch": f"{len(self.overwatch_options(hero))} options",
                "Guard": "half damage",
            }
            for i, label in enumerate(self.SKILL_GROUP_MENU):
                enabled = self.action_enabled(label)
                lines.append(self.line_box(self.sub_line(f"{label:<12} {details[label]}", self.skill_group_index == i, enabled)))
            lines.append(self.line_box(""))
            lines.append(self.line_box("Skill list, prepared attacks, and defense."))

        elif self.state == "party_group_menu":
            lines.append(self.section_header("Party", Style.BRIGHT_CYAN))
            details = {
                "Hero": f"{len(self.controllable_heroes_alive())} manual",
                "Tactics": self.follower_tactic,
                "Control": f"{len(self.active_manual_companion_names())} manual",
            }
            for i, label in enumerate(self.PARTY_GROUP_MENU):
                lines.append(self.line_box(self.sub_line(f"{label:<8} {details[label]}", self.party_group_index == i, True)))
            lines.append(self.line_box(""))
            lines.append(self.line_box("Companion selection and AI behavior."))

        elif self.state == "control_menu":
            lines.append(self.section_header("Companion Control", Style.BRIGHT_CYAN))
            lines.extend(self.line_boxes("Choose which companions are Manual or AI. Manual units join your party-turn queue. AI units act during follower phase.", limit=3))
            lines.append(self.line_box(""))
            for i, h in enumerate(self.heroes):
                if self.is_required_leader(h):
                    status = "Manual leader"
                    enabled = False
                elif not h.active:
                    status = self.companion_control_label(h)
                    enabled = False
                else:
                    status = self.companion_control_label(h)
                    enabled = True
                lines.append(self.line_box(self.sub_line(f"{h.name:<6} {status}", self.control_menu_index == i, enabled)))
            lines.append(self.line_box(""))
            lines.append(self.line_box("Enter toggles selected active companion."))

        elif self.state == "inspect":
            lines.append(self.section_header("Inspect Map", Style.BRIGHT_CYAN))
            inspected = self.unit_at(self.cursor)
            if inspected:
                lines.append(self.line_box(f"{inspected.name} [{inspected.team}]"))
                lines.append(self.line_box(f"HP {inspected.hp}/{inspected.max_hp}  AP {inspected.action_points}"))
                lines.append(self.line_box(f"Weapon: {clip(inspected.weapon.name, 18)}"))
                status = self.status_text(inspected)
                lines.append(self.line_box(status if status else "No status effects"))
            else:
                lines.append(self.line_box(self.terrain_description(self.cursor)))
                lines.append(self.line_box("Move cursor to examine."))
                lines.append(self.line_box("X/Esc/C returns to commands."))

        elif self.state == "enemy_view":
            lines.append(self.section_header(f"Enemy View [{self.current_enemy_view_sort()}]", Style.BRIGHT_RED))
            targets = self.sorted_enemy_view_targets()
            if not targets:
                lines.append(self.line_box("No enemies."))
            else:
                enemy = self.selected_enemy_view_target()
                for i, foe in enumerate(targets[:8]):
                    selected = (foe is enemy)
                    hp = f"{foe.hp}/{foe.max_hp}" if foe.alive else "DOWN"
                    intent = self.ui_enemy_intent_summary(foe) if foe.alive else "down"
                    danger = "!" if self.ui_enemy_intent_priority(foe) >= 70 else " "
                    detail = f"{danger}{foe.name:<14} {foe.role[:6]:<6} HP {hp:<7} {intent[:10]}"
                    lines.append(self.line_box(self.sub_line(detail, selected, foe.alive)))
                if len(targets) > 8:
                    lines.append(self.line_box(f"+{len(targets)-8} more"))
                lines.append(self.panel_rule())
                if enemy:
                    for detail in self.enemy_inspection_lines(enemy)[:10]:
                        lines.append(self.line_box(clip(detail, inner)))
                    lines.append(self.line_box("S: sort   Z/Enter: focus   X/Esc/C: commands."))

        elif self.state == "target_move":
            lines.append(self.section_header("Move Target", Style.BRIGHT_GREEN))
            valid = self.cursor in self.reachable_tiles(hero)
            path = self.find_path(hero, self.cursor)
            if hero.rooted > 0:
                lines.append(self.line_box(c("Rooted: confirm to break free.", Style.BRIGHT_YELLOW)))
            else:
                lines.append(self.line_box("Choose a destination tile."))
            move_cost = self.path_cost(path) if path else 0
            lines.append(self.line_box(("Valid" if valid else "Invalid") + f" | Cost {move_cost}"))
            lines.append(self.line_box("Z/Enter: move   X/Esc/C: cancel"))

        elif self.state == "target_attack":
            weapon = hero.weapon
            targets = self.weapon_targets(hero, self.cursor, weapon)
            barrels = self.weapon_barrel_tiles(hero, self.cursor, weapon)
            lines.append(self.section_header("Attack Target", Style.BRIGHT_YELLOW))
            lines.extend(self.line_boxes(f"{weapon.name}: {self.weapon_profile_label(weapon)}", limit=3))
            if targets:
                lines.append(self.line_box("Affects: " + clip(", ".join(t.name for t in targets), inner - 9)))
                for target in targets[:3]:
                    dmg = self.weapon_damage_against(hero, target, weapon)
                    rider = f" +{weapon.status}" if weapon.status else ""
                    kill = " KO" if target.hp <= dmg else ""
                    lines.append(self.line_box(f"{target.name:<13} {dmg}d{rider:<12} -> {max(0, target.hp-dmg):>2} HP{kill}"))
                if len(targets) > 3:
                    lines.append(self.line_box(f"+{len(targets)-3} more targets"))
            elif barrels:
                lines.append(self.line_box(f"Explosive barrels hit: {len(barrels)}"))
            else:
                objective_hits = [p for p in self.objective_object_tiles if p in self.weapon_affected_tiles(hero.pos, self.cursor, weapon) and self.tile_at(p) == TILE_CRATE]
                if objective_hits:
                    lines.append(self.line_box(f"Objective crates hit: {len(objective_hits)}"))
                else:
                    in_range = self.cursor in self.weapon_area(hero.pos, weapon)
                    lines.append(self.line_box(c("No enemy in pattern." if in_range else "Cursor out of weapon range.", Style.BRIGHT_YELLOW)))
                lines.append(self.line_box("Z/Enter: attack   X/Esc/C: cancel"))

        elif self.state == "skill_menu":
            lines.append(self.section_header("Skills", Style.BRIGHT_MAGENTA))
            for i, s in enumerate(self.available_skills(hero)):
                enabled = hero.mp >= s.mp_cost and hero.action_points > 0
                shape = s.shape if s.shape != "multishot" else f"{s.shots}shot"
                rider = self.status_rider_label(s)
                rank = self.skill_rank_label(hero, s.name)
                label = f"{s.name:<13} {rank:<4} {s.mp_cost}MP {self.skill_power_label(s)}{rider} {shape[:6]}"
                lines.append(self.line_box(self.sub_line(label, self.skill_index == i, enabled)))
            lines.append(self.line_box(""))
            lines.extend(self.line_boxes(self.skill_shape_label(skill), limit=2))
            lines.extend(self.line_boxes(skill.description, limit=5))

        elif self.state == "target_skill":
            skill = self.selected_skill(hero)
            affected = [e.name for e in self.skill_targets(hero, self.cursor, skill)]
            lines.append(self.section_header(skill.name, Style.BRIGHT_MAGENTA))
            shape = skill.shape if skill.shape != "multishot" else f"{skill.shots}-shot"
            rider = self.status_rider_label(skill)
            rank = self.skill_rank_label(hero, skill.name)
            lines.append(self.line_box(f"{rank} | Cost {skill.mp_cost}MP | {self.skill_power_label(skill)}{rider} | R{skill.range_max} | {shape}"))
            lines.extend(self.line_boxes(skill.description, limit=4))
            verb = "Targets" if skill.target_team == "ally" else "Hits"
            lines.append(self.line_box(f"{verb}: " + (", ".join(affected) if affected else "none")))
            lines.append(self.line_box("Z/Enter: cast   X/Esc/C: cancel"))

        elif self.state == "support_target_menu":
            skill = self.selected_skill(hero)
            lines.append(self.section_header(f"{skill.name}: Choose Ally", Style.BRIGHT_MAGENTA))
            targets = self.support_targets_for_skill(hero, skill)
            if not targets:
                lines.append(self.line_box("No valid allies."))
            for i, ally in enumerate(targets):
                invalid = self.skill_target_validity_message(hero, ally, skill)
                if skill.effect == "heal":
                    detail = f"HP {ally.hp}/{ally.max_hp}"
                elif skill.effect == "transfer_ap":
                    detail = f"gets +{hero.action_points} AP"
                else:
                    detail = f"AP {ally.action_points}"
                lines.append(self.line_box(self.sub_line(f"{ally.name:<8} {detail}", self.support_target_index == i, invalid is None)))
                lines.append(self.line_box("Z/Enter: use   X/Esc/C: cancel"))

        elif self.state == "item_menu":
            lines.append(self.section_header("Items", Style.BRIGHT_GREEN))
            entries, hidden_above, hidden_below = self.item_menu_window(hero, max_entries=8)
            if hidden_above:
                lines.append(self.line_box(f"^ {hidden_above} more owned item(s)"))
            for i, item in entries:
                count = hero.inventory.get(item.name, 0)
                label = f"{item.name:<14} x{count} {self.item_power_label(item)}"
                lines.append(self.line_box(self.sub_line(label, self.item_index == i, True)))
            if hidden_below:
                lines.append(self.line_box(f"v {hidden_below} more owned item(s)"))
            item = self.selected_item()
            lines.append(self.line_box(""))
            lines.extend(self.line_boxes(f"{item.name}: {self.item_power_label(item)}", limit=2))
            lines.extend(self.line_boxes(item.description, limit=4))
            lines.append(self.line_box("Z/Enter: select   X/Esc/C: cancel"))

        elif self.state == "item_target_menu":
            item = self.selected_item()
            lines.append(self.section_header(f"{item.name}: Choose Ally", Style.BRIGHT_GREEN))
            lines.extend(self.line_boxes(item.description, limit=3))
            targets = self.item_ally_targets(hero, item)
            if not targets:
                lines.append(self.line_box("No valid allies."))
            for i, ally in enumerate(targets):
                invalid = self.item_target_validity_message(hero, item, target=ally)
                if item.effect == "heal":
                    detail = f"HP {ally.hp}/{ally.max_hp}"
                elif item.effect == "mp":
                    detail = f"MP {ally.mp}/{ally.max_mp}"
                elif item.effect == "cleanse":
                    detail = self.status_text(ally) or "No status"
                elif item.effect == "guard":
                    detail = "Guard" if ally.guard else "No guard"
                else:
                    detail = f"AP {ally.action_points}"
                lines.append(self.line_box(self.sub_line(f"{ally.name:<8} {detail}", self.item_target_index == i, invalid is None)))
                lines.append(self.line_box("Z/Enter: use   X/Esc/C: cancel"))

        elif self.state == "target_item":
            item = self.selected_item()
            targets = [e.name for e in self.item_enemy_targets(hero, item, self.cursor)]
            lines.append(self.section_header(f"Throw: {item.name}", Style.BRIGHT_GREEN))
            lines.append(self.line_box(f"{self.item_power_label(item)} | R{item.range_max}"))
            lines.append(self.line_box("Hits: " + (", ".join(targets) if targets else "none")))
            lines.append(self.line_box("Z/Enter: throw   X/Esc/C: cancel"))

        elif self.state == "overwatch_menu":
            lines.append(self.section_header("Overwatch", Style.BRIGHT_CYAN))
            options = self.overwatch_options(hero)
            for i, opt in enumerate(options):
                enabled = self.overwatch_option_enabled(opt, hero)
                label = f"{opt['label']:<14} {opt['detail']}"
                lines.append(self.line_box(self.sub_line(label, self.overwatch_menu_index == i, enabled)))
            lines.append(self.line_box("AP now; MP only if triggered."))

        elif self.state == "target_overwatch":
            option = self.pending_overwatch_option or self.selected_overwatch_option()
            targets = self.overwatch_target_names_for_option(hero, option, self.cursor)
            tiles = self.overwatch_tiles_for_option(hero, option, self.cursor)
            lines.append(self.section_header(f"Overwatch: {option.get('label', '?')}", Style.BRIGHT_CYAN))
            lines.append(self.line_box(f"Watched tiles: {len(tiles)} | Uses: 1"))
            lines.append(self.line_box("Triggers when enemy enters."))
            lines.append(self.line_box("Now in area: " + (", ".join(targets) if targets else "none")))
            lines.append(self.line_box("Z/Enter: set   X/Esc/C: cancel"))

        elif self.state == "tactics_menu":
            lines.append(self.section_header("Follower Tactics", Style.BRIGHT_MAGENTA))
            tactics = ["Balanced", "Aggressive", "Cautious", "Support"]
            for i, name in enumerate(tactics):
                lines.append(self.line_box(self.sub_line(name, self.tactics_index == i, True)))
            lines.append(self.line_box(""))
            if self.manual_teammates:
                lines.append(self.line_box("Inactive while manual control is ON."))
            else:
                lines.append(self.line_box(clip(self.tactic_description(), inner)))

        elif self.state == "hero_menu":
            lines.append(self.section_header("Party", Style.BRIGHT_CYAN))
            for i, h in enumerate(self.heroes):
                if not h.active:
                    status = "Reserve"
                    enabled = False
                else:
                    role = "AI" if h.ai_controlled else "Player"
                    status = "DOWN" if not h.alive else f"{role} HP {h.hp}/{h.max_hp} AP {h.action_points}"
                    enabled = h.alive and not h.ai_controlled
                lines.append(self.line_box(self.sub_line(f"{h.name} {status}", self.hero_menu_index == i, enabled)))
            lines.append(self.line_box("Main Menu Party changes active roster."))

        elif self.state == "map_menu":
            lines.append(self.section_header("Arenas", Style.BRIGHT_GREEN))
            for i, (name, _map, _pos) in enumerate(self.maps):
                suffix = "current" if i == self.map_index else "select"
                lines.append(self.line_box(self.sub_line(f"{name:<17} {suffix}", self.map_menu_index == i, True)))
            lines.append(self.line_box(""))
            lines.append(self.line_box("Enter resets on selected arena."))

        preview = self.preview_lines()
        if preview:
            lines.append(self.panel_rule())
            lines.append(self.section_header("Tactical Preview", Style.BRIGHT_WHITE))
            used_preview = 0
            for line in preview:
                for boxed in self.line_boxes(line, limit=2):
                    lines.append(boxed)
                    used_preview += 1
                    if used_preview >= (5 if self.clean_ui else 7):
                        break
                if used_preview >= (5 if self.clean_ui else 7):
                    break

        if self.state == "command":
            intents = self.enemy_intent_lines()
            if intents:
                lines.append(self.panel_rule())
                lines.append(self.section_header("Enemy Intent", Style.BRIGHT_RED))
                for line in intents[: (2 if self.clean_ui else len(intents))]:
                    lines.append(self.line_box(clip(line, inner)))

        lines.append(self.panel_rule())
        if self.clean_ui:
            lines.append(self.line_box(c("Controls: ", Style.BOLD) + clip(self.clean_controls_line(), inner - 10)))
        else:
            lines.append(self.section_header("Controls", Style.BRIGHT_WHITE))
            if self.state in ("target_move", "target_attack", "target_skill", "target_item", "target_overwatch"):
                lines.append(self.line_box("WASD/arrows: move cursor"))
                lines.append(self.line_box("Enter/Space: confirm target"))
            else:
                lines.append(self.line_box("WASD/arrows: navigate menu"))
                lines.append(self.line_box("Enter/Space: confirm"))
            lines.append(self.line_box("X/Esc/C: back    H: help"))
        lines.append(c("└" + "─" * inner + "┘", Style.BRIGHT_BLACK))
        return lines

    def enemy_summary(self, enemy: Unit) -> str:
        if not enemy.alive:
            return f"{enemy.glyph}:{enemy.name} down"
        role = enemy.role[:4] if enemy.role else "mob"
        status = self.status_text(enemy)
        cd = ",".join(f"{k}:{v}" for k, v in enemy.cooldowns.items() if v > 0)
        extra = ""
        if status:
            extra += f" {status}"
        if cd:
            extra += f" CD[{cd}]"
        return clip(f"{enemy.glyph}:{enemy.name} {role} {enemy.hp}/{enemy.max_hp}{extra}", 32)

    def bottom_hint(self) -> str:
        if self.state == "command":
            return f"Commands: Z/Enter select | Tab heroes | Y enemy view | L combat status | U UI {self.ui_status_label()} | H help | Q quit"
        if self.state == "combat_log":
            return "Combat Status: Tab/V event log | X/Esc/C/L/Z/Enter close"
        if self.state == "inspect":
            return "Inspect: WASD/Arrows move cursor   X/Esc/C returns to command menu"
        if self.state == "enemy_view":
            return f"Enemy View: Up/Down enemy   S sort {self.current_enemy_view_sort()}   Z/Enter focus   X/Esc/C command"
        if self.state == "skill_group_menu":
            return "Skills: Cast Skill / Overwatch / Guard   Z/Enter: select   X/Esc/C: command menu"
        if self.state == "skill_menu":
            return "WASD/Arrows: choose skill   Z/Enter: select skill   X/Esc/C: Skills menu"
        if self.state == "overwatch_menu":
            return "Choose weapon/area skill for Overwatch   Z/Enter: select   X/Esc/C: Skills menu"
        if self.state == "support_target_menu":
            return "Choose ally for support skill   Z/Enter: use   X/Esc/C: skill menu"
        if self.state == "item_menu":
            return "Choose item   Z/Enter: select   X/Esc/C: command menu"
        if self.state == "item_target_menu":
            return "Choose ally for item   Z/Enter: use   X/Esc/C: item menu"
        if self.state == "target_item":
            return "Choose target tile for thrown item   Z/Enter: throw   X/Esc/C: item menu"
        if self.state == "party_group_menu":
            return "Party: Hero / Tactics / Control   Z/Enter: select   X/Esc/C: command menu"
        if self.state == "control_menu":
            return "Control: choose companion   Z/Enter: toggle Manual/AI   X/Esc/C: Party menu"
        if self.state == "tactics_menu":
            return "Choose companion AI style   Z/Enter: apply   X/Esc/C: Party menu"
        if self.state == "hero_menu":
            return "Hero menu: select manual heroes; use Control to toggle companions   X/Esc/C: Party menu"
        if self.state == "map_menu":
            return "Choose arena   Z/Enter: load/reset battle   X/Esc/C: command menu"
        return "WASD/Arrows: move cursor   ? enemy path   ! likely enemy threat   Z/Enter: confirm   X/Esc/C: cancel"

    def use_compact_layout(self, terminal_height: int, side_by_side: bool) -> bool:
        if FORCE_ROOMY:
            return False
        if FORCE_COMPACT:
            return True
        # Side-by-side is usually around 40+ lines in roomy mode.
        # Stacked is taller, so it needs compact mode sooner.
        return terminal_height < (36 if side_by_side else 44)

    def compact_panel_limit(self, terminal_height: int, side_by_side: bool) -> int:
        if side_by_side:
            return max(18, terminal_height - 3)
        # In stacked mode the panel appears below the map, so keep it short.
        return max(10, terminal_height - (self.map_height_tiles() + 12))

    def trim_panel_for_height(self, panel: List[str], limit: int) -> List[str]:
        if len(panel) <= limit:
            return panel
        if limit <= 6:
            return panel[:limit]
        return panel[: max(0, limit - 2)] + [
            c("│" + "…" * (PANEL_W - 2) + "│", Style.BRIGHT_BLACK),
            c("└" + "─" * (PANEL_W - 2) + "┘", Style.BRIGHT_BLACK),
        ]

    def render(self) -> None:
        if self.state == "combat_log":
            self.render_combat_log()
            return
        hero = self.selected_hero
        reachable: Set[Pos] = set()
        path: Set[Pos] = set()
        attack: Set[Pos] = set()
        skill_r: Set[Pos] = set()
        aoe: Set[Pos] = set()
        overwatch_tiles: Set[Pos] = self.active_overwatch_tiles()
        overwatch_hit_positions: Set[Pos] = {e.pos for e in self.enemies_alive() if e.pos in overwatch_tiles}
        skill_hit_positions: Set[Pos] = set()
        item_aoe: Set[Pos] = set()
        item_hit_positions: Set[Pos] = set()
        enemy_path: Set[Pos] = set()

        terminal_size = shutil.get_terminal_size(fallback=(100, 30))
        terminal_width = terminal_size.columns
        terminal_height = terminal_size.lines

        map_width = self.map_width_tiles() * CELL_W
        panel_width = PANEL_W
        side_by_side_width = map_width + 4 + panel_width
        side_by_side = terminal_width >= side_by_side_width
        compact = self.use_compact_layout(terminal_height, side_by_side)

        # Player-facing preview shows likely enemy intent, not every possible
        # movement+attack tile. The broader enemy_danger_tiles() remains for AI.
        show_danger = self.state == "target_move" or (self.state == "command" and self.current_menu_option() == "Move")
        if show_danger:
            enemy_path, danger = self.enemy_intent_preview_tiles()
        else:
            danger = set()

        if self.turn == "hero" and hero.action_points > 0:
            if self.state == "target_move":
                reachable = set(self.reachable_tiles(hero))
                path = set(self.find_path(hero, self.cursor)[1:])
            elif self.state == "target_attack":
                attack = self.weapon_area(hero.pos, hero.weapon)
                if self.cursor in attack:
                    aoe = self.weapon_affected_tiles(hero.pos, self.cursor, hero.weapon)
                    skill_hit_positions = {enemy.pos for enemy in self.weapon_targets(hero, self.cursor, hero.weapon)}
            elif self.state == "target_skill":
                skill = self.selected_skill(hero)
                skill_r = self.skill_range(hero.pos, skill)
                if self.cursor in skill_r:
                    aoe = self.skill_affected_tiles(hero.pos, self.cursor, skill)
                    skill_hit_positions = {enemy.pos for enemy in self.skill_targets(hero, self.cursor, skill)}
            elif self.state == "target_item":
                item = self.selected_item()
                item_aoe = self.item_affected_tiles(hero, item, self.cursor)
                item_hit_positions = {enemy.pos for enemy in self.item_enemy_targets(hero, item, self.cursor)}
            elif self.state == "target_overwatch":
                option = self.pending_overwatch_option or self.selected_overwatch_option()
                prospective = self.overwatch_tiles_for_option(hero, option, self.cursor)
                overwatch_tiles |= prospective
                overwatch_hit_positions |= {e.pos for e in self.enemies_alive() if e.pos in prospective}

        map_lines: List[str] = []
        title = "ASCII Tactical Combat Prototype v113"
        if compact:
            title = "Combat Prototype v113"
        map_lines.append(c(title, Style.BOLD, Style.BRIGHT_WHITE))

        turn_color = Style.BRIGHT_CYAN if self.turn == "hero" else Style.BRIGHT_RED
        state_line = f"{self.map_name} | R{self.round_no} | {c(self.turn.upper(), Style.BOLD, turn_color)} | {c(self.state_label(), Style.BOLD, Style.BRIGHT_YELLOW)}"
        map_lines.append(state_line)

        if not compact:
            map_lines.append(clip("Party: " + self.active_party_summary(map_width - 7), map_width))
            map_lines.append(clip(self.objective_text(), map_width))
            map_lines.append(clip(self.combat_legend_line(), map_width))

        map_lines.append(c("─" * map_width, Style.BRIGHT_BLACK))

        for y in range(self.map_height_tiles()):
            row = "".join(self.cell((x, y), reachable, path, danger, attack, skill_r, aoe | item_aoe, overwatch_tiles, overwatch_hit_positions, skill_hit_positions | item_hit_positions, enemy_path) for x in range(self.map_width_tiles()))
            map_lines.append(row)

        map_lines.append(c("─" * map_width, Style.BRIGHT_BLACK))

        if compact:
            inspected = self.unit_at(self.cursor)
            if inspected:
                summary = f"{inspected.name} {inspected.hp}/{inspected.max_hp}"
            else:
                summary = self.terrain_description(self.cursor)
            map_lines.append(clip(f"{self.state_label()} | {summary}", map_width))
        else:
            if self.state == "inspect":
                map_lines.append("Inspect: terrain, cover, units, status")
            elif self.state == "enemy_view":
                map_lines.append("Enemy View: roles, intent, threat, counterplay")
            elif self.state == "target_move":
                map_lines.append("Move: + reachable | * path | ? enemy path | ! likely danger")
            elif self.state == "target_attack":
                map_lines.append("Attack: x weapon range | choose enemy")
            elif self.state == "target_skill":
                map_lines.append("Skill: o range | O area | <e> hit")
            elif self.state == "target_item":
                map_lines.append("Item: O blast | <e> hit")
            elif self.state == "target_overwatch":
                map_lines.append("Overwatch: W watched | !e! covered")
            elif self.overwatch_actions:
                map_lines.append("Active overwatch: W watched | !e! covered")
            else:
                map_lines.append("Menu active: use command panel")
            map_lines.append("")
            map_lines.extend(self.battle_footer_lines(map_width, compact))

        map_lines = [clip_visible(line, map_width) for line in map_lines]

        panel = self.make_panel()
        if compact:
            panel = self.make_compact_panel()
        panel_limit = self.compact_panel_limit(terminal_height, side_by_side) if compact else 10_000
        panel = self.trim_panel_for_height(panel, panel_limit)

        rows: List[str] = []
        if side_by_side:
            height = max(len(map_lines), len(panel))
            for i in range(height):
                left = map_lines[i] if i < len(map_lines) else ""
                right = panel[i] if i < len(panel) else ""
                rows.append(pad(clip_visible(left, map_width), map_width + 4) + clip_visible(right, PANEL_W))
        else:
            rows.extend(map_lines)
            rows.append(c("─" * min(map_width, terminal_width), Style.BRIGHT_BLACK))
            rows.extend(panel)

        hint_width = max(20, min(terminal_width - 2, side_by_side_width))
        hint = clip(self.bottom_hint(), hint_width - 2)
        rows.append(c(" " + hint + " ", Style.BLACK, Style.BG_SELECT, Style.BOLD))

        # Final height guard. Prefer losing low-priority lower lines over making
        # the user scroll. The active map and command panel stay visible first.
        max_rows = max(10, terminal_height - 1)
        if len(rows) > max_rows:
            rows = rows[:max_rows]
            if rows:
                rows[-1] = c(" UI compacted to fit terminal height. Use --roomy or enlarge window. ", Style.BLACK, Style.BG_SELECT, Style.BOLD)

        rows = [clip_visible(row, terminal_width) for row in rows]
        clear_screen()
        sys.stdout.write("\n".join(rows))
        sys.stdout.flush()

    # ----- command starts -----

    def current_menu_option(self) -> str:
        options = self.command_menu_options()
        self.menu_index %= len(options)
        return options[self.menu_index]

    def command_menu_options(self) -> List[str]:
        if self.allow_battle_map_selection:
            return list(self.MAIN_MENU)
        return [label for label in self.MAIN_MENU if label != "Map"]

    def current_skill_group_option(self) -> str:
        return self.SKILL_GROUP_MENU[self.skill_group_index]

    def current_party_group_option(self) -> str:
        return self.PARTY_GROUP_MENU[self.party_group_index]

    def choose_menu_option(self) -> None:
        option = self.current_menu_option()
        if not self.action_enabled(option):
            self.push(f"{option} is unavailable.")
            return
        if option == "Inspect":
            self.start_inspect()
        elif option == "Enemy View":
            self.start_enemy_view()
        elif option == "Move":
            self.start_move()
        elif option == "Attack":
            self.start_attack()
        elif option == "Skills":
            self.start_skill_group_menu()
        elif option == "Item":
            self.start_item()
        elif option == "Party":
            self.start_party_group_menu()
        elif option == "Map":
            self.start_map_menu()
        elif option == "End Turn":
            self.end_turn()

    def choose_skill_group_option(self) -> None:
        option = self.current_skill_group_option()
        if not self.action_enabled(option):
            self.push(f"{option} is unavailable.")
            return
        if option == "Cast Skill":
            self.start_skill()
        elif option == "Overwatch":
            self.start_overwatch()
        elif option == "Guard":
            self.guard_action()

    def choose_party_group_option(self) -> None:
        option = self.current_party_group_option()
        if option == "Hero":
            self.start_hero_menu()
        elif option == "Tactics":
            self.start_tactics_menu()
        elif option == "Control":
            self.start_control_menu()


    def default_attack_cursor(self, hero: Unit) -> Pos:
        targets = [e for e in self.enemies_alive() if e.pos in self.weapon_area(hero.pos, hero.weapon)]
        if targets:
            return min(targets, key=lambda e: e.hp).pos
        return min(self.enemies_alive(), key=lambda e: manhattan(hero.pos, e.pos)).pos if self.enemies_alive() else hero.pos

    def default_skill_cursor(self, hero: Unit, skill: Skill) -> Pos:
        best_center = hero.pos
        best_score = -1
        for center in self.skill_range(hero.pos, skill):
            targets = self.skill_targets(hero, center, skill)
            score = (
                sum(min(skill.damage, e.hp) for e in targets)
                + 20 * sum(1 for e in targets if e.hp <= skill.damage)
                + 5 * len(targets)
            )
            if score > best_score:
                best_score = score
                best_center = center

        # If no enemy is currently targetable, start the cursor on the in-range
        # tile closest to the nearest enemy instead of leaving it on a random tile.
        if best_score <= 0 and self.enemies_alive():
            nearest = min(self.enemies_alive(), key=lambda e: manhattan(hero.pos, e.pos))
            best_center = min(self.skill_range(hero.pos, skill), key=lambda p: manhattan(p, nearest.pos))
        return best_center

    def start_skill_group_menu(self) -> None:
        self.state = "skill_group_menu"
        self.skill_group_index = 0
        self.push("Skills opened: Cast Skill, Overwatch, or Guard.")

    def start_party_group_menu(self) -> None:
        self.state = "party_group_menu"
        self.party_group_index = 0
        self.push("Party opened: Hero, Tactics, or Control.")

    def start_inspect(self) -> None:
        self.state = "inspect"
        self.cursor = self.selected_hero.pos
        self.push("Inspect mode. Move cursor to examine tiles and units.")

    def start_move(self) -> None:
        hero = self.selected_hero
        if hero.action_points <= 0:
            self.push("No AP for movement.")
            return
        self.state = "target_move"
        self.cursor = hero.pos
        self.push("Move selected. Now choose destination on the map.")

    def start_attack(self) -> None:
        hero = self.selected_hero
        if hero.action_points <= 0:
            self.push("No AP for attack.")
            return
        self.state = "target_attack"
        self.cursor = self.default_attack_cursor(hero)
        self.push("Attack selected. Choose enemy target.")

    def start_skill(self) -> None:
        hero = self.selected_hero
        if hero.action_points <= 0:
            self.push("No AP for skill.")
            return
        if not any(hero.mp >= s.mp_cost for s in self.available_skills(hero)):
            self.push("Not enough MP for any skill.")
            return
        self.state = "skill_menu"
        self.skill_index = 0
        self.push(f"Skill submenu opened. {hero.name} knows {len(self.available_skills(hero))} class skills.")

    def confirm_skill_menu(self) -> None:
        hero = self.selected_hero
        skill = self.selected_skill(hero)
        if hero.action_points <= 0:
            self.push("No AP for skill.")
            return
        if hero.mp < skill.mp_cost:
            self.push(f"Not enough MP for {skill.name}.")
            return
        if skill.target_team == "ally":
            targets = self.support_targets_for_skill(hero, skill)
            if not targets:
                self.push("No valid allies for that skill.")
                return
            self.support_target_index = 0
            self.state = "support_target_menu"
            self.push(f"{skill.name} selected. Choose an ally.")
            return
        self.state = "target_skill"
        self.cursor = self.default_skill_cursor(hero, skill)
        self.push(f"{skill.name} selected. Choose target tile.")

    def start_item(self) -> None:
        hero = self.selected_hero
        if hero.action_points <= 0:
            self.push("No AP for item.")
            return
        if not self.usable_items(hero):
            self.push("No usable items.")
            return
        self.state = "item_menu"
        self.item_index = 0
        self.push("Item submenu opened.")

    def start_overwatch(self) -> None:
        hero = self.selected_hero
        self.overwatch_return_state = self.state if self.state in ("skill_group_menu", "command") else "command"
        if hero.action_points <= 0:
            self.push("No AP for overwatch.")
            return
        options = self.overwatch_options(hero)
        if not options:
            self.push("No overwatch options available.")
            return
        self.state = "overwatch_menu"
        self.overwatch_menu_index = 0
        self.pending_overwatch_option = None
        self.push("Overwatch opened. Choose an attack or skill to watch with.")

    def refresh_manual_teammates(self) -> None:
        self.manual_teammates = any(
            h.active and h.alive and h.name in self.manual_companion_names
            for h in self.heroes
            if not self.is_required_leader(h)
        )

    def companion_control_label(self, hero: Unit) -> str:
        if self.is_required_leader(hero):
            return "Manual leader"
        if not hero.active:
            pref = "Manual" if hero.name in self.manual_companion_names else "AI"
            return f"Reserve ({pref} pref)"
        return "Manual" if hero.name in self.manual_companion_names else "AI"

    def apply_companion_control_settings(self) -> None:
        for hero in self.heroes:
            if self.is_required_leader(hero):
                hero.ai_controlled = False
            elif hero.team == "hero":
                hero.ai_controlled = not (hero.active and hero.name in self.manual_companion_names)
        self.refresh_manual_teammates()

        selected = self.heroes[self.selected_hero_idx % len(self.heroes)]
        if not (selected.active and selected.alive and not selected.ai_controlled):
            self.selected_hero_idx = 0
            self.advance_to_next_ready_hero()
        self.cursor = self.selected_hero.pos

    def active_manual_companion_names(self) -> List[str]:
        return [h.name for h in self.heroes if h.active and h.alive and not self.is_required_leader(h) and not h.ai_controlled]

    def active_ai_companion_names(self) -> List[str]:
        return [h.name for h in self.heroes if h.active and h.alive and not self.is_required_leader(h) and h.ai_controlled]

    def toggle_teammate_control(self) -> None:
        active_companions = [h for h in self.heroes if h.active and not self.is_required_leader(h)]
        if not active_companions:
            self.push("No active companions to toggle.")
            return

        all_manual = all(h.name in self.manual_companion_names for h in active_companions)
        if all_manual:
            for hero in active_companions:
                self.manual_companion_names.discard(hero.name)
            mode = "All active companions set to AI."
        else:
            for hero in active_companions:
                self.manual_companion_names.add(hero.name)
            mode = "All active companions set to Manual."

        self.apply_companion_control_settings()
        self.state = "command"
        self.push(mode)

    def start_control_menu(self) -> None:
        self.state = "control_menu"
        self.control_menu_index = 0
        self.push("Control menu opened. Toggle each companion Manual/AI.")

    def confirm_control(self) -> None:
        hero = self.heroes[self.control_menu_index % len(self.heroes)]
        if self.is_required_leader(hero):
            self.push(f"{hero.name} is the required manual leader.")
            return
        if not hero.active:
            self.push(f"{hero.name} is in reserve. Activate from the Main Menu first.")
            return

        if hero.name in self.manual_companion_names:
            self.manual_companion_names.remove(hero.name)
            mode = "AI"
        else:
            self.manual_companion_names.add(hero.name)
            mode = "Manual"

        self.apply_companion_control_settings()
        self.state = "control_menu"
        self.push(f"{hero.name} set to {mode}.")


    def start_tactics_menu(self) -> None:
        self.state = "tactics_menu"
        self.tactics_index = ["Balanced", "Aggressive", "Cautious", "Support"].index(self.follower_tactic)
        self.push("Tactics submenu opened.")

    def start_hero_menu(self) -> None:
        self.state = "hero_menu"
        self.hero_menu_index = self.selected_hero_idx
        self.push("Hero submenu opened.")

    def start_map_menu(self) -> None:
        if not self.allow_battle_map_selection:
            self.push("Map selection is unavailable during this encounter.")
            return
        self.state = "map_menu"
        self.map_menu_index = self.map_index
        self.push("Map submenu opened. Choosing a map resets the battle.")

    # ----- confirmations -----

    def confirm(self) -> None:
        if self.state == "command":
            self.choose_menu_option()
        elif self.state == "target_move":
            self.confirm_move()
        elif self.state == "target_attack":
            self.confirm_attack()
        elif self.state == "skill_group_menu":
            self.choose_skill_group_option()
        elif self.state == "party_group_menu":
            self.choose_party_group_option()
        elif self.state == "control_menu":
            self.confirm_control()
        elif self.state == "skill_menu":
            self.confirm_skill_menu()
        elif self.state == "target_skill":
            self.confirm_skill()
        elif self.state == "support_target_menu":
            self.confirm_support_target()
        elif self.state == "overwatch_menu":
            self.confirm_overwatch_menu()
        elif self.state == "target_overwatch":
            self.confirm_overwatch()
        elif self.state == "item_menu":
            self.confirm_item()
        elif self.state == "item_target_menu":
            self.confirm_item_target()
        elif self.state == "target_item":
            self.confirm_target_item()
        elif self.state == "tactics_menu":
            self.confirm_tactics()
        elif self.state == "hero_menu":
            self.confirm_hero()
        elif self.state == "map_menu":
            self.confirm_map()
        elif self.state == "enemy_view":
            enemy = self.selected_enemy_view_target()
            if enemy:
                self.cursor = enemy.pos
                self.push(f"Focused {enemy.name}: {self.ui_enemy_intent_summary(enemy)}")

    def spend_ap(self, unit: Unit) -> bool:
        if unit.action_points <= 0:
            self.push(f"{unit.name} has no AP.")
            return False
        unit.action_points -= 1
        return True

    def support_targets_for_skill(self, caster: Unit, skill: Skill) -> List[Unit]:
        """List-style support targeting. No map cursor needed.

        This returns only targets that the selected support skill can actually affect,
        so Field Aid does not open a menu full of healthy allies, Cleanse does not
        offer clean allies, and Guarding Call does not offer already-guarding allies.
        """
        targets = [
            target
            for target in self.valid_skill_targets(caster, skill)
            if self.skill_target_validity_message(caster, target, skill) is None
        ]
        # Keep ally lists in party order so manual turns feel predictable:
        # Rook -> Mira -> Brom -> Aria, minus invalid/self targets.
        order = {unit.name: i for i, unit in enumerate(self.heroes)}
        return sorted(targets, key=lambda u: order.get(u.name, 99))

    def selected_support_target(self) -> Optional[Unit]:
        hero = self.selected_hero
        skill = self.selected_skill(hero)
        targets = self.support_targets_for_skill(hero, skill)
        if not targets:
            return None
        self.support_target_index %= len(targets)
        return targets[self.support_target_index]

    def item_count(self, unit: Unit, item: Item) -> int:
        return unit.inventory.get(item.name, 0)

    def usable_items(self, unit: Optional[Unit] = None) -> List[Item]:
        """Return defined combat items the unit currently owns."""
        unit = unit or self.selected_hero
        return [item for item in self.items if self.item_count(unit, item) > 0]

    def item_menu_window(
        self,
        unit: Optional[Unit] = None,
        max_entries: int = 8,
    ) -> Tuple[List[Tuple[int, Item]], int, int]:
        """Return a selection-following slice plus hidden counts above/below."""
        items = self.usable_items(unit)
        if not items:
            return [], 0, 0
        self.item_index %= len(items)
        max_entries = max(1, int(max_entries))
        start = max(0, self.item_index - max_entries // 2)
        start = min(start, max(0, len(items) - max_entries))
        end = min(len(items), start + max_entries)
        return list(enumerate(items[start:end], start=start)), start, len(items) - end

    def selected_item(self) -> Item:
        items = self.usable_items()
        if not items:
            raise RuntimeError("No usable items available.")
        self.item_index %= len(items)
        return items[self.item_index]

    def item_power_label(self, item: Item) -> str:
        if item.effect == "heal":
            return f"Heal {item.amount}"
        if item.effect == "mp":
            return f"MP {item.amount}"
        if item.effect == "cleanse":
            return "Cleanse"
        if item.effect == "guard":
            return "Guard"
        if item.effect == "damage":
            if item.aoe_radius > 0:
                return f"{item.amount}d r{item.aoe_radius}"
            return f"{item.amount}d"
        return item.effect

    def item_targeting_hint(self, item: Item) -> str:
        if item.target_team == "ally":
            return "Choose one ally from the list."
        if item.aoe_radius > 0:
            return f"Throw within {item.range_max}; damages enemies in radius {item.aoe_radius}."
        return f"Throw at one enemy within {item.range_max} tiles."

    def item_affected_tiles(self, user: Unit, item: Item, target: Pos) -> Set[Pos]:
        if item.target_team != "enemy":
            return set()
        if manhattan(user.pos, target) > item.range_max:
            return set()
        if item.aoe_radius > 0:
            return self.aoe_tiles(target, item.aoe_radius)
        return {target}

    def item_enemy_targets(self, user: Unit, item: Item, target: Pos) -> List[Unit]:
        tiles = self.item_affected_tiles(user, item, target)
        return [enemy for enemy in self.enemies_alive() if enemy.pos in tiles]

    def item_ally_targets(self, user: Unit, item: Item) -> List[Unit]:
        """List-style item targeting, filtered to allies the item can actually affect."""
        order = {unit.name: i for i, unit in enumerate(self.heroes)}
        targets = [
            target
            for target in self.heroes_alive()
            if self.item_target_validity_message(user, item, target=target) is None
        ]
        return sorted(targets, key=lambda u: order.get(u.name, 99))


    def selected_item_target(self) -> Optional[Unit]:
        item = self.selected_item()
        targets = self.item_ally_targets(self.selected_hero, item)
        if not targets:
            return None
        self.item_target_index %= len(targets)
        return targets[self.item_target_index]

    def item_target_validity_message(self, user: Unit, item: Item, target: Optional[Unit] = None, target_pos: Optional[Pos] = None) -> Optional[str]:
        if user.action_points <= 0:
            return f"{user.name} has no AP."
        if self.item_count(user, item) <= 0:
            return f"No {item.name} left."

        if item.target_team == "ally":
            if target is None or target.team != "hero" or not target.alive:
                return "Select an ally."
            if item.effect == "heal" and target.hp >= target.max_hp:
                return f"{target.name} is already full HP."
            if item.effect == "mp" and target.mp >= target.max_mp:
                return f"{target.name} is already full MP."
            if item.effect == "cleanse" and target.poison <= 0 and target.rooted <= 0 and target.vulnerable <= 0:
                return f"{target.name} has no status to cleanse."
            if item.effect == "guard" and target.guard:
                return f"{target.name} is already guarding."
            return None

        if target_pos is None:
            return "Select a target tile."
        if manhattan(user.pos, target_pos) > item.range_max:
            return "Item target is out of range."
        targets = self.item_enemy_targets(user, item, target_pos)
        barrels = self.barrel_tiles_in(self.item_affected_tiles(user, item, target_pos))
        if not targets and not barrels:
            return f"{item.name} would hit nothing."
        return None

    def move_unit_along_path(self, unit: Unit, destination: Pos) -> Tuple[Pos, List[str], str]:
        """Move a unit along its chosen path and apply terrain on every entered tile."""
        old = unit.pos
        terrain_msgs: List[str] = []
        slide_msg = ""
        path = self.find_path(unit, destination)
        if not path:
            terrain_msgs.append(f"{unit.name} is blocked")
            return old, terrain_msgs, slide_msg

        for step in path[1:]:
            if not self.is_walkable(step, ignore=unit):
                terrain_msgs.append(f"{unit.name} is blocked")
                break
            previous = unit.pos
            unit.pos = step
            slide_to = self.ice_slide_destination(unit, unit.pos, previous)
            if slide_to != unit.pos:
                self.flash_effect([previous, unit.pos, slide_to], "ice")
                unit.pos = slide_to
                slide_msg = f" {unit.name} slides to {unit.pos}."
                self.apply_entry_terrain(unit, unit.pos, terrain_msgs)
                break
            self.apply_entry_terrain(unit, unit.pos, terrain_msgs)
            if not unit.alive:
                break
        return old, terrain_msgs, slide_msg

    def confirm_move(self) -> None:
        hero = self.selected_hero
        if hero.rooted > 0:
            if not self.spend_ap(hero):
                return
            hero.rooted = max(0, hero.rooted - 1)
            self.state = "command"
            self.push(f"{hero.name} breaks free from roots but cannot move.")
            return
        reachable = self.reachable_tiles(hero)
        if self.cursor not in reachable:
            self.push("That tile is not reachable.")
            return
        if self.unit_at(self.cursor) not in (None, hero):
            self.push("That tile is occupied.")
            return
        if not self.spend_ap(hero):
            return
        old, terrain_msgs, slide_msg = self.move_unit_along_path(hero, self.cursor)
        hero.guard = False
        self.clear_overwatch_for_unit(hero)
        self.state = "command"
        suffix = (" " + " ".join(terrain_msgs)) if terrain_msgs else ""
        self.record_tutorial_event("move")
        self.push(f"{hero.name} moved {old} -> {hero.pos}.{slide_msg}{suffix}")



    def confirm_attack(self) -> None:
        hero = self.selected_hero
        weapon = hero.weapon
        if self.cursor not in self.weapon_area(hero.pos, weapon):
            self.push("Target is out of range.")
            return

        targets = self.weapon_targets(hero, self.cursor, weapon)
        barrels = self.weapon_barrel_tiles(hero, self.cursor, weapon)
        affected_tiles = self.weapon_affected_tiles(hero.pos, self.cursor, weapon)
        objective_hits = [p for p in self.objective_object_tiles if p in affected_tiles and self.tile_at(p) == TILE_CRATE]
        if not targets and not barrels and not objective_hits:
            self.push("No enemy, objective, or explosive barrel selected.")
            return

        if not self.spend_ap(hero):
            return
        self.clear_overwatch_for_unit(hero)
        self.flash_effect(affected_tiles or [self.cursor], self.weapon_effect_kind(weapon), frames=2 if len(affected_tiles) > 1 else 1)

        parts: List[str] = []
        for target in list(targets):
            if not target.alive:
                continue
            raw_damage = self.weapon_damage_against(hero, target, weapon)
            dmg = target.take_damage(raw_damage)
            status_text = self.apply_weapon_status(target, weapon)
            self.combat_stats["player_damage"] += dmg
            self.record_actor_damage(hero, dmg)
            part = f"{target.name} {dmg}{status_text}"
            if not target.alive:
                part += " KO"
                part += " " + self.award_xp(hero, target)
            parts.append(part)

        for barrel in barrels:
            result = self.explode_barrel(barrel, hero)
            if result:
                parts.append(result)
        parts.extend(self.objective_object_hits(affected_tiles))

        self.state = "command"
        self.record_tutorial_event("attack")
        self.push(f"{hero.name} attacks with {weapon.name}: " + ("; ".join(parts) if parts else "no effect."))
        return


    def confirm_skill(self) -> None:
        hero = self.selected_hero
        skill = self.selected_skill(hero)
        if skill.target_team == "ally":
            self.state = "support_target_menu"
            self.support_target_index = 0
            self.push(f"{skill.name} uses ally list targeting.")
            return
        if hero.mp < skill.mp_cost:
            self.push("Not enough MP.")
            return
        if self.cursor not in self.skill_range(hero.pos, skill):
            self.push("Target is out of skill range.")
            return

        tiles = self.skill_affected_tiles(hero.pos, self.cursor, skill)
        affected = self.skill_targets(hero, self.cursor, skill)
        barrels = self.barrel_tiles_in(tiles)
        objective_hits = [p for p in self.objective_object_tiles if p in tiles and self.tile_at(p) == TILE_CRATE]
        if not affected and not barrels and not objective_hits:
            self.push(f"{skill.name} would hit nothing.")
            return

        if affected:
            primary_target = affected[0]
            invalid = self.skill_target_validity_message(hero, primary_target, skill)
            if invalid:
                self.push(invalid)
                return

        if not self.spend_ap(hero):
            return

        self.clear_overwatch_for_unit(hero)
        hero.mp -= skill.mp_cost
        self.combat_stats["skills_used"] += 1
        self.record_skill_use(hero, skill)
        self.record_build_synergy_use(hero, skill)
        self.flash_effect(tiles, self.skill_effect_kind(skill), frames=2 if skill.aoe_radius > 0 or skill.shape in ("burst", "cone", "strip") else 1)

        parts = []
        combo_triggers = 0
        for e in affected:
            combo_bonus = self.skill_combo_damage_bonus(hero, e, skill)
            triggered = combo_bonus > 0 or (self.skill_combo_triggered(hero, e, skill) and (skill.combo_ap_gain or skill.combo_mp_gain))
            if triggered:
                combo_triggers += 1
            dmg = e.take_damage(skill.damage + combo_bonus)
            self.apply_skill_status(e, skill)
            self.combat_stats["player_damage"] += dmg
            self.record_actor_damage(hero, dmg)
            part = f"{e.name} {dmg}"
            if combo_bonus:
                part += " combo"
            if skill.status:
                part += f" +{skill.status}"
            if not e.alive:
                part += " KO"
                self.award_xp(hero, e)
            parts.append(part)

        combo_result = self.apply_skill_combo_rewards(hero, skill, combo_triggers)
        if combo_result:
            parts.append(combo_result)

        for barrel in barrels:
            result = self.explode_barrel(barrel, hero)
            if result:
                parts.append(result)
        parts.extend(self.objective_object_hits(tiles))

        zone = self.create_skill_zone(hero, skill, self.cursor, tiles)
        if zone:
            parts.append(f"{zone.kind} zone {zone.duration}t")

        self.state = "command"
        self.record_tutorial_event("skill")
        self.push(f"{hero.name} uses {skill.name}: " + ", ".join(parts) + ".")


    def confirm_support_target(self) -> None:
        hero = self.selected_hero
        skill = self.selected_skill(hero)
        target = self.selected_support_target()
        invalid = self.skill_target_validity_message(hero, target, skill)
        if invalid:
            self.push(invalid)
            return
        if hero.mp < skill.mp_cost:
            self.push("Not enough MP.")
            return

        if skill.effect == "transfer_ap":
            transfer = hero.action_points
            if transfer <= 0:
                self.push(f"{hero.name} has no AP to transfer.")
                return
            self.clear_overwatch_for_unit(hero)
            hero.mp -= skill.mp_cost
            self.combat_stats["skills_used"] += 1
            self.record_skill_use(hero, skill)
            self.record_build_synergy_use(hero, skill)
            self.combat_stats["ap_transferred"] = self.combat_stats.get("ap_transferred", 0) + transfer
            hero.action_points = 0
            hero.guard = False
            target.action_points += transfer
            self.state = "command"
            self.record_tutorial_event("skill")
            self.record_tutorial_event("item")
            self.push(f"{hero.name} coordinates with {target.name}: transferred {transfer} AP and ended turn.")
            return

        if not self.spend_ap(hero):
            return
        self.clear_overwatch_for_unit(hero)
        hero.mp -= skill.mp_cost
        self.combat_stats["skills_used"] += 1
        self.record_skill_use(hero, skill)
        self.record_build_synergy_use(hero, skill)
        hero.guard = False

        if skill.effect == "heal":
            self.flash_effect([target.pos], "heal")
            combo_bonus = self.skill_combo_heal_bonus(hero, target, skill)
            heal = min(skill.heal_amount + combo_bonus, target.max_hp - target.hp)
            target.hp += heal
            combo_result = self.apply_skill_combo_rewards(hero, skill, 1 if combo_bonus else 0)
            combo_text = " combo" if combo_bonus else ""
            tail = f" {combo_result}." if combo_result else ""
            self.state = "command"
            self.record_tutorial_event("skill")
            self.record_tutorial_event("item")
            self.push(f"{hero.name} uses {skill.name}: {target.name} +{heal} HP{combo_text}.{tail}")
            return

        if skill.effect == "restore_mp":
            self.flash_effect([target.pos], "mp")
            gain = min(skill.mp_amount, target.max_mp - target.mp)
            target.mp += gain
            self.state = "command"
            self.record_tutorial_event("skill")
            self.record_tutorial_event("item")
            self.push(f"{hero.name} uses {skill.name}: {target.name} +{gain} MP.")
            return

        if skill.effect == "cleanse":
            self.flash_effect([target.pos], "cleanse")
            target.poison = 0
            target.rooted = 0
            target.vulnerable = 0
            self.state = "command"
            self.record_tutorial_event("skill")
            self.record_tutorial_event("item")
            self.push(f"{hero.name} uses {skill.name}: {target.name}'s status effects are removed.")
            return

        if skill.effect == "guard":
            self.flash_effect([target.pos], "guard")
            target.guard = True
            self.state = "command"
            self.record_tutorial_event("skill")
            self.record_tutorial_event("item")
            self.push(f"{hero.name} uses {skill.name}: {target.name} is guarding.")
            return

        self.state = "command"
        self.push(f"{skill.name} has no support effect.")

    def confirm_overwatch_menu(self) -> None:
        hero = self.selected_hero
        option = self.selected_overwatch_option()
        if not self.overwatch_option_enabled(option, hero):
            self.push(f"{option.get('label', 'Overwatch')} is unavailable.")
            return
        self.pending_overwatch_option = option
        self.cursor = self.default_overwatch_cursor(hero, option)
        self.state = "target_overwatch"
        self.push(f"Overwatch selected: {option.get('label')}. Choose line of sight.")

    def confirm_overwatch(self) -> None:
        hero = self.selected_hero
        option = self.pending_overwatch_option or self.selected_overwatch_option()
        if not self.overwatch_option_enabled(option, hero):
            self.push(f"{option.get('label', 'Overwatch')} is unavailable.")
            return
        tiles = self.overwatch_tiles_for_option(hero, option, self.cursor)
        if not tiles:
            self.push("That overwatch area is empty.")
            return
        if not self.spend_ap(hero):
            return
        self.clear_overwatch_for_unit(hero)
        action = OverwatchAction(
            owner=hero,
            kind=str(option.get("kind", "weapon")),
            name=str(option.get("label", "Overwatch")),
            target=self.cursor,
            tiles=set(tiles),
            skill_index=int(option["skill_index"]) if option.get("kind") == "skill" else None,
        )
        self.overwatch_actions.append(action)
        hero.guard = False
        self.pending_overwatch_option = None
        self.overwatch_return_state = "command"
        self.state = "command"
        self.record_tutorial_event("overwatch")
        names = self.overwatch_target_names_for_option(hero, option, self.cursor)
        suffix = f" Currently covered: {', '.join(names)}." if names else ""
        self.push(f"{hero.name} sets Overwatch with {action.name}." + suffix)

    def confirm_item(self) -> None:
        hero = self.selected_hero
        item = self.selected_item()
        if hero.action_points <= 0:
            self.push("No AP for item.")
            return
        if self.item_count(hero, item) <= 0:
            self.push(f"No {item.name} left.")
            return
        if item.target_team == "ally":
            targets = self.item_ally_targets(hero, item)
            if not targets:
                self.push("No valid allies.")
                return
            self.item_target_index = 0
            self.state = "item_target_menu"
            self.push(f"{item.name} selected. Choose an ally.")
            return
        self.state = "target_item"
        if self.enemies_alive():
            self.cursor = min(self.enemies_alive(), key=lambda e: manhattan(hero.pos, e.pos)).pos
        else:
            self.cursor = hero.pos
        self.push(f"{item.name} selected. Choose target tile.")

    def consume_selected_item(self, user: Unit, item: Item) -> None:
        user.inventory[item.name] = max(0, user.inventory.get(item.name, 0) - 1)
        if item.name == "Potion":
            self.combat_stats["potions_used"] += 1
        self.combat_stats["items_used"] = self.combat_stats.get("items_used", 0) + 1
        self.record_item_use(user, item)

    def confirm_item_target(self) -> None:
        hero = self.selected_hero
        item = self.selected_item()
        target = self.selected_item_target()
        invalid = self.item_target_validity_message(hero, item, target=target)
        if invalid:
            self.push(invalid)
            return
        if not self.spend_ap(hero):
            return
        self.clear_overwatch_for_unit(hero)
        self.consume_selected_item(hero, item)
        hero.guard = False

        if item.effect == "heal":
            self.flash_effect([target.pos], "heal")
            amount = min(item.amount, target.max_hp - target.hp)
            target.hp += amount
            self.state = "command"
            self.record_tutorial_event("item")
            self.push(f"{hero.name} uses {item.name}: {target.name} +{amount} HP.")
            return
        if item.effect == "mp":
            self.flash_effect([target.pos], "mp")
            amount = min(item.amount, target.max_mp - target.mp)
            target.mp += amount
            self.state = "command"
            self.record_tutorial_event("item")
            self.push(f"{hero.name} uses {item.name}: {target.name} +{amount} MP.")
            return
        if item.effect == "cleanse":
            self.flash_effect([target.pos], "cleanse")
            target.poison = 0
            target.rooted = 0
            target.vulnerable = 0
            self.state = "command"
            self.record_tutorial_event("item")
            self.push(f"{hero.name} uses {item.name}: {target.name}'s status cleared.")
            return
        if item.effect == "guard":
            self.flash_effect([target.pos], "guard")
            target.guard = True
            self.state = "command"
            self.record_tutorial_event("item")
            self.push(f"{hero.name} uses {item.name}: {target.name} guards.")
            return

        self.state = "command"
        self.push(f"{hero.name} uses {item.name}.")

    def confirm_target_item(self) -> None:
        hero = self.selected_hero
        item = self.selected_item()
        invalid = self.item_target_validity_message(hero, item, target_pos=self.cursor)
        if invalid:
            self.push(invalid)
            return
        if not self.spend_ap(hero):
            return
        self.clear_overwatch_for_unit(hero)
        self.consume_selected_item(hero, item)
        hero.guard = False

        targets = self.item_enemy_targets(hero, item, self.cursor)
        affected_item_tiles = self.item_affected_tiles(hero, item, self.cursor)
        self.flash_effect(affected_item_tiles, "fire" if item.aoe_radius > 0 else "hit", frames=2 if item.aoe_radius > 0 else 1)
        barrels = self.barrel_tiles_in(affected_item_tiles)
        parts = []
        for enemy in list(targets):
            dmg = enemy.take_damage(item.amount)
            self.combat_stats["player_damage"] += dmg
            self.record_actor_damage(hero, dmg)
            part = f"{enemy.name} {dmg}"
            if not enemy.alive:
                part += " KO"
                self.award_xp(hero, enemy)
            parts.append(part)
        for barrel in barrels:
            result = self.explode_barrel(barrel, hero)
            if result:
                parts.append(result)

        self.state = "command"
        self.record_tutorial_event("item")
        self.push(f"{hero.name} uses {item.name}: " + ", ".join(parts) + ".")

    def confirm_tactics(self) -> None:
        tactics = ["Balanced", "Aggressive", "Cautious", "Support"]
        self.follower_tactic = tactics[self.tactics_index]
        self.state = "command"
        self.push(f"AI companion tactic set to {self.follower_tactic}.")

    def confirm_hero(self) -> None:
        hero = self.heroes[self.hero_menu_index]
        if not hero.active:
            self.push("That hero is in reserve. Change party from the Main Menu.")
            return
        if not hero.alive:
            self.push("That hero is down.")
            return
        if hero.ai_controlled:
            self.push("That hero is AI-controlled. Use Party > Control to set them Manual.")
            return
        self.selected_hero_idx = self.hero_menu_index
        self.cursor = self.selected_hero.pos
        self.state = "command"
        self.push(f"Selected {self.selected_hero.name} ({self.selected_hero.action_points} AP).")

    def confirm_map(self) -> None:
        if not self.allow_battle_map_selection:
            self.state = "command"
            self.push("Map selection is unavailable during this encounter.")
            return
        self.map_index = self.map_menu_index
        self.map_name, self.map, self.start_positions = self.maps[self.map_index]
        self.custom_encounter_enabled = False
        self.custom_encounter_enabled = False
        self.active_enemy_names = set(self.enemy_loadout_for_map(self.map_name))
        self.tutorial_active = False
        self.tutorial_mode = "basic"
        self.tutorial_flags = set()
        self.reset_battle_positions()
        self.state = "command"
        self.push(f"Loaded arena: {self.map_name}.")

    def restart_current_battle(self) -> None:
        self.reset_battle_positions()
        self.state = "command"
        self.push(f"Reset {self.map_name}.")

    def reset_battle_positions(self) -> None:
        # Reset encounter to make map testing clean and predictable.
        # Rebuild the selected arena so exploded barrels and destroyed objects reset cleanly.
        self.maps = self.build_maps()
        self.map_name, self.map, self.start_positions = self.maps[self.map_index]

        base_stats = {
            "Rook": {"max_hp": 42, "max_mp": 12, "weapon_damage": 6, "move_range": 5, "inventory": {"Potion": 2, "Ether": 1, "Cleanse Kit": 1, "Guard Tonic": 1, "Throwing Knife": 2, "Fire Bomb": 1}},
            "Mira": {"max_hp": 30, "max_mp": 16, "weapon_damage": 4, "move_range": 4, "inventory": {"Potion": 1, "Ether": 1, "Throwing Knife": 1}},
            "Brom": {"max_hp": 38, "max_mp": 10, "weapon_damage": 5, "move_range": 4, "inventory": {"Potion": 1, "Guard Tonic": 1, "Throwing Knife": 1}},
            "Aria": {"max_hp": 26, "max_mp": 18, "weapon_damage": 3, "move_range": 5, "inventory": {"Potion": 1, "Ether": 1, "Cleanse Kit": 1}},
            "Nia": {"max_hp": 32, "max_mp": 14, "weapon_damage": 4, "move_range": 6, "inventory": {"Potion": 1, "Throwing Knife": 2, "Guard Tonic": 1}},
            "Dax": {"max_hp": 44, "max_mp": 8, "weapon_damage": 6, "move_range": 4, "inventory": {"Potion": 2, "Guard Tonic": 1}},
            "Luma": {"max_hp": 28, "max_mp": 20, "weapon_damage": 3, "move_range": 5, "inventory": {"Potion": 1, "Ether": 2, "Cleanse Kit": 1}},
            "Training Dummy": {"max_hp": 30, "max_mp": 0, "weapon_damage": 0, "move_range": 0, "potions": 0},
            "Crow": {"max_hp": 18, "max_mp": 0, "weapon_damage": 3, "move_range": 6, "potions": 1},
            "Boar": {"max_hp": 34, "max_mp": 0, "weapon_damage": 5, "move_range": 4, "potions": 1},
            "Vine": {"max_hp": 24, "max_mp": 0, "weapon_damage": 4, "move_range": 2, "potions": 1},
            "Slime": {"max_hp": 22, "max_mp": 0, "weapon_damage": 3, "move_range": 2, "potions": 1},
            "Wolf": {"max_hp": 20, "max_mp": 0, "weapon_damage": 4, "move_range": 6, "potions": 1},
            "Bandit": {"max_hp": 22, "max_mp": 0, "weapon_damage": 4, "move_range": 4, "potions": 1},
            "Shield Guard": {"max_hp": 30, "max_mp": 0, "weapon_damage": 4, "move_range": 3, "potions": 1},
            "Sporeling": {"max_hp": 18, "max_mp": 0, "weapon_damage": 2, "move_range": 3, "potions": 1},
            "Wisp": {"max_hp": 16, "max_mp": 0, "weapon_damage": 4, "move_range": 5, "potions": 1},
            "Rockback": {"max_hp": 42, "max_mp": 0, "weapon_damage": 6, "move_range": 2, "potions": 1},
            "Marsh Toad": {"max_hp": 26, "max_mp": 0, "weapon_damage": 3, "move_range": 3, "potions": 1},
            "Razor Hare": {"max_hp": 16, "max_mp": 0, "weapon_damage": 3, "move_range": 7, "potions": 1},
            "Ember Imp": {"max_hp": 20, "max_mp": 0, "weapon_damage": 3, "move_range": 4, "potions": 1},
            "Frost Moth": {"max_hp": 18, "max_mp": 0, "weapon_damage": 2, "move_range": 5, "potions": 1},
            "Burrower": {"max_hp": 28, "max_mp": 0, "weapon_damage": 5, "move_range": 3, "potions": 1},
            "Thornback": {"max_hp": 32, "max_mp": 0, "weapon_damage": 4, "move_range": 3, "potions": 1},
            "Old Briarthorn": {"max_hp": 72, "max_mp": 0, "weapon_damage": 7, "move_range": 2, "potions": 2},
        }
        self.enforce_party_limit()
        if self.custom_encounter_enabled:
            if not self.active_enemy_names:
                self.active_enemy_names = set(self.selected_custom_enemy_names())
        else:
            self.active_enemy_names = set(self.enemy_loadout_for_map(self.map_name))
        for unit in self.heroes + self.enemies:
            if unit.team == "hero":
                unit.active = unit.name in self.active_party_names
            else:
                unit.active = unit.name in self.active_enemy_names
            base_name = self.enemy_base_name(unit.name) if unit.team == "enemy" else unit.name
            if base_name in base_stats:
                spec = base_stats[base_name]
                if unit.team == "hero":
                    progress = self.ensure_progress_entry(unit)
                    unit.level = int(progress["level"])
                    unit.xp = int(progress["xp"])
                    unit.move_range = int(spec.get("move_range", unit.move_range))
                    unit.max_hp = spec["max_hp"] + int(progress["hp_bonus"])
                    unit.max_mp = spec["max_mp"] + int(progress["mp_bonus"])
                    unit.weapon = self.base_weapon_for_hero(unit.name)
                    self.apply_equipment_to_hero(unit)
                    unit.inventory = dict(spec["inventory"])
                    for item_name, bonus in self.item_loadout_bonus.items():
                        if bonus > 0:
                            unit.inventory[item_name] = unit.inventory.get(item_name, 0) + bonus
                else:
                    unit.max_hp = spec["max_hp"]
                    unit.max_mp = spec["max_mp"]
                    unit.move_range = int(spec.get("move_range", unit.move_range))
                    unit.weapon.damage = spec["weapon_damage"]
                    if self.enemy_is_elite_name(unit.name):
                        unit.max_hp = int(unit.max_hp * 1.5)
                        unit.weapon.damage += 2
                    potion_count = int(spec.get("potions", 0))
                    unit.inventory = {"Potion": potion_count} if potion_count > 0 else {}
                    unit.level = 1
                    unit.xp = 0
            elif unit.team == "hero":
                progress = self.ensure_progress_entry(unit)
                custom = progress.get("custom_base_stats", {})
                if not isinstance(custom, dict):
                    custom = {"max_hp": 34, "max_mp": 12, "weapon_damage": 5, "move_range": 5}
                    progress["custom_base_stats"] = custom
                unit.level = int(progress["level"])
                unit.xp = int(progress["xp"])
                unit.move_range = int(custom.get("move_range", unit.move_range))
                unit.max_hp = int(custom.get("max_hp", unit.max_hp)) + int(progress["hp_bonus"])
                unit.max_mp = int(custom.get("max_mp", unit.max_mp)) + int(progress["mp_bonus"])
                unit.weapon = self.base_weapon_for_hero(unit.name)
                self.apply_equipment_to_hero(unit)
                unit.inventory = dict(progress.get("custom_inventory", {"Potion": 1, "Ether": 1}))
                for item_name, bonus in self.item_loadout_bonus.items():
                    if bonus > 0:
                        unit.inventory[item_name] = unit.inventory.get(item_name, 0) + bonus
            if unit.name in self.start_positions:
                unit.pos = self.start_positions[unit.name]
            unit.hp = unit.max_hp
            unit.mp = unit.max_mp
            unit.guard = False
            unit.poison = 0
            unit.rooted = 0
            unit.vulnerable = 0
            unit.action_points = 2 if unit.team == "hero" else 0
            for key in unit.cooldowns:
                unit.cooldowns[key] = 0
        self.place_active_party_members()

        # Preserve initial intended enemy cooldown offsets.
        for enemy in self.enemies:
            if not enemy.active:
                continue
            if self.enemy_base_name(enemy.name) in ("Boar",):
                enemy.cooldowns["Brutal Charge"] = 1
            if self.enemy_base_name(enemy.name) in ("Rockback",):
                enemy.cooldowns["Brutal Charge"] = 2
            if self.enemy_base_name(enemy.name) in ("Vine",):
                enemy.cooldowns["Binding Roots"] = 1
                enemy.cooldowns["Toxic Burst"] = 2
            if self.enemy_base_name(enemy.name) in ("Sporeling",):
                enemy.cooldowns["Toxic Burst"] = 1
            if self.enemy_base_name(enemy.name) in ("Old Briarthorn",):
                enemy.cooldowns["Binding Roots"] = 0
                enemy.cooldowns["Toxic Burst"] = 1
                enemy.cooldowns["War Cry"] = 0
        self.place_active_enemies()

        # Preserve per-companion control settings across battle/map resets.
        self.selected_hero_idx = 0
        self.apply_companion_control_settings()
        self.advance_to_next_ready_hero()
        self.cursor = self.selected_hero.pos
        self.round_no = 1
        self.combat_stats = self.initial_combat_stats()
        self.record_starting_threat()
        self.rewards = {key: 0 for key in self.loot_keys}
        self.battle_result_processed = False
        self.last_result_lines = []
        self.result_section_index = 0
        self.overwatch_actions = []
        self.pending_overwatch_option = None
        self.zones = []
        self.combat_log = []
        self.combat_log_scroll = 0
        self.combat_log_return_state = "command"
        self.setup_objective_state()
        self.add_combat_log_entry(f"Battle reset on {self.map_name}. Objective: {self.objective_mode}.", category="SYSTEM")

    def guard_action(self) -> None:
        hero = self.selected_hero
        if hero.action_points <= 0:
            self.push("No AP for guard.")
            return
        if not self.spend_ap(hero):
            return
        self.clear_overwatch_for_unit(hero)
        hero.guard = True
        self.flash_effect([hero.pos], "guard")
        self.state = "command"
        self.record_tutorial_event("guard")
        self.push(f"{hero.name} guards. Damage halved until next hero turn.")

    def ensure_progress_entry(self, hero: Unit) -> Dict[str, object]:
        progress = self.party_progress.setdefault(hero.name, {})
        progress.setdefault("level", hero.level)
        progress.setdefault("xp", hero.xp)
        progress.setdefault("hp_bonus", 0)
        progress.setdefault("mp_bonus", 0)
        progress.setdefault("damage_bonus", 0)
        progress.setdefault("class", self.default_class_for_hero(hero.name))
        valid_classes = set(self.class_names())
        focus_class = str(progress.get("class", self.default_class_for_hero(hero.name)))
        if focus_class not in valid_classes:
            focus_class = self.default_class_for_hero(hero.name)
            progress["class"] = focus_class
        active_classes = progress.setdefault("active_classes", [focus_class])
        if not isinstance(active_classes, list):
            active_classes = list(active_classes) if isinstance(active_classes, (set, tuple)) else [focus_class]
            progress["active_classes"] = active_classes
        active_classes[:] = [str(name) for name in active_classes if str(name) in valid_classes]
        if focus_class not in active_classes:
            active_classes.insert(0, focus_class)
        if not active_classes:
            active_classes.append(focus_class)
        progress.setdefault("subclass", self.default_subclass_for_hero(hero.name))
        progress.setdefault("color", self.default_hero_color_name(hero.name))
        # Give a couple of starter SP so the class system is testable immediately.
        progress.setdefault("skill_points", 3)
        unlocks = progress.setdefault("class_unlocks", {})
        if not isinstance(unlocks, dict):
            unlocks = {}
            progress["class_unlocks"] = unlocks
        for class_name in self.class_names():
            current = unlocks.setdefault(class_name, set())
            if not isinstance(current, set):
                unlocks[class_name] = set(current)
        ranks = progress.setdefault("skill_ranks", {})
        if not isinstance(ranks, dict):
            ranks = {}
            progress["skill_ranks"] = ranks
        for class_name in self.class_names():
            class_ranks = ranks.setdefault(class_name, {})
            if not isinstance(class_ranks, dict):
                ranks[class_name] = dict(class_ranks)

        defaults = self.default_equipment_for_hero(hero.name)
        equipped = progress.setdefault("equipped_gear", dict(defaults))
        if not isinstance(equipped, dict):
            equipped = dict(defaults)
            progress["equipped_gear"] = equipped
        for slot, name in defaults.items():
            equipped.setdefault(slot, name)

        unlocked = progress.setdefault("unlocked_gear", {})
        if not isinstance(unlocked, dict):
            unlocked = {}
            progress["unlocked_gear"] = unlocked
        for slot, name in defaults.items():
            slot_set = unlocked.setdefault(slot, {name})
            if not isinstance(slot_set, set):
                slot_set = set(slot_set)
                unlocked[slot] = slot_set
            slot_set.add(name)
        return progress


    def gain_hero_xp(self, hero: Unit, amount: int) -> List[str]:
        """Apply persistent XP/level gains and mirror them onto the current unit."""
        if amount <= 0 or hero.team != "hero":
            return []

        progress = self.ensure_progress_entry(hero)
        progress["xp"] += amount
        level_messages: List[str] = []

        while progress["xp"] >= 20:
            progress["xp"] -= 20
            progress["level"] = int(progress.get("level", 1)) + 1
            progress["hp_bonus"] = int(progress.get("hp_bonus", 0)) + 4
            progress["mp_bonus"] = int(progress.get("mp_bonus", 0)) + 2
            progress["damage_bonus"] = int(progress.get("damage_bonus", 0)) + 1
            progress["skill_points"] = int(progress.get("skill_points", 0)) + 1
            self.combat_stats["level_ups"] = self.combat_stats.get("level_ups", 0) + 1
            level_messages.append(f"{hero.name} reached Lv {progress['level']}! +1 SP.")

        hero.level = int(progress["level"])
        hero.xp = int(progress["xp"])
        hero.max_hp = self.base_hero_stat(hero.name, "max_hp") + int(progress["hp_bonus"])
        hero.max_mp = self.base_hero_stat(hero.name, "max_mp") + int(progress["mp_bonus"])
        hero.weapon.damage = self.base_hero_stat(hero.name, "weapon_damage") + int(progress["damage_bonus"])
        hero.hp = min(hero.max_hp, hero.hp)
        hero.mp = min(hero.max_mp, hero.mp)
        return level_messages


    def base_hero_stat(self, name: str, key: str) -> int:
        base = {
            "Rook": {"max_hp": 42, "max_mp": 12, "weapon_damage": 6, "move_range": 5},
            "Mira": {"max_hp": 30, "max_mp": 16, "weapon_damage": 4, "move_range": 4},
            "Brom": {"max_hp": 38, "max_mp": 10, "weapon_damage": 5, "move_range": 4},
            "Aria": {"max_hp": 26, "max_mp": 18, "weapon_damage": 3, "move_range": 5},
            "Nia": {"max_hp": 32, "max_mp": 14, "weapon_damage": 4, "move_range": 6},
            "Dax": {"max_hp": 44, "max_mp": 8, "weapon_damage": 6, "move_range": 4},
            "Luma": {"max_hp": 28, "max_mp": 20, "weapon_damage": 3, "move_range": 5},
        }
        if name in getattr(self, "party_progress", {}):
            custom = self.party_progress.get(name, {}).get("custom_base_stats", {})
            if isinstance(custom, dict) and key in custom:
                return int(custom.get(key, 0))
        return base.get(name, {}).get(key, {"max_hp": 34, "max_mp": 12, "weapon_damage": 5, "move_range": 5}.get(key, 0))

    def loot_profile_for_enemy(self, name: str) -> Dict[str, Dict[str, int]]:
        return data_loot_profile_for_enemy(self.enemy_base_name(name))

    def merge_rewards(self, *reward_sets: Dict[str, int]) -> Dict[str, int]:
        merged: Dict[str, int] = {}
        for rewards in reward_sets:
            for key, amount in rewards.items():
                if amount <= 0:
                    continue
                merged[key] = merged.get(key, 0) + amount
        return merged

    def loot_text_with_rarity(self, label: str, rewards: Dict[str, int]) -> str:
        if not rewards:
            return ""
        return f"{label}: " + self.inventory_text(rewards)

    def enemy_rare_drop_enabled(self, enemy: Unit) -> bool:
        if enemy.boss or self.enemy_is_boss_name(enemy.name):
            return True
        if self.enemy_is_elite_name(enemy.name):
            return True
        # Deterministic "good play" rare: fast kill or high-risk cleanup.
        return self.round_no <= 4 or enemy.vulnerable > 0 or enemy.poison > 0 or enemy.rooted > 0

    def enemy_reward_preview(self, name: str) -> Dict[str, int]:
        profile = self.loot_profile_for_enemy(name)
        loot = self.merge_rewards(profile.get("common", {}), profile.get("uncommon", {}))
        if self.enemy_is_elite_name(name):
            loot = self.merge_rewards(loot, profile.get("rare", {}), {"Coin": max(4, loot.get("Coin", 0)), "Shard": 1})
        if self.enemy_is_boss_name(name):
            loot = self.merge_rewards(loot, profile.get("rare", {}))
        return loot


    def grant_enemy_rewards(self, enemy: Unit) -> str:
        profile = self.loot_profile_for_enemy(enemy.name)
        common = dict(profile.get("common", {}))
        uncommon = dict(profile.get("uncommon", {}))
        rare = dict(profile.get("rare", {})) if self.enemy_rare_drop_enabled(enemy) else {}
        special: Dict[str, int] = {}

        if self.enemy_is_elite_name(enemy.name):
            special = self.merge_rewards(special, {"Coin": max(4, enemy.max_hp // 6), "Shard": 1})
        if enemy.boss or self.enemy_is_boss_name(enemy.name):
            special = self.merge_rewards(special, {"Relic Cache": 1})

        loot = self.merge_rewards(common, uncommon, rare, special)
        for key, amount in loot.items():
            self.rewards[key] = self.rewards.get(key, 0) + amount

        log: List[str] = self.combat_stats.setdefault("loot_log", [])
        for label, rewards in [
            ("Common", common),
            ("Uncommon", uncommon),
            ("Rare", rare),
            ("Elite", special if self.enemy_is_elite_name(enemy.name) else {}),
            ("Boss", special if enemy.boss or self.enemy_is_boss_name(enemy.name) else {}),
        ]:
            line = self.loot_text_with_rarity(label, rewards)
            if line:
                log.append(f"{enemy.name} — {line}")

        if rare:
            self.combat_stats["rare_loot_found"] = self.combat_stats.get("rare_loot_found", 0) + sum(rare.values())

        return self.inventory_text(loot)


    def award_xp(self, hero: Unit, enemy: Unit) -> str:
        defeated = self.combat_stats.setdefault("defeated", [])
        if enemy.name in defeated:
            return f"{enemy.name} was already defeated."

        gained = 8 + enemy.max_hp // 2
        self.combat_stats["kills"] += 1
        self.record_ko(hero, enemy)
        self.combat_stats["xp_earned"] = self.combat_stats.get("xp_earned", 0) + gained
        defeated.append(enemy.name)
        loot_text = self.grant_enemy_rewards(enemy)
        level_messages = self.gain_hero_xp(hero, gained)
        text = f"{enemy.name} defeated. {hero.name} +{gained} XP. Loot: {loot_text}."
        if level_messages:
            text += " " + " ".join(level_messages)
        return text


    def cancel(self) -> None:
        if self.state == "combat_log":
            self.close_combat_log()
        elif self.state == "command":
            self.push("Already in command menu.")
        elif self.state == "enemy_view":
            self.state = "command"
            self.cursor = self.selected_hero.pos
            self.push("Cancelled. Back to command menu.")
        elif self.state in ("skill_group_menu", "party_group_menu"):
            self.state = "command"
            self.push("Cancelled. Back to command menu.")
        elif self.state == "skill_menu":
            self.state = "skill_group_menu"
            self.push("Cancelled. Back to Skills menu.")
        elif self.state in ("overwatch_menu", "target_overwatch"):
            destination = self.overwatch_return_state if self.overwatch_return_state in ("command", "skill_group_menu") else "command"
            self.state = destination
            self.pending_overwatch_option = None
            self.cursor = self.selected_hero.pos
            self.overwatch_return_state = "command"
            self.push("Cancelled. Back to Skills menu." if destination == "skill_group_menu" else "Cancelled. Back to command menu.")
        elif self.state in ("tactics_menu", "hero_menu", "control_menu"):
            self.state = "party_group_menu"
            self.push("Cancelled. Back to Party menu.")
        elif self.state == "support_target_menu":
            self.state = "skill_menu"
            self.push("Cancelled. Back to skill menu.")
        elif self.state in ("item_target_menu", "target_item"):
            self.state = "item_menu"
            self.push("Cancelled. Back to item menu.")
        else:
            self.state = "command"
            self.cursor = self.selected_hero.pos
            self.pending_overwatch_option = None
            self.push("Cancelled. Back to command menu.")


    def next_hero(self, require_ap: bool = False, announce: bool = True) -> bool:
        for _ in range(len(self.heroes)):
            self.selected_hero_idx = (self.selected_hero_idx + 1) % len(self.heroes)
            h = self.heroes[self.selected_hero_idx]
            if h.active and h.alive and not h.ai_controlled and (not require_ap or h.action_points > 0):
                self.cursor = h.pos
                if announce:
                    self.push(f"Selected {h.name} ({h.action_points} AP).")
                return True
        return False

    def ready_manual_heroes(self) -> List[Unit]:
        return [h for h in self.controllable_heroes_alive() if h.action_points > 0]

    def current_manual_hero_is_ready(self) -> bool:
        h = self.selected_hero
        return h.active and h.alive and not h.ai_controlled and h.action_points > 0

    def advance_to_next_ready_hero(self) -> bool:
        ready = self.ready_manual_heroes()
        if not ready:
            return False
        if self.current_manual_hero_is_ready():
            return True
        previous = self.selected_hero.name
        if self.next_hero(require_ap=True, announce=False):
            self.cursor = self.selected_hero.pos
            self.push(f"{previous} is out of AP. Now controlling {self.selected_hero.name}.")
            return True
        return False


    def maybe_auto_end(self) -> None:
        if self.turn != "hero" or self.state != "command":
            return

        ready = self.ready_manual_heroes()
        if ready:
            self.advance_to_next_ready_hero()
            return

        self.end_turn()


    # ----- enemy turn -----

    def end_turn(self) -> None:
        self.record_tutorial_event("end_turn")
        self.state = "command"
        ai_followers = self.followers_alive()
        if ai_followers:
            self.turn = "ally_ai"
            self.push("Follower turn.")
            self.render()
            if self.frame_delay > 0:
                time.sleep(self.frame_delay)
            self.follower_turn()
            if self.game_over():
                return
        else:
            self.push("No AI follower phase.")
        self.turn = "enemy"
        self.push("Enemy turn.")
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)
        self.enemy_turn()

    def apply_start_of_turn_status(self, unit: Unit, events: List[str]) -> None:
        if not unit.alive:
            return
        if unit.poison > 0:
            dmg = 1
            unit.hp = max(0, unit.hp - dmg)
            if unit.team == "hero":
                self.combat_stats["enemy_damage"] += dmg
                self.record_damage_taken(unit, dmg)
            unit.poison -= 1
            events.append(f"{unit.name} poison {dmg}")
        if unit.vulnerable > 0:
            unit.vulnerable -= 1
        self.apply_start_tile_effects(unit, events)
        # Root is consumed by attempted movement. Do not tick it here,
        # or Vine's Binding Roots expires before the player can react.

    def tick_cooldowns(self, unit: Unit) -> None:
        for key in list(unit.cooldowns):
            if unit.cooldowns[key] > 0:
                unit.cooldowns[key] -= 1

    def apply_party_start_statuses(self, events: List[str]) -> None:
        for hero in self.heroes_alive():
            self.apply_start_of_turn_status(hero, events)

    def follower_turn(self) -> None:
        """Run AI turns for AI-controlled party members before enemies act."""
        events: List[str] = []

        for follower in self.followers_alive():
            # Follower gets to spend its current AP, usually 2.
            while follower.alive and follower.action_points > 0 and self.enemies_alive():
                action = self.choose_follower_action(follower)
                if not action:
                    follower.guard = True
                    follower.action_points = max(0, follower.action_points - 1)
                    events.append(f"{follower.name} guards")
                    break

                kind = action[0]

                if kind == "potion":
                    self.follower_use_potion(follower, events)

                elif kind == "attack":
                    _, target = action
                    self.follower_attack(follower, target, events)

                elif kind == "barrel":
                    _, barrel_pos, _targets, _allies, _score = action
                    self.follower_attack_barrel(follower, barrel_pos, events)

                elif kind == "skill":
                    _, skill, center, targets = action
                    self.follower_cast_skill(follower, skill, center, targets, events)

                elif kind == "move":
                    _, destination = action
                    if follower.rooted > 0:
                        follower.rooted = max(0, follower.rooted - 1)
                        follower.action_points -= 1
                        events.append(f"{follower.name} is rooted")
                        break
                    old, terrain_msgs, slide_msg = self.move_unit_along_path(follower, destination)
                    follower.guard = False
                    self.clear_overwatch_for_unit(follower)
                    follower.action_points -= 1
                    extra = ("; " + "; ".join(terrain_msgs)) if terrain_msgs else ""
                    events.append(f"{follower.name} moves {old}->{follower.pos}{slide_msg}{extra}")
                    self.render()
                    if self.frame_delay > 0:
                        time.sleep(self.frame_delay)

                elif kind == "overwatch":
                    _, option, target, tiles, predicted_targets, _score = action
                    self.follower_set_overwatch(follower, option, target, tiles, predicted_targets, events)
                    # Once Mira sets an overwatch lane, preserve it for the enemy turn.
                    break

                else:
                    follower.guard = True
                    self.clear_overwatch_for_unit(follower)
                    follower.action_points = max(0, follower.action_points - 1)
                    events.append(f"{follower.name} waits")
                    break

        if events:
            self.push("Follower: " + "; ".join(events))
        else:
            self.push("Follower has no action.")

    def choose_follower_action(self, follower: Unit):
        """Pick the follower's next action.

        Mira now treats Overwatch as a party-side planning tool:
        - Aggressive prefers direct hits and only watches if no clean hit exists.
        - Balanced uses Overwatch when it predicts better value than moving.
        - Cautious/Support favor safe lane control and control-skill overwatch.
        """
        heal_threshold = 0.50 if self.follower_tactic in ("Cautious", "Support") else 0.35
        if follower.hp <= follower.max_hp * heal_threshold and follower.inventory.get("Potion", 0) > 0:
            return ("potion",)

        skill_action = self.best_follower_skill_action(follower)
        attack_action = self.best_follower_attack_action(follower)
        barrel_action = self.best_barrel_attack(follower, "enemy", threshold=22)
        overwatch_action = self.best_follower_overwatch_action(follower)

        # Prefer a skill only when it clearly earns the MP.
        # This keeps the follower helpful without letting her solve the whole fight.
        if skill_action:
            _, skill, _center, targets, score = skill_action
            if skill.effect == "heal":
                heal_threshold_score = {
                    "Aggressive": 120,
                    "Balanced": 95,
                    "Cautious": 75,
                    "Support": 55,
                }.get(self.follower_tactic, 95)
                if score >= heal_threshold_score:
                    return ("skill", skill, _center, targets)
            else:
                skill_threshold = {
                    "Aggressive": 60,
                    "Balanced": 85,
                    "Cautious": 110,
                    "Support": 95,
                }.get(self.follower_tactic, 85)
                if self.follower_tactic == "Aggressive" and (len(targets) >= 2 or score >= skill_threshold):
                    return ("skill", skill, _center, targets)
                if len(targets) >= 2 or any(e.hp <= skill.damage for e in targets) or score >= skill_threshold:
                    return ("skill", skill, _center, targets)

        if barrel_action:
            _kind, _barrel_pos, targets, allies, barrel_score = barrel_action
            attack_score = 0
            if attack_action:
                attack_target = attack_action[1]
                attack_score = min(follower.weapon.damage, attack_target.hp) * 8 + (35 if attack_target.hp <= follower.weapon.damage else 0)
            if targets and not allies and barrel_score >= attack_score + 4:
                return barrel_action

        if attack_action:
            # Cautious/support Mira may choose a strong lane instead of a weak poke.
            if overwatch_action and self.follower_tactic in ("Cautious", "Support"):
                _, _option, _target, _tiles, predicted_targets, ow_score = overwatch_action
                attack_target = attack_action[1]
                attack_score = min(follower.weapon.damage, attack_target.hp) * 8 + (35 if attack_target.hp <= follower.weapon.damage else 0)
                if predicted_targets and ow_score >= attack_score + 8:
                    return overwatch_action
            return ("attack", attack_action[1])

        if overwatch_action:
            _, option, _target, _tiles, predicted_targets, ow_score = overwatch_action
            threshold = {
                "Aggressive": 42,
                "Balanced": 34,
                "Cautious": 24,
                "Support": 22,
            }.get(self.follower_tactic, 34)

            # Support gets extra value from control overwatches like Blinding Flash/Snare Burst.
            if option.get("kind") == "skill" and self.follower_tactic == "Support":
                skill = self.skill_from_overwatch_option(option)
                if skill and skill.status in ("root", "vulnerable") and predicted_targets:
                    threshold -= 6

            if ow_score >= threshold:
                return overwatch_action

        move = self.best_follower_move(follower)
        if move and move != follower.pos:
            return ("move", move)

        # Last-chance progress move: if the scorer still prefers the current
        # tile, try the best path-progress tile before giving up.
        target = max(self.enemies_alive(), key=lambda e: -self.ai_progress_to_attack_band(follower, follower.pos, e), default=None)
        fallback_move = self.best_reachable_progress_tile(follower, target) if target else follower.pos
        if fallback_move != follower.pos:
            return ("move", fallback_move)

        # If no good move exists but a weak skill exists, allow it.
        if skill_action:
            _, skill, center, targets, _score = skill_action
            return ("skill", skill, center, targets)

        # If no predicted movement lane exists, guarding is safer than a dead Overwatch.
        return None

    def best_follower_attack_action(self, follower: Unit):
        targets = [
            e for e in self.enemies_alive()
            if e.pos in self.weapon_area(follower.pos, follower.weapon)
        ]
        if not targets:
            return None
        target = max(
            targets,
            key=lambda e: (
                1 if e.hp <= follower.weapon.damage else 0,
                min(follower.weapon.damage, e.hp),
                -e.hp,
            ),
        )
        return ("attack", target)

    def ai_skill_candidate_centers(self, caster: Unit, skill: Skill) -> Set[Pos]:
        """Return a compact set of useful skill targets for AI evaluation.

        v65 larger maps made scanning every tile in skill range noticeably slow.
        These candidates keep AI decisions tactical while scaling with enemy count
        instead of total map area.
        """
        enemies = self.enemies_alive()
        in_range = self.skill_range(caster.pos, skill)
        candidates: Set[Pos] = set()

        if skill.shape == "point":
            candidates |= {enemy.pos for enemy in enemies}
        elif skill.shape == "burst":
            radius = max(0, skill.aoe_radius)
            for enemy in enemies:
                ex, ey = enemy.pos
                for y in range(ey - radius, ey + radius + 1):
                    for x in range(ex - radius, ex + radius + 1):
                        pos = (x, y)
                        if self.in_bounds(pos) and manhattan(pos, enemy.pos) <= radius:
                            candidates.add(pos)
        elif skill.shape == "multishot":
            candidates |= {enemy.pos for enemy in enemies}
        elif skill.shape == "cross":
            candidates.add(caster.pos)
        elif skill.shape in ("strip", "cone"):
            for enemy in enemies:
                direction = self.direction_from_to(caster.pos, enemy.pos)
                if direction == (0, 0):
                    continue
                candidates.add((caster.pos[0] + direction[0] * max(1, skill.range_max), caster.pos[1] + direction[1] * max(1, skill.range_max)))
                candidates.add(enemy.pos)
        else:
            candidates |= {enemy.pos for enemy in enemies}

        # Include barrel centers if the skill can splash them, but avoid scanning the
        # whole map unless the skill actually has area damage.
        if skill.aoe_radius > 0:
            for y, row in enumerate(self.map):
                for x, tile in enumerate(row):
                    if tile == TILE_BARREL:
                        candidates.add((x, y))

        filtered = {pos for pos in candidates if pos in in_range and self.in_bounds(pos)}
        return filtered

    def best_follower_skill_action(self, follower: Unit):
        best = None
        danger = self.enemy_danger_tiles()
        follower_in_danger = follower.pos in danger

        for skill in self.available_skills(follower):
            if follower.mp < skill.mp_cost:
                continue
            if skill.effect == "transfer_ap":
                # Coordinate is intended as player-directed AP transfer to the companion.
                continue

            if skill.effect in ("heal", "restore_mp", "cleanse", "guard"):
                # Ally-list support skills should not scan every tile on the map.
                for ally in self.support_targets_for_skill(follower, skill):
                    score = -999

                    if skill.effect == "heal":
                        if ally.hp >= ally.max_hp:
                            continue
                        total_missing = ally.max_hp - ally.hp
                        low_hp_bonus = 30 if ally.hp <= ally.max_hp * 0.45 else 0
                        self_bonus_penalty = 10 if ally is follower else 0
                        combo_bonus = self.skill_combo_heal_bonus(follower, ally, skill)
                        score = (total_missing + combo_bonus) * 7 + low_hp_bonus - self_bonus_penalty
                        if combo_bonus:
                            score += 18

                    elif skill.effect == "restore_mp":
                        if ally.mp >= ally.max_mp:
                            continue
                        missing_mp = ally.max_mp - ally.mp
                        # MP restoration is most useful for active/manual heroes and Aria-like casters.
                        active_bonus = 12 if not ally.ai_controlled else 4
                        score = missing_mp * 8 + active_bonus

                    elif skill.effect == "cleanse":
                        status_count = int(ally.poison > 0) + int(ally.rooted > 0) + int(ally.vulnerable > 0)
                        if status_count <= 0:
                            continue
                        low_hp_bonus = 10 if ally.hp <= ally.max_hp * 0.5 else 0
                        score = status_count * 32 + low_hp_bonus

                    elif skill.effect == "guard":
                        if ally.guard:
                            continue
                        ally_in_danger = ally.pos in danger
                        low_hp_bonus = 22 if ally.hp <= ally.max_hp * 0.5 else 0
                        score = (35 if ally_in_danger else 8) + low_hp_bonus

                    score -= skill.mp_cost * 5
                    if self.follower_tactic == "Support":
                        score += 18
                    elif self.follower_tactic == "Cautious":
                        score += 8

                    candidate = ("skill", skill, ally.pos, [ally], score)
                    if best is None or score > best[4]:
                        best = candidate
                continue

            for center in self.ai_skill_candidate_centers(follower, skill):
                targets = self.skill_targets(follower, center, skill)
                if not targets:
                    continue

                projected_damages = [skill.damage + self.skill_combo_damage_bonus(follower, e, skill) for e in targets]
                combo_hits = sum(1 for e in targets if self.skill_combo_triggered(follower, e, skill))
                kills = sum(1 for e, dmg_value in zip(targets, projected_damages) if e.hp <= dmg_value)
                total_damage = sum(min(dmg_value, e.hp) for e, dmg_value in zip(targets, projected_damages))
                overkill_waste = sum(max(0, dmg_value - e.hp) for e, dmg_value in zip(targets, projected_damages))
                status_bonus = 0
                if skill.status == "poison":
                    status_bonus = sum(18 for e in targets if e.poison <= 0)
                elif skill.status == "root":
                    status_bonus = sum(16 for e in targets if e.rooted <= 0)
                elif skill.status == "vulnerable":
                    status_bonus = sum(14 for e in targets if e.vulnerable <= 0)
                danger_penalty = 2 if follower_in_danger else 0
                score = (
                    kills * 100
                    + total_damage * 5
                    + len(targets) * 10
                    + status_bonus
                    + combo_hits * 22
                    + (skill.combo_ap_gain + skill.combo_mp_gain) * 8 * combo_hits
                    - skill.mp_cost * 5
                    - overkill_waste
                    - danger_penalty
                )

                candidate = ("skill", skill, center, targets, score)
                if best is None or score > best[4]:
                    best = candidate
        return best

    def best_follower_move(self, follower: Unit) -> Optional[Pos]:
        reachable = list(self.reachable_tiles(follower).keys())
        if not reachable:
            return None

        danger = self.enemy_danger_tiles()
        enemies = self.enemies_alive()
        if not enemies:
            return follower.pos

        primary_target = max(
            enemies,
            key=lambda e: (
                1 if e.hp <= follower.weapon.damage else 0,
                min(follower.weapon.damage, e.hp),
                -self.ai_progress_to_attack_band(follower, follower.pos, e),
                -e.hp,
            ),
        )
        current_progress = self.ai_progress_to_attack_band(follower, follower.pos, primary_target)

        def tile_score(pos: Pos) -> Tuple[int, int, int, int, int, int, int]:
            attack_targets = [
                e for e in enemies
                if follower.weapon.range_min <= manhattan(pos, e.pos) <= follower.weapon.range_max
            ]
            attack_score = 0
            kill_score = 0
            if attack_targets:
                best_target = max(attack_targets, key=lambda e: (e.hp <= follower.weapon.damage, min(follower.weapon.damage, e.hp), -e.hp))
                attack_score = min(follower.weapon.damage, best_target.hp) * 7
                kill_score = 45 if best_target.hp <= follower.weapon.damage else 0

            nearest_enemy_dist = min(manhattan(pos, e.pos) for e in enemies)
            preferred_distance = min(max(1, follower.weapon.range_max), 3)
            distance_score = -abs(nearest_enemy_dist - preferred_distance)
            danger_penalty = 45 if self.follower_tactic in ("Cautious", "Support") else 25
            safety = -danger_penalty if pos in danger else 0
            terrain = self.terrain_score_for_unit(follower, pos, cautious=self.follower_tactic in ("Cautious", "Support"))
            progress = self.ai_movement_progress_bonus(follower, pos, primary_target)

            return (
                attack_score + kill_score,
                progress,
                safety,
                terrain - self.movement_cost(pos),
                self.congestion_escape_bonus(follower, pos),
                distance_score,
                -manhattan(follower.pos, pos),
            )

        best = max(reachable, key=tile_score)
        if best == follower.pos and current_progress > 0:
            alternatives = [p for p in reachable if p != follower.pos]
            if alternatives:
                best_alt = max(alternatives, key=tile_score)
                if self.ai_progress_to_attack_band(follower, best_alt, primary_target) < current_progress or tile_score(best_alt)[1] > -10:
                    best = best_alt
        return best

    def follower_use_potion(self, follower: Unit, events: List[str]) -> None:
        if follower.inventory.get("Potion", 0) <= 0:
            return
        follower.inventory["Potion"] -= 1
        self.combat_stats["potions_used"] += 1
        self.combat_stats["items_used"] = self.combat_stats.get("items_used", 0) + 1
        self.bump_stat_dict("item_usage", "Potion", 1)
        heal = min(14, follower.max_hp - follower.hp)
        follower.hp += heal
        follower.guard = False
        follower.action_points -= 1
        events.append(f"{follower.name} drinks Potion +{heal}")
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)

    def follower_attack(self, follower: Unit, target: Unit, events: List[str]) -> None:
        if not target.alive:
            return
        self.clear_overwatch_for_unit(follower)
        self.flash_effect([target.pos], "hit")
        raw_damage = self.apply_cover_reduction(follower.pos, target, follower.weapon.damage)
        dmg = target.take_damage(raw_damage)
        self.combat_stats["follower_damage"] += dmg
        self.record_actor_damage(follower, dmg)
        follower.guard = False
        follower.action_points -= 1
        msg = f"{follower.name}->{target.name} {dmg}"
        if not target.alive:
            msg += " KO"
            self.award_xp(follower, target)
        events.append(msg)
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)

    def follower_cast_skill(self, follower: Unit, skill: Skill, center: Pos, targets: List[Unit], events: List[str]) -> None:
        if follower.mp < skill.mp_cost:
            return
        self.clear_overwatch_for_unit(follower)
        follower.mp -= skill.mp_cost
        self.combat_stats["skills_used"] += 1
        self.record_skill_use(follower, skill)
        self.record_build_synergy_use(follower, skill)
        follower.guard = False
        follower.action_points -= 1

        if skill.effect in ("heal", "restore_mp", "cleanse", "guard"):
            self.flash_effect([unit.pos for unit in targets], self.skill_effect_kind(skill))
            parts = []
            for ally in list(targets):
                if not ally.alive:
                    continue
                if skill.effect == "heal":
                    if ally.hp >= ally.max_hp:
                        continue
                    combo_bonus = self.skill_combo_heal_bonus(follower, ally, skill)
                    heal = min(skill.heal_amount + combo_bonus, ally.max_hp - ally.hp)
                    ally.hp += heal
                    parts.append(f"{ally.name} +{heal} HP" + (" combo" if combo_bonus else ""))
                    combo_result = self.apply_skill_combo_rewards(follower, skill, 1 if combo_bonus else 0)
                    if combo_result:
                        parts.append(combo_result)
                elif skill.effect == "restore_mp":
                    if ally.mp >= ally.max_mp:
                        continue
                    gain = min(skill.mp_amount, ally.max_mp - ally.mp)
                    ally.mp += gain
                    parts.append(f"{ally.name} +{gain} MP")
                elif skill.effect == "cleanse":
                    if not (ally.poison > 0 or ally.rooted > 0 or ally.vulnerable > 0):
                        continue
                    ally.poison = 0
                    ally.rooted = 0
                    ally.vulnerable = 0
                    parts.append(f"{ally.name} cleansed")
                elif skill.effect == "guard":
                    if ally.guard:
                        continue
                    ally.guard = True
                    parts.append(f"{ally.name} guarding")
            if parts:
                events.append(f"{follower.name} uses {skill.name}: " + ", ".join(parts))
            else:
                events.append(f"{follower.name} uses {skill.name}, but it had no effect")
            self.render()
            if self.frame_delay > 0:
                time.sleep(self.frame_delay)
            return

        self.flash_effect(self.skill_affected_tiles(follower.pos, center, skill), self.skill_effect_kind(skill), frames=2 if skill.aoe_radius > 0 or skill.shape in ("burst", "cone", "strip") else 1)
        parts = []
        combo_triggers = 0
        for enemy in list(targets):
            if not enemy.alive:
                continue
            combo_bonus = self.skill_combo_damage_bonus(follower, enemy, skill)
            triggered = combo_bonus > 0 or (self.skill_combo_triggered(follower, enemy, skill) and (skill.combo_ap_gain or skill.combo_mp_gain))
            if triggered:
                combo_triggers += 1
            dmg = enemy.take_damage(skill.damage + combo_bonus)
            self.apply_skill_status(enemy, skill)
            self.combat_stats["follower_damage"] += dmg
            self.record_actor_damage(follower, dmg)
            part = f"{enemy.name} {dmg}"
            if combo_bonus:
                part += " combo"
            if skill.status:
                part += f" +{skill.status}"
            if not enemy.alive:
                part += " KO"
                self.award_xp(follower, enemy)
            parts.append(part)

        combo_result = self.apply_skill_combo_rewards(follower, skill, combo_triggers)
        if combo_result:
            parts.append(combo_result)
        zone = self.create_skill_zone(follower, skill, center, self.skill_affected_tiles(follower.pos, center, skill))
        if zone:
            parts.append(f"{zone.kind} zone {zone.duration}t")

        events.append(f"{follower.name} uses {skill.name}: " + ", ".join(parts))
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)

    def follower_set_overwatch(
        self,
        follower: Unit,
        option: Dict[str, object],
        target: Pos,
        tiles: Set[Pos],
        predicted_targets: List[Unit],
        events: List[str],
    ) -> None:
        if follower.action_points <= 0:
            return
        self.clear_overwatch_for_unit(follower)
        action = OverwatchAction(
            owner=follower,
            kind=str(option.get("kind", "weapon")),
            name=str(option.get("label", "Overwatch")),
            target=target,
            tiles=set(tiles),
            skill_index=int(option["skill_index"]) if option.get("kind") == "skill" else None,
        )
        self.overwatch_actions.append(action)
        follower.guard = False
        follower.action_points -= 1
        watched = ", ".join(enemy.name for enemy in predicted_targets[:3]) if predicted_targets else "approach"
        events.append(f"{follower.name} overwatches with {action.name} vs {watched}")
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)

    def enemy_ap_budget(self, enemy: Unit) -> int:
        """Enemy action budget for this turn.

        Extra AP is used mainly for movement + action. Offensive actions end the
        enemy's sequence, so 2 AP enemies do not simply double-tap every round.
        """
        return ai_helpers.enemy_ap_budget(enemy)

    def enemy_action_ends_sequence(self, kind: str) -> bool:
        # Movement can be followed by an action. Actual attacks/specials end the
        # sequence to avoid frustrating attack spam from high-AP enemies.
        return ai_helpers.enemy_action_ends_sequence(kind)

    def enemy_action_cost(self, enemy: Unit, kind: str) -> int:
        return ai_helpers.enemy_action_cost(enemy, kind)

    # Enemy turn execution lives in combat.turns; this delegate keeps the public Game API stable.
    def enemy_turn(self) -> None:
        turn_helpers.run_enemy_turn(self)

    def enemy_family(self, enemy: Unit) -> str:
        try:
            from ascii_farmstead_custom_extended import custom_enemy_behavior_family

            return custom_enemy_behavior_family(enemy.name)
        except (ImportError, OSError, TypeError, ValueError):
            return self.enemy_base_name(enemy.name)

    def nearby_enemy_family_count(self, enemy: Unit, family: str, radius: int = 3) -> int:
        return sum(
            1 for other in self.enemies_alive()
            if other is not enemy and self.enemy_family(other) == family and manhattan(other.pos, enemy.pos) <= radius
        )

    def hero_is_isolated(self, hero: Unit) -> bool:
        return all(other is hero or manhattan(other.pos, hero.pos) > 2 for other in self.heroes_alive())

    def best_pack_pounce(self, enemy: Unit):
        if enemy.cooldowns.get("Pack Pounce", 0) > 0:
            return None
        if self.enemy_family(enemy) != "Wolf":
            return None
        targets = [hero for hero in self.attack_targets_for_enemy(enemy) if hero.alive]
        if not targets:
            return None
        pack_bonus = min(3, self.nearby_enemy_family_count(enemy, "Wolf", radius=4))
        best = None
        for hero in targets:
            isolated_bonus = 2 if self.hero_is_isolated(hero) else 0
            status_bonus = 2 if (hero.poison > 0 or hero.rooted > 0 or hero.vulnerable > 0) else 0
            damage = 4 + pack_bonus + isolated_bonus + status_bonus
            score = self.enemy_target_score(enemy, hero) + damage * 7
            if self.hero_is_isolated(hero):
                score += 18
            if hero.hp <= damage:
                score += 45
            candidate = ("pack_pounce", hero, damage, score)
            if best is None or score > best[3]:
                best = candidate
        if best and best[3] >= 35:
            return ("pack_pounce", best[1], best[2])
        return None

    def best_crow_harry(self, enemy: Unit):
        if enemy.cooldowns.get("Harrier Dive", 0) > 0:
            return None
        if self.enemy_family(enemy) != "Crow":
            return None
        targets = self.attack_targets_for_enemy(enemy)
        if not targets:
            return None
        best_target = max(
            targets,
            key=lambda hero: (
                self.enemy_target_score(enemy, hero),
                1 if hero.hp <= hero.max_hp * 0.5 else 0,
                -hero.hp,
            ),
        )
        retreat = self.best_retreat_tile(enemy, best_target)
        if retreat and retreat != enemy.pos:
            return ("harry", best_target, retreat)
        return None

    def best_spore_patch(self, enemy: Unit):
        if enemy.cooldowns.get("Spore Patch", 0) > 0:
            return None
        if self.enemy_family(enemy) != "Sporeling":
            return None
        best = None
        for y in range(max(0, enemy.pos[1] - 4), min(self.map_height_tiles(), enemy.pos[1] + 5)):
            for x in range(max(0, enemy.pos[0] - 4), min(self.map_width_tiles(), enemy.pos[0] + 5)):
                center = (x, y)
                if manhattan(enemy.pos, center) > 4:
                    continue
                targets = [h for h in self.heroes_alive() if h.pos in self.aoe_tiles(center, 1)]
                if not targets:
                    continue
                patch_tiles = [p for p in self.aoe_tiles(center, 1) if self.tile_at(p) in (TILE_FLOOR, TILE_GRASS)]
                score = (
                    len(targets) * 22
                    + sum(1 for h in targets if h.poison <= 0) * 10
                    + sum(1 for h in targets if h.vulnerable <= 0) * 8
                    + len(patch_tiles) * 2
                )
                if best is None or score > best[4]:
                    best = ("spore_patch", center, targets, patch_tiles, score)
        if best and (len(best[2]) >= 2 or best[4] >= 34):
            return ("spore_patch", best[1], best[2], best[3])
        return None

    def best_briar_bloom(self, enemy: Unit):
        if not (enemy.boss or self.enemy_family(enemy) == "Old Briarthorn"):
            return None
        if enemy.cooldowns.get("Briar Bloom", 0) > 0:
            return None
        # Below 70% HP it starts shaping the battlefield; below 40% it gets aggressive.
        if enemy.hp > enemy.max_hp * 0.70 and self.round_no < 4:
            return None

        best = None
        for hero in self.heroes_alive():
            if manhattan(enemy.pos, hero.pos) > 5:
                continue
            tiles = self.aoe_tiles(hero.pos, 1)
            targets = [h for h in self.heroes_alive() if h.pos in tiles]
            thorn_tiles = [p for p in tiles if self.tile_at(p) in (TILE_FLOOR, TILE_GRASS, TILE_MUD)]
            score = len(targets) * 28 + len(thorn_tiles) * 3 + sum(1 for h in targets if h.rooted <= 0) * 8
            if enemy.hp <= enemy.max_hp * 0.40:
                score += 14
            candidate = ("briar_bloom", hero.pos, targets, thorn_tiles, score)
            if best is None or score > best[4]:
                best = candidate
        if best and best[4] >= 35:
            return ("briar_bloom", best[1], best[2], best[3])
        return None

    def elite_drive_action(self, enemy: Unit):
        if not enemy.elite:
            return None
        if enemy.cooldowns.get("Elite Drive", 0) > 0:
            return None
        if enemy.hp > enemy.max_hp * 0.60 and enemy.vulnerable <= 0 and enemy.rooted <= 0:
            return None
        return ("elite_drive",)

    def best_needle_dash(self, enemy: Unit):
        if self.enemy_family(enemy) != "Razor Hare" or enemy.cooldowns.get("Needle Dash", 0) > 0:
            return None
        best = None
        reachable = self.reachable_tiles(enemy)
        for hero in self.heroes_alive():
            if manhattan(enemy.pos, hero.pos) > 6:
                continue
            landings = [p for p in neighbors4(hero.pos) if p in reachable and self.is_walkable(p, ignore=enemy)]
            if not landings:
                continue
            destination = min(landings, key=lambda p: (self.enemy_overwatch_risk(enemy, p), manhattan(enemy.pos, p)))
            damage = 4 + (1 if hero.vulnerable > 0 or self.hero_is_isolated(hero) else 0)
            score = self.enemy_target_score(enemy, hero) + damage * 6 + (14 if self.hero_is_isolated(hero) else 0)
            if hero.hp <= damage:
                score += 45
            candidate = ("needle_dash", hero, destination, damage, score)
            if best is None or score > best[4]:
                best = candidate
        if best and best[4] >= 28:
            return ("needle_dash", best[1], best[2], best[3])
        return None

    def best_cinder_toss(self, enemy: Unit):
        if self.enemy_family(enemy) != "Ember Imp" or enemy.cooldowns.get("Cinder Toss", 0) > 0:
            return None
        best = None
        for y in range(max(0, enemy.pos[1] - 5), min(self.map_height_tiles(), enemy.pos[1] + 6)):
            for x in range(max(0, enemy.pos[0] - 5), min(self.map_width_tiles(), enemy.pos[0] + 6)):
                center = (x, y)
                if manhattan(enemy.pos, center) > 5:
                    continue
                tiles = self.aoe_tiles(center, 1)
                targets = [h for h in self.heroes_alive() if h.pos in tiles]
                barrels = self.barrel_tiles_in(tiles)
                if not targets and not barrels:
                    continue
                score = len(targets) * 24 + len(barrels) * 16 + sum(1 for h in targets if h.vulnerable <= 0) * 6
                if any(h.hp <= 3 for h in targets):
                    score += 30
                candidate = ("cinder_toss", center, targets, barrels, score)
                if best is None or score > best[4]:
                    best = candidate
        if best and best[4] >= 24:
            return ("cinder_toss", best[1], best[2], best[3])
        return None

    def best_frost_cloud(self, enemy: Unit):
        if self.enemy_family(enemy) != "Frost Moth" or enemy.cooldowns.get("Frost Cloud", 0) > 0:
            return None
        best = None
        for hero in self.heroes_alive():
            if manhattan(enemy.pos, hero.pos) > 5:
                continue
            tiles = self.aoe_tiles(hero.pos, 1)
            targets = [h for h in self.heroes_alive() if h.pos in tiles]
            ice_tiles = [p for p in tiles if self.tile_at(p) in (TILE_FLOOR, TILE_DIRT, TILE_GRASS, TILE_MUD)]
            score = len(targets) * 24 + sum(1 for h in targets if h.rooted <= 0) * 10 + len(ice_tiles) * 2
            if len(targets) >= 2:
                score += 14
            candidate = ("frost_cloud", hero.pos, targets, ice_tiles, score)
            if best is None or score > best[4]:
                best = candidate
        if best and best[4] >= 30:
            return ("frost_cloud", best[1], best[2], best[3])
        return None

    def best_burrow_ambush(self, enemy: Unit):
        if self.enemy_family(enemy) != "Burrower" or enemy.cooldowns.get("Burrow Ambush", 0) > 0:
            return None
        best = None
        for hero in self.heroes_alive():
            if manhattan(enemy.pos, hero.pos) > 7:
                continue
            landings = [p for p in neighbors4(hero.pos) if self.is_walkable(p, ignore=enemy)]
            if not landings:
                continue
            # Burrowing ignores normal path distance but still avoids terrible overwatch landings.
            destination = min(landings, key=lambda p: (self.enemy_overwatch_risk(enemy, p), manhattan(p, enemy.pos)))
            damage = 5 + (1 if hero.vulnerable > 0 else 0)
            score = self.enemy_target_score(enemy, hero) + damage * 7 + (18 if hero.hp <= hero.max_hp * 0.5 else 0)
            if hero.hp <= damage:
                score += 50
            candidate = ("burrow_ambush", hero, destination, damage, score)
            if best is None or score > best[4]:
                best = candidate
        if best and best[4] >= 22:
            return ("burrow_ambush", best[1], best[2], best[3])
        return None

    def best_quill_volley(self, enemy: Unit):
        if self.enemy_family(enemy) != "Thornback" or enemy.cooldowns.get("Quill Volley", 0) > 0:
            return None
        best = None
        for hero in self.heroes_alive():
            if manhattan(enemy.pos, hero.pos) > 4:
                continue
            tiles = self.aoe_tiles(hero.pos, 1)
            targets = [h for h in self.heroes_alive() if h.pos in tiles]
            if not targets:
                continue
            score = len(targets) * 22 + sum(1 for h in targets if h.vulnerable <= 0) * 9
            if any(h.hp <= 3 for h in targets):
                score += 25
            candidate = ("quill_volley", hero.pos, targets, score)
            if best is None or score > best[3]:
                best = candidate
        if best and (len(best[2]) >= 2 or best[3] >= 36):
            return ("quill_volley", best[1], best[2])
        return None

    def best_ooze_mire(self, enemy: Unit):
        if self.enemy_family(enemy) not in ("Slime", "Marsh Toad") or enemy.cooldowns.get("Ooze Mire", 0) > 0:
            return None
        best = None
        for hero in self.heroes_alive():
            if manhattan(enemy.pos, hero.pos) > 4:
                continue
            center = hero.pos
            tiles = self.aoe_tiles(center, 1)
            targets = [h for h in self.heroes_alive() if h.pos in tiles]
            mire_tiles = [p for p in tiles if self.in_bounds(p) and self.tile_at(p) in PASSABLE]
            if not mire_tiles:
                continue
            score = len(targets) * 22 + sum(1 for h in targets if h.poison <= 0) * 10 + len(mire_tiles) * 2
            if any(h.hp <= 4 for h in targets):
                score += 20
            candidate = ("ooze_mire", center, targets, mire_tiles, score)
            if best is None or score > best[4]:
                best = candidate
        if best and best[4] >= 24:
            return ("ooze_mire", best[1], best[2], best[3])
        return None

    def best_shield_wall(self, enemy: Unit):
        if self.enemy_family(enemy) not in ("Shield Guard", "Rockback", "Thornback") or enemy.cooldowns.get("Shield Wall", 0) > 0:
            return None
        allies = [
            ally for ally in self.enemies_alive()
            if manhattan(enemy.pos, ally.pos) <= 2 and (not ally.guard or ally.vulnerable > 0 or ally.hp <= ally.max_hp * 0.55)
        ]
        if enemy not in allies:
            allies.append(enemy)
        if len(allies) < 2 and enemy.hp > enemy.max_hp * 0.45 and enemy.vulnerable <= 0:
            return None
        score = len(allies) * 12 + sum(8 for ally in allies if ally.vulnerable > 0) + sum(8 for ally in allies if ally.hp <= ally.max_hp * 0.55)
        if score >= 18:
            return ("shield_wall", allies[:4])
        return None

    def best_phase_shot(self, enemy: Unit):
        if self.enemy_family(enemy) != "Wisp" or enemy.cooldowns.get("Phase Shot", 0) > 0:
            return None
        targets = self.heroes_alive()
        if not targets:
            return None
        reachable = [p for p in self.reachable_tiles(enemy) if self.is_walkable(p, ignore=enemy)]
        if not reachable:
            return None
        best = None
        for hero in targets:
            candidate_tiles = [p for p in reachable if 2 <= manhattan(p, hero.pos) <= 4]
            if not candidate_tiles:
                continue
            dest = max(candidate_tiles, key=lambda p: (self.cover_score_for_enemy_tile(p), min(manhattan(p, h.pos) for h in targets), -self.enemy_overwatch_risk(enemy, p)))
            score = self.enemy_target_score(enemy, hero) + (18 if hero.rooted <= 0 else 0) + (15 if manhattan(enemy.pos, hero.pos) <= 2 else 0)
            if hero.hp <= 3:
                score += 40
            candidate = ("phase_shot", dest, hero, score)
            if best is None or score > best[3]:
                best = candidate
        if best and best[3] >= 28:
            return ("phase_shot", best[1], best[2])
        return None

    def best_briar_heart(self, enemy: Unit):
        if not (enemy.boss or self.enemy_family(enemy) == "Old Briarthorn"):
            return None
        if enemy.cooldowns.get("Briar Heart", 0) > 0:
            return None
        if enemy.hp > enemy.max_hp * 0.55:
            return None
        tiles = [p for p in self.aoe_tiles(enemy.pos, 1) if self.in_bounds(p) and self.tile_at(p) in PASSABLE]
        if not tiles:
            return None
        return ("briar_heart", tiles)

    def choose_enemy_action(self, enemy: Unit):
        elite_drive = self.elite_drive_action(enemy)
        if elite_drive:
            return elite_drive

        heart = self.best_briar_heart(enemy)
        if heart:
            return heart

        # Boss signature behavior should compete with barrel play, not be hidden behind it.
        if enemy.role == "boss":
            bloom = self.best_briar_bloom(enemy)
            if bloom:
                return bloom

        # High-identity specials get first chance.
        for special_picker in (
            self.best_needle_dash,
            self.best_cinder_toss,
            self.best_frost_cloud,
            self.best_burrow_ambush,
            self.best_quill_volley,
            self.best_phase_shot,
            self.best_ooze_mire,
            self.best_shield_wall,
        ):
            special = special_picker(enemy)
            if special:
                return special

        barrel_action = self.best_barrel_attack(enemy, "hero", threshold=26)
        if barrel_action:
            return barrel_action

        if enemy.role == "skirmisher":
            return self.choose_crow_action(enemy)
        if enemy.role == "brute":
            return self.choose_boar_action(enemy)
        if enemy.role == "controller":
            return self.choose_vine_action(enemy)
        if enemy.role == "ranged":
            return self.choose_ranged_action(enemy)
        if enemy.role == "pouncer":
            return self.choose_pouncer_action(enemy)
        if enemy.role == "guardian":
            return self.choose_guardian_action(enemy)
        if enemy.role == "blighter":
            return self.choose_blighter_action(enemy)
        if enemy.role == "boss":
            return self.choose_boss_action(enemy)

        attack = self.best_enemy_attack(enemy)
        if attack:
            return ("attack", attack)
        target = self.enemy_best_target(enemy)
        move = self.best_enemy_move(enemy, target) if target else None
        return ("move", move) if move else None


    def estimated_attack_damage(self, attacker: Unit, target: Unit, base_damage: Optional[int] = None) -> int:
        damage = attacker.weapon.damage if base_damage is None else base_damage
        damage = self.apply_cover_reduction(attacker.pos, target, damage)
        if target.vulnerable > 0:
            damage += 1
        if getattr(target, "defense", 0) > 0:
            damage = max(1, damage - int(getattr(target, "defense", 0)))
        if target.guard:
            damage = max(1, damage // 2)
        return max(1, damage)

    def enemy_target_score(self, enemy: Unit, hero: Unit) -> int:
        return ai_helpers.enemy_target_score(
            enemy,
            hero,
            self.heroes_alive(),
            self.estimated_attack_damage(enemy, hero),
        )

    def enemy_best_target(self, enemy: Unit) -> Optional[Unit]:
        heroes = self.heroes_alive()
        if not heroes:
            return None
        return max(heroes, key=lambda hero: self.enemy_target_score(enemy, hero))

    def attack_targets_for_enemy(self, enemy: Unit) -> List[Unit]:
        return [hero for hero in self.heroes_alive() if self.can_attack(enemy, hero)]

    def best_enemy_attack(self, enemy: Unit) -> Optional[Unit]:
        targets = self.attack_targets_for_enemy(enemy)
        if not targets:
            return None
        return max(
            targets,
            key=lambda hero: (
                1 if hero.hp <= self.estimated_attack_damage(enemy, hero) else 0,
                self.enemy_target_score(enemy, hero),
                -hero.hp,
            ),
        )

    def best_poison_target(self, enemy: Unit) -> Optional[Unit]:
        targets = [
            hero for hero in self.attack_targets_for_enemy(enemy)
            if hero.poison <= 0 and hero.alive
        ]
        if not targets:
            return None
        return max(
            targets,
            key=lambda hero: (
                1 if hero.hp <= enemy.max_hp else 0,
                self.enemy_target_score(enemy, hero) + (10 if hero.hp > self.estimated_attack_damage(enemy, hero, 2) else -15),
            ),
        )

    def best_root_target(self, enemy: Unit) -> Optional[Unit]:
        candidates = [
            hero for hero in self.heroes_alive()
            if hero.rooted <= 0 and manhattan(enemy.pos, hero.pos) <= 4
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda hero: (
                hero.action_points,
                1 if not hero.ai_controlled else 0,
                self.enemy_target_score(enemy, hero),
            ),
        )

    def choose_ranged_action(self, enemy: Unit):
        target = self.enemy_best_target(enemy)
        if not target:
            return None

        closest = self.closest_hero(enemy.pos)
        if closest and manhattan(enemy.pos, closest.pos) <= 1 and enemy.cooldowns.get("Evasive Hop", 0) <= 0:
            retreat = self.best_retreat_tile(enemy, closest)
            if retreat and retreat != enemy.pos:
                return ("retreat", retreat)

        attack = self.best_enemy_attack(enemy)
        if attack:
            return ("attack", attack)

        move = self.best_enemy_move(enemy, target, preferred_min=enemy.weapon.range_min, preferred_max=enemy.weapon.range_max, cautious=True)
        return ("move", move) if move else None

    def choose_pouncer_action(self, enemy: Unit):
        target = self.enemy_best_target(enemy)
        if not target:
            return None

        pounce = self.best_pack_pounce(enemy)
        if pounce:
            return pounce

        if enemy.hp <= enemy.max_hp * 0.35 and enemy.cooldowns.get("Evasive Hop", 0) <= 0:
            threat = self.closest_hero(enemy.pos)
            if threat:
                retreat = self.best_retreat_tile(enemy, threat)
                if retreat and retreat != enemy.pos:
                    return ("retreat", retreat)

        attack = self.best_enemy_attack(enemy)
        if attack:
            return ("attack", attack)

        move = self.best_enemy_move(enemy, target, preferred_min=1, preferred_max=1, cautious=True)
        return ("move", move) if move else None

    def choose_guardian_action(self, enemy: Unit):
        target = self.enemy_best_target(enemy)
        if not target:
            return None

        wall = self.best_shield_wall(enemy)
        if wall:
            return wall

        attack = self.best_enemy_attack(enemy)
        if attack:
            if enemy.cooldowns.get("War Cry", 0) <= 0 and attack.vulnerable <= 0 and attack.hp > self.estimated_attack_damage(enemy, attack) + 2:
                return ("intimidate", attack)
            return ("attack", attack)

        move = self.best_enemy_move(enemy, target, preferred_min=1, preferred_max=1, cautious=False)
        return ("move", move) if move else None


    def choose_blighter_action(self, enemy: Unit):
        target = self.enemy_best_target(enemy)
        if not target:
            return None

        mire = self.best_ooze_mire(enemy)
        if mire:
            return mire

        poison = self.best_poison_target(enemy)
        if poison and enemy.cooldowns.get("Poison Claw", 0) <= 0:
            return ("poison", poison)

        attack = self.best_enemy_attack(enemy)
        if attack:
            return ("attack", attack)

        move = self.best_enemy_move(enemy, target, preferred_min=enemy.weapon.range_min, preferred_max=enemy.weapon.range_max, cautious=True)
        return ("move", move) if move else None


    def choose_boss_action(self, enemy: Unit):
        target = self.enemy_best_target(enemy)
        if not target:
            return None

        # Boss prioritizes visible control patterns over raw double-attacks.
        bloom = self.best_briar_bloom(enemy)
        if bloom:
            return bloom

        if enemy.cooldowns.get("Toxic Burst", 0) <= 0:
            spore = self.best_spore_burst(enemy)
            if spore:
                return spore

        if enemy.cooldowns.get("Binding Roots", 0) <= 0:
            root_target = self.best_root_target(enemy)
            if root_target:
                return ("root", root_target)

        attack = self.best_enemy_attack(enemy)
        if attack:
            if enemy.cooldowns.get("War Cry", 0) <= 0 and attack.vulnerable <= 0:
                return ("intimidate", attack)
            return ("attack", attack)

        move = self.best_enemy_move(enemy, target, preferred_min=1, preferred_max=3, cautious=False)
        return ("move", move) if move else None

    def choose_crow_action(self, enemy: Unit):
        target = self.enemy_best_target(enemy)
        if not target:
            return None

        harry = self.best_crow_harry(enemy)
        if harry:
            return harry

        # If hurt, the skirmisher tries to disengage before trading.
        if enemy.hp <= enemy.max_hp * 0.45 and enemy.cooldowns.get("Evasive Hop", 0) <= 0:
            threat = self.closest_hero(enemy.pos)
            if threat:
                retreat = self.best_retreat_tile(enemy, threat)
                if retreat and retreat != enemy.pos:
                    return ("retreat", retreat)

        poison = self.best_poison_target(enemy)
        if poison and enemy.cooldowns.get("Poison Claw", 0) <= 0:
            return ("poison", poison)

        attack = self.best_enemy_attack(enemy)
        if attack:
            return ("attack", attack)

        move = self.best_enemy_move(enemy, target, preferred_min=enemy.weapon.range_min, preferred_max=enemy.weapon.range_max, cautious=True)
        return ("move", move) if move else None

    def best_charge_action(self, enemy: Unit):
        if enemy.cooldowns.get("Brutal Charge", 0) > 0:
            return None
        best = None
        for hero in self.heroes_alive():
            destination = self.best_charge_destination(enemy, hero)
            if not destination:
                continue
            damage = 6 + (1 if hero.vulnerable > 0 else 0)
            score = self.enemy_target_score(enemy, hero) + damage * 5
            if hero.hp <= damage:
                score += 45
            # Boar is less afraid of overwatch, but it still avoids clearly bad charges when not lethal.
            risk = self.enemy_overwatch_risk(enemy, destination)
            if risk and hero.hp > damage:
                score -= 12
            candidate = ("charge", hero, destination, score)
            if best is None or score > best[3]:
                best = candidate
        if best and best[3] >= 25:
            return ("charge", best[1], best[2])
        return None

    def choose_boar_action(self, enemy: Unit):
        target = self.enemy_best_target(enemy)
        if not target:
            return None

        wall = self.best_shield_wall(enemy)
        if wall:
            return wall

        # Attack immediately if a kill is available; don't waste the turn on War Cry.
        attack = self.best_enemy_attack(enemy)
        if attack and attack.hp <= self.estimated_attack_damage(enemy, attack):
            return ("attack", attack)

        charge = self.best_charge_action(enemy)
        if charge:
            return charge

        attack = self.best_enemy_attack(enemy)
        if attack:
            # War Cry is now a setup action: use it on healthy, non-vulnerable targets,
            # not when a normal attack would nearly finish them.
            if (
                enemy.cooldowns.get("War Cry", 0) <= 0
                and attack.vulnerable <= 0
                and attack.hp > self.estimated_attack_damage(enemy, attack) + 3
            ):
                return ("intimidate", attack)
            return ("attack", attack)

        move = self.best_enemy_move(enemy, target, preferred_min=1, preferred_max=1, cautious=False)
        return ("move", move) if move else None

    def choose_vine_action(self, enemy: Unit):
        spore_patch = self.best_spore_patch(enemy)
        if spore_patch:
            return spore_patch

        # Prefer a multi-target spore if possible.
        if enemy.cooldowns.get("Toxic Burst", 0) <= 0:
            spore = self.best_spore_burst(enemy)
            if spore:
                return spore

        root_target = None
        if enemy.cooldowns.get("Binding Roots", 0) <= 0:
            root_target = self.best_root_target(enemy)
            if root_target:
                return ("root", root_target)

        attack = self.best_enemy_attack(enemy)
        if attack:
            return ("attack", attack)

        target = self.enemy_best_target(enemy)
        if not target:
            return None

        # Controller prefers a tile that keeps targets at thorn range.
        move = self.best_controller_move(enemy, target)
        return ("move", move) if move else None

    def enemy_basic_attack(self, enemy: Unit, target: Unit, events: List[str]) -> None:
        self.flash_effect([target.pos], "hit")
        raw_damage = self.apply_cover_reduction(enemy.pos, target, enemy.weapon.damage)
        dmg = target.take_damage(raw_damage)
        self.combat_stats["enemy_damage"] += dmg
        self.record_damage_taken(target, dmg)
        events.append(f"{enemy.name}->{target.name} {dmg}")
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)

    def enemy_poison_peck(self, enemy: Unit, target: Unit, events: List[str]) -> None:
        self.flash_effect([target.pos], "poison")
        dmg = target.take_damage(2)
        self.combat_stats["enemy_damage"] += dmg
        self.record_damage_taken(target, dmg)
        target.poison = max(target.poison, 2)
        enemy.cooldowns["Poison Claw"] = 4
        events.append(f"{enemy.name} poisons {target.name} {dmg}")
        self.render()
        if self.frame_delay > 0:
            time.sleep(self.frame_delay)

    def enemy_overwatch_risk(self, enemy: Unit, destination: Pos) -> int:
        watched = self.active_overwatch_tiles()
        if not watched:
            return 0
        if destination == enemy.pos:
            return 1 if enemy.pos in watched else 0
        path = self.find_path(enemy, destination)
        if not path:
            path = [enemy.pos, destination]
        return sum(1 for step in path[1:] if step in watched)

    def ally_spacing_score(self, enemy: Unit, pos: Pos) -> int:
        # Positive score means better spacing from other enemies to reduce AoE value.
        others = [e for e in self.enemies_alive() if e is not enemy]
        if not others:
            return 0
        nearest = min(manhattan(pos, other.pos) for other in others)
        if nearest <= 1:
            return -12
        if nearest == 2:
            return -4
        return 4

    def cover_score_for_enemy_tile(self, pos: Pos) -> int:
        # Cover is a light preference, not a full line-of-sight simulation.
        adjacent_cover = sum(1 for p in neighbors4(pos) if self.in_bounds(p) and self.tile_at(p) in COVER_TILES)
        return min(8, adjacent_cover * 3)

    def best_retreat_tile(self, enemy: Unit, threat: Unit) -> Optional[Pos]:
        reachable = list(self.reachable_tiles(enemy))
        if not reachable:
            return None
        watched = self.active_overwatch_tiles()

        def score(pos: Pos) -> Tuple[int, int, int, int, int]:
            risk = self.enemy_overwatch_risk(enemy, pos)
            dist_from_threat = manhattan(pos, threat.pos)
            nearest_hero = min(manhattan(pos, h.pos) for h in self.heroes_alive())
            can_attack_after = any(enemy.weapon.range_min <= manhattan(pos, h.pos) <= enemy.weapon.range_max for h in self.heroes_alive())
            terrain = self.terrain_score_for_unit(enemy, pos, cautious=True) - self.movement_cost(pos)
            return (
                -risk * 50,
                terrain,
                dist_from_threat,
                1 if can_attack_after else 0,
                nearest_hero,
            )

        return max(reachable, key=score)

    def best_charge_destination(self, enemy: Unit, target: Unit) -> Optional[Pos]:
        # Brutal Charge is allowed if target is within 4 tiles and there is a reachable adjacent landing tile.
        if manhattan(enemy.pos, target.pos) > 4:
            return None
        adjacent = [p for p in neighbors4(target.pos) if self.is_walkable(p, ignore=enemy)]
        reachable = self.reachable_tiles(enemy)
        candidates = [p for p in adjacent if p in reachable]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda p: (
                -self.enemy_overwatch_risk(enemy, p),
                self.cover_score_for_enemy_tile(p),
                -manhattan(enemy.pos, p),
            ),
        )

    def best_spore_burst(self, enemy: Unit):
        # Range 4, AoE radius 1, hits heroes only. Prioritize clusters and
        # fresh vulnerable applications.
        best = None
        for y in range(self.map_height_tiles()):
            for x in range(self.map_width_tiles()):
                center = (x, y)
                if manhattan(enemy.pos, center) > 4:
                    continue
                targets = [h for h in self.heroes_alive() if h.pos in self.aoe_tiles(center, 1)]
                if not targets:
                    continue
                score = (
                    len(targets) * 24
                    + sum(1 for h in targets if h.vulnerable <= 0) * 9
                    + sum(1 for h in targets if h.hp <= 4) * 20
                    + sum(h.action_points for h in targets) * 2
                )
                # Avoid wasting Toxic Burst on a single guarded full-HP target.
                if len(targets) == 1 and targets[0].guard and targets[0].hp > targets[0].max_hp * 0.5:
                    score -= 18
                if best is None or score > best[3]:
                    best = ("spore", center, targets, score)
        if best and (len(best[2]) >= 2 or best[3] >= 38):
            return ("spore", best[1], best[2])
        return None

    def closest_hero(self, pos: Pos) -> Optional[Unit]:
        heroes = self.heroes_alive()
        return min(heroes, key=lambda h: manhattan(pos, h.pos)) if heroes else None

    def can_attack(self, attacker: Unit, target: Unit) -> bool:
        d = manhattan(attacker.pos, target.pos)
        return attacker.weapon.range_min <= d <= attacker.weapon.range_max

    def best_enemy_move(
        self,
        enemy: Unit,
        target: Optional[Unit],
        preferred_min: Optional[int] = None,
        preferred_max: Optional[int] = None,
        cautious: bool = True,
    ) -> Pos:
        return ai_helpers.choose_best_enemy_move(
            enemy,
            target,
            list(self.reachable_tiles(enemy).keys()),
            self.heroes_alive(),
            self.active_overwatch_tiles(),
            self.enemy_best_target,
            self.enemy_target_score,
            self.terrain_score_for_unit,
            self.movement_cost,
            self.ally_spacing_score,
            self.congestion_escape_bonus,
            self.ai_progress_to_attack_band,
            self.ai_movement_progress_bonus,
            preferred_min,
            preferred_max,
            cautious,
        )

    def best_controller_move(self, enemy: Unit, target: Unit) -> Pos:
        reachable = list(self.reachable_tiles(enemy))
        if not reachable:
            return enemy.pos

        heroes = self.heroes_alive()

        def score(pos: Pos) -> Tuple[int, int, int, int, int, int]:
            # Controller wants to be in thorn/root range, not adjacent, and not
            # standing in the party's obvious overwatch lane.
            best_target_score = 0
            for hero in heroes:
                d = manhattan(pos, hero.pos)
                in_thorn_range = enemy.weapon.range_min <= d <= enemy.weapon.range_max
                in_root_range = d <= 4 and hero.rooted <= 0
                best_target_score = max(
                    best_target_score,
                    (18 if in_thorn_range else 0)
                    + (14 if in_root_range else 0)
                    + self.enemy_target_score(enemy, hero)
                    - (15 if d <= 1 else 0),
                )
            risk = self.enemy_overwatch_risk(enemy, pos)
            return (
                best_target_score,
                self.cover_score_for_enemy_tile(pos),
                self.ally_spacing_score(enemy, pos),
                -risk * 40,
                -abs(manhattan(pos, target.pos) - 3),
                -manhattan(enemy.pos, pos),
            )

        return max(reachable, key=score)

    # ----- input -----

    def move_cursor(self, dx: int, dy: int) -> None:
        x, y = self.cursor
        new_y = clamp(y + dy, 0, max(0, self.map_height_tiles() - 1))
        row_width = len(self.map[new_y]) if self.map and 0 <= new_y < len(self.map) else self.map_width_tiles()
        new_x = clamp(x + dx, 0, max(0, row_width - 1))
        self.cursor = (new_x, new_y)

    def move_menu_selection(self, delta: int) -> None:
        if self.state == "command":
            options = self.command_menu_options()
            self.menu_index = (self.menu_index + delta) % len(options)
        elif self.state == "skill_group_menu":
            self.skill_group_index = (self.skill_group_index + delta) % len(self.SKILL_GROUP_MENU)
        elif self.state == "party_group_menu":
            self.party_group_index = (self.party_group_index + delta) % len(self.PARTY_GROUP_MENU)
        elif self.state == "control_menu":
            self.control_menu_index = (self.control_menu_index + delta) % len(self.heroes)
        elif self.state == "enemy_view":
            targets = self.sorted_enemy_view_targets()
            if targets:
                self.enemy_view_index = (self.enemy_view_index + delta) % len(targets)
                self.cursor = targets[self.enemy_view_index].pos
        elif self.state == "skill_menu":
            skills = self.available_skills(self.selected_hero)
            if skills:
                self.skill_index = (self.skill_index + delta) % len(skills)
        elif self.state == "overwatch_menu":
            options = self.overwatch_options(self.selected_hero)
            if options:
                self.overwatch_menu_index = (self.overwatch_menu_index + delta) % len(options)
        elif self.state == "support_target_menu":
            targets = self.support_targets_for_skill(self.selected_hero, self.selected_skill(self.selected_hero))
            if targets:
                self.support_target_index = (self.support_target_index + delta) % len(targets)
        elif self.state == "tactics_menu":
            self.tactics_index = (self.tactics_index + delta) % 4
        elif self.state == "hero_menu":
            self.hero_menu_index = (self.hero_menu_index + delta) % len(self.heroes)
        elif self.state == "map_menu":
            self.map_menu_index = (self.map_menu_index + delta) % len(self.maps)
        elif self.state == "item_menu":
            items = self.usable_items(self.selected_hero)
            if items:
                self.item_index = (self.item_index + delta) % len(items)
        elif self.state == "item_target_menu":
            item = self.selected_item()
            targets = self.item_ally_targets(self.selected_hero, item)
            if targets:
                self.item_target_index = (self.item_target_index + delta) % len(targets)

    def handle_direction(self, key: str) -> None:
        dx = dy = 0
        if key in ("UP", "w"):
            dy = -1
        elif key in ("DOWN", "s"):
            dy = 1
        elif key in ("LEFT", "a"):
            dx = -1
        elif key in ("RIGHT", "d"):
            dx = 1

        if self.state_uses_map_cursor():
            self.move_cursor(dx, dy)
        else:
            # Menu/submenu states: both WASD and arrows operate the menu.
            # Up/Down change selected menu row.
            # Left/Right currently do not change focus; they nudge selection too,
            # which matches the user's request that menu should use all directions.
            if dy != 0:
                self.move_menu_selection(dy)
            elif dx != 0:
                self.move_menu_selection(dx)

    def handle_key(self, key: str, reader: KeyReader) -> None:
        if key == "q":
            self.should_quit = True
            return
        if key == "h":
            self.help(reader)
            return
        if key == "u":
            self.toggle_ui_mode()
            return
        if self.state == "combat_log":
            self.handle_combat_log_key(key)
            return
        if key == "l":
            self.start_combat_log()
            return
        if key == "y":
            self.start_enemy_view()
            return
        if key == "s" and self.state == "enemy_view":
            self.cycle_enemy_view_sort(1)
            return
        if key in ("ESC", "c", "x"):
            self.cancel()
            return

        if key == "TAB":
            if self.state == "command":
                self.next_hero(require_ap=False)
            else:
                self.push("Tab cycles heroes only from command menu.")
            return

        if key in ("UP", "DOWN", "LEFT", "RIGHT", "w", "a", "s", "d"):
            self.handle_direction(key)
            return

        if key in ("ENTER", "SPACE", "z"):
            self.confirm()
        elif key == "m":
            self.start_move()
        elif key == "j":
            self.start_attack()
        elif key == "k":
            self.start_skill()
        elif key == "p":
            self.start_item()
        elif key == "g":
            self.guard_action()
        elif key == "o":
            self.start_overwatch()
        elif key == "e":
            self.end_turn()
        else:
            self.push(f"Unknown key {repr(key)}.")

        self.maybe_auto_end()

    def help(self, reader: KeyReader) -> None:
        pages = [
            ("Basics", [
                "Home uses Up/Down and Enter.",
                "X/Esc/Home returns to Home from setup pages.",
                "Start Battle launches the currently selected map or mission.",
                "Maps and Missions select setup first; they do not instantly start battle.",
            ]),
            ("Battle Controls", [
                "Command menu: Up/Down choose, Z/Enter confirm.",
                "Targeting: arrows/WASD move cursor, Z/Enter confirm, X/Esc/C cancel.",
                "L opens the Combat Log.",
                "Party opens hero/tactic/control options during battle.",
            ]),
            ("Setup", [
                "M maps, I missions, P party, J companion editor, L loadout.",
                "E encounter builder, G objectives, K classes, B bestiary.",
                "Encounter Builder: Up/Down row, Left/Right count or map, Z/Enter add/activate.",
                "Tab does not cycle setup pages.",
            ]),
            ("Systems", [
                "Terrain includes cover, mud, thorns, springs, crystals, ice, crates, and barrels.",
                "Classes, subclasses, weapons, and equipment affect skill/attack patterns.",
                "Objectives are optional; defeating all enemies still works unless a special failure condition applies.",
                "Mission presets bundle map, enemies, objective, and flavor for testing.",
            ]),
            ("Troubleshooting", [
                "python combat_prototype_v113.py --no-color",
                "python combat_prototype_v113.py --ascii",
                "python combat_prototype_v113.py --compact",
                "python combat_prototype_v113.py --roomy",
            ]),
        ]
        index = 0
        while True:
            clear_screen()
            print(c("HELP", Style.BOLD, Style.BRIGHT_WHITE))
            print("-" * 78)
            for i, (title, _lines) in enumerate(pages):
                prefix = "> " if i == index else "  "
                if i == index:
                    print(c(prefix + title, Style.BLACK, Style.BG_SELECT, Style.BOLD))
                else:
                    print(prefix + title)
            print()
            title, lines = pages[index]
            print(c(title, Style.BOLD, Style.BRIGHT_CYAN))
            for line in lines:
                for wrapped in wrap_plain(line, 74, subsequent_indent="  "):
                    print("  " + wrapped)
            print()
            print("Up/Down category | Z/Enter/X/Esc/C close")
            key = reader.read_key()
            if key in ("UP", "w", "LEFT", "a"):
                index = (index - 1) % len(pages)
            elif key in ("DOWN", "s", "RIGHT", "d"):
                index = (index + 1) % len(pages)
            elif key in ("ENTER", "SPACE", "z", "ESC", "c", "x", "q", "h"):
                return


    def inventory_text(self, inventory: Optional[Dict[str, int]] = None) -> str:
        inv = self.campaign_inventory if inventory is None else inventory
        shown = [(k, v) for k, v in inv.items() if v > 0]
        return ", ".join(f"{k} x{v}" for k, v in shown) if shown else "None"

    def notable_loot_lines(self, limit: int = 6) -> List[str]:
        logs = list(self.combat_stats.get("loot_log", []))
        if not logs:
            return ["No notable drops."]
        notable = [line for line in logs if any(tag in line for tag in ("Rare:", "Elite:", "Boss:", "cache", "Cache"))]
        if not notable:
            notable = logs
        shown = notable[:limit]
        if len(notable) > limit:
            shown.append(f"...and {len(notable) - limit} more notable drops.")
        return shown

    def loot_summary_line(self) -> str:
        rare = int(self.combat_stats.get("rare_loot_found", 0))
        caches = int(self.combat_stats.get("cache_rewards", 0))
        return f"Rare drops: {rare} | Caches: {caches} | Total reward types: {sum(1 for v in self.rewards.values() if v > 0)}"

    def victory_bonus_rewards(self) -> Dict[str, int]:
        grade = self.performance_grade()
        bonus: Dict[str, int] = {}
        if grade == "S":
            bonus.update({"Coin": 14, "Shard": 1, "Tonic": 1, "Relic Cache": 1})
        elif grade == "A":
            bonus.update({"Coin": 9, "Tonic": 1, "Supply Cache": 1})
        elif grade == "B":
            bonus.update({"Coin": 5, "Supply Cache": 1})
        else:
            bonus.update({"Coin": 2})

        if not any(h.active and not h.alive for h in self.heroes):
            bonus["Guard Tonic"] = bonus.get("Guard Tonic", 0) + 1
        if self.round_no <= 6:
            bonus["Coin"] = bonus.get("Coin", 0) + 4
        if self.combat_stats.get("zones_created", 0) >= 2:
            bonus["Shard"] = bonus.get("Shard", 0) + 1
        if self.combat_stats.get("combo_triggers", 0) >= 2:
            bonus["Fang"] = bonus.get("Fang", 0) + 1
        if bonus.get("Supply Cache", 0) or bonus.get("Relic Cache", 0):
            self.combat_stats["cache_rewards"] = self.combat_stats.get("cache_rewards", 0) + bonus.get("Supply Cache", 0) + bonus.get("Relic Cache", 0)
            self.combat_stats.setdefault("loot_log", []).append("Victory cache — " + self.inventory_text({k: v for k, v in bonus.items() if k in ("Supply Cache", "Relic Cache") and v > 0}))
        return bonus


    def deposit_rewards(self, rewards: Dict[str, int]) -> None:
        for key, amount in rewards.items():
            if amount <= 0:
                continue
            self.campaign_inventory[key] = self.campaign_inventory.get(key, 0) + amount

    def apply_victory_party_xp(self) -> List[str]:
        base = 6
        if self.round_no <= 6:
            base += 3
        if not any(h.active and not h.alive for h in self.heroes):
            base += 2

        lines: List[str] = []
        for hero in self.heroes:
            if not hero.active:
                continue
            before_level = self.party_progress.get(hero.name, {}).get("level", hero.level)
            level_messages = self.gain_hero_xp(hero, base)
            after_level = self.party_progress.get(hero.name, {}).get("level", hero.level)
            self.combat_stats["party_xp_bonus"] = self.combat_stats.get("party_xp_bonus", 0) + base
            if level_messages:
                lines.append(f"{hero.name} +{base} participation XP ({before_level}->{after_level}).")
            else:
                lines.append(f"{hero.name} +{base} participation XP.")
        return lines

    def party_progress_lines(self) -> List[str]:
        lines: List[str] = []
        heroes = [hero for hero in self.heroes if hero.active] if getattr(getattr(self, "current_battle_request", None), "source", "") == "ascii_farmstead" else self.heroes
        for hero in heroes:
            progress = self.ensure_progress_entry(hero)
            status = "active" if hero.active else "reserve"
            lines.append(
                f"{hero.name:<5} {self.hero_class(hero):<8} Lv {int(progress['level'])} XP {int(progress['xp']):>2}/20 "
                f"SP {int(progress.get('skill_points', 0))} "
                f"HP+{int(progress['hp_bonus'])} MP+{int(progress['mp_bonus'])} DMG+{int(progress['damage_bonus'])} "
                f"Gear[{self.hero_equipment_summary(hero)}] ({status})"
            )
        return lines


    def resolve_battle_result(self, result: str) -> List[str]:
        if self.battle_result_processed:
            return self.last_result_lines

        self.battle_result_processed = True
        lines: List[str] = []
        if result.startswith("Victory"):
            bonus = self.victory_bonus_rewards()
            self.deposit_rewards(self.rewards)
            self.deposit_rewards(bonus)
            xp_lines = self.apply_victory_party_xp()

            lines.append(f"Result: Victory on {self.map_name}")
            lines.append(f"Grade: {self.performance_grade()} | Rounds: {self.combat_stats['rounds']} | Tactic: {self.follower_tactic}")
            if self.current_mission_name:
                lines.append("Mission: " + self.current_mission_name)
            lines.append("Objective: " + self.objective_progress_text())
            defeated = ", ".join(self.combat_stats.get("defeated", [])) or "None"
            lines.append(f"Defeated: {defeated}")
            lines.append(f"Kill XP earned: {self.combat_stats.get('xp_earned', 0)}")
            lines.append(f"Participation XP: {self.combat_stats.get('party_xp_bonus', 0)} total")
            lines.append("")
            lines.extend(self.tactical_report_lines(result))
            lines.append("Battle loot: " + self.inventory_text(self.rewards))
            lines.append("Bonus loot: " + self.inventory_text(bonus))
            lines.append("Loot highlights:")
            lines.extend("  " + line for line in self.notable_loot_lines())
            lines.append("Campaign inventory: " + self.inventory_text(self.campaign_inventory))
            lines.append("")
            lines.append("Party progression:")
            lines.extend("  " + line for line in self.party_progress_lines())
            if xp_lines:
                lines.append("")
                lines.append("Participation:")
                lines.extend("  " + line for line in xp_lines)
        else:
            lines.append(f"Result: Defeat on {self.map_name}")
            lines.append("Objective: " + self.objective_progress_text())
            defeated = ", ".join(self.combat_stats.get("defeated", [])) or "None"
            lines.append(f"Enemies defeated before wipeout: {defeated}")
            lines.append(f"Kill XP kept: {self.combat_stats.get('xp_earned', 0)}")
            lines.append("")
            lines.extend(self.tactical_report_lines(result))
            lines.append("")
            lines.append("Battle loot lost on defeat.")
            lines.append("Campaign inventory: " + self.inventory_text(self.campaign_inventory))
            lines.append("")
            lines.append("Party progression:")
            lines.extend("  " + line for line in self.party_progress_lines())

        self.add_combat_log_entry("Battle ended. " + " | ".join(line for line in lines[:6] if line), category="RESULT")
        self.last_result_lines = lines
        return lines

    def result_sections(self, result: str) -> List[Tuple[str, List[str]]]:
        is_victory = result.startswith("Victory")
        defeated = ", ".join(self.combat_stats.get("defeated", [])) or "None"
        summary = [
            f"Result: {'Victory' if is_victory else 'Defeat'} on {self.map_name}",
            f"Grade: {self.performance_grade()} | Rounds: {self.combat_stats.get('rounds', self.round_no)}",
        ]
        if self.current_mission_name:
            summary.append("Mission: " + self.current_mission_name)
        summary.extend([
            "Objective: " + self.objective_progress_text(),
            f"Defeated: {defeated}",
            f"XP: kills {self.combat_stats.get('xp_earned', 0)} | participation {self.combat_stats.get('party_xp_bonus', 0)}",
            "Loot: " + self.loot_summary_line(),
        ])

        if is_victory:
            loot_lines = [
                "Battle loot: " + self.inventory_text(self.rewards),
                "Campaign inventory: " + self.inventory_text(self.campaign_inventory),
            ]
            highlights = self.notable_loot_lines(limit=5)
            if highlights:
                loot_lines.append("Highlights:")
                loot_lines.extend("  " + line for line in highlights)
        else:
            loot_lines = [
                "Battle loot lost on defeat.",
                "Campaign inventory: " + self.inventory_text(self.campaign_inventory),
            ]

        progression = self.party_progress_lines()
        if not progression:
            progression = ["No party progression changes."]

        return [
            ("Summary", summary),
            ("Loot", loot_lines),
            ("Progression", progression),
            ("Tactics", self.tactical_report_lines(result)),
        ]

    def handle_results_key(self, key: str) -> str:
        section_count = 4
        if key in ("LEFT", "a", "UP", "w"):
            self.result_section_index = (self.result_section_index - 1) % section_count
            return "stay"
        if key in ("RIGHT", "d", "DOWN", "s"):
            self.result_section_index = (self.result_section_index + 1) % section_count
            return "stay"
        if key == "q":
            return "quit"
        return "close"

    def render_results_screen(self, result: str) -> None:
        clear_screen()
        is_victory = result.startswith("Victory")
        if not self.battle_result_processed:
            self.last_result_lines = self.resolve_battle_result(result)
            self.battle_result_processed = True
            self.result_section_index = 0

        sections = self.result_sections(result)
        self.result_section_index %= len(sections)
        section_title, section_lines = sections[self.result_section_index]

        terminal = shutil.get_terminal_size(fallback=(100, 30))
        width = max(50, min(100, terminal.columns))
        content_width = max(30, width - 2)
        height = max(12, terminal.lines - 1)

        title = "VICTORY" if is_victory else "DEFEAT"
        color = Style.BRIGHT_GREEN if is_victory else Style.BRIGHT_RED
        rows: List[str] = []
        rows.append(c("ASCII Tactical Combat Prototype v113", Style.BOLD, Style.BRIGHT_WHITE))
        rows.append(c(title, Style.BOLD, color) + " / " + c(section_title, Style.BOLD, Style.BRIGHT_CYAN))
        rows.append("-" * width)
        nav = "  ".join(("[" + name + "]") if i == self.result_section_index else name for i, (name, _lines) in enumerate(sections))
        rows.extend(wrap_plain(nav, content_width))
        rows.append("-" * width)
        for line in section_lines:
            rows.extend(wrap_plain(line, content_width, subsequent_indent="  "))
        rows.append("-" * width)
        if getattr(getattr(self, "current_battle_request", None), "source", "") == "ascii_farmstead":
            controls = "Left/Right or Up/Down: section | Z/Enter/X/Esc/C/Q: return to farm"
        else:
            controls = "Left/Right or Up/Down: section | Z/Enter/X/Esc/C: Main Menu | Q: quit"
        rows.extend(wrap_plain(controls, content_width))
        if len(rows) > height:
            rows = rows[:height]
            rows[-1] = clip("... more text hidden; enlarge window or use wider terminal.", content_width)
        print("\n".join(clip_visible(row, width) for row in rows))


    def victory_summary_lines(self) -> List[str]:
        reward_text = self.inventory_text(self.rewards)
        defeated = ", ".join(self.combat_stats.get("defeated", [])) or "None"
        return [
            f"Map: {self.map_name} | Grade: {self.performance_grade()} | Tactic: {self.follower_tactic}",
            "Party: " + ", ".join(h.name for h in self.heroes if h.active),
            f"Rounds: {self.combat_stats['rounds']}",
            f"Damage dealt: player {self.combat_stats['player_damage']} | follower {self.combat_stats['follower_damage']}",
            f"Damage taken: {self.combat_stats['enemy_damage']}",
            f"Kills: {self.combat_stats['kills']} | Skills: {self.combat_stats['skills_used']} | Items: {self.combat_stats.get('items_used', 0)}",
            f"Defeated: {defeated}",
            f"Kill XP: {self.combat_stats.get('xp_earned', 0)}",
            f"Battle loot: {reward_text}",
            f"Campaign inventory: {self.inventory_text(self.campaign_inventory)}",
        ]


    def objective_modes(self) -> List[str]:
        return ["Defeat All", "Survive", "Escape", "Hold Zone", "Protect Ally", "Destroy Objects"]

    def objective_enabled(self) -> bool:
        return self.objective_mode != "Defeat All"

    def cycle_objective_mode(self, direction: int = 1) -> None:
        modes = self.objective_modes()
        current = modes.index(self.objective_mode) if self.objective_mode in modes else 0
        self.objective_mode = modes[(current + direction) % len(modes)]
        self.objective_menu_index = modes.index(self.objective_mode)
        self.messages = [f"Objective set to {self.objective_mode}."]

    def adjust_objective_parameter(self, direction: int = 1) -> None:
        if self.objective_mode == "Survive":
            self.objective_round_goal = max(2, min(12, self.objective_round_goal + direction))
            self.messages = [f"Survive objective set to {self.objective_round_goal} rounds."]
        elif self.objective_mode == "Hold Zone":
            self.objective_hold_goal = max(1, min(6, self.objective_hold_goal + direction))
            self.messages = [f"Hold objective set to {self.objective_hold_goal} ticks."]
        elif self.objective_mode == "Destroy Objects":
            self.objective_object_goal = max(1, min(5, self.objective_object_goal + direction))
            self.messages = [f"Destroy objective set to {self.objective_object_goal} objects."]
        else:
            self.messages = [f"{self.objective_mode} has no adjustable parameter."]

    def objective_parameter_text(self) -> str:
        if self.objective_mode == "Survive":
            return f"Rounds: {self.objective_round_goal}"
        if self.objective_mode == "Hold Zone":
            return f"Hold ticks: {self.objective_hold_goal}"
        if self.objective_mode == "Destroy Objects":
            return f"Objects: {self.objective_object_goal}"
        if self.objective_mode == "Protect Ally":
            return "Protected ally chosen from active party at battle start."
        if self.objective_mode == "Escape":
            return "Escape tile placed far from the party."
        return "Classic victory condition."

    def objective_setup_description(self) -> str:
        descriptions = {
            "Defeat All": "Classic battle. Win by defeating every enemy.",
            "Survive": "Optional challenge. Win after surviving enough enemy phases; defeating enemies also wins.",
            "Escape": "Optional challenge. Reach the green exit tile; defeating enemies also wins.",
            "Hold Zone": "Optional challenge. Keep any active hero in the hold zone across enemy phases.",
            "Protect Ally": "Optional challenge. Keep the marked ally alive while clearing enemies.",
            "Destroy Objects": "Optional challenge. Break marked objective crates with weapon/skill AoE.",
        }
        return descriptions.get(self.objective_mode, "Optional battle objective.")

    def objective_free_tiles(self) -> List[Pos]:
        occupied = {u.pos for u in self.all_units if u.active}
        tiles: List[Pos] = []
        for y, row in enumerate(self.map):
            for x, tile in enumerate(row):
                pos = (x, y)
                if tile in PASSABLE and pos not in occupied:
                    tiles.append(pos)
        return tiles

    def objective_far_tile(self) -> Optional[Pos]:
        tiles = self.objective_free_tiles()
        heroes = [h.pos for h in self.heroes if h.active]
        if not tiles:
            return None
        if not heroes:
            return tiles[-1]
        return max(tiles, key=lambda p: (min(manhattan(p, h) for h in heroes), p[0], -p[1]))

    def objective_center_tile(self) -> Optional[Pos]:
        tiles = self.objective_free_tiles()
        if not tiles:
            return None
        center = (self.map_width_tiles() // 2, self.map_height_tiles() // 2)
        return min(tiles, key=lambda p: (manhattan(p, center), manhattan(p, self.selected_hero.pos)))

    def objective_tiles_near(self, center: Pos, radius: int = 1) -> Set[Pos]:
        tiles = {center}
        for p in self.aoe_tiles(center, radius):
            if self.in_bounds(p) and self.tile_at(p) in PASSABLE:
                tiles.add(p)
        return tiles

    def setup_objective_state(self) -> None:
        self.objective_hold_progress = 0
        self.objective_destroyed = 0
        self.objective_exit_tile = None
        self.objective_hold_tiles = set()
        self.objective_object_tiles = set()
        self.objective_last_tick_round = 0
        active_heroes = [h for h in self.heroes if h.active]
        self.objective_protect_name = next((h.name for h in active_heroes if h.name != "Rook"), "Rook")

        if self.objective_mode == "Escape":
            self.objective_exit_tile = self.objective_far_tile()
        elif self.objective_mode == "Hold Zone":
            center = self.objective_center_tile()
            self.objective_hold_tiles = self.objective_tiles_near(center, 1) if center else set()
        elif self.objective_mode == "Destroy Objects":
            self.place_objective_objects()

    def place_objective_objects(self) -> None:
        self.objective_object_tiles = set()
        tiles = self.objective_free_tiles()
        if not tiles:
            return
        center = (self.map_width_tiles() // 2, self.map_height_tiles() // 2)
        heroes = [h.pos for h in self.heroes if h.active]
        def score(p: Pos) -> Tuple[int, int, int]:
            hero_dist = min((manhattan(p, h) for h in heroes), default=0)
            return (abs(manhattan(p, center) - 5), -hero_dist, p[0] + p[1])
        chosen = sorted(tiles, key=score)[: self.objective_object_goal]
        for pos in chosen:
            self.set_tile(pos, TILE_CRATE)
            self.objective_object_tiles.add(pos)

    def objective_progress_text(self) -> str:
        if self.objective_mode == "Defeat All":
            return "Defeat all enemies."
        if self.objective_mode == "Survive":
            return f"Survive through Round {self.objective_round_goal}. Current: Round {self.round_no}."
        if self.objective_mode == "Escape":
            tile = self.objective_exit_tile
            return f"Reach the exit tile at {tile}." if tile else "Reach the exit tile."
        if self.objective_mode == "Hold Zone":
            return f"Hold zone progress: {self.objective_hold_progress}/{self.objective_hold_goal}."
        if self.objective_mode == "Protect Ally":
            ally = next((h for h in self.heroes if h.name == self.objective_protect_name), None)
            hp = f" HP {ally.hp}/{ally.max_hp}" if ally else ""
            return f"Protect {self.objective_protect_name}{hp} while clearing enemies."
        if self.objective_mode == "Destroy Objects":
            return f"Destroy marked crates: {self.objective_destroyed}/{self.objective_object_goal}."
        return "Complete the battle objective."

    def objective_text(self) -> str:
        if not self.objective_enabled():
            return "Objective: Defeat all enemies."
        return f"Objective: {self.objective_mode} — {self.objective_progress_text()}"


    def objective_completed(self) -> bool:
        if self.objective_mode == "Defeat All":
            return False
        if self.objective_mode == "Survive":
            return self.round_no > self.objective_round_goal
        if self.objective_mode == "Escape":
            return bool(self.objective_exit_tile and any(h.active and h.alive and h.pos == self.objective_exit_tile for h in self.heroes))
        if self.objective_mode == "Hold Zone":
            return self.objective_hold_progress >= self.objective_hold_goal
        if self.objective_mode == "Destroy Objects":
            return self.objective_destroyed >= self.objective_object_goal
        return False

    def objective_failed(self) -> Optional[str]:
        if self.objective_mode == "Protect Ally":
            ally = next((h for h in self.heroes if h.name == self.objective_protect_name), None)
            if ally and not ally.alive:
                return f"Defeat. Protected ally {ally.name} fell."
        return None

    def tick_objective_progress(self, events: Optional[List[str]] = None) -> None:
        if self.objective_mode != "Hold Zone" or self.objective_last_tick_round == self.round_no:
            return
        self.objective_last_tick_round = self.round_no
        if any(h.active and h.alive and h.pos in self.objective_hold_tiles for h in self.heroes):
            self.objective_hold_progress = min(self.objective_hold_goal, self.objective_hold_progress + 1)
            if events is not None:
                events.append(f"Hold objective +1 ({self.objective_hold_progress}/{self.objective_hold_goal})")
        elif events is not None and self.objective_hold_tiles:
            events.append("Hold objective not advanced")

    def objective_object_hits(self, tiles: Set[Pos]) -> List[str]:
        if self.objective_mode != "Destroy Objects":
            return []
        hits = [p for p in sorted(self.objective_object_tiles) if p in tiles and self.tile_at(p) == TILE_CRATE]
        parts: List[str] = []
        for pos in hits:
            self.set_tile(pos, TILE_FLOOR)
            self.objective_object_tiles.discard(pos)
            self.objective_destroyed += 1
            parts.append(f"objective crate {self.objective_destroyed}/{self.objective_object_goal}")
        return parts

    def objective_marker_at(self, pos: Pos) -> str:
        if self.objective_mode == "Escape" and pos == self.objective_exit_tile:
            return "exit"
        if self.objective_mode == "Hold Zone" and pos in self.objective_hold_tiles:
            return "hold"
        if self.objective_mode == "Destroy Objects" and pos in self.objective_object_tiles:
            return "object"
        return ""

    def objective_marker_cell(self, marker: str) -> str:
        if marker == "exit":
            return c(" E ", Style.BLACK, Style.BG_MOVE, Style.BOLD)
        if marker == "hold":
            return c(" H ", Style.BLACK, Style.BG_OVERWATCH, Style.BOLD)
        if marker == "object":
            return c(" X ", Style.BLACK, Style.BG_ATTACK, Style.BOLD)
        return ""

    def game_over(self) -> Optional[str]:
        if not self.heroes_alive():
            return "Defeat. Your party was wiped out."

        failed = self.objective_failed()
        if failed:
            return failed

        if self.objective_completed():
            return f"Victory. Optional objective complete: {self.objective_mode}."

        if not self.enemies_alive():
            self.record_tutorial_event("victory")
            if self.tutorial_active:
                if self.tutorial_mode == "advanced":
                    return "Advanced tutorial complete. Mixed-role drill cleared."
                return "Tutorial complete. All training enemies defeated."
            if self.objective_enabled():
                return f"Victory. All enemies defeated. Optional objective: {self.objective_mode}."
            return "Victory. All enemies defeated."
        return None


    def tutorial_modes(self) -> List[Tuple[str, str, str, str]]:
        return [
            ("basic", "Basic Tutorial", "Training Yard", "Core controls, safe practice, and first victory."),
            ("advanced", "Advanced Tutorial", "Advanced Training Yard", "Intent sorting, terrain, overwatch lanes, support, and focus fire."),
        ]

    def selected_tutorial_mode(self) -> str:
        modes = self.tutorial_modes()
        self.tutorial_menu_index %= len(modes)
        return modes[self.tutorial_menu_index][0]

    def tutorial_title_for_mode(self, mode: Optional[str] = None) -> str:
        mode = mode or self.tutorial_mode
        for key, title, _map_name, _desc in self.tutorial_modes():
            if key == mode:
                return title
        return "Tutorial"

    def tutorial_map_for_mode(self, mode: Optional[str] = None) -> str:
        mode = mode or self.tutorial_mode
        for key, _title, map_name, _desc in self.tutorial_modes():
            if key == mode:
                return map_name
        return "Training Yard"

    def tutorial_steps_for_mode(self, mode: Optional[str] = None) -> List[Tuple[str, str, str]]:
        mode = mode or self.tutorial_mode
        if mode == "advanced":
            return [
                ("enemy_view", "Sort enemy intent", "Open Enemy View and use it to identify the most dangerous enemy."),
                ("move", "Move with danger in mind", "Reposition while avoiding obvious chokepoint punishment."),
                ("attack", "Focus a priority target", "Use a basic attack to begin focus fire on one enemy."),
                ("skill", "Apply status or area pressure", "Use a skill to exploit range, shape, vulnerable, root, or AoE."),
                ("guard", "Hold a guard line", "Guard with a frontliner before enemy pressure lands."),
                ("overwatch", "Set an overwatch lane", "Cover a bridge, doorway, or chokepoint with Overwatch."),
                ("item", "Recover with support", "Use an item/support skill to heal, cleanse, guard, or transfer AP."),
                ("end_turn", "Resolve a full tactical round", "End the turn and watch AI allies/enemies resolve their plans."),
                ("victory", "Clear the advanced drill", "Defeat the mixed-role training enemies."),
            ]
        return [
            ("enemy_view", "Read an enemy", "Learn what enemies are likely to do before spending AP."),
            ("move", "Move safely", "Practice moving without ending on a dangerous tile."),
            ("attack", "Make an attack", "Use a basic attack on the Training Dummy or Slime."),
            ("skill", "Use a skill", "Cast a skill to learn range, shape, MP cost, and preview text."),
            ("guard", "Guard once", "Use Guard to reduce incoming damage and hold a lane."),
            ("overwatch", "Set Overwatch", "Prepare an attack that triggers during enemy movement."),
            ("item", "Use item/support", "Use an item or support skill to practice ally-list targeting."),
            ("end_turn", "End the round", "Let AI allies and enemies act so turn flow makes sense."),
            ("victory", "Win the tutorial", "Defeat the tutorial enemies when you are comfortable."),
        ]

    def tutorial_steps(self) -> List[Tuple[str, str, str]]:
        return self.tutorial_steps_for_mode(self.tutorial_mode)


    def tutorial_step_controls(self, key: str) -> str:
        controls = {
            "enemy_view": "Y Enemy View; S sort",
            "move": "Move > preview danger/path > Enter",
            "attack": "Attack > priority enemy > Enter",
            "skill": "Skills > Cast Skill > check preview > Enter",
            "guard": "Skills > Guard",
            "overwatch": "Skills > Overwatch > aim lane > Enter",
            "item": "Item, or Skills > Cast Skill > support ally",
            "end_turn": "End Turn",
            "victory": "Use focus fire and support; defeat remaining enemies",
        }
        if self.tutorial_mode != "advanced":
            controls.update({
                "enemy_view": "Y, or command: Enemy View",
                "move": "Move > cursor > Enter",
                "attack": "Attack > target > Enter",
                "skill": "Skills > Cast Skill > target/list > Enter",
                "overwatch": "Skills > Overwatch > choose option > Enter",
                "item": "Item, or Skills > Cast Skill > support skill",
                "victory": "Use what you learned; defeat remaining enemies",
            })
        return controls.get(key, "Use the command menu.")


    def tutorial_step_reason(self, key: str) -> str:
        if self.tutorial_mode == "advanced":
            reasons = {
                "enemy_view": "Advanced fights are won by reading intent before committing AP.",
                "move": "Strong maps punish bad positioning more than bad damage rolls.",
                "attack": "Focus fire removes threats faster than spreading chip damage.",
                "skill": "Status, AoE, and skill shapes turn terrain into advantage.",
                "guard": "Guard lets you hold a lane while enemies waste pressure.",
                "overwatch": "Overwatch makes enemy movement predictable and costly.",
                "item": "Support tools prevent one mistake from becoming a wipe.",
                "end_turn": "Watching the full round teaches how intent, cooldowns, and AI plans interact.",
                "victory": "This drill proves you can handle mixed roles and terrain pressure.",
            }
            return reasons.get(key, "This is part of the advanced battle loop.")
        reasons = {
            "enemy_view": "Good tactics start with knowing enemy intent.",
            "move": "Positioning decides who can attack, guard, or be punished.",
            "attack": "Basic attacks are your reliable no-MP option.",
            "skill": "Skills add range, status effects, combos, and area control.",
            "guard": "Guard keeps frontliners alive when holding chokepoints.",
            "overwatch": "Overwatch turns enemy movement into your opportunity.",
            "item": "Items and support skills recover from mistakes.",
            "end_turn": "The full round matters: allies, enemies, statuses, and cooldowns.",
            "victory": "The tutorial is complete once the practice enemies are down.",
        }
        return reasons.get(key, "This is part of the core battle loop.")


    def tutorial_next_step_title(self) -> str:
        for key, title, _desc in self.tutorial_steps():
            if key not in self.tutorial_flags:
                return title
        return "Tutorial complete"

    def tutorial_completed_count(self) -> int:
        return sum(1 for key, _title, _desc in self.tutorial_steps() if key in self.tutorial_flags)

    def tutorial_current_step(self) -> Tuple[str, str, str]:
        for step in self.tutorial_steps():
            if step[0] not in self.tutorial_flags:
                return step
        return self.tutorial_steps()[-1]

    def record_tutorial_event(self, key: str) -> None:
        if not self.tutorial_active:
            return
        valid = {step[0] for step in self.tutorial_steps()}
        if key not in valid:
            return
        if key not in self.tutorial_flags:
            self.tutorial_flags.add(key)
            title = next(title for step_key, title, _desc in self.tutorial_steps() if step_key == key)
            next_title = self.tutorial_next_step_title()
            if next_title == "Tutorial complete":
                self.push(f"Tutorial step complete: {title}. All lessons done.")
            else:
                self.push(f"Tutorial step complete: {title}. Next: {next_title}.")

    def tutorial_progress_lines(self, limit: int = 9) -> List[str]:
        lines: List[str] = []
        steps = self.tutorial_steps()
        for key, title, _desc in steps[:limit]:
            mark = "✓" if key in self.tutorial_flags else "·"
            lines.append(f"{mark} {title}")
        if len(steps) > limit:
            lines.append(f"+{len(steps)-limit} more")
        return lines

    def tutorial_current_hint_lines(self) -> List[str]:
        key, title, desc = self.tutorial_current_step()
        return [
            f"Lesson: {title}",
            "Do: " + desc,
            "Controls: " + self.tutorial_step_controls(key),
            "Why: " + self.tutorial_step_reason(key),
            f"Progress: {self.tutorial_completed_count()}/{len(self.tutorial_steps())}",
        ]

    def tutorial_map_index(self, mode: Optional[str] = None) -> int:
        target = self.tutorial_map_for_mode(mode)
        for i, (name, _grid, _pos) in enumerate(self.maps):
            if name == target:
                return i
        return 0

    def training_map_index(self) -> int:
        return self.tutorial_map_index("basic")


    def start_tutorial_from_main_menu(self) -> None:
        mode = self.selected_tutorial_mode()
        self.tutorial_mode = mode
        self.tutorial_active = True
        self.tutorial_flags = set()
        self.custom_encounter_enabled = False
        self.active_party_names = {"Rook", "Mira", "Luma"} if mode == "basic" else {"Rook", "Mira", "Brom", "Luma"}
        self.main_menu_index = self.tutorial_map_index(mode)
        self.map_index = self.main_menu_index
        self.map_name, self.map, self.start_positions = self.maps[self.map_index]
        self.map_menu_index = self.map_index
        self.active_enemy_names = set(self.enemy_loadout_for_map(self.map_name))
        self.reset_battle_positions()
        self.in_main_menu = False
        self.state = "command"
        self.turn = "hero"
        if mode == "advanced":
            self.messages = [
                "Advanced Tutorial started. Use Enemy View sorting before committing AP.",
                "Tip: practice guard lines, overwatch lanes, support recovery, and focus fire.",
            ]
        else:
            self.messages = [
                "Tutorial started. The Training Dummy is harmless; practice freely.",
                "Tip: follow the sidebar lesson. Y opens Enemy View. U toggles Clean/Full UI.",
            ]
        self.combat_log = []
        self.combat_log_scroll = 0
        self.log_existing_messages(category="TUTORIAL")


    def class_defs(self) -> Dict[str, Dict[str, object]]:
        return data_class_defs()

    def elemental_subclasses(self) -> List[str]:
        return ["Fire", "Frost", "Storm", "Earth", "Poison", "Light", "Shadow"]

    def default_subclass_for_hero(self, hero_name: str) -> str:
        defaults = {
            "Rook": "Fire",
            "Mira": "Storm",
            "Brom": "Earth",
            "Aria": "Frost",
            "Nia": "Shadow",
            "Dax": "Earth",
            "Luma": "Light",
        }
        return defaults.get(hero_name, "Fire")

    def hero_subclass(self, hero: Unit) -> str:
        progress = self.ensure_progress_entry(hero)
        subclass = str(progress.get("subclass", self.default_subclass_for_hero(hero.name)))
        if subclass not in self.elemental_subclasses():
            subclass = self.default_subclass_for_hero(hero.name)
            progress["subclass"] = subclass
        return subclass

    def subclass_skill_name(self, subclass: str) -> str:
        return {
            "Fire": "Ignite Field",
            "Frost": "Glacial Patch",
            "Storm": "Static Field",
            "Earth": "Quake Field",
            "Poison": "Venom Pool",
            "Light": "Radiant Seal",
            "Shadow": "Umbral Mire",
        }.get(subclass, "Ignite Field")

    def subclass_attack_skill_name(self, subclass: str) -> str:
        return {
            "Fire": "Flame Fan",
            "Frost": "Frost Shards",
            "Storm": "Chain Lightning",
            "Earth": "Seismic Wave",
            "Poison": "Toxic Bloom",
            "Light": "Solar Flare",
            "Shadow": "Umbral Barrage",
        }.get(subclass, "Flame Fan")

    def subclass_skill_names(self, subclass: str) -> List[str]:
        return [self.subclass_skill_name(subclass), self.subclass_attack_skill_name(subclass)]

    def subclass_skill_label(self, subclass: str) -> str:
        return " / ".join(self.subclass_skill_names(subclass))

    def subclass_passive_label(self, subclass: str) -> str:
        return {
            "Fire": "+1 damage and +1 zone damage for fire/burning skills.",
            "Frost": "+1 root duration for frost/root skills and zones.",
            "Storm": "+1 damage for vulnerable/static skills.",
            "Earth": "-1 MP on guard/root/earth skills; +1 root duration on earth zones.",
            "Poison": "+1 poison duration and +1 poison-zone duration.",
            "Light": "+3 healing and -1 MP on cleanse/guard/light skills.",
            "Shadow": "+2 damage against vulnerable/umbral targets.",
        }.get(subclass, "Elemental passive.")

    def class_element_recommendations(self, class_name: str) -> List[str]:
        class_data = self.class_defs().get(class_name, {})
        custom_recommendations = class_data.get("recommended_elements", [])
        if isinstance(custom_recommendations, (list, tuple)) and custom_recommendations:
            return [str(element) for element in custom_recommendations if str(element) in self.elemental_subclasses()]
        return {
            "Vanguard": ["Fire", "Earth", "Light"],
            "Ranger": ["Poison", "Shadow", "Storm", "Frost"],
            "Guardian": ["Earth", "Light", "Frost"],
            "Mystic": ["Fire", "Frost", "Storm", "Poison"],
            "Duelist": ["Storm", "Shadow", "Fire"],
            "Alchemist": ["Poison", "Frost", "Light", "Earth"],
        }.get(class_name, [])

    def build_synergy_tier(self, class_name: str, subclass: str) -> int:
        recs = self.class_element_recommendations(class_name)
        if not recs:
            return 0
        if subclass == recs[0]:
            return 3
        if subclass in recs:
            return 2
        # Adjacent/usable cross-pollination.
        flexible = {
            "Vanguard": ["Storm"],
            "Ranger": ["Fire"],
            "Guardian": ["Poison"],
            "Mystic": ["Light", "Shadow"],
            "Duelist": ["Poison"],
            "Alchemist": ["Fire", "Shadow"],
        }
        return 1 if subclass in flexible.get(class_name, []) else 0

    def build_synergy_rating(self, class_name: str, subclass: str) -> str:
        tier = self.build_synergy_tier(class_name, subclass)
        return {3: "Ideal", 2: "Strong", 1: "Useful", 0: "Neutral"}.get(tier, "Neutral")

    def build_synergy_note(self, class_name: str, subclass: str) -> str:
        notes = {
            ("Vanguard", "Fire"): "aggressive command pressure and burning lane control",
            ("Vanguard", "Earth"): "guard lines, roots, and chokepoint control",
            ("Vanguard", "Light"): "safer frontline support and cheaper guard tools",
            ("Ranger", "Poison"): "poison setup into Predator/Venom finishers",
            ("Ranger", "Shadow"): "vulnerable marks into precision damage",
            ("Ranger", "Storm"): "marking and exposed-target pressure",
            ("Ranger", "Frost"): "trap/root control and lane denial",
            ("Guardian", "Earth"): "tank control with longer roots and rough zones",
            ("Guardian", "Light"): "stronger healing, cleanse, and guard support",
            ("Guardian", "Frost"): "defensive root control",
            ("Mystic", "Fire"): "fire zones and burst spell pressure",
            ("Mystic", "Frost"): "root fields and safe control",
            ("Mystic", "Storm"): "vulnerable fields and combo casting",
            ("Mystic", "Poison"): "clouds, attrition, and zone persistence",
            ("Duelist", "Storm"): "fast exposed-target pressure",
            ("Duelist", "Shadow"): "vulnerable/finisher burst play",
            ("Duelist", "Fire"): "aggressive strike damage",
            ("Alchemist", "Poison"): "maximum flask/poison-zone identity",
            ("Alchemist", "Frost"): "sticky control flasks",
            ("Alchemist", "Light"): "utility support, cleanse, and recovery",
            ("Alchemist", "Earth"): "resin/root zone control",
        }
        return notes.get((class_name, subclass), "works, but does not strongly reinforce this class's main loop")

    def build_synergy_label(self, hero: Unit) -> str:
        class_name = self.hero_class(hero)
        subclass = self.hero_subclass(hero)
        recs = self.class_element_recommendations(class_name)
        rec_text = "/".join(recs[:4]) if recs else "Any"
        return f"{self.build_synergy_rating(class_name, subclass)} | Recommended: {rec_text} | {self.build_synergy_note(class_name, subclass)}"

    def record_build_synergy_use(self, hero: Unit, skill: Skill) -> None:
        if self.build_synergy_tier(self.hero_class(hero), self.hero_subclass(hero)) <= 0:
            return
        # Count actual casts, not menu previews.
        self.combat_stats["build_synergy_uses"] = self.combat_stats.get("build_synergy_uses", 0) + 1

    def cycle_current_hero_subclass(self, direction: int = 1) -> None:
        hero = self.current_class_hero()
        progress = self.ensure_progress_entry(hero)
        subclasses = self.elemental_subclasses()
        current = self.hero_subclass(hero)
        index = subclasses.index(current) if current in subclasses else 0
        progress["subclass"] = subclasses[(index + direction) % len(subclasses)]
        self.messages = [f"{hero.name}'s elemental subclass set to {progress['subclass']}."]

    def default_class_for_hero(self, hero_name: str) -> str:
        return {
            "Rook": "Vanguard",
            "Mira": "Ranger",
            "Brom": "Guardian",
            "Aria": "Mystic",
            "Nia": "Ranger",
            "Dax": "Vanguard",
            "Luma": "Mystic",
        }.get(hero_name, "Vanguard")

    def class_names(self) -> List[str]:
        return list(self.class_defs().keys())

    def skill_by_name(self, name: str) -> Optional[Skill]:
        return next((skill for skill in self.skills if skill.name == name), None)

    def class_tree_for(self, class_name: str) -> List[Tuple[str, int, str]]:
        return list(self.class_defs().get(class_name, {}).get("tree", []))

    def class_default_skills(self, class_name: str) -> List[str]:
        return list(self.class_defs().get(class_name, {}).get("default", ["Spark Shot"]))

    def class_mastery_skill(self, class_name: str) -> str:
        return str(self.class_defs().get(class_name, {}).get("mastery", ""))

    def class_mastery_progress(self, hero: Unit, class_name: Optional[str] = None) -> Tuple[int, int]:
        class_name = class_name or self.hero_class(hero)
        tree = self.class_tree_for(class_name)
        if not tree:
            return (0, 0)
        unlocks = set(self.class_unlocks(hero, class_name))
        ranks = self.skill_rank_map(hero, class_name)
        defaults = set(self.class_default_skills(class_name))
        mastered = 0
        for skill_name, _base_cost, _desc in tree:
            if skill_name in defaults:
                rank = int(ranks.get(skill_name, 1))
            elif skill_name in unlocks:
                rank = int(ranks.get(skill_name, 1))
            else:
                rank = 0
            if rank >= self.skill_max_rank(skill_name, class_name):
                mastered += 1
        return mastered, len(tree)

    def class_mastered(self, hero: Unit, class_name: Optional[str] = None) -> bool:
        mastered, total = self.class_mastery_progress(hero, class_name)
        return total > 0 and mastered >= total

    def class_mastery_label(self, hero: Unit, class_name: Optional[str] = None) -> str:
        class_name = class_name or self.hero_class(hero)
        art = self.class_mastery_skill(class_name)
        mastered, total = self.class_mastery_progress(hero, class_name)
        if not art:
            return "No mastery art"
        status = "UNLOCKED" if self.class_mastered(hero, class_name) else "locked"
        return f"{art} [{status}] {mastered}/{total} tree skills mastered"

    def class_desc(self, class_name: str) -> str:
        return str(self.class_defs().get(class_name, {}).get("desc", ""))

    def class_prereqs(self, class_name: str, skill_name: str) -> List[str]:
        prereqs = self.class_defs().get(class_name, {}).get("prereqs", {})
        return list(prereqs.get(skill_name, [])) if isinstance(prereqs, dict) else []

    def hero_class(self, hero: Unit) -> str:
        progress = self.ensure_progress_entry(hero)
        class_name = str(progress.get("class", self.default_class_for_hero(hero.name)))
        if class_name not in self.class_names():
            class_name = self.default_class_for_hero(hero.name)
            progress["class"] = class_name
        return class_name


    def class_unlocks(self, hero: Unit, class_name: Optional[str] = None) -> Set[str]:
        progress = self.ensure_progress_entry(hero)
        class_name = class_name or self.hero_class(hero)
        unlocks = progress.setdefault("class_unlocks", {})
        if not isinstance(unlocks, dict):
            unlocks = {}
            progress["class_unlocks"] = unlocks
        class_set = unlocks.setdefault(class_name, set())
        if not isinstance(class_set, set):
            class_set = set(class_set)
            unlocks[class_name] = class_set
        return class_set

    def skill_rank_map(self, hero: Unit, class_name: Optional[str] = None) -> Dict[str, int]:
        progress = self.ensure_progress_entry(hero)
        class_name = class_name or self.hero_class(hero)
        ranks = progress.setdefault("skill_ranks", {})
        if not isinstance(ranks, dict):
            ranks = {}
            progress["skill_ranks"] = ranks
        class_ranks = ranks.setdefault(class_name, {})
        if not isinstance(class_ranks, dict):
            class_ranks = dict(class_ranks)
            ranks[class_name] = class_ranks
        return class_ranks

    def skill_max_rank(self, skill_name: str, class_name: Optional[str] = None) -> int:
        if class_name and any(entry[0] == skill_name for entry in self.class_tree_for(class_name)):
            return 3
        return 1

    def skill_rank(self, hero: Unit, skill_name: str, class_name: Optional[str] = None) -> int:
        if class_name:
            if skill_name not in self.known_skill_names(hero):
                return 0
            return max(1, min(self.skill_max_rank(skill_name, class_name), int(self.skill_rank_map(hero, class_name).get(skill_name, 1))))

        if skill_name not in self.known_skill_names(hero):
            return 0

        best_rank = 1
        for candidate in self.hero_active_classes(hero):
            in_class = skill_name in self.class_default_skills(candidate) or skill_name in self.class_unlocks(hero, candidate) or skill_name == self.class_mastery_skill(candidate)
            if not in_class:
                continue
            rank = int(self.skill_rank_map(hero, candidate).get(skill_name, 1))
            best_rank = max(best_rank, min(self.skill_max_rank(skill_name, candidate), max(1, rank)))
        return best_rank

    def skill_rank_label(self, hero: Unit, skill_name: str, class_name: Optional[str] = None) -> str:
        class_name = class_name or self.hero_class(hero)
        rank = self.skill_rank(hero, skill_name, class_name)
        max_rank = self.skill_max_rank(skill_name, class_name)
        return f"R{rank}/{max_rank}" if max_rank > 1 else "R1"

    def skill_upgrade_cost(self, base_cost: int, current_rank: int) -> int:
        return base_cost + current_rank

    def effective_skill(self, hero: Unit, skill: Skill) -> Skill:
        rank = self.skill_rank(hero, skill.name)

        bonus = max(0, rank - 1)
        damage = skill.damage
        heal_amount = skill.heal_amount
        mp_amount = skill.mp_amount
        status_duration = skill.status_duration
        mp_cost = skill.mp_cost
        combo_damage_bonus = skill.combo_damage_bonus
        combo_heal_bonus = skill.combo_heal_bonus
        combo_ap_gain = skill.combo_ap_gain
        combo_mp_gain = skill.combo_mp_gain
        zone_duration = skill.zone_duration
        zone_damage = skill.zone_damage
        zone_status_duration = skill.zone_status_duration

        if skill.effect == "damage":
            damage += bonus * 2
            if skill.status:
                status_duration += bonus
            if combo_damage_bonus:
                combo_damage_bonus += bonus
            if combo_ap_gain and rank >= 3:
                combo_ap_gain += 1
            if combo_mp_gain:
                combo_mp_gain += bonus
        elif skill.effect == "heal":
            heal_amount += bonus * 4
            if combo_heal_bonus:
                combo_heal_bonus += bonus * 2
        elif skill.effect == "restore_mp":
            mp_amount += bonus * 3

        subclass = self.hero_subclass(hero)
        lname = skill.name.lower()
        if subclass == "Fire" and (skill.zone_type == "fire" or any(word in lname for word in ("fire", "flame", "cinder", "ignite", "inferno"))):
            damage += 1
            zone_damage += 1 if zone_duration else 0
        elif subclass == "Frost" and (skill.status == "root" or skill.zone_status == "root" or skill.zone_type == "frost" or any(word in lname for word in ("frost", "ice", "glacial"))):
            status_duration += 1 if skill.status == "root" else 0
            zone_status_duration += 1 if skill.zone_status == "root" else 0
        elif subclass == "Storm" and (skill.status == "vulnerable" or skill.zone_type == "storm" or any(word in lname for word in ("storm", "static", "shock", "thunder"))):
            damage += 1 if skill.effect == "damage" else 0
        elif subclass == "Earth" and (skill.status == "root" or skill.zone_type == "earth" or skill.effect == "guard"):
            if mp_cost > 0:
                mp_cost = max(0, mp_cost - 1)
            zone_status_duration += 1 if skill.zone_status == "root" else 0
        elif subclass == "Poison" and (skill.status == "poison" or skill.zone_status == "poison" or skill.zone_type == "poison" or any(word in lname for word in ("poison", "venom", "toxic", "spore"))):
            status_duration += 1 if skill.status == "poison" else 0
            zone_status_duration += 1 if skill.zone_status == "poison" else 0
            zone_duration += 1 if skill.zone_type == "poison" else 0
        elif subclass == "Light":
            if skill.effect == "heal":
                heal_amount += 3
            if skill.effect == "damage" and any(word in lname for word in ("light", "radiant", "solar", "sun")):
                damage += 1
            if skill.effect in ("cleanse", "guard") or skill.zone_type == "light" or any(word in lname for word in ("light", "radiant", "solar", "sun")):
                mp_cost = max(0, mp_cost - 1)
        elif subclass == "Shadow":
            if skill.status == "vulnerable" or skill.zone_status == "vulnerable" or skill.zone_type == "shadow" or "shadow" in lname or "umbral" in lname:
                damage += 2 if skill.effect == "damage" else 0

        class_name = self.hero_class(hero)
        tier = self.build_synergy_tier(class_name, subclass)
        if tier >= 2:
            if class_name == "Vanguard":
                if skill.effect == "guard":
                    mp_cost = max(0, mp_cost - 1)
                if skill.effect == "damage" and (skill.status in ("vulnerable", "root") or skill.combo_ap_gain or "Command" in skill.name or "Breaker" in skill.name):
                    damage += 1
            elif class_name == "Ranger":
                if skill.effect == "damage" and (skill.status or skill.shape == "multishot" or "Shot" in skill.name or "Trap" in skill.name):
                    damage += 1
                if skill.status in ("poison", "root", "vulnerable"):
                    status_duration += 1
            elif class_name == "Guardian":
                if skill.effect == "heal":
                    heal_amount += 2
                if skill.effect in ("heal", "guard", "cleanse") and mp_cost > 0:
                    mp_cost = max(0, mp_cost - 1)
                if skill.zone_status == "root":
                    zone_status_duration += 1
            elif class_name == "Mystic":
                if skill.zone_type:
                    zone_duration += 1
                    zone_damage += 1 if zone_damage else 0
                if skill.effect == "damage" and (skill.status or skill.zone_type):
                    damage += 1
            elif class_name == "Duelist":
                if skill.effect == "damage" and (skill.shape in ("point", "multishot") or skill.combo_any_status or skill.combo_guarded):
                    damage += 1
                if skill.combo_damage_bonus:
                    combo_damage_bonus += 1
            elif class_name == "Alchemist":
                if skill.zone_type:
                    zone_duration += 1
                if skill.status in ("poison", "root", "vulnerable"):
                    status_duration += 1
                if skill.zone_status:
                    zone_status_duration += 1
            elif bool(self.class_defs().get(class_name, {}).get("custom", False)):
                if skill.effect == "damage":
                    damage += 1
                elif skill.effect == "heal":
                    heal_amount += 2
                elif skill.effect in ("guard", "cleanse", "restore_mp") and mp_cost > 0:
                    mp_cost = max(0, mp_cost - 1)
        elif tier == 1:
            if skill.effect == "damage" and (skill.status or skill.zone_type):
                damage += 1

        if rank >= 3 and mp_cost > 0:
            mp_cost = max(0, mp_cost - 1)

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

    def known_skill_names(self, hero: Unit) -> List[str]:
        names: Set[str] = set()
        for class_name in self.hero_active_classes(hero):
            names.update(self.class_default_skills(class_name))
            names.update(self.class_unlocks(hero, class_name))
            mastery = self.class_mastery_skill(class_name)
            if mastery and self.class_mastered(hero, class_name):
                names.add(mastery)
        for subclass_skill in self.subclass_skill_names(self.hero_subclass(hero)):
            names.add(subclass_skill)
        ordered = [skill.name for skill in self.skills if skill.name in names]
        return ordered or ["Spark Shot"]


    def known_skill_summary(self, hero: Unit) -> str:
        parts = []
        class_name = self.hero_class(hero)
        for name in self.known_skill_names(hero):
            label = self.skill_rank_label(hero, name, class_name)
            parts.append(f"{name} {label}" if label != "R1" else name)
        return ", ".join(parts) if parts else "Spark Shot"

    def available_skills(self, hero: Optional[Unit] = None) -> List[Skill]:
        hero = hero or self.selected_hero
        known = set(self.known_skill_names(hero))
        return [self.effective_skill(hero, skill) for skill in self.skills if skill.name in known]

    def selected_skill(self, hero: Optional[Unit] = None) -> Skill:
        hero = hero or self.selected_hero
        skills = self.available_skills(hero)
        if not skills:
            fallback = self.skill_by_name("Spark Shot") or self.skills[0]
            return fallback
        self.skill_index %= len(skills)
        return skills[self.skill_index]

    def unlock_status_for_skill(self, hero: Unit, skill_name: str, class_name: Optional[str] = None) -> str:
        class_name = class_name or self.hero_class(hero)
        if skill_name in self.class_default_skills(class_name):
            return "default"
        if skill_name in self.class_unlocks(hero, class_name):
            return "known"
        missing = [req for req in self.class_prereqs(class_name, skill_name) if req not in self.class_unlocks(hero, class_name) and req not in self.class_default_skills(class_name)]
        if missing:
            return "needs " + "/".join(missing)
        return "locked"

    def hero_active_classes(self, hero: Unit) -> List[str]:
        progress = self.ensure_progress_entry(hero)
        valid = set(self.class_names())
        focus = self.hero_class(hero)
        raw = progress.setdefault("active_classes", [focus])
        if not isinstance(raw, list):
            raw = list(raw) if isinstance(raw, (set, tuple)) else [focus]
            progress["active_classes"] = raw
        cleaned: List[str] = []
        for class_name in raw:
            class_name = str(class_name)
            if class_name in valid and class_name not in cleaned:
                cleaned.append(class_name)
        if focus in valid and focus not in cleaned:
            cleaned.insert(0, focus)
        if not cleaned:
            cleaned = [self.default_class_for_hero(hero.name)]

        # Normalize legacy/direct state: mastered classes may remain selected,
        # but no character should retain more than 3 unmastered active classes.
        normalized: List[str] = []
        unmastered_count = 0
        for class_name in cleaned:
            if self.class_mastered(hero, class_name):
                normalized.append(class_name)
            elif unmastered_count < self.class_slot_limit():
                normalized.append(class_name)
                unmastered_count += 1

        if focus in valid and focus not in normalized:
            if self.class_mastered(hero, focus):
                normalized.insert(0, focus)
            else:
                mastered_part = [c for c in normalized if self.class_mastered(hero, c)]
                unmastered_part = [c for c in normalized if not self.class_mastered(hero, c) and c != focus]
                normalized = mastered_part + [focus] + unmastered_part[: max(0, self.class_slot_limit() - 1)]
        if not normalized:
            normalized = [self.default_class_for_hero(hero.name)]

        progress["active_classes"] = normalized
        if str(progress.get("class", "")) not in normalized:
            progress["class"] = normalized[0]
        return normalized

    def hero_unmastered_active_classes(self, hero: Unit) -> List[str]:
        return [class_name for class_name in self.hero_active_classes(hero) if not self.class_mastered(hero, class_name)]

    def class_slot_limit(self) -> int:
        return 3

    def class_slot_summary(self, hero: Unit) -> str:
        used = len(self.hero_unmastered_active_classes(hero))
        return f"{used}/{self.class_slot_limit()} unmastered classes"

    def can_add_active_class(self, hero: Unit, class_name: str) -> Tuple[bool, str]:
        if class_name in self.hero_active_classes(hero):
            return True, "already selected"
        if self.class_mastered(hero, class_name):
            return True, "mastered"
        used = len(self.hero_unmastered_active_classes(hero))
        if used >= self.class_slot_limit():
            return False, f"slot full ({used}/{self.class_slot_limit()} unmastered)"
        return True, "available"

    def focus_class_for_hero(self, hero: Unit, class_name: str) -> bool:
        if class_name not in self.class_names():
            self.messages = [f"Unknown class: {class_name}."]
            return False
        ok, reason = self.can_add_active_class(hero, class_name)
        if not ok:
            self.messages = [f"{hero.name} cannot select {class_name}: {reason}. Master a selected class to free a slot."]
            return False
        active = self.hero_active_classes(hero)
        if class_name not in active:
            active.append(class_name)
            self.messages = [f"{hero.name} selected {class_name}. {self.class_slot_summary(hero)}."]
        else:
            self.messages = [f"{hero.name} focused {class_name}."]
        progress = self.ensure_progress_entry(hero)
        progress["class"] = class_name
        self.class_skill_index = 0
        return True

    def class_status_label(self, hero: Unit, class_name: str) -> str:
        focus = self.hero_class(hero)
        active = self.hero_active_classes(hero)
        mastered = self.class_mastered(hero, class_name)
        if class_name == focus:
            return "Focused" if not mastered else "Mastered Focus"
        if class_name in active:
            return "Mastered" if mastered else "Selected"
        if mastered:
            return "Mastered"
        ok, _reason = self.can_add_active_class(hero, class_name)
        return "Available" if ok else "Slot Full"

    def class_index_for_hero(self, hero: Unit) -> int:
        names = self.class_names()
        focused = self.hero_class(hero)
        return names.index(focused) if focused in names else 0

    def sync_class_menu_to_current_hero(self) -> None:
        self.class_menu_class_index = self.class_index_for_hero(self.current_class_hero())
        self.class_skill_index = 0

    def selected_class_for_class_screen(self) -> str:
        names = self.class_names()
        if not names:
            return ""
        self.class_menu_class_index %= len(names)
        return names[self.class_menu_class_index]

    def class_screen_selected_hero_summary(self, hero: Unit) -> str:
        progress = self.ensure_progress_entry(hero)
        active = self.hero_active_classes(hero)
        mastered = [name for name in active if self.class_mastered(hero, name)]
        return f"Lv {int(progress['level'])} | SP {int(progress.get('skill_points', 0))} | {self.class_slot_summary(hero)} | Selected: {', '.join(active)}" + (f" | Mastered: {', '.join(mastered)}" if mastered else "")

    def current_class_hero(self) -> Unit:
        self.class_menu_hero_index %= len(self.heroes)
        return self.heroes[self.class_menu_hero_index]

    def current_class_tree_entry(self, hero: Optional[Unit] = None) -> Optional[Tuple[str, int, str]]:
        hero = hero or self.current_class_hero()
        tree = self.class_tree_for(self.hero_class(hero))
        if not tree:
            return None
        self.class_skill_index %= len(tree)
        return tree[self.class_skill_index]


    def cycle_current_hero_class(self, direction: int = 1) -> None:
        hero = self.current_class_hero()
        names = self.class_names()
        current = names.index(self.hero_class(hero)) if self.hero_class(hero) in names else 0
        target = names[(current + direction) % len(names)]
        self.focus_class_for_hero(hero, target)


    def unlock_current_class_skill(self) -> None:
        hero = self.current_class_hero()
        progress = self.ensure_progress_entry(hero)
        entry = self.current_class_tree_entry(hero)
        if not entry:
            self.messages = ["This class has no unlocks."]
            return

        skill_name, base_cost, _desc = entry
        class_name = self.hero_class(hero)
        was_mastered = self.class_mastered(hero, class_name)
        status = self.unlock_status_for_skill(hero, skill_name, class_name)
        sp = int(progress.get("skill_points", 0))

        if status.startswith("needs "):
            self.messages = [f"{skill_name} requires {status[len('needs '):]} first."]
            return

        if status == "locked":
            cost = int(base_cost)
            if sp < cost:
                self.messages = [f"Not enough SP. {skill_name} costs {cost} SP."]
                return
            progress["skill_points"] = sp - cost
            self.class_unlocks(hero, class_name).add(skill_name)
            self.skill_rank_map(hero, class_name)[skill_name] = 1
            self.messages = [f"{hero.name} unlocked {skill_name} R1 for {cost} SP."]
            if not was_mastered and self.class_mastered(hero, class_name):
                self.messages.append(f"{hero.name} mastered {class_name}! Mastery art unlocked: {self.class_mastery_skill(class_name)}.")
            return

        current_rank = self.skill_rank(hero, skill_name, class_name)
        max_rank = self.skill_max_rank(skill_name, class_name)
        if current_rank >= max_rank:
            self.messages = [f"{skill_name} is already max rank ({current_rank}/{max_rank})."]
            return

        cost = self.skill_upgrade_cost(int(base_cost), current_rank)
        if sp < cost:
            self.messages = [f"Not enough SP. {skill_name} R{current_rank + 1} costs {cost} SP."]
            return

        progress["skill_points"] = sp - cost
        self.skill_rank_map(hero, class_name)[skill_name] = current_rank + 1
        self.messages = [f"{hero.name} upgraded {skill_name} to R{current_rank + 1}/{max_rank} for {cost} SP."]
        if not was_mastered and self.class_mastered(hero, class_name):
            self.messages.append(f"{hero.name} mastered {class_name}! Mastery art unlocked: {self.class_mastery_skill(class_name)}.")

    def class_tree_entry_map(self, class_name: str) -> Dict[str, Tuple[int, str]]:
        return {skill_name: (int(base_cost), desc) for skill_name, base_cost, desc in self.class_tree_for(class_name)}

    def skill_respec_refund_for_rank(self, base_cost: int, rank: int) -> int:
        if rank <= 0:
            return 0
        refund = int(base_cost)
        for current_rank in range(1, max(1, rank)):
            refund += self.skill_upgrade_cost(int(base_cost), current_rank)
        return refund

    def class_sp_invested(self, hero: Unit, class_name: Optional[str] = None) -> int:
        class_name = class_name or self.hero_class(hero)
        entry_map = self.class_tree_entry_map(class_name)
        unlocks = set(self.class_unlocks(hero, class_name))
        ranks = self.skill_rank_map(hero, class_name)
        total = 0
        for skill_name, (base_cost, _desc) in entry_map.items():
            rank = int(ranks.get(skill_name, 0))
            # Unlocked skills should count as at least rank 1.
            if skill_name in unlocks:
                rank = max(rank, 1)
            # Default class skills can be upgraded if they appear in the tree.
            if skill_name in self.class_default_skills(class_name) and rank <= 1:
                continue
            if rank > 0:
                total += self.skill_respec_refund_for_rank(base_cost, rank)
        return total

    def respec_current_class(self) -> None:
        hero = self.current_class_hero()
        progress = self.ensure_progress_entry(hero)
        class_name = self.hero_class(hero)
        refund = self.class_sp_invested(hero, class_name)
        unlocks = self.class_unlocks(hero, class_name)
        ranks = self.skill_rank_map(hero, class_name)

        if refund <= 0 and not unlocks and not ranks:
            self.messages = [f"{hero.name}'s {class_name} has no spent SP to respec."]
            return

        had_mastery = self.class_mastered(hero, class_name)
        mastery_art = self.class_mastery_skill(class_name)
        if had_mastery and class_name in self.hero_active_classes(hero) and len(self.hero_unmastered_active_classes(hero)) >= self.class_slot_limit():
            self.messages = [f"Cannot respec mastered {class_name}: {hero.name} already has {self.class_slot_summary(hero)}. Master or avoid overfilling class slots first."]
            return

        # Current-class respec only: other class unlocks/ranks are untouched.
        unlocks.clear()
        ranks.clear()
        progress["skill_points"] = int(progress.get("skill_points", 0)) + refund
        self.class_skill_index = 0
        self.messages = [f"{hero.name} respecced {class_name}: refunded {refund} SP. Level, XP, gear, and other classes kept."]
        if had_mastery and mastery_art:
            self.messages.append(f"{mastery_art} removed until {class_name} is mastered again.")


    def main_menu_modes(self) -> List[str]:
        return ["home", "maps", "missions", "tutorial", "party", "companions", "loadout", "encounter", "objectives", "classes", "bestiary"]

    def cycle_main_menu_mode(self, direction: int = 1) -> None:
        modes = self.main_menu_modes()
        current = modes.index(self.main_menu_mode) if self.main_menu_mode in modes else 0
        self.main_menu_mode = modes[(current + direction) % len(modes)]

    def cost_text(self, cost: Dict[str, int]) -> str:
        return ", ".join(f"{k} x{v}" for k, v in cost.items()) if cost else "Free"

    def can_afford(self, cost: Dict[str, int]) -> bool:
        return all(self.campaign_inventory.get(k, 0) >= v for k, v in cost.items())

    def spend_cost(self, cost: Dict[str, int]) -> None:
        for key, amount in cost.items():
            self.campaign_inventory[key] = self.campaign_inventory.get(key, 0) - amount

    def equipment_slots(self) -> List[str]:
        return ["weapon", "armor", "charm"]

    def current_loadout_hero(self) -> Unit:
        self.loadout_hero_index %= len(self.heroes)
        return self.heroes[self.loadout_hero_index]

    def current_loadout_slot(self) -> str:
        slots = self.equipment_slots()
        self.loadout_slot_index %= len(slots)
        return slots[self.loadout_slot_index]

    def equipment_defs(self) -> Dict[str, Dict[str, Dict[str, object]]]:
        return data_equipment_defs()

    def default_equipment_for_hero(self, hero_name: str) -> Dict[str, str]:
        return {
            "Rook": {"weapon": "Iron Saber", "armor": "Traveler Clothes", "charm": "Plain Charm"},
            "Mira": {"weapon": "Scout Bow", "armor": "Traveler Clothes", "charm": "Plain Charm"},
            "Brom": {"weapon": "Guard Axe", "armor": "Traveler Clothes", "charm": "Plain Charm"},
            "Aria": {"weapon": "Light Wand", "armor": "Traveler Clothes", "charm": "Plain Charm"},
            "Nia": {"weapon": "Twin Daggers", "armor": "Traveler Clothes", "charm": "Plain Charm"},
            "Dax": {"weapon": "Stone Hammer", "armor": "Traveler Clothes", "charm": "Plain Charm"},
            "Luma": {"weapon": "Sun Rod", "armor": "Traveler Clothes", "charm": "Plain Charm"},
        }.get(hero_name, {
            "weapon": str(getattr(self, "party_progress", {}).get(hero_name, {}).get("custom_base_weapon", "Iron Saber")) if isinstance(getattr(self, "party_progress", {}).get(hero_name, {}), dict) else "Iron Saber",
            "armor": "Traveler Clothes",
            "charm": "Plain Charm",
        })

    def base_weapon_for_hero(self, hero_name: str) -> Weapon:
        if hero_name == "Mira":
            return Weapon("Scout Bow", 4, 2, 4)
        if hero_name == "Brom":
            return Weapon("Guard Axe", 5)
        if hero_name == "Aria":
            return Weapon("Light Wand", 3, 1, 4)
        if hero_name == "Nia":
            return Weapon("Twin Daggers", 4)
        if hero_name == "Dax":
            return Weapon("Stone Hammer", 6)
        if hero_name == "Luma":
            return Weapon("Sun Rod", 3, 1, 4)
        if hero_name in getattr(self, "party_progress", {}):
            progress = self.party_progress.get(hero_name, {})
            weapon_name = str(progress.get("custom_base_weapon", progress.get("equipped_gear", {}).get("weapon", "Iron Saber") if isinstance(progress.get("equipped_gear", {}), dict) else "Iron Saber"))
            damage = int(progress.get("custom_base_stats", {}).get("weapon_damage", 5)) if isinstance(progress.get("custom_base_stats", {}), dict) else 5
            profile = self.weapon_profile_for_name(weapon_name)
            return Weapon(weapon_name, damage, int(profile.get("range_min", 1)), int(profile.get("range_max", 1)))
        return Weapon("Iron Saber", 6)

    def equipment_allowed_for(self, hero_name: str, slot: str, gear_name: str) -> bool:
        gear = self.equipment_defs().get(slot, {}).get(gear_name)
        if not gear:
            return False
        heroes = gear.get("heroes", "all")
        if hero_name in getattr(self, "custom_companion_names", set()) and slot == "weapon":
            return True
        return heroes == "all" or hero_name in list(heroes)

    def equipment_options_for(self, hero: Unit, slot: str) -> List[str]:
        return [
            name for name in self.equipment_defs().get(slot, {})
            if self.equipment_allowed_for(hero.name, slot, name)
        ]

    def ensure_equipment_progress(self, hero: Unit) -> Dict[str, object]:
        return self.ensure_progress_entry(hero)

    def equipped_gear_name(self, hero: Unit, slot: str) -> str:
        progress = self.ensure_equipment_progress(hero)
        equipped = progress.get("equipped_gear", {})
        return str(equipped.get(slot, self.default_equipment_for_hero(hero.name)[slot]))

    def gear_unlocked(self, hero: Unit, slot: str, gear_name: str) -> bool:
        progress = self.ensure_equipment_progress(hero)
        unlocked = progress.get("unlocked_gear", {})
        slot_set = unlocked.get(slot, set()) if isinstance(unlocked, dict) else set()
        if not isinstance(slot_set, set):
            slot_set = set(slot_set)
        return gear_name in slot_set

    def gear_mod_text(self, gear: Dict[str, object]) -> str:
        parts: List[str] = []
        labels = [("dmg", "DMG"), ("hp", "HP"), ("mp", "MP"), ("move", "MV"), ("range_max", "RNG")]
        for key, label in labels:
            value = int(gear.get(key, 0))
            if value:
                sign = "+" if value > 0 else ""
                parts.append(f"{label}{sign}{value}")
        return ", ".join(parts) if parts else "no stat change"

    def hero_equipment_summary(self, hero: Unit) -> str:
        return " / ".join(self.equipped_gear_name(hero, slot) for slot in self.equipment_slots())

    def equipment_total_mods(self, hero: Unit) -> Dict[str, int]:
        mods = {"dmg": 0, "hp": 0, "mp": 0, "move": 0, "range_max": 0}
        defs = self.equipment_defs()
        for slot in self.equipment_slots():
            name = self.equipped_gear_name(hero, slot)
            gear = defs.get(slot, {}).get(name, {})
            for key in mods:
                mods[key] += int(gear.get(key, 0))
        return mods

    def apply_equipment_to_hero(self, hero: Unit) -> None:
        progress = self.ensure_progress_entry(hero)
        mods = self.equipment_total_mods(hero)
        base_weapon = self.base_weapon_for_hero(hero.name)
        weapon_name = self.equipped_gear_name(hero, "weapon")
        profile = self.weapon_profile_for_name(weapon_name)
        range_min = int(profile.get("range_min", base_weapon.range_min))
        range_max = int(profile.get("range_max", base_weapon.range_max))
        aoe_radius = int(profile.get("aoe_radius", base_weapon.aoe_radius))
        hero.weapon = Weapon(
            weapon_name,
            max(0, base_weapon.damage + int(progress.get("damage_bonus", 0)) + mods["dmg"]),
            range_min,
            max(range_min, range_max + mods["range_max"]),
            aoe_radius,
            str(profile.get("shape", "point")),
            str(profile.get("type", "physical")),
            str(profile.get("status", "")),
            int(profile.get("status_duration", 0)),
            int(profile.get("width", 1)),
            int(profile.get("shots", 1)),
            str(profile.get("trait", "")),
        )
        hero.max_hp = max(1, self.base_hero_stat(hero.name, "max_hp") + int(progress.get("hp_bonus", 0)) + mods["hp"])
        hero.max_mp = max(0, self.base_hero_stat(hero.name, "max_mp") + int(progress.get("mp_bonus", 0)) + mods["mp"])
        hero.move_range = max(1, self.base_hero_stat(hero.name, "move_range") + mods["move"])


    def apply_equipment_unlock_or_equip(self, option: Dict[str, object]) -> None:
        hero = next((h for h in self.heroes if h.name == option.get("hero")), None)
        if not hero:
            self.messages = ["Unknown hero for equipment."]
            return
        slot = str(option.get("slot"))
        gear_name = str(option.get("gear"))
        defs = self.equipment_defs()
        gear = defs.get(slot, {}).get(gear_name)
        if not gear or not self.equipment_allowed_for(hero.name, slot, gear_name):
            self.messages = [f"{gear_name} cannot be equipped by {hero.name}."]
            return

        progress = self.ensure_equipment_progress(hero)
        unlocked = progress["unlocked_gear"][slot]
        equipped = progress["equipped_gear"]
        if gear_name not in unlocked:
            cost = dict(gear.get("cost", {}))
            if not self.can_afford(cost):
                self.messages = [f"Not enough materials for {gear_name}. Need {self.cost_text(cost)}."]
                return
            self.spend_cost(cost)
            unlocked.add(gear_name)
            equipped[slot] = gear_name
            self.apply_progress_to_current_heroes()
            self.messages = [f"Unlocked and equipped {gear_name} for {hero.name}. {self.cost_text(cost)} spent."]
            return

        equipped[slot] = gear_name
        self.apply_progress_to_current_heroes()
        self.messages = [f"{hero.name} equipped {gear_name}."]

    def preview_weapon_for_custom(self, gear_name: str, base_damage: int = 5) -> Weapon:
        profile = self.weapon_profile_for_name(gear_name)
        return Weapon(
            gear_name,
            int(base_damage) + int(self.equipment_defs().get("weapon", {}).get(gear_name, {}).get("dmg", 0)),
            int(profile.get("range_min", 1)),
            int(profile.get("range_max", 1)) + int(self.equipment_defs().get("weapon", {}).get(gear_name, {}).get("range_max", 0)),
            int(profile.get("aoe_radius", 0)),
            str(profile.get("shape", "point")),
            str(profile.get("type", "physical")),
            str(profile.get("status", "")),
            int(profile.get("status_duration", 0)),
            int(profile.get("width", 1)),
            int(profile.get("shots", 1)),
            str(profile.get("trait", "")),
        )

    def preview_weapon_for_gear(self, hero: Unit, gear_name: str) -> Weapon:
        progress = self.ensure_progress_entry(hero)
        mods = self.equipment_total_mods(hero)
        # Remove currently-equipped weapon's mods and add candidate weapon's mods.
        current = self.equipped_gear_name(hero, "weapon")
        defs = self.equipment_defs().get("weapon", {})
        current_gear = defs.get(current, {})
        candidate = defs.get(gear_name, {})
        adjusted_mods = dict(mods)
        for key in ("dmg", "range_max"):
            adjusted_mods[key] = int(adjusted_mods.get(key, 0)) - int(current_gear.get(key, 0)) + int(candidate.get(key, 0))
        base_weapon = self.base_weapon_for_hero(hero.name)
        profile = self.weapon_profile_for_name(gear_name)
        range_min = int(profile.get("range_min", base_weapon.range_min))
        range_max = int(profile.get("range_max", base_weapon.range_max))
        return Weapon(
            gear_name,
            max(0, base_weapon.damage + int(progress.get("damage_bonus", 0)) + int(adjusted_mods.get("dmg", 0))),
            range_min,
            max(range_min, range_max + int(adjusted_mods.get("range_max", 0))),
            int(profile.get("aoe_radius", base_weapon.aoe_radius)),
            str(profile.get("shape", "point")),
            str(profile.get("type", "physical")),
            str(profile.get("status", "")),
            int(profile.get("status_duration", 0)),
            int(profile.get("width", 1)),
            int(profile.get("shots", 1)),
            str(profile.get("trait", "")),
        )

    def loadout_options(self) -> List[Dict[str, object]]:
        options: List[Dict[str, object]] = [
            {"label": "Upgrade Rook weapon", "kind": "hero_damage", "hero": "Rook", "cost": {"Coin": 12, "Shard": 1}, "desc": "Rook weapon damage +1."},
            {"label": "Upgrade Mira bow", "kind": "hero_damage", "hero": "Mira", "cost": {"Coin": 10, "Fang": 1}, "desc": "Mira weapon damage +1."},
            {"label": "Upgrade Brom axe", "kind": "hero_damage", "hero": "Brom", "cost": {"Coin": 10, "Stone": 1}, "desc": "Brom weapon damage +1."},
            {"label": "Upgrade Aria wand", "kind": "hero_damage", "hero": "Aria", "cost": {"Coin": 10, "Shard": 1}, "desc": "Aria weapon damage +1."},
            {"label": "Train party endurance", "kind": "party_hp", "cost": {"Coin": 16, "Hide": 2}, "desc": "All heroes gain +2 max HP."},
            {"label": "Train party focus", "kind": "party_mp", "cost": {"Coin": 12, "Tonic": 2}, "desc": "All heroes gain +1 max MP."},
            {"label": "Stock Potions", "kind": "stock_item", "item": "Potion", "cost": {"Coin": 4, "Tonic": 1}, "desc": "+1 starting Potion for each active hero."},
            {"label": "Stock Ethers", "kind": "stock_item", "item": "Ether", "cost": {"Coin": 6, "Shard": 1}, "desc": "+1 starting Ether for each active hero."},
            {"label": "Stock Cleanse Kits", "kind": "stock_item", "item": "Cleanse Kit", "cost": {"Coin": 6, "Spore Cap": 1}, "desc": "+1 starting Cleanse Kit for each active hero."},
            {"label": "Stock Guard Tonics", "kind": "stock_item", "item": "Guard Tonic", "cost": {"Coin": 6, "Hide": 1}, "desc": "+1 starting Guard Tonic for each active hero."},
            {"label": "Stock Throwing Knives", "kind": "stock_item", "item": "Throwing Knife", "cost": {"Coin": 5, "Fang": 1}, "desc": "+1 starting Throwing Knife for each active hero."},
            {"label": "Stock Fire Bombs", "kind": "stock_item", "item": "Fire Bomb", "cost": {"Coin": 10, "Gel": 1, "Shard": 1}, "desc": "+1 starting Fire Bomb for each active hero."},
        ]
        hero = self.current_loadout_hero()
        slot = self.current_loadout_slot()
        defs = self.equipment_defs().get(slot, {})
        for gear_name in self.equipment_options_for(hero, slot):
            gear = defs.get(gear_name, {})
            cost = dict(gear.get("cost", {}))
            profile_note = ""
            if slot == "weapon":
                temp_weapon = self.preview_weapon_for_gear(hero, gear_name)
                profile_note = " | Attack: " + self.weapon_profile_label(temp_weapon)
            options.append({
                "label": f"Equip {gear_name}",
                "kind": "equip_gear",
                "hero": hero.name,
                "slot": slot,
                "gear": gear_name,
                "cost": cost,
                "desc": f"{gear.get('desc', '')} [{self.gear_mod_text(gear)}]{profile_note}",
            })
        return options

    def loadout_status_for_option(self, option: Dict[str, object]) -> str:
        kind = option["kind"]
        if kind == "hero_damage":
            hero_name = str(option["hero"])
            progress = self.party_progress.get(hero_name, {})
            return f"current DMG+{int(progress.get('damage_bonus', 0))}"
        if kind == "party_hp":
            total = sum(self.party_progress.get(h.name, {}).get("hp_bonus", 0) for h in self.heroes)
            return f"party HP bonus total +{total}"
        if kind == "party_mp":
            total = sum(self.party_progress.get(h.name, {}).get("mp_bonus", 0) for h in self.heroes)
            return f"party MP bonus total +{total}"
        if kind == "stock_item":
            item = str(option["item"])
            return f"starting {item} +{self.item_loadout_bonus.get(item, 0)}"
        if kind == "equip_gear":
            hero = next((h for h in self.heroes if h.name == option.get("hero")), None)
            if not hero:
                return "unknown hero"
            slot = str(option.get("slot"))
            gear_name = str(option.get("gear"))
            equipped = self.equipped_gear_name(hero, slot) == gear_name
            unlocked = self.gear_unlocked(hero, slot, gear_name)
            if equipped:
                return "equipped"
            if unlocked:
                return "unlocked; Enter equips"
            return "locked; Enter unlocks+equips"
        return ""

    def apply_progress_to_current_heroes(self) -> None:
        for hero in self.heroes:
            progress = self.ensure_progress_entry(hero)
            hero.level = int(progress["level"])
            hero.xp = int(progress["xp"])
            self.apply_equipment_to_hero(hero)
            hero.hp = min(hero.hp, hero.max_hp)
            hero.mp = min(hero.mp, hero.max_mp)

    def apply_loadout_option(self) -> None:
        options = self.loadout_options()
        option = options[self.loadout_menu_index % len(options)]
        kind = option["kind"]
        if kind == "equip_gear":
            self.apply_equipment_unlock_or_equip(option)
            return

        cost = dict(option["cost"])
        if not self.can_afford(cost):
            self.messages = [f"Not enough materials for {option['label']}. Need {self.cost_text(cost)}."]
            return

        self.spend_cost(cost)
        if kind == "hero_damage":
            hero_name = str(option["hero"])
            hero = next((h for h in self.heroes if h.name == hero_name), None)
            if hero:
                progress = self.ensure_progress_entry(hero)
                progress["damage_bonus"] += 1
                self.apply_progress_to_current_heroes()
                self.messages = [f"{hero_name}'s weapon improved. {self.cost_text(cost)} spent."]
                return
        elif kind == "party_hp":
            for hero in self.heroes:
                self.ensure_progress_entry(hero)["hp_bonus"] += 2
            self.apply_progress_to_current_heroes()
            self.messages = [f"Party endurance improved. {self.cost_text(cost)} spent."]
            return
        elif kind == "party_mp":
            for hero in self.heroes:
                self.ensure_progress_entry(hero)["mp_bonus"] += 1
            self.apply_progress_to_current_heroes()
            self.messages = [f"Party focus improved. {self.cost_text(cost)} spent."]
            return
        elif kind == "stock_item":
            item = str(option["item"])
            self.item_loadout_bonus[item] = self.item_loadout_bonus.get(item, 0) + 1
            self.messages = [f"Starting {item} stock increased. {self.cost_text(cost)} spent."]
            return

        self.messages = ["That loadout option is not implemented."]

    def loadout_stock_text(self) -> str:
        shown = [(k, v) for k, v in self.item_loadout_bonus.items() if v > 0]
        return ", ".join(f"{k} +{v}" for k, v in shown) if shown else "No extra starting stock"

    def enemy_roster_names(self) -> List[str]:
        return list(self.base_enemy_names)

    def strip_copy_suffix(self, name: str) -> str:
        parts = name.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0]
        return name

    def enemy_is_elite_name(self, name: str) -> bool:
        return self.strip_copy_suffix(name).startswith("Elite ")

    def enemy_base_name(self, name: str) -> str:
        base = self.strip_copy_suffix(name)
        if base.startswith("Elite "):
            base = base[len("Elite "):]
        return base

    def enemy_is_boss_name(self, name: str) -> bool:
        return self.enemy_base_name(name) in getattr(self, "boss_enemy_names", set())

    def elite_name_for_base(self, base_name: str, copy_index: int = 1) -> str:
        return f"Elite {base_name}" if copy_index == 1 else f"Elite {base_name} {copy_index}"

    def enemy_by_name(self, name: str) -> Optional[Unit]:
        exact = next((enemy for enemy in self.enemies if enemy.name == name), None)
        if exact:
            return exact
        base = self.enemy_base_name(name)
        return next((enemy for enemy in self.enemies if enemy.name == base), None)

    def max_count_for_enemy(self, base_name: str) -> int:
        return 1 if self.enemy_is_boss_name(base_name) else self.enemy_max_count

    def counts_from_names(self, names: Iterable[str]) -> Dict[str, int]:
        counts = {name: 0 for name in getattr(self, "base_enemy_names", [])}
        for name in names:
            if self.enemy_is_elite_name(name):
                continue
            base = self.enemy_base_name(name)
            if base in counts:
                counts[base] += 1
        return counts

    def elite_counts_from_names(self, names: Iterable[str]) -> Dict[str, int]:
        counts = {name: 0 for name in getattr(self, "base_enemy_names", [])}
        for name in names:
            if not self.enemy_is_elite_name(name):
                continue
            base = self.enemy_base_name(name)
            if base in counts and not self.enemy_is_boss_name(base):
                counts[base] += 1
        return counts

    def enemy_instance_names_for_counts(self, counts: Dict[str, int], elite: bool = False) -> List[str]:
        selected: List[str] = []
        for base_name in self.enemy_roster_names():
            limit = self.max_count_for_enemy(base_name)
            if elite and self.enemy_is_boss_name(base_name):
                continue
            count = max(0, min(limit, counts.get(base_name, 0)))
            for copy_index in range(1, count + 1):
                if elite:
                    selected.append(self.elite_name_for_base(base_name, copy_index))
                else:
                    selected.append(base_name if copy_index == 1 else f"{base_name} {copy_index}")
        return selected


    def encounter_reward_estimate(self, names: Optional[Iterable[str]] = None) -> Dict[str, int]:
        selected = list(names if names is not None else self.selected_custom_enemy_names())
        rewards: Dict[str, int] = {}
        for name in selected:
            for key, amount in self.enemy_reward_preview(name).items():
                rewards[key] = rewards.get(key, 0) + amount
        return rewards

    def enemy_threat_value(self, name: str) -> int:
        enemy = self.enemy_by_name(name)
        if not enemy:
            return 0
        role_weight = {
            "dummy": 0,
            "skirmisher": 8,
            "brute": 15,
            "controller": 13,
            "ranged": 12,
            "pouncer": 11,
            "guardian": 12,
            "blighter": 10,
            "boss": 32,
        }.get(enemy.role, 8)
        threat = enemy.max_hp // 2 + enemy.weapon.damage * 3 + enemy.move_range + role_weight
        base = self.enemy_base_name(name)
        signature_bonus = {
            "Wolf": 8,
            "Crow": 6,
            "Slime": 5,
            "Sporeling": 8,
            "Old Briarthorn": 24,
            "Razor Hare": 7,
            "Ember Imp": 8,
            "Frost Moth": 11,
            "Burrower": 10,
            "Thornback": 10,
            "Shield Guard": 6,
            "Wisp": 8,
            "Marsh Toad": 6,
            "Training Dummy": -15,
        }.get(base, 0)
        threat += signature_bonus
        if name.startswith("Elite "):
            threat += 12
        if self.enemy_is_boss_name(name):
            threat += 25
        return threat

    def encounter_threat_value(self, names: Optional[Iterable[str]] = None) -> int:
        selected = list(names if names is not None else self.selected_custom_enemy_names())
        return sum(self.enemy_threat_value(name) for name in selected)

    def encounter_threat_label(self, value: Optional[int] = None) -> str:
        v = self.encounter_threat_value() if value is None else value
        if v < 70:
            return f"{v} Low"
        if v < 120:
            return f"{v} Medium"
        if v < 180:
            return f"{v} High"
        return f"{v} Extreme"

    def ordered_enemy_names(self, names: Iterable[str]) -> List[str]:
        roster_order = {name: i for i, name in enumerate(self.enemy_roster_names())}
        def sort_key(name: str):
            base = self.enemy_base_name(name)
            elite_offset = 0.5 if self.enemy_is_elite_name(name) else 0
            copy = 1
            parts = name.rsplit(" ", 1)
            if len(parts) == 2 and parts[1].isdigit():
                copy = int(parts[1])
            return (roster_order.get(base, 99), elite_offset, copy)
        return sorted(set(names), key=sort_key)


    def selected_custom_enemy_names(self) -> List[str]:
        normal = self.enemy_instance_names_for_counts(self.custom_enemy_counts, elite=False)
        elites = self.enemy_instance_names_for_counts(self.custom_elite_counts, elite=True)
        return self.ordered_enemy_names(normal + elites)

    def selected_custom_enemy_summary(self) -> str:
        parts = []
        for name in self.enemy_roster_names():
            normal = self.custom_enemy_counts.get(name, 0)
            elite = self.custom_elite_counts.get(name, 0)
            if normal > 0:
                parts.append(f"{name} x{normal}")
            if elite > 0:
                parts.append(f"Elite {name} x{elite}")
        return ", ".join(parts) if parts else "None"

    def custom_enemy_total(self) -> int:
        return sum(self.custom_enemy_counts.values()) + sum(self.custom_elite_counts.values())

    def custom_enemy_cap_reached(self) -> bool:
        return self.custom_enemy_total() >= self.custom_enemy_total_cap

    def sync_custom_encounter_to_map(self) -> None:
        if not any(self.custom_enemy_counts.values()) and not any(self.custom_elite_counts.values()):
            self.custom_enemy_counts = self.counts_from_names(self.enemy_loadout_for_map(self.maps[self.main_menu_index][0]))
            self.custom_elite_counts = {name: 0 for name in self.enemy_roster_names()}

    def reset_custom_encounter_to_map(self) -> None:
        selected_map = self.maps[self.main_menu_index][0]
        self.custom_enemy_counts = self.counts_from_names(self.enemy_loadout_for_map(selected_map))
        self.custom_elite_counts = {name: 0 for name in self.enemy_roster_names()}
        self.messages = [f"Encounter reset to {selected_map}'s default loadout."]

    def mission_builtin_presets(self) -> List[Dict[str, object]]:
        return data_mission_builtin_presets()

    def mission_presets(self) -> List[Dict[str, object]]:
        return self.mission_builtin_presets() + list(self.user_mission_presets)

    def clean_builder_name(self, value: str, fallback: str = "") -> str:
        raw = str(value)
        # Keep names simple and terminal-safe.
        cleaned = re.sub(r"[^A-Za-z0-9 _'\-]", "", raw)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = cleaned[:28].strip()
        if not cleaned:
            cleaned = fallback.strip()[:28]
        return cleaned

    def title_builder_name(self, value: str) -> str:
        cleaned = self.clean_builder_name(value)
        if not cleaned:
            return ""
        # KeyReader normalizes letters to lowercase, so title casing keeps
        # typed names readable in the UI.
        return " ".join(part[:1].upper() + part[1:] for part in cleaned.split(" "))

    def current_name_entry_value(self, target: str) -> str:
        if target == "mission":
            return self.mission_builder_custom_name or self.mission_name_presets()[self.mission_builder_name_index % len(self.mission_name_presets())]
        if target == "companion":
            return self.companion_editor_custom_name or self.companion_name_presets()[self.companion_editor_name_index % len(self.companion_name_presets())]
        return ""

    def begin_name_entry(self, target: str) -> None:
        self.text_entry_target = target
        self.text_entry_buffer = self.current_name_entry_value(target)
        label = "mission" if target == "mission" else "companion"
        self.messages = [f"Typing custom {label} name. Enter confirm, Backspace delete, Esc cancel."]

    def confirm_name_entry(self) -> None:
        target = self.text_entry_target or ""
        fallback = self.current_name_entry_value(target)
        name = self.title_builder_name(self.text_entry_buffer) or fallback
        if target == "mission":
            self.mission_builder_custom_name = name
            self.messages = [f"Mission name set to {name}."]
        elif target == "companion":
            self.companion_editor_custom_name = name
            self.messages = [f"Companion name set to {name}."]
        self.text_entry_target = None
        self.text_entry_buffer = ""

    def cancel_name_entry(self) -> None:
        self.messages = ["Name entry canceled."]
        self.text_entry_target = None
        self.text_entry_buffer = ""

    def handle_name_entry_key(self, key: str) -> None:
        if key in ("ENTER",):
            self.confirm_name_entry()
            return
        if key in ("ESC",):
            self.cancel_name_entry()
            return
        if key == "BACKSPACE":
            self.text_entry_buffer = self.text_entry_buffer[:-1]
            return
        if key == "SPACE":
            if len(self.text_entry_buffer) < 28:
                self.text_entry_buffer += " "
            return
        if len(key) == 1 and key in "abcdefghijklmnopqrstuvwxyz0123456789-_'.": 
            if len(self.text_entry_buffer) < 28:
                self.text_entry_buffer += key
            return

    def render_name_entry(self, width: int) -> None:
        target = self.text_entry_target or ""
        label = "Mission Name" if target == "mission" else "Companion Name"
        clear_screen()
        print(c("ASCII Tactical Combat Prototype v113", Style.BOLD, Style.BRIGHT_WHITE))
        print(c("TYPE CUSTOM NAME", Style.BOLD, Style.BRIGHT_YELLOW))
        print("-" * width)
        print(label)
        print()
        buffer = self.text_entry_buffer
        cursor = "_" if int(time.time() * 2) % 2 == 0 else " "
        for line in wrap_labeled("> ", buffer + cursor, width):
            print(line)
        print()
        print("Allowed: letters, numbers, space, hyphen, underscore, apostrophe, period")
        print("Enter confirm | Backspace delete | Esc cancel")

    def mission_name_presets(self) -> List[str]:
        return [
            "Custom Patrol",
            "Mine Errand",
            "Forage Trouble",
            "Farm Defense",
            "Lost Villager",
            "Ruined Gate",
            "Supply Run",
            "Monster Nest",
            "Caravan Trouble",
            "Stronghold Sweep",
        ]

    def mission_enemy_themes(self) -> List[Tuple[str, List[str], str]]:
        return [
            ("Farm Pests", ["Slime", "Crow", "Razor Hare", "Sporeling"], "Gel, feathers, seeds"),
            ("Mine Monsters", ["Rockback", "Burrower", "Wisp", "Shield Guard"], "Stone, shards, shells"),
            ("Wilderness Beasts", ["Wolf", "Boar", "Vine", "Razor Hare"], "Hide, fang, roots"),
            ("Road Bandits", ["Bandit", "Shield Guard", "Crow", "Ember Imp"], "Coins and supplies"),
            ("Swamp Trouble", ["Marsh Toad", "Sporeling", "Slime", "Vine"], "Toad oil, spores, gel"),
            ("Stronghold Squad", ["Shield Guard", "Bandit", "Thornback", "Burrower"], "Fragments and relics"),
            ("Frost Route", ["Wisp", "Frost Moth", "Wolf", "Rockback"], "Frost wings and sparks"),
            ("Boss Test", ["Old Briarthorn", "Sporeling", "Vine"], "Relic cache and boss loot"),
        ]

    def mission_builder_fields(self) -> List[str]:
        return ["Name", "Map", "Enemy Theme", "Objective", "Parameter"]

    def map_index_for_name(self, map_name: str) -> int:
        for i, (name, _grid, _pos) in enumerate(self.maps):
            if name == map_name:
                return i
        return 0

    def objective_params_for_mode(self, objective: str, parameter: int) -> Dict[str, int]:
        if objective == "Survive":
            return {"round_goal": max(2, min(12, parameter))}
        if objective == "Hold Zone":
            return {"hold_goal": max(1, min(6, parameter))}
        if objective == "Destroy Objects":
            return {"object_goal": max(1, min(5, parameter))}
        return {}

    def objective_params_for_current_setup(self) -> Dict[str, int]:
        if self.objective_mode == "Survive":
            return {"round_goal": self.objective_round_goal}
        if self.objective_mode == "Hold Zone":
            return {"hold_goal": self.objective_hold_goal}
        if self.objective_mode == "Destroy Objects":
            return {"object_goal": self.objective_object_goal}
        return {}

    def battle_request_mission_id(self, mission_name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", mission_name.lower()).strip("-")
        return slug or "mission"

    def active_party_request_ids(self) -> List[str]:
        return [hero.name for hero in self.heroes if hero.name in self.active_party_names]

    def split_enemy_request_names(self, names: Iterable[str]) -> Tuple[Dict[str, int], List[str]]:
        counts = {name: 0 for name in self.enemy_roster_names()}
        explicit: List[str] = []
        for raw_name in names:
            name = str(raw_name)
            base = self.enemy_base_name(name)
            if self.enemy_is_elite_name(name) or base not in counts:
                explicit.append(name)
            else:
                counts[base] += 1
        return {name: count for name, count in counts.items() if count > 0}, explicit

    def create_battle_request_from_mission(self, preset: Dict[str, object]) -> BattleRequest:
        map_name = str(preset.get("map", self.map_name))
        enemies = self.mission_enemy_names(preset)
        enemy_counts, enemy_group = self.split_enemy_request_names(enemies)
        objective = str(preset.get("objective", "Defeat All"))
        objective_params = {key: preset[key] for key in ("round_goal", "hold_goal", "object_goal") if key in preset}
        mission_name = str(preset.get("name", "Mission"))
        return BattleRequest(
            source="mission",
            map_id=self.map_index_for_name(map_name),
            map_name=map_name,
            enemy_counts=enemy_counts,
            enemy_group=enemy_group,
            objective=objective,
            objective_params=objective_params,
            party_ids=self.active_party_request_ids(),
            mission_id=self.battle_request_mission_id(mission_name),
            mission_name=mission_name,
            reward_theme=str(preset.get("theme", "")),
            difficulty_hint=f"threat:{self.mission_threat_value(preset)}",
            return_context={"mission_name": mission_name, "map_name": map_name},
            world_flags_on_victory=[f"mission:{self.battle_request_mission_id(mission_name)}:cleared"],
            world_flags_on_defeat=[f"mission:{self.battle_request_mission_id(mission_name)}:failed"],
        )

    def create_battle_request_from_encounter_builder(self) -> BattleRequest:
        map_name = self.maps[self.main_menu_index % len(self.maps)][0]
        normal_counts = {name: count for name, count in self.custom_enemy_counts.items() if count > 0}
        enemy_group: List[str] = []
        for name, count in self.custom_elite_counts.items():
            for copy_index in range(1, max(0, int(count)) + 1):
                enemy_group.append(self.elite_name_for_base(name, copy_index))
        return BattleRequest(
            source="encounter_builder",
            map_id=self.main_menu_index % len(self.maps),
            map_name=map_name,
            enemy_counts=normal_counts,
            enemy_group=enemy_group,
            objective=self.objective_mode,
            objective_params=self.objective_params_for_current_setup(),
            party_ids=self.active_party_request_ids(),
            mission_name=self.current_mission_name,
            reward_theme=self.current_mission_reward_theme,
            difficulty_hint=f"threat:{self.encounter_threat_value(self.selected_custom_enemy_names())}",
            return_context={"map_name": map_name},
            is_debug=True,
        )

    def create_battle_request_from_selected_setup(self) -> BattleRequest:
        if self.pending_mission_preset:
            return self.create_battle_request_from_mission(self.pending_mission_preset)
        if self.custom_encounter_enabled or self.custom_enemy_total() > 0:
            return self.create_battle_request_from_encounter_builder()

        map_name = self.maps[self.main_menu_index % len(self.maps)][0]
        enemy_counts, enemy_group = self.split_enemy_request_names(self.enemy_loadout_for_map(map_name))
        return BattleRequest(
            source="default_setup",
            map_id=self.main_menu_index % len(self.maps),
            map_name=map_name,
            enemy_counts=enemy_counts,
            enemy_group=enemy_group,
            objective=self.objective_mode,
            objective_params=self.objective_params_for_current_setup(),
            party_ids=self.active_party_request_ids(),
            return_context={"map_name": map_name},
            is_debug=True,
        )

    def start_battle_from_request(self, request: BattleRequest) -> None:
        from .main import configure_game_from_request

        configure_game_from_request(self, request)
        self.remember_battle_request(request)
        self.in_main_menu = False
        self.state = "command"
        self.turn = "hero"
        party = ", ".join(self.active_party_names_list())
        enemies = self.selected_custom_enemy_summary() if self.custom_encounter_enabled else ", ".join(self.enemy_loadout_for_map(self.map_name))
        start_msg = f"Request {request.request_id}: {self.map_name}. Objective: {self.objective_mode}. Party: {party}. Enemies: {enemies}."
        briefing = str(request.return_context.get("encounter_briefing", "") or "")
        self.messages = [clip(line, 78) for line in [briefing, start_msg] if line]
        self.combat_log = []
        self.combat_log_scroll = 0
        if briefing:
            self.add_combat_log_entry(briefing, category="BATTLE")
        self.add_combat_log_entry(start_msg, category="BATTLE")

    def remember_battle_request(self, request: BattleRequest) -> None:
        self.current_battle_request = request
        self.battle_request_id = request.request_id
        self.battle_source = request.source
        self.battle_return_context = dict(request.return_context)
        self.battle_world_flags = dict(request.world_flags)
        self.current_mission_id = str(request.mission_id or "")

    def build_battle_result(self, request: BattleRequest, outcome: str) -> BattleResult:
        return battle_result_from_game(self, outcome, request)

    def objective_parameter_text_for_draft(self, draft: Dict[str, object]) -> str:
        objective = str(draft.get("objective", "Defeat All"))
        if objective == "Survive":
            return f"Rounds: {draft.get('round_goal', self.mission_builder_parameter)}"
        if objective == "Hold Zone":
            return f"Hold ticks: {draft.get('hold_goal', self.mission_builder_parameter)}"
        if objective == "Destroy Objects":
            return f"Objects: {draft.get('object_goal', self.mission_builder_parameter)}"
        return "No parameter"

    def mission_builder_draft(self) -> Dict[str, object]:
        preset_name = self.mission_name_presets()[self.mission_builder_name_index % len(self.mission_name_presets())]
        name = self.clean_builder_name(self.mission_builder_custom_name, preset_name) if self.mission_builder_custom_name else preset_name
        map_name = self.maps[self.mission_builder_map_index % len(self.maps)][0]
        theme_name, enemies, theme_desc = self.mission_enemy_themes()[self.mission_builder_theme_index % len(self.mission_enemy_themes())]
        objective = self.objective_modes()[self.mission_builder_objective_index % len(self.objective_modes())]
        parameter = int(self.mission_builder_parameter)
        draft: Dict[str, object] = {
            "name": name,
            "map": map_name,
            "enemies": list(enemies),
            "objective": objective,
            "theme": theme_name,
            "flavor": f"Builder preset: {theme_name} on {map_name}.",
            "builder": True,
        }
        draft.update(self.objective_params_for_mode(objective, parameter))
        draft["theme_detail"] = theme_desc
        return draft

    def cycle_mission_builder_field(self, direction: int) -> None:
        field = self.mission_builder_fields()[self.mission_builder_field_index % len(self.mission_builder_fields())]
        if field == "Name":
            self.mission_builder_custom_name = ""
            self.mission_builder_name_index = (self.mission_builder_name_index + direction) % len(self.mission_name_presets())
        elif field == "Map":
            self.mission_builder_map_index = (self.mission_builder_map_index + direction) % len(self.maps)
        elif field == "Enemy Theme":
            self.mission_builder_theme_index = (self.mission_builder_theme_index + direction) % len(self.mission_enemy_themes())
        elif field == "Objective":
            self.mission_builder_objective_index = (self.mission_builder_objective_index + direction) % len(self.objective_modes())
        elif field == "Parameter":
            self.mission_builder_parameter = max(1, min(12, self.mission_builder_parameter + direction))

    def save_mission_builder_preset(self) -> Dict[str, object]:
        draft = dict(self.mission_builder_draft())
        existing = {str(p.get("name", "")) for p in self.mission_presets()}
        base_name = str(draft["name"])
        name = base_name
        suffix = 2
        while name in existing:
            name = f"{base_name} {suffix}"
            suffix += 1
        draft["name"] = name
        draft["flavor"] = f"Custom mission preset made in the builder: {draft.get('theme')} on {draft.get('map')}."
        self.user_mission_presets.append(draft)
        self.mission_menu_index = len(self.mission_presets()) - 1
        self.messages = [f"Saved mission preset: {name}."]
        return draft

    def mission_enemy_names(self, preset: Dict[str, object]) -> List[str]:
        return list(preset.get("enemies", []))

    def mission_threat_value(self, preset: Dict[str, object]) -> int:
        return self.encounter_threat_value(self.mission_enemy_names(preset))

    def mission_reward_estimate(self, preset: Dict[str, object]) -> Dict[str, int]:
        return self.encounter_reward_estimate(self.mission_enemy_names(preset))

    def set_custom_counts_from_enemy_names(self, names: Iterable[str]) -> None:
        self.custom_enemy_counts = {name: 0 for name in self.enemy_roster_names()}
        self.custom_elite_counts = {name: 0 for name in self.enemy_roster_names()}
        for raw_name in names:
            name = str(raw_name)
            base = self.enemy_base_name(name)
            if base not in self.custom_enemy_counts:
                continue
            if self.enemy_is_elite_name(name):
                if not self.enemy_is_boss_name(base):
                    self.custom_elite_counts[base] = min(self.max_count_for_enemy(base), self.custom_elite_counts.get(base, 0) + 1)
            else:
                self.custom_enemy_counts[base] = min(self.max_count_for_enemy(base), self.custom_enemy_counts.get(base, 0) + 1)

    def apply_objective_from_mission(self, preset: Dict[str, object]) -> None:
        self.objective_mode = str(preset.get("objective", "Defeat All"))
        if self.objective_mode not in self.objective_modes():
            self.objective_mode = "Defeat All"
        if "round_goal" in preset:
            self.objective_round_goal = int(preset["round_goal"])
        if "hold_goal" in preset:
            self.objective_hold_goal = int(preset["hold_goal"])
        if "object_goal" in preset:
            self.objective_object_goal = int(preset["object_goal"])

    def start_mission_preset(self, preset: Dict[str, object]) -> None:
        request = self.create_battle_request_from_mission(preset)
        map_name = str(preset.get("map", self.maps[self.main_menu_index][0]))
        self.main_menu_index = self.map_index_for_name(map_name)
        self.set_custom_counts_from_enemy_names(self.mission_enemy_names(preset))
        self.apply_objective_from_mission(preset)
        self.current_mission_name = str(preset.get("name", "Mission"))
        self.current_mission_flavor = str(preset.get("flavor", ""))
        self.current_mission_reward_theme = str(preset.get("theme", ""))
        self.start_custom_encounter_from_main_menu()
        if not self.in_main_menu:
            self.remember_battle_request(request)

    def clear_custom_encounter(self) -> None:
        self.custom_enemy_counts = {name: 0 for name in self.enemy_roster_names()}
        self.custom_elite_counts = {name: 0 for name in self.enemy_roster_names()}
        self.current_mission_name = ""
        self.current_mission_flavor = ""
        self.current_mission_reward_theme = ""
        self.messages = ["Custom encounter cleared. Add enemies before starting."]

    def increase_custom_enemy(self) -> None:
        roster = self.enemy_roster_names()
        if not roster:
            return
        name = roster[self.encounter_enemy_index % len(roster)]
        if self.custom_enemy_cap_reached():
            self.messages = [f"Custom encounter cap reached ({self.custom_enemy_total_cap} enemies)."]
            return
        current = self.custom_enemy_counts.get(name, 0)
        limit = self.max_count_for_enemy(name)
        if current >= limit:
            self.messages = [f"{name} is already at max count x{limit}."]
            return
        self.custom_enemy_counts[name] = current + 1
        self.messages = [f"{name} count increased to x{self.custom_enemy_counts[name]}."]

    def decrease_custom_enemy(self) -> None:
        roster = self.enemy_roster_names()
        if not roster:
            return
        name = roster[self.encounter_enemy_index % len(roster)]
        current = self.custom_enemy_counts.get(name, 0)
        if current <= 0:
            self.messages = [f"{name} is already at x0."]
            return
        self.custom_enemy_counts[name] = current - 1
        self.messages = [f"{name} count decreased to x{self.custom_enemy_counts[name]}."]

    def increase_elite_custom_enemy(self) -> None:
        roster = self.enemy_roster_names()
        if not roster:
            return
        name = roster[self.encounter_enemy_index % len(roster)]
        if self.custom_enemy_cap_reached():
            self.messages = [f"Custom encounter cap reached ({self.custom_enemy_total_cap} enemies)."]
            return
        if self.enemy_is_boss_name(name):
            self.messages = [f"{name} is already a boss and cannot be made elite."]
            return
        current = self.custom_elite_counts.get(name, 0)
        if current >= self.enemy_max_count:
            self.messages = [f"Elite {name} is already at max count x{self.enemy_max_count}."]
            return
        self.custom_elite_counts[name] = current + 1
        self.messages = [f"Elite {name} count increased to x{self.custom_elite_counts[name]}."]

    def decrease_elite_custom_enemy(self) -> None:
        roster = self.enemy_roster_names()
        if not roster:
            return
        name = roster[self.encounter_enemy_index % len(roster)]
        current = self.custom_elite_counts.get(name, 0)
        if current <= 0:
            self.messages = [f"Elite {name} is already at x0."]
            return
        self.custom_elite_counts[name] = current - 1
        self.messages = [f"Elite {name} count decreased to x{self.custom_elite_counts[name]}."]

    def toggle_custom_enemy(self) -> None:
        # Compatibility helper: Enter/Space now increases quantity.
        self.increase_custom_enemy()

    def start_custom_encounter_from_main_menu(self) -> None:
        if self.main_menu_mode != "missions":
            self.current_mission_name = ""
            self.current_mission_flavor = ""
            self.current_mission_reward_theme = ""
        self.active_party_names.add("Rook")
        selected = self.selected_custom_enemy_names()
        if not selected:
            self.messages = ["Select at least one enemy before starting a custom encounter."]
            return
        if len(selected) > self.custom_enemy_total_cap:
            self.messages = [f"Custom encounter has {len(selected)} enemies; cap is {self.custom_enemy_total_cap}."]
            return

        self.map_index = self.main_menu_index % len(self.maps)
        self.map_name, self.map, self.start_positions = self.maps[self.map_index]
        self.map_menu_index = self.map_index
        self.custom_encounter_enabled = True
        self.active_enemy_names = set(selected)
        self.tutorial_active = False
        self.tutorial_mode = "basic"
        self.tutorial_flags = set()
        self.reset_battle_positions()
        self.custom_encounter_enabled = True
        self.active_enemy_names = set(selected)
        self.in_main_menu = False
        self.state = "command"
        self.turn = "hero"
        party = ", ".join(self.active_party_names_list())
        enemies = self.selected_custom_enemy_summary()
        mission_note = f"Mission {self.current_mission_name}: " if self.current_mission_name else "Custom encounter: "
        start_msg = f"{mission_note}{self.map_name}. Objective: {self.objective_mode}. Party: {party}. Enemies: {enemies}."
        self.messages = [clip(start_msg, 78)]
        self.combat_log = []
        self.combat_log_scroll = 0
        self.add_combat_log_entry(start_msg, category="BATTLE")
        request = self.create_battle_request_from_encounter_builder()
        self.remember_battle_request(request)

    def active_party_names_list(self) -> List[str]:
        return [h.name for h in self.heroes if h.name in self.active_party_names]

    def enforce_party_limit(self) -> None:
        leader = self.required_leader_name()
        self.active_party_names.add(leader)
        ordered = [h.name for h in self.heroes if h.name in self.active_party_names]
        if leader not in ordered:
            ordered.insert(0, leader)
        if len(ordered) > self.party_limit:
            keep = set(ordered[: self.party_limit])
            self.active_party_names = keep
            self.manual_companion_names &= keep
        else:
            self.active_party_names = set(ordered)

    def party_slots_remaining(self) -> int:
        self.enforce_party_limit()
        return max(0, self.party_limit - len(self.active_party_names))

    def party_role_label(self, hero_name: str) -> str:
        roles = {
            "Mira": "ranged scout",
            "Brom": "melee guard",
            "Aria": "support caster",
            "Nia": "swift striker",
            "Dax": "heavy bruiser",
            "Luma": "healer mystic",
        }
        if hero_name in getattr(self, "custom_companion_names", set()):
            hero = next((h for h in self.heroes if h.name == hero_name), None)
            if hero:
                return f"custom {self.hero_class(hero).lower()}"
            return "custom companion"
        return roles.get(hero_name, "companion")

    def party_start_slots(self) -> List[Pos]:
        rook = self.start_positions.get("Rook", (2, 2))
        rx, ry = rook
        offsets = [
            (0, 0), (1, 0), (0, 1), (1, 1),
            (2, 0), (0, 2), (2, 1), (1, 2),
            (-1, 0), (0, -1), (-1, 1), (1, -1),
            (2, 2), (-1, 2), (2, -1),
        ]
        slots: List[Pos] = []
        for dx, dy in offsets:
            pos = (rx + dx, ry + dy)
            if self.in_bounds(pos) and self.tile_at(pos) in PASSABLE and pos not in slots:
                slots.append(pos)
        # Fallback scan from upper-left if a particular arena has a cramped start.
        for y in range(self.map_height_tiles()):
            for x in range(self.map_width_tiles()):
                pos = (x, y)
                if self.tile_at(pos) in PASSABLE and pos not in slots:
                    slots.append(pos)
        return slots

    def place_active_party_members(self) -> None:
        used: Set[Pos] = set()
        slots = self.party_start_slots()
        for hero in self.heroes:
            if not hero.active:
                continue
            preferred = self.start_positions.get(hero.name)
            if preferred and self.in_bounds(preferred) and self.tile_at(preferred) in PASSABLE and preferred not in used:
                hero.pos = preferred
            else:
                for slot in slots:
                    if slot not in used:
                        hero.pos = slot
                        break
            used.add(hero.pos)

    def companion_name_presets(self) -> List[str]:
        return data_companion_name_presets()

    def companion_glyphs(self) -> List[str]:
        return data_companion_glyphs()

    def companion_archetypes(self) -> List[Tuple[str, Dict[str, int], Dict[str, int]]]:
        return data_companion_archetypes()

    def companion_weapon_choices(self) -> List[str]:
        names = list(self.equipment_defs().get("weapon", {}).keys())
        preferred = [
            "Iron Saber", "Scout Bow", "Guard Axe", "Light Wand", "Twin Daggers", "Stone Hammer", "Sun Rod",
            "Command Blade", "Venom Bow", "War Maul", "Spark Wand", "Shadow Daggers", "Tremor Hammer", "Star Rod",
        ]
        ordered = [name for name in preferred if name in names]
        ordered.extend(name for name in names if name not in ordered)
        return ordered

    def companion_editor_fields(self) -> List[str]:
        return ["Name", "Color", "Archetype", "Class", "Element", "Weapon", "Add to Party", "Manual Control"]

    def companion_draft_name(self) -> str:
        preset = self.companion_name_presets()[self.companion_editor_name_index % len(self.companion_name_presets())]
        base = self.clean_builder_name(self.companion_editor_custom_name, preset) if self.companion_editor_custom_name else preset
        if base not in {h.name for h in self.heroes}:
            return base
        suffix = 2
        while f"{base}{suffix}" in {h.name for h in self.heroes}:
            suffix += 1
        return f"{base}{suffix}"

    def companion_draft_summary(self) -> Dict[str, object]:
        archetype_name, stats, inventory = self.companion_archetypes()[self.companion_editor_archetype_index % len(self.companion_archetypes())]
        class_name = self.class_names()[self.companion_editor_class_index % len(self.class_names())]
        subclass = self.elemental_subclasses()[self.companion_editor_subclass_index % len(self.elemental_subclasses())]
        weapon = self.companion_weapon_choices()[self.companion_editor_weapon_index % len(self.companion_weapon_choices())]
        color = self.companion_color_names()[self.companion_editor_color_index % len(self.companion_color_names())]
        return {
            "name": self.companion_draft_name(),
            "glyph": "@",
            "color": color,
            "archetype": archetype_name,
            "stats": dict(stats),
            "inventory": dict(inventory),
            "class": class_name,
            "subclass": subclass,
            "weapon": weapon,
            "add_to_party": self.companion_editor_add_to_party,
            "manual": self.companion_editor_manual_control,
        }

    def cycle_companion_editor_field(self, direction: int) -> None:
        field = self.companion_editor_fields()[self.companion_editor_field_index % len(self.companion_editor_fields())]
        if field == "Name":
            self.companion_editor_custom_name = ""
            self.companion_editor_name_index = (self.companion_editor_name_index + direction) % len(self.companion_name_presets())
        elif field == "Color":
            self.companion_editor_color_index = (self.companion_editor_color_index + direction) % len(self.companion_color_names())
        elif field == "Archetype":
            self.companion_editor_archetype_index = (self.companion_editor_archetype_index + direction) % len(self.companion_archetypes())
        elif field == "Class":
            self.companion_editor_class_index = (self.companion_editor_class_index + direction) % len(self.class_names())
        elif field == "Element":
            self.companion_editor_subclass_index = (self.companion_editor_subclass_index + direction) % len(self.elemental_subclasses())
        elif field == "Weapon":
            self.companion_editor_weapon_index = (self.companion_editor_weapon_index + direction) % len(self.companion_weapon_choices())
        elif field == "Add to Party":
            self.companion_editor_add_to_party = not self.companion_editor_add_to_party
        elif field == "Manual Control":
            self.companion_editor_manual_control = not self.companion_editor_manual_control

    def create_custom_companion(self) -> Unit:
        draft = self.companion_draft_summary()
        name = str(draft["name"])
        if name in {h.name for h in self.heroes}:
            # Should only happen if a preset was created between render and confirm.
            base = name
            suffix = 2
            while f"{base}{suffix}" in {h.name for h in self.heroes}:
                suffix += 1
            name = f"{base}{suffix}"
        stats = dict(draft["stats"])
        inventory = dict(draft["inventory"])
        weapon_name = str(draft["weapon"])
        hero = Unit(
            name,
            "@",
            self.start_positions.get("Mira", (2, 2)),
            int(stats["max_hp"]),
            int(stats["max_hp"]),
            int(stats["max_mp"]),
            int(stats["max_mp"]),
            int(stats["move_range"]),
            Weapon(weapon_name, int(stats["weapon_damage"])),
            "hero",
            ai_controlled=not bool(draft["manual"]),
            inventory=inventory,
        )
        self.heroes.append(hero)
        self.custom_companion_names.add(name)
        progress = self.ensure_progress_entry(hero)
        progress["custom_base_stats"] = stats
        progress["custom_inventory"] = inventory
        progress["custom_base_weapon"] = weapon_name
        progress["color"] = str(draft["color"])
        progress["class"] = str(draft["class"])
        progress["subclass"] = str(draft["subclass"])
        progress["equipped_gear"] = {"weapon": weapon_name, "armor": "Traveler Clothes", "charm": "Plain Charm"}
        progress["unlocked_gear"] = {
            "weapon": {weapon_name},
            "armor": {"Traveler Clothes"},
            "charm": {"Plain Charm"},
        }
        self.apply_equipment_to_hero(hero)

        if bool(draft["manual"]):
            self.manual_companion_names.add(name)
        if bool(draft["add_to_party"]):
            self.enforce_party_limit()
            if len(self.active_party_names) < self.party_limit:
                self.active_party_names.add(name)
            else:
                self.messages = [f"{name} created in reserve. Color {draft['color']}. Party is full ({self.party_limit}/{self.party_limit})."]
        self.enforce_party_limit()
        if not self.messages or name not in self.messages[-1]:
            party_note = "active party" if name in self.active_party_names else "reserve"
            control_note = "Manual" if name in self.manual_companion_names else "AI"
            self.messages = [f"Created {name}: {draft['archetype']} {draft['class']} / {draft['subclass']} with {weapon_name}. Color {draft['color']}. {party_note}, {control_note}."]
        self.party_menu_index = len(self.heroes) - 1
        self.class_menu_hero_index = len(self.heroes) - 1
        self.loadout_hero_index = len(self.heroes) - 1
        self.companion_editor_custom_name = ""
        self.companion_editor_name_index += 1
        return hero

    def delete_last_custom_companion(self) -> None:
        custom = [h for h in self.heroes if h.name in self.custom_companion_names]
        if not custom:
            self.messages = ["No custom companions to delete."]
            return
        hero = custom[-1]
        self.heroes = [h for h in self.heroes if h.name != hero.name]
        self.custom_companion_names.discard(hero.name)
        self.active_party_names.discard(hero.name)
        self.manual_companion_names.discard(hero.name)
        self.party_progress.pop(hero.name, None)
        self.party_menu_index %= max(1, len(self.heroes))
        self.class_menu_hero_index %= max(1, len(self.heroes))
        self.loadout_hero_index %= max(1, len(self.heroes))
        self.enforce_party_limit()
        self.messages = [f"Deleted custom companion {hero.name}."]

    def party_management_label(self, hero: Unit) -> str:
        color = self.hero_color_name(hero) if hero.team == "hero" else ""
        if self.is_required_leader(hero):
            return f"[x] {hero.name:<5} @ {color:<7} required leader"
        mark = "[x]" if hero.name in self.active_party_names else "[ ]"
        role = self.party_role_label(hero.name)
        return f"{mark} {hero.name:<5} @ {color:<7} {role}"

    def toggle_party_member(self) -> None:
        hero = self.heroes[self.party_menu_index % len(self.heroes)]
        if self.is_required_leader(hero):
            self.messages = [f"{hero.name} is required and cannot be removed from the party."]
            return
        if hero.name in self.active_party_names:
            self.active_party_names.remove(hero.name)
            self.manual_companion_names.discard(hero.name)
            self.enforce_party_limit()
            self.messages = [f"{hero.name} moved to reserve."]
        else:
            self.enforce_party_limit()
            if len(self.active_party_names) >= self.party_limit:
                self.messages = [f"Party is full ({self.party_limit}/{self.party_limit}). Move someone to reserve first."]
                return
            self.active_party_names.add(hero.name)
            self.enforce_party_limit()
            self.messages = [f"{hero.name} added to active party."]

    def start_battle_from_main_menu(self) -> None:
        self.pending_mission_preset = None
        self.current_mission_name = ""
        self.current_mission_flavor = ""
        self.current_mission_reward_theme = ""
        self.active_party_names.add("Rook")
        self.map_index = self.main_menu_index % len(self.maps)
        self.map_name, self.map, self.start_positions = self.maps[self.map_index]
        self.map_menu_index = self.map_index
        self.active_enemy_names = set(self.enemy_loadout_for_map(self.map_name))
        self.tutorial_active = False
        self.tutorial_mode = "basic"
        self.tutorial_flags = set()
        self.reset_battle_positions()
        self.in_main_menu = False
        self.state = "command"
        self.turn = "hero"
        party = ", ".join(self.active_party_names_list())
        enemies = ", ".join(self.enemy_loadout_for_map(self.map_name))
        start_msg = f"Selected {self.map_name}. Traits: {self.map_trait_summary(self.map_name)}. Objective: {self.objective_mode}. Party: {party}. Enemies: {enemies}."
        self.messages = [clip(start_msg, 78)]
        self.combat_log = []
        self.combat_log_scroll = 0
        self.add_combat_log_entry(start_msg, category="BATTLE")
        request = self.create_battle_request_from_selected_setup()
        self.remember_battle_request(request)

    def home_menu_options(self) -> List[Tuple[str, str, str]]:
        return [
            ("start", "Start Battle", "Launch the currently selected setup."),
            ("maps", "Select Map", "Choose a map without starting immediately."),
            ("missions", "Mission Presets", "Choose or build a mission contract."),
            ("party", "Party", "Choose active companions and colors."),
            ("loadout", "Loadout", "Spend loot and equip gear."),
            ("classes", "Classes / Skills", "Change class, element, and skill tree choices."),
            ("companions", "Companion Editor", "Create custom allies for testing."),
            ("encounter", "Encounter Maker", "Build a custom test enemy group."),
            ("objectives", "Optional Objectives", "Set alternate objectives; Defeat All remains default."),
            ("bestiary", "Bestiary", "Inspect enemies and counterplay."),
            ("tutorial", "Tutorials", "Practice basics or advanced tactics."),
            ("help", "Help", "Show controls and feature notes."),
            ("quit", "Quit", "Exit the prototype."),
        ]

    def selected_map_name(self) -> str:
        return self.maps[self.main_menu_index % len(self.maps)][0]

    def pending_mission_label(self) -> str:
        if self.pending_mission_preset:
            return str(self.pending_mission_preset.get("name", "Mission"))
        return "None"

    def setup_launch_label(self) -> str:
        if self.pending_mission_preset:
            return "Mission: " + self.pending_mission_label()
        return "Map: " + self.selected_map_name()

    def setup_summary_lines(self) -> List[str]:
        map_name = self.selected_map_name()
        party_count = len(self.active_party_names_list())
        return [
            f"Ready: {self.setup_launch_label()}",
            f"Map: {map_name}",
            f"Party: {party_count}/{self.party_limit} | Objective: {self.objective_mode}",
        ]


    def select_map_without_starting(self) -> None:
        self.pending_mission_preset = None
        self.map_detail_open = False
        name = self.selected_map_name()
        self.messages = [f"Selected map: {name}. Use Home > Start Battle when ready."]
        self.main_menu_mode = "home"

    def select_mission_without_starting(self, preset: Dict[str, object]) -> None:
        self.pending_mission_preset = dict(preset)
        map_name = str(self.pending_mission_preset.get("map", self.selected_map_name()))
        self.main_menu_index = self.map_index_for_name(map_name)
        self.apply_objective_from_mission(self.pending_mission_preset)
        self.messages = [f"Selected mission: {self.pending_mission_preset.get('name', 'Mission')}. Use Home > Start Battle when ready."]
        self.main_menu_mode = "home"
        self.mission_page_index = 0

    def start_selected_setup_from_home(self) -> None:
        if self.pending_mission_preset:
            preset = dict(self.pending_mission_preset)
            self.pending_mission_preset = None
            self.main_menu_mode = "missions"
            self.start_mission_preset(preset)
            return
        self.start_battle_from_main_menu()

    def activate_home_option(self, reader: Optional[KeyReader] = None) -> None:
        options = self.home_menu_options()
        key = options[self.home_menu_index % len(options)][0]
        if key == "start":
            self.start_selected_setup_from_home()
        elif key == "help":
            if reader is not None:
                self.help(reader)
        elif key == "quit":
            self.should_quit = True
        else:
            self.main_menu_mode = key
            if key == "maps":
                self.map_detail_open = False
            if key == "encounter":
                self.clear_custom_encounter()

    def render_home_menu(self, width: int) -> None:
        print(c("ASCII Tactical Combat Prototype v113", Style.BOLD, Style.BRIGHT_WHITE))
        print(c("HOME", Style.BOLD, Style.BRIGHT_YELLOW))
        print("-" * width)
        for line in self.setup_summary_lines():
            for wrapped in wrap_plain(line, width):
                print(wrapped)
        print("-" * width)

        options = self.home_menu_options()
        selected_i = self.home_menu_index % len(options)
        selected_option = options[selected_i]
        for i, (_key, label, _desc) in enumerate(options):
            prefix = "> " if i == selected_i else "  "
            line = prefix + label
            if i == selected_i:
                print(c(clip(line, 36), Style.BLACK, Style.BG_SELECT, Style.BOLD))
            else:
                print(clip(line, 36))
        print()
        for line in wrap_labeled("Info: ", selected_option[2], width):
            print(c(line[:6], Style.BOLD) + line[6:] if line.startswith("Info: ") else line)
        msg = self.main_menu_message()
        if msg and "Command menu active" not in msg:
            for line in wrap_labeled("Note: ", msg, width):
                print(c(line[:6], Style.BOLD) + line[6:] if line.startswith("Note: ") else line)
        print("Up/Down choose | Z/Enter select | H help | Q quit")


    def render_map_selector(self, width: int) -> None:
        if self.map_detail_open:
            name, _map, _pos = self.maps[self.main_menu_index % len(self.maps)]
            threat = self.map_default_threat_value(name)
            print(c("Map Details", Style.BOLD, Style.BRIGHT_GREEN))
            print(c(name, Style.BOLD, Style.BRIGHT_WHITE))
            for line in wrap_plain(self.map_flavor_text(name), width - 4, subsequent_indent="  "):
                print("  " + line)
            print()
            print(f"Difficulty: {self.threat_difficulty_name(threat)}")
            print(f"Traits: {self.map_trait_summary(name)}")
            print(f"Terrain: {self.terrain_profile_line(name)}")
            for line in wrap_labeled("Default enemies: ", ", ".join(self.enemy_loadout_for_map(name)), width):
                print(line)
            print()
            print("Z/Enter select this map | X/Esc back to list | Home back Home | Q quit")
            return

        print(c("Select Map", Style.BOLD, Style.BRIGHT_GREEN))
        print("Choose a map. Z/Enter opens details; Z/Enter again selects it.")
        print()

        grouped: Dict[str, List[Tuple[int, str]]] = {"Low": [], "Moderate": [], "High": [], "Extreme": []}
        for i, (name, _map, _pos) in enumerate(self.maps):
            difficulty = self.threat_difficulty_name(self.map_default_threat_value(name))
            grouped.setdefault(difficulty, []).append((i, name))

        for difficulty in ("Low", "Moderate", "High", "Extreme"):
            entries = grouped.get(difficulty, [])
            if not entries:
                continue
            print(c(difficulty, Style.BOLD, Style.BRIGHT_CYAN))
            for i, name in entries:
                selected = i == self.main_menu_index % len(self.maps)
                prefix = "> " if selected else "  "
                if selected:
                    print(c(prefix + clip(name, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
                else:
                    print(prefix + clip(name, width - 2))
            print()

        print("Up/Down choose | Z/Enter details | X/Esc back | Q quit")


    def encounter_builder_rows(self) -> List[Tuple[str, str]]:
        rows: List[Tuple[str, str]] = [
            ("action:start", "Start Encounter"),
            ("action:map", "Map"),
            ("action:defaults", "Use Map Defaults"),
            ("action:clear", "Clear All"),
        ]
        for name in self.enemy_roster_names():
            rows.append(("enemy:" + name, name))
        return rows

    def current_encounter_row(self) -> Tuple[str, str]:
        rows = self.encounter_builder_rows()
        if not rows:
            return ("action:start", "Start Encounter")
        self.encounter_enemy_index %= len(rows)
        return rows[self.encounter_enemy_index]

    def encounter_selected_enemy_name(self) -> str:
        row_key, row_label = self.current_encounter_row()
        return row_label if row_key.startswith("enemy:") else ""

    def increase_custom_enemy_by_name(self, name: str) -> None:
        if self.custom_enemy_cap_reached():
            self.messages = [f"Custom encounter cap reached ({self.custom_enemy_total_cap} enemies)."]
            return
        current = self.custom_enemy_counts.get(name, 0)
        limit = self.max_count_for_enemy(name)
        if current >= limit:
            self.messages = [f"{name} is already at max count x{limit}."]
            return
        self.custom_enemy_counts[name] = current + 1
        self.messages = [f"{name} x{self.custom_enemy_counts[name]}."]

    def decrease_custom_enemy_by_name(self, name: str) -> None:
        current = self.custom_enemy_counts.get(name, 0)
        if current <= 0:
            self.messages = [f"{name} is already at x0."]
            return
        self.custom_enemy_counts[name] = current - 1
        self.messages = [f"{name} x{self.custom_enemy_counts[name]}."]

    def encounter_adjust_selected(self, delta: int) -> None:
        row_key, row_label = self.current_encounter_row()
        if row_key == "action:map":
            self.main_menu_index = (self.main_menu_index + delta) % len(self.maps)
            self.reset_custom_encounter_to_map()
            return
        if row_key.startswith("enemy:"):
            if delta > 0:
                self.increase_custom_enemy_by_name(row_label)
            elif delta < 0:
                self.decrease_custom_enemy_by_name(row_label)

    def encounter_activate_selected(self) -> None:
        row_key, row_label = self.current_encounter_row()
        if row_key == "action:start":
            self.start_custom_encounter_from_main_menu()
        elif row_key == "action:map":
            self.main_menu_mode = "maps"
            self.map_detail_open = False
        elif row_key == "action:defaults":
            self.reset_custom_encounter_to_map()
        elif row_key == "action:clear":
            self.clear_custom_encounter()
        elif row_key.startswith("enemy:"):
            self.increase_custom_enemy_by_name(row_label)

    def selected_enemy_brief_line(self, enemy_name: str) -> str:
        enemy = self.enemy_by_name(enemy_name)
        if not enemy:
            return ""
        count = self.custom_enemy_counts.get(enemy_name, 0)
        total = self.enemy_threat_value(enemy_name) * count
        return f"{enemy_name}: {enemy.role}, HP {enemy.max_hp}, DMG {enemy.weapon.damage}, Move {enemy.move_range}, threat each {self.enemy_threat_value(enemy_name)}, selected threat {total}"

    def compact_mission_summary(self, preset: Dict[str, object]) -> List[str]:
        return [
            f"Map: {preset.get('map')} | Objective: {preset.get('objective')}",
            f"Enemies: {', '.join(self.mission_enemy_names(preset))}",
            f"Threat: {self.threat_difficulty_name(self.mission_threat_value(preset))} ({self.mission_threat_value(preset)})",
            f"Brief: {preset.get('flavor', '')}",
        ]

    def render_main_menu(self) -> None:
        dev_menu_helpers.render_main_menu(self)

    def handle_main_menu_key(self, key: str, reader: KeyReader) -> None:
        dev_menu_helpers.handle_main_menu_key(self, key, reader)

    def run(self) -> None:
        enter_alt_screen()
        clear_screen(clear_scrollback=True)
        hide_cursor()
        try:
            with KeyReader() as reader:
                while not self.should_quit:
                    if self.in_main_menu:
                        self.render_main_menu()
                        key = reader.read_key()
                        self.handle_main_menu_key(key, reader)
                        continue

                    over = self.game_over()
                    if over:
                        self.render_results_screen(over)
                        key = reader.read_key()
                        action = self.handle_results_key(key)
                        if action == "quit":
                            self.should_quit = True
                        elif action == "close":
                            if getattr(getattr(self, "current_battle_request", None), "source", "") == "ascii_farmstead":
                                self.should_quit = True
                                continue
                            self.in_main_menu = True
                            self.main_menu_mode = "home"
                            self.main_menu_index = self.map_index
                        continue

                    self.render()

                    key = reader.read_key()
                    self.handle_key(key, reader)
        finally:
            show_cursor()
            clear_screen(clear_scrollback=True)
            exit_alt_screen()
            print("Exited combat prototype.")


if __name__ == "__main__":
    try:
        Game().run()
    except KeyboardInterrupt:
        show_cursor()
        clear_screen()
        print("Exited combat prototype.")
