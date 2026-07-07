from __future__ import annotations

"""Player property, business, trade-network, and procedural election systems."""

from typing import Dict, List, Optional, Tuple

from ascii_farmstead_civic_state import (
    sanitize_civic_profile,
    sanitize_player_businesses,
    sanitize_player_properties,
    sanitize_player_trade_routes,
)
from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK
from ascii_farmstead_helpers import days_in_month
from ascii_farmstead_npc_builder import stable_text_seed
from ascii_farmstead_town_builder import settlement_chunk_key
from ascii_farmstead_ui import MenuItem


BUSINESS_TYPES = {
    "general_store",
    "market_stall",
    "inn",
    "clinic",
    "carpenter",
    "workshop",
    "library",
}
BUSINESS_BASE_PRICES = {
    "general_store": 6200,
    "market_stall": 3200,
    "inn": 7600,
    "clinic": 6800,
    "carpenter": 6500,
    "workshop": 7200,
    "library": 5400,
}
BUSINESS_BASE_INCOME = {
    "general_store": 95,
    "market_stall": 58,
    "inn": 115,
    "clinic": 88,
    "carpenter": 92,
    "workshop": 108,
    "library": 64,
}
BUSINESS_STRATEGIES = {
    "Balanced": "Steady income with no special emphasis.",
    "Local Goods": "Lower profit, stronger town development.",
    "Growth": "Higher income with more reinvestment risk.",
    "Trade": "Improves connected trade-route income.",
}
TOWN_POLICIES = {
    "Public Works": "Town development and civic projects receive priority.",
    "Market Investment": "Local businesses earn slightly more.",
    "Open Trade": "Trade routes earn more and cost less to establish.",
    "Family Services": "Community events and household services receive support.",
    "Wilderness Safety": "Travel services and emergency readiness receive priority.",
}
RESIDENCE_UPGRADE_NAMES = ("Furnished Rooms", "Household Wing", "Town Homestead")
BUSINESS_UPGRADE_NAMES = ("Improved Fixtures", "Expanded Floor", "Regional Operation")
CIVIC_INITIATIVES = {
    "road_grants": {
        "name": "Road and Sign Grants",
        "cost": 650,
        "development": 12,
        "description": "Repair approaches, improve signs, and support public paths.",
    },
    "market_hall": {
        "name": "Covered Market Hall",
        "cost": 900,
        "development": 8,
        "description": "Strengthen local businesses and year-round trading.",
    },
    "trade_depot": {
        "name": "Regional Trade Depot",
        "cost": 1100,
        "development": 8,
        "description": "Improve every player trade route leaving this town.",
    },
    "family_center": {
        "name": "Household and Learning Center",
        "cost": 800,
        "development": 7,
        "description": "Support family gatherings, lessons, and household services.",
    },
    "ranger_post": {
        "name": "Wilderness Ranger Post",
        "cost": 850,
        "development": 9,
        "description": "Improve emergency supplies and wilderness readiness.",
    },
}
BUSINESS_WAGE_POLICIES = {
    "Standard": "Normal wages and steady productivity.",
    "Generous": "Higher wages, better morale, and stronger productivity.",
    "Training": "Lower short-term output while staff develop and the town grows.",
}
BUSINESS_SUPPLY_CONTRACTS = {
    "Reliable Supply": "Stable inventory raises ordinary business income.",
    "Local Exports": "The business promotes town exports and development.",
    "Essential Goods": "Lower profit, but stronger civic reputation and services.",
}
REGIONAL_AGREEMENTS = {
    "Trade Charter": "Raises route income and deepens commercial ties.",
    "Mutual Aid": "Improves safety services in both connected towns.",
    "Cultural Exchange": "Strengthens festivals and resident relationships.",
}
REGIONAL_PROJECTS = {
    "waystation_network": {
        "name": "Regional Waystation Network",
        "cost": 2200,
        "description": "Improves every player route and links distant safe stops.",
    },
    "caravan_league": {
        "name": "Caravan League",
        "cost": 2600,
        "description": "Coordinates schedules and raises regional trade income.",
    },
    "shared_archive": {
        "name": "Shared Regional Archive",
        "cost": 1900,
        "description": "Shares maps, histories, and library resources.",
    },
    "household_exchange": {
        "name": "Household Exchange Program",
        "cost": 1800,
        "description": "Strengthens family services and cultural events.",
    },
    "ranger_network": {
        "name": "Regional Ranger Network",
        "cost": 2300,
        "description": "Improves route reliability and wilderness services.",
    },
}
CARAVAN_ADJECTIVES = (
    "Amber",
    "Blue",
    "Copper",
    "Green",
    "Northbound",
    "Red",
    "Silver",
    "Wayfarer",
)
CARAVAN_NOUNS = (
    "Bell",
    "Cart",
    "Lantern",
    "Mule",
    "Road",
    "Star",
    "Wagon",
    "Wheel",
)
REGIONAL_CONTRACT_LIMIT = 4
CARAVAN_JOURNEY_APPROACHES = {
    "Scout the road": {
        "stamina": 10,
        "reward": 35,
        "note": "Find safer approaches and useful forage.",
    },
    "Help with cargo": {
        "stamina": 8,
        "reward": 55,
        "note": "Load, secure, and account for the route goods.",
    },
    "Share the camp": {
        "stamina": 5,
        "reward": 25,
        "note": "Cook, listen, and strengthen the human side of the route.",
    },
}
CAMPAIGN_ACTIVITIES = {
    "Canvass Households": {
        "money": 0,
        "stamina": 8,
        "minutes": 45,
        "base_support": 6,
        "bloc": "Households",
    },
    "Market Speech": {
        "money": 120,
        "stamina": 5,
        "minutes": 40,
        "base_support": 7,
        "bloc": "Traders",
    },
    "Worker Roundtable": {
        "money": 80,
        "stamina": 6,
        "minutes": 50,
        "base_support": 7,
        "bloc": "Workers",
    },
    "Civic Workshop": {
        "money": 180,
        "stamina": 4,
        "minutes": 60,
        "base_support": 8,
        "bloc": "Civic",
    },
}
VOTER_BLOC_POLICIES = {
    "Households": ("Family Services", "Public Works"),
    "Traders": ("Open Trade", "Market Investment"),
    "Workers": ("Market Investment", "Public Works"),
    "Civic": ("Public Works", "Wilderness Safety"),
}
PETITION_CHOICES = {
    "Fund directly": "Use the civic treasury for an immediate response.",
    "Organize volunteers": "Use time and reputation to coordinate residents.",
    "Study and consult": "Gather information and improve future planning.",
}


