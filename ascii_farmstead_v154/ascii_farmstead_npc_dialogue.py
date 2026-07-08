from __future__ import annotations

"""Contextual dialogue for generated wilderness-settlement residents.

The dialogue layer operates on procedural population records and does not add
those residents to the authored town NPC roster or spawn them onto a live map.
"""

import copy
import random
from typing import Dict, Iterable, List, Optional, Tuple

from ascii_farmstead_npc_builder import (
    ProceduralNpcBuilder,
    procedural_slug,
    sanitize_procedural_job_profile,
    sanitize_procedural_request,
    stable_text_seed,
)


PROCEDURAL_DIALOGUE_TOPICS = (
    "chat",
    "work",
    "home",
    "settlement",
    "weather",
    "season",
    "rumor",
    "personal",
    "memory",
    "secret",
    "request",
)

BAD_WEATHER = {"rain", "rainy", "storm", "stormy", "snow", "snowy", "blizzard"}

ROLE_DIALOGUE: Dict[str, Tuple[str, ...]] = {
    "Mayor": (
        "A town is mostly promises at first. Roads, roofs, clean water - each one says we intend to remain.",
        "The difficult part is not deciding what to build. It is deciding what the place ought to become.",
        "Every new household changes the settlement's needs. That is a healthy sort of complication.",
    ),
    "Clerk": (
        "Records seem dull until a missing detail costs someone a home, a delivery, or a vote.",
        "I write down the small decisions. Those are usually the ones people remember differently later.",
        "A tidy ledger cannot solve every problem, but it can stop us inventing the same problem twice.",
    ),
    "Well Keeper": (
        "A settlement can argue about almost anything, but everyone agrees when the water stops running.",
        "I check the well before breakfast. Quiet work is often the work that keeps everything else possible.",
        "Water remembers the ground it passed through. I pay attention to changes in taste and color.",
    ),
    "Shopkeeper": (
        "The shelves tell me what people are planning before they do. Nails mean building; flour means company.",
        "A good shop keeps ordinary shortages from becoming emergencies.",
        "I try to stock one useful surprise alongside everything people already know to ask for.",
    ),
    "Stockkeeper": (
        "A crate in the wrong place can turn a five-minute delivery into an afternoon.",
        "I count supplies twice when the weather turns. Roads make optimists of merchants.",
        "Storage is a kind of memory: what we saved, what we used, and what we failed to expect.",
    ),
    "Carpenter": (
        "Fresh lumber moves after it is cut. A building is never as still as it looks.",
        "I like repairs. New construction proves ambition; repairs prove commitment.",
        "Good framing disappears behind the walls. I suppose that is the compliment.",
    ),
    "Carpenter Apprentice": (
        "I am learning when to measure again and when to trust the mark already on the board.",
        "Every carpenter has a different opinion about corners. Somehow the roofs still meet.",
        "One day I want to point at a building and know it will outlast my excuses.",
    ),
    "Doctor": (
        "Most emergencies begin as something small that everyone hoped would pass on its own.",
        "The clinic needs routine more than drama: clean tools, honest answers, and supplies replaced on time.",
        "Health is partly medicine and partly whether a community notices when someone disappears for three days.",
    ),
    "Nurse": (
        "People heal better when they understand what is happening. I explain things twice if I need to.",
        "Rest sounds simple until someone is frightened, busy, or responsible for half the town.",
        "I keep the clinic orderly so patients do not have to spend courage on avoidable confusion.",
    ),
    "Librarian": (
        "A new town produces history faster than it produces shelves.",
        "I collect practical knowledge first: routes, planting notes, weather records, remedies. Stories arrive anyway.",
        "Maps become interesting when the path people use disagrees with the path someone planned.",
    ),
    "Archivist": (
        "Official records say what happened. Marginal notes explain why it mattered.",
        "I keep discarded drafts. A corrected mistake still teaches more than a clean final copy.",
        "Someone should remember the settlement before everyone starts pretending it was inevitable.",
    ),
    "Innkeeper": (
        "An inn hears the road before the rest of town does.",
        "Travelers decide whether a place feels safe long before they learn who is in charge.",
        "Hospitality is part warm food and part knowing when a guest would rather not answer.",
    ),
    "Cook": (
        "A shared table can make strangers behave like neighbors for the length of a meal.",
        "I adjust recipes to what the settlement can grow, gather, and trade. That is how a local cuisine begins.",
        "The best compliment is silence for the first few bites.",
    ),
    "Merchant": (
        "A market is a conversation where half the sentences are prices.",
        "I watch what sells quickly, but I pay closer attention to what people ask for and cannot find.",
        "Trade routes are relationships with wagon wheels attached.",
    ),
    "Mechanic": (
        "If a machine is difficult to maintain, it is only borrowing trouble from the future.",
        "I listen before I open anything. A bad rattle often tells you which tool to reach for.",
        "Useful inventions should survive ordinary hands, bad weather, and one very confident mistake.",
    ),
    "Artisan": (
        "Useful things deserve care in their shape. People handle them every day.",
        "A town starts to feel permanent when residents make objects for beauty as well as survival.",
        "I save scraps. Small materials are unusually good at becoming the detail everyone notices.",
    ),
    "Gardener": (
        "Public ground belongs to everyone, which means it can quietly become nobody's responsibility.",
        "I plant for shade, pollinators, and the person who needs somewhere calm to sit.",
        "A garden records the season without needing a calendar.",
    ),
    "Student": (
        "Adults keep calling this place new, but it has been here for as long as I can remember.",
        "I know three shortcuts that are not on the map. One of them is even a good idea.",
        "I am trying to learn enough to choose what I want to be instead of merely choosing what is nearby.",
    ),
    "Retiree": (
        "A young town thinks every problem is new. That confidence is charming and occasionally expensive.",
        "I have stopped rushing to give advice. People hear it better after they ask.",
        "There is satisfaction in watching other people become responsible for tomorrow.",
    ),
    "Settler": (
        "There is always another small thing needed before a building feels like home.",
        "We came here for possibility. Possibility turns out to involve a great deal of carrying lumber.",
        "The settlement feels different each week. I am beginning to recognize which changes are ours.",
    ),
}

