from __future__ import annotations

import os
import re
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional


ENABLE_COLOR = True

GAME_TITLE = "Elsewhere: an ASCII Life-Sim RPG"
GAME_SHORT_TITLE = "Elsewhere"
GAME_VERSION = "0.9.0-beta.1"
GAME_DISPLAY_TITLE = f"{GAME_TITLE} {GAME_VERSION}"
SAVE_SCHEMA_VERSION = 1
SAVE_BACKUP_COUNT = 3
DEBUG_LOG_MAX_BYTES = 1_000_000
DEBUG_LOG_BACKUP_COUNT = 2


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    NIGHT = "\033[38;5;238m"
    LAMP = "\033[93;1m"
    LIT = "\033[38;5;229m"

    GRASS = "\033[32m"
    SOIL_DRY = "\033[38;5;94m"
    SOIL_WET = "\033[38;5;130m"
    WATER = "\033[36m"
    WALL = "\033[90m"
    HOUSE = "\033[33m"
    SHOP = "\033[93m"
    BIN = "\033[95m"
    PLAYER = "\033[97;1m"

    SPRING_GRASS = "\033[92m"
    SUMMER_GRASS = "\033[32m"
    FALL_GRASS = "\033[33m"
    WINTER_GRASS = "\033[97m"

    SPRING_SOIL_DRY = "\033[38;5;94m"
    SUMMER_SOIL_DRY = "\033[38;5;136m"
    FALL_SOIL_DRY = "\033[38;5;130m"
    WINTER_SOIL_DRY = "\033[37m"

    SPRING_SOIL_WET = "\033[38;5;29m"
    SUMMER_SOIL_WET = "\033[34m"
    FALL_SOIL_WET = "\033[36m"
    WINTER_SOIL_WET = "\033[96m"

    SPRING_WEED = "\033[92m"
    SUMMER_WEED = "\033[32m"
    FALL_WEED = "\033[93m"
    WINTER_WEED = "\033[97m"

    WINTER_WATER = "\033[96m"
    RAIN = "\033[96m"
    SNOW = "\033[97m"
    STORM = "\033[37;1m"

    INFRA = "\033[95;1m"
    PLACEMENT = "\033[91;1m"
    PLACEMENT_BAD = "\033[90;1m"
    HOSTILE = "\033[91;1m"

    WEED = "\033[92m"
    STONE = "\033[37m"
    WOOD = "\033[38;5;130m"

    CROP_SPROUT = "\033[92m"
    CROP_MID = "\033[32m"
    CROP_READY = "\033[93;1m"
    CROP_DRY = "\033[38;5;100m"


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

VALID_GAME_LOCATIONS = (
    "Farm",
    "Town",
    "Mine",
    "Wilderness",
    "WildernessOverworld",
    "WildernessCave",
    "WildernessDungeon",
    "ProceduralSettlementInterior",
    "HouseInterior",
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
)

VALID_TOOL_TARGET_MODES = ("FRONT", "STANDING")

