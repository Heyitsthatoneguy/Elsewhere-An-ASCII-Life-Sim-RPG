from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path

from . import ai as ai_helpers
from . import game as game_module
from . import pathfinding as pathfinding_helpers
from .game import Game
from .main import configure_game_from_request
from .models import Zone
from .results import BattleRequest, battle_result_from_game
from .validation import validate_all_content, validate_battle_request, validate_battle_result


def _quiet(callable_obj, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return callable_obj(*args, **kwargs)


def run_smoke_tests() -> None:
    game = Game()
    assert game.maps, "maps did not load"
    assert game.skills, "skills did not load"
    assert game.class_slot_limit() == 3
    forbidden_audio_terms = ["win" + "sound", "\a"]
    package_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in Path(__file__).resolve().parent.glob("*.py")
        if path.name != Path(__file__).name
    ).lower()
    assert not any(term in package_text for term in forbidden_audio_terms)

    for mode in game.main_menu_modes():
        game.main_menu_mode = mode
        _quiet(game.render_main_menu)
        _quiet(game.handle_main_menu_key, "DOWN", None)
        _quiet(game.handle_main_menu_key, "ESC", None)
    original_terminal_size = game_module.shutil.get_terminal_size
    try:
        game_module.shutil.get_terminal_size = lambda fallback=(100, 30): os.terminal_size((60, 24))
        game.main_menu_mode = "home"
        _quiet(game.render_main_menu)
    finally:
        game_module.shutil.get_terminal_size = original_terminal_size
    game.start_battle_from_main_menu()
    assert not game.in_main_menu and game.enemies_alive(), "default battle did not start"
    assert game.current_battle_request is not None
    assert game.current_battle_request.map_name == game.map_name

    item_game = Game()
    item_game.start_battle_from_main_menu()
    item_hero = item_game.selected_hero
    owned_item_defs = item_game.items[:8]
    zero_count_item = item_game.items[8]
    item_hero.inventory = {
        **{item.name: index + 1 for index, item in enumerate(owned_item_defs)},
        zero_count_item.name: 0,
        "Unknown Keepsake": 3,
    }
    item_game.start_item()
    assert item_game.state == "item_menu"
    assert [item.name for item in item_game.usable_items(item_hero)] == [
        item.name for item in owned_item_defs
    ]
    compact_item_panel = game_module.strip_ansi("\n".join(item_game.make_compact_panel()))
    assert owned_item_defs[0].name in compact_item_panel
    assert zero_count_item.name not in compact_item_panel
    assert "Unknown Keepsake" not in compact_item_panel
    assert "more item(s)" in compact_item_panel
    for _ in range(6):
        item_game.move_menu_selection(1)
    assert item_game.selected_item().name == owned_item_defs[6].name
    visible_entries, hidden_above, _hidden_below = item_game.item_menu_window(item_hero, max_entries=4)
    assert owned_item_defs[6].name in [item.name for _index, item in visible_entries]
    assert hidden_above > 0
    scrolled_item_panel = game_module.strip_ansi("\n".join(item_game.make_compact_panel()))
    assert owned_item_defs[6].name in scrolled_item_panel
    assert "^" in scrolled_item_panel

    hero = game.selected_hero
    reachable = game.reachable_tiles(hero)
    helper_reachable = pathfinding_helpers.reachable_tiles(
        hero,
        lambda pos: game.is_walkable(pos, ignore=hero),
        game.movement_cost,
    )
    assert reachable == helper_reachable
    assert game.find_path(hero, hero.pos) == [hero.pos]
    farthest_tile = max(reachable, key=lambda pos: reachable[pos])
    farthest_path = game.find_path(hero, farthest_tile)
    assert farthest_path[0] == hero.pos
    assert farthest_path[-1] == farthest_tile
    assert game.path_cost(farthest_path) == reachable[farthest_tile]
    enemy = game.enemies_alive()[0]
    target = game.heroes_alive()[0]
    helper_score = ai_helpers.enemy_target_score(
        enemy,
        target,
        game.heroes_alive(),
        game.estimated_attack_damage(enemy, target),
    )
    assert game.enemy_target_score(enemy, target) == helper_score
    assert game.enemy_ap_budget(enemy) == ai_helpers.enemy_ap_budget(enemy)
    assert game.enemy_action_ends_sequence("attack") == ai_helpers.enemy_action_ends_sequence("attack")
    assert game.enemy_action_cost(enemy, "move") == ai_helpers.enemy_action_cost(enemy, "move")
    assert game.best_enemy_move(enemy, target) in game.reachable_tiles(enemy)
    game.start_move()
    game.cursor = farthest_tile
    _quiet(game.render)
    assert game._ui_intent_preview_cache
    intent_cache_keys = set(game._ui_intent_preview_cache.keys())
    game.move_cursor(1, 0)
    _quiet(game.render)
    assert set(game._ui_intent_preview_cache.keys()) == intent_cache_keys

    # Crossing the UI-cache limit must retain the newly computed entry. The
    # old clear-all behavior deleted it immediately and caused combat renders
    # to crash with KeyError during animated enemy movement.
    game._ui_intent_cache = {
        ("stale-summary", index): "guard"
        for index in range(96)
    }
    assert game.ui_enemy_intent_summary(enemy)
    assert len(game._ui_intent_cache) == 96
    game._ui_priority_cache = {
        ("stale-priority", index): 0
        for index in range(96)
    }
    assert isinstance(game.ui_enemy_intent_priority(enemy), int)
    assert len(game._ui_priority_cache) == 96

    # Animated AI-phase renders must not recalculate speculative enemy plans
    # after every movement tile.
    game.turn = "enemy"
    original_enemy_intent_summary = game.enemy_intent_summary
    game.enemy_intent_summary = lambda _enemy: (_ for _ in ()).throw(
        AssertionError("AI-phase rendering recalculated enemy intent")
    )
    _quiet(game.render)
    assert game.ui_enemy_intent_summary(enemy) == "acting"
    game.enemy_intent_summary = original_enemy_intent_summary
    game.turn = "hero"

    zone_game = Game()
    zone = Zone(
        "Ooze Mire",
        {(4, 4), (5, 4), (4, 5), (5, 5)},
        "poison",
        3,
        damage=1,
        status="poison",
        status_duration=2,
        owner_team="enemy",
    )
    zone_game.zones = [zone]
    first_zone_key = zone_game.tactical_preview_cache_key()
    assert zone.center == (4, 4)
    zone.tiles.add((6, 5))
    assert zone_game.tactical_preview_cache_key() != first_zone_key

    turn_game = Game()
    turn_game.frame_delay = 0
    turn_game.start_battle_from_main_menu()
    _quiet(turn_game.enemy_turn)
    assert turn_game.turn == "hero"
    assert turn_game.round_no == 2

    mission_game = Game()
    mission_game.main_menu_mode = "missions"
    mission_preset = mission_game.mission_builtin_presets()[0]
    mission_request = mission_game.create_battle_request_from_mission(mission_preset)
    assert mission_request.source == "mission"
    assert validate_battle_request(mission_game, mission_request).ok
    mission_game.start_mission_preset(mission_preset)
    assert mission_game.current_mission_name == "Farm Pest Trouble"
    assert mission_game.current_battle_request is not None
    assert mission_game.current_battle_request.source == "mission"
    assert mission_game.enemies_alive(), "mission preset did not activate enemies"

    encounter_game = Game()
    encounter_game.clear_custom_encounter()
    encounter_game.increase_custom_enemy_by_name("Crow")
    encounter_request = encounter_game.create_battle_request_from_encounter_builder()
    assert encounter_request.enemy_counts == {"Crow": 1}
    assert validate_battle_request(encounter_game, encounter_request).ok
    encounter_game.start_custom_encounter_from_main_menu()
    assert encounter_game.custom_encounter_enabled

    companion_game = Game()
    companion_game.companion_editor_custom_name = "test ally"
    custom = companion_game.create_custom_companion()
    assert custom.name == "test ally"

    setup_ux_game = Game()
    setup_ux_game.main_menu_mode = "missions"
    setup_ux_game.mission_page_index = 1
    _quiet(setup_ux_game.handle_main_menu_key, "x", None)
    assert setup_ux_game.main_menu_mode == "missions"
    assert setup_ux_game.mission_page_index == 0

    saved_builder = []
    setup_ux_game.main_menu_mode = "missions"
    setup_ux_game.mission_page_index = 1
    setup_ux_game.save_mission_builder_preset = lambda: saved_builder.append(True)
    _quiet(setup_ux_game.handle_main_menu_key, "v", None)
    assert saved_builder
    assert setup_ux_game.mission_page_index == 0

    companion_ux_game = Game()
    companion_ux_game.main_menu_mode = "companions"
    _quiet(companion_ux_game.handle_main_menu_key, "x", None)
    assert companion_ux_game.main_menu_mode == "home"
    deleted_custom = []
    companion_ux_game.main_menu_mode = "companions"
    companion_ux_game.delete_last_custom_companion = lambda: deleted_custom.append(True)
    _quiet(companion_ux_game.handle_main_menu_key, "BACKSPACE", None)
    assert deleted_custom

    class_game = Game()
    hero = class_game.heroes[0]
    progress = class_game.ensure_progress_entry(hero)
    progress["skill_points"] = 99
    assert class_game.focus_class_for_hero(hero, "Vanguard")
    assert class_game.focus_class_for_hero(hero, "Ranger")
    assert class_game.focus_class_for_hero(hero, "Guardian")
    assert not class_game.focus_class_for_hero(hero, "Mystic")
    for skill_name, _cost, _desc in class_game.class_tree_for("Vanguard"):
        class_game.class_unlocks(hero, "Vanguard").add(skill_name)
        class_game.skill_rank_map(hero, "Vanguard")[skill_name] = class_game.skill_max_rank(skill_name, "Vanguard")
    assert class_game.class_mastered(hero, "Vanguard")
    assert class_game.focus_class_for_hero(hero, "Mystic")

    log_game = Game()
    log_game.start_battle_from_main_menu()
    log_game.start_combat_log()
    log_game.combat_log_view = "combatants"
    _quiet(log_game.render_combat_log)
    log_game.combat_log_view = "events"
    _quiet(log_game.render_combat_log)
    _quiet(log_game.render_results_screen, "victory")
    result = battle_result_from_game(log_game, "victory")
    assert result.result == "victory"
    assert validate_battle_result(result).ok

    selected_request = Game().create_battle_request_from_selected_setup()
    assert selected_request.map_name
    assert validate_battle_request(Game(), selected_request).ok

    requested = configure_game_from_request(
        Game(),
        BattleRequest(
            source="overworld",
            map_name="Spring Bloomfield",
            enemy_counts={"Slime": 2},
            party_ids=["Rook", "Mira"],
            mission_name="Smoke Mission",
        ),
    )
    assert requested.map_name == "Spring Bloomfield"
    assert requested.current_mission_name == "Smoke Mission"
    assert requested.frame_delay == 0.10
    alias_request = BattleRequest(
        enemy_group=["Slime", "Slime"],
        enemy_counts={"Slime": 2},
    )
    assert alias_request.requested_enemy_names() == ["Slime", "Slime"]

    farmstead_fast = configure_game_from_request(
        Game(),
        BattleRequest(source="ascii_farmstead", enemy_counts={"Slime": 1}),
    )
    assert farmstead_fast.frame_delay == 0.025
    assert not farmstead_fast.allow_battle_map_selection
    assert "Map" not in farmstead_fast.command_menu_options()
    farmstead_fast.state = "command"
    farmstead_fast.start_map_menu()
    assert farmstead_fast.state == "command"
    briefing_game = configure_game_from_request(
        Game(),
        BattleRequest(
            source="ascii_farmstead",
            map_name="Moonlit Quarry",
            enemy_counts={"Rockback": 1, "Wisp": 1},
            return_context={"encounter_briefing": "Stonewall | Even | Threat 101/105"},
        ),
    )
    assert briefing_game.messages[0] == "Stonewall | Even | Threat 101/105"
    assert any("Stonewall" in entry for entry in briefing_game.combat_log)
    debug_request_game = configure_game_from_request(
        Game(),
        BattleRequest(source="debug", enemy_counts={"Slime": 1}, is_debug=True),
    )
    assert debug_request_game.allow_battle_map_selection
    assert "Map" in debug_request_game.command_menu_options()
    farmstead_custom_speed = configure_game_from_request(
        Game(),
        BattleRequest(
            source="ascii_farmstead",
            enemy_counts={"Slime": 1},
            return_context={"farm_combat_frame_delay": 0},
        ),
    )
    assert farmstead_custom_speed.frame_delay == 0
    farmstead_clamped_speed = configure_game_from_request(
        Game(),
        BattleRequest(
            source="ascii_farmstead",
            enemy_counts={"Slime": 1},
            return_context={"farm_combat_frame_delay": 1.0},
        ),
    )
    assert farmstead_clamped_speed.frame_delay == 0.10

    hardened = configure_game_from_request(
        Game(),
        BattleRequest(
            map_id="not-a-number",
            enemy_group=["Unknown Beast"],
            enemy_counts={"Slime": "2", "Missing": "bad"},
            objective="Not Real",
            objective_params={"round_goal": "bad", "hold_goal": -5, "object_goal": 0},
            party_members=["Nobody"],
            return_context={"source": "smoke"},
            world_flags={"mine_node": "cleared"},
        ),
    )
    assert hardened.objective_mode == "Defeat All"
    assert hardened.objective_hold_goal == 1
    assert hardened.objective_object_goal == 1
    assert hardened.selected_custom_enemy_summary() == "Slime x2"
    assert hardened.active_party_names == {"Rook"}
    hardened_result = battle_result_from_game(hardened, "victory")
    assert hardened_result.return_context == {"source": "smoke"}
    assert "mine_node" in hardened_result.world_flags
    assert hardened_result.cleared_flags["battle_result"] == "victory"
    assert hardened_result.cleared_flags[f"cleared:{hardened.map_name}"]

    handoff_request = BattleRequest(
        source="overworld",
        map_name="Spring Bloomfield",
        enemy_counts={"Slime": 1},
        party_ids=["Rook", "Mira"],
        objective="Defeat All",
        mission_id="spring-test",
        mission_name="Spring Test",
        return_context={"farm_plot": "north"},
        world_flags_on_victory=["farm_plot:north:cleared"],
        world_flags_on_defeat=["farm_plot:north:danger"],
    )
    handoff_game = Game()
    assert validate_battle_request(handoff_game, handoff_request).ok
    handoff_game.start_battle_from_request(handoff_request)
    assert not handoff_game.in_main_menu
    assert handoff_game.current_battle_request == handoff_request
    assert handoff_game.enemies_alive()
    victory_result = handoff_game.build_battle_result(handoff_request, "victory")
    defeat_result = handoff_game.build_battle_result(handoff_request, "defeat")
    assert victory_result.outcome == "victory"
    assert victory_result.objective_success
    assert "farm_plot:north:cleared" in victory_result.world_flags
    assert "farm_plot:north:danger" in defeat_result.world_flags
    assert validate_battle_result(victory_result).ok
    assert validate_battle_result(defeat_result).ok

    invalid_report = validate_battle_request(
        Game(),
        BattleRequest(
            source="overworld",
            map_name="Missing Field",
            enemy_counts={"Slime": 0, "Missing": 1},
            party_ids=["Nobody"],
            objective="Survive",
            objective_params={},
        ),
    )
    assert not invalid_report.ok

    content_report = validate_all_content(Game())
    assert content_report.ok, [issue for issue in content_report.issues if issue.severity == "error"]

    class FakeReader:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read_key(self):
            return "q"

    patched = {
        name: getattr(game_module, name)
        for name in ["KeyReader", "enter_alt_screen", "exit_alt_screen", "hide_cursor", "show_cursor", "clear_screen"]
    }
    try:
        game_module.KeyReader = FakeReader
        game_module.enter_alt_screen = lambda: None
        game_module.exit_alt_screen = lambda: None
        game_module.hide_cursor = lambda: None
        game_module.show_cursor = lambda: None
        game_module.clear_screen = lambda clear_scrollback=False: None
        run_game = Game()
        _quiet(run_game.run)
        assert run_game.should_quit
    finally:
        for name, value in patched.items():
            setattr(game_module, name, value)


if __name__ == "__main__":
    run_smoke_tests()
    print("v113 smoke tests passed")