class CivicEconomyMixin:
    """Shared player-facing civic and regional economy behavior."""

    def ensure_civic_economy_state(self) -> None:
        if not isinstance(getattr(self.state, "player_properties", None), dict):
            self.state.player_properties = sanitize_player_properties(
                getattr(self.state, "player_properties", {})
            )
        if not isinstance(getattr(self.state, "player_businesses", None), dict):
            self.state.player_businesses = sanitize_player_businesses(
                getattr(self.state, "player_businesses", {})
            )
        if not isinstance(getattr(self.state, "player_trade_routes", None), dict):
            self.state.player_trade_routes = sanitize_player_trade_routes(
                getattr(self.state, "player_trade_routes", {})
            )
        if not isinstance(getattr(self.state, "civic_profile", None), dict):
            self.state.civic_profile = sanitize_civic_profile(
                getattr(self.state, "civic_profile", {})
            )
        self.state.primary_residence_id = str(
            getattr(self.state, "primary_residence_id", "farmhouse") or "farmhouse"
        )
        if (
            self.state.primary_residence_id != "farmhouse"
            and self.state.primary_residence_id not in self.state.player_properties
        ):
            self.state.primary_residence_id = "farmhouse"
        if not isinstance(getattr(self.state, "civic_income_log", None), list):
            self.state.civic_income_log = []
        self.state.civic_income_log = [
            str(line)
            for line in self.state.civic_income_log
            if str(line or "").strip()
        ][-30:]

    def civic_date_ordinal(
        self,
        month: Optional[int] = None,
        day: Optional[int] = None,
        year: Optional[int] = None,
    ) -> int:
        month = int(getattr(self.state, "month", 1) if month is None else month)
        day = int(getattr(self.state, "day", 1) if day is None else day)
        year = int(getattr(self.state, "year", 1) if year is None else year)
        total = 0
        for previous_year in range(1, max(1, year)):
            total += sum(days_in_month(value, previous_year) for value in range(1, 13))
        total += sum(days_in_month(value, year) for value in range(1, max(1, month)))
        return total + max(1, day)

    def civic_town_key(self, plan: Dict[str, object]) -> str:
        return settlement_chunk_key(int(plan["chunk_x"]), int(plan["chunk_y"]))

    def civic_plan_for_key(self, town_key: str) -> Optional[Dict[str, object]]:
        try:
            chunk_x, chunk_y = [int(value) for value in str(town_key).split(",", 1)]
        except (TypeError, ValueError):
            return None
        return self.procedural_town_plan(chunk_x, chunk_y)

    def property_id_for_building(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> str:
        return f"property:{self.civic_town_key(plan)}:{building.get('id')}"

    def business_id_for_building(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> str:
        return f"business:{self.civic_town_key(plan)}:{building.get('id')}"

    def player_property_for_building(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> Optional[Dict[str, object]]:
        self.ensure_civic_economy_state()
        return self.state.player_properties.get(
            self.property_id_for_building(plan, building)
        )

    def procedural_property_object_location_key(self, property_id: str) -> str:
        return f"Residence:{property_id}"

    def current_procedural_residence_property(self) -> Optional[Dict[str, object]]:
        if not hasattr(self, "on_procedural_town_interior") or not self.on_procedural_town_interior():
            return None
        plan = self.current_procedural_town_plan()
        building = self.current_procedural_town_building()
        if (
            not plan
            or not building
            or str(building.get("type_id", "")) != "home"
        ):
            return None
        return self.player_property_for_building(plan, building)

    def on_player_owned_procedural_residence(self) -> bool:
        return self.current_procedural_residence_property() is not None

    def procedural_residence_has_furnishing(
        self,
        property_record: Optional[Dict[str, object]],
        obj_name: str,
    ) -> bool:
        if not property_record:
            return False
        location_key = self.procedural_property_object_location_key(
            str(property_record.get("id", ""))
        )
        placed_objects = getattr(self.state, "placed_objects", {})
        if not isinstance(placed_objects, dict):
            return False
        prefix = f"{location_key}:"
        return any(
            str(key).startswith(prefix) and str(value) == obj_name
            for key, value in placed_objects.items()
        )

    def procedural_residence_furnishing_stage(
        self,
        property_record: Dict[str, object],
    ) -> int:
        upgrade_level = int(property_record.get("upgrade_level", 0))
        stage = 0
        if bool(property_record.get("built")) or upgrade_level >= 1:
            stage = 1
        if bool(property_record.get("household_moved")) or upgrade_level >= 2:
            stage = 2
        if upgrade_level >= 3:
            stage = 3
        return stage

    def ensure_procedural_residence_furnishings(
        self,
        property_record: Dict[str, object],
        building: Optional[Dict[str, object]] = None,
    ) -> int:
        """Seed movable player furniture into a bought procedural residence."""
        if not isinstance(getattr(self.state, "placed_objects", None), dict):
            self.state.placed_objects = {}
        if not isinstance(property_record, dict):
            return 0
        property_id = str(property_record.get("id", ""))
        if not property_id:
            return 0
        location_key = self.procedural_property_object_location_key(property_id)
        target_stage = self.procedural_residence_furnishing_stage(property_record)
        try:
            current_stage = int(property_record.get("furnishings_level", -1))
        except (TypeError, ValueError):
            current_stage = -1
        if current_stage >= target_stage:
            return 0

        stage_layouts: Dict[int, List[Tuple[str, int, int]]] = {
            0: [
                ("Bed", 8, 8),
                ("Nightstand", 12, 8),
                ("Dresser", 14, 8),
                ("Wall Calendar", 17, 8),
                ("Chest", 10, 12),
                ("Television", 49, 8),
                ("Bookshelf", 10, 21),
                ("Writing Desk", 13, 21),
                ("Wooden Table", 27, 23),
                ("Wooden Chair", 29, 24),
                ("Decorative Rug", 34, 22),
            ],
            1: [
                ("Kitchen Counter", 9, 16),
                ("Pantry", 14, 16),
                ("Wash Basin", 17, 16),
                ("Tea Table", 50, 21),
            ],
            2: [
                ("Family Table", 46, 15),
                ("Couch", 46, 21),
                ("Child Bed", 49, 12),
                ("Toy Shelf", 54, 12),
                ("Study Desk", 49, 15),
            ],
            3: [
                ("Fireplace", 26, 3),
                ("Armchair", 31, 3),
                ("Keepsake Chest", 36, 3),
                ("Wall Art", 48, 3),
                ("House Plant", 56, 3),
                ("Large Rug", 25, 20),
            ],
        }

        def footprint_tiles(obj_name: str, x: int, y: int) -> List[Tuple[int, int]]:
            if hasattr(self, "object_footprint_tiles"):
                return list(self.object_footprint_tiles(obj_name, x, y))
            return [(x, y)]

        def parsed_object_key(key: str) -> Optional[Tuple[str, int, int]]:
            if hasattr(self, "parse_object_key"):
                return self.parse_object_key(key)
            try:
                location, coords = str(key).rsplit(":", 1)
                x_text, y_text = coords.split(",", 1)
                return location, int(x_text), int(y_text)
            except Exception:
                return None

        def location_tiles() -> set:
            occupied = set()
            for key, existing_name in list(self.state.placed_objects.items()):
                parsed = parsed_object_key(str(key))
                if not parsed:
                    continue
                location, ax, ay = parsed
                if location != location_key:
                    continue
                occupied.update(footprint_tiles(str(existing_name), ax, ay))
            return occupied

        added = 0
        occupied_tiles = location_tiles()
        for stage in range(max(-1, current_stage) + 1, target_stage + 1):
            for obj_name, x, y in stage_layouts.get(stage, []):
                key = f"{location_key}:{x},{y}"
                new_tiles = set(footprint_tiles(obj_name, x, y))
                if key in self.state.placed_objects or occupied_tiles.intersection(new_tiles):
                    continue
                self.state.placed_objects[key] = obj_name
                occupied_tiles.update(new_tiles)
                added += 1
        property_record["furnishings_level"] = target_stage
        return added

    def vacate_procedural_residence_for_player(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
        property_record: Optional[Dict[str, object]] = None,
    ) -> int:
        """Move generated residents out of a home after the player buys it."""
        population = self.procedural_settlement_population(
            int(plan.get("chunk_x", 0)),
            int(plan.get("chunk_y", 0)),
        )
        if not population:
            return 0
        buildings = plan.get("buildings", {})
        old_home_id = str(building.get("id", ""))
        town_key = self.civic_town_key(plan)
        owned_home_ids = {
            str(record.get("building_id", ""))
            for record in self.state.player_properties.values()
            if str(record.get("town_key", "")) == town_key
        }
        replacement_buildings = [
            candidate
            for candidate in buildings.values()
            if isinstance(candidate, dict)
            and str(candidate.get("id", "")) != old_home_id
            and str(candidate.get("id", "")) not in owned_home_ids
            and str(candidate.get("type_id", "")) == "home"
        ]
        if not replacement_buildings:
            replacement_buildings = [
                candidate
                for candidate in buildings.values()
                if isinstance(candidate, dict)
                and str(candidate.get("id", "")) != old_home_id
                and str(candidate.get("type_id", "")) == "inn"
            ]
        if not replacement_buildings:
            replacement_buildings = [
                candidate
                for candidate in buildings.values()
                if isinstance(candidate, dict)
                and str(candidate.get("id", "")) != old_home_id
            ]
        if not replacement_buildings:
            return 0

        def replacement_id_for(seed_text: str) -> str:
            index = stable_text_seed(f"{plan.get('seed')}:{old_home_id}:{seed_text}") % len(replacement_buildings)
            return str(replacement_buildings[index].get("id", ""))

        moved_households: Dict[str, str] = {}
        for household_id, household in list(population.get("households", {}).items()):
            if not isinstance(household, dict):
                continue
            if str(household.get("home_building_id", "")) != old_home_id:
                continue
            new_home_id = replacement_id_for(str(household_id))
            household["home_building_id"] = new_home_id
            moved_households[str(household_id)] = new_home_id

        moved_residents = 0
        builder = self.procedural_npc_builder() if hasattr(self, "procedural_npc_builder") else None
        for resident_id, resident in list(population.get("residents", {}).items()):
            if not isinstance(resident, dict):
                continue
            household_id = str(resident.get("household_id", ""))
            should_move = (
                str(resident.get("home_building_id", "")) == old_home_id
                or household_id in moved_households
            )
            if not should_move:
                continue
            new_home_id = moved_households.get(household_id) or replacement_id_for(str(resident_id))
            resident["home_building_id"] = new_home_id
            resident["runtime_location"] = "outdoor"
            resident["runtime_x"] = -1
            resident["runtime_y"] = -1
            resident["runtime_activity"] = "settling into new housing after a property sale"
            memories = list(resident.get("memories", []) or [])
            memories.append(
                f"Relocated from {building.get('name', 'a former home')} after it became a private player residence."
            )
            resident["memories"] = memories[-10:]
            if builder and new_home_id in buildings:
                try:
                    resident["schedule"] = builder.resident_schedule(plan, resident, buildings)
                except Exception:
                    pass
            moved_residents += 1

        if property_record is not None:
            property_record["original_residents_rehoused"] = int(
                property_record.get("original_residents_rehoused", 0)
            ) + moved_residents
        if moved_residents:
            self._procedural_resident_runtime_signature = None
        return moved_residents

    def player_business_for_building(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> Optional[Dict[str, object]]:
        self.ensure_civic_economy_state()
        return self.state.player_businesses.get(
            self.business_id_for_building(plan, building)
        )

    def procedural_town_civic_overlay_lookup(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[Tuple[int, int], Dict[str, object]]:
        plan = plan or self.current_procedural_town_plan()
        if not plan or self.on_procedural_town_interior():
            return {}
        self.ensure_civic_economy_state()
        town_key = self.civic_town_key(plan)
        properties = sorted(
            (
                str(record.get("id", "")),
                int(record.get("upgrade_level", 0)),
                str(record.get("use_mode", "Private")),
            )
            for record in self.state.player_properties.values()
            if str(record.get("town_key", "")) == town_key
        )
        businesses = sorted(
            (
                str(record.get("id", "")),
                int(record.get("upgrade_level", 0)),
                bool(record.get("active", True)),
            )
            for record in self.state.player_businesses.values()
            if str(record.get("town_key", "")) == town_key
        )
        politics = self.ensure_procedural_town_politics(plan)
        initiatives = tuple(
            sorted(str(value) for value in politics.get("completed_initiatives", []) or [])
        )
        projects = tuple(
            sorted(
                str(value)
                for value in self.ensure_regional_council_state().get(
                    "completed_projects",
                    [],
                )
                or []
            )
        )
        signature = (
            town_key,
            tuple(properties),
            tuple(businesses),
            initiatives,
            projects,
        )
        cache = getattr(self, "_procedural_civic_overlay_cache", {})
        if isinstance(cache, dict) and cache.get("signature") == signature:
            return dict(cache.get("lookup", {}))

        grid = self.active_map()
        height = len(grid)
        width = len(grid[0]) if height else 0
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        used = set()

        def reserve(
            anchor_x: int,
            anchor_y: int,
            record: Dict[str, object],
            offsets: Tuple[Tuple[int, int], ...],
        ) -> None:
            for dx, dy in offsets:
                x, y = anchor_x + dx, anchor_y + dy
                if not (1 <= x < width - 1 and 1 <= y < height - 1):
                    continue
                if (x, y) in used or self.procedural_town_building_at(x, y, plan):
                    continue
                if grid[y][x] not in {".", ",", ";", ":", "="}:
                    continue
                lookup[(x, y)] = record
                used.add((x, y))
                return

        building_lookup = plan.get("buildings", {})
        building_offsets = ((-1, 0), (1, 0), (-2, 0), (2, 0), (0, 1), (0, -1))
        for property_record in self.state.player_properties.values():
            if str(property_record.get("town_key", "")) != town_key:
                continue
            building = building_lookup.get(str(property_record.get("building_id", "")))
            if not isinstance(building, dict):
                continue
            level = int(property_record.get("upgrade_level", 0))
            reserve(
                int(building.get("access_x", building.get("door_x", 1))),
                int(building.get("access_y", building.get("door_y", 1))),
                {
                    "symbol": "q",
                    "kind": "residence",
                    "name": str(property_record.get("name", "Town Residence")),
                    "description": (
                        f"A household pennant and maintained frontage mark this as "
                        f"your {str(property_record.get('use_mode', 'Private')).lower()} "
                        f"residence. Exterior tier {level + 1}."
                    ),
                },
                building_offsets,
            )
        for business in self.state.player_businesses.values():
            if str(business.get("town_key", "")) != town_key:
                continue
            building = building_lookup.get(str(business.get("building_id", "")))
            if not isinstance(building, dict):
                continue
            level = int(business.get("upgrade_level", 0))
            reserve(
                int(building.get("access_x", building.get("door_x", 1))),
                int(building.get("access_y", building.get("door_y", 1))),
                {
                    "symbol": "k",
                    "kind": "business",
                    "name": str(business.get("name", "Player Business")),
                    "description": (
                        f"Your painted trade sign identifies this regional operation. "
                        f"Exterior tier {level + 1}; "
                        f"{'open' if business.get('active', True) else 'temporarily closed'}."
                    ),
                },
                tuple(reversed(building_offsets)),
            )

        town_hall = next(
            (
                building
                for building in building_lookup.values()
                if isinstance(building, dict)
                and str(building.get("type_id", "")) == "town_hall"
            ),
            None,
        )
        civic_x = int(town_hall.get("access_x", width // 2)) if town_hall else width // 2
        civic_y = int(town_hall.get("access_y", height // 2)) if town_hall else height // 2
        civic_offsets = (
            (-3, 0), (3, 0), (-4, 1), (4, 1), (-3, 2), (3, 2), (0, 3),
        )
        for index, initiative_id in enumerate(initiatives):
            initiative = CIVIC_INITIATIVES.get(initiative_id, {})
            reserve(
                civic_x,
                civic_y,
                {
                    "symbol": "j",
                    "kind": "initiative",
                    "name": str(initiative.get("name", "Completed Civic Work")),
                    "description": str(
                        initiative.get(
                            "description",
                            "A completed local project has changed this public space.",
                        )
                    ),
                },
                civic_offsets[index:] + civic_offsets[:index],
            )

        entrance = plan.get("entrance", {})
        regional_x = int(entrance.get("x", width // 2))
        regional_y = max(2, min(height - 3, int(entrance.get("y", height - 2)) - 2))
        regional_offsets = (
            (-3, 0), (3, 0), (-2, -1), (2, -1), (-4, -1), (4, -1), (0, -2),
        )
        for index, project_id in enumerate(projects):
            project = REGIONAL_PROJECTS.get(project_id, {})
            reserve(
                regional_x,
                regional_y,
                {
                    "symbol": "u",
                    "kind": "regional_project",
                    "name": str(project.get("name", "Regional Public Work")),
                    "description": str(
                        project.get(
                            "description",
                            "Regional investment is visibly reaching this town.",
                        )
                    ),
                },
                regional_offsets[index:] + regional_offsets[:index],
            )

        self._procedural_civic_overlay_cache = {
            "signature": signature,
            "lookup": dict(lookup),
        }
        return lookup

    def procedural_town_civic_overlay_at(
        self,
        x: int,
        y: int,
    ) -> Optional[Dict[str, object]]:
        return self.procedural_town_civic_overlay_lookup().get((int(x), int(y)))

    def procedural_town_residence_price(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> int:
        rank = self.procedural_town_development_rank(plan)
        comfort = 1 + rank
        return 2800 + rank * 850 + comfort * 250

    def purchase_procedural_town_residence(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
        built: bool = False,
    ) -> bool:
        self.ensure_civic_economy_state()
        if str(building.get("type_id")) != "home":
            return False
        property_id = self.property_id_for_building(plan, building)
        if property_id in self.state.player_properties:
            return False
        price = self.procedural_town_residence_price(plan, building)
        wood_cost = 60 if built else 0
        stone_cost = 30 if built else 0
        if int(self.state.money) < price:
            self.set_message(f"This residence requires {price}g.")
            return False
        if built and (
            int(self.state.inventory.get("Wood", 0)) < wood_cost
            or int(self.state.inventory.get("Stone", 0)) < stone_cost
        ):
            self.set_message(
                f"Building the private annex requires {wood_cost} Wood and {stone_cost} Stone."
            )
            return False
        self.state.money -= price
        if built:
            self.state.inventory["Wood"] -= wood_cost
            self.state.inventory["Stone"] -= stone_cost
        record = {
            "id": property_id,
            "town_key": self.civic_town_key(plan),
            "building_id": str(building["id"]),
            "name": (
                f"Private Annex at {building.get('name')}"
                if built
                else f"Town Residence at {building.get('name')}"
            ),
            "kind": "built_annex" if built else "residence",
            "purchase_price": price,
            "purchased_day": str(getattr(self.state, "date_label", "")),
            "comfort": min(10, 3 + self.procedural_town_development_rank(plan) + (1 if built else 0)),
            "built": bool(built),
            "upgrade_level": 0,
            "household_moved": False,
            "use_mode": "Private",
            "furnishings_level": -1,
            "original_residents_rehoused": 0,
            "lifetime_income": 0,
            "last_income_ordinal": self.civic_date_ordinal(),
        }
        self.state.player_properties[property_id] = record
        moved_residents = self.vacate_procedural_residence_for_player(
            plan,
            building,
            record,
        )
        self.ensure_procedural_residence_furnishings(record, building)
        self._procedural_town_interior_cache = {}
        self.adjust_procedural_town_reputation(
            8,
            "Established a permanent residence",
            plan,
        )
        relocation_note = (
            f" {moved_residents} former resident{'s' if moved_residents != 1 else ''} relocated within town."
            if moved_residents
            else ""
        )
        self.autosave_with_message(
            f"Acquired {record['name']} for {price}g. Starter furnishings are in place.{relocation_note}"
        )
        return True

    def household_residence_property(self) -> Optional[Dict[str, object]]:
        self.ensure_civic_economy_state()
        return next(
            (
                property_record
                for property_record in self.state.player_properties.values()
                if property_record.get("household_moved")
            ),
            None,
        )

    def household_residence_label(self) -> str:
        property_record = self.household_residence_property()
        return (
            str(property_record.get("name"))
            if property_record
            else "the farmhouse"
        )

    def move_household_to_residence(self, property_id: str) -> bool:
        self.ensure_civic_economy_state()
        has_household = bool(
            getattr(self.state, "spouse_npc_id", "")
            or getattr(self.state, "children", [])
        )
        if not has_household:
            self.set_message("There is no spouse or child household to relocate yet.")
            return False
        if property_id == "farmhouse":
            for property_record in self.state.player_properties.values():
                property_record["household_moved"] = False
            self.state.primary_residence_id = "farmhouse"
            self.autosave_with_message("Your household moved back to the farmhouse.")
            return True
        property_record = self.state.player_properties.get(str(property_id))
        if not property_record:
            return False
        for other in self.state.player_properties.values():
            other["household_moved"] = False
        property_record["household_moved"] = True
        self.state.primary_residence_id = str(property_id)
        plan = self.civic_plan_for_key(str(property_record.get("town_key", "")))
        building = (
            plan.get("buildings", {}).get(str(property_record.get("building_id", "")))
            if isinstance(plan, dict)
            else None
        )
        if isinstance(building, dict):
            self.ensure_procedural_residence_furnishings(property_record, building)
            self._procedural_town_interior_cache = {}
        self.autosave_with_message(
            f"Your household moved to {property_record.get('name')}."
        )
        return True

    def procedural_residence_upgrade_cost(
        self,
        property_record: Dict[str, object],
    ) -> Tuple[int, int, int]:
        level = int(property_record.get("upgrade_level", 0))
        return (
            1800 + level * 1200,
            35 + level * 20,
            20 + level * 15,
        )

    def procedural_residence_has_kitchen(
        self,
        property_record: Optional[Dict[str, object]],
    ) -> bool:
        if not property_record:
            return False
        return bool(property_record.get("built")) or int(property_record.get("upgrade_level", 0)) >= 1

    def upgrade_procedural_residence(self, property_id: str) -> bool:
        self.ensure_civic_economy_state()
        property_record = self.state.player_properties.get(str(property_id))
        if not property_record:
            return False
        level = int(property_record.get("upgrade_level", 0))
        if level >= len(RESIDENCE_UPGRADE_NAMES):
            self.set_message("This residence is fully upgraded.")
            return False
        money, wood, stone = self.procedural_residence_upgrade_cost(property_record)
        if (
            int(self.state.money) < money
            or int(self.state.inventory.get("Wood", 0)) < wood
            or int(self.state.inventory.get("Stone", 0)) < stone
        ):
            self.set_message(
                f"The next residence upgrade requires {money}g, {wood} Wood, and {stone} Stone."
            )
            return False
        self.state.money -= money
        self.state.inventory["Wood"] -= wood
        self.state.inventory["Stone"] -= stone
        property_record["upgrade_level"] = level + 1
        property_record["comfort"] = min(
            10,
            int(property_record.get("comfort", 1)) + 1,
        )
        plan = self.civic_plan_for_key(str(property_record.get("town_key", "")))
        building = (
            plan.get("buildings", {}).get(str(property_record.get("building_id", "")))
            if isinstance(plan, dict)
            else None
        )
        if isinstance(building, dict):
            self.ensure_procedural_residence_furnishings(property_record, building)
            self._procedural_town_interior_cache = {}
        self.autosave_with_message(
            f"Completed {RESIDENCE_UPGRADE_NAMES[level]} at "
            f"{property_record.get('name')}."
        )
        return True

    def procedural_residence_sleep_bonus(self) -> int:
        self.ensure_civic_economy_state()
        if (
            self.state.primary_residence_id == "farmhouse"
            or not self.can_sleep_at_primary_town_residence()
        ):
            return 0
        property_record = self.state.player_properties.get(
            self.state.primary_residence_id
        )
        if not property_record:
            return 0
        return max(0, int(property_record.get("comfort", 0)) // 2)

    def set_procedural_property_use(
        self,
        property_id: str,
        use_mode: str,
    ) -> bool:
        self.ensure_civic_economy_state()
        property_record = self.state.player_properties.get(str(property_id))
        if (
            not property_record
            or use_mode not in {"Private", "Guesthouse", "Rental"}
        ):
            return False
        if use_mode != "Private" and (
            property_record.get("household_moved")
            or self.state.primary_residence_id == property_id
        ):
            self.set_message(
                "A primary or household residence must remain private."
            )
            return False
        property_record["use_mode"] = use_mode
        property_record["last_income_ordinal"] = self.civic_date_ordinal()
        self.autosave_with_message(
            f"{property_record.get('name')} is now used as a {use_mode.lower()}."
        )
        return True

    def procedural_property_daily_income(
        self,
        property_record: Dict[str, object],
    ) -> int:
        mode = str(property_record.get("use_mode", "Private"))
        if mode == "Private":
            return 0
        comfort = int(property_record.get("comfort", 1))
        upgrade = int(property_record.get("upgrade_level", 0))
        income = (
            24 + comfort * 4 + upgrade * 8
            if mode == "Guesthouse"
            else 38 + comfort * 5 + upgrade * 10
        )
        if (
            "household_exchange"
            in set(
                self.ensure_regional_council_state().get(
                    "completed_projects",
                    [],
                )
                or []
            )
            and mode == "Guesthouse"
        ):
            income = income * 115 // 100
        return income

    def set_primary_residence(self, property_id: str) -> bool:
        self.ensure_civic_economy_state()
        if property_id == "farmhouse":
            self.state.primary_residence_id = "farmhouse"
            self.autosave_with_message("The farmhouse is now your primary residence.")
            return True
        property_record = self.state.player_properties.get(str(property_id))
        if not property_record:
            return False
        self.state.primary_residence_id = str(property_id)
        self.autosave_with_message(
            f"{property_record.get('name')} is now your primary residence."
        )
        return True

    def can_sleep_at_primary_town_residence(self) -> bool:
        self.ensure_civic_economy_state()
        if not self.on_procedural_town_interior():
            return False
        property_record = self.state.player_properties.get(
            self.state.primary_residence_id
        )
        building = self.current_procedural_town_building()
        plan = self.current_procedural_town_plan()
        return bool(
            property_record
            and building
            and plan
            and property_record.get("town_key") == self.civic_town_key(plan)
            and property_record.get("building_id") == building.get("id")
        )

    def procedural_town_household_members(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> List[Dict[str, object]]:
        property_record = self.player_property_for_building(plan, building)
        if not property_record or not property_record.get("household_moved"):
            return []
        members: List[Dict[str, object]] = []
        spouse_id = str(getattr(self.state, "spouse_npc_id", "") or "")
        if spouse_id:
            spouse = (
                self.npc_record_by_id(spouse_id)
                if hasattr(self, "npc_record_by_id")
                else next(
                    (
                        npc for npc in getattr(self.state, "town_npcs", [])
                        if str(npc.get("id", "")) == spouse_id
                    ),
                    None,
                )
            )
            if spouse and not self.travel_follower_identity_for_npc_id(spouse_id):
                record = dict(spouse)
                record["household_town_resident"] = True
                record["runtime_activity"] = self.spouse_household_activity_label(spouse).replace(
                    "farmhouse",
                    "town home",
                )
                members.append(record)
        for child_npc in self.household_child_npcs():
            child_id = str(child_npc.get("id", ""))
            if self.travel_follower_identity_for_npc_id(child_id):
                continue
            record = dict(child_npc)
            record["household_town_resident"] = True
            record["runtime_activity"] = str(
                child_npc.get("activity", "settling into the town home")
            )
            members.append(record)
        return members

    def reconcile_player_business_staff(self) -> int:
        self.ensure_civic_economy_state()
        updated = 0
        for business in self.state.player_businesses.values():
            plan = self.civic_plan_for_key(str(business.get("town_key", "")))
            if not plan:
                continue
            population = self.procedural_settlement_population(
                int(plan["chunk_x"]),
                int(plan["chunk_y"]),
            ) or {}
            staff_ids = set(business.get("employee_ids", []) or [])
            manager_id = str(business.get("manager_resident_id", "") or "")
            if manager_id:
                staff_ids.add(manager_id)
            for resident_id in staff_ids:
                resident = population.get("residents", {}).get(str(resident_id))
                if not isinstance(resident, dict):
                    continue
                if str(resident.get("workplace_building_id", "")) != str(
                    business.get("building_id", "")
                ):
                    resident["workplace_building_id"] = str(
                        business.get("building_id", "")
                    )
                    updated += 1
                if (
                    resident_id in set(business.get("employee_ids", []) or [])
                ):
                    resident["role"] = "Business Assistant"
                    resident["profession_id"] = "business_assistant"
                try:
                    resident["schedule"] = self.procedural_npc_builder().resident_schedule(
                        plan,
                        resident,
                        plan.get("buildings", {}),
                    )
                except (KeyError, TypeError, ValueError):
                    pass
        return updated

    def procedural_town_residence_menu(
        self,
        building: Dict[str, object],
    ) -> None:
        plan = self.current_procedural_town_plan()
        if not plan:
            return
        while True:
            property_record = self.player_property_for_building(plan, building)
            property_id = self.property_id_for_building(plan, building)
            is_primary = self.state.primary_residence_id == property_id
            household_here = bool(
                property_record and property_record.get("household_moved")
            )
            price = self.procedural_town_residence_price(plan, building)
            upgrade_cost = (
                self.procedural_residence_upgrade_cost(property_record)
                if property_record
                else (0, 0, 0)
            )
            items = [
                MenuItem(
                    label="Household information",
                    value="household",
                    enabled=True,
                ),
                MenuItem(
                    label="Purchase town residence",
                    value="purchase",
                    enabled=property_record is None and self.state.money >= price,
                    hint=f"{price}g; private residential suite",
                ),
                MenuItem(
                    label="Build private annex",
                    value="build",
                    enabled=(
                        property_record is None
                        and self.state.money >= price
                        and self.state.inventory.get("Wood", 0) >= 60
                        and self.state.inventory.get("Stone", 0) >= 30
                    ),
                    hint=f"{price}g, 60 Wood, 30 Stone",
                ),
                MenuItem(
                    label="Make primary residence",
                    value="primary",
                    enabled=bool(property_record) and not is_primary,
                    hint="Already primary" if is_primary else "",
                ),
                MenuItem(
                    label="Move household here",
                    value="household_move",
                    enabled=bool(property_record) and not household_here and bool(
                        self.state.spouse_npc_id or self.state.children
                    ),
                    hint="Household already lives here" if household_here else "",
                ),
                MenuItem(
                    label="Upgrade residence",
                    value="upgrade",
                    enabled=bool(property_record)
                    and int(property_record.get("upgrade_level", 0))
                    < len(RESIDENCE_UPGRADE_NAMES),
                    hint=(
                        f"{upgrade_cost[0]}g, {upgrade_cost[1]} Wood, "
                        f"{upgrade_cost[2]} Stone"
                        if property_record
                        else ""
                    ),
                ),
                MenuItem(
                    label="Set property use",
                    value="use_mode",
                    enabled=bool(property_record),
                    hint=(
                        str(property_record.get("use_mode", "Private"))
                        if property_record
                        else ""
                    ),
                ),
                MenuItem(
                    label="Sleep here",
                    value="sleep",
                    enabled=bool(property_record) and is_primary,
                    hint="Available at your primary residence",
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                str(building.get("name", "Town Residence")),
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "household":
                self.vertical_panel_view(
                    str(building.get("name", "Residence")),
                    self.procedural_town_home_lines(building),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "purchase":
                self.purchase_procedural_town_residence(plan, building)
            elif choice.value == "build":
                self.purchase_procedural_town_residence(plan, building, built=True)
            elif choice.value == "primary":
                self.set_primary_residence(property_id)
            elif choice.value == "household_move":
                self.move_household_to_residence(property_id)
            elif choice.value == "upgrade":
                self.upgrade_procedural_residence(property_id)
            elif choice.value == "use_mode" and property_record:
                mode_items = [
                    MenuItem(
                        label=mode,
                        value=mode,
                        enabled=(
                            mode == "Private"
                            or (
                                not property_record.get("household_moved")
                                and not is_primary
                            )
                        ),
                        hint=(
                            "Personal or household use"
                            if mode == "Private"
                            else f"{self.procedural_property_daily_income({**property_record, 'use_mode': mode})}g/day"
                        ),
                    )
                    for mode in ("Private", "Guesthouse", "Rental")
                ]
                mode_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Property Use",
                    mode_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.set_procedural_property_use(
                        property_id,
                        str(selected.value),
                    )
            elif choice.value == "sleep":
                self.sleep(force=True)
                return

    def procedural_business_price(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> int:
        type_id = str(building.get("type_id", ""))
        base = BUSINESS_BASE_PRICES.get(type_id, 5000)
        return base + self.procedural_town_development_rank(plan) * 900

    def procedural_business_manager_candidates(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> List[Dict[str, object]]:
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        candidates = [
            resident
            for resident in population.get("residents", {}).values()
            if str(resident.get("age_group")) in {"Adult", "Elder"}
            and (
                str(resident.get("workplace_building_id", "")) == str(building.get("id"))
                or str(resident.get("role")) in {"Settler", "Retiree"}
            )
        ]
        return sorted(candidates, key=lambda resident: str(resident.get("name", "")))

    def purchase_procedural_business(
        self,
        plan: Dict[str, object],
        building: Dict[str, object],
    ) -> bool:
        self.ensure_civic_economy_state()
        type_id = str(building.get("type_id", ""))
        if type_id not in BUSINESS_TYPES:
            return False
        business_id = self.business_id_for_building(plan, building)
        if business_id in self.state.player_businesses:
            return False
        if self.procedural_town_reputation(plan) < 40:
            self.set_message("Business ownership requires Welcome Friend reputation.")
            return False
        price = self.procedural_business_price(plan, building)
        if int(self.state.money) < price:
            self.set_message(f"Purchasing this business requires {price}g.")
            return False
        managers = self.procedural_business_manager_candidates(plan, building)
        existing_staff = [
            resident
            for resident in (
                self.procedural_settlement_population(
                    int(plan["chunk_x"]),
                    int(plan["chunk_y"]),
                )
                or {}
            ).get("residents", {}).values()
            if str(resident.get("workplace_building_id", ""))
            == str(building.get("id"))
        ]
        manager_id = str(managers[0].get("id", "")) if managers else ""
        self.state.money -= price
        self.state.player_businesses[business_id] = {
            "id": business_id,
            "town_key": self.civic_town_key(plan),
            "building_id": str(building["id"]),
            "type_id": type_id,
            "name": str(building.get("name", "Local Business")),
            "purchase_price": price,
            "purchased_day": str(getattr(self.state, "date_label", "")),
            "manager_resident_id": manager_id,
            "employee_ids": [
                str(resident.get("id"))
                for resident in existing_staff
                if str(resident.get("id")) != manager_id
            ][:8],
            "strategy": "Balanced",
            "wage_policy": "Standard",
            "supply_contract": "Reliable Supply",
            "last_income_ordinal": self.civic_date_ordinal(),
            "lifetime_income": 0,
            "upgrade_level": 0,
            "total_invested": 0,
            "active": True,
        }
        self.adjust_procedural_town_reputation(
            10,
            f"Invested in {building.get('name')}",
            plan,
        )
        self.autosave_with_message(
            f"Purchased {building.get('name')} for {price}g. Existing staff remain employed."
        )
        return True

    def procedural_business_daily_income(
        self,
        business: Dict[str, object],
    ) -> int:
        plan = self.civic_plan_for_key(str(business.get("town_key", "")))
        if not plan:
            return 0
        base = BUSINESS_BASE_INCOME.get(str(business.get("type_id")), 60)
        base += self.procedural_town_development_rank(plan) * 18
        upgrade_level = int(business.get("upgrade_level", 0))
        base = int(base * (100 + upgrade_level * 18) / 100)
        employee_count = len(business.get("employee_ids", []) or [])
        wage_policy = str(business.get("wage_policy", "Standard"))
        productivity = employee_count * (
            13 if wage_policy == "Generous"
            else 7 if wage_policy == "Training"
            else 10
        )
        wage_cost = employee_count * (
            16 if wage_policy == "Generous"
            else 7 if wage_policy == "Training"
            else 11
        )
        base += productivity - wage_cost
        if business.get("manager_resident_id"):
            population = self.procedural_settlement_population(
                int(plan["chunk_x"]),
                int(plan["chunk_y"]),
            ) or {}
            manager = population.get("residents", {}).get(
                str(business.get("manager_resident_id")),
                {},
            )
            base += 12 + max(0, int(manager.get("relationship", 0)) // 20)
        strategy = str(business.get("strategy", "Balanced"))
        if strategy == "Local Goods":
            base = int(base * 0.9)
        elif strategy == "Growth":
            base = int(base * 1.18)
        policy = str(
            self.ensure_procedural_town_politics(plan).get("current_policy", "")
        )
        if policy == "Market Investment":
            base = int(base * 1.12)
        contract = str(business.get("supply_contract", "Reliable Supply"))
        if contract == "Reliable Supply":
            base = int(base * 1.08)
        elif contract == "Essential Goods":
            base = int(base * 0.94)
        initiatives = set(
            self.ensure_procedural_town_politics(plan).get(
                "completed_initiatives",
                [],
            )
            or []
        )
        if "market_hall" in initiatives:
            base = int(base * 1.10)
        if (
            "shared_archive"
            in set(
                self.ensure_regional_council_state().get(
                    "completed_projects",
                    [],
                )
                or []
            )
            and str(business.get("type_id")) == "library"
        ):
            base = int(base * 1.20)
        return max(0, base)

    def procedural_business_employee_candidates(
        self,
        business: Dict[str, object],
    ) -> List[Dict[str, object]]:
        plan = self.civic_plan_for_key(str(business.get("town_key", "")))
        if not plan:
            return []
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        assigned = set(business.get("employee_ids", []) or [])
        assigned.add(str(business.get("manager_resident_id", "")))
        protected_roles = {"Mayor", "Doctor", "Nurse", "Well Keeper"}
        return sorted(
            [
                resident
                for resident in population.get("residents", {}).values()
                if str(resident.get("id")) not in assigned
                and str(resident.get("age_group")) in {"Adult", "Elder"}
                and str(resident.get("role")) not in protected_roles
            ],
            key=lambda resident: str(resident.get("name", "")),
        )

    def hire_procedural_business_employee(
        self,
        business_id: str,
        resident_id: str,
    ) -> bool:
        self.ensure_civic_economy_state()
        business = self.state.player_businesses.get(str(business_id))
        if not business:
            return False
        candidates = {
            str(resident.get("id")): resident
            for resident in self.procedural_business_employee_candidates(business)
        }
        resident = candidates.get(str(resident_id))
        if not resident:
            return False
        employee_ids = list(business.get("employee_ids", []) or [])
        if len(employee_ids) >= 8:
            return False
        employee_ids.append(str(resident_id))
        business["employee_ids"] = list(dict.fromkeys(employee_ids))
        resident["workplace_building_id"] = str(business.get("building_id", ""))
        if str(resident.get("role")) in {"Settler", "Retiree"}:
            resident["role"] = "Business Assistant"
            resident["profession_id"] = "business_assistant"
        plan = self.civic_plan_for_key(str(business.get("town_key", "")))
        if plan:
            try:
                resident["schedule"] = self.procedural_npc_builder().resident_schedule(
                    plan,
                    resident,
                    plan.get("buildings", {}),
                )
            except (KeyError, TypeError, ValueError):
                pass
            self.adjust_procedural_town_reputation(
                2,
                f"Created work for {resident.get('name')}",
                plan,
            )
        self.autosave_with_message(
            f"Hired {resident.get('name')} at {business.get('name')}."
        )
        return True

    def set_procedural_business_wage_policy(
        self,
        business_id: str,
        wage_policy: str,
    ) -> bool:
        self.ensure_civic_economy_state()
        business = self.state.player_businesses.get(str(business_id))
        if not business or wage_policy not in BUSINESS_WAGE_POLICIES:
            return False
        business["wage_policy"] = wage_policy
        return True

    def set_procedural_business_supply_contract(
        self,
        business_id: str,
        contract: str,
    ) -> bool:
        self.ensure_civic_economy_state()
        business = self.state.player_businesses.get(str(business_id))
        if not business or contract not in BUSINESS_SUPPLY_CONTRACTS:
            return False
        business["supply_contract"] = contract
        return True

    def procedural_business_upgrade_cost(
        self,
        business: Dict[str, object],
    ) -> int:
        level = int(business.get("upgrade_level", 0))
        return 2200 + level * 1800

    def upgrade_procedural_business(self, business_id: str) -> bool:
        self.ensure_civic_economy_state()
        business = self.state.player_businesses.get(str(business_id))
        if not business:
            return False
        level = int(business.get("upgrade_level", 0))
        if level >= len(BUSINESS_UPGRADE_NAMES):
            self.set_message("This business is fully upgraded.")
            return False
        cost = self.procedural_business_upgrade_cost(business)
        if int(self.state.money) < cost:
            self.set_message(f"The next business upgrade requires {cost}g.")
            return False
        self.state.money -= cost
        business["upgrade_level"] = level + 1
        business["total_invested"] = int(
            business.get("total_invested", 0)
        ) + cost
        plan = self.civic_plan_for_key(str(business.get("town_key", "")))
        if plan:
            community = self.ensure_procedural_town_community(plan)
            community["development_points"] = int(
                community.get("development_points", 0)
            ) + 3
        self.autosave_with_message(
            f"Completed {BUSINESS_UPGRADE_NAMES[level]} at {business.get('name')}."
        )
        return True

    def set_procedural_business_active(
        self,
        business_id: str,
        active: bool,
    ) -> bool:
        self.ensure_civic_economy_state()
        business = self.state.player_businesses.get(str(business_id))
        if not business:
            return False
        business["active"] = bool(active)
        business["last_income_ordinal"] = self.civic_date_ordinal()
        self.autosave_with_message(
            f"{business.get('name')} is now "
            f"{'operating' if active else 'temporarily closed'}."
        )
        return True

    def set_procedural_business_strategy(
        self,
        business_id: str,
        strategy: str,
    ) -> bool:
        self.ensure_civic_economy_state()
        business = self.state.player_businesses.get(str(business_id))
        if not business or strategy not in BUSINESS_STRATEGIES:
            return False
        business["strategy"] = strategy
        self.autosave_with_message(
            f"{business.get('name')} now follows a {strategy} strategy."
        )
        return True

    def appoint_procedural_business_manager(
        self,
        business_id: str,
        resident_id: str,
    ) -> bool:
        self.ensure_civic_economy_state()
        business = self.state.player_businesses.get(str(business_id))
        if not business:
            return False
        plan = self.civic_plan_for_key(str(business["town_key"]))
        building = (
            plan.get("buildings", {}).get(str(business["building_id"]))
            if plan
            else None
        )
        if not plan or not isinstance(building, dict):
            return False
        candidate_ids = {
            str(resident.get("id"))
            for resident in self.procedural_business_manager_candidates(plan, building)
        }
        if str(resident_id) not in candidate_ids:
            return False
        previous_manager = str(business.get("manager_resident_id", "") or "")
        employees = [
            str(employee_id)
            for employee_id in business.get("employee_ids", []) or []
            if str(employee_id) != str(resident_id)
        ]
        if previous_manager and previous_manager != str(resident_id):
            employees.append(previous_manager)
        business["employee_ids"] = list(dict.fromkeys(employees))[:8]
        business["manager_resident_id"] = str(resident_id)
        return True

    def discovered_procedural_town_plans(self) -> List[Dict[str, object]]:
        return sorted(
            [
                plan
                for plan in self.ensure_wilderness_settlements().values()
                if isinstance(plan, dict)
                and str(plan.get("source", "")) == "procedural_wilderness"
                and bool(plan.get("discovered"))
            ],
            key=lambda plan: str(plan.get("name", "")),
        )

    def ensure_regional_contract_state(self) -> Dict[str, object]:
        self.ensure_civic_economy_state()
        state = self.state.civic_profile.get("regional_contracts")
        if not isinstance(state, dict):
            state = {}
            self.state.civic_profile["regional_contracts"] = state
        state.setdefault("board_key", "")
        state.setdefault("contracts", {})
        state.setdefault("completed_ids", [])
        state.setdefault("journey_log", [])
        state.setdefault("contracts_completed", 0)
        if not isinstance(state.get("contracts"), dict):
            state["contracts"] = {}
        if not isinstance(state.get("completed_ids"), list):
            state["completed_ids"] = []
        if not isinstance(state.get("journey_log"), list):
            state["journey_log"] = []
        return state

    def regional_contract_board_key(self) -> str:
        week = (max(1, int(getattr(self.state, "day", 1))) - 1) // 7 + 1
        return (
            f"{int(getattr(self.state, 'year', 1))}-"
            f"{int(getattr(self.state, 'month', 1))}-W{week}"
        )

    def refresh_regional_contract_board(self) -> Dict[str, object]:
        state = self.ensure_regional_contract_state()
        board_key = self.regional_contract_board_key()
        if str(state.get("board_key", "")) == board_key:
            return state
        retained = {
            str(contract_id): dict(contract)
            for contract_id, contract in state.get("contracts", {}).items()
            if isinstance(contract, dict)
            and str(contract.get("status", "")) in {"active", "completed"}
        }
        towns = self.discovered_procedural_town_plans()
        generated: Dict[str, Dict[str, object]] = {}
        for index, plan in enumerate(towns):
            town_key = self.civic_town_key(plan)
            market = self.procedural_town_market_profile(plan)
            identity = self.procedural_town_identity(plan)
            seed = stable_text_seed(f"{board_key}:{town_key}:contracts")
            demand = str(market.get("demand", "Wood"))
            supply_quantity = 4 + seed % 5
            supply_id = f"contract:{board_key}:{town_key}:supply"
            generated[supply_id] = {
                "id": supply_id,
                "type": "supply",
                "title": f"{plan.get('name')} Supply Order",
                "description": (
                    f"Deliver {supply_quantity} {demand} to meet this week's "
                    f"market shortage in {plan.get('name')}."
                ),
                "town_key": town_key,
                "route_id": "",
                "item": demand,
                "quantity": supply_quantity,
                "reward": 140 + supply_quantity * 32,
                "reputation_reward": 5,
                "status": "available",
                "posted_key": board_key,
                "accepted_day": "",
                "completed_day": "",
            }
            if index % 2 == 0:
                item = "Wood" if seed % 2 == 0 else "Stone"
                quantity = 10 + (seed // 7) % 9
                works_id = f"contract:{board_key}:{town_key}:works"
                generated[works_id] = {
                    "id": works_id,
                    "type": "public_works",
                    "title": f"{plan.get('name')} Public Works",
                    "description": (
                        f"The town needs {quantity} {item} for roads, signs, "
                        "repairs, and shared facilities."
                    ),
                    "town_key": town_key,
                    "route_id": "",
                    "item": item,
                    "quantity": quantity,
                    "reward": 260 + quantity * 22,
                    "reputation_reward": 8,
                    "status": "available",
                    "posted_key": board_key,
                    "accepted_day": "",
                    "completed_day": "",
                }
            if len(towns) > 1 and index % 2 == 1:
                courier_id = f"contract:{board_key}:{town_key}:courier"
                generated[courier_id] = {
                    "id": courier_id,
                    "type": "courier",
                    "title": f"Courier to {plan.get('name')}",
                    "description": (
                        f"Carry sealed council correspondence to {plan.get('name')} "
                        f"and report at the local contract board."
                    ),
                    "town_key": town_key,
                    "route_id": "",
                    "item": "",
                    "quantity": 0,
                    "reward": 220 + max(1, abs(int(plan["chunk_x"])) + abs(int(plan["chunk_y"]))) * 18,
                    "reputation_reward": 4,
                    "status": "available",
                    "posted_key": board_key,
                    "accepted_day": "",
                    "completed_day": "",
                }
            event = self.procedural_town_active_event(plan)
            if event:
                exports = list(identity.get("exports", ()) or ["Wildflowers"])
                item = str(exports[seed % len(exports)])
                festival_id = f"contract:{board_key}:{town_key}:festival"
                generated[festival_id] = {
                    "id": festival_id,
                    "type": "festival_trade",
                    "title": f"{event.get('name', 'Festival')} Provisioning",
                    "description": (
                        f"Bring 5 {item} to support {plan.get('name')}'s "
                        f"{event.get('name', 'community gathering')}."
                    ),
                    "town_key": town_key,
                    "route_id": "",
                    "item": item,
                    "quantity": 5,
                    "reward": 360,
                    "reputation_reward": 7,
                    "status": "available",
                    "posted_key": board_key,
                    "accepted_day": "",
                    "completed_day": "",
                }
        for route in self.state.player_trade_routes.values():
            if not route.get("active"):
                continue
            self.ensure_player_trade_route_caravan(route)
            route_id = str(route.get("id", ""))
            contract_id = f"contract:{board_key}:{route_id}:escort"
            generated[contract_id] = {
                "id": contract_id,
                "type": "escort",
                "title": f"Escort {route.get('caravan_name')}",
                "description": (
                    f"Travel with {route.get('caravan_name')} between its terminal "
                    "towns and help the crew complete a safe run."
                ),
                "town_key": str(route.get("destination_town_key", "")),
                "route_id": route_id,
                "item": "",
                "quantity": 0,
                "reward": 320 + int(route.get("distance", 1)) * 28,
                "reputation_reward": 6,
                "status": "available",
                "posted_key": board_key,
                "accepted_day": "",
                "completed_day": "",
            }
        retained.update(generated)
        state["contracts"] = retained
        state["board_key"] = board_key
        return state

    def regional_contracts(
        self,
        statuses: Optional[Tuple[str, ...]] = None,
    ) -> List[Dict[str, object]]:
        state = self.refresh_regional_contract_board()
        contracts = [
            contract
            for contract in state.get("contracts", {}).values()
            if isinstance(contract, dict)
            and (
                statuses is None
                or str(contract.get("status", "")) in set(statuses)
            )
        ]
        return sorted(
            contracts,
            key=lambda contract: (
                {"active": 0, "available": 1, "completed": 2}.get(
                    str(contract.get("status", "")),
                    3,
                ),
                str(contract.get("title", "")),
            ),
        )

    def accept_regional_contract(self, contract_id: str) -> bool:
        state = self.refresh_regional_contract_board()
        contract = state.get("contracts", {}).get(str(contract_id))
        active_count = sum(
            1
            for record in state.get("contracts", {}).values()
            if isinstance(record, dict) and record.get("status") == "active"
        )
        if not contract or contract.get("status") != "available":
            return False
        if active_count >= REGIONAL_CONTRACT_LIMIT:
            self.set_message(
                f"You can manage up to {REGIONAL_CONTRACT_LIMIT} regional contracts at once."
            )
            return False
        contract["status"] = "active"
        contract["accepted_day"] = str(getattr(self.state, "date_label", ""))
        self.autosave_with_message(f"Accepted: {contract.get('title')}.")
        return True

    def current_civic_town_key(self) -> str:
        plan = self.current_procedural_town_plan()
        return self.civic_town_key(plan) if plan else ""

    def can_complete_regional_contract(
        self,
        contract: Dict[str, object],
        journey_route_id: str = "",
    ) -> Tuple[bool, str]:
        if str(contract.get("status", "")) != "active":
            return False, "Contract is not active."
        contract_type = str(contract.get("type", ""))
        if contract_type == "escort":
            if str(contract.get("route_id", "")) != str(journey_route_id):
                return False, "Travel with the assigned caravan."
            return True, "Escort completed."
        if self.current_civic_town_key() != str(contract.get("town_key", "")):
            plan = self.civic_plan_for_key(str(contract.get("town_key", ""))) or {}
            return False, f"Report at {plan.get('name', 'the destination town')}."
        if contract_type in {"supply", "public_works", "festival_trade"}:
            item = str(contract.get("item", ""))
            quantity = int(contract.get("quantity", 0))
            carried = int(self.state.inventory.get(item, 0))
            if carried < quantity:
                return False, f"Carry {quantity} {item}. Current: {carried}."
        return True, "Ready to complete."

    def complete_regional_contract(
        self,
        contract_id: str,
        journey_route_id: str = "",
    ) -> bool:
        state = self.refresh_regional_contract_board()
        contract = state.get("contracts", {}).get(str(contract_id))
        if not isinstance(contract, dict):
            return False
        ready, reason = self.can_complete_regional_contract(
            contract,
            journey_route_id=journey_route_id,
        )
        if not ready:
            self.set_message(reason)
            return False
        if str(contract.get("type", "")) in {
            "supply",
            "public_works",
            "festival_trade",
        }:
            item = str(contract.get("item", ""))
            quantity = int(contract.get("quantity", 0))
            self.state.inventory[item] = max(
                0,
                int(self.state.inventory.get(item, 0)) - quantity,
            )
            if self.state.inventory[item] <= 0:
                self.state.inventory.pop(item, None)
        reward = int(contract.get("reward", 0))
        self.state.money += reward
        contract["status"] = "completed"
        contract["completed_day"] = str(getattr(self.state, "date_label", ""))
        contract_id = str(contract.get("id", contract_id))
        state["completed_ids"] = (
            list(state.get("completed_ids", []) or []) + [contract_id]
        )[-80:]
        state["contracts_completed"] = int(
            state.get("contracts_completed", 0)
        ) + 1
        plan = self.civic_plan_for_key(str(contract.get("town_key", "")))
        if plan:
            self.adjust_procedural_town_reputation(
                int(contract.get("reputation_reward", 0)),
                f"Completed regional contract: {contract.get('title')}",
                plan,
            )
            community = self.ensure_procedural_town_community(plan)
            community["development_points"] = int(
                community.get("development_points", 0)
            ) + (
                4
                if str(contract.get("type", "")) == "public_works"
                else 2
            )
        self.autosave_with_message(
            f"Completed {contract.get('title')}. Earned {reward}g."
        )
        return True

    def regional_contract_lines(
        self,
        contract: Dict[str, object],
    ) -> List[str]:
        plan = self.civic_plan_for_key(str(contract.get("town_key", ""))) or {}
        ready, reason = self.can_complete_regional_contract(contract)
        lines = [
            str(contract.get("title", "REGIONAL CONTRACT")).upper(),
            "",
            str(contract.get("description", "")),
            "",
            f"Type: {str(contract.get('type', '')).replace('_', ' ').title()}",
            f"Destination: {plan.get('name', 'regional route')}",
            f"Status: {contract.get('status', 'available')}",
            f"Reward: {contract.get('reward', 0)}g",
            f"Reputation: +{contract.get('reputation_reward', 0)}",
        ]
        if contract.get("item"):
            item = str(contract.get("item"))
            lines.append(
                f"Goods: {contract.get('quantity', 0)} {item} "
                f"(carried {self.state.inventory.get(item, 0)})"
            )
        if contract.get("status") == "active":
            lines.extend(["", f"Completion: {'ready' if ready else reason}"])
        return lines

    def show_regional_contract_menu(self) -> None:
        while True:
            contracts = self.regional_contracts(
                ("active", "available", "completed")
            )
            items = [
                MenuItem(
                    label=str(contract.get("title", "Regional Contract")),
                    value=str(contract.get("id", "")),
                    enabled=True,
                    hint=(
                        f"{contract.get('status')} | {contract.get('reward', 0)}g"
                    ),
                )
                for contract in contracts
            ]
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(
                "Regional Contracts",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return
            contract = self.refresh_regional_contract_board().get(
                "contracts",
                {},
            ).get(str(choice.value))
            if not isinstance(contract, dict):
                continue
            actions = [
                MenuItem(label="Details", value="details", enabled=True),
            ]
            if contract.get("status") == "available":
                actions.append(
                    MenuItem(label="Accept", value="accept", enabled=True)
                )
            elif contract.get("status") == "active":
                ready, reason = self.can_complete_regional_contract(contract)
                actions.append(
                    MenuItem(
                        label="Complete",
                        value="complete",
                        enabled=ready,
                        hint=reason,
                    )
                )
            actions.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            action = self.vertical_panel_select(
                str(contract.get("title", "Regional Contract")),
                actions,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not action or action.value == MENU_BACK:
                continue
            if action.value == "details":
                self.vertical_panel_view(
                    str(contract.get("title", "Regional Contract")),
                    self.regional_contract_lines(contract),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif action.value == "accept":
                self.accept_regional_contract(str(contract.get("id", "")))
            elif action.value == "complete":
                self.complete_regional_contract(str(contract.get("id", "")))

    def regional_journal_overview_lines(self) -> List[str]:
        self.ensure_civic_economy_state()
        self.update_player_trade_caravans()
        towns = self.discovered_procedural_town_plans()
        active_routes = [
            route
            for route in self.state.player_trade_routes.values()
            if route.get("active")
        ]
        active_contracts = self.regional_contracts(("active",))
        council = self.ensure_regional_council_state()
        lines = [
            "REGIONAL JOURNAL",
            "",
            f"Known wilderness towns: {len(towns)}",
            f"Owned residences: {len(self.state.player_properties)}",
            f"Owned businesses: {len(self.state.player_businesses)}",
            f"Active trade routes: {len(active_routes)}",
            f"Active regional contracts: {len(active_contracts)}/{REGIONAL_CONTRACT_LIMIT}",
            (
                f"Regional council: delegate, {council.get('influence', 0)} influence"
                if council.get("member")
                else "Regional council: not joined"
            ),
            "",
            "Town network:",
        ]
        if not towns:
            lines.append("- No wilderness towns have been discovered.")
        for plan in towns:
            key = self.civic_town_key(plan)
            market = self.procedural_town_market_profile(plan)
            routes = sum(
                1
                for route in active_routes
                if key
                in {
                    str(route.get("source_town_key", "")),
                    str(route.get("destination_town_key", "")),
                }
            )
            lines.extend(
                [
                    f"- {plan.get('name')} ({plan.get('chunk_x')}, {plan.get('chunk_y')})",
                    f"  {self.procedural_town_development_tier(plan)} | "
                    f"{self.procedural_town_reputation_label(self.procedural_town_reputation(plan))}",
                    f"  Seeking {market.get('demand', 'general goods')} | routes {routes}",
                ]
            )
        if active_routes:
            lines.extend(["", "Caravans today:"])
            for route in active_routes:
                state = self.player_trade_route_caravan_state(route)
                lines.append(
                    f"- {route.get('caravan_name')}: {state.get('status')} "
                    f"({route.get('good')})"
                )
        if council.get("completed_projects"):
            lines.extend(["", "Regional works:"])
            for project_id in council.get("completed_projects", []):
                project = REGIONAL_PROJECTS.get(str(project_id), {})
                lines.append(f"- {project.get('name', project_id)}")
        return lines

    def regional_journal_opportunity_lines(self) -> List[str]:
        self.ensure_civic_economy_state()
        towns = self.discovered_procedural_town_plans()
        lines = [
            "REGIONAL OPPORTUNITIES",
            "",
            "Useful openings gathered from town records, markets, and public notices.",
            "",
        ]
        if not towns:
            lines.append("- Explore the wilderness to discover a regional town.")
            return lines
        for plan in towns:
            key = self.civic_town_key(plan)
            market = self.procedural_town_market_profile(plan)
            reputation = self.procedural_town_reputation(plan)
            town_properties = [
                record
                for record in self.state.player_properties.values()
                if str(record.get("town_key", "")) == key
            ]
            town_businesses = [
                record
                for record in self.state.player_businesses.values()
                if str(record.get("town_key", "")) == key
            ]
            story_status = self.procedural_town_story_status(plan)
            notes = [
                f"Market buyers seek {market.get('demand', 'general goods')}.",
            ]
            if reputation < 40:
                notes.append("Local work and conversation can establish a welcome reputation.")
            elif not town_properties:
                notes.append("Your standing may support purchasing or building a residence.")
            if town_businesses:
                unlinked = not any(
                    key
                    in {
                        str(route.get("source_town_key", "")),
                        str(route.get("destination_town_key", "")),
                    }
                    for route in self.state.player_trade_routes.values()
                )
                if unlinked and len(towns) > 1:
                    notes.append("An owned business here could anchor a new trade route.")
            if story_status:
                notes.append(f"Community story: {story_status}.")
            lines.append(f"{plan.get('name')}:")
            lines.extend(f"- {note}" for note in notes[:4])
            lines.append("")
        eligible, reason = self.regional_council_eligibility()
        council = self.ensure_regional_council_state()
        if not council.get("member"):
            lines.extend(
                [
                    "Regional council:",
                    f"- {'Eligible to join.' if eligible else reason + '.'}",
                ]
            )
        return lines

    def regional_journal_town_lines(
        self,
        plan: Dict[str, object],
    ) -> List[str]:
        self.ensure_civic_economy_state()
        self.update_player_trade_caravans()
        key = self.civic_town_key(plan)
        community = self.ensure_procedural_town_community(plan)
        identity = self.procedural_town_identity(plan)
        market = self.procedural_town_market_profile(plan)
        event = self.procedural_town_active_event(plan)
        politics = self.ensure_procedural_town_politics(plan)
        properties = [
            record
            for record in self.state.player_properties.values()
            if str(record.get("town_key", "")) == key
        ]
        businesses = [
            record
            for record in self.state.player_businesses.values()
            if str(record.get("town_key", "")) == key
        ]
        routes = [
            route
            for route in self.state.player_trade_routes.values()
            if key
            in {
                str(route.get("source_town_key", "")),
                str(route.get("destination_town_key", "")),
            }
        ]
        lines = [
            str(plan.get("name", "Wilderness Town")).upper(),
            "",
            f"Location: wilderness chunk {key}",
            f"Discovered: {plan.get('discovered_day', 'unknown')}",
            f"Character: {identity.get('industry', 'regional settlement')}",
            f"Motto: {identity.get('motto', '')}",
            f"Standing: {self.procedural_town_reputation_label(self.procedural_town_reputation(plan))} "
            f"({self.procedural_town_reputation(plan)})",
            f"Development: {self.procedural_town_development_tier(plan)} "
            f"({community.get('development_points', 0)} points)",
            "",
            "Today:",
            f"- Market surplus: {market.get('surplus', 'none')}",
            f"- Market demand: {market.get('demand', 'none')}",
            f"- Event: {event.get('name', 'none') if event else 'none'}",
            f"- Policy: {politics.get('current_policy', 'Public Works')}",
            f"- Election: {self.procedural_election_phase(plan)}",
            f"- Community story: {self.procedural_town_story_status(plan)}",
            "",
            "Your presence:",
            f"- Residences: {len(properties)}",
            f"- Businesses: {len(businesses)}",
            f"- Connected routes: {len(routes)}",
        ]
        for record in properties:
            lines.append(
                f"  Residence: {record.get('name')} | "
                f"{record.get('use_mode', 'Private')} | upgrade {record.get('upgrade_level', 0)}"
            )
        for record in businesses:
            lines.append(
                f"  Business: {record.get('name')} | {record.get('strategy', 'Balanced')} | "
                f"{'open' if record.get('active', True) else 'paused'}"
            )
        for route in routes:
            caravan = self.player_trade_route_caravan_state(route)
            lines.append(
                f"  Caravan: {route.get('caravan_name')} | {caravan.get('status')} | "
                f"{route.get('caravan_deliveries', 0)} deliveries"
            )
        initiatives = list(politics.get("completed_initiatives", []) or [])
        if initiatives:
            lines.extend(["", "Visible local works:"])
            for initiative_id in initiatives:
                lines.append(
                    f"- {CIVIC_INITIATIVES.get(str(initiative_id), {}).get('name', initiative_id)}"
                )
        latest = list(community.get("story_log", []) or [])
        if latest:
            lines.extend(["", "Recent record:", f"- {latest[-1]}"])
        return lines

    def show_regional_journal_menu(self) -> None:
        while True:
            towns = self.discovered_procedural_town_plans()
            items = [
                MenuItem(label="Regional overview", value="overview", enabled=True),
                MenuItem(label="Opportunities", value="opportunities", enabled=True),
                MenuItem(
                    label="Regional contracts",
                    value="contracts",
                    enabled=True,
                    hint=f"{len(self.regional_contracts(('active',)))} active",
                ),
            ]
            items.extend(
                MenuItem(
                    label=str(plan.get("name", "Wilderness Town")),
                    value=f"town:{self.civic_town_key(plan)}",
                    enabled=True,
                    hint=self.procedural_town_development_tier(plan),
                )
                for plan in towns
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(
                "Regional Journal",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "overview":
                self.vertical_panel_view(
                    "Regional Overview",
                    self.regional_journal_overview_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "opportunities":
                self.vertical_panel_view(
                    "Regional Opportunities",
                    self.regional_journal_opportunity_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "contracts":
                self.show_regional_contract_menu()
                continue
            if str(choice.value).startswith("town:"):
                plan = self.civic_plan_for_key(str(choice.value)[5:])
                if plan:
                    self.vertical_panel_view(
                        str(plan.get("name", "Town Record")),
                        self.regional_journal_town_lines(plan),
                        LEFT_PANEL_WIDTH,
                        LEFT_PANEL_HEIGHT,
                    )

    def ensure_regional_council_state(self) -> Dict[str, object]:
        self.ensure_civic_economy_state()
        council = self.state.civic_profile.get("regional_council")
        if not isinstance(council, dict):
            council = {}
            self.state.civic_profile["regional_council"] = council
        council.setdefault("member", False)
        council.setdefault("delegate_town_key", "")
        council.setdefault("joined_day", "")
        council.setdefault("influence", 0)
        council.setdefault("treasury", 0)
        council.setdefault("completed_projects", [])
        council.setdefault("agreement_log", [])
        council.setdefault("proposal_log", [])
        council.setdefault("last_session_month", "")
        council.setdefault("last_budget_ordinal", self.civic_date_ordinal())
        return council

    def regional_council_eligibility(self) -> Tuple[bool, str]:
        towns = self.discovered_procedural_town_plans()
        connected_keys = {
            str(route.get("source_town_key", ""))
            for route in self.state.player_trade_routes.values()
            if route.get("active")
        } | {
            str(route.get("destination_town_key", ""))
            for route in self.state.player_trade_routes.values()
            if route.get("active")
        }
        trusted = sum(
            1
            for plan in towns
            if self.procedural_town_reputation(plan) >= 75
        )
        if len(towns) < 3:
            return False, "Discover at least three generated towns"
        if len(connected_keys) < 2:
            return False, "Operate a trade route connecting two towns"
        if trusted < 2 and not self.state.civic_profile.get("offices_held"):
            return False, "Earn trust in two towns or hold local office"
        return True, "Eligible"

    def join_regional_council(self, delegate_town_key: str) -> bool:
        council = self.ensure_regional_council_state()
        eligible, reason = self.regional_council_eligibility()
        plan = self.civic_plan_for_key(delegate_town_key)
        if (
            not eligible
            or not plan
            or not plan.get("discovered")
            or self.procedural_town_reputation(plan) < 75
        ):
            self.set_message(reason)
            return False
        council["member"] = True
        council["delegate_town_key"] = str(delegate_town_key)
        council["joined_day"] = str(getattr(self.state, "date_label", ""))
        council["influence"] = max(10, int(council.get("influence", 0)))
        self.autosave_with_message(
            f"Joined the regional council as {plan.get('name')}'s delegate."
        )
        return True

    def establish_regional_agreement(
        self,
        route_id: str,
        agreement_type: str,
    ) -> bool:
        council = self.ensure_regional_council_state()
        route = self.state.player_trade_routes.get(str(route_id))
        if (
            not council.get("member")
            or not route
            or agreement_type not in REGIONAL_AGREEMENTS
            or str(route.get("agreement_type", "Commercial Route"))
            != "Commercial Route"
        ):
            return False
        cost = 450
        if int(self.state.money) < cost:
            return False
        self.state.money -= cost
        route["agreement_type"] = agreement_type
        council["influence"] = int(council.get("influence", 0)) + 4
        source = self.civic_plan_for_key(str(route.get("source_town_key", ""))) or {}
        destination = self.civic_plan_for_key(
            str(route.get("destination_town_key", ""))
        ) or {}
        council["agreement_log"] = (
            list(council.get("agreement_log", []) or [])
            + [
                f"{agreement_type}: {source.get('name', 'Town')} and "
                f"{destination.get('name', 'Town')}"
            ]
        )[-30:]
        self.autosave_with_message(
            f"Established a {agreement_type} across the {route.get('good')} route."
        )
        return True

    def contribute_to_regional_treasury(self, amount: int) -> bool:
        council = self.ensure_regional_council_state()
        amount = max(1, int(amount))
        if not council.get("member") or int(self.state.money) < amount:
            return False
        self.state.money -= amount
        council["treasury"] = int(council.get("treasury", 0)) + amount
        council["influence"] = int(council.get("influence", 0)) + min(
            5,
            max(1, amount // 500),
        )
        return True

    def regional_project_support(
        self,
        project_id: str,
    ) -> int:
        council = self.ensure_regional_council_state()
        towns = self.discovered_procedural_town_plans()
        trusted = sum(
            1
            for plan in towns
            if self.procedural_town_reputation(plan) >= 75
        )
        agreements = sum(
            1
            for route in self.state.player_trade_routes.values()
            if str(route.get("agreement_type", "Commercial Route"))
            != "Commercial Route"
        )
        project_bias = stable_text_seed(
            f"{project_id}:{len(towns)}:{agreements}:regional-support"
        ) % 11
        return min(
            100,
            35
            + trusted * 10
            + agreements * 8
            + int(council.get("influence", 0)) // 2
            + project_bias,
        )

    def complete_regional_project(self, project_id: str) -> bool:
        council = self.ensure_regional_council_state()
        project = REGIONAL_PROJECTS.get(str(project_id))
        completed = set(council.get("completed_projects", []) or [])
        month_key = f"{int(self.state.year)}-{int(self.state.month)}"
        support = self.regional_project_support(project_id)
        if (
            not council.get("member")
            or not project
            or project_id in completed
            or council.get("last_session_month") == month_key
            or int(council.get("treasury", 0)) < int(project["cost"])
            or support < 60
        ):
            return False
        council["treasury"] = int(council.get("treasury", 0)) - int(
            project["cost"]
        )
        council["completed_projects"] = (
            list(council.get("completed_projects", []) or []) + [project_id]
        )
        council["last_session_month"] = month_key
        council["influence"] = int(council.get("influence", 0)) + 6
        council["proposal_log"] = (
            list(council.get("proposal_log", []) or [])
            + [
                f"{getattr(self.state, 'date_label', '')}: {project['name']} "
                f"approved with {support}% support"
            ]
        )[-20:]
        for plan in self.discovered_procedural_town_plans():
            community = self.ensure_procedural_town_community(plan)
            community["development_points"] = int(
                community.get("development_points", 0)
            ) + 3
        self.autosave_with_message(
            f"The regional council approved {project['name']} with {support}% support."
        )
        return True

    def regional_council_lines(self) -> List[str]:
        council = self.ensure_regional_council_state()
        delegate_plan = self.civic_plan_for_key(
            str(council.get("delegate_town_key", ""))
        )
        lines = [
            "REGIONAL COUNCIL",
            "",
            f"Membership: {'delegate' if council.get('member') else 'not joined'}",
            f"Delegation: {delegate_plan.get('name') if delegate_plan else 'none'}",
            f"Influence: {council.get('influence', 0)}",
            f"Treasury: {council.get('treasury', 0)}g",
            f"Agreements: {len(council.get('agreement_log', []) or [])}",
            f"Regional projects: {len(council.get('completed_projects', []) or [])}",
        ]
        if council.get("proposal_log"):
            lines.extend(["", f"Latest: {council['proposal_log'][-1]}"])
        return lines

    def procedural_town_has_regional_agreement(
        self,
        plan: Dict[str, object],
        agreement_type: str,
    ) -> bool:
        town_key = self.civic_town_key(plan)
        return any(
            str(route.get("agreement_type", "")) == agreement_type
            and town_key
            in {
                str(route.get("source_town_key", "")),
                str(route.get("destination_town_key", "")),
            }
            for route in self.state.player_trade_routes.values()
        )

    def civic_travel_costs(
        self,
        destination_town_key: str,
    ) -> Tuple[int, int, bool]:
        destination = self.civic_plan_for_key(destination_town_key)
        if not destination:
            return 0, 0, False
        current_plan = self.current_procedural_town_plan()
        if current_plan:
            source_x = int(current_plan["chunk_x"])
            source_y = int(current_plan["chunk_y"])
            source_key = self.civic_town_key(current_plan)
        elif str(getattr(self.state, "location", "")) in {
            "Wilderness",
            "WildernessOverworld",
            "ProceduralSettlementInterior",
        }:
            source_x = int(getattr(self.state, "wilderness_chunk_x", 0))
            source_y = int(getattr(self.state, "wilderness_chunk_y", 0))
            source_key = settlement_chunk_key(source_x, source_y)
        else:
            source_x = source_y = 0
            source_key = settlement_chunk_key(0, 0)
        distance = abs(int(destination["chunk_x"]) - source_x)
        distance += abs(int(destination["chunk_y"]) - source_y)
        stamina = max(0, distance * 2)
        minutes = max(0, distance * 10)
        connected = any(
            route.get("active")
            and {
                str(route.get("source_town_key", "")),
                str(route.get("destination_town_key", "")),
            }
            == {source_key, str(destination_town_key)}
            for route in self.state.player_trade_routes.values()
        )
        projects = set(
            self.ensure_regional_council_state().get(
                "completed_projects",
                [],
            )
            or []
        )
        discounted = connected or "waystation_network" in projects
        if discounted:
            stamina = (stamina + 1) // 2
            minutes = (minutes + 1) // 2
        return stamina, minutes, discounted

    def travel_to_civic_town(
        self,
        destination_town_key: str,
        property_id: str = "",
    ) -> bool:
        destination = self.civic_plan_for_key(destination_town_key)
        if not destination or not destination.get("discovered"):
            return False
        stamina, minutes, discounted = self.civic_travel_costs(
            destination_town_key
        )
        if int(self.state.stamina) < stamina:
            self.set_message(f"This journey needs {stamina} stamina.")
            return False
        self.state.stamina = max(0, int(self.state.stamina) - stamina)
        if minutes:
            self.advance_time(minutes)
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(
            int(destination["chunk_x"]),
            int(destination["chunk_y"]),
            entry_side="center",
        )
        destination_label = str(destination.get("name", "the destination town"))
        if property_id:
            property_record = self.state.player_properties.get(str(property_id))
            building = (
                destination.get("buildings", {}).get(
                    str(property_record.get("building_id", ""))
                )
                if property_record
                else None
            )
            if isinstance(building, dict):
                self.state.player_x = int(building.get("access_x", self.state.player_x))
                self.state.player_y = int(building.get("access_y", self.state.player_y))
                self.enter_procedural_town_building(building)
                destination_label = str(property_record.get("name", destination_label))
        self.autosave_with_message(
            f"Traveled to {destination_label}. Cost: {stamina} stamina, "
            f"{minutes} minutes"
            f"{' using the regional network' if discounted else ''}."
        )
        return True

    def civic_travel_menu(self) -> None:
        destinations: List[MenuItem] = []
        for property_id, record in self.state.player_properties.items():
            plan = self.civic_plan_for_key(str(record.get("town_key", "")))
            if not plan:
                continue
            stamina, minutes, discounted = self.civic_travel_costs(
                str(record.get("town_key", ""))
            )
            destinations.append(MenuItem(
                label=str(record.get("name")),
                value=f"property:{property_id}",
                enabled=self.state.stamina >= stamina,
                hint=(
                    f"{stamina} stamina, {minutes} min"
                    f"{' | network' if discounted else ''}"
                ),
            ))
        owned_town_keys = {
            str(record.get("town_key", ""))
            for record in self.state.player_properties.values()
        }
        connected_keys = {
            str(route.get("source_town_key", ""))
            for route in self.state.player_trade_routes.values()
            if route.get("active")
        } | {
            str(route.get("destination_town_key", ""))
            for route in self.state.player_trade_routes.values()
            if route.get("active")
        }
        for town_key in sorted(connected_keys - owned_town_keys):
            plan = self.civic_plan_for_key(town_key)
            if not plan:
                continue
            stamina, minutes, discounted = self.civic_travel_costs(town_key)
            destinations.append(MenuItem(
                label=str(plan.get("name")),
                value=f"town:{town_key}",
                enabled=self.state.stamina >= stamina,
                hint=(
                    f"{stamina} stamina, {minutes} min"
                    f"{' | network' if discounted else ''}"
                ),
            ))
        destinations.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(
            "Civic Travel Network",
            destinations,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if not choice or choice.value == MENU_BACK:
            return
        kind, value = str(choice.value).split(":", 1)
        if kind == "property":
            record = self.state.player_properties.get(value)
            if record:
                self.travel_to_civic_town(
                    str(record.get("town_key", "")),
                    property_id=value,
                )
        else:
            self.travel_to_civic_town(value)

    def regional_council_menu(self) -> None:
        while True:
            council = self.ensure_regional_council_state()
            eligible, reason = self.regional_council_eligibility()
            items = [
                MenuItem(label="Council report", value="report", enabled=True),
                MenuItem(
                    label="Join regional council",
                    value="join",
                    enabled=eligible and not council.get("member"),
                    hint=reason,
                ),
                MenuItem(
                    label="Establish town agreement",
                    value="agreement",
                    enabled=bool(council.get("member"))
                    and any(
                        str(route.get("agreement_type", "Commercial Route"))
                        == "Commercial Route"
                        for route in self.state.player_trade_routes.values()
                    ),
                ),
                MenuItem(
                    label="Contribute regional funds",
                    value="contribute",
                    enabled=bool(council.get("member")) and self.state.money >= 500,
                    hint="500g",
                ),
                MenuItem(
                    label="Propose regional project",
                    value="project",
                    enabled=bool(council.get("member")),
                    hint=f"Treasury {council.get('treasury', 0)}g",
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                "Regional Council",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "report":
                self.vertical_panel_view(
                    "Regional Council",
                    self.regional_council_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "join":
                plans = [
                    plan
                    for plan in self.discovered_procedural_town_plans()
                    if self.procedural_town_reputation(plan) >= 75
                ]
                delegate_items = [
                    MenuItem(
                        label=str(plan.get("name")),
                        value=self.civic_town_key(plan),
                        enabled=True,
                        hint="Serve as this town's delegate",
                    )
                    for plan in plans
                ]
                delegate_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Choose Delegation",
                    delegate_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.join_regional_council(str(selected.value))
            elif choice.value == "agreement":
                routes = [
                    route
                    for route in self.state.player_trade_routes.values()
                    if str(route.get("agreement_type", "Commercial Route"))
                    == "Commercial Route"
                ]
                route_items = [
                    MenuItem(
                        label=str(route.get("good")),
                        value=str(route.get("id")),
                        enabled=True,
                        hint="Convert route into a formal agreement",
                    )
                    for route in routes
                ]
                route_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected_route = self.vertical_panel_select(
                    "Choose Route",
                    route_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if not selected_route or selected_route.value == MENU_BACK:
                    continue
                agreement_items = [
                    MenuItem(
                        label=name,
                        value=name,
                        enabled=True,
                        hint=description,
                    )
                    for name, description in REGIONAL_AGREEMENTS.items()
                ]
                agreement_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected_agreement = self.vertical_panel_select(
                    "Regional Agreement",
                    agreement_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected_agreement and selected_agreement.value != MENU_BACK:
                    self.establish_regional_agreement(
                        str(selected_route.value),
                        str(selected_agreement.value),
                    )
            elif choice.value == "contribute":
                self.contribute_to_regional_treasury(500)
            elif choice.value == "project":
                completed = set(council.get("completed_projects", []) or [])
                project_items = [
                    MenuItem(
                        label=str(record["name"]),
                        value=project_id,
                        enabled=(
                            project_id not in completed
                            and int(council.get("treasury", 0))
                            >= int(record["cost"])
                            and self.regional_project_support(project_id) >= 60
                        ),
                        hint=(
                            "Completed"
                            if project_id in completed
                            else f"{record['cost']}g | support "
                            f"{self.regional_project_support(project_id)}%"
                        ),
                    )
                    for project_id, record in REGIONAL_PROJECTS.items()
                ]
                project_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Regional Projects",
                    project_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.complete_regional_project(str(selected.value))

    def civic_portfolio_lines(self) -> List[str]:
        self.ensure_civic_economy_state()
        return [
            "PLAYER PROPERTY AND COMMERCE",
            "",
            f"Residences: {len(self.state.player_properties)}",
            f"Businesses: {len(self.state.player_businesses)}",
            f"Trade routes: {len(self.state.player_trade_routes)}",
            f"Primary residence: {self.state.primary_residence_id}",
            "",
            f"Lifetime property income: {self.state.civic_profile.get('lifetime_property_income', 0)}g",
            f"Lifetime business income: {self.state.civic_profile.get('lifetime_business_income', 0)}g",
            f"Lifetime trade income: {self.state.civic_profile.get('lifetime_trade_income', 0)}g",
        ]

    def civic_portfolio_menu(self) -> None:
        self.ensure_civic_economy_state()
        while True:
            items = [
                MenuItem(label="Portfolio report", value="report", enabled=True),
                MenuItem(
                    label="Manage residences",
                    value="properties",
                    enabled=bool(self.state.player_properties),
                ),
                MenuItem(
                    label="Manage businesses",
                    value="businesses",
                    enabled=bool(self.state.player_businesses),
                ),
                MenuItem(
                    label="Manage trade routes",
                    value="routes",
                    enabled=bool(self.state.player_trade_routes),
                ),
                MenuItem(
                    label="Travel network",
                    value="travel",
                    enabled=bool(
                        self.state.player_properties
                        or self.state.player_trade_routes
                    ),
                    hint="Owned residences and connected towns",
                ),
                MenuItem(
                    label="Make farmhouse primary",
                    value="farmhouse",
                    enabled=self.state.primary_residence_id != "farmhouse",
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                "Property and Commerce",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "report":
                self.vertical_panel_view(
                    "Portfolio Report",
                    self.civic_portfolio_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "farmhouse":
                self.set_primary_residence("farmhouse")
            elif choice.value == "travel":
                self.civic_travel_menu()
            elif choice.value == "properties":
                property_items = [
                    MenuItem(
                        label=str(record.get("name")),
                        value=str(record.get("id")),
                        enabled=True,
                        hint=(
                            f"{record.get('use_mode', 'Private')} | "
                            f"upgrade {record.get('upgrade_level', 0)}/3"
                        ),
                    )
                    for record in self.state.player_properties.values()
                ]
                property_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Residences",
                    property_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    record = self.state.player_properties.get(str(selected.value))
                    if record:
                        self.vertical_panel_view(
                            str(record.get("name")),
                            [
                                f"Use: {record.get('use_mode', 'Private')}",
                                f"Upgrade: {record.get('upgrade_level', 0)}/3",
                                f"Comfort: {record.get('comfort', 0)}",
                                f"Household: {'yes' if record.get('household_moved') else 'no'}",
                                f"Lifetime income: {record.get('lifetime_income', 0)}g",
                            ],
                            LEFT_PANEL_WIDTH,
                            LEFT_PANEL_HEIGHT,
                        )
            elif choice.value == "businesses":
                business_items = [
                    MenuItem(
                        label=str(record.get("name")),
                        value=str(record.get("id")),
                        enabled=True,
                        hint=(
                            f"{record.get('strategy')} | "
                            f"{'open' if record.get('active') else 'closed'}"
                        ),
                    )
                    for record in self.state.player_businesses.values()
                ]
                business_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Businesses",
                    business_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    record = self.state.player_businesses.get(str(selected.value))
                    if record:
                        self.set_procedural_business_active(
                            str(record["id"]),
                            not bool(record.get("active")),
                        )
            elif choice.value == "routes":
                route_items = [
                    MenuItem(
                        label=str(record.get("good")),
                        value=str(record.get("id")),
                        enabled=True,
                        hint=(
                            f"{record.get('agreement_type', 'Commercial Route')} | "
                            f"{'active' if record.get('active') else 'paused'}"
                        ),
                    )
                    for record in self.state.player_trade_routes.values()
                ]
                route_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Trade Routes",
                    route_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    record = self.state.player_trade_routes.get(str(selected.value))
                    if record:
                        self.set_player_trade_route_active(
                            str(record["id"]),
                            not bool(record.get("active")),
                        )

    def create_player_trade_route(
        self,
        business_id: str,
        destination_town_key: str,
    ) -> bool:
        self.ensure_civic_economy_state()
        business = self.state.player_businesses.get(str(business_id))
        destination = self.civic_plan_for_key(str(destination_town_key))
        source = (
            self.civic_plan_for_key(str(business.get("town_key")))
            if business
            else None
        )
        if not business or not source or not destination:
            return False
        source_key = self.civic_town_key(source)
        destination_key = self.civic_town_key(destination)
        if source_key == destination_key or not destination.get("discovered"):
            return False
        route_id = f"route:{business_id}:{destination_key}"
        if route_id in self.state.player_trade_routes:
            return False
        distance = abs(int(source["chunk_x"]) - int(destination["chunk_x"]))
        distance += abs(int(source["chunk_y"]) - int(destination["chunk_y"]))
        source_identity = self.procedural_town_identity(source)
        destination_identity = self.procedural_town_identity(destination)
        exports = list(source_identity.get("exports", ()) or ["General Goods"])
        imports = set(destination_identity.get("imports", ()) or [])
        good = next((item for item in exports if item in imports), exports[0])
        policy = str(
            self.ensure_procedural_town_politics(source).get("current_policy", "")
        )
        setup_cost = 900 + distance * 45
        if policy == "Open Trade":
            setup_cost = setup_cost * 85 // 100
        if int(self.state.money) < setup_cost:
            self.set_message(f"Establishing this route requires {setup_cost}g.")
            return False
        daily_income = 24 + min(70, distance * 3)
        self.state.money -= setup_cost
        self.state.player_trade_routes[route_id] = {
            "id": route_id,
            "source_town_key": source_key,
            "destination_town_key": destination_key,
            "business_id": str(business_id),
            "good": str(good),
            "distance": max(1, distance),
            "setup_cost": setup_cost,
            "daily_income": daily_income,
            "last_income_ordinal": self.civic_date_ordinal(),
            "lifetime_income": 0,
            "capacity_level": 0,
            "escort_level": 0,
            "total_invested": 0,
            "caravan_name": "",
            "caravan_last_ordinal": self.civic_date_ordinal(),
            "caravan_deliveries": 0,
            "caravan_sales_day": "",
            "caravan_sales": {},
            "caravan_journeys": 0,
            "caravan_last_journey_day": "",
            "active": True,
        }
        self.ensure_player_trade_route_caravan(
            self.state.player_trade_routes[route_id]
        )
        self.adjust_procedural_town_reputation(
            5,
            f"Opened trade with {destination.get('name')}",
            source,
        )
        self.adjust_procedural_town_reputation(
            3,
            f"Opened trade with {source.get('name')}",
            destination,
        )
        self.autosave_with_message(
            f"Established a {good} route from {source.get('name')} to "
            f"{destination.get('name')} for {setup_cost}g."
        )
        return True

    def procedural_trade_route_daily_income(
        self,
        route: Dict[str, object],
    ) -> int:
        base = int(route.get("daily_income", 0))
        capacity = int(route.get("capacity_level", 0))
        escort = int(route.get("escort_level", 0))
        reliability = min(100, 82 + escort * 6)
        agreement = str(route.get("agreement_type", "Commercial Route"))
        if agreement == "Trade Charter":
            base = base * 115 // 100
        elif agreement == "Mutual Aid":
            reliability = min(100, reliability + 6)
        elif agreement == "Cultural Exchange":
            base = base * 107 // 100
        business = self.state.player_businesses.get(
            str(route.get("business_id", "")),
            {},
        )
        if str(business.get("strategy")) == "Trade":
            base = base * 110 // 100
        source = self.civic_plan_for_key(str(route.get("source_town_key", "")))
        if source:
            if self.procedural_town_current_policy(source) == "Open Trade":
                base = base * 115 // 100
            initiatives = set(
                self.ensure_procedural_town_politics(source).get(
                    "completed_initiatives",
                    [],
                )
                or []
            )
            if "trade_depot" in initiatives:
                base = base * 115 // 100
        regional_projects = set(
            self.ensure_regional_council_state().get(
                "completed_projects",
                [],
            )
            or []
        )
        if "waystation_network" in regional_projects:
            base = base * 110 // 100
        if "caravan_league" in regional_projects:
            base = base * 115 // 100
        if "ranger_network" in regional_projects:
            reliability = min(100, reliability + 8)
        if (
            hasattr(self, "has_dynasty_heirloom")
            and self.has_dynasty_heirloom("trade_seal")
        ):
            base = base * 105 // 100
        return max(
            0,
            base * (100 + capacity * 25) * reliability // 10000,
        )

    def upgrade_player_trade_route(
        self,
        route_id: str,
        upgrade_kind: str,
    ) -> bool:
        self.ensure_civic_economy_state()
        route = self.state.player_trade_routes.get(str(route_id))
        fields = {
            "capacity": ("capacity_level", "Larger Caravan"),
            "escort": ("escort_level", "Route Escort"),
        }
        if not route or upgrade_kind not in fields:
            return False
        field, label = fields[upgrade_kind]
        level = int(route.get(field, 0))
        if level >= 3:
            self.set_message(f"{label} is fully upgraded.")
            return False
        cost = (
            1300 + level * 1100
            if upgrade_kind == "capacity"
            else 900 + level * 850
        )
        if int(self.state.money) < cost:
            self.set_message(f"This route upgrade requires {cost}g.")
            return False
        self.state.money -= cost
        route[field] = level + 1
        route["total_invested"] = int(route.get("total_invested", 0)) + cost
        self.autosave_with_message(
            f"Upgraded {label} for the {route.get('good')} route."
        )
        return True

    def set_player_trade_route_active(
        self,
        route_id: str,
        active: bool,
    ) -> bool:
        self.ensure_civic_economy_state()
        route = self.state.player_trade_routes.get(str(route_id))
        if not route:
            return False
        route["active"] = bool(active)
        route["last_income_ordinal"] = self.civic_date_ordinal()
        route["caravan_last_ordinal"] = self.civic_date_ordinal()
        self.autosave_with_message(
            f"The {route.get('good')} route is now "
            f"{'operating' if active else 'paused'}."
        )
        return True

    def ensure_player_trade_route_caravan(
        self,
        route: Dict[str, object],
    ) -> Dict[str, object]:
        seed = stable_text_seed(f"{route.get('id', '')}:caravan")
        if not str(route.get("caravan_name", "")).strip():
            adjective = CARAVAN_ADJECTIVES[seed % len(CARAVAN_ADJECTIVES)]
            noun = CARAVAN_NOUNS[(seed // len(CARAVAN_ADJECTIVES)) % len(CARAVAN_NOUNS)]
            route["caravan_name"] = f"The {adjective} {noun}"
        route["caravan_last_ordinal"] = max(
            0,
            int(route.get("caravan_last_ordinal", 0)),
        )
        route["caravan_deliveries"] = max(
            0,
            int(route.get("caravan_deliveries", 0)),
        )
        if not isinstance(route.get("caravan_sales"), dict):
            route["caravan_sales"] = {}
        route["caravan_sales_day"] = str(route.get("caravan_sales_day", ""))
        route["caravan_journeys"] = max(
            0,
            int(route.get("caravan_journeys", 0)),
        )
        route["caravan_last_journey_day"] = str(
            route.get("caravan_last_journey_day", "")
        )
        return route

    def player_trade_route_caravan_state(
        self,
        route: Dict[str, object],
        ordinal: Optional[int] = None,
    ) -> Dict[str, object]:
        self.ensure_player_trade_route_caravan(route)
        source = self.civic_plan_for_key(str(route.get("source_town_key", ""))) or {}
        destination = self.civic_plan_for_key(
            str(route.get("destination_town_key", ""))
        ) or {}
        if not route.get("active"):
            return {
                "phase": "paused",
                "town_key": "",
                "status": "paused at its depot",
                "next_stop": str(source.get("name", "the source depot")),
            }
        today = self.civic_date_ordinal() if ordinal is None else max(1, int(ordinal))
        travel_days = max(1, min(5, (int(route.get("distance", 1)) + 2) // 3))
        cycle_length = travel_days * 2 + 4
        seed_offset = stable_text_seed(f"{route.get('id', '')}:schedule") % cycle_length
        step = (today + seed_offset) % cycle_length
        source_name = str(source.get("name", "the source town"))
        destination_name = str(destination.get("name", "the destination town"))
        if step <= 1:
            return {
                "phase": "source",
                "town_key": str(route.get("source_town_key", "")),
                "status": f"loading in {source_name}",
                "next_stop": destination_name,
                "arrival_step": 0,
            }
        if step <= travel_days + 1:
            progress = step - 1
            return {
                "phase": "outbound",
                "town_key": "",
                "status": (
                    f"on the road to {destination_name} "
                    f"({progress}/{travel_days} travel days)"
                ),
                "next_stop": destination_name,
                "arrival_step": travel_days + 2,
            }
        if step <= travel_days + 3:
            return {
                "phase": "destination",
                "town_key": str(route.get("destination_town_key", "")),
                "status": f"trading in {destination_name}",
                "next_stop": source_name,
                "arrival_step": travel_days + 2,
            }
        progress = step - travel_days - 3
        return {
            "phase": "returning",
            "town_key": "",
            "status": (
                f"returning to {source_name} "
                f"({progress}/{travel_days} travel days)"
            ),
            "next_stop": source_name,
            "arrival_step": 0,
        }

    def update_player_trade_caravans(self) -> None:
        self.ensure_civic_economy_state()
        today = self.civic_date_ordinal()
        for route in self.state.player_trade_routes.values():
            self.ensure_player_trade_route_caravan(route)
            last = int(route.get("caravan_last_ordinal", 0) or 0)
            if last <= 0:
                route["caravan_last_ordinal"] = today
                continue
            if not route.get("active") or last >= today:
                route["caravan_last_ordinal"] = max(last, today)
                continue
            for ordinal in range(last + 1, min(today, last + 45) + 1):
                current = self.player_trade_route_caravan_state(route, ordinal)
                previous = self.player_trade_route_caravan_state(route, ordinal - 1)
                if (
                    current.get("phase") == "destination"
                    and previous.get("phase") != "destination"
                ):
                    route["caravan_deliveries"] = int(
                        route.get("caravan_deliveries", 0)
                    ) + 1
            route["caravan_last_ordinal"] = today

    def procedural_town_caravan_actors(
        self,
        plan: Dict[str, object],
        occupied: Optional[set] = None,
    ) -> List[Dict[str, object]]:
        if self.on_procedural_town_interior():
            return []
        self.update_player_trade_caravans()
        occupied = occupied if occupied is not None else set()
        town_key = self.civic_town_key(plan)
        buildings = [
            building
            for building in plan.get("buildings", {}).values()
            if isinstance(building, dict)
        ]
        anchor = next(
            (
                building
                for type_id in ("market_stall", "general_store", "inn", "town_hall")
                for building in buildings
                if str(building.get("type_id", "")) == type_id
            ),
            None,
        )
        anchor_x = int(anchor.get("access_x", 40)) if anchor else 40
        anchor_y = int(anchor.get("access_y", 20)) if anchor else 20
        actors: List[Dict[str, object]] = []
        tick = int(getattr(self, "_procedural_resident_move_tick", 0))
        for index, route in enumerate(
            sorted(
                self.state.player_trade_routes.values(),
                key=lambda value: str(value.get("id", "")),
            )
        ):
            state = self.player_trade_route_caravan_state(route)
            if state.get("town_key") != town_key:
                continue
            motion = (
                (-3, 0), (-2, 1), (-1, 0), (0, 1),
                (1, 0), (2, 1), (3, 0), (0, -1),
            )
            dx, dy = motion[
                (tick + index + stable_text_seed(str(route.get("id", "")))) % len(motion)
            ]
            position = self.procedural_town_nearest_resident_tile(
                plan,
                anchor_x + dx,
                anchor_y + dy,
                occupied,
            )
            if position is None:
                continue
            occupied.add(position)
            source = self.civic_plan_for_key(str(route.get("source_town_key", ""))) or {}
            destination = self.civic_plan_for_key(
                str(route.get("destination_town_key", ""))
            ) or {}
            actor = {
                "id": f"caravan:{route.get('id')}",
                "name": str(route.get("caravan_name", "Trade Caravan")),
                "role": "Trade Caravan",
                "relationship": 0,
                "procedural_caravan": True,
                "route_id": str(route.get("id", "")),
                "x": position[0],
                "y": position[1],
                "runtime_x": position[0],
                "runtime_y": position[1],
                "runtime_activity": str(state.get("status", "stopped for trade")),
                "source_name": str(source.get("name", "Source Town")),
                "destination_name": str(destination.get("name", "Destination Town")),
                "next_stop": str(state.get("next_stop", "")),
                "phase": str(state.get("phase", "")),
            }
            actors.append(actor)
        return actors

    def procedural_caravan_stock(
        self,
        actor: Dict[str, object],
    ) -> List[Dict[str, object]]:
        route = self.state.player_trade_routes.get(str(actor.get("route_id", "")))
        if not route:
            return []
        self.ensure_player_trade_route_caravan(route)
        day_key = (
            f"{int(getattr(self.state, 'year', 1))}-"
            f"{int(getattr(self.state, 'month', 1))}-"
            f"{int(getattr(self.state, 'day', 1))}"
        )
        if str(route.get("caravan_sales_day", "")) != day_key:
            route["caravan_sales_day"] = day_key
            route["caravan_sales"] = {}
        current_plan = self.current_procedural_town_plan()
        current_key = self.civic_town_key(current_plan) if current_plan else ""
        origin_key = (
            str(route.get("source_town_key", ""))
            if current_key == str(route.get("destination_town_key", ""))
            else str(route.get("destination_town_key", ""))
        )
        origin = self.civic_plan_for_key(origin_key) or {}
        identity = self.procedural_town_identity(origin) if origin else {}
        item_names = [str(route.get("good", "General Goods"))]
        item_names.extend(str(item) for item in identity.get("exports", ()) or [])
        item_names = list(dict.fromkeys(item_names))[:4]
        sales = route.get("caravan_sales", {})
        capacity = 2 + int(route.get("capacity_level", 0))
        stock: List[Dict[str, object]] = []
        price_lookup = getattr(self, "shippable_unit_price", None)
        for item in item_names:
            base_price = int(price_lookup(item)) if callable(price_lookup) else 0
            if base_price <= 0:
                base_price = 25 + stable_text_seed(item) % 45
            price = max(8, base_price * 135 // 100)
            remaining = max(0, capacity - int(sales.get(item, 0)))
            stock.append(
                {
                    "item": item,
                    "price": price,
                    "remaining": remaining,
                    "origin": str(origin.get("name", "the far end of the route")),
                }
            )
        return stock

    def purchase_procedural_caravan_stock(
        self,
        actor: Dict[str, object],
        item: str,
        quantity: int = 1,
    ) -> bool:
        route = self.state.player_trade_routes.get(str(actor.get("route_id", "")))
        quantity = max(1, int(quantity))
        entry = next(
            (
                record
                for record in self.procedural_caravan_stock(actor)
                if str(record.get("item", "")) == str(item)
            ),
            None,
        )
        if not route or not entry or int(entry.get("remaining", 0)) < quantity:
            return False
        total = int(entry.get("price", 0)) * quantity
        if int(self.state.money) < total:
            self.set_message(f"That cargo costs {total}g.")
            return False
        self.state.money -= total
        self.state.inventory[str(item)] = int(
            self.state.inventory.get(str(item), 0)
        ) + quantity
        sales = route.setdefault("caravan_sales", {})
        sales[str(item)] = int(sales.get(str(item), 0)) + quantity
        plan = self.current_procedural_town_plan()
        if plan:
            self.adjust_procedural_town_reputation(
                1,
                f"Traded with {route.get('caravan_name')}",
                plan,
            )
        self.autosave_with_message(
            f"Bought {quantity} {item} from {route.get('caravan_name')} for {total}g."
        )
        return True

    def can_travel_with_procedural_caravan(
        self,
        actor: Dict[str, object],
    ) -> Tuple[bool, str]:
        route = self.state.player_trade_routes.get(str(actor.get("route_id", "")))
        if not route or not route.get("active"):
            return False, "This route is not operating."
        current_key = self.current_civic_town_key()
        if current_key not in {
            str(route.get("source_town_key", "")),
            str(route.get("destination_town_key", "")),
        }:
            return False, "The caravan is not at one of its terminal towns."
        if str(route.get("caravan_last_journey_day", "")) == str(
            getattr(self.state, "date_label", "")
        ):
            return False, "You already traveled with this caravan today."
        return True, "Join the crew for its next run."

    def procedural_caravan_journey_event_lines(
        self,
        route: Dict[str, object],
        approach: str,
        destination: Dict[str, object],
    ) -> Tuple[List[str], str, int]:
        seed = stable_text_seed(
            f"{route.get('id')}:{self.civic_date_ordinal()}:{approach}:journey"
        )
        travelers = (
            "a family relocating between frontier towns",
            "an apprentice carrying letters from a distant workshop",
            "two performers comparing festival routes",
            "a ranger mapping washouts and safe camps",
            "a peddler with stories from beyond the known settlements",
        )
        camp_scenes = (
            "At camp, the crew repairs harness, trades recipes, and leaves the kettle on for late watches.",
            "The evening camp settles around a low fire while drivers compare road signs and difficult bridges.",
            "A covered waystation turns the camp into a small temporary neighborhood.",
            "Rain taps the wagon canvas while the crew shares food and quietly revises tomorrow's route.",
        )
        incidents = (
            "A fallen branch slows the road. Everyone clears it together without losing cargo.",
            "Fresh tracks suggest wildlife nearby, so the caravan tightens formation and continues carefully.",
            "A wheel pin works loose. The delay becomes an impromptu lesson in roadside repair.",
            "A flooded hollow requires a patient detour, but the route remains safe.",
            "A confusing fork prompts the crew to compare maps before choosing the better-marked path.",
        )
        forage_items = ("Berries", "Wildflowers", "Cave Herbs", "Watercress")
        found_item = forage_items[(seed // 11) % len(forage_items)]
        found_qty = 2 if approach == "Scout the road" else 1
        approach_line = {
            "Scout the road": (
                f"You range ahead, mark a safer approach, and gather "
                f"{found_qty} {found_item} beside the trail."
            ),
            "Help with cargo": (
                "You help rebalance the wagons, verify the cargo ledger, and "
                "catch a damaged tie before it costs the route any goods."
            ),
            "Share the camp": (
                "You keep the fire, listen to the crew's road stories, and make "
                "sure the newest traveler is included in the meal."
            ),
        }.get(approach, "You take an ordinary watch and help where needed.")
        lines = [
            f"CARAVAN JOURNEY: {route.get('caravan_name')}",
            "",
            f"Destination: {destination.get('name', 'the next town')}",
            f"Your role: {approach}",
            "",
            f"Traveler: {travelers[seed % len(travelers)]}.",
            camp_scenes[(seed // 5) % len(camp_scenes)],
            incidents[(seed // 7) % len(incidents)],
            approach_line,
            "",
            "The journey has delays and small problems, but no arbitrary failure state. "
            "Preparation changes the texture and rewards of the trip.",
        ]
        return lines, found_item if approach == "Scout the road" else "", found_qty

    def travel_with_procedural_caravan(
        self,
        actor: Dict[str, object],
        approach: str,
    ) -> bool:
        route = self.state.player_trade_routes.get(str(actor.get("route_id", "")))
        ok, reason = self.can_travel_with_procedural_caravan(actor)
        approach_data = CARAVAN_JOURNEY_APPROACHES.get(str(approach))
        if not ok or not route or not approach_data:
            self.set_message(reason if not ok else "Choose a caravan role.")
            return False
        stamina_cost = int(approach_data["stamina"])
        if int(self.state.stamina) < stamina_cost:
            self.set_message(f"This journey needs {stamina_cost} stamina.")
            return False
        current_key = self.current_civic_town_key()
        source_key = str(route.get("source_town_key", ""))
        destination_key = (
            str(route.get("destination_town_key", ""))
            if current_key == source_key
            else source_key
        )
        destination = self.civic_plan_for_key(destination_key)
        if not destination:
            return False
        self.state.stamina = max(0, int(self.state.stamina) - stamina_cost)
        lines, found_item, found_qty = self.procedural_caravan_journey_event_lines(
            route,
            str(approach),
            destination,
        )
        if found_item:
            self.state.inventory[found_item] = int(
                self.state.inventory.get(found_item, 0)
            ) + found_qty
        approach_reward = int(approach_data["reward"])
        self.state.money += approach_reward
        travel_minutes = min(
            420,
            150 + max(1, int(route.get("distance", 1))) * 18,
        )
        self.advance_time(travel_minutes)
        self.state.location = "Wilderness"
        self.set_wilderness_chunk(
            int(destination["chunk_x"]),
            int(destination["chunk_y"]),
            entry_side="center",
        )
        route["caravan_journeys"] = int(route.get("caravan_journeys", 0)) + 1
        route["caravan_last_journey_day"] = str(
            getattr(self.state, "date_label", "")
        )
        if destination_key == str(route.get("destination_town_key", "")):
            route["caravan_deliveries"] = int(
                route.get("caravan_deliveries", 0)
            ) + 1
        self.adjust_procedural_town_reputation(
            2 if approach == "Share the camp" else 1,
            f"Arrived with {route.get('caravan_name')}",
            destination,
        )
        completed_contracts = 0
        for contract in self.regional_contracts(("active",)):
            if (
                str(contract.get("type", "")) == "escort"
                and str(contract.get("route_id", "")) == str(route.get("id", ""))
                and self.complete_regional_contract(
                    str(contract.get("id", "")),
                    journey_route_id=str(route.get("id", "")),
                )
            ):
                completed_contracts += 1
        state = self.ensure_regional_contract_state()
        summary = (
            f"{getattr(self.state, 'date_label', '')}: traveled with "
            f"{route.get('caravan_name')} to {destination.get('name')} as "
            f"{str(approach).lower()}"
        )
        state["journey_log"] = (
            list(state.get("journey_log", []) or []) + [summary]
        )[-40:]
        lines.extend(
            [
                "",
                f"Travel time: {travel_minutes} minutes",
                f"Stamina: -{stamina_cost}",
                f"Crew pay: {approach_reward}g",
            ]
        )
        if completed_contracts:
            lines.append(f"Escort contracts completed: {completed_contracts}")
        self.vertical_panel_view(
            "Caravan Journey",
            lines,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )
        self.autosave_with_message(
            f"Arrived in {destination.get('name')} with "
            f"{route.get('caravan_name')}."
        )
        return True

    def procedural_caravan_lines(
        self,
        actor: Dict[str, object],
    ) -> List[str]:
        route = self.state.player_trade_routes.get(str(actor.get("route_id", "")), {})
        state = self.player_trade_route_caravan_state(route) if route else {}
        return [
            str(actor.get("name", "TRADE CARAVAN")).upper(),
            "",
            f"Route: {actor.get('source_name')} to {actor.get('destination_name')}",
            f"Primary cargo: {route.get('good', 'General Goods')}",
            f"Current status: {state.get('status', 'unknown')}",
            f"Next stop: {state.get('next_stop', 'unknown')}",
            f"Completed deliveries: {route.get('caravan_deliveries', 0)}",
            f"Journeys together: {route.get('caravan_journeys', 0)}",
            f"Capacity: {int(route.get('capacity_level', 0)) + 1}/4",
            f"Escort: {int(route.get('escort_level', 0))}/3",
            f"Agreement: {route.get('agreement_type', 'Commercial Route')}",
            "",
            "The crew loads, unloads, rests, and walks the market district while in town.",
        ]

    def procedural_caravan_menu(
        self,
        actor: Dict[str, object],
    ) -> None:
        while True:
            travel_ok, travel_reason = self.can_travel_with_procedural_caravan(
                actor
            )
            choice = self.vertical_panel_select(
                str(actor.get("name", "Trade Caravan")),
                [
                    MenuItem(label="Browse cargo", value="cargo", enabled=True),
                    MenuItem(
                        label="Travel with caravan",
                        value="travel",
                        enabled=travel_ok,
                        hint=travel_reason,
                    ),
                    MenuItem(label="Route status", value="status", enabled=True),
                    MenuItem(label="Talk to crew", value="talk", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "status":
                self.vertical_panel_view(
                    "Caravan Route",
                    self.procedural_caravan_lines(actor),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "talk":
                route = self.state.player_trade_routes.get(
                    str(actor.get("route_id", "")),
                    {},
                )
                lines = [
                    "The caravan master checks a weather-marked route ledger.",
                    "",
                    f"“We carry {route.get('good', 'whatever the road needs')} "
                    f"between {actor.get('source_name')} and {actor.get('destination_name')}.”",
                    f"“Next stop is {actor.get('next_stop', 'wherever the road permits')}.”",
                ]
                if int(route.get("escort_level", 0)):
                    lines.append("Armed escorts keep watch over the carts and draft animals.")
                self.vertical_panel_view(
                    "Caravan Crew",
                    lines,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "travel":
                role_items = [
                    MenuItem(
                        label=approach,
                        value=approach,
                        enabled=int(self.state.stamina) >= int(data["stamina"]),
                        hint=f"{data['stamina']} stamina | {data['note']}",
                    )
                    for approach, data in CARAVAN_JOURNEY_APPROACHES.items()
                ]
                role_items.append(
                    MenuItem(label="Back", value=MENU_BACK, enabled=True)
                )
                role = self.vertical_panel_select(
                    "Caravan Role",
                    role_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if role and role.value != MENU_BACK:
                    if self.travel_with_procedural_caravan(
                        actor,
                        str(role.value),
                    ):
                        return
                continue
            stock = self.procedural_caravan_stock(actor)
            items = [
                MenuItem(
                    label=f"{entry['item']} - {entry['price']}g",
                    value=str(entry["item"]),
                    enabled=int(entry["remaining"]) > 0,
                    hint=f"{entry['remaining']} left | from {entry['origin']}",
                )
                for entry in stock
            ]
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            purchase = self.vertical_panel_select(
                "Caravan Cargo",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if purchase and purchase.value != MENU_BACK:
                self.purchase_procedural_caravan_stock(
                    actor,
                    str(purchase.value),
                    1,
                )

    def process_civic_economy(self) -> int:
        self.ensure_civic_economy_state()
        self.reconcile_player_business_staff()
        self.update_player_trade_caravans()
        today = self.civic_date_ordinal()
        property_total = 0
        business_total = 0
        trade_total = 0
        for plan in self.discovered_procedural_town_plans():
            politics = self.ensure_procedural_town_politics(plan)
            last_budget = int(
                politics.get("last_budget_ordinal", today) or today
            )
            elapsed_budget = max(0, min(45, today - last_budget))
            if elapsed_budget:
                daily_budget = 30 + self.procedural_town_development_rank(plan) * 10
                politics["treasury"] = int(
                    politics.get("treasury", 0)
                ) + daily_budget * elapsed_budget
                politics["last_budget_ordinal"] = today
        council = self.ensure_regional_council_state()
        council_last = int(
            council.get("last_budget_ordinal", today) or today
        )
        council_elapsed = max(0, min(45, today - council_last))
        if council_elapsed:
            agreement_count = sum(
                1
                for route in self.state.player_trade_routes.values()
                if str(route.get("agreement_type", "Commercial Route"))
                != "Commercial Route"
            )
            council["treasury"] = int(council.get("treasury", 0)) + (
                20 + agreement_count * 12
            ) * council_elapsed
            council["last_budget_ordinal"] = today
        for property_record in self.state.player_properties.values():
            last = int(
                property_record.get("last_income_ordinal", today) or today
            )
            elapsed = max(0, min(45, today - last))
            if elapsed <= 0:
                continue
            income = self.procedural_property_daily_income(property_record) * elapsed
            property_record["last_income_ordinal"] = today
            property_record["lifetime_income"] = int(
                property_record.get("lifetime_income", 0)
            ) + income
            property_total += income
        for business in self.state.player_businesses.values():
            if not business.get("active"):
                continue
            last = int(business.get("last_income_ordinal", today) or today)
            elapsed = max(0, min(45, today - last))
            if elapsed <= 0:
                continue
            income = self.procedural_business_daily_income(business) * elapsed
            business["last_income_ordinal"] = today
            business["lifetime_income"] = int(business.get("lifetime_income", 0)) + income
            business_total += income
            if str(business.get("strategy")) == "Local Goods":
                plan = self.civic_plan_for_key(str(business.get("town_key", "")))
                if plan:
                    community = self.ensure_procedural_town_community(plan)
                    community["development_points"] = int(
                        community.get("development_points", 0)
                    ) + elapsed
            contract = str(
                business.get("supply_contract", "Reliable Supply")
            )
            plan = self.civic_plan_for_key(str(business.get("town_key", "")))
            if plan and contract == "Local Exports":
                community = self.ensure_procedural_town_community(plan)
                community["development_points"] = int(
                    community.get("development_points", 0)
                ) + max(1, elapsed // 2)
            elif plan and contract == "Essential Goods":
                politics = self.ensure_procedural_town_politics(plan)
                politics["treasury"] = int(
                    politics.get("treasury", 0)
                ) + 8 * elapsed
        for route in self.state.player_trade_routes.values():
            if not route.get("active"):
                continue
            last = int(route.get("last_income_ordinal", today) or today)
            elapsed = max(0, min(45, today - last))
            if elapsed <= 0:
                continue
            income = self.procedural_trade_route_daily_income(route) * elapsed
            route["last_income_ordinal"] = today
            route["lifetime_income"] = int(route.get("lifetime_income", 0)) + income
            trade_total += income
        total = property_total + business_total + trade_total
        if total:
            self.state.money += total
            profile = self.state.civic_profile
            profile["lifetime_property_income"] += property_total
            profile["lifetime_business_income"] += business_total
            profile["lifetime_trade_income"] += trade_total
            line = (
                f"{getattr(self.state, 'date_label', '')}: property {property_total}g, "
                f"business {business_total}g, trade {trade_total}g"
            )
            self.state.civic_income_log = (
                list(self.state.civic_income_log) + [line]
            )[-30:]
        return total

    def ensure_procedural_town_politics(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        community = self.ensure_procedural_town_community(plan)
        politics = community.get("politics")
        if not isinstance(politics, dict):
            politics = {}
            community["politics"] = politics
        seed = stable_text_seed(f"{plan.get('seed')}:{plan.get('id')}:politics")
        politics.setdefault("office", "Mayor")
        politics.setdefault("election_month", (3, 6, 9, 12)[seed % 4])
        politics.setdefault("election_day", 15)
        politics.setdefault("candidate_year", 0)
        politics.setdefault("candidate_ids", [])
        politics.setdefault("candidate_platforms", {})
        politics.setdefault("player_registered", False)
        politics.setdefault("player_platform", "Public Works")
        politics.setdefault("player_vote", "")
        politics.setdefault("endorsements", {})
        politics.setdefault("resolved_year", 0)
        politics.setdefault("incumbent_id", "")
        politics.setdefault("current_policy", "Public Works")
        politics.setdefault("result_log", [])
        politics.setdefault("treasury", 500)
        politics.setdefault("last_budget_ordinal", self.civic_date_ordinal())
        politics.setdefault("last_policy_change", "")
        politics.setdefault("completed_initiatives", [])
        politics.setdefault("initiative_log", [])
        politics.setdefault("campaign_support", {})
        politics.setdefault("campaign_activity_days", [])
        politics.setdefault("campaign_log", [])
        politics.setdefault("debate_year", 0)
        politics.setdefault("debate_scores", {})
        politics.setdefault("last_result_scores", {})
        politics.setdefault("petition_month", "")
        politics.setdefault("active_petition", {})
        politics.setdefault("petition_log", [])
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        residents = list(population.get("residents", {}).values())
        if not politics.get("incumbent_id"):
            mayor = next(
                (resident for resident in residents if resident.get("role") == "Mayor"),
                residents[0] if residents else None,
            )
            politics["incumbent_id"] = str(mayor.get("id", "")) if mayor else ""
        year = int(getattr(self.state, "year", 1))
        if int(politics.get("candidate_year", 0)) != year:
            eligible = [
                resident
                for resident in residents
                if str(resident.get("age_group")) in {"Adult", "Elder"}
            ]
            eligible.sort(
                key=lambda resident: stable_text_seed(
                    f"{plan.get('seed')}:{year}:{resident.get('id')}:candidate"
                )
            )
            candidate_ids = [str(resident.get("id")) for resident in eligible[:3]]
            incumbent = str(politics.get("incumbent_id", ""))
            if incumbent and incumbent not in candidate_ids:
                candidate_ids = ([incumbent] + candidate_ids)[:3]
            politics["candidate_year"] = year
            politics["candidate_ids"] = candidate_ids
            politics["candidate_platforms"] = {
                candidate_id: list(TOWN_POLICIES)[
                    stable_text_seed(f"{candidate_id}:{year}:platform")
                    % len(TOWN_POLICIES)
                ]
                for candidate_id in candidate_ids
            }
            politics["player_registered"] = False
            politics["player_vote"] = ""
            politics["endorsements"] = {}
            politics["campaign_support"] = {}
            politics["campaign_activity_days"] = []
            politics["campaign_log"] = []
            politics["debate_year"] = 0
            politics["debate_scores"] = {}
        return politics

    def procedural_election_phase(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> str:
        politics = self.ensure_procedural_town_politics(plan)
        if not politics:
            return "Unavailable"
        month = int(getattr(self.state, "month", 1))
        day = int(getattr(self.state, "day", 1))
        election_month = int(politics["election_month"])
        election_day = int(politics["election_day"])
        if month < election_month:
            return "Campaign season"
        if month == election_month and day < max(1, election_day - 7):
            return "Campaign season"
        if month == election_month and day <= election_day:
            return "Voting open"
        if int(politics.get("resolved_year", 0)) < int(self.state.year):
            return "Ready to certify"
        return "Term in progress"

    def procedural_town_current_policy(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> str:
        return str(
            self.ensure_procedural_town_politics(plan).get(
                "current_policy",
                "Public Works",
            )
        )

    def procedural_town_election_issue(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, str]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        identity = self.procedural_town_identity(plan)
        market = self.procedural_town_market_profile(plan)
        seed = stable_text_seed(
            f"{plan.get('seed')}:{getattr(self.state, 'year', 1)}:election-issue"
        )
        records = (
            {
                "name": "Public access and repairs",
                "policy": "Public Works",
                "summary": str(identity.get("concern", "Public infrastructure needs attention.")),
            },
            {
                "name": "Local livelihoods",
                "policy": "Market Investment",
                "summary": f"Residents want steadier work around {identity.get('industry', 'local trade')}.",
            },
            {
                "name": "Regional connections",
                "policy": "Open Trade",
                "summary": f"The market is seeking {market.get('demand', 'reliable supplies')}.",
            },
            {
                "name": "Household services",
                "policy": "Family Services",
                "summary": "Families want stronger gathering, learning, and care services.",
            },
            {
                "name": "Wilderness readiness",
                "policy": "Wilderness Safety",
                "summary": "Travelers and residents want safer routes and emergency stores.",
            },
        )
        return dict(records[seed % len(records)])

    def perform_procedural_campaign_activity(
        self,
        activity_name: str,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        activity = CAMPAIGN_ACTIVITIES.get(str(activity_name))
        politics = self.ensure_procedural_town_politics(plan)
        if (
            not plan
            or not activity
            or not politics.get("player_registered")
            or self.procedural_election_phase(plan)
            not in {"Campaign season", "Voting open"}
        ):
            return False
        day_key = self.procedural_town_day_key()
        if day_key in set(politics.get("campaign_activity_days", []) or []):
            self.set_message("You have already held a campaign activity today.")
            return False
        if (
            int(self.state.money) < int(activity["money"])
            or int(self.state.stamina) < int(activity["stamina"])
        ):
            self.set_message(
                f"This activity needs {activity['money']}g and "
                f"{activity['stamina']} stamina."
            )
            return False
        self.state.money -= int(activity["money"])
        self.state.stamina -= int(activity["stamina"])
        self.advance_time(int(activity["minutes"]))
        platform = str(politics.get("player_platform", "Public Works"))
        preferred = VOTER_BLOC_POLICIES.get(str(activity["bloc"]), ())
        issue = self.procedural_town_election_issue(plan)
        gain = int(activity["base_support"])
        if platform in preferred:
            gain += 3
        if platform == issue.get("policy"):
            gain += 3
        gain += min(4, self.procedural_town_reputation(plan) // 40)
        support = politics.setdefault("campaign_support", {})
        support["player"] = int(support.get("player", 0)) + gain
        politics["campaign_activity_days"] = (
            list(politics.get("campaign_activity_days", []) or []) + [day_key]
        )[-45:]
        politics["campaign_log"] = (
            list(politics.get("campaign_log", []) or [])
            + [f"{day_key}: {activity_name} gained {gain} support"]
        )[-30:]
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        attendees = sorted(
            population.get("residents", {}).values(),
            key=lambda resident: stable_text_seed(
                f"{day_key}:{activity_name}:{resident.get('id')}"
            ),
        )
        for resident in attendees[:2]:
            resident["relationship"] = min(
                250,
                int(resident.get("relationship", 0)) + 1,
            )
            memories = list(resident.get("memories", []) or [])
            memories.append(
                f"Attended the farmer's {activity_name} during the Year "
                f"{self.state.year} campaign."
            )
            resident["memories"] = memories[-16:]
        self.autosave_with_message(
            f"Held {activity_name} in {plan.get('name')}. Campaign support +{gain}."
        )
        return True

    def hold_procedural_election_debate(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        if (
            not plan
            or self.procedural_election_phase(plan) != "Voting open"
            or int(politics.get("debate_year", 0)) == int(self.state.year)
        ):
            return False
        issue = self.procedural_town_election_issue(plan)
        scores: Dict[str, int] = {}
        for candidate_id in politics.get("candidate_ids", []):
            platform = str(
                politics.get("candidate_platforms", {}).get(
                    candidate_id,
                    "Public Works",
                )
            )
            score = 5 + stable_text_seed(
                f"{candidate_id}:{self.state.year}:debate"
            ) % 9
            if platform == issue.get("policy"):
                score += 7
            if candidate_id == "player":
                score += min(8, self.procedural_town_reputation(plan) // 20)
                score += min(
                    8,
                    int(
                        politics.get("campaign_support", {}).get(
                            "player",
                            0,
                        )
                    )
                    // 5,
                )
            scores[str(candidate_id)] = score
        politics["debate_year"] = int(self.state.year)
        politics["debate_scores"] = scores
        if "player" in scores:
            support = politics.setdefault("campaign_support", {})
            support["player"] = int(support.get("player", 0)) + max(
                2,
                scores["player"] // 3,
            )
        self.advance_time(60)
        winner = max(scores, key=lambda candidate_id: scores[candidate_id])
        self.autosave_with_message(
            f"The election debate focused on {issue.get('name')}. "
            f"{self.procedural_candidate_name(winner, plan)} made the strongest case."
        )
        return True

    def player_holds_procedural_office(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        return (
            str(
                self.ensure_procedural_town_politics(plan).get(
                    "incumbent_id",
                    "",
                )
            )
            == "player"
        )

    def ensure_procedural_constituent_petition(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        if not plan:
            return {}
        month_key = f"{int(self.state.year)}-{int(self.state.month)}"
        if str(politics.get("petition_month", "")) == month_key:
            petition = politics.get("active_petition", {})
            return petition if isinstance(petition, dict) else {}
        identity = self.procedural_town_identity(plan)
        market = self.procedural_town_market_profile(plan)
        records = (
            {
                "id": "repair_access",
                "title": "Repair an overlooked public approach",
                "request": str(identity.get("concern", "Residents want safer public access.")),
                "treasury_cost": 420,
            },
            {
                "id": "market_shelter",
                "title": "Improve shelter around daily trade",
                "request": f"Traders handling {market.get('demand', 'scarce goods')} want a more dependable public loading area.",
                "treasury_cost": 500,
            },
            {
                "id": "household_room",
                "title": "Open shared household space",
                "request": "Families are asking for a regular place to gather, learn, and share care.",
                "treasury_cost": 460,
            },
            {
                "id": "travel_stores",
                "title": "Restock emergency travel supplies",
                "request": "Residents want public stores ready for difficult weather and long journeys.",
                "treasury_cost": 540,
            },
        )
        petition = dict(records[
            stable_text_seed(
                f"{plan.get('seed')}:{month_key}:petition"
            )
            % len(records)
        ])
        petition.update({
            "month_key": month_key,
            "resolved": False,
            "resolution": "",
        })
        politics["petition_month"] = month_key
        politics["active_petition"] = petition
        return petition

    def resolve_procedural_constituent_petition(
        self,
        choice: str,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        petition = self.ensure_procedural_constituent_petition(plan)
        if (
            not plan
            or not self.player_holds_procedural_office(plan)
            or not petition
            or petition.get("resolved")
            or choice not in PETITION_CHOICES
        ):
            return False
        development = 0
        reputation = 0
        if choice == "Fund directly":
            cost = int(petition.get("treasury_cost", 0))
            if int(politics.get("treasury", 0)) < cost:
                self.set_message(f"The civic treasury needs {cost}g.")
                return False
            politics["treasury"] = int(politics.get("treasury", 0)) - cost
            development, reputation = 8, 4
        elif choice == "Organize volunteers":
            if int(self.state.stamina) < 10:
                self.set_message("Organizing the work needs 10 stamina.")
                return False
            self.state.stamina -= 10
            self.advance_time(90)
            development, reputation = 6, 6
        else:
            self.advance_time(60)
            development, reputation = 3, 3
        petition["resolved"] = True
        petition["resolution"] = choice
        petition["resolved_day"] = str(getattr(self.state, "date_label", ""))
        politics["petition_log"] = (
            list(politics.get("petition_log", []) or [])
            + [
                f"{petition.get('month_key')}: {petition.get('title')} — {choice}"
            ]
        )[-24:]
        community = self.ensure_procedural_town_community(plan)
        community["development_points"] = int(
            community.get("development_points", 0)
        ) + development
        self.adjust_procedural_town_reputation(
            reputation,
            f"Responded to residents: {petition.get('title')}",
            plan,
        )
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        for resident in list(population.get("residents", {}).values())[:3]:
            memories = list(resident.get("memories", []) or [])
            memories.append(
                f"The mayor answered '{petition.get('title')}' through {choice.lower()}."
            )
            resident["memories"] = memories[-16:]
        self.autosave_with_message(
            f"Resolved '{petition.get('title')}' through {choice.lower()}."
        )
        return True

    def set_procedural_town_policy(
        self,
        policy: str,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        if (
            not plan
            or not self.player_holds_procedural_office(plan)
            or policy not in TOWN_POLICIES
        ):
            return False
        month_key = f"{int(self.state.year)}-{int(self.state.month)}"
        if str(politics.get("last_policy_change", "")) == month_key:
            self.set_message("You have already changed town policy this month.")
            return False
        politics["current_policy"] = policy
        politics["last_policy_change"] = month_key
        politics["initiative_log"] = (
            list(politics.get("initiative_log", []) or [])
            + [f"{getattr(self.state, 'date_label', '')}: policy changed to {policy}"]
        )[-20:]
        self.autosave_with_message(
            f"{plan.get('name')} now prioritizes {policy}."
        )
        return True

    def contribute_to_procedural_town_treasury(
        self,
        amount: int,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        amount = max(1, int(amount))
        if not plan or int(self.state.money) < amount:
            return False
        self.state.money -= amount
        politics["treasury"] = int(politics.get("treasury", 0)) + amount
        self.adjust_procedural_town_reputation(
            min(5, max(1, amount // 500)),
            "Contributed to the civic treasury",
            plan,
        )
        self.autosave_with_message(
            f"Contributed {amount}g to {plan.get('name')}'s civic treasury."
        )
        return True

    def complete_procedural_civic_initiative(
        self,
        initiative_id: str,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        initiative = CIVIC_INITIATIVES.get(str(initiative_id))
        completed = set(politics.get("completed_initiatives", []) or [])
        if (
            not plan
            or not initiative
            or not self.player_holds_procedural_office(plan)
            or initiative_id in completed
            or int(politics.get("treasury", 0)) < int(initiative["cost"])
        ):
            return False
        politics["treasury"] = int(politics.get("treasury", 0)) - int(
            initiative["cost"]
        )
        politics["completed_initiatives"] = (
            list(politics.get("completed_initiatives", []) or [])
            + [initiative_id]
        )
        politics["initiative_log"] = (
            list(politics.get("initiative_log", []) or [])
            + [
                f"{getattr(self.state, 'date_label', '')}: completed "
                f"{initiative['name']}"
            ]
        )[-20:]
        community = self.ensure_procedural_town_community(plan)
        community["development_points"] = int(
            community.get("development_points", 0)
        ) + int(initiative["development"])
        self.adjust_procedural_town_reputation(
            6,
            f"Completed civic initiative: {initiative['name']}",
            plan,
        )
        self.autosave_with_message(
            f"Completed {initiative['name']} in {plan.get('name')}."
        )
        return True

    def player_election_eligibility(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Tuple[bool, str]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return False, "No town"
        self.ensure_civic_economy_state()
        property_record = self.state.player_properties.get(
            self.state.primary_residence_id
        )
        if not property_record or property_record.get("town_key") != self.civic_town_key(plan):
            return False, "Primary residence must be in this town"
        if self.procedural_town_reputation(plan) < 75:
            return False, "Requires Trusted Neighbor reputation"
        return True, "Eligible"

    def register_player_for_election(
        self,
        plan: Optional[Dict[str, object]] = None,
        platform: str = "Public Works",
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        eligible, reason = self.player_election_eligibility(plan)
        if not eligible or platform not in TOWN_POLICIES:
            self.set_message(reason)
            return False
        politics = self.ensure_procedural_town_politics(plan)
        if self.procedural_election_phase(plan) not in {"Campaign season", "Voting open"}:
            return False
        politics["player_registered"] = True
        politics["player_platform"] = platform
        if "player" not in politics["candidate_ids"]:
            politics["candidate_ids"].append("player")
        politics["candidate_platforms"]["player"] = platform
        self.autosave_with_message(
            f"Registered for {plan.get('name')}'s mayoral election on a "
            f"{platform} platform."
        )
        return True

    def procedural_candidate_name(
        self,
        candidate_id: str,
        plan: Dict[str, object],
    ) -> str:
        if str(candidate_id) == "player":
            return str(getattr(self.state, "player_name", "Farmer"))
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        resident = population.get("residents", {}).get(str(candidate_id), {})
        return str(resident.get("name", "Resident Candidate"))

    def endorse_procedural_candidate(
        self,
        candidate_id: str,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        if not plan or str(candidate_id) not in politics.get("candidate_ids", []):
            return False
        key = f"{self.civic_town_key(plan)}:{self.state.year}"
        endorsements = self.state.civic_profile.setdefault(
            "campaign_endorsements",
            [],
        )
        if key in endorsements:
            return False
        politics.setdefault("endorsements", {})[str(candidate_id)] = (
            int(politics.get("endorsements", {}).get(str(candidate_id), 0)) + 1
        )
        endorsements.append(key)
        self.adjust_procedural_town_reputation(
            1,
            f"Participated in the {self.state.year} local campaign",
            plan,
        )
        return True

    def cast_procedural_election_vote(
        self,
        candidate_id: str,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        if (
            not plan
            or self.procedural_election_phase(plan) != "Voting open"
            or politics.get("player_vote")
            or str(candidate_id) not in politics.get("candidate_ids", [])
        ):
            return False
        politics["player_vote"] = str(candidate_id)
        self.state.civic_profile["votes_cast"] += 1
        self.autosave_with_message(
            f"Voted for {self.procedural_candidate_name(str(candidate_id), plan)}."
        )
        return True

    def resolve_procedural_election(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Optional[str]:
        plan = plan or self.current_procedural_town_plan()
        politics = self.ensure_procedural_town_politics(plan)
        if (
            not plan
            or self.procedural_election_phase(plan) != "Ready to certify"
        ):
            return None
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        scores: Dict[str, int] = {}
        for candidate_id in politics.get("candidate_ids", []):
            score = 35 + stable_text_seed(
                f"{plan.get('seed')}:{self.state.year}:{candidate_id}:vote"
            ) % 31
            if candidate_id == politics.get("incumbent_id"):
                score += 8
            if candidate_id == "player":
                score += self.procedural_town_reputation(plan) // 5
                score += len(
                    [
                        business
                        for business in self.state.player_businesses.values()
                        if business.get("town_key") == self.civic_town_key(plan)
                    ]
                ) * 4
            else:
                resident = population.get("residents", {}).get(candidate_id, {})
                score += int(resident.get("relationship", 0)) // 12
                if resident.get("role") == "Mayor":
                    score += 6
            score += int(politics.get("endorsements", {}).get(candidate_id, 0)) * 7
            score += int(
                politics.get("campaign_support", {}).get(candidate_id, 0)
            )
            score += int(
                politics.get("debate_scores", {}).get(candidate_id, 0)
            ) // 2
            if politics.get("player_vote") == candidate_id:
                score += 9
            scores[candidate_id] = score
        if not scores:
            return None
        winner = max(
            scores,
            key=lambda candidate_id: (scores[candidate_id], candidate_id),
        )
        politics["incumbent_id"] = winner
        politics["current_policy"] = str(
            politics.get("candidate_platforms", {}).get(winner, "Public Works")
        )
        politics["resolved_year"] = int(self.state.year)
        politics["last_result_scores"] = dict(scores)
        winner_name = self.procedural_candidate_name(winner, plan)
        result = (
            f"Year {self.state.year}: {winner_name} won with {scores[winner]} support "
            f"on {politics['current_policy']}."
        )
        politics["result_log"] = (
            list(politics.get("result_log", []) or []) + [result]
        )[-12:]
        if politics["current_policy"] == "Public Works":
            community = self.ensure_procedural_town_community(plan)
            community["development_points"] = int(
                community.get("development_points", 0)
            ) + 6
        if winner == "player":
            self.state.civic_profile["elections_won"] += 1
            office_key = f"{self.civic_town_key(plan)}:{self.state.year}:Mayor"
            self.state.civic_profile["offices_held"] = (
                list(self.state.civic_profile.get("offices_held", []))
                + [office_key]
            )[-20:]
        elif politics.get("player_registered"):
            self.state.civic_profile["elections_lost"] += 1
        for resident in population.get("residents", {}).values():
            memories = list(resident.get("memories", []) or [])
            memories.append(
                f"{winner_name} won the Year {self.state.year} mayoral election "
                f"on {politics['current_policy']}."
            )
            resident["memories"] = memories[-16:]
        self.autosave_with_message(result)
        return winner

    def procedural_town_politics_lines(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> List[str]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return ["No civic record is available."]
        politics = self.ensure_procedural_town_politics(plan)
        incumbent = self.procedural_candidate_name(
            str(politics.get("incumbent_id", "")),
            plan,
        )
        lines = [
            f"{plan.get('name', 'Town').upper()} CIVIC RECORD",
            "",
            f"Office: {politics.get('office')}",
            f"Current officeholder: {incumbent}",
            f"Current policy: {politics.get('current_policy')}",
            f"Civic treasury: {politics.get('treasury', 0)}g",
            f"Election: Month {politics.get('election_month')}, day {politics.get('election_day')}",
            f"Phase: {self.procedural_election_phase(plan)}",
            f"Leading issue: {self.procedural_town_election_issue(plan).get('name', 'none')}",
            f"Completed initiatives: {len(politics.get('completed_initiatives', []) or [])}",
            "",
            "Candidates:",
        ]
        for candidate_id in politics.get("candidate_ids", []):
            lines.append(
                f"- {self.procedural_candidate_name(candidate_id, plan)}: "
                f"{politics.get('candidate_platforms', {}).get(candidate_id, 'Public Works')}"
            )
        if politics.get("result_log"):
            lines.extend(["", f"Latest: {politics['result_log'][-1]}"])
        if politics.get("last_result_scores"):
            lines.append("Certified support:")
            for candidate_id, score in sorted(
                politics["last_result_scores"].items(),
                key=lambda entry: (-int(entry[1]), str(entry[0])),
            ):
                lines.append(
                    f"- {self.procedural_candidate_name(candidate_id, plan)}: {score}"
                )
        if politics.get("campaign_log"):
            lines.extend(["", f"Campaign: {politics['campaign_log'][-1]}"])
        if politics.get("petition_log"):
            lines.extend(["", f"Constituents: {politics['petition_log'][-1]}"])
        return lines

    def procedural_town_politics_menu(self) -> None:
        plan = self.current_procedural_town_plan()
        if not plan:
            return
        while True:
            politics = self.ensure_procedural_town_politics(plan)
            eligible, reason = self.player_election_eligibility(plan)
            phase = self.procedural_election_phase(plan)
            petition = (
                self.ensure_procedural_constituent_petition(plan)
                if self.player_holds_procedural_office(plan)
                else {}
            )
            items = [
                MenuItem(label="Civic record", value="record", enabled=True),
                MenuItem(
                    label="Set town policy",
                    value="policy",
                    enabled=self.player_holds_procedural_office(plan),
                    hint="Mayor only; one change per month",
                ),
                MenuItem(
                    label="Fund civic initiative",
                    value="initiative",
                    enabled=self.player_holds_procedural_office(plan),
                    hint=f"Treasury {politics.get('treasury', 0)}g",
                ),
                MenuItem(
                    label="Contribute to treasury",
                    value="treasury",
                    enabled=int(self.state.money) >= 250,
                    hint="250g contribution",
                ),
                MenuItem(
                    label="Campaign activity",
                    value="campaign",
                    enabled=bool(politics.get("player_registered"))
                    and phase in {"Campaign season", "Voting open"}
                    and self.procedural_town_day_key()
                    not in set(politics.get("campaign_activity_days", []) or []),
                    hint=f"Support {politics.get('campaign_support', {}).get('player', 0)}",
                ),
                MenuItem(
                    label="Election debate",
                    value="debate",
                    enabled=phase == "Voting open"
                    and int(politics.get("debate_year", 0)) != int(self.state.year),
                    hint=str(self.procedural_town_election_issue(plan).get("name", "")),
                ),
                MenuItem(
                    label="Constituent petition",
                    value="petition",
                    enabled=bool(petition) and not petition.get("resolved"),
                    hint=str(petition.get("title", "Mayor only")) if petition else "Mayor only",
                ),
                MenuItem(
                    label="Register as candidate",
                    value="register",
                    enabled=eligible and not politics.get("player_registered")
                    and phase in {"Campaign season", "Voting open"},
                    hint=reason,
                ),
                MenuItem(
                    label="Endorse candidate",
                    value="endorse",
                    enabled=phase in {"Campaign season", "Voting open"},
                ),
                MenuItem(
                    label="Cast vote",
                    value="vote",
                    enabled=phase == "Voting open" and not politics.get("player_vote"),
                ),
                MenuItem(
                    label="Certify result",
                    value="resolve",
                    enabled=phase == "Ready to certify",
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                "Town Politics",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "record":
                self.vertical_panel_view(
                    "Civic Record",
                    self.procedural_town_politics_lines(plan),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "policy":
                policy_items = [
                    MenuItem(
                        label=policy,
                        value=policy,
                        enabled=policy != politics.get("current_policy"),
                        hint=description,
                    )
                    for policy, description in TOWN_POLICIES.items()
                ]
                policy_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Set Town Policy",
                    policy_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.set_procedural_town_policy(str(selected.value), plan)
            elif choice.value == "initiative":
                completed = set(politics.get("completed_initiatives", []) or [])
                initiative_items = [
                    MenuItem(
                        label=str(record["name"]),
                        value=initiative_id,
                        enabled=(
                            initiative_id not in completed
                            and int(politics.get("treasury", 0))
                            >= int(record["cost"])
                        ),
                        hint=(
                            "Completed"
                            if initiative_id in completed
                            else f"{record['cost']}g | {record['description']}"
                        ),
                    )
                    for initiative_id, record in CIVIC_INITIATIVES.items()
                ]
                initiative_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Civic Initiatives",
                    initiative_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.complete_procedural_civic_initiative(
                        str(selected.value),
                        plan,
                    )
            elif choice.value == "treasury":
                self.contribute_to_procedural_town_treasury(250, plan)
            elif choice.value == "campaign":
                activity_items = [
                    MenuItem(
                        label=name,
                        value=name,
                        enabled=(
                            self.state.money >= int(record["money"])
                            and self.state.stamina >= int(record["stamina"])
                        ),
                        hint=(
                            f"{record['money']}g, {record['stamina']} stamina, "
                            f"{record['minutes']} min"
                        ),
                    )
                    for name, record in CAMPAIGN_ACTIVITIES.items()
                ]
                activity_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Campaign Activity",
                    activity_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.perform_procedural_campaign_activity(
                        str(selected.value),
                        plan,
                    )
            elif choice.value == "debate":
                self.hold_procedural_election_debate(plan)
            elif choice.value == "petition":
                petition_items = [
                    MenuItem(
                        label=name,
                        value=name,
                        enabled=(
                            name != "Fund directly"
                            or int(politics.get("treasury", 0))
                            >= int(petition.get("treasury_cost", 0))
                        ),
                        hint=description,
                    )
                    for name, description in PETITION_CHOICES.items()
                ]
                petition_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    str(petition.get("title", "Constituent Petition")),
                    petition_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.resolve_procedural_constituent_petition(
                        str(selected.value),
                        plan,
                    )
            elif choice.value == "register":
                platform_items = [
                    MenuItem(
                        label=policy,
                        value=policy,
                        enabled=True,
                        hint=description,
                    )
                    for policy, description in TOWN_POLICIES.items()
                ]
                platform_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                platform = self.vertical_panel_select(
                    "Choose Platform",
                    platform_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if platform and platform.value != MENU_BACK:
                    self.register_player_for_election(plan, str(platform.value))
            elif choice.value in {"endorse", "vote"}:
                candidates = [
                    MenuItem(
                        label=self.procedural_candidate_name(candidate_id, plan),
                        value=candidate_id,
                        enabled=True,
                        hint=str(
                            politics.get("candidate_platforms", {}).get(
                                candidate_id,
                                "Public Works",
                            )
                        ),
                    )
                    for candidate_id in politics.get("candidate_ids", [])
                ]
                candidates.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Candidates",
                    candidates,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    if choice.value == "endorse":
                        self.endorse_procedural_candidate(str(selected.value), plan)
                    else:
                        self.cast_procedural_election_vote(str(selected.value), plan)
            elif choice.value == "resolve":
                self.resolve_procedural_election(plan)

    def procedural_trade_route_management_menu(
        self,
        business: Dict[str, object],
    ) -> None:
        routes = [
            route
            for route in self.state.player_trade_routes.values()
            if route.get("business_id") == business.get("id")
        ]
        if not routes:
            self.set_message("This business has no established trade routes.")
            return
        route_items = []
        for route in routes:
            destination = self.civic_plan_for_key(
                str(route.get("destination_town_key", ""))
            ) or {}
            route_items.append(MenuItem(
                label=f"{route.get('good')} to {destination.get('name', 'Town')}",
                value=str(route.get("id")),
                enabled=True,
                hint=(
                    f"{self.procedural_trade_route_daily_income(route)}g/day | "
                    f"{'active' if route.get('active') else 'paused'}"
                ),
            ))
        route_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        selected = self.vertical_panel_select(
            "Manage Trade Routes",
            route_items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if not selected or selected.value == MENU_BACK:
            return
        route = self.state.player_trade_routes.get(str(selected.value))
        if not route:
            return
        while True:
            capacity = int(route.get("capacity_level", 0))
            escort = int(route.get("escort_level", 0))
            items = [
                MenuItem(
                    label="Route report",
                    value="report",
                    enabled=True,
                ),
                MenuItem(
                    label="Upgrade caravan capacity",
                    value="capacity",
                    enabled=capacity < 3,
                    hint=f"Level {capacity}/3",
                ),
                MenuItem(
                    label="Improve route escort",
                    value="escort",
                    enabled=escort < 3,
                    hint=f"Level {escort}/3",
                ),
                MenuItem(
                    label="Pause route" if route.get("active") else "Resume route",
                    value="toggle",
                    enabled=True,
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                str(route.get("good", "Trade Route")),
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "report":
                self.vertical_panel_view(
                    "Trade Route",
                    [
                        f"Good: {route.get('good')}",
                        f"Distance: {route.get('distance')} chunks",
                        f"Capacity: {route.get('capacity_level', 0)}/3",
                        f"Escort: {route.get('escort_level', 0)}/3",
                        f"Daily income: {self.procedural_trade_route_daily_income(route)}g",
                        f"Lifetime income: {route.get('lifetime_income', 0)}g",
                        f"Status: {'active' if route.get('active') else 'paused'}",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value in {"capacity", "escort"}:
                self.upgrade_player_trade_route(
                    str(route["id"]),
                    str(choice.value),
                )
            elif choice.value == "toggle":
                self.set_player_trade_route_active(
                    str(route["id"]),
                    not bool(route.get("active")),
                )

    def procedural_business_management_menu(
        self,
        building: Dict[str, object],
    ) -> None:
        plan = self.current_procedural_town_plan()
        if not plan:
            return
        while True:
            business = self.player_business_for_building(plan, building)
            price = self.procedural_business_price(plan, building)
            items = [
                MenuItem(
                    label="Purchase business",
                    value="purchase",
                    enabled=(
                        business is None
                        and self.procedural_town_reputation(plan) >= 40
                        and self.state.money >= price
                    ),
                    hint=f"{price}g; requires Welcome Friend reputation",
                ),
                MenuItem(
                    label="Business report",
                    value="report",
                    enabled=bool(business),
                ),
                MenuItem(
                    label="Set strategy",
                    value="strategy",
                    enabled=bool(business),
                ),
                MenuItem(
                    label="Upgrade business",
                    value="upgrade",
                    enabled=bool(business)
                    and int(business.get("upgrade_level", 0))
                    < len(BUSINESS_UPGRADE_NAMES),
                    hint=(
                        f"Level {business.get('upgrade_level', 0)}/3"
                        if business
                        else ""
                    ),
                ),
                MenuItem(
                    label="Temporarily close" if business and business.get("active") else "Reopen business",
                    value="toggle",
                    enabled=bool(business),
                ),
                MenuItem(
                    label="Appoint manager",
                    value="manager",
                    enabled=bool(business),
                ),
                MenuItem(
                    label="Hire resident",
                    value="hire",
                    enabled=bool(business)
                    and bool(
                        self.procedural_business_employee_candidates(business)
                        if business
                        else []
                    )
                    and len(business.get("employee_ids", []) or []) < 8
                    if business
                    else False,
                    hint=(
                        f"{len(business.get('employee_ids', []) or [])}/8 employees"
                        if business
                        else ""
                    ),
                ),
                MenuItem(
                    label="Set wage policy",
                    value="wages",
                    enabled=bool(business),
                    hint=str(business.get("wage_policy", "")) if business else "",
                ),
                MenuItem(
                    label="Set supply contract",
                    value="contract",
                    enabled=bool(business),
                    hint=str(business.get("supply_contract", "")) if business else "",
                ),
                MenuItem(
                    label="Establish trade route",
                    value="route",
                    enabled=bool(business) and len(self.discovered_procedural_town_plans()) >= 2,
                ),
                MenuItem(
                    label="Manage trade routes",
                    value="manage_routes",
                    enabled=bool(business) and any(
                        route.get("business_id") == business.get("id")
                        for route in self.state.player_trade_routes.values()
                    ),
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                f"{building.get('name')} Ownership",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "purchase":
                self.purchase_procedural_business(plan, building)
            elif choice.value == "report" and business:
                self.vertical_panel_view(
                    "Business Report",
                    [
                        str(business.get("name", "BUSINESS")).upper(),
                        "",
                        f"Strategy: {business.get('strategy')}",
                        f"Upgrade level: {business.get('upgrade_level', 0)}/3",
                        f"Operating: {'yes' if business.get('active') else 'no'}",
                        f"Daily income estimate: {self.procedural_business_daily_income(business)}g",
                        f"Lifetime income: {business.get('lifetime_income', 0)}g",
                        f"Total reinvested: {business.get('total_invested', 0)}g",
                        f"Manager assigned: {'yes' if business.get('manager_resident_id') else 'no'}",
                        f"Employees: {len(business.get('employee_ids', []) or [])}",
                        f"Wage policy: {business.get('wage_policy', 'Standard')}",
                        f"Supply contract: {business.get('supply_contract', 'Reliable Supply')}",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "strategy" and business:
                strategy_items = [
                    MenuItem(label=name, value=name, enabled=True, hint=description)
                    for name, description in BUSINESS_STRATEGIES.items()
                ]
                strategy_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Business Strategy",
                    strategy_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.set_procedural_business_strategy(
                        str(business["id"]),
                        str(selected.value),
                    )
            elif choice.value == "upgrade" and business:
                self.upgrade_procedural_business(str(business["id"]))
            elif choice.value == "toggle" and business:
                self.set_procedural_business_active(
                    str(business["id"]),
                    not bool(business.get("active")),
                )
            elif choice.value == "manager" and business:
                candidates = self.procedural_business_manager_candidates(plan, building)
                manager_items = [
                    MenuItem(
                        label=str(resident.get("name")),
                        value=str(resident.get("id")),
                        enabled=True,
                        hint=str(resident.get("role", "Resident")),
                    )
                    for resident in candidates
                ]
                manager_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Appoint Manager",
                    manager_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.appoint_procedural_business_manager(
                        str(business["id"]),
                        str(selected.value),
                    )
            elif choice.value == "hire" and business:
                candidates = self.procedural_business_employee_candidates(business)
                employee_items = [
                    MenuItem(
                        label=str(resident.get("name")),
                        value=str(resident.get("id")),
                        enabled=True,
                        hint=str(resident.get("role", "Resident")),
                    )
                    for resident in candidates
                ]
                employee_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Hire Resident",
                    employee_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.hire_procedural_business_employee(
                        str(business["id"]),
                        str(selected.value),
                    )
            elif choice.value == "wages" and business:
                wage_items = [
                    MenuItem(label=name, value=name, enabled=True, hint=description)
                    for name, description in BUSINESS_WAGE_POLICIES.items()
                ]
                wage_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Wage Policy",
                    wage_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.set_procedural_business_wage_policy(
                        str(business["id"]),
                        str(selected.value),
                    )
            elif choice.value == "contract" and business:
                contract_items = [
                    MenuItem(label=name, value=name, enabled=True, hint=description)
                    for name, description in BUSINESS_SUPPLY_CONTRACTS.items()
                ]
                contract_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Supply Contract",
                    contract_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.set_procedural_business_supply_contract(
                        str(business["id"]),
                        str(selected.value),
                    )
            elif choice.value == "route" and business:
                source_key = self.civic_town_key(plan)
                destinations = [
                    destination
                    for destination in self.discovered_procedural_town_plans()
                    if self.civic_town_key(destination) != source_key
                ]
                route_items = [
                    MenuItem(
                        label=str(destination.get("name")),
                        value=self.civic_town_key(destination),
                        enabled=True,
                        hint=(
                            f"Chunk {destination.get('chunk_x')},"
                            f"{destination.get('chunk_y')}"
                        ),
                    )
                    for destination in destinations
                ]
                route_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                selected = self.vertical_panel_select(
                    "Trade Destination",
                    route_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if selected and selected.value != MENU_BACK:
                    self.create_player_trade_route(
                        str(business["id"]),
                        str(selected.value),
                    )
            elif choice.value == "manage_routes" and business:
                self.procedural_trade_route_management_menu(business)


__all__ = [
    "BUSINESS_STRATEGIES",
    "BUSINESS_TYPES",
    "CivicEconomyMixin",
    "TOWN_POLICIES",
    "sanitize_civic_profile",
    "sanitize_player_businesses",
    "sanitize_player_properties",
    "sanitize_player_trade_routes",
]
