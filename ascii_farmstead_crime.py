"""Player crime, witnesses, stealth sight lines, and streamlined penalties."""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Set, Tuple

from ascii_farmstead_helpers import quantity_agreement
from ascii_farmstead_support import clear_screen, colorize, normalize_key, read_key
from ascii_farmstead_ui import MenuItem, menu_select, strip_ansi


CRIME_PROFILES: Dict[str, Dict[str, object]] = {
    "theft": {"label": "Theft", "fine": 100, "jail_hours": 8, "reputation": -4},
    "trespass": {"label": "Trespassing", "fine": 50, "jail_hours": 4, "reputation": -2},
    "property_damage": {"label": "Property damage", "fine": 150, "jail_hours": 12, "reputation": -5},
    "civilian_assault": {"label": "Assault", "fine": 250, "jail_hours": 24, "reputation": -8},
}

LAW_ROLE_WORDS = (
    "sheriff", "deputy", "constable", "marshal", "guard", "officer", "lawkeeper",
)
FACING_VECTORS = {
    "UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0),
}

# An unconfronted incident goes cold and is dropped after this many in-game
# minutes, so a bounty does not sit forever in places with no one to enforce it.
CRIME_INCIDENT_EXPIRY_MINUTES = 3 * 1440


class CrimeStealthMixin:
    """A light, readable crime system driven by NPC vision rather than dice."""

    def crime_profile(self, offense: str) -> Dict[str, object]:
        return dict(CRIME_PROFILES.get(str(offense), CRIME_PROFILES["theft"]))

    def crime_is_law_actor(self, actor: Mapping[str, object]) -> bool:
        role = " ".join(
            str(actor.get(key, "") or "")
            for key in ("role", "profession", "job", "title")
        ).casefold()
        return any(word in role for word in LAW_ROLE_WORDS)

    def crime_actor_facing(self, actor: Mapping[str, object]) -> str:
        for key in ("runtime_facing", "facing"):
            facing = str(actor.get(key, "") or "").upper()
            if facing in FACING_VECTORS:
                return facing
        identity = str(actor.get("id", actor.get("name", "npc")) or "npc")
        return tuple(FACING_VECTORS)[sum(ord(char) for char in identity) % 4]

    def crime_actor_awake(self, actor: Mapping[str, object]) -> bool:
        activity = " ".join(
            str(actor.get(key, "") or "")
            for key in ("activity", "runtime_activity")
        ).casefold()
        return not any(word in activity for word in ("sleep", "in bed", "asleep"))

    def crime_actor_vision_range(self, actor: Mapping[str, object]) -> int:
        if not self.crime_actor_awake(actor):
            return 0
        distance = 9 if self.crime_is_law_actor(actor) else 7
        hour = int(getattr(self.state, "hour", 12) or 12)
        if hour < 6 or hour >= 21:
            distance -= 2
        weather = str(getattr(self.state, "weather", "") or "").casefold()
        if weather in {"stormy", "blizzard"}:
            distance -= 2
        elif weather in {"rainy", "snowy"}:
            distance -= 1
        return max(2, distance)

    def crime_current_observers(self) -> List[Dict[str, object]]:
        """Return visible-world people in local map coordinates without duplicates."""
        found: Dict[str, Dict[str, object]] = {}

        def add(actor: object, x: object, y: object, activity: str = "") -> None:
            if not isinstance(actor, Mapping):
                return
            record = actor if isinstance(actor, dict) else dict(actor)
            identity = str(record.get("id", record.get("name", "")) or "")
            if not identity or identity in found:
                return
            hostile_sources = {
                str(row.get("source_npc_id", ""))
                for row in self.crime_world_state().get("civilian_hostiles", [])
                if isinstance(row, dict) and not bool(row.get("defeated", False))
            }
            if identity in hostile_sources:
                return
            try:
                record["_crime_x"], record["_crime_y"] = int(x), int(y)
            except (TypeError, ValueError):
                return
            if activity and not record.get("activity"):
                record["activity"] = activity
            found[identity] = record

        try:
            for (x, y), actor in self.town_npc_position_lookup().items():
                if (
                    getattr(self, "on_wilderness", lambda: False)()
                    and getattr(self, "in_seamless_town_district", lambda: False)()
                    and not getattr(self, "current_procedural_town_plan", lambda: None)()
                ):
                    world_x, world_y = self.home_world_world_for_town_position(int(x), int(y))
                    x = world_x - int(self.state.wilderness_chunk_x) * self.active_map_width()
                    y = world_y - int(self.state.wilderness_chunk_y) * self.active_map_height()
                add(actor, x, y)
        except Exception:
            pass
        if getattr(self, "on_wilderness", lambda: False)():
            try:
                for actor in self.get_wilderness_travelers():
                    add(actor, actor.get("x"), actor.get("y"))
            except Exception:
                pass
            route_sources = (
                ("wilderness_chunk_has_route_hamlet", "route_hamlet_record", "residents", "route_hamlet_resident_position"),
                ("wilderness_chunk_has_route_leisure", "route_leisure_record", "staff", "route_leisure_staff_position"),
                ("wilderness_chunk_has_route_heritage", "route_heritage_record", "caretakers", "route_heritage_caretaker_position"),
            )
            for has_name, record_name, people_key, position_name in route_sources:
                try:
                    if not getattr(self, has_name)(self.state.wilderness_chunk_x, self.state.wilderness_chunk_y):
                        continue
                    for actor in getattr(self, record_name)().get(people_key, ()):
                        x, y, activity = getattr(self, position_name)(actor)
                        add(actor, x, y, activity)
                except Exception:
                    continue
        if hasattr(self, "active_temporary_participants"):
            try:
                for participant in self.active_temporary_participants():
                    if str(participant.get("location", "")) != str(getattr(self.state, "location", "")):
                        continue
                    actor = self.temporary_participant_actor(participant)
                    add(actor, participant.get("x"), participant.get("y"), str(participant.get("purpose", "accompanying you")))
            except Exception:
                pass
        return list(found.values())

    def crime_vision_blocked(self, x: int, y: int) -> bool:
        if not self.in_active_bounds(int(x), int(y)):
            return True
        try:
            tile = str(self.active_map()[int(y)][int(x)])
        except Exception:
            return True
        # On town/wilderness maps a blank space is ordinary open ground (see
        # `passable()`), not a wall -- only treat it as sight-blocking where
        # it actually means unbuilt void, e.g. mines and building interiors.
        open_ground_uses_blank = bool(
            getattr(self, "on_town", lambda: False)() or getattr(self, "on_wilderness", lambda: False)()
        )
        blocking_tiles = {"#", "_"} if open_ground_uses_blank else {"#", " ", "_"}
        if tile in blocking_tiles:
            return True
        try:
            _key, obj_name, anchor_x, anchor_y = self.placed_object_at(int(x), int(y))
            if obj_name and anchor_x is not None and anchor_y is not None:
                rotation = self.object_rotation_for_key(_key, obj_name)
                if not self.object_cell_walkable(obj_name, x, y, anchor_x, anchor_y, rotation):
                    return True
        except Exception:
            pass
        return False

    def crime_line_clear(self, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
        """Bresenham sight check. Only intermediate cells can block the target."""
        x0, y0 = map(int, start)
        x1, y1 = map(int, end)
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx - dy
        while (x0, y0) != (x1, y1):
            twice = 2 * error
            if twice > -dy:
                error -= dy
                x0 += sx
            if twice < dx:
                error += dx
                y0 += sy
            if (x0, y0) != (x1, y1) and self.crime_vision_blocked(x0, y0):
                return False
        return True

    def crime_actor_can_see(self, actor: Mapping[str, object], x: int, y: int) -> bool:
        try:
            ax, ay = int(actor.get("_crime_x", actor.get("x"))), int(actor.get("_crime_y", actor.get("y")))
        except (TypeError, ValueError):
            return False
        fx, fy = FACING_VECTORS[self.crime_actor_facing(actor)]
        dx, dy = int(x) - ax, int(y) - ay
        forward = dx * fx + dy * fy
        lateral = abs(dx * fy - dy * fx)
        concealment = max(0, int(getattr(self, "alchemy_effect_value", lambda _name: 0)("stealth") or 0))
        if (int(x), int(y)) == (int(self.state.player_x), int(self.state.player_y)):
            if bool(getattr(self.state, "crime_crouching", False)):
                concealment += 2
                if self.crime_player_has_cover():
                    concealment += 2
            if self.crime_target_is_dark(int(x), int(y)):
                concealment += 2
        effective_range = max(1, self.crime_actor_vision_range(actor) - concealment)
        if forward < 1 or forward > effective_range:
            return False
        if lateral > max(0, (forward + 1) // 2):
            return False
        return self.crime_line_clear((ax, ay), (int(x), int(y)))

    def crime_sight_tiles(self) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
        if bool(getattr(self, "_crime_sight_frame_ready", False)):
            cached = getattr(self, "_crime_sight_cache", None)
            if isinstance(cached, tuple) and len(cached) == 2:
                return cached
        actors = self.crime_current_observers()
        signature = (
            str(getattr(self.state, "location", "")), id(self.active_map()),
            int(getattr(self.state, "hour", 0)), str(getattr(self.state, "weather", "")),
            max(0, int(getattr(self, "alchemy_effect_value", lambda _name: 0)("stealth") or 0)),
            bool(getattr(self.state, "crime_crouching", False)),
            self.crime_active_lights_signature(),
            tuple(sorted(
                (str(actor.get("id", actor.get("name", ""))), int(actor.get("_crime_x", -1)),
                 int(actor.get("_crime_y", -1)), self.crime_actor_facing(actor),
                 str(actor.get("runtime_activity", actor.get("activity", ""))))
                for actor in actors
            )),
        )
        if signature == getattr(self, "_crime_sight_cache_signature", None):
            if bool(getattr(self, "_crime_sight_frame_active", False)):
                self._crime_sight_frame_ready = True
            return getattr(self, "_crime_sight_cache", (set(), set()))
        civilian: Set[Tuple[int, int]] = set()
        law: Set[Tuple[int, int]] = set()
        width, height = self.active_map_width(), self.active_map_height()
        for actor in actors:
            target = law if self.crime_is_law_actor(actor) else civilian
            ax, ay = int(actor["_crime_x"]), int(actor["_crime_y"])
            radius = self.crime_actor_vision_range(actor)
            for y in range(max(0, ay - radius), min(height, ay + radius + 1)):
                for x in range(max(0, ax - radius), min(width, ax + radius + 1)):
                    if self.crime_actor_can_see(actor, x, y):
                        target.add((x, y))
        self._crime_sight_cache_signature = signature
        self._crime_sight_cache = (civilian, law)
        if bool(getattr(self, "_crime_sight_frame_active", False)):
            self._crime_sight_frame_ready = True
        return civilian, law

    def render_crime_sight_overlay_cell(self, rendered: str, x: int, y: int) -> str:
        if not bool(getattr(self.state, "stealth_mode_enabled", False)):
            return rendered
        civilian, law = self.crime_sight_tiles()
        position = (int(x), int(y))
        if position not in civilian and position not in law:
            return rendered
        glyph = strip_ansi(str(rendered)) or " "
        palette = "\033[48;5;52m\033[97;1m" if position in law else "\033[48;5;58m\033[97m"
        return colorize(glyph[-1], palette)

    def stealth_observers_of_player(self) -> List[Dict[str, object]]:
        x, y = int(self.state.player_x), int(self.state.player_y)
        return [actor for actor in self.crime_current_observers() if self.crime_actor_can_see(actor, x, y)]

    def stealth_status_text(self) -> str:
        observers = self.stealth_observers_of_player()
        if not observers:
            return "Hidden"
        law = sum(1 for actor in observers if self.crime_is_law_actor(actor))
        return f"Observed ({len(observers)}; {law} law)" if law else f"Observed ({len(observers)})"

    def crime_incident_hud_text(self) -> str:
        incident = self.state.crime_incident if isinstance(self.state.crime_incident, dict) else {}
        if str(incident.get("status", "")) != "reported":
            return ""
        return (
            f"WANTED {incident.get('label', 'Crime')} · "
            f"{int(incident.get('fine', 0))}g/{int(incident.get('jail_hours', 0))}h"
        )

    def toggle_stealth_mode(self) -> None:
        self.state.stealth_mode_enabled = not bool(getattr(self.state, "stealth_mode_enabled", False))
        # M is a mode toggle, so it now changes the player's actual stance as
        # well as displaying sight cones.  The P menu remains available for
        # distractions and lamps, and can still adjust the stance directly.
        self.state.crime_crouching = bool(self.state.stealth_mode_enabled)
        self._crime_sight_cache_signature = None
        self.invalidate_draw_cache()
        if self.state.stealth_mode_enabled:
            self.set_message(
                "Stealth mode enabled: you crouch to reduce detection; amber marks civilian sight and red marks law sight."
            )
        else:
            self.set_message("Stealth mode disabled: you stand and move normally.")

    def confirm_crime_action(self, offense: str, *, owner: str = "", detail: str = "") -> bool:
        if not bool(getattr(self.state, "crime_enabled", True)):
            self.set_message("Player crime is disabled in Settings. Nothing was taken.")
            return False
        profile = self.crime_profile(offense)
        witnesses = self.stealth_observers_of_player()
        witness_text = "No one currently has line of sight."
        if witnesses:
            names = ", ".join(str(actor.get("name", actor.get("role", "Someone"))) for actor in witnesses[:4])
            witness_text = f"Currently visible to: {names}."
        if not bool(getattr(self.state, "crime_confirmation_enabled", True)):
            self._crime_action_confirmed = True
            self._crime_action_committed = False
            return True
        extra = [
            f"This is explicitly a CRIME: {profile['label']}.",
            f"If reported: {profile['fine']}g fine or {profile['jail_hours']}-hour jail time skip.",
            witness_text,
        ]
        if owner:
            extra.insert(1, f"Owner: {owner}")
        if detail:
            extra.insert(2 if owner else 1, detail)
        choice = menu_select(
            "Confirm Crime",
            [
                MenuItem(label=f"Commit CRIME: {profile['label']}", value="commit", enabled=True),
                MenuItem(label="Cancel", value="cancel", enabled=True),
            ],
            footer="This action cannot happen accidentally.",
            extra_lines=extra,
        )
        confirmed = bool(choice and choice.value == "commit")
        self._crime_action_confirmed = confirmed
        self._crime_action_committed = False
        if not confirmed:
            self.set_message("Crime cancelled. Nothing was taken.")
        return confirmed

    def mark_stolen_property(self, item_name: str, quantity: int, owner: str = "") -> None:
        if not item_name or int(quantity) <= 0:
            return
        records = self.state.stolen_items
        record = records.setdefault(str(item_name), {"quantity": 0, "owner": str(owner or "")})
        record["quantity"] = max(0, int(record.get("quantity", 0) or 0)) + int(quantity)
        if owner:
            record["owner"] = str(owner)

    def commit_crime_incident(
        self, offense: str, *, owner: str = "", detail: str = "",
        forced_witnesses: Optional[List[Mapping[str, object]]] = None,
    ) -> str:
        if bool(getattr(self, "_crime_action_committed", False)):
            incident = getattr(self.state, "crime_incident", {}) or {}
            return str(incident.get("result_text", ""))
        self._crime_action_committed = True
        profile = self.crime_profile(offense)
        witnesses = list(forced_witnesses) if forced_witnesses is not None else self.stealth_observers_of_player()
        names = [str(actor.get("name", actor.get("role", "Witness"))) for actor in witnesses]
        history = {
            "offense": str(offense), "label": str(profile["label"]), "owner": str(owner),
            "detail": str(detail), "witnessed": bool(witnesses), "witnesses": names,
            "year": int(getattr(self.state, "year", 1)), "season": str(getattr(self.state, "season", "")),
            "day": int(getattr(self.state, "day", 1)), "hour": int(getattr(self.state, "hour", 0)),
        }
        self.state.crime_history.append(history)
        self.state.crime_history = self.state.crime_history[-100:]
        getattr(self, "break_alchemy_stealth", lambda: False)()
        if not witnesses:
            history["result"] = "unseen"
            return " No witness saw the crime."
        incident = dict(history)
        incident.update({
            "fine": int(profile["fine"]), "jail_hours": int(profile["jail_hours"]),
            "reputation": int(profile["reputation"]), "status": "reported", "grace_steps": 2,
            "reported_absolute_minute": self.crime_absolute_minute(),
        })
        self.state.crime_incident = incident
        self.state.social_reputation = max(-1000, int(self.state.social_reputation) + int(profile["reputation"]))
        if self.current_procedural_town_plan() and hasattr(self, "adjust_procedural_town_reputation"):
            self.adjust_procedural_town_reputation(int(profile["reputation"]), f"Witnessed {str(profile['label']).lower()}")
        if any(self.crime_is_law_actor(actor) for actor in witnesses):
            incident["grace_steps"] = 0
            incident["result_text"] = " Law enforcement witnessed the crime."
        else:
            incident["result_text"] = f" Witnessed by {', '.join(names[:3])}; the incident will be reported."
        return str(incident["result_text"])

    def confiscate_stolen_property(self) -> int:
        removed = 0
        evidence = self.crime_world_state().setdefault("evidence_items", {})
        for item_name, record in list(self.state.stolen_items.items()):
            marked = max(0, int(record.get("quantity", 0) or 0)) if isinstance(record, dict) else 0
            carried = max(0, int(self.state.inventory.get(item_name, 0) or 0))
            quantity = min(marked, carried)
            if quantity:
                self.state.inventory[item_name] = carried - quantity
                evidence[item_name] = max(0, int(evidence.get(item_name, 0) or 0)) + quantity
                removed += quantity
        self.state.stolen_items = {}
        return removed

    def crime_guard_confrontation(self) -> None:
        incident = self.state.crime_incident if isinstance(self.state.crime_incident, dict) else {}
        if not incident or str(incident.get("status", "")) != "reported":
            return
        fine, hours = int(incident.get("fine", 100)), int(incident.get("jail_hours", 8))
        choice = menu_select(
            "Stopped by Law Enforcement",
            [
                MenuItem(label=f"Pay fixed fine ({fine}g)", value="fine", enabled=int(self.state.money) >= fine,
                         hint="Closes this incident immediately" if int(self.state.money) >= fine else "not enough money"),
                MenuItem(label=f"Surrender ({hours}-hour time skip)", value="jail", enabled=True,
                         hint="No court scene or real-time waiting"),
                MenuItem(label="Flee", value="flee", enabled=True, hint="The current incident remains active"),
            ],
            footer="Penalty depends only on this incident; prior offenses do not increase it.",
            extra_lines=[
                f"Charge: {incident.get('label', 'Crime')}",
                f"Witnesses: {', '.join(incident.get('witnesses', [])[:4]) or 'reported witness'}",
            ],
        )
        if not choice or choice.value == "flee":
            incident["grace_steps"] = 3
            self.set_message("You flee. Law enforcement will continue looking for you in this area.")
            return
        if choice.value == "fine":
            self.state.money -= fine
            removed = self.confiscate_stolen_property()
            self.state.crime_incident = {}
            suffix = f" {quantity_agreement(removed, 'stolen item')} returned." if removed else ""
            self.autosave_with_message(f"Paid the fixed {fine}g fine.{suffix}")
            return
        self.serve_crime_sentence(hours, str(incident.get("label", "the offense")))

    def serve_crime_sentence(self, hours: int, label: str) -> None:
        remaining = max(1, int(hours)) * 60
        removed = self.confiscate_stolen_property()
        detention_log = self.crime_world_state()["detention_log"]
        detention_log.append({
            "label": str(label), "hours": max(1, int(hours)),
            "date": str(getattr(self.state, "date_label", "")),
            "facility": "nearest sheriff holding cell",
        })
        self.crime_world_state()["detention_log"] = detention_log[-50:]
        self.state.crime_incident = {}
        while remaining > 0:
            step = min(60, remaining)
            self.advance_time(step)
            remaining -= step
        suffix = f" {quantity_agreement(removed, 'stolen item')} returned." if removed else ""
        self.autosave_with_message(f"Served a fixed {hours}-hour sentence for {label.lower()}; time advanced.{suffix}")

    def crime_absolute_minute(self) -> int:
        return (
            int(self.absolute_game_day()) * 1440
            + int(getattr(self.state, "hour", 0) or 0) * 60
            + int(getattr(self.state, "minute", 0) or 0)
        )

    def crime_decay_incident(self) -> None:
        """Drop an unconfronted incident once it has gone cold.

        Places without any law-enforcement presence (the starting town has
        none) could otherwise leave a reported incident active forever.
        """
        incident = self.state.crime_incident if isinstance(self.state.crime_incident, dict) else {}
        if not incident or str(incident.get("status", "")) != "reported":
            return
        reported_at = incident.get("reported_absolute_minute")
        if reported_at is None:
            return
        if self.crime_absolute_minute() - int(reported_at) < CRIME_INCIDENT_EXPIRY_MINUTES:
            return
        label = str(incident.get("label", "the incident"))
        self.state.crime_incident = {}
        self.set_message(f"Enough time has passed that the report of {label.lower()} has gone cold. No charge remains on record.")

    def sheriff_board_menu(self) -> None:
        """Let the player resolve an active incident by walking up to a jail/board.

        Some towns (the starting town among them) have no patrolling
        law-enforcement NPC, so `crime_guard_confrontation` would otherwise
        never trigger there. This gives the player a way to turn themselves
        in and settle an active charge without needing to be caught.
        """
        incident = self.state.crime_incident if isinstance(self.state.crime_incident, dict) else {}
        if not incident or str(incident.get("status", "")) != "reported":
            self.set_message("The jail ledger is quiet. No active charges are on record for you.")
            return
        self.crime_guard_confrontation()

    def crime_update_after_player_move(self) -> None:
        self._crime_sight_cache_signature = None
        incident = self.state.crime_incident if isinstance(self.state.crime_incident, dict) else {}
        if not incident or str(incident.get("status", "")) != "reported":
            return
        grace = max(0, int(incident.get("grace_steps", 0) or 0))
        if grace:
            incident["grace_steps"] = grace - 1
            return
        px, py = int(self.state.player_x), int(self.state.player_y)
        law = [actor for actor in self.crime_current_observers() if self.crime_is_law_actor(actor)]
        for actor in law:
            ax, ay = int(actor["_crime_x"]), int(actor["_crime_y"])
            if self.crime_actor_can_see(actor, px, py) or abs(px - ax) + abs(py - ay) <= 2:
                self.crime_guard_confrontation()
                return
            dx, dy = px - ax, py - ay
            actor["runtime_facing"] = "RIGHT" if abs(dx) >= abs(dy) and dx > 0 else (
                "LEFT" if abs(dx) >= abs(dy) else ("DOWN" if dy > 0 else "UP")
            )
            actor["runtime_activity"] = "searching for a reported suspect"
            actor["runtime_target_x"], actor["runtime_target_y"] = px, py
            if "runtime_x" in actor:
                continue
            try:
                if getattr(self, "on_town_interior", lambda: False)():
                    location = self.town_npc_observed_runtime_location()
                    self.town_npc_move_interior_toward(actor, location, (px, py))
                elif getattr(self, "on_town", lambda: False)():
                    self.town_npc_move_town_toward(actor, (px, py))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Physical stealth actions and world-space crime interactions

    def crime_world_state(self) -> Dict[str, object]:
        state = self.state.crime_world_state
        if not isinstance(state, dict):
            state = {}
            self.state.crime_world_state = state
        state.setdefault("unlocked_doors", [])
        state.setdefault("entered_private_rooms", [])
        state.setdefault("damaged_tiles", {})
        state.setdefault("civilian_hostiles", [])
        state.setdefault("detention_log", [])
        state.setdefault("evidence_items", {})
        return state

    def crime_scope_key(self) -> str:
        location = str(getattr(self.state, "location", "world"))
        if getattr(self, "on_procedural_town_interior", lambda: False)():
            return ":".join((
                location,
                str(getattr(self.state, "current_procedural_settlement_key", "")),
                str(getattr(self.state, "current_procedural_building_id", "")),
                str(int(getattr(self.state, "current_procedural_building_floor", 0) or 0)),
            ))
        if getattr(self, "on_wilderness", lambda: False)():
            return f"Wilderness:{int(self.state.wilderness_chunk_x)},{int(self.state.wilderness_chunk_y)}"
        return location

    def crime_position_key(self, x: int, y: int) -> str:
        return f"{self.crime_scope_key()}:{int(x)},{int(y)}"

    def crime_current_room(self, x: int, y: int) -> Optional[Dict[str, object]]:
        if getattr(self, "on_procedural_town_interior", lambda: False)():
            room = self.procedural_town_room_at_position(int(x), int(y))
            return dict(room) if isinstance(room, dict) else None
        if getattr(self, "on_town_interior", lambda: False)():
            layout_by_location = {
                "GeneralStoreInterior": "general_store", "BlacksmithInterior": "blacksmith",
                "LibraryInterior": "library", "MuseumInterior": "museum",
                "MayorHouseInterior": "mayor_house", "InnInterior": "inn",
                "FurnitureStoreInterior": "furniture_store", "CarpenterStoreInterior": "carpenter",
                "AnimalStoreInterior": "animal_store", "ClinicInterior": "clinic",
                "TownHallInterior": "town_hall", "MarketRowInterior": "market_row",
            }
            layout_id = layout_by_location.get(str(getattr(self.state, "location", "")), "")
            if layout_id:
                try:
                    from ascii_farmstead_authored_interiors import AUTHORED_MODULAR_LAYOUTS
                    from ascii_farmstead_procedural_interiors import procedural_interior_room_plan
                    type_id, variant, program = AUTHORED_MODULAR_LAYOUTS[layout_id]
                    plan = procedural_interior_room_plan(type_id, variant, 1, 0, None, program)
                    for room in plan.get("rooms", ()):
                        x1, y1, x2, y2 = room.get("rect", (0, 0, 0, 0))
                        if int(x1) < int(x) < int(x2) and int(y1) < int(y) < int(y2):
                            result = dict(room)
                            result["id"] = f"authored:{layout_id}:{room.get('id', 'room')}"
                            return result
                except Exception:
                    pass
        return None

    def crime_room_restricted(self, room: Optional[Mapping[str, object]]) -> bool:
        if not isinstance(room, Mapping):
            return False
        privacy = str(room.get("privacy", "public") or "public").casefold()
        return privacy in {"private", "service", "restricted"}

    def crime_player_owns_current_building(self) -> bool:
        return bool(
            getattr(self, "on_player_owned_procedural_residence", lambda: False)()
            or getattr(self, "on_house", lambda: False)()
        )

    def crime_room_key(self, room: Mapping[str, object]) -> str:
        day = f"{int(getattr(self.state, 'year', 1))}:{str(getattr(self.state, 'season', ''))}:{int(getattr(self.state, 'day', 1))}"
        return f"{self.crime_scope_key()}:{room.get('id', room.get('source_id', 'private'))}:{day}"

    def crime_check_trespass_move(self, x: int, y: int, old_x: int, old_y: int) -> bool:
        if self.crime_player_owns_current_building():
            return True
        room = self.crime_current_room(x, y)
        old_room = self.crime_current_room(old_x, old_y)
        if not self.crime_room_restricted(room):
            return True
        if isinstance(old_room, Mapping) and self.crime_room_key(old_room) == self.crime_room_key(room):
            return True
        key = self.crime_room_key(room)
        entered = self.crime_world_state()["entered_private_rooms"]
        if key in entered:
            return True
        role = str(room.get("role", "private room")).replace("_", " ")
        if not self.confirm_crime_action(
            "trespass", owner=self.location_label(),
            detail=f"Crossing this threshold enters a restricted {role}.",
        ):
            return False
        result = self.commit_crime_incident(
            "trespass", owner=self.location_label(), detail=f"Entered restricted {role}",
        )
        entered.append(key)
        self._crime_action_confirmed = False
        self._crime_action_committed = False
        self.set_message(f"You enter the restricted {role}.{result}")
        return True

    def crime_door_private_room(self, x: int, y: int) -> Optional[Dict[str, object]]:
        candidates: List[Dict[str, object]] = []
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            room = self.crime_current_room(int(x) + dx, int(y) + dy)
            if self.crime_room_restricted(room):
                candidates.append(room)
        return next((
            room for room in candidates
            if str(room.get("privacy", "") or "").casefold() == "restricted"
        ), candidates[0] if candidates else None)

    def crime_door_is_locked(self, x: int, y: int) -> bool:
        if self.crime_player_owns_current_building():
            return False
        room = self.crime_door_private_room(x, y)
        if not room:
            return False
        if str(room.get("privacy", "") or "").casefold() != "restricted":
            return False
        return self.crime_position_key(x, y) not in self.crime_world_state()["unlocked_doors"]

    def crime_handle_closed_door(self, x: int, y: int) -> bool:
        if not self.crime_door_is_locked(x, y):
            return False
        room = self.crime_door_private_room(x, y) or {}
        role = str(room.get("role", "private room")).replace("_", " ")
        has_pick = bool(getattr(self, "owns_tool", lambda _name: False)("Lockpick"))
        choice = menu_select(
            "Locked Private Door",
            [
                MenuItem(label="Knock", value="knock", enabled=True, hint="Ask for access without committing a crime"),
                MenuItem(label="CRIME: Pick the lock", value="pick", enabled=has_pick,
                         hint="requires the Lockpick tool" if not has_pick else "hands-on three-pin lock"),
                MenuItem(label="Leave it alone", value="back", enabled=True),
            ],
            footer="The restricted room is clearly marked before any illegal action.",
            extra_lines=[f"Beyond the door: {role.title()}", "Owner access only."],
        )
        if not choice or choice.value == "back":
            self.set_message("You leave the locked door alone.")
            return True
        if choice.value == "knock":
            self.crime_emit_noise(x, y, 4, "knocking at a private door")
            self.set_message("You knock. No one grants access to the restricted room.")
            return True
        self.crime_start_lockpicking(x, y, room)
        return True

    def crime_lockpick_targets(self, x: int, y: int) -> Tuple[int, int, int]:
        seed = sum(ord(char) for char in self.crime_position_key(x, y))
        return tuple(1 + ((seed // divisor) % 7) for divisor in (3, 11, 29))

    def crime_start_lockpicking(self, x: int, y: int, room: Optional[Mapping[str, object]] = None) -> bool:
        if not getattr(self, "owns_tool", lambda _name: False)("Lockpick"):
            self.set_message("You need a Lockpick from a carpenter before you can manipulate this lock.")
            return False
        role = str((room or {}).get("role", "private room")).replace("_", " ")
        if not self.confirm_crime_action(
            "trespass", owner=self.location_label(), detail=f"Pick the lock protecting the {role}.",
        ):
            return False
        targets = self.crime_lockpick_targets(x, y)
        pin, position, mistakes = 0, 4, 0
        automatic = getattr(self, "_crime_lockpick_test_result", None)
        while pin < len(targets) and mistakes < 5:
            target = targets[pin]
            if automatic is None:
                clear_screen()
                print("LOCKPICKING")
                print("=" * 48)
                print(f"Pin {pin + 1}/3   Noise mistakes: {mistakes}/5")
                print()
                print("Tumbler: " + " ".join("^" if index == position else "·" for index in range(1, 8)))
                difference = abs(position - target)
                tension = "clicking" if difference == 0 else "binding" if difference == 1 else "loose"
                print(f"Tension: {tension}")
                print()
                print("Left/Right or A/D adjust | Z/Enter set pin | B/X/Esc cancel")
                key = normalize_key(read_key())
            else:
                key = "z"
                position = target if bool(automatic) else ((target % 7) + 1)
            if key in {"b", "x", "q", "\x1b", "\t"}:
                self.set_message("You withdraw the lockpick without opening the door.")
                self._crime_action_confirmed = False
                return False
            if key in {"a", "LEFT"}:
                position = 7 if position <= 1 else position - 1
                continue
            if key in {"d", "RIGHT"}:
                position = 1 if position >= 7 else position + 1
                continue
            if key not in {"z", "\r", "\n"}:
                continue
            if position == target:
                pin += 1
                position = 4
            else:
                mistakes += 1
                self.crime_emit_noise(x, y, 3 + mistakes, "a lockpick scraping in a private lock")
                if automatic is not None:
                    break
        if pin < len(targets):
            result = self.commit_crime_incident(
                "trespass", owner=self.location_label(), detail="Attempted to pick a private lock",
            )
            self._crime_action_confirmed = False
            self._crime_action_committed = False
            self.set_message(f"The lock resists you; the attempt made too much noise.{result}")
            return False
        self.crime_world_state()["unlocked_doors"].append(self.crime_position_key(x, y))
        result = self.commit_crime_incident(
            "trespass", owner=self.location_label(), detail=f"Picked the lock protecting the {role}",
        )
        grid = self.active_map()
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
            grid[y][x] = "|"
        self.crime_emit_noise(x, y, 2, "a lock opening")
        self._crime_action_confirmed = False
        self._crime_action_committed = False
        self.set_message(f"The final pin settles and the private door opens.{result}")
        return True

    def crime_apply_world_mutations(self) -> None:
        mutations = self.crime_world_state().get("damaged_tiles", {})
        if not isinstance(mutations, dict):
            return
        prefix = self.crime_scope_key() + ":"
        grid = self.active_map()
        for key, replacement in mutations.items():
            if not str(key).startswith(prefix):
                continue
            try:
                coords = str(key)[len(prefix):]
                x_text, y_text = coords.split(",", 1)
                x, y = int(x_text), int(y_text)
                if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
                    grid[y][x] = str(replacement)[:1] or "."
            except Exception:
                continue

    def crime_property_damage_candidate(self, tool: str, x: int, y: int) -> bool:
        if self.crime_player_owns_current_building() or not self.in_active_bounds(x, y):
            return False
        if not (
            getattr(self, "on_town_interior", lambda: False)()
            or getattr(self, "on_procedural_town_interior", lambda: False)()
            or getattr(self, "on_authored_town_residence", lambda: False)()
        ):
            return False
        if str(tool) not in {"Hammer", "Axe", "Pickaxe"}:
            return False
        tile = str(self.active_map()[int(y)][int(x)])
        if tile in {"D", "<", ">", "U", "&"}:
            return False
        if tile in {"#", "_", "|", "-"}:
            return True
        try:
            return bool(self.starting_town_catalog_furniture_at(x, y)) or bool(
                self.procedural_town_catalog_furniture_at(x, y)
            )
        except Exception:
            return False

    def crime_damage_property(self, tool: str, x: int, y: int) -> bool:
        if not self.crime_property_damage_candidate(tool, x, y):
            return False
        tile = str(self.active_map()[int(y)][int(x)])
        label = "door" if tile in {"_", "|"} else "wall or fixture" if tile in {"#", "-"} else "furniture"
        if not self.confirm_crime_action(
            "property_damage", owner=self.location_label(),
            detail=f"Use the {tool} to deliberately damage this {label}.",
        ):
            return True
        if not self.spend_stamina(5):
            self._crime_action_confirmed = False
            return True
        replacement = "|" if tile in {"_", "|"} else "."
        damaged_cells = [(int(x), int(y))]
        try:
            furniture = self.catalog_furniture_at(x, y)
        except Exception:
            furniture = None
        if isinstance(furniture, dict):
            anchor_x = int(x) - int(furniture.get("offset_x", 0) or 0)
            anchor_y = int(y) - int(furniture.get("offset_y", 0) or 0)
            width = max(1, int(furniture.get("width", 1) or 1))
            height = max(1, int(furniture.get("height", 1) or 1))
            damaged_cells = []
            for cell_y in range(anchor_y, anchor_y + height):
                for cell_x in range(anchor_x, anchor_x + width):
                    cell_record = self.catalog_furniture_at(cell_x, cell_y)
                    if isinstance(cell_record, dict) and str(cell_record.get("name")) == str(furniture.get("name")):
                        damaged_cells.append((cell_x, cell_y))
        for cell_x, cell_y in damaged_cells:
            self.crime_world_state()["damaged_tiles"][self.crime_position_key(cell_x, cell_y)] = replacement
            self.active_map()[cell_y][cell_x] = replacement
        self.crime_emit_noise(x, y, 9, f"{tool.lower()} striking property")
        result = self.commit_crime_incident(
            "property_damage", owner=self.location_label(), detail=f"Damaged a {label} with a {tool}",
        )
        self._crime_action_confirmed = False
        self._crime_action_committed = False
        self.autosave_with_message(f"You break the {label} with the {tool}.{result}")
        return True

    def crime_target_is_dark(self, x: int, y: int) -> bool:
        if not (
            getattr(self, "on_town_interior", lambda: False)()
            or getattr(self, "on_procedural_town_interior", lambda: False)()
            or getattr(self, "on_house", lambda: False)()
        ):
            return False
        try:
            return not any(
                max(abs(int(x) - lx), abs(int(y) - ly)) <= 4
                for lx, ly in self.active_furniture_light_positions()
            )
        except Exception:
            return False

    def crime_active_lights_signature(self) -> Tuple[Tuple[int, int], ...]:
        if not (
            getattr(self, "on_town_interior", lambda: False)()
            or getattr(self, "on_procedural_town_interior", lambda: False)()
            or getattr(self, "on_house", lambda: False)()
        ):
            return ()
        try:
            return tuple(self.active_furniture_light_positions())
        except Exception:
            return ()

    def crime_player_has_cover(self) -> bool:
        px, py = int(self.state.player_x), int(self.state.player_y)
        try:
            tile = str(self.active_map()[py][px])
        except Exception:
            tile = "."
        if tile in {"T", "^", "*", "S", "V"}:
            return True
        return any(
            self.crime_vision_blocked(px + dx, py + dy)
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
        )

    def crime_emit_noise(self, x: int, y: int, radius: int, label: str = "noise") -> int:
        alerted = 0
        for actor in self.crime_current_observers():
            ax, ay = int(actor.get("_crime_x", -99)), int(actor.get("_crime_y", -99))
            if abs(ax - int(x)) + abs(ay - int(y)) > max(1, int(radius)):
                continue
            dx, dy = int(x) - ax, int(y) - ay
            actor["runtime_facing"] = "RIGHT" if abs(dx) >= abs(dy) and dx > 0 else (
                "LEFT" if abs(dx) >= abs(dy) else ("DOWN" if dy > 0 else "UP")
            )
            actor["runtime_activity"] = f"investigating {label}"
            actor["runtime_target_x"], actor["runtime_target_y"] = int(x), int(y)
            alerted += 1
        self._crime_sight_cache_signature = None
        return alerted

    def crime_throw_distraction(self) -> bool:
        clear_screen()
        print("THROW DISTRACTION")
        print("=" * 48)
        print("Choose a direction with WASD/Arrows/numpad. B/X/Esc cancels.")
        while True:
            key = normalize_key(read_key())
            if key in {"b", "x", "q", "\x1b", "\t"}:
                self.set_message("You keep the stone in your hand.")
                return False
            movement = getattr(__import__("ascii_farmstead_support"), "movement_delta_for_key")(key)
            if not movement or tuple(movement) == (0, 0):
                continue
            dx, dy = movement
            x, y = int(self.state.player_x), int(self.state.player_y)
            for _step in range(5):
                nx, ny = x + int(dx), y + int(dy)
                if self.crime_vision_blocked(nx, ny):
                    break
                x, y = nx, ny
            self.crime_emit_noise(x, y, 8, "a thrown stone clattering")
            self.advance_time(1)
            self.set_message(f"A stone clatters at ({x},{y}); nearby people turn to investigate.")
            return True

    def crime_stealth_action_menu(self) -> None:
        crouching = bool(getattr(self.state, "crime_crouching", False))
        nearby_light = self.crime_nearby_active_light()
        choice = menu_select(
            "Stealth Actions",
            [
                MenuItem(label="Stand normally" if crouching else "Crouch and keep low", value="crouch", enabled=True,
                         hint="Crouching is stronger beside cover"),
                MenuItem(label="Throw a stone distraction", value="distract", enabled=True,
                         hint="choose a direction; nearby people face the sound"),
                MenuItem(label="Extinguish nearby lamp", value="light", enabled=nearby_light is not None,
                         hint="creates a darker hiding area" if nearby_light else "no lit lamp within reach"),
                MenuItem(label="Back", value="back", enabled=True),
            ],
            footer="M toggles the full crouched stealth mode and exact sight cones. Darkness and cover improve concealment.",
            extra_lines=[f"Current visibility: {self.stealth_status_text()}"],
        )
        if not choice or choice.value == "back":
            return
        if choice.value == "crouch":
            self.state.crime_crouching = not crouching
            self._crime_sight_cache_signature = None
            self.invalidate_draw_cache()
            self.set_message("You crouch and move carefully." if self.state.crime_crouching else "You stand and move normally.")
        elif choice.value == "distract":
            self.crime_throw_distraction()
        elif choice.value == "light" and nearby_light is not None:
            if not self.use_catalog_furniture_action_at(*nearby_light):
                self.set_message("That light cannot be reached from here.")

    def crime_nearby_active_light(self) -> Optional[Tuple[int, int]]:
        try:
            px, py = int(self.state.player_x), int(self.state.player_y)
            return next((
                (x, y) for x, y in self.active_furniture_light_positions()
                if max(abs(px - int(x)), abs(py - int(y))) <= 1
            ), None)
        except Exception:
            return None

    def crime_actor_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        for actor in self.crime_current_observers():
            if (int(actor.get("_crime_x", -1)), int(actor.get("_crime_y", -1))) == (int(x), int(y)):
                return actor
        return None

    def crime_npc_interaction_menu(self, actor: Mapping[str, object]) -> bool:
        choice = menu_select(
            str(actor.get("name", "Person")),
            [
                MenuItem(label="Talk normally", value="talk", enabled=True),
                MenuItem(label="Create a distraction nearby", value="distract", enabled=True,
                         hint="makes them look away from you"),
                MenuItem(label="CRIME: Assault", value="assault", enabled=True,
                         hint="starts map-native combat; the victim is always a witness"),
                MenuItem(label="Back", value="back", enabled=True),
            ],
            footer="Hostile actions are separated and clearly marked.",
        )
        if not choice or choice.value == "back":
            return True
        if choice.value == "talk":
            return False
        if choice.value == "distract":
            self.crime_throw_distraction()
            return True
        self.crime_assault_actor(actor)
        return True

    def crime_assault_actor(self, actor: Mapping[str, object]) -> bool:
        if self.crime_is_law_actor(actor):
            detail = "Attacking law enforcement starts a dangerous fight."
        else:
            detail = "Attacking this person starts map-native combat."
        if not self.confirm_crime_action(
            "civilian_assault", owner=str(actor.get("name", "Civilian")), detail=detail,
        ):
            return False
        victim = actor if isinstance(actor, dict) else dict(actor)
        other_witnesses = self.stealth_observers_of_player()
        forced = [victim] + [row for row in other_witnesses if str(row.get("id")) != str(victim.get("id"))]
        result = self.commit_crime_incident(
            "civilian_assault", owner=str(victim.get("name", "Civilian")),
            detail="Initiated an unprovoked attack", forced_witnesses=forced,
        )
        if not getattr(self, "on_wilderness", lambda: False)():
            victim["runtime_activity"] = "fleeing after an assault"
            self.state.social_reputation = max(-1000, int(self.state.social_reputation) - 2)
            self.set_message(f"You strike at {victim.get('name', 'the civilian')}; they flee and call for help.{result}")
            self._crime_action_confirmed = False
            self._crime_action_committed = False
            return True
        enemy = {
            "id": f"civilian-hostile:{victim.get('id', victim.get('name', 'npc'))}",
            "source_npc_id": str(victim.get("id", "")),
            "species": str(victim.get("name", "Civilian")),
            "role": str(victim.get("role", "Resident")),
            "field_combat_kind": "civilian",
            "chunk_x": int(self.state.wilderness_chunk_x), "chunk_y": int(self.state.wilderness_chunk_y),
            "x": int(victim.get("_crime_x", victim.get("x", self.state.player_x + 1))),
            "y": int(victim.get("_crime_y", victim.get("y", self.state.player_y))),
            "floor": max(1, int(getattr(self.state, "combat_level", 1))),
            "behavior": "aggressive" if self.crime_is_law_actor(victim) else "skirmisher",
            "alert": True, "defeated": False, "boss": False,
        }
        hostiles = self.crime_world_state()["civilian_hostiles"]
        hostiles[:] = [row for row in hostiles if str(row.get("id")) != str(enemy["id"])]
        hostiles.append(enemy)
        self.begin_wilderness_field_combat(enemy, reason="unprovoked assault")
        self._crime_action_confirmed = False
        self._crime_action_committed = False
        self.set_message(f"{victim.get('name', 'The civilian')} defends themself as the assault is reported.{result}")
        return True

    def crime_civilian_combat_enemies(self) -> List[Dict[str, object]]:
        if not getattr(self, "on_wilderness", lambda: False)():
            return []
        cx, cy = int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
        return [
            row for row in self.crime_world_state().get("civilian_hostiles", [])
            if isinstance(row, dict) and not bool(row.get("defeated", False))
            and (int(row.get("chunk_x", 0)), int(row.get("chunk_y", 0))) == (cx, cy)
        ]

    def crime_resolve_civilian_enemy(self, enemy: Dict[str, object]) -> List[str]:
        enemy["defeated"] = True
        enemy["alert"] = False
        source_id = str(enemy.get("source_npc_id", ""))
        try:
            source = self.npc_record_by_id(source_id)
        except Exception:
            source = None
        if isinstance(source, dict):
            source["runtime_activity"] = "recovering from an assault"
            source["crime_injured_until_day"] = int(getattr(self.state, "day", 1)) + 2
        return [f"{enemy.get('species', 'The civilian')} is incapacitated, not killed. The assault remains on record."]

    def crime_sheriff_board_menu(self) -> bool:
        building = getattr(self, "current_procedural_town_building", lambda: None)()
        if not isinstance(building, dict) or str(building.get("type_id", "")) != "sheriff_office":
            return False
        incident = self.state.crime_incident if isinstance(self.state.crime_incident, dict) else {}
        choice = menu_select(
            "Sheriff Office Notice Board",
            [
                MenuItem(label="Posted bounties", value="bounties", enabled=True),
                MenuItem(label="Your wanted notice", value="wanted", enabled=bool(incident),
                         hint=self.crime_incident_hud_text() or "no active notice"),
                MenuItem(label=f"Pay current fine ({int(incident.get('fine', 0))}g)", value="pay",
                         enabled=bool(incident) and int(self.state.money) >= int(incident.get("fine", 0))),
                MenuItem(label="Surrender at the front desk", value="surrender", enabled=bool(incident),
                         hint="fixed jail time skip; no court sequence"),
                MenuItem(label="Back", value="back", enabled=True),
            ],
            footer="Cells, records, armory, and evidence storage are physical restricted rooms in this building.",
        )
        if not choice or choice.value == "back":
            return True
        if choice.value == "bounties":
            self.show_bounty_board_menu()
        elif choice.value == "wanted":
            self.vertical_panel_view(
                "Wanted Notice",
                [
                    f"Name: {getattr(self.state, 'player_name', 'Player')}",
                    f"Charge: {incident.get('label', 'Unknown')}",
                    f"Fixed fine: {incident.get('fine', 0)}g",
                    f"Alternative sentence: {incident.get('jail_hours', 0)} hours",
                    f"Witnesses: {', '.join(incident.get('witnesses', [])) or 'none listed'}",
                    "", "Prior offenses do not increase this penalty.",
                ], 48, 20,
            )
        elif choice.value == "pay":
            fine = int(incident.get("fine", 0))
            self.state.money -= fine
            removed = self.confiscate_stolen_property()
            self.state.crime_incident = {}
            self.autosave_with_message(
                f"Paid the posted {fine}g fine. {quantity_agreement(removed, 'stolen item')} returned."
            )
        elif choice.value == "surrender":
            self.serve_crime_sentence(int(incident.get("jail_hours", 1)), str(incident.get("label", "the offense")))
        return True