WEATHER_DIALOGUE: Dict[str, Tuple[str, ...]] = {
    "sunny": (
        "Clear weather makes every unfinished job look personally accusatory.",
        "A day like this puts people in the road. News travels faster when nobody is hurrying indoors.",
    ),
    "cloudy": (
        "The clouds are holding their decision. I suppose we can do the same for an hour.",
        "This light makes the whole settlement look quieter than it is.",
    ),
    "rainy": (
        "Rain finds the honest low points in every road and roof.",
        "Wet weather slows the work, but it also shows us exactly what needs improving.",
    ),
    "stormy": (
        "Storm days are when a town discovers whether its preparations were real or merely reassuring.",
        "I am keeping close to shelter today. Pride is a poor roof.",
    ),
    "snowy": (
        "Snow makes familiar distances feel newly negotiable.",
        "Everyone walks differently in snow. Even the hurried people become careful.",
    ),
    "blizzard": (
        "Nobody should be proving anything outdoors in this weather.",
        "In a blizzard, checking on the nearest household matters more than finishing the day's plan.",
    ),
}

SEASON_DIALOGUE: Dict[str, Tuple[str, ...]] = {
    "spring": (
        "Spring makes the settlement look hopeful before it has earned the confidence.",
        "Every thaw reveals one repair and three new ideas.",
    ),
    "summer": (
        "Summer stretches the workday until people forget that an evening is allowed to be quiet.",
        "The town feels fullest in summer; every doorway seems to have someone passing through it.",
    ),
    "fall": (
        "Fall turns every conversation toward stores, roofs, and how much time remains.",
        "The cooler air makes people practical. Winter is an excellent editor of unnecessary plans.",
    ),
    "winter": (
        "Winter reduces a town to the things it truly maintains.",
        "This season makes neighbors visible. You notice quickly which chimney has gone cold.",
    ),
}

