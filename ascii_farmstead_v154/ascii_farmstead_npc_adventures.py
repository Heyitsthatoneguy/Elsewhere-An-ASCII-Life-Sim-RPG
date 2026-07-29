from __future__ import annotations

"""Persistent, bounded progression and regional adventures for town residents."""

from typing import Dict, Iterable, List, Optional, Tuple


NPC_ADVENTURE_ROLES = {
    "Sheriff", "Deputy", "Miner", "Blacksmith", "Mechanic", "Carpenter",
    "Carpenter Apprentice", "Botanist", "Fisher", "Courier", "Scholar",
    "Doctor", "Nurse", "Gardener", "Merchant", "Settler",
}
GENERATED_ADVENTURE_ROLES = {
    "Deputy", "Nurse", "Mechanic", "Carpenter Apprentice", "Gardener", "Settler",
}

ROLE_LOADOUTS: Dict[str, Tuple[str, str, str]] = {
    "Sheriff": ("Patrol Saber", "Roadwarden Coat", "Lawkeeper"),
    "Deputy": ("Patrol Spear", "Roadwarden Coat", "Lawkeeper"),
    "Miner": ("Miner's Pick", "Reinforced Workwear", "Delver"),
    "Blacksmith": ("Forge Hammer", "Leather Apron", "Vanguard"),
    "Mechanic": ("Mechanic's Wrench", "Padded Workcoat", "Tinkerer"),
    "Carpenter": ("Wood Axe", "Leather Apron", "Vanguard"),
    "Carpenter Apprentice": ("Wood Axe", "Padded Workcoat", "Scout"),
    "Botanist": ("Field Knife", "Weatherproof Cloak", "Naturalist"),
    "Fisher": ("Boat Hook", "Weatherproof Cloak", "Scout"),
    "Courier": ("Walking Staff", "Traveling Leathers", "Scout"),
    "Scholar": ("Walking Staff", "Weatherproof Cloak", "Researcher"),
    "Doctor": ("Walking Staff", "Padded Workcoat", "Medic"),
    "Nurse": ("Field Knife", "Padded Workcoat", "Medic"),
    "Gardener": ("Pruning Blade", "Reinforced Workwear", "Naturalist"),
    "Merchant": ("Traveling Blade", "Traveling Leathers", "Scout"),
    "Settler": ("Wood Axe", "Reinforced Workwear", "Vanguard"),
}

GEAR_PREFIXES = ("Serviceable", "Tempered", "Proven", "Masterwork")


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except Exception:
        return default


def sanitize_npc_progression_records(value: object) -> Dict[str, Dict[str, object]]:
    if not isinstance(value, dict):
        return {}
    clean: Dict[str, Dict[str, object]] = {}
    for npc_id, raw in value.items():
        if not isinstance(raw, dict):
            continue
        history = raw.get("history", [])
        clean[str(npc_id)[:120]] = {
            "level": _bounded_int(raw.get("level", 1), 1, 1, 30),
            "xp": _bounded_int(raw.get("xp", 0), 0, 0, 999999),
            "vocation": str(raw.get("vocation", "Civilian"))[:40],
            "weapon": str(raw.get("weapon", "Walking Staff"))[:80],
            "armor": str(raw.get("armor", "Traveling Clothes"))[:80],
            "gear_tier": _bounded_int(raw.get("gear_tier", 0), 0, 0, 3),
            "courage": _bounded_int(raw.get("courage", 25), 25, 0, 100),
            "journeys": _bounded_int(raw.get("journeys", 0), 0, 0, 9999),
            "victories": _bounded_int(raw.get("victories", 0), 0, 0, 9999),
            "rescues": _bounded_int(raw.get("rescues", 0), 0, 0, 9999),
            "recovery_until_day": _bounded_int(raw.get("recovery_until_day", 0), 0, 0, 9999999),
            "last_adventure_day": _bounded_int(raw.get("last_adventure_day", 0), 0, 0, 9999999),
            "last_outcome": str(raw.get("last_outcome", ""))[:240],
            "history": [
                str(row)[:240] for row in history if str(row or "").strip()
            ][-8:] if isinstance(history, list) else [],
        }
    return clean


