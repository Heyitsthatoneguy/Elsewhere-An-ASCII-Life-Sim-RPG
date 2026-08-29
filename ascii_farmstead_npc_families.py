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
from ascii_farmstead_helpers import kinship_term, pronouns_for_sex, quantity_agreement
from ascii_farmstead_npc_builder import (
    FEMALE_GIVEN_NAMES,
    MALE_GIVEN_NAMES,
    SURNAMES,
    ProceduralNpcBuilder,
)


NPC_FAMILY_VERSION = 3
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

    def _family_generated_name(self, sex: str, surname: str, *seed_parts: object) -> str:
        pool = MALE_GIVEN_NAMES if str(sex) == "Male" else FEMALE_GIVEN_NAMES
        seed = self._npc_family_seed("lineage-name", *seed_parts)
        given = str(pool[seed % len(pool)]) if pool else ("Arthur" if sex == "Male" else "Alice")
        clean_surname = str(surname or "").strip()
        if not clean_surname:
            clean_surname = str(SURNAMES[(seed // 17) % len(SURNAMES)]) if SURNAMES else "Hart"
        return f"{given} {clean_surname}".strip()

    def _family_surname_for_actor(self, actor: Dict[str, object], actor_id: str) -> str:
        name_parts = str(actor.get("name", "")).strip().split()
        if len(name_parts) > 1:
            return name_parts[-1]
        seed = self._npc_family_seed("lineage-surname", actor_id)
        return str(SURNAMES[seed % len(SURNAMES)]) if SURNAMES else "Hart"

    def _family_deceased_for_age(self, age: int, *seed_parts: object) -> bool:
        age = max(0, int(age))
        if age >= 99:
            return True
        chance = 0.01 if age < 60 else min(0.97, 0.03 + (age - 60) * 0.035)
        roll = (self._npc_family_seed("lineage-mortality", *seed_parts) % 10000) / 10000.0
        return roll < chance

    def _family_generated_role(self, person_id: str, age: int) -> str:
        if int(age) >= 66:
            return "Retiree"
        roles = (
            "Gardener", "Carpenter", "Cook", "Tailor", "Fisher", "Miner",
            "Courier", "Teacher", "Shop Assistant", "Rancher", "Clerk",
        )
        return roles[self._npc_family_seed("lineage-role", person_id) % len(roles)]

    def _family_generated_schedule(self, person_id: str) -> Dict[str, object]:
        seed = self._npc_family_seed("lineage-schedule", person_id)
        public = (
            (43, 24), (48, 22), (35, 25), (52, 28), (39, 18),
            (45, 30), (56, 23), (31, 21),
        )
        morning = public[seed % len(public)]
        midday = public[(seed // 7 + 3) % len(public)]
        evening = public[(seed // 29 + 5) % len(public)]
        return {
            "morning": morning,
            "midday": midday,
            "afternoon": midday,
            "evening": evening,
            "rain": {"inside": "Town Inn"},
        }

    def _new_lineage_profile(
        self,
        person_id: str,
        name: str,
        sex: str,
        age: int,
        *,
        realm: str,
        parent_ids: Optional[List[str]] = None,
        child_ids: Optional[List[str]] = None,
        household_id: str = "",
        spouse_id: str = "",
        deceased: Optional[bool] = None,
        lineage_horizon: bool = False,
        anchor: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        age = max(0, int(age))
        dead = self._family_deceased_for_age(age, person_id) if deceased is None else bool(deceased)
        if lineage_horizon and deceased is None:
            # The finite edge of the recorded tree represents older archival
            # generations. A small number remain alive as true grandparents;
            # most are named deceased records instead of another crowd of
            # invisible or homeless NPCs.
            dead = bool(
                dead
                or self._npc_family_seed("lineage-horizon", person_id) % 100 < 78
            )
        stage = "Child" if age < 13 else "Teen" if age < 18 else "Adult" if age < 65 else "Elder"
        seed = self._npc_family_seed("lineage-person", person_id)
        anchor = anchor if isinstance(anchor, dict) else {}
        home_x = int(anchor.get("home_x", anchor.get("x", 42)) or 42)
        home_y = int(anchor.get("home_y", anchor.get("y", 22)) or 22)
        role = self._family_generated_role(person_id, age)
        profile = {
            "id": str(person_id),
            "npc_id": str(person_id),
            "name": str(name),
            "sex": str(sex),
            "age_years": age,
            "age_group": stage,
            "life_stage": stage,
            "birth_year": int(self.state.year) - age,
            "birthday_month": 1 + seed % 12,
            "birthday_day": 1 + (seed // 13) % 28,
            "last_birthday_year": 0,
            "role": role,
            "occupation": role,
            "marital_status": "Married" if spouse_id else "Single",
            "npc_spouse_id": str(spouse_id),
            "courtship_partner_id": "",
            "courtship_started_day": 0,
            "engagement_day": 0,
            "marriage_day": 0,
            "pregnancy_due_day": 0,
            "parent_ids": list(parent_ids or []),
            "child_ids": list(child_ids or []),
            "household_id": str(household_id or f"family-household:{person_id}"),
            "family_home_residence_id": "",
            "generation": 0,
            "deceased": dead,
            "death_year": int(self.state.year) - max(0, seed % 12) if dead else 0,
            "family_generated": True,
            "lineage_realm": str(realm),
            "lineage_horizon": bool(lineage_horizon),
            # A family tree is not a housing permit.  Generated parents,
            # siblings, cousins, and grandparents live elsewhere in the
            # region and visit; only the authored cast permanently occupies
            # Elsewhere's finite homes.
            "residence_scope": "Regional",
            "romanceable": bool(not dead and stage in {"Adult", "Elder"} and not spouse_id),
            "home": str(anchor.get("home", "Private Home") or "Private Home"),
            "home_name": str(anchor.get("home_name", anchor.get("home", "Private Home")) or "Private Home"),
            "origin": str(anchor.get("origin", "Elsewhere") or "Elsewhere"),
            "district": str(anchor.get("district", "Central Park") or "Central Park"),
            "home_x": home_x,
            "home_y": home_y,
            "x": home_x,
            "y": home_y,
            "wander_radius": 5,
            "schedule": self._family_generated_schedule(person_id),
            "personality_traits": [
                ("Practical", "Warm", "Reserved", "Curious", "Patient", "Blunt")[seed % 6],
                ("Steady", "Sociable", "Private", "Restless", "Generous", "Wry")[(seed // 11) % 6],
            ],
            "goal": "Keep family ties alive without surrendering an independent life.",
        }
        profile["personality"] = ", ".join(profile["personality_traits"])
        return profile

    def _link_family_parent_child(
        self, profiles: Dict[str, Dict[str, object]], parent_id: str, child_id: str
    ) -> None:
        parent = profiles.get(str(parent_id))
        child = profiles.get(str(child_id))
        if not isinstance(parent, dict) or not isinstance(child, dict):
            return
        if str(child_id) not in parent.setdefault("child_ids", []):
            parent["child_ids"].append(str(child_id))
        if str(parent_id) not in child.setdefault("parent_ids", []):
            child["parent_ids"].append(str(parent_id))
        child["parent_ids"] = list(dict.fromkeys(str(value) for value in child["parent_ids"]))[:2]

    def _ensure_lineage_parent_pair(
        self,
        profiles: Dict[str, Dict[str, object]],
        child: Dict[str, object],
        child_id: str,
        *,
        realm: str,
        surname: str,
        horizon: bool = False,
    ) -> List[str]:
        existing = [str(value) for value in child.get("parent_ids", []) or [] if str(value)]
        for existing_id in existing:
            if isinstance(profiles.get(existing_id), dict):
                continue
            source = None
            if hasattr(self, "procedural_resident_by_id"):
                source = self.procedural_resident_by_id(existing_id)
            if source is None:
                source = next(
                    (
                        value for value in getattr(self.state, "town_npcs", []) or []
                        if isinstance(value, dict) and str(value.get("id", "")) == existing_id
                    ),
                    None,
                )
            if isinstance(source, dict):
                source_age = _int(source.get("age_years"), _int(child.get("age_years"), 25) + 25)
                profiles[existing_id] = {
                    "id": existing_id, "npc_id": existing_id,
                    "name": str(source.get("name", existing_id)),
                    "sex": str(source.get("sex", "Unknown")),
                    "age_years": source_age,
                    "age_group": str(source.get("age_group", "Adult")),
                    "life_stage": str(source.get("age_group", "Adult")),
                    "parent_ids": list(source.get("parent_ids", []) or []),
                    "child_ids": list(source.get("child_ids", []) or []),
                    "marital_status": str(source.get("marital_status", "Single")),
                    "npc_spouse_id": str(source.get("npc_spouse_id", "")),
                    "household_id": str(source.get("household_id", f"family-household:{existing_id}")),
                    "lineage_realm": str(realm),
                }
        sexes = {
            str(profiles[value].get("sex", "")): value
            for value in existing if isinstance(profiles.get(value), dict)
        }
        child_age = _int(child.get("age_years"), 25)
        parent_ids: List[str] = list(existing)
        for sex, suffix in (("Female", "mother"), ("Male", "father")):
            if sex in sexes:
                continue
            parent_id = f"family:{realm}:{child_id}:{suffix}"
            parent_age = child_age + 20 + self._npc_family_seed("parent-age", child_id, suffix) % 15
            parent_name = self._family_generated_name(sex, surname, child_id, suffix)
            if not isinstance(profiles.get(parent_id), dict):
                profiles[parent_id] = self._new_lineage_profile(
                    parent_id, parent_name, sex, parent_age,
                    realm=realm, child_ids=[child_id], lineage_horizon=horizon,
                    anchor=child,
                )
            parent_ids.append(parent_id)
            sexes[sex] = parent_id
        parent_ids = list(dict.fromkeys(parent_ids))[:2]
        child["parent_ids"] = parent_ids
        for parent_id in parent_ids:
            self._link_family_parent_child(profiles, parent_id, child_id)
        if len(parent_ids) == 2:
            first, second = profiles.get(parent_ids[0]), profiles.get(parent_ids[1])
            if isinstance(first, dict) and isinstance(second, dict):
                first["npc_spouse_id"] = parent_ids[1]
                second["npc_spouse_id"] = parent_ids[0]
                first["romanceable"] = second["romanceable"] = False
                shared_household = f"family-household:{child_id}:parents"
                first["household_id"] = second["household_id"] = shared_household
                if not first.get("deceased") and not second.get("deceased"):
                    first["marital_status"] = second["marital_status"] = "Married"
                elif first.get("deceased") and second.get("deceased"):
                    first["marital_status"] = second["marital_status"] = "Deceased"
                else:
                    living, departed = (second, first) if first.get("deceased") else (first, second)
                    living["marital_status"] = "Widowed"
                    living["romanceable"] = str(living.get("age_group", "")) in {"Adult", "Elder"}
                    departed["marital_status"] = "Deceased"
        return parent_ids

    def _ensure_authored_ancestry(
        self, family: Dict[str, object], roots: List[Dict[str, object]]
    ) -> None:
        profiles: Dict[str, Dict[str, object]] = family["profiles"]
        changed = False
        for actor in roots:
            actor_id = str(actor.get("id", ""))
            profile = profiles.get(actor_id)
            if not actor_id or not isinstance(profile, dict) or profile.get("ancestry_initialized"):
                continue
            changed = True
            profile.setdefault("id", actor_id)
            profile.setdefault("name", str(actor.get("name", actor_id)))
            profile.setdefault("age_group", str(profile.get("life_stage", "Adult")))
            profile["origin"] = str(actor.get("origin", "Elsewhere") or "Elsewhere")
            profile["home"] = str(actor.get("home", "Private Home") or "Private Home")
            profile["home_x"] = int(actor.get("home_x", actor.get("x", 42)) or 42)
            profile["home_y"] = int(actor.get("home_y", actor.get("y", 22)) or 22)
            surname = self._family_surname_for_actor(actor, actor_id)
            parent_ids = self._ensure_lineage_parent_pair(
                profiles, profile, actor_id, realm="town", surname=surname,
            )
            # Parents themselves receive a recorded generation. Their parents
            # form the practical edge of the ledger; living grandparents still
            # enter the world, while earlier ancestry is explicitly archival.
            for parent_id in parent_ids:
                parent = profiles.get(parent_id)
                if not isinstance(parent, dict) or not parent.get("family_generated"):
                    continue
                parent_surname = self._family_surname_for_actor(parent, parent_id)
                self._ensure_lineage_parent_pair(
                    profiles, parent, parent_id, realm="town",
                    surname=parent_surname, horizon=True,
                )

            rng = self._npc_family_rng("extended-family", actor_id)
            if parent_ids and rng.random() < 0.42:
                sibling_id = f"family:town:{actor_id}:sibling"
                if sibling_id not in profiles:
                    sibling_sex = "Female" if rng.random() < 0.5 else "Male"
                    sibling_age = max(18, _int(profile.get("age_years"), 25) + rng.randint(-6, 6))
                    profiles[sibling_id] = self._new_lineage_profile(
                        sibling_id,
                        self._family_generated_name(sibling_sex, surname, actor_id, "sibling"),
                        sibling_sex, sibling_age, realm="town", parent_ids=list(parent_ids),
                        anchor=actor,
                    )
                    for parent_id in parent_ids:
                        self._link_family_parent_child(profiles, parent_id, sibling_id)
                sibling = profiles[sibling_id]
                if rng.random() < 0.48 and _int(sibling.get("age_years"), 0) >= 22:
                    child_id = f"family:town:{actor_id}:niece-nephew"
                    co_id = f"family:town:{actor_id}:sibling-partner"
                    if co_id not in profiles:
                        co_sex = "Male" if sibling.get("sex") == "Female" else "Female"
                        profiles[co_id] = self._new_lineage_profile(
                            co_id,
                            self._family_generated_name(co_sex, "", actor_id, "sibling-partner"),
                            co_sex, max(20, _int(sibling.get("age_years"), 25) + rng.randint(-4, 4)),
                            realm="town", spouse_id=sibling_id, anchor=actor,
                        )
                        self._ensure_lineage_parent_pair(
                            profiles, profiles[co_id], co_id, realm="town",
                            surname=self._family_surname_for_actor(profiles[co_id], co_id),
                            horizon=True,
                        )
                        sibling["marital_status"] = "Married"
                        sibling["npc_spouse_id"] = co_id
                        sibling["romanceable"] = False
                    if child_id not in profiles:
                        child_sex = "Female" if rng.random() < 0.5 else "Male"
                        child_age = max(0, min(17, _int(sibling.get("age_years"), 25) - 20 - rng.randrange(8)))
                        profiles[child_id] = self._new_lineage_profile(
                            child_id,
                            self._family_generated_name(child_sex, surname, actor_id, "niece-nephew"),
                            child_sex, child_age, realm="town",
                            parent_ids=[sibling_id, co_id], anchor=actor,
                        )
                        self._link_family_parent_child(profiles, sibling_id, child_id)
                        self._link_family_parent_child(profiles, co_id, child_id)

            # Some parents have siblings of their own, which creates genuine
            # aunts/uncles and cousins without assigning children to everyone.
            if parent_ids and rng.random() < 0.34:
                parent_id = parent_ids[0]
                parent = profiles.get(parent_id, {})
                grandparent_ids = list(parent.get("parent_ids", []) or [])
                if grandparent_ids:
                    relative_id = f"family:town:{actor_id}:aunt-uncle"
                    relative_sex = "Female" if rng.random() < 0.5 else "Male"
                    relative_age = max(35, _int(parent.get("age_years"), 50) + rng.randint(-8, 8))
                    if relative_id not in profiles:
                        profiles[relative_id] = self._new_lineage_profile(
                            relative_id,
                            self._family_generated_name(relative_sex, surname, actor_id, "aunt-uncle"),
                            relative_sex, relative_age, realm="town",
                            parent_ids=grandparent_ids, anchor=actor,
                        )
                        for grandparent_id in grandparent_ids:
                            self._link_family_parent_child(profiles, grandparent_id, relative_id)
                    if rng.random() < 0.55:
                        cousin_id = f"family:town:{actor_id}:cousin"
                        if cousin_id not in profiles:
                            cousin_sex = "Female" if rng.random() < 0.5 else "Male"
                            cousin_age = max(18, min(50, relative_age - 20 - rng.randrange(10)))
                            co_parent_id = f"family:town:{actor_id}:aunt-uncle-partner"
                            if co_parent_id not in profiles:
                                co_parent_sex = "Male" if relative_sex == "Female" else "Female"
                                profiles[co_parent_id] = self._new_lineage_profile(
                                    co_parent_id,
                                    self._family_generated_name(co_parent_sex, "", actor_id, "aunt-uncle-partner"),
                                    co_parent_sex, max(32, relative_age + rng.randint(-5, 5)),
                                    realm="town", spouse_id=relative_id, anchor=actor,
                                )
                                self._ensure_lineage_parent_pair(
                                    profiles, profiles[co_parent_id], co_parent_id,
                                    realm="town",
                                    surname=self._family_surname_for_actor(profiles[co_parent_id], co_parent_id),
                                    horizon=True,
                                )
                                profiles[relative_id]["marital_status"] = "Married"
                                profiles[relative_id]["npc_spouse_id"] = co_parent_id
                                profiles[relative_id]["romanceable"] = False
                            profiles[cousin_id] = self._new_lineage_profile(
                                cousin_id,
                                self._family_generated_name(cousin_sex, surname, actor_id, "cousin"),
                                cousin_sex, cousin_age, realm="town",
                                parent_ids=[relative_id, co_parent_id], anchor=actor,
                            )
                            self._link_family_parent_child(profiles, relative_id, cousin_id)
                            self._link_family_parent_child(profiles, co_parent_id, cousin_id)
            profile["ancestry_initialized"] = True
        family["version"] = NPC_FAMILY_VERSION
        sync_token = f"{NPC_FAMILY_VERSION}:{len(profiles)}"
        if changed or str(family.get("lineage_sync_token", "")) != sync_token:
            self._sync_living_authored_family_people(family)
            family["lineage_sync_token"] = sync_token

    def _sync_living_authored_family_people(self, family: Dict[str, object]) -> None:
        households = family.setdefault("households", {})
        # Migrate saves produced by the old lineage pass.  It promoted dozens
        # of generated relatives into the starting village without assigning
        # real bedrooms or homes, producing crowds of 50-70 residents.
        self.state.town_npcs = [
            npc for npc in (getattr(self.state, "town_npcs", []) or [])
            if not (isinstance(npc, dict) and npc.get("family_generated"))
        ]
        for profile in family.get("profiles", {}).values():
            if (
                isinstance(profile, dict)
                and profile.get("family_generated")
                and str(profile.get("lineage_realm", "")) == "town"
            ):
                profile["residence_scope"] = "Regional"
                profile["origin"] = str(profile.get("origin") or "Elsewhere")
                profile["origin_name"] = str(profile.get("origin") or "Elsewhere")
        existing = {
            str(npc.get("id", "")): npc
            for npc in getattr(self.state, "town_npcs", []) or []
            if isinstance(npc, dict)
        }
        for person_id, profile in family.get("profiles", {}).items():
            if (
                not isinstance(profile, dict)
                or not profile.get("family_generated")
                or str(profile.get("lineage_realm", "")) != "town"
                or bool(profile.get("deceased", False))
            ):
                continue
            if str(profile.get("residence_scope", "Elsewhere")) != "Elsewhere":
                world_profiles = getattr(self.state, "world_npc_profiles", None)
                if isinstance(world_profiles, dict):
                    regional = copy.deepcopy(profile)
                    regional["world_npc_profile"] = True
                    regional["family_regional"] = True
                    regional["origin"] = str(regional.get("origin", "the regional roads"))
                    world_profiles.setdefault(str(person_id), regional)
                continue
            actor = existing.get(str(person_id))
            if actor is None:
                actor = copy.deepcopy(profile)
                self.state.town_npcs.append(actor)
                existing[str(person_id)] = actor
            else:
                for key in (
                    "name", "sex", "age_years", "age_group", "life_stage", "role",
                    "marital_status", "npc_spouse_id", "parent_ids", "child_ids",
                    "household_id", "deceased", "romanceable", "family_generated",
                    "lineage_realm", "personality", "personality_traits", "schedule",
                ):
                    if key in profile:
                        actor[key] = copy.deepcopy(profile[key])
            household_id = str(profile.get("household_id", f"family-household:{person_id}"))
            household = households.setdefault(household_id, {
                "id": household_id,
                "home_residence_id": "",
                "member_ids": [],
                "married_couple_ids": [],
                "capacity": 6,
            })
            if str(person_id) not in household.setdefault("member_ids", []):
                household["member_ids"].append(str(person_id))
            spouse_id = str(profile.get("npc_spouse_id", "") or "")
            if spouse_id and spouse_id not in household["member_ids"]:
                household["member_ids"].append(spouse_id)
            if spouse_id:
                household["married_couple_ids"] = [str(person_id), spouse_id]

    def family_regional_visitors_today(self) -> List[Dict[str, object]]:
        family = self.ensure_npc_family_state()
        world_profiles = getattr(self.state, "world_npc_profiles", {})
        day_number = self.absolute_game_day() if hasattr(self, "absolute_game_day") else 0
        candidates = [
            profile for profile in family.get("profiles", {}).values()
            if isinstance(profile, dict)
            and profile.get("family_generated")
            and not profile.get("deceased")
            and str(profile.get("residence_scope", "")) == "Regional"
        ]
        candidates.sort(key=lambda profile: str(profile.get("id", "")))
        visitors = []
        for profile in candidates:
            person_id = str(profile.get("id", ""))
            if (self._npc_family_seed("family-visit", person_id) + day_number) % 11 != 0:
                continue
            visitor = (
                world_profiles.get(person_id)
                if isinstance(world_profiles, dict)
                else None
            )
            if not isinstance(visitor, dict):
                visitor = copy.deepcopy(profile)
                if isinstance(world_profiles, dict):
                    world_profiles[person_id] = visitor
            visitor["world_npc_profile"] = True
            visitor["family_regional"] = True
            visitor["route_slot"] = 3 + len(visitors)
            visitor["origin_id"] = "family-region"
            visitor["origin_name"] = str(visitor.get("origin", "the surrounding region"))
            visitor["regional_news"] = "Family visits are bringing personal news between Elsewhere and nearby settlements."
            visitor["distance_chunks"] = 1 + self._npc_family_seed("family-visit-distance", person_id) % 6
            visitor["purpose"] = "visiting relatives and handling errands in Elsewhere"
            visitor["activity"] = "spending the day with relatives in town"
            visitor.setdefault("runtime_location", "Town")
            visitor.setdefault("x", 57)
            visitor.setdefault("y", 10)
            visitors.append(visitor)
            if len(visitors) >= 3:
                break
        return visitors

    def ensure_npc_lineage_for_actor(
        self, actor: Dict[str, object], realm: str = "world"
    ) -> Dict[str, object]:
        """Ensure any conversational NPC has real, named parent records."""
        actor_id = str(actor.get("id", "") or "")
        if not actor_id:
            return {}
        family = self.ensure_npc_family_state()
        profiles: Dict[str, Dict[str, object]] = family["profiles"]
        profile = profiles.get(actor_id)
        if not isinstance(profile, dict):
            age = _int(actor.get("age_years"), 30)
            profile = {
                "id": actor_id, "npc_id": actor_id,
                "name": str(actor.get("name", actor_id)),
                "sex": str(actor.get("sex", "Unknown")),
                "age_years": age,
                "age_group": str(actor.get("age_group", "Adult")),
                "life_stage": str(actor.get("age_group", "Adult")),
                "parent_ids": list(actor.get("parent_ids", []) or []),
                "child_ids": list(actor.get("child_ids", []) or []),
                "marital_status": str(actor.get("marital_status", "Single")),
                "npc_spouse_id": str(actor.get("npc_spouse_id", "")),
                "household_id": str(actor.get("household_id", f"family-household:{actor_id}")),
                "lineage_realm": str(realm),
            }
            profiles[actor_id] = profile
        surname = self._family_surname_for_actor(actor, actor_id)
        parent_ids = self._ensure_lineage_parent_pair(
            profiles, profile, actor_id, realm=str(realm), surname=surname,
        )
        for parent_id in parent_ids:
            parent = profiles.get(parent_id)
            if isinstance(parent, dict) and not parent.get("parent_ids"):
                self._ensure_lineage_parent_pair(
                    profiles, parent, parent_id, realm=str(realm),
                    surname=self._family_surname_for_actor(parent, parent_id),
                    horizon=True,
                )
        actor["parent_ids"] = list(profile.get("parent_ids", []) or [])
        actor["child_ids"] = list(profile.get("child_ids", []) or [])
        if str(realm) == "town":
            self._sync_living_authored_family_people(family)
        else:
            world_profiles = getattr(self.state, "world_npc_profiles", None)
            if isinstance(world_profiles, dict):
                for person_id, person in profiles.items():
                    if (
                        isinstance(person, dict)
                        and person.get("family_generated")
                        and str(person.get("lineage_realm", "")) == str(realm)
                        and not person.get("deceased")
                    ):
                        world_record = copy.deepcopy(person)
                        world_record["world_npc_profile"] = True
                        world_profiles.setdefault(str(person_id), world_record)
        return profile

    def _ensure_authored_family_profiles(self, family: Dict[str, object]) -> None:
        profiles = family["profiles"]
        households = family["households"]
        valid_npcs = [
            npc for npc in getattr(self.state, "town_npcs", [])
            if isinstance(npc, dict) and not npc.get("family_generated")
        ]
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
        self._ensure_authored_ancestry(family, valid_npcs)

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

    def npc_family_relative_records(self, npc_id: str) -> List[Dict[str, object]]:
        """Derive ordinary kinship labels from the persistent parent graph."""
        npc_id = str(npc_id)
        family = self.ensure_npc_family_state()
        profiles: Dict[str, Dict[str, object]] = family.get("profiles", {})
        person = profiles.get(npc_id)
        if not isinstance(person, dict):
            actor = self.npc_record_by_id(npc_id) if hasattr(self, "npc_record_by_id") else None
            if isinstance(actor, dict):
                person = self.ensure_npc_lineage_for_actor(actor, str(actor.get("lineage_realm", "world")))
        if not isinstance(person, dict):
            return []

        def record_for(person_id: str) -> Optional[Dict[str, object]]:
            record = profiles.get(str(person_id))
            if isinstance(record, dict):
                return record
            actor = self.npc_record_by_id(str(person_id)) if hasattr(self, "npc_record_by_id") else None
            return actor if isinstance(actor, dict) else None

        def children_of(person_id: str) -> List[str]:
            record = record_for(person_id)
            return [str(value) for value in (record.get("child_ids", []) if record else []) if str(value)]

        def parents_of(person_id: str) -> List[str]:
            record = record_for(person_id)
            return [str(value) for value in (record.get("parent_ids", []) if record else []) if str(value)]

        rows: List[Dict[str, object]] = []
        seen = {npc_id}

        def add(person_id: str, relation: str) -> None:
            person_id = str(person_id)
            if not person_id or person_id in seen:
                return
            record = record_for(person_id)
            if not isinstance(record, dict):
                return
            seen.add(person_id)
            rows.append({
                "id": person_id,
                "name": str(record.get("name", self.town_npc_name(person_id))),
                "relation": relation,
                "sex": str(record.get("sex", "Unknown")),
                "age_years": _int(record.get("age_years"), 0),
                "deceased": bool(record.get("deceased", False)),
                "role": str(record.get("role", record.get("occupation", "Resident"))),
                "record": record,
            })

        parent_ids = parents_of(npc_id)
        for parent_id in parent_ids:
            parent = record_for(parent_id) or {}
            add(parent_id, "mother" if parent.get("sex") == "Female" else "father")
        child_ids = children_of(npc_id)
        for child_id in child_ids:
            add(child_id, "daughter" if (record_for(child_id) or {}).get("sex") == "Female" else "son")
        spouse_id = str(person.get("npc_spouse_id", "") or "")
        if spouse_id:
            add(spouse_id, "spouse")

        sibling_ids = set()
        for parent_id in parent_ids:
            sibling_ids.update(children_of(parent_id))
        sibling_ids.discard(npc_id)
        for sibling_id in sorted(sibling_ids):
            sibling = record_for(sibling_id) or {}
            add(sibling_id, "sister" if sibling.get("sex") == "Female" else "brother")
            for younger_id in children_of(sibling_id):
                younger = record_for(younger_id) or {}
                add(younger_id, "niece" if younger.get("sex") == "Female" else "nephew")

        grandparent_ids = set()
        for parent_id in parent_ids:
            grandparent_ids.update(parents_of(parent_id))
        for grandparent_id in sorted(grandparent_ids):
            grandparent = record_for(grandparent_id) or {}
            add(
                grandparent_id,
                "grandmother" if grandparent.get("sex") == "Female" else "grandfather",
            )

        parent_siblings = set()
        for parent_id in parent_ids:
            for grandparent_id in parents_of(parent_id):
                parent_siblings.update(children_of(grandparent_id))
        parent_siblings.difference_update(parent_ids)
        for relative_id in sorted(parent_siblings):
            relative = record_for(relative_id) or {}
            add(relative_id, "aunt" if relative.get("sex") == "Female" else "uncle")
            for cousin_id in children_of(relative_id):
                add(cousin_id, "cousin")

        for child_id in child_ids:
            for grandchild_id in children_of(child_id):
                grandchild = record_for(grandchild_id) or {}
                add(
                    grandchild_id,
                    "granddaughter" if grandchild.get("sex") == "Female" else "grandson",
                )
        return rows

    def npc_family_relative_ids(self, npc_id: str) -> List[str]:
        return [str(row.get("id", "")) for row in self.npc_family_relative_records(npc_id)]

    def npc_family_people_are_related(self, first_id: str, second_id: str) -> bool:
        first_id, second_id = str(first_id), str(second_id)
        if not first_id or not second_id:
            return False
        return second_id in set(self.npc_family_relative_ids(first_id))

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
            and str(profile.get("marital_status", "Single")) in {"Single", "Widowed"}
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
        pairs = [
            (woman, man) for woman in women for man in men
            if profiles[woman].get("household_id") != profiles[man].get("household_id")
            and not self.npc_family_people_are_related(woman, man)
        ]
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
            pairs = [
                (woman, man) for woman in women for man in men
                if woman.get("household_id") != man.get("household_id")
                and not bool(set(woman.get("parent_ids", []) or []) & set(man.get("parent_ids", []) or []))
                and str(woman.get("id", "")) not in set(man.get("parent_ids", []) or [])
                and str(man.get("id", "")) not in set(woman.get("parent_ids", []) or [])
            ]
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
        if isinstance(plan, dict):
            builder.assign_household_rooms(plan, population)
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
        relatives = self.npc_family_relative_records(npc_id)
        if relatives:
            lines.append("Known family:")
            for relative in relatives[:12]:
                status_note = "deceased" if relative.get("deceased") else str(relative.get("role", "resident")).lower()
                lines.append(
                    f"- {relative.get('name')} ({relative.get('relation')}; {status_note})"
                )
        return lines

    def npc_family_dialogue_line(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        profile = self.npc_family_profile(npc_id)
        status = str(profile.get("marital_status", npc.get("marital_status", "Single")))
        spouse_id = str(profile.get("npc_spouse_id", npc.get("npc_spouse_id", "")))
        partner_id = str(profile.get("courtship_partner_id", npc.get("courtship_partner_id", "")))
        child_ids = list(profile.get("child_ids", npc.get("child_ids", [])) or [])
        relatives = self.npc_family_relative_records(npc_id)
        living = [row for row in relatives if not row.get("deceased")]
        deceased = [row for row in relatives if row.get("deceased")]
        statements: List[str] = []
        if spouse_id:
            spouse_record = next(
                (row for row in relatives if str(row.get("id", "")) == spouse_id),
                {},
            )
            if status == "Widowed" or spouse_record.get("deceased"):
                statements.append(
                    f"My late {kinship_term('spouse', self.npc_sex(spouse_id))} was "
                    f"{self.town_npc_name(spouse_id)}. Some parts of our life together still shape my days."
                )
            else:
                # "X and I have" is a compound subject, and the spoken-contraction pass
                # turns it into "X and I've been settling", which is not English.
                statements.append(f"{self.town_npc_name(spouse_id)} and I are settling into married life together.")
        elif status == "Engaged" and partner_id:
            statements.append(f"{self.town_npc_name(partner_id)} and I are planning our wedding, but we still keep separate homes until then.")
        elif status == "Courting" and partner_id:
            statements.append(f"I have been spending more time with {self.town_npc_name(partner_id)}. We are taking things slowly and still live separately.")
        if child_ids:
            child_names = [self.town_npc_name(value) for value in child_ids[:3]]
            kin = "child is" if len(child_names) == 1 else "children are"
            statements.append(f"My {kin} {', '.join(child_names)}.")
        close_order = (
            "mother", "father", "sister", "brother", "grandmother", "grandfather",
            "daughter", "son", "aunt", "uncle", "cousin", "niece", "nephew",
        )
        living_ordered = [
            row for relation in close_order for row in living if row.get("relation") == relation
        ]
        selected = (
            living_ordered[
                self._npc_family_seed("family-dialogue-living", npc_id, self.town_npc_day_key())
                % len(living_ordered)
            ]
            if living_ordered else None
        )
        if selected:
            # Relation rows carry the person's sex, so a named relative gets a
            # real pronoun instead of the neutral fallback. Both slots here sit
            # beside verbs that do not vary ("work ... keeps"), so the swap is safe.
            kin = pronouns_for_sex(selected.get("sex"))
            statements.append(
                f"My {selected.get('relation')} {selected.get('name')} is still part of my life; "
                f"{kin['possessive']} work as a {str(selected.get('role', 'resident')).lower()} "
                f"keeps {kin['object']} busy."
            )
        deceased_ordered = [
            row for relation in close_order for row in deceased if row.get("relation") == relation
        ]
        remembered = (
            deceased_ordered[
                self._npc_family_seed("family-dialogue-deceased", npc_id, self.town_npc_day_key())
                % len(deceased_ordered)
            ]
            if deceased_ordered else None
        )
        if remembered:
            gone = pronouns_for_sex(remembered.get("sex"))
            statements.append(
                f"My {remembered.get('relation')} {remembered.get('name')} died, but I still find "
                f"myself repeating things {gone['subject']} taught me."
            )
        if statements:
            return " ".join(statements[:3])
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
            if profile.get("family_generated"):
                continue
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
        generated_relatives = [
            profile for profile in profiles.values()
            if isinstance(profile, dict) and profile.get("family_generated")
        ]
        if generated_relatives:
            living_local = sum(
                not profile.get("deceased") and profile.get("residence_scope") == "Elsewhere"
                for profile in generated_relatives
            )
            living_regional = sum(
                not profile.get("deceased") and profile.get("residence_scope") == "Regional"
                for profile in generated_relatives
            )
            lines.append(
                f"- Family ledger: {len(generated_relatives)} named relatives; "
                f"{living_local} live locally and {living_regional} live elsewhere in the region."
            )
        populations = list(self.ensure_procedural_settlement_populations().values())
        if populations:
            lines.extend(["", "Wilderness settlements:"])
            for population in sorted(populations, key=lambda value: str(value.get("settlement_name", ""))):
                residents = list(population.get("residents", {}).values())
                married = sum(1 for resident in residents if resident.get("marital_status") == "Married") // 2
                courting = sum(1 for resident in residents if resident.get("marital_status") in {"Courting", "Engaged"}) // 2
                children = sum(1 for resident in residents if resident.get("age_group") in {"Child", "Teen"})
                lines.append(
                    f"- {population.get('settlement_name', 'Settlement')}: "
                    f"{quantity_agreement(married, 'married household')}, "
                    f"{quantity_agreement(courting, 'developing relationship')}, "
                    f"{quantity_agreement(children, 'young resident')}"
                )
        events = list(family.get("events", []))[-8:]
        lines.extend(["", "Recent family news:"])
        lines.extend(f"- {event.get('text', '')}" for event in reversed(events))
        if not events:
            lines.append("- No recent family events.")
        return lines


__all__ = ["NpcFamilyLifeMixin"]
