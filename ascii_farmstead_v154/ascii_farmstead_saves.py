from __future__ import annotations

"""Save/load and save-slot management for Elsewhere.

The mixin expects a FarmGame-like object that owns maps, crops, normalization
hooks, and UI panel methods. Keeping save behavior here separates persistence
from the main game loop without changing the legacy entry point.
"""

import json
import os
import shutil
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ascii_farmstead_data import (
    HEIGHT,
    LEFT_PANEL_HEIGHT,
    LEFT_PANEL_WIDTH,
    MENU_BACK,
    MINE_MAX_FLOOR,
    WIDTH,
)
from ascii_farmstead_helpers import format_date
from ascii_farmstead_state import Crop, GameState, prepare_loaded_state_data
from ascii_farmstead_support import (
    GAME_VERSION,
    SAVE_BACKUP_COUNT,
    SAVE_PATH,
    SAVE_SCHEMA_VERSION,
    SAVE_SLOT_COUNT,
    append_debug_log,
    grid_to_save_rows,
    save_backup_path,
    save_backup_paths,
    save_slot_path,
    saved_rows_to_grid,
    set_color_enabled,
)
from ascii_farmstead_ui import MenuItem


def rotate_save_backups(path: Path) -> None:
    """Preserve the last few complete saves before replacing the live file."""
    path = Path(path)
    if not path.exists():
        return
    save_backup_path(path, SAVE_BACKUP_COUNT).unlink(missing_ok=True)
    for number in range(SAVE_BACKUP_COUNT, 1, -1):
        source = save_backup_path(path, number - 1)
        destination = save_backup_path(path, number)
        if source.exists():
            os.replace(source, destination)
    first_backup = save_backup_path(path, 1)
    temporary_backup = first_backup.with_name(f"{first_backup.name}.tmp")
    try:
        shutil.copy2(path, temporary_backup)
        os.replace(temporary_backup, first_backup)
    finally:
        temporary_backup.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    """Commit text with an atomic same-directory replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def quarantine_broken_save(path: Path) -> Optional[Path]:
    """Move an unreadable live save aside without overwriting older evidence."""
    path = Path(path)
    if not path.exists():
        return None
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.stem}.broken-{timestamp}{path.suffix}")
    counter = 2
    while candidate.exists():
        candidate = path.with_name(
            f"{path.stem}.broken-{timestamp}-{counter}{path.suffix}"
        )
        counter += 1
    path.replace(candidate)
    return candidate


def delete_save_family(path: Path) -> None:
    """Delete a selected save and its automatic recovery copies."""
    path = Path(path)
    paths = [
        path,
        path.with_name(f"{path.name}.tmp"),
        *save_backup_paths(path),
    ]
    for candidate in paths:
        candidate.unlink(missing_ok=True)


class SaveLoadMixin:
    def any_save_file_exists(self) -> bool:
        if SAVE_PATH.exists():
            return True
        return any(save_slot_path(i).exists() for i in range(1, SAVE_SLOT_COUNT + 1))

    def current_save_summary(self) -> str:
        return self.save_file_summary(SAVE_PATH, empty_label="No current save")

    def save_file_summary(self, path: Path, empty_label: str = "empty") -> str:
        if not path.exists():
            return empty_label
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = data.get("state", {})
            month = int(state.get("month", 3))
            day = int(state.get("day", 1))
            year = int(state.get("year", 1))
            money = state.get("money", "?")
            player_name = GameState.clean_player_name(state.get("player_name", "Farmer"))
            return f"{player_name} | {format_date(month, day, year)} | ${money}"
        except Exception:
            return "unreadable"

    def slot_summary(self, slot_number: int) -> str:
        return self.save_file_summary(save_slot_path(slot_number), empty_label="empty")

    def copy_current_save_to_slot(self, slot_number: int) -> bool:
        slot_path = save_slot_path(slot_number)
        if self.save(quiet=True, path=slot_path):
            self.set_message(f"Saved current farm to slot {slot_number}.")
            return True
        return False

    def load_slot(self, slot_number: int) -> bool:
        slot_path = save_slot_path(slot_number)
        if not slot_path.exists():
            self.set_message(f"Slot {slot_number} is empty.")
            return False
        loaded = self.load_from_path(slot_path)
        if loaded:
            # Mirror loaded slot to normal current save so startup resumes from it.
            self.save(quiet=True, path=SAVE_PATH)
            self.set_message(f"Loaded slot {slot_number}.")
        return loaded

    def delete_slot(self, slot_number: int) -> bool:
        slot_path = save_slot_path(slot_number)
        if not slot_path.exists() and not any(
            backup.exists() for backup in save_backup_paths(slot_path)
        ):
            self.set_message(f"Slot {slot_number} is already empty.")
            return False
        try:
            delete_save_family(slot_path)
            self.set_message(f"Deleted slot {slot_number}.")
            return True
        except Exception as exc:
            self.set_message(f"Could not delete slot {slot_number}: {exc}")
            return False

    def delete_current_save_and_restart(self) -> bool:
        try:
            settings = self.startup_settings_snapshot()
            delete_save_family(SAVE_PATH)
            self.__init__()
            self.apply_startup_settings_snapshot(settings)
            if self.character_creation_menu():
                self.save(quiet=True, path=SAVE_PATH)
                self.set_message("Deleted current save. Started a fresh farm.")
            else:
                self.set_message("Deleted current save. Character creation cancelled.")
            return True
        except Exception as exc:
            self.set_message(f"Could not delete current save: {exc}")
            return False

    def show_save_location(self):
        rows = [
            "Current save:",
            str(SAVE_PATH),
            "",
            "Slots:",
        ]
        for i in range(1, SAVE_SLOT_COUNT + 1):
            rows.append(f"Slot {i}: {save_slot_path(i)}")
        self.vertical_panel_view("Save Location", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        return MENU_BACK

    def confirm_save_slot(self, slot_number: int):
        summary = self.slot_summary(slot_number)
        items = [
            MenuItem(label=f"Save to slot {slot_number}", value="yes", enabled=True, hint=summary),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ]
        choice = self.vertical_panel_select(
            f"Overwrite Slot {slot_number}",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice and choice.value == "yes":
            self.copy_current_save_to_slot(slot_number)

    def confirm_load_slot(self, slot_number: int):
        summary = self.slot_summary(slot_number)
        if summary == "empty":
            self.set_message(f"Slot {slot_number} is empty.")
            return
        items = [
            MenuItem(label=f"Load slot {slot_number}", value="yes", enabled=True, hint=summary),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ]
        choice = self.vertical_panel_select(
            f"Load Slot {slot_number}",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice and choice.value == "yes":
            self.load_slot(slot_number)

    def confirm_delete_slot(self, slot_number: int):
        summary = self.slot_summary(slot_number)
        if summary == "empty":
            self.set_message(f"Slot {slot_number} is already empty.")
            return
        items = [
            MenuItem(label=f"Delete slot {slot_number}", value="yes", enabled=True, hint=summary),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ]
        choice = self.vertical_panel_select(
            f"Delete Slot {slot_number}",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice and choice.value == "yes":
            self.delete_slot(slot_number)

    def confirm_delete_current_save(self):
        summary = self.current_save_summary()
        if summary == "No current save":
            self.set_message("There is no current save to delete.")
            return
        items = [
            MenuItem(label="Delete current save", value="yes", enabled=True, hint=summary),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ]
        choice = self.vertical_panel_select(
            "Delete Current Save",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice and choice.value == "yes":
            self.delete_current_save_and_restart()

    def show_slot_action_menu(self, slot_number: int):
        while True:
            summary = self.slot_summary(slot_number)
            items = [
                MenuItem(label="Save current here", value="save", enabled=True, hint=summary),
                MenuItem(label="Load this slot", value="load", enabled=summary != "empty", hint=summary),
                MenuItem(label="Delete this slot", value="delete", enabled=summary != "empty", hint=summary),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                f"Slot {slot_number}",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return MENU_BACK
            if choice.value == "save":
                self.confirm_save_slot(slot_number)
                return "changed"
            if choice.value == "load":
                self.confirm_load_slot(slot_number)
                return "changed"
            if choice.value == "delete":
                self.confirm_delete_slot(slot_number)
                return "changed"

    def show_save_manager(self):
        while True:
            items = [
                MenuItem(label="Save now", value="save_now", enabled=True, hint=self.current_save_summary()),
                MenuItem(label="Reload current save", value="reload", enabled=SAVE_PATH.exists(), hint=self.current_save_summary()),
                MenuItem(label="Delete current save", value="delete_current", enabled=SAVE_PATH.exists(), hint=self.current_save_summary()),
            ]
            for i in range(1, SAVE_SLOT_COUNT + 1):
                items.append(MenuItem(label=f"Slot {i}", value=f"slot:{i}", enabled=True, hint=self.slot_summary(i)))
            items.extend([
                MenuItem(label="Save location", value="location", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])

            choice = self.vertical_panel_select(
                "Save Manager",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )

            if choice is None or choice.value == MENU_BACK:
                return MENU_BACK

            if choice.value == "save_now":
                self.save()
                continue

            if choice.value == "reload":
                self.load()
                continue

            if choice.value == "delete_current":
                self.confirm_delete_current_save()
                continue

            if choice.value == "location":
                self.show_save_location()
                continue

            raw = str(choice.value)
            if raw.startswith("slot:"):
                slot_number = int(raw.split(":", 1)[1])
                self.show_slot_action_menu(slot_number)
                continue

    def save(self, quiet: bool = False, path: Optional[Path] = None):
        """Save the game, but never crash gameplay if saving fails."""
        target_path = path or SAVE_PATH
        data = {
            "save_schema_version": SAVE_SCHEMA_VERSION,
            "game_version": GAME_VERSION,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
            "state": asdict(self.state),
            "base_map": grid_to_save_rows(self.base_map),
            "town_map": grid_to_save_rows(self.town_map),
            "mine_map": grid_to_save_rows(self.get_mine_floor_map(self.state.mine_floor)),
            "mine_maps": {str(k): grid_to_save_rows(v) for k, v in getattr(self, "mine_maps", {}).items()},
            "mine_enemies": getattr(self, "mine_enemies", {}),
            "wilderness_map": grid_to_save_rows(self.get_wilderness_chunk_map(0, 0)),
            "wilderness_maps": {
                str(k): grid_to_save_rows(v)
                for k, v in getattr(self, "wilderness_maps", {}).items()
                if str(k) not in getattr(self, "_wilderness_stream_preloaded_chunks", set())
            },
            "wilderness_cave_maps": {str(k): grid_to_save_rows(v) for k, v in getattr(self, "wilderness_cave_maps", {}).items()},
            "wilderness_dungeon_maps": {str(k): grid_to_save_rows(v) for k, v in getattr(self, "wilderness_dungeon_maps", {}).items()},
            "wilderness_dungeon_enemies": getattr(self, "wilderness_dungeon_enemies", {}),
            "wilderness_stronghold_enemies": getattr(self, "wilderness_stronghold_enemies", {}),
            "wilderness_animals": {
                str(k): v
                for k, v in getattr(self, "wilderness_animals", {}).items()
                if (
                    str(k) not in getattr(self, "_wilderness_stream_preloaded_chunks", set())
                    or str(k) in getattr(self, "_wilderness_stream_dirty_actor_chunks", set())
                )
            },
            "crops": {k: asdict(v) for k, v in self.crops.items()},
        }
        for map_attr, _ in self.FIXED_INTERIOR_MAP_SPECS:
            data[map_attr] = grid_to_save_rows(getattr(self, map_attr))
        try:
            serialized = json.dumps(data, indent=2)
            rotate_save_backups(target_path)
            atomic_write_text(target_path, serialized)
            if not quiet:
                self.set_message(f"Game saved to: {target_path}")
            return True
        except Exception as exc:
            self.set_message(f"Could not save game to {target_path}: {exc}")
            return False

    def load_from_path(self, path: Path, allow_recovery: bool = True):
        """
        Load the save file defensively. If an older/broken save cannot be loaded,
        back it up and continue with a new game instead of crashing on startup.
        """
        if not path.exists():
            append_debug_log(f"load_from_path: no save at {path}")
            self.set_message(f"No save file found at: {path}")
            return False

        try:
            append_debug_log(f"load_from_path: reading {path}")
            data = json.loads(path.read_text(encoding="utf-8"))

            if not isinstance(data, dict):
                raise ValueError("Save file root is not an object.")
            try:
                schema_version = int(data.get("save_schema_version", 0))
            except (TypeError, ValueError):
                raise ValueError("Save schema version is invalid.")
            if schema_version < 0:
                raise ValueError("Save schema version is invalid.")
            if schema_version > SAVE_SCHEMA_VERSION:
                raise ValueError(
                    "This save was created by a newer version of Elsewhere "
                    f"(schema {schema_version}; supported {SAVE_SCHEMA_VERSION})."
                )
            if "state" not in data or "base_map" not in data or "crops" not in data:
                raise ValueError("Save file is missing required fields.")

            state_data = data["state"]
            if not isinstance(state_data, dict):
                raise ValueError("Save state is not an object.")
            actor_fields = {"last_grazed_day", "outside", "x", "y", "activity"}
            saved_animals = state_data.get("farm_animals", [])
            has_current_actor_fields = not isinstance(saved_animals, list) or all(
                not isinstance(animal, dict) or actor_fields.issubset(animal)
                for animal in saved_animals
            )

            self.state = GameState(**prepare_loaded_state_data(state_data))
            if hasattr(self, "ensure_container_state"):
                self.ensure_container_state()

            set_color_enabled(bool(self.state.color_enabled))

            loaded_map = saved_rows_to_grid(data["base_map"], WIDTH, HEIGHT, exact_size=False, uniform_width=True)
            if loaded_map is None:
                raise ValueError("Saved map has the wrong shape.")
            self.base_map = loaded_map

            # v135: always regenerate the exterior town map so old saves do not
            # restore the pre-grid town skeleton. Interiors and gameplay state still load.
            self.town_map = self.make_town_map()

            loaded_mine_maps = data.get("mine_maps")
            self.mine_maps = {}
            if isinstance(loaded_mine_maps, dict):
                for floor_key, rows in loaded_mine_maps.items():
                    loaded_floor = saved_rows_to_grid(rows, WIDTH, HEIGHT)
                    if str(floor_key).isdigit() and loaded_floor is not None:
                        self.mine_maps[str(floor_key)] = loaded_floor

            loaded_mine_map = data.get("mine_map")
            legacy_mine_map = saved_rows_to_grid(loaded_mine_map, WIDTH, HEIGHT)
            if not self.mine_maps and legacy_mine_map is not None:
                self.mine_maps["1"] = legacy_mine_map

            if not self.mine_maps:
                self.mine_maps["1"] = self.make_mine_map(1)

            self.state.mine_floor = max(1, min(MINE_MAX_FLOOR, int(getattr(self.state, "mine_floor", 1))))
            self.state.deepest_mine_floor = max(int(getattr(self.state, "deepest_mine_floor", 1)), self.state.mine_floor)
            self.mine_map = self.get_mine_floor_map(self.state.mine_floor)
            loaded_mine_enemies = data.get("mine_enemies")
            self.mine_enemies = {}
            if isinstance(loaded_mine_enemies, dict):
                for floor_key, enemies in loaded_mine_enemies.items():
                    if isinstance(floor_key, str) and floor_key.isdigit() and isinstance(enemies, list):
                        self.mine_enemies[str(int(floor_key))] = [enemy for enemy in enemies if isinstance(enemy, dict)]
            if hasattr(self, "normalize_mine_enemies"):
                self.normalize_mine_enemies()

            for map_attr, factory_name in self.FIXED_INTERIOR_MAP_SPECS:
                loaded_interior_map = saved_rows_to_grid(data.get(map_attr), WIDTH, HEIGHT)
                if loaded_interior_map is None:
                    loaded_interior_map = getattr(self, factory_name)()
                setattr(self, map_attr, loaded_interior_map)

            loaded_wilderness_maps = data.get("wilderness_maps")
            self.wilderness_maps = {}
            if isinstance(loaded_wilderness_maps, dict):
                for chunk_key, rows in loaded_wilderness_maps.items():
                    loaded_chunk = saved_rows_to_grid(rows, WIDTH, HEIGHT, exact_size=False)
                    if isinstance(chunk_key, str) and "," in chunk_key and loaded_chunk is not None:
                        self.wilderness_maps[chunk_key] = loaded_chunk

            loaded_wilderness_map = data.get("wilderness_map")
            if "0,0" not in self.wilderness_maps:
                loaded_origin = saved_rows_to_grid(loaded_wilderness_map, WIDTH, HEIGHT, exact_size=False)
                if loaded_origin is not None:
                    self.wilderness_maps["0,0"] = loaded_origin
                else:
                    self.wilderness_maps["0,0"] = self.make_wilderness_chunk(0, 0)

            loaded_wilderness_cave_maps = data.get("wilderness_cave_maps")
            self.wilderness_cave_maps = {}
            if isinstance(loaded_wilderness_cave_maps, dict):
                for cave_key, rows in loaded_wilderness_cave_maps.items():
                    loaded_cave = saved_rows_to_grid(rows, 8, 8, exact_size=False)
                    if isinstance(cave_key, str) and loaded_cave is not None:
                        self.wilderness_cave_maps[cave_key] = loaded_cave

            loaded_wilderness_dungeon_maps = data.get("wilderness_dungeon_maps")
            self.wilderness_dungeon_maps = {}
            if isinstance(loaded_wilderness_dungeon_maps, dict):
                for dungeon_key, rows in loaded_wilderness_dungeon_maps.items():
                    loaded_dungeon = saved_rows_to_grid(rows, 8, 8, exact_size=False)
                    if isinstance(dungeon_key, str) and loaded_dungeon is not None:
                        self.wilderness_dungeon_maps[dungeon_key] = loaded_dungeon

            loaded_wilderness_dungeon_enemies = data.get("wilderness_dungeon_enemies")
            self.wilderness_dungeon_enemies = {}
            if isinstance(loaded_wilderness_dungeon_enemies, dict):
                for dungeon_key, enemies in loaded_wilderness_dungeon_enemies.items():
                    if isinstance(dungeon_key, str) and isinstance(enemies, list):
                        self.wilderness_dungeon_enemies[dungeon_key] = [
                            enemy for enemy in enemies if isinstance(enemy, dict)
                        ]
            if hasattr(self, "normalize_wilderness_dungeon_enemies"):
                self.normalize_wilderness_dungeon_enemies()

            loaded_wilderness_stronghold_enemies = data.get("wilderness_stronghold_enemies")
            self.wilderness_stronghold_enemies = {}
            if isinstance(loaded_wilderness_stronghold_enemies, dict):
                for stronghold_key, enemies in loaded_wilderness_stronghold_enemies.items():
                    if isinstance(stronghold_key, str) and isinstance(enemies, list):
                        self.wilderness_stronghold_enemies[stronghold_key] = [
                            enemy for enemy in enemies if isinstance(enemy, dict)
                        ]
            if hasattr(self, "normalize_wilderness_stronghold_enemies"):
                self.normalize_wilderness_stronghold_enemies()

            loaded_wilderness_animals = data.get("wilderness_animals")
            self.wilderness_animals = {}
            if isinstance(loaded_wilderness_animals, dict):
                for animal_key, animals in loaded_wilderness_animals.items():
                    if isinstance(animal_key, str) and isinstance(animals, list):
                        clean_animals = []
                        for animal in animals:
                            if not isinstance(animal, dict):
                                continue
                            try:
                                species = str(animal.get("species", "Animal"))
                                clean_animals.append({
                                    "id": str(animal.get("id", f"{animal_key}:{len(clean_animals)}:{species}")),
                                    "species": species,
                                    "x": int(animal.get("x", 0)),
                                    "y": int(animal.get("y", 0)),
                                    "seen": bool(animal.get("seen", False)),
                                    "calm": int(animal.get("calm", 0)),
                                })
                            except Exception:
                                continue
                        self.wilderness_animals[animal_key] = clean_animals
            self._wilderness_stream_dirty_actor_chunks = set(self.wilderness_animals)

            self.ensure_wilderness_chunks()
            self.ensure_wilderness_caves()
            if hasattr(self, "ensure_wilderness_dungeons"):
                self.ensure_wilderness_dungeons()
            self.ensure_wilderness_animals()
            self.normalize_map_transitions()
            try:
                map_width = max(3, int(self.active_map_width()))
                map_height = max(3, int(self.active_map_height()))
                self.state.player_x = max(1, min(map_width - 2, int(self.state.player_x)))
                self.state.player_y = max(1, min(map_height - 2, int(self.state.player_y)))
            except (AttributeError, TypeError, ValueError):
                self.state.location = "Farm"
                self.state.player_x = 8
                self.state.player_y = 9

            loaded_crops = data["crops"]
            if not isinstance(loaded_crops, dict):
                raise ValueError("Saved crops field is not an object.")
            migrated_crops = {}
            for k, v in loaded_crops.items():
                if isinstance(v, dict):
                    v.setdefault("care_days", 0)
                    v.setdefault("missed_water_days", 0)
                    v.setdefault("fertilized", False)
                    migrated_crops[k] = Crop(**v)
            self.crops = migrated_crops
            self.normalize_farm_animals()
            if not has_current_actor_fields:
                self.update_farm_animal_actors(force=True)
            self.normalize_town_npcs()
            self.normalize_travel_followers()
            self.validate_active_scene_state()

            self.bed_pos = (6, 4)
            self.set_message(f"Loaded your farm from: {path}")
            return True

        except Exception as exc:
            append_debug_log(
                f"load_from_path failed: {path} | {type(exc).__name__}: {exc}"
            )
            if not allow_recovery:
                return False
            recovery_paths = [
                backup_path
                for backup_path in save_backup_paths(path)
                if backup_path.exists()
            ]
            broken_path = None
            try:
                broken_path = quarantine_broken_save(path)
            except Exception as quarantine_exc:
                append_debug_log(
                    "Could not quarantine broken save "
                    f"{path}: {type(quarantine_exc).__name__}: {quarantine_exc}"
                )
            for recovery_path in recovery_paths:
                append_debug_log(
                    f"Attempting automatic save recovery from {recovery_path}"
                )
                if not self.load_from_path(
                    recovery_path,
                    allow_recovery=False,
                ):
                    continue
                restored = self.save(quiet=True, path=path)
                if restored:
                    self.set_message(
                        f"Recovered your save from {recovery_path.name}. "
                        f"The unreadable file was kept as "
                        f"{broken_path.name if broken_path else 'a broken save'}."
                    )
                else:
                    self.set_message(
                        f"Loaded recovery copy {recovery_path.name}, but could "
                        "not restore the current save file. Save again manually."
                    )
                return True
            if broken_path:
                self.set_message(
                    f"Save could not load and no recovery copy worked. "
                    f"The unreadable file was kept as {broken_path}. Error: {exc}"
                )
            else:
                self.set_message(
                    f"Save could not load and no recovery copy worked. Error: {exc}"
                )
            return False

    def load(self):
        append_debug_log(f"load() called: {SAVE_PATH}")
        return self.load_from_path(SAVE_PATH)



__all__ = ["SaveLoadMixin"]
