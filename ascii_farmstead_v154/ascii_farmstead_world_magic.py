from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

from ascii_battle_prototype.combat.models import Skill
from ascii_farmstead_combat import farmstead_combat_profile
from ascii_farmstead_custom_content import custom_ability_records
from ascii_farmstead_data import CROP_DATA, MENU_BACK, MENU_CONFIRM_KEYS
from ascii_farmstead_support import C, colorize, movement_delta_for_key, normalize_key, read_key
from ascii_farmstead_ui import MenuItem


WORLD_MAGIC_KINDS = {
    "fire", "ice", "wet", "scorched", "earth_bridge", "growth",
    "cleared", "charged", "purified", "shadow", "steam", "mud",
    "electrified", "overgrowth", "slick_ice",
}

WORLD_MAGIC_MASTERY_THRESHOLDS = (
    (0, "Initiate"),
    (10, "Practiced"),
    (30, "Adept"),
    (75, "Master"),
)

WORLD_MAGIC_AFFINITY_LABELS = {
    "fire": "Ignite vegetation, burn away brush, and melt conjured ice.",
    "water": "Extinguish fires, soak ground, and water crops across the ability area.",
    "frost": "Freeze water into temporary walkable ice and smother nearby flames.",
    "earth": "Raise temporary stepping stones, till owned soil, and clear loose obstacles.",
    "storm": "Charge the ground, scatter brush, and ignite dry wilderness vegetation.",
    "nature": "Restore scorched ground and encourage crops or wild vegetation to grow.",
    "poison": "Wither weeds and invasive brush without producing harvestable resources.",
    "light": "Purify scorched, poisoned, or shadowed ground and nurture crops gently.",
    "shadow": "Create a short-lived veil that muffles exposed ground.",
    "wind": "Scatter loose weeds, quench weak flames, and dry soaked ground.",
}


