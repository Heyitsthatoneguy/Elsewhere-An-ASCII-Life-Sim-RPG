from __future__ import annotations

"""Physical regional caravans, route incidents, and delivery consequences."""

from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK
from ascii_farmstead_npc_builder import stable_text_seed
from ascii_farmstead_support import C, colorize
from ascii_farmstead_ui import MenuItem


TRADE_ROUTE_CREW_ROLES = {
    "route_guard": "Route Guard",
    "caravan_driver": "Caravan Driver",
    "regional_courier": "Regional Courier",
    "trade_representative": "Trade Representative",
}

TRADE_ROUTE_INCIDENTS = {
    "rockfall": {
        "name": "Rockfall",
        "description": "Fresh stone has blocked the wagon lane and pinned one wheel against the shoulder.",
        "supply": "Stone",
        "symbol": "#",
    },
    "washout": {
        "name": "Road Washout",
        "description": "Runoff has cut through the roadbed and left the loaded wagons without a safe crossing.",
        "supply": "Wood",
        "symbol": "~",
    },
    "broken_axle": {
        "name": "Broken Axle",
        "description": "A wagon axle has split. The crew has unloaded the cart while repairs are prepared.",
        "supply": "Wood",
        "symbol": "O",
    },
    "bandit_sign": {
        "name": "Unsafe Road",
        "description": "Scouts found signs of an ambush ahead. The caravan has formed a guarded roadside camp.",
        "supply": "Field Snack",
        "symbol": "!",
    },
    "flooded_ford": {
        "name": "Flooded Ford",
        "description": "The ford is running too high for loaded carts, forcing the crew to mark a safer approach.",
        "supply": "Fiber",
        "symbol": "~",
    },
}