class NpcAdventureMixin:
    """Shared progression for authored and procedural adult residents."""

    def npc_progression_store(self) -> Dict[str, Dict[str, object]]:
        life = self.regional_town_life_state()
        records = life.get("npc_progression")
        if not isinstance(records, dict):
            records = {}
            life["npc_progression"] = records
        return records

    @staticmethod
    def npc_adventure_identity(npc: Dict[str, object]) -> str:
        return str(npc.get("id") or npc.get("name") or "resident")[:120]

    def npc_adventure_eligible(self, npc: Dict[str, object]) -> bool:
        age_group = str(npc.get("age_group", npc.get("life_stage", "Adult")))
        return (
            not bool(npc.get("deceased", False))
            and age_group not in {"Baby", "Toddler", "Young Child", "Child", "Teen"}
            and str(npc.get("role", "")) in NPC_ADVENTURE_ROLES
        )

    def npc_progression_record(self, npc: Dict[str, object]) -> Dict[str, object]:
        key = self.npc_adventure_identity(npc)
        store = self.npc_progression_store()
        raw = store.get(key)
        if not isinstance(raw, dict):
            role = str(npc.get("role", "Civilian"))
            weapon, armor, vocation = ROLE_LOADOUTS.get(
                role, ("Walking Staff", "Traveling Clothes", "Civilian")
            )
            raw_traits = npc.get("personality", npc.get("traits", [])) or []
            if isinstance(raw_traits, str):
                traits = {raw_traits}
            else:
                traits = {str(value) for value in raw_traits}
            courage = 25 + (15 if "Bold" in traits else 0) + (10 if "Protective" in traits else 0)
            raw = {
                "level": 1, "xp": 0, "vocation": vocation,
                "weapon": weapon, "armor": armor, "gear_tier": 0,
                "courage": min(80, courage), "journeys": 0, "victories": 0,
                "rescues": 0, "recovery_until_day": 0, "last_adventure_day": 0,
                "last_outcome": "", "history": [],
            }
            store[key] = raw
        return raw

    @staticmethod
    def npc_xp_for_next_level(level: int) -> int:
        return 60 + max(1, int(level)) * 45

    def npc_adventure_refresh_gear(self, npc: Dict[str, object], record: Dict[str, object]) -> None:
        role = str(npc.get("role", "Civilian"))
        base_weapon, base_armor, vocation = ROLE_LOADOUTS.get(
            role, ("Walking Staff", "Traveling Clothes", "Civilian")
        )
        level = int(record.get("level", 1))
        tier = 3 if level >= 10 else 2 if level >= 6 else 1 if level >= 3 else 0
        prefix = GEAR_PREFIXES[tier]
        record["gear_tier"] = tier
        record["weapon"] = f"{prefix} {base_weapon}"
        record["armor"] = f"{prefix} {base_armor}"
        record["vocation"] = vocation

    def award_npc_adventure_xp(self, npc: Dict[str, object], amount: int) -> int:
        record = self.npc_progression_record(npc)
        record["xp"] = int(record.get("xp", 0)) + max(0, int(amount))
        gained = 0
        while int(record["level"]) < 30:
            needed = self.npc_xp_for_next_level(int(record["level"]))
            if int(record["xp"]) < needed:
                break
            record["xp"] = int(record["xp"]) - needed
            record["level"] = int(record["level"]) + 1
            gained += 1
        self.npc_adventure_refresh_gear(npc, record)
        return gained

    def npc_adventure_power(self, npc: Dict[str, object]) -> int:
        record = self.npc_progression_record(npc)
        return (
            int(record.get("level", 1)) * 8
            + int(record.get("gear_tier", 0)) * 12
            + int(record.get("courage", 25)) // 4
        )

    def npc_adventure_profile_lines(self, npc: Dict[str, object]) -> List[str]:
        record = self.npc_progression_record(npc)
        level = int(record.get("level", 1))
        recovery = int(record.get("recovery_until_day", 0))
        today = self.absolute_game_day()
        lines = [
            "",
            "Regional experience:",
            f"Level {level} {record.get('vocation', 'Civilian')}  |  "
            f"XP {record.get('xp', 0)}/{self.npc_xp_for_next_level(level)}",
            f"Equipment: {record.get('weapon')} / {record.get('armor')}",
            f"Journeys: {record.get('journeys', 0)}  |  Victories: {record.get('victories', 0)}",
            f"Disposition: courage {record.get('courage', 25)}/100; "
            + (f"recovering for {recovery - today} more day(s)" if recovery > today else "fit for ordinary duties"),
        ]
        if record.get("last_outcome"):
            lines.append(f"Latest journey: {record['last_outcome']}")
        history = list(record.get("history", []) or [])
        if history:
            lines.extend(["Recent field history:", *[f"- {row}" for row in history[-3:]]])
        elif not self.npc_adventure_eligible(npc):
            lines.append("This resident does not normally undertake dangerous regional work.")
        return lines

    def npc_adventure_dialogue_line(self, npc: Dict[str, object]) -> str:
        record = self.npc_progression_record(npc)
        trip = self.regional_town_life_state().setdefault(
            "resident_trips", {}
        ).get(self.npc_adventure_identity(npc), {})
        if isinstance(trip, dict) and trip:
            return (
                f'"I am preparing for {trip.get("purpose", "regional fieldwork")} near '
                f'{trip.get("destination_name", "the regional roads")}. I expect to return '
                f'{trip.get("expected_return", "soon")}."'
            )
        if int(record.get("recovery_until_day", 0)) > self.absolute_game_day():
            return (
                '"I misjudged a threat on the last route. Recovery is part of fieldwork too; '
                'pretending otherwise only creates a second casualty."'
            )
        if record.get("last_outcome"):
            return f'"My last regional journey {record["last_outcome"]}."'
        if self.npc_adventure_eligible(npc):
            return (
                f'"My {str(record.get("weapon", "equipment")).lower()} is for the road, '
                'not for showing off in town. The sensible victory is getting everyone home."'
            )
        return ""

    def npc_adventure_journal_lines(self) -> List[str]:
        life = self.regional_town_life_state()
        trips = [
            trip for trip in life.get("resident_trips", {}).values()
            if isinstance(trip, dict)
            and str(trip.get("trip_kind", "")) == "regional_adventure"
        ]
        lines = ["", "Resident field journeys:"]
        if trips:
            for trip in sorted(trips, key=lambda row: str(row.get("resident_name", "")))[:8]:
                lines.append(
                    f"- {trip.get('resident_name', 'Resident')}: "
                    f"{trip.get('destination_name', 'Regional Roads')} "
                    f"(return {trip.get('expected_return', 'unknown')}; danger {trip.get('danger', 0)}/100)"
                )
        else:
            lines.append("- No residents are currently away on field journeys.")
        recovering = [
            (npc_id, record)
            for npc_id, record in self.npc_progression_store().items()
            if int(record.get("recovery_until_day", 0)) > self.absolute_game_day()
        ]
        if recovering:
            lines.append("Recovering residents:")
            lines.extend(
                f"- {npc_id}: {int(record['recovery_until_day']) - self.absolute_game_day()} day(s)"
                for npc_id, record in recovering[:6]
            )
        return lines

    @staticmethod
    def npc_adventure_route_chunks(
        trip: Dict[str, object], identity: str = ""
    ) -> List[Tuple[int, int]]:
        """Return a stable Manhattan route between a resident's actual towns."""
        # Existing road projection indexes destination -> home: outbound travel
        # walks the list backward, while return travel walks it forward.
        x = int(trip.get("chunk_x", 0) or 0)
        y = int(trip.get("chunk_y", 0) or 0)
        target_x = int(trip.get("origin_chunk_x", 0) or 0)
        target_y = int(trip.get("origin_chunk_y", 0) or 0)
        path = [(x, y)]
        horizontal_first = sum(map(ord, str(identity))) % 2 == 0
        for axis in (("x", "y") if horizontal_first else ("y", "x")):
            while (x if axis == "x" else y) != (
                target_x if axis == "x" else target_y
            ) and len(path) < 1200:
                if axis == "x":
                    x += 1 if target_x > x else -1
                else:
                    y += 1 if target_y > y else -1
                path.append((x, y))
        return path

    def npc_adventure_prepare_trip(
        self,
        npc: Dict[str, object],
        destination: Dict[str, object],
        route: Dict[str, object],
        *,
        origin: Tuple[int, int] = (0, 0),
        origin_name: str = "Elsewhere",
        purpose: str = "surveying a regional route",
        generated: bool = False,
    ) -> Dict[str, object]:
        today = self.absolute_game_day()
        travel_days = max(1, int(route.get("travel_days", 1)))
        record = self.npc_progression_record(npc)
        record["last_adventure_day"] = today
        distance = max(1, int(route.get("distance_chunks", 1)))
        danger = min(100, 12 + distance * 3 + (18 if route.get("route_condition") == "Hazardous" else 0))
        return {
            "destination_id": str(destination.get("id", "")),
            "destination_name": str(destination.get("name", "Regional Roads")),
            "destination_kind": str(destination.get("kind", "road_service")),
            "chunk_x": int(destination.get("chunk_x", 0)),
            "chunk_y": int(destination.get("chunk_y", 0)),
            "origin_chunk_x": int(origin[0]), "origin_chunk_y": int(origin[1]),
            "origin_name": str(origin_name)[:80],
            "resident_name": str(npc.get("name", "Resident"))[:80],
            "resident_role": str(npc.get("role", "Traveler"))[:50],
            "depart_day_number": today,
            "return_day_number": today + travel_days,
            "expected_return": self.regional_return_date_label(travel_days),
            "purpose": str(purpose)[:180],
            "route_condition": str(route.get("route_condition", "Open")),
            "trip_kind": "regional_adventure",
            "danger": danger,
            "generated_resident": bool(generated),
            "resolved": False,
        }

    def resolve_npc_adventure_trip(
        self, npc: Dict[str, object], trip: Dict[str, object]
    ) -> str:
        if bool(trip.get("resolved", False)):
            return str(trip.get("outcome", "returned safely"))
        record = self.npc_progression_record(npc)
        identity = self.npc_adventure_identity(npc)
        seed = sum(
            (index + 1) * ord(ch)
            for index, ch in enumerate(
                f"{identity}:{trip.get('depart_day_number')}:{trip.get('destination_id')}"
            )
        )
        danger = int(trip.get("danger", 15))
        power = self.npc_adventure_power(npc)
        roll = seed % 100
        if roll + power >= danger + 45:
            outcome = "cleared a dangerous stretch of road and returned with useful field experience"
            xp = 42 + danger // 2
            record["victories"] = int(record.get("victories", 0)) + 1
        elif roll + power >= danger + 12:
            outcome = "completed the journey safely after avoiding unnecessary danger"
            xp = 25 + danger // 3
        else:
            outcome = "returned injured after withdrawing from a threat beyond their preparation"
            xp = 16 + danger // 4
            record["recovery_until_day"] = self.absolute_game_day() + 2
        gained = self.award_npc_adventure_xp(npc, xp)
        record["journeys"] = int(record.get("journeys", 0)) + 1
        record["last_outcome"] = outcome
        history = list(record.get("history", []) or [])
        history.append(f"{trip.get('destination_name', 'Regional Roads')}: {outcome}.")
        record["history"] = history[-8:]
        trip["resolved"] = True
        trip["outcome"] = outcome
        trip["xp_awarded"] = xp
        if gained:
            outcome += f" They reached level {record.get('level')}."
        return outcome

    def ensure_generated_npc_adventure(
        self,
        plan: Dict[str, object],
        population: Dict[str, object],
    ) -> None:
        life = self.regional_town_life_state()
        trips = life.setdefault("resident_trips", {})
        today = self.absolute_game_day()
        origin = (int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0)))
        origin_key = f"{origin[0]},{origin[1]}"
        checks = life.setdefault("npc_adventure_checks", {})
        if int(checks.get(origin_key, -1)) == today:
            return
        checks[origin_key] = today
        residents = [
            resident for resident in population.get("residents", {}).values()
            if (
                isinstance(resident, dict)
                and self.npc_adventure_eligible(resident)
                and str(resident.get("role", "")) in GENERATED_ADVENTURE_ROLES
            )
        ]
        for resident in residents:
            trip = trips.get(self.npc_adventure_identity(resident))
            if isinstance(trip, dict) and trip:
                if today >= int(trip.get("return_day_number", today + 1)):
                    outcome = self.resolve_npc_adventure_trip(resident, trip)
                    trips.pop(self.npc_adventure_identity(resident), None)
                    life.setdefault("event_log", []).append(
                        f"{self.town_npc_day_key()}: {resident.get('name')} {outcome}."
                    )
                return
        if not residents or today % 7 not in {1, 4}:
            return
        candidates = [
            resident for resident in residents
            if int(self.npc_progression_record(resident).get("recovery_until_day", 0)) <= today
            and today - int(self.npc_progression_record(resident).get("last_adventure_day", 0)) >= 6
        ]
        if not candidates:
            return
        candidates.sort(key=lambda resident: self.npc_adventure_identity(resident))
        resident = candidates[(today + sum(map(ord, origin_key))) % len(candidates)]
        destinations = [
            destination for destination in self.regional_real_destinations()
            if (int(destination.get("chunk_x", 0)), int(destination.get("chunk_y", 0))) != origin
        ]
        if not destinations:
            return
        destination = destinations[
            (today + sum(map(ord, self.npc_adventure_identity(resident)))) % len(destinations)
        ]
        route = self.regional_route_profile(destination, self.npc_adventure_identity(resident))
        trips[self.npc_adventure_identity(resident)] = self.npc_adventure_prepare_trip(
            resident,
            destination,
            route,
            origin=origin,
            origin_name=str(plan.get("name", "Wilderness Town")),
            purpose=f"handling {str(resident.get('role', 'resident')).lower()} fieldwork along the regional roads",
            generated=True,
        )
