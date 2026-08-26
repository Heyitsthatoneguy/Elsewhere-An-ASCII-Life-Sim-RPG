from __future__ import annotations

"""Persistent world work shared by boards, dialogue, and autonomous residents.

An opportunity is one authoritative record.  The bulletin board advertises it,
the giver talks about it, the player's Quest Log tracks it, and an adventurous
resident may physically undertake it if the player leaves it unclaimed.
"""

import heapq
import random
from typing import Dict, Iterable, List, Optional, Tuple

from ascii_farmstead_data import (
    CRAFTING_RECIPES,
    FISH_DATA,
    MENU_BACK,
    TOWN_NPC_DEFINITIONS,
    WILDERNESS_FORAGE_DATA,
    WILDERNESS_FORAGE_SYMBOLS,
)
from ascii_farmstead_helpers import forage_item_for_symbol, quantity_item_phrase
from ascii_farmstead_wilderness_generation import BIOME_PLANT_SYMBOLS, wilderness_tile_semantics


WORLD_OPPORTUNITY_SCHEMA_VERSION = 3
WORLD_OPPORTUNITY_OPEN_CAP = 6
WORLD_OPPORTUNITY_HISTORY_CAP = 24
WORLD_OPPORTUNITY_ACTIVE_PARTY_CAP = 5
NPC_TRAVEL_STEP_MINUTES = 6
NPC_ROUTE_SEGMENT_LIMIT = 48


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _safe_dict(value: object) -> Dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_text_list(value: object, limit: int = 24, width: int = 240) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(row)[:width] for row in value if str(row or "").strip()][-limit:]


def sanitize_world_opportunity_state(value: object) -> Dict[str, object]:
    raw = _safe_dict(value)
    opportunities: Dict[str, Dict[str, object]] = {}
    for raw_id, source in _safe_dict(raw.get("opportunities")).items():
        if not isinstance(source, dict):
            continue
        opportunity_id = str(source.get("id", raw_id) or raw_id)[:160]
        if not opportunity_id:
            continue
        record = dict(source)
        record["id"] = opportunity_id
        record["status"] = str(source.get("status", "open"))[:32]
        record["kind"] = str(source.get("kind", "gather_delivery"))[:40]
        record["title"] = str(source.get("title", "Local Work"))[:120]
        record["description"] = str(source.get("description", ""))[:800]
        record["giver_id"] = str(source.get("giver_id", ""))[:160]
        record["giver_name"] = str(source.get("giver_name", ""))[:100]
        record["quest_id"] = str(source.get("quest_id", opportunity_id))[:180]
        record["created_day"] = _bounded_int(source.get("created_day", 1), 1, 1, 9999999)
        record["claimed_day"] = _bounded_int(source.get("claimed_day", 0), 0, 0, 9999999)
        record["resolved_day"] = _bounded_int(source.get("resolved_day", 0), 0, 0, 9999999)
        record["reward_money"] = _bounded_int(source.get("reward_money", 0), 0, 0, 9999999)
        record["quantity"] = _bounded_int(source.get("quantity", 1), 1, 1, 9999)
        record["history"] = _safe_text_list(source.get("history"), 16)
        record["resource_positions"] = [
            {
                "world_x": _bounded_int(row.get("world_x", 0), 0, -99999999, 99999999),
                "world_y": _bounded_int(row.get("world_y", 0), 0, -99999999, 99999999),
                "item": str(row.get("item", ""))[:100],
                "symbol": str(row.get("symbol", ""))[:1],
            }
            for row in (source.get("resource_positions", []) if isinstance(source.get("resource_positions"), list) else [])
            if isinstance(row, dict)
        ][:24]
        for field in ("giver_position", "destination", "target_position", "turn_in"):
            record[field] = _safe_dict(source.get(field))
        opportunities[opportunity_id] = record

    parties: Dict[str, Dict[str, object]] = {}
    for raw_id, source in _safe_dict(raw.get("parties")).items():
        if not isinstance(source, dict):
            continue
        party_id = str(source.get("id", raw_id) or raw_id)[:160]
        if not party_id:
            continue
        record = dict(source)
        record["id"] = party_id
        record["opportunity_id"] = str(source.get("opportunity_id", ""))[:160]
        record["status"] = str(source.get("status", "active"))[:32]
        record["phase"] = str(source.get("phase", "preparing"))[:40]
        record["leader_id"] = str(source.get("leader_id", ""))[:160]
        record["leader_name"] = str(source.get("leader_name", "Resident"))[:100]
        record["member_ids"] = [str(row)[:160] for row in source.get("member_ids", []) if str(row)][:4]
        record["member_names"] = [str(row)[:100] for row in source.get("member_names", []) if str(row)][:4]
        record["world_x"] = _bounded_int(source.get("world_x", 0), 0, -99999999, 99999999)
        record["world_y"] = _bounded_int(source.get("world_y", 0), 0, -99999999, 99999999)
        record["target_world_x"] = _bounded_int(source.get("target_world_x", 0), 0, -99999999, 99999999)
        record["target_world_y"] = _bounded_int(source.get("target_world_y", 0), 0, -99999999, 99999999)
        record["minute_remainder"] = _bounded_int(source.get("minute_remainder", 0), 0, 0, NPC_TRAVEL_STEP_MINUTES - 1)
        record["quantity"] = _bounded_int(source.get("quantity", 1), 1, 1, 9999)
        record["gathered"] = _bounded_int(source.get("gathered", 0), 0, 0, 9999)
        record["wait_minutes"] = _bounded_int(source.get("wait_minutes", 0), 0, 0, 100000)
        record["inventories"] = {
            str(actor_id)[:160]: {
                str(item)[:100]: _bounded_int(quantity, 0, 0, 999999)
                for item, quantity in _safe_dict(inventory).items()
                if _bounded_int(quantity, 0, 0, 999999) > 0
            }
            for actor_id, inventory in _safe_dict(source.get("inventories")).items()
            if isinstance(inventory, dict)
        }
        record["history"] = _safe_text_list(source.get("history"), 20)
        record["task_kind"] = str(source.get("task_kind", ""))[:40]
        record["arrival_phase"] = str(source.get("arrival_phase", ""))[:40]
        record["task_index"] = _bounded_int(source.get("task_index", 0), 0, 0, 9999)
        record["action_progress"] = _bounded_int(source.get("action_progress", 0), 0, 0, 100000)
        record["party_health"] = _bounded_int(source.get("party_health", 0), 0, 0, 999999)
        record["party_max_health"] = _bounded_int(source.get("party_max_health", 0), 0, 0, 999999)
        record["route_target_world_x"] = _bounded_int(source.get("route_target_world_x", 0), 0, -99999999, 99999999)
        record["route_target_world_y"] = _bounded_int(source.get("route_target_world_y", 0), 0, -99999999, 99999999)
        record["stuck_steps"] = _bounded_int(source.get("stuck_steps", 0), 0, 0, 9999)
        record["action_target"] = _safe_dict(source.get("action_target"))
        record["route_steps"] = [
            {
                "world_x": _bounded_int(row.get("world_x", 0), 0, -99999999, 99999999),
                "world_y": _bounded_int(row.get("world_y", 0), 0, -99999999, 99999999),
            }
            for row in (source.get("route_steps", []) if isinstance(source.get("route_steps"), list) else [])
            if isinstance(row, dict)
        ][:NPC_ROUTE_SEGMENT_LIMIT]
        record["task_waypoints"] = [
            dict(row) for row in source.get("task_waypoints", [])
            if isinstance(row, dict)
        ][:64]
        parties[party_id] = record

    return {
        "schema_version": WORLD_OPPORTUNITY_SCHEMA_VERSION,
        "seeded": bool(raw.get("seeded", False)),
        "last_refresh_day": _bounded_int(raw.get("last_refresh_day", 0), 0, 0, 9999999),
        "last_claim_day": _bounded_int(raw.get("last_claim_day", 0), 0, 0, 9999999),
        "next_serial": _bounded_int(raw.get("next_serial", 1), 1, 1, 99999999),
        "opportunities": opportunities,
        "parties": parties,
        "event_log": _safe_text_list(raw.get("event_log"), WORLD_OPPORTUNITY_HISTORY_CAP),
    }


