from __future__ import annotations

"""Rare procedural wilderness towns and their runtime interactions."""

from collections import deque
import copy
import math
import random
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ascii_farmstead_data import (
    LEFT_PANEL_HEIGHT,
    LEFT_PANEL_WIDTH,
    MENU_BACK,
)
from ascii_farmstead_npc_builder import (
    procedural_population_key,
    stable_text_seed,
)
from ascii_farmstead_npc_dialogue import BAD_WEATHER
from ascii_farmstead_town_builder import (
    SETTLEMENT_BUILDING_CATALOG,
    SETTLEMENT_STYLES,
    WildernessTownBuilder,
    parse_settlement_coord,
    settlement_chunk_key,
    settlement_rect_tiles,
)
from ascii_farmstead_ui import MenuItem


Position = Tuple[int, int]
PROCEDURAL_TOWN_RUNTIME_VERSION = 1
PROCEDURAL_TOWN_GRID_SIZE = 13
PROCEDURAL_TOWN_MIN_DISTANCE = 8
PROCEDURAL_TOWN_OVERWORLD_SYMBOL = "t"
PROCEDURAL_TOWN_SIGN_SYMBOL = "?"
PROCEDURAL_TOWN_DOOR_SYMBOL = "d"
PROCEDURAL_TOWN_INTERIOR_LOCATION = "ProceduralSettlementInterior"
PROCEDURAL_TOWN_OPEN_BUILDINGS = {"well", "market_stall", "park"}
PROCEDURAL_TOWN_BUILDING_SYMBOLS = {
    str(record["symbol"])
    for record in SETTLEMENT_BUILDING_CATALOG.values()
}

PROCEDURAL_TOWN_IDENTITIES = (
    {
        "industry": "timber and joinery",
        "architecture": "deep eaves, timber frames, and carved doorposts",
        "custom": "neighbors leave a marked scrap of wood when offering help",
        "food": "honey-glazed root stew",
        "founding": "carpenters and stranded wagon families rebuilt together after an early storm",
        "motto": "Measure twice; welcome once.",
        "concern": "The outer footbridges and roofs need reinforcing before the next severe season.",
        "story_item": "Wood",
        "story_quantities": (12, 20, 30),
        "exports": ("Wood", "Hardwood", "Fiber"),
        "imports": ("Coal", "Copper Bar", "Honey"),
        "festival_name": "Joiners' Exchange",
        "festival_activity": "demonstrating repairs, trading patterns, and raising a communal frame",
        "festival_gift": "Field Snack",
        "story_stages": (
            ("Storm Brace Supply", "Gather sound timber for the most exposed roofs.", "Fresh braces appear beneath the oldest eaves."),
            ("Bridge Workday", "Supply the lumber needed for a town-wide bridge repair.", "The footbridges are rebuilt with carved handrails."),
            ("Public Joinery Hall", "Provide the final stock for a permanent communal workshop.", "A public joinery hall preserves tools, patterns, and apprenticeships."),
        ),
    },
    {
        "industry": "herbs, remedies, and careful fieldwork",
        "architecture": "whitewashed walls, herb racks, and sheltered courtyards",
        "custom": "the first cup brewed from a new harvest is shared with a neighbor",
        "food": "herbed woodland salad",
        "founding": "foragers established a recovery camp that slowly became permanent",
        "motto": "Notice early; mend gently.",
        "concern": "The clinic garden is struggling to keep pace with travelers and winter stores.",
        "story_item": "Cave Herbs",
        "story_quantities": (3, 5, 8),
        "exports": ("Cave Herbs", "Health Potion", "Honey"),
        "imports": ("Fiber", "Wood", "Coal"),
        "festival_name": "First-Cup Gathering",
        "festival_activity": "sharing new remedies, comparing field notes, and brewing the season's first cup",
        "festival_gift": "Cave Herbs",
        "story_stages": (
            ("Emergency Tonic Stores", "Restock the clinic's most urgent herb shelves.", "Travelers find emergency tonics waiting by the clinic door."),
            ("Sheltered Herb Beds", "Supply enough herbs to establish hardy seed stock.", "New sheltered beds green the clinic courtyard."),
            ("Community Physic Garden", "Complete the stores needed for a permanent public garden.", "A public garden now teaches remedies and supports the clinic."),
        ),
    },
    {
        "industry": "market trade and road hospitality",
        "architecture": "painted signs, broad porches, and covered market walks",
        "custom": "new arrivals ring a small brass bell before their first market purchase",
        "food": "berry-and-honey travel bread",
        "founding": "two caravan routes began sharing one guarded rest stop",
        "motto": "Every road brings a story.",
        "concern": "Unreliable supplies are making the town too dependent on a single trade road.",
        "story_item": "Stone",
        "story_quantities": (10, 18, 26),
        "exports": ("Berries", "Honey", "Jam Toast"),
        "imports": ("Stone", "Wood", "Iron Ore"),
        "festival_name": "Roadsmeet Fair",
        "festival_activity": "welcoming caravans, exchanging road stories, and setting a long public table",
        "festival_gift": "Berry Mix",
        "story_stages": (
            ("Road Marker Foundations", "Provide stone for reliable markers on the weakest route.", "Fresh markers now guide travelers through bad visibility."),
            ("Covered Trade Walk", "Reinforce a sheltered place for delayed caravans.", "A covered walk keeps trade moving through poor weather."),
            ("Second Caravan Yard", "Finish a second receiving yard to diversify the town's roads.", "Two independent trade routes now serve the town."),
        ),
    },
    {
        "industry": "records, mapping, and wilderness scholarship",
        "architecture": "stone foundations, tall windows, and weatherproof archives",
        "custom": "every household adds one verified fact to the public ledger each season",
        "food": "mapmaker's mushroom toast",
        "founding": "surveyors stayed to preserve routes that otherwise vanished between seasons",
        "motto": "A remembered road remains open.",
        "concern": "The archive lacks durable materials for copying maps and local histories.",
        "story_item": "Fiber",
        "story_quantities": (6, 10, 16),
        "exports": ("Maple", "Field Snack", "Soft Fiber"),
        "imports": ("Fiber", "Cave Herbs", "Copper Ore"),
        "festival_name": "Ledger Day",
        "festival_activity": "copying maps, verifying local stories, and adding new facts to the public ledger",
        "festival_gift": "Maple",
        "story_stages": (
            ("Field Note Bindings", "Provide fiber for durable copies of vulnerable field notes.", "Weatherproof field books return to the surveyors."),
            ("Route Archive", "Bind the town's scattered maps into one public collection.", "A route archive now records safe paths and seasonal hazards."),
            ("Memory Room", "Finish enough archival material for a permanent history room.", "A public memory room preserves the town's stories and maps."),
        ),
    },
    {
        "industry": "metalwork, repair, and practical invention",
        "architecture": "stone workshops, metal brackets, and compact warm homes",
        "custom": "broken household objects are displayed once a year with the story of their repair",
        "food": "smoky corn and root skillet",
        "founding": "repair crews serving distant mines decided the road needed a permanent workshop",
        "motto": "Useful is beautiful.",
        "concern": "The workshop needs reliable fuel and fittings to keep public equipment maintained.",
        "story_item": "Coal",
        "story_quantities": (5, 9, 14),
        "exports": ("Copper Bar", "Iron Ore", "Coal"),
        "imports": ("Wood", "Fiber", "Cave Herbs"),
        "festival_name": "Mending Day",
        "festival_activity": "repairing household objects, telling their stories, and testing practical inventions",
        "festival_gift": "Coal",
        "story_stages": (
            ("Public Repair Fuel", "Replenish fuel for urgent repairs to public equipment.", "The workshop keeps a dedicated public repair furnace lit."),
            ("Shared Tool Rack", "Supply enough fuel to restore tools loaned across town.", "A shared rack of maintained tools opens to every household."),
            ("Civic Repair Works", "Complete the reserves for a permanent public repair program.", "The civic repair works now maintain wells, signs, and road fittings."),
        ),
    },
)

PROCEDURAL_DEVELOPMENT_STOCK = {
    "Growing Town": (("Honey", 90),),
    "Established Town": (("Hardwood", 135), ("Copper Bar", 210)),
    "Regional Center": (("Iron Bar", 390), ("Health Potion", 165)),
}

PROCEDURAL_LOCAL_STOCK = {
    "general_store": (
        ("Mixed Seeds", 30),
        ("Basic Fertilizer", 25),
        ("Field Snack", 45),
        ("Wood", 55),
        ("Stone", 40),
    ),
    "market_stall": (
        ("Wildflower", 30),
        ("Berries", 40),
        ("Watercress", 45),
        ("Honey", 90),
        ("Soft Fiber", 105),
    ),
    "clinic": (
        ("Cave Herbs", 65),
        ("Health Potion", 180),
        ("Mana Potion", 180),
        ("Animal Medicine", 130),
        ("Honey", 85),
    ),
    "carpenter": (
        ("Wood", 50),
        ("Stone", 38),
        ("Fiber", 45),
        ("Hardwood", 140),
    ),
    "workshop": (
        ("Coal", 55),
        ("Copper Ore", 75),
        ("Copper Bar", 220),
        ("Iron Ore", 125),
    ),
    "library": (
        ("Maple", 75),
        ("Fiber", 50),
        ("Cave Herbs", 70),
        ("Field Snack", 40),
    ),
    "inn": (
        ("Woodland Salad", 145),
        ("Jam Toast", 95),
        ("Berry Mix", 70),
        ("Field Snack", 45),
    ),
}


def procedural_town_completed_plan(plan: Dict[str, object]) -> Dict[str, object]:
    plan["status"] = "established"
    plan["source"] = "procedural_wilderness"
    plan["auto_generated"] = True
    plan["runtime_version"] = PROCEDURAL_TOWN_RUNTIME_VERSION
    for building in plan.get("buildings", {}).values():
        if not isinstance(building, dict):
            continue
        building["phase_index"] = 3
        building["status"] = "complete"
        building["material_contributions"] = {}
        building["money_contributed"] = 0
        building["labor_done"] = 0
    plan["construction_queue"] = []
    return plan