LOADED_STATE_DEFAULTS = {
    "color_enabled": True,
    "shop_auto_open_enabled": True,
    "shop_menu_suppressed_until_exit": False,
    "bin_auto_open_enabled": True,
    "bin_menu_suppressed_until_exit": False,
    "show_target_info": True,
    "show_control_hints": True,
    "player_name": "Farmer",
    "player_sex": "Female",
    "player_color": "White",
    "player_birthday_month": 3,
    "player_birthday_day": 1,
    "spouse_moved_to_farm": False,
    "owned_tools": [],
    "storage_inventory": {},
    "placed_objects": {},
    "fertilized_tiles": {},
    "farm_expansions": [],
    "house_upgrades": [],
    "held_object": None,
    "wilderness_seed": 1337,
    "wilderness_chunk_x": 0,
    "wilderness_chunk_y": 0,
    "wilderness_chunks_visited": 1,
    "wilderness_animals_seen": 0,
    "farm_building_harvest_days": {},
    "farm_building_boosts": {},
    "farm_animals": [],
    "next_farm_animal_id": 1,
    "town_npcs": [],
    "town_npc_dialogue_counts": {},
    "town_npc_relationships": {},
    "town_npc_last_talk_day": {},
    "town_npc_last_gift_day": {},
    "town_npc_last_gift_reactions": {},
    "town_npc_recent_gifts": {},
    "town_npc_last_court_day": {},
    "town_npc_courtship_counts": {},
    "town_npc_relationship_milestones": {},
    "town_npc_recent_dialogue_ids": {},
    "town_npc_last_proposal_day": {},
    "dating_npc_ids": [],
    "spouse_npc_id": "",
    "marriage_month": 0,
    "marriage_day": 0,
    "marriage_year": 0,
    "family_event_log": [],
    "family_event_flags": [],
    "family_planning_last_discussion_day": "",
    "pregnancy_checkup_months_seen": [],
    "child_milestone_flags": [],
    "family_help_enabled": True,
    "family_last_help_day": "",
    "family_bond": 0,
    "family_meal_last_day": "",
    "family_last_meal": "",
    "spouse_support_mode": "Balanced",
    "child_affection": {},
    "child_last_gift_day": {},
    "child_last_lesson_day": {},
    "child_learning_points": {},
    "child_chore_assignments": {},
    "unlocked_party_member_ids": [],
    "active_party_member_ids": [],
    "max_party_members": 4,
    "party_tactic": "Balanced",
    "manual_party_member_ids": [],
    "combat_party_progress": {},
    "combat_campaign_inventory": {},
    "combat_item_loadout_bonus": {},
    "combat_bestiary_seen": [],
    "combat_bestiary_defeated": {},
    "completed_combat_mission_ids": [],
    "last_combat_report": [],
    "party_member_hp": {},
    "party_member_focus": {},
    "party_member_last_relationship_gain_day": {},
    "pregnancy_active": False,
    "pregnancy_parent_npc_id": "",
    "pregnancy_gestational_parent": "",
    "pregnancy_start_month": 0,
    "pregnancy_start_day": 0,
    "pregnancy_start_year": 0,
    "pregnancy_due_month": 0,
    "pregnancy_due_day": 0,
    "pregnancy_due_year": 0,
    "children": [],
    "next_child_id": 1,
    "mail_read_ids": [],
    "mail_claimed_ids": [],
    "market_purchase_counts": {},
    "completed_errand_ids": [],
    "completed_resident_request_ids": [],
    "completed_companion_quest_ids": [],
    "learned_recipe_ids": [],
    "library_research_ids": [],
    "completed_town_project_ids": [],
    "completed_town_restoration_project_ids": [],
    "completed_mine_special_ids": [],
    "attended_festival_ids": [],
    "completed_bulletin_job_ids": [],
    "completed_scene_ids": [],
    "seen_scene_ids": [],
    "scene_flags": [],
    "active_scene_id": "",
    "active_scene_step_index": 0,
    "active_food_buffs": {},
    "fish_ponds": {},
    "artisan_processors": {},
    "overworld_cursor_chunk_x": 0,
    "overworld_cursor_chunk_y": 0,
    "overworld_return_chunk_x": 0,
    "overworld_return_chunk_y": 0,
    "overworld_return_x": 0,
    "overworld_return_y": 0,
    "cave_return_location": "Wilderness",
    "cave_return_chunk_x": 0,
    "cave_return_chunk_y": 0,
    "cave_return_x": 0,
    "cave_return_y": 0,
    "current_cave_key": "",
    "wilderness_caves_discovered": 0,
    "mine_floor": 1,
    "deepest_mine_floor": 1,
    "unlocked_mine_elevators": [1],
    "cleared_mine_floors": [],
    "unlocked_mine_down_stairs": [],
    "mine_floor_clear_rewards_claimed": [],
    "mine_seed": 4242,
    "mine_combat_victories": 0,
    "mine_combat_defeats": 0,
    "mine_combat_flees": 0,
    "mine_enemies_defeated": 0,
    "combat_level": 1,
    "combat_exp": 0,
    "combat_exp_to_next": 20,
    "combat_max_hp": 34,
    "combat_current_hp": 34,
    "combat_attack": 3,
    "combat_defense": 0,
    "combat_focus": 8,
    "combat_max_focus": 8,
    "combat_skill_points": 0,
    "equipped_weapon": "Rusty Sword",
    "equipped_armor": "Work Clothes",
    "equipped_accessory": "None",
    "shipped_today_items": {},
    "last_shipping_report": [],
    "last_automation_report": [],
    "automation_machines": {},
    "fishing_target_x": 0,
    "fishing_target_y": 0,
    "fishing_elapsed": 0.0,
    "fishing_bite_at": 0.0,
    "fishing_end_at": 0.0,
    "fishing_will_bite": True,
    "fishing_pool": [],
    "location": "Farm",
    "facing": "DOWN",
    "tool_target_mode": "FRONT",
    "live_time_enabled": True,
    "time_speed": "Brisk",
}


