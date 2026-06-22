from __future__ import annotations

"""Multi-generational dynasty, aging, retirement, and succession systems."""

from typing import Dict, List, Optional, Tuple

from ascii_farmstead_combat import (
    DEFAULT_COMBAT_ACCESSORY,
    DEFAULT_COMBAT_ARMOR,
    DEFAULT_COMBAT_ATTACK,
    DEFAULT_COMBAT_DEFENSE,
    DEFAULT_COMBAT_EXP,
    DEFAULT_COMBAT_EXP_TO_NEXT,
    DEFAULT_COMBAT_MAX_FOCUS,
    DEFAULT_COMBAT_MAX_HP,
    DEFAULT_COMBAT_SKILL_POINTS,
    DEFAULT_COMBAT_WEAPON,
)
from ascii_farmstead_data import LEFT_PANEL_HEIGHT, LEFT_PANEL_WIDTH, MENU_BACK
from ascii_farmstead_helpers import add_months_to_date, format_birthday, format_date
from ascii_farmstead_npc_builder import stable_text_seed
from ascii_farmstead_ui import MenuItem


DYNASTY_RETIREMENT_AGE = 55
DYNASTY_HEIR_AGE_MONTHS = 216
DYNASTY_HEALTH_WARNING_AGE = 75

DYNASTY_HEIRLOOMS: Dict[str, Dict[str, str]] = {
    "field_journal": {
        "name": "Founder's Field Journal",
        "description": "Household notes preserve confidence, affection, and practical memory.",
        "effect": "+15 starting family bond for each new generation.",
    },
    "trade_seal": {
        "name": "Caravan Trade Seal",
        "description": "A worn seal recognized along routes founded by the family.",
        "effect": "+5% income from active trade routes.",
    },
    "civic_signet": {
        "name": "Civic Signet",
        "description": "A public-service token that opens doors for the next farmstead head.",
        "effect": "More friendship carries into the next generation.",
    },
    "delver_medal": {
        "name": "Delver's Medal",
        "description": "A hard-earned emblem from the deepest expeditions of an earlier life.",
        "effect": "+1 starting combat attack for future heirs.",
    },
}


