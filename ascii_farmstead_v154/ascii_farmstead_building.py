from __future__ import annotations

"""Cursor-driven construction and placed-object relocation.

BuildingMixin expects a FarmGame-like object that provides map queries,
rendering, menus, persistence, inventory, and automation helpers. Keeping the
interactive build workspace here gives construction work a focused module
without changing the save format or the legacy entry point.
"""

from typing import List, Optional, Tuple

from ascii_farmstead_data import (
    INFRASTRUCTURE_DATA,
    LEFT_PANEL_HEIGHT,
    LEFT_PANEL_WIDTH,
    MENU_BACK,
    MENU_CONFIRM_KEYS,
    VIEW_HEIGHT,
    VIEW_WIDTH,
)
from ascii_farmstead_support import C, clear_screen, colorize, normalize_key, read_key
from ascii_farmstead_ui import MenuItem


class BuildingMixin:
    def object_has_attached_state(self, key: str, obj_name: str) -> bool:
        """Return whether moving this object must preserve location-keyed state."""
        if key in self.ensure_automation_machines():
            record = self.ensure_automation_machines().get(key)
            if isinstance(record, dict) and (
                int(record.get("seed_qty", 0) or 0) > 0
                or bool(record.get("seed_crop"))
            ):
                return True
        if key in self.state.artisan_processors:
            return True
        pond = self.state.fish_ponds.get(key)
        if isinstance(pond, dict) and (
            bool(pond.get("fish"))
            or int(pond.get("count", 0) or 0) > 0
            or int(pond.get("ready", 0) or 0) > 0
        ):
            return True
        if key in self.state.farm_building_harvest_days:
            return True
        if key in self.state.farm_building_boosts:
            return True
        if any(str(animal.get("building_key", "")) == key for animal in self.state.farm_animals):
            return True
        return False

    def object_store_block_reason(self, key: str, obj_name: str) -> str:
        """Explain why an object must be emptied before returning it to inventory."""
        if key in self.state.artisan_processors:
            return "finish and collect the Preserves Jar first, or move it instead"
        pond = self.state.fish_ponds.get(key)
        if isinstance(pond, dict) and (
            bool(pond.get("fish"))
            or int(pond.get("count", 0) or 0) > 0
            or int(pond.get("ready", 0) or 0) > 0
        ):
            return "clear and harvest the Fish Pond first, or move it instead"
        if any(str(animal.get("building_key", "")) == key for animal in self.state.farm_animals):
            return "this building houses animals; move it instead"
        return ""

    def clear_placed_object_state(self, key: str, obj_name: str):
        """Remove location-keyed state when an object truly leaves the map."""
        if obj_name == "Seed Hopper":
            self.unload_seed_hopper_key(key, quiet=True)
        self.ensure_automation_machines().pop(key, None)
        self.state.artisan_processors.pop(key, None)
        self.state.fish_ponds.pop(key, None)
        self.state.farm_building_harvest_days.pop(key, None)
        self.state.farm_building_boosts.pop(key, None)

    def rekey_placed_object_state(self, old_key: str, new_key: str):
        """Transfer every known object-attached record to a new anchor key."""
        if old_key == new_key:
            return
        keyed_mappings = [
            self.ensure_automation_machines(),
            self.state.artisan_processors,
            self.state.fish_ponds,
            self.state.farm_building_harvest_days,
            self.state.farm_building_boosts,
        ]
        for mapping in keyed_mappings:
            if old_key in mapping:
                mapping[new_key] = mapping.pop(old_key)
        for animal in self.state.farm_animals:
            if str(animal.get("building_key", "")) == old_key:
                animal["building_key"] = new_key

    def place_inventory_object_at(self, obj_name: str, x: int, y: int, autosave: bool = True) -> bool:
        """Place one inventory object while keeping the item selected for repeats."""
        if self.state.inventory.get(obj_name, 0) <= 0:
            self.set_message(f"You do not have a {obj_name} to place.")
            return False
        ok, reason = self.can_place_object(obj_name, x, y)
        if not ok:
            self.set_message(f"Cannot place {obj_name}: {reason}.")
            return False
        self.set_placed_object(x, y, obj_name)
        self.state.inventory[obj_name] = max(0, self.state.inventory.get(obj_name, 0) - 1)
        remaining = self.state.inventory.get(obj_name, 0)
        message = f"Placed {obj_name} at {x},{y}. {remaining} remaining."
        if autosave:
            self.autosave_with_message(message)
        else:
            self.set_message(message)
        return True

    def move_placed_object(self, old_key: str, x: int, y: int, autosave: bool = True) -> bool:
        """Atomically move an object and all records attached to its anchor key."""
        obj_name = self.state.placed_objects.get(old_key)
        if not obj_name:
            self.set_message("That object is no longer there.")
            return False
        parsed = self.parse_object_key(old_key)
        if not parsed or parsed[0] != self.current_object_location_key():
            self.set_message("Objects can only be moved within the current build area.")
            return False
        ok, reason = self.can_place_object(obj_name, x, y, ignore_object_key=old_key)
        if not ok:
            self.set_message(f"Cannot move {obj_name}: {reason}.")
            return False
        new_key = self.obj_key(x, y)
        if new_key != old_key:
            self.state.placed_objects.pop(old_key, None)
            self.state.placed_objects[new_key] = obj_name
            self.rekey_placed_object_state(old_key, new_key)
        message = f"Moved {obj_name} to {x},{y}."
        if autosave:
            self.autosave_with_message(message)
        else:
            self.set_message(message)
        return True

    def store_placed_object_at(self, x: int, y: int, autosave: bool = True) -> bool:
        """Return a placed object to inventory when doing so cannot lose contents."""
        key, obj_name, _ax, _ay = self.placed_object_at(x, y)
        if not key or not obj_name:
            self.set_message("There is no placed object under the cursor.")
            return False
        reason = self.object_store_block_reason(key, obj_name)
        if reason:
            self.set_message(f"Cannot store {obj_name}: {reason}.")
            return False
        self.clear_placed_object_state(key, obj_name)
        self.state.placed_objects.pop(key, None)
        self.state.inventory[obj_name] = self.state.inventory.get(obj_name, 0) + 1
        message = f"Stored {obj_name} in inventory."
        if autosave:
            self.autosave_with_message(message)
        else:
            self.set_message(message)
        return True

    def infrastructure_items_in_inventory(self) -> List[Tuple[str, int]]:
        return [
            (name, self.state.inventory.get(name, 0))
            for name in INFRASTRUCTURE_DATA
            if self.state.inventory.get(name, 0) > 0
        ]

    def placed_objects_in_current_scope(self) -> List[Tuple[str, str]]:
        scope = self.current_object_location_key()
        objects: List[Tuple[str, str]] = []
        for key, obj_name in self.state.placed_objects.items():
            parsed = self.parse_object_key(str(key))
            if parsed and parsed[0] == scope:
                objects.append((str(key), str(obj_name)))
            elif scope == "Farm" and parsed and ":" not in str(key) and parsed[0] == "Farm":
                objects.append((str(key), str(obj_name)))
        return objects

    def build_palette_menu(self, selected_obj: Optional[str] = None) -> Tuple[str, Optional[str]]:
        items: List[MenuItem] = [
            MenuItem(
                label="Move existing objects",
                value=("move", None),
                enabled=bool(self.placed_objects_in_current_scope()),
                hint="cursor pickup/move",
            )
        ]
        for name, qty in self.infrastructure_items_in_inventory():
            data = INFRASTRUCTURE_DATA[name]
            category = str(data.get("category", "infrastructure"))
            hint = f"x{qty} {self.footprint_label(name)}"
            if category == "automation":
                hint = f"x{qty} automation"
            elif category == "furniture":
                hint = f"x{qty} furniture"
            if name == selected_obj:
                hint += " selected"
            items.append(MenuItem(label=name, value=("select", name), enabled=True, hint=hint))
        items.extend([
            MenuItem(label="Exit Build Mode", value=("exit", None), enabled=True),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ])
        choice = self.vertical_panel_select(
            "Build Palette",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return "back", selected_obj
        action, obj_name = choice.value
        return str(action), str(obj_name) if obj_name else None

    def show_place_item_menu(self):
        return self.build_mode(open_palette=True)

    def placement_mode(self, obj_name: str):
        """Compatibility entry point for callers that preselect an item."""
        return self.build_mode(initial_obj=obj_name)

    def show_pickup_object_menu(self):
        return self.build_mode()

    def pickup_mode(self):
        """Compatibility entry point for the old front-tile pickup mode."""
        return self.build_mode()

    def build_mode(self, initial_obj: Optional[str] = None, open_palette: bool = False):
        """Unified cursor workspace for placing, moving, and storing objects."""
        if not self.can_hold_objects_here():
            self.set_message("Build Mode is available on owned farm land and inside the farmhouse.")
            return MENU_BACK

        selected_obj = initial_obj if initial_obj and self.state.inventory.get(initial_obj, 0) > 0 else None
        moving_key: Optional[str] = None
        cursor_x, cursor_y = self.target_tile_pos()
        if not self.in_active_bounds(cursor_x, cursor_y):
            cursor_x, cursor_y = self.state.player_x, self.state.player_y

        if initial_obj and not selected_obj:
            self.set_message(f"You do not have a {initial_obj} to place.")
        else:
            self.set_message("Build Mode active. Move the cursor anywhere in this area.")

        palette_pending = bool(open_palette)
        opening_palette = bool(open_palette)
        while True:
            if palette_pending:
                action, palette_obj = self.build_palette_menu(selected_obj)
                palette_pending = False
                if action == "exit":
                    self.set_message("Build Mode closed. Camera recentered on you.")
                    self.invalidate_draw_cache()
                    return "closed"
                if action == "select" and palette_obj:
                    selected_obj = palette_obj
                    moving_key = None
                    self.set_message(f"Selected {selected_obj}. Place repeatedly with Z/Enter.")
                elif action == "move":
                    selected_obj = None
                    moving_key = None
                    self.set_message("Move mode selected. Put the cursor on an object and press Z/Enter.")
                elif action == "back" and opening_palette and initial_obj is None:
                    self.set_message("Build Mode cancelled.")
                    return MENU_BACK
                opening_palette = False

            self.draw_build_workspace(cursor_x, cursor_y, selected_obj, moving_key)
            key = normalize_key(read_key())
            if len(key) == 1 and key.isalpha():
                key = key.lower()

            if key in ["\t", "\x1b", "q", "b"]:
                if moving_key:
                    obj_name = self.state.placed_objects.get(moving_key, "object")
                    self.set_message(f"Cancelled moving {obj_name}; it remains in its original position.")
                else:
                    self.set_message("Build Mode closed. Camera recentered on you.")
                self.invalidate_draw_cache()
                return "closed"

            dx, dy = 0, 0
            if key in ["w", "UP"]:
                dy = -1
            elif key in ["s", "DOWN"]:
                dy = 1
            elif key in ["a", "LEFT"]:
                dx = -1
            elif key in ["d", "RIGHT"]:
                dx = 1
            if dx or dy:
                cursor_x = max(0, min(self.active_map_width() - 1, cursor_x + dx))
                cursor_y = max(0, min(self.active_map_height() - 1, cursor_y + dy))
                continue

            if key == "p":
                palette_pending = True
                continue

            if key == "c":
                if moving_key:
                    obj_name = self.state.placed_objects.get(moving_key, "object")
                    moving_key = None
                    self.set_message(f"Cancelled moving {obj_name}; the original was never removed.")
                elif selected_obj:
                    self.set_message(f"Cleared {selected_obj} selection. Cursor is ready to move existing objects.")
                    selected_obj = None
                else:
                    self.set_message("Nothing is currently selected.")
                continue

            if key == "i":
                self.vertical_panel_view(
                    "Build Inspection",
                    self.look_tile_lines(cursor_x, cursor_y),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                self.invalidate_draw_cache()
                continue

            if key == "x":
                target_x, target_y = cursor_x, cursor_y
                if moving_key:
                    parsed = self.parse_object_key(moving_key)
                    if parsed:
                        _scope, target_x, target_y = parsed
                if self.store_placed_object_at(target_x, target_y):
                    moving_key = None
                continue

            if key in MENU_CONFIRM_KEYS:
                if moving_key:
                    if self.move_placed_object(moving_key, cursor_x, cursor_y):
                        moving_key = None
                    continue

                if selected_obj:
                    if self.place_inventory_object_at(selected_obj, cursor_x, cursor_y):
                        if self.state.inventory.get(selected_obj, 0) <= 0:
                            self.set_message(f"Placed your last {selected_obj}. Press P to choose another item.")
                            selected_obj = None
                    continue

                target_key, target_obj, _ax, _ay = self.placed_object_at(cursor_x, cursor_y)
                if target_key and target_obj:
                    moving_key = target_key
                    self.set_message(f"Moving {target_obj}. Choose a destination and press Z/Enter; C cancels.")
                else:
                    palette_pending = True
                continue

            self.set_message("Build Mode: move cursor, Z act, P palette, X store, I inspect, C cancel.")

    def draw_build_workspace(
        self,
        cursor_x: int,
        cursor_y: int,
        selected_obj: Optional[str] = None,
        moving_key: Optional[str] = None,
    ):
        self.invalidate_draw_cache()
        clear_screen()
        for line in self.header_lines():
            print(line)

        moving_obj = self.state.placed_objects.get(moving_key, "") if moving_key else ""
        preview_obj = moving_obj or selected_obj or ""
        ignore_key = moving_key if moving_obj else None
        ok, reason = (
            self.can_place_object(preview_obj, cursor_x, cursor_y, ignore_key)
            if preview_obj
            else (False, "no item selected")
        )
        target_key, target_obj, target_ax, target_ay = self.placed_object_at(cursor_x, cursor_y)
        if preview_obj:
            highlight = set(self.object_footprint_tiles(preview_obj, cursor_x, cursor_y))
            anchor = (cursor_x, cursor_y)
        elif target_obj and target_ax is not None and target_ay is not None:
            highlight = set(self.object_footprint_tiles(target_obj, target_ax, target_ay))
            anchor = (target_ax, target_ay)
        else:
            highlight = {(cursor_x, cursor_y)}
            anchor = (cursor_x, cursor_y)

        cam_x, cam_y = self.camera_origin_for_cursor(cursor_x, cursor_y)
        map_w = self.active_map_width()
        map_h = self.active_map_height()
        npc_positions = self.town_npc_position_lookup()

        for screen_y in range(VIEW_HEIGHT):
            world_y = cam_y + screen_y
            line = []
            for screen_x in range(VIEW_WIDTH):
                world_x = cam_x + screen_x
                npc = npc_positions.get((world_x, world_y))
                if world_x >= map_w or world_y >= map_h:
                    line.append(" ")
                elif (world_x, world_y) in highlight:
                    marker = "X" if (world_x, world_y) == anchor else "x"
                    valid_highlight = ok if preview_obj else bool(target_obj)
                    line.append(colorize(marker, C.PLACEMENT if valid_highlight else C.PLACEMENT_BAD))
                elif world_x == self.state.player_x and world_y == self.state.player_y:
                    line.append(self.render_player())
                elif self.on_farm() and self.farm_animal_at(world_x, world_y):
                    line.append(self.render_farm_animal(self.farm_animal_at(world_x, world_y)))
                elif self.travel_follower_at(world_x, world_y):
                    line.append(self.render_travel_follower(self.travel_follower_at(world_x, world_y)))
                elif npc:
                    line.append(self.render_town_npc(npc))
                else:
                    overlay = self.render_weather_overlay(world_x, world_y)
                    if overlay is not None:
                        line.append(overlay)
                    else:
                        line.append(self.render_tile(world_x, world_y))
            print("".join(line))

        for line in self.footer_lines():
            print(line)

        if moving_obj:
            print(
                f"Moving: {moving_obj} ({self.footprint_label(moving_obj)}) | "
                f"Destination: {cursor_x},{cursor_y} | {'OK' if ok else 'Blocked: ' + reason}"
            )
        elif selected_obj:
            qty = self.state.inventory.get(selected_obj, 0)
            print(
                f"Building: {selected_obj} x{qty} ({self.footprint_label(selected_obj)}) | "
                f"Anchor: {cursor_x},{cursor_y} | {'OK' if ok else 'Blocked: ' + reason}"
            )
        elif target_obj:
            state_note = " | attached state" if target_key and self.object_has_attached_state(target_key, target_obj) else ""
            print(f"Cursor: {cursor_x},{cursor_y} | {target_obj} ({self.footprint_label(target_obj)}){state_note}")
        else:
            print(f"Cursor: {cursor_x},{cursor_y} | Empty build tile | Press P for the palette")
        print("WASD/Arrows move cursor | Z/Enter place/pick/move | P palette | X store")
        print("I inspect | C cancel/clear selection | B/Q/Esc/Tab exit")

    def draw_with_pickup_cursor(self):
        """Compatibility renderer for the former pickup mode."""
        x, y = self.target_tile_pos()
        self.draw_build_workspace(x, y)

    def draw_with_placement_cursor(self, obj_name: str):
        """Compatibility renderer for the former placement mode."""
        x, y = self.target_tile_pos()
        self.draw_build_workspace(x, y, selected_obj=obj_name)
