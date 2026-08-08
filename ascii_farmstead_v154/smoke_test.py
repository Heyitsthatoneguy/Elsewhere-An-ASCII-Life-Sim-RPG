#!/usr/bin/env python3
"""Lightweight smoke checks for Elsewhere refactors.

This script intentionally avoids external dependencies and should not import
from future feature systems in a way that would create circular imports. It
checks that static data, pure helpers, save-sensitive state, the main game
object, and a temporary save/load round trip still work.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from collections import deque
import contextlib
import io
import json
import os
import random
import re

import ascii_farmstead_data as data
import ascii_farmstead_actors as actors
import ascii_farmstead_building as building
import ascii_farmstead_civic_state as civic_state
import ascii_farmstead_custom_content as custom_content
import ascii_farmstead_custom_extended as custom_extended
import ascii_farmstead_custom_menus as custom_menus
import ascii_farmstead_containers as container_system
import ascii_farmstead_dynasty as dynasty
import ascii_farmstead_excavation as excavation
import ascii_farmstead_furniture as furniture_art
import ascii_farmstead_furniture_catalog as furniture_catalog
import ascii_farmstead_furniture_actions as furniture_actions
import ascii_farmstead_board_visuals as board_visuals
import ascii_farmstead_checkers as checkers
import ascii_farmstead_chess as chess
import ascii_farmstead_mancala as mancala
import ascii_farmstead_holdem as holdem
import ascii_farmstead_hearts as hearts
import ascii_farmstead_solitaire as solitaire
import ascii_farmstead_cards as playing_cards
import ascii_farmstead_ur as royal_ur
import ascii_farmstead_game_tables as game_tables
import ascii_farmstead_helpers as helpers
import ascii_farmstead_inventory as inventory
import ascii_farmstead_random_loot as random_loot
import ascii_farmstead_minigame_ui as minigame_ui
import ascii_farmstead_npcs as npcs
import ascii_farmstead_dialogue as dialogue_system
import ascii_farmstead_saves as saves
import ascii_farmstead_state as state
import ascii_farmstead_town_builder as town_builder
import ascii_farmstead_npc_builder as npc_builder
import ascii_farmstead_npc_dialogue as npc_dialogue
import ascii_farmstead_dialogue_library as dialogue_library
import ascii_farmstead_procedural_interiors as procedural_interiors
import ascii_farmstead_procedural_furnishing as procedural_furnishing
import ascii_farmstead_procedural_towns as procedural_towns
import ascii_farmstead_wilderness as wilderness_system
import ascii_farmstead_support as support
import ascii_farmstead_tavern_games as tavern_games
import ascii_farmstead_ui as ui
import ascii_farmstead_visuals as visuals
import ascii_farmstead_victory as victory
import ascii_farmstead_v154_item_alias_fixes as farmstead_main
import elsewhere
from ascii_battle_prototype.combat.game import Game as BattleGame
from ascii_battle_prototype.combat.main import configure_game_from_request
from ascii_battle_prototype.combat.results import BattleRequest
from ascii_battle_prototype.combat.validation import validate_all_content
from ascii_farmstead_combat import (
    COMBAT_EQUIPMENT_SLOTS,
    DEFAULT_COMBAT_ACCESSORY,
    DEFAULT_COMBAT_ARMOR,
    DEFAULT_COMBAT_WEAPON,
    FARMSTEAD_COMPANION_DATA,
    build_player_combat_profile,
    grant_combat_exp,
    mine_battle_request_for_enemy,
    mine_enemy_role,
    translated_battle_loot,
)
from ascii_farmstead_support import VALID_GAME_LOCATIONS
from ascii_farmstead_v154_item_alias_fixes import FarmGame, GameState, MenuItem, prepare_loaded_state_data

ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def visible_terminal_len(text: object) -> int:
    return len(ANSI_CSI_RE.sub("", str(text)))


def main() -> int:
    assert support.GAME_TITLE == "Elsewhere: an ASCII Life-Sim RPG"
    assert support.GAME_SHORT_TITLE == "Elsewhere"
    assert support.GAME_VERSION == "0.9.0-beta.6"
    assert support.movement_delta_for_key("NUM7") == (-1, -1)
    assert support.movement_delta_for_key("NUM8") == (0, -1)
    assert support.movement_delta_for_key("NUM3") == (1, 1)
    assert support.normalize_key("NUM8") == "UP"
    assert support.normalize_key("2") == "2"
    assert elsewhere.main is farmstead_main.main
    packaged_names = support.packaged_legacy_data_names()
    assert "custom_content.json" in packaged_names
    assert "custom_content.backup1.json" in packaged_names
    assert "custom_content_export.json" in packaged_names
    assert data.WIDTH == 54
    assert data.HEIGHT == 22
    assert data.CROP_DATA
    assert data.TOWN_NPC_DEFINITIONS
    assert data.FISH_DATA
    assert data.RESIDENT_REQUEST_DATA
    assert data.COMPANION_QUEST_DATA
    assert ui.clean_text_entry("A deliberately long custom description", "", 180) == "A deliberately long custom description"
    assert len(ui.clean_text_entry("x" * 80, "", 24)) == 24

    original_custom_content_path = custom_content.CUSTOM_CONTENT_PATH
    with TemporaryDirectory() as custom_directory:
        custom_content.CUSTOM_CONTENT_PATH = Path(custom_directory) / "custom_content.json"
        building_template_rows = custom_extended.default_custom_building_template_rows("home")
        building_template_grid = [list(row) for row in building_template_rows]
        building_template_grid[5][9] = "d"
        building_template_grid[5][10] = "P"
        building_template_grid[6][9] = "l"
        building_template_grid[7][9] = "|"
        building_template_grid[7][10] = "_"
        building_template_rows = ["".join(row) for row in building_template_grid]
        inn_template_rows = custom_extended.default_custom_building_template_rows("inn")
        inn_template_grid = [list(row) for row in inn_template_rows]
        inn_template_grid[6][14] = "b"
        inn_template_grid[6][48] = "b"
        inn_template_grid[17][14] = "f"
        inn_template_grid[21][34] = "&"
        inn_template_grid[22][34] = "t"
        inn_template_rows = ["".join(row) for row in inn_template_grid]
        inn_upper_rows = custom_extended.default_custom_building_template_rows("inn", 1)
        inn_upper_grid = [list(row) for row in inn_upper_rows]
        inn_upper_grid[7][31] = ">"
        inn_upper_grid[8][14] = "b"
        inn_upper_grid[8][48] = "s"
        inn_upper_rows = ["".join(row) for row in inn_upper_grid]
        authored_store_override_rows = custom_extended.default_custom_building_template_rows(
            "general_store"
        )
        authored_store_override_grid = [list(row) for row in authored_store_override_rows]
        for override_y, override_row in enumerate(authored_store_override_grid):
            for override_x, override_tile in enumerate(override_row):
                if override_tile == "&":
                    authored_store_override_grid[override_y][override_x] = "."
        authored_store_override_grid[6][10] = "r"
        authored_store_override_rows = [
            "".join(row) for row in authored_store_override_grid
        ]
        procedural_store_override_grid = [
            list(row) for row in authored_store_override_rows
        ]
        procedural_store_override_grid[6][10] = "s"
        procedural_store_override_rows = [
            "".join(row) for row in procedural_store_override_grid
        ]
        custom_library = {
            "version": 1,
            "abilities": [
                {
                    "name": "Seed Shot",
                    "description": "A hand-drawn draining briar attack.",
                    "effect": "damage",
                    "mp_cost": 3,
                    "damage": 5,
                    "range_max": 5,
                    "shape": "custom",
                    "custom_pattern": [[0, 0], [1, 0], [1, -1], [1, 1]],
                    "pattern_anchor": "target",
                    "pattern_rotate": True,
                    "armor_pierce": 2,
                    "displacement": 1,
                    "life_steal": 3,
                    "combo_status": "poison",
                    "combo_damage_bonus": 4,
                    "combo_mp_gain": 2,
                },
                {
                    "name": "Harvest Grace",
                    "description": "Restore an ally.",
                    "effect": "heal",
                    "mp_cost": 4,
                    "heal_amount": 9,
                },
                {
                    "name": "Orchard Nova",
                    "description": "Root enemies in an orchard burst.",
                    "effect": "damage",
                    "mp_cost": 5,
                    "damage": 6,
                    "range_max": 5,
                    "shape": "burst",
                    "aoe_radius": 1,
                    "status": "root",
                    "status_duration": 1,
                },
                {
                    "name": "Briar Line",
                    "description": "Control a narrow lane.",
                    "effect": "damage",
                    "mp_cost": 5,
                    "damage": 5,
                    "range_max": 6,
                    "shape": "strip",
                    "status": "root",
                    "status_duration": 1,
                },
                {
                    "name": "Final Reaping",
                    "description": "A custom mastery strike.",
                    "effect": "damage",
                    "mp_cost": 8,
                    "damage": 10,
                    "range_max": 4,
                    "shape": "point",
                },
            ],
            "classes": [
                {
                    "name": "Hedge Warden",
                    "description": "Controls lanes with cultivated magic.",
                    "default_abilities": ["Seed Shot", "Harvest Grace", "Orchard Nova"],
                    "progression_abilities": [{"name": "Briar Line", "cost": 1}],
                    "mastery_ability": "Final Reaping",
                    "recommended_elements": ["Earth", "Poison"],
                }
            ],
            "enemies": [
                {
                    "name": "Hedge Beast",
                    "description": "A heavy custom creature.",
                    "glyph": "h",
                    "archetype": "Brute",
                    "max_hp": 38,
                    "move_range": 4,
                    "weapon_name": "Branch Maul",
                    "damage": 6,
                    "range_min": 1,
                    "range_max": 2,
                    "defense": 1,
                }
            ],
            "equipment": [
                {
                    "name": "Farmer Crown",
                    "slot": "charm",
                    "description": "A sturdy custom charm.",
                    "hp": 6,
                    "mp": 2,
                    "coin_cost": 20,
                    "material": "Stone",
                    "material_cost": 2,
                }
            ],
            "maps": [
                {
                    "name": "Hedge Trial",
                    "description": "A custom wilderness arena.",
                    "theme": "Wild",
                    "width": 24,
                    "height": 14,
                    "cover_density": 2,
                    "hazard_density": 1,
                    "seed": 42,
                    "enemy_names": ["Hedge Beast", "Wolf", "Slime"],
                    "objective": "Defeat All",
                }
            ],
            "dungeon_rooms": [
                {
                    "name": "Root Gallery",
                    "description": "A custom rooted room.",
                    "theme": "root",
                    "pattern": "Pillars",
                    "density": 3,
                    "seed": 7,
                    "enabled": True,
                }
            ],
            "building_templates": [
                {
                    "name": "Archive Cottage",
                    "description": "A custom procedural home with a marked archive desk.",
                    "building_type": "home",
                    "max_occupancy": 8,
                    "enabled": True,
                    "rows": building_template_rows,
                    "colors": [{"floor": 0, "x": 9, "y": 5, "color": "blue"}],
                    "spawns": [{"floor": 0, "x": 11, "y": 6}],
                    "zones": [
                        {"kind": "bedroom", "x1": 8, "y1": 5, "x2": 18, "y2": 9},
                        {"kind": "office", "x1": 8, "y1": 5, "x2": 12, "y2": 7},
                    ],
                },
                {
                    "name": "Two Room Inn",
                    "description": "A custom inn where each bedroom zone represents one rentable room.",
                    "building_type": "inn",
                    "max_occupancy": 6,
                    "enabled": True,
                    "floors": [
                        {"name": "Common Floor", "rows": inn_template_rows},
                        {"name": "Guest Loft", "rows": inn_upper_rows},
                    ],
                    "zones": [
                        {"kind": "bedroom", "x1": 9, "y1": 5, "x2": 19, "y2": 9},
                        {"kind": "bedroom", "x1": 43, "y1": 5, "x2": 53, "y2": 9},
                        {"kind": "bedroom", "floor": 1, "x1": 9, "y1": 5, "x2": 19, "y2": 10},
                        {"kind": "kitchen", "x1": 9, "y1": 16, "x2": 19, "y2": 20},
                        {"kind": "shopping_counter", "x1": 31, "y1": 20, "x2": 38, "y2": 22},
                        {"kind": "dining", "x1": 31, "y1": 22, "x2": 42, "y2": 24},
                    ],
                },
                {
                    "name": "Built-in General Store",
                    "description": "A direct authored-map override.",
                    "building_type": "general_store",
                    "max_occupancy": 0,
                    "enabled": True,
                    "manual_layout": True,
                    "builtin_preset_id": "authored:make_general_store_map",
                    "overrides_builtin": True,
                    "rows": authored_store_override_rows,
                },
                {
                    "name": "General Store Layout A",
                    "description": "A direct procedural-layout override.",
                    "building_type": "general_store",
                    "max_occupancy": 0,
                    "enabled": True,
                    "manual_layout": True,
                    "builtin_preset_id": "procedural:general_store:0",
                    "overrides_builtin": True,
                    "rows": procedural_store_override_rows,
                },
            ],
        }
        saved, save_message = custom_content.save_custom_content(custom_library)
        assert saved, save_message
        loaded_custom, custom_warnings = custom_content.load_custom_content()
        assert not custom_warnings
        assert loaded_custom["abilities"][0]["name"] == "Seed Shot"
        assert loaded_custom["abilities"][0]["custom_pattern"] == [[0, 0], [1, 0], [1, -1], [1, 1]]
        assert loaded_custom["abilities"][0]["armor_pierce"] == 2
        assert loaded_custom["abilities"][0]["displacement"] == 1
        assert loaded_custom["abilities"][0]["life_steal"] == 3
        assert custom_content.ability_balance_label(loaded_custom["abilities"][0])
        custom_battle_game = BattleGame()
        seed_shot = custom_battle_game.skill_by_name("Seed Shot")
        assert seed_shot is not None and seed_shot.shape == "custom"
        assert seed_shot.custom_pattern == ((0, 0), (1, 0), (1, -1), (1, 1))
        custom_battle_game.map = [list("...............") for _ in range(15)]
        right_pattern = custom_battle_game.skill_affected_tiles((5, 5), (7, 5), seed_shot)
        assert {(7, 5), (8, 5), (8, 4), (8, 6)} <= right_pattern
        down_pattern = custom_battle_game.skill_affected_tiles((5, 5), (5, 7), seed_shot)
        assert {(5, 7), (5, 8), (6, 8), (4, 8)} <= down_pattern
        custom_hero = custom_battle_game.selected_hero
        custom_target = custom_battle_game.enemies[0]
        for index, unit in enumerate(custom_battle_game.heroes + custom_battle_game.enemies):
            unit.pos = (index, 0)
        custom_hero.pos = (8, 10)
        custom_target.pos = (10, 10)
        custom_target.defense = 3
        assert custom_battle_game.skill_damage_against(custom_target, seed_shot) == seed_shot.damage + 2
        assert custom_battle_game.apply_skill_displacement(custom_hero, custom_target, seed_shot) == 1
        assert custom_target.pos == (11, 10)
        custom_hero.hp = custom_hero.max_hp - 5
        assert custom_battle_game.apply_skill_life_steal(custom_hero, seed_shot, 10) == 3
        assert custom_hero.hp == custom_hero.max_hp - 2
        assert custom_battle_game.skill_by_name("Orchard Nova") is not None
        assert "Hedge Warden" in custom_battle_game.class_names()
        assert "Hedge Beast" in custom_battle_game.enemy_roster_names()
        assert custom_battle_game.enemy_by_name("Hedge Beast").role == "brute"
        assert custom_battle_game.enemy_by_name("Hedge Beast").defense == 1
        assert custom_battle_game.enemy_family(custom_battle_game.enemy_by_name("Hedge Beast")) == "Boar"
        assert "Farmer Crown" in custom_battle_game.equipment_defs()["charm"]
        assert any(name == "Hedge Trial" for name, _grid, _positions in custom_battle_game.maps)
        assert custom_battle_game.enemy_loadout_for_map("Hedge Trial") == ["Hedge Beast", "Wolf", "Slime"]
        custom_validation = validate_all_content(custom_battle_game)
        assert custom_validation.ok, [
            (issue.code, issue.context, issue.message)
            for issue in custom_validation.issues
            if issue.severity == "error"
        ]
        assert custom_battle_game.class_element_recommendations("Hedge Warden") == ["Earth", "Poison"]
        custom_arena = next(grid for name, grid, _positions in custom_battle_game.maps if name == "Hedge Trial")
        assert len(custom_arena) == 14
        assert all(len(row) == 24 for row in custom_arena)
        room_record = custom_extended.custom_dungeon_room_records(enabled_only=True, theme="root")[0]
        room_grid = [["." for _ in range(13)] for _ in range(9)]
        assert custom_extended.stamp_custom_dungeon_room(room_grid, (1, 1, 11, 7), room_record)
        assert all(room_grid[4][x] == "." for x in range(1, 12))
        assert all(room_grid[y][6] == "." for y in range(1, 8))
        building_record = custom_extended.custom_building_template_records("home", enabled_only=True)[0]
        cached_building_record = custom_extended.custom_building_template_records(
            "home", enabled_only=True
        )[0]
        assert cached_building_record is building_record
        assert building_record["name"] == "Archive Cottage"
        assert building_record["max_occupancy"] == 8
        assert building_record["generation_weight"] == 5
        assert building_record["zones"][0]["kind"] == "bedroom"
        assert building_record["colors"][0] == {"floor": 0, "x": 9, "y": 5, "color": "blue"}
        assert building_record["spawns"][0] == {"floor": 0, "x": 11, "y": 6}
        assert not custom_extended.custom_building_template_records(
            "general_store",
            enabled_only=True,
        )
        authored_store_override = custom_extended.custom_building_template_override(
            "authored:make_general_store_map"
        )
        assert authored_store_override is not None
        assert authored_store_override["manual_layout"]
        assert authored_store_override["overrides_builtin"]
        assert "&" not in "".join(authored_store_override["rows"])
        assert authored_store_override["rows"][6][10] == "r"
        procedural_store_override = custom_extended.custom_building_template_override(
            "procedural:general_store:0"
        )
        assert procedural_store_override is not None
        assert procedural_store_override["rows"][6][10] == "s"
        furnishing_home_rows = [
            row.replace("b", "I").replace("f", "k")
            for row in custom_extended.default_custom_building_template_rows("home")
        ]
        furnishing_home = custom_extended.sanitize_custom_building_template({
            "name": "Expanded Furnishing Home",
            "building_type": "home",
            "rows": furnishing_home_rows,
        })
        assert furnishing_home is not None
        furnishing_home_tiles = "".join(furnishing_home["rows"])
        assert "I" in furnishing_home_tiles and "k" in furnishing_home_tiles
        assert "b" not in furnishing_home_tiles and "f" not in furnishing_home_tiles
        building_grid = custom_extended.stamp_custom_building_template(building_record)
        assert building_grid is not None
        assert building_grid[5][9] == "d"
        assert building_grid[5][10] == "P"
        assert building_grid[7][9] == "|"
        assert building_grid[7][10] == "_"
        zone_only_grid = [list(row) for row in custom_extended.default_custom_building_template_rows("home")]
        zone_only_grid[8][14] = "."
        zone_only_grid[8][20] = "b"
        zone_only_template = custom_extended.sanitize_custom_building_template({
            "name": "Zone Metadata Only",
            "building_type": "home",
            "rows": ["".join(row) for row in zone_only_grid],
            "zones": [{"kind": "bedroom", "x1": 8, "y1": 5, "x2": 18, "y2": 9}],
            "enabled": True,
        })
        assert zone_only_template is not None
        zone_only_stamped = custom_extended.stamp_custom_building_template(zone_only_template)
        assert zone_only_stamped is not None
        assert zone_only_stamped[8][14] == "."
        inn_record = custom_extended.custom_building_template_records("inn", enabled_only=True)[0]
        assert inn_record["name"] == "Two Room Inn"
        assert inn_record["max_occupancy"] == 6
        assert len(inn_record["floors"]) == 2
        assert sum(1 for zone in inn_record["zones"] if zone["kind"] == "bedroom") == 3
        assert custom_extended.stamp_custom_building_template(inn_record, 1)[7][31] == ">"
        altered_building_record = dict(building_record)
        altered_floors = [
            {"name": floor["name"], "rows": list(floor["rows"])}
            for floor in building_record["floors"]
        ]
        altered_rows = list(altered_floors[0]["rows"])
        altered_rows[5] = altered_rows[5][:11] + "p" + altered_rows[5][12:]
        altered_floors[0]["rows"] = altered_rows
        altered_building_record["floors"] = altered_floors
        assert (
            custom_extended.custom_building_template_signature(altered_building_record)
            != custom_extended.custom_building_template_signature(building_record)
        )
        custom_farm_game = FarmGame()
        # Public starting-town blueprint overrides are legacy records now.
        # Runtime interiors use modular room graphs and catalog furniture.
        assert custom_farm_game.general_store_map[6][10] != "r"
        assert "&" in "".join(
            "".join(row) for row in custom_farm_game.general_store_map
        )
        assert len(custom_farm_game.general_store_map) == 28
        assert len(custom_farm_game.general_store_map[0]) == 64
        assert custom_farm_game._starting_town_catalog_furniture_cache[
            "GeneralStoreInterior"
        ]
        custom_farm_game.transition_to_general_store()
        authored_override_doors = [
            (x, y)
            for y, row in enumerate(custom_farm_game.general_store_map)
            for x, tile in enumerate(row)
            if tile == "D"
        ]
        assert any(
            abs(custom_farm_game.state.player_x - door_x)
            + abs(custom_farm_game.state.player_y - door_y)
            == 1
            for door_x, door_y in authored_override_doors
        )
        built_in_building_presets = custom_farm_game.built_in_building_template_presets()
        assert len(built_in_building_presets) == 59
        assert len({
            str(record["name"]).casefold()
            for record in built_in_building_presets
        }) == len(built_in_building_presets)
        assert len({
            str(record["builtin_preset_id"])
            for record in built_in_building_presets
        }) == len(built_in_building_presets)
        assert {
            record["_preset_group"]
            for record in built_in_building_presets
        } == {"Starting Town & Farm", "Procedural Town Layouts"}
        assert sum(
            record["_preset_origin"] == "authored"
            for record in built_in_building_presets
        ) == 19
        assert sum(
            record["_preset_origin"] == "procedural"
            for record in built_in_building_presets
        ) == 40
        assert {
            "market_stall",
            "sheriff_office",
        }.issubset({
            str(record["building_type"])
            for record in built_in_building_presets
        })
        assert all(not record["enabled"] for record in built_in_building_presets)
        assert all(record.get("builtin_preset_id") for record in built_in_building_presets)
        built_in_farmhouse = next(
            record
            for record in built_in_building_presets
            if record["name"] == "Built-in Farmhouse"
        )
        assert {"&", "b", "f", "D"}.issubset(set("".join(built_in_farmhouse["rows"])))
        assert built_in_farmhouse["zones"]
        assert built_in_farmhouse["spawns"]
        built_in_blacksmith = next(
            record
            for record in built_in_building_presets
            if record["name"] == "Built-in Blacksmith"
        )
        assert {"q", "o", "w", "a", "x"}.issubset(set("".join(built_in_blacksmith["rows"])))
        procedural_store_presets = [
            record
            for record in built_in_building_presets
            if record["_preset_origin"] == "procedural"
            and record["building_type"] == "general_store"
        ]
        assert len(procedural_store_presets) == 4
        assert len({
            tuple(
                "".join("." if tile != " " else " " for tile in row)
                for row in record["rows"]
            )
            for record in procedural_store_presets
        }) == 4
        override_building = {
            "id": "override-store",
            "type_id": "general_store",
            "name": "Override Store",
        }
        override_seed = next(
            seed
            for seed in range(100)
            if npc_builder.stable_text_seed(
                f"{seed}:general_store:override-store:interior-variants"
            ) % 4 == 0
        )
        override_plan = {
            "id": "override-plan",
            "seed": override_seed,
            "buildings": {"override-store": override_building},
        }
        selected_override = npc_builder.procedural_custom_building_template(
            override_plan,
            override_building,
        )
        assert selected_override is not None
        assert selected_override["builtin_preset_id"] == "procedural:general_store:0"
        assert selected_override["rows"][6][10] == "s"
        copied_store_preset = custom_farm_game.custom_building_editable_preset_copy(
            procedural_store_presets[0],
            [{"name": f"{procedural_store_presets[0]['name']} Copy"}],
        )
        assert copied_store_preset is not None
        assert copied_store_preset["name"].endswith("Copy 2")
        assert not copied_store_preset["enabled"]
        assert "_preset_group" not in copied_store_preset
        assert copied_store_preset["building_type"] == "general_store"
        assert custom_extended.sanitize_custom_building_template({
            "name": "Market Preset",
            "building_type": "market_stall",
        })["building_type"] == "market_stall"
        assert custom_extended.sanitize_custom_building_template({
            "name": "Sheriff Preset",
            "building_type": "sheriff_office",
        })["building_type"] == "sheriff_office"
        assert custom_farm_game.custom_building_mouse_canvas_point({
            "kind": "mouse",
            "x": 9,
            "y": 7,
        }) == (9, 5)
        assert custom_farm_game.custom_building_mouse_canvas_point({
            "kind": "mouse",
            "x": 64,
            "y": 7,
        }) is None
        assert custom_farm_game.custom_building_line_points(
            (5, 5), (9, 5)
        ) == [(5, 5), (6, 5), (7, 5), (8, 5), (9, 5)]
        clipboard_source = [
            "abcdef",
            "ghijkl",
            "mnopqr",
        ]
        clipboard = custom_farm_game.custom_building_extract_clipboard(
            clipboard_source,
            {"x1": 1, "y1": 0, "x2": 3, "y2": 1},
        )
        assert clipboard == ["bcd", "hij"]
        assert custom_farm_game.custom_building_transform_clipboard(
            clipboard,
            "horizontal",
        ) == ["dcb", "jih"]
        assert custom_farm_game.custom_building_transform_clipboard(
            clipboard,
            "vertical",
        ) == ["hij", "bcd"]
        assert custom_farm_game.custom_building_transform_clipboard(
            clipboard,
            "clockwise",
        ) == ["hb", "ic", "jd"]
        pasted_clipboard = custom_farm_game.custom_building_paste_clipboard(
            ["." * 64] * 28,
            ["A ", " B"],
            2,
            3,
            transparent=True,
        )
        assert pasted_clipboard[3][2:4] == "A."
        assert pasted_clipboard[4][2:4] == ".B"
        clipboard_preview = custom_farm_game.custom_building_clipboard_preview(
            ["." * 64] * 28,
            ["A ", " B"],
            63,
            27,
        )
        assert clipboard_preview["tiles"][(63, 27)] == ("A", False)
        assert clipboard_preview["clipped"] == 3
        assert clipboard_preview["overwritten"] == 0
        overwrite_preview_rows = ["." * 64 for _ in range(28)]
        overwrite_preview_rows[4] = overwrite_preview_rows[4][:5] + "#" + overwrite_preview_rows[4][6:]
        overwrite_preview = custom_farm_game.custom_building_clipboard_preview(
            overwrite_preview_rows,
            ["A"],
            5,
            4,
        )
        assert overwrite_preview["tiles"][(5, 4)] == ("A", True)
        assert overwrite_preview["overwritten"] == 1
        transparent_preview = custom_farm_game.custom_building_clipboard_preview(
            overwrite_preview_rows,
            [" A"],
            4,
            4,
            transparent=True,
        )
        assert (4, 4) not in transparent_preview["tiles"]
        assert transparent_preview["overwritten"] == 1
        room_shell = custom_farm_game.custom_building_room_shell(
            [" " * 64] * 28,
            {"x1": 2, "y1": 3, "x2": 6, "y2": 7},
        )
        assert room_shell[3][2:7] == "#####"
        assert room_shell[5][2:7] == "#...#"
        move_source = [["." for _ in range(64)] for _ in range(28)]
        move_source[2][2:5] = list("ABC")
        move_source[3][2:5] = list("DEF")
        moved_selection = custom_farm_game.custom_building_move_selection(
            ["".join(row) for row in move_source],
            {"x1": 2, "y1": 2, "x2": 4, "y2": 3},
            8,
            6,
        )
        assert moved_selection[2][2:5] == "   "
        assert moved_selection[3][2:5] == "   "
        assert moved_selection[6][8:11] == "ABC"
        assert moved_selection[7][8:11] == "DEF"
        room_kits = custom_farm_game.custom_building_room_kits()
        assert len(room_kits) >= 16
        assert len({str(kit["name"]) for kit in room_kits}) == len(room_kits)
        assert all(
            len({len(str(row)) for row in kit["rows"]}) == 1
            for kit in room_kits
        )
        inn_room_kit = next(kit for kit in room_kits if kit["name"] == "Inn Guest Room")
        assert "".join(inn_room_kit["rows"]).count("b") == 1
        furnishing_arrangements = [
            kit
            for kit in room_kits
            if kit.get("group") == "Furnishing Arrangements"
        ]
        assert len(furnishing_arrangements) >= 9
        assert {
            "bedroom",
            "dining",
            "library_stacks",
            "clinic_ward",
            "shopping_counter",
            "storage",
            "workshop",
        }.issubset({str(kit["zone"]) for kit in furnishing_arrangements})
        zone_overlay = custom_farm_game.custom_building_floor_zone_overlay(
            [
                {"kind": "bedroom", "floor": 0, "x1": 1, "y1": 1, "x2": 4, "y2": 4},
                {"kind": "kitchen", "floor": 0, "x1": 4, "y1": 1, "x2": 7, "y2": 4},
                {"kind": "office", "floor": 1, "x1": 8, "y1": 8, "x2": 10, "y2": 10},
            ],
            0,
        )
        assert zone_overlay[(1, 1)] == "B"
        assert zone_overlay[(7, 1)] == "K"
        assert zone_overlay[(4, 2)] == "+"
        assert (8, 8) not in zone_overlay
        original_canvas_clear = custom_menus.clear_screen
        original_color_enabled = support.get_color_enabled()
        try:
            support.set_color_enabled(True)
            custom_menus.clear_screen = lambda: None
            canvas_output = io.StringIO()
            semantic_rows = ["#D&b".ljust(custom_extended.BUILDING_TEMPLATE_WIDTH)] + [
                " " * custom_extended.BUILDING_TEMPLATE_WIDTH
            ] * (custom_extended.BUILDING_TEMPLATE_HEIGHT - 1)
            with contextlib.redirect_stdout(canvas_output):
                custom_farm_game.draw_custom_building_template_canvas(
                    "Colored Canvas",
                    semantic_rows,
                    20,
                    20,
                )
            rendered_canvas = canvas_output.getvalue()
            assert "\x1b[" in rendered_canvas
            assert support.colorize(
                "#",
                visuals.interior_tile_color("#", context="public", ambient=False),
            ) in rendered_canvas
            assert support.colorize(
                "&",
                visuals.interior_tile_color("&", context="public", ambient=False),
            ) in rendered_canvas
        finally:
            custom_menus.clear_screen = original_canvas_clear
            support.set_color_enabled(original_color_enabled)
        horizontal_door_grid = [[" " for _ in range(64)] for _ in range(28)]
        horizontal_door_grid[3][2:7] = list("#####")
        horizontal_door_grid[2][4] = "."
        horizontal_door_grid[4][4] = "."
        smart_horizontal_door, horizontal_door_placed = custom_farm_game.custom_building_smart_door(
            ["".join(row) for row in horizontal_door_grid],
            4,
            3,
        )
        assert horizontal_door_placed
        assert smart_horizontal_door[3][4] == "_"
        vertical_door_grid = [[" " for _ in range(64)] for _ in range(28)]
        for door_y in range(2, 7):
            vertical_door_grid[door_y][4] = "#"
        vertical_door_grid[4][3] = "."
        vertical_door_grid[4][5] = "."
        smart_vertical_door, vertical_door_placed = custom_farm_game.custom_building_smart_door(
            ["".join(row) for row in vertical_door_grid],
            4,
            4,
        )
        assert vertical_door_placed
        assert smart_vertical_door[4][4] == "|"
        exterior_door, exterior_door_placed = custom_farm_game.custom_building_smart_door(
            ["".join(row) for row in horizontal_door_grid],
            3,
            3,
            exterior=True,
        )
        assert exterior_door_placed
        assert exterior_door[3][3] == "D"
        assert set(custom_farm_game.custom_building_flood_points(
            [
                "#####",
                "#..##",
                "#..##",
                "#####",
            ],
            1,
            1,
        )) == {(1, 1), (2, 1), (1, 2), (2, 2)}
        fixture_groups = custom_farm_game.custom_building_fixture_brush_groups()
        grouped_fixture_symbols = [
            symbol
            for _group_name, brushes in fixture_groups
            for _label, symbol, _hint in brushes
        ]
        assert len(grouped_fixture_symbols) == len(set(grouped_fixture_symbols))
        assert set(grouped_fixture_symbols) == {
            symbol
            for _label, symbol, _hint in custom_farm_game.custom_building_fixture_brushes()
        }
        assert {
            "primary_bedroom", "guest_room", "nursery", "bathroom",
            "pantry", "living_room", "private_hall", "service_hall",
        } <= set(custom_extended.BUILDING_TEMPLATE_ZONE_KINDS)
        assert all(
            custom_extended.BUILDING_TEMPLATE_ZONE_LABELS.get(kind)
            for kind in custom_extended.BUILDING_TEMPLATE_ZONE_KINDS
        )
        neutral_fixture_catalog = custom_extended.building_template_fixture_catalog(
            "Smoke Test Building"
        )
        assert set(grouped_fixture_symbols) <= set(neutral_fixture_catalog)
        assert all(
            "uncatalogued" not in neutral_fixture_catalog[symbol]["desc"].lower()
            and neutral_fixture_catalog[symbol]["hint"]
            for symbol in grouped_fixture_symbols
        )
        for authored_location in (
            "GeneralStoreInterior",
            "BlacksmithInterior",
            "LibraryInterior",
            "MayorHouseInterior",
            "InnInterior",
            "FurnitureStoreInterior",
            "CarpenterStoreInterior",
            "AnimalStoreInterior",
            "ClinicInterior",
            "TownHallInterior",
            "MarketRowInterior",
            "MuseumInterior",
            "TownResidenceInterior",
        ):
            assert set(grouped_fixture_symbols) <= set(
                custom_farm_game.town_interior_tile_catalog(authored_location)
            ), f"{authored_location} does not recognize every editor fixture"
        # Room-aware zoning follows architecture like the player's reference
        # inn: each guest room remains distinct, while the counter, kitchen,
        # dining room, and public hall receive coherent functional areas.
        reference_inn_rows = [" " * custom_extended.BUILDING_TEMPLATE_WIDTH for _ in range(16)] + [
            "                        ###############                         ",
            "            #############$...-...-...f#############            ",
            "            #b.l#b.l#b.l#....--&--....#b.l#b.l#b.l#            ",
            "            #b..#b..#b..#.............#b..#b..#b..#            ",
            "            ##.###.###.##.............##.###.###.##            ",
            "            #.....................................#            ",
            "            ##.###.###.##.............##.###.###.##            ",
            "            #b..#b..#b..#.c.........c.#b..#b..#b..#            ",
            "            #b.l#b.l#b.l#ctc..,,,..ctc#b.l#b.l#b.l#            ",
            "            #############.c...,,,...c.#############            ",
            "                        #######D#######                         ",
            " " * custom_extended.BUILDING_TEMPLATE_WIDTH,
        ]
        reference_inn_rows = [
            row.ljust(custom_extended.BUILDING_TEMPLATE_WIDTH)[
                :custom_extended.BUILDING_TEMPLATE_WIDTH
            ]
            for row in reference_inn_rows
        ]
        inferred_reference_zones = custom_farm_game.custom_building_preset_zones(
            [{"name": "Ground Floor", "rows": reference_inn_rows}],
            "inn",
        )
        inferred_reference_bedrooms = {
            (zone["x1"], zone["y1"], zone["x2"], zone["y2"])
            for zone in inferred_reference_zones
            if zone["kind"] == "bedroom"
        }
        assert len(inferred_reference_bedrooms) == 12
        assert {
            "shopping_counter",
            "kitchen",
            "dining",
            "public_hall",
        } <= {str(zone["kind"]) for zone in inferred_reference_zones}
        assert all(
            all(
                reference_inn_rows[y][x] != "#"
                for y in range(zone["y1"], zone["y2"] + 1)
                for x in range(zone["x1"], zone["x2"] + 1)
            )
            for zone in inferred_reference_zones
            if zone["kind"] == "bedroom"
        )
        furnishing_symbols = set(custom_extended.BUILDING_TEMPLATE_FURNISHING_DATA)
        assert len(furnishing_symbols) >= 18
        assert furnishing_symbols.issubset(custom_extended.BUILDING_TEMPLATE_ALLOWED_TILES)
        assert furnishing_symbols.issubset(set(grouped_fixture_symbols))
        furnishing_catalog = custom_farm_game.procedural_town_interior_tile_catalog({
            "name": "Furnishing Test Home",
            "type_id": "home",
        })
        furnishing_blocking = custom_farm_game.procedural_town_interior_blocking_tiles()
        for symbol, furnishing in custom_extended.BUILDING_TEMPLATE_FURNISHING_DATA.items():
            assert symbol in furnishing_catalog
            assert "custom fixture" not in furnishing_catalog[symbol]["desc"].lower()
            assert str(furnishing["name"]).lower() in furnishing_catalog[symbol]["hint"].lower()
            assert symbol in furnishing_blocking
            assert visuals.interior_tile_color(symbol)
        assert custom_extended.building_template_functional_furniture_name(
            custom_extended.BUILDING_TEMPLATE_FURNISHING_DATA["H"]
        ) == "Bookshelf"
        assert custom_extended.building_template_functional_furniture_name(
            custom_extended.BUILDING_TEMPLATE_FURNISHING_DATA["N"]
        ) == "Nightstand"
        assert custom_extended.building_template_functional_furniture_name(
            custom_extended.BUILDING_TEMPLATE_GENERIC_FIXTURE_DATA["f"]
        ) == "Fireplace"
        fixture_visual_game = FarmGame()
        fixture_visual_game.state.location = "TownResidenceInterior"
        fixture_visual_game.state.detailed_glyphs_enabled = True
        fixture_visual_grid = [list("HNLf")]
        assert ANSI_CSI_RE.sub(
            "", fixture_visual_game.render_interior_visual_tile(
                fixture_visual_grid, 0, 0, "home",
            ),
        ) == "▥"
        assert ANSI_CSI_RE.sub(
            "", fixture_visual_game.render_interior_visual_tile(
                fixture_visual_grid, 1, 0, "home",
            ),
        ) == "▤"
        assert ANSI_CSI_RE.sub(
            "", fixture_visual_game.render_interior_visual_tile(
                fixture_visual_grid, 2, 0, "home",
            ),
        ) == "✦"
        assert ANSI_CSI_RE.sub(
            "", fixture_visual_game.render_interior_visual_tile(
                fixture_visual_grid, 3, 0, "home",
            ),
        ) == "♨"
        fixture_visual_game.state.detailed_glyphs_enabled = False
        assert ANSI_CSI_RE.sub(
            "", fixture_visual_game.render_interior_visual_tile(
                fixture_visual_grid, 0, 0, "home",
            ),
        ) == "H"
        duplicated = custom_farm_game.custom_building_duplicate_floor_data(
            [{"name": "Ground Floor", "rows": ["." * 64] * 28}],
            [{"kind": "bedroom", "floor": 0, "x1": 1, "y1": 1, "x2": 4, "y2": 4}],
            [{"floor": 0, "x": 2, "y": 2}],
            [{"floor": 0, "x": 3, "y": 3, "color": "blue"}],
            0,
        )
        duplicate_floors, duplicate_zones, duplicate_spawns, duplicate_colors, duplicate_index = duplicated
        assert duplicate_index == 1
        assert duplicate_floors[1]["name"] == "Ground Floor Copy"
        assert duplicate_zones[-1]["floor"] == 1
        assert duplicate_spawns[-1]["floor"] == 1
        assert duplicate_colors[-1]["floor"] == 1
        transform_rows = [[" " for _ in range(64)] for _ in range(28)]
        transform_rows[3][2] = "A"
        transformed = custom_farm_game.custom_building_transform_floor_data(
            [{"name": "Upper", "rows": ["".join(row) for row in transform_rows]}],
            [{"kind": "office", "floor": 0, "x1": 2, "y1": 3, "x2": 4, "y2": 5}],
            [{"floor": 0, "x": 2, "y": 3}],
            [{"floor": 0, "x": 2, "y": 3, "color": "blue"}],
            0,
            "horizontal",
        )
        transform_floors, transform_zones, transform_spawns, transform_colors = transformed
        assert transform_floors[0]["rows"][3][61] == "A"
        assert (transform_zones[0]["x1"], transform_zones[0]["x2"]) == (59, 61)
        assert transform_spawns[0]["x"] == 61
        assert transform_colors[0]["x"] == 61
        linked_stair_floors, stairs_linked = custom_farm_game.custom_building_link_stair_floors(
            [
                {"name": "Ground", "rows": ["." * 64] * 28},
                {"name": "Upper", "rows": ["." * 64] * 28},
            ],
            0,
            12,
            9,
        )
        assert stairs_linked
        assert linked_stair_floors[0]["rows"][9][12] == "<"
        assert linked_stair_floors[1]["rows"][9][12] == ">"
        weighted_templates = [
            {"name": "Rare", "generation_weight": 1},
            {"name": "Frequent", "generation_weight": 9},
        ]
        weighted_names = [
            npc_builder.weighted_custom_building_template(
                weighted_templates,
                seed,
            )["name"]
            for seed in range(100)
        ]
        assert weighted_names.count("Rare") == 10
        assert weighted_names.count("Frequent") == 90
        assert not custom_farm_game.custom_building_template_validation(
            built_in_farmhouse
        )["critical"]
        isolated_rows = [[" " for _ in range(64)] for _ in range(28)]
        isolated_rows[1][1] = "."
        isolated_rows[27][32] = "D"
        isolated_template = custom_extended.sanitize_custom_building_template({
            "name": "Isolated Door",
            "building_type": "home",
            "rows": ["".join(row) for row in isolated_rows],
        })
        assert custom_farm_game.custom_building_template_validation(
            isolated_template
        )["critical"]
        assert ui.menu_mouse_item_index(
            2,
            1,
            "Mouse Menu",
            [MenuItem("One"), MenuItem("Two")],
            None,
            0,
            2,
        ) == 0
        assert ui.menu_mouse_item_index(
            2,
            3,
            "Mouse Menu",
            [MenuItem("One"), MenuItem("Two")],
            ["Details"],
            0,
            2,
        ) == 0

        original_editor_input = custom_menus.read_key_or_mouse
        original_editor_draw = custom_farm_game.draw_custom_building_template_canvas
        original_editor_menu_select = custom_menus.menu_select
        original_rect_selector = custom_farm_game.custom_building_rect_selector
        custom_farm_game.draw_custom_building_template_canvas = lambda *args, **kwargs: None
        try:
            fixture_events = iter([
                {"kind": "mouse", "x": 5, "y": 7, "left": False, "right": False, "wheel": -1},
                {"kind": "mouse", "x": 5, "y": 7, "left": True, "right": False, "wheel": 0},
                {"kind": "mouse", "x": 9, "y": 7, "left": True, "right": False, "wheel": 0},
                {"kind": "mouse", "x": 9, "y": 7, "left": False, "right": False, "wheel": 0},
                {"kind": "mouse", "x": 7, "y": 7, "left": False, "right": True, "wheel": 0},
                {"kind": "mouse", "x": 8, "y": 7, "left": False, "right": True, "wheel": 0},
                {"kind": "mouse", "x": 8, "y": 7, "left": False, "right": False, "wheel": 0},
                {"kind": "key", "key": "q"},
            ])
            custom_menus.read_key_or_mouse = lambda: next(fixture_events)
            mouse_fixture_rows = custom_farm_game.custom_building_fixture_editor(
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT
            )
            assert mouse_fixture_rows[5][5:10] == "##  #"

            hover_events = iter([
                {
                    "kind": "mouse",
                    "x": 6,
                    "y": 8,
                    "left": True,
                    "right": False,
                    "wheel": 0,
                    "moved": True,
                },
                {
                    "kind": "mouse",
                    "x": 7,
                    "y": 8,
                    "left": False,
                    "right": False,
                    "wheel": 0,
                    "moved": True,
                },
                {"kind": "key", "key": "q"},
            ])
            custom_menus.read_key_or_mouse = lambda: next(hover_events)
            hover_rows = custom_farm_game.custom_building_fixture_editor(
                [" " * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT
            )
            assert not any(row.strip() for row in hover_rows)

            undo_redo_events = iter([
                {"kind": "mouse", "x": 0, "y": 0, "left": False, "right": False, "wheel": -1},
                {"kind": "key", "key": "\r"},
                {"kind": "key", "key": "u"},
                {"kind": "key", "key": "y"},
                {"kind": "key", "key": "q"},
            ])
            custom_menus.read_key_or_mouse = lambda: next(undo_redo_events)
            undo_redo_rows = custom_farm_game.custom_building_fixture_editor(
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT
            )
            assert undo_redo_rows[
                custom_extended.BUILDING_TEMPLATE_HEIGHT // 2
            ][
                custom_extended.BUILDING_TEMPLATE_WIDTH // 2
            ] == "#"

            color_events = iter([
                {"kind": "mouse", "x": 2, "y": 6, "left": True, "right": False, "wheel": 0},
                {"kind": "mouse", "x": 4, "y": 6, "left": True, "right": False, "wheel": 0},
                {"kind": "mouse", "x": 4, "y": 6, "left": False, "right": False, "wheel": 0},
                {"kind": "mouse", "x": 3, "y": 6, "left": False, "right": True, "wheel": 0},
                {"kind": "mouse", "x": 3, "y": 6, "left": False, "right": False, "wheel": 0},
                {"kind": "key", "key": "q"},
            ])
            custom_menus.read_key_or_mouse = lambda: next(color_events)
            mouse_colors = custom_farm_game.custom_building_color_editor(
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT,
                [],
                0,
            )
            mouse_color_points = {
                (int(record["x"]), int(record["y"]), str(record["color"]))
                for record in mouse_colors
            }
            assert (2, 4, "brown") in mouse_color_points
            assert (4, 4, "brown") in mouse_color_points
            assert not any(x == 3 and y == 4 for x, y, _color in mouse_color_points)

            hover_color_events = iter([
                {
                    "kind": "mouse",
                    "x": 6,
                    "y": 8,
                    "left": True,
                    "right": False,
                    "wheel": 0,
                    "moved": True,
                },
                {
                    "kind": "mouse",
                    "x": 6,
                    "y": 8,
                    "left": False,
                    "right": False,
                    "wheel": 0,
                    "moved": True,
                },
                {"kind": "key", "key": "q"},
            ])
            custom_menus.read_key_or_mouse = lambda: next(hover_color_events)
            assert custom_farm_game.custom_building_color_editor(
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT,
                [],
                0,
            ) == []

            rect_events = iter([
                {"kind": "mouse", "x": 2, "y": 4, "left": True, "right": False, "wheel": 0},
                {"kind": "mouse", "x": 7, "y": 8, "left": True, "right": False, "wheel": 0},
                {"kind": "mouse", "x": 7, "y": 8, "left": False, "right": False, "wheel": 0},
            ])
            custom_menus.read_key_or_mouse = lambda: next(rect_events)
            assert custom_farm_game.custom_building_rect_selector(
                "Mouse Rectangle",
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT,
            ) == {"x1": 2, "y1": 2, "x2": 7, "y2": 6}

            point_events = iter([
                {"kind": "mouse", "x": 11, "y": 9, "left": True, "right": False, "wheel": 0},
            ])
            custom_menus.read_key_or_mouse = lambda: next(point_events)
            assert custom_farm_game.custom_building_point_selector(
                "Mouse Point",
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT,
            ) == {"x": 11, "y": 7}

            zone_menu_values = iter(["redraw", 0, custom_menus.MENU_BACK])
            custom_menus.menu_select = lambda *args, **kwargs: SimpleNamespace(
                value=next(zone_menu_values)
            )
            captured_initial_rects = []
            custom_farm_game.custom_building_rect_selector = lambda *args, **kwargs: (
                captured_initial_rects.append(kwargs.get("initial_rect"))
                or {"x1": 4, "y1": 5, "x2": 12, "y2": 13}
            )
            redrawn_zones = custom_farm_game.custom_building_zone_menu(
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT,
                [{"kind": "bedroom", "floor": 0, "x1": 1, "y1": 2, "x2": 8, "y2": 9}],
                0,
            )
            assert captured_initial_rects == [(1, 2, 8, 9)]
            assert redrawn_zones == [
                {"kind": "bedroom", "floor": 0, "x1": 4, "y1": 5, "x2": 12, "y2": 13}
            ]

            zone_delete_values = iter(["delete_floor", "delete", custom_menus.MENU_BACK])
            custom_menus.menu_select = lambda *args, **kwargs: SimpleNamespace(
                value=next(zone_delete_values)
            )
            remaining_zones = custom_farm_game.custom_building_zone_menu(
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT,
                [
                    {"kind": "bedroom", "floor": 0, "x1": 1, "y1": 2, "x2": 8, "y2": 9},
                    {"kind": "office", "floor": 1, "x1": 2, "y1": 3, "x2": 7, "y2": 8},
                ],
                0,
            )
            assert remaining_zones == [
                {"kind": "office", "floor": 1, "x1": 2, "y1": 3, "x2": 7, "y2": 8}
            ]

            custom_menus.menu_select = original_editor_menu_select
            custom_farm_game.custom_building_rect_selector = original_rect_selector

            preview_place_events = iter([
                {"kind": "key", "key": "RIGHT"},
                {"kind": "key", "key": "DOWN"},
                {"kind": "key", "key": "z"},
            ])
            custom_menus.read_key_or_mouse = lambda: next(preview_place_events)
            assert custom_farm_game.custom_building_clipboard_placement_selector(
                "Preview Placement",
                ["." * custom_extended.BUILDING_TEMPLATE_WIDTH]
                * custom_extended.BUILDING_TEMPLATE_HEIGHT,
                ["ABC", "DEF"],
                initial_point=(3, 4),
            ) == {"x": 4, "y": 5}
        finally:
            custom_menus.read_key_or_mouse = original_editor_input
            custom_menus.menu_select = original_editor_menu_select
            custom_farm_game.draw_custom_building_template_canvas = original_editor_draw
            custom_farm_game.custom_building_rect_selector = original_rect_selector
        custom_presets = custom_farm_game.all_tactical_mission_presets()
        custom_preset = next(preset for preset in custom_presets if preset.get("map") == "Hedge Trial")
        custom_mission_request = custom_farm_game.mission_preset_request(custom_preset)
        assert custom_mission_request.map_name == "Hedge Trial"
        assert custom_mission_request.enemy_counts.get("Hedge Beast") == 1
        custom_dungeon_grid = custom_farm_game.make_wilderness_dungeon_map("smoke:custom-room", 1)
        assert "<" in {tile for row in custom_dungeon_grid for tile in row}
        custom_dungeon_max_floor = custom_farm_game.dungeon_max_floor_for_key("smoke:custom-room")
        final_custom_dungeon_grid = custom_farm_game.make_wilderness_dungeon_map(
            "smoke:custom-room",
            custom_dungeon_max_floor,
        )
        assert "P" in {tile for row in final_custom_dungeon_grid for tile in row}
        custom_building_game = FarmGame()
        custom_plan = custom_building_game.wilderness_town_builder().create_plan(
            321,
            654,
            seed=98765,
            name="Template Test",
            style="Crossroads",
        )
        procedural_towns.procedural_town_completed_plan(custom_plan)
        custom_plan["source"] = "procedural_wilderness"
        custom_plan["map_applied"] = True
        custom_building_game.ensure_wilderness_settlements()["321,654"] = custom_plan
        home_template_building = next(
            building
            for building in custom_plan["buildings"].values()
            if building["type_id"] == "home"
        )
        custom_building_game.state.location = procedural_towns.PROCEDURAL_TOWN_INTERIOR_LOCATION
        custom_building_game.state.current_procedural_settlement_key = "321,654"
        custom_building_game.state.current_procedural_building_id = str(home_template_building["id"])
        custom_home_interior = custom_building_game.procedural_town_interior_map(home_template_building)
        template_width, template_height = custom_building_game.procedural_town_interior_source_dimensions(
            home_template_building
        )
        orient_template_position = lambda x, y: custom_building_game.procedural_town_orient_position(
            x,
            y,
            template_width,
            template_height,
            custom_building_game.procedural_town_building_door_side(home_template_building),
        )
        desk_x, desk_y = orient_template_position(9, 5)
        resident_x, resident_y = orient_template_position(10, 5)
        open_door_x, open_door_y = orient_template_position(9, 7)
        closed_door_x, closed_door_y = orient_template_position(10, 7)
        assert custom_home_interior[desk_y][desk_x] == "d"
        assert custom_home_interior[resident_y][resident_x] == "P"
        assert custom_home_interior[open_door_y][open_door_x] == "|"
        assert custom_home_interior[closed_door_y][closed_door_x] == "_"
        assert custom_building_game.procedural_town_interior_tile_passable("|")
        assert not custom_building_game.procedural_town_interior_tile_passable("_")
        assert custom_building_game.procedural_town_custom_tile_color_key(desk_x, desk_y) == "blue"
        expected_spawn = orient_template_position(11, 6)
        assert custom_building_game.procedural_town_template_spawn_anchors(
            custom_plan,
            home_template_building,
        )[0] == expected_spawn
        custom_building_game.use_procedural_town_interior_action(closed_door_x, closed_door_y)
        assert custom_home_interior[closed_door_y][closed_door_x] == "|"
        custom_building_game.use_procedural_town_interior_action(closed_door_x, closed_door_y)
        assert custom_home_interior[closed_door_y][closed_door_x] == "_"
        assert npc_builder.procedural_building_capacity(custom_plan, home_template_building) == 8
        custom_population = custom_building_game.generate_procedural_settlement_population(321, 654, force=True)
        assert custom_population is not None
        custom_household = next(
            household
            for household in custom_population["households"].values()
            if str(household["home_building_id"]) == str(home_template_building["id"])
        )
        assert custom_household["capacity"] == 8
        inn_template_building = next(
            building
            for building in custom_plan["buildings"].values()
            if building["type_id"] == "inn"
        )
        assert npc_builder.procedural_building_capacity(custom_plan, inn_template_building) == 3
        custom_population = custom_building_game.generate_procedural_settlement_population(321, 654, force=True)
        inn_household = next(
            household
            for household in custom_population["households"].values()
            if str(household["home_building_id"]) == str(inn_template_building["id"])
        )
        assert inn_household["capacity"] == 3
        assert len(inn_household["member_ids"]) <= 3
        custom_building_game.state.current_procedural_building_id = str(inn_template_building["id"])
        custom_building_game.state.current_procedural_building_floor = 0
        custom_building_game.state.hour = 22
        custom_building_game.state.weather = "Sunny"
        bedroom_anchors = custom_building_game.procedural_town_template_zone_anchors(
            custom_plan,
            inn_template_building,
            ["bedroom"],
        )
        assert len(bedroom_anchors) == 2
        custom_building_game.state.current_procedural_building_floor = 1
        upper_bedroom_anchors = custom_building_game.procedural_town_template_zone_anchors(
            custom_plan,
            inn_template_building,
            ["bedroom"],
        )
        assert len(upper_bedroom_anchors) == 1
        custom_building_game.state.current_procedural_building_floor = 0
        custom_building_game.ensure_procedural_town_resident_runtime(force_reanchor=True)
        inn_runtime_residents = [
            resident
            for resident in custom_population["residents"].values()
            if str(resident.get("home_building_id")) == str(inn_template_building["id"])
            and str(resident.get("runtime_location")) == f"building:{inn_template_building['id']}"
            and int(resident.get("runtime_floor", 0) or 0) == 0
        ]
        active_bedroom_anchors = bedroom_anchors
        if not inn_runtime_residents:
            custom_building_game.state.current_procedural_building_floor = 1
            custom_building_game.ensure_procedural_town_resident_runtime(force_reanchor=True)
            inn_runtime_residents = [
                resident
                for resident in custom_population["residents"].values()
                if str(resident.get("home_building_id")) == str(inn_template_building["id"])
                and str(resident.get("runtime_location")) == f"building:{inn_template_building['id']}"
                and int(resident.get("runtime_floor", 0) or 0) == 1
            ]
            active_bedroom_anchors = upper_bedroom_anchors
        assert inn_runtime_residents
        for resident in inn_runtime_residents:
            target = (int(resident["runtime_target_x"]), int(resident["runtime_target_y"]))
            assert target in custom_building_game.procedural_town_interior_resident_candidates_for(
                custom_plan,
                inn_template_building,
                resident,
                "late",
            )
        assert active_bedroom_anchors
        custom_request = BattleRequest(
            source="ascii_farmstead",
            return_context={
                "farm_player": {
                    "name": "Custom Tester",
                    "starting_class": "Hedge Warden",
                    "progression": {"class": "Hedge Warden", "active_classes": ["Hedge Warden"]},
                }
            },
        )
        configured_custom_game = configure_game_from_request(BattleGame(), custom_request)
        custom_hero = next(hero for hero in configured_custom_game.heroes if hero.name == "Custom Tester")
        assert configured_custom_game.hero_class(custom_hero) == "Hedge Warden"
        assert "Seed Shot" in configured_custom_game.known_skill_names(custom_hero)
        replacement_library = {
            "version": 1,
            "abilities": [custom_library["abilities"][0]],
            "classes": custom_library["classes"],
            "enemies": [],
            "equipment": [],
            "maps": [],
            "dungeon_rooms": [],
            "building_templates": [],
        }
        replaced, replace_message = custom_content.save_custom_content(replacement_library)
        assert replaced, replace_message
        replacement_game = BattleGame()
        assert "Hedge Warden" not in replacement_game.class_names()
        assert "Hedge Beast" not in replacement_game.enemy_roster_names()
        assert "Farmer Crown" not in replacement_game.equipment_defs()["charm"]
        assert not any(name == "Hedge Trial" for name, _grid, _positions in replacement_game.maps)

        recovery_path = Path(custom_directory) / "recovery_custom_content.json"
        first_library = custom_content.empty_custom_content()
        first_library["abilities"] = [custom_library["abilities"][0]]
        second_library = custom_content.empty_custom_content()
        second_library["abilities"] = custom_library["abilities"][:2]
        assert custom_content.save_custom_content(first_library, recovery_path)[0]
        assert custom_content.save_custom_content(second_library, recovery_path)[0]
        assert custom_content.custom_content_backup_path(recovery_path, 1).exists()
        recovery_path.write_text("{interrupted", encoding="utf-8")
        custom_content.invalidate_custom_content_cache()
        recovered_library, recovery_warnings = custom_content.load_custom_content(recovery_path)
        assert len(recovered_library["abilities"]) == 1
        assert recovery_warnings and "Recovered custom content" in recovery_warnings[0]
        assert list(Path(custom_directory).glob("recovery_custom_content.broken-*.json"))
        assert json.loads(recovery_path.read_text(encoding="utf-8"))["abilities"][0]["name"] == "Seed Shot"

        unrecoverable_path = Path(custom_directory) / "unrecoverable_custom_content.json"
        unrecoverable_path.write_text("{broken", encoding="utf-8")
        custom_content.invalidate_custom_content_cache()
        empty_library, empty_warnings = custom_content.load_custom_content(unrecoverable_path)
        assert empty_library == custom_content.empty_custom_content()
        assert empty_warnings and "no valid recovery copy" in empty_warnings[0]
        assert list(Path(custom_directory).glob("unrecoverable_custom_content.broken-*.json"))
    custom_content.CUSTOM_CONTENT_PATH = original_custom_content_path
    custom_content.invalidate_custom_content_cache()

    pattern_editor_game = FarmGame()
    original_pattern_read_key = custom_menus.read_key
    pattern_keys = iter(["d", "z", "\r"])
    try:
        custom_menus.read_key = lambda: next(pattern_keys)
        with contextlib.redirect_stdout(io.StringIO()):
            edited_pattern = pattern_editor_game.custom_ability_pattern_editor([[0, 0]])
        assert edited_pattern == [[0, 0], [1, 0]]
    finally:
        custom_menus.read_key = original_pattern_read_key

    inline_picker_game = FarmGame()
    inline_records = []
    inline_picker_game.custom_content_data = lambda: {
        "abilities": list(inline_records),
        "classes": [],
    }
    inline_picker_game.custom_ability_builder = lambda: {
        "name": "Inline Pattern",
        "effect": "damage",
        "mp_cost": 3,
        "damage": 5,
        "range_max": 4,
        "shape": "custom",
        "custom_pattern": [[0, 0], [1, 0]],
    }
    inline_picker_game.save_custom_ability_record = lambda record: (
        inline_records.append(dict(record)) or "Saved Inline Pattern."
    )
    original_custom_menu_select = custom_menus.menu_select
    try:
        custom_menus.menu_select = lambda *args, **kwargs: MenuItem(
            "Create a new ability...", value="__create_ability__"
        )
        assert inline_picker_game.custom_ability_picker("Starting Ability") == "Inline Pattern"
    finally:
        custom_menus.menu_select = original_custom_menu_select

    assert helpers.season_for_month(3) == "Spring"
    assert helpers.days_in_month(2, 4) == 29
    assert helpers.format_date(3, 1, 1) == "March 1, Year 1"
    assert all(helpers.precipitation_symbol("Snowy") in {"*", ".", "·"} for _ in range(20))
    for calendar_year in (1, 4, 100, 400, 999):
        slow_days_before = sum(
            366 if helpers.is_leap_year(year) else 365
            for year in range(1, calendar_year)
        )
        slow_days_before += helpers.day_of_year(12, 31, calendar_year) - 1
        assert helpers.weekday_for_date(12, 31, calendar_year) == helpers.WEEKDAY_NAMES[slow_days_before % 7]
    assert helpers.weekday_for_date(1, 1, 10**12) in helpers.WEEKDAY_NAMES
    assert helpers.mine_theme_for_floor(20) == "Crystal Hollows"
    assert "Last day of the month" in helpers.calendar_events_for(3, 31, 1)

    loaded_state = state.GameState(**state.prepare_loaded_state_data({}))
    assert loaded_state.money == 0
    assert loaded_state.town_development_stage == 3
    assert set(loaded_state.unlocked_town_buildings) == set(data.RESTORED_TOWN_BUILDINGS)
    assert state.town_restoration_project_completed(loaded_state, "restore_blacksmith")
    assert loaded_state.completed_scene_ids == []
    assert loaded_state.seen_scene_ids == []
    assert loaded_state.scene_flags == []
    assert loaded_state.combat_level == 1
    assert loaded_state.combat_exp == 0
    assert loaded_state.combat_exp_to_next == 20
    assert loaded_state.combat_current_hp == loaded_state.combat_max_hp
    assert loaded_state.time_speed == data.DEFAULT_TIME_SPEED == "Brisk"
    assert loaded_state.hour == 7 and loaded_state.wake_hour == 7
    assert loaded_state.mine_return_location == "Farm"
    time_speed_game = FarmGame()
    time_speed_game.state.live_time_enabled = True
    time_speed_game.state.time_speed = "Brisk"
    time_speed_game.state.hour = 6
    time_speed_game.state.minute = 0
    time_speed_game.world_tick(data.TIME_SPEED_REAL_SECONDS["Brisk"])
    assert (time_speed_game.state.hour, time_speed_game.state.minute) == (6, 1)
    time_speed_game.state.time_speed = "invalid"
    assert time_speed_game.time_speed_key() == data.DEFAULT_TIME_SPEED
    malformed_state = state.GameState(
        **state.prepare_loaded_state_data({
            "day": None,
            "year": None,
            "player_color": [],
            "tool_levels": "invalid",
            "attended_festival_ids": False,
            "unlocked_mine_elevators": 999,
            "mail_claimed_ids": False,
            "owned_tools": -1,
        })
    )
    assert malformed_state.day == 1
    assert malformed_state.year == 1
    assert malformed_state.player_color == "White"
    assert isinstance(malformed_state.tool_levels, dict)
    assert malformed_state.attended_festival_ids == []
    assert malformed_state.unlocked_mine_elevators == [1]
    assert malformed_state.mail_claimed_ids == []
    assert malformed_state.owned_tools == []
    assert loaded_state.equipped_weapon == "Rusty Sword"
    assert loaded_state.equipped_weapon == DEFAULT_COMBAT_WEAPON
    assert loaded_state.equipped_armor == DEFAULT_COMBAT_ARMOR
    assert loaded_state.equipped_accessory == DEFAULT_COMBAT_ACCESSORY
    assert loaded_state.player_birth_year == -19
    assert loaded_state.player_generation == 1
    assert loaded_state.player_lifespan_age >= 70
    assert loaded_state.dynasty_history == []
    assert loaded_state.dynasty_elders == []
    assert loaded_state.dynasty_kin == []
    assert loaded_state.dynasty_heirlooms == []
    assert loaded_state.aging_and_death_enabled
    assert loaded_state.mortality_mode == "Natural Mortality"
    assert not loaded_state.player_run_ended
    assert loaded_state.player_frozen_age == 0
    assert dynasty.DYNASTY_HEIR_AGE_MONTHS == 216
    loaded_ageless_state = GameState(
        **prepare_loaded_state_data(
            {
                "aging_and_death_enabled": False,
                "player_frozen_age": 42,
            }
        )
    )
    assert not loaded_ageless_state.aging_and_death_enabled
    assert loaded_ageless_state.mortality_mode == "Immortal"
    assert loaded_ageless_state.player_frozen_age == 42

    ageless_game = FarmGame()
    ageless_game.state.year = 80
    ageless_game.state.month = 3
    ageless_game.state.day = 1
    ageless_game.state.player_name = "Mara"
    ageless_game.state.player_birth_year = 20
    ageless_game.state.player_birthday_month = 3
    ageless_game.state.player_birthday_day = 1
    ageless_game.state.player_lifespan_age = 60
    adult_child = {
        "id": 1,
        "name": "Elin",
        "birth_month": 3,
        "birth_day": 1,
        "birth_year": 60,
    }
    teen_child = {
        "id": 2,
        "name": "Tess",
        "birth_month": 3,
        "birth_day": 1,
        "birth_year": 63,
    }
    ageless_game.state.children = [adult_child, teen_child]
    ageless_elder = {
        "id": "dynasty_elder:1",
        "name": "Old Mara",
        "birth_month": 3,
        "birth_day": 1,
        "birth_year": 5,
        "age_years": 75,
        "age_group": "Elder",
        "lifespan_age": 75,
        "active": True,
        "dynasty_elder": True,
    }
    ageless_game.state.dynasty_elders = [ageless_elder]
    ageless_game.set_aging_and_death_enabled(False, autosave=False)
    assert not ageless_game.state.aging_and_death_enabled
    assert ageless_game.player_age() == 60
    assert ageless_game.household_child_age_months(adult_child) == 240
    assert ageless_game.household_child_age_months(teen_child) == 204
    assert "Life stage:" in ageless_game.player_age_display_line()
    assert "Age:" not in ageless_game.player_age_display_line()
    assert "Life stage:" in ageless_game.household_child_age_display_line(
        adult_child
    )
    assert ageless_game.process_player_lifespan_overnight() == ""
    assert ageless_game.process_dynasty_family_overnight() == ""
    assert ageless_elder["active"]
    ageless_game.state.year = 90
    assert ageless_game.player_age() == 60
    assert ageless_game.household_child_age_months(adult_child) == 240
    assert ageless_game.household_child_age_months(teen_child) == 216
    assert "turns" not in " ".join(
        ageless_game.birthday_events_for_date(3, 1, 90)
    )
    ageless_game.set_aging_and_death_enabled(True, autosave=False)
    assert ageless_game.state.aging_and_death_enabled
    assert ageless_game.player_age() == 60
    assert ageless_game.household_child_age_months(adult_child) == 240
    assert ageless_game.household_child_age_months(teen_child) == 216
    ageless_game.state.year = 91
    assert ageless_game.player_age() == 61
    assert ageless_game.household_child_age_months(adult_child) == 252
    assert ageless_game.household_child_age_months(teen_child) == 228

    dynasty_game = FarmGame()
    dynasty_game.state.year = 80
    dynasty_game.state.month = 3
    dynasty_game.state.day = 1
    dynasty_game.state.player_name = "Mara"
    dynasty_game.state.player_birth_year = 20
    dynasty_game.state.player_birthday_month = 3
    dynasty_game.state.player_birthday_day = 1
    dynasty_game.state.player_generation = 1
    dynasty_game.state.player_lifespan_age = 94
    dynasty_game.state.money = 5000
    dynasty_game.state.spouse_npc_id = "mira_seed"
    dynasty_game.state.spouse_moved_to_farm = True
    dynasty_game.state.player_properties["test_property"] = {
        "id": "test_property",
        "town_key": "1,1",
        "building_id": "home:test",
        "name": "Inherited Cottage",
        "kind": "residence",
        "purchase_price": 1000,
        "purchased_day": "",
        "comfort": 2,
        "built": False,
        "upgrade_level": 0,
        "household_moved": False,
        "use_mode": "Private",
        "lifetime_income": 0,
        "last_income_ordinal": 0,
    }
    heir_child = {
        "id": 1,
        "name": "Elin",
        "sex": "Female",
        "birth_month": 2,
        "birth_day": 10,
        "birth_year": 60,
        "parent_npc_id": "",
        "personality_seed": 1221,
        "personality_trait": "Studious",
        "favorite_gift": "Book",
        "apprentice_path": "Scholar",
        "starting_class": "Mystic",
    }
    sibling_child = {
        "id": 2,
        "name": "Tess",
        "sex": "Female",
        "birth_month": 4,
        "birth_day": 12,
        "birth_year": 70,
        "parent_npc_id": "mira_seed",
        "personality_seed": 1442,
        "personality_trait": "Curious",
        "favorite_gift": "Wildflower",
        "apprentice_path": "Builder",
        "starting_class": "Guardian",
    }
    dynasty_game.state.children = [heir_child, sibling_child]
    heir_key = dynasty_game.child_key(heir_child)
    dynasty_game.state.child_learning_points[heir_key] = {
        "Study": 36,
        "Farmcraft": 12,
    }
    dynasty_game.state.child_affection[heir_key] = 180
    dynasty_game.state.child_chore_assignments[heir_key] = "Study help"
    assert dynasty_game.player_age() == 60
    assert dynasty_game.player_birth_date_label() == "March 1, Year 20"
    assert dynasty_game.player_life_stage() == "Senior"
    assert dynasty_game.eligible_dynasty_heirs() == [heir_child]
    assert dynasty_game.designate_dynasty_heir(1)
    assert dynasty_game.can_retire_current_player()[0]
    assert dynasty_game.perform_dynasty_succession(
        1,
        reason="Retirement",
        transition_years=3,
        interactive=False,
        heirloom_type="field_journal",
    )
    assert dynasty_game.state.player_name == "Elin"
    assert dynasty_game.state.player_generation == 2
    assert dynasty_game.state.year == 83
    assert dynasty_game.player_age() == 23
    assert dynasty_game.state.player_background == "Studious Scholar"
    assert dynasty_game.state.player_starting_class == "Mystic"
    assert dynasty_game.state.combat_level >= 2
    assert dynasty_game.state.money == 5000
    assert "test_property" in dynasty_game.state.player_properties
    assert dynasty_game.state.children == []
    assert dynasty_game.state.spouse_npc_id == ""
    assert dynasty_game.state.dynasty_history[-1]["name"] == "Mara"
    assert dynasty_game.state.dynasty_elders[-1]["name"] == "Mara"
    assert any(
        kin.get("name") == "Tess" and kin.get("relation") == "Sibling"
        for kin in dynasty_game.state.dynasty_kin
    )
    assert any(
        kin.get("relation") == "Parent"
        and kin.get("linked_npc_id") == "mira_seed"
        for kin in dynasty_game.state.dynasty_kin
    )
    assert dynasty_game.has_dynasty_heirloom("field_journal")
    assert dynasty_game.state.family_bond == 105
    assert dynasty_game.state.dynasty_transition_log
    assert any(
        "generation: 2" in line.casefold()
        for line in dynasty_game.dynasty_ledger_lines()
    )
    assert any(
        "turns 24" in event
        for event in dynasty_game.birthday_events_for_date(2, 10, 84)
    )
    assert any(
        "Tess" in event
        for event in dynasty_game.birthday_events_for_date(4, 12, 83)
    )
    assert any(
        "Sibling: Tess" in line
        for line in dynasty_game.dynasty_family_tree_lines()
    )
    dynasty_game.state.location = "HouseInterior"
    assert any(
        resident.get("dynasty_elder")
        for resident in dynasty_game.town_npc_position_lookup().values()
    )
    assert any(
        resident.get("dynasty_kin")
        for resident in dynasty_game.town_npc_position_lookup().values()
    )
    retired_elder = dynasty_game.state.dynasty_elders[-1]
    retired_elder["lifespan_age"] = dynasty_game.dynasty_person_age(
        retired_elder
    )
    family_passing = dynasty_game.process_dynasty_family_overnight()
    assert "died peacefully" in family_passing
    assert not retired_elder["active"]
    loaded_dynasty_state = GameState(
        **prepare_loaded_state_data(
            {
                "year": dynasty_game.state.year,
                "month": dynasty_game.state.month,
                "day": dynasty_game.state.day,
                "player_name": dynasty_game.state.player_name,
                "player_sex": dynasty_game.state.player_sex,
                "player_birth_year": dynasty_game.state.player_birth_year,
                "player_birthday_month": dynasty_game.state.player_birthday_month,
                "player_birthday_day": dynasty_game.state.player_birthday_day,
                "player_generation": dynasty_game.state.player_generation,
                "player_lifespan_age": dynasty_game.state.player_lifespan_age,
                "player_background": dynasty_game.state.player_background,
                "player_starting_class": dynasty_game.state.player_starting_class,
                "dynasty_name": dynasty_game.state.dynasty_name,
                "dynasty_history": dynasty_game.state.dynasty_history,
                "dynasty_elders": dynasty_game.state.dynasty_elders,
                "dynasty_kin": dynasty_game.state.dynasty_kin,
                "dynasty_heirlooms": dynasty_game.state.dynasty_heirlooms,
                "dynasty_transition_log": (
                    dynasty_game.state.dynasty_transition_log
                ),
            }
        )
    )
    assert loaded_dynasty_state.player_generation == 2
    assert loaded_dynasty_state.player_birth_year == 60
    assert loaded_dynasty_state.dynasty_history[-1]["name"] == "Mara"
    assert loaded_dynasty_state.dynasty_elders[-1]["name"] == "Mara"
    assert any(
        kin.get("name") == "Tess"
        for kin in loaded_dynasty_state.dynasty_kin
    )
    assert loaded_dynasty_state.dynasty_heirlooms[-1]["type"] == (
        "field_journal"
    )
    assert loaded_dynasty_state.dynasty_transition_log

    death_game = FarmGame()
    death_game.state.year = 100
    death_game.state.month = 6
    death_game.state.day = 15
    death_game.state.player_name = "Old Rowan"
    death_game.state.player_birth_year = 10
    death_game.state.player_birthday_month = 6
    death_game.state.player_birthday_day = 15
    death_game.state.player_lifespan_age = 90
    death_heir = {
        "id": 1,
        "name": "Reed",
        "sex": "Male",
        "birth_month": 1,
        "birth_day": 1,
        "birth_year": 78,
        "parent_npc_id": "",
        "personality_seed": 991,
        "personality_trait": "Practical",
        "favorite_gift": "Stone",
        "apprentice_path": "Builder",
        "starting_class": "Guardian",
    }
    death_game.state.children = [death_heir]
    death_game.state.designated_heir_child_id = 1
    death_message = death_game.process_player_lifespan_overnight()
    assert "died peacefully" in death_message
    assert death_game.state.player_name == "Reed"
    assert death_game.state.player_generation == 2
    assert death_game.state.dynasty_history[-1]["end_reason"] == (
        "Natural death in old age"
    )
    assert death_game.state.dynasty_elders == []
    heirless_game = FarmGame()
    heirless_game.state.year = 95
    heirless_game.state.month = 4
    heirless_game.state.day = 2
    heirless_game.state.player_birth_year = 5
    heirless_game.state.player_birthday_month = 4
    heirless_game.state.player_birthday_day = 2
    heirless_game.state.player_lifespan_age = 90
    grace_message = heirless_game.process_player_lifespan_overnight()
    assert "grace year" in grace_message
    assert heirless_game.state.player_generation == 1
    assert heirless_game.state.player_lifespan_age == 91

    natural_combat_game = FarmGame()
    natural_combat_game.set_mortality_mode("Natural Mortality", autosave=False)
    assert not natural_combat_game.handle_combat_defeat_mortality(
        "Killed by a test slime",
        interactive=False,
    )
    assert not natural_combat_game.state.player_run_ended

    dynasty_death_game = FarmGame()
    dynasty_death_game.autosave_with_message = (
        lambda message: dynasty_death_game.set_message(message)
    )
    dynasty_death_game.save = lambda *args, **kwargs: True
    dynasty_death_game.state.year = 10
    minor_heir = dict(death_heir)
    minor_heir.update({"name": "Young Reed", "birth_year": 5})
    dynasty_death_game.state.children = [minor_heir]
    dynasty_death_game.set_mortality_mode("Dynasty Permadeath", autosave=False)
    assert dynasty_death_game.handle_combat_defeat_mortality(
        "Killed by a cave wyrm",
        source="smoke combat",
        interactive=False,
    )
    assert dynasty_death_game.state.player_name == "Young Reed"
    assert dynasty_death_game.state.player_generation == 2
    assert dynasty_death_game.player_age() >= 18
    assert not dynasty_death_game.state.player_run_ended
    assert dynasty_death_game.state.mortality_history[-1]["successor_name"] == "Young Reed"
    assert "cave wyrm" in dynasty_death_game.state.player_death_record["death_cause"]

    true_death_game = FarmGame()
    true_death_game.save = lambda *args, **kwargs: True
    true_death_game.set_mortality_mode("True Permadeath", autosave=False)
    assert true_death_game.handle_combat_defeat_mortality(
        "Killed by the final test dragon",
        source="smoke combat",
        interactive=False,
    )
    assert true_death_game.state.player_run_ended
    assert true_death_game.state.player_run_outcome == "death"
    assert true_death_game.state.combat_current_hp == 0
    assert any("final test dragon" in line for line in true_death_game.player_memorial_lines())

    deterministic_contract_a = victory.build_victory_contract(
        player_name="Aster",
        birth_year=76,
        starting_class="Fighter",
        wilderness_seed=1337,
        start_month=3,
        start_day=1,
        start_year=100,
    )
    deterministic_contract_b = victory.build_victory_contract(
        player_name="Aster",
        birth_year=76,
        starting_class="Fighter",
        wilderness_seed=1337,
        start_month=3,
        start_day=1,
        start_year=100,
    )
    assert deterministic_contract_a == deterministic_contract_b
    assert len(deterministic_contract_a["objectives"]) == 5
    assert {objective["category"] for objective in deterministic_contract_a["objectives"]} == {
        "Economy", "Exploration", "Mastery", "Community", "Legacy",
    }
    assert len({objective["metric"] for objective in deterministic_contract_a["objectives"]}) == 5
    assert not victory.sanitize_victory_contract({
        "objectives": [{"category": "Economy", "metric": "wealth", "target": 1}],
    })

    malformed_finite_state = GameState(
        victory_mode=victory.VICTORY_MODE_FINITE,
        victory_contract={
            "objectives": [{"category": "Economy", "metric": "wealth", "target": 1}],
        },
    )
    assert malformed_finite_state.victory_mode == victory.VICTORY_MODE_OPEN
    assert malformed_finite_state.victory_contract == {}

    synthetic_contract = victory.sanitize_victory_contract({
        "id": "smoke-victory",
        "title": "The Tested Legacy",
        "created_month": 3,
        "created_day": 1,
        "created_year": 100,
        "objectives": [
            {
                "category": "Economy", "metric": "wealth", "title": "Reserve",
                "description": "Hold funds.", "target": 100, "unit": "g",
            },
            {
                "category": "Exploration", "metric": "explored_chunks", "title": "Survey",
                "description": "Explore regions.", "target": 2, "unit": "regions",
            },
            {
                "category": "Mastery", "metric": "combat_level", "title": "Train",
                "description": "Gain levels.", "target": 2, "unit": "level",
            },
            {
                "category": "Community", "metric": "town_stage", "title": "Restore",
                "description": "Develop town.", "target": 1, "unit": "stage",
            },
            {
                "category": "Legacy", "metric": "gear_enhancement", "title": "Temper",
                "description": "Enhance gear.", "target": 1, "unit": "ranks",
            },
        ],
    })
    assert synthetic_contract
    victory_game = FarmGame()
    victory_game.save = lambda *args, **kwargs: True
    victory_game.configure_victory_mode(victory.VICTORY_MODE_FINITE, synthetic_contract)
    victory_game.state.money = 0
    assert not victory_game.check_victory_completion(interactive=False)
    victory_game.state.money = 100
    victory_game.state.wilderness_chunks_visited = 2
    victory_game.state.combat_level = 2
    victory_game.state.town_development_stage = 1
    victory_game.state.inventory[DEFAULT_COMBAT_WEAPON] = 1
    victory_game.state.equipment_workshop = {
        DEFAULT_COMBAT_WEAPON: {"enhancement": 1, "reforge_count": 0},
    }
    assert victory_game.victory_completed_objective_count() == 5
    assert victory_game.check_victory_completion(interactive=False)
    assert victory_game.state.player_run_ended
    assert victory_game.state.player_run_outcome == "victory"
    assert victory_game.state.victory_contract["completed"]
    assert victory_game.state.victory_record["contract_title"] == "The Tested Legacy"
    assert victory_game.state.victory_record["objectives"]
    assert any("read-only" in line for line in victory_game.victory_summary_lines())
    assert not victory_game.check_victory_completion(interactive=False)

    victory_round_trip = GameState(**prepare_loaded_state_data({
        "player_run_ended": True,
        "player_run_outcome": "victory",
        "victory_mode": victory.VICTORY_MODE_FINITE,
        "victory_contract": victory_game.state.victory_contract,
        "victory_record": victory_game.state.victory_record,
    }))
    assert victory_round_trip.player_run_ended
    assert victory_round_trip.player_run_outcome == "victory"
    assert victory_round_trip.victory_contract["completed"]
    with TemporaryDirectory() as victory_temp_dir:
        victory_save_path = Path(victory_temp_dir) / "victory.json"
        victory_save_path.write_text(json.dumps({
            "state": {
                "player_run_ended": True,
                "player_run_outcome": "victory",
                "victory_record": victory_game.state.victory_record,
                "player_name": "Aster",
                "month": 3,
                "day": 8,
                "year": 100,
            },
        }), encoding="utf-8")
        assert victory_game.save_file_summary(victory_save_path).startswith("VICTORY | Aster")

    immortal_game = FarmGame()
    immortal_game.set_mortality_mode("Immortal", autosave=False)
    assert not immortal_game.state.aging_and_death_enabled
    assert not immortal_game.combat_defeat_is_lethal()
    assert loaded_state.cleared_mine_floors == []
    assert loaded_state.mine_recent_combat_maps == []
    assert loaded_state.mine_recent_combat_signatures == []
    assert loaded_state.unlocked_party_member_ids == []
    assert loaded_state.active_party_member_ids == []
    assert loaded_state.max_party_members == 4
    assert loaded_state.party_tactic == "Balanced"
    assert loaded_state.manual_party_member_ids == []
    assert loaded_state.travel_follower_ids == []
    assert loaded_state.max_travel_followers == 3
    assert loaded_state.travel_follower_states == {}
    assert loaded_state.wilderness_settlements == {}
    assert loaded_state.procedural_settlement_populations == {}
    assert loaded_state.current_procedural_settlement_key == ""
    assert loaded_state.current_procedural_building_id == ""
    assert loaded_state.bounty_board_offers == {}
    assert loaded_state.active_bounties == {}
    assert loaded_state.completed_bounty_log == []
    loaded_bounty_state = state.GameState(**state.prepare_loaded_state_data({
        "bounty_board_offers": {
            "4,-2": {
                "week_key": "1-1-W0",
                "town_key": "4,-2",
                "town_name": "Testwatch",
                "offers": [{
                    "id": "posted",
                    "title": "Wanted: Test Target",
                    "target_name": "Test Target",
                    "species": "Bandit",
                    "chunk_x": "7",
                    "chunk_y": "-3",
                    "reward_money": "120",
                    "reward_items": {"Old Coin": "2", "Bad": "not-number"},
                    "status": "defeated",
                    "target_defeated": True,
                }],
            },
        },
        "active_bounties": {
            "active": {
                "id": "active",
                "title": "Wanted: Active Target",
                "target_name": "Active Target",
                "species": "Wolf",
                "chunk_x": 8,
                "chunk_y": -4,
                "reward_money": 150,
                "reward_items": {"Small Pelt": 1},
                "status": "accepted",
            },
            "claimed": {
                "id": "claimed",
                "status": "claimed",
            },
        },
        "completed_bounty_log": [{
            "id": "done",
            "title": "Wanted: Old Target",
            "target_name": "Old Target",
            "chunk_x": 1,
            "chunk_y": 2,
            "status": "defeated",
        }],
    }))
    assert loaded_bounty_state.bounty_board_offers["4,-2"]["offers"][0]["status"] == "available"
    assert loaded_bounty_state.bounty_board_offers["4,-2"]["offers"][0]["target_defeated"] is False
    assert loaded_bounty_state.bounty_board_offers["4,-2"]["offers"][0]["reward_items"] == {"Old Coin": 2}
    assert list(loaded_bounty_state.active_bounties) == ["active"]
    assert loaded_bounty_state.completed_bounty_log[0]["status"] == "claimed"
    assert loaded_bounty_state.completed_bounty_log[0]["target_defeated"] is True
    loaded_work_state = state.GameState(**state.prepare_loaded_state_data({
        "travel_follower_ids": ["spouse:mira_seed"],
        "travel_follower_states": {
            "spouse:mira_seed": {
                "mode": "work",
                "task": "plant_seeds",
                "work_day": "1-3-1",
                "work_units": 2,
                "task_xp": {"water_crops": 5, "plant_seeds": 3},
                "work_totals": {"water_crops": 9, "gather_forage": 2, "clear_debris": 1, "invalid": 4},
                "work_log": ["1-3-1, 07:00 - watered Turnip"],
                "bond_points": "18",
                "checkin_day": "1-3-1",
                "shared_moment_day": "",
                "outing_day": "1-3-1",
                "outing_locations": ["Farm", "Farm", "Town"],
                "outing_bond_count": 2,
                "memory_flags": ["visited:Farm", "visited:Farm"],
                "memories": ["1-3-1 - Set out across the home fields together."],
                "expedition_role": "Gatherer",
                "bond_milestones": ["Familiar", "Familiar", "invalid"],
                "forage_find_day": "1-3-1",
            },
        },
    }))
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["mode"] == "work"
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["task"] == "plant_seeds"
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["task_xp"] == {
        "water_crops": 5,
        "plant_seeds": 3,
    }
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["work_totals"] == {
        "water_crops": 9,
        "gather_forage": 2,
        "clear_debris": 1,
    }
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["bond_points"] == 18
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["outing_locations"] == ["Farm", "Town"]
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["memory_flags"] == ["visited:Farm"]
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["expedition_role"] == "Gatherer"
    assert loaded_work_state.travel_follower_states["spouse:mira_seed"]["bond_milestones"] == ["Familiar"]
    assert loaded_state.party_member_hp == {}
    assert loaded_state.party_member_focus == {}
    assert loaded_state.party_member_last_relationship_gain_day == {}
    assert loaded_state.completed_resident_request_ids == []
    assert loaded_state.completed_companion_quest_ids == []
    assert loaded_state.automation_machines == {}
    assert loaded_state.museum_donated_record_ids == []
    assert loaded_state.museum_donation_counts == {}
    assert loaded_state.museum_reward_claims == []
    assert loaded_state.museum_exhibit_unlocks == []
    assert loaded_state.excavation_sites == {}
    assert loaded_state.excavation_discoveries == []
    assert loaded_state.excavation_exp == 0
    assert loaded_state.archaeology_finds == 0
    assert loaded_state.paleontology_finds == 0
    assert loaded_state.tavern_blackjack_stats == {}
    assert loaded_state.tavern_checkers_stats == {}
    assert loaded_state.tavern_checkers_match == {}
    assert loaded_state.tavern_chess_stats == {}
    assert loaded_state.tavern_chess_match == {}
    assert loaded_state.tavern_mancala_stats == {}
    assert loaded_state.tavern_mancala_match == {}
    assert loaded_state.tavern_holdem_stats == {}
    assert loaded_state.tavern_hearts_stats == {}
    assert loaded_state.tavern_hearts_match == {}
    assert loaded_state.tavern_solitaire_stats == {}
    assert loaded_state.tavern_solitaire_match == {}
    assert loaded_state.tavern_ur_stats == {}
    assert loaded_state.tavern_ur_match == {}
    assert loaded_state.tavern_game_discoveries == []
    assert loaded_state.marriage_month == 0
    assert loaded_state.family_event_log == []
    assert loaded_state.hud_activity_log == []
    assert loaded_state.show_hud_sidebar is True
    assert loaded_state.family_event_flags == []
    assert loaded_state.pregnancy_checkup_months_seen == []
    assert loaded_state.child_milestone_flags == []
    assert loaded_state.family_help_enabled is True
    assert loaded_state.family_bond == 0
    assert loaded_state.family_meal_last_day == ""
    assert loaded_state.family_last_meal == ""
    assert loaded_state.spouse_support_mode == "Balanced"
    assert loaded_state.child_affection == {}
    assert loaded_state.child_last_gift_day == {}
    assert loaded_state.child_last_lesson_day == {}
    assert loaded_state.child_learning_points == {}
    assert loaded_state.child_chore_assignments == {}
    child_state = state.GameState(children=[{
        "id": 1,
        "name": "Test Child",
        "sex": "Male",
        "birth_month": 3,
        "birth_day": 1,
        "birth_year": 1,
        "parent_npc_id": "finn_fisher",
    }])
    assert child_state.children[0]["personality_trait"] == ""
    assert "favorite_gift" in child_state.children[0]
    assert child_state.children[0]["starting_class"] == ""
    capped_party_state = state.GameState(
        max_party_members=9,
        party_tactic="Not Real",
        manual_party_member_ids=["a", "a", "z"],
        unlocked_party_member_ids=["a", "a", "b", ""],
        active_party_member_ids=["a", "b", "c", "d"],
    )
    assert capped_party_state.max_party_members == 4
    assert capped_party_state.party_tactic == "Balanced"
    assert capped_party_state.manual_party_member_ids == ["a", "z"]
    assert capped_party_state.unlocked_party_member_ids == ["a", "b"]
    assert capped_party_state.active_party_member_ids == ["a", "b", "c"]
    legacy_mine_state = state.GameState(**state.prepare_loaded_state_data({"mine_floor": 3, "deepest_mine_floor": 4}))
    assert legacy_mine_state.mine_floor == 3
    assert legacy_mine_state.deepest_mine_floor == 4
    assert legacy_mine_state.cleared_mine_floors == [1, 2, 3]
    assert legacy_mine_state.unlocked_mine_down_stairs == [1, 2, 3]
    assert legacy_mine_state.mine_floor_clear_rewards_claimed == [1, 2, 3]
    migrated_combat_state = state.GameState(**state.prepare_loaded_state_data({
        "combat_current_hp": "bad",
        "equipped_weapon": "Missing",
        "equipped_armor": "Missing",
        "equipped_accessory": "Missing",
    }))
    assert migrated_combat_state.combat_current_hp == migrated_combat_state.combat_max_hp
    assert migrated_combat_state.equipped_weapon == "Rusty Sword"
    assert migrated_combat_state.equipped_armor == "Work Clothes"
    assert migrated_combat_state.equipped_accessory == "None"
    migrated_recovery_state = state.GameState(**state.prepare_loaded_state_data({
        "natural_stamina_recovery_minutes": "bad",
        "natural_health_recovery_minutes": 999,
        "natural_health_recovery_delay_minutes": -8,
    }))
    assert migrated_recovery_state.natural_stamina_recovery_minutes == 0
    assert migrated_recovery_state.natural_health_recovery_minutes == 19
    assert migrated_recovery_state.natural_health_recovery_delay_minutes == 0
    migrated_profile = build_player_combat_profile(migrated_combat_state)
    assert migrated_profile["weapon"] == DEFAULT_COMBAT_WEAPON
    assert migrated_profile["armor"] == DEFAULT_COMBAT_ARMOR
    assert migrated_profile["accessory"] == DEFAULT_COMBAT_ACCESSORY
    legacy_loot_state = state.GameState(**state.prepare_loaded_state_data({
        "money": 100,
        "combat_campaign_inventory": {"Coin": 3, "Shard": 1, "Relic Cache": 1},
    }))
    assert legacy_loot_state.money == 100 + 15
    assert legacy_loot_state.inventory["Crystal Shard"] >= 1
    assert legacy_loot_state.inventory["Gold Ore"] >= 1
    assert legacy_loot_state.combat_campaign_inventory == {}
    assert state.Crop("Turnip").symbol() == "'"
    assert GameState is state.GameState
    assert prepare_loaded_state_data is state.prepare_loaded_state_data
    assert issubclass(FarmGame, building.BuildingMixin)
    assert FarmGame.build_mode.__module__ == "ascii_farmstead_building"
    assert FarmGame.move_placed_object.__module__ == "ascii_farmstead_building"
    detour_step = actors.shortest_path_step(
        (0, 0),
        [(2, 0)],
        lambda x, y: 0 <= x < 3 and 0 <= y < 3 and (x, y) != (1, 0),
    )
    assert detour_step == (0, 1)
    assert actors.shortest_path_step(
        (0, 0),
        [(1, 0)],
        lambda x, y: (x, y) != (1, 0),
    ) is None

    actor_game = FarmGame()
    actor_game.state.location = "Town"
    actor_game.state.hour = 10
    actor_game.state.minute = 0
    actor_game.state.weather = "Sunny"
    actor_game.state.player_x = 5
    actor_game.state.player_y = 7
    coop_key = "Farm:15,9"
    actor_game.state.placed_objects[coop_key] = "Chicken Coop"
    for y in range(7, 14):
        for x in range(13, 22):
            actor_game.base_map[y][x] = "."
    blocked_grazing_tile = (14, 9)
    actor_game.crops[f"Farm:{blocked_grazing_tile[0]},{blocked_grazing_tile[1]}"] = state.Crop("Turnip")
    actor = actor_game.make_farm_animal("Chicken", coop_key)
    actor["id"] = 7001
    actor["name"] = "Actor Hen"
    actor_game.state.farm_animals.append(actor)
    assert blocked_grazing_tile not in actor_game.farm_animal_home_tiles(actor)
    actor_game.update_farm_animal_actors(force=True)
    assert actor["outside"] is True
    assert actor_game.farm_animal_actor_position(actor) in actor_game.farm_animal_home_tiles(actor)

    actor_game.state.location = "Farm"
    actor["fed"] = False
    actor["last_grazed_day"] = ""
    assert actor_game.farm_animal_apply_grazing(actor, force=True)
    assert actor["fed"] is True
    assert actor["last_grazed_day"] == actor_game.farm_animal_day_key()
    assert actor["activity"] == "grazing"
    assert actor_game.farm_animal_growth_stage(actor) == "Baby"
    assert not actor_game.farm_animal_product_ready(actor)
    actor["age"] = actor_game.farm_animal_maturity_days(actor)
    actor["product_ready_count"] = 0
    actor["product_progress"] = 0
    actor_game.state.inventory["Animal Feed"] = 1
    actor_game.state.inventory["Grooming Brush"] = 1
    actor["fed"] = False
    assert actor_game.hand_feed_single_farm_animal(actor)
    assert actor["fed"] and actor["hand_fed_today"]
    assert actor_game.state.inventory["Animal Feed"] == 0
    assert actor_game.pet_single_farm_animal(actor)
    assert actor_game.brush_single_farm_animal(actor)
    assert actor_game.clean_animal_shelter(coop_key)
    actor_game.update_farm_animals_overnight()
    assert actor["care_streak"] == 1
    assert actor["product_ready_count"] == 1
    assert actor_game.farm_animal_product_ready(actor)
    egg_before = int(actor_game.state.inventory.get("Bird Egg", 0))
    assert actor_game.collect_single_animal_product(actor)
    assert int(actor_game.state.inventory.get("Bird Egg", 0)) == egg_before + 1
    assert actor["product_ready_count"] == 0
    assert any("Affection:" in line for line in actor_game.farm_animal_detail_lines(actor))
    assert actor_game.farm_animal_product_cycle_days({"species": "Sheep"}) == 5

    actor["outside"] = True
    actor["x"], actor["y"] = 20, 10
    actor_game.state.player_x = 19
    actor_game.state.player_y = 10
    player_before = (actor_game.state.player_x, actor_game.state.player_y)
    animal_before = actor_game.farm_animal_actor_position(actor)
    actor_game.move(1, 0)
    assert (actor_game.state.player_x, actor_game.state.player_y) == player_before
    assert actor_game.farm_animal_actor_position(actor) != animal_before
    assert actor["activity"] == "startled"

    home_tile = actor_game.farm_animal_home_tiles(actor)[0]
    actor_game.state.player_x = 5
    actor_game.state.player_y = 7
    actor["outside"] = True
    actor["x"], actor["y"] = home_tile
    actor_game.state.hour = 20
    actor_game.state.weather = "Sunny"
    actor_game.update_farm_animal_actors(force=True)
    assert actor["outside"] is False
    assert (actor["x"], actor["y"]) == (-1, -1)

    actor["outside"] = True
    actor["x"], actor["y"] = home_tile
    actor_game.state.hour = 12
    actor_game.state.weather = "Storm"
    actor_game.update_farm_animal_actors(force=True)
    assert actor["outside"] is False
    assert (actor["x"], actor["y"]) == (-1, -1)
    actor_game.state.location = "Town"
    actor_game.state.hour = 12
    actor_game.state.weather = "Sunny"
    actor["outside"] = True
    actor["x"], actor["y"] = 20, 10
    actor["activity"] = "watching clouds"
    actor_save_fields = {
        field: actor[field]
        for field in ["last_grazed_day", "outside", "x", "y", "activity"]
    }

    follower_game = FarmGame()
    follower_game.autosave_with_message = lambda message: follower_game.set_message(message)
    follower_game.state.location = "Farm"
    follower_game.state.player_x = 8
    follower_game.state.player_y = 9
    follower_game.state.spouse_npc_id = "mira_seed"
    follower_game.state.spouse_moved_to_farm = True
    spouse_follower_id = "spouse:mira_seed"
    follower_game.state.travel_follower_ids = [spouse_follower_id]
    follower_game.state.travel_follower_states = {
        spouse_follower_id: {
            "location": "Home",
            "x": -1,
            "y": -1,
            "mode": "follow",
            "activity": "joining you",
        }
    }
    follower_game.normalize_travel_followers()
    assert spouse_follower_id in follower_game.travel_follower_candidate_ids()
    assert follower_game.recover_travel_follower(spouse_follower_id)
    spouse_position = follower_game.travel_follower_position(spouse_follower_id)
    assert spouse_position is not None
    assert actors.manhattan_distance(
        spouse_position,
        (follower_game.state.player_x, follower_game.state.player_y),
    ) == 1
    follower_game.set_travel_follower_mode(spouse_follower_id, "wait")
    waiting_position = follower_game.travel_follower_position(spouse_follower_id)
    assert waiting_position == spouse_position
    follower_game.set_travel_follower_mode(spouse_follower_id, "follow")
    assert follower_game.travel_follower_position(spouse_follower_id) == waiting_position
    assert follower_game.travel_follower_identity_for_npc_id("mira_seed") == spouse_follower_id
    work_crop_x, work_crop_y = 10, 10
    follower_game.base_map[work_crop_y][work_crop_x] = ","
    work_crop = state.Crop("Turnip")
    follower_game.set_crop_for_scope("Farm", work_crop_x, work_crop_y, work_crop)
    follower_game.state.hour = 6
    follower_game.state.minute = 50
    assert "plant_seeds" in follower_game.travel_follower_task_options(spouse_follower_id)
    assert "clear_debris" in follower_game.travel_follower_task_options(spouse_follower_id)
    assert follower_game.assign_travel_follower_task(spouse_follower_id, "water_crops")
    follower_game.advance_time(20)
    assert work_crop.watered
    spouse_work_record = follower_game.travel_follower_record(spouse_follower_id)
    assert spouse_work_record["work_units"] == 1
    assert spouse_work_record["task_xp"]["water_crops"] == 2
    assert spouse_work_record["work_totals"]["water_crops"] == 1
    assert "watering Turnip" in spouse_work_record["work_log"][-1]
    assert follower_game.travel_follower_preferred_task(spouse_follower_id) == "water_crops"
    assert follower_game.travel_follower_work_limit(spouse_follower_id) == 7
    assert follower_game.travel_follower_position(spouse_follower_id) == (work_crop_x, work_crop_y)
    water_job = follower_game.travel_follower_job_profile(spouse_follower_id, "water_crops")
    assert water_job["title"] == "Irrigation Helper"
    assert water_job["preferred"] is True
    assert water_job["daily_limit"] == 7

    plant_x, plant_y = 13, 10
    follower_game.base_map[plant_y][plant_x] = ","
    follower_game.state.selected_seed = "Turnip"
    follower_game.state.inventory["Turnip Seeds"] = 1
    assert follower_game.assign_travel_follower_task(spouse_follower_id, "plant_seeds")
    follower_game.advance_time(60)
    planted_crop = follower_game.crop_for_scope("Farm", plant_x, plant_y)
    assert planted_crop is not None and planted_crop.name == "Turnip"
    assert follower_game.state.inventory["Turnip Seeds"] == 0
    assert spouse_work_record["task_xp"]["plant_seeds"] == 1
    plant_report = follower_game.travel_follower_work_report_lines(spouse_follower_id)
    assert "FOLLOWER JOB REPORT" in plant_report
    assert any("Field Sower" in line for line in plant_report)
    assert any("Job morale:" in line for line in plant_report)

    harvest_x, harvest_y = 11, 10
    follower_game.base_map[harvest_y][harvest_x] = ","
    harvest_crop = state.Crop(
        "Turnip",
        age=data.CROP_DATA["Turnip"]["growth_days"],
        ready=True,
        care_days=data.CROP_DATA["Turnip"]["growth_days"],
    )
    follower_game.set_crop_for_scope("Farm", harvest_x, harvest_y, harvest_crop)
    turnips_before = sum(
        qty for item_name, qty in follower_game.state.inventory.items()
        if item_name.endswith("Turnip")
    )
    assert follower_game.assign_travel_follower_task(spouse_follower_id, "harvest_crops")
    follower_game.advance_time(60)
    assert follower_game.crop_for_scope("Farm", harvest_x, harvest_y) is None
    assert sum(
        qty for item_name, qty in follower_game.state.inventory.items()
        if item_name.endswith("Turnip")
    ) == turnips_before + 1

    follower_game.state.farm_animals = [{
        "id": 501,
        "name": "Pip",
        "species": "Chicken",
        "trait": "Gentle",
        "building_key": "test-coop",
        "fed": False,
        "petted_today": False,
        "happiness": 50,
        "health": 100,
        "affection": 0,
        "x": 12,
        "y": 10,
    }]
    follower_game.state.inventory["Mixed Seeds"] = 1
    assert follower_game.assign_travel_follower_task(spouse_follower_id, "animal_care")
    follower_game.advance_time(60)
    cared_animal = follower_game.state.farm_animals[0]
    assert cared_animal["fed"]
    assert cared_animal["petted_today"]
    assert follower_game.state.inventory["Mixed Seeds"] == 0
    debris_before = sum(row.count("^") + row.count("o") + row.count("*") for row in follower_game.base_map)
    if debris_before == 0:
        follower_game.base_map[2][2] = "^"
        debris_before = 1
    material_before = sum(int(follower_game.state.inventory.get(item, 0)) for item in ["Wood", "Stone", "Fiber"])
    assert follower_game.assign_travel_follower_task(spouse_follower_id, "clear_debris")
    follower_game.advance_time(60)
    debris_after = sum(row.count("^") + row.count("o") + row.count("*") for row in follower_game.base_map)
    material_after = sum(int(follower_game.state.inventory.get(item, 0)) for item in ["Wood", "Stone", "Fiber"])
    assert debris_after == debris_before - 1
    assert material_after > material_before
    clear_job = follower_game.travel_follower_job_profile(spouse_follower_id, "clear_debris")
    assert clear_job["title"] == "Groundskeeper"
    assert clear_job["output"] == "cleared farm space"
    assert follower_game.set_travel_follower_mode(spouse_follower_id, "follow")
    player_start = (follower_game.state.player_x, follower_game.state.player_y)
    follower_game.move(1, 0)
    assert (follower_game.state.player_x, follower_game.state.player_y) != player_start
    assert actors.manhattan_distance(
        follower_game.travel_follower_position(spouse_follower_id),
        (follower_game.state.player_x, follower_game.state.player_y),
    ) <= 1
    spouse_profile = follower_game.travel_follower_combat_profile(spouse_follower_id)
    assert spouse_profile["name"] == "Mira"
    assert follower_game.active_farmstead_companion_profiles()[0]["id"] == spouse_follower_id
    follower_game.transition_to_mine()
    assert follower_game.travel_follower_position(spouse_follower_id) is not None
    spouse_record = follower_game.travel_follower_record(spouse_follower_id)
    spouse_bond_before = follower_game.travel_follower_bond_points(spouse_follower_id)
    spouse_relation_before = follower_game.town_npc_relationship("mira_seed")
    family_bond_before = follower_game.family_bond_score()
    spouse_line, spouse_checkin_gain = follower_game.check_in_with_travel_follower(spouse_follower_id)
    assert spouse_line
    assert spouse_checkin_gain == 1
    assert follower_game.check_in_with_travel_follower(spouse_follower_id)[1] == 0
    assert follower_game.town_npc_relationship("mira_seed") == spouse_relation_before + 1
    assert follower_game.family_bond_score() == family_bond_before + 1
    moment_bond_before = follower_game.travel_follower_bond_points(spouse_follower_id)
    moment_relation_before = follower_game.town_npc_relationship("mira_seed")
    moment_family_before = follower_game.family_bond_score()
    shared, shared_detail = follower_game.share_travel_follower_moment(spouse_follower_id)
    assert shared and "Mira" in shared_detail
    assert follower_game.travel_follower_bond_points(spouse_follower_id) == moment_bond_before + 4
    assert follower_game.town_npc_relationship("mira_seed") == moment_relation_before + 2
    assert follower_game.family_bond_score() == moment_family_before + 2
    assert any("Mira" in memory for memory in spouse_record["memories"])
    assert not follower_game.share_travel_follower_moment(spouse_follower_id)[0]
    follower_game.state.location = "Wilderness"
    spouse_record["outing_day"] = "previous-day"
    spouse_record["outing_locations"] = []
    spouse_record["outing_bond_count"] = 0
    outing_bond_before = follower_game.travel_follower_bond_points(spouse_follower_id)
    assert follower_game.record_travel_follower_outing(spouse_follower_id)
    assert not follower_game.record_travel_follower_outing(spouse_follower_id)
    assert follower_game.travel_follower_bond_points(spouse_follower_id) == outing_bond_before + 1
    outing_theme = follower_game.travel_follower_location_theme()[0]
    assert f"visited:{outing_theme}" in spouse_record["memory_flags"]
    assert follower_game.travel_follower_bond_points(spouse_follower_id) >= spouse_bond_before + 6
    spouse_record["bond_points"] = 9
    spouse_record["bond_milestones"] = []
    follower_game.adjust_travel_follower_bond(spouse_follower_id, 1)
    assert spouse_record["bond_milestones"] == ["Familiar"]
    assert follower_game.travel_follower_expedition_role_options(spouse_follower_id) == [
        "Balanced",
        "Scout",
        "Gatherer",
    ]
    spouse_record["mode"] = "wait"
    assert follower_game.set_travel_follower_expedition_role(spouse_follower_id, "Gatherer")
    spouse_record["mode"] = "follow"
    spouse_record["outing_day"] = "previous-day"
    spouse_record["outing_locations"] = []
    spouse_record["outing_bond_count"] = 0
    spouse_record["forage_find_day"] = ""
    follower_game.state.location = "Wilderness"
    gatherer_theme = follower_game.travel_follower_location_theme()[0]
    found_item = follower_game.travel_follower_outing_find(spouse_follower_id, gatherer_theme)
    found_before = follower_game.state.inventory.get(found_item, 0)
    assert follower_game.record_travel_follower_outing(spouse_follower_id)
    assert follower_game.state.inventory.get(found_item, 0) == found_before + 1
    assert spouse_record["forage_find_day"] == follower_game.travel_follower_work_day_key()
    spouse_record["bond_points"] = 64
    skill_points_before = int(
        follower_game.combat_progress_for_key(
            follower_game.travel_follower_tactical_key(spouse_follower_id)
        ).get("skill_points", 0)
    )
    follower_game.adjust_travel_follower_bond(spouse_follower_id, 1)
    assert "Close" in spouse_record["bond_milestones"]
    assert int(
        follower_game.combat_progress_for_key(
            follower_game.travel_follower_tactical_key(spouse_follower_id)
        ).get("skill_points", 0)
    ) == skill_points_before + 1
    spouse_record["mode"] = "wait"
    assert follower_game.set_travel_follower_expedition_role(spouse_follower_id, "Guardian")
    spouse_record["mode"] = "follow"
    guardian_profile = follower_game.travel_follower_combat_profile(spouse_follower_id)
    spouse_record["expedition_role"] = "Balanced"
    balanced_profile = follower_game.travel_follower_combat_profile(spouse_follower_id)
    assert guardian_profile["defense"] == balanced_profile["defense"] + 1
    assert guardian_profile["max_hp"] == balanced_profile["max_hp"] + 3
    spouse_record["mode"] = "wait"
    assert follower_game.set_travel_follower_expedition_role(spouse_follower_id, "Support")
    spouse_record["mode"] = "follow"
    support_profile = follower_game.travel_follower_combat_profile(spouse_follower_id)
    assert support_profile["max_focus"] == balanced_profile["max_focus"] + 3
    assert support_profile["inventory"]["Potion"] == balanced_profile["inventory"].get("Potion", 0) + 1
    spouse_record["mode"] = "wait"
    assert follower_game.set_travel_follower_expedition_role(spouse_follower_id, "Scout")
    spouse_record["mode"] = "follow"
    spouse_record["outing_day"] = follower_game.travel_follower_work_day_key()
    spouse_record["outing_locations"] = []
    spouse_record["outing_bond_count"] = 0
    scout_bond_before = follower_game.travel_follower_bond_points(spouse_follower_id)
    for location in ["Farm", "Town", "Mine"]:
        follower_game.state.location = location
        assert follower_game.record_travel_follower_outing(spouse_follower_id)
    assert follower_game.travel_follower_bond_points(spouse_follower_id) == scout_bond_before + 3
    forage_before = sum(follower_game.state.inventory.values())
    follower_game.state.location = "Farm"
    assert follower_game.assign_travel_follower_task(spouse_follower_id, "gather_forage")
    follower_game.advance_time(60)
    assert sum(follower_game.state.inventory.values()) == forage_before + 1
    assert spouse_record["work_totals"]["gather_forage"] == 1
    assert follower_game.set_travel_follower_mode(spouse_follower_id, "follow")
    follower_game.travel_follower_record(spouse_follower_id)["mode"] = "wait"
    assert follower_game.active_farmstead_companion_profiles() == []
    follower_game.travel_follower_record(spouse_follower_id)["mode"] = "follow"

    follower_game.state.children = [{
        "id": 77,
        "name": "Scout",
        "sex": "Female",
        "birth_month": 3,
        "birth_day": 1,
        "birth_year": 5,
        "parent_npc_id": "mira_seed",
        "personality_seed": 77,
        "personality_trait": "Curious",
        "favorite_gift": "Wildflower",
        "apprentice_path": "Scholar",
        "starting_class": "Mystic",
    }]
    follower_game.state.year = 10
    follower_game.state.month = 3
    follower_game.state.day = 1
    child_follower_id = "child:77"
    assert follower_game.household_child_stage(follower_game.state.children[0]) == "Young Child"
    assert child_follower_id in follower_game.travel_follower_candidate_ids()
    assert follower_game.travel_follower_task_options(child_follower_id) == ["animal_care"]
    assert not follower_game.travel_follower_can_enter_location(child_follower_id, "Mine")
    assert not follower_game.travel_follower_combat_eligible(child_follower_id)
    follower_game.state.location = "Farm"
    follower_game.state.travel_follower_ids = [child_follower_id]
    follower_game.state.travel_follower_states[child_follower_id] = {
        "location": "Home",
        "x": -1,
        "y": -1,
        "mode": "follow",
        "activity": "joining you",
    }
    follower_game.normalize_travel_followers()
    assert follower_game.recover_travel_follower(child_follower_id)
    follower_game.state.location = "Mine"
    follower_game.sync_travel_followers()
    assert follower_game.travel_follower_position(child_follower_id) is None
    assert follower_game.travel_follower_record(child_follower_id)["activity"] == "waiting safely at home"
    follower_game.state.location = "Farm"
    follower_game.sync_travel_followers()
    assert follower_game.travel_follower_position(child_follower_id) is not None
    child = follower_game.state.children[0]
    child_affection_before = follower_game.child_affection_score(child)
    child_family_before = follower_game.family_bond_score()
    child_line, child_checkin_gain = follower_game.check_in_with_travel_follower(child_follower_id)
    assert child_line
    assert child_checkin_gain == 1
    assert follower_game.child_affection_score(child) == child_affection_before + 1
    child_moment_affection = follower_game.child_affection_score(child)
    child_moment_family = follower_game.family_bond_score()
    child_learning_before = follower_game.child_learning_map(child).get("Farming", 0)
    child_shared, child_detail = follower_game.share_travel_follower_moment(child_follower_id)
    assert child_shared and "Scout" in child_detail
    assert follower_game.child_affection_score(child) == child_moment_affection + 4
    assert follower_game.family_bond_score() == child_moment_family + 2
    assert follower_game.child_learning_map(child)["Farming"] == child_learning_before + 1
    assert any("Scout" in memory for memory in follower_game.travel_follower_record(child_follower_id)["memories"])
    assert not follower_game.share_travel_follower_moment(child_follower_id)[0]
    assert follower_game.family_bond_score() >= child_family_before + 2
    cared_animal["fed"] = True
    cared_animal["petted_today"] = False
    child_record = follower_game.travel_follower_record(child_follower_id)
    child_record["work_totals"]["animal_care"] = 3
    care_learning_before = follower_game.child_learning_map(child).get("Care", 0)
    assert follower_game.assign_travel_follower_task(child_follower_id, "animal_care")
    follower_game.advance_time(60)
    assert child_record["work_totals"]["animal_care"] == 4
    assert follower_game.child_learning_map(child)["Care"] == care_learning_before + 1
    assert follower_game.set_travel_follower_mode(child_follower_id, "follow")
    follower_save_fields = dict(follower_game.travel_follower_record(child_follower_id))

    formation_game = FarmGame()
    formation_game.autosave_with_message = lambda message: formation_game.set_message(message)
    formation_game.state.location = "Farm"
    formation_game.state.player_x = 8
    formation_game.state.player_y = 9
    formation_game.state.facing = "DOWN"
    formation_game.state.year = 30
    formation_game.state.month = 3
    formation_game.state.day = 1
    formation_game.state.spouse_npc_id = "mira_seed"
    formation_game.state.spouse_moved_to_farm = True
    formation_game.state.children = [
        {
            "id": child_id,
            "name": child_name,
            "sex": "Female",
            "birth_month": 3,
            "birth_day": 1,
            "birth_year": 5,
            "parent_npc_id": "mira_seed",
            "personality_seed": child_id,
            "personality_trait": "Curious",
            "favorite_gift": "Wildflower",
            "apprentice_path": "Scholar",
            "starting_class": "Mystic",
        }
        for child_id, child_name in [(77, "Scout"), (78, "Rowan"), (79, "Wren")]
    ]
    formation_ids = [spouse_follower_id, "child:77", "child:78"]
    for follower_id in formation_ids:
        assert formation_game.set_travel_follower(follower_id)
    assert formation_game.state.max_travel_followers == 3
    assert formation_game.active_travel_follower_ids() == formation_ids
    assert formation_game.travel_follower_position(spouse_follower_id) == (8, 8)
    assert formation_game.travel_follower_position("child:77") == (9, 9)
    assert formation_game.travel_follower_position("child:78") == (7, 9)
    assert {
        profile["id"]
        for profile in formation_game.active_farmstead_companion_profiles()
    } == set(formation_ids)
    active_profiles = formation_game.active_farmstead_companion_profiles()
    progression_by_name = {
        str(profile.get("name")): str(profile.get("progression_id"))
        for profile in active_profiles
    }
    assert progression_by_name["Mira"] == "mira_seed"
    assert progression_by_name["Scout"] == "child:77"
    request = formation_game.farmstead_tactical_request(
        "Spring Bloomfield",
        ["Slime"],
        "Defeat All",
        {},
        "family-smoke",
        "Family Smoke",
        "",
    )
    assert request.return_context["farm_progression_keys"]["Mira"] == "mira_seed"
    assert request.return_context["farm_progression_keys"]["Scout"] == "child:77"
    battle_game = configure_game_from_request(BattleGame(), request)
    assert "Mira" not in battle_game.tactic_description()
    loadout_labels = [str(option.get("label", "")) for option in battle_game.loadout_options()]
    assert "Upgrade Mira bow" not in loadout_labels
    assert "Upgrade Scout's weapon" in loadout_labels
    synthetic_result = SimpleNamespace(
        return_context={"farm_progression_keys": request.return_context["farm_progression_keys"]},
        party_progression={
            "Mira": {"level": 1, "xp": 12, "skill_points": 2, "class": "Ranger", "subclass": "Storm"},
            "Scout": {"level": 1, "xp": 9, "skill_points": 2, "class": "Mystic", "subclass": "Storm"},
        },
        class_progress={},
        defeated_enemies=[],
        outcome="victory",
        result="victory",
        mission_id="",
        mission_name="Synthetic",
        objective="Defeat All",
        summary="Synthetic victory",
        loot={},
    )
    formation_game.apply_tactical_progression_result(synthetic_result)
    assert formation_game.state.combat_party_progress["mira_seed"]["xp"] == 12
    assert formation_game.state.combat_party_progress["child:77"]["xp"] == 9
    assert "spouse:mira_seed" not in formation_game.state.combat_party_progress
    tactical_family_keys = formation_game.tactical_member_keys(unlocked_only=True)
    assert "mira_seed" in tactical_family_keys
    assert "child:77" in tactical_family_keys
    assert "child:78" in tactical_family_keys
    child_training = formation_game.combat_progress_for_key("child:77")
    assert child_training["class"] == "Mystic"
    assert formation_game.tactical_member_name("child:77") == "Scout"
    assert "Young Adult" in formation_game.tactical_member_role("child:77")
    assert formation_game.tactical_default_gear_for_key("child:77")["weapon"] == "Light Wand"
    assert not formation_game.set_travel_follower("child:79")
    assert "full" in formation_game.state.message.lower()
    assert formation_game.set_travel_follower_formation_slot("child:78", 0)
    assert formation_game.active_travel_follower_ids() == ["child:78", spouse_follower_id, "child:77"]
    assert formation_game.travel_follower_formation_label("child:78") == "Rear guard"
    assert formation_game.travel_follower_formation_label(spouse_follower_id) == "Left flank"
    formation_start = (formation_game.state.player_x, formation_game.state.player_y)
    formation_game.move(0, 1)
    assert (formation_game.state.player_x, formation_game.state.player_y) != formation_start
    formation_positions = [
        formation_game.travel_follower_position(follower_id)
        for follower_id in formation_game.active_travel_follower_ids()
    ]
    assert all(position is not None for position in formation_positions)
    assert len(set(formation_positions)) == 3
    assert (formation_game.state.player_x, formation_game.state.player_y) not in set(formation_positions)
    assert all(
        actors.manhattan_distance(
            position,
            (formation_game.state.player_x, formation_game.state.player_y),
        ) <= 2
        for position in formation_positions
    )
    assert formation_game.travel_follower_movement_style() == "Adaptive"
    assert formation_game.travel_follower_effective_movement_style() == "Formation"
    assert formation_game.set_travel_follower_movement_style("Single File")
    assert formation_game.travel_follower_effective_movement_style() == "Single File"
    line_start = (formation_game.state.player_x, formation_game.state.player_y)
    formation_game.move(0, 1)
    line_ids = formation_game.active_travel_follower_ids()
    line_positions = [
        formation_game.travel_follower_position(follower_id)
        for follower_id in line_ids
    ]
    assert line_positions[0] == line_start
    assert all(position is not None for position in line_positions)
    assert len(set(line_positions)) == len(line_positions)
    player_before_backtrack = (
        formation_game.state.player_x,
        formation_game.state.player_y,
    )
    first_follower_before_backtrack = formation_game.travel_follower_position(line_ids[0])
    assert first_follower_before_backtrack is not None
    formation_game.move(
        first_follower_before_backtrack[0] - player_before_backtrack[0],
        first_follower_before_backtrack[1] - player_before_backtrack[1],
    )
    assert (
        formation_game.state.player_x,
        formation_game.state.player_y,
    ) == first_follower_before_backtrack
    assert formation_game.travel_follower_position(line_ids[0]) == player_before_backtrack
    formation_game.state.location = "House"
    assert formation_game.set_travel_follower_movement_style("Adaptive")
    assert formation_game.travel_follower_effective_movement_style() == "Single File"
    formation_game.state.location = "Farm"
    formation_game.reform_travel_follower_formation()
    assert formation_game.set_travel_follower_mode("child:78", "home")
    assert formation_game.active_travel_follower_ids() == [spouse_follower_id, "child:77"]
    assert formation_game.travel_follower_formation_label(spouse_follower_id) == "Rear guard"
    assert formation_game.travel_follower_formation_label("child:77") == "Left flank"
    assert formation_game.set_travel_follower_mode(spouse_follower_id, "wait")
    assert formation_game.regroup_travel_followers()
    assert all(
        formation_game.travel_follower_record(follower_id)["mode"] == "follow"
        for follower_id in formation_game.active_travel_follower_ids()
    )
    assert all(
        formation_game.travel_follower_position(follower_id) is not None
        for follower_id in formation_game.active_travel_follower_ids()
    )

    settlement_builder = town_builder.WildernessTownBuilder()
    settlement_plan = settlement_builder.create_plan(
        4,
        -2,
        seed=918273,
        name="Smoke Crossing",
        style="Crossroads",
    )
    settlement_plan_repeat = settlement_builder.create_plan(
        4,
        -2,
        seed=918273,
        name="Smoke Crossing",
        style="Crossroads",
    )
    assert settlement_plan == settlement_plan_repeat
    assert settlement_plan["name"] == "Smoke Crossing"
    assert len(settlement_plan["lots"]) == 12
    assert len(settlement_plan["buildings"]) == 12
    assert settlement_builder.validate(settlement_plan) == {"errors": [], "warnings": []}
    varied_settlement_plan = settlement_builder.create_plan(
        5,
        -2,
        seed=918274,
        name="Smoke Crossing Variant",
        style="Crossroads",
    )
    assert settlement_builder.validate(varied_settlement_plan) == {"errors": [], "warnings": []}
    settlement_signature = sorted(
        (
            building["type_id"],
            building["lot_id"],
            building["x"],
            building["y"],
        )
        for building in settlement_plan["buildings"].values()
    )
    varied_settlement_signature = sorted(
        (
            building["type_id"],
            building["lot_id"],
            building["x"],
            building["y"],
        )
        for building in varied_settlement_plan["buildings"].values()
    )
    assert settlement_signature != varied_settlement_signature
    settlement_summary = settlement_builder.summary(settlement_plan)
    assert settlement_summary["tier"] == "Survey Camp"
    assert settlement_summary["buildings_planned"] == 12
    assert settlement_summary["buildings_complete"] == 0
    assert len(settlement_builder.preview(settlement_plan)) == 38
    assert any("S" in row for row in settlement_builder.preview(settlement_plan))

    manual_plan = settlement_builder.create_plan(
        8,
        3,
        seed=4455,
        name="Manual Hamlet",
        starter_layout=False,
    )
    assert settlement_builder.add_road_line(manual_plan, (43, 36), (43, 12)) > 0
    assert settlement_builder.add_lot(
        manual_plan,
        "civic_lot",
        31,
        5,
        9,
        6,
        "Civic",
    )
    assert not settlement_builder.add_lot(
        manual_plan,
        "overlap_lot",
        33,
        6,
        9,
        6,
        "Civic",
    )
    manual_hall_id = settlement_builder.place_building(
        manual_plan,
        "civic_lot",
        "town_hall",
        building_id="manual_hall",
    )
    assert manual_hall_id == "manual_hall"
    assert settlement_builder.queue_building(manual_plan, manual_hall_id)
    for expected_phase in ["Foundation", "Frame", "Complete"]:
        manual_hall = manual_plan["buildings"][manual_hall_id]
        requirements = town_builder.settlement_phase_requirements(manual_hall)
        accepted = settlement_builder.contribute(
            manual_plan,
            manual_hall_id,
            materials=dict(requirements["materials"]),
            money=int(requirements["money"]),
        )
        assert accepted["materials"] == requirements["materials"]
        assert accepted["money"] == requirements["money"]
        progress = settlement_builder.apply_labor(manual_plan, int(requirements["labor"]))
        assert progress and expected_phase in progress[-1]
    assert town_builder.settlement_building_phase(manual_plan["buildings"][manual_hall_id]) == "Complete"
    assert settlement_builder.summary(manual_plan)["buildings_complete"] == 1

    settlement_game = FarmGame()
    settlement_game.autosave_with_message = lambda message: settlement_game.set_message(message)
    authored_town_before = [row[:] for row in settlement_game.town_map]
    wilderness_before = [
        row[:]
        for row in settlement_game.get_wilderness_chunk_map(4, -2)
    ]
    game_plan = settlement_game.create_wilderness_settlement_plan(
        4,
        -2,
        style="Market Ring",
        name="Future Market",
    )
    assert game_plan["style"] == "Market Ring"
    assert settlement_game.town_map == authored_town_before
    overlay_preview = settlement_game.wilderness_settlement_preview(4, -2, over_wilderness=True)
    assert overlay_preview
    assert settlement_game.get_wilderness_chunk_map(4, -2) == wilderness_before
    assert settlement_game.town_map == authored_town_before
    structural_validation = settlement_game.wilderness_settlement_validation(
        4,
        -2,
        check_terrain=False,
    )
    assert structural_validation["errors"] == []
    terrain_validation = settlement_game.wilderness_settlement_validation(
        4,
        -2,
        check_terrain=True,
    )
    assert terrain_validation["errors"] == []
    assert settlement_game.wilderness_settlement_report_lines(4, -2)
    project_id = next(iter(game_plan["buildings"]))
    assert settlement_game.queue_wilderness_settlement_building(4, -2, project_id)
    project = game_plan["buildings"][project_id]
    project_requirements = town_builder.settlement_phase_requirements(project)
    settlement_game.state.money = int(project_requirements["money"])
    for item_name, qty in project_requirements["materials"].items():
        settlement_game.state.inventory[item_name] = int(qty)
    settlement_contribution = settlement_game.contribute_to_wilderness_settlement(
        4,
        -2,
        project_id,
    )
    assert settlement_contribution["money"] == project_requirements["money"]
    assert settlement_contribution["materials"] == project_requirements["materials"]
    settlement_progress = settlement_game.advance_wilderness_settlement_construction(
        4,
        -2,
        int(project_requirements["labor"]),
    )
    assert settlement_progress and "Foundation" in settlement_progress[0]
    settlement_save_fields = state.prepare_loaded_state_data({
        "wilderness_settlements": settlement_game.state.wilderness_settlements,
    })["wilderness_settlements"]
    assert "4,-2" in settlement_save_fields

    assert len(npc_builder.ADDITIONAL_FEMALE_GIVEN_NAMES) == 150
    assert len(npc_builder.ADDITIONAL_MALE_GIVEN_NAMES) == 150
    assert (
        len(npc_builder.ADDITIONAL_FEMALE_GIVEN_NAMES)
        + len(npc_builder.ADDITIONAL_MALE_GIVEN_NAMES)
    ) == 300
    all_procedural_given_names = (
        npc_builder.FEMALE_GIVEN_NAMES
        + npc_builder.MALE_GIVEN_NAMES
    )
    assert len(all_procedural_given_names) == 348
    assert len({
        name.casefold()
        for name in all_procedural_given_names
    }) == len(all_procedural_given_names)
    procedural_builder = npc_builder.ProceduralNpcBuilder()
    name_probe_plan = {"seed": 90210}
    sampled_female_names = {
        procedural_builder.choose_given_name(
            name_probe_plan,
            f"female-name-probe:{index}",
            "Female",
        )
        for index in range(1000)
    }
    sampled_male_names = {
        procedural_builder.choose_given_name(
            name_probe_plan,
            f"male-name-probe:{index}",
            "Male",
        )
        for index in range(1000)
    }
    assert sampled_female_names & set(npc_builder.ADDITIONAL_FEMALE_GIVEN_NAMES)
    assert sampled_male_names & set(npc_builder.ADDITIONAL_MALE_GIVEN_NAMES)
    assert len(npc_builder.ADDITIONAL_SURNAMES) == 300
    assert len(npc_builder.SURNAMES) == 324
    assert len({
        surname.casefold()
        for surname in npc_builder.SURNAMES
    }) == len(npc_builder.SURNAMES)
    sampled_surnames = {
        procedural_builder.household_surname(
            name_probe_plan,
            f"surname-probe:{index}",
        )
        for index in range(1200)
    }
    assert sampled_surnames & set(npc_builder.ADDITIONAL_SURNAMES)
    assert sampled_surnames.issubset(set(npc_builder.SURNAMES))
    population_plan = settlement_builder.create_plan(
        11,
        -7,
        seed=602214,
        name="Generational Crossing",
        style="Crossroads",
    )
    for population_building in population_plan["buildings"].values():
        population_building["phase_index"] = 3
        population_building["status"] = "complete"
    generated_population = procedural_builder.create_population(population_plan)
    repeated_population = procedural_builder.create_population(population_plan)
    assert generated_population == repeated_population
    population_summary = procedural_builder.summary(generated_population)
    assert population_summary["population"] > 0
    assert population_summary["households"] > 0
    assert population_summary["employed"] > 0
    assert population_summary["children"] >= 1
    assert population_summary["teens"] >= 1
    assert population_summary["elders"] >= 1
    assert population_summary["roles"]["Mayor"] == 1
    assert population_summary["roles"]["Doctor"] == 1
    assert population_summary["average_job_skill"] > 0
    assert population_summary["average_job_morale"] > 0
    assert population_summary["weekly_wages"] > 0
    assert population_summary["service_tags"]
    assert population_summary["occupied_rooms"] > 0
    assert population_summary["residents_without_rooms"] >= 0
    assert procedural_builder.validate(
        generated_population,
        population_plan,
    ) == {"errors": [], "warnings": []}
    generated_ids = set(generated_population["residents"])
    assert len(generated_ids) == population_summary["population"]
    for generated_household in generated_population["households"].values():
        assert generated_household["head_resident_id"] in generated_household["member_ids"]
        assert generated_household["room_assignment_version"] == 2
        room_assigned_ids = {
            resident_id
            for occupant_ids in generated_household["room_assignments"].values()
            for resident_id in occupant_ids
        }
        assert room_assigned_ids.isdisjoint(
            set(generated_household["unassigned_room_member_ids"])
        )
        assert room_assigned_ids | set(generated_household["unassigned_room_member_ids"]) == set(
            generated_household["member_ids"]
        )
        household_home = population_plan["buildings"][generated_household["home_building_id"]]
        sleeping_rooms = {
            room["id"]: room
            for room in npc_builder.procedural_building_sleeping_rooms(
                population_plan,
                household_home,
            )
        }
        if (
            household_home["type_id"] == "home"
            and npc_builder.procedural_custom_building_template(
                population_plan,
                household_home,
            ) is None
        ):
            assert not generated_household["unassigned_room_member_ids"]
            assert generated_household["architectural_capacity"] == sum(
                room["capacity"] for room in sleeping_rooms.values()
            )
            if any(
                generated_population["residents"][resident_id]["age_group"] == "Child"
                for resident_id in generated_household["member_ids"]
            ):
                assert "nursery" in generated_household["room_conversions"].values()
                assert any(room["role"] == "nursery" for room in sleeping_rooms.values())
        assert set(generated_household["room_assignments"]) <= set(sleeping_rooms)
        for room_id, occupant_ids in generated_household["room_assignments"].items():
            assert len(occupant_ids) <= sleeping_rooms[room_id]["capacity"]
            if household_home["type_id"] == "inn":
                assert len(occupant_ids) == 1
        married_ids = generated_household.get("married_couple_ids", [])
        if married_ids:
            assert len(married_ids) == 2
            married_people = [generated_population["residents"][resident_id] for resident_id in married_ids]
            assert {resident["sex"] for resident in married_people} == {"Male", "Female"}
            assert all(resident["marital_status"] == "Married" for resident in married_people)
            married_room_ids = {resident["assigned_room_id"] for resident in married_people}
            if "" not in married_room_ids and household_home["type_id"] != "inn":
                assert len(married_room_ids) == 1
    for generated_resident in generated_population["residents"].values():
        assert generated_resident["household_role"] != "Partner"
        assert set(npc_builder.PROCEDURAL_ROUTINE_PHASES).issubset(
            generated_resident["schedule"]
        )
        assert generated_resident["home_building_id"] in population_plan["buildings"]
        assert population_plan["buildings"][generated_resident["home_building_id"]]["phase_index"] == 3
        household = generated_population["households"][generated_resident["household_id"]]
        if generated_resident["assigned_room_id"]:
            assert generated_resident["assigned_room_label"]
            assert generated_resident["id"] in household["room_assignments"][generated_resident["assigned_room_id"]]
            assert generated_resident["assigned_room_label"].lower() in generated_resident["schedule"]["late"]["activity"]
        else:
            assert generated_resident["id"] in household["unassigned_room_member_ids"]
        job_profile = generated_resident["job_profile"]
        assert job_profile["title"]
        assert job_profile["duties"]
        assert job_profile["service_tags"]
        assert 0 <= job_profile["skill"] <= 5
        assert 0 <= job_profile["morale"] <= 100
        assert job_profile["quality"] in {"Learning", "Capable", "Skilled", "Expert"}
        workplace_id = generated_resident["workplace_building_id"]
        if workplace_id:
            assert workplace_id in population_plan["buildings"]
            assert population_plan["buildings"][workplace_id]["phase_index"] == 3
            assert job_profile["workplace"]
            assert job_profile["weekly_wage"] > 0
        if generated_resident["age_group"] in {"Child", "Teen"}:
            assert generated_resident["guardian_ids"]
            assert all(
                guardian_id in generated_population["residents"]
                for guardian_id in generated_resident["guardian_ids"]
            )
    routine_resident = next(iter(generated_population["residents"].values()))
    assert procedural_builder.routine_for(routine_resident, "work_morning")
    assert procedural_builder.routine_for(
        routine_resident,
        "work_morning",
        bad_weather=True,
    ) == routine_resident["schedule"]["bad_weather"]
    work_dialogue = npc_dialogue.ProceduralNpcDialogueBuilder().lines_for_topic(
        routine_resident,
        generated_population,
        {
            "phase": "work_morning",
            "bad_weather": False,
            "weather": "sunny",
            "season": "spring",
        },
        "work",
    )
    assert any("skill" in line and "morale" in line for line in work_dialogue)
    sanitized_population = npc_builder.sanitize_procedural_settlement_populations({
        "11,-7": generated_population
    })["11,-7"]
    sanitized_resident = next(iter(sanitized_population["residents"].values()))
    assert sanitized_resident["job_profile"]["title"]
    assert sanitized_resident["job_profile"]["service_tags"]
    assert "assigned_room_id" in sanitized_resident
    assert all(
        household["room_assignment_version"] == 2
        and "architectural_capacity" in household
        and "room_conversions" in household
        for household in sanitized_population["households"].values()
    )

    workplace_only_plan = settlement_builder.create_plan(
        12,
        -7,
        seed=602215,
        name="Unhoused Works",
        starter_layout=False,
    )
    assert settlement_builder.add_lot(
        workplace_only_plan,
        "hall_lot",
        31,
        5,
        9,
        6,
        "Civic",
    )
    workplace_hall_id = settlement_builder.place_building(
        workplace_only_plan,
        "hall_lot",
        "town_hall",
        building_id="unhoused_hall",
    )
    workplace_only_plan["buildings"][workplace_hall_id]["phase_index"] = 3
    workplace_only_plan["buildings"][workplace_hall_id]["status"] = "complete"
    unhoused_population = procedural_builder.create_population(workplace_only_plan)
    assert unhoused_population["status"] == "awaiting_housing"
    assert unhoused_population["residents"] == {}
    assert len(unhoused_population["job_vacancies"]) == 2
    assert procedural_builder.validate(
        unhoused_population,
        workplace_only_plan,
    )["errors"] == []

    population_game = FarmGame()
    population_game.autosave_with_message = lambda message: population_game.set_message(message)
    authored_npcs_before_population = [
        dict(record)
        for record in population_game.state.town_npcs
    ]
    game_population_plan = population_game.create_wilderness_settlement_plan(
        11,
        -7,
        name="Generational Crossing",
    )
    for population_building in game_population_plan["buildings"].values():
        population_building["phase_index"] = 3
        population_building["status"] = "complete"
    game_population = population_game.generate_procedural_settlement_population(11, -7)
    assert game_population
    assert population_game.state.town_npcs == authored_npcs_before_population
    authored_npc_ids = {
        str(record.get("id", ""))
        for record in population_game.state.town_npcs
    }
    assert set(game_population["residents"]).isdisjoint(authored_npc_ids)
    assert population_game.procedural_settlement_population_validation(
        11,
        -7,
    ) == {"errors": [], "warnings": []}
    assert population_game.procedural_settlement_population_report_lines(11, -7)
    persistent_resident_id = next(iter(game_population["residents"]))
    persistent_resident = game_population["residents"][persistent_resident_id]
    dialogue_preview = population_game.procedural_settlement_conversation(
        11,
        -7,
        persistent_resident_id,
        remember=False,
    )
    assert dialogue_preview["category"] == "first_meeting"
    assert dialogue_preview == population_game.procedural_settlement_conversation(
        11,
        -7,
        persistent_resident_id,
        remember=False,
    )
    assert persistent_resident["met"] is False
    first_conversation = population_game.procedural_settlement_conversation(
        11,
        -7,
        persistent_resident_id,
    )
    assert first_conversation["relationship_gain"] == 2
    assert persistent_resident["met"] is True
    assert persistent_resident["dialogue_count"] == 1
    assert persistent_resident["recent_dialogue_ids"]
    assert persistent_resident["memories"]
    repeat_conversation = population_game.procedural_settlement_conversation(
        11,
        -7,
        persistent_resident_id,
    )
    assert repeat_conversation["relationship_gain"] == 0
    assert repeat_conversation["id"] != first_conversation["id"]
    assert "rumor" not in population_game.procedural_settlement_dialogue_topics(
        11,
        -7,
        persistent_resident_id,
    )
    persistent_resident["relationship"] = 160
    unlocked_topics = population_game.procedural_settlement_dialogue_topics(
        11,
        -7,
        persistent_resident_id,
    )
    assert {"rumor", "personal", "memory", "secret", "request"}.issubset(unlocked_topics)
    for dialogue_topic in [
        "work",
        "home",
        "settlement",
        "weather",
        "season",
        "rumor",
        "personal",
        "memory",
        "secret",
    ]:
        topic_result = population_game.procedural_settlement_conversation(
            11,
            -7,
            persistent_resident_id,
            topic=dialogue_topic,
            remember=False,
        )
        assert topic_result["text"]
        assert topic_result["topic"] == dialogue_topic
    assert npc_dialogue.procedural_relationship_tier(160) == "Trusted"
    assert npc_dialogue.procedural_time_phase(12) == "lunch"
    request_conversation = population_game.procedural_settlement_conversation(
        11,
        -7,
        persistent_resident_id,
        topic="request",
    )
    procedural_request = request_conversation["request"]
    assert procedural_request["status"] == "active"
    assert population_game.procedural_settlement_request_status(
        11,
        -7,
        persistent_resident_id,
    ).startswith("Need ")
    population_game.state.inventory[procedural_request["item"]] = procedural_request["quantity"]
    money_before_request = population_game.state.money
    assert population_game.procedural_settlement_request_status(
        11,
        -7,
        persistent_resident_id,
    ) == "Ready"
    assert population_game.complete_procedural_settlement_request(
        11,
        -7,
        persistent_resident_id,
    )
    assert population_game.state.money == money_before_request + procedural_request["reward_money"]
    assert procedural_request["id"] in persistent_resident["completed_request_ids"]
    assert persistent_resident["active_request"]["status"] == "completed"
    assert population_game.procedural_settlement_conversation_lines(
        11,
        -7,
        persistent_resident_id,
        topic="request",
        remember=False,
    )
    persistent_resident["relationship"] = 42
    persistent_resident["met"] = True
    persistent_resident["memories"] = ["First hello"]
    reconciled_population = population_game.reconcile_procedural_settlement_population(11, -7)
    assert reconciled_population["generation"] == 2
    assert reconciled_population["residents"][persistent_resident_id]["relationship"] == 42
    assert reconciled_population["residents"][persistent_resident_id]["met"] is True
    assert reconciled_population["residents"][persistent_resident_id]["memories"] == ["First hello"]
    assert reconciled_population["residents"][persistent_resident_id]["dialogue_count"] == 3
    assert reconciled_population["residents"][persistent_resident_id]["active_request"]["status"] == "completed"
    assert procedural_request["id"] in reconciled_population["residents"][persistent_resident_id]["completed_request_ids"]

    procedural_town_game = FarmGame()
    procedural_town_game.autosave_with_message = (
        lambda message: procedural_town_game.set_message(message)
    )
    procedural_special_events = []
    procedural_town_game.play_world_event_scene = (
        lambda event_id, title, steps, completion_message="":
        procedural_special_events.append((str(event_id), str(title), list(steps), str(completion_message))) or True
    )
    procedural_town_game.state.wilderness_seed = 24681357
    procedural_town_game._procedural_town_site_cache = {}
    authored_town_before_runtime = [
        row[:]
        for row in procedural_town_game.town_map
    ]
    procedural_town_sites = []
    claim_site_count = 0
    dungeon_site_count = 0
    stronghold_site_count = 0
    for procedural_chunk_y in range(-50, 51):
        for procedural_chunk_x in range(-50, 51):
            if procedural_town_game.wilderness_chunk_has_procedural_settlement(
                procedural_chunk_x,
                procedural_chunk_y,
            ):
                procedural_town_sites.append(
                    (procedural_chunk_x, procedural_chunk_y)
                )
            if procedural_town_game.is_claimable_wilderness_chunk(
                procedural_chunk_x,
                procedural_chunk_y,
            ):
                claim_site_count += 1
            if procedural_town_game.wilderness_chunk_has_dungeon_site(
                procedural_chunk_x,
                procedural_chunk_y,
            ):
                dungeon_site_count += 1
            if procedural_town_game.wilderness_chunk_has_stronghold(
                procedural_chunk_x,
                procedural_chunk_y,
            ):
                stronghold_site_count += 1
    assert procedural_town_sites
    assert len(procedural_town_sites) * 2 < claim_site_count
    assert len(procedural_town_sites) * 2 < dungeon_site_count
    assert len(procedural_town_sites) * 2 < stronghold_site_count
    assert all(
        abs(chunk_x) + abs(chunk_y) >= procedural_towns.PROCEDURAL_TOWN_MIN_DISTANCE
        for chunk_x, chunk_y in procedural_town_sites
    )
    assert all(
        not procedural_town_game.is_claimable_wilderness_chunk(chunk_x, chunk_y)
        and not procedural_town_game.wilderness_chunk_has_dungeon_site(chunk_x, chunk_y)
        and not procedural_town_game.wilderness_chunk_has_stronghold(chunk_x, chunk_y)
        for chunk_x, chunk_y in procedural_town_sites
    )
    procedural_town_repeat = FarmGame()
    procedural_town_repeat.state.wilderness_seed = 24681357
    procedural_town_repeat._procedural_town_site_cache = {}
    assert procedural_town_sites == [
        (chunk_x, chunk_y)
        for chunk_y in range(-50, 51)
        for chunk_x in range(-50, 51)
        if procedural_town_repeat.wilderness_chunk_has_procedural_settlement(
            chunk_x,
            chunk_y,
        )
    ]
    procedural_town_chunk = min(
        procedural_town_sites,
        key=lambda position: abs(position[0]) + abs(position[1]),
    )
    assert procedural_town_game.procedural_town_region_selected(*procedural_town_chunk)
    assert procedural_town_chunk in procedural_town_game.wilderness_region_chunks(*procedural_town_chunk)
    procedural_town_x, procedural_town_y = procedural_town_chunk
    mapped_town_name = procedural_town_game.procedural_town_name(
        procedural_town_x,
        procedural_town_y,
    )
    assert procedural_town_game.procedural_town_plan(
        procedural_town_x,
        procedural_town_y,
    ) is None
    assert procedural_town_game.overworld_chunk_preview_symbol(
        procedural_town_x,
        procedural_town_y,
    ) == "_"
    assert any(
        "unknown" in line.lower()
        for line in procedural_town_game.overworld_chunk_detail_lines(
            procedural_town_x,
            procedural_town_y,
        )
    )
    assert any(item == "Regional Chart" for item, _price in procedural_towns.PROCEDURAL_LOCAL_STOCK["general_store"])

    knowledge_game = FarmGame()
    knowledge_game.autosave_with_message = lambda message: knowledge_game.set_message(message)
    knowledge_game.state.location = "Wilderness"
    knowledge_game.set_wilderness_chunk(0, 0)
    origin_region_members = knowledge_game.wilderness_region_chunks(0, 0)
    chart_target = next(point for point in origin_region_members if point != (0, 0))
    assert not knowledge_game.wilderness_chunk_known(*chart_target)
    knowledge_game.enter_wilderness_overworld()
    knowledge_game.state.overworld_cursor_chunk_x = 3
    knowledge_game.state.overworld_cursor_chunk_y = 0
    knowledge_game.overworld_enter_selected_chunk()
    assert knowledge_game.on_wilderness_overworld()
    assert "unknown" in knowledge_game.state.message.lower()
    knowledge_game.cancel_wilderness_overworld()
    knowledge_game.state.inventory["Regional Chart"] = 1
    assert knowledge_game.use_consumable_item("Regional Chart")
    assert all(knowledge_game.wilderness_chunk_known(*point) for point in origin_region_members)
    assert knowledge_game.overworld_chunk_preview_symbol(*chart_target) != "_"
    assert knowledge_game.state.inventory["Regional Chart"] == 0
    assert not knowledge_game.use_consumable_item("Regional Chart")
    knowledge_game.enter_wilderness_overworld()
    cartography_lines = knowledge_game.overworld_lines()
    cartography_plain = [ANSI_CSI_RE.sub("", line) for line in cartography_lines]
    assert len(cartography_lines) == data.VIEW_HEIGHT
    assert max(ui.visible_text_len(line) for line in cartography_lines) <= data.VIEW_WIDTH
    assert any("\u250c" in line and "\u2510" in line for line in cartography_plain)
    assert any("[@]" in line for line in cartography_plain)
    assert any("\u00b7" in line for line in cartography_plain[3:14])
    assert any("\u2591" in line for line in cartography_plain[3:14])
    assert any("Close B/X/Esc/Q/Tab" in line for line in cartography_plain)
    assert any("UNKNOWN" in line and "GOAL" in line for line in cartography_plain)
    nearby_chart_target = min(
        (point for point in origin_region_members if point != (0, 0)),
        key=lambda point: abs(point[0]) + abs(point[1]),
    )
    knowledge_game.state.overworld_cursor_chunk_x, knowledge_game.state.overworld_cursor_chunk_y = nearby_chart_target
    moved_cartography_rows = [ANSI_CSI_RE.sub("", line) for line in knowledge_game.overworld_lines()]
    moved_cartography_plain = "\n".join(moved_cartography_rows)
    assert "\n".join(moved_cartography_rows[3:14]).count("@") == 1
    assert "[" in moved_cartography_plain and "]" in moved_cartography_plain
    knowledge_game.state.detailed_glyphs_enabled = False
    simple_cartography_plain = "\n".join(ANSI_CSI_RE.sub("", line) for line in knowledge_game.overworld_lines())
    assert "+" in simple_cartography_plain and "_" in simple_cartography_plain
    assert "\u2591" not in simple_cartography_plain and "\u250c" not in simple_cartography_plain
    knowledge_game.state.detailed_glyphs_enabled = True
    knowledge_game.cancel_wilderness_overworld()
    nearby_region_profiles = {
        knowledge_game.wilderness_region_profile(x, y)["key"]: knowledge_game.wilderness_region_profile(x, y)
        for y in range(-12, 13)
        for x in range(-12, 13)
    }
    organic_sizes = {int(profile["size"]) for profile in nearby_region_profiles.values()}
    assert len(organic_sizes) >= 2
    assert any(size != 9 for size in organic_sizes)
    for profile in list(nearby_region_profiles.values())[:8]:
        members = knowledge_game.wilderness_region_chunks(int(profile["center_x"]), int(profile["center_y"]))
        assert len(members) == int(profile["size"])
        assert all(knowledge_game.wilderness_region_profile(*point)["key"] == profile["key"] for point in members)

    known_road_chunks = [point for point in origin_region_members if knowledge_game.wilderness_chunk_has_regional_road(*point)]
    assert len(known_road_chunks) >= 2
    road_source, road_target = known_road_chunks[0], known_road_chunks[-1]
    knowledge_game.state.overworld_return_chunk_x, knowledge_game.state.overworld_return_chunk_y = road_source
    knowledge_game.state.overworld_cursor_chunk_x, knowledge_game.state.overworld_cursor_chunk_y = road_target
    road_distance = abs(road_target[0] - road_source[0]) + abs(road_target[1] - road_source[1])
    assert knowledge_game.overworld_regional_road_discount(*road_target)
    road_stamina, road_minutes, _road_waypoint = knowledge_game.overworld_travel_costs(*road_target)
    assert road_stamina <= (road_distance * 2 * 3 + 3) // 4
    assert road_minutes <= (road_distance * 10 * 3 + 3) // 4
    assert "road discount" in " ".join(knowledge_game.overworld_chunk_detail_lines(*road_target)).lower()

    river_profiles = [knowledge_game.wilderness_world_river_profile(sector) for sector in range(-8, 9)]
    assert all(int(profile["source_y"]) != int(profile["mouth_y"]) for profile in river_profiles)
    sea_river = next(profile for profile in river_profiles if profile["reaches_sea"])
    sea_source_x = knowledge_game.wilderness_world_river_center(int(sea_river["source_y"]), int(sea_river["sector"]))
    sea_mouth_x = knowledge_game.wilderness_world_river_center(int(sea_river["mouth_y"]), int(sea_river["sector"]))
    assert knowledge_game.wilderness_world_water_tile(sea_source_x, int(sea_river["source_y"]))
    assert knowledge_game.wilderness_world_water_tile(sea_mouth_x, int(sea_river["mouth_y"]))
    assert knowledge_game.wilderness_world_biome_tile(sea_mouth_x, int(sea_river["mouth_y"])) == "["
    mouth_chunk = (sea_mouth_x // 86, int(sea_river["mouth_y"]) // 38)
    assert "Coastal river delta" in knowledge_game.wilderness_chunk_hydrology_features(*mouth_chunk)
    knowledge_game.discover_wilderness_chunk(*mouth_chunk)
    assert knowledge_game.overworld_chunk_preview_symbol(*mouth_chunk) in {"d", "!", "X", "D", "?", "t"}
    river_length = (int(sea_river["mouth_y"]) - int(sea_river["source_y"])) * int(sea_river["direction"])
    delta_progress = int(river_length * 0.94)
    delta_y = int(sea_river["source_y"]) + int(sea_river["direction"]) * delta_progress
    delta_center = knowledge_game.wilderness_world_river_center(delta_y, int(sea_river["sector"]))
    assert sum(knowledge_game.wilderness_world_water_tile(delta_center + offset, delta_y) for offset in range(-20, 21)) >= 7
    for boundary_y in (37, 38):
        assert knowledge_game.wilderness_world_water_tile(
            knowledge_game.wilderness_world_river_center(boundary_y, 0), boundary_y
        )

    seamless_game = FarmGame()
    seamless_game.autosave_with_message = lambda message: seamless_game.set_message(message)
    seamless_game.state.wilderness_seed = 24681357
    seamless_game.state.location = "Wilderness"
    seamless_game.set_wilderness_chunk(6, 7)
    seamless_grid = seamless_game.active_map()
    assert "#" not in seamless_grid[0] and "#" not in seamless_grid[-1]
    assert all(row[0] != "#" and row[-1] != "#" for row in seamless_grid)
    crossing_y = 9
    seamless_east_key = seamless_game.wilderness_chunk_key(7, 7)
    seamless_game.get_wilderness_chunk_map(7, 7)[crossing_y][0] = ";"
    seamless_game.repaired_wilderness_chunks.add(seamless_east_key)
    seamless_game.state.player_x = len(seamless_grid[0]) - 2
    seamless_game.state.player_y = crossing_y
    assert seamless_game.transition_wilderness_chunk(1, 0)
    assert (seamless_game.state.wilderness_chunk_x, seamless_game.state.wilderness_chunk_y) == (7, 7)
    assert (seamless_game.state.player_x, seamless_game.state.player_y) == (0, crossing_y)

    stream_game = FarmGame()
    stream_game.autosave_with_message = lambda message: stream_game.set_message(message)
    stream_game.state.location = "Wilderness"
    stream_game.set_wilderness_chunk(6, 7)
    visited_before_stream = stream_game.wilderness_visited_map_count()
    counter_before_stream = int(stream_game.state.wilderness_chunks_visited)
    assert stream_game.prepare_wilderness_stream_window(limit=8) == 8
    assert len(stream_game._wilderness_stream_preloaded_chunks) == 8
    assert stream_game.wilderness_visited_map_count() == visited_before_stream
    assert int(stream_game.state.wilderness_chunks_visited) == counter_before_stream
    west_key = stream_game.wilderness_chunk_key(5, 7)
    east_key = stream_game.wilderness_chunk_key(7, 7)
    assert not stream_game.wilderness_chunk_known(5, 7)
    stream_game.state.player_x = 2
    stream_game.state.player_y = 9
    stream_game.wilderness_maps[west_key][9][85] = "["
    stream_game.ensure_wilderness_animals()
    stream_game.wilderness_animals[west_key] = []
    stream_game.ensure_wilderness_travelers()
    stream_game._wilderness_travelers[stream_game.wilderness_traveler_cache_key(5, 7)] = []
    stream_game.ensure_wilderness_strongholds()
    stream_game.wilderness_stronghold_enemies[stream_game.wilderness_stronghold_key(5, 7)] = []
    streamed_lines = [ANSI_CSI_RE.sub("", line) for line in stream_game.map_lines()]
    assert len(streamed_lines) == farmstead_main.VIEW_HEIGHT
    assert all(len(line) == farmstead_main.VIEW_WIDTH for line in streamed_lines)
    rendered_player_symbol = ANSI_CSI_RE.sub("", stream_game.render_player())
    assert streamed_lines[farmstead_main.VIEW_HEIGHT // 2][farmstead_main.VIEW_WIDTH // 2] == rendered_player_symbol
    assert streamed_lines[farmstead_main.VIEW_HEIGHT // 2][farmstead_main.VIEW_WIDTH // 2 - 3] == "["
    preloaded_east_map = stream_game.wilderness_maps[east_key]
    preloaded_east_map[9][0] = ";"
    stream_game.repaired_wilderness_chunks.add(east_key)
    stream_game.state.player_x = 84
    stream_game.state.player_y = 9
    stream_game.transition_wilderness_chunk(1, 0)
    assert stream_game.wilderness_map is preloaded_east_map
    assert east_key not in stream_game._wilderness_stream_preloaded_chunks
    assert stream_game.wilderness_chunk_known(7, 7)
    assert stream_game.wilderness_visited_map_count() == visited_before_stream + 1
    with TemporaryDirectory() as stream_save_directory:
        stream_save_path = Path(stream_save_directory) / "stream-save.json"
        stream_game.save(quiet=True, path=stream_save_path)
        stream_save_data = json.loads(stream_save_path.read_text(encoding="utf-8"))
        assert all(key not in stream_save_data["wilderness_maps"] for key in stream_game._wilderness_stream_preloaded_chunks)
        assert all(key not in stream_save_data["wilderness_animals"] for key in stream_game._wilderness_stream_preloaded_chunks)

    seam_home_random_state = random.getstate()
    legacy_lane_grid = [[";" for _ in range(86)] for _ in range(38)]
    legacy_lane_before = [row[:] for row in legacy_lane_grid]
    stream_game.clear_wilderness_chunk_entry_lanes(legacy_lane_grid)
    assert legacy_lane_grid == legacy_lane_before

    seam_game = FarmGame()
    seam_game.autosave_with_message = lambda message: seam_game.set_message(message)
    seam_game.state.location = "Wilderness"
    seam_game.set_wilderness_chunk(6, 7)
    seam_game.prepare_wilderness_stream_window(limit=8)
    seam_west_key = seam_game.wilderness_chunk_key(6, 7)
    seam_east_key = seam_game.wilderness_chunk_key(7, 7)
    seam_game.wilderness_maps[seam_west_key][9][85] = ";"
    seam_game.wilderness_maps[seam_east_key][9][0] = ";"
    seam_game.repaired_wilderness_chunks.update({seam_west_key, seam_east_key})
    seam_game.state.player_x, seam_game.state.player_y = 85, 9
    seam_game.move(1, 0)
    assert (seam_game.state.wilderness_chunk_x, seam_game.state.wilderness_chunk_y) == (7, 7)
    assert (seam_game.state.player_x, seam_game.state.player_y) == (0, 9)
    seam_game.move(-1, 0)
    assert (seam_game.state.wilderness_chunk_x, seam_game.state.wilderness_chunk_y) == (6, 7)
    assert (seam_game.state.player_x, seam_game.state.player_y) == (85, 9)

    home_world_game = FarmGame()
    home_world_game.autosave_with_message = lambda message: home_world_game.set_message(message)
    assert home_world_game.on_wilderness()
    assert home_world_game.state.seamless_home_world_version == 2
    assert not home_world_game.origin_world_gateway_positions()
    assert not home_world_game.origin_world_sign_positions()
    assert len(home_world_game.home_world_authored_chunks()) >= 8

    def home_world_tile(game, world_x, world_y):
        chunk_x, chunk_y, local_x, local_y = game.home_world_chunk_from_world(world_x, world_y)
        return game.get_wilderness_chunk_map(chunk_x, chunk_y)[local_y][local_x]

    # The complete authored maps are stamped at their original scale but are
    # physically separated by a 32-tile ravine passage in world space.
    town_edge_world = home_world_game.home_world_world_for_town_position(111, 20)
    farm_edge_world = home_world_game.home_world_world_for_farm_position(0, 10)
    assert town_edge_world == (-33, 10)
    assert farm_edge_world == (0, 10)
    assert home_world_tile(home_world_game, *town_edge_world) == ":"
    assert home_world_tile(home_world_game, *farm_edge_world) == ":"
    assert list(range(town_edge_world[0] + 1, farm_edge_world[0])) == list(range(-32, 0))
    assert all(home_world_tile(home_world_game, x, 10) == ":" for x in range(-32, 0))
    assert all(home_world_tile(home_world_game, x, 7) == "," for x in range(-32, 0))
    assert all(home_world_tile(home_world_game, x, 6) == "#" for x in range(-32, 0))
    # The passage never overwrites either source map.
    untouched_town_world = home_world_game.home_world_world_for_town_position(100, 16)
    assert home_world_tile(home_world_game, *untouched_town_world) == home_world_game.town_map[16][100]
    assert home_world_tile(home_world_game, 5, 6) == home_world_game.base_map[6][5] == "."
    assert home_world_tile(
        home_world_game, *home_world_game.home_world_world_for_town_position(*data.TOWN_DOORS["general_store"])
    ) == "D"
    mine_arrival = home_world_game.home_world_destination_world_positions()["mine"]
    assert home_world_tile(home_world_game, mine_arrival[0], mine_arrival[1] - 1) == "V"
    # The old source-map rectangles no longer draw an impassable wall around
    # either district. Actual roads and player-built fences remain intact.
    for source_kind, source_map, world_for_source in (
        ("town", home_world_game.town_map, home_world_game.home_world_world_for_town_position),
        ("farm", home_world_game.base_map, home_world_game.home_world_world_for_farm_position),
    ):
        source_height = len(source_map)
        perimeter_wall = next(
            (x, y)
            for y, row in enumerate(source_map)
            for x, tile in enumerate(row)
            if tile == "#"
            and (x in {0, len(row) - 1} or y in {0, source_height - 1})
        )
        perimeter_world = world_for_source(*perimeter_wall)
        assert home_world_tile(home_world_game, *perimeter_world) != "#"
        home_world_game.set_player_home_world_position(*perimeter_world)
        assert home_world_game.home_world_open_perimeter_at(
            source_kind, *perimeter_wall
        )

    # Farm debris remains canonical in the embedded world. Clearing with the
    # normal F-tool route must update both the visible chunk and base_map so a
    # seamless layer refresh cannot resurrect weeds, stones, or fallen wood.
    for debris_symbol, tool_name in (("^", "Hoe"), ("o", "Pickaxe"), ("*", "Axe")):
        debris_game = FarmGame()
        debris_game.autosave_with_message = lambda message: debris_game.set_message(message)
        source_x, source_y = next(
            (x, y)
            for y, row in enumerate(debris_game.base_map)
            for x, tile in enumerate(row)
            if tile == debris_symbol
        )
        neighbor = next(
            (source_x + dx, source_y + dy, -dx, -dy)
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
            if (
                0 <= source_y + dy < len(debris_game.base_map)
                and 0 <= source_x + dx < len(debris_game.base_map[source_y + dy])
                and debris_game.base_map[source_y + dy][source_x + dx] == "."
            )
        )
        player_x, player_y, face_dx, face_dy = neighbor
        facing = {
            (0, -1): "UP", (0, 1): "DOWN",
            (-1, 0): "LEFT", (1, 0): "RIGHT",
        }[(face_dx, face_dy)]
        debris_game.return_to_seamless_farm(player_x, player_y, facing=facing)
        debris_game.state.tool_target_mode = "FRONT"
        if tool_name not in debris_game.state.owned_tools:
            debris_game.state.owned_tools.append(tool_name)
        debris_game.state.tool_levels[tool_name] = max(
            1, int(debris_game.state.tool_levels.get(tool_name, 0)),
        )
        debris_game.state.selected_tool_index = debris_game.state.available_tools.index(tool_name)
        assert debris_game.active_map()[source_y][source_x] == debris_symbol
        debris_game.use_tool()
        assert debris_game.active_map()[source_y][source_x] == "."
        assert debris_game.base_map[source_y][source_x] == "."
        debris_game.refresh_seamless_farm_layer()
        assert debris_game.active_map()[source_y][source_x] == "."

    # Ordinary farming actions must treat base_map as authoritative while also
    # updating the seamless chunk the player can see.
    farm_action_game = FarmGame()
    farm_action_game.autosave_with_message = lambda message: farm_action_game.set_message(message)
    farm_action_game.return_to_seamless_farm(4, 6, facing="RIGHT")
    farm_action_game.set_farm_work_tile(5, 6, ".")
    farm_action_game.state.stamina = 100
    farm_action_game.use_hoe(5, 6)
    assert farm_action_game.active_map()[6][5] == ","
    assert farm_action_game.base_map[6][5] == ","
    farm_action_game.refresh_seamless_farm_layer()
    assert farm_action_game.active_map()[6][5] == ","

    farm_action_game.state.inventory["Turnip Seeds"] = 1
    farm_action_game.state.selected_seed = "Turnip"
    farm_action_game.use_seeds(5, 6)
    planted_crop = farm_action_game.get_crop(5, 6)
    assert planted_crop is not None and planted_crop.name == "Turnip"
    farm_action_game.use_watering_can(5, 6)
    assert planted_crop.watered
    assert farm_action_game.active_map()[6][5] == "w"
    assert farm_action_game.base_map[6][5] == "w"
    planted_crop.ready = True
    farm_action_game.use_harvest(5, 6)
    assert farm_action_game.get_crop(5, 6) is None
    assert farm_action_game.active_map()[6][5] == ","
    assert farm_action_game.base_map[6][5] == ","
    farm_action_game.refresh_seamless_farm_layer()
    assert farm_action_game.active_map()[6][5] == ","

    # Failed stamina checks are transactions: they cannot modify terrain.
    tired_hoe_game = FarmGame()
    tired_hoe_game.return_to_seamless_farm(4, 6, facing="RIGHT")
    tired_hoe_game.set_farm_work_tile(5, 6, ".")
    tired_hoe_game.state.stamina = 0
    tired_hoe_game.use_hoe(5, 6)
    assert tired_hoe_game.active_map()[6][5] == "."
    assert tired_hoe_game.base_map[6][5] == "."

    tired_water_game = FarmGame()
    tired_water_game.return_to_seamless_farm(4, 6, facing="RIGHT")
    tired_water_game.set_farm_work_tile(5, 6, ",")
    tired_water_game.state.stamina = 0
    tired_water_game.use_watering_can(5, 6)
    assert tired_water_game.active_map()[6][5] == ","
    assert tired_water_game.base_map[6][5] == ","

    # Sleeping must restamp overnight source-map changes before save() performs
    # its visible-to-source safety sync.
    overnight_farm_game = FarmGame()
    overnight_farm_game.return_to_seamless_farm(4, 6, facing="RIGHT")
    overnight_farm_game.set_farm_work_tile(5, 6, "w")
    for candidate_day in range(1, 27):
        next_month, next_day, next_year = helpers.advance_date(1, candidate_day, 1)
        next_weather = helpers.forecast_weather_for_date(next_month, next_day, next_year)
        if not helpers.weather_waters_crops(next_weather):
            overnight_farm_game.state.month = 1
            overnight_farm_game.state.day = candidate_day
            overnight_farm_game.state.year = 1
            break
    else:
        raise AssertionError("Expected at least one dry forecast date for overnight farm regression.")
    overnight_farm_game.save = (
        lambda quiet=True, path=None: overnight_farm_game.sync_seamless_farm_to_base_map()
    )
    overnight_farm_game.sleep(force=True)
    assert not helpers.weather_waters_crops(overnight_farm_game.state.weather)
    assert overnight_farm_game.base_map[6][5] == ","
    assert overnight_farm_game.active_map()[6][5] == ","

    home_world_game.return_to_seamless_farm(0, 10, facing="LEFT")
    home_world_game.move(-1, 0)
    assert home_world_game.on_wilderness()
    assert home_world_game.home_world_source_at(
        home_world_game.state.player_x, home_world_game.state.player_y,
    ) == ("", -1, -1)
    assert home_world_game.home_world_current_world_position() == (-1, 10)
    for _ in range(32):
        home_world_game.move(-1, 0)
    assert home_world_game.home_world_source_at(
        home_world_game.state.player_x, home_world_game.state.player_y,
    ) == ("town", 111, 20)
    home_world_game.move(1, 0)
    assert home_world_game.home_world_source_at(
        home_world_game.state.player_x, home_world_game.state.player_y,
    ) == ("", -1, -1)
    for _ in range(32):
        home_world_game.move(1, 0)
    assert home_world_game.home_world_source_at(
        home_world_game.state.player_x, home_world_game.state.player_y,
    ) == ("farm", 0, 10)

    # Farm expansions extend the physical world layer. The Grand Farm crosses
    # a backend chunk boundary, while object keys remain canonical farm-source
    # coordinates and the normal held-item footprint preview stays visible.
    expanded_farm_game = FarmGame()
    expanded_farm_game.autosave_with_message = lambda message: expanded_farm_game.set_message(message)
    expanded_farm_game.state.money = 99_999
    for expansion_name in (
        "East Field Expansion", "South Field Expansion", "Grand Farm Expansion",
    ):
        assert expanded_farm_game.purchase_farm_expansion(expansion_name)
    assert (expanded_farm_game.farm_width(), expanded_farm_game.farm_height()) == (90, 34)
    expanded_farm_game.return_to_seamless_farm(87, 5, facing="RIGHT")
    assert expanded_farm_game.home_world_farm_source_position(
        expanded_farm_game.state.player_x, expanded_farm_game.state.player_y,
    ) == (87, 5)
    assert expanded_farm_game.active_map()[5][2] == expanded_farm_game.base_map[5][88] == "."
    expanded_farm_game.state.inventory["Fence"] = 1
    expanded_farm_game.state.held_object = "Fence"
    preview_lines = [
        ANSI_CSI_RE.sub("", line)
        for line in expanded_farm_game.wilderness_stream_map_lines()
    ]
    assert any("X" in line for line in preview_lines)
    assert expanded_farm_game.place_held_object()
    assert expanded_farm_game.state.placed_objects["Farm:88,5"] == "Fence"

    # Upgraded tools and farm automation must cross the hidden backend seam at
    # source x=86 without clipping or switching to chunk-local coordinates.
    expanded_farm_game.remove_placed_object(2, 5)
    expanded_farm_game.return_to_seamless_farm(85, 6, facing="RIGHT")
    expanded_farm_game.state.tool_levels["Hoe"] = 3
    expanded_farm_game.state.stamina = 100
    for local_y in (5, 6, 7):
        expanded_farm_game.set_farm_work_tile(86, local_y, ".")
    expanded_farm_game.use_hoe(86, 6)
    assert all(expanded_farm_game.base_map[y][86] == "," for y in (5, 6, 7))
    east_farm_chunk = expanded_farm_game.get_wilderness_chunk_map(1, 0)
    assert all(east_farm_chunk[y][0] == "," for y in (5, 6, 7))
    expanded_farm_game.state.selected_seed = "Turnip"
    expanded_farm_game.state.inventory["Turnip Seeds"] = 9
    expanded_farm_game.area_sow_selected_seed()
    assert all(expanded_farm_game.get_crop(86, y) is not None for y in (5, 6, 7))

    expanded_farm_game.set_farm_work_tile(86, 8, "o")
    expanded_farm_game.state.tool_levels["Pickaxe"] = 3
    expanded_farm_game.state.stamina = 100
    expanded_farm_game.use_weeds(86, 8)
    assert expanded_farm_game.base_map[8][86] == "."
    assert east_farm_chunk[8][0] == "."

    expanded_farm_game.state.placed_objects["Farm:87,10"] = "Sprinkler"
    expanded_farm_game.base_map[10][88] = ","
    assert expanded_farm_game.apply_sprinklers() >= 1
    assert expanded_farm_game.base_map[10][88] == "w"
    expanded_farm_game.refresh_seamless_farm_layer()
    assert east_farm_chunk[10][2] == "w"

    # Livestock and the player use the same source coordinate space in expanded
    # farm chunks, so an animal cannot path onto the player's apparent local tile.
    expanded_farm_game.return_to_seamless_farm(88, 5)
    expanded_farm_game.base_map[5][88] = "."
    expanded_farm_game.refresh_seamless_farm_layer()
    boundary_animal = {"outside": True, "x": 87, "y": 5}
    assert expanded_farm_game.farm_animal_player_source_position() == (88, 5)
    assert not expanded_farm_game.farm_animal_tile_available(boundary_animal, 88, 5)

    # Authored residents use one source-coordinate render/interaction route in
    # the seamless town. A visible NPC must be the same record interaction sees.
    resident_game = FarmGame()
    resident_game.return_to_seamless_town(50, 20)
    resident = next(
        npc for npc in resident_game.active_town_npcs()
        if not resident_game.travel_follower_identity_for_npc_id(str(npc.get("id", "")))
    )
    occupied = set(resident_game.authored_town_exterior_npc_positions())
    placement = None
    facing_by_offset = {
        (0, 1): "UP", (0, -1): "DOWN", (1, 0): "LEFT", (-1, 0): "RIGHT",
    }
    for npc_y, row in enumerate(resident_game.town_map):
        for npc_x, tile in enumerate(row):
            if tile not in {".", "=", ":", ","} or (npc_x, npc_y) in occupied:
                continue
            for (dx, dy), facing in facing_by_offset.items():
                player_x, player_y = npc_x + dx, npc_y + dy
                if (
                    0 <= player_y < len(resident_game.town_map)
                    and 0 <= player_x < len(resident_game.town_map[player_y])
                    and resident_game.town_map[player_y][player_x] in {".", "=", ":", ","}
                ):
                    placement = (npc_x, npc_y, player_x, player_y, facing)
                    break
            if placement:
                break
        if placement:
            break
    assert placement is not None
    npc_x, npc_y, player_x, player_y, facing = placement
    resident.update({
        "runtime_location": "Town", "indoors": False, "indoor_location": "",
        "x": npc_x, "y": npc_y,
    })
    resident_game.return_to_seamless_town(player_x, player_y, facing=facing)
    assert resident_game.town_npc_at(*resident_game.front_tile_pos()) is resident
    opened_residents = []
    resident_game.town_npc_menu = lambda npc: opened_residents.append(str(npc.get("id", "")))
    resident_game.general_interact()
    assert opened_residents == [str(resident.get("id", ""))]

    # Lowercase h is also an authored town-building surface. Bumping those
    # borders must not treat the glyph as a wilderness-structure doorway and
    # invent an Old Watchtower interior for the home chunk.
    structure_collision_game = FarmGame()
    structure_collision_game.state.location = "Wilderness"
    structure_collision_game.set_wilderness_chunk(-2, 0)
    collision_grid = structure_collision_game.active_map()
    false_structure_bump = None
    for border_y, row in enumerate(collision_grid):
        for border_x, tile in enumerate(row):
            if tile != wilderness_system.WILDERNESS_STRUCTURE_SYMBOL:
                continue
            for bump_dx, bump_dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                player_x, player_y = border_x - bump_dx, border_y - bump_dy
                if (
                    0 <= player_y < len(collision_grid)
                    and 0 <= player_x < len(collision_grid[player_y])
                    and collision_grid[player_y][player_x] in {".", "=", ":", ","}
                ):
                    false_structure_bump = (
                        player_x, player_y, bump_dx, bump_dy, border_x, border_y,
                    )
                    break
            if false_structure_bump:
                break
        if false_structure_bump:
            break
    assert false_structure_bump is not None
    player_x, player_y, bump_dx, bump_dy, border_x, border_y = false_structure_bump
    assert not structure_collision_game.current_wilderness_structure_door_at(border_x, border_y)
    assert "Old Watchtower" not in structure_collision_game.describe_tile(border_x, border_y)
    assert "open building door" not in structure_collision_game.target_action_hint(border_x, border_y).lower()
    assert not structure_collision_game.enter_wilderness_structure(border_x, border_y)
    assert structure_collision_game.on_wilderness()
    structure_collision_game.state.player_x, structure_collision_game.state.player_y = player_x, player_y
    structure_collision_game.move(bump_dx, bump_dy)
    assert structure_collision_game.on_wilderness()
    assert (structure_collision_game.state.player_x, structure_collision_game.state.player_y) == (
        player_x, player_y,
    )

    # Capital A is both the Animal Store façade and the outpost-door glyph.
    # No authored building surface may dispatch a wilderness transition merely
    # because its character resembles a site marker.
    facade_game = FarmGame()
    authored_door_positions = set(data.TOWN_DOORS.values()) | set(
        data.AUTHORED_TOWN_RESIDENCE_ID_BY_DOOR
    )
    facade_symbols = {"G", "C", "X", "L", "M", "I", "Y", "A", "H", "R", "P", "U", "Q", "h"}
    checked_facades = 0
    for source_y, row in enumerate(facade_game.town_map):
        for source_x, tile in enumerate(row):
            if tile not in facade_symbols or (source_x, source_y) in authored_door_positions:
                continue
            facade_game.return_to_seamless_town(source_x, source_y)
            local_x, local_y = facade_game.state.player_x, facade_game.state.player_y
            assert not facade_game.current_wilderness_outpost_door_at(local_x, local_y)
            assert not facade_game.current_wilderness_structure_door_at(local_x, local_y)
            assert not facade_game.try_enter_wilderness_transition_at(local_x, local_y)
            assert facade_game.on_wilderness()
            checked_facades += 1
    assert checked_facades > 100

    # Exterior doors retain spatially correct interior round trips.
    home_world_game.return_to_seamless_farm(5, 6, facing="UP")
    home_world_game.move(0, -1)
    assert home_world_game.on_house()
    home_world_game.transition_from_house_to_farm()
    assert home_world_game.on_wilderness()
    assert home_world_game.home_world_source_at(
        home_world_game.state.player_x, home_world_game.state.player_y,
    ) == ("farm", 5, 6)
    store_door_x, store_door_y = data.TOWN_DOORS["general_store"]
    home_world_game.return_to_seamless_town(store_door_x, store_door_y + 1, facing="UP")
    home_world_game.move(0, -1)
    assert home_world_game.on_general_store()
    home_world_game.transition_from_general_store_to_town()
    assert home_world_game.on_wilderness()
    assert home_world_game.home_world_source_at(
        home_world_game.state.player_x, home_world_game.state.player_y,
    ) == ("town", store_door_x, store_door_y + 1)
    home_world_game.set_player_home_world_position(*mine_arrival, facing="UP")
    home_world_game.move(0, -1)
    assert home_world_game.on_mine()
    home_world_game.transition_from_mine_to_farm()
    assert home_world_game.on_wilderness()
    assert home_world_game.home_world_current_world_position() == mine_arrival

    # Regional navigation now points to real places instead of scale-model
    # gateway markers.
    home_destinations = {
        str(node["id"]): node
        for node in home_world_game.wilderness_road_destinations_for_chunk(0, 0)
    }
    assert {"main-town", "home-farm", "home-mine"}.issubset(home_destinations)
    arrivals = home_world_game.home_world_destination_world_positions()
    for node_id, arrival_id in (("main-town", "town"), ("home-farm", "farm"), ("home-mine", "mine")):
        assert (
            home_destinations[node_id]["world_x"], home_destinations[node_id]["world_y"],
        ) == arrivals[arrival_id]

    # Legacy exterior locations migrate in place to their canonical world cells.
    migration_game = FarmGame()
    migration_game.state.seamless_home_world_version = 0
    migration_game.state.location = "Town"
    migration_game.state.player_x, migration_game.state.player_y = 41, 20
    migration_game.ensure_seamless_home_world()
    assert migration_game.on_wilderness()
    assert migration_game.home_world_source_at(
        migration_game.state.player_x, migration_game.state.player_y,
    ) == ("town", 41, 20)

    # Version-one seamless saves used the adjacent town origin. Preserve town
    # source positions while moving the player and nearby followers west into
    # the physically separated version-two town.
    v1_migration_game = FarmGame()
    v1_migration_game.state.seamless_home_world_version = 1
    old_world_x, old_world_y = -112 + 41, -10 + 20
    old_chunk_x, old_chunk_y, old_local_x, old_local_y = v1_migration_game.home_world_chunk_from_world(
        old_world_x, old_world_y,
    )
    v1_migration_game.state.location = "Wilderness"
    v1_migration_game.state.wilderness_chunk_x = old_chunk_x
    v1_migration_game.state.wilderness_chunk_y = old_chunk_y
    v1_migration_game.state.player_x = old_local_x
    v1_migration_game.state.player_y = old_local_y
    v1_migration_game.state.travel_follower_states = {
        "migration-follower": {
            "location": "Wilderness", "x": old_local_x + 1, "y": old_local_y,
            "mode": "follow", "activity": "following",
        },
    }
    v1_migration_game.ensure_seamless_home_world()
    assert v1_migration_game.state.seamless_home_world_version == 2
    assert v1_migration_game.home_world_source_at(
        v1_migration_game.state.player_x, v1_migration_game.state.player_y,
    ) == ("town", 41, 20)
    migrated_follower = v1_migration_game.state.travel_follower_states["migration-follower"]
    follower_world = v1_migration_game.wilderness_world_coords(
        v1_migration_game.state.wilderness_chunk_x,
        v1_migration_game.state.wilderness_chunk_y,
        int(migrated_follower["x"]), int(migrated_follower["y"]),
    )
    assert follower_world == v1_migration_game.home_world_world_for_town_position(42, 20)

    assert all(home_world_game.base_map[y][0] == ":" for y in range(8, 13))
    assert all(home_world_game.base_map[0][x] == "<" for x in range(25, 30))
    assert all(home_world_game.base_map[y][-1] == ":" for y in range(8, 13))
    assert not any(
        tile in {"E", "N", "W"}
        for row in home_world_game.base_map
        for tile in row
    )
    assert all(home_world_game.town_map[y][data.TOWN_WIDTH - 1] == ":" for y in range(18, 23))
    assert all(home_world_game.town_map[0][x] == ":" for x in range(56, 60))
    assert all(home_world_game.town_map[y][data.WIDTH - 1] != "E" for y in range(9, 13))
    assert all(home_world_game.town_map[0][x] != "W" for x in range(25, 30))

    commute_game = FarmGame()
    commute_game.autosave_with_message = lambda message: commute_game.set_message(message)
    commute_game.state.location = "Wilderness"
    commute_game.set_wilderness_chunk(0, 0)
    commute_game.state.hour, commute_game.state.minute = 9, 0
    assert commute_game.state.weekday == "Thursday"
    thursday_commuters = [
        row
        for chunk_x, chunk_y in commute_game.home_world_authored_chunks()
        for row in commute_game.home_region_commuters_for_chunk(chunk_x, chunk_y)
    ]
    assert {row["id"] for row in thursday_commuters} == {"cora_courier", "hana_botanist"}
    assert not commute_game.home_region_commuters_for_chunk(1, 0)
    assert all(row["route_destination_id"] == "home-farm" for row in thursday_commuters)
    assert all(tuple((row["preferred_x"], row["preferred_y"])) in set(row["home_route_points"]) for row in thursday_commuters)
    cora = commute_game.npc_record_by_id("cora_courier")
    assert commute_game.town_npc_desired_location(cora) == "RegionalTravel"
    assert cora["regional_destination"] == "Home Farm"
    generated_commuters = [
        row
        for chunk_x, chunk_y in commute_game.home_world_authored_chunks()
        for row in commute_game.generate_wilderness_travelers(chunk_x, chunk_y)
        if row.get("home_region_commute")
    ]
    assert {row["id"] for row in generated_commuters} == {"cora_courier", "hana_botanist"}
    assert all(
        commute_game.wilderness_world_on_regional_road(
            *commute_game.wilderness_world_coords(
                int(row["chunk_x"]), int(row["chunk_y"]), int(row["x"]), int(row["y"]),
            ),
            int(row["chunk_x"]), int(row["chunk_y"]),
        )
        for row in generated_commuters
    )
    assert all(
        (row["route_destination_world_x"], row["route_destination_world_y"])
        == arrivals["farm"]
        for row in generated_commuters
    )
    assert "regular local work route" in " ".join(commute_game.wilderness_traveler_lines(generated_commuters[0])).lower()
    commuter_topic_lines = {
        topic: " ".join(commute_game.wilderness_traveler_lines(generated_commuters[0], topic))
        for topic in ("work", "route", "region", "event")
    }
    assert len(set(commuter_topic_lines.values())) == 4
    assert generated_commuters[0]["route_destination_name"] in commuter_topic_lines["route"]
    commute_game.state.hour = 10
    working_commuters = commute_game.home_region_commuters_for_chunk(0, 0)
    assert not working_commuters
    commute_game.return_to_seamless_farm(8, 9)
    destination_workers = commute_game.home_region_destination_npc_positions()
    assert {npc["id"] for npc in destination_workers.values()} == {"cora_courier", "hana_botanist"}
    assert all(commute_game.is_interactable_tile(x, y) for x, y in destination_workers)
    assert all(commute_game.passable(x, y) for x, y in destination_workers)
    local_helper = next(npc for npc in destination_workers.values() if npc["id"] == "cora_courier")
    money_before_local_help = commute_game.state.money
    stamina_before_local_help = commute_game.state.stamina
    snack_before_local_help = commute_game.state.inventory.get("Field Snack", 0)
    relationship_before_local_help = commute_game.town_npc_relationship("cora_courier")
    assert commute_game.complete_home_region_local_work(local_helper)
    assert commute_game.state.money == money_before_local_help + 25
    assert commute_game.state.stamina == min(
        commute_game.max_stamina(),
        stamina_before_local_help - 3 + 30 // 5,
    )
    assert commute_game.state.inventory.get("Field Snack", 0) == snack_before_local_help + 1
    assert commute_game.town_npc_relationship("cora_courier") == relationship_before_local_help + 2
    assert not commute_game.complete_home_region_local_work(local_helper)
    commute_game.state.location = "Wilderness"
    commute_game.set_wilderness_chunk(0, 0)
    commute_game.state.hour, commute_game.state.minute = 15, 0
    returning_commuters = [
        row
        for chunk_x, chunk_y in commute_game.home_world_authored_chunks()
        for row in commute_game.home_region_commuters_for_chunk(chunk_x, chunk_y)
    ]
    assert returning_commuters and all(row["route_destination_id"] == "main-town" for row in returning_commuters)
    assert all(
        (row["route_destination_world_x"], row["route_destination_world_y"])
        == arrivals["town"]
        for row in returning_commuters
    )
    commute_game.state.hour = 17
    assert not commute_game.home_region_commuters_for_chunk(0, 0)
    commute_game.state.month, commute_game.state.day = 3, 5
    commute_game.state.hour, commute_game.state.minute = 9, 0
    assert commute_game.state.weekday == "Monday"
    monday_commuters = [
        row
        for chunk_x, chunk_y in commute_game.home_world_authored_chunks()
        for row in commute_game.home_region_commuters_for_chunk(chunk_x, chunk_y)
    ]
    assert {row["id"] for row in monday_commuters} == {"garrick_miner"}
    assert monday_commuters[0]["route_destination_id"] == "home-mine"
    assert (
        monday_commuters[0]["route_destination_world_x"],
        monday_commuters[0]["route_destination_world_y"],
    ) == arrivals["mine"]
    commute_game.state.hour = 11
    assert not commute_game.home_region_commuters_for_chunk(0, 0)
    commute_game.state.location = "Mine"
    commute_game.state.mine_floor = 1
    mine_workers = commute_game.home_region_destination_npc_positions()
    assert {npc["id"] for npc in mine_workers.values()} == {"garrick_miner"}
    garrick = next(iter(mine_workers.values()))
    coal_before_local_help = commute_game.state.inventory.get("Coal", 0)
    assert commute_game.complete_home_region_local_work(garrick)
    assert commute_game.state.inventory.get("Coal", 0) == coal_before_local_help + 1
    assert commute_game.home_region_work_record()["mine_safety_day"] == commute_game.town_npc_day_key()
    commute_game.state.location = "Wilderness"
    commute_game.set_wilderness_chunk(0, 0)
    commute_game.state.hour = 9
    commute_game.state.weather = "Stormy"
    assert not commute_game.home_region_commuters_for_chunk(0, 0)
    commute_game.state.weather = "Sunny"
    commute_game.state.spouse_npc_id = "garrick_miner"
    assert not commute_game.home_region_commute_plan(commute_game.npc_record_by_id("garrick_miner"))
    commute_game.state.spouse_npc_id = ""
    commute_game.state.hour, commute_game.state.minute = 9, 50
    commute_cache_key = commute_game.wilderness_traveler_cache_key(0, 0)
    commute_game.ensure_wilderness_travelers()
    commute_game._wilderness_travelers[commute_cache_key] = [{"id": "cache-sentinel"}]
    commute_game.advance_time(10)
    assert commute_cache_key not in commute_game._wilderness_travelers

    climate_game = FarmGame()
    climate_game.autosave_with_message = lambda message: climate_game.set_message(message)
    climate_game.state.location = "Wilderness"
    climate_game.set_wilderness_chunk(0, 0)
    climate_game.state.month = 12
    # Use an explicit off-farm water tile; the removed miniature home hub no
    # longer supplies a decorative pond at this legacy test coordinate.
    climate_game.active_map()[12][72] = "~"
    assert climate_game.state.season == "Winter"
    assert climate_game.wilderness_water_is_frozen_at(72, 12)
    assert climate_game.passable(72, 12)
    assert climate_game.wilderness_stream_actor_passable(0, 0, 72, 12)
    climate_game.state.player_x, climate_game.state.player_y = 60, 20
    assert climate_game.animal_passable_tile(72, 12)
    frozen_glyph = ANSI_CSI_RE.sub("", climate_game.render_streamed_wilderness_raw_tile("~", frozen_water=True))
    assert frozen_glyph == "\u2550"
    original_biome_query = climate_game.wilderness_world_biome_tile
    climate_game.wilderness_world_biome_tile = lambda _wx, _wy: "["
    assert not climate_game.wilderness_water_is_frozen_at(72, 12)
    climate_game.wilderness_world_biome_tile = original_biome_query
    assert "froze" in climate_game.resolve_wilderness_freeze_thaw("Autumn", "Winter")
    climate_game.state.player_x, climate_game.state.player_y = 72, 12
    climate_game.state.month = 3
    thaw_message = climate_game.resolve_wilderness_freeze_thaw("Winter", "Spring")
    assert "nearest bank" in thaw_message
    assert (climate_game.state.player_x, climate_game.state.player_y) != (72, 12)
    assert climate_game.passable(climate_game.state.player_x, climate_game.state.player_y)

    climate_game.state.month, climate_game.state.day = 3, 15
    climate_game.state.weather = "Sunny"
    spring_blooms = {}
    seasonal_chunk = (2, 2)
    for candidate_chunk in ((2, 2), (2, 3), (3, 2), (3, 3), (4, 2)):
        climate_game.set_wilderness_chunk(*candidate_chunk)
        spring_surfaces = climate_game.wilderness_seasonal_surface_lookup()
        spring_blooms = {
            point: data
            for point, data in spring_surfaces.items()
            if data["kind"] == "spring_bloom"
        }
        if spring_blooms:
            seasonal_chunk = candidate_chunk
            break
    assert spring_blooms
    bloom_point, bloom_visual = next(iter(spring_blooms.items()))
    streamed_bloom = ANSI_CSI_RE.sub(
        "",
        climate_game.render_streamed_wilderness_tile(
            seasonal_chunk[0], seasonal_chunk[1], bloom_point[0], bloom_point[1], climate_game.active_map(),
            seasonal_lookup={bloom_point: bloom_visual},
        ),
    )
    assert streamed_bloom == bloom_visual["symbol"]
    climate_game.prepare_wilderness_runtime_overlays()
    visible_bloom = next(point for point in spring_blooms if climate_game.wilderness_seasonal_surface_at(*point))
    flowers_before = climate_game.state.inventory.get("Wildflowers", 0)
    stamina_before_bloom = climate_game.state.stamina
    assert climate_game.interact_with_wilderness_seasonal_surface(*visible_bloom)
    assert climate_game.state.inventory.get("Wildflowers", 0) == flowers_before + 1
    assert climate_game.state.stamina == min(
        climate_game.max_stamina(),
        stamina_before_bloom - 1 + 5 // 5,
    )
    assert not climate_game.wilderness_seasonal_surface_at(*visible_bloom)

    climate_game.state.month, climate_game.state.day = 10, 15
    fall_surfaces = climate_game.wilderness_seasonal_surface_lookup()
    assert any(data["kind"] == "autumn_leaves" for data in fall_surfaces.values())
    climate_game.state.month, climate_game.state.day = 12, 20
    winter_surfaces = climate_game.wilderness_seasonal_surface_lookup()
    assert any(data["kind"] == "snow_drift" for data in winter_surfaces.values())
    climate_game.state.month, climate_game.state.day = 4, 8
    climate_game.state.weather = "Stormy"
    storm_surfaces = climate_game.wilderness_seasonal_surface_lookup()
    assert any(data["kind"] == "storm_debris" and data["blocking"] for data in storm_surfaces.values())

    climate_game.set_wilderness_chunk(0, 0)
    climate_game.state.month, climate_game.state.day = 2, 24
    climate_game.state.weather = "Sunny"
    assert climate_game.wilderness_seasonal_surface_lookup().get((72, 12), {}).get("kind") == "cracking_ice"
    climate_game.state.month, climate_game.state.day = 3, 5
    assert climate_game.wilderness_seasonal_surface_lookup().get((72, 12), {}).get("kind") == "ice_floes"

    climate_game.state.location = "Farm"
    climate_game.state.month, climate_game.state.day = 12, 20
    pond_x, pond_y = next(
        (x, y) for y, row in enumerate(climate_game.base_map) for x, tile in enumerate(row) if tile == "~"
    )
    assert climate_game.passable(pond_x, pond_y)
    assert "frozen farm pond" in climate_game.describe_tile(pond_x, pond_y).lower()
    assert ANSI_CSI_RE.sub("", climate_game.render_tile(pond_x, pond_y)) in {"~", "═"}
    stamina_before_frozen_cast = climate_game.state.stamina
    climate_game.start_fishing_cast(pond_x, pond_y)
    assert "frozen solid" in climate_game.state.message.lower()
    assert climate_game.state.stamina == stamina_before_frozen_cast
    climate_game.state.location = "Wilderness"
    climate_game.set_wilderness_chunk(0, 0)
    climate_game.state.month = 6
    current_climate_map = climate_game.get_wilderness_chunk_map(0, 0)
    neighbor_climate_map = climate_game.get_wilderness_chunk_map(1, 0)
    current_climate_map[20][20] = "i"
    neighbor_climate_map[20][20] = "i"
    assert climate_game.clear_out_of_season_wilderness_forage() >= 2
    assert current_climate_map[20][20] != "i" and neighbor_climate_map[20][20] != "i"
    random.setstate(seam_home_random_state)

    stage2_game = FarmGame()
    stage2_game.autosave_with_message = lambda message: stage2_game.set_message(message)
    stage2_game.state.location = "Wilderness"
    stage2_game.set_wilderness_chunk(6, 7)
    region_anchor = stage2_game.wilderness_region_coords(6, 7)
    region_cache_size = len(stage2_game._wilderness_region_coords_cache)
    assert all(stage2_game.wilderness_region_coords(6, 7) == region_anchor for _ in range(100))
    assert len(stage2_game._wilderness_region_coords_cache) == region_cache_size
    assert stage2_game.wilderness_region_structure_chunk(6, 7) == stage2_game.wilderness_region_structure_chunk(6, 7)
    assert stage2_game.wilderness_region_outpost_chunk(6, 7) == stage2_game.wilderness_region_outpost_chunk(6, 7)
    assert stage2_game._wilderness_region_structure_chunk_cache
    assert stage2_game._wilderness_region_outpost_chunk_cache

    animal_overlay_calls = {"event": 0, "seasonal": 0}
    original_event_lookup = stage2_game.wilderness_event_visual_lookup
    original_seasonal_lookup = stage2_game.wilderness_seasonal_surface_lookup
    def counted_event_lookup(*args, **kwargs):
        animal_overlay_calls["event"] += 1
        return original_event_lookup(*args, **kwargs)
    def counted_seasonal_lookup(*args, **kwargs):
        animal_overlay_calls["seasonal"] += 1
        return original_seasonal_lookup(*args, **kwargs)
    stage2_game.wilderness_event_visual_lookup = counted_event_lookup
    stage2_game.wilderness_seasonal_surface_lookup = counted_seasonal_lookup
    stage2_game.generate_wilderness_animals_for_chunk(6, 7)
    stage2_game.wilderness_event_visual_lookup = original_event_lookup
    stage2_game.wilderness_seasonal_surface_lookup = original_seasonal_lookup
    assert animal_overlay_calls == {"event": 1, "seasonal": 1}, animal_overlay_calls
    stage2_game.map_lines()
    first_prefetch_keys = set(stage2_game._wilderness_stream_preloaded_chunks)
    assert len(first_prefetch_keys) == 1
    # Frame cost varies by machine; pin the throttle clock so this verifies
    # immediate-repeat behavior instead of depending on rendering under 0.75s.
    stage2_game._wilderness_stream_last_prefetch_time = farmstead_main.time.monotonic()
    stage2_game.map_lines()
    assert set(stage2_game._wilderness_stream_preloaded_chunks) == first_prefetch_keys
    stage2_east_key = stage2_game.wilderness_chunk_key(7, 7)
    stage2_game.wilderness_maps.pop(stage2_east_key, None)
    stage2_game._wilderness_stream_preloaded_chunks.discard(stage2_east_key)
    for runtime_cache_name in (
        "wilderness_static_checked_chunks",
        "wilderness_balanced_chunks",
        "wilderness_procedural_town_checked_chunks",
        "repaired_wilderness_chunks",
    ):
        runtime_cache = getattr(stage2_game, runtime_cache_name, None)
        if isinstance(runtime_cache, set):
            runtime_cache.discard(stage2_east_key)
    stage2_game.state.player_x, stage2_game.state.player_y = 84, 9
    assert (7, 7) in stage2_game.wilderness_stream_viewport_chunks(84, 9)
    assert stage2_game.prepare_wilderness_visible_chunks(84, 9) >= 1
    assert stage2_east_key in stage2_game.wilderness_maps
    assert stage2_east_key in stage2_game._wilderness_stream_preloaded_chunks
    stage2_game.prepare_wilderness_stream_window(limit=8)
    stage2_game.ensure_wilderness_animals()
    stage2_game.wilderness_animals[stage2_east_key] = [{"id": "stream-deer", "species": "Deer", "x": 2, "y": 9, "seen": False, "calm": 1}]
    stage2_game.ensure_wilderness_travelers()
    stage2_game._wilderness_travelers[stage2_game.wilderness_traveler_cache_key(7, 7)] = []
    stage2_game.ensure_wilderness_strongholds()
    stage2_game.wilderness_stronghold_enemies[stage2_game.wilderness_stronghold_key(7, 7)] = []
    stage2_game.state.player_x = 84
    stage2_game.state.player_y = 9
    stream_world_x, stream_world_y = stage2_game.wilderness_world_coords(7, 7, 0, 9)
    stream_visual_key = int(stream_world_x) * 31 + int(stream_world_y) * 17
    current_stream_color = stage2_game.render_streamed_wilderness_raw_tile(".", stream_visual_key)
    assert stage2_game.render_streamed_wilderness_tile(7, 7, 0, 9, [["." if (x, y) == (0, 9) else ";" for x in range(86)] for y in range(38)]) == current_stream_color
    assert visuals.visual_style_issues() == []
    horizontal_wall = [list("....."), list("#####"), list(".....")]
    vertical_wall = [list(".#."), list(".#."), list(".#.")]
    assert visuals.architectural_wall_glyph(horizontal_wall, 2, 1) == "\u2500"
    assert visuals.architectural_wall_glyph(vertical_wall, 1, 1) == "\u2502"
    assert visuals.architectural_wall_glyph(horizontal_wall, 2, 1, detailed=False) == "#"
    assert visuals.exterior_window_at(horizontal_wall, 2, 1, visual_key=0)
    assert visuals.wilderness_display_glyph("~", 0, 0) == "\u2248"
    assert visuals.wilderness_display_glyph("~", 1, 0) == "~"
    assert visuals.wilderness_display_glyph(".", 0, 0, detailed=False) == "."
    light_room = [list("......."), list("...f..."), list("......."), list(".......")]
    assert visuals.interior_light_color(light_room, 3, 3, ".", support.C.FLOOR, 22) == support.C.LIT
    assert visuals.interior_light_color(light_room, 3, 3, ".", support.C.FLOOR, 12) == support.C.FLOOR
    rendered_wall = stage2_game.render_interior_visual_tile(horizontal_wall, 2, 1, "public")
    assert ANSI_CSI_RE.sub("", rendered_wall) == "\u2500"
    assert horizontal_wall[1][2] == "#"
    companion_glyph, companion_color = visuals.actor_style("follower", "@", "companion")
    assert companion_glyph == "&" and companion_color == support.C.ACTOR_FOLLOWER
    spouse_glyph, spouse_color = visuals.actor_style("follower", "@", "spouse")
    assert spouse_glyph == "@" and spouse_color == support.C.ACTOR_FAMILY
    elite_glyph, elite_color = visuals.actor_style("hostile", "s", elite=True, bounty=True)
    assert elite_glyph == "S" and elite_color == support.C.ACTOR_BOUNTY
    landscape_glyph, landscape_color = visuals.wilderness_landmark_style("j", "large_lake")
    assert landscape_glyph == "\u25c6" and landscape_color == support.C.LANDMARK_NATURAL
    assert visuals.wilderness_landmark_style("j", "large_lake", detailed=False)[0] == "j"
    assert visuals.wilderness_landmark_style("k")[0] == "\u2261"
    assert visuals.weather_overlay_allowed(".") is True
    assert visuals.weather_overlay_allowed("j") is False
    assert visuals.weather_overlay_allowed("#") is False
    near_weather = visuals.weather_overlay_style("Rainy", 0, 0.1)
    far_weather = visuals.weather_overlay_style("Rainy", 0, 0.9)
    assert near_weather[0] == far_weather[0] == "'"
    assert near_weather[1] != far_weather[1] and support.C.DIM in far_weather[1]
    assert ANSI_CSI_RE.sub("", stage2_game.render_streamed_wilderness_raw_tile("j", 0, None, "large_lake")) == "\u25c6"
    assert ANSI_CSI_RE.sub("", stage2_game.render_mine_enemy({"species": "Elite Slime", "boss": True})) == "S"
    town_surface_map = [
        list("....."),
        list(".GGG."),
        list(".GGG."),
        list(".GDG."),
        list("....."),
    ]
    assert visuals.town_building_surface(town_surface_map, 1, 1)[0] == "\u250c"
    assert visuals.town_building_surface(town_surface_map, 2, 1)[0] == "\u2500"
    assert visuals.town_building_surface(town_surface_map, 1, 2)[0] == "\u2502"
    assert visuals.town_building_surface(town_surface_map, 2, 2, visual_key=1)[0] in {"\u2591", "\u2592"}
    assert visuals.town_building_surface(town_surface_map, 1, 3)[0] == "\u2514"
    assert visuals.town_building_surface(town_surface_map, 2, 2, detailed=False)[0] == "G"
    forge_surface_map = [list("....."), list(".XXX."), list(".XXX."), list(".XDX."), list(".....")]
    civic_surface_map = [list("....."), list(".RRR."), list(".RRR."), list(".RDR."), list(".....")]
    assert visuals.town_building_surface(town_surface_map, 1, 1)[1] != visuals.town_building_surface(forge_surface_map, 1, 1)[1]
    assert visuals.town_building_surface(forge_surface_map, 1, 1)[0] == "\u250f"
    assert visuals.town_building_surface(civic_surface_map, 1, 1)[0] == "\u2554"
    town_surface_game = FarmGame()
    town_surface_game.state.location = "Town"
    rendered_town_roof = ANSI_CSI_RE.sub("", town_surface_game.render_tile(6, 4, town_surface_game.town_map))
    assert rendered_town_roof in {"\u2591", "\u2592", "o"}
    assert town_surface_game.town_map[4][6] == "G"
    assert ANSI_CSI_RE.sub("", town_surface_game.render_tile(*data.TOWN_DOORS["general_store"], town_surface_game.town_map)) == "D"
    locked_library_glyphs = {
        ANSI_CSI_RE.sub("", town_surface_game.render_tile(x, y, town_surface_game.town_map))
        for y in range(3, 9)
        for x in range(36, 47)
    }
    assert "x" not in locked_library_glyphs and "\u2573" not in locked_library_glyphs
    assert ANSI_CSI_RE.sub("", town_surface_game.render_tile(*data.TOWN_DOORS["library"], town_surface_game.town_map)) == "\u2501"
    town_frame_lookup_calls = {"events": 0, "lamps": 0, "per_tile_lamps": 0}
    original_town_event_features = town_surface_game.town_public_event_features
    original_town_lamp_lookup = town_surface_game.town_streetlamp_lit_tile_lookup
    original_tile_lamp_check = town_surface_game.tile_is_near_streetlamp

    def tracked_town_event_features():
        town_frame_lookup_calls["events"] += 1
        return original_town_event_features()

    def tracked_town_lamp_lookup(radius=5):
        town_frame_lookup_calls["lamps"] += 1
        return original_town_lamp_lookup(radius)

    def tracked_tile_lamp_check(x, y, radius=5):
        town_frame_lookup_calls["per_tile_lamps"] += 1
        return original_tile_lamp_check(x, y, radius)

    town_surface_game.town_public_event_features = tracked_town_event_features
    town_surface_game.town_streetlamp_lit_tile_lookup = tracked_town_lamp_lookup
    town_surface_game.tile_is_near_streetlamp = tracked_tile_lamp_check
    try:
        assert town_surface_game.map_lines()
    finally:
        town_surface_game.town_public_event_features = original_town_event_features
        town_surface_game.town_streetlamp_lit_tile_lookup = original_town_lamp_lookup
        town_surface_game.tile_is_near_streetlamp = original_tile_lamp_check
    assert town_frame_lookup_calls == {"events": 1, "lamps": 1, "per_tile_lamps": 0}
    assert town_surface_game._base_tile_color_cache[0] == town_surface_game.state.season
    farm_surface_game = FarmGame()
    farm_surface_game.state.location = "Farm"
    assert ANSI_CSI_RE.sub("", farm_surface_game.render_tile(3, 2, farm_surface_game.base_map)) == "\u250c"
    assert ANSI_CSI_RE.sub("", farm_surface_game.render_tile(5, 5, farm_surface_game.base_map)) == "D"
    assert farm_surface_game.base_map[2][3] == "H"
    shed_glyph, _shed_color = visuals.farm_structure_surface("Storage Shed", 5, 4, 2, 2)
    pond_glyph, _pond_color = visuals.farm_structure_surface("Fish Pond", 4, 3, 1, 1)
    assert shed_glyph == "S" and pond_glyph == "\u2248"
    assert visuals.farm_structure_surface("Chicken Coop", 4, 3, 0, 0)[0] == "\u250c"
    assert visuals.farm_structure_surface("Tool Shed", 4, 3, 0, 0)[0] == "\u250f"
    assert visuals.farm_structure_surface("Well", 2, 2, 0, 0)[0] == "\u256d"
    assert visuals.farm_structure_surface("Storage Shed", 5, 4, 2, 2, detailed=False)[0] == "S"
    assert visuals.connected_network_glyph(False, True, False, False) == "\u2500"
    assert visuals.connected_network_glyph(True, True, True, True) == "\u253c"
    assert visuals.connected_network_glyph(False, False, False, False, detailed=False, isolated="|") == "|"
    natural_cave_map = [list("#####"), list("#.<C#"), list("#####")]
    dungeon_visual_map = [list("#####"), list("#.$S#"), list("#####")]
    assert visuals.underground_tile_style(natural_cave_map, 0, 0, "cave")[0] in {"#", "▒", "▓"}
    assert visuals.underground_tile_style(natural_cave_map, 0, 0, "cave", detailed=False)[0] == "#"
    assert visuals.underground_tile_style(natural_cave_map, 2, 1, "cave")[1] == support.C.UNDERGROUND_EXIT
    assert visuals.underground_tile_style(natural_cave_map, 3, 1, "cave")[0] == "♦"
    assert visuals.underground_tile_style(dungeon_visual_map, 2, 0, "dungeon")[0] == "─"
    assert visuals.underground_tile_style(dungeon_visual_map, 2, 1, "dungeon")[1] == support.C.ORE_GOLD
    assert visuals.underground_tile_style(dungeon_visual_map, 3, 1, "dungeon")[1] == support.C.UNDERGROUND_RELIC
    animated_underground_water = [list("~")]
    assert visuals.underground_tile_style(animated_underground_water, 0, 0, "mine", visual_phase=0, visual_key=0)[0] == "≈"
    assert visuals.underground_tile_style(animated_underground_water, 0, 0, "mine", visual_phase=1, visual_key=0)[0] == "~"
    underground_render_game = FarmGame()
    underground_render_game.state.location = "Mine"
    underground_render_map = [list("#####"), list("#.OP#"), list("#####")]
    assert ANSI_CSI_RE.sub("", underground_render_game.render_tile(2, 1, underground_render_map)) == "O"
    assert ANSI_CSI_RE.sub("", underground_render_game.render_tile(3, 1, underground_render_map)) == "◆"
    assert underground_render_map[1][3] == "P"
    farm_surface_game.state.placed_objects["Farm:20,10"] = "Fence"
    farm_surface_game.state.placed_objects["Farm:21,10"] = "Fence"
    assert ANSI_CSI_RE.sub("", farm_surface_game.render_placed_object("Fence", 20, 10, 20, 10)) == "\u2500"
    placed_frame_lookup = farm_surface_game.build_frame_placed_object_lookup()
    assert placed_frame_lookup[(20, 10)][1] == "Fence"
    assert placed_frame_lookup[(21, 10)][1] == "Fence"
    farm_surface_game.map_lines()
    assert getattr(farm_surface_game, "_frame_placed_object_lookup", None) is None
    crop_weather_game = FarmGame()
    crop_weather_game.state.location = "Farm"
    crop_weather_game.state.weather = "Rainy"
    crop_weather_game.set_crop(10, 10, state.Crop("Turnip"))
    assert crop_weather_game.render_weather_overlay(10, 10) is None
    assert visuals.wilderness_tile_color("%", "Spring") == support.C.FOREST
    assert visuals.wilderness_tile_color("l", "Spring") == support.C.FUNGAL
    assert visuals.wilderness_tile_color("r", "Spring") == support.C.WETLAND
    assert visuals.wilderness_tile_color("`", "Spring") == support.C.DESERT
    assert visuals.wilderness_tile_color("[", "Spring") == support.C.COAST
    assert visuals.wilderness_tile_color("~", "Spring", 0, 0) != visuals.wilderness_tile_color("~", "Spring", 1, 0)
    assert visuals.wilderness_tile_color(";", "Fall") == support.C.FALL_GRASS
    assert visuals.wilderness_tile_color(";", "Winter") == support.C.TUNDRA
    assert visuals.wilderness_tile_color("%", "Winter") == support.C.TUNDRA
    assert visuals.wilderness_tile_color("r", "Winter") == support.C.TUNDRA
    assert visuals.wilderness_tile_color("%", "Spring", weather="Snowy") == support.C.TUNDRA
    assert visuals.wilderness_tile_color(";", "Summer", weather="Stormy") == support.C.WETLAND
    assert visuals.interior_tile_color(".", "public") == support.C.FLOOR
    assert visuals.interior_tile_color(".", "home") == support.C.FLOOR_WARM
    assert visuals.interior_tile_color("D", "public") == support.C.DOOR
    assert visuals.wilderness_tile_color("%", "Spring", high_contrast=True) == support.C.SPRING_GRASS
    assert visuals.cartography_symbol_style("_", "unknown")[0] == "\u2591"
    assert visuals.cartography_symbol_style("T", "home")[0] == "\u2302"
    assert visuals.cartography_symbol_style("t", "town")[0] == "\u25a3"
    assert visuals.cartography_symbol_style(":", "road")[0] == "\u2500"
    assert visuals.cartography_symbol_style("d", "delta")[0] == "\u224b"
    assert visuals.cartography_symbol_style("d", "survey")[0] == "\u25c7"
    assert visuals.cartography_symbol_style("P", "port")[0] == "\u2261"
    assert visuals.cartography_symbol_style("_", "unknown", detailed=False)[0] == "_"
    assert visuals.cartography_symbol_style(":", "road", detailed=False)[0] == ":"
    assert visuals.cartography_symbol_style("P", "port", detailed=False)[0] == "P"
    assert visuals.cartography_symbol_style("~", "water", high_contrast=True)[1] == support.C.WATER + support.C.BOLD
    visual_settings = stage2_game.startup_settings_snapshot()
    assert visual_settings["ambient_visuals_enabled"] is True
    assert visual_settings["high_contrast_enabled"] is False
    assert visual_settings["detailed_glyphs_enabled"] is True
    assert visual_settings["show_hud_sidebar"] is True
    assert visual_settings["wake_hour"] == 7
    assert stage2_game.wake_time_label() == "7:00 AM"
    stage2_game.state.wake_hour = 12
    stage2_game.cycle_wake_time_setting()
    assert stage2_game.state.wake_hour == 4
    stage2_game.state.wake_hour = 7
    stage2_game.apply_startup_settings_snapshot({
        **visual_settings,
        "ambient_visuals_enabled": False,
        "high_contrast_enabled": True,
        "detailed_glyphs_enabled": False,
        "show_hud_sidebar": False,
        "wake_hour": 9,
    })
    assert stage2_game.state.ambient_visuals_enabled is False
    assert stage2_game.state.high_contrast_enabled is True
    assert stage2_game.state.detailed_glyphs_enabled is False
    assert stage2_game.state.show_hud_sidebar is False
    assert stage2_game.state.wake_hour == 9
    stage2_game.apply_startup_settings_snapshot(visual_settings)
    ambient_phase_before = int(getattr(stage2_game, "_ambient_visual_phase", 0))
    stage2_game.world_tick(0.91)
    assert int(getattr(stage2_game, "_ambient_visual_phase", 0)) == ambient_phase_before + 1
    original_weather = stage2_game.state.weather
    stage2_game.state.weather = "Stormy"
    east_grid = stage2_game.wilderness_maps[stage2_east_key]
    first_weather_pass = []
    second_weather_pass = []
    for weather_y in range(len(east_grid)):
        for weather_x in range(len(east_grid[0])):
            world_weather_x, world_weather_y = stage2_game.wilderness_world_coords(7, 7, weather_x, weather_y)
            first_weather_pass.append(stage2_game.render_weather_overlay(weather_x, weather_y, east_grid, world_weather_x, world_weather_y))
            second_weather_pass.append(stage2_game.render_weather_overlay(weather_x, weather_y, east_grid, world_weather_x, world_weather_y))
    assert first_weather_pass == second_weather_pass
    assert any(value is not None for value in first_weather_pass)
    weather_phase_before = int(getattr(stage2_game, "_weather_visual_phase", 0))
    stage2_game.world_tick(0.23)
    assert int(getattr(stage2_game, "_weather_visual_phase", 0)) == weather_phase_before + 1
    animated_weather_pass = []
    for weather_y in range(len(east_grid)):
        for weather_x in range(len(east_grid[0])):
            world_weather_x, world_weather_y = stage2_game.wilderness_world_coords(7, 7, weather_x, weather_y)
            animated_weather_pass.append(stage2_game.render_weather_overlay(weather_x, weather_y, east_grid, world_weather_x, world_weather_y))
    assert animated_weather_pass != first_weather_pass
    neighbor_weather_calls = []
    original_weather_renderer = stage2_game.render_weather_overlay

    def track_stream_weather(x, y, tile_map=None, world_x=None, world_y=None):
        if world_x is not None and int(world_x) >= 7 * 86:
            neighbor_weather_calls.append((int(world_x), int(world_y)))
        return original_weather_renderer(x, y, tile_map, world_x, world_y)

    stage2_game.render_weather_overlay = track_stream_weather
    stage2_game.map_lines()
    stage2_game.render_weather_overlay = original_weather_renderer
    stage2_game.state.weather = original_weather
    assert neighbor_weather_calls
    stage2_lines = [ANSI_CSI_RE.sub("", line) for line in stage2_game.map_lines()]
    deer_screen_x = farmstead_main.VIEW_WIDTH // 2 + 4
    assert stage2_lines[farmstead_main.VIEW_HEIGHT // 2][deer_screen_x] == stage2_game.animal_symbol("Deer")
    assert "deer" in stage2_game.describe_streamed_wilderness_tile(88, 9).lower()
    assert any("Snapshot only" in line for line in stage2_game.streamed_wilderness_look_lines(88, 9))
    look_lines = [ANSI_CSI_RE.sub("", line) for line in stage2_game.wilderness_stream_map_lines(88, 9, (88, 9))]
    assert look_lines[farmstead_main.VIEW_HEIGHT // 2][farmstead_main.VIEW_WIDTH // 2] == "X"
    boundary_interaction_random_state = random.getstate()
    boundary_traveler = {"id": "boundary-ranger", "name": "Vale", "role": "Ranger", "x": 0, "y": 9, "anchor_x": 0, "anchor_y": 9, "activity": "checking the boundary trail"}
    stage2_game._wilderness_travelers[stage2_game.wilderness_traveler_cache_key(7, 7)] = [boundary_traveler]
    stage2_game.wilderness_maps[stage2_east_key][9][0] = "."
    stage2_game.state.player_x, stage2_game.state.player_y = 85, 9
    stage2_game.state.facing = "RIGHT"
    boundary_interactions = []
    stage2_game.show_wilderness_traveler = lambda traveler: boundary_interactions.append(str(traveler.get("id", "")))
    assert stage2_game.is_interactable_tile(86, 9)
    stage2_game.general_interact()
    assert boundary_interactions == ["boundary-ranger"]
    assert (stage2_game.state.wilderness_chunk_x, stage2_game.state.wilderness_chunk_y) == (7, 7)
    stage2_game.set_wilderness_chunk(6, 7)
    stage2_game._wilderness_travelers[stage2_game.wilderness_traveler_cache_key(7, 7)] = []
    random.setstate(boundary_interaction_random_state)
    stage2_game.wilderness_maps[stage2_east_key][9][0] = "W"
    assert stage2_game.is_interactable_tile(86, 9)
    watercress_before_stream_action = int(stage2_game.state.inventory.get("Watercress", 0))
    stage2_game.use_wilderness_action(86, 9)
    assert (stage2_game.state.wilderness_chunk_x, stage2_game.state.wilderness_chunk_y) == (7, 7)
    assert int(stage2_game.state.inventory.get("Watercress", 0)) == watercress_before_stream_action + 1

    stage3_game = FarmGame()
    stage3_game.autosave_with_message = lambda message: stage3_game.set_message(message)
    stage3_game.state.location = "Wilderness"
    stage3_game.set_wilderness_chunk(6, 7)
    stage3_game.prepare_wilderness_stream_window(limit=8)
    stage3_current_key = stage3_game.wilderness_chunk_key(6, 7)
    stage3_east_key = stage3_game.wilderness_chunk_key(7, 7)
    stage3_game.wilderness_maps[stage3_current_key][9][85] = "."
    stage3_game.wilderness_maps[stage3_east_key][9][0] = "."
    stage3_game.wilderness_maps[stage3_current_key][10][85] = "."
    stage3_game.wilderness_maps[stage3_current_key][10][84] = "."
    stage3_game.wilderness_maps[stage3_east_key][10][0] = "."
    stage3_game.ensure_wilderness_animals()
    stage3_animal = {"id": "crossing-deer", "species": "Deer", "x": 0, "y": 9, "seen": False, "calm": 1}
    stage3_game.wilderness_animals[stage3_current_key] = []
    stage3_game.wilderness_animals[stage3_east_key] = [stage3_animal]
    stage3_game.ensure_wilderness_travelers()
    stage3_current_travelers = stage3_game.wilderness_traveler_cache_key(6, 7)
    stage3_east_travelers = stage3_game.wilderness_traveler_cache_key(7, 7)
    stage3_traveler = {"id": "crossing-ranger", "name": "Rook", "role": "Ranger", "x": 0, "y": 10, "anchor_x": 0, "anchor_y": 10, "activity": "walking the regional trails"}
    stage3_game._wilderness_travelers[stage3_current_travelers] = []
    stage3_game._wilderness_travelers[stage3_east_travelers] = [stage3_traveler]
    moved_animal, animal_chunk_x, animal_chunk_y = stage3_game.try_move_wilderness_stream_actor(
        "animal", stage3_animal, 7, 7, [(-1, 0)]
    )
    assert moved_animal and (animal_chunk_x, animal_chunk_y) == (6, 7)
    assert stage3_animal in stage3_game.wilderness_animals[stage3_current_key]
    assert stage3_animal not in stage3_game.wilderness_animals[stage3_east_key]
    assert (stage3_animal["x"], stage3_animal["y"]) == (85, 9)
    moved_traveler, traveler_chunk_x, traveler_chunk_y = stage3_game.try_move_wilderness_stream_actor(
        "traveler", stage3_traveler, 7, 7, [(-1, 0)]
    )
    assert moved_traveler and (traveler_chunk_x, traveler_chunk_y) == (6, 7)
    assert stage3_traveler in stage3_game._wilderness_travelers[stage3_current_travelers]
    assert stage3_traveler not in stage3_game._wilderness_travelers[stage3_east_travelers]
    traveler_random = wilderness_system.random.random
    traveler_shuffle = wilderness_system.random.shuffle
    try:
        wilderness_system.random.random = lambda: 0.0
        wilderness_system.random.shuffle = lambda values: None
        stage3_game.update_wilderness_travelers()
    finally:
        wilderness_system.random.random = traveler_random
        wilderness_system.random.shuffle = traveler_shuffle
    assert stage3_traveler in stage3_game._wilderness_travelers[stage3_current_travelers]
    assert (stage3_traveler["x"], stage3_traveler["y"]) == (84, 10)
    assert stage3_game.update_wilderness_stream_actors(limit=1) == 1
    assert stage3_east_key in stage3_game._wilderness_stream_dirty_actor_chunks
    with TemporaryDirectory() as stage3_save_directory:
        stage3_save_path = Path(stage3_save_directory) / "stream-actors.json"
        stage3_game.save(quiet=True, path=stage3_save_path)
        stage3_save_data = json.loads(stage3_save_path.read_text(encoding="utf-8"))
        assert stage3_east_key not in stage3_save_data["wilderness_maps"]
        assert stage3_east_key in stage3_save_data["wilderness_animals"]

    stream_tool_random_state = random.getstate()
    stream_tool_game = FarmGame()
    stream_tool_game.autosave_with_message = lambda message: stream_tool_game.set_message(message)
    stream_tool_game.state.location = "Wilderness"
    stream_tool_game.set_wilderness_chunk(6, 7)
    stream_tool_game.prepare_wilderness_stream_window(limit=8)
    stream_tool_east_key = stream_tool_game.wilderness_chunk_key(7, 7)
    stream_tool_game.wilderness_maps[stream_tool_east_key][9][0] = "~"
    stream_tool_game.state.player_x, stream_tool_game.state.player_y = 85, 9
    stream_tool_game.state.facing = "RIGHT"
    stream_tool_game.state.selected_tool_index = stream_tool_game.state.available_tools.index("Fishing Rod")
    stream_tool_game.state.stamina = 50
    assert stream_tool_game.water_tile_at(86, 9)
    stream_tool_game.use_wilderness_tool()
    assert (stream_tool_game.state.wilderness_chunk_x, stream_tool_game.state.wilderness_chunk_y) == (7, 7)
    assert stream_tool_game.state.fishing_active
    assert (stream_tool_game.state.fishing_target_x, stream_tool_game.state.fishing_target_y) == (0, 9)
    stream_tool_game.clear_fishing_state()
    stream_tool_game.set_wilderness_chunk(6, 7)
    stream_tool_game.wilderness_maps[stream_tool_east_key][9][0] = "T"
    stream_tool_game.state.player_x, stream_tool_game.state.player_y = 85, 9
    stream_tool_game.state.facing = "RIGHT"
    stream_tool_game.state.owned_tools.append("Axe")
    stream_tool_game.state.tool_levels["Axe"] = 1
    stream_tool_game.state.selected_tool_index = stream_tool_game.state.available_tools.index("Axe")
    wood_before_stream_tool = int(stream_tool_game.state.inventory.get("Wood", 0))
    stream_tool_game.use_wilderness_tool()
    assert (stream_tool_game.state.wilderness_chunk_x, stream_tool_game.state.wilderness_chunk_y) == (7, 7)
    assert int(stream_tool_game.state.inventory.get("Wood", 0)) > wood_before_stream_tool
    assert stream_tool_game.wilderness_maps[stream_tool_east_key][9][0] != "T"
    random.setstate(stream_tool_random_state)
    regional_segments = seamless_game.wilderness_region_route_segments(7, 7)
    assert regional_segments
    regional_edges = seamless_game.wilderness_road_network_edges(7, 7)
    assert regional_edges
    assert all(edge["kind"] in {"regional_route", "local_spur"} for edge in regional_edges)
    assert all(
        str(node.get("kind", "")) != "region_center"
        for edge in regional_edges
        for node in (edge["start"], edge["end"])
    )
    purposeful_kinds = {
        "main_town", "town", "port_city", "port", "founded_town",
        "reclaimed_stronghold", "outpost", "road_service",
    }
    local_spurs = [edge for edge in regional_edges if edge["kind"] == "local_spur"]
    assert local_spurs
    assert all(str(edge["end"].get("kind", "")) in purposeful_kinds for edge in local_spurs)
    assert all(
        str(node.get("kind", "")) in purposeful_kinds
        for node in seamless_game.wilderness_road_destinations_for_chunk(7, 7)
    )
    route_start, route_end = regional_segments[0]
    midpoint_wx = (route_start[0] + route_end[0]) // 2
    midpoint_wy = (route_start[1] + route_end[1]) // 2
    road_chunk = (midpoint_wx // 86, midpoint_wy // 38)
    blank_road_grid = [[";" for _ in range(86)] for _ in range(38)]
    assert seamless_game.apply_wilderness_regional_roads(blank_road_grid, *road_chunk) > 0
    assert any(tile in {":", "="} for row in blank_road_grid for tile in row)
    traveler_spur = next(edge for edge in local_spurs if str(edge["end"].get("kind", "")) in {"outpost", "road_service"})
    traveler_chunk = (int(traveler_spur["end"]["chunk_x"]), int(traveler_spur["end"]["chunk_y"]))
    road_travelers = seamless_game.generate_wilderness_travelers(*traveler_chunk)
    traveler_grid = seamless_game.get_wilderness_chunk_map(*traveler_chunk)
    routed_traveler = next((traveler for traveler in road_travelers if traveler.get("road_route")), None)
    if routed_traveler is None:
        road_x, road_y = next(
            (x, y)
            for y, row in enumerate(traveler_grid)
            for x, tile in enumerate(row)
            if tile == ":"
        )
        routed_traveler = {"id": "route-smoke", "name": "Route Smoke", "role": "Courier", "x": road_x, "y": road_y}
        seamless_game.assign_wilderness_traveler_route(routed_traveler, *traveler_chunk)
    assert routed_traveler["route_destination_name"]
    assert routed_traveler["route_destination_kind"] in purposeful_kinds
    assert traveler_grid[int(routed_traveler["y"])][int(routed_traveler["x"])] == ":"
    assert not procedural_town_game.wilderness_chunk_has_safe_waypoint(
        procedural_town_x,
        procedural_town_y,
    )
    procedural_town_map = procedural_town_game.get_wilderness_chunk_map(
        procedural_town_x,
        procedural_town_y,
    )
    procedural_town_plan = procedural_town_game.procedural_town_plan(
        procedural_town_x,
        procedural_town_y,
    )
    assert procedural_town_plan is not None
    assert procedural_town_plan["source"] == "procedural_wilderness"
    assert procedural_town_plan["auto_generated"] is True
    town_geography = procedural_town_plan.get("geography", {})
    assert town_geography.get("region_key") == procedural_town_game.wilderness_region_profile(procedural_town_x, procedural_town_y)["key"]
    assert town_geography.get("setting")
    assert town_geography.get("water_access") in {"waterfront", "near watershed", "inland"}
    eligible_region_scores = [
        procedural_town_game.procedural_town_geography(cx, cy)["site_score"]
        for cx, cy in procedural_town_game.wilderness_region_chunks(procedural_town_x, procedural_town_y)
        if abs(cx) + abs(cy) >= procedural_towns.PROCEDURAL_TOWN_MIN_DISTANCE
        and procedural_town_game.procedural_town_terrain_is_eligible(cx, cy)
        and not procedural_town_game.is_claimable_wilderness_chunk(cx, cy)
        and not procedural_town_game.wilderness_chunk_has_dungeon_site(cx, cy)
        and not procedural_town_game.wilderness_chunk_has_stronghold(cx, cy)
    ]
    assert eligible_region_scores and town_geography["site_score"] == max(eligible_region_scores)
    hinterland_game = FarmGame()
    hinterland_game.autosave_with_message = lambda message: hinterland_game.set_message(message)
    hinterland_game.state.wilderness_seed = 24681357
    hinterland_chunks = hinterland_game.procedural_town_hinterland_chunks(procedural_town_x, procedural_town_y)
    assert 1 <= len(hinterland_chunks) <= 3
    hinterland_chunk = hinterland_chunks[0]
    hinterland_game.state.location = "Wilderness"
    hinterland_game.set_wilderness_chunk(*hinterland_chunk)
    hinterland_profile = hinterland_game.procedural_town_hinterland_profile()
    assert hinterland_profile and tuple(hinterland_profile["town_chunk"]) == procedural_town_chunk
    hinterland_position = hinterland_game.procedural_town_hinterland_position()
    assert hinterland_position != (-1, -1)
    assert hinterland_game.procedural_town_hinterland_position(
        hinterland_chunk[0], hinterland_chunk[1], hinterland_game.active_map()
    ) == hinterland_position
    hinterland_stream_features = hinterland_game.wilderness_stream_feature_lookup(
        hinterland_chunk[0], hinterland_chunk[1], hinterland_game.active_map()
    )
    assert hinterland_stream_features[hinterland_position]["kind"] == "hinterland"
    assert not hinterland_game.passable(*hinterland_position)
    assert hinterland_profile["name"].lower() in hinterland_game.describe_tile(*hinterland_position).lower()
    linked_plan = hinterland_game.ensure_procedural_town_plan(*procedural_town_chunk)
    development_before = int(hinterland_game.ensure_procedural_town_community(linked_plan).get("development_points", 0))
    hinterland_game.state.stamina = 50
    assert hinterland_game.work_procedural_town_hinterland()
    assert int(hinterland_game.ensure_procedural_town_community(linked_plan).get("development_points", 0)) == development_before + 2
    assert not hinterland_game.work_procedural_town_hinterland()
    assert hinterland_game.overworld_chunk_preview_symbol(*hinterland_chunk) in {"h", "V"}
    assert procedural_town_plan["map_applied"] is True
    assert int(procedural_town_plan["runtime_version"]) >= 14
    assert procedural_town_plan.get("regional_approaches")
    assert any(tile != "#" for tile in procedural_town_map[0])
    assert any(tile != "#" for tile in procedural_town_map[-1])
    assert any(row[0] != "#" for row in procedural_town_map)
    assert any(row[-1] != "#" for row in procedural_town_map)
    assert procedural_town_plan["discovered"] is False
    assert procedural_town_plan["specialty"] in {"library", "workshop", "park"}
    sheriff_exterior = next(
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] == "sheriff_office"
    )
    procedural_town_game.state.location = "Wilderness"
    procedural_town_game.state.wilderness_chunk_x = procedural_town_x
    procedural_town_game.state.wilderness_chunk_y = procedural_town_y
    sheriff_interior = procedural_town_game.procedural_town_interior_map(
        sheriff_exterior
    )
    assert any("P" in row for row in sheriff_interior)
    assert all(
        building["phase_index"] == 3
        for building in procedural_town_plan["buildings"].values()
    )
    procedural_enterable_exteriors = [
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] not in procedural_towns.PROCEDURAL_TOWN_OPEN_BUILDINGS
    ]
    procedural_open_exteriors = [
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] in procedural_towns.PROCEDURAL_TOWN_OPEN_BUILDINGS
    ]
    assert sum(
        row.count(procedural_towns.PROCEDURAL_TOWN_DOOR_SYMBOL)
        for row in procedural_town_map
    ) == len(procedural_enterable_exteriors)
    assert all(
        procedural_town_map[int(building["door_y"])][int(building["door_x"])]
        == procedural_towns.PROCEDURAL_TOWN_DOOR_SYMBOL
        for building in procedural_enterable_exteriors
    )
    assert all(
        procedural_town_map[int(building["door_y"])][int(building["door_x"])]
        != procedural_towns.PROCEDURAL_TOWN_DOOR_SYMBOL
        for building in procedural_open_exteriors
    )
    general_store_exterior = next(
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] == "general_store"
    )
    gs_x = int(general_store_exterior["x"])
    gs_y = int(general_store_exterior["y"])
    gs_w = int(general_store_exterior["width"])
    gs_h = int(general_store_exterior["height"])
    assert procedural_town_map[gs_y][gs_x] == "#"
    assert procedural_town_map[gs_y][gs_x + gs_w - 1] == "#"
    assert procedural_town_map[gs_y + gs_h - 1][gs_x] == "#"
    assert procedural_town_map[gs_y + gs_h - 1][gs_x + gs_w - 1] == "#"
    assert procedural_town_map[gs_y + gs_h // 2][gs_x + gs_w // 2] == "G"
    stale_refresh_game = FarmGame()
    stale_refresh_game.state.wilderness_seed = procedural_town_game.state.wilderness_seed
    stale_refresh_game.state.location = "Wilderness"
    stale_grid = stale_refresh_game.get_wilderness_chunk_map(
        procedural_town_x,
        procedural_town_y,
    )
    stale_plan = stale_refresh_game.procedural_town_plan(
        procedural_town_x,
        procedural_town_y,
    )
    assert stale_plan is not None
    stale_plan["runtime_version"] = procedural_towns.PROCEDURAL_TOWN_RUNTIME_VERSION - 1
    stale_plan["map_applied"] = True
    stale_grid[2][2] = procedural_towns.PROCEDURAL_TOWN_DOOR_SYMBOL
    refreshed_grid = stale_refresh_game.ensure_procedural_town_applied(
        stale_grid,
        procedural_town_x,
        procedural_town_y,
    )
    refreshed_plan = stale_refresh_game.procedural_town_plan(
        procedural_town_x,
        procedural_town_y,
    )
    assert refreshed_plan["runtime_version"] == procedural_towns.PROCEDURAL_TOWN_RUNTIME_VERSION
    assert refreshed_grid[2][2] != procedural_towns.PROCEDURAL_TOWN_DOOR_SYMBOL
    assert sum(
        row.count(procedural_towns.PROCEDURAL_TOWN_DOOR_SYMBOL)
        for row in refreshed_grid
    ) == len([
        building
        for building in refreshed_plan["buildings"].values()
        if building["type_id"] not in procedural_towns.PROCEDURAL_TOWN_OPEN_BUILDINGS
    ])
    assert procedural_town_game.town_map == authored_town_before_runtime
    procedural_runtime_population = procedural_town_game.procedural_settlement_population(
        procedural_town_x,
        procedural_town_y,
    )
    assert procedural_runtime_population
    assert procedural_town_game.procedural_settlement_population_validation(
        procedural_town_x,
        procedural_town_y,
    ) == {"errors": [], "warnings": []}
    assigned_runtime_resident = next(
        resident
        for resident in procedural_runtime_population["residents"].values()
        if resident.get("assigned_room_id")
    )
    assigned_runtime_home = procedural_town_plan["buildings"][
        assigned_runtime_resident["home_building_id"]
    ]
    assigned_floor_count = procedural_town_game.procedural_town_building_floor_count(
        procedural_town_plan,
        assigned_runtime_home,
    )
    procedural_town_game.state.current_procedural_settlement_key = (
        f"{procedural_town_x},{procedural_town_y}"
    )
    procedural_town_game.state.current_procedural_building_id = str(assigned_runtime_home["id"])
    procedural_town_game.state.current_procedural_building_floor = int(
        assigned_runtime_resident["assigned_room_floor"]
    )
    procedural_town_game.state.location = procedural_towns.PROCEDURAL_TOWN_INTERIOR_LOCATION
    assigned_room_anchors = procedural_town_game.procedural_town_assigned_room_anchor(
        procedural_town_plan,
        assigned_runtime_home,
        assigned_runtime_resident,
    )
    assert len(assigned_room_anchors) == 1
    assigned_room_grid = procedural_town_game.procedural_town_interior_map(
        assigned_runtime_home,
        floor=assigned_runtime_resident["assigned_room_floor"],
    )
    assert procedural_town_game.procedural_town_interior_tile_passable(
        assigned_room_grid[assigned_room_anchors[0][1]][assigned_room_anchors[0][0]]
    )
    assert procedural_town_game.procedural_town_resident_preferred_interior_floor(
        procedural_town_plan,
        assigned_runtime_home,
        assigned_runtime_resident,
        "late",
        assigned_floor_count,
        0,
    ) == int(assigned_runtime_resident["assigned_room_floor"])
    procedural_town_game.state.location = "Wilderness"
    procedural_town_game.state.wilderness_chunk_x = procedural_town_x
    procedural_town_game.state.wilderness_chunk_y = procedural_town_y
    district_growth_game = FarmGame()
    district_growth_game.autosave_with_message = (
        lambda message: district_growth_game.set_message(message)
    )
    district_growth_game.state.wilderness_seed = procedural_town_game.state.wilderness_seed
    district_growth_game._procedural_town_site_cache = {}
    district_plan = district_growth_game.ensure_procedural_town_plan(
        procedural_town_x,
        procedural_town_y,
    )
    district_community = district_growth_game.ensure_procedural_town_community(
        district_plan
    )
    district_community["development_points"] = 170
    assert district_growth_game.refresh_procedural_town_growth(district_plan) == 6
    districts = district_community["districts"]
    assert len(districts) == 6
    assert district_community["district_count"] == 6
    district_community["development_points"] = 570
    assert district_growth_game.procedural_town_district_target_count(district_plan) == 22
    district_community["development_points"] = 170
    footprint = {
        (procedural_town_x, procedural_town_y),
        *{
            (int(district["chunk_x"]), int(district["chunk_y"]))
            for district in districts
        },
    }
    assert len(footprint) == 7
    assert all(
        any(
            neighbor in footprint
            for neighbor in (
                (int(district["chunk_x"]) + 1, int(district["chunk_y"])),
                (int(district["chunk_x"]) - 1, int(district["chunk_y"])),
                (int(district["chunk_x"]), int(district["chunk_y"]) + 1),
                (int(district["chunk_x"]), int(district["chunk_y"]) - 1),
            )
        )
        for district in districts
    )
    for district in districts:
        district_chunk = (int(district["chunk_x"]), int(district["chunk_y"]))
        assert (
            district_growth_game.procedural_town_plan(*district_chunk)
            is district_plan
        )
        local_buildings = district_growth_game.procedural_town_buildings_for_chunk(
            district_plan,
            *district_chunk,
        )
        assert local_buildings
        assert all(
            int(building["district_chunk_x"]) == district_chunk[0]
            and int(building["district_chunk_y"]) == district_chunk[1]
            and int(building["phase_index"]) == 3
            for building in local_buildings
        )
        assert all(
            43 not in range(int(building["x"]), int(building["x"]) + int(building["width"]))
            and 19 not in range(int(building["y"]), int(building["y"]) + int(building["height"]))
            for building in local_buildings
        )
        district_map = district_growth_game.get_wilderness_chunk_map(
            *district_chunk
        )
        assert district["map_applied"] is True
        assert district_map[19][43] == ":"
        assert sum(
            row.count(procedural_towns.PROCEDURAL_TOWN_DOOR_SYMBOL)
            for row in district_map
        ) == len([
            building
            for building in local_buildings
            if building["type_id"] not in procedural_towns.PROCEDURAL_TOWN_OPEN_BUILDINGS
        ])
    district_population = district_growth_game.procedural_settlement_population(
        procedural_town_x,
        procedural_town_y,
    )
    assert district_population
    assert district_growth_game.procedural_settlement_population_validation(
        procedural_town_x,
        procedural_town_y,
    ) == {"errors": [], "warnings": []}
    assert any(
        district_growth_game.procedural_town_building_chunk(
            district_plan,
            district_plan["buildings"].get(str(resident.get("home_building_id", ""))),
        )
        != (procedural_town_x, procedural_town_y)
        for resident in district_population["residents"].values()
    )
    district_growth_game.state.hour = 12
    assert sum(
        bool(district_growth_game.procedural_town_stream_resident_lookup(
            int(district["chunk_x"]),
            int(district["chunk_y"]),
        ))
        for district in districts
    ) >= 2
    entry_district = districts[0]
    entry_chunk = (
        int(entry_district["chunk_x"]),
        int(entry_district["chunk_y"]),
    )
    district_growth_game.state.location = "Wilderness"
    district_growth_game.set_wilderness_chunk(*entry_chunk)
    assert "District" in district_growth_game.location_label()
    entry_building = next(
        building
        for building in district_growth_game.procedural_town_buildings_for_chunk(
            district_plan,
            *entry_chunk,
        )
        if building["type_id"] not in procedural_towns.PROCEDURAL_TOWN_OPEN_BUILDINGS
    )
    assert district_growth_game.procedural_town_building_door_at(
        int(entry_building["door_x"]),
        int(entry_building["door_y"]),
    )["id"] == entry_building["id"]
    assert district_growth_game.enter_procedural_town_building(entry_building)
    assert district_growth_game.current_procedural_town_plan() is district_plan
    assert district_growth_game.exit_procedural_town_building()
    assert (
        district_growth_game.state.wilderness_chunk_x,
        district_growth_game.state.wilderness_chunk_y,
    ) == entry_chunk
    district_report = "\n".join(
        district_growth_game.procedural_town_report_lines(*entry_chunk)
    )
    assert "Developed footprint: 7 chunks" in district_report
    assert "Current district:" in district_report
    procedural_town_game.state.location = "Wilderness"
    procedural_town_game.set_wilderness_chunk(
        procedural_town_x,
        procedural_town_y,
    )
    bounty_context = procedural_town_game.bounty_board_context()
    assert bounty_context is not None
    assert bounty_context["town_key"] == procedural_town_game.wilderness_chunk_key(
        procedural_town_x,
        procedural_town_y,
    )
    bounty_board = procedural_town_game.ensure_bounty_board_offers(bounty_context)
    assert bounty_board is not None
    assert bounty_board["week_key"] == procedural_town_game.bounty_week_key()
    assert len(bounty_board["offers"]) == 5
    primary_bounty = bounty_board["offers"][0]
    assert procedural_town_game.accept_bounty(primary_bounty)
    assert not procedural_town_game.accept_bounty(primary_bounty)
    for extra_bounty in bounty_board["offers"][1:3]:
        assert procedural_town_game.accept_bounty(extra_bounty)
    assert procedural_town_game.active_bounty_count() == 3
    assert not procedural_town_game.accept_bounty(bounty_board["offers"][3])
    bounty_overview = "\n".join(procedural_town_game.active_bounty_overview_lines())
    assert "Active: 3/3" in bounty_overview
    assert (
        f"Chunk ({primary_bounty['chunk_x']},{primary_bounty['chunk_y']})"
        in bounty_overview
    )
    captured_adventure_items = []
    original_vertical_panel_select = procedural_town_game.vertical_panel_select

    def capture_adventure_menu(title, items, *args, **kwargs):
        if title == "Adventure":
            captured_adventure_items.extend(items)
        return MenuItem(label="Back", value=farmstead_main.MENU_BACK, enabled=True)

    procedural_town_game.vertical_panel_select = capture_adventure_menu
    try:
        assert procedural_town_game.show_combat_status_menu() == farmstead_main.MENU_BACK
    finally:
        procedural_town_game.vertical_panel_select = original_vertical_panel_select
    assert any(
        item.label == "Bounties" and "3/3" in str(item.hint)
        for item in captured_adventure_items
    )
    bounty_chunk_x = int(primary_bounty["chunk_x"])
    bounty_chunk_y = int(primary_bounty["chunk_y"])
    assert procedural_town_game.overworld_chunk_preview_symbol(
        bounty_chunk_x,
        bounty_chunk_y,
    ) == "!"
    assert any(
        "Bounty target" in line
        for line in procedural_town_game.overworld_chunk_detail_lines(
            bounty_chunk_x,
            bounty_chunk_y,
        )
    )
    procedural_town_game.set_wilderness_chunk(bounty_chunk_x, bounty_chunk_y)
    bounty_targets = procedural_town_game.get_bounty_targets_for_chunk(
        bounty_chunk_x,
        bounty_chunk_y,
    )
    primary_target = next(
        target
        for target in bounty_targets
        if target["id"] == primary_bounty["id"]
    )
    assert primary_target["target_x"] >= 0
    assert primary_target["target_y"] >= 0
    assert procedural_town_game.bounty_target_at(
        primary_target["x"],
        primary_target["y"],
    )["id"] == primary_bounty["id"]
    assert not procedural_town_game.passable(
        primary_target["x"],
        primary_target["y"],
    )
    assert "bounty combat" in procedural_town_game.interaction_hint(
        primary_target["x"],
        primary_target["y"],
    ).lower()
    procedural_town_game.mark_bounty_target_defeated(primary_target)
    assert procedural_town_game.state.active_bounties[
        primary_bounty["id"]
    ]["status"] == "defeated"
    assert "Ready to turn in" in "\n".join(
        procedural_town_game.active_bounty_overview_lines()
    )
    reward_money = int(primary_bounty["reward_money"])
    reward_items = dict(primary_bounty["reward_items"])
    money_before_bounty_turn_in = procedural_town_game.state.money
    inventory_before_bounty_turn_in = {
        item: int(procedural_town_game.state.inventory.get(item, 0))
        for item in reward_items
    }
    procedural_town_game.set_wilderness_chunk(
        procedural_town_x,
        procedural_town_y,
    )
    assert procedural_town_game.claim_bounty_reward(primary_bounty["id"])
    assert procedural_town_game.state.money == money_before_bounty_turn_in + reward_money
    for item, quantity in reward_items.items():
        assert procedural_town_game.state.inventory.get(item, 0) == (
            inventory_before_bounty_turn_in[item] + quantity
        )
    assert primary_bounty["id"] not in procedural_town_game.state.active_bounties
    assert procedural_town_game.state.completed_bounty_log[-1]["id"] == primary_bounty["id"]
    look_clear_calls = 0
    original_clear_screen = farmstead_main.clear_screen

    def tracked_clear_screen():
        nonlocal look_clear_calls
        look_clear_calls += 1

    farmstead_main.clear_screen = tracked_clear_screen
    try:
        procedural_town_game._terminal_prepared = True
        procedural_town_game._force_full_redraw = True
        with contextlib.redirect_stdout(io.StringIO()):
            procedural_town_game.draw_with_look_cursor(
                procedural_town_game.state.player_x,
                procedural_town_game.state.player_y,
            )
    finally:
        farmstead_main.clear_screen = original_clear_screen
    assert look_clear_calls == 0
    procedural_runtime_population = (
        procedural_town_game.procedural_settlement_population(
            procedural_town_x,
            procedural_town_y,
        )
    )
    assert procedural_runtime_population
    assert procedural_town_plan["discovered"] is True
    assert procedural_town_game.location_label() == procedural_town_plan["name"]
    procedural_identity = procedural_town_game.procedural_town_identity(
        procedural_town_plan
    )
    assert {
        "industry",
        "architecture",
        "custom",
        "food",
        "founding",
        "motto",
        "concern",
        "story_item",
        "exports",
        "imports",
        "festival_name",
        "story_stages",
    }.issubset(procedural_identity)
    assert procedural_town_game.procedural_town_reputation(procedural_town_plan) >= 2
    render_lookup_calls = {
        "civic": 0,
        "followers": 0,
    }
    original_civic_overlay_lookup = (
        procedural_town_game.procedural_town_civic_overlay_lookup
    )
    original_follower_position_lookup = (
        procedural_town_game.travel_follower_position_lookup
    )

    def tracked_civic_overlay_lookup():
        render_lookup_calls["civic"] += 1
        return original_civic_overlay_lookup()

    def tracked_follower_position_lookup(map_width=None, map_height=None):
        render_lookup_calls["followers"] += 1
        return original_follower_position_lookup(map_width, map_height)

    procedural_town_game.procedural_town_civic_overlay_lookup = (
        tracked_civic_overlay_lookup
    )
    procedural_town_game.travel_follower_position_lookup = (
        tracked_follower_position_lookup
    )
    try:
        assert procedural_town_game.map_lines()
    finally:
        procedural_town_game.procedural_town_civic_overlay_lookup = (
            original_civic_overlay_lookup
        )
        procedural_town_game.travel_follower_position_lookup = (
            original_follower_position_lookup
        )
    assert render_lookup_calls == {
        "civic": 1,
        "followers": 1,
    }

    runtime_destination_calls = 0
    original_runtime_destination = (
        procedural_town_game.procedural_town_resident_runtime_destination
    )

    def tracked_runtime_destination(resident, plan, context=None, event=None):
        nonlocal runtime_destination_calls
        runtime_destination_calls += 1
        return original_runtime_destination(resident, plan, context, event)

    procedural_town_game.procedural_town_resident_runtime_destination = (
        tracked_runtime_destination
    )
    try:
        procedural_town_game.ensure_procedural_town_resident_runtime(
            force_reanchor=True
        )
        calls_after_reanchor = runtime_destination_calls
        assert calls_after_reanchor > 0
        procedural_town_game.ensure_procedural_town_resident_runtime()
        assert runtime_destination_calls == calls_after_reanchor
    finally:
        procedural_town_game.procedural_town_resident_runtime_destination = (
            original_runtime_destination
        )
    assert procedural_town_game.procedural_town_resident_runtime_activity(
        "building:home", "outdoor", "sleeping at home", "late"
    ) == "walking home to sleep"
    fixture_test_grid = [["#" for _ in range(9)] for _ in range(7)]
    for fixture_y in range(1, 6):
        for fixture_x in range(1, 8):
            fixture_test_grid[fixture_y][fixture_x] = "."
    fixture_test_grid[3][4] = "H"
    fixture_test_grid[2][2] = "R"
    fixture_test_grid[4][4] = "|"
    book_anchors = procedural_town_game.procedural_town_fixture_interaction_anchors(
        fixture_test_grid,
        {"H"},
        "smoke:librarian",
    )
    assert set(book_anchors) == {(3, 3), (5, 3), (4, 2)}
    assert all(
        procedural_town_game.procedural_town_interior_tile_passable(
            fixture_test_grid[y][x]
        )
        for x, y in book_anchors
    )
    assert procedural_town_game.procedural_town_adjacent_fixture_symbol(
        fixture_test_grid,
        (3, 3),
        {"H"},
    ) == "H"
    assert procedural_town_game.procedural_town_face_adjacent_fixture(
        fixture_test_grid,
        (3, 3),
        {"H"},
    ) == "RIGHT"
    assert procedural_town_game.procedural_town_resident_fixture_activity(
        "H",
        "work_morning",
        "handling local research",
        {"type_id": "library"},
    ) == "reading and organizing the local shelves"
    assert procedural_town_game.procedural_town_resident_fixture_activity(
        "W",
        "work_morning",
        "tending patients",
        {"type_id": "clinic"},
    ) == "checking remedies and treatment supplies"
    fixture_resident = {
        "id": "fixture-resident",
        "role": "Settler",
        "home_building_id": "fixture-home",
    }
    fixture_home = {"id": "fixture-home", "type_id": "home"}
    assert {"b", "B", "I", "J", "K"}.issubset(
        procedural_town_game.procedural_town_resident_fixture_symbols(
            fixture_resident,
            fixture_home,
            "late",
            "sleeping at home",
        )
    )
    fixture_librarian = {"id": "fixture-archivist", "role": "Archivist"}
    assert {"H", "i", "l", "L"}.issubset(
        procedural_town_game.procedural_town_resident_fixture_symbols(
            fixture_librarian,
            {"id": "fixture-library", "type_id": "library"},
            "work_morning",
            "organizing research books",
        )
    )
    assert procedural_town_game.procedural_town_resident_fixture_symbols(
        {"id": "fixture-shopkeeper", "role": "Shopkeeper"},
        {"id": "fixture-store", "type_id": "general_store"},
        "work_morning",
        "checking store stock",
    ) == {"&"}
    original_runtime_hour = procedural_town_game.state.hour
    procedural_town_game.state.hour = 23
    procedural_town_game.ensure_procedural_town_resident_runtime(
        force_reanchor=True
    )
    assert all(
        str(resident.get("runtime_location", ""))
        == f"building:{resident.get('home_building_id')}"
        for resident in procedural_runtime_population["residents"].values()
        if (
            not resident.get("deceased")
            and resident.get("home_building_id")
            and str(resident.get("id", ""))
            not in procedural_town_game.regional_town_life_state().get(
                "resident_trips", {}
            )
        )
    )
    procedural_town_game.state.hour = original_runtime_hour
    procedural_town_game.ensure_procedural_town_resident_runtime(
        force_reanchor=True
    )

    procedural_resident_ids = set(
        procedural_runtime_population["residents"]
    )
    assert all(
        isinstance(resident.get("social_connections"), dict)
        for resident in procedural_runtime_population["residents"].values()
    )
    assert all(
        linked_id in procedural_resident_ids
        for resident in procedural_runtime_population["residents"].values()
        for connection_ids in resident["social_connections"].values()
        for linked_id in (
            connection_ids
            if isinstance(connection_ids, list)
            else [connection_ids]
        )
        if linked_id
    )
    assert procedural_town_game.wilderness_chunk_has_safe_waypoint(
        procedural_town_x,
        procedural_town_y,
    )
    assert procedural_town_game.overworld_chunk_preview_symbol(
        procedural_town_x,
        procedural_town_y,
    ) == procedural_towns.PROCEDURAL_TOWN_OVERWORLD_SYMBOL
    assert any(
        procedural_town_plan["name"] in line
        for line in procedural_town_game.overworld_chunk_detail_lines(
            procedural_town_x,
            procedural_town_y,
        )
    )
    procedural_town_game.state.hour = 10
    streamed_resident_positions = procedural_town_game.procedural_town_stream_resident_lookup(
        procedural_town_x,
        procedural_town_y,
    )
    assert streamed_resident_positions
    runtime_resident_positions = procedural_town_game.procedural_town_resident_position_lookup()
    assert runtime_resident_positions
    assert (
        procedural_town_game.procedural_town_resident_position_lookup()
        is runtime_resident_positions
    )
    assert set(streamed_resident_positions) == set(runtime_resident_positions)
    original_town_position = (
        procedural_town_game.state.player_x,
        procedural_town_game.state.player_y,
    )
    open_neighbor = next(
        (
            (dx, dy)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if procedural_town_game.passable(
                original_town_position[0] + dx,
                original_town_position[1] + dy,
            )
        ),
        None,
    )
    assert open_neighbor is not None
    procedural_town_game.move(*open_neighbor)
    assert (
        procedural_town_game.state.player_x,
        procedural_town_game.state.player_y,
    ) != original_town_position
    runtime_resident_positions = (
        procedural_town_game.procedural_town_resident_position_lookup()
    )
    runtime_resident_position, runtime_resident = next(
        iter(runtime_resident_positions.items())
    )
    assert procedural_town_game.town_npc_at(*runtime_resident_position) is runtime_resident
    assert procedural_town_game.passable(*runtime_resident_position)
    assert runtime_resident["name"] in procedural_town_game.interaction_hint(
        *runtime_resident_position
    )
    procedural_town_game.state.hour = 12
    procedural_town_game.update_procedural_town_residents(force_reanchor=True)
    lunch_residents = [
        resident
        for resident in procedural_runtime_population["residents"].values()
        if resident["runtime_location"] == "outdoor"
    ]
    lunch_targets = [
        (int(resident["runtime_target_x"]), int(resident["runtime_target_y"]))
        for resident in lunch_residents
    ]
    assert len(lunch_targets) == len(set(lunch_targets))
    residents_before_walking = {
        resident["id"]: (
            resident["runtime_x"],
            resident["runtime_y"],
        )
        for resident in procedural_runtime_population["residents"].values()
        if resident["runtime_location"] == "outdoor"
    }
    movement_observed = False
    previous_walking_positions = dict(residents_before_walking)
    for _ in range(30):
        procedural_town_game.update_procedural_town_residents()
        current_walking_positions = {
            resident["id"]: (
                resident["runtime_x"],
                resident["runtime_y"],
            )
            for resident in procedural_runtime_population["residents"].values()
            if resident["runtime_location"] == "outdoor"
        }
        if any(
            previous_walking_positions.get(resident_id)
            != current_walking_positions.get(resident_id)
            for resident_id in current_walking_positions
        ):
            movement_observed = True
        previous_walking_positions = current_walking_positions
    residents_after_walking = {
        resident["id"]: (
            resident["runtime_x"],
            resident["runtime_y"],
        )
        for resident in procedural_runtime_population["residents"].values()
        if resident["runtime_location"] == "outdoor"
    }
    assert movement_observed
    walking_positions = list(residents_after_walking.values())
    assert max(
        sum(
            abs(x - other_x) + abs(y - other_y) <= 2
            for other_x, other_y in walking_positions
        )
        for x, y in walking_positions
    ) <= 4
    assert any(
        resident["runtime_steps_today"] > 0
        for resident in procedural_runtime_population["residents"].values()
    )
    procedural_town_game.state.hour = 14
    procedural_town_game.ensure_procedural_town_resident_runtime()
    commuter = next(
        resident
        for resident in procedural_runtime_population["residents"].values()
        if resident.get("workplace_building_id")
        and resident.get("runtime_schedule_location")
        == f"building:{resident.get('workplace_building_id')}"
        and resident.get("runtime_transition") == "approach"
    )
    commuter_workplace = procedural_town_plan["buildings"][str(commuter["workplace_building_id"])]
    assert commuter["runtime_location"] == "outdoor"
    assert commuter["runtime_transition"] == "approach"
    assert (commuter["runtime_target_x"], commuter["runtime_target_y"]) == (
        commuter_workplace["access_x"],
        commuter_workplace["access_y"],
    )
    for _ in range(180):
        procedural_town_game.update_procedural_town_residents()
        if commuter["runtime_location"] == f"building:{commuter_workplace['id']}":
            break
    assert commuter["runtime_location"] == f"building:{commuter_workplace['id']}"
    assert commuter["runtime_transition"] == "settle"
    commuter_landing = procedural_town_game.procedural_town_interior_entry_landing(
        procedural_town_game.procedural_town_interior_map(commuter_workplace),
        commuter_workplace,
    )
    assert (commuter["runtime_x"], commuter["runtime_y"]) == commuter_landing
    procedural_town_game.state.hour = 12
    procedural_town_game.update_procedural_town_residents(force_reanchor=True)
    runtime_resident = next(
        resident
        for resident in procedural_runtime_population["residents"].values()
        if resident["runtime_location"] == "outdoor"
    )
    resident_menu_labels = [
        item.label
        for item in procedural_town_game.procedural_town_resident_menu_items(
            runtime_resident
        )
    ]
    assert all(label in resident_menu_labels for label in ["Talk", "Profile", "Status", "Back"])
    assert not {"Give Gift", "Ask Rumor", "Request", "Courtship", "Propose"}.intersection(resident_menu_labels)
    assert resident_menu_labels[-1] == "Back"
    liked_gift = runtime_resident["likes"][0]
    procedural_town_game.state.inventory[liked_gift] = 1
    relationship_before_gift = runtime_resident["relationship"]
    gift_connection_ids = list(
        runtime_resident["social_connections"].get("family", [])
    )
    if runtime_resident["social_connections"].get("friend"):
        gift_connection_ids.append(
            runtime_resident["social_connections"]["friend"]
        )
    gift_connection_relationships = {
        resident_id: procedural_runtime_population["residents"][resident_id]["relationship"]
        for resident_id in gift_connection_ids
    }
    assert procedural_town_game.give_procedural_town_resident_gift(
        runtime_resident,
        liked_gift,
    )
    assert runtime_resident["relationship"] == relationship_before_gift + 8
    assert runtime_resident["last_gift_day"]
    assert liked_gift in runtime_resident["recent_gifts"]
    assert any(
        procedural_runtime_population["residents"][resident_id]["relationship"]
        == relationship + 1
        for resident_id, relationship in gift_connection_relationships.items()
    )
    runtime_conversation = procedural_town_game.procedural_settlement_conversation(
        procedural_town_x,
        procedural_town_y,
        runtime_resident["id"],
    )
    assert runtime_conversation["text"]
    assert procedural_town_game.procedural_town_primary_dialogue_topic(
        runtime_resident,
        procedural_town_plan,
    ) in procedural_town_game.procedural_settlement_dialogue_topics(
        procedural_town_x,
        procedural_town_y,
        runtime_resident["id"],
    )
    available_resident_topics = procedural_town_game.procedural_settlement_dialogue_topics(
        procedural_town_x,
        procedural_town_y,
        runtime_resident["id"],
    )
    topic_conversations = {
        topic: procedural_town_game.procedural_settlement_conversation(
            procedural_town_x,
            procedural_town_y,
            runtime_resident["id"],
            topic=topic,
            remember=False,
        )["text"]
        for topic in ("chat", "work", "home", "settlement", "weather")
        if topic in available_resident_topics
    }
    assert len(set(topic_conversations.values())) >= 4
    assert all(len(text) >= 35 for text in topic_conversations.values())
    assert all(
        procedural_town_game.procedural_town_service_kind(building["type_id"])
        != "information"
        for building in procedural_town_plan["buildings"].values()
    )
    town_hall_building = next(
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] == "town_hall"
    )
    procedural_town_game.state.hour = 10
    procedural_town_game.update_procedural_town_residents(force_reanchor=True)
    hall_hours = procedural_town_game.procedural_town_building_hours(town_hall_building)
    assert hall_hours == (8, 17)
    assert procedural_town_game.procedural_town_building_is_open(town_hall_building)
    assert any("Hours:" in line for line in procedural_town_game.procedural_town_building_lines(town_hall_building))
    assert procedural_town_game.procedural_town_building_door_at(
        town_hall_building["door_x"],
        town_hall_building["door_y"],
    ) == town_hall_building
    procedural_town_game.state.hour = 2
    assert not procedural_town_game.procedural_town_building_is_open(town_hall_building)
    assert not procedural_town_game.enter_procedural_town_building(town_hall_building)
    assert procedural_town_game.state.location == "Wilderness"
    assert "opens at" in procedural_town_game.state.message.lower()
    procedural_town_game.state.hour = 10
    assert procedural_town_game.enter_procedural_town_building(town_hall_building)
    assert procedural_town_game.on_procedural_town_interior()
    assert procedural_town_game.active_map()
    assert procedural_town_game.current_procedural_town_building()["id"] == town_hall_building["id"]
    if not procedural_town_game.procedural_town_resident_position_lookup():
        assert procedural_town_game.procedural_town_building_floor_count(
            procedural_town_plan,
            town_hall_building,
        ) > 1
        assert procedural_town_game.change_procedural_town_building_floor(1)
    hall_resident_lookup = procedural_town_game.procedural_town_resident_position_lookup()
    assert hall_resident_lookup
    hall_worker = next(
        resident
        for resident in hall_resident_lookup.values()
        if str(resident.get("workplace_building_id", "")) == str(town_hall_building["id"])
    )
    assert any(
        item.value == "service"
        for item in procedural_town_game.procedural_town_resident_menu_items(hall_worker)
    )
    assert {
        "ProceduralSettlementInterior", "WildernessOutpost", "WildernessStructure"
    }.issubset(procedural_town_game.travel_follower_allowed_locations("companion:mira_seed"))
    hall_grid = procedural_town_game.active_map()
    room_door = next(
        (x, y)
        for y, row in enumerate(hall_grid)
        for x, tile in enumerate(row)
        if procedural_town_game.procedural_town_interior_tile_passable(tile)
        and (x, y) != (procedural_town_game.state.player_x, procedural_town_game.state.player_y)
        and (x, y) not in hall_resident_lookup
    )
    original_room_door_tile = hall_grid[room_door[1]][room_door[0]]
    hall_grid[room_door[1]][room_door[0]] = "_"
    door_test_resident = {"runtime_x": 1, "runtime_y": 1, "runtime_blocked_ticks": 2}
    assert procedural_town_game.procedural_town_resident_open_door_for_step(
        door_test_resident, *room_door
    )
    assert hall_grid[room_door[1]][room_door[0]] == "|"
    door_test_resident["runtime_x"], door_test_resident["runtime_y"] = len(hall_grid[0]) - 2, len(hall_grid) - 2
    procedural_town_game.procedural_town_resident_close_used_door(door_test_resident, set())
    assert hall_grid[room_door[1]][room_door[0]] == "_"
    hall_grid[room_door[1]][room_door[0]] = original_room_door_tile
    procedural_town_game.state.current_procedural_building_floor = 0
    ground_hall_grid = procedural_town_game.procedural_town_interior_map(town_hall_building)
    hall_landing = procedural_town_game.procedural_town_interior_entry_landing(
        ground_hall_grid, town_hall_building
    )
    procedural_town_game.state.player_x, procedural_town_game.state.player_y = next(
        (x, y)
        for y, row in enumerate(ground_hall_grid)
        for x, tile in enumerate(row)
        if procedural_town_game.procedural_town_interior_tile_passable(tile)
        and abs(x - hall_landing[0]) + abs(y - hall_landing[1]) > 4
    )
    procedural_town_game.state.hour = 21
    procedural_town_game.ensure_procedural_town_resident_runtime()
    assert hall_worker["runtime_transition"] == "leave"
    for _ in range(180):
        procedural_town_game.update_procedural_town_residents()
        if hall_worker["runtime_location"] == "outdoor":
            break
    assert hall_worker["runtime_location"] == "outdoor"
    assert (hall_worker["runtime_x"], hall_worker["runtime_y"]) == (
        town_hall_building["access_x"], town_hall_building["access_y"]
    )
    procedural_town_game.state.hour = 10
    procedural_town_game.update_procedural_town_residents(force_reanchor=True)
    assert procedural_town_game.exit_procedural_town_building()
    assert procedural_town_game.state.location == "Wilderness"
    clinic_building = next(
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] == "clinic"
    )
    procedural_town_game.state.money = 120
    procedural_town_game.state.stamina = 10
    procedural_town_game.state.combat_current_hp = 1
    assert procedural_town_game.enter_procedural_town_building(clinic_building)
    assert any(
        "p" in row or "," in row
        for row in procedural_town_game.active_map()
    )
    color_lookup_calls = 0
    color_key_calls = 0
    original_color_lookup = procedural_town_game.procedural_town_custom_tile_color_lookup
    original_color_key = procedural_town_game.procedural_town_custom_tile_color_key

    def tracked_color_lookup(floor=None):
        nonlocal color_lookup_calls
        color_lookup_calls += 1
        return original_color_lookup(floor)

    def tracked_color_key(x, y, floor=None):
        nonlocal color_key_calls
        color_key_calls += 1
        return original_color_key(x, y, floor)

    procedural_town_game.procedural_town_custom_tile_color_lookup = tracked_color_lookup
    procedural_town_game.procedural_town_custom_tile_color_key = tracked_color_key
    try:
        assert procedural_town_game.map_lines()
    finally:
        procedural_town_game.procedural_town_custom_tile_color_lookup = original_color_lookup
        procedural_town_game.procedural_town_custom_tile_color_key = original_color_key
    assert color_lookup_calls == 1
    assert color_key_calls == 0
    local_service_buildings = [
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] in procedural_towns.PROCEDURAL_LOCAL_STOCK
    ]
    assert local_service_buildings
    staffed_store = next(
        building for building in local_service_buildings
        if building["type_id"] == "general_store"
    )
    procedural_town_game.state.location = procedural_towns.PROCEDURAL_TOWN_INTERIOR_LOCATION
    procedural_town_game.state.current_procedural_settlement_key = (
        f"{procedural_town_plan['chunk_x']},{procedural_town_plan['chunk_y']}"
    )
    procedural_town_game.state.current_procedural_building_id = str(staffed_store["id"])
    procedural_town_game.state.current_procedural_building_floor = 0
    procedural_town_game.state.hour = 10
    procedural_town_game.update_procedural_town_residents(force_reanchor=True)
    staffed_store_grid = procedural_town_game.procedural_town_interior_map(staffed_store)
    service_counters = {
        (x, y)
        for y, row in enumerate(staffed_store_grid)
        for x, tile in enumerate(row)
        if tile == "&"
    }
    store_staff = [
        resident
        for resident in procedural_town_game.procedural_town_resident_position_lookup().values()
        if str(resident.get("workplace_building_id", "")) == str(staffed_store["id"])
        and str(resident.get("role", "")) in {"Shopkeeper", "Merchant"}
    ]
    assert service_counters and store_staff
    assert any(
        abs(int(worker["runtime_x"]) - counter_x) + abs(int(worker["runtime_y"]) - counter_y) == 1
        for worker in store_staff
        for counter_x, counter_y in service_counters
    ), (
        [(worker.get("role"), worker.get("runtime_x"), worker.get("runtime_y")) for worker in store_staff],
        sorted(service_counters),
    )
    assert any(
        str(worker.get("runtime_fixture_symbol", "")) in {"&", "$", "V"}
        for worker in store_staff
    )
    assert any(
        "service" in str(worker.get("runtime_activity", "")).lower()
        or "display" in str(worker.get("runtime_activity", "")).lower()
        for worker in store_staff
    )
    assert any(
        item.value == "service"
        for item in procedural_town_game.procedural_town_resident_menu_items(store_staff[0])
    )
    procedural_interior_buildings = [
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] not in procedural_towns.PROCEDURAL_TOWN_OPEN_BUILDINGS
    ]
    assert procedural_interior_buildings
    for candidate_x, candidate_y in procedural_town_game.procedural_town_interior_resident_candidates():
        assert not (candidate_y >= 18 and candidate_x in {31, 32, 33})
    procedural_blocking_tiles = procedural_town_game.procedural_town_interior_blocking_tiles()
    assert " " in procedural_blocking_tiles
    assert not procedural_town_game.procedural_town_interior_tile_passable(" ")
    procedural_interior_community = procedural_town_game.ensure_procedural_town_community(
        procedural_town_plan
    )
    expected_tiles_by_type = {
        "general_store": {"&", "$", "s"},
        "market_stall": {"&", "$", "s"},
        "inn": {"&", "$", "b", "f"},
        "home": {"&", "b", "f"},
        "clinic": {"&", "+", "b"},
        "library": {"&", "l", "P"},
        "carpenter": {"&", "w", "a", "x"},
        "workshop": {"&", "w", "a", "x"},
        "town_hall": {"&", "d", "P"},
    }
    procedural_layout_types = tuple(expected_tiles_by_type)
    assert not procedural_furnishing.validate_furnishing_kits()

    def assert_functional_room_furnishings(grid, room_plan):
        def room_cells(room, symbol):
            x1, y1, x2, y2 = room["rect"]
            return [
                (x, y)
                for y in range(y1 + 1, y2)
                for x in range(x1 + 1, x2)
                if grid[y][x] == symbol
            ]

        def adjacent(first, second):
            return any(
                abs(x1 - x2) + abs(y1 - y2) == 1
                for x1, y1 in first
                for x2, y2 in second
            )

        for room in room_plan["rooms"]:
            role = str(room.get("role", ""))
            x1, y1, x2, y2 = room["rect"]
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            assert grid[center_y][center_x] in {".", ",", "_", "|", "<", ">"}
            if str(room.get("occupancy_kind", "")) in {"resident", "guest"}:
                assert room_cells(room, "b")
            if role == "kitchen":
                assert room_cells(room, "f")
            if role in {"common", "common_room", "reading", "council", "meeting"}:
                tables, chairs = room_cells(room, "t"), room_cells(room, "c")
                assert tables and chairs and adjacent(tables, chairs)
            if role in {"study", "office"}:
                desks, chairs = room_cells(room, "d"), room_cells(room, "c")
                assert desks and chairs and adjacent(desks, chairs)

    cross_type_variant_signatures = set()
    for procedural_layout_type in procedural_layout_types:
        variant_probe_building = {
            "id": f"smoke:{procedural_layout_type}",
            "type_id": procedural_layout_type,
            "room_program_variant": 1,
        }
        floor_count = 2 if procedural_layout_type in {"home", "inn"} else 1
        variant_probe_grids = []
        for layout_variant in range(4):
            catalog_placements = []
            variant_probe_grids.append(
                procedural_town_game.procedural_town_generated_ground_floor_map(
                procedural_town_plan,
                variant_probe_building,
                floor_count,
                None,
                None,
                procedural_interior_community,
                layout_variant,
                layout_variant,
                catalog_placements,
            )
            )
            assert catalog_placements
            assert all(
                str(placement.get("name", "")) in furniture_catalog.FURNITURE_CATALOG_DATA
                and placement.get("cells")
                and str(placement.get("room_role", ""))
                for placement in catalog_placements
            )
        variant_probe_signatures = {
            tuple(
                "".join("." if tile != " " else " " for tile in row)
                for row in variant_grid
            )
            for variant_grid in variant_probe_grids
        }
        assert len(variant_probe_signatures) == 4, (
            f"{procedural_layout_type} procedural layouts do not have four distinct plans"
        )
        cross_type_variant_signatures.update(variant_probe_signatures)
        for layout_variant, variant_grid in enumerate(variant_probe_grids):
            variant_symbols = set("".join("".join(row) for row in variant_grid))
            assert expected_tiles_by_type[procedural_layout_type] <= variant_symbols
            assert sum(row.count("D") for row in variant_grid) == 1
            assert sum(row.count("&") for row in variant_grid) == 1
            room_plan = procedural_interiors.procedural_interior_room_plan(
                procedural_layout_type,
                layout_variant,
                floor_count,
                0,
            )
            assert not room_plan["validation"], (
                procedural_layout_type,
                layout_variant,
                room_plan["validation"],
            )
            room_ids = {str(room["id"]) for room in room_plan["rooms"]}
            assert len(room_ids) == len(room_plan["rooms"])
            assert len({str(room["size"]) for room in room_plan["rooms"]}) >= 3
            assert_functional_room_furnishings(variant_grid, room_plan)
        program_signatures = set()
        program_room_counts = []
        for program_variant in range(3):
            program_probe_building = dict(
                variant_probe_building,
                id=f"smoke:{procedural_layout_type}:program:{program_variant}",
                room_program_variant=program_variant,
            )
            for program_layout_variant in range(4):
                program_grid = procedural_town_game.procedural_town_generated_ground_floor_map(
                    procedural_town_plan,
                    program_probe_building,
                    floor_count,
                    None,
                    None,
                    procedural_interior_community,
                    program_layout_variant,
                    program_layout_variant,
                )
                program_plan = procedural_interiors.procedural_interior_room_plan(
                    procedural_layout_type,
                    program_layout_variant,
                    floor_count,
                    0,
                    None,
                    program_variant,
                )
                assert not program_plan["validation"], (
                    procedural_layout_type,
                    program_variant,
                    program_layout_variant,
                    program_plan["validation"],
                )
                assert program_plan["program_name"] == (
                    "Compact", "Standard", "Expanded"
                )[program_variant]
                assert_functional_room_furnishings(program_grid, program_plan)
                if procedural_layout_type in {"home", "inn"}:
                    program_upper_grid = (
                        procedural_town_game.procedural_town_generated_upper_floor_map(
                            procedural_town_plan,
                            program_probe_building,
                            1,
                            2,
                            program_layout_variant,
                        )
                    )
                    program_upper_plan = procedural_interiors.procedural_interior_room_plan(
                        procedural_layout_type,
                        program_layout_variant,
                        2,
                        1,
                        None,
                        program_variant,
                    )
                    assert not program_upper_plan["validation"]
                    assert_functional_room_furnishings(
                        program_upper_grid,
                        program_upper_plan,
                    )
                if program_layout_variant == 0:
                    program_room_counts.append(len(program_plan["rooms"]))
                    program_signatures.add(tuple(
                        "".join("." if tile != " " else " " for tile in row)
                        for row in program_grid
                    ))
        assert len(program_signatures) == 3
        assert program_room_counts[0] < program_room_counts[2]
        if procedural_layout_type == "general_store":
            assert all(
                sum(row.count("_") for row in variant_grid) >= 1
                for variant_grid in variant_probe_grids
            ), "Private and service shop rooms should have meaningful doors"
        if procedural_layout_type == "home":
            for layout_variant in range(4):
                home_plan = procedural_interiors.procedural_interior_room_plan(
                    "home", layout_variant, 2, 0,
                )
                home_rooms = {str(room["id"]): room for room in home_plan["rooms"]}
                assert home_plan["resident_capacity"] == 3
                assert home_rooms["primary_bath"]["parent"] == "primary"
                assert home_rooms["primary_bath"]["connection"] == "direct"
                assert home_rooms["primary"]["capacity"] == 2
                assert home_rooms["bedroom_2"]["capacity"] == 1
                adaptive_rooms = {"floor:0:study": "nursery"}
                adapted_plan = procedural_interiors.procedural_interior_room_plan(
                    "home", layout_variant, 1, 0, adaptive_rooms,
                )
                adapted_study = next(
                    room for room in adapted_plan["rooms"] if room["id"] == "study"
                )
                assert adapted_plan["resident_capacity"] == 4
                assert adapted_study["role"] == "nursery"
                assert adapted_study["adapted_from"] == "study"
                assert adapted_study["capacity"] == 1
                adapted_grid = procedural_interiors.build_procedural_ground_floor(
                    "home",
                    layout_variant,
                    0,
                    1,
                    room_overrides=adaptive_rooms,
                )
                assert sum(row.count("b") for row in adapted_grid) == 3
                assert procedural_interiors.procedural_building_room_capacity(
                    "home", layout_variant, 1, adaptive_rooms,
                ) == 4
            assert procedural_interiors.sanitize_procedural_room_overrides({
                "floor:0:study": "bedroom",
                "floor:9:study": "nursery",
                "floor:0:kitchen": "kitchen",
            }) == {"floor:0:study": "bedroom"}
        if procedural_layout_type == "inn":
            for layout_variant, variant_grid in enumerate(variant_probe_grids):
                inn_plan = procedural_interiors.procedural_interior_room_plan(
                    "inn", layout_variant, 2, 0,
                )
                upper_grid = procedural_town_game.procedural_town_generated_upper_floor_map(
                    procedural_town_plan,
                    variant_probe_building,
                    1,
                    2,
                    layout_variant,
                )
                upper_plan = procedural_interiors.procedural_interior_room_plan(
                    "inn", layout_variant, 2, 1,
                )
                assert sum(row.count("b") for row in variant_grid) == 4
                assert sum(row.count("b") for row in upper_grid) == 6
                assert sum(row.count(">") for row in upper_grid) == 1
                assert inn_plan["guest_capacity"] == 4
                assert upper_plan["guest_capacity"] == 6
                assert all(
                    int(room["capacity"]) == 1
                    for room in (*inn_plan["rooms"], *upper_plan["rooms"])
                    if str(room.get("role")) == "guest_room"
                )
                assert procedural_interiors.procedural_building_room_capacity(
                    "inn", layout_variant, 2,
                ) == 10
    assert len(cross_type_variant_signatures) >= 24, (
        "Procedural building roles still reuse too many identical shells"
    )
    original_building_service = procedural_town_game.procedural_town_building_service
    generated_shape_signatures = set()
    generated_shape_signatures_by_type = {}
    generated_building_counts_by_type = {}
    generated_service_positions = set()
    resolved_room_container_profiles = set()
    try:
        for proc_building in procedural_interior_buildings:
            procedural_town_game.state.location = procedural_towns.PROCEDURAL_TOWN_INTERIOR_LOCATION
            procedural_town_game.state.current_procedural_settlement_key = (
                f"{procedural_town_plan['chunk_x']},{procedural_town_plan['chunk_y']}"
            )
            procedural_town_game.state.current_procedural_building_id = str(proc_building["id"])
            procedural_town_game.state.current_procedural_building_floor = 0
            display_grid = procedural_town_game.procedural_town_interior_map(proc_building)
            catalog_lookup = {}
            custom_template = procedural_town_game.procedural_town_custom_building_template(
                procedural_town_plan,
                proc_building,
            )
            property_record = (
                procedural_town_game.player_property_for_building(
                    procedural_town_plan, proc_building
                )
                if str(proc_building.get("type_id", "")) == "home"
                else None
            )
            if not custom_template and not property_record:
                furniture_scope = (
                    str(procedural_town_plan.get("id", "")),
                    str(proc_building.get("id", "")),
                    0,
                )
                catalog_lookup = procedural_town_game._procedural_town_catalog_furniture_cache.get(
                    furniture_scope, {}
                )
                assert catalog_lookup
                furniture_position, furniture_cell = next(iter(catalog_lookup.items()))
                assert furniture_cell["name"] in furniture_catalog.FURNITURE_CATALOG_DATA
                assert visible_terminal_len(
                    procedural_town_game.render_tile(
                        furniture_position[0], furniture_position[1], display_grid
                    )
                ) == 1
                furniture_description = procedural_town_game.procedural_town_interior_tile_description(
                    display_grid[furniture_position[1]][furniture_position[0]],
                    proc_building,
                    *furniture_position,
                )
                assert str(furniture_cell["name"]) in furniture_description
                assert procedural_town_game.procedural_town_interior_tile_interactable(
                    display_grid[furniture_position[1]][furniture_position[0]],
                    proc_building,
                    *furniture_position,
                )
            architecture_lines = procedural_town_game.procedural_town_modular_architecture_lines(
                procedural_town_plan,
                proc_building,
            )
            if architecture_lines:
                assert any("Architecture:" in line for line in architecture_lines)
                assert any(
                    program_name in line
                    for program_name in ("Compact", "Standard", "Expanded")
                    for line in architecture_lines
                )
                assert int(proc_building.get("room_program_variant", -1)) in {0, 1, 2}
                assert any("capacity" in line.lower() for line in architecture_lines)
                assert any(
                    "Furnishing plan:" in line and "lanes kept clear" in line
                    for line in architecture_lines
                )
                modular_anchors = procedural_town_game.procedural_town_modular_room_anchors(
                    procedural_town_plan,
                    proc_building,
                    ["public_hall"],
                )
                assert modular_anchors
                assert all(
                    procedural_town_game.procedural_town_interior_tile_passable(
                        display_grid[y][x]
                    )
                    for x, y in modular_anchors
                )
                room_fixture = next(
                    (
                        (x, y, tile, room, profile)
                        for y, row in enumerate(display_grid)
                        for x, tile in enumerate(row)
                        for room in [
                            procedural_town_game.procedural_town_room_at_position(
                                x,
                                y,
                                proc_building,
                            )
                        ]
                        if isinstance(room, dict)
                        for profile in [
                            procedural_town_game.procedural_room_container_profile(
                                str(proc_building.get("type_id", "")),
                                str(room.get("role", "")),
                                str(room.get("source_id", room.get("id", ""))),
                                tile,
                            )
                        ]
                        if profile
                    ),
                    None,
                )
                if room_fixture:
                    fixture_x, fixture_y, _tile, fixture_room, expected_profile = room_fixture
                    catalog_container = procedural_town_game.procedural_town_catalog_furniture_at(
                        fixture_x, fixture_y,
                    )
                    if isinstance(catalog_container, dict):
                        catalog_name = str(catalog_container.get("name", ""))
                        expected_profile = str(
                            data.INFRASTRUCTURE_DATA.get(catalog_name, {}).get(
                                "container_profile", expected_profile,
                            )
                        )
                    static_profile = procedural_town_game.static_container_profile_at(
                        fixture_x,
                        fixture_y,
                    )
                    assert static_profile and static_profile[0] == expected_profile
                    container_record = procedural_town_game.world_container_at(
                        fixture_x,
                        fixture_y,
                    )
                    assert container_record and container_record["profile"] == expected_profile
                    assert container_record["owner"]
                    assert procedural_town_game.world_container_at(
                        fixture_x,
                        fixture_y,
                    ) is container_record
                    assert str(fixture_room.get("id", "")).startswith("floor:")
                    resolved_room_container_profiles.add(expected_profile)
            procedural_symbols = set(
                "".join("".join(row) for row in display_grid)
            )
            for semantic_tile in procedural_symbols:
                semantic_description = (
                    procedural_town_game.procedural_town_interior_tile_description(
                        semantic_tile,
                        proc_building,
                    )
                )
                semantic_hint = (
                    procedural_town_game.procedural_town_interior_tile_hint(
                        semantic_tile,
                        proc_building,
                    )
                )
                assert len(semantic_description) >= 8
                assert "nothing here needs your attention" not in semantic_description.lower()
                assert "settlement building interior" not in semantic_description.lower()
                assert semantic_hint and "nothing" not in semantic_hint.lower()
                if semantic_tile not in {" ", "#", ".", ","}:
                    assert (
                        procedural_town_game.procedural_town_interior_tile_interactable(
                            semantic_tile,
                            proc_building,
                        )
                    )
            door_side = procedural_town_game.procedural_town_building_door_side(proc_building)
            display_doors = [
                (x, y)
                for y, row in enumerate(display_grid)
                for x, tile in enumerate(row)
                if tile == "D"
            ]
            assert display_doors
            display_door_x, display_door_y = display_doors[0]
            assert {
                "north": display_door_y == 0,
                "south": display_door_y == len(display_grid) - 1,
                "west": display_door_x == 0,
                "east": display_door_x == len(display_grid[0]) - 1,
            }[door_side]
            landing_x, landing_y = procedural_town_game.procedural_town_interior_entry_landing(
                display_grid,
                proc_building,
            )
            assert 0 <= landing_y < len(display_grid)
            assert 0 <= landing_x < len(display_grid[landing_y])
            assert display_grid[landing_y][landing_x] not in procedural_blocking_tiles
            if door_side == "north":
                grid = [row[:] for row in reversed(display_grid)]
            elif door_side == "west":
                grid = [list(row) for row in zip(*display_grid)][::-1]
            elif door_side == "east":
                grid = [list(row) for row in zip(*display_grid[::-1])]
            else:
                grid = [row[:] for row in display_grid]
            door_x = len(grid[0]) // 2
            door_y = len(grid) - 1
            procedural_town_game.state.player_x = door_x
            procedural_town_game.state.player_y = door_y - 2
            assert len(grid[0]) >= 60
            assert len(grid) >= 26
            assert grid[door_y][door_x] == "D"
            assert grid[0][0] == " "
            assert grid[door_y - 1][door_x] == ".", (
                f"{proc_building['type_id']} entrance landing is obstructed"
            )
            assert any(
                grid[y][x] == "."
                for y in range(1, 18)
                for x in range(len(grid[y]))
            ), f"{proc_building['type_id']} has no branch beyond the front room"
            assert any(
                grid[y][x] == "."
                for y in range(len(grid))
                for x in list(range(1, 24)) + list(range(41, len(grid[y]) - 1))
            ), f"{proc_building['type_id']} has no side branch beyond the front room"
            assert any(ch == " " for row in grid for ch in row), f"{proc_building['type_id']} has no exterior void"
            assert any(grid[8][x] in {"#", " "} for x in range(len(grid[8]))), (
                f"{proc_building['type_id']} still looks like a full-width spoke template"
            )
            shape_signature = tuple(
                "".join("." if ch != " " else " " for ch in row)
                for row in grid
            )
            generated_shape_signatures.add(shape_signature)
            generated_shape_signatures_by_type.setdefault(
                str(proc_building["type_id"]),
                set(),
            ).add(shape_signature)
            generated_building_counts_by_type[str(proc_building["type_id"])] = (
                generated_building_counts_by_type.get(str(proc_building["type_id"]), 0) + 1
            )
            seen = {(door_x, door_y - 2)}
            queue = deque([(door_x, door_y - 2)])
            while queue:
                x, y = queue.popleft()
                for nx, ny in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                    display_nx, display_ny = procedural_town_game.procedural_town_orient_position(
                        nx,
                        ny,
                        len(grid[0]),
                        len(grid),
                        door_side,
                    )
                    catalog_walkable = bool(
                        catalog_lookup.get((display_nx, display_ny), {}).get(
                            "walkable_kind"
                        )
                    )
                    if (
                        (nx, ny) in seen
                        or not (0 <= ny < len(grid) and 0 <= nx < len(grid[ny]))
                        or (
                            grid[ny][nx] in procedural_blocking_tiles
                            and grid[ny][nx] != "_"
                            and not catalog_walkable
                        )
                    ):
                        continue
                    seen.add((nx, ny))
                    queue.append((nx, ny))
            if str(proc_building["type_id"]) in {"general_store", "market_stall"}:
                unreachable_floor = [
                    (x, y)
                    for y, row in enumerate(grid)
                    for x, ch in enumerate(row)
                    if ch in {".", ","}
                    and (x, y) not in seen
                ]
                assert not unreachable_floor, (
                    f"{proc_building['type_id']} has unreachable room floor near "
                    f"{unreachable_floor[:3]}"
                )
            expected_tiles = expected_tiles_by_type.get(str(proc_building["type_id"]), {"&"})
            service_positions = []
            for tile in expected_tiles:
                positions = [
                    (x, y)
                    for y, row in enumerate(grid)
                    for x, ch in enumerate(row)
                    if ch == tile
                ]
                assert positions, f"{proc_building['type_id']} missing generated interior tile {tile!r}"
                if tile == "&":
                    service_positions = positions
                    assert len(positions) == 1
                assert any(
                    (x + dx, y + dy) in seen
                    for x, y in positions
                    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
                ), f"{proc_building['type_id']} tile {tile!r} is not reachable"
            passive_fixture = next(
                (
                    (x, y)
                    for y, row in enumerate(display_grid)
                    for x, tile in enumerate(row)
                    if tile not in {
                        " ", "#", ".", ",", "D", "|", "_", "<", "U", ">",
                        "&", "P",
                    }
                    and not procedural_town_game.game_table_fixture_id(tile)
                ),
                None,
            )
            if passive_fixture:
                original_show_world_container = procedural_town_game.show_world_container
                original_fixture_select = procedural_town_game.vertical_panel_select
                original_fixture_view = procedural_town_game.vertical_panel_view
                original_fixture_safe_menu = procedural_town_game.safe_menu
                procedural_town_game.show_world_container = (
                    lambda record: procedural_town_game.set_message(
                        f"Opened functional {record.get('name', 'container')}."
                    )
                )
                procedural_town_game.vertical_panel_select = lambda *args, **kwargs: MenuItem(
                    label="Back", value=data.MENU_BACK, enabled=True,
                )
                procedural_town_game.vertical_panel_view = lambda *args, **kwargs: None
                procedural_town_game.safe_menu = (
                    lambda menu_func, close_message: procedural_town_game.set_message(close_message)
                )
                try:
                    procedural_town_game.use_procedural_town_interior_action(
                        *passive_fixture
                    )
                finally:
                    procedural_town_game.show_world_container = original_show_world_container
                    procedural_town_game.vertical_panel_select = original_fixture_select
                    procedural_town_game.vertical_panel_view = original_fixture_view
                    procedural_town_game.safe_menu = original_fixture_safe_menu
                assert procedural_town_game.state.message
                assert (
                    "nothing here needs your attention"
                    not in procedural_town_game.state.message.lower()
                )
            service_calls = []
            procedural_town_game.procedural_town_building_service = (
                lambda service_building, service_calls=service_calls: service_calls.append(service_building["id"]) or True
            )
            source_x, source_y = service_positions[0]
            sx, sy = procedural_town_game.procedural_town_orient_position(
                source_x,
                source_y,
                len(grid[0]),
                len(grid),
                door_side,
            )
            generated_service_positions.add((sx, sy))
            procedural_town_game.use_procedural_town_interior_action(sx, sy)
            assert service_calls == [proc_building["id"]]
    finally:
        procedural_town_game.procedural_town_building_service = original_building_service
    assert len(generated_shape_signatures) >= 4
    if generated_building_counts_by_type.get("home", 0) >= 2:
        assert len(generated_shape_signatures_by_type.get("home", set())) >= 2
    assert any(
        len(signatures) >= 2
        for type_id, signatures in generated_shape_signatures_by_type.items()
        if generated_building_counts_by_type.get(type_id, 0) >= 2
    )
    assert len(generated_service_positions) >= 2
    assert len(resolved_room_container_profiles) >= 3
    progression_probe = next(
        resident
        for resident in procedural_town_game.procedural_settlement_residents(
            int(procedural_town_plan["chunk_x"]),
            int(procedural_town_plan["chunk_y"]),
        )
        if procedural_town_game.npc_adventure_eligible(resident)
    )
    progression_record = procedural_town_game.npc_progression_record(progression_probe)
    assert progression_record["level"] == 1
    procedural_town_game.award_npc_adventure_xp(progression_probe, 300)
    assert progression_record["level"] >= 3
    assert progression_record["gear_tier"] >= 1
    assert progression_record["weapon"].startswith("Tempered ")
    progression_lines = procedural_town_game.npc_adventure_profile_lines(
        progression_probe
    )
    assert any("Regional experience" in line for line in progression_lines)
    adventure_destination = {
        "id": "adventure-test",
        "name": "Distant Test Camp",
        "kind": "outpost",
        "chunk_x": int(procedural_town_plan["chunk_x"]) + 4,
        "chunk_y": int(procedural_town_plan["chunk_y"]) + 2,
    }
    adventure_route = {
        "travel_days": 2,
        "distance_chunks": 6,
        "route_condition": "Hazardous",
    }
    adventure_trip = procedural_town_game.npc_adventure_prepare_trip(
        progression_probe,
        adventure_destination,
        adventure_route,
        origin=(
            int(procedural_town_plan["chunk_x"]),
            int(procedural_town_plan["chunk_y"]),
        ),
        origin_name=str(procedural_town_plan["name"]),
        generated=True,
    )
    adventure_path = procedural_town_game.npc_adventure_route_chunks(
        adventure_trip,
        str(progression_probe["id"]),
    )
    assert adventure_path[0] == (
        adventure_destination["chunk_x"],
        adventure_destination["chunk_y"],
    )
    assert adventure_path[-1] == (
        int(procedural_town_plan["chunk_x"]),
        int(procedural_town_plan["chunk_y"]),
    )
    journeys_before = int(progression_record["journeys"])
    outcome = procedural_town_game.resolve_npc_adventure_trip(
        progression_probe,
        adventure_trip,
    )
    assert outcome
    assert int(progression_record["journeys"]) == journeys_before + 1
    xp_after_resolution = int(progression_record["xp"])
    procedural_town_game.resolve_npc_adventure_trip(
        progression_probe,
        adventure_trip,
    )
    assert int(progression_record["xp"]) == xp_after_resolution
    progression_state_probe = GameState(
        regional_town_life={
            "npc_progression": {
                "resident:test": {
                    **progression_record,
                    "history": ["A" * 300],
                }
            },
            "resident_trips": {
                "resident:test": {
                    **adventure_trip,
                    "danger": 999,
                }
            },
            "npc_adventure_checks": {"4,2": 18},
        }
    )
    saved_progression = progression_state_probe.regional_town_life[
        "npc_progression"
    ]["resident:test"]
    saved_trip = progression_state_probe.regional_town_life[
        "resident_trips"
    ]["resident:test"]
    assert saved_progression["level"] == progression_record["level"]
    assert len(saved_progression["history"][0]) == 240
    assert saved_trip["trip_kind"] == "regional_adventure"
    assert saved_trip["danger"] == 100
    assert saved_trip["generated_resident"] is True
    assert all(
        procedural_town_game.procedural_town_local_stock(building)
        for building in local_service_buildings
    )
    market_profile = procedural_town_game.procedural_town_market_profile(
        procedural_town_plan
    )
    assert market_profile["surplus"] in procedural_identity["exports"]
    assert (
        market_profile["demand"] in procedural_identity["imports"]
        or market_profile["demand"] in {"Wood", "Cave Herbs"}
    )
    general_store_building = next(
        building
        for building in local_service_buildings
        if building["type_id"] == "general_store"
    )
    stock_entry = procedural_town_game.procedural_town_local_stock(
        general_store_building
    )[0]
    stock_remaining_before = stock_entry["remaining"]
    assert stock_remaining_before >= 2
    procedural_town_game.state.money = 2000
    money_before_purchase = procedural_town_game.state.money
    inventory_before_purchase = procedural_town_game.state.inventory.get(
        stock_entry["item"],
        0,
    )
    reputation_before_purchase = procedural_town_game.procedural_town_reputation()
    assert procedural_town_game.purchase_procedural_town_stock(
        general_store_building,
        stock_entry["item"],
        2,
    )
    assert procedural_town_game.state.money == (
        money_before_purchase - stock_entry["price"] * 2
    )
    assert procedural_town_game.state.inventory[stock_entry["item"]] == (
        inventory_before_purchase + 2
    )
    purchased_entry = next(
        entry
        for entry in procedural_town_game.procedural_town_local_stock(
            general_store_building
        )
        if entry["item"] == stock_entry["item"]
    )
    assert purchased_entry["remaining"] == stock_remaining_before - 2
    assert procedural_town_game.procedural_town_reputation() > reputation_before_purchase
    demand_offer = procedural_town_game.procedural_town_demand_offer(
        procedural_town_plan
    )
    procedural_town_game.state.inventory[demand_offer["item"]] = (
        procedural_town_game.state.inventory.get(demand_offer["item"], 0) + 2
    )
    money_before_demand_sale = procedural_town_game.state.money
    assert procedural_town_game.sell_procedural_town_demand(
        demand_offer["item"],
        2,
        procedural_town_plan,
    )
    assert procedural_town_game.state.money == (
        money_before_demand_sale + demand_offer["price"] * 2
    )
    assert procedural_town_game.procedural_town_demand_offer(
        procedural_town_plan
    )["remaining"] == demand_offer["remaining"] - 2
    commission = procedural_town_game.procedural_town_commission(
        procedural_town_plan
    )
    procedural_town_game.state.inventory[commission["item"]] = (
        procedural_town_game.state.inventory.get(commission["item"], 0)
        + commission["quantity"]
    )
    development_before_commission = (
        procedural_town_game.ensure_procedural_town_community(
            procedural_town_plan
        )["development_points"]
    )
    assert procedural_town_game.complete_procedural_town_commission(
        procedural_town_plan
    )
    assert procedural_town_game.procedural_town_commission(
        procedural_town_plan
    )["completed"]
    assert (
        procedural_town_game.ensure_procedural_town_community(
            procedural_town_plan
        )["development_points"]
        == development_before_commission + 5
    )
    procedural_town_game.state.stamina = 10
    procedural_town_game.state.combat_current_hp = 1
    assert procedural_town_game.use_procedural_town_special_service(
        clinic_building
    )
    assert procedural_town_game.state.stamina == 30
    assert (
        procedural_town_game.state.combat_current_hp
        == procedural_town_game.state.combat_max_hp
    )
    inn_building = next(
        building
        for building in local_service_buildings
        if building["type_id"] == "inn"
    )
    expected_inn_games = game_tables.venue_game_ids(
        f"{procedural_town_plan.get('id')}:{inn_building.get('id')}",
        "inn",
        count=2,
    )
    procedural_inn_map = procedural_town_game.procedural_town_interior_map(
        inn_building
    )
    procedural_inn_glyphs = set("".join("".join(row) for row in procedural_inn_map))
    assert {
        str(game_tables.GAME_TABLE_DATA[game_id]["glyph"])
        for game_id in expected_inn_games
    } <= procedural_inn_glyphs
    assert len(expected_inn_games) == 2
    assert {
        str(game_tables.GAME_TABLE_DATA[game_id]["category"])
        for game_id in expected_inn_games
    } == {"card", "board"}
    assert "|" not in procedural_inn_glyphs
    assert 4 <= sum(row.count("_") for row in procedural_inn_map) <= 16
    procedural_store_map = procedural_town_game.procedural_town_interior_map(
        general_store_building
    )
    procedural_store_glyphs = set("".join("".join(row) for row in procedural_store_map))
    assert "_" in procedural_store_glyphs
    assert "|" not in procedural_store_glyphs
    procedural_town_game.state.stamina = 20
    assert procedural_town_game.use_procedural_town_special_service(inn_building)
    assert procedural_town_game.state.stamina == min(
        procedural_town_game.max_stamina(),
        20 + 35 + 120 // 5,
    )
    procedural_service_calls = []
    original_safe_menu = procedural_town_game.safe_menu
    procedural_town_game.safe_menu = (
        lambda menu_func, close_message: procedural_service_calls.append(close_message)
    )
    for service_building in local_service_buildings:
        if service_building["type_id"] not in {"carpenter", "library", "workshop"}:
            continue
        assert procedural_town_game.use_procedural_town_special_service(
            service_building
        )
        assert procedural_service_calls[-1] == f"{service_building['name']} closed."
    procedural_town_game.safe_menu = original_safe_menu
    local_shop_calls = []
    original_local_shop_menu = procedural_town_game.procedural_town_local_shop_menu
    procedural_town_game.procedural_town_local_shop_menu = (
        lambda building: local_shop_calls.append(building["type_id"])
    )
    for service_building in local_service_buildings:
        assert procedural_town_game.procedural_town_building_service(
            service_building
        )
    procedural_town_game.procedural_town_local_shop_menu = original_local_shop_menu
    assert set(local_shop_calls) == {
        building["type_id"] for building in local_service_buildings
    }
    community = procedural_town_game.ensure_procedural_town_community(
        procedural_town_plan
    )
    story_stage_before = community["story_stage"]
    development_before_story = community["development_points"]
    required_story_item, required_story_quantity = (
        procedural_town_game.procedural_town_story_requirements(
            procedural_town_plan
        )
    )
    procedural_town_game.state.inventory[required_story_item] = (
        procedural_town_game.state.inventory.get(required_story_item, 0)
        + required_story_quantity
    )
    assert procedural_town_game.complete_procedural_town_story_stage(
        procedural_town_plan
    )
    assert community["story_stage"] == story_stage_before + 1
    assert community["development_points"] > development_before_story
    assert community["completed_projects"]
    assert len(
        procedural_town_game.procedural_town_development_benefits(
            procedural_town_plan
        )
    ) >= 2
    original_event_day = procedural_town_game.state.day
    original_event_weather = procedural_town_game.state.weather
    procedural_town_game.state.weather = "Sunny"
    active_event = {}
    for candidate_day in range(1, 29):
        procedural_town_game.state.day = candidate_day
        active_event = procedural_town_game.procedural_town_active_event(
            procedural_town_plan
        )
        if active_event:
            break
    assert active_event
    development_before_event = community["development_points"]
    reputation_before_event = procedural_town_game.procedural_town_reputation()
    total_relationship_before_event = sum(
        resident["relationship"]
        for resident in procedural_runtime_population["residents"].values()
    )
    assert procedural_town_game.participate_procedural_town_event(
        procedural_town_plan
    )
    assert not procedural_town_game.participate_procedural_town_event(
        procedural_town_plan
    )
    expected_event_development = (
        3
        if procedural_town_game.procedural_town_current_policy(
            procedural_town_plan
        ) == "Public Works"
        else 2
    )
    assert (
        community["development_points"]
        == development_before_event + expected_event_development
    )
    assert procedural_town_game.procedural_town_reputation() > reputation_before_event
    assert sum(
        resident["relationship"]
        for resident in procedural_runtime_population["residents"].values()
    ) >= total_relationship_before_event + min(
        3,
        len(procedural_runtime_population["residents"]),
    )
    procedural_town_game.state.day = original_event_day
    procedural_town_game.state.weather = original_event_weather
    festival_event = {}
    procedural_town_game.state.weather = "Sunny"
    for candidate_day in range(1, 8):
        procedural_town_game.state.day = candidate_day
        if procedural_town_game.state.weekday == "Saturday":
            festival_event = procedural_town_game.procedural_town_active_event(
                procedural_town_plan
            )
            break
    assert festival_event["id"] == "identity_festival"
    assert festival_event["name"] == procedural_identity["festival_name"]
    procedural_town_game.state.day = original_event_day
    procedural_town_game.state.weather = original_event_weather
    procedural_town_game.adjust_procedural_town_reputation(
        200,
        "Smoke test trusted standing",
        procedural_town_plan,
    )
    assert procedural_town_game.claim_procedural_town_support(
        procedural_town_plan
    )
    assert not procedural_town_game.claim_procedural_town_support(
        procedural_town_plan
    )
    well_building = next(
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] == "well"
    )
    procedural_town_game.state.stamina = 50
    assert procedural_town_game.procedural_town_building_service(well_building)
    assert procedural_town_game.state.stamina == 58
    assert not procedural_town_game.procedural_town_building_service(well_building)
    assert procedural_town_game.procedural_town_report_lines(
        procedural_town_x,
        procedural_town_y,
    )
    assert procedural_town_game.procedural_town_development_tier(
        procedural_town_plan
    ) != "Unknown"
    partner_x, partner_y = next(
        site for site in procedural_town_sites
        if site != (procedural_town_x, procedural_town_y)
    )
    partner_plan = procedural_town_game.ensure_procedural_town_plan(
        partner_x,
        partner_y,
    )
    assert partner_plan is not None
    partner_plan["discovered"] = True
    assert (
        procedural_town_game.procedural_town_trade_partner(
            procedural_town_plan
        )["name"]
        == partner_plan["name"]
    )
    assert any(
        partner_plan["name"] in entry["note"]
        for entry in procedural_town_game.procedural_town_local_stock(
            general_store_building
        )
    )
    home_building = next(
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] == "home"
    )
    population_before_home_purchase = procedural_town_game.procedural_settlement_population(
        procedural_town_x,
        procedural_town_y,
    ) or {}
    former_home_resident_ids = [
        str(resident_id)
        for resident_id, resident in population_before_home_purchase.get("residents", {}).items()
        if str(resident.get("home_building_id", "")) == str(home_building["id"])
    ]
    assert procedural_town_game.exit_procedural_town_building()
    assert procedural_town_game.enter_procedural_town_building(home_building)
    procedural_town_game.state.money = 100000
    procedural_town_game.state.inventory["Wood"] = (
        procedural_town_game.state.inventory.get("Wood", 0) + 160
    )
    procedural_town_game.state.inventory["Stone"] = (
        procedural_town_game.state.inventory.get("Stone", 0) + 130
    )
    assert procedural_town_game.purchase_procedural_town_residence(
        procedural_town_plan,
        home_building,
        built=True,
    )
    property_record = procedural_town_game.player_property_for_building(
        procedural_town_plan,
        home_building,
    )
    assert property_record is not None
    assert property_record["built"] is True
    assert procedural_town_game.procedural_residence_has_kitchen(property_record)
    assert procedural_town_game.has_kitchen_access()
    property_scope = procedural_town_game.procedural_property_object_location_key(
        property_record["id"]
    )
    assert procedural_town_game.current_object_location_key() == property_scope
    residence_width, residence_height = procedural_town_game.procedural_town_interior_source_dimensions(
        home_building
    )
    orient_residence_position = lambda x, y: procedural_town_game.procedural_town_orient_position(
        x,
        y,
        residence_width,
        residence_height,
        procedural_town_game.procedural_town_building_door_side(home_building),
    )
    def residence_furnishing_position(name):
        for key, placed_name in procedural_town_game.state.placed_objects.items():
            parsed = procedural_town_game.parse_object_key(str(key))
            if not parsed or str(placed_name) != name:
                continue
            location_key, source_x, source_y = parsed
            if location_key == property_scope:
                return orient_residence_position(source_x, source_y)
        raise AssertionError(f"Purchased procedural residence is missing {name}")

    bed_position = residence_furnishing_position("Bed")
    calendar_position = residence_furnishing_position("Wall Calendar")
    television_position = residence_furnishing_position("Television")
    kitchen_position = residence_furnishing_position("Kitchen Counter")
    chair_position = next(
        (x, y)
        for y, row in enumerate(procedural_town_game.active_map())
        for x, tile in enumerate(row)
        if tile in {".", ","}
        and not procedural_town_game.get_placed_object(x, y)
        and procedural_town_game.can_place_object("Wooden Chair", x, y)[0]
    )
    assert procedural_town_game.get_placed_object(*bed_position) == "Bed"
    assert procedural_town_game.get_placed_object(*calendar_position) == "Wall Calendar"
    assert procedural_town_game.get_placed_object(*television_position) == "Television"
    assert procedural_town_game.get_placed_object(*kitchen_position) == "Kitchen Counter"
    assert procedural_town_game.active_map()[bed_position[1]][bed_position[0]] == "."
    assert procedural_town_game.active_map()[kitchen_position[1]][kitchen_position[0]] == "."
    assert procedural_town_game.can_hold_objects_here()
    assert procedural_town_game.can_place_object("Wooden Chair", *chair_position)[0]
    procedural_town_game.state.hour = 23
    procedural_family_position = procedural_town_game.family_procedural_furniture_activity_position(
        "test_household_member", ("sleep",),
        {(procedural_town_game.state.player_x, procedural_town_game.state.player_y)},
    )
    assert procedural_family_position is not None
    assert procedural_town_game.procedural_town_interior_tile_passable(
        procedural_town_game.active_map()[procedural_family_position[1]][procedural_family_position[0]]
    )
    assert procedural_town_game.get_placed_object(*procedural_family_position) is None
    procedural_town_game.state.hour = 12
    population_after_home_purchase = procedural_town_game.procedural_settlement_population(
        procedural_town_x,
        procedural_town_y,
    ) or {}
    assert all(
        str(population_after_home_purchase.get("residents", {}).get(resident_id, {}).get("home_building_id", ""))
        != str(home_building["id"])
        for resident_id in former_home_resident_ids
    )
    home_lines = procedural_town_game.procedural_town_home_lines(home_building)
    assert any("Residents: Unoccupied" in line for line in home_lines)
    assert any("Kitchen: ready" in line for line in home_lines)
    assert any("Bedroom suite: ready" in line for line in home_lines)
    assert procedural_town_game.set_primary_residence(property_record["id"])
    assert procedural_town_game.can_sleep_at_primary_town_residence()
    sleep_calls = []
    original_sleep = procedural_town_game.sleep
    procedural_town_game.sleep = lambda force=False: sleep_calls.append(force)
    procedural_town_game.use_procedural_town_interior_action(*bed_position)
    procedural_town_game.sleep = original_sleep
    assert sleep_calls == [False]
    cooking_calls = []
    original_safe_menu_for_residence = procedural_town_game.safe_menu
    procedural_town_game.safe_menu = (
        lambda menu_func, close_message: cooking_calls.append(close_message)
    )
    procedural_town_game.use_procedural_town_interior_action(*kitchen_position)
    procedural_town_game.safe_menu = original_safe_menu_for_residence
    assert cooking_calls == ["Cooking closed."]
    assert procedural_town_game.upgrade_procedural_residence(
        property_record["id"]
    )
    assert property_record["upgrade_level"] == 1
    assert procedural_town_game.get_placed_object(*kitchen_position) == "Kitchen Counter"
    assert procedural_town_game.procedural_residence_sleep_bonus() > 0
    procedural_town_game.state.spouse_npc_id = str(
        procedural_town_game.state.town_npcs[0]["id"]
    )
    procedural_town_game.state.spouse_moved_to_farm = True
    assert procedural_town_game.move_household_to_residence(
        property_record["id"]
    )
    assert property_record["household_moved"] is True
    family_table_position = residence_furnishing_position("Family Table")
    assert procedural_town_game.get_placed_object(*family_table_position) == "Family Table"
    assert procedural_town_game.household_residence_property() is property_record
    assert any(
        resident.get("household_town_resident")
        for resident in procedural_town_game.procedural_town_resident_position_lookup().values()
    )
    second_home_building = next(
        building
        for building in procedural_town_plan["buildings"].values()
        if building["type_id"] == "home" and building["id"] != home_building["id"]
    )
    assert procedural_town_game.purchase_procedural_town_residence(
        procedural_town_plan,
        second_home_building,
    )
    rental_property = procedural_town_game.player_property_for_building(
        procedural_town_plan,
        second_home_building,
    )
    assert rental_property is not None
    assert procedural_town_game.set_procedural_property_use(
        rental_property["id"],
        "Rental",
    )
    assert procedural_town_game.procedural_property_daily_income(
        rental_property
    ) > 0
    assert procedural_town_game.exit_procedural_town_building()
    assert procedural_town_game.enter_procedural_town_building(clinic_building)
    assert procedural_town_game.purchase_procedural_business(
        procedural_town_plan,
        general_store_building,
    )
    business_record = procedural_town_game.player_business_for_building(
        procedural_town_plan,
        general_store_building,
    )
    assert business_record is not None
    base_business_income = procedural_town_game.procedural_business_daily_income(
        business_record
    )
    assert procedural_town_game.upgrade_procedural_business(
        business_record["id"]
    )
    assert business_record["upgrade_level"] == 1
    assert procedural_town_game.procedural_business_daily_income(
        business_record
    ) > base_business_income
    assert procedural_town_game.set_procedural_business_active(
        business_record["id"],
        False,
    )
    assert business_record["active"] is False
    assert procedural_town_game.set_procedural_business_active(
        business_record["id"],
        True,
    )
    assert procedural_town_game.set_procedural_business_strategy(
        business_record["id"],
        "Trade",
    )
    manager_candidates = procedural_town_game.procedural_business_manager_candidates(
        procedural_town_plan,
        general_store_building,
    )
    if manager_candidates:
        assert procedural_town_game.appoint_procedural_business_manager(
            business_record["id"],
            manager_candidates[-1]["id"],
        )
    employee_candidates = (
        procedural_town_game.procedural_business_employee_candidates(
            business_record
        )
    )
    assert employee_candidates
    employee_candidate = employee_candidates[0]
    assert procedural_town_game.hire_procedural_business_employee(
        business_record["id"],
        employee_candidate["id"],
    )
    assert employee_candidate["id"] in business_record["employee_ids"]
    assert procedural_town_game.set_procedural_business_wage_policy(
        business_record["id"],
        "Generous",
    )
    assert procedural_town_game.set_procedural_business_supply_contract(
        business_record["id"],
        "Local Exports",
    )
    assert business_record["wage_policy"] == "Generous"
    assert business_record["supply_contract"] == "Local Exports"
    politics = procedural_town_game.ensure_procedural_town_politics(
        procedural_town_plan
    )
    procedural_town_game.state.month = politics["election_month"]
    procedural_town_game.state.day = 1
    eligible, eligibility_reason = procedural_town_game.player_election_eligibility(
        procedural_town_plan
    )
    assert eligible, eligibility_reason
    assert procedural_town_game.register_player_for_election(
        procedural_town_plan,
        "Open Trade",
    )
    election_issue = procedural_town_game.procedural_town_election_issue(
        procedural_town_plan
    )
    assert election_issue["policy"] in {
        "Public Works",
        "Market Investment",
        "Open Trade",
        "Family Services",
        "Wilderness Safety",
    }
    support_before_campaign = int(
        politics["campaign_support"].get("player", 0)
    )
    procedural_town_game.state.stamina = 100
    assert procedural_town_game.perform_procedural_campaign_activity(
        "Market Speech",
        procedural_town_plan,
    )
    assert int(politics["campaign_support"]["player"]) > support_before_campaign
    assert not procedural_town_game.perform_procedural_campaign_activity(
        "Worker Roundtable",
        procedural_town_plan,
    )
    resident_candidate = next(
        candidate_id
        for candidate_id in politics["candidate_ids"]
        if candidate_id != "player"
    )
    assert procedural_town_game.endorse_procedural_candidate(
        resident_candidate,
        procedural_town_plan,
    )
    procedural_town_game.state.day = max(1, politics["election_day"] - 2)
    assert procedural_town_game.procedural_election_phase(
        procedural_town_plan
    ) == "Voting open"
    assert procedural_town_game.hold_procedural_election_debate(
        procedural_town_plan
    )
    assert politics["debate_scores"]
    assert not procedural_town_game.hold_procedural_election_debate(
        procedural_town_plan
    )
    assert procedural_town_game.cast_procedural_election_vote(
        "player",
        procedural_town_plan,
    )
    procedural_town_game.state.day = politics["election_day"] + 1
    assert procedural_town_game.resolve_procedural_election(
        procedural_town_plan
    ) == "player"
    assert politics["incumbent_id"] == "player"
    assert politics["current_policy"] == "Open Trade"
    assert politics["last_result_scores"]["player"] > 0
    assert procedural_town_game.state.civic_profile["elections_won"] == 1
    assert any(event_id.startswith("election_debate:") for event_id, _title, _steps, _message in procedural_special_events)
    assert any(event_id.startswith("election_result:") for event_id, _title, _steps, _message in procedural_special_events)
    petition = procedural_town_game.ensure_procedural_constituent_petition(
        procedural_town_plan
    )
    resident_memory_count_before_petition = sum(
        len(resident.get("memories", []) or [])
        for resident in procedural_runtime_population["residents"].values()
    )
    procedural_town_game.state.stamina = 100
    assert procedural_town_game.resolve_procedural_constituent_petition(
        "Organize volunteers",
        procedural_town_plan,
    )
    assert petition["resolved"] is True
    assert petition["resolution"] == "Organize volunteers"
    assert sum(
        len(resident.get("memories", []) or [])
        for resident in procedural_runtime_population["residents"].values()
    ) > resident_memory_count_before_petition
    assert any(
        event_id.startswith("constituent_petition:")
        for event_id, _title, _steps, _message in procedural_special_events
    )
    assert procedural_town_game.create_player_trade_route(
        business_record["id"],
        procedural_town_game.civic_town_key(partner_plan),
    )
    trade_route = next(
        iter(procedural_town_game.state.player_trade_routes.values())
    )
    assert trade_route["source_town_key"] == procedural_town_game.civic_town_key(
        procedural_town_plan
    )
    assert trade_route["caravan_name"]
    caravan_phases = {
        procedural_town_game.player_trade_route_caravan_state(
            trade_route,
            procedural_town_game.civic_date_ordinal() + offset,
        )["phase"]
        for offset in range(20)
    }
    assert {"source", "outbound", "destination", "returning"} <= caravan_phases
    assert trade_route["route_reliability"] == 82
    route_path = procedural_town_game.player_trade_route_chunk_path(trade_route)
    assert route_path[0] == (
        int(procedural_town_plan["chunk_x"]), int(procedural_town_plan["chunk_y"])
    )
    assert route_path[-1] == (int(partner_plan["chunk_x"]), int(partner_plan["chunk_y"]))
    incident_chunk = route_path[len(route_path) // 2]
    trade_route["caravan_incident"] = {
        "type": "broken_axle",
        "status": "open",
        "ordinal": procedural_town_game.civic_date_ordinal(),
        "chunk_x": incident_chunk[0],
        "chunk_y": incident_chunk[1],
        "destination_town_key": procedural_town_game.civic_town_key(partner_plan),
        "progress": 0,
        "resolved_by": "",
    }
    disrupted_income = procedural_town_game.procedural_trade_route_daily_income(trade_route)
    disrupted_state = procedural_town_game.player_trade_route_caravan_state(trade_route)
    assert disrupted_state["phase"] == "disrupted"
    assert any(
        "Trade route disruption" in event
        for event in procedural_town_game.regional_circulation_calendar_events_for_date(
            procedural_town_game.state.month,
            procedural_town_game.state.day,
            procedural_town_game.state.year,
        )
    )
    assert any("DELAYED" in line for line in procedural_town_game.regional_journal_overview_lines())
    assert procedural_town_game.trade_route_state_chunk(trade_route, disrupted_state) == incident_chunk
    road_caravans = procedural_town_game.player_trade_route_wilderness_actors(*incident_chunk)
    road_caravan = next(actor for actor in road_caravans if actor.get("procedural_caravan"))
    assert road_caravan["route_id"] == trade_route["id"]
    assert procedural_town_game.render_wilderness_traveler(road_caravan)
    generated_road_scene = procedural_town_game.generate_wilderness_travelers(*incident_chunk)
    assert any(
        actor.get("procedural_caravan") and actor.get("route_id") == trade_route["id"]
        for actor in generated_road_scene
    )
    old_location = procedural_town_game.state.location
    old_chunk = (
        procedural_town_game.state.wilderness_chunk_x,
        procedural_town_game.state.wilderness_chunk_y,
    )
    procedural_town_game.state.location = "Wilderness"
    procedural_town_game.state.wilderness_chunk_x = incident_chunk[0]
    procedural_town_game.state.wilderness_chunk_y = incident_chunk[1]
    procedural_town_game.state.stamina = 100
    incident_money_before = int(procedural_town_game.state.money)
    incident_development_before = int(trade_route["route_development_points"])
    assert procedural_town_game.resolve_player_trade_route_incident(trade_route["id"], "labor")
    assert trade_route["caravan_incident"]["status"] == "resolved"
    assert procedural_town_game.state.money == incident_money_before + 85
    assert int(trade_route["route_development_points"]) == incident_development_before + 3
    assert procedural_town_game.procedural_trade_route_daily_income(trade_route) > disrupted_income
    delivery_count_before = int(trade_route["caravan_deliveries"])
    procedural_town_game.record_player_trade_route_delivery(
        trade_route, procedural_town_game.civic_date_ordinal()
    )
    assert int(trade_route["caravan_deliveries"]) == delivery_count_before + 1
    market_effect = procedural_town_game.regional_trade_market_effect(partner_plan)
    assert str(trade_route["good"]) in market_effect["delivered"]
    assert "caravan deliveries" in str(
        procedural_town_game.procedural_town_market_profile(partner_plan)["headline"]
    ).lower()
    procedural_town_game.state.wilderness_chunk_x = int(partner_plan["chunk_x"])
    procedural_town_game.state.wilderness_chunk_y = int(partner_plan["chunk_y"])
    partner_shop = next(
        building for building in partner_plan["buildings"].values()
        if building.get("type_id") in {"general_store", "market_stall"}
    )
    delivered_stock = next(
        entry for entry in procedural_town_game.procedural_town_local_stock(partner_shop)
        if entry["item"] == trade_route["good"]
    )
    assert delivered_stock["note"] == "Fresh caravan delivery"
    follower_id = next(
        follower_id for follower_id in procedural_town_game.travel_follower_candidate_ids()
        if procedural_town_game.travel_follower_is_eligible(follower_id)
    )
    procedural_town_game.state.travel_follower_ids = [follower_id]
    procedural_town_game.normalize_travel_followers()
    assert "route_guard" not in procedural_town_game.travel_follower_task_options(follower_id)
    assert procedural_town_game.assign_follower_to_trade_route(
        trade_route["id"], "route_guard", follower_id
    )
    assert "route_guard" in procedural_town_game.travel_follower_task_options(follower_id)
    crew_development_before = int(trade_route["route_development_points"])
    assert procedural_town_game.perform_trade_route_follower_work(follower_id, "route_guard")
    assert procedural_town_game.perform_trade_route_follower_work(follower_id, "route_guard")
    assert int(trade_route["route_development_points"]) == crew_development_before + 1
    trade_route["route_development_points"] = 30
    sanitized_route = civic_state.sanitize_player_trade_routes(
        {trade_route["id"]: trade_route}
    )[trade_route["id"]]
    assert sanitized_route["route_reliability"] == trade_route["route_reliability"]
    assert sanitized_route["crew_assignments"]["route_guard"] == follower_id
    assert sanitized_route["caravan_incident"]["status"] == "resolved"
    assert sanitized_route["route_development_points"] == 30
    infrastructure = procedural_town_game.player_trade_route_wilderness_actors(
        *route_path[len(route_path) // 2]
    )
    assert any(actor.get("trade_route_feature") for actor in infrastructure)
    procedural_town_game.state.location = old_location
    (
        procedural_town_game.state.wilderness_chunk_x,
        procedural_town_game.state.wilderness_chunk_y,
    ) = old_chunk
    route_income_before_upgrades = (
        procedural_town_game.procedural_trade_route_daily_income(trade_route)
    )
    assert procedural_town_game.upgrade_player_trade_route(
        trade_route["id"],
        "capacity",
    )
    assert procedural_town_game.upgrade_player_trade_route(
        trade_route["id"],
        "escort",
    )
    assert procedural_town_game.procedural_trade_route_daily_income(
        trade_route
    ) > route_income_before_upgrades
    assert procedural_town_game.set_player_trade_route_active(
        trade_route["id"],
        False,
    )
    assert trade_route["active"] is False
    assert procedural_town_game.set_player_trade_route_active(
        trade_route["id"],
        True,
    )
    assert procedural_town_game.contribute_to_procedural_town_treasury(
        1000,
        procedural_town_plan,
    )
    assert procedural_town_game.complete_procedural_civic_initiative(
        "trade_depot",
        procedural_town_plan,
    )
    assert "trade_depot" in politics["completed_initiatives"]
    assert procedural_town_game.set_procedural_town_policy(
        "Market Investment",
        procedural_town_plan,
    )
    assert not procedural_town_game.set_procedural_town_policy(
        "Family Services",
        procedural_town_plan,
    )
    assert politics["current_policy"] == "Market Investment"
    third_x, third_y = next(
        site
        for site in procedural_town_sites
        if site not in {
            (procedural_town_x, procedural_town_y),
            (partner_x, partner_y),
        }
    )
    third_plan = procedural_town_game.ensure_procedural_town_plan(
        third_x,
        third_y,
    )
    assert third_plan is not None
    third_plan["discovered"] = True
    procedural_town_game.adjust_procedural_town_reputation(
        100,
        "Regional council test standing",
        partner_plan,
    )
    route_income_before_agreement = (
        procedural_town_game.procedural_trade_route_daily_income(trade_route)
    )
    eligible, council_reason = procedural_town_game.regional_council_eligibility()
    assert eligible, council_reason
    assert procedural_town_game.join_regional_council(
        procedural_town_game.civic_town_key(procedural_town_plan)
    )
    assert any(event_id.startswith("regional_council_join:") for event_id, _title, _steps, _message in procedural_special_events)
    assert procedural_town_game.establish_regional_agreement(
        trade_route["id"],
        "Trade Charter",
    )
    assert trade_route["agreement_type"] == "Trade Charter"
    assert any(
        event_id.startswith("regional_agreement:")
        for event_id, _title, _steps, _message in procedural_special_events
    )
    assert procedural_town_game.contribute_to_regional_treasury(3000)
    assert procedural_town_game.complete_regional_project("caravan_league")
    assert any(event_id.startswith("regional_project:") for event_id, _title, _steps, _message in procedural_special_events)
    regional_council = procedural_town_game.ensure_regional_council_state()
    assert "caravan_league" in regional_council["completed_projects"]
    assert regional_council["member"] is True
    assert regional_council["agreement_log"]
    assert any(
        "Membership: delegate" in line
        for line in procedural_town_game.regional_council_lines()
    )
    assert any(
        "Lifetime property income" in line
        for line in procedural_town_game.civic_portfolio_lines()
    )
    assert any(
        trade_route["caravan_name"] in line
        for line in procedural_town_game.regional_journal_overview_lines()
    )
    assert any(
        procedural_town_plan["name"].upper() in line
        for line in procedural_town_game.regional_journal_town_lines(
            procedural_town_plan
        )
    )
    assert procedural_town_game.regional_journal_opportunity_lines()
    assert procedural_town_game.procedural_trade_route_daily_income(
        trade_route
    ) > route_income_before_agreement
    travel_costs = procedural_town_game.civic_travel_costs(
        procedural_town_game.civic_town_key(partner_plan)
    )
    assert travel_costs[2] is True
    procedural_town_game.state.stamina = 100
    assert procedural_town_game.travel_to_civic_town(
        procedural_town_game.civic_town_key(partner_plan)
    )
    assert (
        procedural_town_game.state.wilderness_chunk_x,
        procedural_town_game.state.wilderness_chunk_y,
    ) == (partner_x, partner_y)
    procedural_town_game.state.stamina = 100
    assert procedural_town_game.travel_to_civic_town(
        procedural_town_game.civic_town_key(procedural_town_plan),
        property_id=property_record["id"],
    )
    assert procedural_town_game.on_procedural_town_interior()
    assert (
        procedural_town_game.current_procedural_town_building()["id"]
        == home_building["id"]
    )
    assert procedural_town_game.exit_procedural_town_building()
    civic_overlays = procedural_town_game.procedural_town_civic_overlay_lookup(
        procedural_town_plan
    )
    overlay_kinds = {
        str(record.get("kind", ""))
        for record in civic_overlays.values()
    }
    assert {"residence", "business", "initiative", "regional_project"} <= overlay_kinds
    source_key = procedural_town_game.civic_town_key(procedural_town_plan)
    today_ordinal = procedural_town_game.civic_date_ordinal()
    source_day_offset = next(
        offset
        for offset in range(20)
        if procedural_town_game.player_trade_route_caravan_state(
            trade_route,
            today_ordinal + offset,
        ).get("town_key") == source_key
    )
    procedural_town_game.state.day += source_day_offset
    procedural_town_game.update_procedural_town_residents(force_reanchor=True)
    caravan_actor = next(
        resident
        for resident in procedural_town_game.procedural_town_resident_position_lookup().values()
        if resident.get("procedural_caravan")
    )
    assert caravan_actor["route_id"] == trade_route["id"]
    caravan_stock = procedural_town_game.procedural_caravan_stock(caravan_actor)
    assert caravan_stock and caravan_stock[0]["remaining"] > 0
    caravan_item = str(caravan_stock[0]["item"])
    caravan_remaining = int(caravan_stock[0]["remaining"])
    caravan_inventory_before = int(
        procedural_town_game.state.inventory.get(caravan_item, 0)
    )
    assert procedural_town_game.purchase_procedural_caravan_stock(
        caravan_actor,
        caravan_item,
    )
    assert (
        procedural_town_game.state.inventory[caravan_item]
        == caravan_inventory_before + 1
    )
    assert next(
        entry
        for entry in procedural_town_game.procedural_caravan_stock(caravan_actor)
        if entry["item"] == caravan_item
    )["remaining"] == caravan_remaining - 1
    contract_state = procedural_town_game.refresh_regional_contract_board()
    contract_types = {
        contract["type"]
        for contract in contract_state["contracts"].values()
    }
    assert {"supply", "public_works", "courier", "escort"} <= contract_types
    source_supply_contract = next(
        contract
        for contract in contract_state["contracts"].values()
        if contract["type"] == "supply"
        and contract["town_key"] == source_key
    )
    assert procedural_town_game.accept_regional_contract(
        source_supply_contract["id"]
    )
    contract_item = str(source_supply_contract["item"])
    procedural_town_game.state.inventory[contract_item] = (
        procedural_town_game.state.inventory.get(contract_item, 0)
        + int(source_supply_contract["quantity"])
    )
    contract_money_before = procedural_town_game.state.money
    assert procedural_town_game.complete_regional_contract(
        source_supply_contract["id"]
    )
    assert procedural_town_game.state.money > contract_money_before
    escort_contract = next(
        contract
        for contract in contract_state["contracts"].values()
        if contract["type"] == "escort"
        and contract["route_id"] == trade_route["id"]
    )
    assert procedural_town_game.accept_regional_contract(
        escort_contract["id"]
    )
    journey_lines, journey_foraged_item, journey_foraged_qty = (
        procedural_town_game.procedural_caravan_journey_event_lines(
            trade_route,
            "Scout the road",
            partner_plan,
        )
    )
    assert journey_lines
    assert journey_foraged_item
    assert journey_foraged_qty == 2
    original_vertical_panel_view = procedural_town_game.vertical_panel_view
    procedural_town_game.vertical_panel_view = (
        lambda *args, **kwargs: None
    )
    procedural_town_game.state.stamina = 100
    trade_route["caravan_last_journey_day"] = ""
    route_journeys_before = int(trade_route.get("caravan_journeys", 0))
    assert procedural_town_game.travel_with_procedural_caravan(
        caravan_actor,
        "Share the camp",
    )
    procedural_town_game.vertical_panel_view = original_vertical_panel_view
    assert trade_route["caravan_journeys"] == route_journeys_before + 1
    assert escort_contract["status"] == "completed"
    assert procedural_town_game.ensure_regional_contract_state()["journey_log"]
    assert any(event_id.startswith("caravan_journey:") for event_id, _title, _steps, _message in procedural_special_events)
    assert (
        procedural_town_game.state.wilderness_chunk_x,
        procedural_town_game.state.wilderness_chunk_y,
    ) == (partner_x, partner_y)
    procedural_town_game.state.stamina = 100
    assert procedural_town_game.travel_to_civic_town(source_key)
    assert procedural_town_game.enter_procedural_town_building(clinic_building)
    procedural_runtime_population = (
        procedural_town_game.procedural_settlement_population(
            procedural_town_x,
            procedural_town_y,
        )
    )
    assert procedural_runtime_population
    runtime_resident = procedural_runtime_population["residents"][
        runtime_resident["id"]
    ]
    employee_candidate = procedural_runtime_population["residents"][
        employee_candidate["id"]
    ]
    money_before_civic_income = procedural_town_game.state.money
    property_lifetime_before = rental_property["lifetime_income"]
    business_lifetime_before = business_record["lifetime_income"]
    trade_lifetime_before = trade_route["lifetime_income"]
    treasury_before_civic_income = politics["treasury"]
    regional_treasury_before_income = regional_council["treasury"]
    procedural_town_game.state.day += 1
    civic_income = procedural_town_game.process_civic_economy()
    assert civic_income > 0
    assert procedural_town_game.state.money == money_before_civic_income + civic_income
    assert rental_property["lifetime_income"] > property_lifetime_before
    assert business_record["lifetime_income"] > business_lifetime_before
    assert trade_route["lifetime_income"] > trade_lifetime_before
    assert politics["treasury"] > treasury_before_civic_income
    assert regional_council["treasury"] > regional_treasury_before_income
    assert procedural_town_game.process_civic_economy() == 0
    assert any(
        "Current policy: Market Investment" in line
        for line in procedural_town_game.procedural_town_report_lines(
            procedural_town_x,
            procedural_town_y,
        )
    )
    assert any(
        "Regional council member: yes" in line
        for line in procedural_town_game.procedural_town_report_lines(
            procedural_town_x,
            procedural_town_y,
        )
    )
    romance_resident = runtime_resident
    romance_resident["age_group"] = "Adult"
    romance_resident["age_years"] = 28
    romance_resident["romanceable"] = True
    romance_resident["marital_status"] = "Single"
    romance_resident["courtship_partner_id"] = ""
    romance_resident["npc_spouse_id"] = ""
    romance_resident["sex"] = (
        "Male"
        if procedural_town_game.state.player_sex == "Female"
        else "Female"
    )
    romance_resident["met"] = True
    romance_resident["relationship"] = 220
    romance_resident_id = str(romance_resident["id"])
    procedural_town_game.state.town_npc_relationships[
        romance_resident_id
    ] = 220
    procedural_town_game.state.town_npc_dialogue_counts[
        romance_resident_id
    ] = 30
    romance_resident["dialogue_count"] = 30
    procedural_town_game.state.town_npc_courtship_counts[
        romance_resident_id
    ] = 12
    procedural_town_game.state.spouse_npc_id = ""
    procedural_town_game.state.spouse_moved_to_farm = False
    procedural_town_game.state.dating_npc_ids = []
    proposal_item = procedural_town_game.proposal_item_for_npc(
        romance_resident
    )
    procedural_town_game.state.inventory[proposal_item] = (
        procedural_town_game.state.inventory.get(proposal_item, 0) + 1
    )
    procedural_town_game.state.inventory[data.WEDDING_RING_ITEM] = 1
    assert procedural_town_game.is_marriageable_npc(romance_resident)
    assert procedural_town_game.can_start_dating_with_npc(
        romance_resident
    )[0]
    assert procedural_town_game.can_propose_to_town_npc(
        romance_resident
    )[0]
    romance_menu_labels = [
        item.label
        for item in procedural_town_game.procedural_town_resident_menu_items(
            romance_resident
        )
    ]
    assert "Courtship" not in romance_menu_labels
    assert "Propose" not in romance_menu_labels
    assert "relationship" in {
        value for value, _label, _hint
        in procedural_town_game.dialogue_topic_options(romance_resident, "procedural")
    }
    relationship_options = []
    original_relationship_choose = procedural_town_game.dialogue_choose
    original_relationship_say = procedural_town_game.dialogue_say
    procedural_town_game.dialogue_choose = lambda actor, prompt, phase, options, transcript: (
        relationship_options.extend(options), "back"
    )[-1]
    procedural_town_game.dialogue_say = lambda *args, **kwargs: True
    try:
        assert procedural_town_game.dialogue_handle_relationship_topic(
            romance_resident, "procedural", []
        )
    finally:
        procedural_town_game.dialogue_choose = original_relationship_choose
        procedural_town_game.dialogue_say = original_relationship_say
    relationship_values = {value for value, _label, _hint in relationship_options}
    assert {"status", "gift", "courtship", "proposal", "back"}.issubset(relationship_values)
    original_wedding_date_picker = procedural_town_game.choose_scheduled_wedding_date
    procedural_town_game.choose_scheduled_wedding_date = (
        lambda _npc: procedural_town_game.date_after_days(7)
    )
    try:
        assert procedural_town_game.propose_to_town_npc(
            romance_resident,
            present=True,
        )
    finally:
        procedural_town_game.choose_scheduled_wedding_date = original_wedding_date_picker
    assert any(
        event_id.startswith(f"proposal:{romance_resident_id}:")
        for event_id, _title, _steps, _message in procedural_special_events
    )
    procedural_town_game.state.spouse_npc_id = romance_resident_id
    procedural_town_game.state.dating_npc_ids = [romance_resident_id]
    procedural_town_game.state.spouse_moved_to_farm = True
    procedural_town_game.state.marriage_month = procedural_town_game.state.month
    procedural_town_game.state.marriage_day = procedural_town_game.state.day
    procedural_town_game.state.marriage_year = procedural_town_game.state.year
    procedural_town_game.mark_family_event_flag(
        f"family_planning_discussed:{romance_resident_id}"
    )
    assert (
        procedural_town_game.npc_record_by_id(romance_resident_id)
        is romance_resident
    )
    assert procedural_town_game.town_npc_name(
        romance_resident_id
    ) == romance_resident["name"]
    assert procedural_town_game.can_start_pregnancy_with_spouse(
        romance_resident
    )[0]
    assert any(
        romance_resident["name"] in line
        for line in procedural_town_game.marriage_status_lines()
    )
    assert any(
        romance_resident["name"] in line
        for line in procedural_town_game.journal_relationship_lines()
    )
    assert any(
        romance_resident["name"] in line
        for line in procedural_town_game.birthday_events_for_date(
            int(romance_resident["birthday_month"]),
            int(romance_resident["birthday_day"]),
            procedural_town_game.state.year,
        )
    )
    assert procedural_town_game.exit_procedural_town_building()
    assert procedural_town_game.enter_procedural_town_building(home_building)
    assert any(
        str(resident.get("id", "")) == romance_resident_id
        and resident.get("household_town_resident")
        for resident in procedural_town_game.procedural_town_resident_position_lookup().values()
    )
    assert procedural_town_game.exit_procedural_town_building()
    assert procedural_town_game.enter_procedural_town_building(clinic_building)
    aging_resident = next(
        resident
        for resident in procedural_runtime_population["residents"].values()
        if resident["id"]
        not in {
            employee_candidate["id"],
            business_record["manager_resident_id"],
            romance_resident_id,
        }
    )
    aging_resident["age_group"] = "Teen"
    aging_resident["age_years"] = 17
    aging_resident["role"] = "Student"
    aging_resident["profession_id"] = "student"
    resident_ages_before_year = {
        resident_id: resident["age_years"]
        for resident_id, resident in procedural_runtime_population["residents"].items()
    }
    procedural_town_game.state.year += 1
    procedural_town_game.advance_procedural_town_life(procedural_town_plan)
    assert all(
        resident["age_years"] == min(
            95,
            resident_ages_before_year[resident_id] + 1,
        )
        for resident_id, resident in procedural_runtime_population["residents"].items()
    )
    assert aging_resident["age_group"] == "Adult"
    assert aging_resident["role"] == "Settler"
    assert aging_resident["profession_id"] == "settler"
    procedural_town_game.state.aging_and_death_enabled = False
    aging_resident["age_group"] = "Teen"
    aging_resident["age_years"] = 17
    aging_resident["role"] = "Student"
    aging_resident["profession_id"] = "student"
    frozen_adult_age = int(romance_resident["age_years"])
    procedural_town_game.state.year += 1
    procedural_town_game.advance_procedural_town_life(procedural_town_plan)
    assert aging_resident["age_years"] == 18
    assert aging_resident["age_group"] == "Adult"
    assert romance_resident["age_years"] == frozen_adult_age
    ageless_resident_profile = (
        procedural_town_game.procedural_town_resident_profile_lines(
            romance_resident
        )
    )
    assert any("Life stage: Adult" in line for line in ageless_resident_profile)
    assert not any(line.startswith("Age:") for line in ageless_resident_profile)
    procedural_town_game.state.aging_and_death_enabled = True

    test_inventory = {
        "Turnip": 1,
        "Silver Turnip": 2,
        "Pond Minnow": 1,
    }
    assert inventory.inventory_crop_quantity(test_inventory, "Turnip") == 3
    assert inventory.inventory_fish_quantity(test_inventory) == 1
    assert inventory.consume_ingredient(test_inventory, "Any Fish", 1) == 1
    assert ui.fit_text("abcdef", 4) == "a..."
    assert ui.MenuItem("Talk").label == "Talk"
    assert MenuItem is ui.MenuItem
    assert ui.meter_text(5, 10, 6, detailed=False) == "###---"
    assert ui.meter_text(5, 10, 6, detailed=True) == "███░░░"
    wrapped_chips = ui.wrap_status_chips(
        [ui.status_chip("Spring 1"), ui.status_chip("Farm"), ui.status_chip("Sunny")],
        22,
    )
    assert len(wrapped_chips) == 2
    assert all(ui.visible_text_len(line) <= 22 for line in wrapped_chips)
    framed_menu = ui.menu_render_lines(
        "Household",
        [
            ui.MenuItem("Schedule", hint="Review today's family schedule."),
            ui.MenuItem("Locked outing", enabled=False, hint="Choose a free weekend first."),
        ],
        1,
        "Arrows move | Enter select | Esc cancel",
        ["Upcoming family occasions"],
        width=44,
    )
    plain_framed_menu = [ui.strip_ansi(line) for line in framed_menu]
    assert plain_framed_menu[0].startswith("┌ Household ")
    assert plain_framed_menu[-1] == "└" + "─" * 42 + "┘"
    assert any("[unavailable]" in line for line in plain_framed_menu)
    assert any("Choose a free weekend first" in line for line in plain_framed_menu)
    assert all(ui.visible_text_len(line) == 44 for line in framed_menu)
    scrolling_menu = ui.menu_render_lines(
        "Long Builder List",
        [ui.MenuItem(f"Option {index}") for index in range(20)],
        12,
        width=40,
        item_offset=10,
        max_visible_items=4,
    )
    plain_scrolling_menu = [ui.strip_ansi(line) for line in scrolling_menu]
    assert any("Option 12" in line and ">" in line for line in plain_scrolling_menu)
    assert not any("Option 0" in line for line in plain_scrolling_menu)
    assert any("↑ 10 more" in line for line in plain_scrolling_menu)
    assert any("↓ 6 more" in line for line in plain_scrolling_menu)
    long_menu_hint = (
        "This selected option has enough explanatory text to require multiple "
        "lines without entering the selectable menu area."
    )
    wrapped_menu_hint = ui.menu_context_lines(long_menu_hint, width=32)
    assert len(wrapped_menu_hint) >= 3
    assert all(ui.visible_text_len(line) <= 32 for line in wrapped_menu_hint)
    assert "selectable menu area" in " ".join(
        " ".join(wrapped_menu_hint).split()
    )
    original_ui_read_key = ui.read_key
    original_ui_draw_menu = ui.draw_menu
    disabled_menu_key_count = {"value": 0}
    disabled_menu_keys = iter(["UP", "\r", "DOWN", "\r"])

    def disabled_menu_read_key():
        disabled_menu_key_count["value"] += 1
        return next(disabled_menu_keys)

    try:
        ui.read_key = disabled_menu_read_key
        ui.draw_menu = lambda *args, **kwargs: None
        disabled_choice = ui.menu_select(
            "Disabled Choice Help",
            [
                ui.MenuItem("Locked", value="locked", enabled=False, hint="Need 10 Wood"),
                ui.MenuItem("Open", value="open", enabled=True),
            ],
        )
        assert disabled_choice and disabled_choice.value == "open"
        assert disabled_menu_key_count["value"] == 4
        captured_full_menu_footer = []
        ui.read_key = lambda: "b"
        ui.draw_menu = lambda _title, _items, _selected, footer="", _extra=None, **_kwargs: captured_full_menu_footer.append(footer)
        assert ui.menu_select(
            "Visible Cancellation",
            [ui.MenuItem("Continue", value="continue")],
            footer="Choose an option.",
        ) is None
        assert captured_full_menu_footer and "B/X/Esc/Q/Tab cancel" in captured_full_menu_footer[-1]
        ui.read_key = lambda: "\t"
        assert ui.menu_select(
            "Tab Cancellation",
            [ui.MenuItem("Continue", value="continue")],
        ) is None
        paging_keys = iter(["RIGHT", "\r"])
        ui.read_key = lambda: next(paging_keys)
        ui.draw_menu = lambda *args, **kwargs: None
        paged_choice = ui.menu_select(
            "Paged Builder List",
            [ui.MenuItem(f"Option {index}", value=index) for index in range(30)],
        )
        assert paged_choice and int(paged_choice.value) >= 4
    finally:
        ui.read_key = original_ui_read_key
        ui.draw_menu = original_ui_draw_menu

    panel_game = FarmGame()
    original_main_read_key = farmstead_main.read_key
    panel_key_count = {"value": 0}
    panel_keys = iter(["UP", "\r", "DOWN", "\r"])
    panel_draws = []

    def panel_read_key():
        panel_key_count["value"] += 1
        return next(panel_keys)

    try:
        farmstead_main.read_key = panel_read_key
        panel_game.draw_with_left_panel = (
            lambda panel_lines, panel_width, context_lines=None:
            panel_draws.append((list(panel_lines), list(context_lines or [])))
        )
        panel_choice = panel_game.vertical_panel_select(
            "Disabled Choice Help",
            [
                MenuItem(
                    "Locked",
                    value="locked",
                    enabled=False,
                    hint=long_menu_hint,
                ),
                MenuItem("Open", value="open", enabled=True),
            ],
            return_back=True,
        )
        assert panel_choice and panel_choice.value == "open"
        assert panel_key_count["value"] == 4
        assert any(
            long_menu_hint in " ".join(context_lines)
            for _panel_lines, context_lines in panel_draws
        )
        assert not any(
            "Hint:" in ui.strip_ansi(line)
            for panel_lines, _context_lines in panel_draws
            for line in panel_lines
        )
        one_action_items = [MenuItem("Use landmark", value="work", enabled=True)]
        panel_keys = iter(["DOWN", "\r"])
        visible_back_choice = panel_game.vertical_panel_select(
            "One-Action Landmark",
            one_action_items,
            return_back=True,
        )
        assert visible_back_choice and visible_back_choice.value == farmstead_main.MENU_BACK
        assert len(one_action_items) == 1
        assert any(
            "Back" in ui.strip_ansi(line)
            for panel_lines, _context_lines in panel_draws
            for line in panel_lines
        )
        panel_keys = iter(["b"])
        shortcut_back_choice = panel_game.vertical_panel_select(
            "Back Shortcut",
            [MenuItem("Continue", value="continue", enabled=True)],
            return_back=True,
        )
        assert shortcut_back_choice and shortcut_back_choice.value == farmstead_main.MENU_BACK
        panel_keys = iter(["END", "\r"])
        end_choice = panel_game.vertical_panel_select(
            "Long Menu End",
            [MenuItem(f"Row {index}", value=index, enabled=True) for index in range(30)],
        )
        assert end_choice and end_choice.value == 29
        panel_keys = iter(["END", "b"])
        panel_draws.clear()
        panel_game.vertical_panel_view(
            "Long Viewer",
            [f"Viewer row {index}" for index in range(40)],
            panel_height=14,
        )
        assert panel_draws and any(
            "Viewer row 39" in ui.strip_ansi(line)
            for line in panel_draws[-1][0]
        )
    finally:
        farmstead_main.read_key = original_main_read_key

    quest_exit_game = FarmGame()
    quest_exit_calls = []
    quest_exit_choices = iter([
        MenuItem("Back", value=farmstead_main.MENU_BACK, enabled=True),
        MenuItem("Back", value=farmstead_main.MENU_BACK, enabled=True),
    ])

    def quest_exit_selector(title, items, *args, **kwargs):
        quest_exit_calls.append((str(title), list(items)))
        return next(quest_exit_choices)

    quest_exit_game.vertical_panel_select = quest_exit_selector
    assert quest_exit_game.show_unified_quest_log_menu() == "__BACK__"
    assert quest_exit_game.show_planned_event_menu() == "__BACK__"
    assert len(quest_exit_calls) == 2
    assert all(
        sum(item.value == farmstead_main.MENU_BACK for item in items) == 1
        for _title, items in quest_exit_calls
    )

    dialogue_exit_game = FarmGame()
    dialogue_exit_game._draw_dialogue_frame = lambda *args, **kwargs: None
    dialogue_exit_game.dialogue_read_key = lambda: "b"
    dialogue_actor = {"id": "exit-audit", "name": "Exit Audit", "role": "Tester"}
    assert not dialogue_exit_game.dialogue_say(
        dialogue_actor, "This line can be left safely.", "audit", [],
    )
    assert dialogue_exit_game.dialogue_choose(
        dialogue_actor,
        "This choice can be left safely.",
        "audit",
        [("continue", "Continue", "")],
        [],
    ) == "goodbye"

    keybind_game = FarmGame()
    keybind_game.autosave_with_message = lambda message: keybind_game.set_message(message)
    keybind_game.state.inventory["Turnip Seeds"] = 1
    keybind_game.state.inventory["Carrot Seeds"] = 1
    starting_tool = keybind_game.state.selected_tool_index
    keybind_game.handle_key("e")
    assert keybind_game.state.selected_tool_index == (starting_tool + 1) % len(keybind_game.state.available_tools)
    keybind_game.handle_key("q")
    assert keybind_game.state.selected_tool_index == starting_tool
    keybind_game.handle_key("2")
    assert keybind_game.state.selected_seed in {"Turnip", "Carrot"}
    first_seed = keybind_game.state.selected_seed
    keybind_game.handle_key("1")
    assert keybind_game.state.selected_seed in {"Turnip", "Carrot"}
    assert keybind_game.state.selected_seed != first_seed
    numpad_game = FarmGame()
    numpad_game.autosave_with_message = lambda message: numpad_game.set_message(message)
    numpad_game.update_farm_animal_actors = lambda force=False: None
    diagonal_start = next(
        (x, y)
        for y in range(2, numpad_game.active_map_height() - 2)
        for x in range(2, numpad_game.active_map_width() - 2)
        if numpad_game.passable(x - 1, y - 1)
        and numpad_game.passable(x - 1, y)
        and numpad_game.passable(x, y - 1)
    )
    numpad_game.state.player_x, numpad_game.state.player_y = diagonal_start
    numpad_game.handle_key("NUM7")
    assert (numpad_game.state.player_x, numpad_game.state.player_y) == (
        diagonal_start[0] - 1, diagonal_start[1] - 1,
    )
    diagonal_test_random_state = random.getstate()
    blocked_start = (numpad_game.state.player_x, numpad_game.state.player_y)
    original_numpad_passable = numpad_game.passable
    numpad_game.passable = lambda x, y, ignore_travel_follower_id=None: (
        False if (x, y) == (blocked_start[0] + 1, blocked_start[1])
        else original_numpad_passable(x, y, ignore_travel_follower_id)
    )
    numpad_game.handle_key("NUM3")
    assert (numpad_game.state.player_x, numpad_game.state.player_y) == (
        blocked_start[0] + 1,
        blocked_start[1] + 1,
    ), "One blocked side should not prevent an otherwise open diagonal"
    numpad_game.state.player_x, numpad_game.state.player_y = blocked_start
    numpad_game.passable = lambda x, y, ignore_travel_follower_id=None: (
        False
        if (x, y) in {
            (blocked_start[0] + 1, blocked_start[1]),
            (blocked_start[0], blocked_start[1] + 1),
        }
        else original_numpad_passable(x, y, ignore_travel_follower_id)
    )
    numpad_game.handle_key("NUM3")
    assert (numpad_game.state.player_x, numpad_game.state.player_y) == (
        blocked_start[0] + 1,
        blocked_start[1] + 1,
    ), "Open diagonal destinations should remain reachable between blocked side tiles"
    numpad_game.state.player_x, numpad_game.state.player_y = blocked_start
    diagonal_destination = (blocked_start[0] + 1, blocked_start[1] + 1)
    numpad_game.passable = lambda x, y, ignore_travel_follower_id=None: (
        False
        if (x, y) == diagonal_destination
        else original_numpad_passable(x, y, ignore_travel_follower_id)
    )
    numpad_game.handle_key("NUM3")
    assert (numpad_game.state.player_x, numpad_game.state.player_y) == blocked_start, (
        "A genuinely blocked diagonal destination should remain impassable"
    )
    numpad_game.passable = original_numpad_passable
    random.setstate(diagonal_test_random_state)
    tool_called = {"value": False}
    keybind_game.use_tool = lambda: tool_called.__setitem__("value", True)
    keybind_game.handle_key("f")
    assert tool_called["value"]
    keybind_game.handle_key("\x1b")
    assert keybind_game.running
    assert "Esc again" in keybind_game.state.message
    keybind_game.handle_key("w")
    assert keybind_game.running
    assert keybind_game._escape_quit_armed_until == 0.0
    keybind_game.handle_key("\x1b")
    assert keybind_game.running
    keybind_game.handle_key("\x1b")
    assert not keybind_game.running

    battle_keybind_game = BattleGame()
    battle_keybind_game.state = "inspect"
    battle_keybind_game.cursor = (5, 5)
    battle_keybind_game.handle_key("NUM9", SimpleNamespace())
    assert battle_keybind_game.cursor == (6, 4)
    battle_keybind_game.state = "command"
    battle_keybind_game.handle_key("z", SimpleNamespace())
    assert battle_keybind_game.state == "inspect"
    battle_keybind_game.state = "skill_menu"
    battle_keybind_game.handle_key("x", SimpleNamespace())
    assert battle_keybind_game.state == "skill_group_menu"

    sleep_combat_game = FarmGame()
    sleep_combat_game.save = lambda *args, **kwargs: True
    sleep_combat_game.state.combat_party_progress["player"] = {"hp_bonus": 8, "mp_bonus": 4, "damage_bonus": 2}
    sleep_profile = build_player_combat_profile(sleep_combat_game.state)
    assert sleep_profile["max_hp"] == sleep_profile["base_max_hp"] + 8
    assert sleep_profile["max_focus"] == sleep_profile["base_max_focus"] + 4
    assert sleep_profile["attack"] == sleep_profile["base_attack"] + 2
    sleep_combat_game.state.combat_current_hp = 3
    sleep_combat_game.state.combat_focus = 0
    sleep_combat_game.sleep(force=True)
    rested_profile = build_player_combat_profile(sleep_combat_game.state)
    assert sleep_combat_game.state.stamina == sleep_combat_game.max_stamina()
    assert sleep_combat_game.state.combat_current_hp == rested_profile["max_hp"]
    assert sleep_combat_game.state.combat_focus == rested_profile["max_focus"]
    normalized_boosted_state = state.GameState(
        combat_party_progress={"player": {"hp_bonus": 8, "mp_bonus": 4}},
        combat_current_hp=999,
        combat_focus=999,
    )
    normalized_profile = build_player_combat_profile(normalized_boosted_state)
    assert normalized_boosted_state.combat_current_hp == normalized_profile["max_hp"]
    assert normalized_boosted_state.combat_focus == normalized_profile["max_focus"]
    handoff_game = configure_game_from_request(
        BattleGame(),
        BattleRequest(
            source="ascii_farmstead",
            enemy_counts={"Slime": 1},
            party_ids=["Rook"],
            return_context={
                "farm_player": rested_profile,
                "farm_party_limit": 1,
                "farm_party_tactic": "Balanced",
            },
        ),
    )
    handoff_player = next(hero for hero in handoff_game.heroes if hero.name == rested_profile["name"])
    assert handoff_game.frame_delay == 0.025
    assert handoff_player.max_hp == rested_profile["max_hp"]
    assert handoff_player.max_mp == rested_profile["max_focus"]
    assert handoff_player.hp == rested_profile["max_hp"]
    assert handoff_player.mp == rested_profile["max_focus"]

    food_recovery_game = FarmGame()
    food_recovery_game.save = lambda *args, **kwargs: True
    food_recovery_game.state.stamina = 100
    food_recovery_game.state.combat_current_hp = 5
    food_recovery_game.state.inventory["Field Snack"] = 1
    assert food_recovery_game.eat_food("Field Snack")
    assert food_recovery_game.state.stamina > 100
    assert food_recovery_game.state.combat_current_hp > 5
    food_recovery_game.state.stamina = 100
    food_recovery_game.state.combat_focus = 0
    food_recovery_game.state.inventory["Honey"] = 1
    assert food_recovery_game.eat_food("Honey")
    assert food_recovery_game.state.combat_focus > 0
    food_recovery_game.state.inventory["Pantry Stew"] = 2
    food_profile = build_player_combat_profile(food_recovery_game.state)
    assert food_profile["combat_items"].get("Pantry Stew") == 2
    assert any(item.name == "Pantry Stew" and item.effect == "heal" for item in BattleGame().items)
    assert any(item.name == "Honey" and item.effect == "mp" for item in BattleGame().items)
    batch_food_game = FarmGame()
    batch_food_game.save = lambda *args, **kwargs: True
    batch_food_game.state.stamina = 40
    batch_food_game.state.combat_current_hp = 10
    batch_food_game.state.inventory["Field Snack"] = 3
    assert batch_food_game.eat_food("Field Snack", qty=2)
    assert batch_food_game.state.inventory["Field Snack"] == 1
    assert batch_food_game.state.stamina == 64
    assert batch_food_game.state.combat_current_hp > 10
    batch_potion_game = FarmGame()
    batch_potion_game.save = lambda *args, **kwargs: True
    batch_potion_game.state.combat_current_hp = 1
    batch_potion_game.state.inventory["Potion"] = 2
    assert batch_potion_game.use_consumable_item("Potion", qty=2)
    assert batch_potion_game.state.inventory["Potion"] == 0
    assert batch_potion_game.state.combat_current_hp == 29
    batch_potion_game.state.combat_focus = 0
    batch_potion_game.state.inventory["Ether"] = 2
    assert batch_potion_game.use_consumable_item("Ether", qty=2)
    assert batch_potion_game.state.inventory["Ether"] == 0
    assert batch_potion_game.state.combat_focus == min(build_player_combat_profile(batch_potion_game.state)["max_focus"], 12)
    assert build_player_combat_profile(batch_potion_game.state)["combat_items"].get("Potion", 0) == 0
    batch_potion_game.state.inventory["Potion"] = 3
    assert build_player_combat_profile(batch_potion_game.state)["combat_items"].get("Potion") == 3
    expected_gear = {
        "weapon": ["Rusty Sword", "Stone Club", "Copper Sword", "Iron Sword", "Copper Hammer", "Iron Hammer", "Short Bow"],
        "armor": ["Work Clothes", "Padded Jacket", "Copper Mail", "Iron Mail", "Explorer Coat"],
        "accessory": ["Miner's Charm", "Bat Wing Charm", "Stone Ring", "Focus Band", "Lucky Button"],
    }
    catalog_state = state.GameState()
    for slot, names in expected_gear.items():
        _field_name, gear_data, _default = COMBAT_EQUIPMENT_SLOTS[slot]
        for name in names:
            assert name in gear_data, f"missing {slot} gear: {name}"
            record = gear_data[name]
            assert record.get("id")
            assert record.get("name") == name
            assert record.get("slot") == slot
            assert record.get("description")
            assert isinstance(record.get("cost"), dict)
            assert name in catalog_state.inventory
            money = int(record.get("cost", {}).get("money", 0) or 0)
            assert money >= 0
            for material, qty in (record.get("cost", {}).get("items", {}) or {}).items():
                assert material in catalog_state.inventory, f"{name} uses unknown material {material}"
                assert int(qty) > 0

    town_npc_ids = {str(npc["id"]) for npc in data.TOWN_NPC_DEFINITIONS}
    assert set(data.TOWN_NPC_DIALOGUE_DATA) == town_npc_ids
    assert set(data.TOWN_NPC_CONTEXTUAL_DIALOGUE_DATA) == town_npc_ids
    for npc_id in sorted(town_npc_ids):
        dialogue_record = data.TOWN_NPC_DIALOGUE_DATA[npc_id]
        assert dialogue_record.get("profile"), f"{npc_id} is missing a dialogue profile"
        assert dialogue_record.get("talk"), f"{npc_id} is missing talk dialogue"
        context_record = data.TOWN_NPC_CONTEXTUAL_DIALOGUE_DATA[npc_id]
        assert isinstance(context_record, dict) and context_record, f"{npc_id} is missing contextual dialogue"
        for category, lines in context_record.items():
            assert category, f"{npc_id} has a blank contextual dialogue category"
            assert isinstance(lines, list) and lines, f"{npc_id}:{category} has no dialogue lines"
            for raw_line in lines:
                text = str(raw_line.get("text", "") if isinstance(raw_line, dict) else raw_line)
                assert text.strip(), f"{npc_id}:{category} has blank dialogue"
                assert "\ufffd" not in text, f"{npc_id}:{category} has malformed replacement characters"
    combat_salvage_names = {
        "Coin", "Shard", "Tonic", "Gel", "Fang", "Spore Cap", "Stone", "Throwing Knife",
        "Guard Tonic", "Potion", "Ether", "Cleanse Kit", "Root Fiber", "Relic Cache", "Hide",
    }

    def assert_known_inventory_items(items, context):
        for item_name, qty in (items or {}).items():
            assert item_name in catalog_state.inventory, f"{context} uses unknown item {item_name}"
            assert int(qty) > 0

    assert data.AUTOMATION_OBJECT_DATA
    expected_automation = {
        "Sprinkler", "Quality Sprinkler", "Rain Barrel", "Pipe Segment",
        "Irrigation Pump", "Water Tank", "Harvest Crate", "Shipping Loader", "Seed Hopper",
    }
    assert expected_automation.issubset(set(data.AUTOMATION_OBJECT_DATA))
    for item_name, record in data.AUTOMATION_OBJECT_DATA.items():
        assert item_name in data.INFRASTRUCTURE_DATA
        assert record.get("item_id")
        assert record.get("display_name")
        assert len(str(record.get("symbol", ""))) == 1
        assert record.get("description")
        assert record.get("footprint", [1, 1])
        assert "Farm" in record.get("place_locations", [])
        assert "Farm" in record.get("works_on", [])
        assert "Claim" in record.get("works_on", [])
        assert isinstance(record.get("automation"), dict) and record["automation"].get("kind")
        assert item_name in catalog_state.inventory
        assert_known_inventory_items(record.get("cost", {}), f"automation {item_name} cost")
    assert data.INFRASTRUCTURE_DATA["Pipe Segment"].get("walkable") is True
    assert not furniture_art.validate_furniture_art()
    legacy_furniture_visuals = {
        "Wooden Chair": ("╥",),
        "Armchair": ("▰",),
        "Bed": ("○▓▓", "╚═╝"),
        "Wooden Table": ("╾╼",),
        "Bookshelf": ("▥", "▤"),
        "Decorative Rug": ("╭◆╮", "╰◇╯"),
        "House Plant": ("♣",),
        "Wall Calendar": ("▧",),
        "Wall Mirror": ("◉",),
        "Wall Art": ("◇",),
        "Dresser": ("▤▤",),
        "Television": ("▣",),
        "Shelf": ("▥▤",),
        "Kitchen Counter": ("╾○▤╼",),
        "Couch": ("╭▓╮",),
        "Large Rug": ("╭───╮", "│◆◇◆│", "╰───╯"),
        "Nightstand": ("▤",),
        "Wash Basin": ("◉◉",),
        "Pantry": ("▦▦",),
        "Fireplace": ("╭♨╮",),
        "Writing Desk": ("╾▤",),
        "Tea Table": ("●",),
        "Standing Lamp": ("✦",),
        "Flower Vase": ("⚘",),
        "Wardrobe": ("▥▥",),
        "Room Divider": ("│", "│"),
        "Crib": ("╫╫",),
        "Child Bed": ("○▓",),
        "Toy Shelf": ("▦",),
        "Study Desk": ("╾▧",),
        "Family Table": ("╾◆╼",),
        "Keepsake Chest": ("▰◆",),
    }
    for furniture_name, expected_rows in legacy_furniture_visuals.items():
        assert furniture_art.furniture_art_rows(furniture_name, detailed=True) == expected_rows
        simple_rows = furniture_art.furniture_art_rows(furniture_name, detailed=False)
        assert simple_rows
        assert [len(row) for row in simple_rows] == [len(row) for row in expected_rows]
        expected_size = tuple(data.INFRASTRUCTURE_DATA[furniture_name].get("footprint", [1, 1]))
        assert furniture_art.furniture_art_size(furniture_name) == expected_size
        for rotation in range(4):
            rotated_rows = furniture_art.furniture_art_rows(furniture_name, True, rotation)
            assert rotated_rows and len({len(row) for row in rotated_rows}) == 1
            for offset_y, row in enumerate(rotated_rows):
                for offset_x, _glyph in enumerate(row):
                    cell = furniture_art.furniture_art_cell(
                        furniture_name, offset_x, offset_y, True, rotation,
                    )
                    assert cell is not None and cell[1] != "default"
    assert not furniture_catalog.validate_furniture_catalog()
    expanded_furniture_names = set(furniture_catalog.FURNITURE_CATALOG_DATA)
    assert len(expanded_furniture_names) == 300
    assert expanded_furniture_names.issubset(data.INFRASTRUCTURE_DATA)
    assert expanded_furniture_names.issubset(furniture_art.FURNITURE_ART)
    assert all(name in catalog_state.inventory for name in expanded_furniture_names)
    assert {
        str(data.INFRASTRUCTURE_DATA[name].get("catalog_collection", ""))
        for name in expanded_furniture_names
    } == {"Hearthwood", "Coastal", "Manor"}
    assert all(
        sum(
            1 for name in expanded_furniture_names
            if data.INFRASTRUCTURE_DATA[name].get("catalog_collection") == collection
        ) == 100
        for collection in ("Hearthwood", "Coastal", "Manor")
    )
    assert {
        "Hearthwood Captain Chair",
        "Coastal Apothecary Cabinet",
        "Manor Long Hall Carpet",
    }.issubset(expanded_furniture_names)
    expected_catalog_groups = {
        "Seating", "Tables & Work", "Storage", "Bedroom", "Kitchen",
        "Bath", "Lighting & Decor", "Wall Decor", "Rugs",
    }
    assert {
        str(data.INFRASTRUCTURE_DATA[name].get("furniture_group", ""))
        for name in expanded_furniture_names
    } == expected_catalog_groups
    catalog_container_names = {
        name for name in expanded_furniture_names
        if data.INFRASTRUCTURE_DATA[name].get("container_profile")
    }
    assert catalog_container_names
    assert catalog_container_names.issubset(container_system.PLAYER_CONTAINER_DATA)
    all_furniture_records = {
        name: record
        for name, record in data.INFRASTRUCTURE_DATA.items()
        if record.get("category") == "furniture"
    }
    assert len(all_furniture_records) == 353
    assert not furniture_actions.furniture_action_coverage(all_furniture_records)
    assert all(
        str(record.get("furniture_action", "")) in furniture_actions.FURNITURE_ACTION_LABELS
        for record in all_furniture_records.values()
    )
    assert furniture_art.furniture_display_glyph("[", "wood", True) == "╭"
    assert furniture_art.furniture_display_glyph("#", "linen", True) == "░"
    assert furniture_art.furniture_display_glyph("F", "fire", True) == "♨"
    assert furniture_art.furniture_display_glyph("~", "water", True) == "≈"
    assert furniture_art.furniture_display_glyph("[", "wood", False) == "["
    catalog_visual_signatures = set()
    for furniture_name in furniture_catalog.FURNITURE_CATALOG_DATA:
        for rotation in range(4):
            source_rows = furniture_art.furniture_art_rows(
                furniture_name, True, rotation,
            )
            display_rows = furniture_art.furniture_display_rows(
                furniture_name, True, rotation,
            )
            assert len(display_rows) == len(source_rows)
            assert all(
                len(display_row) == len(source_row)
                for display_row, source_row in zip(display_rows, source_rows)
            )
            assert all(len(glyph) == 1 for row in display_rows for glyph in row)
            assert not ({"╞", "╡", "▓", "❬", "❭"} & set("".join(display_rows)))
        catalog_visual_signatures.add(
            furniture_art.furniture_display_rows(furniture_name, True, 0)
        )
        assert furniture_art.furniture_display_rows(
            furniture_name, False, 0,
        ) == furniture_art.furniture_art_rows(furniture_name, False, 0)
    assert len(catalog_visual_signatures) >= 90
    assert furniture_art.furniture_display_rows(
        "Hearthwood Single Bed", True, 0,
    ) == ("╭○░╮", "╰──╯")
    assert furniture_art.furniture_display_rows(
        "Hearthwood Stove Range", True, 0,
    ) == ("╭♨─♨╮",)
    assert furniture_art.furniture_display_material_role(
        "Hearthwood Bathtub", "[", "water",
    ) == "stone"
    assert furniture_art.furniture_display_material_role(
        "Hearthwood Indoor Planter", "f", "accent",
    ) == "plant"

    expanded_catalog_game = FarmGame()
    expanded_catalog_game.state.location = "HouseInterior"
    expanded_catalog_game.house_map = [
        list("#" * 70) if y in {0, 23} else list("#" + "." * 68 + "#")
        for y in range(24)
    ]
    expanded_catalog_game.state.player_x = 2
    expanded_catalog_game.state.player_y = 2
    assert len({
        expanded_catalog_game.catalog_furniture_color({
            "glyph": "=", "material_role": "wood", "collection": collection,
        })
        for collection in ("Hearthwood", "Coastal", "Manor")
    }) == 3

    furniture_mechanics_game = FarmGame()
    furniture_mechanics_game.state.location = "HouseInterior"
    furniture_mechanics_game.house_map = [list("." * 64) for _ in range(28)]
    furniture_mechanics_game.state.player_x = 4
    furniture_mechanics_game.state.player_y = 5
    furniture_mechanics_game.state.stamina = 40
    furniture_mechanics_game.autosave_with_message = furniture_mechanics_game.set_message
    furniture_mechanics_game.vertical_panel_view = lambda *args, **kwargs: None

    assert furniture_mechanics_game.use_functional_furniture("Wooden Chair", 5, 5)
    assert furniture_mechanics_game.state.player_furniture_pose.get("pose") == "seated"
    assert (furniture_mechanics_game.state.player_x, furniture_mechanics_game.state.player_y) == (5, 5)
    furniture_mechanics_game.move(1, 0)
    assert not furniture_mechanics_game.state.player_furniture_pose

    original_furniture_select = furniture_mechanics_game.vertical_panel_select
    furniture_mechanics_game.vertical_panel_select = (
        lambda *args, **kwargs: MenuItem(label="Water and tend", value="water", enabled=True)
    )
    assert furniture_mechanics_game.use_functional_furniture("House Plant", 8, 8)
    furniture_mechanics_game.vertical_panel_select = original_furniture_select
    plant_key = furniture_mechanics_game.furniture_state_key("House Plant", 8, 8)
    assert furniture_mechanics_game.state.furniture_states[plant_key]["care"] == 1
    assert furniture_mechanics_game.state.furniture_states[plant_key]["watered_day"] == furniture_mechanics_game.town_npc_day_key()

    assert furniture_mechanics_game.use_functional_furniture("Standing Lamp", 9, 8)
    lamp_key = furniture_mechanics_game.furniture_state_key("Standing Lamp", 9, 8)
    assert furniture_mechanics_game.state.furniture_states[lamp_key]["light_on"] is False
    assert furniture_mechanics_game.use_functional_furniture("Standing Lamp", 9, 8)
    assert furniture_mechanics_game.state.furniture_states[lamp_key]["light_on"] is True

    _journal_key, journal_state = furniture_mechanics_game.furniture_state_record("Writing Desk", 10, 8)
    furniture_mechanics_game.write_furniture_journal_entry("Writing Desk", journal_state)
    assert furniture_mechanics_game.state.furniture_journal_entries[-1]["furniture"] == "Writing Desk"

    furniture_mechanics_game.state.combat_current_hp = max(1, furniture_mechanics_game.state.combat_max_hp - 5)
    before_bath_hp = furniture_mechanics_game.state.combat_current_hp
    assert furniture_mechanics_game.use_functional_furniture("Wash Basin", 11, 8)
    assert furniture_mechanics_game.state.combat_current_hp > before_bath_hp
    assert furniture_mechanics_game.use_functional_furniture("Wall Art", 12, 8)
    furniture_mechanics_game.vertical_panel_select = (
        lambda *args, **kwargs: MenuItem(label="Feed and observe", value="observe", enabled=True)
    )
    assert furniture_mechanics_game.use_functional_furniture("Hearthwood Aquarium", 13, 8)
    furniture_mechanics_game.vertical_panel_select = original_furniture_select
    aquarium_key = furniture_mechanics_game.furniture_state_key("Hearthwood Aquarium", 13, 8)
    aquarium_state = furniture_mechanics_game.state.furniture_states[aquarium_key]
    aquarium_state["fish"] = {"Pond Minnow": 2}
    aquarium_state["feedings"] = 3
    aquarium_state.pop("fed_day", None)
    furniture_mechanics_game.observe_furniture_aquarium(
        "Hearthwood Aquarium", aquarium_state, 2,
    )
    assert aquarium_state["feedings"] == 4
    assert sum(aquarium_state["fish"].values()) == 3
    furniture_mechanics_game.vertical_panel_select = (
        lambda *args, **kwargs: MenuItem(label="Clean and straighten rug", value="clean", enabled=True)
    )
    assert furniture_mechanics_game.use_functional_furniture("Decorative Rug", 14, 8)
    furniture_mechanics_game.vertical_panel_select = original_furniture_select
    rug_key = furniture_mechanics_game.furniture_state_key("Decorative Rug", 14, 8)
    assert furniture_mechanics_game.state.furniture_states[rug_key]["straightened"] is True

    # Original farmhouse furniture has dedicated mechanics rather than generic
    # flavor-only fallbacks. Television channels persist and the cooking station
    # teaches no more than one recipe in a given week.
    _tv_key, tv_state = furniture_mechanics_game.furniture_state_record("Television", 16, 8)
    recipes_before_tv = len(furniture_mechanics_game.known_recipe_names())
    furniture_mechanics_game.watch_furniture_tv_channel("Television", tv_state, "cooking", 1)
    recipes_after_tv = len(furniture_mechanics_game.known_recipe_names())
    assert tv_state["channel"] == "cooking"
    assert tv_state["powered_on"] is True
    assert recipes_after_tv >= recipes_before_tv
    assert tv_state["cooking_broadcast_week"] == furniture_mechanics_game.bounty_week_key()
    furniture_mechanics_game.watch_furniture_tv_channel("Television", tv_state, "cooking", 1)
    assert len(furniture_mechanics_game.known_recipe_names()) == recipes_after_tv

    _nightstand_key, nightstand_state = furniture_mechanics_game.furniture_state_record("Nightstand", 17, 8)
    focus_before_reading = max(0, int(furniture_mechanics_game.state.combat_max_focus) - 10)
    furniture_mechanics_game.state.combat_focus = focus_before_reading
    furniture_mechanics_game.use_nightstand_bedside_reading("Nightstand", nightstand_state, 2)
    assert furniture_mechanics_game.state.combat_focus > focus_before_reading
    assert nightstand_state["bedside_read_day"] == furniture_mechanics_game.town_npc_day_key()

    furniture_mechanics_game.state.children = [{"id": 991, "name": "Robin"}]
    family_bond_before_furniture = furniture_mechanics_game.family_bond_score()
    furniture_mechanics_game.vertical_panel_select = (
        lambda *args, **kwargs: MenuItem(label="Read a bedtime story", value="story", enabled=True)
    )
    assert furniture_mechanics_game.use_functional_furniture("Child Bed", 18, 8)
    furniture_mechanics_game.vertical_panel_select = original_furniture_select
    assert furniture_mechanics_game.family_bond_score() > family_bond_before_furniture

    furniture_mechanics_game.vertical_panel_select = (
        lambda *args, **kwargs: MenuItem(label="Warm up by the fire", value="warm", enabled=True)
    )
    assert furniture_mechanics_game.use_functional_furniture("Fireplace", 19, 8)
    furniture_mechanics_game.vertical_panel_select = original_furniture_select
    hearth_key = furniture_mechanics_game.furniture_state_key("Fireplace", 19, 8)
    assert furniture_mechanics_game.state.furniture_states[hearth_key]["warmed_day"] == furniture_mechanics_game.town_npc_day_key()

    furniture_mechanics_game.set_placed_object(15, 8, "Room Divider")
    placed_divider_key = furniture_mechanics_game.obj_key(15, 8)
    assert not furniture_mechanics_game.passable(15, 8)
    assert furniture_mechanics_game.use_functional_furniture(
        "Room Divider", 15, 8, object_key=placed_divider_key,
    )
    divider_key = f"placed:{placed_divider_key}:Room Divider"
    assert furniture_mechanics_game.state.furniture_states[divider_key]["open"] is True
    assert furniture_mechanics_game.passable(15, 8)
    assert furniture_actions.furniture_action_id(
        "Hearthwood Tub Screen", data.INFRASTRUCTURE_DATA["Hearthwood Tub Screen"],
    ) == "privacy"
    furniture_mechanics_game.set_placed_object(6, 6, "Standing Lamp")
    furniture_mechanics_game.set_placed_object(7, 6, "Wooden Table")
    support_bonus, support_names = furniture_mechanics_game.furniture_room_support(
        "seat", 5, 5,
    )
    assert support_bonus >= 2
    assert {"Standing Lamp", "Wooden Table"}.issubset(set(support_names))
    chair_key = furniture_mechanics_game.furniture_state_key("Wooden Chair", 5, 5)
    chair_state = furniture_mechanics_game.state.furniture_states[chair_key]
    chair_state["uses"] = 15
    assert furniture_mechanics_game.furniture_familiarity_label(chair_state) == "Trusted"
    effectiveness, _supporters = furniture_mechanics_game.furniture_effectiveness(
        "seat", 5, 5, chair_state,
    )
    assert effectiveness >= 4
    table_key = furniture_mechanics_game.obj_key(7, 6)
    _table_state_key, table_state = furniture_mechanics_game.furniture_state_record(
        "Wooden Table", 7, 6, object_key=table_key,
    )
    furniture_mechanics_game.state.inventory["Quartz"] = 1
    comfort_before_display = furniture_mechanics_game.house_comfort_score()
    assert furniture_mechanics_game.furniture_place_display_item(
        "Wooden Table", table_state, "Quartz",
    )
    assert furniture_mechanics_game.state.inventory.get("Quartz", 0) == 0
    assert table_state["display_item"] == "Quartz"
    assert furniture_mechanics_game.house_comfort_score() > comfort_before_display
    assert "displayed Quartz" in furniture_mechanics_game.object_store_block_reason(
        table_key, "Wooden Table",
    )
    assert furniture_mechanics_game.furniture_take_display_item(
        "Wooden Table", table_state, quiet=True,
    )
    assert furniture_mechanics_game.state.inventory["Quartz"] == 1
    aquarium_state["fish"] = {"Pond Minnow": 1}
    furniture_mechanics_game.set_placed_object(20, 8, "Hearthwood Aquarium")
    placed_aquarium_key = furniture_mechanics_game.obj_key(20, 8)
    placed_aquarium_state_key = f"placed:{placed_aquarium_key}:Hearthwood Aquarium"
    furniture_mechanics_game.state.furniture_states[placed_aquarium_state_key] = aquarium_state
    assert "remove the aquarium's fish" in furniture_mechanics_game.object_store_block_reason(
        placed_aquarium_key, "Hearthwood Aquarium",
    )
    for furniture_name in sorted(expanded_furniture_names):
        furniture_data = data.INFRASTRUCTURE_DATA[furniture_name]
        art_rows = furniture_art.furniture_art_rows(furniture_name)
        assert art_rows
        assert tuple(furniture_data["footprint"]) == (len(art_rows[0]), len(art_rows))
        assert int(furniture_data.get("price", 0)) > 0
        assert furniture_data.get("category") == "furniture"
        expanded_catalog_game.state.placed_objects = {}
        expanded_catalog_game.state.placed_floor_objects = {}
        expanded_catalog_game.state.placed_object_rotations = {}
        expanded_catalog_game.state.placed_floor_object_rotations = {}
        expanded_catalog_game.state.placed_object_finishes = {}
        expanded_catalog_game.state.placed_floor_object_finishes = {}
        placement = (
            (10, 0)
            if furniture_data.get("placement_surface") == "wall"
            else (10, 5)
        )
        assert expanded_catalog_game.can_place_object(furniture_name, *placement)[0], furniture_name
        expanded_catalog_game.set_placed_object(*placement, furniture_name)
        assert expanded_catalog_game.get_placed_object(*placement) == furniture_name
        rendered = ANSI_CSI_RE.sub(
            "", expanded_catalog_game.render_tile(*placement),
        )
        assert len(rendered) == 1
        key = expanded_catalog_game.obj_key(*placement)
        if furniture_data.get("placement_layer") == "floor":
            assert expanded_catalog_game.state.placed_floor_objects[key] == furniture_name
        else:
            assert expanded_catalog_game.state.placed_objects[key] == furniture_name
    assert tuple(furniture_art.FURNITURE_FINISHES) == (
        "Natural", "Whitewashed", "Walnut", "Cherry", "Forest", "Ocean", "Royal",
    )
    assert furniture_art.normalize_furniture_finish("ocean") == "Ocean"
    assert furniture_art.normalize_furniture_finish("unknown") == "Natural"
    assert furniture_art.furniture_component_at("Kitchen Suite", 1, 1, 0) == "cook"
    assert furniture_art.furniture_component_at("Kitchen Suite", 0, 1, 1) == "cook"
    assert furniture_art.furniture_component_at("Kitchen Suite", 0, 4, 1) == "wash"
    assert furniture_art.furniture_component_at("Kitchen Suite", 7, 0, 2) == "cook"
    assert furniture_art.furniture_component_at("Kitchen Suite", 1, 7, 3) == "cook"
    assert furniture_art.furniture_component_at("Reading Nook", 0, 2, 0) == "bookshelf"
    assert furniture_art.furniture_component_at("Reading Nook", 8, 2, 0) == "rest"
    assert furniture_art.furniture_component_at("Dressing Vanity", 3, 0, 0) == "mirror"
    assert furniture_art.furniture_component_at("Dressing Vanity", 3, 2, 0) == "storage"
    large_furniture_functions = {
        "Four-Poster Bed": "sleep",
        "Dining Set": "family_meal",
        "Library Bookcase": "bookshelf",
        "Sectional Couch": "rest",
        "Kitchen Suite": "cook",
        "Display Counter": "display_storage",
        "Workshop Bench": "craft",
        "Bathing Tub": "bathe",
        "Dressing Vanity": "mirror",
        "Storage Hutch": "storage",
        "Stone Hearth": "hearth",
        "Reading Nook": "bookshelf",
        "Parlor Set": "rest",
    }
    for furniture_name, expected_function in large_furniture_functions.items():
        furniture_record = data.INFRASTRUCTURE_DATA[furniture_name]
        assert furniture_record["category"] == "furniture"
        assert furniture_record["furniture_function"] == expected_function
        assert tuple(furniture_record["footprint"]) == furniture_art.furniture_art_size(furniture_name)
        detailed_rows = furniture_art.furniture_art_rows(furniture_name, detailed=True)
        simple_rows = furniture_art.furniture_art_rows(furniture_name, detailed=False)
        assert detailed_rows and simple_rows
        assert [len(row) for row in detailed_rows] == [len(row) for row in simple_rows]

    furniture_art_game = FarmGame()
    furniture_art_game.state.location = "HouseInterior"
    furniture_art_game.house_map = [list("." * 40) for _ in range(16)]
    furniture_art_game.state.player_x = 1
    furniture_art_game.state.player_y = 1
    for furniture_name, artwork in legacy_furniture_visuals.items():
        furniture_art_game.state.placed_objects = {}
        furniture_art_game.state.placed_floor_objects = {}
        furniture_art_game.state.placed_object_rotations = {}
        furniture_art_game.set_placed_object(5, 5, furniture_name)
        for offset_y, artwork_row in enumerate(artwork):
            for offset_x, expected_glyph in enumerate(artwork_row):
                rendered = ANSI_CSI_RE.sub(
                    "",
                    furniture_art_game.render_placed_object(
                        furniture_name, 5 + offset_x, 5 + offset_y, 5, 5,
                    ),
                )
                assert rendered == expected_glyph
        furniture_art_game.state.detailed_glyphs_enabled = False
        simple_glyph = ANSI_CSI_RE.sub(
            "", furniture_art_game.render_placed_object(furniture_name, 5, 5, 5, 5),
        )
        assert simple_glyph == furniture_art.furniture_art_rows(furniture_name, False)[0][0]
        furniture_art_game.state.detailed_glyphs_enabled = True
    furniture_art_game.state.placed_objects = {}
    furniture_art_game.state.placed_floor_objects = {}
    furniture_art_game.set_placed_object(5, 5, "Television")
    television_object_key = furniture_art_game.obj_key(5, 5)
    _television_state_key, television_visual_state = furniture_art_game.furniture_state_record(
        "Television", 5, 5, object_key=television_object_key,
    )
    television_off_render = furniture_art_game.render_placed_object("Television", 5, 5, 5, 5)
    assert support.C.FLOOR_SHADOW in television_off_render
    television_visual_state.update({"powered_on": True, "channel": "cooking"})
    television_on_render = furniture_art_game.render_placed_object("Television", 5, 5, 5, 5)
    assert support.C.LAMP in television_on_render
    for furniture_name in large_furniture_functions:
        furniture_art_game.state.placed_objects = {}
        furniture_art_game.state.placed_object_rotations = {}
        assert furniture_art_game.can_place_object(furniture_name, 5, 5)[0]
        furniture_art_game.set_placed_object(5, 5, furniture_name)
        artwork = furniture_art.furniture_art_rows(furniture_name, detailed=True)
        for offset_y, artwork_row in enumerate(artwork):
            for offset_x, expected_glyph in enumerate(artwork_row):
                tile_x, tile_y = 5 + offset_x, 5 + offset_y
                assert furniture_art_game.get_placed_object(tile_x, tile_y) == furniture_name
                rendered = ANSI_CSI_RE.sub(
                    "",
                    furniture_art_game.render_placed_object(
                        furniture_name, tile_x, tile_y, 5, 5,
                    ),
                )
                assert rendered == expected_glyph
                expected_walkable = bool(furniture_art.furniture_walkable_kind(
                    furniture_name, offset_x, offset_y,
                ))
                assert furniture_art_game.passable(tile_x, tile_y) is expected_walkable
        last_x = 5 + len(artwork[0]) - 1
        last_y = 5 + len(artwork) - 1
        assert furniture_art_game.target_action_hint(last_x, last_y).startswith("Z:")

        rotated_rows = furniture_art.furniture_art_rows(
            furniture_name, detailed=True, rotation=1,
        )
        assert furniture_art_game.object_footprint_size(furniture_name, 1) == (
            len(rotated_rows[0]), len(rotated_rows),
        )
        furniture_art_game.state.placed_objects = {}
        furniture_art_game.state.placed_object_rotations = {}
        assert furniture_art_game.can_place_object(furniture_name, 5, 5, rotation=1)[0]
        furniture_art_game.set_placed_object(5, 5, furniture_name, rotation=1)
        rotated_key = furniture_art_game.obj_key(5, 5)
        assert furniture_art_game.object_rotation_for_key(rotated_key) == 1
        assert furniture_art_game.get_placed_object(
            5 + len(rotated_rows[0]) - 1, 5 + len(rotated_rows) - 1,
        ) == furniture_name
        for offset_y, artwork_row in enumerate(rotated_rows):
            for offset_x, expected_glyph in enumerate(artwork_row):
                rendered = ANSI_CSI_RE.sub(
                    "",
                    furniture_art_game.render_placed_object(
                        furniture_name, 5 + offset_x, 5 + offset_y, 5, 5,
                        rotation=1,
                    ),
                )
                assert rendered == expected_glyph
    assert ANSI_CSI_RE.sub(
        "",
        furniture_art_game.render_held_object_preview(
            "Kitchen Suite", 6, 5, 5, 5, True,
        ),
    ) == furniture_art.furniture_art_rows("Kitchen Suite")[0][1]

    furniture_function_calls = []
    furniture_art_game.sleep = lambda force=False: furniture_function_calls.append("sleep")
    furniture_art_game.safe_menu = (
        lambda menu_func, close_message: furniture_function_calls.append(close_message)
    )
    furniture_art_game.show_bookshelf_menu = lambda: furniture_function_calls.append("bookshelf")
    furniture_art_game.restore_stamina_from_house = (
        lambda key, amount, source: furniture_function_calls.append(("rest", source, amount))
    )
    furniture_art_game.show_player_color_mirror_menu = lambda: furniture_function_calls.append("mirror")
    furniture_art_game.show_player_combat_equipment_menu = lambda: furniture_function_calls.append("gear")
    furniture_art_game.family_meal_menu = lambda: furniture_function_calls.append("meal") or "changed"
    furniture_art_game.vertical_panel_select = lambda title, items, *args, **kwargs: next(
        (item for item in items if item.value == "sleep"),
        next(
            (item for item in items if item.value == "meal"),
            next((item for item in items if item.value == "appearance"), items[-1]),
        ),
    )
    for furniture_name in large_furniture_functions:
        furniture_art_game.use_house_furniture(furniture_name)
    assert "sleep" in furniture_function_calls
    assert "Cooking closed." in furniture_function_calls
    assert "Crafting closed." in furniture_function_calls
    assert "bookshelf" in furniture_function_calls
    assert "meal" in furniture_function_calls
    assert "mirror" in furniture_function_calls
    assert furniture_art_game.state.player_furniture_pose.get("pose") == "seated"
    furniture_art_game.use_house_furniture_component("Kitchen Suite", "cook", 1, 1)
    furniture_art_game.use_house_furniture_component("Kitchen Suite", "wash", 1, 1)
    furniture_art_game.use_house_furniture_component("Workshop Bench", "craft", 1, 1)
    furniture_art_game.use_house_furniture_component("Workshop Bench", "gear", 1, 1)
    furniture_art_game.use_house_furniture_component("Parlor Set", "social", 1, 1)
    furniture_art_game.use_house_furniture_component("Dressing Vanity", "mirror", 1, 1)
    assert furniture_function_calls.count("Cooking closed.") >= 2
    assert furniture_function_calls.count("Crafting closed.") >= 2
    assert "Equipment closed." in furniture_function_calls

    furniture_rotation_game = FarmGame()
    furniture_rotation_game.state.location = "HouseInterior"
    furniture_rotation_game.house_map = [list("." * 40) for _ in range(20)]
    furniture_rotation_game.autosave_with_message = furniture_rotation_game.set_message
    furniture_rotation_game.state.player_x = 1
    furniture_rotation_game.state.player_y = 1
    furniture_rotation_game.set_placed_object(
        6, 6, "Kitchen Suite", rotation=1, finish="Ocean",
    )
    kitchen_key = furniture_rotation_game.obj_key(6, 6)
    assert furniture_rotation_game.object_finish_for_key(kitchen_key) == "Ocean"
    assert furniture_rotation_game.rotated_furniture_use_edges("Kitchen Suite", 1) == ("west",)
    assert furniture_rotation_game.furniture_accessible_from_player(
        kitchen_key, "Kitchen Suite", 6, 7,
    )[0] is False
    furniture_rotation_game.state.player_x = 5
    furniture_rotation_game.state.player_y = 7
    assert furniture_rotation_game.furniture_accessible_from_player(
        kitchen_key, "Kitchen Suite", 6, 7,
    )[0] is True
    assert furniture_rotation_game.target_action_hint(6, 7).startswith("Z: use stove")
    furniture_rotation_game.state.player_x = 1
    furniture_rotation_game.state.player_y = 1
    furniture_rotation_game.state.facing = "RIGHT"
    furniture_rotation_game.state.player_x = 5
    furniture_rotation_game.state.player_y = 7
    assert furniture_rotation_game.pickup_front_object_to_hand()
    assert furniture_rotation_game.state.held_object == "Kitchen Suite"
    assert furniture_rotation_game.state.held_object_rotation == 1
    assert furniture_rotation_game.state.held_object_finish == "Ocean"
    assert furniture_rotation_game.rotate_held_object()
    assert furniture_rotation_game.state.held_object_rotation == 2
    assert furniture_rotation_game.cycle_held_object_finish()
    assert furniture_rotation_game.state.held_object_finish == "Royal"
    furniture_rotation_game.store_held_object()
    assert furniture_rotation_game.state.held_object is None
    assert furniture_rotation_game.state.held_object_rotation == 0
    assert furniture_rotation_game.state.held_object_finish == "Natural"

    furniture_rotation_game.set_placed_object(
        20, 5, "Dining Set", finish="Cherry",
    )
    dining_key = furniture_rotation_game.obj_key(20, 5)
    assert furniture_rotation_game.object_finish_for_key(dining_key) == "Cherry"
    cherry_render = furniture_rotation_game.render_placed_object(
        "Dining Set", 20, 5, 20, 5,
    )
    assert support.C.ROOF_RED in cherry_render

    # Rugs occupy a saved floor-decoration layer: they remain walkable and
    # editable while solid furniture can overlap them.
    assert data.INFRASTRUCTURE_DATA["Decorative Rug"]["placement_layer"] == "floor"
    assert data.INFRASTRUCTURE_DATA["Large Rug"]["placement_layer"] == "floor"
    migrated_rug_state = GameState(
        placed_objects={"HouseInterior:5,5": "Decorative Rug"},
        placed_object_rotations={"HouseInterior:5,5": 1},
        placed_object_finishes={"HouseInterior:5,5": "Ocean"},
    )
    assert "HouseInterior:5,5" not in migrated_rug_state.placed_objects
    assert migrated_rug_state.placed_floor_objects["HouseInterior:5,5"] == "Decorative Rug"
    assert migrated_rug_state.placed_floor_object_rotations["HouseInterior:5,5"] == 1
    assert migrated_rug_state.placed_floor_object_finishes["HouseInterior:5,5"] == "Ocean"

    floor_layer_game = FarmGame()
    floor_layer_game.state.location = "HouseInterior"
    floor_layer_game.house_map = [list("." * 30) for _ in range(16)]
    floor_layer_game.state.player_x = 1
    floor_layer_game.state.player_y = 1
    floor_layer_game.state.placed_objects = {}
    floor_layer_game.state.placed_floor_objects = {}
    floor_layer_game.state.placed_object_rotations = {}
    floor_layer_game.state.placed_floor_object_rotations = {}
    floor_layer_game.state.placed_object_finishes = {}
    floor_layer_game.state.placed_floor_object_finishes = {}
    floor_layer_game.autosave_with_message = floor_layer_game.set_message
    assert floor_layer_game.can_place_object("Decorative Rug", 5, 5, rotation=1)[0]
    floor_layer_game.set_placed_object(5, 5, "Decorative Rug", rotation=1, finish="Ocean")
    rug_key = floor_layer_game.obj_key(5, 5)
    assert rug_key not in floor_layer_game.state.placed_objects
    assert floor_layer_game.state.placed_floor_objects[rug_key] == "Decorative Rug"
    assert floor_layer_game.passable(5, 5)
    assert floor_layer_game.can_place_object("Couch", 6, 6)[0]
    floor_layer_game.set_placed_object(6, 6, "Couch")
    couch_key = floor_layer_game.obj_key(6, 6)
    assert floor_layer_game.placed_object_at(6, 6)[:2] == (couch_key, "Couch")
    assert floor_layer_game.placed_object_at(5, 6)[:2] == (rug_key, "Decorative Rug")
    assert not floor_layer_game.passable(6, 6)
    assert floor_layer_game.passable(5, 6)
    assert not floor_layer_game.can_place_object("Large Rug", 4, 4)[0]
    assert floor_layer_game.move_placed_object(rug_key, 10, 8)
    moved_rug_key = floor_layer_game.obj_key(10, 8)
    assert rug_key not in floor_layer_game.state.placed_floor_objects
    assert floor_layer_game.state.placed_floor_objects[moved_rug_key] == "Decorative Rug"
    assert floor_layer_game.object_rotation_for_key(moved_rug_key, "Decorative Rug") == 1
    assert floor_layer_game.object_finish_for_key(moved_rug_key, "Decorative Rug") == "Ocean"
    assert floor_layer_game.house_comfort_score() >= 3

    # Wall furnishings mount to real walls instead of consuming circulation
    # floor, while remaining ordinary movable and functional furniture.
    for wall_furnishing in ("Wall Calendar", "Wall Mirror", "Wall Art"):
        assert data.INFRASTRUCTURE_DATA[wall_furnishing]["placement_surface"] == "wall"
        assert furniture_art.furniture_has_art(wall_furnishing)
    wall_furniture_game = FarmGame()
    wall_furniture_game.state.location = "HouseInterior"
    wall_furniture_game.house_map = wall_furniture_game.make_house_map()
    wall_furniture_game.state.placed_objects = {}
    wall_furniture_game.state.placed_floor_objects = {}
    wall_furniture_game.state.placed_object_rotations = {}
    wall_furniture_game.state.placed_floor_object_rotations = {}
    wall_furniture_game.state.placed_object_finishes = {}
    wall_furniture_game.state.placed_floor_object_finishes = {}
    min_x, min_y, _max_x, _max_y = wall_furniture_game.house_floor_bounds()
    mount_x, mount_y = min_x + 3, min_y - 1
    assert wall_furniture_game.house_map[mount_y][mount_x] == "#"
    assert wall_furniture_game.can_place_object("Wall Calendar", mount_x, mount_y)[0]
    assert not wall_furniture_game.can_place_object("Wall Calendar", mount_x, min_y)[0]
    assert not wall_furniture_game.can_place_object("Wooden Chair", mount_x, mount_y)[0]
    wall_furniture_game.set_placed_object(mount_x, mount_y, "Wall Calendar")
    wall_furniture_game.state.player_x = mount_x
    wall_furniture_game.state.player_y = min_y
    wall_furniture_game.state.facing = "UP"
    assert wall_furniture_game.passable(mount_x, min_y)
    assert wall_furniture_game.target_action_hint(mount_x, mount_y).startswith("Z:")
    assert "Placement: Wall-mounted" in wall_furniture_game.look_tile_lines(mount_x, mount_y)
    assert ANSI_CSI_RE.sub(
        "", wall_furniture_game.render_tile(mount_x, mount_y),
    ) == "▧"
    wall_furniture_game.set_object_finish_for_key(
        wall_furniture_game.obj_key(mount_x, mount_y), "Wall Calendar", "Royal",
    )
    assert support.C.LIT in wall_furniture_game.render_tile(mount_x, mount_y)

    isolated_wall_game = FarmGame()
    isolated_wall_game.state.location = "HouseInterior"
    isolated_wall_game.house_map = [list(" " * 20) for _ in range(12)]
    isolated_wall_game.house_map[5][5] = "#"
    isolated_wall_game.state.placed_objects = {}
    isolated_wall_game.state.placed_floor_objects = {}
    assert not isolated_wall_game.can_place_object("Wall Art", 5, 5)[0]

    legacy_wall_game = FarmGame()
    legacy_wall_game.state.location = "HouseInterior"
    legacy_wall_game.house_map = legacy_wall_game.make_house_map()
    legacy_wall_game.state.placed_objects = {"HouseInterior:20,8": "Wall Art"}
    legacy_wall_game.state.placed_floor_objects = {}
    legacy_wall_game.state.placed_object_rotations = {}
    legacy_wall_game.state.placed_floor_object_rotations = {}
    legacy_wall_game.state.placed_object_finishes = {"HouseInterior:20,8": "Ocean"}
    legacy_wall_game.state.placed_floor_object_finishes = {}
    legacy_wall_game.rebuild_house_for_current_upgrades(preserve_existing=True)
    migrated_wall_entries = [
        (key, name) for key, name in legacy_wall_game.state.placed_objects.items()
        if name == "Wall Art"
    ]
    assert len(migrated_wall_entries) == 1
    migrated_wall_key, _name = migrated_wall_entries[0]
    _scope, migrated_wall_x, migrated_wall_y = legacy_wall_game.parse_object_key(migrated_wall_key)
    assert legacy_wall_game.house_map[migrated_wall_y][migrated_wall_x] == "#"
    assert any(
        0 <= ny < len(legacy_wall_game.house_map)
        and 0 <= nx < len(legacy_wall_game.house_map[ny])
        and legacy_wall_game.house_map[ny][nx] in legacy_wall_game.house_floor_tiles()
        for nx, ny in (
            (migrated_wall_x, migrated_wall_y - 1),
            (migrated_wall_x + 1, migrated_wall_y),
            (migrated_wall_x, migrated_wall_y + 1),
            (migrated_wall_x - 1, migrated_wall_y),
        )
    )
    assert legacy_wall_game.object_finish_for_key(migrated_wall_key, "Wall Art") == "Ocean"

    # Coordinated furniture keeps its complete placement footprint while
    # exposing real seats and intentional negative space to actor movement.
    assert furniture_art.furniture_walkable_kind("Wooden Chair", 0, 0) == "seat"
    assert furniture_art.furniture_walkable_kind("Couch", 1, 0) == "seat"
    assert furniture_art.furniture_walkable_kind("Dining Set", 0, 1) == "seat"
    assert furniture_art.furniture_walkable_kind("Dining Set", 1, 1) == ""
    assert furniture_art.furniture_walkable_kind("Dining Set", 2, 0, rotation=1) == "seat"
    assert furniture_art.furniture_walkable_kind("Parlor Set", 4, 0) == "open"
    assert furniture_art.furniture_walkable_kind("Parlor Set", 1, 1) == "seat"

    seating_game = FarmGame()
    seating_game.state.location = "HouseInterior"
    seating_game.house_map = [list("." * 40) for _ in range(18)]
    seating_game.state.placed_objects = {}
    seating_game.state.placed_floor_objects = {}
    seating_game.state.placed_object_rotations = {}
    seating_game.state.placed_floor_object_rotations = {}
    seating_game.state.placed_object_finishes = {}
    seating_game.state.placed_floor_object_finishes = {}
    seating_game.state.player_x = 1
    seating_game.state.player_y = 1
    seating_game.set_placed_object(5, 5, "Dining Set")
    dining_seat = (5, 6)
    dining_table = (6, 6)
    assert seating_game.passable(*dining_seat)
    assert not seating_game.passable(*dining_table)
    assert seating_game.in_house_bounds_for_npc(*dining_seat)
    assert not seating_game.in_house_bounds_for_npc(*dining_table)
    assert not seating_game.can_place_object("Wooden Chair", *dining_seat)[0]
    assert "Furniture cell: Seat (walkable)" in seating_game.look_tile_lines(*dining_seat)
    seating_game.state.player_x, seating_game.state.player_y = dining_seat
    seating_game.state.facing = "RIGHT"
    assert seating_game.interaction_target_pos() == dining_seat
    assert seating_game.furniture_accessible_from_player(
        seating_game.obj_key(5, 5), "Dining Set", *dining_seat,
    )[0]
    seat_uses = []
    seating_game.restore_stamina_from_house = (
        lambda key, amount, source: seat_uses.append((key, amount, source))
    )
    seating_game.use_house_action(*dining_seat)
    assert seat_uses and seat_uses[-1][2] == "dining set"
    seating_game.state.player_x = 1
    seating_game.state.player_y = 1
    family_seat = seating_game.family_furniture_activity_position(
        "seat-test", ("family_meal",), set(),
    )
    assert family_seat is not None
    assert furniture_art.furniture_walkable_kind(
        "Dining Set", family_seat[0] - 5, family_seat[1] - 5,
    ) == "seat"
    seating_game.set_placed_object(15, 5, "Four-Poster Bed")
    assigned_bed_key = seating_game.obj_key(15, 5)
    assigned_bed_state_key = f"placed:{assigned_bed_key}:Four-Poster Bed"
    seating_game.state.furniture_states[assigned_bed_state_key] = {
        "name": "Four-Poster Bed",
        "assigned_actor_id": "household_child:77",
        "assigned_name": "Test Child",
    }
    family_bond_before_assignment_use = seating_game.family_bond_score()
    assigned_sleep_position = seating_game.family_furniture_activity_position(
        "household_child:77", ("sleep",), set(),
    )
    assert assigned_sleep_position is not None
    assert seating_game.state.furniture_states[assigned_bed_state_key]["household_uses"] == 1
    assert seating_game.state.furniture_states[assigned_bed_state_key]["uses"] == 1
    assert seating_game.family_bond_score() == family_bond_before_assignment_use + 1
    assert seating_game.family_furniture_activity_position(
        "household_child:78", ("sleep",), set(),
    ) is None

    seating_game.state.placed_objects = {}
    seating_game.state.placed_object_rotations = {}
    seating_game.set_placed_object(5, 5, "Dining Set", rotation=1)
    assert seating_game.passable(7, 5)
    assert not seating_game.passable(6, 6)

    ensemble_game = FarmGame()
    ensemble_game.state.location = "HouseInterior"
    ensemble_game.house_map = [list("." * 100) for _ in range(20)]
    ensemble_game.state.placed_objects = {}
    ensemble_game.state.placed_object_rotations = {}
    ensemble_game.state.placed_object_finishes = {}
    ensemble_game.state.player_x = 95
    ensemble_game.state.player_y = 18
    ensemble_layout = [
        ("Four-Poster Bed", 2, 2), ("Storage Hutch", 2, 6),
        ("Kitchen Suite", 15, 2), ("Dining Set", 15, 5),
        ("Sectional Couch", 30, 2), ("Stone Hearth", 30, 5),
        ("Reading Nook", 45, 2), ("Workshop Bench", 45, 6),
        ("Family Table", 60, 2), ("Child Bed", 60, 5),
        ("Bathing Tub", 75, 2), ("Dressing Vanity", 75, 6),
    ]
    for furniture_name, x, y in ensemble_layout:
        assert ensemble_game.can_place_object(furniture_name, x, y)[0]
        ensemble_game.set_placed_object(x, y, furniture_name)
    ensembles = ensemble_game.house_furniture_ensemble_status()
    assert {entry["name"] for entry in ensembles if entry["active"]} == {
        "Bedroom Retreat", "Working Kitchen", "Cozy Parlor",
        "Study Corner", "Family Room", "Proper Washroom",
    }
    assert sum(int(entry["bonus"]) for entry in ensembles if entry["active"]) == 22
    for recipe_name in ["Rain Barrel", "Pipe Segment", "Irrigation Pump", "Water Tank", "Harvest Crate", "Shipping Loader", "Seed Hopper"]:
        assert recipe_name in data.CRAFTING_RECIPES
        output_name, output_qty = data.CRAFTING_RECIPES[recipe_name]["output"]
        assert output_name in data.AUTOMATION_OBJECT_DATA
        assert int(output_qty) > 0
        assert_known_inventory_items(data.CRAFTING_RECIPES[recipe_name].get("cost", {}), f"automation recipe {recipe_name}")

    for companion_id, companion in FARMSTEAD_COMPANION_DATA.items():
        assert companion.get("id") == companion_id
        assert companion.get("npc_id") in town_npc_ids
        assert companion.get("name")
        assert companion.get("role")
        assert companion.get("description")
        assert int(companion.get("max_hp", 0)) > 0
        assert int(companion.get("attack", 0)) > 0
        required_building = str(companion.get("required_building", "") or "")
        assert not required_building or required_building in data.TOWN_BUILDING_DATA

    assert len(FARMSTEAD_COMPANION_DATA) >= 20
    assert set(data.COMPANION_QUEST_DATA).issubset(set(FARMSTEAD_COMPANION_DATA))
    assert set(FARMSTEAD_COMPANION_DATA).issubset(set(data.COMPANION_QUEST_DATA))

    resident_request_ids = set()
    for request_id, request in data.RESIDENT_REQUEST_DATA.items():
        assert request_id not in resident_request_ids
        resident_request_ids.add(request_id)
        assert request.get("npc_id") in town_npc_ids
        assert request.get("title")
        assert request.get("description")
        requirements = request.get("requirements", {}) or {}
        assert_known_inventory_items(requirements.get("items", {}), f"resident request {request_id} requirement")
        required_building = str(requirements.get("required_building", "") or "")
        assert not required_building or required_building in data.TOWN_BUILDING_DATA
        rewards = request.get("rewards", {}) or {}
        assert_known_inventory_items(rewards.get("items", {}), f"resident request {request_id} reward")
        for item_name, qty in (rewards.get("combat_salvage", {}) or {}).items():
            assert item_name in combat_salvage_names, f"resident request {request_id} uses unknown combat salvage {item_name}"
            assert int(qty) > 0
        _combat_money, combat_items = translated_battle_loot(rewards.get("combat_salvage", {}) or {})
        assert_known_inventory_items(combat_items, f"resident request {request_id} combat reward")

    companion_quest_ids = set()
    for companion_id, quests in data.COMPANION_QUEST_DATA.items():
        assert companion_id in FARMSTEAD_COMPANION_DATA
        assert quests
        npc_id = str(FARMSTEAD_COMPANION_DATA[companion_id].get("npc_id", ""))
        assert npc_id in town_npc_ids
        for quest in quests:
            quest_id = str(quest.get("id", ""))
            assert quest_id and quest_id not in companion_quest_ids
            companion_quest_ids.add(quest_id)
            assert quest.get("title")
            assert quest.get("description")
            requirements = quest.get("requirements", {}) or {}
            assert_known_inventory_items(requirements.get("items", {}), f"companion quest {quest_id} requirement")
            required_building = str(requirements.get("required_building", "") or "")
            assert not required_building or required_building in data.TOWN_BUILDING_DATA
            for enemy_name, qty in (requirements.get("bestiary_defeated", {}) or {}).items():
                assert enemy_name in farmstead_main.MINE_ENEMY_PROFILES
                assert int(qty) > 0
            rewards = quest.get("rewards", {}) or {}
            assert "combat_progress" in rewards
            for item_name, qty in (rewards.get("combat_salvage", {}) or {}).items():
                assert item_name in combat_salvage_names, f"companion quest {quest_id} uses unknown combat salvage {item_name}"
                assert int(qty) > 0
            _combat_money, combat_items = translated_battle_loot(rewards.get("combat_salvage", {}) or {})
            assert_known_inventory_items(combat_items, f"companion quest {quest_id} combat reward")

    game = FarmGame()
    assert isinstance(game, saves.SaveLoadMixin)
    assert isinstance(game, npcs.NpcMixin)
    assert game.dynamic_reactive_dialogue_templates() == {}
    assert game.state.location == "Wilderness"
    assert game.in_seamless_farm_district()
    assert game.state.town_development_stage == 0
    assert game.state.unlocked_town_buildings == list(data.INITIAL_UNLOCKED_TOWN_BUILDINGS)
    assert game.is_town_building_unlocked("general_store")
    assert game.is_town_building_unlocked("blacksmith")
    assert not game.is_town_building_unlocked("museum")
    assert game.town_map[data.TOWN_DOORS["museum"][1]][data.TOWN_DOORS["museum"][0]] == "Q"
    assert game.town_map[data.TOWN_NOTICE_BOARD_POS[1]][data.TOWN_NOTICE_BOARD_POS[0]] == "N"
    assert data.TOWN_RESTORATION_PROJECT_DATA["restore_blacksmith"]["target_building"] == "blacksmith"
    assert data.TOWN_RESTORATION_PROJECT_DATA["restore_museum"]["target_building"] == "museum"
    assert "restore_blacksmith" not in state.available_town_restoration_projects(game.state)
    assert not state.can_complete_town_restoration_project(game.state, "restore_blacksmith")
    assert "Museum Sign" == game.town_sign_title(76, 9)
    assert any("MUSEUM" in line for line in game.town_sign_lines(76, 9))
    assert any("Museum" in line for line in game.town_directory_lines())
    assert any("Museum" in line for line in game.town_bulletin_lines())
    assert game.state.town_npcs
    assert len(game.active_town_npcs()) < len(game.state.town_npcs)
    assert game.scene_catalog()
    assert "life:first_land_claim" in game.scene_catalog()
    scene_game = FarmGame()
    scene_baseline = scene_game.town_npc_relationship("eli_carpenter")
    captured_scene_frames = []
    original_scene_draw = scene_game._draw_dialogue_frame
    scene_game._draw_dialogue_frame = (
        lambda actor, text, phase, transcript, *args, **kwargs:
        captured_scene_frames.append((dict(actor), str(text), str(phase), list(transcript)))
    )
    try:
        assert scene_game.start_scene("life:first_land_claim")
        scene_game.draw_scene()
        assert captured_scene_frames
        assert captured_scene_frames[-1][0]["name"] == "Eli"
        assert "The First Deed" in captured_scene_frames[-1][2]
        assert scene_game.handle_scene_key("b") is False
    finally:
        scene_game._draw_dialogue_frame = original_scene_draw
    assert scene_game.state.active_scene_id == ""
    assert "life:first_land_claim" in scene_game.state.completed_scene_ids
    assert "scene_flag:life:first_land_claim" in scene_game.state.scene_flags
    assert scene_game.town_npc_relationship("eli_carpenter") == scene_baseline + 4
    assert any(
        entry.get("category") == "dialogue" and "Eli:" in entry.get("text", "")
        for entry in scene_game.state.hud_activity_log
    )
    runtime_scene = scene_game.register_special_event_scene(
        "smoke_runtime_event", "Persistent World Event",
        [
            {"type": "narration", "text": "The world remains visible around a runtime event."},
            {"type": "give_item", "item": "Wood", "qty": 2},
            {"type": "set_flag", "flag": "smoke_runtime_outcome"},
        ],
        "Runtime event complete.",
    )
    assert runtime_scene["id"] == "special:smoke_runtime_event"
    assert scene_game.scene_by_id("special:smoke_runtime_event")["title"] == "Persistent World Event"
    runtime_wood_before = int(scene_game.state.inventory.get("Wood", 0))
    assert scene_game.start_scene("special:smoke_runtime_event")
    assert scene_game.skip_active_scene()
    assert scene_game.state.inventory.get("Wood", 0) == runtime_wood_before + 2
    assert "smoke_runtime_outcome" in scene_game.state.scene_flags
    assert "special:smoke_runtime_event" in scene_game.state.completed_scene_ids
    persisted_runtime_state = state.GameState(active_scene_id="special:valid", active_scene_step_index=0, special_event_scenes={
        "special:valid": {
            "id": "special:valid", "title": "Valid", "steps": [{"type": "narration", "text": "Valid step."}],
        },
        "invalid": {"id": "invalid", "steps": [{"type": "narration", "text": "Invalid namespace."}]},
        "special:empty": {"id": "special:empty", "steps": []},
    })
    assert list(persisted_runtime_state.special_event_scenes) == ["special:valid"]
    assert persisted_runtime_state.active_scene_id == "special:valid"
    first_npc = game.state.town_npcs[0]
    assert game.town_npc_relationship(str(first_npc["id"])) == 0
    assert game.town_npc_friendship_label(0) == "Stranger"
    first_talk_lines = game.town_npc_dialogue_lines(first_npc)
    assert len(first_talk_lines) >= 5
    assert any(game.town_npc_work_insight(first_npc) in line for line in first_talk_lines)
    assert "already talked" not in "\n".join(first_talk_lines).lower()
    spring_dialogue = game.contextual_dialogue_entries_for_category(first_npc, "spring")
    assert spring_dialogue
    assert spring_dialogue[0]["text"] == data.TOWN_NPC_CONTEXTUAL_DIALOGUE_DATA[first_npc["id"]]["spring"][0]
    assert all(not game.low_quality_dialogue_text(entry["text"]) for entry in spring_dialogue)
    assert not any("Mud everywhere" in entry["text"] for entry in spring_dialogue)
    authored_work_insights = {
        game.town_npc_work_insight(npc)
        for npc in game.state.town_npcs
    }
    assert len(authored_work_insights) >= 20
    mira_dialogue = game.npc_record_by_id("mira_seed")
    assert mira_dialogue
    assert all(
        len(" ".join(game.town_npc_conversation_topic_lines(mira_dialogue, topic))) >= 140
        for topic in ("mind", "activity", "work", "place", "people")
    )
    assert not next(
        item for item in game.town_npc_conversation_topic_items(mira_dialogue)
        if item.value == "personal"
    ).enabled
    original_dialogue_select = game.vertical_panel_select
    game.vertical_panel_select = lambda *args, **kwargs: MenuItem(
        label="Suggest a Concrete Next Step", value="practical", enabled=True
    )
    try:
        thoughtful_response = game.npc_dialogue_response_choice(mira_dialogue, True)
    finally:
        game.vertical_panel_select = original_dialogue_select
    assert thoughtful_response["preferred_style"] == "practical"
    assert thoughtful_response["effect"] == 2
    assert FarmGame.town_npc_conversation_menu.__module__ == "ascii_farmstead_dialogue"
    expanded_lines = dialogue_library.expanded_dialogue_catalog()
    assert dialogue_library.EXPANDED_DIALOGUE_LINE_COUNT == 3000
    assert len(dialogue_library.VOICE_PROFILES) == 25
    assert len(dialogue_library.DIALOGUE_LIBRARY_TOPICS) == 12
    assert all(len(dialogue_library.TOPIC_PATTERNS[topic]) == 10 for topic in dialogue_library.DIALOGUE_LIBRARY_TOPICS)
    assert len(expanded_lines) == 3000
    assert len(set(expanded_lines.values())) == 3000
    assert all(line and "{" not in line and "}" not in line and "\n" not in line for line in expanded_lines.values())
    assert dialogue_library.dialogue_profile_for_role("Blacksmith")["id"] == "smith"
    assert dialogue_library.dialogue_profile_for_role("Librarian")["id"] == "archive"
    assert dialogue_library.dialogue_profile_for_role("Tundra Warden")["id"] == "nature"
    smith_library_line = game.dialogue_library_line(first_npc | {"role": "Blacksmith"}, "work", "smoke")
    archive_library_line = game.dialogue_library_line(first_npc | {"role": "Librarian"}, "work", "smoke")
    assert smith_library_line != archive_library_line
    assert game.dialogue_library_line(first_npc, "work", "stable") == game.dialogue_library_line(first_npc, "work", "stable")
    dialogue_topics = game.dialogue_topic_options(first_npc, "authored")
    assert [value for value, _label, _hint in dialogue_topics] == [
        "directions", "background", "family", "work", "interests",
        "people", "player", "smalltalk", "arrangements", "companions", "relationship", "goodbye",
    ]
    first_greeting = game.dialogue_greeting(first_npc, "authored", True, False)
    assert first_npc["name"] in first_greeting
    assert "work as" not in first_greeting.lower()
    assert game.dialogue_demeanor(
        {"id": "warm_test", "name": "Warm", "role": "Gardener", "personality": "Cheerful, warm"},
        "procedural", True,
    ) == "warm"
    assert game.dialogue_demeanor(
        {"id": "skeptic_test", "name": "Skeptic", "role": "Vendor", "personality": "Shrewd, skeptical"},
        "procedural", True,
    ) == "skeptical"
    assert game.dialogue_demeanor(
        {"id": "duty_test", "name": "Duty", "role": "Innkeeper", "personality": "Suspicious", "activity": "serving guests at the counter"},
        "procedural", True,
    ) == "professional"
    assert game.dialogue_greeting(first_npc, "spouse", False, False) == ""
    assert game.dialogue_farewell(first_npc, "child") == ""
    original_dialogue_reader = game.dialogue_read_key
    original_dialogue_draw = game._draw_dialogue_frame
    original_hud_dialogue_log = json.loads(json.dumps(game.state.hud_activity_log))
    game.dialogue_read_key = lambda: "\r"
    game._draw_dialogue_frame = lambda *args, **kwargs: None
    try:
        assert game.dialogue_say(first_npc, "The road is busy this morning.", "chit-chat", [])
    finally:
        game.dialogue_read_key = original_dialogue_reader
        game._draw_dialogue_frame = original_dialogue_draw
    assert game.state.hud_activity_log[-1]["category"] == "dialogue"
    assert first_npc["name"] in game.state.hud_activity_log[-1]["text"]
    game.state.hud_activity_log = original_hud_dialogue_log
    original_dialogue_width = dialogue_system.terminal_width
    original_dialogue_height = dialogue_system.terminal_height
    original_dialogue_clear = dialogue_system.clear_screen
    original_frame_renderer = game.render_frame_text
    original_centered_print = game.centered_print
    dialogue_system.terminal_width = lambda: 80
    dialogue_system.terminal_height = lambda: 30
    dialogue_system.clear_screen = lambda: None
    game.render_frame_text = lambda: "LEGACY HUD\nVISIBLE WORLD\nPLAYER AND NPC"
    game.centered_print = lambda line, *args, **kwargs: print(line)
    try:
        frame_output = io.StringIO()
        with contextlib.redirect_stdout(frame_output):
            game._draw_dialogue_frame(
                first_npc,
                "The world remains visible while this conversation continues.",
                "main subject",
                [],
                [("continue", "Continue talking", "Advance this conversation."), ("goodbye", "Leave", "Return to the world.")],
                0,
            )
        rendered_dialogue = frame_output.getvalue()
    finally:
        dialogue_system.terminal_width = original_dialogue_width
        dialogue_system.terminal_height = original_dialogue_height
        dialogue_system.clear_screen = original_dialogue_clear
        game.render_frame_text = original_frame_renderer
        game.centered_print = original_centered_print
    assert rendered_dialogue.startswith("LEGACY HUD\nVISIBLE WORLD\nPLAYER AND NPC\n")
    assert first_npc["name"] in rendered_dialogue
    assert "Continue talking" in rendered_dialogue
    assert "B/X/Esc/Q/Tab leave" in rendered_dialogue
    original_say = game.dialogue_say
    original_choose = game.dialogue_choose
    original_quiz = game.npc_dialogue_response_choice
    dialogue_turns = []
    dialogue_choices = iter(["topics", "background", "family", "interests", "companions", "goodbye"])
    game.dialogue_say = lambda actor, text, phase, transcript: (
        transcript.append({"speaker": str(actor.get("name", "NPC")), "text": str(text), "phase": str(phase)}),
        dialogue_turns.append((str(phase), str(text))),
        True,
    )[-1]
    game.dialogue_choose = lambda *args, **kwargs: next(dialogue_choices)
    game.npc_dialogue_response_choice = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("normal conversation must not invoke the legacy relationship quiz")
    )
    try:
        dialogue_result = game.run_unified_npc_conversation(
            first_npc, kind="authored", first_meeting=True, repeated_today=False
        )
    finally:
        game.dialogue_say = original_say
        game.dialogue_choose = original_choose
        game.npc_dialogue_response_choice = original_quiz
    assert dialogue_result["completed"]
    assert dialogue_result["topics"] == ["background", "family", "interests", "companions"]
    assert [phase for phase, _text in dialogue_turns].count("greeting") == 1
    assert [phase for phase, _text in dialogue_turns].count("main subject") == 1
    assert [phase for phase, _text in dialogue_turns].count("response") == 4
    assert "_dialogue_kind" not in first_npc
    known_places = game.dialogue_known_places(first_npc, "authored")
    assert known_places and all(place.get("name") and place.get("id") for place in known_places)
    assert isinstance(game.state.npc_dialogue_social_state, dict)
    assert isinstance(game.state.social_reputation, int)
    assert isinstance(game.state.player_origin, str) and game.state.player_origin
    assert game.state.player_background.lower() in game.dialogue_player_disclosure_statement("background").lower()
    assert game.state.player_origin.lower() in game.dialogue_player_disclosure_statement("background").lower()
    assert "wilderness" in game.dialogue_player_disclosure_statement("travels").lower()
    assert "generation" in game.dialogue_player_disclosure_statement("ancestry").lower()
    original_social_state = json.loads(json.dumps(game.state.npc_dialogue_social_state))
    original_world_dialogue_log = json.loads(json.dumps(game.state.hud_activity_log))
    knowledge_source = {
        "id": "knowledge_source", "name": "Nora", "role": "Courier",
        "personality": "Observant", "relationship": 0,
    }
    knowledge_listener = {
        "id": "knowledge_listener", "name": "Pax", "role": "Innkeeper",
        "personality": "Reserved", "relationship": 0,
    }
    source_packet = game.dialogue_add_knowledge(
        knowledge_source, "procedural", "The north bridge is closed for repairs.",
        subject="road closure", source_name="personal observation",
        source_kind="firsthand", confidence=100,
    )
    assert source_packet["source_kind"] == "firsthand"
    assert game.dialogue_propagate_knowledge(
        knowledge_source, "procedural", knowledge_listener, "procedural"
    )
    listener_packet = game.dialogue_social_slot(
        knowledge_listener, "procedural"
    )["knowledge"][-1]
    assert listener_packet["source_name"] == "Nora"
    assert listener_packet["source_kind"] == "hearsay"
    assert int(listener_packet["confidence"]) < int(source_packet["confidence"])
    mood_actor = {
        "id": "mood_actor", "name": "Vale", "role": "Miner",
        "personality": "Calm", "relationship": 0,
    }
    mood = game.dialogue_set_mood(
        mood_actor, "procedural", "angry", "a broken promise", 3, 2
    )
    assert game.dialogue_demeanor(mood_actor, "procedural") == "hostile"
    mood["expires_day"] = game.dialogue_absolute_day() - 1
    assert game.dialogue_current_mood(mood_actor, "procedural") == {}
    arc_actor = {
        "id": "arc_actor", "name": "Tess", "role": "Ranger",
        "personality": "Practical", "relationship": 0,
    }
    arc_thread = game.dialogue_current_thread(arc_actor, "procedural", create=True)
    assert arc_thread["profile"] == "roads" and arc_thread["stage"] == 0
    arc_line, arc_gain = game.dialogue_advance_thread(
        arc_actor, "procedural", arc_thread, "support"
    )
    assert arc_thread["stage"] == 1 and arc_gain == 1 and arc_line
    repeated_arc_line, repeated_arc_gain = game.dialogue_advance_thread(
        arc_actor, "procedural", arc_thread, "support"
    )
    assert arc_thread["stage"] == 1 and repeated_arc_gain == 0
    assert "already" in repeated_arc_line.lower()
    original_dialogue_absolute_day = game.dialogue_absolute_day
    base_arc_day = original_dialogue_absolute_day()
    try:
        game.dialogue_absolute_day = lambda: base_arc_day + 1
        game.dialogue_advance_thread(arc_actor, "procedural", arc_thread, "challenge")
        game.dialogue_absolute_day = lambda: base_arc_day + 2
        game.dialogue_advance_thread(arc_actor, "procedural", arc_thread, "listen")
    finally:
        game.dialogue_absolute_day = original_dialogue_absolute_day
    assert arc_thread["stage"] == 3 and arc_thread["status"] == "resolved"
    arc_slot = game.dialogue_social_slot(arc_actor, "procedural")
    assert arc_slot["thread_history"]
    assert arc_slot["story_consequences"][-1]["profile"] == "roads"
    assert arc_slot["story_aftermath"]["thread_id"] == arc_thread["id"]
    assert arc_actor["story_outcome"]["profile"] == "roads"
    assert "route" in game.dialogue_activity(arc_actor, "procedural")
    assert game.dialogue_current_thread(arc_actor, "procedural", create=True) == {}
    aftermath_listener = {
        "id": "aftermath_listener", "name": "Orin", "role": "Courier",
        "personality": "Curious", "relationship": 0,
    }
    assert game.dialogue_propagate_knowledge(
        arc_actor, "procedural", aftermath_listener, "procedural"
    )
    assert "route" in game.dialogue_social_slot(
        aftermath_listener, "procedural"
    )["knowledge"][-1]["text"].lower()
    original_dialogue_absolute_day = game.dialogue_absolute_day
    resolved_arc_day = int(arc_thread["resolved_day"])
    try:
        game.dialogue_absolute_day = lambda: resolved_arc_day + 1
        arc_slot["initiation"] = {}
        aftermath_initiation = game.dialogue_prepare_initiation(
            arc_actor, "procedural"
        )
        assert aftermath_initiation["reason"] == "story_aftermath"
        assert game.dialogue_accept_initiation(arc_actor, "procedural")
        assert arc_slot["story_aftermath"]["acknowledged"]
        game.dialogue_absolute_day = lambda: resolved_arc_day + 13
        assert game.dialogue_current_thread(arc_actor, "procedural", create=True) == {}
        game.dialogue_absolute_day = lambda: resolved_arc_day + 14
        next_arc_thread = game.dialogue_current_thread(
            arc_actor, "procedural", create=True
        )
        assert next_arc_thread["profile"] == "personal"
        assert next_arc_thread["id"] != arc_thread["id"]
    finally:
        game.dialogue_absolute_day = original_dialogue_absolute_day
    introduced_actor = {
        "id": "introduced_actor", "name": "Ira", "role": "Scholar",
        "personality": "Skeptical", "relationship": 0,
    }
    game.dialogue_social_slot(introduced_actor, "procedural")["introductions"].append({
        "source_name": "Nora", "purpose": "that you were looking for the archive",
        "acknowledged": False,
    })
    introduced_greeting = game.dialogue_greeting(
        introduced_actor, "procedural", True, False
    )
    assert "Nora" in introduced_greeting and introduced_actor["name"] in introduced_greeting
    assert game.dialogue_social_slot(
        introduced_actor, "procedural"
    )["introductions"][-1]["acknowledged"]
    arrangement_actor = {
        "id": "arrangement_actor", "name": "Mara", "role": "Courier",
        "personality": "Warm", "relationship": 0,
    }
    arrangement_target = {
        "id": "arrangement_target", "name": "Sol", "role": "Archivist",
        "personality": "Reserved", "relationship": 0,
        "procedural_resident": True,
    }
    original_known_people = game.dialogue_known_people
    original_dialogue_choose_for_arrangement = game.dialogue_choose
    original_dialogue_say_for_arrangement = game.dialogue_say
    game.dialogue_known_people = lambda actor, kind: [arrangement_target]
    arrangement_choices = iter(["introduction", "arrangement_target"])
    game.dialogue_choose = lambda *args, **kwargs: next(arrangement_choices)
    game.dialogue_say = lambda *args, **kwargs: True
    try:
        assert game.dialogue_handle_practical_arrangement(
            arrangement_actor, "procedural", []
        )
    finally:
        game.dialogue_known_people = original_known_people
        game.dialogue_choose = original_dialogue_choose_for_arrangement
        game.dialogue_say = original_dialogue_say_for_arrangement
    assert game.dialogue_social_slot(
        arrangement_target, "procedural"
    )["introductions"][-1]["source_name"] == "Mara"
    group_actor = {
        "id": "group_actor", "name": "Oren", "role": "Carpenter",
        "personality": "Blunt", "relationship": 0,
    }
    group_partner = {
        "id": "group_partner", "name": "Lio", "role": "Gardener",
        "personality": "Warm", "relationship": 0,
    }
    group_actor["_dialogue_group_partner"] = {
        "actor": group_partner, "kind": "procedural", "distance": 2,
    }
    group_turns = []
    original_dialogue_choose_for_group = game.dialogue_choose
    original_dialogue_say_for_group = game.dialogue_say
    game.dialogue_choose = lambda *args, **kwargs: "work"
    game.dialogue_say = lambda speaker, text, phase, transcript: (
        group_turns.append((str(speaker.get("name", "")), str(phase), str(text))), True
    )[-1]
    try:
        assert game.dialogue_handle_group_topic(group_actor, "procedural", [])
    finally:
        game.dialogue_choose = original_dialogue_choose_for_group
        game.dialogue_say = original_dialogue_say_for_group
    assert [name for name, _phase, _text in group_turns] == ["Oren", "Lio"]
    witness_actor = {
        "id": "world_witness", "name": "Rowan", "role": "Ranger",
        "personality": "Skeptical, observant", "activity": "checking trail markers",
        "relationship": 0,
    }
    original_nearby_dialogue_actors = game.world_dialogue_nearby_actors
    game.world_dialogue_nearby_actors = lambda radius=7: [{
        "actor": witness_actor, "kind": "procedural",
        "x": int(game.state.player_x) + 1, "y": int(game.state.player_y),
        "distance": 1,
    }]
    try:
        assert not game.world_dialogue_event_is_worth_witnessing(
            "You need more wood.", "warning"
        )
        assert game.world_dialogue_record_player_event(
            "Repaired the old trail marker.", "gain"
        ) == 1
    finally:
        game.world_dialogue_nearby_actors = original_nearby_dialogue_actors
    witness_slot = game.dialogue_social_slot(witness_actor, "procedural")
    assert witness_slot["witnessed_events"][-1]["action"].startswith("repair ")
    assert witness_slot["knowledge"][-1]["source_kind"] == "firsthand"
    initiated_callout = game.dialogue_initiation_callout(
        witness_actor, "procedural"
    )
    assert game.state.player_name in initiated_callout
    assert "talk" in initiated_callout.lower()
    accepted_initiation = game.dialogue_accept_initiation(
        witness_actor, "procedural"
    )
    assert accepted_initiation
    witness_callback = game.dialogue_witness_callback(
        witness_actor, "procedural", "conversation"
    )
    assert "saw you repair" in witness_callback.lower()
    assert witness_slot["witnessed_events"][-1]["conversation_acknowledged"]
    pair_reply = game.world_dialogue_pair_exchange(
        {
            "actor": witness_actor, "kind": "procedural",
            "x": 10, "y": 10, "distance": 2,
        },
        {
            "actor": {
                "id": "world_listener", "name": "June", "role": "Courier",
                "personality": "Warm", "activity": "sorting deliveries",
            },
            "kind": "procedural", "x": 12, "y": 10, "distance": 3,
        },
    )
    assert all(pair_reply) and "June" in pair_reply[0]
    assert game.world_dialogue_emit_ambient([{
        "actor": witness_actor, "kind": "procedural",
        "x": 10, "y": 10, "distance": 2,
    }])
    assert game.state.hud_activity_log[-1]["category"] == "dialogue"
    assert "Rowan" in game.state.hud_activity_log[-1]["text"]
    game.state.hud_activity_log = original_world_dialogue_log
    original_social_reputation = int(game.state.social_reputation)
    social_actor = {
        "id": "social_test", "name": "Lina", "role": "Gardener",
        "personality": "Cheerful, warm", "relationship": 0,
    }
    social_turns = []
    original_say = game.dialogue_say
    original_choose = game.dialogue_choose
    game.dialogue_say = lambda actor, text, phase, transcript: (
        social_turns.append((str(actor.get("name", "")), str(phase), str(text))), True
    )[-1]
    game.dialogue_choose = lambda *args, **kwargs: "compliment_character"
    try:
        assert game.dialogue_handle_smalltalk(social_actor, "procedural", [])
        relationship_after_first_compliment = int(social_actor["relationship"])
        reputation_after_first_compliment = int(game.state.social_reputation)
        assert game.dialogue_handle_smalltalk(social_actor, "procedural", [])
    finally:
        game.dialogue_say = original_say
        game.dialogue_choose = original_choose
    assert relationship_after_first_compliment == 2
    assert reputation_after_first_compliment == original_social_reputation + 1
    assert int(social_actor["relationship"]) == relationship_after_first_compliment
    assert int(game.state.social_reputation) == reputation_after_first_compliment
    assert any("changes nothing further" in text for _speaker, _phase, text in social_turns)
    insult_actor = {
        "id": "insult_test", "name": "Brom", "role": "Blacksmith",
        "personality": "Gruff, blunt", "relationship": 0,
    }
    game.dialogue_say = lambda actor, text, phase, transcript: True
    game.dialogue_choose = lambda *args, **kwargs: "insult_work"
    try:
        assert game.dialogue_handle_smalltalk(insult_actor, "procedural", [])
    finally:
        game.dialogue_say = original_say
        game.dialogue_choose = original_choose
    assert int(insult_actor["relationship"]) == -4
    assert int(game.state.social_reputation) == reputation_after_first_compliment - 2
    disclosure_turns = []
    game.dialogue_say = lambda actor, text, phase, transcript: (
        disclosure_turns.append((str(actor.get("name", "")), str(phase), str(text))), True
    )[-1]
    game.dialogue_choose = lambda *args, **kwargs: "background"
    try:
        assert game.dialogue_handle_player_disclosure(social_actor, "procedural", [])
        assert game.dialogue_handle_player_disclosure(social_actor, "procedural", [])
    finally:
        game.dialogue_say = original_say
        game.dialogue_choose = original_choose
    assert disclosure_turns[0][0] == game.state.player_name and disclosure_turns[0][1] == "you"
    assert any("mentioning that before" in text for _speaker, _phase, text in disclosure_turns)
    game.state.npc_dialogue_social_state = original_social_state
    game.state.social_reputation = original_social_reputation
    assert isinstance(game.state.npc_dialogue_promises, dict)
    assert game.dialogue_work_situation({"id": "child:test", "name": "Test Child"}, "child") is None
    original_promises = json.loads(json.dumps(game.state.npc_dialogue_promises))
    original_completed_errands = list(game.state.completed_errand_ids or [])
    errand_situation = game.dialogue_work_situation(first_npc, "authored")
    assert errand_situation and errand_situation["type"] == "authored_errand"
    assert errand_situation["deadline"] == "today"
    game.dialogue_record_promise(first_npc, "authored", errand_situation)
    active_promise = game.state.npc_dialogue_promises[
        game.dialogue_promise_key(first_npc, "authored")
    ]["active"]
    assert active_promise["status"] == "active"
    assert "you said" in game.dialogue_promise_callback(first_npc, "authored").lower()
    game.state.completed_errand_ids.append(str(errand_situation["id"]))
    assert "followed through" in game.dialogue_promise_callback(first_npc, "authored").lower()
    promise_slot = game.state.npc_dialogue_promises[
        game.dialogue_promise_key(first_npc, "authored")
    ]
    assert not promise_slot["active"]
    assert promise_slot["history"][-1]["status"] == "fulfilled"
    game.state.completed_errand_ids = list(original_completed_errands)
    original_quest_records = json.loads(json.dumps(game.state.quest_records or {}))
    original_tracked_quest_id = str(game.state.tracked_quest_id or "")
    dialogue_quest = game.accept_dialogue_quest(first_npc, "authored", errand_situation)
    assert dialogue_quest["status"] in {"active", "ready"}
    assert game.state.tracked_quest_id == dialogue_quest["id"]
    assert game.tracked_quest_hud_text()
    assert any(str(dialogue_quest["title"]) in line for line in game.unified_quest_journal_lines())
    assert any("Current objective" in line for line in game.quest_detail_lines(dialogue_quest))
    assert game.complete_dialogue_quest_for_situation(first_npc, "authored", errand_situation)
    assert game.quest_record(str(dialogue_quest["id"]))["status"] == "completed"

    destination = game.quest_capture_current_destination()
    original_destination_x = int(destination["x"])
    destination["x"] = max(0, min(game.active_map_width() - 1, int(game.state.player_x) + 3))
    if int(destination["x"]) == int(game.state.player_x):
        destination["x"] = max(0, int(game.state.player_x) - 3)
    if "world_x" in destination:
        destination["world_x"] = int(destination["world_x"]) + int(destination["x"]) - original_destination_x
    destination["label"] = "Smoke-test destination"
    route_quest = game.register_quest({
        "id": "smoke:visit", "title": "A Visible Destination", "category": "General",
        "description": "Verify tracked world navigation.",
        "objectives": [{
            "id": "visit", "kind": "visit", "description": "Reach the marked destination.",
            "target": 1, "destination": destination,
        }],
    }, accept=True)
    assert game.track_quest(str(route_quest["id"]), announce=False)
    route = game.tracked_quest_navigation()
    assert route["direction"] in {"E", "W"} and int(route["distance"]) > 0
    assert game.tracked_quest_local_position() == (int(destination["x"]), int(destination["y"]))

    defeat_quest = game.register_quest({
        "id": "smoke:defeat_event", "title": "Defeat Dangerous Foes", "category": "Wilderness",
        "objectives": [{
            "id": "defeat", "kind": "defeat", "target_tag": "boss", "target": 2,
            "description": "Defeat two bosses.",
        }],
    }, accept=True)
    assert game.record_quest_event("defeat", target_name="Slime", target_tags=["enemy"]) == 0
    assert game.record_quest_event("defeat", target_name="Ogre", target_tags=["enemy", "boss"]) == 1
    defeat_quest = game.quest_record("smoke:defeat_event")
    assert defeat_quest["objectives"][0]["current"] == 1
    assert "defeated 1/2" in game.quest_progress_label(defeat_quest)

    craft_quest = game.register_quest({
        "id": "smoke:craft_event", "title": "Prepare Supplies", "category": "Town",
        "objectives": [{
            "id": "craft", "kind": "craft", "target_names": ["Field Ration"], "target": 3,
            "description": "Craft three field rations.",
        }],
    }, accept=True)
    assert game.record_quest_event(
        "craft", target_id="ration_recipe", target_name="field ration", amount=3,
        target_tags=["crafted"], note="Prepared field supplies.",
    ) == 1
    assert game.quest_record("smoke:craft_event")["status"] == "ready"

    location_quest = game.register_quest({
        "id": "smoke:location_event", "title": "Recover Mine Evidence", "category": "General",
        "objectives": [{
            "id": "loot", "kind": "loot", "target_name": "Ancient Cog", "location": "Mine",
            "target": 1, "description": "Recover an Ancient Cog in the mine.",
        }],
    }, accept=True)
    assert game.record_quest_event("loot", target_name="Ancient Cog", location="Wilderness") == 0
    assert game.record_quest_event("loot", target_name="ancient cog", location="mine") == 1
    assert game.quest_record("smoke:location_event")["status"] == "ready"

    legacy_snapshots = game.legacy_unified_quest_snapshots()
    legacy_sources = {str(row.get("legacy_source", "")) for row in legacy_snapshots}
    assert {"resident", "companion", "bulletin", "mission"}.issubset(legacy_sources)
    assert all(str(row.get("id", "")).startswith("legacy:") for row in legacy_snapshots)
    assert game.sync_legacy_quest_records() >= 0
    resident_snapshot = next(row for row in legacy_snapshots if row.get("legacy_source") == "resident")
    resident_mirror = game.quest_record(str(resident_snapshot["id"]))
    assert resident_mirror["legacy_managed"] and resident_mirror["legacy_direct_turn_in"]
    assert game.legacy_unified_quest_detail_lines(resident_mirror)
    bulletin_snapshot = next(row for row in legacy_snapshots if row.get("legacy_source") == "bulletin")
    assert not bulletin_snapshot["legacy_direct_turn_in"]
    mission_snapshot = next(row for row in legacy_snapshots if row.get("legacy_source") == "mission")
    assert mission_snapshot["status"] in {"offered", "completed"}

    legacy_bounties_before = json.loads(json.dumps(game.state.active_bounties or {}))
    game.state.active_bounties["smoke:legacy_bounty"] = {
        "id": "smoke:legacy_bounty", "title": "Tracked Smoke Bounty", "status": "accepted",
        "target_name": "Smoke Bandit", "species": "Bandit", "chunk_x": 2, "chunk_y": -1,
        "reward_money": 250, "description": "Verify unified bounty tracking.",
    }
    try:
        bounty_snapshot = next(
            row for row in game.legacy_unified_quest_snapshots()
            if row.get("legacy_source") == "bounty" and row.get("legacy_source_id") == "smoke:legacy_bounty"
        )
        assert bounty_snapshot["status"] == "active" and not bounty_snapshot["legacy_direct_turn_in"]
        bounty_destination = bounty_snapshot["objectives"][0]["destination"]
        assert bounty_destination["chunk_x"] == 2 and bounty_destination["chunk_y"] == -1
        assert "world_x" in bounty_destination and "world_y" in bounty_destination
        game.state.active_bounties["smoke:legacy_bounty"]["status"] = "defeated"
        ready_bounty = next(
            row for row in game.legacy_unified_quest_snapshots()
            if row.get("legacy_source_id") == "smoke:legacy_bounty"
        )
        assert ready_bounty["status"] == "ready" and ready_bounty["objectives"][0]["destination"] == {}
    finally:
        game.state.active_bounties = legacy_bounties_before

    original_legacy_provider = game.legacy_unified_quest_snapshots
    synthetic_legacy = {
        "id": "legacy:smoke:temporary", "title": "Temporary Legacy Work", "category": "General",
        "description": "Verify source disappearance and tracker cleanup.", "status": "active",
        "objectives": [{
            "id": "legacy_progress", "kind": "manual", "target": 1, "current": 0,
            "description": "Wait for the posting to expire.",
        }],
        "legacy_source": "smoke", "legacy_source_id": "temporary", "legacy_managed": True,
    }
    try:
        game.legacy_unified_quest_snapshots = lambda: [dict(synthetic_legacy)]
        game.sync_legacy_quest_records()
        assert game.track_quest("legacy:smoke:temporary", announce=False)
        game.legacy_unified_quest_snapshots = lambda: []
        game.sync_legacy_quest_records()
        assert game.quest_record("legacy:smoke:temporary")["status"] == "abandoned"
        assert game.state.tracked_quest_id == ""
    finally:
        game.legacy_unified_quest_snapshots = original_legacy_provider
        game.sync_legacy_quest_records()

    original_complete_resident = game.complete_resident_request
    completed_through_adapter = []
    game.complete_resident_request = lambda request_id: completed_through_adapter.append(str(request_id)) or True
    try:
        assert game.complete_legacy_unified_quest({
            "legacy_source": "resident", "legacy_source_id": "smoke_request",
        })
    finally:
        game.complete_resident_request = original_complete_resident
    assert completed_through_adapter == ["smoke_request"]

    original_planned_events = json.loads(json.dumps(game.state.planned_events or {}))
    original_temporary_states = json.loads(json.dumps(game.state.temporary_participant_states or {}))
    game.state.planned_events["smoke:invalid_row"] = "not an event"
    game.state.planned_events["smoke:legacy_plan"] = {
        "title": "Legacy Plan", "status": "unknown", "due_day": -4, "due_hour": 99,
        "duration_minutes": 0, "participants": ["invalid", {"name": "Valid Guest"}],
        "destination": "invalid",
    }
    game.state.temporary_participant_states["smoke:orphan"] = {"event_id": "missing:event"}
    normalized_plans = game.ensure_planned_event_state()
    assert "smoke:invalid_row" not in normalized_plans
    assert "smoke:orphan" not in game.state.temporary_participant_states
    legacy_plan = normalized_plans["smoke:legacy_plan"]
    assert legacy_plan["id"] == "smoke:legacy_plan" and legacy_plan["status"] == "planned"
    assert legacy_plan["due_day"] >= 1 and legacy_plan["due_hour"] == 23
    assert legacy_plan["duration_minutes"] == 120 and len(legacy_plan["participants"]) == 1
    assert legacy_plan["destination"] == {}
    game.state.planned_events.pop("smoke:legacy_plan", None)
    now_minute = game.quest_absolute_day() * 1440 + int(game.state.hour) * 60 + int(game.state.minute)
    planned = game.schedule_planned_event({
        "id": "smoke:shared_time", "title": "Smoke Test Walk", "status": "ready",
        "expires_at_minute": now_minute + 60,
        "participants": [{
            "actor_id": str(first_npc.get("id", "")), "name": str(first_npc.get("name", "Guest")),
            "role": str(first_npc.get("role", "Guest")), "kind": "authored",
            "mode": "accompany", "purpose": "testing temporary company",
        }],
    })
    assert game.activate_planned_event(str(planned["id"]))
    assert str(first_npc.get("id", "")) in game.temporary_participant_actor_ids()
    assert game.temporary_participant_at(int(game.state.player_x), int(game.state.player_y))
    assert any("Smoke Test Walk" in line for line in game.planned_event_journal_lines())
    assert any(
        "Smoke Test Walk" in line
        for line in game.planned_event_calendar_lines(game.state.month, game.state.day, game.state.year)
    )
    planned["expires_at_minute"] = now_minute - 1
    game.update_planned_events()
    assert planned["status"] == "completed"
    assert not game.active_temporary_participants()

    store_place = {"id": "town:general_store", "name": "General Store", "kind": "town"}
    store_destination = game.quest_destination_for_known_place(store_place)
    assert store_destination["location"] == "Wilderness"
    assert "world_x" in store_destination and "world_y" in store_destination

    meeting_destination = game.quest_capture_current_destination()
    meeting_destination["label"] = "the smoke-test meeting place"
    meeting = game.schedule_planned_event({
        "id": "smoke:meeting", "title": "Meet the Smoke Tester", "status": "planned",
        "auto_activate": True, "due_day": game.quest_absolute_day(), "due_hour": int(game.state.hour),
        "destination": meeting_destination,
        "participants": [{
            "actor_id": str(first_npc.get("id", "")), "name": str(first_npc.get("name", "Guest")),
            "role": str(first_npc.get("role", "Guest")), "kind": "authored", "mode": "meet",
            "destination": meeting_destination,
        }],
    })
    game.update_planned_events()
    game.update_planned_events()
    assert meeting["status"] == "active"
    meeting_guest = game.temporary_participant_at(int(game.state.player_x), int(game.state.player_y))
    assert meeting_guest and meeting_guest["mode"] == "meet"
    assert game.complete_planned_event("smoke:meeting", reason="smoke-test meeting")

    guide_actor = dict(first_npc)
    guide_relationship_before = game.town_npc_relationship(str(guide_actor.get("id", "")))
    original_known_places = game.dialogue_known_places
    original_arrangement_choose = game.dialogue_choose
    original_arrangement_say = game.dialogue_say
    game.dialogue_known_places = lambda actor, kind: [store_place]
    guide_choices = iter(["guide", "town:general_store"])
    game.dialogue_choose = lambda *args, **kwargs: next(guide_choices)
    game.dialogue_say = lambda *args, **kwargs: True
    try:
        assert game.dialogue_handle_practical_arrangement(guide_actor, "authored", [])
    finally:
        game.dialogue_known_places = original_known_places
        game.dialogue_choose = original_arrangement_choose
        game.dialogue_say = original_arrangement_say
    guide_events = [
        event for event in game.state.planned_events.values()
        if isinstance(event, dict) and str(event.get("id", "")).startswith("guided_route:")
    ]
    assert guide_events and guide_events[-1]["status"] == "active"
    guide_event = guide_events[-1]
    guide_quest = game.quest_record(str(guide_event["quest_id"]))
    assert guide_quest and game.state.tracked_quest_id == guide_quest["id"]
    assert game.complete_planned_event(str(guide_event["id"]), reason="arrived together")
    assert game.quest_record(str(guide_quest["id"]))["status"] == "completed"
    assert game.town_npc_relationship(str(guide_actor.get("id", ""))) >= guide_relationship_before + 2
    game.state.town_npc_relationships[str(guide_actor.get("id", ""))] = guide_relationship_before

    date_actor = next(
        npc for npc in game.state.town_npcs
        if game.is_marriageable_npc(npc) and game.is_heterosexual_match_for_player(npc)
    )
    date_actor_id = str(date_actor["id"])
    date_relationship_existed = date_actor_id in game.state.town_npc_relationships
    date_relationship_before = game.town_npc_relationship(date_actor_id)
    date_courtship_before = game.town_npc_courtship_count(date_actor_id)
    date_last_court_before = game.state.town_npc_last_court_day.get(date_actor_id)
    dating_before = list(game.state.dating_npc_ids or [])
    date_social_before = json.loads(json.dumps(game.state.npc_dialogue_social_state or {}))
    original_activity_known_places = game.dialogue_known_places
    original_activity_known_people = game.dialogue_known_people
    original_activity_choose = game.dialogue_choose
    original_activity_say = game.dialogue_say
    original_activity_autosave = game.autosave_with_message
    game.state.town_npc_relationships[date_actor_id] = max(100, date_relationship_before)
    game.state.town_npc_last_court_day.pop(date_actor_id, None)
    game.dialogue_known_places = lambda actor, kind: []
    date_choices = iter(["__HERE__", "1", "10"])
    game.dialogue_choose = lambda *args, **kwargs: next(date_choices)
    game.dialogue_say = lambda *args, **kwargs: True
    game.autosave_with_message = lambda message: game.set_message(message)
    try:
        assert game.dialogue_schedule_shared_activity(date_actor, "authored", [], romantic=True)
        date_event = next(
            event for event in game.state.planned_events.values()
            if isinstance(event, dict) and str(event.get("id", "")).startswith(f"relationship_date:{date_actor_id}:")
        )
        assert date_event["status"] == "planned" and date_event["requires_attendance"]
        assert game.open_planned_events_for_actor(date_actor_id, ("relationship_date",)) == [date_event]
        date_month, date_day, date_year = game.date_after_days(1)
        assert any("Date with" in line for line in game.planned_event_calendar_lines(date_month, date_day, date_year))
        assert any("Date with" in line for line in game.planned_event_journal_lines())
        date_event["status"] = "ready"
        assert game.activate_planned_event(str(date_event["id"]))
        date_participant = next(
            row for row in game.active_temporary_participants()
            if str(row.get("event_id", "")) == str(date_event["id"])
        )
        relationship_at_arrival = game.town_npc_relationship(date_actor_id)
        game.dialogue_choose = lambda *args, **kwargs: "conversation"
        assert game.talk_to_temporary_participant(date_participant)
        assert date_event["status"] == "completed"
        assert date_event["activity_choice"] == "conversation"
        assert date_event["relationship_gain"] > 0
        assert game.town_npc_relationship(date_actor_id) > relationship_at_arrival
        assert game.town_npc_courtship_count(date_actor_id) == date_courtship_before + 1
        assert not game.open_planned_events_for_actor(date_actor_id, ("relationship_date",))
        date_meeting = next(
            row for row in game.dialogue_social_slot(date_actor, "authored")["meetings"]
            if str(row.get("event_id", "")) == str(date_event["id"])
        )
        assert date_meeting["completed"]

        outing_choices = iter(["__HERE__", "2", "14"])
        game.dialogue_choose = lambda *args, **kwargs: next(outing_choices)
        assert game.dialogue_schedule_shared_activity(date_actor, "authored", [], romantic=False)
        outing_event = next(
            event for event in game.state.planned_events.values()
            if isinstance(event, dict) and str(event.get("id", "")).startswith(f"social_outing:{date_actor_id}:")
        )
        outing_event["status"] = "ready"
        assert game.activate_planned_event(str(outing_event["id"]))
        outing_participant = next(
            row for row in game.active_temporary_participants()
            if str(row.get("event_id", "")) == str(outing_event["id"])
        )
        outing_relationship_before = game.town_npc_relationship(date_actor_id)
        game.dialogue_choose = lambda *args, **kwargs: "exploration"
        assert game.talk_to_temporary_participant(outing_participant)
        assert outing_event["status"] == "completed"
        assert outing_event["activity_choice"] == "exploration"
        assert game.town_npc_relationship(date_actor_id) == outing_relationship_before + 2

        gathering_people = [
            npc for npc in game.state.town_npcs
            if str(npc.get("id", "")) != date_actor_id
        ][:3]
        gathering_host, gathering_guest_one, gathering_guest_two = gathering_people
        gathering_relationships_before = {
            str(npc["id"]): (
                str(npc["id"]) in game.state.town_npc_relationships,
                game.town_npc_relationship(str(npc["id"])),
            )
            for npc in gathering_people
        }
        game.state.town_npc_relationships[str(gathering_host["id"])] = 50
        game.dialogue_known_people = lambda actor, kind: [gathering_guest_one, gathering_guest_two]
        gathering_arrangement_options = []
        game.dialogue_choose = lambda actor, prompt, phase, options, transcript: (
            gathering_arrangement_options.extend(options), "back"
        )[-1]
        assert game.dialogue_handle_practical_arrangement(gathering_host, "authored", [])
        assert "gathering" in {value for value, _label, _hint in gathering_arrangement_options}
        gathering_choices = iter([
            str(gathering_guest_one["id"]), str(gathering_guest_two["id"]),
            "__HERE__", "1", "12",
        ])
        game.dialogue_choose = lambda *args, **kwargs: next(gathering_choices)
        assert game.dialogue_schedule_group_gathering(gathering_host, "authored", [])
        gathering_event = next(
            event for event in game.state.planned_events.values()
            if isinstance(event, dict) and str(event.get("id", "")).startswith(f"social_gathering:{gathering_host['id']}:")
        )
        assert len(gathering_event["participants"]) == 3
        assert gathering_event["requires_attendance"]
        gathering_event["status"] = "ready"
        assert game.activate_planned_event(str(gathering_event["id"]))
        gathering_positions = {
            position: row for position, row in game.temporary_participant_position_lookup().items()
            if str(row.get("event_id", "")) == str(gathering_event["id"])
        }
        assert len(gathering_positions) == 3
        assert len({(int(row["x"]), int(row["y"])) for row in gathering_positions.values()}) == 3
        gathering_actor_ids = {str(row.get("actor_id", "")) for row in gathering_positions.values()}
        assert gathering_actor_ids.issubset(game.temporary_participant_actor_ids())
        gathering_runtime_host = next(
            row for row in gathering_positions.values()
            if str(row.get("actor_id", "")) == str(gathering_host["id"])
        )
        gathering_before_completion = {
            str(npc["id"]): game.town_npc_relationship(str(npc["id"]))
            for npc in gathering_people
        }
        game.dialogue_choose = lambda *args, **kwargs: "plans"
        assert game.talk_to_temporary_participant(gathering_runtime_host)
        assert gathering_event["status"] == "completed"
        assert gathering_event["activity_choice"] == "plans"
        assert len(gathering_event["relationship_gains"]) == 3
        for npc in gathering_people:
            npc_id = str(npc["id"])
            assert (
                game.town_npc_relationship(npc_id) - gathering_before_completion[npc_id]
                == int(gathering_event["relationship_gains"][npc_id])
            )
        assert int(gathering_event["relationship_gains"][str(gathering_host["id"])]) == 2
        assert all(
            0 <= int(gathering_event["relationship_gains"][str(guest["id"])]) <= 1
            for guest in (gathering_guest_one, gathering_guest_two)
        )
        assert all(
            any(
                str(meeting.get("event_id", "")) == str(gathering_event["id"]) and meeting.get("completed")
                for meeting in game.dialogue_social_slot(npc, "authored")["meetings"]
            )
            for npc in gathering_people
        )
        for npc_id, (existed, relationship_before) in gathering_relationships_before.items():
            if existed:
                game.state.town_npc_relationships[npc_id] = relationship_before
            else:
                game.state.town_npc_relationships.pop(npc_id, None)

        used_social_ids = {date_actor_id, *(str(npc["id"]) for npc in gathering_people)}
        invitation_actors = [
            npc for npc in game.state.town_npcs
            if str(npc.get("id", "")) not in used_social_ids
        ][:2]
        invitation_actor, declining_actor = invitation_actors
        invitation_actor_id = str(invitation_actor["id"])
        declining_actor_id = str(declining_actor["id"])
        invitation_relationship_restore = {
            npc_id: (npc_id in game.state.town_npc_relationships, game.town_npc_relationship(npc_id))
            for npc_id in (invitation_actor_id, declining_actor_id)
        }
        invitation_dialogue_restore = {
            npc_id: (npc_id in game.state.town_npc_dialogue_counts, game.town_npc_dialogue_count(npc_id))
            for npc_id in (invitation_actor_id, declining_actor_id)
        }
        for npc_id in (invitation_actor_id, declining_actor_id):
            game.state.town_npc_relationships[npc_id] = 80
            game.state.town_npc_dialogue_counts[npc_id] = 5

        invitation = game.dialogue_prepare_npc_invitation(invitation_actor, "authored", force=True)
        assert invitation and invitation["status"] == "pending"
        invitation_slot = game.dialogue_social_slot(invitation_actor, "authored")
        invitation_slot["initiation"] = {}
        callout = game.dialogue_initiation_callout(invitation_actor, "authored")
        assert game.state.player_name in callout and "join me" in callout
        invitation_choices = iter(["time", "2", "18", "accept", "goodbye"])
        game.dialogue_choose = lambda *args, **kwargs: next(invitation_choices)
        game.dialogue_say = lambda actor, text, phase, transcript: (
            transcript.append({"speaker": str(actor.get("name", "NPC")), "text": str(text), "phase": str(phase)}), True
        )[-1]
        invitation_result = game.run_unified_npc_conversation(
            invitation_actor, kind="authored", first_meeting=False, repeated_today=False
        )
        assert invitation_result["completed"]
        assert invitation["status"] == "accepted"
        invitation_event = game.state.planned_events[str(invitation["event_id"])]
        assert invitation_event["initiated_by_npc"]
        assert invitation_event["due_hour"] == 18
        assert invitation_event["due_day"] == game.dialogue_absolute_day() + 2
        assert any("Outing with" in line or "Date with" in line for line in game.planned_event_journal_lines())
        assert game.open_planned_events_for_actor(
            invitation_actor_id, ("relationship_date", "social_outing")
        ) == [invitation_event]

        declining_invitation = game.dialogue_prepare_npc_invitation(declining_actor, "authored", force=True)
        declining_relationship_before = game.town_npc_relationship(declining_actor_id)
        game.dialogue_choose = lambda *args, **kwargs: "decline"
        assert game.dialogue_handle_npc_invitation(
            declining_actor, "authored", declining_invitation, []
        )
        assert declining_invitation["status"] == "declined"
        assert game.town_npc_relationship(declining_actor_id) == declining_relationship_before
        assert game.dialogue_social_slot(declining_actor, "authored")["invitation_history"][-1]["status"] == "declined"
        for npc_id, (existed, relationship_before) in invitation_relationship_restore.items():
            if existed:
                game.state.town_npc_relationships[npc_id] = relationship_before
            else:
                game.state.town_npc_relationships.pop(npc_id, None)
        for npc_id, (existed, dialogue_before) in invitation_dialogue_restore.items():
            if existed:
                game.state.town_npc_dialogue_counts[npc_id] = dialogue_before
            else:
                game.state.town_npc_dialogue_counts.pop(npc_id, None)

        story_worker = next(
            npc for npc in game.state.town_npcs if "Blacksmith" in str(npc.get("role", ""))
        )
        story_worker_id = str(story_worker["id"])
        story_worker_relationship_existed = story_worker_id in game.state.town_npc_relationships
        story_worker_relationship_before = game.town_npc_relationship(story_worker_id)
        story_wood_before = int(game.state.inventory.get("Wood", 0) or 0)
        story_stone_before = int(game.state.inventory.get("Stone", 0) or 0)
        story_coal_before = int(game.state.inventory.get("Coal", 0) or 0)
        game.state.town_npc_relationships[story_worker_id] = 20
        story_thread = {
            "id": "smoke:story:work", "profile": "work", "title": "Pressure at Work",
            "stage": 0, "status": "active", "created_day": game.dialogue_absolute_day(),
            "updated_day": game.dialogue_absolute_day(), "last_discussed_day": 0,
        }
        game.dialogue_social_slot(story_worker, "authored")["threads"].append(story_thread)
        game.dialogue_choose = lambda *args, **kwargs: "support"
        game.dialogue_say = lambda *args, **kwargs: True
        assert game.dialogue_handle_thread(story_worker, "authored", story_thread, [])
        story_work_quest = game.quest_record(str(story_thread["quest_id"]))
        story_work_objective = game.quest_current_objective(story_work_quest)
        assert story_work_quest["category"] == "Relationships"
        assert story_work_objective["kind"] == "item" and story_work_objective["item"] == "Wood"
        assert story_thread["stage"] == 0 and story_thread["support_status"] == "active"
        game.state.inventory["Wood"] = int(story_work_objective["target"])
        relationship_before_story_turn_in = game.town_npc_relationship(story_worker_id)
        assert game.dialogue_handle_thread(story_worker, "authored", story_thread, [])
        story_work_quest = game.quest_record(str(story_thread["quest_id"]))
        assert story_work_quest["status"] == "completed"
        assert int(game.state.inventory.get("Wood", 0) or 0) == 0
        assert game.town_npc_relationship(story_worker_id) == relationship_before_story_turn_in + 3
        assert story_thread["stage"] == 1 and story_thread["support_status"] == "completed"
        first_story_quest_id = str(story_work_quest["id"])
        assert len(story_thread["support_history"]) == 1
        quest_count_after_first_support = len([
            quest for quest in game.state.quest_records.values()
            if isinstance(quest, dict) and str(quest.get("dialogue_thread_id", "")) == str(story_thread["id"])
        ])
        assert game.dialogue_handle_thread(story_worker, "authored", story_thread, [])
        assert len([
            quest for quest in game.state.quest_records.values()
            if isinstance(quest, dict) and str(quest.get("dialogue_thread_id", "")) == str(story_thread["id"])
        ]) == quest_count_after_first_support

        story_thread["last_discussed_day"] = game.dialogue_absolute_day() - 1
        assert game.dialogue_handle_thread(story_worker, "authored", story_thread, [])
        second_story_quest = game.quest_record(str(story_thread["quest_id"]))
        second_story_objective = game.quest_current_objective(second_story_quest)
        assert str(second_story_quest["id"]) != first_story_quest_id
        assert int(second_story_quest["dialogue_thread_stage"]) == 1
        assert (second_story_objective["item"], int(second_story_objective["target"])) == ("Stone", 8)
        game.state.inventory["Stone"] = 8
        assert game.dialogue_handle_thread(story_worker, "authored", story_thread, [])
        second_story_quest = game.quest_record(str(second_story_quest["id"]))
        assert second_story_quest["status"] == "completed" and story_thread["stage"] == 2
        assert int(game.state.inventory.get("Stone", 0) or 0) == 0

        story_thread["last_discussed_day"] = game.dialogue_absolute_day() - 1
        assert game.dialogue_handle_thread(story_worker, "authored", story_thread, [])
        third_story_quest = game.quest_record(str(story_thread["quest_id"]))
        third_story_objective = game.quest_current_objective(third_story_quest)
        assert len({first_story_quest_id, str(second_story_quest["id"]), str(third_story_quest["id"])}) == 3
        assert int(third_story_quest["dialogue_thread_stage"]) == 2
        assert (third_story_objective["item"], int(third_story_objective["target"])) == ("Coal", 4)
        game.state.inventory["Coal"] = 4
        assert game.dialogue_handle_thread(story_worker, "authored", story_thread, [])
        third_story_quest = game.quest_record(str(third_story_quest["id"]))
        assert third_story_quest["status"] == "completed"
        assert story_thread["stage"] == 3 and story_thread["status"] == "resolved"
        assert len(story_thread["support_history"]) == 3
        assert [int(row["stage"]) for row in story_thread["support_history"]] == [0, 1, 2]
        assert game.town_npc_relationship(story_worker_id) == relationship_before_story_turn_in + 3 + 4 + 5
        assert any(
            str(row.get("id", "")) == str(story_thread["id"])
            for row in game.dialogue_social_slot(story_worker, "authored")["thread_history"]
        )
        story_activity_actor = dict(story_worker)
        for field in ("social_partner_id", "social_day_key", "social_phase", "social_activity"):
            story_activity_actor.pop(field, None)
        assert game.town_npc_activity_label(story_activity_actor) == str(
            story_worker["story_outcome"]["activity"]
        )

        story_route_actor = next(
            npc for npc in game.state.town_npcs
            if "Fisher" in str(npc.get("role", "")) or "Courier" in str(npc.get("role", ""))
        )
        story_route_id = str(story_route_actor["id"])
        story_route_relationship_existed = story_route_id in game.state.town_npc_relationships
        story_route_relationship_before = game.town_npc_relationship(story_route_id)
        game.state.town_npc_relationships[story_route_id] = 20
        story_route_thread = {
            "id": "smoke:story:roads", "profile": "roads", "title": "A Route in Question",
            "stage": 0, "status": "active", "created_day": game.dialogue_absolute_day(),
            "updated_day": game.dialogue_absolute_day(), "last_discussed_day": 0,
        }
        game.dialogue_social_slot(story_route_actor, "authored")["threads"].append(story_route_thread)
        game.dialogue_known_places = original_activity_known_places
        story_route_quest = game.dialogue_begin_story_support(
            story_route_actor, "authored", story_route_thread
        )
        story_route_objective = game.quest_current_objective(story_route_quest)
        assert story_route_objective["kind"] == "visit"
        story_route_participants = [
            participant for participant in game.active_temporary_participants()
            if str(participant.get("quest_id", "")) == str(story_route_quest["id"])
        ]
        assert len(story_route_participants) == 1
        assert story_route_participants[0]["mode"] == "accompany"
        assert game.track_quest(str(story_route_quest["id"]), announce=False)
        story_route_quest = game.quest_record(str(story_route_quest["id"]))
        story_route_objective = game.quest_current_objective(story_route_quest)
        story_route_objective["complete"] = True
        game.refresh_quest_states()
        story_route_quest = game.quest_record(str(story_route_quest["id"]))
        assert story_route_quest["status"] == "ready"
        assert game.quest_tracking_destination(story_route_quest)["label"] == str(story_route_actor["name"])
        story_resolution, story_relationship_gain = game.dialogue_resolve_story_support(
            story_route_actor, "authored", story_route_thread
        )
        story_route_quest = game.quest_record(str(story_route_quest["id"]))
        assert story_resolution and story_relationship_gain == 3
        assert story_route_quest["status"] == "completed"
        assert not [
            participant for participant in game.active_temporary_participants()
            if str(participant.get("quest_id", "")) == str(story_route_quest["id"])
        ]
        assert story_route_thread["stage"] == 1
        if story_worker_relationship_existed:
            game.state.town_npc_relationships[story_worker_id] = story_worker_relationship_before
        else:
            game.state.town_npc_relationships.pop(story_worker_id, None)
        if story_route_relationship_existed:
            game.state.town_npc_relationships[story_route_id] = story_route_relationship_before
        else:
            game.state.town_npc_relationships.pop(story_route_id, None)
        if story_wood_before:
            game.state.inventory["Wood"] = story_wood_before
        else:
            game.state.inventory.pop("Wood", None)
        if story_stone_before:
            game.state.inventory["Stone"] = story_stone_before
        else:
            game.state.inventory.pop("Stone", None)
        if story_coal_before:
            game.state.inventory["Coal"] = story_coal_before
        else:
            game.state.inventory.pop("Coal", None)

        missed_event = game.schedule_planned_event({
            "id": "smoke:missed_outing", "title": "Missed Outing", "kind": "social_outing",
            "status": "active", "requires_attendance": True,
            "expires_at_minute": now_minute - 1,
        })
        game.update_planned_events()
        assert missed_event["status"] == "missed"

        management_day = game.quest_absolute_day() + 2
        managed_a = game.schedule_planned_event({
            "id": "smoke:managed_a", "title": "Managed Picnic", "kind": "social_outing",
            "status": "planned", "requires_attendance": True,
            "due_day": management_day, "due_hour": 14, "duration_minutes": 180,
            "destination": {"location": "Wilderness", "label": "Lakeside trail"},
        })
        managed_b = game.schedule_planned_event({
            "id": "smoke:managed_b", "title": "Managed Date", "kind": "relationship_date",
            "status": "planned", "requires_attendance": True,
            "due_day": management_day, "due_hour": 15, "duration_minutes": 120,
        })
        assert managed_a["conflict_ids"] == ["smoke:managed_b"]
        assert managed_b["conflict_ids"] == ["smoke:managed_a"]
        old_expiry = int(managed_b["expires_at_minute"])
        assert game.reschedule_planned_event("smoke:managed_b", management_day + 1, 10)
        assert managed_b["due_day"] == management_day + 1 and managed_b["due_hour"] == 10
        assert managed_b["reschedule_count"] == 1 and int(managed_b["expires_at_minute"]) != old_expiry
        assert not managed_a["conflict_ids"] and not managed_b["conflict_ids"]
        assert game.cancel_planned_event("smoke:managed_b")
        assert managed_b["status"] == "cancelled"
        assert any("Managed Date [Cancelled]" in line for line in game.planned_event_history_lines())
        assert not game.reschedule_planned_event("smoke:managed_b", management_day + 3, 12)

        protected = game.schedule_planned_event({
            "id": "smoke:protected_plan", "title": "Quest-critical Guide", "kind": "meeting",
            "status": "planned", "requires_attendance": True, "quest_id": "smoke:visit",
            "due_day": management_day, "due_hour": 8,
        })
        assert not game.planned_event_player_manageable(protected)
        assert not game.cancel_planned_event("smoke:protected_plan")

        original_weather = game.state.weather
        game.state.weather = "Stormy"
        managed_a["due_day"], managed_a["due_hour"] = game.quest_absolute_day(), int(game.state.hour)
        managed_a["expires_at_minute"] = now_minute + 240
        game.update_planned_events()
        assert managed_a["status"] == "planned" and managed_a["due_day"] == game.quest_absolute_day() + 1
        assert managed_a["weather_delays"] == 1
        game.state.weather = original_weather

        deceased_before = list(game.state.deceased_spouse_npc_ids or [])
        game.state.deceased_spouse_npc_ids = deceased_before + ["smoke:unavailable_person"]
        unavailable = game.schedule_planned_event({
            "id": "smoke:unavailable", "title": "Unavailable Guest", "kind": "social_outing",
            "status": "planned", "requires_attendance": True,
            "due_day": game.quest_absolute_day() + 1, "due_hour": 12,
            "participants": [{"actor_id": "smoke:unavailable_person", "name": "Unavailable Guest"}],
        })
        game.update_planned_events()
        assert unavailable["status"] == "cancelled"
        assert "unavailable participant" in unavailable["completion_reason"]
        game.state.deceased_spouse_npc_ids = deceased_before
    finally:
        game.dialogue_known_places = original_activity_known_places
        game.dialogue_known_people = original_activity_known_people
        game.dialogue_choose = original_activity_choose
        game.dialogue_say = original_activity_say
        game.autosave_with_message = original_activity_autosave
        if date_relationship_existed:
            game.state.town_npc_relationships[date_actor_id] = date_relationship_before
        else:
            game.state.town_npc_relationships.pop(date_actor_id, None)
        game.state.town_npc_courtship_counts[date_actor_id] = date_courtship_before
        if date_last_court_before is None:
            game.state.town_npc_last_court_day.pop(date_actor_id, None)
        else:
            game.state.town_npc_last_court_day[date_actor_id] = date_last_court_before
        game.state.dating_npc_ids = dating_before
        game.state.npc_dialogue_social_state = date_social_before
    game.state.planned_events = original_planned_events
    game.state.temporary_participant_states = original_temporary_states
    game.state.quest_records = original_quest_records
    game.state.tracked_quest_id = original_tracked_quest_id
    situation_turns = []
    situation_options = []
    original_say = game.dialogue_say
    original_choose = game.dialogue_choose
    game.dialogue_say = lambda actor, text, phase, transcript: (
        situation_turns.append((str(phase), str(text))), True
    )[-1]
    game.dialogue_choose = lambda actor, prompt, phase, options, transcript: (
        situation_options.extend(options), "decline"
    )[-1]
    try:
        assert game.dialogue_handle_work_situation(first_npc, "authored", [])
    finally:
        game.dialogue_say = original_say
        game.dialogue_choose = original_choose
    assert any(value == "decline" and "no relationship penalty" in hint for value, _label, hint in situation_options)
    assert "honest refusal" in situation_turns[-1][1]
    game.state.npc_dialogue_promises = original_promises
    game.state.completed_errand_ids = original_completed_errands
    tutorials = game.tutorial_catalog()
    assert "quick_start" in tutorials
    assert any("bookshelf" in line.lower() for line in tutorials["quick_start"]["lines"])
    assert len(tutorials) >= 35
    tutorial_category_keys = [
        key
        for _category_title, _category_hint, guide_keys in game.tutorial_categories()
        for key in guide_keys
    ]
    assert set(tutorial_category_keys) == set(tutorials)
    assert len(tutorial_category_keys) == len(set(tutorial_category_keys))
    assert all(len(list(guide["lines"])) >= 6 for guide in tutorials.values())
    assert any("5" in line and "level" in line.lower() for line in tutorials["stamina_leveling"]["lines"])
    assert "dynasty_and_succession" in tutorials
    assert "politics_and_elections" in tutorials
    assert "followers_parties_tasks" in tutorials
    assert "tutorial_bookshelf_note" in {str(letter.get("id")) for letter in game.generated_mail()}
    default_profile = build_player_combat_profile(game.state)
    assert default_profile["name"] == game.state.player_name
    assert default_profile["weapon"] == DEFAULT_COMBAT_WEAPON
    assert default_profile["armor"] == DEFAULT_COMBAT_ARMOR
    assert default_profile["accessory"] == DEFAULT_COMBAT_ACCESSORY
    assert default_profile["attack"] >= game.state.combat_attack
    combat_lines = game.combat_status_lines()
    assert any("COMBAT STATUS" in line for line in combat_lines)
    assert any("Combat HP persists" in line for line in combat_lines)
    assert any("Deepest Floor" in line for line in combat_lines)
    assert any("Party:" in line for line in combat_lines)
    mission_board_lines = game.combat_mission_board_lines()
    assert any("COMBAT MISSION BOARD" in line for line in mission_board_lines)
    assert any("Contracts cleared" in line for line in mission_board_lines)
    assert any("Seasonal contract" in line for line in mission_board_lines)
    assert "open" in game.combat_mission_board_hint() or "cleared" in game.combat_mission_board_hint()
    farm_pest_lines = game.combat_mission_lines(farmstead_main.tactical_mission_builtin_presets()[0])
    assert any("Posted by: Mira" in line for line in farm_pest_lines)
    assert any("Estimated Rewards:" in line for line in farm_pest_lines)
    assert any("Estimated Time:" in line for line in farm_pest_lines)
    assert any("Town Effect:" in line for line in farm_pest_lines)
    calendar_lines = game.today_calendar_notice_lines()
    assert any("CALENDAR NOTICES" in line for line in calendar_lines)
    assert any("Today:" in line for line in calendar_lines)
    long_calendar_event = (
        "The regional caravan council gathers at the restored market hall "
        "to review winter supply agreements and public road maintenance."
    )
    wrapped_calendar_events = game.calendar_event_panel_lines(
        [long_calendar_event],
        width=50,
        max_rows=6,
    )
    assert len(wrapped_calendar_events) > 1
    assert all(
        visible_terminal_len(line) <= 50
        for line in wrapped_calendar_events
    )
    crowded_calendar_events = game.calendar_event_panel_lines(
        [long_calendar_event] * 5,
        width=50,
        max_rows=6,
    )
    assert len(crowded_calendar_events) <= 6
    assert any("more event" in line for line in crowded_calendar_events)
    calendar_wrap_game = FarmGame()
    calendar_panel_lines = []
    original_clear_screen = farmstead_main.clear_screen
    try:
        farmstead_main.clear_screen = lambda: None
        calendar_wrap_game.centered_print = (
            lambda text="", width=data.UI_WIDTH: calendar_panel_lines.append(text)
        )
        calendar_wrap_game.selected_calendar_events_text = (
            lambda *_args: [long_calendar_event] * 3
        )
        calendar_wrap_game.draw_calendar_panel(3, 100, 1)
    finally:
        farmstead_main.clear_screen = original_clear_screen
    assert calendar_panel_lines
    assert all(
        visible_terminal_len(line) <= 52
        for line in calendar_panel_lines
    )
    assert game.seasonal_combat_contract_label_for_date(game.state.month, game.state.day, game.state.year)
    hazard_found = False
    hm, hd, hy = game.state.month, game.state.day, game.state.year
    for _ in range(90):
        if game.mine_hazard_label_for_date(hm, hd, hy):
            hazard_found = True
            break
        hm, hd, hy = helpers.advance_date(hm, hd, hy)
    assert hazard_found

    # Every card game shares the player's authored card faces. Single-character
    # ranks and the wider ten intentionally use different spacing.
    king_heart = [line.rstrip() for line in playing_cards.plain_card_lines(("K", "H"))]
    ten_spade = [line.rstrip() for line in playing_cards.plain_card_lines(("10", "S"))]
    assert king_heart == [
        "+-----+",
        "|K    |",
        "|     |",
        "|  ♥  |",
        "|     |",
        "|    K|",
        "+-----+",
    ]
    assert ten_spade == [
        "+-----+",
        "|10   |",
        "|     |",
        "|  ♠  |",
        "|     |",
        "|   10|",
        "+-----+",
    ]
    assert all(
        len(line) == playing_cards.CARD_RENDER_WIDTH
        for line in playing_cards.plain_card_lines(("9", "C"))
    )
    assert playing_cards.card_suit_glyph("D") == "♦"
    assert playing_cards.card_suit_glyph("C") == "♣"
    assert playing_cards.card_color(("Q", "H")) == support.C.ROOF_RED
    assert playing_cards.card_color(("Q", "S")) == support.C.TUNDRA
    hidden_card = playing_cards.plain_card_lines(("A", "S"), hidden=True)
    assert any("?" in line for line in hidden_card)
    wrapped_cards = playing_cards.rendered_card_rows(
        [f"{rank}H" for rank in ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")],
        max_per_row=7,
        cursor=8,
        selected=[8],
        show_numbers=True,
    )
    assert sum("+-----+" in ui.strip_ansi(line) for line in wrapped_cards) == 4
    assert any("^SELECTED^" in line for line in wrapped_cards)

    # Game access is physically distributed among venue fixtures and movable furniture.
    assert len(game_tables.GAME_TABLE_DATA) == 8
    assert game_tables.venue_game_ids("Mae's Inn", "maes_inn") == (
        "blackjack",
        "hearts",
        "checkers",
    )
    stable_venue_games = game_tables.venue_game_ids("settlement:12,9:inn:2", "inn", count=3)
    assert stable_venue_games == game_tables.venue_game_ids(
        "settlement:12,9:inn:2", "inn", count=3
    )
    assert len(stable_venue_games) == 3
    assert {
        game_tables.GAME_TABLE_DATA[game_id]["category"]
        for game_id in stable_venue_games
    } == {"card", "board"}
    rotating_tables = game_tables.rotating_game_furniture("1:Spring:0", count=2)
    assert len(rotating_tables) == 2
    assert all(name in game_tables.GAME_TABLE_BY_FURNITURE for name in rotating_tables)
    assert game_tables.rare_recovered_game_table("ruin:test", 1.0) in game_tables.GAME_TABLE_BY_FURNITURE
    for game_id, table in game_tables.GAME_TABLE_DATA.items():
        furniture = data.INFRASTRUCTURE_DATA[str(table["name"])]
        assert furniture["game_id"] == game_id
        assert furniture["category"] == "furniture"
        assert furniture["footprint"] == [3, 1]
    game_table_game = FarmGame()
    opened_game_tables = []
    game_table_game.blackjack_table_menu = (
        lambda venue: opened_game_tables.append(("blackjack", venue))
    )
    assert game_table_game.use_game_table_furniture(
        "Blackjack Table",
        "Smoke Test Game Room",
    )
    assert opened_game_tables == [("blackjack", "Smoke Test Game Room")]
    assert game_table_game.state.tavern_game_discoveries == ["blackjack"]
    game_table_game.discover_game_tables(("checkers", "invalid", "blackjack"))
    assert game_table_game.state.tavern_game_discoveries == ["blackjack", "checkers"]
    authored_game_table_game = FarmGame()
    authored_game_table_game.state.location = "GeneralStoreInterior"
    authored_game_grid = [["." for _ in range(3)] for _ in range(3)]
    authored_game_table_game.active_map = lambda: authored_game_grid
    authored_game_table_game.in_active_bounds = (
        lambda x, y: 0 <= int(x) < 3 and 0 <= int(y) < 3
    )
    opened_authored_tables = []
    authored_game_table_game.open_physical_game_table = (
        lambda game_id, venue: opened_authored_tables.append((game_id, venue))
    )
    for game_id, table in game_tables.GAME_TABLE_DATA.items():
        glyph = str(table["glyph"])
        authored_game_grid[1][1] = glyph
        authored_record = authored_game_table_game.town_interior_tile_catalog(
            "GeneralStoreInterior"
        )[glyph]
        assert str(table["name"]) in authored_record["hint"]
        assert authored_game_table_game.use_town_interior_game_table_action(1, 1)
        assert opened_authored_tables[-1][0] == game_id
    assert len(opened_authored_tables) == len(game_tables.GAME_TABLE_DATA)
    game_table_game.state.location = "HouseInterior"
    game_table_game.state.inventory["Chess Table"] = 1
    chess_table_position = next(
        (x, y)
        for y, row in enumerate(game_table_game.house_map)
        for x, _tile in enumerate(row)
        if game_table_game.can_place_object("Chess Table", x, y)[0]
    )
    assert game_table_game.place_inventory_object_at(
        "Chess Table", *chess_table_position, autosave=False
    )
    chess_table_key, chess_table_name, chess_table_x, chess_table_y = (
        game_table_game.placed_object_at(chess_table_position[0] + 1, chess_table_position[1])
    )
    assert chess_table_key == game_table_game.obj_key(*chess_table_position)
    assert chess_table_name == "Chess Table"
    assert (chess_table_x, chess_table_y) == chess_table_position
    game_table_game.chess_menu = (
        lambda venue: opened_game_tables.append(("chess", venue))
    )
    game_table_game.use_house_furniture("Chess Table")
    assert opened_game_tables[-1] == ("chess", "Home Game Room")
    assert "chess" in game_table_game.state.tavern_game_discoveries
    sanitized_game_table_state = GameState(**prepare_loaded_state_data({
        "tavern_game_discoveries": ["invalid", "chess", "chess"],
    }))
    assert sanitized_game_table_state.tavern_game_discoveries == ["chess"]
    assert {"1", "3", "5"} <= set(
        "".join("".join(row) for row in game_table_game.make_inn_interior_map())
    )
    authored_public_interiors = (
        game_table_game.make_general_store_map(),
        game_table_game.make_blacksmith_interior_map(),
        game_table_game.make_library_interior_map(),
        game_table_game.make_furniture_store_map(),
        game_table_game.make_carpenter_store_map(),
        game_table_game.make_museum_interior_map(),
    )
    assert all(
        "|" not in "".join("".join(row) for row in interior)
        for interior in authored_public_interiors
    )
    modular_inn_grid = game_table_game.make_inn_interior_map()
    starting_inn_plan = procedural_interiors.procedural_interior_room_plan(
        "inn", 2, 1, 0, None, 2
    )
    assert sum(row.count("B") for row in modular_inn_grid) == int(
        starting_inn_plan["guest_capacity"]
    )
    assert sum(row.count("_") for row in modular_inn_grid) >= int(
        starting_inn_plan["guest_capacity"]
    )
    roadside_table_game = FarmGame()
    roadside_table_game.state.location = "WildernessStructure"
    roadside_table_game.state.wilderness_chunk_x = 91
    roadside_table_game.state.wilderness_chunk_y = 73
    roadside_table_game.state.current_wilderness_structure_key = "91,73"
    roadside_record = roadside_table_game.wilderness_structure_record()
    roadside_record.update({
        "type_id": "roadside_inn",
        "name": "Smoke Test Roadside Inn",
        "repaired": True,
    })
    roadside_map = roadside_table_game.wilderness_structure_map()
    expected_roadside_games = game_tables.venue_game_ids(
        "91,73", "roadside_inn", count=2
    )
    roadside_glyph_positions = {
        tile: (x, y)
        for y, row in enumerate(roadside_map)
        for x, tile in enumerate(row)
        if tile in game_tables.GAME_TABLE_BY_GLYPH
    }
    assert {
        str(game_tables.GAME_TABLE_DATA[game_id]["glyph"])
        for game_id in expected_roadside_games
    } == set(roadside_glyph_positions)
    opened_roadside_tables = []
    roadside_table_game.open_physical_game_table = (
        lambda game_id, venue: opened_roadside_tables.append((game_id, venue))
    )
    roadside_glyph = str(
        game_tables.GAME_TABLE_DATA[expected_roadside_games[0]]["glyph"]
    )
    roadside_table_game.use_wilderness_structure_action(
        *roadside_glyph_positions[roadside_glyph]
    )
    assert opened_roadside_tables == [
        (expected_roadside_games[0], "Smoke Test Roadside Inn")
    ]

    # Tavern blackjack uses a deterministic, UI-independent rules engine.
    assert len(tavern_games.make_blackjack_deck(random.Random(17))) == 52
    assert len(set(tavern_games.make_blackjack_deck(random.Random(17)))) == 52
    assert tavern_games.blackjack_hand_value([("A", "S"), ("9", "H")]) == (20, True)
    assert tavern_games.blackjack_hand_value([("A", "S"), ("A", "H"), ("9", "D"), ("K", "C")]) == (21, False)

    # A table sitting now uses one countable 52-card shoe across rounds.
    expected_shoe_order = tavern_games.make_blackjack_deck(random.Random(117))
    countable_shoe = tavern_games.BlackjackShoe(random.Random(117))
    assert countable_shoe.cards_remaining == 52
    assert countable_shoe.cards_seen == 0
    assert not countable_shoe.prepare_round()
    countable_shoe.start_round()
    first_shoe_round = tavern_games.BlackjackRound(10, shoe=countable_shoe)
    assert first_shoe_round.player_hands[0]["cards"] == [
        expected_shoe_order[0], expected_shoe_order[2],
    ]
    assert first_shoe_round.dealer_cards == [
        expected_shoe_order[1], expected_shoe_order[3],
    ]
    first_shoe_round.stand(0)
    first_shoe_round.settle()
    countable_shoe.finish_round(first_shoe_round)
    cards_after_first_round = countable_shoe.cards_remaining
    next_counted_card = countable_shoe.deck[0]
    assert len(countable_shoe.deck) + len(countable_shoe.discard) == 52
    assert countable_shoe.cards_seen == 52 - cards_after_first_round
    assert not countable_shoe.prepare_round()
    countable_shoe.start_round()
    second_shoe_round = tavern_games.BlackjackRound(10, shoe=countable_shoe)
    assert second_shoe_round.player_hands[0]["cards"][0] == next_counted_card
    second_shoe_round.stand(0)
    second_shoe_round.settle()
    countable_shoe.finish_round(second_shoe_round)
    assert countable_shoe.shuffle_count == 1
    cut_order = tavern_games.make_blackjack_deck(random.Random(118))
    countable_shoe.deck[:] = cut_order[:tavern_games.BLACKJACK_CUT_CARD_REMAINING]
    countable_shoe.discard[:] = cut_order[tavern_games.BLACKJACK_CUT_CARD_REMAINING:]
    assert countable_shoe.needs_shuffle
    assert countable_shoe.prepare_round()
    assert countable_shoe.cards_remaining == 52
    assert countable_shoe.cards_seen == 0
    assert not countable_shoe.discard
    assert countable_shoe.shuffle_count == 2

    natural_round = tavern_games.BlackjackRound(10, deck=[
        ("A", "S"), ("9", "H"), ("K", "D"), ("7", "C"), ("2", "S"),
    ])
    natural_results = natural_round.settle()
    assert natural_results[0]["outcome"] == "blackjack"
    assert natural_results[0]["payout"] == 25
    assert natural_results[0]["profit"] == 15
    assert len(natural_round.dealer_cards) == 2

    dealer_natural_round = tavern_games.BlackjackRound(10, deck=[
        ("10", "S"), ("A", "H"), ("9", "D"), ("K", "C"),
    ])
    dealer_natural_results = dealer_natural_round.settle()
    assert dealer_natural_results[0]["outcome"] == "loss"

    soft_seventeen_round = tavern_games.BlackjackRound(10, deck=[
        ("10", "S"), ("A", "H"), ("7", "D"), ("6", "C"), ("K", "S"),
    ])
    soft_seventeen_round.stand(0)
    soft_seventeen_results = soft_seventeen_round.settle()
    assert soft_seventeen_results[0]["outcome"] == "push"
    assert len(soft_seventeen_round.dealer_cards) == 2

    double_round = tavern_games.BlackjackRound(10, deck=[
        ("5", "S"), ("9", "H"), ("6", "D"), ("7", "C"),
        ("10", "H"), ("2", "D"),
    ])
    assert double_round.can_double(0)
    double_round.double(0)
    double_results = double_round.settle()
    assert double_results[0]["outcome"] == "win"
    assert double_results[0]["wager"] == 20
    assert double_results[0]["profit"] == 20

    split_round = tavern_games.BlackjackRound(10, deck=[
        ("8", "S"), ("9", "H"), ("8", "D"), ("7", "C"),
        ("3", "H"), ("K", "D"), ("4", "S"),
    ])
    assert split_round.can_split(0)
    split_round.split(0)
    assert len(split_round.player_hands) == 2
    assert all(int(hand["wager"]) == 10 for hand in split_round.player_hands)
    split_round.stand(0)
    split_round.stand(1)
    assert len(split_round.settle()) == 2

    blackjack_game = FarmGame()
    blackjack_game.save = lambda *args, **kwargs: True
    blackjack_game.state.money = 100
    played_natural = tavern_games.BlackjackRound(10, deck=[
        ("A", "S"), ("9", "H"), ("K", "D"), ("7", "C"), ("2", "S"),
    ])
    assert blackjack_game.play_blackjack_round(
        10, "Smoke Test Inn", round_state=played_natural, show_result=False,
    )[0]["outcome"] == "blackjack"
    assert blackjack_game.state.money == 115
    assert blackjack_game.state.tavern_blackjack_stats["rounds_played"] == 1
    assert blackjack_game.state.tavern_blackjack_stats["naturals"] == 1
    assert blackjack_game.state.tavern_blackjack_stats["net_winnings"] == 15
    assert any("Blackjack:" in line for line in blackjack_game.journal_overview_lines())
    prepared_blackjack_state = prepare_loaded_state_data({
        "tavern_blackjack_stats": blackjack_game.state.tavern_blackjack_stats,
    })
    reloaded_blackjack_state = GameState(**prepared_blackjack_state)
    assert reloaded_blackjack_state.tavern_blackjack_stats["naturals"] == 1
    assert reloaded_blackjack_state.tavern_blackjack_stats["net_winnings"] == 15

    # Grid board games use explicit white/dark-grey backgrounds instead of
    # relying on invisible terminal spaces.
    assert board_visuals.board_tile_is_light(0, 0)
    assert not board_visuals.board_tile_is_light(1, 0)
    assert board_visuals.board_tile_background(0, 0) == board_visuals.BOARD_LIGHT_BG
    assert board_visuals.board_tile_background(1, 0) == board_visuals.BOARD_DARK_BG
    assert board_visuals.BOARD_LIGHT_BG != board_visuals.BOARD_DARK_BG
    assert ui.visible_text_len(board_visuals.board_tile("[ ]", 0, 0, "cursor")) == 3
    assert ui.visible_text_len(board_visuals.board_tile("(.)", 1, 0, "destination")) == 3
    minigame_controls_output = io.StringIO()
    with contextlib.redirect_stdout(minigame_controls_output):
        minigame_ui.minigame_controls(
            "WASD/arrows/numpad: move",
            "1-7: jump to option",
            "Z/Enter/Space: confirm",
            "R: suggested action",
            "H: rules",
            "B/X/Esc/Q/Tab: pause",
        )
    minigame_control_lines = minigame_controls_output.getvalue().splitlines()
    assert minigame_control_lines
    assert all(ui.visible_text_len(line) <= minigame_ui.MINIGAME_WIDTH for line in minigame_control_lines)
    assert "CONTROLS" in ui.strip_ansi(minigame_control_lines[0])
    assert ui.visible_text_len(minigame_ui.minigame_meter("Progress", 3, 7, width=14)) > 20

    # American checkers enforces captures, chained jumps, kings, and resumable state.
    assert checkers.checkers_piece_glyph("r") == "⛀"
    assert checkers.checkers_piece_glyph("R") == "⛁"
    assert checkers.checkers_piece_glyph("b") == "⛂"
    assert checkers.checkers_piece_glyph("B") == "⛃"
    starting_checkers_board = checkers.new_checkers_board()
    assert sum(piece in {"r", "R"} for row in starting_checkers_board for piece in row) == 12
    assert sum(piece in {"b", "B"} for row in starting_checkers_board for piece in row) == 12
    assert len(checkers.checkers_legal_moves(starting_checkers_board, "player")) == 7

    capture_board = [[checkers.CHECKERS_EMPTY for _x in range(8)] for _y in range(8)]
    capture_board[5][2] = "r"
    capture_board[4][3] = "b"
    capture_board[5][6] = "r"
    mandatory_moves = checkers.checkers_legal_moves(capture_board, "player")
    assert len(mandatory_moves) == 1
    assert mandatory_moves[0]["from"] == (2, 5)
    assert mandatory_moves[0]["to"] == (4, 3)
    assert mandatory_moves[0]["capture"] == (3, 4)

    chain_board = [[checkers.CHECKERS_EMPTY for _x in range(8)] for _y in range(8)]
    chain_board[6][1] = "r"
    chain_board[5][2] = "b"
    chain_board[3][4] = "b"
    first_jump = checkers.checkers_legal_moves(chain_board, "player")[0]
    first_jump_result = checkers.apply_checkers_move(chain_board, first_jump)
    assert first_jump_result["captured"]
    continuation = checkers.checkers_legal_moves(chain_board, "player", only_from=(3, 4))
    assert len(continuation) == 1
    assert continuation[0]["to"] == (5, 2)

    promotion_board = [[checkers.CHECKERS_EMPTY for _x in range(8)] for _y in range(8)]
    promotion_board[1][2] = "r"
    promotion_move = next(
        move for move in checkers.checkers_legal_moves(promotion_board, "player")
        if move["to"] == (1, 0)
    )
    assert checkers.apply_checkers_move(promotion_board, promotion_move)["promoted"]
    assert promotion_board[0][1] == "R"
    assert any(
        move["to"][1] == 1
        for move in checkers.checkers_piece_moves(promotion_board, 1, 0)
    )

    ai_board = [[checkers.CHECKERS_EMPTY for _x in range(8)] for _y in range(8)]
    ai_board[2][3] = "b"
    ai_board[3][4] = "r"
    ai_moves = checkers.checkers_legal_moves(ai_board, "ai")
    assert ai_moves and all(move["capture"] for move in ai_moves)
    chosen_ai_move = checkers.choose_checkers_ai_move(
        ai_board, ai_moves, "Expert", random.Random(44),
    )
    assert chosen_ai_move["capture"] == (4, 3)

    checkers_game = FarmGame()
    checkers_game.save = lambda *args, **kwargs: True
    active_checkers_match = checkers_game.new_checkers_match("Practiced", "Smoke Test Inn")
    assert checkers_game.valid_checkers_match(active_checkers_match)
    opening_move = checkers.checkers_legal_moves(active_checkers_match["board"], "player")[0]
    checkers_game._checkers_complete_turn(active_checkers_match, "player", opening_move)
    assert active_checkers_match["turn"] == "ai"
    checkers_game._checkers_ai_turn(active_checkers_match)
    assert active_checkers_match["turn"] == "player"
    assert active_checkers_match["move_count"] >= 2
    checkers_game.pause_checkers_match()
    assert checkers_game.state.tavern_checkers_match
    prepared_checkers_state = prepare_loaded_state_data({
        "tavern_checkers_stats": checkers_game.state.tavern_checkers_stats,
        "tavern_checkers_match": checkers_game.state.tavern_checkers_match,
    })
    reloaded_checkers_state = GameState(**prepared_checkers_state)
    assert reloaded_checkers_state.tavern_checkers_match["difficulty"] == "Practiced"
    reloaded_checkers_game = FarmGame()
    reloaded_checkers_game.state = reloaded_checkers_state
    reloaded_checkers_game.ensure_checkers_state()
    assert reloaded_checkers_game.valid_checkers_match(
        reloaded_checkers_game.state.tavern_checkers_match,
    )
    reloaded_checkers_game.save = lambda *args, **kwargs: True
    reloaded_checkers_game.finish_checkers_match("loss", resigned=True)
    assert reloaded_checkers_game.state.tavern_checkers_stats["games_played"] == 1
    assert reloaded_checkers_game.state.tavern_checkers_stats["losses"] == 1
    assert not reloaded_checkers_game.state.tavern_checkers_match
    assert any("CHECKERS RECORD" in line for line in reloaded_checkers_game.tavern_game_record_lines())

    # Chess covers legal movement, special moves, endings, AI, and resumable state.
    assert chess.chess_piece_glyph("K") == "♔"
    assert chess.chess_piece_glyph("Q") == "♕"
    assert chess.chess_piece_glyph("p") == "♟"
    assert chess.chess_piece_name("n") == "Black knight"
    starting_chess_board = chess.new_chess_board()
    assert sum(piece.isupper() for row in starting_chess_board for piece in row if piece != ".") == 16
    assert sum(piece.islower() for row in starting_chess_board for piece in row if piece != ".") == 16
    chess_game = FarmGame()
    chess_game.save = lambda *args, **kwargs: True
    active_chess_match = chess_game.new_chess_match("Practiced", "Smoke Test Inn")
    assert chess_game.valid_chess_match(active_chess_match)
    assert len(chess.chess_legal_moves(active_chess_match, "player")) == 20
    e4_move = next(
        move for move in chess.chess_legal_moves(active_chess_match, "player")
        if move["from"] == (4, 6) and move["to"] == (4, 4)
    )
    chess.apply_chess_move(active_chess_match, e4_move)
    assert active_chess_match["board"][4][4] == "P"
    assert active_chess_match["en_passant"] == [4, 5]
    assert active_chess_match["turn"] == "ai"
    chosen_chess_move = chess.choose_chess_ai_move(
        active_chess_match, "Expert", random.Random(45),
    )
    assert chosen_chess_move in chess.chess_legal_moves(active_chess_match, "ai")

    en_passant_board = [[chess.CHESS_EMPTY for _x in range(8)] for _y in range(8)]
    en_passant_board[7][4] = "K"
    en_passant_board[0][4] = "k"
    en_passant_board[3][4] = "P"
    en_passant_board[1][3] = "p"
    en_passant_match = chess_game.new_chess_match("Friendly", "Rules Table")
    en_passant_match.update({
        "board": en_passant_board, "turn": "ai", "castling": "",
        "en_passant": None, "halfmove_clock": 0, "position_counts": {},
    })
    d5_move = next(
        move for move in chess.chess_legal_moves(en_passant_match, "ai")
        if move["from"] == (3, 1) and move["to"] == (3, 3)
    )
    chess.apply_chess_move(en_passant_match, d5_move)
    en_passant_move = next(
        move for move in chess.chess_legal_moves(en_passant_match, "player")
        if move["from"] == (4, 3) and move["to"] == (3, 2)
    )
    assert en_passant_move.get("en_passant")
    chess.apply_chess_move(en_passant_match, en_passant_move)
    assert en_passant_match["board"][2][3] == "P"
    assert en_passant_match["board"][3][3] == chess.CHESS_EMPTY

    castle_board = [[chess.CHESS_EMPTY for _x in range(8)] for _y in range(8)]
    castle_board[7][4], castle_board[7][7], castle_board[0][4] = "K", "R", "k"
    castle_match = chess_game.new_chess_match("Friendly", "Rules Table")
    castle_match.update({
        "board": castle_board, "turn": "player", "castling": "K",
        "en_passant": None, "halfmove_clock": 0, "position_counts": {},
    })
    castle_move = next(
        move for move in chess.chess_legal_moves(castle_match, "player", (4, 7))
        if move.get("castle") == "king"
    )
    castled = chess.clone_chess_match(castle_match)
    chess.apply_chess_move(castled, castle_move)
    assert castled["board"][7][6] == "K" and castled["board"][7][5] == "R"
    castle_match["board"][0][5] = "r"
    assert not any(
        move.get("castle")
        for move in chess.chess_legal_moves(castle_match, "player", (4, 7))
    )

    pin_board = [[chess.CHESS_EMPTY for _x in range(8)] for _y in range(8)]
    pin_board[7][4], pin_board[6][4], pin_board[0][4], pin_board[0][0] = "K", "R", "r", "k"
    pin_match = chess_game.new_chess_match("Friendly", "Rules Table")
    pin_match.update({
        "board": pin_board, "turn": "player", "castling": "",
        "en_passant": None, "halfmove_clock": 0, "position_counts": {},
    })
    assert not any(
        move["to"][0] != 4
        for move in chess.chess_legal_moves(pin_match, "player", (4, 6))
    )

    promotion_board = [[chess.CHESS_EMPTY for _x in range(8)] for _y in range(8)]
    promotion_board[7][4], promotion_board[0][7], promotion_board[1][0] = "K", "k", "P"
    promotion_match = chess_game.new_chess_match("Friendly", "Rules Table")
    promotion_match.update({
        "board": promotion_board, "turn": "player", "castling": "",
        "en_passant": None, "halfmove_clock": 0, "position_counts": {},
    })
    promotion_moves = [
        move for move in chess.chess_legal_moves(promotion_match, "player", (0, 1))
        if move["to"] == (0, 0)
    ]
    assert {move.get("promotion") for move in promotion_moves} == {"Q", "R", "B", "N"}
    queen_promotion = next(move for move in promotion_moves if move.get("promotion") == "Q")
    chess.apply_chess_move(promotion_match, queen_promotion)
    assert promotion_match["board"][0][0] == "Q"

    mate_match = chess_game.new_chess_match("Friendly", "Rules Table")
    for source, target in (
        ((5, 6), (5, 5)), ((4, 1), (4, 3)),
        ((6, 6), (6, 4)), ((3, 0), (7, 4)),
    ):
        side = str(mate_match["turn"])
        move = next(
            candidate for candidate in chess.chess_legal_moves(mate_match, side)
            if candidate["from"] == source and candidate["to"] == target
        )
        chess.apply_chess_move(mate_match, move)
    assert chess.chess_match_outcome(mate_match) == "loss_checkmate"

    stalemate_board = [[chess.CHESS_EMPTY for _x in range(8)] for _y in range(8)]
    stalemate_board[0][0], stalemate_board[2][2], stalemate_board[2][1] = "k", "K", "Q"
    stalemate_match = chess_game.new_chess_match("Friendly", "Rules Table")
    stalemate_match.update({
        "board": stalemate_board, "turn": "ai", "castling": "",
        "en_passant": None, "halfmove_clock": 0, "position_counts": {},
    })
    assert chess.chess_match_outcome(stalemate_match) == "draw_stalemate"
    material_match = chess.clone_chess_match(stalemate_match)
    material_match["board"][2][1] = chess.CHESS_EMPTY
    material_match["turn"] = "player"
    assert chess.chess_match_outcome(material_match) == "draw_material"
    repetition_match = chess_game.new_chess_match("Friendly", "Rules Table")
    repetition_match["position_counts"][chess.chess_position_key(repetition_match)] = 3
    assert chess.chess_match_outcome(repetition_match) == "draw_repetition"

    persistent_chess_match = chess_game.new_chess_match("Practiced", "Smoke Test Inn")
    chess_game._apply_live_chess_move(
        persistent_chess_match,
        next(
            move for move in chess.chess_legal_moves(persistent_chess_match, "player")
            if move["from"] == (4, 6) and move["to"] == (4, 4)
        ),
    )
    chess_game._chess_ai_turn(persistent_chess_match)
    assert persistent_chess_match["turn"] == "player"
    assert len(persistent_chess_match["move_history"]) == 2
    chess_game.pause_chess_match()
    prepared_chess_state = prepare_loaded_state_data({
        "tavern_chess_stats": chess_game.state.tavern_chess_stats,
        "tavern_chess_match": chess_game.state.tavern_chess_match,
    })
    reloaded_chess_state = GameState(**prepared_chess_state)
    reloaded_chess_game = FarmGame()
    reloaded_chess_game.state = reloaded_chess_state
    reloaded_chess_game.ensure_chess_state()
    assert reloaded_chess_game.valid_chess_match(
        reloaded_chess_game.state.tavern_chess_match,
    )
    reloaded_chess_game.save = lambda *args, **kwargs: True
    reloaded_chess_game.finish_chess_match("loss", resigned=True)
    assert reloaded_chess_game.state.tavern_chess_stats["games_played"] == 1
    assert reloaded_chess_game.state.tavern_chess_stats["losses"] == 1
    assert not reloaded_chess_game.state.tavern_chess_match
    assert any("CHESS RECORD" in line for line in reloaded_chess_game.tavern_game_record_lines())

    # Kalah-style mancala covers sowing, stores, captures, extra turns, AI, and wagers.
    starting_mancala_board = mancala.new_mancala_board()
    assert len(starting_mancala_board) == 14
    assert sum(starting_mancala_board) == 48
    assert mancala.mancala_legal_pits(starting_mancala_board, "player") == list(range(6))
    assert mancala.mancala_legal_pits(starting_mancala_board, "ai") == list(range(7, 13))
    assert mancala.mancala_sow_path(starting_mancala_board, "player", 2) == [3, 4, 5, 6]
    extra_turn_board = list(starting_mancala_board)
    extra_turn_result = mancala.apply_mancala_move(extra_turn_board, "player", 2)
    assert extra_turn_result["extra_turn"]
    assert extra_turn_board[6] == 1
    assert sum(extra_turn_board) == 48

    skip_store_board = [0] * 14
    skip_store_board[5] = 8
    skip_store_board[7] = 1
    skip_path = mancala.mancala_sow_path(skip_store_board, "player", 5)
    assert skip_path == [6, 7, 8, 9, 10, 11, 12, 0]
    assert 13 not in skip_path

    capture_mancala_board = [0] * 14
    capture_mancala_board[0] = 1
    capture_mancala_board[11] = 5
    capture_result = mancala.apply_mancala_move(capture_mancala_board, "player", 0)
    assert capture_result["captured"] == 6
    assert capture_mancala_board[6] == 6
    assert capture_mancala_board[1] == capture_mancala_board[11] == 0

    sweep_board = [0] * 14
    sweep_board[5] = 1
    sweep_board[7] = 2
    sweep_result = mancala.apply_mancala_move(sweep_board, "player", 5)
    assert sweep_result["game_over"]
    assert sweep_board[6] == 1 and sweep_board[13] == 2
    assert mancala.mancala_board_outcome(sweep_board) == "loss"

    for difficulty in ("Friendly", "Practiced", "Expert"):
        ai_pit = mancala.choose_mancala_ai_pit(
            starting_mancala_board, difficulty, random.Random(46),
        )
        assert ai_pit in mancala.mancala_legal_pits(starting_mancala_board, "ai")
    assert mancala.mancala_profit_for_win(100, "Friendly") == 100
    assert mancala.mancala_profit_for_win(100, "Practiced") == 150
    assert mancala.mancala_profit_for_win(100, "Expert") == 200

    mancala_game = FarmGame()
    mancala_game.save = lambda *args, **kwargs: True
    mancala_game.state.money = 1000
    active_mancala_match = mancala_game.new_mancala_match(
        "Practiced", "Smoke Test Inn", 100,
    )
    assert mancala_game.valid_mancala_match(active_mancala_match)
    assert mancala_game.state.money == 900
    mancala_game._mancala_complete_move(active_mancala_match, "player", 2)
    assert active_mancala_match["turn"] == "player"
    assert active_mancala_match["player_extra_turns"] == 1
    active_mancala_match["board"] = [0] * 14
    active_mancala_match["board"][6] = 30
    active_mancala_match["board"][13] = 18
    mancala_game.finish_mancala_match("win")
    assert mancala_game.state.money == 1150
    assert mancala_game.state.tavern_mancala_stats["games_played"] == 1
    assert mancala_game.state.tavern_mancala_stats["wins"] == 1
    assert mancala_game.state.tavern_mancala_stats["net_winnings"] == 150

    persisted_mancala_match = mancala_game.new_mancala_match(
        "Expert", "Smoke Test Inn", 50,
    )
    assert mancala_game.state.money == 1100
    mancala_game._mancala_complete_move(persisted_mancala_match, "player", 0)
    mancala_game.pause_mancala_match()
    prepared_mancala_state = prepare_loaded_state_data({
        "money": mancala_game.state.money,
        "tavern_mancala_stats": mancala_game.state.tavern_mancala_stats,
        "tavern_mancala_match": mancala_game.state.tavern_mancala_match,
    })
    reloaded_mancala_state = GameState(**prepared_mancala_state)
    reloaded_mancala_game = FarmGame()
    reloaded_mancala_game.state = reloaded_mancala_state
    reloaded_mancala_game.ensure_mancala_state()
    assert reloaded_mancala_game.valid_mancala_match(
        reloaded_mancala_game.state.tavern_mancala_match,
    )
    assert reloaded_mancala_game.state.tavern_mancala_match["wager"] == 50
    reloaded_mancala_game.save = lambda *args, **kwargs: True
    reloaded_mancala_game.finish_mancala_match("loss", resigned=True)
    assert reloaded_mancala_game.state.money == 1100
    assert reloaded_mancala_game.state.tavern_mancala_stats["games_played"] == 2
    assert reloaded_mancala_game.state.tavern_mancala_stats["losses"] == 1
    assert reloaded_mancala_game.state.tavern_mancala_stats["net_winnings"] == 100
    assert not reloaded_mancala_game.state.tavern_mancala_match
    assert any("MANCALA RECORD" in line for line in reloaded_mancala_game.tavern_game_record_lines())

    # Hold'em evaluates all standard hands and returns uncommitted table stakes.
    assert holdem.poker_five_card_rank([
        ("A", "S"), ("K", "S"), ("Q", "S"), ("J", "S"), ("10", "S"),
    ]) == (8, 14)
    assert holdem.poker_five_card_rank([
        ("A", "S"), ("2", "D"), ("3", "C"), ("4", "H"), ("5", "S"),
    ]) == (4, 5)
    full_house = holdem.poker_best_rank([
        ("K", "S"), ("K", "D"), ("K", "C"), ("4", "H"), ("4", "S"), ("2", "C"), ("A", "D"),
    ])
    assert full_house[:3] == (6, 13, 4)
    holdem_game = FarmGame()
    holdem_game.save = lambda *args, **kwargs: True
    holdem_game.state.money = 1000
    holdem_game._holdem_player_bet = lambda table, _difficulty: table.player_call()
    holdem_result = holdem_game.play_holdem_hand(100, "Practiced", "Smoke Test Inn", show_result=False)
    assert holdem_result is not None
    assert holdem_game.state.tavern_holdem_stats["hands_played"] == 1
    assert holdem_game.state.money == 1000 + int(holdem_result["profit"])
    assert int(holdem_result["payout"]) >= 0

    # Hearts enforces passing, opening lead, suit following, points, and moon scoring.
    hearts_match = {"scores": [0, 0, 0, 0], "round_index": 0}
    hearts.deal_hearts_round(hearts_match, random.Random(47))
    assert all(len(hand) == 13 for hand in hearts_match["hands"])
    player_pass = list(hearts_match["hands"][0][:3])
    hearts.apply_hearts_passes(hearts_match, player_pass)
    assert hearts_match["phase"] == "play"
    assert all(len(hand) == 13 for hand in hearts_match["hands"])
    holder = next(seat for seat, hand in enumerate(hearts_match["hands"]) if "2C" in hand)
    assert hearts_match["turn"] == holder
    opening_result = hearts.play_hearts_card(hearts_match, holder, "2C")
    assert not opening_result["trick_complete"]
    assert hearts.hearts_trick_points([
        {"seat": 0, "card": "2H"}, {"seat": 1, "card": "QS"},
    ]) == 14
    assert hearts.hearts_round_scores([26, 0, 0, 0]) == [0, 26, 26, 26]
    simulated_hearts_round = {"scores": [0, 0, 0, 0], "round_index": 0}
    hearts.deal_hearts_round(simulated_hearts_round, random.Random(71))
    hearts.apply_hearts_passes(
        simulated_hearts_round,
        hearts.choose_hearts_pass(simulated_hearts_round["hands"][0]),
    )
    hearts_ai_rng = random.Random(72)
    final_hearts_play = {}
    for _play_index in range(52):
        acting_seat = int(simulated_hearts_round["turn"])
        chosen_card = hearts.choose_hearts_ai_card(
            simulated_hearts_round["hands"][acting_seat],
            simulated_hearts_round["trick"],
            bool(simulated_hearts_round["hearts_broken"]),
            int(simulated_hearts_round["trick_number"]) == 0,
            hearts_ai_rng,
        )
        final_hearts_play = hearts.play_hearts_card(
            simulated_hearts_round, acting_seat, chosen_card,
        )
    assert final_hearts_play["round_complete"]
    assert sum(simulated_hearts_round["round_points"]) == 26
    assert not any(simulated_hearts_round["hands"])
    hearts_game = FarmGame()
    hearts_game.save = lambda *args, **kwargs: True
    saved_hearts_match = hearts_game.new_hearts_match("Smoke Test Inn")
    assert hearts_game.valid_hearts_match(saved_hearts_match)
    hearts_game.pause_hearts_match()
    prepared_hearts_state = prepare_loaded_state_data({
        "tavern_hearts_stats": hearts_game.state.tavern_hearts_stats,
        "tavern_hearts_match": hearts_game.state.tavern_hearts_match,
    })
    reloaded_hearts_game = FarmGame()
    reloaded_hearts_game.state = GameState(**prepared_hearts_state)
    reloaded_hearts_game.ensure_hearts_state()
    assert reloaded_hearts_game.valid_hearts_match(reloaded_hearts_game.state.tavern_hearts_match)

    # Draw-one Klondike preserves all cards and supports stock, tableau, and foundations.
    solitaire_match = solitaire.new_solitaire_match(random.Random(48), "Smoke Test Inn")
    assert sum(len(pile) for pile in solitaire_match["tableau"]) == 28
    assert len(solitaire_match["stock"]) == 24
    assert solitaire.SolitaireMixin.valid_solitaire_match(solitaire_match)
    assert solitaire.solitaire_can_tableau("QH", "KS")
    assert not solitaire.solitaire_can_tableau("QS", "KS")
    assert solitaire.solitaire_can_foundation("AS", [])
    move_fixture = {
        "stock": [], "waste": ["AS"], "foundations": {suit: [] for suit in solitaire.SOLITAIRE_SUITS},
        "tableau": [[] for _ in range(7)], "moves": 0, "foundation_moves": 0,
    }
    assert solitaire.solitaire_move_waste_to_foundation(move_fixture, "S")
    assert move_fixture["foundations"]["S"] == ["AS"]
    solitaire_game = FarmGame()
    solitaire_game.save = lambda *args, **kwargs: True
    saved_solitaire = solitaire_game.new_solitaire_game("Smoke Test Inn")
    assert solitaire_game.valid_solitaire_match(saved_solitaire)
    solitaire.solitaire_draw_stock(saved_solitaire)
    solitaire_game.pause_solitaire_game()
    prepared_solitaire_state = prepare_loaded_state_data({
        "tavern_solitaire_stats": solitaire_game.state.tavern_solitaire_stats,
        "tavern_solitaire_match": solitaire_game.state.tavern_solitaire_match,
    })
    reloaded_solitaire_game = FarmGame()
    reloaded_solitaire_game.state = GameState(**prepared_solitaire_state)
    reloaded_solitaire_game.ensure_solitaire_state()
    assert reloaded_solitaire_game.valid_solitaire_match(
        reloaded_solitaire_game.state.tavern_solitaire_match,
    )

    # The Royal Game of Ur handles exact entry/exit, captures, safe rosettes, AI, and wagers.
    ur_match = {
        "positions": {"player": [royal_ur.UR_HOME] * 7, "ai": [royal_ur.UR_HOME] * 7},
    }
    assert royal_ur.ur_legal_pieces(ur_match, "player", 4) == list(range(7))
    rosette_move = royal_ur.apply_ur_move(ur_match, "player", 0, 4)
    assert rosette_move["extra_turn"] and ur_match["positions"]["player"][0] == 3
    ur_match["positions"]["player"][0] = 3
    ur_match["positions"]["ai"][0] = 4
    capture_move = royal_ur.apply_ur_move(ur_match, "player", 0, 1)
    assert capture_move["captured_piece"] == 0
    assert ur_match["positions"]["ai"][0] == royal_ur.UR_HOME
    safe_match = {
        "positions": {
            "player": [3] + [royal_ur.UR_HOME] * 6,
            "ai": [7] + [royal_ur.UR_HOME] * 6,
        },
    }
    assert 0 not in royal_ur.ur_legal_pieces(safe_match, "player", 4)
    assert royal_ur.ur_board_coordinate("player", 0) == (3, 2)
    assert royal_ur.ur_board_coordinate("ai", 0) == (3, 0)
    assert royal_ur.ur_board_coordinate("player", 4) == (0, 1)
    assert royal_ur.ur_board_coordinate("player", 13) == (6, 2)
    ur_capture_display = {
        "positions": {
            "player": [4] + [royal_ur.UR_HOME] * 6,
            "ai": [6] + [royal_ur.UR_HOME] * 6,
        },
        "roll": 2,
    }
    ur_board_lines = [
        ui.strip_ansi(line)
        for line in royal_ur.render_ur_board_lines(ur_capture_display, [0], 0)
    ]
    assert len(ur_board_lines) == 7
    assert all(ui.visible_text_len(line) == 33 for line in ur_board_lines)
    assert ur_board_lines[0] == "┌───┬───┬───┬───┐       ┌───┬───┐"
    assert ur_board_lines[-1] == "└───┴───┴───┴───┘       └───┴───┘"
    assert "@" in "".join(ur_board_lines)
    assert "×" in "".join(ur_board_lines)
    assert "".join(ur_board_lines).count("✦") == 5
    assert royal_ur.choose_ur_ai_piece(
        {"positions": {"player": [royal_ur.UR_HOME] * 7, "ai": [royal_ur.UR_HOME] * 7}},
        "Expert", 4, random.Random(49),
    ) in range(7)
    simulated_ur = {
        "positions": {
            "player": [royal_ur.UR_HOME] * 7,
            "ai": [royal_ur.UR_HOME] * 7,
        },
    }
    ur_rng = random.Random(50)
    ur_turn = "player"
    ur_winner = ""
    for _ur_turn_index in range(2000):
        ur_roll = royal_ur.ur_roll_total(royal_ur.roll_ur_dice(ur_rng))
        legal_ur_pieces = royal_ur.ur_legal_pieces(simulated_ur, ur_turn, ur_roll)
        if not legal_ur_pieces:
            ur_turn = royal_ur.ur_opponent(ur_turn)
            continue
        if ur_turn == "ai":
            ur_piece = royal_ur.choose_ur_ai_piece(
                simulated_ur, "Expert", ur_roll, ur_rng,
            )
        else:
            ur_piece = max(
                legal_ur_pieces,
                key=lambda piece: royal_ur.ur_move_score(
                    simulated_ur, "player", piece, ur_roll,
                ),
            )
        simulated_ur_result = royal_ur.apply_ur_move(
            simulated_ur, ur_turn, ur_piece, ur_roll,
        )
        if simulated_ur_result["won"]:
            ur_winner = ur_turn
            break
        if not simulated_ur_result["extra_turn"]:
            ur_turn = royal_ur.ur_opponent(ur_turn)
    assert ur_winner in {"player", "ai"}
    ur_game = FarmGame()
    ur_game.save = lambda *args, **kwargs: True
    ur_game.state.money = 1000
    winning_ur_match = ur_game.new_ur_match("Expert", "Smoke Test Inn", 100)
    winning_ur_match["positions"]["player"] = [royal_ur.UR_FINISHED] * 6 + [13]
    winning_ur_match["roll"] = 1
    winning_ur_match["dice"] = [1, 0, 0, 0]
    win_move = ur_game._complete_ur_move(winning_ur_match, "player", 6)
    assert win_move["won"]
    ur_game.finish_ur_match("win")
    assert ur_game.state.money == 1200
    assert ur_game.state.tavern_ur_stats["wins"] == 1
    assert ur_game.state.tavern_ur_stats["net_winnings"] == 200
    assert any("TEXAS HOLD'EM RECORD" in line for line in ur_game.tavern_game_record_lines())
    assert any("HEARTS RECORD" in line for line in ur_game.tavern_game_record_lines())
    assert any("SOLITAIRE RECORD" in line for line in ur_game.tavern_game_record_lines())
    assert any("ROYAL GAME OF UR RECORD" in line for line in ur_game.tavern_game_record_lines())

    original_game_save = game.save
    game.save = lambda *args, **kwargs: True
    museum_catalog = game.museum_donation_catalog()
    assert "agriculture:Turnip" in museum_catalog
    assert "fishing:Pond Minnow" in museum_catalog
    assert "geology:Crystal Shard" in museum_catalog
    assert "archaeology:Painted Pottery Sherd" in museum_catalog
    assert "paleontology:Trackway Slab" in museum_catalog
    assert "engineering:Sprinkler" in museum_catalog
    assert "bestiary:Wisp:Crystal Shard" in museum_catalog
    assert game.museum_total_possible() >= len(data.CROP_DATA) + len(data.FISH_DATA)
    game.state.inventory["Turnip"] = 1
    assert any(record.get("id") == "agriculture:Turnip" for record in game.museum_donation_candidates())
    starting_money = game.state.money
    assert game.donate_museum_record("agriculture:Turnip")
    assert "agriculture:Turnip" in game.state.museum_donated_record_ids
    assert inventory.inventory_ingredient_quantity(game.state.inventory, "Turnip") == 0
    assert game.state.museum_donation_counts.get("agriculture") == 1
    assert game.state.money >= starting_money + 100
    assert not game.donate_museum_record("agriculture:Turnip")
    assert any("Museum donations:" in line for line in game.journal_overview_lines())
    assert any("Turnip" in line for line in game.museum_exhibit_lines("agriculture"))
    game.state.inventory["Crystal Shard"] = game.state.inventory.get("Crystal Shard", 0) + 1
    assert game.donate_museum_record("bestiary:Wisp:Crystal Shard")
    wisp_bestiary = game.combat_bestiary_lines("Wisp")
    assert any("Museum specimen: Crystal Shard (donated)" in line for line in wisp_bestiary)
    assert any("Weaknesses and Prep:" in line for line in wisp_bestiary)
    assert any("Likely Floors:" in line for line in wisp_bestiary)

    # Archaeology and paleontology share a persistent, deterministic field
    # framework while retaining different layer depth and tool risks.
    archaeology_site = game.excavation_site("archaeology", 10, 8, "smoke_ruin")
    matching_archaeology_site = game._new_excavation_site(
        archaeology_site["id"], "archaeology", archaeology_site["week"],
    )
    assert archaeology_site["cells"] == matching_archaeology_site["cells"]
    archaeology_find_index = next(
        index for index, cell in enumerate(archaeology_site["cells"]) if cell.get("find_id")
    )
    archaeology_x = archaeology_find_index % game.EXCAVATION_WIDTH
    archaeology_y = archaeology_find_index // game.EXCAVATION_WIDTH
    archaeology_cell = archaeology_site["cells"][archaeology_find_index]
    archaeology_item = archaeology_cell["find_id"]
    assert game.excavation_apply_action(
        archaeology_site, archaeology_x, archaeology_y, "survey",
    )["success"]
    while archaeology_cell["layers"] > 0:
        assert game.excavation_apply_action(
            archaeology_site, archaeology_x, archaeology_y, "brush",
        )["success"]
    assert game.excavation_apply_action(
        archaeology_site, archaeology_x, archaeology_y, "stabilize",
    )["success"]
    recovered = game.excavation_apply_action(
        archaeology_site, archaeology_x, archaeology_y, "recover",
    )
    assert recovered["success"]
    assert game.state.inventory.get(archaeology_item, 0) == 1
    assert game.state.archaeology_finds == 1
    assert game.state.excavation_exp > 0
    assert game.state.excavation_discoveries[-1]["condition"] == 100
    assert game.state.excavation_discoveries[-1]["context_score"] >= 1
    assert excavation.EXCAVATION_FIND_DATA[archaeology_item]["value"] > 0
    archaeology_record_id = game.museum_record_id("archaeology", archaeology_item)
    assert any(
        record.get("id") == archaeology_record_id
        for record in game.museum_donation_candidates()
    )
    assert game.donate_museum_record(archaeology_record_id)
    assert game.state.museum_donation_counts.get("archaeology") == 1

    paleontology_site = game.excavation_site("paleontology", 12, 9, "smoke_fossil")
    paleontology_find_index = next(
        index for index, cell in enumerate(paleontology_site["cells"]) if cell.get("find_id")
    )
    paleontology_x = paleontology_find_index % game.EXCAVATION_WIDTH
    paleontology_y = paleontology_find_index // game.EXCAVATION_WIDTH
    paleontology_cell = paleontology_site["cells"][paleontology_find_index]
    paleontology_cell["layers"] = 2
    paleontology_cell["hardness"] = 2
    condition_before_pick = paleontology_cell["condition"]
    assert game.excavation_apply_action(
        paleontology_site, paleontology_x, paleontology_y, "pick",
    )["success"]
    assert paleontology_cell["layers"] == 0
    assert paleontology_cell["condition"] < condition_before_pick
    assert game.excavation_apply_action(
        paleontology_site, paleontology_x, paleontology_y, "recover",
    )["success"]
    assert game.state.paleontology_finds == 1
    assert any("Field research:" in line for line in game.journal_overview_lines())
    assert any("Recent finds:" in line for line in game.excavation_journal_lines())
    prepared_excavation_state = prepare_loaded_state_data({
        "excavation_sites": game.state.excavation_sites,
        "excavation_discoveries": game.state.excavation_discoveries,
        "excavation_exp": game.state.excavation_exp,
        "archaeology_finds": game.state.archaeology_finds,
        "paleontology_finds": game.state.paleontology_finds,
    })
    reloaded_excavation_state = GameState(**prepared_excavation_state)
    assert reloaded_excavation_state.excavation_sites
    assert len(reloaded_excavation_state.excavation_discoveries) == 2
    assert reloaded_excavation_state.archaeology_finds == 1
    assert reloaded_excavation_state.paleontology_finds == 1

    game.state.location = "MuseumInterior"
    assert game.location_label() == "Museum"
    assert sum(row.count("D") for row in game.active_map()) == 1
    museum_service_tiles = [
        (x, y)
        for y, row in enumerate(game.active_map())
        for x, ch in enumerate(row)
        if ch == "&"
    ]
    assert len(museum_service_tiles) == 1
    museum_x, museum_y = museum_service_tiles[0]
    assert any("d" in row for row in game.active_map())
    assert game.is_interactable_tile(museum_x, museum_y)
    assert "donate" in game.interaction_hint(museum_x, museum_y)
    game.save = original_game_save

    restoration_game = FarmGame()
    restoration_game.save = lambda *args, **kwargs: True
    restoration_game.unlock_town_building("library")
    restoration_game.state.money = 999999
    restoration_game.state.inventory["Wood"] = 80
    restoration_game.state.inventory["Stone"] = 80
    restoration_game.state.inventory["Copper Bar"] = 4
    restoration_game.state.inventory["Quartz"] = 2
    assert state.can_complete_town_restoration_project(restoration_game.state, "restore_museum")
    assert restoration_game.complete_town_restoration_project("restore_museum")
    assert restoration_game.is_town_building_unlocked("museum")
    assert restoration_game.town_map[data.TOWN_DOORS["museum"][1]][data.TOWN_DOORS["museum"][0]] == "D"
    assert restoration_game.transition_to_museum() is None
    assert restoration_game.state.location == "MuseumInterior"
    restoration_game.move(0, 1)
    assert restoration_game.state.location == "Wilderness"
    assert restoration_game.home_world_source_at(
        restoration_game.state.player_x, restoration_game.state.player_y,
    ) == ("town", data.TOWN_DOORS["museum"][0], data.TOWN_DOORS["museum"][1] + 1)

    progress_game = FarmGame()
    progress_game.state.owned_wilderness_claims = {"0,0": {"name": "Test Claim"}}
    progress_game.state.automation_machines = {"Farm:1,1": {"item": "Sprinkler"}}
    progress_game.state.mine_combat_victories = 1
    progress_game.state.deepest_mine_floor = 5
    progress_requests = progress_game.resident_request_data()
    for request_id in [
        "progress_first_claim_waymarkers",
        "progress_first_automation_check",
        "progress_first_mine_after_action",
        "progress_deep_route_markers",
    ]:
        assert request_id in progress_requests
        request = progress_requests[request_id]
        assert request.get("npc_id") in town_npc_ids
        assert_known_inventory_items((request.get("requirements", {}) or {}).get("items", {}), f"dynamic request {request_id} requirement")
        assert_known_inventory_items((request.get("rewards", {}) or {}).get("items", {}), f"dynamic request {request_id} reward")
    assert progress_game.scene_conditions_met(progress_game.scene_by_id("life:first_land_claim"), {"npc_id": "eli_carpenter"})
    progress_mail_ids = {str(letter.get("id")) for letter in progress_game.generated_mail()}
    assert "progress_first_claim_deed" in progress_mail_ids
    assert "progress_first_automation" in progress_mail_ids
    assert "progress_first_mine_win" in progress_mail_ids
    assert "progress_deep_floor_warning" in progress_mail_ids
    assert "tutorial_bookshelf_note" in progress_mail_ids

    festival_game = FarmGame()
    festival_game.autosave_with_message = lambda message: festival_game.set_message(message)
    festival_special_events = []
    festival_game.play_world_event_scene = (
        lambda event_id, title, steps, completion_message="":
        festival_special_events.append((str(event_id), str(title), list(steps))) or True
    )
    festival_game.state.month, festival_game.state.day, festival_game.state.year = 3, 7, 1
    festival = festival_game.todays_festival()
    assert festival and festival["id"] == "spring_seed_fair"
    activities = festival_game.festival_activity_options(festival)
    assert len(activities) >= 3
    assert festival_game.complete_festival_activity(festival, activities[0])
    assert festival_game.festival_activity_completed("spring_seed_fair", str(activities[0]["id"]))
    assert festival_game.state.inventory.get("Mixed Seeds", 0) >= 2
    assert festival_special_events and festival_special_events[-1][0].startswith("festival_activity:")
    assert festival_game.attend_todays_festival()
    assert any(event_id.startswith("festival:") for event_id, _title, _steps in festival_special_events)

    market_game = FarmGame()
    market_game.vertical_panel_view = lambda *args, **kwargs: None
    market_game.autosave_with_message = lambda message: market_game.set_message(message)
    market_game.state.month, market_game.state.day, market_game.state.year = 3, 3, 1
    assert market_game.today_market_day_label()
    assert market_game.market_day_discount_percent() == 10
    market_stock_names = {str(entry.get("item")) for entry in market_game.today_market_stock()}
    assert {"Mixed Seeds", "Field Snack", "Basic Fertilizer"}.issubset(market_stock_names)
    assert market_game.claim_market_day_sample()
    assert market_game.market_day_sample_claimed()
    prep_market_game = FarmGame()
    prep_market_game.state.month, prep_market_game.state.day, prep_market_game.state.year = 3, 1, 1
    assert prep_market_game.seasonal_combat_contract_label_for_date(3, 1, 1)
    prep_stock_names = {str(entry.get("item")) for entry in prep_market_game.today_market_stock()}
    assert {"Field Snack", "Honey", "Cave Herbs"}.issubset(prep_stock_names)
    assert any("JOURNAL / CODEX" in line for line in game.journal_overview_lines())
    assert any("Today's priorities:" in line for line in game.journal_overview_lines())
    assert any("PROGRESSION GOALS" in line for line in game.journal_progression_lines())
    progression_tracks = {str(goal.get("track")) for goal in game.active_progression_goals()}
    assert {"Town", "Land", "Tools & Automation", "Combat", "Home & Family"}.issubset(progression_tracks)
    assert game.progression_priority_goals()
    assert game.progression_morning_priority_summary()
    morning_goal_game = FarmGame()
    morning_goal_game.save = lambda *args, **kwargs: True
    morning_goal_game.sleep(force=True)
    assert "Priority:" in morning_goal_game.state.message
    assert any("QUEST JOURNAL" in line for line in game.journal_quest_lines())
    assert any("LAND CLAIMS" in line for line in game.journal_land_claim_lines())
    assert any("RELATIONSHIPS" in line for line in game.journal_relationship_lines())
    assert any("BIRTHDAYS" in line for line in game.journal_birthday_lines())
    assert any("BESTIARY" in line for line in game.journal_bestiary_lines())
    assert any("COMBAT REPORTS" in line for line in game.journal_combat_report_lines())
    assert any("CRAFTING GOALS" in line for line in game.journal_crafting_goal_lines())
    game.state.message = (
        "First HUD row that is intentionally long enough to wrap under renderer control instead of terminal auto wrapping.\n"
        "Second HUD row that should also wrap cleanly when the message takes more than two rows.\n"
        "Third HUD row."
    )
    hud_width = game.hud_line_width()
    plain_header = [ANSI_CSI_RE.sub("", line) for line in game.header_lines()]
    assert any("[STA " in line and "/" in line for line in plain_header)
    assert any("[HP " in line and "/" in line for line in plain_header)
    assert any("[Tool " in line for line in plain_header)
    hud_footer = game.footer_lines()
    assert len(hud_footer) <= game.hud_footer_budget()
    assert len(hud_footer) >= 1
    assert all(visible_terminal_len(line) <= hud_width for line in hud_footer)
    plain_footer = [ANSI_CSI_RE.sub("", line) for line in hud_footer]
    if game.hud_sidebar_active():
        assert not any(line.startswith("MESSAGE |") for line in plain_footer)
        sidebar_lines = [ANSI_CSI_RE.sub("", line) for line in game.hud_sidebar_lines()]
        assert len(sidebar_lines) == data.VIEW_HEIGHT
        assert any("ACTIVITY" in line for line in sidebar_lines)
        assert not any("INTERACTION" in line or "TARGET" in line for line in sidebar_lines)
    else:
        assert any(line.startswith("MESSAGE |") for line in plain_footer)
    original_terminal_width = farmstead_main.terminal_width
    hud_regression_game = FarmGame()
    original_row_count = hud_regression_game.terminal_row_count
    try:
        farmstead_main.terminal_width = lambda: 100
        hud_regression_game.terminal_row_count = lambda: 36
        assert hud_regression_game.hud_sidebar_active()
        hud_regression_game.set_message("Found a Copper Ore.")
        hud_regression_game.set_message("Found a Copper Ore.")
        assert hud_regression_game.state.hud_activity_log[-1]["count"] == 2
        assert hud_regression_game.state.hud_activity_log[-1]["category"] == "gain"
        wide_sidebar = [ANSI_CSI_RE.sub("", line) for line in hud_regression_game.hud_sidebar_lines()]
        assert len(wide_sidebar) == data.VIEW_HEIGHT
        assert any("Found a Copper Ore. x2" in line for line in wide_sidebar)
        assert all(len(line) == hud_regression_game.hud_sidebar_width() for line in wide_sidebar)
        assert any("Copper Ore" in line for line in hud_regression_game.hud_activity_log_lines("gain"))
        for activity_index in range(30):
            hud_regression_game.add_hud_activity(f"History event {activity_index}.", "general")
        history_frame, history_scroll, history_max_scroll = hud_regression_game.hud_fullscreen_history_frame(
            "all", None, width=90, height=30,
        )
        plain_history_frame = [ANSI_CSI_RE.sub("", line) for line in history_frame]
        assert len(plain_history_frame) == 30
        assert all(len(line) == 90 for line in plain_history_frame)
        assert any("ACTIVITY HISTORY" in line for line in plain_history_frame)
        assert any("B/X/J/Esc/Q/Tab close" in line for line in plain_history_frame)
        assert history_scroll == history_max_scroll and history_max_scroll > 0
        assert any("Copper Ore" in line for line in hud_regression_game.hud_fullscreen_history_rows("gain", 70))
        hud_regression_game.state.show_hud_sidebar = False
        assert not hud_regression_game.hud_sidebar_active()
        assert any("MESSAGE |" in ANSI_CSI_RE.sub("", line) for line in hud_regression_game.footer_lines())
        hud_regression_game.state.show_hud_sidebar = True

        farmstead_main.terminal_width = lambda: 73
        hud_regression_game.terminal_row_count = lambda: 31
        assert not hud_regression_game.hud_sidebar_active()
        hud_regression_game.state.player_name = "Aaron"
        hud_regression_game.state.money = 999999
        hud_regression_game.state.player_x = 8
        hud_regression_game.state.player_y = 6
        hud_regression_game.state.facing = "RIGHT"
        hud_regression_game.state.selected_tool_index = data.TOOLS.index("Seeds")
        hud_regression_game.state.selected_seed = "Turnip"
        hud_regression_game.state.message = "Selected tool: Seeds."
        narrow_hud_lines = hud_regression_game.header_lines() + hud_regression_game.footer_lines()
        assert not any("..." in line for line in narrow_hud_lines)
        assert any("World position 8,6" in line for line in narrow_hud_lines)
        assert any("claim friendship rewards" in line for line in narrow_hud_lines)
    finally:
        farmstead_main.terminal_width = original_terminal_width
        hud_regression_game.terminal_row_count = original_row_count
    weather_shelter_game = FarmGame()
    weather_shelter_game.state.weather = "Stormy"
    weather_shelter_game.state.current_cave_key = "0,0"
    weather_shelter_game.state.current_dungeon_key = "0,0:1,1"
    for location, expected_label in [
        ("Mine", "Underground"),
        ("WildernessCave", "Underground"),
        ("WildernessDungeon", "Underground"),
        ("HouseInterior", "Sheltered"),
        ("ProceduralSettlementInterior", "Sheltered"),
    ]:
        weather_shelter_game.state.location = location
        assert weather_shelter_game.location_is_weather_sheltered()
        assert weather_shelter_game.visible_weather_label() == expected_label
        assert weather_shelter_game.render_weather_overlay(1, 1) is None
        assert "Stormy" not in " ".join(weather_shelter_game.header_lines())
    weather_shelter_game.state.location = "Farm"
    assert not weather_shelter_game.location_is_weather_sheltered()
    assert weather_shelter_game.visible_weather_label() == "Stormy"
    hoe_index = data.TOOLS.index("Hoe")
    weather_shelter_game.state.selected_tool_index = hoe_index
    grass_x, grass_y = next(
        (x, y)
        for y, row in enumerate(weather_shelter_game.base_map)
        for x, tile in enumerate(row)
        if tile == "."
    )
    tool_hint = weather_shelter_game.target_action_hint(grass_x, grass_y)
    assert tool_hint.startswith("F:")
    assert not tool_hint.startswith("E:")
    render_locations = list(VALID_GAME_LOCATIONS)
    if "WildernessOverworld" not in render_locations:
        render_locations.append("WildernessOverworld")
    for location in render_locations:
        game.state.location = location
        if location == "Town":
            game.state.player_x, game.state.player_y = 57, 22
        elif location == "Wilderness":
            game.set_wilderness_chunk(0, 0)
            game.state.player_x, game.state.player_y = 10, 10
        elif location == "WildernessCave":
            game.state.current_cave_key = "0,0"
            game.state.player_x, game.state.player_y = 27, 18
        elif location == "WildernessDungeon":
            game.state.current_dungeon_key = "0,0"
            game.state.player_x, game.state.player_y = 27, 18
        else:
            game.state.player_x, game.state.player_y = 8, 9
        if not game.in_active_bounds(game.state.player_x, game.state.player_y):
            game.state.player_x, game.state.player_y = 1, 1
        game.state.message = f"Render sweep for {location}. " + ("Long HUD text " * 8)
        frame_width = max(game.hud_display_width(), game.active_map_width())
        for rendered_line in game.render_frame_text().splitlines():
            assert visible_terminal_len(rendered_line) <= frame_width
    interior_audit_specs = [
        ("GeneralStoreInterior", "general_store_map", {"D", "&", "P", "s", "f", "b", "t"}),
        ("BlacksmithInterior", "blacksmith_interior_map", {"D", "&", "P", "a", "f", "o", "q", "w", "t"}),
        ("LibraryInterior", "library_interior_map", {"D", "&", "P", "A", "l", "t"}),
        ("MayorHouseInterior", "mayor_house_map", {"D", "&", "P", "F", "d"}),
        ("InnInterior", "inn_interior_map", {"D", "&", "P", "B", "k", "p"}),
        ("FurnitureStoreInterior", "furniture_store_map", {"D", "&", "P", "C", "m", "A"}),
        ("CarpenterStoreInterior", "carpenter_store_map", {"D", "&", "P", "b", "w", "t"}),
        ("AnimalStoreInterior", "animal_store_map", {"D", "&", "P", "m", "c", "p", "h", "f"}),
        ("ClinicInterior", "clinic_map", {"D", "&", "P", "e", "m", "b", "s"}),
        ("TownHallInterior", "town_hall_map", {"D", "&", "P", "p", "r", "m", "n"}),
        ("MarketRowInterior", "market_row_map", {"D", "&", "P", "v", "f", "r", "t", "m"}),
        ("MuseumInterior", "museum_interior_map", {"D", "d", "&", "P", "C", "F", "G", "M", "A", "E", "S"}),
    ]
    authored_private_door_minimums = {
        "GeneralStoreInterior": 2,
        "LibraryInterior": 1,
        "MayorHouseInterior": 1,
        "InnInterior": 4,
        "MuseumInterior": 1,
        "FurnitureStoreInterior": 1,
        "ClinicInterior": 2,
        "TownHallInterior": 2,
    }
    authored_layout_signatures = set()
    authored_catalog_actions = set()
    authored_factory_by_attr = dict(game.TOWN_INTERIOR_MAP_SPECS)
    for location, map_attr, required_tiles in interior_audit_specs:
        game.state.location = location
        game.state.player_x, game.state.player_y = 27, 18
        game.state.hour, game.state.minute = 6, 0
        runtime_grid = getattr(game, map_attr)
        grid = getattr(game, authored_factory_by_attr[map_attr])()
        # Public starting-town maps always come from the modular runtime; old
        # blueprint override records no longer replace this architecture.
        setattr(game, map_attr, grid)
        game.state.player_x = len(grid[0]) - 2
        game.state.player_y = len(grid) - 2
        cam_x, cam_y = game.camera_origin()
        assert cam_x == max(0, len(grid[0]) - farmstead_main.VIEW_WIDTH)
        assert cam_y == max(0, len(grid) - farmstead_main.VIEW_HEIGHT)
        player_screen_x = game.state.player_x - cam_x
        player_screen_y = game.state.player_y - cam_y
        camera_rows = [ANSI_CSI_RE.sub("", row) for row in game.map_lines()]
        assert camera_rows[player_screen_y][player_screen_x] == ANSI_CSI_RE.sub(
            "", game.render_player()
        )
        game.state.player_x, game.state.player_y = 27, 18
        catalog_lookup = game._starting_town_catalog_furniture_cache.get(location, {})
        assert catalog_lookup, f"{location} has no catalog furniture layer"
        for furniture_position, furniture_cell in catalog_lookup.items():
            furniture_name = str(furniture_cell.get("name", "Furniture"))
            authored_catalog_actions.add(furniture_actions.furniture_action_id(
                furniture_name, data.INFRASTRUCTURE_DATA.get(furniture_name, {}),
            ))
            use_hint = game.town_interior_tile_hint(*furniture_position)
            assert use_hint.startswith("Z/Enter:")
            assert not use_hint.lower().startswith("z/enter: inspect")
            assert game.is_interactable_tile(*furniture_position)
        catalog_position, catalog_cell = next(iter(catalog_lookup.items()))
        assert catalog_cell["name"] in furniture_catalog.FURNITURE_CATALOG_DATA
        catalog_description = game.town_interior_tile_description(*catalog_position)
        assert str(catalog_cell["name"]) in str(catalog_description)
        assert visible_terminal_len(
            game.render_tile(catalog_position[0], catalog_position[1], grid)
        ) == 1
        source_catalog_glyph = str(catalog_cell.get("glyph", " "))[:1]
        expected_catalog_glyph = furniture_art.furniture_display_cell(
            str(catalog_cell["name"]),
            int(catalog_cell.get("offset_x", 0) or 0),
            int(catalog_cell.get("offset_y", 0) or 0),
            True,
            int(catalog_cell.get("rotation", 0) or 0),
        ) or furniture_art.furniture_display_glyph(
            source_catalog_glyph,
            catalog_cell.get("material_role", "wood"),
            True,
        )
        expected_catalog_glyph = furniture_art.furniture_orient_display_glyph(
            expected_catalog_glyph,
            catalog_cell.get("building_side", "south"),
        )
        assert ANSI_CSI_RE.sub(
            "", game.render_tile(catalog_position[0], catalog_position[1], grid)
        ) == expected_catalog_glyph
        authored_layout_signatures.add(tuple("".join(row) for row in grid))
        interior_symbols = set("".join("".join(row) for row in grid))
        interior_catalog = game.town_interior_tile_catalog(location)
        assert interior_symbols <= set(interior_catalog), (
            f"{location} contains uncatalogued glyphs: "
            f"{sorted(interior_symbols - set(interior_catalog))}"
        )
        for semantic_tile in interior_symbols:
            semantic_record = interior_catalog[semantic_tile]
            semantic_description = str(semantic_record.get("desc", ""))
            semantic_hint = str(semantic_record.get("hint", ""))
            assert len(semantic_description) >= 8
            assert "nothing here needs your attention" not in semantic_description.lower()
            assert "uncatalogued" not in semantic_description.lower()
            assert semantic_hint and "nothing" not in semantic_hint.lower()
            semantic_furniture_name = game.town_semantic_furniture_name(semantic_tile)
            semantic_x, semantic_y = next(
                (x, y)
                for y, row in enumerate(grid)
                for x, tile in enumerate(row)
                if tile == semantic_tile
            )
            if semantic_furniture_name:
                live_semantic_hint = game.town_interior_tile_hint(semantic_x, semantic_y)
                assert not live_semantic_hint.lower().startswith("z/enter: inspect")
            semantic_furniture = game.starting_town_catalog_furniture_at(
                semantic_x, semantic_y
            )
            resolved_description = game.town_interior_tile_description(
                semantic_x, semantic_y
            )
            if semantic_furniture:
                assert str(semantic_furniture["name"]) in str(resolved_description)
            else:
                assert resolved_description == semantic_description
            if semantic_tile not in {".", ":", ",", "#", " "}:
                assert semantic_tile in game.town_interior_interactable_tiles()
        exit_positions = [
            (x, y)
            for y, row in enumerate(grid)
            for x, tile in enumerate(row)
            if tile == "D"
        ]
        assert len(exit_positions) == 1, f"{location} needs exactly one exterior exit"
        entry_x, entry_y = game.authored_interior_entry_tile()
        assert game.passable(entry_x, entry_y), f"{location} entry lane is blocked"
        assert not any(
            tile == "|" for row in grid for tile in row
        ), f"{location} public room connections should be open archways"
        assert sum(row.count("_") for row in grid) >= authored_private_door_minimums.get(
            location, 0
        ), f"{location} should retain purposeful private/service doors"
        full_width_spoke_rows = sum(
            1
            for lane_y in (8, 11, 14, 16)
            if all(grid[lane_y][lane_x] == "." for lane_x in range(8, 46))
        )
        assert full_width_spoke_rows <= 1, f"{location} still looks like the old full-width spoke template"
        sleep_x, sleep_y = game.indoor_npc_base_position(location)
        assert game.passable(sleep_x, sleep_y), f"{location} sleep anchor blocked at {sleep_x},{sleep_y}"
        seen = {(entry_x, entry_y)}
        queue = deque([(entry_x, entry_y)])
        while queue:
            x, y = queue.popleft()
            for nx, ny in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                if (
                    (nx, ny) in seen
                    or not game.in_active_bounds(nx, ny)
                    or (
                        not game.passable(nx, ny)
                        and grid[ny][nx] != "_"
                    )
                ):
                    continue
                seen.add((nx, ny))
                queue.append((nx, ny))
        for tile in required_tiles:
            positions = [(x, y) for y, row in enumerate(grid) for x, ch in enumerate(row) if ch == tile]
            assert positions, f"{location} missing interior tile {tile!r}"
            if tile == "&":
                assert len(positions) == 1, f"{location} should have one clear service point, found {len(positions)}"
            assert any(
                (x + dx, y + dy) in seen
                for x, y in positions
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
            ), f"{location} tile {tile!r} is not reachable"
        assert "leave" in game.interaction_hint(*exit_positions[0])
        setattr(game, map_attr, runtime_grid)
    assert len(authored_layout_signatures) >= len(interior_audit_specs) - 1, "Authored town interiors are too visually repetitive"
    assert {"seat", "sleep", "cook", "work", "storage", "table"}.issubset(authored_catalog_actions)

    game.state.location = "GeneralStoreInterior"
    general_store_catalog = game._starting_town_catalog_furniture_cache["GeneralStoreInterior"]
    shared_container_cells = {}
    for position, cell in general_store_catalog.items():
        furniture_name = str(cell.get("name", ""))
        if not data.INFRASTRUCTURE_DATA.get(furniture_name, {}).get("container_profile"):
            continue
        shared_container_cells.setdefault(
            game.furniture_state_key(furniture_name, position[0], position[1], cell), []
        ).append(position)
    multi_cell_container = next(cells for cells in shared_container_cells.values() if len(cells) >= 2)
    first_container = game.world_container_at(*multi_cell_container[0])
    second_container = game.world_container_at(*multi_cell_container[1])
    assert first_container is second_container
    assert first_container.get("name") in data.INFRASTRUCTURE_DATA

    original_safe_menu = game.safe_menu
    counter_services = []
    game.safe_menu = lambda menu_func, close_message: counter_services.append(close_message)
    counter_service_specs = [
        ("GeneralStoreInterior", "general_store_map", "use_general_store_action"),
        ("BlacksmithInterior", "blacksmith_interior_map", "use_blacksmith_interior_action"),
        ("MuseumInterior", "museum_interior_map", "use_museum_action"),
        ("InnInterior", "inn_interior_map", "use_inn_action"),
        ("CarpenterStoreInterior", "carpenter_store_map", "use_carpenter_store_action"),
        ("FurnitureStoreInterior", "furniture_store_map", "use_furniture_store_action"),
        ("ClinicInterior", "clinic_map", "use_clinic_action"),
        ("TownHallInterior", "town_hall_map", "use_town_hall_action"),
        ("MarketRowInterior", "market_row_map", "use_market_row_action"),
        ("AnimalStoreInterior", "animal_store_map", "use_animal_store_action"),
    ]
    for location, map_attr, action_name in counter_service_specs:
        game.state.location = location
        counter_grid = getattr(game, map_attr)
        counter_positions = [
            (x, y, tile)
            for y, row in enumerate(counter_grid)
            for x, tile in enumerate(row)
            if tile in {"$", "&"}
        ]
        counter_x, counter_y, _counter_tile = next(
            (entry for entry in counter_positions if entry[2] == "$"),
            next(entry for entry in counter_positions if entry[2] == "&"),
        )
        before_counter_service = len(counter_services)
        getattr(game, action_name)(counter_x, counter_y)
        assert len(counter_services) == before_counter_service + 1
    game.safe_menu = original_safe_menu
    for residence_id in data.AUTHORED_TOWN_RESIDENCE_DATA:
        game.state.current_authored_residence_id = residence_id
        game.state.location = "TownResidenceInterior"
        runtime_residence_grid = game.authored_town_residence_map(residence_id)
        residence_grid = game.make_authored_town_residence_map(residence_id)
        game._authored_town_residence_maps[residence_id] = residence_grid
        residence_catalog = game.town_interior_tile_catalog(
            "TownResidenceInterior"
        )
        residence_symbols = set(
            "".join("".join(row) for row in residence_grid)
        )
        assert residence_symbols <= set(residence_catalog)
        assert all(
            "nothing here needs your attention"
            not in str(residence_catalog[tile]["desc"]).lower()
            for tile in residence_symbols
        )
        game._authored_town_residence_maps[residence_id] = runtime_residence_grid
    game.state.current_authored_residence_id = ""
    for authored_map_attr, authored_factory_name in game.TOWN_INTERIOR_MAP_SPECS:
        setattr(game, authored_map_attr, getattr(game, authored_factory_name)())
    game.state.location = "InnInterior"
    inn_closed_door = next(
        (x, y)
        for y, row in enumerate(game.inn_interior_map)
        for x, tile in enumerate(row)
        if tile == "_"
    )
    assert game.use_town_room_door_action(*inn_closed_door)
    assert game.inn_interior_map[inn_closed_door[1]][inn_closed_door[0]] == "|"
    assert game.use_town_room_door_action(*inn_closed_door)
    assert game.inn_interior_map[inn_closed_door[1]][inn_closed_door[0]] == "_"
    door_route_game = FarmGame()
    door_route_game.inn_interior_map = door_route_game.make_inn_interior_map()
    door_route_game.state.town_npcs = []
    route_door = None
    for door_y, row in enumerate(door_route_game.inn_interior_map):
        for door_x, tile in enumerate(row):
            if tile != "_":
                continue
            for start, target, far in (
                ((door_x - 1, door_y), (door_x + 1, door_y), (door_x + 2, door_y)),
                ((door_x + 1, door_y), (door_x - 1, door_y), (door_x - 2, door_y)),
                ((door_x, door_y - 1), (door_x, door_y + 1), (door_x, door_y + 2)),
                ((door_x, door_y + 1), (door_x, door_y - 1), (door_x, door_y - 2)),
            ):
                if (
                    door_route_game.authored_town_interior_passable("InnInterior", *start)
                    and door_route_game.authored_town_interior_passable("InnInterior", *target)
                    and door_route_game.authored_town_interior_passable("InnInterior", *far)
                ):
                    route_door = ((door_x, door_y), start, target, far)
                    break
            if route_door:
                break
        if route_door:
            break
    assert route_door is not None
    (route_door_x, route_door_y), route_start, route_target, route_far = route_door
    door_test_npc = {
        "id": "authored_door_test",
        "interior_x": route_start[0],
        "interior_y": route_start[1],
        "steps_today": 0,
    }
    assert door_route_game.inn_interior_map[route_door_y][route_door_x] == "_"
    door_route_game.town_npc_move_interior_toward(
        door_test_npc,
        "InnInterior",
        route_target,
    )
    assert (door_test_npc["interior_x"], door_test_npc["interior_y"]) == (
        route_door_x,
        route_door_y,
    )
    assert door_route_game.inn_interior_map[route_door_y][route_door_x] == "|"
    door_test_npc["interior_x"], door_test_npc["interior_y"] = route_far
    door_route_game.town_npc_close_used_interior_door(
        door_test_npc,
        "InnInterior",
        route_far,
    )
    assert door_route_game.inn_interior_map[route_door_y][route_door_x] == "_"

    service_action_specs = [
        ("GeneralStoreInterior", "general_store_map", "use_general_store_action", "General Store closed."),
        ("BlacksmithInterior", "blacksmith_interior_map", "use_blacksmith_interior_action", "Blacksmith closed."),
        ("LibraryInterior", "library_interior_map", "use_library_action", "Library closed."),
        ("MuseumInterior", "museum_interior_map", "use_museum_action", "Museum closed."),
        ("InnInterior", "inn_interior_map", "use_inn_action", "Inn services closed."),
        ("FurnitureStoreInterior", "furniture_store_map", "use_furniture_store_action", "Furniture Store closed."),
        ("CarpenterStoreInterior", "carpenter_store_map", "use_carpenter_store_action", "Carpenter closed."),
        ("AnimalStoreInterior", "animal_store_map", "use_animal_store_action", "Animal Store closed."),
        ("ClinicInterior", "clinic_map", "use_clinic_action", "Clinic closed."),
        ("TownHallInterior", "town_hall_map", "use_town_hall_action", "Town Hall closed."),
        ("MarketRowInterior", "market_row_map", "use_market_row_action", "Market Row closed."),
    ]
    original_safe_menu = game.safe_menu
    try:
        for location, map_attr, action_name, expected_fallback in service_action_specs:
            game.state.location = location
            grid = getattr(game, map_attr)
            sx, sy = next((x, y) for y, row in enumerate(grid) for x, ch in enumerate(row) if ch == "&")
            opened = []
            game.safe_menu = lambda callback, fallback, opened=opened: opened.append(fallback)
            getattr(game, action_name)(sx, sy)
            assert opened == [expected_fallback], f"{location} service point did not open its service menu"
            passive_x, passive_y = next(
                (x, y)
                for y, row in enumerate(grid)
                for x, tile in enumerate(row)
                if tile == "-"
            )
            expected_passive_description = game.town_interior_tile_catalog(
                location
            )["-"]["desc"]
            getattr(game, action_name)(passive_x, passive_y)
            assert game.state.message == expected_passive_description
    finally:
        game.safe_menu = original_safe_menu

    routine_game = FarmGame()
    routine_game.state.town_development_stage = 3
    routine_game.state.unlocked_town_buildings = list(data.TOWN_BUILDING_IDS)
    routine_game.state.hour, routine_game.state.minute = 6, 0
    routine_game.state.weather = "Sunny"
    for npc in routine_game.active_town_npcs():
        wake_entry = routine_game.town_npc_routine_plan(npc).get("wake", {})
        wake_location = routine_game.normalize_town_npc_schedule_value(wake_entry)
        assert isinstance(wake_location, dict) and "inside" in wake_location, f"{npc.get('id')} does not wake indoors"
        assert (
            str(wake_location["inside"]) == "Private Home"
            or str(wake_location["inside"]).strip().lower() in data.AUTHORED_TOWN_RESIDENCE_ID_BY_NAME
            or routine_game.town_interior_location_for_name(str(wake_location["inside"]))
        ), f"{npc.get('id')} has no valid home destination"
    old_jun = next(npc for npc in routine_game.active_town_npcs() if npc.get("id") == "old_jun")
    assert routine_game.town_npc_indoor_location(old_jun) == "Meadow Cottage"
    inn_sleepers = [
        npc for npc in routine_game.active_town_npcs()
        if routine_game.town_npc_actual_location(npc) == "InnInterior"
    ]
    assert {str(npc.get("id")) for npc in inn_sleepers} == {"mae_innkeeper", "chef_basil", "aria_musician"}
    routine_game.state.location = "InnInterior"
    routine_game.state.player_x, routine_game.state.player_y = 27, 18
    inn_positions = routine_game.town_indoor_npc_positions()
    assert len(inn_positions) == 3
    assert len(set(inn_positions.values())) == 3, "Inn sleepers should occupy separate rooms"
    inn_bed_anchors = set(routine_game.town_npc_fixture_room_anchors("InnInterior", {"B"}))
    assert set(inn_positions.values()) <= inn_bed_anchors
    # Late travelers describe the trip home instead of appearing to sleep on
    # the street, and the 11 PM fallback resolves every blocked route indoors.
    routine_game.state.location = "Wilderness"
    routine_game.return_to_seamless_town(50, 24)
    routine_game.state.hour, routine_game.state.minute = 22, 0
    late_npc = next(npc for npc in routine_game.active_town_npcs() if npc.get("id") != routine_game.state.spouse_npc_id)
    late_npc["runtime_location"] = "Town"
    late_npc["indoors"] = False
    assert routine_game.town_npc_activity_label(late_npc) == "walking home to sleep"
    routine_game.state.hour = 23
    routine_game.update_town_npcs(force_reanchor=True)
    assert all(
        routine_game.town_npc_actual_location(npc) != "Town"
        for npc in routine_game.active_town_npcs()
    )

    assert len(data.AUTHORED_TOWN_RESIDENCE_DATA) == 6
    assigned_residents = [
        str(npc_id)
        for residence in data.AUTHORED_TOWN_RESIDENCE_DATA.values()
        for npc_id in residence.get("residents", ())
    ]
    assert len(assigned_residents) == len(set(assigned_residents)) == 21
    residence_signatures = set()
    for residence_id, residence in data.AUTHORED_TOWN_RESIDENCE_DATA.items():
        door_x, door_y = residence["door"]
        assert routine_game.town_map[door_y][door_x] == "D"
        assert routine_game.town_map[door_y + 1][door_x] in {":", "="}
        assert sum(
            1 for y in range(door_y - 5, door_y + 1)
            for x in range(door_x - 5, door_x + 6)
            if routine_game.town_map[y][x] == "h"
        ) >= 50
        residence_map = routine_game.authored_town_residence_map(residence_id)
        residence_signatures.add(tuple("".join(row) for row in residence_map))
        assert sum(row.count("D") for row in residence_map) == 1
        assert sum(row.count("B") for row in residence_map) == len(residence.get("residents", ()))
        assert sum(row.count("k") for row in residence_map) == 1
        routine_game.state.current_authored_residence_id = residence_id
        routine_game.state.location = "TownResidenceInterior"
        entry_x, entry_y = routine_game.authored_interior_entry_tile()
        routine_game.state.player_x, routine_game.state.player_y = entry_x, entry_y
        assert routine_game.passable(entry_x, entry_y)
        routine_game.exit_authored_town_residence()
        assert routine_game.state.location == "Wilderness"
        assert routine_game.home_world_source_at(
            routine_game.state.player_x, routine_game.state.player_y,
        ) == ("town", door_x, door_y + 1)
        assert routine_game.enter_authored_town_residence(residence_id)
        assert routine_game.location_label() == residence.get("label")
    assert len(residence_signatures) == len(data.AUTHORED_TOWN_RESIDENCE_DATA)

    household_game = FarmGame()
    household_game.state.town_development_stage = 3
    household_game.state.unlocked_town_buildings = list(data.TOWN_BUILDING_IDS)
    while household_game.state.weekday != "Monday":
        household_game.state.day += 1
    household_game.state.hour, household_game.state.minute = 14, 0
    household_game.state.weather = "Sunny"
    household_game.state.location = "Town"
    household_game.state.player_x, household_game.state.player_y = 57, 22
    for _ in range(20):
        household_game.update_town_npcs()
    household_game.state.hour = 17
    for _ in range(350):
        household_game.update_town_npcs()
    for residence_id, residence in data.AUTHORED_TOWN_RESIDENCE_DATA.items():
        runtime_location = household_game.town_npc_residence_runtime_location(residence_id)
        occupants = [
            npc for npc in household_game.active_town_npcs()
            if household_game.town_npc_actual_location(npc) == runtime_location
        ]
        assert {str(npc.get("id")) for npc in occupants} == set(residence.get("residents", ()))
        household_game.state.current_authored_residence_id = residence_id
        household_game.state.location = "TownResidenceInterior"
        household_game.state.player_x, household_game.state.player_y = 27, 18
        positions = household_game.town_indoor_npc_positions()
        assert len(positions) == len(occupants)
        assert len(set(positions.values())) == len(occupants)
    social_pairs = [
        npc for npc in household_game.active_town_npcs()
        if str(npc.get("social_partner_id", "")) and "household news" in str(npc.get("social_activity", ""))
    ]
    assert len(social_pairs) >= 12

    visit_game = FarmGame()
    visit_game.state.town_development_stage = 3
    visit_game.state.unlocked_town_buildings = list(data.TOWN_BUILDING_IDS)
    while visit_game.state.weekday != "Saturday":
        visit_game.state.day += 1
    visit_game.state.hour, visit_game.state.minute = 14, 0
    visit_game.state.weather = "Sunny"
    visit_game.state.location = "Town"
    visit_game.state.player_x, visit_game.state.player_y = 57, 22
    for _ in range(20):
        visit_game.update_town_npcs()
    visit_game.state.hour = 17
    visitors = [
        npc for npc in visit_game.active_town_npcs()
        if data.AUTHORED_TOWN_RESIDENCE_ID_BY_NPC.get(str(npc.get("id", "")))
        and visit_game.town_npc_desired_location(npc)
        != visit_game.town_npc_residence_runtime_location(
            data.AUTHORED_TOWN_RESIDENCE_ID_BY_NPC[str(npc.get("id", ""))]
        )
    ]
    assert visitors
    for _ in range(400):
        visit_game.update_town_npcs()
    assert all(
        visit_game.town_npc_actual_location(npc) == visit_game.town_npc_desired_location(npc)
        for npc in visitors
    )

    malformed_regional_state = GameState(regional_town_life={
        "visitors": [{"id": "route:test", "x": "bad", "route_slot": "bad"}],
        "visitor_bonds": {"route:test": "bad"},
        "npc_social_links": {"a|b": {"score": "bad", "meetings": "bad"}},
        "journeys": {"bad": {"origin_chunk_x": "bad"}},
        "resident_trips": {"bad": {"return_day_number": "bad"}},
    })
    assert malformed_regional_state.regional_town_life["visitors"][0]["x"] == 58
    assert malformed_regional_state.regional_town_life["npc_social_links"]["a|b"]["meetings"] == 0
    assert not malformed_regional_state.regional_town_life["journeys"]
    assert not malformed_regional_state.regional_town_life["resident_trips"]

    real_destinations = procedural_town_game.regional_real_destinations()
    discovered_destination = next(
        destination for destination in real_destinations
        if (int(destination.get("chunk_x", 0)), int(destination.get("chunk_y", 0)))
        == (int(procedural_town_plan["chunk_x"]), int(procedural_town_plan["chunk_y"]))
    )
    assert discovered_destination["known"] is True
    assert discovered_destination["name"] == procedural_town_plan["name"]
    assert discovered_destination["industry"]
    assert discovered_destination["exports"]

    circulation_game = FarmGame()
    circulation_game.state.wilderness_seed = 24681357
    circulation_game.state.hour = 6
    circulation_game.state.weather = "Sunny"
    inbound_visitors = circulation_game.ensure_regional_town_visitors()
    assert inbound_visitors
    inbound_visitor = next(
        visitor for visitor in inbound_visitors
        if visitor.get("origin_kind") in {"road_service", "outpost"}
        and circulation_game.wilderness_chunk_has_regional_road(
            int(visitor.get("origin_chunk_x", 0)), int(visitor.get("origin_chunk_y", 0))
        )
    )
    assert inbound_visitor["runtime_location"] == "InTransit"
    assert inbound_visitor["origin_id"]
    assert inbound_visitor["distance_chunks"] >= 1
    assert inbound_visitor["route_condition"] in {"Open", "Reliable", "Well Maintained", "Weather Delayed", "Hazardous"}
    visitor_topic_lines = {
        topic: " ".join(circulation_game.regional_visitor_conversation_lines(inbound_visitor, topic, 6))
        for topic in ("work", "origin", "town", "news", "personal")
    }
    assert len(set(visitor_topic_lines.values())) == 5
    assert str(inbound_visitor["origin"]) in visitor_topic_lines["origin"]
    origin_chunk = (int(inbound_visitor["origin_chunk_x"]), int(inbound_visitor["origin_chunk_y"]))
    projected = circulation_game.regional_circulation_travelers_for_chunk(*origin_chunk)
    assert any(record.get("id") == inbound_visitor["id"] for record in projected)
    circulation_game.state.location = "Wilderness"
    circulation_game.state.wilderness_chunk_x, circulation_game.state.wilderness_chunk_y = origin_chunk
    route_travelers = circulation_game.generate_wilderness_travelers(*origin_chunk)
    matching_route_traveler = next(record for record in route_travelers if record.get("id") == inbound_visitor["id"])
    assert matching_route_traveler["regional_circulation"] is True
    assert matching_route_traveler["route_destination_name"] == "Elsewhere"
    assert matching_route_traveler["road_route"] is True
    assert (
        matching_route_traveler["route_destination_world_x"],
        matching_route_traveler["route_destination_world_y"],
    ) == circulation_game.home_world_destination_world_positions()["town"]
    circulation_game.autosave_with_message = lambda message: circulation_game.set_message(message)
    circulation_game.state.stamina = 100
    money_before_escort = int(circulation_game.state.money)
    bond_before_escort = int(
        circulation_game.regional_town_life_state().setdefault("visitor_bonds", {}).get(
            str(inbound_visitor["id"]), 0
        ) or 0
    )
    assert circulation_game.assist_regional_circulation_traveler(matching_route_traveler) is True
    assert circulation_game.state.stamina == min(
        circulation_game.max_stamina(),
        100 - 4 + 40 // 5,
    )
    assert circulation_game.state.money == money_before_escort + 45
    assert matching_route_traveler["route_condition"] == "Traveler Assisted"
    assert int(
        circulation_game.regional_town_life_state()["visitor_bonds"].get(
            str(inbound_visitor["id"]), 0
        ) or 0
    ) == bond_before_escort + 2
    assert circulation_game.assist_regional_circulation_traveler(matching_route_traveler) is False

    market_life_game = FarmGame()
    market_life_game.state.town_development_stage = 3
    market_life_game.state.unlocked_town_buildings = list(data.TOWN_BUILDING_IDS)
    market_life_game.state.month, market_life_game.state.day, market_life_game.state.year = 3, 14, 1
    market_life_game.state.hour, market_life_game.state.minute = 14, 0
    market_life_game.state.weather = "Sunny"
    market_life_game.state.location = "Town"
    market_life_game.state.player_x, market_life_game.state.player_y = 57, 22
    market_occasion = market_life_game.todays_town_public_occasion()
    assert market_occasion.get("kind") == "market"
    assert "Regional Market" in str(market_occasion.get("name"))
    market_features = market_life_game.town_public_event_features()
    assert len(market_features) >= 9
    assert sum(feature.get("action") == "market" for feature in market_features.values()) == 3
    assert any("Public occasion" in line for line in market_life_game.selected_calendar_events_text(3, 14, 1))
    for _ in range(320):
        market_life_game.update_town_npcs()
    market_visitors = market_life_game.regional_town_visitors()
    assert len(market_visitors) == 3
    assert len({str(visitor.get("id")) for visitor in market_visitors}) == 3
    assert len({(int(visitor.get("x")), int(visitor.get("y"))) for visitor in market_visitors}) == 3
    assert all(visitor.get("origin_id") and visitor.get("regional_news") for visitor in market_visitors)
    assert all(int(visitor.get("distance_chunks", 0)) >= 1 for visitor in market_visitors)
    register_text = "\n".join(market_life_game.inn_guest_register_lines())
    assert "INN GUEST REGISTER" in register_text
    assert all(str(visitor.get("origin")) in register_text for visitor in market_visitors)
    cartographer = next(visitor for visitor in market_visitors if visitor.get("role") == "Cartographer")
    unknown_origin_chunks = market_life_game.regional_origin_chart_unknown_count(cartographer)
    assert unknown_origin_chunks > 0
    market_life_game.state.money = 1000
    market_life_game.autosave_with_message = lambda message: market_life_game.set_message(message)
    assert market_life_game.purchase_regional_visitor_origin_chart(cartographer)
    assert market_life_game.regional_origin_chart_unknown_count(cartographer) == 0
    goods_visitor = next(visitor for visitor in market_visitors if market_life_game.regional_visitor_stock(visitor))
    assert all(record.get("item") and int(record.get("price", 0)) > 0 for record in market_life_game.regional_visitor_stock(goods_visitor))
    assert sum(
        "browsing stalls" in market_life_game.town_npc_activity_label(npc)
        for npc in market_life_game.active_town_npcs()
    ) >= 10
    market_life_game.state.hour = 18
    for _ in range(300):
        market_life_game.update_town_npcs()
    assert all(visitor.get("runtime_location") == "InnInterior" for visitor in market_visitors)
    market_life_game.state.location = "InnInterior"
    market_life_game.state.player_x, market_life_game.state.player_y = 27, 18
    visitor_positions = market_life_game.regional_visitor_position_lookup()
    assert len(visitor_positions) == len(market_visitors)
    assert len(set(visitor_positions)) == len(market_visitors)
    assert not set(visitor_positions).intersection(set(market_life_game.town_indoor_npc_positions().values()))
    market_life_game.state.hour = 22
    market_life_game.update_town_npcs()
    assert all(visitor.get("runtime_location") == "GuestLodging" for visitor in market_visitors)

    festival_life_game = FarmGame()
    festival_life_game.state.town_development_stage = 3
    festival_life_game.state.unlocked_town_buildings = list(data.TOWN_BUILDING_IDS)
    festival_life_game.state.month, festival_life_game.state.day, festival_life_game.state.year = 3, 7, 1
    festival_life_game.state.hour, festival_life_game.state.minute = 18, 0
    festival_life_game.state.weather = "Sunny"
    festival_life_game.state.location = "Town"
    festival_life_game.state.player_x, festival_life_game.state.player_y = 57, 22
    festival_life_game.state.spouse_npc_id = "mira_seed"
    festival_life_game.state.spouse_moved_to_farm = True
    assert festival_life_game.todays_town_public_occasion().get("kind") == "festival"
    mira_festival = next(npc for npc in festival_life_game.active_town_npcs() if npc.get("id") == "mira_seed")
    assert festival_life_game.town_npc_desired_location(mira_festival) == "Town"
    festival_targets = {
        festival_life_game.town_npc_schedule_anchor(npc)
        for npc in festival_life_game.active_town_npcs()
    }
    assert len(festival_targets) == len(festival_life_game.active_town_npcs())
    for _ in range(600):
        festival_life_game.update_town_npcs()
    assert len(festival_life_game.regional_town_visitors()) == 5
    assert len(festival_life_game.regional_town_life_state()["npc_social_links"]) >= 12

    regional_trip_game = FarmGame()
    regional_trip_game.state.town_development_stage = 3
    regional_trip_game.state.unlocked_town_buildings = list(data.TOWN_BUILDING_IDS)
    while regional_trip_game.state.weekday != "Tuesday":
        regional_trip_game.state.day += 1
    regional_trip_game.state.hour, regional_trip_game.state.minute = 14, 0
    regional_trip_game.state.weather = "Sunny"
    regional_trip_game.state.location = "Town"
    regional_trip_game.state.player_x, regional_trip_game.state.player_y = 57, 22
    traveling_residents = [
        npc for npc in regional_trip_game.active_town_npcs()
        if regional_trip_game.town_npc_desired_location(npc) == "RegionalTravel"
    ]
    assert traveling_residents
    for _ in range(350):
        regional_trip_game.update_town_npcs()
    assert all(regional_trip_game.town_npc_actual_location(npc) == "RegionalTravel" for npc in traveling_residents)
    assert all(str(npc.get("regional_destination", "")) for npc in traveling_residents)
    assert all(npc.get("regional_destination_id") for npc in traveling_residents)
    assert all(isinstance(npc.get("regional_destination_chunk_x"), int) for npc in traveling_residents)
    trip_records = regional_trip_game.regional_town_life_state()["resident_trips"]
    long_distance_residents = [
        npc for npc in traveling_residents if str(npc.get("id")) in trip_records
    ]
    local_commuting_residents = [
        npc for npc in traveling_residents if str(npc.get("id")) not in trip_records
    ]
    assert long_distance_residents
    assert all(regional_trip_game.home_region_commute_plan(npc) for npc in local_commuting_residents)
    primary_trip_npc = long_distance_residents[0]
    primary_trip = trip_records[str(primary_trip_npc["id"])]
    assert int(primary_trip["return_day_number"]) > int(primary_trip["depart_day_number"])
    assert primary_trip["expected_return"]
    assert primary_trip["destination_name"] == primary_trip_npc["regional_destination"]
    assert any(
        "Regional departure" in event
        for event in regional_trip_game.regional_circulation_calendar_events_for_date(
            regional_trip_game.state.month, regional_trip_game.state.day, regional_trip_game.state.year
        )
    )
    trip_path = regional_trip_game.regional_circulation_route_chunks(
        int(primary_trip["chunk_x"]), int(primary_trip["chunk_y"]), str(primary_trip_npc["id"])
    )
    projected_resident = [
        traveler
        for point in set(trip_path)
        for traveler in regional_trip_game.regional_circulation_travelers_for_chunk(*point)
        if traveler.get("id") == primary_trip_npc["id"]
    ]
    assert projected_resident
    assert projected_resident[0]["authored_resident_trip"] is True
    regional_trip_game.state.hour = 17
    for _ in range(350):
        regional_trip_game.update_town_npcs()
    assert all(regional_trip_game.town_npc_actual_location(npc) == "RegionalTravel" for npc in long_distance_residents)
    assert all(regional_trip_game.town_npc_actual_location(npc) != "RegionalTravel" for npc in local_commuting_residents)
    travel_days = max(
        int(trip_records[str(npc["id"])]["return_day_number"])
        - int(trip_records[str(npc["id"])]["depart_day_number"])
        for npc in long_distance_residents
    )
    for _ in range(travel_days):
        (
            regional_trip_game.state.month,
            regional_trip_game.state.day,
            regional_trip_game.state.year,
        ) = helpers.advance_date(
            regional_trip_game.state.month,
            regional_trip_game.state.day,
            regional_trip_game.state.year,
        )
    regional_trip_game.state.hour = 17
    for npc in traveling_residents:
        regional_trip_game.town_npc_desired_location(npc)
    for _ in range(350):
        regional_trip_game.update_town_npcs()
    assert all(regional_trip_game.town_npc_actual_location(npc) != "RegionalTravel" for npc in traveling_residents)

    authored_route_game = FarmGame()
    authored_route_game.state.unlocked_town_buildings = list(data.TOWN_BUILDING_IDS)
    authored_route_game.state.hour, authored_route_game.state.minute = 11, 55
    authored_route_game.state.weather = "Sunny"
    authored_route_game.state.location = "GeneralStoreInterior"
    authored_route_game.state.player_x, authored_route_game.state.player_y = 25, 16
    mira = next(npc for npc in authored_route_game.active_town_npcs() if npc.get("id") == "mira_seed")
    assert authored_route_game.town_npc_actual_location(mira) == "GeneralStoreInterior"
    authored_route_game.update_town_npcs()
    service_anchor = authored_route_game.town_npc_interior_anchor(mira, "GeneralStoreInterior")
    for _ in range(80):
        authored_route_game.update_town_npcs()
        if (int(mira.get("interior_x", -1)), int(mira.get("interior_y", -1))) == service_anchor:
            break
    assert (int(mira.get("interior_x", -1)), int(mira.get("interior_y", -1))) == service_anchor
    assert authored_route_game.town_npc_work_service_available(mira)

    authored_route_game.state.hour, authored_route_game.state.minute = 12, 0
    interior_steps = []
    for _ in range(100):
        interior_steps.append((int(mira.get("interior_x", -1)), int(mira.get("interior_y", -1))))
        authored_route_game.update_town_npcs()
        if authored_route_game.town_npc_actual_location(mira) == "Town":
            break
    assert authored_route_game.town_npc_actual_location(mira) == "Town"
    assert len(set(interior_steps)) > 1, "Mira should visibly walk to the store door"
    assert (int(mira.get("x", -1)), int(mira.get("y", -1))) == authored_route_game.town_npc_exterior_access("GeneralStoreInterior", "mira_seed")

    authored_route_game.state.location = "Town"
    authored_route_game.state.player_x, authored_route_game.state.player_y = 57, 22
    lunch_target = authored_route_game.town_npc_schedule_anchor(mira)
    reached_lunch_target = False
    for _ in range(12):
        authored_route_game.update_town_npcs()
        if (int(mira.get("x", -1)), int(mira.get("y", -1))) == lunch_target:
            reached_lunch_target = True
            break
    assert reached_lunch_target, "Mira should follow town paths to her lunch destination"

    authored_route_game.state.hour, authored_route_game.state.minute = 14, 0
    for _ in range(200):
        authored_route_game.update_town_npcs()
        if authored_route_game.town_npc_actual_location(mira) == "GeneralStoreInterior":
            break
    assert authored_route_game.town_npc_actual_location(mira) == "GeneralStoreInterior"
    assert (
        int(mira.get("interior_x", -1)),
        int(mira.get("interior_y", -1)),
    ) == authored_route_game.town_npc_nearest_interior_tile(
        "GeneralStoreInterior",
        27,
        18,
    )

    transition_game = FarmGame()
    transition_game.state.unlocked_town_buildings = list(data.TOWN_BUILDING_IDS)
    transition_audit_specs = [
        ("general_store", "GeneralStoreInterior", "transition_to_general_store", "transition_from_general_store_to_town"),
        ("blacksmith", "BlacksmithInterior", "transition_to_blacksmith_interior", "transition_from_blacksmith_to_town"),
        ("library", "LibraryInterior", "transition_to_library_interior", "transition_from_library_to_town"),
        ("mayor_house", "MayorHouseInterior", "transition_to_mayor_house", "transition_from_mayor_house_to_town"),
        ("inn", "InnInterior", "transition_to_inn_interior", "transition_from_inn_to_town"),
        ("furniture_store", "FurnitureStoreInterior", "transition_to_furniture_store", "transition_from_furniture_store_to_town"),
        ("carpenter", "CarpenterStoreInterior", "transition_to_carpenter_store", "transition_from_carpenter_store_to_town"),
        ("animal_store", "AnimalStoreInterior", "transition_to_animal_store", "transition_from_animal_store_to_town"),
        ("clinic", "ClinicInterior", "transition_to_clinic", "transition_from_clinic_to_town"),
        ("town_hall", "TownHallInterior", "transition_to_town_hall", "transition_from_town_hall_to_town"),
        ("market_row", "MarketRowInterior", "transition_to_market_row", "transition_from_market_row_to_town"),
        ("museum", "MuseumInterior", "transition_to_museum", "transition_from_museum_to_town"),
    ]
    for building_id, interior_location, enter_method, exit_method in transition_audit_specs:
        door_x, door_y = data.TOWN_DOORS[building_id]
        transition_game.state.location = "Town"
        transition_game.state.player_x, transition_game.state.player_y = door_x, door_y + 1
        getattr(transition_game, enter_method)()
        assert transition_game.state.location == interior_location, f"{building_id} did not enter {interior_location}"
        assert transition_game.in_active_bounds(transition_game.state.player_x, transition_game.state.player_y), f"{building_id} interior spawn out of bounds"
        assert transition_game.passable(transition_game.state.player_x, transition_game.state.player_y), f"{building_id} interior spawn blocked"
        getattr(transition_game, exit_method)()
        assert transition_game.state.location == "Wilderness", f"{building_id} did not exit to the seamless town"
        assert transition_game.home_world_source_at(
            transition_game.state.player_x, transition_game.state.player_y,
        ) == ("town", door_x, door_y + 1), f"{building_id} town exit is misplaced"
        assert transition_game.in_active_bounds(transition_game.state.player_x, transition_game.state.player_y), f"{building_id} town exit out of bounds"
        assert transition_game.passable(transition_game.state.player_x, transition_game.state.player_y), f"{building_id} town exit blocked"
    house_layout = game.default_house_furniture_layout()
    assert "Wall Calendar" in house_layout
    assert "Bookshelf" in house_layout
    assert "Crib" in data.INFRASTRUCTURE_DATA
    assert "Family Table" in data.INFRASTRUCTURE_DATA
    assert game.state.last_automation_report == []
    assert any("FARM AUTOMATION" in line for line in game.automation_status_lines())

    family_game = FarmGame()
    family_game.vertical_panel_view = lambda *args, **kwargs: None
    family_game.autosave_with_message = lambda message: family_game.set_message(message)
    family_special_events = []
    family_game.play_world_event_scene = (
        lambda event_id, title, steps, completion_message="":
        family_special_events.append((str(event_id), str(title), list(steps))) or True
    )
    spouse = family_game.town_npc_definition("finn_fisher")
    assert spouse
    family_game.state.player_sex = "Female"
    family_game.state.spouse_npc_id = "finn_fisher"
    family_game.state.spouse_moved_to_farm = True
    family_game.state.marriage_month = family_game.state.month
    family_game.state.marriage_day = family_game.state.day
    family_game.state.marriage_year = family_game.state.year
    family_game.state.town_npc_relationships["finn_fisher"] = 220
    family_game.state.town_npc_dialogue_counts["finn_fisher"] = 30
    family_game.state.town_npc_courtship_counts["finn_fisher"] = 12
    assert family_game.town_npc_role_color(spouse) == support.C.WATER
    generated_spouse_color = {
        "id": "proc:test-town:spouse",
        "role": "Merchant",
        "color": "Red",
    }
    family_game.state.spouse_npc_id = str(generated_spouse_color["id"])
    assert family_game.town_npc_role_color(generated_spouse_color) == dict(data.PLAYER_COLOR_OPTIONS)["Red"]
    family_game.state.spouse_npc_id = "finn_fisher"
    assert family_game.family_status_lines()
    assert family_game.marriage_status_lines()
    assert not family_game.can_start_pregnancy_with_spouse(spouse)[0]
    family_game.mark_family_event_flag("family_planning_discussed:finn_fisher")
    ok, reason = family_game.can_start_pregnancy_with_spouse(spouse)
    assert ok, reason
    assert family_game.start_pregnancy_with_spouse(spouse)
    assert family_game.state.pregnancy_active
    assert family_game.pregnancy_month_number() == 1
    assert family_game.pregnancy_checkup_available()
    assert family_game.complete_pregnancy_checkup(spouse)
    assert not family_game.pregnancy_checkup_available()
    family_game.state.month = family_game.state.pregnancy_due_month
    family_game.state.day = family_game.state.pregnancy_due_day
    family_game.state.year = family_game.state.pregnancy_due_year
    family_game.choose_child_birth_options = (
        lambda default_name, _sex, profile: (default_name, str(profile.get("starting_class", "Vanguard")))
    )
    birth_msg = family_game.update_family_overnight(interactive=True)
    assert "was born" in birth_msg
    assert not family_game.state.pregnancy_active
    assert family_game.state.children
    child = family_game.state.children[0]
    assert any(event_id.startswith("birth:") for event_id, _title, _steps in family_special_events)
    assert child.get("personality_trait")
    assert child.get("favorite_gift")
    assert child.get("apprentice_path")
    assert child.get("starting_class") in family_game.child_starting_class_catalog()
    family_game.state.year = max(family_game.state.year, int(child.get("birth_year", 1)) + 7)
    milestone_note = family_game.record_child_milestones_overnight(interactive=True)
    assert str(child.get("name")) in milestone_note
    assert any(
        event_id.startswith("child_milestone:")
        for event_id, _title, _steps in family_special_events
    )
    assert any("Trait:" in line for line in family_game.household_child_status_lines(child))
    child_conversation_topics = {
        topic: " ".join(family_game.household_child_talk_lines(child, topic))
        for topic in ("feelings", "activity", "learning", "chores", "family")
    }
    assert len(set(child_conversation_topics.values())) == 5
    assert all(str(child.get("name")) in text for text in child_conversation_topics.values())
    assert all("Affection:" not in text for text in child_conversation_topics.values())
    family_game.state.inventory["Field Snack"] = 2
    assert family_game.share_family_meal("Field Snack")
    assert family_game.state.family_bond > 0
    assert family_game.state.family_last_meal == "Field Snack"
    family_game.state.family_bond = 100
    assert family_game.family_sleep_bonus() == 4
    assert family_game.set_spouse_support_mode("Meals")
    assert family_game.state.spouse_support_mode == "Meals"
    favorite = str(child.get("favorite_gift"))
    family_game.state.inventory[favorite] = family_game.state.inventory.get(favorite, 0) + 1
    assert family_game.give_child_gift(child, favorite)
    assert family_game.child_affection_score(child) > 0
    assert family_game.teach_child_lesson(child, "Farming")
    assert family_game.child_learning_map(child).get("Farming") == 1
    assert family_game.assign_child_chore(child, "Gather forage")
    assert family_game.child_chore_assignment(child) == "Gather forage"
    assert any("TODAY AT HOME" in line for line in family_game.family_today_lines())
    assert any("FAMILY GROWTH" in line for line in family_game.family_growth_report_lines())
    assert family_game.ensure_family_world_state()["version"] == 1
    assert family_game.family_weekly_priority() == "Togetherness"
    family_game.state.hour = 10
    family_game.state.minute = 0
    child_destination = family_game.family_child_destination(child)
    assert family_game.family_child_destination(child) is child_destination
    assert child_destination["location"] == "LibraryInterior"
    assert "studying" in str(child_destination["activity"])
    spouse_destination = family_game.family_spouse_destination(spouse)
    assert family_game.family_spouse_destination(spouse) is spouse_destination
    assert spouse_destination["location"] == "Original"
    family_game.state.location = "HouseInterior"
    assert not any(
        str(actor.get("id", "")) == f"household_child:{child.get('id')}"
        for actor in family_game.household_child_npcs()
    )
    assert not any(
        str(actor.get("id", "")) == "finn_fisher"
        for actor in family_game.town_npc_position_lookup().values()
    )
    family_game.state.location = "LibraryInterior"
    assert any(
        str(actor.get("id", "")) == f"household_child:{child.get('id')}"
        for actor in family_game.town_npc_position_lookup().values()
    )
    family_game.state.location = "HouseInterior"
    family_game.state.hour = 19
    family_game.state.minute = 0
    family_game.house_map = [list("." * 55) for _ in range(20)]
    family_game.state.placed_objects = {}
    family_game.state.placed_object_rotations = {}
    family_game.state.placed_object_finishes = {}
    family_game.state.player_x = 1
    family_game.state.player_y = 1
    family_game.set_placed_object(5, 5, "Dining Set")
    family_game.set_placed_object(20, 5, "Reading Nook", rotation=1)
    family_game.set_placed_object(35, 5, "Four-Poster Bed")
    family_lookup = family_game.town_npc_position_lookup()
    family_actor_ids = {str(actor.get("id", "")) for actor in family_lookup.values()}
    assert "finn_fisher" in family_actor_ids
    assert f"household_child:{child.get('id')}" in family_actor_ids
    family_positions = [
        position for position, actor in family_lookup.items()
        if str(actor.get("id", "")) in {"finn_fisher", f"household_child:{child.get('id')}"}
    ]
    assert len(family_positions) == len(set(family_positions)) == 2
    assert all(family_game.in_house_bounds_for_npc(*position) for position in family_positions)
    for family_position in family_positions:
        family_key, family_object, family_ax, family_ay = family_game.placed_object_at(*family_position)
        assert (
            family_object is None
            or family_game.object_cell_walkable(
                family_object, *family_position, family_ax, family_ay,
                family_game.object_rotation_for_key(family_key, family_object),
            )
        )
    family_activities = [
        str(actor.get("runtime_activity", actor.get("activity", "")))
        for actor in family_lookup.values()
        if str(actor.get("id", "")) in {"finn_fisher", f"household_child:{child.get('id')}"}
    ]
    assert all(activity for activity in family_activities)
    assert any(
        marker in " ".join(family_activities)
        for marker in ("reading", "relaxing", "table", "conversation")
    )
    household_schedule_text = " ".join(family_game.family_member_schedule_lines())
    assert any(
        marker in household_schedule_text
        for marker in ("reading", "relaxing", "table", "conversation")
    )
    family_game.state.location = "Farm"
    assert family_game.set_family_weekly_priority("Rest")
    assert family_game.family_sleep_bonus() == 5
    checkin_bond = family_game.family_bond_score()
    assert family_game.complete_family_partnership_checkin()
    assert family_game.family_bond_score() > checkin_bond
    assert not family_game.family_partnership_checkin_available()[0]
    assert any(
        event_id.startswith("partnership_checkin:")
        for event_id, _title, _steps in family_special_events
    )
    assert family_game.schedule_family_outing("Library Visit", 1)
    planned_outing = dict(family_game.state.family_world_state["planned_outing"])
    family_game.state.month = int(planned_outing["month"])
    family_game.state.day = int(planned_outing["day"])
    family_game.state.year = int(planned_outing["year"])
    outing_bond = family_game.family_bond_score()
    outing_learning = int(family_game.child_learning_map(child).get("Study", 0))
    assert family_game.family_world_outing_ready()
    assert family_game.complete_planned_family_outing()
    assert family_game.family_bond_score() > outing_bond
    assert family_game.child_learning_map(child).get("Study", 0) > outing_learning
    assert family_game.state.family_world_state["outing_history"]
    assert not family_game.state.family_world_state["planned_outing"]
    assert family_special_events and family_special_events[-1][0].startswith("family_outing:")
    assert any("HOUSEHOLD DASHBOARD" in line for line in family_game.family_world_dashboard_lines())
    family_game.state.player_birthday_month = 4
    family_game.state.player_birthday_day = 2
    family_game.state.owned_wilderness_claims["2,3"] = {
        "chunk_x": 2,
        "chunk_y": 3,
        "name": "Test Prairie Claim",
        "farm_type": "Prairie Farm",
        "traits": "open land",
    }
    family_game.state.mine_combat_victories = 2
    family_game.state.deepest_mine_floor = 6
    family_game.state.combat_level = 3
    family_game.state.automation_machines["Farm:10,10"] = {"seed_crop": "Turnip", "seed_qty": 1}
    reactive_context = family_game.dialogue_context_for_npc(spouse)
    assert reactive_context["owned_claim_count"] == 1
    reactive_categories = family_game.dialogue_categories_for_npc(spouse)
    assert "land_claim_owned" in reactive_categories
    assert "combat_victory" in reactive_categories
    assert "combat_level" in reactive_categories
    assert "automation_active" in reactive_categories
    assert "child_school_age" in reactive_categories
    assert family_game.contextual_dialogue_entries_for_category(spouse, "land_claim_owned")
    assert family_game.contextual_dialogue_entries_for_category(spouse, "combat_victory")
    assert family_game.town_npc_reactivity_lines(spouse, limit=3)
    help_msg = family_game.apply_family_household_help_overnight()
    assert "Household help" in help_msg
    family_game.toggle_family_help()
    assert family_game.state.family_help_enabled is False

    wedding_game = FarmGame()
    wedding_game.vertical_panel_view = lambda *args, **kwargs: None
    wedding_game.vertical_panel_select = (
        lambda title, items, *args, **kwargs:
        next(item for item in items if item.value == 7)
    )
    wedding_game.autosave_with_message = (
        lambda message: wedding_game.set_message(message)
    )
    wedding_special_events = []
    wedding_game.play_world_event_scene = (
        lambda event_id, title, steps, completion_message="":
        wedding_special_events.append((str(event_id), str(title), list(steps))) or True
    )
    wedding_game.state.player_sex = "Female"
    wedding_game.state.money = data.WEDDING_RING_PRICE + 500
    assert wedding_game.purchase_wedding_ring()
    assert wedding_game.state.money == 500
    assert wedding_game.state.inventory[data.WEDDING_RING_ITEM] == 1
    fiance = wedding_game.npc_record_by_id("finn_fisher")
    assert fiance and wedding_game.is_heterosexual_match_for_player(fiance)
    fiance_id = str(fiance["id"])
    wedding_game.state.town_npc_relationships[fiance_id] = 220
    wedding_game.state.town_npc_dialogue_counts[fiance_id] = 30
    wedding_game.state.town_npc_courtship_counts[fiance_id] = 12
    wedding_game.state.dating_npc_ids = [fiance_id]
    wedding_game.set_relationship_milestone(fiance_id, "trusted")
    assert wedding_game.can_propose_to_town_npc(fiance)[0]
    assert wedding_game.propose_to_town_npc(fiance)
    assert wedding_game.state.engaged_npc_id == fiance_id
    assert wedding_game.state.spouse_npc_id == ""
    assert wedding_game.state.inventory[data.WEDDING_RING_ITEM] == 0
    assert wedding_game.wedding_date_label() != "not recorded"
    wedding_plan = wedding_game.ensure_family_world_state()["wedding_plan"]
    wedding_plan["venue"] = "Farm Meadow"
    wedding_plan["style"] = "Intimate"
    wedding_plan["guest_focus"] = "Immediate household"
    ceremony_text = " ".join(wedding_game.wedding_ceremony_lines(fiance))
    assert "Farm Meadow" in ceremony_text
    assert "Intimate" in ceremony_text
    assert "Immediate household" in ceremony_text
    assert any(
        "Wedding ceremony" in event
        for event in wedding_game.calendar_advisory_events_for_date(
            wedding_game.state.wedding_month,
            wedding_game.state.wedding_day,
            wedding_game.state.wedding_year,
        )
    )
    wedding_game.state.month = wedding_game.state.wedding_month
    wedding_game.state.day = wedding_game.state.wedding_day
    wedding_game.state.year = wedding_game.state.wedding_year
    wedding_game.state.weather = "Clear"
    wedding_message = wedding_game.process_scheduled_wedding_overnight(
        interactive=True
    )
    assert "married" in wedding_message
    assert wedding_game.state.spouse_npc_id == fiance_id
    assert wedding_game.state.engaged_npc_id == ""
    assert any("Farm Meadow" in row for row in wedding_game.state.family_event_log)
    assert wedding_game.state.marriage_history[-1]["status"] == "married"
    assert wedding_special_events and wedding_special_events[-1][0].startswith("wedding:")
    assert any("Farm Meadow" in str(step.get("text", "")) for step in wedding_special_events[-1][2])
    assert wedding_game.marriage_date_label() != "not recorded"
    spouse_age_before_pause = wedding_game.spouse_age_years(fiance)
    wedding_game.set_aging_and_death_enabled(False, autosave=False)
    wedding_game.state.year += 3
    assert wedding_game.spouse_age_years(fiance) == spouse_age_before_pause
    assert any(
        "Spouse life stage:" in line
        for line in wedding_game.marriage_status_lines()
    )
    wedding_game.set_aging_and_death_enabled(True, autosave=False)
    assert wedding_game.spouse_age_years(fiance) == spouse_age_before_pause

    marriage_scene_key, marriage_scene_title = wedding_game.available_marriage_scene(fiance)
    assert marriage_scene_key.startswith("anniversary:")
    assert marriage_scene_title == "Anniversary"
    marriage_relationship_before = wedding_game.town_npc_relationship(fiance_id)
    marriage_turns = []
    original_marriage_say = wedding_game.dialogue_say
    original_marriage_choose = wedding_game.dialogue_choose
    wedding_game.dialogue_say = lambda actor, text, phase, transcript: (
        transcript.append({"speaker": str(actor.get("name", "NPC")), "text": str(text), "phase": str(phase)}),
        marriage_turns.append((str(actor.get("name", "NPC")), str(phase), str(text))),
        True,
    )[-1]
    wedding_game.dialogue_choose = lambda *args, **kwargs: "Adventure"
    try:
        assert wedding_game.play_marriage_scene(fiance)
    finally:
        wedding_game.dialogue_say = original_marriage_say
        wedding_game.dialogue_choose = original_marriage_choose
    assert marriage_turns[0][0] == "Narrator"
    assert any(turn[0] == str(fiance["name"]) for turn in marriage_turns)
    assert wedding_game.family_weekly_priority() == "Adventure"
    assert wedding_game.has_family_event_flag(marriage_scene_key)
    assert wedding_game.town_npc_relationship(fiance_id) == marriage_relationship_before + 3

    birthday_month, birthday_day = wedding_game.npc_birthday(fiance)
    wedding_game.state.month = birthday_month
    wedding_game.state.day = birthday_day
    wedding_game.state.spouse_birth_year = wedding_game.state.year - 90
    wedding_game.state.spouse_lifespan_age = 90
    passing_message = wedding_game.process_spouse_lifespan_overnight(
        interactive=False
    )
    assert "died peacefully" in passing_message
    assert wedding_game.state.spouse_npc_id == ""
    assert fiance_id in wedding_game.state.deceased_spouse_npc_ids
    assert wedding_game.state.marriage_history[-1]["status"] == "widowed"
    assert any(
        "Remarriage: available" in line
        for line in wedding_game.marriage_status_lines()
    )
    assert fiance_id not in {
        str(npc.get("id", ""))
        for npc in wedding_game.active_town_npcs()
    }

    remarriage_candidate = next(
        npc
        for npc in wedding_game.state.town_npcs
        if (
            str(npc.get("id", "")) != fiance_id
            and wedding_game.is_marriageable_npc(npc)
        )
    )
    remarriage_id = str(remarriage_candidate["id"])
    wedding_game.state.town_npc_relationships[remarriage_id] = 220
    wedding_game.state.town_npc_dialogue_counts[remarriage_id] = 30
    wedding_game.state.town_npc_courtship_counts[remarriage_id] = 12
    wedding_game.state.dating_npc_ids = [remarriage_id]
    wedding_game.set_relationship_milestone(remarriage_id, "trusted")
    wedding_game.state.inventory[data.WEDDING_RING_ITEM] = 1
    assert wedding_game.can_propose_to_town_npc(remarriage_candidate)[0]
    assert wedding_game.propose_to_town_npc(remarriage_candidate)
    assert wedding_game.state.engaged_npc_id == remarriage_id
    assert wedding_game.state.spouse_npc_id == ""

    automation_game = FarmGame()
    automation_game.autosave_with_message = lambda message: automation_game.set_message(message)
    automation_game.state.location = "Farm"
    automation_game.base_map[10][10] = ","
    automation_game.base_map[10][11] = ","
    automation_game.base_map[11][10] = ","
    automation_game.state.placed_objects["Farm:10,9"] = "Rain Barrel"
    automation_game.state.placed_objects["Farm:12,10"] = "Harvest Crate"
    automation_game.state.placed_objects["Farm:13,10"] = "Shipping Loader"
    automation_game.state.placed_objects["Farm:14,10"] = "Shipping Bin"
    ready_crop = state.Crop("Turnip", age=data.CROP_DATA["Turnip"]["growth_days"], ready=True)
    automation_game.crops["Farm:11,10"] = ready_crop
    report = automation_game.run_daily_farm_automation()
    assert automation_game.base_map[10][10] == "w"
    assert automation_game.crop_for_scope("Farm", 11, 10) is None
    assert automation_game.state.shipped_today_items
    assert automation_game.state.shipped_today > 0
    assert any("irrigation watered" in line for line in report)
    assert any("harvest crates picked" in line for line in report)
    assert any("Shipping Loader" in line for line in automation_game.automation_status_lines("Farm"))

    shipping_game = FarmGame()
    shipping_game.shipping_bin_target = lambda: (5, 7)
    shipping_game.vertical_quantity_select = lambda *args, **kwargs: 3
    shipping_game.autosave_with_message = lambda message: shipping_game.set_message(message)
    shipping_game.state.inventory["Turnip"] = 5
    shipping_game.state.inventory["Wood"] = 12
    shipping_game.state.inventory["Copper Ore"] = 4
    shipping_game.state.inventory["Quartz"] = 2
    safe_shipping_names = {item_name for item_name, _qty, _price in shipping_game.shippable_items()}
    assert "Turnip" in safe_shipping_names
    assert "Wood" not in safe_shipping_names
    assert "Copper Ore" not in safe_shipping_names
    assert "Quartz" not in safe_shipping_names
    assert shipping_game.is_shippable_item("Turnip")
    assert not shipping_game.is_shippable_item("Wood")
    assert "protected" in shipping_game.item_hint_for_goods_list("Wood", 12)
    turnip_price = shipping_game.shippable_unit_price("Turnip")
    assert shipping_game.ship_inventory_item("Turnip")
    assert shipping_game.state.inventory["Turnip"] == 2
    assert shipping_game.state.shipped_today_items["Turnip"] == 3
    assert shipping_game.state.shipped_today == 3 * turnip_price
    assert not shipping_game.ship_inventory_item("Wood")
    assert shipping_game.state.inventory["Wood"] == 12
    assert shipping_game.reclaim_shipped_item("Turnip", 1)
    assert shipping_game.state.inventory["Turnip"] == 3
    assert shipping_game.state.shipped_today_items["Turnip"] == 2
    assert shipping_game.state.shipped_today == 2 * turnip_price
    assert any("Turnip" in line for line in shipping_game.shipping_report_lines())

    shop_qty_game = FarmGame()
    shop_qty_game.autosave_with_message = lambda message: shop_qty_game.set_message(message)
    shop_qty_game.state.location = "GeneralStoreInterior"
    shop_qty_game.state.money = 1000
    store_choices = iter([
        MenuItem(label="Buy infrastructure", value="infrastructure"),
        MenuItem(label="Fence", value="infra:Fence"),
        MenuItem(label="Choose quantity", value="buy_infra"),
    ])
    shop_qty_game.vertical_panel_select = lambda *args, **kwargs: next(store_choices)
    shop_qty_game.vertical_quantity_select = lambda *args, **kwargs: 7
    shop_qty_game.buy_menu()
    assert shop_qty_game.state.inventory["Fence"] == 7
    assert shop_qty_game.state.money == 1000 - (7 * int(data.INFRASTRUCTURE_DATA["Fence"]["price"]))

    general_potion_game = FarmGame()
    general_potion_game.autosave_with_message = lambda message: general_potion_game.set_message(message)
    general_potion_game.state.location = "GeneralStoreInterior"
    general_potion_game.state.money = 1000
    general_potion_choices = iter([
        MenuItem(label="Buy combat supplies", value="combat_supplies"),
        MenuItem(label="Health Potion", value="supply:Potion"),
    ])
    general_potion_game.vertical_panel_select = lambda *args, **kwargs: next(general_potion_choices)
    general_potion_game.vertical_quantity_select = lambda *args, **kwargs: 2
    general_potion_game.buy_menu()
    assert general_potion_game.state.inventory["Potion"] == 2
    assert general_potion_game.state.money == 1000 - 2 * int(general_potion_game.combat_supply_shop_stock("general")[0]["price"])

    bulk_shop_game = FarmGame()
    bulk_shop_game.autosave_with_message = lambda message: bulk_shop_game.set_message(message)
    bulk_shop_game.state.money = 5000
    assert bulk_shop_game.purchase_automation_item("Rain Barrel", qty=2)
    assert bulk_shop_game.state.inventory["Rain Barrel"] == 2
    assert bulk_shop_game.state.money == 5000 - (2 * int(data.INFRASTRUCTURE_DATA["Rain Barrel"]["price"]))
    assert bulk_shop_game.purchase_farm_building("Storage Shed", qty=2)
    assert bulk_shop_game.state.inventory["Storage Shed"] == 2

    clinic_qty_game = FarmGame()
    clinic_qty_game.autosave_with_message = lambda message: clinic_qty_game.set_message(message)
    clinic_qty_game.state.money = 1000
    clinic_qty_game.vertical_panel_select = lambda *args, **kwargs: MenuItem(label="Buy Animal Medicine", value="animal_medicine")
    clinic_qty_game.vertical_quantity_select = lambda *args, **kwargs: 3
    clinic_qty_game.clinic_menu()
    assert clinic_qty_game.state.inventory["Animal Medicine"] == 3
    clinic_potion_game = FarmGame()
    clinic_potion_game.autosave_with_message = lambda message: clinic_potion_game.set_message(message)
    clinic_potion_game.state.money = 1000
    clinic_potion_game.vertical_panel_select = lambda *args, **kwargs: MenuItem(label="Buy Mana Potion", value="ether")
    clinic_potion_game.vertical_quantity_select = lambda *args, **kwargs: 2
    clinic_potion_game.clinic_menu()
    assert clinic_potion_game.state.inventory["Ether"] == 2
    assert clinic_potion_game.state.money == 1000 - 2 * int(clinic_potion_game.combat_supply_shop_stock("clinic")[1]["price"])

    market_qty_game = FarmGame()
    market_qty_game.autosave_with_message = lambda message: market_qty_game.set_message(message)
    market_qty_game.state.money = 1000
    market_qty_game.vertical_panel_select = lambda *args, **kwargs: MenuItem(label="Buy Berries", value="Berries")
    market_qty_game.vertical_quantity_select = lambda *args, **kwargs: 2
    market_qty_game.market_row_menu()
    assert market_qty_game.state.inventory["Berries"] == 2
    assert market_qty_game.market_item_bought_today("Berries") == 2

    hopper_game = FarmGame()
    hopper_game.state.location = "Farm"
    hopper_game.base_map[10][10] = ","
    hopper_game.base_map[10][11] = ","
    hopper_game.state.placed_objects["Farm:10,10"] = "Seed Hopper"
    hopper_game.state.automation_machines["Farm:10,10"] = {"seed_crop": "Turnip", "seed_qty": 2, "last_message": ""}
    hopper_report = hopper_game.run_daily_farm_automation()
    assert hopper_game.crop_for_scope("Farm", 11, 10) is not None
    assert hopper_game.state.automation_machines["Farm:10,10"]["seed_qty"] == 1
    assert any("seed hoppers planted" in line for line in hopper_report)
    assert "Turnip Seeds x1" in "\n".join(hopper_game.automation_status_lines("Farm"))
    hopper_game.remove_placed_object(10, 10)
    assert hopper_game.state.inventory["Turnip Seeds"] >= 1
    assert "Farm:10,10" not in hopper_game.state.automation_machines

    build_game = FarmGame()
    build_game.autosave_with_message = lambda message: build_game.set_message(message)
    build_game.state.location = "Farm"
    build_game.state.inventory["Fence"] = 3
    for x in range(18, 24):
        build_game.base_map[10][x] = "."
    assert build_game.place_inventory_object_at("Fence", 18, 10, autosave=False)
    assert build_game.place_inventory_object_at("Fence", 19, 10, autosave=False)
    assert build_game.state.placed_objects["Farm:18,10"] == "Fence"
    assert build_game.state.placed_objects["Farm:19,10"] == "Fence"
    assert build_game.state.inventory["Fence"] == 1

    cursor_build_game = FarmGame()
    cursor_build_game.autosave_with_message = lambda message: cursor_build_game.set_message(message)
    cursor_build_game.draw_build_workspace = lambda *args, **kwargs: None
    cursor_build_game.state.location = "Farm"
    cursor_build_game.state.player_x = 10
    cursor_build_game.state.player_y = 10
    cursor_build_game.state.facing = "RIGHT"
    cursor_build_game.state.tool_target_mode = "FRONT"
    cursor_build_game.state.inventory["Fence"] = 2
    cursor_build_game.base_map[10][12] = "."
    cursor_build_game.base_map[10][13] = "."
    original_build_read_key = building.read_key
    build_keys = iter(["d", "\r", "d", "\r", "q"])
    building.read_key = lambda: next(build_keys)
    try:
        cursor_build_game.build_mode(initial_obj="Fence")
    finally:
        building.read_key = original_build_read_key
    assert cursor_build_game.state.placed_objects["Farm:12,10"] == "Fence"
    assert cursor_build_game.state.placed_objects["Farm:13,10"] == "Fence"
    assert cursor_build_game.state.inventory["Fence"] == 0

    house_layout_game = FarmGame()
    house_layout_game.state.location = "HouseInterior"
    custom_house_grid = [list(row) for row in house_layout_game.house_map]
    custom_house_grid[6][15] = "#"
    custom_house_grid[6][16] = "."
    house_layout_game.state.custom_house_map_rows = ["".join(row) for row in custom_house_grid]
    house_layout_game.house_map = house_layout_game.make_house_map()
    assert house_layout_game.house_map[6][15] == "#"
    assert house_layout_game.house_map[6][16] == "."

    hopper_old = "Farm:20,12"
    hopper_new = "Farm:22,12"
    build_game.state.placed_objects[hopper_old] = "Seed Hopper"
    build_game.state.automation_machines[hopper_old] = {
        "seed_crop": "Turnip",
        "seed_qty": 7,
        "last_message": "Loaded.",
    }
    build_game.base_map[12][22] = "."
    assert build_game.move_placed_object(hopper_old, 22, 12, autosave=False)
    assert hopper_old not in build_game.state.placed_objects
    assert hopper_old not in build_game.state.automation_machines
    assert build_game.state.placed_objects[hopper_new] == "Seed Hopper"
    assert build_game.state.automation_machines[hopper_new]["seed_qty"] == 7

    jar_old = "Farm:24,12"
    jar_new = "Farm:26,12"
    build_game.state.placed_objects[jar_old] = "Preserves Jar"
    build_game.state.artisan_processors[jar_old] = {
        "input": "Turnip",
        "output": "Pickled Turnip",
        "qty": 1,
        "days_left": 1,
    }
    build_game.base_map[12][26] = "."
    assert build_game.move_placed_object(jar_old, 26, 12, autosave=False)
    assert jar_old not in build_game.state.artisan_processors
    assert build_game.state.artisan_processors[jar_new]["input"] == "Turnip"
    assert not build_game.store_placed_object_at(26, 12, autosave=False)
    assert build_game.state.placed_objects[jar_new] == "Preserves Jar"

    pond_old = "Farm:30,4"
    pond_new = "Farm:36,4"
    build_game.state.placed_objects[pond_old] = "Fish Pond"
    build_game.state.fish_ponds[pond_old] = {"fish": "Carp", "count": 3, "days": 1, "ready": 2}
    build_game.state.farm_building_harvest_days[pond_old] = "1-3-1"
    build_game.state.farm_building_boosts[pond_old] = "baited"
    for y in range(4, 7):
        for x in range(36, 40):
            build_game.base_map[y][x] = "."
    assert build_game.move_placed_object(pond_old, 36, 4, autosave=False)
    assert pond_old not in build_game.state.fish_ponds
    assert build_game.state.fish_ponds[pond_new]["ready"] == 2
    assert build_game.state.farm_building_harvest_days[pond_new] == "1-3-1"
    assert build_game.state.farm_building_boosts[pond_new] == "baited"

    coop_old = "Farm:4,4"
    coop_new = "Farm:10,4"
    build_game.state.placed_objects[coop_old] = "Chicken Coop"
    build_game.state.farm_animals.append({
        "id": 999,
        "name": "Smoke Hen",
        "species": "Chicken",
        "building_key": coop_old,
    })
    for y in range(4, 7):
        for x in range(10, 14):
            build_game.base_map[y][x] = "."
    assert build_game.move_placed_object(coop_old, 10, 4, autosave=False)
    assert build_game.state.farm_animals[-1]["building_key"] == coop_new
    assert not build_game.store_placed_object_at(10, 4, autosave=False)
    assert build_game.state.placed_objects[coop_new] == "Chicken Coop"

    claim_auto_game = FarmGame()
    claim_auto_game.state.owned_wilderness_claims["2,3"] = {
        "chunk_x": 2,
        "chunk_y": 3,
        "name": "Smoke Claim",
        "farm_type_id": "prairie",
    }
    claim_scope = claim_auto_game.claim_scope_key(2, 3)
    claim_map = claim_auto_game.get_wilderness_chunk_map(2, 3)
    claim_map[10][10] = ","
    claim_auto_game.state.placed_objects[f"{claim_scope}:10,9"] = "Rain Barrel"
    claim_report = claim_auto_game.run_daily_farm_automation()
    assert claim_map[10][10] == "w"
    assert any("Smoke Claim" in line or "Claim" in line for line in claim_report)

    sleep_auto_game = FarmGame()
    sleep_auto_game.save = lambda quiet=False, path=None: True
    sleep_auto_game.state.location = "Farm"
    sleep_auto_game.state.wake_hour = 9
    sleep_auto_game.base_map[10][10] = ","
    sleep_auto_game.state.placed_objects["Farm:10,9"] = "Rain Barrel"
    sleep_auto_game.sleep(force=True)
    assert (sleep_auto_game.state.hour, sleep_auto_game.state.minute) == (9, 0)
    assert sleep_auto_game.state.last_automation_report
    assert "Automation report ready" in sleep_auto_game.state.message

    request_game = FarmGame()
    request_game.autosave_with_message = lambda message: request_game.set_message(message)
    assert request_game.available_resident_request_ids()
    assert request_game.resident_request_status("mira_seed_trial") == "Missing"
    assert request_game.resident_request_lines("mira_seed_trial")
    request_game.state.inventory["Turnip"] = 3
    before_money = request_game.state.money
    assert request_game.resident_request_status("mira_seed_trial") == "Ready"
    assert request_game.complete_resident_request("mira_seed_trial")
    assert "mira_seed_trial" in request_game.state.completed_resident_request_ids
    assert request_game.state.inventory["Turnip"] == 0
    assert request_game.state.inventory["Mixed Seeds"] >= 3
    assert request_game.state.money == before_money + 260
    assert request_game.town_npc_relationship("mira_seed") >= 12

    companion_quest_game = FarmGame()
    companion_quest_game.autosave_with_message = lambda message: companion_quest_game.set_message(message)
    companion_quest_game.unlock_town_building("blacksmith")
    companion_quest_game.state.town_npc_relationships["brom_smith"] = 60
    companion_quest_game.state.deepest_mine_floor = 3
    companion_quest_game.state.inventory["Iron Ore"] = 5
    companion_quest_game.state.inventory["Coal"] = 3
    assert companion_quest_game.companion_quest_status("brom_smith", data.COMPANION_QUEST_DATA["brom_smith"][0]) == "Ready"
    brom_progress_before = dict(companion_quest_game.combat_progress_for_key("brom_smith"))
    brom_money_before = companion_quest_game.state.money
    brom_stone_before = companion_quest_game.state.inventory.get("Stone", 0)
    assert companion_quest_game.complete_companion_quest("brom_smith", "brom_tempered_edge")
    assert "brom_tempered_edge" in companion_quest_game.state.completed_companion_quest_ids
    brom_progress_after = companion_quest_game.combat_progress_for_key("brom_smith")
    assert int(brom_progress_after["skill_points"]) == int(brom_progress_before["skill_points"]) + 1
    assert int(brom_progress_after["damage_bonus"]) == int(brom_progress_before["damage_bonus"]) + 1
    assert companion_quest_game.state.money == brom_money_before + 40
    assert companion_quest_game.state.inventory["Stone"] == brom_stone_before + 1
    assert companion_quest_game.state.combat_campaign_inventory == {}

    party_game = FarmGame()
    party_game.autosave_with_message = lambda message: party_game.set_message(message)
    party_game.state.unlocked_party_member_ids = ["missing", "brom_smith", "brom_smith"]
    party_game.state.active_party_member_ids = ["missing", "brom_smith"]
    party_game.sanitize_party_members(refresh_unlocks=False)
    assert party_game.state.unlocked_party_member_ids == ["brom_smith"]
    assert party_game.state.active_party_member_ids == []
    party_game.unlock_town_building("blacksmith")
    party_game.state.town_npc_relationships["brom_smith"] = 60
    party_game.refresh_unlocked_party_members()
    assert "brom_smith" in party_game.state.unlocked_party_member_ids
    assert party_game.party_companion_is_eligible("brom_smith")
    assert party_game.add_party_member("brom_smith")
    assert party_game.active_party_member_ids() == ["brom_smith"]
    assert party_game.set_party_tactic("Support")
    assert party_game.party_tactic() == "Support"
    assert party_game.set_party_member_manual_control("brom_smith", True)
    assert party_game.manual_party_member_ids() == ["brom_smith"]
    brom_profile = party_game.farmstead_companion_profile("brom_smith")
    assert brom_profile["name"] == "Brom"
    assert brom_profile["class"] == "Vanguard"
    assert brom_profile["manual_control"] is True
    assert brom_profile["max_hp"] >= int(FARMSTEAD_COMPANION_DATA["brom_smith"]["max_hp"])
    party_game.state.active_party_member_ids = list(FARMSTEAD_COMPANION_DATA)
    for building_id in ["blacksmith", "clinic", "animal_store", "library"]:
        party_game.unlock_town_building(building_id)
    for companion in FARMSTEAD_COMPANION_DATA.values():
        party_game.state.town_npc_relationships[str(companion["npc_id"])] = 100
    party_game.state.deepest_mine_floor = 3
    party_game.refresh_unlocked_party_members()
    assert len(party_game.active_party_member_ids()) == 3
    assert party_game.manual_party_member_ids() == ["brom_smith"]

    party_ui_game = FarmGame()
    party_ui_views = []
    party_ui_titles = []
    party_ui_labels = []
    party_ui_game.vertical_panel_view = lambda title, *args, **kwargs: party_ui_views.append(title)
    party_ui_game.vertical_panel_select = lambda title, items, *args, **kwargs: (
        party_ui_titles.append(title)
        or party_ui_labels.extend(item.label for item in items)
        or MenuItem(label="Back", value=farmstead_main.MENU_BACK)
    )
    assert party_ui_game.show_party_menu() == farmstead_main.MENU_BACK
    assert party_ui_titles == ["Battle Party"]
    assert "Travel Follower" not in party_ui_labels
    assert party_ui_views == []

    follower_ui_game = FarmGame()
    follower_ui_game.state.spouse_npc_id = "mira_seed"
    follower_ui_game.state.spouse_moved_to_farm = True
    follower_ui_game.state.year = 10
    follower_ui_game.state.children = [{
        "id": 77,
        "name": "Scout",
        "sex": "Female",
        "birth_month": 3,
        "birth_day": 1,
        "birth_year": 5,
        "parent_npc_id": "mira_seed",
        "personality_seed": 77,
        "personality_trait": "Curious",
        "favorite_gift": "Wildflower",
        "apprentice_path": "Scholar",
        "starting_class": "Mystic",
    }]
    follower_ui_game.state.travel_follower_ids = [spouse_follower_id, child_follower_id]
    follower_ui_game.normalize_travel_followers()
    follower_ui_labels = []
    follower_ui_game.vertical_panel_select = lambda title, items, *args, **kwargs: (
        follower_ui_labels.extend(item.label for item in items)
        or MenuItem(label="Back", value=farmstead_main.MENU_BACK)
    )
    assert follower_ui_game.travel_follower_menu(spouse_follower_id) == farmstead_main.MENU_BACK
    assert "Connect" in follower_ui_labels
    assert "Job report" in follower_ui_labels
    assert "Assign / change follower job" in follower_ui_labels
    assert "Expedition role" in follower_ui_labels
    assert "Formation position" in follower_ui_labels
    connection_ui_labels = []
    follower_ui_game.vertical_panel_select = lambda title, items, *args, **kwargs: (
        connection_ui_labels.extend(item.label for item in items)
        or MenuItem(label="Back", value=farmstead_main.MENU_BACK)
    )
    assert follower_ui_game.travel_follower_connection_menu(spouse_follower_id) == farmstead_main.MENU_BACK
    assert "Check In" in connection_ui_labels
    assert "Share a quiet moment" in connection_ui_labels
    assert "Spouse support focus" in connection_ui_labels
    assert "Bond & Memories" in connection_ui_labels
    formation_ui_labels = []
    follower_ui_game.vertical_panel_select = lambda title, items, *args, **kwargs: (
        formation_ui_labels.extend(item.label for item in items)
        or MenuItem(label="Back", value=farmstead_main.MENU_BACK)
    )
    assert follower_ui_game.travel_follower_formation_menu(spouse_follower_id) == farmstead_main.MENU_BACK
    assert "Rear guard" in formation_ui_labels
    assert "Left flank" in formation_ui_labels
    follower_ui_game.travel_follower_record(spouse_follower_id)["bond_points"] = 30
    role_ui_labels = []
    follower_ui_game.vertical_panel_select = lambda title, items, *args, **kwargs: (
        role_ui_labels.extend(item.label for item in items)
        or MenuItem(label="Back", value=farmstead_main.MENU_BACK)
    )
    assert follower_ui_game.travel_follower_expedition_role_menu(spouse_follower_id) == farmstead_main.MENU_BACK
    assert {"Balanced", "Scout", "Gatherer", "Guardian", "Support"} <= set(role_ui_labels)
    follower_group_labels = []
    follower_ui_game.vertical_panel_select = lambda title, items, *args, **kwargs: (
        follower_group_labels.extend(item.label for item in items)
        or MenuItem(label="Back", value=farmstead_main.MENU_BACK)
    )
    assert follower_ui_game.show_travel_follower_menu() == farmstead_main.MENU_BACK
    assert "Regroup everyone" in follower_group_labels
    assert "Send everyone home" in follower_group_labels

    combat_ui_game = FarmGame()
    combat_ui_views = []
    combat_ui_titles = []
    combat_ui_labels = []
    combat_ui_game.vertical_panel_view = lambda title, *args, **kwargs: combat_ui_views.append(title)
    combat_ui_game.vertical_panel_select = lambda title, items, *args, **kwargs: (
        combat_ui_titles.append(title)
        or combat_ui_labels.extend(item.label for item in items)
        or MenuItem(label="Back", value=farmstead_main.MENU_BACK)
    )
    assert combat_ui_game.show_combat_status_menu() == farmstead_main.MENU_BACK
    assert combat_ui_titles == ["Adventure"]
    assert combat_ui_views == []
    assert "Skills" in combat_ui_labels
    assert "Training" not in combat_ui_labels

    menu_route_game = FarmGame()
    menu_route_calls = []
    root_choices = iter([
        MenuItem(label="Build Mode", value="build"),
        MenuItem(label="Backpack", value="backpack"),
        MenuItem(label="Farm & Home", value="farm"),
        MenuItem(label="People", value="people"),
        MenuItem(label="Adventure", value="adventure"),
        MenuItem(label="Journal", value="journal"),
        MenuItem(label="System", value="system"),
        MenuItem(label="Close", value=None),
    ])
    menu_route_game.vertical_panel_select = lambda *args, **kwargs: next(root_choices)
    for method_name, marker in [
        ("show_place_item_menu", "build"),
        ("show_backpack_menu", "backpack"),
        ("show_farm_home_menu", "farm"),
        ("show_people_menu", "people"),
        ("show_combat_status_menu", "adventure"),
        ("show_journal_codex_menu", "journal"),
        ("show_system_menu", "system"),
    ]:
        setattr(
            menu_route_game,
            method_name,
            lambda marker=marker: menu_route_calls.append(marker) or farmstead_main.MENU_BACK,
        )
    menu_route_game.show_inventory()
    assert menu_route_calls == ["build", "backpack", "farm", "people", "adventure", "journal", "system"]

    backpack_route_game = FarmGame()
    backpack_calls = []
    backpack_choices = iter([
        MenuItem(label="Carried goods", value="goods"),
        MenuItem(label="Food", value="food"),
        MenuItem(label="Storage", value="storage"),
        MenuItem(label="Back", value=farmstead_main.MENU_BACK),
    ])
    backpack_route_game.vertical_panel_select = lambda *args, **kwargs: next(backpack_choices)
    backpack_route_game.show_carried_goods_menu = lambda: backpack_calls.append("goods") or farmstead_main.MENU_BACK
    backpack_route_game.show_food_menu = lambda: backpack_calls.append("food") or farmstead_main.MENU_BACK
    backpack_route_game.show_player_storage_index = lambda: backpack_calls.append("storage") or farmstead_main.MENU_BACK
    assert backpack_route_game.show_backpack_menu() == farmstead_main.MENU_BACK
    assert backpack_calls == ["goods", "food", "storage"]

    farm_route_game = FarmGame()
    farm_route_calls = []
    farm_choices = iter([
        MenuItem(label="Build Mode", value="build"),
        MenuItem(label="Tools", value="tools"),
        MenuItem(label="Automation", value="automation"),
        MenuItem(label="Crafting", value="crafting"),
        MenuItem(label="Cooking", value="cooking"),
        MenuItem(label="Land Claims", value="claims"),
        MenuItem(label="Back", value=farmstead_main.MENU_BACK),
    ])
    farm_route_game.vertical_panel_select = lambda *args, **kwargs: next(farm_choices)
    for method_name, marker in [
        ("show_place_item_menu", "build"),
        ("show_tool_status", "tools"),
        ("show_automation_report_menu", "automation"),
        ("show_crafting_menu", "crafting"),
        ("show_cooking_menu", "cooking"),
        ("show_land_claims_menu", "claims"),
    ]:
        setattr(
            farm_route_game,
            method_name,
            lambda *args, marker=marker, **kwargs: farm_route_calls.append(marker) or farmstead_main.MENU_BACK,
        )
    assert farm_route_game.show_farm_home_menu() == farmstead_main.MENU_BACK
    assert farm_route_calls == ["build", "tools", "automation", "crafting", "cooking", "claims"]

    people_route_game = FarmGame()
    people_route_calls = []
    people_route_views = []
    people_choices = iter([
        MenuItem(label="Relationships", value="relationships"),
        MenuItem(label="Family", value="family"),
        MenuItem(label="Followers & Helpers", value="followers"),
        MenuItem(label="Companion roster", value="companions"),
        MenuItem(label="Back", value=farmstead_main.MENU_BACK),
    ])
    people_route_game.vertical_panel_select = lambda *args, **kwargs: next(people_choices)
    people_route_game.vertical_panel_view = lambda title, *args, **kwargs: people_route_views.append(title)
    people_route_game.show_travel_follower_menu = lambda: people_route_calls.append("followers") or farmstead_main.MENU_BACK
    people_route_game.show_party_menu = lambda: people_route_calls.append("companions") or farmstead_main.MENU_BACK
    assert people_route_game.show_people_menu() == farmstead_main.MENU_BACK
    assert people_route_views == ["Relationships", "Family"]
    assert people_route_calls == ["followers", "companions"]

    journal_route_game = FarmGame()
    journal_route_calls = []
    journal_route_views = []
    journal_choices = iter([
        MenuItem(label="Today", value="today"),
        MenuItem(label="Quests", value="quests"),
        MenuItem(label="Calendar & Birthdays", value="calendar"),
        MenuItem(label="Progress Goals", value="progress"),
        MenuItem(label="Records & Discoveries", value="records"),
        MenuItem(label="Back", value=farmstead_main.MENU_BACK),
    ])
    journal_route_game.vertical_panel_select = lambda *args, **kwargs: next(journal_choices)
    journal_route_game.vertical_panel_view = lambda title, *args, **kwargs: journal_route_views.append(title)
    journal_route_game.show_unified_quest_log_menu = lambda: journal_route_calls.append("quests") or farmstead_main.MENU_BACK
    journal_route_game.show_journal_calendar_menu = lambda: journal_route_calls.append("calendar") or farmstead_main.MENU_BACK
    journal_route_game.show_journal_records_menu = lambda: journal_route_calls.append("records") or farmstead_main.MENU_BACK
    assert journal_route_game.show_journal_codex_menu() == farmstead_main.MENU_BACK
    assert journal_route_views == ["Today", "Progress Goals"]
    assert journal_route_calls == ["quests", "calendar", "records"]

    system_route_game = FarmGame()
    system_route_calls = []
    system_choices = iter([
        MenuItem(label="Save Manager", value="save"),
        MenuItem(label="Settings", value="settings"),
        MenuItem(label="Tutorials", value="tutorials"),
        MenuItem(label="Full Help", value="help"),
        MenuItem(label="Back", value=farmstead_main.MENU_BACK),
    ])
    system_route_game.vertical_panel_select = lambda *args, **kwargs: next(system_choices)
    for method_name, marker in [
        ("show_save_manager", "save"),
        ("show_settings_menu", "settings"),
        ("tutorial_menu", "tutorials"),
        ("show_help", "help"),
    ]:
        setattr(
            system_route_game,
            method_name,
            lambda marker=marker: system_route_calls.append(marker) or farmstead_main.MENU_BACK,
        )
    assert system_route_game.show_system_menu() == farmstead_main.MENU_BACK
    assert system_route_calls == ["save", "settings", "tutorials", "help"]
    settings_ui_game = FarmGame()
    settings_ui_labels = []
    settings_ui_game.vertical_panel_select = (
        lambda _title, items, *args, **kwargs: (
            settings_ui_labels.extend(item.label for item in items)
            or MenuItem(label="Back", value=farmstead_main.MENU_BACK)
        )
    )
    assert settings_ui_game.show_settings_menu() == farmstead_main.MENU_BACK
    assert "Mortality mode" in settings_ui_labels

    adventure_route_game = FarmGame()
    adventure_route_calls = []
    adventure_route_views = []
    adventure_choices = iter([
        MenuItem(label="Combat status", value="view"),
        MenuItem(label="Battle party", value="party"),
        MenuItem(label="Missions", value="missions"),
        MenuItem(label="Skills", value="training"),
        MenuItem(label="Loadout", value="loadout"),
        MenuItem(label="Bestiary", value="bestiary"),
        MenuItem(label="Battle reports", value="report"),
        MenuItem(label="Back", value=farmstead_main.MENU_BACK),
    ])
    adventure_route_game.repair_combat_equipment = lambda announce=True: []
    adventure_route_game.vertical_panel_select = lambda *args, **kwargs: next(adventure_choices)
    adventure_route_game.vertical_panel_view = lambda title, *args, **kwargs: adventure_route_views.append(title)
    for method_name, marker in [
        ("show_party_menu", "party"),
        ("show_combat_mission_menu", "missions"),
        ("show_combat_training_menu", "training"),
        ("show_combat_loadout_menu", "loadout"),
        ("show_combat_bestiary_menu", "bestiary"),
        ("show_last_combat_report", "report"),
    ]:
        setattr(
            adventure_route_game,
            method_name,
            lambda marker=marker: adventure_route_calls.append(marker) or farmstead_main.MENU_BACK,
        )
    assert adventure_route_game.show_combat_status_menu() == farmstead_main.MENU_BACK
    assert adventure_route_views == ["Combat Status"]
    assert adventure_route_calls == ["party", "missions", "training", "loadout", "bestiary", "report"]

    gear_game = FarmGame()
    gear_game.autosave_with_message = lambda message: gear_game.set_message(message)
    gear_game.state.inventory["Iron Sword"] = 1
    assert "Iron Sword" in gear_game.owned_combat_equipment_names("weapon")
    assert gear_game.equip_combat_item("weapon", "Iron Sword")
    equipped_profile = build_player_combat_profile(gear_game.state)
    assert equipped_profile["weapon"] == "Iron Sword"
    assert equipped_profile["attack"] == gear_game.state.combat_attack + 5
    gear_game.state.equipped_weapon = "Missing"
    gear_game.state.equipped_armor = "Missing"
    gear_game.state.equipped_accessory = "Missing"
    repair_lines = gear_game.repair_combat_equipment()
    assert repair_lines
    assert gear_game.state.equipped_weapon == DEFAULT_COMBAT_WEAPON
    assert gear_game.state.equipped_armor == DEFAULT_COMBAT_ARMOR
    assert gear_game.state.equipped_accessory == DEFAULT_COMBAT_ACCESSORY

    forge_game = FarmGame()
    forge_game.autosave_with_message = lambda message: forge_game.set_message(message)
    forge_game.state.money = 999999
    forge_game.state.inventory["Copper Bar"] = 2
    forge_game.state.inventory["Coal"] = 1
    forge_game.state.inventory["Fiber"] = 20
    forge_game.state.inventory["Bat Guano"] = 2
    forge_game.state.inventory["Quartz"] = 2
    forge_game.state.inventory["Wood"] = 15
    forge_game.state.inventory["Soft Fiber"] = 3
    before_money = forge_game.state.money
    assert forge_game.combat_gear_unlock_available("Copper Sword")
    assert forge_game.can_purchase_combat_gear("Copper Sword")
    assert forge_game.purchase_combat_gear("Copper Sword", equip_now=True)
    assert forge_game.state.inventory["Copper Sword"] == 1
    assert forge_game.state.inventory["Copper Bar"] == 0
    assert forge_game.state.inventory["Coal"] == 0
    assert forge_game.state.money == before_money - 800
    assert "Copper Sword" in forge_game.owned_combat_equipment_names("weapon")
    forged_profile = build_player_combat_profile(forge_game.state)
    assert forged_profile["weapon"] == "Copper Sword"
    assert forged_profile["attack"] == forge_game.state.combat_attack + 3
    assert not forge_game.can_purchase_combat_gear("Copper Sword")
    assert forge_game.can_purchase_combat_gear("Padded Jacket")
    assert forge_game.purchase_combat_gear("Padded Jacket", equip_now=True)
    padded_profile = build_player_combat_profile(forge_game.state)
    assert padded_profile["armor"] == "Padded Jacket"
    assert padded_profile["defense"] == forge_game.state.combat_defense + 2
    assert padded_profile["max_hp"] == forge_game.state.combat_max_hp + 5
    assert forge_game.can_purchase_combat_gear("Fang Spear")
    assert forge_game.purchase_combat_gear("Fang Spear", equip_now=True)
    fang_profile = build_player_combat_profile(forge_game.state)
    assert fang_profile["weapon"] == "Fang Spear"

    # Procedural equipment keeps a persistent stat identity while travelling
    # through the ordinary backpack, containers, shipping, and loadout systems.
    generated_game = FarmGame()
    generated_game.autosave_with_message = lambda message: generated_game.set_message(message)
    generated_name = random_loot.generate_random_equipment(
        generated_game.state,
        "smoke:dungeon:chest:1",
        item_level=14,
        quality_bonus=2,
        slot="weapon",
    )
    generated_record = generated_game.state.generated_equipment[generated_name]
    assert generated_record["slot"] == "weapon"
    assert generated_record["rarity"] in random_loot.GENERATED_EQUIPMENT_RARITIES
    assert 1 <= generated_record["range_min"] <= generated_record["range_max"] <= 6
    assert generated_game.container_item_sell_price(generated_name) == generated_record["value"]
    assert any("Equipment:" in line for line in generated_game.container_item_detail_lines(generated_name))
    generated_game.state.inventory[generated_name] = 1
    assert generated_name in generated_game.owned_combat_equipment_names("weapon")
    assert generated_game.equip_combat_item("weapon", generated_name)
    generated_profile = build_player_combat_profile(generated_game.state)
    assert generated_profile["weapon"] == generated_name
    assert generated_profile["weapon_range_min"] == generated_record["range_min"]
    assert generated_profile["weapon_range_max"] == generated_record["range_max"]
    assert generated_profile["attack"] == generated_game.state.combat_attack + generated_record["attack"]
    generated_game.shipping_bin_target = lambda: (1, 1)
    assert not generated_game.ship_inventory_item(generated_name)
    assert generated_game.state.inventory[generated_name] == 1
    generated_storage = generated_game.create_container_record(
        "generated-gear-storage", 1, 1, "crate",
        take_policy="player", allow_deposit=True, contents={},
    )
    assert generated_game.deposit_all_into_container(generated_storage) >= 0
    assert generated_game.state.inventory[generated_name] == 1
    assert generated_name not in generated_storage["contents"]
    generated_round_trip = state.GameState(
        generated_equipment=dict(generated_game.state.generated_equipment),
        equipped_weapon=generated_name,
        inventory={generated_name: 1},
    )
    assert generated_round_trip.equipped_weapon == generated_name
    assert generated_name in generated_round_trip.generated_equipment

    # The blacksmith workshop applies real combat bonuses, previews deterministic
    # reforges, escalates costs, and salvages only unequipped generated gear.
    workshop_game = FarmGame()
    workshop_game.autosave_with_message = lambda message: workshop_game.set_message(message)
    for item_name in list(workshop_game.state.inventory):
        workshop_game.state.inventory[item_name] = 0
    workshop_name = random_loot.generate_random_equipment(
        workshop_game.state, "workshop-smoke", item_level=12, slot="weapon"
    )
    workshop_record = workshop_game.state.generated_equipment[workshop_name]
    workshop_record.update({
        "rarity": "Rare",
        "attack": 5,
        "defense": 1,
        "max_hp": 0,
        "max_focus": 0,
        "affixes": ["Keen", "Guarded"],
    })
    workshop_game.state.inventory[workshop_name] = 1
    workshop_game.state.inventory["Copper Bar"] = 3
    workshop_game.state.inventory["Coal"] = 5
    workshop_game.state.inventory["Crystal Shard"] = 5
    workshop_game.state.inventory[random_loot.WORKSHOP_SALVAGE_ITEM] = 8
    workshop_game.state.money = 50_000
    assert workshop_game.equip_combat_item("weapon", workshop_name)
    workshop_attack_before = build_player_combat_profile(workshop_game.state)["attack"]
    workshop_value_before = workshop_game.container_item_sell_price(workshop_name)
    first_upgrade_cost = random_loot.equipment_enhancement_cost(workshop_game.state, workshop_name)
    money_before_upgrade = workshop_game.state.money
    copper_before_upgrade = workshop_game.state.inventory["Copper Bar"]
    assert random_loot.can_afford_workshop_cost(workshop_game.state, first_upgrade_cost)
    assert random_loot.enhance_equipment(workshop_game.state, workshop_name)
    assert random_loot.equipment_enhancement_level(workshop_game.state, workshop_name) == 1
    assert build_player_combat_profile(workshop_game.state)["attack"] == workshop_attack_before + 1
    assert workshop_game.container_item_sell_price(workshop_name) > workshop_value_before
    assert workshop_game.state.money == money_before_upgrade - first_upgrade_cost[0]
    assert workshop_game.state.inventory["Copper Bar"] == copper_before_upgrade - 1
    assert any("Enhancement: +1" in line for line in workshop_game.container_item_detail_lines(workshop_name))

    old_affix = "Keen"
    replacement_affix = random_loot.preview_reforge_affix(
        workshop_game.state, workshop_name, old_affix
    )
    assert replacement_affix and replacement_affix not in workshop_record["affixes"]
    reforge_cost_before = random_loot.equipment_reforge_cost(workshop_game.state, workshop_name)
    stats_before_reforge = {
        stat: int(workshop_record.get(stat, 0) or 0)
        for stat in ["attack", "defense", "max_hp", "max_focus"]
    }
    assert random_loot.reforge_generated_equipment(
        workshop_game.state, workshop_name, old_affix
    ) == replacement_affix
    assert old_affix not in workshop_record["affixes"]
    assert replacement_affix in workshop_record["affixes"]
    for stat in stats_before_reforge:
        expected = (
            stats_before_reforge[stat]
            - int(random_loot.AFFIX_BONUS_BY_LABEL[old_affix].get(stat, 0))
            + int(random_loot.AFFIX_BONUS_BY_LABEL[replacement_affix].get(stat, 0))
        )
        assert int(workshop_record.get(stat, 0) or 0) == max(0, expected)
    assert random_loot.equipment_reforge_cost(workshop_game.state, workshop_name)[0] > reforge_cost_before[0]
    assert not random_loot.salvage_generated_equipment(workshop_game.state, workshop_name)
    workshop_game.state.equipped_weapon = DEFAULT_COMBAT_WEAPON
    expected_salvage = random_loot.generated_equipment_salvage_yield(
        workshop_game.state, workshop_name
    )
    recovered_salvage = random_loot.salvage_generated_equipment(
        workshop_game.state, workshop_name
    )
    assert recovered_salvage == expected_salvage
    assert workshop_game.state.inventory[workshop_name] == 0
    assert workshop_game.state.inventory[random_loot.WORKSHOP_SALVAGE_ITEM] >= expected_salvage[random_loot.WORKSHOP_SALVAGE_ITEM]

    workshop_round_trip = state.GameState(
        generated_equipment=dict(workshop_game.state.generated_equipment),
        equipment_workshop=dict(workshop_game.state.equipment_workshop),
        inventory={workshop_name: 1},
    )
    assert random_loot.equipment_enhancement_level(workshop_round_trip, workshop_name) == 1
    assert workshop_round_trip.equipment_workshop[workshop_name]["reforge_count"] == 1

    static_workshop_state = state.GameState(
        money=5000,
        inventory={"Copper Bar": 2, "Coal": 2},
    )
    static_attack_before = build_player_combat_profile(static_workshop_state)["attack"]
    assert random_loot.enhance_equipment(static_workshop_state, DEFAULT_COMBAT_WEAPON)
    assert build_player_combat_profile(static_workshop_state)["attack"] == static_attack_before + 1
    assert random_loot.equipment_enhancement_cap(static_workshop_state, DEFAULT_COMBAT_WEAPON) == 3

    workshop_menu_game = FarmGame()
    workshop_menu_game.state.location = "BlacksmithInterior"
    workshop_menu_game.ensure_current_town_service_unlocked = lambda: True
    workshop_menu_game.is_town_building_unlocked = lambda _building: True
    workshop_menu_labels = []
    workshop_menu_game.vertical_panel_select = lambda _title, items, *args, **kwargs: (
        workshop_menu_labels.extend(item.label for item in items)
        or MenuItem(label="Leave", value="leave")
    )
    workshop_menu_game.blacksmith_menu()
    assert "Gear Workshop" in workshop_menu_labels
    remote_workshop_game = FarmGame()
    remote_workshop_game.state.location = "Wilderness"
    remote_workshop_labels = []
    remote_workshop_game.vertical_panel_select = lambda _title, items, *args, **kwargs: (
        remote_workshop_labels.extend(item.label for item in items)
        or MenuItem(label="Leave", value="leave")
    )
    remote_workshop_game.blacksmith_menu(service_override=True)
    assert "Gear Workshop" in remote_workshop_labels

    deterministic_state_a = state.GameState()
    deterministic_state_b = state.GameState()
    deterministic_name_a = random_loot.generate_random_equipment(
        deterministic_state_a, "same-source", item_level=9, slot="armor"
    )
    deterministic_name_b = random_loot.generate_random_equipment(
        deterministic_state_b, "same-source", item_level=9, slot="armor"
    )
    assert deterministic_name_a == deterministic_name_b
    assert deterministic_state_a.generated_equipment[deterministic_name_a] == deterministic_state_b.generated_equipment[deterministic_name_b]
    idempotent_name = random_loot.generate_random_equipment(
        deterministic_state_a, "same-source", item_level=9, slot="armor"
    )
    assert idempotent_name == deterministic_name_a
    collision_rng_seed = 77881
    collision_name_a = random_loot.generate_random_equipment(
        deterministic_state_a, "collision-source-a", item_level=9, slot="armor",
        rng=random.Random(collision_rng_seed),
    )
    collision_name = random_loot.generate_random_equipment(
        deterministic_state_a, "collision-source-b", item_level=9, slot="armor",
        rng=random.Random(collision_rng_seed),
    )
    assert collision_name_a != deterministic_name_a or collision_name != deterministic_name_a
    assert collision_name != deterministic_name_a
    assert collision_name == f"{collision_name_a} 2"

    reward_state_a = state.GameState()
    reward_state_b = state.GameState()
    reward_a = random_loot.add_random_reward_items(
        reward_state_a, {"Ruin Scrap": 1}, "reward-smoke", 18,
        gear_chance=1.0, consumable_chance=1.0, valuable_chance=1.0,
        quality_bonus=3,
    )
    reward_b = random_loot.add_random_reward_items(
        reward_state_b, {"Ruin Scrap": 1}, "reward-smoke", 18,
        gear_chance=1.0, consumable_chance=1.0, valuable_chance=1.0,
        quality_bonus=3,
    )
    assert reward_a == reward_b
    assert len(reward_state_a.generated_equipment) == 1
    reward_gear_name = next(iter(reward_state_a.generated_equipment))
    assert reward_a[reward_gear_name] == 1
    assert any(name in reward_a for name in random_loot.RANDOM_CONSUMABLES)
    assert any(name in reward_a for name in random_loot.RANDOM_VALUABLES)
    assert fang_profile["weapon_range_max"] == 2

    gated_gear_game = FarmGame()
    assert not gated_gear_game.combat_gear_unlock_available("Iron Sword")
    gated_gear_game.state.inventory["Iron Ore"] = 1
    assert gated_gear_game.combat_gear_unlock_available("Iron Sword")
    assert not gated_gear_game.combat_gear_unlock_available("Relic Halberd")
    gated_gear_game.state.inventory["Ruin Scrap"] = 1
    assert gated_gear_game.combat_gear_unlock_available("Relic Halberd")

    gear_loot_money, gear_loot_items = translated_battle_loot({
        "Spider Silk": 2,
        "Clockwork Carapace": 1,
        "Relic Arrowhead": 1,
        "Crystal Fang": 1,
        "Coin": 3,
    })
    assert gear_loot_money == 15
    assert gear_loot_items["Soft Fiber"] == 2
    assert gear_loot_items["Ruin Scrap"] == 1
    assert gear_loot_items["Relic Fragment"] == 1
    assert gear_loot_items["Crystal Shard"] == 1

    tactical_gear_game = FarmGame()
    tactical_gear_game.save = lambda *args, **kwargs: True
    tactical_gear_game.autosave_with_message = lambda message: tactical_gear_game.set_message(message)
    tactical_gear_game.state.money = 999999
    tactical_gear_game.state.inventory["Crystal Shard"] = 1
    tactical_gear_game.state.inventory["Soft Fiber"] = 1
    crystal_cost = tactical_gear_game.tactical_gear_cost("weapon", "Crystal Skewer")
    assert tactical_gear_game.can_afford_tactical_cost(crystal_cost)
    assert tactical_gear_game.equip_tactical_gear("player", "weapon", "Crystal Skewer")
    assert tactical_gear_game.combat_progress_for_key("player")["equipped_gear"]["weapon"] == "Crystal Skewer"

    restore_game = FarmGame()
    restore_game.autosave_with_message = lambda message: restore_game.set_message(message)
    restore_project = data.TOWN_RESTORATION_PROJECT_DATA["restore_blacksmith"]
    for item_name, qty in restore_project["items"].items():
        restore_game.state.inventory[item_name] = int(qty)
    before_money = restore_game.state.money
    before_wood = restore_game.state.inventory["Wood"]
    assert restore_game.complete_town_restoration_project("restore_blacksmith")
    assert restore_game.is_town_building_unlocked("blacksmith")
    assert "restore_blacksmith" in restore_game.state.completed_town_restoration_project_ids
    assert restore_game.state.money == before_money
    assert restore_game.state.inventory["Wood"] == before_wood
    assert restore_game.town_restoration_project_status("restore_blacksmith") == "Completed"
    assert restore_game.state.town_development_stage == 0

    mine_game = FarmGame()
    mine_game.autosave_with_message = lambda message: mine_game.set_message(message)
    mine_game.state.player_name = "Avery"
    mine_game.state.player_color = "Green"
    mine_game.state.location = "Mine"
    mine_game.state.mine_floor = 1
    mine_game.mine_map = mine_game.get_mine_floor_map(1)
    mine_enemies = mine_game.get_mine_enemies(1)
    assert mine_enemies, "mine floor did not spawn enemies"
    mine_enemy = mine_enemies[0]
    mine_game.mine_enemies = {"1": [mine_enemy]}
    assert mine_game.mine_enemy_at(int(mine_enemy["x"]), int(mine_enemy["y"])) is mine_enemy
    assert "Combat" in mine_game.target_action_hint(int(mine_enemy["x"]), int(mine_enemy["y"]))
    assert not mine_game.is_mine_floor_cleared(1)
    assert not mine_game.mine_floor_stairs_available(1)
    assert "sealed" in mine_game.locked_mine_down_stairs_message(1)
    request = mine_battle_request_for_enemy(1, mine_enemy, mine_game.state)
    mine_profile = build_player_combat_profile(mine_game.state)
    assert request.return_context["farm_player"]["name"] == "Avery"
    assert request.return_context["farm_player"]["attack"] == mine_profile["attack"]
    assert request.return_context["farm_player"]["defense"] == mine_profile["defense"]
    assert request.return_context["farm_player"]["weapon"] == mine_profile["weapon"]
    assert request.party_ids == ["Rook"]
    mine_variants = {
        (
            variant_request.map_name,
            tuple(sorted(variant_request.enemy_counts.items())),
        )
        for index in range(8)
        for variant_request in [
            mine_battle_request_for_enemy(
                1,
                {"id": f"mine:1:{index}:Slime", "species": "Slime"},
                mine_game.state,
            )
        ]
    }
    assert len(mine_variants) >= 3
    assert len({map_name for map_name, _counts in mine_variants}) >= 2
    assert all(sum(amount for _name, amount in counts) == 1 for _map_name, counts in mine_variants)

    directed_state = state.GameState(location="Mine")
    directed_profiles = [
        {"id": "ally-1", "name": "Ally One", "battle_id": "Ally One"},
        {"id": "ally-2", "name": "Ally Two", "battle_id": "Ally Two"},
        {"id": "ally-3", "name": "Ally Three", "battle_id": "Ally Three"},
    ]
    directed_variants = [
        mine_battle_request_for_enemy(
            20,
            {"id": f"mine:20:{index}:Rockback", "species": "Rockback"},
            directed_state,
            directed_profiles,
            3,
        )
        for index in range(8)
    ]
    assert len({variant.map_name for variant in directed_variants}) >= 2
    assert len({variant.return_context["encounter_signature"] for variant in directed_variants}) >= 3
    for variant in directed_variants:
        context = variant.return_context
        assert context["encounter_briefing"]
        assert context["encounter_danger"] in {"Favorable", "Even", "Dangerous", "Severe"}
        assert int(context["encounter_threat"]) <= int(context["encounter_budget"]) * 1.18
        assert len({mine_enemy_role(name) for name in variant.enemy_counts}) >= 2

    director_cases = [
        (1, "Slime"),
        (6, "Sporeling"),
        (12, "Rockback"),
        (20, "Wisp"),
        (28, "Ember Imp"),
        (36, "Crystal Spider"),
    ]
    for floor, primary in director_cases:
        for party_size in range(1, 5):
            profiles = directed_profiles[: max(0, party_size - 1)]
            variant = mine_battle_request_for_enemy(
                floor,
                {"id": f"mine:{floor}:0:{primary}", "species": primary},
                state.GameState(location="Mine"),
                profiles,
                party_size,
            )
            context = variant.return_context
            assert int(context["encounter_threat"]) <= int(context["encounter_budget"]) * 1.18
            control_count = sum(
                amount
                for name, amount in variant.enemy_counts.items()
                if mine_enemy_role(name) in {"controller", "blighter"}
            )
            if party_size == 1:
                assert control_count <= 1

    miniboss_request = mine_battle_request_for_enemy(
        20,
        {"id": "mine:20:0:Rockback", "species": "Rockback"},
        directed_state,
    )
    assert miniboss_request.return_context["encounter_special"] == "miniboss"
    assert any(name.startswith("Elite ") for name in miniboss_request.enemy_counts)

    repeated_enemy = {"id": "mine:20:7:Rockback", "species": "Rockback"}
    first_directed = mine_battle_request_for_enemy(20, repeated_enemy, directed_state, directed_profiles, 3)
    directed_state.mine_recent_combat_maps = [first_directed.map_name]
    directed_state.mine_recent_combat_signatures = [first_directed.return_context["encounter_signature"]]
    second_directed = mine_battle_request_for_enemy(20, repeated_enemy, directed_state, directed_profiles, 3)
    assert second_directed.map_name != first_directed.map_name
    assert second_directed.return_context["encounter_signature"] != first_directed.return_context["encounter_signature"]
    configured_battle = configure_game_from_request(BattleGame(), request)
    assert configured_battle.active_party_names_list() == ["Avery"]
    assert "Rook" not in configured_battle.active_party_names_list()
    assert "Mira" not in configured_battle.active_party_names_list()
    assert configured_battle.selected_hero.name == "Avery"
    assert configured_battle.selected_hero.max_hp == mine_game.state.combat_max_hp
    assert "Map" not in configured_battle.command_menu_options()
    assert request.return_context["encounter_briefing"] in configured_battle.messages
    configured_battle.start_map_menu()
    assert configured_battle.state == "command"
    for enemy_name in ["Crystal Spider", "Cave Lynx", "Gloomcap", "Clockwork Beetle", "Relic Archer"]:
        assert configured_battle.enemy_by_name(enemy_name), f"missing tactical enemy {enemy_name}"
        assert farmstead_main.mine_enemy_profile(enemy_name)["description"]

    party_mine_game = FarmGame()
    party_mine_game.autosave_with_message = lambda message: party_mine_game.set_message(message)
    party_mine_game.save = lambda quiet=True, path=None: True
    party_mine_game.state.player_name = "Avery"
    party_mine_game.state.location = "Mine"
    party_mine_game.state.mine_floor = 1
    party_mine_game.state.deepest_mine_floor = 3
    party_mine_game.mine_map = party_mine_game.get_mine_floor_map(1)
    party_mine_game.unlock_town_building("blacksmith")
    party_mine_game.state.town_npc_relationships["brom_smith"] = 60
    party_mine_game.state.town_npc_dialogue_counts["brom_smith"] = 3
    assert party_mine_game.refresh_unlocked_party_members() == ["brom_smith"]
    assert party_mine_game.add_party_member("brom_smith")
    assert party_mine_game.set_party_tactic("Support")
    assert party_mine_game.set_party_member_manual_control("brom_smith", True)
    party_enemy = {"id": "party:enemy", "species": "Slime", "floor": 1, "x": 11, "y": 10, "alert": False, "defeated": False}
    party_mine_game.mine_enemies = {"1": [party_enemy]}
    party_request = mine_battle_request_for_enemy(
        1,
        party_enemy,
        party_mine_game.state,
        party_mine_game.active_farmstead_companion_profiles(),
        party_mine_game.party_total_limit(),
    )
    assert party_request.party_ids == ["Rook", "Brom"]
    assert party_request.return_context["farm_party_limit"] == 4
    assert party_request.return_context["farm_party_tactic"] == "Support"
    assert party_request.return_context["farm_companions"][0]["name"] == "Brom"
    assert party_request.return_context["farm_companions"][0]["manual_control"] is True
    solo_scaled = mine_battle_request_for_enemy(20, {"id": "solo-scale", "species": "Rockback"}, party_mine_game.state)
    party_scaled = mine_battle_request_for_enemy(
        20,
        {"id": "party-scale", "species": "Rockback"},
        party_mine_game.state,
        companion_profiles=[
            {"id": "brom_smith", "name": "Brom", "battle_id": "Brom"},
            {"id": "mira_seed", "name": "Mira", "battle_id": "Mira"},
            {"id": "dr_ivy", "name": "Dr. Ivy", "battle_id": "Dr. Ivy"},
        ],
        party_limit=4,
    )
    assert len(party_scaled.party_ids) == 4
    assert len(party_scaled.requested_enemy_names()) > len(solo_scaled.requested_enemy_names())
    configured_party_battle = configure_game_from_request(BattleGame(), party_request)
    assert configured_party_battle.active_party_names_list() == ["Avery", "Brom"]
    assert configured_party_battle.follower_tactic == "Support"
    assert "Mira" not in configured_party_battle.active_party_names_list()
    assert "Aria" not in configured_party_battle.active_party_names_list()
    brom_unit = next(hero for hero in configured_party_battle.heroes if hero.name == "Brom")
    assert not brom_unit.ai_controlled
    assert "Brom" in configured_party_battle.manual_companion_names
    assert brom_unit.glyph == "@"
    assert brom_unit.max_hp >= int(FARMSTEAD_COMPANION_DATA["brom_smith"]["max_hp"])
    before_brom_relationship = party_mine_game.town_npc_relationship("brom_smith")
    party_mine_game.apply_mine_battle_result(
        party_enemy,
        SimpleNamespace(
            outcome="victory",
            defeated_enemies=["Slime"],
            loot={},
            party_status={"Avery": {"hp": 30, "max_hp": 34, "mp": 8, "max_mp": 8, "inventory": {}}},
            return_context={"farm_player_items": {}},
        ),
    )
    assert party_mine_game.town_npc_relationship("brom_smith") == before_brom_relationship + 2
    assert party_mine_game.grant_party_relationship_after_battle("victory") == []
    assert party_mine_game.town_npc_relationship("brom_smith") == before_brom_relationship + 2

    knockout_win_game = FarmGame()
    knockout_win_game.autosave_with_message = lambda message: knockout_win_game.set_message(message)
    knockout_win_game.state.player_name = "Avery"
    knockout_win_game.state.location = "Mine"
    knockout_win_game.state.mine_floor = 1
    knockout_win_game.mine_map = knockout_win_game.get_mine_floor_map(1)
    knockout_enemy = {
        "id": "knockout:enemy",
        "species": "Slime",
        "floor": 1,
        "x": 11,
        "y": 10,
        "alert": False,
        "defeated": False,
    }
    knockout_win_game.mine_enemies = {"1": [knockout_enemy]}
    knockout_win_game.apply_mine_battle_result(
        knockout_enemy,
        SimpleNamespace(
            outcome="victory",
            defeated_enemies=["Slime"],
            loot={},
            party_status={
                "Avery": {"hp": 0, "max_hp": 34, "mp": 0, "max_mp": 8, "inventory": {}},
                "Brom": {"hp": 12, "max_hp": 48, "mp": 3, "max_mp": 8, "inventory": {}},
            },
            return_context={"farm_player_items": {}},
        ),
    )
    assert knockout_win_game.state.combat_current_hp == 1
    assert "HP 1/" in knockout_win_game.state.message

    party_mine_game.apply_tactical_progression_result(
        SimpleNamespace(
            outcome="victory",
            defeated_enemies=["Elite Slime"],
            loot={"Coin": 2},
            party_progression={
                "Avery": {"class": "Ranger", "subclass": "Storm", "skill_points": 4, "level": 1, "xp": 0},
                "Brom": {"class": "Guardian", "subclass": "Earth", "skill_points": 3, "level": 2, "xp": 6},
            },
            return_context={
                "farm_progression_keys": {"Avery": "player", "Brom": "brom_smith"},
                "combat_campaign_inventory": {"Coin": 22, "Shard": 3},
                "combat_item_loadout_bonus": {"Potion": 1},
                "combat_report_lines": ["Result: Victory", "Defeated: Slime"],
                "combat_mission": True,
                "mission_id": "smoke-mission",
            },
        )
    )
    assert party_mine_game.state.combat_party_progress["player"]["class"] == "Ranger"
    assert party_mine_game.state.combat_party_progress["brom_smith"]["class"] == "Guardian"
    assert party_mine_game.state.combat_campaign_inventory == {}
    assert party_mine_game.state.combat_item_loadout_bonus["Potion"] == 1
    assert party_mine_game.state.combat_bestiary_defeated["Slime"] >= 1
    assert "smoke-mission" in party_mine_game.state.completed_combat_mission_ids
    assert party_mine_game.state.last_combat_report[0] == "Result: Victory"
    assert "Farm rewards: $10" in party_mine_game.state.last_combat_report
    assert party_mine_game.combat_loot_for_result(SimpleNamespace(
        loot={"Coin": 1},
        return_context={
            "farm_combat_campaign_inventory": {"Coin": 5},
            "combat_campaign_inventory": {"Coin": 9, "Shard": 1},
        },
    )) == {"Coin": 4, "Shard": 1}
    player_progress = party_mine_game.combat_progress_for_key("player")
    player_progress["skill_points"] = 9
    party_mine_game.save_combat_progress_for_key("player", player_progress, autosave=False)
    assert party_mine_game.set_tactical_member_class("player", "Ranger")
    assert party_mine_game.train_tactical_skill("player", "Snare Trap")
    assert "Snare Trap" in party_mine_game.state.combat_party_progress["player"]["class_unlocks"]["Ranger"]
    mission_request = party_mine_game.mission_preset_request(farmstead_main.tactical_mission_builtin_presets()[0])
    assert mission_request.source == "ascii_farmstead"
    assert mission_request.return_context["combat_mission"] is True
    configured_mission = configure_game_from_request(BattleGame(), mission_request)
    assert configured_mission.campaign_inventory["Coin"] == 0
    assert configured_mission.item_loadout_bonus["Potion"] == 1
    assert "Brom" in configured_mission.active_party_names_list()
    assert configured_mission.party_progress["Brom"]["class"] == "Guardian"

    tactical_cost_game = FarmGame()
    tactical_cost_game.autosave_with_message = lambda message: tactical_cost_game.set_message(message)
    tactical_cost_game.state.money = 20
    tactical_cost_game.state.inventory["Cave Herbs"] = 1
    snack_option = tactical_cost_game.tactical_supply_options()[0]
    assert tactical_cost_game.tactical_cost_text(snack_option["cost"]) == "$20, 1 Cave Herbs"
    assert tactical_cost_game.can_afford_tactical_cost(snack_option["cost"])
    assert tactical_cost_game.apply_tactical_supply_option(snack_option)
    assert tactical_cost_game.state.money == 0
    assert tactical_cost_game.state.inventory["Cave Herbs"] == 0
    assert tactical_cost_game.state.combat_item_loadout_bonus["Potion"] == 1

    deep_reward_game = FarmGame()
    deep_reward_game.state.mine_floor = 20
    deep_result = SimpleNamespace(
        outcome="victory",
        defeated_enemies=["Wisp", "Rockback"],
        loot={"Coin": 2},
        return_context={"floor": 20, "farm_player_items": {}},
    )
    deep_loot = deep_reward_game.combat_loot_for_result(deep_result)
    assert deep_loot["Coin"] == 2
    assert deep_loot["Crystal Shard"] >= 1
    assert deep_reward_game.combat_time_cost_minutes(deep_result, "mine") >= 20

    mission_impact_game = FarmGame()
    mission_impact_game.autosave_with_message = lambda message: mission_impact_game.set_message(message)
    mission_preset = farmstead_main.tactical_mission_builtin_presets()[0]
    mission_id = mission_impact_game.tactical_slug(str(mission_preset["name"]), "combat-mission")
    before_mira = mission_impact_game.town_npc_relationship("mira_seed")
    mission_impact_game.apply_combat_mission_result(
        SimpleNamespace(
            outcome="victory",
            defeated_enemies=["Slime"],
            loot={"Coin": 1},
            party_status={},
            mission_id=mission_id,
            mission_name=str(mission_preset["name"]),
            return_context={
                "farm_player_items": {},
                "combat_mission": True,
                "mission_id": mission_id,
                "mission_name": str(mission_preset["name"]),
                "farm_combat_depth": 1,
            },
        )
    )
    assert mission_id in mission_impact_game.state.completed_combat_mission_ids
    assert mission_impact_game.town_npc_relationship("mira_seed") >= before_mira + 4
    assert "Victory: Farm Pest Trouble" in mission_impact_game.state.message
    assert "min" in mission_impact_game.state.message

    before_money = mine_game.state.money
    before_hour, before_minute = mine_game.state.hour, mine_game.state.minute
    before_level = mine_game.state.combat_level
    mine_game.apply_mine_battle_result(
        mine_enemy,
        SimpleNamespace(
            outcome="victory",
            defeated_enemies=[mine_enemy["species"]],
            loot={"Coin": 2, "Gel": 1},
            party_status={"Avery": {"hp": 21, "max_hp": 34, "mp": 5, "max_mp": 8, "inventory": {}}},
            return_context={**request.return_context, "farm_player_items": {}},
        ),
    )
    assert mine_game.state.mine_combat_victories == 1
    assert mine_game.state.money == before_money + 10 + 28
    assert (mine_game.state.hour, mine_game.state.minute) != (before_hour, before_minute)
    assert "Victory:" in mine_game.state.message and "min" in mine_game.state.message
    assert mine_game.state.inventory.get("Sap", 0) >= 1
    assert mine_game.state.combat_current_hp == 21
    assert mine_game.state.natural_health_recovery_delay_minutes == 30
    assert mine_game.state.natural_health_recovery_minutes == 0
    assert mine_game.state.combat_exp > 0 or mine_game.state.combat_level > before_level
    assert mine_game.state.mine_recent_combat_maps[-1] == request.map_name
    assert mine_game.state.mine_recent_combat_signatures[-1] == request.return_context["encounter_signature"]
    assert mine_game.mine_enemy_at(int(mine_enemy["x"]), int(mine_enemy["y"])) is None
    assert mine_game.is_mine_floor_cleared(1)
    assert mine_game.mine_floor_stairs_available(1)
    assert mine_game.get_mine_enemies(1, create=False) == []
    assert state.mine_floor_clear_reward_claimed(mine_game.state, 1)

    level_game = FarmGame()
    starting_stamina_cap = level_game.max_stamina()
    starting_stamina = level_game.state.stamina
    level_game.state.combat_exp = level_game.state.combat_exp_to_next - 1
    gained, level_lines = grant_combat_exp(level_game.state, 5)
    assert gained == 5
    assert level_game.state.combat_level == 2
    assert level_game.max_stamina() == starting_stamina_cap + 5
    assert level_game.state.stamina == starting_stamina + 5
    assert level_lines and "Level 2" in level_lines[0]
    assert "Maximum stamina +5" in level_lines[0]

    recovery_game = FarmGame()
    recovery_profile = build_player_combat_profile(recovery_game.state)
    recovery_game.state.stamina = recovery_game.max_stamina() - 20
    recovery_game.state.combat_current_hp = int(recovery_profile["max_hp"]) - 10
    starting_recovery_stamina = recovery_game.state.stamina
    starting_recovery_hp = recovery_game.state.combat_current_hp
    recovery_game.record_player_damage()
    recovery_game.advance_time(29)
    assert recovery_game.state.stamina == starting_recovery_stamina + 5
    assert recovery_game.state.combat_current_hp == starting_recovery_hp
    assert recovery_game.state.natural_health_recovery_delay_minutes == 1
    recovery_game.advance_time(1)
    assert recovery_game.state.stamina == starting_recovery_stamina + 6
    assert recovery_game.state.combat_current_hp == starting_recovery_hp
    assert recovery_game.state.natural_health_recovery_delay_minutes == 0
    recovery_game.advance_time(19)
    assert recovery_game.state.combat_current_hp == starting_recovery_hp
    recovery_game.advance_time(1)
    assert recovery_game.state.combat_current_hp == starting_recovery_hp + 1
    recovery_game.advance_time(20, allow_natural_recovery=False)
    assert recovery_game.state.combat_current_hp == starting_recovery_hp + 1
    recovery_game.advance_time(40)
    assert recovery_game.state.combat_current_hp == starting_recovery_hp + 3

    item_game = FarmGame()
    item_game.autosave_with_message = lambda message: item_game.set_message(message)
    item_game.state.player_name = "Avery"
    item_game.state.location = "Mine"
    item_game.state.inventory["Field Snack"] = 2
    item_enemy = {"id": "item:enemy", "species": "Slime", "floor": 1, "x": 11, "y": 10, "alert": False, "defeated": False}
    item_game.mine_enemies = {"1": [item_enemy]}
    item_game.apply_mine_battle_result(
        item_enemy,
        SimpleNamespace(
            outcome="fled",
            defeated_enemies=[],
            loot={},
            party_status={"Avery": {"hp": 18, "max_hp": 34, "mp": 8, "max_mp": 8, "inventory": {"Field Snack": 1}}},
            return_context={"farm_player_items": {"Field Snack": 2}},
        ),
    )
    assert item_game.state.inventory["Field Snack"] == 1
    assert item_game.state.combat_current_hp == 18
    assert not item_game.is_mine_floor_cleared(1)
    assert item_game.get_mine_enemies(1, create=False)

    encounter_game = FarmGame()
    encounter_game.autosave_with_message = lambda message: encounter_game.set_message(message)
    encounter_game.state.player_name = "Robin"
    encounter_game.state.location = "Mine"
    encounter_game.state.mine_floor = 1
    encounter_game.mine_map = encounter_game.get_mine_floor_map(1)
    encounter_game.state.player_x = 10
    encounter_game.state.player_y = 10
    encounter_enemy = {"id": "smoke:enemy", "species": "Slime", "floor": 1, "x": 11, "y": 10, "alert": False, "defeated": False}
    encounter_game.mine_enemies = {"1": [encounter_enemy]}
    battle_requests = []
    original_run_mine_battle = farmstead_main.run_mine_battle
    try:
        farmstead_main.run_mine_battle = lambda request: (
            battle_requests.append(request)
            or SimpleNamespace(outcome="victory", defeated_enemies=["Slime"], loot={})
        )
        assert encounter_game.check_mine_enemy_engagement(reason="smoke")
    finally:
        farmstead_main.run_mine_battle = original_run_mine_battle
    assert battle_requests and battle_requests[0].source == "ascii_farmstead"
    assert battle_requests[0].return_context["farm_player"]["name"] == "Robin"
    assert encounter_game.state.mine_combat_victories == 1
    assert encounter_game.is_mine_floor_cleared(1)
    assert encounter_game.mine_floor_stairs_available(1)
    assert encounter_game.get_mine_enemies(1, create=False) == []

    claim_game = FarmGame()
    claim_game.autosave_with_message = lambda message: claim_game.set_message(message)
    claim_game.state.location = "Wilderness"
    claim_game.state.money = data.WILDERNESS_CLAIM_PRICE + 500
    claim_coords = None
    for cy in range(-8, 9):
        for cx in range(-8, 9):
            if (cx, cy) != (0, 0) and claim_game.is_claimable_wilderness_chunk(cx, cy):
                claim_coords = (cx, cy)
                break
        if claim_coords:
            break
    assert claim_coords is not None
    cx, cy = claim_coords
    claim_game.set_wilderness_chunk(cx, cy)
    marker = None
    for y, row in enumerate(claim_game.active_map()):
        for x, tile in enumerate(row):
            if tile == data.WILDERNESS_CLAIM_SYMBOL:
                marker = (x, y)
                break
        if marker:
            break
    assert marker is not None
    farm_type_id = claim_game.recommended_wilderness_claim_farm_type_id(cx, cy)
    preview_identity = claim_game.wilderness_claim_identity(cx, cy, farm_type_id)
    assert preview_identity["name"]
    assert preview_identity["deed_code"].startswith("LC-")
    assert claim_game.purchase_current_wilderness_claim(marker[0], marker[1], farm_type_id)
    claim_key = claim_game.wilderness_chunk_key(cx, cy)
    claim = claim_game.state.owned_wilderness_claims[claim_key]
    assert claim["name"] == preview_identity["name"]
    assert claim["deed_code"] == preview_identity["deed_code"]
    assert claim["landmark"]
    assert claim["identity"]
    assert "Survey note:" in claim_game.land_claim_detail_lines(claim_key, claim)
    assert "Design implication:" in claim_game.land_claim_identity_lines(claim_key, claim)

    stronghold_game = FarmGame()
    stronghold_game.autosave_with_message = lambda message: stronghold_game.set_message(message)
    stronghold_game.state.player_name = "Avery"
    stronghold_game.state.wilderness_seed = 24681357
    stronghold_coords = None

    def stronghold_has_expansion_land(cx, cy):
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            water_samples = sum(
                1
                for local_y in (4, 11, 19, 27, 34)
                for local_x in (6, 23, 43, 63, 79)
                if stronghold_game.wilderness_world_water_tile(
                    nx * 86 + local_x,
                    ny * 38 + local_y,
                )
            )
            if water_samples <= 15:
                return True
        return False

    for cy in range(-80, 81):
        for cx in range(-80, 81):
            if (
                stronghold_game.wilderness_chunk_has_stronghold(cx, cy)
                and not stronghold_game.wilderness_chunk_has_procedural_settlement(cx, cy)
                and stronghold_has_expansion_land(cx, cy)
            ):
                stronghold_coords = (cx, cy)
                break
        if stronghold_coords:
            break
    assert stronghold_coords is not None
    scx, scy = stronghold_coords
    assert not stronghold_game.is_claimable_wilderness_chunk(scx, scy)
    assert not stronghold_game.wilderness_chunk_has_dungeon_site(scx, scy)
    stronghold_game.state.location = "Wilderness"
    stronghold_game.set_wilderness_chunk(scx, scy)
    stronghold_map = stronghold_game.active_map()
    stronghold_marker = None
    for y, row in enumerate(stronghold_map):
        for x, tile in enumerate(row):
            if tile == "!":
                stronghold_marker = (x, y)
                break
        if stronghold_marker:
            break
    assert stronghold_marker is not None
    assert "stronghold" in stronghold_game.describe_tile(*stronghold_marker).lower()
    assert stronghold_game.get_wilderness_animals(scx, scy) == []
    stronghold_enemies = list(stronghold_game.get_wilderness_stronghold_enemies(scx, scy))
    assert stronghold_enemies
    assert any(enemy.get("boss") for enemy in stronghold_enemies)
    stronghold_enemy_bases = {"Bandit", "Shield Guard", "Wolf", "Burrower", "Rockback", "Thornback", "Sporeling", "Moss Haunt", "Ember Imp", "Ruin Bat", "Marsh Toad"}
    assert all(str(enemy.get("species", "")).replace("Elite ", "") in stronghold_enemy_bases for enemy in stronghold_enemies)
    assert {str(enemy.get("species", "")).replace("Elite ", "") for enemy in stronghold_enemies} <= set(BattleGame().enemy_roster_names())
    first_enemy = stronghold_enemies[0]
    assert "Combat" in stronghold_game.target_action_hint(int(first_enemy["x"]), int(first_enemy["y"]))
    stronghold_game.start_wilderness_stronghold_combat_encounter(first_enemy, reason="smoke")
    assert stronghold_game.wilderness_field_combat_active()
    assert first_enemy.get("field_combat_kind") == "stronghold"
    first_enemy = stronghold_game.ensure_dungeon_roguelike_enemy(first_enemy)
    field_hp_before = int(first_enemy["hp"])
    assert stronghold_game.dungeon_resolve_player_attack(
        first_enemy, attack_value=8, advance_turn=False,
    )
    assert int(first_enemy["hp"]) <= field_hp_before
    assert not hasattr(stronghold_game, "_active_tactical_battle")
    stronghold_game.end_wilderness_field_combat("Stronghold field-combat smoke complete.")
    assert not stronghold_game.wilderness_field_combat_active()
    money_before_stronghold = stronghold_game.state.money
    inventory_before_stronghold = sum(int(stronghold_game.state.inventory.get(item, 0)) for item in ["Wood", "Stone", "Fiber", "Coal", "Copper Ore", "Iron Ore", "Ruin Scrap"])
    for enemy in list(stronghold_game.get_wilderness_stronghold_enemies(scx, scy)):
        stronghold_game.apply_wilderness_stronghold_battle_result(
            enemy,
            SimpleNamespace(
                outcome="victory",
                defeated_enemies=[enemy["species"]],
                loot={},
                party_status={"Avery": {"hp": 30, "max_hp": 34, "mp": 8, "max_mp": 8, "inventory": {}}},
                return_context={"farm_player_items": {}},
            ),
        )
    stronghold_record = stronghold_game.wilderness_stronghold_record(scx, scy)
    assert stronghold_record["cleared"] is True
    assert stronghold_game.get_wilderness_stronghold_enemies(scx, scy, create=False) == []
    assert stronghold_game.state.wilderness_strongholds_cleared >= 1
    assert stronghold_game.state.money > money_before_stronghold
    inventory_after_stronghold = sum(int(stronghold_game.state.inventory.get(item, 0)) for item in ["Wood", "Stone", "Fiber", "Coal", "Copper Ore", "Iron Ore", "Ruin Scrap"])
    assert inventory_after_stronghold > inventory_before_stronghold
    assert "reclaimed" in stronghold_game.describe_tile(*stronghold_marker).lower()
    assert stronghold_game.wilderness_chunk_has_safe_waypoint(scx, scy)
    assert stronghold_game.overworld_chunk_preview_symbol(scx, scy) == "!"
    assert any("Reclaimed benefits" in line for line in stronghold_game.wilderness_stronghold_status_lines(scx, scy))
    can_found, found_reason = stronghold_game.can_found_town_at_reclaimed_stronghold(scx, scy)
    assert can_found, found_reason
    founded_plan = stronghold_game.found_town_at_reclaimed_stronghold("Avery's Watch", scx, scy, autosave=False)
    assert founded_plan is not None
    assert founded_plan is stronghold_game.wilderness_settlement_plan(scx, scy)
    assert founded_plan["name"] == "Avery's Watch"
    assert founded_plan["source"] == "reclaimed_stronghold"
    assert founded_plan["discovered"] is True
    assert founded_plan["status"] == "construction"
    assert founded_plan["construction_queue"]
    assert stronghold_record.get("founded_settlement_name") == "Avery's Watch"
    assert stronghold_record.get("founded_settlement_key") == stronghold_game.wilderness_stronghold_key(scx, scy)
    assert any("Town foundation" in line for line in stronghold_game.wilderness_stronghold_status_lines(scx, scy))
    assert any("Avery's Watch" in line for line in stronghold_game.wilderness_stronghold_status_lines(scx, scy))
    can_found_again, _reason = stronghold_game.can_found_town_at_reclaimed_stronghold(scx, scy)
    assert not can_found_again
    assert not stronghold_game.wilderness_settlement_validation(scx, scy, check_terrain=False)["errors"]
    assert any("Build flow" in line for line in stronghold_game.reclaimed_stronghold_town_overview_lines(scx, scy))
    board_pos = stronghold_game.ensure_reclaimed_stronghold_build_board(scx, scy)
    assert board_pos is not None
    board_x, board_y = board_pos
    assert stronghold_game.active_map()[board_y][board_x] == "n"
    assert stronghold_game.reclaimed_stronghold_build_board_at(board_x, board_y)
    assert "build board" in stronghold_game.describe_tile(board_x, board_y).lower()
    assert "build board" in stronghold_game.interaction_hint(board_x, board_y).lower()
    assert "Road" in [item["name"] for item in stronghold_game.reclaimed_stronghold_build_catalog().values()]
    stronghold_game.state.money = max(stronghold_game.state.money, 10000)

    stronghold_build_rejections = {}

    def first_valid_stronghold_build_position(item_id):
        stronghold_build_rejections.clear()
        grid = stronghold_game.active_map()
        for yy in range(2, len(grid) - 2):
            for xx in range(2, len(grid[0]) - 2):
                ok, reason = stronghold_game.can_place_reclaimed_stronghold_build_item(item_id, xx, yy, scx, scy)
                if ok:
                    return xx, yy
                stronghold_build_rejections[reason] = stronghold_build_rejections.get(reason, 0) + 1
        return None

    # Reserve a valid building footprint before adding one-tile decorations;
    # the first valid road tile can otherwise consume the only approach to a
    # large footprint on especially rugged stronghold maps.
    home_pos = first_valid_stronghold_build_position("building:home")
    assert home_pos is not None, stronghold_build_rejections
    money_before_home = stronghold_game.state.money
    assert stronghold_game.place_reclaimed_stronghold_build_item("building:home", home_pos[0], home_pos[1], scx, scy, autosave=False)
    assert stronghold_game.state.money == money_before_home - 850
    home_feature_id, home_feature = stronghold_game.reclaimed_stronghold_feature_at(home_pos[0], home_pos[1], scx, scy)
    assert home_feature_id.startswith("feature:")
    assert home_feature and home_feature["kind"] == "building"
    assert home_feature["name"] == "Settler Home"
    assert not stronghold_game.passable(home_pos[0], home_pos[1])
    assert "Settler Home" in stronghold_game.describe_tile(home_pos[0], home_pos[1])

    road_pos = first_valid_stronghold_build_position("road")
    assert road_pos is not None
    money_before_road = stronghold_game.state.money
    assert stronghold_game.place_reclaimed_stronghold_build_item("road", road_pos[0], road_pos[1], scx, scy, autosave=False)
    assert stronghold_game.state.money == money_before_road - 10
    assert stronghold_game.active_map()[road_pos[1]][road_pos[0]] == ":"
    assert stronghold_game.passable(*road_pos)
    road_feature_id, road_feature = stronghold_game.reclaimed_stronghold_feature_at(road_pos[0], road_pos[1], scx, scy)
    assert road_feature_id.startswith("road:")
    assert road_feature and road_feature["kind"] == "road"
    assert "Road" in stronghold_game.describe_tile(*road_pos)

    stronghold_game.state.money = max(stronghold_game.state.money, 10000)
    store_pos = first_valid_stronghold_build_position("building:general_store")
    assert store_pos is not None, stronghold_build_rejections
    assert stronghold_game.place_reclaimed_stronghold_build_item("building:general_store", store_pos[0], store_pos[1], scx, scy, autosave=False)
    population_plan = stronghold_game.reclaimed_stronghold_population_plan(scx, scy)
    assert population_plan is not None
    assert population_plan["source"] == "reclaimed_stronghold"
    assert any(str(building.get("type_id")) == "home" for building in population_plan["buildings"].values())
    assert any(str(building.get("type_id")) == "general_store" for building in population_plan["buildings"].values())
    population = stronghold_game.reconcile_reclaimed_stronghold_population(scx, scy)
    assert population is not None
    population_summary = stronghold_game.procedural_npc_builder().summary(population)
    assert population_summary["population"] >= 1
    assert population_summary["households"] >= 1
    assert population_summary["service_tags"]
    assert population_summary["average_job_skill"] > 0
    assert any(
        str(resident.get("home_building_id", "")).startswith("reclaimed_")
        for resident in population["residents"].values()
    )
    assert all(
        resident.get("job_profile", {}).get("title")
        for resident in population["residents"].values()
    )
    frontier = stronghold_game.founded_town_frontier_candidates(stronghold_record)
    assert frontier
    expansion_chunk = frontier[0]
    expansion_cost = stronghold_game.founded_town_expansion_cost(stronghold_record)
    stronghold_game.state.money = max(stronghold_game.state.money, expansion_cost + 5000)
    money_before_expansion = stronghold_game.state.money
    expansion_district = stronghold_game.expand_founded_town(
        expansion_chunk[0],
        expansion_chunk[1],
        "Market",
        scx,
        scy,
        autosave=False,
    )
    assert expansion_district is not None
    assert stronghold_game.state.money == money_before_expansion - expansion_cost
    assert stronghold_game.founded_town_root_context(*expansion_chunk)[0:2] == (scx, scy)
    assert stronghold_game.wilderness_settlement_plan(*expansion_chunk) is None
    assert stronghold_game.overworld_chunk_preview_symbol(*expansion_chunk) == procedural_towns.PROCEDURAL_TOWN_OVERWORLD_SYMBOL
    assert any(
        "Market District" in line
        for line in stronghold_game.overworld_chunk_detail_lines(*expansion_chunk)
    )
    expansion_map = stronghold_game.get_wilderness_chunk_map(*expansion_chunk)
    parent_chunk = (
        int(expansion_district["parent_chunk_x"]),
        int(expansion_district["parent_chunk_y"]),
    )
    dx = expansion_chunk[0] - parent_chunk[0]
    dy = expansion_chunk[1] - parent_chunk[1]
    if dx:
        edge_x = 0 if dx > 0 else len(expansion_map[0]) - 1
        assert expansion_map[19][edge_x] == ":"
    else:
        edge_y = 0 if dy > 0 else len(expansion_map) - 1
        assert expansion_map[edge_y][43] == ":"
    stronghold_game.set_wilderness_chunk(*expansion_chunk)
    district_board = stronghold_game.ensure_reclaimed_stronghold_build_board(
        *expansion_chunk
    )
    assert district_board is not None
    assert stronghold_game.reclaimed_stronghold_build_board_at(
        *district_board,
        *expansion_chunk,
    )
    assert "Market District" in stronghold_game.location_label()
    district_catalog = stronghold_game.reclaimed_stronghold_build_catalog(
        *expansion_chunk
    )
    assert district_catalog["building:market_stall"]["district_fit"] == "favored"
    assert district_catalog["building:market_stall"]["cost"] < district_catalog["building:market_stall"]["base_cost"]
    assert district_catalog["building:clinic"]["district_fit"] == "outside specialization"
    assert district_catalog["building:clinic"]["cost"] > district_catalog["building:clinic"]["base_cost"]

    def first_valid_district_build_position(item_id):
        grid = stronghold_game.active_map()
        for yy in range(2, len(grid) - 2):
            for xx in range(2, len(grid[0]) - 2):
                ok, _reason = stronghold_game.can_place_reclaimed_stronghold_build_item(
                    item_id,
                    xx,
                    yy,
                    expansion_chunk[0],
                    expansion_chunk[1],
                )
                if ok:
                    return xx, yy
        return None

    clinic_pos = first_valid_district_build_position("building:clinic")
    assert clinic_pos is not None
    assert stronghold_game.place_reclaimed_stronghold_build_item(
        "building:clinic",
        clinic_pos[0],
        clinic_pos[1],
        expansion_chunk[0],
        expansion_chunk[1],
        autosave=False,
    )
    municipality = stronghold_game.ensure_founded_town_municipality(
        stronghold_record
    )
    municipality["treasury"] = 1000
    first_market_pos = first_valid_district_build_position("building:market_stall")
    assert first_market_pos is not None
    money_before_subsidized_build = stronghold_game.state.money
    assert stronghold_game.place_reclaimed_stronghold_build_item(
        "building:market_stall",
        first_market_pos[0],
        first_market_pos[1],
        expansion_chunk[0],
        expansion_chunk[1],
        autosave=False,
    )
    first_market_feature = next(
        feature
        for feature in stronghold_game.reclaimed_stronghold_feature_records(
            stronghold_record,
            *expansion_chunk,
        ).values()
        if feature.get("type_id") == "market_stall"
    )
    assert int(first_market_feature["municipal_subsidy"]) > 0
    assert stronghold_game.state.money > (
        money_before_subsidized_build - int(first_market_feature["project_cost"])
    )
    second_market_pos = first_valid_district_build_position("building:market_stall")
    assert second_market_pos is not None
    assert stronghold_game.place_reclaimed_stronghold_build_item(
        "building:market_stall",
        second_market_pos[0],
        second_market_pos[1],
        expansion_chunk[0],
        expansion_chunk[1],
        autosave=False,
    )
    market_metrics = stronghold_game.founded_town_site_metrics(
        stronghold_record,
        expansion_district,
    )
    assert market_metrics["kind"] == "Market"
    assert market_metrics["label"] in {"Established", "Thriving"}
    assert not any(
        "Market Stall" in demand
        for demand in stronghold_game.founded_town_site_demands(
            stronghold_record,
            expansion_district,
        )
    )
    expanded_population_plan = stronghold_game.reclaimed_stronghold_population_plan(
        *expansion_chunk
    )
    assert expanded_population_plan is not None
    district_clinic = next(
        building
        for building in expanded_population_plan["buildings"].values()
        if building["type_id"] == "clinic"
        and (
            int(building["district_chunk_x"]),
            int(building["district_chunk_y"]),
        ) == expansion_chunk
    )
    assert district_clinic["district_maturity"] in {"Established", "Thriving"}
    revenue_week = stronghold_game.civic_date_ordinal() // 7
    municipality["last_revenue_week"] = revenue_week - 1
    treasury_before_revenue = int(municipality["treasury"])
    weekly_revenue = stronghold_game.process_founded_town_revenue(
        stronghold_record
    )
    assert weekly_revenue > 0
    assert int(municipality["treasury"]) == treasury_before_revenue + weekly_revenue
    assert any(
        "Favored construction costs 15% less" in line
        for line in stronghold_game.founded_town_site_status_lines(
            *expansion_chunk
        )
    )
    stronghold_game.state.hour = 12
    assert stronghold_game.enter_procedural_town_building(district_clinic)
    assert stronghold_game.exit_procedural_town_building()
    assert (
        stronghold_game.state.wilderness_chunk_x,
        stronghold_game.state.wilderness_chunk_y,
    ) == expansion_chunk
    expanded_overview = "\n".join(
        stronghold_game.reclaimed_stronghold_town_overview_lines(*expansion_chunk)
    )
    assert "Developed footprint: 2 chunk(s)" in expanded_overview
    assert "Town treasury: $" in expanded_overview
    assert "Market / Established" in expanded_overview or "Market / Thriving" in expanded_overview
    stronghold_game.set_wilderness_chunk(scx, scy)
    current_population_plan = stronghold_game.current_procedural_town_plan()
    assert current_population_plan is not None
    assert current_population_plan["source"] == "reclaimed_stronghold"
    stronghold_game.state.hour = 12
    stronghold_game.state.minute = 0
    stronghold_game.update_procedural_town_residents(force_reanchor=True)
    resident_lookup = stronghold_game.procedural_town_resident_position_lookup()
    assert resident_lookup
    resident_pos, visible_resident = next(iter(resident_lookup.items()))
    assert stronghold_game.procedural_town_resident_at(*resident_pos)["id"] == visible_resident["id"]
    assert "talk" in stronghold_game.interaction_hint(*resident_pos).lower()
    conversation = stronghold_game.procedural_settlement_conversation(
        scx,
        scy,
        str(visible_resident.get("id", "")),
        topic="chat",
        remember=True,
    )
    assert conversation and conversation.get("text")
    resident_report = stronghold_game.reclaimed_stronghold_population_report_lines(scx, scy)
    assert any("Population:" in line for line in resident_report)
    assert any("Residents:" in line for line in resident_report)
    assert any("Service coverage:" in line for line in resident_report)
    overlap_ok, overlap_reason = stronghold_game.can_place_reclaimed_stronghold_build_item("bench", home_pos[0], home_pos[1], scx, scy)
    assert not overlap_ok and "overlap" in overlap_reason
    marker_ok, marker_reason = stronghold_game.can_place_reclaimed_stronghold_build_item("building:home", stronghold_marker[0], stronghold_marker[1], scx, scy)
    assert not marker_ok and ("blocked" in marker_reason or "open" in marker_reason)
    assert any("Placed at stronghold" in line for line in stronghold_game.reclaimed_stronghold_town_overview_lines(scx, scy))
    first_project = str(founded_plan["construction_queue"][0])
    # This fixture deliberately supplies industrial quantities; give its test
    # backpack enough expansions so capacity rules do not obscure town logic.
    stronghold_game.state.backpack_upgrades = 100
    stronghold_game.ensure_container_state()
    stronghold_game.state.inventory.update({
        "Wood": 999,
        "Stone": 999,
        "Iron Bar": 999,
        "Cloth": 999,
        "Cave Herbs": 999,
        "Wildflower": 999,
        "Copper Bar": 999,
    })
    stronghold_game.state.money = max(stronghold_game.state.money, 5000)
    accepted = stronghold_game.contribute_to_wilderness_settlement(scx, scy, first_project, use_available=True)
    assert accepted["materials"] or accepted["money"]
    first_building = founded_plan["buildings"][first_project]
    assert stronghold_game.wilderness_town_builder().phase_funded(first_building)
    phase_before = int(first_building.get("phase_index", 0))
    stronghold_game.state.stamina = 100
    assert stronghold_game.work_on_reclaimed_stronghold_town(scx, scy, labor=999, minutes=5, stamina_cost=1)
    assert int(first_building.get("phase_index", 0)) > phase_before
    stronghold_game.state.stamina = 20
    stronghold_game.state.combat_current_hp = 5
    assert stronghold_game.rest_at_reclaimed_stronghold()
    assert stronghold_game.state.stamina > 20
    assert stronghold_game.state.combat_current_hp > 5
    assert stronghold_record.get("last_rest_day") == stronghold_game.errand_day_key()
    assert not stronghold_game.rest_at_reclaimed_stronghold()
    cache_before = sum(int(stronghold_game.state.inventory.get(item, 0)) for item in ["Wood", "Stone", "Fiber", "Coal", "Copper Ore", "Ruin Scrap", "Soft Fiber", "Marsh Reed"])
    assert stronghold_game.claim_reclaimed_stronghold_cache()
    cache_after = sum(int(stronghold_game.state.inventory.get(item, 0)) for item in ["Wood", "Stone", "Fiber", "Coal", "Copper Ore", "Ruin Scrap", "Soft Fiber", "Marsh Reed"])
    assert cache_after > cache_before
    assert stronghold_record.get("last_cache_week") == stronghold_game.stronghold_cache_week_key()
    assert not stronghold_game.claim_reclaimed_stronghold_cache()
    stronghold_game.state.overworld_return_chunk_x = scx
    stronghold_game.state.overworld_return_chunk_y = scy
    stronghold_game.state.overworld_cursor_chunk_x = scx + 2
    stronghold_game.state.overworld_cursor_chunk_y = scy
    stamina_cost, minutes_cost, waypoint_discount = stronghold_game.overworld_travel_costs()
    assert waypoint_discount is True
    assert stamina_cost == 2
    assert minutes_cost == 10

    wilderness_balance_game = FarmGame()
    wilderness_balance_game.state.wilderness_seed = 24681357
    wilderness_balance_game.wilderness_maps = {}
    sample_wilderness_coords = [
        (0, 0),
        (1, 0),
        (-1, 2),
        (3, 4),
        (4, -4),
        (-4, -4),
        (6, 2),
        (-6, 3),
        (2, -7),
    ]

    def count_grid_symbol(grid, symbol):
        return sum(row.count(symbol) for row in grid)

    for sample_cx, sample_cy in sample_wilderness_coords:
        sample_grid = wilderness_balance_game.make_wilderness_chunk(sample_cx, sample_cy)
        assert wilderness_balance_game.wilderness_chunk_economy_score(sample_grid) <= wilderness_balance_game.wilderness_valuable_spawn_budget(sample_cx, sample_cy)
        for capped_symbol in ["Y", "u", "Z", "M", "O", "e", "N", "z", "m", "k"]:
            assert count_grid_symbol(sample_grid, capped_symbol) <= wilderness_balance_game.wilderness_symbol_spawn_cap(capped_symbol, sample_cx, sample_cy)
    origin_grid = wilderness_balance_game.make_wilderness_chunk(0, 0)
    assert count_grid_symbol(origin_grid, "R") >= 1
    assert count_grid_symbol(origin_grid, "K") >= 1
    assert count_grid_symbol(origin_grid, "Q") >= 1
    assert count_grid_symbol(origin_grid, "Y") <= wilderness_balance_game.wilderness_symbol_spawn_cap("Y", 0, 0)
    assert count_grid_symbol(origin_grid, "u") <= wilderness_balance_game.wilderness_symbol_spawn_cap("u", 0, 0)

    # Wilderness regions provide stable identity and useful, bounded fieldwork.
    region_a = wilderness_balance_game.wilderness_region_profile(0, 0)
    same_region_point = wilderness_balance_game.wilderness_region_chunks(0, 0)[-1]
    region_b = wilderness_balance_game.wilderness_region_profile(*same_region_point)
    assert region_a["key"] == region_b["key"]
    assert region_a["name"] == region_b["name"]
    assert len(region_a["traits"]) == 2
    legacy_region_key = f"region:{region_a['key']}"
    wilderness_balance_game.state.wilderness_poi_state = {
        legacy_region_key: {"kind": "region", "project": {"completed": True, "supplied": {}, "labor": 0}}
    }
    migrated_project = wilderness_balance_game.wilderness_region_project(0, 0)
    assert migrated_project["level"] == 1
    assert migrated_project["active_tier"] == 0
    wilderness_balance_game.state.wilderness_poi_state = {}
    field_coords = None
    field_pos = None
    for field_cy in range(-5, 6):
        for field_cx in range(-5, 6):
            field_grid = wilderness_balance_game.make_wilderness_chunk(field_cx, field_cy)
            positions = [(x, y) for y, row in enumerate(field_grid) for x, tile in enumerate(row) if tile == "E"]
            if positions:
                field_coords, field_pos = (field_cx, field_cy), positions[0]
                break
        if field_coords:
            break
    assert field_coords is not None and field_pos is not None
    wilderness_balance_game.autosave_with_message = lambda message: wilderness_balance_game.set_message(message)
    wilderness_balance_game.state.location = "Wilderness"
    wilderness_balance_game.wilderness_maps = {}
    wilderness_balance_game.set_wilderness_chunk(*field_coords)
    field_map = wilderness_balance_game.active_map()
    field_positions = [(x, y) for y, row in enumerate(field_map) for x, tile in enumerate(row) if tile == "E"]
    assert field_positions
    fx, fy = field_positions[0]
    assert "fieldwork" in wilderness_balance_game.describe_tile(fx, fy).lower()
    wilderness_balance_game.state.stamina = 50
    money_before_fieldwork = wilderness_balance_game.state.money
    assert wilderness_balance_game.perform_wilderness_fieldwork(fx, fy)
    assert wilderness_balance_game.state.money > money_before_fieldwork
    assert not wilderness_balance_game.perform_wilderness_fieldwork(fx, fy)
    mastery_count, mastery_label = wilderness_balance_game.wilderness_region_mastery(*field_coords)
    assert mastery_count == 1 and mastery_label == "Surveyed"
    project_profile = wilderness_balance_game.wilderness_region_project_profile(*field_coords)
    for project_item, project_need in project_profile["materials"].items():
        wilderness_balance_game.state.inventory[project_item] = int(project_need)
    money_before_project = wilderness_balance_game.state.money
    assert wilderness_balance_game.contribute_wilderness_region_project(*field_coords)
    assert not wilderness_balance_game.wilderness_region_project_complete(*field_coords)
    for _shift in range(int(project_profile["labor"])):
        assert wilderness_balance_game.work_on_wilderness_region_project(*field_coords, fieldwork=True)
    assert wilderness_balance_game.wilderness_region_project_complete(*field_coords)
    assert wilderness_balance_game.state.money >= money_before_project + 250
    assert wilderness_balance_game.wilderness_chunk_has_safe_waypoint(*field_coords)
    wilderness_balance_game.apply_wilderness_region_project_to_grid(field_map, *field_coords)
    assert any("H" in row for row in field_map)
    project_lines = wilderness_balance_game.wilderness_region_project_lines(*field_coords)
    assert any("Development: level 1/3" in line for line in project_lines)

    # Completed regional routes grow into field stations and living preserves.
    for expected_level in [2, 3]:
        assert wilderness_balance_game.begin_wilderness_region_project_expansion(*field_coords)
        tier_profile = wilderness_balance_game.wilderness_region_project_tier_profile(*field_coords, expected_level)
        for project_item, project_need in tier_profile["materials"].items():
            wilderness_balance_game.state.inventory[project_item] = int(project_need)
        assert wilderness_balance_game.contribute_wilderness_region_project(*field_coords)
        for _shift in range(int(tier_profile["labor"])):
            assert wilderness_balance_game.work_on_wilderness_region_project(*field_coords, fieldwork=True)
        assert wilderness_balance_game.wilderness_region_project_level(*field_coords) == expected_level
    assert wilderness_balance_game.wilderness_region_project_maxed(*field_coords)
    wilderness_balance_game.apply_wilderness_region_project_to_grid(field_map, *field_coords)
    assert any("Q" in row for row in field_map)
    assert any("K" in row for row in field_map)
    wilderness_balance_game.state.stamina = 50
    money_before_maintenance = wilderness_balance_game.state.money
    assert wilderness_balance_game.maintain_wilderness_region_preserve(*field_coords)
    assert wilderness_balance_game.state.money == money_before_maintenance + 100
    assert not wilderness_balance_game.maintain_wilderness_region_preserve(*field_coords)
    assert wilderness_balance_game.wilderness_region_project(*field_coords)["maintenance_rounds"] == 1
    initiative = wilderness_balance_game.wilderness_seasonal_initiative_profile(*field_coords)
    assert wilderness_balance_game.state.season in initiative["name"]
    money_before_initiative = wilderness_balance_game.state.money
    assert wilderness_balance_game.undertake_wilderness_seasonal_initiative(*field_coords)
    assert wilderness_balance_game.state.money >= money_before_initiative + 150
    assert not wilderness_balance_game.undertake_wilderness_seasonal_initiative(*field_coords)
    assert wilderness_balance_game.wilderness_region_project(*field_coords)["seasonal_cycles"] == 1
    phenomenon_profile = wilderness_balance_game.wilderness_phenomenon_profile(*field_coords)
    assert phenomenon_profile["name"] and phenomenon_profile["story"]
    money_before_phenomenon = wilderness_balance_game.state.money
    assert wilderness_balance_game.resolve_wilderness_phenomenon(fx, fy, "study")
    assert wilderness_balance_game.state.money > money_before_phenomenon
    assert not wilderness_balance_game.resolve_wilderness_phenomenon(fx, fy, "study")
    phenomenon_lines = wilderness_balance_game.wilderness_phenomenon_lines(fx, fy)
    assert any("Resolved by:" in line for line in phenomenon_lines)
    expedition_offer = wilderness_balance_game.wilderness_expedition_offer(*field_coords)
    assert (expedition_offer["target_x"], expedition_offer["target_y"]) != field_coords
    assert wilderness_balance_game.accept_wilderness_expedition(*field_coords)
    assert not wilderness_balance_game.accept_wilderness_expedition(*field_coords)
    expedition_target = (int(expedition_offer["target_x"]), int(expedition_offer["target_y"]))
    assert wilderness_balance_game.overworld_chunk_preview_symbol(*expedition_target) == "?"
    assert any("Target chunk:" in line for line in wilderness_balance_game.wilderness_expedition_lines(*field_coords))
    wilderness_balance_game.set_wilderness_chunk(*expedition_target)
    expedition_sites = [(x, y) for y, row in enumerate(wilderness_balance_game.active_map()) for x, tile in enumerate(row) if tile == "E"]
    assert expedition_sites
    ex, ey = expedition_sites[0]
    wilderness_balance_game.state.stamina = 50
    money_before_expedition = wilderness_balance_game.state.money
    assert not wilderness_balance_game.complete_wilderness_expedition(ex, ey)
    objective_positions = wilderness_balance_game.wilderness_expedition_objective_positions()
    assert len(objective_positions) == 3
    wilderness_balance_game.prepare_wilderness_runtime_overlays()
    camp_position = wilderness_balance_game.wilderness_expedition_camp_position()
    assert camp_position != (-1, -1) and camp_position not in objective_positions
    assert wilderness_balance_game.wilderness_expedition_camp_visual_at(*camp_position)
    assert not wilderness_balance_game.passable(*camp_position)
    assert wilderness_balance_game.is_interactable_tile(*camp_position)
    assert "ranger camp" in wilderness_balance_game.interaction_hint(*camp_position).lower()
    assert "expedition camp" in wilderness_balance_game.describe_tile(*camp_position).lower()
    wilderness_balance_game.state.stamina = 20
    assert wilderness_balance_game.rest_at_wilderness_expedition_camp()
    assert wilderness_balance_game.state.stamina > 20
    assert not wilderness_balance_game.rest_at_wilderness_expedition_camp()
    camp_snacks_before = int(wilderness_balance_game.state.inventory.get("Field Snack", 0))
    assert wilderness_balance_game.claim_wilderness_expedition_camp_supplies()
    assert wilderness_balance_game.state.inventory["Field Snack"] == camp_snacks_before + 1
    assert not wilderness_balance_game.claim_wilderness_expedition_camp_supplies()
    first_objective = wilderness_balance_game.wilderness_expedition_objective_at(*objective_positions[0])
    assert first_objective["index"] == 1 and not first_objective["surveyed"]
    assert first_objective["kind"] in {"track", "repair", "deliver", "clues", "summit", "survey"}
    active_expedition = wilderness_balance_game.active_wilderness_expedition_for_chunk(*expedition_target)
    original_objective_kind = active_expedition.get("objective_kind", "survey")
    objective_symbols = {}
    for objective_kind in ("track", "repair", "deliver", "clues", "summit", "survey"):
        active_expedition["objective_kind"] = objective_kind
        varied_objective = wilderness_balance_game.wilderness_expedition_objective_at(*objective_positions[0])
        objective_symbols[objective_kind] = varied_objective["symbol"]
        assert varied_objective["action"]
    assert len(set(objective_symbols.values())) >= 5
    active_expedition["objective_kind"] = original_objective_kind
    if active_expedition.get("objective_kind") == "repair":
        wilderness_balance_game.state.inventory["Wood"] = max(3, int(wilderness_balance_game.state.inventory.get("Wood", 0)))
    elif active_expedition.get("objective_kind") == "deliver":
        wilderness_balance_game.state.inventory["Fiber"] = max(3, int(wilderness_balance_game.state.inventory.get("Fiber", 0)))
    assert "survey marker" in wilderness_balance_game.describe_tile(*objective_positions[0]).lower()
    assert wilderness_balance_game.is_interactable_tile(*objective_positions[0])
    assert "survey expedition point" in wilderness_balance_game.interaction_hint(*objective_positions[0]).lower()
    for objective_position in objective_positions:
        assert wilderness_balance_game.survey_wilderness_expedition_objective(*objective_position)
    assert not wilderness_balance_game.survey_wilderness_expedition_objective(*objective_positions[0])
    assert wilderness_balance_game.wilderness_expedition_objective_at(*objective_positions[0])["surveyed"]
    assert any("Physical survey points: 3/3" in line for line in wilderness_balance_game.wilderness_expedition_lines(*expedition_target))
    assert wilderness_balance_game.complete_wilderness_expedition(ex, ey)
    assert wilderness_balance_game.state.money > money_before_expedition
    assert not wilderness_balance_game.complete_wilderness_expedition(ex, ey)
    completed_expeditions, expedition_rank = wilderness_balance_game.wilderness_expedition_rank(*expedition_target)
    assert completed_expeditions == 1 and expedition_rank == "Scout"
    expedition_benefits = wilderness_balance_game.wilderness_expedition_rank_benefits(*expedition_target)
    assert expedition_benefits["rank"] == "Scout" and expedition_benefits["stamina_discount"] == 0
    assert not wilderness_balance_game.accept_wilderness_expedition(*expedition_target)
    assert wilderness_balance_game.overworld_chunk_preview_symbol(*expedition_target) != "?"
    event_profile = wilderness_balance_game.wilderness_weekly_event_profile(*expedition_target)
    event_material = str(event_profile["material"])
    wilderness_balance_game.state.inventory[event_material] = max(2, int(wilderness_balance_game.state.inventory.get(event_material, 0)))
    vitality_before_event, _vitality_label = wilderness_balance_game.wilderness_region_vitality(*expedition_target)
    assert wilderness_balance_game.resolve_wilderness_weekly_event(*expedition_target, "respond")
    vitality_after_event, vitality_label = wilderness_balance_game.wilderness_region_vitality(*expedition_target)
    assert vitality_after_event == vitality_before_event + 5
    assert vitality_label in {"Recovering", "Stable", "Flourishing", "Legendary"}
    assert not wilderness_balance_game.resolve_wilderness_weekly_event(*expedition_target, "observe")
    event_lines = wilderness_balance_game.wilderness_weekly_event_lines(*expedition_target)
    assert any("complete" in line.lower() for line in event_lines)
    region_record = wilderness_balance_game.wilderness_region_record(*expedition_target)
    assert region_record["event_history"][-1]["name"] == event_profile["name"]
    region_record["vitality_points"] = 100
    assert wilderness_balance_game.wilderness_region_vitality(*expedition_target) == (100, "Legendary")
    assert wilderness_balance_game.wilderness_region_vitality_benefits(*expedition_target)["yield"] == 2
    wilderness_balance_game.apply_wilderness_vitality_consequences_to_grid(wilderness_balance_game.active_map(), *expedition_target)
    consequence_positions = {tile: next(((x, y) for y, row in enumerate(wilderness_balance_game.active_map()) for x, value in enumerate(row) if value == tile), None) for tile in ("v", "g", "i")}
    assert all(consequence_positions.values())
    wilderness_balance_game.state.stamina = 50
    for symbol, consequence_kind in (("v", "refuge"), ("g", "staffed_site"), ("i", "excursion")):
        position = consequence_positions[symbol]
        assert wilderness_balance_game.wilderness_vitality_consequence_at(*position) == consequence_kind
        assert not wilderness_balance_game.passable(*position)
        assert wilderness_balance_game.is_interactable_tile(*position)
        assert wilderness_balance_game.use_wilderness_vitality_consequence(consequence_kind)
        assert not wilderness_balance_game.use_wilderness_vitality_consequence(consequence_kind)
    wilderness_balance_game.prepare_wilderness_runtime_overlays()
    event_visuals = wilderness_balance_game.wilderness_event_visual_lookup()
    assert event_visuals
    (visual_x, visual_y), visual_data = next(iter(event_visuals.items()))
    assert visual_data["event"] == event_profile["name"]
    assert event_profile["name"] in wilderness_balance_game.describe_tile(visual_x, visual_y)
    wilderness_balance_game.state.hour = 12
    wilderness_balance_game.state.minute = 0
    wilderness_balance_game.state.day = 1
    specialist_schedule = wilderness_balance_game.wilderness_specialist_schedule(*expedition_target)
    specialist_chunk = (int(specialist_schedule["chunk_x"]), int(specialist_schedule["chunk_y"]))
    assert specialist_schedule["presence"] == "wilderness"
    wilderness_balance_game.set_wilderness_chunk(*specialist_chunk)
    travelers = wilderness_balance_game.get_wilderness_travelers()
    assert travelers
    traveler = next(current for current in travelers if current.get("scheduled_specialist"))
    assert traveler.get("recurring") and traveler.get("home_name") and traveler.get("residence")
    recurring_record = wilderness_balance_game.recurring_wilderness_traveler_record(*expedition_target)
    assert traveler["name"] == recurring_record["name"]
    other_region_chunk = next(
        chunk
        for chunk in wilderness_balance_game.wilderness_region_chunks(*expedition_target)
        if chunk != specialist_chunk
        and not wilderness_balance_game.procedural_town_plan(*chunk)
        and not wilderness_balance_game.wilderness_chunk_has_stronghold(*chunk)
    )
    assert not any(
        current.get("scheduled_specialist")
        for current in wilderness_balance_game.generate_wilderness_travelers(*other_region_chunk)
    )
    traveler_x, traveler_y = int(traveler["x"]), int(traveler["y"])
    assert wilderness_balance_game.wilderness_traveler_at(traveler_x, traveler_y) is traveler
    assert wilderness_balance_game.passable(traveler_x, traveler_y)
    assert traveler["name"] in wilderness_balance_game.describe_tile(traveler_x, traveler_y)
    assert "talk" in wilderness_balance_game.interaction_hint(traveler_x, traveler_y).lower()
    traveler_lookup = wilderness_balance_game.frame_actor_position_lookups(len(wilderness_balance_game.active_map()[0]), len(wilderness_balance_game.active_map()))["wilderness_travelers"]
    assert traveler_lookup[(traveler_x, traveler_y)] is traveler
    traveler_menu_item = wilderness_balance_game._wilderness_menu_item(
        "talk", "Talk", "Hear what this traveler has noticed about the region."
    )
    assert traveler_menu_item.label == "Talk"
    assert traveler_menu_item.value == "talk"
    assert traveler_menu_item.enabled is True
    assert traveler_menu_item.hint.startswith("Hear what")
    traveler_menu_items = []
    traveler_conversations = []
    original_vertical_panel_select = wilderness_balance_game.vertical_panel_select
    original_vertical_panel_view = wilderness_balance_game.vertical_panel_view
    original_unified_conversation = wilderness_balance_game.run_unified_npc_conversation

    def select_traveler_talk(_title, items, *_args, **_kwargs):
        traveler_menu_items.extend(items)
        for preferred in ("talk", "work", "leave"):
            selected = next((item for item in items if item.value == preferred), None)
            if selected:
                return selected
        return None

    wilderness_balance_game.vertical_panel_select = select_traveler_talk
    wilderness_balance_game.vertical_panel_view = lambda *args, **kwargs: None
    wilderness_balance_game.run_unified_npc_conversation = lambda actor, **kwargs: (
        traveler_conversations.append((actor, kwargs)),
        {"completed": True, "transcript": [{"phase": "main subject"}], "topics": []},
    )[-1]
    menu_traveler = dict(traveler)
    menu_traveler["recurring"] = False
    wilderness_balance_game.show_wilderness_traveler(menu_traveler)
    wilderness_balance_game.vertical_panel_select = original_vertical_panel_select
    wilderness_balance_game.vertical_panel_view = original_vertical_panel_view
    wilderness_balance_game.run_unified_npc_conversation = original_unified_conversation
    assert [item.label for item in traveler_menu_items[:2]] == ["Talk", "Join regional patrol"]
    assert traveler_conversations and traveler_conversations[0][1]["kind"] == "traveler"
    wilderness_balance_game.state.stamina = 50
    assert wilderness_balance_game.talk_to_recurring_wilderness_traveler(traveler)
    assert not wilderness_balance_game.talk_to_recurring_wilderness_traveler(traveler)
    assert wilderness_balance_game.patrol_with_wilderness_traveler(traveler)
    assert not wilderness_balance_game.patrol_with_wilderness_traveler(traveler)
    assert recurring_record["bond"] == 3
    assert wilderness_balance_game.complete_recurring_wilderness_traveler_assignment(traveler)
    second_story = wilderness_balance_game.recurring_wilderness_traveler_assignment(traveler)
    wilderness_balance_game.state.inventory[second_story["item"]] = int(second_story["qty"])
    assert wilderness_balance_game.complete_recurring_wilderness_traveler_assignment(traveler)
    recurring_record["bond"] = 8
    third_story = wilderness_balance_game.recurring_wilderness_traveler_assignment(traveler)
    wilderness_balance_game.state.inventory[third_story["item"]] = int(third_story["qty"])
    wilderness_balance_game.state.stamina = 50
    assert wilderness_balance_game.complete_recurring_wilderness_traveler_assignment(traveler)
    assert recurring_record["story_stage"] == 3 and recurring_record["established_route"]
    assert len(recurring_record["memories"]) == 3
    assert not wilderness_balance_game.complete_recurring_wilderness_traveler_assignment(traveler)
    specialist_topic_lines = {
        topic: " ".join(wilderness_balance_game.wilderness_traveler_lines(traveler, topic))
        for topic in ("work", "route", "region", "event", "home", "schedule", "personal")
    }
    assert len(set(specialist_topic_lines.values())) == len(specialist_topic_lines)
    assert recurring_record["home_name"] in specialist_topic_lines["home"]
    specialist_notes = " ".join(wilderness_balance_game.wilderness_specialist_notes_lines(traveler))
    assert "FIELD JOURNAL" in specialist_notes and recurring_record["home_name"] in specialist_notes
    wilderness_balance_game.state.stamina = 50
    assert wilderness_balance_game.study_with_wilderness_specialist(traveler)
    assert not wilderness_balance_game.study_with_wilderness_specialist(traveler)
    specialist_sample = wilderness_balance_game.wilderness_outpost_sample_item(*expedition_target)
    wilderness_balance_game.state.inventory[specialist_sample] = max(
        1, int(wilderness_balance_game.state.inventory.get(specialist_sample, 0))
    )
    assert wilderness_balance_game.share_wilderness_specialist_sample(traveler)
    assert not wilderness_balance_game.share_wilderness_specialist_sample(traveler)
    recurring_record["bond"] = max(4, int(recurring_record["bond"]))
    wilderness_balance_game.state.stamina = 50
    assert wilderness_balance_game.prepare_climate_route_with_traveler(traveler)
    wilderness_balance_game.state.money = max(100, wilderness_balance_game.state.money)
    snacks_before_traveler = int(wilderness_balance_game.state.inventory.get("Field Snack", 0))
    assert wilderness_balance_game.buy_wilderness_traveler_supply("Field Snack", 35)
    assert wilderness_balance_game.state.inventory["Field Snack"] == snacks_before_traveler + 1
    subhabitat_names = {wilderness_balance_game.wilderness_subhabitat_profile(cx, cy)["name"] for cx, cy in sample_wilderness_coords}
    assert len(subhabitat_names) >= 3
    outpost_chunk = wilderness_balance_game.wilderness_region_outpost_chunk(*expedition_target)
    assert wilderness_balance_game.wilderness_chunk_has_outpost(*outpost_chunk)
    wilderness_balance_game.set_wilderness_chunk(*outpost_chunk)
    outpost_positions = [(x, y) for y, row in enumerate(wilderness_balance_game.active_map()) for x, tile in enumerate(row) if tile == "A"]
    assert outpost_positions
    outpost_x, outpost_y = outpost_positions[0]
    assert wilderness_balance_game.current_wilderness_outpost_door_at(
        outpost_x, outpost_y
    )
    outpost_side = wilderness_balance_game.wilderness_exterior_door_side(
        wilderness_balance_game.active_map(), outpost_x, outpost_y
    )
    outpost_dx, outpost_dy = wilderness_balance_game.wilderness_door_delta(outpost_side)
    expected_outpost_return = (outpost_x + outpost_dx, outpost_y + outpost_dy)
    assert "outpost" in wilderness_balance_game.describe_tile(outpost_x, outpost_y).lower() or "lodge" in wilderness_balance_game.describe_tile(outpost_x, outpost_y).lower()
    wilderness_balance_game.state.hour = 20
    wilderness_balance_game.state.minute = 0
    wilderness_balance_game.enter_wilderness_outpost(outpost_x, outpost_y)
    assert wilderness_balance_game.on_wilderness_outpost()
    assert wilderness_balance_game.location_is_weather_sheltered()
    outpost_map = wilderness_balance_game.active_map()
    assert len(outpost_map) == 15 and len(outpost_map[0]) == 31
    outpost_doors = [(x, y) for y, row in enumerate(outpost_map) for x, tile in enumerate(row) if tile == "D"]
    assert len(outpost_doors) == 1
    outpost_door_x, outpost_door_y = outpost_doors[0]
    assert {
        "north": outpost_door_y == 0,
        "south": outpost_door_y == len(outpost_map) - 1,
        "west": outpost_door_x == 0,
        "east": outpost_door_x == len(outpost_map[0]) - 1,
    }[outpost_side]
    assert (wilderness_balance_game.state.player_x, wilderness_balance_game.state.player_y) == (
        outpost_door_x - outpost_dx,
        outpost_door_y - outpost_dy,
    )
    assert (
        wilderness_balance_game.state.wilderness_outpost_return_x,
        wilderness_balance_game.state.wilderness_outpost_return_y,
    ) == expected_outpost_return
    assert any("P" in row for row in outpost_map)
    assert any("@" in row for row in outpost_map)
    assert any("n" in row for row in outpost_map)
    assert sum(row.count("b") for row in outpost_map) >= 2
    records_position = next(
        (x, y)
        for y, row in enumerate(outpost_map)
        for x, tile in enumerate(row)
        if tile == "P"
    )
    keeper_position = next(
        (x, y)
        for y, row in enumerate(outpost_map)
        for x, tile in enumerate(row)
        if tile == "@"
    )
    specialist_home_position = next(
        (x, y)
        for y, row in enumerate(outpost_map)
        for x, tile in enumerate(row)
        if tile == "n"
    )
    assert "Regional records" in wilderness_balance_game.describe_tile(*records_position)
    keeper = wilderness_balance_game.wilderness_outpost_keeper(*outpost_chunk)
    keeper_name = keeper["name"]
    assert keeper["role"] == "Preserve Warden"
    assert keeper is wilderness_balance_game.wilderness_outpost_keeper(*outpost_chunk)
    assert keeper_name in wilderness_balance_game.describe_tile(*keeper_position)
    assert keeper_name in wilderness_balance_game.interaction_hint(*keeper_position)
    assert wilderness_balance_game.passable(*keeper_position)
    assert recurring_record["name"] in wilderness_balance_game.describe_tile(*specialist_home_position)
    assert recurring_record["name"] in wilderness_balance_game.interaction_hint(*specialist_home_position)
    assert wilderness_balance_game.passable(*specialist_home_position)
    assert wilderness_balance_game.is_interactable_tile(*specialist_home_position)
    wilderness_balance_game.vertical_panel_view = lambda *args, **kwargs: None
    keeper_topic_lines = {
        topic: " ".join(wilderness_balance_game.wilderness_outpost_keeper_lines(keeper, topic))
        for topic in ("work", "region", "event", "personal")
    }
    assert len(set(keeper_topic_lines.values())) == 4
    original_outpost_select = wilderness_balance_game.vertical_panel_select
    original_unified_conversation = wilderness_balance_game.run_unified_npc_conversation
    outpost_conversations = []

    def select_outpost_dialogue(title, *args, **kwargs):
        if str(title).startswith("Talk with"):
            return MenuItem(label="Ask About Their Work", value="work", enabled=True)
        return MenuItem(label="Leave the Conversation There", value="leave", enabled=True)

    wilderness_balance_game.vertical_panel_select = select_outpost_dialogue
    wilderness_balance_game.run_unified_npc_conversation = lambda actor, **kwargs: (
        outpost_conversations.append((actor, kwargs)),
        {"completed": True, "transcript": [{"phase": "main subject"}], "topics": []},
    )[-1]
    bond_before_talk = int(keeper["bond"])
    try:
        assert wilderness_balance_game.talk_to_wilderness_outpost_keeper(keeper)
        assert keeper["bond"] == bond_before_talk + 1
        assert not wilderness_balance_game.talk_to_wilderness_outpost_keeper(keeper)
    finally:
        wilderness_balance_game.vertical_panel_select = original_outpost_select
        wilderness_balance_game.run_unified_npc_conversation = original_unified_conversation
    assert len(outpost_conversations) == 2
    assert all(call[1]["kind"] == "outpost" for call in outpost_conversations)
    sample_item = wilderness_balance_game.wilderness_outpost_sample_item(*outpost_chunk)
    wilderness_balance_game.state.inventory[sample_item] = max(1, int(wilderness_balance_game.state.inventory.get(sample_item, 0)))
    bond_before_sample = int(keeper["bond"])
    assert wilderness_balance_game.share_wilderness_outpost_sample(keeper)
    assert keeper["bond"] == bond_before_sample + 3
    assert not wilderness_balance_game.share_wilderness_outpost_sample(keeper)
    wilderness_balance_game.state.town_npc_relationships["mira_seed"] = 100
    wilderness_balance_game.state.unlocked_party_member_ids = ["mira_seed"]
    wilderness_balance_game.state.travel_follower_ids = ["companion:mira_seed"]
    assert wilderness_balance_game.active_travel_follower_ids() == ["companion:mira_seed"]
    wilderness_balance_game.state.inventory["Field Snack"] = max(1, int(wilderness_balance_game.state.inventory.get("Field Snack", 0)))
    wilderness_balance_game.state.stamina = 50
    follower_bond_before_excursion = wilderness_balance_game.travel_follower_bond_points("companion:mira_seed")
    vitality_before_excursion, _ = wilderness_balance_game.wilderness_region_vitality(*outpost_chunk)
    assert wilderness_balance_game.perform_wilderness_group_excursion("study")
    assert wilderness_balance_game.travel_follower_bond_points("companion:mira_seed") == follower_bond_before_excursion + 4
    vitality_after_excursion, _ = wilderness_balance_game.wilderness_region_vitality(*outpost_chunk)
    assert vitality_after_excursion == vitality_before_excursion + 5
    follower_memories = wilderness_balance_game.travel_follower_record("companion:mira_seed")["memories"]
    assert any("Guided Nature Study" in memory for memory in follower_memories)
    assert not wilderness_balance_game.perform_wilderness_group_excursion("picnic")
    assert wilderness_balance_game.wilderness_region_record(*outpost_chunk)["group_excursion_history"][-1]["participants"] == ["Mira"]
    wilderness_balance_game.state.stamina = 20
    assert wilderness_balance_game.rest_at_wilderness_outpost()
    assert not wilderness_balance_game.rest_at_wilderness_outpost()
    supplies_before = int(wilderness_balance_game.state.inventory.get("Field Snack", 0))
    assert wilderness_balance_game.claim_wilderness_outpost_supplies()
    assert wilderness_balance_game.state.inventory["Field Snack"] == supplies_before + 1
    assert not wilderness_balance_game.claim_wilderness_outpost_supplies()
    wilderness_balance_game.exit_wilderness_outpost()
    assert wilderness_balance_game.on_wilderness()
    assert (wilderness_balance_game.state.player_x, wilderness_balance_game.state.player_y) == expected_outpost_return

    # Weekly environmental events now alter traversal and wildlife in the physical map.
    physical_event_game = FarmGame()
    physical_event_game.autosave_with_message = lambda message: physical_event_game.set_message(message)
    physical_event_game.state.wilderness_seed = 24681357
    physical_event_game.state.location = "Wilderness"
    physical_event_game.state.tool_levels["Pickaxe"] = 1
    rockfall_position = None
    for event_cy in range(-12, 13):
        for event_cx in range(-12, 13):
            if physical_event_game.wilderness_weekly_event_profile(event_cx, event_cy).get("name") != "Fresh Rockfall":
                continue
            physical_event_game.set_wilderness_chunk(event_cx, event_cy)
            physical_event_game.prepare_wilderness_runtime_overlays()
            blocking_points = [position for position, data in physical_event_game.wilderness_event_visual_lookup().items() if data.get("blocking")]
            if blocking_points:
                rockfall_position = blocking_points[0]
                break
        if rockfall_position:
            break
    assert rockfall_position is not None
    assert not physical_event_game.passable(*rockfall_position)
    assert "clear rockfall" in physical_event_game.interaction_hint(*rockfall_position).lower()
    stone_before_rockfall = int(physical_event_game.state.inventory.get("Stone", 0))
    physical_event_game.state.stamina = 50
    assert physical_event_game.interact_with_wilderness_event_feature(*rockfall_position)
    assert physical_event_game.state.inventory["Stone"] == stone_before_rockfall + 1
    physical_event_game.prepare_wilderness_runtime_overlays()
    assert not physical_event_game.wilderness_event_blocking_at(*rockfall_position)
    assert physical_event_game.passable(*rockfall_position)

    migration_found = False
    for migration_cy in range(-12, 13):
        for migration_cx in range(-12, 13):
            if physical_event_game.wilderness_weekly_event_profile(migration_cx, migration_cy).get("name") != "Migrating Herd":
                continue
            physical_event_game.set_wilderness_chunk(migration_cx, migration_cy)
            animals = physical_event_game.generate_wilderness_animals_for_chunk(migration_cx, migration_cy)
            if sum(1 for animal in animals if animal.get("species") == "Deer") >= 3:
                migration_found = True
                break
        if migration_found:
            break
    assert migration_found

    # Every region can contribute a persistent, enterable, restorable structure.
    structure_game = FarmGame()
    structure_game.autosave_with_message = lambda message: structure_game.set_message(message)
    structure_game.state.location = "Wilderness"
    structure_chunk = None
    structure_position = None
    structure_grid = None
    for region_y in range(-3, 4):
        for region_x in range(-3, 4):
            candidate = structure_game.wilderness_region_structure_chunk(region_x * 3, region_y * 3)
            if structure_game.home_world_chunk_is_authored(*candidate):
                continue
            grid = structure_game.make_wilderness_chunk(*candidate)
            positions = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == "h"]
            if positions:
                structure_chunk, structure_position, structure_grid = candidate, positions[0], grid
                break
        if structure_chunk:
            break
    assert structure_chunk is not None and structure_position is not None
    structure_key = structure_game.wilderness_chunk_key(*structure_chunk)
    structure_game.wilderness_maps[structure_key] = structure_grid
    structure_game.repaired_wilderness_chunks.add(structure_key)
    structure_game.set_wilderness_chunk(*structure_chunk)
    refreshed_structure_positions = [
        (x, y)
        for y, row in enumerate(structure_game.active_map())
        for x, _tile in enumerate(row)
        if structure_game.current_wilderness_structure_door_at(x, y)
    ]
    assert refreshed_structure_positions
    sx, sy = refreshed_structure_positions[0]
    structure_side = structure_game.wilderness_exterior_door_side(
        structure_game.active_map(), sx, sy
    )
    structure_dx, structure_dy = structure_game.wilderness_door_delta(structure_side)
    expected_structure_return = (sx + structure_dx, sy + structure_dy)
    assert "restore" in structure_game.describe_tile(sx, sy).lower()
    assert structure_game.is_interactable_tile(sx, sy)
    assert not structure_game.passable(sx, sy)
    structure_game.enter_wilderness_structure(sx, sy)
    assert structure_game.on_wilderness_structure()
    assert structure_game.location_is_weather_sheltered()
    structure_map = structure_game.active_map()
    structure_doors = [(x, y) for y, row in enumerate(structure_map) for x, tile in enumerate(row) if tile == "D"]
    assert len(structure_doors) == 1
    structure_door_x, structure_door_y = structure_doors[0]
    assert {
        "north": structure_door_y == 0,
        "south": structure_door_y == len(structure_map) - 1,
        "west": structure_door_x == 0,
        "east": structure_door_x == len(structure_map[0]) - 1,
    }[structure_side]
    assert (structure_game.state.player_x, structure_game.state.player_y) == (
        structure_door_x - structure_dx,
        structure_door_y - structure_dy,
    )
    assert (
        structure_game.state.wilderness_structure_return_x,
        structure_game.state.wilderness_structure_return_y,
    ) == expected_structure_return
    assert any("b" in row for row in structure_map) and any("P" in row for row in structure_map)
    assert {len(structure_map), len(structure_map[0])} == {28, 64}
    structure_room_doors = [
        (x, y)
        for y, row in enumerate(structure_map)
        for x, tile in enumerate(row)
        if tile == "_"
    ]
    assert structure_room_doors
    closed_x, closed_y = structure_room_doors[0]
    assert not structure_game.passable(closed_x, closed_y)
    structure_game.use_wilderness_structure_action(closed_x, closed_y)
    assert structure_game.active_map()[closed_y][closed_x] == "|"
    assert structure_game.passable(closed_x, closed_y)
    structure_catalog = getattr(structure_game, "_wilderness_structure_catalog_furniture_cache", {})
    assert structure_catalog.get(structure_game.state.current_wilderness_structure_key)
    structure_record = structure_game.wilderness_structure_record()
    structure_profile = structure_game.WILDERNESS_STRUCTURE_TYPES[structure_record["type_id"]]
    for material, quantity in structure_profile["materials"].items():
        structure_game.state.inventory[material] = int(quantity)
    vitality_before_structure, _ = structure_game.wilderness_region_vitality(*structure_chunk)
    assert structure_game.repair_wilderness_structure()
    assert structure_record["repaired"]
    assert not structure_game.repair_wilderness_structure()
    assert any("@" in row for row in structure_game.wilderness_structure_map())
    vitality_after_structure, _ = structure_game.wilderness_region_vitality(*structure_chunk)
    assert vitality_after_structure == vitality_before_structure + 8
    assert structure_game.claim_wilderness_structure_service()
    assert not structure_game.claim_wilderness_structure_service()
    assert structure_game.perform_wilderness_structure_work()
    assert not structure_game.perform_wilderness_structure_work()
    assert structure_record.get("activities_completed") == 1
    structure_game.state.stamina = 20
    assert structure_game.rest_at_wilderness_structure()
    assert structure_game.state.stamina > 20
    assert not structure_game.rest_at_wilderness_structure()
    structure_game.exit_wilderness_structure()
    assert structure_game.on_wilderness()
    assert (structure_game.state.player_x, structure_game.state.player_y) == expected_structure_return

    # Broad landscapes reshape chunks while remaining navigable and repeatable.
    landscape_game = FarmGame()
    landscape_game.autosave_with_message = lambda message: landscape_game.set_message(message)
    landscape_game.play_world_event_scene = lambda *_args, **_kwargs: True
    landscape_game.state.location = "Wilderness"
    landscape_types = {landscape_game.wilderness_major_landscape_profile(cx, cy)["type_id"] for cy in range(-8, 9) for cx in range(-8, 9)}
    assert len(landscape_types) >= 7
    assert "large_lake" in landscape_types and "ravine" in landscape_types
    landscape_chunk = None
    landscape_position = None
    for landscape_cy in range(-8, 9):
        for landscape_cx in range(-8, 9):
            if landscape_game.wilderness_major_landscape_profile(landscape_cx, landscape_cy)["type_id"] == "hot_springs":
                continue
            grid = landscape_game.make_wilderness_chunk(landscape_cx, landscape_cy)
            positions = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == "j"]
            if positions:
                landscape_chunk, landscape_position = (landscape_cx, landscape_cy), positions[0]
                break
        if landscape_chunk:
            break
    assert landscape_chunk is not None and landscape_position is not None
    landscape_game.set_wilderness_chunk(*landscape_chunk)
    assert not landscape_game.passable(*landscape_position)
    assert landscape_game.is_interactable_tile(*landscape_position)
    assert "major landscape" in landscape_game.interaction_hint(*landscape_position).lower()
    vitality_before_landscape, _ = landscape_game.wilderness_region_vitality(*landscape_chunk)
    money_before_landscape = landscape_game.state.money
    landscape_kind = str(landscape_game.wilderness_landscape_record()["type_id"])
    landscape_work = landscape_game.WILDERNESS_LANDSCAPE_WORK[landscape_kind]
    landscape_drop_before = {
        item: int(landscape_game.state.inventory.get(item, 0))
        for item in landscape_work["drops"]
    }
    assert landscape_game.interact_with_wilderness_landscape()
    assert landscape_game.state.money == money_before_landscape + int(landscape_work["money"])
    assert all(
        int(landscape_game.state.inventory.get(item, 0))
        == landscape_drop_before[item] + int(quantity)
        for item, quantity in landscape_work["drops"].items()
    )
    assert landscape_game.wilderness_region_vitality(*landscape_chunk)[0] == vitality_before_landscape + 1
    assert not landscape_game.interact_with_wilderness_landscape()
    hot_spring_record = landscape_game.wilderness_landscape_record()
    hot_spring_record["type_id"] = "hot_springs"
    hot_spring_record.pop("rest_day", None)
    landscape_game.state.stamina = 20
    assert landscape_game.interact_with_wilderness_landscape()
    assert landscape_game.state.stamina > 20
    assert not landscape_game.interact_with_wilderness_landscape()

    # Landmark sites are real multi-tile places with a practical anchor, not lone glyphs.
    landmark_game = FarmGame()
    landmark_game.state.location = "Wilderness"
    landmark_anchors = {
        "ranger_camp": "R", "stone_ruin": "P", "trail_shelter": "Q",
        "overlook": "K", "old_quarry": "?", "spring_garden": "?",
        "fungal_garden": "?", "waystone": "?",
    }
    for index, (kind, anchor) in enumerate(landmark_anchors.items()):
        landmark_grid = [["." for _x in range(86)] for _y in range(38)]
        landmark_game.stamp_wilderness_landmark_site(
            landmark_grid, 43, 19, kind, random.Random(71000 + index)
        )
        assert any(anchor in row for row in landmark_grid), kind
        assert sum(tile != "." for row in landmark_grid for tile in row) >= 18, kind
        assert any(":" in row for row in landmark_grid), kind
    field_grid = [[";" for _x in range(86)] for _y in range(38)]
    landmark_game.stamp_wilderness_field_station(field_grid, 43, 19, ";")
    assert any("E" in row for row in field_grid)
    assert any("B" in row for row in field_grid)
    assert sum(row.count("#") for row in field_grid) >= 14
    for site_id, symbol in (("lighthouse", "I"), ("sea_fort", "%"), ("bird_sanctuary", "b"), ("hidden_cove", "c"), ("weather_station", "w")):
        island_grid = [["[" for _x in range(86)] for _y in range(38)]
        landmark_game.stamp_wilderness_island_compound(island_grid, (43, 19), site_id, symbol)
        assert island_grid[19][43] == symbol, site_id
        assert sum(tile != "[" for row in island_grid for tile in row) >= 12, site_id
    for consequence_kind, symbol in (("refuge", "v"), ("staffed_site", "g"), ("excursion", "i")):
        consequence_grid = [["." for _x in range(86)] for _y in range(38)]
        landmark_game.stamp_wilderness_vitality_site(consequence_grid, 43, 19, consequence_kind, symbol)
        assert consequence_grid[19][43] == symbol, consequence_kind
        assert sum(tile != "." for row in consequence_grid for tile in row) >= 12, consequence_kind

    # Far-frontier climate provinces add true desert and tundra without changing the established core world.
    climate_game = FarmGame()
    climate_game.autosave_with_message = lambda message: climate_game.set_message(message)
    climate_coords = {}
    for climate_cy in range(-90, 91):
        for climate_cx in range(-90, 91):
            scanned_climate_profile = climate_game.wilderness_region_profile(climate_cx, climate_cy)
            climate_tile = scanned_climate_profile["biome"]
            if climate_tile in {"`", '"'} and climate_tile not in climate_coords:
                climate_coords[climate_tile] = (int(scanned_climate_profile["center_x"]), int(scanned_climate_profile["center_y"]))
            if len(climate_coords) == 2:
                break
        if len(climate_coords) == 2:
            break
    assert set(climate_coords) == {"`", '"'}
    assert climate_game.wilderness_world_biome_tile(*climate_game.wilderness_world_coords(0, 0, 43, 19)) not in {"`", '"'}
    for climate_tile, climate_chunk in climate_coords.items():
        climate_grid = climate_game.make_wilderness_chunk(*climate_chunk)
        assert sum(row.count(climate_tile) for row in climate_grid) >= 20
        climate_profile = climate_game.wilderness_region_profile(*climate_chunk)
        assert climate_profile["biome"] == climate_tile
        assert climate_game.wilderness_subhabitat_profile(*climate_chunk)["biome"] == climate_tile
        assert climate_game.wilderness_field_site_type(*climate_chunk)["name"] in {"Desert Water Survey", "Tundra Migration Post"}
        assert climate_game.wilderness_region_project_profile(*climate_chunk)["id"] in {"desert_well_route", "tundra_shelter_line"}
        climate_event = climate_game.wilderness_weekly_event_profile(*climate_chunk)
        assert climate_event["name"] in ({"Sandstorm Drifts", "Desert Bloom"} if climate_tile == "`" else {"Whiteout Drifts", "Tundra Herd Passage"})
        assert climate_event["material"] == ("Clay" if climate_tile == "`" else "Fiber")
        climate_rng = random.Random(991)
        expected_species = {"`": {"Lizard", "Hawk", "Fox", "Rabbit"}, '"': {"Deer", "Fox", "Owl", "Hawk"}}[climate_tile]
        assert climate_game.animal_species_for_biome(climate_tile, climate_rng) in expected_species
        climate_structure_chunk = climate_game.wilderness_region_structure_chunk(*climate_chunk)
        expected_structure = {"`": "desert_caravanserai", '"': "tundra_wayhouse"}[climate_tile]
        assert climate_game.wilderness_structure_type(*climate_structure_chunk) == expected_structure
        climate_traveler = climate_game.recurring_wilderness_traveler_record(*climate_chunk)
        assert climate_traveler["role"] == {"`": "Desert Guide", '"': "Tundra Warden"}[climate_tile]
        climate_game.state.wilderness_chunk_x, climate_game.state.wilderness_chunk_y = climate_structure_chunk
        climate_structure_record = climate_game.wilderness_structure_record()
        climate_structure_record["repaired"] = True
        assert climate_game.claim_wilderness_structure_service()
        assert not climate_game.claim_wilderness_structure_service()
        assert climate_game.wilderness_climate_prepared()
        climate_region_record = climate_game.wilderness_region_record(*climate_structure_chunk)
        climate_region_record.pop("climate_prepared_week", None)
        climate_traveler["bond"] = 4
        climate_game.state.stamina = 50
        climate_actor = {"recurring": True, "role": climate_traveler["role"], "name": climate_traveler["name"]}
        assert climate_game.prepare_climate_route_with_traveler(climate_actor)
        assert climate_game.wilderness_climate_prepared()
        assert not climate_game.prepare_climate_route_with_traveler(climate_actor)

    coastal_chunk = None
    coastal_grid = None
    for coastal_cy in range(-90, 91):
        for coastal_cx in range(-90, 91):
            coastal_profile = climate_game.wilderness_region_profile(coastal_cx, coastal_cy)
            if coastal_profile["biome"] == "[":
                candidate = (int(coastal_profile["center_x"]), int(coastal_profile["center_y"]))
                candidate_grid = climate_game.make_wilderness_chunk(*candidate)
                if sum(row.count("~") for row in candidate_grid) >= 80 and sum(row.count("[") for row in candidate_grid) >= 10:
                    coastal_chunk, coastal_grid = candidate, candidate_grid
                    break
        if coastal_chunk:
            break
    assert coastal_chunk is not None
    assert coastal_grid is not None
    assert sum(row.count("~") for row in coastal_grid) >= 80
    assert sum(row.count("[") for row in coastal_grid) >= 10
    ocean_water = []
    for ocean_y, row in enumerate(coastal_grid):
        for ocean_x, tile in enumerate(row):
            if tile != "~":
                continue
            ocean_wx, ocean_wy = climate_game.wilderness_world_coords(
                *coastal_chunk, ocean_x, ocean_y
            )
            if climate_game.wilderness_world_ocean_tile(ocean_wx, ocean_wy):
                ocean_water.append((ocean_x, ocean_y, ocean_wx, ocean_wy))
    assert len(ocean_water) >= 80
    assert climate_game.wilderness_world_current(
        ocean_water[0][2], ocean_water[0][3]
    )["glyph"] in {"<", ">", "^", "v"}
    assert climate_game.wilderness_field_site_type(*coastal_chunk)["name"] == "Coastal Survey Station"
    assert climate_game.wilderness_region_project_profile(*coastal_chunk)["id"] == "coastal_channel_network"
    coastal_structure_chunk = climate_game.wilderness_region_structure_chunk(*coastal_chunk)
    assert climate_game.wilderness_structure_type(*coastal_structure_chunk) == "coastal_ferry_house"
    assert climate_game.recurring_wilderness_traveler_record(*coastal_chunk)["role"] == "Coast Pilot"
    assert climate_game.wilderness_weekly_event_profile(*coastal_chunk)["name"] in {"King Tide", "Seabird Gathering"}
    assert climate_game.animal_species_for_biome("[", random.Random(992)) in {"Duck", "Heron", "Frog", "Songbird"}
    climate_game.state.location = "Wilderness"
    climate_game.state.wilderness_chunk_x, climate_game.state.wilderness_chunk_y = coastal_chunk
    climate_game.state.wilderness_map = coastal_grid
    climate_game.state.month = 3
    climate_game.state.weather = "Cloudy"
    climate_game.state.hour = 10
    assert climate_game.fishing_location_name() == "Coast"
    coastal_fish = set(climate_game.available_fish_here())
    assert {"Tide Sardine", "Silver Salmon"}.issubset(coastal_fish)
    assert "River Chub" not in coastal_fish
    climate_game.state.hour = 13
    assert "Mackerel" in climate_game.available_fish_here()
    reef_target = None
    desert_island_seen = False
    tropical_island_seen = False
    checked_coastal_regions = set()
    for reef_cy in range(-95, 96):
        for reef_cx in range(-95, 96):
            reef_profile = climate_game.wilderness_region_profile(reef_cx, reef_cy)
            reef_anchor = (int(reef_profile["rx"]), int(reef_profile["ry"]))
            if reef_profile["biome"] != "[" or reef_anchor in checked_coastal_regions:
                continue
            checked_coastal_regions.add(reef_anchor)
            reef_chunk = (int(reef_profile["center_x"]), int(reef_profile["center_y"]))
            reef_grid = climate_game.make_wilderness_chunk(*reef_chunk)
            desert_island_seen = desert_island_seen or any(chr(96) in row for row in reef_grid)
            tropical_island_seen = tropical_island_seen or any(";" in row for row in reef_grid)
            for reef_y, row in enumerate(reef_grid):
                for reef_x, tile in enumerate(row):
                    if tile != "~":
                        continue
                    reef_wx, reef_wy = climate_game.wilderness_world_coords(
                        *reef_chunk, reef_x, reef_y
                    )
                    if climate_game.wilderness_world_reef_at(reef_wx, reef_wy):
                        reef_target = (reef_chunk, reef_grid, reef_x, reef_y)
                        break
                if reef_target:
                    break
            if reef_target and desert_island_seen and tropical_island_seen:
                break
        if reef_target and desert_island_seen and tropical_island_seen:
            break
    assert reef_target is not None
    assert desert_island_seen and tropical_island_seen
    reef_chunk, reef_grid, reef_x, reef_y = reef_target
    climate_game.state.wilderness_chunk_x, climate_game.state.wilderness_chunk_y = reef_chunk
    climate_game.state.wilderness_map = reef_grid
    reef_fish = set(climate_game.available_fish_here(reef_x, reef_y))
    assert {"Coral Dart", "Parrotfish", "Reef Grouper"}.intersection(reef_fish)
    coastal_settlement = climate_game.wilderness_fishing_settlement_record()
    coastal_settlement["level"] = 3
    before_sardines = climate_game.state.inventory.get("Tide Sardine", 0)
    assert climate_game.claim_fishing_settlement_weekly_catch()
    assert climate_game.state.inventory.get("Tide Sardine", 0) == before_sardines + 4
    assert climate_game.state.inventory.get("Mackerel", 0) >= 1
    assert not climate_game.claim_fishing_settlement_weekly_catch()
    landscape_record = climate_game.wilderness_landscape_record()
    landscape_drops = dict(
        climate_game.WILDERNESS_LANDSCAPE_WORK.get(str(landscape_record.get("type_id", "")), {}).get("drops", {"Fiber": 1})
    )
    before_coastal_materials = sum(climate_game.state.inventory.get(item, 0) for item in landscape_drops)
    climate_game.play_world_event_scene = lambda *_args, **_kwargs: True
    assert climate_game.interact_with_wilderness_landscape()
    after_coastal_materials = sum(climate_game.state.inventory.get(item, 0) for item in landscape_drops)
    assert after_coastal_materials > before_coastal_materials

    coast_region = climate_game.wilderness_region_profile(*coastal_chunk)
    island_chunk = None
    for island_cx, island_cy in climate_game.wilderness_region_chunks(*coastal_chunk):
        if climate_game.wilderness_island_site_profile(island_cx, island_cy):
            island_chunk = (island_cx, island_cy)
            break
    assert island_chunk is not None
    island_grid = climate_game.make_wilderness_chunk(*island_chunk)
    climate_game.state.wilderness_chunk_x, climate_game.state.wilderness_chunk_y = island_chunk
    climate_game.state.wilderness_map = island_grid
    island_profile = climate_game.wilderness_island_site_profile()
    island_position = climate_game.wilderness_island_site_position()
    assert island_position != (-1, -1)
    assert climate_game.wilderness_island_site_at(*island_position)["id"] == island_profile["id"]
    assert not climate_game.passable(*island_position)
    for material, quantity in island_profile["materials"].items():
        climate_game.state.inventory[material] = max(quantity, climate_game.state.inventory.get(material, 0))
    assert climate_game.restore_wilderness_island_site()
    assert climate_game.wilderness_island_site_record()["restored"]
    assert climate_game.claim_wilderness_island_site_service()
    assert not climate_game.claim_wilderness_island_site_service()

    maritime_encounter = None
    climate_game.state.wilderness_boating = True
    for encounter_cx, encounter_cy in climate_game.wilderness_region_chunks(*coastal_chunk):
        climate_game.state.wilderness_chunk_x, climate_game.state.wilderness_chunk_y = encounter_cx, encounter_cy
        climate_game.state.wilderness_map = climate_game.make_wilderness_chunk(encounter_cx, encounter_cy)
        maritime_encounter = climate_game.wilderness_maritime_encounter()
        if maritime_encounter:
            break
    assert maritime_encounter
    encounter_position = tuple(maritime_encounter["position"])
    assert climate_game.wilderness_maritime_encounter_at(*encounter_position)["id"] == maritime_encounter["id"]
    assert not climate_game.passable(*encounter_position)
    vitality_before_encounter = climate_game.wilderness_region_vitality(
        climate_game.state.wilderness_chunk_x,
        climate_game.state.wilderness_chunk_y,
    )
    assert climate_game.resolve_wilderness_maritime_encounter()
    assert not climate_game.wilderness_maritime_encounter()
    assert climate_game.wilderness_region_vitality(
        climate_game.state.wilderness_chunk_x,
        climate_game.state.wilderness_chunk_y,
    ) > vitality_before_encounter

    inland_game = FarmGame()
    inland_game.state.location = "Wilderness"
    inland_game.state.wilderness_chunk_x = 0
    inland_game.state.wilderness_chunk_y = 0
    assert inland_game.fishing_location_name() == "Wilderness"
    assert "Tide Sardine" not in inland_game.available_fish_here()

    # Docks provide rental/owned skiffs, real water movement, and known ferry links.
    boat_game = FarmGame()
    boat_game.autosave_with_message = lambda message: boat_game.set_message(message)
    boat_game.state.wilderness_seed = 24681357
    boat_game.state.location = "Wilderness"
    known_docks = []
    for boat_cy in range(-6, 7):
        for boat_cx in range(-6, 7):
            grid = boat_game.make_wilderness_chunk(boat_cx, boat_cy)
            positions = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == "k"]
            if positions:
                if not known_docks or abs(known_docks[0][0][0] - boat_cx) + abs(known_docks[0][0][1] - boat_cy) <= 6:
                    known_docks.append(((boat_cx, boat_cy), positions[0]))
                if len(known_docks) >= 2:
                    break
        if len(known_docks) >= 2:
            break
    assert len(known_docks) >= 2
    for chunk, _position in known_docks[:2]:
        boat_game.set_wilderness_chunk(*chunk)
    first_chunk, first_dock = known_docks[0]
    boat_game.set_wilderness_chunk(*first_chunk)
    assert "water travel" in boat_game.describe_tile(*first_dock).lower()
    assert not boat_game.passable(*first_dock)
    boat_game.state.money = 2000
    assert boat_game.rent_wilderness_boat()
    assert not boat_game.rent_wilderness_boat()
    money_after_rental = boat_game.state.money
    assert boat_game.embark_wilderness_boat(*first_dock)
    assert boat_game.state.wilderness_boating
    assert boat_game.active_map()[boat_game.state.player_y][boat_game.state.player_x] in {"~", "="}
    assert boat_game.passable(boat_game.state.player_x, boat_game.state.player_y)
    assert not boat_game.passable(*boat_game.wilderness_dock_land_tile(*first_dock))
    assert boat_game.disembark_wilderness_boat(*first_dock)
    assert not boat_game.state.wilderness_boating
    assert boat_game.buy_wilderness_boat()
    assert boat_game.state.wilderness_boat_owned and boat_game.state.money == money_after_rental - 1200
    ferry_destinations = boat_game.known_wilderness_ferry_destinations()
    assert ferry_destinations
    ferry_money_before = boat_game.state.money
    assert boat_game.take_wilderness_ferry(ferry_destinations[0])
    assert boat_game.state.money == ferry_money_before - int(ferry_destinations[0]["cost"])

    raft_game = FarmGame()
    raft_game.autosave_with_message = lambda message: raft_game.set_message(message)
    raft_game.state.location = "Wilderness"
    raft_game.state.wilderness_chunk_x = 40
    raft_game.state.wilderness_chunk_y = 40
    raft_grid = [["." for _ in range(86)] for _ in range(38)]
    raft_grid[10][11] = "~"
    raft_grid[10][12] = "~"
    raft_game.wilderness_map = raft_grid
    raft_key = raft_game.wilderness_chunk_key(40, 40)
    raft_game.wilderness_maps[raft_key] = raft_grid
    raft_game.wilderness_open_water_at = (
        lambda x, y: 0 <= y < len(raft_grid)
        and 0 <= x < len(raft_grid[0])
        and raft_grid[y][x] == "~"
    )
    # Keep this synthetic movement fixture isolated from normal legacy-chunk
    # repair, which may legitimately turn its tiny water strip into a bridge.
    raft_game.wilderness_static_checked_chunks = {raft_key}
    raft_game.state.player_x, raft_game.state.player_y = 10, 10
    raft_game.state.inventory["Explorer Raft"] = 1
    # This fixture verifies terrain movement, not generated actors, events, or
    # virtual landmarks occupying the artificial landing tile between moves.
    raft_game.travel_follower_at = lambda *_args: None
    raft_game.animal_at = lambda *_args: None
    raft_game.procedural_town_resident_at = lambda *_args: None
    raft_game.procedural_town_hinterland_at = lambda *_args: {}
    raft_game.wilderness_maritime_encounter_at = lambda *_args: {}
    raft_game.wilderness_island_site_at = lambda *_args: {}
    raft_game.wilderness_water_salvage_at = lambda *_args: False
    raft_game.wilderness_expedition_camp_visual_at = lambda *_args: False
    raft_game.wilderness_event_blocking_at = lambda *_args: False
    raft_game.wilderness_seasonal_surface_blocking_at = lambda *_args: False
    raft_game.wilderness_traveler_at = lambda *_args: {}
    raft_game.wilderness_stronghold_enemy_at = lambda *_args: None
    raft_game.wilderness_random_combat_enemy_at = lambda *_args: None
    raft_game.wilderness_random_combat_visual_at = lambda *_args: None
    raft_game.bounty_target_at = lambda *_args: None
    raft_game.apply_wilderness_current_after_move = lambda *_args: False
    raft_game.reclaimed_stronghold_build_board_at = lambda *_args: False
    raft_game.reclaimed_stronghold_feature_at = lambda *_args: ("", {})
    raft_game.current_procedural_town_plan = lambda: None
    assert raft_game.wilderness_watercraft_available()
    raft_game.move(1, 0)
    assert raft_game.state.wilderness_boating
    assert (raft_game.state.player_x, raft_game.state.player_y) == (11, 10)
    raft_grid[10][10] = "."
    assert raft_game.prepare_wilderness_water_movement(10, 10)
    assert not raft_game.state.wilderness_boating
    raft_game.move(-1, 0)
    assert not raft_game.state.wilderness_boating
    assert (raft_game.state.player_x, raft_game.state.player_y) == (10, 10)
    disconnected_dock_grid = [["." for _ in range(30)] for _ in range(16)]
    disconnected_dock_grid[8][8] = "k"
    disconnected_dock_grid[8][24] = "~"
    assert raft_game.ensure_wilderness_docks_touch_water(
        disconnected_dock_grid, 40, 40
    ) > 0
    assert any(
        disconnected_dock_grid[8 + dy][8 + dx] == "~"
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    )

    fishing_game = FarmGame()
    fishing_game.autosave_with_message = lambda message: fishing_game.set_message(message)
    fishing_game.state.wilderness_seed = 24681357
    fishing_game.state.location = "Wilderness"
    fishing_chunk = None
    fishing_grid = None
    for fishing_cy in range(-10, 11):
        for fishing_cx in range(-10, 11):
            if not fishing_game.wilderness_chunk_has_fishing_settlement(fishing_cx, fishing_cy):
                continue
            candidate_grid = [["~" for _ in range(86)] for _ in range(38)]
            for x in range(86): candidate_grid[0][x] = candidate_grid[-1][x] = "#"
            for y in range(38): candidate_grid[y][0] = candidate_grid[y][-1] = "#"
            fishing_game.place_wilderness_fishing_settlement(candidate_grid, fishing_cx, fishing_cy)
            if any("q" in row for row in candidate_grid):
                fishing_chunk, fishing_grid = (fishing_cx, fishing_cy), candidate_grid
                break
        if fishing_chunk:
            break
    assert fishing_chunk is not None and fishing_grid is not None
    fishing_game.state.wilderness_chunk_x, fishing_game.state.wilderness_chunk_y = fishing_chunk
    fishing_game.wilderness_map = fishing_grid
    fishing_game.wilderness_maps[fishing_game.wilderness_chunk_key(*fishing_chunk)] = fishing_grid
    settlement_positions = [(x, y) for y, row in enumerate(fishing_grid) for x, tile in enumerate(row) if tile == "q"]
    assert len(settlement_positions) == 1
    harbor = settlement_positions[0]
    assert fishing_game.wilderness_dock_water_tile(*harbor) != (-1, -1)
    assert fishing_game.wilderness_dock_land_tile(*harbor) != (-1, -1)
    settlement_record = fishing_game.wilderness_fishing_settlement_record()
    assert settlement_record["level"] == 0
    vitality_before_harbor, _ = fishing_game.wilderness_region_vitality(*fishing_chunk)
    for expected_level in (1, 2, 3):
        upgrade = fishing_game.fishing_settlement_upgrade_profile(expected_level)
        for material, quantity in upgrade["materials"].items(): fishing_game.state.inventory[material] = int(quantity)
        assert fishing_game.develop_wilderness_fishing_settlement()
        assert settlement_record["level"] == expected_level
    assert not fishing_game.develop_wilderness_fishing_settlement()
    assert fishing_game.wilderness_region_vitality(*fishing_chunk)[0] == vitality_before_harbor + 24
    assert fishing_game.claim_fishing_settlement_weekly_catch()
    assert not fishing_game.claim_fishing_settlement_weekly_catch()
    harbor_money_before = fishing_game.state.money
    assert fishing_game.claim_fishing_settlement_trade_income()
    assert fishing_game.state.money > harbor_money_before
    assert not fishing_game.claim_fishing_settlement_trade_income()
    fishing_game.state.wilderness_boat_owned = True
    assert fishing_game.embark_wilderness_boat(*harbor)
    salvage_position = fishing_game.wilderness_water_salvage_position()
    assert salvage_position != (-1, -1)
    assert not fishing_game.passable(*salvage_position)
    wood_before_salvage = int(fishing_game.state.inventory.get("Wood", 0))
    assert fishing_game.collect_wilderness_water_salvage()
    assert fishing_game.state.inventory["Wood"] > wood_before_salvage
    assert fishing_game.wilderness_water_salvage_position() == (-1, -1)
    assert not fishing_game.collect_wilderness_water_salvage()
    assert fishing_game.disembark_wilderness_boat(*harbor)
    cargo_dx, cargo_dy = fishing_chunk[0] + 1, fishing_chunk[1]
    cargo_grid = [["." for _ in range(86)] for _ in range(38)]
    for x in range(86): cargo_grid[0][x] = cargo_grid[-1][x] = "#"
    for y in range(38): cargo_grid[y][0] = cargo_grid[y][-1] = "#"
    cargo_grid[10][10] = "k"
    cargo_grid[10][11] = "~"
    cargo_key = fishing_game.wilderness_chunk_key(cargo_dx, cargo_dy)
    fishing_game.wilderness_maps[cargo_key] = cargo_grid
    assert fishing_game.accept_wilderness_water_cargo()
    active_cargo = fishing_game.active_wilderness_water_cargo()
    assert active_cargo and active_cargo["destination"] == cargo_key
    assert not fishing_game.accept_wilderness_water_cargo()
    cargo_reward = int(active_cargo["reward"])
    cargo_money_before = fishing_game.state.money
    fishing_game.state.wilderness_chunk_x, fishing_game.state.wilderness_chunk_y = cargo_dx, cargo_dy
    fishing_game.wilderness_map = cargo_grid
    assert fishing_game.complete_wilderness_water_cargo()
    assert fishing_game.state.money == cargo_money_before + cargo_reward
    assert not fishing_game.complete_wilderness_water_cargo()
    assert fishing_game.wilderness_region_record(cargo_dx, cargo_dy)["water_cargo_deliveries"] == 1

    wilderness_poi_game = FarmGame()
    wilderness_poi_game.autosave_with_message = lambda message: wilderness_poi_game.set_message(message)
    wilderness_poi_game.vertical_panel_view = lambda *args, **kwargs: None
    landmark_special_events = []
    wilderness_poi_game.play_world_event_scene = (
        lambda event_id, title, steps, completion_message="":
        landmark_special_events.append((str(event_id), str(title), list(steps))) or True
    )
    wilderness_poi_game.state.wilderness_seed = 24681357
    wilderness_poi_game.wilderness_maps = {}
    wilderness_poi_game.wilderness_map = []
    wilderness_poi_game.state.location = "Wilderness"
    # Chunk 0,0 is now the physical home farm. Exercise the legacy complete
    # landmark collection on an isolated non-home test chunk instead.
    wilderness_poi_game.set_wilderness_chunk(6, 7)
    poi_map = wilderness_poi_game.make_wilderness_map(
        wilderness_poi_game.state.wilderness_seed,
    )
    wilderness_poi_game.wilderness_map = poi_map
    wilderness_poi_game.wilderness_maps[
        wilderness_poi_game.wilderness_chunk_key()
    ] = poi_map
    assert wilderness_poi_game.current_wilderness_map_fast_ready()
    assert wilderness_poi_game.active_map() is wilderness_poi_game.wilderness_map
    poi_map = wilderness_poi_game.active_map()

    def first_tile(tile):
        for yy, row in enumerate(poi_map):
            for xx, ch in enumerate(row):
                if ch == tile:
                    return (xx, yy)
        return None

    camp_pos = first_tile("R")
    shelter_pos = first_tile("Q")
    ruin_pos = first_tile("P")
    assert camp_pos is not None
    assert shelter_pos is not None
    assert ruin_pos is not None
    wilderness_poi_game.state.stamina = 40
    assert wilderness_poi_game.rest_at_wilderness_poi(camp_pos[0], camp_pos[1], "camp", "Ranger Camp", 20, 0.12, 20)
    assert wilderness_poi_game.state.stamina > 40
    assert not wilderness_poi_game.rest_at_wilderness_poi(camp_pos[0], camp_pos[1], "camp", "Ranger Camp", 20, 0.12, 20)
    assert wilderness_poi_game.claim_wilderness_poi_cache(shelter_pos[0], shelter_pos[1], "shelter", "Wilderness Shelter")
    assert not wilderness_poi_game.claim_wilderness_poi_cache(shelter_pos[0], shelter_pos[1], "shelter", "Wilderness Shelter")
    assert wilderness_poi_game.search_wilderness_ruin(ruin_pos[0], ruin_pos[1])
    assert not wilderness_poi_game.search_wilderness_ruin(ruin_pos[0], ruin_pos[1])
    wilderness_poi_game.state.stamina = 100
    assert wilderness_poi_game.work_wilderness_minor_landmark(20, 20, "waystone")
    assert any(event_id.startswith("landmark_work:") for event_id, _title, _steps in landmark_special_events)
    wilderness_poi_game.state.inventory["Stone"] = 10
    wilderness_poi_game.state.inventory["Wood"] = 4
    assert wilderness_poi_game.restore_wilderness_ruin(ruin_pos[0], ruin_pos[1])
    assert any(event_id.startswith("ruin_restored:") for event_id, _title, _steps in landmark_special_events)
    wilderness_poi_game.state.stamina = 100
    assert wilderness_poi_game.explore_wilderness_landscape_route()
    assert any(event_id.startswith("landscape_route:") for event_id, _title, _steps in landmark_special_events)
    assert wilderness_poi_game.interact_with_wilderness_landscape()
    assert any(
        event_id.startswith("landscape_specialty:")
        or event_id.startswith("hot_springs_rest:")
        for event_id, _title, _steps in landmark_special_events
    )
    wilderness_poi_game.vertical_panel_select = (
        lambda *_args, **_kwargs: MenuItem(label="Survey", value="survey", enabled=True)
    )
    wilderness_poi_game.open_wilderness_overlook_site(10, 10)
    assert any(event_id.startswith("overlook_survey:") for event_id, _title, _steps in landmark_special_events)
    assert wilderness_poi_game.state.wilderness_poi_state

    # Every random-landmark menu must treat the selector's explicit Back
    # sentinel as cancellation instead of redrawing a parent loop.
    landmark_back_game = FarmGame()
    landmark_back_game.state.location = "Wilderness"
    landmark_back_calls = []
    landmark_back_game.vertical_panel_select = (
        lambda title, *_args, **_kwargs: (
            landmark_back_calls.append(str(title))
            or MenuItem(
                label="Back",
                value=farmstead_main.MENU_BACK,
                enabled=True,
            )
        )
    )
    landmark_back_game.vertical_panel_view = (
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Back must not open another landmark screen")
        )
    )
    landmark_back_game.show_wilderness_field_site(10, 10)
    landmark_back_game.show_wilderness_region_project(10, 10)
    landmark_back_game.show_wilderness_phenomenon(10, 10)
    landmark_back_game.open_wilderness_ruin_site(10, 10)
    landmark_back_game.open_wilderness_overlook_site(10, 10)
    landmark_back_game.open_wilderness_landscape_site()
    assert len(landmark_back_calls) == 6

    # Peaceful NPCs can share a tile with the player, while hostile actors
    # remain solid.
    npc_collision_game = FarmGame()
    npc_collision_game.state.location = "Town"
    town_step = next(
        (x, y, dx, dy)
        for y, row in enumerate(npc_collision_game.town_map)
        for x, _tile in enumerate(row)
        for dx, dy in ((1, 0), (0, 1))
        if 3 <= x < len(row) - 3
        and 3 <= y < len(npc_collision_game.town_map) - 3
        if npc_collision_game.passable(x, y)
        and npc_collision_game.passable(x + dx, y + dy)
    )
    start_x, start_y, step_dx, step_dy = town_step
    npc_target = (start_x + step_dx, start_y + step_dy)
    peaceful_npc = {"name": "Path Test Resident", "location": "Town"}
    npc_collision_game.town_npc_at = (
        lambda x, y: peaceful_npc if (int(x), int(y)) == npc_target else None
    )
    assert npc_collision_game.passable(*npc_target)
    npc_collision_game.state.player_x = start_x
    npc_collision_game.state.player_y = start_y
    npc_collision_game.move(step_dx, step_dy)
    assert (
        npc_collision_game.state.player_x,
        npc_collision_game.state.player_y,
    ) == npc_target
    npc_collision_game.state.facing = "LEFT" if step_dx else "UP"
    spoken_to = []
    npc_collision_game.town_npc_menu = lambda npc: spoken_to.append(npc)
    npc_collision_game.general_interact()
    assert spoken_to == [peaceful_npc]
    npc_collision_game.state.location = "Mine"
    mine_enemy_position = next(
        (x, y)
        for y, row in enumerate(npc_collision_game.mine_map)
        for x, tile in enumerate(row)
        if tile == "."
    )
    npc_collision_game.mine_enemy_at = (
        lambda x, y: {"species": "Collision Test Slime"}
        if (int(x), int(y)) == mine_enemy_position
        else None
    )
    assert not npc_collision_game.passable(*mine_enemy_position)

    field_combat_game = FarmGame()
    field_combat_game.autosave_with_message = lambda message: field_combat_game.set_message(message)
    field_combat_game.state.location = "Wilderness"
    field_combat_game.set_wilderness_chunk(12, 12)
    field_points = []
    for yy in range(8, field_combat_game.active_map_height() - 8):
        for xx in range(8, field_combat_game.active_map_width() - 8):
            if field_combat_game.passable(xx, yy):
                field_points.append((xx, yy))
            if len(field_points) >= 3:
                break
        if len(field_points) >= 3:
            break
    assert len(field_points) >= 3
    field_enemies = [
        {
            "id": f"field-smoke:{index}", "encounter_id": "field-smoke",
            "field_combat_kind": "encounter", "species": species,
            "chunk_x": 12, "chunk_y": 12, "floor": 10,
            "x": point[0], "y": point[1], "alert": True,
            "defeated": False, "boss": False,
        }
        for index, (species, point) in enumerate(zip(("Bandit", "Wolf"), field_points[:2]))
    ]
    field_combat_game.state.wilderness_combat_encounters["12,12"] = {
        "id": "field-smoke", "week": field_combat_game.stronghold_cache_week_key(),
        "present": True, "resolved": False, "name": "Smoke Roadblock",
        "description": "A test roadblock.", "reward_money": 25,
        "enemies": field_enemies,
        "visuals": [{"x": field_points[2][0], "y": field_points[2][1], "symbol": "|", "name": "Road Barricade", "blocking": True}],
    }
    assert field_combat_game.wilderness_random_combat_visual_at(*field_points[2])
    assert not field_combat_game.passable(*field_points[2])
    assert field_combat_game.begin_wilderness_field_combat(field_enemies[0], reason="smoke")
    assert field_combat_game.wilderness_field_combat_active()
    field_money_before = field_combat_game.state.money
    for enemy in field_enemies:
        field_combat_game.ensure_dungeon_roguelike_enemy(enemy)
        enemy["hp"] = 1
        assert field_combat_game.dungeon_resolve_player_attack(
            enemy, attack_value=99, advance_turn=False,
        )
    assert not field_combat_game.wilderness_field_combat_active()
    assert field_combat_game.state.wilderness_combat_encounters["12,12"]["resolved"] is True
    assert field_combat_game.state.money == field_money_before + 25
    assert len(field_combat_game.dungeon_floor_loot()) == 2
    assert field_combat_game.state.wilderness_field_loot["12,12"]

    false_entry_game = FarmGame()
    false_entry_game.autosave_with_message = lambda message: false_entry_game.set_message(message)
    false_entry_game.state.location = "Wilderness"
    blacksmith_chunk_x, blacksmith_chunk_y, blacksmith_x, blacksmith_y = (
        false_entry_game.home_world_chunk_from_world(-124, -7)
    )
    false_entry_game.set_wilderness_chunk(blacksmith_chunk_x, blacksmith_chunk_y)
    assert false_entry_game.active_map()[blacksmith_y][blacksmith_x] == "X"
    assert not false_entry_game.is_wilderness_dungeon_entrance_at(blacksmith_x, blacksmith_y)
    false_entry_game.state.player_x = blacksmith_x
    false_entry_game.state.player_y = blacksmith_y - 1
    false_entry_game.move(0, 1)
    assert false_entry_game.state.location == "Wilderness"
    assert (false_entry_game.state.player_x, false_entry_game.state.player_y) == (
        blacksmith_x, blacksmith_y - 1,
    )

    dungeon_game = FarmGame()
    dungeon_game.autosave_with_message = lambda message: dungeon_game.set_message(message)
    dungeon_game.state.player_name = "Avery"
    dungeon_coords = None
    for cy in range(-50, 51):
        for cx in range(-50, 51):
            preview_key = f"{cx},{cy}:0,0"
            if (
                dungeon_game.wilderness_chunk_has_dungeon_site(cx, cy)
                and not dungeon_game.dungeon_is_mega(preview_key)
                and not dungeon_game.procedural_town_plan(cx, cy)
            ):
                dungeon_coords = (cx, cy)
                break
        if dungeon_coords:
            break
    assert dungeon_coords is not None
    assert dungeon_game.overworld_chunk_preview_symbol(*dungeon_coords) == "_"
    dungeon_game.state.location = "Wilderness"
    dungeon_game.set_wilderness_chunk(*dungeon_coords)
    assert dungeon_game.overworld_chunk_preview_symbol(*dungeon_coords) == "X"
    dungeon_entrance = None
    for y, row in enumerate(dungeon_game.active_map()):
        for x, tile in enumerate(row):
            if dungeon_game.is_wilderness_dungeon_entrance_at(x, y):
                dungeon_entrance = (x, y)
                break
        if dungeon_entrance:
            break
    assert dungeon_entrance is not None
    assert dungeon_game.is_wilderness_dungeon_entrance_at(*dungeon_entrance)
    assert "dungeon" in dungeon_game.describe_tile(*dungeon_entrance).lower()
    # An unrelated X must not become an entrance even in a dungeon-bearing
    # chunk; symbol-only dispatch caused building walls to teleport players.
    dungeon_game.active_map()[1][1] = "X"
    assert not dungeon_game.is_wilderness_dungeon_entrance_at(1, 1)
    assert not dungeon_game.enter_wilderness_dungeon(1, 1)
    assert dungeon_game.state.location == "Wilderness"
    assert dungeon_game.enter_wilderness_dungeon(*dungeon_entrance)
    assert dungeon_game.state.location == "WildernessDungeon"
    dungeon_max_floor = dungeon_game.dungeon_max_floor_for_key(dungeon_game.state.current_dungeon_key)
    dungeon_map = dungeon_game.active_map()
    dungeon_symbols = set("".join("".join(row) for row in dungeon_map))
    if dungeon_max_floor > 1:
        assert ">" in dungeon_symbols
    else:
        assert ">" not in dungeon_symbols
    assert "+" in dungeon_symbols
    assert "$" in dungeon_symbols
    assert ("P" in dungeon_symbols) == (dungeon_max_floor == 1)
    assert "!" in dungeon_symbols
    assert "S" in dungeon_symbols
    assert "?" in dungeon_symbols
    assert not (set("oqcigACdhmb") & dungeon_symbols)
    dungeon_game.dungeon_update_exploration()
    dungeon_rooms, dungeon_room_lookup = dungeon_game.dungeon_room_regions()
    assert len(dungeon_rooms) >= 2
    explored_before_doors = set(dungeon_game.dungeon_explored_tiles())
    assert (dungeon_game.state.player_x, dungeon_game.state.player_y) in explored_before_doors
    concealed_room_position = next(
        (
            position
            for position, room_id in dungeon_room_lookup.items()
            if room_id not in dungeon_game.dungeon_roguelike_record()["revealed_rooms"]
        ),
        None,
    )
    assert concealed_room_position is not None
    assert concealed_room_position not in explored_before_doors
    assert ANSI_CSI_RE.sub("", dungeon_game.render_tile(*concealed_room_position)) == " "
    assert "Unexplored darkness" in dungeon_game.describe_tile(*concealed_room_position)

    dungeon_doors = [(x, y) for y, row in enumerate(dungeon_map) for x, tile in enumerate(row) if tile == "+"]
    revealed_by_door = set()
    for candidate_door_x, candidate_door_y in dungeon_doors:
        before_rooms = set(dungeon_game.dungeon_roguelike_record()["revealed_rooms"])
        dungeon_game.dungeon_reveal_rooms_adjacent_to_door(candidate_door_x, candidate_door_y)
        revealed_by_door = (
            set(dungeon_game.dungeon_roguelike_record()["revealed_rooms"])
            - before_rooms
        )
        if revealed_by_door:
            break
    assert revealed_by_door
    assert any(
        dungeon_game.dungeon_tile_explored(*position)
        for position, room_id in dungeon_room_lookup.items()
        if room_id in revealed_by_door
    )
    door_x, door_y = dungeon_doors[0]
    assert dungeon_game.dungeon_set_door_closed(door_x, door_y, True)
    assert dungeon_game.dungeon_door_closed(door_x, door_y)
    assert ANSI_CSI_RE.sub("", dungeon_game.render_dungeon_door(door_x, door_y)) == "+"
    assert not dungeon_game.passable(door_x, door_y)
    door_test_enemy = {"id": "door-test", "species": "Dustling", "x": max(1, door_x - 1), "y": door_y}
    assert not dungeon_game.dungeon_enemy_apply_step(door_test_enemy, (door_x, door_y))
    assert not dungeon_game.dungeon_door_closed(door_x, door_y)
    assert ANSI_CSI_RE.sub("", dungeon_game.render_dungeon_door(door_x, door_y)) == "/"

    dungeon_traps = [(x, y) for y, row in enumerate(dungeon_map) for x, tile in enumerate(row) if tile == "!"]
    assert len(dungeon_traps) >= 2
    hidden_trap_x, hidden_trap_y = dungeon_traps[0]
    assert ANSI_CSI_RE.sub("", dungeon_game.render_dungeon_trap(hidden_trap_x, hidden_trap_y)) == "."
    assert dungeon_game.dungeon_trap_kind(hidden_trap_x, hidden_trap_y) in {
        "needle", "snare", "alarm", "blast",
    }
    if dungeon_game.dungeon_tile_explored(hidden_trap_x, hidden_trap_y):
        assert "suspicious" not in dungeon_game.describe_tile(hidden_trap_x, hidden_trap_y).lower()
        assert not dungeon_game.is_interactable_tile(hidden_trap_x, hidden_trap_y)
    dungeon_game.dungeon_roguelike_record()["revealed_traps"].append(
        dungeon_game.dungeon_feature_key(hidden_trap_x, hidden_trap_y)
    )
    assert ANSI_CSI_RE.sub("", dungeon_game.render_dungeon_trap(hidden_trap_x, hidden_trap_y)) == "!"
    enemy_trap_x, enemy_trap_y = dungeon_traps[1]
    trapped_enemy = {
        "id": "trap-test", "species": "Dustling", "x": enemy_trap_x, "y": enemy_trap_y,
        "hp": 99, "max_hp": 99, "attack": 4, "defense": 0,
    }
    assert dungeon_game.dungeon_enemy_trigger_trap(trapped_enemy)
    assert int(trapped_enemy["hp"]) < 99
    assert dungeon_game.active_map()[enemy_trap_y][enemy_trap_x] == ":"

    companion_test_profile = {"id": "companion-test", "name": "Test Ally", "max_hp": 8, "defense": 0}
    companion_test_runtime = dungeon_game.dungeon_companion_runtime(companion_test_profile)
    companion_test_target = {
        "kind": "companion", "id": "companion-test", "name": "Test Ally",
        "position": (dungeon_game.state.player_x, dungeon_game.state.player_y),
        "profile": companion_test_profile, "runtime": companion_test_runtime,
    }
    knockout_enemy = {"species": "Hollow Sentinel", "attack": 50, "defense": 0}
    dungeon_game.dungeon_enemy_attack_companion(knockout_enemy, companion_test_target)
    assert companion_test_runtime["hp"] == 0
    assert companion_test_runtime["knocked_out"] is True
    dungeon_game.reset_dungeon_companions_after_exit()
    exit_pos = [(x, y) for y, row in enumerate(dungeon_map) for x, tile in enumerate(row) if tile in {"<", "U"}][0]
    assert "exit" in dungeon_game.describe_tile(*exit_pos).lower()

    blocked_for_route = {"#", " ", "$", "P"}
    reachable = {exit_pos}
    queue = deque([exit_pos])
    while queue:
        cx, cy = queue.popleft()
        for ox, oy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = cx + ox, cy + oy
            if not (0 <= ny < len(dungeon_map) and 0 <= nx < len(dungeon_map[0])):
                continue
            if (nx, ny) in reachable or dungeon_map[ny][nx] in blocked_for_route:
                continue
            reachable.add((nx, ny))
            queue.append((nx, ny))
    for y, row in enumerate(dungeon_map):
        for x, tile in enumerate(row):
            if tile not in blocked_for_route:
                assert (x, y) in reachable
            if tile in ["$", "P"]:
                assert any((x + ox, y + oy) in reachable for ox, oy in [(1, 0), (-1, 0), (0, 1), (0, -1)])

    dungeon_enemies = dungeon_game.get_wilderness_dungeon_enemies()
    assert dungeon_enemies
    assert any(enemy.get("boss") for enemy in dungeon_enemies) == (dungeon_max_floor == 1)
    assert all(int(enemy.get("dungeon_floor", 0)) == 1 for enemy in dungeon_enemies)
    dungeon_enemy_bases = {
        "Dustling",
        "Ruin Bat",
        "Moss Haunt",
        "Shardling",
        "Hollow Sentinel",
        "Clockwork Beetle",
        "Relic Archer",
    }
    assert all(str(enemy.get("species", "")).replace("Elite ", "") in dungeon_enemy_bases for enemy in dungeon_enemies)
    assert dungeon_enemy_bases <= set(BattleGame().enemy_roster_names())

    map_combat_enemy = next(enemy for enemy in dungeon_enemies if not enemy.get("boss"))
    map_combat_enemy = dungeon_game.ensure_dungeon_roguelike_enemy(map_combat_enemy)
    assert int(map_combat_enemy["max_hp"]) > 0
    assert str(map_combat_enemy["behavior"])
    player_pos = (dungeon_game.state.player_x, dungeon_game.state.player_y)
    adjacent_combat_pos = next(
        (player_pos[0] + dx, player_pos[1] + dy)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if dungeon_game.active_map()[player_pos[1] + dy][player_pos[0] + dx] in {".", "+", ":", "~", ";"}
        and dungeon_game.dungeon_enemy_passable_tile(
            player_pos[0] + dx,
            player_pos[1] + dy,
            ignore_enemy_id=str(map_combat_enemy["id"]),
        )
    )
    map_combat_enemy["x"], map_combat_enemy["y"] = adjacent_combat_pos
    map_combat_enemy["hp"] = 1
    map_combat_enemy["defense"] = 0
    map_combat_enemy["dodge"] = 0.0
    terrain_before_combat_test = dungeon_game.active_map()[adjacent_combat_pos[1]][adjacent_combat_pos[0]]
    dungeon_game.active_map()[adjacent_combat_pos[1]][adjacent_combat_pos[0]] = "~"
    assert dungeon_game.dungeon_player_move_cost(*adjacent_combat_pos) == 2
    assert dungeon_game.dungeon_terrain_noise_radius(*adjacent_combat_pos) == 4
    dungeon_game.active_map()[adjacent_combat_pos[1]][adjacent_combat_pos[0]] = '"'
    assert dungeon_game.dungeon_terrain_cover(*adjacent_combat_pos) > 0
    dungeon_game.active_map()[adjacent_combat_pos[1]][adjacent_combat_pos[0]] = terrain_before_combat_test
    map_combat_enemy["alert"] = False
    dungeon_game._dungeon_turn_messages = []
    assert dungeon_game.dungeon_emit_noise(*player_pos, 2, label="smoke test") >= 1
    assert map_combat_enemy["alert"]
    assert (map_combat_enemy["heard_x"], map_combat_enemy["heard_y"]) == player_pos
    original_behavior = map_combat_enemy["behavior"]
    map_combat_enemy["behavior"] = "guardian"
    map_combat_enemy["slow"] = False
    map_combat_enemy["intent"] = {}
    dungeon_game.dungeon_enemy_take_turn(map_combat_enemy, 1)
    assert map_combat_enemy["intent"].get("type") == "heavy"
    assert ANSI_CSI_RE.sub("", dungeon_game.render_dungeon_roguelike_enemy(map_combat_enemy)) == "!"
    map_combat_enemy["intent"] = {}
    map_combat_enemy["behavior"] = original_behavior

    dungeon_skills = {skill.name: skill for skill in dungeon_game.dungeon_available_skills()}
    assert {"Spark Shot", "Battle Standard", "Ignite Field", "Flame Fan"} <= set(dungeon_skills)
    assert dungeon_game.dungeon_skill_rank("Spark Shot") == 1
    flame_tiles = dungeon_game.dungeon_skill_affected_tiles(
        player_pos,
        adjacent_combat_pos,
        dungeon_skills["Flame Fan"],
    )
    assert adjacent_combat_pos in flame_tiles
    drawn_dungeon_skill = custom_content.ability_to_skill({
        "name": "Dungeon Pattern Test",
        "effect": "damage",
        "damage": 4,
        "range_max": 5,
        "shape": "custom",
        "custom_pattern": [[0, 0], [1, 0], [1, 1]],
        "pattern_anchor": "target",
        "pattern_rotate": True,
        "armor_pierce": 2,
        "displacement": 1,
        "life_steal": 2,
        "combo_guarded": True,
        "combo_ap_gain": 1,
    })
    drawn_dungeon_tiles = dungeon_game.dungeon_skill_affected_tiles(
        player_pos,
        adjacent_combat_pos,
        drawn_dungeon_skill,
    )
    assert adjacent_combat_pos in drawn_dungeon_tiles
    assert "drawn" in dungeon_game.dungeon_skill_shape_label(drawn_dungeon_skill)

    map_combat_enemy["max_hp"] = 100
    map_combat_enemy["hp"] = 100
    map_combat_enemy["defense"] = 3
    map_combat_enemy["statuses"] = {}
    dungeon_profile = build_player_combat_profile(dungeon_game.state)
    dungeon_game.state.combat_current_hp = int(dungeon_profile["max_hp"]) - 5
    dungeon_game.state.combat_focus = dungeon_game.state.combat_max_focus
    dungeon_game.dungeon_roguelike_record()["guard_turns"] = 2
    drawn_turn_before = int(dungeon_game.dungeon_roguelike_record()["turn"])
    dungeon_game.dungeon_available_skills = lambda: [drawn_dungeon_skill]
    assert dungeon_game.dungeon_cast_skill_at("Dungeon Pattern Test", adjacent_combat_pos)
    assert int(map_combat_enemy["hp"]) == 97
    assert int(dungeon_game.state.combat_current_hp) == int(dungeon_profile["max_hp"]) - 3
    assert int(dungeon_game.dungeon_roguelike_record()["turn"]) == drawn_turn_before
    del dungeon_game.dungeon_available_skills
    map_combat_enemy["x"], map_combat_enemy["y"] = adjacent_combat_pos
    map_combat_enemy["hp"] = 100
    map_combat_enemy["defense"] = 0
    map_combat_enemy["statuses"] = {}
    dungeon_game.dungeon_roguelike_record()["guard_turns"] = 0
    dungeon_game.state.combat_focus = dungeon_game.state.combat_max_focus
    focus_before_skill = dungeon_game.state.combat_focus
    turn_before_skill = int(dungeon_game.dungeon_roguelike_record()["turn"])
    assert dungeon_game.dungeon_cast_skill_at("Spark Shot", adjacent_combat_pos)
    assert int(map_combat_enemy["hp"]) == 100 - int(dungeon_skills["Spark Shot"].damage)
    assert dungeon_game.state.combat_focus == focus_before_skill - int(dungeon_skills["Spark Shot"].mp_cost)
    assert int(dungeon_game.dungeon_roguelike_record()["turn"]) == turn_before_skill + 1

    progress = dungeon_game.combat_progress_for_key("player")
    progress["class"] = "Ranger"
    progress["active_classes"] = ["Ranger"]
    ranger_skills = {skill.name: skill for skill in dungeon_game.dungeon_available_skills()}
    assert "Venom Dart" in ranger_skills
    map_combat_enemy["hp"] = 100
    map_combat_enemy["statuses"] = {}
    dungeon_game.state.combat_focus = dungeon_game.state.combat_max_focus
    assert dungeon_game.dungeon_cast_skill_at("Venom Dart", adjacent_combat_pos)
    assert int(map_combat_enemy["statuses"].get("poison", 0)) > 0
    assert "poison" in dungeon_game.describe_tile(*adjacent_combat_pos).lower()
    progress["class"] = "Vanguard"
    progress["active_classes"] = ["Vanguard"]

    ignite = {skill.name: skill for skill in dungeon_game.dungeon_available_skills()}["Ignite Field"]
    dungeon_game.dungeon_create_skill_zone(ignite, {adjacent_combat_pos})
    assert dungeon_game.dungeon_skill_zone_at(*adjacent_combat_pos)
    assert ANSI_CSI_RE.sub("", dungeon_game.render_dungeon_skill_zone(*adjacent_combat_pos)) == "f"
    map_combat_enemy["x"], map_combat_enemy["y"] = adjacent_combat_pos[0] + 1, adjacent_combat_pos[1]
    assert "field" in dungeon_game.describe_tile(*adjacent_combat_pos).lower()
    map_combat_enemy["x"], map_combat_enemy["y"] = adjacent_combat_pos
    dungeon_game.dungeon_roguelike_record()["skill_zones"] = []

    dungeon_game.state.combat_focus = dungeon_game.state.combat_max_focus
    turn_before_guard = int(dungeon_game.dungeon_roguelike_record()["turn"])
    assert dungeon_game.dungeon_cast_support_skill("Battle Standard", "player")
    assert int(dungeon_game.dungeon_roguelike_record()["guard_turns"]) == 1
    assert int(dungeon_game.dungeon_roguelike_record()["turn"]) == turn_before_guard + 1

    map_combat_enemy["intent"] = {}
    map_combat_enemy["statuses"] = {}
    dungeon_game.state.combat_attack = 99
    map_combat_enemy["hp"] = 1
    enemy_count_before_map_combat = len(dungeon_game.get_wilderness_dungeon_enemies())
    dungeon_turn_before = int(dungeon_game.dungeon_roguelike_record()["turn"])
    random.seed(1)
    dungeon_game.start_wilderness_dungeon_combat_encounter(map_combat_enemy, reason="smoke-bump")
    assert dungeon_game.state.location == "WildernessDungeon"
    assert len(dungeon_game.get_wilderness_dungeon_enemies()) == enemy_count_before_map_combat - 1
    assert int(dungeon_game.dungeon_roguelike_record()["turn"]) == dungeon_turn_before + 1
    dropped_pile = dungeon_game.dungeon_floor_loot_at(*adjacent_combat_pos)
    assert dropped_pile and dropped_pile["source"] == map_combat_enemy["species"]
    assert ANSI_CSI_RE.sub("", dungeon_game.render_tile(*adjacent_combat_pos)) == "*"
    assert "remains" in dungeon_game.describe_tile(*adjacent_combat_pos).lower()
    money_before_floor_loot = dungeon_game.state.money
    inventory_before_floor_loot = sum(int(value) for value in dungeon_game.state.inventory.values())
    assert dungeon_game.collect_dungeon_loot_at(*adjacent_combat_pos, announce=False)
    assert dungeon_game.dungeon_floor_loot_at(*adjacent_combat_pos) is None
    assert (
        dungeon_game.state.money > money_before_floor_loot
        or sum(int(value) for value in dungeon_game.state.inventory.values()) > inventory_before_floor_loot
    )
    dungeon_game.handle_key("NUM5")
    assert int(dungeon_game.dungeon_roguelike_record()["turn"]) == dungeon_turn_before + 2, (
        dungeon_turn_before, int(dungeon_game.dungeon_roguelike_record()["turn"]), dungeon_game.state.message
    )
    dungeon_footer_text = " ".join(ANSI_CSI_RE.sub("", line) for line in dungeon_game.footer_lines())
    assert "WASD/Num move/attack" in dungeon_footer_text
    assert "F aim" in dungeon_footer_text

    trap_x, trap_y = [(x, y) for y, row in enumerate(dungeon_map) for x, tile in enumerate(row) if tile == "!"][0]
    dungeon_game.state.combat_current_hp = 20
    dungeon_game.state.combat_focus = 10
    dungeon_game.trigger_wilderness_dungeon_trap(trap_x, trap_y)
    assert dungeon_game.active_map()[trap_y][trap_x] == ":"
    assert 1 <= dungeon_game.state.combat_current_hp <= 20
    assert any(
        (
            dungeon_game.state.combat_current_hp < 20,
            dungeon_game.state.combat_focus < 10,
            int(dungeon_game.dungeon_roguelike_record().get("poison_turns", 0)) > 0,
            int(dungeon_game.dungeon_roguelike_record().get("root_turns", 0)) > 0,
            "alarm" in dungeon_game.state.message.lower(),
        )
    )
    assert dungeon_game.wilderness_dungeon_feature_id(trap_x, trap_y, 1) in dungeon_game.dungeon_record()["triggered_traps"]

    shrine_x, shrine_y = [(x, y) for y, row in enumerate(dungeon_game.active_map()) for x, tile in enumerate(row) if tile == "S"][0]
    dungeon_game.state.combat_current_hp = 5
    dungeon_game.use_wilderness_dungeon_shrine(shrine_x, shrine_y)
    assert dungeon_game.state.combat_current_hp > 5
    assert dungeon_game.wilderness_dungeon_feature_id(shrine_x, shrine_y, 1) in dungeon_game.dungeon_record()["used_shrines"]

    inscription_x, inscription_y = [(x, y) for y, row in enumerate(dungeon_game.active_map()) for x, tile in enumerate(row) if tile == "?"][0]
    dungeon_loot_items = {"Old Coin", "Ruin Scrap", "Relic Fragment", "Dust Silk", "Stone Sigil", "Ancient Cog", "Bat Wing"}
    inscription_before = sum(int(dungeon_game.state.inventory.get(item, 0)) for item in dungeon_loot_items)
    dungeon_game.read_wilderness_dungeon_inscription(inscription_x, inscription_y)
    inscription_after = sum(int(dungeon_game.state.inventory.get(item, 0)) for item in dungeon_loot_items)
    assert inscription_after > inscription_before
    assert dungeon_game.wilderness_dungeon_feature_id(inscription_x, inscription_y, 1) in dungeon_game.dungeon_record()["read_inscriptions"]

    chest_x, chest_y = [(x, y) for y, row in enumerate(dungeon_map) for x, tile in enumerate(row) if tile == "$"][0]
    money_before_chest = dungeon_game.state.money
    loot_before_chest = sum(int(dungeon_game.state.inventory.get(item, 0)) for item in dungeon_loot_items)
    dungeon_game.open_wilderness_dungeon_chest(chest_x, chest_y)
    assert dungeon_game.active_map()[chest_y][chest_x] == "."
    assert dungeon_game.state.money > money_before_chest
    loot_after_chest = sum(int(dungeon_game.state.inventory.get(item, 0)) for item in dungeon_loot_items)
    assert loot_after_chest > loot_before_chest
    assert dungeon_game.wilderness_dungeon_feature_id(chest_x, chest_y, 1) in dungeon_game.dungeon_record()["opened_chests"]
    while dungeon_game.state.current_dungeon_floor < dungeon_max_floor:
        dungeon_game.descend_wilderness_dungeon()
    assert dungeon_game.state.current_dungeon_floor == dungeon_max_floor
    final_dungeon_symbols = set("".join("".join(row) for row in dungeon_game.active_map()))
    assert "P" in final_dungeon_symbols
    boss_enemy = next(enemy for enemy in dungeon_game.get_wilderness_dungeon_enemies() if enemy.get("boss"))
    assert int(boss_enemy.get("dungeon_floor", 0)) == dungeon_max_floor
    dungeon_game.apply_wilderness_dungeon_battle_result(
        boss_enemy,
        SimpleNamespace(
            outcome="victory",
            defeated_enemies=[boss_enemy["species"]],
            loot={},
            party_status={"Avery": {"hp": 30, "max_hp": 34, "mp": 8, "max_mp": 8, "inventory": {}}},
            return_context={"farm_player_items": {}},
        ),
    )
    assert dungeon_game.dungeon_record()["cleared"] is True
    assert dungeon_game.get_wilderness_dungeon_enemies(create=False) == []

    mega_game = FarmGame()
    mega_coords = None
    for cy in range(-100, 101):
        for cx in range(-100, 101):
            preview_key = f"{cx},{cy}:0,0"
            if (
                mega_game.wilderness_chunk_has_dungeon_site(cx, cy)
                and mega_game.dungeon_is_mega(preview_key)
                and not mega_game.procedural_town_plan(cx, cy)
            ):
                mega_coords = (cx, cy)
                break
        if mega_coords:
            break
    assert mega_coords is not None
    mega_game.state.location = "Wilderness"
    mega_game.set_wilderness_chunk(*mega_coords)
    mega_entrance = next(
        (x, y)
        for y, row in enumerate(mega_game.active_map())
        for x, tile in enumerate(row)
        if mega_game.is_wilderness_dungeon_entrance_at(x, y)
    )
    assert "mega-dungeon" in mega_game.describe_tile(*mega_entrance).lower()
    mega_game.enter_wilderness_dungeon(*mega_entrance)
    mega_key = mega_game.state.current_dungeon_key
    mega_max_floor = mega_game.dungeon_max_floor_for_key(mega_key)
    assert mega_game.dungeon_is_mega(mega_key)
    assert 10 <= mega_max_floor <= 15
    assert mega_game.dungeon_record()["kind"] == "mega"
    assert len({mega_game.dungeon_floor_theme(mega_key, floor) for floor in range(1, mega_max_floor + 1)}) >= 3
    assert mega_game.dungeon_checkpoint_floors(mega_key)
    guardian_floor = 3
    guardian_map = mega_game.get_wilderness_dungeon_map(mega_key, guardian_floor)
    guardian_symbols = set("".join("".join(row) for row in guardian_map))
    assert {">", "P", "S", "?"} <= guardian_symbols
    guardian_enemies = mega_game.get_wilderness_dungeon_enemies(mega_key, guardian_floor)
    guardian = next(enemy for enemy in guardian_enemies if enemy.get("guardian"))
    assert guardian["boss"] is True
    assert guardian["final_boss"] is False
    mega_game.state.current_dungeon_floor = guardian_floor
    mega_game.descend_wilderness_dungeon()
    assert mega_game.state.current_dungeon_floor == guardian_floor
    mega_game.dungeon_defeat_enemy(guardian, "Test explorer")
    assert mega_game.dungeon_record()["cleared"] is False
    assert guardian_floor in mega_game.dungeon_record()["defeated_guardians"]
    mega_game.descend_wilderness_dungeon()
    first_checkpoint = mega_game.dungeon_checkpoint_floors(mega_key)[0]
    assert mega_game.state.current_dungeon_floor == first_checkpoint
    assert mega_game.dungeon_record()["checkpoint_floor"] == first_checkpoint
    refuge_map = mega_game.active_map()
    assert sum(row.count("S") for row in refuge_map) >= 2
    assert "!" not in set("".join("".join(row) for row in refuge_map))
    assert mega_game.get_wilderness_dungeon_enemies(create=True) == []
    final_map = mega_game.get_wilderness_dungeon_map(mega_key, mega_max_floor)
    assert any("P" in row for row in final_map)
    final_guardian = next(
        enemy
        for enemy in mega_game.get_wilderness_dungeon_enemies(mega_key, mega_max_floor)
        if enemy.get("boss")
    )
    assert final_guardian["final_boss"] is True
    mega_game.return_from_wilderness_dungeon("")
    mega_game.enter_wilderness_dungeon(*mega_entrance)
    assert mega_game.state.current_dungeon_floor == first_checkpoint
    assert "Expedition Refuge" in mega_game.dungeon_stratum_name(mega_key, first_checkpoint)
    mega_game.ascend_wilderness_dungeon()
    assert mega_game.state.location == "Wilderness"

    legacy_dungeon_game = FarmGame()
    legacy_key = "9,9:12,12"
    legacy_dungeon_game.state.wilderness_dungeon_state[legacy_key] = {
        "discovered": True,
        "max_floor": 2,
    }
    assert not legacy_dungeon_game.dungeon_is_mega(legacy_key)
    assert legacy_dungeon_game.dungeon_max_floor_for_key(legacy_key) == 2

    with TemporaryDirectory() as temp_dir:
        build_save_path = Path(temp_dir) / "ascii_farmstead_build_mode_smoke_save.json"
        assert build_game.save(quiet=True, path=build_save_path)
        loaded_build_game = FarmGame()
        assert loaded_build_game.load_from_path(build_save_path)
        assert loaded_build_game.state.automation_machines[hopper_new]["seed_qty"] == 7
        assert loaded_build_game.state.artisan_processors[jar_new]["input"] == "Turnip"
        assert loaded_build_game.state.fish_ponds[pond_new]["ready"] == 2
        house_layout_save_path = Path(temp_dir) / "ascii_farmstead_house_layout_smoke_save.json"
        assert house_layout_game.save(quiet=True, path=house_layout_save_path)
        loaded_house_layout_game = FarmGame()
        assert loaded_house_layout_game.load_from_path(house_layout_save_path)
        assert loaded_house_layout_game.house_map[6][15] == "#"
        assert loaded_house_layout_game.state.custom_house_map_rows
        game_table_save_path = Path(temp_dir) / "ascii_farmstead_game_table_smoke_save.json"
        assert game_table_game.save(quiet=True, path=game_table_save_path)
        loaded_game_table_game = FarmGame()
        assert loaded_game_table_game.load_from_path(game_table_save_path)
        assert {"blackjack", "checkers", "chess"} <= set(
            loaded_game_table_game.state.tavern_game_discoveries
        )
        assert loaded_game_table_game.placed_object_at(
            chess_table_position[0] + 1, chess_table_position[1]
        )[1] == "Chess Table"
        assert loaded_game_table_game.store_placed_object_at(
            *chess_table_position, autosave=False
        )
        assert loaded_game_table_game.state.inventory["Chess Table"] == 1
        assert loaded_build_game.state.farm_building_boosts[pond_new] == "baited"
        assert any(animal.get("building_key") == coop_new for animal in loaded_build_game.state.farm_animals)

        actor_save_path = Path(temp_dir) / "ascii_farmstead_actor_smoke_save.json"
        assert actor_game.save(quiet=True, path=actor_save_path)
        loaded_actor_game = FarmGame()
        assert loaded_actor_game.load_from_path(actor_save_path)
        loaded_actor = loaded_actor_game.find_farm_animal(7001)
        assert loaded_actor is not None
        for field, expected in actor_save_fields.items():
            assert loaded_actor[field] == expected

        follower_save_path = Path(temp_dir) / "ascii_farmstead_follower_smoke_save.json"
        assert follower_game.save(quiet=True, path=follower_save_path)
        loaded_follower_game = FarmGame()
        assert loaded_follower_game.load_from_path(follower_save_path)
        assert loaded_follower_game.state.travel_follower_ids == [child_follower_id]
        loaded_follower_record = loaded_follower_game.travel_follower_record(child_follower_id)
        for field in (
            "mode", "task", "task_xp", "work_totals", "work_log", "work_units",
        ):
            assert loaded_follower_record[field] == follower_save_fields[field]
        assert loaded_follower_record["location"] == "Wilderness"
        assert loaded_follower_game.travel_follower_position(child_follower_id) is not None

        formation_save_path = Path(temp_dir) / "ascii_farmstead_formation_smoke_save.json"
        assert formation_game.save(quiet=True, path=formation_save_path)
        loaded_formation_game = FarmGame()
        assert loaded_formation_game.load_from_path(formation_save_path)
        loaded_formation_game.autosave_with_message = (
            lambda message: loaded_formation_game.set_message(message)
        )
        assert loaded_formation_game.state.max_travel_followers == 3
        assert loaded_formation_game.state.travel_follower_ids == [spouse_follower_id, "child:77"]
        loaded_formation_positions = [
            loaded_formation_game.travel_follower_position(follower_id)
            for follower_id in loaded_formation_game.state.travel_follower_ids
        ]
        assert all(position is not None for position in loaded_formation_positions)
        assert len(set(loaded_formation_positions)) == 2
        assert loaded_formation_game.send_all_travel_followers_home()
        assert loaded_formation_game.state.travel_follower_ids == []
        assert all(
            loaded_formation_game.travel_follower_record(follower_id)["mode"] == "home"
            for follower_id in [spouse_follower_id, "child:77"]
        )

        settlement_save_path = Path(temp_dir) / "ascii_farmstead_settlement_builder_smoke_save.json"
        assert settlement_game.save(quiet=True, path=settlement_save_path)
        loaded_settlement_game = FarmGame()
        assert loaded_settlement_game.load_from_path(settlement_save_path)
        loaded_plan = loaded_settlement_game.wilderness_settlement_plan(4, -2)
        assert loaded_plan is not None
        assert loaded_plan["name"] == "Future Market"
        assert loaded_plan["style"] == "Market Ring"
        assert loaded_plan["buildings"][project_id]["phase_index"] == 1
        assert loaded_settlement_game.wilderness_settlement_validation(
            4,
            -2,
            check_terrain=False,
        )["errors"] == []

        population_save_path = Path(temp_dir) / "ascii_farmstead_npc_builder_smoke_save.json"
        assert population_game.save(quiet=True, path=population_save_path)
        loaded_population_game = FarmGame()
        assert loaded_population_game.load_from_path(population_save_path)
        loaded_population = loaded_population_game.procedural_settlement_population(11, -7)
        assert loaded_population is not None
        assert loaded_population["generation"] == 2
        assert loaded_population["residents"][persistent_resident_id]["relationship"] == 42
        assert loaded_population["residents"][persistent_resident_id]["memories"] == ["First hello"]
        assert loaded_population["residents"][persistent_resident_id]["dialogue_count"] == 3
        assert loaded_population["residents"][persistent_resident_id]["recent_dialogue_ids"]
        assert loaded_population["residents"][persistent_resident_id]["active_request"]["status"] == "completed"
        assert procedural_request["id"] in loaded_population["residents"][persistent_resident_id]["completed_request_ids"]
        assert loaded_population_game.procedural_settlement_population_validation(
            11,
            -7,
        ) == {"errors": [], "warnings": []}
        assert loaded_population_game.state.town_npcs == authored_npcs_before_population

        procedural_town_save_path = (
            Path(temp_dir) / "ascii_farmstead_procedural_town_smoke_save.json"
        )
        assert procedural_town_game.save(
            quiet=True,
            path=procedural_town_save_path,
        )
        loaded_procedural_town_game = FarmGame()
        assert loaded_procedural_town_game.load_from_path(procedural_town_save_path)
        loaded_procedural_plan = loaded_procedural_town_game.procedural_town_plan(
            procedural_town_x,
            procedural_town_y,
        )
        assert loaded_procedural_plan is not None
        assert loaded_procedural_plan["name"] == procedural_town_plan["name"]
        assert loaded_procedural_plan["specialty"] == procedural_town_plan["specialty"]
        assert loaded_procedural_plan["discovered"] is True
        loaded_community = loaded_procedural_town_game.ensure_procedural_town_community(
            loaded_procedural_plan
        )
        assert {
            key: value
            for key, value in loaded_community["identity"].items()
            if key not in {"story_quantities", "story_stages", "exports", "imports"}
        } == {
            key: value
            for key, value in community["identity"].items()
            if key not in {"story_quantities", "story_stages", "exports", "imports"}
        }
        assert list(loaded_community["identity"]["story_quantities"]) == list(
            community["identity"]["story_quantities"]
        )
        assert list(loaded_community["identity"]["exports"]) == list(
            community["identity"]["exports"]
        )
        assert list(loaded_community["identity"]["imports"]) == list(
            community["identity"]["imports"]
        )
        assert [
            list(stage)
            for stage in loaded_community["identity"]["story_stages"]
        ] == [
            list(stage)
            for stage in community["identity"]["story_stages"]
        ]
        assert loaded_community["reputation"] == community["reputation"]
        assert loaded_community["development_points"] == community["development_points"]
        assert loaded_community["story_stage"] == community["story_stage"]
        assert loaded_community["event_log"] == community["event_log"]
        assert loaded_community["last_life_year"] == community["last_life_year"]
        assert loaded_community["completed_projects"] == community["completed_projects"]
        assert loaded_community["market_purchases"] == community["market_purchases"]
        assert loaded_community["market_sales"] == community["market_sales"]
        assert loaded_community["commission_log"] == community["commission_log"]
        assert loaded_community["support_claims"] == community["support_claims"]
        assert loaded_community["social_log"] == community["social_log"]
        assert loaded_community["politics"] == community["politics"]
        assert (
            loaded_procedural_town_game.state.primary_residence_id
            == property_record["id"]
        )
        assert (
            loaded_procedural_town_game.state.player_properties[property_record["id"]]
            == property_record
        )
        assert (
            loaded_procedural_town_game.state.player_properties[rental_property["id"]]
            == rental_property
        )
        assert (
            loaded_procedural_town_game.state.player_businesses[business_record["id"]]
            == business_record
        )
        assert (
            loaded_procedural_town_game.state.player_trade_routes[trade_route["id"]]
            == trade_route
        )
        assert (
            loaded_procedural_town_game.state.civic_profile
            == procedural_town_game.state.civic_profile
        )
        assert (
            loaded_procedural_town_game.state.spouse_npc_id
            == romance_resident_id
        )
        assert (
            loaded_procedural_town_game.town_npc_name(romance_resident_id)
            == romance_resident["name"]
        )
        assert (
            loaded_procedural_town_game.state.civic_income_log
            == procedural_town_game.state.civic_income_log
        )
        assert loaded_procedural_town_game.on_procedural_town_interior()
        assert loaded_procedural_town_game.active_map()
        assert (
            loaded_procedural_town_game.current_procedural_town_building()["id"]
            == clinic_building["id"]
        )
        loaded_runtime_population = (
            loaded_procedural_town_game.procedural_settlement_population(
                procedural_town_x,
                procedural_town_y,
            )
        )
        assert loaded_runtime_population is not None
        assert runtime_resident["id"] in loaded_runtime_population["residents"]
        loaded_moving_resident = loaded_runtime_population["residents"][
            runtime_resident["id"]
        ]
        loaded_romance_resident = loaded_runtime_population["residents"][
            romance_resident_id
        ]
        assert loaded_romance_resident["romanceable"] is True
        assert loaded_romance_resident["relationship"] == romance_resident[
            "relationship"
        ]
        loaded_employee = loaded_runtime_population["residents"][
            employee_candidate["id"]
        ]
        assert (
            loaded_employee["workplace_building_id"]
            == business_record["building_id"]
        )
        assert loaded_employee["role"] == "Business Assistant"
        assert (
            loaded_moving_resident["runtime_steps_today"]
            == runtime_resident["runtime_steps_today"]
        )
        assert loaded_moving_resident["last_gift_day"] == runtime_resident["last_gift_day"]
        assert liked_gift in loaded_moving_resident["recent_gifts"]
        assert loaded_moving_resident["relationship"] == runtime_resident["relationship"]
        assert (
            loaded_moving_resident["social_connections"]
            == runtime_resident["social_connections"]
        )
        assert loaded_moving_resident["age_years"] == runtime_resident["age_years"]
        assert loaded_moving_resident["role"] == runtime_resident["role"]
        assert (
            loaded_moving_resident["profession_id"]
            == runtime_resident["profession_id"]
        )
        assert loaded_procedural_town_game.exit_procedural_town_building()
        assert loaded_procedural_town_game.location_label() == procedural_town_plan["name"]
        assert loaded_procedural_town_game.town_map == authored_town_before_runtime

        district_growth_save_path = (
            Path(temp_dir) / "ascii_farmstead_town_district_growth_smoke_save.json"
        )
        assert district_growth_game.save(
            quiet=True,
            path=district_growth_save_path,
        )
        loaded_district_growth_game = FarmGame()
        assert loaded_district_growth_game.load_from_path(
            district_growth_save_path
        )
        loaded_district_plan = loaded_district_growth_game.procedural_town_plan(
            procedural_town_x,
            procedural_town_y,
        )
        assert loaded_district_plan is not None
        loaded_districts = loaded_district_growth_game.ensure_procedural_town_community(
            loaded_district_plan
        )["districts"]
        assert [
            (
                int(district["chunk_x"]),
                int(district["chunk_y"]),
                str(district["kind"]),
                tuple(
                    str(building["id"])
                    for building in district.get("buildings", [])
                ),
            )
            for district in loaded_districts
        ] == [
            (
                int(district["chunk_x"]),
                int(district["chunk_y"]),
                str(district["kind"]),
                tuple(
                    str(building["id"])
                    for building in district.get("buildings", [])
                ),
            )
            for district in districts
        ]
        loaded_entry_district = loaded_districts[0]
        loaded_entry_chunk = (
            int(loaded_entry_district["chunk_x"]),
            int(loaded_entry_district["chunk_y"]),
        )
        assert (
            loaded_district_growth_game.procedural_town_plan(
                *loaded_entry_chunk
            )
            is loaded_district_plan
        )
        loaded_district_map = loaded_district_growth_game.get_wilderness_chunk_map(
            *loaded_entry_chunk
        )
        assert loaded_district_map[19][43] == ":"
        assert loaded_district_growth_game.procedural_settlement_population_validation(
            procedural_town_x,
            procedural_town_y,
        ) == {"errors": [], "warnings": []}

        work_save_game = FarmGame()
        work_save_game.autosave_with_message = lambda message: work_save_game.set_message(message)
        work_save_game.state.spouse_npc_id = "mira_seed"
        work_save_game.state.spouse_moved_to_farm = True
        work_save_game.state.travel_follower_ids = [spouse_follower_id]
        work_save_game.normalize_travel_followers()
        assert work_save_game.assign_travel_follower_task(spouse_follower_id, "water_crops")
        work_record = dict(work_save_game.travel_follower_record(spouse_follower_id))
        work_save_path = Path(temp_dir) / "ascii_farmstead_follower_work_smoke_save.json"
        assert work_save_game.save(quiet=True, path=work_save_path)
        loaded_work_game = FarmGame()
        assert loaded_work_game.load_from_path(work_save_path)
        assert loaded_work_game.state.travel_follower_ids == [spouse_follower_id]
        assert loaded_work_game.travel_follower_record(spouse_follower_id) == work_record

        wedding_save_path = Path(temp_dir) / "elsewhere_wedding_smoke_save.json"
        assert wedding_game.save(quiet=True, path=wedding_save_path)
        loaded_wedding_game = FarmGame()
        assert loaded_wedding_game.load_from_path(wedding_save_path)
        assert loaded_wedding_game.state.engaged_npc_id == remarriage_id
        assert loaded_wedding_game.wedding_date_label() != "not recorded"
        assert loaded_wedding_game.state.marriage_history[-1]["status"] == "widowed"
        assert fiance_id in loaded_wedding_game.state.deceased_spouse_npc_ids

        save_path = Path(temp_dir) / "ascii_farmstead_smoke_save.json"
        assert game.save(quiet=True, path=save_path)
        loaded_game = FarmGame()
        assert loaded_game.load_from_path(save_path)
        assert loaded_game.state.location in VALID_GAME_LOCATIONS
        assert loaded_game.state.town_development_stage == 0
        assert loaded_game.is_town_building_unlocked("blacksmith")
        position_save_path = Path(temp_dir) / "elsewhere_position_recovery.json"
        position_game = FarmGame()
        position_game.state.player_x = 10**12
        position_game.state.player_y = -(10**12)
        assert position_game.save(quiet=True, path=position_save_path)
        loaded_position_game = FarmGame()
        assert loaded_position_game.load_from_path(position_save_path)
        assert 1 <= loaded_position_game.state.player_x < loaded_position_game.active_map_width() - 1
        assert 1 <= loaded_position_game.state.player_y < loaded_position_game.active_map_height() - 1
        mine_save_path = Path(temp_dir) / "ascii_farmstead_mine_smoke_save.json"
        assert mine_game.save(quiet=True, path=mine_save_path)
        loaded_mine_game = FarmGame()
        assert loaded_mine_game.load_from_path(mine_save_path)
        assert loaded_mine_game.is_mine_floor_cleared(1)
        assert loaded_mine_game.mine_floor_stairs_available(1)
        assert loaded_mine_game.get_mine_enemies(1, create=False) == []
        assert loaded_mine_game.state.mine_recent_combat_maps == mine_game.state.mine_recent_combat_maps
        assert loaded_mine_game.state.mine_recent_combat_signatures == mine_game.state.mine_recent_combat_signatures
        stronghold_save_path = Path(temp_dir) / "ascii_farmstead_stronghold_smoke_save.json"
        assert stronghold_game.save(quiet=True, path=stronghold_save_path)
        loaded_stronghold_game = FarmGame()
        assert loaded_stronghold_game.load_from_path(stronghold_save_path)
        loaded_record = loaded_stronghold_game.wilderness_stronghold_record(scx, scy, create=False)
        assert loaded_record.get("cleared") is True
        assert loaded_stronghold_game.get_wilderness_stronghold_enemies(scx, scy, create=False) == []
        loaded_founded_districts = loaded_stronghold_game.founded_town_districts(
            loaded_record
        )
        assert len(loaded_founded_districts) == 1
        assert (
            int(loaded_founded_districts[0]["chunk_x"]),
            int(loaded_founded_districts[0]["chunk_y"]),
        ) == expansion_chunk
        assert loaded_stronghold_game.founded_town_root_context(
            *expansion_chunk
        )[0:2] == (scx, scy)
        loaded_expansion_map = loaded_stronghold_game.get_wilderness_chunk_map(
            *expansion_chunk
        )
        assert loaded_expansion_map[
            int(loaded_founded_districts[0]["build_board_y"])
        ][int(loaded_founded_districts[0]["build_board_x"])] == "n"
        loaded_expanded_plan = loaded_stronghold_game.reclaimed_stronghold_population_plan(
            *expansion_chunk
        )
        assert any(
            building["type_id"] == "clinic"
            and (
                int(building["district_chunk_x"]),
                int(building["district_chunk_y"]),
            ) == expansion_chunk
            for building in loaded_expanded_plan["buildings"].values()
        )
        loaded_municipality = loaded_stronghold_game.ensure_founded_town_municipality(
            loaded_record
        )
        assert int(loaded_municipality["treasury"]) == int(municipality["treasury"])
        assert int(loaded_municipality["lifetime_revenue"]) >= weekly_revenue
        loaded_market_metrics = loaded_stronghold_game.founded_town_site_metrics(
            loaded_record,
            loaded_founded_districts[0],
        )
        assert loaded_market_metrics["label"] in {"Established", "Thriving"}
        assert sum(
            1
            for building in loaded_expanded_plan["buildings"].values()
            if building["type_id"] == "market_stall"
            and (
                int(building["district_chunk_x"]),
                int(building["district_chunk_y"]),
            ) == expansion_chunk
        ) == 2
        field_save_path = Path(temp_dir) / "ascii_farmstead_field_combat_smoke_save.json"
        assert field_combat_game.save(quiet=True, path=field_save_path)
        loaded_field_game = FarmGame()
        assert loaded_field_game.load_from_path(field_save_path)
        assert loaded_field_game.state.wilderness_combat_encounters["12,12"]["resolved"] is True
        assert len(loaded_field_game.state.wilderness_field_loot["12,12"]) == 2
        dungeon_save_path = Path(temp_dir) / "ascii_farmstead_dungeon_smoke_save.json"
        assert dungeon_game.save(quiet=True, path=dungeon_save_path)
        loaded_dungeon_game = FarmGame()
        assert loaded_dungeon_game.load_from_path(dungeon_save_path)
        assert loaded_dungeon_game.state.location == "WildernessDungeon"
        assert loaded_dungeon_game.state.current_dungeon_floor == dungeon_max_floor
        assert loaded_dungeon_game.dungeon_record()["cleared"] is True
        assert ">" not in set("".join("".join(row) for row in loaded_dungeon_game.active_map()))

        safety_save_path = Path(temp_dir) / "elsewhere_save_safety.json"
        safety_game = FarmGame()
        safety_game.state.money = 111
        assert safety_game.save(quiet=True, path=safety_save_path)
        first_document = json.loads(safety_save_path.read_text(encoding="utf-8"))
        assert first_document["save_schema_version"] == support.SAVE_SCHEMA_VERSION
        assert first_document["game_version"] == support.GAME_VERSION
        assert first_document["saved_at_utc"]
        assert not safety_save_path.with_name(
            f"{safety_save_path.name}.tmp"
        ).exists()

        safety_game.state.money = 222
        assert safety_game.save(quiet=True, path=safety_save_path)
        first_backup_path = support.save_backup_path(safety_save_path, 1)
        assert first_backup_path.exists()
        first_backup = json.loads(first_backup_path.read_text(encoding="utf-8"))
        assert first_backup["state"]["money"] == 111

        safety_save_path.write_text("{interrupted", encoding="utf-8")
        recovered_game = FarmGame()
        assert recovered_game.load_from_path(safety_save_path)
        assert recovered_game.state.money == 111
        assert json.loads(
            safety_save_path.read_text(encoding="utf-8")
        )["state"]["money"] == 111
        assert list(Path(temp_dir).glob("elsewhere_save_safety.broken-*.json"))

        committed_document = safety_save_path.read_text(encoding="utf-8")
        original_replace = saves.os.replace

        def fail_live_save_commit(source, destination):
            if (
                Path(destination) == safety_save_path
                and Path(source).name == f"{safety_save_path.name}.tmp"
            ):
                raise OSError("simulated interrupted commit")
            return original_replace(source, destination)

        saves.os.replace = fail_live_save_commit
        try:
            recovered_game.state.money = 333
            assert not recovered_game.save(quiet=True, path=safety_save_path)
        finally:
            saves.os.replace = original_replace
        assert safety_save_path.read_text(encoding="utf-8") == committed_document
        assert not safety_save_path.with_name(
            f"{safety_save_path.name}.tmp"
        ).exists()

        legacy_save_path = Path(temp_dir) / "elsewhere_legacy_save.json"
        legacy_document = json.loads(committed_document)
        legacy_document.pop("save_schema_version", None)
        legacy_document.pop("game_version", None)
        legacy_document.pop("saved_at_utc", None)
        legacy_save_path.write_text(
            json.dumps(legacy_document),
            encoding="utf-8",
        )
        assert FarmGame().load_from_path(legacy_save_path)

        future_save_path = Path(temp_dir) / "elsewhere_future_save.json"
        future_document = json.loads(committed_document)
        future_document["save_schema_version"] = (
            support.SAVE_SCHEMA_VERSION + 1
        )
        future_save_path.write_text(
            json.dumps(future_document),
            encoding="utf-8",
        )
        assert not FarmGame().load_from_path(future_save_path)
        assert list(Path(temp_dir).glob("elsewhere_future_save.broken-*.json"))

        original_data_override = os.environ.get("ELSEWHERE_DATA_DIR")
        override_directory = Path(temp_dir) / "custom_elsewhere_data"
        os.environ["ELSEWHERE_DATA_DIR"] = str(override_directory)
        try:
            assert support.get_game_data_directory() == override_directory
        finally:
            if original_data_override is None:
                os.environ.pop("ELSEWHERE_DATA_DIR", None)
            else:
                os.environ["ELSEWHERE_DATA_DIR"] = original_data_override

    # Universal containers and bounded backpack capacity.
    from ascii_farmstead_inventory import CapacityInventory

    container_game = FarmGame()
    assert isinstance(container_game.state.inventory, CapacityInventory)
    assert container_game.backpack_capacity() == 200
    for item_name in list(container_game.state.inventory):
        container_game.state.inventory[item_name] = 0
    container_game.state.inventory["Tarnished Locket"] = 205
    assert container_game.state.inventory["Tarnished Locket"] == 200
    assert container_game.state.inventory.used_points() == 800
    rejected = container_game.drop_rejected_inventory_near_player()
    assert rejected == {"Tarnished Locket": 5}
    dropped_pack = container_game.dropped_pack_at(
        container_game.state.player_x, container_game.state.player_y
    )
    assert dropped_pack and dropped_pack["contents"]["Tarnished Locket"] == 5
    container_game.state.inventory["Tarnished Locket"] = 0
    assert container_game.take_from_container(
        dropped_pack, "Tarnished Locket", 3, autosave=False
    ) == 3
    assert dropped_pack["contents"]["Tarnished Locket"] == 2
    container_game.state.money = container_game.backpack_upgrade_price()
    container_game.autosave_with_message = lambda message: container_game.set_message(message)
    assert container_game.purchase_backpack_upgrade()
    assert container_game.backpack_capacity() == 250

    container_game.state.location = "HouseInterior"
    chest_x, chest_y = 10, 10
    container_game.state.placed_objects[container_game.obj_key(chest_x, chest_y)] = "Chest"
    chest = container_game.player_container_record(chest_x, chest_y, "Chest")
    assert chest["take_policy"] == "player"
    assert chest["capacity"] == 500
    chest["contents"]["Foreign Coin"] = 2
    assert container_game.take_from_container(chest, "Foreign Coin", 1, autosave=False) == 1
    assert chest["contents"]["Foreign Coin"] == 1
    assert container_game.container_item_sell_price("Foreign Coin") > 0

    # Cached carrying weight must remain exact through every dict mutation,
    # and take-all must skip a large item when compact materials still fit.
    capacity_probe = CapacityInventory({"Wood": 8, "Foreign Coin": 2}, capacity=20)
    assert capacity_probe.used_points() == 16
    capacity_probe["Wood"] = 4
    assert capacity_probe.used_points() == 12
    assert capacity_probe.pop("Foreign Coin") == 2
    assert capacity_probe.used_points() == 4
    capacity_probe.update({"Stone": 4, "Tarnished Locket": 1})
    assert capacity_probe.used_points() == 12
    del capacity_probe["Stone"]
    assert capacity_probe.used_points() == 8
    capacity_probe.clear()
    assert capacity_probe.used_points() == 0

    compact_take_game = FarmGame()
    for item_name in list(compact_take_game.state.inventory):
        compact_take_game.state.inventory[item_name] = 0
    compact_take_game.state.inventory["Tarnished Locket"] = 199
    compact_take_game.state.inventory["Turnip Seeds"] = 1
    compact_record = compact_take_game.create_container_record(
        "compact-take-probe", 1, 1, "crate",
        contents={"Foreign Coin": 1, "Wood": 5},
    )
    compact_take_game.autosave_with_message = lambda message: compact_take_game.set_message(message)
    assert compact_take_game.take_all_from_container(compact_record) == 3
    assert compact_record["contents"] == {"Foreign Coin": 1, "Wood": 2}

    # Container furniture keeps its contents through cursor moves and cannot be
    # packed into inventory while loaded.
    movable_container_game = FarmGame()
    movable_container_game.state.location = "HouseInterior"
    movable_container_game.can_place_object = lambda *_args, **_kwargs: (True, "")
    old_container_key = movable_container_game.obj_key(10, 10)
    movable_container_game.state.placed_objects[old_container_key] = "Chest"
    movable_record = movable_container_game.player_container_record(
        10, 10, "Chest", object_key=old_container_key
    )
    movable_record["contents"] = {"Foreign Coin": 2}
    assert movable_container_game.object_has_attached_state(old_container_key, "Chest")
    assert "empty" in movable_container_game.object_store_block_reason(old_container_key, "Chest")
    assert movable_container_game.move_placed_object(old_container_key, 12, 10, autosave=False)
    new_container_key = movable_container_game.obj_key(12, 10)
    assert movable_record["object_key"] == new_container_key
    assert movable_record["contents"] == {"Foreign Coin": 2}
    assert movable_container_game.player_container_record_for_object_key(
        new_container_key, "Chest"
    ) is movable_record
    movable_record["contents"] = {}
    assert movable_container_game.store_placed_object_at(12, 10, autosave=False)
    assert movable_container_game.player_container_record_for_object_key(
        new_container_key, "Chest"
    ) is None

    # Bulk storage fills available space without deleting overflow.
    bulk_store_game = FarmGame()
    for item_name in list(bulk_store_game.state.inventory):
        bulk_store_game.state.inventory[item_name] = 0
    bulk_store_game.state.inventory["Wood"] = 8
    bulk_store_game.state.inventory["Foreign Coin"] = 3
    bulk_record = bulk_store_game.create_container_record(
        "bulk-store-probe", 1, 1, "crate",
        take_policy="player", allow_deposit=True, capacity=6, contents={},
    )
    bulk_store_game.autosave_with_message = lambda message: bulk_store_game.set_message(message)
    assert bulk_store_game.deposit_all_into_container(bulk_record) == 6
    assert sum(bulk_record["contents"].values()) == 6
    assert sum(bulk_store_game.state.inventory.values()) == 5

    # The Take Items browser collects complete stacks successively without
    # opening the old amount selector between each item.
    rapid_take_game = FarmGame()
    for item_name in list(rapid_take_game.state.inventory):
        rapid_take_game.state.inventory[item_name] = 0
    rapid_take_record = rapid_take_game.create_container_record(
        "rapid-take-probe", 2, 2, "crate",
        contents={"Foreign Coin": 2, "Wood": 5},
    )
    rapid_take_choices = iter([
        MenuItem(label="Foreign Coin", value="item:Foreign Coin", enabled=True),
        MenuItem(label="Wood", value="item:Wood", enabled=True),
        MenuItem(label="Back", value=farmstead_main.MENU_BACK, enabled=True),
    ])
    rapid_take_game.vertical_panel_select = (
        lambda *_args, **_kwargs: next(rapid_take_choices)
    )
    rapid_take_game.vertical_quantity_select = (
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("taking a stack must not open a quantity selector")
        )
    )
    rapid_take_game.autosave_with_message = (
        lambda message: rapid_take_game.set_message(message)
    )
    rapid_take_game.take_container_items_menu(rapid_take_record)
    assert rapid_take_record["contents"] == {"Foreign Coin": 0, "Wood": 0}
    assert rapid_take_game.state.inventory["Foreign Coin"] == 2
    assert rapid_take_game.state.inventory["Wood"] == 5

    # Inspect Contents also remains open so several entries can be examined in
    # one visit.
    rapid_inspect_game = FarmGame()
    rapid_inspect_record = rapid_inspect_game.create_container_record(
        "rapid-inspect-probe", 2, 2, "bookshelf",
        contents={"Old Town Ledger": 1, "Water-Stained Journal": 1},
    )
    rapid_inspect_choices = iter([
        MenuItem(label="Old Town Ledger", value="item:Old Town Ledger", enabled=True),
        MenuItem(label="Water-Stained Journal", value="item:Water-Stained Journal", enabled=True),
        MenuItem(label="Back", value=farmstead_main.MENU_BACK, enabled=True),
    ])
    inspected_titles = []
    rapid_inspect_game.vertical_panel_select = (
        lambda *_args, **_kwargs: next(rapid_inspect_choices)
    )
    rapid_inspect_game.vertical_panel_view = (
        lambda title, *_args, **_kwargs: inspected_titles.append(str(title))
    )
    rapid_inspect_game.inspect_container_contents_menu(rapid_inspect_record)
    assert inspected_titles == ["Old Town Ledger", "Water-Stained Journal"]

    # Interior chairs are not accidental loot cabinets. Real wilderness shelves
    # remain containers.
    semantic_container_game = FarmGame()
    semantic_container_game.state.location = "WildernessStructure"
    structure_map = semantic_container_game.active_map()
    chair_position = next(
        (x, y)
        for y, row in enumerate(structure_map)
        for x, tile in enumerate(row)
        if tile == "c"
    )
    shelf_position = next(
        (x, y)
        for y, row in enumerate(structure_map)
        for x, tile in enumerate(row)
        if tile == "s"
    )
    assert semantic_container_game.static_container_profile_at(*chair_position) is None
    assert semantic_container_game.static_container_profile_at(*shelf_position)[0] == "crate"

    # Physical cargo, carts, nests, and remains at wilderness combat sites now
    # use the persistent container loop instead of being flavor-only scenery.
    encounter_container_game = FarmGame()
    encounter_container_game.state.location = "Wilderness"
    encounter_container_game.state.wilderness_chunk_x = 7
    encounter_container_game.state.wilderness_chunk_y = -4
    encounter_visual = {"x": 8, "y": 9, "name": "Salvage Crate"}
    encounter_container_game.wilderness_random_combat_visual_at = (
        lambda x, y: encounter_visual if (int(x), int(y)) == (8, 9) else None
    )
    encounter_container_game.wilderness_random_combat_record = (
        lambda *_args, **_kwargs: {"id": "encounter:container-smoke"}
    )
    encounter_record = encounter_container_game.world_container_at(8, 9)
    assert encounter_record and encounter_record["name"] == "Salvage Crate"
    assert encounter_visual["container"] is encounter_record
    assert encounter_container_game.world_container_at(8, 9) is encounter_record
    assert encounter_record["contents"]

    # Dungeon chest browsing retains the dungeon's depth/theme-aware reward
    # table and records depletion for legacy save compatibility.
    dungeon_container_game = FarmGame()
    dungeon_container_game.state.location = "WildernessDungeon"
    dungeon_container_game.state.current_dungeon_key = "container-dungeon"
    dungeon_container_game.state.current_dungeon_floor = 6
    dungeon_container_grid = [["." for _ in range(7)] for _ in range(7)]
    dungeon_container_grid[3][3] = "$"
    dungeon_container_game.active_map = lambda: dungeon_container_grid
    dungeon_container_game.in_active_bounds = (
        lambda x, y: 0 <= int(y) < 7 and 0 <= int(x) < 7
    )
    dungeon_container_record = {"opened_chests": []}
    dungeon_container_game.dungeon_record = lambda _key: dungeon_container_record
    dungeon_container_game.wilderness_dungeon_chest_loot = (
        lambda *_args: (37, {"Copper Ore": 2, "Relic Fragment": 1})
    )
    dungeon_chest = dungeon_container_game.dungeon_chest_container_at(3, 3)
    assert dungeon_chest["money"] == 37
    assert dungeon_chest["contents"] == {"Copper Ore": 2, "Relic Fragment": 1}
    dungeon_chest["money"] = 0
    dungeon_chest["contents"] = {}
    dungeon_container_game.remove_empty_loot_pile(dungeon_chest)
    assert dungeon_chest["dungeon_chest_id"] in dungeon_container_record["opened_chests"]

    # Authored fixtures are location-aware: real stock and storage are
    # containers, while reused glyphs such as the carpenter's sawhorse are not.
    authored_fixture_game = FarmGame()
    authored_fixture_game.in_active_bounds = lambda x, y: 0 <= int(x) < 3 and 0 <= int(y) < 3
    authored_grid = [["." for _ in range(3)] for _ in range(3)]
    authored_fixture_game.active_map = lambda: authored_grid
    authored_fixture_game.state.location = "GeneralStoreInterior"
    authored_grid[1][1] = "s"
    assert authored_fixture_game.static_container_profile_at(1, 1)[0] == "store_seeds"
    authored_fixture_game.state.location = "ClinicInterior"
    authored_grid[1][1] = "m"
    assert authored_fixture_game.static_container_profile_at(1, 1)[0] == "clinic_cabinet"
    authored_fixture_game.state.location = "CarpenterStoreInterior"
    authored_grid[1][1] = "s"
    assert authored_fixture_game.static_container_profile_at(1, 1) is None
    authored_grid[1][1] = "l"
    assert authored_fixture_game.static_container_profile_at(1, 1)[0] == "lumber_crate"
    authored_fixture_game.state.location = "GeneralStoreInterior"
    authored_grid[1][1] = "H"
    assert authored_fixture_game.static_container_profile_at(1, 1)[:2] == (
        "store_general_goods",
        "display",
    )
    authored_fixture_game.state.location = "TownResidenceInterior"
    authored_grid[1][1] = "y"
    assert authored_fixture_game.static_container_profile_at(1, 1)[:2] == (
        "storage_chest",
        "theft",
    )

    # Procedural businesses use their own semantic stock profiles, while a
    # residence remains owned storage rather than generic free loot.
    procedural_fixture_game = FarmGame()
    procedural_fixture_game.state.location = "ProceduralSettlementInterior"
    procedural_fixture_game.in_active_bounds = lambda x, y: 0 <= int(x) < 3 and 0 <= int(y) < 3
    procedural_grid = [["." for _ in range(3)] for _ in range(3)]
    procedural_grid[1][1] = "s"
    procedural_fixture_game.active_map = lambda: procedural_grid
    procedural_fixture_game.current_procedural_town_building = lambda: {"type_id": "clinic"}
    procedural_fixture_game.on_player_owned_procedural_residence = lambda: False
    procedural_profile = procedural_fixture_game.static_container_profile_at(1, 1)
    assert procedural_profile[:2] == ("clinic_supply", "display")
    procedural_fixture_game.current_procedural_town_building = lambda: {"type_id": "residence"}
    procedural_profile = procedural_fixture_game.static_container_profile_at(1, 1)
    assert procedural_profile[:2] == ("shelf", "theft")
    procedural_grid[1][1] = "H"
    procedural_fixture_game.current_procedural_town_building = lambda: {"type_id": "library"}
    procedural_profile = procedural_fixture_game.static_container_profile_at(1, 1)
    assert procedural_profile[:2] == ("civic_archive", "display")
    procedural_grid[1][1] = "y"
    procedural_fixture_game.current_procedural_town_building = lambda: {"type_id": "home"}
    procedural_profile = procedural_fixture_game.static_container_profile_at(1, 1)
    assert procedural_profile[:2] == ("storage_chest", "theft")
    procedural_grid[1][1] = "W"
    procedural_fixture_game.current_procedural_town_building = lambda: {"type_id": "clinic"}
    procedural_profile = procedural_fixture_game.static_container_profile_at(1, 1)
    assert procedural_profile[:2] == ("clinic_cabinet", "display")

    # Generated fixtures resolve through their room purpose, so the same glyph
    # can be a dresser, desk, guest nightstand, archive, or evidence locker.
    room_fixture_cases = (
        ("home", {"role": "bedroom", "source_id": "bedroom_2"}, "d", "household_dresser", "theft"),
        ("inn", {"role": "guest_room", "source_id": "guest_1"}, "d", "guest_nightstand", "theft"),
        ("clinic", {"role": "examination", "source_id": "exam_1"}, "+", "clinic_cabinet", "theft"),
        ("library", {"role": "stacks", "source_id": "stacks"}, "l", "library_shelf", "display"),
        ("sheriff_office", {"role": "storage", "source_id": "evidence"}, "s", "evidence_locker", "theft"),
        ("general_store", {"role": "sales", "source_id": "sales"}, "$", "store_general_goods", "display"),
    )
    for building_type, room_record, tile, expected_profile, expected_policy in room_fixture_cases:
        procedural_grid[1][1] = tile
        procedural_fixture_game.current_procedural_town_building = (
            lambda building_type=building_type: {
                "id": f"room-profile:{building_type}",
                "type_id": building_type,
                "name": f"Profile {building_type}",
            }
        )
        procedural_fixture_game.procedural_town_room_at_position = (
            lambda *_args, room_record=room_record, **_kwargs: dict(room_record)
        )
        procedural_fixture_game.on_player_owned_procedural_residence = lambda: False
        profile = procedural_fixture_game.static_container_profile_at(1, 1)
        assert profile[:2] == (expected_profile, expected_policy)
        record = procedural_fixture_game.world_container_at(1, 1)
        assert record["profile"] == expected_profile
        assert record["take_policy"] == expected_policy
        assert record["contents"]
        assert procedural_fixture_game.world_container_at(1, 1) is record
        procedural_fixture_game.state.world_containers.clear()

    # Generated dungeon floors contain several distinct, wall-hugging minor
    # containers in addition to treasure chests.
    generated_container_game = FarmGame()
    generated_container_game.state.wilderness_seed = 104729
    generated_dungeon = generated_container_game.make_wilderness_dungeon_map(
        "container-variety-dungeon", 3
    )
    minor_positions = [
        (x, y, tile)
        for y, row in enumerate(generated_dungeon)
        for x, tile in enumerate(row)
        if tile in {"l", "s", "u"}
    ]
    assert len(minor_positions) >= 3
    assert len({tile for _x, _y, tile in minor_positions}) == 3
    assert all(
        any(
            generated_dungeon[y + dy][x + dx] == "#"
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
        for x, y, _tile in minor_positions
    )
    generated_container_game.state.location = "WildernessDungeon"
    generated_container_game.state.current_dungeon_key = "container-variety-dungeon"
    generated_container_game.state.current_dungeon_floor = 3
    generated_container_game.active_map = lambda: generated_dungeon
    generated_container_game.in_active_bounds = lambda x, y: (
        0 <= int(y) < len(generated_dungeon)
        and 0 <= int(x) < len(generated_dungeon[int(y)])
    )
    expected_minor_profiles = {
        "l": "dungeon_archive", "s": "dungeon_supply", "u": "dungeon_urn",
    }
    for x, y, tile in minor_positions:
        profile = generated_container_game.static_container_profile_at(x, y)
        assert profile and profile[0] == expected_minor_profiles[tile]
        record = generated_container_game.world_container_at(x, y)
        assert record and record["contents"]

    # Recovered practical items are usable, valuable, and rare carried tools
    # contribute their passive dungeon bonuses.
    from ascii_farmstead_containers import CONTAINER_ITEM_DATA

    useful_loot_game = FarmGame()
    for item_name in list(useful_loot_game.state.inventory):
        useful_loot_game.state.inventory[item_name] = 0
    useful_loot_game.autosave_with_message = lambda message: useful_loot_game.set_message(message)
    useful_profile = build_player_combat_profile(useful_loot_game.state)
    useful_loot_game.state.combat_current_hp = int(useful_profile["max_hp"]) - 15
    useful_loot_game.state.inventory["Field Bandage"] = 1
    assert useful_loot_game.is_inventory_consumable_item("Field Bandage")
    assert useful_loot_game.use_consumable_item("Field Bandage")
    assert useful_loot_game.state.combat_current_hp == int(useful_profile["max_hp"])
    useful_loot_game.state.stamina = max(0, useful_loot_game.max_stamina() - 20)
    useful_loot_game.state.inventory["Restorative Salts"] = 1
    assert useful_loot_game.use_consumable_item("Restorative Salts")
    assert useful_loot_game.state.stamina == useful_loot_game.max_stamina()
    useful_loot_game.state.inventory["Surveyor's Lens"] = 1
    useful_loot_game.state.inventory["Locksmith's Roll"] = 1
    assert useful_loot_game.container_passive_bonus("trap_scout") == 0.12
    assert useful_loot_game.container_passive_bonus("trap_disarm") == 0.12
    assert "trap discovery" in " ".join(
        useful_loot_game.container_item_detail_lines("Surveyor's Lens")
    )
    for item_name, item_data in CONTAINER_ITEM_DATA.items():
        assert int(item_data.get("value", 0) or 0) > 0, item_name
        assert useful_loot_game.container_item_sell_price(item_name) > 0

    # Stealing currency has the same ownership consequence as stealing items.
    theft_container_game = FarmGame()
    theft_penalties = []
    theft_container_game.current_procedural_town_plan = lambda: {"name": "Test Town"}
    theft_container_game.adjust_procedural_town_reputation = (
        lambda amount, reason: theft_penalties.append((amount, reason))
    )
    theft_record = theft_container_game.create_container_record(
        "theft-money-probe", 1, 1, "cabinet",
        take_policy="theft", contents={},
    )
    theft_record["money"] = 25
    assert theft_container_game.take_container_money(theft_record, autosave=False) == 25
    assert theft_penalties == [(-3, "Took property without permission")]

    # Learned abilities can safely and persistently reshape ordinary world tiles.
    from ascii_battle_prototype.combat.models import Skill
    from ascii_battle_prototype.combat.skills import create_default_skills
    from ascii_farmstead_combat import farmstead_combat_profile

    magic_game = FarmGame()
    magic_game.state.location = "Farm"
    magic_game.state.player_x, magic_game.state.player_y = 10, 10
    magic_game.state.combat_focus = 30
    magic_game.autosave_with_message = lambda message: magic_game.set_message(message)
    learned_ability_names = {
        skill.name for skill in magic_game.dungeon_available_skills()
    }
    persistent_ability_names = {
        skill.name for skill in magic_game.player_ability_menu_skills()
    }
    assert learned_ability_names <= persistent_ability_names
    assert "Water Weave" in persistent_ability_names

    support_skill = Skill(
        "Test Field Aid", mp_cost=3, damage=0, range_max=99,
        shape="support", effect="heal", heal_amount=7,
    )
    magic_profile = farmstead_combat_profile(magic_game.state)
    magic_game.state.combat_current_hp = int(magic_profile["max_hp"]) - 8
    support_hp_before = magic_game.state.combat_current_hp
    assert magic_game.world_cast_support_ability(support_skill)
    assert magic_game.state.combat_current_hp > support_hp_before

    guard_skill = Skill(
        "Test Guard", mp_cost=2, damage=0, range_max=99,
        shape="support", effect="guard",
    )
    assert magic_game.world_cast_support_ability(guard_skill)
    magic_game.state.location = "Wilderness"
    magic_game.state.wilderness_chunk_x = 0
    magic_game.state.wilderness_chunk_y = 0
    assert magic_game.begin_wilderness_field_combat({
        "id": "prepared-guard-test", "species": "Bandit",
        "x": 12, "y": 10, "floor": 1,
    })
    assert magic_game.wilderness_field_combat_record()["guard_turns"] == 2
    magic_game.end_wilderness_field_combat("Prepared guard smoke complete.")
    magic_game.state.location = "Farm"

    upgraded_skills = {
        skill.name: skill for skill in create_default_skills()
    }
    assert upgraded_skills["Spark Shot"].combo_mp_gain == 1
    assert upgraded_skills["Shatter Shot"].armor_pierce == 3
    assert upgraded_skills["Flame Burst"].zone_type == "fire"
    assert upgraded_skills["Toxic Cloud"].zone_duration == 3

    frost_skill = Skill(
        "Test Ice Lance", mp_cost=4, damage=1, range_max=5,
        shape="point", description="Freeze water into ice.",
    )
    magic_game.base_map[10][12] = "~"
    assert magic_game.world_magic_cast_at(frost_skill, (12, 10))
    assert magic_game.world_magic_effect_at(12, 10)["kind"] == "ice"
    assert magic_game.passable(12, 10)

    fire_skill = Skill(
        "Test Fireball", mp_cost=4, damage=1, range_max=5,
        shape="point", description="Ignite dry brush.",
    )
    magic_game.base_map[11][12] = "^"
    assert magic_game.world_magic_cast_at(fire_skill, (12, 11))
    assert magic_game.world_magic_effect_at(12, 11)["kind"] == "fire"
    assert not magic_game.passable(12, 11)

    water_skill = Skill(
        "Test Tidal Wash", mp_cost=4, damage=0, range_max=5,
        shape="point", description="Water terrain.",
    )
    assert magic_game.world_magic_cast_at(water_skill, (12, 11))
    assert magic_game.world_magic_effect_at(12, 11)["kind"] == "steam"

    wind_skill = Skill(
        "Test Trail Gust", mp_cost=3, damage=0, range_max=5,
        shape="point", description="Disperse exposed magic with wind.",
    )
    assert magic_game.world_magic_cast_at(wind_skill, (12, 11))
    assert not magic_game.world_magic_effect_at(12, 11)

    crop_x, crop_y = 13, 10
    magic_game.base_map[crop_y][crop_x] = ","
    magic_game.set_crop(crop_x, crop_y, state.Crop("Turnip"))
    assert magic_game.world_magic_cast_at(water_skill, (crop_x, crop_y))
    assert magic_game.get_crop(crop_x, crop_y).watered
    assert magic_game.base_map[crop_y][crop_x] == "w"
    protected_crop_focus = magic_game.state.combat_focus
    assert not magic_game.world_magic_cast_at(frost_skill, (crop_x, crop_y))
    assert magic_game.state.combat_focus == protected_crop_focus

    nature_skill = Skill(
        "Test Nature Bloom", mp_cost=4, damage=0, range_max=5,
        shape="point", description="Encourage natural growth.",
    )
    crop_age = magic_game.get_crop(crop_x, crop_y).age
    assert magic_game.world_magic_cast_at(nature_skill, (crop_x, crop_y))
    assert magic_game.get_crop(crop_x, crop_y).age == crop_age + 1
    focus_before_repeat = magic_game.state.combat_focus
    assert not magic_game.world_magic_cast_at(nature_skill, (crop_x, crop_y))
    assert magic_game.state.combat_focus == focus_before_repeat

    reaction_x, reaction_y = 14, 10
    magic_game.base_map[reaction_y][reaction_x] = "."
    assert magic_game.world_magic_cast_at(water_skill, (reaction_x, reaction_y))
    storm_skill = Skill(
        "Test Spark Shot", mp_cost=4, damage=1, range_max=5,
        shape="point", description="Charge wet ground with storm magic.",
    )
    assert magic_game.world_magic_cast_at(storm_skill, (reaction_x, reaction_y))
    assert magic_game.world_magic_effect_at(reaction_x, reaction_y)["kind"] == "electrified"
    assert not magic_game.passable(reaction_x, reaction_y)
    earth_skill = Skill(
        "Test Stone Path", mp_cost=4, damage=0, range_max=5,
        shape="point", description="Ground unstable magic with earth.",
    )
    assert magic_game.world_magic_cast_at(earth_skill, (reaction_x, reaction_y))
    assert magic_game.world_magic_effect_at(reaction_x, reaction_y)["kind"] == "cleared"

    magic_game.state.world_magic_cast_counts["storm"] = 30
    assert magic_game.world_magic_mastery_label("storm") == "Adept"
    assert magic_game.world_magic_field_cost(storm_skill) == 1
    assert magic_game.world_magic_duration("charged", "storm") > 90

    bridge_x, bridge_y = 14, 11
    magic_game.base_map[bridge_y][bridge_x] = "~"
    magic_game.world_magic_set_effect(bridge_x, bridge_y, "ice", 1, "test thaw", original_tile="~")
    magic_game.state.player_x, magic_game.state.player_y = bridge_x, bridge_y
    magic_game.advance_time(2)
    assert magic_game.world_magic_effect_at(bridge_x, bridge_y)["kind"] == "ice"
    assert "another 15 minutes" in magic_game.state.message

    magic_game.state.weather = "Rainy"
    magic_game.base_map[12][12] = "."
    assert magic_game.world_magic_cast_at(fire_skill, (12, 12))
    assert magic_game.world_magic_effect_at(12, 12)["kind"] == "wet"
    assert custom_content.sanitize_custom_ability({
        "name": "Canal Maker", "effect": "damage", "damage": 1,
        "world_element": "Water",
    })["world_element"] == "Water"

    spread_game = FarmGame()
    spread_game.state.location = "Wilderness"
    spread_game.state.player_x, spread_game.state.player_y = 18, 20
    spread_grid = spread_game.active_map()
    spread_grid[20][20] = "^"
    spread_grid[20][21] = "."
    for blocked_x, blocked_y in ((19, 20), (20, 19), (20, 21)):
        spread_grid[blocked_y][blocked_x] = "#"
    spread_game.world_magic_set_effect(20, 20, "fire", 120, "spread test", original_tile="^")
    spread_game.advance_time(21)
    assert spread_game.world_magic_effect_at(21, 20)["kind"] == "fire"
    spread_grid[20][22] = "."
    spread_game.world_magic_set_effect(22, 20, "wet", 180, "firebreak test", original_tile=".")
    spread_game.advance_time(21)
    assert spread_game.world_magic_effect_at(22, 20)["kind"] == "wet"

    # Field targeting treats neighboring wilderness chunks as one visible space.
    seam_magic_game = FarmGame()
    seam_magic_game.state.location = "Wilderness"
    seam_magic_game.state.combat_focus = 30
    current_grid = seam_magic_game.active_map()
    chunk_width = len(current_grid[0])
    seam_magic_game.state.player_x, seam_magic_game.state.player_y = chunk_width - 2, 20
    neighbor_x = int(seam_magic_game.state.wilderness_chunk_x) + 1
    neighbor_y = int(seam_magic_game.state.wilderness_chunk_y)
    neighbor_grid = seam_magic_game.get_wilderness_chunk_map(neighbor_x, neighbor_y)
    neighbor_grid[20][1] = "~"
    seam_target = (chunk_width + 1, 20)
    assert seam_magic_game.world_magic_shape_tiles(
        (seam_magic_game.state.player_x, seam_magic_game.state.player_y), seam_target, frost_skill,
    ) == {seam_target}
    seam_magic_game.world_magic_set_preview({seam_target}, "frost")
    assert seam_magic_game.world_magic_preview_render_at(1, 20, neighbor_x, neighbor_y)
    seam_magic_game.world_magic_clear_preview()
    assert not seam_magic_game.world_magic_preview_render_at(1, 20, neighbor_x, neighbor_y)
    assert seam_magic_game.world_magic_cast_at(frost_skill, seam_target)
    seam_effect = seam_magic_game.world_magic_effect_at(1, 20, neighbor_x, neighbor_y)
    assert seam_effect["kind"] == "ice"
    assert seam_effect["chunk_x"] == neighbor_x
    assert seam_effect["x"] == 1
    assert seam_magic_game.state.last_world_magic_ability == frost_skill.name
    seam_magic_game.state.last_world_magic_ability = "Water Weave"
    assert seam_magic_game.world_magic_last_skill().name == "Water Weave"

    prepared_magic_state = prepare_loaded_state_data({
        "world_magic_effects": magic_game.state.world_magic_effects,
        "world_magic_tile_cooldowns": magic_game.state.world_magic_tile_cooldowns,
        "world_magic_cast_counts": magic_game.state.world_magic_cast_counts,
        "last_world_magic_ability": "Water Weave",
    })
    reloaded_magic_state = GameState(**prepared_magic_state)
    assert reloaded_magic_state.world_magic_effects
    assert reloaded_magic_state.world_magic_cast_counts.get("frost", 0) == 1
    assert reloaded_magic_state.last_world_magic_ability == "Water Weave"

    print("Elsewhere smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
