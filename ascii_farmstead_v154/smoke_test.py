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
import re

import ascii_farmstead_data as data
import ascii_farmstead_actors as actors
import ascii_farmstead_building as building
import ascii_farmstead_custom_content as custom_content
import ascii_farmstead_custom_extended as custom_extended
import ascii_farmstead_dynasty as dynasty
import ascii_farmstead_helpers as helpers
import ascii_farmstead_inventory as inventory
import ascii_farmstead_npcs as npcs
import ascii_farmstead_saves as saves
import ascii_farmstead_state as state
import ascii_farmstead_town_builder as town_builder
import ascii_farmstead_npc_builder as npc_builder
import ascii_farmstead_npc_dialogue as npc_dialogue
import ascii_farmstead_procedural_towns as procedural_towns
import ascii_farmstead_support as support
import ascii_farmstead_ui as ui
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
    assert support.GAME_VERSION == "0.9.0-beta.2"
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
        custom_library = {
            "version": 1,
            "abilities": [
                {
                    "name": "Seed Shot",
                    "description": "A precise custom starter.",
                    "effect": "damage",
                    "mp_cost": 2,
                    "damage": 4,
                    "range_max": 5,
                    "shape": "point",
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
                }
            ],
        }
        saved, save_message = custom_content.save_custom_content(custom_library)
        assert saved, save_message
        loaded_custom, custom_warnings = custom_content.load_custom_content()
        assert not custom_warnings
        assert loaded_custom["abilities"][0]["name"] == "Seed Shot"
        assert custom_content.ability_balance_label(loaded_custom["abilities"][0])
        custom_battle_game = BattleGame()
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
        assert building_record["name"] == "Archive Cottage"
        assert building_record["max_occupancy"] == 8
        assert building_record["zones"][0]["kind"] == "bedroom"
        assert building_record["colors"][0] == {"floor": 0, "x": 9, "y": 5, "color": "blue"}
        assert building_record["spawns"][0] == {"floor": 0, "x": 11, "y": 6}
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
        assert custom_home_interior[5][9] == "d"
        assert custom_home_interior[5][10] == "P"
        assert custom_home_interior[7][9] == "|"
        assert custom_home_interior[7][10] == "_"
        assert custom_building_game.procedural_town_interior_tile_passable("|")
        assert not custom_building_game.procedural_town_interior_tile_passable("_")
        assert custom_building_game.procedural_town_custom_tile_color_key(9, 5) == "blue"
        assert custom_building_game.procedural_town_template_spawn_anchors(
            custom_plan,
            home_template_building,
        )[0] == (11, 6)
        custom_building_game.use_procedural_town_interior_action(10, 7)
        assert custom_home_interior[7][10] == "|"
        custom_building_game.use_procedural_town_interior_action(10, 7)
        assert custom_home_interior[7][10] == "_"
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
    assert loaded_state.marriage_month == 0
    assert loaded_state.family_event_log == []
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
    assert "visited:Wilderness" in spouse_record["memory_flags"]
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
    found_item = follower_game.travel_follower_outing_find(spouse_follower_id, "Wilderness")
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

    procedural_builder = npc_builder.ProceduralNpcBuilder()
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
    assert procedural_builder.validate(
        generated_population,
        population_plan,
    ) == {"errors": [], "warnings": []}
    generated_ids = set(generated_population["residents"])
    assert len(generated_ids) == population_summary["population"]
    for generated_household in generated_population["households"].values():
        assert generated_household["head_resident_id"] in generated_household["member_ids"]
    for generated_resident in generated_population["residents"].values():
        assert set(npc_builder.PROCEDURAL_ROUTINE_PHASES).issubset(
            generated_resident["schedule"]
        )
        assert generated_resident["home_building_id"] in population_plan["buildings"]
        assert population_plan["buildings"][generated_resident["home_building_id"]]["phase_index"] == 3
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
    assert (
        abs(procedural_town_chunk[0]) + abs(procedural_town_chunk[1])
        <= 2 * (procedural_towns.PROCEDURAL_TOWN_GRID_SIZE - 1)
    )
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
    ) == procedural_towns.PROCEDURAL_TOWN_OVERWORLD_SYMBOL
    assert any(
        mapped_town_name in line and "unvisited" in line.lower()
        for line in procedural_town_game.overworld_chunk_detail_lines(
            procedural_town_x,
            procedural_town_y,
        )
    )
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
    assert procedural_town_plan["map_applied"] is True
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
    runtime_resident_positions = procedural_town_game.procedural_town_resident_position_lookup()
    assert runtime_resident_positions
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
    assert not procedural_town_game.passable(*runtime_resident_position)
    assert runtime_resident["name"] in procedural_town_game.interaction_hint(
        *runtime_resident_position
    )
    procedural_town_game.state.hour = 12
    procedural_town_game.update_procedural_town_residents(force_reanchor=True)
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
    assert any(
        resident["runtime_steps_today"] > 0
        for resident in procedural_runtime_population["residents"].values()
    )
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
    assert resident_menu_labels == [
        "Talk",
        "Give gift",
        "Ask rumor",
        "Request",
        "Profile",
        "Status",
        "Back",
    ]
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
    assert procedural_town_game.procedural_town_building_door_at(
        town_hall_building["door_x"],
        town_hall_building["door_y"],
    ) == town_hall_building
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
    assert procedural_town_game.procedural_town_resident_position_lookup()
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
    original_building_service = procedural_town_game.procedural_town_building_service
    generated_shape_signatures = set()
    generated_shape_signatures_by_type = {}
    generated_building_counts_by_type = {}
    generated_service_positions = set()
    try:
        for proc_building in procedural_interior_buildings:
            procedural_town_game.state.location = procedural_towns.PROCEDURAL_TOWN_INTERIOR_LOCATION
            procedural_town_game.state.current_procedural_settlement_key = (
                f"{procedural_town_plan['chunk_x']},{procedural_town_plan['chunk_y']}"
            )
            procedural_town_game.state.current_procedural_building_id = str(proc_building["id"])
            grid = procedural_town_game.procedural_town_interior_map(proc_building)
            door_x = len(grid[0]) // 2
            door_y = len(grid) - 1
            procedural_town_game.state.player_x = door_x
            procedural_town_game.state.player_y = door_y - 2
            assert len(grid[0]) >= 60
            assert len(grid) >= 26
            assert grid[door_y][door_x] == "D"
            assert grid[0][0] == " "
            for lane_y in range(18, door_y):
                for lane_x in range(door_x - 1, door_x + 2):
                    assert grid[lane_y][lane_x] == ".", (
                        f"{proc_building['type_id']} front approach cluttered at {lane_x},{lane_y}"
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
                    if (
                        (nx, ny) in seen
                        or not (0 <= ny < len(grid) and 0 <= nx < len(grid[ny]))
                        or grid[ny][nx] in procedural_blocking_tiles
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
            service_calls = []
            procedural_town_game.procedural_town_building_service = (
                lambda service_building, service_calls=service_calls: service_calls.append(service_building["id"]) or True
            )
            sx, sy = service_positions[0]
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
    procedural_town_game.state.stamina = 20
    assert procedural_town_game.use_procedural_town_special_service(inn_building)
    assert procedural_town_game.state.stamina == 55
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
    assert procedural_town_game.get_placed_object(8, 8) == "Bed"
    assert procedural_town_game.get_placed_object(17, 8) == "Wall Calendar"
    assert procedural_town_game.get_placed_object(49, 8) == "Television"
    assert procedural_town_game.get_placed_object(9, 16) == "Kitchen Counter"
    assert procedural_town_game.active_map()[8][8] == "."
    assert procedural_town_game.active_map()[16][9] == "."
    assert procedural_town_game.can_hold_objects_here()
    assert procedural_town_game.can_place_object("Wooden Chair", 18, 12)[0]
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
    procedural_town_game.use_procedural_town_interior_action(8, 8)
    procedural_town_game.sleep = original_sleep
    assert sleep_calls == [False]
    cooking_calls = []
    original_safe_menu_for_residence = procedural_town_game.safe_menu
    procedural_town_game.safe_menu = (
        lambda menu_func, close_message: cooking_calls.append(close_message)
    )
    procedural_town_game.use_procedural_town_interior_action(9, 16)
    procedural_town_game.safe_menu = original_safe_menu_for_residence
    assert cooking_calls == ["Cooking closed."]
    assert procedural_town_game.upgrade_procedural_residence(
        property_record["id"]
    )
    assert property_record["upgrade_level"] == 1
    assert procedural_town_game.get_placed_object(9, 16) == "Kitchen Counter"
    assert procedural_town_game.procedural_residence_sleep_bonus() > 0
    procedural_town_game.state.spouse_npc_id = str(
        procedural_town_game.state.town_npcs[0]["id"]
    )
    procedural_town_game.state.spouse_moved_to_farm = True
    assert procedural_town_game.move_household_to_residence(
        property_record["id"]
    )
    assert property_record["household_moved"] is True
    assert procedural_town_game.get_placed_object(46, 15) == "Family Table"
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
    assert procedural_town_game.establish_regional_agreement(
        trade_route["id"],
        "Trade Charter",
    )
    assert trade_route["agreement_type"] == "Trade Charter"
    assert procedural_town_game.contribute_to_regional_treasury(3000)
    assert procedural_town_game.complete_regional_project("caravan_league")
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
    assert "Courtship" in romance_menu_labels
    assert "Propose" in romance_menu_labels
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
    finally:
        farmstead_main.read_key = original_main_read_key

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
    assert game.state.location == "Farm"
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
    first_npc = game.state.town_npcs[0]
    assert game.town_npc_relationship(str(first_npc["id"])) == 0
    assert game.town_npc_friendship_label(0) == "Stranger"
    first_talk_lines = game.town_npc_dialogue_lines(first_npc)
    assert len(first_talk_lines) == 1
    assert first_talk_lines[0].strip()
    assert "already talked" not in "\n".join(first_talk_lines).lower()
    spring_dialogue = game.contextual_dialogue_entries_for_category(first_npc, "spring")
    assert spring_dialogue
    assert all(not game.low_quality_dialogue_text(entry["text"]) for entry in spring_dialogue)
    assert not any("Mud everywhere" in entry["text"] for entry in spring_dialogue)
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

    original_game_save = game.save
    game.save = lambda *args, **kwargs: True
    museum_catalog = game.museum_donation_catalog()
    assert "agriculture:Turnip" in museum_catalog
    assert "fishing:Pond Minnow" in museum_catalog
    assert "geology:Crystal Shard" in museum_catalog
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
    game.state.location = "MuseumInterior"
    assert game.location_label() == "Museum"
    assert game.active_map()[19][27] == "D"
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
    assert restoration_game.state.location == "Town"
    assert (restoration_game.state.player_x, restoration_game.state.player_y) == (data.TOWN_DOORS["museum"][0], data.TOWN_DOORS["museum"][1] + 1)

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
    festival_game.state.month, festival_game.state.day, festival_game.state.year = 3, 7, 1
    festival = festival_game.todays_festival()
    assert festival and festival["id"] == "spring_seed_fair"
    activities = festival_game.festival_activity_options(festival)
    assert len(activities) >= 3
    assert festival_game.complete_festival_activity(festival, activities[0])
    assert festival_game.festival_activity_completed("spring_seed_fair", str(activities[0]["id"]))
    assert festival_game.state.inventory.get("Mixed Seeds", 0) >= 2

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
    hud_footer = game.footer_lines()
    assert len(hud_footer) <= game.hud_footer_budget()
    assert len(hud_footer) >= 4
    assert all(visible_terminal_len(line) <= hud_width for line in hud_footer)
    original_terminal_width = farmstead_main.terminal_width
    hud_regression_game = FarmGame()
    original_row_count = hud_regression_game.terminal_row_count
    try:
        farmstead_main.terminal_width = lambda: 73
        hud_regression_game.terminal_row_count = lambda: 31
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
        assert any("Map 54x22" in line for line in narrow_hud_lines)
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
        frame_width = max(game.hud_line_width(), game.active_map_width())
        for rendered_line in game.render_frame_text().splitlines():
            assert visible_terminal_len(rendered_line) <= frame_width
    assert game.make_general_store_map()[17][42] == "P"
    assert game.make_library_interior_map()[17][42] == "P"
    assert game.make_town_hall_map()[17][42] == "P"

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
    authored_layout_signatures = set()
    for location, map_attr, required_tiles in interior_audit_specs:
        game.state.location = location
        game.state.player_x, game.state.player_y = 27, 18
        game.state.hour, game.state.minute = 6, 0
        grid = getattr(game, map_attr)
        authored_layout_signatures.add(tuple("".join(row) for row in grid))
        assert grid[19][27] == "D", f"{location} missing exit"
        assert game.passable(27, 18), f"{location} entry lane is blocked"
        full_width_spoke_rows = sum(
            1
            for lane_y in (8, 11, 14, 16)
            if all(grid[lane_y][lane_x] == "." for lane_x in range(8, 46))
        )
        assert full_width_spoke_rows <= 1, f"{location} still looks like the old full-width spoke template"
        sleep_x, sleep_y = game.indoor_npc_base_position(location)
        assert game.passable(sleep_x, sleep_y), f"{location} sleep anchor blocked at {sleep_x},{sleep_y}"
        seen = {(27, 18)}
        queue = deque([(27, 18)])
        while queue:
            x, y = queue.popleft()
            for nx, ny in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                if (nx, ny) in seen or not game.in_active_bounds(nx, ny) or not game.passable(nx, ny):
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
        assert "leave" in game.interaction_hint(27, 19)
    assert len(authored_layout_signatures) >= len(interior_audit_specs) - 1, "Authored town interiors are too visually repetitive"

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
    finally:
        game.safe_menu = original_safe_menu

    routine_game = FarmGame()
    routine_game.state.hour, routine_game.state.minute = 6, 0
    routine_game.state.weather = "Sunny"
    for npc in routine_game.active_town_npcs():
        wake_entry = routine_game.town_npc_routine_plan(npc).get("wake", {})
        wake_location = routine_game.normalize_town_npc_schedule_value(wake_entry)
        assert isinstance(wake_location, dict) and "inside" in wake_location, f"{npc.get('id')} does not wake indoors"
        assert routine_game.town_interior_location_for_name(str(wake_location["inside"])), f"{npc.get('id')} has no bedroom interior"
    assert routine_game.town_npc_indoor_location(next(npc for npc in routine_game.active_town_npcs() if npc.get("id") == "old_jun")) == "Inn"

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
        assert transition_game.state.location == "Town", f"{building_id} did not exit to town"
        assert (transition_game.state.player_x, transition_game.state.player_y) == (door_x, door_y + 1), f"{building_id} town exit is misplaced"
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
    birth_msg = family_game.update_family_overnight()
    assert "was born" in birth_msg
    assert not family_game.state.pregnancy_active
    assert family_game.state.children
    child = family_game.state.children[0]
    assert child.get("personality_trait")
    assert child.get("favorite_gift")
    assert child.get("apprentice_path")
    assert child.get("starting_class") in family_game.child_starting_class_catalog()
    family_game.state.year = max(family_game.state.year, int(child.get("birth_year", 1)) + 7)
    assert any("Trait:" in line for line in family_game.household_child_status_lines(child))
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
        interactive=False
    )
    assert "married" in wedding_message
    assert wedding_game.state.spouse_npc_id == fiance_id
    assert wedding_game.state.engaged_npc_id == ""
    assert wedding_game.state.marriage_history[-1]["status"] == "married"
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
    sleep_auto_game.base_map[10][10] = ","
    sleep_auto_game.state.placed_objects["Farm:10,9"] = "Rain Barrel"
    sleep_auto_game.sleep(force=True)
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
    assert "Check in" in connection_ui_labels
    assert "Share a quiet moment" in connection_ui_labels
    assert "Spouse support focus" in connection_ui_labels
    assert "Bond & memories" in connection_ui_labels
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
    backpack_route_game.show_chest_storage_menu = lambda: backpack_calls.append("storage") or farmstead_main.MENU_BACK
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
    journal_route_game.show_journal_calendar_menu = lambda: journal_route_calls.append("calendar") or farmstead_main.MENU_BACK
    journal_route_game.show_journal_records_menu = lambda: journal_route_calls.append("records") or farmstead_main.MENU_BACK
    assert journal_route_game.show_journal_codex_menu() == farmstead_main.MENU_BACK
    assert journal_route_views == ["Today", "Quest Journal", "Progress Goals"]
    assert journal_route_calls == ["calendar", "records"]

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
    assert "Aging & natural death" in settings_ui_labels

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
    stronghold_coords = None
    for cy in range(-80, 81):
        for cx in range(-80, 81):
            if (
                stronghold_game.wilderness_chunk_has_stronghold(cx, cy)
                and not stronghold_game.wilderness_chunk_has_procedural_settlement(cx, cy)
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

    def first_valid_stronghold_build_position(item_id):
        grid = stronghold_game.active_map()
        for yy in range(2, len(grid) - 2):
            for xx in range(2, len(grid[0]) - 2):
                ok, _reason = stronghold_game.can_place_reclaimed_stronghold_build_item(item_id, xx, yy, scx, scy)
                if ok:
                    return xx, yy
        return None

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

    home_pos = first_valid_stronghold_build_position("building:home")
    assert home_pos is not None
    money_before_home = stronghold_game.state.money
    assert stronghold_game.place_reclaimed_stronghold_build_item("building:home", home_pos[0], home_pos[1], scx, scy, autosave=False)
    assert stronghold_game.state.money == money_before_home - 850
    home_feature_id, home_feature = stronghold_game.reclaimed_stronghold_feature_at(home_pos[0], home_pos[1], scx, scy)
    assert home_feature_id.startswith("feature:")
    assert home_feature and home_feature["kind"] == "building"
    assert home_feature["name"] == "Settler Home"
    assert not stronghold_game.passable(home_pos[0], home_pos[1])
    assert "Settler Home" in stronghold_game.describe_tile(home_pos[0], home_pos[1])
    stronghold_game.state.money = max(stronghold_game.state.money, 10000)
    store_pos = first_valid_stronghold_build_position("building:general_store")
    assert store_pos is not None
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

    wilderness_poi_game = FarmGame()
    wilderness_poi_game.autosave_with_message = lambda message: wilderness_poi_game.set_message(message)
    wilderness_poi_game.vertical_panel_view = lambda *args, **kwargs: None
    wilderness_poi_game.state.wilderness_seed = 24681357
    wilderness_poi_game.wilderness_maps = {}
    wilderness_poi_game.wilderness_map = []
    wilderness_poi_game.state.location = "Wilderness"
    wilderness_poi_game.set_wilderness_chunk(0, 0)
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
    assert wilderness_poi_game.state.wilderness_poi_state

    dungeon_game = FarmGame()
    dungeon_game.autosave_with_message = lambda message: dungeon_game.set_message(message)
    dungeon_game.state.player_name = "Avery"
    dungeon_coords = None
    for cy in range(-50, 51):
        for cx in range(-50, 51):
            if dungeon_game.wilderness_chunk_has_dungeon_site(cx, cy):
                dungeon_coords = (cx, cy)
                break
        if dungeon_coords:
            break
    assert dungeon_coords is not None
    assert dungeon_game.overworld_chunk_preview_symbol(*dungeon_coords) == "X"
    dungeon_game.state.location = "Wilderness"
    dungeon_game.set_wilderness_chunk(*dungeon_coords)
    dungeon_entrance = None
    for y, row in enumerate(dungeon_game.active_map()):
        for x, tile in enumerate(row):
            if tile == "X":
                dungeon_entrance = (x, y)
                break
        if dungeon_entrance:
            break
    assert dungeon_entrance is not None
    assert "dungeon" in dungeon_game.describe_tile(*dungeon_entrance).lower()
    dungeon_game.enter_wilderness_dungeon(*dungeon_entrance)
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

    trap_x, trap_y = [(x, y) for y, row in enumerate(dungeon_map) for x, tile in enumerate(row) if tile == "!"][0]
    dungeon_game.state.combat_current_hp = 20
    dungeon_game.trigger_wilderness_dungeon_trap(trap_x, trap_y)
    assert dungeon_game.active_map()[trap_y][trap_x] == ":"
    assert 1 <= dungeon_game.state.combat_current_hp < 20
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
        assert loaded_follower_game.travel_follower_record(child_follower_id) == follower_save_fields
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

    print("Elsewhere smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
