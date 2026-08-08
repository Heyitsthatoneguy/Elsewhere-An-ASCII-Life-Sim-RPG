"""Unified quests, tracked objectives, planned events, and temporary participants.

Existing errands, resident requests, bounties, and contracts remain valid.  This
module provides the common player-facing record they can migrate into without
requiring every older subsystem to be rewritten at once.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from ascii_farmstead_actors import manhattan_distance, shortest_path_step
from ascii_farmstead_data import MENU_BACK, TOWN_DOORS
from ascii_farmstead_support import C, colorize
from ascii_farmstead_ui import MenuItem


QUEST_ACTIVE_STATUSES = {"offered", "active", "ready"}
QUEST_CATEGORIES = {
    "Personal", "Relationships", "Household", "Town", "Politics",
    "Wilderness", "Business", "Bounties", "General",
}


class QuestSystemMixin:
    """Persistent common quest/event behavior for a FarmGame-like object."""

    # ------------------------------------------------------------------
    # Quest records

    def ensure_quest_state(self) -> Dict[str, Dict[str, object]]:
        store = getattr(self.state, "quest_records", None)
        if not isinstance(store, dict):
            store = {}
            self.state.quest_records = store
        clean: Dict[str, Dict[str, object]] = {}
        for raw_id, raw in store.items():
            if not isinstance(raw, dict):
                continue
            quest_id = str(raw.get("id", raw_id) or raw_id)
            if not quest_id:
                continue
            status = str(raw.get("status", "offered") or "offered").lower()
            if status not in {"offered", "active", "ready", "completed", "abandoned"}:
                status = "offered"
            objectives = []
            for index, objective in enumerate(raw.get("objectives", []) or []):
                if not isinstance(objective, dict):
                    continue
                row = dict(objective)
                row["id"] = str(row.get("id", f"objective:{index}"))
                row["kind"] = str(row.get("kind", "manual") or "manual").lower()
                row["description"] = str(row.get("description", "Complete the objective.") or "Complete the objective.")
                row["current"] = max(0, int(row.get("current", 0) or 0))
                row["target"] = max(1, int(row.get("target", 1) or 1))
                row["complete"] = bool(row.get("complete", False))
                if not isinstance(row.get("destination", {}), dict):
                    row["destination"] = {}
                objectives.append(row)
            if not objectives:
                objectives = [{
                    "id": "objective:0", "kind": "manual",
                    "description": str(raw.get("description", "Continue the quest.")),
                    "current": 0, "target": 1, "complete": False,
                    "destination": {},
                }]
            category = str(raw.get("category", "General") or "General").title()
            if category not in QUEST_CATEGORIES:
                category = "General"
            record = dict(raw)
            record.update({
                "id": quest_id,
                "title": str(raw.get("title", quest_id) or quest_id),
                "category": category,
                "description": str(raw.get("description", "") or ""),
                "status": status,
                "giver_id": str(raw.get("giver_id", "") or ""),
                "giver_name": str(raw.get("giver_name", "") or ""),
                "objectives": objectives,
                "stage": max(0, min(len(objectives) - 1, int(raw.get("stage", 0) or 0))),
                "rewards": dict(raw.get("rewards", {}) or {}),
                "participants": [str(value) for value in raw.get("participants", []) or [] if str(value)],
                "journal": [str(value)[:300] for value in raw.get("journal", []) or [] if str(value)][-20:],
            })
            if not isinstance(record.get("turn_in", {}), dict):
                record["turn_in"] = {}
            clean[quest_id] = record
        self.state.quest_records = clean
        tracked = str(getattr(self.state, "tracked_quest_id", "") or "")
        if tracked not in clean or str(clean[tracked].get("status", "")) not in {"active", "ready"}:
            self.state.tracked_quest_id = ""
        return clean

    def quest_record(self, quest_id: str) -> Dict[str, object]:
        if str(quest_id).startswith("legacy:"):
            self.sync_legacy_quest_records()
        return self.ensure_quest_state().get(str(quest_id), {})

    def sync_legacy_quest_records(self) -> int:
        """Mirror authoritative older obligations without duplicating their rewards."""
        provider = getattr(self, "legacy_unified_quest_snapshots", None)
        if not callable(provider) or bool(getattr(self, "_syncing_legacy_quests", False)):
            return 0
        self._syncing_legacy_quests = True
        changed = 0
        try:
            snapshots = [row for row in provider() if isinstance(row, dict)]
            store = self.ensure_quest_state()
            seen: set[str] = set()
            for snapshot in snapshots:
                quest_id = str(snapshot.get("id", "") or "")
                if not quest_id.startswith("legacy:"):
                    continue
                seen.add(quest_id)
                existing = store.get(quest_id)
                if not isinstance(existing, dict):
                    existing = {"id": quest_id, "journal": []}
                    store[quest_id] = existing
                    changed += 1
                prior_status = str(existing.get("status", ""))
                journal = list(existing.get("journal", []) or [])[-20:]
                accepted_day = existing.get("accepted_day")
                existing.update(dict(snapshot))
                existing["id"] = quest_id
                existing["legacy_managed"] = True
                existing["journal"] = journal
                if accepted_day is not None:
                    existing["accepted_day"] = accepted_day
                if prior_status and prior_status != str(existing.get("status", "")):
                    existing["journal"] = (journal + [
                        f"Legacy obligation status changed from {prior_status} to {existing.get('status')}.",
                    ])[-20:]
                    changed += 1
            for quest_id, quest in list(store.items()):
                if not str(quest_id).startswith("legacy:") or quest_id in seen or not isinstance(quest, dict):
                    continue
                if str(quest.get("status", "")) in {"completed", "abandoned"}:
                    continue
                quest["status"] = "abandoned"
                quest["journal"] = (list(quest.get("journal", [])) + [
                    "This board posting or contract is no longer available.",
                ])[-20:]
                changed += 1
            self.state.quest_records = store
            tracked = str(getattr(self.state, "tracked_quest_id", "") or "")
            if tracked.startswith("legacy:"):
                tracked_record = store.get(tracked, {})
                if str(tracked_record.get("status", "")) not in {"active", "ready"}:
                    self.state.tracked_quest_id = ""
            return changed
        finally:
            self._syncing_legacy_quests = False

    def register_quest(self, record: Dict[str, object], accept: bool = False) -> Dict[str, object]:
        quest_id = str(record.get("id", "") or "")
        if not quest_id:
            raise ValueError("Quest records require a stable id.")
        store = self.ensure_quest_state()
        if quest_id in store:
            existing = store[quest_id]
            if accept and str(existing.get("status", "")) == "offered":
                existing["status"] = "active"
                existing["accepted_day"] = self.quest_absolute_day()
            return existing
        raw = dict(record)
        raw["status"] = "active" if accept else str(raw.get("status", "offered"))
        raw.setdefault("offered_day", self.quest_absolute_day())
        self.state.quest_records[quest_id] = raw
        normalized = self.ensure_quest_state()[quest_id]
        if accept:
            normalized["accepted_day"] = self.quest_absolute_day()
            if not getattr(self.state, "tracked_quest_id", ""):
                self.state.tracked_quest_id = quest_id
        return normalized

    def quest_absolute_day(self) -> int:
        if hasattr(self, "absolute_game_day"):
            return int(self.absolute_game_day())
        return (
            max(0, int(getattr(self.state, "year", 1)) - 1) * 112
            + max(0, int(getattr(self.state, "month", 1)) - 1) * 28
            + max(1, int(getattr(self.state, "day", 1)))
        )

    def accept_quest(self, quest_id: str, announce: bool = True) -> bool:
        quest = self.quest_record(quest_id)
        if not quest or str(quest.get("status", "")) not in {"offered", "active"}:
            return False
        newly_active = str(quest.get("status", "")) == "offered"
        quest["status"] = "active"
        quest.setdefault("accepted_day", self.quest_absolute_day())
        if not getattr(self.state, "tracked_quest_id", ""):
            self.state.tracked_quest_id = str(quest_id)
        self.refresh_quest_states()
        if announce and newly_active and hasattr(self, "set_message"):
            self.set_message(f"Quest accepted: {quest.get('title', quest_id)}.", "social")
        return True

    def track_quest(self, quest_id: str, announce: bool = True) -> bool:
        quest = self.quest_record(quest_id)
        if not quest or str(quest.get("status", "")) not in {"active", "ready"}:
            return False
        self.state.tracked_quest_id = str(quest_id)
        if announce and hasattr(self, "set_message"):
            self.set_message(f"Tracking quest: {quest.get('title', quest_id)}.")
        return True

    def untrack_quest(self, announce: bool = True) -> None:
        self.state.tracked_quest_id = ""
        if announce and hasattr(self, "set_message"):
            self.set_message("Quest tracking cleared.")

    def tracked_quest(self) -> Dict[str, object]:
        quest_id = str(getattr(self.state, "tracked_quest_id", "") or "")
        if quest_id.startswith("legacy:"):
            self.sync_legacy_quest_records()
        store = getattr(self.state, "quest_records", {})
        if not quest_id or not isinstance(store, dict):
            return {}
        quest = store.get(quest_id, {})
        if not isinstance(quest, dict) or str(quest.get("status", "")) not in {"active", "ready"}:
            return {}
        objective = self.quest_current_objective(quest)
        if objective:
            ready = self.quest_objective_ready(quest, objective)
            objective["ready"] = ready
            if int(quest.get("stage", 0) or 0) >= len(quest.get("objectives", []) or []) - 1:
                quest["status"] = "ready" if ready else "active"
        return quest

    def quest_current_objective(self, quest: Dict[str, object]) -> Dict[str, object]:
        objectives = list(quest.get("objectives", []) or [])
        if not objectives:
            return {}
        stage = max(0, min(len(objectives) - 1, int(quest.get("stage", 0) or 0)))
        return objectives[stage] if isinstance(objectives[stage], dict) else {}

    def quest_objective_ready(self, quest: Dict[str, object], objective: Dict[str, object]) -> bool:
        if bool(objective.get("complete", False)):
            return True
        kind = str(objective.get("kind", "manual"))
        target = max(1, int(objective.get("target", 1) or 1))
        if kind == "item":
            item = str(objective.get("item", ""))
            return bool(item) and int(getattr(self.state, "inventory", {}).get(item, 0) or 0) >= target
        if kind == "money":
            return int(getattr(self.state, "money", 0) or 0) >= target
        if kind == "flag":
            flag = str(objective.get("flag", ""))
            flags = set(getattr(self.state, "scene_flags", []) or [])
            return bool(flag) and flag in flags
        if kind == "visit":
            return self.quest_destination_reached(dict(objective.get("destination", {}) or {}))
        return int(objective.get("current", 0) or 0) >= target

    def refresh_quest_states(self) -> None:
        store = self.ensure_quest_state()
        for quest in store.values():
            if str(quest.get("status", "")) not in {"active", "ready"}:
                continue
            objective = self.quest_current_objective(quest)
            ready = bool(objective) and self.quest_objective_ready(quest, objective)
            quest["status"] = "ready" if ready and int(quest.get("stage", 0)) >= len(quest.get("objectives", [])) - 1 else "active"
            objective["ready"] = ready
        tracked = str(getattr(self.state, "tracked_quest_id", "") or "")
        if tracked and tracked not in store:
            self.state.tracked_quest_id = ""

    def record_quest_event(self, kind: str, **payload: object) -> int:
        kind = str(kind).lower()
        changed = 0
        for quest in self.ensure_quest_state().values():
            if str(quest.get("status", "")) not in {"active", "ready"}:
                continue
            objective = self.quest_current_objective(quest)
            if str(objective.get("kind", "")) != kind:
                continue
            expected_values = {
                str(value).strip().casefold()
                for value in [
                    objective.get("target_id", ""), objective.get("target_name", ""),
                    *(objective.get("target_ids", []) or []), *(objective.get("target_names", []) or []),
                ]
                if str(value).strip()
            }
            actual_values = {
                str(value).strip().casefold()
                for value in [
                    payload.get("target_id", ""), payload.get("target_name", ""),
                    *(payload.get("target_ids", []) or []), *(payload.get("target_names", []) or []),
                ]
                if str(value).strip()
            }
            if expected_values and expected_values.isdisjoint(actual_values):
                continue
            expected_tags = {
                str(value).strip().casefold()
                for value in [objective.get("target_tag", ""), *(objective.get("target_tags", []) or [])]
                if str(value).strip()
            }
            actual_tags = {
                str(value).strip().casefold()
                for value in [payload.get("target_tag", ""), *(payload.get("target_tags", []) or [])]
                if str(value).strip()
            }
            if expected_tags and expected_tags.isdisjoint(actual_tags):
                continue
            required_location = str(objective.get("location", "") or "").strip().casefold()
            actual_location = str(payload.get("location", getattr(self.state, "location", "")) or "").strip().casefold()
            if required_location and required_location != actual_location:
                continue
            amount = max(1, int(payload.get("amount", 1) or 1))
            before = int(objective.get("current", 0) or 0)
            objective["current"] = min(int(objective.get("target", 1) or 1), before + amount)
            if int(objective["current"]) != before:
                changed += 1
                quest["journal"] = (list(quest.get("journal", [])) + [
                    str(payload.get("note", objective.get("description", "Objective progressed.")))
                ])[-20:]
        self.refresh_quest_states()
        return changed

    def advance_quest_stage(self, quest_id: str) -> bool:
        quest = self.quest_record(quest_id)
        if not quest or str(quest.get("status", "")) not in {"active", "ready"}:
            return False
        objective = self.quest_current_objective(quest)
        if not self.quest_objective_ready(quest, objective):
            return False
        objective["complete"] = True
        stage = int(quest.get("stage", 0) or 0)
        if stage + 1 < len(quest.get("objectives", [])):
            quest["stage"] = stage + 1
            quest["status"] = "active"
        else:
            quest["status"] = "ready"
        return True

    def complete_quest(self, quest_id: str, grant_rewards: bool = True) -> bool:
        quest = self.quest_record(quest_id)
        if not quest or str(quest.get("status", "")) == "completed":
            return False
        objective = self.quest_current_objective(quest)
        if str(quest.get("status", "")) != "ready" and not self.quest_objective_ready(quest, objective):
            return False
        if grant_rewards:
            for item, quantity in dict(quest.get("consume_items", {}) or {}).items():
                quantity = max(0, int(quantity))
                if quantity:
                    self.state.inventory[str(item)] = max(
                        0, int(self.state.inventory.get(str(item), 0) or 0) - quantity
                    )
                    if self.state.inventory[str(item)] <= 0:
                        self.state.inventory.pop(str(item), None)
            rewards = dict(quest.get("rewards", {}) or {})
            self.state.money += max(0, int(rewards.get("money", 0) or 0))
            for item, quantity in dict(rewards.get("items", {}) or {}).items():
                if int(quantity) > 0:
                    self.state.inventory[str(item)] = int(self.state.inventory.get(str(item), 0) or 0) + int(quantity)
            relationship = int(rewards.get("relationship", 0) or 0)
            giver_id = str(quest.get("giver_id", ""))
            if relationship and giver_id and hasattr(self, "adjust_town_npc_relationship"):
                self.adjust_town_npc_relationship(giver_id, relationship)
        quest["status"] = "completed"
        quest["completed_day"] = self.quest_absolute_day()
        quest["journal"] = (list(quest.get("journal", [])) + ["Quest completed."])[-20:]
        if str(getattr(self.state, "tracked_quest_id", "")) == str(quest_id):
            self.state.tracked_quest_id = ""
            replacement = next(
                (row for row in self.active_quests() if str(row.get("id")) != str(quest_id)),
                None,
            )
            if replacement:
                self.state.tracked_quest_id = str(replacement.get("id", ""))
        if hasattr(self, "set_message"):
            self.set_message(f"Quest complete: {quest.get('title', quest_id)}.", "gain")
        for event in self.ensure_planned_event_state().values():
            if not isinstance(event, dict) or str(event.get("linked_quest_id", "")) != str(quest_id):
                continue
            if str(event.get("status", "")) in {"planned", "ready", "active"}:
                self.complete_planned_event(str(event.get("id", "")), reason="linked quest completed")
        for participant in self.state.temporary_participant_states.values():
            if isinstance(participant, dict) and str(participant.get("quest_id", "")) == str(quest_id):
                participant["status"] = "completed"
        return True

    def active_quests(self) -> List[Dict[str, object]]:
        self.refresh_quest_states()
        return sorted(
            [row for row in self.ensure_quest_state().values() if str(row.get("status", "")) in {"active", "ready"}],
            key=lambda row: (str(row.get("status")) != "ready", str(row.get("category")), str(row.get("title"))),
        )

    # ------------------------------------------------------------------
    # Coordinates, tracking, and display

    def quest_capture_current_destination(self) -> Dict[str, object]:
        destination = {
            "location": str(getattr(self.state, "location", "")),
            "x": int(getattr(self.state, "player_x", 0)),
            "y": int(getattr(self.state, "player_y", 0)),
        }
        if destination["location"] == "Wilderness" and hasattr(self, "wilderness_world_coords"):
            destination.update({
                "chunk_x": int(self.state.wilderness_chunk_x),
                "chunk_y": int(self.state.wilderness_chunk_y),
            })
            world_x, world_y = self.wilderness_world_coords(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
                int(self.state.player_x), int(self.state.player_y),
            )
            destination.update({"world_x": int(world_x), "world_y": int(world_y)})
        return destination

    def quest_destination_for_known_place(
        self, place: Dict[str, object]
    ) -> Dict[str, object]:
        """Turn dialogue place knowledge into a stable navigable destination."""
        if not isinstance(place, dict):
            return {}
        place_id = str(place.get("id", ""))
        kind = str(place.get("kind", ""))
        label = str(place.get("name", "Known place"))
        if kind == "town" and hasattr(self, "home_world_destination_world_positions"):
            if place_id == "town:farm":
                world = self.home_world_destination_world_positions().get("farm")
            elif place_id == "town:mine":
                world = self.home_world_destination_world_positions().get("mine")
            else:
                building_id = place_id.split(":", 1)[-1]
                door = TOWN_DOORS.get(building_id)
                world = self.home_world_world_for_town_position(*door) if door and hasattr(self, "home_world_world_for_town_position") else None
            if world:
                return {
                    "location": "Wilderness", "world_x": int(world[0]), "world_y": int(world[1]),
                    "label": label, "place_id": place_id,
                }
        if kind == "wilderness" and hasattr(self, "wilderness_world_coords"):
            chunk_x, chunk_y = int(place.get("x", 0)), int(place.get("y", 0))
            world_x, world_y = self.wilderness_world_coords(chunk_x, chunk_y, 43, 19)
            return {
                "location": "Wilderness", "chunk_x": chunk_x, "chunk_y": chunk_y,
                "world_x": int(world_x), "world_y": int(world_y),
                "label": label, "place_id": place_id,
            }
        if kind == "settlement":
            destination = self.quest_capture_current_destination()
            destination.update({
                "x": int(place.get("x", destination.get("x", 0))),
                "y": int(place.get("y", destination.get("y", 0))),
                "label": label, "place_id": place_id,
            })
            if destination.get("location") == "Wilderness" and hasattr(self, "wilderness_world_coords"):
                world_x, world_y = self.wilderness_world_coords(
                    int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
                    int(destination["x"]), int(destination["y"]),
                )
                destination.update({"world_x": int(world_x), "world_y": int(world_y)})
            return destination
        return {}

    def quest_destination_reached(self, destination: Dict[str, object], radius: int = 1) -> bool:
        if not destination:
            return False
        location = str(destination.get("location", ""))
        if location and location != str(getattr(self.state, "location", "")):
            return False
        target = self.quest_destination_local_position(destination)
        if target is None:
            return False
        return manhattan_distance(
            (int(self.state.player_x), int(self.state.player_y)), target
        ) <= max(0, int(radius))

    def quest_destination_local_position(
        self, destination: Dict[str, object]
    ) -> Optional[Tuple[int, int]]:
        if not destination:
            return None
        if str(getattr(self.state, "location", "")) == "Wilderness" and "world_x" in destination:
            origin_x, origin_y = self.wilderness_world_coords(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y), 0, 0
            )
            return int(destination["world_x"]) - int(origin_x), int(destination["world_y"]) - int(origin_y)
        if str(destination.get("location", "")) == str(getattr(self.state, "location", "")):
            try:
                return int(destination.get("x", 0)), int(destination.get("y", 0))
            except Exception:
                return None
        return None

    def quest_tracking_destination(
        self, quest: Dict[str, object]
    ) -> Dict[str, object]:
        objective = self.quest_current_objective(quest)
        if self.quest_objective_ready(quest, objective):
            quest_id = str(quest.get("id", ""))
            participant = next((
                row for row in self.active_temporary_participants()
                if str(row.get("quest_id", "")) == quest_id
            ), None)
            if isinstance(participant, dict):
                destination = {
                    "location": str(participant.get("location", self.state.location)),
                    "x": int(participant.get("x", self.state.player_x)),
                    "y": int(participant.get("y", self.state.player_y)),
                    "label": str(participant.get("name", "the accompanying quest giver")),
                }
                if "world_x" in participant and "world_y" in participant:
                    destination["world_x"] = int(participant["world_x"])
                    destination["world_y"] = int(participant["world_y"])
                return destination
            turn_in = dict(quest.get("turn_in", {}) or {})
            if turn_in:
                return turn_in
        return dict(objective.get("destination", {}) or {})

    def quest_direction_label(self, dx: int, dy: int) -> str:
        vertical = "N" if dy < 0 else "S" if dy > 0 else ""
        horizontal = "W" if dx < 0 else "E" if dx > 0 else ""
        return vertical + horizontal or "HERE"

    def tracked_quest_navigation(self) -> Dict[str, object]:
        quest = self.tracked_quest()
        if not quest:
            return {}
        objective = self.quest_current_objective(quest)
        destination = self.quest_tracking_destination(quest)
        local = self.quest_destination_local_position(destination)
        result = {
            "quest": quest,
            "objective": objective,
            "destination": destination,
            "description": str(objective.get("description", "Continue the quest.")),
        }
        if local is None:
            result["location_label"] = str(destination.get("label", destination.get("location", "Unknown destination")))
            return result
        dx = int(local[0]) - int(self.state.player_x)
        dy = int(local[1]) - int(self.state.player_y)
        result.update({
            "local_x": int(local[0]), "local_y": int(local[1]),
            "dx": dx, "dy": dy,
            "direction": self.quest_direction_label(dx, dy),
            "distance": abs(dx) + abs(dy),
        })
        return result

    def tracked_quest_hud_text(self) -> str:
        nav = self.tracked_quest_navigation()
        if not nav:
            return ""
        quest = nav["quest"]
        title = str(quest.get("title", "Quest"))
        if "distance" in nav:
            route = "here" if int(nav["distance"]) <= 1 else f"{nav['direction']} {nav['distance']} tiles"
        else:
            route = str(nav.get("location_label", nav.get("description", "objective unknown")))
        ready = "Ready — return" if str(quest.get("status")) == "ready" else str(nav.get("description", "Continue"))
        return f"Quest {title}: {ready} | {route}"

    def tracked_quest_local_position(self) -> Optional[Tuple[int, int]]:
        nav = self.tracked_quest_navigation()
        if "local_x" not in nav:
            return None
        position = int(nav["local_x"]), int(nav["local_y"])
        if hasattr(self, "in_active_bounds") and not self.in_active_bounds(*position):
            return None
        return position

    def tracked_quest_stream_position(self) -> Optional[Tuple[int, int]]:
        nav = self.tracked_quest_navigation()
        if "local_x" not in nav:
            return None
        return int(nav["local_x"]), int(nav["local_y"])

    def render_tracked_quest_marker(self) -> str:
        return colorize("!", C.LANDMARK_ACTIVE)

    def quest_progress_label(self, quest: Dict[str, object]) -> str:
        objective = self.quest_current_objective(quest)
        kind = str(objective.get("kind", "manual"))
        if kind == "item":
            item = str(objective.get("item", "item"))
            current = int(self.state.inventory.get(item, 0) or 0)
            return f"{item} {current}/{int(objective.get('target', 1))}"
        if kind in {"visit", "flag"}:
            return "ready" if self.quest_objective_ready(quest, objective) else "in progress"
        labels = {
            "defeat": "defeated", "craft": "crafted", "fish": "caught",
            "harvest": "harvested", "loot": "recovered", "talk": "spoken",
            "escort": "escorted", "inspect": "inspected", "repair": "repaired",
        }
        progress = f"{int(objective.get('current', 0))}/{int(objective.get('target', 1))}"
        return f"{labels.get(kind, 'progress')} {progress}"

    def quest_detail_lines(self, quest: Dict[str, object]) -> List[str]:
        objective = self.quest_current_objective(quest)
        rows = [
            str(quest.get("title", "Quest")).upper(), "",
            f"Category: {quest.get('category', 'General')}",
            f"Status: {str(quest.get('status', 'offered')).title()}",
            f"Given by: {quest.get('giver_name', 'Unknown') or 'Unknown'}", "",
            str(quest.get("description", "")), "", "Current objective:",
            f"- {objective.get('description', 'Continue the quest.')}",
            f"- Progress: {self.quest_progress_label(quest)}",
        ]
        destination = self.quest_tracking_destination(quest)
        if destination:
            rows.append(f"- Destination: {destination.get('label', destination.get('location', 'Marked location'))}")
        rewards = dict(quest.get("rewards", {}) or {})
        if rewards:
            rows.extend(["", "Rewards:"])
            if int(rewards.get("money", 0) or 0):
                rows.append(f"- {int(rewards['money'])}g")
            rows.extend(f"- {qty} {item}" for item, qty in dict(rewards.get("items", {}) or {}).items())
            if int(rewards.get("relationship", 0) or 0):
                rows.append(f"- Relationship {int(rewards['relationship']):+d} with {quest.get('giver_name', 'the quest giver')}")
        journal = list(quest.get("journal", []) or [])
        if journal:
            rows.extend(["", "Journal:", *[f"- {line}" for line in journal[-6:]]])
        return rows

    def unified_quest_journal_lines(self) -> List[str]:
        self.sync_legacy_quest_records()
        self.refresh_quest_states()
        records = list(self.ensure_quest_state().values())
        lines = ["TRACKED QUESTS", ""]
        tracked = self.tracked_quest()
        if tracked:
            lines.extend([
                f"> {tracked.get('title')}",
                f"  {self.quest_current_objective(tracked).get('description')}",
                f"  {self.tracked_quest_hud_text()}", "",
            ])
        else:
            lines.extend(["No quest is currently tracked.", ""])
        for status, label in (("active", "ACTIVE"), ("ready", "READY TO TURN IN"), ("offered", "OFFERS"), ("completed", "COMPLETED")):
            group = [row for row in records if str(row.get("status")) == status]
            if not group:
                continue
            lines.extend([label, ""])
            for quest in sorted(group, key=lambda row: str(row.get("title", ""))):
                lines.append(f"- {quest.get('title')} [{self.quest_progress_label(quest)}]")
            lines.append("")
        if not records:
            lines.append("No unified quests have been recorded yet. Dialogue offers will appear here when accepted.")
        lines.extend(["", *self.planned_event_journal_lines()])
        return lines

    def show_unified_quest_log_menu(self):
        while True:
            self.sync_legacy_quest_records()
            self.refresh_quest_states()
            records = list(self.ensure_quest_state().values())
            items = []
            for quest in sorted(records, key=lambda row: (
                str(row.get("status")) == "completed", str(row.get("status")) != "ready", str(row.get("title"))
            )):
                marker = "> " if str(getattr(self.state, "tracked_quest_id", "")) == str(quest.get("id")) else ""
                items.append(MenuItem(
                    label=f"{marker}{quest.get('title', 'Quest')}", value=str(quest.get("id")), enabled=True,
                    hint=f"{str(quest.get('status', 'offered')).title()} | {self.quest_progress_label(quest)}",
                ))
            items.append(MenuItem(label="Legacy obligations", value="__LEGACY__", enabled=True, hint="resident requests, companion quests, jobs, contracts, and missions"))
            items.append(MenuItem(label="Planned activities", value="__PLANS__", enabled=True, hint="meetings, shared time, guides, outings, and temporary participants"))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Quest Log", items, 56, 24, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return "__BACK__"
            if choice.value == "__LEGACY__":
                self.vertical_panel_view("Legacy Obligations", self.journal_legacy_quest_lines(), 56, 24)
                continue
            if choice.value == "__PLANS__":
                self.show_planned_event_menu()
                continue
            quest = self.quest_record(str(choice.value))
            if not quest:
                continue
            legacy_managed = bool(quest.get("legacy_managed", False))
            actions = [MenuItem(label="View details", value="view", enabled=True)]
            if str(quest.get("status")) in {"active", "ready"}:
                tracked = str(getattr(self.state, "tracked_quest_id", "")) == str(quest.get("id"))
                actions.append(MenuItem(label="Stop tracking" if tracked else "Track quest", value="untrack" if tracked else "track", enabled=True))
            if str(quest.get("status")) == "offered" and not legacy_managed:
                actions.append(MenuItem(label="Accept quest", value="accept", enabled=True))
            if legacy_managed and bool(quest.get("legacy_direct_turn_in", False)) and str(quest.get("status")) == "ready":
                actions.append(MenuItem(label="Turn in", value="legacy_complete", enabled=True, hint="use the original reward and completion rules"))
            if legacy_managed:
                actions.append(MenuItem(label="Open source", value="legacy_source", enabled=True, hint="open the responsible board or request list"))
            actions.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            action = self.vertical_panel_select(str(quest.get("title", "Quest")), actions, 52, 20, return_back=True)
            if not action or action.value == MENU_BACK:
                continue
            if action.value == "view":
                detail_provider = getattr(self, "legacy_unified_quest_detail_lines", None)
                lines = detail_provider(quest) if legacy_managed and callable(detail_provider) else self.quest_detail_lines(quest)
                self.vertical_panel_view(str(quest.get("title", "Quest")), lines, 56, 24)
            elif action.value == "track":
                self.track_quest(str(quest.get("id")))
            elif action.value == "untrack":
                self.untrack_quest()
            elif action.value == "accept":
                self.accept_quest(str(quest.get("id")))
            elif action.value == "legacy_complete":
                completer = getattr(self, "complete_legacy_unified_quest", None)
                if callable(completer) and completer(quest):
                    self.sync_legacy_quest_records()
            elif action.value == "legacy_source":
                opener = getattr(self, "open_legacy_unified_quest_source", None)
                if callable(opener):
                    opener(quest)

    # ------------------------------------------------------------------
    # Dialogue compatibility

    def dialogue_quest_id(
        self, actor: Dict[str, object], kind: str, situation: Dict[str, object]
    ) -> str:
        return f"dialogue:{kind}:{actor.get('id') or actor.get('name')}:{situation.get('id', situation.get('type', 'work'))}"

    def dialogue_quest_for_situation(
        self, actor: Dict[str, object], kind: str, situation: Dict[str, object]
    ) -> Dict[str, object]:
        record = dict(situation.get("record", {}) or {})
        situation_type = str(situation.get("type", "work"))
        item = str(record.get("item", situation.get("item", "")) or "")
        quantity = int(record.get("qty", record.get("quantity", situation.get("qty", 1))) or 1)
        if item:
            objective = {
                "id": "acquire", "kind": "item", "item": item,
                "target": max(1, quantity), "current": 0,
                "description": f"Acquire {max(1, quantity)} {item} for {self.dialogue_actor_name(actor)}.",
                "destination": {},
            }
        else:
            objective = {
                "id": "work", "kind": "manual", "target": 1, "current": 0,
                "description": str(situation.get("summary", "Complete the agreed work.")).capitalize() + ".",
                "destination": self.quest_capture_current_destination(),
            }
        destination = self.quest_capture_current_destination()
        destination["label"] = f"{self.dialogue_actor_name(actor)} — {getattr(self.state, 'location', 'current location')}"
        return {
            "id": self.dialogue_quest_id(actor, kind, situation),
            "title": str(situation.get("title", f"Help {self.dialogue_actor_name(actor)}")),
            "category": "Relationships" if kind in {"spouse", "child", "companion"} else "Town" if kind in {"authored", "procedural"} else "Wilderness",
            "description": str(situation.get("prompt", situation.get("summary", "Help with a practical request."))),
            "giver_id": str(actor.get("id", "")),
            "giver_name": self.dialogue_actor_name(actor),
            "source_type": situation_type,
            "source_id": str(situation.get("id", "")),
            "objectives": [objective],
            "turn_in": destination,
            "rewards": {},
            "journal": [f"Accepted through conversation with {self.dialogue_actor_name(actor)}."],
        }

    def accept_dialogue_quest(
        self, actor: Dict[str, object], kind: str, situation: Dict[str, object]
    ) -> Dict[str, object]:
        record = self.dialogue_quest_for_situation(actor, kind, situation)
        quest = self.register_quest(record, accept=True)
        self.track_quest(str(quest.get("id", "")), announce=False)
        return quest

    def complete_dialogue_quest_for_situation(
        self, actor: Dict[str, object], kind: str, situation: Dict[str, object]
    ) -> bool:
        quest_id = self.dialogue_quest_id(actor, kind, situation)
        quest = self.quest_record(quest_id)
        if not quest:
            return False
        objective = self.quest_current_objective(quest)
        objective["complete"] = True
        objective["current"] = int(objective.get("target", 1) or 1)
        quest["status"] = "ready"
        return self.complete_quest(quest_id, grant_rewards=False)

    # ------------------------------------------------------------------
    # Planned events and temporary participants

    def ensure_planned_event_state(self) -> Dict[str, Dict[str, object]]:
        if not isinstance(getattr(self.state, "planned_events", None), dict):
            self.state.planned_events = {}
        if not isinstance(getattr(self.state, "temporary_participant_states", None), dict):
            self.state.temporary_participant_states = {}
        allowed_statuses = {"planned", "ready", "active", "completed", "missed", "cancelled"}
        clean: Dict[str, Dict[str, object]] = {}
        for raw_id, event in self.state.planned_events.items():
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id", raw_id) or raw_id)
            if not event_id:
                continue
            event["id"] = event_id
            event["title"] = str(event.get("title", "Planned activity") or "Planned activity")[:120]
            event["kind"] = str(event.get("kind", "planned_activity") or "planned_activity")
            status = str(event.get("status", "planned") or "planned").lower()
            event["status"] = status if status in allowed_statuses else "planned"
            event["due_day"] = max(1, int(event.get("due_day", self.quest_absolute_day()) or self.quest_absolute_day()))
            event["due_hour"] = max(0, min(23, int(event.get("due_hour", 12) or 0)))
            event["duration_minutes"] = max(30, min(720, int(event.get("duration_minutes", 120) or 120)))
            event["participants"] = [
                row for row in event.get("participants", []) or [] if isinstance(row, dict)
            ][:16]
            if not isinstance(event.get("destination", {}), dict):
                event["destination"] = {}
            event["conflict_ids"] = [str(value) for value in event.get("conflict_ids", []) or [] if str(value)][:16]
            clean[event_id] = event
        open_rows = {
            event_id: event for event_id, event in clean.items()
            if str(event.get("status", "")) in {"planned", "ready", "active"}
        }
        closed_rows = [
            (event_id, event) for event_id, event in clean.items() if event_id not in open_rows
        ]
        closed_rows.sort(key=lambda pair: (
            int(pair[1].get("completed_day", pair[1].get("due_day", 0)) or 0), pair[0]
        ), reverse=True)
        self.state.planned_events = {**open_rows, **dict(closed_rows[:100])}
        self.state.temporary_participant_states = {
            str(raw_id): row
            for raw_id, row in self.state.temporary_participant_states.items()
            if isinstance(row, dict) and str(row.get("event_id", "")) in self.state.planned_events
        }
        return self.state.planned_events

    def schedule_planned_event(self, record: Dict[str, object]) -> Dict[str, object]:
        store = self.ensure_planned_event_state()
        event_id = str(record.get("id", "") or f"plan:{self.quest_absolute_day()}:{len(store) + 1}")
        event = dict(record)
        kind = str(record.get("kind", "planned_activity") or "planned_activity")
        default_duration = {
            "meeting": 120, "relationship_date": 180,
            "social_outing": 180, "social_gathering": 240,
        }.get(kind, 120)
        event.update({
            "id": event_id,
            "title": str(record.get("title", "Planned activity")),
            "status": str(record.get("status", "planned")),
            "kind": kind,
            "due_day": int(record.get("due_day", self.quest_absolute_day()) or self.quest_absolute_day()),
            "due_hour": int(record.get("due_hour", getattr(self.state, "hour", 12)) or 0),
            "duration_minutes": max(30, int(record.get("duration_minutes", default_duration) or default_duration)),
            "participants": [dict(row) for row in record.get("participants", []) or [] if isinstance(row, dict)],
            "destination": dict(record.get("destination", {}) or {}),
        })
        if self.planned_event_requires_attendance(event) and not int(event.get("expires_at_minute", 0) or 0):
            start, end = self.planned_event_time_span(event)
            event["expires_at_minute"] = end + 120
        store[event_id] = event
        self.refresh_planned_event_conflicts()
        return event

    def planned_event_requires_attendance(self, event: Dict[str, object]) -> bool:
        return bool(event.get("requires_attendance", False)) or str(event.get("kind", "")) in {
            "meeting", "relationship_date", "social_outing", "social_gathering",
        }

    def planned_event_player_manageable(self, event: Dict[str, object]) -> bool:
        """Keep quest machinery safe while allowing genuine appointments to be edited."""
        if bool(event.get("locked_schedule", False)) or str(event.get("quest_id", "")):
            return False
        return bool(event.get("player_manageable", False)) or self.planned_event_requires_attendance(event)

    def planned_event_time_span(self, event: Dict[str, object]) -> Tuple[int, int]:
        start = int(event.get("due_day", self.quest_absolute_day())) * 1440 + int(event.get("due_hour", 0)) * 60
        return start, start + max(30, int(event.get("duration_minutes", 120) or 120))

    def planned_event_conflicts(
        self, candidate: Dict[str, object], exclude_id: str = ""
    ) -> List[Dict[str, object]]:
        if not self.planned_event_requires_attendance(candidate):
            return []
        candidate_start, candidate_end = self.planned_event_time_span(candidate)
        conflicts: List[Dict[str, object]] = []
        for event in self.ensure_planned_event_state().values():
            if not isinstance(event, dict) or str(event.get("id", "")) == str(exclude_id):
                continue
            if str(event.get("status", "")) not in {"planned", "ready", "active"}:
                continue
            if not self.planned_event_requires_attendance(event):
                continue
            other_start, other_end = self.planned_event_time_span(event)
            if candidate_start < other_end and other_start < candidate_end:
                conflicts.append(event)
        return sorted(conflicts, key=lambda row: self.planned_event_time_span(row)[0])

    def planned_event_sync_social_records(
        self, event: Dict[str, object], outcome: str = ""
    ) -> None:
        event_id = str(event.get("id", ""))
        for participant in event.get("participants", []) or []:
            if not isinstance(participant, dict):
                continue
            actor = self.temporary_participant_actor(participant)
            if not actor or not hasattr(self, "dialogue_social_slot"):
                continue
            slot = self.dialogue_social_slot(actor, str(participant.get("kind", "authored")))
            for meeting in slot.get("meetings", []) or []:
                if not isinstance(meeting, dict) or str(meeting.get("event_id", "")) != event_id:
                    continue
                meeting["day"] = int(event.get("due_day", meeting.get("day", 0)) or 0)
                meeting["hour"] = int(event.get("due_hour", meeting.get("hour", 0)) or 0)
                meeting["destination"] = dict(event.get("destination", meeting.get("destination", {})) or {})
                if outcome:
                    meeting["completed"] = True
                    meeting["outcome"] = str(outcome)
                    meeting[f"{outcome}_day"] = self.quest_absolute_day()
                    if outcome == "missed":
                        meeting["missed"] = True
                    if outcome == "cancelled":
                        meeting["cancelled"] = True
            invitation = slot.get("invitation", {})
            if isinstance(invitation, dict) and str(invitation.get("event_id", "")) == event_id:
                if outcome:
                    invitation["status"] = str(outcome)
                    invitation["resolved_day"] = self.quest_absolute_day()
                else:
                    invitation["due_day"] = int(event.get("due_day", invitation.get("due_day", 0)) or 0)
                    invitation["due_hour"] = int(event.get("due_hour", invitation.get("due_hour", 0)) or 0)
                    invitation["destination"] = dict(event.get("destination", invitation.get("destination", {})) or {})

    def cancel_planned_event(self, event_id: str, reason: str = "cancelled by the player") -> bool:
        event = self.ensure_planned_event_state().get(str(event_id), {})
        if (
            not isinstance(event, dict)
            or str(event.get("status", "")) not in {"planned", "ready", "active"}
            or not self.planned_event_player_manageable(event)
        ):
            return False
        event["status"] = "cancelled"
        event["completed_day"] = self.quest_absolute_day()
        event["completion_reason"] = str(reason)
        for participant in self.state.temporary_participant_states.values():
            if isinstance(participant, dict) and str(participant.get("event_id", "")) == str(event_id):
                participant["status"] = "completed"
        self.planned_event_sync_social_records(event, "cancelled")
        self.refresh_planned_event_conflicts()
        return True

    def reschedule_planned_event(self, event_id: str, due_day: int, due_hour: int) -> bool:
        event = self.ensure_planned_event_state().get(str(event_id), {})
        if (
            not isinstance(event, dict)
            or str(event.get("status", "")) != "planned"
            or not self.planned_event_player_manageable(event)
        ):
            return False
        due_day, due_hour = int(due_day), max(0, min(23, int(due_hour)))
        if due_day < self.quest_absolute_day():
            return False
        old_due = int(event.get("due_day", due_day)) * 1440 + int(event.get("due_hour", due_hour)) * 60
        old_expiry = int(event.get("expires_at_minute", 0) or 0)
        grace = max(60, old_expiry - old_due) if old_expiry else max(120, int(event.get("duration_minutes", 120)) + 120)
        event["due_day"], event["due_hour"] = due_day, due_hour
        event["expires_at_minute"] = due_day * 1440 + due_hour * 60 + grace
        event["rescheduled_day"] = self.quest_absolute_day()
        event["reschedule_count"] = int(event.get("reschedule_count", 0) or 0) + 1
        self.planned_event_sync_social_records(event)
        self.refresh_planned_event_conflicts()
        return True

    def refresh_planned_event_conflicts(self) -> None:
        for event in self.ensure_planned_event_state().values():
            if not isinstance(event, dict) or str(event.get("status", "")) not in {"planned", "ready", "active"}:
                if isinstance(event, dict):
                    event["conflict_ids"] = []
                continue
            event["conflict_ids"] = [
                str(row.get("id", "")) for row in self.planned_event_conflicts(
                    event, exclude_id=str(event.get("id", ""))
                )
            ]

    def planned_event_invalid_participants(self, event: Dict[str, object]) -> List[str]:
        invalid: List[str] = []
        deceased_ids = {str(value) for value in getattr(self.state, "deceased_spouse_npc_ids", []) or []}
        for participant in event.get("participants", []) or []:
            if not isinstance(participant, dict):
                continue
            actor_id = str(participant.get("actor_id", ""))
            actor = self.npc_record_by_id(actor_id) if actor_id and hasattr(self, "npc_record_by_id") else None
            if actor_id in deceased_ids or (isinstance(actor, dict) and bool(actor.get("deceased", False))):
                invalid.append(str(participant.get("name", actor_id or "A participant")))
        return invalid

    def planned_event_weather_delay(self, event: Dict[str, object]) -> bool:
        if not self.planned_event_requires_attendance(event) or int(event.get("weather_delays", 0) or 0) >= 2:
            return False
        weather = str(getattr(self.state, "weather", "") or "").lower()
        if not any(word in weather for word in ("storm", "blizzard", "hurricane", "severe")):
            return False
        destination = dict(event.get("destination", {}) or {})
        label = str(destination.get("label", "")).lower()
        location = str(destination.get("location", "")).lower()
        outdoors = location == "wilderness" or any(
            word in label for word in ("trail", "lake", "river", "beach", "forest", "park", "farm", "outdoor", "wilderness")
        )
        if not outdoors:
            return False
        event["due_day"] = int(event.get("due_day", self.quest_absolute_day())) + 1
        if int(event.get("expires_at_minute", 0) or 0):
            event["expires_at_minute"] = int(event["expires_at_minute"]) + 1440
        event["weather_delays"] = int(event.get("weather_delays", 0) or 0) + 1
        event["last_weather_delay"] = weather or "severe weather"
        self.planned_event_sync_social_records(event)
        return True

    def open_planned_events_for_actor(
        self, actor_id: str, kinds: Sequence[str] = ()
    ) -> List[Dict[str, object]]:
        actor_id = str(actor_id or "")
        allowed = {str(value) for value in kinds if str(value)}
        if not actor_id:
            return []
        rows: List[Dict[str, object]] = []
        for event in self.ensure_planned_event_state().values():
            if not isinstance(event, dict):
                continue
            if str(event.get("status", "")) not in {"planned", "ready", "active"}:
                continue
            if allowed and str(event.get("kind", "")) not in allowed:
                continue
            if any(
                str(participant.get("actor_id", "")) == actor_id
                for participant in event.get("participants", []) or []
                if isinstance(participant, dict)
            ):
                rows.append(event)
        return rows

    def complete_planned_event(self, event_id: str, reason: str = "completed") -> bool:
        event = self.ensure_planned_event_state().get(str(event_id), {})
        if not isinstance(event, dict) or str(event.get("status", "")) in {"completed", "cancelled"}:
            return False
        event["status"] = "completed"
        event["completed_day"] = self.quest_absolute_day()
        event["completion_reason"] = str(reason)
        for participant in self.state.temporary_participant_states.values():
            if isinstance(participant, dict) and str(participant.get("event_id", "")) == str(event_id):
                participant["status"] = "completed"
        self.planned_event_sync_social_records(event, "completed")
        self.refresh_planned_event_conflicts()
        quest_id = str(event.get("quest_id", ""))
        if quest_id:
            quest = self.quest_record(quest_id)
            if quest and str(quest.get("status", "")) in {"active", "ready"}:
                objective = self.quest_current_objective(quest)
                objective["current"] = int(objective.get("target", 1) or 1)
                objective["complete"] = True
                quest["status"] = "ready"
                self.complete_quest(quest_id, grant_rewards=True)
        return True

    def miss_planned_event(self, event_id: str) -> bool:
        event = self.ensure_planned_event_state().get(str(event_id), {})
        if not isinstance(event, dict) or str(event.get("status", "")) in {"completed", "cancelled", "missed"}:
            return False
        event["status"] = "missed"
        event["completed_day"] = self.quest_absolute_day()
        for participant in self.state.temporary_participant_states.values():
            if not isinstance(participant, dict) or str(participant.get("event_id", "")) != str(event_id):
                continue
            participant["status"] = "completed"
            actor = self.temporary_participant_actor(participant)
            if hasattr(self, "dialogue_social_slot"):
                slot = self.dialogue_social_slot(actor, str(participant.get("kind", "authored")))
                for meeting in slot.get("meetings", []) or []:
                    if isinstance(meeting, dict) and str(meeting.get("event_id", "")) == str(event_id):
                        meeting["completed"] = True
                        meeting["missed"] = True
        self.planned_event_sync_social_records(event, "missed")
        self.refresh_planned_event_conflicts()
        return True

    def activate_planned_event(self, event_id: str) -> bool:
        event = self.ensure_planned_event_state().get(str(event_id), {})
        if not isinstance(event, dict) or str(event.get("status", "")) not in {"planned", "ready"}:
            return False
        event["status"] = "active"
        destination = dict(event.get("destination", {}) or {})
        for participant in event.get("participants", []) or []:
            actor_id = str(participant.get("actor_id", "") or "")
            if not actor_id:
                continue
            mode = str(participant.get("mode", "accompany"))
            participant_destination = dict(participant.get("destination", destination) or {})
            participant_location = (
                str(participant_destination.get("location", self.state.location))
                if mode in {"meet", "attend"}
                else str(self.state.location)
            )
            key = f"{event_id}:{actor_id}"
            self.state.temporary_participant_states[key] = {
                "id": key,
                "event_id": str(event_id), "actor_id": actor_id,
                "name": str(participant.get("name", actor_id)),
                "role": str(participant.get("role", "Guest")),
                "kind": str(participant.get("kind", "authored")),
                "mode": mode,
                "purpose": str(participant.get("purpose", event.get("title", "the shared plan"))),
                "quest_id": str(event.get("quest_id", participant.get("quest_id", "")) or ""),
                "status": "active", "location": participant_location,
                "x": int(participant_destination.get("x", self.state.player_x)),
                "y": int(participant_destination.get("y", self.state.player_y)),
                "destination": participant_destination,
            }
            runtime = self.state.temporary_participant_states[key]
            if participant_location == "Wilderness" and hasattr(self, "wilderness_world_coords"):
                if mode in {"meet", "attend"} and "world_x" in participant_destination:
                    runtime["world_x"] = int(participant_destination["world_x"])
                    runtime["world_y"] = int(participant_destination["world_y"])
                else:
                    world_x, world_y = self.wilderness_world_coords(
                        int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
                        int(runtime["x"]), int(runtime["y"]),
                    )
                    runtime["world_x"], runtime["world_y"] = int(world_x), int(world_y)
        return True

    def update_planned_events(self) -> None:
        now_day = self.quest_absolute_day()
        now_hour = int(getattr(self.state, "hour", 0))
        now_minute = now_day * 1440 + now_hour * 60 + int(getattr(self.state, "minute", 0))
        for event in self.ensure_planned_event_state().values():
            status = str(event.get("status", ""))
            if status == "planned":
                invalid = self.planned_event_invalid_participants(event)
                if invalid:
                    event["status"] = "cancelled"
                    event["completed_day"] = now_day
                    event["completion_reason"] = f"unavailable participant: {', '.join(invalid)}"
                    self.planned_event_sync_social_records(event, "cancelled")
                    if hasattr(self, "set_message"):
                        self.set_message(
                            f"{event.get('title', 'A planned activity')} was cancelled because "
                            f"{', '.join(invalid)} could no longer attend.", "social"
                        )
                    continue
                due = (int(event.get("due_day", now_day)), int(event.get("due_hour", 0)))
                if (now_day, now_hour) >= due:
                    if self.planned_event_weather_delay(event):
                        if hasattr(self, "set_message"):
                            self.set_message(
                                f"Severe weather moved {str(event.get('title', 'the outdoor plan')).lower()} to tomorrow.",
                                "social",
                            )
                        continue
                    event["status"] = "ready"
                    status = "ready"
                else:
                    continue
            if status == "ready" and bool(event.get("auto_activate", False)):
                self.activate_planned_event(str(event.get("id", "")))
                continue
            if status != "active":
                continue
            expires_at = int(event.get("expires_at_minute", 0) or 0)
            if expires_at and now_minute >= expires_at:
                requires_attendance = self.planned_event_requires_attendance(event)
                if requires_attendance:
                    self.miss_planned_event(str(event.get("id", "")))
                else:
                    self.complete_planned_event(str(event.get("id", "")), reason="time elapsed")
                if hasattr(self, "set_message"):
                    message = (
                        f"The time for {str(event.get('title', 'the meeting')).lower()} passed. It remains part of your shared history, without an automatic relationship penalty."
                        if requires_attendance else f"{event.get('title', 'The planned activity')} has ended."
                    )
                    self.set_message(message, "social")
                continue

        self.refresh_planned_event_conflicts()

    def planned_event_journal_lines(self) -> List[str]:
        self.update_planned_events()
        events = [
            row for row in self.ensure_planned_event_state().values()
            if isinstance(row, dict) and str(row.get("status", "")) in {"planned", "ready", "active"}
        ]
        lines = ["PLANNED ACTIVITIES", ""]
        if not events:
            return lines + ["- Nothing is currently arranged."]
        for event in sorted(events, key=lambda row: (int(row.get("due_day", 0)), int(row.get("due_hour", 0)), str(row.get("title", "")))):
            destination = dict(event.get("destination", {}) or {})
            status = str(event.get("status", "planned")).replace("_", " ").title()
            participants = ", ".join(str(row.get("name", "Guest")) for row in event.get("participants", []) or [])
            lines.append(f"- {event.get('title', 'Planned activity')} [{status}]")
            if participants:
                lines.append(f"  With: {participants}")
            if destination:
                lines.append(f"  Where: {destination.get('label', destination.get('location', 'Marked place'))}")
            if str(event.get("status", "")) == "planned":
                remaining = max(0, int(event.get("due_day", 0)) - self.quest_absolute_day())
                lines.append(f"  When: {'today' if remaining == 0 else 'tomorrow' if remaining == 1 else f'in {remaining} days'}, around {int(event.get('due_hour', 0)):02d}:00")
            conflicts = list(event.get("conflict_ids", []) or [])
            if conflicts:
                lines.append(f"  Conflict: overlaps {len(conflicts)} other appointment{'s' if len(conflicts) != 1 else ''}")
            if int(event.get("weather_delays", 0) or 0):
                lines.append(f"  Weather delay: {event.get('last_weather_delay', 'severe weather')}")
        return lines

    def planned_event_history_lines(self, limit: int = 20) -> List[str]:
        events = [
            row for row in self.ensure_planned_event_state().values()
            if isinstance(row, dict) and str(row.get("status", "")) in {"completed", "missed", "cancelled"}
        ]
        lines = ["ACTIVITY HISTORY", ""]
        if not events:
            return lines + ["- No completed, missed, or cancelled activities yet."]
        events.sort(key=lambda row: (
            int(row.get("completed_day", row.get("due_day", 0)) or 0),
            int(row.get("due_hour", 0) or 0), str(row.get("title", "")),
        ), reverse=True)
        for event in events[:max(1, int(limit))]:
            status = str(event.get("status", "completed")).title()
            lines.append(f"- {event.get('title', 'Planned activity')} [{status}]")
            reason = str(event.get("completion_reason", "") or "")
            if reason:
                lines.append(f"  {reason.capitalize()}.")
        return lines

    def planned_event_detail_lines(self, event: Dict[str, object]) -> List[str]:
        destination = dict(event.get("destination", {}) or {})
        participants = ", ".join(
            str(row.get("name", "Guest")) for row in event.get("participants", []) or [] if isinstance(row, dict)
        ) or "No named participants"
        lines = [
            str(event.get("title", "Planned activity")), "",
            f"Status: {str(event.get('status', 'planned')).replace('_', ' ').title()}",
            f"Participants: {participants}",
            f"Place: {destination.get('label', destination.get('location', 'No fixed destination'))}",
            f"Time: day {int(event.get('due_day', 0))}, {int(event.get('due_hour', 0)):02d}:00",
            f"Expected duration: {max(1, int(event.get('duration_minutes', 120)) // 60)}h "
            f"{int(event.get('duration_minutes', 120)) % 60:02d}m",
        ]
        conflicts = [
            self.ensure_planned_event_state().get(str(event_id), {})
            for event_id in event.get("conflict_ids", []) or []
        ]
        conflicts = [row for row in conflicts if isinstance(row, dict) and row]
        if conflicts:
            lines.extend(["", "Schedule conflict:"])
            lines.extend(f"- {row.get('title', 'Another appointment')}" for row in conflicts)
        if int(event.get("reschedule_count", 0) or 0):
            lines.append(f"Rescheduled: {int(event.get('reschedule_count', 0))} time(s)")
        if int(event.get("weather_delays", 0) or 0):
            lines.append(f"Weather delays: {int(event.get('weather_delays', 0))}")
        reason = str(event.get("completion_reason", "") or "")
        if reason:
            lines.extend(["", f"Outcome: {reason.capitalize()}."])
        return lines

    def show_planned_event_menu(self):
        while True:
            self.update_planned_events()
            events = [row for row in self.ensure_planned_event_state().values() if isinstance(row, dict)]
            events.sort(key=lambda row: (
                str(row.get("status", "")) not in {"ready", "active"},
                str(row.get("status", "")) != "planned",
                int(row.get("due_day", 0)), int(row.get("due_hour", 0)),
            ))
            items: List[MenuItem] = []
            for event in events:
                status = str(event.get("status", "planned"))
                marker = "! " if event.get("conflict_ids") else ""
                items.append(MenuItem(
                    label=f"{marker}{event.get('title', 'Planned activity')}",
                    value=str(event.get("id", "")), enabled=True,
                    hint=f"{status.replace('_', ' ').title()} | Day {int(event.get('due_day', 0))}, {int(event.get('due_hour', 0)):02d}:00",
                ))
            if not items:
                items.append(MenuItem(label="No activities recorded", value="__EMPTY__", enabled=False))
            items.append(MenuItem(label="Activity history", value="__HISTORY__", enabled=True, hint="completed, missed, and cancelled plans"))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Planned Activities", items, 60, 25, return_back=True)
            if not choice or choice.value == MENU_BACK:
                return "__BACK__"
            if choice.value == "__HISTORY__":
                self.vertical_panel_view("Activity History", self.planned_event_history_lines(), 58, 24)
                continue
            event = self.ensure_planned_event_state().get(str(choice.value), {})
            if not isinstance(event, dict) or not event:
                continue
            actions = [MenuItem(label="View details", value="view", enabled=True)]
            manageable = self.planned_event_player_manageable(event)
            if manageable and str(event.get("status", "")) == "planned":
                actions.append(MenuItem(label="Reschedule", value="reschedule", enabled=True, hint="choose another day and time"))
            if manageable and str(event.get("status", "")) in {"planned", "ready", "active"}:
                actions.append(MenuItem(label="Cancel activity", value="cancel", enabled=True, hint="remove it without an automatic relationship penalty"))
            actions.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            action = self.vertical_panel_select(str(event.get("title", "Activity")), actions, 54, 21, return_back=True)
            if not action or action.value == MENU_BACK:
                continue
            if action.value == "view":
                self.vertical_panel_view(str(event.get("title", "Activity")), self.planned_event_detail_lines(event), 58, 24)
                continue
            if action.value == "reschedule":
                day = self.vertical_panel_select("Choose Day", [
                    MenuItem(label="Tomorrow", value="1", enabled=True),
                    MenuItem(label="In two days", value="2", enabled=True),
                    MenuItem(label="In three days", value="3", enabled=True),
                    MenuItem(label="In one week", value="7", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ], 44, 18, return_back=True)
                if not day or day.value == MENU_BACK:
                    continue
                hour = self.vertical_panel_select("Choose Time", [
                    MenuItem(label=f"{value:02d}:00", value=str(value), enabled=True)
                    for value in (8, 10, 12, 14, 17, 20)
                ] + [MenuItem(label="Back", value=MENU_BACK, enabled=True)], 40, 20, return_back=True)
                if not hour or hour.value == MENU_BACK:
                    continue
                self.reschedule_planned_event(
                    str(event.get("id", "")), self.quest_absolute_day() + int(day.value), int(hour.value)
                )
                if hasattr(self, "autosave_with_message"):
                    self.autosave_with_message(f"Rescheduled {str(event.get('title', 'the activity')).lower()}.")
                continue
            if action.value == "cancel":
                confirm = self.vertical_panel_select("Cancel Activity?", [
                    MenuItem(label="Keep the plan", value="keep", enabled=True),
                    MenuItem(label="Cancel it", value="cancel", enabled=True, hint="no automatic relationship penalty"),
                ], 48, 16, return_back=True)
                if confirm and confirm.value == "cancel":
                    self.cancel_planned_event(str(event.get("id", "")))
                    if hasattr(self, "autosave_with_message"):
                        self.autosave_with_message(f"Cancelled {str(event.get('title', 'the activity')).lower()}.")

    def planned_event_calendar_lines(self, month: int, day: int, year: int) -> List[str]:
        if not hasattr(self, "absolute_game_day"):
            return []
        target_day = int(self.absolute_game_day(month, day, year))
        return [
            f"Plan: {event.get('title', 'Planned activity')} at {int(event.get('due_hour', 0)):02d}:00"
            for event in self.ensure_planned_event_state().values()
            if isinstance(event, dict)
            and str(event.get("status", "")) in {"planned", "ready", "active"}
            and int(event.get("due_day", -1)) == target_day
        ]

    def active_planned_event(self) -> Dict[str, object]:
        self.update_planned_events()
        events = [
            row for row in self.ensure_planned_event_state().values()
            if isinstance(row, dict) and str(row.get("status", "")) in {"ready", "active"}
        ]
        return sorted(events, key=lambda row: (str(row.get("status")) != "active", int(row.get("due_day", 0))))[0] if events else {}

    def planned_event_hud_text(self) -> str:
        event = self.active_planned_event()
        if not event:
            return ""
        destination = dict(event.get("destination", {}) or {})
        local = self.quest_destination_local_position(destination)
        route = str(destination.get("label", destination.get("location", "the meeting place")))
        if local is not None:
            dx, dy = int(local[0]) - int(self.state.player_x), int(local[1]) - int(self.state.player_y)
            distance = abs(dx) + abs(dy)
            route = "here" if distance <= 1 else f"{self.quest_direction_label(dx, dy)} {distance} tiles"
        return f"Plan {event.get('title', 'Activity')}: {route}"

    def active_temporary_participants(self) -> List[Dict[str, object]]:
        self.ensure_planned_event_state()
        return [
            row for row in self.state.temporary_participant_states.values()
            if isinstance(row, dict) and str(row.get("status", "")) in {"active", "arrived"}
        ]

    def temporary_participant_actor_ids(self) -> set[str]:
        return {str(row.get("actor_id", "")) for row in self.active_temporary_participants() if row.get("actor_id")}

    def temporary_participant_meeting_positions(self) -> Dict[str, Tuple[int, int]]:
        groups: Dict[str, List[Dict[str, object]]] = {}
        for row in self.active_temporary_participants():
            if str(row.get("location", "")) != str(getattr(self.state, "location", "")):
                continue
            if str(row.get("mode", "")) not in {"meet", "attend"}:
                continue
            groups.setdefault(str(row.get("event_id", row.get("id", ""))), []).append(row)
        positions: Dict[str, Tuple[int, int]] = {}
        occupied: set[Tuple[int, int]] = set()
        for event_id in sorted(groups):
            attendees = sorted(groups[event_id], key=lambda row: str(row.get("id", row.get("actor_id", ""))))
            if not attendees:
                continue
            destination = dict(attendees[0].get("destination", {}) or {})
            base = self.quest_destination_local_position(destination)
            if base is None:
                continue
            bx, by = int(base[0]), int(base[1])
            offsets = [(0, 0)]
            for radius in range(1, 5):
                ring = [
                    (dx, dy)
                    for dy in range(-radius, radius + 1)
                    for dx in range(-radius, radius + 1)
                    if max(abs(dx), abs(dy)) == radius
                ]
                ring.sort(key=lambda offset: (abs(offset[0]) + abs(offset[1]), offset[1], offset[0]))
                offsets.extend(ring)
            for attendee in attendees:
                position = next((
                    (bx + dx, by + dy)
                    for dx, dy in offsets
                    if (bx + dx, by + dy) not in occupied
                    and self.temporary_participant_tile_available(attendee, bx + dx, by + dy)
                ), None)
                if position is None:
                    continue
                participant_id = str(attendee.get("id", attendee.get("actor_id", "")))
                positions[participant_id] = position
                attendee["x"], attendee["y"] = int(position[0]), int(position[1])
                occupied.add(position)
        return positions

    def temporary_participant_position_lookup(self) -> Dict[Tuple[int, int], Dict[str, object]]:
        meeting_positions = self.temporary_participant_meeting_positions()
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        for row in self.active_temporary_participants():
            if str(row.get("location", "")) != str(getattr(self.state, "location", "")):
                continue
            if str(row.get("mode", "")) in {"meet", "attend"}:
                position = meeting_positions.get(str(row.get("id", row.get("actor_id", ""))))
                if position is None:
                    continue
                lookup[position] = row
                continue
            try:
                position = int(row.get("x", -1)), int(row.get("y", -1))
            except Exception:
                continue
            if position[0] >= 0 and position[1] >= 0:
                lookup[position] = row
        return lookup

    def temporary_participant_at(self, x: int, y: int) -> Dict[str, object]:
        return self.temporary_participant_position_lookup().get((int(x), int(y)), {})

    def rebase_temporary_participant_positions(self) -> None:
        if str(getattr(self.state, "location", "")) != "Wilderness" or not hasattr(self, "wilderness_world_coords"):
            return
        origin_x, origin_y = self.wilderness_world_coords(
            int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y), 0, 0
        )
        for participant in self.active_temporary_participants():
            if str(participant.get("location", "")) != "Wilderness":
                continue
            if str(participant.get("mode", "")) in {"meet", "attend"}:
                continue
            if "world_x" in participant and "world_y" in participant:
                participant["x"] = int(participant["world_x"]) - int(origin_x)
                participant["y"] = int(participant["world_y"]) - int(origin_y)

    def temporary_participant_actor(self, participant: Dict[str, object]) -> Dict[str, object]:
        actor_id = str(participant.get("actor_id", ""))
        actor = self.npc_record_by_id(actor_id) if actor_id and hasattr(self, "npc_record_by_id") else None
        if isinstance(actor, dict):
            return actor
        return {
            "id": actor_id or str(participant.get("id", "temporary_participant")),
            "name": str(participant.get("name", "Guest")),
            "role": str(participant.get("role", "Guest")),
            "activity": str(participant.get("mode", "accompanying you")),
            "relationship": int(participant.get("relationship", 0) or 0),
        }

    def talk_to_temporary_participant(self, participant: Dict[str, object]) -> bool:
        actor = self.temporary_participant_actor(participant)
        kind = str(participant.get("kind", "authored"))
        if hasattr(self, "run_unified_npc_conversation"):
            mode = str(participant.get("mode", "accompany"))
            event = self.ensure_planned_event_state().get(str(participant.get("event_id", "")), {})
            event_kind = str(event.get("kind", "")) if isinstance(event, dict) else ""
            if event_kind == "social_gathering" and hasattr(
                self, "dialogue_handle_planned_gathering_arrival"
            ):
                if not self.dialogue_handle_planned_gathering_arrival(actor, kind, event, participant):
                    return True
                self.record_quest_event(
                    "social_gathering", target_id=str(event.get("id", "")),
                    note=f"Completed {event.get('title', 'a group gathering')} with its invited guests.",
                )
                for attendee in event.get("participants", []) or []:
                    attendee_actor = self.temporary_participant_actor({
                        "actor_id": str(attendee.get("actor_id", "")),
                        "name": str(attendee.get("name", "Guest")),
                        "role": str(attendee.get("role", "Guest")),
                    })
                    attendee_kind = str(attendee.get("kind", "authored"))
                    if hasattr(self, "dialogue_social_slot"):
                        slot = self.dialogue_social_slot(attendee_actor, attendee_kind)
                        for meeting in slot.get("meetings", []) or []:
                            if isinstance(meeting, dict) and str(meeting.get("event_id", "")) == str(event.get("id", "")):
                                meeting["completed"] = True
                                meeting["completed_day"] = self.quest_absolute_day()
                self.complete_planned_event(str(event.get("id", "")), reason="gathered in the world")
                if hasattr(self, "autosave_with_message"):
                    self.autosave_with_message(f"Completed {event.get('title', 'the gathering')}.")
                return True
            if event_kind in {"relationship_date", "social_outing"} and hasattr(
                self, "dialogue_handle_planned_activity_arrival"
            ):
                if not self.dialogue_handle_planned_activity_arrival(actor, kind, event, participant):
                    return True
                self.record_quest_event(
                    "social_activity", target_id=str(actor.get("id", "")),
                    note=f"Completed {event.get('title', 'a planned activity')} with {actor.get('name', 'a participant')}.",
                )
                if hasattr(self, "dialogue_social_slot"):
                    slot = self.dialogue_social_slot(actor, kind)
                    for meeting in slot.get("meetings", []) or []:
                        if isinstance(meeting, dict) and str(meeting.get("event_id", "")) == str(event.get("id", "")):
                            meeting["completed"] = True
                            meeting["completed_day"] = self.quest_absolute_day()
                self.complete_planned_event(
                    str(participant.get("event_id", "")), reason="shared in the world"
                )
                if hasattr(self, "autosave_with_message"):
                    self.autosave_with_message(
                        f"Completed {event.get('title', 'the planned activity')}."
                    )
                return True
            self.run_unified_npc_conversation(
                actor, kind=kind, first_meeting=False, repeated_today=False,
                agenda_override=(
                    f"We're taking part in {str(event.get('title', 'this plan')).lower()}. "
                    f"My role right now is to {mode.replace('_', ' ')}."
                ),
            )
            self.record_quest_event(
                "talk", target_id=str(actor.get("id", "")),
                note=f"Spoke with {actor.get('name', 'a participant')} during {event.get('title', 'the planned activity')}.",
            )
            if mode in {"meet", "attend"} or str(participant.get("status", "")) == "arrived":
                if hasattr(self, "dialogue_social_slot"):
                    slot = self.dialogue_social_slot(actor, kind)
                    for meeting in slot.get("meetings", []) or []:
                        if isinstance(meeting, dict) and str(meeting.get("event_id", "")) == str(event.get("id", "")):
                            meeting["completed"] = True
                            meeting["completed_day"] = self.quest_absolute_day()
                self.complete_planned_event(str(participant.get("event_id", "")), reason="met in the world")
            return True
        return False

    def render_temporary_participant(self, participant: Dict[str, object]) -> str:
        return colorize("@", C.LANDMARK_ACTIVE)

    def temporary_participant_tile_available(
        self, participant: Dict[str, object], x: int, y: int
    ) -> bool:
        if not self.in_active_bounds(int(x), int(y)):
            return False
        if (int(x), int(y)) == (int(self.state.player_x), int(self.state.player_y)):
            return True
        try:
            return bool(self.passable(int(x), int(y)))
        except Exception:
            return False

    def temporary_participant_route_edge_goals(
        self, participant: Dict[str, object], target: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        width, height = self.active_map_width(), self.active_map_height()
        tx, ty = int(target[0]), int(target[1])
        candidates: List[Tuple[int, int]] = []
        if tx < 0:
            candidates = [(0, y) for y in range(height)]
        elif tx >= width:
            candidates = [(width - 1, y) for y in range(height)]
        elif ty < 0:
            candidates = [(x, 0) for x in range(width)]
        elif ty >= height:
            candidates = [(x, height - 1) for x in range(width)]
        return [
            point for point in candidates
            if self.temporary_participant_tile_available(participant, *point)
        ]

    def update_temporary_participants_after_player_move(self) -> None:
        self.rebase_temporary_participant_positions()
        player = int(self.state.player_x), int(self.state.player_y)
        occupied = set(self.temporary_participant_position_lookup())
        for participant in self.active_temporary_participants():
            if str(participant.get("location", "")) != str(self.state.location):
                continue
            mode = str(participant.get("mode", "accompany"))
            current = int(participant.get("x", player[0])), int(participant.get("y", player[1]))
            if mode == "accompany":
                if manhattan_distance(current, player) <= 2:
                    continue
                goals = [
                    (player[0] + dx, player[1] + dy)
                    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
                    if self.temporary_participant_tile_available(participant, player[0] + dx, player[1] + dy)
                ]
            elif mode == "guide":
                destination = dict(participant.get("destination", {}) or {})
                target = self.quest_destination_local_position(destination)
                target_is_local = bool(target is not None and self.in_active_bounds(*target))
                if target is not None:
                    goals = [target] if target_is_local else self.temporary_participant_route_edge_goals(participant, target)
                else:
                    goals = []
                if target is not None and manhattan_distance(current, target) <= 1:
                    participant["status"] = "arrived"
                    self.record_quest_event("escort", target_id=str(participant.get("event_id", "")), note=f"Arrived with {participant.get('name', 'the guide')}.")
                    if hasattr(self, "set_message"):
                        self.set_message(f"You and {participant.get('name', 'your guide')} have reached {destination.get('label', 'the destination')}. Talk to them to conclude the journey.", "social")
                    continue
            else:
                continue
            if not goals:
                continue
            occupied.discard(current)
            step = shortest_path_step(
                current, goals,
                lambda x, y: self.temporary_participant_tile_available(participant, x, y),
                blocked=occupied, max_nodes=max(256, self.active_map_width() * self.active_map_height()),
            )
            if step:
                participant["x"], participant["y"] = int(step[0]), int(step[1])
                if str(participant.get("location", "")) == "Wilderness" and hasattr(self, "wilderness_world_coords"):
                    world_x, world_y = self.wilderness_world_coords(
                        int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
                        int(step[0]), int(step[1]),
                    )
                    participant["world_x"], participant["world_y"] = int(world_x), int(world_y)
                occupied.add(step)

    def sync_temporary_participants(self) -> None:
        self.update_planned_events()
        self.rebase_temporary_participant_positions()
        for participant in self.active_temporary_participants():
            if str(participant.get("mode", "")) != "accompany":
                continue
            if str(participant.get("location", "")) != str(self.state.location):
                participant.update({
                    "location": str(self.state.location),
                    "x": int(self.state.player_x), "y": int(self.state.player_y),
                })
                if str(self.state.location) == "Wilderness" and hasattr(self, "wilderness_world_coords"):
                    world_x, world_y = self.wilderness_world_coords(
                        int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y),
                        int(self.state.player_x), int(self.state.player_y),
                    )
                    participant["world_x"], participant["world_y"] = int(world_x), int(world_y)


__all__ = ["QuestSystemMixin"]