class ProceduralTownRuntimeMixin:
    """FarmGame integration for rare generated wilderness settlements."""

    def procedural_town_region_origin(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Position:
        size = PROCEDURAL_TOWN_GRID_SIZE
        return (int(chunk_x) // size) * size, (int(chunk_y) // size) * size

    def procedural_town_site_for_region(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Position:
        cell_x, cell_y = self.procedural_town_region_origin(chunk_x, chunk_y)
        cache = getattr(self, "_procedural_town_site_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._procedural_town_site_cache = cache
        cache_key = (int(getattr(self.state, "wilderness_seed", 0)), cell_x, cell_y)
        if cache_key in cache:
            return cache[cache_key]

        size = PROCEDURAL_TOWN_GRID_SIZE
        total = size * size
        start = int(self.wilderness_hash01(cell_x, cell_y, 33001) * total) % total
        step = 71  # Coprime to 13 * 13, so every cell position is visited.
        fallback: Optional[Position] = None
        for offset in range(total):
            index = (start + offset * step) % total
            candidate_x = cell_x + index % size
            candidate_y = cell_y + index // size
            if candidate_x == 0 and candidate_y == 0:
                continue
            if abs(candidate_x) + abs(candidate_y) < PROCEDURAL_TOWN_MIN_DISTANCE:
                continue
            if self.is_claimable_wilderness_chunk(candidate_x, candidate_y):
                continue
            if self.wilderness_chunk_has_dungeon_site(candidate_x, candidate_y):
                continue
            if self.wilderness_chunk_has_stronghold(candidate_x, candidate_y):
                continue
            if fallback is None:
                fallback = (candidate_x, candidate_y)
            if self.procedural_town_terrain_is_eligible(candidate_x, candidate_y):
                cache[cache_key] = (candidate_x, candidate_y)
                return cache[cache_key]
        cache[cache_key] = fallback or (cell_x + size - 1, cell_y + size - 1)
        return cache[cache_key]

    def procedural_town_terrain_is_eligible(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> bool:
        samples = (
            (16, 9), (43, 9), (70, 9),
            (16, 19), (43, 19), (70, 19),
            (16, 29), (43, 29), (70, 29),
        )
        water = 0
        ridge = 0
        for x, y in samples:
            world_x, world_y = self.wilderness_world_coords(chunk_x, chunk_y, x, y)
            if self.wilderness_world_water_tile(world_x, world_y):
                water += 1
            elif self.wilderness_world_biome_tile(world_x, world_y) == "x":
                ridge += 1
        return water <= 2 and ridge <= 5

    def wilderness_chunk_has_procedural_settlement(
        self,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> bool:
        cx = int(
            getattr(self.state, "wilderness_chunk_x", 0)
            if chunk_x is None
            else chunk_x
        )
        cy = int(
            getattr(self.state, "wilderness_chunk_y", 0)
            if chunk_y is None
            else chunk_y
        )
        return (cx, cy) == self.procedural_town_site_for_region(cx, cy)

    def procedural_town_plan(
        self,
        chunk_x: Optional[int] = None,
        chunk_y: Optional[int] = None,
    ) -> Optional[Dict[str, object]]:
        cx = int(
            getattr(self.state, "wilderness_chunk_x", 0)
            if chunk_x is None
            else chunk_x
        )
        cy = int(
            getattr(self.state, "wilderness_chunk_y", 0)
            if chunk_y is None
            else chunk_y
        )
        plan = self.wilderness_settlement_plan(cx, cy)
        if not isinstance(plan, dict):
            return None
        if str(plan.get("source", "")) != "procedural_wilderness":
            return None
        return plan

    def procedural_town_name(self, chunk_x: int, chunk_y: int) -> str:
        seed = self.wilderness_chunk_seed(chunk_x, chunk_y) + 33011
        return WildernessTownBuilder().generated_name(seed, chunk_x, chunk_y)

    def procedural_town_style(self, chunk_x: int, chunk_y: int) -> str:
        index = int(self.wilderness_hash01(chunk_x, chunk_y, 33012) * len(SETTLEMENT_STYLES))
        return SETTLEMENT_STYLES[min(len(SETTLEMENT_STYLES) - 1, index)]

    def ensure_procedural_town_community(
        self,
        plan: Dict[str, object],
    ) -> Dict[str, object]:
        service_state = plan.setdefault("service_state", {})
        community = service_state.get("community")
        if not isinstance(community, dict):
            community = {}
            service_state["community"] = community
        cx, cy = int(plan["chunk_x"]), int(plan["chunk_y"])
        identity_index = stable_text_seed(
            f"{plan.get('seed')}:{cx}:{cy}:identity"
        ) % len(PROCEDURAL_TOWN_IDENTITIES)
        identity = copy.deepcopy(PROCEDURAL_TOWN_IDENTITIES[identity_index])
        stored_identity = community.get("identity")
        if not isinstance(stored_identity, dict):
            stored_identity = {}
            community["identity"] = stored_identity
        for key, value in identity.items():
            stored_identity.setdefault(key, copy.deepcopy(value))
        community.setdefault("reputation", 0)
        community.setdefault("development_points", 0)
        community.setdefault("story_stage", 0)
        community.setdefault("story_completed", False)
        community.setdefault("story_log", [])
        community.setdefault("event_log", [])
        community.setdefault("last_event_day", "")
        community["social_version"] = max(
            2,
            int(community.get("social_version", 0)),
        )
        community.setdefault("social_log", [])
        community.setdefault("completed_projects", [])
        community.setdefault("market_day_key", "")
        community.setdefault("market_purchases", {})
        community.setdefault("market_sales", {})
        community.setdefault("commission_log", [])
        community.setdefault("support_claims", [])
        community.setdefault("founded_year", max(1, int(plan.get("seed", 1)) % 18 + 1))
        community.setdefault("last_life_year", int(getattr(self.state, "year", 1)))
        population = self.procedural_settlement_population(cx, cy)
        if population:
            self.ensure_procedural_town_social_network(plan, population)
        return community

    def procedural_town_identity(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        return dict(self.ensure_procedural_town_community(plan).get("identity", {}))

    def procedural_town_reputation(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> int:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return 0
        return int(self.ensure_procedural_town_community(plan).get("reputation", 0))

    def procedural_town_reputation_label(self, reputation: Optional[int] = None) -> str:
        value = self.procedural_town_reputation() if reputation is None else int(reputation)
        if value >= 120:
            return "Community Pillar"
        if value >= 75:
            return "Trusted Neighbor"
        if value >= 40:
            return "Welcome Friend"
        if value >= 15:
            return "Familiar Traveler"
        return "Outsider"

    def adjust_procedural_town_reputation(
        self,
        amount: int,
        reason: str = "",
        plan: Optional[Dict[str, object]] = None,
    ) -> int:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return 0
        community = self.ensure_procedural_town_community(plan)
        before = int(community.get("reputation", 0))
        after = max(0, min(200, before + int(amount)))
        community["reputation"] = after
        if reason and after != before:
            log = list(community.get("story_log", []) or [])
            log.append(f"{getattr(self.state, 'date_label', '')}: {reason} ({after - before:+} reputation)")
            community["story_log"] = log[-30:]
        return after - before

    def procedural_town_development_tier(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> str:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return "Unknown"
        community = self.ensure_procedural_town_community(plan)
        points = int(community.get("development_points", 0))
        if points >= 100:
            return "Regional Center"
        if points >= 55:
            return "Established Town"
        if points >= 25:
            return "Growing Town"
        return "Frontier Town"

    def procedural_town_day_key(self) -> str:
        return (
            f"{int(getattr(self.state, 'year', 1))}-"
            f"{int(getattr(self.state, 'month', 1))}-"
            f"{int(getattr(self.state, 'day', 1))}"
        )

    def procedural_town_development_rank(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> int:
        return {
            "Frontier Town": 0,
            "Growing Town": 1,
            "Established Town": 2,
            "Regional Center": 3,
        }.get(self.procedural_town_development_tier(plan), 0)

    def procedural_town_development_benefits(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> List[str]:
        rank = self.procedural_town_development_rank(plan)
        benefits = [
            "A basic local market and public services are operating.",
        ]
        if rank >= 1:
            benefits.append("Shops carry larger daily supplies and one regional good.")
        if rank >= 2:
            benefits.append("Skilled goods appear in local stock and civic commissions pay more.")
        if rank >= 3:
            benefits.append("The town offers its broadest stock, strongest services, and larger trade orders.")
        return benefits

    def procedural_town_market_profile(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        identity = self.procedural_town_identity(plan)
        exports = list(identity.get("exports", ()) or ["Wood"])
        imports = list(identity.get("imports", ()) or ["Stone"])
        day_key = self.procedural_town_day_key()
        seed = stable_text_seed(
            f"{plan.get('seed')}:{day_key}:{getattr(self.state, 'season', 'Spring')}:market"
        )
        surplus = str(exports[seed % len(exports)])
        demand = str(imports[(seed // 7) % len(imports)])
        weather = str(getattr(self.state, "weather", "Sunny"))
        if weather in {"Storm", "Stormy", "Blizzard"}:
            demand = "Wood" if "Wood" not in exports else "Cave Herbs"
        partner = self.procedural_town_trade_partner(plan)
        return {
            "day_key": day_key,
            "surplus": surplus,
            "demand": demand,
            "season": str(getattr(self.state, "season", "Spring")),
            "weather": weather,
            "partner": str(partner.get("name", "")) if partner else "",
            "headline": (
                f"Plenty of {surplus}; buyers are actively seeking {demand}."
            ),
        }

    def procedural_town_trade_partner(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        candidates: List[Tuple[int, Dict[str, object]]] = []
        for other in self.ensure_wilderness_settlements().values():
            if not isinstance(other, dict) or other is plan:
                continue
            if (
                str(other.get("source", "")) != "procedural_wilderness"
                or not bool(other.get("discovered"))
            ):
                continue
            distance = abs(int(other.get("chunk_x", 0)) - int(plan["chunk_x"]))
            distance += abs(int(other.get("chunk_y", 0)) - int(plan["chunk_y"]))
            candidates.append((distance, other))
        if not candidates:
            return {}
        distance, partner = min(
            candidates,
            key=lambda value: (value[0], str(value[1].get("name", ""))),
        )
        return {
            "name": str(partner.get("name", "another wilderness town")),
            "distance": distance,
            "chunk_x": int(partner.get("chunk_x", 0)),
            "chunk_y": int(partner.get("chunk_y", 0)),
        }

    def ensure_procedural_town_market_day(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        community = self.ensure_procedural_town_community(plan)
        day_key = self.procedural_town_day_key()
        if str(community.get("market_day_key", "")) != day_key:
            community["market_day_key"] = day_key
            community["market_purchases"] = {}
            community["market_sales"] = {}
        return community

    def procedural_town_demand_offer(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        profile = self.procedural_town_market_profile(plan)
        item = str(profile.get("demand", "Stone"))
        base_price = 0
        price_lookup = getattr(self, "shippable_unit_price", None)
        if callable(price_lookup):
            base_price = int(price_lookup(item))
        if base_price <= 0:
            base_price = next(
                (
                    int(price)
                    for stock in PROCEDURAL_LOCAL_STOCK.values()
                    for stock_item, price in stock
                    if stock_item == item
                ),
                20,
            )
        rank = self.procedural_town_development_rank(plan)
        reputation = self.procedural_town_reputation(plan)
        premium = 125 + rank * 5 + min(15, reputation // 10)
        limit = 5 + rank * 3
        community = self.ensure_procedural_town_market_day(plan)
        sold = int(community.get("market_sales", {}).get(item, 0))
        return {
            "item": item,
            "price": max(1, base_price * premium // 100),
            "limit": limit,
            "remaining": max(0, limit - sold),
            "premium": premium,
        }

    def sell_procedural_town_demand(
        self,
        item_name: str,
        quantity: int = 1,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        offer = self.procedural_town_demand_offer(plan)
        if not plan or str(offer.get("item")) != str(item_name):
            return False
        quantity = max(1, int(quantity))
        available = int(getattr(self.state, "inventory", {}).get(item_name, 0))
        remaining = int(offer.get("remaining", 0))
        if available < quantity or remaining < quantity:
            self.set_message(
                f"The town can buy at most {min(available, remaining)} more {item_name} today."
            )
            return False
        self.state.inventory[item_name] = available - quantity
        if self.state.inventory[item_name] <= 0:
            self.state.inventory.pop(item_name, None)
        payout = int(offer["price"]) * quantity
        self.state.money += payout
        community = self.ensure_procedural_town_market_day(plan)
        sales = community.setdefault("market_sales", {})
        sales[item_name] = int(sales.get(item_name, 0)) + quantity
        community["development_points"] = int(
            community.get("development_points", 0)
        ) + max(1, quantity // 3)
        self.adjust_procedural_town_reputation(
            min(3, 1 + quantity // 4),
            f"Filled local demand for {item_name}",
            plan,
        )
        self.autosave_with_message(
            f"Sold {quantity} {item_name} to {plan.get('name')} for {payout}g."
        )
        return True

    def procedural_town_commission(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        offer = self.procedural_town_demand_offer(plan)
        rank = self.procedural_town_development_rank(plan)
        quantity = min(int(offer.get("limit", 5)), 3 + rank * 2)
        reward = int(offer.get("price", 20)) * quantity + 60 + rank * 45
        key = f"{self.procedural_town_day_key()}:{offer.get('item')}"
        community = self.ensure_procedural_town_community(plan)
        return {
            "key": key,
            "item": str(offer.get("item", "Stone")),
            "quantity": quantity,
            "reward": reward,
            "completed": key in set(community.get("commission_log", []) or []),
        }

    def complete_procedural_town_commission(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        commission = self.procedural_town_commission(plan)
        if not plan or commission.get("completed"):
            return False
        item = str(commission["item"])
        quantity = int(commission["quantity"])
        if int(self.state.inventory.get(item, 0)) < quantity:
            self.set_message(f"The work board needs {quantity} {item}.")
            return False
        self.state.inventory[item] -= quantity
        if self.state.inventory[item] <= 0:
            self.state.inventory.pop(item, None)
        self.state.money += int(commission["reward"])
        community = self.ensure_procedural_town_community(plan)
        community["commission_log"] = (
            list(community.get("commission_log", []) or [])
            + [str(commission["key"])]
        )[-40:]
        community["development_points"] = int(
            community.get("development_points", 0)
        ) + 5
        self.adjust_procedural_town_reputation(
            5,
            f"Completed the civic work order for {item}",
            plan,
        )
        self.autosave_with_message(
            f"Completed {plan.get('name')}'s work order. Earned {commission['reward']}g."
        )
        return True

    def claim_procedural_town_support(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        if not plan or self.procedural_town_reputation(plan) < 75:
            return False
        community = self.ensure_procedural_town_community(plan)
        week_key = (
            f"{int(getattr(self.state, 'year', 1))}-"
            f"{int(getattr(self.state, 'month', 1))}-"
            f"{(int(getattr(self.state, 'day', 1)) - 1) // 7 + 1}"
        )
        if week_key in set(community.get("support_claims", []) or []):
            self.set_message("The town has already helped outfit you this week.")
            return False
        identity = self.procedural_town_identity(plan)
        exports = list(identity.get("exports", ()) or ["Field Snack"])
        item = str(exports[
            stable_text_seed(f"{plan.get('seed')}:{week_key}:support") % len(exports)
        ])
        quantity = 2 if self.procedural_town_development_rank(plan) >= 2 else 1
        self.state.inventory[item] = int(self.state.inventory.get(item, 0)) + quantity
        community["support_claims"] = (
            list(community.get("support_claims", []) or []) + [week_key]
        )[-24:]
        self.autosave_with_message(
            f"{plan.get('name')} provided {quantity} {item} from its community stores."
        )
        return True

    def advance_procedural_town_life(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> int:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return 0
        community = self.ensure_procedural_town_community(plan)
        current_year = int(getattr(self.state, "year", 1))
        last_year = int(community.get("last_life_year", current_year))
        if current_year <= last_year:
            return 0
        elapsed = current_year - last_year
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        if not population:
            community["last_life_year"] = current_year
            return 0

        transitions = 0
        transition_notes: List[str] = []
        aging_enabled = bool(
            getattr(self.state, "aging_and_death_enabled", True)
        )
        for resident in population.get("residents", {}).values():
            old_group = str(resident.get("age_group", "Adult"))
            old_age = int(resident.get("age_years", 30))
            if aging_enabled:
                new_age = min(95, old_age + elapsed)
            elif old_age < 18:
                new_age = min(18, old_age + elapsed)
            else:
                new_age = old_age
            if new_age < 13:
                new_group = "Child"
            elif new_age < 18:
                new_group = "Teen"
            elif new_age < 65:
                new_group = "Adult"
            else:
                new_group = "Elder"
            resident["age_years"] = new_age
            resident["age_group"] = new_group
            resident["romanceable"] = new_group in {"Adult", "Elder"}
            if new_group == old_group:
                continue
            transitions += 1
            if new_group == "Teen":
                resident["role"] = "Student"
                resident["profession_id"] = "student"
            elif new_group == "Adult" and str(resident.get("role")) == "Student":
                resident["role"] = "Settler"
                resident["profession_id"] = "settler"
                resident["workplace_building_id"] = ""
                resident["household_role"] = "Adult Household Member"
            elif new_group == "Elder":
                resident["role"] = "Retiree"
                resident["profession_id"] = "retiree"
                resident["workplace_building_id"] = ""
                resident["household_role"] = "Elder"
            tags = [
                str(tag)
                for tag in resident.get("dialogue_tags", []) or []
                if str(tag) not in {"child", "teen", "adult", "elder"}
            ]
            tags.append(new_group.lower())
            resident["dialogue_tags"] = list(dict.fromkeys(tags))[-8:]
            try:
                resident["schedule"] = self.procedural_npc_builder().resident_schedule(
                    plan,
                    resident,
                    plan.get("buildings", {}),
                )
            except (KeyError, TypeError, ValueError):
                pass
            note = f"Became a {new_group.lower()} in Year {current_year}."
            memories = list(resident.get("memories", []) or [])
            memories.append(note)
            resident["memories"] = memories[-16:]
            transition_notes.append(
                f"{resident.get('name', 'A resident')} entered {new_group.lower()}hood."
            )
        community["last_life_year"] = current_year
        if transition_notes:
            story_log = list(community.get("story_log", []) or [])
            story_log.extend(transition_notes)
            community["story_log"] = story_log[-30:]
            self.ensure_procedural_town_social_network(plan, population)
        return transitions

    def ensure_procedural_town_social_network(
        self,
        plan: Dict[str, object],
        population: Dict[str, object],
    ) -> None:
        residents = sorted(
            population.get("residents", {}).values(),
            key=lambda value: str(value.get("id", "")),
        )
        if len(residents) < 2:
            return
        signature_rows = tuple(
            (
                str(resident.get("id", "")),
                str(resident.get("household_id", "")),
                str(resident.get("workplace_building_id", "") or ""),
            )
            for resident in residents
        )
        signature = str(
            stable_text_seed(
                f"{plan.get('seed')}:{signature_rows}:social-network-v2"
            )
        )
        service_state = plan.setdefault("service_state", {})
        community = service_state.setdefault("community", {})
        if (
            isinstance(community, dict)
            and str(community.get("social_network_signature", ""))
            == signature
        ):
            return
        by_household: Dict[str, List[str]] = {}
        by_workplace: Dict[str, List[str]] = {}
        for resident in residents:
            by_household.setdefault(str(resident.get("household_id", "")), []).append(
                str(resident["id"])
            )
            workplace = str(resident.get("workplace_building_id", "") or "")
            if workplace:
                by_workplace.setdefault(workplace, []).append(str(resident["id"]))
        resident_ids = sorted(
            (str(resident["id"]) for resident in residents),
            key=lambda resident_id: stable_text_seed(
                f"{plan.get('seed')}:{resident_id}:social-order"
            ),
        )
        friend_by_id: Dict[str, str] = {}
        for index in range(0, len(resident_ids), 2):
            first = resident_ids[index]
            second = (
                resident_ids[index + 1]
                if index + 1 < len(resident_ids)
                else resident_ids[0]
            )
            friend_by_id[first] = second
            friend_by_id[second] = first
        for resident in residents:
            resident_id = str(resident["id"])
            family = [
                other_id
                for other_id in by_household.get(str(resident.get("household_id", "")), [])
                if other_id != resident_id
            ]
            coworkers = [
                other_id
                for other_id in by_workplace.get(
                    str(resident.get("workplace_building_id", "") or ""),
                    [],
                )
                if other_id != resident_id
            ]
            candidates = [
                other_id for other_id in resident_ids
                if other_id != resident_id and other_id not in family
            ]
            friend = friend_by_id.get(resident_id, "")
            if friend in family:
                friend = next(
                    (
                        candidate for candidate in candidates
                        if candidate not in coworkers
                    ),
                    candidates[0] if candidates else "",
                )
            rival_candidates = [
                other_id for other_id in candidates
                if other_id != friend and other_id not in coworkers
            ]
            rival = rival_candidates[
                stable_text_seed(f"{resident_id}:rival") % len(rival_candidates)
            ] if rival_candidates else ""
            resident["social_connections"] = {
                "family": family[:4],
                "coworkers": coworkers[:4],
                "friend": friend,
                "rival": rival,
            }
            traits = set(resident.get("personality_traits", []) or [])
            resident["social_opinion"] = (
                "protective of the town's routines"
                if "Protective" in traits
                else "curious about how the town is changing"
                if "Curious" in traits
                else "always looking for a fair compromise"
                if "Diplomatic" in traits or "Kind" in traits
                else "eager to prove that ambitious plans can work"
                if "Ambitious" in traits
                else "skeptical until a plan survives practical testing"
                if "Cautious" in traits
                else "practical about community problems"
            )
        if isinstance(community, dict):
            community["social_network_signature"] = signature

    def procedural_town_resident_name(
        self,
        resident_id: str,
        population: Dict[str, object],
    ) -> str:
        resident = population.get("residents", {}).get(str(resident_id), {})
        return str(resident.get("given_name") or resident.get("name") or "someone")

    def spread_procedural_town_social_reputation(
        self,
        resident: Dict[str, object],
        reason: str,
        plan: Optional[Dict[str, object]] = None,
    ) -> int:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return 0
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        connections = resident.get("social_connections", {})
        if not isinstance(connections, dict):
            return 0
        linked_ids = list(connections.get("family", []) or [])
        friend_id = str(connections.get("friend", "") or "")
        if friend_id:
            linked_ids.append(friend_id)
        changed = 0
        day_key = self.procedural_town_day_key()
        for resident_id in list(dict.fromkeys(linked_ids))[:3]:
            linked = population.get("residents", {}).get(str(resident_id))
            if not isinstance(linked, dict):
                continue
            flag = f"social_echo:{day_key}:{resident.get('id')}:{reason}"
            flags = list(linked.get("conversation_flags", []) or [])
            if flag in flags:
                continue
            linked["relationship"] = min(
                250,
                int(linked.get("relationship", 0)) + 1,
            )
            flags.append(flag)
            linked["conversation_flags"] = flags[-40:]
            changed += 1
        if changed:
            community = self.ensure_procedural_town_community(plan)
            social_log = list(community.get("social_log", []) or [])
            social_log.append(
                f"{resident.get('name', 'A resident')}'s {reason} reached {changed} close connection(s)."
            )
            community["social_log"] = social_log[-20:]
        return changed

    def add_procedural_town_specialty(
        self,
        plan: Dict[str, object],
    ) -> None:
        roll = int(self.wilderness_hash01(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
            33013,
        ) * 3)
        replacement = ("library", "workshop", "park")[min(2, roll)]
        lot_id = "lot_1_1"
        lot = plan.get("lots", {}).get(lot_id)
        if not isinstance(lot, dict):
            return
        old_building_id = str(lot.get("building_id", "") or "")
        if old_building_id:
            plan.get("buildings", {}).pop(old_building_id, None)
        lot["building_id"] = ""
        lot["zone"] = str(SETTLEMENT_BUILDING_CATALOG[replacement]["zone"])
        names = {
            "library": "Settlement Library",
            "workshop": "Common Works",
            "park": "Founders Green",
        }
        WildernessTownBuilder().place_building(
            plan,
            lot_id,
            replacement,
            building_id=f"specialty:{replacement}",
            name=names[replacement],
        )
        plan["specialty"] = replacement

    def ensure_procedural_town_plan(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Optional[Dict[str, object]]:
        cx, cy = int(chunk_x), int(chunk_y)
        if not self.wilderness_chunk_has_procedural_settlement(cx, cy):
            return None
        key = settlement_chunk_key(cx, cy)
        settlements = self.ensure_wilderness_settlements()
        existing = settlements.get(key)
        if isinstance(existing, dict):
            if str(existing.get("source", "")) != "procedural_wilderness":
                return None
            self.ensure_procedural_town_community(existing)
            return existing

        seed = self.wilderness_chunk_seed(cx, cy) + 33000
        plan = WildernessTownBuilder().create_plan(
            cx,
            cy,
            seed=seed,
            name=self.procedural_town_name(cx, cy),
            style=self.procedural_town_style(cx, cy),
        )
        self.add_procedural_town_specialty(plan)
        procedural_town_completed_plan(plan)
        plan["map_applied"] = False
        plan["discovered"] = False
        plan["discovered_day"] = ""
        plan.setdefault("notes", []).append(
            (
                "This naturally generated town occupies one deterministic "
                f"{PROCEDURAL_TOWN_GRID_SIZE}x{PROCEDURAL_TOWN_GRID_SIZE} wilderness region."
            )
        )
        settlements[key] = plan
        self.generate_procedural_settlement_population(cx, cy, force=True)
        self.ensure_procedural_town_community(plan)
        return plan

    def procedural_town_dominant_ground(
        self,
        grid: List[List[str]],
    ) -> str:
        counts: Dict[str, int] = {}
        for row in grid:
            for tile in row:
                if tile in {".", ";", "%", "l", "r", "x"}:
                    counts[tile] = counts.get(tile, 0) + 1
        if not counts:
            return "."
        tile = max(counts, key=counts.get)
        return "." if tile in {"x", "r"} else tile

    def apply_procedural_town_to_grid(
        self,
        grid: List[List[str]],
        chunk_x: int,
        chunk_y: int,
    ) -> List[List[str]]:
        plan = self.ensure_procedural_town_plan(chunk_x, chunk_y)
        if not plan or not grid:
            return grid
        height = len(grid)
        width = len(grid[0]) if height else 0
        ground = self.procedural_town_dominant_ground(grid)

        for lot in plan.get("lots", {}).values():
            if not isinstance(lot, dict):
                continue
            lot_ground = ";" if str(lot.get("zone")) == "Green" else ","
            for x, y in settlement_rect_tiles(
                int(lot["x"]),
                int(lot["y"]),
                int(lot["width"]),
                int(lot["height"]),
            ):
                if 1 <= x < width - 1 and 1 <= y < height - 1:
                    grid[y][x] = lot_ground

        for raw_coord in plan.get("roads", []):
            position = parse_settlement_coord(raw_coord)
            if not position:
                continue
            x, y = position
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = ":"

        for building in plan.get("buildings", {}).values():
            if not isinstance(building, dict):
                continue
            catalog = SETTLEMENT_BUILDING_CATALOG[str(building["type_id"])]
            symbol = str(catalog["symbol"])
            for x, y in settlement_rect_tiles(
                int(building["x"]),
                int(building["y"]),
                int(building["width"]),
                int(building["height"]),
            ):
                if 1 <= x < width - 1 and 1 <= y < height - 1:
                    grid[y][x] = symbol
            door_x, door_y = int(building["door_x"]), int(building["door_y"])
            if 0 <= door_x < width and 0 <= door_y < height:
                grid[door_y][door_x] = PROCEDURAL_TOWN_DOOR_SYMBOL
            access_x, access_y = int(building["access_x"]), int(building["access_y"])
            if 0 <= access_x < width and 0 <= access_y < height:
                grid[access_y][access_x] = ":"

        center_x, center_y = width // 2, height // 2
        for x in range(0, center_x + 1):
            if 0 < x < width - 1:
                grid[center_y][x] = ":"
        for x in range(center_x, width):
            if 0 < x < width - 1:
                grid[center_y][x] = ":"
        for y in range(0, center_y + 1):
            if 0 < y < height - 1:
                grid[y][center_x] = ":"
        for y in range(center_y, height):
            if 0 < y < height - 1:
                grid[y][center_x] = ":"

        entrance = plan.get("entrance", {})
        sign_x = max(2, min(width - 3, int(entrance.get("x", center_x)) + 2))
        sign_y = max(2, min(height - 3, int(entrance.get("y", height - 2)) - 1))
        grid[sign_y][sign_x] = PROCEDURAL_TOWN_SIGN_SYMBOL
        plan["sign_x"] = sign_x
        plan["sign_y"] = sign_y
        plan["map_applied"] = True
        plan["runtime_version"] = PROCEDURAL_TOWN_RUNTIME_VERSION
        plan["status"] = "established"

        for x in range(width):
            if grid[0][x] not in {"S"}:
                grid[0][x] = "#"
            if grid[height - 1][x] not in {"S"}:
                grid[height - 1][x] = "#"
        for y in range(height):
            grid[y][0] = "#"
            grid[y][width - 1] = "#"
        for x in range(max(1, center_x - 4), min(width - 1, center_x + 5)):
            grid[0][x] = ":"
            grid[height - 1][x] = ":"
            if height > 2:
                grid[1][x] = ground
                grid[height - 2][x] = ground
        for y in range(max(1, center_y - 4), min(height - 1, center_y + 5)):
            grid[y][0] = ":"
            grid[y][width - 1] = ":"
            if width > 2:
                grid[y][1] = ground
                grid[y][width - 2] = ground
        return grid

    def ensure_procedural_town_applied(
        self,
        grid: List[List[str]],
        chunk_x: int,
        chunk_y: int,
    ) -> List[List[str]]:
        plan = self.ensure_procedural_town_plan(chunk_x, chunk_y)
        if not plan:
            return grid
        if (
            bool(plan.get("map_applied"))
            and int(plan.get("runtime_version", 0)) >= PROCEDURAL_TOWN_RUNTIME_VERSION
            and any(PROCEDURAL_TOWN_DOOR_SYMBOL in row for row in grid)
        ):
            return grid
        return self.apply_procedural_town_to_grid(grid, chunk_x, chunk_y)

    def discover_procedural_town(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Optional[Dict[str, object]]:
        plan = self.procedural_town_plan(chunk_x, chunk_y)
        if not plan:
            return None
        newly_discovered = not bool(plan.get("discovered", False))
        if newly_discovered:
            plan["discovered"] = True
            plan["discovered_day"] = str(getattr(self.state, "date_label", ""))
            plan.setdefault("notes", []).append(
                f"Discovered on {plan['discovered_day'] or 'an unknown date'}."
            )
            self._procedural_town_just_discovered_name = str(plan.get("name", "a wilderness town"))
        self.reconcile_procedural_settlement_population(chunk_x, chunk_y)
        self.ensure_procedural_town_community(plan)
        self.advance_procedural_town_life(plan)
        if hasattr(self, "reconcile_player_business_staff"):
            self.reconcile_player_business_staff()
        if hasattr(self, "ensure_procedural_town_politics"):
            self.ensure_procedural_town_politics(plan)
        if hasattr(self, "process_civic_economy"):
            income = self.process_civic_economy()
            if income:
                self._procedural_town_civic_income = income
        if newly_discovered:
            self.adjust_procedural_town_reputation(
                2,
                "Arrived and introduced yourself to the town",
                plan,
            )
        return plan

    def current_procedural_town_plan(self) -> Optional[Dict[str, object]]:
        if str(getattr(self.state, "location", "")) == PROCEDURAL_TOWN_INTERIOR_LOCATION:
            key = str(getattr(self.state, "current_procedural_settlement_key", "") or "")
            try:
                cx_text, cy_text = key.split(",", 1)
                return self.procedural_town_plan(int(cx_text), int(cy_text))
            except Exception:
                return None
        if str(getattr(self.state, "location", "")) != "Wilderness":
            return None
        return self.procedural_town_plan(
            int(getattr(self.state, "wilderness_chunk_x", 0)),
            int(getattr(self.state, "wilderness_chunk_y", 0)),
        )

    def on_procedural_town(self) -> bool:
        return self.current_procedural_town_plan() is not None

    def on_procedural_town_interior(self) -> bool:
        return str(getattr(self.state, "location", "")) == PROCEDURAL_TOWN_INTERIOR_LOCATION

    def procedural_town_building_at(
        self,
        x: int,
        y: int,
        plan: Optional[Dict[str, object]] = None,
    ) -> Optional[Dict[str, object]]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return None
        for building in plan.get("buildings", {}).values():
            if not isinstance(building, dict):
                continue
            if (int(x), int(y)) in settlement_rect_tiles(
                int(building["x"]),
                int(building["y"]),
                int(building["width"]),
                int(building["height"]),
            ):
                return building
        return None

    def procedural_town_building_door_at(
        self,
        x: int,
        y: int,
        plan: Optional[Dict[str, object]] = None,
    ) -> Optional[Dict[str, object]]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return None
        for building in plan.get("buildings", {}).values():
            if not isinstance(building, dict):
                continue
            if int(building.get("door_x", -1)) == int(x) and int(
                building.get("door_y", -1)
            ) == int(y):
                return building
        return None

    def procedural_town_map_tile_passable(
        self,
        x: int,
        y: int,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return False
        grid = self.get_wilderness_chunk_map(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        if y < 0 or y >= len(grid) or x < 0 or x >= len(grid[y]):
            return False
        if self.procedural_town_building_at(x, y, plan):
            return False
        return grid[y][x] not in {
            "#", "~", "T", "o", "*", "V", "X", "!",
            PROCEDURAL_TOWN_SIGN_SYMBOL,
        }

    def procedural_town_interior_map(
        self,
        building: Optional[Dict[str, object]] = None,
    ) -> List[List[str]]:
        plan = self.current_procedural_town_plan()
        if not plan:
            return [["#" for _ in range(34)] for _ in range(18)]
        if building is None:
            building = plan.get("buildings", {}).get(
                str(getattr(self.state, "current_procedural_building_id", ""))
            )
        if not isinstance(building, dict):
            return [["#" for _ in range(34)] for _ in range(18)]
        cache = getattr(self, "_procedural_town_interior_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._procedural_town_interior_cache = cache
        community = self.ensure_procedural_town_community(plan)
        property_record = (
            self.player_property_for_building(plan, building)
            if hasattr(self, "player_property_for_building")
            and str(building.get("type_id")) == "home"
            else None
        )
        business_record = (
            self.player_business_for_building(plan, building)
            if hasattr(self, "player_business_for_building")
            else None
        )
        cache_key = (
            f"{plan.get('id')}:{building.get('id')}:{PROCEDURAL_TOWN_RUNTIME_VERSION}:"
            f"{self.procedural_town_development_rank(plan)}:"
            f"{community.get('story_stage', 0)}:"
            f"{bool(property_record)}:{bool(property_record and property_record.get('built'))}:"
            f"{int(property_record.get('upgrade_level', 0)) if property_record else 0}:"
            f"{bool(property_record and property_record.get('household_moved'))}:"
            f"{int(business_record.get('upgrade_level', 0)) if business_record else 0}"
        )
        if cache_key in cache:
            return cache[cache_key]

        width, height = 42, 20
        grid = [["." for _ in range(width)] for _ in range(height)]
        for x in range(width):
            grid[0][x] = "#"
            grid[height - 1][x] = "#"
        for y in range(height):
            grid[y][0] = "#"
            grid[y][width - 1] = "#"
        door_x = width // 2
        grid[height - 1][door_x] = "D"
        grid[height - 2][door_x] = "."
        type_id = str(building.get("type_id", "home"))

        for x in range(5, width - 5):
            if x not in {door_x - 1, door_x, door_x + 1}:
                grid[5][x] = "-"
        for x in range(7, width - 7, 5):
            grid[4][x] = "s"
        grid[8][door_x] = "&"
        grid[9][door_x] = "."
        grid[10][door_x - 5] = "t"
        grid[10][door_x + 5] = "t"
        grid[11][door_x - 5] = "c"
        grid[11][door_x + 5] = "c"

        if type_id in {"home", "inn"}:
            for x in (8, 13, width - 14, width - 9):
                grid[3][x] = "b"
            grid[3][door_x] = "f"
        if type_id in {"clinic"}:
            grid[3][10] = "b"
            grid[3][width - 11] = "b"
            grid[7][10] = "+"
            grid[7][width - 11] = "+"
        if type_id in {"library"}:
            for y in (3, 7, 12):
                for x in range(6, width - 6, 4):
                    grid[y][x] = "l"
        if type_id in {"carpenter", "workshop"}:
            grid[3][8] = "w"
            grid[3][width - 9] = "a"
            grid[7][8] = "x"
            grid[7][width - 9] = "x"
        if type_id in {"general_store"}:
            for x in range(8, width - 8, 4):
                grid[3][x] = "$"
        if type_id == "town_hall":
            grid[3][door_x] = "P"
            grid[3][door_x - 8] = "d"
            grid[3][door_x + 8] = "d"

        identity = self.procedural_town_identity(plan)
        development_rank = self.procedural_town_development_rank(plan)
        if development_rank >= 1:
            if type_id in {"general_store", "inn"}:
                grid[7][7] = "$"
                grid[7][width - 8] = "$"
            elif type_id == "clinic":
                grid[10][7] = "+"
            elif type_id == "library":
                grid[15][door_x - 6] = "l"
                grid[15][door_x + 6] = "l"
        if development_rank >= 2 and type_id in {"carpenter", "workshop"}:
            grid[12][7] = "w"
            grid[12][width - 8] = "a"
        if development_rank >= 3 and type_id == "town_hall":
            grid[7][door_x - 8] = "d"
            grid[7][door_x + 8] = "d"
        if community.get("story_completed") and type_id == "town_hall":
            grid[7][door_x] = "f"
        if business_record:
            upgrade_level = int(business_record.get("upgrade_level", 0))
            if upgrade_level >= 1:
                grid[15][7] = "$" if type_id in {"general_store", "inn"} else "s"
            if upgrade_level >= 2:
                grid[15][width - 8] = "s"
            if upgrade_level >= 3:
                grid[16][door_x] = "P"
        decor_seed = stable_text_seed(
            f"{plan.get('seed')}:{building.get('id')}:{identity.get('industry')}"
        )
        for offset in range(5):
            x = 5 + (decor_seed + offset * 11) % (width - 10)
            y = 6 + (decor_seed // (offset + 1) + offset * 7) % (height - 10)
            if grid[y][x] == ".":
                grid[y][x] = "p" if offset < 2 else ","
        if type_id == "home":
            population = self.procedural_settlement_population(
                int(plan["chunk_x"]),
                int(plan["chunk_y"]),
            ) or {}
            household_members = [
                resident
                for resident in population.get("residents", {}).values()
                if str(resident.get("home_building_id", "")) == str(building.get("id"))
            ]
            for index, _resident in enumerate(household_members[:4]):
                x = 7 + index * 8
                grid[3][min(width - 4, x)] = "b"
            if any(
                str(resident.get("age_group")) in {"Child", "Teen"}
                for resident in household_members
            ):
                grid[7][width - 8] = "P"
            if property_record:
                grid[14][7] = "b"
                grid[14][11] = "c"
                grid[14][15] = "P"
                if property_record.get("built"):
                    grid[13][7] = "p"
                    grid[13][15] = "p"
                upgrade_level = int(property_record.get("upgrade_level", 0))
                if upgrade_level >= 1:
                    grid[14][27] = "s"
                    grid[14][31] = "c"
                if upgrade_level >= 2:
                    grid[16][19] = "t"
                    grid[16][23] = "c"
                if upgrade_level >= 3:
                    grid[13][27] = "p"
                    grid[13][31] = "f"

        cache[cache_key] = grid
        return grid

    def current_procedural_town_building(self) -> Optional[Dict[str, object]]:
        plan = self.current_procedural_town_plan()
        if not plan:
            return None
        building = plan.get("buildings", {}).get(
            str(getattr(self.state, "current_procedural_building_id", ""))
        )
        return building if isinstance(building, dict) else None

    def enter_procedural_town_building(
        self,
        building: Dict[str, object],
    ) -> bool:
        plan = self.current_procedural_town_plan()
        if not plan:
            return False
        type_id = str(building.get("type_id", ""))
        if type_id in PROCEDURAL_TOWN_OPEN_BUILDINGS:
            self.procedural_town_building_service(building)
            return False
        self.state.current_procedural_settlement_key = settlement_chunk_key(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        self.state.current_procedural_building_id = str(building["id"])
        self.state.procedural_settlement_return_x = int(building["access_x"])
        self.state.procedural_settlement_return_y = int(building["access_y"])
        self.state.location = PROCEDURAL_TOWN_INTERIOR_LOCATION
        interior = self.procedural_town_interior_map(building)
        self.state.player_x = len(interior[0]) // 2
        self.state.player_y = len(interior) - 3
        self.state.facing = "UP"
        self.set_message(f"You entered {building.get('name', 'the building')}.")
        return True

    def exit_procedural_town_building(self) -> bool:
        key = str(getattr(self.state, "current_procedural_settlement_key", "") or "")
        try:
            cx_text, cy_text = key.split(",", 1)
            cx, cy = int(cx_text), int(cy_text)
        except Exception:
            return False
        building = self.current_procedural_town_building()
        self.state.location = "Wilderness"
        self.state.wilderness_chunk_x = cx
        self.state.wilderness_chunk_y = cy
        self.wilderness_map = self.get_wilderness_chunk_map(cx, cy)
        self.state.player_x = max(
            1,
            min(
                len(self.wilderness_map[0]) - 2,
                int(getattr(self.state, "procedural_settlement_return_x", 1)),
            ),
        )
        self.state.player_y = max(
            1,
            min(
                len(self.wilderness_map) - 2,
                int(getattr(self.state, "procedural_settlement_return_y", 1)),
            ),
        )
        self.state.facing = "DOWN"
        self.state.current_procedural_building_id = ""
        self.set_message(
            f"You stepped outside {building.get('name', 'the building') if building else 'the building'}."
        )
        return True

    def procedural_town_building_lines(
        self,
        building: Dict[str, object],
        plan: Optional[Dict[str, object]] = None,
    ) -> List[str]:
        plan = plan or self.current_procedural_town_plan() or {}
        population = self.procedural_settlement_population(
            int(plan.get("chunk_x", 0)),
            int(plan.get("chunk_y", 0)),
        ) or {}
        staff = [
            str(resident.get("name"))
            for resident in population.get("residents", {}).values()
            if str(resident.get("workplace_building_id", "")) == str(building.get("id"))
        ]
        catalog = SETTLEMENT_BUILDING_CATALOG.get(str(building.get("type_id")), {})
        return [
            str(building.get("name", "Settlement Building")).upper(),
            "",
            f"Town: {plan.get('name', 'Wilderness Settlement')}",
            f"Type: {catalog.get('name', building.get('type_id', 'Building'))}",
            f"Staff: {', '.join(staff) if staff else 'No assigned staff'}",
            f"Local style: {self.procedural_town_identity(plan).get('architecture', 'practical frontier construction')}",
            "",
            "This building was generated from the settlement blueprint.",
            "Its residents, workplace assignments, and schedules persist with the town.",
        ]

    def procedural_town_resident_schedule_entry(
        self,
        resident: Dict[str, object],
        plan: Dict[str, object],
        context: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        context = context or self.procedural_settlement_dialogue_context(
            int(plan["chunk_x"]), int(plan["chunk_y"])
        )
        return self.procedural_npc_builder().routine_for(
            resident,
            str(context["phase"]),
            bad_weather=bool(context["bad_weather"]),
        )

    def procedural_town_nearest_resident_tile(
        self,
        plan: Dict[str, object],
        x: int,
        y: int,
        used: Set[Position],
    ) -> Optional[Position]:
        grid = self.get_wilderness_chunk_map(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        queue = deque([(int(x), int(y))])
        seen = {(int(x), int(y))}
        while queue:
            tx, ty = queue.popleft()
            if (
                (tx, ty) not in used
                and (tx, ty) != (
                    int(getattr(self.state, "player_x", -1)),
                    int(getattr(self.state, "player_y", -1)),
                )
                and self.procedural_town_map_tile_passable(tx, ty, plan)
            ):
                return tx, ty
            for nx, ny in ((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)):
                if (nx, ny) in seen:
                    continue
                if 0 <= ny < len(grid) and 0 <= nx < len(grid[ny]):
                    seen.add((nx, ny))
                    queue.append((nx, ny))
            if len(seen) > 220:
                break
        return None

    def procedural_town_resident_runtime_destination(
        self,
        resident: Dict[str, object],
        plan: Dict[str, object],
        context: Optional[Dict[str, object]] = None,
        event: Optional[Dict[str, object]] = None,
    ) -> Tuple[str, int, int, str]:
        context = context or self.procedural_settlement_dialogue_context(
            int(plan["chunk_x"]), int(plan["chunk_y"])
        )
        event = (
            self.procedural_town_active_event(plan)
            if event is None
            else event
        )
        if event and str(event.get("phase")) == str(
            context.get("phase")
        ):
            building = next(
                (
                    value for value in plan.get("buildings", {}).values()
                    if str(value.get("type_id")) == str(event.get("building_type"))
                ),
                None,
            )
            if isinstance(building, dict):
                if str(building.get("type_id")) in PROCEDURAL_TOWN_OPEN_BUILDINGS:
                    return (
                        "outdoor",
                        int(building.get("access_x", 1)),
                        int(building.get("access_y", 1)),
                        str(event.get("activity", "joining a town gathering")),
                    )
                return (
                    f"building:{building.get('id')}",
                    -1,
                    -1,
                    str(event.get("activity", "joining a town gathering")),
                )
        entry = self.procedural_town_resident_schedule_entry(
            resident,
            plan,
            context,
        )
        activity = str(entry.get("activity", "following today's routine"))
        if str(entry.get("kind", "")) == "building":
            building_id = str(entry.get("building_id", "") or "")
            building = plan.get("buildings", {}).get(building_id)
            type_id = str(building.get("type_id", "")) if isinstance(building, dict) else ""
            if isinstance(building, dict) and type_id not in PROCEDURAL_TOWN_OPEN_BUILDINGS:
                return f"building:{building_id}", -1, -1, activity
            if isinstance(building, dict):
                return (
                    "outdoor",
                    int(building.get("access_x", entry.get("x", 1))),
                    int(building.get("access_y", entry.get("y", 1))),
                    activity,
                )
        return (
            "outdoor",
            int(entry.get("x", 1)),
            int(entry.get("y", 1)),
            activity,
        )

    def procedural_town_interior_resident_candidates(self) -> List[Position]:
        return [
            (9, 9), (14, 9), (27, 9), (32, 9),
            (9, 14), (14, 14), (27, 14), (32, 14),
            (19, 8), (23, 8), (19, 14), (23, 14),
        ]

    def procedural_town_runtime_tile_passable(
        self,
        x: int,
        y: int,
        occupied: Set[Position],
        plan: Dict[str, object],
        interior: bool,
    ) -> bool:
        if (int(x), int(y)) in occupied:
            return False
        if (int(x), int(y)) == (
            int(getattr(self.state, "player_x", -1)),
            int(getattr(self.state, "player_y", -1)),
        ):
            return False
        if interior:
            grid = self.procedural_town_interior_map()
            if not (0 <= y < len(grid) and 0 <= x < len(grid[y])):
                return False
            return grid[y][x] not in {
                "#", "-", "D", "&", "$", "+", "l", "w", "x", "a",
                "b", "t", "c", "s", "f", "P", "d", "p",
            }
        return self.procedural_town_map_tile_passable(x, y, plan)

    def ensure_procedural_town_resident_runtime(
        self,
        force_reanchor: bool = False,
    ) -> None:
        plan = self.current_procedural_town_plan()
        if not plan:
            return
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        if not population:
            return
        context = self.procedural_settlement_dialogue_context(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        event = self.procedural_town_active_event(plan)
        phase = str(context["phase"])
        day_key = str(context["day_key"])
        weather = str(context["weather"])
        interior = self.on_procedural_town_interior()
        current_building = self.current_procedural_town_building() if interior else None
        current_building_id = str(current_building.get("id", "")) if current_building else ""
        event_signature = (
            str(event.get("phase", "")),
            str(event.get("building_type", "")),
            str(event.get("activity", "")),
        ) if isinstance(event, dict) else ("", "", "")
        resident_ids = tuple(sorted(
            str(resident_id)
            for resident_id in population.get("residents", {})
        ))
        runtime_signature = (
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
            phase,
            day_key,
            weather,
            bool(interior),
            current_building_id,
            event_signature,
            resident_ids,
        )
        if (
            not force_reanchor
            and getattr(self, "_procedural_resident_runtime_signature", None)
            == runtime_signature
        ):
            return
        occupied: Set[Position] = set()
        indoor_index = 0
        for resident in sorted(
            population.get("residents", {}).values(),
            key=lambda value: str(value.get("id", "")),
        ):
            if bool(resident.get("deceased", False)):
                continue
            location, target_x, target_y, activity = (
                self.procedural_town_resident_runtime_destination(
                    resident,
                    plan,
                    context,
                    event,
                )
            )
            previous_day_key = str(resident.get("runtime_day_key", ""))
            changed = (
                force_reanchor
                or str(resident.get("runtime_phase", "")) != phase
                or str(resident.get("runtime_day_key", "")) != day_key
                or str(resident.get("runtime_weather", "")) != weather
                or str(resident.get("runtime_location", "")) != location
            )
            resident["runtime_phase"] = phase
            resident["runtime_day_key"] = day_key
            resident["runtime_weather"] = weather
            resident["runtime_location"] = location
            resident["runtime_activity"] = activity
            resident["procedural_resident"] = True
            if previous_day_key != day_key:
                resident["runtime_steps_today"] = 0

            if interior:
                if location != f"building:{current_building_id}":
                    continue
                candidates = self.procedural_town_interior_resident_candidates()
                preferred = candidates[
                    stable_text_seed(resident.get("id", "")) % len(candidates)
                ]
                if changed or not self.procedural_town_runtime_tile_passable(
                    int(resident.get("runtime_x", -1)),
                    int(resident.get("runtime_y", -1)),
                    occupied,
                    plan,
                    interior=True,
                ):
                    ordered = candidates[indoor_index:] + candidates[:indoor_index]
                    position = next(
                        (
                            candidate
                            for candidate in ordered
                            if self.procedural_town_runtime_tile_passable(
                                candidate[0],
                                candidate[1],
                                occupied,
                                plan,
                                interior=True,
                            )
                        ),
                        preferred,
                    )
                    resident["runtime_x"], resident["runtime_y"] = position
                position = (
                    int(resident.get("runtime_x", preferred[0])),
                    int(resident.get("runtime_y", preferred[1])),
                )
                occupied.add(position)
                indoor_index += 1
                continue

            if location != "outdoor":
                continue
            runtime_x = int(resident.get("runtime_x", -1))
            runtime_y = int(resident.get("runtime_y", -1))
            if (
                changed
                or not self.procedural_town_map_tile_passable(
                    runtime_x,
                    runtime_y,
                    plan,
                )
                or (runtime_x, runtime_y) in occupied
            ):
                position = self.procedural_town_nearest_resident_tile(
                    plan,
                    target_x,
                    target_y,
                    occupied,
                )
                if position is None:
                    continue
                resident["runtime_x"], resident["runtime_y"] = position
            occupied.add((
                int(resident.get("runtime_x", target_x)),
                int(resident.get("runtime_y", target_y)),
            ))
        self._procedural_resident_runtime_signature = runtime_signature

    def update_procedural_town_residents(
        self,
        force_reanchor: bool = False,
    ) -> None:
        plan = self.current_procedural_town_plan()
        if not plan:
            return
        self.ensure_procedural_town_resident_runtime(force_reanchor=force_reanchor)
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        if not population:
            return
        self._procedural_resident_move_tick = (
            int(getattr(self, "_procedural_resident_move_tick", 0)) + 1
        )
        tick = int(self._procedural_resident_move_tick)
        interior = self.on_procedural_town_interior()
        current_building = self.current_procedural_town_building() if interior else None
        visible_location = (
            f"building:{current_building.get('id')}" if current_building else "outdoor"
        )
        residents = [
            resident
            for resident in population.get("residents", {}).values()
            if (
                not bool(resident.get("deceased", False))
                and str(resident.get("runtime_location", "")) == visible_location
            )
        ]
        occupied: Set[Position] = {
            (
                int(resident.get("runtime_x", -1)),
                int(resident.get("runtime_y", -1)),
            )
            for resident in residents
        }
        context = self.procedural_settlement_dialogue_context(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        event = self.procedural_town_active_event(plan)
        for resident in sorted(residents, key=lambda value: str(value.get("id", ""))):
            x = int(resident.get("runtime_x", -1))
            y = int(resident.get("runtime_y", -1))
            if x < 0 or y < 0:
                continue
            role = str(resident.get("role", "Settler"))
            move_percent = 32
            if role in {"Student", "Merchant", "Carpenter Apprentice"}:
                move_percent = 48
            elif role in {"Mayor", "Librarian", "Archivist", "Doctor", "Retiree"}:
                move_percent = 20
            if str(resident.get("runtime_phase", "")) == "late":
                move_percent //= 2
            if str(resident.get("runtime_weather", "")) in BAD_WEATHER:
                move_percent //= 2
            roll = stable_text_seed(
                f"{resident.get('id')}:{resident.get('runtime_day_key')}:{tick}"
            ) % 100
            if roll >= move_percent:
                continue
            occupied.discard((x, y))
            options = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            rotation = stable_text_seed(f"{resident.get('id')}:{tick}:direction") % 4
            options = options[rotation:] + options[:rotation]
            if interior:
                target_x, target_y = 21, 10
                radius = 14
            else:
                _location, target_x, target_y, _activity = (
                    self.procedural_town_resident_runtime_destination(
                        resident,
                        plan,
                        context,
                        event,
                    )
                )
                radius = 6
            if abs(x - target_x) + abs(y - target_y) > radius:
                options.sort(
                    key=lambda delta: abs(x + delta[0] - target_x)
                    + abs(y + delta[1] - target_y)
                )
            moved = False
            for dx, dy in options:
                nx, ny = x + dx, y + dy
                if not interior and abs(nx - target_x) + abs(ny - target_y) > radius + 2:
                    continue
                if not self.procedural_town_runtime_tile_passable(
                    nx,
                    ny,
                    occupied,
                    plan,
                    interior,
                ):
                    continue
                resident["runtime_x"], resident["runtime_y"] = nx, ny
                resident["runtime_facing"] = (
                    "RIGHT" if dx > 0 else "LEFT" if dx < 0
                    else "DOWN" if dy > 0 else "UP"
                )
                resident["runtime_steps_today"] = int(
                    resident.get("runtime_steps_today", 0)
                ) + 1
                occupied.add((nx, ny))
                moved = True
                break
            if not moved:
                occupied.add((x, y))

    def procedural_town_resident_position_lookup(
        self,
    ) -> Dict[Position, Dict[str, object]]:
        plan = self.current_procedural_town_plan()
        if not plan:
            return {}
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        if not population:
            return {}
        lookup: Dict[Position, Dict[str, object]] = {}
        self.ensure_procedural_town_resident_runtime()
        if self.on_procedural_town_interior():
            building = self.current_procedural_town_building()
            visible_location = (
                f"building:{building.get('id')}" if building else ""
            )
        else:
            visible_location = "outdoor"
        deceased_ids = set(
            getattr(self.state, "deceased_spouse_npc_ids", []) or []
        )
        for resident in population.get("residents", {}).values():
            if (
                bool(resident.get("deceased", False))
                or str(resident.get("id", "")) in deceased_ids
            ):
                continue
            if (
                str(resident.get("id", ""))
                == str(getattr(self.state, "spouse_npc_id", ""))
                and bool(getattr(self.state, "spouse_moved_to_farm", False))
            ):
                continue
            if str(resident.get("runtime_location", "")) != visible_location:
                continue
            position = (
                int(resident.get("runtime_x", -1)),
                int(resident.get("runtime_y", -1)),
            )
            if position[0] < 0 or position[1] < 0:
                continue
            resident["x"], resident["y"] = position
            lookup[position] = resident
        if (
            self.on_procedural_town_interior()
            and building
            and hasattr(self, "procedural_town_household_members")
        ):
            household_members = self.procedural_town_household_members(
                plan,
                building,
            )
            candidates = [
                (7, 16), (11, 16), (15, 16), (27, 16),
                (31, 16), (19, 13), (23, 13), (34, 13),
            ]
            for member in household_members:
                position = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate not in lookup
                        and self.procedural_town_runtime_tile_passable(
                            candidate[0],
                            candidate[1],
                            set(lookup),
                            plan,
                            interior=True,
                        )
                    ),
                    None,
                )
                if position is None:
                    continue
                member["x"], member["y"] = position
                member["runtime_x"], member["runtime_y"] = position
                lookup[position] = member
        if (
            not self.on_procedural_town_interior()
            and hasattr(self, "dynasty_kin_for_procedural_town")
        ):
            candidates = [
                (8, 18), (14, 18), (20, 18), (28, 18),
                (36, 18), (44, 18), (52, 18), (60, 18),
                (10, 14), (22, 14), (46, 14), (58, 14),
            ]
            for relative in self.dynasty_kin_for_procedural_town(plan):
                position = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate not in lookup
                        and self.procedural_town_runtime_tile_passable(
                            candidate[0],
                            candidate[1],
                            set(lookup),
                            plan,
                            interior=False,
                        )
                    ),
                    None,
                )
                if position is None:
                    continue
                relative["x"], relative["y"] = position
                relative["runtime_x"], relative["runtime_y"] = position
                relative["runtime_location"] = "outdoor"
                lookup[position] = relative
        if (
            not self.on_procedural_town_interior()
            and hasattr(self, "procedural_town_caravan_actors")
        ):
            for caravan in self.procedural_town_caravan_actors(plan, set(lookup)):
                position = (
                    int(caravan.get("runtime_x", -1)),
                    int(caravan.get("runtime_y", -1)),
                )
                if position[0] >= 0 and position[1] >= 0 and position not in lookup:
                    lookup[position] = caravan
        return lookup

    def procedural_town_resident_at(
        self,
        x: int,
        y: int,
    ) -> Optional[Dict[str, object]]:
        return self.procedural_town_resident_position_lookup().get((int(x), int(y)))

    def procedural_town_plan_for_resident(
        self,
        resident: Dict[str, object],
    ) -> Optional[Dict[str, object]]:
        resident_id = str(resident.get("id", ""))
        populations = getattr(
            self.state,
            "procedural_settlement_populations",
            {},
        )
        if not isinstance(populations, dict):
            return None
        for town_key, population in populations.items():
            if not isinstance(population, dict):
                continue
            residents = population.get("residents", {})
            if not isinstance(residents, dict) or resident_id not in residents:
                continue
            try:
                chunk_x, chunk_y = [
                    int(value)
                    for value in str(town_key).split(",", 1)
                ]
            except (TypeError, ValueError):
                return None
            return self.procedural_town_plan(chunk_x, chunk_y)
        return None

    def procedural_town_resident_profile_lines(
        self,
        resident: Dict[str, object],
    ) -> List[str]:
        plan = (
            self.current_procedural_town_plan()
            or self.procedural_town_plan_for_resident(resident)
            or {}
        )
        population = self.procedural_settlement_population(
            int(plan.get("chunk_x", 0)),
            int(plan.get("chunk_y", 0)),
        ) or {}
        connections = resident.get("social_connections", {})
        family_ids = (
            connections.get("family", [])
            if isinstance(connections, dict)
            else []
        )
        family = [
            self.procedural_town_resident_name(resident_id, population)
            for resident_id in family_ids
        ]
        friend = self.procedural_town_resident_name(
            str(connections.get("friend", ""))
            if isinstance(connections, dict)
            else "",
            population,
        )
        lines = [
            str(resident.get("name", "Resident")).upper(),
            "",
            f"Town: {plan.get('name', 'Wilderness Settlement')}",
            f"Role: {resident.get('role', 'Settler')}",
            (
                f"Age: {resident.get('age_group', 'Adult')} "
                f"({resident.get('age_years', '?')})"
                if bool(
                    getattr(
                        self.state,
                        "aging_and_death_enabled",
                        True,
                    )
                )
                else f"Life stage: {resident.get('age_group', 'Adult')}"
            ),
            f"Household role: {resident.get('household_role', 'Resident')}",
            f"Personality: {resident.get('personality', 'Practical')}",
            f"Community outlook: {resident.get('social_opinion', 'practical about community problems')}",
            f"Current activity: {resident.get('runtime_activity', 'following today’s routine')}",
            f"Goal: {resident.get('goal', '')}",
            f"Family here: {', '.join(family) if family else 'None listed'}",
            f"Close friend: {friend if friend != 'someone' else 'Not yet established'}",
            "",
            f"Likes: {', '.join(resident.get('likes', []) or []) or 'Unknown'}",
            f"Dislikes: {', '.join(resident.get('dislikes', []) or []) or 'Unknown'}",
            f"Relationship: {resident.get('relationship', 0)}",
            f"Times spoken: {resident.get('dialogue_count', 0)}",
        ]
        if self.is_marriageable_npc(resident):
            lines.extend(["", *self.town_npc_romance_lines(resident)])
        return lines

    def procedural_town_resident_status_lines(
        self,
        resident: Dict[str, object],
    ) -> List[str]:
        plan = self.current_procedural_town_plan() or {}
        cx, cy = int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))
        request_status = self.procedural_settlement_request_status(
            cx,
            cy,
            str(resident.get("id", "")),
        )
        lines = [
            str(resident.get("name", "Resident")).upper(),
            "",
            f"Relationship: {resident.get('relationship', 0)}",
            f"Met: {'yes' if resident.get('met') else 'no'}",
            f"Times spoken: {resident.get('dialogue_count', 0)}",
            f"Last topic: {str(resident.get('last_dialogue_topic', '') or 'none').replace('_', ' ').title()}",
            f"Current activity: {resident.get('runtime_activity', 'following today’s routine')}",
            f"Current schedule phase: {str(resident.get('runtime_phase', '') or 'unknown').replace('_', ' ').title()}",
            f"Steps today: {resident.get('runtime_steps_today', 0)}",
            f"Request: {request_status}",
            "",
            f"Memories recorded: {len(resident.get('memories', []) or [])}",
            f"Completed requests: {len(resident.get('completed_request_ids', []) or [])}",
        ]
        if self.is_marriageable_npc(resident):
            lines.extend(["", *self.town_npc_romance_lines(resident)])
        return lines

    def procedural_town_primary_dialogue_topic(
        self,
        resident: Dict[str, object],
        plan: Dict[str, object],
    ) -> str:
        if not bool(resident.get("met", False)):
            return "chat"
        resident_id = str(resident.get("id", ""))
        available = set(self.procedural_settlement_dialogue_topics(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
            resident_id,
        ))
        context = self.procedural_settlement_dialogue_context(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        )
        topics: List[str] = []
        if bool(context.get("bad_weather")):
            topics.append("weather")
        phase = str(context.get("phase", ""))
        if phase in {"work_morning", "work_afternoon"}:
            topics.append("work")
        elif phase in {"evening", "late", "wake"}:
            topics.append("home")
        topics.extend(["settlement", "season", "work", "home", "chat"])
        for optional in ("personal", "memory", "secret"):
            if optional in available:
                topics.append(optional)
        choices = [topic for topic in topics if topic in available]
        if not choices:
            return "chat"
        seed = stable_text_seed(
            f"{resident_id}:{context.get('day_key')}:{resident.get('dialogue_count', 0)}"
        )
        return choices[seed % len(choices)]

    def talk_to_procedural_town_resident(
        self,
        resident: Dict[str, object],
    ) -> Optional[Dict[str, object]]:
        plan = self.current_procedural_town_plan()
        if not plan:
            return None
        topic = self.procedural_town_primary_dialogue_topic(resident, plan)
        result = self.procedural_settlement_conversation(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
            str(resident.get("id", "")),
            topic=topic,
            remember=True,
        )
        if not result:
            return None
        resident_id = str(resident.get("id", ""))
        self.state.town_npc_dialogue_counts[resident_id] = int(
            resident.get("dialogue_count", 0)
        )
        self.state.town_npc_last_talk_day[resident_id] = str(
            resident.get("last_talk_day", self.town_npc_day_key())
        )
        social_line = self.procedural_town_social_dialogue_line(
            resident,
            plan,
            category=str(result.get("category", "")),
        )
        primary_text = (
            social_line
            if social_line and str(result.get("category")) != "first_meeting"
            and stable_text_seed(
                f"{resident.get('id')}:{resident.get('dialogue_count')}:social"
            ) % 3 == 0
            else str(result.get("text", "Good to see you."))
        )
        lines = [f'"{primary_text}"']
        if result.get("follow_up") and str(result.get("category")) == "first_meeting":
            lines.extend(["", f'"{result.get("follow_up")}"'])
        self.vertical_panel_view(
            str(resident.get("name", "Resident")),
            lines,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )
        bonus = (
            f" Relationship +{result.get('relationship_gain')}."
            if int(result.get("relationship_gain", 0) or 0) > 0
            else ""
        )
        self.autosave_with_message(
            f"Talked to {resident.get('name', 'the resident')}.{bonus}"
        )
        if int(result.get("relationship_gain", 0) or 0) > 0:
            self.adjust_procedural_town_reputation(
                1,
                f"Got to know {resident.get('name', 'a resident')}",
                plan,
            )
        return result

    def procedural_town_social_dialogue_line(
        self,
        resident: Dict[str, object],
        plan: Optional[Dict[str, object]] = None,
        category: str = "",
    ) -> str:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return ""
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        connections = resident.get("social_connections", {})
        if not isinstance(connections, dict):
            return ""
        friend = self.procedural_town_resident_name(
            str(connections.get("friend", "")),
            population,
        )
        rival = self.procedural_town_resident_name(
            str(connections.get("rival", "")),
            population,
        )
        coworkers = [
            self.procedural_town_resident_name(value, population)
            for value in connections.get("coworkers", []) or []
        ]
        family = [
            self.procedural_town_resident_name(value, population)
            for value in connections.get("family", []) or []
        ]
        identity = self.procedural_town_identity(plan)
        choices = [
            f"{friend} and I disagree about small things, which is how I know I trust them with large ones."
            if friend != "someone" else "",
            f"{rival} has a different idea about what this town needs next. They may even be partly right."
            if rival != "someone" else "",
            f"I work beside {coworkers[0]}. You learn a person's real habits when a task runs late."
            if coworkers else "",
            f"At home, {family[0]} is usually the first to notice when I am carrying work through the door."
            if family else "",
            f"Our custom is simple: {identity.get('custom', 'neighbors help when they can')}.",
            f"People here say, '{identity.get('motto', 'Keep the road open.')}'",
        ]
        choices = [choice for choice in choices if choice]
        if not choices:
            return ""
        return choices[
            stable_text_seed(
                f"{resident.get('id')}:{category}:{resident.get('dialogue_count')}"
            ) % len(choices)
        ]

    def procedural_town_resident_gift_value(
        self,
        resident: Dict[str, object],
        item_name: str,
    ) -> Tuple[int, str]:
        item = str(item_name)
        likes = {str(value) for value in resident.get("likes", []) or []}
        dislikes = {str(value) for value in resident.get("dislikes", []) or []}
        if item in dislikes:
            return -2, "disliked"
        if item in likes:
            return 8, "liked"
        return 1, "accepted"

    def give_procedural_town_resident_gift(
        self,
        resident: Dict[str, object],
        item_name: str,
    ) -> bool:
        item = str(item_name)
        day_key = (
            f"{int(getattr(self.state, 'year', 1))}-"
            f"{int(getattr(self.state, 'month', 1))}-"
            f"{int(getattr(self.state, 'day', 1))}"
        )
        if str(resident.get("last_gift_day", "")) == day_key:
            self.set_message(f"You already gave {resident.get('name', 'them')} a gift today.")
            return False
        inventory = getattr(self.state, "inventory", {})
        if not isinstance(inventory, dict) or int(inventory.get(item, 0) or 0) <= 0:
            self.set_message(f"You are not carrying {item}.")
            return False
        if hasattr(self, "is_giftable_inventory_item") and not self.is_giftable_inventory_item(item):
            self.set_message(f"You cannot give {item}.")
            return False
        amount, reaction = self.procedural_town_resident_gift_value(resident, item)
        birthday = self.is_npc_birthday(resident)
        amount, fatigue_note = self.apply_gift_fatigue(
            str(resident.get("id", "")),
            item,
            amount,
            birthday=birthday,
        )
        if birthday:
            amount += self.birthday_gift_bonus(amount)
        inventory[item] = int(inventory.get(item, 0)) - 1
        if inventory[item] <= 0:
            inventory.pop(item, None)
        resident["relationship"] = max(
            -50,
            min(250, int(resident.get("relationship", 0) or 0) + amount),
        )
        resident["last_gift_day"] = day_key
        resident_id = str(resident.get("id", ""))
        self.state.town_npc_last_gift_day[resident_id] = day_key
        self.state.town_npc_relationships[resident_id] = int(
            resident.get("relationship", 0)
        )
        recent = list(resident.get("recent_gifts", []) or [])
        recent.append(item)
        resident["recent_gifts"] = recent[-8:]
        self.remember_recent_gift_for_npc(
            str(resident.get("id", "")),
            item,
        )
        memory = (
            f"{getattr(self.state, 'date_label', day_key)} - "
            f"{getattr(self.state, 'player_name', 'The farmer')} gave them {item}."
        )
        memories = list(resident.get("memories", []) or [])
        memories.append(memory)
        resident["memories"] = memories[-16:]
        response = {
            "liked": "They brighten and thank you warmly.",
            "disliked": "They accept it carefully, without pretending to enjoy it.",
            "accepted": "They thank you for thinking of them.",
        }[reaction]
        if birthday:
            response += " They are especially touched that you remembered their birthday."
        elif fatigue_note:
            response += f" It is becoming a {fatigue_note}."
        self.autosave_with_message(
            f"Gave {item} to {resident.get('name', 'the resident')}. "
            f"{response} Relationship {amount:+}."
        )
        if amount > 0:
            self.adjust_procedural_town_reputation(
                2 if amount >= 8 else 1,
                f"Gave {resident.get('name', 'a resident')} a gift",
            )
        if amount >= 8:
            self.spread_procedural_town_social_reputation(
                resident,
                "delight over a thoughtful gift",
            )
        return True

    def complete_procedural_settlement_request(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
    ) -> bool:
        completed = super().complete_procedural_settlement_request(
            chunk_x,
            chunk_y,
            resident_id,
        )
        if not completed:
            return False
        plan = self.procedural_town_plan(chunk_x, chunk_y)
        if plan:
            community = self.ensure_procedural_town_community(plan)
            community["development_points"] = int(
                community.get("development_points", 0)
            ) + 3
            self.adjust_procedural_town_reputation(
                6,
                "Completed a resident request",
                plan,
            )
            population = self.procedural_settlement_population(chunk_x, chunk_y) or {}
            resident = population.get("residents", {}).get(str(resident_id))
            if isinstance(resident, dict):
                self.spread_procedural_town_social_reputation(
                    resident,
                    "gratitude for completed work",
                    plan,
                )
        return True

    def procedural_town_resident_gift_menu(
        self,
        resident: Dict[str, object],
    ) -> bool:
        choices = [
            MenuItem(
                label=str(item),
                value=str(item),
                enabled=True,
                hint=(
                    f"x{qty}; relationship "
                    f"{self.procedural_town_resident_gift_value(resident, str(item))[0]:+}"
                ),
            )
            for item, qty in sorted(getattr(self.state, "inventory", {}).items())
            if int(qty or 0) > 0
            and (
                not hasattr(self, "is_giftable_inventory_item")
                or self.is_giftable_inventory_item(str(item))
            )
        ]
        choices.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(
            f"Gift to {resident.get('name', 'Resident')}",
            choices,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if not choice or choice.value == MENU_BACK:
            return False
        return self.give_procedural_town_resident_gift(
            resident,
            str(choice.value),
        )

    def talk_to_procedural_household_spouse(
        self,
        resident: Dict[str, object],
    ) -> None:
        resident_id = str(resident.get("id", ""))
        today = self.town_npc_day_key()
        first_today = str(resident.get("last_talk_day", "")) != today
        resident["dialogue_count"] = int(resident.get("dialogue_count", 0)) + 1
        resident["last_talk_day"] = today
        self.state.town_npc_dialogue_counts[resident_id] = int(
            resident["dialogue_count"]
        )
        self.state.town_npc_last_talk_day[resident_id] = today
        gain = self.adjust_town_npc_relationship(
            resident_id,
            2 if first_today else 0,
        )
        lines = [
            f"{resident.get('name', 'Your spouse')} looks up from "
            f"{self.spouse_household_activity_label(resident)}.",
            "",
            (
                f"“I still think about {resident.get('goal', 'the life we chose to build')}. "
                "It feels different now that it belongs to both of us.”"
            ),
            "",
            f"Personality: {resident.get('personality', 'Practical')}",
            f"Relationship: {self.town_npc_relationship(resident_id)}"
            f"{f' ({gain:+})' if gain else ''}",
        ]
        self.vertical_panel_view(
            str(resident.get("name", "Your Spouse")),
            lines,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )
        self.autosave_with_message(
            f"Talked with {resident.get('name', 'your spouse')} at home."
        )

    def procedural_household_spouse_menu(
        self,
        resident: Dict[str, object],
    ) -> None:
        while True:
            resident_id = str(resident.get("id", ""))
            gifted_today = str(resident.get("last_gift_day", "")) == (
                self.town_npc_day_key()
            )
            court_ok, court_reason = self.can_court_town_npc(resident)
            scene_key, scene_title = self.available_marriage_scene(resident)
            family_reason = self.can_start_pregnancy_with_spouse(resident)[1]
            items = [
                MenuItem(label="Talk", value="talk", enabled=True),
                MenuItem(
                    label="Give gift",
                    value="gift",
                    enabled=not gifted_today,
                    hint=(
                        "Already gave a gift today"
                        if gifted_today
                        else "Choose a carried item"
                    ),
                ),
                MenuItem(
                    label="Spend time together",
                    value="courtship",
                    enabled=True,
                    hint="Available" if court_ok else court_reason,
                ),
                MenuItem(
                    label="Marriage event",
                    value="marriage_scene",
                    enabled=bool(scene_key),
                    hint=scene_title if scene_title else "none ready",
                ),
                MenuItem(
                    label="Family memories",
                    value="family_memories",
                    enabled=True,
                    hint=f"{len(self.state.family_event_log or [])} logged",
                ),
                MenuItem(
                    label="Plan family",
                    value="plan_family",
                    enabled=True,
                    hint=family_reason,
                ),
            ]
            if self.state.pregnancy_active:
                items.append(
                    MenuItem(
                        label="Pregnancy check-in",
                        value="pregnancy_checkup",
                        enabled=True,
                        hint=(
                            "ready"
                            if self.pregnancy_checkup_available()
                            else "view"
                        ),
                    )
                )
            items.extend(
                [
                    MenuItem(
                        label="Family status",
                        value="family_status",
                        enabled=True,
                    ),
                    MenuItem(
                        label="Family meal",
                        value="family_meal",
                        enabled=True,
                        hint=self.family_meal_available()[1],
                    ),
                    MenuItem(
                        label="Spouse support",
                        value="spouse_support",
                        enabled=self.state.spouse_moved_to_farm,
                        hint=self.spouse_support_mode(),
                    ),
                    MenuItem(
                        label="Household help",
                        value="household_help",
                        enabled=True,
                        hint=(
                            "enabled"
                            if self.state.family_help_enabled
                            else "disabled"
                        ),
                    ),
                    MenuItem(label="Profile", value="profile", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ]
            )
            choice = self.vertical_panel_select(
                str(resident.get("name", "Your Spouse")),
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "talk":
                self.talk_to_procedural_household_spouse(resident)
                return
            if choice.value == "gift":
                if self.procedural_town_resident_gift_menu(resident):
                    return
                continue
            if choice.value == "courtship":
                if self.court_town_npc(resident):
                    return
                continue
            if choice.value == "marriage_scene":
                if self.play_marriage_scene(resident):
                    return
                continue
            if choice.value == "family_memories":
                self.vertical_panel_view(
                    "Family Memories",
                    self.family_event_log_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "plan_family":
                if self.family_planning_menu(resident) == "changed":
                    return
                continue
            if choice.value == "pregnancy_checkup":
                if self.complete_pregnancy_checkup(resident):
                    return
                continue
            if choice.value == "family_status":
                self.vertical_panel_view(
                    "Family",
                    self.family_status_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "family_meal":
                if self.family_meal_menu() == "changed":
                    return
                continue
            if choice.value == "spouse_support":
                if self.spouse_support_menu() == "changed":
                    return
                continue
            if choice.value == "household_help":
                self.toggle_family_help()
                return
            if choice.value == "profile":
                self.vertical_panel_view(
                    str(resident.get("name", "Your Spouse")),
                    self.procedural_town_resident_profile_lines(resident),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue

    def procedural_town_resident_menu(
        self,
        resident: Dict[str, object],
    ) -> None:
        plan = self.current_procedural_town_plan()
        if not plan:
            return
        cx, cy = int(plan["chunk_x"]), int(plan["chunk_y"])
        resident_id = str(resident.get("id", ""))
        while True:
            request_status = self.procedural_settlement_request_status(
                cx,
                cy,
                resident_id,
            )
            items = self.procedural_town_resident_menu_items(resident)
            choice = self.vertical_panel_select(
                str(resident.get("name", "Resident")),
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                self.set_message(
                    f"Stopped talking to {resident.get('name', 'the resident')}."
                )
                return
            if choice.value == "talk":
                self.talk_to_procedural_town_resident(resident)
                return
            if choice.value == "gift":
                if self.procedural_town_resident_gift_menu(resident):
                    return
                continue
            if choice.value == "rumor":
                result = self.procedural_settlement_conversation(
                    cx,
                    cy,
                    resident_id,
                    topic="rumor",
                    remember=False,
                )
                rumor_text = (
                    self.procedural_town_social_dialogue_line(
                        resident,
                        plan,
                        category="rumor",
                    )
                    if int(resident.get("relationship", 0)) >= 60
                    else ""
                ) or (str(result.get("text")) if result else "No rumor today.")
                self.vertical_panel_view(
                    f"{resident.get('name')} Rumor",
                    [f'"{rumor_text}"'],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "request":
                if request_status == "Ready":
                    if self.complete_procedural_settlement_request(
                        cx,
                        cy,
                        resident_id,
                    ):
                        return
                else:
                    self.ensure_procedural_resident_request(cx, cy, resident_id)
                    self.vertical_panel_view(
                        f"{resident.get('name')} Request",
                        self.procedural_settlement_conversation_lines(
                            cx,
                            cy,
                            resident_id,
                            topic="request",
                            remember=False,
                        ),
                        LEFT_PANEL_WIDTH,
                        LEFT_PANEL_HEIGHT,
                    )
                continue
            if choice.value == "courtship":
                if self.court_town_npc(resident):
                    return
                continue
            if choice.value == "proposal":
                if self.propose_to_town_npc(resident):
                    return
                continue
            if choice.value == "wedding_plans":
                self.vertical_panel_view(
                    "Wedding Plans",
                    self.marriage_status_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "move_spouse":
                if self.invite_spouse_to_farm(resident):
                    return
                continue
            if choice.value == "marriage_scene":
                if self.play_marriage_scene(resident):
                    return
                continue
            if choice.value == "family_memories":
                self.vertical_panel_view(
                    "Family Memories",
                    self.family_event_log_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "plan_family":
                if self.family_planning_menu(resident) == "changed":
                    return
                continue
            if choice.value == "pregnancy_checkup":
                if self.complete_pregnancy_checkup(resident):
                    return
                continue
            if choice.value == "family_status":
                self.vertical_panel_view(
                    "Family",
                    self.family_status_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "family_meal":
                if self.family_meal_menu() == "changed":
                    return
                continue
            if choice.value == "spouse_support":
                if self.spouse_support_menu() == "changed":
                    return
                continue
            if choice.value == "household_help":
                self.vertical_panel_view(
                    "Household Help",
                    self.family_help_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                toggle = self.vertical_panel_select(
                    "Household Help",
                    [
                        MenuItem(
                            label="Toggle household help",
                            value="toggle",
                            enabled=True,
                        ),
                        MenuItem(
                            label="Back",
                            value=MENU_BACK,
                            enabled=True,
                        ),
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if toggle and toggle.value == "toggle":
                    self.toggle_family_help()
                    return
                continue
            if choice.value == "profile":
                self.vertical_panel_view(
                    str(resident.get("name", "Resident")),
                    self.procedural_town_resident_profile_lines(resident),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "status":
                self.vertical_panel_view(
                    str(resident.get("name", "Resident")),
                    self.procedural_town_resident_status_lines(resident),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue

    def procedural_town_resident_menu_items(
        self,
        resident: Dict[str, object],
    ) -> List[MenuItem]:
        plan = self.current_procedural_town_plan()
        if not plan:
            return []
        cx, cy = int(plan["chunk_x"]), int(plan["chunk_y"])
        resident_id = str(resident.get("id", ""))
        available_topics = set(
            self.procedural_settlement_dialogue_topics(cx, cy, resident_id)
        )
        gifted_today = str(resident.get("last_gift_day", "")) == (
            f"{int(getattr(self.state, 'year', 1))}-"
            f"{int(getattr(self.state, 'month', 1))}-"
            f"{int(getattr(self.state, 'day', 1))}"
        )
        request_status = self.procedural_settlement_request_status(
            cx,
            cy,
            resident_id,
        )
        items = [
            MenuItem(label="Talk", value="talk", enabled=True),
            MenuItem(
                label="Give gift",
                value="gift",
                enabled=not gifted_today,
                hint="Already gave a gift today" if gifted_today else "Choose a carried item",
            ),
            MenuItem(
                label="Ask rumor",
                value="rumor",
                enabled="rumor" in available_topics,
                hint="Build friendship first" if "rumor" not in available_topics else "",
            ),
            MenuItem(
                label="Request",
                value="request",
                enabled="request" in available_topics,
                hint=request_status,
            ),
        ]
        if self.is_marriageable_npc(resident):
            court_ok, court_reason = self.can_court_town_npc(resident)
            proposal_ok, proposal_reason = self.can_propose_to_town_npc(resident)
            items.append(
                MenuItem(
                    label="Courtship",
                    value="courtship",
                    enabled=True,
                    hint="Available" if court_ok else court_reason,
                )
            )
            if str(getattr(self.state, "engaged_npc_id", "")) == resident_id:
                items.append(
                    MenuItem(
                        label="Wedding plans",
                        value="wedding_plans",
                        enabled=True,
                        hint=self.wedding_date_label(),
                    )
                )
            else:
                items.append(
                    MenuItem(
                        label="Propose",
                        value="proposal",
                        enabled=True,
                        hint="Ready" if proposal_ok else proposal_reason,
                    )
                )
        if str(getattr(self.state, "spouse_npc_id", "")) == resident_id:
            move_ok, move_reason = self.can_invite_spouse_to_farm(resident)
            _family_ok, family_reason = self.can_start_pregnancy_with_spouse(
                resident
            )
            scene_key, scene_title = self.available_marriage_scene(resident)
            items.extend(
                [
                    MenuItem(
                        label="Move to farm",
                        value="move_spouse",
                        enabled=move_ok,
                        hint=move_reason,
                    ),
                    MenuItem(
                        label="Marriage event",
                        value="marriage_scene",
                        enabled=bool(scene_key),
                        hint=scene_title if scene_title else "none ready",
                    ),
                    MenuItem(
                        label="Family memories",
                        value="family_memories",
                        enabled=True,
                        hint=f"{len(self.state.family_event_log or [])} logged",
                    ),
                    MenuItem(
                        label="Plan family",
                        value="plan_family",
                        enabled=True,
                        hint=family_reason,
                    ),
                ]
            )
            if self.state.pregnancy_active:
                items.append(
                    MenuItem(
                        label="Pregnancy check-in",
                        value="pregnancy_checkup",
                        enabled=True,
                        hint=(
                            "ready"
                            if self.pregnancy_checkup_available()
                            else "view"
                        ),
                    )
                )
            items.extend(
                [
                    MenuItem(
                        label="Family status",
                        value="family_status",
                        enabled=True,
                        hint=f"{len(self.state.children)} child(ren)",
                    ),
                    MenuItem(
                        label="Family meal",
                        value="family_meal",
                        enabled=True,
                        hint=self.family_meal_available()[1],
                    ),
                    MenuItem(
                        label="Spouse support",
                        value="spouse_support",
                        enabled=self.state.spouse_moved_to_farm,
                        hint=self.spouse_support_mode(),
                    ),
                    MenuItem(
                        label="Household help",
                        value="household_help",
                        enabled=True,
                        hint=(
                            "enabled"
                            if self.state.family_help_enabled
                            else "disabled"
                        ),
                    ),
                ]
            )
        items.extend(
            [
                MenuItem(label="Profile", value="profile", enabled=True),
                MenuItem(label="Status", value="status", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
        )
        return items

    def procedural_town_sign_lines(
        self,
        plan: Dict[str, object],
    ) -> List[str]:
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        summary = self.procedural_npc_builder().summary(population)
        specialty = str(plan.get("specialty", "")).replace("_", " ").title()
        identity = self.procedural_town_identity(plan)
        event = self.procedural_town_active_event(plan)
        market = self.procedural_town_market_profile(plan)
        return [
            str(plan.get("name", "Wilderness Settlement")).upper(),
            "",
            f"Established wilderness town",
            f"Population: {summary.get('population', 0)}",
            f"Households: {summary.get('households', 0)}",
            f"Style: {plan.get('style', 'Crossroads')}",
            f"Specialty: {specialty or 'General settlement'}",
            f"Known for: {identity.get('industry', 'regional trade')}",
            f"Motto: {identity.get('motto', '')}",
            f"Standing: {self.procedural_town_reputation_label(self.procedural_town_reputation(plan))}",
            f"Development: {self.procedural_town_development_tier(plan)}",
            f"Market: {market.get('surplus')} plentiful; seeking {market.get('demand')}",
            f"Today's event: {event.get('name', 'none') if event else 'none'}",
            "",
            "Travelers are welcome. Homes remain private unless invited.",
            "Completed public buildings can be entered through their marked doors.",
        ]

    def procedural_town_building_service(
        self,
        building: Dict[str, object],
    ) -> bool:
        type_id = str(building.get("type_id", ""))
        if type_id in PROCEDURAL_LOCAL_STOCK:
            self.procedural_town_local_shop_menu(building)
            return True
        if type_id == "town_hall":
            self.procedural_town_hall_menu()
            return True
        if type_id == "well":
            return self.use_procedural_town_well(building)
        if type_id == "park":
            return self.use_procedural_town_green(building)
        if type_id == "home":
            if hasattr(self, "procedural_town_residence_menu"):
                self.procedural_town_residence_menu(building)
            else:
                self.vertical_panel_view(
                    str(building.get("name", "Settlement Home")),
                    self.procedural_town_home_lines(building),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            return True
        self.vertical_panel_view(
            str(building.get("name", "Settlement Building")),
            self.procedural_town_building_lines(building),
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )
        return True

    def procedural_town_local_stock(
        self,
        building: Dict[str, object],
    ) -> List[Dict[str, object]]:
        type_id = str(building.get("type_id", ""))
        identity = self.procedural_town_identity()
        reputation = self.procedural_town_reputation()
        plan = self.current_procedural_town_plan()
        rank = self.procedural_town_development_rank(plan)
        profile = self.procedural_town_market_profile(plan)
        discount = (
            15 if reputation >= 120
            else 10 if reputation >= 75
            else 5 if reputation >= 40
            else 0
        ) + rank * 2
        candidates = list(PROCEDURAL_LOCAL_STOCK.get(type_id, ()))
        special_notes: Dict[str, str] = {}
        if type_id in {"general_store", "market_stall"}:
            price_lookup = getattr(self, "shippable_unit_price", None)
            for item in list(identity.get("exports", ()) or []):
                base_price = int(price_lookup(item)) * 2 if callable(price_lookup) else 0
                candidates.append((str(item), max(30, base_price)))
            tier_names = ("Growing Town", "Established Town", "Regional Center")
            for tier_name in tier_names[:rank]:
                candidates.extend(PROCEDURAL_DEVELOPMENT_STOCK.get(tier_name, ()))
            partner = self.procedural_town_trade_partner(plan)
            if partner and rank >= 1:
                partner_plan = self.procedural_town_plan(
                    int(partner["chunk_x"]),
                    int(partner["chunk_y"]),
                )
                partner_identity = (
                    self.procedural_town_identity(partner_plan)
                    if partner_plan
                    else {}
                )
                partner_exports = list(partner_identity.get("exports", ()) or [])
                if partner_exports:
                    partner_item = str(partner_exports[
                        stable_text_seed(
                            f"{partner.get('name')}:{self.procedural_town_day_key()}:caravan"
                        ) % len(partner_exports)
                    ])
                    partner_price = (
                        int(price_lookup(partner_item)) * 2
                        if callable(price_lookup)
                        else 0
                    )
                    candidates.append((partner_item, max(45, partner_price * 6 // 5)))
                    special_notes[partner_item] = (
                        f"Caravan stock from {partner.get('name')}"
                    )
        merged: Dict[str, int] = {}
        for item, base_price in candidates:
            merged[str(item)] = min(
                int(base_price),
                merged.get(str(item), int(base_price)),
            )
        entries: List[Dict[str, object]] = []
        for item, base_price in merged.items():
            market_modifier = (
                -15 if item == str(profile.get("surplus"))
                else 20 if item == str(profile.get("demand"))
                else 0
            )
            price = max(
                1,
                int(base_price * (100 - discount + market_modifier) / 100),
            )
            limit = (
                8 if type_id in {"general_store", "market_stall"} else 5
            ) + rank * 3
            if item == str(profile.get("surplus")):
                limit += 4
            remaining = self.procedural_town_stock_remaining(
                building,
                item,
                limit,
                plan,
            )
            entries.append({
                "item": item,
                "price": price,
                "limit": limit,
                "remaining": remaining,
                "note": (
                    special_notes[item]
                    if item in special_notes
                    else "Local surplus"
                    if item == str(profile.get("surplus"))
                    else "Locally scarce today"
                    if item == str(profile.get("demand"))
                    else f"Local {identity.get('industry', 'trade')} stock"
                ),
            })
        return sorted(entries, key=lambda entry: (int(entry["remaining"]) <= 0, str(entry["item"])))

    def procedural_town_stock_remaining(
        self,
        building: Dict[str, object],
        item_name: str,
        limit: int,
        plan: Optional[Dict[str, object]] = None,
    ) -> int:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return 0
        community = self.ensure_procedural_town_market_day(plan)
        key = f"{building.get('id')}:{item_name}"
        purchased = int(community.get("market_purchases", {}).get(key, 0))
        return max(0, int(limit) - purchased)

    def purchase_procedural_town_stock(
        self,
        building: Dict[str, object],
        item_name: str,
        quantity: int = 1,
    ) -> bool:
        entry = next(
            (
                value for value in self.procedural_town_local_stock(building)
                if str(value.get("item")) == str(item_name)
            ),
            None,
        )
        if not entry:
            return False
        quantity = max(1, int(quantity))
        total = int(entry["price"]) * quantity
        if int(entry.get("remaining", 0)) < quantity:
            self.set_message(
                f"{building.get('name', 'The shop')} only has "
                f"{entry.get('remaining', 0)} {item_name} left today."
            )
            return False
        if int(getattr(self.state, "money", 0)) < total:
            self.set_message(f"You need {total}g for {quantity} {item_name}.")
            return False
        self.state.money -= total
        self.state.inventory[item_name] = int(self.state.inventory.get(item_name, 0)) + quantity
        plan = self.current_procedural_town_plan()
        if plan:
            community = self.ensure_procedural_town_market_day(plan)
            purchases = community.setdefault("market_purchases", {})
            key = f"{building.get('id')}:{item_name}"
            purchases[key] = int(purchases.get(key, 0)) + quantity
        self.adjust_procedural_town_reputation(
            1,
            f"Traded at {building.get('name', 'a local shop')}",
        )
        self.autosave_with_message(
            f"Bought {quantity} {item_name} from {building.get('name')} for {total}g."
        )
        return True

    def procedural_town_sell_demand_menu(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        offer = self.procedural_town_demand_offer(plan)
        if not plan or not offer:
            return False
        item = str(offer["item"])
        available = int(self.state.inventory.get(item, 0))
        max_quantity = min(available, int(offer["remaining"]))
        if max_quantity <= 0:
            self.set_message(f"You have no {item} that the town can still buy today.")
            return False
        quantity = self.vertical_quantity_select(
            "Fill Local Demand",
            item,
            int(offer["price"]),
            max_qty=max_quantity,
            start_qty=1,
            panel_width=LEFT_PANEL_WIDTH,
            panel_height=LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if quantity == MENU_BACK or quantity is None or int(quantity) <= 0:
            return False
        return self.sell_procedural_town_demand(
            item,
            int(quantity),
            plan,
        )

    def procedural_town_local_shop_menu(
        self,
        building: Dict[str, object],
    ) -> None:
        plan = self.current_procedural_town_plan() or {}
        identity = self.procedural_town_identity(plan)
        while True:
            stock = self.procedural_town_local_stock(building)
            type_id = str(building.get("type_id", ""))
            items = [
                MenuItem(
                    label=str(entry["item"]),
                    value=str(entry["item"]),
                    enabled=(
                        int(getattr(self.state, "money", 0)) >= int(entry["price"])
                        and int(entry.get("remaining", 0)) > 0
                    ),
                    hint=(
                        f"{entry['price']}g | {entry.get('remaining', 0)}/{entry.get('limit', 0)} left"
                        f" | {entry['note']}"
                    ),
                )
                for entry in stock
            ]
            service_labels = {
                "clinic": "Receive treatment",
                "inn": "Rent room and meal",
                "library": "Research recipes",
                "carpenter": "Review farm projects",
                "workshop": "Review tool services",
            }
            if type_id in service_labels:
                items.append(MenuItem(
                    label=service_labels[type_id],
                    value="local_service",
                    enabled=True,
                ))
            if type_id in {
                "general_store",
                "market_stall",
                "inn",
                "clinic",
                "carpenter",
                "workshop",
                "library",
            } and hasattr(self, "procedural_business_management_menu"):
                owned_business = self.player_business_for_building(plan, building)
                items.append(MenuItem(
                    label="Business ownership",
                    value="business",
                    enabled=True,
                    hint=(
                        f"Owned | {owned_business.get('strategy')}"
                        if owned_business
                        else "Purchase and manage this business"
                    ),
                ))
            offer = self.procedural_town_demand_offer(plan)
            if type_id in {"general_store", "market_stall"} and offer:
                item = str(offer["item"])
                sellable = min(
                    int(self.state.inventory.get(item, 0)),
                    int(offer["remaining"]),
                )
                items.append(MenuItem(
                    label=f"Sell requested {item}",
                    value="sell_demand",
                    enabled=sellable > 0,
                    hint=(
                        f"{offer['price']}g each | town needs {offer['remaining']}"
                        if sellable > 0
                        else f"Town needs {offer['remaining']}; carried 0"
                    ),
                ))
            items.extend([
                MenuItem(label="Local notice", value="notice", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(
                str(building.get("name", "Local Shop")),
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "notice":
                self.vertical_panel_view(
                    str(building.get("name", "Local Notice")),
                    [
                        str(plan.get("name", "TOWN")).upper(),
                        "",
                        f"Known for: {identity.get('industry', 'regional trade')}",
                        f"Local custom: {identity.get('custom', '')}",
                        f"Local food: {identity.get('food', '')}",
                        f"Reputation: {self.procedural_town_reputation_label()}",
                        f"Market: {self.procedural_town_market_profile(plan).get('headline', '')}",
                        f"Development: {self.procedural_town_development_tier(plan)}",
                        "",
                        "Prices improve with trust and town development.",
                        "Daily supply and demand refresh each morning.",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "local_service":
                self.use_procedural_town_special_service(building)
                return
            if choice.value == "sell_demand":
                self.procedural_town_sell_demand_menu(plan)
                return
            if choice.value == "business":
                self.procedural_business_management_menu(building)
                continue
            entry = next(value for value in stock if value["item"] == choice.value)
            max_qty = max(
                1,
                min(
                    20,
                    int(entry.get("remaining", 0)),
                    int(getattr(self.state, "money", 0)) // int(entry["price"]),
                ),
            )
            qty = self.vertical_quantity_select(
                "Buy Local Stock",
                str(entry["item"]),
                int(entry["price"]),
                max_qty=max_qty,
                start_qty=1,
                panel_width=LEFT_PANEL_WIDTH,
                panel_height=LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if qty == MENU_BACK or qty is None or int(qty) <= 0:
                continue
            self.purchase_procedural_town_stock(
                building,
                str(entry["item"]),
                int(qty),
            )
            return

    def use_procedural_town_special_service(
        self,
        building: Dict[str, object],
    ) -> bool:
        type_id = str(building.get("type_id", ""))
        rank = self.procedural_town_development_rank()
        if type_id == "clinic":
            policy_discount = (
                15
                if hasattr(self, "procedural_town_current_policy")
                and self.procedural_town_current_policy() == "Wilderness Safety"
                else 0
            )
            if (
                hasattr(self, "ensure_procedural_town_politics")
                and "ranger_post"
                in set(
                    self.ensure_procedural_town_politics(
                        self.current_procedural_town_plan()
                    ).get("completed_initiatives", [])
                    or []
                )
            ):
                policy_discount += 10
            current_plan = self.current_procedural_town_plan()
            if (
                current_plan
                and hasattr(self, "procedural_town_has_regional_agreement")
                and self.procedural_town_has_regional_agreement(
                    current_plan,
                    "Mutual Aid",
                )
            ):
                policy_discount += 8
            if (
                hasattr(self, "ensure_regional_council_state")
                and "ranger_network"
                in set(
                    self.ensure_regional_council_state().get(
                        "completed_projects",
                        [],
                    )
                    or []
                )
            ):
                policy_discount += 7
            price = max(
                60,
                120
                - self.procedural_town_reputation() // 4
                - rank * 8
                - policy_discount,
            )
            if self.state.money < price:
                self.set_message(f"Treatment costs {price}g.")
                return False
            self.state.money -= price
            self.restore_stamina(20 + rank * 5)
            self.state.combat_current_hp = int(self.state.combat_max_hp)
            self.adjust_procedural_town_reputation(2, "Trusted the local clinic")
            self.autosave_with_message(
                f"Received treatment at {building.get('name')} for {price}g."
            )
            return True
        if type_id == "inn":
            price = max(
                35,
                80 - self.procedural_town_reputation() // 5 - rank * 6,
            )
            if self.state.money < price:
                self.set_message(f"A room and meal cost {price}g.")
                return False
            self.state.money -= price
            self.restore_stamina(35 + rank * 5)
            self.advance_time(120)
            self.adjust_procedural_town_reputation(1, "Stayed at the local inn")
            self.autosave_with_message(
                f"Rested at {building.get('name')} for {price}g."
            )
            return True
        if type_id == "library":
            menu = getattr(self, "library_menu", None)
        elif type_id == "carpenter":
            menu = lambda: self.carpenter_menu(auto_opened=False)
        elif type_id == "workshop":
            menu = lambda: self.blacksmith_menu(auto_opened=False)
        else:
            return False
        if callable(menu):
            self.safe_menu(menu, f"{building.get('name', 'Service')} closed.")
            return True
        return False

    def procedural_town_service_kind(self, type_id: str) -> str:
        return {
            "general_store": "general_store",
            "carpenter": "carpenter",
            "clinic": "clinic",
            "library": "library",
            "inn": "inn",
            "market_stall": "market",
            "workshop": "workshop",
            "town_hall": "civic",
            "well": "well",
            "park": "green",
            "home": "home",
        }.get(str(type_id), "information")

    def procedural_town_home_lines(
        self,
        building: Dict[str, object],
    ) -> List[str]:
        plan = self.current_procedural_town_plan() or {}
        population = self.procedural_settlement_population(
            int(plan.get("chunk_x", 0)),
            int(plan.get("chunk_y", 0)),
        ) or {}
        residents = [
            str(resident.get("name"))
            for resident in population.get("residents", {}).values()
            if str(resident.get("home_building_id", "")) == str(building.get("id", ""))
        ]
        property_record = (
            self.player_property_for_building(plan, building)
            if hasattr(self, "player_property_for_building")
            else None
        )
        return [
            str(building.get("name", "Settlement Home")).upper(),
            "",
            f"Residents: {', '.join(residents) if residents else 'Unoccupied'}",
            (
                f"Your residence: {property_record.get('name')}"
                if property_record
                else "Your residence: not owned"
            ),
            (
                "Primary residence: yes"
                if property_record
                and getattr(self.state, "primary_residence_id", "")
                == property_record.get("id")
                else "Primary residence: no"
            ),
            (
                f"Residence upgrade: {property_record.get('upgrade_level', 0)}/3"
                if property_record
                else "Residence upgrade: unavailable"
            ),
            (
                "Player household: lives here"
                if property_record and property_record.get("household_moved")
                else "Player household: elsewhere"
            ),
            "",
            "This is a private household rather than a public service.",
            "Residents can still be met here when their daily schedule brings them home.",
        ]

    def procedural_town_hall_menu(self) -> None:
        plan = self.current_procedural_town_plan()
        if not plan:
            return
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        while True:
            commission = self.procedural_town_commission(plan)
            commission_carried = int(
                self.state.inventory.get(str(commission.get("item", "")), 0)
            )
            items = [
                MenuItem(label="Town report", value="report", enabled=True),
                MenuItem(
                    label="Politics and elections",
                    value="politics",
                    enabled=hasattr(self, "procedural_town_politics_menu"),
                    hint=(
                        self.procedural_election_phase(plan)
                        if hasattr(self, "procedural_election_phase")
                        else ""
                    ),
                ),
                MenuItem(
                    label="Regional council",
                    value="regional",
                    enabled=hasattr(self, "regional_council_menu"),
                    hint=(
                        "Regional governance and agreements"
                        if hasattr(self, "regional_council_menu")
                        else ""
                    ),
                ),
                MenuItem(
                    label="Regional contracts",
                    value="contracts",
                    enabled=hasattr(self, "show_regional_contract_menu"),
                    hint=(
                        f"{len(self.regional_contracts(('active',)))} active"
                        if hasattr(self, "regional_contracts")
                        else ""
                    ),
                ),
                MenuItem(
                    label="Property and commerce",
                    value="ownership",
                    enabled=hasattr(self, "ensure_civic_economy_state"),
                    hint=(
                        f"{len(getattr(self.state, 'player_properties', {}) or {})} properties, "
                        f"{len(getattr(self.state, 'player_businesses', {}) or {})} businesses"
                    ),
                ),
                MenuItem(
                    label="Trade bulletin",
                    value="trade",
                    enabled=True,
                    hint=str(self.procedural_town_market_profile(plan).get("headline", "")),
                ),
                MenuItem(
                    label="Civic work board",
                    value="commission",
                    enabled=not bool(commission.get("completed")),
                    hint=(
                        "Completed today"
                        if commission.get("completed")
                        else f"{commission.get('quantity')} {commission.get('item')} | carried {commission_carried}"
                    ),
                ),
                MenuItem(
                    label="Local concern",
                    value="story",
                    enabled=True,
                    hint=self.procedural_town_story_status(plan),
                ),
                MenuItem(
                    label="Community event",
                    value="event",
                    enabled=bool(self.procedural_town_active_event(plan)),
                    hint=(
                        str(self.procedural_town_active_event(plan).get("name"))
                        if self.procedural_town_active_event(plan)
                        else "No event today"
                    ),
                ),
                MenuItem(
                    label="Community support",
                    value="support",
                    enabled=self.procedural_town_reputation(plan) >= 75,
                    hint=(
                        "Weekly supplies for trusted neighbors"
                        if self.procedural_town_reputation(plan) >= 75
                        else "Requires Trusted Neighbor reputation"
                    ),
                ),
                MenuItem(
                    label="Development benefits",
                    value="benefits",
                    enabled=True,
                    hint=self.procedural_town_development_tier(plan),
                ),
                MenuItem(
                    label="Resident directory",
                    value="directory",
                    enabled=True,
                    hint=f"{len(population.get('residents', {}))} residents",
                ),
                MenuItem(label="Building directory", value="buildings", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                str(plan.get("name", "Town Hall")),
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "report":
                self.vertical_panel_view(
                    str(plan.get("name", "Town")),
                    self.procedural_town_report_lines(
                        int(plan["chunk_x"]),
                        int(plan["chunk_y"]),
                    ),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "politics":
                self.procedural_town_politics_menu()
            elif choice.value == "regional":
                self.regional_council_menu()
            elif choice.value == "contracts":
                self.show_regional_contract_menu()
            elif choice.value == "ownership":
                self.civic_portfolio_menu()
            elif choice.value == "trade":
                offer = self.procedural_town_demand_offer(plan)
                self.vertical_panel_view(
                    "Trade Bulletin",
                    [
                        "TODAY'S LOCAL MARKET",
                        "",
                        str(self.procedural_town_market_profile(plan).get("headline", "")),
                        f"Buying: {offer.get('item')} for {offer.get('price')}g each",
                        f"Remaining demand: {offer.get('remaining')}/{offer.get('limit')}",
                        "",
                        "General stores and market stalls buy the requested good.",
                        "Local stock is limited and refreshes each morning.",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "commission":
                if commission_carried >= int(commission.get("quantity", 0)):
                    self.complete_procedural_town_commission(plan)
                else:
                    self.vertical_panel_view(
                        "Civic Work Board",
                        [
                            "DAILY CIVIC WORK ORDER",
                            "",
                            f"Needed: {commission.get('quantity')} {commission.get('item')}",
                            f"Carried: {commission_carried}",
                            f"Reward: {commission.get('reward')}g",
                            "",
                            "Completion improves both reputation and town development.",
                        ],
                        LEFT_PANEL_WIDTH,
                        LEFT_PANEL_HEIGHT,
                    )
            elif choice.value == "story":
                if self.procedural_town_story_ready(plan):
                    self.complete_procedural_town_story_stage(plan)
                else:
                    self.vertical_panel_view(
                        "Local Concern",
                        self.procedural_town_story_lines(plan),
                        LEFT_PANEL_WIDTH,
                        LEFT_PANEL_HEIGHT,
                    )
            elif choice.value == "event":
                self.participate_procedural_town_event(plan)
            elif choice.value == "support":
                self.claim_procedural_town_support(plan)
            elif choice.value == "benefits":
                self.vertical_panel_view(
                    "Town Development",
                    [
                        self.procedural_town_development_tier(plan).upper(),
                        "",
                        *self.procedural_town_development_benefits(plan),
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "directory":
                rows = ["RESIDENT DIRECTORY", ""]
                for resident in sorted(
                    population.get("residents", {}).values(),
                    key=lambda value: str(value.get("name", "")),
                ):
                    rows.append(
                        f"- {resident.get('name')}: {resident.get('role')} "
                        f"({resident.get('runtime_activity', 'following today’s routine')})"
                    )
                self.vertical_panel_view(
                    "Resident Directory",
                    rows,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "buildings":
                rows = ["BUILDING DIRECTORY", ""]
                for building in sorted(
                    plan.get("buildings", {}).values(),
                    key=lambda value: str(value.get("name", "")),
                ):
                    rows.append(
                        f"- {building.get('name')}: "
                        f"{self.procedural_town_service_kind(str(building.get('type_id', ''))).replace('_', ' ')}"
                    )
                self.vertical_panel_view(
                    "Building Directory",
                    rows,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )

    def procedural_town_story_requirements(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Tuple[str, int]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return "", 0
        community = self.ensure_procedural_town_community(plan)
        identity = dict(community.get("identity", {}))
        stage = min(2, int(community.get("story_stage", 0)))
        quantities = list(identity.get("story_quantities", (8, 14, 20)))
        return str(identity.get("story_item", "Wood")), int(quantities[stage])

    def procedural_town_story_status(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> str:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return "Unavailable"
        community = self.ensure_procedural_town_community(plan)
        if community.get("story_completed"):
            return "Resolved"
        item, quantity = self.procedural_town_story_requirements(plan)
        carried = int(getattr(self.state, "inventory", {}).get(item, 0))
        return "Ready" if carried >= quantity else f"Needs {quantity} {item}"

    def procedural_town_story_ready(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        return self.procedural_town_story_status(plan) == "Ready"

    def procedural_town_story_lines(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> List[str]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return ["No town concern is available."]
        community = self.ensure_procedural_town_community(plan)
        identity = dict(community.get("identity", {}))
        stage = int(community.get("story_stage", 0))
        item, quantity = self.procedural_town_story_requirements(plan)
        stages = list(identity.get("story_stages", ()) or [])
        if community.get("story_completed"):
            return [
                "LOCAL CONCERN RESOLVED",
                "",
                str(identity.get("concern", "")),
                "",
                *[
                    f"- {project}"
                    for project in community.get("completed_projects", []) or []
                ],
                "",
                "Your help left visible, lasting changes throughout the town.",
            ]
        stage_record = (
            stages[min(stage, len(stages) - 1)]
            if stages
            else ("Emergency Supply", str(identity.get("concern", "")), "")
        )
        return [
            str(stage_record[0]).upper(),
            "",
            str(identity.get("concern", "")),
            "",
            str(stage_record[1]),
            "",
            f"Current stage: {stage + 1}/3",
            f"Needed: {quantity} {item}",
            f"Carried: {int(self.state.inventory.get(item, 0))}",
            f"Result: {stage_record[2]}",
            "",
            "Each stage improves town development and local reputation.",
        ]

    def complete_procedural_town_story_stage(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return False
        community = self.ensure_procedural_town_community(plan)
        if community.get("story_completed"):
            return False
        item, quantity = self.procedural_town_story_requirements(plan)
        if int(self.state.inventory.get(item, 0)) < quantity:
            return False
        self.state.inventory[item] -= quantity
        if self.state.inventory[item] <= 0:
            self.state.inventory.pop(item, None)
        stage = int(community.get("story_stage", 0)) + 1
        community["story_stage"] = stage
        community["development_points"] = int(
            community.get("development_points", 0)
        ) + 18 + stage * 4
        reward = 180 + stage * 120
        self.state.money += reward
        self.adjust_procedural_town_reputation(
            12 + stage * 3,
            f"Completed local concern stage {stage}",
            plan,
        )
        identity = self.procedural_town_identity(plan)
        stages = list(identity.get("story_stages", ()) or [])
        if stages:
            stage_record = stages[min(stage - 1, len(stages) - 1)]
            projects = list(community.get("completed_projects", []) or [])
            projects.append(str(stage_record[2]))
            community["completed_projects"] = list(dict.fromkeys(projects))[-8:]
        if stage >= 3:
            community["story_completed"] = True
        self.autosave_with_message(
            f"Helped resolve stage {stage} of {plan.get('name')}'s local concern. "
            f"Earned {reward}g."
        )
        return True

    def procedural_town_active_event(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        plan = plan or self.current_procedural_town_plan()
        if not plan:
            return {}
        weather = str(getattr(self.state, "weather", "Sunny"))
        if weather in {"Storm", "Stormy", "Blizzard"}:
            return {
                "id": "weather_watch",
                "name": "Weather Watch",
                "phase": "evening",
                "building_type": "town_hall",
                "activity": "checking supplies and neighbors before severe weather",
                "reward": 5,
            }
        weekday = str(getattr(self.state, "weekday", ""))
        identity = self.procedural_town_identity(plan)
        if weekday == "Saturday" and int(getattr(self.state, "day", 1)) <= 7:
            return {
                "id": "identity_festival",
                "name": str(identity.get("festival_name", "Founders' Gathering")),
                "phase": "lunch",
                "building_type": (
                    "market_stall"
                    if any(
                        str(building.get("type_id")) == "market_stall"
                        for building in plan.get("buildings", {}).values()
                    )
                    else "town_hall"
                ),
                "activity": str(
                    identity.get(
                        "festival_activity",
                        "sharing food and remembering the town's founding",
                    )
                ),
                "reward": 7,
                "gift_item": str(identity.get("festival_gift", "Field Snack")),
            }
        events = {
            "Wednesday": {
                "id": "local_market",
                "name": "Local Market Day",
                "phase": "lunch",
                "building_type": "market_stall",
                "activity": "trading, shopping, and exchanging road news",
                "reward": 3,
            },
            "Friday": {
                "id": "community_table",
                "name": "Community Table",
                "phase": "evening",
                "building_type": "inn",
                "activity": "sharing food and catching up with neighbors",
                "reward": 4,
            },
            "Sunday": {
                "id": "open_council",
                "name": "Open Council",
                "phase": "lunch",
                "building_type": "town_hall",
                "activity": "attending the weekly open council",
                "reward": 4,
            },
        }
        return dict(events.get(weekday, {}))

    def participate_procedural_town_event(
        self,
        plan: Optional[Dict[str, object]] = None,
    ) -> bool:
        plan = plan or self.current_procedural_town_plan()
        event = self.procedural_town_active_event(plan)
        if not plan or not event:
            return False
        community = self.ensure_procedural_town_community(plan)
        day_key = (
            f"{int(self.state.year)}-{int(self.state.month)}-{int(self.state.day)}"
        )
        event_key = f"{day_key}:{event['id']}"
        if event_key in set(community.get("event_log", []) or []):
            self.set_message("You already joined this town event today.")
            return False
        community["event_log"] = (
            list(community.get("event_log", []) or []) + [event_key]
        )[-30:]
        self.adjust_procedural_town_reputation(
            int(event.get("reward", 3)),
            f"Joined {event.get('name')}",
            plan,
        )
        policy = (
            self.procedural_town_current_policy(plan)
            if hasattr(self, "procedural_town_current_policy")
            else ""
        )
        initiatives = (
            set(
                self.ensure_procedural_town_politics(plan).get(
                    "completed_initiatives",
                    [],
                )
                or []
            )
            if hasattr(self, "ensure_procedural_town_politics")
            else set()
        )
        community["development_points"] = int(
            community.get("development_points", 0)
        ) + 2 + (1 if policy == "Public Works" else 0)
        population = self.procedural_settlement_population(
            int(plan["chunk_x"]),
            int(plan["chunk_y"]),
        ) or {}
        residents = sorted(
            population.get("residents", {}).values(),
            key=lambda resident: stable_text_seed(
                f"{event_key}:{resident.get('id')}:attendee"
            ),
        )
        attendee_count = (
            5
            if "family_center" in initiatives
            else 4
            if policy == "Family Services"
            else 3
        )
        if (
            hasattr(self, "procedural_town_has_regional_agreement")
            and self.procedural_town_has_regional_agreement(
                plan,
                "Cultural Exchange",
            )
        ):
            attendee_count += 1
        if (
            hasattr(self, "ensure_regional_council_state")
            and "household_exchange"
            in set(
                self.ensure_regional_council_state().get(
                    "completed_projects",
                    [],
                )
                or []
            )
        ):
            attendee_count += 1
        for resident in residents[:attendee_count]:
            resident["relationship"] = min(
                250,
                int(resident.get("relationship", 0)) + 1,
            )
            memories = list(resident.get("memories", []) or [])
            memories.append(
                f"{getattr(self.state, 'date_label', day_key)} - "
                f"Shared {event.get('name')} with the farmer."
            )
            resident["memories"] = memories[-16:]
        gift_item = str(event.get("gift_item", "") or "")
        if gift_item:
            self.state.inventory[gift_item] = int(
                self.state.inventory.get(gift_item, 0)
            ) + 1
        self.restore_stamina(
            6
            + (4 if policy == "Family Services" else 0)
            + (2 if "family_center" in initiatives else 0)
        )
        self.advance_time(45)
        self.autosave_with_message(
            f"Joined {plan.get('name')}'s {event.get('name')}. "
            f"Reputation improved"
            f"{f' and received {gift_item}' if gift_item else ''}."
        )
        return True

    def use_procedural_town_well(
        self,
        building: Dict[str, object],
    ) -> bool:
        plan = self.current_procedural_town_plan()
        if not plan:
            return False
        day_key = (
            f"{int(getattr(self.state, 'year', 1))}-"
            f"{int(getattr(self.state, 'month', 1))}-"
            f"{int(getattr(self.state, 'day', 1))}"
        )
        service_state = plan.setdefault("service_state", {})
        key = f"well:{building.get('id')}:last_day"
        if str(service_state.get(key, "")) == day_key:
            self.set_message("You already stopped for fresh well water today.")
            return False
        before = int(getattr(self.state, "stamina", 0))
        safety_bonus = (
            3
            if hasattr(self, "procedural_town_current_policy")
            and self.procedural_town_current_policy(plan) == "Wilderness Safety"
            else 0
        )
        if (
            hasattr(self, "ensure_procedural_town_politics")
            and "ranger_post"
            in set(
                self.ensure_procedural_town_politics(plan).get(
                    "completed_initiatives",
                    [],
                )
                or []
            )
        ):
            safety_bonus += 2
        if (
            hasattr(self, "procedural_town_has_regional_agreement")
            and self.procedural_town_has_regional_agreement(plan, "Mutual Aid")
        ):
            safety_bonus += 2
        if (
            hasattr(self, "ensure_regional_council_state")
            and "ranger_network"
            in set(
                self.ensure_regional_council_state().get(
                    "completed_projects",
                    [],
                )
                or []
            )
        ):
            safety_bonus += 2
        self.restore_stamina(8 + safety_bonus)
        service_state[key] = day_key
        self.autosave_with_message(
            f"Drank fresh water at {building.get('name', 'the public well')}. "
            f"Stamina +{self.state.stamina - before}."
        )
        return True

    def use_procedural_town_green(
        self,
        building: Dict[str, object],
    ) -> bool:
        before = int(getattr(self.state, "stamina", 0))
        self.restore_stamina(5)
        if hasattr(self, "advance_time"):
            self.advance_time(20)
        self.autosave_with_message(
            f"Rested at {building.get('name', 'the village green')}. "
            f"Stamina +{self.state.stamina - before}."
        )
        return True

    def use_procedural_town_interior_action(
        self,
        x: int,
        y: int,
    ) -> None:
        resident = self.procedural_town_resident_at(x, y)
        if resident:
            if resident.get("household_town_resident"):
                self.town_npc_menu(resident)
            else:
                self.procedural_town_resident_menu(resident)
            return
        tile = self.procedural_town_interior_map()[y][x]
        if tile == "D":
            self.exit_procedural_town_building()
            return
        building = self.current_procedural_town_building()
        if tile == "&" and building:
            self.procedural_town_building_service(building)
            return
        if tile == "d" and building and str(building.get("type_id")) == "town_hall":
            current_plan = self.current_procedural_town_plan()
            if not current_plan:
                self.set_message("The civic display is currently unavailable.")
                return
            community = self.ensure_procedural_town_community(current_plan)
            projects = list(community.get("completed_projects", []) or [])
            self.set_message(
                projects[-1]
                if projects
                else "The civic display records current work, arrivals, and public decisions."
            )
            return
        if tile == "f" and building and str(building.get("type_id")) == "town_hall":
            self.set_message(
                "A permanent display commemorates the local concern the town overcame."
            )
            return
        if tile == "$":
            self.set_message("Shelves hold the town's limited daily stock and regional goods.")
            return
        if tile == "+":
            self.set_message("Remedies are labeled by use, season, and the person who prepared them.")
            return
        if tile == "l":
            self.set_message("Local records mix family histories with practical wilderness notes.")
            return
        if tile == "p":
            self.set_message("A carefully tended planter reflects the town's local style.")
            return
        if tile == ",":
            self.set_message("A woven rug softens the hard-used floor.")
            return
        if tile in {"b", "t", "c", "s", "l", "$", "w", "a", "x", "+", "P", "d", "f"}:
            self.set_message("A carefully maintained part of the settlement building.")
            return
        self.set_message("Nothing here needs your attention.")

    def procedural_town_report_lines(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> List[str]:
        plan = self.procedural_town_plan(chunk_x, chunk_y)
        if not plan:
            return ["No procedural town exists in this wilderness chunk."]
        population = self.procedural_settlement_population(chunk_x, chunk_y) or {}
        summary = self.procedural_npc_builder().summary(population)
        identity = self.procedural_town_identity(plan)
        community = self.ensure_procedural_town_community(plan)
        event = self.procedural_town_active_event(plan)
        market = self.procedural_town_market_profile(plan)
        commission = self.procedural_town_commission(plan)
        politics = (
            self.ensure_procedural_town_politics(plan)
            if hasattr(self, "ensure_procedural_town_politics")
            else {}
        )
        local_key = settlement_chunk_key(chunk_x, chunk_y)
        owned_businesses = [
            business
            for business in getattr(self.state, "player_businesses", {}).values()
            if business.get("town_key") == local_key
        ]
        owned_properties = [
            property_record
            for property_record in getattr(self.state, "player_properties", {}).values()
            if property_record.get("town_key") == local_key
        ]
        trade_routes = [
            route
            for route in getattr(self.state, "player_trade_routes", {}).values()
            if route.get("source_town_key") == local_key
        ]
        regional_council = (
            self.ensure_regional_council_state()
            if hasattr(self, "ensure_regional_council_state")
            else {}
        )
        return [
            "RARE PROCEDURAL WILDERNESS TOWN",
            "",
            f"Name: {plan.get('name')}",
            f"Chunk: {chunk_x},{chunk_y}",
            f"Style: {plan.get('style')}",
            f"Specialty: {str(plan.get('specialty', 'general')).replace('_', ' ').title()}",
            f"Discovered: {'yes' if plan.get('discovered') else 'no'}",
            f"Population: {summary.get('population', 0)}",
            f"Households: {summary.get('households', 0)}",
            f"Employed: {summary.get('employed', 0)}",
            f"Vacancies: {summary.get('vacancies', 0)}",
            f"Reputation: {self.procedural_town_reputation_label(self.procedural_town_reputation(plan))} ({self.procedural_town_reputation(plan)})",
            f"Development: {self.procedural_town_development_tier(plan)} ({community.get('development_points', 0)} points)",
            f"Industry: {identity.get('industry', '')}",
            f"Architecture: {identity.get('architecture', '')}",
            f"Custom: {identity.get('custom', '')}",
            f"Local food: {identity.get('food', '')}",
            f"Founded: {identity.get('founding', '')}",
            f"Current concern: {self.procedural_town_story_status(plan)}",
            f"Today's event: {event.get('name', 'none') if event else 'none'}",
            f"Market surplus: {market.get('surplus', 'none')}",
            f"Market demand: {market.get('demand', 'none')}",
            (
                f"Nearest known trade partner: {market.get('partner')}"
                if market.get("partner")
                else "Nearest known trade partner: none discovered"
            ),
            (
                f"Civic work order: completed"
                if commission.get("completed")
                else f"Civic work order: {commission.get('quantity')} {commission.get('item')}"
            ),
            f"Completed civic projects: {len(community.get('completed_projects', []) or [])}",
            (
                f"Mayor: {self.procedural_candidate_name(str(politics.get('incumbent_id', '')), plan)}"
                if politics and hasattr(self, "procedural_candidate_name")
                else "Mayor: unavailable"
            ),
            f"Current policy: {politics.get('current_policy', 'unavailable')}",
            f"Civic treasury: {politics.get('treasury', 0)}g",
            f"Civic initiatives: {len(politics.get('completed_initiatives', []) or [])}",
            (
                f"Election phase: {self.procedural_election_phase(plan)}"
                if politics and hasattr(self, "procedural_election_phase")
                else "Election phase: unavailable"
            ),
            f"Player residences here: {len(owned_properties)}",
            f"Player-owned businesses here: {len(owned_businesses)}",
            f"Player trade routes from town: {len(trade_routes)}",
            f"Regional council member: {'yes' if regional_council.get('member') else 'no'}",
            f"Regional agreements: {len(regional_council.get('agreement_log', []) or [])}",
            f"Regional projects: {len(regional_council.get('completed_projects', []) or [])}",
            "",
            "Development benefits:",
            *[
                f"- {benefit}"
                for benefit in self.procedural_town_development_benefits(plan)
            ],
            "",
            f"Rarity: one candidate per {PROCEDURAL_TOWN_GRID_SIZE}x{PROCEDURAL_TOWN_GRID_SIZE} chunk region",
            "The authored town is unchanged.",
        ]


__all__ = [
    "PROCEDURAL_TOWN_BUILDING_SYMBOLS",
    "PROCEDURAL_TOWN_GRID_SIZE",
    "PROCEDURAL_TOWN_DOOR_SYMBOL",
    "PROCEDURAL_TOWN_INTERIOR_LOCATION",
    "PROCEDURAL_TOWN_MIN_DISTANCE",
    "PROCEDURAL_TOWN_OPEN_BUILDINGS",
    "PROCEDURAL_TOWN_OVERWORLD_SYMBOL",
    "PROCEDURAL_TOWN_RUNTIME_VERSION",
    "ProceduralTownRuntimeMixin",
    "procedural_town_completed_plan",
]
