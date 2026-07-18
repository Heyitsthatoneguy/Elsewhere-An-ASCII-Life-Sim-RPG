"""Regional identity and meaningful fieldwork for the procedural wilderness."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_inventory import add_inventory_items, format_drops
from ascii_farmstead_visuals import actor_style


FIELD_SITE_SYMBOL = "E"
WILDERNESS_OUTPOST_SYMBOL = "A"
WILDERNESS_STRUCTURE_SYMBOL = "h"
WILDERNESS_LANDSCAPE_SYMBOL = "j"
WILDERNESS_DOCK_SYMBOL = "k"
WILDERNESS_FISHING_SETTLEMENT_SYMBOL = "q"
WILDERNESS_REFUGE_SYMBOL = "v"
WILDERNESS_STAFFED_SITE_SYMBOL = "g"
WILDERNESS_EXCURSION_SYMBOL = "i"

MARITIME_ENCOUNTER_TYPES = (
    {"id": "shipwreck", "name": "Fresh Shipwreck", "symbol": "&", "description": "Broken timbers and a sealed supply chest roll in the swell."},
    {"id": "fishing_boat", "name": "Working Fishing Boat", "symbol": "f", "description": "A local crew sorts its catch and waves your skiff alongside."},
    {"id": "merchant_vessel", "name": "Coastal Merchant", "symbol": "$", "description": "A shallow-draft trader pauses between island ports."},
    {"id": "stranded_traveler", "name": "Stranded Traveler", "symbol": "!", "description": "A damaged dinghy drifts without a working oar."},
    {"id": "whale_pod", "name": "Passing Whale Pod", "symbol": "W", "description": "Dark backs and pale spray move steadily through the channel."},
    {"id": "survey_vessel", "name": "Marine Survey Vessel", "symbol": "s", "description": "Researchers are charting currents and island wildlife."},
)

ISLAND_SITE_TYPES = (
    {"id": "lighthouse", "name": "Dark Lighthouse", "symbol": "I", "materials": {"Stone": 10, "Wood": 8, "Fiber": 4}, "benefit": "A weekly navigation stipend and safer regional routes."},
    {"id": "sea_fort", "name": "Ruined Sea Fort", "symbol": "%", "materials": {"Stone": 12, "Wood": 6}, "benefit": "A weekly salvage store maintained by island wardens."},
    {"id": "bird_sanctuary", "name": "Abandoned Bird Sanctuary", "symbol": "b", "materials": {"Wood": 6, "Fiber": 8, "Stone": 4}, "benefit": "Weekly habitat materials and stronger coastal vitality."},
    {"id": "hidden_cove", "name": "Overgrown Smuggler Cove", "symbol": "c", "materials": {"Wood": 8, "Fiber": 6, "Stone": 4}, "benefit": "A legitimate fishing shelter with a weekly stored catch."},
    {"id": "weather_station", "name": "Silent Weather Station", "symbol": "w", "materials": {"Stone": 8, "Wood": 8, "Fiber": 4}, "benefit": "Weekly forecast research and coastal survey pay."},
)


class WildernessRevampMixin:
    """Adds deterministic regions, field sites, discoveries, and mastery."""

    def wilderness_random_combat_key(self, chunk_x: int, chunk_y: int) -> str:
        return f"{int(chunk_x)},{int(chunk_y)}"

    def wilderness_random_combat_eligible(self, chunk_x: int, chunk_y: int) -> bool:
        cx, cy = int(chunk_x), int(chunk_y)
        if abs(cx) + abs(cy) <= 1:
            return False
        if (
            self.wilderness_chunk_has_procedural_settlement(cx, cy)
            or self.wilderness_chunk_has_stronghold(cx, cy)
            or self.wilderness_chunk_has_dungeon_site(cx, cy)
            or self.wilderness_chunk_has_outpost(cx, cy)
            or self.wilderness_chunk_has_structure(cx, cy)
            or self.is_claimable_wilderness_chunk(cx, cy)
            or self.owned_wilderness_claim(cx, cy)
        ):
            return False
        grid = self.get_wilderness_chunk_map(cx, cy)
        if not grid:
            return False
        water = sum(1 for row in grid for tile in row if tile in {"~", "="})
        return water < max(1, len(grid) * len(grid[0]) * 2 // 3)

    def wilderness_random_combat_spawn_candidates(
        self, chunk_x: int, chunk_y: int, *, roads_only: bool = False,
    ) -> List[Tuple[int, int]]:
        grid = self.get_wilderness_chunk_map(chunk_x, chunk_y)
        if not grid:
            return []
        h, w = len(grid), len(grid[0])
        road_tiles = {":", ","}
        candidates: List[Tuple[int, int]] = []
        for y in range(7, h - 7):
            for x in range(7, w - 7):
                if roads_only and grid[y][x] not in road_tiles:
                    continue
                if not self.wilderness_stream_actor_passable(chunk_x, chunk_y, x, y):
                    continue
                if self.wilderness_stream_actor_occupied(chunk_x, chunk_y, x, y):
                    continue
                if (
                    self.on_wilderness()
                    and int(chunk_x) == int(self.state.wilderness_chunk_x)
                    and int(chunk_y) == int(self.state.wilderness_chunk_y)
                    and abs(x - int(self.state.player_x)) + abs(y - int(self.state.player_y)) < 9
                ):
                    continue
                candidates.append((x, y))
        return candidates

    def generate_wilderness_random_combat_encounter(
        self, chunk_x: int, chunk_y: int,
    ) -> Dict[str, object]:
        cx, cy = int(chunk_x), int(chunk_y)
        week = self.stronghold_cache_week_key()
        key = self.wilderness_random_combat_key(cx, cy)
        seed_text = f"{int(self.state.wilderness_seed)}:{key}:{week}:field-combat"
        rng = random.Random(sum((index + 1) * ord(ch) for index, ch in enumerate(seed_text)))
        record: Dict[str, object] = {
            "id": f"encounter:{key}:{week}", "chunk_x": cx, "chunk_y": cy,
            "week": week, "present": False, "resolved": False, "enemies": [],
        }
        if not self.wilderness_random_combat_eligible(cx, cy) or rng.random() >= 0.10:
            return record

        grid = self.get_wilderness_chunk_map(cx, cy)
        roads = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile in {":", ","}]
        region = self.wilderness_region_profile(cx, cy)
        climate = str(region.get("climate", region.get("ecosystem", ""))).lower()
        choices = ["predator_pack", "scavenger_camp", "monster_nest"]
        if roads:
            choices.extend(["roadblock", "caravan_raid"])
        if any(word in climate for word in ("coast", "marsh", "wet", "flood")):
            choices.append("marsh_stalkers")
        if any(word in climate for word in ("desert", "arid", "dune")):
            choices.append("desert_raiders")
        kind = rng.choice(choices)
        definitions = {
            "roadblock": ("Bandit Roadblock", ["Bandit", "Bandit", "Shield Guard"], "Travelers are being stopped and robbed along this route."),
            "caravan_raid": ("Caravan Under Attack", ["Bandit", "Wolf", "Bandit", "Shield Guard"], "Raiders have scattered cargo across a traveled road."),
            "predator_pack": ("Hunting Pack", ["Wolf", "Wolf", "Razor Hare", "Thornback"], "An unusually aggressive pack is stalking the surrounding trails."),
            "scavenger_camp": ("Hostile Scavenger Camp", ["Bandit", "Ruin Bat", "Moss Haunt"], "Armed scavengers have occupied a temporary camp around old debris."),
            "monster_nest": ("Wilderness Nest", ["Sporeling", "Thornback", "Ruin Bat", "Moss Haunt"], "A cluster of hostile creatures is defending a fresh nest."),
            "marsh_stalkers": ("Marsh Stalkers", ["Marsh Toad", "Sporeling", "Moss Haunt"], "Predators have gathered around a wet crossing."),
            "desert_raiders": ("Dustroad Raiders", ["Bandit", "Ember Imp", "Shield Guard"], "Raiders are using the exposed route as an ambush point."),
        }
        name, pool, description = definitions[kind]
        candidates = self.wilderness_random_combat_spawn_candidates(
            cx, cy, roads_only=kind in {"roadblock", "caravan_raid", "desert_raiders"},
        )
        if len(candidates) < 4:
            candidates = self.wilderness_random_combat_spawn_candidates(cx, cy)
        if not candidates:
            return record
        anchor = rng.choice(candidates)
        candidates.sort(key=lambda point: abs(point[0] - anchor[0]) + abs(point[1] - anchor[1]))
        count = min(4, 2 + (1 if abs(cx) + abs(cy) >= 6 else 0) + (1 if rng.random() < 0.22 else 0))
        enemies: List[Dict[str, object]] = []
        used: List[Tuple[int, int]] = []
        for x, y in candidates:
            if len(enemies) >= count:
                break
            if any(abs(x - ux) + abs(y - uy) < 3 for ux, uy in used):
                continue
            species = rng.choice(pool)
            boss = len(enemies) == count - 1 and count >= 4 and rng.random() < 0.35
            if boss:
                species = f"Elite {species}"
            enemies.append({
                "id": f"{record['id']}:{len(enemies)}:{species}",
                "encounter_id": str(record["id"]), "field_combat_kind": "encounter",
                "species": species, "chunk_x": cx, "chunk_y": cy,
                "floor": max(3, 4 + (abs(cx) + abs(cy)) * 2),
                "x": int(x), "y": int(y), "alert": False,
                "defeated": False, "boss": boss,
            })
            used.append((x, y))
        if len(enemies) < 2:
            return record
        visual_specs = {
            "roadblock": [("|", "Road Barricade", True), ("&", "Stolen Crate", True), ("|", "Road Barricade", True)],
            "caravan_raid": [("C", "Overturned Cart", True), ("&", "Scattered Cargo", True), ("&", "Scattered Cargo", True)],
            "predator_pack": [("n", "Predator Den", True), ("%", "Gnawed Remains", False)],
            "scavenger_camp": [("^", "Scavenger Campfire", False), ("&", "Salvage Crate", True), ("t", "Bedroll", False)],
            "monster_nest": [("n", "Monster Nest", True), ("%", "Shed Carapace", False), ("%", "Old Remains", False)],
            "marsh_stalkers": [("n", "Reed Nest", True), ('"', "Reed Blind", True)],
            "desert_raiders": [("^", "Raiders' Fire", False), ("|", "Dustroad Barricade", True), ("&", "Water Crate", True)],
        }
        enemy_positions = {(int(enemy["x"]), int(enemy["y"])) for enemy in enemies}
        visual_candidates = sorted(
            self.wilderness_random_combat_spawn_candidates(cx, cy),
            key=lambda point: abs(point[0] - anchor[0]) + abs(point[1] - anchor[1]),
        )
        visuals: List[Dict[str, object]] = []
        for symbol, visual_name, blocking in visual_specs.get(kind, []):
            point = next((
                candidate for candidate in visual_candidates
                if candidate not in enemy_positions
                and candidate not in {(int(v["x"]), int(v["y"])) for v in visuals}
                and abs(candidate[0] - anchor[0]) + abs(candidate[1] - anchor[1]) <= 6
            ), None)
            if point is None:
                break
            visuals.append({
                "x": int(point[0]), "y": int(point[1]), "symbol": symbol,
                "name": visual_name, "blocking": bool(blocking),
            })
        record.update({
            "present": True, "kind": kind, "name": name,
            "description": description, "enemies": enemies,
            "visuals": visuals,
            "anchor_x": int(anchor[0]), "anchor_y": int(anchor[1]),
            "reward_money": 30 + min(90, (abs(cx) + abs(cy)) * 8),
        })
        return record

    def wilderness_random_combat_record(
        self, chunk_x: int, chunk_y: int, *, create: bool = True,
    ) -> Dict[str, object]:
        records = getattr(self.state, "wilderness_combat_encounters", None)
        if not isinstance(records, dict):
            records = {}
            self.state.wilderness_combat_encounters = records
        key = self.wilderness_random_combat_key(chunk_x, chunk_y)
        record = records.get(key)
        week = self.stronghold_cache_week_key()
        if create and (not isinstance(record, dict) or str(record.get("week", "")) != week):
            record = self.generate_wilderness_random_combat_encounter(chunk_x, chunk_y)
            records[key] = record
        return record if isinstance(record, dict) and str(record.get("week", "")) == week else {}

    def get_wilderness_random_combat_enemies(
        self, chunk_x: Optional[int] = None, chunk_y: Optional[int] = None, create: bool = True,
    ) -> List[Dict[str, object]]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        record = self.wilderness_random_combat_record(cx, cy, create=create)
        if not record.get("present") or record.get("resolved"):
            return []
        enemies = record.get("enemies", [])
        return [enemy for enemy in enemies if isinstance(enemy, dict) and not bool(enemy.get("defeated", False))]

    def wilderness_random_combat_enemy_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if not self.on_wilderness():
            return None
        return next((
            enemy for enemy in self.get_wilderness_random_combat_enemies(create=False)
            if (int(enemy.get("x", -1)), int(enemy.get("y", -1))) == (int(x), int(y))
        ), None)

    def wilderness_random_combat_visual_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if not self.on_wilderness():
            return None
        record = self.wilderness_random_combat_record(
            self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, create=False,
        )
        if not record.get("present") or record.get("resolved"):
            return None
        return next((
            visual for visual in record.get("visuals", [])
            if isinstance(visual, dict)
            and (int(visual.get("x", -1)), int(visual.get("y", -1))) == (int(x), int(y))
        ), None)

    def remove_wilderness_random_combat_enemy(self, enemy: Dict[str, object]) -> None:
        enemy["defeated"] = True
        enemy["alert"] = False

    def resolve_wilderness_random_combat_encounter_if_clear(
        self, enemy: Dict[str, object],
    ) -> List[str]:
        cx = int(enemy.get("chunk_x", self.state.wilderness_chunk_x))
        cy = int(enemy.get("chunk_y", self.state.wilderness_chunk_y))
        record = self.wilderness_random_combat_record(cx, cy, create=False)
        if not record or self.get_wilderness_random_combat_enemies(cx, cy, create=False):
            return []
        record["resolved"] = True
        money = max(0, int(record.get("reward_money", 0)))
        self.state.money += money
        self.add_wilderness_region_vitality(cx, cy, 2, str(record.get("name", "field encounter")))
        return [
            f"{record.get('name', 'The encounter')} is resolved: +{money}g and +2 regional vitality."
        ]

    def nearest_engaging_wilderness_random_combat_enemy(self) -> Optional[Dict[str, object]]:
        if not self.on_wilderness():
            return None
        px, py = int(self.state.player_x), int(self.state.player_y)
        nearby = [
            enemy for enemy in self.get_wilderness_random_combat_enemies(create=False)
            if max(abs(int(enemy.get("x", -99)) - px), abs(int(enemy.get("y", -99)) - py)) <= 1
        ]
        return min(
            nearby,
            key=lambda enemy: abs(int(enemy.get("x", 0)) - px) + abs(int(enemy.get("y", 0)) - py),
            default=None,
        )

    def check_wilderness_random_combat_engagement(self, reason: str = "nearby") -> bool:
        enemy = self.nearest_engaging_wilderness_random_combat_enemy()
        if not enemy:
            return False
        if self.begin_wilderness_field_combat(enemy, reason=reason):
            self.advance_dungeon_roguelike_turn("hostile engagement")
        return True

    WILDERNESS_STRUCTURE_TYPES = {
        "abandoned_cabin": {"name": "Abandoned Cabin", "materials": {"Wood": 8, "Stone": 3}, "role": "Trapper", "benefit": "A safe bunk and weekly trail supplies."},
        "watchtower": {"name": "Old Watchtower", "materials": {"Wood": 10, "Stone": 6}, "role": "Lookout", "benefit": "A staffed survey point that strengthens the region."},
        "wayside_shrine": {"name": "Wayside Shrine", "materials": {"Stone": 8, "Fiber": 4}, "role": "Pilgrim", "benefit": "A quiet place for recovery and regional stories."},
        "research_hut": {"name": "Derelict Research Hut", "materials": {"Wood": 8, "Stone": 4, "Fiber": 4}, "role": "Researcher", "benefit": "Weekly ecological samples and field observations."},
        "hunting_lodge": {"name": "Weathered Hunting Lodge", "materials": {"Wood": 12, "Stone": 5}, "role": "Hunter", "benefit": "A safe lodge with provisions and wildlife reports."},
        "roadside_inn": {"name": "Shuttered Roadside Inn", "materials": {"Wood": 14, "Stone": 6, "Fiber": 6}, "role": "Innkeeper", "benefit": "A staffed rest stop with meals and traveler news."},
        "desert_caravanserai": {"name": "Abandoned Desert Caravanserai", "materials": {"Stone": 12, "Clay": 10, "Fiber": 6}, "role": "Desert Host", "benefit": "Shade, water stores, and weekly crossing supplies."},
        "tundra_wayhouse": {"name": "Snowbound Tundra Wayhouse", "materials": {"Wood": 12, "Stone": 8, "Fiber": 10}, "role": "Winter Keeper", "benefit": "A heated refuge with weekly cold-weather provisions."},
        "coastal_ferry_house": {"name": "Abandoned Coastal Ferry House", "materials": {"Wood": 14, "Stone": 8, "Fiber": 8}, "role": "Ferry Keeper", "benefit": "A sheltered landing with weekly boat and fishing supplies."},
    }

    def connect_wilderness_site_to_regional_road(
        self,
        grid: List[List[str]],
        start: Tuple[int, int],
        road_targets: List[Tuple[int, int]],
    ) -> bool:
        """Carve a short walkable approach from a landmark to its existing road."""
        if not grid or not road_targets:
            return False
        h, w = len(grid), len(grid[0])
        start = (int(start[0]), int(start[1]))
        targets = {(int(x), int(y)) for x, y in road_targets if 0 <= int(x) < w and 0 <= int(y) < h}
        if not targets or not (0 <= start[0] < w and 0 <= start[1] < h):
            return False
        blocked = {
            "#", "S", "V", "X", "!", "E", WILDERNESS_OUTPOST_SYMBOL,
            WILDERNESS_STRUCTURE_SYMBOL, WILDERNESS_LANDSCAPE_SYMBOL,
            WILDERNESS_DOCK_SYMBOL, WILDERNESS_FISHING_SETTLEMENT_SYMBOL,
        }
        frontier = [start]
        parents = {start: None}
        found = start if start in targets else None
        cursor = 0
        while cursor < len(frontier) and found is None:
            x, y = frontier[cursor]
            cursor += 1
            for point in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                px, py = point
                if not (0 <= px < w and 0 <= py < h) or point in parents:
                    continue
                if grid[py][px] in blocked and point not in targets:
                    continue
                parents[point] = (x, y)
                if point in targets:
                    found = point
                    break
                frontier.append(point)
        if found is None:
            return False
        point = found
        path = []
        while point is not None:
            path.append(point)
            point = parents.get(point)
        for x, y in reversed(path):
            if (x, y) == start or (x, y) in targets:
                continue
            if grid[y][x] not in blocked:
                grid[y][x] = "=" if grid[y][x] == "~" else ":"
        return True

    @staticmethod
    def wilderness_door_delta(side: str) -> Tuple[int, int]:
        return {
            "north": (0, -1), "south": (0, 1),
            "west": (-1, 0), "east": (1, 0),
        }.get(str(side), (0, 1))

    def wilderness_door_side_toward_routes(
        self,
        center: Tuple[int, int],
        road_targets: List[Tuple[int, int]],
        fallback_value: float,
    ) -> str:
        cx, cy = center
        if road_targets:
            tx, ty = min(road_targets, key=lambda point: abs(point[0] - cx) + abs(point[1] - cy))
            dx, dy = tx - cx, ty - cy
            if abs(dx) > abs(dy):
                return "east" if dx > 0 else "west"
            if dy:
                return "south" if dy > 0 else "north"
        return ("north", "east", "south", "west")[int(float(fallback_value) * 4) % 4]

    def stamp_wilderness_building_exterior(
        self,
        grid: List[List[str]],
        center: Tuple[int, int],
        size: Tuple[int, int],
        side: str,
        door_symbol: str,
        ground: str,
    ) -> Tuple[int, int, int, int]:
        """Stamp a solid overhead building silhouette with one obvious doorway."""
        cx, cy = int(center[0]), int(center[1])
        width = max(7, int(size[0]) | 1)
        height = max(7, int(size[1]) | 1)
        half_w, half_h = width // 2, height // 2
        left, right = cx - half_w, cx + half_w
        top, bottom = cy - half_h, cy + half_h
        for y in range(max(1, top - 2), min(len(grid) - 1, bottom + 3)):
            for x in range(max(1, left - 2), min(len(grid[0]) - 1, right + 3)):
                if grid[y][x] not in {"S", "V", "X", "!", "=", "~"}:
                    grid[y][x] = ground
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if 1 <= y < len(grid) - 1 and 1 <= x < len(grid[0]) - 1:
                    grid[y][x] = "#"
        if side == "north":
            door_x, door_y = cx, top
        elif side == "west":
            door_x, door_y = left, cy
        elif side == "east":
            door_x, door_y = right, cy
        else:
            door_x, door_y = cx, bottom
        grid[door_y][door_x] = str(door_symbol)[:1]
        dx, dy = self.wilderness_door_delta(side)
        outside_x, outside_y = door_x + dx, door_y + dy
        for step in (1, 2, 3):
            px, py = door_x + dx * step, door_y + dy * step
            if 1 <= py < len(grid) - 1 and 1 <= px < len(grid[0]) - 1 and grid[py][px] not in {"~", "=", "S"}:
                grid[py][px] = ":"
        return door_x, door_y, outside_x, outside_y

    def wilderness_exterior_door_side(self, grid: List[List[str]], x: int, y: int) -> str:
        """Infer which wall contains an exterior marker, including legacy hollow buildings."""
        x, y = int(x), int(y)
        if not grid or not (1 <= y < len(grid) - 1 and 1 <= x < len(grid[0]) - 1):
            return "south"
        horizontal = grid[y][x - 1] == "#" and grid[y][x + 1] == "#"
        vertical = grid[y - 1][x] == "#" and grid[y + 1][x] == "#"
        if horizontal:
            above = sum(grid[yy][xx] == "#" for yy in range(max(1, y - 8), y) for xx in range(max(1, x - 6), min(len(grid[0]) - 1, x + 7)))
            below = sum(grid[yy][xx] == "#" for yy in range(y + 1, min(len(grid) - 1, y + 9)) for xx in range(max(1, x - 6), min(len(grid[0]) - 1, x + 7)))
            return "south" if above >= below else "north"
        if vertical:
            left = sum(grid[yy][xx] == "#" for yy in range(max(1, y - 6), min(len(grid) - 1, y + 7)) for xx in range(max(1, x - 8), x))
            right = sum(grid[yy][xx] == "#" for yy in range(max(1, y - 6), min(len(grid) - 1, y + 7)) for xx in range(x + 1, min(len(grid[0]) - 1, x + 9)))
            return "east" if left >= right else "west"
        return "south"

    @staticmethod
    def orient_south_door_interior(grid: List[List[str]], side: str) -> List[List[str]]:
        """Rotate a south-door interior so its doorway matches the exterior wall."""
        result = [list(row) for row in grid]
        side = str(side or "south").lower()
        if side == "north":
            return [row[:] for row in reversed(result)]
        if side == "west":
            return [list(row) for row in zip(*result[::-1])]
        if side == "east":
            return [list(row) for row in zip(*result)][::-1]
        return result

    def wilderness_interior_entry_landing(self, grid: List[List[str]], side: str) -> Tuple[int, int]:
        doors = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == "D"]
        if not doors:
            return len(grid[0]) // 2, max(1, len(grid) - 2)
        door_x, door_y = doors[0]
        dx, dy = self.wilderness_door_delta(side)
        inward_x, inward_y = door_x - dx, door_y - dy
        return inward_x, inward_y

    def upgrade_wilderness_building_exteriors(
        self, grid: List[List[str]], chunk_x: int, chunk_y: int
    ) -> None:
        """Expand legacy outpost/structure doorway markers into solid buildings."""
        if not grid:
            return
        cx, cy = int(chunk_x), int(chunk_y)
        road_targets = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile in {":", "="}]
        targets = []
        if self.wilderness_chunk_has_structure(cx, cy):
            marker = next(((x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == WILDERNESS_STRUCTURE_SYMBOL), None)
            type_id = self.wilderness_structure_type(cx, cy)
            size = (17, 9) if type_id in {"hunting_lodge", "roadside_inn", "desert_caravanserai", "tundra_wayhouse", "coastal_ferry_house"} else ((9, 9) if type_id == "watchtower" else (13, 7))
            if marker:
                targets.append((marker, size, WILDERNESS_STRUCTURE_SYMBOL, 88905))
        if self.wilderness_chunk_has_outpost(cx, cy):
            marker = next(((x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == WILDERNESS_OUTPOST_SYMBOL), None)
            if marker:
                targets.append((marker, (15, 9), WILDERNESS_OUTPOST_SYMBOL, 88513))
        for (door_x, door_y), size, symbol, _salt in targets:
            side = self.wilderness_exterior_door_side(grid, door_x, door_y)
            half_w, half_h = size[0] // 2, size[1] // 2
            center_x = door_x + (half_w if side == "west" else (-half_w if side == "east" else 0))
            center_y = door_y + (half_h if side == "north" else (-half_h if side == "south" else 0))
            center_x = max(half_w + 2, min(len(grid[0]) - half_w - 3, center_x))
            center_y = max(half_h + 2, min(len(grid) - half_h - 3, center_y))
            footprint_walls = sum(
                grid[y][x] == "#"
                for y in range(center_y - half_h, center_y + half_h + 1)
                for x in range(center_x - half_w, center_x + half_w + 1)
            )
            if footprint_walls >= size[0] * size[1] - 2:
                continue
            ground = self.wilderness_world_biome_tile(*self.wilderness_world_coords(cx, cy, center_x, center_y))
            _new_x, _new_y, outside_x, outside_y = self.stamp_wilderness_building_exterior(
                grid, (center_x, center_y), size, side, symbol, ground
            )
            self.connect_wilderness_site_to_regional_road(grid, (outside_x, outside_y), road_targets)

    def wilderness_structure_type(self, chunk_x: int, chunk_y: int) -> str:
        biome = str(self.wilderness_region_profile(chunk_x, chunk_y).get("biome", ";"))
        if biome == "`": return "desert_caravanserai"
        if biome == '"': return "tundra_wayhouse"
        if biome == "[": return "coastal_ferry_house"
        favored = {";": "roadside_inn", "%": "hunting_lodge", "l": "research_hut", "r": "wayside_shrine", "x": "watchtower"}.get(biome, "abandoned_cabin")
        choices = [favored, "abandoned_cabin", "watchtower", "wayside_shrine", "research_hut", "hunting_lodge", "roadside_inn"]
        return choices[int(self.wilderness_hash01(chunk_x, chunk_y, 88901) * len(choices)) % len(choices)]

    def wilderness_region_structure_chunk(self, chunk_x: int, chunk_y: int) -> Tuple[int, int]:
        rx, ry = self.wilderness_region_coords(chunk_x, chunk_y)
        candidates = self.wilderness_region_chunks(chunk_x, chunk_y)
        outpost = self.wilderness_region_outpost_chunk(chunk_x, chunk_y)
        safe_candidates = [point for point in candidates if point != outpost and not self.wilderness_chunk_has_stronghold(*point) and not self.procedural_town_plan(*point) and not self.is_claimable_wilderness_chunk(*point)]
        candidates = safe_candidates or [point for point in candidates if point != outpost]
        rng = random.Random(self.wilderness_chunk_seed(rx, ry) + 88902)
        return candidates[rng.randrange(len(candidates))]

    def wilderness_chunk_has_structure(self, chunk_x: int, chunk_y: int) -> bool:
        return (int(chunk_x), int(chunk_y)) == self.wilderness_region_structure_chunk(chunk_x, chunk_y)

    def wilderness_structure_marker_at(
        self,
        x: int,
        y: int,
        grid: Optional[List[List[str]]] = None,
    ) -> bool:
        grid = self.active_map() if grid is None else grid
        if not grid or not (0 <= int(y) < len(grid) and 0 <= int(x) < len(grid[0])):
            return False
        if grid[int(y)][int(x)] != WILDERNESS_STRUCTURE_SYMBOL:
            return False
        wall_neighbors = 0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = int(x) + dx, int(y) + dy
            if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] == "#":
                wall_neighbors += 1
        return wall_neighbors > 0

    def wilderness_structure_marker_positions(
        self,
        grid: List[List[str]],
    ) -> List[Tuple[int, int]]:
        return [
            (x, y)
            for y, row in enumerate(grid)
            for x, _tile in enumerate(row)
            if self.wilderness_structure_marker_at(x, y, grid)
        ]

    def wilderness_structure_record(self, chunk_x: int = None, chunk_y: int = None) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        self.ensure_wilderness_poi_state()
        key = f"structure:{cx},{cy}"
        profile_id = self.wilderness_structure_type(cx, cy)
        profile = self.WILDERNESS_STRUCTURE_TYPES[profile_id]
        record = self.state.wilderness_poi_state.setdefault(key, {})
        record.setdefault("kind", "wilderness_structure")
        record.setdefault("type_id", profile_id)
        record.setdefault("name", profile["name"])
        record.setdefault("repaired", False)
        return record

    def place_wilderness_structure(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        if not self.wilderness_chunk_has_structure(chunk_x, chunk_y) or self.procedural_town_plan(chunk_x, chunk_y) or self.wilderness_chunk_has_stronghold(chunk_x, chunk_y):
            return
        if self.wilderness_structure_marker_positions(grid):
            return
        h, w = len(grid), len(grid[0]) if grid else 0
        road_targets = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile in {":", "="}]
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 88903)
        type_id = self.wilderness_structure_type(chunk_x, chunk_y)
        if type_id in {"hunting_lodge", "roadside_inn", "desert_caravanserai", "tundra_wayhouse", "coastal_ferry_house"}:
            building_size = (17, 9)
        elif type_id == "watchtower":
            building_size = (9, 9)
        else:
            building_size = (13, 7)
        half_w, half_h = building_size[0] // 2, building_size[1] // 2
        blocked = {"~", "=", ":", "S", "V", "X", "!", "A", "E", "h", "j", "k", "q"}
        candidates = [
            (x, y)
            for y in range(half_h + 4, h - half_h - 4)
            for x in range(half_w + 4, w - half_w - 4)
            if all(
                grid[yy][xx] not in blocked
                for yy in range(y - half_h - 2, y + half_h + 3)
                for xx in range(x - half_w - 2, x + half_w + 3)
            )
        ]
        if not candidates:
            return
        cx, cy = rng.choice(candidates)
        ground = self.wilderness_world_biome_tile(*self.wilderness_world_coords(chunk_x, chunk_y, cx, cy))
        side = self.wilderness_door_side_toward_routes(
            (cx, cy), road_targets, self.wilderness_hash01(chunk_x, chunk_y, 88904)
        )
        _door_x, _door_y, outside_x, outside_y = self.stamp_wilderness_building_exterior(
            grid, (cx, cy), building_size, side, WILDERNESS_STRUCTURE_SYMBOL, ground
        )
        self.connect_wilderness_site_to_regional_road(grid, (outside_x, outside_y), road_targets)

    def wilderness_structure_map(self) -> List[List[str]]:
        key = str(self.state.current_wilderness_structure_key or self.wilderness_chunk_key())
        try:
            cx, cy = [int(part) for part in key.split(",", 1)]
        except (TypeError, ValueError):
            cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        record = self.wilderness_structure_record(cx, cy)
        type_id = str(record.get("type_id", "abandoned_cabin"))
        repaired = bool(record.get("repaired", False))
        width, height = (35, 19) if type_id in {"hunting_lodge", "roadside_inn", "desert_caravanserai", "tundra_wayhouse", "coastal_ferry_house"} else (29, 15)
        grid = [[" " for _ in range(width)] for _ in range(height)]
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                grid[y][x] = "."
        for x in range(width):
            grid[0][x] = grid[-1][x] = "#"
        for y in range(height):
            grid[y][0] = grid[y][-1] = "#"
        grid[-1][width // 2] = "D"
        grid[3][4], grid[4][4], grid[4][5] = "b", "t", "c"
        grid[3][width - 5], grid[4][width - 5] = "f", "s"
        grid[3][width // 2] = "P"
        if type_id in {"watchtower", "research_hut"}:
            for x in range(8, width - 8): grid[7][x] = "-"
            grid[7][width // 2] = "|"
            grid[5][width // 2] = "d"
        elif type_id in {"hunting_lodge", "roadside_inn", "desert_caravanserai", "tundra_wayhouse", "coastal_ferry_house"}:
            for y in range(2, height - 4): grid[y][width // 2] = "-"
            grid[height // 2][width // 2] = "|"
            grid[6][7], grid[6][8], grid[7][7], grid[7][8] = "t", "c", "c", "t"
            if type_id == "roadside_inn": grid[5][width // 2 - 3] = "&"
            if type_id == "desert_caravanserai":
                grid[5][width // 2 - 3] = "&"
                grid[5][5] = grid[5][width - 6] = "P"
            if type_id == "tundra_wayhouse":
                grid[5][width // 2 - 3] = "f"
                grid[5][5] = grid[5][width - 6] = "b"
            if type_id == "coastal_ferry_house":
                grid[5][width // 2 - 3] = "&"
                grid[5][5], grid[5][width - 6] = "s", "P"
        elif type_id == "wayside_shrine":
            grid[5][width // 2] = "+"
            grid[6][width // 2 - 2] = grid[6][width // 2 + 2] = "c"
        grid[3][width // 2 - 2 if type_id in {"hunting_lodge", "roadside_inn", "desert_caravanserai", "tundra_wayhouse", "coastal_ferry_house"} else width // 2] = "P"
        if repaired:
            grid[5][width // 2 + 2] = "@"
        return self.orient_south_door_interior(
            grid, getattr(self.state, "wilderness_structure_door_side", "south")
        )

    def enter_wilderness_structure(self, x: int, y: int):
        side = self.wilderness_exterior_door_side(self.active_map(), x, y)
        dx, dy = self.wilderness_door_delta(side)
        self.state.current_wilderness_structure_key = self.wilderness_chunk_key()
        self.state.wilderness_structure_return_x = int(x) + dx
        self.state.wilderness_structure_return_y = int(y) + dy
        self.state.wilderness_structure_door_side = side
        self.state.location = "WildernessStructure"
        grid = self.wilderness_structure_map()
        self.state.player_x, self.state.player_y = self.wilderness_interior_entry_landing(grid, side)
        self.state.facing = {"north": "DOWN", "south": "UP", "west": "RIGHT", "east": "LEFT"}[side]
        self.set_message(f"Entered {self.wilderness_structure_record().get('name', 'the wilderness structure')}.")

    def exit_wilderness_structure(self):
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        return_x = int(self.state.wilderness_structure_return_x)
        return_y = int(self.state.wilderness_structure_return_y)
        self.state.player_x, self.state.player_y = self.nearest_active_passable_tile(return_x, return_y)
        side = str(getattr(self.state, "wilderness_structure_door_side", "south"))
        self.state.facing = {"north": "UP", "south": "DOWN", "west": "LEFT", "east": "RIGHT"}.get(side, "DOWN")
        self.set_message("Returned to the wilderness.")

    def repair_wilderness_structure(self, chunk_x: int = None, chunk_y: int = None) -> bool:
        record = self.wilderness_structure_record(chunk_x, chunk_y)
        if record.get("repaired"):
            self.set_message("This structure is already restored and staffed.")
            return False
        profile = self.WILDERNESS_STRUCTURE_TYPES[str(record["type_id"])]
        missing = {item: qty - int(self.state.inventory.get(item, 0)) for item, qty in profile["materials"].items() if int(self.state.inventory.get(item, 0)) < qty}
        if missing:
            self.set_message(f"Restoration still needs {format_drops(missing)}.")
            return False
        for item, qty in profile["materials"].items():
            self.state.inventory[item] -= qty
        record["repaired"] = True
        record["repaired_year"], record["repaired_season"] = int(self.state.year), str(self.state.season)
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 8, f"restored {record['name']}")
        self.advance_time(120)
        self.autosave_with_message(f"Restored {record['name']}. It is now staffed and provides regional services.")
        return True

    def wilderness_structure_lines(self, chunk_x: int = None, chunk_y: int = None) -> List[str]:
        record = self.wilderness_structure_record(chunk_x, chunk_y)
        profile = self.WILDERNESS_STRUCTURE_TYPES[str(record["type_id"])]
        status = "Restored and staffed" if record.get("repaired") else "Abandoned; restoration available"
        materials = format_drops(profile["materials"])
        rows = [str(record["name"]).upper(), "", f"Status: {status}", f"Regional role: {profile['role']}", str(profile["benefit"]), "", f"Restoration: {materials}"]
        if str(record.get("type_id")) in {"desert_caravanserai", "tundra_wayhouse"}:
            rows.extend(["", f"Route preparation: {'active this week' if self.wilderness_climate_prepared(chunk_x, chunk_y) else 'available through weekly service'}", "Preparation reduces frontier fieldwork and expedition exertion."])
        return rows

    def wilderness_climate_prepared(self, chunk_x: int = None, chunk_y: int = None) -> bool:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        region = self.wilderness_region_record(cx, cy)
        return region.get("climate_prepared_week") == self.stronghold_cache_week_key()

    def set_wilderness_climate_prepared(self, source: str) -> bool:
        region = self.wilderness_region_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        week = self.stronghold_cache_week_key()
        if region.get("climate_prepared_week") == week:
            self.set_message("Your frontier route preparation is already active this week.")
            return False
        region["climate_prepared_week"] = week
        region["climate_prepared_source"] = str(source)
        return True

    def show_wilderness_structure_exterior(self, x: int, y: int):
        record = self.wilderness_structure_record()
        items = [self._wilderness_menu_item("enter", f"Enter {record['name']}", "Explore the interior and use any available fixtures."), self._wilderness_menu_item("inspect", "Inspect structure", "Review its purpose and restoration requirements.")]
        if not record.get("repaired"):
            items.append(self._wilderness_menu_item("repair", "Restore structure", "Contribute materials and two hours of labor."))
        choice = self.vertical_panel_select(str(record["name"]), items, 52, 22, return_back=True)
        if not choice:
            return
        if choice.value == "enter": self.enter_wilderness_structure(x, y)
        elif choice.value == "inspect": self.vertical_panel_view(str(record["name"]), self.wilderness_structure_lines(), 52, 22)
        elif choice.value == "repair": self.repair_wilderness_structure()

    def rest_at_wilderness_structure(self) -> bool:
        record = self.wilderness_structure_record()
        day = self.errand_day_key()
        if record.get("last_rest_day") == day:
            self.set_message("You already rested here today.")
            return False
        before = int(self.state.stamina)
        self.restore_stamina(35 if record.get("repaired") else 16)
        self.advance_time(35 if record.get("repaired") else 20)
        record["last_rest_day"] = day
        self.autosave_with_message(f"Rested at {record['name']}: +{int(self.state.stamina) - before} stamina.")
        return True

    def claim_wilderness_structure_service(self) -> bool:
        record = self.wilderness_structure_record()
        if not record.get("repaired"):
            self.set_message("Restore this structure before its regional service becomes available.")
            return False
        week = self.stronghold_cache_week_key()
        if record.get("service_week") == week:
            self.set_message("You already used this structure's regional service this week.")
            return False
        drops = {"abandoned_cabin": {"Wood": 2, "Field Snack": 1}, "watchtower": {"Field Snack": 1, "Fiber": 2}, "wayside_shrine": {"Wild Herbs": 2}, "research_hut": {"Mushrooms": 2, "Strange Spores": 1}, "hunting_lodge": {"Field Snack": 2, "Fiber": 1}, "roadside_inn": {"Field Snack": 2}, "desert_caravanserai": {"Field Snack": 2, "Clay": 2, "Wild Herbs": 1}, "tundra_wayhouse": {"Field Snack": 2, "Fiber": 2, "Winter Root": 1}, "coastal_ferry_house": {"Field Snack": 1, "Wood": 2, "Fiber": 2, "Marsh Reed": 1}}.get(str(record["type_id"]), {"Field Snack": 1})
        add_inventory_items(self.state.inventory, drops)
        record["service_week"] = week
        prepared = str(record.get("type_id")) in {"desert_caravanserai", "tundra_wayhouse"} and self.set_wilderness_climate_prepared(str(record["name"]))
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 2, f"visited {record['name']}")
        suffix = " Frontier route preparation is active for the week." if prepared else ""
        self.autosave_with_message(f"Received weekly support from {record['name']}: {format_drops(drops)}.{suffix}")
        return True

    def use_wilderness_structure_action(self, x: int, y: int):
        tile = self.active_map()[y][x]
        record = self.wilderness_structure_record()
        if tile == "D": self.exit_wilderness_structure()
        elif tile == "b": self.rest_at_wilderness_structure()
        elif tile in {"s", "&"}: self.claim_wilderness_structure_service()
        elif tile == "P": self.vertical_panel_view(str(record["name"]), self.wilderness_structure_lines(), 52, 22)
        elif tile == "@":
            role = self.WILDERNESS_STRUCTURE_TYPES[str(record["type_id"])]["role"]
            self.set_message(f"The {role.lower()} shares current trail conditions and thanks you for restoring this place.")
        else: self.set_message(f"You examine the interior of {record['name']}.")

    def wilderness_region_coords(self, chunk_x: int, chunk_y: int) -> Tuple[int, int]:
        """Return the anchor of the nearest organic region.

        Anchors are jittered on a coarse world lattice. Nearest-anchor ownership
        produces contiguous, irregular regions with variable chunk counts while
        remaining deterministic and cheap to query anywhere in the world.
        """
        cx, cy = int(chunk_x), int(chunk_y)
        cell_size = 5
        gx, gy = cx // cell_size, cy // cell_size
        best = None
        for sy in range(gy - 2, gy + 3):
            for sx in range(gx - 2, gx + 3):
                ax = sx * cell_size + int(self.wilderness_hash01(sx, sy, 87901) * cell_size)
                ay = sy * cell_size + int(self.wilderness_hash01(sx, sy, 87902) * cell_size)
                distance = (cx - ax) ** 2 + (cy - ay) ** 2
                candidate = (distance, ax, ay, sx, sy)
                if best is None or candidate < best:
                    best = candidate
        return int(best[1]), int(best[2])

    def wilderness_region_chunks(self, chunk_x: int, chunk_y: int) -> List[Tuple[int, int]]:
        """Enumerate all persistent chunks belonging to an organic region."""
        anchor = self.wilderness_region_coords(chunk_x, chunk_y)
        cache_key = (int(self.state.wilderness_seed), anchor)
        cache = getattr(self, "_wilderness_region_chunks_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_region_chunks_cache = cache
        if cache_key not in cache:
            ax, ay = anchor
            members = [
                (cx, cy)
                for cy in range(ay - 8, ay + 9)
                for cx in range(ax - 8, ax + 9)
                if self.wilderness_region_coords(cx, cy) == anchor
            ]
            members.sort(key=lambda point: ((point[0] - ax) ** 2 + (point[1] - ay) ** 2, point[1], point[0]))
            cache[cache_key] = members or [anchor]
        return list(cache[cache_key])

    def wilderness_region_profile(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        rx, ry = self.wilderness_region_coords(chunk_x, chunk_y)
        cache_key = (int(self.state.wilderness_seed), rx, ry)
        cache = getattr(self, "_wilderness_region_profile_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_region_profile_cache = cache
        if cache_key in cache:
            return dict(cache[cache_key])
        members = self.wilderness_region_chunks(chunk_x, chunk_y)
        center_x = min(members, key=lambda point: (point[0] - rx) ** 2 + (point[1] - ry) ** 2)[0]
        center_y = min(members, key=lambda point: (point[0] - rx) ** 2 + (point[1] - ry) ** 2)[1]
        wx, wy = center_x * 86 + 43, center_y * 38 + 19
        biome = self.wilderness_world_biome_tile(wx, wy)
        names = {
            ";": (["Amber", "Lark", "Sunward", "Clover"], ["Prairie", "Downs", "Reach", "Fields"]),
            "%": (["Elder", "Whisper", "Foxglove", "Greenveil"], ["Wood", "Forest", "Thicket", "Wilds"]),
            "l": (["Mooncap", "Mosslight", "Dew", "Spore"], ["Hollow", "Glen", "Basin", "Vale"]),
            "r": (["Reed", "Heron", "Mist", "Willow"], ["Marsh", "Fen", "Wetlands", "Delta"]),
            "x": (["Flint", "High", "Storm", "Iron"], ["Ridge", "Crags", "Heights", "Escarpment"]),
            "`": (["Red", "Sun", "Cinder", "Dust"], ["Desert", "Badlands", "Waste", "Basin"]),
            '"': (["Frost", "White", "Winter", "Aurora"], ["Tundra", "Snowfield", "Reach", "Highland"]),
            "[": (["Salt", "Gull", "Tide", "Storm"], ["Coast", "Archipelago", "Strand", "Isles"]),
        }
        seed = self.wilderness_chunk_seed(rx * 17 + 5, ry * 19 - 7)
        rng = random.Random(seed + 88001)
        first, second = names.get(biome, names[";"])
        trait_pool = {
            ";": ["open skies", "flowering grasslands", "old grazing trails", "migratory birds"],
            "%": ["ancient canopy", "hidden clearings", "fallen timber", "abundant wildlife"],
            "l": ["rare fungi", "mossy springs", "glowing spores", "sheltered hollows"],
            "r": ["rich waterways", "reed beds", "seasonal pools", "waterfowl habitat"],
            "x": ["mineral seams", "wind-cut ledges", "wide views", "old stone paths"],
            "`": ["shifting dunes", "dry washes", "sun-baked shelves", "rare desert bloom"],
            '"': ["wind-packed snow", "frozen heath", "migrating herds", "brief summer flowers"],
            "[": ["tidal islands", "salt marshes", "seabird colonies", "sheltered anchorages"],
        }.get(biome, ["wild country", "old trails", "seasonal forage", "quiet clearings"])
        traits = rng.sample(trait_pool, 2)
        profile = {
            "key": f"organic:{rx},{ry}", "rx": rx, "ry": ry,
            "center_x": center_x, "center_y": center_y, "size": len(members),
            "name": f"{rng.choice(first)} {rng.choice(second)}", "biome": biome, "traits": traits,
        }
        cache[cache_key] = profile
        return dict(profile)

    def wilderness_region_condition(self, chunk_x: int, chunk_y: int) -> str:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        season = str(self.state.season)
        choices = {
            "Spring": ["new growth", "high water", "nesting season", "muddy trails"],
            "Summer": ["long daylight", "heavy bloom", "dry trails", "active wildlife"],
            "Fall": ["seedfall", "migrating wildlife", "cool rains", "ripe forage"],
            "Winter": ["deep frost", "clear sightlines", "animal tracks", "sparse forage"],
        }.get(season, ["settled weather"])
        index = (int(profile["rx"]) * 7 + int(profile["ry"]) * 11 + int(self.state.month)) % len(choices)
        return choices[index]

    def wilderness_field_site_type(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        wx, wy = self.wilderness_world_coords(chunk_x, chunk_y, 43, 19)
        biome = self.wilderness_world_biome_tile(wx, wy)
        return {
            ";": {"name": "Pollinator Meadow", "work": "survey flowering plants and pollinators", "drops": {"Mixed Seeds": 2, "Wild Herbs": 1}},
            "%": {"name": "Old-Growth Plot", "work": "clear a study trail and record the oldest trees", "drops": {"Wood": 2, "Pine Nuts": 1}},
            "l": {"name": "Fungal Study Ring", "work": "catalog fungi without disturbing the ring", "drops": {"Mushrooms": 2, "Strange Spores": 1}},
            "r": {"name": "Watershed Station", "work": "sample the water and restore a reed bank", "drops": {"Marsh Reed": 2, "Clay": 1}},
            "x": {"name": "Geology Cairn", "work": "map the exposed strata and repair the route cairn", "drops": {"Stone": 2, "Coal": 1}},
            "`": {"name": "Desert Water Survey", "work": "chart dry washes and protect a seasonal spring", "drops": {"Clay": 2, "Wild Herbs": 1}},
            '"': {"name": "Tundra Migration Post", "work": "record cold-weather tracks and repair snow markers", "drops": {"Fiber": 2, "Winter Root": 1}},
            "[": {"name": "Coastal Survey Station", "work": "chart tides, nesting islands, and safe channels", "drops": {"Marsh Reed": 2, "Fiber": 1}},
        }.get(biome, {"name": "Naturalist Plot", "work": "record the local ecology", "drops": {"Wild Herbs": 1}})

    def wilderness_subhabitat_profile(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        wx, wy = self.wilderness_world_coords(chunk_x, chunk_y, 43, 19)
        biome = self.wilderness_world_biome_tile(wx, wy)
        options = {
            ";": [("Flower Downs", [";", ";", ";", "^"]), ("Heather Moor", [";", ";", "x", "^"]), ("Open Grazing Steppe", [";", ";", ".", "."])],
            "%": [("Pine Shadow", ["%", "%", "%", "l"]), ("Birchbreak Grove", ["%", "%", ";", "."]), ("Fernwood", ["%", "%", "l", "r"])],
            "l": [("Moss Basin", ["l", "l", "r", "%"]), ("Sporewood", ["l", "l", "%", "%"]), ("Sink Hollow", ["l", "l", "x", "r"])],
            "r": [("Reed Floodplain", ["r", "r", "r", ";"]), ("Oxbow Meadow", ["r", "r", ";", "."]), ("Willow Fen", ["r", "r", "%", "l"])],
            "x": [("Scree Valley", ["x", "x", "x", "."]), ("High Moor", ["x", "x", ";", "^"]), ("Springcut Ridge", ["x", "x", "r", "."])],
            "`": [("Dune Sea", ["`", "`", "`", "."]), ("Red Badlands", ["`", "`", "x", "o"]), ("Dry Wash", ["`", "`", "r", "."])],
            '"': [("Open Tundra", ['"', '"', '"', ";"]), ("Snowfield", ['"', '"', "x", "."]), ("Frozen Heath", ['"', '"', "%", ";"])],
            "[": [
                ("Tidal Strand", ["[", "[", "r", "."]),
                ("Rocky Isles", ["[", "[", "x", "."]),
                ("Salt Marsh Coast", ["[", "r", "r", ";"]),
                ("Palm Cays", [";", ";", "[", "."]),
                ("Desert Isles", [chr(96), chr(96), "[", "x"]),
            ],
        }.get(biome, [("Wild Country", [biome, "."])])
        index = int(self.wilderness_hash01(chunk_x, chunk_y, 88500) * len(options)) % len(options)
        name, palette = options[index]
        return {"name": name, "biome": biome, "palette": palette}

    def apply_wilderness_subhabitat(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        """Shape broad terrain patches without adding valuable resource density."""
        if not grid:
            return
        profile = self.wilderness_subhabitat_profile(chunk_x, chunk_y)
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 88501)
        h, w = len(grid), len(grid[0])
        replaceable = set([".", ";", "%", "l", "r", "x", "`", '"', "["])
        for patch_index in range(3):
            cx, cy = rng.randint(10, w - 11), rng.randint(6, h - 7)
            rx, ry = rng.randint(7, 15), rng.randint(3, 6)
            for y in range(max(1, cy - ry), min(h - 1, cy + ry + 1)):
                for x in range(max(1, cx - rx), min(w - 1, cx + rx + 1)):
                    if grid[y][x] not in replaceable:
                        continue
                    ellipse = ((x - cx) / max(1, rx)) ** 2 + ((y - cy) / max(1, ry)) ** 2
                    if ellipse <= 1.0 and rng.random() < 0.72:
                        grid[y][x] = rng.choice(profile["palette"])

    def wilderness_major_landscape_profile(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        biome = str(self.wilderness_region_profile(chunk_x, chunk_y).get("biome", ";"))
        options = {
            ";": [("flower_field", "Great Flower Field"), ("moorland", "Windward Moor"), ("large_lake", "Prairie Lake")],
            "%": [("pine_forest", "Deep Pine Stand"), ("birch_grove", "White Birch Grove"), ("waterfall", "Forest Waterfall")],
            "l": [("hot_springs", "Mosslight Hot Springs"), ("ravine", "Fern Ravine"), ("large_lake", "Hollow Lake")],
            "r": [("floodplain", "Braided Floodplain"), ("large_lake", "Heron Lake"), ("waterfall", "Marshfall")],
            "x": [("rocky_valley", "Stonecut Valley"), ("snowy_highlands", "Snowbound Highland"), ("ravine", "Highland Ravine")],
            "`": [("desert_dunes", "Great Dune Sea"), ("rocky_valley", "Redstone Badlands"), ("hot_springs", "Desert Oasis")],
            '"': [("snowy_highlands", "Glacial Highland"), ("tundra_plain", "Open Tundra"), ("large_lake", "Frozen Mere")],
            "[": [
                ("archipelago", "Saltwind Archipelago"),
                ("tropical_isles", "Palmglass Isles"),
                ("desert_isles", "Sunscar Cays"),
                ("floodplain", "Great Tidal Flat"),
                ("rocky_valley", "Sea Cliffs"),
            ],
        }.get(biome, [("moorland", "Open Moor")])
        index = int(self.wilderness_hash01(chunk_x, chunk_y, 89010) * len(options)) % len(options)
        type_id, name = options[index]
        return {"type_id": type_id, "name": name, "biome": biome}

    def apply_wilderness_major_landscape(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        """Carve one navigable, low-value landscape formation into an ordinary chunk."""
        if not grid or self.wilderness_hash01(chunk_x, chunk_y, 89011) < 0.42:
            return
        if self.procedural_town_plan(chunk_x, chunk_y) or self.wilderness_chunk_has_stronghold(chunk_x, chunk_y) or self.wilderness_chunk_has_outpost(chunk_x, chunk_y) or self.wilderness_chunk_has_structure(chunk_x, chunk_y) or self.is_claimable_wilderness_chunk(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return
        profile = self.wilderness_major_landscape_profile(chunk_x, chunk_y)
        kind = str(profile["type_id"])
        h, w = len(grid), len(grid[0])
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 89012)
        cx, cy = rng.randint(16, w - 17), rng.randint(9, h - 10)
        replaceable = {".", ";", "%", "l", "r", "x", "`", '"', "[", "^", "T", "o", "*"}
        for y in range(cy - 6, cy + 7):
            for x in range(cx - 12, cx + 13):
                if grid[y][x] not in replaceable:
                    continue
                ellipse = ((x - cx) / 12.0) ** 2 + ((y - cy) / 6.0) ** 2
                if ellipse > 1.0:
                    continue
                if kind == "large_lake": grid[y][x] = "~" if ellipse < 0.72 else "r"
                elif kind == "floodplain": grid[y][x] = "~" if (x + y) % 7 == 0 else "r"
                elif kind == "pine_forest": grid[y][x] = "T" if rng.random() < 0.22 else "%"
                elif kind == "birch_grove": grid[y][x] = "T" if rng.random() < 0.10 else rng.choice(["%", ";", "."])
                elif kind == "flower_field": grid[y][x] = ";"
                elif kind == "moorland": grid[y][x] = rng.choice([";", ";", "x"])
                elif kind == "rocky_valley": grid[y][x] = "o" if rng.random() < 0.12 else "x"
                elif kind == "snowy_highlands": grid[y][x] = "x"
                elif kind == "ravine": grid[y][x] = "#" if abs(x - cx) <= 1 and abs(y - cy) < 5 else "x"
                elif kind == "hot_springs": grid[y][x] = "~" if ellipse < 0.30 else "l"
                elif kind == "waterfall": grid[y][x] = "~" if abs(x - cx) <= 1 else ("r" if abs(x - cx) <= 3 else str(profile["biome"]))
                elif kind == "desert_dunes": grid[y][x] = "x" if (x - cx) % 6 == 0 and rng.random() < 0.35 else "`"
                elif kind == "tundra_plain": grid[y][x] = "x" if rng.random() < 0.06 else '"'
                elif kind == "archipelago": grid[y][x] = "~" if rng.random() < 0.72 else rng.choice(["[", "[", "x"])
                elif kind == "tropical_isles":
                    grid[y][x] = "~" if rng.random() < 0.66 else ("T" if rng.random() < 0.10 else rng.choice([";", ";", "["]))
                elif kind == "desert_isles":
                    grid[y][x] = "~" if rng.random() < 0.70 else ("o" if rng.random() < 0.09 else rng.choice([chr(96), chr(96), "x"]))
        # A bridge/ford keeps water and ravine formations traversable before the
        # general trail repair runs, and the marker anchors inspection/activity.
        if kind in {"large_lake", "floodplain", "ravine", "waterfall", "archipelago", "tropical_isles", "desert_isles"}:
            for x in range(cx - 3, cx + 4): grid[cy][x] = "="
        marker_x = cx + (11 if kind == "large_lake" else (7 if kind == "hot_springs" else 0))
        marker_y = cy
        self.stamp_wilderness_landscape_facilities(grid, cx, cy, kind, (marker_x, marker_y))

    def wilderness_landscape_record(self, chunk_x: int = None, chunk_y: int = None) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        self.ensure_wilderness_poi_state()
        profile = self.wilderness_major_landscape_profile(cx, cy)
        record = self.state.wilderness_poi_state.setdefault(f"landscape:{cx},{cy}", {})
        record.setdefault("kind", "major_landscape")
        record.setdefault("type_id", profile["type_id"])
        record.setdefault("name", profile["name"])
        return record

    def interact_with_wilderness_landscape(self) -> bool:
        record = self.wilderness_landscape_record()
        kind, day, week = str(record["type_id"]), self.errand_day_key(), self.stronghold_cache_week_key()
        if kind == "hot_springs":
            if record.get("rest_day") == day:
                self.set_message("You already soaked in these hot springs today.")
                return False
            before = int(self.state.stamina)
            self.restore_stamina(28)
            self.advance_time(40)
            record["rest_day"] = day
            self.autosave_with_message(f"Soaked in {record['name']}: +{int(self.state.stamina) - before} stamina.")
            return True
        if record.get("survey_week") == week:
            self.set_message(f"You already recorded this week's observations at {record['name']}.")
            return False
        self.advance_time(15)
        self.state.money += 30
        coastal_drops = {}
        if self.wilderness_region_profile(
            self.state.wilderness_chunk_x,
            self.state.wilderness_chunk_y,
        ).get("biome") == "[":
            coastal_drops = {
                "archipelago": {"Fiber": 1, "Marsh Reed": 1},
                "floodplain": {"Clay": 1, "Marsh Reed": 2},
                "rocky_valley": {"Stone": 2, "Fiber": 1},
            }.get(kind, {"Marsh Reed": 1})
            add_inventory_items(self.state.inventory, coastal_drops)
        record["survey_week"] = week
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 1, f"surveyed {record['name']}")
        gathered = f", plus {format_drops(coastal_drops)}" if coastal_drops else ""
        self.autosave_with_message(f"Recorded changing conditions at {record['name']}: +30g and +1 regional vitality{gathered}.")
        return True

    def place_wilderness_dock(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        """Place a small usable dock beside substantial connected water."""
        if not grid or self.procedural_town_plan(chunk_x, chunk_y) or self.wilderness_chunk_has_stronghold(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return
        if sum(row.count("~") for row in grid) < 24 or self.wilderness_hash01(chunk_x, chunk_y, 89100) < 0.46:
            return
        if any(WILDERNESS_DOCK_SYMBOL in row for row in grid):
            return
        h, w = len(grid), len(grid[0])
        candidates = []
        for y in range(3, h - 3):
            for x in range(4, w - 4):
                if grid[y][x] not in {".", ";", "%", "l", "r", "x", "`", '"', "[", ":"}:
                    continue
                adjacent_water = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if grid[y + dy][x + dx] == "~"]
                adjacent_land = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if grid[y + dy][x + dx] not in {"~", "#"}]
                if adjacent_water and adjacent_land:
                    candidates.append((x, y))
        if not candidates:
            return
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 89101)
        x, y = rng.choice(candidates)
        grid[y][x] = WILDERNESS_DOCK_SYMBOL

    def apply_wilderness_ocean_coherence(
        self,
        grid: List[List[str]],
        chunk_x: int,
        chunk_y: int,
    ) -> int:
        """Expand true ocean water across safe generic terrain in old coastal chunks."""
        if not grid or self.wilderness_region_profile(chunk_x, chunk_y).get("biome") != "[":
            return 0
        changed = 0
        generic_land = {".", ";", "%", "l", "r", "x", "[", chr(96)}
        for y, row in enumerate(grid):
            for x, tile in enumerate(row):
                wx, wy = self.wilderness_world_coords(chunk_x, chunk_y, x, y)
                expected_water = self.wilderness_world_ocean_tile(wx, wy)
                if expected_water and tile in generic_land:
                    row[x] = "~"
                    changed += 1
                elif not expected_water and tile in generic_land:
                    surface = self.wilderness_world_island_surface(wx, wy)
                    if tile != surface:
                        row[x] = surface
                        changed += 1
        return changed

    def ensure_wilderness_destination_island(
        self,
        grid: List[List[str]],
        chunk_x: int,
        chunk_y: int,
    ) -> int:
        """Keep meaningful coastal destinations on a practical island footprint."""
        if not grid or self.wilderness_region_profile(chunk_x, chunk_y).get("biome") != "[":
            return 0
        has_destination = bool(
            self.wilderness_chunk_has_stronghold(chunk_x, chunk_y)
            or self.procedural_town_plan(chunk_x, chunk_y)
            or self.owned_wilderness_claim(chunk_x, chunk_y)
            or self.is_claimable_wilderness_chunk(chunk_x, chunk_y)
            or self.wilderness_chunk_has_outpost(chunk_x, chunk_y)
            or self.wilderness_chunk_has_structure(chunk_x, chunk_y)
        )
        if not has_destination:
            return 0
        h, w = len(grid), len(grid[0])
        center_x, center_y = w // 2, h // 2
        radius_x = 34 if (
            self.wilderness_chunk_has_stronghold(chunk_x, chunk_y)
            or self.procedural_town_plan(chunk_x, chunk_y)
            or self.owned_wilderness_claim(chunk_x, chunk_y)
        ) else 20
        radius_y = 15 if radius_x >= 34 else 9
        changed = 0
        for y in range(max(1, center_y - radius_y), min(h - 1, center_y + radius_y + 1)):
            for x in range(max(1, center_x - radius_x), min(w - 1, center_x + radius_x + 1)):
                ellipse = (
                    ((x - center_x) / max(1, radius_x)) ** 2
                    + ((y - center_y) / max(1, radius_y)) ** 2
                )
                if ellipse > 1.0 or grid[y][x] != "~":
                    continue
                wx, wy = self.wilderness_world_coords(chunk_x, chunk_y, x, y)
                grid[y][x] = self.wilderness_world_island_surface(wx, wy)
                changed += 1
        return changed

    def ensure_wilderness_docks_touch_water(
        self,
        grid: List[List[str]],
        chunk_x: int,
        chunk_y: int,
    ) -> int:
        """Connect every dock/harbor marker to real water without moving the marker."""
        if not grid:
            return 0
        h, w = len(grid), len(grid[0])
        markers = [
            (x, y)
            for y, row in enumerate(grid)
            for x, tile in enumerate(row)
            if tile in {WILDERNESS_DOCK_SYMBOL, WILDERNESS_FISHING_SETTLEMENT_SYMBOL}
        ]
        if not markers:
            return 0
        changed = 0
        protected = {
            WILDERNESS_DOCK_SYMBOL,
            WILDERNESS_FISHING_SETTLEMENT_SYMBOL,
            WILDERNESS_OUTPOST_SYMBOL,
            WILDERNESS_STRUCTURE_SYMBOL,
            FIELD_SITE_SYMBOL,
            "#", "V", "X", "!", "S", "R", "J", "P", "K", "Q", "Y",
        }
        for mx, my in markers:
            adjacent = [
                (mx + dx, my + dy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= mx + dx < w and 0 <= my + dy < h
            ]
            if any(grid[y][x] in {"~", "="} for x, y in adjacent):
                continue
            waters = [
                (abs(x - mx) + abs(y - my), x, y)
                for y, row in enumerate(grid)
                for x, tile in enumerate(row)
                if tile == "~"
            ]
            if not waters:
                continue
            _distance, target_x, target_y = min(waters)
            x, y = mx, my
            horizontal_first = abs(target_x - mx) >= abs(target_y - my)
            axes = ("x", "y") if horizontal_first else ("y", "x")
            for axis in axes:
                target = target_x if axis == "x" else target_y
                while (x if axis == "x" else y) != target:
                    if axis == "x":
                        x += 1 if target > x else -1
                    else:
                        y += 1 if target > y else -1
                    if (x, y) == (target_x, target_y):
                        break
                    if grid[y][x] in protected:
                        continue
                    if grid[y][x] != "~":
                        grid[y][x] = "~"
                        changed += 1
            # A blocked channel still receives a guaranteed one-tile landing.
            if not any(grid[y][x] in {"~", "="} for x, y in adjacent):
                adjacent.sort(key=lambda point: abs(point[0] - target_x) + abs(point[1] - target_y))
                ax, ay = adjacent[0]
                if grid[ay][ax] not in protected:
                    grid[ay][ax] = "~"
                    changed += 1
        return changed

    def wilderness_dock_water_tile(self, x: int, y: int) -> Tuple[int, int]:
        grid = self.active_map()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = int(x) + dx, int(y) + dy
            if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] in {"~", "="}:
                return nx, ny
        return (-1, -1)

    def wilderness_dock_land_tile(self, x: int, y: int) -> Tuple[int, int]:
        grid = self.active_map()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = int(x) + dx, int(y) + dy
            if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] in {".", ";", "%", "l", "r", "x", "`", '"', "[", ":", "^"}:
                return nx, ny
        return (-1, -1)

    def wilderness_boat_available(self) -> bool:
        return bool(self.state.wilderness_boat_owned or self.state.wilderness_boat_rental_day == self.errand_day_key())

    def wilderness_portable_raft_available(self) -> bool:
        return int(self.state.inventory.get("Explorer Raft", 0)) > 0

    def wilderness_watercraft_available(self) -> bool:
        return bool(self.wilderness_portable_raft_available() or self.wilderness_boat_available())

    def wilderness_open_water_at(self, x: int, y: int) -> bool:
        if not self.in_active_bounds(x, y) or self.active_map()[int(y)][int(x)] != "~":
            return False
        return not self.wilderness_water_is_frozen_at(int(x), int(y))

    def wilderness_water_description(self, x: int, y: int) -> str:
        if self.wilderness_water_is_frozen_at(int(x), int(y)):
            return "Frozen freshwater ice: walk across carefully."
        wx, wy = self.wilderness_world_coords(
            self.state.wilderness_chunk_x,
            self.state.wilderness_chunk_y,
            int(x),
            int(y),
        )
        travel = (
            "Step into it to launch your watercraft automatically."
            if self.wilderness_watercraft_available()
            else "Craft an Explorer Raft or obtain a skiff to enter it."
        )
        if self.wilderness_world_reef_at(wx, wy):
            return f"Warm coral shallows rich in tropical fish. {travel}"
        current = self.wilderness_world_current(wx, wy)
        if current:
            strength = "strong " if int(current.get("strength", 1)) >= 2 else ""
            return (
                f"Open ocean with a {strength}{current.get('name', 'moving')} current. "
                f"Fish here or {travel[0].lower() + travel[1:]}"
            )
        return f"Open water. Fish here or {travel[0].lower() + travel[1:]}"

    def wilderness_water_movement_preview(self, x: int, y: int) -> bool:
        if not self.on_wilderness() or not self.in_active_bounds(x, y):
            return False
        if self.wilderness_open_water_at(x, y):
            return self.wilderness_watercraft_available()
        was_boating = bool(self.state.wilderness_boating)
        if was_boating and self.active_map()[int(y)][int(x)] != "=":
            self.state.wilderness_boating = False
        try:
            return bool(self.passable(int(x), int(y)))
        finally:
            self.state.wilderness_boating = was_boating

    def prepare_wilderness_water_movement(self, x: int, y: int) -> bool:
        """Switch between walking and watercraft as part of an ordinary step."""
        if not self.on_wilderness() or not self.in_active_bounds(x, y):
            return True
        target_tile = self.active_map()[int(y)][int(x)]
        if self.wilderness_open_water_at(x, y):
            if not self.wilderness_watercraft_available():
                self.set_message(
                    "Open water blocks the way. Craft an Explorer Raft or obtain a skiff."
                )
                return False
            was_boating = bool(self.state.wilderness_boating)
            if not self.state.wilderness_boating:
                self.state.wilderness_boating = True
                craft = "Explorer Raft" if self.wilderness_portable_raft_available() else "skiff"
                self.set_message(f"Your {craft} takes the water automatically.")
            if not self.passable(int(x), int(y)):
                self.state.wilderness_boating = was_boating
                return False
            return True
        if self.state.wilderness_boating and target_tile != "=":
            self.state.wilderness_boating = False
            if not self.passable(int(x), int(y)):
                self.state.wilderness_boating = True
                return False
            self.set_message("You pull the watercraft ashore and continue on foot.")
        return True

    def apply_wilderness_current_after_move(self, dx: int, dy: int) -> bool:
        if not self.on_wilderness() or not self.state.wilderness_boating:
            return False
        x, y = int(self.state.player_x), int(self.state.player_y)
        if not self.wilderness_open_water_at(x, y):
            return False
        wx, wy = self.wilderness_world_coords(
            self.state.wilderness_chunk_x,
            self.state.wilderness_chunk_y,
            x,
            y,
        )
        current = self.wilderness_world_current(wx, wy)
        if not current:
            return False
        aligned = (int(dx), int(dy)) == (int(current["dx"]), int(current["dy"]))
        opposed = (int(dx), int(dy)) == (-int(current["dx"]), -int(current["dy"]))
        serial = int(getattr(self, "_wilderness_current_step_serial", 0)) + 1
        self._wilderness_current_step_serial = serial
        if aligned and int(current.get("strength", 1)) >= 2 and serial % 3 == 0:
            nx, ny = x + int(current["dx"]), y + int(current["dy"])
            if (
                self.in_active_bounds(nx, ny)
                and self.wilderness_open_water_at(nx, ny)
                and self.passable(nx, ny)
            ):
                previous = (x, y)
                self.state.player_x, self.state.player_y = nx, ny
                self.update_travel_followers_after_player_move(previous)
                self.set_message(
                    f"A strong {current['name']} current carries your watercraft one extra tile."
                )
                return True
        if opposed and serial % 4 == 0:
            self.set_message(f"You paddle steadily against the {current['name']} current.")
        return False

    def rent_wilderness_boat(self) -> bool:
        if self.state.wilderness_boat_owned:
            self.set_message("You already own a wilderness skiff.")
            return False
        if self.state.wilderness_boat_rental_day == self.errand_day_key():
            self.set_message("Today's skiff rental is already active.")
            return False
        if int(self.state.money) < 75:
            self.set_message("A skiff rental costs 75g for the day.")
            return False
        self.state.money -= 75
        self.state.wilderness_boat_rental_day = self.errand_day_key()
        self.autosave_with_message("Rented a wilderness skiff for the day. It launches automatically when you step into water.")
        return True

    def buy_wilderness_boat(self) -> bool:
        if self.state.wilderness_boat_owned:
            self.set_message("You already own a wilderness skiff.")
            return False
        if int(self.state.money) < 1200:
            self.set_message("A personal wilderness skiff costs 1,200g.")
            return False
        self.state.money -= 1200
        self.state.wilderness_boat_owned = True
        self.autosave_with_message("Purchased a wilderness skiff. It now launches automatically from any safe shore.")
        return True

    def embark_wilderness_boat(self, dock_x: int, dock_y: int) -> bool:
        if not self.wilderness_watercraft_available():
            self.set_message("Craft an Explorer Raft or rent or purchase a skiff first.")
            return False
        water = self.wilderness_dock_water_tile(dock_x, dock_y)
        if water == (-1, -1):
            self.set_message("This dock no longer reaches navigable water.")
            return False
        self.state.wilderness_boating = True
        self.state.player_x, self.state.player_y = water
        self.advance_time(5)
        self.set_message("Embarked. Ordinary movement now carries the skiff across open water and back onto shore.")
        return True

    def disembark_wilderness_boat(self, dock_x: int, dock_y: int) -> bool:
        land = self.wilderness_dock_land_tile(dock_x, dock_y)
        if land == (-1, -1):
            self.set_message("There is no safe landing beside this dock.")
            return False
        self.state.wilderness_boating = False
        self.state.player_x, self.state.player_y = land
        self.advance_time(5)
        self.set_message("Secured the skiff and stepped ashore.")
        return True

    def known_wilderness_ferry_destinations(self) -> List[Dict[str, object]]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        destinations = []
        maps = getattr(self, "wilderness_maps", {})
        if not isinstance(maps, dict):
            return []
        for key, grid in maps.items():
            try: dx, dy = [int(part) for part in str(key).split(",", 1)]
            except (TypeError, ValueError): continue
            distance = abs(dx - cx) + abs(dy - cy)
            if not distance or distance > 6 or not isinstance(grid, list) or not any(WILDERNESS_DOCK_SYMBOL in row or WILDERNESS_FISHING_SETTLEMENT_SYMBOL in row for row in grid):
                continue
            destinations.append({"key": key, "x": dx, "y": dy, "distance": distance, "cost": 25 + distance * 15, "name": self.wilderness_region_profile(dx, dy)["name"]})
        return sorted(destinations, key=lambda value: (int(value["distance"]), str(value["name"])))[:8]

    def take_wilderness_ferry(self, destination: Dict[str, object]) -> bool:
        cost = int(destination.get("cost", 0))
        if int(self.state.money) < cost:
            self.set_message(f"The ferry passage costs {cost}g.")
            return False
        self.state.money -= cost
        self.state.wilderness_boating = False
        self.set_wilderness_chunk(int(destination["x"]), int(destination["y"]))
        docks = [(x, y) for y, row in enumerate(self.active_map()) for x, tile in enumerate(row) if tile in {WILDERNESS_DOCK_SYMBOL, WILDERNESS_FISHING_SETTLEMENT_SYMBOL}]
        if docks:
            land = self.wilderness_dock_land_tile(*docks[0])
            if land != (-1, -1): self.state.player_x, self.state.player_y = land
        self.advance_time(20 + int(destination.get("distance", 1)) * 15)
        self.autosave_with_message(f"Took the ferry to {destination.get('name', 'a known dock')} for {cost}g.")
        return True

    def show_wilderness_dock(self, x: int, y: int):
        items = []
        if self.state.wilderness_boating:
            items.append(self._wilderness_menu_item("disembark", "Disembark", "Secure the skiff and step onto shore."))
        else:
            if self.wilderness_watercraft_available(): items.append(self._wilderness_menu_item("embark", "Launch watercraft", "Optional shortcut; ordinary movement also launches automatically."))
            if not self.wilderness_portable_raft_available():
                items.append(self._wilderness_menu_item("raft_info", "Explorer Raft plans", "Craft with 20 Wood and 10 Fiber; reusable from any shore."))
            if not self.state.wilderness_boat_owned: items.append(self._wilderness_menu_item("rent", "Rent skiff - 75g", "Available from every dock for the current day."))
            if not self.state.wilderness_boat_owned: items.append(self._wilderness_menu_item("buy", "Buy skiff - 1,200g", "Permanent access from every wilderness dock."))
            for destination in self.known_wilderness_ferry_destinations():
                items.append(self._wilderness_menu_item(f"ferry:{destination['key']}", f"Ferry to {destination['name']} - {destination['cost']}g", f"Known dock at chunk ({destination['x']},{destination['y']}); {destination['distance']} chunks away."))
        active_cargo = self.active_wilderness_water_cargo()
        if active_cargo:
            items.append(self._wilderness_menu_item("cargo_status", "Review carried cargo", f"Bound for {active_cargo.get('destination_name')} ({active_cargo.get('destination')})."))
            if str(active_cargo.get("destination")) == self.wilderness_chunk_key(): items.append(self._wilderness_menu_item("cargo_deliver", "Deliver contracted cargo", f"Receive {active_cargo.get('reward')}g."))
        choice = self.vertical_panel_select("Wilderness Dock", items, 50, 20, return_back=True)
        if not choice: return
        if choice.value == "embark": self.embark_wilderness_boat(x, y)
        elif choice.value == "disembark": self.disembark_wilderness_boat(x, y)
        elif choice.value == "rent": self.rent_wilderness_boat()
        elif choice.value == "buy": self.buy_wilderness_boat()
        elif choice.value == "raft_info": self.set_message("Craft an Explorer Raft from 20 Wood and 10 Fiber. It deploys automatically from any shore.")
        elif choice.value == "cargo_status": self.vertical_panel_view("Water Cargo", self.wilderness_water_cargo_lines(), 52, 22)
        elif choice.value == "cargo_deliver": self.complete_wilderness_water_cargo()
        elif str(choice.value).startswith("ferry:"):
            destination = next((value for value in self.known_wilderness_ferry_destinations() if f"ferry:{value['key']}" == choice.value), None)
            if destination: self.take_wilderness_ferry(destination)

    def wilderness_region_port_chunk(self, chunk_x: int, chunk_y: int) -> Optional[Tuple[int, int]]:
        """Choose one reliable harbor site for a coastal organic region."""
        anchor = self.wilderness_region_coords(chunk_x, chunk_y)
        cache_key = (int(self.state.wilderness_seed), anchor)
        cache = getattr(self, "_wilderness_region_port_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_region_port_cache = cache
        if cache_key in cache:
            return cache[cache_key]
        world_x, world_y = self.wilderness_world_coords(anchor[0], anchor[1], 43, 19)
        if self.wilderness_world_biome_tile(world_x, world_y) != "[":
            cache[cache_key] = None
            return None
        scored = []
        occupied = {
            self.wilderness_region_outpost_chunk(*anchor),
            self.wilderness_region_structure_chunk(*anchor),
        }
        if self.procedural_town_region_selected(*anchor):
            occupied.add(self.procedural_town_site_for_region(*anchor))
        samples = [(x, y) for y in (5, 10, 15, 20, 25, 30, 35) for x in (8, 18, 28, 38, 48, 58, 68, 78)]
        for candidate_x, candidate_y in self.wilderness_region_chunks(*anchor):
            if self.is_claimable_wilderness_chunk(candidate_x, candidate_y) or self.wilderness_chunk_has_stronghold(candidate_x, candidate_y):
                continue
            if (candidate_x, candidate_y) in occupied:
                continue
            water = 0
            for x, y in samples:
                wx, wy = self.wilderness_world_coords(candidate_x, candidate_y, x, y)
                water += 1 if self.wilderness_world_water_tile(wx, wy) else 0
            if water >= 12:
                scored.append((-water, abs(candidate_x - anchor[0]) + abs(candidate_y - anchor[1]), candidate_y, candidate_x))
        scored.sort()
        cache[cache_key] = (scored[0][3], scored[0][2]) if scored else None
        return cache[cache_key]

    def wilderness_chunk_has_fishing_settlement(self, chunk_x: int, chunk_y: int) -> bool:
        designated_port = self.wilderness_region_port_chunk(chunk_x, chunk_y)
        if designated_port == (int(chunk_x), int(chunk_y)):
            return True
        if self.wilderness_hash01(chunk_x, chunk_y, 89200) < 0.86:
            return False
        return not (self.procedural_town_plan(chunk_x, chunk_y) or self.wilderness_chunk_has_stronghold(chunk_x, chunk_y) or self.wilderness_chunk_has_outpost(chunk_x, chunk_y) or self.wilderness_chunk_has_structure(chunk_x, chunk_y) or self.is_claimable_wilderness_chunk(chunk_x, chunk_y))

    def wilderness_fishing_settlement_record(self, chunk_x: int = None, chunk_y: int = None, create: bool = True) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        self.ensure_wilderness_poi_state()
        key = f"fishing_settlement:{cx},{cy}"
        record = self.state.wilderness_poi_state.get(key)
        if not isinstance(record, dict):
            if not create: return {}
            record = {"kind": "fishing_settlement", "name": self.wilderness_fishing_settlement_name(cx, cy), "level": 0}
            self.state.wilderness_poi_state[key] = record
        record["level"] = max(0, min(3, int(record.get("level", 0))))
        return record

    def wilderness_fishing_settlement_name(self, chunk_x: int, chunk_y: int) -> str:
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 89201)
        return f"{rng.choice(['Reed', 'Gull', 'Stillwater', 'Driftwood', 'Heron', 'Silverfin'])} {rng.choice(['Landing', 'Cove', 'Harbor', 'Isle'])}"

    def fishing_settlement_stage_name(self, level: int) -> str:
        return ["Fishing Camp", "Island Village", "Working Wharf", "Trade Harbor"][max(0, min(3, int(level)))]

    def fishing_settlement_upgrade_profile(self, level: int) -> Dict[str, object]:
        return {
            1: {"name": "Build the Island Village", "materials": {"Wood": 10, "Stone": 4, "Fiber": 6}, "minutes": 120},
            2: {"name": "Construct the Working Wharf", "materials": {"Wood": 16, "Stone": 10, "Iron Bar": 2}, "minutes": 180},
            3: {"name": "Establish the Trade Harbor", "materials": {"Wood": 24, "Stone": 16, "Iron Bar": 4, "Cloth": 2}, "minutes": 240},
        }.get(int(level), {})

    def place_wilderness_fishing_settlement(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        if not grid or not self.wilderness_chunk_has_fishing_settlement(chunk_x, chunk_y) or sum(row.count("~") for row in grid) < 55:
            return
        h, w = len(grid), len(grid[0])
        road_targets = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile in {":", "="}]
        water_centers = []
        for y in range(7, h - 7):
            for x in range(11, w - 11):
                if grid[y][x] == "~" and sum(1 for yy in range(y - 3, y + 4) for xx in range(x - 6, x + 7) if grid[yy][xx] == "~") >= 45:
                    water_centers.append((x, y))
        if not water_centers:
            return
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 89202)
        cx, cy = rng.choice(water_centers)
        level = int(self.wilderness_fishing_settlement_record(chunk_x, chunk_y)["level"])
        for y in range(cy - 3, cy + 4):
            for x in range(cx - 7, cx + 8):
                ellipse = ((x - cx) / 7.0) ** 2 + ((y - cy) / 3.0) ** 2
                if ellipse <= 1.0: grid[y][x] = ";" if level <= 0 else "."
        # Harbor faces the surrounding water; compact buildings grow inland.
        grid[cy][cx + 7] = WILDERNESS_FISHING_SETTLEMENT_SYMBOL
        grid[cy][cx + 6] = ":"
        for hx, hy in [(cx - 3, cy - 1)] + ([(cx, cy + 1)] if level >= 1 else []) + ([(cx + 2, cy - 1)] if level >= 2 else []):
            for yy in range(hy - 1, hy + 2):
                for xx in range(hx - 1, hx + 2): grid[yy][xx] = "#"
            grid[hy + 1][hx] = "."
        if level >= 3:
            for x in range(cx + 3, cx + 7): grid[cy + 2][x] = "="
        self.connect_wilderness_site_to_regional_road(grid, (cx + 6, cy), road_targets)

    def develop_wilderness_fishing_settlement(self) -> bool:
        record = self.wilderness_fishing_settlement_record()
        next_level = int(record["level"]) + 1
        profile = self.fishing_settlement_upgrade_profile(next_level)
        if not profile:
            self.set_message("This trade harbor is fully developed.")
            return False
        missing = {item: int(qty) - int(self.state.inventory.get(item, 0)) for item, qty in profile["materials"].items() if int(self.state.inventory.get(item, 0)) < int(qty)}
        if missing:
            self.set_message(f"{profile['name']} still needs {format_drops(missing)}.")
            return False
        for item, qty in profile["materials"].items(): self.state.inventory[item] -= int(qty)
        record["level"] = next_level
        self.advance_time(int(profile["minutes"]))
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 4 + next_level * 2, str(profile["name"]))
        self.place_wilderness_fishing_settlement(self.active_map(), self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        self.autosave_with_message(f"{profile['name']} complete. {record['name']} is now a {self.fishing_settlement_stage_name(next_level)}.")
        return True

    def claim_fishing_settlement_weekly_catch(self) -> bool:
        record = self.wilderness_fishing_settlement_record()
        level = int(record["level"])
        if level <= 0:
            self.set_message("Develop the camp into a village before a shared catch is available.")
            return False
        week = self.stronghold_cache_week_key()
        if record.get("catch_week") == week:
            self.set_message("You already collected this harbor's shared catch this week.")
            return False
        coastal = self.wilderness_region_profile(
            self.state.wilderness_chunk_x,
            self.state.wilderness_chunk_y,
        ).get("biome") == "["
        drops = ({"Tide Sardine": 1 + level, "Marsh Reed": level}
                 if coastal else {"River Chub": 1 + level, "Fiber": level})
        if level >= 2: drops["Mackerel" if coastal else "Carp"] = 1
        if level >= 3: drops["Field Snack"] = 1
        add_inventory_items(self.state.inventory, drops)
        record["catch_week"] = week
        self.autosave_with_message(f"Collected {record['name']}'s weekly shared catch: {format_drops(drops)}.")
        return True

    def claim_fishing_settlement_trade_income(self) -> bool:
        record = self.wilderness_fishing_settlement_record()
        if int(record["level"]) < 3:
            self.set_message("A fully developed trade harbor is required for route income.")
            return False
        week = self.stronghold_cache_week_key()
        if record.get("trade_income_week") == week:
            self.set_message("This week's harbor trade income is already collected.")
            return False
        known_routes = max(1, len(self.known_wilderness_ferry_destinations()))
        income = 120 + min(180, known_routes * 30)
        self.state.money += income
        record["trade_income_week"] = week
        self.autosave_with_message(f"Collected {income}g from {record['name']}'s connected trade routes.")
        return True

    def fishing_settlement_lines(self) -> List[str]:
        record = self.wilderness_fishing_settlement_record()
        level = int(record["level"])
        rows = [str(record["name"]).upper(), "", f"Stage: {self.fishing_settlement_stage_name(level)} ({level}/3)", "Boat-accessible island community", "", "Growth unlocks:", "1 - Weekly shared catch", "2 - Expanded catch and working wharf", "3 - Trade-route income and completed harbor"]
        profile = self.fishing_settlement_upgrade_profile(level + 1)
        if profile: rows.extend(["", f"Next: {profile['name']}", f"Needs: {format_drops(profile['materials'])}"])
        return rows

    def show_wilderness_fishing_settlement(self, x: int, y: int):
        record = self.wilderness_fishing_settlement_record()
        items = [self._wilderness_menu_item("status", f"{record['name']} status", "Review island growth and benefits.")]
        if self.state.wilderness_boating: items.append(self._wilderness_menu_item("land", "Land at harbor", "Secure the skiff and step onto the island."))
        elif self.wilderness_watercraft_available(): items.append(self._wilderness_menu_item("embark", "Launch watercraft", "Depart from the island harbor."))
        if int(record["level"]) < 3: items.append(self._wilderness_menu_item("develop", "Develop settlement", "Contribute the next stage's materials and labor."))
        if int(record["level"]) >= 1: items.append(self._wilderness_menu_item("catch", "Collect weekly shared catch", "Receive fish and netting supplies."))
        if int(record["level"]) >= 3: items.append(self._wilderness_menu_item("income", "Collect trade-route income", "Weekly income scales with known dock connections."))
        active_cargo = self.active_wilderness_water_cargo()
        if active_cargo:
            items.append(self._wilderness_menu_item("cargo_status", "Review carried cargo", f"Bound for {active_cargo.get('destination_name')} ({active_cargo.get('destination')})."))
            if str(active_cargo.get("destination")) == self.wilderness_chunk_key(): items.append(self._wilderness_menu_item("cargo_deliver", "Deliver contracted cargo", f"Receive {active_cargo.get('reward')}g."))
        elif int(record["level"]) >= 2:
            items.append(self._wilderness_menu_item("cargo_accept", "Accept weekly cargo contract", "Carry harbor goods to a known dock for payment."))
        choice = self.vertical_panel_select(str(record["name"]), items, 52, 23, return_back=True)
        if not choice: return
        if choice.value == "status": self.vertical_panel_view(str(record["name"]), self.fishing_settlement_lines(), 52, 23)
        elif choice.value == "land": self.disembark_wilderness_boat(x, y)
        elif choice.value == "embark": self.embark_wilderness_boat(x, y)
        elif choice.value == "develop": self.develop_wilderness_fishing_settlement()
        elif choice.value == "catch": self.claim_fishing_settlement_weekly_catch()
        elif choice.value == "income": self.claim_fishing_settlement_trade_income()
        elif choice.value == "cargo_status": self.vertical_panel_view("Water Cargo", self.wilderness_water_cargo_lines(), 52, 22)
        elif choice.value == "cargo_accept": self.accept_wilderness_water_cargo()
        elif choice.value == "cargo_deliver": self.complete_wilderness_water_cargo()

    def wilderness_water_cargo_state(self) -> Dict[str, object]:
        self.ensure_wilderness_poi_state()
        state = self.state.wilderness_poi_state.setdefault("water_cargo", {})
        return state if isinstance(state, dict) else {}

    def wilderness_water_cargo_offer(self) -> Dict[str, object]:
        source = self.wilderness_chunk_key()
        destinations = self.known_wilderness_ferry_destinations()
        if not destinations:
            return {}
        week = self.stronghold_cache_week_key()
        rng = random.Random(self.wilderness_chunk_seed(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y) + sum(ord(ch) for ch in week) * 29 + 89300)
        destination = rng.choice(destinations)
        cargo = rng.choice(["smoked fish", "netting bundles", "preserved reeds", "lamp oil", "boat timber", "medical herbs"])
        distance = int(destination["distance"])
        return {"id": f"{source}:{week}", "source": source, "source_name": self.wilderness_fishing_settlement_record().get("name", "Island Harbor"), "destination": str(destination["key"]), "destination_name": str(destination["name"]), "cargo": cargo, "distance": distance, "reward": 140 + distance * 65, "week": week}

    def active_wilderness_water_cargo(self) -> Dict[str, object]:
        active = self.wilderness_water_cargo_state().get("active", {})
        return active if isinstance(active, dict) else {}

    def accept_wilderness_water_cargo(self) -> bool:
        record = self.wilderness_fishing_settlement_record()
        if int(record.get("level", 0)) < 2:
            self.set_message("A working wharf is required before cargo contracts become available.")
            return False
        state = self.wilderness_water_cargo_state()
        if self.active_wilderness_water_cargo():
            self.set_message("You already have an active water cargo contract.")
            return False
        offer = self.wilderness_water_cargo_offer()
        if not offer:
            self.set_message("Discover another dock before requesting a cargo route.")
            return False
        if state.get("completed_offer_id") == offer["id"]:
            self.set_message("This harbor's cargo contract is complete for the week.")
            return False
        state["active"] = dict(offer)
        self.autosave_with_message(f"Loaded {offer['cargo']} for {offer['destination_name']} at chunk ({offer['destination']}). Reward: {offer['reward']}g.")
        return True

    def complete_wilderness_water_cargo(self) -> bool:
        state = self.wilderness_water_cargo_state()
        active = self.active_wilderness_water_cargo()
        if not active:
            self.set_message("You are not carrying contracted harbor cargo.")
            return False
        if str(active.get("destination")) != self.wilderness_chunk_key():
            self.set_message(f"This cargo is bound for {active.get('destination_name')} at chunk ({active.get('destination')}).")
            return False
        reward = int(active.get("reward", 0))
        self.state.money += reward
        state["completed_offer_id"] = str(active.get("id", ""))
        history = state.setdefault("history", [])
        history.append({"cargo": active.get("cargo"), "source": active.get("source"), "destination": active.get("destination"), "reward": reward, "year": int(self.state.year), "season": str(self.state.season)})
        state["history"] = history[-20:]
        state["active"] = {}
        destination_record = self.wilderness_region_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        destination_record["water_cargo_deliveries"] = int(destination_record.get("water_cargo_deliveries", 0)) + 1
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 3, "completed water cargo route")
        self.autosave_with_message(f"Delivered the harbor cargo: +{reward}g and +3 regional vitality.")
        return True

    def wilderness_water_cargo_lines(self) -> List[str]:
        active = self.active_wilderness_water_cargo()
        if active:
            return ["ACTIVE WATER CARGO", "", f"Cargo: {active.get('cargo')}", f"From: {active.get('source_name')} ({active.get('source')})", f"To: {active.get('destination_name')} ({active.get('destination')})", f"Distance: {active.get('distance')} chunks", f"Reward: {active.get('reward')}g", "", "Cargo persists until delivered at the destination dock or harbor."]
        offer = self.wilderness_water_cargo_offer()
        if offer:
            return ["AVAILABLE WATER CARGO", "", f"Cargo: {offer['cargo']}", f"Destination: {offer['destination_name']} ({offer['destination']})", f"Distance: {offer['distance']} chunks", f"Reward: {offer['reward']}g"]
        return ["WATER CARGO", "", "No connected destination is currently known."]

    def wilderness_water_salvage_position(
        self,
        chunk_x: int = None,
        chunk_y: int = None,
        grid: List[List[str]] = None,
    ) -> Tuple[int, int]:
        if not self.on_wilderness() or not self.state.wilderness_boating:
            return (-1, -1)
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        signature = f"{int(self.state.wilderness_seed)}:{self.wilderness_chunk_key(cx, cy)}:{self.stronghold_cache_week_key()}"
        cache = getattr(self, "_wilderness_water_salvage_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_water_salvage_cache = cache
        if signature in cache:
            return tuple(cache[signature])
        region = self.wilderness_region_record(cx, cy)
        week = self.stronghold_cache_week_key()
        if region.get("water_salvage_week") == week:
            cache[signature] = (-1, -1)
            return (-1, -1)
        if grid is None:
            grid = self.active_map() if (cx, cy) == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)) else self.wilderness_stream_map(cx, cy)
        if not grid:
            cache[signature] = (-1, -1)
            return (-1, -1)
        candidates = [(x, y) for y in range(3, len(grid) - 3) for x in range(4, len(grid[0]) - 4) if grid[y][x] == "~"]
        if len(candidates) < 12:
            cache[signature] = (-1, -1)
            return (-1, -1)
        rng = random.Random(self.wilderness_chunk_seed(cx, cy) + sum(ord(ch) for ch in week) * 31 + 89310)
        cache[signature] = rng.choice(candidates)
        return tuple(cache[signature])

    def wilderness_water_salvage_at(self, x: int, y: int) -> bool:
        return self.wilderness_water_salvage_position() == (int(x), int(y))

    def collect_wilderness_water_salvage(self) -> bool:
        if not self.state.wilderness_boating:
            self.set_message("You need a skiff to recover floating salvage.")
            return False
        region = self.wilderness_region_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        week = self.stronghold_cache_week_key()
        if region.get("water_salvage_week") == week:
            self.set_message("You already recovered this chunk's floating salvage this week.")
            return False
        rng = random.Random(self.wilderness_chunk_seed(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y) + sum(ord(ch) for ch in week) * 31 + 89311)
        drops = {"Wood": rng.randint(1, 3), "Fiber": rng.randint(1, 2)}
        if rng.random() < 0.45: drops["Field Snack"] = 1
        add_inventory_items(self.state.inventory, drops)
        region["water_salvage_week"] = week
        self._wilderness_water_salvage_cache = {}
        self.advance_time(10)
        self.autosave_with_message(f"Recovered floating salvage: {format_drops(drops)}.")
        return True

    def wilderness_maritime_encounter(
        self,
        chunk_x: int = None,
        chunk_y: int = None,
        grid: List[List[str]] = None,
    ) -> Dict[str, object]:
        """Return this chunk's deterministic weekly sea encounter, if unresolved."""
        if not self.on_wilderness() or not self.state.wilderness_boating:
            return {}
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        if self.wilderness_region_profile(cx, cy).get("biome") != "[":
            return {}
        self.ensure_wilderness_poi_state()
        week = self.stronghold_cache_week_key()
        record = self.state.wilderness_poi_state.setdefault(f"maritime:{cx},{cy}", {})
        if record.get("resolved_week") == week:
            return {}
        signature = f"{int(self.state.wilderness_seed)}:{cx},{cy}:{week}"
        cache = getattr(self, "_wilderness_maritime_encounter_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_maritime_encounter_cache = cache
        if signature in cache:
            return dict(cache[signature])
        if grid is None:
            grid = self.active_map() if (cx, cy) == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)) else self.wilderness_stream_map(cx, cy)
        if not grid:
            cache[signature] = {}
            return {}
        salvage = self.wilderness_water_salvage_position(cx, cy, grid)
        candidates = [(x, y) for y in range(3, len(grid) - 3) for x in range(4, len(grid[0]) - 4)
                      if grid[y][x] == "~" and (x, y) != salvage]
        if len(candidates) < 30:
            cache[signature] = {}
            return {}
        seed = self.wilderness_chunk_seed(cx, cy) + sum(ord(ch) for ch in week) * 47 + 91370
        rng = random.Random(seed)
        if rng.random() >= 0.58:
            cache[signature] = {}
            return {}
        profile = dict(MARITIME_ENCOUNTER_TYPES[rng.randrange(len(MARITIME_ENCOUNTER_TYPES))])
        profile["position"] = rng.choice(candidates)
        profile["week"] = week
        cache[signature] = dict(profile)
        return profile

    def wilderness_maritime_encounter_at(self, x: int, y: int) -> Dict[str, object]:
        encounter = self.wilderness_maritime_encounter()
        return encounter if tuple(encounter.get("position", (-1, -1))) == (int(x), int(y)) else {}

    def resolve_wilderness_maritime_encounter(self) -> bool:
        encounter = self.wilderness_maritime_encounter()
        if not encounter:
            self.set_message("There is no unresolved maritime encounter here.")
            return False
        encounter_id = str(encounter["id"])
        rng = random.Random(self.wilderness_chunk_seed(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y) + 91371)
        drops, money, vitality, message = {}, 0, 1, ""
        if encounter_id == "shipwreck":
            drops = {"Wood": rng.randint(2, 4), "Fiber": 2, "Iron Ore": 1}
            if rng.random() < 0.35:
                drops["Regional Chart"] = 1
            message = "Recovered useful cargo from the fresh wreck"
        elif encounter_id == "fishing_boat":
            drops = {"Tide Sardine": 2, "Mackerel": 1}
            message = "Helped haul the local crew's nets and shared their catch"
        elif encounter_id == "merchant_vessel":
            money, drops = 90, {"Field Snack": 1}
            message = "Guided a coastal merchant through the island channel"
        elif encounter_id == "stranded_traveler":
            money, vitality = 180, 3
            message = "Towed a stranded traveler safely to a marked route"
        elif encounter_id == "whale_pod":
            money, vitality = 60, 3
            message = "Recorded the passing whale pod without disturbing it"
        else:
            money, drops, vitality = 110, {"Marsh Reed": 1, "Regional Chart": 1}, 2
            message = "Assisted the marine survey crew with current readings"
        if drops:
            add_inventory_items(self.state.inventory, drops)
        self.state.money += money
        self.advance_time(20)
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, vitality, message.lower())
        record = self.state.wilderness_poi_state.setdefault(f"maritime:{self.wilderness_chunk_key()}", {})
        record["resolved_week"] = self.stronghold_cache_week_key()
        record["last_type"] = encounter_id
        self._wilderness_maritime_encounter_cache = {}
        reward = []
        if money: reward.append(f"{money}g")
        if drops: reward.append(format_drops(drops))
        reward.append(f"+{vitality} regional vitality")
        self.autosave_with_message(f"{message}: {', '.join(reward)}.")
        return True

    def wilderness_island_site_profile(self, chunk_x: int = None, chunk_y: int = None) -> Dict[str, object]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        cache = getattr(self, "_wilderness_island_site_profile_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_island_site_profile_cache = cache
        signature = f"{int(self.state.wilderness_seed)}:{cx},{cy}"
        if signature in cache:
            return dict(cache[signature])
        region = self.wilderness_region_profile(cx, cy)
        if region.get("biome") != "[":
            cache[signature] = {}
            return {}
        rx, ry = int(region["rx"]), int(region["ry"])
        rng = random.Random(self.wilderness_chunk_seed(rx, ry) + 91720)
        members = self.wilderness_region_chunks(cx, cy)
        scored_members = []
        for member_x, member_y in members:
            score = 0
            for sample_y in (5, 12, 19, 26, 33):
                for sample_x in (8, 22, 36, 50, 64, 78):
                    wx, wy = self.wilderness_world_coords(member_x, member_y, sample_x, sample_y)
                    if self.wilderness_world_biome_tile(wx, wy) == "[" and not self.wilderness_world_water_tile(wx, wy):
                        score += 1
            if score:
                scored_members.append((score, member_x, member_y))
        scored_members.sort(reverse=True)
        viable = scored_members[:min(5, len(scored_members))]
        site_chunk = members[0]
        if viable:
            selected = viable[rng.randrange(len(viable))]
            site_chunk = (selected[1], selected[2])
        if (cx, cy) != site_chunk:
            cache[signature] = {}
            return {}
        profile = dict(ISLAND_SITE_TYPES[rng.randrange(len(ISLAND_SITE_TYPES))])
        profile["chunk"] = site_chunk
        cache[signature] = profile
        return dict(profile)

    def wilderness_island_site_position(
        self,
        chunk_x: int = None,
        chunk_y: int = None,
        grid: List[List[str]] = None,
    ) -> Tuple[int, int]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        profile = self.wilderness_island_site_profile(cx, cy)
        if not profile:
            return (-1, -1)
        signature = f"{int(self.state.wilderness_seed)}:{self.wilderness_chunk_key(cx, cy)}"
        cache = getattr(self, "_wilderness_island_site_position_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_island_site_position_cache = cache
        if signature in cache:
            return tuple(cache[signature])
        if grid is None:
            grid = self.active_map() if (cx, cy) == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)) else self.wilderness_stream_map(cx, cy)
        if not grid:
            cache[signature] = (-1, -1)
            return (-1, -1)
        candidates = []
        coastal_land = []
        for y in range(6, len(grid) - 6):
            for x in range(8, len(grid[0]) - 8):
                # Ocean provinces now contain salt strands, tropical ground,
                # desert cays, and rocky isles. Island facilities may use any
                # clear island surface rather than requiring the legacy coast
                # glyph specifically.
                if grid[y][x] not in {".", "[", ";", chr(96), "x"}:
                    continue
                wx, wy = self.wilderness_world_coords(cx, cy, x, y)
                if not self.wilderness_world_is_ocean_province(wx, wy):
                    continue
                land_score = sum(
                    grid[yy][xx] != "~"
                    for yy in range(y - 4, y + 5)
                    for xx in range(x - 6, x + 7)
                )
                coastal_land.append((land_score, x, y))
                if any(grid[y + dy][x + dx] == "~" for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    candidates.append((land_score, x, y))
        candidates = candidates or coastal_land
        if not candidates:
            cache[signature] = (-1, -1)
            return (-1, -1)
        rng = random.Random(self.wilderness_chunk_seed(cx, cy) + 91721)
        candidates.sort(reverse=True)
        shortlist = candidates[:max(1, min(8, len(candidates)))]
        _score, site_x, site_y = rng.choice(shortlist)
        cache[signature] = (site_x, site_y)
        return tuple(cache[signature])

    def apply_wilderness_island_site_compound(self, grid: List[List[str]], chunk_x: int, chunk_y: int) -> None:
        """Build a visible restoration compound around this region's island site."""
        profile = self.wilderness_island_site_profile(chunk_x, chunk_y)
        if not profile:
            return
        position = self.wilderness_island_site_position(chunk_x, chunk_y, grid)
        self.stamp_wilderness_island_compound(grid, position, str(profile["id"]), str(profile["symbol"]))

    def wilderness_island_site_at(self, x: int, y: int) -> Dict[str, object]:
        profile = self.wilderness_island_site_profile()
        return profile if self.wilderness_island_site_position() == (int(x), int(y)) else {}

    def wilderness_island_site_record(self) -> Dict[str, object]:
        self.ensure_wilderness_poi_state()
        profile = self.wilderness_island_site_profile()
        key = f"island_site:{self.wilderness_chunk_key()}"
        record = self.state.wilderness_poi_state.setdefault(key, {})
        if profile:
            record.setdefault("type_id", profile["id"])
            record.setdefault("name", profile["name"])
            record.setdefault("restored", False)
            record.setdefault("discovered", False)
        return record

    def restore_wilderness_island_site(self) -> bool:
        profile, record = self.wilderness_island_site_profile(), self.wilderness_island_site_record()
        if not profile or record.get("restored"):
            self.set_message("This island site is already restored." if record.get("restored") else "There is no island site here.")
            return False
        missing = {item: qty - int(self.state.inventory.get(item, 0)) for item, qty in profile["materials"].items() if int(self.state.inventory.get(item, 0)) < qty}
        if missing:
            self.set_message(f"Restoring {profile['name']} still needs {format_drops(missing)}.")
            return False
        for item, qty in profile["materials"].items():
            self.state.inventory[item] -= qty
        record["restored"] = True
        record["discovered"] = True
        self.advance_time(180)
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, 8, f"restored {profile['name']}")
        self.autosave_with_message(f"Restored {profile['name']}. {profile['benefit']}")
        return True

    def claim_wilderness_island_site_service(self) -> bool:
        profile, record = self.wilderness_island_site_profile(), self.wilderness_island_site_record()
        if not profile or not record.get("restored"):
            self.set_message("Restore this island site before its weekly service is available.")
            return False
        week = self.stronghold_cache_week_key()
        if record.get("service_week") == week:
            self.set_message("This island site's weekly service is already complete.")
            return False
        site_id = str(profile["id"])
        drops, money, vitality = {}, 0, 2
        if site_id == "lighthouse": money = 140
        elif site_id == "sea_fort": drops = {"Stone": 3, "Iron Ore": 1}
        elif site_id == "bird_sanctuary": drops, vitality = {"Fiber": 2, "Wildflower": 1}, 4
        elif site_id == "hidden_cove": drops = {"Tide Sardine": 3, "Mackerel": 1}
        else: money, drops = 100, {"Marsh Reed": 1}
        if drops: add_inventory_items(self.state.inventory, drops)
        self.state.money += money
        record["service_week"] = week
        self.advance_time(25)
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, vitality, f"maintained {profile['name']}")
        rewards = ([f"{money}g"] if money else []) + ([format_drops(drops)] if drops else []) + [f"+{vitality} regional vitality"]
        self.autosave_with_message(f"Completed {profile['name']}'s weekly work: {', '.join(rewards)}.")
        return True

    def show_wilderness_island_site(self):
        profile, record = self.wilderness_island_site_profile(), self.wilderness_island_site_record()
        if not profile:
            return
        record["discovered"] = True
        items = []
        if not record.get("restored"):
            items.append(self._wilderness_menu_item("restore", f"Restore site - {format_drops(profile['materials'])}", "Contribute materials and three hours of work."))
        else:
            items.append(self._wilderness_menu_item("service", "Complete weekly site work", str(profile["benefit"])))
        items.append(self._wilderness_menu_item("chart", "Chart surrounding waters", "Reveal nearby wilderness coordinates from this island facility."))
        choice = self.vertical_panel_select(str(profile["name"]), items, 52, 22, return_back=True)
        if not choice: return
        if choice.value == "restore": self.restore_wilderness_island_site()
        elif choice.value == "service": self.claim_wilderness_island_site_service()
        elif choice.value == "chart":
            added = self.map_nearby_wilderness_chunks(1)
            self.advance_time(20)
            self.autosave_with_message(f"Charted {added} nearby area(s) from {profile['name']}.")

    def wilderness_region_outpost_chunk(self, chunk_x: int, chunk_y: int) -> Tuple[int, int]:
        rx, ry = self.wilderness_region_coords(chunk_x, chunk_y)
        candidates = self.wilderness_region_chunks(chunk_x, chunk_y)
        for cx, cy in candidates:
            if (cx, cy) == (0, 0):
                continue
            if self.wilderness_chunk_has_procedural_settlement(cx, cy) or self.wilderness_chunk_has_stronghold(cx, cy) or self.wilderness_chunk_has_dungeon_site(cx, cy) or self.is_claimable_wilderness_chunk(cx, cy):
                continue
            return cx, cy
        return candidates[0]

    def wilderness_chunk_has_outpost(self, chunk_x: int, chunk_y: int) -> bool:
        return (int(chunk_x), int(chunk_y)) == self.wilderness_region_outpost_chunk(chunk_x, chunk_y)

    def wilderness_outpost_name(self, chunk_x: int, chunk_y: int) -> str:
        region = self.wilderness_region_profile(chunk_x, chunk_y)
        level = self.wilderness_region_project_level(chunk_x, chunk_y)
        suffix = "Trail Cabin" if level <= 0 else ("Ranger Outpost" if level == 1 else ("Field Station" if level == 2 else "Preserve Lodge"))
        return f"{region['name']} {suffix}"

    def place_wilderness_outpost(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        if not self.wilderness_chunk_has_outpost(chunk_x, chunk_y) or not grid:
            return
        h, w = len(grid), len(grid[0])
        road_targets = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile in {":", "="}]
        cx = 18 + int(self.wilderness_hash01(chunk_x, chunk_y, 88510) * max(1, w - 36))
        cy = 8 + int(self.wilderness_hash01(chunk_x, chunk_y, 88511) * max(1, h - 18))
        cx, cy = self.choose_wilderness_landmark_center(grid, cx, cy)
        ground = self.wilderness_world_biome_tile(*self.wilderness_world_coords(chunk_x, chunk_y, cx, cy))
        side = self.wilderness_door_side_toward_routes(
            (cx, cy), road_targets, self.wilderness_hash01(chunk_x, chunk_y, 88512)
        )
        _door_x, _door_y, outside_x, outside_y = self.stamp_wilderness_building_exterior(
            grid, (cx, cy), (15, 9), side, WILDERNESS_OUTPOST_SYMBOL, ground
        )
        self.connect_wilderness_site_to_regional_road(grid, (outside_x, outside_y), road_targets)

    def wilderness_outpost_map(self) -> List[List[str]]:
        key = str(getattr(self.state, "current_wilderness_outpost_key", "") or self.wilderness_chunk_key())
        try:
            cx, cy = [int(part) for part in key.split(",", 1)]
        except Exception:
            cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        level = self.wilderness_region_project_level(cx, cy)
        door_side = str(getattr(self.state, "wilderness_outpost_door_side", "south"))
        specialist_schedule = self.wilderness_specialist_schedule(cx, cy)
        specialist_home = str(specialist_schedule.get("presence", "")) == "outpost"
        signature = f"{key}:{level}:{door_side}:{self.errand_day_key()}:{int(self.state.hour)}:{int(specialist_home)}"
        if getattr(self, "_wilderness_outpost_map_signature", "") == signature and isinstance(getattr(self, "_wilderness_outpost_map", None), list):
            return self._wilderness_outpost_map
        width, height = 31, 15
        grid = [[" " for _ in range(width)] for _ in range(height)]
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                grid[y][x] = "."
        for x in range(width):
            grid[0][x] = grid[height - 1][x] = "#"
        for y in range(height):
            grid[y][0] = grid[y][width - 1] = "#"
        grid[height - 1][width // 2] = "D"
        grid[3][4] = "b"
        grid[4][4] = "t"
        grid[4][5] = "c"
        grid[3][8] = "b"
        grid[4][8] = "n" if specialist_home else "c"
        grid[3][width - 5] = "f"
        grid[4][width - 5] = "s"
        grid[3][width // 2] = "P"
        if level >= 1:
            for x in range(10, 21):
                grid[7][x] = "-"
            grid[7][width // 2] = "|"
            grid[6][width // 2] = "&"
            grid[5][width // 2] = "@"
        if level >= 2:
            grid[10][5] = "l"
            grid[10][6] = "l"
            grid[10][width - 6] = "w"
            grid[10][width - 5] = "a"
        if level >= 3:
            grid[10][width // 2 - 1] = "p"
            grid[10][width // 2] = "p"
            grid[10][width // 2 + 1] = "p"
        grid = self.orient_south_door_interior(grid, door_side)
        self._wilderness_outpost_map = grid
        self._wilderness_outpost_map_signature = signature
        return grid

    def enter_wilderness_outpost(self, x: int, y: int):
        side = self.wilderness_exterior_door_side(self.active_map(), x, y)
        dx, dy = self.wilderness_door_delta(side)
        self.state.current_wilderness_outpost_key = self.wilderness_chunk_key()
        self.state.wilderness_outpost_return_x = int(x) + dx
        self.state.wilderness_outpost_return_y = int(y) + dy
        self.state.wilderness_outpost_door_side = side
        self._wilderness_outpost_map_signature = ""
        self.state.location = "WildernessOutpost"
        grid = self.wilderness_outpost_map()
        self.state.player_x, self.state.player_y = self.wilderness_interior_entry_landing(grid, side)
        self.state.facing = {"north": "DOWN", "south": "UP", "west": "RIGHT", "east": "LEFT"}[side]
        self.set_message(f"Entered {self.wilderness_outpost_name(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)}.")

    def exit_wilderness_outpost(self):
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        return_x = int(self.state.wilderness_outpost_return_x)
        return_y = int(self.state.wilderness_outpost_return_y)
        self.state.player_x, self.state.player_y = self.nearest_active_passable_tile(return_x, return_y)
        side = str(getattr(self.state, "wilderness_outpost_door_side", "south"))
        self.state.facing = {"north": "UP", "south": "DOWN", "west": "LEFT", "east": "RIGHT"}.get(side, "DOWN")
        self.set_message("You step back onto the wilderness trail.")

    def wilderness_outpost_lines(self) -> List[str]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_profile(cx, cy)
        level = self.wilderness_region_project_level(cx, cy)
        points, vitality = self.wilderness_region_vitality(cx, cy)
        completed, rank = self.wilderness_expedition_rank(cx, cy)
        keeper = self.wilderness_outpost_keeper(cx, cy) if level >= 1 else {}
        specialist = self.recurring_wilderness_traveler_record(cx, cy)
        specialist_schedule = self.wilderness_specialist_schedule(cx, cy)
        rows = [self.wilderness_outpost_name(cx, cy).upper(), "", f"Region: {region['name']}", f"Sub-habitat: {self.wilderness_subhabitat_profile(cx, cy)['name']}", f"Outpost development: level {level}/3", f"Ecological vitality: {vitality} ({points})", f"Expedition rank: {rank} ({completed})"]
        if keeper:
            rows.append(f"Regional steward: {keeper['name']} — {keeper['role']} ({self.wilderness_outpost_keeper_bond_label(keeper)})")
        rows.extend([
            f"Resident specialist: {specialist['name']} — {specialist['role']} ({self.recurring_wilderness_traveler_bond_label(specialist['bond'])})",
            f"Specialist residence: {specialist['residence']}",
            f"Current specialist assignment: {specialist_schedule['activity']}",
            "",
            "This outpost grows with the regional stewardship project.",
            "The resident specialist follows a real home, commute, fieldwork, and records schedule.",
            "Use the records desk for regional reports and the service counter for supplies.",
        ])
        return rows

    def wilderness_outpost_keeper(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        region = self.wilderness_region_record(chunk_x, chunk_y)
        keeper = region.setdefault("outpost_keeper", {})
        if not keeper.get("name"):
            names = ["Ansel", "Bea", "Cedar", "Dorian", "Elowen", "Faye", "Grove", "Hazel", "Isidore", "June", "Keir", "Maren"]
            profile = self.wilderness_region_profile(chunk_x, chunk_y)
            rng = random.Random(self.wilderness_chunk_seed(int(profile["rx"]) * 41 + 3, int(profile["ry"]) * 43 - 5) + 88700)
            keeper["name"] = rng.choice(names)
        level = self.wilderness_region_project_level(chunk_x, chunk_y)
        keeper["role"] = "Trail Caretaker" if level <= 0 else ("Regional Ranger" if level == 1 else ("Field Researcher" if level == 2 else "Preserve Warden"))
        keeper["bond"] = max(0, int(keeper.get("bond", 0)))
        keeper.setdefault("conversations", 0)
        keeper.setdefault("samples_shared", 0)
        return keeper

    def wilderness_outpost_keeper_bond_label(self, keeper: Dict[str, object]) -> str:
        bond = max(0, int(keeper.get("bond", 0)))
        if bond >= 15:
            return "Trusted Partner"
        if bond >= 8:
            return "Stewardship Colleague"
        if bond >= 3:
            return "Familiar"
        return "New Contact"

    def wilderness_outpost_keeper_lines(self, keeper: Dict[str, object], topic: str = "work") -> List[str]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_profile(cx, cy)
        event = self.wilderness_weekly_event_profile(cx, cy)
        vitality_points, vitality = self.wilderness_region_vitality(cx, cy)
        role = str(keeper.get("role", "Trail Caretaker"))
        work_line = {
            "Regional Ranger": "A route only stays safe when somebody walks it often enough to notice a missing marker, a new washout, or unfamiliar tracks.",
            "Field Researcher": "I compare the same sites across weather and seasons. One observation is interesting; a pattern can guide the whole region.",
            "Preserve Warden": "This place began to thrive when stewardship became a routine shared by travelers, staff, and nearby settlements.",
        }.get(role, "I keep the roof sound, the records dry, and a lamp ready for whoever reaches the trail after dark.")
        if topic == "region":
            dialogue = (
                f"{region['name']} is at {vitality.lower()} vitality. "
                "I notice that in trail use, wildlife movement, forage, and how confidently people travel after dusk."
            )
        elif topic == "event":
            dialogue = (
                f"This week's {event['name']} is not just a notice-board title. "
                "It changes what appears on the ground, which routes need attention, and what samples are worth recording."
            )
        elif topic == "personal":
            dialogue = (
                "I used to think maintaining a place meant preventing change. Now I think it means helping the right changes survive."
                if int(keeper.get("bond", 0) or 0) >= 8
                else "Ask me again after we have worked the same trails a few more times. Trust out here is built from repeated returns."
            )
        else:
            dialogue = work_line
        return [
            f'"{dialogue}"',
            "",
            f"Current work: {role}",
            f"Region: {region['name']} — {vitality} vitality ({vitality_points})",
            f"Current event: {event['name']}",
            f"Trust: {self.wilderness_outpost_keeper_bond_label(keeper)} ({keeper.get('bond', 0)})",
        ]

    def talk_to_wilderness_outpost_keeper(self, keeper: Dict[str, object]) -> bool:
        topic_items = [
            self._wilderness_menu_item("work", "Ask About Their Work", str(keeper.get("role", "Trail Caretaker"))),
            self._wilderness_menu_item("region", "Ask About This Region", "Vitality, routes, and inhabitants"),
            self._wilderness_menu_item("event", "Ask About This Week's Event", "Visible environmental changes"),
            self._wilderness_menu_item("personal", "Ask Why They Stay", self.wilderness_outpost_keeper_bond_label(keeper)),
        ]
        choice = self.vertical_panel_select(
            f"Talk with {keeper.get('name', 'Regional Steward')}",
            topic_items,
            52,
            23,
            return_back=True,
        )
        if not choice:
            return False
        day = self.errand_day_key()
        gained = keeper.get("last_conversation_day") != day
        if gained:
            keeper["last_conversation_day"] = day
            keeper["bond"] = int(keeper.get("bond", 0)) + 1
            keeper["conversations"] = int(keeper.get("conversations", 0)) + 1
        self.vertical_panel_view(str(keeper.get("name", "Regional Steward")), self.wilderness_outpost_keeper_lines(keeper, str(choice.value)), 52, 24)
        response = self.npc_dialogue_response_choice(
            keeper,
            influence_available=gained,
            title=f"Respond to {keeper.get('name', 'Them')}",
        )
        response_effect = int(response.get("effect", 0) or 0) if gained else 0
        if response_effect:
            keeper["bond"] = max(0, min(250, int(keeper.get("bond", 0)) + response_effect))
        self.vertical_panel_view(
            str(keeper.get("name", "Regional Steward")),
            [
                str(response.get("reaction", "The steward returns to the regional records.")),
                "",
                f"Regional trust influence: {response_effect:+}"
                if response_effect
                else "No further trust influence today."
                if not gained
                else "No trust change.",
            ],
            52,
            23,
        )
        self.autosave_with_message(
            f"Spoke with {keeper.get('name', 'the regional steward')}."
            + (f" Trust {1 + response_effect:+}." if gained else "")
        )
        return gained

    def wilderness_outpost_sample_item(self, chunk_x: int, chunk_y: int) -> str:
        biome = self.wilderness_region_profile(chunk_x, chunk_y)["biome"]
        return {";": "Wild Herbs", "%": "Pine Nuts", "l": "Mushrooms", "r": "Marsh Reed", "x": "Stone", "`": "Clay", '"': "Winter Root", "[": "Marsh Reed"}.get(biome, "Wild Herbs")

    def share_wilderness_outpost_sample(self, keeper: Dict[str, object]) -> bool:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_record(cx, cy)
        week = self.stronghold_cache_week_key()
        if region.get("outpost_sample_week") == week:
            self.set_message("You already contributed an ecological sample here this week.")
            return False
        item = self.wilderness_outpost_sample_item(cx, cy)
        if int(self.state.inventory.get(item, 0)) <= 0:
            self.set_message(f"Bring 1 {item} as this week's regional sample.")
            return False
        self.state.inventory[item] -= 1
        self.advance_time(15)
        self.state.money += 60
        keeper["bond"] = int(keeper.get("bond", 0)) + 3
        keeper["samples_shared"] = int(keeper.get("samples_shared", 0)) + 1
        region["outpost_sample_week"] = week
        self.add_wilderness_region_vitality(cx, cy, 3, f"sample shared with {keeper.get('name', 'outpost steward')}")
        self.autosave_with_message(f"Shared 1 {item} with {keeper.get('name', 'the steward')}: +60g, +3 trust, and +3 regional vitality.")
        return True

    def wilderness_group_excursion_key(self) -> str:
        return f"{int(self.state.year)}:{self.state.season}"

    def wilderness_group_excursion_profile(self, focus: str) -> Dict[str, object]:
        return {
            "study": {"name": "Guided Nature Study", "description": "Follow the steward's survey route and let every participant record what catches their attention.", "stamina": 7, "minutes": 80, "bond": 4, "vitality": 5, "learning": 2},
            "trail": {"name": "Group Trail Workday", "description": "Share tools, repair route markers, and leave a safer path for the next traveler.", "stamina": 9, "minutes": 100, "bond": 3, "vitality": 7, "learning": 1},
            "picnic": {"name": "Wilderness Picnic", "description": "Take an unhurried meal outside and let companionship matter more than productivity.", "stamina": 4, "minutes": 90, "bond": 6, "vitality": 3, "learning": 1},
        }.get(str(focus), {})

    def wilderness_group_excursion_lines(self) -> List[str]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_record(cx, cy)
        participants = self.active_travel_follower_ids()
        names = [str(self.travel_follower_data(fid).get("name", fid)) for fid in participants]
        completed = region.get("last_group_excursion") == self.wilderness_group_excursion_key()
        return ["GUIDED GROUP EXCURSION", "", f"Region: {self.wilderness_region_profile(cx, cy)['name']}", f"Season: {self.state.season}, Year {self.state.year}", f"Status: {'completed this season' if completed else 'available'}", f"Participants: {', '.join(names) if names else 'No active traveling followers'}", "", "Nature Study: stronger child learning and balanced bonds.", "Trail Workday: strongest regional vitality and project help.", "Wilderness Picnic: strongest follower and family bonds.", "", "Every excursion uses 1 Field Snack and refreshes next season."]

    def perform_wilderness_group_excursion(self, focus: str) -> bool:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        if self.wilderness_region_project_level(cx, cy) < 1:
            self.set_message("Develop the trail cabin into a ranger outpost before arranging group excursions.")
            return False
        participants = list(self.active_travel_follower_ids())
        if not participants:
            self.set_message("Bring at least one active traveling follower for a group excursion.")
            return False
        region = self.wilderness_region_record(cx, cy)
        key = self.wilderness_group_excursion_key()
        if region.get("last_group_excursion") == key:
            self.set_message("This region's guided excursion is already complete for the season.")
            return False
        profile = self.wilderness_group_excursion_profile(focus)
        if not profile:
            self.set_message("That excursion focus is unavailable.")
            return False
        if int(self.state.inventory.get("Field Snack", 0)) <= 0:
            self.set_message("A guided group excursion needs 1 Field Snack for the shared break.")
            return False
        stamina_cost = max(2, int(profile["stamina"]) - min(2, len(participants) - 1))
        if not self.spend_stamina(stamina_cost):
            return False
        self.state.inventory["Field Snack"] -= 1
        self.advance_time(max(45, int(profile["minutes"]) - min(20, len(participants) * 5)))
        participant_names = [str(self.travel_follower_data(fid).get("name", fid)) for fid in participants]
        family_participants = 0
        for follower_id in participants:
            data = self.travel_follower_data(follower_id)
            name = str(data.get("name", follower_id))
            self.adjust_travel_follower_bond(follower_id, int(profile["bond"]))
            kind, _source_id = self.travel_follower_identity_kind(follower_id)
            if kind == "child":
                child = self.travel_follower_child(follower_id)
                if child:
                    self.adjust_child_affection(child, 3 if focus == "picnic" else 2)
                    learning = self.child_learning_map(child)
                    topic = "Foraging" if focus in {"study", "picnic"} else "Farming"
                    learning[topic] = int(learning.get(topic, 0)) + int(profile["learning"])
                    self.update_child_apprentice_path_from_learning(child)
                family_participants += 1
            elif kind == "spouse":
                family_participants += 1
            memory = f"{self.state.season} Year {self.state.year} - {profile['name']} in {self.wilderness_region_profile(cx, cy)['name']} with {', '.join(participant_names)}."
            self.record_travel_follower_memory(follower_id, memory, flag=f"wilderness_excursion:{self.wilderness_region_profile(cx, cy)['key']}:{key}")
        if family_participants:
            self.adjust_family_bond(3 if focus == "picnic" else 2)
            self.record_family_event(str(profile["name"]), f"The household joined {profile['name'].lower()} in {self.wilderness_region_profile(cx, cy)['name']}.")
        if focus == "trail":
            self.work_on_wilderness_region_project(cx, cy, fieldwork=True)
        if focus == "picnic":
            self.restore_stamina(8 + len(participants) * 2)
        self.add_wilderness_region_vitality(cx, cy, int(profile["vitality"]), str(profile["name"]))
        keeper = self.wilderness_outpost_keeper(cx, cy)
        keeper["bond"] = int(keeper.get("bond", 0)) + 1
        region["last_group_excursion"] = key
        history = region.setdefault("group_excursion_history", [])
        history.append({"name": profile["name"], "season": str(self.state.season), "year": int(self.state.year), "participants": participant_names})
        region["group_excursion_history"] = history[-12:]
        self.autosave_with_message(f"Completed {profile['name']} with {', '.join(participant_names)}: stronger bonds and +{profile['vitality']} regional vitality.")
        return True

    def show_wilderness_group_excursion_menu(self):
        items = [
            self._wilderness_menu_item("status", "Excursion overview", "Review participants, availability, and focus outcomes."),
            self._wilderness_menu_item("study", "Guided Nature Study", "Prioritize observation, learning, and shared discovery."),
            self._wilderness_menu_item("trail", "Group Trail Workday", "Prioritize stewardship, infrastructure, and vitality."),
            self._wilderness_menu_item("picnic", "Wilderness Picnic", "Prioritize family time, rest, and companion bonds."),
        ]
        choice = self.vertical_panel_select("Guided Group Excursion", items, 52, 24, return_back=True)
        if not choice:
            return
        if choice.value == "status":
            self.vertical_panel_view("Guided Group Excursion", self.wilderness_group_excursion_lines(), 52, 24)
        else:
            self.perform_wilderness_group_excursion(str(choice.value))

    def show_wilderness_outpost_keeper(self):
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        keeper = self.wilderness_outpost_keeper(cx, cy)
        keeper_position = next(
            (
                (x, y)
                for y, row in enumerate(self.active_map())
                for x, tile in enumerate(row)
                if tile == "@"
            ),
            (15, 5),
        )
        sample = self.wilderness_outpost_sample_item(cx, cy)
        items = [
            self._wilderness_menu_item("talk", "Talk", "Discuss the region and build a lasting working relationship."),
            self._wilderness_menu_item("sample", f"Share weekly sample — 1 {sample}", "Contribute research material for trust, vitality, and pay."),
            self._wilderness_menu_item("expedition", "Expedition desk", "Review, accept, or file the regional expedition."),
            self._wilderness_menu_item("planning", "Regional planning", "Review and advance the regional stewardship project."),
            self._wilderness_menu_item("excursion", "Guided group excursion", "Take followers or family on a seasonal regional outing."),
        ]
        choice = self.vertical_panel_select(f"{keeper['name']} — {keeper['role']}", items, 52, 24, return_back=True)
        if not choice:
            return
        if choice.value == "talk":
            self.talk_to_wilderness_outpost_keeper(keeper)
        elif choice.value == "sample":
            self.share_wilderness_outpost_sample(keeper)
        elif choice.value == "expedition":
            self.show_wilderness_expedition_menu(*keeper_position)
        elif choice.value == "planning":
            self.show_wilderness_region_project(*keeper_position)
        elif choice.value == "excursion":
            self.show_wilderness_group_excursion_menu()

    def show_wilderness_outpost_specialist(self):
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        specialist = self.wilderness_specialist_actor(cx, cy)
        self.show_wilderness_traveler(specialist)

    def rest_at_wilderness_outpost(self) -> bool:
        region = self.wilderness_region_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        day = self.errand_day_key()
        if region.get("outpost_last_rest_day") == day:
            self.set_message("You already rested at this outpost today.")
            return False
        before = int(self.state.stamina)
        self.restore_stamina(35 + self.wilderness_region_project_level(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y) * 10)
        self.advance_time(35)
        region["outpost_last_rest_day"] = day
        self.autosave_with_message(f"Rested at the outpost: +{int(self.state.stamina) - before} stamina.")
        return True

    def claim_wilderness_outpost_supplies(self) -> bool:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_record(cx, cy)
        week = self.stronghold_cache_week_key()
        if region.get("outpost_last_supply_week") == week:
            self.set_message("The outpost supply locker has already been checked this week.")
            return False
        level = self.wilderness_region_project_level(cx, cy)
        drops = {"Field Snack": 1, "Wood": 1 + level, "Fiber": 1 + level}
        add_inventory_items(self.state.inventory, drops)
        region["outpost_last_supply_week"] = week
        self.autosave_with_message(f"Collected outpost supplies: {format_drops(drops)}.")
        return True

    def use_wilderness_outpost_action(self, x: int, y: int):
        tile = self.active_map()[y][x]
        if tile == "D":
            self.exit_wilderness_outpost()
        elif tile == "b":
            self.rest_at_wilderness_outpost()
        elif tile == "P":
            self.vertical_panel_view("Regional Outpost Records", self.wilderness_outpost_lines(), 52, 24)
        elif tile == "@":
            self.show_wilderness_outpost_keeper()
        elif tile == "n":
            self.show_wilderness_outpost_specialist()
        elif tile in {"&", "s"}:
            self.claim_wilderness_outpost_supplies()
        else:
            self.set_message("The outpost is quiet and orderly.")

    def place_wilderness_field_site(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        """Place one low-value, high-purpose site in most non-civic chunks."""
        if chunk_x == 0 and chunk_y == 0:
            return
        if (
            self.procedural_town_plan(chunk_x, chunk_y)
            or self.wilderness_chunk_has_stronghold(chunk_x, chunk_y)
            or self.is_claimable_wilderness_chunk(chunk_x, chunk_y)
            or self.owned_wilderness_claim(chunk_x, chunk_y)
            or self.wilderness_chunk_has_outpost(chunk_x, chunk_y)
            or self.wilderness_chunk_has_structure(chunk_x, chunk_y)
        ):
            return
        if self.wilderness_hash01(chunk_x, chunk_y, 88020) < 0.32:
            return
        h, w = len(grid), len(grid[0]) if grid else 0
        if not h or not w:
            return
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 88021)
        blocked = {"#", "~", "=", "S", "V", "X", "!", "D", "&", "P", "R", "Q", "K", FIELD_SITE_SYMBOL}
        candidates = []
        for y in range(5, h - 5):
            for x in range(7, w - 7):
                if grid[y][x] not in blocked and all(grid[y + dy][x + dx] not in blocked for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    footprint = [grid[yy][xx] for yy in range(y - 3, y + 4) for xx in range(x - 5, x + 6)]
                    conflicts = sum(tile in blocked for tile in footprint)
                    road_access = sum(tile in {":", "="} for tile in footprint)
                    candidates.append((conflicts * 10 - road_access, x, y))
        if not candidates:
            return
        candidates.sort()
        _score, x, y = rng.choice(candidates[:min(16, len(candidates))])
        ground = self.wilderness_world_biome_tile(*self.wilderness_world_coords(chunk_x, chunk_y, x, y))
        self.stamp_wilderness_field_station(grid, x, y, ground)

    def wilderness_region_record(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        self.ensure_wilderness_poi_state()
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        key = f"region:{profile['key']}"
        if key not in self.state.wilderness_poi_state:
            legacy_key = f"region:{int(chunk_x) // 3},{int(chunk_y) // 3}"
            legacy = self.state.wilderness_poi_state.get(legacy_key, {})
            self.state.wilderness_poi_state[key] = dict(legacy) if isinstance(legacy, dict) else {}
            if legacy:
                self.state.wilderness_poi_state[key]["migrated_from"] = legacy_key
        record = self.state.wilderness_poi_state[key]
        record.setdefault("kind", "region")
        record.setdefault("name", profile["name"])
        record.setdefault("discovered_chunks", [])
        record.setdefault("completed_sites", [])
        record.setdefault("fieldwork_count", 0)
        record.setdefault("project", {})
        return record

    def wilderness_region_project_profile(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        biome = self.wilderness_region_profile(chunk_x, chunk_y)["biome"]
        return {
            ";": {"id": "wildlife_corridor", "name": "Wildlife Corridor", "description": "Mark protected nesting ground and connect the meadow trails.", "materials": {"Wood": 8, "Fiber": 8, "Wild Herbs": 3}, "labor": 4},
            "%": {"id": "restored_trail", "name": "Restored Forest Trail", "description": "Clear deadfall and establish durable route markers beneath the canopy.", "materials": {"Wood": 10, "Stone": 6, "Fiber": 4}, "labor": 4},
            "l": {"id": "research_camp", "name": "Mycology Research Camp", "description": "Build a dry study platform that protects the surrounding fungal beds.", "materials": {"Wood": 8, "Stone": 6, "Fiber": 6}, "labor": 5},
            "r": {"id": "wetland_boardwalk", "name": "Wetland Boardwalk", "description": "Raise a safe crossing above the reeds and seasonal floodwater.", "materials": {"Wood": 12, "Marsh Reed": 8, "Stone": 4}, "labor": 5},
            "x": {"id": "waystone_route", "name": "Highland Waystone Route", "description": "Repair the cairns and secure a dependable path across exposed ground.", "materials": {"Stone": 12, "Wood": 6, "Coal": 3}, "labor": 5},
            "`": {"id": "desert_well_route", "name": "Desert Well Route", "description": "Mark reliable shade and reinforce a seasonal water route.", "materials": {"Stone": 10, "Clay": 8, "Fiber": 6}, "labor": 5},
            '"': {"id": "tundra_shelter_line", "name": "Tundra Shelter Line", "description": "Build windbreaks and durable markers across exposed snowfields.", "materials": {"Wood": 10, "Stone": 8, "Fiber": 8}, "labor": 5},
            "[": {"id": "coastal_channel_network", "name": "Coastal Channel Network", "description": "Mark safe channels and repair public landings across the islands.", "materials": {"Wood": 14, "Stone": 8, "Fiber": 8}, "labor": 6},
        }.get(biome, {"id": "trail_project", "name": "Regional Trail Project", "description": "Establish a dependable wilderness route.", "materials": {"Wood": 8, "Stone": 8, "Fiber": 4}, "labor": 4})

    def wilderness_region_project(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        region = self.wilderness_region_record(chunk_x, chunk_y)
        project = region.setdefault("project", {})
        profile = self.wilderness_region_project_profile(chunk_x, chunk_y)
        project.setdefault("id", profile["id"])
        project.setdefault("supplied", {})
        project.setdefault("labor", 0)
        project.setdefault("completed", False)
        if "level" not in project:
            project["level"] = 1 if bool(project.get("completed", False)) else 0
        project["level"] = max(0, min(3, int(project.get("level", 0))))
        project.setdefault("active_tier", 0 if project["level"] > 0 else 1)
        project["active_tier"] = max(0, min(3, int(project.get("active_tier", 0))))
        if project["active_tier"] <= project["level"]:
            project["active_tier"] = 0
        return project

    def wilderness_region_project_level(self, chunk_x: int, chunk_y: int) -> int:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        state = getattr(self.state, "wilderness_poi_state", {})
        region = state.get(f"region:{profile['key']}", {}) if isinstance(state, dict) else {}
        project = region.get("project", {}) if isinstance(region, dict) else {}
        if not isinstance(project, dict):
            return 0
        if "level" in project:
            return max(0, min(3, int(project.get("level", 0))))
        return 1 if bool(project.get("completed", False)) else 0

    def wilderness_region_project_tier_profile(self, chunk_x: int, chunk_y: int, tier: int = 0) -> Dict[str, object]:
        base = self.wilderness_region_project_profile(chunk_x, chunk_y)
        project = self.wilderness_region_project(chunk_x, chunk_y)
        tier = int(tier or project.get("active_tier", 0) or min(3, int(project.get("level", 0)) + 1))
        tier = max(1, min(3, tier))
        scale = (1.0, 1.5, 2.0)[tier - 1]
        materials = {item: max(1, int(round(int(qty) * scale))) for item, qty in base["materials"].items()}
        labels = {
            1: ("Route Foundation", "Establish safe access and the first maintained work site."),
            2: ("Regional Field Station", "Expand the route into a supplied station for longer expeditions."),
            3: ("Living Regional Preserve", "Connect the field sites into a mature, continuously tended preserve."),
        }
        label, description = labels[tier]
        return {**base, "tier": tier, "tier_name": label, "tier_description": description, "materials": materials, "labor": int(base["labor"]) + (tier - 1) * 2}

    def wilderness_region_project_phase_ready(self, chunk_x: int, chunk_y: int) -> bool:
        project = self.wilderness_region_project(chunk_x, chunk_y)
        if int(project.get("active_tier", 0)) <= 0:
            return False
        profile = self.wilderness_region_project_tier_profile(chunk_x, chunk_y, int(project["active_tier"]))
        supplied = project.get("supplied", {}) if isinstance(project.get("supplied", {}), dict) else {}
        return all(int(supplied.get(item, 0)) >= int(need) for item, need in profile["materials"].items()) and int(project.get("labor", 0)) >= int(profile["labor"])

    def wilderness_region_project_complete(self, chunk_x: int, chunk_y: int) -> bool:
        return self.wilderness_region_project_level(chunk_x, chunk_y) >= 1

    def wilderness_region_project_maxed(self, chunk_x: int, chunk_y: int) -> bool:
        return self.wilderness_region_project_level(chunk_x, chunk_y) >= 3

    def begin_wilderness_region_project_expansion(self, chunk_x: int, chunk_y: int) -> bool:
        project = self.wilderness_region_project(chunk_x, chunk_y)
        level = int(project.get("level", 0))
        if level >= 3:
            self.set_message("This regional preserve is fully developed; weekly stewardship remains available.")
            return False
        if int(project.get("active_tier", 0)) > level:
            self.set_message("The current regional expansion is already underway.")
            return False
        project["active_tier"] = level + 1
        project["supplied"] = {}
        project["labor"] = 0
        tier = self.wilderness_region_project_tier_profile(chunk_x, chunk_y, level + 1)
        self.autosave_with_message(f"Began {tier['tier_name']} expansion for {tier['name']}.")
        return True

    def wilderness_region_project_lines(self, chunk_x: int, chunk_y: int) -> List[str]:
        region = self.wilderness_region_profile(chunk_x, chunk_y)
        project = self.wilderness_region_project(chunk_x, chunk_y)
        base = self.wilderness_region_project_profile(chunk_x, chunk_y)
        level = int(project.get("level", 0))
        active_tier = int(project.get("active_tier", 0))
        profile = self.wilderness_region_project_tier_profile(chunk_x, chunk_y, active_tier or min(3, level + 1))
        supplied = project["supplied"]
        rows = [str(base["name"]).upper(), "", f"Region: {region['name']}", str(base["description"]), "", f"Development: level {level}/3"]
        benefits = ["Level 1: safe regional travel and lower fieldwork stamina.", "Level 2: field-station pay and stronger careful-foraging yields.", "Level 3: preserve bonuses and recurring weekly stewardship."]
        rows.extend(benefits)
        if active_tier > 0:
            rows.extend(["", f"ACTIVE: Level {active_tier} - {profile['tier_name']}", str(profile["tier_description"]), "", "Materials:"])
            for item, need in profile["materials"].items():
                rows.append(f"- {item}: {min(int(need), int(supplied.get(item, 0)))}/{need}")
            rows.extend([f"Labor shifts: {min(int(profile['labor']), int(project.get('labor', 0)))}/{profile['labor']}", "", "Contribute supplies or volunteer a 45-minute work shift."])
        elif level >= 3:
            ready = project.get("last_maintenance_week") != self.stronghold_cache_week_key()
            seasonal_ready = project.get("last_seasonal_initiative") != self.wilderness_seasonal_initiative_key()
            rows.extend(["", "MATURE PRESERVE", f"Weekly stewardship: {'ready' if ready else 'completed this week'}", f"Seasonal initiative: {'ready' if seasonal_ready else 'completed this season'}", f"Recorded seasonal cycles: {int(project.get('seasonal_cycles', 0))}", "The region continues to need surveys, repairs, and habitat care."])
        else:
            rows.extend(["", f"Level {level + 1} expansion is available.", "Begin it when you are ready to deepen the region's infrastructure."])
        return rows

    def contribute_wilderness_region_project(self, chunk_x: int, chunk_y: int) -> bool:
        project = self.wilderness_region_project(chunk_x, chunk_y)
        active_tier = int(project.get("active_tier", 0))
        if active_tier <= 0:
            self.set_message("Begin the next regional expansion before contributing construction supplies.")
            return False
        profile = self.wilderness_region_project_tier_profile(chunk_x, chunk_y, active_tier)
        supplied = project["supplied"]
        moved: Dict[str, int] = {}
        for item, need in profile["materials"].items():
            missing = max(0, int(need) - int(supplied.get(item, 0)))
            amount = min(missing, int(self.state.inventory.get(item, 0)))
            if amount <= 0:
                continue
            self.state.inventory[item] -= amount
            supplied[item] = int(supplied.get(item, 0)) + amount
            moved[item] = amount
        if not moved:
            self.set_message("You are not carrying any supplies this project still needs.")
            return False
        self._finish_wilderness_region_project_if_ready(chunk_x, chunk_y)
        self.autosave_with_message(f"Contributed to {profile['name']}: {format_drops(moved)}.")
        return True

    def work_on_wilderness_region_project(self, chunk_x: int, chunk_y: int, fieldwork: bool = False) -> bool:
        project = self.wilderness_region_project(chunk_x, chunk_y)
        active_tier = int(project.get("active_tier", 0))
        if active_tier <= 0:
            level = int(project.get("level", 0))
            if fieldwork and level < 3:
                active_tier = level + 1
                project["active_tier"] = active_tier
                project["supplied"] = {}
                project["labor"] = 0
            elif fieldwork and level >= 3:
                week = self.stronghold_cache_week_key()
                if project.get("last_maintenance_week") != week:
                    project["last_maintenance_week"] = week
                    project["maintenance_rounds"] = int(project.get("maintenance_rounds", 0)) + 1
                return True
            else:
                self.set_message("There is no active expansion. Begin the next project level first.")
                return False
        profile = self.wilderness_region_project_tier_profile(chunk_x, chunk_y, active_tier)
        if not fieldwork:
            if not self.spend_stamina(8):
                return False
            self.advance_time(45)
        follower_bonus = 1 if len(self.active_travel_follower_ids()) >= 2 else 0
        project["labor"] = min(int(profile["labor"]), int(project.get("labor", 0)) + 1 + follower_bonus)
        completed = self._finish_wilderness_region_project_if_ready(chunk_x, chunk_y)
        message = f"Completed {'a habitat shift' if fieldwork else 'a project work shift'} for {profile['name']}."
        if follower_bonus:
            message += " Your followers completed an additional shift together."
        if completed:
            message += " The regional project is complete."
        if not fieldwork:
            self.autosave_with_message(message)
        return True

    def _finish_wilderness_region_project_if_ready(self, chunk_x: int, chunk_y: int) -> bool:
        project = self.wilderness_region_project(chunk_x, chunk_y)
        if not self.wilderness_region_project_phase_ready(chunk_x, chunk_y):
            return False
        tier = int(project.get("active_tier", 1))
        project["level"] = max(int(project.get("level", 0)), tier)
        project["active_tier"] = 0
        project["completed"] = True
        project["supplied"] = {}
        project["labor"] = 0
        self.state.money += 200 + tier * 100
        add_inventory_items(self.state.inventory, {"Field Snack": tier + 1})
        self.add_wilderness_region_vitality(chunk_x, chunk_y, 8 + tier * 2, f"project level {tier}")
        if self.on_wilderness() and int(self.state.wilderness_chunk_x) == int(chunk_x) and int(self.state.wilderness_chunk_y) == int(chunk_y):
            self.apply_wilderness_region_project_to_grid(self.active_map(), chunk_x, chunk_y)
        return True

    def maintain_wilderness_region_preserve(self, chunk_x: int, chunk_y: int) -> bool:
        if not self.wilderness_region_project_maxed(chunk_x, chunk_y):
            self.set_message("This region must reach preserve level before recurring stewardship begins.")
            return False
        project = self.wilderness_region_project(chunk_x, chunk_y)
        week = self.stronghold_cache_week_key()
        if project.get("last_maintenance_week") == week:
            self.set_message("You already completed this region's stewardship round this week.")
            return False
        if not self.spend_stamina(max(3, 6 - min(2, len(self.active_travel_follower_ids())))):
            return False
        self.advance_time(40)
        biome = self.wilderness_region_profile(chunk_x, chunk_y)["biome"]
        drops = {
            ";": {"Mixed Seeds": 2, "Wild Herbs": 2}, "%": {"Wood": 3, "Pine Nuts": 2},
            "l": {"Mushrooms": 3, "Strange Spores": 1}, "r": {"Marsh Reed": 3, "Clay": 2},
            "x": {"Stone": 3, "Coal": 2},
        }.get(biome, {"Wild Herbs": 2})
        add_inventory_items(self.state.inventory, drops)
        self.state.money += 100
        project["last_maintenance_week"] = week
        project["maintenance_rounds"] = int(project.get("maintenance_rounds", 0)) + 1
        self.add_wilderness_region_vitality(chunk_x, chunk_y, 3, "weekly preserve stewardship")
        self.autosave_with_message(f"Completed weekly stewardship in {self.wilderness_region_profile(chunk_x, chunk_y)['name']}: +100g and {format_drops(drops)}.")
        return True

    def wilderness_seasonal_initiative_key(self) -> str:
        return f"{int(self.state.year)}:{self.state.season}"

    def wilderness_seasonal_initiative_profile(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        biome = self.wilderness_region_profile(chunk_x, chunk_y)["biome"]
        season = str(self.state.season)
        seasonal_action = {
            "Spring": "survey new growth and repair winter-damaged routes",
            "Summer": "monitor water, shade, and peak wildlife activity",
            "Fall": "collect seed records and prepare habitat for migration",
            "Winter": "map tracks and reinforce exposed shelters",
        }.get(season, "conduct a full seasonal habitat survey")
        focus = {";": "Grassland Census", "%": "Canopy Survey", "l": "Fungal Cycle Study", "r": "Watershed Watch", "x": "Highland Route Audit"}.get(biome, "Regional Habitat Survey")
        drops = {
            ";": {"Mixed Seeds": 3, "Wild Herbs": 2}, "%": {"Wood": 3, "Pine Nuts": 2},
            "l": {"Mushrooms": 3, "Strange Spores": 1}, "r": {"Marsh Reed": 3, "Watercress": 2},
            "x": {"Stone": 4, "Coal": 2},
        }.get(biome, {"Wild Herbs": 2})
        return {"name": f"{season} {focus}", "action": seasonal_action, "drops": drops}

    def undertake_wilderness_seasonal_initiative(self, chunk_x: int, chunk_y: int) -> bool:
        if self.wilderness_region_project_level(chunk_x, chunk_y) < 2:
            self.set_message("Build a regional field station before undertaking seasonal initiatives.")
            return False
        project = self.wilderness_region_project(chunk_x, chunk_y)
        key = self.wilderness_seasonal_initiative_key()
        profile = self.wilderness_seasonal_initiative_profile(chunk_x, chunk_y)
        if project.get("last_seasonal_initiative") == key:
            self.set_message("This region's seasonal initiative is already complete.")
            return False
        followers = min(2, len(self.active_travel_follower_ids()))
        if not self.spend_stamina(max(8, 12 - followers * 2)):
            return False
        self.advance_time(max(60, 90 - followers * 10))
        drops = dict(profile["drops"])
        add_inventory_items(self.state.inventory, drops)
        money = 150 + followers * 25
        self.state.money += money
        project["last_seasonal_initiative"] = key
        project["seasonal_cycles"] = int(project.get("seasonal_cycles", 0)) + 1
        self.add_wilderness_region_vitality(chunk_x, chunk_y, 8, str(profile["name"]))
        self.autosave_with_message(f"Completed {profile['name']}—{profile['action']}: +{money}g and {format_drops(drops)}.")
        return True

    def apply_wilderness_region_project_to_grid(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        """Make a completed regional project visible without expensive regeneration."""
        level = self.wilderness_region_project_level(chunk_x, chunk_y)
        if level <= 0 or not grid:
            return
        h, w = len(grid), len(grid[0])
        sites = [(x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == FIELD_SITE_SYMBOL]
        for x, y in sites:
            for dx in range(-4, 5):
                xx = x + dx
                if 1 <= xx < w - 1 and grid[y][xx] not in {"~", "=", "#", "S", "V", "X", "!", FIELD_SITE_SYMBOL}:
                    grid[y][xx] = ":"
            fire_x, fire_y = min(w - 2, x + 2), max(1, y - 1)
            if grid[fire_y][fire_x] not in {"~", "=", "#", "S", "V", "X", "!", FIELD_SITE_SYMBOL}:
                grid[fire_y][fire_x] = "H"
            if level >= 2:
                shelter_x, shelter_y = max(1, x - 2), max(1, y - 1)
                if grid[shelter_y][shelter_x] not in {"~", "=", "#", "S", "V", "X", "!", FIELD_SITE_SYMBOL}:
                    grid[shelter_y][shelter_x] = "Q"
            if level >= 3:
                overlook_x, overlook_y = x, max(1, y - 2)
                if grid[overlook_y][overlook_x] not in {"~", "=", "#", "S", "V", "X", "!", FIELD_SITE_SYMBOL}:
                    grid[overlook_y][overlook_x] = "K"

    def discover_wilderness_chunk(self, chunk_x: int, chunk_y: int) -> bool:
        record = self.wilderness_region_record(chunk_x, chunk_y)
        key = f"{int(chunk_x)},{int(chunk_y)}"
        discovered = record.setdefault("discovered_chunks", [])
        if key in discovered:
            return False
        discovered.append(key)
        return True

    def wilderness_chunk_known(self, chunk_x: int, chunk_y: int) -> bool:
        """Whether the player has visited or received reliable knowledge of a chunk."""
        cx, cy = int(chunk_x), int(chunk_y)
        key = f"{cx},{cy}"
        if (cx, cy) == (0, 0):
            return True
        record = self.wilderness_region_record(cx, cy)
        if key in record.get("discovered_chunks", []) or key in record.get("mapped_chunks", []):
            return True
        # Preserve destinations from older saves and knowledge granted by other systems.
        preloaded = getattr(self, "_wilderness_stream_preloaded_chunks", set())
        if key in getattr(self, "wilderness_maps", {}) and key not in preloaded:
            return True
        if key in (self.state.owned_wilderness_claims or {}):
            return True
        if self.active_bounty_for_chunk(cx, cy) or self.active_wilderness_expedition_for_chunk(cx, cy):
            return True
        settlement = self.procedural_town_plan(cx, cy)
        if settlement and bool(settlement.get("discovered", False)):
            return True
        stronghold = self.wilderness_stronghold_record(cx, cy, create=False)
        return bool(stronghold.get("cleared", False))

    def map_current_wilderness_region(self) -> int:
        """Reveal, but do not generate, every chunk in the current named region."""
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        profile = self.wilderness_region_profile(cx, cy)
        record = self.wilderness_region_record(cx, cy)
        mapped = record.setdefault("mapped_chunks", [])
        added = 0
        for x, y in self.wilderness_region_chunks(cx, cy):
            key = f"{x},{y}"
            if key not in mapped:
                mapped.append(key)
                added += 1
        return added

    def current_wilderness_region_has_unknown_chunks(self) -> bool:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        profile = self.wilderness_region_profile(cx, cy)
        return any(not self.wilderness_chunk_known(x, y) for x, y in self.wilderness_region_chunks(cx, cy))

    def wilderness_region_mastery(self, chunk_x: int, chunk_y: int) -> Tuple[int, str]:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        state = getattr(self.state, "wilderness_poi_state", {})
        record = state.get(f"region:{profile['key']}", {}) if isinstance(state, dict) else {}
        count = len(record.get("completed_sites", []))
        if count >= 6:
            return count, "Naturalist"
        if count >= 3:
            return count, "Trailwise"
        if count >= 1:
            return count, "Surveyed"
        return count, "Unstudied"

    def wilderness_region_vitality(self, chunk_x: int, chunk_y: int) -> Tuple[int, str]:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        state = getattr(self.state, "wilderness_poi_state", {})
        region = state.get(f"region:{profile['key']}", {}) if isinstance(state, dict) else {}
        points = max(0, int(region.get("vitality_points", 0))) if isinstance(region, dict) else 0
        if points >= 100:
            return points, "Legendary"
        if points >= 50:
            return points, "Flourishing"
        if points >= 20:
            return points, "Stable"
        return points, "Recovering"

    def wilderness_region_vitality_benefits(self, chunk_x: int, chunk_y: int) -> Dict[str, int]:
        _points, level = self.wilderness_region_vitality(chunk_x, chunk_y)
        return {
            "Recovering": {"money": 0, "yield": 0},
            "Stable": {"money": 10, "yield": 0},
            "Flourishing": {"money": 25, "yield": 1},
            "Legendary": {"money": 45, "yield": 2},
        }[level]

    def add_wilderness_region_vitality(self, chunk_x: int, chunk_y: int, amount: int, reason: str) -> int:
        region = self.wilderness_region_record(chunk_x, chunk_y)
        before = max(0, int(region.get("vitality_points", 0)))
        region["vitality_points"] = before + max(0, int(amount))
        history = region.setdefault("vitality_history", [])
        history.append({"reason": str(reason), "points": max(0, int(amount)), "week": self.stronghold_cache_week_key()})
        region["vitality_history"] = history[-16:]
        if self.on_wilderness() and (int(chunk_x), int(chunk_y)) == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)):
            self.apply_wilderness_vitality_consequences_to_grid(self.active_map(), chunk_x, chunk_y)
        return int(region["vitality_points"])

    def apply_wilderness_vitality_consequences_to_grid(self, grid: List[List[str]], chunk_x: int, chunk_y: int):
        """Make regional health physically visible without adding valuable spawns."""
        if not grid or self.procedural_town_plan(chunk_x, chunk_y) or self.wilderness_chunk_has_stronghold(chunk_x, chunk_y) or self.owned_wilderness_claim(chunk_x, chunk_y):
            return
        points, _label = self.wilderness_region_vitality(chunk_x, chunk_y)
        wanted = []
        if points >= 20: wanted.append(WILDERNESS_REFUGE_SYMBOL)
        if points >= 50: wanted.append(WILDERNESS_STAFFED_SITE_SYMBOL)
        if points >= 100: wanted.append(WILDERNESS_EXCURSION_SYMBOL)
        if not wanted:
            return
        h, w = len(grid), len(grid[0])
        blocked = {"#", "~", "=", "S", "V", "X", "!", "T", "o", "*", "?", "R", "J", "P", "K", "Q", "A", "E", WILDERNESS_STRUCTURE_SYMBOL, WILDERNESS_DOCK_SYMBOL, WILDERNESS_FISHING_SETTLEMENT_SYMBOL, WILDERNESS_LANDSCAPE_SYMBOL}
        candidates = [(x, y) for y in range(5, h - 5) for x in range(7, w - 7) if grid[y][x] not in blocked and grid[y][x] in {".", ";", "%", "l", "r", "x", "`", '"', "[", ":"}]
        rng = random.Random(self.wilderness_chunk_seed(chunk_x, chunk_y) + 89400)
        rng.shuffle(candidates)
        used = set()
        for symbol in wanted:
            existing = next(((x, y) for y, row in enumerate(grid) for x, tile in enumerate(row) if tile == symbol), None)
            if existing:
                x, y = existing
                nearby_walls = sum(
                    grid[yy][xx] == "#"
                    for yy in range(max(1, y - 5), min(h - 1, y + 6))
                    for xx in range(max(1, x - 7), min(w - 1, x + 8))
                )
                if nearby_walls < 6:
                    kind = {WILDERNESS_REFUGE_SYMBOL: "refuge", WILDERNESS_STAFFED_SITE_SYMBOL: "staffed_site", WILDERNESS_EXCURSION_SYMBOL: "excursion"}[symbol]
                    self.stamp_wilderness_vitality_site(grid, x, y, kind, symbol)
                used.add(existing)
                continue
            position = next((point for point in candidates if all(abs(point[0] - px) + abs(point[1] - py) >= 12 for px, py in used)), None)
            if not position:
                continue
            x, y = position
            kind = {WILDERNESS_REFUGE_SYMBOL: "refuge", WILDERNESS_STAFFED_SITE_SYMBOL: "staffed_site", WILDERNESS_EXCURSION_SYMBOL: "excursion"}[symbol]
            self.stamp_wilderness_vitality_site(grid, x, y, kind, symbol)
            actual = next(((xx, yy) for yy, row in enumerate(grid) for xx, tile in enumerate(row) if tile == symbol), position)
            used.add(actual)

    def wilderness_vitality_consequence_at(self, x: int, y: int) -> str:
        if not self.on_wilderness(): return ""
        return {WILDERNESS_REFUGE_SYMBOL: "refuge", WILDERNESS_STAFFED_SITE_SYMBOL: "staffed_site", WILDERNESS_EXCURSION_SYMBOL: "excursion"}.get(self.active_map()[int(y)][int(x)], "")

    def wilderness_vitality_consequence_lines(self, kind: str) -> List[str]:
        points, label = self.wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        profile = {"refuge": ("Wildlife Refuge", "Protected habitat and observation blinds created by a stable region."), "staffed_site": ("Staffed Field Activity", "Rangers and researchers now maintain a regular public field presence."), "excursion": ("Public Excursion Site", "A legendary region now supports guided visits for households and travelers.")}.get(kind, ("Regional Improvement", "A visible consequence of regional stewardship."))
        return [profile[0].upper(), "", profile[1], "", f"Regional vitality: {label} ({points})", "This activity refreshes weekly and remains while the vitality threshold is met."]

    def use_wilderness_vitality_consequence(self, kind: str) -> bool:
        region = self.wilderness_region_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        week = self.stronghold_cache_week_key()
        key = f"consequence:{kind}:{week}"
        completed = region.setdefault("consequence_activities", [])
        if key in completed:
            self.set_message("You already participated in this regional activity this week.")
            return False
        stamina, minutes = {"refuge": (3, 25), "staffed_site": (4, 35), "excursion": (3, 45)}.get(kind, (3, 25))
        if not self.spend_stamina(stamina): return False
        self.advance_time(minutes)
        if kind == "refuge":
            self.state.money += 35
            message = "Completed a refuge wildlife count: +35g."
        elif kind == "staffed_site":
            add_inventory_items(self.state.inventory, {"Field Snack": 1, "Wild Herbs": 1})
            self.state.money += 45
            message = "Assisted the staffed field team: +45g, Field Snack, and Wild Herbs."
        else:
            before = int(self.state.stamina)
            self.restore_stamina(18)
            for follower_id in self.active_travel_follower_ids():
                self.adjust_travel_follower_bond(follower_id, 2)
            message = f"Joined a guided public excursion: +{int(self.state.stamina) - before} stamina and +2 active-follower bond."
        completed.append(key)
        region["consequence_activities"] = completed[-16:]
        self.autosave_with_message(message)
        return True

    def perform_wilderness_fieldwork(self, x: int, y: int, method: str = "survey") -> bool:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        poi = self.wilderness_poi_record(x, y, "field_site")
        week = self.stronghold_cache_week_key()
        if poi.get("last_work_week") == week:
            self.set_message("You already completed this field site this week.")
            return False
        project_level = self.wilderness_region_project_level(cx, cy)
        project_complete = project_level >= 1
        stamina_cost = 6 if project_level <= 0 else (4 if project_level == 1 else 3)
        if self.wilderness_climate_prepared(cx, cy): stamina_cost = max(1, stamina_cost - 1)
        if not self.spend_stamina(stamina_cost):
            return False
        self.advance_time(30)
        site = self.wilderness_field_site_type(cx, cy)
        drops = dict(site["drops"])
        region = self.wilderness_region_record(cx, cy)
        site_key = f"{cx},{cy}"
        completed = region.setdefault("completed_sites", [])
        first = site_key not in completed
        if first:
            completed.append(site_key)
            drops["Field Snack"] = drops.get("Field Snack", 0) + 1
        count = len(completed)
        follower_count = min(2, len(self.active_travel_follower_ids()))
        project = self.wilderness_region_project(cx, cy)
        seasonal_legacy = min(40, int(project.get("seasonal_cycles", 0)) * 5)
        vitality_benefits = self.wilderness_region_vitality_benefits(cx, cy)
        money = 30 + min(90, count * 10) + follower_count * 10 + max(0, project_level - 1) * 20 + seasonal_legacy + int(vitality_benefits["money"])
        if method == "restoration":
            money = max(20, money - 15)
            self.work_on_wilderness_region_project(cx, cy, fieldwork=True)
        elif method == "forage":
            money = max(15, money - 20)
            primary = next(iter(site["drops"]))
            drops[primary] = int(drops.get(primary, 0)) + 1 + min(2, project_level) + int(vitality_benefits["yield"])
        self.state.money += money
        add_inventory_items(self.state.inventory, drops)
        poi["last_work_week"] = week
        poi["times_completed"] = int(poi.get("times_completed", 0)) + 1
        region["fieldwork_count"] = int(region.get("fieldwork_count", 0)) + 1
        self.add_wilderness_region_vitality(cx, cy, 2 if method == "restoration" else 1, f"{method} fieldwork")
        suffix = " New regional discovery recorded." if first else ""
        follower_text = f" {follower_count} follower{'s' if follower_count != 1 else ''} assisted." if follower_count else ""
        self.autosave_with_message(f"Completed {site['name']} {method} work: +{money}g and {format_drops(drops)}.{suffix}{follower_text}")
        return True

    def wilderness_phenomenon_profile(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        biome = self.wilderness_region_profile(chunk_x, chunk_y)["biome"]
        variants = {
            ";": [
                {"name": "Abandoned Bee Skeps", "story": "Wild bees have occupied a row of collapsed old skeps.", "action": "repair the shelter without disturbing the swarm", "materials": {"Wood": 2, "Fiber": 2}, "study": {"Wildflowers": 1}, "help": {"Wild Honey": 2}},
                {"name": "Nesting Ground", "story": "Ground-nesting birds have settled directly across an old footpath.", "action": "mark a quiet detour around the nests", "materials": {"Wood": 2, "Fiber": 1}, "study": {"Feather": 1}, "help": {"Mixed Seeds": 2, "Feather": 2}},
            ],
            "%": [
                {"name": "Storm-Felled Grove", "story": "A recent storm has tangled several young trees beneath deadfall.", "action": "free the saplings and stack the usable timber", "materials": {"Fiber": 2}, "study": {"Acorn": 2}, "help": {"Wood": 4, "Pine Nuts": 1}},
                {"name": "Hidden Game Trail", "story": "Fresh tracks converge on a narrow, nearly invisible animal trail.", "action": "remove old wire and leave the passage safe", "materials": {"Fiber": 1}, "study": {"Wild Herbs": 1}, "help": {"Fiber": 3, "Wild Herbs": 2}},
            ],
            "l": [
                {"name": "Spore Bloom", "story": "A rare fruiting bloom has appeared around a rotting nurse log.", "action": "stabilize the damp log and collect a careful sample", "materials": {"Wood": 1, "Clay": 1}, "study": {"Mushrooms": 1}, "help": {"Strange Spores": 2, "Morel": 1}},
                {"name": "Fairy Ring", "story": "An unusually perfect ring of mushrooms surrounds untouched moss.", "action": "redirect the trail before boots destroy the ring", "materials": {"Stone": 2}, "study": {"Mushrooms": 2}, "help": {"Strange Spores": 1, "Wild Herbs": 2}},
            ],
            "r": [
                {"name": "Stranded Waterfowl Nest", "story": "Rising water has isolated a nest on a crumbling reed shelf.", "action": "brace the shelf above the waterline", "materials": {"Wood": 2, "Marsh Reed": 2}, "study": {"Feather": 1}, "help": {"Feather": 3, "Bird Egg": 1}},
                {"name": "Blocked Spring Channel", "story": "Silt and storm debris are choking a clear feeder stream.", "action": "open the channel and reinforce its banks", "materials": {"Stone": 2, "Marsh Reed": 2}, "study": {"Watercress": 1}, "help": {"Clay": 2, "Watercress": 2}},
            ],
            "x": [
                {"name": "Fallen Waystone", "story": "A carved route stone lies face-down beneath loose scree.", "action": "raise and brace the old marker", "materials": {"Stone": 3, "Wood": 1}, "study": {"Ruin Scrap": 1}, "help": {"Ruin Scrap": 2, "Coal": 1}},
                {"name": "Exposed Fossil Bed", "story": "Rain has exposed delicate impressions in a shale ledge.", "action": "shore up the ledge and recover loose fragments", "materials": {"Wood": 2, "Stone": 2}, "study": {"Stone": 2}, "help": {"Quartz": 1, "Stone": 3}},
            ],
        }.get(biome, [])
        if not variants:
            return {"name": "Unusual Tracks", "story": "Unfamiliar tracks cross the site.", "action": "mark and study the trail", "materials": {"Fiber": 1}, "study": {"Wild Herbs": 1}, "help": {"Wild Herbs": 2}}
        index = int(self.wilderness_hash01(chunk_x, chunk_y, 88110) * len(variants)) % len(variants)
        return variants[index]

    def wilderness_phenomenon_lines(self, x: int, y: int) -> List[str]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        profile = self.wilderness_phenomenon_profile(cx, cy)
        record = self.wilderness_poi_record(x, y, "phenomenon")
        material_text = ", ".join(f"{qty} {item}" for item, qty in profile["materials"].items())
        rows = [str(profile["name"]).upper(), "", str(profile["story"]), ""]
        if record.get("resolved"):
            rows.extend([f"Resolved by: {record.get('resolution', 'field study')}", "Your decision has become part of this region's field record."])
        else:
            rows.extend(["Document: 3 stamina, 20 minutes; modest research reward.", f"Intervene: 7 stamina, 35 minutes, and {material_text}.", f"Intervention: {profile['action']}."])
        return rows

    def resolve_wilderness_phenomenon(self, x: int, y: int, method: str) -> bool:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        profile = self.wilderness_phenomenon_profile(cx, cy)
        record = self.wilderness_poi_record(x, y, "phenomenon")
        if record.get("resolved"):
            self.set_message(f"You already resolved {profile['name']}.")
            return False
        if method == "intervene":
            missing = [f"{qty} {item}" for item, qty in profile["materials"].items() if int(self.state.inventory.get(item, 0)) < int(qty)]
            if missing:
                self.set_message("Intervention needs " + ", ".join(missing) + ".")
                return False
            preserve_bonus = 1 if self.wilderness_region_project_level(cx, cy) >= 3 else 0
            if not self.spend_stamina(max(3, 7 - min(2, len(self.active_travel_follower_ids())) - preserve_bonus)):
                return False
            for item, qty in profile["materials"].items():
                self.state.inventory[item] -= int(qty)
            self.advance_time(35)
            drops, money = dict(profile["help"]), 90
            resolution = "active stewardship"
            self.work_on_wilderness_region_project(cx, cy, fieldwork=True)
        else:
            if not self.spend_stamina(3):
                return False
            self.advance_time(20)
            drops, money = dict(profile["study"]), 35
            resolution = "careful documentation"
        add_inventory_items(self.state.inventory, drops)
        self.state.money += money
        record["resolved"] = True
        record["resolution"] = resolution
        record["season"] = str(self.state.season)
        region = self.wilderness_region_record(cx, cy)
        region["phenomena_resolved"] = int(region.get("phenomena_resolved", 0)) + 1
        self.add_wilderness_region_vitality(cx, cy, 5 if method == "intervene" else 2, str(profile["name"]))
        self.autosave_with_message(f"Resolved {profile['name']} through {resolution}: +{money}g and {format_drops(drops)}.")
        return True

    def show_wilderness_phenomenon(self, x: int, y: int):
        profile = self.wilderness_phenomenon_profile(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        if self.wilderness_poi_record(x, y, "phenomenon").get("resolved"):
            self.vertical_panel_view(str(profile["name"]), self.wilderness_phenomenon_lines(x, y), 50, 22)
            return
        items = [
            self._wilderness_menu_item("study", "Document carefully", "Spend 3 stamina and 20 minutes for a safe research reward."),
            self._wilderness_menu_item("intervene", "Actively intervene", "Spend materials and effort for a stronger stewardship outcome."),
            self._wilderness_menu_item("notes", "Assess the situation", "Review the discovery and intervention requirements."),
        ]
        while True:
            choice = self.vertical_panel_select(str(profile["name"]), items, 50, 23, return_back=True)
            if not choice:
                return
            if choice.value in {"study", "intervene"}:
                self.resolve_wilderness_phenomenon(x, y, choice.value)
                return
            self.vertical_panel_view(str(profile["name"]), self.wilderness_phenomenon_lines(x, y), 50, 23)

    def wilderness_weekly_event_profile(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        region = self.wilderness_region_profile(chunk_x, chunk_y)
        biome = region["biome"]
        pools = {
            ";": [("Mass Wildflower Bloom", "map the bloom before weather scatters it", {"Wildflowers": 2}), ("Migrating Herd", "protect a quiet crossing through the grassland", {"Wild Herbs": 2})],
            "%": [("Windfall Week", "clear fresh deadfall from animal passages", {"Wood": 3}), ("Canopy Nesting Rush", "mark nesting trees and redirect trail traffic", {"Pine Nuts": 2})],
            "l": [("Fruiting Surge", "record a sudden region-wide fungal bloom", {"Mushrooms": 3}), ("Mosswater Rise", "trace new springwater through the hollow", {"Strange Spores": 1})],
            "r": [("High-Water Pulse", "inspect flooded banks and reinforce safe channels", {"Marsh Reed": 3}), ("Waterfowl Arrival", "establish quiet observation lanes", {"Feather": 2})],
            "x": [("Fresh Rockfall", "reopen marked routes after a minor slide", {"Stone": 3}), ("Mineral Exposure", "document newly exposed seams without stripping them", {"Coal": 2})],
            "`": [("Sandstorm Drifts", "clear windblown crossings and remark the desert route", {"Clay": 3}), ("Desert Bloom", "map a brief flowering pulse around seasonal water", {"Wildflowers": 2})],
            '"': [("Whiteout Drifts", "reopen snow markers after a whiteout", {"Fiber": 3}), ("Tundra Herd Passage", "protect a broad migration lane across the frozen heath", {"Winter Root": 2})],
            "[": [("King Tide", "inspect flooded landings and remark safe channels", {"Marsh Reed": 3}), ("Seabird Gathering", "protect nesting islands from route traffic", {"Feather": 2})],
        }.get(biome, [("Changing Trails", "survey this week's changing wilderness routes", {"Wild Herbs": 2})])
        week_score = sum(ord(ch) for ch in self.stronghold_cache_week_key())
        index = (int(region["rx"]) * 7 + int(region["ry"]) * 13 + week_score) % len(pools)
        name, action, drops = pools[index]
        material_pool = {";": "Fiber", "%": "Wood", "l": "Clay", "r": "Marsh Reed", "x": "Stone", "`": "Clay", '"': "Fiber", "[": "Marsh Reed"}
        return {"name": name, "action": action, "drops": drops, "material": material_pool.get(biome, "Fiber"), "week": self.stronghold_cache_week_key()}

    def wilderness_weekly_event_lines(self, chunk_x: int, chunk_y: int) -> List[str]:
        region = self.wilderness_region_profile(chunk_x, chunk_y)
        event = self.wilderness_weekly_event_profile(chunk_x, chunk_y)
        record = self.wilderness_region_record(chunk_x, chunk_y)
        points, vitality = self.wilderness_region_vitality(chunk_x, chunk_y)
        rows = [str(event["name"]).upper(), "", f"Region: {region['name']}", f"Current vitality: {vitality} ({points})", "", str(event["action"]).capitalize() + ".", ""]
        if record.get("last_event_week") == event["week"]:
            rows.extend(["This week's event response is complete.", f"Response: {record.get('last_event_response', 'field observation')}"])
        else:
            rows.extend(["Observe: 3 stamina, 20 minutes, +2 vitality.", f"Respond: 6 stamina, 35 minutes, 2 {event['material']}, +5 vitality.", "A new regional event rotates in next week."])
        return rows

    def resolve_wilderness_weekly_event(self, chunk_x: int, chunk_y: int, method: str) -> bool:
        event = self.wilderness_weekly_event_profile(chunk_x, chunk_y)
        region = self.wilderness_region_record(chunk_x, chunk_y)
        if region.get("last_event_week") == event["week"]:
            self.set_message("This region's weekly environmental event is already complete.")
            return False
        followers = min(2, len(self.active_travel_follower_ids()) + (1 if self.wilderness_climate_prepared(chunk_x, chunk_y) else 0))
        drops = dict(event["drops"])
        if method == "respond":
            material = str(event["material"])
            if int(self.state.inventory.get(material, 0)) < 2:
                self.set_message(f"Active response requires 2 {material}.")
                return False
            if not self.spend_stamina(max(3, 6 - followers)):
                return False
            self.state.inventory[material] -= 2
            self.advance_time(max(20, 35 - followers * 5))
            primary = next(iter(drops))
            drops[primary] = int(drops[primary]) + 2
            money, vitality_gain, response = 90 + followers * 15, 5, "active ecological response"
            self.work_on_wilderness_region_project(chunk_x, chunk_y, fieldwork=True)
        else:
            if not self.spend_stamina(3):
                return False
            self.advance_time(20)
            money, vitality_gain, response = 45, 2, "careful field observation"
        add_inventory_items(self.state.inventory, drops)
        self.state.money += money
        self.add_wilderness_region_vitality(chunk_x, chunk_y, vitality_gain, str(event["name"]))
        region["last_event_week"] = event["week"]
        region["last_event_response"] = response
        history = region.setdefault("event_history", [])
        history.append({"name": event["name"], "response": response, "week": event["week"]})
        region["event_history"] = history[-12:]
        self.autosave_with_message(f"Completed {event['name']} through {response}: +{money}g, +{vitality_gain} vitality, and {format_drops(drops)}.")
        return True

    def show_wilderness_weekly_event(self, x: int, y: int):
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        event = self.wilderness_weekly_event_profile(cx, cy)
        region = self.wilderness_region_record(cx, cy)
        items = [self._wilderness_menu_item("status", "Review environmental event", "Read the current regional situation and response options.")]
        if region.get("last_event_week") != event["week"]:
            items.extend([
                self._wilderness_menu_item("observe", "Observe and document", "Use little energy for modest vitality and rewards."),
                self._wilderness_menu_item("respond", "Organize active response", "Spend regional materials for greater ecological progress."),
            ])
        choice = self.vertical_panel_select(str(event["name"]), items, 52, 23, return_back=True)
        if not choice:
            return
        if choice.value == "status":
            self.vertical_panel_view(str(event["name"]), self.wilderness_weekly_event_lines(cx, cy), 52, 23)
        elif choice.value in {"observe", "respond"}:
            self.resolve_wilderness_weekly_event(cx, cy, choice.value)

    def wilderness_event_visual_lookup(
        self,
        chunk_x: int = None,
        chunk_y: int = None,
        grid: List[List[str]] = None,
    ) -> Dict[Tuple[int, int], Dict[str, object]]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        if not self.on_wilderness() or self.procedural_town_plan(cx, cy) or self.wilderness_chunk_has_stronghold(cx, cy) or self.wilderness_chunk_has_structure(cx, cy) or self.owned_wilderness_claim(cx, cy):
            return {}
        cache_key = f"{cx},{cy}:{self.stronghold_cache_week_key()}"
        cache = getattr(self, "_wilderness_event_visual_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_event_visual_cache = cache
        if cache_key in cache:
            return cache[cache_key]
        if grid is None:
            grid = self.active_map() if (cx, cy) == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)) else self.wilderness_stream_map(cx, cy)
        if not grid:
            return {}
        event = self.wilderness_weekly_event_profile(cx, cy)
        name = str(event["name"])
        visual_profiles = {
            "Mass Wildflower Bloom": ('"', "blooming wildflowers", "crop"),
            "Migrating Herd": ("'", "fresh migration tracks", "wood"),
            "Windfall Week": ("/", "storm-fallen branches", "wood"),
            "Canopy Nesting Rush": ("v", "active nesting canopy", "crop"),
            "Fruiting Surge": ("*", "dense fruiting fungi", "magic"),
            "Mosswater Rise": ("'", "moss-bright springwater", "water"),
            "High-Water Pulse": ("~", "temporary floodwater", "water"),
            "Waterfowl Arrival": ("v", "waterfowl gathering ground", "crop"),
            "Fresh Rockfall": ("%", "fresh rockfall debris", "stone"),
            "Mineral Exposure": (";", "glinting exposed strata", "stone"),
            "Sandstorm Drifts": ("~", "windblown sand drifts", "stone"),
            "Desert Bloom": ('"', "brief desert wildflowers", "crop"),
            "Whiteout Drifts": ("%", "deep wind-packed snow", "water"),
            "Tundra Herd Passage": ("'", "fresh tundra migration tracks", "wood"),
            "King Tide": ("~", "temporary saltwater flooding", "water"),
            "Seabird Gathering": ("v", "dense seabird nesting grounds", "crop"),
        }
        symbol, description, color = visual_profiles.get(name, ("'", "signs of this week's environmental change", "crop"))
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        region_record = self.wilderness_region_record(cx, cy)
        cleared = set(str(value) for value in region_record.get("cleared_event_tiles", []) if str(value).startswith(f"{self.stronghold_cache_week_key()}:") )
        allowed = set([".", ";", "%", "l", "r", "x", "`", '"', "[", ":", "^"])
        for y in range(2, len(grid) - 2):
            for x in range(2, len(grid[0]) - 2):
                if grid[y][x] not in allowed:
                    continue
                wx, wy = self.wilderness_world_coords(cx, cy, x, y)
                field = self.wilderness_value_noise(wx + 7300, wy - 5100, 22.0, 88310)
                detail = self.wilderness_hash01(wx, wy, 88311)
                if field > 0.66 and detail > 0.72:
                    point_key = f"{self.stronghold_cache_week_key()}:{x},{y}"
                    if point_key in cleared:
                        continue
                    blocking = name in {"Fresh Rockfall", "High-Water Pulse", "Sandstorm Drifts", "Whiteout Drifts", "King Tide"} and grid[y][x] != ":"
                    lookup[(x, y)] = {"symbol": symbol, "description": description, "color": color, "event": name, "blocking": blocking, "point_key": point_key}
        cache[cache_key] = lookup
        if len(cache) > 12:
            for old_key in list(cache)[:-12]:
                cache.pop(old_key, None)
        return lookup

    def wilderness_event_visual_at(self, x: int, y: int) -> Dict[str, object]:
        signature = f"{int(self.state.wilderness_chunk_x)},{int(self.state.wilderness_chunk_y)}:{self.stronghold_cache_week_key()}"
        if getattr(self, "_active_wilderness_event_visual_signature", "") != signature:
            self.prepare_wilderness_runtime_overlays()
        lookup = getattr(self, "_active_wilderness_event_visual_lookup", {})
        return lookup.get((int(x), int(y)), {}) if isinstance(lookup, dict) else {}

    def wilderness_event_blocking_at(self, x: int, y: int) -> bool:
        return bool(self.wilderness_event_visual_at(x, y).get("blocking", False))

    def interact_with_wilderness_event_feature(self, x: int, y: int) -> bool:
        visual = self.wilderness_event_visual_at(x, y)
        if not visual:
            return False
        event = str(visual.get("event", "Regional Event"))
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_record(cx, cy)
        if event in {"Sandstorm Drifts", "Whiteout Drifts"}:
            if not self.spend_stamina(4):
                return False
            self.advance_time(12)
            cleared = region.setdefault("cleared_event_tiles", [])
            cleared.append(str(visual.get("point_key", f"{self.stronghold_cache_week_key()}:{x},{y}")))
            region["cleared_event_tiles"] = list(dict.fromkeys(str(value) for value in cleared))[-40:]
            drops = {"Clay": 1} if event == "Sandstorm Drifts" else {"Fiber": 1}
            add_inventory_items(self.state.inventory, drops)
            self.add_wilderness_region_vitality(cx, cy, 1, f"cleared {event}")
            self._wilderness_event_visual_cache = {}
            self.prepare_wilderness_runtime_overlays()
            self.autosave_with_message(f"Cleared a route through the {event.lower()}: {format_drops(drops)} and +1 regional vitality.")
            return True
        if event == "Fresh Rockfall":
            if not self.owns_tool("Pickaxe"):
                self.set_message("Equip and own a Pickaxe to clear this temporary rockfall.")
                return False
            if not self.spend_stamina(5 if self.tool_level("Pickaxe") <= 1 else 3):
                return False
            self.advance_time(10)
            cleared = region.setdefault("cleared_event_tiles", [])
            cleared.append(str(visual.get("point_key", f"{self.stronghold_cache_week_key()}:{x},{y}")))
            region["cleared_event_tiles"] = list(dict.fromkeys(str(value) for value in cleared))[-40:]
            add_inventory_items(self.state.inventory, {"Stone": 1})
            self.add_wilderness_region_vitality(cx, cy, 1, "cleared temporary rockfall")
            self._wilderness_event_visual_cache = {}
            self.prepare_wilderness_runtime_overlays()
            self.autosave_with_message("Cleared part of the temporary rockfall: +1 Stone and +1 regional vitality.")
            return True
        if event == "High-Water Pulse":
            self.set_message("Temporary floodwater covers this low ground. Follow maintained trails or wait for next week's conditions.")
            return False
        if event in {"Mass Wildflower Bloom", "Fruiting Surge", "Desert Bloom"}:
            week = self.stronghold_cache_week_key()
            if region.get("event_sample_week") == week:
                self.set_message("You already collected this region's event sample this week.")
                return False
            if not self.spend_stamina(2):
                return False
            self.advance_time(10)
            drops = {"Wildflowers": 2} if event in {"Mass Wildflower Bloom", "Desert Bloom"} else {"Mushrooms": 2, "Strange Spores": 1}
            add_inventory_items(self.state.inventory, drops)
            region["event_sample_week"] = week
            self.add_wilderness_region_vitality(cx, cy, 1, f"sampled {event}")
            self.autosave_with_message(f"Collected a careful {event.lower()} sample: {format_drops(drops)}.")
            return True
        self.set_message(f"You examine the {str(visual.get('description', 'environmental change'))} and note it in the regional record.")
        return True

    def wilderness_seasonal_surface_lookup(
        self,
        chunk_x: int = None,
        chunk_y: int = None,
        grid: List[List[str]] = None,
    ) -> Dict[Tuple[int, int], Dict[str, object]]:
        """Deterministic daily surface changes layered over persistent terrain."""
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        if not self.on_wilderness():
            return {}
        cache_key = (
            f"{cx},{cy}:{self.errand_day_key()}:{self.state.weather}:"
            f"{self.state.season}"
        )
        cache = getattr(self, "_wilderness_seasonal_surface_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_seasonal_surface_cache = cache
        if cache_key in cache:
            return cache[cache_key]
        if grid is None:
            grid = (
                self.active_map()
                if (cx, cy) == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y))
                else self.wilderness_stream_map(cx, cy)
            )
        if not grid:
            return {}
        region = self.wilderness_region_record(cx, cy)
        day_key = self.errand_day_key()
        cleared = {
            str(value)
            for value in region.get("cleared_seasonal_tiles", [])
            if str(value).startswith(f"{day_key}:")
        }
        season = str(self.state.season)
        weather = str(self.state.weather)
        month, day = int(self.state.month), int(self.state.day)
        ground = {".", ";", "%", "l", "r", "x", "`", '"', "[", "^"}
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}

        if month == 12:
            snow_amount = min(1.0, 0.15 + day / 40.0)
        elif month == 1:
            snow_amount = min(1.0, 0.55 + day / 65.0)
        elif month == 2:
            snow_amount = max(0.12, 0.85 - day / 38.0)
        else:
            snow_amount = 0.0

        for y in range(1, len(grid) - 1):
            for x in range(1, len(grid[0]) - 1):
                tile = str(grid[y][x])
                wx, wy = self.wilderness_world_coords(cx, cy, x, y)
                kind = ""
                symbol = "'"
                description = ""
                color = "crop"
                blocking = False

                if tile == "~" and self.wilderness_world_biome_tile(wx, wy) != "[":
                    if season == "Winter" and month == 2 and day >= 20:
                        kind, symbol, description, color = "cracking_ice", "~", "late-winter ice crossed by dark thaw cracks", "water"
                    elif season == "Spring" and month == 3 and day <= 10:
                        kind, symbol, description, color = "ice_floes", "~", "last pale ice floes drifting on newly open freshwater", "water"
                elif tile in ground and tile not in {":", "="}:
                    storm_roll = self.wilderness_hash01(wx, wy, 99101)
                    seasonal_roll = self.wilderness_hash01(wx, wy, 99102)
                    detail_roll = self.wilderness_hash01(wx, wy, 99103)
                    if weather in {"Storm", "Stormy"} and storm_roll < 0.007:
                        kind, symbol, description, color = "storm_debris", "/", "fresh branches and storm debris scattered across the ground", "wood"
                        blocking = True
                    elif season == "Winter" and seasonal_roll < 0.006 + snow_amount * 0.012:
                        kind, symbol, description, color = "snow_drift", "%", "a wind-shaped drift left by accumulating winter snow", "water"
                        blocking = weather == "Blizzard" and detail_roll < 0.55
                    elif season == "Spring" and tile == "r" and weather in {"Rain", "Rainy", "Storm", "Stormy"} and seasonal_roll < 0.045:
                        kind, symbol, description, color = "spring_high_water", "~", "seasonal high water spreading across low wetland ground", "water"
                        blocking = True
                    elif season == "Spring" and tile in {".", ";", "%"} and seasonal_roll < 0.012:
                        kind, symbol, description, color = "spring_bloom", '"', "a small spring bloom rooted in the warming ground", "crop"
                    elif season == "Fall" and tile in {".", ";", "%", "l"} and seasonal_roll < 0.016:
                        kind, symbol, description, color = "autumn_leaves", "L", "a fresh layer of fallen autumn leaves", "wood"

                if not kind:
                    continue
                point_key = f"{day_key}:{kind}:{x},{y}"
                if point_key in cleared:
                    continue
                lookup[(x, y)] = {
                    "kind": kind, "symbol": symbol, "description": description,
                    "color": color, "blocking": blocking, "point_key": point_key,
                }
        cache[cache_key] = lookup
        if len(cache) > 16:
            for old_key in list(cache)[:-16]:
                cache.pop(old_key, None)
        return lookup

    def wilderness_seasonal_surface_at(self, x: int, y: int) -> Dict[str, object]:
        signature = (
            f"{int(self.state.wilderness_chunk_x)},{int(self.state.wilderness_chunk_y)}:"
            f"{self.errand_day_key()}:{self.state.weather}:{self.state.season}"
        )
        if getattr(self, "_active_wilderness_seasonal_surface_signature", "") != signature:
            self.prepare_wilderness_runtime_overlays()
        if (int(x), int(y)) in getattr(self, "_active_wilderness_event_visual_lookup", {}):
            return {}
        lookup = getattr(self, "_active_wilderness_seasonal_surface_lookup", {})
        return lookup.get((int(x), int(y)), {}) if isinstance(lookup, dict) else {}

    def wilderness_seasonal_surface_blocking_at(self, x: int, y: int) -> bool:
        return bool(self.wilderness_seasonal_surface_at(x, y).get("blocking", False))

    def clear_wilderness_seasonal_surface(self, visual: Dict[str, object]) -> None:
        region = self.wilderness_region_record(
            int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        )
        cleared = region.setdefault("cleared_seasonal_tiles", [])
        cleared.append(str(visual.get("point_key", "")))
        region["cleared_seasonal_tiles"] = list(dict.fromkeys(str(value) for value in cleared if value))[-80:]
        self._wilderness_seasonal_surface_cache = {}
        self.prepare_wilderness_runtime_overlays()

    def interact_with_wilderness_seasonal_surface(self, x: int, y: int) -> bool:
        visual = self.wilderness_seasonal_surface_at(x, y)
        if not visual:
            return False
        kind = str(visual.get("kind", ""))
        if kind in {"cracking_ice", "ice_floes"}:
            self.set_message(
                "The freshwater ice is visibly breaking apart; the seasonal crossing is changing back into open water."
            )
            return True
        if kind == "spring_high_water":
            self.set_message("Spring high water covers this low ground. Use roads or higher terrain until it recedes.")
            return True
        cost, minutes, drops, vitality = 1, 5, {}, 0
        if kind == "spring_bloom":
            drops = {"Wildflowers": 1}
        elif kind == "autumn_leaves":
            drops = {"Fiber": 1}
        elif kind == "snow_drift":
            cost, minutes, vitality = 2, 10, 1
        elif kind == "storm_debris":
            cost = 2 if self.owns_tool("Axe") else 4
            minutes, drops, vitality = 12, {"Wood": 1}, 1
        if not self.spend_stamina(cost):
            return False
        self.advance_time(minutes)
        add_inventory_items(self.state.inventory, drops)
        if vitality:
            self.add_wilderness_region_vitality(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y), vitality,
                f"cleared {kind.replace('_', ' ')}",
            )
        self.clear_wilderness_seasonal_surface(visual)
        reward = f": {format_drops(drops)}" if drops else ""
        self.autosave_with_message(
            f"Cleared {str(visual.get('description', kind)).lower()}{reward}."
        )
        return True

    def wilderness_expedition_camp_position(
        self,
        chunk_x: int = None,
        chunk_y: int = None,
        grid: List[List[str]] = None,
    ) -> Tuple[int, int]:
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        if not self.on_wilderness() or not self.active_wilderness_expedition_for_chunk(cx, cy):
            return (-1, -1)
        expedition = self.active_wilderness_expedition_for_chunk(cx, cy)
        cache_key = str(expedition.get("id", ""))
        cache = getattr(self, "_wilderness_expedition_camp_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_expedition_camp_cache = cache
        if cache_key in cache:
            return tuple(cache[cache_key])
        if grid is None:
            grid = self.active_map() if (cx, cy) == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)) else self.wilderness_stream_map(cx, cy)
        if not grid:
            return (-1, -1)
        objectives = set(self.wilderness_expedition_objective_positions(cx, cy, grid))
        candidates = [(x, y) for y in range(5, len(grid) - 5) for x in range(7, len(grid[0]) - 7) if grid[y][x] in {".", ";", "%", "l", "r", "x", "`", '"', "[", ":"} and (x, y) not in objectives]
        rng = random.Random(self.wilderness_chunk_seed(cx, cy) + 88680)
        position = rng.choice(candidates) if candidates else (len(grid[0]) // 2, len(grid) // 2)
        cache[cache_key] = position
        return position

    def wilderness_expedition_camp_at(self, x: int, y: int) -> Dict[str, object]:
        expedition = self.active_wilderness_expedition_for_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y) if self.on_wilderness() else {}
        return expedition if expedition and self.wilderness_expedition_camp_position() == (int(x), int(y)) else {}

    def rest_at_wilderness_expedition_camp(self) -> bool:
        expedition = self.active_wilderness_expedition_for_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        if not expedition:
            return False
        day = self.errand_day_key()
        if expedition.get("camp_rest_day") == day:
            self.set_message("You already rested at the expedition tent today.")
            return False
        before = int(self.state.stamina)
        self.restore_stamina(22)
        self.advance_time(20)
        expedition["camp_rest_day"] = day
        self.autosave_with_message(f"Rested at the expedition tent: +{int(self.state.stamina) - before} stamina.")
        return True

    def claim_wilderness_expedition_camp_supplies(self) -> bool:
        expedition = self.active_wilderness_expedition_for_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        if not expedition:
            return False
        if expedition.get("camp_supplies_claimed"):
            self.set_message("You already collected this expedition's tent supplies.")
            return False
        drops = {"Field Snack": 1, "Fiber": 1}
        add_inventory_items(self.state.inventory, drops)
        expedition["camp_supplies_claimed"] = True
        self.autosave_with_message(f"Collected expedition tent supplies: {format_drops(drops)}.")
        return True

    def show_wilderness_expedition_camp(self):
        expedition = self.active_wilderness_expedition_for_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        items = [
            self._wilderness_menu_item("briefing", "Review expedition briefing", "Review the objective and physical survey progress."),
            self._wilderness_menu_item("rest", "Rest at ranger tent", "Recover 22 stamina once per day."),
            self._wilderness_menu_item("supplies", "Check expedition supplies", "Collect the one-time field ration cache."),
        ]
        choice = self.vertical_panel_select("Temporary Ranger Camp", items, 50, 22, return_back=True)
        if not choice:
            return
        if choice.value == "briefing":
            self.vertical_panel_view("Expedition Briefing", self.wilderness_expedition_lines(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y), 52, 24)
        elif choice.value == "rest":
            self.rest_at_wilderness_expedition_camp()
        elif choice.value == "supplies":
            self.claim_wilderness_expedition_camp_supplies()

    def prepare_wilderness_runtime_overlays(self):
        if not self.on_wilderness():
            self._active_wilderness_event_visual_lookup = {}
            self._active_wilderness_seasonal_surface_lookup = {}
            self._active_wilderness_expedition_objective_lookup = {}
            self._active_wilderness_expedition_camp_position = (-1, -1)
            self._active_wilderness_event_visual_signature = ""
            self._active_wilderness_seasonal_surface_signature = ""
            return
        self._active_wilderness_event_visual_lookup = self.wilderness_event_visual_lookup()
        self._active_wilderness_seasonal_surface_lookup = self.wilderness_seasonal_surface_lookup()
        objective_lookup = {}
        for x, y in self.wilderness_expedition_objective_positions():
            objective = self.wilderness_expedition_objective_at(x, y)
            if objective:
                objective_lookup[(x, y)] = objective
        self._active_wilderness_expedition_objective_lookup = objective_lookup
        self._active_wilderness_expedition_camp_position = self.wilderness_expedition_camp_position()
        self._active_wilderness_event_visual_signature = f"{int(self.state.wilderness_chunk_x)},{int(self.state.wilderness_chunk_y)}:{self.stronghold_cache_week_key()}"
        self._active_wilderness_seasonal_surface_signature = (
            f"{int(self.state.wilderness_chunk_x)},{int(self.state.wilderness_chunk_y)}:"
            f"{self.errand_day_key()}:{self.state.weather}:{self.state.season}"
        )

    def wilderness_expedition_objective_visual_at(self, x: int, y: int) -> Dict[str, object]:
        lookup = getattr(self, "_active_wilderness_expedition_objective_lookup", {})
        return lookup.get((int(x), int(y)), {}) if isinstance(lookup, dict) else {}

    def wilderness_expedition_camp_visual_at(self, x: int, y: int) -> bool:
        return tuple(getattr(self, "_active_wilderness_expedition_camp_position", (-1, -1))) == (int(x), int(y))

    def ensure_wilderness_travelers(self):
        if not isinstance(getattr(self, "_wilderness_travelers", None), dict):
            self._wilderness_travelers = {}

    def wilderness_traveler_cache_key(self, chunk_x: int, chunk_y: int) -> str:
        hour = max(0, min(23, int(getattr(self.state, "hour", 12) or 0)))
        schedule_band = "home" if hour < 8 or hour >= 18 else ("commute" if hour < 9 or hour >= 17 else "work")
        return f"{int(chunk_x)},{int(chunk_y)}:{self.stronghold_cache_week_key()}:{self.errand_day_key()}:{schedule_band}"

    def recurring_wilderness_traveler_record(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        region = self.wilderness_region_record(chunk_x, chunk_y)
        record = region.get("recurring_traveler")
        if not isinstance(record, dict):
            biome = str(self.wilderness_region_profile(chunk_x, chunk_y).get("biome", ";"))
            role = {";": "Herbalist", "%": "Woodward", "l": "Mycologist", "r": "Wetland Warden", "x": "Prospector", "`": "Desert Guide", '"': "Tundra Warden", "[": "Coast Pilot"}.get(biome, "Ranger")
            rx, ry = self.wilderness_region_coords(chunk_x, chunk_y)
            rng = random.Random(self.wilderness_chunk_seed(rx, ry) + 88450)
            name = f"{rng.choice(['Alden', 'Briar', 'Corin', 'Della', 'Emery', 'Fern', 'Galen', 'Hollis', 'Iona', 'Jory', 'Kit', 'Linden'])} {rng.choice(['Ash', 'Brook', 'Fen', 'Morrow', 'Pike', 'Reed', 'Stone', 'Vale', 'Wren'])}"
            record = {"id": f"route:{self.wilderness_region_profile(chunk_x, chunk_y)['key']}", "name": name, "role": role, "bond": 0, "story_stage": 0, "memories": []}
            region["recurring_traveler"] = record
        home_x, home_y = self.wilderness_region_outpost_chunk(chunk_x, chunk_y)
        record["home_chunk_x"] = int(home_x)
        record["home_chunk_y"] = int(home_y)
        record["home_name"] = self.wilderness_outpost_name(home_x, home_y)
        record["residence"] = f"a private bunk and workroom at {record['home_name']}"
        record.setdefault("bond", 0)
        record.setdefault("story_stage", 0)
        record.setdefault("memories", [])
        record.setdefault("field_lessons", 0)
        record.setdefault("samples_received", 0)
        return record

    def wilderness_specialist_schedule(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        """Return the one physical place occupied by a region's specialist.

        Specialists sleep and keep records at the regional outpost, commute at
        the edges of the workday, and visit one deterministic field tract at a
        time. This prevents the old same-person-in-every-chunk projection.
        """
        record = self.recurring_wilderness_traveler_record(chunk_x, chunk_y)
        home = (int(record["home_chunk_x"]), int(record["home_chunk_y"]))
        hour = max(0, min(23, int(getattr(self.state, "hour", 12) or 0)))
        weather = str(getattr(self.state, "weather", "Sunny") or "Sunny").lower()
        day_number = max(1, int(getattr(self.state, "day", 1) or 1))
        office_day = day_number % 7 in {2, 6}
        severe_weather = weather in {"stormy", "blizzard", "sandstorm", "whiteout"}
        candidates = [
            (int(cx), int(cy))
            for cx, cy in self.wilderness_region_chunks(chunk_x, chunk_y)
            if (int(cx), int(cy)) not in {home, (0, 0)}
            and not self.wilderness_chunk_has_procedural_settlement(cx, cy)
            and not self.wilderness_chunk_has_stronghold(cx, cy)
        ]
        if not candidates:
            candidates = [home]
        candidates.sort()
        identity_seed = sum((index + 1) * ord(char) for index, char in enumerate(str(record["id"])))
        day_seed = day_number + int(getattr(self.state, "year", 1) or 1) * 37 + identity_seed
        work_chunk = candidates[day_seed % len(candidates)]
        subhabitat = self.wilderness_subhabitat_profile(*work_chunk)

        if hour < 8 or hour >= 18 or office_day or severe_weather:
            reason = (
                "sheltering from dangerous weather and updating regional records"
                if severe_weather
                else "cataloguing samples and updating the regional field journal"
                if office_day and 8 <= hour < 18
                else "off duty at home"
            )
            return {
                "presence": "outpost",
                "chunk_x": home[0],
                "chunk_y": home[1],
                "activity": reason,
                "work_chunk_x": work_chunk[0],
                "work_chunk_y": work_chunk[1],
                "work_site": str(subhabitat.get("name", "regional field tract")),
                "hours": "Field days 9:00-17:00; records days and severe weather at the outpost",
            }
        if hour < 9 or hour >= 17:
            return {
                "presence": "wilderness",
                "chunk_x": home[0],
                "chunk_y": home[1],
                "activity": f"walking between {record['home_name']} and today's {str(subhabitat.get('name', 'field tract')).lower()}",
                "work_chunk_x": work_chunk[0],
                "work_chunk_y": work_chunk[1],
                "work_site": str(subhabitat.get("name", "regional field tract")),
                "hours": "Field days 9:00-17:00; records days and severe weather at the outpost",
            }
        return {
            "presence": "wilderness",
            "chunk_x": work_chunk[0],
            "chunk_y": work_chunk[1],
            "activity": f"conducting a repeat survey of {str(subhabitat.get('name', 'the local habitat'))}",
            "work_chunk_x": work_chunk[0],
            "work_chunk_y": work_chunk[1],
            "work_site": str(subhabitat.get("name", "regional field tract")),
            "hours": "Field days 9:00-17:00; records days and severe weather at the outpost",
        }

    def wilderness_specialist_actor(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        record = self.recurring_wilderness_traveler_record(chunk_x, chunk_y)
        schedule = self.wilderness_specialist_schedule(chunk_x, chunk_y)
        actor = dict(record)
        actor.update({
            "recurring": True,
            "scheduled_specialist": True,
            "activity": str(schedule["activity"]),
            "schedule": dict(schedule),
            "home_name": str(record["home_name"]),
            "residence": str(record["residence"]),
        })
        return actor

    def recurring_wilderness_traveler_bond_label(self, bond: int) -> str:
        if int(bond) >= 12: return "Trusted Trail Partner"
        if int(bond) >= 8: return "Route Companion"
        if int(bond) >= 4: return "Familiar Face"
        return "New Acquaintance"

    def wilderness_traveler_route_destination(
        self,
        chunk_x: int,
        chunk_y: int,
        identity: str,
        exclude_id: str = "",
    ) -> Dict[str, object]:
        """Choose a stable named destination from the purposeful road graph."""
        destinations = [
            node for node in self.wilderness_road_destinations_for_chunk(chunk_x, chunk_y)
            if str(node.get("id", "")) != str(exclude_id)
        ]
        if not destinations:
            return {}
        destinations.sort(key=lambda node: str(node.get("id", "")))
        identity_seed = sum((index + 1) * ord(char) for index, char in enumerate(str(identity)))
        index = int(self.wilderness_hash01(chunk_x + identity_seed, chunk_y - identity_seed, 88409) * len(destinations))
        return dict(destinations[min(len(destinations) - 1, index)])

    def assign_wilderness_traveler_route(
        self,
        traveler: Dict[str, object],
        chunk_x: int,
        chunk_y: int,
    ) -> None:
        destination = self.wilderness_traveler_route_destination(
            chunk_x, chunk_y, str(traveler.get("id", "traveler"))
        )
        if not destination:
            return
        traveler.update({
            "road_route": True,
            "route_destination_id": str(destination["id"]),
            "route_destination_name": str(destination["name"]),
            "route_destination_kind": str(destination["kind"]),
            "route_destination_chunk_x": int(destination["chunk_x"]),
            "route_destination_chunk_y": int(destination["chunk_y"]),
            "route_destination_world_x": int(destination["world_x"]),
            "route_destination_world_y": int(destination["world_y"]),
            "route_steps": 0,
            "activity": f"following the road toward {destination['name']}",
        })

    def wilderness_traveler_route_options(
        self,
        traveler: Dict[str, object],
        chunk_x: int,
        chunk_y: int,
        options: List[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        """Prefer connected road tiles that reduce distance to a named destination."""
        x, y = int(traveler.get("x", 0)), int(traveler.get("y", 0))
        target_world_x = int(traveler.get("route_destination_world_x", 0))
        target_world_y = int(traveler.get("route_destination_world_y", 0))
        fixed_local_path = {
            (int(point[0]), int(point[1]))
            for point in traveler.get("home_route_points", [])
            if isinstance(point, (list, tuple)) and len(point) >= 2
        }

        def score(step: Tuple[int, int]) -> Tuple[int, int, int]:
            destination_x, destination_y, local_x, local_y = self.wilderness_stream_resolve_from_chunk(
                chunk_x, chunk_y, x + step[0], y + step[1]
            )
            destination_grid = self.wilderness_stream_map(destination_x, destination_y)
            tile = destination_grid[local_y][local_x] if destination_grid else "#"
            next_world_x, next_world_y = self.wilderness_world_coords(destination_x, destination_y, local_x, local_y)
            fixed_route_penalty = (
                0
                if not fixed_local_path
                or ((destination_x, destination_y) == (0, 0) and (local_x, local_y) in fixed_local_path)
                else 4
            )
            return (
                fixed_route_penalty,
                0 if tile in {":", "="} else 3,
                abs(next_world_x - target_world_x) + abs(next_world_y - target_world_y),
            )

        return sorted(options, key=score)

    def generate_wilderness_travelers(self, chunk_x: int, chunk_y: int) -> List[Dict[str, object]]:
        if self.procedural_town_plan(chunk_x, chunk_y) or self.wilderness_chunk_has_stronghold(chunk_x, chunk_y):
            return []
        level = self.wilderness_region_project_level(chunk_x, chunk_y)
        vitality_points, vitality = self.wilderness_region_vitality(chunk_x, chunk_y)
        seed = self.wilderness_chunk_seed(chunk_x, chunk_y) + sum(ord(ch) for ch in self.stronghold_cache_week_key()) * 17 + 88400
        rng = random.Random(seed)
        has_regional_road = self.wilderness_chunk_has_regional_road(chunk_x, chunk_y)
        # Ordinary wilderness traffic is occasional. Regional specialists are
        # handled separately by their one-location daily schedule below.
        ordinary_chance = 0.08 + (0.20 if has_regional_road else 0.0)
        ordinary_chance += 0.04 if level >= 2 else 0.0
        ordinary_chance += 0.04 if vitality in {"Flourishing", "Legendary"} else 0.0
        ordinary_count = 1 if rng.random() < ordinary_chance else 0
        if ordinary_count and has_regional_road and rng.random() < 0.10:
            ordinary_count = 2
        biome = self.wilderness_region_profile(chunk_x, chunk_y)["biome"]
        roles = ["Courier", "Pilgrim", "Hunter"]
        roles.append({";": "Herbalist", "%": "Woodward", "l": "Mycologist", "r": "Wetland Warden", "x": "Prospector", "`": "Desert Guide", '"': "Tundra Warden", "[": "Coast Pilot"}.get(biome, "Traveler"))
        if level >= 2:
            roles.append("Trail Merchant")
        names = ["Alden", "Briar", "Corin", "Della", "Emery", "Fern", "Galen", "Hollis", "Iona", "Jory", "Kit", "Linden"]
        grid = self.wilderness_stream_map(chunk_x, chunk_y) or self.get_wilderness_chunk_map(chunk_x, chunk_y)
        blocked = {"#", "~", "=", "S", "V", "X", "!", "T", "o", "*", "?", "R", "J", "P", "K", "Q", "E", WILDERNESS_OUTPOST_SYMBOL, WILDERNESS_STRUCTURE_SYMBOL}
        candidates = [(x, y) for y in range(3, len(grid) - 3) for x in range(4, len(grid[0]) - 4) if grid[y][x] not in blocked]
        if (
            self.on_wilderness()
            and (int(chunk_x), int(chunk_y))
            == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y))
        ):
            candidates = [
                (x, y)
                for x, y in candidates
                if not self.wilderness_event_visual_at(x, y)
                and not self.wilderness_seasonal_surface_at(x, y)
                and not self.wilderness_expedition_objective_at(x, y)
                and not self.wilderness_expedition_camp_visual_at(x, y)
            ]
        rng.shuffle(candidates)
        road_candidates = []
        if has_regional_road:
            road_candidates = [
                (x, y) for x, y in candidates
                if grid[y][x] == ":" and self.wilderness_world_on_regional_road(
                    *self.wilderness_world_coords(chunk_x, chunk_y, x, y), chunk_x, chunk_y
                )
            ]
            rng.shuffle(road_candidates)
        travelers = []
        used = set()
        specialist_schedule = self.wilderness_specialist_schedule(chunk_x, chunk_y)
        specialist_here = (
            str(specialist_schedule.get("presence", "")) == "wilderness"
            and (int(specialist_schedule.get("chunk_x", 0)), int(specialist_schedule.get("chunk_y", 0)))
            == (int(chunk_x), int(chunk_y))
        )
        if specialist_here:
            preferred = (road_candidates or candidates) if 8 <= int(self.state.hour) < 9 or 17 <= int(self.state.hour) < 18 else candidates
            position = next(((x, y) for x, y in preferred if all(abs(x - ux) + abs(y - uy) >= 7 for ux, uy in used)), None)
            if position:
                x, y = position
                specialist = self.wilderness_specialist_actor(chunk_x, chunk_y)
                specialist.update({"x": x, "y": y, "anchor_x": x, "anchor_y": y, "vitality_seen": vitality_points})
                travelers.append(specialist)
                used.add(position)

        for index in range(ordinary_count):
            preferred = road_candidates if road_candidates else candidates
            position = next(((x, y) for x, y in preferred if all(abs(x - ux) + abs(y - uy) >= 7 for ux, uy in used)), None)
            if not position:
                break
            x, y = position
            role = roles[(index + int(rng.random() * len(roles))) % len(roles)]
            traveler = {
                "id": f"traveler:{chunk_x},{chunk_y}:{self.stronghold_cache_week_key()}:{index}",
                "name": rng.choice(names),
                "role": role,
                "x": x,
                "y": y,
                "anchor_x": x,
                "anchor_y": y,
                "activity": "walking the regional trails",
                "vitality_seen": vitality_points,
                "temporary_traveler": True,
            }
            if position in road_candidates:
                self.assign_wilderness_traveler_route(traveler, chunk_x, chunk_y)
            travelers.append(traveler)
            used.add(position)
        if has_regional_road and hasattr(self, "regional_circulation_travelers_for_chunk"):
            for traveler in self.regional_circulation_travelers_for_chunk(chunk_x, chunk_y):
                if any(str(existing.get("id", "")) == str(traveler.get("id", "")) for existing in travelers):
                    continue
                preferred = (int(traveler.get("preferred_x", -1)), int(traveler.get("preferred_y", -1)))
                local_road_candidates = []
                if traveler.get("home_region_commute"):
                    commute_path = {
                        (int(point[0]), int(point[1]))
                        for point in traveler.get("home_route_points", [])
                        if isinstance(point, (list, tuple)) and len(point) >= 2
                    }
                    local_road_candidates = sorted(
                        (
                            (x, y) for x, y in road_candidates
                            if (x, y) in commute_path
                        ),
                        key=lambda point: abs(point[0] - preferred[0]) + abs(point[1] - preferred[1]),
                    )
                position = (
                    preferred
                    if preferred in road_candidates
                    and all(abs(preferred[0] - ux) + abs(preferred[1] - uy) >= 3 for ux, uy in used)
                    else next(
                        (
                            (x, y) for x, y in (local_road_candidates or road_candidates)
                            if all(abs(x - ux) + abs(y - uy) >= (2 if traveler.get("home_region_commute") else 5) for ux, uy in used)
                        ),
                        None,
                    )
                )
                if not position:
                    continue
                x, y = position
                target_cx = int(traveler.get("route_destination_chunk_x", 0))
                target_cy = int(traveler.get("route_destination_chunk_y", 0))
                target_world_x = traveler.get("route_destination_world_x")
                target_world_y = traveler.get("route_destination_world_y")
                if target_world_x is None or target_world_y is None:
                    destination_id = str(traveler.get("route_destination_id", ""))
                    destination = next(
                        (
                            node for node in self.wilderness_road_destinations_for_chunk(target_cx, target_cy)
                            if str(node.get("id", "")) == destination_id
                        ),
                        {},
                    )
                    if destination:
                        target_world_x, target_world_y = int(destination["world_x"]), int(destination["world_y"])
                    else:
                        target_world_x, target_world_y = self.wilderness_world_coords(target_cx, target_cy, 43, 19)
                traveler.update({
                    "x": x, "y": y, "anchor_x": x, "anchor_y": y,
                    "route_destination_world_x": int(target_world_x),
                    "route_destination_world_y": int(target_world_y),
                    "route_steps": 0,
                })
                travelers.append(traveler)
                used.add(position)
        return travelers

    def get_wilderness_travelers_for_chunk(self, chunk_x: int, chunk_y: int) -> List[Dict[str, object]]:
        if not self.on_wilderness():
            return []
        self.ensure_wilderness_travelers()
        key = self.wilderness_traveler_cache_key(chunk_x, chunk_y)
        if key not in self._wilderness_travelers:
            self._wilderness_travelers[key] = self.generate_wilderness_travelers(chunk_x, chunk_y)
        return self._wilderness_travelers[key]

    def get_wilderness_travelers(self) -> List[Dict[str, object]]:
        return self.get_wilderness_travelers_for_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)

    def wilderness_traveler_at(self, x: int, y: int) -> Dict[str, object]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        for traveler in list(self.get_wilderness_travelers()):
            if int(traveler.get("x", -1)) == int(x) and int(traveler.get("y", -1)) == int(y):
                return traveler
        return {}

    def render_wilderness_traveler(self, traveler: Dict[str, object]) -> str:
        from ascii_farmstead_support import C, colorize
        role = str(traveler.get("role", "Traveler"))
        symbol = "&" if role == "Trail Merchant" else "@"
        symbol, color = actor_style(
            "traveler",
            symbol,
            role,
            detailed=bool(getattr(self.state, "detailed_glyphs_enabled", True)),
            high_contrast=bool(getattr(self.state, "high_contrast_enabled", False)),
        )
        return colorize(symbol, color)

    def update_wilderness_travelers(self):
        if not self.on_wilderness():
            return
        cx = int(self.state.wilderness_chunk_x)
        cy = int(self.state.wilderness_chunk_y)
        for traveler in list(self.get_wilderness_travelers()):
            if traveler.get("static_actor"):
                continue
            if random.random() > 0.34:
                continue
            x, y = int(traveler.get("x", 0)), int(traveler.get("y", 0))
            anchor_x, anchor_y = int(traveler.get("anchor_x", x)), int(traveler.get("anchor_y", y))
            options = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            random.shuffle(options)
            if traveler.get("road_route"):
                current_world_x, current_world_y = self.wilderness_world_coords(cx, cy, x, y)
                target_world_x = int(traveler.get("route_destination_world_x", current_world_x))
                target_world_y = int(traveler.get("route_destination_world_y", current_world_y))
                if traveler.get("fixed_road_route") and abs(current_world_x - target_world_x) + abs(current_world_y - target_world_y) <= 1:
                    continue
                if (
                    not traveler.get("fixed_road_route")
                    and abs(current_world_x - target_world_x) + abs(current_world_y - target_world_y) <= 3
                ):
                    destination = self.wilderness_traveler_route_destination(
                        cx, cy, f"{traveler.get('id')}:{traveler.get('route_steps', 0)}",
                        str(traveler.get("route_destination_id", "")),
                    )
                    if destination:
                        traveler.update({
                            "route_destination_id": str(destination["id"]),
                            "route_destination_name": str(destination["name"]),
                            "route_destination_kind": str(destination["kind"]),
                            "route_destination_chunk_x": int(destination["chunk_x"]),
                            "route_destination_chunk_y": int(destination["chunk_y"]),
                            "route_destination_world_x": int(destination["world_x"]),
                            "route_destination_world_y": int(destination["world_y"]),
                        })
                        target_world_x, target_world_y = int(destination["world_x"]), int(destination["world_y"])

                options = self.wilderness_traveler_route_options(traveler, cx, cy, options)
            else:
                options.sort(key=lambda step: abs(x + step[0] - anchor_x) + abs(y + step[1] - anchor_y) if abs(x - anchor_x) + abs(y - anchor_y) > 8 else 0)
            for dx, dy in options:
                moved, destination_x, destination_y = self.try_move_wilderness_stream_actor(
                    "traveler", traveler, cx, cy, [(dx, dy)]
                )
                if not moved:
                    continue
                if (destination_x, destination_y) == (cx, cy):
                    nx, ny = int(traveler.get("x", x)), int(traveler.get("y", y))
                    if traveler.get("road_route"):
                        traveler["route_steps"] = int(traveler.get("route_steps", 0)) + 1
                        traveler["activity"] = f"following the road toward {traveler.get('route_destination_name', 'a settlement')}"
                    else:
                        traveler["activity"] = "surveying the weekly event" if self.wilderness_event_visual_at(nx, ny) else "walking the regional trails"
                break

    def wilderness_traveler_lines(self, traveler: Dict[str, object], topic: str = "work") -> List[str]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_profile(cx, cy)
        points, vitality = self.wilderness_region_vitality(cx, cy)
        event = self.wilderness_weekly_event_profile(cx, cy)
        role = str(traveler.get("role", "Traveler"))
        work_dialogue = {
            "Ranger": "I read a trail by what changed since the last patrol: fresh tracks, moved stones, damaged markers, and whether travelers are avoiding a bend.",
            "Naturalist": "I revisit the same habitats because a useful observation needs a before and an after, not just an unusual specimen.",
            "Herbalist": "I harvest by season, weather, and recovery rate. A medicinal patch is only useful if it survives being useful.",
            "Woodward": "A healthy wood needs fallen timber for habitat, clear passages for travel, and enough restraint to tell those needs apart.",
            "Mycologist": "The visible cap is a brief announcement from a much larger life under the soil and deadwood.",
            "Wetland Warden": "Water chooses the trail eventually. My job is to notice early enough that people and habitat do not lose the same argument.",
            "Prospector": "I record seams, unstable faces, and what should remain untouched. A survey is not permission to empty a place.",
            "Desert Guide": "I measure a desert route in shade, water, landmarks, and honest turnaround points rather than distance alone.",
            "Tundra Warden": "A marker has to remain legible after wind erases the tracks that led to it. Placement matters more than height.",
            "Coast Pilot": "I remember channels by tide, current, wind, and what lies down-current of a mistake.",
            "Trail Merchant": "I follow maintained routes because predictable travel lets small settlements trade without paying for every uncertainty twice.",
            "Courier": "A useful route is one I can describe honestly to the next person: where it narrows, where it floods, and where a tired traveler can stop.",
            "Pilgrim": "I travel slowly enough to learn which places people care for, which they fear, and which they only pass because the road insists.",
            "Hunter": "I watch tracks, wind, feeding grounds, and breeding seasons. Taking from a place without learning its limits is how a good range becomes an empty one.",
        }.get(role, "I travel by observing what the road, weather, and people are doing now rather than what an old map promised.")
        if topic == "route":
            if traveler.get("road_route"):
                dialogue = (
                    f"I am following the road toward {traveler.get('route_destination_name', 'a nearby destination')}. "
                    f"The route is {str(traveler.get('route_condition', 'open')).lower()}, but I still watch every junction for recent traffic."
                )
            else:
                dialogue = f"I am {traveler.get('activity', 'walking the regional trails')}. Out here, a route is a sequence of safe decisions rather than a painted line."
        elif topic == "region":
            dialogue = f"{region['name']} is currently {vitality.lower()}. That affects wildlife, forage, travelers, and how far maintained routes can safely reach."
        elif topic == "event":
            dialogue = f"The {event['name'].lower()} is changing what I look for this week. The evidence is on the terrain if you follow it instead of only reading the report."
        elif topic == "personal":
            if traveler.get("recurring"):
                record = self.recurring_wilderness_traveler_record(cx, cy)
                dialogue = (
                    "I return because this route has become part of my life, not merely a line between assignments. Our shared work is one reason it feels that way."
                    if int(record.get("bond", 0) or 0) >= 6
                    else "I do not tell every passing traveler why I keep returning. Walk the route with me a few times and the answer may become obvious."
                )
            else:
                dialogue = "Some journeys are work and some are a way to keep moving. I am still deciding which kind this one is."
        elif topic == "home":
            if traveler.get("scheduled_specialist") or traveler.get("recurring"):
                dialogue = (
                    f"I live at {traveler.get('home_name', 'the regional outpost')}. "
                    "My bunk is there, along with the field journals, drying shelves, and the specimens that should not be carried through rain."
                )
            elif traveler.get("route_destination_name"):
                dialogue = (
                    f"I am between homes and obligations at the moment. My next reliable roof is near "
                    f"{traveler.get('route_destination_name')}."
                )
            else:
                dialogue = "I am traveling rather than residing here; tonight's shelter depends on how far the road and weather allow me to go."
        elif topic == "schedule":
            schedule = traveler.get("schedule", {}) if isinstance(traveler.get("schedule"), dict) else {}
            dialogue = (
                f"{schedule.get('hours', 'My route changes with weather and assigned work.')} "
                f"Today I am {traveler.get('activity', 'following the regional circuit')}."
            )
        else:
            dialogue = work_dialogue
        rows = [f'"{dialogue}"', "", f"Role: {role}", f"Region: {region['name']} — {vitality} vitality ({points})", f"Current event: {event['name']}", f"Activity: {traveler.get('activity', 'traveling')}"]
        if traveler.get("road_route"):
            rows.append(f"Road destination: {traveler.get('route_destination_name', 'a nearby landmark')}")
        if traveler.get("scheduled_specialist") or traveler.get("recurring"):
            schedule = traveler.get("schedule", {}) if isinstance(traveler.get("schedule"), dict) else self.wilderness_specialist_schedule(cx, cy)
            rows.extend([
                f"Home: {traveler.get('home_name', self.wilderness_outpost_name(cx, cy))}",
                f"Today's field site: {schedule.get('work_site', 'regional survey tract')}",
                f"Routine: {schedule.get('hours', 'Field days and outpost record days')}",
            ])
        if traveler.get("regional_circulation"):
            if traveler.get("home_region_commute"):
                rows.extend([
                    "This is an Elsewhere resident following a regular local work route.",
                    f"Purpose: {traveler.get('commute_purpose', 'local town business')}",
                    f"Route condition: {traveler.get('route_condition', 'Local Maintained Road')}",
                ])
            else:
                rows.extend([
                    f"This is the same traveler recorded by the Elsewhere inn and regional calendar.",
                    f"Route condition: {traveler.get('route_condition', 'Open')}",
                ])
        if traveler.get("recurring"):
            record = self.recurring_wilderness_traveler_record(cx, cy)
            rows.extend(["", f"Relationship: {self.recurring_wilderness_traveler_bond_label(record['bond'])} ({record['bond']})", f"Regional story: {record['story_stage']}/3", f"Shared memories: {len(record['memories'])}"])
        return rows

    def talk_to_recurring_wilderness_traveler(self, traveler: Dict[str, object], quiet: bool = False) -> bool:
        if not traveler.get("recurring"): return False
        record = self.recurring_wilderness_traveler_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        day = self.errand_day_key()
        if record.get("talk_day") == day:
            if not quiet:
                self.set_message(f"{record['name']} has already shared today's route observations with you.")
            return False
        record["talk_day"] = day
        record["bond"] = int(record["bond"]) + 1
        if not quiet:
            self.autosave_with_message(f"Caught up with {record['name']}. Relationship: {self.recurring_wilderness_traveler_bond_label(record['bond'])} ({record['bond']}).")
        return True

    def recurring_wilderness_traveler_assignment(self, traveler: Dict[str, object]) -> Dict[str, object]:
        record = self.recurring_wilderness_traveler_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        stage = int(record["story_stage"]) + 1
        role_item = {"Herbalist": "Wild Herbs", "Woodward": "Wood", "Mycologist": "Mushrooms", "Wetland Warden": "Marsh Reed", "Prospector": "Stone", "Desert Guide": "Clay", "Tundra Warden": "Winter Root", "Coast Pilot": "Marsh Reed"}.get(str(record["role"]), "Fiber")
        return {1: {"name": "Walk the Old Circuit", "bond": 1, "item": "", "qty": 0, "stamina": 4, "minutes": 35, "reward": 60, "vitality": 2}, 2: {"name": "Restore the Traveler's Cache", "bond": 4, "item": role_item, "qty": 3, "stamina": 5, "minutes": 50, "reward": 120, "vitality": 4}, 3: {"name": "Establish the Permanent Route", "bond": 8, "item": "Field Snack", "qty": 2, "stamina": 7, "minutes": 75, "reward": 220, "vitality": 7}}.get(stage, {})

    def complete_recurring_wilderness_traveler_assignment(self, traveler: Dict[str, object]) -> bool:
        if not traveler.get("recurring"): return False
        record = self.recurring_wilderness_traveler_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        assignment = self.recurring_wilderness_traveler_assignment(traveler)
        if not assignment:
            self.set_message("Your shared regional route is already fully established.")
            return False
        if int(record["bond"]) < int(assignment["bond"]):
            self.set_message(f"Build your relationship to {assignment['bond']} before beginning {assignment['name']}.")
            return False
        item, qty = str(assignment["item"]), int(assignment["qty"])
        if item and int(self.state.inventory.get(item, 0)) < qty:
            self.set_message(f"{assignment['name']} requires {qty} {item}.")
            return False
        assignment_stamina = max(1, int(assignment["stamina"]) - (1 if self.wilderness_climate_prepared() else 0))
        if not self.spend_stamina(assignment_stamina): return False
        if item: self.state.inventory[item] -= qty
        self.advance_time(int(assignment["minutes"]))
        record["story_stage"] = int(record["story_stage"]) + 1
        record["bond"] = int(record["bond"]) + 2
        record["memories"] = (list(record.get("memories", [])) + [f"Year {self.state.year}, {self.state.season}: {assignment['name']}"])[-12:]
        if int(record["story_stage"]) >= 3: record["established_route"] = True
        self.state.money += int(assignment["reward"])
        self.add_wilderness_region_vitality(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y, int(assignment["vitality"]), str(assignment["name"]))
        self.autosave_with_message(f"Completed {assignment['name']} with {record['name']}: +{assignment['reward']}g, +{assignment['vitality']} vitality, and +2 relationship.")
        return True

    def prepare_climate_route_with_traveler(self, traveler: Dict[str, object]) -> bool:
        if not traveler.get("recurring"):
            return False
        record = self.recurring_wilderness_traveler_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        if int(record.get("bond", 0)) < 4:
            self.set_message("Become a Familiar Face before asking for detailed regional route preparation.")
            return False
        if self.wilderness_climate_prepared():
            self.set_message("Your specialist route preparation is already active this week.")
            return False
        if not self.spend_stamina(2): return False
        self.advance_time(20)
        self.set_wilderness_climate_prepared(str(record["name"]))
        self.autosave_with_message(f"{record['name']} helped prepare your regional route: reduced fieldwork and expedition exertion this week.")
        return True

    def patrol_with_wilderness_traveler(self, traveler: Dict[str, object]) -> bool:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_record(cx, cy)
        key = f"{self.stronghold_cache_week_key()}:{traveler.get('role', 'traveler')}"
        patrols = region.setdefault("traveler_patrols", [])
        if key in patrols:
            self.set_message(f"You already joined a {str(traveler.get('role', 'traveler')).lower()} patrol this week.")
            return False
        if not self.spend_stamina(4):
            return False
        self.advance_time(25)
        patrols.append(key)
        region["traveler_patrols"] = patrols[-12:]
        self.state.money += 35
        self.add_wilderness_region_vitality(cx, cy, 2, f"patrol with {traveler.get('role', 'traveler')}")
        if traveler.get("recurring"):
            record = self.recurring_wilderness_traveler_record(cx, cy)
            record["bond"] = int(record["bond"]) + 2
        self.autosave_with_message(f"Patrolled with {traveler.get('name', 'the traveler')}: +35g and +2 regional vitality.")
        return True

    def wilderness_specialist_notes_lines(self, traveler: Dict[str, object]) -> List[str]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        record = self.recurring_wilderness_traveler_record(cx, cy)
        schedule = self.wilderness_specialist_schedule(cx, cy)
        completed, mastery = self.wilderness_region_mastery(cx, cy)
        points, vitality = self.wilderness_region_vitality(cx, cy)
        event = self.wilderness_weekly_event_profile(cx, cy)
        rows = [
            f"{record['name'].upper()}'S FIELD JOURNAL",
            "",
            f"Profession: {record['role']}",
            f"Home: {record['home_name']}",
            f"Residence: {record['residence']}",
            f"Today's assignment: {schedule['activity']}",
            f"Survey tract: {schedule['work_site']} ({schedule['work_chunk_x']},{schedule['work_chunk_y']})",
            f"Routine: {schedule['hours']}",
            "",
            f"Regional vitality: {vitality} ({points})",
            f"Player field mastery: {mastery} ({completed} completed sites)",
            f"Current event under observation: {event['name']}",
            f"Lessons completed together: {int(record.get('field_lessons', 0))}",
            f"Specimens contributed: {int(record.get('samples_received', 0))}",
            f"Shared route memories: {len(record.get('memories', []))}",
        ]
        memories = list(record.get("memories", []))[-4:]
        if memories:
            rows.extend(["", "RECENT SHARED WORK"] + [f"- {memory}" for memory in memories])
        return rows

    def study_with_wilderness_specialist(self, traveler: Dict[str, object]) -> bool:
        if not traveler.get("recurring"):
            return False
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_record(cx, cy)
        week = self.stronghold_cache_week_key()
        if region.get("specialist_lesson_week") == week:
            self.set_message("You already completed a field lesson with this region's specialist this week.")
            return False
        if not self.spend_stamina(3):
            return False
        self.advance_time(40)
        mapped = self.map_nearby_wilderness_chunks(1)
        record = self.recurring_wilderness_traveler_record(cx, cy)
        record["bond"] = int(record.get("bond", 0)) + 2
        record["field_lessons"] = int(record.get("field_lessons", 0)) + 1
        memory = f"Year {self.state.year}, {self.state.season}: field lesson at {self.wilderness_subhabitat_profile(cx, cy)['name']}"
        record["memories"] = (list(record.get("memories", [])) + [memory])[-12:]
        region["specialist_lesson_week"] = week
        self.state.money += 25
        self.add_wilderness_region_vitality(cx, cy, 2, f"field lesson with {record['name']}")
        self.autosave_with_message(
            f"Completed a field lesson with {record['name']}: +25g, +2 relationship, +2 vitality, and {mapped} nearby area(s) charted."
        )
        return True

    def share_wilderness_specialist_sample(self, traveler: Dict[str, object]) -> bool:
        if not traveler.get("recurring"):
            return False
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        region = self.wilderness_region_record(cx, cy)
        week = self.stronghold_cache_week_key()
        if region.get("specialist_sample_week") == week:
            self.set_message("This region's specialist has already catalogued your specimen this week.")
            return False
        item = self.wilderness_outpost_sample_item(cx, cy)
        if int(self.state.inventory.get(item, 0)) <= 0:
            self.set_message(f"Bring 1 {item} appropriate to this region's current study.")
            return False
        self.state.inventory[item] -= 1
        self.advance_time(15)
        record = self.recurring_wilderness_traveler_record(cx, cy)
        record["bond"] = int(record.get("bond", 0)) + 3
        record["samples_received"] = int(record.get("samples_received", 0)) + 1
        region["specialist_sample_week"] = week
        self.state.money += 50
        self.add_wilderness_region_vitality(cx, cy, 3, f"specimen catalogued by {record['name']}")
        self.autosave_with_message(
            f"{record['name']} catalogued 1 {item}: +50g, +3 relationship, and +3 regional vitality."
        )
        return True

    def buy_wilderness_traveler_supply(self, item: str, price: int) -> bool:
        if int(self.state.money) < int(price):
            self.set_message(f"You need {price}g for {item}.")
            return False
        self.state.money -= int(price)
        add_inventory_items(self.state.inventory, {str(item): 1})
        self.autosave_with_message(f"Bought 1 {item} for {price}g from the trail traveler.")
        return True

    def show_wilderness_traveler(self, traveler: Dict[str, object]):
        items = [
            self._wilderness_menu_item("talk", "Talk", "Hear what this traveler has noticed about the region."),
            self._wilderness_menu_item("patrol", "Join regional patrol", "Spend 4 stamina and 25 minutes improving the region."),
        ]
        if traveler.get("regional_circulation"):
            items.append(self._wilderness_menu_item(
                "escort", "Walk together" if traveler.get("home_region_commute") else "Escort along road",
                (
                    "Spend 2 stamina and 20 minutes helping this resident with the local route."
                    if traveler.get("home_region_commute")
                    else "Spend 4 stamina and 40 minutes helping this known traveler reach the next stop."
                ),
            ))
        role = str(traveler.get("role", "Traveler"))
        if traveler.get("recurring"):
            sample = self.wilderness_outpost_sample_item(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
            items.extend([
                self._wilderness_menu_item("notes", "Review Field Journal", "Home, schedule, current survey, regional findings, and shared history."),
                self._wilderness_menu_item("lesson", "Join Weekly Field Lesson", "Spend 3 stamina and 40 minutes learning the tract and charting nearby ground."),
                self._wilderness_menu_item("sample", f"Contribute Specimen — 1 {sample}", "Catalog a regional specimen for pay, relationship, and vitality."),
            ])
            assignment = self.recurring_wilderness_traveler_assignment(traveler)
            if assignment:
                items.append(self._wilderness_menu_item("story", str(assignment["name"]), f"Regional story stage {int(self.recurring_wilderness_traveler_record(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)['story_stage']) + 1}/3."))
            items.append(self._wilderness_menu_item("prepare", "Prepare Regional Route", "At Familiar Face, reduce local fieldwork and expedition exertion this week."))
        if role in {"Trail Merchant", "Ranger", "Naturalist", "Desert Guide", "Tundra Warden"}:
            items.append(self._wilderness_menu_item("snack", "Buy Field Snack — 35g", "Purchase one travel ration."))
        if role in {"Trail Merchant", "Herbalist", "Naturalist", "Mycologist", "Wetland Warden", "Desert Guide", "Tundra Warden"}:
            items.append(self._wilderness_menu_item("herbs", "Buy Wild Herbs — 20g", "Purchase one useful regional herb bundle."))
        choice = self.vertical_panel_select(f"{traveler.get('name', 'Traveler')} — {traveler.get('role', 'Traveler')}", items, 52, 23, return_back=True)
        if not choice:
            return
        if choice.value == "talk":
            topic_items = [
                self._wilderness_menu_item("route", "Ask About Their Route", str(traveler.get("activity", "Traveling"))),
                self._wilderness_menu_item("work", "Ask About Their Work", str(traveler.get("role", "Traveler"))),
                self._wilderness_menu_item("region", "Ask About This Region", "Vitality, terrain, and travel"),
                self._wilderness_menu_item("event", "Ask What They've Seen", str(self.wilderness_weekly_event_profile(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y).get("name", "Weekly event"))),
            ]
            if traveler.get("recurring"):
                topic_items.extend([
                    self._wilderness_menu_item("home", "Ask About Their Home", str(traveler.get("home_name", "Regional outpost"))),
                    self._wilderness_menu_item("schedule", "Ask About Their Routine", str(traveler.get("activity", "Regional fieldwork"))),
                    self._wilderness_menu_item("personal", "Ask Why They Stay", "Requires repeated meetings for a full answer"),
                ])
            topic_choice = self.vertical_panel_select(
                f"Talk with {traveler.get('name', 'Traveler')}",
                topic_items,
                52,
                23,
                return_back=True,
            )
            if not topic_choice:
                return
            self.vertical_panel_view(
                str(traveler.get("name", "Traveler")),
                self.wilderness_traveler_lines(traveler, str(topic_choice.value)),
                52,
                23,
            )
            influence_available = False
            if traveler.get("recurring"):
                influence_available = self.talk_to_recurring_wilderness_traveler(traveler, quiet=True)
            elif traveler.get("regional_circulation") and hasattr(self, "talk_to_regional_circulation_traveler"):
                influence_available = self.talk_to_regional_circulation_traveler(traveler)
            response = self.npc_dialogue_response_choice(
                traveler,
                influence_available=influence_available,
                title=f"Respond to {traveler.get('name', 'Them')}",
            )
            response_effect = int(response.get("effect", 0) or 0) if influence_available else 0
            if response_effect and traveler.get("recurring"):
                record = self.recurring_wilderness_traveler_record(
                    self.state.wilderness_chunk_x,
                    self.state.wilderness_chunk_y,
                )
                record["bond"] = max(0, min(250, int(record.get("bond", 0)) + response_effect))
            elif response_effect and traveler.get("regional_circulation"):
                traveler_id = str(traveler.get("id", "regional_visitor"))
                if traveler.get("authored_resident_trip"):
                    self.adjust_town_npc_relationship(traveler_id, response_effect)
                else:
                    bonds = self.regional_town_life_state().setdefault("visitor_bonds", {})
                    bonds[traveler_id] = max(0, min(250, int(bonds.get(traveler_id, 0) or 0) + response_effect))
            self.vertical_panel_view(
                str(traveler.get("name", "Traveler")),
                [
                    str(response.get("reaction", "The traveler turns their attention back to the route.")),
                    "",
                    f"Connection influence: {response_effect:+}"
                    if response_effect
                    else "No further connection influence today."
                    if not influence_available
                    else "No connection change.",
                ],
                52,
                23,
            )
            self.autosave_with_message(
                f"Spoke with {traveler.get('name', 'the traveler')}."
                + (f" Connection {1 + response_effect:+}." if influence_available else "")
            )
        elif choice.value == "patrol":
            self.patrol_with_wilderness_traveler(traveler)
        elif choice.value == "escort" and hasattr(self, "assist_regional_circulation_traveler"):
            self.assist_regional_circulation_traveler(traveler)
        elif choice.value == "snack":
            self.buy_wilderness_traveler_supply("Field Snack", 35)
        elif choice.value == "herbs":
            self.buy_wilderness_traveler_supply("Wild Herbs", 20)
        elif choice.value == "notes":
            self.vertical_panel_view(
                f"{traveler.get('name', 'Specialist')} — Field Journal",
                self.wilderness_specialist_notes_lines(traveler),
                54,
                25,
            )
        elif choice.value == "lesson":
            self.study_with_wilderness_specialist(traveler)
        elif choice.value == "sample":
            self.share_wilderness_specialist_sample(traveler)
        elif choice.value == "story":
            self.complete_recurring_wilderness_traveler_assignment(traveler)
        elif choice.value == "prepare":
            self.prepare_climate_route_with_traveler(traveler)

    def wilderness_expedition_rank(self, chunk_x: int, chunk_y: int) -> Tuple[int, str]:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        state = getattr(self.state, "wilderness_poi_state", {})
        region = state.get(f"region:{profile['key']}", {}) if isinstance(state, dict) else {}
        completed = int(region.get("expeditions_completed", 0)) if isinstance(region, dict) else 0
        if completed >= 12:
            return completed, "Warden"
        if completed >= 7:
            return completed, "Pathfinder"
        if completed >= 3:
            return completed, "Ranger"
        return completed, "Scout"

    def wilderness_expedition_rank_benefits(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        completed, rank = self.wilderness_expedition_rank(chunk_x, chunk_y)
        if rank == "Warden":
            return {"rank": rank, "stamina_discount": 3, "time_discount": 15, "money_bonus": 50, "extra_supplies": 2}
        if rank == "Pathfinder":
            return {"rank": rank, "stamina_discount": 2, "time_discount": 10, "money_bonus": 25, "extra_supplies": 1}
        if rank == "Ranger":
            return {"rank": rank, "stamina_discount": 1, "time_discount": 5, "money_bonus": 10, "extra_supplies": 0}
        return {"rank": rank, "stamina_discount": 0, "time_discount": 0, "money_bonus": 0, "extra_supplies": 0}

    def wilderness_expedition_offer(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        region = self.wilderness_region_profile(chunk_x, chunk_y)
        rx, ry = int(region["rx"]), int(region["ry"])
        candidates = []
        for cx, cy in self.wilderness_region_chunks(chunk_x, chunk_y):
            if (cx, cy) == (int(chunk_x), int(chunk_y)) or (cx, cy) == (0, 0):
                continue
            if self.wilderness_hash01(cx, cy, 88020) < 0.32:
                continue
            if self.wilderness_chunk_has_procedural_settlement(cx, cy) or self.wilderness_chunk_has_stronghold(cx, cy) or self.wilderness_chunk_has_dungeon_site(cx, cy) or self.is_claimable_wilderness_chunk(cx, cy):
                continue
            candidates.append((cx, cy))
        if not candidates:
            candidates = [(int(region["center_x"]), int(region["center_y"]))]
        week_score = sum(ord(ch) for ch in self.stronghold_cache_week_key())
        rng = random.Random(self.wilderness_chunk_seed(rx * 31 + week_score, ry * 37 - week_score) + 88200)
        tx, ty = rng.choice(candidates)
        biome = region["biome"]
        mission_pool = {
            ";": [("Migration Count", "count migrating animals and mark quiet nesting lanes"), ("Seedbank Survey", "collect a full record of the meadow's seasonal seed sources")],
            "%": [("Canopy Transect", "follow an old transect and assess storm damage"), ("Wildlife Passage", "map a safe passage between dense forest clearings")],
            "l": [("Spore Transect", "trace the region's fungal cycle across a second hollow"), ("Mosswater Survey", "sample shaded springs feeding the hollow")],
            "r": [("Floodplain Watch", "measure water marks and inspect vulnerable reed banks"), ("Waterfowl Count", "survey seasonal waterfowl without disturbing their shelter")],
            "x": [("Ridge Traverse", "inspect cairns and chart the safest exposed route"), ("Strata Survey", "compare distant rock faces across the highland")],
            "`": [("Dry Wash Traverse", "follow flood signs and mark dependable desert crossings"), ("Oasis Survey", "deliver supplies and record the seasonal water table")],
            '"': [("Tundra Track", "follow herd signs across the frozen heath"), ("Snow Marker Line", "repair route markers buried by drifting snow")],
            "[": [("Island Channel Survey", "deliver supplies and chart a safe route through the islands"), ("Seabird Census", "track nesting colonies across the outer coast")],
        }.get(biome, [("Regional Traverse", "complete a detailed cross-region field survey")])
        name, objective = rng.choice(mission_pool)
        kind = {"Migration Count": "track", "Seedbank Survey": "clues", "Canopy Transect": "repair", "Wildlife Passage": "track", "Spore Transect": "clues", "Mosswater Survey": "deliver", "Floodplain Watch": "repair", "Waterfowl Count": "track", "Ridge Traverse": "summit", "Strata Survey": "clues", "Dry Wash Traverse": "track", "Oasis Survey": "deliver", "Tundra Track": "track", "Snow Marker Line": "repair", "Island Channel Survey": "deliver", "Seabird Census": "track"}.get(name, "survey")
        return {"id": f"{region['key']}:{self.stronghold_cache_week_key()}", "name": name, "objective": objective, "objective_kind": kind, "region_key": region["key"], "region_name": region["name"], "target_x": tx, "target_y": ty, "accepted_week": self.stronghold_cache_week_key()}

    def active_wilderness_expedition(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        profile = self.wilderness_region_profile(chunk_x, chunk_y)
        state = getattr(self.state, "wilderness_poi_state", {})
        region = state.get(f"region:{profile['key']}", {}) if isinstance(state, dict) else {}
        expedition = region.get("active_expedition", {}) if isinstance(region, dict) else {}
        return expedition if isinstance(expedition, dict) else {}

    def active_wilderness_expedition_for_chunk(self, chunk_x: int, chunk_y: int) -> Dict[str, object]:
        state = getattr(self.state, "wilderness_poi_state", {})
        if not isinstance(state, dict):
            return {}
        for key, region in state.items():
            if not str(key).startswith("region:") or not isinstance(region, dict):
                continue
            expedition = region.get("active_expedition", {})
            if isinstance(expedition, dict) and int(expedition.get("target_x", 999999)) == int(chunk_x) and int(expedition.get("target_y", 999999)) == int(chunk_y):
                return expedition
        return {}

    def wilderness_expedition_objective_positions(
        self,
        chunk_x: int = None,
        chunk_y: int = None,
        grid: List[List[str]] = None,
    ) -> List[Tuple[int, int]]:
        if not self.on_wilderness():
            return []
        cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
        cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
        expedition = self.active_wilderness_expedition_for_chunk(cx, cy)
        required = max(0, int(expedition.get("required_points", 0))) if expedition else 0
        if not expedition or required <= 0:
            return []
        cache_key = f"{expedition.get('id', '')}:{cx},{cy}:{required}"
        cache = getattr(self, "_wilderness_expedition_objective_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._wilderness_expedition_objective_cache = cache
        if cache_key in cache:
            return list(cache[cache_key])
        if grid is None:
            grid = self.active_map() if (cx, cy) == (int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)) else self.wilderness_stream_map(cx, cy)
        if not grid:
            return []
        blocked = {"#", "~", "=", "S", "V", "X", "!", "T", "o", "*", "?", "R", "J", "P", "K", "Q", "A", "E", WILDERNESS_STRUCTURE_SYMBOL}
        candidates = [(x, y) for y in range(4, len(grid) - 4) for x in range(6, len(grid[0]) - 6) if grid[y][x] not in blocked]
        seed = self.wilderness_chunk_seed(cx, cy) + sum(ord(ch) for ch in str(expedition.get("id", ""))) * 23 + 88600
        rng = random.Random(seed)
        rng.shuffle(candidates)
        positions: List[Tuple[int, int]] = []
        for position in candidates:
            if any(abs(position[0] - px) + abs(position[1] - py) < 14 for px, py in positions):
                continue
            positions.append(position)
            if len(positions) >= required:
                break
        cache[cache_key] = positions
        if len(cache) > 12:
            for old_key in list(cache)[:-12]:
                cache.pop(old_key, None)
        return list(positions)

    def wilderness_expedition_objective_at(self, x: int, y: int) -> Dict[str, object]:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        return self.wilderness_expedition_objective_for_chunk_at(cx, cy, x, y, self.active_map())

    def wilderness_expedition_objective_for_chunk_at(
        self,
        chunk_x: int,
        chunk_y: int,
        x: int,
        y: int,
        grid: List[List[str]] = None,
    ) -> Dict[str, object]:
        cx, cy = int(chunk_x), int(chunk_y)
        expedition = self.active_wilderness_expedition_for_chunk(cx, cy)
        if not expedition:
            return {}
        positions = self.wilderness_expedition_objective_positions(cx, cy, grid)
        try:
            index = positions.index((int(x), int(y)))
        except ValueError:
            return {}
        point_id = f"{int(x)},{int(y)}"
        surveyed = expedition.get("surveyed_points", []) if isinstance(expedition.get("surveyed_points", []), list) else []
        kind = str(expedition.get("objective_kind", "survey"))
        labels = {"track": "follow and record trail signs", "repair": "repair a damaged trail marker", "deliver": "stock a remote field cache", "clues": "search for the next field clue", "summit": "secure the ascent route" if index < len(positions) - 1 else "reach and record the summit", "survey": "survey the marked location"}
        symbols = {"track": "t", "repair": "!", "deliver": "c", "clues": "?", "summit": "^", "survey": "?"}
        return {"index": index + 1, "total": len(positions), "point_id": point_id, "surveyed": point_id in surveyed, "name": expedition.get("name", "Regional Expedition"), "objective": expedition.get("objective", "survey the region"), "kind": kind, "action": labels.get(kind, labels["survey"]), "symbol": symbols.get(kind, "?")}

    def survey_wilderness_expedition_objective(self, x: int, y: int) -> bool:
        objective = self.wilderness_expedition_objective_at(x, y)
        if not objective:
            self.set_message("There is no active expedition objective here.")
            return False
        if objective["surveyed"]:
            self.set_message("This expedition point is already surveyed.")
            return False
        followers = min(2, len(self.active_travel_follower_ids()) + (1 if self.wilderness_climate_prepared() else 0))
        kind = str(objective.get("kind", "survey"))
        material = {"repair": ("Wood", 1), "deliver": ("Fiber", 1)}.get(kind)
        if material and int(self.state.inventory.get(material[0], 0)) < material[1]:
            self.set_message(f"This objective requires {material[1]} {material[0]}.")
            return False
        base_stamina = {"track": 3, "repair": 4, "deliver": 3, "clues": 3, "summit": 5, "survey": 3}.get(kind, 3)
        if not self.spend_stamina(max(1, base_stamina - followers)):
            return False
        if material: self.state.inventory[material[0]] -= material[1]
        base_minutes = {"track": 14, "repair": 18, "deliver": 12, "clues": 15, "summit": 22, "survey": 12}.get(kind, 12)
        self.advance_time(max(5, base_minutes - followers * 3))
        expedition = self.active_wilderness_expedition_for_chunk(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        surveyed = expedition.setdefault("surveyed_points", [])
        surveyed.append(str(objective["point_id"]))
        expedition["surveyed_points"] = list(dict.fromkeys(str(point) for point in surveyed))
        self.prepare_wilderness_runtime_overlays()
        complete_count = len(expedition["surveyed_points"])
        required = max(0, int(expedition.get("required_points", 0)))
        suffix = " Return to the field site to file the expedition report." if complete_count >= required else ""
        self.autosave_with_message(f"Completed expedition objective {objective['index']}/{objective['total']} — {objective.get('action', 'surveyed the point')}: {complete_count}/{required} complete.{suffix}")
        return True

    def accept_wilderness_expedition(self, chunk_x: int, chunk_y: int) -> bool:
        region = self.wilderness_region_record(chunk_x, chunk_y)
        active = region.get("active_expedition", {})
        if isinstance(active, dict) and active:
            self.set_message(f"You already have an active regional expedition: {active.get('name', 'Expedition')}.")
            return False
        if region.get("last_expedition_week") == self.stronghold_cache_week_key():
            self.set_message("You already completed this region's expedition assignment this week.")
            return False
        offer = self.wilderness_expedition_offer(chunk_x, chunk_y)
        offer["required_points"] = 3
        offer["surveyed_points"] = []
        region["active_expedition"] = dict(offer)
        self.autosave_with_message(f"Accepted {offer['name']}. Target wilderness chunk: ({offer['target_x']},{offer['target_y']}).")
        return True

    def complete_wilderness_expedition(self, x: int, y: int) -> bool:
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        expedition = self.active_wilderness_expedition_for_chunk(cx, cy)
        if not expedition:
            self.set_message("This is not the target of an active regional expedition.")
            return False
        required_points = max(0, int(expedition.get("required_points", 0)))
        surveyed_points = expedition.get("surveyed_points", []) if isinstance(expedition.get("surveyed_points", []), list) else []
        if len(set(str(point) for point in surveyed_points)) < required_points:
            self.set_message(f"Complete all physical expedition objectives before filing the report ({len(set(surveyed_points))}/{required_points}).")
            return False
        followers = min(2, len(self.active_travel_follower_ids()) + (1 if self.wilderness_climate_prepared(cx, cy) else 0))
        benefits = self.wilderness_expedition_rank_benefits(cx, cy)
        if not self.spend_stamina(max(2, 8 - followers * 2 - int(benefits["stamina_discount"]))):
            return False
        self.advance_time(max(25, 55 - followers * 10 - int(benefits["time_discount"])))
        region_key = str(expedition.get("region_key", ""))
        region = self.state.wilderness_poi_state.get(f"region:{region_key}", {})
        completed_before = int(region.get("expeditions_completed", 0))
        project_level = self.wilderness_region_project_level(cx, cy)
        money = 120 + min(180, completed_before * 15) + project_level * 25 + followers * 20 + int(benefits["money_bonus"])
        biome = self.wilderness_region_profile(cx, cy)["biome"]
        drops = {";": {"Mixed Seeds": 2}, "%": {"Wood": 3}, "l": {"Mushrooms": 3}, "r": {"Marsh Reed": 3}, "x": {"Stone": 3}}.get(biome, {"Wild Herbs": 2})
        if int(benefits["extra_supplies"]) > 0:
            primary = next(iter(drops))
            drops[primary] = int(drops[primary]) + int(benefits["extra_supplies"])
        add_inventory_items(self.state.inventory, drops)
        self.state.money += money
        region["expeditions_completed"] = completed_before + 1
        history = region.setdefault("expedition_history", [])
        history.append({"name": expedition.get("name", "Expedition"), "target": f"{cx},{cy}", "year": int(self.state.year), "season": str(self.state.season)})
        region["expedition_history"] = history[-12:]
        region["active_expedition"] = {}
        region["last_expedition_week"] = self.stronghold_cache_week_key()
        self.add_wilderness_region_vitality(cx, cy, 4, str(expedition.get("name", "regional expedition")))
        self.work_on_wilderness_region_project(cx, cy, fieldwork=True)
        _count, rank = self.wilderness_expedition_rank(cx, cy)
        self.autosave_with_message(f"Completed {expedition.get('name', 'regional expedition')}: +{money}g and {format_drops(drops)}. Expedition rank: {rank}.")
        return True

    def wilderness_expedition_lines(self, chunk_x: int, chunk_y: int) -> List[str]:
        region = self.wilderness_region_profile(chunk_x, chunk_y)
        completed, rank = self.wilderness_expedition_rank(chunk_x, chunk_y)
        active = self.active_wilderness_expedition(chunk_x, chunk_y)
        benefits = self.wilderness_expedition_rank_benefits(chunk_x, chunk_y)
        benefit_text = f"Current benefits: -{benefits['stamina_discount']} stamina, -{benefits['time_discount']} minutes, +{benefits['money_bonus']}g"
        rows = ["REGIONAL EXPEDITIONS", "", f"Region: {region['name']}", f"Expedition rank: {rank} ({completed} completed)", benefit_text, "", "Ranks: Ranger 3, Pathfinder 7, Warden 12", ""]
        if active:
            required = max(0, int(active.get("required_points", 0)))
            surveyed = len(set(str(point) for point in active.get("surveyed_points", []) if point is not None)) if isinstance(active.get("surveyed_points", []), list) else 0
            kind = str(active.get("objective_kind", "survey")).replace("_", " ").title()
            supply = " Bring 3 Wood." if active.get("objective_kind") == "repair" else (" Bring 3 Fiber." if active.get("objective_kind") == "deliver" else "")
            rows.extend([f"ACTIVE: {active.get('name', 'Expedition')}", str(active.get("objective", "Complete the field survey.")), f"Objective style: {kind}.{supply}", f"Target chunk: ({active.get('target_x')},{active.get('target_y')})", f"Physical survey points: {surveyed}/{required}", "The target chunk is marked ?; distinct objective markers appear inside it."])
        else:
            offer = self.wilderness_expedition_offer(chunk_x, chunk_y)
            region_record = self.wilderness_region_record(chunk_x, chunk_y)
            if region_record.get("last_expedition_week") == self.stronghold_cache_week_key():
                rows.extend(["WEEKLY ASSIGNMENT COMPLETE", "A new regional expedition will be posted next week."])
            else:
                rows.extend([f"AVAILABLE: {offer['name']}", str(offer["objective"]), f"Objective style: {str(offer.get('objective_kind', 'survey')).title()}", f"Target chunk: ({offer['target_x']},{offer['target_y']})", "Offers refresh weekly until accepted; accepted expeditions persist."])
        return rows

    def show_wilderness_expedition_menu(self, x: int, y: int):
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        active_here = self.active_wilderness_expedition_for_chunk(cx, cy)
        active_region = self.active_wilderness_expedition(cx, cy)
        items = [self._wilderness_menu_item("status", "Expedition briefing", "Review rank, objective, target, and reward growth.")]
        if active_here:
            items.append(self._wilderness_menu_item("complete", f"Complete {active_here.get('name', 'expedition')}", "Conduct the target survey with your traveling party."))
        elif not active_region and self.wilderness_region_record(cx, cy).get("last_expedition_week") != self.stronghold_cache_week_key():
            offer = self.wilderness_expedition_offer(cx, cy)
            items.append(self._wilderness_menu_item("accept", f"Accept {offer['name']}", f"Travel to chunk ({offer['target_x']},{offer['target_y']})."))
        choice = self.vertical_panel_select("Regional Expeditions", items, 52, 24, return_back=True)
        if not choice:
            return
        if choice.value == "status":
            self.vertical_panel_view("Regional Expeditions", self.wilderness_expedition_lines(cx, cy), 52, 24)
        elif choice.value == "accept":
            self.accept_wilderness_expedition(cx, cy)
        elif choice.value == "complete":
            self.complete_wilderness_expedition(x, y)

    def show_wilderness_field_site(self, x: int, y: int):
        site = self.wilderness_field_site_type(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y)
        items = [
            self._wilderness_menu_item("survey", "Conduct paid survey", "Record the site carefully for the largest payment."),
            self._wilderness_menu_item("restoration", "Restore habitat", "Take less pay and add labor to the regional project."),
            self._wilderness_menu_item("forage", "Forage carefully", "Take less pay in exchange for additional local materials."),
            self._wilderness_menu_item("phenomenon", "Investigate local discovery", "Make a one-time ecological choice unique to this chunk."),
            self._wilderness_menu_item("event", "Weekly environmental event", "Respond to a rotating regional ecological situation."),
            self._wilderness_menu_item("expedition", "Regional expeditions", "Accept mapped field missions and build an expedition rank."),
            self._wilderness_menu_item("project", "Regional project", "Review, supply, or work on this region's permanent improvement."),
        ]
        while True:
            choice = self.vertical_panel_select(str(site["name"]), items, 48, 24, return_back=True)
            if not choice:
                return
            if choice.value in {"survey", "restoration", "forage"}:
                self.perform_wilderness_fieldwork(x, y, choice.value)
                return
            if choice.value == "project":
                self.show_wilderness_region_project(x, y)
                continue
            if choice.value == "phenomenon":
                self.show_wilderness_phenomenon(x, y)
                continue
            if choice.value == "event":
                self.show_wilderness_weekly_event(x, y)
                continue
            if choice.value == "expedition":
                self.show_wilderness_expedition_menu(x, y)
                continue

    def show_wilderness_region_project(self, x: int, y: int):
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        profile = self.wilderness_region_project_profile(cx, cy)
        while True:
            project = self.wilderness_region_project(cx, cy)
            level = int(project.get("level", 0))
            active = int(project.get("active_tier", 0)) > 0
            items = [
                self._wilderness_menu_item("status", "Project overview", "Review requirements and permanent benefits."),
                self._wilderness_menu_item("supply", "Contribute carried supplies", "Add every carried material the project still needs."),
                self._wilderness_menu_item("labor", "Volunteer work shift", "Spend 8 stamina and 45 minutes on construction."),
            ]
            if not active and level < 3:
                items.append(self._wilderness_menu_item("expand", f"Begin level {level + 1} expansion", "Start the next stage of regional growth."))
            if level >= 3:
                items.append(self._wilderness_menu_item("maintain", "Weekly preserve stewardship", "Continue habitat care for recurring pay and materials."))
            if level >= 2:
                initiative = self.wilderness_seasonal_initiative_profile(cx, cy)
                items.append(self._wilderness_menu_item("seasonal", str(initiative["name"]), "Undertake this season's major regional initiative."))
            choice = self.vertical_panel_select(f"Regional Project: {profile['name']}", items, 52, 25, return_back=True)
            if not choice:
                return
            if choice.value == "status":
                self.vertical_panel_view(str(profile["name"]), self.wilderness_region_project_lines(cx, cy), 52, 25)
            elif choice.value == "supply":
                self.contribute_wilderness_region_project(cx, cy)
            elif choice.value == "labor":
                self.work_on_wilderness_region_project(cx, cy)
            elif choice.value == "expand":
                self.begin_wilderness_region_project_expansion(cx, cy)
            elif choice.value == "maintain":
                self.maintain_wilderness_region_preserve(cx, cy)
            elif choice.value == "seasonal":
                self.undertake_wilderness_seasonal_initiative(cx, cy)

    def _wilderness_menu_item(self, value: str, label: str, description: str):
        """Build a wilderness option without confusing its label and action ID."""
        from ascii_farmstead_ui import MenuItem
        return MenuItem(label=label, value=value, enabled=True, hint=description)