def set_color_enabled(enabled: bool):
    global ENABLE_COLOR
    ENABLE_COLOR = bool(enabled)


def get_color_enabled() -> bool:
    return ENABLE_COLOR


def enable_ansi_colors():
    """Enable ANSI escape sequences on Windows when possible."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def colorize(text: str, color: str) -> str:
    if not ENABLE_COLOR:
        return text
    return f"{color}{text}{C.RESET}"


def visual_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def pad_visual(text: str, width: int) -> str:
    visible = visual_len(text)
    if visible >= width:
        return text
    return text + (" " * (width - visible))


def normalize_key(key: str) -> str:
    """Normalize single-letter keys while preserving special keys."""
    if len(key) == 1 and key.isalpha():
        return key.lower()
    return key


def source_directory() -> Path:
    """Return the source/executable directory without using PyInstaller temp files."""
    if bool(getattr(sys, "frozen", False)):
        return Path(sys.executable).resolve().parent
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()


def get_game_data_directory() -> Path:
    """Use portable source saves and per-user storage for packaged builds."""
    override = str(os.environ.get("ELSEWHERE_DATA_DIR", "")).strip()
    if override:
        return Path(override).expanduser().resolve()
    if not bool(getattr(sys, "frozen", False)):
        return source_directory()
    if os.name == "nt":
        root = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or str(Path.home())
        )
        return Path(root) / "Elsewhere"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Elsewhere"
    root = os.environ.get("XDG_DATA_HOME")
    return (
        Path(root) / "elsewhere"
        if root
        else Path.home() / ".local" / "share" / "elsewhere"
    )


def get_save_path() -> Path:
    """Return the current save path for this runtime."""
    return get_game_data_directory() / "ascii_farmstead_save.json"


GAME_DATA_DIRECTORY = get_game_data_directory()
SAVE_PATH = get_save_path()
ERROR_LOG_PATH = SAVE_PATH.with_name("ascii_farmstead_error.log")
DEBUG_LOG_PATH = SAVE_PATH.with_name("ascii_farmstead_debug.log")
CRASH_REPORT_PATH = SAVE_PATH.with_name("ascii_farmstead_crash_report.txt")
SAVE_SLOT_COUNT = 3


def save_slot_path(slot_number: int) -> Path:
    return SAVE_PATH.with_name(f"ascii_farmstead_slot_{slot_number}.json")


def save_backup_path(path: Path, backup_number: int) -> Path:
    number = max(1, int(backup_number))
    return path.with_name(f"{path.stem}.backup{number}{path.suffix}")


def save_backup_paths(path: Path) -> List[Path]:
    return [
        save_backup_path(path, number)
        for number in range(1, SAVE_BACKUP_COUNT + 1)
    ]


def packaged_legacy_data_names() -> List[str]:
    return [
        "ascii_farmstead_save.json",
        "custom_content.json",
        "custom_content_export.json",
        "custom_content.json.backup",
    ] + [
        f"ascii_farmstead_slot_{number}.json"
        for number in range(1, SAVE_SLOT_COUNT + 1)
    ] + [
        f"custom_content.backup{number}.json"
        for number in range(1, SAVE_BACKUP_COUNT + 1)
    ]


def migrate_packaged_legacy_data() -> None:
    """Copy portable saves and custom content into packaged user storage once."""
    if not bool(getattr(sys, "frozen", False)):
        return
    legacy_directory = source_directory()
    if legacy_directory == GAME_DATA_DIRECTORY:
        return
    try:
        GAME_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
        for name in packaged_legacy_data_names():
            source = legacy_directory / name
            destination = GAME_DATA_DIRECTORY / name
            if source.exists() and not destination.exists():
                shutil.copy2(source, destination)
    except Exception:
        pass


def rotate_text_log(path: Path) -> None:
    """Keep verbose runtime logs bounded without affecting crash reporting."""
    try:
        if not path.exists() or path.stat().st_size < DEBUG_LOG_MAX_BYTES:
            return
        oldest = path.with_name(f"{path.name}.{DEBUG_LOG_BACKUP_COUNT}")
        oldest.unlink(missing_ok=True)
        for number in range(DEBUG_LOG_BACKUP_COUNT - 1, 0, -1):
            source = path.with_name(f"{path.name}.{number}")
            if source.exists():
                source.replace(path.with_name(f"{path.name}.{number + 1}"))
        path.replace(path.with_name(f"{path.name}.1"))
    except Exception:
        pass


migrate_packaged_legacy_data()


def append_debug_log(message: str):
    """Append a timestamped debug message beside the save file."""
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        rotate_text_log(DEBUG_LOG_PATH)
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def safe_len(obj) -> str:
    try:
        return str(len(obj))
    except Exception:
        return "?"


def build_debug_snapshot(game=None, context: str = "") -> str:
    """Build a text snapshot of game/runtime state for debugging."""
    lines = []
    lines.append(f"{GAME_DISPLAY_TITLE} Debug Snapshot")
    lines.append("=" * 40)
    lines.append(f"Context: {context}")
    lines.append(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Python: {sys.version}")
    lines.append(f"Executable: {sys.executable}")
    lines.append(f"Platform: {sys.platform}")
    lines.append(f"CWD: {Path.cwd()}")
    lines.append(f"Support module path: {Path(__file__).resolve()}")
    lines.append(f"Save path: {SAVE_PATH}")
    lines.append(f"Debug log: {DEBUG_LOG_PATH}")
    lines.append(f"Error log: {ERROR_LOG_PATH}")
    lines.append(f"Crash report: {CRASH_REPORT_PATH}")

    if game is not None:
        try:
            s = game.state
            lines.append("")
            lines.append("Game State")
            lines.append("-" * 40)
            lines.append(f"Location: {getattr(s, 'location', '?')}")
            lines.append(f"Position: {getattr(s, 'player_x', '?')},{getattr(s, 'player_y', '?')}")
            lines.append(f"Facing: {getattr(s, 'facing', '?')}")
            lines.append(f"Date/time: Y{getattr(s, 'year', '?')} M{getattr(s, 'month', '?')} D{getattr(s, 'day', '?')} {getattr(s, 'hour', '?')}:{getattr(s, 'minute', '?')}")
            lines.append(f"Season: {getattr(s, 'season', '?')}")
            lines.append(f"Weather: {getattr(s, 'weather', '?')}")
            lines.append(f"Money/Stamina: ${getattr(s, 'money', '?')} / {getattr(s, 'stamina', '?')}")
            lines.append(f"Selected tool: {getattr(s, 'selected_tool', '?')}")
            lines.append(f"Held object: {getattr(s, 'held_object', None)}")
            lines.append(f"Message: {getattr(s, 'message', '')}")
            lines.append(f"Mine floor/deepest: {getattr(s, 'mine_floor', '?')}/{getattr(s, 'deepest_mine_floor', '?')}")
            lines.append(f"Wilderness seed: {getattr(s, 'wilderness_seed', '?')}")
            lines.append(f"Wilderness animals seen: {getattr(s, 'wilderness_animals_seen', '?')}")
            lines.append(f"Mine seed: {getattr(s, 'mine_seed', '?')}")
            lines.append(f"Inventory keys: {safe_len(getattr(s, 'inventory', {}))}")
            lines.append(f"Placed objects: {safe_len(getattr(s, 'placed_objects', {}))}")
            lines.append(f"Crops: {safe_len(getattr(game, 'crops', {}))}")
            lines.append(f"Wilderness map size: {safe_len(getattr(game, 'wilderness_map', []))} rows")
            try:
                wm = getattr(game, 'wilderness_map', [])
                if wm:
                    lines.append(f"Wilderness row widths: min={min(len(r) for r in wm)} max={max(len(r) for r in wm)}")
                    symbols = sorted({ch for row in wm for ch in row})
                    lines.append(f"Wilderness symbols: {''.join(symbols)}")
            except Exception as map_exc:
                lines.append(f"Wilderness map inspect error: {map_exc}")
            try:
                lines.append(f"Active map: {game.active_map_width()}x{game.active_map_height()}")
            except Exception as active_exc:
                lines.append(f"Active map error: {active_exc}")
        except Exception as snap_exc:
            lines.append(f"Snapshot error: {snap_exc}")

    return "\n".join(lines) + "\n"


def write_debug_report(game=None, exc: Optional[BaseException] = None, context: str = ""):
    """Write a detailed crash/debug report and append to the debug log."""
    try:
        report = build_debug_snapshot(game, context)
        if exc is not None:
            report += "\nException\n" + "-" * 40 + "\n"
            report += "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        CRASH_REPORT_PATH.write_text(report, encoding="utf-8")
        append_debug_log(f"Wrote crash report: {CRASH_REPORT_PATH} | context={context} | exc={exc}")
    except Exception:
        pass


def grid_to_save_rows(grid: List[List[str]]) -> List[str]:
    return ["".join(row) for row in grid]


def saved_rows_to_grid(
    rows,
    width: int,
    height: int,
    *,
    exact_size: bool = True,
    uniform_width: bool = False,
) -> Optional[List[List[str]]]:
    """Convert saved string rows into a mutable grid if the shape is valid."""
    if not isinstance(rows, list):
        return None
    if exact_size:
        if len(rows) != height:
            return None
    elif len(rows) < height:
        return None
    if any(not isinstance(row, str) for row in rows):
        return None

    row_widths = {len(row) for row in rows}
    if exact_size:
        if row_widths != {width}:
            return None
    else:
        if any(row_width < width for row_width in row_widths):
            return None
        if uniform_width and len(row_widths) != 1:
            return None

    return [list(row) for row in rows]


def copy_default_value(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    if isinstance(value, set):
        return set(value)
    return value


def default_tool_levels_for(owned_tools) -> Dict[str, int]:
    owned = set(owned_tools or [])
    return {
        "Hoe": 1,
        "Watering Can": 1,
        "Axe": 1 if "Axe" in owned else 0,
        "Pickaxe": 1 if "Pickaxe" in owned else 0,
    }


def clear_screen():
    """Fast ANSI clear. Avoid shelling out to cls/clear, which causes severe flicker."""
    try:
        sys.stdout.write("\033[H\033[2J")
        sys.stdout.flush()
    except Exception:
        print("\n" * 3)


def read_key_timeout(timeout: float) -> str:
    """Single-key reader with timeout. Returns '' if no key was pressed."""
    if os.name == "nt":
        import msvcrt

        deadline = time.time() + max(0.0, timeout)
        while time.time() < deadline:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in [b"\x00", b"\xe0"]:
                    while not msvcrt.kbhit() and time.time() < deadline:
                        time.sleep(0.005)
                    if not msvcrt.kbhit():
                        return ""
                    ch2 = msvcrt.getch()
                    return {
                        b"H": "UP",
                        b"P": "DOWN",
                        b"K": "LEFT",
                        b"M": "RIGHT",
                    }.get(ch2, "")
                try:
                    return ch.decode("utf-8")
                except UnicodeDecodeError:
                    return ""
            time.sleep(0.01)
        return ""

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        readable, _, _ = select.select([sys.stdin], [], [], max(0.0, timeout))
        if not readable:
            return ""

        ch = sys.stdin.read(1)
        if ch == "\x1b":
            readable, _, _ = select.select([sys.stdin], [], [], 0.01)
            if readable:
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    readable, _, _ = select.select([sys.stdin], [], [], 0.01)
                    if readable:
                        ch3 = sys.stdin.read(1)
                        return {
                            "A": "UP",
                            "B": "DOWN",
                            "C": "RIGHT",
                            "D": "LEFT",
                        }.get(ch3, "\x1b")
            return "\x1b"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_key() -> str:
    """Cross-platform-ish single-key reader with arrow key support."""
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getch()
        if ch in [b"\x00", b"\xe0"]:
            ch2 = msvcrt.getch()
            return {
                b"H": "UP",
                b"P": "DOWN",
                b"K": "LEFT",
                b"M": "RIGHT",
            }.get(ch2, "")
        try:
            return ch.decode("utf-8")
        except UnicodeDecodeError:
            return ""

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                return {
                    "A": "UP",
                    "B": "DOWN",
                    "C": "RIGHT",
                    "D": "LEFT",
                }.get(ch3, "\x1b")
            return "\x1b"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def configure_console_encoding():
    """Best effort: reduce Windows double-click encoding weirdness."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def write_error_log(exc: BaseException, game=None, context: str = "fatal"):
    try:
        ERROR_LOG_PATH.write_text(
            f"{GAME_DISPLAY_TITLE} crashed.\n\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            encoding="utf-8",
        )
    except Exception:
        pass
    try:
        write_debug_report(game=game, exc=exc, context=context)
    except Exception:
        pass
