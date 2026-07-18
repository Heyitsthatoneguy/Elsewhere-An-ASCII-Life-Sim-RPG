"""Physical, useful wilderness landmark sites."""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

from ascii_farmstead_inventory import add_inventory_items, format_drops


class WildernessLandmarkMixin:
    """Multi-tile landmark construction and action-led interactions."""

    LANDMARK_PROTECTED = {"S", "V", "X", "!", "A", "E", "q", "k", "h", ":", "="}

    def _landmark_set(
        self, grid: List[List[str]], x: int, y: int, tile: str,
        preserve_water: bool = True, overwrite_route: bool = False,
    ) -> None:
        if not grid or not (1 <= y < len(grid) - 1 and 1 <= x < len(grid[0]) - 1):
            return
        old = grid[y][x]
        if old in self.LANDMARK_PROTECTED and not (overwrite_route and old == ":"):
            return
        if preserve_water and old in {"~", "="}:
            return
        grid[y][x] = tile

    def _landmark_clear(self, grid: List[List[str]], cx: int, cy: int, rx: int, ry: int, floor: str = ".") -> None:
        for y in range(max(1, cy - ry), min(len(grid) - 1, cy + ry + 1)):
            for x in range(max(1, cx - rx), min(len(grid[0]) - 1, cx + rx + 1)):
                if grid[y][x] not in self.LANDMARK_PROTECTED | {"~", "="}:
                    grid[y][x] = floor

    def choose_wilderness_landmark_center(
        self, grid: List[List[str]], preferred_x: int, preferred_y: int
    ) -> Tuple[int, int]:
        """Move a planned site locally onto a dry footprint without changing its chunk identity."""
        if not grid:
            return int(preferred_x), int(preferred_y)
        h, w = len(grid), len(grid[0])
        candidates = []
        for y in range(max(6, int(preferred_y) - 11), min(h - 6, int(preferred_y) + 12), 2):
            for x in range(max(9, int(preferred_x) - 15), min(w - 9, int(preferred_x) + 16), 2):
                if grid[y][x] in self.LANDMARK_PROTECTED | {"~", "#"}:
                    continue
                footprint = [
                    grid[yy][xx]
                    for yy in range(y - 4, y + 5)
                    for xx in range(x - 8, x + 9)
                ]
                dry = sum(tile not in {"~", "="} for tile in footprint)
                conflicts = sum(tile in self.LANDMARK_PROTECTED for tile in footprint)
                distance = abs(x - int(preferred_x)) + abs(y - int(preferred_y))
                candidates.append((dry * 3 - conflicts * 12 - distance, x, y))
        if not candidates:
            return max(9, min(w - 10, int(preferred_x))), max(6, min(h - 7, int(preferred_y)))
        _score, x, y = max(candidates)
        return x, y

    def stamp_wilderness_landmark_site(
        self, grid: List[List[str]], cx: int, cy: int, type_id: str, rng: random.Random
    ) -> None:
        """Build a complete outdoor site around one functional anchor."""
        if not grid:
            return
        h, w = len(grid), len(grid[0])
        cx, cy = max(9, min(w - 10, int(cx))), max(6, min(h - 7, int(cy)))

        if type_id == "ranger_camp":
            self._landmark_clear(grid, cx, cy, 8, 5)
            for tent_x in (cx - 5, cx + 3):
                for x in range(tent_x - 2, tent_x + 3):
                    self._landmark_set(grid, x, cy - 3, "#")
                for y in range(cy - 3, cy + 1):
                    self._landmark_set(grid, tent_x - 2, y, "#")
                    self._landmark_set(grid, tent_x + 2, y, "#")
                self._landmark_set(grid, tent_x, cy, ".")
            self._landmark_set(grid, cx, cy + 1, "H")
            self._landmark_set(grid, cx + 3, cy + 2, "B")
            self._landmark_set(grid, cx - 2, cy + 2, "R", overwrite_route=True)
        elif type_id == "stone_ruin":
            self._landmark_clear(grid, cx, cy, 9, 5, ",")
            for x in range(cx - 7, cx + 8):
                if x not in {cx - 1, cx, cx + 1}:
                    self._landmark_set(grid, x, cy - 4, "#")
                if x not in {cx, cx + 1}:
                    self._landmark_set(grid, x, cy + 4, "#")
            for y in range(cy - 4, cy + 5):
                if y not in {cy - 1, cy, cy + 1}:
                    self._landmark_set(grid, cx - 7, y, "#")
                    self._landmark_set(grid, cx + 7, y, "#")
            for dx, dy in ((-4, -2), (4, -2), (-4, 2), (4, 2), (0, -2)):
                self._landmark_set(grid, cx + dx, cy + dy, "J")
            self._landmark_set(grid, cx, cy, "P", overwrite_route=True)
        elif type_id == "trail_shelter":
            self._landmark_clear(grid, cx, cy, 7, 5)
            for x in range(cx - 5, cx + 6):
                self._landmark_set(grid, x, cy - 3, "#")
                self._landmark_set(grid, x, cy + 2, "#")
            for y in range(cy - 3, cy + 3):
                self._landmark_set(grid, cx - 5, y, "#")
                self._landmark_set(grid, cx + 5, y, "#")
            self._landmark_set(grid, cx, cy + 2, ".")
            self._landmark_set(grid, cx - 3, cy, "H")
            self._landmark_set(grid, cx + 3, cy, "B")
            self._landmark_set(grid, cx + 5, cy + 3, "Q", overwrite_route=True)
        elif type_id == "overlook":
            self._landmark_clear(grid, cx, cy, 8, 5)
            for y in range(cy - 3, cy + 2):
                for x in range(cx - 6, cx + 7):
                    self._landmark_set(grid, x, y, ",")
            for x in range(cx - 6, cx + 7):
                self._landmark_set(grid, x, cy - 3, "#")
            for y in range(cy - 3, cy + 2):
                self._landmark_set(grid, cx - 6, y, "#")
                self._landmark_set(grid, cx + 6, y, "#")
            self._landmark_set(grid, cx, cy - 1, "K", overwrite_route=True)
        elif type_id == "old_quarry":
            self._landmark_clear(grid, cx, cy, 9, 5, "x")
            for radius in (8, 6, 4):
                for x in range(cx - radius, cx + radius + 1):
                    if rng.random() < 0.72:
                        self._landmark_set(grid, x, cy - max(2, radius // 2), "#")
            for dx, dy in ((-5, 1), (4, -1), (6, 2), (-2, -2)):
                self._landmark_set(grid, cx + dx, cy + dy, "M")
            self._landmark_set(grid, cx, cy, "?", overwrite_route=True)
        elif type_id in {"spring_garden", "fungal_garden"}:
            floor = ";" if type_id == "spring_garden" else "l"
            crop = "Y" if type_id == "spring_garden" else "u"
            self._landmark_clear(grid, cx, cy, 9, 5, floor)
            for x in range(cx - 8, cx + 9):
                if x not in {cx, cx + 1}:
                    self._landmark_set(grid, x, cy - 4, "#")
                    self._landmark_set(grid, x, cy + 4, "#")
            for y in range(cy - 4, cy + 5):
                self._landmark_set(grid, cx - 8, y, "#")
                self._landmark_set(grid, cx + 8, y, "#")
            for y in (cy - 2, cy, cy + 2):
                for x in range(cx - 6, cx + 7, 3):
                    if (x, y) != (cx, cy):
                        self._landmark_set(grid, x, y, crop)
            self._landmark_set(grid, cx + 5, cy, "~", preserve_water=False)
            self._landmark_set(grid, cx, cy, "?", overwrite_route=True)
        else:
            self._landmark_clear(grid, cx, cy, 8, 5)
            for dx, dy in ((-5, 0), (5, 0), (0, -3), (-4, -2), (4, -2), (-4, 2), (4, 2)):
                self._landmark_set(grid, cx + dx, cy + dy, "#")
            for x in range(cx - 7, cx + 8):
                self._landmark_set(grid, x, cy, ":")
            for y in range(cy - 4, cy + 6):
                self._landmark_set(grid, cx, y, ":")
            self._landmark_set(grid, cx, cy, "?", overwrite_route=True)

        for y in range(cy + 3, min(h - 1, cy + 7)):
            self._landmark_set(grid, cx, y, ":")

    def stamp_wilderness_field_station(self, grid: List[List[str]], x: int, y: int, biome: str) -> None:
        """Turn a field marker into a working survey compound."""
        self._landmark_clear(grid, x, y, 7, 4, biome if biome not in {"~", "="} else ".")
        for xx in range(x - 5, x + 6):
            self._landmark_set(grid, xx, y - 3, "#")
        for yy in range(y - 3, y + 2):
            self._landmark_set(grid, x - 5, yy, "#")
        self._landmark_set(grid, x - 5, y, ".")
        for xx in (x - 3, x, x + 3):
            self._landmark_set(grid, xx, y + 2, ",")
            self._landmark_set(grid, xx, y + 3, ",")
        self._landmark_set(grid, x, y, "E", overwrite_route=True)
        self._landmark_set(grid, x + 3, y - 1, "B")
        for yy in range(y + 3, min(len(grid) - 1, y + 7)):
            self._landmark_set(grid, x, yy, ":")

    def stamp_wilderness_vitality_site(
        self, grid: List[List[str]], x: int, y: int, kind: str, symbol: str
    ) -> None:
        """Build the public facilities unlocked by long-term regional care."""
        x = max(8, min(len(grid[0]) - 9, int(x)))
        y = max(6, min(len(grid) - 7, int(y)))
        self._landmark_clear(grid, x, y, 7, 5)
        if kind == "refuge":
            for xx in range(x - 6, x + 7):
                if xx not in {x, x + 1}:
                    self._landmark_set(grid, xx, y - 4, "#")
                    self._landmark_set(grid, xx, y + 3, "#")
            for yy in range(y - 4, y + 4):
                self._landmark_set(grid, x - 6, yy, "#")
                self._landmark_set(grid, x + 6, yy, "#")
            for dx, dy in ((-3, -1), (-2, -1), (3, 1), (4, 1)):
                self._landmark_set(grid, x + dx, y + dy, "~", preserve_water=False)
        elif kind == "staffed_site":
            for xx in range(x - 5, x + 6):
                self._landmark_set(grid, xx, y - 3, "#")
            for yy in range(y - 3, y + 2):
                self._landmark_set(grid, x - 5, yy, "#")
            self._landmark_set(grid, x + 4, y - 1, "B")
            self._landmark_set(grid, x - 2, y + 2, "H")
        else:
            for xx in range(x - 5, x + 6):
                self._landmark_set(grid, xx, y - 3, "#")
            self._landmark_set(grid, x - 5, y - 2, "#")
            self._landmark_set(grid, x + 5, y - 2, "#")
            self._landmark_set(grid, x - 3, y + 1, "H")
            self._landmark_set(grid, x + 3, y + 1, "B")
        self._landmark_set(grid, x, y, symbol, overwrite_route=True)
        for yy in range(y + 3, min(len(grid) - 1, y + 7)):
            self._landmark_set(grid, x, yy, ":")

    def stamp_wilderness_landscape_facilities(
        self, grid: List[List[str]], cx: int, cy: int, kind: str, marker: Tuple[int, int]
    ) -> None:
        """Add purpose-built paths and facilities to a broad natural formation."""
        mx, my = marker
        if kind in {"large_lake", "floodplain", "archipelago"}:
            for x in range(max(2, cx - 10), min(len(grid[0]) - 2, cx + 11)):
                if grid[cy][x] == "~":
                    grid[cy][x] = "="
            self._landmark_set(grid, max(2, min(len(grid[0]) - 3, cx + 8)), cy, "k", preserve_water=False)
        elif kind == "waterfall":
            for x in range(cx - 5, cx + 6):
                self._landmark_set(grid, x, cy + 3, "=")
            self._landmark_set(grid, cx + 6, cy - 2, "K")
        elif kind == "hot_springs":
            for dx, dy in ((-5, -2), (-4, -2), (-5, -1), (4, 2), (5, 2), (5, 1)):
                self._landmark_set(grid, cx + dx, cy + dy, "~", preserve_water=False)
            self._landmark_set(grid, cx - 8, cy + 2, "Q")
            self._landmark_set(grid, cx - 5, cy + 3, "H")
        elif kind in {"ravine", "rocky_valley", "snowy_highlands"}:
            for offset in range(-10, 11):
                self._landmark_set(grid, cx + offset, cy + (abs(offset) // 4) - 2, ":")
            self._landmark_set(grid, cx + 8, cy - 3, "K")
        elif kind in {"pine_forest", "birch_grove"}:
            for x in range(cx - 9, cx + 10):
                self._landmark_set(grid, x, cy - 3, ":")
                self._landmark_set(grid, x, cy + 3, ":")
            for y in range(cy - 3, cy + 4):
                self._landmark_set(grid, cx - 9, y, ":")
                self._landmark_set(grid, cx + 9, y, ":")
        else:
            for x in range(cx - 9, cx + 10):
                self._landmark_set(grid, x, cy, ":")
            for y in range(cy - 4, cy + 5):
                self._landmark_set(grid, cx, y, ":")
        self._landmark_set(grid, mx, my, "j", preserve_water=False, overwrite_route=True)

    def wilderness_landmark_kind_at(self, x: int, y: int) -> str:
        grid = self.active_map()
        nearby = {
            grid[yy][xx]
            for yy in range(max(0, int(y) - 6), min(len(grid), int(y) + 7))
            for xx in range(max(0, int(x) - 9), min(len(grid[0]), int(x) + 10))
        }
        if "R" in nearby: return "ranger_camp"
        if "P" in nearby or "J" in nearby: return "stone_ruin"
        if "K" in nearby: return "overlook"
        if "Q" in nearby: return "trail_shelter"
        if "M" in nearby: return "old_quarry"
        if "u" in nearby: return "fungal_garden"
        if "Y" in nearby or "G" in nearby: return "spring_garden"
        return "waystone"

    def _nearest_landmark_symbol(self, x: int, y: int, symbol: str) -> Tuple[int, int]:
        grid = self.active_map()
        candidates = [
            (abs(xx - int(x)) + abs(yy - int(y)), xx, yy)
            for yy in range(max(0, int(y) - 7), min(len(grid), int(y) + 8))
            for xx in range(max(0, int(x) - 10), min(len(grid[0]), int(x) + 11))
            if grid[yy][xx] == symbol
        ]
        best = min(candidates) if candidates else (0, int(x), int(y))
        return best[1], best[2]

    def map_nearby_wilderness_chunks(self, radius: int = 1) -> int:
        """Reveal nearby coordinates without generating or visiting terrain."""
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        added = 0
        for ty in range(cy - int(radius), cy + int(radius) + 1):
            for tx in range(cx - int(radius), cx + int(radius) + 1):
                mapped = self.wilderness_region_record(tx, ty).setdefault("mapped_chunks", [])
                key = f"{tx},{ty}"
                if key not in mapped:
                    mapped.append(key)
                    added += 1
        return added

    def work_wilderness_minor_landmark(self, x: int, y: int, kind: str) -> bool:
        record = self.wilderness_poi_record(x, y, f"landmark_{kind}")
        week = self.stronghold_cache_week_key()
        if record.get("work_week") == week:
            self.set_message("This landmark's useful work is already complete for the week.")
            return False
        if kind == "old_quarry":
            if not self.owns_tool("Pickaxe"):
                self.set_message("You need a Pickaxe to work the old quarry safely.")
                return False
            if not self.spend_stamina(7): return False
            rng = self.wilderness_poi_rng(x, y, kind, 55001 + int(self.state.year) * 53 + int(self.state.day))
            drops = {"Stone": rng.randint(4, 7), "Coal": rng.randint(1, 2)}
            if rng.random() < 0.45: drops["Copper Ore"] = 1
            minutes, message = 55, "Worked the quarry's accessible seam"
        elif kind in {"spring_garden", "fungal_garden"}:
            if not self.spend_stamina(4): return False
            if kind == "fungal_garden":
                drops = {"Mushrooms": 2, "Fiber": 1}
                if self.state.season == "Spring": drops["Morel"] = 1
            else:
                seasonal = {"Spring": "Salmonberry", "Summer": "Wild Herbs", "Fall": "Blackberry", "Winter": "Winter Root"}.get(str(self.state.season), "Wild Herbs")
                drops = {seasonal: 2, "Mixed Seeds": 1}
            minutes, message = 40, "Tended the abandoned growing beds"
        else:
            if not self.spend_stamina(3): return False
            mapped, drops = self.map_nearby_wilderness_chunks(1), {}
            minutes, message = 25, f"Aligned the waystones and charted {mapped} nearby area(s)"
        if drops: add_inventory_items(self.state.inventory, drops)
        self.advance_time(minutes)
        record["work_week"] = week
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 1, message.lower())
        reward = f": {format_drops(drops)}" if drops else "."
        self.autosave_with_message(f"{message}{reward}")
        return True

    def open_wilderness_minor_landmark(self, x: int, y: int) -> None:
        kind = self.wilderness_landmark_kind_at(x, y)
        redirects = {
            "ranger_camp": ("R", self.show_wilderness_ranger_camp),
            "stone_ruin": ("P", self.open_wilderness_ruin_site),
            "overlook": ("K", self.open_wilderness_overlook_site),
            "trail_shelter": ("Q", self.show_wilderness_shelter_menu),
        }
        if kind in redirects:
            symbol, callback = redirects[kind]
            callback(*self._nearest_landmark_symbol(x, y, symbol))
            return
        names = {"old_quarry": "Old Quarry", "spring_garden": "Abandoned Spring Garden", "fungal_garden": "Sheltered Fungal Garden", "waystone": "Waystone Crossroads"}
        labels = {"old_quarry": "Work the accessible seam", "spring_garden": "Tend the growing beds", "fungal_garden": "Tend the fungal beds", "waystone": "Align stones and chart trails"}
        choice = self.vertical_panel_select(
            names.get(kind, "Wilderness Landmark"),
            [self._wilderness_menu_item("work", labels.get(kind, "Use landmark"), "A concrete weekly activity tied to this place.")],
            48, 18, return_back=True,
        )
        if choice and choice.value == "work":
            self.work_wilderness_minor_landmark(x, y, kind)

    def excavate_wilderness_ruin(self, x: int, y: int) -> bool:
        record = self.wilderness_poi_record(x, y, "ruin")
        week = self.stronghold_cache_week_key()
        if record.get("excavation_week") == week:
            self.set_message("The safe excavation areas have already been worked this week.")
            return False
        if not self.spend_stamina(5): return False
        rng = self.wilderness_poi_rng(x, y, "ruin", 56000 + int(self.state.year) * 97 + int(self.state.day))
        drops: Dict[str, int] = {"Ruin Scrap": rng.randint(1, 2), "Stone": rng.randint(1, 3)}
        if rng.random() < 0.45: drops["Mixed Seeds"] = 1
        if rng.random() < 0.12: drops["Ancient Seed"] = 1
        add_inventory_items(self.state.inventory, drops)
        self.advance_time(45)
        record["excavation_week"] = week
        record["excavations"] = int(record.get("excavations", 0)) + 1
        self.autosave_with_message(f"Excavated the ruin and recovered {format_drops(drops)}.")
        return True

    def restore_wilderness_ruin(self, x: int, y: int) -> bool:
        record = self.wilderness_poi_record(x, y, "ruin")
        if record.get("restored"):
            self.set_message("The ruin's courtyard and route stones are already restored.")
            return False
        materials = {"Stone": 10, "Wood": 4}
        missing = {item: qty - int(self.state.inventory.get(item, 0)) for item, qty in materials.items() if int(self.state.inventory.get(item, 0)) < qty}
        if missing:
            self.set_message(f"Restoration needs {format_drops(missing)}.")
            return False
        for item, qty in materials.items(): self.state.inventory[item] -= qty
        record["restored"] = True
        self.advance_time(120)
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 6, "restored old route monument")
        grid = self.active_map()
        for yy in range(max(1, y - 4), min(len(grid) - 1, y + 5)):
            for xx in range(max(1, x - 7), min(len(grid[0]) - 1, x + 8)):
                if grid[yy][xx] == "J": grid[yy][xx] = "#"
        self.autosave_with_message("Restored the ruin's courtyard and reopened its old route marker.")
        return True

    def open_wilderness_ruin_site(self, x: int, y: int) -> None:
        record = self.wilderness_poi_record(x, y, "ruin")
        items = [self._wilderness_menu_item("excavate", "Excavate a safe section", "Weekly salvage and archaeology work.")]
        if record.get("restored"):
            items.append(self._wilderness_menu_item("route", "Use restored route marker", "Chart the surrounding wilderness."))
        else:
            items.append(self._wilderness_menu_item("restore", "Restore courtyard - 10 Stone, 4 Wood", "Permanent regional improvement."))
        choice = self.vertical_panel_select("Old Route Ruin", items, 48, 18, return_back=True)
        if not choice: return
        if choice.value == "excavate": self.excavate_wilderness_ruin(x, y)
        elif choice.value == "restore": self.restore_wilderness_ruin(x, y)
        elif choice.value == "route":
            added = self.map_nearby_wilderness_chunks(2)
            self.advance_time(20)
            self.autosave_with_message(f"Used the restored route marker to chart {added} nearby area(s).")

    def open_wilderness_overlook_site(self, x: int, y: int) -> None:
        record = self.wilderness_poi_record(x, y, "overlook")
        choice = self.vertical_panel_select(
            "Wilderness Overlook",
            [
                self._wilderness_menu_item("survey", "Survey the surrounding region", "Chart regional terrain from the platform."),
                self._wilderness_menu_item("watch", "Observe wildlife movement", "A short daily observation that improves regional care."),
            ],
            48, 18, return_back=True,
        )
        if not choice: return
        if choice.value == "survey":
            week = self.stronghold_cache_week_key()
            if record.get("survey_week") == week:
                self.set_message("You already completed this overlook's survey this week.")
                return
            if not self.spend_stamina(4): return
            added = self.map_current_wilderness_region()
            self.advance_time(35)
            record["survey_week"] = week
            self.autosave_with_message(f"Surveyed from the overlook and charted {added} regional area(s).")
        elif choice.value == "watch":
            day = self.errand_day_key()
            if record.get("watch_day") == day:
                self.set_message("You already completed today's wildlife watch here.")
                return
            self.advance_time(25)
            record["watch_day"] = day
            self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 1, "overlook wildlife watch")
            self.autosave_with_message("Completed a wildlife watch from the overlook. Regional vitality increased.")

    def explore_wilderness_landscape_route(self) -> bool:
        record = self.wilderness_landscape_record()
        day = self.errand_day_key()
        if record.get("route_day") == day:
            self.set_message("You already completed this landmark route today.")
            return False
        if not self.spend_stamina(5): return False
        kind = str(record.get("type_id", "moorland"))
        drops = {
            "large_lake": {"Marsh Reed": 2}, "floodplain": {"Clay": 2, "Marsh Reed": 1},
            "pine_forest": {"Wood": 2, "Fiber": 1}, "birch_grove": {"Wood": 1, "Wild Herbs": 1},
            "flower_field": {"Wildflower": 2}, "moorland": {"Fiber": 2},
            "rocky_valley": {"Stone": 3}, "snowy_highlands": {"Stone": 2, "Winter Root": 1},
            "ravine": {"Stone": 2, "Wild Herbs": 1}, "hot_springs": {"Wild Herbs": 2},
            "waterfall": {"Stone": 1, "Marsh Reed": 1}, "desert_dunes": {"Clay": 2},
            "tundra_plain": {"Winter Root": 2}, "archipelago": {"Marsh Reed": 2, "Fiber": 1},
        }.get(kind, {"Fiber": 1})
        add_inventory_items(self.state.inventory, drops)
        self.advance_time(45)
        record["route_day"] = day
        self.autosave_with_message(f"Completed the marked route through {record.get('name', 'the landmark')} and gathered {format_drops(drops)}.")
        return True

    def open_wilderness_landscape_site(self) -> None:
        record = self.wilderness_landscape_record()
        choice = self.vertical_panel_select(
            str(record.get("name", "Major Landmark")),
            [
                self._wilderness_menu_item("route", "Explore the marked landmark route", "Daily traversal with terrain materials."),
                self._wilderness_menu_item("special", "Complete landmark specialty work", "Weekly observation, or a restorative soak."),
                self._wilderness_menu_item("map", "Chart from the landmark station", "Reveal nearby wilderness coordinates."),
            ],
            50, 19, return_back=True,
        )
        if not choice: return
        if choice.value == "route": self.explore_wilderness_landscape_route()
        elif choice.value == "special": self.interact_with_wilderness_landscape()
        elif choice.value == "map":
            added = self.map_nearby_wilderness_chunks(1)
            self.advance_time(20)
            self.autosave_with_message(f"Charted {added} nearby area(s) from the landmark station.")

    def update_ranger_camp_map(self, x: int, y: int) -> bool:
        record = self.wilderness_poi_record(x, y, "camp")
        week = self.stronghold_cache_week_key()
        if record.get("map_week") == week:
            self.set_message("The ranger camp route map is already current this week.")
            return False
        added = self.map_nearby_wilderness_chunks(2)
        self.advance_time(20)
        record["map_week"] = week
        self.autosave_with_message(f"Updated the ranger route map and charted {added} nearby area(s).")
        return True

    def maintain_wilderness_shelter(self, x: int, y: int) -> bool:
        record = self.wilderness_poi_record(x, y, "shelter")
        week = self.stronghold_cache_week_key()
        if record.get("maintenance_week") == week:
            self.set_message("This shelter has already been maintained this week.")
            return False
        materials = {"Wood": 2, "Fiber": 1}
        missing = {item: qty - int(self.state.inventory.get(item, 0)) for item, qty in materials.items() if int(self.state.inventory.get(item, 0)) < qty}
        if missing:
            self.set_message(f"Shelter maintenance needs {format_drops(missing)}.")
            return False
        for item, qty in materials.items(): self.state.inventory[item] -= qty
        record["maintenance_week"], record["maintained"] = week, True
        self.advance_time(35)
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 2, "maintained public trail shelter")
        self.autosave_with_message("Repaired the bunks, roof, and public supply shelf at the trail shelter.")
        return True

    def stamp_wilderness_island_compound(
        self, grid: List[List[str]], position: Tuple[int, int], type_id: str, symbol: str
    ) -> None:
        """Give island restoration sites a visible purpose-specific compound."""
        if not grid or position == (-1, -1): return
        cx = max(8, min(len(grid[0]) - 9, int(position[0])))
        cy = max(6, min(len(grid) - 7, int(position[1])))
        self._landmark_clear(grid, cx, cy, 7, 5, "[")
        if type_id == "lighthouse":
            for y in range(cy - 3, cy + 3):
                for x in range(cx - 3, cx + 4):
                    if abs(x - cx) == 3 or y in {cy - 3, cy + 2}: self._landmark_set(grid, x, y, "#")
            for y in range(cy + 3, min(len(grid) - 1, cy + 7)): self._landmark_set(grid, cx, y, "=")
        elif type_id == "sea_fort":
            for x in range(cx - 6, cx + 7):
                self._landmark_set(grid, x, cy - 4, "#")
                self._landmark_set(grid, x, cy + 4, "#")
            for y in range(cy - 4, cy + 5):
                self._landmark_set(grid, cx - 6, y, "#")
                self._landmark_set(grid, cx + 6, y, "#")
            self._landmark_set(grid, cx, cy + 4, ".")
        elif type_id == "bird_sanctuary":
            for x in range(cx - 6, cx + 7, 2):
                self._landmark_set(grid, x, cy - 3, "#")
                self._landmark_set(grid, x, cy + 3, "#")
            for dx, dy in ((-4, -1), (-2, 2), (3, -2), (5, 1)): self._landmark_set(grid, cx + dx, cy + dy, "e")
        elif type_id == "hidden_cove":
            for x in range(cx - 5, cx + 1):
                self._landmark_set(grid, x, cy - 3, "#")
                self._landmark_set(grid, x, cy + 1, "#")
            for y in range(cy - 3, cy + 2):
                self._landmark_set(grid, cx - 5, y, "#")
            self._landmark_set(grid, cx - 2, cy + 1, ".")
            for x in range(cx - 5, cx + 6): self._landmark_set(grid, x, cy + 2, "=")
            self._landmark_set(grid, cx - 5, cy, "Q")
            self._landmark_set(grid, cx + 5, cy, "k")
        else:
            for x in range(cx - 5, cx + 6):
                self._landmark_set(grid, x, cy - 3, "#")
                self._landmark_set(grid, x, cy + 3, "#")
            for y in range(cy - 3, cy + 4): self._landmark_set(grid, cx - 5, y, "#")
            self._landmark_set(grid, cx - 5, cy, ".")
            self._landmark_set(grid, cx + 3, cy, "K")
        self._landmark_set(grid, cx, cy, str(symbol)[:1], preserve_water=False, overwrite_route=True)

    def upgrade_wilderness_landmark_sites(
        self, grid: List[List[str]], chunk_x: int, chunk_y: int
    ) -> None:
        """Expand legacy one-character landmarks when an old saved chunk is loaded."""
        if not grid:
            return
        cx, cy = int(chunk_x), int(chunk_y)
        if (
            self.procedural_town_plan(cx, cy)
            or self.wilderness_chunk_has_stronghold(cx, cy)
            or self.owned_wilderness_claim(cx, cy)
        ):
            return
        rng = random.Random(self.wilderness_chunk_seed(cx, cy) + 119301)
        anchors = {
            symbol: [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == symbol]
            for symbol in ("R", "P", "K", "Q", "?", "E", "j")
        }
        stamped: List[Tuple[int, int]] = []

        def distant(x: int, y: int, radius: int = 10) -> bool:
            return all(abs(x - px) + abs(y - py) > radius for px, py in stamped)

        for symbol, kind in (("P", "stone_ruin"), ("R", "ranger_camp"), ("K", "overlook"), ("Q", "trail_shelter")):
            for x, y in anchors[symbol]:
                if distant(x, y):
                    self.stamp_wilderness_landmark_site(grid, x, y, kind, rng)
                    stamped.append((x, y))
        for x, y in anchors["?"]:
            if not distant(x, y):
                continue
            nearby = {
                grid[yy][xx]
                for yy in range(max(0, y - 6), min(len(grid), y + 7))
                for xx in range(max(0, x - 9), min(len(grid[0]), x + 10))
            }
            kind = "old_quarry" if "M" in nearby else ("fungal_garden" if "u" in nearby else ("spring_garden" if "Y" in nearby else "waystone"))
            self.stamp_wilderness_landmark_site(grid, x, y, kind, rng)
            stamped.append((x, y))
        for x, y in anchors["E"]:
            ground = self.wilderness_world_biome_tile(*self.wilderness_world_coords(cx, cy, x, y))
            self.stamp_wilderness_field_station(grid, x, y, ground)
        for marker_x, marker_y in anchors["j"][:1]:
            kind = str(self.wilderness_major_landscape_profile(cx, cy).get("type_id", "moorland"))
            landscape_x = marker_x - (11 if kind == "large_lake" else (7 if kind == "hot_springs" else 0))
            self.stamp_wilderness_landscape_facilities(grid, landscape_x, marker_y, kind, (marker_x, marker_y))
        self.apply_wilderness_island_site_compound(grid, cx, cy)
