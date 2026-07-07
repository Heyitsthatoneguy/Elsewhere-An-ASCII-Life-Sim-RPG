from __future__ import annotations

"""NPC, relationship, family, dialogue, and NPC-scene behavior.

NpcMixin expects a FarmGame-like object that provides maps, UI panels, item
helpers, errands, birthday helpers, and persistence. Keeping this large cluster
here gives future NPC work a dedicated surface while preserving the legacy
entry point and save behavior.
"""

import random
import textwrap
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import *  # noqa: F403
from ascii_farmstead_helpers import *  # noqa: F403
from ascii_farmstead_inventory import *  # noqa: F403
from ascii_farmstead_state import GameState
from ascii_farmstead_support import (
    C,
    VALID_GAME_LOCATIONS,
    append_debug_log,
    clear_screen,
    colorize,
    normalize_key,
    read_key,
)
from ascii_farmstead_ui import MenuItem, pad_to, text_entry_menu
from ascii_battle_prototype.combat.classes import class_defs as tactical_class_defs


class NpcMixin:
    def town_npc_safe_tile_label(self, x: int, y: int) -> str:
        tile = self.town_map[y][x] if 0 <= y < len(self.town_map) and 0 <= x < len(self.town_map[y]) else "#"
        return {
            "=": "road",
            ":": "plaza path",
            ",": "park grass",
            ".": "grass",
        }.get(tile, "town")

    def town_npc_mood(self, npc: Dict[str, object]) -> str:
        friendship = self.town_npc_relationship(str(npc.get("id", "")))
        period = self.town_time_period()
        if friendship >= 100:
            return "trusting"
        if friendship >= 60:
            return "friendly"
        if self.town_weather_is_severe_for_routines():
            return "tense"
        if self.town_weather_is_bad_for_routines():
            return "weather-wary"
        if friendship < 0:
            return "guarded"
        if period == "morning":
            return "busy"
        if period == "evening":
            return "winding down"
        return "available"

    def town_npc_role_color(self, npc: Dict[str, object]) -> str:
        role = str(npc.get("role", "Villager"))
        friendship = self.town_npc_relationship(str(npc.get("id", "")))
        if friendship < 0:
            return C.DIM
        if friendship >= 100:
            return C.PLAYER
        role_colors = {
            "Mayor": C.CROP_READY,
            "Seed Seller": C.SPRING_GRASS,
            "Blacksmith": C.STONE,
            "Carpenter": C.WOOD,
            "Animal Keeper": C.HOUSE,
            "Librarian": C.SNOW,
            "Traveler": C.WATER,
            "Doctor": C.RAIN,
            "Innkeeper": C.LAMP,
            "Chef": C.FALL_GRASS,
            "Market Vendor": C.SHOP,
            "Gardener": C.GRASS,
            "Fisher": C.WATER,
            "Miner": C.STONE,
            "Kid": C.PLAYER,
            "Courier": C.LAMP,
            "Artist": C.PLACEMENT,
            "Recluse": C.NIGHT,
            "Orchardist": C.FALL_GRASS,
            "Tailor": C.PLACEMENT,
            "Musician": C.LAMP,
            "Beekeeper": C.CROP_READY,
            "Botanist": C.SPRING_GRASS,
            "Mechanic": C.INFRA,
            "Scholar": C.SNOW,
            "Retiree": C.WOOD,
            "Newborn": C.CROP_READY,
            "Infant": C.CROP_READY,
            "Toddler": C.CROP_MID,
            "Young Child": C.SPRING_GRASS,
            "Child": C.PLAYER,
            "Teen": C.WATER,
            "Young Adult": C.PLAYER,
        }
        return role_colors.get(role, C.SHOP)

    def town_npc_near_player(self, npc: Dict[str, object], distance: int = 3) -> bool:
        if not self.on_town() or self.town_npc_is_indoor(npc):
            return False
        try:
            return abs(int(npc.get("x", 0)) - self.state.player_x) + abs(int(npc.get("y", 0)) - self.state.player_y) <= distance
        except Exception:
            return False

    def town_npc_face_player(self, npc: Dict[str, object]):
        try:
            if self.on_house() and str(npc.get("id", "")) == self.state.spouse_npc_id:
                npc_x, npc_y = self.spouse_farmhouse_position()
            elif self.on_town_interior():
                npc_pos = self.town_indoor_npc_positions().get(str(npc.get("id", "")))
                if not npc_pos:
                    return
                npc_x, npc_y = npc_pos
            else:
                npc_x, npc_y = int(npc.get("x", 0)), int(npc.get("y", 0))
            dx = self.state.player_x - npc_x
            dy = self.state.player_y - npc_y
        except Exception:
            return
        if abs(dx) > abs(dy):
            npc["facing"] = "RIGHT" if dx > 0 else "LEFT"
        elif dy:
            npc["facing"] = "DOWN" if dy > 0 else "UP"

    def town_npc_activity_label(self, npc: Dict[str, object]) -> str:
        if self.is_household_child_npc(npc):
            child = self.child_record_from_npc(npc)
            return self.household_child_activity_label(child) if child else "growing up at home"
        role = str(npc.get("role", "Villager"))
        phase = self.town_npc_current_routine_phase(npc)
        entry = self.town_npc_schedule_raw_value(npc)
        entry_activity = str(entry.get("activity", "")) if isinstance(entry, dict) else ""
        if entry_activity:
            if self.town_npc_is_indoor(npc):
                place = self.town_npc_indoor_location(npc)
                if place and place.lower() not in entry_activity.lower():
                    return f"{entry_activity} inside {place}"
            return entry_activity
        if self.town_npc_is_indoor(npc):
            place = self.town_npc_indoor_location(npc)
            if str(place).lower() == "farmhouse":
                return "settling into farmhouse life"
            indoor_work = {
                "Mayor": "reviewing town requests",
                "Seed Seller": "sorting seed stock",
                "Blacksmith": "checking tool orders",
                "Carpenter": "drafting build plans",
                "Animal Keeper": "checking animal-care notes",
                "Librarian": "cataloguing records",
                "Doctor": "preparing clinic supplies",
                "Innkeeper": "keeping the inn running",
                "Chef": "testing pantry recipes",
                "Market Vendor": "counting market stock",
                "Tailor": "sorting fabric samples",
                "Mechanic": "tuning a small mechanism",
                "Scholar": "checking civic records",
            }
            return f"{indoor_work.get(role, 'working')} inside {place}"
        if self.town_weather_is_severe_for_routines():
            return "moving carefully between gusts"
        if self.town_weather_is_bad_for_routines():
            return "keeping to sheltered paths"
        routine_activity = self.town_npc_role_activity(npc, phase)
        if routine_activity and routine_activity != "following their routine":
            return routine_activity
        period = self.town_time_period()
        activities = {
            "Mayor": {"morning": "checking civic routes", "midday": "listening for town concerns", "evening": "heading back to review notes"},
            "Seed Seller": {"morning": "opening the seed ledger", "midday": "watching what farmers buy", "evening": "counting tomorrow's packets"},
            "Blacksmith": {"morning": "hauling coal and scrap", "midday": "testing tool balance", "evening": "letting the forge cool"},
            "Carpenter": {"morning": "measuring service paths", "midday": "studying building footprints", "evening": "checking road grades"},
            "Animal Keeper": {"morning": "checking feed orders", "midday": "watching animal store traffic", "evening": "planning tomorrow's care route"},
            "Librarian": {"morning": "opening the records", "midday": "cross-checking town notes", "evening": "taking field observations"},
            "Traveler": {"morning": "testing shortcuts", "midday": "mapping park routes", "evening": "watching the east road"},
            "Doctor": {"morning": "checking clinic stock", "midday": "making wellness rounds", "evening": "looking for quiet air"},
            "Innkeeper": {"morning": "preparing the common room", "midday": "collecting town gossip", "evening": "welcoming travelers"},
            "Chef": {"morning": "planning meals", "midday": "searching for fresh ingredients", "evening": "thinking about specials"},
            "Market Vendor": {"morning": "checking stall space", "midday": "pricing small goods", "evening": "watching customer flow"},
            "Gardener": {"morning": "tending park edges", "midday": "checking seasonal growth", "evening": "listening to the grass"},
            "Fisher": {"morning": "reading the water", "midday": "tracking fish movement", "evening": "checking river shadows"},
            "Miner": {"morning": "testing stone chips", "midday": "talking shop by the forge", "evening": "counting old mine stories"},
            "Kid": {"morning": "looking for shortcuts", "midday": "making up park rules", "evening": "racing the streetlamps home"},
            "Courier": {"morning": "running delivery loops", "midday": "checking road timing", "evening": "making one last circuit"},
            "Artist": {"morning": "sketching light", "midday": "studying park color", "evening": "planning banners"},
            "Recluse": {"morning": "watching the north road", "midday": "keeping to quiet edges", "evening": "counting wilderness sounds"},
            "Orchardist": {"morning": "checking park soil", "midday": "planning orchard rows", "evening": "noting where shade falls"},
            "Tailor": {"morning": "cutting fabric samples", "midday": "studying work-worn clothes", "evening": "matching colors to people"},
            "Musician": {"morning": "warming up scales", "midday": "listening to road rhythms", "evening": "saving melodies for the inn"},
            "Beekeeper": {"morning": "checking flower routes", "midday": "watching pollinators work", "evening": "counting jars and frames"},
            "Botanist": {"morning": "pressing plant samples", "midday": "comparing wild growth", "evening": "looking for cave notes"},
            "Mechanic": {"morning": "tightening small gears", "midday": "studying sprinkler pressure", "evening": "sketching tool ideas"},
            "Scholar": {"morning": "reading old town maps", "midday": "tracking civic changes", "evening": "writing careful notes"},
            "Retiree": {"morning": "checking the south benches", "midday": "pretending not to gossip", "evening": "heading home slowly"},
        }
        return activities.get(role, {}).get(period, "following their routine")

    def town_npc_dialogue_data(self, npc_or_id) -> Dict[str, object]:
        npc_id = str(npc_or_id.get("id", "")) if isinstance(npc_or_id, dict) else str(npc_or_id)
        data = TOWN_NPC_DIALOGUE_DATA.get(npc_id, {})
        if isinstance(data, dict) and data:
            return data
        npc = (
            npc_or_id
            if isinstance(npc_or_id, dict)
            else self.npc_record_by_id(npc_id)
        )
        if isinstance(npc, dict) and self.is_procedural_npc(npc):
            return {
                "profile": str(
                    npc.get(
                        "friend_secret",
                        "They are building a life where roads and households are still new.",
                    )
                ),
                "motivation": str(
                    npc.get(
                        "goal",
                        "They want their wilderness town to become a lasting home.",
                    )
                ),
                "rumor": str(
                    npc.get(
                        "rumor",
                        "Caravans carry more stories than their manifests admit.",
                    )
                ),
                "secret": str(
                    npc.get(
                        "friend_secret",
                        "They are still deciding what home means here.",
                    )
                ),
                "courtship": (
                    f"You and {npc.get('name', 'the resident')} step away from "
                    "the town road and trade stories about the lives you are each trying to build."
                ),
            }
        return {}

    def town_npc_profile_lines(self, npc: Dict[str, object]) -> List[str]:
        data = self.town_npc_dialogue_data(npc)
        profile = str(data.get("profile", "They are finding their place in town one ordinary day at a time."))
        motivation = str(data.get("motivation", "They want the town to work a little better than it did yesterday."))
        rumor = str(data.get("rumor", "People are still learning the shape of the expanded town."))
        lines = [
            f"{npc.get('name')} - {npc.get('role')}",
            "",
            f"Character: {profile}",
            f"Mood: {self.town_npc_mood(npc)}",
            f"Birthday: {self.npc_birthday_label(npc)}",
            f"Activity: {self.town_npc_activity_label(npc)}",
            f"Purpose: {motivation}",
            "",
            f"Current location: {self.town_npc_location_label(npc)}",
            f"Routine: {self.town_npc_routine_brief(npc)}",
            self.town_npc_next_routine_line(npc),
            f"Rumor: {rumor}",
        ]
        reactivity = self.town_npc_reactivity_lines(npc, limit=3)
        if reactivity:
            lines.extend(["", "What they notice:"])
            lines.extend(f"- {line}" for line in reactivity)
        if self.is_marriageable_npc(npc):
            lines.append("")
            lines.extend(self.town_npc_romance_lines(npc))
        return lines

    def town_npc_rumor_lines(self, npc: Dict[str, object]) -> List[str]:
        data = self.town_npc_dialogue_data(npc)
        rumor = str(data.get("rumor", "The town is changing quickly, and people are still choosing what to keep."))
        secret = str(data.get("secret", "There is more happening in town than the notice boards say."))
        friendship = self.town_npc_relationship(str(npc.get("id", "")))
        lines = [f"{npc.get('name')} shares a rumor:", "", rumor]
        if friendship >= 60:
            lines.extend(["", "Because you know each other well, they add:", secret])
        reactivity = self.town_npc_reactivity_lines(npc, limit=1)
        if reactivity:
            lines.extend(["", "They also notice:", reactivity[0]])
        return lines

    def town_npc_reactivity_lines(self, npc: Dict[str, object], limit: int = 3) -> List[str]:
        lines: List[str] = []
        reactive_categories = self.town_npc_reactive_categories()
        for category in self.dialogue_categories_for_npc(npc):
            if category not in reactive_categories:
                continue
            entries = self.contextual_dialogue_entries_for_category(npc, category)
            if not entries:
                continue
            text = str(entries[0].get("text", "")).strip()
            if text and text not in lines:
                lines.append(text)
            if len(lines) >= int(limit):
                break
        return lines

    def town_npc_context_line(self, npc: Dict[str, object]) -> str:
        mood = self.town_npc_mood(npc)
        activity = self.town_npc_activity_label(npc)
        if self.town_npc_is_indoor(npc):
            return f"{npc.get('name', 'They')} is {activity} and seems {mood}."
        ax, ay = self.town_npc_schedule_anchor(npc)
        area = self.town_npc_safe_tile_label(ax, ay)
        return f"{npc.get('name', 'They')} is {activity} by the {area} near {ax},{ay}; mood: {mood}."

    def town_npc_relationship_note(self, npc: Dict[str, object]) -> str:
        points = self.town_npc_relationship(str(npc.get("id", "")))
        if points >= 200:
            return "They trust you with the parts of life that are not easy to explain."
        if points >= 150:
            return "They trust you with decisions and worries that stay out of ordinary conversation."
        if points >= 100:
            return "They trust you enough to drop the town politeness and speak plainly."
        if points >= 60:
            return "They are comfortable when you stop to talk."
        if points >= 25:
            return "They recognize you and remember that you show up."
        if points < 0:
            return "They are careful around you and need a reason to relax."
        return "You are still getting to know each other."

    def procedural_resident_by_id(
        self,
        npc_id: str,
    ) -> Optional[Dict[str, object]]:
        populations = getattr(
            self.state,
            "procedural_settlement_populations",
            {},
        )
        if not isinstance(populations, dict):
            return None
        for population in populations.values():
            if not isinstance(population, dict):
                continue
            residents = population.get("residents", {})
            if not isinstance(residents, dict):
                continue
            resident = residents.get(str(npc_id))
            if isinstance(resident, dict):
                resident["procedural_resident"] = True
                return resident
        return None

    def npc_record_by_id(
        self,
        npc_id: str,
    ) -> Optional[Dict[str, object]]:
        npc_id = str(npc_id)
        authored = next(
            (
                npc
                for npc in getattr(self.state, "town_npcs", []) or []
                if str(npc.get("id", "")) == npc_id
            ),
            None,
        )
        if authored:
            return authored
        elder = next(
            (
                record
                for record in getattr(self.state, "dynasty_elders", []) or []
                if isinstance(record, dict)
                and str(record.get("id", "")) == npc_id
            ),
            None,
        )
        if elder:
            elder["dynasty_elder"] = True
            return elder
        kin = next(
            (
                record
                for record in getattr(self.state, "dynasty_kin", []) or []
                if isinstance(record, dict)
                and str(record.get("id", "")) == npc_id
            ),
            None,
        )
        if kin:
            kin["dynasty_kin"] = True
            return kin
        return self.procedural_resident_by_id(npc_id)

    def is_procedural_npc(self, npc_or_id: object) -> bool:
        if isinstance(npc_or_id, dict):
            return bool(
                npc_or_id.get("procedural_resident")
                or str(npc_or_id.get("id", "")).startswith("proc:")
            )
        return str(npc_or_id).startswith("proc:")

    def town_npc_name(self, npc_id: str) -> str:
        definition = self.town_npc_definition(str(npc_id))
        if isinstance(definition, dict) and definition:
            return str(definition.get("name", npc_id))
        npc = self.npc_record_by_id(str(npc_id))
        return str(npc.get("name", npc_id)) if npc else str(npc_id)

    def npc_sex(self, npc_or_id: object) -> str:
        npc_id = str(npc_or_id.get("id", "")) if isinstance(npc_or_id, dict) else str(npc_or_id)
        npc = (
            npc_or_id
            if isinstance(npc_or_id, dict)
            else self.npc_record_by_id(npc_id)
        )
        if isinstance(npc, dict) and str(npc.get("sex", "")) in VALID_PLAYER_SEXES:
            return str(npc.get("sex"))
        return NPC_SEX_BY_ID.get(npc_id, "Unknown")

    def is_romance_candidate_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        if (
            bool(npc.get("deceased", False))
            or npc_id in set(
                getattr(self.state, "deceased_spouse_npc_ids", []) or []
            )
        ):
            return False
        if npc_id in ROMANCE_NPC_DATA:
            return True
        return bool(
            self.is_procedural_npc(npc)
            and npc.get("romanceable")
            and str(npc.get("age_group", "")) in {"Adult", "Elder"}
        )

    def is_heterosexual_match_for_player(self, npc: Dict[str, object]) -> bool:
        player_sex = str(getattr(self.state, "player_sex", "Female"))
        npc_sex = self.npc_sex(npc)
        return player_sex in VALID_PLAYER_SEXES and npc_sex in VALID_PLAYER_SEXES and player_sex != npc_sex

    def is_marriageable_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        if not self.is_romance_candidate_npc(npc):
            return False
        return self.state.spouse_npc_id == npc_id or self.is_heterosexual_match_for_player(npc)

    def romance_data_for_npc(self, npc: Dict[str, object]) -> Dict[str, str]:
        data = ROMANCE_NPC_DATA.get(str(npc.get("id", "")), {})
        if isinstance(data, dict) and data:
            return data
        if self.is_procedural_npc(npc):
            traits = [
                str(trait)
                for trait in npc.get("personality_traits", []) or []
            ]
            style = (
                ", ".join(traits[:2]).lower()
                if traits
                else str(npc.get("personality", "quiet and practical")).lower()
            )
            proposal_item = "Wildflower Honey"
            likes = [str(item) for item in npc.get("likes", []) or []]
            for preferred in (
                "Wildflower Honey",
                "Ancient Preserves",
                "Berry Jam",
                "Mushroom Preserve",
                "Wildflowers",
            ):
                if preferred in likes:
                    proposal_item = preferred
                    break
            return {
                "style": style,
                "proposal_item": proposal_item,
                "vow": (
                    f"{npc.get('name', 'They')} promises that wherever the road "
                    "leads, neither of you will have to build a home alone."
                ),
            }
        return {}

    def proposal_item_for_npc(self, npc: Dict[str, object]) -> str:
        return str(self.romance_data_for_npc(npc).get("proposal_item", "Wildflower Honey"))

    def town_npc_dialogue_count(self, npc_id: str) -> int:
        npc_id = str(npc_id)
        recorded = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        procedural = self.procedural_resident_by_id(npc_id)
        if procedural:
            recorded = max(
                recorded,
                int(procedural.get("dialogue_count", 0)),
            )
            self.state.town_npc_dialogue_counts[npc_id] = recorded
        return recorded

    def romance_label_for_npc(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        if not self.is_romance_candidate_npc(npc):
            return "Not romanceable"
        if self.state.spouse_npc_id == npc_id:
            return "Spouse"
        if str(getattr(self.state, "engaged_npc_id", "")) == npc_id:
            return "Engaged"
        if not self.is_heterosexual_match_for_player(npc):
            return "Unavailable"
        points = self.town_npc_relationship(npc_id)
        if npc_id in set(self.state.dating_npc_ids or []):
            return "Ready to propose" if points >= RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP else "Dating"
        if points >= RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP:
            return "Ready to propose"
        if points >= 150:
            return "Trusted"
        if points >= 100:
            return "Close bond"
        if points >= 60:
            return "Courtship ready"
        if points >= 25:
            return "Interested"
        return "New connection"

    def romance_note_for_npc(self, npc: Dict[str, object]) -> str:
        if not self.is_romance_candidate_npc(npc):
            return "They are part of town life, but not a romance candidate."
        npc_id = str(npc.get("id", ""))
        points = self.town_npc_relationship(npc_id)
        if self.state.spouse_npc_id == npc_id:
            return "You are married; the relationship is now about showing up in ordinary ways."
        if self.state.spouse_npc_id:
            return f"You are already married to {self.town_npc_name(self.state.spouse_npc_id)}."
        if str(getattr(self.state, "engaged_npc_id", "")) == npc_id:
            return (
                f"You are engaged. The wedding is scheduled for "
                f"{self.wedding_date_label()}."
            )
        if str(getattr(self.state, "engaged_npc_id", "")):
            return (
                f"You are already engaged to "
                f"{self.town_npc_name(self.state.engaged_npc_id)}."
            )
        if not self.is_heterosexual_match_for_player(npc):
            return "This character is not romantically interested in you."
        if npc_id in set(self.state.dating_npc_ids or []):
            return "You are dating. Daily talks, useful gifts, and time together still matter."
        if points >= 60:
            return "They trust you enough to spend intentional time together."
        return "Build trust through daily conversations, useful gifts, and errands."

    def town_npc_romance_lines(self, npc: Dict[str, object]) -> List[str]:
        if not self.is_marriageable_npc(npc):
            return []
        data = self.romance_data_for_npc(npc)
        npc_id = str(npc.get("id", ""))
        item = self.proposal_item_for_npc(npc)
        points = self.town_npc_relationship(npc_id)
        talks = self.town_npc_dialogue_count(npc_id)
        today = self.town_npc_day_key()
        court_today = self.state.town_npc_last_court_day.get(npc_id) == today
        lines = [
            f"Romance: {self.romance_label_for_npc(npc)}",
            f"Courtship style: {data.get('style', 'warm')}",
            self.romance_note_for_npc(npc),
            f"Wedding ring: {self.state.inventory.get(WEDDING_RING_ITEM, 0)} owned",
            f"Personal proposal touch: {item} ({self.state.inventory.get(item, 0)} owned; optional)",
            f"Proposal: needs {RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP} friendship, {RELATIONSHIP_PROPOSAL_REQUIRED_TALKS} talks, {RELATIONSHIP_PROPOSAL_REQUIRED_COURTSHIP} courtship, and a ring.",
            f"Current: {points} friendship, {talks} talks.",
            f"Courtship time: {self.town_npc_courtship_count(npc_id)}",
            "Courtship: already spent time today" if court_today else "Courtship: available today",
        ]
        return lines

    def can_court_town_npc(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.is_marriageable_npc(npc):
            return False, f"{npc.get('name', 'They')} is not a romance candidate."
        if self.state.spouse_npc_id and self.state.spouse_npc_id != npc_id:
            return False, f"You are already married to {self.town_npc_name(self.state.spouse_npc_id)}."
        if (
            str(getattr(self.state, "engaged_npc_id", "") or "")
            and str(self.state.engaged_npc_id) != npc_id
        ):
            return False, (
                f"You are engaged to "
                f"{self.town_npc_name(self.state.engaged_npc_id)}."
            )
        today = self.town_npc_day_key()
        if self.state.town_npc_last_court_day.get(npc_id) == today:
            return False, f"You already spent courtship time with {npc.get('name', 'them')} today."
        if self.town_npc_relationship(npc_id) < RELATIONSHIP_COURTSHIP_REQUIRED_FRIENDSHIP:
            return False, "Get to know them a little better before courtship."
        return True, "Courtship available."

    def can_start_dating_with_npc(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.is_marriageable_npc(npc):
            return False, f"{npc.get('name', 'They')} is not a romance candidate."
        if self.state.spouse_npc_id:
            return False, f"You are already married to {self.town_npc_name(self.state.spouse_npc_id)}."
        if npc_id in set(self.state.dating_npc_ids or []):
            return False, "You are already dating."
        points = self.town_npc_relationship(npc_id)
        if points < RELATIONSHIP_DATING_REQUIRED_FRIENDSHIP:
            return False, f"Dating needs {RELATIONSHIP_DATING_REQUIRED_FRIENDSHIP} friendship. Current: {points}."
        talks = self.town_npc_dialogue_count(npc_id)
        if talks < RELATIONSHIP_DATING_REQUIRED_TALKS:
            return False, f"Dating needs more conversations: {talks}/{RELATIONSHIP_DATING_REQUIRED_TALKS}."
        courtships = self.town_npc_courtship_count(npc_id)
        if courtships < RELATIONSHIP_DATING_REQUIRED_COURTSHIP:
            return False, f"Dating needs more courtship time: {courtships}/{RELATIONSHIP_DATING_REQUIRED_COURTSHIP}."
        return True, "Ready to start dating."

    def town_npc_courtship_scene_line(self, npc: Dict[str, object]) -> str:
        data = self.town_npc_dialogue_data(npc)
        scene = data.get("courtship")
        if scene:
            return str(scene)
        return f"You spend quiet time with {npc.get('name')}, away from the usual errands."

    def court_town_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        ok, reason = self.can_court_town_npc(npc)
        if not ok:
            self.vertical_panel_view(f"{npc.get('name', 'Villager')} Courtship", self.town_npc_romance_lines(npc) + ["", reason], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            self.set_message(reason)
            return False

        before = self.town_npc_relationship(npc_id)
        gain = RELATIONSHIP_SPOUSE_COURTSHIP_GAIN if self.state.spouse_npc_id == npc_id else (RELATIONSHIP_DATING_COURTSHIP_GAIN if npc_id in set(self.state.dating_npc_ids or []) else RELATIONSHIP_COURTSHIP_GAIN)
        actual_gain = self.adjust_town_npc_relationship(npc_id, gain)
        after = self.town_npc_relationship(npc_id)
        self.state.town_npc_last_court_day[npc_id] = self.town_npc_day_key()
        self.increment_town_npc_courtship_count(npc_id)
        started_dating = False
        dating_ok, _dating_reason = self.can_start_dating_with_npc(npc)
        if dating_ok:
            self.state.dating_npc_ids.append(npc_id)
            started_dating = True

        rows = [
            f"{npc.get('name')} Courtship",
            "",
            self.town_npc_courtship_scene_line(npc),
            f"Relationship: {before} -> {after} ({actual_gain:+})",
            "",
            self.romance_note_for_npc(npc),
        ]
        if started_dating:
            rows.extend(["", f"{npc.get('name')} is now dating you."])
        if self.state.spouse_npc_id == npc_id:
            rows.extend(["", "It feels less like impressing each other and more like keeping the home fires noticed."])
        self.vertical_panel_view(f"{npc.get('name')} Courtship", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Spent time with {npc.get('name')}. Relationship {actual_gain:+}.")
        return True

    def can_propose_to_town_npc(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.is_marriageable_npc(npc):
            return False, f"{npc.get('name', 'They')} is not a romance candidate."
        if self.state.spouse_npc_id == npc_id:
            return False, f"You are already married to {npc.get('name', 'them')}."
        if self.state.spouse_npc_id:
            return False, f"You are already married to {self.town_npc_name(self.state.spouse_npc_id)}."
        if str(getattr(self.state, "engaged_npc_id", "") or ""):
            return False, (
                f"You are engaged to "
                f"{self.town_npc_name(self.state.engaged_npc_id)}."
            )
        if str(getattr(self.state, "engaged_npc_id", "")) == npc_id:
            return False, f"You are already engaged to {npc.get('name', 'them')}."
        if str(getattr(self.state, "engaged_npc_id", "")):
            return False, (
                f"You are already engaged to "
                f"{self.town_npc_name(self.state.engaged_npc_id)}."
            )
        points = self.town_npc_relationship(npc_id)
        if points < RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP:
            return False, f"Relationship needs to reach {RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP} before proposing. Current: {points}."
        talks = self.town_npc_dialogue_count(npc_id)
        if talks < RELATIONSHIP_PROPOSAL_REQUIRED_TALKS:
            return False, f"Talk with them more before proposing. Current talks: {talks}/{RELATIONSHIP_PROPOSAL_REQUIRED_TALKS}."
        courtships = self.town_npc_courtship_count(npc_id)
        if courtships < RELATIONSHIP_PROPOSAL_REQUIRED_COURTSHIP:
            return False, f"Spend more courtship time before proposing. Current: {courtships}/{RELATIONSHIP_PROPOSAL_REQUIRED_COURTSHIP}."
        if self.is_sample_milestone_npc(npc_id) and not self.has_relationship_milestone(npc_id, "trusted"):
            return False, "A trust milestone needs to happen before proposing."
        if self.state.inventory.get(WEDDING_RING_ITEM, 0) <= 0:
            return False, (
                f"You need 1 {WEDDING_RING_ITEM}. "
                f"The General Store sells one for ${WEDDING_RING_PRICE}."
            )
        return True, "Ready to propose."

    def proposal_status_lines(self, npc: Dict[str, object]) -> List[str]:
        ok, reason = self.can_propose_to_town_npc(npc)
        lines = self.town_npc_romance_lines(npc)
        lines.extend(["", "Proposal:", reason])
        if ok:
            lines.append("Choose Propose again from their menu when you are ready.")
        return lines

    def can_purchase_wedding_ring(self) -> Tuple[bool, str]:
        if int(self.state.inventory.get(WEDDING_RING_ITEM, 0)) > 0:
            return False, "You already own a wedding ring."
        if str(getattr(self.state, "engaged_npc_id", "") or ""):
            return False, "Your engagement ring has already been offered."
        if str(getattr(self.state, "spouse_npc_id", "") or ""):
            return False, "You are already married."
        if int(self.state.money) < WEDDING_RING_PRICE:
            return False, f"Costs ${WEDDING_RING_PRICE}."
        return True, f"Costs ${WEDDING_RING_PRICE}; required for a proposal."

    def purchase_wedding_ring(self) -> bool:
        ok, reason = self.can_purchase_wedding_ring()
        if not ok:
            self.set_message(reason)
            return False
        self.state.money -= WEDDING_RING_PRICE
        self.state.inventory[WEDDING_RING_ITEM] = 1
        self.autosave_with_message(
            f"Bought a {WEDDING_RING_ITEM} for ${WEDDING_RING_PRICE}."
        )
        return True

    def date_after_days(self, days: int) -> Tuple[int, int, int]:
        month = int(self.state.month)
        day = int(self.state.day)
        year = int(self.state.year)
        for _ in range(max(0, int(days))):
            month, day, year = advance_date(month, day, year)
        return month, day, year

    def wedding_date_label(self) -> str:
        return self.family_date_label(
            self.state.wedding_month,
            self.state.wedding_day,
            self.state.wedding_year,
        )

    def choose_scheduled_wedding_date(
        self,
        npc: Dict[str, object],
    ) -> Optional[Tuple[int, int, int]]:
        options = [
            (7, "One week"),
            (14, "Two weeks"),
            (28, "Four weeks"),
        ]
        items = []
        for days, label in options:
            month, day, year = self.date_after_days(days)
            items.append(
                MenuItem(
                    label=label,
                    value=days,
                    enabled=True,
                    hint=format_date(month, day, year),
                )
            )
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(
            f"Wedding Date with {npc.get('name', 'Partner')}",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return None
        return self.date_after_days(int(choice.value))

    def propose_to_town_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        ok, reason = self.can_propose_to_town_npc(npc)
        if not ok:
            self.vertical_panel_view(f"Proposal to {npc.get('name', 'Villager')}", self.proposal_status_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            self.set_message(reason)
            return False

        wedding_date = self.choose_scheduled_wedding_date(npc)
        if wedding_date is None:
            self.set_message("Proposal cancelled before setting a wedding date.")
            return False

        personal_item = self.proposal_item_for_npc(npc)
        self.state.inventory[WEDDING_RING_ITEM] = max(
            0,
            int(self.state.inventory.get(WEDDING_RING_ITEM, 0)) - 1,
        )
        self.state.engaged_npc_id = npc_id
        (
            self.state.engagement_month,
            self.state.engagement_day,
            self.state.engagement_year,
        ) = (
            int(self.state.month),
            int(self.state.day),
            int(self.state.year),
        )
        (
            self.state.wedding_month,
            self.state.wedding_day,
            self.state.wedding_year,
        ) = wedding_date
        self.state.dating_npc_ids = [npc_id]
        engagement_relationship = min(
            RELATIONSHIP_MAX,
            max(self.town_npc_relationship(npc_id), 205),
        )
        self.state.town_npc_relationships[npc_id] = engagement_relationship
        procedural = self.procedural_resident_by_id(npc_id)
        if procedural:
            procedural["relationship"] = engagement_relationship
            memories = list(procedural.get("memories", []) or [])
            memories.append(
                f"{getattr(self.state, 'date_label', '')} - Became engaged to "
                f"{getattr(self.state, 'player_name', 'the farmer')}."
            )
            procedural["memories"] = memories[-16:]
        self.state.town_npc_last_proposal_day[npc_id] = self.town_npc_day_key()

        vow = self.romance_data_for_npc(npc).get("vow", f"{npc.get('name')} promises to build a life beside you.")
        rows = [
            f"Proposal to {npc.get('name')}",
            "",
            f"You offer the {WEDDING_RING_ITEM}.",
            "",
            str(vow),
            "",
            f"{npc.get('name')} accepts.",
            "",
            f"Wedding date: {self.wedding_date_label()}",
            "The date has been marked on the calendar. The marriage begins when the ceremony occurs.",
        ]
        if self.state.inventory.get(personal_item, 0) > 0:
            rows.append(
                f"You also have {personal_item}, something especially meaningful to them."
            )
        self.record_family_event(
            "Engagement",
            f"Became engaged to {npc.get('name')}; wedding scheduled for "
            f"{self.wedding_date_label()}.",
            flag=(
                f"engagement:{npc_id}:{self.state.year}:"
                f"{self.state.month}:{self.state.day}"
            ),
        )
        self.vertical_panel_view(f"Proposal to {npc.get('name')}", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(
            f"{npc.get('name')} accepted. Wedding: {self.wedding_date_label()}."
        )
        return True

    def wedding_ceremony_lines(
        self,
        npc: Dict[str, object],
    ) -> List[str]:
        name = str(npc.get("name", "your partner"))
        vow = str(
            self.romance_data_for_npc(npc).get(
                "vow",
                f"{name} promises to build a life beside you.",
            )
        )
        weather = str(getattr(self.state, "weather", "Clear"))
        setting = (
            "Rain taps against the Town Hall windows while neighbors crowd warmly inside."
            if weather in {"Rainy", "Stormy"}
            else "Snow softens the town outside while the ceremony gathers indoors."
            if weather in {"Snowy", "Blizzard"}
            else "The town gathers beneath clear light, with the Town Hall doors left open."
        )
        family_names = [
            str(child.get("name", "your child"))
            for child in getattr(self.state, "children", []) or []
        ]
        family_line = (
            f"Your household gathers close: {', '.join(family_names[:4])}."
            if family_names
            else "Friends and neighbors fill the front rows."
        )
        return [
            f"Wedding of {self.state.player_name} and {name}",
            "",
            setting,
            family_line,
            "",
            "The town clerk asks each of you to speak plainly about the life you are choosing.",
            vow,
            "",
            "You exchange vows and sign the household ledger.",
            "The room breaks into applause, conversation, and the practical chaos of shared food.",
            "",
            f"Marriage recorded: {format_date(self.state.month, self.state.day, self.state.year)}",
        ]

    def initialize_spouse_lifespan(
        self,
        npc: Dict[str, object],
    ) -> None:
        if int(getattr(self.state, "spouse_lifespan_age", 0) or 0) > 0:
            return
        npc_id = str(npc.get("id", "spouse"))
        try:
            age = int(npc.get("age_years", 0) or 0)
        except Exception:
            age = 0
        if age <= 0:
            seed = sum(
                (index + 1) * ord(character)
                for index, character in enumerate(npc_id)
            )
            age = 24 + seed % 26
        birthday_month, birthday_day = self.npc_birthday(npc)
        birthday_passed = (
            int(self.state.month),
            int(self.state.day),
        ) >= (int(birthday_month), int(birthday_day))
        birth_year = int(self.state.year) - age - (0 if birthday_passed else 1)
        self.state.spouse_birth_year = birth_year
        if hasattr(self, "dynasty_lifespan_for_identity"):
            lifespan = self.dynasty_lifespan_for_identity(
                str(npc.get("name", npc_id)),
                birth_year,
                int(getattr(self.state, "player_generation", 1)),
            )
        else:
            lifespan = 88 + (
                sum(ord(character) for character in npc_id) % 14
            )
        self.state.spouse_lifespan_age = max(
            70,
            min(115, max(age + 5, int(lifespan))),
        )

    def complete_scheduled_wedding(
        self,
        interactive: bool = True,
    ) -> str:
        npc_id = str(getattr(self.state, "engaged_npc_id", "") or "")
        if not npc_id:
            return ""
        npc = self.npc_record_by_id(npc_id)
        if not npc or bool(npc.get("deceased", False)):
            self.state.engaged_npc_id = ""
            self.state.wedding_month = 0
            self.state.wedding_day = 0
            self.state.wedding_year = 0
            return " The scheduled wedding could not proceed."

        self.state.spouse_npc_id = npc_id
        self.state.spouse_moved_to_farm = False
        self.state.marriage_month = int(self.state.month)
        self.state.marriage_day = int(self.state.day)
        self.state.marriage_year = int(self.state.year)
        self.state.engaged_npc_id = ""
        self.state.wedding_month = 0
        self.state.wedding_day = 0
        self.state.wedding_year = 0
        self.state.town_npc_relationships[npc_id] = min(
            RELATIONSHIP_MAX,
            max(self.town_npc_relationship(npc_id), 220),
        )
        self.state.family_bond = min(
            999,
            int(getattr(self.state, "family_bond", 0)) + 10,
        )
        self.state.spouse_birth_year = 0
        self.state.spouse_lifespan_age = 0
        self.state.spouse_frozen_age = 0
        self.initialize_spouse_lifespan(npc)
        self.state.marriage_history.append({
            "spouse_npc_id": npc_id,
            "spouse_name": str(npc.get("name", npc_id)),
            "marriage_month": int(self.state.month),
            "marriage_day": int(self.state.day),
            "marriage_year": int(self.state.year),
            "status": "married",
        })
        self.state.marriage_history = self.state.marriage_history[-12:]

        procedural = self.procedural_resident_by_id(npc_id)
        if procedural:
            procedural["relationship"] = self.state.town_npc_relationships[npc_id]
            memories = list(procedural.get("memories", []) or [])
            memories.append(
                f"{getattr(self.state, 'date_label', '')} - Married "
                f"{getattr(self.state, 'player_name', 'the farmer')}."
            )
            procedural["memories"] = memories[-16:]

        self.record_family_event(
            "Wedding",
            f"Married {npc.get('name')} in a Town Hall ceremony.",
            flag=(
                f"wedding:{npc_id}:{self.state.year}:"
                f"{self.state.month}:{self.state.day}"
            ),
        )
        if interactive:
            self.vertical_panel_view(
                "Wedding Day",
                self.wedding_ceremony_lines(npc),
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
            )
        return f" Wedding day: you married {npc.get('name')}."

    def process_scheduled_wedding_overnight(
        self,
        interactive: bool = True,
    ) -> str:
        if not str(getattr(self.state, "engaged_npc_id", "") or ""):
            return ""
        if not (
            int(getattr(self.state, "wedding_month", 0) or 0)
            and int(getattr(self.state, "wedding_day", 0) or 0)
            and int(getattr(self.state, "wedding_year", 0) or 0)
        ):
            return ""
        if not date_reached(
            self.state.month,
            self.state.day,
            self.state.year,
            self.state.wedding_month,
            self.state.wedding_day,
            self.state.wedding_year,
        ):
            return ""
        return self.complete_scheduled_wedding(interactive=interactive)

    def spouse_age_years(self, npc: Optional[Dict[str, object]] = None) -> int:
        npc = npc or self.npc_record_by_id(self.state.spouse_npc_id)
        if not npc:
            return 0
        if (
            not self.aging_and_death_active()
            and int(getattr(self.state, "spouse_frozen_age", 0) or 0) > 0
        ):
            return int(self.state.spouse_frozen_age)
        self.initialize_spouse_lifespan(npc)
        birthday_month, birthday_day = self.npc_birthday(npc)
        age = int(self.state.year) - int(self.state.spouse_birth_year)
        if (
            int(self.state.month),
            int(self.state.day),
        ) < (int(birthday_month), int(birthday_day)):
            age -= 1
        return max(0, age)

    def handle_spouse_death(
        self,
        reason: str = "old age",
        interactive: bool = True,
    ) -> str:
        npc_id = str(getattr(self.state, "spouse_npc_id", "") or "")
        if not npc_id:
            return ""
        npc = self.npc_record_by_id(npc_id) or {"id": npc_id}
        name = str(npc.get("name") or self.town_npc_name(npc_id))
        age = self.spouse_age_years(npc)
        npc["deceased"] = True
        npc["death_year"] = int(self.state.year)
        npc["death_age"] = age
        npc["activity"] = "remembered by the household"
        if npc_id not in self.state.deceased_spouse_npc_ids:
            self.state.deceased_spouse_npc_ids.append(npc_id)
        for record in reversed(self.state.marriage_history):
            if (
                str(record.get("spouse_npc_id", "")) == npc_id
                and str(record.get("status", "married")) == "married"
            ):
                record["status"] = "widowed"
                record["death_month"] = int(self.state.month)
                record["death_day"] = int(self.state.day)
                record["death_year"] = int(self.state.year)
                record["death_age"] = age
                record["death_reason"] = str(reason)
                break
        else:
            self.state.marriage_history.append({
                "spouse_npc_id": npc_id,
                "spouse_name": name,
                "marriage_month": int(self.state.marriage_month),
                "marriage_day": int(self.state.marriage_day),
                "marriage_year": int(self.state.marriage_year),
                "status": "widowed",
                "death_month": int(self.state.month),
                "death_day": int(self.state.day),
                "death_year": int(self.state.year),
                "death_age": age,
                "death_reason": str(reason),
            })

        follower_id = ""
        if hasattr(self, "travel_follower_identity_for_npc_id"):
            follower_id = str(
                self.travel_follower_identity_for_npc_id(npc_id) or ""
            )
        if follower_id:
            self.state.travel_follower_ids = [
                value
                for value in self.state.travel_follower_ids
                if str(value) != follower_id
            ]
            self.state.travel_follower_states.pop(follower_id, None)

        self.state.dating_npc_ids = [
            value
            for value in self.state.dating_npc_ids
            if str(value) != npc_id
        ]
        self.state.spouse_npc_id = ""
        self.state.spouse_moved_to_farm = False
        self.state.marriage_month = 0
        self.state.marriage_day = 0
        self.state.marriage_year = 0
        self.state.spouse_birth_year = 0
        self.state.spouse_lifespan_age = 0
        self.state.spouse_frozen_age = 0
        self.record_family_event(
            "Spouse Passing",
            f"{name} died peacefully from {reason} at age {age}.",
            flag=f"spouse_death:{npc_id}:{self.state.year}",
        )
        if interactive:
            self.vertical_panel_view(
                "A Family Passing",
                [
                    f"{name} died peacefully from {reason} at age {age}.",
                    "",
                    "The household enters a period of mourning.",
                    "The marriage remains in the family record.",
                    "In time, you may court and marry again if you choose.",
                ],
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
            )
        return f" {name}, your spouse, died peacefully from {reason} at age {age}."

    def process_spouse_lifespan_overnight(
        self,
        interactive: bool = True,
    ) -> str:
        if not str(getattr(self.state, "spouse_npc_id", "") or ""):
            return ""
        if not self.aging_and_death_active():
            return ""
        npc = self.npc_record_by_id(self.state.spouse_npc_id)
        if not npc:
            return ""
        self.initialize_spouse_lifespan(npc)
        if self.npc_birthday(npc) != (
            int(self.state.month),
            int(self.state.day),
        ):
            return ""
        if self.spouse_age_years(npc) < int(self.state.spouse_lifespan_age):
            return ""
        return self.handle_spouse_death(
            "old age",
            interactive=interactive,
        )

    def spouse_lives_on_farm(self) -> bool:
        return bool(self.state.spouse_npc_id and self.state.spouse_moved_to_farm)

    def family_date_label(self, month: int, day: int, year: int) -> str:
        if int(month) <= 0 or int(day) <= 0 or int(year) <= 0:
            return "not recorded"
        return format_date(int(month), int(day), int(year))

    def marriage_date_label(self) -> str:
        return self.family_date_label(self.state.marriage_month, self.state.marriage_day, self.state.marriage_year)

    def has_family_event_flag(self, flag: str) -> bool:
        return str(flag) in set(getattr(self.state, "family_event_flags", []) or [])

    def mark_family_event_flag(self, flag: str):
        flag = str(flag or "").strip()
        if not flag:
            return
        if not isinstance(self.state.family_event_flags, list):
            self.state.family_event_flags = []
        if flag not in self.state.family_event_flags:
            self.state.family_event_flags.append(flag)

    def record_family_event(self, title: str, detail: str = "", flag: str = ""):
        if not isinstance(self.state.family_event_log, list):
            self.state.family_event_log = []
        date = format_date(self.state.month, self.state.day, self.state.year)
        line = f"{date} - {title}"
        if detail:
            line += f": {detail}"
        self.state.family_event_log.append(line)
        self.state.family_event_log = [str(row) for row in self.state.family_event_log if row is not None][-30:]
        if flag:
            self.mark_family_event_flag(flag)

    def family_event_log_lines(self) -> List[str]:
        lines = ["FAMILY MEMORIES", ""]
        if not self.state.family_event_log:
            lines.append("No family milestones recorded yet.")
            return lines
        lines.extend(f"- {line}" for line in self.state.family_event_log[-18:])
        return lines

    def family_bond_score(self) -> int:
        try:
            return max(0, min(999, int(getattr(self.state, "family_bond", 0))))
        except Exception:
            return 0

    def family_bond_rank(self) -> str:
        score = self.family_bond_score()
        if score >= 300:
            return "Deeply Rooted"
        if score >= 180:
            return "Close-Knit"
        if score >= 90:
            return "Comfortable"
        if score >= 35:
            return "Settling In"
        return "New Household"

    def adjust_family_bond(self, amount: int) -> int:
        before = self.family_bond_score()
        after = max(0, min(999, before + int(amount)))
        self.state.family_bond = after
        return after - before

    def family_bond_lines(self) -> List[str]:
        return [
            "Household bond",
            f"- Rank: {self.family_bond_rank()}",
            f"- Score: {self.family_bond_score()}/999",
            f"- Last shared meal: {self.state.family_last_meal or 'none recorded'}",
            f"- Sleep stamina bonus: +{self.family_sleep_bonus()}",
        ]

    def family_sleep_bonus(self) -> int:
        if self.family_member_count() <= 1:
            return 0
        score = self.family_bond_score()
        if score >= 300:
            return 8
        if score >= 180:
            return 6
        if score >= 90:
            return 4
        if score >= 35:
            return 2
        return 0

    def family_today_lines(self) -> List[str]:
        lines = [
            "TODAY AT HOME",
            "",
            f"Date: {format_date(self.state.month, self.state.day, self.state.year)}",
            f"Household residence: {self.household_residence_label() if hasattr(self, 'household_residence_label') else 'the farmhouse'}",
            f"Household bond: {self.family_bond_rank()} ({self.family_bond_score()})",
            "",
            "Available today:",
        ]
        meal_ok, meal_reason = self.family_meal_available()
        lines.append(f"- Family meal: {'ready' if meal_ok else meal_reason}")
        if self.spouse_lives_on_farm():
            lines.append(f"- Spouse support: {self.spouse_support_mode()}")
        elif str(getattr(self.state, "engaged_npc_id", "") or ""):
            lines.append(
                f"- Wedding: {self.wedding_date_label()} with "
                f"{self.town_npc_name(self.state.engaged_npc_id)}"
            )
        if self.state.pregnancy_active:
            lines.append(f"- Pregnancy: month {self.pregnancy_month_number()} of 9")
            lines.append(f"- Check-in: {'ready' if self.pregnancy_checkup_available() else 'not ready or completed'}")
        spouse = self.npc_record_by_id(self.state.spouse_npc_id)
        if spouse:
            scene_key, scene_title = self.available_marriage_scene(spouse)
            lines.append(f"- Marriage event: {scene_title if scene_key else 'none ready'}")
        if self.state.children:
            lines.extend(["", "Children:"])
        for child in self.state.children:
            child = self.ensure_child_profile_fields(child)
            key = self.child_key(child)
            gift_done = self.state.child_last_gift_day.get(key) == self.town_npc_day_key() if isinstance(self.state.child_last_gift_day, dict) else False
            lesson_done = self.state.child_last_lesson_day.get(key) == self.town_npc_day_key() if isinstance(self.state.child_last_lesson_day, dict) else False
            birthday = " birthday" if self.is_child_birthday(child) else ""
            lines.append(
                f"- {child.get('name', 'Child')}: {self.household_child_stage(child)}{birthday}; "
                f"gift {'done' if gift_done else 'open'}, lesson {'done' if lesson_done else 'open'}, "
                f"chore {self.child_chore_assignment(child)}"
            )
        if not self.state.children and not self.state.spouse_npc_id:
            lines.append("- No spouse or children in the household yet.")
        return lines

    def family_growth_report_lines(self) -> List[str]:
        lines = [
            "FAMILY GROWTH",
            "",
            f"Household bond: {self.family_bond_rank()} ({self.family_bond_score()})",
            f"Children: {len(self.state.children)}",
        ]
        if not self.state.children:
            lines.extend([
                "",
                f"No children are living in {self.household_residence_label() if hasattr(self, 'household_residence_label') else 'the farmhouse'} yet.",
            ])
            return lines
        for child in self.state.children:
            child = self.ensure_child_profile_fields(child)
            age_months = self.household_child_age_months(child)
            stage = self.household_child_stage(child)
            next_stage_line = "fully grown for the current system"
            for next_stage, month_mark in self.child_stage_months().items():
                if age_months < month_mark:
                    next_stage_line = f"{next_stage} in {month_mark - age_months} month(s)"
                    break
            top_topic, top_points = self.child_top_learning_topic(child)
            lines.extend([
                "",
                f"{child.get('name', 'Child')} - {stage}",
                f"- {self.household_child_age_display_line(child)}",
                f"- Next stage: {next_stage_line}",
                f"- Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
                f"- Path: {child.get('apprentice_path', 'Helper')}",
                f"- Learning: {top_topic if top_topic else 'none yet'}{f' ({top_points})' if top_topic else ''}",
                f"- Chore: {self.child_chore_assignment(child)}",
            ])
        return lines

    def family_member_count(self) -> int:
        elder_count = sum(
            1
            for elder in getattr(self.state, "dynasty_elders", []) or []
            if isinstance(elder, dict) and elder.get("active", True)
        )
        resident_kin_count = sum(
            1
            for kin in getattr(self.state, "dynasty_kin", []) or []
            if isinstance(kin, dict)
            and kin.get("active", True)
            and not kin.get("linked_existing_npc")
            and str(kin.get("residence", "")) == "Farmhouse"
        )
        return (
            1
            + (1 if self.spouse_lives_on_farm() else 0)
            + len(getattr(self.state, "children", []) or [])
            + elder_count
            + resident_kin_count
        )

    def family_meal_candidates(self) -> List[Tuple[str, int, int]]:
        if hasattr(self, "edible_items_in_inventory"):
            return list(self.edible_items_in_inventory())
        rows: List[Tuple[str, int, int]] = []
        for item_name, qty in sorted(self.state.inventory.items()):
            if int(qty) > 0 and is_food_item(str(item_name)):
                rows.append((str(item_name), int(qty), food_stamina_value(str(item_name))))
        return rows

    def family_meal_available(self) -> Tuple[bool, str]:
        if self.family_member_count() <= 1:
            return False, "Family meals need a spouse or child in the household."
        if self.state.family_meal_last_day == self.town_npc_day_key():
            return False, "The household already shared a meal today."
        if not self.family_meal_candidates():
            return False, "You are not carrying any food to share."
        return True, "Share food with the household."

    def share_family_meal(self, item_name: str) -> bool:
        item_name = str(item_name)
        ok, reason = self.family_meal_available()
        if not ok:
            self.set_message(reason)
            return False
        if self.state.inventory.get(item_name, 0) <= 0 or not is_food_item(item_name):
            self.set_message(f"You do not have a shareable {item_name}.")
            return False

        self.state.inventory[item_name] -= 1
        if self.state.inventory[item_name] <= 0:
            self.state.inventory.pop(item_name, None)

        participants = self.family_member_count()
        stamina_value = max(1, food_stamina_value(item_name))
        bond_gain = min(18, 4 + participants + max(1, stamina_value // 12))
        self.adjust_family_bond(bond_gain)
        if self.spouse_lives_on_farm():
            self.adjust_town_npc_relationship(self.state.spouse_npc_id, min(5, 2 + stamina_value // 25))
        for child in self.state.children:
            self.adjust_child_affection(child, 3 + (1 if item_name == str(self.ensure_child_profile_fields(child).get("favorite_gift", "")) else 0))

        recovered = min(10, max(2, stamina_value // 4))
        recovered = self.restore_stamina(recovered)
        self.state.family_meal_last_day = self.town_npc_day_key()
        self.state.family_last_meal = item_name
        self.record_family_event("Family Meal", f"Shared {item_name} with the household.")
        self.autosave_with_message(f"Shared {item_name} at home. Household bond +{bond_gain}. Stamina +{recovered}.")
        return True

    def family_meal_lines(self) -> List[str]:
        ok, reason = self.family_meal_available()
        lines = [
            "FAMILY MEAL",
            "",
            f"Household: {self.family_member_count()} member(s)",
            f"Status: {'ready' if ok else reason}",
            f"Last meal: {self.state.family_last_meal or 'none'}",
            "",
            *self.family_bond_lines(),
            "",
            "Carried food:",
        ]
        meals = self.family_meal_candidates()
        if meals:
            for item_name, qty, stamina in meals[:14]:
                lines.append(f"- {item_name} x{qty}: +{stamina} stamina food")
        else:
            lines.append("- No food carried.")
        return lines

    def family_meal_menu(self):
        while True:
            ok, reason = self.family_meal_available()
            items: List[MenuItem] = []
            for item_name, qty, stamina in self.family_meal_candidates():
                items.append(MenuItem(label=item_name, value=item_name, enabled=ok, hint=f"x{qty}; +{stamina}"))
            items.append(MenuItem(label="Meal notes", value="notes", enabled=True, hint=reason if not ok else "household bond"))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Family Meal", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed family meal menu.")
                return MENU_BACK
            if choice.value == "notes":
                self.vertical_panel_view("Family Meal", self.family_meal_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if self.share_family_meal(str(choice.value)):
                return "changed"

    def spouse_support_modes(self) -> Dict[str, Dict[str, str]]:
        return {
            "Balanced": {"label": "Balanced", "note": "A little food, a little tidying, and no strong priority."},
            "Meals": {"label": "Meals", "note": "Your spouse tries to keep simple food ready overnight."},
            "Farm": {"label": "Farm", "note": "Your spouse focuses on seeds, small supplies, and farm prep."},
            "Forage": {"label": "Forage", "note": "Your spouse keeps an eye out for useful wild goods."},
            "Rest": {"label": "Rest", "note": "Your spouse keeps the house quiet instead of producing items."},
        }

    def spouse_support_mode(self) -> str:
        mode = str(getattr(self.state, "spouse_support_mode", "Balanced") or "Balanced")
        if mode not in self.spouse_support_modes():
            mode = "Balanced"
            self.state.spouse_support_mode = mode
        return mode

    def spouse_support_mode_lines(self) -> List[str]:
        lines = [
            "SPOUSE SUPPORT",
            "",
            f"Current focus: {self.spouse_support_mode()}",
            f"Household help: {'enabled' if self.state.family_help_enabled else 'disabled'}",
            "",
            "Focus options:",
        ]
        for mode, data in self.spouse_support_modes().items():
            marker = "*" if mode == self.spouse_support_mode() else "-"
            lines.append(f"{marker} {mode}: {data['note']}")
        lines.extend(["", "Support happens overnight when household help is enabled."])
        return lines

    def set_spouse_support_mode(self, mode: str) -> bool:
        mode = str(mode)
        if mode not in self.spouse_support_modes():
            self.set_message("Unknown spouse support focus.")
            return False
        self.state.spouse_support_mode = mode
        self.record_family_event("Spouse Support", f"Household support focus set to {mode}.")
        self.autosave_with_message(f"Spouse support focus set to {mode}.")
        return True

    def spouse_support_menu(self):
        if not self.spouse_lives_on_farm():
            self.set_message("Spouse support is available after your spouse moves onto the farm.")
            return MENU_BACK
        while True:
            items = [
                MenuItem(label=mode, value=mode, enabled=True, hint=data["note"])
                for mode, data in self.spouse_support_modes().items()
            ]
            items.append(MenuItem(label="Support notes", value="notes", enabled=True, hint=self.spouse_support_mode()))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Spouse Support", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed spouse support menu.")
                return MENU_BACK
            if choice.value == "notes":
                self.vertical_panel_view("Spouse Support", self.spouse_support_mode_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if self.set_spouse_support_mode(str(choice.value)):
                return "changed"

    def spouse_help_drop(self) -> Tuple[str, int, str]:
        mode = self.spouse_support_mode()
        if mode == "Meals":
            if self.has_kitchen_access():
                return "Field Snack", 2, "packed simple food for the household"
            return "Berries", 2, "set aside berries for the household"
        if mode == "Farm":
            return "Mixed Seeds", 2, "sorted useful farm supplies before bed"
        if mode == "Forage":
            return "Wildflower", 1, "brought in a useful wildflower from the path"
        if mode == "Rest":
            return "", 0, "kept the farmhouse quiet so everyone could recover"
        item = "Field Snack" if self.has_kitchen_access() else "Berries"
        return item, 1, f"prepared {item}"

    def marriage_days_elapsed(self) -> int:
        if not (self.state.marriage_month and self.state.marriage_day and self.state.marriage_year):
            return 0
        return max(
            0,
            self.absolute_game_day()
            - self.absolute_game_day(self.state.marriage_month, self.state.marriage_day, self.state.marriage_year),
        )

    def marriage_anniversary_today(self) -> bool:
        return bool(
            self.state.spouse_npc_id
            and self.state.marriage_month == self.state.month
            and self.state.marriage_day == self.state.day
            and self.state.year > self.state.marriage_year
        )

    def available_marriage_scene(self, npc: Dict[str, object]) -> Tuple[str, str]:
        npc_id = str(npc.get("id", ""))
        if self.state.spouse_npc_id != npc_id:
            return "", ""
        if self.marriage_anniversary_today():
            key = f"anniversary:{self.state.year}:{npc_id}"
            if not self.has_family_event_flag(key):
                return key, "Anniversary"
        if self.state.spouse_moved_to_farm and self.marriage_days_elapsed() >= 7:
            key = f"first_household_conflict:{npc_id}"
            if not self.has_family_event_flag(key):
                return key, "First Household Conflict"
        if self.state.spouse_moved_to_farm and self.marriage_days_elapsed() >= 14:
            key = f"shared_household_goal:{npc_id}"
            if not self.has_family_event_flag(key):
                return key, "Shared Household Goal"
        return "", ""

    def marriage_scene_lines(self, npc: Dict[str, object], scene_key: str, scene_title: str) -> List[str]:
        name = str(npc.get("name", "your spouse"))
        if scene_key.startswith("anniversary:"):
            return [
                "Anniversary",
                "",
                f"You and {name} pause long enough to remember that the household began as a choice, not a checklist.",
                f"{name} marks the calendar and asks what kind of year you want to build next.",
                "",
                "Relationship: the marriage feels steadier for being noticed.",
            ]
        if scene_key.startswith("first_household_conflict:"):
            return [
                "First Household Conflict",
                "",
                f"The first real household disagreement with {name} is not dramatic. That almost makes it harder to ignore.",
                "You talk through chores, space, sleep, and the small expectations neither of you said out loud.",
                "",
                "Outcome: the farmhouse feels more honest afterward.",
            ]
        return [
            "Shared Household Goal",
            "",
            f"You and {name} sit with the farm ledger and choose a shared priority for the season.",
            "The goal is simple: keep the home useful, keep meals stocked, and make room for family life before it becomes urgent.",
            "",
            "Outcome: household help and family planning are easier to track from the family status page.",
        ]

    def play_marriage_scene(self, npc: Dict[str, object]) -> bool:
        scene_key, scene_title = self.available_marriage_scene(npc)
        if not scene_key:
            self.set_message("No new marriage scene is ready.")
            return False
        rows = self.marriage_scene_lines(npc, scene_key, scene_title)
        self.record_family_event(scene_title, f"Shared with {npc.get('name', 'your spouse')}.", flag=scene_key)
        self.adjust_town_npc_relationship(str(npc.get("id", "")), 3)
        self.vertical_panel_view(scene_title, rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Shared a marriage scene with {npc.get('name', 'your spouse')}.")
        return True

    def marriage_status_lines(self) -> List[str]:
        if not self.state.spouse_npc_id:
            if str(getattr(self.state, "engaged_npc_id", "") or ""):
                return [
                    "Engagement",
                    "",
                    f"Fiance: {self.town_npc_name(self.state.engaged_npc_id)}",
                    f"Wedding date: {self.wedding_date_label()}",
                    "The ceremony will occur when that date arrives.",
                ]
            history = [
                record
                for record in getattr(self.state, "marriage_history", []) or []
                if isinstance(record, dict)
            ]
            if history and str(history[-1].get("status", "")) == "widowed":
                last = history[-1]
                return [
                    "Marriage: widowed",
                    "",
                    f"Late spouse: {last.get('spouse_name', 'remembered spouse')}",
                    f"Married: {self.family_date_label(last.get('marriage_month', 0), last.get('marriage_day', 0), last.get('marriage_year', 0))}",
                    f"Died: {self.family_date_label(last.get('death_month', 0), last.get('death_day', 0), last.get('death_year', 0))}",
                    "Remarriage: available whenever you are ready to court someone again.",
                ]
            return ["Marriage: none"]
        spouse_name = self.town_npc_name(self.state.spouse_npc_id)
        spouse = self.npc_record_by_id(self.state.spouse_npc_id)
        spouse_age = self.spouse_age_years(spouse) if spouse else 0
        age_line = (
            f"Spouse life stage: {self.player_life_stage(spouse_age)}"
            if not self.aging_and_death_active()
            else f"Spouse age: {spouse_age}"
        )
        lines = [
            "Marriage",
            "",
            f"Spouse: {spouse_name}",
            age_line,
            f"Wedding date: {self.marriage_date_label()}",
            f"Days married: {self.marriage_days_elapsed()}",
            "Anniversary: today" if self.marriage_anniversary_today() else f"Anniversary: {self.marriage_date_label()}",
            "Household: spouse lives at the farmhouse" if self.state.spouse_moved_to_farm else "Household: spouse has not moved in",
            f"Household help: {'enabled' if self.state.family_help_enabled else 'disabled'}",
        ]
        if spouse:
            _key, scene = self.available_marriage_scene(spouse)
            lines.append(f"Next marriage scene: {scene if scene else 'none ready'}")
        previous_marriages = max(
            0,
            len(getattr(self.state, "marriage_history", []) or []) - 1,
        )
        if previous_marriages:
            lines.append(f"Earlier marriages remembered: {previous_marriages}")
        return lines

    def can_invite_spouse_to_farm(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.state.spouse_npc_id or self.state.spouse_npc_id != npc_id:
            return False, "Only your spouse can move onto the farm."
        if self.state.spouse_moved_to_farm:
            return False, f"{npc.get('name', 'Your spouse')} already lives at the farmhouse."
        return True, "Invite them to move into the farmhouse."

    def invite_spouse_to_farm(self, npc: Dict[str, object]) -> bool:
        ok, reason = self.can_invite_spouse_to_farm(npc)
        if not ok:
            self.set_message(reason)
            return False
        self.state.spouse_moved_to_farm = True
        npc["indoors"] = True
        npc["indoor_location"] = "Farmhouse"
        npc["activity"] = "settling into farmhouse life"
        rows = [
            f"{npc.get('name')} Moves In",
            "",
            f"{npc.get('name')} agrees to move into the farmhouse with you.",
            "They will now appear at home, and you can keep talking, gifting, and spending courtship time together there.",
        ]
        self.record_family_event("Move-In", f"{npc.get('name')} moved into the farmhouse.", flag=f"move_in:{npc_id}")
        self.vertical_panel_view("Farmhouse Move-In", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"{npc.get('name')} moved into the farmhouse.")
        return True

    def pregnancy_due_date_label(self) -> str:
        if not self.state.pregnancy_active:
            return "No due date"
        return format_date(self.state.pregnancy_due_month, self.state.pregnancy_due_day, self.state.pregnancy_due_year)

    def pregnancy_start_date_label(self) -> str:
        if not self.state.pregnancy_active:
            return "No pregnancy"
        return format_date(self.state.pregnancy_start_month, self.state.pregnancy_start_day, self.state.pregnancy_start_year)

    def pregnancy_month_number(self) -> int:
        if not self.state.pregnancy_active:
            return 0
        elapsed = months_between_dates(
            self.state.pregnancy_start_month,
            self.state.pregnancy_start_day,
            self.state.pregnancy_start_year,
            self.state.month,
            self.state.day,
            self.state.year,
        )
        return max(1, min(9, elapsed + 1))

    def pregnancy_gestational_parent_name(self) -> str:
        if self.state.pregnancy_gestational_parent == "player":
            return self.state.player_name
        if self.state.pregnancy_parent_npc_id:
            return self.town_npc_name(self.state.pregnancy_parent_npc_id)
        return "the household"

    def family_planning_discussed_with_spouse(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        return self.has_family_event_flag(f"family_planning_discussed:{npc_id}")

    def family_planning_discussion_lines(self, npc: Dict[str, object]) -> List[str]:
        pregnant_parent = self.state.player_name if self.player_sex == "Female" else str(npc.get("name", "your spouse"))
        return [
            "Family Planning",
            "",
            f"You and {npc.get('name', 'your spouse')} talk about whether you want kids or not.",
            "You discuss space, money, field work, sleep, and whether the house is ready to become louder.",
            "",
            f"If you try for a baby, {pregnant_parent} would carry the pregnancy.",
            "Pregnancy lasts 9 in-game months and the due date is marked on the calendar.",
            "",
            "This conversation unlocks the Try for Baby option when the romance requirements are met.",
        ]

    def discuss_family_planning(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        if self.state.spouse_npc_id != npc_id:
            self.set_message("Family planning is only available with your spouse.")
            return False
        self.state.family_planning_last_discussion_day = self.town_npc_day_key()
        self.mark_family_event_flag(f"family_planning_discussed:{npc_id}")
        self.record_family_event("Family Planning", f"Talked with {npc.get('name', 'your spouse')} about children.")
        self.adjust_town_npc_relationship(npc_id, 2)
        self.vertical_panel_view("Family Planning", self.family_planning_discussion_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Talked with {npc.get('name', 'your spouse')} about family planning.")
        return True

    def family_planning_menu(self, npc: Dict[str, object]):
        while True:
            pregnancy_ok, pregnancy_reason = self.can_start_pregnancy_with_spouse(npc)
            discussed = self.family_planning_discussed_with_spouse(npc)
            items = [
                MenuItem(label="Talk about children", value="talk", enabled=True, hint="required" if not discussed else "discussed"),
                MenuItem(label="Try for baby", value="try", enabled=pregnancy_ok, hint=pregnancy_reason),
                MenuItem(label="Pregnancy status", value="status", enabled=True, hint="active" if self.state.pregnancy_active else "none"),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select("Family Planning", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed family planning.")
                return MENU_BACK
            if choice.value == "talk":
                self.discuss_family_planning(npc)
                continue
            if choice.value == "try":
                if self.start_pregnancy_with_spouse(npc):
                    return "changed"
                continue
            if choice.value == "status":
                self.vertical_panel_view("Family", self.family_status_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue

    def pregnancy_checkup_key(self) -> str:
        if not self.state.pregnancy_active:
            return ""
        return f"{self.state.pregnancy_parent_npc_id}:{self.pregnancy_month_number()}"

    def pregnancy_checkup_available(self) -> bool:
        key = self.pregnancy_checkup_key()
        return bool(key and key not in set(getattr(self.state, "pregnancy_checkup_months_seen", []) or []))

    def pregnancy_checkup_lines(self, npc: Dict[str, object]) -> List[str]:
        month = self.pregnancy_month_number()
        notes = {
            1: "The household is mostly planning: space, food, work pace, and what not to put off.",
            2: "The early routine is becoming real. Gentle meals and reliable sleep matter more.",
            3: "The pregnancy is visible in the calendar now: not urgent, but no longer abstract.",
            4: "The farmhouse starts feeling smaller. Paths, storage, and rest spots matter.",
            5: "Everyone has advice. Some of it is even useful.",
            6: "The household starts preparing a proper nursery corner.",
            7: "Travel and heavy chores need more planning. The due date feels close now.",
            8: "The house moves carefully. The calendar is checked more than once.",
            9: "The baby is due soon. Sleep will trigger the birth once the due date arrives.",
        }
        clinic = "Clinic support is available." if self.is_town_building_unlocked("clinic") else "The Clinic is not restored yet, so the household keeps the check-in simple."
        return [
            "Pregnancy Check-In",
            "",
            f"Month: {month} of 9",
            f"Due date: {self.pregnancy_due_date_label()}",
            f"Pregnant: {self.pregnancy_gestational_parent_name()}",
            "",
            notes.get(month, "The household keeps checking in and adjusting."),
            clinic,
            "",
            f"{npc.get('name', 'Your spouse')} stays close to the practical details: meals, rest, and enough room to move.",
        ]

    def complete_pregnancy_checkup(self, npc: Dict[str, object]) -> bool:
        if not self.state.pregnancy_active:
            self.set_message("No pregnancy is active.")
            return False
        key = self.pregnancy_checkup_key()
        if not key:
            self.set_message("Pregnancy record is incomplete.")
            return False
        if not isinstance(self.state.pregnancy_checkup_months_seen, list):
            self.state.pregnancy_checkup_months_seen = []
        if key not in self.state.pregnancy_checkup_months_seen:
            self.state.pregnancy_checkup_months_seen.append(key)
            self.record_family_event("Pregnancy Check-In", f"Month {self.pregnancy_month_number()} check-in with {npc.get('name', 'your spouse')}.")
            self.adjust_town_npc_relationship(str(npc.get("id", "")), 1)
        self.vertical_panel_view("Pregnancy Check-In", self.pregnancy_checkup_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Completed pregnancy month {self.pregnancy_month_number()} check-in.")
        return True

    def family_planning_progress(self, npc: Dict[str, object]) -> Tuple[int, int, int]:
        npc_id = str(npc.get("id", ""))
        friendship = self.town_npc_relationship(npc_id)
        talks = self.town_npc_dialogue_count(npc_id)
        courtships = self.town_npc_courtship_count(npc_id)
        return friendship, talks, courtships

    def family_planning_progress_lines(self, npc: Dict[str, object]) -> List[str]:
        friendship, talks, courtships = self.family_planning_progress(npc)
        return [
            "Family planning readiness:",
            f"- Friendship: {friendship}/{FAMILY_PLANNING_REQUIRED_FRIENDSHIP}",
            f"- Talks: {talks}/{FAMILY_PLANNING_REQUIRED_TALKS}",
            f"- Courtship time: {courtships}/{FAMILY_PLANNING_REQUIRED_COURTSHIP}",
        ]

    def can_start_pregnancy_with_spouse(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.state.spouse_npc_id or self.state.spouse_npc_id != npc_id:
            return False, "Family planning is only available with your spouse."
        if not self.state.spouse_moved_to_farm:
            return False, "Invite your spouse to move in with you first."
        if self.state.pregnancy_active:
            return False, f"A pregnancy is already underway. Due: {self.pregnancy_due_date_label()}."
        friendship, talks, courtships = self.family_planning_progress(npc)
        if friendship < FAMILY_PLANNING_REQUIRED_FRIENDSHIP:
            return False, f"Needs deeper romance: friendship {friendship}/{FAMILY_PLANNING_REQUIRED_FRIENDSHIP}."
        if talks < FAMILY_PLANNING_REQUIRED_TALKS:
            return False, f"Needs more shared history: talks {talks}/{FAMILY_PLANNING_REQUIRED_TALKS}."
        if courtships < FAMILY_PLANNING_REQUIRED_COURTSHIP:
            return False, f"Needs more spouse time: courtship {courtships}/{FAMILY_PLANNING_REQUIRED_COURTSHIP}."
        if not self.family_planning_discussed_with_spouse(npc):
            return False, "Talk about children together first."
        if self.player_sex == "Female" and self.npc_sex(npc) == "Male":
            return True, "Plan for the player to carry a child."
        if self.player_sex == "Male" and self.npc_sex(npc) == "Female":
            return True, f"Plan for {npc.get('name', 'your spouse')} to carry a child."
        return False, "Pregnancy requires a male and female spouse pair."

    @property
    def player_sex(self) -> str:
        return str(getattr(self.state, "player_sex", "Female"))

    def start_pregnancy_with_spouse(self, npc: Dict[str, object]) -> bool:
        ok, reason = self.can_start_pregnancy_with_spouse(npc)
        if not ok:
            self.set_message(reason)
            return False

        due_month, due_day, due_year = add_months_to_date(self.state.month, self.state.day, self.state.year, 9)
        self.state.pregnancy_active = True
        self.state.pregnancy_parent_npc_id = str(npc.get("id", ""))
        self.state.pregnancy_gestational_parent = "player" if self.player_sex == "Female" else "spouse"
        self.state.pregnancy_start_month = self.state.month
        self.state.pregnancy_start_day = self.state.day
        self.state.pregnancy_start_year = self.state.year
        self.state.pregnancy_due_month = due_month
        self.state.pregnancy_due_day = due_day
        self.state.pregnancy_due_year = due_year

        rows = [
            "Family Planning",
            "",
            f"You and {npc.get('name', 'your spouse')} talk honestly about building a family.",
            "The household begins preparing for a baby.",
            "",
            "Pregnancy:",
            f"Start date: {self.pregnancy_start_date_label()}",
            f"Due date: {self.pregnancy_due_date_label()}",
            "Length: 9 in-game months",
            f"Pregnant: {self.pregnancy_gestational_parent_name()}",
        ]
        rows.extend([""] + self.family_planning_progress_lines(npc))
        self.record_family_event("Pregnancy", f"Pregnancy started with {npc.get('name', 'your spouse')}; due {self.pregnancy_due_date_label()}.", flag=f"pregnancy_started:{self.state.year}:{self.state.month}:{self.state.day}")
        self.vertical_panel_view("Family Planning", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Your household is expecting a baby. Due: {self.pregnancy_due_date_label()}.")
        return True

    def child_name_pool(self, sex: str) -> List[str]:
        if sex == "Male":
            return ["Milo", "Owen", "Noel", "Toby", "Leo", "Reed", "Cal", "Emmett"]
        return ["Lina", "Clara", "June", "Ada", "Nell", "Rose", "Mara", "Elin"]

    def next_child_name(self, sex: str) -> str:
        pool = self.child_name_pool(sex)
        used = {str(child.get("name", "")) for child in self.state.children}
        for offset in range(len(pool)):
            name = pool[(int(self.state.next_child_id) - 1 + offset) % len(pool)]
            if name not in used:
                return name
        return f"Child {self.state.next_child_id}"

    def child_trait_catalog(self) -> List[Dict[str, str]]:
        return [
            {"trait": "Curious", "favorite": "Wildflower", "path": "Scholar", "note": "asks careful questions about ordinary things."},
            {"trait": "Outdoorsy", "favorite": "Berries", "path": "Forager", "note": "wants the door open and pockets full of leaves."},
            {"trait": "Studious", "favorite": "Cave Herbs", "path": "Archivist", "note": "likes labels, lists, and being read to twice."},
            {"trait": "Practical", "favorite": "Wood", "path": "Builder", "note": "turns every corner into a small project."},
            {"trait": "Gentle", "favorite": "Honey", "path": "Caretaker", "note": "notices moods before anyone names them."},
            {"trait": "Bold", "favorite": "Stone", "path": "Explorer", "note": "steps forward first and asks questions second."},
            {"trait": "Musical", "favorite": "Jam Toast", "path": "Artist", "note": "finds rhythm in spoons, rain, and footsteps."},
            {"trait": "Tinkering", "favorite": "Crystal Shard", "path": "Mechanic", "note": "wants to know what every hinge is hiding."},
        ]

    def child_starting_class_catalog(self) -> Dict[str, str]:
        try:
            defs = tactical_class_defs()
        except Exception:
            defs = {}
        catalog: Dict[str, str] = {}
        for class_name in ["Vanguard", "Ranger", "Guardian", "Mystic", "Duelist", "Alchemist"]:
            data = defs.get(class_name, {}) if isinstance(defs, dict) else {}
            catalog[class_name] = str(data.get("desc", "") or "A balanced combat training path.")
        if not catalog:
            catalog = {
                "Vanguard": "Frontline command and reliable pressure.",
                "Ranger": "Ranged control, traps, and precision.",
                "Guardian": "Protection, healing, and steady defense.",
                "Mystic": "Elemental casting and status control.",
                "Duelist": "Mobile single-target pressure.",
                "Alchemist": "Utility, flasks, poison, and support.",
            }
        return catalog

    def child_starting_class_for_path(self, path: str) -> str:
        return {
            "Scholar": "Mystic",
            "Forager": "Ranger",
            "Archivist": "Mystic",
            "Builder": "Guardian",
            "Caretaker": "Guardian",
            "Explorer": "Ranger",
            "Artist": "Duelist",
            "Mechanic": "Alchemist",
            "Farmer": "Vanguard",
            "Cook": "Alchemist",
            "Helper": "Vanguard",
        }.get(str(path or ""), "Vanguard")

    def choose_child_birth_options(self, default_name: str, sex: str, profile_fields: Dict[str, str]) -> Tuple[str, str]:
        child_name = text_entry_menu(
            "New Baby",
            f"Name your {str(sex).lower()} child.",
            default_name,
            16,
        )
        if child_name is None or not str(child_name).strip():
            child_name = default_name

        class_catalog = self.child_starting_class_catalog()
        default_class = str(profile_fields.get("starting_class") or self.child_starting_class_for_path(profile_fields.get("apprentice_path", "")))
        items = [
            MenuItem(
                label=class_name,
                value=class_name,
                enabled=True,
                hint=("suggested" if class_name == default_class else str(desc)[:64]),
            )
            for class_name, desc in class_catalog.items()
        ]
        choice = self.vertical_panel_select("Starting Class", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=False)
        starting_class = str(choice.value) if choice and str(choice.value) in class_catalog else default_class
        return str(child_name), starting_class

    def spouse_trait_bias_for_child(self, parent_npc_id: str) -> Optional[str]:
        data = ROMANCE_NPC_DATA.get(str(parent_npc_id), {})
        style = str(data.get("style", "") if isinstance(data, dict) else "")
        return {
            "curious": "Curious",
            "inventive": "Tinkering",
            "thoughtful": "Studious",
            "adventurous": "Bold",
            "gentle": "Gentle",
            "tender": "Gentle",
            "steady": "Practical",
            "patient": "Outdoorsy",
            "expressive": "Musical",
            "passionate": "Musical",
        }.get(style)

    def child_profile_fields(self, child_id: int, sex: str, parent_npc_id: str, seed: int) -> Dict[str, str]:
        catalog = self.child_trait_catalog()
        rng = random.Random(int(seed) + int(child_id) * 131)
        biased_trait = self.spouse_trait_bias_for_child(parent_npc_id)
        if biased_trait and rng.random() < 0.45:
            entry = next((row for row in catalog if row["trait"] == biased_trait), catalog[0])
        else:
            entry = catalog[rng.randrange(len(catalog))]
        return {
            "personality_trait": entry["trait"],
            "favorite_gift": entry["favorite"],
            "apprentice_path": entry["path"],
            "starting_class": self.child_starting_class_for_path(entry["path"]),
        }

    def ensure_child_profile_fields(self, child: Dict[str, object]) -> Dict[str, object]:
        seed = int(child.get("personality_seed", int(child.get("id", 1)) * 97) or 97)
        fields = self.child_profile_fields(
            int(child.get("id", 1)),
            str(child.get("sex", "Female")),
            str(child.get("parent_npc_id", self.state.spouse_npc_id)),
            seed,
        )
        changed = False
        for key, value in fields.items():
            if not str(child.get(key, "") or ""):
                child[key] = value
                changed = True
        return child

    def child_trait_note(self, child: Dict[str, object]) -> str:
        child = self.ensure_child_profile_fields(child)
        trait = str(child.get("personality_trait", "Curious"))
        entry = next((row for row in self.child_trait_catalog() if row["trait"] == trait), None)
        note = entry["note"] if entry else "is still becoming themselves."
        return f"{child.get('name', 'Your child')} is {trait.lower()} and {note}"

    def child_key(self, child: Dict[str, object]) -> str:
        return str(child.get("id", child.get("name", "child"))).strip() or "child"

    def child_affection_score(self, child: Dict[str, object]) -> int:
        if not isinstance(self.state.child_affection, dict):
            self.state.child_affection = {}
        try:
            return max(0, int(self.state.child_affection.get(self.child_key(child), 0)))
        except Exception:
            return 0

    def child_affection_rank(self, child: Dict[str, object]) -> str:
        score = self.child_affection_score(child)
        if score >= 180:
            return "Devoted"
        if score >= 100:
            return "Attached"
        if score >= 45:
            return "Comfortable"
        if score >= 12:
            return "Warming Up"
        return "New Bond"

    def adjust_child_affection(self, child: Dict[str, object], amount: int) -> int:
        if not isinstance(self.state.child_affection, dict):
            self.state.child_affection = {}
        key = self.child_key(child)
        before = self.child_affection_score(child)
        after = max(0, min(999, before + int(amount)))
        self.state.child_affection[key] = after
        return after - before

    def child_gift_value(self, child: Dict[str, object], item_name: str) -> Tuple[int, str]:
        child = self.ensure_child_profile_fields(child)
        item_name = str(item_name)
        favorite = str(child.get("favorite_gift", "Wildflower"))
        if item_name == favorite:
            return 14, "favorite"
        if is_food_item(item_name):
            return 7, "snack"
        if item_name in ["Wildflower", "Wildflowers", "Berries", "Soft Fiber", "Wood", "Stone", "Cave Herbs", "Crystal Shard", "Honey"]:
            return 5, "liked"
        return 3, "accepted"

    def give_child_gift(self, child: Dict[str, object], item_name: str) -> bool:
        child = self.ensure_child_profile_fields(child)
        key = self.child_key(child)
        today = self.town_npc_day_key()
        if not isinstance(self.state.child_last_gift_day, dict):
            self.state.child_last_gift_day = {}
        if self.state.child_last_gift_day.get(key) == today:
            self.set_message(f"You already gave {child.get('name', 'your child')} a gift today.")
            return False
        item_name = str(item_name)
        if self.state.inventory.get(item_name, 0) <= 0:
            self.set_message(f"You are not carrying {item_name}.")
            return False

        gain, reaction = self.child_gift_value(child, item_name)
        birthday_bonus = 6 if self.is_child_birthday(child) else 0
        gain += birthday_bonus
        self.state.inventory[item_name] -= 1
        if self.state.inventory[item_name] <= 0:
            self.state.inventory.pop(item_name, None)
        actual = self.adjust_child_affection(child, gain)
        self.adjust_family_bond(max(1, actual // 3))
        self.state.child_last_gift_day[key] = today
        if reaction == "favorite":
            detail = f"{child.get('name', 'Your child')} loved receiving {item_name}."
        elif reaction == "snack":
            detail = f"{child.get('name', 'Your child')} happily shared {item_name} as a snack."
        else:
            detail = f"{child.get('name', 'Your child')} accepted {item_name}."
        if birthday_bonus:
            detail += " The birthday timing made it special."
        self.record_family_event("Child Gift", detail)
        self.autosave_with_message(f"Gave {item_name} to {child.get('name', 'your child')}. Affection +{actual}.")
        return True

    def child_gift_menu(self, child: Dict[str, object]):
        child = self.ensure_child_profile_fields(child)
        items: List[MenuItem] = []
        for item_name, qty in sorted(self.state.inventory.items()):
            if int(qty) <= 0:
                continue
            gain, reaction = self.child_gift_value(child, str(item_name))
            items.append(MenuItem(label=str(item_name), value=str(item_name), enabled=True, hint=f"x{qty}; {reaction}; +{gain}"))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        if len(items) == 1:
            self.set_message("You are not carrying anything to give.")
            return False
        choice = self.vertical_panel_select(f"Gift to {child.get('name', 'Child')}", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Child gift cancelled.")
            return False
        return self.give_child_gift(child, str(choice.value))

    def child_lesson_topic_data(self) -> Dict[str, Dict[str, str]]:
        return {
            "Farming": {"path": "Farmer", "note": "soil, seasons, watering, and watching plants closely"},
            "Foraging": {"path": "Forager", "note": "safe wild foods, weather signs, and careful walking"},
            "Crafting": {"path": "Builder", "note": "tools, repairs, storage, and useful little builds"},
            "Cooking": {"path": "Cook", "note": "pantry sense, simple meals, and sharing food"},
            "Mining": {"path": "Explorer", "note": "stone, ore, safety, and when to turn back"},
            "Reading": {"path": "Scholar", "note": "letters, ledgers, maps, and patient attention"},
            "Music": {"path": "Artist", "note": "rhythm, memory, and making the house feel alive"},
            "Care": {"path": "Caretaker", "note": "noticing needs, kindness, and steady routines"},
        }

    def child_lesson_topics(self, child: Dict[str, object]) -> Dict[str, Dict[str, str]]:
        stage = self.household_child_stage(child)
        all_topics = self.child_lesson_topic_data()
        if stage in ["Newborn", "Infant"]:
            return {}
        if stage == "Toddler":
            return {key: all_topics[key] for key in ["Care", "Music", "Reading"]}
        if stage == "Young Child":
            return {key: all_topics[key] for key in ["Farming", "Foraging", "Reading", "Music", "Care"]}
        return all_topics

    def child_learning_map(self, child: Dict[str, object]) -> Dict[str, int]:
        if not isinstance(self.state.child_learning_points, dict):
            self.state.child_learning_points = {}
        key = self.child_key(child)
        raw = self.state.child_learning_points.get(key)
        if not isinstance(raw, dict):
            raw = {}
            self.state.child_learning_points[key] = raw
        clean: Dict[str, int] = {}
        for topic, points in raw.items():
            try:
                clean[str(topic)] = max(0, int(points))
            except Exception:
                continue
        self.state.child_learning_points[key] = clean
        return clean

    def child_top_learning_topic(self, child: Dict[str, object]) -> Tuple[str, int]:
        learning = self.child_learning_map(child)
        if not learning:
            return "", 0
        topic, points = max(learning.items(), key=lambda row: (row[1], row[0]))
        return topic, int(points)

    def update_child_apprentice_path_from_learning(self, child: Dict[str, object]):
        topic, points = self.child_top_learning_topic(child)
        if not topic or points < 3:
            return
        topic_data = self.child_lesson_topic_data().get(topic, {})
        if topic_data.get("path"):
            child["apprentice_path"] = topic_data["path"]

    def teach_child_lesson(self, child: Dict[str, object], topic: str) -> bool:
        child = self.ensure_child_profile_fields(child)
        topics = self.child_lesson_topics(child)
        topic = str(topic)
        if topic not in topics:
            self.set_message(f"{child.get('name', 'Your child')} is not ready for that lesson yet.")
            return False
        key = self.child_key(child)
        today = self.town_npc_day_key()
        if not isinstance(self.state.child_last_lesson_day, dict):
            self.state.child_last_lesson_day = {}
        if self.state.child_last_lesson_day.get(key) == today:
            self.set_message(f"You already spent lesson time with {child.get('name', 'your child')} today.")
            return False
        learning = self.child_learning_map(child)
        learning[topic] = int(learning.get(topic, 0)) + 1
        self.state.child_last_lesson_day[key] = today
        self.adjust_child_affection(child, 5)
        self.adjust_family_bond(2)
        self.update_child_apprentice_path_from_learning(child)
        self.record_family_event("Child Lesson", f"Taught {child.get('name', 'your child')} about {topic.lower()}.")
        self.autosave_with_message(f"Taught {child.get('name', 'your child')} a {topic.lower()} lesson.")
        return True

    def child_learning_lines(self, child: Dict[str, object]) -> List[str]:
        child = self.ensure_child_profile_fields(child)
        topic, points = self.child_top_learning_topic(child)
        lines = [
            f"{child.get('name', 'Child')} Learning",
            "",
            f"Stage: {self.household_child_stage(child)}",
            f"Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
            f"Current path: {child.get('apprentice_path', 'Helper')}",
            f"Starting class: {child.get('starting_class', 'Vanguard')}",
            f"Strongest interest: {topic if topic else 'none yet'}{f' ({points})' if topic else ''}",
            "",
            "Lesson record:",
        ]
        learning = self.child_learning_map(child)
        if learning:
            for lesson_topic, lesson_points in sorted(learning.items(), key=lambda row: (-row[1], row[0])):
                lines.append(f"- {lesson_topic}: {lesson_points}")
        else:
            lines.append("- No lessons recorded yet.")
        lines.extend(["", "Available lessons:"])
        topics = self.child_lesson_topics(child)
        if topics:
            for lesson_topic, data in topics.items():
                lines.append(f"- {lesson_topic}: {data['note']}")
        else:
            lines.append("- Too young for lessons; care and routine matter most.")
        return lines

    def child_lesson_menu(self, child: Dict[str, object]):
        topics = self.child_lesson_topics(child)
        items = [
            MenuItem(label=topic, value=topic, enabled=True, hint=data["path"])
            for topic, data in topics.items()
        ]
        items.append(MenuItem(label="Learning record", value="record", enabled=True, hint=self.household_child_stage(child)))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(f"Lesson with {child.get('name', 'Child')}", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Lesson cancelled.")
            return False
        if choice.value == "record":
            self.vertical_panel_view(f"{child.get('name', 'Child')} Learning", self.child_learning_lines(child), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return False
        return self.teach_child_lesson(child, str(choice.value))

    def child_chore_options(self, child: Dict[str, object]) -> Dict[str, str]:
        stage = self.household_child_stage(child)
        if stage in ["Newborn", "Infant", "Toddler"]:
            return {"Rest and play": "Too young for chores; this keeps the expectation gentle."}
        options = {
            "Set table": "Small household routine.",
            "Sort pantry": "Light organizing and simple food prep.",
            "Rest and play": "No contribution; preserves affection and keeps pressure low.",
        }
        if stage in ["Child", "Teen", "Young Adult"]:
            options.update({
                "Gather forage": "Small berries or flowers from safe nearby paths.",
                "Collect kindling": "A little wood for household supplies.",
                "Study": "Learning-focused help with notes and labels.",
            })
        if stage in ["Teen", "Young Adult"]:
            options.update({
                "Farm rounds": "Light farm prep and seed sorting.",
                "Tinker": "Careful work with odd parts and small repairs.",
            })
        return options

    def assign_child_chore(self, child: Dict[str, object], chore: str) -> bool:
        child = self.ensure_child_profile_fields(child)
        chore = str(chore)
        options = self.child_chore_options(child)
        if chore not in options:
            self.set_message(f"{child.get('name', 'Your child')} is not ready for that chore.")
            return False
        if not isinstance(self.state.child_chore_assignments, dict):
            self.state.child_chore_assignments = {}
        key = self.child_key(child)
        self.state.child_chore_assignments[key] = chore
        if chore == "Rest and play":
            self.adjust_child_affection(child, 2)
        else:
            self.adjust_family_bond(1)
        self.record_family_event("Child Chore", f"{child.get('name', 'Your child')} was assigned: {chore}.")
        self.autosave_with_message(f"{child.get('name', 'Your child')} will focus on {chore.lower()}.")
        return True

    def child_chore_assignment(self, child: Dict[str, object]) -> str:
        if not isinstance(self.state.child_chore_assignments, dict):
            self.state.child_chore_assignments = {}
        return str(self.state.child_chore_assignments.get(self.child_key(child), "Rest and play") or "Rest and play")

    def child_chore_lines(self, child: Dict[str, object]) -> List[str]:
        child = self.ensure_child_profile_fields(child)
        lines = [
            f"{child.get('name', 'Child')} Chores",
            "",
            f"Stage: {self.household_child_stage(child)}",
            f"Current focus: {self.child_chore_assignment(child)}",
            "",
            "Available choices:",
        ]
        for chore, note in self.child_chore_options(child).items():
            marker = "*" if chore == self.child_chore_assignment(child) else "-"
            lines.append(f"{marker} {chore}: {note}")
        lines.extend(["", "Chores only create small overnight help. Automation still handles serious farm labor."])
        return lines

    def child_chore_menu(self, child: Dict[str, object]):
        items = [
            MenuItem(label=chore, value=chore, enabled=True, hint=note)
            for chore, note in self.child_chore_options(child).items()
        ]
        items.append(MenuItem(label="Chore notes", value="notes", enabled=True, hint=self.child_chore_assignment(child)))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(f"Chores for {child.get('name', 'Child')}", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Chore assignment cancelled.")
            return False
        if choice.value == "notes":
            self.vertical_panel_view(f"{child.get('name', 'Child')} Chores", self.child_chore_lines(child), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return False
        return self.assign_child_chore(child, str(choice.value))

    def child_stage_months(self) -> Dict[str, int]:
        return {
            "Infant": 2,
            "Toddler": 12,
            "Young Child": 36,
            "Child": 72,
            "Teen": 144,
            "Young Adult": 216,
        }

    def household_child_raw_age_months(self, child: Dict[str, object]) -> int:
        return months_between_dates(
            int(child.get("birth_month", self.state.month)),
            int(child.get("birth_day", self.state.day)),
            int(child.get("birth_year", self.state.year)),
            self.state.month,
            self.state.day,
            self.state.year,
        )

    def household_child_age_months(self, child: Dict[str, object]) -> int:
        raw_months = self.household_child_raw_age_months(child)
        if (
            bool(getattr(self.state, "aging_and_death_enabled", True))
            or raw_months < 216
        ):
            return raw_months
        return max(216, int(child.get("aging_frozen_months", 216) or 216))

    def household_child_age_display_line(
        self,
        child: Dict[str, object],
    ) -> str:
        age_months = self.household_child_age_months(child)
        if (
            not bool(getattr(self.state, "aging_and_death_enabled", True))
            and age_months >= 216
        ):
            return f"Life stage: {self.household_child_stage(child)}"
        return f"Age: {age_months} month(s)"

    def household_child_stage(self, child: Dict[str, object]) -> str:
        age_months = self.household_child_age_months(child)
        if age_months < 2:
            return "Newborn"
        if age_months < 12:
            return "Infant"
        if age_months < 36:
            return "Toddler"
        if age_months < 72:
            return "Young Child"
        if age_months < 144:
            return "Child"
        if age_months < 216:
            return "Teen"
        return "Young Adult"

    def household_child_activity_label(self, child: Dict[str, object]) -> str:
        self.ensure_child_profile_fields(child)
        stage = self.household_child_stage(child)
        trait = str(child.get("personality_trait", "Curious")).lower()
        return {
            "Newborn": "sleeping in the farmhouse nursery",
            "Infant": f"watching the household with {trait} attention",
            "Toddler": "toddling between furniture and safe edges",
            "Young Child": "playing near the farmhouse table",
            "Child": f"learning household routines with a {trait} streak",
            "Teen": f"testing a {trait} sense of independence",
            "Young Adult": f"helping around the farmhouse as a {trait} young adult",
        }.get(stage, "growing up at home")

    def pregnancy_status_lines(self) -> List[str]:
        if not self.state.pregnancy_active:
            return ["Pregnancy: none active."]
        checkups = len(getattr(self.state, "pregnancy_checkup_months_seen", []) or [])
        return [
            "Pregnancy",
            "",
            f"Month: {self.pregnancy_month_number()} of 9",
            f"Start date: {self.pregnancy_start_date_label()}",
            f"Due date: {self.pregnancy_due_date_label()}",
            f"Pregnant: {self.pregnancy_gestational_parent_name()}",
            f"Monthly check-ins: {checkups}/9",
            "Current check-in: ready" if self.pregnancy_checkup_available() else "Current check-in: completed or not ready",
            "",
            "Birth happens after sleeping once the due date arrives.",
        ]

    def household_child_status_lines(self, child: Dict[str, object]) -> List[str]:
        child = self.ensure_child_profile_fields(child)
        age_months = self.household_child_age_months(child)
        stage = self.household_child_stage(child)
        birth = format_date(int(child.get("birth_month", 1)), int(child.get("birth_day", 1)), int(child.get("birth_year", 1)))
        next_lines = []
        for next_stage, month_mark in self.child_stage_months().items():
            if age_months < month_mark:
                next_lines.append(f"Next stage: {next_stage} at {month_mark} month(s)")
                next_lines.append(f"Time until next stage: {month_mark - age_months} month(s)")
                break
        if not next_lines:
            next_lines.append("Next stage: fully grown for the current system")
        top_topic, top_points = self.child_top_learning_topic(child)
        chore = self.child_chore_assignment(child)
        return [
            f"{child.get('name', 'Child')} - {stage}",
            "",
            f"Sex: {child.get('sex', 'Unknown')}",
            self.household_child_age_display_line(child),
            f"Birthday: {self.child_birthday_label(child)}",
            (
                f"Born: {birth}"
                if (
                    bool(
                        getattr(
                            self.state,
                            "aging_and_death_enabled",
                            True,
                        )
                    )
                    or age_months < 216
                )
                else "Birth record: preserved in the family ledger"
            ),
            f"Other parent: {self.town_npc_name(str(child.get('parent_npc_id', self.state.spouse_npc_id)))}",
            f"Trait: {child.get('personality_trait', 'Curious')}",
            f"Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
            f"Favorite gift: {child.get('favorite_gift', 'Wildflower')}",
            f"Possible path: {child.get('apprentice_path', 'Helper')}",
            f"Starting class: {child.get('starting_class', 'Vanguard')}",
            f"Learning: {top_topic if top_topic else 'none yet'}{f' ({top_points})' if top_topic else ''}",
            f"Chore focus: {chore}",
            *next_lines,
            "",
            f"Activity: {self.household_child_activity_label(child)}.",
            self.child_trait_note(child),
        ]

    def family_status_lines(self) -> List[str]:
        self.normalize_town_npcs()
        lines = ["Family", ""]
        lines.append(f"Player: {self.state.player_name}")
        lines.append(self.player_birth_display_line())
        lines.append(self.player_age_display_line())
        lines.append(f"Generation: {self.state.player_generation}")
        lines.append(f"Health outlook: {self.player_health_outlook()}")
        lines.append("")
        lines.extend(self.marriage_status_lines())
        lines.extend(["", *self.family_bond_lines()])
        lines.append("")
        if self.state.spouse_npc_id:
            lines.append(f"Spouse: {self.town_npc_name(self.state.spouse_npc_id)}")
            lines.append("Household: spouse lives at the farmhouse" if self.state.spouse_moved_to_farm else "Household: spouse has not moved in")
            lines.append(f"Support focus: {self.spouse_support_mode()}")
            spouse = self.npc_record_by_id(self.state.spouse_npc_id)
            if spouse:
                lines.extend([""] + self.family_planning_progress_lines(spouse))
        elif str(getattr(self.state, "engaged_npc_id", "") or ""):
            lines.append(
                f"Fiance: {self.town_npc_name(self.state.engaged_npc_id)}"
            )
            lines.append(f"Wedding: {self.wedding_date_label()}")
        else:
            lines.append("Spouse: none")
        lines.append("")
        lines.extend(self.pregnancy_status_lines())
        lines.extend(["", f"Children: {len(self.state.children)}"])
        for child in self.state.children:
            child = self.ensure_child_profile_fields(child)
            top_topic, top_points = self.child_top_learning_topic(child)
            child_age = self.household_child_age_months(child)
            stage = self.household_child_stage(child)
            adult_age_hidden = (
                not bool(
                    getattr(
                        self.state,
                        "aging_and_death_enabled",
                        True,
                    )
                )
                and child_age >= 216
            )
            age_detail = "" if adult_age_hidden else f", {child_age} month(s)"
            lines.append(
                f"- {child.get('name', 'Child')}: {stage}{age_detail}, "
                f"{child.get('personality_trait')} "
                f"(likes {child.get('favorite_gift')}; affection {self.child_affection_rank(child)}; "
                f"class {child.get('starting_class', 'Vanguard')}; "
                f"{top_topic or 'no lesson focus'}{f' {top_points}' if top_topic else ''})"
            )
        if not self.state.children:
            lines.append("- None yet")
        active_elders = [
            elder
            for elder in getattr(self.state, "dynasty_elders", []) or []
            if isinstance(elder, dict) and elder.get("active", True)
        ]
        lines.extend(["", f"Retired family elders: {len(active_elders)}"])
        for elder in active_elders:
            lines.append(
                f"- {elder.get('name')}: Generation {elder.get('generation')}, "
                f"{self.dynasty_person_age_phrase(elder)}, "
                f"{elder.get('activity', 'keeping family history')}"
            )
        active_kin = [
            kin
            for kin in getattr(self.state, "dynasty_kin", []) or []
            if isinstance(kin, dict) and kin.get("active", True)
        ]
        lines.extend(["", f"Extended family: {len(active_kin)}"])
        for kin in active_kin:
            lines.append(
                f"- {self.dynasty_relation_for_generation(kin)} "
                f"{kin.get('name')}: {self.dynasty_person_age_phrase(kin)}, "
                f"{kin.get('occupation', 'family')}; "
                f"{kin.get('residence', 'Farmhouse')}"
            )
        lines.extend(["", "Household help:", f"- {'Enabled' if self.state.family_help_enabled else 'Disabled'}"])
        candidates = self.household_help_candidate_children()
        helper_count = (1 if self.spouse_lives_on_farm() else 0) + len(candidates)
        lines.append(f"- Potential helpers: {helper_count}")
        recent = list(getattr(self.state, "family_event_log", []) or [])[-6:]
        lines.extend(["", "Recent family memories:"])
        lines.extend(f"- {row}" for row in recent) if recent else lines.append("- No family memories recorded yet.")
        return lines

    def pregnancy_due_reached(self) -> bool:
        return bool(
            self.state.pregnancy_active
            and date_reached(
                self.state.month,
                self.state.day,
                self.state.year,
                self.state.pregnancy_due_month,
                self.state.pregnancy_due_day,
                self.state.pregnancy_due_year,
            )
        )

    def child_milestone_key(self, child: Dict[str, object], stage: Optional[str] = None) -> str:
        return f"child:{child.get('id', '?')}:{stage or self.household_child_stage(child)}"

    def record_child_milestones_overnight(self) -> str:
        if not isinstance(self.state.child_milestone_flags, list):
            self.state.child_milestone_flags = []
        notes: List[str] = []
        for child in self.state.children:
            self.ensure_child_profile_fields(child)
            stage = self.household_child_stage(child)
            key = self.child_milestone_key(child, stage)
            if key in self.state.child_milestone_flags:
                continue
            self.state.child_milestone_flags.append(key)
            if stage == "Newborn":
                continue
            name = str(child.get("name", "Your child"))
            self.record_family_event("Child Milestone", f"{name} reached the {stage} stage.", flag=key)
            notes.append(f" {name} is now a {stage}.")
        return "".join(notes)

    def update_family_overnight(self, interactive: bool = False) -> str:
        if not self.pregnancy_due_reached():
            return self.record_child_milestones_overnight()

        rng = random.Random(self.state.year * 10000 + self.state.month * 100 + self.state.day + int(self.state.next_child_id) * 37)
        sex = "Female" if rng.random() < 0.5 else "Male"
        child_name = self.next_child_name(sex)
        parent_id = self.state.pregnancy_parent_npc_id or self.state.spouse_npc_id
        personality_seed = rng.randint(1000, 999999)
        profile_fields = self.child_profile_fields(int(self.state.next_child_id), sex, parent_id, personality_seed)
        if interactive:
            try:
                child_name, starting_class = self.choose_child_birth_options(child_name, sex, profile_fields)
                profile_fields["starting_class"] = starting_class
            except Exception as exc:
                append_debug_log(f"Child birth options fallback: {type(exc).__name__}: {exc}")
        child = {
            "id": int(self.state.next_child_id),
            "name": child_name,
            "sex": sex,
            "birth_month": self.state.month,
            "birth_day": self.state.day,
            "birth_year": self.state.year,
            "parent_npc_id": parent_id,
            "personality_seed": personality_seed,
            **profile_fields,
        }
        self.state.children.append(child)
        self.record_family_event(
            "Birth",
            f"{child_name} was born. Trait: {profile_fields['personality_trait']}. Starting class: {profile_fields.get('starting_class', 'Vanguard')}. Birthday: {format_birthday(self.state.month, self.state.day)}.",
            flag=f"birth:{child.get('id')}",
        )
        self.mark_family_event_flag(self.child_milestone_key(child, "Newborn"))
        self.state.next_child_id = int(self.state.next_child_id) + 1
        self.state.pregnancy_active = False
        self.state.pregnancy_parent_npc_id = ""
        self.state.pregnancy_gestational_parent = ""
        self.state.pregnancy_start_month = 0
        self.state.pregnancy_start_day = 0
        self.state.pregnancy_start_year = 0
        self.state.pregnancy_due_month = 0
        self.state.pregnancy_due_day = 0
        self.state.pregnancy_due_year = 0
        self.state.pregnancy_checkup_months_seen = []
        return f" {child_name} was born and now lives in the farmhouse. Starting class: {profile_fields.get('starting_class', 'Vanguard')}."

    def household_help_candidate_children(self) -> List[Dict[str, object]]:
        helpers: List[Dict[str, object]] = []
        for child in self.state.children:
            stage = self.household_child_stage(child)
            if stage in ["Young Child", "Child", "Teen", "Young Adult"]:
                helpers.append(self.ensure_child_profile_fields(child))
        return helpers

    def child_help_drop(self, child: Dict[str, object]) -> Tuple[str, int, str]:
        chore = self.child_chore_assignment(child)
        chore_table = {
            "Set table": ("Field Snack", 1, "set the table and saved a simple bite"),
            "Sort pantry": ("Field Snack", 1, "sorted pantry shelves and found a spare snack"),
            "Gather forage": ("Berries", 2, "brought in berries from a careful nearby walk"),
            "Collect kindling": ("Wood", 3, "stacked a little kindling by the door"),
            "Study": ("Cave Herbs", 1, "copied useful herb notes into the family ledger"),
            "Farm rounds": ("Mixed Seeds", 2, "checked the yard and sorted seeds for tomorrow"),
            "Tinker": ("Crystal Shard", 1, "found a small useful shard while checking odd corners"),
            "Rest and play": ("", 0, "rested, played, and kept the house feeling lighter"),
        }
        if chore in chore_table:
            return chore_table[chore]
        trait = str(child.get("personality_trait", "Curious"))
        table = {
            "Curious": ("Wildflower", 1, "pressed a wildflower into the family ledger"),
            "Outdoorsy": ("Berries", 2, "brought in berries from a careful morning walk"),
            "Studious": ("Cave Herbs", 1, "sorted useful herbs from the pantry notes"),
            "Practical": ("Wood", 3, "stacked a little kindling by the door"),
            "Gentle": ("Honey", 1, "saved a small jar of honey for the household"),
            "Bold": ("Stone", 3, "cleared stones from a safe corner of the yard"),
            "Musical": ("Jam Toast", 1, "made a simple breakfast before anyone asked"),
            "Tinkering": ("Crystal Shard", 1, "found a small shard while checking odd corners"),
        }
        return table.get(trait, ("Wildflower", 1, "helped with a small household task"))

    def apply_family_household_help_overnight(self) -> str:
        if not bool(getattr(self.state, "family_help_enabled", True)):
            return ""
        today = self.town_npc_day_key()
        if self.state.family_last_help_day == today:
            return ""
        helpers: List[str] = []
        drops: Dict[str, int] = {}
        if self.spouse_lives_on_farm():
            spouse_name = self.town_npc_name(self.state.spouse_npc_id)
            item, qty, note = self.spouse_help_drop()
            if item and qty > 0:
                drops[item] = drops.get(item, 0) + int(qty)
            helpers.append(f"{spouse_name} {note}")
        for child in self.household_help_candidate_children()[:2]:
            item, qty, note = self.child_help_drop(child)
            if item and qty > 0:
                drops[item] = drops.get(item, 0) + int(qty)
            helpers.append(f"{child.get('name', 'Your child')} {note}")
        if not drops and not helpers:
            return ""
        if drops:
            add_inventory_items(self.state.inventory, drops)
        if self.spouse_support_mode() == "Rest" and self.spouse_lives_on_farm():
            self.adjust_family_bond(2)
        self.state.family_last_help_day = today
        detail = "; ".join(helpers[:3])
        self.record_family_event("Household Help", detail)
        if drops:
            return f" Household help: {format_drops(drops)}."
        return " Household help: the farmhouse felt calmer overnight."

    def toggle_family_help(self) -> bool:
        self.state.family_help_enabled = not bool(getattr(self.state, "family_help_enabled", True))
        self.autosave_with_message(f"Household help {'enabled' if self.state.family_help_enabled else 'disabled'}.")
        return self.state.family_help_enabled

    def family_help_lines(self) -> List[str]:
        lines = [
            "HOUSEHOLD HELP",
            "",
            f"Status: {'enabled' if self.state.family_help_enabled else 'disabled'}",
            "",
            "When enabled, family members may add a small overnight contribution.",
            "This is intentionally light support, not a replacement for farm automation.",
            "",
            "Possible helpers:",
        ]
        if self.spouse_lives_on_farm():
            item, qty, note = self.spouse_help_drop()
            reward = f" ({qty} {item})" if item and qty > 0 else ""
            lines.append(f"- {self.town_npc_name(self.state.spouse_npc_id)}: {note}{reward}")
        for child in self.household_help_candidate_children():
            item, qty, note = self.child_help_drop(child)
            reward = f" ({qty} {item})" if item and qty > 0 else ""
            lines.append(f"- {child.get('name', 'Child')}: {note}{reward}")
        if len(lines) <= 8:
            lines.append("- No older child helpers yet.")
        return lines

    def town_npc_day_key(self) -> str:
        return f"{self.state.year}-{self.state.month}-{self.state.day}"

    def absolute_game_day(self, month: Optional[int] = None, day: Optional[int] = None, year: Optional[int] = None) -> int:
        month = self.state.month if month is None else int(month)
        day = self.state.day if day is None else int(day)
        year = self.state.year if year is None else int(year)
        total = 0
        for y in range(1, max(1, year)):
            total += 366 if is_leap_year(y) else 365
        return total + day_of_year(month, day, year)

    def town_weather_is_bad_for_routines(self) -> bool:
        return str(self.state.weather) in ["Rain", "Rainy", "Storm", "Stormy", "Snow", "Snowy", "Blizzard"]

    def town_weather_is_severe_for_routines(self) -> bool:
        return str(self.state.weather) in ["Storm", "Stormy", "Blizzard"]

    def town_routine_phase(self, hour: Optional[int] = None) -> str:
        h = int(getattr(self.state, "hour", 6) if hour is None else hour)
        if 6 <= h < 8:
            return "wake"
        if 8 <= h < 12:
            return "work_morning"
        if 12 <= h < 14:
            return "lunch"
        if 14 <= h < 17:
            return "work_afternoon"
        if 17 <= h < 21:
            return "evening"
        return "late"

    def town_routine_phase_label(self, phase: Optional[str] = None) -> str:
        return TOWN_ROUTINE_PHASE_LABELS.get(str(phase or self.town_routine_phase()), "Routine")

    def town_time_period(self) -> str:
        phase = self.town_routine_phase()
        if phase in ["wake", "work_morning"]:
            return "morning"
        if phase in ["lunch", "work_afternoon"]:
            return "midday"
        return "evening"

    def town_npc_definition(self, npc_id: str) -> Dict[str, object]:
        for definition in TOWN_NPC_DEFINITIONS:
            if definition.get("id") == npc_id:
                return definition
        return {}

    def town_npc_routine_entry(self, value, activity: str = "") -> Dict[str, object]:
        if isinstance(value, dict):
            entry = dict(value)
            if activity and not entry.get("activity"):
                entry["activity"] = activity
            return entry
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            entry = {"at": (int(value[0]), int(value[1]))}
            if activity:
                entry["activity"] = activity
            return entry
        entry = {"at": (0, 0)}
        if activity:
            entry["activity"] = activity
        return entry

    def town_npc_sleep_home_name(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        overrides = {
            "mayor_ruth": "Mayor's House",
            "lulu_child": "Mayor's House",
            "old_jun": "Inn",
            "finn_fisher": "Inn",
            "cora_courier": "Inn",
            "penny_artist": "Inn",
            "silas_recluse": "Inn",
            "rowan_orchard": "Inn",
            "theo_beekeeper": "Inn",
            "otto_retiree": "Inn",
        }
        home = str(overrides.get(npc_id, npc.get("home", "")))
        if self.town_interior_location_for_name(home):
            return home
        return "Inn"

    def town_npc_home_routine_value(self, npc: Dict[str, object]):
        home = self.town_npc_sleep_home_name(npc)
        if self.town_interior_location_for_name(home):
            return {"inside": home}
        return (int(npc.get("home_x", npc.get("x", 0))), int(npc.get("home_y", npc.get("y", 0))))

    def town_npc_role_activity(self, npc: Dict[str, object], phase: Optional[str] = None) -> str:
        role = str(npc.get("role", "Villager"))
        phase_key = str(phase or self.town_npc_current_routine_phase(npc))
        if phase_key == "wake":
            return "waking up in their bedroom"
        if phase_key == "late":
            return "sleeping in their bedroom"
        activities = TOWN_NPC_ROUTINE_ACTIVITIES.get(role, {})
        if phase_key in activities:
            return str(activities[phase_key])
        if phase_key == "bad_weather":
            return "keeping to a weather-safe routine"
        if phase_key == "wake":
            return "starting the day near home"
        if phase_key == "lunch":
            return "taking a midday break"
        if phase_key == "late":
            return "turning in for the night"
        return "following their routine"

    def town_npc_routine_plan(self, npc: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        definition = self.town_npc_definition(str(npc.get("id", "")))
        schedule = definition.get("schedule", {}) if isinstance(definition, dict) else {}
        role = str(npc.get("role", "Villager"))
        home = self.town_npc_home_routine_value(npc)
        morning = schedule.get("morning", home)
        midday = schedule.get("midday", morning)
        evening = schedule.get("evening", home)
        rain = schedule.get("rain", morning if role in TOWN_INDOOR_WORK_ROLES else home)
        afternoon = schedule.get("afternoon", morning if role in TOWN_INDOOR_WORK_ROLES else midday)

        return {
            "wake": self.town_npc_routine_entry(home, self.town_npc_role_activity(npc, "wake")),
            "work_morning": self.town_npc_routine_entry(morning, self.town_npc_role_activity(npc, "work_morning")),
            "lunch": self.town_npc_routine_entry(schedule.get("lunch", midday), self.town_npc_role_activity(npc, "lunch")),
            "work_afternoon": self.town_npc_routine_entry(afternoon, self.town_npc_role_activity(npc, "work_afternoon")),
            "evening": self.town_npc_routine_entry(evening, self.town_npc_role_activity(npc, "evening")),
            "late": self.town_npc_routine_entry(home, self.town_npc_role_activity(npc, "late")),
            "bad_weather": self.town_npc_routine_entry(rain, self.town_npc_role_activity(npc, "bad_weather")),
        }

    def town_npc_current_routine_phase(self, npc: Dict[str, object]) -> str:
        phase = self.town_routine_phase()
        if phase not in ["late"] and self.town_weather_is_bad_for_routines():
            plan = self.town_npc_routine_plan_without_phase_check(npc)
            if "bad_weather" in plan:
                return "bad_weather"
        return phase

    def town_npc_routine_plan_without_phase_check(self, npc: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        definition = self.town_npc_definition(str(npc.get("id", "")))
        schedule = definition.get("schedule", {}) if isinstance(definition, dict) else {}
        role = str(npc.get("role", "Villager"))
        home = self.town_npc_home_routine_value(npc)
        morning = schedule.get("morning", home)
        midday = schedule.get("midday", morning)
        evening = schedule.get("evening", home)
        rain = schedule.get("rain", morning if role in TOWN_INDOOR_WORK_ROLES else home)
        afternoon = schedule.get("afternoon", morning if role in TOWN_INDOOR_WORK_ROLES else midday)
        return {
            "wake": self.town_npc_routine_entry(home, self.town_npc_role_activity(npc, "wake")),
            "work_morning": self.town_npc_routine_entry(morning, self.town_npc_role_activity(npc, "work_morning")),
            "lunch": self.town_npc_routine_entry(schedule.get("lunch", midday), self.town_npc_role_activity(npc, "lunch")),
            "work_afternoon": self.town_npc_routine_entry(afternoon, self.town_npc_role_activity(npc, "work_afternoon")),
            "evening": self.town_npc_routine_entry(evening, self.town_npc_role_activity(npc, "evening")),
            "late": self.town_npc_routine_entry(home, self.town_npc_role_activity(npc, "late")),
            "bad_weather": self.town_npc_routine_entry(rain, self.town_npc_role_activity(npc, "bad_weather")),
        }

    def town_npc_schedule_raw_value(self, npc: Dict[str, object]):
        if self.spouse_lives_on_farm() and str(npc.get("id", "")) == self.state.spouse_npc_id:
            return {"inside": "Farmhouse", "activity": self.spouse_household_activity_label(npc)}
        plan = self.town_npc_routine_plan(npc)
        phase = self.town_npc_current_routine_phase(npc)
        return plan.get(phase) or plan.get(self.town_routine_phase()) or plan.get("lunch") or (npc.get("home_x", npc.get("x", 0)), npc.get("home_y", npc.get("y", 0)))

    def normalize_town_npc_schedule_value(self, value):
        if isinstance(value, dict):
            if "inside" in value:
                return {"inside": str(value.get("inside", "Building"))}
            if "at" in value:
                value = value.get("at")
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return (int(value[0]), int(value[1]))
        return (0, 0)

    def town_npc_routine_location_label_for_entry(self, entry) -> str:
        raw = self.normalize_town_npc_schedule_value(entry)
        if isinstance(raw, dict) and "inside" in raw:
            return f"inside {raw.get('inside', 'Building')}"
        try:
            ax, ay = int(raw[0]), int(raw[1])
        except Exception:
            return "somewhere in town"
        return f"near {ax},{ay}"

    def town_npc_routine_activity_for_entry(self, npc: Dict[str, object], phase: str, entry) -> str:
        if isinstance(entry, dict) and entry.get("activity"):
            return str(entry.get("activity"))
        return self.town_npc_role_activity(npc, phase)

    def town_npc_routine_brief(self, npc: Dict[str, object], phase: Optional[str] = None) -> str:
        phase_key = str(phase or self.town_npc_current_routine_phase(npc))
        plan = self.town_npc_routine_plan(npc)
        entry = plan.get(phase_key) or plan.get(self.town_routine_phase()) or {}
        activity = self.town_npc_routine_activity_for_entry(npc, phase_key, entry)
        location = self.town_npc_routine_location_label_for_entry(entry)
        return f"{self.town_routine_phase_label(phase_key)}: {activity} ({location})"

    def town_npc_next_routine_phase(self, npc: Dict[str, object]) -> Tuple[str, str]:
        current = self.town_routine_phase()
        try:
            index = TOWN_ROUTINE_PHASE_ORDER.index(current)
        except ValueError:
            index = 0
        next_phase = TOWN_ROUTINE_PHASE_ORDER[(index + 1) % len(TOWN_ROUTINE_PHASE_ORDER)]
        return next_phase, TOWN_ROUTINE_PHASE_STARTS.get(next_phase, "")

    def town_npc_next_routine_line(self, npc: Dict[str, object]) -> str:
        next_phase, starts = self.town_npc_next_routine_phase(npc)
        prefix = f"Next at {starts}" if starts else "Next"
        return f"{prefix}: {self.town_npc_routine_brief(npc, next_phase)}"

    def town_npc_routine_lines(self, npc: Dict[str, object]) -> List[str]:
        plan = self.town_npc_routine_plan(npc)
        lines: List[str] = []
        for phase in TOWN_ROUTINE_PHASE_ORDER:
            entry = plan.get(phase)
            if not entry:
                continue
            start = TOWN_ROUTINE_PHASE_STARTS.get(phase, "")
            label = self.town_routine_phase_label(phase)
            activity = self.town_npc_routine_activity_for_entry(npc, phase, entry)
            location = self.town_npc_routine_location_label_for_entry(entry)
            lines.append(f"{start} {label}: {activity} ({location})")
        if self.town_weather_is_bad_for_routines() and plan.get("bad_weather"):
            entry = plan["bad_weather"]
            activity = self.town_npc_routine_activity_for_entry(npc, "bad_weather", entry)
            location = self.town_npc_routine_location_label_for_entry(entry)
            lines.append(f"Bad weather: {activity} ({location})")
        return lines

    def town_npc_is_indoor(self, npc: Dict[str, object]) -> bool:
        raw = self.normalize_town_npc_schedule_value(self.town_npc_schedule_raw_value(npc))
        return isinstance(raw, dict) and "inside" in raw

    def town_npc_indoor_location(self, npc: Dict[str, object]) -> str:
        raw = self.normalize_town_npc_schedule_value(self.town_npc_schedule_raw_value(npc))
        if isinstance(raw, dict) and "inside" in raw:
            return str(raw.get("inside", "Building"))
        return ""

    def town_npc_location_label(self, npc: Dict[str, object]) -> str:
        if self.town_npc_is_indoor(npc):
            return f"inside {self.town_npc_indoor_location(npc)}"
        ax, ay = self.town_npc_schedule_anchor(npc)
        return f"near {ax},{ay}"

    def town_npc_is_available(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        if not npc_id:
            return False
        if (
            bool(npc.get("deceased", False))
            or npc_id in set(
                getattr(self.state, "deceased_spouse_npc_ids", []) or []
            )
        ):
            return False
        if self.is_household_child_npc(npc):
            return True
        if npc_id == getattr(self.state, "spouse_npc_id", ""):
            return True
        try:
            stage = int(getattr(self.state, "town_development_stage", 0))
        except Exception:
            stage = 0
        if stage >= 3:
            return True
        required_building = TOWN_NPC_REQUIRED_BUILDINGS.get(npc_id, "")
        if required_building:
            return bool(self.is_town_building_unlocked(required_building))
        if stage <= 0:
            return npc_id in set(TOWN_STAGE0_NPC_IDS)
        return True

    def active_town_npcs(self) -> List[Dict[str, object]]:
        self.normalize_town_npcs()
        return [
            npc
            for npc in self.state.town_npcs
            if self.town_npc_is_available(npc)
        ]

    def inactive_town_npcs(self) -> List[Dict[str, object]]:
        self.normalize_town_npcs()
        return [
            npc
            for npc in self.state.town_npcs
            if (
                not bool(npc.get("deceased", False))
                and str(npc.get("id", "")) not in set(
                    getattr(self.state, "deceased_spouse_npc_ids", []) or []
                )
                and not self.town_npc_is_available(npc)
            )
        ]

    def visible_town_npcs(self) -> List[Dict[str, object]]:
        self.normalize_town_npcs()
        return [npc for npc in self.active_town_npcs() if not self.town_npc_is_indoor(npc)]

    def town_npc_schedule_anchor(self, npc: Dict[str, object]) -> Tuple[int, int]:
        raw = self.normalize_town_npc_schedule_value(self.town_npc_schedule_raw_value(npc))
        if isinstance(raw, dict) and "inside" in raw:
            # Indoor NPCs keep their last known map position but do not render on the town map.
            return int(npc.get("current_anchor_x", npc.get("home_x", npc.get("x", 0)))), int(npc.get("current_anchor_y", npc.get("home_y", npc.get("y", 0))))

        try:
            ax, ay = int(raw[0]), int(raw[1])
        except Exception:
            ax, ay = int(npc.get("home_x", npc.get("x", 0))), int(npc.get("home_y", npc.get("y", 0)))

        safe_tiles = [".", "=", ":", ",", "?", "!"]
        if 0 <= ax < TOWN_WIDTH and 0 <= ay < TOWN_HEIGHT and self.town_map[ay][ax] in safe_tiles:
            return ax, ay

        best: Optional[Tuple[int, int]] = None
        best_dist = 9999
        for radius in range(1, 5):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = ax + dx, ay + dy
                    if not (0 <= nx < TOWN_WIDTH and 0 <= ny < TOWN_HEIGHT):
                        continue
                    if self.town_map[ny][nx] not in safe_tiles:
                        continue
                    dist = abs(dx) + abs(dy)
                    if dist < best_dist:
                        best = (nx, ny)
                        best_dist = dist
            if best is not None:
                return best

        return int(npc.get("home_x", npc.get("x", 0))), int(npc.get("home_y", npc.get("y", 0)))

    def town_npc_relationship(self, npc_id: str) -> int:
        procedural = self.procedural_resident_by_id(str(npc_id))
        if procedural:
            try:
                return int(procedural.get("relationship", 0))
            except Exception:
                return 0
        try:
            return int(self.state.town_npc_relationships.get(str(npc_id), 0))
        except Exception:
            return 0

    def town_npc_courtship_count(self, npc_id: str) -> int:
        if not isinstance(self.state.town_npc_courtship_counts, dict):
            self.state.town_npc_courtship_counts = {}
        try:
            return max(0, int(self.state.town_npc_courtship_counts.get(str(npc_id), 0)))
        except Exception:
            return 0

    def increment_town_npc_courtship_count(self, npc_id: str):
        npc_id = str(npc_id)
        self.state.town_npc_courtship_counts[npc_id] = self.town_npc_courtship_count(npc_id) + 1

    def relationship_milestones_for_npc(self, npc_id: str) -> set:
        if not isinstance(self.state.town_npc_relationship_milestones, dict):
            self.state.town_npc_relationship_milestones = {}
        milestones = self.state.town_npc_relationship_milestones.get(str(npc_id), [])
        if not isinstance(milestones, list):
            milestones = []
        clean = {str(flag) for flag in milestones if flag is not None}
        self.state.town_npc_relationship_milestones[str(npc_id)] = sorted(clean)
        return clean

    def has_relationship_milestone(self, npc_id: str, milestone: str) -> bool:
        return str(milestone) in self.relationship_milestones_for_npc(str(npc_id))

    def set_relationship_milestone(self, npc_id: str, milestone: str):
        npc_id = str(npc_id)
        milestones = self.relationship_milestones_for_npc(npc_id)
        milestones.add(str(milestone))
        self.state.town_npc_relationship_milestones[npc_id] = sorted(milestones)

    def is_sample_milestone_npc(self, npc_id: str) -> bool:
        return str(npc_id) in RELATIONSHIP_MILESTONE_SAMPLE_NPCS

    def relationship_gain_cap_for_npc(self, npc_id: str) -> int:
        npc_id = str(npc_id)
        cap = RELATIONSHIP_MAX
        if not self.is_sample_milestone_npc(npc_id):
            return cap
        talks = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        if talks < 3:
            cap = min(cap, 59)
        if not self.has_relationship_milestone(npc_id, "close_friend"):
            cap = min(cap, 99)
        if not self.has_relationship_milestone(npc_id, "trusted"):
            cap = min(cap, 149)
        return cap

    def relationship_gate_hint_for_npc(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        if not self.is_sample_milestone_npc(npc_id):
            return ""
        talks = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        if talks < 3:
            return f"Needs more conversations before friendship can deepen ({talks}/3 talks)."
        if not self.has_relationship_milestone(npc_id, "close_friend"):
            return "Needs a personal moment before becoming a Close Friend."
        if not self.has_relationship_milestone(npc_id, "trusted"):
            return "Needs a trust moment before becoming Trusted."
        return "Major friendship gates cleared."

    def relationship_is_waiting_on_gate(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        cap = self.relationship_gain_cap_for_npc(npc_id)
        return cap < RELATIONSHIP_MAX and self.town_npc_relationship(npc_id) >= cap

    def recent_gifts_for_npc(self, npc_id: str) -> List[Dict[str, object]]:
        if not isinstance(self.state.town_npc_recent_gifts, dict):
            self.state.town_npc_recent_gifts = {}
        npc_id = str(npc_id)
        gifts = self.state.town_npc_recent_gifts.get(npc_id, [])
        if not isinstance(gifts, list):
            gifts = []
        today = self.absolute_game_day()
        clean: List[Dict[str, object]] = []
        for gift in gifts:
            if not isinstance(gift, dict):
                continue
            try:
                day_number = int(gift.get("day_number", today))
            except Exception:
                day_number = today
            if today - day_number <= 7:
                clean.append({
                    "item": str(gift.get("item", "")),
                    "day": str(gift.get("day", "")),
                    "day_number": day_number,
                })
        self.state.town_npc_recent_gifts[npc_id] = clean[-10:]
        return self.state.town_npc_recent_gifts[npc_id]

    def remember_recent_gift_for_npc(self, npc_id: str, item: str):
        npc_id = str(npc_id)
        gifts = self.recent_gifts_for_npc(npc_id)
        gifts.append({
            "item": str(item),
            "day": self.town_npc_day_key(),
            "day_number": self.absolute_game_day(),
        })
        self.state.town_npc_recent_gifts[npc_id] = gifts[-10:]

    def repeated_gift_count_for_npc(self, npc_id: str, item: str) -> int:
        canonical_item = str(item)
        return sum(1 for gift in self.recent_gifts_for_npc(str(npc_id)) if str(gift.get("item", "")) == canonical_item)

    def apply_gift_fatigue(self, npc_id: str, item: str, amount: int, birthday: bool = False) -> Tuple[int, str]:
        if birthday or amount <= 0:
            return amount, ""
        repeats = self.repeated_gift_count_for_npc(npc_id, item)
        if repeats <= 0:
            return amount, ""
        if amount <= 2:
            return 1, "familiar gift"
        reduced = max(1, int(round(amount * 0.5)))
        return reduced, "familiar gift"

    def birthday_gift_bonus(self, base_amount: int) -> int:
        if base_amount >= 8:
            return 6
        if base_amount >= 4:
            return 4
        if base_amount > 0:
            return 2
        return 0

    def town_npc_friendship_label(self, points: int) -> str:
        if points >= 200:
            return "Deep Bond"
        if points >= 150:
            return "Trusted"
        if points >= 100:
            return "Close Friend"
        if points >= 60:
            return "Friend"
        if points >= 25:
            return "Acquaintance"
        if points >= 0:
            return "Stranger"
        return "Strained"

    def adjust_town_npc_relationship(self, npc_id: str, amount: int) -> int:
        current = self.town_npc_relationship(npc_id)
        amount = int(amount)
        target = current + amount
        if amount > 0:
            cap = self.relationship_gain_cap_for_npc(npc_id)
            if current >= cap:
                target = current
            else:
                target = min(target, cap)
        target = max(RELATIONSHIP_MIN, min(RELATIONSHIP_MAX, target))
        self.state.town_npc_relationships[npc_id] = target
        procedural = self.procedural_resident_by_id(str(npc_id))
        if procedural:
            procedural["relationship"] = target
        return target - current

    def best_gift_item_for_npc(self, npc: Dict[str, object]) -> Optional[str]:
        definition = self.town_npc_definition(str(npc.get("id", "")))
        likes = list(definition.get("likes", [])) if isinstance(definition, dict) else []
        fallback_items = [
            "Ancient Preserves", "Wildflower Honey", "Berry Jam", "Mushroom Preserve",
            "Wildflower", "Berries", "Bird Egg", "Duck Egg", "Milk",
            "Carrot", "Tomato", "Corn", "Watercress", "Cave Herbs",
        ]
        candidates = []
        for item in list(likes) + fallback_items + list(self.state.inventory.keys()):
            if item in candidates:
                continue
            if self.state.inventory.get(item, 0) <= 0:
                continue
            amount, reaction = self.gift_quality_for_npc(npc, item)
            if amount > 0:
                candidates.append((amount, reaction, item))
        if not candidates:
            return None
        candidates.sort(key=lambda row: (row[0], 1 if row[1] == "loved" else 0, row[2]), reverse=True)
        return candidates[0][2]

    def is_giftable_inventory_item(self, item_name: str) -> bool:
        if self.state.inventory.get(item_name, 0) <= 0:
            return False
        if item_name in INFRASTRUCTURE_DATA:
            return False
        if item_name.endswith(" Seeds"):
            return False
        return True

    def gift_reaction_label(self, amount: int, reaction: str) -> str:
        if reaction == "loved":
            return "loved"
        if amount < 0:
            return "disliked"
        if amount >= 8:
            return "liked"
        if amount >= 4:
            return "appreciated"
        return "neutral"

    def gift_menu_items_for_npc(self, npc: Dict[str, object]) -> List[MenuItem]:
        items: List[MenuItem] = []
        birthday_today = self.is_npc_birthday(npc)
        for item_name, qty in sorted(self.state.inventory.items()):
            if not self.is_giftable_inventory_item(item_name):
                continue
            amount, reaction = self.gift_quality_for_npc(npc, item_name)
            display_amount, fatigue_note = self.apply_gift_fatigue(str(npc.get("id", "")), item_name, amount, birthday=birthday_today)
            if birthday_today and amount > 0:
                display_amount += self.birthday_gift_bonus(amount)
            reaction_label = self.gift_reaction_label(amount, reaction)
            hint = f"x{qty}; {reaction_label}; relationship {display_amount:+}"
            if fatigue_note:
                hint = f"{fatigue_note}; {hint}"
            if birthday_today and amount > 0:
                hint = f"birthday; {hint}"
            items.append(MenuItem(
                label=item_name,
                value=item_name,
                enabled=True,
                hint=hint,
            ))
        return items

    def artisan_goods(self) -> List[str]:
        return [
            "Berry Jam",
            "Pickled Turnips",
            "Pickled Carrots",
            "Tomato Preserve",
            "Corn Relish",
            "Mushroom Preserve",
            "Wildflower Honey",
            "Ancient Preserves",
        ]

    def is_artisan_good(self, item_name: str) -> bool:
        return item_name in set(self.artisan_goods())

    def artisan_good_lines(self, item_name: str) -> List[str]:
        if not self.is_artisan_good(item_name):
            return []
        lines = [
            "Artisan good:",
            "Made with a Preserves Jar.",
            "Good for shipping, gifting, eating, and pantry recipes.",
        ]
        uses = self.ingredient_usage_lines(item_name)
        if uses:
            lines.extend(["", "Pantry recipe uses:"])
            lines.extend(uses)
        return lines

    def gift_quality_for_npc(self, npc: Dict[str, object], item: str) -> Tuple[int, str]:
        definition = self.town_npc_definition(str(npc.get("id", "")))
        likes = list(definition.get("likes", [])) if isinstance(definition, dict) else []
        dislikes = list(definition.get("dislikes", [])) if isinstance(definition, dict) else []
        try:
            canonical_item = self.canonical_item_name(item)
            canonical_likes = [self.canonical_item_name(name) for name in likes]
            canonical_dislikes = [self.canonical_item_name(name) for name in dislikes]
        except Exception:
            canonical_item = item
            canonical_likes = likes
            canonical_dislikes = dislikes
        if item in likes or canonical_item in canonical_likes:
            return 8, "loved"
        if item in dislikes or canonical_item in canonical_dislikes:
            return -5, "disliked"
        if self.is_artisan_good(item):
            return 5, "liked artisan gift"
        role = str(npc.get("role", "Villager"))
        role_affinity = {
            "Seed Seller": ["Seeds", "Turnip", "Carrot", "Tomato", "Corn", "Wildflower", "Watercress"],
            "Blacksmith": ["Ore", "Coal", "Bar", "Stone", "Crystal", "Quartz", "Amethyst", "Topaz"],
            "Miner": ["Ore", "Coal", "Bar", "Stone", "Crystal", "Quartz", "Amethyst", "Topaz"],
            "Carpenter": ["Wood", "Hardwood", "Fiber", "Stone Path", "Fence"],
            "Animal Keeper": ["Egg", "Milk", "Fiber", "Animal Medicine"],
            "Doctor": ["Cave Herbs", "Honey", "Watercress", "Animal Medicine", "Milk"],
            "Fisher": ["Minnow", "Sunfish", "Carp", "Chub", "Fish"],
            "Chef": ["Carrot", "Tomato", "Corn", "Turnip", "Salad", "Stew", "Jam", "Preserve"],
            "Innkeeper": ["Salad", "Egg", "Milk", "Berries", "Honey"],
            "Gardener": ["Wildflower", "Watercress", "Maple", "Lettuce"],
            "Artist": ["Wildflower", "Fiber", "Maple", "Honey"],
            "Recluse": ["Cave", "Spores", "Mushroom", "Chub"],
            "Orchardist": ["Maple", "Honey", "Jam", "Berries", "Wildflower", "Fruit"],
            "Tailor": ["Fiber", "Soft Fiber", "Wildflower", "Honey", "Maple"],
            "Musician": ["Jam", "Toast", "Honey", "Sunfish", "Wildflower"],
            "Beekeeper": ["Honey", "Wildflower", "Flowers", "Maple", "Jam"],
            "Botanist": ["Cave Herbs", "Spores", "Mushroom", "Watercress", "Wildflower"],
            "Mechanic": ["Bar", "Crystal", "Sprinkler", "Coal", "Ore", "Quartz"],
            "Scholar": ["Cave Herbs", "Maple", "Preserves", "Honey", "Quartz"],
            "Retiree": ["Toast", "Milk", "Berries", "Chub", "Maple"],
        }
        if any(token in item for token in role_affinity.get(role, [])):
            return 4, "appreciated role gift"
        if item in FOOD_DATA or item in FISH_DATA or item in RESOURCE_ITEMS:
            return 2, "accepted"
        return 1, "accepted"

    def give_selected_gift_to_town_npc(self, npc: Dict[str, object], item: str) -> bool:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        today = self.town_npc_day_key()
        if self.state.town_npc_last_gift_day.get(npc_id) == today:
            self.set_message(f"You already gave {npc.get('name', 'them')} a gift today.")
            return False
        if not self.is_giftable_inventory_item(item):
            self.set_message(f"You cannot give {item}.")
            return False
        self.state.inventory[item] -= 1
        amount, reaction = self.gift_quality_for_npc(npc, item)
        base_amount = amount
        gift_dialogue_category = self.gift_reaction_dialogue_category(base_amount, reaction)
        fatigue_note = ""
        birthday_today = self.is_npc_birthday(npc)
        amount, fatigue_note = self.apply_gift_fatigue(npc_id, item, amount, birthday=birthday_today)
        birthday_bonus = 0
        if birthday_today and base_amount > 0:
            birthday_bonus = self.birthday_gift_bonus(base_amount)
            amount += birthday_bonus
        actual_gain = self.adjust_town_npc_relationship(npc_id, amount)
        self.state.town_npc_last_gift_day[npc_id] = today
        self.state.town_npc_last_gift_reactions[npc_id] = {
            "day": today,
            "item": item,
            "reaction": reaction,
            "category": gift_dialogue_category,
            "relationship": int(actual_gain),
            "fatigue": fatigue_note,
        }
        self.remember_recent_gift_for_npc(npc_id, item)

        if reaction == "loved":
            response = f"{npc.get('name')} accepts {item} with a look that says you understood them exactly."
        elif reaction == "liked artisan gift":
            response = f"{npc.get('name')} studies the work on {item} and seems genuinely impressed."
        elif reaction == "appreciated role gift":
            response = f"{npc.get('name')} turns {item} over, already imagining where it fits into their work."
        elif reaction == "liked":
            response = f"{npc.get('name')} thanks you for {item}; it will not go to waste."
        elif reaction == "disliked":
            response = f"{npc.get('name')} accepts {item} politely, but the pause gives them away."
        else:
            response = f"{npc.get('name')} accepts {item} and tucks it away with a small thanks."
        if fatigue_note and actual_gain > 0:
            response += " The repeated gift feels familiar, so it means a little less this week."
        if birthday_bonus:
            response += " Remembering their birthday makes the gift mean more."
        gift_line = self.choose_npc_dialogue(npc, immediate_category=gift_dialogue_category).get("text", "")
        if gift_line:
            response += f' "{gift_line}"'
        if actual_gain > 0:
            gain_text = f" Relationship +{actual_gain}."
        elif actual_gain < 0:
            gain_text = f" Relationship {actual_gain}."
        else:
            gain_text = " Relationship unchanged."
        self.autosave_with_message(f"Gave {item} to {npc.get('name')}. {response}{gain_text}")
        return True

    def give_gift_to_town_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        if self.state.town_npc_last_gift_day.get(npc_id) == self.town_npc_day_key():
            self.set_message(f"You already gave {npc.get('name', 'them')} a gift today.")
            return False

        items = self.gift_menu_items_for_npc(npc)
        if not items:
            self.set_message("You are not carrying anything suitable to give.")
            return False
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))

        choice = self.vertical_panel_select(
            f"Gift to {npc.get('name', 'Villager')}",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Gift cancelled.")
            return False
        return self.give_selected_gift_to_town_npc(npc, str(choice.value))

    def town_npc_status_lines(self, npc: Dict[str, object]) -> List[str]:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        points = self.town_npc_relationship(npc_id)
        definition = self.town_npc_definition(npc_id)
        likes = ", ".join(definition.get("likes", [])[:5]) if isinstance(definition, dict) else "Unknown"
        dislikes = ", ".join(definition.get("dislikes", [])[:4]) if isinstance(definition, dict) else "Unknown"
        lines = [
            f"{npc.get('name')} - {npc.get('role')}",
            "",
            f"Friendship: {self.town_npc_friendship_label(points)} ({points})",
            f"Relationship tier: {self.relationship_tier_for_npc(npc)}",
            self.town_npc_relationship_note(npc),
            f"Milestone: {self.relationship_gate_hint_for_npc(npc)}" if self.relationship_gate_hint_for_npc(npc) else "Milestone: none",
            f"Sex: {self.npc_sex(npc)}",
            f"Birthday: {self.npc_birthday_label(npc)}",
            f"Mood: {self.town_npc_mood(npc)}",
            f"District: {npc.get('district')}",
            f"Home: {npc.get('home')}",
            f"Current location: {self.town_npc_location_label(npc)}",
            f"Routine: {self.town_npc_routine_brief(npc)}",
            self.town_npc_next_routine_line(npc),
            f"Times spoken to: {self.state.town_npc_dialogue_counts.get(npc_id, 0)}",
            "",
            f"Likes: {likes or 'Unknown'}",
            f"Dislikes: {dislikes or 'Unknown'}",
            "",
        ]
        if self.state.spouse_npc_id == npc_id:
            lines.insert(8, "Household: lives at the farmhouse" if self.state.spouse_moved_to_farm else "Household: can be invited to move onto the farm")
        lines.extend(self.town_npc_profile_lines(npc)[2:])
        lines.extend(["", "Tip:", "NPCs can be indoors during work hours or bad weather. Check the directory if someone is not visible outside."])
        return lines

    def town_npc_route_hint(self, npc: Dict[str, object]) -> str:
        if self.town_npc_is_indoor(npc):
            place = self.town_npc_indoor_location(npc)
            door_hints = {
                "Farmhouse": "Farmhouse: Use your farm door.",
                "General Store": "General Store: Use the North Market Street door at 10,8.",
                "Blacksmith": "Blacksmith: Use the North Market Street door at 25,8.",
                "Library": "Library: Use the North Market Street door at 41,8.",
                "Mayor's House": "Mayor's House: Use the Civic Boulevard door at 10,20.",
                "Inn": "Inn: Use the Civic Boulevard door at 25,20.",
                "Town Hall": "Town Hall: Use the Civic Boulevard door at 41,20.",
                "Furniture Store": "Furniture Store: Use the Civic Boulevard door at 57,20.",
                "Carpenter": "Carpenter: Use the Civic Boulevard door at 73,20.",
                "Animal Store": "Animal Store: Use the Civic Boulevard door at 89,20.",
                "Clinic": "Clinic: Use the South Civic Walk door at 10,32.",
                "Market Row": "Market Row: Use the market promenade door at 73,32.",
            }
            return door_hints.get(place, f"Look inside {place}.")
        ax, ay = self.town_npc_schedule_anchor(npc)
        if ay <= 13:
            district = "North Market Street"
        elif 14 <= ay <= 23:
            district = "Civic Boulevard"
        elif ax >= 92 and 24 <= ay <= 43:
            district = "East Commons"
        elif ay >= 44:
            district = "South Canal Walk"
        elif 24 <= ay <= 36 and 36 <= ax <= 68:
            district = "Central Park"
        elif ay >= 34:
            district = "South Civic Walk"
        elif ax >= 64:
            district = "Market Promenade"
        else:
            district = "grid road loop"
        return f"Look around the {district} near {ax},{ay}."

    def town_npc_whereabouts_lines(self, npc: Dict[str, object]) -> List[str]:
        npc_id = str(npc.get("id", ""))
        lines = [
            f"WHERE IS {str(npc.get('name', 'NPC')).upper()}?",
            "",
            f"Role: {npc.get('role')}",
            f"Friendship: {self.town_npc_friendship_label(self.town_npc_relationship(npc_id))} ({self.town_npc_relationship(npc_id)})",
            f"Mood: {self.town_npc_mood(npc)}",
            f"Current location: {self.town_npc_location_label(npc)}",
            f"Routine: {self.town_npc_routine_brief(npc)}",
            self.town_npc_next_routine_line(npc),
            "",
            "How to find them:",
            self.town_npc_route_hint(npc),
            "",
        ]
        if self.is_marriageable_npc(npc):
            lines.insert(4, f"Romance: {self.romance_label_for_npc(npc)}")
        if self.town_npc_is_indoor(npc):
            lines.append("They are currently indoors and will not appear on the outdoor town map.")
        else:
            ax, ay = self.town_npc_schedule_anchor(npc)
            lines.append(f"They should be visible outdoors near {ax},{ay}, unless they wander a few tiles away.")
        lines.extend([
            "",
            "Today's routine:",
        ])
        lines.extend(self.town_npc_routine_lines(npc))
        lines.extend([
            "",
            "Tip:",
            "NPC locations change with time of day and weather.",
        ])
        return lines

    def find_town_npc_menu(self):
        self.normalize_town_npcs()
        while True:
            items: List[MenuItem] = []
            for npc in self.active_town_npcs():
                npc_id = str(npc.get("id", ""))
                hint = f"{self.town_routine_phase_label(self.town_npc_current_routine_phase(npc))}; {self.town_npc_location_label(npc)}"
                friendship = self.town_npc_friendship_label(self.town_npc_relationship(npc_id))
                items.append(MenuItem(
                    label=f"{npc.get('name')} - {npc.get('role')}",
                    value=npc_id,
                    enabled=True,
                    hint=f"{friendship}; {self.romance_label_for_npc(npc)}; {hint}" if self.is_marriageable_npc(npc) else f"{friendship}; {hint}",
                ))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Find NPC", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed Find NPC.")
                return
            npc = next((n for n in self.active_town_npcs() if str(n.get("id", "")) == str(choice.value)), None)
            if npc:
                self.vertical_panel_view(f"Find {npc.get('name')}", self.town_npc_whereabouts_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue

    def town_npc_directory_lines(self) -> List[str]:
        self.normalize_town_npcs()
        active_npcs = self.active_town_npcs()
        inactive_count = len(self.inactive_town_npcs())
        lines = ["TOWN NPC DIRECTORY", "", f"Active residents: {len(active_npcs)}", f"Away until restoration: {inactive_count}", ""]
        for npc in active_npcs:
            npc_id = str(npc.get("id", ""))
            points = self.town_npc_relationship(npc_id)
            lines.append(f"{npc.get('name')} - {npc.get('role')}")
            lines.append(f"  {self.town_npc_friendship_label(points)} ({points}) | {self.town_npc_mood(npc)}")
            if self.is_marriageable_npc(npc):
                lines.append(f"  Romance: {self.romance_label_for_npc(npc)}")
            lines.append(f"  {self.town_npc_routine_brief(npc)}")
            lines.append(f"  {self.town_npc_location_label(npc)} | {self.town_npc_route_hint(npc)}")
        if inactive_count:
            lines.extend(["", "Later arrivals are tied to closed services such as the Clinic, Blacksmith, Library, Animal Store, and Market Row."])
        lines.extend(["", "Use Town Hall's Find NPC service for full daily schedules.", "NPCs can be outdoors, indoors, or sheltering from bad weather."])
        return lines

    def make_default_town_npcs(self) -> List[Dict[str, object]]:
        npcs: List[Dict[str, object]] = []
        for npc in TOWN_NPC_DEFINITIONS:
            birthday_month, birthday_day = NPC_BIRTHDAY_BY_ID.get(str(npc["id"]), (3, 1))
            npcs.append({
                "id": npc["id"],
                "name": npc["name"],
                "symbol": "@",
                "sex": NPC_SEX_BY_ID.get(str(npc["id"]), "Unknown"),
                "birthday_month": birthday_month,
                "birthday_day": birthday_day,
                "role": npc["role"],
                "home": npc["home"],
                "x": int(npc["x"]),
                "y": int(npc["y"]),
                "home_x": int(npc["x"]),
                "home_y": int(npc["y"]),
                "district": npc["district"],
                "wander_radius": int(npc["wander_radius"]),
                "current_anchor_x": int(npc["x"]),
                "current_anchor_y": int(npc["y"]),
                "indoors": False,
                "indoor_location": "",
                "facing": "DOWN",
                "activity": "",
                "routine_phase": "",
                "routine_label": "",
                "routine_day_key": "",
                "routine_weather": "",
                "steps_today": 0,
            })
        return npcs

    def normalize_town_npcs(self):
        if not isinstance(self.state.town_npcs, list) or not self.state.town_npcs:
            self.state.town_npcs = self.make_default_town_npcs()
        if not isinstance(self.state.town_npc_dialogue_counts, dict):
            self.state.town_npc_dialogue_counts = {}

        definitions = {npc["id"]: npc for npc in TOWN_NPC_DEFINITIONS}
        existing_ids = set()
        clean: List[Dict[str, object]] = []
        for npc in self.state.town_npcs:
            if not isinstance(npc, dict):
                continue
            npc_id = str(npc.get("id", ""))
            if npc_id not in definitions:
                continue
            base = definitions[npc_id]
            birthday_month, birthday_day = NPC_BIRTHDAY_BY_ID.get(npc_id, (3, 1))
            existing_ids.add(npc_id)
            try:
                x = int(npc.get("x", base["x"]))
                y = int(npc.get("y", base["y"]))
            except Exception:
                x, y = int(base["x"]), int(base["y"])
            if not (0 <= x < TOWN_WIDTH and 0 <= y < TOWN_HEIGHT):
                x, y = int(base["x"]), int(base["y"])
            if hasattr(self, "town_map") and 0 <= x < TOWN_WIDTH and 0 <= y < TOWN_HEIGHT:
                if self.town_map[y][x] not in [".", "=", ":", ","]:
                    x, y = self.nearest_town_passable_tile(int(base["x"]), int(base["y"]))
            npc.update({
                "id": npc_id,
                "name": str(npc.get("name", base["name"])),
                "symbol": "@",
                "sex": NPC_SEX_BY_ID.get(npc_id, "Unknown"),
                "birthday_month": birthday_month,
                "birthday_day": birthday_day,
                "role": str(npc.get("role", base["role"])),
                "home": str(npc.get("home", base["home"])),
                "x": x,
                "y": y,
                "home_x": int(npc.get("home_x", base["x"])),
                "home_y": int(npc.get("home_y", base["y"])),
                "district": str(npc.get("district", base["district"])),
                "wander_radius": int(npc.get("wander_radius", base["wander_radius"])),
                "current_anchor_x": int(npc.get("current_anchor_x", base["x"])),
                "current_anchor_y": int(npc.get("current_anchor_y", base["y"])),
                "indoors": bool(npc.get("indoors", False)),
                "indoor_location": str(npc.get("indoor_location", "")),
                "facing": str(npc.get("facing", "DOWN")),
                "activity": str(npc.get("activity", "")),
                "routine_phase": str(npc.get("routine_phase", "")),
                "routine_label": str(npc.get("routine_label", "")),
                "routine_day_key": str(npc.get("routine_day_key", "")),
                "routine_weather": str(npc.get("routine_weather", "")),
                "steps_today": int(npc.get("steps_today", 0)) if str(npc.get("steps_today", 0)).isdigit() else 0,
            })
            clean.append(npc)
        for npc_id, base in definitions.items():
            if npc_id not in existing_ids:
                birthday_month, birthday_day = NPC_BIRTHDAY_BY_ID.get(npc_id, (3, 1))
                clean.append({
                    "id": base["id"], "name": base["name"], "symbol": "@",
                    "sex": NPC_SEX_BY_ID.get(str(base["id"]), "Unknown"),
                    "birthday_month": birthday_month, "birthday_day": birthday_day,
                    "role": base["role"], "home": base["home"],
                    "x": int(base["x"]), "y": int(base["y"]),
                    "home_x": int(base["x"]), "home_y": int(base["y"]),
                    "district": base["district"], "wander_radius": int(base["wander_radius"]),
                    "current_anchor_x": int(base["x"]), "current_anchor_y": int(base["y"]),
                    "indoors": False, "indoor_location": "",
                    "facing": "DOWN",
                    "activity": "",
                    "routine_phase": "",
                    "routine_label": "",
                    "routine_day_key": "",
                    "routine_weather": "",
                    "steps_today": 0,
                })
        self.state.town_npcs = clean
        if not isinstance(self.state.town_npc_relationships, dict):
            self.state.town_npc_relationships = {}
        if not isinstance(self.state.town_npc_last_talk_day, dict):
            self.state.town_npc_last_talk_day = {}
        if not isinstance(self.state.town_npc_last_gift_day, dict):
            self.state.town_npc_last_gift_day = {}
        if not isinstance(self.state.town_npc_last_gift_reactions, dict):
            self.state.town_npc_last_gift_reactions = {}
        if not isinstance(self.state.town_npc_recent_gifts, dict):
            self.state.town_npc_recent_gifts = {}
        if not isinstance(self.state.town_npc_last_court_day, dict):
            self.state.town_npc_last_court_day = {}
        if not isinstance(self.state.town_npc_courtship_counts, dict):
            self.state.town_npc_courtship_counts = {}
        if not isinstance(self.state.town_npc_relationship_milestones, dict):
            self.state.town_npc_relationship_milestones = {}
        if not isinstance(self.state.town_npc_recent_dialogue_ids, dict):
            self.state.town_npc_recent_dialogue_ids = {}
        if not isinstance(self.state.town_npc_last_proposal_day, dict):
            self.state.town_npc_last_proposal_day = {}
        if not isinstance(self.state.dating_npc_ids, list):
            self.state.dating_npc_ids = []
        self.state.dating_npc_ids = [
            str(npc_id)
            for npc_id in self.state.dating_npc_ids
            if (
                str(npc_id) in definitions
                or self.procedural_resident_by_id(str(npc_id)) is not None
            )
        ]
        if (
            str(self.state.spouse_npc_id or "")
            and str(self.state.spouse_npc_id or "") not in definitions
            and self.procedural_resident_by_id(
                str(self.state.spouse_npc_id or "")
            )
            is None
        ):
            self.state.spouse_npc_id = ""
            self.state.spouse_moved_to_farm = False
        if (
            str(getattr(self.state, "engaged_npc_id", "") or "")
            and str(self.state.engaged_npc_id) not in definitions
            and self.procedural_resident_by_id(
                str(self.state.engaged_npc_id)
            )
            is None
        ):
            self.state.engaged_npc_id = ""
            self.state.wedding_month = 0
            self.state.wedding_day = 0
            self.state.wedding_year = 0
        for npc in self.state.town_npcs:
            npc_id = str(npc.get("id", ""))
            self.state.town_npc_relationships.setdefault(npc_id, 0)
            try:
                self.state.town_npc_courtship_counts[npc_id] = max(0, int(self.state.town_npc_courtship_counts.get(npc_id, 0)))
            except Exception:
                self.state.town_npc_courtship_counts[npc_id] = 0
            recent = self.state.town_npc_recent_dialogue_ids.get(npc_id, [])
            if not isinstance(recent, list):
                recent = []
            self.state.town_npc_recent_dialogue_ids[npc_id] = [str(line_id) for line_id in recent[-8:] if line_id is not None]
            reaction = self.state.town_npc_last_gift_reactions.get(npc_id, {})
            if not isinstance(reaction, dict):
                reaction = {}
            if reaction and str(reaction.get("day", "")) != self.town_npc_day_key():
                reaction = {}
            self.state.town_npc_last_gift_reactions[npc_id] = reaction
            gifts = self.state.town_npc_recent_gifts.get(npc_id, [])
            if not isinstance(gifts, list):
                gifts = []
            clean_gifts: List[Dict[str, object]] = []
            today_number = self.absolute_game_day()
            for gift in gifts:
                if not isinstance(gift, dict):
                    continue
                try:
                    day_number = int(gift.get("day_number", today_number))
                except Exception:
                    day_number = today_number
                if today_number - day_number > 7:
                    continue
                clean_gifts.append({
                    "item": str(gift.get("item", "")),
                    "day": str(gift.get("day", "")),
                    "day_number": day_number,
                })
            self.state.town_npc_recent_gifts[npc_id] = clean_gifts[-10:]
            milestones = self.state.town_npc_relationship_milestones.get(npc_id, [])
            if not isinstance(milestones, list):
                milestones = []
            self.state.town_npc_relationship_milestones[npc_id] = sorted({str(flag) for flag in milestones if flag is not None})

    def town_interior_location_for_name(self, name: str) -> str:
        return TOWN_INTERIOR_LOCATION_BY_NAME.get(str(name or "").strip().lower(), "")

    def current_town_interior_name(self) -> str:
        return TOWN_INTERIOR_NAME_BY_LOCATION.get(self.state.location, self.location_label())

    def town_npc_indoor_state(self, npc: Dict[str, object]) -> str:
        place = self.town_npc_indoor_location(npc)
        if str(place).lower() == "farmhouse":
            return "HouseInterior"
        return self.town_interior_location_for_name(place)

    def is_household_child_npc(self, npc: Dict[str, object]) -> bool:
        return str(npc.get("id", "")).startswith("household_child:")

    def child_record_from_npc(self, npc: Dict[str, object]) -> Optional[Dict[str, object]]:
        npc_id = str(npc.get("id", ""))
        if not npc_id.startswith("household_child:"):
            return None
        child_id_text = npc_id.split(":", 1)[1]
        for child in self.state.children:
            if str(child.get("id", "")) == child_id_text:
                return child
        return None

    def spouse_farmhouse_position(self) -> Tuple[int, int]:
        min_x, min_y, max_x, max_y = self.house_floor_bounds()
        center_x = (min_x + max_x) // 2
        phase = self.town_routine_phase()
        if phase == "wake":
            preferred = [(min_x + 6, min_y + 2), (min_x + 9, min_y + 3), (center_x, min_y + 4)]
        elif phase == "lunch":
            preferred = [(center_x + 1, min_y + 7), (max_x - 8, min_y + 4), (center_x, max_y - 5)]
        elif phase == "work_afternoon":
            preferred = [(min_x + 5, max_y - 4), (max_x - 6, min_y + 4), (center_x, max_y - 5)]
        elif phase == "evening":
            preferred = [(center_x - 2, max_y - 5), (max_x - 4, max_y - 4), (center_x + 2, max_y - 4)]
        elif phase == "late":
            preferred = [(min_x + 6, min_y + 2), (min_x + 9, min_y + 3), (center_x, min_y + 4)]
        else:
            preferred = [
                (min_x + 9, min_y + 3),
                (max_x - 5, min_y + 4),
                (center_x, min_y + 7),
                (max_x - 4, max_y - 4),
            ]
        for x, y in preferred:
            if self.in_house_bounds_for_npc(x, y):
                return x, y
        return min_x + 1, min_y + 1

    def spouse_household_activity_label(self, npc: Dict[str, object]) -> str:
        mode = self.spouse_support_mode().lower()
        home = (
            self.household_residence_label()
            if hasattr(self, "household_residence_label")
            else "the farmhouse"
        )
        if self.state.pregnancy_active:
            if self.state.pregnancy_gestational_parent == "spouse" and self.state.pregnancy_parent_npc_id == str(npc.get("id", "")):
                return f"moving carefully through pregnancy month {self.pregnancy_month_number()} with a {mode} household focus"
            return f"preparing {home} for pregnancy month {self.pregnancy_month_number()} with a {mode} household focus"
        if self.state.children:
            youngest = min(self.state.children, key=lambda child: self.household_child_age_months(child))
            return f"keeping an eye on {youngest.get('name', 'the child')} and the household's {mode} focus"
        phase = self.town_routine_phase()
        return {
            "wake": f"starting the morning in {home}",
            "work_morning": "checking household chores before town errands",
            "lunch": f"setting out a simple meal in {home}",
            "work_afternoon": f"using the desk in {home} for shared plans",
            "evening": f"winding down in {home}",
            "late": "getting ready for sleep",
            "bad_weather": f"keeping close to {home} during bad weather",
        }.get(phase, f"settling into life in {home}")

    def in_house_bounds_for_npc(self, x: int, y: int) -> bool:
        if not (0 <= y < len(self.house_map) and 0 <= x < len(self.house_map[y])):
            return False
        if self.house_map[y][x] not in self.house_floor_tiles():
            return False
        if x == self.state.player_x and y == self.state.player_y:
            return False
        for key, obj_name in self.state.placed_objects.items():
            parsed = self.parse_object_key(str(key))
            if not parsed:
                continue
            location, ax, ay = parsed
            if location == "HouseInterior" and (x, y) in self.object_footprint_tiles(str(obj_name), ax, ay):
                return False
        return True

    def household_child_positions(self) -> Dict[int, Tuple[int, int]]:
        min_x, min_y, max_x, max_y = self.house_floor_bounds()
        center_x = (min_x + max_x) // 2
        preferred = [
            (min_x + 3, min_y + 5),
            (min_x + 5, min_y + 5),
            (min_x + 7, min_y + 6),
            (center_x - 2, max_y - 4),
            (center_x + 2, max_y - 4),
            (max_x - 6, max_y - 5),
            (max_x - 4, max_y - 3),
            (min_x + 4, max_y - 3),
        ]
        used = set()
        if self.spouse_lives_on_farm():
            used.add(self.spouse_farmhouse_position())
        positions: Dict[int, Tuple[int, int]] = {}

        for child in self.state.children:
            try:
                child_id = int(child.get("id", 0))
            except Exception:
                continue
            assigned: Optional[Tuple[int, int]] = None
            for x, y in preferred:
                if (x, y) in used:
                    continue
                if self.in_house_bounds_for_npc(x, y):
                    assigned = (x, y)
                    break
            if assigned is None:
                for y in range(min_y, max_y + 1):
                    for x in range(min_x, max_x + 1):
                        if (x, y) in used:
                            continue
                        if self.in_house_bounds_for_npc(x, y):
                            assigned = (x, y)
                            break
                    if assigned is not None:
                        break
            if assigned is None:
                assigned = (min_x, min_y)
            positions[child_id] = assigned
            used.add(assigned)
        return positions

    def household_child_npcs(self) -> List[Dict[str, object]]:
        positions = self.household_child_positions()
        npcs: List[Dict[str, object]] = []
        for child in self.state.children:
            try:
                child_id = int(child.get("id", 0))
            except Exception:
                continue
            x, y = positions.get(child_id, self.spouse_farmhouse_position())
            stage = self.household_child_stage(child)
            npcs.append({
                "id": f"household_child:{child_id}",
                "name": str(child.get("name", f"Child {child_id}")),
                "symbol": "@",
                "sex": str(child.get("sex", "Unknown")),
                "role": stage,
                "home": "Farmhouse",
                "x": x,
                "y": y,
                "district": "Farmhouse",
                "facing": "DOWN",
                "activity": self.household_child_activity_label(child),
            })
        return npcs

    def household_child_talk_lines(self, child: Dict[str, object]) -> List[str]:
        stage = self.household_child_stage(child)
        lines = self.household_child_status_lines(child)
        if self.is_child_birthday(child):
            lines.extend(["", f"Today is {child.get('name', 'your child')}'s birthday. The farmhouse feels a little more awake because of it."])
        lines.extend(["", "Check-in:"])
        if stage == "Newborn":
            lines.append(f"{child.get('name', 'The baby')} sleeps in short, delicate stretches.")
        elif stage == "Infant":
            lines.append(f"{child.get('name', 'The baby')} follows your voice and settles when the house is calm.")
        elif stage == "Toddler":
            lines.append(f"{child.get('name', 'The toddler')} toddles a few brave steps before grabbing the nearest safe edge.")
        elif stage == "Young Child":
            lines.append(f"{child.get('name', 'Your child')} turns ordinary furniture into whole adventures and asks for one more story.")
        elif stage == "Child":
            lines.append(f"{child.get('name', 'Your child')} asks about the farm, the town, and why adults always look busy.")
        elif stage == "Teen":
            lines.append(f"{child.get('name', 'Your teen')} wants more responsibility and pretends that does not also mean more chores.")
        else:
            lines.append(f"{child.get('name', 'Your child')} has grown into a capable young adult, still rooted in the household for now.")
        top_topic, top_points = self.child_top_learning_topic(child)
        lines.extend([
            "",
            f"Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
            f"Chore focus: {self.child_chore_assignment(child)}",
            f"Learning focus: {top_topic if top_topic else 'none yet'}{f' ({top_points})' if top_topic else ''}",
        ])
        return lines

    def household_child_menu(self, npc: Dict[str, object]):
        child = self.child_record_from_npc(npc)
        if not child:
            self.set_message("The household record for this child is missing.")
            return
        while True:
            items = [
                MenuItem(label="Check in", value="talk", enabled=True),
                MenuItem(label="Status", value="status", enabled=True, hint=self.household_child_stage(child)),
                MenuItem(label="Traits", value="traits", enabled=True, hint=str(self.ensure_child_profile_fields(child).get("personality_trait", ""))),
                MenuItem(label="Give gift", value="gift", enabled=True, hint=str(child.get("favorite_gift", "favorite"))),
                MenuItem(label="Lesson", value="lesson", enabled=True, hint="daily"),
                MenuItem(label="Chore", value="chore", enabled=True, hint=self.child_chore_assignment(child)),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(str(child.get("name", "Child")), items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message(f"Stopped checking on {child.get('name', 'the child')}.")
                return
            if choice.value == "talk":
                self.vertical_panel_view(str(child.get("name", "Child")), self.household_child_talk_lines(child), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                self.set_message(f"Checked in on {child.get('name', 'the child')}.")
                return
            if choice.value == "status":
                self.vertical_panel_view(str(child.get("name", "Child")), self.household_child_status_lines(child), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "traits":
                child = self.ensure_child_profile_fields(child)
                rows = [
                    f"{child.get('name', 'Child')} Traits",
                    "",
                    f"Trait: {child.get('personality_trait', 'Curious')}",
                    f"Favorite gift: {child.get('favorite_gift', 'Wildflower')}",
                    f"Possible path: {child.get('apprentice_path', 'Helper')}",
                    f"Starting class: {child.get('starting_class', 'Vanguard')}",
                    f"Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
                    "",
                    self.child_trait_note(child),
                    "",
                    f"Current chore: {self.child_chore_assignment(child)}",
                ]
                self.vertical_panel_view(str(child.get("name", "Child")), rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "gift":
                if self.child_gift_menu(child):
                    return
                continue
            if choice.value == "lesson":
                if self.child_lesson_menu(child):
                    return
                continue
            if choice.value == "chore":
                if self.child_chore_menu(child):
                    return
                continue

    def indoor_npc_base_position(self, location: str) -> Tuple[int, int]:
        if self.town_routine_phase() in ["wake", "late"]:
            return {
                "HouseInterior": self.spouse_farmhouse_position(),
                "GeneralStoreInterior": (27, 9),
                "BlacksmithInterior": (27, 9),
                "LibraryInterior": (27, 9),
                "MayorHouseInterior": (27, 9),
                "InnInterior": (27, 9),
                "FurnitureStoreInterior": (27, 9),
                "CarpenterStoreInterior": (27, 9),
                "AnimalStoreInterior": (27, 9),
                "ClinicInterior": (27, 9),
                "TownHallInterior": (27, 9),
                "MarketRowInterior": (27, 9),
                "MuseumInterior": (27, 9),
            }.get(location, (27, 9))
        return {
            "HouseInterior": self.spouse_farmhouse_position(),
            "GeneralStoreInterior": (27, 8),
            "BlacksmithInterior": (27, 8),
            "LibraryInterior": (27, 9),
            "MayorHouseInterior": (27, 10),
            "InnInterior": (24, 9),
            "FurnitureStoreInterior": (27, 9),
            "CarpenterStoreInterior": (27, 9),
            "AnimalStoreInterior": (27, 9),
            "ClinicInterior": (27, 9),
            "TownHallInterior": (27, 9),
            "MarketRowInterior": (27, 12),
            "MuseumInterior": (27, 9),
        }.get(location, (27, 9))

    def town_indoor_npc_positions(self, normalize: bool = True) -> Dict[str, Tuple[int, int]]:
        if not self.on_town_interior():
            return {}
        if normalize:
            self.normalize_town_npcs()
        npcs = [
            npc for npc in self.active_town_npcs()
            if self.town_npc_is_indoor(npc) and self.town_npc_indoor_state(npc) == self.state.location
        ]
        npcs.sort(key=lambda npc: str(npc.get("id", "")))
        base_x, base_y = self.indoor_npc_base_position(self.state.location)
        offsets = [
            (0, 0), (-2, 0), (2, 0), (0, 2), (0, -2), (-4, 1), (4, 1),
            (-3, 3), (3, 3), (-5, -1), (5, -1), (-1, 4), (1, 4),
        ]
        positions: Dict[str, Tuple[int, int]] = {}
        used = set()

        for npc in npcs:
            npc_id = str(npc.get("id", ""))
            assigned: Optional[Tuple[int, int]] = None
            for dx, dy in offsets:
                cx, cy = base_x + dx, base_y + dy
                for radius in range(0, 5):
                    candidates = [(cx, cy)] if radius == 0 else []
                    if radius > 0:
                        for yy in range(cy - radius, cy + radius + 1):
                            for xx in range(cx - radius, cx + radius + 1):
                                if abs(xx - cx) + abs(yy - cy) == radius:
                                    candidates.append((xx, yy))
                    for tx, ty in candidates:
                        if (tx, ty) in used:
                            continue
                        if tx == self.state.player_x and ty == self.state.player_y:
                            continue
                        if self.in_active_bounds(tx, ty) and self.passable(tx, ty):
                            assigned = (tx, ty)
                            break
                    if assigned is not None:
                        break
                if assigned is not None:
                    break
            if assigned is not None:
                positions[npc_id] = assigned
                used.add(assigned)
        return positions

    def town_npc_position_lookup(self) -> Dict[Tuple[int, int], Dict[str, object]]:
        if (
            hasattr(self, "procedural_town_resident_position_lookup")
            and (
                (hasattr(self, "on_wilderness") and self.on_wilderness())
                or (
                    hasattr(self, "on_procedural_town_interior")
                    and self.on_procedural_town_interior()
                )
            )
        ):
            procedural_lookup = self.procedural_town_resident_position_lookup()
            if procedural_lookup:
                return procedural_lookup
        if not (self.on_town() or self.on_town_interior() or self.on_house()):
            return {}
        self.normalize_town_npcs()
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}

        if self.on_house():
            if self.spouse_lives_on_farm():
                spouse = self.npc_record_by_id(self.state.spouse_npc_id)
                if spouse and not self.travel_follower_identity_for_npc_id(str(spouse.get("id", ""))):
                    lookup[self.spouse_farmhouse_position()] = spouse
            for child_npc in self.household_child_npcs():
                try:
                    if self.travel_follower_identity_for_npc_id(str(child_npc.get("id", ""))):
                        continue
                    lookup[(int(child_npc.get("x", 0)), int(child_npc.get("y", 0)))] = child_npc
                except Exception:
                    continue
            if hasattr(self, "dynasty_elder_npcs"):
                for elder in self.dynasty_elder_npcs():
                    position = (
                        int(elder.get("x", 12)),
                        int(elder.get("y", 9)),
                    )
                    if position in lookup:
                        position = (
                            min(34, position[0] + 2),
                            min(16, position[1] + 1),
                        )
                    lookup[position] = elder
            if hasattr(self, "dynasty_kin_npcs"):
                for relative in self.dynasty_kin_npcs():
                    position = (
                        int(relative.get("x", 18)),
                        int(relative.get("y", 9)),
                    )
                    while position in lookup:
                        position = (
                            min(34, position[0] + 1),
                            min(16, position[1] + 1),
                        )
                    lookup[position] = relative
            return lookup

        if self.on_town_interior():
            positions = self.town_indoor_npc_positions(normalize=False)
            for npc in self.active_town_npcs():
                npc_id = str(npc.get("id", ""))
                if self.travel_follower_identity_for_npc_id(npc_id):
                    continue
                position = positions.get(npc_id)
                if position:
                    lookup[position] = npc
            return lookup

        for npc in self.active_town_npcs():
            if self.travel_follower_identity_for_npc_id(str(npc.get("id", ""))):
                continue
            if self.town_npc_is_indoor(npc):
                continue
            try:
                lookup[(int(npc.get("x", -1)), int(npc.get("y", -1)))] = npc
            except Exception:
                continue
        return lookup

    def town_npc_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        return self.town_npc_position_lookup().get((int(x), int(y)))

    def render_town_npc(self, npc: Dict[str, object]) -> str:
        if npc.get("procedural_caravan"):
            return colorize("C", C.SHOP)
        return colorize("@", self.town_npc_role_color(npc))

    def town_npc_passable_tile(self, x: int, y: int, ignore_npc_id: Optional[str] = None) -> bool:
        if not self.on_town():
            return False
        if not self.in_active_bounds(x, y):
            return False
        if x == self.state.player_x and y == self.state.player_y:
            return False
        if self.travel_follower_at(x, y):
            return False
        for other in self.active_town_npcs():
            if str(other.get("id", "")) == str(ignore_npc_id or ""):
                continue
            if self.travel_follower_identity_for_npc_id(str(other.get("id", ""))):
                continue
            if self.town_npc_is_indoor(other):
                continue
            try:
                if int(other.get("x", -1)) == int(x) and int(other.get("y", -1)) == int(y):
                    return False
            except Exception:
                continue
        tile = self.active_map()[y][x]
        return tile in [".", "=", ":", ",", "?", "!"]

    def nearest_town_npc_passable_tile(self, x: int, y: int, ignore_npc_id: Optional[str] = None, radius_limit: int = 8) -> Tuple[int, int]:
        if self.town_npc_passable_tile(x, y, ignore_npc_id):
            return x, y
        for radius in range(1, radius_limit + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = x + dx, y + dy
                    if self.town_npc_passable_tile(nx, ny, ignore_npc_id):
                        return nx, ny
        return self.nearest_town_passable_tile(x, y)

    def reset_town_npc_daily_routines(self):
        self.normalize_town_npcs()
        for npc in self.state.town_npcs:
            npc["steps_today"] = 0
            npc["routine_phase"] = ""
            npc["routine_label"] = ""
            npc["routine_day_key"] = self.town_npc_day_key()
            npc["routine_weather"] = str(self.state.weather)

    def update_town_npcs(self, force_reanchor: bool = False):
        if not self.on_town():
            return
        self.normalize_town_npcs()
        for npc in self.active_town_npcs():
            try:
                npc_id = str(npc.get("id", ""))
                phase = self.town_npc_current_routine_phase(npc)
                previous_phase = str(npc.get("routine_phase", ""))
                previous_weather = str(npc.get("routine_weather", ""))
                phase_changed = (
                    force_reanchor
                    or previous_phase != phase
                    or previous_weather != str(self.state.weather)
                    or str(npc.get("routine_day_key", "")) != self.town_npc_day_key()
                )
                npc["routine_phase"] = phase
                npc["routine_label"] = self.town_routine_phase_label(phase)
                npc["routine_weather"] = str(self.state.weather)
                npc["routine_day_key"] = self.town_npc_day_key()

                if self.town_npc_is_indoor(npc):
                    npc["indoors"] = True
                    npc["indoor_location"] = self.town_npc_indoor_location(npc)
                    npc["activity"] = self.town_npc_activity_label(npc)
                    continue

                npc["indoors"] = False
                npc["indoor_location"] = ""
                x = int(npc.get("x", 0))
                y = int(npc.get("y", 0))
                ax, ay = self.town_npc_schedule_anchor(npc)
                npc["current_anchor_x"] = ax
                npc["current_anchor_y"] = ay
                npc["activity"] = self.town_npc_activity_label(npc)

                # If an NPC was effectively unavailable/indoors and is now outside, place them near their current anchor.
                if phase_changed or self.town_map[y][x] not in [".", "=", ":", ","] or abs(x - ax) + abs(y - ay) > max(12, int(npc.get("wander_radius", 5)) * 3):
                    npc["x"], npc["y"] = self.nearest_town_npc_passable_tile(ax, ay, npc_id)
                    continue

                if self.town_npc_near_player(npc, distance=2):
                    self.town_npc_face_player(npc)
                    if random.random() > 0.12:
                        continue

                role = str(npc.get("role", "Villager"))
                move_chance = 0.28
                if role in ["Courier", "Kid", "Traveler", "Musician"]:
                    move_chance = 0.48
                elif role in ["Orchardist", "Beekeeper", "Botanist"]:
                    move_chance = 0.34
                elif role in ["Recluse", "Librarian", "Mayor", "Scholar", "Retiree"]:
                    move_chance = 0.18
                if phase == "lunch":
                    move_chance *= 1.2
                elif phase in ["work_morning", "work_afternoon"] and role in TOWN_INDOOR_WORK_ROLES:
                    move_chance *= 0.65
                elif phase == "late":
                    move_chance *= 0.45
                if self.town_weather_is_bad_for_routines():
                    move_chance *= 0.55
                if self.town_weather_is_severe_for_routines():
                    move_chance *= 0.25
                if self.town_time_period() == "evening":
                    move_chance *= 0.75

                if random.random() > move_chance:
                    continue

                radius = max(3, int(npc.get("wander_radius", 5)) // 2 + 2)
                options = [(1,0),(-1,0),(0,1),(0,-1)]
                random.shuffle(options)

                if abs(x - ax) + abs(y - ay) > radius:
                    options = sorted(options, key=lambda d: abs((x + d[0]) - ax) + abs((y + d[1]) - ay))

                for dx, dy in options:
                    nx, ny = x + dx, y + dy
                    if abs(nx - ax) + abs(ny - ay) > radius + 2:
                        continue
                    if self.town_npc_passable_tile(nx, ny, npc_id):
                        npc["x"], npc["y"] = nx, ny
                        npc["steps_today"] = int(npc.get("steps_today", 0)) + 1
                        if dx > 0:
                            npc["facing"] = "RIGHT"
                        elif dx < 0:
                            npc["facing"] = "LEFT"
                        elif dy > 0:
                            npc["facing"] = "DOWN"
                        elif dy < 0:
                            npc["facing"] = "UP"
                        break
            except Exception:
                continue

    def town_npc_role_dialogue_lines(self, npc: Dict[str, object]) -> List[str]:
        first = self.choose_npc_dialogue(npc)
        second = self.choose_npc_dialogue(npc)
        lines = [f'"{first.get("text", "Good to see you.")}"']
        if second.get("id") != first.get("id"):
            lines.append(f'"{second.get("text", "Good to see you.")}"')
        return lines

    def town_npc_weather_dialogue_line(self, npc: Dict[str, object]) -> str:
        choices = self.curated_dialogue_lines_for_category(npc, self.weather_dialogue_category())
        note = choices[0] if choices else "They keep one eye on the weather before committing to plans."
        return f"Weather: {note} ({self.state.weather} today.)"

    def town_npc_season_dialogue_line(self, npc: Dict[str, object]) -> str:
        choices = self.curated_dialogue_lines_for_category(npc, str(self.state.season).lower())
        note = choices[0] if choices else f"{self.state.season} is shaping today's routine."
        return f"Season: {note}"

    def town_npc_memory_lines(self, npc: Dict[str, object], already_talked: bool) -> List[str]:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        friendship = self.town_npc_relationship(npc_id)
        count = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        lines: List[str] = []
        if count >= 12:
            lines.append("They start talking before you have fully stepped into view.")
        elif count >= 5:
            lines.append("They have started to recognize your usual route through town.")
        if friendship >= 100:
            lines.append("They no longer spend energy making every sentence sound proper.")
        elif friendship >= 60:
            lines.append("They seem genuinely glad you stopped.")
        elif friendship < 0:
            lines.append("They keep the conversation short enough to escape if needed.")
        if already_talked:
            lines.append("You already talked today, so this is more of a quick check-in.")
        return lines

    def town_npc_errand_hint_line(self, npc: Dict[str, object]) -> str:
        errand = self.errand_for_npc(npc)
        if errand.get("completed"):
            return "Their errand is already complete today."
        if self.can_complete_errand(errand):
            return f"You have what they need today: {errand.get('qty')} {errand.get('item')}."
        return f"Today's errand: {errand.get('qty')} {errand.get('item')}."

    def town_npc_daily_pick(self, npc: Dict[str, object], category: str, choices: List[str]) -> str:
        if not choices:
            return ""
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        seed_text = f"{self.town_npc_day_key()}:{npc_id}:{category}:{self.state.season}:{self.state.weather}:{self.town_time_period()}"
        index = sum(ord(ch) for ch in seed_text) % len(choices)
        return choices[index]

    def relationship_tier_for_npc(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        if self.state.spouse_npc_id == npc_id:
            return "Spouse"
        if npc_id in set(self.state.dating_npc_ids or []):
            return "Dating"
        points = self.town_npc_relationship(npc_id)
        if points >= 200:
            return "Deep Bond"
        if points >= 150:
            return "Trusted"
        if points >= 100:
            return "Close Friend"
        if points >= 60:
            return "Friend"
        if points >= 25:
            return "Acquaintance"
        return "Stranger"

    def relationship_dialogue_category_for_tier(self, tier: str) -> str:
        if tier in ["Spouse", "Dating", "Deep Bond"]:
            return "deep_bond"
        if tier in ["Trusted", "Close Friend"]:
            return "high_friendship"
        if tier in ["Friend", "Acquaintance"]:
            return "medium_friendship"
        return "low_friendship"

    def weather_dialogue_category(self) -> str:
        weather = str(self.state.weather).strip().lower()
        return {
            "rain": "rainy",
            "rainy": "rainy",
            "storm": "stormy",
            "stormy": "stormy",
            "snow": "snowy",
            "snowy": "snowy",
            "blizzard": "blizzard",
            "cloud": "cloudy",
            "cloudy": "cloudy",
            "sun": "sunny",
            "sunny": "sunny",
        }.get(weather, weather if weather else "sunny")

    def time_dialogue_category(self) -> str:
        phase = self.town_routine_phase()
        if phase in ["wake", "work_morning"]:
            return "morning"
        if phase in ["lunch", "work_afternoon"]:
            return "midday"
        if phase == "evening":
            return "evening"
        return "late"

    def gift_reaction_dialogue_category(self, amount: int, reaction: str) -> str:
        reaction = str(reaction)
        if amount < 0 or reaction == "disliked":
            return "after_disliked_gift"
        if amount >= 4 or reaction in ["loved", "liked artisan gift", "appreciated role gift", "liked"]:
            return "after_liked_gift"
        return "after_neutral_gift"

    def last_gift_dialogue_category_for_npc(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        reaction = self.state.town_npc_last_gift_reactions.get(npc_id, {}) if isinstance(self.state.town_npc_last_gift_reactions, dict) else {}
        if not isinstance(reaction, dict) or str(reaction.get("day", "")) != self.town_npc_day_key():
            return ""
        return str(reaction.get("category", ""))

    def town_npc_reactivity_voice(self, npc: Dict[str, object]) -> str:
        role = str(npc.get("role", "Villager"))
        return {
            "Mayor": "civic",
            "Seed Seller": "farm",
            "Blacksmith": "forge",
            "Carpenter": "builder",
            "Animal Keeper": "care",
            "Librarian": "records",
            "Traveler": "travel",
            "Doctor": "medical",
            "Innkeeper": "hospitality",
            "Chef": "food",
            "Market Vendor": "market",
            "Gardener": "nature",
            "Fisher": "water",
            "Miner": "mine",
            "Kid": "child",
            "Courier": "routes",
            "Artist": "art",
            "Recluse": "wild",
            "Orchardist": "orchard",
            "Tailor": "tailor",
            "Musician": "music",
            "Beekeeper": "pollinator",
            "Botanist": "botany",
            "Mechanic": "mechanic",
            "Scholar": "records",
            "Retiree": "elder",
        }.get(role, "town")

    def town_npc_reactive_categories(self) -> set:
        return {
            "player_married",
            "spouse_at_home",
            "marriage_anniversary",
            "pregnancy_checkup_due",
            "pregnancy_early",
            "pregnancy_mid",
            "pregnancy_late",
            "child_birthday_today",
            "child_newborn",
            "child_young",
            "child_school_age",
            "child_teen",
            "family_bond_high",
            "family_meal_recent",
            "land_claim_owned",
            "land_claim_many",
            "automation_active",
            "house_comfortable",
            "combat_victory",
            "combat_level",
            "mine_depth",
            "mine_deep",
            "mine_hazard_day",
            "combat_contract_day",
            "market_day",
            "storm_warning",
            "town_work_completed",
        }

    def land_claim_dialogue_context(self) -> Dict[str, object]:
        claims = self.state.owned_wilderness_claims if isinstance(getattr(self.state, "owned_wilderness_claims", None), dict) else {}
        summary: Dict[str, object] = {
            "owned_claim_count": len(claims),
            "claim_name": "",
            "claim_type": "",
            "claim_traits": "",
            "claim_key": "",
        }
        if not claims:
            return summary
        claim_key = sorted(str(key) for key in claims.keys())[0]
        claim = claims.get(claim_key, {})
        if not isinstance(claim, dict):
            return summary
        try:
            if hasattr(self, "ensure_wilderness_claim_identity"):
                claim = self.ensure_wilderness_claim_identity(claim_key, claim)
        except Exception:
            pass
        summary.update({
            "claim_name": str(claim.get("name", f"Claim {claim_key}")),
            "claim_type": str(claim.get("farm_type") or claim.get("type") or "farm claim"),
            "claim_traits": str(claim.get("traits") or claim.get("identity") or "raw land"),
            "claim_key": claim_key,
        })
        return summary

    def child_dialogue_context(self) -> Dict[str, object]:
        children = list(getattr(self.state, "children", []) or [])
        summary: Dict[str, object] = {
            "children_count": len(children),
            "youngest_child_name": "",
            "youngest_child_stage": "",
            "child_birthday_today": False,
        }
        if not children:
            return summary
        try:
            youngest = min(children, key=lambda child: self.household_child_age_months(child))
            self.ensure_child_profile_fields(youngest)
            summary["youngest_child_name"] = str(youngest.get("name", "your child"))
            summary["youngest_child_stage"] = self.household_child_stage(youngest)
            summary["child_birthday_today"] = any(self.is_child_birthday(child) for child in children)
        except Exception:
            summary["youngest_child_name"] = str(children[0].get("name", "your child")) if isinstance(children[0], dict) else "your child"
            summary["youngest_child_stage"] = "Child"
        return summary

    def calendar_dialogue_context(self) -> Dict[str, object]:
        summary = {
            "market_day": False,
            "mine_hazard": "",
            "seasonal_contract": "",
            "storm_warning": self.town_weather_is_severe_for_routines(),
        }
        try:
            events = self.selected_calendar_events_text(self.state.month, self.state.day, self.state.year)
            event_text = " ".join(str(row).lower() for row in events)
            summary["market_day"] = "market day" in event_text
            summary["storm_warning"] = bool(summary["storm_warning"] or "storm warning" in event_text)
        except Exception:
            pass
        try:
            summary["mine_hazard"] = str(self.mine_hazard_label_for_date(self.state.month, self.state.day, self.state.year) or "")
        except Exception:
            summary["mine_hazard"] = ""
        try:
            summary["seasonal_contract"] = str(self.seasonal_combat_contract_label_for_date(self.state.month, self.state.day, self.state.year) or "")
        except Exception:
            summary["seasonal_contract"] = ""
        return summary

    def npc_reactive_format_values(self, npc: Dict[str, object], context: Dict[str, object]) -> Dict[str, object]:
        spouse_name = self.town_npc_name(str(getattr(self.state, "spouse_npc_id", ""))) if getattr(self.state, "spouse_npc_id", "") else "your spouse"
        last_meal = str(getattr(self.state, "family_last_meal", "") or "a shared meal")
        return {
            "player": str(getattr(self.state, "player_name", "you")),
            "npc": str(npc.get("name", "they")),
            "spouse": spouse_name,
            "family_rank": self.family_bond_rank() if hasattr(self, "family_bond_rank") else "steady",
            "support_mode": self.spouse_support_mode() if hasattr(self, "spouse_support_mode") else "Balanced",
            "meal": last_meal,
            "pregnancy_month": context.get("pregnancy_month", 0),
            "pregnancy_due": context.get("pregnancy_due", "the due date"),
            "child": context.get("youngest_child_name", "your child"),
            "child_stage": context.get("youngest_child_stage", "Child"),
            "children_count": context.get("children_count", 0),
            "claim_name": context.get("claim_name", "your land claim"),
            "claim_type": context.get("claim_type", "farm claim"),
            "claim_traits": context.get("claim_traits", "raw land"),
            "claim_count": context.get("owned_claim_count", 0),
            "automation_count": context.get("automation_count", 0),
            "house_rank": context.get("house_comfort_rank", "comfortable"),
            "combat_level": context.get("combat_level", 1),
            "deepest_floor": context.get("deepest_mine_floor", 1),
            "victories": context.get("mine_combat_victories", 0),
            "hazard": context.get("mine_hazard", "today's mine hazard"),
            "contract": context.get("seasonal_contract", "the seasonal mine contract"),
            "season": str(getattr(self.state, "season", "the season")).lower(),
            "weather": str(getattr(self.state, "weather", "weather")).lower(),
        }

    def dialogue_role_focus(self, npc: Dict[str, object]) -> str:
        return {
            "Mayor": "town services",
            "Seed Seller": "seed stock",
            "Blacksmith": "tools and mine gear",
            "Carpenter": "paths and building plans",
            "Animal Keeper": "feed and animal care",
            "Librarian": "records and research",
            "Traveler": "routes",
            "Doctor": "rest and supplies",
            "Innkeeper": "meals and visitors",
            "Chef": "seasonal food",
            "Market Vendor": "market stock",
            "Gardener": "public plantings",
            "Fisher": "water and weather",
            "Miner": "mine safety",
            "Kid": "shortcuts",
            "Courier": "delivery routes",
            "Artist": "color and light",
            "Recluse": "the north road",
            "Orchardist": "slow growth",
            "Tailor": "work clothes",
            "Musician": "music nights",
            "Beekeeper": "flowers and hives",
            "Botanist": "wild plants",
            "Mechanic": "machines",
            "Scholar": "town records",
            "Retiree": "benches and routines",
        }.get(str(npc.get("role", "Villager")), "daily work")

    def curated_dialogue_lines_for_category(self, npc: Dict[str, object], category: str) -> List[str]:
        category = str(category or "")
        focus = self.dialogue_role_focus(npc)
        try:
            context = self.dialogue_context_for_npc(npc)
            values = self.npc_reactive_format_values(npc, context)
        except Exception:
            values = {
                "spouse": "your spouse",
                "child": "your child",
                "claim_name": "your land claim",
                "claim_count": 0,
                "automation_count": 0,
                "deepest_floor": 1,
                "hazard": "today's mine hazard",
                "contract": "the posted mine contract",
            }

        table: Dict[str, List[str]] = {
            "spring": [
                f"Spring changes {focus} faster than the ledger can keep up.",
                "Fresh growth is useful, but it still needs planning.",
                "This is a good season to set habits before the busy months hit.",
            ],
            "summer": [
                f"Summer makes {focus} depend on shade, water, and timing.",
                "Work early if you can; the afternoon makes everything heavier.",
                "Hot weather rewards short routes and prepared supplies.",
            ],
            "fall": [
                f"Fall is good for finishing {focus} before winter slows the town down.",
                "Everything feels more deliberate once the air cools.",
                "Good season for storage, repairs, and last big outdoor pushes.",
            ],
            "winter": [
                f"Winter makes {focus} slower, but not less important.",
                "Cold days are good for planning, repairs, cooking, and town work.",
                "Watch your routes when snow or ice starts building up.",
            ],
            "sunny": [
                f"Clear weather makes {focus} easier to read.",
                "Good day to travel, harvest, or handle errands before conditions change.",
                "Bright days are useful. Do not spend all of it in menus.",
            ],
            "cloudy": [
                f"Cloud cover keeps {focus} a little easier on the eyes.",
                "Weather might turn, so finish outdoor plans while the roads are steady.",
                "Not every productive day has to be pretty.",
            ],
            "rainy": [
                "Rain helps crops, but it can make roads and wilderness trips messy.",
                f"Rain changes the rhythm of {focus}; plan for slower movement.",
                "If the fields are watered for you, use the saved time well.",
            ],
            "stormy": [
                "Storms are not worth gambling with unless you are prepared.",
                f"Bad weather puts {focus} second to getting home safely.",
                "Keep trips short and bring recovery items if you leave town.",
            ],
            "snowy": [
                "Snow slows the town down, but quiet days can still be useful.",
                f"Snow makes {focus} depend on warm rooms and short routes.",
                "Careful footing matters more than speed today.",
            ],
            "blizzard": [
                "This is shelter weather. Travel only if the reason is worth the risk.",
                f"Blizzards make {focus} wait its turn.",
                "If you must go out, keep the route short and come back early.",
            ],
            "quest_or_story_flag_related": [
                "That job you finished changed more than the checklist.",
                "People noticed the work, even if they do not all know who to thank.",
                "A completed repair makes the town feel less temporary.",
            ],
            "town_work_completed": [
                "Seeing a closed place open again changes the whole route through town.",
                "The town feels more useful when its services actually work.",
                "That repair gave people another reason to leave the house.",
            ],
            "player_married": [
                "I heard about the wedding. That changes the shape of home, doesn't it?",
                "Marriage makes ordinary routines carry more weight.",
                "I hope you and {spouse} are making the farm feel like a shared place.",
            ],
            "spouse_at_home": [
                "{spouse} moving to the farm must change the mornings.",
                "A second person in the farmhouse means the place has to work for both of you.",
                "Shared space is practical work as much as romance.",
            ],
            "marriage_anniversary": [
                "Anniversaries are easy to miss when chores get loud. Do something deliberate.",
                "Happy anniversary. Even a small gift counts if you meant it.",
                "A remembered day can hold a household together better than a speech.",
            ],
            "child_related": [
                "{child} must be changing the farmhouse schedule.",
                "Children make small routines matter more than people expect.",
                "A quiet house is useful, but a lived-in house has its own kind of luck.",
            ],
            "family_bond_high": [
                "Your household sounds steadier lately.",
                "A family that eats, rests, and plans together can handle more than it thinks.",
                "The farm feels different when home is working too.",
            ],
            "family_meal_recent": [
                "A shared meal is one of the better uses for farm food.",
                "Cooking for the household turns inventory into memory.",
                "Dinner does more work than people give it credit for.",
            ],
            "land_claim_owned": [
                "{claim_name} sounds like raw land with real potential.",
                "A purchased claim is not a finished farm. That is the point.",
                "Fast travel helps, but the land still needs your hands on it.",
            ],
            "land_claim_many": [
                "{claim_count} claims is a lot of land to remember. Keep notes.",
                "More claims mean more freedom, but also more places to leave unfinished work.",
                "Separate farms work best when each one has a clear purpose.",
            ],
            "automation_active": [
                "Automation helps most when the farm still has clear paths.",
                "{automation_count} machine setup can save time if you keep it fed and accessible.",
                "A good machine should remove chores, not make the farm harder to walk through.",
            ],
            "house_comfortable": [
                "Your farmhouse looks more like a home now.",
                "Comfort is not just decoration if it helps you recover.",
                "A better room changes how the whole day starts.",
            ],
            "combat_victory": [
                "You made it back from a fight. Recover before you chase the next one.",
                "HP and MP matter after the battle too, so sleep or use supplies before pushing on.",
                "Winning once is not a reason to enter the next room hurt.",
            ],
            "combat_level": [
                "You are getting stronger, but supplies still decide long trips.",
                "Skill does not replace health potions, mana potions, or a way home.",
                "A better fighter still needs a plan.",
            ],
            "mine_depth": [
                "Floor {deepest_floor} is deep enough that preparation starts to matter.",
                "The mine is easier to leave safely if you decide your limit before going down.",
                "Bring food or potions before treating the mine like a quick errand.",
            ],
            "mine_deep": [
                "Floor {deepest_floor} is not casual work anymore.",
                "Deep mining is party work if you have companions ready.",
                "Do not let ore tempt you past your recovery supplies.",
            ],
            "mine_hazard_day": [
                "{hazard} is on the calendar. Read it before going underground.",
                "Mine hazard days reward caution more than courage.",
                "If you go during a hazard, bring healing and leave early.",
            ],
            "combat_contract_day": [
                "{contract} is posted today. Check the mission board before you commit.",
                "Seasonal contracts pay better when you prepare for the target.",
                "A contract is optional. Gear up before making it your problem.",
            ],
            "market_day": [
                "Market Row rotates stock on market days, so check it before spending elsewhere.",
                "Limited stock goes faster when the town is busy.",
                "Market days are good for rare goods, not impulse buying everything.",
            ],
            "storm_warning": [
                "The warning is there for a reason. Finish errands early.",
                "Storm warnings make long wilderness routes a bad bargain.",
                "If tomorrow looks rough, handle travel today or prepare to stay close.",
            ],
        }
        lines = table.get(category, [])
        formatted: List[str] = []
        for line in lines:
            try:
                formatted.append(line.format(**values))
            except Exception:
                formatted.append(line)
        return formatted

    def low_quality_dialogue_text(self, text: str) -> bool:
        clean = " ".join(str(text or "").strip().split())
        if not clean:
            return True
        lowered = clean.lower()
        exact = {
            "mud everywhere.",
            "too hot today.",
            "good weather today.",
            "nice out.",
            "rain started.",
            "bad weather today.",
            "kids keep a house busy.",
            "they were asking about you.",
            "you bought land, right?",
            "how many claims do you have now?",
            "i saw something moving on your farm.",
            "your spouse moved in, right?",
            "i heard you got married.",
            "you made it back.",
            "heard about the mine.",
            "you went deeper?",
            "mine hazard today, right?",
            "prices will be weird.",
        }
        if lowered in exact:
            return True
        fragments = [
            "placeholder",
            "not implemented",
            "coming soon",
            "combat stamina",
            "battle stamina",
            "???",
            "lorem ipsum",
        ]
        return any(fragment in lowered for fragment in fragments)

    def dynamic_reactive_dialogue_templates(self) -> Dict[str, Dict[str, str]]:
        # Dialogue now comes from TOWN_NPC_CONTEXTUAL_DIALOGUE_DATA.
        # Keeping these old generated templates disabled prevents generic
        # reactive lines from slipping into otherwise hand-written conversations.
        return {}

    def dynamic_contextual_dialogue_entries_for_category(self, npc: Dict[str, object], category: str) -> List[Dict[str, str]]:
        category = str(category)
        if category not in self.town_npc_reactive_categories():
            return []
        context = self.dialogue_context_for_npc(npc)
        templates = self.dynamic_reactive_dialogue_templates().get(category, {})
        if not templates:
            return []
        voice = self.town_npc_reactivity_voice(npc)
        template = templates.get(voice) or templates.get("default", "")
        if not template:
            return []
        try:
            text = template.format(**self.npc_reactive_format_values(npc, context))
        except Exception:
            text = template
        entry = self.dialogue_entry_from_raw(str(npc.get("id", "")), category, 0, text)
        return [entry] if entry else []

    def dialogue_context_for_npc(self, npc: Dict[str, object]) -> Dict[str, object]:
        festival_name = ""
        try:
            festival = self.todays_festival()
            if festival:
                festival_name = str(festival.get("name", "Festival"))
        except Exception:
            festival_name = ""
        tier = self.relationship_tier_for_npc(npc)
        claim_context = self.land_claim_dialogue_context()
        child_context = self.child_dialogue_context()
        calendar_context = self.calendar_dialogue_context()
        pregnancy_month = self.pregnancy_month_number() if bool(self.state.pregnancy_active) else 0
        try:
            house_rank = self.house_comfort_rank()
        except Exception:
            house_rank = ""
        context = {
            "npc_id": str(npc.get("id", "")),
            "season": str(self.state.season).lower(),
            "weather": self.weather_dialogue_category(),
            "time": self.time_dialogue_category(),
            "location": str(getattr(self.state, "location", "")),
            "relationship_tier": tier,
            "relationship_category": self.relationship_dialogue_category_for_tier(tier),
            "dating": str(npc.get("id", "")) in set(self.state.dating_npc_ids or []),
            "spouse": self.state.spouse_npc_id == str(npc.get("id", "")),
            "pregnancy": bool(self.state.pregnancy_active),
            "children": bool(self.state.children),
            "npc_birthday": self.is_npc_birthday(npc),
            "player_birthday": self.is_player_birthday(),
            "festival": bool(festival_name),
            "festival_name": festival_name,
            "gift_category": self.last_gift_dialogue_category_for_npc(npc),
            "story_flag": bool(self.state.completed_town_project_ids or self.state.completed_bulletin_job_ids),
            "player_married": bool(self.state.spouse_npc_id),
            "spouse_at_home": bool(self.spouse_lives_on_farm()),
            "marriage_anniversary": self.marriage_anniversary_today(),
            "pregnancy_month": pregnancy_month,
            "pregnancy_due": self.pregnancy_due_date_label() if bool(self.state.pregnancy_active) else "",
            "pregnancy_checkup_due": bool(self.state.pregnancy_active and self.pregnancy_checkup_available()),
            "family_bond_score": self.family_bond_score() if hasattr(self, "family_bond_score") else 0,
            "family_last_meal": str(getattr(self.state, "family_last_meal", "") or ""),
            "automation_count": len(getattr(self.state, "automation_machines", {}) or {}) if isinstance(getattr(self.state, "automation_machines", {}), dict) else 0,
            "house_comfort_rank": house_rank,
            "house_comfortable": bool(house_rank in ["Cozy", "Deluxe"] or getattr(self.state, "house_upgrades", [])),
            "combat_level": int(getattr(self.state, "combat_level", 1) or 1),
            "deepest_mine_floor": int(getattr(self.state, "deepest_mine_floor", 1) or 1),
            "mine_combat_victories": int(getattr(self.state, "mine_combat_victories", 0) or 0),
            "town_work_completed": bool(
                getattr(self.state, "completed_town_project_ids", [])
                or getattr(self.state, "completed_bulletin_job_ids", [])
                or getattr(self.state, "completed_resident_request_ids", [])
            ),
        }
        context.update(claim_context)
        context.update(child_context)
        context.update(calendar_context)
        return context

    def dialogue_categories_for_npc(self, npc: Dict[str, object], immediate_category: str = "") -> List[str]:
        context = self.dialogue_context_for_npc(npc)
        categories: List[str] = []

        def add(category: str):
            if category and category not in categories:
                categories.append(category)

        add(immediate_category)
        add(str(context.get("gift_category", "")))
        if context.get("npc_birthday"):
            add("birthday")
        if context.get("player_birthday"):
            add("player_birthday")
        if context.get("festival"):
            add("festival_day")
        if context.get("spouse"):
            add("spouse")
        elif context.get("dating"):
            add("dating")
        if context.get("marriage_anniversary"):
            add("marriage_anniversary")
        if context.get("player_married") and not context.get("spouse"):
            add("player_married")
        if context.get("spouse_at_home") and not context.get("spouse"):
            add("spouse_at_home")
        if context.get("pregnancy"):
            if context.get("pregnancy_checkup_due"):
                add("pregnancy_checkup_due")
            month = int(context.get("pregnancy_month", 0) or 0)
            if month >= 7:
                add("pregnancy_late")
            elif month >= 4:
                add("pregnancy_mid")
            else:
                add("pregnancy_early")
            add("pregnancy")
        if context.get("children"):
            if context.get("child_birthday_today"):
                add("child_birthday_today")
            stage = str(context.get("youngest_child_stage", ""))
            if stage in ["Newborn", "Infant"]:
                add("child_newborn")
            elif stage in ["Toddler", "Young Child"]:
                add("child_young")
            elif stage in ["Child"]:
                add("child_school_age")
            elif stage in ["Teen", "Young Adult"]:
                add("child_teen")
            add("child_related")
        if int(context.get("family_bond_score", 0) or 0) >= 90:
            add("family_bond_high")
        if context.get("family_last_meal"):
            add("family_meal_recent")
        if int(context.get("owned_claim_count", 0) or 0) >= 1:
            add("land_claim_many" if int(context.get("owned_claim_count", 0) or 0) >= 2 else "land_claim_owned")
        if int(context.get("automation_count", 0) or 0) >= 1:
            add("automation_active")
        if context.get("house_comfortable"):
            add("house_comfortable")
        if int(context.get("mine_combat_victories", 0) or 0) >= 1:
            add("combat_victory")
        if int(context.get("combat_level", 1) or 1) >= 3:
            add("combat_level")
        deepest_floor = int(context.get("deepest_mine_floor", 1) or 1)
        if deepest_floor >= 10:
            add("mine_deep")
        elif deepest_floor >= 3:
            add("mine_depth")
        combat_started = bool(
            int(context.get("deepest_mine_floor", 1) or 1) >= 3
            or int(context.get("mine_combat_victories", 0) or 0) >= 1
            or int(context.get("combat_level", 1) or 1) >= 2
        )
        if context.get("mine_hazard") and combat_started:
            add("mine_hazard_day")
        if context.get("seasonal_contract") and combat_started:
            add("combat_contract_day")
        if context.get("market_day"):
            add("market_day")
        if context.get("storm_warning"):
            add("storm_warning")
        if context.get("story_flag"):
            add("quest_or_story_flag_related")
        if context.get("town_work_completed"):
            add("town_work_completed")
        add(str(context.get("relationship_category", "")))
        add(str(context.get("weather", "")))
        add(str(context.get("season", "")))
        add(str(context.get("time", "")))
        add("daily_generic")
        add("legacy_talk")
        return categories

    def stable_dialogue_line_id(self, npc_id: str, category: str, text: str) -> str:
        clean = []
        for ch in str(text).lower():
            clean.append(ch if ch.isalnum() else "_")
        slug = "_".join("".join(clean).split("_"))[:40] or "line"
        checksum = sum((index + 1) * ord(ch) for index, ch in enumerate(str(text))) % 100000
        return f"{npc_id}:{category}:{checksum}:{slug}"

    def dialogue_entry_from_raw(self, npc_id: str, category: str, index: int, raw: object) -> Optional[Dict[str, str]]:
        try:
            if isinstance(raw, dict):
                text = str(raw.get("text", "")).strip()
                line_id = str(raw.get("id", "")).strip()
            else:
                text = str(raw).strip()
                line_id = ""
            if not text:
                return None
            if not line_id:
                line_id = self.stable_dialogue_line_id(npc_id, category, text)
            return {"id": line_id, "text": text, "category": category}
        except Exception:
            return None

    def contextual_dialogue_entries_for_category(self, npc: Dict[str, object], category: str) -> List[Dict[str, str]]:
        npc_id = str(npc.get("id", ""))
        data = TOWN_NPC_CONTEXTUAL_DIALOGUE_DATA.get(npc_id, {})
        if not isinstance(data, dict):
            data = {}
        curated_pool = self.curated_dialogue_lines_for_category(npc, category)
        raw_pool = curated_pool if curated_pool else data.get(category, [])
        if category == "legacy_talk":
            legacy_data = self.town_npc_dialogue_data(npc)
            raw_pool = legacy_data.get("talk", [])
        if isinstance(raw_pool, (str, dict)):
            raw_pool = [raw_pool]
        if not isinstance(raw_pool, list):
            return []
        entries: List[Dict[str, str]] = []
        for index, raw in enumerate(raw_pool):
            entry = self.dialogue_entry_from_raw(npc_id, category, index, raw)
            if entry and not self.low_quality_dialogue_text(str(entry.get("text", ""))):
                entries.append(entry)
        dynamic_entries = self.dynamic_contextual_dialogue_entries_for_category(npc, category)
        for entry in dynamic_entries:
            if entry and entry.get("id") not in {existing.get("id") for existing in entries}:
                entries.append(entry)
        return entries

    def recent_dialogue_ids_for_npc(self, npc_id: str) -> List[str]:
        if not isinstance(self.state.town_npc_recent_dialogue_ids, dict):
            self.state.town_npc_recent_dialogue_ids = {}
        recent = self.state.town_npc_recent_dialogue_ids.get(str(npc_id), [])
        if not isinstance(recent, list):
            recent = []
        recent = [str(line_id) for line_id in recent[-8:] if line_id is not None]
        self.state.town_npc_recent_dialogue_ids[str(npc_id)] = recent
        return recent

    def remember_npc_dialogue_line(self, npc_id: str, line_id: str):
        npc_id = str(npc_id)
        line_id = str(line_id or "")
        if not line_id:
            return
        recent = [existing for existing in self.recent_dialogue_ids_for_npc(npc_id) if existing != line_id]
        recent.append(line_id)
        self.state.town_npc_recent_dialogue_ids[npc_id] = recent[-8:]

    def choose_npc_dialogue(self, npc: Dict[str, object], immediate_category: str = "", remember: bool = True) -> Dict[str, str]:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        try:
            categories = self.dialogue_categories_for_npc(npc, immediate_category)
            recent = set(self.recent_dialogue_ids_for_npc(npc_id))
            first_any: Optional[Dict[str, str]] = None
            for category in categories:
                entries = self.contextual_dialogue_entries_for_category(npc, category)
                if not entries:
                    continue
                if first_any is None:
                    first_any = entries[0]
                fresh = [entry for entry in entries if entry["id"] not in recent]
                if not fresh:
                    continue
                candidates = fresh
                seed_text = f"{self.town_npc_day_key()}:{npc_id}:{category}:{self.state.hour}:{self.state.minute}:{len(recent)}"
                index = sum(ord(ch) for ch in seed_text) % len(candidates)
                chosen = candidates[index]
                if remember:
                    self.remember_npc_dialogue_line(npc_id, chosen["id"])
                return chosen
            if first_any:
                if remember:
                    self.remember_npc_dialogue_line(npc_id, first_any["id"])
                return first_any
        except Exception as exc:
            append_debug_log(f"Dialogue selection fallback for {npc_id}: {type(exc).__name__}: {exc}")

        fallback = str(self.town_npc_daily_pick(npc, "fallback_talk", [
            "Hey.",
            "Need something?",
            "I am busy right now.",
            "Come back later.",
        ]) or "Hey.")
        line_id = self.stable_dialogue_line_id(npc_id, "fallback", fallback)
        if remember:
            self.remember_npc_dialogue_line(npc_id, line_id)
        return {"id": line_id, "text": fallback, "category": "fallback"}

    def eligible_relationship_milestone_event(self, npc: Dict[str, object]) -> Tuple[str, Dict[str, object]]:
        npc_id = str(npc.get("id", ""))
        events = RELATIONSHIP_MILESTONE_EVENTS.get(npc_id, {})
        if not isinstance(events, dict):
            return "", {}
        points = self.town_npc_relationship(npc_id)
        talks = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        for milestone in ["close_friend", "trusted"]:
            event = events.get(milestone, {})
            if not isinstance(event, dict):
                continue
            if self.has_relationship_milestone(npc_id, milestone):
                continue
            if points < int(event.get("requires_points", 0)):
                continue
            if talks < int(event.get("requires_talks", 0)):
                continue
            return milestone, event
        return "", {}

    def try_relationship_milestone_event(self, npc: Dict[str, object]) -> List[str]:
        npc_id = str(npc.get("id", ""))
        try:
            milestone, event = self.eligible_relationship_milestone_event(npc)
            if not milestone or not event:
                return []
            self.set_relationship_milestone(npc_id, milestone)
            bonus = int(event.get("bonus", 0) or 0)
            actual_bonus = self.adjust_town_npc_relationship(npc_id, bonus) if bonus else 0
            title = str(event.get("title", "Relationship Moment"))
            lines = [title, ""]
            raw_lines = event.get("lines", [])
            if isinstance(raw_lines, list):
                lines.extend(str(line) for line in raw_lines if str(line).strip())
            if actual_bonus > 0:
                lines.extend(["", f"Relationship +{actual_bonus}."])
            if milestone == "close_friend":
                lines.append("Close Friend tier can now be reached.")
            elif milestone == "trusted":
                lines.append("Trusted and deeper tiers can now be reached.")
            return lines
        except Exception as exc:
            append_debug_log(f"Relationship milestone fallback for {npc_id}: {type(exc).__name__}: {exc}")
            return []

    def scene_catalog(self) -> Dict[str, Dict[str, object]]:
        scenes: Dict[str, Dict[str, object]] = {}
        for npc_id, milestone_events in RELATIONSHIP_MILESTONE_EVENTS.items():
            if not isinstance(milestone_events, dict):
                continue
            npc_name = self.town_npc_name(npc_id)
            for milestone, event in milestone_events.items():
                if not isinstance(event, dict):
                    continue
                scene_id = f"npc_milestone:{npc_id}:{milestone}"
                required_milestones = ["close_friend"] if milestone == "trusted" else []
                raw_lines = event.get("lines", [])
                narrator_steps = [
                    {"type": "narration", "text": str(line)}
                    for line in raw_lines
                    if str(line).strip()
                ]
                quote = RELATIONSHIP_MILESTONE_SCENE_QUOTES.get((npc_id, str(milestone)), "")
                steps: List[Dict[str, object]] = narrator_steps
                if quote:
                    steps.append({"type": "dialogue", "speaker": npc_name, "text": quote})
                theme_flag = RELATIONSHIP_MILESTONE_THEME_FLAGS.get((npc_id, str(milestone)), "")
                steps.append(
                    {"type": "set_npc_milestone", "npc_id": npc_id, "milestone": str(milestone)},
                )
                if theme_flag:
                    steps.extend([
                        {"type": "set_npc_milestone", "npc_id": npc_id, "milestone": theme_flag},
                        {"type": "set_flag", "flag": f"npc_milestone:{npc_id}:{theme_flag}"},
                    ])
                steps.extend([
                    {"type": "relationship", "npc_id": npc_id, "amount": int(event.get("bonus", 0) or 0)},
                    {"type": "set_flag", "flag": f"scene_flag:{scene_id}"},
                    {"type": "message", "text": f"{npc_name}'s relationship milestone advanced."},
                ])
                scenes[scene_id] = {
                    "id": scene_id,
                    "title": f"{npc_name}: {event.get('title', 'Relationship Moment')}",
                    "completion_flag": scene_id,
                    "repeatable": False,
                    "priority": 120 if milestone == "trusted" else 110,
                    "trigger": {
                        "npc_id": npc_id,
                        "min_relationship": int(event.get("requires_points", 0) or 0),
                        "min_talks": int(event.get("requires_talks", 0) or 0),
                        "required_milestones": required_milestones,
                        "blocked_milestones": [str(milestone)],
                    },
                    "steps": steps,
                }
        scenes.update(self.life_event_scene_catalog())
        return scenes

    def life_event_scene_catalog(self) -> Dict[str, Dict[str, object]]:
        scenes: Dict[str, Dict[str, object]] = {}

        def add_scene(
            key: str,
            title: str,
            trigger: Dict[str, object],
            steps: List[Dict[str, object]],
            priority: int = 125,
        ):
            scene_id = f"life:{key}"
            final_steps = list(steps)
            final_steps.extend([
                {"type": "set_flag", "flag": f"scene_flag:{scene_id}"},
                {"type": "message", "text": f"{title} recorded."},
            ])
            scenes[scene_id] = {
                "id": scene_id,
                "title": title,
                "completion_flag": scene_id,
                "repeatable": False,
                "priority": priority,
                "trigger": trigger,
                "steps": final_steps,
            }

        spouse_id = str(getattr(self.state, "spouse_npc_id", "") or "")
        spouse_name = self.town_npc_name(spouse_id) if spouse_id else "your spouse"

        if spouse_id:
            add_scene(
                "spouse_move_in",
                "A Home Shared",
                {"npc_id": spouse_id, "spouse": True, "spouse_moved_to_farm": True},
                [
                    {
                        "type": "narration",
                        "text": "The farmhouse feels different once another daily route begins and ends at the same door.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "I moved my things in, but I do not want this to feel like I arrived finished. We can decide what home becomes from here.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 5},
                ],
                priority=150,
            )
            add_scene(
                "first_family_meal",
                "The First Shared Table",
                {"npc_id": spouse_id, "spouse": True, "spouse_moved_to_farm": True, "family_last_meal": True},
                [
                    {
                        "type": "narration",
                        "text": "A meal at home turns the room from useful shelter into a place with memory.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "This is small, but it matters. Food, a table, and a minute where nothing needs fixing immediately.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 4},
                ],
                priority=145,
            )
            add_scene(
                "expecting_household",
                "Planning Room For More",
                {"npc_id": spouse_id, "spouse": True, "pregnancy": True},
                [
                    {
                        "type": "narration",
                        "text": "The farmhouse ledger gains a new kind of entry: space, time, care, and all the ordinary logistics of becoming a larger household.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "Nine months is a long promise. I want us to use it well, not rush through it because the calendar says we can.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 5},
                ],
                priority=148,
            )
            add_scene(
                "first_child_home",
                "A New Voice At Home",
                {"npc_id": spouse_id, "spouse": True, "children": True},
                [
                    {
                        "type": "narration",
                        "text": "The farmhouse sounds different now: softer footsteps, new schedules, and the small gravity of a child living under the same roof.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "We are going to learn this one day at a time. That is probably the only honest way to do it.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 6},
                ],
                priority=152,
            )
            add_scene(
                "rooted_household",
                "A Rooted Household",
                {"npc_id": spouse_id, "spouse": True, "min_family_bond": 90},
                [
                    {
                        "type": "narration",
                        "text": "After enough shared routines, home stops being a project and starts becoming something that catches everyone when the day is heavy.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "I can feel it now. The house is not just where we recover from work. It is part of why the work feels worth doing.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 5},
                ],
                priority=135,
            )

        add_scene(
            "first_land_claim",
            "The First Deed",
            {"npc_id": "eli_carpenter", "min_owned_claims": 1},
            [
                {
                    "type": "dialogue",
                    "speaker": "Eli",
                    "text": "A raw claim is not a farm yet. Good. That means it is still yours to shape instead of something you are forced to inherit.",
                },
                {
                    "type": "narration",
                    "text": "Eli sketches a rough access line and marks where a workshop crew could deliver materials without taking over the land.",
                },
                {"type": "relationship", "npc_id": "eli_carpenter", "amount": 4},
            ],
            priority=132,
        )
        add_scene(
            "first_mine_victory",
            "After The First Fight",
            {"npc_id": "brom_smith", "min_mine_combat_victories": 1},
            [
                {
                    "type": "dialogue",
                    "speaker": "Brom",
                    "text": "You came back breathing and with your head still on. That is the first useful combat lesson. The second is learning why it worked.",
                },
                {
                    "type": "narration",
                    "text": "Brom checks your gear for cracked edges and notes which repairs should be routine after mine fights.",
                },
                {"type": "relationship", "npc_id": "brom_smith", "amount": 4},
            ],
            priority=131,
        )
        add_scene(
            "first_automation_machine",
            "A Machine Joins The Farm",
            {"npc_id": "jules_mechanic", "min_automation_machines": 1},
            [
                {
                    "type": "dialogue",
                    "speaker": "Jules",
                    "text": "That is the good kind of machine: boring when it works, obvious when it needs attention, and never mysterious on purpose.",
                },
                {
                    "type": "narration",
                    "text": "Jules draws a maintenance mark in the corner of the plan, then circles the part that should stay reachable.",
                },
                {"type": "relationship", "npc_id": "jules_mechanic", "amount": 4},
            ],
            priority=130,
        )
        add_scene(
            "deep_mine_report",
            "The Mine Gets Serious",
            {"npc_id": "garrick_miner", "min_deepest_mine_floor": 5},
            [
                {
                    "type": "dialogue",
                    "speaker": "Garrick",
                    "text": "Past the first few floors, the mine stops testing whether you are brave and starts testing whether you pay attention.",
                },
                {
                    "type": "narration",
                    "text": "Garrick marks a few danger signs in your route notes: fresh cracks, echo changes, and floors that sound hollow under a boot.",
                },
                {"type": "relationship", "npc_id": "garrick_miner", "amount": 4},
            ],
            priority=129,
        )
        return scenes

    def scene_by_id(self, scene_id: str) -> Dict[str, object]:
        scene = self.scene_catalog().get(str(scene_id), {})
        return scene if isinstance(scene, dict) else {}

    def scene_is_completed(self, scene_or_id: object) -> bool:
        scene = self.scene_by_id(str(scene_or_id)) if isinstance(scene_or_id, str) else scene_or_id
        if not isinstance(scene, dict) or not scene:
            return False
        if bool(scene.get("repeatable", False)):
            return False
        scene_id = str(scene.get("id", ""))
        completion_flag = str(scene.get("completion_flag", scene_id))
        completed = set(str(x) for x in (self.state.completed_scene_ids or []))
        return scene_id in completed or completion_flag in completed

    def mark_scene_seen(self, scene_id: str):
        scene_id = str(scene_id)
        if scene_id and scene_id not in set(self.state.seen_scene_ids or []):
            self.state.seen_scene_ids.append(scene_id)

    def mark_scene_completed(self, scene: Dict[str, object]):
        scene_id = str(scene.get("id", ""))
        completion_flag = str(scene.get("completion_flag", scene_id))
        for value in [scene_id, completion_flag]:
            if value and value not in set(self.state.completed_scene_ids or []):
                self.state.completed_scene_ids.append(value)

    def scene_conditions_met(self, scene: Dict[str, object], context: Optional[Dict[str, object]] = None) -> bool:
        context = context or {}
        try:
            if not isinstance(scene, dict) or not scene.get("id"):
                return False
            if self.scene_is_completed(scene):
                return False
            trigger = scene.get("trigger", {}) or {}
            if not isinstance(trigger, dict):
                return False
            completed_scenes = set(str(x) for x in (self.state.completed_scene_ids or []))
            scene_flags = set(str(x) for x in (self.state.scene_flags or [])) | completed_scenes
            completed_projects = set(str(x) for x in (self.state.completed_town_project_ids or []))

            npc_id = str(trigger.get("npc_id", ""))
            context_npc_id = str(context.get("npc_id", ""))
            if npc_id and context_npc_id and npc_id != context_npc_id:
                return False

            locations = trigger.get("locations", trigger.get("location", None))
            if isinstance(locations, str):
                locations = [locations]
            if isinstance(locations, list) and locations and self.state.location not in [str(location) for location in locations]:
                return False

            seasons = trigger.get("seasons", trigger.get("season", None))
            if isinstance(seasons, str):
                seasons = [seasons]
            if isinstance(seasons, list) and seasons and self.state.season not in [str(season) for season in seasons]:
                return False

            weather = trigger.get("weather", None)
            if isinstance(weather, str):
                weather = [weather]
            if isinstance(weather, list) and weather and str(self.state.weather) not in [str(value) for value in weather]:
                return False

            times = trigger.get("time", trigger.get("times", None))
            if isinstance(times, str):
                times = [times]
            if isinstance(times, list) and times and self.time_dialogue_category() not in [str(value) for value in times]:
                return False

            months = trigger.get("months", trigger.get("month", None))
            if months is not None:
                if not isinstance(months, (list, tuple, set)):
                    months = [months]
                if int(self.state.month) not in [int(value) for value in months]:
                    return False
            days = trigger.get("days", trigger.get("day", None))
            if days is not None:
                if not isinstance(days, (list, tuple, set)):
                    days = [days]
                if int(self.state.day) not in [int(value) for value in days]:
                    return False
            dates = trigger.get("dates", trigger.get("date", None))
            if dates is not None:
                if not isinstance(dates, (list, tuple, set)):
                    dates = [dates]
                today_values = {
                    f"{int(self.state.month)}-{int(self.state.day)}",
                    f"{int(self.state.month)}/{int(self.state.day)}",
                    f"{int(self.state.year)}-{int(self.state.month)}-{int(self.state.day)}",
                    format_date(int(self.state.month), int(self.state.day), int(self.state.year)),
                }
                if not any(str(value) in today_values for value in dates):
                    return False

            if "festival" in trigger and bool(trigger.get("festival")) != bool(self.todays_festival_id()):
                return False
            festival_ids = trigger.get("festival_ids", trigger.get("festival_id", None))
            if festival_ids is not None:
                if not isinstance(festival_ids, (list, tuple, set)):
                    festival_ids = [festival_ids]
                if str(self.todays_festival_id() or "") not in [str(value) for value in festival_ids]:
                    return False

            if npc_id:
                npc = context.get("npc")
                if not isinstance(npc, dict):
                    npc = next((n for n in self.state.town_npcs if str(n.get("id", "")) == npc_id), {})
                if int(trigger.get("min_relationship", -999999)) > self.town_npc_relationship(npc_id):
                    return False
                if int(trigger.get("min_talks", 0)) > int(self.state.town_npc_dialogue_counts.get(npc_id, 0)):
                    return False
                tier = str(trigger.get("relationship_tier", ""))
                if tier and isinstance(npc, dict) and self.relationship_tier_for_npc(npc) != tier:
                    return False
                for milestone in trigger.get("required_milestones", []) or []:
                    if not self.has_relationship_milestone(npc_id, str(milestone)):
                        return False
                for milestone in trigger.get("blocked_milestones", []) or []:
                    if self.has_relationship_milestone(npc_id, str(milestone)):
                        return False
                if "dating" in trigger and bool(trigger.get("dating")) != (npc_id in set(self.state.dating_npc_ids or [])):
                    return False
                if "spouse" in trigger and bool(trigger.get("spouse")) != (self.state.spouse_npc_id == npc_id):
                    return False

            for flag in trigger.get("required_flags", []) or []:
                if str(flag) not in scene_flags:
                    return False
            for flag in trigger.get("blocked_flags", []) or []:
                if str(flag) in scene_flags:
                    return False

            for scene_id in trigger.get("required_completed_scenes", trigger.get("completed_scenes", [])) or []:
                if str(scene_id) not in completed_scenes:
                    return False
            for scene_id in trigger.get("blocked_completed_scenes", trigger.get("unfinished_scenes", [])) or []:
                if str(scene_id) in completed_scenes:
                    return False

            for project_id in trigger.get("required_town_projects", trigger.get("completed_town_projects", [])) or []:
                if str(project_id) not in completed_projects:
                    return False
            for project_id in trigger.get("blocked_town_projects", trigger.get("unfinished_town_projects", [])) or []:
                if str(project_id) in completed_projects:
                    return False

            if "pregnancy" in trigger and bool(trigger.get("pregnancy")) != bool(self.state.pregnancy_active):
                return False
            if "children" in trigger and bool(trigger.get("children")) != bool(self.state.children):
                return False
            if "spouse_moved_to_farm" in trigger and bool(trigger.get("spouse_moved_to_farm")) != bool(getattr(self.state, "spouse_moved_to_farm", False)):
                return False
            if int(trigger.get("min_children", 0) or 0) > len(getattr(self.state, "children", []) or []):
                return False
            if int(trigger.get("min_family_bond", 0) or 0) > self.family_bond_score():
                return False
            claims = getattr(self.state, "owned_wilderness_claims", {}) or {}
            claim_count = len(claims) if isinstance(claims, dict) else 0
            if int(trigger.get("min_owned_claims", 0) or 0) > claim_count:
                return False
            automation = getattr(self.state, "automation_machines", {}) or {}
            automation_count = len(automation) if isinstance(automation, dict) else 0
            if int(trigger.get("min_automation_machines", 0) or 0) > automation_count:
                return False
            if int(trigger.get("min_mine_combat_victories", 0) or 0) > int(getattr(self.state, "mine_combat_victories", 0) or 0):
                return False
            if int(trigger.get("min_deepest_mine_floor", 0) or 0) > int(getattr(self.state, "deepest_mine_floor", 1) or 1):
                return False
            if trigger.get("family_last_meal") and not str(getattr(self.state, "family_last_meal", "") or ""):
                return False

            inventory = trigger.get("inventory_contains", {}) or {}
            if isinstance(inventory, dict):
                for item, qty in inventory.items():
                    if int(self.state.inventory.get(str(item), 0)) < int(qty):
                        return False
            elif isinstance(inventory, str):
                if int(self.state.inventory.get(inventory, 0)) <= 0:
                    return False
            elif isinstance(inventory, (list, tuple, set)):
                for item in inventory:
                    if int(self.state.inventory.get(str(item), 0)) <= 0:
                        return False
            return True
        except Exception as exc:
            append_debug_log(f"Scene condition fallback: {type(exc).__name__}: {exc}")
            return False

    def eligible_scenes_for_context(self, context: Optional[Dict[str, object]] = None) -> List[Dict[str, object]]:
        context = context or {}
        scenes: List[Dict[str, object]] = []
        for scene in self.scene_catalog().values():
            if self.scene_conditions_met(scene, context):
                scenes.append(scene)
        scenes.sort(key=lambda scene: int(scene.get("priority", 0)), reverse=True)
        return scenes

    def validate_active_scene_state(self):
        if not self.state.active_scene_id:
            self.state.active_scene_step_index = 0
            return
        scene = self.scene_by_id(self.state.active_scene_id)
        steps = scene.get("steps", []) if isinstance(scene, dict) else []
        if not scene or not isinstance(steps, list) or self.state.active_scene_step_index >= len(steps):
            append_debug_log(f"Cancelled invalid active scene: {self.state.active_scene_id}")
            self.state.active_scene_id = ""
            self.state.active_scene_step_index = 0

    def start_scene(self, scene_or_id: object) -> bool:
        scene = self.scene_by_id(str(scene_or_id)) if isinstance(scene_or_id, str) else scene_or_id
        if not isinstance(scene, dict) or not scene.get("id"):
            append_debug_log(f"Invalid scene start request: {scene_or_id}")
            return False
        if self.scene_is_completed(scene):
            append_debug_log(f"Scene already completed: {scene.get('id')}")
            return False
        steps = scene.get("steps", [])
        if not isinstance(steps, list) or not steps:
            append_debug_log(f"Scene has no valid steps: {scene.get('id')}")
            return False
        self.state.active_scene_id = str(scene.get("id", ""))
        self.state.active_scene_step_index = 0
        self.mark_scene_seen(self.state.active_scene_id)
        append_debug_log(f"Starting scene: {self.state.active_scene_id}")
        return True

    def current_scene(self) -> Dict[str, object]:
        self.validate_active_scene_state()
        return self.scene_by_id(self.state.active_scene_id) if self.state.active_scene_id else {}

    def current_scene_step(self) -> Dict[str, object]:
        scene = self.current_scene()
        steps = scene.get("steps", []) if scene else []
        try:
            step = steps[int(self.state.active_scene_step_index)]
            return step if isinstance(step, dict) else {}
        except Exception:
            return {}

    def step_is_visible_scene_text(self, step: Dict[str, object]) -> bool:
        return str(step.get("type", "")) in ["dialogue", "narration", "text"]

    def advance_scene_to_visible_step(self) -> bool:
        while self.state.active_scene_id:
            step = self.current_scene_step()
            if step and self.step_is_visible_scene_text(step):
                return True
            if not self.advance_scene() and not self.state.active_scene_id:
                return False
        return False

    def apply_scene_step_effect(self, scene: Dict[str, object], step: Dict[str, object]):
        step_type = str(step.get("type", ""))
        try:
            if step_type == "relationship":
                self.adjust_town_npc_relationship(str(step.get("npc_id", "")), int(step.get("amount", 0)))
            elif step_type == "give_item":
                item = str(step.get("item", ""))
                qty = int(step.get("qty", 1))
                if item and qty > 0:
                    self.state.inventory[item] = int(self.state.inventory.get(item, 0)) + qty
            elif step_type == "remove_item":
                item = str(step.get("item", ""))
                qty = int(step.get("qty", 1))
                if item and qty > 0:
                    self.state.inventory[item] = max(0, int(self.state.inventory.get(item, 0)) - qty)
            elif step_type == "set_flag":
                flag = str(step.get("flag", ""))
                if flag and flag not in set(self.state.scene_flags or []):
                    self.state.scene_flags.append(flag)
            elif step_type == "set_npc_milestone":
                npc_id = str(step.get("npc_id", ""))
                milestone = str(step.get("milestone", ""))
                if npc_id and milestone:
                    self.set_relationship_milestone(npc_id, milestone)
            elif step_type == "unlock_recipe":
                recipe_id = str(step.get("recipe_id", ""))
                if recipe_id and recipe_id not in set(self.state.learned_recipe_ids or []):
                    self.state.learned_recipe_ids.append(recipe_id)
            elif step_type == "message":
                self.state.message = str(step.get("text", self.state.message))
            elif step_type == "position":
                location = str(step.get("location", ""))
                if location in VALID_GAME_LOCATIONS:
                    self.state.location = location
                if "x" in step and "y" in step:
                    self.state.player_x = int(step.get("x", self.state.player_x))
                    self.state.player_y = int(step.get("y", self.state.player_y))
        except Exception as exc:
            append_debug_log(f"Scene step effect skipped for {scene.get('id', '')}: {type(exc).__name__}: {exc}")

    def complete_scene(self, scene: Dict[str, object]):
        self.mark_scene_completed(scene)
        append_debug_log(f"Completed scene: {scene.get('id', '')}")
        self.state.active_scene_id = ""
        self.state.active_scene_step_index = 0

    def advance_scene(self) -> bool:
        scene = self.current_scene()
        if not scene:
            return False
        steps = scene.get("steps", [])
        if not isinstance(steps, list):
            self.complete_scene(scene)
            return False
        while self.state.active_scene_step_index < len(steps):
            step = steps[self.state.active_scene_step_index]
            if isinstance(step, dict):
                self.apply_scene_step_effect(scene, step)
            self.state.active_scene_step_index += 1
            if self.state.active_scene_step_index >= len(steps):
                self.complete_scene(scene)
                return False
            next_step = steps[self.state.active_scene_step_index]
            if isinstance(next_step, dict) and self.step_is_visible_scene_text(next_step):
                return True
        self.complete_scene(scene)
        return False

    def draw_scene(self):
        if not self.advance_scene_to_visible_step():
            return
        scene = self.current_scene()
        step = self.current_scene_step()
        self.invalidate_draw_cache()
        clear_screen()
        title = str(scene.get("title", "Scene"))
        step_type = str(step.get("type", "narration"))
        speaker = str(step.get("speaker", "Narrator" if step_type != "dialogue" else ""))
        text = str(step.get("text", ""))
        width = 68
        self.centered_print("+" + "-" * width + "+", width + 2)
        self.centered_print("|" + pad_to(title.center(width), width) + "|", width + 2)
        self.centered_print("+" + "-" * width + "+", width + 2)
        if speaker:
            self.centered_print("|" + pad_to(speaker, width) + "|", width + 2)
            self.centered_print("+" + "-" * width + "+", width + 2)
        for line in textwrap.wrap(text, width=width - 4) or [""]:
            self.centered_print("|" + pad_to("  " + line, width) + "|", width + 2)
        self.centered_print("+" + "-" * width + "+", width + 2)
        self.centered_print("|" + pad_to("Enter/Space/E/Z continue", width) + "|", width + 2)
        self.centered_print("+" + "-" * width + "+", width + 2)

    def handle_scene_key(self, key: str) -> bool:
        key = normalize_key(key)
        if key in MENU_CONFIRM_KEYS:
            return self.advance_scene()
        return True

    def play_scene(self, scene_or_id: object) -> bool:
        if not self.start_scene(scene_or_id):
            return False
        while self.state.active_scene_id:
            if not self.advance_scene_to_visible_step():
                continue
            self.draw_scene()
            self.handle_scene_key(read_key())
        self.invalidate_draw_cache()
        return True

    def maybe_play_scene_for_context(self, context: Dict[str, object]) -> bool:
        try:
            scenes = self.eligible_scenes_for_context(context)
            if not scenes:
                return False
            return self.play_scene(scenes[0])
        except Exception as exc:
            append_debug_log(f"Scene context fallback: {type(exc).__name__}: {exc}")
            return False

    def town_npc_dialogue_lines(self, npc: Dict[str, object], first_talk_today: Optional[bool] = None) -> List[str]:
        conversation = self.town_npc_role_dialogue_lines(npc)
        primary_line = conversation[0] if conversation else "Good to see you."
        return [str(primary_line)]

    def town_npc_menu(self, npc: Dict[str, object]):
        if self.is_household_child_npc(npc):
            self.household_child_menu(npc)
            return
        if (
            hasattr(self, "is_dynasty_elder_npc")
            and self.is_dynasty_elder_npc(npc)
        ):
            self.dynasty_elder_menu(npc)
            return
        if (
            hasattr(self, "is_dynasty_kin_npc")
            and self.is_dynasty_kin_npc(npc)
        ):
            self.dynasty_kin_menu(npc)
            return
        if (
            self.is_procedural_npc(npc)
            and str(npc.get("id", ""))
            == str(getattr(self.state, "spouse_npc_id", ""))
            and hasattr(self, "procedural_household_spouse_menu")
        ):
            self.procedural_household_spouse_menu(npc)
            return
        while True:
            npc_id = str(npc.get("id", npc.get("name", "npc")))
            today = self.town_npc_day_key()
            talked_today = self.state.town_npc_last_talk_day.get(npc_id) == today
            gifted_today = self.state.town_npc_last_gift_day.get(npc_id) == today
            errand = self.errand_for_npc(npc)
            errand_hint = "done" if errand.get("completed") else ("ready" if self.can_complete_errand(errand) else f"needs {errand.get('item')}")
            court_ok, _court_reason = self.can_court_town_npc(npc) if self.is_marriageable_npc(npc) else (False, "not romanceable")
            proposal_ok, proposal_reason = self.can_propose_to_town_npc(npc) if self.is_marriageable_npc(npc) else (False, "not romanceable")
            court_menu_hint = "Available" if court_ok else "Build friendship first"
            proposal_menu_hint = "Ready" if proposal_ok else proposal_reason
            items = [
                MenuItem(label="Talk", value="talk", enabled=True),
                MenuItem(label="Give gift", value="gift", enabled=not gifted_today, hint="Choose a carried item" if not gifted_today else "Already gave a gift today"),
                MenuItem(label="Ask rumor", value="rumor", enabled=True),
                MenuItem(label="Errand", value="errand", enabled=True, hint=errand_hint),
            ]
            if self.is_marriageable_npc(npc):
                items.append(
                    MenuItem(
                        label="Courtship",
                        value="courtship",
                        enabled=True,
                        hint=court_menu_hint,
                    )
                )
                if str(getattr(self.state, "engaged_npc_id", "")) == npc_id:
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
                            hint=proposal_menu_hint,
                        )
                    )
            if self.state.spouse_npc_id == npc_id:
                move_ok, move_reason = self.can_invite_spouse_to_farm(npc)
                family_ok, family_reason = self.can_start_pregnancy_with_spouse(npc)
                scene_key, scene_title = self.available_marriage_scene(npc)
                items.append(MenuItem(
                    label="Move to farm",
                    value="move_spouse",
                    enabled=move_ok,
                    hint=move_reason,
                ))
                items.append(MenuItem(
                    label="Marriage event",
                    value="marriage_scene",
                    enabled=bool(scene_key),
                    hint=scene_title if scene_title else "none ready",
                ))
                items.append(MenuItem(label="Family memories", value="family_memories", enabled=True, hint=f"{len(self.state.family_event_log or [])} logged"))
                items.append(MenuItem(
                    label="Plan family",
                    value="plan_family",
                    enabled=True,
                    hint=family_reason,
                ))
                if self.state.pregnancy_active:
                    items.append(MenuItem(
                        label="Pregnancy check-in",
                        value="pregnancy_checkup",
                        enabled=True,
                        hint="ready" if self.pregnancy_checkup_available() else "view",
                    ))
                family_hint = "pregnancy active" if self.state.pregnancy_active else f"{len(self.state.children)} child(ren)"
                items.append(MenuItem(label="Family status", value="family_status", enabled=True, hint=family_hint))
                meal_ok, meal_reason = self.family_meal_available()
                items.append(MenuItem(
                    label="Family meal",
                    value="family_meal",
                    enabled=True,
                    hint="ready" if meal_ok else meal_reason,
                ))
                items.append(MenuItem(
                    label="Spouse support",
                    value="spouse_support",
                    enabled=self.state.spouse_moved_to_farm,
                    hint=self.spouse_support_mode(),
                ))
                items.append(MenuItem(
                    label="Household help",
                    value="household_help",
                    enabled=True,
                    hint="enabled" if self.state.family_help_enabled else "disabled",
                ))
            items.extend([
                MenuItem(label="Profile", value="profile", enabled=True),
                MenuItem(label="Status", value="status", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(str(npc.get("name", "Villager")), items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message(f"Stopped talking to {npc.get('name', 'the villager')}.")
                return
            if choice.value == "talk":
                self.talk_to_town_npc(npc)
                return
            if choice.value == "gift":
                self.give_gift_to_town_npc(npc)
                return
            if choice.value == "rumor":
                self.vertical_panel_view(f"{npc.get('name')} Rumor", self.town_npc_rumor_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                self.set_message(f"Asked {npc.get('name')} about rumors.")
                continue
            if choice.value == "errand":
                errand = self.errand_for_npc(npc)
                if self.can_complete_errand(errand):
                    self.complete_errand(errand)
                    return
                self.vertical_panel_view(f"{npc.get('name')} Errand", self.errand_lines(errand), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                self.set_message(f"{npc.get('name')} needs {errand.get('qty')} {errand.get('item')}.")
                continue
            if choice.value == "courtship":
                if self.court_town_npc(npc):
                    return
                continue
            if choice.value == "proposal":
                if self.propose_to_town_npc(npc):
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
                if self.invite_spouse_to_farm(npc):
                    return
                continue
            if choice.value == "marriage_scene":
                if self.play_marriage_scene(npc):
                    return
                continue
            if choice.value == "family_memories":
                self.vertical_panel_view("Family Memories", self.family_event_log_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "plan_family":
                if self.family_planning_menu(npc) == "changed":
                    return
                continue
            if choice.value == "pregnancy_checkup":
                if self.complete_pregnancy_checkup(npc):
                    return
                continue
            if choice.value == "family_status":
                self.vertical_panel_view("Family", self.family_status_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                self.set_message("Reviewed family status.")
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
                self.vertical_panel_view("Household Help", self.family_help_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                toggle_items = [
                    MenuItem(label="Toggle household help", value="toggle", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ]
                toggle_choice = self.vertical_panel_select("Household Help", toggle_items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
                if toggle_choice and toggle_choice.value == "toggle":
                    self.toggle_family_help()
                    return
                continue
            if choice.value == "profile":
                self.vertical_panel_view(f"{npc.get('name')} Profile", self.town_npc_profile_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "status":
                self.vertical_panel_view(str(npc.get("name", "Villager")), self.town_npc_status_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue

    def talk_to_town_npc(self, npc: Dict[str, object]):
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        today = self.town_npc_day_key()
        first_talk_today = self.state.town_npc_last_talk_day.get(npc_id) != today
        self.state.town_npc_dialogue_counts[npc_id] = int(self.state.town_npc_dialogue_counts.get(npc_id, 0)) + 1
        actual_gain = 0
        if first_talk_today:
            actual_gain = self.adjust_town_npc_relationship(npc_id, RELATIONSHIP_TALK_GAIN)
            self.state.town_npc_last_talk_day[npc_id] = today
            if self.maybe_play_scene_for_context({"type": "npc_talk", "npc": npc, "npc_id": npc_id}):
                message = self.state.message or f"Shared a moment with {npc.get('name', 'the villager')}."
                self.autosave_with_message(message)
                return
        title = f"{npc.get('name', 'Villager')}"
        lines = self.town_npc_dialogue_lines(npc, first_talk_today=first_talk_today)
        self.vertical_panel_view(title, lines, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        bonus = f" Relationship +{actual_gain}." if actual_gain > 0 else ""
        self.autosave_with_message(f"Talked to {npc.get('name', 'the villager')}.{bonus}")



__all__ = ["NpcMixin"]
