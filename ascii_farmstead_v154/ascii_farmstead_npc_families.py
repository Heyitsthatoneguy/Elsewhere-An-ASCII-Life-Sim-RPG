"""Persistent autonomous family lives for authored and procedural NPCs."""

from __future__ import annotations

import copy
import hashlib
import random
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import (
    AUTHORED_TOWN_RESIDENCE_DATA,
    AUTHORED_TOWN_RESIDENCE_ID_BY_NPC,
)
from ascii_farmstead_npc_builder import ProceduralNpcBuilder


NPC_FAMILY_VERSION = 1
FAMILY_CHILD_NAMES = (
    "Ada", "Anya", "Clara", "Daisy", "Elise", "Flora", "Grace", "Iris",
    "Alice", "June", "Nora", "Rose", "Theo", "Arthur", "Caleb", "Evan",
    "Felix", "Henry", "Jonah", "Leo", "Milo", "Owen", "Robin", "Sam",
)


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class NpcFamilyLifeMixin:
    """Give non-player residents persistent courtship, marriage, and children."""

    def _npc_family_seed(self, *parts: object) -> int:
        text = ":".join(str(part) for part in parts)
        return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)

    def _npc_family_rng(self, *parts: object) -> random.Random:
        return random.Random(self._npc_family_seed(self.state.wilderness_seed, *parts))

    def ensure_npc_family_state(self) -> Dict[str, object]:
        raw = getattr(self.state, "npc_family_state", None)
        family = raw if isinstance(raw, dict) else {}
        family.setdefault("version", NPC_FAMILY_VERSION)
        family.setdefault("last_processed_day", 0)
        family.setdefault("profiles", {})
        family.setdefault("households", {})
        family.setdefault("events", [])
        family.setdefault("next_child_id", 1)
        if not isinstance(family["profiles"], dict):
            family["profiles"] = {}
        if not isinstance(family["households"], dict):
            family["households"] = {}
        if not isinstance(family["events"], list):
            family["events"] = []
        self.state.npc_family_state = family
        self._ensure_authored_family_profiles(family)
        return family

    def _authored_age(self, npc: Dict[str, object]) -> int:
        if str(npc.get("id", "")) == "lulu_child" or str(npc.get("role", "")) == "Kid":
            return 9
        return 23 + self._npc_family_seed("authored-age", npc.get("id", "")) % 35

    def _new_authored_profile(self, npc: Dict[str, object]) -> Dict[str, object]:
        npc_id = str(npc.get("id", ""))
        age = self._authored_age(npc)
        residence_id = AUTHORED_TOWN_RESIDENCE_ID_BY_NPC.get(npc_id, "")
        return {
            "npc_id": npc_id,
            "sex": str(npc.get("sex", "Unknown")),
            "age_years": age,
            "life_stage": "Child" if age < 13 else "Teen" if age < 18 else "Adult",
            "last_birthday_year": 0,
            "marital_status": "Single",
            "courtship_partner_id": "",
            "courtship_started_day": 0,
            "engagement_day": 0,
            "npc_spouse_id": "",
            "marriage_day": 0,
            "pregnancy_due_day": 0,
            "parent_ids": [],
            "child_ids": [],
            "household_id": f"authored-household:{npc_id}",
            "family_home_residence_id": residence_id,
            "generation": 1,
        }

    def _ensure_authored_family_profiles(self, family: Dict[str, object]) -> None:
        profiles = family["profiles"]
        households = family["households"]
        valid_npcs = [npc for npc in getattr(self.state, "town_npcs", []) if isinstance(npc, dict)]
        for npc in valid_npcs:
            npc_id = str(npc.get("id", ""))
            if not npc_id:
                continue
            profile = profiles.get(npc_id)
            if not isinstance(profile, dict):
                profile = self._new_authored_profile(npc)
                profiles[npc_id] = profile
            defaults = self._new_authored_profile(npc)
            for key, value in defaults.items():
                profile.setdefault(key, copy.deepcopy(value))
            profile["sex"] = str(npc.get("sex", profile.get("sex", "Unknown")))
            household_id = str(profile.get("household_id", defaults["household_id"]))
            profile["household_id"] = household_id
            household = households.setdefault(household_id, {
                "id": household_id,
                "home_residence_id": str(profile.get("family_home_residence_id", "")),
                "member_ids": [],
                "married_couple_ids": [],
                "capacity": 5,
            })
            members = household.setdefault("member_ids", [])
            if npc_id not in members:
                members.append(npc_id)
            household.setdefault("married_couple_ids", [])
            household.setdefault("capacity", 5)

        # Lulu and Ruth are an existing parent-child household, not an unmarried couple.
        if "lulu_child" in profiles and "mayor_ruth" in profiles:
            lulu = profiles["lulu_child"]
            ruth = profiles["mayor_ruth"]
            if not lulu.get("parent_ids"):
                lulu["parent_ids"] = ["mayor_ruth"]
            if "lulu_child" not in ruth.setdefault("child_ids", []):
                ruth["child_ids"].append("lulu_child")
            self._move_authored_resident_to_household("lulu_child", str(ruth["household_id"]), family)

    def _move_authored_resident_to_household(
        self, npc_id: str, target_id: str, family: Dict[str, object]
    ) -> None:
        profiles = family["profiles"]
        households = family["households"]
        profile = profiles.get(npc_id)
        target = households.get(target_id)
        if not isinstance(profile, dict) or not isinstance(target, dict):
            return
        old_id = str(profile.get("household_id", ""))
        old = households.get(old_id)
        if isinstance(old, dict):
            old["member_ids"] = [value for value in old.get("member_ids", []) if value != npc_id]
        if npc_id not in target.setdefault("member_ids", []):
            target["member_ids"].append(npc_id)
        profile["household_id"] = target_id
        profile["family_home_residence_id"] = str(target.get("home_residence_id", ""))

    def npc_family_profile(self, npc_id: str) -> Dict[str, object]:
        return self.ensure_npc_family_state()["profiles"].get(str(npc_id), {})

    def npc_family_home_residence_id(self, npc_id: str) -> str:
        return str(self.npc_family_profile(npc_id).get("family_home_residence_id", ""))

    def _npc_family_log(
        self, event_type: str, text: str, participants: List[str], realm: str = "town"
    ) -> str:
        family = self.ensure_npc_family_state()
        event = {
            "day": self.absolute_game_day(),
            "date": self.town_npc_day_key(),
            "type": event_type,
            "realm": realm,
            "participants": list(participants),
            "text": str(text),
        }
        family["events"].append(event)
        family["events"] = family["events"][-120:]
        return str(text)

    def _npc_is_player_committed(self, npc_id: str) -> bool:
        return npc_id in {
            str(getattr(self.state, "spouse_npc_id", "") or ""),
            str(getattr(self.state, "engaged_npc_id", "") or ""),
            *[str(value) for value in (getattr(self.state, "dating_npc_ids", []) or [])],
        }

    def _eligible_authored_family_adult(self, npc_id: str, profile: Dict[str, object]) -> bool:
        return bool(
            str(profile.get("sex", "")) in {"Male", "Female"}
            and str(profile.get("life_stage", "")) == "Adult"
            and 20 <= _int(profile.get("age_years"), 30) <= 68
            and str(profile.get("marital_status", "Single")) == "Single"
            and not self._npc_is_player_committed(npc_id)
        )

    def _advance_authored_relationships(self, today: int, family: Dict[str, object]) -> List[str]:
        profiles = family["profiles"]
        messages: List[str] = []
        handled = set()
        for npc_id, profile in list(profiles.items()):
            partner_id = str(profile.get("courtship_partner_id", ""))
            if not partner_id or partner_id not in profiles:
                continue
            pair = tuple(sorted((npc_id, partner_id)))
            if pair in handled:
                continue
            handled.add(pair)
            partner = profiles[partner_id]
            status = str(profile.get("marital_status", "Single"))
            if status == "Courting" and today - _int(profile.get("courtship_started_day")) >= 45:
                profile["marital_status"] = partner["marital_status"] = "Engaged"
                profile["engagement_day"] = partner["engagement_day"] = today
                names = [self.town_npc_name(value) for value in pair]
                messages.append(self._npc_family_log("Engagement", f"{names[0]} and {names[1]} became engaged.", list(pair)))
            elif status == "Engaged" and today - _int(profile.get("engagement_day")) >= 21:
                message = self._marry_authored_pair(pair[0], pair[1], today, family)
                if message:
                    messages.append(message)
        return messages

    def _marry_authored_pair(
        self, first_id: str, second_id: str, today: int, family: Dict[str, object]
    ) -> str:
        profiles = family["profiles"]
        households = family["households"]
        first, second = profiles[first_id], profiles[second_id]
        if {str(first.get("sex")), str(second.get("sex"))} != {"Male", "Female"}:
            return ""
        target_id = str(first.get("household_id", ""))
        target = households.get(target_id, {})
        if len(target.get("member_ids", [])) >= _int(target.get("capacity"), 5):
            target_id = str(second.get("household_id", ""))
            target = households.get(target_id, {})
        if len(target.get("member_ids", [])) >= _int(target.get("capacity"), 5):
            return ""
        self._move_authored_resident_to_household(second_id if target_id == first.get("household_id") else first_id, target_id, family)
        for profile, spouse_id in ((first, second_id), (second, first_id)):
            profile["marital_status"] = "Married"
            profile["npc_spouse_id"] = spouse_id
            profile["marriage_day"] = today
            profile["courtship_partner_id"] = ""
        target["married_couple_ids"] = [first_id, second_id]
        names = (self.town_npc_name(first_id), self.town_npc_name(second_id))
        return self._npc_family_log("Wedding", f"{names[0]} and {names[1]} were married and established a household together.", [first_id, second_id])

    def _start_authored_courtship(self, today: int, family: Dict[str, object]) -> str:
        if today % 14:
            return ""
        profiles = family["profiles"]
        women = sorted(npc_id for npc_id, p in profiles.items() if p.get("sex") == "Female" and self._eligible_authored_family_adult(npc_id, p))
        men = sorted(npc_id for npc_id, p in profiles.items() if p.get("sex") == "Male" and self._eligible_authored_family_adult(npc_id, p))
        pairs = [(woman, man) for woman in women for man in men if profiles[woman].get("household_id") != profiles[man].get("household_id")]
        if not pairs:
            return ""
        rng = self._npc_family_rng("town-courtship", today)
        if rng.random() > 0.65:
            return ""
        first_id, second_id = pairs[rng.randrange(len(pairs))]
        for npc_id, partner_id in ((first_id, second_id), (second_id, first_id)):
            profiles[npc_id]["marital_status"] = "Courting"
            profiles[npc_id]["courtship_partner_id"] = partner_id
            profiles[npc_id]["courtship_started_day"] = today
        names = (self.town_npc_name(first_id), self.town_npc_name(second_id))
        return self._npc_family_log("Courtship", f"{names[0]} and {names[1]} started courting. They still maintain separate homes.", [first_id, second_id])

    def _update_authored_ages(self, family: Dict[str, object]) -> None:
        if not bool(getattr(self.state, "aging_and_death_enabled", True)):
            return
        profiles = family["profiles"]
        npc_by_id = {str(npc.get("id", "")): npc for npc in self.state.town_npcs if isinstance(npc, dict)}
        for npc_id, profile in profiles.items():
            npc = npc_by_id.get(npc_id, {})
            if (
                _int(npc.get("birthday_month"), 0) == self.state.month
                and _int(npc.get("birthday_day"), 0) == self.state.day
                and _int(profile.get("last_birthday_year"), 0) < self.state.year
            ):
                profile["age_years"] = _int(profile.get("age_years"), 18) + 1
                profile["last_birthday_year"] = self.state.year
                age = _int(profile["age_years"])
                profile["life_stage"] = "Child" if age < 13 else "Teen" if age < 18 else "Adult" if age < 65 else "Elder"

    def _make_authored_child(self, mother_id: str, father_id: str, today: int, family: Dict[str, object], adopted: bool = False) -> str:
        profiles, households = family["profiles"], family["households"]
        mother, father = profiles[mother_id], profiles[father_id]
        household_id = str(mother.get("household_id", ""))
        household = households.get(household_id, {})
        if len(household.get("member_ids", [])) >= _int(household.get("capacity"), 5):
            return ""
        number = max(1, _int(family.get("next_child_id"), 1))
        family["next_child_id"] = number + 1
        child_id = f"family:town:{number}"
        rng = self._npc_family_rng("town-child", number, today)
        sex = "Female" if rng.randrange(2) == 0 else "Male"
        given = FAMILY_CHILD_NAMES[(number + rng.randrange(len(FAMILY_CHILD_NAMES))) % len(FAMILY_CHILD_NAMES)]
        mother_npc = next((npc for npc in self.state.town_npcs if npc.get("id") == mother_id), {})
        residence_id = str(mother.get("family_home_residence_id", ""))
        home_label = str(
            AUTHORED_TOWN_RESIDENCE_DATA.get(residence_id, {}).get(
                "label", mother_npc.get("home", "Private Home")
            )
        )
        child = {
            "id": child_id, "name": given, "symbol": "@", "sex": sex,
            "birthday_month": self.state.month, "birthday_day": self.state.day,
            "role": "Kid", "home": home_label,
            "x": _int(mother_npc.get("x"), 42), "y": _int(mother_npc.get("y"), 22),
            "home_x": _int(mother_npc.get("home_x"), 42), "home_y": _int(mother_npc.get("home_y"), 22),
            "district": str(mother_npc.get("district", "Central Park")), "wander_radius": 4,
            "family_generated": True,
        }
        self.state.town_npcs.append(child)
        profiles[child_id] = {
            **self._new_authored_profile(child),
            "age_years": 0, "life_stage": "Child", "parent_ids": [mother_id, father_id],
            "household_id": household_id, "family_home_residence_id": residence_id,
            "generation": max(_int(mother.get("generation"), 1), _int(father.get("generation"), 1)) + 1,
        }
        household.setdefault("member_ids", []).append(child_id)
        for parent in (mother, father):
            if child_id not in parent.setdefault("child_ids", []):
                parent["child_ids"].append(child_id)
        self.normalize_town_npcs()
        kind = "Adoption" if adopted else "Birth"
        verb = "adopted" if adopted else "welcomed"
        return self._npc_family_log(kind, f"{self.town_npc_name(mother_id)} and {self.town_npc_name(father_id)} {verb} {given} into their family.", [mother_id, father_id, child_id])

    def _process_authored_children(self, today: int, family: Dict[str, object]) -> List[str]:
        profiles, households = family["profiles"], family["households"]
        messages: List[str] = []
        handled = set()
        for npc_id, profile in list(profiles.items()):
            spouse_id = str(profile.get("npc_spouse_id", ""))
            if profile.get("marital_status") != "Married" or not spouse_id or spouse_id in handled or spouse_id not in profiles:
                continue
            handled.update((npc_id, spouse_id))
            pair = (profile, profiles[spouse_id])
            female = profile if profile.get("sex") == "Female" else profiles[spouse_id]
            male = profiles[spouse_id] if female is profile else profile
            female_id = npc_id if female is profile else spouse_id
            male_id = spouse_id if female is profile else npc_id
            due = _int(female.get("pregnancy_due_day"), 0)
            if due and today >= due:
                female["pregnancy_due_day"] = 0
                message = self._make_authored_child(female_id, male_id, today, family)
                if message:
                    messages.append(message)
                continue
            household = households.get(str(profile.get("household_id", "")), {})
            room = len(household.get("member_ids", [])) < _int(household.get("capacity"), 5)
            children = len(set(profile.get("child_ids", [])) | set(profiles[spouse_id].get("child_ids", [])))
            if self.state.day != 1 or due or not room or children >= 3:
                continue
            rng = self._npc_family_rng("town-family-growth", today, *sorted((npc_id, spouse_id)))
            female_age = _int(female.get("age_years"), 30)
            if 20 <= female_age <= 43 and rng.random() < 0.07:
                female["pregnancy_due_day"] = today + 270
                messages.append(self._npc_family_log("Pregnancy", f"{self.town_npc_name(female_id)} and {self.town_npc_name(male_id)} are expecting a child.", [female_id, male_id]))
            elif female_age > 43 and rng.random() < 0.025:
                message = self._make_authored_child(female_id, male_id, today, family, adopted=True)
                if message:
                    messages.append(message)
        return messages

    def _initialize_procedural_families(self, population: Dict[str, object]) -> None:
        residents = population.get("residents", {})
        households = population.get("households", {})
        for resident in residents.values():
            resident.setdefault("marital_status", "Single")
            resident.setdefault("courtship_partner_id", "")
            resident.setdefault("courtship_started_day", 0)
            resident.setdefault("engagement_day", 0)
            resident.setdefault("npc_spouse_id", "")
            resident.setdefault("marriage_day", 0)
            resident.setdefault("pregnancy_due_day", 0)
            resident.setdefault("parent_ids", list(resident.get("guardian_ids", [])))
            resident.setdefault("child_ids", list(resident.get("dependent_ids", [])))
            resident.setdefault("generation", 1)
        for household in households.values():
            household.setdefault("married_couple_ids", [])
            members = [residents[value] for value in household.get("member_ids", []) if value in residents]
            young = [value for value in members if value.get("age_group") in {"Child", "Teen"}]
            women = [value for value in members if value.get("sex") == "Female" and value.get("age_group") == "Adult"]
            men = [value for value in members if value.get("sex") == "Male" and value.get("age_group") == "Adult"]
            if young and women and men and not household.get("married_couple_ids"):
                wife, husband = women[0], men[0]
                household["married_couple_ids"] = [wife["id"], husband["id"]]
                for resident, spouse in ((wife, husband), (husband, wife)):
                    resident["marital_status"] = "Married"
                    resident["npc_spouse_id"] = spouse["id"]
                    resident["household_role"] = "Spouse" if resident is not members[0] else "Head"
                    resident["child_ids"] = [child["id"] for child in young]
                for child in young:
                    child["parent_ids"] = [wife["id"], husband["id"]]
                    child["guardian_ids"] = [wife["id"], husband["id"]]

    def _process_procedural_population(self, population: Dict[str, object], today: int) -> List[str]:
        self._initialize_procedural_families(population)
        residents = population.get("residents", {})
        households = population.get("households", {})
        messages: List[str] = []
        settlement = str(population.get("settlement_name", "a wilderness settlement"))
        builder = ProceduralNpcBuilder()
        plan = self.wilderness_settlement_plan(
            _int(population.get("chunk_x")), _int(population.get("chunk_y"))
        ) if hasattr(self, "wilderness_settlement_plan") else None
        if bool(getattr(self.state, "aging_and_death_enabled", True)):
            for resident in residents.values():
                if (
                    _int(resident.get("birthday_month"), 0) == self.state.month
                    and _int(resident.get("birthday_day"), 0) == self.state.day
                    and _int(resident.get("last_birthday_year"), 0) < self.state.year
                ):
                    resident["age_years"] = _int(resident.get("age_years"), 18) + 1
                    resident["last_birthday_year"] = self.state.year
                    age = _int(resident["age_years"])
                    resident["age_group"] = "Child" if age < 13 else "Teen" if age < 18 else "Adult" if age < 65 else "Elder"
                    resident["romanceable"] = resident["age_group"] in {"Adult", "Elder"}
        # Advance established relationships. Couples retain separate homes until this wedding step.
        handled = set()
        for resident_id, resident in list(residents.items()):
            partner_id = str(resident.get("courtship_partner_id", ""))
            if not partner_id or partner_id not in residents:
                continue
            pair = tuple(sorted((resident_id, partner_id)))
            if pair in handled:
                continue
            handled.add(pair)
            partner = residents[partner_id]
            status = str(resident.get("marital_status", "Single"))
            if status == "Courting" and today - _int(resident.get("courtship_started_day")) >= 45:
                resident["marital_status"] = partner["marital_status"] = "Engaged"
                resident["engagement_day"] = partner["engagement_day"] = today
                messages.append(self._npc_family_log("Engagement", f"{resident['name']} and {partner['name']} became engaged in {settlement}.", list(pair), str(population.get("id", ""))))
            elif status == "Engaged" and today - _int(resident.get("engagement_day")) >= 21:
                target_id = str(resident.get("household_id", ""))
                target = households.get(target_id, {})
                mover, stay = partner, resident
                if len(target.get("member_ids", [])) >= _int(target.get("capacity"), 1):
                    target_id = str(partner.get("household_id", ""))
                    target = households.get(target_id, {})
                    mover, stay = resident, partner
                if len(target.get("member_ids", [])) < _int(target.get("capacity"), 1):
                    old = households.get(str(mover.get("household_id", "")), {})
                    old["member_ids"] = [value for value in old.get("member_ids", []) if value != mover["id"]]
                    target.setdefault("member_ids", []).append(mover["id"])
                    mover["household_id"] = target_id
                    mover["home_building_id"] = stay["home_building_id"]
                    if isinstance(plan, dict):
                        mover["schedule"] = builder.resident_schedule(
                            plan, mover, builder.completed_building_map(plan)
                        )
                    for person, spouse in ((resident, partner), (partner, resident)):
                        person["marital_status"] = "Married"
                        person["npc_spouse_id"] = spouse["id"]
                        person["courtship_partner_id"] = ""
                        person["marriage_day"] = today
                    target["married_couple_ids"] = [resident_id, partner_id]
                    messages.append(self._npc_family_log("Wedding", f"{resident['name']} and {partner['name']} married and established a shared home in {settlement}.", list(pair), str(population.get("id", ""))))

        if self.state.day == 1:
            women = [value for value in residents.values() if value.get("sex") == "Female" and value.get("age_group") == "Adult" and value.get("marital_status") == "Single" and not self._npc_is_player_committed(str(value.get("id", "")))]
            men = [value for value in residents.values() if value.get("sex") == "Male" and value.get("age_group") == "Adult" and value.get("marital_status") == "Single" and not self._npc_is_player_committed(str(value.get("id", "")))]
            pairs = [(woman, man) for woman in women for man in men if woman.get("household_id") != man.get("household_id")]
            rng = self._npc_family_rng("procedural-courtship", population.get("id", ""), today)
            if pairs and rng.random() < 0.35:
                woman, man = pairs[rng.randrange(len(pairs))]
                for person, partner in ((woman, man), (man, woman)):
                    person["marital_status"] = "Courting"
                    person["courtship_partner_id"] = partner["id"]
                    person["courtship_started_day"] = today
                messages.append(self._npc_family_log("Courtship", f"{woman['name']} and {man['name']} began courting in {settlement}; each kept their own home.", [woman["id"], man["id"]], str(population.get("id", ""))))

        # Births and adoptions are capacity bounded and only occur in married households.
        for household in households.values():
            couple = [value for value in household.get("married_couple_ids", []) if value in residents]
            if len(couple) != 2 or len(household.get("member_ids", [])) >= _int(household.get("capacity"), 1):
                continue
            people = [residents[value] for value in couple]
            female = next((value for value in people if value.get("sex") == "Female"), None)
            male = next((value for value in people if value.get("sex") == "Male"), None)
            if female is None or male is None:
                continue
            due = _int(female.get("pregnancy_due_day"), 0)
            adopted = False
            if not due and self.state.day == 1:
                rng = self._npc_family_rng("procedural-family-growth", population.get("id", ""), household.get("id", ""), today)
                child_count = len(set(female.get("child_ids", [])) | set(male.get("child_ids", [])))
                age = _int(female.get("age_years"), 30)
                if child_count < 3 and 20 <= age <= 43 and rng.random() < 0.06:
                    female["pregnancy_due_day"] = today + 270
                    messages.append(self._npc_family_log("Pregnancy", f"{female['name']} and {male['name']} are expecting a child in {settlement}.", [female["id"], male["id"]], str(population.get("id", ""))))
                elif child_count < 3 and age > 43 and rng.random() < 0.025:
                    due, adopted = today, True
            if (due and today >= due) or adopted:
                if not isinstance(plan, dict):
                    continue
                buildings = builder.completed_building_map(plan)
                home = buildings.get(str(household.get("home_building_id", "")))
                if not home:
                    continue
                serial = _int(population.get("next_family_resident_id"), 1)
                population["next_family_resident_id"] = serial + 1
                origin = f"family-child:{serial}"
                child = builder.create_resident(plan, origin, str(household["id"]), home, str(household.get("surname", "")), "Student", "student", None, age_group="Child")
                child["age_years"] = 0
                child["sex"] = "Female" if self._npc_family_rng("procedural-child-sex", child["id"]).randrange(2) == 0 else "Male"
                child["parent_ids"] = [female["id"], male["id"]]
                child["guardian_ids"] = [female["id"], male["id"]]
                child["generation"] = max(_int(female.get("generation"), 1), _int(male.get("generation"), 1)) + 1
                child["schedule"] = builder.resident_schedule(plan, child, buildings)
                builder.ensure_unique_resident_name(child, residents, plan, origin)
                residents[child["id"]] = child
                household.setdefault("member_ids", []).append(child["id"])
                female["pregnancy_due_day"] = 0
                for parent in (female, male):
                    parent.setdefault("child_ids", []).append(child["id"])
                    parent.setdefault("dependent_ids", []).append(child["id"])
                kind, verb = ("Adoption", "adopted") if adopted else ("Birth", "welcomed")
                messages.append(self._npc_family_log(kind, f"{female['name']} and {male['name']} {verb} {child['name']} into their family in {settlement}.", [female["id"], male["id"], child["id"]], str(population.get("id", ""))))
        population["family_last_processed_day"] = today
        return messages

    def process_npc_family_life_overnight(self) -> str:
        family = self.ensure_npc_family_state()
        today = self.absolute_game_day()
        if _int(family.get("last_processed_day"), 0) >= today:
            return ""
        self._update_authored_ages(family)
        messages = self._advance_authored_relationships(today, family)
        started = self._start_authored_courtship(today, family)
        if started:
            messages.append(started)
        messages.extend(self._process_authored_children(today, family))
        for population in self.ensure_procedural_settlement_populations().values():
            if _int(population.get("family_last_processed_day"), 0) < today:
                messages.extend(self._process_procedural_population(population, today))
        family["last_processed_day"] = today
        return f" Town life: {messages[-1]}" if messages else ""

    def npc_family_status_lines(self, npc_id: str) -> List[str]:
        profile = self.npc_family_profile(npc_id)
        if not profile:
            return []
        status = str(profile.get("marital_status", "Single"))
        spouse_id = str(profile.get("npc_spouse_id", ""))
        partner_id = str(profile.get("courtship_partner_id", ""))
        lines = [f"Family life: {status}"]
        if spouse_id:
            lines.append(f"Spouse: {self.town_npc_name(spouse_id)}")
        elif partner_id:
            lines.append(f"{status} with: {self.town_npc_name(partner_id)}")
            if status in {"Courting", "Engaged"}:
                lines.append("Household: separate homes until marriage")
        children = [self.town_npc_name(value) for value in profile.get("child_ids", [])]
        if children:
            lines.append(f"Children: {', '.join(children)}")
        return lines

    def npc_family_dialogue_line(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        profile = self.npc_family_profile(npc_id)
        status = str(profile.get("marital_status", npc.get("marital_status", "Single")))
        spouse_id = str(profile.get("npc_spouse_id", npc.get("npc_spouse_id", "")))
        partner_id = str(profile.get("courtship_partner_id", npc.get("courtship_partner_id", "")))
        child_ids = list(profile.get("child_ids", npc.get("child_ids", [])) or [])
        if spouse_id:
            return f'"{self.town_npc_name(spouse_id)} and I have been settling into married life together."'
        if status == "Engaged" and partner_id:
            return f'"{self.town_npc_name(partner_id)} and I are planning our wedding, but we still keep separate homes until then."'
        if status == "Courting" and partner_id:
            return f'"I have been spending more time with {self.town_npc_name(partner_id)}. We are taking things slowly and still live separately."'
        if child_ids:
            return '"Family life has a way of reorganizing every ordinary day."'
        if profile.get("parent_ids"):
            return '"Home is where my family expects me back at the end of the day."'
        return ""

    def npc_family_overview_lines(self) -> List[str]:
        family = self.ensure_npc_family_state()
        profiles = family["profiles"]
        lines = [
            "Residents form opposite-sex couples over time. Courtship and engagement do not merge homes; only marriage establishes a shared household.",
            "",
            "Starting town households:",
        ]
        shown = set()
        for npc_id, profile in sorted(profiles.items(), key=lambda item: self.town_npc_name(item[0])):
            status = str(profile.get("marital_status", "Single"))
            partner = str(profile.get("npc_spouse_id", "") or profile.get("courtship_partner_id", ""))
            pair = tuple(sorted((npc_id, partner))) if partner else (npc_id,)
            if pair in shown or (status == "Single" and not profile.get("child_ids") and not profile.get("parent_ids")):
                continue
            shown.add(pair)
            text = f"- {self.town_npc_name(npc_id)}: {status}"
            if partner:
                text += f" with {self.town_npc_name(partner)}"
            if profile.get("child_ids"):
                text += f"; {len(profile['child_ids'])} child(ren)"
            lines.append(text)
        populations = list(self.ensure_procedural_settlement_populations().values())
        if populations:
            lines.extend(["", "Wilderness settlements:"])
            for population in sorted(populations, key=lambda value: str(value.get("settlement_name", ""))):
                residents = list(population.get("residents", {}).values())
                married = sum(1 for resident in residents if resident.get("marital_status") == "Married") // 2
                courting = sum(1 for resident in residents if resident.get("marital_status") in {"Courting", "Engaged"}) // 2
                children = sum(1 for resident in residents if resident.get("age_group") in {"Child", "Teen"})
                lines.append(f"- {population.get('settlement_name', 'Settlement')}: {married} married household(s), {courting} developing relationship(s), {children} young resident(s)")
        events = list(family.get("events", []))[-8:]
        lines.extend(["", "Recent family news:"])
        lines.extend(f"- {event.get('text', '')}" for event in reversed(events))
        if not events:
            lines.append("- No recent family events.")
        return lines


__all__ = ["NpcFamilyLifeMixin"]