class WorldOpportunityMixin:
    """One persistent source of truth for local work and NPC expeditions."""

    def ensure_world_opportunity_state(self) -> Dict[str, object]:
        current = getattr(self.state, "world_opportunity_state", None)
        if (
            isinstance(current, dict)
            and int(current.get("schema_version", 0) or 0) == WORLD_OPPORTUNITY_SCHEMA_VERSION
            and isinstance(current.get("opportunities"), dict)
            and isinstance(current.get("parties"), dict)
        ):
            state = current
        else:
            state = sanitize_world_opportunity_state(current)
            self.state.world_opportunity_state = state
        if not bool(state.get("seeded", False)):
            self.seed_starting_world_opportunities()
            state = self.state.world_opportunity_state
        self.sync_world_opportunity_quests()
        return state

    def world_opportunity_day(self) -> int:
        return int(self.quest_absolute_day()) if hasattr(self, "quest_absolute_day") else int(self.absolute_game_day())

    @staticmethod
    def world_opportunity_stable_number(text: object) -> int:
        value = 2166136261
        for char in str(text):
            value ^= ord(char)
            value = (value * 16777619) & 0xFFFFFFFF
        return value

    def world_opportunity_actor(self, actor_id: str) -> Dict[str, object]:
        actor_id = str(actor_id)
        if hasattr(self, "npc_record_by_id"):
            record = self.npc_record_by_id(actor_id)
            if isinstance(record, dict) and record:
                return record
        for record in TOWN_NPC_DEFINITIONS:
            if str(record.get("id", "")) == actor_id:
                return dict(record)
        populations = getattr(self.state, "procedural_settlement_populations", {})
        if isinstance(populations, dict):
            for population in populations.values():
                if not isinstance(population, dict):
                    continue
                record = _safe_dict(population.get("residents")).get(actor_id)
                if isinstance(record, dict):
                    return record
        return {}

    def world_opportunity_procedural_actor_home(
        self, actor_id: str
    ) -> Tuple[Dict[str, object], Optional[Tuple[int, int]]]:
        populations = getattr(self.state, "procedural_settlement_populations", {})
        if not isinstance(populations, dict):
            return {}, None
        for town_key, population in populations.items():
            if not isinstance(population, dict):
                continue
            actor = _safe_dict(population.get("residents")).get(str(actor_id))
            if not isinstance(actor, dict):
                continue
            try:
                chunk_x, chunk_y = (int(value) for value in str(town_key).split(",", 1))
            except (TypeError, ValueError):
                plan = self.procedural_town_plan_for_resident(actor) if hasattr(self, "procedural_town_plan_for_resident") else None
                if not plan:
                    return actor, None
                chunk_x, chunk_y = int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))
            return actor, (chunk_x, chunk_y)
        return {}, None

    def world_opportunity_actor_position(self, actor: Dict[str, object]) -> Dict[str, object]:
        generated_actor, generated_home = self.world_opportunity_procedural_actor_home(
            str(actor.get("id", ""))
        )
        if generated_actor and generated_home:
            chunk_x, chunk_y = generated_home
            local_x, local_y = 43, 19
            runtime_location = str(generated_actor.get("runtime_location", ""))
            runtime_x = int(generated_actor.get("runtime_x", -1) or -1)
            runtime_y = int(generated_actor.get("runtime_y", -1) or -1)
            if runtime_location == "outdoor" and runtime_x >= 0 and runtime_y >= 0:
                local_x, local_y = runtime_x, runtime_y
            elif runtime_location.startswith("building:") and hasattr(self, "procedural_town_plan"):
                plan = self.procedural_town_plan(chunk_x, chunk_y) or {}
                building = (
                    self.procedural_town_runtime_building(plan, runtime_location)
                    if plan and hasattr(self, "procedural_town_runtime_building") else None
                )
                if building:
                    local_x = int(building.get("access_x", local_x))
                    local_y = int(building.get("access_y", local_y))
            wx, wy = self.wilderness_world_coords(chunk_x, chunk_y, local_x, local_y)
        elif actor.get("chunk_x") is not None and actor.get("chunk_y") is not None:
            wx, wy = self.wilderness_world_coords(
                int(actor.get("chunk_x", 0)), int(actor.get("chunk_y", 0)),
                int(actor.get("x", 43)), int(actor.get("y", 19)),
            )
        elif hasattr(self, "home_world_world_for_town_position"):
            wx, wy = self.home_world_world_for_town_position(
                int(actor.get("x", 42)), int(actor.get("y", 22))
            )
        else:
            wx, wy = int(actor.get("x", 42)), int(actor.get("y", 22))
        return {
            "location": "Wilderness", "world_x": int(wx), "world_y": int(wy),
            "label": str(actor.get("name", "the requester")),
            **(
                {"chunk_x": int(generated_home[0]), "chunk_y": int(generated_home[1])}
                if generated_home else {}
            ),
        }

    def world_opportunity_tile_item(
        self, tile: str, x: int, y: int, chunk_x: int, chunk_y: int
    ) -> str:
        tile = str(tile)[:1]
        if tile in BIOME_PLANT_SYMBOLS and hasattr(self, "wilderness_biome_plant_record"):
            item = str(self.wilderness_biome_plant_record(x, y, chunk_x, chunk_y, tile).get("item", ""))
            return self.canonical_item_name(item) if hasattr(self, "canonical_item_name") else item
        if tile in {"T", "*"}:
            return "Wood"
        if tile == "o":
            return "Stone"
        if tile == "W":
            return "Watercress"
        if tile == "N":
            return "Pine Nuts"
        if tile == "F":
            return "Wildflowers"
        if tile == "Y":
            return "Salmonberry" if self.state.season == "Spring" else "Blackberry" if self.state.season == "Fall" else "Wild Berries"
        if tile == "u":
            return "Mushrooms"
        if tile in WILDERNESS_FORAGE_SYMBOLS:
            return str(forage_item_for_symbol(tile) or "")
        return ""

    def world_opportunity_resource_candidates(
        self, preferred_item: str = "", minimum: int = 1,
        origin_chunk: Optional[Tuple[int, int]] = None,
    ) -> Tuple[str, List[Dict[str, object]]]:
        preferred_item = (
            self.canonical_item_name(preferred_item)
            if preferred_item and hasattr(self, "canonical_item_name") else str(preferred_item)
        )
        if origin_chunk:
            base_cx, base_cy = int(origin_chunk[0]), int(origin_chunk[1])
        else:
            center = self.home_world_world_for_town_position(55, 22)
            base_cx, base_cy, _lx, _ly = self.home_world_chunk_from_world(*center)
        offsets = (
            (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1),
            (2, 0), (0, 2), (2, 1), (1, 2), (-1, 1),
        )
        grouped: Dict[str, List[Dict[str, object]]] = {}
        for dx, dy in offsets:
            cx, cy = int(base_cx + dx), int(base_cy + dy)
            if hasattr(self, "home_world_chunk_is_authored") and self.home_world_chunk_is_authored(cx, cy):
                continue
            grid = self.get_wilderness_chunk_map(cx, cy)
            for y in range(2, max(2, len(grid) - 2)):
                for x in range(2, max(2, len(grid[y]) - 2)):
                    tile = grid[y][x]
                    item = self.world_opportunity_tile_item(tile, x, y, cx, cy)
                    if not item:
                        continue
                    wx, wy = self.wilderness_world_coords(cx, cy, x, y)
                    grouped.setdefault(item, []).append({
                        "world_x": int(wx), "world_y": int(wy),
                        "item": item, "symbol": str(tile)[:1],
                    })
            if preferred_item and len(grouped.get(preferred_item, [])) >= minimum:
                return preferred_item, grouped[preferred_item][:24]
            viable = [(item, rows) for item, rows in grouped.items() if len(rows) >= minimum]
            if viable and not preferred_item:
                viable.sort(key=lambda pair: (-len(pair[1]), pair[0]))
                return viable[0][0], viable[0][1][:24]
        if preferred_item and grouped.get(preferred_item):
            return preferred_item, grouped[preferred_item][:24]
        viable = [(item, rows) for item, rows in grouped.items() if len(rows) >= minimum]
        if viable:
            viable.sort(key=lambda pair: (-len(pair[1]), pair[0]))
            return viable[0][0], viable[0][1][:24]
        if grouped:
            item, rows = max(grouped.items(), key=lambda pair: len(pair[1]))
            return item, rows[:24]
        return "", []

    def world_opportunity_road_target(self, serial: int) -> Dict[str, object]:
        center = self.home_world_world_for_town_position(55, 22)
        base_cx, base_cy, _lx, _ly = self.home_world_chunk_from_world(*center)
        offsets = ((2, 0), (1, 1), (0, 2), (2, 1), (1, 2))
        cx, cy = offsets[int(serial) % len(offsets)]
        cx, cy = base_cx + cx, base_cy + cy
        # Don't generate distant chunks merely because a save was loaded. The
        # radius is intentionally generous; once the player or an NPC reaches
        # the chunk, ordinary generation supplies the exact walkable approach.
        x = 38 + self.world_opportunity_stable_number(f"x:{serial}:{cx}") % 11
        y = 15 + self.world_opportunity_stable_number(f"y:{serial}:{cy}") % 9
        wx, wy = self.wilderness_world_coords(cx, cy, x, y)
        return {"location": "Wilderness", "world_x": wx, "world_y": wy, "chunk_x": cx, "chunk_y": cy, "x": x, "y": y, "label": f"road survey point ({cx}, {cy})"}

    def build_world_opportunity(self, kind: str, serial: int, starting: bool = False) -> Dict[str, object]:
        today = self.world_opportunity_day()
        actor_pairs = (
            ("dr_ivy", "niko_traveler"),
            ("mayor_ruth", "eli_carpenter"),
            ("niko_traveler", "tess_reader"),
            ("poppy_rancher", "mae_innkeeper"),
        )
        giver_id, destination_id = actor_pairs[int(serial) % len(actor_pairs)]
        giver = self.world_opportunity_actor(giver_id) or dict(TOWN_NPC_DEFINITIONS[0])
        destination_actor = self.world_opportunity_actor(destination_id) or giver
        giver_position = self.world_opportunity_actor_position(giver)
        destination = self.world_opportunity_actor_position(destination_actor)
        opportunity_id = f"world-work:{today}:{serial}:{kind}"
        base = {
            "id": opportunity_id, "quest_id": opportunity_id,
            "kind": kind, "status": "open", "created_day": today,
            "giver_id": str(giver.get("id", "")), "giver_name": str(giver.get("name", "Resident")),
            "giver_position": giver_position, "turn_in": giver_position,
            "reward_money": 180 + (serial % 4) * 35, "history": [],
            "starting_opportunity": bool(starting), "serial": int(serial),
            "town_key": "main-town", "npc_competition_enabled": True,
        }
        if kind == "gather_delivery":
            item = {
                "Spring": "Wild Herbs", "Summer": "Wild Berries",
                "Fall": "Blackberry", "Winter": "Winter Root",
            }.get(str(self.state.season), "Wild Herbs")
            positions: List[Dict[str, object]] = []
            quantity = 3
            base.update({
                "title": f"{giver.get('name', 'A Resident')}'s Forage Request",
                "description": f"{giver.get('name', 'A resident')} needs {quantity_item_phrase(item, quantity)} gathered from the wilderness and brought back in person.",
                "item": item, "quantity": quantity, "resource_positions": positions,
                "target_position": dict(positions[0]) if positions else dict(giver_position),
                "reward_money": 210 + quantity * 35,
            })
        elif kind == "courier":
            cargo = "Sealed Civic Parcel"
            base.update({
                "title": f"Parcel for {destination_actor.get('name', 'a Resident')}",
                "description": f"Carry a sealed parcel from {giver.get('name', 'the sender')} to {destination_actor.get('name', 'the recipient')}. The parcel must physically arrive with its courier.",
                "item": cargo, "quantity": 1, "destination": destination,
                "destination_actor_id": str(destination_actor.get("id", "")),
                "destination_actor_name": str(destination_actor.get("name", "Resident")),
                "reward_money": 260,
            })
        else:
            target = self.world_opportunity_road_target(serial)
            base.update({
                "kind": "survey", "title": "Road Condition Survey",
                "description": f"Visit {target['label']}, inspect the route in person, then report back to {giver.get('name', 'the requester')}.",
                "quantity": 1, "target_position": target, "reward_money": 300,
            })
        return base

    def seed_starting_world_opportunities(self) -> None:
        state = sanitize_world_opportunity_state(getattr(self.state, "world_opportunity_state", None))
        if state.get("seeded"):
            self.state.world_opportunity_state = state
            return
        for kind in ("gather_delivery", "courier", "survey"):
            serial = int(state["next_serial"])
            state["next_serial"] = serial + 1
            opportunity = self.build_world_opportunity(kind, serial, starting=True)
            state["opportunities"][opportunity["id"]] = opportunity
        state["seeded"] = True
        state["last_refresh_day"] = self.world_opportunity_day()
        state["event_log"].append("The town began posting work tied to real people, routes, and supplies.")
        self.state.world_opportunity_state = state

    def world_opportunity_quest_record(self, opportunity: Dict[str, object]) -> Dict[str, object]:
        kind = str(opportunity.get("kind", ""))
        giver_position = dict(opportunity.get("giver_position", {}) or {})
        if kind == "gather_delivery":
            item, quantity = str(opportunity.get("item", "Wild Herbs")), int(opportunity.get("quantity", 1))
            objectives = [{
                "id": "gather", "kind": "item", "item": item, "target": quantity,
                "consume": True, "description": f"Gather {quantity_item_phrase(item, quantity)}.",
            }]
        elif kind == "courier":
            destination = dict(opportunity.get("destination", {}) or {})
            objectives = [{
                "id": "deliver", "kind": "visit", "target": 1,
                "destination": destination, "destination_radius": 3,
                "description": f"Carry the sealed parcel to {opportunity.get('destination_actor_name', 'the recipient')}.",
            }]
            giver_position = destination
        else:
            objectives = [
                {
                    "id": "survey", "kind": "visit", "target": 1,
                    "destination": dict(opportunity.get("target_position", {}) or {}),
                    "destination_radius": 2, "description": f"Reach and inspect {dict(opportunity.get('target_position', {}) or {}).get('label', 'the survey point')}.",
                },
                {
                    "id": "report", "kind": "visit", "target": 1,
                    "destination": giver_position, "destination_radius": 3,
                    "description": f"Return to {opportunity.get('giver_name', 'the requester')} with the survey.",
                },
            ]
        status = "offered"
        if str(opportunity.get("status", "")) == "claimed_player":
            status = "active"
        elif str(opportunity.get("status", "")) == "resolved" and str(opportunity.get("resolved_by", "")) == "player":
            status = "completed"
        elif str(opportunity.get("status", "")) in {"claimed_npc", "resolved", "withdrawn"}:
            status = "abandoned"
        return {
            "id": str(opportunity["quest_id"]), "title": str(opportunity.get("title", "Local Work")),
            "category": "Town", "description": str(opportunity.get("description", "")),
            "giver_id": str(opportunity.get("giver_id", "")), "giver_name": str(opportunity.get("giver_name", "")),
            "objectives": objectives, "status": status,
            "rewards": {"money": int(opportunity.get("reward_money", 0)), "xp": 15, "reputation": 1},
            "turn_in": giver_position, "require_turn_in": True,
            "world_opportunity_id": str(opportunity["id"]), "source": "world_opportunity",
            "journal": list(opportunity.get("history", []) or [])[-8:],
        }

    def sync_world_opportunity_quests(self) -> None:
        if bool(getattr(self, "_syncing_world_opportunities", False)):
            return
        state = getattr(self.state, "world_opportunity_state", {})
        if not isinstance(state, dict):
            return
        self._syncing_world_opportunities = True
        try:
            store = getattr(self.state, "quest_records", None)
            if not isinstance(store, dict):
                store = {}
                self.state.quest_records = store
            for opportunity in state.get("opportunities", {}).values():
                if not isinstance(opportunity, dict):
                    continue
                quest_id = str(opportunity.get("quest_id", opportunity.get("id", "")))
                if not quest_id:
                    continue
                desired = self.world_opportunity_quest_record(opportunity)
                existing = store.get(quest_id)
                if not isinstance(existing, dict):
                    if bool(opportunity.get("linked_existing_quest", False)):
                        continue
                    store[quest_id] = desired
                    continue
                # Player progress is authoritative while active. Only synchronize
                # availability and descriptive fields around it.
                existing["title"] = desired["title"]
                existing["description"] = desired["description"]
                existing["world_opportunity_id"] = opportunity["id"]
                if str(opportunity.get("status")) in {"claimed_npc", "withdrawn"}:
                    existing["status"] = "abandoned"
                elif str(opportunity.get("status")) == "resolved":
                    existing["status"] = "completed" if str(opportunity.get("resolved_by")) == "player" else "abandoned"
        finally:
            self._syncing_world_opportunities = False

    def world_opportunities(self, statuses: Iterable[str] = ()) -> List[Dict[str, object]]:
        state = self.ensure_world_opportunity_state()
        allowed = set(str(value) for value in statuses)
        records = [row for row in state["opportunities"].values() if isinstance(row, dict)]
        if allowed:
            records = [row for row in records if str(row.get("status", "")) in allowed]
        return sorted(records, key=lambda row: (int(row.get("created_day", 0)), str(row.get("title", ""))))

    def world_opportunity_for_quest(self, quest_id: str) -> Dict[str, object]:
        for record in self.world_opportunities():
            if str(record.get("quest_id", "")) == str(quest_id):
                return record
        return {}

    def world_opportunity_for_giver(self, actor_id: str) -> Dict[str, object]:
        actor_id = str(actor_id)
        candidates = [
            row for row in self.world_opportunities(("open", "claimed_player"))
            if str(row.get("giver_id", "")) == actor_id
        ]
        return candidates[0] if candidates else {}

    def accept_quest(self, quest_id: str, announce: bool = True) -> bool:
        accepted = bool(super().accept_quest(quest_id, announce=announce))
        if not accepted:
            return False
        opportunity = self.world_opportunity_for_quest(quest_id)
        if opportunity and str(opportunity.get("status", "")) == "open":
            opportunity["status"] = "claimed_player"
            opportunity["claimed_day"] = self.world_opportunity_day()
            opportunity["history"] = (list(opportunity.get("history", [])) + ["You accepted this work."])[-16:]
            if str(opportunity.get("kind")) == "courier" and not opportunity.get("player_cargo_issued"):
                item = str(opportunity.get("item", "Sealed Civic Parcel"))
                quantity = int(opportunity.get("quantity", 1))
                self.state.inventory[item] = int(self.state.inventory.get(item, 0)) + quantity
                opportunity["player_cargo_issued"] = True
        return True

    def complete_quest(self, quest_id: str, grant_rewards: bool = True) -> bool:
        opportunity = self.world_opportunity_for_quest(quest_id)
        if opportunity and str(opportunity.get("kind")) == "courier":
            item = str(opportunity.get("item", "Sealed Civic Parcel"))
            quantity = int(opportunity.get("quantity", 1))
            if int(self.state.inventory.get(item, 0)) < quantity:
                if hasattr(self, "set_message"):
                    self.set_message(f"You need the {item.lower()} to finish this delivery.")
                return False
        completed = bool(super().complete_quest(quest_id, grant_rewards=grant_rewards))
        if not completed or not opportunity:
            return completed
        if str(opportunity.get("kind")) == "courier":
            item = str(opportunity.get("item", "Sealed Civic Parcel"))
            quantity = int(opportunity.get("quantity", 1))
            self.state.inventory[item] = max(0, int(self.state.inventory.get(item, 0)) - quantity)
            if self.state.inventory[item] <= 0:
                self.state.inventory.pop(item, None)
        opportunity["status"] = "resolved"
        opportunity["resolved_by"] = "player"
        opportunity["resolved_day"] = self.world_opportunity_day()
        opportunity["history"] = (list(opportunity.get("history", [])) + ["You completed the work in person."])[-16:]
        return True

    def world_opportunity_situation_for_actor(
        self, actor: Dict[str, object], kind: str
    ) -> Optional[Dict[str, object]]:
        opportunity = self.world_opportunity_for_giver(str(actor.get("id", "")))
        if not opportunity:
            return None
        quest = self.quest_record(str(opportunity.get("quest_id", "")))
        status = str(quest.get("status", "offered"))
        objective = self.quest_current_objective(quest) if quest else {}
        return {
            "type": "world_opportunity", "id": str(opportunity["id"]),
            "quest_id": str(opportunity["quest_id"]), "quest_record": quest,
            "title": str(opportunity.get("title", "Local Work")),
            "summary": str(objective.get("description", opportunity.get("description", "help with the work"))).rstrip("."),
            "record": opportunity, "prompt": str(opportunity.get("description", "")),
            "promise": status == "offered", "deadline": "until someone completes it",
            "ready": status == "ready",
        }

    def world_opportunity_board_lines(self, opportunity: Dict[str, object]) -> List[str]:
        status = str(opportunity.get("status", "open"))
        status_label = {
            "open": "Available", "claimed_player": "Accepted by you",
            "claimed_npc": f"Accepted by {opportunity.get('claimed_by_name', 'a resident')}",
            "resolved": f"Completed by {opportunity.get('resolved_by_name', opportunity.get('resolved_by', 'someone'))}",
            "withdrawn": "No longer posted",
        }.get(status, status.title())
        lines = [
            str(opportunity.get("title", "Local Work")), "",
            str(opportunity.get("description", "")), "",
            f"Requested by: {opportunity.get('giver_name', 'A resident')}",
            f"Status: {status_label}",
            f"Reward: {opportunity.get('reward_money', 0)}g", "",
        ]
        if status == "open":
            lines.append("You can accept this here or ask the requester about it in person.")
        elif status == "claimed_player":
            quest = self.quest_record(str(opportunity.get("quest_id", "")))
            lines.append(f"Current objective: {self.quest_current_objective(quest).get('description', 'Continue the work.')}")
        elif status == "claimed_npc":
            party = self.world_opportunity_party_for(opportunity)
            lines.append(f"Current activity: {party.get('activity', party.get('phase', 'On the road'))}")
        history = list(opportunity.get("history", []) or [])
        if history:
            lines.extend(["", "Recent history:", *[f"- {row}" for row in history[-4:]]])
        return lines

    def world_opportunity_town_key(self, plan: Dict[str, object]) -> str:
        return str(
            plan.get("key")
            or plan.get("settlement_key")
            or f"procedural:{int(plan.get('chunk_x', 0))},{int(plan.get('chunk_y', 0))}"
        )

    def world_opportunity_origin_chunk(
        self, opportunity: Dict[str, object]
    ) -> Tuple[int, int]:
        raw = opportunity.get("procedural_town_chunk", [])
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            return int(raw[0]), int(raw[1])
        position = _safe_dict(opportunity.get("giver_position"))
        if "chunk_x" in position and "chunk_y" in position:
            return int(position["chunk_x"]), int(position["chunk_y"])
        if "world_x" in position and "world_y" in position:
            chunk_x, chunk_y, _x, _y = self.home_world_chunk_from_world(
                int(position["world_x"]), int(position["world_y"])
            )
            return int(chunk_x), int(chunk_y)
        return 0, 0

    def world_opportunity_world_point(
        self, chunk_x: int, chunk_y: int, x: int, y: int, label: str, **extra: object
    ) -> Dict[str, object]:
        world_x, world_y = self.wilderness_world_coords(
            int(chunk_x), int(chunk_y), int(x), int(y)
        )
        return {
            "location": "Wilderness", "chunk_x": int(chunk_x), "chunk_y": int(chunk_y),
            "x": int(x), "y": int(y), "world_x": int(world_x), "world_y": int(world_y),
            "label": str(label), **extra,
        }

    def world_opportunity_rural_site(
        self, opportunity: Dict[str, object]
    ) -> Tuple[Tuple[int, int], Dict[str, object]]:
        if not hasattr(self, "rural_region_site_chunk") or not hasattr(self, "rural_site_record"):
            return (0, 0), {}
        origin_x, origin_y = self.world_opportunity_origin_chunk(opportunity)
        site_x, site_y = self.rural_region_site_chunk(origin_x, origin_y)
        if abs(int(site_x)) >= 10**7 or abs(int(site_y)) >= 10**7:
            return (0, 0), {}
        self.get_wilderness_chunk_map(int(site_x), int(site_y))
        record = self.rural_site_record(int(site_x), int(site_y))
        return (int(site_x), int(site_y)), record if isinstance(record, dict) else {}

    def world_opportunity_rural_container(
        self,
        chunk_x: int,
        chunk_y: int,
        feature: Dict[str, object],
    ) -> Dict[str, object]:
        self.ensure_container_state()
        key = f"rural:{int(chunk_x)},{int(chunk_y)}:{int(feature.get('x', 0))},{int(feature.get('y', 0))}:crate"
        record = self.state.world_containers.get(key)
        if isinstance(record, dict):
            return record
        contents = self.deterministic_container_contents(key, str(feature.get("profile", "crate")))
        record = {
            "key": key, "scope": f"wilderness:{int(chunk_x)},{int(chunk_y)}",
            "x": int(feature.get("x", 0)), "y": int(feature.get("y", 0)),
            "profile": str(feature.get("profile", "crate")),
            "name": str(feature.get("name", "Shared Supply Crate")),
            "capacity": 200, "contents": contents, "take_policy": "owned",
            "allow_deposit": False, "owner": "the household", "opened": False, "extra_action": "",
        }
        self.state.world_containers[key] = record
        return record

    def world_opportunity_existing_salvage_target(
        self, quantity: int
    ) -> Dict[str, object]:
        containers = getattr(self.state, "world_containers", {})
        if not isinstance(containers, dict):
            return {}
        for key, record in sorted(containers.items(), key=lambda pair: str(pair[0])):
            if not isinstance(record, dict) or str(record.get("take_policy", "")) != "free":
                continue
            contents = _safe_dict(record.get("contents"))
            if sum(max(0, int(value)) for value in contents.values()) < max(1, int(quantity)):
                continue
            scope = str(record.get("scope", ""))
            if not scope.startswith("wilderness:"):
                continue
            try:
                chunk_x, chunk_y = (int(value) for value in scope.split(":", 1)[1].split(",", 1))
            except (TypeError, ValueError):
                continue
            return self.world_opportunity_world_point(
                chunk_x, chunk_y, int(record.get("x", 0)), int(record.get("y", 0)),
                str(record.get("name", "abandoned cache")), container_key=str(record.get("key", key)),
            )
        return {}

    def world_opportunity_water_target(
        self, opportunity: Dict[str, object], ocean: bool = False
    ) -> Dict[str, object]:
        origin_x, origin_y = self.world_opportunity_origin_chunk(opportunity)
        offsets = [
            (dx, dy)
            for radius in range(0, 5)
            for dy in range(-radius, radius + 1)
            for dx in range(-radius, radius + 1)
            if max(abs(dx), abs(dy)) == radius
        ]
        for dx, dy in offsets:
            chunk_x, chunk_y = origin_x + dx, origin_y + dy
            if hasattr(self, "home_world_chunk_is_authored") and self.home_world_chunk_is_authored(chunk_x, chunk_y):
                continue
            grid = self.get_wilderness_chunk_map(chunk_x, chunk_y)
            for y in range(2, max(2, len(grid) - 2)):
                for x in range(2, max(2, len(grid[y]) - 2)):
                    if grid[y][x] != "~":
                        continue
                    world_x, world_y = self.wilderness_world_coords(chunk_x, chunk_y, x, y)
                    is_ocean = bool(self.wilderness_world_ocean_tile(world_x, world_y)) if hasattr(self, "wilderness_world_ocean_tile") else False
                    if bool(ocean) != is_ocean:
                        continue
                    return self.world_opportunity_world_point(
                        chunk_x, chunk_y, x, y,
                        "open coastal water" if ocean else "fresh water",
                        habitat="ocean" if ocean else "freshwater",
                    )
        return {}

    def world_opportunity_danger_targets(
        self, opportunity: Dict[str, object], quantity: int
    ) -> List[Dict[str, object]]:
        if not hasattr(self, "get_wilderness_random_combat_enemies"):
            return []
        origin_x, origin_y = self.world_opportunity_origin_chunk(opportunity)
        targets: List[Dict[str, object]] = []
        for radius in range(1, 6):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    chunk_x, chunk_y = origin_x + dx, origin_y + dy
                    for enemy in self.get_wilderness_random_combat_enemies(chunk_x, chunk_y, create=True):
                        if not isinstance(enemy, dict) or bool(enemy.get("defeated", False)):
                            continue
                        targets.append(self.world_opportunity_world_point(
                            chunk_x, chunk_y, int(enemy.get("x", 0)), int(enemy.get("y", 0)),
                            str(enemy.get("species", "hostile creature")),
                            enemy_id=str(enemy.get("id", "")), encounter_id=str(enemy.get("encounter_id", "")),
                        ))
                        if len(targets) >= max(1, int(quantity)):
                            return targets
        return targets

    def world_opportunity_linked_task_plan(
        self, opportunity: Dict[str, object]
    ) -> Dict[str, object]:
        quest = self.quest_record(str(opportunity.get("quest_id", "")))
        if not quest:
            return {}
        request_type = str(quest.get("request_type", ""))
        objectives = [dict(row) for row in quest.get("objectives", []) if isinstance(row, dict)]
        quantity = max(1, sum(max(1, int(row.get("target", 1) or 1)) for row in objectives))
        origin = self.world_opportunity_origin_chunk(opportunity)
        plan: Dict[str, object] = {
            "task_kind": request_type, "quantity": quantity, "task_waypoints": [],
        }
        if request_type == "neighbors":
            for objective in objectives:
                actor = self.world_opportunity_actor(str(objective.get("target_id", "")))
                if actor:
                    plan["task_waypoints"].append({
                        **self.world_opportunity_actor_position(actor),
                        "actor_id": str(actor.get("id", "")), "actor_name": str(actor.get("name", "a neighbor")),
                    })
        elif request_type == "survey":
            plan["task_waypoints"] = [
                dict(row.get("destination", {})) for row in objectives
                if isinstance(row.get("destination"), dict)
            ]
        elif request_type == "harvest":
            (chunk_x, chunk_y), site = self.world_opportunity_rural_site(opportunity)
            week = self.stronghold_cache_week_key() if hasattr(self, "stronghold_cache_week_key") else str(self.world_opportunity_day() // 7)
            harvested = _safe_dict(site.get("harvested_crop_tiles"))
            points = []
            for feature in site.get("features", []):
                if not isinstance(feature, dict) or str(feature.get("kind")) not in {"crop", "orchard_tree"}:
                    continue
                tile_key = f"{int(feature.get('x', 0))},{int(feature.get('y', 0))}"
                if str(harvested.get(tile_key, "")) == week:
                    continue
                points.append(self.world_opportunity_world_point(
                    chunk_x, chunk_y, int(feature.get("x", 0)), int(feature.get("y", 0)),
                    str(feature.get("name", "crop row")), rural_feature_key=tile_key,
                    item=str(feature.get("item", feature.get("name", "Produce"))),
                ))
            plan["task_waypoints"] = points[:quantity]
        elif request_type == "fish":
            target_tag = str(objectives[0].get("target_tag", "freshwater")) if objectives else "freshwater"
            target = self.world_opportunity_water_target(opportunity, ocean=target_tag == "ocean")
            if target:
                plan["task_waypoints"] = [target]
                plan["fish_tag"] = target_tag
        elif request_type == "salvage":
            target = self.world_opportunity_existing_salvage_target(quantity)
            if target:
                plan["task_waypoints"] = [target]
        elif request_type == "craft":
            (chunk_x, chunk_y), site = self.world_opportunity_rural_site(opportunity)
            workbench = next((
                row for row in site.get("features", [])
                if isinstance(row, dict) and str(row.get("kind")) == "workbench"
            ), None)
            _item, resources = self.world_opportunity_resource_candidates("Wood", 2, origin)
            if workbench and len(resources) >= 2:
                plan.update({
                    "item": "Wood", "material_quantity": 2,
                    "resource_positions": resources, "recipe_name": "Fence",
                    "workbench": self.world_opportunity_world_point(
                        chunk_x, chunk_y, int(workbench.get("x", 0)), int(workbench.get("y", 0)),
                        str(workbench.get("name", "workbench")), feature_kind="workbench",
                    ),
                    "task_waypoints": resources[:1],
                })
        elif request_type == "danger":
            plan["task_waypoints"] = self.world_opportunity_danger_targets(opportunity, quantity)
        elif request_type == "delivery" and objectives:
            item = str(objectives[0].get("item", ""))
            canonical = self.canonical_item_name(item) if hasattr(self, "canonical_item_name") else item
            _found, resources = self.world_opportunity_resource_candidates(canonical, quantity, origin)
            if len(resources) >= quantity and _found == canonical:
                plan.update({"item": canonical, "resource_positions": resources, "task_waypoints": resources[:quantity]})
            else:
                (chunk_x, chunk_y), site = self.world_opportunity_rural_site(opportunity)
                points = [
                    self.world_opportunity_world_point(
                        chunk_x, chunk_y, int(feature.get("x", 0)), int(feature.get("y", 0)),
                        str(feature.get("name", canonical)), rural_feature_key=f"{int(feature.get('x', 0))},{int(feature.get('y', 0))}", item=canonical,
                    )
                    for feature in site.get("features", [])
                    if isinstance(feature, dict)
                    and str(feature.get("kind")) in {"crop", "orchard_tree", "timber_stack", "drying_rack"}
                    and (self.canonical_item_name(str(feature.get("item", ""))) if hasattr(self, "canonical_item_name") else str(feature.get("item", ""))) == canonical
                ]
                if len(points) >= quantity:
                    plan.update({"item": canonical, "rural_delivery": True, "task_waypoints": points[:quantity]})
        waypoints = plan.get("task_waypoints", [])
        if not isinstance(waypoints, list) or not waypoints:
            return {}
        if request_type in {"harvest", "delivery", "danger"} and len(waypoints) < quantity:
            return {}
        return plan

    def ensure_procedural_town_opportunities(
        self, plan: Optional[Dict[str, object]] = None
    ) -> List[Dict[str, object]]:
        plan = dict(plan or self.current_procedural_town_plan() or {})
        if not plan or not hasattr(self, "procedural_settlement_residents"):
            return []
        chunk_x, chunk_y = int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))
        town_key = self.world_opportunity_town_key(plan)
        residents = [
            row for row in self.procedural_settlement_residents(chunk_x, chunk_y)
            if isinstance(row, dict)
            and str(row.get("age_group", row.get("life_stage", "Adult"))) not in {"Baby", "Toddler", "Young Child", "Child", "Teen"}
        ]
        residents.sort(
            key=lambda row: self.world_opportunity_stable_number(
                f"{town_key}:{self.world_opportunity_day() // 7}:{row.get('id')}"
            )
        )
        state = self.ensure_world_opportunity_state()
        linked: List[Dict[str, object]] = []
        for resident in residents[:3]:
            request = self.ensure_procedural_resident_request(chunk_x, chunk_y, str(resident.get("id", "")))
            quest_id = str(request.get("quest_id", ""))
            quest = self.quest_record(quest_id) if quest_id else {}
            if not quest:
                continue
            opportunity_id = f"world-link:{quest_id}"
            status = {
                "offered": "open", "active": "claimed_player", "ready": "claimed_player",
                "completed": "resolved", "abandoned": "withdrawn",
            }.get(str(quest.get("status", "offered")), "open")
            existing = state["opportunities"].get(opportunity_id)
            record = existing if isinstance(existing, dict) else {}
            if bool(record.get("resolved_by")) and str(record.get("status")) == "resolved":
                status = "resolved"
            giver_position = self.world_opportunity_actor_position(resident)
            request_type = str(quest.get("request_type", ""))
            record.update({
                "id": opportunity_id, "quest_id": quest_id,
                "kind": "linked_quest", "status": status,
                "title": str(quest.get("title", request.get("title", "Resident Request"))),
                "description": str(quest.get("description", request.get("description", ""))),
                "giver_id": str(resident.get("id", "")),
                "giver_name": str(resident.get("name", resident.get("given_name", "Resident"))),
                "giver_position": giver_position,
                "turn_in": giver_position,
                "reward_money": int(dict(quest.get("rewards", {}) or {}).get("money", 0) or 0),
                "created_day": int(quest.get("offered_day", self.world_opportunity_day()) or self.world_opportunity_day()),
                "town_key": town_key, "town_name": str(plan.get("name", "Wilderness Town")),
                "procedural_town_chunk": [chunk_x, chunk_y],
                "request_type": request_type,
                "objectives": [dict(row) for row in quest.get("objectives", []) if isinstance(row, dict)],
                "npc_competition_enabled": request_type in {
                    "delivery", "harvest", "fish", "craft", "danger", "salvage", "neighbors", "survey",
                },
                "linked_existing_quest": True,
                "history": list(record.get("history", []) or []),
            })
            if status == "resolved":
                record.setdefault("resolved_by", "player")
                record.setdefault("resolved_by_name", str(getattr(self.state, "player_name", "the player")))
            state["opportunities"][opportunity_id] = record
            linked.append(record)
        return linked

    def world_opportunity_board_menu(
        self, town_key: str = "main-town", board_title: str = "Town Notice Board"
    ):
        # Imported lazily because GameState sanitizes this module while the UI
        # module itself imports GameState.
        from ascii_farmstead_ui import MenuItem

        while True:
            records = [
                row for row in self.world_opportunities(("open", "claimed_player", "claimed_npc", "resolved"))
                if str(row.get("town_key", "main-town")) == str(town_key)
            ]
            records = records[-10:]
            items: List[MenuItem] = []
            for record in records:
                status = str(record.get("status", "open"))
                marker = {"open": "!", "claimed_player": ">", "claimed_npc": "@", "resolved": "x"}.get(status, " ")
                hint = {"open": "available", "claimed_player": "in your Quest Log", "claimed_npc": "another party is doing this", "resolved": "completed"}.get(status, status)
                items.append(MenuItem(label=f"{marker} {record.get('title')}", value=str(record.get("id")), enabled=True, hint=hint))
            if str(town_key) == "main-town":
                items.append(MenuItem(label="Town notices", value="notices", enabled=True))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select(board_title, items, 58, 24, return_back=True)
            if not choice or choice.value == MENU_BACK:
                self.set_message("Closed the notice board.")
                return
            if choice.value == "notices":
                self.vertical_panel_view("Town Notices", self.town_bulletin_lines(), 58, 24)
                continue
            opportunity = next((row for row in records if str(row.get("id")) == str(choice.value)), {})
            if not opportunity:
                continue
            actions = [MenuItem(label="Read posting", value="view", enabled=True)]
            if str(opportunity.get("status")) == "open":
                actions.append(MenuItem(label="Accept work", value="accept", enabled=True, hint="adds the same posting to your Quest Log"))
            if str(opportunity.get("status")) == "claimed_player":
                actions.append(MenuItem(label="Track quest", value="track", enabled=True))
            actions.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            action = self.vertical_panel_select(str(opportunity.get("title", "Posted Work")), actions, 56, 20, return_back=True)
            if not action or action.value == MENU_BACK:
                continue
            if action.value == "view":
                self.vertical_panel_view(str(opportunity.get("title", "Posted Work")), self.world_opportunity_board_lines(opportunity), 58, 24)
            elif action.value == "accept":
                self.accept_quest(str(opportunity.get("quest_id", "")))
            elif action.value == "track":
                self.track_quest(str(opportunity.get("quest_id", "")))

    def npc_adventure_inclination(self, npc: Dict[str, object]) -> str:
        record = self.npc_progression_record(npc)
        existing = str(record.get("adventure_inclination", ""))
        if existing:
            return existing
        role = str(npc.get("role", ""))
        score = self.world_opportunity_stable_number(self.npc_adventure_identity(npc)) % 100
        if role in {"Traveler", "Courier", "Sheriff", "Deputy", "Miner", "Hunter", "Wayfarer"}:
            score += 7
        inclination = "Homebound"
        if score >= 102:
            inclination = "Professional Adventurer"
        elif score >= 94:
            inclination = "Adventurous"
        elif score >= 80:
            inclination = "Occasional Traveler"
        elif score >= 58:
            inclination = "Local Helper"
        record["adventure_inclination"] = inclination
        return inclination

    def npc_can_lead_world_opportunity(self, npc: Dict[str, object]) -> bool:
        if bool(npc.get("deceased", False)):
            return False
        if str(npc.get("age_group", npc.get("life_stage", "Adult"))) in {"Baby", "Toddler", "Young Child", "Child", "Teen"}:
            return False
        return self.npc_adventure_inclination(npc) in {"Adventurous", "Professional Adventurer"}

    def npc_world_opportunity_party_members(
        self, leader: Dict[str, object], opportunity: Optional[Dict[str, object]] = None
    ) -> List[Dict[str, object]]:
        candidates = [leader]
        leader_id = str(leader.get("id", ""))
        generated_leader, generated_home = self.world_opportunity_procedural_actor_home(leader_id)
        if generated_leader and generated_home:
            population = self.procedural_settlement_population(*generated_home) if hasattr(self, "procedural_settlement_population") else None
            residents = _safe_dict(population.get("residents")) if isinstance(population, dict) else {}
            connections = _safe_dict(generated_leader.get("social_connections"))
            linked_ids = [str(connections.get("friend", ""))]
            linked_ids.extend(str(value) for value in connections.get("family", []) if str(value))
            for actor_id in linked_ids:
                actor = residents.get(actor_id)
                if not isinstance(actor, dict) or self.npc_world_opportunity_assignment(actor_id):
                    continue
                if self.npc_adventure_inclination(actor) in {
                    "Occasional Traveler", "Adventurous", "Professional Adventurer",
                }:
                    candidates.append(actor)
                    break
            return candidates[:3]
        links = self.regional_town_life_state().get("npc_social_links", {})
        friends: List[Tuple[int, Dict[str, object]]] = []
        for actor in self.active_town_npcs():
            actor_id = str(actor.get("id", ""))
            if not actor_id or actor_id == leader_id or self.npc_world_opportunity_assignment(actor_id):
                continue
            pair_id = "|".join(sorted((leader_id, actor_id)))
            link = links.get(pair_id, {}) if isinstance(links, dict) else {}
            score = int(link.get("score", 0) or 0) if isinstance(link, dict) else 0
            inclination = self.npc_adventure_inclination(actor)
            if score >= 3 and inclination in {"Occasional Traveler", "Adventurous", "Professional Adventurer"}:
                friends.append((score, actor))
        friends.sort(key=lambda pair: (-pair[0], str(pair[1].get("name", ""))))
        if friends:
            candidates.append(friends[0][1])
        return candidates[:3]

    def npc_world_opportunity_assignment(self, actor_id: str) -> Dict[str, object]:
        state = getattr(self.state, "world_opportunity_state", {})
        if not isinstance(state, dict):
            return {}
        for party in state.get("parties", {}).values():
            if isinstance(party, dict) and str(party.get("status", "")) == "active" and str(actor_id) in party.get("member_ids", []):
                return party
        return {}

    def world_opportunity_party_for(self, opportunity: Dict[str, object]) -> Dict[str, object]:
        state = getattr(self.state, "world_opportunity_state", {})
        return dict(state.get("parties", {}).get(str(opportunity.get("party_id", "")), {}) or {}) if isinstance(state, dict) else {}

    def npc_claim_world_opportunity(self, opportunity: Dict[str, object], leader: Dict[str, object]) -> Dict[str, object]:
        linked_plan = (
            self.world_opportunity_linked_task_plan(opportunity)
            if bool(opportunity.get("linked_existing_quest", False)) else {}
        )
        if bool(opportunity.get("linked_existing_quest", False)) and not linked_plan:
            opportunity["history"] = (
                list(opportunity.get("history", []))
                + ["No resident party found a physical route and source for this request yet."]
            )[-16:]
            return {}
        members = self.npc_world_opportunity_party_members(leader, opportunity)
        giver_position = dict(opportunity.get("giver_position", {}) or {})
        member_ids = [str(actor.get("id", "")) for actor in members]
        member_names = [str(actor.get("name", "Resident")) for actor in members]
        leader_id = member_ids[0]
        party_id = f"party:{opportunity['id']}:{leader_id}"
        kind = str(opportunity.get("kind", ""))
        if linked_plan:
            target = dict(list(linked_plan.get("task_waypoints", []))[0])
        elif kind == "gather_delivery":
            target = dict(opportunity.get("resource_positions", [{}])[0] if opportunity.get("resource_positions") else opportunity.get("target_position", {}))
        else:
            target = dict(opportunity.get("destination" if kind == "courier" else "target_position", {}) or {})
        inventories = {actor_id: {} for actor_id in member_ids}
        if kind == "courier":
            inventories[leader_id][str(opportunity.get("item", "Sealed Civic Parcel"))] = int(opportunity.get("quantity", 1))
        power = sum(max(1, int(self.npc_adventure_power(actor))) for actor in members)
        start_position = self.world_opportunity_actor_position(leader) if linked_plan else giver_position
        party = {
            "id": party_id, "opportunity_id": str(opportunity["id"]), "status": "active",
            "phase": "outbound", "leader_id": leader_id, "leader_name": member_names[0],
            "member_ids": member_ids, "member_names": member_names,
            "world_x": int(start_position.get("world_x", 0)), "world_y": int(start_position.get("world_y", 0)),
            "target_world_x": int(target.get("world_x", 0)), "target_world_y": int(target.get("world_y", 0)),
            "quantity": int(linked_plan.get("quantity", opportunity.get("quantity", 1))), "gathered": 0,
            "inventories": inventories, "minute_remainder": 0, "wait_minutes": 0,
            "activity": f"traveling toward {target.get('label', opportunity.get('title', 'the work site'))}",
            "history": [f"{', '.join(member_names)} left to undertake {opportunity.get('title', 'local work')}."],
            "task_kind": str(linked_plan.get("task_kind", "")),
            "task_waypoints": list(linked_plan.get("task_waypoints", []) or []),
            "task_index": 0, "action_progress": 0,
            "arrival_phase": {
                "delivery": "gathering", "harvest": "harvesting", "fish": "fishing",
                "craft": "gathering", "danger": "fighting", "salvage": "salvaging",
                "neighbors": "visiting", "survey": "surveying",
            }.get(str(linked_plan.get("task_kind", "")), "delivering"),
            "party_max_health": max(30, power * 2), "party_health": max(30, power * 2),
        }
        for field in ("item", "resource_positions", "material_quantity", "recipe_name", "workbench", "fish_tag", "rural_delivery"):
            if field in linked_plan:
                party[field] = linked_plan[field]
        self.world_opportunity_set_party_target(
            party,
            target,
            str(party.get("arrival_phase", "delivering")),
            travel_phase="task_travel" if linked_plan else "outbound",
        )
        state = self.ensure_world_opportunity_state()
        state["parties"][party_id] = party
        opportunity["status"] = "claimed_npc"
        opportunity["claimed_by_id"] = leader_id
        opportunity["claimed_by_name"] = member_names[0]
        opportunity["claimed_day"] = self.world_opportunity_day()
        opportunity["party_id"] = party_id
        opportunity["history"] = (list(opportunity.get("history", [])) + [f"{member_names[0]} accepted the posting{f' with {member_names[1]}' if len(member_names) > 1 else ''}."])[-16:]
        quest = self.quest_record(str(opportunity.get("quest_id", "")))
        if quest and str(quest.get("status", "")) == "offered":
            quest["status"] = "abandoned"
            quest["journal"] = (list(quest.get("journal", [])) + [f"{member_names[0]}'s party accepted this work first."])[-20:]
        return party

    def world_opportunity_find_next_resource(self, opportunity: Dict[str, object]) -> Dict[str, object]:
        item = str(opportunity.get("item", ""))
        for row in list(opportunity.get("resource_positions", []) or []):
            wx, wy = int(row.get("world_x", 0)), int(row.get("world_y", 0))
            cx, cy, x, y = self.home_world_chunk_from_world(wx, wy)
            grid = self.get_wilderness_chunk_map(cx, cy)
            if 0 <= y < len(grid) and 0 <= x < len(grid[y]) and self.world_opportunity_tile_item(grid[y][x], x, y, cx, cy) == item:
                return row
        found_item, rows = self.world_opportunity_resource_candidates(
            item, max(1, int(opportunity.get("quantity", 1)))
        )
        if rows and found_item and found_item != item:
            # The player can deplete or seasonally replace a posted resource
            # before a competing party reaches it. The party adapts to what is
            # physically present rather than receiving imaginary supplies.
            opportunity["item"] = found_item
            opportunity["history"] = (
                list(opportunity.get("history", []))
                + [f"The original patch was unavailable, so the party arranged to bring {found_item} instead."]
            )[-16:]
        opportunity["resource_positions"] = rows
        return dict(rows[0]) if rows else {}

    def world_opportunity_consume_resource(self, opportunity: Dict[str, object], position: Dict[str, object]) -> bool:
        wx, wy = int(position.get("world_x", 0)), int(position.get("world_y", 0))
        cx, cy, x, y = self.home_world_chunk_from_world(wx, wy)
        grid = self.get_wilderness_chunk_map(cx, cy)
        if not (0 <= y < len(grid) and 0 <= x < len(grid[y])):
            return False
        item = self.world_opportunity_tile_item(grid[y][x], x, y, cx, cy)
        if item != str(opportunity.get("item", "")):
            return False
        grid[y][x] = self.wilderness_world_biome_tile(wx, wy)
        return True

    def world_opportunity_consume_named_resource(
        self, item: str, position: Dict[str, object]
    ) -> bool:
        wx, wy = int(position.get("world_x", 0)), int(position.get("world_y", 0))
        chunk_x, chunk_y, x, y = self.home_world_chunk_from_world(wx, wy)
        grid = self.get_wilderness_chunk_map(chunk_x, chunk_y)
        if not (0 <= y < len(grid) and 0 <= x < len(grid[y])):
            return False
        actual = self.world_opportunity_tile_item(grid[y][x], x, y, chunk_x, chunk_y)
        canonical = self.canonical_item_name(item) if hasattr(self, "canonical_item_name") else str(item)
        if actual != canonical:
            return False
        grid[y][x] = self.wilderness_world_biome_tile(wx, wy)
        return True

    def world_opportunity_position_has_item(
        self, item: str, position: Dict[str, object]
    ) -> bool:
        wx, wy = int(position.get("world_x", 0)), int(position.get("world_y", 0))
        chunk_x, chunk_y, x, y = self.home_world_chunk_from_world(wx, wy)
        grid = self.get_wilderness_chunk_map(chunk_x, chunk_y)
        if not (0 <= y < len(grid) and 0 <= x < len(grid[y])):
            return False
        actual = self.world_opportunity_tile_item(grid[y][x], x, y, chunk_x, chunk_y)
        canonical = self.canonical_item_name(item) if hasattr(self, "canonical_item_name") else str(item)
        return actual == canonical

    def world_opportunity_party_inventory(self, party: Dict[str, object]) -> Dict[str, int]:
        inventories = party.setdefault("inventories", {})
        return inventories.setdefault(str(party.get("leader_id", "")), {})

    def world_opportunity_world_tile(self, world_x: int, world_y: int) -> str:
        chunk_x, chunk_y, local_x, local_y = self.home_world_chunk_from_world(
            int(world_x), int(world_y)
        )
        grid = self.get_wilderness_chunk_map(chunk_x, chunk_y)
        if 0 <= local_y < len(grid) and 0 <= local_x < len(grid[local_y]):
            return str(grid[local_y][local_x])
        return "#"

    def world_opportunity_world_walkable(self, world_x: int, world_y: int) -> bool:
        """Cheap, location-independent terrain check for off-screen residents."""
        tile = self.world_opportunity_world_tile(world_x, world_y)
        semantics = wilderness_tile_semantics(tile)
        if bool(semantics.get("walkable", False)):
            return True
        # Fresh inland water is a legitimate winter route. Ocean water remains
        # unsafe because these small work parties do not silently acquire boats.
        if tile == "~" and str(getattr(self.state, "season", "")) == "Winter":
            return not (
                bool(self.wilderness_world_ocean_tile(int(world_x), int(world_y)))
                if hasattr(self, "wilderness_world_ocean_tile") else False
            )
        return False

    @staticmethod
    def world_opportunity_target_needs_approach(target: Dict[str, object]) -> bool:
        return any(
            target.get(field)
            for field in (
                "actor_id", "enemy_id", "container_key", "rural_feature_key",
                "feature_kind", "habitat",
            )
        )

    def world_opportunity_approach_position(
        self,
        target: Dict[str, object],
        origin: Tuple[int, int],
        *,
        force_adjacent: bool = False,
    ) -> Tuple[int, int]:
        action_x = int(target.get("world_x", origin[0]))
        action_y = int(target.get("world_y", origin[1]))
        adjacent = bool(force_adjacent or self.world_opportunity_target_needs_approach(target))
        if not adjacent and self.world_opportunity_world_walkable(action_x, action_y):
            return action_x, action_y
        candidates: List[Tuple[int, int, int, int, int]] = []
        for radius in range(1, 7):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) != radius:
                        continue
                    world_x, world_y = action_x + dx, action_y + dy
                    if not self.world_opportunity_world_walkable(world_x, world_y):
                        continue
                    origin_distance = abs(world_x - int(origin[0])) + abs(world_y - int(origin[1]))
                    stable = self.world_opportunity_stable_number(
                        f"approach:{action_x},{action_y}:{world_x},{world_y}"
                    )
                    candidates.append((radius, origin_distance, stable, world_x, world_y))
            if candidates:
                break
        if candidates:
            candidates.sort()
            return int(candidates[0][3]), int(candidates[0][4])
        # A malformed legacy target must not strand the save migration. Keep the
        # old coordinate and let the route report that no safe approach was found.
        return action_x, action_y

    @staticmethod
    def world_opportunity_same_action_target(
        party: Dict[str, object], target: Dict[str, object]
    ) -> bool:
        action = _safe_dict(party.get("action_target"))
        return (
            int(action.get("world_x", 10**9)) == int(target.get("world_x", -10**9))
            and int(action.get("world_y", 10**9)) == int(target.get("world_y", -10**9))
        )

    def world_opportunity_set_party_target(
        self,
        party: Dict[str, object],
        target: Dict[str, object],
        arrival_phase: str,
        *,
        travel_phase: str = "task_travel",
        force_adjacent: bool = False,
    ) -> None:
        origin = (int(party.get("world_x", 0)), int(party.get("world_y", 0)))
        target = dict(target)
        target_x, target_y = self.world_opportunity_approach_position(
            target, origin, force_adjacent=force_adjacent
        )
        party["action_target"] = target
        party["target_world_x"] = target_x
        party["target_world_y"] = target_y
        party["target_label"] = str(target.get("label", "the next work site"))
        party["route_steps"] = []
        party["route_target_world_x"] = target_x
        party["route_target_world_y"] = target_y
        party["stuck_steps"] = 0
        party["phase"] = str(travel_phase)
        party["arrival_phase"] = str(arrival_phase)
        party["activity"] = f"traveling toward {party['target_label']}"

    def world_opportunity_next_task_waypoint(
        self, party: Dict[str, object], arrival_phase: str
    ) -> bool:
        party["task_index"] = int(party.get("task_index", 0)) + 1
        waypoints = list(party.get("task_waypoints", []) or [])
        index = int(party.get("task_index", 0))
        if index >= len(waypoints):
            return False
        self.world_opportunity_set_party_target(party, dict(waypoints[index]), arrival_phase)
        return True

    def world_opportunity_begin_return(
        self, party: Dict[str, object], opportunity: Dict[str, object]
    ) -> None:
        giver = _safe_dict(opportunity.get("giver_position"))
        self.world_opportunity_set_party_target(
            party, giver, "delivering", travel_phase="returning", force_adjacent=True
        )
        party["activity"] = f"returning to {opportunity.get('giver_name', 'the requester')}"

    def world_opportunity_harvest_rural_feature(
        self, waypoint: Dict[str, object]
    ) -> str:
        chunk_x, chunk_y = int(waypoint.get("chunk_x", 0)), int(waypoint.get("chunk_y", 0))
        site = self.rural_site_record(chunk_x, chunk_y) if hasattr(self, "rural_site_record") else {}
        tile_key = str(waypoint.get("rural_feature_key", ""))
        if not site or not tile_key:
            return ""
        week = self.stronghold_cache_week_key() if hasattr(self, "stronghold_cache_week_key") else str(self.world_opportunity_day() // 7)
        harvested = site.setdefault("harvested_crop_tiles", {})
        if str(harvested.get(tile_key, "")) == week:
            return ""
        harvested[tile_key] = week
        return str(waypoint.get("item", "Produce"))

    def world_opportunity_take_salvage(
        self, waypoint: Dict[str, object]
    ) -> str:
        containers = getattr(self.state, "world_containers", {})
        record = containers.get(str(waypoint.get("container_key", ""))) if isinstance(containers, dict) else None
        if not isinstance(record, dict):
            return ""
        contents = record.get("contents")
        if not isinstance(contents, dict):
            return ""
        item = next((name for name in sorted(contents) if int(contents.get(name, 0)) > 0), "")
        if not item:
            return ""
        contents[item] = int(contents.get(item, 0)) - 1
        record["contents"] = contents
        record["opened"] = True
        return item

    def world_opportunity_fish_name(
        self, party: Dict[str, object], opportunity: Dict[str, object]
    ) -> str:
        ocean = str(party.get("fish_tag", "freshwater")) == "ocean"
        candidates = []
        for name, data in FISH_DATA.items():
            if bool(data.get("junk", False)):
                continue
            habitats = {str(value).lower() for value in data.get("habitats", [])}
            if ocean != ("ocean" in habitats):
                continue
            seasons = {str(value) for value in data.get("seasons", [])}
            if seasons and str(getattr(self.state, "season", "")) not in seasons:
                continue
            candidates.append(str(name))
        if not candidates:
            candidates = [str(name) for name, data in FISH_DATA.items() if not bool(data.get("junk", False))]
        candidates.sort()
        index = self.world_opportunity_stable_number(
            f"{opportunity.get('id')}:{party.get('gathered', 0)}:{party.get('world_x')}:{party.get('world_y')}"
        ) % max(1, len(candidates))
        return candidates[index] if candidates else "Fish"

    def world_opportunity_enemy_record(
        self, waypoint: Dict[str, object]
    ) -> Dict[str, object]:
        chunk_x, chunk_y = int(waypoint.get("chunk_x", 0)), int(waypoint.get("chunk_y", 0))
        enemy_id = str(waypoint.get("enemy_id", ""))
        for enemy in self.get_wilderness_random_combat_enemies(chunk_x, chunk_y, create=False):
            if str(enemy.get("id", "")) == enemy_id:
                return enemy
        return {}

    def world_opportunity_fail_npc_party(
        self, party: Dict[str, object], opportunity: Dict[str, object], reason: str
    ) -> None:
        party["status"] = "failed"
        party["phase"] = "failed"
        party["activity"] = str(reason)
        party["history"] = (list(party.get("history", [])) + [str(reason)])[-20:]
        opportunity["status"] = "open"
        opportunity["party_id"] = ""
        opportunity["claimed_by_id"] = ""
        opportunity["claimed_by_name"] = ""
        opportunity["history"] = (list(opportunity.get("history", [])) + [str(reason)])[-16:]
        quest = self.quest_record(str(opportunity.get("quest_id", "")))
        if quest and str(quest.get("status", "")) == "abandoned":
            quest["status"] = "offered"
            quest["journal"] = (list(quest.get("journal", [])) + [str(reason)])[-20:]
        recovery_day = self.world_opportunity_day() + 2
        for actor_id in party.get("member_ids", []):
            actor = self.world_opportunity_actor(str(actor_id))
            if actor:
                self.npc_progression_record(actor)["recovery_until_day"] = recovery_day

    def advance_linked_world_opportunity_party(
        self, party: Dict[str, object], opportunity: Dict[str, object], minutes: int
    ) -> bool:
        phase = str(party.get("phase", "task_travel"))
        budget = int(party.get("minute_remainder", 0)) + max(0, int(minutes))
        steps, party["minute_remainder"] = divmod(budget, NPC_TRAVEL_STEP_MINUTES)
        if phase in {"task_travel", "returning"}:
            moved = self.world_opportunity_move_party(party, steps)
            if (int(party.get("world_x", 0)), int(party.get("world_y", 0))) != (
                int(party.get("target_world_x", 0)), int(party.get("target_world_y", 0))
            ):
                return bool(moved)
            if phase == "returning":
                party["phase"] = "delivering"
            else:
                party["phase"] = str(party.get("arrival_phase", "delivering"))
                party["action_progress"] = 0
            phase = str(party.get("phase", ""))
        waypoints = list(party.get("task_waypoints", []) or [])
        index = min(max(0, int(party.get("task_index", 0))), max(0, len(waypoints) - 1))
        waypoint = dict(waypoints[index]) if waypoints else {}
        inventory = self.world_opportunity_party_inventory(party)
        quantity = max(1, int(party.get("quantity", 1)))
        if phase == "gathering":
            item = str(party.get("item", opportunity.get("item", "Wood")))
            gathered_item = (
                self.world_opportunity_harvest_rural_feature(waypoint)
                if bool(party.get("rural_delivery", False)) else ""
            )
            if gathered_item or self.world_opportunity_consume_named_resource(item, waypoint):
                item = gathered_item or item
                inventory[item] = int(inventory.get(item, 0)) + 1
                party["gathered"] = int(party.get("gathered", 0)) + 1
                party["history"] = (list(party.get("history", [])) + [f"Gathered 1 {item} at ({waypoint.get('world_x')}, {waypoint.get('world_y')})."])[-20:]
            needed = int(party.get("material_quantity", quantity))
            if int(party.get("gathered", 0)) >= needed:
                if str(party.get("task_kind")) == "craft":
                    self.world_opportunity_set_party_target(party, _safe_dict(party.get("workbench")), "crafting")
                else:
                    self.world_opportunity_begin_return(party, opportunity)
            elif str(party.get("task_kind")) == "craft":
                next_target = next((
                    dict(row) for row in party.get("resource_positions", [])
                    if self.world_opportunity_position_has_item(item, row)
                ), None)
                if next_target:
                    self.world_opportunity_set_party_target(party, next_target, "gathering")
                else:
                    self.world_opportunity_fail_npc_party(party, opportunity, "The party returned after the needed materials were no longer present.")
            elif not self.world_opportunity_next_task_waypoint(party, "gathering"):
                self.world_opportunity_fail_npc_party(party, opportunity, "The party couldn't recover all of the requested supplies.")
            return True
        if phase == "harvesting":
            item = self.world_opportunity_harvest_rural_feature(waypoint)
            if item:
                inventory[item] = int(inventory.get(item, 0)) + 1
                party["gathered"] = int(party.get("gathered", 0)) + 1
                party["history"] = (list(party.get("history", [])) + [f"Harvested {item} from {waypoint.get('label', 'a crop row')}."])[-20:]
            if int(party.get("gathered", 0)) >= quantity:
                self.world_opportunity_begin_return(party, opportunity)
            elif not self.world_opportunity_next_task_waypoint(party, "harvesting"):
                self.world_opportunity_fail_npc_party(party, opportunity, "The crop rows had already been harvested.")
            return True
        if phase == "fishing":
            party["action_progress"] = int(party.get("action_progress", 0)) + max(0, int(minutes))
            party["activity"] = f"fishing from {waypoint.get('label', 'the water')}"
            while int(party.get("action_progress", 0)) >= 45 and int(party.get("gathered", 0)) < quantity:
                party["action_progress"] = int(party.get("action_progress", 0)) - 45
                fish = self.world_opportunity_fish_name(party, opportunity)
                inventory[fish] = int(inventory.get(fish, 0)) + 1
                party["gathered"] = int(party.get("gathered", 0)) + 1
                party["history"] = (list(party.get("history", [])) + [f"Caught 1 {fish} from {waypoint.get('label', 'the water')}."])[-20:]
            if int(party.get("gathered", 0)) >= quantity:
                self.world_opportunity_begin_return(party, opportunity)
            return True
        if phase == "salvaging":
            party["action_progress"] = int(party.get("action_progress", 0)) + max(0, int(minutes))
            while int(party.get("action_progress", 0)) >= 10 and int(party.get("gathered", 0)) < quantity:
                party["action_progress"] = int(party.get("action_progress", 0)) - 10
                item = self.world_opportunity_take_salvage(waypoint)
                if not item:
                    self.world_opportunity_fail_npc_party(party, opportunity, "The supply crate had already been emptied.")
                    return True
                inventory[item] = int(inventory.get(item, 0)) + 1
                party["gathered"] = int(party.get("gathered", 0)) + 1
                party["history"] = (list(party.get("history", [])) + [f"Recovered 1 {item} from {waypoint.get('label', 'a container')}."])[-20:]
            if int(party.get("gathered", 0)) >= quantity:
                self.world_opportunity_begin_return(party, opportunity)
            return True
        if phase == "crafting":
            recipe_name = str(party.get("recipe_name", "Fence"))
            recipe = CRAFTING_RECIPES.get(recipe_name, {})
            costs = _safe_dict(recipe.get("cost"))
            if any(int(inventory.get(item, 0)) < int(cost) for item, cost in costs.items()):
                self.world_opportunity_fail_npc_party(party, opportunity, "The party reached the workbench without the required materials.")
                return True
            for item, cost in costs.items():
                inventory[item] = int(inventory.get(item, 0)) - int(cost)
            output_name, output_quantity = recipe.get("output", (recipe_name, 1))
            inventory[str(output_name)] = int(inventory.get(str(output_name), 0)) + int(output_quantity)
            party["gathered"] = quantity
            party["history"] = (list(party.get("history", [])) + [f"Crafted {quantity_item_phrase(str(output_name), int(output_quantity))} at {waypoint.get('label', 'the workbench')}."])[-20:]
            self.world_opportunity_begin_return(party, opportunity)
            return True
        if phase == "visiting":
            target = self.world_opportunity_actor(str(waypoint.get("actor_id", "")))
            leader = self.world_opportunity_actor(str(party.get("leader_id", "")))
            if target and leader:
                target["memories"] = (list(target.get("memories", [])) + [f"{leader.get('name', 'A neighbor')} checked in while helping {opportunity.get('giver_name', 'a resident')}."])[-30:]
                leader["memories"] = (list(leader.get("memories", [])) + [f"Spoke with {target.get('name', 'a neighbor')} for {opportunity.get('giver_name', 'a resident')}."])[-30:]
                party["history"] = (list(party.get("history", [])) + [f"Checked in with {target.get('name', 'a neighbor')} in person."])[-20:]
                party["gathered"] = int(party.get("gathered", 0)) + 1
            if not self.world_opportunity_next_task_waypoint(party, "visiting"):
                self.world_opportunity_begin_return(party, opportunity)
            return True
        if phase == "surveying":
            party["action_progress"] = int(party.get("action_progress", 0)) + max(0, int(minutes))
            party["activity"] = f"walking and recording conditions at {waypoint.get('label', 'the survey point')}"
            if int(party.get("action_progress", 0)) < 30:
                return True
            party["history"] = (list(party.get("history", [])) + [f"Surveyed {waypoint.get('label', 'the route')} at ({waypoint.get('world_x')}, {waypoint.get('world_y')})."])[-20:]
            party["gathered"] = int(party.get("gathered", 0)) + 1
            party["action_progress"] = 0
            if not self.world_opportunity_next_task_waypoint(party, "surveying"):
                self.world_opportunity_begin_return(party, opportunity)
            return True
        if phase == "fighting":
            enemy = self.world_opportunity_enemy_record(waypoint)
            if enemy and not bool(enemy.get("defeated", False)):
                level = max(1, int(enemy.get("floor", 1)))
                enemy.setdefault("max_hp", 8 + level * 2)
                enemy.setdefault("hp", int(enemy.get("max_hp", 10)))
                enemy.setdefault("attack", 2 + level // 2)
                enemy.setdefault("defense", level // 4)
                members = [self.world_opportunity_actor(str(actor_id)) for actor_id in party.get("member_ids", [])]
                power = sum(self.npc_adventure_power(actor) for actor in members if actor)
                damage = max(2, power // max(2, len(members) + 1) - int(enemy.get("defense", 0)))
                enemy["hp"] = max(0, int(enemy.get("hp", 1)) - damage)
                party["party_health"] = max(0, int(party.get("party_health", 1)) - max(1, int(enemy.get("attack", 2)) - len(members)))
                party["activity"] = f"fighting {enemy.get('species', 'a hostile creature')} at the actual encounter site"
                if int(party.get("party_health", 0)) <= 0:
                    self.world_opportunity_fail_npc_party(party, opportunity, "The party withdrew injured after the hostile group proved too strong.")
                    return True
                if int(enemy.get("hp", 0)) <= 0:
                    enemy["defeated"] = True
                    enemy["alert"] = False
                    party["gathered"] = int(party.get("gathered", 0)) + 1
                    party["history"] = (list(party.get("history", [])) + [f"Defeated {enemy.get('species', 'a hostile creature')} at ({waypoint.get('world_x')}, {waypoint.get('world_y')})."])[-20:]
                    for actor in members:
                        if actor:
                            self.npc_progression_record(actor)["victories"] = int(self.npc_progression_record(actor).get("victories", 0)) + 1
                    record = self.wilderness_random_combat_record(int(waypoint.get("chunk_x", 0)), int(waypoint.get("chunk_y", 0)), create=False)
                    if record and not self.get_wilderness_random_combat_enemies(int(waypoint.get("chunk_x", 0)), int(waypoint.get("chunk_y", 0)), create=False):
                        record["resolved"] = True
                        record["resolved_by"] = "npc_party"
            if int(party.get("gathered", 0)) >= quantity:
                self.world_opportunity_begin_return(party, opportunity)
            elif (not enemy or bool(enemy.get("defeated", False))) and not self.world_opportunity_next_task_waypoint(party, "fighting"):
                self.world_opportunity_begin_return(party, opportunity)
            return True
        if phase == "delivering":
            if str(party.get("task_kind")) in {"delivery", "harvest", "fish", "craft", "salvage"}:
                inventory.clear()
            self.world_opportunity_complete_npc_party(party, opportunity)
            return True
        return False

    def world_opportunity_move_party(self, party: Dict[str, object], steps: int) -> int:
        """Move a saved party through real cardinal terrain, favoring roads."""
        moved = 0
        for _ in range(max(0, int(steps))):
            x, y = int(party.get("world_x", 0)), int(party.get("world_y", 0))
            tx, ty = int(party.get("target_world_x", x)), int(party.get("target_world_y", y))
            if (x, y) == (tx, ty):
                break
            route_target = (
                int(party.get("route_target_world_x", tx)),
                int(party.get("route_target_world_y", ty)),
            )
            route = list(party.get("route_steps", []) or [])
            if route_target != (tx, ty):
                route = []
            if route:
                next_step = dict(route[0])
                next_position = (
                    int(next_step.get("world_x", x)),
                    int(next_step.get("world_y", y)),
                )
                if (
                    abs(next_position[0] - x) + abs(next_position[1] - y) != 1
                    or not self.world_opportunity_world_walkable(*next_position)
                ):
                    route = []
            if not route:
                route = self.world_opportunity_route_segment((x, y), (tx, ty))
                party["route_target_world_x"], party["route_target_world_y"] = tx, ty
            if not route:
                party["stuck_steps"] = int(party.get("stuck_steps", 0)) + 1
                party["activity"] = f"finding a safe way around the terrain toward {party.get('target_label', 'the work site')}"
                party["route_steps"] = []
                break
            next_step = dict(route.pop(0))
            x, y = int(next_step["world_x"]), int(next_step["world_y"])
            party["world_x"], party["world_y"] = x, y
            party["route_steps"] = route
            party["stuck_steps"] = 0
            tile = self.world_opportunity_world_tile(x, y)
            party["travel_surface"] = (
                "a bridge" if tile == "=" else
                "a maintained road" if tile == ":" else
                "open country"
            )
            moved += 1
        return moved

    def world_opportunity_route_segment(
        self,
        start: Tuple[int, int],
        target: Tuple[int, int],
        max_nodes: int = 900,
    ) -> List[Dict[str, int]]:
        """Return a bounded A* segment without simulating every distant tile at once."""
        start = (int(start[0]), int(start[1]))
        target = (int(target[0]), int(target[1]))
        if start == target:
            return []
        tile_cache: Dict[Tuple[int, int], str] = {}

        def tile_at(position: Tuple[int, int]) -> str:
            if position not in tile_cache:
                tile_cache[position] = self.world_opportunity_world_tile(*position)
            return tile_cache[position]

        def walkable(position: Tuple[int, int]) -> bool:
            if position == start:
                return True
            tile = tile_at(position)
            semantics = wilderness_tile_semantics(tile)
            if bool(semantics.get("walkable", False)):
                return True
            if tile == "~" and str(getattr(self.state, "season", "")) == "Winter":
                return not (
                    bool(self.wilderness_world_ocean_tile(*position))
                    if hasattr(self, "wilderness_world_ocean_tile") else False
                )
            return False

        def movement_cost(position: Tuple[int, int]) -> float:
            tile = tile_at(position)
            if tile == "=":
                return 0.32
            if tile == ":":
                return 0.42
            if tile in {".", ","}:
                return 0.90
            if tile in {"x", "r", "`", '"', "["}:
                return 1.30
            return 1.08

        def distance(position: Tuple[int, int]) -> int:
            return abs(position[0] - target[0]) + abs(position[1] - target[1])

        frontier: List[Tuple[float, int, Tuple[int, int]]] = []
        heapq.heappush(frontier, (distance(start) * 0.55, 0, start))
        came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
        costs: Dict[Tuple[int, int], float] = {start: 0.0}
        best = start
        best_rank = (distance(start), 0.0)
        serial = 0
        while frontier and len(came_from) < max(32, int(max_nodes)):
            _priority, _serial, current = heapq.heappop(frontier)
            if current == target:
                best = current
                break
            for step_x, step_y in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                candidate = (current[0] + step_x, current[1] + step_y)
                if not walkable(candidate):
                    continue
                new_cost = costs[current] + movement_cost(candidate)
                if new_cost >= costs.get(candidate, float("inf")):
                    continue
                costs[candidate] = new_cost
                came_from[candidate] = current
                serial += 1
                remaining = distance(candidate)
                heapq.heappush(frontier, (new_cost + remaining * 0.55, serial, candidate))
                rank = (remaining, new_cost)
                if rank < best_rank:
                    best, best_rank = candidate, rank
        if best == start:
            return []
        path: List[Tuple[int, int]] = []
        cursor = best
        while cursor != start:
            path.append(cursor)
            previous = came_from.get(cursor)
            if previous is None:
                return []
            cursor = previous
        path.reverse()
        return [
            {"world_x": world_x, "world_y": world_y}
            for world_x, world_y in path[:NPC_ROUTE_SEGMENT_LIMIT]
        ]

    def world_opportunity_complete_npc_party(self, party: Dict[str, object], opportunity: Dict[str, object]) -> None:
        leader = self.world_opportunity_actor(str(party.get("leader_id", ""))) or {
            "id": str(party.get("leader_id", "")), "name": str(party.get("leader_name", "Resident")), "role": "Traveler",
        }
        party["status"] = "completed"
        party["phase"] = "completed"
        party["activity"] = "finished the work and returned to ordinary life"
        opportunity["status"] = "resolved"
        opportunity["resolved_by"] = "npc_party"
        opportunity["resolved_by_name"] = str(party.get("leader_name", "A resident"))
        opportunity["resolved_day"] = self.world_opportunity_day()
        outcome = f"{party.get('leader_name', 'A resident')}'s party physically completed {opportunity.get('title', 'the posted work')}."
        opportunity["history"] = (list(opportunity.get("history", [])) + [outcome])[-16:]
        party["history"] = (list(party.get("history", [])) + [outcome])[-20:]
        if bool(opportunity.get("linked_existing_quest", False)):
            quest = self.quest_record(str(opportunity.get("quest_id", "")))
            if quest:
                quest["status"] = "completed"
                quest["completed_by_npc"] = True
                quest["completed_by_name"] = str(party.get("leader_name", "A resident"))
                quest["completed_day"] = self.world_opportunity_day()
                for objective in quest.get("objectives", []):
                    if isinstance(objective, dict):
                        objective["current"] = max(1, int(objective.get("target", 1) or 1))
                        objective["complete"] = True
                quest["journal"] = (
                    list(quest.get("journal", []))
                    + [f"{party.get('leader_name', 'A resident')}'s party completed this request in the world."]
                )[-20:]
            giver = self.world_opportunity_actor(str(opportunity.get("giver_id", "")))
            if giver:
                if quest and hasattr(self, "procedural_request_summary"):
                    giver["active_request"] = self.procedural_request_summary(quest)
                completed_ids = [str(value) for value in giver.get("completed_request_ids", [])]
                completed_ids.append(str(opportunity.get("quest_id", "")))
                giver["completed_request_ids"] = list(dict.fromkeys(completed_ids))[-40:]
                giver["memories"] = (
                    list(giver.get("memories", []))
                    + [f"{party.get('leader_name', 'A resident')}'s party completed {opportunity.get('title', 'a local request')}."]
                )[-30:]
        for actor_id in party.get("member_ids", []):
            actor = self.world_opportunity_actor(str(actor_id)) or {"id": str(actor_id), "name": str(actor_id), "role": "Traveler"}
            record = self.npc_progression_record(actor)
            record["journeys"] = int(record.get("journeys", 0)) + 1
            record["earnings"] = int(record.get("earnings", 0)) + int(opportunity.get("reward_money", 0)) // max(1, len(party.get("member_ids", [])))
            record["last_outcome"] = f"completed {opportunity.get('title', 'posted work')} with real fieldwork"
            record["history"] = (list(record.get("history", [])) + [outcome])[-8:]
            self.award_npc_adventure_xp(actor, 25 + 5 * len(party.get("member_ids", [])))
        state = self.ensure_world_opportunity_state()
        state["event_log"] = (list(state.get("event_log", [])) + [outcome])[-WORLD_OPPORTUNITY_HISTORY_CAP:]

    def advance_world_opportunity_party(self, party: Dict[str, object], minutes: int) -> bool:
        state = self.ensure_world_opportunity_state()
        opportunity = state["opportunities"].get(str(party.get("opportunity_id", "")), {})
        if not opportunity or str(party.get("status")) != "active":
            return False
        if bool(opportunity.get("linked_existing_quest", False)):
            return self.advance_linked_world_opportunity_party(party, opportunity, minutes)
        budget = int(party.get("minute_remainder", 0)) + max(0, int(minutes))
        steps, party["minute_remainder"] = divmod(budget, NPC_TRAVEL_STEP_MINUTES)
        phase = str(party.get("phase", "outbound"))
        if phase in {"outbound", "returning"}:
            moved = self.world_opportunity_move_party(party, steps)
            if moved:
                party["activity"] = "traveling through the world toward the work site" if phase == "outbound" else f"returning to {opportunity.get('giver_name', 'the requester')}"
            if (int(party.get("world_x", 0)), int(party.get("world_y", 0))) != (int(party.get("target_world_x", 0)), int(party.get("target_world_y", 0))):
                return bool(moved)
            kind = str(opportunity.get("kind", ""))
            if phase == "returning":
                party["phase"] = "delivering"
            elif kind == "gather_delivery":
                party["phase"] = "gathering"
            elif kind == "survey":
                party["phase"] = "surveying"
                party["wait_minutes"] = 30
            else:
                party["phase"] = "delivering"
        phase = str(party.get("phase", ""))
        if phase == "gathering":
            target = self.world_opportunity_find_next_resource(opportunity)
            if not target:
                party["activity"] = f"searching the terrain for {opportunity.get('item', 'the requested forage')}"
                return False
            if not self.world_opportunity_same_action_target(party, target):
                self.world_opportunity_set_party_target(
                    party, target, "gathering", travel_phase="outbound"
                )
                party["activity"] = f"walking to a real patch of {opportunity.get('item', 'forage')}"
                return True
            if self.world_opportunity_consume_resource(opportunity, target):
                item = str(opportunity.get("item", ""))
                inventory = party["inventories"].setdefault(str(party.get("leader_id", "")), {})
                inventory[item] = int(inventory.get(item, 0)) + 1
                party["gathered"] = int(party.get("gathered", 0)) + 1
                party["history"] = (list(party.get("history", [])) + [f"Gathered 1 {item} at ({target.get('world_x')}, {target.get('world_y')})."])[-20:]
            if int(party.get("gathered", 0)) >= int(party.get("quantity", 1)):
                self.world_opportunity_begin_return(party, opportunity)
            else:
                next_target = self.world_opportunity_find_next_resource(opportunity)
                if next_target:
                    self.world_opportunity_set_party_target(
                        party, next_target, "gathering", travel_phase="outbound"
                    )
            return True
        if phase == "surveying":
            party["wait_minutes"] = max(0, int(party.get("wait_minutes", 0)) - int(minutes))
            party["activity"] = "walking the survey site and recording the actual route condition"
            if int(party.get("wait_minutes", 0)) <= 0:
                self.world_opportunity_begin_return(party, opportunity)
            return True
        if phase == "delivering":
            if str(opportunity.get("kind")) == "gather_delivery":
                inventory = party["inventories"].setdefault(str(party.get("leader_id", "")), {})
                needed = int(opportunity.get("quantity", 1))
                if sum(max(0, int(value)) for value in inventory.values()) < needed:
                    party["phase"] = "gathering"
                    return True
                for item in list(inventory):
                    moved = min(needed, max(0, int(inventory.get(item, 0))))
                    inventory[item] = int(inventory.get(item, 0)) - moved
                    needed -= moved
                    if needed <= 0:
                        break
            elif str(opportunity.get("kind")) == "courier":
                inventory = party["inventories"].setdefault(str(party.get("leader_id", "")), {})
                cargo = str(opportunity.get("item", "Sealed Civic Parcel"))
                if int(inventory.get(cargo, 0)) < int(opportunity.get("quantity", 1)):
                    party["activity"] = "looking for the parcel that must physically reach its recipient"
                    return False
                inventory[cargo] = max(
                    0,
                    int(inventory.get(cargo, 0)) - int(opportunity.get("quantity", 1)),
                )
            self.world_opportunity_complete_npc_party(party, opportunity)
            return True
        return False

    def world_opportunity_eligible_leaders(
        self, opportunity: Dict[str, object]
    ) -> List[Dict[str, object]]:
        raw_home = opportunity.get("procedural_town_chunk", [])
        if isinstance(raw_home, (list, tuple)) and len(raw_home) >= 2:
            population = (
                self.procedural_settlement_population(int(raw_home[0]), int(raw_home[1]))
                if hasattr(self, "procedural_settlement_population") else None
            )
            candidates = list(_safe_dict(population.get("residents")).values()) if isinstance(population, dict) else []
        else:
            candidates = list(self.active_town_npcs())
        active_abstract = self.regional_town_life_state().get("resident_trips", {})
        giver_id = str(opportunity.get("giver_id", ""))
        return [
            npc for npc in candidates
            if isinstance(npc, dict)
            and str(npc.get("id", "")) != giver_id
            and self.npc_can_lead_world_opportunity(npc)
            and not self.npc_world_opportunity_assignment(str(npc.get("id", "")))
            and str(npc.get("id", "")) not in active_abstract
        ]

    def world_opportunity_try_npc_claim(self) -> bool:
        state = self.ensure_world_opportunity_state()
        today = self.world_opportunity_day()
        if int(state.get("last_claim_day", 0)) == today:
            return False
        active_parties = [
            party for party in state.get("parties", {}).values()
            if isinstance(party, dict) and str(party.get("status", "")) == "active"
        ]
        if len(active_parties) >= WORLD_OPPORTUNITY_ACTIVE_PARTY_CAP:
            return False
        active_towns = {
            str(_safe_dict(state.get("opportunities")).get(
                str(party.get("opportunity_id", "")), {}
            ).get("town_key", "main-town"))
            for party in active_parties
        }
        open_records = [
            row for row in self.world_opportunities(("open",))
            if today - int(row.get("created_day", today)) >= 2
            and bool(row.get("npc_competition_enabled", True))
            and str(row.get("town_key", "main-town")) not in active_towns
        ]
        if not open_records:
            return False
        open_records.sort(key=lambda row: self.world_opportunity_stable_number(f"claim:{today}:{row.get('id')}"))
        for opportunity in open_records:
            leaders = self.world_opportunity_eligible_leaders(opportunity)
            leaders.sort(key=lambda npc: self.world_opportunity_stable_number(f"{today}:{npc.get('id')}"))
            for leader in leaders:
                if self.npc_claim_world_opportunity(opportunity, leader):
                    state["last_claim_day"] = today
                    return True
        return False

    def world_opportunity_periodic_refresh(self) -> bool:
        state = self.ensure_world_opportunity_state()
        today = self.world_opportunity_day()
        last_refresh = int(state.get("last_refresh_day", 0))
        open_count = len([
            row for row in self.world_opportunities(("open", "claimed_player", "claimed_npc"))
            if str(row.get("town_key", "main-town")) == "main-town"
        ])
        if today - last_refresh < 7 or open_count >= WORLD_OPPORTUNITY_OPEN_CAP:
            return False
        serial = int(state.get("next_serial", 1))
        state["next_serial"] = serial + 1
        kind = ("gather_delivery", "courier", "survey")[serial % 3]
        opportunity = self.build_world_opportunity(kind, serial)
        state["opportunities"][opportunity["id"]] = opportunity
        state["last_refresh_day"] = today
        state["event_log"] = (list(state.get("event_log", [])) + [f"{opportunity['giver_name']} posted {opportunity['title']}."])[-WORLD_OPPORTUNITY_HISTORY_CAP:]
        self.sync_world_opportunity_quests()
        return True

    def update_world_opportunities(self, minutes: int = 0) -> None:
        state = self.ensure_world_opportunity_state()
        moved = False
        for party in list(state.get("parties", {}).values()):
            if isinstance(party, dict) and str(party.get("status", "")) == "active":
                moved = self.advance_world_opportunity_party(party, minutes) or moved
        self.world_opportunity_periodic_refresh()
        self.world_opportunity_try_npc_claim()
        self.sync_world_opportunity_quests()
        if moved and hasattr(self, "_wilderness_travelers") and isinstance(self._wilderness_travelers, dict):
            self._wilderness_travelers.clear()

    def world_opportunity_party_display_positions(
        self,
        world_x: int,
        world_y: int,
        member_count: int,
    ) -> List[Tuple[int, int]]:
        chunk_x, chunk_y, local_x, local_y = self.home_world_chunk_from_world(world_x, world_y)
        candidates: List[Tuple[int, int, int, int]] = []
        for radius in range(0, 6):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) != radius:
                        continue
                    x, y = local_x + dx, local_y + dy
                    if not (0 <= x < 86 and 0 <= y < 38):
                        continue
                    candidate_world_x, candidate_world_y = self.wilderness_world_coords(
                        chunk_x, chunk_y, x, y
                    )
                    if not self.world_opportunity_world_walkable(candidate_world_x, candidate_world_y):
                        continue
                    stable = self.world_opportunity_stable_number(
                        f"party-display:{world_x},{world_y}:{x},{y}"
                    )
                    candidates.append((radius, stable, x, y))
            if len(candidates) >= max(1, int(member_count)):
                break
        candidates.sort()
        return [(int(row[2]), int(row[3])) for row in candidates[:max(1, int(member_count))]]

    def world_opportunity_party_detail_lines(self, party_id: str) -> List[str]:
        state = self.ensure_world_opportunity_state()
        party = _safe_dict(_safe_dict(state.get("parties")).get(str(party_id)))
        if not party:
            return ["That work party is no longer traveling."]
        opportunity = _safe_dict(
            _safe_dict(state.get("opportunities")).get(str(party.get("opportunity_id", "")))
        )
        carried: Dict[str, int] = {}
        for inventory in _safe_dict(party.get("inventories")).values():
            for item, quantity in _safe_dict(inventory).items():
                carried[str(item)] = int(carried.get(str(item), 0)) + max(0, int(quantity))
        target_x = int(party.get("target_world_x", party.get("world_x", 0)))
        target_y = int(party.get("target_world_y", party.get("world_y", 0)))
        remaining = abs(int(party.get("world_x", 0)) - target_x) + abs(int(party.get("world_y", 0)) - target_y)
        lines = [
            str(opportunity.get("title", "Posted Work")),
            str(opportunity.get("description", "A local resident posted this work.")),
            "",
            f"Party: {', '.join(str(name) for name in party.get('member_names', []) if str(name))}",
            f"Current work: {party.get('activity', 'undertaking the request')}",
            f"Travel surface: {party.get('travel_surface', 'local paths')}",
            f"Next stop: {party.get('target_label', 'the work site')} at ({target_x}, {target_y})",
            f"Distance remaining: {remaining} tiles",
            f"Progress: {int(party.get('gathered', 0))}/{max(1, int(party.get('quantity', 1)))}",
            f"Reward on return: {int(opportunity.get('reward_money', 0))}g",
        ]
        if carried:
            lines.extend([
                "",
                "Carried supplies:",
                *[
                    f"- {quantity_item_phrase(quantity, item)}"
                    for item, quantity in sorted(carried.items()) if quantity > 0
                ],
            ])
        history = [str(row) for row in party.get("history", []) if str(row).strip()][-4:]
        if history:
            lines.extend(["", "Recent progress:", *[f"- {row}" for row in history]])
        return lines

    def world_opportunity_travelers_for_chunk(self, chunk_x: int, chunk_y: int) -> List[Dict[str, object]]:
        state = self.ensure_world_opportunity_state()
        results: List[Dict[str, object]] = []
        for party in state.get("parties", {}).values():
            if not isinstance(party, dict) or str(party.get("status", "")) != "active":
                continue
            cx, cy, local_x, local_y = self.home_world_chunk_from_world(int(party.get("world_x", 0)), int(party.get("world_y", 0)))
            if (cx, cy) != (int(chunk_x), int(chunk_y)):
                continue
            member_ids = [str(value) for value in party.get("member_ids", []) if str(value)]
            positions = self.world_opportunity_party_display_positions(
                int(party.get("world_x", 0)), int(party.get("world_y", 0)), len(member_ids)
            )
            opportunity = _safe_dict(
                _safe_dict(state.get("opportunities")).get(str(party.get("opportunity_id", "")))
            )
            for index, actor_id in enumerate(party.get("member_ids", [])):
                member_names = list(party.get("member_names", []) or [])
                actor = self.world_opportunity_actor(str(actor_id)) or {
                    "id": str(actor_id),
                    "name": member_names[index] if index < len(member_names) else "Resident",
                    "role": "Traveler",
                }
                progression = self.npc_progression_record(actor)
                display_x, display_y = positions[index] if index < len(positions) else (local_x, local_y)
                results.append({
                    **dict(actor), "id": str(actor_id),
                    "preferred_x": int(display_x), "preferred_y": int(display_y),
                    "x": int(display_x), "y": int(display_y),
                    "chunk_x": int(chunk_x), "chunk_y": int(chunk_y),
                    "world_opportunity_party": True, "resident_adventure_trip": True,
                    "regional_circulation": True, "static_actor": True,
                    "activity": str(party.get("activity", "undertaking posted work")),
                    "opportunity_id": str(party.get("opportunity_id", "")),
                    "party_id": str(party.get("id", "")),
                    "opportunity_title": str(opportunity.get("title", "Posted Work")),
                    "opportunity_reward": int(opportunity.get("reward_money", 0)),
                    "party_members": list(party.get("member_names", []) or []),
                    "party_phase": str(party.get("phase", "traveling")),
                    "party_progress": f"{int(party.get('gathered', 0))}/{max(1, int(party.get('quantity', 1)))}",
                    "route_destination_name": str(party.get("target_label", "the next work site")),
                    "route_destination_world_x": int(party.get("target_world_x", party.get("world_x", 0))),
                    "route_destination_world_y": int(party.get("target_world_y", party.get("world_y", 0))),
                    "route_condition": str(party.get("travel_surface", "local paths")).title(),
                    "adventure_level": int(progression.get("level", 1)),
                    "adventure_weapon": str(progression.get("weapon", "Travel Gear")),
                })
        return results

    def world_opportunity_actor_away_entry(self, actor_id: str) -> Dict[str, object]:
        party = self.npc_world_opportunity_assignment(actor_id)
        if not party:
            return {}
        opportunity = self.ensure_world_opportunity_state()["opportunities"].get(str(party.get("opportunity_id", "")), {})
        return {
            "away": str(opportunity.get("title", "posted fieldwork")),
            "activity": str(party.get("activity", "undertaking posted work in the world")),
        }

    def world_opportunity_adventure_line(self, npc: Dict[str, object]) -> str:
        party = self.npc_world_opportunity_assignment(str(npc.get("id", "")))
        if party:
            opportunity = self.ensure_world_opportunity_state()["opportunities"].get(str(party.get("opportunity_id", "")), {})
            return f'"I took {opportunity.get("title", "a posted job")}. Right now, we are {str(party.get("activity", "working on it")).lower()}."'
        record = self.npc_progression_record(npc)
        history = list(record.get("history", []) or [])
        if history:
            return f'"{history[-1]} It was real work, not just something that happened while I was offscreen."'
        return ""

    def world_opportunity_journal_lines(self) -> List[str]:
        records = self.world_opportunities(("open", "claimed_player", "claimed_npc"))
        lines = ["", "Persistent local opportunities:"]
        if not records:
            return lines + ["- No unresolved postings."]
        for record in records[:8]:
            status = str(record.get("status", "open")).replace("_", " ")
            lines.append(f"- {record.get('title')}: {status}; requester {record.get('giver_name')}")
        return lines