REQUEST_POOLS: Dict[str, Tuple[Tuple[str, int, int, str], ...]] = {
    "Mayor": (("Wood", 8, 14, "for repairs to shared notice boards and public railings"),),
    "Clerk": (("Fiber", 3, 6, "for binding ledgers and securing document bundles"),),
    "Well Keeper": (("Stone", 6, 12, "to reinforce the well path and drainage edge"),),
    "Shopkeeper": (
        ("Carrot", 2, 4, "to fill a gap in the week's produce shelf"),
        ("Berries", 2, 5, "for a small display of local goods"),
    ),
    "Stockkeeper": (("Wood", 6, 10, "to repair crates before the next delivery"),),
    "Carpenter": (
        ("Wood", 10, 18, "for a set of necessary settlement repairs"),
        ("Hardwood", 2, 4, "for hinges and braces that should not need replacing"),
    ),
    "Carpenter Apprentice": (("Stone", 5, 9, "for practice foundations and corner setting"),),
    "Doctor": (("Cave Herbs", 2, 4, "to restore the clinic's basic remedy supply"),),
    "Nurse": (("Honey", 1, 2, "for soothing mixtures kept at the clinic"),),
    "Librarian": (("Fiber", 2, 4, "for repairs to bindings and map rolls"),),
    "Archivist": (("Maple", 1, 3, "for preserving and organizing local records"),),
    "Innkeeper": (
        ("Berries", 2, 5, "for breakfasts served to travelers"),
        ("Milk", 1, 2, "for the inn kitchen"),
    ),
    "Cook": (
        ("Tomato", 2, 4, "for the next shared supper"),
        ("Corn", 2, 4, "for a dependable batch of hot food"),
    ),
    "Merchant": (("Wildflower", 2, 4, "for a market display that looks worth stopping for"),),
    "Mechanic": (
        ("Copper Bar", 1, 2, "for replacement fittings and small mechanisms"),
        ("Coal", 3, 6, "for the workshop heat and forge"),
    ),
    "Artisan": (("Soft Fiber", 2, 4, "for a run of practical household work"),),
    "Gardener": (
        ("Wildflower", 3, 6, "to establish color around the public paths"),
        ("Watercress", 2, 4, "for the damp edge of the public garden"),
    ),
    "Student": (("Berries", 1, 3, "for a study outing that became longer than planned"),),
    "Retiree": (("Honey", 1, 2, "for the household pantry"),),
    "Settler": (
        ("Wood", 6, 12, "for ordinary household repairs"),
        ("Stone", 5, 10, "to finish a path near home"),
    ),
}


def procedural_relationship_tier(points: object) -> str:
    value = int(points or 0)
    if value >= 200:
        return "Deep Bond"
    if value >= 150:
        return "Trusted"
    if value >= 100:
        return "Close Friend"
    if value >= 60:
        return "Friend"
    if value >= 25:
        return "Acquaintance"
    return "Stranger"


def procedural_time_phase(hour: object) -> str:
    value = int(hour or 6)
    if 6 <= value < 8:
        return "wake"
    if 8 <= value < 12:
        return "work_morning"
    if 12 <= value < 14:
        return "lunch"
    if 14 <= value < 17:
        return "work_afternoon"
    if 17 <= value < 21:
        return "evening"
    return "late"