class DynastyMixin:
    """Player years, family succession, dynasty records, and elder actors."""

    def aging_and_death_active(self) -> bool:
        return bool(getattr(self.state, "aging_and_death_enabled", True))

    def dynasty_lifespan_for_identity(
        self,
        name: str,
        birth_year: int,
        generation: int,
    ) -> int:
        seed = stable_text_seed(
            f"{str(name).casefold()}:{int(birth_year)}:{int(generation)}:lifespan"
        )
        return 88 + seed % 14

    def raw_player_age_on_date(
        self,
        month: int,
        day: int,
        year: int,
    ) -> int:
        age = int(year) - int(getattr(self.state, "player_birth_year", year))
        birthday = (
            int(getattr(self.state, "player_birthday_month", 3)),
            int(getattr(self.state, "player_birthday_day", 1)),
        )
        if (int(month), int(day)) < birthday:
            age -= 1
        return max(0, age)

    def player_age_on_date(
        self,
        month: int,
        day: int,
        year: int,
    ) -> int:
        raw_age = self.raw_player_age_on_date(month, day, year)
        if self.aging_and_death_active() or raw_age < 18:
            return raw_age
        frozen_age = int(getattr(self.state, "player_frozen_age", 0) or 0)
        return max(18, frozen_age or raw_age)

    def player_age(self) -> int:
        return self.player_age_on_date(
            int(self.state.month),
            int(self.state.day),
            int(self.state.year),
        )

    def player_birth_date_label(self) -> str:
        return format_date(
            int(self.state.player_birthday_month),
            int(self.state.player_birthday_day),
            int(self.state.player_birth_year),
        )

    def player_life_stage(self, age: Optional[int] = None) -> str:
        age = self.player_age() if age is None else max(0, int(age))
        if age < 35:
            return "Young Adult"
        if age < 55:
            return "Established Adult"
        if age < 70:
            return "Senior"
        if age < 85:
            return "Elder"
        return "Venerable Elder"

    def player_age_display_line(self) -> str:
        if not self.aging_and_death_active():
            return f"Life stage: {self.player_life_stage()}"
        return f"Age: {self.player_age()} ({self.player_life_stage()})"

    def player_birth_display_line(self) -> str:
        if not self.aging_and_death_active():
            return f"Birthday: {format_birthday(self.state.player_birthday_month, self.state.player_birthday_day)}"
        return f"Born: {self.player_birth_date_label()}"

    def player_health_outlook(self, age: Optional[int] = None) -> str:
        if not self.aging_and_death_active():
            return "Aging and natural death are disabled."
        age = self.player_age() if age is None else max(0, int(age))
        remaining = int(self.state.player_lifespan_age) - age
        if age < DYNASTY_HEALTH_WARNING_AGE:
            return "No age-related concerns."
        if remaining > 10:
            return "Age is noticeable, but daily life remains steady."
        if remaining > 5:
            return "The household has begun planning for eventual succession."
        if remaining > 2:
            return "Old age is advanced. Designating an heir is strongly advised."
        if remaining > 0:
            return "The family recognizes that succession may be close."
        return "Natural lifespan has been reached; succession is imminent."

    def child_dynasty_id(self, child: Dict[str, object]) -> int:
        try:
            return max(0, int(child.get("id", 0)))
        except Exception:
            return 0

    def raw_dynasty_person_age(
        self,
        person: Dict[str, object],
        month: Optional[int] = None,
        day: Optional[int] = None,
        year: Optional[int] = None,
    ) -> int:
        month = int(self.state.month if month is None else month)
        day = int(self.state.day if day is None else day)
        year = int(self.state.year if year is None else year)
        birth_month = max(1, min(12, int(person.get("birth_month", 3) or 3)))
        birth_day = max(1, min(31, int(person.get("birth_day", 1) or 1)))
        birth_year = int(person.get("birth_year", year) or year)
        age = year - birth_year
        if (month, day) < (birth_month, birth_day):
            age -= 1
        return max(0, age)

    def dynasty_person_age(
        self,
        person: Dict[str, object],
        month: Optional[int] = None,
        day: Optional[int] = None,
        year: Optional[int] = None,
    ) -> int:
        age = self.raw_dynasty_person_age(person, month, day, year)
        if self.aging_and_death_active() or age < 18:
            return age
        frozen_age = int(
            person.get(
                "frozen_age_years",
                person.get("age_years", age),
            )
            or age
        )
        return max(18, frozen_age)

    def dynasty_person_life_stage(
        self,
        person: Dict[str, object],
    ) -> str:
        existing = str(person.get("age_group", "") or "")
        if (
            not self.aging_and_death_active()
            and existing in {"Adult", "Elder"}
        ):
            return existing
        age = self.dynasty_person_age(person)
        if age < 13:
            return "Child"
        if age < 18:
            return "Teen"
        if age < 65:
            return "Adult"
        return "Elder"

    def dynasty_person_age_phrase(
        self,
        person: Dict[str, object],
    ) -> str:
        if not self.aging_and_death_active():
            return f"life stage {self.dynasty_person_life_stage(person)}"
        return f"age {self.dynasty_person_age(person)}"

    def set_aging_and_death_enabled(
        self,
        enabled: bool,
        autosave: bool = True,
    ) -> None:
        enabled = bool(enabled)
        if enabled == self.aging_and_death_active():
            return
        if not enabled:
            self.state.player_frozen_age = max(
                18,
                self.raw_player_age_on_date(
                    self.state.month,
                    self.state.day,
                    self.state.year,
                ),
            )
            if str(getattr(self.state, "spouse_npc_id", "") or ""):
                spouse = self.npc_record_by_id(self.state.spouse_npc_id)
                if spouse:
                    self.initialize_spouse_lifespan(spouse)
                    self.state.spouse_frozen_age = max(
                        18,
                        self.spouse_age_years(spouse),
                    )
            for child in getattr(self.state, "children", []) or []:
                raw_months = self.household_child_raw_age_months(child)
                if raw_months >= DYNASTY_HEIR_AGE_MONTHS:
                    child["aging_frozen_months"] = raw_months
            for person in [
                *getattr(self.state, "dynasty_elders", []),
                *getattr(self.state, "dynasty_kin", []),
            ]:
                if isinstance(person, dict) and person.get("active", True):
                    raw_age = self.raw_dynasty_person_age(person)
                    if raw_age >= 18:
                        person["frozen_age_years"] = raw_age
                        person["age_years"] = raw_age
            self.state.aging_and_death_enabled = False
            message = (
                "Aging and death disabled. Children still grow to adulthood; "
                "adults remain in their current life stage."
            )
        else:
            frozen_age = max(
                18,
                int(getattr(self.state, "player_frozen_age", 18) or 18),
            )
            birthday_passed = (
                int(self.state.player_birthday_month),
                int(self.state.player_birthday_day),
            ) <= (int(self.state.month), int(self.state.day))
            self.state.player_birth_year = (
                int(self.state.year) - frozen_age
                if birthday_passed
                else int(self.state.year) - frozen_age - 1
            )
            self.state.player_frozen_age = 0
            if (
                str(getattr(self.state, "spouse_npc_id", "") or "")
                and int(getattr(self.state, "spouse_frozen_age", 0) or 0) > 0
            ):
                spouse = self.npc_record_by_id(self.state.spouse_npc_id)
                if spouse:
                    frozen_spouse_age = int(self.state.spouse_frozen_age)
                    spouse_birthday = self.npc_birthday(spouse)
                    spouse_birthday_passed = spouse_birthday <= (
                        int(self.state.month),
                        int(self.state.day),
                    )
                    self.state.spouse_birth_year = (
                        int(self.state.year) - frozen_spouse_age
                        if spouse_birthday_passed
                        else int(self.state.year) - frozen_spouse_age - 1
                    )
                self.state.spouse_frozen_age = 0
            for child in getattr(self.state, "children", []) or []:
                frozen_months = int(child.pop("aging_frozen_months", 0) or 0)
                if frozen_months <= 0:
                    frozen_months = min(
                        self.household_child_raw_age_months(child),
                        DYNASTY_HEIR_AGE_MONTHS,
                    )
                raw_months = self.household_child_raw_age_months(child)
                paused_months = max(0, raw_months - frozen_months)
                if paused_months:
                    month, day, year = add_months_to_date(
                        int(child.get("birth_month", 1)),
                        int(child.get("birth_day", 1)),
                        int(child.get("birth_year", 1)),
                        paused_months,
                    )
                    child["birth_month"] = month
                    child["birth_day"] = day
                    child["birth_year"] = year
            for person in [
                *getattr(self.state, "dynasty_elders", []),
                *getattr(self.state, "dynasty_kin", []),
            ]:
                if not isinstance(person, dict):
                    continue
                frozen = int(person.pop("frozen_age_years", 0) or 0)
                if frozen <= 0:
                    continue
                birthday_passed = (
                    int(person.get("birth_month", 3)),
                    int(person.get("birth_day", 1)),
                ) <= (int(self.state.month), int(self.state.day))
                person["birth_year"] = (
                    int(self.state.year) - frozen
                    if birthday_passed
                    else int(self.state.year) - frozen - 1
                )
                person["age_years"] = frozen
            self.state.aging_and_death_enabled = True
            message = "Aging and natural death enabled. Life stages will progress again."
        if autosave:
            self.autosave_with_message(message)
        else:
            self.set_message(message)

    def dynasty_relation_for_generation(
        self,
        person: Dict[str, object],
    ) -> str:
        relation = str(person.get("relation", "Relative"))
        gap = int(self.state.player_generation) - int(
            person.get("generation", self.state.player_generation)
        )
        if relation == "Sibling" and gap > 0:
            return "Aunt" if str(person.get("sex")) == "Female" else "Uncle"
        if relation == "Parent" and gap > 0:
            return "Grandparent" if gap == 1 else "Ancestor"
        return relation

    def has_dynasty_heirloom(self, heirloom_type: str) -> bool:
        return any(
            isinstance(record, dict)
            and str(record.get("type", "")) == str(heirloom_type)
            for record in getattr(self.state, "dynasty_heirlooms", []) or []
        )

    def dynasty_heirloom_options(
        self,
        record: Dict[str, object],
    ) -> List[str]:
        options = ["field_journal"]
        if int(record.get("businesses", 0)) or int(record.get("routes", 0)):
            options.append("trade_seal")
        if record.get("offices_held"):
            options.append("civic_signet")
        if int(record.get("mine_depth", 1)) >= 5:
            options.append("delver_medal")
        return options

    def preferred_dynasty_heirloom(
        self,
        record: Dict[str, object],
    ) -> str:
        options = self.dynasty_heirloom_options(record)
        for heirloom_type in (
            "civic_signet",
            "trade_seal",
            "delver_medal",
            "field_journal",
        ):
            if heirloom_type in options and not self.has_dynasty_heirloom(
                heirloom_type
            ):
                return heirloom_type
        return options[0]

    def add_dynasty_heirloom(
        self,
        heirloom_type: str,
        record: Dict[str, object],
    ) -> Dict[str, object]:
        if heirloom_type not in DYNASTY_HEIRLOOMS:
            heirloom_type = "field_journal"
        definition = DYNASTY_HEIRLOOMS[heirloom_type]
        heirloom_id = (
            f"heirloom:{record.get('generation', 1)}:{heirloom_type}"
        )
        existing = next(
            (
                item
                for item in self.state.dynasty_heirlooms
                if str(item.get("id", "")) == heirloom_id
            ),
            None,
        )
        if existing:
            return existing
        heirloom = {
            "id": heirloom_id,
            "type": heirloom_type,
            "name": definition["name"],
            "description": definition["description"],
            "effect": definition["effect"],
            "origin_generation": int(record.get("generation", 1)),
            "origin_name": str(record.get("name", "Unknown")),
            "year": int(record.get("end_year", self.state.year)),
        }
        self.state.dynasty_heirlooms = (
            list(self.state.dynasty_heirlooms) + [heirloom]
        )[-20:]
        return heirloom

    def eligible_dynasty_heirs(self) -> List[Dict[str, object]]:
        heirs = [
            child
            for child in getattr(self.state, "children", []) or []
            if isinstance(child, dict)
            and self.household_child_age_months(child) >= DYNASTY_HEIR_AGE_MONTHS
        ]
        return sorted(
            heirs,
            key=lambda child: (
                -self.household_child_age_months(child),
                str(child.get("name", "")),
            ),
        )

    def designated_dynasty_heir(self) -> Optional[Dict[str, object]]:
        heir_id = int(getattr(self.state, "designated_heir_child_id", 0) or 0)
        return next(
            (
                child
                for child in self.eligible_dynasty_heirs()
                if self.child_dynasty_id(child) == heir_id
            ),
            None,
        )

    def designate_dynasty_heir(self, child_id: int) -> bool:
        child = next(
            (
                candidate
                for candidate in self.eligible_dynasty_heirs()
                if self.child_dynasty_id(candidate) == int(child_id)
            ),
            None,
        )
        if not child:
            self.set_message("Only a young-adult child can be designated as heir.")
            return False
        self.state.designated_heir_child_id = self.child_dynasty_id(child)
        self.record_family_event(
            "Heir Designated",
            f"{child.get('name')} was named heir to the farmstead.",
            flag=f"heir:{self.state.player_generation}:{child.get('id')}",
        )
        self.autosave_with_message(
            f"{child.get('name')} is now the designated heir."
        )
        return True

    def dynasty_heir_upbringing_lines(
        self,
        child: Dict[str, object],
    ) -> List[str]:
        child = self.ensure_child_profile_fields(child)
        child_key = self.child_key(child)
        learning = dict(
            getattr(self.state, "child_learning_points", {}).get(
                child_key,
                {},
            )
            or {}
        )
        learning_rows = sorted(
            learning.items(),
            key=lambda row: (-int(row[1]), str(row[0])),
        )
        top_subject = learning_rows[0][0] if learning_rows else "General Studies"
        top_points = int(learning_rows[0][1]) if learning_rows else 0
        return [
            f"{child.get('name', 'Heir')} - succession profile",
            "",
            (
                f"Age: {self.household_child_age_months(child) // 12}"
                if self.aging_and_death_active()
                else f"Life stage: {self.household_child_stage(child)}"
            ),
            f"Trait: {child.get('personality_trait', 'Curious')}",
            f"Upbringing path: {child.get('apprentice_path', 'Helper')}",
            f"Starting class: {child.get('starting_class', 'Vanguard')}",
            f"Strongest subject: {top_subject} ({top_points})",
            f"Chore specialty: {self.child_chore_assignment(child)}",
            f"Affection: {self.child_affection_rank(child)} "
            f"({self.child_affection_score(child)})",
            "",
            "These records become the heir's starting background, combat training, "
            "confidence, and inherited family bond.",
        ]

    def dynasty_record_for_current_player(
        self,
        reason: str,
        end_year: int,
    ) -> Dict[str, object]:
        return {
            "generation": int(self.state.player_generation),
            "name": str(self.state.player_name),
            "sex": str(self.state.player_sex),
            "birth_month": int(self.state.player_birthday_month),
            "birth_day": int(self.state.player_birthday_day),
            "birth_year": int(self.state.player_birth_year),
            "age": self.player_age(),
            "end_year": int(end_year),
            "end_reason": str(reason),
            "background": str(self.state.player_background),
            "starting_class": str(self.state.player_starting_class),
            "money_inherited": int(self.state.money),
            "properties": len(getattr(self.state, "player_properties", {}) or {}),
            "businesses": len(getattr(self.state, "player_businesses", {}) or {}),
            "routes": len(getattr(self.state, "player_trade_routes", {}) or {}),
            "claims": len(getattr(self.state, "owned_wilderness_claims", {}) or {}),
            "children": [
                {
                    "id": self.child_dynasty_id(child),
                    "name": str(child.get("name", "Child")),
                    "sex": str(child.get("sex", "Unknown")),
                    "birth_year": int(child.get("birth_year", self.state.year)),
                    "path": str(child.get("apprentice_path", "Helper")),
                }
                for child in getattr(self.state, "children", []) or []
                if isinstance(child, dict)
            ],
            "spouse_name": (
                self.town_npc_name(self.state.spouse_npc_id)
                if self.state.spouse_npc_id
                else ""
            ),
            "offices_held": list(
                getattr(self.state, "civic_profile", {}).get(
                    "offices_held",
                    [],
                )
                or []
            ),
            "museum_donations": len(
                getattr(self.state, "museum_donated_record_ids", []) or []
            ),
            "mine_depth": int(getattr(self.state, "deepest_mine_floor", 1)),
        }

    def add_retired_player_elder(
        self,
        record: Dict[str, object],
    ) -> None:
        elder_id = f"dynasty_elder:{record.get('generation', 1)}"
        elder = {
            "id": elder_id,
            "name": str(record.get("name", "Retired Farmer")),
            "sex": str(record.get("sex", "Unknown")),
            "role": "Retired Farmer",
            "age_group": "Elder",
            "age_years": int(record.get("age", 60)),
            "birth_month": int(record.get("birth_month", 3)),
            "birth_day": int(record.get("birth_day", 1)),
            "birth_year": int(record.get("birth_year", self.state.year - 60)),
            "lifespan_age": self.dynasty_lifespan_for_identity(
                str(record.get("name", "Retired Farmer")),
                int(record.get("birth_year", self.state.year - 60)),
                int(record.get("generation", 1)),
            ),
            "generation": int(record.get("generation", 1)),
            "relation": "Parent",
            "retired_year": int(record.get("end_year", self.state.year)),
            "background": str(record.get("background", "Farmer")),
            "starting_class": str(record.get("starting_class", "Vanguard")),
            "relationship": 250,
            "dynasty_elder": True,
            "activity": "keeping the family history and offering practical advice",
            "active": True,
        }
        self.state.dynasty_elders = [
            existing
            for existing in self.state.dynasty_elders
            if str(existing.get("id", "")) != elder_id
        ] + [elder]
        self.state.town_npc_relationships[elder_id] = 250

    def dynasty_kin_occupation(self, child: Dict[str, object]) -> str:
        path = str(child.get("apprentice_path", "Helper"))
        return {
            "Scholar": "Researcher and tutor",
            "Builder": "Carpenter",
            "Farmer": "Independent grower",
            "Rancher": "Animal keeper",
            "Merchant": "Trader",
            "Explorer": "Wilderness guide",
            "Healer": "Community healer",
            "Miner": "Prospector",
            "Fisher": "Fisher",
            "Cook": "Cook",
        }.get(path, f"{path} specialist")

    def archive_outgoing_household_as_kin(
        self,
        heir: Dict[str, object],
        record: Dict[str, object],
        transition_years: int,
    ) -> List[Dict[str, object]]:
        heir_id = self.child_dynasty_id(heir)
        new_generation = int(record.get("generation", 1)) + 1
        archived: List[Dict[str, object]] = []
        sibling_index = 0
        discovered_towns = self.discovered_procedural_town_plans()
        for child in getattr(self.state, "children", []) or []:
            if (
                not isinstance(child, dict)
                or self.child_dynasty_id(child) == heir_id
            ):
                continue
            child = self.ensure_child_profile_fields(child)
            child_id = self.child_dynasty_id(child)
            kin_id = (
                f"dynasty_kin:{new_generation}:"
                f"{child_id or sibling_index + 1}"
            )
            age_months = self.household_child_age_months(child)
            if age_months < DYNASTY_HEIR_AGE_MONTHS:
                residence = "Farmhouse"
            elif sibling_index == 0 and transition_years <= 3:
                residence = "Farmhouse"
            elif discovered_towns:
                town = discovered_towns[sibling_index % len(discovered_towns)]
                residence = str(town.get("name", "A wilderness town"))
            else:
                residence = "Elsewhere in the region"
            birth_year = int(child.get("birth_year", self.state.year - 18))
            kin = {
                "id": kin_id,
                "name": str(child.get("name", "Sibling")),
                "sex": str(child.get("sex", "Unknown")),
                "role": "Family",
                "relation": "Sibling",
                "generation": new_generation,
                "birth_month": int(child.get("birth_month", 3)),
                "birth_day": int(child.get("birth_day", 1)),
                "birth_year": birth_year,
                "lifespan_age": self.dynasty_lifespan_for_identity(
                    str(child.get("name", "Sibling")),
                    birth_year,
                    new_generation,
                ),
                "personality_trait": str(
                    child.get("personality_trait", "Curious")
                ),
                "apprentice_path": str(
                    child.get("apprentice_path", "Helper")
                ),
                "starting_class": str(
                    child.get("starting_class", "Vanguard")
                ),
                "occupation": self.dynasty_kin_occupation(child),
                "residence": residence,
                "relationship": max(
                    120,
                    min(250, self.child_affection_score(child)),
                ),
                "age_group": "Adult",
                "dynasty_kin": True,
                "active": True,
                "activity": (
                    f"working as a {self.dynasty_kin_occupation(child).lower()}"
                ),
            }
            archived.append(kin)
            sibling_index += 1

        spouse_id = str(getattr(self.state, "spouse_npc_id", "") or "")
        if spouse_id:
            spouse = self.npc_record_by_id(spouse_id) or {}
            try:
                birth_month, birth_day = self.npc_birthday(spouse)
            except Exception:
                birth_month, birth_day = 3, 1
            estimated_age = 38 + stable_text_seed(
                f"{spouse_id}:{record.get('end_year')}:parent-age"
            ) % 18
            birth_year = int(record.get("end_year", self.state.year)) - estimated_age
            archived.append(
                {
                    "id": f"dynasty_parent:{record.get('generation', 1)}:{spouse_id}",
                    "name": str(
                        spouse.get("name")
                        or record.get("spouse_name")
                        or "Parent"
                    ),
                    "sex": str(spouse.get("sex", "Unknown")),
                    "role": "Family",
                    "relation": "Parent",
                    "generation": int(record.get("generation", 1)),
                    "linked_npc_id": spouse_id,
                    "birth_month": int(birth_month),
                    "birth_day": int(birth_day),
                    "birth_year": birth_year,
                    "lifespan_age": self.dynasty_lifespan_for_identity(
                        str(spouse.get("name", spouse_id)),
                        birth_year,
                        int(record.get("generation", 1)),
                    ),
                    "residence": str(
                        spouse.get("home_name")
                        or spouse.get("town_name")
                        or "Their former home"
                    ),
                    "occupation": str(spouse.get("role", "Retired villager")),
                    "relationship": 220,
                    "dynasty_kin": True,
                    "linked_existing_npc": True,
                    "active": True,
                }
            )

        existing_by_id = {
            str(item.get("id", "")): item
            for item in getattr(self.state, "dynasty_kin", []) or []
            if isinstance(item, dict)
        }
        for kin in archived:
            existing_by_id[str(kin.get("id", ""))] = kin
        self.state.dynasty_kin = list(existing_by_id.values())[-40:]
        return archived

    def reset_personal_state_for_heir(
        self,
        child: Dict[str, object],
    ) -> None:
        relationship_cap = (
            75 if self.has_dynasty_heirloom("civic_signet") else 60
        )
        relationship_divisor = (
            2 if self.has_dynasty_heirloom("civic_signet") else 3
        )
        inherited_relationships = {
            str(npc_id): max(
                0,
                min(relationship_cap, int(points) // relationship_divisor),
            )
            for npc_id, points in (
                getattr(self.state, "town_npc_relationships", {}) or {}
            ).items()
            if not str(npc_id).startswith(
                ("dynasty_elder:", "dynasty_kin:")
            )
        }
        for elder in getattr(self.state, "dynasty_elders", []) or []:
            if isinstance(elder, dict) and elder.get("active", True):
                inherited_relationships[str(elder.get("id", ""))] = 250
        for kin in getattr(self.state, "dynasty_kin", []) or []:
            if isinstance(kin, dict) and kin.get("active", True):
                inherited_relationships[str(kin.get("id", ""))] = int(
                    kin.get("relationship", 180)
                )
        for population in (
            getattr(self.state, "procedural_settlement_populations", {}) or {}
        ).values():
            if not isinstance(population, dict):
                continue
            for resident in population.get("residents", {}).values():
                if not isinstance(resident, dict):
                    continue
                resident["relationship"] = max(
                    0,
                    min(
                        relationship_cap,
                        int(resident.get("relationship", 0))
                        // relationship_divisor,
                    ),
                )
                resident["dialogue_count"] = 0
                resident["last_talk_day"] = ""
                resident["last_gift_day"] = ""
        self.state.town_npc_relationships = inherited_relationships
        self.state.town_npc_dialogue_counts = {}
        self.state.town_npc_last_talk_day = {}
        self.state.town_npc_last_gift_day = {}
        self.state.town_npc_last_court_day = {}
        self.state.town_npc_courtship_counts = {}
        self.state.town_npc_last_proposal_day = {}
        self.state.dating_npc_ids = []
        self.state.engaged_npc_id = ""
        self.state.engagement_month = 0
        self.state.engagement_day = 0
        self.state.engagement_year = 0
        self.state.wedding_month = 0
        self.state.wedding_day = 0
        self.state.wedding_year = 0
        self.state.spouse_npc_id = ""
        self.state.spouse_moved_to_farm = False
        self.state.marriage_month = 0
        self.state.marriage_day = 0
        self.state.marriage_year = 0
        self.state.spouse_birth_year = 0
        self.state.spouse_lifespan_age = 0
        self.state.spouse_frozen_age = 0
        self.state.marriage_history = []
        self.state.deceased_spouse_npc_ids = []
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
        self.state.children = []
        self.state.next_child_id = 1
        self.state.child_affection = {}
        self.state.child_last_gift_day = {}
        self.state.child_last_lesson_day = {}
        self.state.child_learning_points = {}
        self.state.child_chore_assignments = {}
        self.state.child_milestone_flags = []
        self.state.family_event_flags = []
        self.state.family_meal_last_day = ""
        self.state.family_last_meal = ""
        self.state.family_help_enabled = True
        self.state.family_bond = min(
            120,
            max(20, self.child_affection_score(child) // 2),
        )
        self.state.designated_heir_child_id = 0
        self.state.travel_follower_ids = [
            follower_id
            for follower_id in self.state.travel_follower_ids
            if not str(follower_id).startswith("household_child:")
        ]
        self.state.active_party_member_ids = [
            member_id
            for member_id in self.state.active_party_member_ids
            if not str(member_id).startswith("household_child:")
        ]
        for property_record in self.state.player_properties.values():
            property_record["household_moved"] = False
        self.state.primary_residence_id = "farmhouse"
        civic_profile = getattr(self.state, "civic_profile", {})
        if isinstance(civic_profile, dict):
            civic_profile["campaign_endorsements"] = []
            civic_profile["offices_held"] = []
            council = civic_profile.get("regional_council", {})
            if isinstance(council, dict):
                council["member"] = False
                council["delegate_town_key"] = ""
            contracts = civic_profile.get("regional_contracts", {})
            if isinstance(contracts, dict):
                for contract in contracts.get("contracts", {}).values():
                    if (
                        isinstance(contract, dict)
                        and contract.get("status") == "active"
                    ):
                        contract["status"] = "available"
                        contract["accepted_day"] = ""
        for plan in self.discovered_procedural_town_plans():
            politics = self.ensure_procedural_town_politics(plan)
            if str(politics.get("incumbent_id", "")) == "player":
                replacement = next(
                    (
                        candidate_id
                        for candidate_id in politics.get("candidate_ids", [])
                        if str(candidate_id) != "player"
                    ),
                    "",
                )
                politics["incumbent_id"] = str(replacement)
            politics["candidate_ids"] = [
                candidate_id
                for candidate_id in politics.get("candidate_ids", [])
                if str(candidate_id) != "player"
            ]
            politics["player_registered"] = False

    def initialize_heir_combat(
        self,
        child: Dict[str, object],
    ) -> None:
        child = self.ensure_child_profile_fields(child)
        child_key = self.child_key(child)
        learning = dict(
            getattr(self.state, "child_learning_points", {}).get(
                child_key,
                {},
            )
            or {}
        )
        training = sum(max(0, int(value)) for value in learning.values())
        starting_level = 1 + min(4, training // 18)
        self.state.player_starting_class = str(
            child.get("starting_class", "Vanguard")
        )
        self.state.player_background = (
            f"{child.get('personality_trait', 'Curious')} "
            f"{child.get('apprentice_path', 'Helper')}"
        )
        self.state.combat_level = starting_level
        self.state.combat_exp = DEFAULT_COMBAT_EXP
        self.state.combat_exp_to_next = DEFAULT_COMBAT_EXP_TO_NEXT
        self.state.combat_max_hp = DEFAULT_COMBAT_MAX_HP + (starting_level - 1) * 4
        self.state.combat_current_hp = self.state.combat_max_hp
        self.state.combat_attack = DEFAULT_COMBAT_ATTACK + (starting_level - 1)
        if self.has_dynasty_heirloom("delver_medal"):
            self.state.combat_attack += 1
        self.state.combat_defense = DEFAULT_COMBAT_DEFENSE + (starting_level - 1) // 2
        self.state.combat_max_focus = DEFAULT_COMBAT_MAX_FOCUS + (starting_level - 1) // 2
        self.state.combat_focus = self.state.combat_max_focus
        self.state.combat_skill_points = DEFAULT_COMBAT_SKILL_POINTS
        self.state.equipped_weapon = DEFAULT_COMBAT_WEAPON
        self.state.equipped_armor = DEFAULT_COMBAT_ARMOR
        self.state.equipped_accessory = DEFAULT_COMBAT_ACCESSORY

    def advance_dynasty_kin_transition(self, years: int) -> Tuple[int, int]:
        moved = 0
        households = 0
        towns = self.discovered_procedural_town_plans()
        for index, kin in enumerate(self.state.dynasty_kin):
            if not isinstance(kin, dict) or not kin.get("active", True):
                continue
            age = self.dynasty_person_age(kin)
            kin["age_years"] = age
            if (
                kin.get("relation") == "Sibling"
                and age >= 20
                and years >= 3
                and str(kin.get("residence")) == "Farmhouse"
                and stable_text_seed(f"{kin.get('id')}:{self.state.year}:move") % 3
                != 0
            ):
                if towns:
                    town = towns[index % len(towns)]
                    kin["residence"] = str(
                        town.get("name", "A wilderness town")
                    )
                else:
                    kin["residence"] = "Elsewhere in the region"
                moved += 1
            if (
                kin.get("relation") == "Sibling"
                and age >= 24
                and years >= 3
                and not kin.get("formed_household")
                and stable_text_seed(
                    f"{kin.get('id')}:{self.state.year}:household"
                )
                % 4
                != 0
            ):
                kin["formed_household"] = True
                kin["household_children"] = (
                    stable_text_seed(f"{kin.get('id')}:children") % 3
                )
                households += 1
        for elder in self.state.dynasty_elders:
            if isinstance(elder, dict) and elder.get("active", True):
                elder["age_years"] = self.dynasty_person_age(elder)
        return moved, households

    def dynasty_transition_income(self, years: int) -> int:
        operating_days = min(300, max(0, int(years)) * 45)
        if operating_days <= 0:
            return 0
        total = 0
        property_total = 0
        business_total = 0
        trade_total = 0
        for property_record in self.state.player_properties.values():
            income = self.procedural_property_daily_income(
                property_record
            ) * operating_days
            property_record["lifetime_income"] = int(
                property_record.get("lifetime_income", 0)
            ) + income
            property_total += income
        for business in self.state.player_businesses.values():
            if not business.get("active"):
                continue
            income = self.procedural_business_daily_income(
                business
            ) * operating_days
            business["lifetime_income"] = int(
                business.get("lifetime_income", 0)
            ) + income
            business_total += income
        for route in self.state.player_trade_routes.values():
            if not route.get("active"):
                continue
            income = self.procedural_trade_route_daily_income(
                route
            ) * operating_days
            route["lifetime_income"] = int(
                route.get("lifetime_income", 0)
            ) + income
            trade_total += income
        total = property_total + business_total + trade_total
        if total:
            self.state.money += total
            profile = getattr(self.state, "civic_profile", {})
            if isinstance(profile, dict):
                profile["lifetime_property_income"] = int(
                    profile.get("lifetime_property_income", 0)
                ) + property_total
                profile["lifetime_business_income"] = int(
                    profile.get("lifetime_business_income", 0)
                ) + business_total
                profile["lifetime_trade_income"] = int(
                    profile.get("lifetime_trade_income", 0)
                ) + trade_total
        today = self.civic_date_ordinal()
        for collection in (
            self.state.player_properties,
            self.state.player_businesses,
            self.state.player_trade_routes,
        ):
            for asset in collection.values():
                asset["last_income_ordinal"] = today
        return total

    def simulate_dynasty_transition(self, years: int) -> List[str]:
        years = max(0, min(10, int(years)))
        if years <= 0:
            return ["No time jump; succession occurred immediately."]
        start_year = int(self.state.year)
        self.state.year += years
        towns_changed = 0
        elections_changed = 0
        for plan in self.discovered_procedural_town_plans():
            community = self.ensure_procedural_town_community(plan)
            community["development_points"] = int(
                community.get("development_points", 0)
            ) + years * 2
            self.advance_procedural_town_life(plan)
            politics = self.ensure_procedural_town_politics(plan)
            politics["treasury"] = int(
                politics.get("treasury", 0)
            ) + years * 120
            candidates = [
                str(candidate_id)
                for candidate_id in politics.get("candidate_ids", []) or []
                if str(candidate_id) != "player"
            ]
            if years >= 3 and candidates:
                next_incumbent = candidates[
                    stable_text_seed(
                        f"{plan.get('settlement_key')}:{self.state.year}:succession"
                    )
                    % len(candidates)
                ]
                if str(politics.get("incumbent_id", "")) != next_incumbent:
                    politics["incumbent_id"] = next_incumbent
                    elections_changed += 1
            towns_changed += 1
        route_deliveries = 0
        for route in self.state.player_trade_routes.values():
            if not route.get("active"):
                continue
            deliveries = years * max(4, 8 - min(4, int(route.get("distance", 1))))
            route["caravan_deliveries"] = int(
                route.get("caravan_deliveries", 0)
            ) + deliveries
            route["caravan_last_ordinal"] = self.civic_date_ordinal()
            route_deliveries += deliveries
        kin_moved, kin_households = self.advance_dynasty_kin_transition(years)
        legacy_income = self.dynasty_transition_income(years)
        self.state.weather = self.state.weather
        lines = [
            f"Time passed: Year {start_year} to Year {self.state.year}",
            f"Generated towns that continued developing: {towns_changed}",
            f"Town leadership changes: {elections_changed}",
            f"Caravan deliveries completed: {route_deliveries}",
            f"Estate income during the transition: {legacy_income}g",
            f"Relatives who established new homes: {kin_moved}",
            f"Relatives who began households of their own: {kin_households}",
            "Businesses, claims, homes, museum records, and regional projects remained in the family.",
        ]
        self.state.dynasty_transition_log = (
            list(self.state.dynasty_transition_log) + lines
        )[-40:]
        return lines

    def perform_dynasty_succession(
        self,
        child_id: int,
        reason: str = "Retirement",
        transition_years: int = 3,
        interactive: bool = True,
        heirloom_type: str = "",
    ) -> bool:
        child = next(
            (
                candidate
                for candidate in self.eligible_dynasty_heirs()
                if self.child_dynasty_id(candidate) == int(child_id)
            ),
            None,
        )
        if not child:
            self.set_message("No eligible heir was selected.")
            return False
        child = self.ensure_child_profile_fields(child)
        old_name = str(self.state.player_name)
        old_generation = int(self.state.player_generation)
        record = self.dynasty_record_for_current_player(
            reason,
            int(self.state.year),
        )
        self.state.dynasty_history = (
            list(self.state.dynasty_history) + [record]
        )[-40:]
        archived_kin = self.archive_outgoing_household_as_kin(
            child,
            record,
            transition_years,
        )
        if str(reason).casefold() == "retirement":
            self.add_retired_player_elder(record)
        available_heirlooms = self.dynasty_heirloom_options(record)
        if heirloom_type not in available_heirlooms:
            heirloom_type = self.preferred_dynasty_heirloom(record)
        heirloom = self.add_dynasty_heirloom(heirloom_type, record)

        child_learning = dict(
            getattr(self.state, "child_learning_points", {}).get(
                self.child_key(child),
                {},
            )
            or {}
        )
        child_affection = self.child_affection_score(child)
        child_chore = self.child_chore_assignment(child)
        self.initialize_heir_combat(child)
        self.state.player_name = str(child.get("name", "Heir"))
        self.state.player_sex = str(child.get("sex", "Female"))
        self.state.player_birthday_month = int(child.get("birth_month", 3))
        self.state.player_birthday_day = int(child.get("birth_day", 1))
        self.state.player_birth_year = int(child.get("birth_year", self.state.year - 18))
        self.state.player_generation = old_generation + 1
        self.state.player_lifespan_age = self.dynasty_lifespan_for_identity(
            self.state.player_name,
            self.state.player_birth_year,
            self.state.player_generation,
        )
        self.state.player_frozen_age = (
            max(18, self.household_child_age_months(child) // 12)
            if not self.aging_and_death_active()
            else 0
        )
        self.reset_personal_state_for_heir(child)
        heirloom_bond = (
            15 if self.has_dynasty_heirloom("field_journal") else 0
        )
        self.state.family_bond = min(
            150,
            max(25, child_affection // 2) + heirloom_bond,
        )
        transition_lines = self.simulate_dynasty_transition(transition_years)
        self.state.dynasty_last_family_update_year = int(self.state.year)
        self.state.location = "Farm"
        self.state.player_x = 8
        self.state.player_y = 9
        self.state.facing = "DOWN"
        self.state.stamina = self.max_stamina()
        self.state.hour = 6
        self.state.minute = 0
        self.state.weather = self.state.weather
        top_learning = max(
            child_learning.items(),
            key=lambda row: int(row[1]),
            default=("General Studies", 0),
        )
        summary = [
            f"GENERATION {self.state.player_generation}",
            "",
            f"{old_name}'s chapter ended through {str(reason).lower()}.",
            f"You now play as {self.state.player_name}.",
            self.player_age_display_line(),
            f"Background: {self.state.player_background}",
            f"Starting class: {self.state.player_starting_class}",
            f"Strongest learning: {top_learning[0]} ({top_learning[1]})",
            f"Chore specialty: {child_chore}",
            f"Starting family bond: {self.state.family_bond}",
            f"Living relatives carried forward: {len(archived_kin)}",
            f"Chosen heirloom: {heirloom.get('name')}",
            f"Heirloom effect: {heirloom.get('effect')}",
            "",
            "Inheritance:",
            "- Farm, claims, residences, businesses, trade routes, storage, museum records, and regional works",
            "- A portion of family introductions, but not the former player's romances or offices",
            "",
            *transition_lines,
        ]
        self.record_family_event(
            "Succession",
            f"{self.state.player_name} became the Generation "
            f"{self.state.player_generation} farmstead head after {old_name}.",
            flag=f"succession:{self.state.player_generation}",
        )
        if interactive:
            self.vertical_panel_view(
                "Dynasty Succession",
                summary,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
            )
        self.autosave_with_message(
            f"Generation {self.state.player_generation} begins with "
            f"{self.state.player_name}."
        )
        return True

    def can_retire_current_player(self) -> Tuple[bool, str]:
        if (
            self.aging_and_death_active()
            and self.player_age() < DYNASTY_RETIREMENT_AGE
        ):
            return (
                False,
                f"Retirement opens at age {DYNASTY_RETIREMENT_AGE}. "
                f"Current age: {self.player_age()}.",
            )
        if not self.eligible_dynasty_heirs():
            return False, "Retirement requires at least one young-adult child."
        return True, "Ready to pass the farmstead to an heir."

    def process_player_lifespan_overnight(self) -> str:
        if not self.aging_and_death_active():
            return ""
        if not self.is_player_birthday():
            return ""
        age = self.player_age()
        if age >= DYNASTY_HEALTH_WARNING_AGE:
            self.state.dynasty_last_health_warning_year = int(self.state.year)
        if age < int(self.state.player_lifespan_age):
            if age >= DYNASTY_HEALTH_WARNING_AGE:
                return f" {self.state.player_name} is now {age}; {self.player_health_outlook()}"
            return f" {self.state.player_name} is now {age}."
        heirs = self.eligible_dynasty_heirs()
        heir = self.designated_dynasty_heir() or (heirs[0] if heirs else None)
        if heir:
            old_name = str(self.state.player_name)
            heir_name = str(heir.get("name", "the heir"))
            if self.perform_dynasty_succession(
                self.child_dynasty_id(heir),
                reason="Natural death in old age",
                transition_years=1,
                interactive=False,
            ):
                return (
                    f" {old_name} died peacefully in old age. "
                    f"After a year of mourning and transition, {heir_name} "
                    "became head of the farmstead."
                )
        self.state.player_lifespan_age = min(
            115,
            int(self.state.player_lifespan_age) + 1,
        )
        return (
            " Old age has become serious, but no adult heir is available. "
            "The household has been granted a grace year to prepare succession."
        )

    def process_dynasty_family_overnight(self) -> str:
        if not self.aging_and_death_active():
            self.state.dynasty_last_family_update_year = int(self.state.year)
            return ""
        notices: List[str] = []
        today = (int(self.state.month), int(self.state.day))
        groups = (
            ("elder", self.state.dynasty_elders),
            ("relative", self.state.dynasty_kin),
        )
        for kind, people in groups:
            for person in people:
                if not isinstance(person, dict) or not person.get("active", True):
                    continue
                birthday = (
                    int(person.get("birth_month", 3) or 3),
                    int(person.get("birth_day", 1) or 1),
                )
                if birthday != today:
                    continue
                age = self.dynasty_person_age(person)
                person["age_years"] = age
                lifespan = int(
                    person.get(
                        "lifespan_age",
                        self.dynasty_lifespan_for_identity(
                            str(person.get("name", "Relative")),
                            int(person.get("birth_year", self.state.year - age)),
                            int(person.get("generation", 1)),
                        ),
                    )
                )
                person["lifespan_age"] = lifespan
                if age < lifespan:
                    continue
                person["active"] = False
                person["death_year"] = int(self.state.year)
                person["death_age"] = age
                person["activity"] = "remembered in the family archive"
                name = str(person.get("name", "A relative"))
                relation = (
                    "retired farmstead head"
                    if kind == "elder"
                    else self.dynasty_relation_for_generation(person).lower()
                )
                self.record_family_event(
                    "Family Passing",
                    f"{name}, {relation}, died peacefully at age {age}.",
                    flag=f"dynasty_death:{person.get('id')}:{self.state.year}",
                )
                notices.append(
                    f"{name}, the family's {relation}, died peacefully at age {age}."
                )
        self.state.dynasty_last_family_update_year = int(self.state.year)
        if not notices:
            return ""
        return " " + " ".join(notices)

    def dynasty_birthday_events_for_date(
        self,
        month: int,
        day: int,
        year: int,
    ) -> List[str]:
        events: List[str] = []
        for person in [
            *self.state.dynasty_elders,
            *self.state.dynasty_kin,
        ]:
            if not isinstance(person, dict) or not person.get("active", True):
                continue
            if person.get("linked_existing_npc"):
                continue
            if (
                int(person.get("birth_month", 0) or 0),
                int(person.get("birth_day", 0) or 0),
            ) != (int(month), int(day)):
                continue
            relation = (
                "family elder"
                if person.get("dynasty_elder")
                else self.dynasty_relation_for_generation(person).lower()
            )
            events.append(
                (
                    f"{person.get('name', 'Relative')}'s birthday "
                    f"({relation}, "
                    f"turns {self.dynasty_person_age(person, month, day, year)})"
                    if self.aging_and_death_active()
                    else f"{person.get('name', 'Relative')}'s birthday "
                    f"({relation}, {self.dynasty_person_life_stage(person)})"
                )
            )
        return events

    def dynasty_family_tree_lines(self) -> List[str]:
        lines = [
            "FAMILY TREE",
            "",
            f"Generation {self.state.player_generation}: "
            f"{self.state.player_name} (current farmstead head)",
        ]
        living = [
            person
            for person in [
                *self.state.dynasty_elders,
                *self.state.dynasty_kin,
            ]
            if isinstance(person, dict) and person.get("active", True)
        ]
        if living:
            lines.extend(["", "Living relatives:"])
            for person in sorted(
                living,
                key=lambda row: (
                    int(row.get("generation", 0)),
                    str(row.get("name", "")),
                ),
            ):
                relation = (
                    self.dynasty_relation_for_generation(person)
                    if person.get("dynasty_kin")
                    else (
                        "Parent"
                        if int(person.get("generation", 0))
                        == int(self.state.player_generation) - 1
                        else "Ancestor"
                    )
                )
                detail = str(
                    person.get("occupation")
                    or person.get("background")
                    or "Family"
                )
                residence = str(person.get("residence", "Farmhouse"))
                lines.append(
                    f"- {relation}: {person.get('name')} "
                    f"({self.dynasty_person_age_phrase(person)}, {detail}; "
                    f"{residence})"
                )
                if person.get("formed_household"):
                    lines.append(
                        f"  Their household includes "
                        f"{int(person.get('household_children', 0))} child(ren)."
                    )
        deceased = [
            person
            for person in [
                *self.state.dynasty_elders,
                *self.state.dynasty_kin,
            ]
            if isinstance(person, dict) and not person.get("active", True)
        ]
        if deceased:
            lines.extend(["", "Remembered relatives:"])
            for person in deceased[-12:]:
                lines.append(
                    f"- {person.get('name')} "
                    f"(died Year {person.get('death_year', '?')}, "
                    f"age {person.get('death_age', '?')})"
                )
        if len(lines) == 3:
            lines.extend(["", "No earlier household records have been preserved yet."])
        return lines

    def dynasty_ledger_lines(self) -> List[str]:
        heir = self.designated_dynasty_heir()
        lines = [
            str(self.state.dynasty_name).upper(),
            "",
            f"Current generation: {self.state.player_generation}",
            f"Farmstead head: {self.state.player_name}",
            self.player_birth_display_line(),
            self.player_age_display_line(),
            f"Background: {self.state.player_background}",
            f"Starting class: {self.state.player_starting_class}",
            f"Health outlook: {self.player_health_outlook()}",
            f"Designated heir: {heir.get('name') if heir else 'none'}",
            f"Eligible heirs: {len(self.eligible_dynasty_heirs())}",
            f"Retired elders living with the family: "
            f"{sum(1 for elder in self.state.dynasty_elders if elder.get('active'))}",
            f"Other living relatives recorded: "
            f"{sum(1 for kin in self.state.dynasty_kin if kin.get('active'))}",
            f"Family heirlooms: {len(self.state.dynasty_heirlooms)}",
            "",
            "Inherited estate:",
            f"- Wilderness claims: {len(self.state.owned_wilderness_claims)}",
            f"- Residences: {len(self.state.player_properties)}",
            f"- Businesses: {len(self.state.player_businesses)}",
            f"- Trade routes: {len(self.state.player_trade_routes)}",
            f"- Museum records: {len(self.state.museum_donated_record_ids)}",
        ]
        if self.state.dynasty_history:
            lines.extend(["", "Previous generations:"])
            for record in self.state.dynasty_history[-8:]:
                lines.append(
                    f"- Generation {record.get('generation')}: "
                    f"{record.get('name')} (age {record.get('age')}, "
                    f"{record.get('end_reason')}, Year {record.get('end_year')})"
                )
        if self.state.dynasty_heirlooms:
            lines.extend(["", "Heirloom collection:"])
            for heirloom in self.state.dynasty_heirlooms[-8:]:
                lines.append(
                    f"- {heirloom.get('name')} "
                    f"(Generation {heirloom.get('origin_generation')})"
                )
                lines.append(f"  {heirloom.get('effect')}")
        return lines

    def dynasty_heir_menu(self) -> None:
        heirs = self.eligible_dynasty_heirs()
        if not heirs:
            self.set_message("No children have reached young adulthood yet.")
            return
        items = [
            MenuItem(
                label=str(child.get("name", "Heir")),
                value=self.child_dynasty_id(child),
                enabled=True,
                hint=(
                    f"{child.get('personality_trait', 'Curious')} | "
                    f"{child.get('apprentice_path', 'Helper')} | "
                    f"{child.get('starting_class', 'Vanguard')}"
                ),
            )
            for child in heirs
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(
            "Choose Heir",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return
        child = next(
            child
            for child in heirs
            if self.child_dynasty_id(child) == int(choice.value)
        )
        self.vertical_panel_view(
            str(child.get("name", "Heir")),
            self.dynasty_heir_upbringing_lines(child),
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )
        self.designate_dynasty_heir(int(choice.value))

    def dynasty_retirement_menu(self) -> None:
        ready, reason = self.can_retire_current_player()
        if not ready:
            self.set_message(reason)
            return
        heir = self.designated_dynasty_heir() or self.eligible_dynasty_heirs()[0]
        items = [
            MenuItem(
                label="Immediate handoff",
                value=0,
                enabled=True,
                hint="No time jump",
            ),
            MenuItem(
                label="Three-year chapter",
                value=3,
                enabled=True,
                hint="World and heir mature for three years",
            ),
            MenuItem(
                label="Five-year chapter",
                value=5,
                enabled=True,
                hint="A larger generational transition",
            ),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ]
        choice = self.vertical_panel_select(
            f"Retire to {heir.get('name')}",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return
        record = self.dynasty_record_for_current_player(
            "Retirement",
            int(self.state.year),
        )
        heirloom_items = [
            MenuItem(
                label=DYNASTY_HEIRLOOMS[heirloom_type]["name"],
                value=heirloom_type,
                enabled=True,
                hint=DYNASTY_HEIRLOOMS[heirloom_type]["effect"],
            )
            for heirloom_type in self.dynasty_heirloom_options(record)
        ]
        heirloom_items.append(
            MenuItem(label="Back", value=MENU_BACK, enabled=True)
        )
        heirloom_choice = self.vertical_panel_select(
            "Choose a Legacy Heirloom",
            heirloom_items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if heirloom_choice is None or heirloom_choice.value == MENU_BACK:
            return
        self.perform_dynasty_succession(
            self.child_dynasty_id(heir),
            reason="Retirement",
            transition_years=int(choice.value),
            interactive=True,
            heirloom_type=str(heirloom_choice.value),
        )

    def show_dynasty_menu(self) -> None:
        while True:
            ready, retirement_reason = self.can_retire_current_player()
            heir = self.designated_dynasty_heir()
            items = [
                MenuItem(label="Dynasty ledger", value="ledger", enabled=True),
                MenuItem(label="Family tree", value="tree", enabled=True),
                MenuItem(
                    label="Heirloom collection",
                    value="heirlooms",
                    enabled=bool(self.state.dynasty_heirlooms),
                    hint=f"{len(self.state.dynasty_heirlooms)} preserved",
                ),
                MenuItem(
                    label="Choose heir",
                    value="heir",
                    enabled=bool(self.eligible_dynasty_heirs()),
                    hint=(
                        heir.get("name")
                        if heir
                        else f"{len(self.eligible_dynasty_heirs())} eligible"
                    ),
                ),
                MenuItem(
                    label="Retire and continue",
                    value="retire",
                    enabled=ready,
                    hint=retirement_reason,
                ),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(
                "Dynasty",
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "ledger":
                self.vertical_panel_view(
                    "Dynasty Ledger",
                    self.dynasty_ledger_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "tree":
                self.vertical_panel_view(
                    "Family Tree",
                    self.dynasty_family_tree_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "heirlooms":
                lines = ["HEIRLOOM COLLECTION", ""]
                for heirloom in self.state.dynasty_heirlooms:
                    lines.extend(
                        [
                            str(heirloom.get("name", "Heirloom")),
                            f"- Origin: {heirloom.get('origin_name')}, "
                            f"Generation {heirloom.get('origin_generation')}",
                            f"- {heirloom.get('description')}",
                            f"- Effect: {heirloom.get('effect')}",
                            "",
                        ]
                    )
                self.vertical_panel_view(
                    "Heirlooms",
                    lines,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "heir":
                self.dynasty_heir_menu()
            elif choice.value == "retire":
                self.dynasty_retirement_menu()
                return

    def is_dynasty_elder_npc(self, npc: Dict[str, object]) -> bool:
        return bool(
            npc.get("dynasty_elder")
            or str(npc.get("id", "")).startswith("dynasty_elder:")
        )

    def is_dynasty_kin_npc(self, npc: Dict[str, object]) -> bool:
        return bool(
            npc.get("dynasty_kin")
            or str(npc.get("id", "")).startswith("dynasty_kin:")
        )

    def dynasty_kin_npcs(self) -> List[Dict[str, object]]:
        relatives: List[Dict[str, object]] = []
        positions = ((18, 9), (20, 9), (18, 11), (20, 11), (22, 10))
        for index, raw in enumerate(self.state.dynasty_kin):
            if (
                not isinstance(raw, dict)
                or not raw.get("active", True)
                or raw.get("linked_existing_npc")
                or str(raw.get("residence", "")) != "Farmhouse"
            ):
                continue
            relative = raw
            relative["dynasty_kin"] = True
            relative["x"], relative["y"] = positions[index % len(positions)]
            relative["age_years"] = self.dynasty_person_age(relative)
            relative["age_group"] = self.dynasty_person_life_stage(relative)
            relative["relationship"] = int(
                self.state.town_npc_relationships.get(
                    str(relative.get("id", "")),
                    relative.get("relationship", 180),
                )
            )
            relatives.append(relative)
        return relatives

    def dynasty_kin_for_procedural_town(
        self,
        plan: Dict[str, object],
    ) -> List[Dict[str, object]]:
        town_name = str(plan.get("name", ""))
        relatives: List[Dict[str, object]] = []
        for raw in self.state.dynasty_kin:
            if (
                not isinstance(raw, dict)
                or not raw.get("active", True)
                or raw.get("linked_existing_npc")
                or str(raw.get("residence", "")) != town_name
            ):
                continue
            relative = raw
            relative["dynasty_kin"] = True
            relative["age_years"] = self.dynasty_person_age(relative)
            relative["runtime_activity"] = (
                f"going about their work as "
                f"{str(relative.get('occupation', 'a local worker')).lower()}"
            )
            relatives.append(relative)
        return relatives

    def dynasty_kin_dialogue_lines(
        self,
        relative: Dict[str, object],
    ) -> List[str]:
        relation = self.dynasty_relation_for_generation(relative)
        trait = str(relative.get("personality_trait", "Curious"))
        occupation = str(relative.get("occupation", "family work"))
        variants = {
            "Studious": "I still keep notes the way we did when we were young.",
            "Practical": "A family name is useful, but the work still has to be done.",
            "Curious": "There is always another road beyond the one we inherited.",
            "Kind": "The place matters because people can come home to it.",
            "Bold": "I intend to add a story or two of my own to that ledger.",
        }
        return [
            f"{relative.get('name')} greets you as family.",
            "",
            variants.get(
                trait,
                "We grew from the same household, even if our lives took different shapes.",
            ),
            "",
            f"Relation: {relation}",
            (
                f"Age: {self.dynasty_person_age(relative)}"
                if self.aging_and_death_active()
                else f"Life stage: {self.dynasty_person_life_stage(relative)}"
            ),
            f"Work: {occupation}",
            f"Home: {relative.get('residence', 'Farmhouse')}",
        ]

    def dynasty_kin_menu(self, relative: Dict[str, object]) -> None:
        while True:
            relative_id = str(relative.get("id", ""))
            talked_today = (
                self.state.town_npc_last_talk_day.get(relative_id)
                == self.town_npc_day_key()
            )
            choice = self.vertical_panel_select(
                str(relative.get("name", "Relative")),
                [
                    MenuItem(
                        label="Talk",
                        value="talk",
                        enabled=True,
                        hint="Already talked today" if talked_today else "Family conversation",
                    ),
                    MenuItem(
                        label="Ask about their work",
                        value="work",
                        enabled=True,
                    ),
                    MenuItem(
                        label="Recall a family memory",
                        value="memory",
                        enabled=True,
                    ),
                    MenuItem(label="Family tree", value="tree", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "talk":
                if not talked_today:
                    self.state.town_npc_last_talk_day[
                        relative_id
                    ] = self.town_npc_day_key()
                    self.adjust_town_npc_relationship(relative_id, 2)
                    relative["relationship"] = int(
                        self.state.town_npc_relationships.get(
                            relative_id,
                            relative.get("relationship", 180),
                        )
                    )
                self.vertical_panel_view(
                    str(relative.get("name", "Relative")),
                    self.dynasty_kin_dialogue_lines(relative),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "work":
                self.vertical_panel_view(
                    "A Life Beyond the Farm",
                    [
                        f"{relative.get('name')} works as "
                        f"{str(relative.get('occupation', 'a regional specialist')).lower()}.",
                        "",
                        f"Upbringing path: {relative.get('apprentice_path', 'Helper')}",
                        f"Starting training: {relative.get('starting_class', 'Vanguard')}",
                        f"Current home: {relative.get('residence', 'Farmhouse')}",
                        (
                            f"Their household includes "
                            f"{int(relative.get('household_children', 0))} child(ren)."
                            if relative.get("formed_household")
                            else "They have not started a separate household."
                        ),
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "memory":
                generation = int(relative.get("generation", 1)) - 1
                history = next(
                    (
                        record
                        for record in self.state.dynasty_history
                        if int(record.get("generation", 0)) == generation
                    ),
                    {},
                )
                self.vertical_panel_view(
                    "Shared Memory",
                    [
                        f"{relative.get('name')} remembers growing up during "
                        f"{history.get('name', 'the previous head')}'s chapter.",
                        "",
                        f"The family then held {history.get('claims', 0)} claim(s), "
                        f"{history.get('businesses', 0)} business(es), and "
                        f"{history.get('routes', 0)} trade route(s).",
                        "",
                        "The memory is ordinary in its details—and therefore worth keeping.",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "tree":
                self.vertical_panel_view(
                    "Family Tree",
                    self.dynasty_family_tree_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )

    def dynasty_elder_npcs(self) -> List[Dict[str, object]]:
        elders: List[Dict[str, object]] = []
        positions = ((12, 9), (14, 9), (10, 10), (16, 10))
        for index, raw in enumerate(self.state.dynasty_elders):
            if not isinstance(raw, dict) or not raw.get("active", True):
                continue
            elder = raw
            elder["dynasty_elder"] = True
            elder["age_years"] = self.dynasty_person_age(elder)
            elder["x"], elder["y"] = positions[index % len(positions)]
            elder["activity"] = str(
                elder.get(
                    "activity",
                    "keeping the family history and offering practical advice",
                )
            )
            elders.append(elder)
        return elders

    def dynasty_elder_menu(self, elder: Dict[str, object]) -> None:
        while True:
            choice = self.vertical_panel_select(
                str(elder.get("name", "Family Elder")),
                [
                    MenuItem(label="Talk", value="talk", enabled=True),
                    MenuItem(label="Ask about the old days", value="history", enabled=True),
                    MenuItem(label="Dynasty ledger", value="ledger", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "talk":
                self.vertical_panel_view(
                    str(elder.get("name", "Family Elder")),
                    [
                        f"{elder.get('name')} pauses over the household ledger.",
                        "",
                        "“The farm is yours now. That does not mean you have to make "
                        "the same choices I did.”",
                        "",
                        f"Generation: {elder.get('generation', 1)}",
                        f"Former background: {elder.get('background', 'Farmer')}",
                        f"Activity: {elder.get('activity')}",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "history":
                record = next(
                    (
                        entry
                        for entry in self.state.dynasty_history
                        if int(entry.get("generation", 0))
                        == int(elder.get("generation", -1))
                    ),
                    {},
                )
                self.vertical_panel_view(
                    "The Old Days",
                    [
                        f"{elder.get('name')} remembers Generation "
                        f"{elder.get('generation', 1)}.",
                        "",
                        f"Claims held: {record.get('claims', 0)}",
                        f"Businesses founded: {record.get('businesses', 0)}",
                        f"Trade routes established: {record.get('routes', 0)}",
                        f"Deepest mine floor: {record.get('mine_depth', 1)}",
                        f"Spouse: {record.get('spouse_name') or 'none recorded'}",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
            elif choice.value == "ledger":
                self.vertical_panel_view(
                    "Dynasty Ledger",
                    self.dynasty_ledger_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )


__all__ = [
    "DYNASTY_HEALTH_WARNING_AGE",
    "DYNASTY_HEIR_AGE_MONTHS",
    "DYNASTY_RETIREMENT_AGE",
    "DynastyMixin",
]