class RegionalEconomyMixin:
    """Extends the existing civic trade routes without creating a second economy."""

    def ensure_player_trade_route_caravan(self, route: Dict[str, object]) -> Dict[str, object]:
        route = super().ensure_player_trade_route_caravan(route)
        route["route_reliability"] = max(35, min(100, int(route.get("route_reliability", 82) or 82)))
        route["route_development_points"] = max(0, int(route.get("route_development_points", 0) or 0))
        route["delivery_streak"] = max(0, int(route.get("delivery_streak", 0) or 0))
        route["missed_deliveries"] = max(0, int(route.get("missed_deliveries", 0) or 0))
        route["last_delivery_ordinal"] = max(0, int(route.get("last_delivery_ordinal", 0) or 0))
        route["incident_cycle_key"] = str(route.get("incident_cycle_key", ""))
        route["roadwork_day"] = str(route.get("roadwork_day", ""))
        route["waystation_use_day"] = str(route.get("waystation_use_day", ""))
        route["route_event_log"] = [
            str(value) for value in (
                route.get("route_event_log", []) if isinstance(route.get("route_event_log"), list) else []
            ) if str(value or "").strip()
        ][-24:]
        assignments = route.get("crew_assignments")
        if not isinstance(assignments, dict):
            assignments = {}
        route["crew_assignments"] = {
            role: str(assignments.get(role, "") or "")
            for role in TRADE_ROUTE_CREW_ROLES
            if str(assignments.get(role, "") or "")
        }
        counters = route.get("crew_work_counters")
        if not isinstance(counters, dict):
            counters = {}
        route["crew_work_counters"] = {
            role: max(0, int(counters.get(role, 0) or 0))
            for role in TRADE_ROUTE_CREW_ROLES
        }
        incident = route.get("caravan_incident")
        if not isinstance(incident, dict):
            incident = {}
        incident_type = str(incident.get("type", ""))
        if incident_type not in TRADE_ROUTE_INCIDENTS:
            incident = {}
        elif incident:
            incident = {
                "type": incident_type,
                "status": str(incident.get("status", "open")),
                "ordinal": max(0, int(incident.get("ordinal", 0) or 0)),
                "chunk_x": int(incident.get("chunk_x", 0) or 0),
                "chunk_y": int(incident.get("chunk_y", 0) or 0),
                "destination_town_key": str(incident.get("destination_town_key", "")),
                "progress": max(0, int(incident.get("progress", 0) or 0)),
                "resolved_by": str(incident.get("resolved_by", "")),
            }
        route["caravan_incident"] = incident
        return route

    def player_trade_route_development_level(self, route: Dict[str, object]) -> int:
        points = max(0, int(route.get("route_development_points", 0) or 0))
        return 3 if points >= 60 else 2 if points >= 30 else 1 if points >= 10 else 0

    def player_trade_route_development_name(self, route: Dict[str, object]) -> str:
        return ("Unmarked Track", "Signed Route", "Sheltered Road", "Patrolled Corridor")[
            self.player_trade_route_development_level(route)
        ]

    def player_trade_route_chunk_path(self, route: Dict[str, object]) -> List[Tuple[int, int]]:
        source = self.civic_plan_for_key(str(route.get("source_town_key", ""))) or {}
        destination = self.civic_plan_for_key(str(route.get("destination_town_key", ""))) or {}
        if not source or not destination:
            return []
        start = (int(source.get("chunk_x", 0)), int(source.get("chunk_y", 0)))
        end = (int(destination.get("chunk_x", 0)), int(destination.get("chunk_y", 0)))
        if hasattr(self, "regional_circulation_route_chunks"):
            first = list(self.regional_circulation_route_chunks(*start, f"{route.get('id')}:source"))
            second = list(self.regional_circulation_route_chunks(*end, f"{route.get('id')}:destination"))
            if first and second:
                path = first + list(reversed(second[:-1]))
                clean: List[Tuple[int, int]] = []
                for point in path:
                    point = (int(point[0]), int(point[1]))
                    if not clean or clean[-1] != point:
                        clean.append(point)
                return clean
        path = [start]
        x, y = start
        horizontal_first = stable_text_seed(str(route.get("id", ""))) % 2 == 0
        axes = ("x", "y") if horizontal_first else ("y", "x")
        for axis in axes:
            target = end[0] if axis == "x" else end[1]
            while (x if axis == "x" else y) != target:
                if axis == "x":
                    x += 1 if target > x else -1
                else:
                    y += 1 if target > y else -1
                path.append((x, y))
        return path

    def _scheduled_player_trade_route_caravan_state(
        self, route: Dict[str, object], ordinal: Optional[int] = None
    ) -> Dict[str, object]:
        state = dict(super().player_trade_route_caravan_state(route, ordinal))
        if state.get("phase") not in {"outbound", "returning"}:
            state.setdefault("travel_days", max(1, min(5, (int(route.get("distance", 1)) + 2) // 3)))
            state.setdefault("progress", 0)
            return state
        today = self.civic_date_ordinal() if ordinal is None else max(1, int(ordinal))
        travel_days = max(1, min(5, (int(route.get("distance", 1)) + 2) // 3))
        cycle_length = travel_days * 2 + 4
        seed_offset = stable_text_seed(f"{route.get('id', '')}:schedule") % cycle_length
        step = (today + seed_offset) % cycle_length
        state["travel_days"] = travel_days
        state["progress"] = step - 1 if state.get("phase") == "outbound" else step - travel_days - 3
        return state

    def player_trade_route_caravan_state(
        self, route: Dict[str, object], ordinal: Optional[int] = None
    ) -> Dict[str, object]:
        scheduled = self._scheduled_player_trade_route_caravan_state(route, ordinal)
        if scheduled.get("phase") == "paused":
            return scheduled
        incident = route.get("caravan_incident", {})
        if isinstance(incident, dict) and str(incident.get("status", "")) == "open":
            details = TRADE_ROUTE_INCIDENTS.get(str(incident.get("type", "")), {})
            return {
                "phase": "disrupted",
                "town_key": "",
                "status": f"delayed by {str(details.get('name', 'a road incident')).lower()}",
                "next_stop": str(scheduled.get("next_stop", "the next terminal")),
                "chunk_x": int(incident.get("chunk_x", 0)),
                "chunk_y": int(incident.get("chunk_y", 0)),
                "travel_days": int(scheduled.get("travel_days", 1)),
                "progress": int(scheduled.get("progress", 1)),
                "incident": dict(incident),
            }
        return scheduled

    def trade_route_has_crew_role(self, route: Dict[str, object], role: str) -> bool:
        return bool(str((route.get("crew_assignments", {}) or {}).get(str(role), "")))

    def maybe_start_player_trade_route_incident(
        self, route: Dict[str, object], ordinal: int, state: Dict[str, object]
    ) -> bool:
        if str(state.get("phase", "")) not in {"outbound", "returning"}:
            return False
        cycle_key = f"{ordinal}:{state.get('phase')}"
        if str(route.get("incident_cycle_key", "")) == cycle_key:
            return False
        route["incident_cycle_key"] = cycle_key
        if str((route.get("caravan_incident", {}) or {}).get("status", "")) == "open":
            return False
        threshold = 28
        threshold -= int(route.get("escort_level", 0) or 0) * 5
        threshold -= self.player_trade_route_development_level(route) * 3
        if self.trade_route_has_crew_role(route, "route_guard"):
            threshold -= 8
        if self.trade_route_has_crew_role(route, "caravan_driver"):
            threshold -= 4
        roll = stable_text_seed(f"{route.get('id')}:{ordinal}:incident") % 100
        if roll >= max(4, threshold):
            return False
        kinds = tuple(TRADE_ROUTE_INCIDENTS)
        incident_type = kinds[stable_text_seed(f"{route.get('id')}:{ordinal}:kind") % len(kinds)]
        path = self.player_trade_route_chunk_path(route)
        if len(path) < 3:
            return False
        index = 1 + stable_text_seed(f"{route.get('id')}:{ordinal}:place") % (len(path) - 2)
        destination_key = (
            str(route.get("destination_town_key", ""))
            if state.get("phase") == "outbound"
            else str(route.get("source_town_key", ""))
        )
        route["caravan_incident"] = {
            "type": incident_type,
            "status": "open",
            "ordinal": int(ordinal),
            "chunk_x": int(path[index][0]),
            "chunk_y": int(path[index][1]),
            "destination_town_key": destination_key,
            "progress": 0,
            "resolved_by": "",
        }
        route["delivery_streak"] = 0
        route["route_reliability"] = max(35, int(route.get("route_reliability", 82)) - 4)
        details = TRADE_ROUTE_INCIDENTS[incident_type]
        log = route.setdefault("route_event_log", [])
        log.append(f"Day {ordinal}: {details['name']} delayed the caravan at chunk {path[index]}.")
        route["route_event_log"] = log[-24:]
        return True

    def resolve_trade_route_incident_by_crew(self, route: Dict[str, object], reason: str) -> None:
        incident = route.get("caravan_incident", {})
        if not isinstance(incident, dict) or str(incident.get("status", "")) != "open":
            return
        incident["status"] = "resolved"
        incident["resolved_by"] = str(reason)
        route["route_reliability"] = min(100, int(route.get("route_reliability", 82)) + 1)
        route["route_development_points"] = int(route.get("route_development_points", 0)) + 1
        log = route.setdefault("route_event_log", [])
        log.append(f"Day {self.civic_date_ordinal()}: the crew cleared the disruption ({reason}).")
        route["route_event_log"] = log[-24:]

    def record_player_trade_route_delivery(
        self, route: Dict[str, object], ordinal: int, already_counted: bool = False
    ) -> None:
        if not already_counted:
            route["caravan_deliveries"] = int(route.get("caravan_deliveries", 0)) + 1
        route["last_delivery_ordinal"] = max(int(route.get("last_delivery_ordinal", 0)), int(ordinal))
        route["delivery_streak"] = int(route.get("delivery_streak", 0)) + 1
        route["route_reliability"] = min(100, int(route.get("route_reliability", 82)) + 1)
        capacity = int(route.get("capacity_level", 0))
        route["route_development_points"] = int(route.get("route_development_points", 0)) + 1 + capacity
        destination = self.civic_plan_for_key(str(route.get("destination_town_key", "")))
        if destination:
            community = self.ensure_procedural_town_community(destination)
            good = str(route.get("good", "General Goods"))
            quantity = 5 + capacity * 3
            imports = community.setdefault("recent_route_imports", {})
            imports[good] = {
                "ordinal": int(ordinal), "quantity": quantity,
                "route_name": str(route.get("caravan_name", "Trade Caravan")),
            }
            community["route_deliveries"] = int(community.get("route_deliveries", 0)) + 1
            if int(community["route_deliveries"]) % 3 == 0:
                community["development_points"] = int(community.get("development_points", 0)) + 1
            events = community.setdefault("event_log", [])
            events.append(
                f"{getattr(self.state, 'date_label', '')}: {route.get('caravan_name')} delivered {quantity} {good}."
            )
            community["event_log"] = events[-30:]
        log = route.setdefault("route_event_log", [])
        log.append(f"Day {ordinal}: delivered {route.get('good', 'goods')} to the destination market.")
        route["route_event_log"] = log[-24:]

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
                incident = route.get("caravan_incident", {})
                if isinstance(incident, dict) and str(incident.get("status", "")) == "open":
                    age = ordinal - int(incident.get("ordinal", ordinal))
                    auto_days = 2 if self.trade_route_has_crew_role(route, "route_guard") else 3
                    if age >= auto_days:
                        route["missed_deliveries"] = int(route.get("missed_deliveries", 0)) + 1
                        route["route_reliability"] = max(35, int(route.get("route_reliability", 82)) - 2)
                        self.resolve_trade_route_incident_by_crew(route, "crew recovery")
                current = self._scheduled_player_trade_route_caravan_state(route, ordinal)
                previous = self._scheduled_player_trade_route_caravan_state(route, ordinal - 1)
                if (
                    current.get("phase") in {"outbound", "returning"}
                    and current.get("phase") != previous.get("phase")
                ):
                    self.maybe_start_player_trade_route_incident(route, ordinal, current)
                incident_open = str((route.get("caravan_incident", {}) or {}).get("status", "")) == "open"
                if (
                    current.get("phase") == "destination"
                    and previous.get("phase") != "destination"
                    and not incident_open
                ):
                    self.record_player_trade_route_delivery(route, ordinal)
            route["caravan_last_ordinal"] = today

    def procedural_trade_route_daily_income(self, route: Dict[str, object]) -> int:
        income = int(super().procedural_trade_route_daily_income(route))
        self.ensure_player_trade_route_caravan(route)
        reliability = int(route.get("route_reliability", 82))
        income = income * max(55, reliability) // 82
        development = self.player_trade_route_development_level(route)
        income = income * (100 + development * 5) // 100
        assignments = route.get("crew_assignments", {}) or {}
        if assignments.get("caravan_driver"):
            income = income * 108 // 100
        if assignments.get("regional_courier"):
            income = income * 105 // 100
        if assignments.get("trade_representative"):
            income = income * 110 // 100
        if str((route.get("caravan_incident", {}) or {}).get("status", "")) == "open":
            income = income * 55 // 100
        return max(0, income)

    def regional_circulation_calendar_events_for_date(
        self, month: int, day: int, year: int
    ) -> List[str]:
        events = list(super().regional_circulation_calendar_events_for_date(month, day, year))
        target = self.civic_date_ordinal(month, day, year)
        for route in self.state.player_trade_routes.values():
            incident = route.get("caravan_incident", {}) or {}
            if str(incident.get("status", "")) != "open":
                continue
            details = TRADE_ROUTE_INCIDENTS.get(str(incident.get("type", "")), {})
            started = int(incident.get("ordinal", 0) or 0)
            if target == started:
                events.append(
                    f"Trade route disruption: {route.get('caravan_name')} - {details.get('name', 'road incident')} "
                    f"at chunk ({incident.get('chunk_x', 0)},{incident.get('chunk_y', 0)})."
                )
            recovery_days = 2 if self.trade_route_has_crew_role(route, "route_guard") else 3
            if target == started + recovery_days:
                events.append(
                    f"Expected crew recovery: {route.get('caravan_name')} unless the route is cleared sooner."
                )
        return events

    def regional_journal_overview_lines(self) -> List[str]:
        lines = list(super().regional_journal_overview_lines())
        active = [route for route in self.state.player_trade_routes.values() if route.get("active")]
        if not active:
            return lines
        lines.extend(["", "Route operations:"])
        for route in active:
            incident = route.get("caravan_incident", {}) or {}
            disruption = ""
            if str(incident.get("status", "")) == "open":
                details = TRADE_ROUTE_INCIDENTS.get(str(incident.get("type", "")), {})
                disruption = (
                    f" | DELAYED: {details.get('name', 'incident')} at "
                    f"({incident.get('chunk_x', 0)},{incident.get('chunk_y', 0)})"
                )
            lines.append(
                f"- {route.get('caravan_name')}: reliability {route.get('route_reliability', 82)}/100 | "
                f"{self.player_trade_route_development_name(route)} | streak {route.get('delivery_streak', 0)}"
                f"{disruption}"
            )
        return lines

    def regional_trade_market_effect(self, plan: Dict[str, object]) -> Dict[str, Dict[str, int]]:
        town_key = self.civic_town_key(plan)
        today = self.civic_date_ordinal()
        delivered: Dict[str, int] = {}
        shortages: Dict[str, int] = {}
        for route in self.state.player_trade_routes.values():
            self.ensure_player_trade_route_caravan(route)
            good = str(route.get("good", "General Goods"))
            if str(route.get("destination_town_key", "")) != town_key:
                continue
            age = today - int(route.get("last_delivery_ordinal", 0) or 0)
            if 0 <= age <= 5:
                delivered[good] = max(delivered.get(good, 0), 5 + int(route.get("capacity_level", 0)) * 3 - age)
            incident = route.get("caravan_incident", {}) or {}
            if (
                str(incident.get("status", "")) == "open"
                and str(incident.get("destination_town_key", "")) == town_key
            ):
                shortages[good] = max(shortages.get(good, 0), 3)
        return {"delivered": delivered, "shortages": shortages}

    def procedural_town_market_profile(self, plan: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        profile = dict(super().procedural_town_market_profile(plan))
        active_plan = plan or self.current_procedural_town_plan()
        if not active_plan:
            return profile
        effects = self.regional_trade_market_effect(active_plan)
        profile["route_effects"] = effects
        delivered = list(effects["delivered"])
        shortages = list(effects["shortages"])
        if delivered:
            profile["headline"] = f"Recent caravan deliveries have made {', '.join(delivered)} plentiful."
        if shortages:
            profile["headline"] = f"A delayed caravan has made {', '.join(shortages)} unusually scarce."
        return profile

    def procedural_town_local_stock(self, building: Dict[str, object]) -> List[Dict[str, object]]:
        entries = [dict(entry) for entry in super().procedural_town_local_stock(building)]
        plan = self.current_procedural_town_plan()
        if not plan:
            return entries
        effects = self.regional_trade_market_effect(plan)
        delivered = effects["delivered"]
        shortages = effects["shortages"]
        by_item = {str(entry.get("item")): entry for entry in entries}
        for item, quantity in delivered.items():
            if item not in by_item and str(building.get("type_id", "")) in {"general_store", "market_stall"}:
                price_lookup = getattr(self, "shippable_unit_price", None)
                base = int(price_lookup(item)) * 2 if callable(price_lookup) else 40
                limit = max(1, int(quantity))
                remaining = self.procedural_town_stock_remaining(building, item, limit, plan)
                entry = {
                    "item": item, "price": max(1, base * 85 // 100),
                    "limit": limit, "remaining": remaining,
                    "note": "Fresh caravan delivery",
                }
                entries.append(entry)
                by_item[item] = entry
            elif item in by_item:
                entry = by_item[item]
                bonus = max(1, int(quantity))
                entry["price"] = max(1, int(entry.get("price", 1)) * 85 // 100)
                entry["limit"] = int(entry.get("limit", 0)) + bonus
                entry["remaining"] = int(entry.get("remaining", 0)) + bonus
                entry["note"] = "Fresh caravan delivery"
        for item, severity in shortages.items():
            if item not in by_item:
                continue
            entry = by_item[item]
            entry["price"] = max(1, int(entry.get("price", 1)) * (115 + int(severity) * 3) // 100)
            entry["remaining"] = max(0, int(entry.get("remaining", 0)) - int(severity))
            entry["note"] = "Caravan-delayed shortage"
        return sorted(entries, key=lambda entry: (int(entry.get("remaining", 0)) <= 0, str(entry.get("item", ""))))

    def procedural_town_demand_offer(self, plan: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        offer = dict(super().procedural_town_demand_offer(plan))
        active_plan = plan or self.current_procedural_town_plan()
        if not active_plan or not offer:
            return offer
        effects = self.regional_trade_market_effect(active_plan)
        item = str(offer.get("item", ""))
        if item in effects["delivered"]:
            relief = max(1, int(effects["delivered"][item]))
            offer["price"] = max(1, int(offer.get("price", 1)) * 80 // 100)
            offer["limit"] = max(1, int(offer.get("limit", 1)) - relief)
            offer["remaining"] = min(int(offer.get("remaining", 0)), int(offer["limit"]))
            offer["route_note"] = "Recent deliveries have relieved this shortage."
        elif item in effects["shortages"]:
            severity = int(effects["shortages"][item])
            offer["price"] = max(1, int(offer.get("price", 1)) * (120 + severity * 3) // 100)
            offer["limit"] = int(offer.get("limit", 1)) + severity
            offer["remaining"] = int(offer.get("remaining", 0)) + severity
            offer["route_note"] = "A delayed caravan has deepened this shortage."
        return offer

    def trade_route_assigned_to_follower(self, follower_id: str) -> Tuple[Optional[Dict[str, object]], str]:
        for route in self.state.player_trade_routes.values():
            for role, assigned_id in (route.get("crew_assignments", {}) or {}).items():
                if str(assigned_id) == str(follower_id):
                    return route, str(role)
        return None, ""

    def assign_follower_to_trade_route(self, route_id: str, role: str, follower_id: str) -> bool:
        route = self.state.player_trade_routes.get(str(route_id))
        if not route or role not in TRADE_ROUTE_CREW_ROLES:
            return False
        if follower_id not in self.active_travel_follower_ids():
            self.set_message("That follower must be active before joining a caravan crew.")
            return False
        for other in self.state.player_trade_routes.values():
            assignments = other.setdefault("crew_assignments", {})
            for assigned_role in list(assignments):
                if str(assignments.get(assigned_role, "")) == str(follower_id) or (
                    other is route and assigned_role == role
                ):
                    displaced_id = str(assignments.get(assigned_role, ""))
                    assignments.pop(assigned_role, None)
                    if displaced_id and displaced_id != str(follower_id):
                        displaced = self.travel_follower_record(displaced_id)
                        displaced.update({"mode": "home", "task": "", "activity": "returned from caravan duty"})
        route.setdefault("crew_assignments", {})[role] = str(follower_id)
        record = self.travel_follower_record(str(follower_id))
        record.update({
            "mode": "work", "task": role, "location": "Wilderness",
            "activity": f"serving as {TRADE_ROUTE_CREW_ROLES[role].lower()} aboard {route.get('caravan_name')}",
        })
        self.reset_travel_follower_work_day()
        name = self.travel_follower_data(str(follower_id)).get("name", follower_id)
        self.autosave_with_message(f"Assigned {name} to {route.get('caravan_name')} as {TRADE_ROUTE_CREW_ROLES[role].lower()}.")
        return True

    def travel_follower_task_options(self, follower_id: str) -> List[str]:
        options = [
            task for task in super().travel_follower_task_options(follower_id)
            if task not in TRADE_ROUTE_CREW_ROLES
        ]
        route, role = self.trade_route_assigned_to_follower(follower_id)
        if route and role:
            options.append(role)
        return options

    def assign_travel_follower_task(self, follower_id: str, task_id: str) -> bool:
        if str(task_id) not in TRADE_ROUTE_CREW_ROLES:
            for route in self.state.player_trade_routes.values():
                assignments = route.setdefault("crew_assignments", {})
                for role in list(assignments):
                    if str(assignments.get(role, "")) == str(follower_id):
                        assignments.pop(role, None)
        return super().assign_travel_follower_task(follower_id, task_id)

    def perform_trade_route_follower_work(self, follower_id: str, task_id: str) -> bool:
        route, role = self.trade_route_assigned_to_follower(follower_id)
        if not route or role != str(task_id) or not route.get("active"):
            self.travel_follower_record(follower_id)["activity"] = "waiting for an active route assignment"
            return False
        counters = route.setdefault("crew_work_counters", {})
        counters[role] = int(counters.get(role, 0)) + 1
        if int(counters[role]) % 2 == 0:
            route["route_development_points"] = int(route.get("route_development_points", 0)) + 1
        if role == "route_guard":
            incident = route.get("caravan_incident", {}) or {}
            if str(incident.get("status", "")) == "open":
                incident["progress"] = int(incident.get("progress", 0)) + 1
                if int(incident["progress"]) >= 4:
                    self.resolve_trade_route_incident_by_crew(route, f"guarded by {self.travel_follower_data(follower_id).get('name', follower_id)}")
            route["route_reliability"] = min(100, int(route.get("route_reliability", 82)) + 1)
            activity = "patrolled the caravan road and checked the night watch"
        elif role == "caravan_driver":
            route["route_reliability"] = min(100, int(route.get("route_reliability", 82)) + 1)
            activity = "maintained the wagons, harness, and safe road pace"
        elif role == "regional_courier":
            activity = "carried manifests and route news between the terminals"
        else:
            destination = self.civic_plan_for_key(str(route.get("destination_town_key", "")))
            if destination and int(counters[role]) % 4 == 0:
                community = self.ensure_procedural_town_community(destination)
                community["development_points"] = int(community.get("development_points", 0)) + 1
            activity = "negotiated orders and kept both terminal markets informed"
        self.travel_follower_record(follower_id)["activity"] = activity
        return True

    def travel_with_procedural_caravan(self, actor: Dict[str, object], approach: str) -> bool:
        route = self.state.player_trade_routes.get(str(actor.get("route_id", "")))
        deliveries_before = int(route.get("caravan_deliveries", 0)) if route else 0
        result = bool(super().travel_with_procedural_caravan(actor, approach))
        if result and route and int(route.get("caravan_deliveries", 0)) > deliveries_before:
            self.record_player_trade_route_delivery(route, self.civic_date_ordinal(), already_counted=True)
        return result

    def trade_route_crew_menu(self, route: Dict[str, object]) -> None:
        while True:
            assignments = route.get("crew_assignments", {}) or {}
            items = [
                MenuItem(
                    label=f"{label}: {self.travel_follower_data(str(assignments.get(role, ''))).get('name', 'Unassigned')}",
                    value=role, enabled=True,
                    hint="Assign an active follower to this route role.",
                )
                for role, label in TRADE_ROUTE_CREW_ROLES.items()
            ]
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Caravan Crew", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return
            role = str(choice.value)
            candidates = [
                MenuItem(
                    label=str(self.travel_follower_data(follower_id).get("name", follower_id)),
                    value=follower_id, enabled=True,
                    hint=str(self.travel_follower_data(follower_id).get("role", "Follower")),
                ) for follower_id in self.active_travel_follower_ids()
            ]
            if assignments.get(role):
                candidates.append(MenuItem(label="Clear assignment", value="__clear__", enabled=True))
            candidates.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            selected = self.vertical_panel_select(TRADE_ROUTE_CREW_ROLES[role], candidates, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not selected or selected.value == MENU_BACK:
                continue
            if selected.value == "__clear__":
                follower_id = str(assignments.pop(role, ""))
                if follower_id:
                    record = self.travel_follower_record(follower_id)
                    record.update({"mode": "home", "task": "", "activity": "returned from caravan duty"})
                self.autosave_with_message(f"Cleared the {TRADE_ROUTE_CREW_ROLES[role].lower()} assignment.")
            else:
                self.assign_follower_to_trade_route(str(route.get("id", "")), role, str(selected.value))

    def resolve_player_trade_route_incident(self, route_id: str, approach: str) -> bool:
        route = self.state.player_trade_routes.get(str(route_id))
        incident = route.get("caravan_incident", {}) if route else {}
        if not route or not isinstance(incident, dict) or str(incident.get("status", "")) != "open":
            self.set_message("This caravan has no unresolved road disruption.")
            return False
        details = TRADE_ROUTE_INCIDENTS.get(str(incident.get("type", "")), {})
        supply = str(details.get("supply", "Wood"))
        choices = {
            "labor": {"stamina": 7, "minutes": 55, "money": 85, "points": 3},
            "supplies": {"stamina": 3, "minutes": 25, "money": 110, "points": 4, "item": supply, "qty": 2},
            "escort": {"stamina": 9, "minutes": 75, "money": 140, "points": 5},
        }
        cost = choices.get(str(approach))
        if not cost:
            return False
        item = str(cost.get("item", ""))
        qty = int(cost.get("qty", 0))
        if item and int(self.state.inventory.get(item, 0)) < qty:
            self.set_message(f"This repair needs {qty} {item}.")
            return False
        if int(self.state.stamina) < int(cost["stamina"]):
            self.set_message(f"This response needs {cost['stamina']} stamina.")
            return False
        self.state.stamina -= int(cost["stamina"])
        if item:
            self.state.inventory[item] -= qty
            if self.state.inventory[item] <= 0:
                self.state.inventory.pop(item, None)
        self.advance_time(int(cost["minutes"]))
        self.state.money += int(cost["money"])
        incident["status"] = "resolved"
        incident["resolved_by"] = f"player:{approach}"
        route["route_reliability"] = min(100, int(route.get("route_reliability", 82)) + 3)
        route["route_development_points"] = int(route.get("route_development_points", 0)) + int(cost["points"])
        log = route.setdefault("route_event_log", [])
        log.append(f"{getattr(self.state, 'date_label', '')}: player resolved {details.get('name', 'road disruption')} by {approach}.")
        route["route_event_log"] = log[-24:]
        if hasattr(self, "add_wilderness_region_vitality"):
            self.add_wilderness_region_vitality(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y), 3,
                f"cleared {details.get('name', 'a caravan disruption')}",
            )
        self.autosave_with_message(
            f"Resolved {details.get('name', 'the road disruption')}: +{cost['money']}g, +3 regional vitality."
        )
        return True

    def help_operating_caravan(self, route: Dict[str, object]) -> bool:
        today = str(getattr(self.state, "date_label", ""))
        if str(route.get("roadwork_day", "")) == today:
            self.set_message("You already helped this caravan's road crew today.")
            return False
        if int(self.state.stamina) < 4:
            self.set_message("Road work needs 4 stamina.")
            return False
        self.state.stamina -= 4
        self.advance_time(40)
        self.state.money += 45
        route["roadwork_day"] = today
        route["route_development_points"] = int(route.get("route_development_points", 0)) + 2
        route["route_reliability"] = min(100, int(route.get("route_reliability", 82)) + 1)
        self.autosave_with_message(f"Helped {route.get('caravan_name')} maintain the road: +45g and route development.")
        return True

    def procedural_caravan_lines(self, actor: Dict[str, object]) -> List[str]:
        lines = list(super().procedural_caravan_lines(actor))
        route = self.state.player_trade_routes.get(str(actor.get("route_id", "")), {})
        if not route:
            return lines
        incident = route.get("caravan_incident", {}) or {}
        assignments = route.get("crew_assignments", {}) or {}
        insert = [
            f"Reliability: {route.get('route_reliability', 82)}/100",
            f"Road: {self.player_trade_route_development_name(route)} ({route.get('route_development_points', 0)} development)",
            f"Delivery streak: {route.get('delivery_streak', 0)} | Missed: {route.get('missed_deliveries', 0)}",
            "Crew: " + (
                ", ".join(
                    f"{TRADE_ROUTE_CREW_ROLES.get(role, role)} - {self.travel_follower_data(str(follower_id)).get('name', follower_id)}"
                    for role, follower_id in assignments.items()
                ) if assignments else "no follower assignments"
            ),
        ]
        if str(incident.get("status", "")) == "open":
            details = TRADE_ROUTE_INCIDENTS.get(str(incident.get("type", "")), {})
            insert.extend([
                f"ACTIVE DISRUPTION: {details.get('name', 'Road incident')}",
                str(details.get("description", "The route is delayed.")),
                f"Location: chunk ({incident.get('chunk_x', 0)},{incident.get('chunk_y', 0)})",
            ])
        return lines[:8] + insert + lines[8:]

    def procedural_caravan_menu(self, actor: Dict[str, object]) -> None:
        if str(getattr(self.state, "location", "")) != "Wilderness":
            return super().procedural_caravan_menu(actor)
        route = self.state.player_trade_routes.get(str(actor.get("route_id", "")))
        if not route:
            return
        while True:
            incident = route.get("caravan_incident", {}) or {}
            disrupted = str(incident.get("status", "")) == "open"
            items = [
                MenuItem(label="Browse cargo", value="cargo", enabled=True),
                MenuItem(label="Resolve road disruption", value="resolve", enabled=disrupted,
                         hint="Help the stranded caravan continue its route."),
                MenuItem(label="Help road crew", value="roadwork", enabled=not disrupted,
                         hint="4 stamina, 40 minutes; improve this route."),
                MenuItem(label="Route status", value="status", enabled=True),
                MenuItem(label="Talk to crew", value="talk", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(str(actor.get("name", "Trade Caravan")), items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "status":
                self.vertical_panel_view("Caravan Route", self.procedural_caravan_lines(actor), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "talk":
                self.vertical_panel_view("Caravan Crew", [
                    "The caravan has made a real camp beside the road.", "",
                    f"Cargo: {route.get('good', 'General Goods')}",
                    f"Next stop: {self.player_trade_route_caravan_state(route).get('next_stop', 'the next terminal')}",
                    "The crew remembers repaired crossings, safe camps, shortages, and every traveler who lends a hand.",
                ], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice.value == "roadwork":
                self.help_operating_caravan(route)
            elif choice.value == "resolve":
                details = TRADE_ROUTE_INCIDENTS.get(str(incident.get("type", "")), {})
                supply = str(details.get("supply", "Wood"))
                approaches = [
                    MenuItem(label="Clear and repair with crew", value="labor", enabled=int(self.state.stamina) >= 7, hint="7 stamina, 55 minutes"),
                    MenuItem(label=f"Provide 2 {supply}", value="supplies", enabled=int(self.state.stamina) >= 3 and int(self.state.inventory.get(supply, 0)) >= 2, hint="3 stamina, 25 minutes"),
                    MenuItem(label="Escort caravan through", value="escort", enabled=int(self.state.stamina) >= 9, hint="9 stamina, 75 minutes"),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ]
                selected = self.vertical_panel_select(str(details.get("name", "Road Disruption")), approaches, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
                if selected and selected.value != MENU_BACK and self.resolve_player_trade_route_incident(str(route.get("id", "")), str(selected.value)):
                    return
            else:
                stock = self.procedural_caravan_stock(actor)
                stock_items = [
                    MenuItem(label=f"{entry['item']} - {entry['price']}g", value=str(entry["item"]), enabled=int(entry["remaining"]) > 0,
                             hint=f"{entry['remaining']} left | from {entry['origin']}")
                    for entry in stock
                ]
                stock_items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
                purchase = self.vertical_panel_select("Caravan Cargo", stock_items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
                if purchase and purchase.value != MENU_BACK:
                    self.purchase_procedural_caravan_stock(actor, str(purchase.value), 1)

    def trade_route_state_chunk(self, route: Dict[str, object], state: Dict[str, object]) -> Optional[Tuple[int, int]]:
        if state.get("phase") == "disrupted":
            return int(state.get("chunk_x", 0)), int(state.get("chunk_y", 0))
        if state.get("phase") not in {"outbound", "returning"}:
            return None
        path = self.player_trade_route_chunk_path(route)
        if state.get("phase") == "returning":
            path = list(reversed(path))
        if not path:
            return None
        travel_days = max(1, int(state.get("travel_days", 1)))
        progress = max(1, int(state.get("progress", 1)))
        time_fraction = (int(getattr(self.state, "hour", 12)) + int(getattr(self.state, "minute", 0)) / 60.0) / 24.0
        fraction = min(1.0, max(0.0, (progress - 1 + time_fraction) / travel_days))
        index = min(len(path) - 1, max(0, round(fraction * (len(path) - 1))))
        return path[index]

    def player_trade_route_wilderness_actors(self, chunk_x: int, chunk_y: int) -> List[Dict[str, object]]:
        self.update_player_trade_caravans()
        actors: List[Dict[str, object]] = []
        for route in self.state.player_trade_routes.values():
            if not route.get("active"):
                continue
            state = self.player_trade_route_caravan_state(route)
            point = self.trade_route_state_chunk(route, state)
            if point == (int(chunk_x), int(chunk_y)):
                source = self.civic_plan_for_key(str(route.get("source_town_key", ""))) or {}
                destination = self.civic_plan_for_key(str(route.get("destination_town_key", ""))) or {}
                actors.append({
                    "id": f"road-caravan:{route.get('id')}",
                    "name": str(route.get("caravan_name", "Trade Caravan")),
                    "role": "Trade Caravan", "procedural_caravan": True,
                    "route_id": str(route.get("id", "")), "static_actor": True,
                    "activity": str(state.get("status", "traveling the trade road")),
                    "source_name": str(source.get("name", "Source Town")),
                    "destination_name": str(destination.get("name", "Destination Town")),
                    "next_stop": str(state.get("next_stop", "")),
                    "phase": str(state.get("phase", "")),
                })
            level = self.player_trade_route_development_level(route)
            path = self.player_trade_route_chunk_path(route)
            if level and len(path) >= 3:
                feature_indices = [len(path) // 2]
                if level >= 3:
                    feature_indices.extend([len(path) // 3, len(path) * 2 // 3])
                if any(path[index] == (int(chunk_x), int(chunk_y)) for index in set(feature_indices)):
                    actors.append({
                        "id": f"route-feature:{route.get('id')}:{chunk_x},{chunk_y}",
                        "name": self.player_trade_route_development_name(route),
                        "role": "Route Infrastructure", "trade_route_feature": True,
                        "route_id": str(route.get("id", "")), "static_actor": True,
                        "feature_level": level,
                    })
        return actors

    def wilderness_traveler_cache_key(self, chunk_x: int, chunk_y: int) -> str:
        return (
            f"{super().wilderness_traveler_cache_key(chunk_x, chunk_y)}:"
            f"D{self.civic_date_ordinal()}:H{int(getattr(self.state, 'hour', 0)) // 6}"
        )

    def generate_wilderness_travelers(self, chunk_x: int, chunk_y: int) -> List[Dict[str, object]]:
        travelers = list(super().generate_wilderness_travelers(chunk_x, chunk_y))
        additions = self.player_trade_route_wilderness_actors(chunk_x, chunk_y)
        if not additions:
            return travelers
        grid = self.wilderness_stream_map(chunk_x, chunk_y) or self.get_wilderness_chunk_map(chunk_x, chunk_y)
        occupied = {(int(value.get("x", -1)), int(value.get("y", -1))) for value in travelers}
        road = [
            (x, y) for y in range(3, len(grid) - 3) for x in range(4, len(grid[0]) - 4)
            if grid[y][x] in {":", "="} and (x, y) not in occupied
        ]
        fallback = [
            (x, y) for y in range(3, len(grid) - 3) for x in range(4, len(grid[0]) - 4)
            if grid[y][x] not in {"#", "~", "S", "V", "X", "!"} and (x, y) not in occupied
        ]
        candidates = road or fallback
        for index, actor in enumerate(additions):
            position = next((point for point in candidates if all(abs(point[0] - ox) + abs(point[1] - oy) >= 4 for ox, oy in occupied)), None)
            if not position:
                continue
            actor.update({"x": position[0], "y": position[1], "anchor_x": position[0], "anchor_y": position[1]})
            travelers.append(actor)
            occupied.add(position)
            if actor.get("procedural_caravan") and str(actor.get("phase", "")) == "disrupted":
                route = self.state.player_trade_routes.get(str(actor.get("route_id", "")), {})
                incident = route.get("caravan_incident", {}) or {}
                details = TRADE_ROUTE_INCIDENTS.get(str(incident.get("type", "")), {})
                nearby = [
                    point for point in candidates
                    if point not in occupied and abs(point[0] - position[0]) + abs(point[1] - position[1]) <= 3
                ][:2]
                for part_index, part in enumerate(nearby):
                    travelers.append({
                        **actor,
                        "id": f"{actor.get('id')}:scene:{part_index}",
                        "x": part[0], "y": part[1], "anchor_x": part[0], "anchor_y": part[1],
                        "caravan_visual_part": True,
                        "caravan_visual_symbol": str(details.get("symbol", "O")) if part_index == 0 else "O",
                    })
                    occupied.add(part)
        return travelers

    def render_wilderness_traveler(self, traveler: Dict[str, object]) -> str:
        if traveler.get("caravan_visual_part"):
            symbol = str(traveler.get("caravan_visual_symbol", "O"))[:1]
            return colorize(symbol, C.DANGER if symbol in {"!", "#"} else C.WATER if symbol == "~" else C.SHOP)
        if traveler.get("trade_route_feature"):
            level = int(traveler.get("feature_level", 1))
            return colorize(("+", "A", "P")[max(0, min(2, level - 1))], C.SHOP)
        if traveler.get("procedural_caravan"):
            return colorize("&", C.SHOP)
        return super().render_wilderness_traveler(traveler)

    def wilderness_traveler_lines(self, traveler: Dict[str, object], topic: str = "work") -> List[str]:
        if traveler.get("procedural_caravan") or traveler.get("trade_route_feature"):
            route = self.state.player_trade_routes.get(str(traveler.get("route_id", "")), {})
            actor = dict(traveler)
            actor.setdefault("source_name", str((self.civic_plan_for_key(str(route.get("source_town_key", ""))) or {}).get("name", "Source Town")))
            actor.setdefault("destination_name", str((self.civic_plan_for_key(str(route.get("destination_town_key", ""))) or {}).get("name", "Destination Town")))
            lines = self.procedural_caravan_lines(actor)
            if traveler.get("trade_route_feature"):
                lines.extend(["", "This infrastructure exists because deliveries and road work developed the route."])
            return lines
        return super().wilderness_traveler_lines(traveler, topic)

    def use_trade_route_feature(self, traveler: Dict[str, object]) -> bool:
        route = self.state.player_trade_routes.get(str(traveler.get("route_id", "")))
        if not route:
            return False
        if int(traveler.get("feature_level", 1)) < 2:
            self.set_message("This signed route offers direction, but no sheltered rest yet.")
            return False
        today = str(getattr(self.state, "date_label", ""))
        if str(route.get("waystation_use_day", "")) == today:
            self.set_message("You already rested at this route waystation today.")
            return False
        route["waystation_use_day"] = today
        self.advance_time(20)
        maximum = int(self.max_stamina()) if hasattr(self, "max_stamina") else 100
        self.state.stamina = min(maximum, int(self.state.stamina) + 8)
        self.autosave_with_message("Rested at the developed trade-route shelter: +8 stamina.")
        return True

    def show_wilderness_traveler(self, traveler: Dict[str, object]):
        if traveler.get("procedural_caravan"):
            self.procedural_caravan_menu(traveler)
            return
        if traveler.get("trade_route_feature"):
            choice = self.vertical_panel_select(
                str(traveler.get("name", "Trade Route")),
                [
                    MenuItem(label="Read route board", value="report", enabled=True),
                    MenuItem(label="Rest at waystation", value="rest", enabled=int(traveler.get("feature_level", 1)) >= 2),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True,
            )
            if choice and choice.value == "report":
                self.vertical_panel_view("Trade Route", self.wilderness_traveler_lines(traveler), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            elif choice and choice.value == "rest":
                self.use_trade_route_feature(traveler)
            return
        return super().show_wilderness_traveler(traveler)
