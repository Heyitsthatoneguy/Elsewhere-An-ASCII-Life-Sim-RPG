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
from ascii_farmstead_helpers import (
    item_name_for_quantity,
    naturalize_item_quantity_text,
    quantity_item_phrase,
)


PROCEDURAL_DIALOGUE_TOPICS = (
    "chat",
    "work",
    "home",
    "background",
    "interests",
    "people",
    "settlement",
    "politics",
    "weather",
    "season",
    "concerns",
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
        "The difficult part isn't deciding what to build. It's deciding what the place ought to become.",
        "Every new household changes the settlement's needs. That's a healthy sort of complication.",
    ),
    "Clerk": (
        "Records seem dull until a missing detail costs someone a home, a delivery, or a vote.",
        "I write down the small decisions. Those are usually the ones people remember differently later.",
        "A tidy ledger can't solve every problem, but it can stop us inventing the same problem twice.",
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
        "I'm learning when to measure again and when to trust the mark already on the board.",
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
    "Sheriff": (
        "A safe road is one people can use without thinking about who made it safe.",
        "Most trouble is easier to prevent when residents report what they actually saw instead of improving the story.",
        "I would rather escort one frightened traveler home than arrest someone after the damage is done.",
    ),
    "Deputy": (
        "Patrol work is mostly learning what ordinary looks like, so you notice when it changes.",
        "I check roads, doors, and faces. A town usually warns you before it has a serious problem.",
        "The badge does not make every disagreement my business. Knowing the difference is part of the job.",
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
        "I adjust recipes to what the settlement can grow, gather, and trade. That's how a local cuisine begins.",
        "The best compliment is silence for the first few bites.",
    ),
    "Merchant": (
        "A market is a conversation where half the sentences are prices.",
        "I watch what sells quickly, but I pay closer attention to what people ask for and can't find.",
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
        "I know three shortcuts that aren't on the map. One of them is even a good idea.",
        "I'm trying to learn enough to choose what I want to be instead of merely choosing what is nearby.",
    ),
    "Retiree": (
        "A young town thinks every problem is new. That confidence is charming and occasionally expensive.",
        "I've stopped rushing to give advice. People hear it better after they ask.",
        "There's satisfaction in watching other people become responsible for tomorrow.",
    ),
    "Settler": (
        "There's always another small thing needed before a building feels like home.",
        "We came here for possibility. Possibility turns out to involve a great deal of carrying lumber.",
        "The settlement feels different each week. I'm beginning to recognize which changes are ours.",
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
        "I'm keeping close to shelter today. Pride is a poor roof.",
        "That thunder is close enough that I'm postponing anything that can wait.",
        "The wind keeps changing direction. I wouldn't trust a long route until it settles.",
        "I'm listening for loose shutters. They always announce themselves at the worst moment.",
        "The roads will be muddy after this. Give the low crossings extra room.",
        "A warm room and a dry coat sound better every time the sky flashes.",
        "If you travel today, keep an easy way back. This weather can turn quickly.",
        "The rain is coming sideways now. Even the covered paths aren't staying dry.",
        "I hope everyone outside has noticed how dark the clouds have become.",
        "There will be branches down after this. Watch the road edges tomorrow.",
        "This is weather for checking on people nearby, not proving how far you can walk.",
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


PROCEDURAL_QUEST_ARCHETYPES: Dict[str, Tuple[str, ...]] = {
    "Mayor": ("survey", "neighbors", "delivery", "danger"),
    "Clerk": ("neighbors", "survey", "salvage", "delivery"),
    "Well Keeper": ("survey", "craft", "delivery", "salvage"),
    "Shopkeeper": ("delivery", "harvest", "fish", "neighbors"),
    "Stockkeeper": ("delivery", "salvage", "craft", "survey"),
    "Carpenter": ("craft", "salvage", "survey", "delivery"),
    "Carpenter Apprentice": ("craft", "salvage", "survey", "harvest"),
    "Doctor": ("delivery", "harvest", "salvage", "survey"),
    "Nurse": ("delivery", "neighbors", "harvest", "survey"),
    "Sheriff": ("danger", "survey", "neighbors", "salvage"),
    "Deputy": ("danger", "survey", "salvage", "neighbors"),
    "Librarian": ("survey", "salvage", "neighbors", "delivery"),
    "Archivist": ("survey", "salvage", "neighbors", "delivery"),
    "Innkeeper": ("fish", "harvest", "delivery", "neighbors"),
    "Cook": ("harvest", "fish", "delivery", "craft"),
    "Merchant": ("delivery", "survey", "salvage", "neighbors"),
    "Mechanic": ("craft", "salvage", "delivery", "survey"),
    "Artisan": ("craft", "salvage", "delivery", "neighbors"),
    "Gardener": ("harvest", "survey", "delivery", "neighbors"),
    "Student": ("neighbors", "survey", "fish", "salvage"),
    "Retiree": ("neighbors", "survey", "delivery", "fish"),
    "Settler": ("delivery", "harvest", "survey", "salvage", "craft", "fish"),
}

TRAIT_CHAT_LINES: Dict[str, Tuple[str, ...]] = {
    "Cheerful": (
        "I've had worse days and less interesting company.",
        "There's usually something worth enjoying before the work is finished.",
    ),
    "Reserved": (
        "I'm not avoiding conversation. I simply prefer one that knows where it's going.",
        "Quiet doesn't mean nothing is happening. It usually means I'm still thinking.",
    ),
    "Practical": (
        "I trust a plan more once somebody has named the tools it requires.",
        "A small useful improvement is still an improvement.",
    ),
    "Curious": (
        "I keep finding one question underneath another. It makes ordinary errands take longer.",
        "The town becomes more interesting when you ask why people chose this particular way of doing things.",
    ),
    "Patient": (
        "Not every problem improves because someone hurried toward it.",
        "I can wait for a good answer, provided nobody mistakes patience for indifference.",
    ),
    "Bold": (
        "If the cautious route and the useful route disagree, I at least want to know why.",
        "I would rather test a sensible risk than spend the year wondering about it.",
    ),
    "Gentle": (
        "People usually tell you what matters after they believe you won't use it carelessly.",
        "A difficult day does not need another sharp edge added to it.",
    ),
    "Wry": (
        "The day remains under control, if we use a generous definition of control.",
        "Every efficient system eventually meets a person carrying the wrong key.",
    ),
    "Methodical": (
        "I like knowing what comes next. Surprises are more manageable when the ordinary work is in order.",
        "Most mistakes become less mysterious once you write down the sequence honestly.",
    ),
    "Restless": (
        "I've been in one place long enough that my feet are beginning to object.",
        "A finished task mostly makes me notice the next road.",
    ),
    "Hospitable": (
        "Nobody should have to earn basic warmth before they can sit down.",
        "A welcome isn't complicated, but people remember when one was missing.",
    ),
    "Protective": (
        "I notice who has not come home yet. Somebody should.",
        "Preparation is easier than explaining afterward why nobody thought ahead.",
    ),
    "Calm": (
        "Most decisions improve after the first frightened thought has passed.",
        "I prefer to understand the shape of a problem before I give it my energy.",
    ),
}

RELATIONSHIP_CHAT_LINES: Dict[str, Tuple[str, ...]] = {
    "Stranger": (
        "I don't know you yet, so let's start with something ordinary.",
        "You are welcome to ask, but I may keep the personal answer for another day.",
    ),
    "Acquaintance": (
        "We have spoken enough that I recognize the way you approach a conversation.",
        "I'm beginning to know which questions you ask because you care and which you ask from curiosity.",
    ),
    "Friend": (
        "I can give you the honest version instead of the polite one.",
        "You know enough of my life that I don't have to explain every name before I tell the story.",
    ),
    "Close Friend": (
        "You can usually tell when something is bothering me before I decide to mention it.",
        "There aren't many people I would trust with the unfinished version of a thought.",
    ),
}


def procedural_relationship_tier(points: object) -> str:
    value = int(points or 0)
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
        topics = [
            "chat", "work", "home", "background", "interests",
            "settlement", "politics", "weather", "season",
        ]
        if points >= 25:
            topics.extend(["people", "concerns", "rumor"])
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
            "description": f"{resident.get('name')} needs {quantity_item_phrase(item, quantity)} {purpose}.",
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
        skill = int(job_profile.get("skill", 0) or 0)
        morale = int(job_profile.get("morale", 0) or 0)
        connections = resident.get("social_connections", {}) if isinstance(resident.get("social_connections"), dict) else {}
        residents = population.get("residents", {}) if isinstance(population.get("residents"), dict) else {}

        def connected_name(key: str) -> str:
            target = residents.get(str(connections.get(key, "")), {})
            return str(target.get("given_name") or target.get("name") or "") if isinstance(target, dict) else ""

        friend_name = connected_name("friend")
        rival_name = connected_name("rival")
        coworker_names = [
            str(residents.get(str(value), {}).get("given_name") or residents.get(str(value), {}).get("name") or "")
            for value in connections.get("coworkers", []) or []
            if isinstance(residents.get(str(value)), dict)
        ]
        settlement_context = context.get("settlement", {}) if isinstance(context.get("settlement"), dict) else {}
        identity = settlement_context.get("identity", {}) if isinstance(settlement_context.get("identity"), dict) else {}
        market = settlement_context.get("market", {}) if isinstance(settlement_context.get("market"), dict) else {}
        geography = settlement_context.get("geography", {}) if isinstance(settlement_context.get("geography"), dict) else {}
        event = settlement_context.get("event", {}) if isinstance(settlement_context.get("event"), dict) else {}
        recent_memories = [str(value) for value in resident.get("memories", []) if str(value).strip()]
        hobbies = [str(value) for value in resident.get("hobbies", []) if str(value).strip()]
        likes = [str(value) for value in resident.get("likes", []) if str(value).strip()]
        dislikes = [str(value) for value in resident.get("dislikes", []) if str(value).strip()]
        vacancies = len(population.get("job_vacancies", []) or [])

        if topic == "first_meeting":
            introductions = [
                f"I'm {name}. I work as the {str(job_profile.get('title', role)).lower()} here in {settlement}.",
                f"I don't think we've met. I'm {name}; most days you'll find me {activity}.",
                f"You're new to me. I'm {name}. Ask plainly if there's something you need.",
                f"My name is {name}. I came here because I {str(resident.get('reason_for_settling', 'wanted useful work')).rstrip('.')}.",
                f"I'm {name}. Welcome to {settlement}; we're still deciding what kind of town this will become.",
            ]
            if "Cheerful" in traits or "Hospitable" in traits:
                introductions.extend([
                    f"I don't recognize you yet, but that can be fixed. I'm {name}.",
                    f"New face? I'm {name}. You're welcome to stop me if you need directions or company.",
                ])
            if "Reserved" in traits:
                introductions.append(f"I'm {name}. I may be quiet at first; it isn't meant as a slight.")
            if "Wry" in traits:
                introductions.append(f"I'm {name}. I would offer a polished introduction, but the day has already used most of the polish.")
            return introductions
        if topic == "work":
            lines = list(ROLE_DIALOGUE.get(role, ROLE_DIALOGUE["Settler"]))
            duties = [str(value) for value in job_profile.get("duties", []) if str(value or "").strip()]
            if duties:
                lines.extend([
                    f"Today's main responsibility is {duties[0]}.",
                    f"The part people rarely notice is {duties[-1]}. It only becomes visible when nobody does it.",
                ])
            output = str(job_profile.get("output", "") or "")
            benefit = str(job_profile.get("public_benefit", "") or "")
            if output or benefit:
                lines.append(
                    f"If the job goes well, the town gets {output or 'a little more stability'}"
                    + (f"; mostly it {benefit}." if benefit else ".")
                )
            lines.append(
                f"I'd call my current pace {str(job_profile.get('quality', 'Capable')).lower()}: "
                + (
                    "I'm still learning the difficult parts of the work"
                    if skill <= 1 else
                    "I know the routine, though experience still catches me by surprise"
                    if skill <= 3 else
                    "I know the work well enough to notice trouble early"
                )
                + (
                    ", and lately I've had energy to spare."
                    if morale >= 70 else
                    ", and I'm managing the pace well enough."
                    if morale >= 40 else
                    ", though lately the work has been wearing me down."
                )
            )
            lines.append(
                f"Right now I'm {activity}"
                + (f" near {building_name}." if building_name else ".")
            )
            if coworker_names:
                lines.append(f"I work most often with {coworker_names[0]}. We divide the work well, even when we disagree about the order.")
            if morale < 40:
                lines.append("The work matters to me, but the current pace isn't sustainable. Something will have to change.")
            elif morale >= 75:
                lines.append("For once, the workload and the available hands are close to matching. I intend to enjoy that while it lasts.")
            if phase == "lunch":
                lines.append("I'm technically taking a break. My hands have stopped working; my mind hasn't received the message.")
            return lines
        if topic == "home":
            household_role = str(resident.get("household_role", "Resident"))
            if member_names:
                names = ", ".join(member_names[:3])
                household_line = {
                    "Head": "I'm usually the one who keeps the household organized, though everyone gets a say.",
                    "Spouse": "I share responsibility for the household, even when we divide the chores differently.",
                    "Child": "The adults handle most of the household work, but I still have chores of my own.",
                    "Teen": "I do my share at home, even if we don't always agree on what that should mean.",
                    "Elder Relative": "I've lived long enough to know which household problems need advice and which need patience.",
                    "Adult Relative": "I share the home and take responsibility for my part of it.",
                    "Housemate": "We share the home and divide the work as fairly as we can.",
                }.get(household_role, "I do my share of the household work without worrying much about titles.")
                return [
                    f"I share a home with {names}.",
                    household_line,
                    "We don't always keep the same hours, so meals and evenings are when we actually catch up.",
                    f"My room is {str(resident.get('assigned_room_label', 'a private corner of the house')).lower()}. It isn't grand, but it feels like mine.",
                    "At home, unfinished chores are usually less important than noticing when someone has had a difficult day.",
                ]
            return [
                "I live alone for now. It makes the quiet restful right up until something heavy needs moving.",
                f"The house is beginning to feel like mine rather than simply an address in {settlement}.",
                "Living alone means every misplaced object is evidence against me personally.",
            ]
        if topic == "background":
            return [
                f"I was born around {resident.get('birthplace', 'another community in the region')}.",
                f"I grew up in {resident.get('upbringing', 'a household that valued practical work')}.",
                f"One experience that stayed with me was {resident.get('formative_event', 'being trusted with work that mattered to other people')}.",
                str(resident.get("arrival_story", f"I came to {settlement} because there was useful work here.")),
                f"I didn't arrive as the person I am now. {settlement} has changed some of my habits, and I have changed a little of it in return.",
            ]
        if topic == "interests":
            lines = [
                f"When work leaves me alone, I make time for {', '.join(hobbies[:3])}." if hobbies else "I usually spend free time walking, reading, or repairing something at home.",
                f"I can lose an afternoon to {hobbies[0]}." if hobbies else "A quiet walk can take more of an afternoon than I intend.",
            ]
            if likes:
                lines.append(f"I have a particular fondness for {', '.join(likes[:2])}, though I don't expect everyone to understand it.")
            if dislikes:
                lines.append(f"I can do without {', '.join(dislikes[:2])}. Experience has already made the argument.")
            if friend_name and hobbies:
                lines.append(f"{friend_name} occasionally joins me for {hobbies[0]}. We approach it so differently that it stays interesting.")
            return lines
        if topic == "people":
            lines = []
            if friend_name:
                lines.extend([
                    f"{friend_name} is the person I look for when I need an honest answer instead of a reassuring one.",
                    f"I trust {friend_name} with the sort of problem that sounds foolish until you explain the whole thing.",
                ])
            if rival_name:
                lines.extend([
                    f"{rival_name} and I disagree about what this town needs. I don't dislike them enough to pretend they're always wrong.",
                    f"I keep an eye on {rival_name}. Competition can improve the work, provided neither of us starts performing for an audience.",
                ])
            if coworker_names:
                lines.append(f"You learn a person's real habits by working late beside them. I've learned quite a few of {coworker_names[0]}'s.")
            if member_names:
                lines.append(f"At home, {member_names[0]} is usually the first person to notice when I'm carrying the workday through the door.")
            return lines or ["I know people here, but I don't sort them into stories for strangers."]
        if topic == "settlement":
            lines = [
                f"{settlement} changes whenever a building is finished, but it changes more when someone decides to stay.",
                (
                    f"We still have {vacancies} important job{'s' if vacancies != 1 else ''} unfilled. "
                    "Buildings alone don't make services reliable."
                    if vacancies
                    else "For now, every completed workplace has someone responsible for it. That's a good sign."
                ),
                "The planned road tells one story. The footpaths people choose will tell another.",
            ]
            if identity:
                lines.extend([
                    f"People say our local custom is that {str(identity.get('custom', 'neighbors help when they can')).rstrip('.')}.",
                    f"The town is becoming known for {identity.get('industry', 'regional trade')}. Whether that becomes an identity or only a good season remains to be seen.",
                ])
            if market:
                lines.append(f"We have plenty of {market.get('surplus', 'local goods')}, but people keep asking for {market.get('demand', 'supplies the road has not brought')}.")
            if geography:
                lines.append(f"The {geography.get('setting', 'local landscape')} shapes the town more than any council plan. Water, roads, and weather decide what is practical.")
            if event:
                lines.append(f"Today's {event.get('name', 'town activity')} has changed the usual routine. Even people who aren't participating have an opinion about it.")
            development = str(settlement_context.get("development", ""))
            if development:
                lines.append(f"People describe the town as {development.lower()} now. I still remember when that would have sounded overly generous.")
            return lines
        if topic == "politics":
            civic = context.get("civic", {}) if isinstance(context.get("civic"), dict) else {}
            phase_label = str(civic.get("phase", "between elections"))
            mayor = str(civic.get("mayor", "the mayor"))
            issue = str(civic.get("issue", "ordinary town business"))
            mandate = str(civic.get("mandate", "no special mandate"))
            latest = str(civic.get("latest_decision", "") or "")
            lines = [
                f"The election is {phase_label.lower()}. {issue} is the question people keep returning to.",
                f"{mayor} holds the office, with {mandate.lower()} as the election mandate.",
                "I care less about a slogan than whether the road, shop, clinic, and homes work when people need them.",
            ]
            if role in {"Mayor", "Clerk"}:
                lines.append(
                    "The notice board has the election date, current portfolios, and public decisions in writing."
                )
            if latest:
                lines.append(f"The latest decision on the public record is: {latest}")
            return lines
        if topic == "weather":
            weather = str(context.get("weather", "sunny")).lower()
            lines = list(WEATHER_DIALOGUE.get(weather, (
                f"This {weather} weather is changing how everyone moves through town.",
                "I check the sky before I trust the day's plan.",
            )))
            if role in {"Carpenter", "Carpenter Apprentice", "Mechanic"}:
                lines.append("Weather exposes weak roofs, swollen boards, and neglected fittings. It's an unpleasant but accurate inspection.")
            if role in {"Doctor", "Nurse"}:
                lines.append("Bad weather changes who comes to the clinic and who decides to wait longer than they should.")
            if role in {"Merchant", "Shopkeeper", "Stockkeeper", "Innkeeper"}:
                lines.append("The weather changes deliveries first, prices second, and people's tempers shortly afterward.")
            if member_names and context.get("bad_weather"):
                lines.append(f"I'll feel better once I know {member_names[0]} is home and out of this.")
            return lines
        if topic == "season":
            season = str(context.get("season", "spring")).lower()
            lines = list(SEASON_DIALOGUE.get(season, (
                f"{season.title()} has its own opinion about how the settlement should work.",
            )))
            if role in {"Gardener", "Cook", "Shopkeeper", "Innkeeper"}:
                lines.append(f"What grows and arrives in {season} changes what people eat, trade, and expect to find on a shelf.")
            if role in {"Carpenter", "Mechanic", "Well Keeper"}:
                lines.append(f"This is the season when I discover which maintenance from last year was actually finished.")
            if hobbies:
                lines.append(f"I make more time for {hobbies[0]} in {season}, or at least I claim I will.")
            return lines
        if topic == "concerns":
            lines = []
            if morale < 45:
                lines.append("The pace of work is wearing people down. Nothing dramatic has happened, which is why it would be easy to ignore.")
            if vacancies:
                lines.append(f"Those {vacancies} unfilled jobs worry me. A locked service is still absent, no matter how fine the building looks.")
            if market:
                lines.append(f"The shortage of {market.get('demand', 'necessary supplies')} is becoming more than an inconvenience.")
            if context.get("bad_weather"):
                lines.append("I'm thinking about the households farthest from shelter. Difficult weather makes small distances matter.")
            if rival_name:
                lines.append(f"I worry that my disagreement with {rival_name} is becoming easier to repeat than to resolve.")
            lines.extend([
                "Growth can hide neglect. A new building draws attention away from the door, bridge, or household already having trouble.",
                "I don't think the town is in danger. I do think ordinary problems become serious when everybody assumes someone else has noticed.",
            ])
            return lines
        if topic == "rumor":
            lines = [
                str(resident.get("rumor", "People are already debating what the settlement should build next.")),
                "I can't promise the story improved by passing through three households, but it certainly became more detailed.",
            ]
            if friend_name:
                lines.append(f"{friend_name} heard that something along the regional road has changed. They were careful about what they claimed to know.")
            if rival_name:
                lines.append(f"Someone says {rival_name} is preparing a proposal of their own. That may be fact, suspicion, or wishful thinking.")
            if event:
                lines.append(f"Most of today's talk concerns {event.get('name', 'the town gathering')}. The versions already disagree about who started it.")
            civic = context.get("civic", {}) if isinstance(context.get("civic"), dict) else {}
            if civic.get("latest_decision"):
                lines.append(f"People are still arguing about the latest public decision: {civic.get('latest_decision')}")
            return lines
        if topic == "personal":
            goal = str(resident.get("goal", "Build a stable life here."))
            lines = [
                f"What I want, honestly? {goal}",
                (
                    f"You have become a {tier.lower()}, which means I can answer without turning everything into polite weather."
                ),
                (
                    f"People call me {traits[0].lower()}."
                    + (f" They are not wrong, though {traits[1].lower()} is closer on difficult days." if len(traits) > 1 else "")
                    if traits
                    else "I'm still deciding which parts of me belong to this place."
                ),
            ]
            if hobbies:
                lines.append(f"I would like a life with enough room left in it for {hobbies[0]}, not only work and recovery from work.")
            if friend_name:
                lines.append(f"Part of what keeps me here is knowing {friend_name} would notice if I left without saying goodbye.")
            if morale < 40:
                lines.append("I'm proud of what I do, but I don't want exhaustion to become the only proof that it matters.")
            return lines
        if topic == "memory":
            if recent_memories:
                lines = [f"I remember this clearly: {memory}" for memory in recent_memories[-3:]]
                lines.extend([
                    "Small moments are often the ones that change how I expect you to behave the next time.",
                    "We have enough shared history now that I don't have to judge you only by your latest decision.",
                ])
                return lines
            return ["We haven't made enough history together for me to pretend otherwise."]
        if topic == "secret":
            lines = [
                str(resident.get("friend_secret", "I'm still deciding whether this place can become permanent.")),
                "I don't tell everyone that. Please let it remain mine to share.",
            ]
            if "Bold" in traits:
                lines.append("People mistake confidence for certainty. I'm often afraid; I've simply learned how I want to act while afraid.")
            if "Cheerful" in traits:
                lines.append("Being the cheerful person can become a job nobody remembers assigning. Some days I don't have the energy for it.")
            if "Reserved" in traits:
                lines.append("Sometimes I wait so long to say what matters that silence starts making the decision for me.")
            if "Protective" in traits:
                lines.append("I'm better at noticing other people's limits than admitting my own.")
            return lines
        if topic == "request":
            request = sanitize_procedural_request(resident.get("active_request", {}))
            if request and request.get("status") == "completed":
                return [
                    f"You already finished {str(request.get('title', 'that work')).lower()}. I haven't forgotten.",
                    "Let me solve at least one of my own problems before I bring you another.",
                ]
            if request:
                offer = str(request.get("offer_text") or request.get("description") or "I could use some practical help.")
                lines = [offer]
                if request.get("objective_summary"):
                    lines.append(str(request["objective_summary"]))
                lines.append(f"The pay is {request.get('reward_money')}g. More importantly, I'll remember who followed through.")
                if str(request.get("status")) == "active":
                    lines.append("You already agreed to this. Ask if you need the details again; I would rather repeat them than have you guess.")
                elif str(request.get("status")) == "ready":
                    lines.append("It looks like you have done what I asked. We can settle it now.")
                return lines
            return ["I don't need anything specific right now, which is rare enough to appreciate."]

        generic: List[str] = [
            f"Good to see you. I was {activity}.",
            f"{settlement} has been busy today, though not always in the places people expected.",
            "Some days a short conversation is enough to make the work feel less solitary.",
            f"I've been thinking about {str(job_profile.get('daily_focus', 'the work still ahead')).lower()}.",
            f"The {str(context.get('weekday', 'day')).lower()} routine feels slightly different this week.",
        ]
        for trait in traits:
            generic.extend(TRAIT_CHAT_LINES.get(trait, ()))
        generic.extend(RELATIONSHIP_CHAT_LINES.get(tier, ()))
        if friend_name:
            generic.append(f"I spoke with {friend_name} earlier. They gave me something worth thinking about, even if I'm not ready to repeat it.")
        if recent_memories and tier in {"Friend", "Close Friend"}:
            generic.append(f"I was thinking about the last thing we did together: {recent_memories[-1]}")
        if phase == "late":
            generic.append("It's late enough that I'm no longer pretending tomorrow's work belongs to today.")
        if context.get("bad_weather"):
            generic.append("The weather has shortened everybody's plans and lengthened every indoor conversation.")
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
        context = {
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
        plan = self.procedural_town_plan(int(chunk_x), int(chunk_y))
        if plan:
            identity = (
                self.procedural_town_identity(plan)
                if hasattr(self, "procedural_town_identity") else {}
            )
            market = (
                self.procedural_town_market_profile(plan)
                if hasattr(self, "procedural_town_market_profile") else {}
            )
            event = (
                self.procedural_town_active_event(plan)
                if hasattr(self, "procedural_town_active_event") else {}
            )
            context["settlement"] = {
                "name": str(plan.get("name", "the settlement")),
                "specialty": str(plan.get("specialty", "") or ""),
                "identity": dict(identity or {}),
                "market": dict(market or {}),
                "event": dict(event or {}),
                "geography": dict(plan.get("geography", {}) or {}),
                "development": (
                    self.procedural_town_development_tier(plan)
                    if hasattr(self, "procedural_town_development_tier") else ""
                ),
            }
        if plan and hasattr(self, "ensure_procedural_town_politics"):
            politics = self.ensure_procedural_town_politics(plan)
            latest_records = (
                list(politics.get("policy_change_log", []) or [])
                + list(politics.get("edict_log", []) or [])
                + list(politics.get("zoning_log", []) or [])
                + list(politics.get("municipal_build_log", []) or [])
                + list(politics.get("result_log", []) or [])
            )
            incumbent_id = str(politics.get("incumbent_id", ""))
            mayor = (
                self.procedural_candidate_name(incumbent_id, plan)
                if hasattr(self, "procedural_candidate_name")
                else "the mayor"
            )
            issue = (
                self.procedural_town_election_issue(plan).get("name", "ordinary town business")
                if hasattr(self, "procedural_town_election_issue")
                else "ordinary town business"
            )
            context["civic"] = {
                "phase": self.procedural_election_phase(plan),
                "mayor": mayor,
                "issue": issue,
                "mandate": str(politics.get("current_policy", "Public Works")),
                "latest_decision": str(latest_records[-1]) if latest_records else "",
            }
        return context

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
        if str(resident.get("age_group", "Adult")) == "Child":
            return {}
        context = self.procedural_settlement_dialogue_context(chunk_x, chunk_y)
        existing = sanitize_procedural_request(resident.get("active_request", {}))
        cycle_key = str(self.quest_absolute_day() // 7)

        # Convert item-only requests from older saves into ordinary unified
        # quests. The player keeps both their progress and the promised reward.
        if existing and not existing.get("quest_id") and existing.get("item"):
            quest = self.procedural_legacy_request_quest(
                chunk_x, chunk_y, resident, population, existing
            )
            self.register_quest(quest, accept=str(existing.get("status")) == "active")
            existing = self.procedural_request_summary(self.quest_record(str(quest["id"])))
            resident["active_request"] = existing
            resident["last_request_cycle"] = cycle_key
            return copy.deepcopy(existing)

        if existing and existing.get("quest_id"):
            quest = self.quest_record(str(existing["quest_id"]))
            if quest:
                existing = self.procedural_request_summary(quest)
                resident["active_request"] = existing
                if str(quest.get("status")) in {"offered", "active", "ready"}:
                    return copy.deepcopy(existing)
                if str(resident.get("last_request_cycle", "")) == cycle_key:
                    return copy.deepcopy(existing)

        if str(resident.get("last_request_cycle", "")) == cycle_key and existing:
            return copy.deepcopy(existing)
        quest = self.build_procedural_resident_quest(
            chunk_x, chunk_y, resident, population, context, cycle_key
        )
        if not quest:
            return {}
        registered = self.register_quest(quest, accept=False)
        request = self.procedural_request_summary(registered)
        resident["active_request"] = request
        resident["last_request_cycle"] = cycle_key
        resident["last_request_day"] = str(context["day_key"])
        recent_types = [
            str(value) for value in resident.get("recent_request_types", [])
            if str(value) != str(quest.get("request_type", ""))
        ]
        recent_types.append(str(quest.get("request_type", "")))
        resident["recent_request_types"] = recent_types[-3:]
        return copy.deepcopy(request)

    def procedural_quest_destination(
        self, chunk_x: int, chunk_y: int, label: str
    ) -> Dict[str, object]:
        destination: Dict[str, object] = {
            "location": "Wilderness", "chunk_x": int(chunk_x),
            "chunk_y": int(chunk_y), "label": str(label),
        }
        if hasattr(self, "wilderness_world_coords"):
            world_x, world_y = self.wilderness_world_coords(
                int(chunk_x), int(chunk_y), 43, 19
            )
            destination.update({"world_x": int(world_x), "world_y": int(world_y)})
        else:
            destination.update({"x": 43, "y": 19})
        return destination

    def procedural_request_summary(self, quest: Dict[str, object]) -> Dict[str, object]:
        if not isinstance(quest, dict) or not quest:
            return {}
        objectives = [row for row in quest.get("objectives", []) if isinstance(row, dict)]
        stage = max(0, min(len(objectives) - 1, int(quest.get("stage", 0) or 0))) if objectives else 0
        current = objectives[stage] if objectives else {}
        rewards = dict(quest.get("rewards", {}) or {})
        summary = {
            "id": str(quest.get("id", "")),
            "quest_id": str(quest.get("id", "")),
            "title": str(quest.get("title", "A Resident's Request")),
            "description": str(quest.get("description", "")),
            "offer_text": str(quest.get("offer_text", quest.get("description", ""))),
            "objective_summary": str(current.get("description", "Continue the request.")),
            "request_type": str(quest.get("request_type", "errand")),
            "cycle_key": str(quest.get("cycle_key", "")),
            "reward_money": max(0, int(rewards.get("money", 0) or 0)),
            "reward_relationship": max(0, int(quest.get("procedural_relationship_reward", 0) or 0)),
            "created_day": str(quest.get("created_day", quest.get("offered_day", ""))),
            "status": str(quest.get("status", "offered")),
        }
        if str(current.get("kind", "")) == "item":
            summary["item"] = str(current.get("item", ""))
            summary["quantity"] = max(1, int(current.get("target", 1) or 1))
        return summary

    def procedural_legacy_request_quest(
        self,
        chunk_x: int,
        chunk_y: int,
        resident: Dict[str, object],
        population: Dict[str, object],
        request: Dict[str, object],
    ) -> Dict[str, object]:
        item = str(request.get("item", "Wood"))
        quantity = max(1, int(request.get("quantity", 1) or 1))
        settlement = str(population.get("settlement_name", "the settlement"))
        return {
            "id": str(request.get("id", f"proc-request:{resident.get('id')}:legacy")),
            "title": str(request.get("title", f"A Delivery for {resident.get('given_name', 'a resident')}")),
            "category": "Town",
            "description": str(request.get("description", f"Bring {quantity_item_phrase(item, quantity)} to {resident.get('name', 'the resident')}.")),
            "offer_text": str(request.get("description", f"I need {quantity_item_phrase(item, quantity)} for my work.")),
            "giver_id": str(resident.get("id", "")),
            "giver_name": str(resident.get("name", "Resident")),
            "request_type": "delivery",
            "procedural_resident_quest": True,
            "procedural_town_chunk": [int(chunk_x), int(chunk_y)],
            "objectives": [{
                "id": "delivery", "kind": "item", "item": item,
                "description": f"Carry {quantity_item_phrase(item, quantity)} back to {resident.get('given_name', 'the resident')}.",
                "current": 0, "target": quantity, "complete": False, "consume": True,
            }],
            "turn_in": self.procedural_quest_destination(chunk_x, chunk_y, settlement),
            "require_turn_in": False,
            "rewards": {"money": int(request.get("reward_money", 0) or 0), "xp": 10, "reputation": 1},
            "procedural_relationship_reward": int(request.get("reward_relationship", 5) or 5),
            "created_day": str(request.get("created_day", "")),
            "completion_text": f"You completed {resident.get('given_name', 'the resident')}'s delivery.",
        }

    def build_procedural_resident_quest(
        self,
        chunk_x: int,
        chunk_y: int,
        resident: Dict[str, object],
        population: Dict[str, object],
        context: Dict[str, object],
        cycle_key: str,
    ) -> Dict[str, object]:
        role = str(resident.get("role", "Settler"))
        choices = list(PROCEDURAL_QUEST_ARCHETYPES.get(role, PROCEDURAL_QUEST_ARCHETYPES["Settler"]))
        recent = set(str(value) for value in resident.get("recent_request_types", [])[-2:])
        fresh = [value for value in choices if value not in recent] or choices
        seed = stable_text_seed(f"{resident.get('id')}:{cycle_key}:quest")
        rng = random.Random(seed)
        request_type = fresh[rng.randrange(len(fresh))]
        other_residents = [
            row for row in population.get("residents", {}).values()
            if isinstance(row, dict) and str(row.get("id")) != str(resident.get("id"))
            and str(row.get("age_group", "Adult")) != "Child"
        ]
        if request_type == "neighbors" and not other_residents:
            request_type = "survey"
        settlement = str(population.get("settlement_name", "the settlement"))
        given_name = str(resident.get("given_name") or resident.get("name") or "the resident")
        role_title = str(resident.get("job_title") or resident.get("profession") or role).lower()
        quest_id = (
            f"proc-quest:{procedural_slug(settlement)}:{procedural_slug(resident.get('id'))}:"
            f"{cycle_key}:{request_type}"
        )
        objectives: List[Dict[str, object]] = []
        offer_text = ""
        title = ""
        if request_type == "delivery":
            item, minimum, maximum, purpose = rng.choice(REQUEST_POOLS.get(role, REQUEST_POOLS["Settler"]))
            quantity = rng.randint(int(minimum), int(maximum))
            title = f"Supplies for {given_name}"
            offer_text = f"I'm short of {quantity_item_phrase(item, quantity)} {purpose}. Could you bring it to me?"
            objectives.append({
                "id": "delivery", "kind": "item", "item": item,
                "description": f"Bring {quantity_item_phrase(item, quantity)} to {given_name} in {settlement}.",
                "current": 0, "target": quantity, "complete": False, "consume": True,
            })
        elif request_type == "harvest":
            quantity = rng.randint(3, 6)
            title = f"Fresh Produce for {settlement}"
            offer_text = f"The town could use fresher produce than the road is bringing. Would you harvest {quantity} crops for us?"
            objectives.append({
                "id": "harvest", "kind": "harvest", "target_tag": "crop",
                "description": f"Harvest {quantity} crops of any kind.",
                "current": 0, "target": quantity, "complete": False,
            })
        elif request_type == "fish":
            quantity = rng.randint(2, 4)
            geography = context.get("settlement", {}).get("geography", {}) if isinstance(context.get("settlement"), dict) else {}
            fish_tag = "ocean" if "waterfront" in str(geography.get("water_access", "")) and rng.randrange(3) == 0 else "freshwater"
            water_label = "ocean fish" if fish_tag == "ocean" else "freshwater fish"
            title = f"A Catch for {given_name}"
            offer_text = f"I need {quantity} {water_label} for the next few meals. Would you catch them yourself?"
            objectives.append({
                "id": "fish", "kind": "fish", "target_tag": fish_tag,
                "description": f"Catch {quantity} {water_label}.",
                "current": 0, "target": quantity, "complete": False,
            })
        elif request_type == "craft":
            quantity = rng.randint(1, 3)
            title = f"Made by Hand"
            offer_text = f"As the {role_title}, I can use a few things made locally instead of ordered from far away. Could you craft {quantity}?"
            objectives.append({
                "id": "craft", "kind": "craft", "target_tag": "crafted",
                "description": f"Craft {quantity} useful item{'s' if quantity != 1 else ''}.",
                "current": 0, "target": quantity, "complete": False,
            })
        elif request_type == "danger":
            quantity = rng.randint(2, 4)
            title = f"Safer Roads Near {settlement}"
            offer_text = f"Travelers have reported hostile creatures near the roads. Defeat {quantity} enemies before somebody gets cornered."
            objectives.append({
                "id": "danger", "kind": "defeat", "target_tag": "enemy",
                "description": f"Defeat {quantity} hostile enemies.",
                "current": 0, "target": quantity, "complete": False,
            })
        elif request_type == "salvage":
            quantity = rng.randint(2, 4)
            title = f"Useful Things Left Behind"
            offer_text = f"Old sites around here still hold usable material. Search containers and recover {quantity} pieces of loot."
            objectives.append({
                "id": "salvage", "kind": "loot",
                "description": f"Take {quantity} items from containers or fallen enemies.",
                "current": 0, "target": quantity, "complete": False,
            })
        elif request_type == "neighbors":
            rng.shuffle(other_residents)
            targets = other_residents[:min(2, len(other_residents))]
            names = [str(row.get("given_name") or row.get("name")) for row in targets]
            title = "Check on the Neighbors"
            offer_text = f"I haven't had time to check on {', then '.join(names)}. Would you speak with them and come back?"
            for index, target in enumerate(targets):
                target_name = str(target.get("given_name") or target.get("name"))
                objectives.append({
                    "id": f"talk:{index}", "kind": "talk", "target_id": str(target.get("id", "")),
                    "description": f"Speak with {target_name}.", "current": 0,
                    "target": 1, "complete": False,
                })
        else:
            directions = [(1, 0, "east"), (-1, 0, "west"), (0, 1, "south"), (0, -1, "north")]
            rng.shuffle(directions)
            title = f"Road Survey for {settlement}"
            offer_text = "Two nearby stretches of road need a first-hand look. Visit them, then tell me what the route is like."
            for index, (dx, dy, direction) in enumerate(directions[:2]):
                target_label = f"the {direction} approach to {settlement}"
                objectives.append({
                    "id": f"survey:{index}", "kind": "visit",
                    "description": f"Survey {target_label}.", "current": 0,
                    "target": 1, "complete": False,
                    "destination": self.procedural_quest_destination(chunk_x + dx, chunk_y + dy, target_label),
                    "destination_radius": 24,
                })
        relationship_reward = 5 + len(objectives) + rng.randint(0, 3)
        money_reward = 90 + sum(max(1, int(row.get("target", 1) or 1)) for row in objectives) * 28 + len(objectives) * 35
        return {
            "id": quest_id, "title": title, "category": "Town",
            "description": offer_text, "offer_text": offer_text,
            "giver_id": str(resident.get("id", "")), "giver_name": str(resident.get("name", "Resident")),
            "request_type": request_type, "cycle_key": cycle_key,
            "procedural_resident_quest": True,
            "procedural_town_chunk": [int(chunk_x), int(chunk_y)],
            "objectives": objectives, "stage": 0,
            "turn_in": self.procedural_quest_destination(chunk_x, chunk_y, settlement),
            "require_turn_in": False,
            "rewards": {"money": money_reward, "xp": 12 + len(objectives) * 4, "reputation": 1},
            "procedural_relationship_reward": relationship_reward,
            "created_day": str(context.get("day_key", "")),
            "completion_text": f"You finished {given_name}'s request.",
        }

    def accept_procedural_settlement_request(
        self, chunk_x: int, chunk_y: int, resident_id: str
    ) -> bool:
        request = self.ensure_procedural_resident_request(chunk_x, chunk_y, resident_id)
        quest_id = str(request.get("quest_id", ""))
        if not quest_id or not self.accept_quest(quest_id):
            return False
        resident = self.procedural_settlement_resident_record(chunk_x, chunk_y, resident_id)
        if resident:
            resident["active_request"] = self.procedural_request_summary(self.quest_record(quest_id))
        return True

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
        if hasattr(self, "record_quest_event"):
            self.record_quest_event(
                "talk",
                target_id=str(resident.get("id", "")),
                target_name=str(resident.get("name", "Resident")),
                target_tags=["resident", procedural_slug(resident.get("role", "settler"))],
                amount=1,
                location=str(getattr(self.state, "location", "")),
                note=f"Spoke with {resident.get('name', 'a resident')} in {population.get('settlement_name', 'the settlement')}.",
            )
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
        quest_id = str(request.get("quest_id", ""))
        quest = self.quest_record(quest_id) if quest_id else {}
        if quest:
            self.refresh_quest_states()
            request = self.procedural_request_summary(self.quest_record(quest_id))
            resident["active_request"] = request
        status = str(request.get("status", "offered"))
        if status == "completed":
            return "Completed"
        if status == "offered":
            return "Available"
        if status == "ready":
            return "Ready"
        if status == "abandoned":
            return "No longer available"
        if request.get("item"):
            item = str(request["item"])
            quantity = int(request.get("quantity", 1) or 1)
            carried = int(getattr(self.state, "inventory", {}).get(item, 0) or 0)
            missing = quantity - carried
            return "Ready" if missing <= 0 else f"Need {missing} more {item_name_for_quantity(item, missing)}"
        return str(request.get("objective_summary", "In progress"))

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
        quest_id = str(request.get("quest_id", ""))
        if not request or not quest_id:
            return False
        self.refresh_quest_states()
        quest = self.quest_record(quest_id)
        if not quest or str(quest.get("status", "")) != "ready":
            return False
        reward_money = int(dict(quest.get("rewards", {}) or {}).get("money", 0) or 0)
        relationship_reward = int(quest.get("procedural_relationship_reward", 0) or 0)
        if not self.complete_quest(quest_id):
            return False
        resident["relationship"] = min(
            250,
            int(resident.get("relationship", 0) or 0)
            + relationship_reward,
        )
        request = self.procedural_request_summary(self.quest_record(quest_id))
        resident["active_request"] = request
        completed = list(resident.get("completed_request_ids", []) or [])
        if quest_id not in completed:
            completed.append(quest_id)
        resident["completed_request_ids"] = completed[-20:]
        memory = (
            f"{getattr(self.state, 'date_label', request.get('created_day'))} - "
            f"{getattr(self.state, 'player_name', 'The farmer')} completed "
            f"{str(request.get('title', 'a request')).lower()}."
        )
        memories = list(resident.get("memories", []) or [])
        if memory not in memories:
            memories.append(memory)
        resident["memories"] = memories[-16:]
        message = (
            f"Completed {resident.get('name')}'s request. "
            f"Earned {reward_money}g and "
            f"{relationship_reward} relationship."
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
            return ["No resident was found."]
        lines = [
            f"{result.get('speaker')}",
            f"Topic: {str(result.get('topic', 'chat')).title()}",
            f"How they know you: {result.get('relationship_tier')}",
            "",
            f'"{result.get("text")}"',
        ]
        if result.get("follow_up"):
            lines.extend(["", f'"{result.get("follow_up")}"'])
        if int(result.get("relationship_gain", 0) or 0):
            lines.extend(["", "The conversation leaves you on warmer terms."])
        request = result.get("request", {})
        if isinstance(request, dict) and request and str(result.get("topic")) == "request":
            lines.extend([
                "",
                f"Objective: {request.get('objective_summary', request.get('description', 'Continue the request.'))}",
                f"Reward: {request.get('reward_money')}g and improved relations",
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
            self.set_message("No resident was found.")
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