class ProceduralNpcDialogueBuilder:
    """Build deterministic contextual conversations for one resident."""

    def stable_line_id(self, resident_id: str, topic: str, text: str) -> str:
        return (
            f"{resident_id}:{procedural_slug(topic)}:"
            f"{stable_text_seed(text) % 100000}:{procedural_slug(text)[:36]}"
        )

    def household_members(
        self,
        resident: Dict[str, object],
        population: Dict[str, object],
    ) -> List[Dict[str, object]]:
        household = population.get("households", {}).get(
            str(resident.get("household_id", "")),
            {},
        )
        return [
            population.get("residents", {}).get(resident_id)
            for resident_id in household.get("member_ids", [])
            if isinstance(population.get("residents", {}).get(resident_id), dict)
            and resident_id != resident.get("id")
        ]

    def available_topics(
        self,
        resident: Dict[str, object],
        population: Dict[str, object],
    ) -> List[str]:
        points = int(resident.get("relationship", 0) or 0)
        topics = ["chat", "work", "home", "settlement", "weather", "season"]
        if points >= 25:
            topics.append("rumor")
        if points >= 60:
            topics.append("personal")
        if points >= 60 and resident.get("memories"):
            topics.append("memory")
        if points >= 150:
            topics.append("secret")
        if str(resident.get("age_group", "Adult")) != "Child":
            topics.append("request")
        return topics

    def request_for(
        self,
        resident: Dict[str, object],
        context: Dict[str, object],
    ) -> Dict[str, object]:
        role = str(resident.get("role", "Settler"))
        pool = REQUEST_POOLS.get(role, REQUEST_POOLS["Settler"])
        day_key = str(context.get("day_key", "1-1-1"))
        rng = random.Random(stable_text_seed(f"{resident.get('id')}:{day_key}:request"))
        item, minimum, maximum, purpose = pool[rng.randrange(len(pool))]
        quantity = rng.randint(int(minimum), int(maximum))
        relationship_reward = 5 + min(5, quantity // 3)
        money_reward = 45 + quantity * 24 + relationship_reward * 5
        request_id = (
            f"proc-request:{procedural_slug(resident.get('id'))}:"
            f"{procedural_slug(day_key)}:{procedural_slug(item)}"
        )
        return {
            "id": request_id,
            "title": f"{role}'s {item} Request",
            "description": f"{resident.get('name')} needs {quantity} {item} {purpose}.",
            "item": item,
            "quantity": quantity,
            "reward_money": money_reward,
            "reward_relationship": relationship_reward,
            "created_day": day_key,
            "status": "active",
        }

    def lines_for_topic(
        self,
        resident: Dict[str, object],
        population: Dict[str, object],
        context: Dict[str, object],
        topic: str,
    ) -> List[str]:
        name = str(resident.get("given_name") or resident.get("name") or "Resident")
        settlement = str(population.get("settlement_name", "the settlement"))
        role = str(resident.get("role", "Settler"))
        phase = str(context.get("phase", "work_morning"))
        schedule = resident.get("schedule", {}) if isinstance(resident.get("schedule"), dict) else {}
        routine = schedule.get(
            "bad_weather" if context.get("bad_weather") and phase != "late" else phase,
            {},
        )
        activity = str(routine.get("activity", "") or "keeping to today's routine")
        building_name = str(routine.get("building_name", "") or "")
        members = self.household_members(resident, population)
        member_names = [str(member.get("given_name") or member.get("name")) for member in members]
        tier = procedural_relationship_tier(resident.get("relationship", 0))
        traits = [str(value) for value in resident.get("personality_traits", [])]
        job_profile = sanitize_procedural_job_profile(
            resident.get("job_profile", {}),
            role,
        )

        if topic == "first_meeting":
            return [
                f"I'm {name}. I work as the {str(job_profile.get('title', role)).lower()} here in {settlement}.",
                f"We are still learning what kind of place {settlement} will be. You may as well learn it with us.",
                f"New face? I'm {name}. If you get lost, follow the road until someone starts giving you directions.",
            ]
        if topic == "work":
            lines = list(ROLE_DIALOGUE.get(role, ROLE_DIALOGUE["Settler"]))
            duties = [str(value) for value in job_profile.get("duties", []) if str(value or "").strip()]
            if duties:
                lines.append(f"Today's practical work is {duties[0]}. Tomorrow it will probably be the task I forgot to fear.")
            output = str(job_profile.get("output", "") or "")
            benefit = str(job_profile.get("public_benefit", "") or "")
            if output or benefit:
                lines.append(
                    f"If the job goes well, the town gets {output or 'a little more stability'}"
                    + (f"; mostly it {benefit}." if benefit else ".")
                )
            lines.append(
                f"I'd call my current pace {str(job_profile.get('quality', 'Capable')).lower()}: "
                f"skill {job_profile.get('skill', 0)}/5, morale {job_profile.get('morale', 0)}/100."
            )
            lines.append(
                f"Right now I am {activity}"
                + (f" near {building_name}." if building_name else ".")
            )
            return lines
        if topic == "home":
            household_role = str(resident.get("household_role", "Resident"))
            if member_names:
                names = ", ".join(member_names[:2])
                return [
                    f"I share home with {names}. A household develops its own weather, regardless of the sky.",
                    f"My place in the household is '{household_role}', though daily chores are less formal than the record.",
                    f"Home is where everyone notices which task you hoped somebody else would do.",
                ]
            return [
                "I live alone for now. It makes the quiet restful right up until something heavy needs moving.",
                f"The house is beginning to feel like mine rather than simply an address in {settlement}.",
            ]
        if topic == "settlement":
            vacancies = len(population.get("job_vacancies", []) or [])
            return [
                f"{settlement} changes whenever a building is finished, but it changes more when someone decides to stay.",
                (
                    f"We still have {vacancies} important job{'s' if vacancies != 1 else ''} unfilled. "
                    "Buildings alone do not make services reliable."
                    if vacancies
                    else "For now, every completed workplace has someone responsible for it. That is a good sign."
                ),
                "The planned road tells one story. The footpaths people choose will tell another.",
            ]
        if topic == "weather":
            weather = str(context.get("weather", "sunny")).lower()
            return list(WEATHER_DIALOGUE.get(weather, (
                f"This {weather} weather is changing how everyone moves through town.",
                "I check the sky before I trust the day's plan.",
            )))
        if topic == "season":
            season = str(context.get("season", "spring")).lower()
            return list(SEASON_DIALOGUE.get(season, (
                f"{season.title()} has its own opinion about how the settlement should work.",
            )))
        if topic == "rumor":
            return [
                str(resident.get("rumor", "People are already debating what the settlement should build next.")),
                "I cannot promise the story improved by passing through three households, but it certainly became more detailed.",
            ]
        if topic == "personal":
            goal = str(resident.get("goal", "Build a stable life here."))
            return [
                f"What I want, honestly? {goal}",
                (
                    f"You have become a {tier.lower()}, which means I can answer without turning everything into polite weather."
                ),
                (
                    f"People call me {traits[0].lower()}."
                    + (f" They are not wrong, though {traits[1].lower()} is closer on difficult days." if len(traits) > 1 else "")
                    if traits
                    else "I am still deciding which parts of me belong to this place."
                ),
            ]
        if topic == "memory":
            memories = [str(value) for value in resident.get("memories", []) if str(value).strip()]
            if memories:
                return [
                    f"I remember this: {memory}",
                    "It is strange which moments become landmarks after enough time passes.",
                ] if (memory := memories[-1]) else []
            return ["We have not made enough history together for me to pretend otherwise."]
        if topic == "secret":
            return [
                str(resident.get("friend_secret", "I am still deciding whether this place can become permanent.")),
                "I do not tell everyone that. Please let it remain mine to share.",
            ]
        if topic == "request":
            request = sanitize_procedural_request(resident.get("active_request", {}))
            if request and request.get("status") == "completed":
                return [
                    f"You already helped with the {request.get('item')}. I have not forgotten.",
                    "Let me solve at least one of my own problems before I bring you another.",
                ]
            if request:
                return [
                    str(request.get("description", "")),
                    (
                        f"If you can bring {request.get('quantity')} {request.get('item')}, "
                        f"I can pay {request.get('reward_money')}g."
                    ),
                ]
            return ["I do not need anything specific today, which is rare enough to appreciate."]

        generic = [
            f"Good to see you. I was {activity}.",
            f"{settlement} is busy in a quiet way today.",
            "Some days a short conversation is enough to make the work feel less solitary.",
        ]
        if "Wry" in traits:
            generic.append("Everything is under control, provided nobody asks for an inventory.")
        if "Reserved" in traits:
            generic.append("I do not always have much to say, but I do notice when you stop by.")
        if "Cheerful" in traits:
            generic.append("There you are. The day has improved by at least one conversation.")
        return generic

    def choose_conversation(
        self,
        resident: Dict[str, object],
        population: Dict[str, object],
        context: Dict[str, object],
        topic: str = "chat",
    ) -> Dict[str, object]:
        available = self.available_topics(resident, population)
        requested_topic = str(topic or "chat").lower()
        if requested_topic not in available:
            requested_topic = "chat"
        category = (
            "first_meeting"
            if requested_topic == "chat" and not bool(resident.get("met", False))
            else requested_topic
        )
        texts = [
            text.strip()
            for text in self.lines_for_topic(
                resident,
                population,
                context,
                category,
            )
            if str(text).strip()
        ]
        if not texts:
            texts = ["Good to see you."]
        resident_id = str(resident.get("id", "resident"))
        entries = [
            {
                "id": self.stable_line_id(resident_id, category, text),
                "text": text,
                "category": category,
            }
            for text in texts
        ]
        recent = set(str(value) for value in resident.get("recent_dialogue_ids", []))
        fresh = [entry for entry in entries if entry["id"] not in recent]
        choices = fresh or entries
        seed_text = (
            f"{resident_id}:{context.get('day_key')}:{context.get('hour')}:"
            f"{category}:{resident.get('dialogue_count', 0)}:{len(recent)}"
        )
        chosen = choices[stable_text_seed(seed_text) % len(choices)]
        follow_up = ""
        if category in {"first_meeting", "request", "secret", "memory"} and len(entries) > 1:
            follow_entry = next((entry for entry in entries if entry["id"] != chosen["id"]), None)
            if follow_entry:
                follow_up = str(follow_entry["text"])
        return {
            **chosen,
            "topic": requested_topic,
            "speaker": str(resident.get("name", "Resident")),
            "follow_up": follow_up,
            "available_topics": available,
            "relationship_tier": procedural_relationship_tier(
                resident.get("relationship", 0)
            ),
        }


class ProceduralNpcDialogueMixin:
    """FarmGame accessors and mutations for generated-resident conversations."""

    def procedural_npc_dialogue_builder(self) -> ProceduralNpcDialogueBuilder:
        builder = getattr(self, "_procedural_npc_dialogue_builder", None)
        if not isinstance(builder, ProceduralNpcDialogueBuilder):
            builder = ProceduralNpcDialogueBuilder()
            self._procedural_npc_dialogue_builder = builder
        return builder

    def procedural_settlement_dialogue_context(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Dict[str, object]:
        weather = str(getattr(self.state, "weather", "Sunny") or "Sunny").lower()
        hour = int(getattr(self.state, "hour", 6) or 6)
        phase = procedural_time_phase(hour)
        return {
            "chunk_x": int(chunk_x),
            "chunk_y": int(chunk_y),
            "day_key": (
                f"{int(getattr(self.state, 'year', 1))}-"
                f"{int(getattr(self.state, 'month', 1))}-"
                f"{int(getattr(self.state, 'day', 1))}"
            ),
            "date_label": str(getattr(self.state, "date_label", "")),
            "weekday": str(getattr(self.state, "weekday", "")),
            "season": str(getattr(self.state, "season", "Spring")).lower(),
            "weather": weather,
            "bad_weather": weather in BAD_WEATHER,
            "hour": hour,
            "minute": int(getattr(self.state, "minute", 0) or 0),
            "phase": phase,
            "player_name": str(getattr(self.state, "player_name", "Farmer")),
        }

    def procedural_settlement_resident_record(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
    ) -> Optional[Dict[str, object]]:
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        if not population:
            return None
        resident = population.get("residents", {}).get(str(resident_id))
        return resident if isinstance(resident, dict) else None

    def ensure_procedural_resident_request(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
    ) -> Dict[str, object]:
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        resident = self.procedural_settlement_resident_record(
            chunk_x,
            chunk_y,
            resident_id,
        )
        if not population or not resident:
            return {}
        context = self.procedural_settlement_dialogue_context(chunk_x, chunk_y)
        existing = sanitize_procedural_request(resident.get("active_request", {}))
        day_key = str(context["day_key"])
        if existing and (
            existing.get("status") == "active"
            or str(resident.get("last_request_day", "")) == day_key
        ):
            resident["active_request"] = existing
            return copy.deepcopy(existing)
        request = self.procedural_npc_dialogue_builder().request_for(
            resident,
            context,
        )
        resident["active_request"] = request
        resident["last_request_day"] = day_key
        return copy.deepcopy(request)

    def procedural_settlement_dialogue_topics(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
    ) -> List[str]:
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        resident = self.procedural_settlement_resident_record(
            chunk_x,
            chunk_y,
            resident_id,
        )
        if not population or not resident:
            return []
        return self.procedural_npc_dialogue_builder().available_topics(
            resident,
            population,
        )

    def procedural_settlement_conversation(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
        topic: str = "chat",
        remember: bool = True,
    ) -> Optional[Dict[str, object]]:
        population = self.procedural_settlement_population(chunk_x, chunk_y)
        resident = self.procedural_settlement_resident_record(
            chunk_x,
            chunk_y,
            resident_id,
        )
        if not population or not resident:
            return None
        requested_topic = str(topic or "chat").lower()
        if requested_topic == "request" and remember:
            self.ensure_procedural_resident_request(chunk_x, chunk_y, resident_id)
        context = self.procedural_settlement_dialogue_context(chunk_x, chunk_y)
        result = self.procedural_npc_dialogue_builder().choose_conversation(
            resident,
            population,
            context,
            requested_topic,
        )
        result["relationship_gain"] = 0
        result["relationship"] = int(resident.get("relationship", 0) or 0)
        result["request"] = copy.deepcopy(
            sanitize_procedural_request(resident.get("active_request", {}))
        )
        if not remember:
            return result

        day_key = str(context["day_key"])
        first_meeting = not bool(resident.get("met", False))
        first_today = str(resident.get("last_talk_day", "")) != day_key
        relationship_gain = 2 if first_meeting else (1 if first_today else 0)
        resident["met"] = True
        resident["relationship"] = max(
            -50,
            min(250, int(resident.get("relationship", 0) or 0) + relationship_gain),
        )
        resident["dialogue_count"] = int(resident.get("dialogue_count", 0) or 0) + 1
        resident["last_talk_day"] = day_key
        resident["last_dialogue_topic"] = str(result.get("topic", "chat"))
        recent = [
            str(value)
            for value in resident.get("recent_dialogue_ids", [])
            if str(value) != str(result.get("id", ""))
        ]
        recent.append(str(result.get("id", "")))
        resident["recent_dialogue_ids"] = recent[-10:]
        flags = list(resident.get("conversation_flags", []) or [])
        flag = {
            "first_meeting": "introduced",
            "rumor": "rumor_shared",
            "personal": "personal_goal_shared",
            "secret": "secret_shared",
            "request": "request_discussed",
        }.get(str(result.get("category", "")))
        if flag and flag not in flags:
            flags.append(flag)
        resident["conversation_flags"] = flags[-40:]
        if first_meeting:
            memory = (
                f"{context.get('date_label') or day_key} - Met "
                f"{context.get('player_name', 'the farmer')} in "
                f"{population.get('settlement_name', 'the settlement')}."
            )
            memories = list(resident.get("memories", []) or [])
            if memory not in memories:
                memories.append(memory)
            resident["memories"] = memories[-16:]
        result["relationship_gain"] = relationship_gain
        result["relationship"] = int(resident["relationship"])
        result["relationship_tier"] = procedural_relationship_tier(
            resident["relationship"]
        )
        return result

    def procedural_settlement_request_status(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
    ) -> str:
        resident = self.procedural_settlement_resident_record(
            chunk_x,
            chunk_y,
            resident_id,
        )
        if not resident:
            return "Missing resident"
        request = sanitize_procedural_request(resident.get("active_request", {}))
        if not request:
            return "No request"
        if request.get("status") == "completed":
            return "Completed"
        item = str(request["item"])
        quantity = int(request["quantity"])
        carried = int(getattr(self.state, "inventory", {}).get(item, 0) or 0)
        return "Ready" if carried >= quantity else f"Need {quantity - carried} more {item}"

    def complete_procedural_settlement_request(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
    ) -> bool:
        resident = self.procedural_settlement_resident_record(
            chunk_x,
            chunk_y,
            resident_id,
        )
        if not resident:
            return False
        request = sanitize_procedural_request(resident.get("active_request", {}))
        if not request or request.get("status") != "active":
            return False
        inventory = getattr(self.state, "inventory", {})
        item = str(request["item"])
        quantity = int(request["quantity"])
        if not isinstance(inventory, dict) or int(inventory.get(item, 0) or 0) < quantity:
            return False
        inventory[item] = int(inventory.get(item, 0) or 0) - quantity
        if inventory[item] <= 0:
            inventory.pop(item, None)
        self.state.money = int(getattr(self.state, "money", 0) or 0) + int(
            request.get("reward_money", 0)
        )
        resident["relationship"] = min(
            250,
            int(resident.get("relationship", 0) or 0)
            + int(request.get("reward_relationship", 0)),
        )
        request["status"] = "completed"
        resident["active_request"] = request
        completed = list(resident.get("completed_request_ids", []) or [])
        if request["id"] not in completed:
            completed.append(request["id"])
        resident["completed_request_ids"] = completed[-20:]
        memory = (
            f"{getattr(self.state, 'date_label', request.get('created_day'))} - "
            f"{getattr(self.state, 'player_name', 'The farmer')} helped provide "
            f"{quantity} {item}."
        )
        memories = list(resident.get("memories", []) or [])
        if memory not in memories:
            memories.append(memory)
        resident["memories"] = memories[-16:]
        message = (
            f"Completed {resident.get('name')}'s request. "
            f"Earned {request.get('reward_money')}g and "
            f"{request.get('reward_relationship')} relationship."
        )
        if hasattr(self, "autosave_with_message"):
            self.autosave_with_message(message)
        elif hasattr(self, "set_message"):
            self.set_message(message)
        return True

    def procedural_settlement_conversation_lines(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
        topic: str = "chat",
        remember: bool = False,
    ) -> List[str]:
        result = self.procedural_settlement_conversation(
            chunk_x,
            chunk_y,
            resident_id,
            topic=topic,
            remember=remember,
        )
        if not result:
            return ["No generated resident was found."]
        lines = [
            f"{result.get('speaker')}",
            f"Topic: {str(result.get('topic', 'chat')).title()}",
            f"Relationship: {result.get('relationship_tier')} ({result.get('relationship')})",
            "",
            f'"{result.get("text")}"',
        ]
        if result.get("follow_up"):
            lines.extend(["", f'"{result.get("follow_up")}"'])
        if int(result.get("relationship_gain", 0) or 0):
            lines.extend(["", f"Relationship +{result.get('relationship_gain')}"])
        request = result.get("request", {})
        if isinstance(request, dict) and request and str(result.get("topic")) == "request":
            lines.extend([
                "",
                f"Needs: {request.get('quantity')} {request.get('item')}",
                f"Reward: {request.get('reward_money')}g, relationship +{request.get('reward_relationship')}",
                f"Status: {self.procedural_settlement_request_status(chunk_x, chunk_y, resident_id)}",
            ])
        lines.extend([
            "",
            "Available topics: "
            + ", ".join(str(value).title() for value in result.get("available_topics", [])),
        ])
        return lines

    def show_procedural_settlement_conversation(
        self,
        chunk_x: int,
        chunk_y: int,
        resident_id: str,
        topic: str = "chat",
    ):
        resident = self.procedural_settlement_resident_record(
            chunk_x,
            chunk_y,
            resident_id,
        )
        if not resident:
            self.set_message("No generated resident was found.")
            return None
        return self.vertical_panel_view(
            str(resident.get("name", "Resident")),
            self.procedural_settlement_conversation_lines(
                chunk_x,
                chunk_y,
                resident_id,
                topic=topic,
                remember=True,
            ),
            88,
            40,
        )


__all__ = [
    "BAD_WEATHER",
    "PROCEDURAL_DIALOGUE_TOPICS",
    "ProceduralNpcDialogueBuilder",
    "ProceduralNpcDialogueMixin",
    "procedural_relationship_tier",
    "procedural_time_phase",
]