class WorldMagicMixin:
    """Persistent, safe terrain interactions driven by ordinary combat skills."""

    def ensure_world_magic_state(self) -> None:
        if not isinstance(getattr(self.state, "world_magic_effects", None), dict):
            self.state.world_magic_effects = {}
        if not isinstance(getattr(self.state, "world_magic_tile_cooldowns", None), dict):
            self.state.world_magic_tile_cooldowns = {}
        if not isinstance(getattr(self.state, "world_magic_cast_counts", None), dict):
            self.state.world_magic_cast_counts = {}

    def world_magic_clock(self) -> int:
        s = self.state
        days = (max(0, int(s.year)) * 12 + max(1, int(s.month))) * 32 + max(1, int(s.day))
        return (days * 24 + max(0, int(s.hour))) * 60 + max(0, int(s.minute))

    def world_magic_scope(self) -> str:
        s = self.state
        location = str(s.location)
        if location == "Wilderness":
            return "Wilderness"
        if location == "Mine":
            return f"Mine:{int(s.mine_floor)}"
        if location == "WildernessCave":
            return f"Cave:{getattr(s, 'current_cave_key', '')}"
        if location == "WildernessDungeon":
            return f"Dungeon:{getattr(s, 'current_dungeon_key', '')}:{int(getattr(s, 'current_dungeon_floor', 1))}"
        if location == "ProceduralTownInterior":
            return (
                f"TownInterior:{getattr(s, 'current_procedural_settlement_key', '')}:"
                f"{getattr(s, 'current_procedural_building_id', '')}:"
                f"{int(getattr(s, 'current_procedural_building_floor', 0))}"
            )
        if location == "WildernessStructure":
            return f"Structure:{getattr(s, 'current_wilderness_structure_key', '')}"
        if location == "WildernessOutpost":
            return f"Outpost:{getattr(s, 'current_wilderness_outpost_key', '')}"
        if location == "TownResidenceInterior":
            return f"Residence:{getattr(s, 'current_authored_residence_id', '')}"
        return location

    def world_magic_tile_context(
        self, x: int, y: int,
    ) -> Optional[Tuple[Optional[int], Optional[int], int, int, List[List[str]]]]:
        if self.on_wilderness():
            chunk_x, chunk_y, local_x, local_y = self.wilderness_stream_resolve(int(x), int(y))
            if (
                abs(int(chunk_x) - int(self.state.wilderness_chunk_x)) > 1
                or abs(int(chunk_y) - int(self.state.wilderness_chunk_y)) > 1
            ):
                return None
            grid = self.wilderness_stream_map(chunk_x, chunk_y)
            if grid is None:
                grid = self.get_wilderness_chunk_map(chunk_x, chunk_y)
            return int(chunk_x), int(chunk_y), int(local_x), int(local_y), grid
        if not self.in_active_bounds(int(x), int(y)):
            return None
        return None, None, int(x), int(y), self.active_map()

    def world_magic_target_has_town(self, x: int, y: int) -> bool:
        context = self.world_magic_tile_context(x, y)
        if context is None or context[0] is None:
            return bool(self.on_town() or self.on_town_interior())
        return bool(self.procedural_town_plan(int(context[0]), int(context[1])))

    def world_magic_key_at(
        self,
        x: int,
        y: int,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> str:
        if self.world_magic_scope() == "Wilderness" or chunk_x is not None or chunk_y is not None:
            cx = int(self.state.wilderness_chunk_x if chunk_x is None else chunk_x)
            cy = int(self.state.wilderness_chunk_y if chunk_y is None else chunk_y)
            world_x, world_y = self.wilderness_world_coords(cx, cy, int(x), int(y))
            return f"Wilderness:{world_x},{world_y}"
        return f"{self.world_magic_scope()}:{int(x)},{int(y)}"

    def world_magic_effect_at(
        self,
        x: int,
        y: int,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> Dict[str, object]:
        self.ensure_world_magic_state()
        if not self.state.world_magic_effects:
            return {}
        key = self.world_magic_key_at(x, y, chunk_x, chunk_y)
        record = self.state.world_magic_effects.get(key, {})
        if not isinstance(record, dict):
            self.state.world_magic_effects.pop(key, None)
            return {}
        if int(record.get("expires_at", 0) or 0) <= self.world_magic_clock():
            kind = str(record.get("kind", ""))
            if kind in {"ice", "earth_bridge"} and self.world_magic_effect_under_player(key):
                record = dict(record)
                record["expires_at"] = self.world_magic_clock() + 15
                self.state.world_magic_effects[key] = record
            elif kind == "fire":
                record = dict(record)
                record["kind"] = "scorched"
                record["expires_at"] = self.world_magic_clock() + 3 * 24 * 60
                self.state.world_magic_effects[key] = record
            else:
                self.state.world_magic_effects.pop(key, None)
                return {}
        return record

    def world_magic_set_effect(
        self,
        x: int,
        y: int,
        kind: str,
        duration: int,
        source: str,
        *,
        original_tile: str = "",
        generation: int = 0,
    ) -> None:
        self.ensure_world_magic_state()
        context = self.world_magic_tile_context(x, y)
        if context is None:
            return
        chunk_x, chunk_y, local_x, local_y, _grid = context
        key = self.world_magic_key_at(local_x, local_y, chunk_x, chunk_y)
        self.state.world_magic_effects[key] = {
            "kind": str(kind),
            "scope": self.world_magic_scope(),
            "x": int(local_x),
            "y": int(local_y),
            "created_at": self.world_magic_clock(),
            "expires_at": self.world_magic_clock() + max(1, int(duration)),
            "source": str(source)[:48],
            "original_tile": str(original_tile)[:1],
            "chunk_x": int(chunk_x or 0),
            "chunk_y": int(chunk_y or 0),
            "next_spread_at": self.world_magic_clock() + 20 if str(kind) == "fire" else 0,
            "spread_count": 0,
            "generation": max(0, int(generation)),
        }

    def world_magic_remove_effect(self, x: int, y: int) -> Dict[str, object]:
        self.ensure_world_magic_state()
        context = self.world_magic_tile_context(x, y)
        if context is None:
            return {}
        chunk_x, chunk_y, local_x, local_y, _grid = context
        record = self.state.world_magic_effects.pop(
            self.world_magic_key_at(local_x, local_y, chunk_x, chunk_y), {}
        )
        return record if isinstance(record, dict) else {}

    def world_magic_render_at(
        self,
        x: int,
        y: int,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> Optional[str]:
        record = self.world_magic_effect_at(x, y, chunk_x, chunk_y)
        kind = str(record.get("kind", ""))
        if kind == "wet" and chunk_x is None and chunk_y is None and self.on_farm_work_land() and self.get_crop(x, y):
            return None
        style = {
            "fire": ("*", C.HOSTILE),
            "ice": ("=", C.SNOW),
            "wet": (",", C.WATER),
            "scorched": (";", C.STONE),
            "earth_bridge": (":", C.STONE),
            "growth": ('"', C.GRASS),
            "cleared": (".", C.SOIL_DRY),
            "charged": ("+", C.STORM),
            "purified": ("+", C.CROP_READY),
            "shadow": (".", C.BIN),
            "steam": ("~", C.SNOW),
            "mud": ("%", C.SOIL_WET),
            "electrified": ("~", C.STORM),
            "overgrowth": ('"', C.CROP_READY),
            "slick_ice": ("_", C.SNOW),
        }.get(kind)
        return colorize(*style) if style else None

    def world_magic_preview_render_at(
        self,
        x: int,
        y: int,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> Optional[str]:
        preview_keys = getattr(self, "_world_magic_preview_keys", set())
        if not isinstance(preview_keys, set) or not preview_keys:
            return None
        key = self.world_magic_key_at(x, y, chunk_x, chunk_y)
        if key not in preview_keys:
            return None
        affinity = str(getattr(self, "_world_magic_preview_affinity", ""))
        color = {
            "fire": C.HOSTILE,
            "water": C.WATER,
            "frost": C.SNOW,
            "earth": C.STONE,
            "storm": C.STORM,
            "nature": C.CROP_READY,
            "poison": C.GRASS,
            "light": C.CROP_READY,
            "shadow": C.BIN,
            "wind": C.PLACEMENT,
        }.get(affinity, C.PLACEMENT)
        return colorize("+", color)

    def world_magic_set_preview(
        self, tiles: Set[Tuple[int, int]], affinity: str,
    ) -> None:
        keys: Set[str] = set()
        for x, y in tiles:
            context = self.world_magic_tile_context(x, y)
            if context is None:
                continue
            chunk_x, chunk_y, local_x, local_y, _grid = context
            keys.add(self.world_magic_key_at(local_x, local_y, chunk_x, chunk_y))
        self._world_magic_preview_keys = keys
        self._world_magic_preview_affinity = str(affinity)

    def world_magic_clear_preview(self) -> None:
        self._world_magic_preview_keys = set()
        self._world_magic_preview_affinity = ""

    def world_magic_passability_override(self, x: int, y: int) -> Optional[bool]:
        kind = str(self.world_magic_effect_at(x, y).get("kind", ""))
        if kind in {"fire", "electrified"}:
            return False
        if kind in {"ice", "earth_bridge", "cleared", "scorched", "slick_ice", "steam", "mud"}:
            return True
        return None

    def world_magic_description_at(
        self,
        x: int,
        y: int,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> str:
        record = self.world_magic_effect_at(x, y, chunk_x, chunk_y)
        kind = str(record.get("kind", ""))
        if chunk_x is None and chunk_y is None and self.on_farm_work_land() and self.get_crop(x, y):
            return ""
        description = {
            "fire": "Magical fire is actively burning here. Water, frost, wind, or rain can extinguish it.",
            "ice": "A temporary conjured ice bridge covers the water and can be crossed on foot.",
            "wet": "The ground is magically soaked and resistant to fire for a while.",
            "scorched": "Recently burned ground is clear but will recover naturally in a few days.",
            "earth_bridge": "Raised stepping stones form a temporary crossing over the water.",
            "growth": "Fresh magically encouraged growth covers this patch.",
            "cleared": "Loose vegetation or rubble has been dispersed temporarily.",
            "charged": "Static energy crackles over the ground and will dissipate soon.",
            "purified": "A faint cleansing glow lingers over the restored ground.",
            "shadow": "A short-lived magical veil muffles the exposed ground.",
            "steam": "A warm cloud marks an elemental reaction between heat and water. Wind can disperse it.",
            "mud": "Water and earth magic have churned this patch into temporary mud.",
            "electrified": "Water carries a dangerous magical charge here. Wind or light can discharge it safely.",
            "overgrowth": "Water and nature magic have produced dense, temporary overgrowth.",
            "slick_ice": "A thin magical ice sheet covers the ground. It is passable but temporary.",
        }.get(kind, "")
        if not description:
            return ""
        remaining = max(1, int(record.get("expires_at", 0)) - self.world_magic_clock())
        if remaining >= 1440:
            time_text = f"about {math.ceil(remaining / 1440)} day(s)"
        elif remaining >= 60:
            time_text = f"about {math.ceil(remaining / 60)} hour(s)"
        else:
            time_text = f"about {remaining} minute(s)"
        return f"{description} It should last {time_text}."

    def world_magic_custom_affinities(self) -> Dict[str, str]:
        affinities: Dict[str, str] = {}
        for record in custom_ability_records():
            name = str(record.get("name", ""))
            affinity = str(record.get("world_element", "") or "").strip().lower()
            if name and affinity:
                affinities[name.casefold()] = affinity
        return affinities

    def world_magic_affinity(self, skill: Skill) -> str:
        custom = self.world_magic_custom_affinities().get(str(skill.name).casefold(), "")
        if custom:
            return custom
        zone = str(getattr(skill, "zone_type", "") or "").lower()
        if zone in {"fire", "frost", "storm", "earth", "poison", "light", "shadow"}:
            return zone
        lowered_name = str(skill.name).lower()
        lowered_description = str(getattr(skill, "description", "")).lower()
        keyword_groups = (
            ("frost", ("frost", "ice", "glacial", "rime", "hail", "snow", "freeze")),
            ("fire", ("fire", "flame", "cinder", "ignite", "inferno", "ember", "meteor")),
            ("water", ("water", "rain", "tide", "tidal", "aqua", "aqueous", "hydro", "geyser", "mist")),
            ("storm", ("storm", "lightning", "thunder", "shock", "static", "spark")),
            ("earth", ("earth", "stone", "quake", "seismic", "rock", "boulder")),
            ("wind", ("wind", "gust", "gale", "cyclone", "tornado")),
            ("nature", ("nature", "thorn", "vine", "growth", "bloom", "snare", "root")),
            ("poison", ("poison", "venom", "toxic", "acid", "spore")),
            ("light", ("light", "radiant", "solar", "sun", "cleanse")),
            ("shadow", ("shadow", "umbral", "dark", "void")),
        )
        for affinity, words in keyword_groups:
            if any(word in lowered_name for word in words):
                return affinity
        for affinity, words in keyword_groups:
            if any(word in lowered_description for word in words):
                return affinity
        return ""

    def world_magic_field_cost(self, skill: Skill) -> int:
        base = 0 if int(skill.mp_cost) <= 0 else max(1, (int(skill.mp_cost) + 1) // 2)
        if base <= 0:
            return 0
        tier = self.world_magic_mastery_tier(self.world_magic_affinity(skill))
        discount = 2 if tier >= 3 else (1 if tier >= 2 else 0)
        return max(1, base - discount)

    def world_magic_mastery_count(self, affinity: str) -> int:
        self.ensure_world_magic_state()
        return max(0, int(self.state.world_magic_cast_counts.get(str(affinity), 0) or 0))

    def world_magic_mastery_tier(self, affinity: str) -> int:
        count = self.world_magic_mastery_count(affinity)
        tier = 0
        for index, (threshold, _label) in enumerate(WORLD_MAGIC_MASTERY_THRESHOLDS):
            if count >= threshold:
                tier = index
        return tier

    def world_magic_mastery_label(self, affinity: str) -> str:
        return WORLD_MAGIC_MASTERY_THRESHOLDS[self.world_magic_mastery_tier(affinity)][1]

    def world_magic_mastery_next(self, affinity: str) -> Tuple[int, str]:
        count = self.world_magic_mastery_count(affinity)
        for threshold, label in WORLD_MAGIC_MASTERY_THRESHOLDS[1:]:
            if count < threshold:
                return threshold, label
        return WORLD_MAGIC_MASTERY_THRESHOLDS[-1]

    def world_magic_mastery_hint(self, affinity: str) -> str:
        count = self.world_magic_mastery_count(affinity)
        threshold, next_label = self.world_magic_mastery_next(affinity)
        if count >= WORLD_MAGIC_MASTERY_THRESHOLDS[-1][0]:
            return f"Master | {count} casts"
        return f"{self.world_magic_mastery_label(affinity)} {count}/{threshold} -> {next_label}"

    def world_magic_mastery_lines(self) -> List[str]:
        affinities = sorted(
            set(WORLD_MAGIC_AFFINITY_LABELS)
            | {str(key) for key in self.state.world_magic_cast_counts}
        )
        lines = [
            "FIELD MASTERY", "",
            "Successful terrain-changing casts build mastery in their affinity.",
            "Practiced: effects last 25% longer.",
            "Adept: effects last 50% longer and field casts cost 1 less MP.",
            "Master: effects last twice as long and field casts cost 2 less MP.", "",
        ]
        for affinity in affinities:
            lines.append(f"{affinity.title()}: {self.world_magic_mastery_hint(affinity)}")
        return lines

    def world_magic_duration(self, kind: str, affinity: str = "") -> int:
        weather = str(getattr(self.state, "weather", ""))
        season = str(getattr(self.state, "season", ""))
        if kind == "fire":
            base = 45 if weather in {"Rain", "Rainy", "Storm", "Stormy"} else 120
            return int(round(base * self.world_magic_mastery_duration_multiplier(affinity)))
        if kind == "ice":
            if season == "Winter":
                base = 24 * 60
            elif weather == "Hot" or season == "Summer":
                base = 3 * 60
            else:
                base = 8 * 60
            return int(round(base * self.world_magic_mastery_duration_multiplier(affinity)))
        base = {
            "wet": 3 * 60,
            "earth_bridge": 12 * 60,
            "growth": 24 * 60,
            "cleared": 8 * 60,
            "charged": 90,
            "purified": 6 * 60,
            "shadow": 2 * 60,
            "steam": 45,
            "mud": 4 * 60,
            "electrified": 90,
            "overgrowth": 8 * 60,
            "slick_ice": 3 * 60,
        }.get(kind, 60)
        return int(round(base * self.world_magic_mastery_duration_multiplier(affinity)))

    def world_magic_mastery_duration_multiplier(self, affinity: str) -> float:
        return (1.0, 1.25, 1.5, 2.0)[self.world_magic_mastery_tier(affinity)] if affinity else 1.0

    def world_magic_shape_tiles(
        self, origin: Tuple[int, int], target: Tuple[int, int], skill: Skill,
    ) -> Set[Tuple[int, int]]:
        if abs(target[0] - origin[0]) + abs(target[1] - origin[1]) > max(1, int(skill.range_max)):
            return set()
        shape = str(skill.shape)
        tiles: Set[Tuple[int, int]] = set()
        direction = self.dungeon_cardinal_direction(origin, target)
        if shape == "custom" and skill.custom_pattern:
            base = origin if skill.pattern_anchor == "caster" else target
            for raw_dx, raw_dy in skill.custom_pattern:
                dx, dy = int(raw_dx), int(raw_dy)
                if skill.pattern_rotate:
                    if direction == (0, 1):
                        dx, dy = -dy, dx
                    elif direction == (-1, 0):
                        dx, dy = -dx, -dy
                    elif direction == (0, -1):
                        dx, dy = dy, -dx
                tiles.add((base[0] + dx, base[1] + dy))
        elif shape == "burst":
            radius = max(0, int(skill.aoe_radius))
            tiles = {
                (target[0] + dx, target[1] + dy)
                for dx in range(-radius, radius + 1)
                for dy in range(-radius, radius + 1)
                if abs(dx) + abs(dy) <= radius
            }
        elif shape == "cross":
            tiles = {origin}
            for distance in range(1, max(1, int(skill.range_max)) + 1):
                tiles.update(
                    (origin[0] + dx * distance, origin[1] + dy * distance)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                )
        elif shape in {"strip", "cone"}:
            perpendicular = (-direction[1], direction[0])
            for step in range(1, max(1, int(skill.range_max)) + 1):
                spread = max(0, int(skill.width) // 2) if shape == "strip" else min(step, max(1, int(skill.width)))
                for offset in range(-spread, spread + 1):
                    tiles.add((
                        origin[0] + direction[0] * step + perpendicular[0] * offset,
                        origin[1] + direction[1] * step + perpendicular[1] * offset,
                    ))
        elif shape == "multishot":
            candidates = [
                (target[0] + dx, target[1] + dy)
                for dx in range(-2, 3)
                for dy in range(-2, 3)
                if abs(dx) + abs(dy) <= 2
            ]
            candidates.sort(key=lambda point: (abs(point[0] - target[0]) + abs(point[1] - target[1]), point[1], point[0]))
            tiles = set(candidates[:max(1, int(skill.shots))])
        else:
            tiles = {target}
        if self.on_wilderness():
            return {(x, y) for x, y in tiles if self.world_magic_tile_context(x, y) is not None}
        return {(x, y) for x, y in tiles if self.in_active_bounds(x, y)}

    def world_magic_tile_protected(self, x: int, y: int) -> bool:
        if (int(x), int(y)) == (int(self.state.player_x), int(self.state.player_y)):
            return True
        context = self.world_magic_tile_context(x, y)
        if context is None:
            return True
        chunk_x, chunk_y, local_x, local_y, grid = context
        if self.on_wilderness():
            actor_kind, _actor_record = self.wilderness_stream_actor_at(int(x), int(y))
            if actor_kind:
                return True
            is_current_chunk = (
                int(chunk_x) == int(self.state.wilderness_chunk_x)
                and int(chunk_y) == int(self.state.wilderness_chunk_y)
            )
            if is_current_chunk and self.dropped_pack_at(local_x, local_y):
                return True
            tile = str(grid[local_y][local_x])
            return tile in {
                "#", "H", "D", "$", "&", "@", "+", "_", "|", "<", ">",
                "V", "X", "!", "A", "E", "k", "q", "S", "B",
            }
        if self.travel_follower_at(x, y) or self.town_npc_at(x, y):
            return True
        if self.dropped_pack_at(x, y):
            return True
        if self.on_farm() and self.farm_animal_at(x, y):
            return True
        if (self.on_wilderness() or self.on_procedural_town_interior()) and self.procedural_town_resident_at(x, y):
            return True
        if self.on_farm_work_land() or self.on_house():
            if self.get_placed_object(x, y):
                return True
        tile = str(self.active_map()[int(y)][int(x)])
        return tile in {
            "#", "H", "D", "$", "&", "@", "+", "_", "|", "<", ">",
            "V", "X", "!", "A", "E", "k", "q", "S", "B",
        }

    def world_magic_growth_ready(self, x: int, y: int, affinity: str) -> bool:
        self.ensure_world_magic_state()
        cooldown_key = f"{affinity}:{self.world_magic_key_at(x, y)}"
        today = f"{self.state.year}-{self.state.month}-{self.state.day}"
        if str(self.state.world_magic_tile_cooldowns.get(cooldown_key, "")) == today:
            return False
        self.state.world_magic_tile_cooldowns[cooldown_key] = today
        return True

    def world_magic_apply_to_tile(self, affinity: str, skill: Skill, x: int, y: int) -> str:
        context = self.world_magic_tile_context(x, y)
        if context is None:
            return ""
        if self.world_magic_tile_protected(x, y):
            return ""
        chunk_x, chunk_y, local_x, local_y, grid = context
        tile = str(grid[local_y][local_x])
        existing_record = self.world_magic_effect_at(local_x, local_y, chunk_x, chunk_y)
        existing = str(existing_record.get("kind", ""))
        source = str(skill.name)
        crop = self.get_crop(local_x, local_y) if self.on_farm_work_land() else None
        if crop and affinity not in {"water", "nature", "light"}:
            return ""

        if affinity == "water":
            if existing == "fire":
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "steam", self.world_magic_duration("steam", affinity), source, original_tile=tile)
                return "made steam"
            if existing == "charged":
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "electrified", self.world_magic_duration("electrified", affinity), source, original_tile=tile)
                return "electrified"
            if existing == "scorched":
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "wet", self.world_magic_duration("wet", affinity), source, original_tile=tile)
                return "cooled"
            changed = False
            if crop and not crop.watered:
                crop.watered = True
                changed = True
            if tile == ",":
                grid[local_y][local_x] = "w"
                changed = True
            if changed:
                self.world_magic_set_effect(x, y, "wet", self.world_magic_duration("wet", affinity), source, original_tile=tile)
                return "watered"
            if tile in {".", ";", "%", "l", "r", "x", "`", '"', "[", "^"} and existing != "wet":
                self.world_magic_set_effect(x, y, "wet", self.world_magic_duration("wet", affinity), source, original_tile=tile)
                return "soaked"
            return ""

        if affinity == "frost":
            if existing == "fire":
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "steam", self.world_magic_duration("steam", affinity), source, original_tile=tile)
                return "made steam"
            if existing in {"wet", "mud"}:
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "slick_ice", self.world_magic_duration("slick_ice", affinity), source, original_tile=tile)
                return "flash-frozen"
            if tile == "~" and existing not in {"ice", "earth_bridge"}:
                self.world_magic_set_effect(x, y, "ice", self.world_magic_duration("ice", affinity), source, original_tile=tile)
                return "frozen"
            return ""

        if affinity == "fire":
            if existing in {"ice", "slick_ice", "wet", "mud"}:
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "steam", self.world_magic_duration("steam", affinity), source, original_tile=tile)
                return "made steam"
            if existing == "steam" or tile == "~" or crop:
                return ""
            if (
                self.world_magic_target_has_town(x, y)
            ):
                return ""
            if tile in {".", ";", "%", "l", "r", "x", "`", '"', "[", "^", "T", "*"} and existing != "fire":
                self.world_magic_set_effect(x, y, "fire", self.world_magic_duration("fire", affinity), source, original_tile=tile)
                return "ignited"
            return ""

        if affinity == "earth":
            if existing == "wet":
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "mud", self.world_magic_duration("mud", affinity), source, original_tile=tile)
                return "made mud"
            if existing in {"charged", "electrified"}:
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "cleared", self.world_magic_duration("cleared", affinity), source, original_tile=tile)
                return "grounded"
            if tile == "~" and existing not in {"ice", "earth_bridge"}:
                self.world_magic_set_effect(x, y, "earth_bridge", self.world_magic_duration("earth_bridge", affinity), source, original_tile=tile)
                return "bridged"
            if self.on_farm_work_land() and tile == "." and not crop:
                grid[local_y][local_x] = ","
                return "tilled"
            if tile in {"^", "o", "*"} and existing != "cleared":
                self.world_magic_set_effect(x, y, "cleared", self.world_magic_duration("cleared", affinity), source, original_tile=tile)
                return "cleared"
            return ""

        if affinity in {"wind", "storm"}:
            if existing == "fire" and affinity == "wind":
                self.world_magic_remove_effect(x, y)
                return "extinguished"
            if existing == "wet" and affinity == "wind":
                self.world_magic_remove_effect(x, y)
                return "dried"
            if affinity == "wind" and existing in {"steam", "shadow", "electrified"}:
                self.world_magic_remove_effect(x, y)
                return "dispersed"
            if affinity == "wind" and existing == "mud":
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "cleared", self.world_magic_duration("cleared", affinity), source, original_tile=tile)
                return "dried"
            if affinity == "storm" and existing in {"wet", "mud"}:
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "electrified", self.world_magic_duration("electrified", affinity), source, original_tile=tile)
                return "electrified"
            if affinity == "storm" and existing == "fire":
                existing_record["expires_at"] = int(existing_record.get("expires_at", self.world_magic_clock())) + 45
                return "fanned"
            if tile == "^" and existing != "cleared":
                self.world_magic_set_effect(x, y, "cleared", self.world_magic_duration("cleared", affinity), source, original_tile=tile)
                return "cleared"
            if affinity == "storm" and self.on_wilderness() and tile in {".", ";", "%", "l", "r", "x", "`", '"', "["} and existing not in {"wet", "fire"}:
                self.world_magic_set_effect(x, y, "charged", self.world_magic_duration("charged", affinity), source, original_tile=tile)
                return "charged"
            return ""

        if affinity in {"nature", "light"}:
            if crop and self.world_magic_growth_ready(x, y, affinity):
                crop.watered = True
                if affinity == "nature":
                    growth_days = max(1, int(CROP_DATA[crop.name]["growth_days"]))
                    crop.age = min(growth_days, int(crop.age) + 1)
                    crop.care_days = min(growth_days, int(crop.care_days) + 1)
                    crop.ready = bool(crop.age >= growth_days)
                    return "grown"
                return "nurtured"
            if crop:
                return ""
            if affinity == "nature" and existing in {"wet", "mud"}:
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "overgrowth", self.world_magic_duration("overgrowth", affinity), source, original_tile=tile)
                return "made overgrowth"
            if existing in {"scorched", "shadow", "charged", "electrified"}:
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "purified", self.world_magic_duration("purified", affinity), source, original_tile=tile)
                return "restored"
            if affinity == "nature" and tile in {".", ";", "%", "l", "r", "x", "`", '"', "["} and existing != "growth":
                self.world_magic_set_effect(x, y, "growth", self.world_magic_duration("growth", affinity), source, original_tile=tile)
                return "grown"
            return ""

        if affinity == "poison":
            if existing == "overgrowth":
                self.world_magic_remove_effect(x, y)
                self.world_magic_set_effect(x, y, "cleared", self.world_magic_duration("cleared", affinity), source, original_tile=tile)
                return "withered"
            if tile in {"^", '"'} and existing != "cleared":
                self.world_magic_set_effect(x, y, "cleared", self.world_magic_duration("cleared", affinity), source, original_tile=tile)
                return "withered"
            return ""

        if affinity == "shadow" and tile not in {"~", "#", " "} and existing != "shadow":
            self.world_magic_set_effect(x, y, "shadow", self.world_magic_duration("shadow", affinity), source, original_tile=tile)
            return "veiled"
        return ""

    def world_magic_cast_at(self, skill: Skill, target: Tuple[int, int]) -> bool:
        affinity = self.world_magic_affinity(skill)
        if not affinity:
            self.set_message(f"{skill.name} has no world interaction affinity.")
            return False
        cost = self.world_magic_field_cost(skill)
        if int(self.state.combat_focus) < cost:
            self.set_message(f"{skill.name} needs {cost} MP for field casting.")
            return False
        origin = (int(self.state.player_x), int(self.state.player_y))
        tiles = self.world_magic_shape_tiles(origin, target, skill)
        results: Dict[str, int] = {}
        for x, y in sorted(tiles, key=lambda point: (point[1], point[0])):
            result = self.world_magic_apply_to_tile(affinity, skill, x, y)
            if result:
                results[result] = results.get(result, 0) + 1
        if not results:
            self.set_message(f"{skill.name} cannot change anything in that area; no MP was spent.")
            return False
        self.state.combat_focus = max(0, int(self.state.combat_focus) - cost)
        self.ensure_world_magic_state()
        self.state.last_world_magic_ability = str(skill.name)[:48]
        old_tier = self.world_magic_mastery_tier(affinity)
        self.state.world_magic_cast_counts[affinity] = int(self.state.world_magic_cast_counts.get(affinity, 0)) + 1
        new_tier = self.world_magic_mastery_tier(affinity)
        self.advance_time(5)
        summary = ", ".join(f"{name} {count}" for name, count in sorted(results.items()))
        milestone = (
            f" {affinity.title()} field mastery reached {self.world_magic_mastery_label(affinity)}."
            if new_tier > old_tier else ""
        )
        self.set_message(f"{skill.name} reshapes the area: {summary}. MP -{cost}.{milestone}")
        self.invalidate_draw_cache()
        return True

    def world_magic_aim_skill(self, skill: Skill) -> bool:
        origin = (int(self.state.player_x), int(self.state.player_y))
        cursor_x, cursor_y = self.target_tile_pos()
        if self.world_magic_tile_context(cursor_x, cursor_y) is None:
            cursor_x, cursor_y = origin
        affinity = self.world_magic_affinity(skill)
        cost = self.world_magic_field_cost(skill)
        while True:
            affected = self.world_magic_shape_tiles(origin, (cursor_x, cursor_y), skill)
            self.world_magic_set_preview(affected, affinity)
            self.set_message(
                f"{skill.name} [{affinity.title()}]: {cost} MP, {self.dungeon_skill_shape_label(skill)}, "
                f"range {skill.range_max}, {len(affected)} tile(s). Move cursor; Z/Enter cast; V/X/Esc/Q cancel."
            )
            self.draw_with_look_cursor(cursor_x, cursor_y)
            key = normalize_key(read_key())
            if len(key) == 1 and key.isalpha():
                key = key.lower()
            if key in {"v", "b", "x", "q", "f", "\t", "\x1b"}:
                self.world_magic_clear_preview()
                self.set_message("World casting cancelled; no MP spent.")
                self.invalidate_draw_cache()
                return False
            movement = movement_delta_for_key(key)
            if movement:
                candidate = (cursor_x + movement[0], cursor_y + movement[1])
                if (
                    self.world_magic_tile_context(*candidate) is not None
                    and abs(candidate[0] - origin[0]) + abs(candidate[1] - origin[1]) <= int(skill.range_max)
                ):
                    cursor_x, cursor_y = candidate
                continue
            if key in MENU_CONFIRM_KEYS:
                self.world_magic_clear_preview()
                return self.world_magic_cast_at(skill, (cursor_x, cursor_y))

    def world_magic_last_skill(self) -> Optional[Skill]:
        remembered = str(getattr(self.state, "last_world_magic_ability", "") or "")
        if not remembered:
            return None
        return next((skill for skill in self.world_magic_available_skills() if skill.name == remembered), None)

    def quick_cast_last_world_ability(self) -> bool:
        if self.map_native_combat_active():
            self.set_message("Use the combat ability menu while enemies are taking turns.")
            return False
        skill = self.world_magic_last_skill()
        if skill is None:
            self.set_message("No field ability is remembered yet. Press V to choose one.")
            return False
        return self.world_magic_aim_skill(skill)

    def world_magic_available_skills(self) -> List[Skill]:
        skills = [skill for skill in self.dungeon_available_skills() if self.world_magic_affinity(skill)]
        existing = {skill.name for skill in skills}
        field_techniques = [
            Skill(
                "Water Weave", mp_cost=3, damage=0, range_max=4,
                aoe_radius=1, shape="burst",
                description="A practical water spell for crops, fire, and dry ground.",
            ),
        ]
        if int(getattr(self.state, "combat_level", 1)) >= 2:
            field_techniques.append(Skill(
                "Trail Gust", mp_cost=3, damage=0, range_max=5,
                shape="strip", width=1,
                description="A controlled wind that scatters brush and weak fire.",
            ))
        if int(getattr(self.state, "combat_level", 1)) >= 4:
            field_techniques.append(Skill(
                "Verdant Touch", mp_cost=4, damage=0, range_max=3,
                shape="point",
                description="Nature magic that restores ground and encourages careful growth.",
            ))
        skills.extend(skill for skill in field_techniques if skill.name not in existing)
        return skills

    def player_ability_menu_skills(self) -> List[Skill]:
        """Keep the character's complete ability set visible in every context."""
        skills = list(self.dungeon_available_skills())
        existing = {skill.name for skill in skills}
        skills.extend(
            skill
            for skill in self.world_magic_available_skills()
            if skill.name not in existing
        )
        return skills

    def world_support_ability_status(self, skill: Skill) -> Tuple[bool, str]:
        focus = int(self.state.combat_focus)
        cost = max(0, int(skill.mp_cost))
        if focus < cost:
            return False, f"needs {cost} MP"
        profile = farmstead_combat_profile(self.state)
        if skill.effect == "heal":
            if int(self.state.combat_current_hp) >= int(profile["max_hp"]):
                return False, "HP is already full"
            return True, f"restore {skill.heal_amount} HP"
        if skill.effect == "restore_mp":
            if focus >= int(profile["max_focus"]):
                return False, "MP is already full"
            if int(skill.mp_amount) <= cost:
                return False, "reserved for tactical combat"
            return True, f"channel {skill.mp_amount} MP before its {cost} MP cost"
        if skill.effect == "cleanse":
            combat = self.wilderness_field_combat_record()
            poisoned = int(combat.get("poison_turns", 0)) > 0
            return (poisoned, "remove poison" if poisoned else "no harmful condition to cleanse")
        if skill.effect == "guard":
            prepared = int(self.wilderness_field_combat_record().get("prepared_guard_turns", 0))
            return (prepared <= 0, "prepare Guard for the next hostile engagement" if prepared <= 0 else "Guard is already prepared")
        return False, "requires an active tactical target"

    def world_cast_support_ability(self, skill: Skill) -> bool:
        enabled, reason = self.world_support_ability_status(skill)
        if not enabled:
            self.set_message(f"{skill.name}: {reason}.")
            return False
        profile = farmstead_combat_profile(self.state)
        cost = max(0, int(skill.mp_cost))
        self.state.combat_focus = max(0, int(self.state.combat_focus) - cost)
        result = ""
        if skill.effect == "heal":
            before = int(self.state.combat_current_hp)
            self.state.combat_current_hp = min(
                int(profile["max_hp"]),
                before + max(0, int(skill.heal_amount)),
            )
            result = f"restores {self.state.combat_current_hp - before} HP"
        elif skill.effect == "restore_mp":
            before = int(self.state.combat_focus)
            self.state.combat_focus = min(
                int(profile["max_focus"]),
                before + max(0, int(skill.mp_amount)),
            )
            result = f"leaves you with {self.state.combat_focus} MP"
        elif skill.effect == "cleanse":
            self.wilderness_field_combat_record()["poison_turns"] = 0
            result = "removes the lingering poison"
        elif skill.effect == "guard":
            self.wilderness_field_combat_record()["prepared_guard_turns"] = 2
            result = "prepares Guard for your next hostile engagement"
        self.advance_time(5)
        self.set_message(f"{skill.name} {result}. MP -{cost}.")
        self.invalidate_draw_cache()
        return True

    def show_player_ability_menu(self):
        """Open one persistent ability entry point, regardless of location."""
        if not self.map_native_combat_active() and self.on_wilderness():
            px, py = int(self.state.player_x), int(self.state.player_y)
            nearby = [
                enemy
                for enemy in self.wilderness_field_combat_enemies()
                if (
                    bool(enemy.get("alert", False))
                    or abs(int(enemy.get("x", 0)) - px) + abs(int(enemy.get("y", 0)) - py) <= 6
                )
                and abs(int(enemy.get("x", 0)) - px) + abs(int(enemy.get("y", 0)) - py) <= 16
            ]
            if nearby:
                target = min(
                    nearby,
                    key=lambda enemy: abs(int(enemy.get("x", 0)) - px)
                    + abs(int(enemy.get("y", 0)) - py),
                )
                self.begin_wilderness_field_combat(target, reason="readied ability")
        if self.map_native_combat_active():
            return self.dungeon_combat_ability_menu()
        return self.show_world_magic_menu()

    def show_world_magic_menu(self):
        if self.map_native_combat_active():
            return self.dungeon_combat_ability_menu()
        while True:
            skills = self.player_ability_menu_skills()
            remembered_skill = self.world_magic_last_skill()
            items = []
            for skill in skills:
                affinity = self.world_magic_affinity(skill)
                if affinity:
                    cost = self.world_magic_field_cost(skill)
                    enabled = int(self.state.combat_focus) >= cost
                    label = f"{skill.name} [Field: {affinity.title()}]"
                    hint = (
                        f"{cost} MP | range {skill.range_max} | "
                        f"{self.dungeon_skill_shape_label(skill)} | "
                        f"{self.world_magic_mastery_hint(affinity)}. {skill.description}"
                    )
                elif skill.effect != "damage":
                    enabled, support_hint = self.world_support_ability_status(skill)
                    label = f"{skill.name} [Support]"
                    hint = f"{skill.mp_cost} MP | {support_hint}. {skill.description}"
                else:
                    enabled = False
                    label = f"{skill.name} [Combat]"
                    hint = (
                        f"Learned and ready. Engage a hostile to use its "
                        f"{self.dungeon_skill_shape_label(skill)} attack. {skill.description}"
                    )
                items.append(MenuItem(
                    label=label,
                    value=skill.name,
                    enabled=enabled,
                    hint=hint,
                ))
            if remembered_skill is not None:
                items.insert(0, MenuItem(
                    label=f"Quick cast: {remembered_skill.name}",
                    value="quick_cast",
                    enabled=int(self.state.combat_focus) >= self.world_magic_field_cost(remembered_skill),
                    hint="remembered field ability (Y)",
                ))
            items.append(MenuItem(label="Field mastery", value="mastery", enabled=True, hint="affinity progression and bonuses"))
            items.append(MenuItem(label="World interaction guide", value="guide", enabled=True, hint="elemental terrain rules"))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(
                "Abilities",
                items,
                return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed Abilities.")
                return MENU_BACK
            if choice.value == "guide":
                lines = [
                    "ABILITIES", "",
                    "Your learned abilities remain listed everywhere instead of changing with the current screen.",
                    "Elemental abilities use their real range and area shape as field tools outside combat.",
                    "Healing, channeling, cleansing, and guard preparation can also be used while exploring.",
                    "Pure combat techniques stay visible and become usable as soon as a hostile engages you.",
                    "The colored + overlay previews every affected tile and remains continuous across nearby wilderness chunks.",
                    "After a successful cast, press Y to quickly aim that remembered ability again.",
                    "Every character knows Water Weave; Trail Gust unlocks at level 2 and Verdant Touch at level 4.",
                    "Field casting costs roughly half the normal MP and advances time by five minutes.",
                    "No MP is spent when an ability cannot change the selected terrain.", "",
                ]
                lines.extend(f"{name.title()}: {description}" for name, description in WORLD_MAGIC_AFFINITY_LABELS.items())
                lines.extend([
                    "", "Safety:",
                    "People, animals, crops, furniture, doors, buildings, and major landmarks are protected.",
                    "Fire cannot be started in town or public interiors. Rain shortens and extinguishes exposed fires.",
                    "Wilderness fire spreads through nearby dry vegetation, but water, roads, stone, and bare ground form firebreaks.",
                    "Combine elements: heat and water make steam; storm charges wet ground; earth and water make mud.",
                    "Frost flash-freezes wet ground, while nature turns wet soil into temporary overgrowth.",
                    "Wind disperses steam and charges; light or earth can safely ground electrified terrain.",
                    "Use Z/Enter on an active effect to inspect, dismiss, smother, melt, or ground it.",
                    "Growth can accelerate each crop tile only once per day.",
                ])
                self.vertical_panel_view("World Ability Guide", lines)
                continue
            if choice.value == "mastery":
                self.vertical_panel_view("Field Mastery", self.world_magic_mastery_lines())
                continue
            if choice.value == "quick_cast" and remembered_skill is not None:
                self.world_magic_aim_skill(remembered_skill)
                continue
            skill = next((entry for entry in skills if entry.name == str(choice.value)), None)
            if skill:
                if self.world_magic_affinity(skill):
                    self.world_magic_aim_skill(skill)
                    return "cast"
                if skill.effect != "damage":
                    self.world_cast_support_ability(skill)
                    return "cast"

    def world_magic_record_is_current(self, record: Dict[str, object]) -> bool:
        if str(record.get("scope", "")) != self.world_magic_scope():
            return False
        if self.world_magic_scope() != "Wilderness":
            return True
        return (
            int(record.get("chunk_x", 0)) == int(self.state.wilderness_chunk_x)
            and int(record.get("chunk_y", 0)) == int(self.state.wilderness_chunk_y)
        )

    def world_magic_effect_under_player(self, key: str) -> bool:
        return str(key) == self.world_magic_key_at(int(self.state.player_x), int(self.state.player_y))

    def spread_world_magic_fires(self, now: int) -> bool:
        if not self.on_wilderness() or bool(self.current_procedural_town_plan()):
            return False
        effects = self.state.world_magic_effects
        current_fires = [
            (key, record) for key, record in list(effects.items())
            if isinstance(record, dict)
            and str(record.get("kind", "")) == "fire"
            and self.world_magic_record_is_current(record)
            and int(record.get("expires_at", 0) or 0) > int(now)
        ]
        if len(current_fires) >= 24:
            return False
        changed = False
        flammable = {".", ";", "%", "l", "r", "x", "`", '"', "[", "^", "T", "*"}
        for key, record in current_fires:
            if len(current_fires) >= 24:
                break
            if int(record.get("generation", 0) or 0) >= 4:
                continue
            if int(record.get("spread_count", 0) or 0) >= 2:
                continue
            if int(record.get("next_spread_at", 0) or 0) > int(now):
                continue
            x, y = int(record.get("x", 0)), int(record.get("y", 0))
            directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
            offset = (sum(ord(char) for char in str(key)) + int(record.get("spread_count", 0))) % len(directions)
            directions = directions[offset:] + directions[:offset]
            spread = False
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if not self.in_active_bounds(nx, ny) or self.world_magic_tile_protected(nx, ny):
                    continue
                tile = str(self.active_map()[ny][nx])
                existing = str(self.world_magic_effect_at(nx, ny).get("kind", ""))
                if tile not in flammable or existing not in {"", "growth", "overgrowth", "scorched"}:
                    continue
                self.world_magic_set_effect(
                    nx, ny, "fire", self.world_magic_duration("fire"),
                    str(record.get("source", "spreading fire")),
                    original_tile=tile,
                    generation=int(record.get("generation", 0)) + 1,
                )
                current_fires.append((self.world_magic_key_at(nx, ny), self.world_magic_effect_at(nx, ny)))
                spread = True
                changed = True
                break
            record["spread_count"] = int(record.get("spread_count", 0) or 0) + 1
            record["next_spread_at"] = int(now) + 20
            effects[key] = record
            if not spread:
                record["spread_count"] = 2
        return changed

    def dismiss_world_magic_effect(self, x: int, y: int, *, smother: bool = False) -> bool:
        record = self.world_magic_effect_at(x, y)
        if not record:
            self.set_message("That magical effect has already faded.")
            return False
        kind = str(record.get("kind", ""))
        if smother and kind == "fire":
            if not self.spend_stamina(2):
                return False
            self.world_magic_remove_effect(x, y)
            self.world_magic_set_effect(x, y, "wet", 90, "smothered fire", original_tile=str(self.active_map()[y][x]))
            self.advance_time(5)
            self.set_message("You smother the magical fire and leave a damp firebreak. Stamina -2.")
        else:
            self.world_magic_remove_effect(x, y)
            self.advance_time(1)
            action = {
                "ice": "The ice bridge melts away.",
                "earth_bridge": "The stepping stones settle beneath the water.",
                "electrified": "You safely ground the magical charge.",
                "fire": "You dismiss the magical flame before it can spread.",
            }.get(kind, f"You dismiss the {kind.replace('_', ' ')} effect.")
            self.set_message(action)
        self.invalidate_draw_cache()
        return True

    def interact_with_world_magic_effect(self, x: int, y: int) -> bool:
        if self.on_farm_work_land() and self.get_crop(x, y):
            return False
        record = self.world_magic_effect_at(x, y)
        if not record:
            return False
        kind = str(record.get("kind", ""))
        items = [MenuItem(label="Inspect effect", value="inspect", enabled=True, hint=str(record.get("source", "field magic")))]
        if kind == "fire":
            items.append(MenuItem(label="Smother fire", value="smother", enabled=True, hint="2 stamina; leaves a wet firebreak"))
        dismiss_label = {
            "ice": "Melt ice bridge",
            "earth_bridge": "Dismiss stepping stones",
            "electrified": "Ground magical charge",
            "fire": "Dismiss flame",
        }.get(kind, "Dismiss effect")
        items.extend([
            MenuItem(label=dismiss_label, value="dismiss", enabled=True, hint="ends your temporary effect"),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ])
        while True:
            choice = self.vertical_panel_select("World Effect", items, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Left the magical effect undisturbed.")
                return True
            if choice.value == "inspect":
                self.vertical_panel_view("World Effect", [
                    kind.replace("_", " ").upper(), "",
                    self.world_magic_description_at(x, y),
                    f"Created by: {record.get('source', 'field magic')}",
                    f"Original terrain: {record.get('original_tile', '') or 'unknown'}",
                ])
                continue
            if choice.value == "smother":
                self.dismiss_world_magic_effect(x, y, smother=True)
                return True
            if choice.value == "dismiss":
                self.dismiss_world_magic_effect(x, y)
                return True

    def advance_world_magic_effects(self, minutes: int) -> None:
        self.ensure_world_magic_state()
        now = self.world_magic_clock()
        raining = str(getattr(self.state, "weather", "")) in {"Rain", "Rainy", "Storm", "Stormy"}
        changed = self.spread_world_magic_fires(now) if not raining else False
        for key, raw in list(self.state.world_magic_effects.items()):
            if not isinstance(raw, dict):
                self.state.world_magic_effects.pop(key, None)
                continue
            kind = str(raw.get("kind", ""))
            if kind not in WORLD_MAGIC_KINDS:
                self.state.world_magic_effects.pop(key, None)
                continue
            if raining and kind == "fire" and str(raw.get("scope", "")) in {"Farm", "Town", "Wilderness"}:
                raw["kind"] = "wet"
                raw["expires_at"] = now + self.world_magic_duration("wet")
                self.state.world_magic_effects[key] = raw
                changed = True
                continue
            if int(raw.get("expires_at", 0) or 0) > now:
                continue
            if kind == "fire":
                raw["kind"] = "scorched"
                raw["expires_at"] = now + 3 * 24 * 60
                self.state.world_magic_effects[key] = raw
                changed = True
            elif kind in {"ice", "earth_bridge"} and self.world_magic_effect_under_player(key):
                raw["expires_at"] = now + 15
                self.state.world_magic_effects[key] = raw
                self.set_message("The temporary crossing beneath you is weakening. It will hold for another 15 minutes.")
                changed = True
            else:
                self.state.world_magic_effects.pop(key, None)
                changed = True
        if len(self.state.world_magic_tile_cooldowns) > 1500:
            today = f"{self.state.year}-{self.state.month}-{self.state.day}"
            self.state.world_magic_tile_cooldowns = {
                key: value for key, value in self.state.world_magic_tile_cooldowns.items()
                if str(value) == today
            }
        if changed:
            self.invalidate_draw_cache()
