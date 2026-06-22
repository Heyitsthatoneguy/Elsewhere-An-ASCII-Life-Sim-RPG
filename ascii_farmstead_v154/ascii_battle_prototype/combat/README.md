# Combat Prototype v113 Backend Layout

`combat_prototype_v113.py` is the single-command launcher. The runtime package is `combat/`.

- `game.py`: live battle state, turn flow, rendering orchestration, and developer menu flow.
- `models.py`: core dataclasses such as `Unit`, `Weapon`, `Skill`, `Item`, `Zone`, and `OverwatchAction`.
- `constants.py`: terminal flags, map dimensions, tile glyphs, and terrain sets.
- `rendering.py` and `input.py`: terminal drawing helpers, wrapping/clipping safety, and keyboard input.
- `dev_menus.py`: main setup/developer menu rendering and key handling. `Game.render_main_menu()` and `Game.handle_main_menu_key()` delegate here.
- `pathfinding.py`: reusable movement range, path reconstruction, and attack-band distance helpers. `Game` supplies callbacks for live map state.
- `ai.py`: reusable enemy AP policy, target scoring, and movement choice helpers.
- `turns.py`: enemy turn resolution and special-action side effects. `Game.enemy_turn()` delegates here to keep existing callers stable.
- `maps.py`, `enemies.py`, `skills.py`, `items.py`, `classes.py`, `equipment.py`, `missions.py`, `companions.py`, and `loot.py`: content definitions and factories. Future content prompts should usually edit these files first.
- `results.py`: `BattleRequest` and `BattleResult` integration payloads for a future farming/life-sim overworld.
- `validation.py`: content and handoff validators for maps, enemies, objectives, rewards, mission presets, requests, and results.
- `main.py`: launcher helpers plus `configure_game_from_request()` and `run_battle_request()` as the future overworld hook.
- `smoke_tests.py`: non-interactive validation for core setup, menus, class slots/mastery, custom companions, battle setup, combat-log views, result payloads, and request configuration.

Run `python combat_prototype_v113.py --validate-content` to check combat content without opening the UI.

No persistent saves or sound functionality are introduced in v113.
