from __future__ import annotations

"""Turn-by-turn, knowledge-aware conversations shared by every NPC family.

The game used to present several unrelated generated remarks at once and then
require the same social-response quiz. This module keeps one conversational
subject on screen: an opening, one relevant matter, follow-up questions, and a
closing.
"""

import hashlib
import re
import sys
import textwrap
from typing import Dict, List, Optional, Sequence, Tuple

from ascii_farmstead_data import (
    MENU_CONFIRM_KEYS,
    RELATIONSHIP_DATING_REQUIRED_FRIENDSHIP,
    RELATIONSHIP_DATING_REQUIRED_TALKS,
    RELATIONSHIP_TALK_GAIN,
    TOWN_BUILDING_DATA,
)
from ascii_farmstead_dialogue_library import contextual_dialogue_line
from ascii_farmstead_helpers import clause_from_sentence, kinship_term, name_list, pronouns_for_sex, quantity_agreement, quantity_item_phrase
from ascii_farmstead_npc_builder import FEMALE_GIVEN_NAMES, MALE_GIVEN_NAMES, SURNAMES
from ascii_farmstead_relationship_dialogue import (
    child_household_line,
    romance_flirt_response,
    romance_status_line,
    spouse_household_line,
    child_stage_group,
    spouse_stage_group,
)
from ascii_farmstead_custom_story import (
    apply_custom_dialogue_override,
    dialogue_variable_context,
)
from ascii_farmstead_support import C, clear_screen, colorize, normalize_key, read_key
from ascii_farmstead_ui import fit_text, pad_to, strip_ansi, terminal_height, terminal_width


DialogueOption = Tuple[str, str, str]


ROLE_INTERESTS: Dict[str, Tuple[str, ...]] = {
    "Mayor": ("local history", "civic planning", "public festivals"),
    "Seed Seller": ("gardening", "seasonal cooking", "crop journals"),
    "Blacksmith": ("metalwork", "mining", "tool design"),
    "Carpenter": ("woodworking", "architecture", "bridge design"),
    "Animal Keeper": ("animal care", "riding", "country fairs"),
    "Librarian": ("reading", "local history", "quiet walks"),
    "Traveler": ("maps", "roadside stories", "exploration"),
    "Doctor": ("herbal remedies", "medical journals", "walking"),
    "Innkeeper": ("cooking", "card games", "traveler stories"),
    "Chef": ("cooking", "foraging", "recipe collecting"),
    "Market Vendor": ("collecting", "local gossip", "festivals"),
    "Gardener": ("gardening", "flowers", "weather watching"),
    "Fisher": ("fishing", "boats", "weather watching"),
    "Miner": ("geology", "cave exploration", "tool collecting"),
    "Courier": ("running", "maps", "roadside news"),
    "Artist": ("painting", "color", "festivals"),
    "Orchardist": ("orchards", "preserving fruit", "beekeeping"),
    "Tailor": ("sewing", "fashion", "color"),
    "Musician": ("music", "tavern performances", "local stories"),
    "Beekeeper": ("beekeeping", "flowers", "woodworking"),
    "Botanist": ("botany", "foraging", "field journals"),
    "Mechanic": ("machines", "tool design", "puzzles"),
    "Scholar": ("history", "maps", "board games"),
    "Retiree": ("local history", "gardening", "people watching"),
    "Ranger": ("hiking", "wildlife", "maps"),
    "Hunter": ("tracking", "campcraft", "wildlife"),
    "Researcher": ("field research", "maps", "collecting samples"),
}

SERVICE_ROLE_WORDS = {
    "mayor", "clerk", "seller", "shopkeeper", "vendor", "merchant",
    "doctor", "nurse", "innkeeper", "chef", "bartender", "librarian",
    "blacksmith", "carpenter", "mechanic", "tailor", "sheriff", "deputy",
}
WARM_PERSONALITY_WORDS = {
    "cheerful", "warm", "friendly", "hospitable", "upbeat", "energetic",
    "gentle", "kind", "talkative", "optimistic", "patient",
}
SKEPTICAL_PERSONALITY_WORDS = {
    "skeptical", "suspicious", "wary", "shrewd", "guarded", "pragmatic",
    "protective", "cautious", "opportunistic", "restless",
}
BLUNT_PERSONALITY_WORDS = {
    "gruff", "blunt", "exacting", "stubborn", "stern", "direct", "wry",
    "impatient", "abrasive", "severe",
}
RESERVED_PERSONALITY_WORDS = {
    "quiet", "reserved", "observant", "solitary", "calm", "archival",
    "methodical", "private", "reclusive", "measured",
}


DIALOGUE_ARC_PROFILES: Dict[str, Dict[str, object]] = {
    "roads": {
        "title": "A Route in Question",
        "roles": {"ranger", "hunter", "courier", "traveler", "fisher", "pilot", "warden", "guide"},
        "stages": (
            "One of my regular routes has become unreliable. I have been taking the long way around until I know why.",
            "Two other travelers reported the same trouble. I am marking a safer detour before someone gets stranded.",
            "The detour is marked. I want to walk it once in bad weather before I recommend it to anyone else.",
            "The new route held up. Travelers have started using my markers without needing directions.",
        ),
    },
    "work": {
        "title": "Pressure at Work",
        "roles": {"seller", "merchant", "vendor", "innkeeper", "chef", "blacksmith", "carpenter", "mechanic", "tailor"},
        "stages": (
            "I have taken on more work than I can finish properly. Two customers are already waiting on me.",
            "I sorted the orders by when they are actually needed. One person complained, but the list finally makes sense.",
            "I am changing how I accept new orders. I would rather turn work away than promise what I cannot deliver.",
            "The new schedule is working. I finish fewer jobs late, and people know when to expect me.",
        ),
    },
    "care": {
        "title": "Someone Needs Care",
        "roles": {"doctor", "nurse", "healer", "animal", "keeper", "gardener", "herbalist"},
        "stages": (
            "Someone I look after has not been doing well. I am worried, though I try not to show it around them.",
            "Their condition is clearer now. Rest will help more than another hurried remedy.",
            "They are improving. The hard part is keeping the routine steady once everyone stops worrying.",
            "They are stable now. We still follow the care schedule, but it no longer controls the whole day.",
        ),
    },
    "research": {
        "title": "An Unfinished Finding",
        "roles": {"librarian", "scholar", "researcher", "botanist", "archivist", "artist"},
        "stages": (
            "I noticed the same pattern in several records. I need another sample before I trust it.",
            "A second set of notes shows it too. I want to check somewhere beyond the original survey area.",
            "The evidence is consistent enough to share. I expect someone will find a question I missed.",
            "Other researchers checked the result and found the same pattern. We know what to investigate next.",
        ),
    },
    "community": {
        "title": "A Community Decision",
        "roles": {"mayor", "clerk", "sheriff", "deputy", "retiree"},
        "stages": (
            "Two groups want different uses for the same public space. Both have a fair reason to care about it.",
            "I met with both sides. They disagree about the solution, but at least they agree on the actual problem now.",
            "There is enough room to try a shared schedule. Neither side loves it, but both agreed to test it.",
            "The shared schedule is still in place. Complaints have slowed down, and people are using the space again.",
        ),
    },
    "personal": {
        "title": "A Personal Crossroads",
        "roles": set(),
        "stages": (
            "I have fallen into a routine I never really chose. Lately I have been wondering what to change.",
            "I know which part of the routine matters to me and which part I only kept out of habit.",
            "I made one small change rather than overturning the whole week. So far, I can keep it up.",
            "The change has lasted. My days feel less automatic now.",
        ),
    },
}

STORY_AFTERMATH_PROFILES: Dict[str, Dict[str, str]] = {
    "roads": {
        "summary": "The revised route held under real travel and is becoming part of local habit.",
        "activity": "checking the revised route and comparing travelers' reports",
        "follow_up": "The new route is holding. Travelers have started following the markers on their own.",
    },
    "work": {
        "summary": "The new work order separated genuine priorities from constant emergencies.",
        "activity": "testing a steadier work order and protecting its priorities",
        "follow_up": "The new order held up during a busy day. I am keeping it.",
    },
    "care": {
        "summary": "A dependable care routine replaced the cycle of reacting only when something became urgent.",
        "activity": "maintaining the care routine that the household helped stabilize",
        "follow_up": "They are doing better. We are still following the care schedule, just to be safe.",
    },
    "research": {
        "summary": "The finding survived a second field test and changed what evidence people seek next.",
        "activity": "organizing the verified finding and planning the next survey",
        "follow_up": "Other researchers found the same pattern. We are planning the next survey now.",
    },
    "community": {
        "summary": "The compromise held long enough to become a shared public arrangement rather than one person's proposal.",
        "activity": "checking how the new community arrangement is working in practice",
        "follow_up": "The shared schedule is still working. Both groups have kept their side of the agreement.",
    },
    "personal": {
        "summary": "A small deliberate change became part of the routine instead of fading after one ambitious day.",
        "activity": "protecting the deliberate change that is now part of the routine",
        "follow_up": "The change has lasted. I do not have to remind myself to keep it up anymore.",
    },
}


def _stable_index(seed: str, size: int) -> int:
    if size <= 1:
        return 0
    digest = hashlib.sha256(str(seed).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % size


def _first_person(text: object, name: str = "") -> str:
    line = " ".join(str(text or "").strip().split())
    replacements = (
        (f"{name} wants", "I want"),
        (f"{name} keeps", "I keep"),
        (f"{name} thinks", "I think"),
        (f"{name} says", "I think"),
        ("They want", "I want"),
        ("They keep", "I keep"),
        ("They think", "I think"),
        ("She wants", "I want"),
        ("He wants", "I want"),
    )
    for source, replacement in replacements:
        if source and line.startswith(source):
            return replacement + line[len(source):]
    return line


_SPOKEN_CONTRACTIONS: Tuple[Tuple[str, str], ...] = (
    ("Will not", "Won't"), ("will not", "won't"),
    ("Would not", "Wouldn't"), ("would not", "wouldn't"),
    ("Could not", "Couldn't"), ("could not", "couldn't"),
    ("Should not", "Shouldn't"), ("should not", "shouldn't"),
    ("Cannot", "Can't"), ("cannot", "can't"),
    ("Can not", "Can't"), ("can not", "can't"),
    ("Do not", "Don't"), ("do not", "don't"),
    ("Does not", "Doesn't"), ("does not", "doesn't"),
    ("Did not", "Didn't"), ("did not", "didn't"),
    ("Is not", "Isn't"), ("is not", "isn't"),
    ("Are not", "Aren't"), ("are not", "aren't"),
    ("Was not", "Wasn't"), ("was not", "wasn't"),
    ("Were not", "Weren't"), ("were not", "weren't"),
    ("Has not", "Hasn't"), ("has not", "hasn't"),
    ("Have not", "Haven't"), ("have not", "haven't"),
    ("Had not", "Hadn't"), ("had not", "hadn't"),
    ("I am", "I'm"), ("I have", "I've"), ("I will", "I'll"), ("I would", "I'd"),
    ("You are", "You're"), ("you are", "you're"),
    ("You have", "You've"), ("you have", "you've"),
    ("You will", "You'll"), ("you will", "you'll"),
    ("You would", "You'd"), ("you would", "you'd"),
    ("We are", "We're"), ("we are", "we're"),
    ("We have", "We've"), ("we have", "we've"),
    ("We will", "We'll"), ("we will", "we'll"),
    ("We would", "We'd"), ("we would", "we'd"),
    ("They are", "They're"), ("they are", "they're"),
    ("They have", "They've"), ("they have", "they've"),
    ("They will", "They'll"), ("they will", "they'll"),
    ("They would", "They'd"), ("they would", "they'd"),
    ("It is", "It's"), ("it is", "it's"),
    ("It has", "It's"), ("it has", "it's"),
    ("That is", "That's"), ("that is", "that's"),
    ("That has", "That's"), ("that has", "that's"),
    ("There is", "There's"), ("there is", "there's"),
    ("What is", "What's"), ("what is", "what's"),
    ("Who is", "Who's"), ("who is", "who's"),
    ("Where is", "Where's"), ("where is", "where's"),
    ("Let us", "Let's"), ("let us", "let's"),
)

# These subject/auxiliary contractions need a following thought. Forms such as
# "It's." and "I've." are fragments when the expanded phrase was a complete
# short answer. Negative contractions ("I don't.") remain natural on their own.
_SPOKEN_CONTRACTIONS_REQUIRING_CONTINUATION = {
    expanded
    for expanded, _contracted in _SPOKEN_CONTRACTIONS
    if expanded.split(" ", 1)[0].casefold() in {
        "i", "you", "we", "they", "it", "that", "there",
        "what", "who", "where",
    }
}


# "I've seen it" is the perfect tense and reads naturally; "I've time", "do
# you've it" and "you've to let me finish" are not English at all. The
# contraction needs a past participle after it, so the rule is written as a
# requirement rather than a list of exclusions: a participle this table misses
# merely leaves the full form standing, while an exclusion it misses puts a
# broken sentence in front of the player.
#
# Regular participles are caught by the -ed suffix. There is deliberately no
# -en suffix rule, because "children", "kitchen" and "garden" would satisfy it
# and "I've children" is exactly the error being prevented.
_PERFECT_ADVERBS: Tuple[str, ...] = (
    "never", "already", "always", "just", "still", "ever", "only", "often",
    "recently", "finally", "nearly", "almost", "barely", "hardly", "simply",
    "actually", "certainly", "probably", "truly", "really", "since", "long",
)
_IRREGULAR_PARTICIPLES: Tuple[str, ...] = (
    "been", "seen", "gone", "done", "had", "got", "gotten", "made", "taken",
    "given", "come", "found", "said", "told", "known", "become", "left", "put",
    "kept", "heard", "brought", "thought", "run", "won", "lost", "met", "read",
    "written", "spoken", "eaten", "forgotten", "chosen", "driven", "ridden",
    "fallen", "grown", "drawn", "flown", "worn", "torn", "sworn", "borne",
    "shown", "sown", "blown", "thrown", "begun", "drunk", "sung", "sunk",
    "rung", "hung", "held", "felt", "meant", "sent", "spent", "built", "burnt",
    "learnt", "dealt", "slept", "swept", "crept", "leapt", "dreamt", "paid",
    "laid", "sold", "stood", "understood", "caught", "taught", "fought",
    "sought", "bought", "cost", "cut", "hit", "let", "set", "shut", "split",
)
_PERFECT_TENSE_GUARD = r"(?=\s+(?:(?:%s)\s+)*(?:%s|\w+ed)\b)" % (
    "|".join(_PERFECT_ADVERBS),
    "|".join(_IRREGULAR_PARTICIPLES),
)


_FIRST_PERSON_SUBJECT = re.compile(r"(?:\w+[ ,]+){0,2}I\b")


def _as_spoken_intent(text: object) -> str:
    """Give a bare role goal a speaker.

    Role definitions store goals as imperatives ("Keep records clear enough
    that no resident disappears between ledgers") because they read well as a
    profile line and after an explicit lead-in such as "What I want,
    honestly?". Delivered as a plain answer to "what do you want from life"
    they become orders, so a missing subject is supplied here rather than
    rewriting data that other callers rely on.
    """
    line = " ".join(str(text or "").split())
    if not line or _FIRST_PERSON_SUBJECT.match(line):
        return line
    head = line.rstrip(".")
    return f"I want to {head[:1].lower()}{head[1:]}."


def _as_spoken_sentence(fragment: object, frame: str) -> str:
    """Return a phrase as something an NPC can actually say aloud.

    Background fields arrive in two shapes. Authored world profiles store a
    complete first-person sentence ("I grew up in a busy household."), while
    the procedural town builder stores a bare phrase ("a household where
    everyone learned a trade") intended to be embedded. Concatenating the
    second kind produced lowercase run-ons with no verb, so a phrase gets a
    frame and a sentence is left alone.
    """
    text = " ".join(str(fragment or "").split())
    if not text:
        return ""
    if text[:1].isupper() and text[-1:] in ".!?":
        return text
    return frame.format(text.rstrip("."))


def naturalize_spoken_dialogue(text: object) -> str:
    """Use ordinary contractions in game-authored spoken dialogue."""
    line = str(text or "")
    for expanded, contracted in _SPOKEN_CONTRACTIONS:
        continuation_guard = (
            r"(?!\s*(?:[.!?,;\u2026]|$))"
            if expanded in _SPOKEN_CONTRACTIONS_REQUIRING_CONTINUATION
            else ""
        )
        preceding_guard = ""
        if expanded in _SPOKEN_CONTRACTIONS_REQUIRING_CONTINUATION:
            # "better at this than I am at that" keeps its full form; a
            # subject contraction stranded after a comparative reads as a
            # mistake rather than as natural speech.
            preceding_guard += r"(?<!\bthan )(?<!\bas )"
        if expanded.casefold().endswith((" have", " has")):
            continuation_guard += _PERFECT_TENSE_GUARD
        if expanded.casefold() == "it has":
            # In "living it has been simpler" the pronoun belongs to the
            # verb before it, so "it" is an object here and cannot take the
            # contraction the way a subject "it has" would.
            preceding_guard += r"(?<!ing )"
        if expanded.casefold() in {"what is", "who is", "where is"}:
            # "What's it like?" is ordinary speech, but "What's it?" and
            # "What's it now?" are not English -- the interrogative is the
            # complement and "it" is the subject, so there is nothing for the
            # contraction to lean on once the clause closes. Block only that
            # shape: a bare "it" (optionally plus a closing adverb) ending it.
            continuation_guard += (
                r"(?!\s+it(?:\s+(?:now|then|again|this\s+time))?\s*(?:[.!?,;…]|$))"
            )
        line = re.sub(
            rf"{preceding_guard}\b{re.escape(expanded)}\b(?!['â€™]){continuation_guard}",
            contracted,
            line,
        )
    return line


class DialogueFlowMixin:
    """A FarmGame mixin for coherent, advancing NPC conversations."""

    def dialogue_naturalize_spoken(self, text: object) -> str:
        return naturalize_spoken_dialogue(text)

    def dialogue_grounded_origin(
        self, actor: Dict[str, object], kind: str, current: str = ""
    ) -> str:
        """Return a geographic origin, never a shop, street, or placeholder."""
        candidates = (
            actor.get("origin_name"), actor.get("settlement_name"),
            actor.get("origin"), current,
        )
        rejected_words = {
            "street", "road", "avenue", "boulevard", "store", "shop",
            "inn", "clinic", "library", "hall", "blacksmith", "market row",
            "park", "private home", "some town", "nearby settlement",
        }
        for value in candidates:
            label = " ".join(str(value or "").split()).strip()
            folded = label.casefold()
            if label and not any(word in folded for word in rejected_words):
                return label
        if kind in {"authored", "spouse", "child"}:
            return "Elsewhere"
        try:
            chunk_x = int(actor.get("origin_chunk_x", actor.get("home_chunk_x", actor.get("chunk_x"))))
            chunk_y = int(actor.get("origin_chunk_y", actor.get("home_chunk_y", actor.get("chunk_y"))))
            return f"the region around ({chunk_x},{chunk_y})"
        except (TypeError, ValueError):
            return "the surrounding region"

    def dialogue_read_key(self) -> str:
        return read_key()

    def dialogue_actor_name(self, actor: Dict[str, object]) -> str:
        return str(actor.get("name", "Traveler") or "Traveler")

    def dialogue_actor_role(self, actor: Dict[str, object]) -> str:
        return str(
            actor.get("job_title")
            or actor.get("role")
            or actor.get("profession")
            or "Resident"
        )

    def dialogue_is_persistent_world_actor(
        self, actor: Dict[str, object], kind: str = "",
    ) -> bool:
        return bool(actor.get("world_npc_profile", False))

    def dialogue_world_actor_eligible(
        self, actor: Dict[str, object], kind: str,
    ) -> bool:
        actor_id = str(actor.get("id", "") or "")
        if not actor_id or actor_id.startswith(("child:", "household_child:", "enemy:")):
            return False
        if kind in {"authored", "procedural", "spouse", "child", "companion", "player"}:
            return bool(actor.get("world_npc_profile", False))
        return not bool(actor.get("temporary_only", False) or actor.get("non_person", False))

    def dialogue_promote_world_actor(
        self, actor: Dict[str, object], kind: str,
    ) -> Dict[str, object]:
        """Promote an ad-hoc world speaker into one persistent full NPC profile."""
        if not self.dialogue_world_actor_eligible(actor, kind):
            return actor
        profiles = getattr(self.state, "world_npc_profiles", None)
        if not isinstance(profiles, dict):
            profiles = {}
            self.state.world_npc_profiles = profiles
        actor_id = str(actor.get("id", "") or "")[:160]
        existing = profiles.get(actor_id)
        if isinstance(existing, dict):
            profile = existing
        else:
            digest = hashlib.sha256(actor_id.encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "big")
            sex = str(actor.get("sex", ""))
            if sex not in {"Female", "Male"}:
                sex = "Female" if seed % 2 == 0 else "Male"
            role = self.dialogue_actor_role(actor)
            supplied_name = str(actor.get("name", "") or "").strip()
            generic_names = {
                "", "resident", "traveler", "visitor", "caretaker", "manager",
                "worker", "ranger", "keeper", "homesteader", role.casefold(),
            }
            if supplied_name.casefold() in generic_names:
                given_pool = FEMALE_GIVEN_NAMES if sex == "Female" else MALE_GIVEN_NAMES
                supplied_name = (
                    f"{given_pool[seed % len(given_pool)]} "
                    f"{SURNAMES[(seed // 131) % len(SURNAMES)]}"
                )
            age = 21 + (seed % 35)
            personalities = (
                "Warm", "Reserved", "Practical", "Bold", "Patient", "Wry",
                "Skeptical", "Curious", "Blunt", "Gentle", "Restless", "Private",
            )
            traits = [
                personalities[(seed // divisor) % len(personalities)]
                for divisor in (7, 43, 211)
            ]
            traits = list(dict.fromkeys(traits))
            interests = list(ROLE_INTERESTS.get(role, ROLE_INTERESTS.get("Resident", ("local news", "walking", "practical crafts"))))
            broader_hobbies = (
                "card games", "fishing", "reading", "cooking", "woodworking",
                "gardening", "long walks", "music", "painting", "collecting maps",
                "animal care", "stargazing", "swimming", "repairing old tools",
            )
            hobbies = list(dict.fromkeys([
                *interests[:2],
                broader_hobbies[(seed // 19) % len(broader_hobbies)],
                broader_hobbies[(seed // 73) % len(broader_hobbies)],
            ]))[:4]
            origin = self.dialogue_grounded_origin(actor, kind)
            upbringings = (
                "I grew up in a busy household where privacy had to be negotiated.",
                "My family moved often, so I learned to judge places by the people who kept returning.",
                "I was raised around practical work and adults who expected promises to mean something.",
                "I had a quiet upbringing, with more books and solitary walks than crowds.",
                "Money was uneven when I was young, and I still notice waste faster than comfort.",
                "I grew up near working land, where weather could rearrange every plan before breakfast.",
            )
            turning_points = (
                "I chose this work after discovering that competence gave me more freedom than charm ever did.",
                "An early mistake taught me to ask better questions before acting certain.",
                "I once left this kind of life behind, then returned after learning what I actually missed.",
                "Someone trusted me with real responsibility before I felt ready, and I grew into it.",
                "A difficult season changed what I consider security and what I consider merely familiar.",
                "I followed another person's plan for years before deciding to build a life that felt like mine.",
            )
            family_stories = (
                "My parents are still living, though distance means we mostly keep in touch through letters.",
                "I have siblings scattered along different roads; affection survives even when schedules do not cooperate.",
                "Most of my family history is ordinary: work, disagreements, reconciliations, and people doing their best unevenly.",
                "I was raised by relatives who made room for me when plans changed. I do not forget that kind of loyalty.",
                "My family is small now, but we remain close enough to notice when someone goes quiet.",
                "I am not estranged from my family, exactly. We simply became people who understand one another better at a distance.",
            )
            ambitions = (
                "I want enough stability to choose my next step instead of merely reacting to it.",
                "I would like to become excellent at this work without letting it consume every private part of me.",
                "Eventually I want a home people enter because they are welcome, not because they need something.",
                "I want to see more of the world, but I also want somewhere I am genuinely expected to return to.",
                "I am trying to build a life with room for work, affection, and a little harmless irresponsibility.",
                "I want to leave something useful behind and still enjoy enough of my life to remember living it.",
            )
            role_folded = role.casefold()
            logically_adult = not any(word in role_folded for word in ("child", "student", "minor"))
            npc_spouse_id = str(actor.get("npc_spouse_id", "") or "")
            marital_status = str(
                actor.get("marital_status", "Married" if npc_spouse_id else "Single") or "Single"
            )
            profile = {
                "id": actor_id,
                "name": supplied_name or f"Traveler {seed % 997}",
                "role": role,
                "sex": sex,
                "age": age,
                "birth_year": max(1, int(getattr(self.state, "year", 1)) - age),
                "age_group": "Adult",
                "marital_status": marital_status,
                "npc_spouse_id": npc_spouse_id,
                "romanceable": bool(
                    actor.get("romanceable", logically_adult and marital_status == "Single")
                ),
                "deceased": bool(actor.get("deceased", False)),
                "world_npc_profile": True,
                "world_npc_kind": str(kind),
                "personality": traits[0] if traits else "Practical",
                "personality_traits": traits,
                "disposition": traits[1] if len(traits) > 1 else traits[0],
                "origin": origin,
                "origin_name": origin,
                "home_name": str(actor.get("home_name") or actor.get("home") or origin),
                "background": f"{upbringings[(seed // 17) % len(upbringings)]} {turning_points[(seed // 29) % len(turning_points)]}",
                "upbringing": upbringings[(seed // 17) % len(upbringings)],
                "formative_event": turning_points[(seed // 29) % len(turning_points)],
                "family_story": family_stories[(seed // 37) % len(family_stories)],
                "ambition": ambitions[(seed // 53) % len(ambitions)],
                "goal": ambitions[(seed // 53) % len(ambitions)],
                "hobbies": hobbies,
                "interests": hobbies,
                "likes": ["Wildflower Honey", "Berry Jam", "Wildflowers"],
                "relationship": max(0, int(actor.get("relationship", actor.get("bond", 0)) or 0)),
                "bond": max(0, int(actor.get("bond", actor.get("relationship", 0)) or 0)),
                "conversations": max(0, int(actor.get("conversations", 0) or 0)),
                "recent_conversation_topics": [],
                "color": str(actor.get("color", "White") or "White"),
            }
            profiles[actor_id] = profile

        # Refresh only world-facing context. Biography and relationship data
        # remain stable even when the source system rebuilds its actor dict.
        for field in (
            "role", "job_title", "profession", "activity", "runtime_activity",
            "runtime_location", "district", "origin", "origin_name", "home",
            "home_name", "destination_name", "settlement_name", "chunk_x", "chunk_y",
            "home_chunk_x", "home_chunk_y", "origin_chunk_x", "origin_chunk_y",
            "route_destination", "route_destination_name",
            "route_destination_chunk_x", "route_destination_chunk_y", "local_site_name",
            "x", "y", "color", "recurring", "regional_circulation",
        ):
            if field in actor and actor.get(field) not in (None, ""):
                profile[field] = actor[field]
        grounded_origin = self.dialogue_grounded_origin(
            actor, kind, str(profile.get("origin", "") or "")
        )
        profile["origin"] = grounded_origin
        profile["origin_name"] = grounded_origin
        canonical_relationship = int(
            getattr(self.state, "town_npc_relationships", {}).get(
                actor_id, profile.get("relationship", profile.get("bond", 0))
            ) or 0
        )
        canonical_conversations = int(
            getattr(self.state, "town_npc_dialogue_counts", {}).get(
                actor_id, profile.get("conversations", 0)
            ) or 0
        )
        profile["relationship"] = canonical_relationship
        profile["bond"] = canonical_relationship
        profile["conversations"] = canonical_conversations
        self.state.town_npc_relationships.setdefault(actor_id, canonical_relationship)
        self.state.town_npc_dialogue_counts.setdefault(actor_id, canonical_conversations)
        actor.clear()
        actor.update(profile)
        return actor

    def dialogue_commit_world_actor(
        self, actor: Dict[str, object], kind: str, interacted: bool,
    ) -> None:
        if not self.dialogue_is_persistent_world_actor(actor, kind):
            return
        actor_id = str(actor.get("id", "") or "")
        if not actor_id:
            return
        if interacted:
            today = self.dialogue_day_key()
            self.state.town_npc_dialogue_counts[actor_id] = (
                int(self.state.town_npc_dialogue_counts.get(actor_id, 0) or 0) + 1
            )
            if self.state.town_npc_last_talk_day.get(actor_id) != today:
                if hasattr(self, "adjust_town_npc_relationship"):
                    self.adjust_town_npc_relationship(actor_id, RELATIONSHIP_TALK_GAIN)
                self.state.town_npc_last_talk_day[actor_id] = today
        actor["conversations"] = int(self.state.town_npc_dialogue_counts.get(actor_id, 0) or 0)
        actor["relationship"] = int(self.state.town_npc_relationships.get(actor_id, 0) or 0)
        actor["bond"] = int(actor["relationship"])
        profile = dict(actor)
        for transient in ("_dialogue_kind", "_dialogue_group_partner"):
            profile.pop(transient, None)
        profile["world_npc_profile"] = True
        self.state.world_npc_profiles[actor_id] = profile

    def dialogue_library_line(
        self,
        actor: Dict[str, object],
        topic: str,
        salt: str = "",
    ) -> str:
        kind = str(actor.get("_dialogue_kind", "authored"))
        activity = self.dialogue_activity(actor, kind) if hasattr(self, "dialogue_activity") else str(actor.get("activity", "following today's routine"))
        activity = str(activity).replace("their ", "my ")
        setting = str(
            actor.get("runtime_location")
            or actor.get("district")
            or actor.get("home_name")
            or actor.get("home")
            or getattr(self.state, "location", "Elsewhere")
        )
        actor_id = str(actor.get("id") or actor.get("name") or "npc")
        role = self.dialogue_actor_role(actor)
        talk_count = int(getattr(self.state, "town_npc_dialogue_counts", {}).get(actor_id, actor.get("dialogue_count", 0)) or 0)
        return contextual_dialogue_line(
            role,
            topic,
            f"{self.dialogue_day_key()}:{actor_id}:{talk_count}:{salt}",
            {
                "player": str(getattr(self.state, "player_name", "neighbor")),
                "time": str(self.town_time_period() if hasattr(self, "town_time_period") else "day"),
                "weather": str(getattr(self.state, "weather", "clear")).lower(),
                "season": str(getattr(self.state, "season", "Spring")),
                "setting": setting,
                "familiarity": self.dialogue_familiarity_label(actor, kind),
                "vantage": self.dialogue_voice_vantage(actor, kind),
            },
        )

    def dialogue_day_key(self) -> str:
        if hasattr(self, "town_npc_day_key"):
            return str(self.town_npc_day_key())
        return f"{getattr(self.state, 'year', 1)}:{getattr(self.state, 'month', 1)}:{getattr(self.state, 'day', 1)}"

    def dialogue_relationship_points(
        self, actor: Dict[str, object], kind: str
    ) -> int:
        actor_id = str(actor.get("id", ""))
        if (
            kind in {"authored", "spouse"} or self.dialogue_is_persistent_world_actor(actor, kind)
        ) and actor_id and hasattr(self, "town_npc_relationship"):
            return int(self.town_npc_relationship(actor_id))
        if kind == "child":
            return int(actor.get("affection", actor.get("bond", 0)) or 0)
        return int(actor.get("relationship", actor.get("bond", 0)) or 0)

    def dialogue_is_family_or_companion(
        self, actor: Dict[str, object], kind: str
    ) -> bool:
        actor_id = str(actor.get("id", ""))
        if kind in {"spouse", "child", "companion"}:
            return True
        return bool(
            actor_id
            and actor_id == str(getattr(self.state, "spouse_npc_id", ""))
        )

    def dialogue_familiarity_label(
        self, actor: Dict[str, object], kind: str
    ) -> str:
        if self.dialogue_is_family_or_companion(actor, kind):
            return "Family" if kind != "companion" else "Companion"
        points = self.dialogue_relationship_points(actor, kind)
        if points < 0:
            return "Wary"
        if points < 25:
            return "Unfamiliar"
        if points < 60:
            return "Recognized"
        if points < 100:
            return "Familiar"
        if points < 150:
            return "Close"
        return "Trusted"

    def dialogue_personality_words(self, actor: Dict[str, object]) -> set[str]:
        raw_traits = actor.get("traits", []) or []
        traits = list(raw_traits) if isinstance(raw_traits, (list, tuple, set)) else [raw_traits]
        personality_traits = actor.get("personality_traits", []) or []
        if not isinstance(personality_traits, (list, tuple, set)):
            personality_traits = [personality_traits]
        values = [
            actor.get("personality", ""), actor.get("disposition", ""),
            *traits, *personality_traits,
        ]
        words: set[str] = set()
        for value in values:
            cleaned = str(value).lower().replace("-", " ").replace(",", " ")
            words.update(part for part in cleaned.split() if part)
        return words

    def dialogue_is_on_duty(self, actor: Dict[str, object], kind: str) -> bool:
        role_words = set(self.dialogue_actor_role(actor).lower().replace("-", " ").split())
        if not role_words.intersection(SERVICE_ROLE_WORDS):
            return False
        activity = self.dialogue_activity(actor, kind).lower()
        duty_phrases = (
            "working", "on duty", "at the counter", "serving", "staffing",
            "seeing patients", "running the", "tending the", "helping customers",
            "opening the", "closing the", "preparing meals", "keeping records",
        )
        return any(phrase in activity for phrase in duty_phrases)

    def dialogue_demeanor(
        self, actor: Dict[str, object], kind: str, first_meeting: bool = False
    ) -> str:
        if self.dialogue_is_on_duty(actor, kind):
            return "professional"
        relationship = self.dialogue_relationship_points(actor, kind)
        reputation = int(getattr(self.state, "social_reputation", 0) or 0)
        words = self.dialogue_personality_words(actor)
        mood = self.dialogue_current_mood(actor, kind)
        mood_label = str(mood.get("label", ""))
        mood_intensity = int(mood.get("intensity", 0) or 0)
        if mood_label == "angry" and mood_intensity >= 2:
            return "hostile" if relationship < 25 else "blunt"
        if mood_label in {"grieving", "embarrassed", "worried"} and mood_intensity >= 2:
            return "reserved"
        if mood_label == "suspicious" and mood_intensity >= 2:
            return "wary" if first_meeting else "skeptical"
        if mood_label in {"grateful", "excited", "proud", "hopeful"} and relationship >= 0:
            return "warm"
        if relationship < 0:
            return "hostile"
        if first_meeting and reputation <= -15:
            return "wary"
        if relationship >= 100:
            return "warm" if not words.intersection(BLUNT_PERSONALITY_WORDS) else "blunt"
        if words.intersection(BLUNT_PERSONALITY_WORDS):
            return "blunt"
        if words.intersection(SKEPTICAL_PERSONALITY_WORDS):
            return "skeptical"
        if words.intersection(RESERVED_PERSONALITY_WORDS):
            return "reserved"
        if words.intersection(WARM_PERSONALITY_WORDS) or (first_meeting and reputation >= 20):
            return "warm"
        return "neutral"

    def dialogue_voice_vantage(self, actor: Dict[str, object], kind: str) -> str:
        return {
            "professional": "Speaking professionally",
            "warm": "Honestly",
            "skeptical": "From where I stand",
            "blunt": "To be direct",
            "reserved": "For what it is worth",
            "wary": "As far as I am willing to say",
            "hostile": "If you insist on asking",
            "neutral": "From my experience",
        }[self.dialogue_demeanor(actor, kind)]

    def dialogue_text_pages(
        self,
        text: object,
        width: int,
        lines_per_page: int,
    ) -> List[List[str]]:
        """Wrap all dialogue text into pages so presentation never drops words."""
        width = max(12, int(width))
        lines_per_page = max(1, int(lines_per_page))
        wrapped: List[str] = []
        raw = str(text or "").replace("\r", "")
        for paragraph in raw.split("\n"):
            wrapped.extend(
                textwrap.wrap(
                    paragraph,
                    width=width,
                    break_long_words=False,
                    break_on_hyphens=False,
                ) or [""]
            )
        return [
            wrapped[index:index + lines_per_page]
            for index in range(0, len(wrapped), lines_per_page)
        ] or [[""]]

    def dialogue_recent_exchange_rows(
        self,
        transcript: Sequence[Dict[str, str]],
        current_text: str,
        width: int,
        max_rows: int,
    ) -> List[str]:
        """Return a compact visual memory of the turns immediately before this one."""
        entries = [dict(entry) for entry in transcript if isinstance(entry, dict)]
        if entries:
            latest = " ".join(str(entries[-1].get("text", "") or "").split())
            if latest == " ".join(str(current_text or "").split()):
                entries = entries[:-1]
        rows: List[str] = []
        for entry in entries[-4:]:
            speaker = str(entry.get("speaker", "") or "Narrator")
            speech = " ".join(str(entry.get("text", "") or "").split())
            if not speech:
                continue
            rows.append(f"{speaker} › {speech}")
        return [fit_text(row, width) for row in rows[-max(0, int(max_rows)):]]

    def _draw_dialogue_frame(
        self,
        actor: Dict[str, object],
        text: str,
        phase: str,
        transcript: Sequence[Dict[str, str]],
        options: Sequence[DialogueOption] = (),
        selected: int = 0,
        text_page: int = 0,
    ) -> int:
        """Render a fixed-height in-world conversation dock and return page count."""
        width = max(42, min(88, terminal_width() - 4))
        screen_height = max(16, int(terminal_height()))
        # Conversations are a primary interface, not a two-line overlay.  Use
        # the available terminal while retaining a small view of the world.
        panel_height = max(14, min(24, screen_height - 3))
        name = self.dialogue_actor_name(actor)
        role = self.dialogue_actor_role(actor)
        kind = str(actor.get("_dialogue_kind", "authored"))
        is_scene = kind == "scene"
        scene_title = str(actor.get("_scene_title", "") or "")
        scene_progress = str(actor.get("_scene_progress", "") or "")
        border_style = C.LANDMARK_ACTIVE if is_scene else C.UI_BORDER

        def top_border(label: str) -> str:
            title = f" {label} "
            return colorize("┌" + title + "─" * max(0, width - len(title)) + "┐", border_style + C.BOLD)

        def divider(label: str = "") -> str:
            title = f" {label} " if label else ""
            return colorize("├" + title + "─" * max(0, width - len(title)) + "┤", C.UI_BORDER)

        def row(value: object = "", style: str = "") -> str:
            fitted = fit_text(str(value), width)
            body = colorize(fitted, style) if style else fitted
            return colorize("│", C.UI_BORDER) + pad_to(body, width) + colorize("│", C.UI_BORDER)

        def bottom_border() -> str:
            return colorize("└" + "─" * width + "┘", border_style + C.BOLD)

        panel: List[str] = [top_border("SCENE" if is_scene else "CONVERSATION")]
        if is_scene:
            panel.append(row(scene_title or "In-world scene", C.LANDMARK_ACTIVE))
            step_label = str(actor.get("_scene_step_label", "") or "Action")
            context_parts: List[str] = []
            if step_label.casefold() not in {"action", "narration"}:
                context_parts.append(f"{name} · {role}")
            if scene_progress:
                context_parts.append(scene_progress)
            location = str(actor.get("_scene_location", "") or "")
            if location:
                context_parts.append(location)
            staging_status = str(actor.get("_scene_staging_status", "") or "")
            if staging_status:
                context_parts.append(staging_status)
            context = " · ".join(context_parts) or "In-world action"
        else:
            panel.append(row(f"{name} · {role}", C.ACTOR_NPC))
            familiarity = self.dialogue_familiarity_label(actor, kind)
            demeanor = self.dialogue_demeanor(actor, kind).title()
            context = f"{familiarity} · {demeanor}"
        panel.append(row(context, C.UI_MUTED))

        history_rows_allowed = 1 if options else 3
        history_rows = self.dialogue_recent_exchange_rows(
            transcript, str(text), width - 2, history_rows_allowed,
        )
        panel.append(divider("RECENT EXCHANGE"))
        if history_rows:
            for history_row in history_rows:
                speaker_style = C.SERVICE if history_row.startswith("You ›") else C.UI_MUTED
                panel.append(row(" " + history_row, speaker_style))
        else:
            panel.append(row(" The conversation begins here.", C.UI_MUTED))

        page_count = 1
        if options:
            prompt_pages = self.dialogue_text_pages(text, width - 4, 2)
            page_count = len(prompt_pages)
            text_page = max(0, min(int(text_page), page_count - 1))
            prompt_rows = list(prompt_pages[text_page])
            if page_count > 1 and prompt_rows:
                prompt_rows[-1] = fit_text(
                    f"{prompt_rows[-1]}  [{text_page + 1}/{page_count}]", width - 4
                )
            selected_hint = str(options[selected][2] or "") if options else ""
            hint_rows = (
                self.dialogue_text_pages(selected_hint, width - 4, 2)[0]
                if selected_hint else []
            )
            visible_count = max(
                1,
                min(7, panel_height - len(panel) - len(prompt_rows) - len(hint_rows) - 4),
            )
            start = max(
                0,
                min(int(selected) - visible_count // 2, max(0, len(options) - visible_count)),
            )
            end = min(len(options), start + visible_count)
            panel.append(divider("YOUR RESPONSE"))
            for prompt_row in prompt_rows:
                panel.append(row(" " + prompt_row, C.UI_TITLE))
            for index in range(start, end):
                _value, label, hint = options[index]
                prefix = "> " if index == selected else "  "
                scroll_marker = ""
                if index == start and start > 0:
                    scroll_marker = " ↑"
                if index == end - 1 and end < len(options):
                    scroll_marker = " ↓"
                line = f"{prefix}{index + 1}. {label}{scroll_marker}"
                panel.append(row(line, C.UI_SELECTED if index == selected else ""))
            for hint_row in hint_rows:
                panel.append(row(" " + hint_row, C.UI_MUTED))
            controls = "↑/↓ choose · Z/Enter select · H history · B/X/Esc leave"
        else:
            available_text_rows = max(2, panel_height - len(panel) - 4)
            text_pages = self.dialogue_text_pages(text, width - 4, available_text_rows)
            page_count = len(text_pages)
            text_page = max(0, min(int(text_page), page_count - 1))
            step_label = str(actor.get("_scene_step_label", "") or name)
            heading = step_label.upper() if is_scene else name.upper()
            if page_count > 1:
                heading += f" · PAGE {text_page + 1}/{page_count}"
            panel.append(divider(heading))
            for speech_row in text_pages[text_page]:
                style = C.UI_MUTED if is_scene and step_label.casefold() in {"action", "narration"} else C.UI_TITLE
                panel.append(row("  " + speech_row, style))
            if is_scene:
                controls = "Z/Enter continue · H history · B/X/Esc skip (outcomes apply)"
            elif page_count > 1:
                controls = "Z/Enter next · Left/Right pages · H history · B/X/Esc leave"
            else:
                controls = "Z/Enter/Space continue · H history · B/X/Esc leave"

        while len(panel) < panel_height - 3:
            panel.append(row())
        if len(panel) > panel_height - 3:
            panel = panel[:panel_height - 3]
        panel.extend([divider(), row(controls, C.UI_MUTED), bottom_border()])

        output_lines: List[str] = []
        if hasattr(self, "render_frame_text"):
            try:
                base_lines = self.render_frame_text().splitlines()
                world_rows = max(4, screen_height - panel_height - 1)
                output_lines.extend(base_lines[:world_rows])
            except Exception:
                pass
        margin = " " * max(0, (terminal_width() - (width + 2)) // 2)
        output_lines.extend(margin + line for line in panel)
        try:
            sys.stdout.write("\033[H" + "\n".join("\033[2K" + line for line in output_lines) + "\033[J")
            sys.stdout.flush()
        except Exception:
            clear_screen()
            for line in output_lines:
                print(line)
        return page_count

    def dialogue_history_lines(
        self, transcript: Sequence[Dict[str, str]]
    ) -> List[str]:
        rows: List[str] = ["CONVERSATION HISTORY", ""]
        for entry in transcript[-24:]:
            speaker = str(entry.get("speaker", ""))
            text = str(entry.get("text", ""))
            rows.append(f"{speaker}: {text}" if speaker else text)
            rows.append("")
        return rows or ["No dialogue yet."]

    def dialogue_say(
        self,
        actor: Dict[str, object],
        text: str,
        phase: str,
        transcript: List[Dict[str, str]],
    ) -> bool:
        source_line = " ".join(str(text or "").strip().split())
        line = apply_custom_dialogue_override(
            source_line,
            dialogue_variable_context(self, actor),
        )
        scene_label = str(actor.get("_scene_step_label", "") or "").casefold()
        if line == source_line and scene_label not in {"action", "narration"}:
            line = naturalize_spoken_dialogue(line)
        if not line:
            return True
        speaker = self.dialogue_actor_name(actor)
        transcript.append({"speaker": speaker, "text": line, "phase": phase})
        if hasattr(self, "add_hud_activity"):
            self.add_hud_activity(f"{speaker}: {line}", "dialogue")
        text_page = 0
        while True:
            rendered_page_count = self._draw_dialogue_frame(
                actor, line, phase, transcript, text_page=text_page,
            )
            page_count = max(1, int(rendered_page_count or 1))
            key = normalize_key(self.dialogue_read_key())
            if key in MENU_CONFIRM_KEYS:
                if text_page + 1 < page_count:
                    text_page += 1
                    continue
                return True
            if key in {"RIGHT", "d", "PGDN"} and page_count > 1:
                text_page = min(page_count - 1, text_page + 1)
            elif key in {"LEFT", "a", "PGUP"} and page_count > 1:
                text_page = max(0, text_page - 1)
            elif key == "h":
                self.vertical_panel_view(
                    "Conversation History",
                    self.dialogue_history_lines(transcript),
                    68, 25,
                )
            elif key in {"b", "x", "\x1b", "q", "\t"}:
                return False

    def dialogue_choose(
        self,
        actor: Dict[str, object],
        prompt: str,
        phase: str,
        options: Sequence[DialogueOption],
        transcript: List[Dict[str, str]],
    ) -> str:
        prompt = naturalize_spoken_dialogue(prompt)
        choices = [
            (value, naturalize_spoken_dialogue(label), hint)
            for value, label, hint in options
        ]
        if not choices:
            return ""
        selected = 0
        text_page = 0
        while True:
            rendered_page_count = self._draw_dialogue_frame(
                actor, prompt, phase, transcript, choices, selected,
                text_page=text_page,
            )
            page_count = max(1, int(rendered_page_count or 1))
            key = normalize_key(self.dialogue_read_key())
            if key in {"UP", "w", "NUM8"}:
                selected = (selected - 1) % len(choices)
                text_page = 0
            elif key in {"DOWN", "s", "NUM2"}:
                selected = (selected + 1) % len(choices)
                text_page = 0
            elif key in {"RIGHT", "d", "PGDN"} and page_count > 1:
                text_page = min(page_count - 1, text_page + 1)
            elif key in {"LEFT", "a", "PGUP"} and page_count > 1:
                text_page = max(0, text_page - 1)
            elif len(key) == 1 and key.isdigit() and 1 <= int(key) <= len(choices):
                selected = int(key) - 1
                value, label, _hint = choices[selected]
                transcript.append({"speaker": "You", "text": label, "phase": phase})
                if hasattr(self, "add_hud_activity"):
                    self.add_hud_activity(f"You: {label}", "dialogue")
                return value
            elif key in MENU_CONFIRM_KEYS:
                value, label, _hint = choices[selected]
                transcript.append({"speaker": "You", "text": label, "phase": phase})
                if hasattr(self, "add_hud_activity"):
                    self.add_hud_activity(f"You: {label}", "dialogue")
                return value
            elif key == "h":
                self.vertical_panel_view(
                    "Conversation History",
                    self.dialogue_history_lines(transcript),
                    68, 25,
                )
            elif key in {"b", "x", "\x1b", "q", "\t"}:
                return "goodbye"

    def dialogue_greeting(
        self, actor: Dict[str, object], kind: str, first_meeting: bool, repeated_today: bool
    ) -> str:
        name = self.dialogue_actor_name(actor)
        if self.dialogue_is_family_or_companion(actor, kind):
            return ""
        if first_meeting:
            slot = self.dialogue_social_slot(actor, kind)
            introduction = next(
                (
                    row for row in reversed(slot.get("introductions", []) or [])
                    if isinstance(row, dict) and not row.get("acknowledged")
                ),
                None,
            )
            if introduction:
                introduction["acknowledged"] = True
                source = str(introduction.get("source_name", "someone we both know"))
                purpose = str(introduction.get("purpose", "that you might stop by"))
                return f"You must be {getattr(self.state, 'player_name', 'the newcomer')}. {source} told me {purpose}. I'm {name}."
        demeanor = self.dialogue_demeanor(actor, kind, first_meeting)
        period = str(self.town_time_period() if hasattr(self, "town_time_period") else "day")
        if repeated_today:
            repeat_pools = {
                "professional": (
                    "Was there something else I can help with?", "Welcome back. What else did you need?",
                    "Something else, then? Go ahead.", "Still here. What else do you need?",
                ),
                "warm": (
                    "Back again? Good. What did you forget to ask?", "Oh, hello again! What is it?",
                    "You are back, and I do not mind at all.", "Twice in one day. I must be good company.",
                ),
                "skeptical": (
                    "You are back already. What changed?", "Another question? Go ahead.",
                    "Back so soon. Did the answer not hold?", "Something you thought of after leaving?",
                ),
                "blunt": (
                    "Again? What is it?", "You came back quickly. Speak.",
                    "Still here. Get to it.", "More, then. Fine.",
                ),
                "reserved": (
                    "Hello again. Was there something else?", "You are back. I am listening.",
                    "Yes? I have not moved.", "Something else came to you, then.",
                ),
                "wary": (
                    "What do you need this time?", "You again. Keep it brief.",
                    "Twice now. What is this about?", "You keep coming back. Why?",
                ),
                "hostile": (
                    "We already spoke. What now?", "Make this quick.",
                    "Still here?", "You are pushing it.",
                ),
                "neutral": (
                    "Did you need something else?", "Was there something you forgot to ask?",
                    "Something else, then?", "Back again. Go on.",
                ),
            }
            # Seeded on the conversation count as well as the day: without it an
            # NPC gives the identical greeting every time you reopen the
            # conversation, which is the repetition players actually notice.
            return _cycling_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:again",
                repeat_pools[demeanor],
                actor.get("dialogue_count", 0),
            )
        if first_meeting:
            first_pools = {
                "professional": (
                    f"Good {period}. How can I help you? I'm {name}.",
                    f"Welcome. I'm {name}. What can I do for you today?",
                    f"Hello. I'm {name}; let me know what you need.",
                ),
                "warm": (
                    f"Oh, hello! I don't think we've met. I'm {name}.",
                    f"A new face! I'm {name}. It is good to meet you.",
                    f"Hello there. I'm {name}; I was hoping we would eventually meet.",
                ),
                "skeptical": (
                    f"I don't recognize you. I'm {name}. What did you need?",
                    f"You're new around here, aren't you? I'm {name}. Why did you stop me?",
                    f"We haven't met. People call me {name}. What is this about?",
                ),
                "blunt": (
                    f"You're new. I'm {name}. Was there a reason you stopped me?",
                    f"I don't know you. {name}. What do you want?",
                    f"We haven't met, so let us keep this simple. I'm {name}.",
                ),
                "reserved": (
                    f"Hello. I don't believe we've met. I'm {name}.",
                    f"You must be new. I'm {name}. Was there something you wanted to ask?",
                    f"Good {period}. I'm {name}; I usually take a little time to know people.",
                ),
                "wary": (
                    f"I haven't seen you before. I'm {name}. Keep this straightforward.",
                    f"You're a stranger to me. What do you need? My name is {name}.",
                    f"We don't know one another. I'm {name}, and I would rather know why you approached.",
                ),
                "hostile": (
                    "I don't know you. What is it?",
                    f"You can call me {name}. Do not mistake an introduction for trust.",
                    "Stopping strangers without a reason is a poor habit. Speak.",
                ),
                "neutral": (
                    f"Good {period}. I don't think we've met. I'm {name}.",
                    f"Hello. I'm {name}. What brought you over?",
                    f"We haven't been introduced. I'm {name}.",
                ),
            }
            return _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:first:{demeanor}",
                first_pools[demeanor],
            )
        tier = self.dialogue_familiarity_label(actor, kind)
        if tier in {"Close", "Trusted"}:
            pools = {
                "warm": (
                    "There you are! I am glad you stopped.", "Good, I was hoping I would see you.",
                    "You have a talent for arriving when I want the company.",
                    "There you are. The day improves.",
                ),
                "blunt": (
                    "There you are. I can speak plainly with you.",
                    "Good. You are someone I do not have to perform for.",
                    "You. Good. I have been saving the honest version.",
                    "There you are. No need for the polite opening.",
                ),
                "reserved": (
                    "I'm glad you came by.", "It is good to see someone familiar.",
                    "You are welcome here, and I do not say that often.",
                    "Good. I did not want to spend the whole day quiet.",
                ),
                "skeptical": (
                    "I trust you enough to skip the polite version.",
                    "Good. I wanted your honest opinion.",
                    "You I can talk to without measuring every word.",
                    "There you are. I have been wanting a straight answer from someone.",
                ),
            }
            base = _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:close:{demeanor}",
                pools.get(demeanor, (
                    "There you are. It is good to see you.",
                    "I was hoping our paths would cross.",
                    "Good. I would rather talk to you than most people today.",
                    "There you are. That is the day starting properly.",
                )),
            )
        else:
            # The first greeting of the day, from every acquaintance, for the
            # whole game. Every NPC starts out "neutral", so a two-line pool
            # here meant the entire town shared two sentences.
            pools = {
                "professional": (
                    f"Good {period}. How can I help?", "Welcome back. What did you need?",
                    f"Good {period}. What brings you by?",
                    "You caught me between tasks. What do you need?",
                    "Hello. I have a moment if you do.",
                ),
                "warm": (
                    "Hello again! How have you been?",
                    "There you are. It is good to see a familiar face.",
                    "There you are! I was thinking about the last time we talked.",
                    "Hello! You always turn up at a reasonable hour.",
                    "Good to see you. Come on, then, what is it?",
                ),
                "skeptical": (
                    "Hello again. What is on your mind?", "You have another question, I assume.",
                    "Back again. What is it this time?",
                    "Hello. I will hear you out.",
                    "You have that look about you. Go on.",
                ),
                "blunt": (
                    "There you are. What is it?", "Hello. Speak plainly and we will get along.",
                    "You again. What do you need?",
                    "Hello. Make it useful.",
                    "Right. What is it?",
                ),
                "reserved": (
                    "Hello again.", "Good to see you. Was there something you wanted to discuss?",
                    "Hello. I am here.",
                    "Good to see you. Take your time.",
                    "You found me. What is it?",
                ),
                "wary": (
                    "What do you want?", "I suppose we can speak for a moment.",
                    "You are back. Say your piece.",
                    "Hello. I am listening, for now.",
                    "What do you need from me?",
                ),
                "hostile": (
                    "What is it now?", "I have little patience for this, but speak.",
                    "You again.",
                    "Say it and go.",
                    "I have nothing new for you.",
                ),
                "neutral": (
                    f"Good {period}.", "Hello again. Was there something you needed?",
                    "Hello. What can I do for you?",
                    "Good to see you. What is it?",
                    f"Good {period}. Go on, then.",
                ),
            }
            base = _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:greeting:{demeanor}", pools[demeanor]
            )
        return base

    def dialogue_refresh_routine_rumors(
        self, actor: Dict[str, object], kind: str
    ) -> List[Dict[str, str]]:
        heard = [dict(value) for value in actor.get("heard_rumors", []) or [] if isinstance(value, dict)]
        social_slot = self.dialogue_social_slot(actor, kind)
        for knowledge in social_slot.get("knowledge", []) or []:
            if not isinstance(knowledge, dict) or int(knowledge.get("confidence", 0) or 0) < 30:
                continue
            source_kind = str(knowledge.get("source_kind", "hearsay"))
            source_name = str(knowledge.get("source_name", "someone on my route"))
            knowledge_text = str(knowledge.get("text", ""))
            if source_kind == "firsthand" and source_name == "personal observation":
                related_event = next(
                    (
                        row for row in social_slot.get("witnessed_events", []) or []
                        if isinstance(row, dict)
                        and str(row.get("id", "")) == str(knowledge.get("id", ""))
                    ),
                    None,
                )
                if related_event:
                    knowledge_text = self.world_dialogue_event_knowledge_summary(related_event)
                else:
                    legacy_event = {
                        "text": knowledge_text,
                        "action": self.world_dialogue_event_action(knowledge_text),
                        "category": str(knowledge.get("subject", "general")),
                        "location": knowledge.get("location", "nearby"),
                    }
                    knowledge_text = self.world_dialogue_event_knowledge_summary(legacy_event)
                if not knowledge_text:
                    continue
            source = (
                "something they personally witnessed"
                if source_kind == "firsthand"
                else "public notice" if source_kind == "public"
                else source_name
            )
            packet = {
                "text": knowledge_text,
                "source": source,
                "day": str(knowledge.get("day", self.dialogue_day_key())),
                "confidence": str(knowledge.get("confidence", 50)),
            }
            if packet["text"] and not any(item.get("text") == packet["text"] for item in heard):
                heard.append(packet)
        actor_id = str(actor.get("id", ""))
        if kind == "authored" and hasattr(self, "town_npc_reactivity_lines"):
            for text in self.town_npc_reactivity_lines(actor, limit=2):
                packet = {"text": str(text), "source": "something they witnessed around town", "day": self.dialogue_day_key()}
                if packet["text"] and not any(item.get("text") == packet["text"] for item in heard):
                    heard.append(packet)
        partner_id = str(actor.get("social_partner_id", ""))
        if partner_id and hasattr(self, "npc_record_by_id"):
            partner = self.npc_record_by_id(partner_id)
            if isinstance(partner, dict):
                rumor = str(partner.get("rumor", "") or self.town_npc_dialogue_data(partner).get("rumor", ""))
                if rumor and not any(item.get("text") == rumor for item in heard):
                    heard.append({
                        "text": rumor,
                        "source": str(partner.get("name", "a neighbor")),
                        # Named sources get a real pronoun when the rumour is
                        # retold; anything without a record falls back to they.
                        "source_sex": self.npc_sex(partner) if hasattr(self, "npc_sex") else "",
                        "day": self.dialogue_day_key(),
                    })
        actor["heard_rumors"] = heard[-8:]
        return actor["heard_rumors"]

    def dialogue_disclosure_callback(self, actor: Dict[str, object], kind: str) -> str:
        """Bring up something the player shared on an earlier day.

        Disclosures have always been recorded and persisted, but the only thing
        that ever read them back was a check to avoid repeating a reaction, so
        an NPC remembered what you told them and then never mentioned it again.
        Witnessed events and overheard knowledge both already have callbacks;
        this gives the player's own confidences the same treatment.
        """
        slot = self.dialogue_social_slot(actor, kind)
        today = self.dialogue_day_key()
        earlier = [
            row for row in (slot.get("disclosures") or [])
            if isinstance(row, dict)
            and str(row.get("subject", ""))
            and str(row.get("day", "")) != today
        ]
        if not earlier:
            return ""
        subject = str(earlier[-1].get("subject", ""))
        pools = {
            "background": (
                "You told me where you came from. I have thought about it since.",
                "I remember what you said about where you grew up. It explains a few things.",
                "You mentioned your background last time. I did not press then, but I was interested.",
            ),
            "deeds": (
                "You mentioned what you have been getting done. People have started noticing, if you had not.",
                "I keep thinking about the work you described. It was not a small thing.",
                "You told me what you finished. I hope somebody thanked you properly.",
            ),
            "travels": (
                "You were telling me about your travels. Did the route hold?",
                "I have been picturing the places you described. I do not get out that far.",
                "You mentioned where you had been. Go carefully next time.",
            ),
            "loot": (
                "You showed me what you were carrying. I am still curious where it came from.",
                "That gear you described has stayed in my head.",
                "You mentioned what you had found. That is rare to see around here.",
            ),
            "companions": (
                "You told me about the people traveling with you. I hope they are still with you.",
                "How are the ones you were traveling with? You spoke well of them.",
                "You mentioned your companions. Good company is worth more than good weather.",
            ),
            "family": (
                "You told me about your household. I have wondered how they are.",
                "How is your family? You spoke about them last time.",
                "You mentioned your household. That kind of thing stays with me.",
            ),
            "ancestry": (
                "You told me about your line. That is more history than most people carry.",
                "I have thought about what you said about the family before you. It is a lot to inherit.",
                "You mentioned your ancestry. It explains the way you go about things.",
            ),
        }
        lines = pools.get(subject)
        if not lines:
            return ""
        # An occasional callback reads as memory; every conversation reads as a
        # stuck record. Fire on roughly one day in three.
        if _stable_index(f"{today}:{actor.get('id')}:disclosure-callback", 3):
            return ""
        return _stable_pick(f"{today}:{actor.get('id')}:disclosure:{subject}", lines)

    def dialogue_chitchat(self, actor: Dict[str, object], kind: str) -> str:
        witnessed = self.dialogue_witness_callback(actor, kind, "conversation")
        if witnessed:
            return witnessed
        mood_line = self.dialogue_mood_context_line(actor, kind)
        if mood_line:
            return mood_line
        recalled = self.dialogue_disclosure_callback(actor, kind)
        if recalled:
            return recalled
        if kind == "child":
            subject = _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:child-chitchat",
                ("day", "home", "family", "wish"),
            )
            return child_household_line(
                self.dialogue_child_stage(actor),
                subject,
                self.dialogue_household_content_context(actor, kind),
                f"{self.dialogue_day_key()}:{actor.get('id')}:smalltalk",
            )
        if kind == "spouse" and _stable_index(
            f"{self.dialogue_day_key()}:{actor.get('id')}:spouse-chitchat", 3
        ):
            subject = _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:spouse-subject",
                ("home", "needs", "affection", "plans"),
            )
            return spouse_household_line(
                subject,
                self.dialogue_household_content_context(actor, kind),
                f"{self.dialogue_day_key()}:{actor.get('id')}:smalltalk",
                self.dialogue_spouse_stage(),
            )
        rumors = self.dialogue_refresh_routine_rumors(actor, kind)
        own_rumor = str(actor.get("rumor", ""))
        if not own_rumor and kind == "authored" and hasattr(self, "town_npc_dialogue_data"):
            own_rumor = str(self.town_npc_dialogue_data(actor).get("rumor", ""))
        candidates = list(rumors)
        if own_rumor:
            candidates.append({"text": own_rumor, "source": "local talk", "day": self.dialogue_day_key()})
        if candidates:
            packet = candidates[_stable_index(f"{self.dialogue_day_key()}:{actor.get('id')}:rumor", len(candidates))]
            text = _first_person(packet.get("text", ""), self.dialogue_actor_name(actor))
            source = str(packet.get("source", "local talk"))
            confidence = int(packet.get("confidence", 100) or 100)
            uncertainty = " I have not confirmed it myself." if confidence < 55 else ""
            if source == "public notice":
                return f"A public notice confirmed this: {text}{uncertainty}"
            if source not in {
                "local talk", "something they witnessed around town",
                "something they personally witnessed",
            }:
                teller = pronouns_for_sex(packet.get("source_sex"))
                return (
                    f"I was speaking with {source}. {teller['subject'].capitalize()} mentioned "
                    f"that {text[:1].lower() + text[1:]}{uncertainty}"
                )
            if source in {"something they witnessed around town", "something they personally witnessed"}:
                return text
            return f"People have been talking. {text}"
        weather = str(getattr(self.state, "weather", "clear") or "clear").lower()
        season = str(getattr(self.state, "season", "Spring") or "Spring")
        activity = self.dialogue_activity(actor, kind).replace("their ", "my ")
        weather_line = (
            f"The {weather} weather has slowed me down today."
            if any(word in weather for word in ("rain", "storm", "snow", "blizzard"))
            else f"The {weather} weather has made the day's work easier."
        )
        return _stable_pick(
            f"{self.dialogue_day_key()}:{actor.get('id')}:grounded-smalltalk",
            (
                weather_line,
                f"{season} has changed the pace around {self.world_dialogue_location_label()}.",
                f"I've been {activity}. How has your day been going?",
            ),
        )

    def dialogue_activity(self, actor: Dict[str, object], kind: str) -> str:
        outcome = actor.get("story_outcome", {})
        if (
            isinstance(outcome, dict)
            and str(outcome.get("activity", ""))
            and int(outcome.get("visible_until_day", 0) or 0) >= self.dialogue_absolute_day()
        ):
            return str(outcome["activity"])
        if kind == "authored" and hasattr(self, "town_npc_activity_label"):
            return str(self.town_npc_activity_label(actor))
        return str(actor.get("runtime_activity") or actor.get("activity") or "following today's routine")

    def dialogue_activity_matches_role(
        self, actor: Dict[str, object], activity: str
    ) -> bool:
        """Reject accidental second-job claims produced by mismatched schedules."""
        role = self.dialogue_actor_role(actor).casefold()
        text = str(activity or "").casefold()
        profession_markers = {
            "teach": ("teacher", "tutor", "librarian", "scholar"),
            "mining": ("miner", "blacksmith", "prospector", "quarry"),
            "working the mine": ("miner", "blacksmith", "prospector"),
            "fishing": ("fisher", "ferryman", "harbor"),
            "seeing patients": ("doctor", "nurse", "healer"),
            "serving meals": ("chef", "innkeeper", "server"),
        }
        mentioned = [roles for phrase, roles in profession_markers.items() if phrase in text]
        return not mentioned or any(
            any(token in role for token in roles) for roles in mentioned
        )

    def dialogue_agenda(self, actor: Dict[str, object], kind: str) -> str:
        name = self.dialogue_actor_name(actor)
        thread = self.dialogue_current_thread(actor, kind, create=False)
        if thread and bool(thread.get("introduced", False)):
            return (
                f"There is something I have been carrying forward: "
                f"{thread.get('title', 'an ongoing matter')}. "
                f"{self.dialogue_thread_line(actor, kind, thread)}"
            )
        aftermath = self.dialogue_story_aftermath(actor, kind)
        if aftermath and int(aftermath.get("last_agenda_day", 0) or 0) != self.dialogue_absolute_day():
            aftermath["last_agenda_day"] = self.dialogue_absolute_day()
            return str(aftermath.get("follow_up", aftermath.get("summary", "")))
        if kind == "spouse":
            return spouse_household_line(
                "plans",
                self.dialogue_household_content_context(actor, kind),
                f"{self.dialogue_day_key()}:{actor.get('id')}:agenda",
                self.dialogue_spouse_stage(),
            )
        activity = self.dialogue_activity(actor, kind).replace("their ", "my ")
        if kind == "authored" and hasattr(self, "town_npc_work_insight"):
            insight = self.town_npc_work_insight(actor)
        else:
            insight = str(actor.get("goal", "I am trying to keep today's work from becoming tomorrow's problem."))
        insight = _as_spoken_intent(_first_person(insight, name))
        if not self.dialogue_activity_matches_role(actor, activity):
            return insight or f"I'm a {self.dialogue_actor_role(actor).lower()}."
        if insight and insight.casefold() not in activity.casefold():
            return f"I've been {activity}. {insight}"
        return f"I've been {activity}."

    def dialogue_topic_options(
        self, actor: Dict[str, object], kind: str
    ) -> List[DialogueOption]:
        options: List[DialogueOption] = [
            ("directions", "Could you give me directions?", "Only places this person knows will be listed."),
            ("background", "Where are you from?", "Home, origin, and how they came to be here."),
            ("past", "Tell me about your past.", "Upbringing and experiences they are comfortable discussing."),
            ("ambition", "What do you want from life?", "Personal hopes beyond today's occupation and routine."),
            ("family", "How is your family?", "Answers reflect their actual household and trust."),
            ("work", "How is work going?", "Profession, current task, requests, and quests."),
            ("interests", "What do you enjoy doing?", "Things they do when work is finished."),
            ("people", "Who do you know around here?", "Family, coworkers, friends, and traveling companions."),
            ("player", "Let me tell you about myself.", "Share your background, deeds, travels, possessions, family, companions, or ancestry."),
            ("smalltalk", "Let's talk for a while.", "Chat casually, offer a sincere compliment, or deliberately insult them."),
            ("arrangements", "Can we make some plans?", "Arrange introductions, messages, meetings, directions, travel, and family plans."),
            ("companions", "Let's talk about companions.", "Your traveling party and people seeking company."),
        ]
        if str(actor.get("id", "")) and (
            kind in {"authored", "procedural", "spouse"}
            or self.dialogue_is_persistent_world_actor(actor, kind)
        ):
            romance_allowed = bool(
                hasattr(self, "is_marriageable_npc")
                and hasattr(self, "is_heterosexual_match_for_player")
                and self.is_marriageable_npc(actor)
                and self.is_heterosexual_match_for_player(actor)
            )
            established_romance = bool(
                romance_allowed
                and self.dialogue_romance_stage(actor) in {"dating", "engaged", "married"}
            )
            options.append((
                "relationship",
                "Let's talk about our relationship." if established_romance else "Let's talk about our friendship.",
                (
                    "Discuss dating, commitment, and the bond between you."
                    if established_romance
                    else "Discuss how well you know one another and how the friendship is developing."
                ),
            ))
        relationship_tier = (
            self.relationship_tier_for_npc(actor)
            if hasattr(self, "relationship_tier_for_npc")
            else "Stranger"
        )
        if relationship_tier in {"Friend", "Close Friend", "Dating", "Engaged", "Spouse"} and kind != "child":
            options.append(("private", "Tell me something you don't say often.", "A more candid thought unlocked by genuine familiarity."))
        current_thread = self.dialogue_current_thread(actor, kind, create=False)
        if current_thread and bool(current_thread.get("introduced", False)):
            options.append(("thread", "About what we discussed before...", "Continue the personal situation across conversations."))
        if actor.get("_dialogue_group_partner"):
            options.append(("group", "What does everyone think?", "Bring the nearby participant into the same conversation."))
        actor_id = str(actor.get("id", ""))
        if kind in {"spouse", "child"} or actor_id.startswith(("spouse:", "child:")):
            options.append(("household", "How are things at home?", "Plans, safety, finances, memories, and family outings."))
        options.append(("goodbye", "I should get going.", "Leave the conversation naturally."))
        return options

    def dialogue_choose_topic(
        self,
        actor: Dict[str, object],
        kind: str,
        transcript: List[Dict[str, str]],
    ) -> str:
        """Present broad conversational intentions before detailed questions."""
        available = {
            value: (value, label, hint)
            for value, label, hint in self.dialogue_topic_options(actor, kind)
        }
        groups = {
            "about": ("background", "past", "ambition", "family", "interests", "people", "private"),
            "world": ("directions", "work", "companions"),
            "social": ("smalltalk", "player", "group"),
            "plans": ("arrangements", "thread", "household"),
        }
        while True:
            top: List[DialogueOption] = [
                ("about", "Ask about them", "Their home, past, family, interests, ambitions, and acquaintances."),
                ("world", "Ask about places or work", "Directions, local work, and traveling companions."),
                ("social", "Chat or share something", "Small talk, compliments, and things you want to tell them."),
            ]
            if any(value in available for value in groups["plans"]):
                top.append(("plans", "Discuss plans or ongoing matters", "Meetings, outings, household plans, and conversations already in progress."))
            if "relationship" in available:
                top.append(available["relationship"])
            top.append(available.get("goodbye", ("goodbye", "I should get going.", "End the conversation.")))
            category = self.dialogue_choose(actor, "What would you like to talk about?", "topics", top, transcript)
            if not category or category in {"goodbye", "relationship"}:
                return category
            choices = [available[value] for value in groups.get(category, ()) if value in available]
            choices.append(("back", "Choose another subject", "Return to the conversation categories."))
            topic = self.dialogue_choose(actor, "What do you want to ask?", "questions", choices, transcript)
            if topic == "back":
                continue
            return topic

    def dialogue_known_places(
        self, actor: Dict[str, object], kind: str
    ) -> List[Dict[str, object]]:
        places: List[Dict[str, object]] = []
        if kind in {"authored", "spouse", "child", "companion"}:
            for building_id, data in TOWN_BUILDING_DATA.items():
                if hasattr(self, "is_town_building_unlocked") and not self.is_town_building_unlocked(building_id):
                    continue
                places.append({"id": f"town:{building_id}", "name": str(data["label"]), "district": str(data["district"]), "kind": "town"})
            places.extend([
                {"id": "town:farm", "name": "Your Farm", "district": "west of town", "kind": "town"},
                {"id": "town:mine", "name": "The Mines", "district": "beyond the northern routes", "kind": "town"},
            ])
        plan = self.current_procedural_town_plan() if hasattr(self, "current_procedural_town_plan") else None
        if kind == "procedural" and isinstance(plan, dict):
            for building in plan.get("buildings", []) or []:
                if not isinstance(building, dict) or not building.get("completed", True):
                    continue
                places.append({
                    "id": f"settlement:{building.get('id')}",
                    "name": str(building.get("name", "Settlement building")),
                    "x": int(building.get("door_x", building.get("x", 0)) or 0),
                    "y": int(building.get("door_y", building.get("y", 0)) or 0),
                    "kind": "settlement",
                })
        # Adults can share real regional knowledge even when they are not
        # currently labeled as travelers.  The returned destinations all come
        # from actual routes, settlements, or discovered sites and therefore
        # have usable chunk coordinates.
        if kind != "child":
            # A traveler should know the actual places on their route, not only
            # landmarks that the player happened to discover first.  These
            # fields are populated by the purposeful road network and are
            # stable enough to guide or mark on the map.
            route_places = []
            for prefix in ("route_destination", "local_site", "home", "origin"):
                name = str(actor.get(f"{prefix}_name", "") or "")
                if not name:
                    continue
                if prefix == "route_destination":
                    cx = actor.get("route_destination_chunk_x")
                    cy = actor.get("route_destination_chunk_y")
                elif prefix == "home":
                    cx = actor.get("home_chunk_x")
                    cy = actor.get("home_chunk_y")
                elif prefix == "origin":
                    cx = actor.get("origin_chunk_x")
                    cy = actor.get("origin_chunk_y")
                else:
                    cx = actor.get("chunk_x", getattr(self.state, "wilderness_chunk_x", 0))
                    cy = actor.get("chunk_y", getattr(self.state, "wilderness_chunk_y", 0))
                try:
                    route_place = {
                        "id": f"wilderness:{int(cx)},{int(cy)}:{prefix}",
                        "name": name,
                        "x": int(cx), "y": int(cy), "kind": "wilderness",
                        "route_known": True,
                    }
                    world_x = actor.get(f"{prefix}_world_x")
                    world_y = actor.get(f"{prefix}_world_y")
                    if prefix == "local_site":
                        local_x, local_y = actor.get("local_site_x"), actor.get("local_site_y")
                        if local_x is not None and local_y is not None and hasattr(self, "wilderness_world_coords"):
                            world_x, world_y = self.wilderness_world_coords(
                                int(cx), int(cy), int(local_x), int(local_y)
                            )
                    if world_x is not None and world_y is not None:
                        route_place.update({"world_x": int(world_x), "world_y": int(world_y)})
                    route_places.append(route_place)
                except (TypeError, ValueError):
                    continue
            places.extend(route_places)
            if hasattr(self, "wilderness_road_destinations_for_chunk"):
                try:
                    cx = int(actor.get("chunk_x", getattr(self.state, "wilderness_chunk_x", 0)))
                    cy = int(actor.get("chunk_y", getattr(self.state, "wilderness_chunk_y", 0)))
                    for destination in self.wilderness_road_destinations_for_chunk(cx, cy):
                        if not isinstance(destination, dict) or not destination.get("name"):
                            continue
                        road_place = {
                            "id": f"wilderness:{int(destination.get('chunk_x', cx))},{int(destination.get('chunk_y', cy))}:{destination.get('id', 'road')}",
                            "name": str(destination["name"]),
                            "x": int(destination.get("chunk_x", cx)),
                            "y": int(destination.get("chunk_y", cy)),
                            "kind": "wilderness", "route_known": True,
                        }
                        if "world_x" in destination and "world_y" in destination:
                            road_place.update({
                                "world_x": int(destination["world_x"]),
                                "world_y": int(destination["world_y"]),
                            })
                        places.append(road_place)
                except Exception:
                    pass
            state = getattr(self.state, "wilderness_poi_state", {})
            if isinstance(state, dict):
                for key, record in state.items():
                    if not isinstance(record, dict) or not record.get("name"):
                        continue
                    if not any(record.get(flag) for flag in ("discovered", "repaired", "restored", "visited")):
                        continue
                    chunk_x, chunk_y = record.get("chunk_x"), record.get("chunk_y")
                    local_x, local_y = record.get("x"), record.get("y")
                    key_parts = str(key).split(":")
                    try:
                        # Current POI keys are ``chunk_x,chunk_y:kind:x,y``.
                        # The old code parsed the final pair as chunk coordinates,
                        # sending guides toward unrelated regions. Legacy records
                        # may instead use ``kind:chunk_x,chunk_y``.
                        if chunk_x is None or chunk_y is None:
                            chunk_pair = key_parts[0] if "," in key_parts[0] else key_parts[-1]
                            chunk_x, chunk_y = (int(value) for value in chunk_pair.split(",", 1))
                        cx, cy = int(chunk_x), int(chunk_y)
                        place = {
                            "id": f"wilderness:{cx},{cy}:{record.get('kind', 'poi')}:{key}",
                            "name": str(record["name"]), "x": cx, "y": cy,
                            "kind": "wilderness",
                        }
                        if local_x is not None and local_y is not None and hasattr(self, "wilderness_world_coords"):
                            world_x, world_y = self.wilderness_world_coords(cx, cy, int(local_x), int(local_y))
                            place.update({
                                "local_x": int(local_x), "local_y": int(local_y),
                                "world_x": int(world_x), "world_y": int(world_y),
                            })
                        places.append(place)
                    except (TypeError, ValueError):
                        continue
        unique: Dict[str, Dict[str, object]] = {}
        for place in places:
            unique.setdefault(str(place.get("id", place.get("name"))), place)
        return list(unique.values())[:18]

    def dialogue_direction_answer(
        self, actor: Dict[str, object], place: Dict[str, object]
    ) -> str:
        kind = str(place.get("kind", "known"))
        name = str(place.get("name", "that place"))
        if kind == "town":
            return f"{name} is in {place.get('district', 'town')}. The town roads and signs will take you there from the central avenue."
        if kind == "settlement":
            plan = self.current_procedural_town_plan() or {}
            sign_x, sign_y = int(plan.get("sign_x", 0) or 0), int(plan.get("sign_y", 0) or 0)
            dx, dy = int(place.get("x", 0)) - sign_x, int(place.get("y", 0)) - sign_y
            horizontal = "east" if dx > 0 else "west" if dx < 0 else ""
            vertical = "south" if dy > 0 else "north" if dy < 0 else ""
            direction = "-".join(part for part in (vertical, horizontal) if part) or "near the town center"
            return f"{name} is {direction} of the settlement sign. Follow the finished streets; its door opens onto the road."
        if kind == "wilderness":
            cx, cy = int(place.get("x", 0)), int(place.get("y", 0))
            if hasattr(self, "map_nearby_wilderness_chunks"):
                mapped = self.wilderness_region_record(cx, cy).setdefault("mapped_chunks", [])
                coord = f"{cx},{cy}"
                if coord not in mapped:
                    mapped.append(coord)
            current_x = int(getattr(self.state, "wilderness_chunk_x", 0) or 0)
            current_y = int(getattr(self.state, "wilderness_chunk_y", 0) or 0)
            dx, dy = cx - current_x, cy - current_y
            vertical = "north" if dy < 0 else "south" if dy > 0 else ""
            horizontal = "west" if dx < 0 else "east" if dx > 0 else ""
            heading = "-".join(value for value in (vertical, horizontal) if value) or "here in this area"
            distance = abs(dx) + abs(dy)
            route_note = (
                "Stay on the connected road and check the junction signs."
                if bool(place.get("route_known"))
                else "Watch the terrain and road markers as you approach."
            )
            if distance:
                return (
                    f"{name} is about {distance} chunk{'s' if distance != 1 else ''} {heading} of here, near ({cx},{cy}). "
                    f"{route_note} I've marked the destination on your map."
                )
            return f"{name} is {heading}, in this chunk. {route_note} I've marked it on your map."
        return f"I know {name}, but not well enough to give you a precise route. Ask someone who travels there regularly."

    def dialogue_background_answer(self, actor: Dict[str, object], kind: str) -> str:
        background = str(actor.get("background", "") or "").strip()
        origin = self.dialogue_grounded_origin(actor, kind)
        coordinates = ""
        try:
            cx = int(actor.get("origin_chunk_x", actor.get("home_chunk_x")))
            cy = int(actor.get("origin_chunk_y", actor.get("home_chunk_y")))
            coordinates = f" near wilderness coordinates ({cx},{cy})"
        except (TypeError, ValueError):
            pass
        if background and origin:
            return f"I'm from {origin}{coordinates}. {background}"
        if background:
            return background
        if origin:
            return f"I'm from {origin}."
        if kind == "authored":
            return "I'm from Elsewhere. I've lived here long enough to know the town and most of the people in it."
        home = str(actor.get("home", "") or "")
        if home:
            return f"I live around {home}."
        if kind in {"traveler", "regional_visitor"}:
            return "I spend most of my time traveling. I don't have a hometown I speak for on every road."
        return "I live nearby, though I don't know you well enough to give you my whole history yet."

    def dialogue_kinship_context(self, actor: Dict[str, object]) -> Dict[str, str]:
        """Kinship words for a romance line: what each side is to the other."""
        player_sex = str(getattr(self.state, "player_sex", "") or "")
        actor_sex = self.npc_sex(actor) if hasattr(self, "npc_sex") else ""
        return {
            "player_kin": kinship_term("spouse", player_sex),
            "speaker_kin": kinship_term("spouse", actor_sex),
        }

    def dialogue_personal_history_answer(self, actor: Dict[str, object], kind: str) -> str:
        upbringing = _as_spoken_sentence(
            actor.get("upbringing", ""), "I grew up in {}."
        )
        turning_point = _as_spoken_sentence(
            actor.get("formative_event", ""), "What shaped me was {}."
        )
        if upbringing or turning_point:
            return " ".join(part for part in (upbringing, turning_point) if part)
        return self.dialogue_library_line(actor, "personal", "history")

    def dialogue_ambition_answer(self, actor: Dict[str, object], kind: str) -> str:
        ambition = str(actor.get("ambition") or actor.get("goal") or "").strip()
        if ambition:
            return _as_spoken_intent(_first_person(ambition, self.dialogue_actor_name(actor)))
        return self.dialogue_library_line(actor, "personal", "ambition")

    def dialogue_private_answer(self, actor: Dict[str, object], kind: str) -> str:
        relationship = self.dialogue_relationship_points(actor, kind)
        if relationship < 60:
            # Declining is still a conversation. Both answers past this
            # threshold already rotate; without this the refusal is the same
            # sentence every time until relationship reaches 60, which for most
            # NPCs is the whole game.
            guarded = (
                "I have private thoughts, but privacy stops meaning anything if I surrender it on request.",
                "Ask me again when we know each other better. I do not think you mean anything by it, but that answer is not free yet.",
                "There are things I keep to myself. That is not suspicion of you, it is how I stay recognizable to myself.",
                "Not yet. I like the question more than I want to admit, which is exactly why I am not answering it.",
                "I would rather earn the kind of conversation where that has an answer than hand one over now.",
                "Some of me stays behind a door. You are welcome to keep knocking.",
            )
            return _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:private-guarded", guarded
            )
        actor_id = str(actor.get("id", ""))
        romantic = bool(
            actor_id == str(getattr(self.state, "spouse_npc_id", "") or "")
            or actor_id == str(getattr(self.state, "engaged_npc_id", "") or "")
            or actor_id in set(getattr(self.state, "dating_npc_ids", []) or [])
        )
        if romantic:
            lines = (
                "Sometimes I lose the thread of what you are saying because I am thinking about kissing you. I usually recover before you notice.",
                "I like the respectable parts of what we are building. I also like that not every thought I have about you is respectable.",
                "There are evenings when I want conversation, and evenings when I would rather close the door and let silence become something else.",
                "I still feel a private thrill when you choose me in public and look at me as if the public is temporarily irrelevant.",
                "I have imagined waking beside you often enough that it no longer feels like an idle thought.",
                "You make restraint feel less like virtue and more like a decision I keep having to make again.",
            )
        else:
            lines = (
                "I worry that being useful has become the easiest way for me to avoid asking whether I am happy.",
                "Part of me wants to leave without explanation just to learn who I am when nobody already knows my role.",
                "I am lonelier than I usually admit, though company chosen badly can make loneliness feel merciful.",
                "I sometimes envy people who ask directly for affection. I learned to make myself indispensable instead.",
                "There are choices I defend because changing them would require admitting how long I was wrong.",
                "I want a life that contains more desire and less performance, but I am still learning the difference.",
            )
        return _stable_pick(f"{self.dialogue_day_key()}:{actor_id}:private:{relationship}", lines)

    def dialogue_family_answer(self, actor: Dict[str, object], kind: str) -> str:
        actor_id = str(actor.get("id", ""))
        if kind == "child":
            return "You already know my family."
        family_line = ""
        if actor_id and hasattr(self, "npc_family_dialogue_line"):
            family_line = str(self.npc_family_dialogue_line(actor)).strip().strip('"')
        if kind == "procedural" and hasattr(self, "current_procedural_town_plan"):
            plan = self.current_procedural_town_plan() or {}
            population = self.procedural_settlement_population(
                int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))
            )
            members = self.procedural_npc_dialogue_builder().household_members(actor, population or {})
            if members:
                names = ", ".join(str(member.get("name", "a relative")) for member in members)
                return f"{family_line} I share my household with {names}.".strip()
        if actor_id and hasattr(self, "npc_family_dialogue_line"):
            line = str(self.npc_family_dialogue_line(actor)).strip().strip('"“”')
            if line and not family_line:
                return line
        if family_line:
            return family_line
        spouse = str(actor.get("spouse_name", ""))
        children = [str(value) for value in actor.get("children_names", []) or []]
        if spouse or children:
            parts = ([f"I'm married to {spouse}"] if spouse else []) + ([f"our {'child is' if len(children) == 1 else 'children are'} {', '.join(children)}"] if children else [])
            return "; ".join(parts) + "."
        family_story = str(actor.get("family_story", "") or "").strip()
        if family_story:
            return family_story
        household = str(actor.get("household_name", ""))
        if household:
            return f"I belong to the {household} household."
        if self.dialogue_relationship_points(actor, kind) < 25:
            return "I don't usually discuss my family with someone I've only just met."
        return "I don't have a spouse or children to tell you about."

    def dialogue_work_answer(
        self, actor: Dict[str, object], kind: str, opportunities: bool = False
    ) -> str:
        role = self.dialogue_actor_role(actor)
        if opportunities:
            if kind == "procedural" and hasattr(self, "current_procedural_town_plan"):
                plan = self.current_procedural_town_plan() or {}
                result = self.procedural_settlement_conversation(
                    int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0)),
                    str(actor.get("id", "")), topic="request", remember=False,
                )
                if result:
                    return str(result.get("text", "I will let you know when work is available."))
            if kind == "authored" and hasattr(self, "errand_for_npc"):
                errand = self.errand_for_npc(actor)
                if isinstance(errand, dict):
                    if errand.get("completed"):
                        return _stable_pick(
                            f"{self.dialogue_day_key()}:{actor.get('id')}:errand-done",
                            (
                                "You already helped with what I needed today. Ask again tomorrow.",
                                "You have covered what I needed today. Come back tomorrow.",
                                "That is settled, thanks to you. Ask again tomorrow.",
                                "Nothing more today, since you handled it. Tomorrow is another matter.",
                            ),
                        )
                    qty = int(errand.get("qty", 1) or 1)
                    phrase = quantity_item_phrase(errand.get("item", "supplies"), qty)
                    return f"I could use {phrase}. Bring the full amount when you have it, and we can settle the work properly."
            return _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:no-work",
                (
                    "I don't have a specific job for you right now.",
                    "Nothing that needs another pair of hands today. Ask again.",
                    "Not at the moment. When something comes up, you will be the one I think of.",
                    "No work to hand out today. That is a good sign, mostly.",
                    "Nothing right now. Check back when the season turns, if not before.",
                ),
            )
        activity = self.dialogue_activity(actor, kind).replace("their ", "my ").strip().rstrip(".")
        if (
            activity
            and activity not in {"following today's routine", "going about the day"}
            and self.dialogue_activity_matches_role(actor, activity)
        ):
            return f"I'm a {role.lower()}. Right now, I'm {activity}."
        return f"I'm a {role.lower()}."

    def dialogue_promise_key(self, actor: Dict[str, object], kind: str) -> str:
        actor_id = str(actor.get("id") or actor.get("name") or "npc")
        return f"{kind}:{actor_id}"

    def dialogue_promise_store(self) -> Dict[str, Dict[str, object]]:
        store = getattr(self.state, "npc_dialogue_promises", None)
        if not isinstance(store, dict):
            store = {}
            self.state.npc_dialogue_promises = store
        for key in list(store):
            slot = store.get(key)
            if not isinstance(slot, dict):
                store.pop(key, None)
                continue
            if not isinstance(slot.get("active", {}), dict):
                slot["active"] = {}
            history = slot.get("history", [])
            slot["history"] = [dict(row) for row in history if isinstance(row, dict)][-12:]
        return store

    def dialogue_record_promise(
        self, actor: Dict[str, object], kind: str, situation: Dict[str, object]
    ) -> Dict[str, object]:
        key = self.dialogue_promise_key(actor, kind)
        slot = self.dialogue_promise_store().setdefault(key, {"active": {}, "history": []})
        record = {
            "id": str(situation.get("id", "")),
            "type": str(situation.get("type", "work")),
            "actor_id": str(actor.get("id", "")),
            "actor_name": self.dialogue_actor_name(actor),
            "summary": str(situation.get("summary", "help with their work")),
            "made_day": self.dialogue_day_key(),
            "status": "active",
            "stage": int(situation.get("stage", 0) or 0),
        }
        slot["active"] = record
        return record

    def dialogue_resolve_promise(
        self,
        actor: Dict[str, object],
        kind: str,
        status: str,
        note: str,
    ) -> None:
        slot = self.dialogue_promise_store().setdefault(
            self.dialogue_promise_key(actor, kind), {"active": {}, "history": []}
        )
        active = dict(slot.get("active", {}) or {})
        if not active:
            return
        active["status"] = str(status)
        active["resolved_day"] = self.dialogue_day_key()
        active["note"] = str(note)
        slot["history"] = (list(slot.get("history", []) or []) + [active])[-12:]
        slot["active"] = {}

    def dialogue_promise_callback(
        self, actor: Dict[str, object], kind: str
    ) -> str:
        slot = self.dialogue_promise_store().get(self.dialogue_promise_key(actor, kind), {})
        active = dict(slot.get("active", {}) or {}) if isinstance(slot, dict) else {}
        if not active:
            return ""
        current_day = self.dialogue_day_key()
        promise_type = str(active.get("type", ""))
        target_id = str(active.get("id", ""))
        summary = str(active.get("summary", "what you offered to do"))
        fulfilled = False
        if promise_type == "authored_errand":
            fulfilled = target_id in set(getattr(self.state, "completed_errand_ids", []) or [])
        elif promise_type in {"procedural_request", "procedural_quest"}:
            request = actor.get("active_request", {})
            fulfilled = bool(
                isinstance(request, dict)
                and str(request.get("id", "")) == target_id
                and str(request.get("status", "")) == "completed"
            )
        elif promise_type == "traveler_assignment" and hasattr(self, "recurring_wilderness_traveler_record"):
            record = self.recurring_wilderness_traveler_record(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
            )
            fulfilled = int(record.get("story_stage", 0) or 0) > int(active.get("stage", 0) or 0)
        if fulfilled:
            self.dialogue_resolve_promise(actor, kind, "fulfilled", summary)
            return f"You followed through on your promise to {summary}. I noticed, and I appreciate it."
        if promise_type == "authored_errand" and str(active.get("made_day", "")) != current_day:
            if kind == "authored" and hasattr(self, "adjust_town_npc_relationship"):
                self.adjust_town_npc_relationship(str(actor.get("id", "")), -1)
            self.dialogue_resolve_promise(actor, kind, "missed", summary)
            return f"You said you would {summary}, but the day passed before it happened. I will make other arrangements."
        if str(active.get("last_reminder_day", "")) == current_day:
            return ""
        live = self.dialogue_promise_store()[self.dialogue_promise_key(actor, kind)]["active"]
        live["last_reminder_day"] = current_day
        return f"You said you would {summary}. I'm still counting on you."

    def dialogue_work_situation(
        self, actor: Dict[str, object], kind: str
    ) -> Optional[Dict[str, object]]:
        if hasattr(self, "world_opportunity_situation_for_actor"):
            opportunity = self.world_opportunity_situation_for_actor(actor, kind)
            if opportunity:
                return opportunity
        if kind == "authored" and hasattr(self, "errand_for_npc"):
            errand = self.errand_for_npc(actor)
            if isinstance(errand, dict) and not errand.get("completed"):
                item, qty = str(errand.get("item", "supplies")), int(errand.get("qty", 1))
                return {
                    "type": "authored_errand", "id": str(errand.get("id", "")),
                    "summary": f"bring me {quantity_item_phrase(item, qty)}", "record": errand,
                    "prompt": f"I need {quantity_item_phrase(item, qty)} before the day is over. I can pay {errand.get('money', 0)}g.",
                    "promise": True, "deadline": "today",
                    "ready": bool(self.can_complete_errand(errand)),
                }
        if kind == "procedural" and hasattr(self, "ensure_procedural_resident_request"):
            plan = self.current_procedural_town_plan() or {}
            request = self.ensure_procedural_resident_request(
                int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0)), str(actor.get("id", ""))
            )
            if isinstance(request, dict) and str(request.get("status", "")) in {"offered", "active", "ready"}:
                quest_id = str(request.get("quest_id", ""))
                quest = self.quest_record(quest_id) if quest_id and hasattr(self, "quest_record") else {}
                status = str(quest.get("status", request.get("status", "offered")))
                objective = self.quest_current_objective(quest) if quest and hasattr(self, "quest_current_objective") else {}
                summary = str(objective.get("description", request.get("objective_summary", "help with the request")))
                return {
                    "type": "procedural_quest", "id": str(request.get("id", "")),
                    "quest_id": quest_id, "quest_record": quest,
                    "title": str(request.get("title", "Resident Request")),
                    "summary": clause_from_sentence(summary), "record": request,
                    "prompt": str(request.get("offer_text") or request.get("description") or summary),
                    "promise": status == "offered", "deadline": "until the request is completed",
                    "ready": status == "ready",
                    "chunk_x": int(plan.get("chunk_x", 0)), "chunk_y": int(plan.get("chunk_y", 0)),
                }
        if kind == "traveler" and actor.get("recurring") and hasattr(self, "recurring_wilderness_traveler_assignment"):
            assignment = self.recurring_wilderness_traveler_assignment(actor)
            record = self.recurring_wilderness_traveler_record(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
            )
            if assignment and int(record.get("bond", 0) or 0) >= int(assignment.get("bond", 0) or 0):
                item, qty = str(assignment.get("item", "")), int(assignment.get("qty", 0) or 0)
                materials_ready = not item or int(self.state.inventory.get(item, 0) or 0) >= qty
                stamina_ready = int(getattr(self.state, "stamina", 0) or 0) >= int(assignment.get("stamina", 0) or 0)
                requirements = f" It requires {quantity_item_phrase(item, qty)}." if item else ""
                return {
                    "type": "traveler_assignment", "id": str(assignment.get("name", "regional assignment")),
                    "summary": f"help establish {assignment.get('name', 'the regional route')}",
                    "record": assignment, "stage": int(record.get("story_stage", 0) or 0),
                    "prompt": f"The next real piece of work is {assignment.get('name', 'the regional assignment')}.{requirements} It will take {assignment.get('stamina', 0)} stamina and about {assignment.get('minutes', 0)} minutes.",
                    "promise": True, "deadline": "whenever the route work is completed",
                    "ready": materials_ready and stamina_ready,
                }
        if kind == "caretaker" and hasattr(self, "perform_wilderness_structure_work"):
            record = self.wilderness_structure_record()
            if record.get("repaired") and record.get("activity_week") != self.stronghold_cache_week_key():
                return {
                    "type": "caretaker_work", "id": f"site-work:{self.stronghold_cache_week_key()}",
                    "summary": "help with this site's current regional work",
                    "prompt": "There is work to do around the site. It will take some time and energy, but I can pay the posted reward.",
                    "promise": False, "ready": True,
                }
        return None

    def dialogue_complete_work_situation(
        self, actor: Dict[str, object], kind: str, situation: Dict[str, object]
    ) -> bool:
        situation_type = str(situation.get("type", ""))
        if situation_type == "authored_errand":
            return bool(self.complete_errand(dict(situation.get("record", {}) or {})))
        if situation_type in {"procedural_request", "procedural_quest"}:
            return bool(self.complete_procedural_settlement_request(
                int(situation.get("chunk_x", 0)), int(situation.get("chunk_y", 0)), str(actor.get("id", ""))
            ))
        if situation_type == "traveler_assignment":
            return bool(self.complete_recurring_wilderness_traveler_assignment(actor))
        if situation_type == "caretaker_work":
            return bool(self.perform_wilderness_structure_work())
        if situation_type == "world_opportunity":
            quest_id = str(situation.get("quest_id", ""))
            quest = self.quest_record(quest_id) if quest_id else {}
            return bool(
                quest
                and str(quest.get("status", "")) == "ready"
                and self.complete_quest(quest_id)
            )
        return False

    def dialogue_actor_quest_entries(
        self, actor: Dict[str, object], kind: str
    ) -> List[Dict[str, object]]:
        """Every request from this actor the player is currently carrying.

        Conversation-accepted quests and legacy resident/companion/contract
        quests complete through different code paths, so each entry records
        which one to use rather than assuming a single generic completer.
        """
        actor_id = str(actor.get("id", "") or "")
        if not actor_id or not hasattr(self, "ensure_quest_state"):
            return []
        if hasattr(self, "sync_legacy_quest_records"):
            self.sync_legacy_quest_records()
        if hasattr(self, "refresh_quest_states"):
            self.refresh_quest_states()
        situation = self.dialogue_work_situation(actor, kind)
        situation_quest_id = (
            self.dialogue_quest_id(actor, kind, situation)
            if situation and hasattr(self, "dialogue_quest_id")
            else ""
        )
        entries: List[Dict[str, object]] = []
        for quest in self.ensure_quest_state().values():
            status = str(quest.get("status", ""))
            if status not in {"active", "ready"}:
                continue
            quest_id = str(quest.get("id", ""))
            if quest_id.startswith("relationship_story:"):
                continue
            if quest_id.startswith("dialogue:"):
                # Only offer it while the underlying request is still on offer;
                # an expired same-day errand is closed out elsewhere.
                if not situation_quest_id or quest_id != situation_quest_id:
                    continue
                entries.append({"quest": quest, "ready": status == "ready", "situation": situation})
                continue
            if str(quest.get("giver_id", "")) != actor_id:
                continue
            if bool(quest.get("legacy_managed", False)) and not bool(quest.get("legacy_direct_turn_in", False)):
                continue
            # Most residents have a standing request on offer that the player
            # has never engaged with; those belong on the request board, not in
            # "I finished one of your requests". Only count work actually taken
            # on, or work that can be handed over right now.
            if quest.get("accepted_day") is None and status != "ready":
                continue
            entries.append({"quest": quest, "ready": status == "ready", "situation": None})
        return entries

    def dialogue_quest_outstanding_text(self, quest: Dict[str, object]) -> str:
        objective = (
            self.quest_current_objective(quest)
            if hasattr(self, "quest_current_objective") else {}
        )
        return str(objective.get("description", "the work we agreed on") or "the work we agreed on")

    def dialogue_handle_quest_turn_in(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        entries = self.dialogue_actor_quest_entries(actor, kind)
        if not entries:
            return self.dialogue_say(
                actor, "You have not taken anything on for me yet.", "work", transcript,
            )
        options: List[DialogueOption] = []
        for index, entry in enumerate(entries):
            quest = dict(entry["quest"])
            options.append((
                str(index),
                str(quest.get("title", "Request")),
                "Ready to hand over now."
                if entry["ready"]
                else f"Not finished: {self.dialogue_quest_outstanding_text(quest)}",
            ))
        options.append(("back", "Never mind", "Return to the conversation."))
        choice = self.dialogue_choose(actor, "Which request?", "decision", options, transcript)
        if not choice or choice == "back":
            return True
        try:
            entry = entries[int(choice)]
        except (TypeError, ValueError, IndexError):
            return True
        quest = entry["quest"]
        if not entry["ready"]:
            return self.dialogue_say(
                actor,
                f"Not yet — {self.dialogue_quest_outstanding_text(quest)}",
                "outcome", transcript,
            )
        situation = entry["situation"]
        if situation is not None:
            # Conversation-accepted work pays through the original errand or
            # request, not through the quest's own (empty) reward table.
            success = bool(self.dialogue_complete_work_situation(actor, kind, situation))
            if success:
                self.dialogue_resolve_promise(
                    actor, kind, "fulfilled", str(situation.get("summary", "the work")),
                )
                if hasattr(self, "complete_dialogue_quest_for_situation"):
                    self.complete_dialogue_quest_for_situation(actor, kind, situation)
        else:
            success = bool(
                self.dialogue_turn_in_quest(quest)
                if hasattr(self, "dialogue_turn_in_quest") else False
            )
        if success:
            return self.dialogue_say(actor, "That settles it. Thank you.", "outcome", transcript)
        return self.dialogue_say(
            actor,
            str(getattr(self.state, "message", "That could not be settled right now.")),
            "outcome", transcript,
        )

    def dialogue_offer_quest_turn_in(
        self,
        actor: Dict[str, object],
        quest: Dict[str, object],
        transcript: List[Dict[str, str]],
    ) -> bool:
        title = str(quest.get("title", "that request"))
        if not self.dialogue_say(
            actor, f"About {title} — I believe that's finished on your end. Do you have it?", "work", transcript
        ):
            return False
        options: List[DialogueOption] = [
            ("turn_in", "Yes, here it is.", "Complete the request now and receive its reward."),
            ("later", "Not yet.", "Leave the request open for later."),
        ]
        choice = self.dialogue_choose(actor, "Turn it in now?", "decision", options, transcript)
        if choice == "turn_in":
            success = self.dialogue_turn_in_quest(quest) if hasattr(self, "dialogue_turn_in_quest") else False
            if success:
                return self.dialogue_say(actor, "That settles it. Thank you.", "outcome", transcript)
            return self.dialogue_say(
                actor,
                str(getattr(self.state, "message", "That could not be settled right now.")),
                "outcome", transcript,
            )
        return self.dialogue_say(actor, "All right. I will hold onto it until you are ready.", "outcome", transcript)

    def dialogue_handle_work_situation(
        self,
        actor: Dict[str, object],
        kind: str,
        transcript: List[Dict[str, str]],
    ) -> bool:
        if hasattr(self, "dialogue_ready_quest_from_actor"):
            ready_quest = self.dialogue_ready_quest_from_actor(actor)
            if ready_quest:
                return self.dialogue_offer_quest_turn_in(actor, ready_quest, transcript)
        situation = self.dialogue_work_situation(actor, kind)
        if not situation:
            return self.dialogue_say(
                actor, self.dialogue_work_answer(actor, kind, True), "work", transcript
            )
        # A request already accepted as a tracked quest is turned in through the
        # same completion path, so say that plainly instead of re-offering it as
        # if it were new work the player had never agreed to.
        accepted_quest: Dict[str, object] = {}
        if hasattr(self, "dialogue_quest_id") and hasattr(self, "quest_record"):
            accepted_quest = self.quest_record(
                self.dialogue_quest_id(actor, kind, situation)
            ) or {}
            if str(accepted_quest.get("status", "")) not in {"active", "ready"}:
                accepted_quest = {}
        prompt_text = str(situation["prompt"])
        if accepted_quest:
            prompt_text = (
                f"About {accepted_quest.get('title', 'what you agreed to')} — "
                f"{prompt_text}"
            )
        if not self.dialogue_say(actor, prompt_text, "work", transcript):
            return False
        options: List[DialogueOption] = []
        if situation.get("ready"):
            if accepted_quest:
                options.append((
                    "now",
                    f"Turn in: {accepted_quest.get('title', 'the agreed work')}",
                    "Hand over the agreed items or finish the work now and receive the reward.",
                ))
            else:
                options.append(("now", "Do the work now", "The listed items, stamina, time, and rewards apply immediately."))
        elif accepted_quest:
            options.append((
                "status", "Ask what is still outstanding",
                "Hear exactly what this tracked quest still needs before it can be turned in.",
            ))
        if situation.get("promise") and not accepted_quest:
            options.append((
                "promise", "Accept as a tracked quest",
                f"Adds this request to the Quest Log and records your commitment {situation.get('deadline', 'until it is resolved')}."
            ))
        options.append(("decline", "Not right now", "Makes no promise and causes no relationship penalty."))
        choice = self.dialogue_choose(actor, "What will you do?", "decision", options, transcript)
        if choice == "status":
            objective = (
                self.quest_current_objective(accepted_quest)
                if hasattr(self, "quest_current_objective") else {}
            )
            return self.dialogue_say(
                actor,
                f"Not yet — {objective.get('description', 'the agreed work is still unfinished')}",
                "outcome", transcript,
            )
        if choice == "now":
            success = self.dialogue_complete_work_situation(actor, kind, situation)
            if success:
                self.dialogue_resolve_promise(actor, kind, "fulfilled", str(situation.get("summary", "the work")))
                if hasattr(self, "complete_dialogue_quest_for_situation"):
                    self.complete_dialogue_quest_for_situation(actor, kind, situation)
                return self.dialogue_say(actor, "That takes care of it. Thank you.", "outcome", transcript)
            return self.dialogue_say(actor, str(getattr(self.state, "message", "The work could not be completed right now.")), "outcome", transcript)
        if choice == "promise":
            self.dialogue_record_promise(actor, kind, situation)
            quest = (
                self.accept_dialogue_quest(actor, kind, situation)
                if hasattr(self, "accept_dialogue_quest")
                else {}
            )
            return self.dialogue_say(
                actor,
                f"All right. I'll be waiting for you to {situation.get('summary', 'help')}. Let me know when it's done.",
                "outcome", transcript,
            )
        return self.dialogue_say(actor, "All right. I will ask someone else.", "outcome", transcript)

    def dialogue_interest_answer(self, actor: Dict[str, object]) -> str:
        role = self.dialogue_actor_role(actor)
        interests = list(actor.get("hobbies", []) or actor.get("interests", []) or ROLE_INTERESTS.get(role, ()))
        if not interests:
            likes = [str(value) for value in actor.get("likes", []) or []][:2]
            interests = likes or ["walking", "local stories"]
        listed = ", ".join(str(value).lower() for value in interests[:3])
        primary = str(interests[0]).lower()
        templates = (
            f"When work allows it, I make time for {listed}.",
            f"Lately I have been spending any free moment on {primary}.",
            f"If a whole afternoon opened up, I would probably lose it to {primary}.",
            f"{listed[:1].upper()}{listed[1:]} -- that is where my attention goes once the work is done.",
        )
        return _stable_pick(f"{self.dialogue_day_key()}:{actor.get('id')}:interests", templates)

    def dialogue_personal_story(self, actor: Dict[str, object], kind: str) -> str:
        """Offer a concrete anecdote assembled from facts this actor actually has."""
        personal_history = str(actor.get("personal_history", "") or "").strip()
        if personal_history:
            return personal_history
        name = self.dialogue_actor_name(actor)
        origin = str(
            actor.get("origin")
            or actor.get("home_name")
            or actor.get("home")
            or actor.get("district")
            or ""
        ).strip()
        role = self.dialogue_actor_role(actor).lower()
        activity = self.dialogue_activity(actor, kind).replace("their ", "my ")
        interests = list(actor.get("hobbies", []) or actor.get("interests", []) or ())
        if origin:
            return (
                f"When I first came from {origin}, I underestimated how much time {role} work would take. "
                f"These days, most of it looks like {activity}."
            )
        if interests:
            interest = str(interests[0]).lower()
            return (
                f"I started making time for {interest} because my work kept taking over the entire day. "
                f"I am not always good at stopping, but the habit has lasted."
            )
        return (
            f"Not long ago, while I was {activity}, a small problem took most of the afternoon. "
            "I fixed it eventually, but I still check that part of the work twice."
        )

    def dialogue_known_people(self, actor: Dict[str, object], kind: str) -> List[Dict[str, object]]:
        people: List[Dict[str, object]] = []
        ids: List[str] = []
        for field in ("social_partner_id", "npc_spouse_id", "courtship_partner_id"):
            value = str(actor.get(field, ""))
            if value:
                ids.append(value)
        ids.extend(str(value) for value in actor.get("child_ids", []) or [])
        ids.extend(str(value) for value in actor.get("household_member_ids", []) or [])
        if hasattr(self, "npc_family_profile"):
            profile = self.npc_family_profile(str(actor.get("id", "")))
            if isinstance(profile, dict):
                ids.extend(str(value) for value in profile.get("child_ids", []) or [])
                ids.extend(str(value) for value in profile.get("parent_ids", []) or [])
                for field in ("npc_spouse_id", "courtship_partner_id"):
                    value = str(profile.get(field, ""))
                    if value:
                        ids.append(value)
        if hasattr(self, "npc_family_relative_ids"):
            ids.extend(self.npc_family_relative_ids(str(actor.get("id", ""))))
        if kind == "procedural" and hasattr(self, "current_procedural_town_plan"):
            plan = self.current_procedural_town_plan() or {}
            population = self.procedural_settlement_population(
                int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))
            )
            if isinstance(population, dict):
                members = self.procedural_npc_dialogue_builder().household_members(actor, population)
                people.extend(member for member in members if isinstance(member, dict))
        if self.dialogue_is_persistent_world_actor(actor, kind):
            profiles = getattr(self.state, "world_npc_profiles", {})
            origin = str(actor.get("origin_name") or actor.get("origin") or "").casefold()
            if isinstance(profiles, dict) and origin:
                local_peers = [
                    profile for profile in profiles.values()
                    if isinstance(profile, dict)
                    and str(profile.get("id", "")) != str(actor.get("id", ""))
                    and str(profile.get("origin_name") or profile.get("origin") or "").casefold() == origin
                ]
                local_peers.sort(key=lambda profile: str(profile.get("id", "")))
                people.extend(local_peers[:4])
        for person_id in ids:
            person = self.npc_record_by_id(person_id) if hasattr(self, "npc_record_by_id") else None
            if isinstance(person, dict):
                people.append(person)
        unique: Dict[str, Dict[str, object]] = {}
        for person in people:
            unique.setdefault(str(person.get("id", person.get("name"))), person)
        return list(unique.values())[:12]

    def dialogue_news_answer(self, actor: Dict[str, object], kind: str) -> str:
        rumors = self.dialogue_refresh_routine_rumors(actor, kind)
        if rumors:
            packet = rumors[-1]
            source = str(packet.get("source", "someone on my route"))
            text = _first_person(packet.get("text", ""), self.dialogue_actor_name(actor))
            if source in {"something they witnessed around town", "something they personally witnessed"}:
                return f"I saw this myself: {text}"
            if source == "public notice":
                return f"The public notice says: {text}"
            return f"{source} told me: {text}"
        return "I haven't heard anything reliable enough to repeat."

    def dialogue_companion_answer(self, actor: Dict[str, object]) -> str:
        # Every branch here used to be a single fixed sentence, so asking twice
        # returned the same words for the rest of the game.
        seed = f"{self.dialogue_day_key()}:{actor.get('id')}:companions"
        follower_ids = list(getattr(self.state, "travel_follower_ids", []) or [])
        if follower_ids and hasattr(self, "travel_follower_data"):
            names = name_list([
                str(self.travel_follower_data(follower_id).get("name", "a companion"))
                for follower_id in follower_ids
            ])
            return _stable_pick(seed, (
                f"I can see you are traveling with {names}. How long have you been on the road together?",
                f"You have {names} with you. A route is easier with somebody to disagree with.",
                f"Traveling with {names}, then. Company changes which roads are sensible.",
                f"You and {names} look like you have been walking a while. Rest if you need it.",
            ))
        if self.dialogue_actor_role(actor) in {"Traveler", "Ranger", "Hunter", "Wayfarer"}:
            return _stable_pick(seed, (
                "I sometimes travel with other people when a route is dangerous or the work needs more hands.",
                "I take company when the road earns it. Most days it does not.",
                "I have walked with others when the season made it sensible. I have also walked alone and preferred it.",
                "It depends on the route. Some of them are not worth doing without a second pair of eyes.",
            ))
        return _stable_pick(seed, (
            "It looks like you are traveling alone today.",
            "Nobody with you today, then. That suits some people.",
            "You are on your own out here. I hope that is by choice.",
            "Just you today. The road is quieter that way, for better or worse.",
        ))

    def dialogue_social_key(self, actor: Dict[str, object], kind: str) -> str:
        return f"{kind}:{actor.get('id') or actor.get('name') or 'npc'}"

    def dialogue_social_slot(
        self, actor: Dict[str, object], kind: str
    ) -> Dict[str, object]:
        store = getattr(self.state, "npc_dialogue_social_state", None)
        if not isinstance(store, dict):
            store = {}
            self.state.npc_dialogue_social_state = store
        key = self.dialogue_social_key(actor, kind)
        slot = store.setdefault(key, {})
        if not isinstance(slot, dict):
            slot = {}
            store[key] = slot
        disclosures = slot.get("disclosures", [])
        slot["disclosures"] = [row for row in disclosures if isinstance(row, dict)][-12:]
        witnessed = slot.get("witnessed_events", [])
        valid_witnessed: List[Dict[str, object]] = []
        for row in witnessed:
            if not isinstance(row, dict):
                continue
            action = self.world_dialogue_event_action(row.get("text", ""))
            category = str(row.get("category", ""))
            if not action and category not in {"combat", "social"}:
                continue
            row["action"] = action
            valid_witnessed.append(row)
        slot["witnessed_events"] = valid_witnessed[-8:]
        for field, limit in (
            ("knowledge", 16), ("threads", 6), ("thread_history", 12),
            ("introductions", 8), ("meetings", 6), ("invitation_history", 8),
            ("story_consequences", 8),
        ):
            rows = slot.get(field, [])
            slot[field] = [row for row in rows if isinstance(row, dict)][-limit:]
        for field, limit in (
            ("recent_observation_templates", 12),
            ("recent_observation_reactions", 10),
            ("recent_companion_line_ids", 12),
        ):
            values = slot.get(field, [])
            if not isinstance(values, list):
                values = []
            slot[field] = [str(value)[:120] for value in values if str(value or "")][-limit:]
        # Story threads created by the earlier automatic system did not record
        # whether their opening was ever spoken. Retire those fragments instead
        # of presenting a mid-story "since we last spoke" prompt in old saves.
        for thread in slot["threads"]:
            if "introduced" not in thread:
                thread["status"] = "retired"
        if not isinstance(slot.get("mood", {}), dict):
            slot["mood"] = {}
        if not isinstance(slot.get("initiation", {}), dict):
            slot["initiation"] = {}
        initiation = slot.get("initiation", {})
        if isinstance(initiation, dict) and str(initiation.get("reason", "")) == "witnessed_event":
            source_id = str(initiation.get("source_event_id", ""))
            source = next(
                (
                    row for row in slot["witnessed_events"]
                    if source_id and str(row.get("id", "")) == source_id
                ),
                None,
            )
            if not source or str(source.get("category", "")) != "combat":
                slot["initiation"] = {}
        if not isinstance(slot.get("invitation", {}), dict):
            slot["invitation"] = {}
        if not isinstance(slot.get("story_aftermath", {}), dict):
            slot["story_aftermath"] = {}
        return slot

    def dialogue_absolute_day(self) -> int:
        if hasattr(self, "absolute_game_day"):
            return int(self.absolute_game_day())
        return (
            max(0, int(getattr(self.state, "year", 1)) - 1) * 112
            + max(0, int(getattr(self.state, "month", 1)) - 1) * 28
            + max(1, int(getattr(self.state, "day", 1)))
        )

    def dialogue_set_mood(
        self,
        actor: Dict[str, object],
        kind: str,
        label: str,
        cause: str,
        intensity: int = 1,
        duration_days: int = 2,
    ) -> Dict[str, object]:
        slot = self.dialogue_social_slot(actor, kind)
        mood = {
            "label": str(label),
            "cause": str(cause),
            "intensity": max(1, min(3, int(intensity))),
            "started_day": self.dialogue_absolute_day(),
            "expires_day": self.dialogue_absolute_day() + max(1, int(duration_days)),
        }
        slot["mood"] = mood
        return mood

    def dialogue_current_mood(
        self, actor: Dict[str, object], kind: str
    ) -> Dict[str, object]:
        slot = self.dialogue_social_slot(actor, kind)
        mood = slot.get("mood", {})
        if not isinstance(mood, dict) or not mood.get("label"):
            return {}
        if int(mood.get("expires_day", 0) or 0) < self.dialogue_absolute_day():
            slot["mood"] = {}
            return {}
        return mood

    def dialogue_mood_context_line(
        self, actor: Dict[str, object], kind: str
    ) -> str:
        mood = self.dialogue_current_mood(actor, kind)
        if not mood:
            return ""
        label = str(mood.get("label", "thoughtful"))
        cause = str(mood.get("cause", "recent events"))
        return {
            "grateful": f"I am still grateful about {cause}.",
            "worried": f"I have been worried about {cause}.",
            "angry": f"I am still angry about {cause}.",
            "grieving": f"I am carrying some grief about {cause}; I may not have many words for it.",
            "excited": f"I am genuinely excited about {cause}.",
            "embarrassed": f"I am still a little embarrassed about {cause}.",
            "suspicious": f"I remain suspicious about {cause}.",
            "proud": f"I am proud of what happened with {cause}.",
        }.get(label, f"I have been feeling {label} because of {cause}.")

    def dialogue_add_knowledge(
        self,
        actor: Dict[str, object],
        kind: str,
        text: str,
        *,
        subject: str = "local news",
        source_name: str = "personal observation",
        source_kind: str = "firsthand",
        confidence: int = 100,
        knowledge_id: str = "",
        original_text: str = "",
        distorted: bool = False,
        corrected: bool = False,
    ) -> Dict[str, object]:
        clean = " ".join(str(text or "").split())[:240]
        if not clean:
            return {}
        packet_id = str(knowledge_id or hashlib.sha256(
            f"{subject}:{clean}".encode("utf-8")
        ).hexdigest()[:16])
        slot = self.dialogue_social_slot(actor, kind)
        existing = next(
            (row for row in slot["knowledge"] if str(row.get("id", "")) == packet_id),
            None,
        )
        packet = {
            "id": packet_id,
            "subject": str(subject),
            "text": clean,
            "source_name": str(source_name),
            "source_kind": str(source_kind),
            "confidence": max(10, min(100, int(confidence))),
            "day": self.dialogue_day_key(),
            "location": self.world_dialogue_location_label() if hasattr(self, "world_dialogue_location_label") else str(getattr(self.state, "location", "Elsewhere")),
            "distorted": bool(distorted),
            "corrected": bool(corrected),
        }
        if original_text:
            packet["original_text"] = " ".join(str(original_text).split())[:240]
        if existing is not None:
            # A firsthand correction is authoritative for this listener.  An
            # older uncorrected copy may still circulate elsewhere, but hearing
            # it again must not overwrite what the player already clarified.
            if bool(existing.get("corrected")) and not bool(packet.get("corrected")):
                return existing
            existing.update(packet)
            return existing
        slot["knowledge"] = (list(slot["knowledge"]) + [packet])[-16:]
        return packet

    # A rumour about the player is recorded second person ("You defeated the
    # cave lurker near the mine.") and until now travelled word-perfect, only
    # losing confidence. These swaps are what actually gets misremembered
    # between one telling and the next: the verb. Each pair keeps the sentence
    # grammatical while changing what it claims, so the player has something
    # worth correcting rather than a vaguer version of the truth.
    RUMOR_VERB_DRIFT: Dict[str, Tuple[str, ...]] = {
        "defeated": ("chased off", "barely escaped from", "needed help defeating"),
        "rescued": ("were paid to rescue", "nearly failed to rescue", "only helped rescue"),
        "extinguished": ("watched someone put out", "accidentally started"),
        "cleared": ("helped clear", "paid somebody to clear", "claimed to have cleared"),
        "repaired": ("replaced", "patched", "were shown how to repair"),
        "built": ("paid somebody to build", "helped somebody build", "claimed credit for building"),
        "crafted": ("bought", "were given", "traded for"),
        "completed": ("half finished", "took credit for completing", "needed help completing"),
        "discovered": ("were told about", "walked past", "claimed to find"),
        "helped": ("were paid to help", "watched somebody help", "promised to help"),
    }

    def dialogue_drift_rumor(self, text: object, seed: str) -> str:
        """Garble a second-person rumour the way retelling actually garbles one.

        Returns "" when nothing sensible can be changed, so the caller keeps the
        accurate wording rather than inventing a distortion.
        """
        line = " ".join(str(text or "").split())
        if not line.lower().startswith("you "):
            return ""
        rest = line[4:]
        for past, replacements in self.RUMOR_VERB_DRIFT.items():
            if not rest.lower().startswith(past + " ") and rest.lower() != past + ".":
                continue
            swapped = _stable_pick(f"{seed}:drift:{past}", replacements)
            if not swapped:
                return ""
            tail = rest[len(past):]
            return f"You {swapped}{tail}"
        return ""

    def dialogue_player_rumor_first_person(self, text: object) -> str:
        """Convert an authored second-person player rumor into player speech."""
        line = " ".join(str(text or "").split())
        if not line:
            return ""
        openings = (
            (r"^You are\b", "I am"),
            (r"^You were\b", "I was"),
            (r"^You have\b", "I have"),
            (r"^You had\b", "I had"),
            (r"^You do\b", "I do"),
            (r"^You did\b", "I did"),
            (r"^You\b", "I"),
        )
        for pattern, replacement in openings:
            converted, count = re.subn(pattern, replacement, line, count=1, flags=re.I)
            if count:
                line = converted
                break
        line = re.sub(r"\byourself\b", "myself", line, flags=re.I)
        line = re.sub(r"\byours\b", "mine", line, flags=re.I)
        line = re.sub(r"\byour\b", "my", line, flags=re.I)
        return line

    def dialogue_knowledge_is_about_player(self, packet: object) -> bool:
        """A packet the player can speak to: recorded about them, in second person."""
        if not isinstance(packet, dict):
            return False
        return " ".join(str(packet.get("text", "")).split()).lower().startswith("you ")

    def dialogue_distorted_player_rumors(
        self, actor: Dict[str, object], kind: str
    ) -> List[Dict[str, object]]:
        """Packets this NPC holds that are wrong about the player and still fixable."""
        slot = self.dialogue_social_slot(actor, kind)
        return [
            row for row in slot.get("knowledge", []) or []
            if isinstance(row, dict)
            and row.get("distorted")
            and not row.get("corrected")
            and str(row.get("original_text", ""))
            and self.dialogue_knowledge_is_about_player(row)
        ]

    def dialogue_correct_knowledge(
        self, actor: Dict[str, object], kind: str, packet_id: str
    ) -> Dict[str, object]:
        """Set the record straight: restore the firsthand wording and re-raise confidence.

        The corrected packet keeps travelling, so the fix spreads the same way
        the error did instead of stopping with the one person who was told.
        """
        slot = self.dialogue_social_slot(actor, kind)
        packet = next(
            (row for row in slot.get("knowledge", []) or []
             if isinstance(row, dict) and str(row.get("id", "")) == str(packet_id)),
            None,
        )
        if not packet:
            return {}
        original = str(packet.get("original_text", "") or "")
        if not original:
            return {}
        packet["text"] = original
        packet["distorted"] = False
        packet["corrected"] = True
        packet["source_kind"] = "corrected"
        packet["source_name"] = str(getattr(self.state, "player_name", "the player"))
        packet["confidence"] = 95
        return packet

    def dialogue_handle_rumor_correction(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        """Let the player set straight a garbled rumour about themselves.

        Only reachable when this NPC is actually holding a distorted packet, so
        the option never appears as decoration.
        """
        wrong = self.dialogue_distorted_player_rumors(actor, kind)
        if not wrong:
            return True
        options: List[DialogueOption] = [
            (
                str(row.get("id", "")),
                str(row.get("text", "")),
                "They heard this from %s." % str(row.get("source_name", "someone")),
            )
            for row in wrong[-4:]
        ]
        options.append(("back", "Leave it for now", "Let the story stand as they heard it."))
        chosen = self.dialogue_choose(
            actor, "What did they get wrong?", "the record", options, transcript
        )
        if not chosen or chosen == "back":
            return True
        packet = next(
            (row for row in wrong if str(row.get("id", "")) == chosen), None
        )
        if not packet:
            return True
        garbled = str(packet.get("text", ""))
        truth = str(packet.get("original_text", ""))
        spoken_truth = self.dialogue_player_rumor_first_person(truth)
        if not self.dialogue_say(
            self.dialogue_player_speaker(),
            "That is not quite how it went. %s" % spoken_truth,
            "you",
            transcript,
        ):
            return False
        corrected = self.dialogue_correct_knowledge(actor, kind, chosen)
        if not corrected:
            return True
        demeanor = self.dialogue_demeanor(actor, kind)
        reactions = {
            "professional": (
                "Then I have been repeating it wrong. I will say so next time it comes up.",
                "Noted, and corrected. I would rather carry the accurate version.",
            ),
            "warm": (
                "Oh, I am glad you said something. I have been telling it the other way.",
                "Thank you for putting me right. I would hate to have kept spreading that.",
            ),
            "skeptical": (
                "That is a better story than the one going round, which makes me believe it.",
                "I did wonder. The version I had did not quite hang together.",
            ),
            "blunt": (
                "Right. I had it wrong. It will not happen twice.",
                "Good. I would rather be corrected than repeat nonsense.",
            ),
            "reserved": (
                "Thank you. I will keep the accurate version.",
                "I appreciate you telling me. I do not like passing on what I cannot vouch for.",
            ),
            "wary": (
                "Perhaps. I will hold your version alongside the one I was given.",
                "You would say that either way. Still, I will remember you said it.",
            ),
            "hostile": (
                "If you say so. I am not the one who started it.",
                "Fine. Take it up with whoever told me.",
            ),
            "neutral": (
                "Then I had it wrong. I will pass on the version you gave me.",
                "That is worth knowing. I will not repeat the other one.",
            ),
        }
        line = _stable_pick(
            "%s:%s:rumor-correction:%s" % (self.dialogue_day_key(), actor.get("id"), chosen),
            reactions.get(demeanor, reactions["neutral"]),
        )
        self.dialogue_set_mood(actor, kind, "thoughtful", "the story going round about you", 1, 2)
        return self.dialogue_say(actor, line, "response", transcript)

    def dialogue_propagate_knowledge(
        self,
        source_actor: Dict[str, object],
        source_kind: str,
        listener: Dict[str, object],
        listener_kind: str,
    ) -> bool:
        source_slot = self.dialogue_social_slot(source_actor, source_kind)
        listener_slot = self.dialogue_social_slot(listener, listener_kind)
        known_ids = {str(row.get("id", "")) for row in listener_slot["knowledge"]}
        packet = next(
            (
                row for row in reversed(source_slot["knowledge"])
                if str(row.get("id", "")) not in known_ids
                and int(row.get("confidence", 0) or 0) >= 35
            ),
            None,
        )
        if not packet:
            return False
        confidence = max(20, int(packet.get("confidence", 60) or 60) - 18)
        text = str(packet.get("text", ""))
        original = str(packet.get("original_text", "") or text)
        distorted = bool(packet.get("distorted"))
        # Once a retelling has lost enough confidence it starts losing accuracy
        # too, but only for rumours about the player -- those are the ones the
        # player is in a position to correct. A packet already put right stays
        # right as it travels on.
        if (
            not packet.get("corrected")
            and confidence < 60
            and self.dialogue_knowledge_is_about_player(packet)
        ):
            # Seeded on the hop as well as the packet, so a later telling
            # garbles differently rather than repeating the same mistake. Each
            # variant is derived from the firsthand wording, so retellings stay
            # single-step wrong instead of compounding into nonsense.
            drifted = self.dialogue_drift_rumor(
                original, "%s:%d" % (str(packet.get("id", "")), confidence)
            )
            if drifted and drifted != text:
                text = drifted
                distorted = True
        self.dialogue_add_knowledge(
            listener,
            listener_kind,
            text,
            subject=str(packet.get("subject", "local news")),
            source_name=self.dialogue_actor_name(source_actor),
            source_kind="hearsay" if str(packet.get("source_kind")) != "public" else "public",
            confidence=confidence,
            knowledge_id=str(packet.get("id", "")),
            original_text=original,
            distorted=distorted,
            corrected=bool(packet.get("corrected")),
        )
        return True

    def dialogue_arc_profile(
        self, actor: Dict[str, object]
    ) -> Tuple[str, Dict[str, object]]:
        role_words = set(
            self.dialogue_actor_role(actor).casefold().replace("-", " ").split()
        )
        for profile_id, profile in DIALOGUE_ARC_PROFILES.items():
            if profile_id == "personal":
                continue
            if role_words.intersection(set(profile.get("roles", set()))):
                return profile_id, profile
        return "personal", DIALOGUE_ARC_PROFILES["personal"]

    def dialogue_story_aftermath(
        self, actor: Dict[str, object], kind: str
    ) -> Dict[str, object]:
        slot = self.dialogue_social_slot(actor, kind)
        aftermath = slot.get("story_aftermath", {})
        if not isinstance(aftermath, dict) or not aftermath.get("thread_id"):
            return {}
        return aftermath

    def dialogue_story_cooldown_remaining(
        self, actor: Dict[str, object], kind: str
    ) -> int:
        slot = self.dialogue_social_slot(actor, kind)
        resolved_days = [
            int(row.get("resolved_day", 0) or 0)
            for row in slot.get("thread_history", []) or []
            if isinstance(row, dict) and str(row.get("status", "")) == "resolved"
        ]
        if not resolved_days:
            return 0
        return max(0, 14 - (self.dialogue_absolute_day() - max(resolved_days)))

    def dialogue_current_thread(
        self, actor: Dict[str, object], kind: str, create: bool = False
    ) -> Dict[str, object]:
        slot = self.dialogue_social_slot(actor, kind)
        active = next(
            (row for row in slot["threads"] if str(row.get("status", "active")) == "active"),
            None,
        )
        if active or not create:
            return active or {}
        if self.dialogue_story_cooldown_remaining(actor, kind) > 0:
            return {}
        profile_id, profile = self.dialogue_arc_profile(actor)
        latest_history = next(
            (row for row in reversed(slot["thread_history"]) if isinstance(row, dict)),
            {},
        )
        if (
            profile_id != "personal"
            and str(latest_history.get("profile", "")) == profile_id
        ):
            profile_id, profile = "personal", DIALOGUE_ARC_PROFILES["personal"]
        serial = len(slot["thread_history"]) + len(slot["threads"]) + 1
        actor_id = str(actor.get("id") or actor.get("name") or "npc")
        thread = {
            "id": f"{actor_id}:{profile_id}:{serial}",
            "profile": profile_id,
            "title": str(profile.get("title", "An Ongoing Matter")),
            "stage": 0,
            "status": "active",
            "created_day": self.dialogue_absolute_day(),
            "updated_day": self.dialogue_absolute_day(),
            "last_discussed_day": 0,
            "introduced": False,
        }
        slot["threads"] = (list(slot["threads"]) + [thread])[-6:]
        return thread

    def dialogue_should_begin_thread(
        self,
        actor: Dict[str, object],
        kind: str,
        *,
        first_meeting: bool = False,
        repeated_today: bool = False,
        agenda_override: str = "",
    ) -> bool:
        """Only begin a personal arc when the relationship can support one."""
        if first_meeting or repeated_today or agenda_override:
            return False
        if kind in {"traveler", "regional_visitor", "outpost", "caretaker"}:
            if not bool(actor.get("recurring", False)):
                return False
        if (
            kind not in {"authored", "procedural", "spouse", "companion", "traveler"}
            and not self.dialogue_is_persistent_world_actor(actor, kind)
        ):
            return False
        if self.dialogue_relationship_points(actor, kind) < 25:
            return False
        return not bool(self.dialogue_current_thread(actor, kind, create=False))

    def dialogue_thread_line(
        self, actor: Dict[str, object], kind: str, thread: Dict[str, object]
    ) -> str:
        profile = DIALOGUE_ARC_PROFILES.get(
            str(thread.get("profile", "personal")), DIALOGUE_ARC_PROFILES["personal"]
        )
        stages = tuple(profile.get("stages", ()))
        stage = max(0, min(len(stages) - 1, int(thread.get("stage", 0) or 0)))
        return str(stages[stage]) if stages else "There is something unresolved I have been thinking about."

    def dialogue_finalize_thread_resolution(
        self, actor: Dict[str, object], kind: str, thread: Dict[str, object]
    ) -> None:
        if int(thread.get("stage", 0) or 0) < 3 or str(thread.get("status", "")) == "resolved":
            return
        thread["status"] = "resolved"
        thread["resolved_day"] = self.dialogue_absolute_day()
        slot = self.dialogue_social_slot(actor, kind)
        profile = str(thread.get("profile", "personal"))
        aftermath_profile = STORY_AFTERMATH_PROFILES.get(profile, STORY_AFTERMATH_PROFILES["personal"])
        aftermath = {
            "thread_id": str(thread.get("id", "")),
            "profile": profile,
            "title": str(thread.get("title", "A Personal Matter")),
            "summary": str(aftermath_profile["summary"]),
            "activity": str(aftermath_profile["activity"]),
            "follow_up": str(aftermath_profile["follow_up"]),
            "resolved_day": self.dialogue_absolute_day(),
            "available_day": self.dialogue_absolute_day() + 1,
            "acknowledged": False,
            "called_out_day": 0,
        }
        thread["aftermath"] = dict(aftermath)
        slot["story_aftermath"] = aftermath
        if not any(str(row.get("thread_id", "")) == str(thread.get("id", "")) for row in slot["story_consequences"]):
            slot["story_consequences"] = (list(slot["story_consequences"]) + [dict(aftermath)])[-8:]
        actor["story_outcome"] = {
            "thread_id": str(thread.get("id", "")),
            "profile": profile,
            "summary": str(aftermath_profile["summary"]),
            "activity": str(aftermath_profile["activity"]),
            "resolved_day": self.dialogue_absolute_day(),
            "visible_until_day": self.dialogue_absolute_day() + 14,
        }
        if not any(str(row.get("id", "")) == str(thread.get("id", "")) for row in slot["thread_history"]):
            slot["thread_history"] = (list(slot["thread_history"]) + [dict(thread)])[-12:]
        self.dialogue_add_knowledge(
            actor, kind, f"{thread.get('title', 'A personal matter')} reached a stable resolution. {aftermath_profile['summary']}",
            subject="personal story", source_name=self.dialogue_actor_name(actor),
            source_kind="firsthand", confidence=100,
        )

    def dialogue_story_support_plan(
        self, actor: Dict[str, object], kind: str, thread: Dict[str, object]
    ) -> Dict[str, object]:
        profile = str(thread.get("profile", "personal"))
        stage = max(0, min(2, int(thread.get("stage", 0) or 0)))
        actor_name = self.dialogue_actor_name(actor)
        turn_in = self.quest_capture_current_destination()
        turn_in["label"] = f"Return to {actor_name}"
        item_profiles = {
            "work": (
                ("Wood", 5, "Bring basic materials so the competing work demands can be separated in practice."),
                ("Stone", 8, "Bring durable materials for the revised arrangement they have chosen to test."),
                ("Coal", 4, "Bring reliable fuel so the new work routine can survive a complete production cycle."),
            ),
            "care": (
                ("Cave Herbs", 2, "Bring initial care supplies so the concern can be assessed consistently."),
                ("Honey", 1, "Bring a restorative supply that supports the longer care routine."),
                ("Cave Herbs", 4, "Bring enough dependable herbs to stabilize the routine beyond the immediate concern."),
            ),
        }
        if profile in item_profiles:
            item, quantity, objective_text = item_profiles[profile][stage]
            return {
                "description": f"Help {actor_name} with stage {stage + 1} of {str(thread.get('title', 'an ongoing matter')).lower()} through a concrete supply task.",
                "objective": {
                    "id": f"practical_support:{stage}", "kind": "item", "item": item,
                    "target": quantity, "current": 0, "complete": False,
                    "description": f"{objective_text} ({quantity_item_phrase(item, quantity)})",
                },
                "turn_in": turn_in, "consume_items": {item: quantity}, "accompany": False,
            }

        preference_words = {
            "roads": ("wilderness", "mine", "farm", "station", "trail"),
            "research": ("library", "museum", "wilderness", "garden"),
            "community": ("town hall", "town", "market", "green"),
            "personal": ("farm", "inn", "library", "market"),
        }.get(profile, ())
        destinations: List[Tuple[str, Dict[str, object]]] = []
        for place in self.dialogue_known_places(actor, kind):
            destination = self.quest_destination_for_known_place(place)
            if destination:
                destinations.append((str(place.get("name", "Known place")), dict(destination)))
        used_places = {
            str(row.get("place_name", ""))
            for row in thread.get("support_history", []) or []
            if isinstance(row, dict) and row.get("place_name")
        }
        fresh_destinations = [row for row in destinations if row[0] not in used_places]
        if fresh_destinations:
            destinations = fresh_destinations
        preferred = [
            row for row in destinations
            if any(word in row[0].lower() for word in preference_words)
            and not self.quest_destination_reached(row[1], radius=3)
        ]
        pool = preferred or [row for row in destinations if not self.quest_destination_reached(row[1], radius=3)] or destinations
        if not pool:
            return {
                "description": f"Help {actor_name} turn stage {stage + 1} of a personal decision into practical preparation.",
                "objective": {
                    "id": f"practical_support:{stage}", "kind": "item", "item": "Wood",
                    "target": 3 + stage * 2, "current": 0, "complete": False,
                    "description": f"Bring {3 + stage * 2} Wood for the next practical step.",
                },
                "turn_in": turn_in, "consume_items": {"Wood": 3 + stage * 2}, "accompany": False,
            }
        place_name, destination = pool[_stable_index(f"story-support:{thread.get('id')}:{thread.get('stage', 0)}", len(pool))]
        verbs = {
            "roads": "Travel the questioned route and see whether the reported problem is visible on the ground.",
            "research": "Visit a second field site and compare it with the evidence already collected.",
            "community": "Visit the affected public place and listen to what the decision changes there.",
            "personal": "Visit somewhere outside the usual routine and return with a concrete point of comparison.",
        }
        return {
            "description": f"Help {actor_name} with stage {stage + 1} of {str(thread.get('title', 'an ongoing matter')).lower()} by going into the world together.",
            "objective": {
                "id": f"field_support:{stage}", "kind": "visit", "target": 1,
                "current": 0, "complete": False, "destination": destination,
                "description": f"{verbs.get(profile, verbs['personal'])} Destination: {place_name}.",
            },
            "turn_in": turn_in, "consume_items": {},
            "accompany": profile in {"roads", "research"},
            "place_name": place_name,
        }

    def dialogue_begin_story_support(
        self, actor: Dict[str, object], kind: str, thread: Dict[str, object]
    ) -> Dict[str, object]:
        stage = max(0, min(2, int(thread.get("stage", 0) or 0)))
        quest_id = f"relationship_story:{thread.get('id', '')}:stage:{stage}"
        existing = self.quest_record(quest_id) if hasattr(self, "quest_record") else {}
        if existing and str(existing.get("status", "")) in {"active", "ready"}:
            thread["quest_id"] = quest_id
            thread["support_stage"] = stage
            thread["support_status"] = "active"
            return existing
        plan = self.dialogue_story_support_plan(actor, kind, thread)
        actor_id = str(actor.get("id", ""))
        quest = self.register_quest({
            "id": quest_id,
            "title": f"{self.dialogue_actor_name(actor)}: {thread.get('title', 'Practical Support')} — Part {stage + 1}",
            "category": "Relationships",
            "description": str(plan.get("description", "Help with the matter discussed in conversation.")),
            "giver_id": actor_id, "giver_name": self.dialogue_actor_name(actor),
            "participants": [actor_id],
            "objectives": [dict(plan.get("objective", {}))],
            "turn_in": dict(plan.get("turn_in", {}) or {}),
            "consume_items": dict(plan.get("consume_items", {}) or {}),
            "rewards": {"relationship": 3 + stage},
            "journal": [f"You offered practical support during stage {stage + 1} of an ongoing personal conversation."],
            "dialogue_thread_id": str(thread.get("id", "")),
            "dialogue_kind": kind,
            "dialogue_thread_stage": stage,
        }, accept=True)
        thread["quest_id"] = quest_id
        thread["support_stage"] = stage
        thread["support_status"] = "active"
        thread["last_discussed_day"] = self.dialogue_absolute_day()
        thread["updated_day"] = self.dialogue_absolute_day()
        if bool(plan.get("accompany", False)):
            now_minute = self.dialogue_absolute_day() * 1440 + int(getattr(self.state, "hour", 0)) * 60 + int(getattr(self.state, "minute", 0))
            event = self.schedule_planned_event({
                "id": f"story_support:{actor_id}:{now_minute}",
                "title": f"Fieldwork with {self.dialogue_actor_name(actor)}",
                "kind": "story_support", "status": "ready",
                "linked_quest_id": quest_id,
                "due_day": self.dialogue_absolute_day(), "due_hour": int(getattr(self.state, "hour", 0)),
                "destination": dict(plan.get("objective", {}).get("destination", {}) or {}),
                "participants": [{
                    "actor_id": actor_id, "name": self.dialogue_actor_name(actor),
                    "role": str(actor.get("role", "Companion")), "kind": kind,
                    "mode": "accompany", "purpose": "helping investigate their ongoing story",
                    "quest_id": quest_id,
                }],
            })
            self.activate_planned_event(str(event.get("id", "")))
            thread["support_event_id"] = str(event.get("id", ""))
        if not getattr(self.state, "tracked_quest_id", ""):
            self.track_quest(quest_id, announce=False)
        if hasattr(self, "autosave_with_message"):
            self.autosave_with_message(f"Quest accepted: {quest.get('title', 'Practical support')}.")
        return quest

    def dialogue_resolve_story_support(
        self, actor: Dict[str, object], kind: str, thread: Dict[str, object]
    ) -> Tuple[str, int]:
        quest_id = str(thread.get("quest_id", ""))
        quest = self.quest_record(quest_id) if quest_id and hasattr(self, "quest_record") else {}
        if not quest:
            return "", 0
        self.refresh_quest_states()
        quest = self.quest_record(quest_id)
        status = str(quest.get("status", ""))
        if status not in {"ready", "completed"}:
            objective = self.quest_current_objective(quest)
            return f"I'm still waiting on this: {objective.get('description', 'the work we discussed')}", 0
        before = self.dialogue_invitation_relationship(actor, kind)
        if status == "ready" and not self.complete_quest(quest_id, grant_rewards=True):
            return "The objective is ready, but we could not settle it yet.", 0
        relationship = self.dialogue_invitation_relationship(actor, kind) - before
        if str(thread.get("support_status", "")) != "completed":
            completed_quest = self.quest_record(quest_id)
            completed_objective = self.quest_current_objective(completed_quest)
            completed_stage = max(0, min(2, int(thread.get("support_stage", thread.get("stage", 0)) or 0)))
            history = list(thread.get("support_history", []) or [])
            history.append({
                "quest_id": quest_id,
                "stage": completed_stage,
                "completed_day": self.dialogue_absolute_day(),
                "objective": str(completed_objective.get("description", "Practical support completed.")),
                "item": str(completed_objective.get("item", "")),
                "place_name": str(dict(completed_objective.get("destination", {}) or {}).get("label", "")),
                "relationship_gain": int(relationship),
            })
            thread["support_history"] = history[-3:]
            thread["support_status"] = "completed"
            thread["updated_day"] = self.dialogue_absolute_day()
            thread["last_discussed_day"] = self.dialogue_absolute_day()
            thread["stage"] = min(3, max(int(thread.get("stage", 0) or 0), completed_stage + 1))
            self.dialogue_set_mood(actor, kind, "grateful", "the practical support you completed with me", 2, 4)
            self.dialogue_finalize_thread_resolution(actor, kind, thread)
        line = "Your help gave me enough information to decide. " + self.dialogue_thread_line(actor, kind, thread)
        return line, relationship

    def dialogue_advance_thread(
        self,
        actor: Dict[str, object],
        kind: str,
        thread: Dict[str, object],
        approach: str,
    ) -> Tuple[str, int]:
        today = self.dialogue_absolute_day()
        if int(thread.get("last_discussed_day", 0) or 0) == today:
            return "We have already taken this as far as we can today. I need time for the conversation to become a decision.", 0
        thread["last_discussed_day"] = today
        thread["updated_day"] = today
        before = int(thread.get("stage", 0) or 0)
        thread["stage"] = min(3, before + 1)
        relationship = 0
        if approach == "support":
            relationship = self.dialogue_adjust_actor_relationship(actor, kind, 1)
            self.dialogue_set_mood(
                actor, kind, "grateful", "the way you supported me without taking over", 2, 3
            )
        elif approach == "challenge":
            self.dialogue_set_mood(
                actor, kind, "thoughtful", "the difficult question you asked", 1, 2
            )
        else:
            self.dialogue_set_mood(actor, kind, "hopeful", "having a clearer next step", 1, 2)
        line = self.dialogue_thread_line(actor, kind, thread)
        self.dialogue_finalize_thread_resolution(actor, kind, thread)
        return line, relationship

    def dialogue_handle_thread(
        self,
        actor: Dict[str, object],
        kind: str,
        thread: Dict[str, object],
        transcript: List[Dict[str, str]],
    ) -> bool:
        if not thread:
            return True
        if (
            str(thread.get("support_status", "")) == "completed"
            and int(thread.get("stage", 0) or 0) < 3
            and int(thread.get("last_discussed_day", 0) or 0) == self.dialogue_absolute_day()
        ):
            return self.dialogue_say(
                actor,
                "We completed one real step today. I need time to live with what it changed before we turn the next part into another task.",
                "ongoing matter", transcript,
            )
        quest_id = str(thread.get("quest_id", ""))
        quest = self.quest_record(quest_id) if quest_id and hasattr(self, "quest_record") else {}
        if quest and str(thread.get("support_status", "")) == "active":
            resolution, relationship = self.dialogue_resolve_story_support(actor, kind, thread)
            quest = self.quest_record(quest_id)
            if str(quest.get("status", "")) == "completed":
                if relationship:
                    if hasattr(self, "add_hud_activity"):
                        self.add_hud_activity(
                            f"Relationship with {self.dialogue_actor_name(actor)} {relationship:+}.", "social"
                        )
                return self.dialogue_say(actor, resolution, "shared undertaking", transcript)
            choice = self.dialogue_choose(actor, "The practical support is still underway.", "ongoing matter", [
                ("support", "Review the shared undertaking", "Restate the tracked physical objective."),
                ("back", "Leave it for now", "Keep the quest active in the Journal."),
            ], transcript)
        else:
            choice = self.dialogue_choose(actor, "How do you respond to the ongoing situation?", "ongoing matter", [
                ("listen", "Ask what changed", "Listen and help them organize the facts."),
                ("support", "Offer practical support", "Create a tracked physical undertaking instead of an immediate relationship reward."),
                ("challenge", "Ask the difficult question", "May help a blunt or skeptical speaker clarify the real problem."),
                ("back", "Leave it for now", "The situation remains available in a later conversation."),
            ], transcript)
        if choice == "back" or not choice:
            return True
        player_lines = {
            "listen": "What has changed since we last spoke about it?",
            "support": "I can help with the practical part, but the decision should remain yours.",
            "challenge": "What answer are you avoiding because it would require you to change something?",
        }
        if not self.dialogue_say(self.dialogue_player_speaker(), player_lines[choice], "you", transcript):
            return False
        if choice == "support":
            if quest and str(quest.get("status", "")) in {"active", "ready"}:
                line, _relationship = self.dialogue_resolve_story_support(actor, kind, thread)
                return self.dialogue_say(actor, line, "shared undertaking", transcript)
            quest = self.dialogue_begin_story_support(actor, kind, thread)
            objective = self.quest_current_objective(quest)
            return self.dialogue_say(
                actor,
                f"Then let's make it specific: {objective.get('description', 'continue the work we discussed')} Come back when you're done.",
                "shared undertaking", transcript,
            )
        line, relationship = self.dialogue_advance_thread(actor, kind, thread, choice)
        if relationship:
            if hasattr(self, "add_hud_activity"):
                self.add_hud_activity(
                    f"Relationship with {self.dialogue_actor_name(actor)} {relationship:+}.", "social"
                )
        return self.dialogue_say(actor, line, "ongoing matter", transcript)

    def dialogue_invitation_relationship(
        self, actor: Dict[str, object], kind: str
    ) -> int:
        actor_id = str(actor.get("id", ""))
        if (
            kind in {"authored", "spouse", "procedural"}
            or self.dialogue_is_persistent_world_actor(actor, kind)
        ) and actor_id and hasattr(self, "town_npc_relationship"):
            return int(self.town_npc_relationship(actor_id))
        if kind == "child":
            return int(actor.get("affection", 0) or 0)
        return int(actor.get("relationship", actor.get("bond", 0)) or 0)

    def dialogue_invitation_activity_label(self, actor: Dict[str, object]) -> str:
        role = self.dialogue_actor_role(actor).lower()
        if any(word in role for word in ("fisher", "sailor", "ferry")):
            return "a fishing afternoon"
        if any(word in role for word in ("librarian", "scholar", "researcher")):
            return "a quiet visit and time to compare notes"
        if any(word in role for word in ("ranger", "hunter", "researcher", "botanist")):
            return "a walk somewhere worth observing"
        if any(word in role for word in ("innkeeper", "chef", "musician")):
            return "an evening away from our ordinary work"
        if any(word in role for word in ("miner", "blacksmith", "carpenter", "mechanic")):
            return "some unhurried time after the day's work"
        return "some time together outside our usual routine"

    def dialogue_prepare_npc_invitation(
        self, actor: Dict[str, object], kind: str, force: bool = False
    ) -> Dict[str, object]:
        slot = self.dialogue_social_slot(actor, kind)
        existing = slot.get("invitation", {})
        if isinstance(existing, dict) and str(existing.get("status", "")) == "pending":
            return existing
        actor_id = str(actor.get("id", "") or "")
        if not actor_id or (
            kind not in {"authored", "procedural", "spouse", "companion"}
            and not self.dialogue_is_persistent_world_actor(actor, kind)
        ):
            return {}
        relationship = self.dialogue_invitation_relationship(actor, kind)
        spouse = actor_id == str(getattr(self.state, "spouse_npc_id", "") or "")
        if relationship < (10 if spouse else 40):
            return {}
        if hasattr(self, "open_planned_events_for_actor") and self.open_planned_events_for_actor(
            actor_id, ("relationship_date", "social_outing", "social_gathering")
        ):
            return {}
        if kind == "authored" and hasattr(self, "town_npc_dialogue_count") and self.town_npc_dialogue_count(actor_id) < 3:
            return {}
        today = self.dialogue_absolute_day()
        last_day = int(slot.get("last_invitation_day", -9999) or -9999)
        if not force and today - last_day < 7:
            return {}
        week = today // 7
        if not force and _stable_index(f"npc-invitation:{week}:{actor_id}", 4) != 0:
            return {}

        current_destination = self.quest_capture_current_destination()
        current_destination["label"] = "where we spoke"
        venue_rows: List[Tuple[str, Dict[str, object]]] = [("where we spoke", current_destination)]
        for place in self.dialogue_known_places(actor, kind):
            destination = self.quest_destination_for_known_place(place)
            if destination:
                venue_rows.append((str(place.get("name", "a place I know")), dict(destination)))
        role = self.dialogue_actor_role(actor).lower()
        role_preferences = {
            "fisher": ("pond", "dock", "coast", "water"),
            "librarian": ("library",), "scholar": ("library", "museum"),
            "innkeeper": ("inn", "tavern"), "musician": ("inn", "tavern", "green"),
            "ranger": ("wilderness", "station", "trail"), "researcher": ("wilderness", "worksite", "field"),
            "gardener": ("garden", "farm", "green"), "chef": ("inn", "market", "farm"),
        }
        preferred_words = next(
            (words for role_word, words in role_preferences.items() if role_word in role), ()
        )
        preferred = [row for row in venue_rows if any(word in row[0].lower() for word in preferred_words)]
        pool = preferred or venue_rows
        venue_name, destination = pool[_stable_index(f"invitation-venue:{week}:{actor_id}", len(pool))]
        romantic = bool(
            actor_id == str(getattr(self.state, "spouse_npc_id", "") or "")
            or actor_id in set(getattr(self.state, "dating_npc_ids", []) or [])
        )
        due_in = 1 + _stable_index(f"invitation-day:{week}:{actor_id}", 2)
        due_hour = 18 if romantic or any(word in role for word in ("innkeeper", "musician", "chef")) else 14
        invitation = {
            "id": f"npc_invitation:{actor_id}:{today}",
            "status": "pending", "created_day": today,
            "kind": "relationship_date" if romantic else "social_outing",
            "romantic": romantic, "activity": self.dialogue_invitation_activity_label(actor),
            "venue_name": venue_name, "destination": dict(destination),
            "due_day": today + due_in, "due_hour": due_hour,
        }
        slot["invitation"] = invitation
        slot["last_invitation_day"] = today
        return invitation

    def dialogue_invitation_summary(self, invitation: Dict[str, object]) -> str:
        remaining = max(0, int(invitation.get("due_day", self.dialogue_absolute_day())) - self.dialogue_absolute_day())
        when = "tomorrow" if remaining == 1 else f"in {remaining} days" if remaining else "today"
        return (
            f"{invitation.get('activity', 'some time together')} at "
            f"{invitation.get('venue_name', 'the suggested place')} {when} around "
            f"{int(invitation.get('due_hour', 14)):02d}:00"
        )

    def dialogue_accept_npc_invitation(
        self, actor: Dict[str, object], kind: str, invitation: Dict[str, object]
    ) -> Dict[str, object]:
        actor_id = str(actor.get("id", ""))
        actor_name = self.dialogue_actor_name(actor)
        event_kind = str(invitation.get("kind", "social_outing"))
        due_day, due_hour = int(invitation.get("due_day", self.dialogue_absolute_day() + 1)), int(invitation.get("due_hour", 14))
        event_id = f"{event_kind}:{actor_id}:invited:{due_day}:{due_hour}"
        title = f"{'Date' if event_kind == 'relationship_date' else 'Outing'} with {actor_name}"
        destination = dict(invitation.get("destination", {}) or {})
        event = self.schedule_planned_event({
            "id": event_id, "title": title, "kind": event_kind,
            "status": "planned", "auto_activate": True, "requires_attendance": True,
            "romantic": bool(invitation.get("romantic", False)), "initiated_by_npc": True,
            "due_day": due_day, "due_hour": due_hour,
            "expires_at_minute": due_day * 1440 + (due_hour + 8) * 60,
            "destination": destination,
            "participants": [{
                "actor_id": actor_id, "name": actor_name,
                "role": str(actor.get("role", "Resident")), "kind": kind,
                "mode": "meet", "purpose": str(invitation.get("activity", "the invitation")),
                "destination": destination,
            }],
        })
        slot = self.dialogue_social_slot(actor, kind)
        slot["meetings"] = (list(slot.get("meetings", [])) + [{
            "day": due_day, "made_day": self.dialogue_absolute_day(),
            "purpose": str(invitation.get("activity", "spend time together")),
            "event_id": event_id, "destination": destination, "completed": False,
        }])[-6:]
        invitation["status"] = "accepted"
        invitation["event_id"] = event_id
        slot["invitation_history"] = (list(slot.get("invitation_history", [])) + [dict(invitation)])[-8:]
        if hasattr(self, "autosave_with_message"):
            self.autosave_with_message(f"Accepted {actor_name}'s invitation.")
        return event

    def dialogue_handle_npc_invitation(
        self, actor: Dict[str, object], kind: str, invitation: Dict[str, object], transcript: List[Dict[str, str]]
    ) -> bool:
        while str(invitation.get("status", "")) == "pending":
            choice = self.dialogue_choose(actor, f"They proposed {self.dialogue_invitation_summary(invitation)}. How do you answer?", "invitation", [
                ("accept", "Accept the invitation", "Put the appointment in the Journal and calendar."),
                ("time", "Suggest another time", "Keep the activity and place, but choose another day and hour."),
                ("place", "Suggest another place", "Keep the proposed time, but choose somewhere else you both know."),
                ("decline", "Decline honestly", "Refuse without an arbitrary relationship penalty."),
                ("later", "Answer later", "Leave the invitation pending."),
            ], transcript)
            if choice == "accept":
                event = self.dialogue_accept_npc_invitation(actor, kind, invitation)
                return self.dialogue_say(
                    actor,
                    f"Good. I will meet you at {event['destination'].get('label', invitation.get('venue_name', 'the agreed place'))} around {int(event['due_hour']):02d}:00. I am glad the answer was yours to give.",
                    "invitation accepted", transcript,
                )
            if choice == "time":
                day_choice = self.dialogue_choose(actor, "Which day would work better?", "reschedule", [
                    ("1", "Tomorrow", "Meet on the next day."), ("2", "In two days", "Meet after one free day."),
                    ("3", "In three days", "Meet farther ahead."), ("back", "Keep the proposal", "Do not change it."),
                ], transcript)
                if day_choice not in {"1", "2", "3"}:
                    continue
                hour_choice = self.dialogue_choose(actor, "What time?", "reschedule", [
                    ("10", "Morning, 10:00", "A morning appointment."), ("14", "Afternoon, 14:00", "An afternoon appointment."),
                    ("18", "Evening, 18:00", "An evening appointment."), ("back", "Keep the proposal", "Do not change it."),
                ], transcript)
                if hour_choice in {"10", "14", "18"}:
                    invitation["due_day"] = self.dialogue_absolute_day() + int(day_choice)
                    invitation["due_hour"] = int(hour_choice)
                    self.dialogue_say(actor, "That time works for me. Thank you for suggesting it directly.", "rescheduled", transcript)
                continue
            if choice == "place":
                current = self.quest_capture_current_destination()
                current["label"] = "where we are now"
                venues: List[Tuple[str, str, Dict[str, object]]] = [("__HERE__", "Meet here", current)]
                for place in self.dialogue_known_places(actor, kind)[:12]:
                    destination = self.quest_destination_for_known_place(place)
                    if destination:
                        venues.append((str(place.get("id", place.get("name", ""))), str(place.get("name", "Known place")), dict(destination)))
                options: List[DialogueOption] = [
                    (place_id, label, str(destination.get("label", destination.get("location", "Known place"))))
                    for place_id, label, destination in venues
                ] + [("back", "Keep the proposal", "Do not change the place.")]
                place_choice = self.dialogue_choose(actor, "Where would you rather meet?", "reschedule", options, transcript)
                selected = next((row for row in venues if row[0] == place_choice), None)
                if selected:
                    invitation["venue_name"] = selected[1]
                    invitation["destination"] = dict(selected[2])
                    self.dialogue_say(actor, "That place makes sense. I can adjust my route.", "rescheduled", transcript)
                continue
            if choice == "decline":
                invitation["status"] = "declined"
                invitation["resolved_day"] = self.dialogue_absolute_day()
                slot = self.dialogue_social_slot(actor, kind)
                slot["invitation_history"] = (list(slot.get("invitation_history", [])) + [dict(invitation)])[-8:]
                return self.dialogue_say(actor, "All right. Maybe another time.", "invitation declined", transcript)
            return False
        return True

    def dialogue_prepare_initiation(
        self, actor: Dict[str, object], kind: str
    ) -> Dict[str, object]:
        slot = self.dialogue_social_slot(actor, kind)
        current = slot.get("initiation", {})
        if isinstance(current, dict) and current and not current.get("acknowledged"):
            if str(current.get("reason", "")) != "witnessed_event":
                return current
            source_event = next(
                (
                    row for row in reversed(slot.get("witnessed_events", []) or [])
                    if isinstance(row, dict)
                    and str(row.get("id", "")) == str(current.get("source_event_id", ""))
                ),
                None,
            )
            action = self.world_dialogue_safe_event_action(source_event or {})
            if action:
                if int(current.get("observation_version", 0) or 0) < 2:
                    current["text"] = self.dialogue_witness_observation_line(
                        actor, kind, source_event or {}, "initiation"
                    )
                    current["observation_version"] = 2
                return current
            current["acknowledged"] = True
        reason = ""
        text = ""
        unseen = next(
            (
                row for row in reversed(slot["witnessed_events"])
                if not bool(row.get("conversation_acknowledged", False))
                and str(row.get("category", "")) == "combat"
                and bool(self.world_dialogue_safe_event_action(row))
            ),
            None,
        )
        thread = self.dialogue_current_thread(actor, kind, create=False)
        due_meeting = next(
            (
                row for row in slot.get("meetings", []) or []
                if not bool(row.get("completed", False))
                and int(row.get("day", 10 ** 9) or 10 ** 9) <= self.dialogue_absolute_day()
            ),
            None,
        )
        if due_meeting:
            reason = "meeting"
            text = "We planned to continue this today. I kept room in my schedule, so let us pick up where we left off."
        elif unseen:
            reason = "witnessed_event"
            text = self.dialogue_witness_observation_line(
                actor, kind, unseen, "initiation"
            )
        elif thread and int(thread.get("updated_day", 0) or 0) < self.dialogue_absolute_day():
            reason = "ongoing_thread"
            text = f"I have an update about {str(thread.get('title', 'what we discussed')).lower()}."
        else:
            aftermath = self.dialogue_story_aftermath(actor, kind)
            if (
                aftermath
                and not bool(aftermath.get("acknowledged", False))
                and int(aftermath.get("available_day", 10 ** 9) or 10 ** 9) <= self.dialogue_absolute_day()
            ):
                reason = "story_aftermath"
                text = str(aftermath.get("follow_up", aftermath.get("summary", "I wanted to tell you what changed.")))
            else:
                invitation = self.dialogue_prepare_npc_invitation(actor, kind)
                if invitation:
                    reason = "invitation"
                    text = f"I wanted to ask whether you would join me for {self.dialogue_invitation_summary(invitation)}."
        if not reason:
            return {}
        current = {
            "reason": reason,
            "text": text,
            "created_day": self.dialogue_absolute_day(),
            "called_out_day": 0,
            "acknowledged": False,
            "source_event_id": str(unseen.get("id", "")) if reason == "witnessed_event" and unseen else "",
            "observation_version": 2 if reason == "witnessed_event" else 0,
        }
        slot["initiation"] = current
        return current

    def dialogue_initiation_callout(
        self, actor: Dict[str, object], kind: str
    ) -> str:
        initiation = self.dialogue_prepare_initiation(actor, kind)
        if not initiation or int(initiation.get("called_out_day", 0) or 0) == self.dialogue_absolute_day():
            return ""
        initiation["called_out_day"] = self.dialogue_absolute_day()
        return f"{getattr(self.state, 'player_name', 'Neighbor')}, could we talk when you have a moment? {initiation.get('text', '')}"

    def dialogue_accept_initiation(
        self, actor: Dict[str, object], kind: str
    ) -> str:
        slot = self.dialogue_social_slot(actor, kind)
        initiation = slot.get("initiation", {})
        if not isinstance(initiation, dict) or not initiation or initiation.get("acknowledged"):
            return ""
        initiation["acknowledged"] = True
        if str(initiation.get("reason", "")) == "witnessed_event":
            source_id = str(initiation.get("source_event_id", ""))
            for event in slot.get("witnessed_events", []) or []:
                if isinstance(event, dict) and str(event.get("id", "")) == source_id:
                    event["conversation_acknowledged"] = True
                    event["ambient_acknowledged"] = True
                    break
        if str(initiation.get("reason", "")) == "story_aftermath":
            aftermath = slot.get("story_aftermath", {})
            if isinstance(aftermath, dict):
                aftermath["acknowledged"] = True
                aftermath["acknowledged_day"] = self.dialogue_absolute_day()
        if str(initiation.get("reason", "")) == "meeting":
            for meeting in slot.get("meetings", []) or []:
                if (
                    isinstance(meeting, dict)
                    and not meeting.get("completed")
                    and int(meeting.get("day", 10 ** 9) or 10 ** 9) <= self.dialogue_absolute_day()
                ):
                    meeting["completed"] = True
                    meeting["completed_day"] = self.dialogue_absolute_day()
                    break
        return str(initiation.get("text", ""))

    # ------------------------------------------------------------------
    # Dialogue in the moving world

    def world_dialogue_actor_kind(self, actor: Dict[str, object]) -> str:
        """Identify the dialogue family used by a visible world actor."""
        explicit = str(actor.get("_dialogue_kind") or actor.get("kind") or "")
        if explicit in {
            "authored", "procedural", "traveler", "regional_visitor",
            "companion", "spouse", "child", "caretaker",
        }:
            return explicit
        actor_id = str(actor.get("id", "") or "")
        if actor.get("procedural_resident") or actor.get("procedural_caravan"):
            return "procedural"
        if actor.get("regional_visitor"):
            return "regional_visitor"
        if actor.get("recurring") or actor.get("regional_circulation"):
            return "traveler"
        if actor_id and actor_id == str(getattr(self.state, "spouse_npc_id", "") or ""):
            return "spouse"
        if actor_id.startswith("child:") or actor_id.startswith("household_child:"):
            return "child"
        return "authored"

    def world_dialogue_nearby_actors(
        self, radius: int = 7
    ) -> List[Dict[str, object]]:
        """Return real actors close enough for the player to see or overhear."""
        if not hasattr(self, "state") or getattr(self.state, "active_scene_id", ""):
            return []
        try:
            player_x = int(self.state.player_x)
            player_y = int(self.state.player_y)
        except Exception:
            return []
        radius = max(1, min(12, int(radius)))
        npc_lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        if hasattr(self, "town_npc_position_lookup"):
            try:
                npc_lookup = dict(self.town_npc_position_lookup() or {})
            except Exception:
                npc_lookup = {}
        follower_lookup = (
            dict(self.travel_follower_position_lookup() or {})
            if hasattr(self, "travel_follower_position_lookup")
            else {}
        )
        traveler_lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        temporary_lookup = (
            dict(self.temporary_participant_position_lookup() or {})
            if hasattr(self, "temporary_participant_position_lookup")
            else {}
        )
        if hasattr(self, "on_wilderness") and self.on_wilderness():
            try:
                traveler_cache = getattr(self, "_wilderness_travelers", {}) or {}
                cache_key = (
                    self.wilderness_traveler_cache_key(
                        int(self.state.wilderness_chunk_x),
                        int(self.state.wilderness_chunk_y),
                    )
                    if hasattr(self, "wilderness_traveler_cache_key")
                    else ""
                )
                overridden_ids = (
                    set(self.temporary_participant_actor_ids())
                    if hasattr(self, "temporary_participant_actor_ids")
                    else set()
                )
                for traveler in traveler_cache.get(cache_key, []) or []:
                    if str(traveler.get("id", "")) in overridden_ids:
                        continue
                    position = (int(traveler.get("x", -1)), int(traveler.get("y", -1)))
                    if position[0] >= 0 and position[1] >= 0:
                        traveler_lookup[position] = traveler
            except Exception:
                traveler_lookup = {}

        nearby: List[Dict[str, object]] = []
        seen: set[str] = set()

        def add_actor(actor: Dict[str, object], kind: str, x: int, y: int) -> None:
            actor_id = str(actor.get("id") or actor.get("name") or f"actor:{x}:{y}")
            social_key = f"{kind}:{actor_id}"
            if social_key in seen:
                return
            seen.add(social_key)
            nearby.append({
                "actor": actor,
                "kind": kind,
                "x": int(x),
                "y": int(y),
                "distance": max(abs(int(x) - player_x), abs(int(y) - player_y)),
            })

        for y in range(player_y - radius, player_y + radius + 1):
            for x in range(player_x - radius, player_x + radius + 1):
                if hasattr(self, "in_active_bounds") and not self.in_active_bounds(x, y):
                    continue
                key = (x, y)
                if getattr(self.state, "location", "") == "Wilderness" and hasattr(self, "home_world_source_at"):
                    home_kind, source_x, source_y = self.home_world_source_at(x, y)
                    if home_kind in {"town", "farm"}:
                        key = (int(source_x), int(source_y))
                actor = npc_lookup.get(key)
                if isinstance(actor, dict):
                    add_actor(actor, self.world_dialogue_actor_kind(actor), x, y)
                traveler = traveler_lookup.get((x, y))
                if isinstance(traveler, dict):
                    add_actor(traveler, "traveler", x, y)
                participant = temporary_lookup.get((x, y))
                if isinstance(participant, dict) and hasattr(self, "temporary_participant_actor"):
                    participant_actor = self.temporary_participant_actor(participant)
                    add_actor(
                        participant_actor,
                        str(participant.get("kind", self.world_dialogue_actor_kind(participant_actor))),
                        x, y,
                    )
                follower_id = follower_lookup.get((x, y))
                if follower_id and hasattr(self, "travel_follower_data"):
                    follower = dict(self.travel_follower_data(str(follower_id)) or {})
                    if follower:
                        record = (
                            self.travel_follower_record(str(follower_id))
                            if hasattr(self, "travel_follower_record")
                            else {}
                        )
                        follower["activity"] = str(
                            record.get("activity", follower.get("activity", "traveling with you"))
                        )
                        if hasattr(self, "travel_follower_personality_label"):
                            follower["personality"] = self.travel_follower_personality_label(str(follower_id))
                        add_actor(follower, "companion", x, y)
        nearby.sort(key=lambda row: (
            int(row.get("distance", 99)),
            str(row.get("actor", {}).get("id", row.get("actor", {}).get("name", ""))),
        ))
        return nearby

    def world_dialogue_location_label(self) -> str:
        if getattr(self.state, "location", "") == "Wilderness" and hasattr(self, "home_world_source_at"):
            kind, _x, _y = self.home_world_source_at(self.state.player_x, self.state.player_y)
            if kind == "town":
                return "the starting town"
            if kind == "farm":
                return "the farm"
            if kind == "mine":
                return "the mine approach"
            if hasattr(self, "current_procedural_town_plan"):
                plan = self.current_procedural_town_plan() or {}
                if plan:
                    return str(plan.get("name", "this settlement"))
            return "this stretch of wilderness"
        raw_location = str(getattr(self.state, "location", "this place") or "this place")
        if hasattr(self, "location_label"):
            try:
                display_location = str(self.location_label() or raw_location)
            except (AttributeError, TypeError, ValueError):
                display_location = raw_location
        else:
            display_location = raw_location
        return self.world_dialogue_safe_location_label(display_location, raw_location)

    def world_dialogue_safe_location_label(
        self, value: object, raw_location: object = ""
    ) -> str:
        """Turn runtime location keys into language an NPC can plausibly use."""
        text = " ".join(strip_ansi(str(value or "")).split()).strip(" .")
        raw = str(raw_location or text).strip()
        labels = {
            "Farm": "the farm",
            "Town": "Elsewhere",
            "Mine": "the mine",
            "Wilderness": "the wilderness",
            "WildernessOverworld": "the wilderness map",
            "WildernessCave": "a wilderness cave",
            "WildernessDungeon": "the dungeon",
            "WildernessOutpost": "the outpost",
            "WildernessStructure": "a wilderness building",
            "RuralInfrastructureInterior": "a roadside building",
            "RoadsideAuxInterior": "a roadside stop",
            "CorridorInfrastructureInterior": "a roadside building",
            "RouteHamletInterior": "a hamlet building",
            "RouteLeisureInterior": "a roadside gathering place",
            "RouteHeritageInterior": "an old roadside building",
            "ProceduralSettlementInterior": "a settlement building",
            "HouseInterior": "the farmhouse",
            "GeneralStoreInterior": "the general store",
            "BlacksmithInterior": "the blacksmith",
            "LibraryInterior": "the library",
            "MayorHouseInterior": "the mayor's house",
            "InnInterior": "the inn",
            "FurnitureStoreInterior": "the furniture store",
            "CarpenterStoreInterior": "the carpenter's shop",
            "AnimalStoreInterior": "the animal store",
            "ClinicInterior": "the clinic",
            "TownHallInterior": "Town Hall",
            "MarketRowInterior": "Market Row",
            "MuseumInterior": "the museum",
            "TownResidenceInterior": "a town residence",
        }
        if raw in labels:
            return labels[raw]
        if text in labels:
            return labels[text]
        if raw.startswith("TownResidence:"):
            return "a town residence"
        if re.search(r"(?i)dungeon[ _-]*room\d*", raw) or re.search(
            r"(?i)dungeon[ _-]*room\d*", text
        ):
            return "the dungeon"
        if re.fullmatch(r"[A-Za-z]+(?:Interior|Location|Room)\d*", text):
            return "a nearby building"
        if re.fullmatch(r"Wilderness\s*\([^)]*\)", text):
            return "the wilderness"
        return text or "this place"

    def world_dialogue_event_action(self, message: object) -> str:
        """Turn a gameplay result into a clause an eyewitness can say naturally."""
        text = " ".join(strip_ansi(str(message or "")).replace("\r", " ").split()).strip(" .")
        if not text:
            return ""
        if text.lower().startswith("you "):
            text = text[4:5].upper() + text[5:]
        text = re.sub(r"\s*\([^)]*\)\s*", " ", text).strip()
        text = text.split(" | ", 1)[0].strip()
        verb_forms = (
            ("Picked up", "pick up"), ("Harvested", "harvest"),
            ("Collected", "collect"), ("Recovered", "recover"),
            ("Crafted", "craft"), ("Built", "build"),
            ("Repaired", "repair"), ("Planted", "plant"),
            ("Watered", "water"), ("Cleared", "clear"),
            ("Defeated", "defeat"), ("Discovered", "discover"),
            ("Bought", "buy"), ("Sold", "sell"), ("Earned", "earn"),
            ("Found", "find"), ("Rescued", "rescue"),
            ("Extinguished", "extinguish"), ("Froze", "freeze"),
            ("Completed", "complete"), ("Opened", "open"),
            ("Took", "take"), ("Cast", "cast"), ("Helped", "help"),
        )
        folded = text.casefold()
        for past, present in verb_forms:
            if folded == past.casefold():
                return present
            prefix = past.casefold() + " "
            if folded.startswith(prefix):
                return f"{present} {text[len(past):].lstrip()}"[:180]
        return ""

    def world_dialogue_safe_event_action(self, event: Dict[str, object]) -> str:
        """Keep only substantial actions that sound natural when repeated aloud."""
        category = str(event.get("category", "general") or "general").casefold()
        raw_action = " ".join(strip_ansi(str(event.get("action", "") or "")).split()).strip(" .")
        action = raw_action or self.world_dialogue_event_action(event.get("text", ""))
        if action and not any(action.casefold().startswith(prefix + " ") or action.casefold() == prefix for prefix in (
            "defeat", "rescue", "extinguish", "clear", "repair", "build", "craft",
            "complete", "discover", "help",
        )):
            reparsed = self.world_dialogue_event_action(action)
            action = reparsed
        folded = action.casefold()
        allowed = {
            "combat": ("defeat", "rescue", "extinguish", "clear"),
            "gain": ("repair", "build", "craft", "complete", "discover", "rescue", "help"),
            "travel": ("discover",),
            "social": ("rescue", "help"),
            "general": ("repair", "build", "craft", "complete", "discover", "rescue", "extinguish", "help"),
        }.get(category, ())
        if not action or not any(folded == prefix or folded.startswith(prefix + " ") for prefix in allowed):
            return ""
        if re.search(r"(?i)DungeonRoom\d*|[A-Za-z]+Interior\d*", action):
            return ""
        if any(token in action for token in ("(", ")", "[", "]", " +", " =")):
            return ""
        return action[:140]

    def world_dialogue_event_place_clause(self, event: Dict[str, object]) -> str:
        place = self.world_dialogue_safe_location_label(event.get("location", "nearby"))
        if place in {"", "nearby", "this place"}:
            return ""
        preposition = (
            "in"
            if place in {"the wilderness", "the dungeon"}
            or place.startswith("the region around ")
            else "at"
        )
        return f" {preposition} {place}"

    def world_dialogue_event_knowledge_summary(self, event: Dict[str, object]) -> str:
        action = self.world_dialogue_safe_event_action(event)
        if not action:
            return ""
        past_forms = {
            "defeat": "defeated", "rescue": "rescued", "extinguish": "extinguished",
            "clear": "cleared", "repair": "repaired", "build": "built",
            "craft": "crafted", "complete": "completed", "discover": "discovered",
            "help": "helped",
        }
        verb, _, rest = action.partition(" ")
        past = past_forms.get(verb.casefold(), "")
        if not past:
            return ""
        detail = f" {rest}" if rest else ""
        return f"You {past}{detail}{self.world_dialogue_event_place_clause(event)}."

    def world_dialogue_event_is_worth_witnessing(
        self, message: object, category: str = ""
    ) -> bool:
        text = " ".join(strip_ansi(str(message or "")).split())
        if not text or len(text) < 5:
            return False
        resolved = str(category or "")
        if not resolved and hasattr(self, "hud_activity_category"):
            resolved = str(self.hud_activity_category(text))
        if resolved in {"dialogue", "warning"}:
            return False
        event = {
            "text": text,
            "action": self.world_dialogue_event_action(text),
            "category": resolved or "general",
        }
        return bool(self.world_dialogue_safe_event_action(event))

    def world_dialogue_record_player_event(
        self, message: object, category: str = ""
    ) -> int:
        """Let nearby people remember a concrete player action for later dialogue."""
        if not self.world_dialogue_event_is_worth_witnessing(message, category):
            return 0
        text = " ".join(strip_ansi(str(message or "")).replace("\r", " ").split())[:220]
        resolved = str(category or "")
        if not resolved and hasattr(self, "hud_activity_category"):
            resolved = str(self.hud_activity_category(text))
        event_seed = (
            f"{self.dialogue_day_key()}:{getattr(self.state, 'hour', 0)}:"
            f"{getattr(self.state, 'minute', 0)}:{self.world_dialogue_location_label()}:{text}"
        )
        event_id = hashlib.sha256(event_seed.encode("utf-8")).hexdigest()[:16]
        event = {
            "id": event_id,
            "text": text,
            "action": self.world_dialogue_event_action(text),
            "category": resolved or "general",
            "day": self.dialogue_day_key(),
            "time": f"{int(getattr(self.state, 'hour', 0)):02d}:{int(getattr(self.state, 'minute', 0)):02d}",
            "location": self.world_dialogue_location_label(),
            "ambient_acknowledged": False,
            "conversation_acknowledged": False,
        }
        recorded = 0
        for row in self.world_dialogue_nearby_actors(radius=7):
            actor = row.get("actor", {})
            kind = str(row.get("kind", "authored"))
            if not isinstance(actor, dict):
                continue
            slot = self.dialogue_social_slot(actor, kind)
            events = slot.setdefault("witnessed_events", [])
            if any(str(item.get("id", "")) == event_id for item in events if isinstance(item, dict)):
                continue
            events.append(dict(event))
            slot["witnessed_events"] = events[-8:]
            knowledge_text = self.world_dialogue_event_knowledge_summary(event)
            self.dialogue_add_knowledge(
                actor,
                kind,
                knowledge_text,
                subject=resolved or "local event",
                source_name="personal observation",
                source_kind="firsthand",
                confidence=100,
                knowledge_id=event_id,
            )
            if resolved == "combat":
                demeanor = self.dialogue_demeanor(actor, kind)
                self.dialogue_set_mood(
                    actor,
                    kind,
                    "suspicious" if demeanor in {"skeptical", "wary", "hostile"} else "worried",
                    "the violence I witnessed nearby",
                    2,
                    2,
                )
            elif resolved in {"gain", "travel"}:
                self.dialogue_set_mood(
                    actor, kind, "curious", "what I saw you accomplish nearby", 1, 2
                )
            recorded += 1
        return recorded

    def dialogue_witness_callback(
        self, actor: Dict[str, object], kind: str, channel: str = "conversation"
    ) -> str:
        slot = self.dialogue_social_slot(actor, kind)
        flag = "ambient_acknowledged" if channel == "ambient" else "conversation_acknowledged"
        event = None
        for row in reversed(slot.get("witnessed_events", []) or []):
            if not isinstance(row, dict) or bool(row.get(flag, False)):
                continue
            if not self.world_dialogue_safe_event_action(row):
                row["ambient_acknowledged"] = True
                row["conversation_acknowledged"] = True
                continue
            event = row
            break
        if not event:
            return ""
        event[flag] = True
        return self.dialogue_witness_observation_line(actor, kind, event, channel)

    def dialogue_fresh_world_line(
        self,
        actor: Dict[str, object],
        kind: str,
        history_field: str,
        candidates: Sequence[Tuple[str, str]],
        seed: str,
        history_limit: int = 10,
    ) -> str:
        """Pick a deterministic line while avoiding recently used structures."""
        usable = [
            (str(line_id), " ".join(str(line or "").split()))
            for line_id, line in candidates
            if str(line_id or "") and str(line or "").strip()
        ]
        if not usable:
            return ""
        slot = self.dialogue_social_slot(actor, kind)
        recent = [str(value) for value in slot.get(history_field, []) or [] if str(value or "")]
        recent_window = (
            set(recent[-min(len(usable) - 1, max(1, history_limit)):])
            if len(usable) > 1 else set()
        )
        available = [row for row in usable if row[0] not in recent_window]
        if not available:
            available = [row for row in usable if row[0] != (recent[-1] if recent else "")] or usable
        choice = available[_stable_index(f"{seed}:{len(recent)}", len(available))]
        slot[history_field] = (recent + [choice[0]])[-max(2, int(history_limit)):]
        return choice[1]

    def world_dialogue_event_past_clause(self, event: Dict[str, object]) -> str:
        action = self.world_dialogue_safe_event_action(event)
        if not action:
            return ""
        verb, _, detail = action.partition(" ")
        past = {
            "defeat": "defeated", "rescue": "rescued", "extinguish": "extinguished",
            "clear": "cleared", "repair": "repaired", "build": "built",
            "craft": "crafted", "complete": "completed", "discover": "discovered",
            "help": "helped",
        }.get(verb.casefold(), "")
        if not past:
            return ""
        return f"{past}{f' {detail}' if detail else ''}{self.world_dialogue_event_place_clause(event)}"

    def dialogue_witness_observation_line(
        self,
        actor: Dict[str, object],
        kind: str,
        event: Dict[str, object],
        channel: str = "conversation",
    ) -> str:
        """Describe a witnessed action through event, relationship, role, and voice."""
        action = self.world_dialogue_safe_event_action(event)
        past_clause = self.world_dialogue_event_past_clause(event)
        if not action or not past_clause:
            return ""
        verb, _, _detail = action.partition(" ")
        place = self.world_dialogue_event_place_clause(event)
        category = str(event.get("category", "general") or "general").casefold()
        event_id = str(event.get("id", "") or f"{category}:{action}:{place}")
        already_mentioned = bool(event.get("ambient_acknowledged", False)) and channel != "ambient"

        pools: Dict[str, Tuple[str, ...]] = {
            "defeat": (
                f"That fight changed in an instant. You {past_clause} before it could get worse.",
                f"I had a clear view when you {past_clause}. You kept your footing.",
                f"For a moment, I wasn't sure how that fight would end. Then you {past_clause}.",
                f"You {past_clause}. The silence afterward felt different.",
                f"Watching you {action}{place} told me a great deal about how you handle danger.",
                f"I was close enough to see the whole fight. You {past_clause} without backing down.",
            ),
            "rescue": (
                f"You {past_clause}. They looked as though they had run out of options.",
                f"I watched you {action}{place}. You didn't leave someone else to face it alone.",
                f"What stayed with me was how quickly you moved to help. You {past_clause}.",
                f"You {past_clause}, and that mattered more than anything anyone could have said afterward.",
                f"I thought help might come too late. Then you {past_clause}.",
                f"The moment you {past_clause}, everyone nearby could finally breathe again.",
            ),
            "extinguish": (
                f"You {past_clause}. Another minute and that fire might have spread.",
                f"I could feel the heat from where I stood when you {past_clause}.",
                f"You moved before anyone else did and {past_clause}.",
                f"The smoke was getting worse until you {past_clause}.",
                f"I watched you {action}{place}. That could have ended very differently.",
                f"You {past_clause}; the whole place felt safer once the flames were gone.",
            ),
            "clear": (
                f"You {past_clause}. The route feels safer now.",
                f"I saw what the place looked like before you {past_clause}. The difference is hard to miss.",
                f"You stayed with the danger until you {past_clause}.",
                f"People will be able to use that ground differently because you {past_clause}.",
                f"I watched you {action}{place}. It wasn't easy work, but it was necessary.",
                f"The area finally went quiet after you {past_clause}.",
            ),
            "repair": (
                f"I watched you {action}{place}. You stayed with the problem until it held.",
                f"You {past_clause}. That should make the route easier for everyone behind us.",
                f"The damage looked worse before you {past_clause}.",
                f"You took the time to {action}{place} instead of walking past it.",
                f"I wasn't sure that could be put right in the field, but you {past_clause}.",
                f"That repair will outlast the moment. You {past_clause} when it mattered.",
            ),
            "build": (
                f"You {past_clause}. It already changes how this place can be used.",
                f"I watched the shape come together while you {action}{place}.",
                f"There was nothing there before you {past_clause}. That's worth noticing.",
                f"You {past_clause}, and now other people can build their plans around it.",
                f"I saw how carefully you worked when you {past_clause}.",
                f"The place feels less temporary after you {past_clause}.",
            ),
            "craft": (
                f"You {past_clause}. The careful part was easy to miss unless someone was watching.",
                f"I saw you {action}{place}. You knew exactly where to slow down.",
                f"You made that look simpler than it was when you {past_clause}.",
                f"The materials didn't look promising until you {past_clause}.",
                f"I watched you {action}{place}; the result says more than a boast would.",
                f"You {past_clause}. I can see the work in the finished piece.",
            ),
            "complete": (
                f"You {past_clause}. It was good to see the work reach an actual end.",
                f"I watched the last part come together when you {past_clause}.",
                f"You kept returning to the work until you {past_clause}.",
                f"People had been waiting on that. You {past_clause} at the right time.",
                f"I wasn't certain the work would be finished today, but you {past_clause}.",
                f"The result is visible now that you {past_clause}.",
            ),
            "discover": (
                f"You {past_clause}. I doubt either of us will forget the first sight of it.",
                f"I was watching your face when you {past_clause}; that gave the moment away.",
                f"You noticed what the rest of us might have walked past and {past_clause}.",
                f"The route became more interesting the moment you {past_clause}.",
                f"I saw you {action}{place}. Now I'm wondering what else is nearby.",
                f"You {past_clause}, and suddenly the map felt incomplete again.",
            ),
            "help": (
                f"You {past_clause}. They won't forget that you stopped for them.",
                f"I watched you {action}{place} when it would have been easier to keep moving.",
                f"You made time to help and {past_clause}. That told me something useful about you.",
                f"They needed another pair of hands, and you {past_clause}.",
                f"You {past_clause}. The work went differently because you were there.",
                f"I noticed that you {past_clause} without waiting to be praised for it.",
            ),
        }
        base_lines = list(pools.get(verb.casefold(), ()))
        base_lines.extend((
            f"I was there when you {past_clause}.",
            f"You {past_clause}. I wanted you to know that someone noticed.",
        ))
        if already_mentioned:
            base_lines.extend((
                f"I've been thinking about it since I watched you {action}{place}.",
                f"About what happened earlier: you {past_clause}, and it has stayed with me.",
            ))
        base_candidates = [
            (f"observation:{verb}:{index}", line)
            for index, line in enumerate(base_lines)
        ]
        base = self.dialogue_fresh_world_line(
            actor, kind, "recent_observation_templates", base_candidates,
            f"{self.dialogue_day_key()}:{actor.get('id')}:{event_id}:{channel}:base", 12,
        )

        demeanor = self.dialogue_demeanor(actor, kind)
        relationship = self.dialogue_relationship_points(actor, kind)
        role = self.dialogue_actor_role(actor).casefold()
        traits = self.dialogue_personality_words(actor)
        reactions: List[Tuple[str, str]] = []
        if kind == "spouse":
            reactions.extend((
                ("spouse:care", "I'm proud of you, but I don't want courage to become carelessness."),
                ("spouse:together", "Next time, let me carry more of the weight with you."),
                ("spouse:home", "I'm glad we're going home together after seeing that through."),
            ))
        elif kind == "child":
            reactions.extend((
                ("child:honest", "It frightened me, but I was glad you knew what to do."),
                ("child:question", "Will you explain how you decided what to do first?"),
                ("child:memory", "I think I'm going to remember that for a long time."),
            ))
        elif kind == "companion":
            reactions.extend((
                ("companion:share", "We came through it together, even if you did the hardest part."),
                ("companion:next", "If something like that happens again, let me take some of the pressure."),
                ("companion:supplies", "We should check ourselves and our supplies before we move on."),
                ("companion:trust", "Seeing that up close makes me trust your judgment more."),
            ))
        if any(word in role for word in ("doctor", "nurse", "medic", "healer")) and category == "combat":
            reactions.append(("role:healer", "Let me check for injuries before we move on."))
        if any(word in role for word in ("ranger", "hunter", "scout", "sheriff", "guard")):
            reactions.append(("role:trail", "That should make this stretch of the route safer."))
        if any(word in role for word in ("carpenter", "builder", "mechanic", "blacksmith")) and verb in {"repair", "build", "craft"}:
            reactions.append(("role:maker", "The workmanship was sound; I was watching the parts most people miss."))
        if traits.intersection({"bold", "brave", "daring", "adventurous"}):
            reactions.append(("trait:bold", "That is the sort of moment that makes a journey worth remembering."))
        if traits.intersection({"cautious", "careful", "wary", "anxious"}):
            reactions.append(("trait:cautious", "I'd rather not depend on luck if we face that situation again."))
        if traits.intersection({"curious", "studious", "observant", "scholarly"}):
            reactions.append(("trait:curious", "I want to understand what you noticed before the rest of us did."))
        if traits.intersection({"practical", "organized", "steady", "reliable"}):
            reactions.append(("trait:practical", "Before we continue, we should decide what that changes for the route ahead."))
        demeanor_reactions = {
            "warm": (
                ("voice:warm:1", "You handled yourself well."),
                ("voice:warm:2", "I'm glad I was there to see how it really happened."),
                ("voice:warm:3", "You did some good there, and I hope you know it."),
            ),
            "professional": (
                ("voice:professional:1", "People working nearby will need to know what changed."),
                ("voice:professional:2", "I'll account for that when I plan the next part of my work."),
                ("voice:professional:3", "That had a practical effect beyond the two of us."),
            ),
            "skeptical": (
                ("voice:skeptical:1", "I'm still deciding what the moment says about you."),
                ("voice:skeptical:2", "One action doesn't answer every question, but it answered one."),
                ("voice:skeptical:3", "I trust what I witnessed more than anything people may claim later."),
            ),
            "blunt": (
                ("voice:blunt:1", "I prefer seeing what someone does to hearing what they claim."),
                ("voice:blunt:2", "It needed doing. You did it. That matters."),
                ("voice:blunt:3", "I'm not going to dress it up, but I noticed."),
            ),
            "reserved": (
                ("voice:reserved:1", "I didn't want to make a fuss about it in front of everyone."),
                ("voice:reserved:2", "I notice more than I usually say aloud."),
                ("voice:reserved:3", "I thought you should hear that from someone who was actually there."),
            ),
            "wary": (
                ("voice:wary:1", "Don't assume that means I trust every choice you make."),
                ("voice:wary:2", "It was the right action; I'm still keeping my own judgment."),
                ("voice:wary:3", "I noticed, though I'm not ready to draw a larger conclusion."),
            ),
            "hostile": (
                ("voice:hostile:1", "It didn't settle everything between us."),
                ("voice:hostile:2", "Doing one useful thing doesn't erase the rest."),
                ("voice:hostile:3", "I can acknowledge what happened without pretending we're friends."),
            ),
            "neutral": (
                ("voice:neutral:1", "People tend to remember things like that."),
                ("voice:neutral:2", "It changed the rest of the day more than you may realize."),
                ("voice:neutral:3", "I wanted to mention it while the details were still clear."),
            ),
        }
        reactions.extend(demeanor_reactions.get(demeanor, demeanor_reactions["neutral"]))
        if relationship >= 100 and kind not in {"spouse", "child"}:
            if category == "combat":
                reactions.extend((
                    ("bond:close:combat:1", "I've known you long enough to recognize how much that demanded of you."),
                    ("bond:close:combat:2", "You don't need to pretend it was easy with me."),
                ))
            else:
                reactions.extend((
                    ("bond:close:work:1", "I've known you long enough to recognize how much care you put into that."),
                    ("bond:close:work:2", "You didn't have to explain why it mattered; I could see it."),
                ))
        reaction = self.dialogue_fresh_world_line(
            actor, kind, "recent_observation_reactions", reactions,
            f"{self.dialogue_day_key()}:{actor.get('id')}:{event_id}:{channel}:reaction", 10,
        )
        line = f"{base} {reaction}".strip()
        if channel == "initiation":
            question = (
                "Is everyone safe now?" if verb in {"rescue", "extinguish"}
                else "Are you hurt?" if category == "combat" or verb in {"defeat", "clear"}
                else "How are you feeling about it now?"
            )
            line = f"{line} {question}"
        return line

    def dialogue_companion_ambient_line(
        self, actor: Dict[str, object], kind: str
    ) -> str:
        """Give active companions varied, grounded remarks about the current journey."""
        name = self.dialogue_actor_name(actor)
        place = self.world_dialogue_location_label()
        place_folded = place.casefold()
        weather = str(getattr(self.state, "weather", "clear") or "clear").casefold()
        season = str(getattr(self.state, "season", "Spring") or "Spring")
        hour = int(getattr(self.state, "hour", 12) or 12)
        minute_band = int(getattr(self.state, "minute", 0) or 0) // 20
        role = self.dialogue_actor_role(actor).casefold()
        traits = self.dialogue_personality_words(actor)
        relationship = self.dialogue_relationship_points(actor, kind)
        activity = self.dialogue_activity(actor, kind).replace("their ", "the ")
        candidates: List[Tuple[str, str]] = []
        if kind == "spouse":
            candidates.extend((
                ("spouse:route:1", "I'm glad we're doing this together instead of only talking about it at home."),
                ("spouse:route:2", "If you want to change our plans, tell me. I'd rather adjust than guess."),
                ("spouse:route:3", "We've been out for a while. I can keep going, but we should check in with each other."),
                ("spouse:route:4", f"Seeing {place} with you feels different from hearing about it afterward."),
            ))
        elif kind == "child":
            candidates.extend((
                ("child:route:1", "I'm still with you. I want to see where this path goes."),
                ("child:route:2", "Can we remember this route so I can draw it later?"),
                ("child:route:3", "I keep looking behind us so the way back doesn't disappear."),
                ("child:route:4", f"There is more to notice around {place} than I expected."),
            ))
        else:
            candidates.extend((
                ("companion:route:1", "I'm keeping pace. Say something if you want to change course."),
                ("companion:route:2", "We've covered a fair amount of ground. The return trip will feel shorter."),
                ("companion:route:3", "I'm watching the path behind us as well as the one ahead."),
                ("companion:route:4", "Before the next difficult stretch, we should check our supplies."),
                ("companion:route:5", f"Traveling through {place} makes more sense when someone else is reading the route too."),
                ("companion:route:6", "If we get separated, I'll return to the last clear landmark."),
            ))
        if "storm" in weather:
            candidates.extend((
                ("weather:storm:1", "That storm is swallowing distant sounds. Let's stay within sight of each other."),
                ("weather:storm:2", "The next shelter matters more than the next mile in weather like this."),
                ("weather:storm:3", "I'm watching the ground. Stormwater can change a safe path quickly."),
            ))
        elif any(word in weather for word in ("rain", "drizzle", "shower")):
            candidates.extend((
                ("weather:rain:1", "The rain is showing us every low place in the road."),
                ("weather:rain:2", "Let's keep moving while the footing is still good."),
                ("weather:rain:3", "Everything smells different after rain; even familiar ground feels new."),
            ))
        elif any(word in weather for word in ("snow", "blizzard")):
            candidates.extend((
                ("weather:snow:1", "Our tracks will make the return easier unless the snow covers them first."),
                ("weather:snow:2", "The snow makes distances deceptive. That ridge is farther away than it looks."),
                ("weather:snow:3", "Fresh tracks stand out clearly. We aren't the only ones moving through here."),
            ))
        else:
            candidates.extend((
                ("weather:clear:1", "Visibility is good. This is the time to learn the shape of the land."),
                ("weather:clear:2", "We can see far enough ahead to choose the better route."),
            ))
        if hour < 10:
            candidates.extend((
                ("time:morning:1", "Morning light makes the road easier to read."),
                ("time:morning:2", "We started early enough to take our time with the difficult ground."),
            ))
        elif hour >= 20:
            candidates.extend((
                ("time:late:1", "It is getting late. Let's decide whether we're pressing on or finding shelter."),
                ("time:late:2", "I can keep going, but darkness changes which risks are worth taking."),
            ))
        else:
            candidates.append(("time:day", f"We still have enough daylight to explore {place} carefully."))
        if "dungeon" in place_folded:
            candidates.extend((
                ("place:dungeon:1", "Let's mark every turn. These corridors are too similar to trust to memory alone."),
                ("place:dungeon:2", "A closed door can hide more than a room. I'll watch our way back."),
                ("place:dungeon:3", "Keep some strength in reserve. Deep places rarely end where you expect."),
            ))
        elif "cave" in place_folded or "mine" in place_folded:
            candidates.extend((
                ("place:cave:1", "The echoes make it hard to judge distance. Stay where we can see each other."),
                ("place:cave:2", "I'm checking the walls and ceiling as we move. Loose stone announces itself quietly."),
                ("place:cave:3", "We should remember where the air feels fresher; that usually points toward an exit."),
            ))
        elif "wilderness" in place_folded:
            candidates.extend((
                ("place:wilderness:1", "The open country looks empty until you slow down enough to notice what is moving."),
                ("place:wilderness:2", f"{season} has changed the landmarks I would normally use out here."),
                ("place:wilderness:3", "A road is useful, but I don't want us to stop reading the land around it."),
            ))
        elif any(word in place_folded for word in ("town", "settlement", "hamlet")):
            candidates.extend((
                ("place:town:1", "We should learn where people gather before we decide how long to stay."),
                ("place:town:2", "Every settlement has a rhythm. Give it a little time and the useful places reveal themselves."),
            ))
        if any(word in role for word in ("ranger", "hunter", "scout", "wayfarer")):
            candidates.extend((
                ("role:ranger:1", "The tracks beside the road are fresher than the tracks on it."),
                ("role:ranger:2", "I'll keep reading the route. You watch for anything that doesn't belong."),
            ))
        elif any(word in role for word in ("doctor", "nurse", "medic", "healer")):
            candidates.extend((
                ("role:healer:1", "Tell me before exhaustion becomes an injury. It is easier to stop trouble early."),
                ("role:healer:2", "I'm keeping an eye on both of us. Adrenaline can hide more than pain."),
            ))
        elif any(word in role for word in ("miner", "prospector", "blacksmith")):
            candidates.append(("role:miner", "The ground tells you what it can bear if you pay attention to the cracks."))
        elif any(word in role for word in ("merchant", "courier", "trader")):
            candidates.append(("role:merchant", "A good route is measured by where it lets people stop, not only where it ends."))
        elif any(word in role for word in ("farmer", "gardener", "rancher")):
            candidates.append(("role:farmer", "I keep noticing which patches of ground would hold water and which would drain."))
        if traits.intersection({"curious", "studious", "observant", "scholarly"}):
            candidates.append(("trait:curious", "I keep finding questions out here that I wouldn't have thought to ask at home."))
        if traits.intersection({"bold", "brave", "daring", "adventurous"}):
            candidates.append(("trait:bold", "If the road becomes dangerous, I'd rather meet it prepared than turn back too soon."))
        if traits.intersection({"cautious", "careful", "wary", "anxious"}):
            candidates.append(("trait:cautious", "I want a clear way back before we commit to going farther."))
        if traits.intersection({"practical", "organized", "steady", "reliable"}):
            candidates.append(("trait:practical", "Let's settle our direction before we spend daylight wandering between choices."))
        if relationship >= 100 or kind == "spouse":
            candidates.extend((
                ("bond:close:1", "We've traveled together long enough that I can usually tell when you're about to change plans."),
                ("bond:close:2", "You don't have to keep a brave face for my sake. Tell me if you need a rest."),
            ))
        if activity and not any(
            phrase in activity.casefold()
            for phrase in ("traveling with", "following", "accompanying")
        ):
            candidates.append((
                "activity:current",
                f"I can keep {activity} while we move, but tell me when you need my full attention.",
            ))
        return self.dialogue_fresh_world_line(
            actor, kind, "recent_companion_line_ids", candidates,
            f"{self.dialogue_day_key()}:{name}:{hour}:{minute_band}:{place}:{weather}", 12,
        )

    def world_dialogue_ambient_line(
        self, actor: Dict[str, object], kind: str
    ) -> str:
        callout = self.dialogue_initiation_callout(actor, kind)
        if callout:
            return callout
        witnessed = self.dialogue_witness_callback(actor, kind, "ambient")
        if witnessed:
            return witnessed
        name = self.dialogue_actor_name(actor)
        activity = self.dialogue_activity(actor, kind).replace("their ", "the ")
        weather = str(getattr(self.state, "weather", "clear") or "clear").casefold()
        hour = int(getattr(self.state, "hour", 12) or 12)
        if kind in {"companion", "spouse", "child"}:
            return self.dialogue_companion_ambient_line(actor, kind)
        # These branches sit in front of the demeanor pools below, so a single
        # fixed line here means every NPC in town says the same sentence for a
        # whole rainy day. Seed per-NPC so weather does not flatten character.
        weather_seed = f"{self.dialogue_day_key()}:{actor.get('id', name)}:ambient-weather"
        if "storm" in weather:
            return _stable_pick(weather_seed, (
                "That storm is making every route and errand harder to judge.",
                "Half the day's plans went out with that wind.",
                "I keep listening for something to come loose on the roof.",
                "Storms like this sort out who prepared and who improvised.",
                "Nothing beyond the door is worth the walk while it is blowing like that.",
            ))
        if any(word in weather for word in ("rain", "drizzle", "shower")):
            return _stable_pick(weather_seed, (
                "The rain has changed which paths people are using today.",
                "Everything takes twice as long once the ground goes soft.",
                "I have given up on staying dry and started on staying useful.",
                "Rain does the watering and ruins the walking. Fair trade, most days.",
                "You can tell who owns decent boots on a day like this.",
            ))
        if any(word in weather for word in ("snow", "blizzard")):
            return _stable_pick(weather_seed, (
                "Fresh snow makes it easy to see who has already passed this way.",
                "The cold sharpens everything, including tempers.",
                "Snow makes the whole place quieter than it has any right to be.",
                "I am counting on the path staying passable until evening.",
                "Everything looks tidier under snow. It is lying to you.",
            ))
        if self.dialogue_is_on_duty(actor, kind):
            return _stable_pick(f"{weather_seed}:duty", (
                f"I am {activity}. Let me know if you need something connected to my work.",
                f"I am in the middle of {activity}. Say what you need and I will fit it in.",
                f"Busy with {activity}, but I can talk while my hands work.",
                f"I have {activity} to finish today. Ask if you need something from me.",
            ))
        if hour >= 21 or hour < 6:
            return _stable_pick(f"{weather_seed}:late", (
                "It is late enough that every light and familiar voice matters.",
                "Late hours make strangers either welcome or worrying. You are the first one.",
                "I should be asleep. So should most people still out here.",
                "Nothing good starts this late, but a good deal of it finishes.",
                "The town is honest at this hour. Nobody is performing for anyone.",
            ))
        demeanor = self.dialogue_demeanor(actor, kind)
        pools = {
            "warm": (
                "Good to see someone else out and about.",
                f"I've been {activity}; it has been an interesting day for it.",
                "You picked a decent moment to say hello.",
                f"I am {activity}, but there is always room for a bit of company.",
            ),
            "professional": (
                f"I'm {activity}; the day's work is still moving.",
                "The local routine has been busier than it looks.",
                "If you need something specific, I can point you the right way.",
                f"I have {activity} to finish, and then the day loosens up.",
            ),
            "skeptical": (
                "The roads have been busy. I'm keeping an eye on who uses them.",
                f"I've been {activity}. Not everything around here is as simple as it looks.",
                "People have been asking a great many questions lately. Yours are welcome to be different.",
                "I notice things. That is habit, not suspicion.",
            ),
            "blunt": (
                f"I'm {activity}. Standing around will not finish it.",
                "If you need something, say it plainly.",
                "Say what you came to say.",
                f"I am {activity}. That is the whole report.",
            ),
            "reserved": (
                f"I've been {activity}. Quiet work suits me.",
                "You notice more when nobody expects you to speak.",
                "I am here most days, if you need something.",
                "I do not mind company. I just do not fill silences.",
            ),
            "wary": (
                "I don't know you well enough to explain what I'm doing.",
                "Keep to the open path and we will have no trouble.",
                "You are welcome to pass. That is as far as I go today.",
                "I would rather know who I am talking to first.",
            ),
            "hostile": (
                "Keep moving.",
                "I have nothing to say to you.",
                "Do not make this a conversation.",
                "Whatever it is, no.",
            ),
            "neutral": (
                f"I've been {activity}.",
                f"People around {self.world_dialogue_location_label()} are settling into today's routine.",
                "An ordinary day so far.",
                f"Nothing unusual to report. I am {activity}.",
            ),
        }
        return _stable_pick(
            f"{self.dialogue_day_key()}:{actor.get('id', name)}:{hour}:{activity}",
            pools.get(demeanor, pools["neutral"]),
        )

    def world_dialogue_pair_exchange(
        self, first: Dict[str, object], second: Dict[str, object]
    ) -> Tuple[str, str]:
        first_actor = first.get("actor", {})
        second_actor = second.get("actor", {})
        if not isinstance(first_actor, dict) or not isinstance(second_actor, dict):
            return "", ""
        first_name = self.dialogue_actor_name(first_actor)
        second_name = self.dialogue_actor_name(second_actor)
        first_kind = str(first.get("kind", "authored"))
        second_kind = str(second.get("kind", "authored"))
        first_activity = self.dialogue_activity(first_actor, first_kind)
        location = self.world_dialogue_location_label()
        self.dialogue_propagate_knowledge(first_actor, first_kind, second_actor, second_kind)
        self.dialogue_propagate_knowledge(second_actor, second_kind, first_actor, first_kind)
        question = _stable_pick(
            f"{self.dialogue_day_key()}:{first_name}:{second_name}:question",
            (
                f"{second_name}, have the routes around {location} been this busy all day?",
                f"{second_name}, did you hear whether today's work is still on schedule?",
                f"{second_name}, I'm {first_activity}. How is your part of the day going?",
            ),
        )
        demeanor = self.dialogue_demeanor(second_actor, second_kind)
        response_pool = {
            "warm": ("Busy, but manageable. I'll tell you if that changes.", "Better now that I can compare notes with someone."),
            "skeptical": ("Busy enough. I would rather confirm the details before repeating them.", "Something changed, but I don't know enough to call it news."),
            "blunt": ("It is moving. Slowly.", "Ask me after the work is actually finished."),
            "reserved": ("A little different than usual. I'll explain when I know why.", "Quiet so far, which is not the same as uneventful."),
            "professional": ("Everything is still operating. I'll pass along any practical change.", "On schedule for now. Check again before closing time."),
            "neutral": ("More or less. People have been adjusting as they go.", "There have been a few changes, but nothing has stopped."),
        }
        response = _stable_pick(
            f"{self.dialogue_day_key()}:{second_name}:{first_name}:response",
            response_pool.get(demeanor, response_pool["neutral"]),
        )
        return question, response

    def world_dialogue_emit_ambient(
        self, nearby: Optional[List[Dict[str, object]]] = None
    ) -> bool:
        actors = list(nearby if nearby is not None else self.world_dialogue_nearby_actors())
        if not actors or not hasattr(self, "add_hud_activity"):
            return False
        seed = (
            f"{self.dialogue_day_key()}:{getattr(self.state, 'hour', 0)}:"
            f"{int(getattr(self.state, 'minute', 0)) // 20}:{self.world_dialogue_location_label()}"
        )
        pair_candidates: List[Tuple[Dict[str, object], Dict[str, object]]] = []
        for index, first in enumerate(actors):
            for second in actors[index + 1:]:
                distance = max(
                    abs(int(first.get("x", 0)) - int(second.get("x", 0))),
                    abs(int(first.get("y", 0)) - int(second.get("y", 0))),
                )
                if distance <= 4:
                    pair_candidates.append((first, second))
        if pair_candidates and _stable_index(seed + ":pair-or-bark", 4) == 0:
            pair = pair_candidates[_stable_index(seed + ":pair", len(pair_candidates))]
            question, response = self.world_dialogue_pair_exchange(*pair)
            if question and response:
                question = naturalize_spoken_dialogue(question)
                response = naturalize_spoken_dialogue(response)
                self.add_hud_activity(
                    f"{self.dialogue_actor_name(pair[0]['actor'])}: \"{question}\"", "dialogue"
                )
                self.add_hud_activity(
                    f"{self.dialogue_actor_name(pair[1]['actor'])}: \"{response}\"", "dialogue"
                )
                return True
        candidates = actors[: min(5, len(actors))]
        selected = candidates[_stable_index(seed + ":speaker", len(candidates))]
        actor = selected.get("actor", {})
        kind = str(selected.get("kind", "authored"))
        if not isinstance(actor, dict):
            return False
        line = naturalize_spoken_dialogue(self.world_dialogue_ambient_line(actor, kind))
        if not line:
            return False
        self.add_hud_activity(f"{self.dialogue_actor_name(actor)}: \"{line}\"", "dialogue")
        return True

    def world_dialogue_tick(self, minutes: int = 1) -> bool:
        """Occasionally surface nearby speech without interrupting movement."""
        if int(minutes) <= 0 or getattr(self.state, "active_scene_id", ""):
            return False
        store = getattr(self.state, "npc_dialogue_social_state", None)
        if not isinstance(store, dict):
            store = {}
            self.state.npc_dialogue_social_state = store
        world_slot = store.setdefault("__world__", {})
        if not isinstance(world_slot, dict):
            world_slot = {}
            store["__world__"] = world_slot
        slot_key = (
            f"{self.dialogue_day_key()}:{int(getattr(self.state, 'hour', 0))}:"
            f"{int(getattr(self.state, 'minute', 0)) // 20}:"
            f"{getattr(self.state, 'location', '')}:"
            f"{getattr(self.state, 'wilderness_chunk_x', 0)},"
            f"{getattr(self.state, 'wilderness_chunk_y', 0)}"
        )
        if str(world_slot.get("last_ambient_slot", "")) == slot_key:
            return False
        world_slot["last_ambient_slot"] = slot_key
        if _stable_index(slot_key + ":frequency", 3) != 0:
            return False
        nearby = self.world_dialogue_nearby_actors()
        if not nearby:
            return False
        return self.world_dialogue_emit_ambient(nearby)

    def dialogue_adjust_social_reputation(
        self, amount: int, actor: Dict[str, object], kind: str, reason: str
    ) -> int:
        before = int(getattr(self.state, "social_reputation", 0) or 0)
        after = max(-1000, min(1000, before + int(amount)))
        self.state.social_reputation = after
        if kind == "procedural" and hasattr(self, "adjust_procedural_town_reputation"):
            plan = self.current_procedural_town_plan() or {}
            if plan and amount:
                self.adjust_procedural_town_reputation(
                    1 if amount > 0 else max(-3, int(amount)), reason, plan
                )
        return after - before

    def dialogue_adjust_actor_relationship(
        self, actor: Dict[str, object], kind: str, amount: int
    ) -> int:
        actor_id = str(actor.get("id", ""))
        if (
            kind in {"authored", "spouse"} or self.dialogue_is_persistent_world_actor(actor, kind)
        ) and actor_id and hasattr(self, "adjust_town_npc_relationship"):
            return int(self.adjust_town_npc_relationship(actor_id, int(amount)))
        if kind == "child" and hasattr(self, "adjust_child_affection"):
            return int(self.adjust_child_affection(actor, int(amount)))
        if kind == "companion" and actor_id and hasattr(self, "adjust_travel_follower_bond"):
            return int(self.adjust_travel_follower_bond(actor_id, int(amount)))
        if kind == "traveler" and actor.get("recurring") and hasattr(self, "recurring_wilderness_traveler_record"):
            record = self.recurring_wilderness_traveler_record(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
            )
            before = int(record.get("bond", 0) or 0)
            record["bond"] = max(0, min(250, before + int(amount)))
            actor["bond"] = int(record["bond"])
            return int(record["bond"]) - before
        if kind == "regional_visitor":
            life = getattr(self.state, "regional_town_life", {})
            if isinstance(life, dict):
                bonds = life.setdefault("visitor_bonds", {})
                before = int(bonds.get(actor_id, actor.get("bond", 0)) or 0)
                bonds[actor_id] = max(0, min(250, before + int(amount)))
                actor["bond"] = int(bonds[actor_id])
                return int(bonds[actor_id]) - before
        field = "relationship" if kind == "procedural" else "bond"
        before = int(actor.get(field, 0) or 0)
        actor[field] = max(-50 if field == "relationship" else 0, min(250, before + int(amount)))
        return int(actor[field]) - before

    def dialogue_player_speaker(self) -> Dict[str, object]:
        return {
            "id": "player", "name": str(getattr(self.state, "player_name", "You")),
            "role": "You", "_dialogue_kind": "player",
        }

    def dialogue_player_disclosure_statement(self, subject: str) -> str:
        if subject == "background":
            background = str(getattr(self.state, "player_background", "farmer"))
            starting_class = str(getattr(self.state, "player_starting_class", "adventurer"))
            origin = str(getattr(self.state, "player_origin", "Nearby Farming Country"))
            return (
                f"I am from {origin}. I came to this life as a {background.lower()}, "
                f"and my original training was as a {starting_class.lower()}."
            )
        if subject == "deeds":
            deeds: List[Tuple[int, str]] = [
                (int(getattr(self.state, "wilderness_strongholds_cleared", 0) or 0), "strongholds reclaimed"),
                (int(getattr(self.state, "mine_enemies_defeated", 0) or 0), "mine enemies defeated"),
                (len(getattr(self.state, "completed_bounty_log", []) or []), "bounties completed"),
                (int(getattr(self.state, "archaeology_finds", 0) or 0), "archaeological finds"),
                (int(getattr(self.state, "paleontology_finds", 0) or 0), "paleontological finds"),
                (len(getattr(self.state, "completed_town_project_ids", []) or []), "town projects completed"),
            ]
            notable = [(count, label) for count, label in sorted(deeds, reverse=True) if count > 0][:3]
            if not notable:
                return "I am still near the beginning of my story. Most of what I have done so far is establish the farm and learn the surrounding roads."
            return "Some of the things I have done include " + ", ".join(f"{count} {label}" for count, label in notable) + "."
        if subject == "travels":
            regions = int(getattr(self.state, "wilderness_chunks_visited", 1) or 1)
            region_word = "region" if regions == 1 else "regions"
            return (
                f"I have crossed {regions} wilderness {region_word}, "
                f"found {int(getattr(self.state, 'wilderness_caves_discovered', 0) or 0)} caves and "
                f"{int(getattr(self.state, 'wilderness_dungeons_discovered', 0) or 0)} dungeons, and I am currently charting around "
                f"({int(getattr(self.state, 'wilderness_chunk_x', 0))},{int(getattr(self.state, 'wilderness_chunk_y', 0))})."
            )
        if subject == "loot":
            equipment = getattr(self.state, "generated_equipment", {})
            names = [
                str(record.get("name", key)) if isinstance(record, dict) else str(key)
                for key, record in (equipment.items() if isinstance(equipment, dict) else [])
            ][-3:]
            if not names:
                carried = sorted(
                    ((int(qty or 0), str(item)) for item, qty in (getattr(self.state, "inventory", {}) or {}).items() if int(qty or 0) > 0),
                    reverse=True,
                )[:3]
                names = [quantity_item_phrase(item, qty) for qty, item in carried]
            gear = [
                str(getattr(self.state, "equipped_weapon", "")),
                str(getattr(self.state, "equipped_armor", "")),
            ]
            details = names or [value for value in gear if value]
            return "The most notable things I have recovered or carried lately are " + ", ".join(details[:4]) + "." if details else "I have not recovered anything remarkable lately."
        if subject == "companions":
            follower_ids = list(getattr(self.state, "travel_follower_ids", []) or [])
            names = [str(self.travel_follower_data(follower_id).get("name", follower_id)) for follower_id in follower_ids] if hasattr(self, "travel_follower_data") else follower_ids
            return f"I currently travel with {', '.join(names)}. We have learned to share roads, danger, and responsibility." if names else "I am traveling alone at the moment, though that has not always been the case."
        if subject == "family":
            spouse_id = str(getattr(self.state, "spouse_npc_id", ""))
            spouse = self.npc_record_by_id(spouse_id) if spouse_id and hasattr(self, "npc_record_by_id") else None
            spouse_name = str(spouse.get("name", spouse_id)) if isinstance(spouse, dict) else spouse_id
            children = [str(child.get("name", "my child")) for child in getattr(self.state, "children", []) or [] if isinstance(child, dict)]
            if spouse_name and children:
                kin = "child is" if len(children) == 1 else "children are"
                return f"I am married to {spouse_name}, and our {kin} {', '.join(children)}."
            if spouse_name:
                return f"I am married to {spouse_name}."
            if children:
                kin = "child is" if len(children) == 1 else "children are"
                return f"My {kin} {', '.join(children)}."
            return "I do not currently have a spouse or children, so my household is still mostly defined by the farm."
        dynasty = str(getattr(self.state, "dynasty_name", "") or f"{getattr(self.state, 'player_name', 'My')} family")
        generation = int(getattr(self.state, "player_generation", 1) or 1)
        history = list(getattr(self.state, "dynasty_history", []) or [])
        heirlooms = list(getattr(self.state, "dynasty_heirlooms", []) or [])
        return (
            f"I'm generation {generation} of the {dynasty}. Our records preserve "
            f"{quantity_agreement(len(history), 'earlier household head')} and "
            f"{quantity_agreement(len(heirlooms), 'family heirloom')}."
        )

    def dialogue_disclosure_reaction(
        self, actor: Dict[str, object], kind: str, subject: str, repeated: bool
    ) -> str:
        if repeated:
            return "You told me about that before. Has anything changed since then?"
        demeanor = self.dialogue_demeanor(actor, kind)
        subject_reactions = {
            "background": "That explains how you ended up here.",
            "deeds": "You've been busy.",
            "travels": "You've covered a lot of ground.",
            "loot": "You've found some interesting things.",
            "companions": "It helps to know who travels with you.",
            "family": "I'll remember their names.",
            "ancestry": "That is a long family history to carry.",
        }
        base = subject_reactions.get(subject, "That helps me understand you better.")
        tones = {
            "professional": "Thanks for explaining. ",
            "warm": "I'm glad you told me. ",
            "skeptical": "I only know your side of it, but I heard you. ",
            "blunt": "All right. ",
            "reserved": "Thank you for telling me. ",
            "wary": "I heard you. ",
            "hostile": "Fine. ",
            "neutral": "I see. ",
        }
        return tones[demeanor] + base

    def dialogue_handle_player_disclosure(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        options: List[DialogueOption] = [
            ("background", "Tell them where you came from", "Your background and original combat training."),
            ("deeds", "Discuss things you have done", "Completed projects, victories, discoveries, and bounties."),
            ("travels", "Describe your recent travels", "Explored wilderness, caves, dungeons, and current coordinates."),
            ("loot", "Show or describe notable loot", "Recent equipment and noteworthy carried possessions."),
            ("companions", "Talk about your companions", "The people currently traveling with you."),
            ("family", "Talk about your spouse or children", "Your actual household and family members."),
            ("ancestry", "Discuss your ancestry", "Dynasty generation, earlier household heads, and heirlooms."),
            ("back", "Talk about something else", "Return to the conversation."),
        ]
        subject = self.dialogue_choose(actor, "What would you like to share?", "about you", options, transcript)
        if not subject or subject == "back":
            return True
        statement = self.dialogue_player_disclosure_statement(subject)
        if not self.dialogue_say(self.dialogue_player_speaker(), statement, "you", transcript):
            return False
        slot = self.dialogue_social_slot(actor, kind)
        repeated = any(str(row.get("subject", "")) == subject for row in slot["disclosures"])
        slot["disclosures"] = (list(slot["disclosures"]) + [{"subject": subject, "day": self.dialogue_day_key()}])[-12:]
        return self.dialogue_say(
            actor, self.dialogue_disclosure_reaction(actor, kind, subject, repeated), "response", transcript
        )

    def dialogue_social_action_reaction(
        self, actor: Dict[str, object], kind: str, action: str
    ) -> str:
        demeanor = self.dialogue_demeanor(actor, kind)
        if action.startswith("compliment"):
            return {
                "professional": "Thank you. I try to do the job well.",
                "warm": "Oh, thank you! That's kind of you.",
                "skeptical": "Thank you. What brought that on?",
                "blunt": "Thanks. I appreciate you being specific.",
                "reserved": "Thank you. I appreciate it.",
                "wary": "Thank you. I'll take you at your word.",
                "hostile": "A compliment does not fix things between us.",
                "neutral": "Thank you. That was kind of you.",
            }[demeanor]
        return {
            "professional": "That was unnecessary. If you need something, ask without insulting me.",
            "warm": "Why would you say that to me?",
            "skeptical": "I wondered how long the polite act would last.",
            "blunt": "If you wanted me to dislike you, it worked.",
            "reserved": "I have nothing further to say to you right now.",
            "wary": "I was right to be cautious around you.",
            "hostile": "Leave me alone.",
            "neutral": "That was rude. I'll remember it.",
        }[demeanor]

    def dialogue_handle_smalltalk(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        action = self.dialogue_choose(actor, "What kind of small talk?", "small talk", [
            ("casual", "Make a casual observation", "Weather, season, activity, or something happening nearby; no social consequence."),
            ("compliment_work", "Compliment their work", "A sincere, specific compliment; relationship and social reputation can improve once per day."),
            ("compliment_character", "Compliment their character", "Personal praise; relationship and social reputation can improve once per day."),
            ("insult_work", "Insult their work", "Relationship -4 and social reputation -2 the first time today."),
            ("insult_personal", "Insult them personally", "Relationship -5 and social reputation -3 the first time today."),
            ("back", "Talk about something else", "Return without saying anything."),
        ], transcript)
        if not action or action == "back":
            return True
        if action == "casual":
            observation = _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:player-smalltalk",
                (
                    f"The {str(getattr(self.state, 'weather', 'clear')).lower()} weather has changed the pace of the day.",
                    f"{getattr(self.state, 'season', 'This season')} seems to be moving quickly this year.",
                    f"It seems busier than usual around {self.world_dialogue_location_label()}.",
                ),
            )
            if not self.dialogue_say(self.dialogue_player_speaker(), observation, "you", transcript):
                return False
            weather = str(getattr(self.state, "weather", "clear") or "clear").lower()
            activity = self.dialogue_activity(actor, kind).replace("their ", "my ")
            return self.dialogue_say(
                actor,
                f"It is. The {weather} weather changes how I handle {activity}.",
                "response",
                transcript,
            )
        compliment = action.startswith("compliment")
        player_line = {
            "compliment_work": "You seem to take your work seriously. I respect that.",
            "compliment_character": "You've been fair with me. I appreciate it.",
            "insult_work": "The way you handle your work is embarrassing.",
            "insult_personal": "Talking to you has made it difficult to respect you.",
        }[action]
        if not self.dialogue_say(self.dialogue_player_speaker(), player_line, "you", transcript):
            return False
        slot = self.dialogue_social_slot(actor, kind)
        today = self.dialogue_day_key()
        day_field = "last_compliment_day" if compliment else "last_insult_day"
        repeated = str(slot.get(day_field, "")) == today
        relationship_change = 0
        reputation_change = 0
        if not repeated:
            relationship_change = self.dialogue_adjust_actor_relationship(
                actor, kind, 2 if compliment else (-4 if action == "insult_work" else -5)
            )
            reputation_change = self.dialogue_adjust_social_reputation(
                1 if compliment else (-2 if action == "insult_work" else -3),
                actor, kind, f"Social interaction with {self.dialogue_actor_name(actor)}",
            )
            slot[day_field] = today
            if not compliment:
                actor["_dialogue_suppress_talk_gain"] = True
                self.dialogue_set_mood(
                    actor, kind, "angry", "the insult you directed at me", 3, 3
                )
            else:
                self.dialogue_set_mood(
                    actor, kind, "grateful", "the sincere compliment you offered", 1, 2
                )
        reaction = self.dialogue_social_action_reaction(actor, kind, action)
        if repeated:
            reaction += " You've already made that clear today."
        else:
            if hasattr(self, "add_hud_activity"):
                self.add_hud_activity(
                    f"Relationship with {self.dialogue_actor_name(actor)} {relationship_change:+}; reputation {reputation_change:+}.",
                    "social",
                )
        return self.dialogue_say(actor, reaction, "response", transcript)

    def dialogue_follower_id_for_actor(
        self, actor: Dict[str, object]
    ) -> str:
        actor_id = str(actor.get("id", "") or "")
        if actor_id.startswith(("companion:", "spouse:", "child:")):
            return actor_id
        if actor_id and hasattr(self, "travel_follower_identity_for_npc_id"):
            return str(self.travel_follower_identity_for_npc_id(actor_id) or "")
        return ""

    def dialogue_schedule_shared_activity(
        self,
        actor: Dict[str, object],
        kind: str,
        transcript: List[Dict[str, str]],
        romantic: bool = False,
    ) -> bool:
        actor_id = str(actor.get("id", "") or "")
        actor_name = self.dialogue_actor_name(actor)
        activity_kinds = ("relationship_date",) if romantic else ("social_outing",)
        if hasattr(self, "open_planned_events_for_actor") and self.open_planned_events_for_actor(
            actor_id, activity_kinds
        ):
            return self.dialogue_say(
                actor,
                "We already have time set aside together. Let us keep that plan before making another one.",
                "arrangement", transcript,
            )

        current_destination = self.quest_capture_current_destination()
        current_destination["label"] = "this place"
        destinations: List[Tuple[str, str, Dict[str, object]]] = [
            ("__HERE__", "Spend time here", current_destination)
        ]
        for place in self.dialogue_known_places(actor, kind):
            destination = self.quest_destination_for_known_place(place)
            if not destination:
                continue
            destinations.append((
                str(place.get("id", place.get("name", len(destinations)))),
                str(place.get("name", "Known place")), dict(destination),
            ))
            if len(destinations) >= 13:
                break
        destination_options: List[DialogueOption] = [
            (place_id, label, str(destination.get("label", destination.get("location", "Known place"))))
            for place_id, label, destination in destinations
        ]
        destination_options.append(("back", "Decide later", "Do not schedule anything yet."))
        selected_place = self.dialogue_choose(
            actor,
            "Where would you like to spend the time together?",
            "date" if romantic else "outing",
            destination_options,
            transcript,
        )
        selected_destination = next(
            (destination for place_id, _label, destination in destinations if place_id == selected_place),
            None,
        )
        if selected_destination is None:
            return True

        day_choice = self.dialogue_choose(actor, "Which day works?", "arrangement", [
            ("1", "Tomorrow", "Meet on the next calendar day."),
            ("2", "In two days", "Leave one full day to prepare."),
            ("3", "In three days", "Put it farther ahead on the calendar."),
            ("back", "Decide later", "Do not schedule the activity."),
        ], transcript)
        if day_choice not in {"1", "2", "3"}:
            return True
        time_choice = self.dialogue_choose(actor, "What time should you meet?", "arrangement", [
            ("10", "Morning, 10:00", "Good for markets, walks, and quiet public places."),
            ("14", "Afternoon, 14:00", "Good for travel and outdoor activities."),
            ("18", "Evening, 18:00", "Good for taverns, meals, and dates."),
            ("back", "Decide later", "Do not schedule the activity."),
        ], transcript)
        if time_choice not in {"10", "14", "18"}:
            return True

        due_day = self.dialogue_absolute_day() + int(day_choice)
        due_hour = int(time_choice)
        event_kind = "relationship_date" if romantic else "social_outing"
        title = f"{'Date' if romantic else 'Outing'} with {actor_name}"
        event_id = f"{event_kind}:{actor_id}:{due_day}:{due_hour}"
        event = self.schedule_planned_event({
            "id": event_id,
            "title": title,
            "kind": event_kind,
            "status": "planned",
            "auto_activate": True,
            "requires_attendance": True,
            "romantic": bool(romantic),
            "due_day": due_day,
            "due_hour": due_hour,
            "expires_at_minute": due_day * 1440 + (due_hour + 8) * 60,
            "destination": dict(selected_destination),
            "participants": [{
                "actor_id": actor_id,
                "name": actor_name,
                "role": str(actor.get("role", "Resident")),
                "kind": kind,
                "mode": "meet",
                "purpose": "a date" if romantic else "a shared outing",
                "destination": dict(selected_destination),
            }],
        })
        slot = self.dialogue_social_slot(actor, kind)
        slot["meetings"] = (list(slot.get("meetings", [])) + [{
            "day": due_day,
            "made_day": self.dialogue_absolute_day(),
            "purpose": "spend intentional time together" if romantic else "share an outing",
            "event_id": event_id,
            "destination": dict(selected_destination),
            "completed": False,
        }])[-6:]
        if hasattr(self, "autosave_with_message"):
            self.autosave_with_message(f"Planned {title.lower()}.")
        return self.dialogue_say(
            actor,
            f"Then we will meet at {event['destination'].get('label', 'the agreed place')} "
            f"in {int(day_choice)} day{'s' if day_choice != '1' else ''}, at {due_hour:02d}:00. I'll see you there.",
            "date" if romantic else "outing",
            transcript,
        )

    def dialogue_handle_planned_activity_arrival(
        self,
        actor: Dict[str, object],
        kind: str,
        event: Dict[str, object],
        participant: Dict[str, object],
    ) -> bool:
        transcript: List[Dict[str, str]] = []
        romantic = str(event.get("kind", "")) == "relationship_date"
        actor_name = self.dialogue_actor_name(actor)
        destination = dict(event.get("destination", {}) or {})
        place = str(destination.get("label", destination.get("location", "the agreed place")))
        narrator = {
            "id": f"activity:{event.get('id', '')}", "name": "Narrator",
            "role": str(event.get("title", "Planned activity")), "_dialogue_kind": "scene",
        }
        if not self.dialogue_say(
            narrator,
            f"You find {actor_name} waiting at {place}.",
            "arrival", transcript,
        ):
            return False
        opening = (
            "I'm glad you came. What do you feel like doing?"
            if romantic else
            "You made it. What should we do first?"
        )
        if not self.dialogue_say(actor, opening, "date" if romantic else "outing", transcript):
            return False
        choices: List[DialogueOption] = [
            ("conversation", "Give them your full attention", "Talk honestly and listen without treating the meeting as a transaction."),
            ("exploration", "Explore the place together", "Walk the surroundings and make the destination part of the memory."),
            ("future", "Talk about future plans", "Discuss work, travel, home, and what each of you wants next."),
        ]
        if romantic:
            choices.extend([
                ("chemistry", "Let the attraction show", "Flirt openly and enjoy being wanted without turning the date into a transaction."),
                ("quiet", "Find a quieter place together", "Step away from the crowd for a more intimate, still non-explicit conversation."),
            ])
        choices.append(("back", "Not yet", "Return to the world without concluding the activity."))
        choice = self.dialogue_choose(
            actor,
            "How do you spend the time together?",
            "date" if romantic else "outing",
            choices,
            transcript,
        )
        if choice not in {"conversation", "exploration", "future", "chemistry", "quiet"}:
            return False

        relationship_gain = 0
        if romantic and hasattr(self, "court_town_npc"):
            can_court, reason = self.can_court_town_npc(actor)
            if can_court:
                before = int(self.town_npc_relationship(str(actor.get("id", ""))))
                self.court_town_npc(actor, present=False)
                relationship_gain = int(self.town_npc_relationship(str(actor.get("id", "")))) - before
            elif self.state.town_npc_last_court_day.get(str(actor.get("id", ""))) != self.town_npc_day_key():
                self.dialogue_say(actor, reason, "date", transcript)
                return False
        else:
            relationship_gain = self.dialogue_adjust_actor_relationship(actor, kind, 2)

        response = {
            "conversation": "I'm glad we had time to talk without rushing.",
            "exploration": f"I had a good time exploring {place} with you.",
            "future": "I'm glad we can talk about what comes next.",
            "chemistry": romance_flirt_response(
                self.dialogue_romance_stage(actor), "playful",
                self.dialogue_demeanor(actor, kind),
                f"{event.get('id')}:{actor.get('id')}:chemistry",
                self.dialogue_kinship_context(actor),
            ),
            "quiet": romance_flirt_response(
                self.dialogue_romance_stage(actor), "private",
                self.dialogue_demeanor(actor, kind),
                f"{event.get('id')}:{actor.get('id')}:quiet",
                self.dialogue_kinship_context(actor),
            ),
        }[choice]
        mood = {
            "conversation": "grateful", "exploration": "excited", "future": "hopeful",
            "chemistry": "excited", "quiet": "hopeful",
        }[choice]
        self.dialogue_set_mood(actor, kind, mood, f"the time you shared at {place}", 2, 3)
        event["activity_choice"] = choice
        event["outcome"] = response
        event["relationship_gain"] = int(relationship_gain)
        if romantic and str(actor.get("id", "")) == str(getattr(self.state, "spouse_npc_id", "")) and hasattr(self, "record_family_event"):
            self.record_family_event("Date", f"Spent intentional time with {actor_name} at {place}.")
        if hasattr(self, "add_hud_activity"):
            self.add_hud_activity(f"Completed {event.get('title', 'a planned activity')} at {place}.", "social")
        self.dialogue_say(
            actor,
            response,
            "reflection", transcript,
        )
        if relationship_gain and hasattr(self, "add_hud_activity"):
            self.add_hud_activity(
                f"Relationship with {actor_name} {relationship_gain:+}.", "social"
            )
        return True

    def dialogue_schedule_group_gathering(
        self,
        actor: Dict[str, object],
        kind: str,
        transcript: List[Dict[str, str]],
    ) -> bool:
        host_id = str(actor.get("id", "") or "")
        host_name = self.dialogue_actor_name(actor)
        if hasattr(self, "open_planned_events_for_actor") and self.open_planned_events_for_actor(
            host_id, ("social_gathering",)
        ):
            return self.dialogue_say(
                actor, "We already have a gathering on the calendar. Let us host that one before planning another.",
                "gathering", transcript,
            )
        candidates = [
            person for person in self.dialogue_known_people(actor, kind)
            if isinstance(person, dict) and str(person.get("id", "")) not in {"", host_id}
        ]
        unique_people: Dict[str, Dict[str, object]] = {}
        for person in candidates:
            unique_people.setdefault(str(person.get("id", person.get("name", ""))), person)
        candidates = list(unique_people.values())[:12]
        if not candidates:
            return self.dialogue_say(
                actor,
                "I do not know anyone appropriate to invite yet. A gathering should grow from actual relationships, not fill itself with strangers.",
                "gathering", transcript,
            )

        invited: List[Dict[str, object]] = []
        while len(invited) < 3:
            remaining = [person for person in candidates if person not in invited]
            if not remaining:
                break
            invite_options: List[DialogueOption] = [
                (str(person.get("id", person.get("name", ""))), str(person.get("name", "Guest")), str(person.get("role", "Known person")))
                for person in remaining
            ]
            if invited:
                invite_options.append((
                    "done", "Finish the guest list",
                    f"Invite {quantity_agreement(len(invited), 'additional guest')}.",
                ))
            else:
                invite_options.append(("back", "Decide later", "Do not schedule a gathering."))
            selected = self.dialogue_choose(
                actor,
                "Who should be invited?" if not invited else "Invite anyone else?",
                "guest list", invite_options, transcript,
            )
            if selected in {"back", "goodbye", ""}:
                return True
            if selected == "done":
                break
            guest = next(
                (person for person in remaining if str(person.get("id", person.get("name", ""))) == selected),
                None,
            )
            if guest is None:
                return True
            invited.append(guest)

        current_destination = self.quest_capture_current_destination()
        current_destination["label"] = "this place"
        venues: List[Tuple[str, str, Dict[str, object]]] = [("__HERE__", "Gather here", current_destination)]
        place_rows = [{"id": "town:farm", "name": "Your Farm", "kind": "town"}] + self.dialogue_known_places(actor, kind)
        seen_venues = {"__HERE__"}
        for place in place_rows:
            place_id = str(place.get("id", place.get("name", "")))
            if not place_id or place_id in seen_venues:
                continue
            destination = self.quest_destination_for_known_place(place)
            if not destination:
                continue
            destination = dict(destination)
            destination["known_place_id"] = place_id
            venues.append((place_id, str(place.get("name", "Known place")), destination))
            seen_venues.add(place_id)
            if len(venues) >= 13:
                break
        venue_options: List[DialogueOption] = [
            (place_id, label, str(destination.get("label", destination.get("location", "Known place"))))
            for place_id, label, destination in venues
        ] + [("back", "Decide later", "Do not schedule the gathering.")]
        selected_venue = self.dialogue_choose(actor, "Where should everyone gather?", "venue", venue_options, transcript)
        venue_row = next((row for row in venues if row[0] == selected_venue), None)
        if venue_row is None:
            return True
        destination = dict(venue_row[2])

        day_choice = self.dialogue_choose(actor, "Which day should everyone meet?", "gathering", [
            ("1", "Tomorrow", "Hold the gathering on the next calendar day."),
            ("2", "In two days", "Give the guests more time to plan."),
            ("3", "In three days", "Schedule it farther ahead."),
            ("back", "Decide later", "Do not schedule the gathering."),
        ], transcript)
        if day_choice not in {"1", "2", "3"}:
            return True
        time_choice = self.dialogue_choose(actor, "When should it begin?", "gathering", [
            ("12", "Midday, 12:00", "A daytime visit or picnic."),
            ("17", "Late afternoon, 17:00", "A social visit after most work routines."),
            ("20", "Evening, 20:00", "A tavern gathering or house party."),
            ("back", "Decide later", "Do not schedule the gathering."),
        ], transcript)
        if time_choice not in {"12", "17", "20"}:
            return True

        due_day, due_hour = self.dialogue_absolute_day() + int(day_choice), int(time_choice)
        house_party = selected_venue == "town:farm"
        title = f"{'House gathering' if house_party else 'Group outing'} with {host_name}"
        event_id = f"social_gathering:{host_id}:{due_day}:{due_hour}"
        attendee_records = [actor, *invited]
        participants = []
        for attendee in attendee_records:
            attendee_kind = kind if str(attendee.get("id", "")) == host_id else self.world_dialogue_actor_kind(attendee)
            participants.append({
                "actor_id": str(attendee.get("id", "")),
                "name": self.dialogue_actor_name(attendee),
                "role": str(attendee.get("role", "Guest")),
                "kind": attendee_kind,
                "mode": "attend",
                "purpose": "hosting the gathering" if str(attendee.get("id", "")) == host_id else "attending the gathering",
                "destination": dict(destination),
            })
        event = self.schedule_planned_event({
            "id": event_id, "title": title, "kind": "social_gathering",
            "status": "planned", "auto_activate": True, "requires_attendance": True,
            "host_id": host_id, "house_party": house_party,
            "due_day": due_day, "due_hour": due_hour,
            "expires_at_minute": due_day * 1440 + (due_hour + 6) * 60,
            "destination": destination, "participants": participants,
        })
        for attendee, participant in zip(attendee_records, participants):
            attendee_kind = str(participant.get("kind", "authored"))
            slot = self.dialogue_social_slot(attendee, attendee_kind)
            slot["meetings"] = (list(slot.get("meetings", [])) + [{
                "day": due_day, "made_day": self.dialogue_absolute_day(),
                "purpose": "attend a house gathering" if house_party else "join a group outing",
                "event_id": event_id, "destination": dict(destination), "completed": False,
            }])[-6:]
        if hasattr(self, "autosave_with_message"):
            self.autosave_with_message(f"Planned {title.lower()}.")
        guests = ", ".join(str(person.get("name", "a guest")) for person in invited)
        return self.dialogue_say(
            actor,
            f"It is settled: {event['destination'].get('label', venue_row[1])}, in {int(day_choice)} day{'s' if day_choice != '1' else ''} at {due_hour:02d}. "
            f"I will make sure {guests} know where to be. Speak with any of us there when you are ready to bring everyone into the conversation.",
            "gathering", transcript,
        )

    def dialogue_handle_planned_gathering_arrival(
        self,
        actor: Dict[str, object],
        kind: str,
        event: Dict[str, object],
        participant: Dict[str, object],
    ) -> bool:
        transcript: List[Dict[str, str]] = []
        destination = dict(event.get("destination", {}) or {})
        place = str(destination.get("label", destination.get("location", "the gathering place")))
        attendee_rows = [row for row in event.get("participants", []) or [] if isinstance(row, dict)]
        attendees: List[Tuple[Dict[str, object], str]] = []
        for row in attendee_rows:
            attendee = self.temporary_participant_actor(row)
            attendees.append((attendee, str(row.get("kind", "authored"))))
        host_id = str(event.get("host_id", ""))
        host_pair = next(((attendee, attendee_kind) for attendee, attendee_kind in attendees if str(attendee.get("id", "")) == host_id), None)
        if host_pair is None:
            host_pair = (actor, kind)
        host, host_kind = host_pair
        narrator = {
            "id": f"gathering:{event.get('id', '')}", "name": "Narrator",
            "role": str(event.get("title", "Gathering")), "_dialogue_kind": "scene",
        }
        names = ", ".join(self.dialogue_actor_name(attendee) for attendee, _kind in attendees)
        if not self.dialogue_say(
            narrator,
            f"The guests arrive at {place}: {names}.",
            "arrival", transcript,
        ):
            return False
        if not self.dialogue_say(
            host,
            "I'm glad everyone made it. What should we talk about first?",
            "host", transcript,
        ):
            return False
        topic = self.dialogue_choose(host, "What brings the gathering together?", "group conversation", [
            ("local", "Exchange local news", "Share sourced observations from everyone's routines."),
            ("work", "Compare work and skills", "Discuss how the guests' responsibilities connect."),
            ("plans", "Make future plans", "Talk about routes, ambitions, and what everyone wants to do next."),
            ("stories", "Trade personal stories", "Let each guest contribute from their own background and personality."),
            ("back", "Not yet", "Leave the gathering active and return when ready."),
        ], transcript)
        if topic not in {"local", "work", "plans", "stories"}:
            return False
        for attendee, attendee_kind in attendees:
            if topic == "local":
                line = self.dialogue_chitchat(attendee, attendee_kind)
            elif topic == "work":
                line = self.dialogue_work_answer(attendee, attendee_kind, False)
            elif topic == "plans":
                line = f"Next, I need to finish {self.dialogue_activity(attendee, attendee_kind)}."
            else:
                line = self.dialogue_personal_story(attendee, attendee_kind)
            attendee["_dialogue_kind"] = attendee_kind
            try:
                if not self.dialogue_say(attendee, line, "group response", transcript):
                    return False
            finally:
                attendee.pop("_dialogue_kind", None)

        gains: Dict[str, int] = {}
        for attendee, attendee_kind in attendees:
            attendee_id = str(attendee.get("id", ""))
            gain = self.dialogue_adjust_actor_relationship(attendee, attendee_kind, 2 if attendee_id == host_id else 1)
            gains[attendee_id] = int(gain)
            self.dialogue_set_mood(attendee, attendee_kind, "grateful", f"the gathering at {place}", 1, 3)
        event["activity_choice"] = topic
        event["relationship_gains"] = gains
        event["outcome"] = f"The group shared {topic} at {place}."
        if bool(event.get("house_party", False)) and hasattr(self, "record_family_event"):
            self.record_family_event("House Gathering", f"Hosted {names} at home.")
        if hasattr(self, "add_hud_activity"):
            self.add_hud_activity(f"The gathering at {place} concluded after a shared conversation.", "social")
        self.dialogue_say(
            host,
            "Thank you for coming. We should do this again.",
            "farewell", transcript,
        )
        return True

    def dialogue_handle_practical_arrangement(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        people = self.dialogue_known_people(actor, kind)
        wilderness_places = [
            place for place in self.dialogue_known_places(actor, kind)
            if str(place.get("kind", "")) == "wilderness"
        ]
        navigable_places = [
            (place, self.quest_destination_for_known_place(place))
            for place in self.dialogue_known_places(actor, kind)
            if hasattr(self, "quest_destination_for_known_place")
        ]
        navigable_places = [(place, destination) for place, destination in navigable_places if destination]
        actor_id = str(actor.get("id", ""))
        follower_id = self.dialogue_follower_id_for_actor(actor)
        follower_already_active = bool(
            follower_id and hasattr(self, "active_travel_follower_ids")
            and follower_id in self.active_travel_follower_ids()
        )
        actor_schedule_overridden = bool(
            actor_id and hasattr(self, "temporary_participant_actor_ids")
            and actor_id in self.temporary_participant_actor_ids()
        )
        household = kind in {"spouse", "child"} or str(actor.get("id", "")).startswith(("spouse:", "child:"))
        options: List[DialogueOption] = []
        if people:
            options.extend([
                ("introduction", "Ask for an introduction", "The selected person will recognize who sent you when you first meet."),
                ("message", "Ask them to carry a message", "Information is added to the recipient's sourced knowledge instead of teleporting the recipient."),
            ])
        if wilderness_places:
            options.append(("map", "Ask them to mark a known place", "Adds reliable map knowledge for a place this speaker has actually visited."))
        options.append(("meeting", "Arrange another meeting", "Schedule a follow-up for tomorrow."))
        if (
            actor_id and kind != "child" and hasattr(self, "schedule_planned_event")
            and not follower_already_active and not actor_schedule_overridden
        ):
            options.append(("walk", "Spend some time together", "They pause their ordinary schedule and accompany you in the world for two hours."))
            relationship = int(self.town_npc_relationship(str(actor.get("id", "")))) if hasattr(self, "town_npc_relationship") else 0
            has_outing = bool(
                hasattr(self, "open_planned_events_for_actor")
                and self.open_planned_events_for_actor(str(actor.get("id", "")), ("social_outing",))
            )
            if relationship >= 20 and not has_outing:
                options.append(("social_outing", "Plan an outing together", "Choose a known destination, day, and time; meet there in the physical world."))
            known_guests = self.dialogue_known_people(actor, kind)
            has_gathering = bool(
                hasattr(self, "open_planned_events_for_actor")
                and self.open_planned_events_for_actor(str(actor.get("id", "")), ("social_gathering",))
            )
            if relationship >= 40 and known_guests and not has_gathering:
                options.append(("gathering", "Plan a house gathering or group outing", "Invite up to three people the speaker actually knows, then choose a venue and time."))
        if navigable_places and actor_id and not follower_already_active and not actor_schedule_overridden:
            options.append(("guide", "Ask them to guide you somewhere", "Creates a tracked journey; follow them to a place they genuinely know."))
        if follower_id and hasattr(self, "set_travel_follower") and not actor_schedule_overridden:
            options.append(("travel", "Ask them to travel with you", "Uses the existing follower eligibility, safety, and party-size rules."))
        if household and hasattr(self, "family_outing_menu"):
            options.append(("outing", "Plan a family outing", "Choose an activity and date with eligible family members."))
        options.append(("back", "Talk about something else", "Return to the conversation."))
        choice = self.dialogue_choose(actor, "What would you like to arrange?", "arrangement", options, transcript)
        if not choice or choice == "back":
            return True
        if choice in {"introduction", "message"}:
            person_options = [
                (str(person.get("id", person.get("name"))), str(person.get("name", "Someone")), str(person.get("role", "Known person")))
                for person in people
            ]
            person_options.append(("back", "Cancel", "Do not make an arrangement."))
            target_id = self.dialogue_choose(actor, "Who did you have in mind?", "arrangement", person_options, transcript)
            target = next(
                (person for person in people if str(person.get("id", person.get("name"))) == target_id),
                None,
            )
            if not isinstance(target, dict):
                return True
            target_kind = self.world_dialogue_actor_kind(target)
            if choice == "introduction":
                target_slot = self.dialogue_social_slot(target, target_kind)
                target_slot["introductions"] = (
                    list(target_slot["introductions"])
                    + [{
                        "source_id": str(actor.get("id", "")),
                        "source_name": self.dialogue_actor_name(actor),
                        "purpose": "that you wanted to meet me",
                        "day": self.dialogue_day_key(),
                        "acknowledged": False,
                    }]
                )[-8:]
                return self.dialogue_say(
                    actor,
                    f"I'll tell {self.dialogue_actor_name(target)} who you are and that I sent you. What they decide after that is theirs.",
                    "arrangement", transcript,
                )
            source_slot = self.dialogue_social_slot(actor, kind)
            packet = next(iter(reversed(source_slot["knowledge"])), None)
            message_text = (
                str(packet.get("text", ""))
                if isinstance(packet, dict)
                else f"{getattr(self.state, 'player_name', 'The player')} would like to speak about recent events near {self.world_dialogue_location_label()}."
            )
            self.dialogue_add_knowledge(
                target, target_kind, message_text,
                subject=str(packet.get("subject", "a delivered message")) if isinstance(packet, dict) else "a delivered message",
                source_name=f"{getattr(self.state, 'player_name', 'the player')}, through {self.dialogue_actor_name(actor)}",
                source_kind="message", confidence=85,
                knowledge_id=str(packet.get("id", "")) if isinstance(packet, dict) else "",
            )
            target_slot = self.dialogue_social_slot(target, target_kind)
            target_slot["initiation"] = {
                "reason": "delivered_message",
                "text": f"{self.dialogue_actor_name(actor)} delivered your message. I wanted to answer it directly.",
                "created_day": self.dialogue_absolute_day(), "called_out_day": 0,
                "acknowledged": False,
            }
            return self.dialogue_say(
                actor, f"I'll carry that to {self.dialogue_actor_name(target)} and make it clear which part came from you.",
                "arrangement", transcript,
            )
        if choice == "map":
            place_options = [
                (str(place["id"]), str(place["name"]), f"Region ({place.get('x', 0)},{place.get('y', 0)})")
                for place in wilderness_places
            ]
            place_options.append(("back", "Cancel", "Do not mark a place."))
            selected = self.dialogue_choose(actor, "Which place should they mark?", "arrangement", place_options, transcript)
            place = next((row for row in wilderness_places if str(row["id"]) == selected), None)
            if place:
                return self.dialogue_say(actor, self.dialogue_direction_answer(actor, place), "arrangement", transcript)
            return True
        if choice == "meeting":
            current_destination = self.quest_capture_current_destination()
            current_destination["label"] = "where you are standing now"
            meeting_places = [("__HERE__", "Meet here", current_destination)] + [
                (str(place.get("id")), str(place.get("name", "Known place")), destination)
                for place, destination in navigable_places[:12]
            ]
            meeting_options = [
                (place_id, label, str(destination.get("label", destination.get("location", "Known place"))))
                for place_id, label, destination in meeting_places
            ]
            meeting_options.append(("back", "Cancel", "Do not schedule the meeting."))
            meeting_choice = self.dialogue_choose(actor, "Where should you meet tomorrow?", "arrangement", meeting_options, transcript)
            selected_meeting = next((row for row in meeting_places if row[0] == meeting_choice), None)
            if selected_meeting is None:
                return True
            meeting_destination = dict(selected_meeting[2])
            meeting_hour = max(8, min(20, int(getattr(self.state, "hour", 10))))
            event_id = f"meeting:{actor.get('id')}:{self.dialogue_absolute_day() + 1}:{meeting_hour}"
            slot = self.dialogue_social_slot(actor, kind)
            slot["meetings"] = (list(slot["meetings"]) + [{
                "day": self.dialogue_absolute_day() + 1,
                "made_day": self.dialogue_absolute_day(),
                "purpose": "continue the current conversation",
                "event_id": event_id,
                "destination": meeting_destination,
                "completed": False,
            }])[-6:]
            self.schedule_planned_event({
                "id": event_id,
                "title": f"Meet {self.dialogue_actor_name(actor)}",
                "kind": "meeting", "status": "planned", "auto_activate": True,
                "due_day": self.dialogue_absolute_day() + 1,
                "due_hour": meeting_hour,
                "expires_at_minute": (self.dialogue_absolute_day() + 1) * 1440 + (meeting_hour + 8) * 60,
                "destination": meeting_destination,
                "participants": [{
                    "actor_id": str(actor.get("id", "")), "name": self.dialogue_actor_name(actor),
                    "role": str(actor.get("role", "Resident")), "kind": kind,
                    "mode": "meet", "purpose": "the meeting you arranged",
                    "destination": meeting_destination,
                }],
            })
            return self.dialogue_say(
                actor,
                f"Tomorrow around {meeting_hour:02d}:00, then. I will meet you at {meeting_destination.get('label', 'the agreed place')}.",
                "arrangement", transcript,
            )
        if choice == "walk":
            now_minute = (
                self.dialogue_absolute_day() * 1440
                + int(getattr(self.state, "hour", 0)) * 60
                + int(getattr(self.state, "minute", 0))
            )
            event = self.schedule_planned_event({
                "id": f"shared_time:{actor.get('id')}:{now_minute}",
                "title": f"Time with {self.dialogue_actor_name(actor)}",
                "status": "ready",
                "due_day": self.dialogue_absolute_day(),
                "due_hour": int(getattr(self.state, "hour", 0)),
                "expires_at_minute": now_minute + 120,
                "destination": self.quest_capture_current_destination(),
                "participants": [{
                    "actor_id": str(actor.get("id", "")),
                    "name": self.dialogue_actor_name(actor),
                    "role": str(actor.get("role", "Companion")),
                    "kind": kind,
                    "mode": "accompany",
                    "purpose": "spending time together",
                }],
            })
            self.activate_planned_event(str(event.get("id", "")))
            return self.dialogue_say(
                actor,
                "All right. I can set aside the next couple of hours. Lead the way, and we can talk while we go.",
                "arrangement", transcript,
            )
        if choice == "social_outing":
            return self.dialogue_schedule_shared_activity(actor, kind, transcript, romantic=False)
        if choice == "gathering":
            return self.dialogue_schedule_group_gathering(actor, kind, transcript)
        if choice == "guide":
            place_options = [
                (str(place.get("id")), str(place.get("name", "Known place")), str(destination.get("label", "Known destination")))
                for place, destination in navigable_places
            ]
            place_options.append(("back", "Cancel", "Do not begin a guided journey."))
            selected = self.dialogue_choose(actor, "Where would you like them to guide you?", "arrangement", place_options, transcript)
            selected_route = next(
                ((place, destination) for place, destination in navigable_places if str(place.get("id")) == selected),
                None,
            )
            if selected_route is None:
                return True
            place, destination = selected_route
            route_minute = (
                self.dialogue_absolute_day() * 1440
                + int(getattr(self.state, "hour", 0)) * 60
                + int(getattr(self.state, "minute", 0))
            )
            event_id = f"guided_route:{actor.get('id')}:{route_minute}"
            quest_id = f"quest:{event_id}"
            quest = self.register_quest({
                "id": quest_id,
                "title": f"Follow {self.dialogue_actor_name(actor)} to {place.get('name', 'the destination')}",
                "category": "Relationships",
                "description": f"Stay near {self.dialogue_actor_name(actor)} while they lead you to a place they know.",
                "giver_id": str(actor.get("id", "")), "giver_name": self.dialogue_actor_name(actor),
                "participants": [str(actor.get("id", ""))],
                "objectives": [{
                    "id": "guided_arrival", "kind": "escort", "target_id": event_id,
                    "target": 1, "current": 0,
                    "description": f"Follow {self.dialogue_actor_name(actor)} to {place.get('name', 'the destination')}.",
                    "destination": destination,
                }],
                "turn_in": destination,
                "rewards": {"relationship": 2},
                "journal": [f"{self.dialogue_actor_name(actor)} agreed to guide you."],
            }, accept=True)
            self.track_quest(str(quest.get("id", quest_id)), announce=False)
            event = self.schedule_planned_event({
                "id": event_id, "title": f"Guided journey with {self.dialogue_actor_name(actor)}",
                "kind": "guided_journey", "status": "ready", "quest_id": quest_id,
                "requires_attendance": True, "player_manageable": True,
                "persistent_until_resolved": True,
                "due_day": self.dialogue_absolute_day(), "due_hour": int(getattr(self.state, "hour", 0)),
                "destination": destination,
                "participants": [{
                    "actor_id": str(actor.get("id", "")), "name": self.dialogue_actor_name(actor),
                    "role": str(actor.get("role", "Guide")), "kind": kind,
                    "mode": "guide", "purpose": f"guiding you to {place.get('name', 'the destination')}",
                    "destination": destination,
                }],
            })
            self.activate_planned_event(str(event.get("id", event_id)))
            return self.dialogue_say(
                actor,
                f"I know the way to {place.get('name', 'that place')}. Stay close, and I'll stop when we get there.",
                "arrangement", transcript,
            )
        if choice == "travel":
            success = bool(self.set_travel_follower(follower_id))
            response = (
                "All right. We travel together from here, and we can revise the plan if the road changes."
                if success else str(getattr(self.state, "message", "I cannot travel with you right now."))
            )
            return self.dialogue_say(actor, response, "arrangement", transcript)
        if choice == "outing":
            result = self.family_outing_menu()
            response = (
                "Good. I'll keep that time free."
                if result and str(result) != "__BACK__"
                else "We can leave the outing undecided for now."
            )
            return self.dialogue_say(actor, response, "household", transcript)
        return True

    def dialogue_handle_group_topic(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        partner_row = actor.get("_dialogue_group_partner", {})
        if not isinstance(partner_row, dict):
            return True
        partner = partner_row.get("actor", {})
        if not isinstance(partner, dict):
            return True
        partner_kind = str(partner_row.get("kind", "authored"))
        choice = self.dialogue_choose(actor, "What do you ask the group?", "group conversation", [
            ("local", "What has changed around here?", "Each speaker answers from their own routine and knowledge."),
            ("work", "How is everyone's work connected?", "Compare current activities and responsibilities."),
            ("plans", "What is everyone doing next?", "Hear immediate plans rather than personal secrets."),
            ("back", "Return to the conversation", "Address the original speaker again."),
        ], transcript)
        if not choice or choice == "back":
            return True
        if choice == "local":
            first_line = self.dialogue_chitchat(actor, kind)
            second_line = self.dialogue_chitchat(partner, partner_kind)
        elif choice == "work":
            first_line = self.dialogue_work_answer(actor, kind, False)
            second_line = self.dialogue_work_answer(partner, partner_kind, False)
        else:
            first_line = f"My next concern is {self.dialogue_activity(actor, kind)}."
            second_line = f"My own route has me {self.dialogue_activity(partner, partner_kind)}."
        if not self.dialogue_say(actor, first_line, "group response", transcript):
            return False
        partner["_dialogue_kind"] = partner_kind
        try:
            return self.dialogue_say(partner, second_line, "group response", transcript)
        finally:
            partner.pop("_dialogue_kind", None)

    def dialogue_nearby_group_partner(
        self, actor: Dict[str, object], kind: str
    ) -> Dict[str, object]:
        if not hasattr(self, "world_dialogue_nearby_actors"):
            return {}
        actor_id = str(actor.get("id") or actor.get("name") or "")
        candidates = []
        for row in self.world_dialogue_nearby_actors(radius=5):
            other = row.get("actor", {})
            if not isinstance(other, dict):
                continue
            other_id = str(other.get("id") or other.get("name") or "")
            if other_id == actor_id or int(row.get("distance", 99) or 99) > 5:
                continue
            candidates.append(row)
        return candidates[0] if candidates else {}

    def dialogue_romance_stage(self, actor: Dict[str, object]) -> str:
        actor_id = str(actor.get("id", "") or "")
        if actor_id and actor_id == str(getattr(self.state, "spouse_npc_id", "") or ""):
            return "married"
        if actor_id and actor_id == str(getattr(self.state, "engaged_npc_id", "") or ""):
            return "engaged"
        if actor_id in set(getattr(self.state, "dating_npc_ids", []) or []):
            return "dating"
        return "interest"

    def dialogue_child_stage(self, actor: Dict[str, object]) -> str:
        if hasattr(self, "household_child_stage"):
            try:
                return str(self.household_child_stage(actor))
            except (TypeError, ValueError):
                pass
        return str(actor.get("role", actor.get("age_group", "Child")) or "Child")

    def dialogue_spouse_stage(self) -> str:
        """Which phase of marriage the player's household is in.

        The wedding is stored as calendar parts, so rebuild it on the same
        112-day year dialogue_absolute_day uses.
        """
        state = self.state
        children = [
            child for child in (getattr(state, "children", []) or [])
            if isinstance(child, dict)
        ]
        try:
            married_year = int(getattr(state, "marriage_year", 0) or 0)
        except (TypeError, ValueError):
            married_year = 0
        years_married = 0.0
        if married_year > 0:
            month = max(1, int(getattr(state, "marriage_month", 1) or 1))
            day = max(1, int(getattr(state, "marriage_day", 1) or 1))
            # Both endpoints must come off the same calendar, so mirror the
            # choice dialogue_absolute_day makes: the real 365-day year when the
            # game exposes it, its 112-day approximation otherwise.
            if hasattr(self, "absolute_game_day"):
                married_on = int(self.absolute_game_day(month, day, married_year))
                year_length = 365.0
            else:
                married_on = max(0, married_year - 1) * 112 + (month - 1) * 28 + day
                year_length = 112.0
            years_married = max(
                0.0, (self.dialogue_absolute_day() - married_on) / year_length
            )
        # a grown child still counts as family but no longer sets the household's
        # daily shape, so an emptier house gets its own voice
        dependents = sum(
            1 for child in children
            if child_stage_group(str(child.get("stage", "Child"))) != "adult"
        )
        return spouse_stage_group(years_married, len(children), dependents)

    def dialogue_household_content_context(
        self, actor: Dict[str, object], kind: str
    ) -> Dict[str, object]:
        children = [
            child for child in (getattr(self.state, "children", []) or [])
            if isinstance(child, dict)
        ]
        child_names = [str(child.get("name", "the children")) for child in children]
        family_state = getattr(self.state, "family_world_state", {}) or {}
        history = family_state.get("outing_history", []) if isinstance(family_state, dict) else []
        latest_memory = history[-1] if history and isinstance(history[-1], dict) else {}
        memory = str(
            latest_memory.get("type")
            or latest_memory.get("destination")
            or "the last day we all made time for one another"
        )
        focus = "what interests you"
        if kind == "child" and hasattr(self, "child_top_learning_topic"):
            try:
                focus = str(self.child_top_learning_topic(actor)[0] or focus)
            except (TypeError, ValueError):
                pass
        priority = (
            str(self.family_weekly_priority())
            if hasattr(self, "family_weekly_priority")
            else "Togetherness"
        )
        home = (
            str(self.family_household_home_label())
            if hasattr(self, "family_household_home_label")
            else str(actor.get("home_name", actor.get("home", "our home")) or "our home")
        )
        properties = len(getattr(self.state, "player_properties", {}) or {})
        return {
            "activity": self.dialogue_activity(actor, kind).replace("their ", "my "),
            "children": name_list(child_names) if child_names else "the children",
            "child_count": len(children),
            # a household with one child still speaks about that child
            "children_are": quantity_agreement(len(children), "is", "are"),
            "children_have": quantity_agreement(len(children), "has", "have"),
            "focus": focus,
            "focus_lower": focus.lower(),
            "home": home,
            "memory": memory,
            "money": int(getattr(self.state, "money", 0) or 0),
            "player": str(getattr(self.state, "player_name", "you")),
            "priority": priority,
            "priority_lower": priority.lower(),
            "property_count": properties,
            "property_label": quantity_agreement(properties, "property", "properties"),
            "season": str(getattr(self.state, "season", "Spring")),
            "weather": str(getattr(self.state, "weather", "Clear")),
            "weather_lower": str(getattr(self.state, "weather", "Clear")).lower(),
        }

    def dialogue_handle_flirt(
        self,
        actor: Dict[str, object],
        kind: str,
        transcript: List[Dict[str, str]],
    ) -> bool:
        stage = self.dialogue_romance_stage(actor)
        relationship = self.dialogue_relationship_points(actor, kind)
        options: List[DialogueOption] = [
            (
                "playful",
                "You are becoming a very distracting part of my day.",
                "Tease them and let the attraction remain light on its feet.",
            ),
            (
                "admiring",
                "I hope you know how attractive you are when you care deeply about something.",
                "Offer mature admiration rooted in who they are.",
            ),
        ]
        if stage in {"dating", "engaged", "married"} or relationship >= 60:
            options.append((
                "direct",
                "I've been wanting to kiss you.",
                "Be direct only after enough familiarity or an established romance.",
            ))
        if stage in {"dating", "engaged", "married"}:
            options.append((
                "private",
                "Later, when we have some privacy, I want you all to myself for a while.",
                "Suggest private time together without making the conversation explicit.",
            ))
        options.append(("back", "Perhaps another time.", "Return without flirting."))
        courted = pronouns_for_sex(self.npc_sex(actor) if hasattr(self, "npc_sex") else "")
        style = self.dialogue_choose(
            actor, f"How do you flirt with {courted['object']}?", "flirting", options, transcript,
        )
        if not style or style == "back":
            return True

        slot = self.dialogue_social_slot(actor, kind)
        today = self.dialogue_absolute_day()
        history = [row for row in slot.get("flirt_history", []) or [] if isinstance(row, dict)]
        demeanor = self.dialogue_demeanor(actor, kind)
        current = relationship
        if current < 0 and stage == "interest":
            response = _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:flirt-boundary",
                (
                    "No. Whatever you intended, that familiarity is not welcome from you.",
                    "You are mistaking access to a conversation for intimacy. Do not.",
                    "I am not interested in being flirted with by someone I do not currently trust.",
                    "Keep this respectful. I have given you no reason to assume I want that attention.",
                ),
            )
        else:
            response = romance_flirt_response(
                stage,
                style,
                demeanor,
                f"{self.dialogue_day_key()}:{actor.get('id')}:{style}:{len(history)}",
                self.dialogue_kinship_context(actor),
            )
        first_today = int(slot.get("last_flirt_day", -1) or -1) != today
        relationship_gain = 0
        if first_today:
            if stage != "interest" or current >= 25:
                relationship_gain = self.dialogue_adjust_actor_relationship(
                    actor, kind, 2 if stage in {"dating", "engaged", "married"} else 1,
                )
            slot["last_flirt_day"] = today
            if stage == "married":
                self.state.family_bond = min(
                    999, int(getattr(self.state, "family_bond", 0) or 0) + 1
                )
        history.append({
            "day": today,
            "stage": stage,
            "style": style,
            "response": response,
            "relationship_gain": int(relationship_gain),
        })
        slot["flirt_history"] = history[-12:]
        self.dialogue_set_mood(actor, kind, "excited", "the attraction between you", 2, 2)
        if relationship_gain and hasattr(self, "add_hud_activity"):
            self.add_hud_activity(
                f"Relationship with {self.dialogue_actor_name(actor)} {relationship_gain:+}.",
                "social",
            )
        return self.dialogue_say(actor, response, "flirting", transcript)

    def dialogue_handle_child_household_topic(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        stage = self.dialogue_child_stage(actor)
        baby = stage in {"Newborn", "Infant"}
        options: List[DialogueOption] = [
            ("day", "Spend a quiet moment together" if baby else "How was your day?", "Listen to what the day felt like from their stage of life."),
            ("home", "Settle them at home" if baby else "How do you feel about home?", "Talk about comfort, privacy, rooms, and belonging."),
            ("family", "Talk about the family", "Let them describe the household in their own terms."),
            ("worry", "Comfort them" if baby else "Is anything worrying you?", "Make room for a concern without turning it immediately into a lesson."),
            ("wish", "What do you want?", "Ask about an immediate wish or a longer-term hope."),
            ("memory", "Remember something together", "Draw from the household's shared history."),
            ("back", "Talk about something else", "Return to the conversation."),
        ]
        choice = self.dialogue_choose(actor, "What do you talk about together?", "family", options, transcript)
        if not choice or choice == "back":
            return True
        line = child_household_line(
            stage,
            choice,
            self.dialogue_household_content_context(actor, kind),
            f"{self.dialogue_day_key()}:{actor.get('id')}:{choice}",
        )
        slot = self.dialogue_social_slot(actor, kind)
        today = self.dialogue_absolute_day()
        if int(slot.get("last_household_checkin_day", -1) or -1) != today:
            slot["last_household_checkin_day"] = today
            gained = self.dialogue_adjust_actor_relationship(actor, kind, 1)
            if gained and hasattr(self, "add_hud_activity"):
                self.add_hud_activity(
                    f"Bond with {self.dialogue_actor_name(actor)} {gained:+}.", "social"
                )
        return self.dialogue_say(actor, line, "family", transcript)

    def dialogue_handle_household_topic(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        if kind == "child":
            return self.dialogue_handle_child_household_topic(actor, kind, transcript)
        actor_id = str(actor.get("id", ""))
        is_spouse = kind == "spouse" or actor_id == str(getattr(self.state, "spouse_npc_id", "") or "")
        options: List[DialogueOption] = [
            ("plans", "Compare today's plans", "Talk through routines, assigned work, and who expects to be home."),
            ("home", "Talk about the life you're building", "Discuss the shared home as a relationship rather than a property report."),
            ("needs", "Ask what they need from you", "Invite an honest answer without choosing their solution for them."),
            ("affection", "Make a little time for each other", "Share ordinary affection without waiting for a milestone."),
            ("safety", "Talk about safety and travel", "Discuss active danger, expeditions, and time away from home."),
            ("finances", "Review household finances", "Discuss current money, property, and the pressure of future plans."),
            ("memory", "Recall something you shared", "Draw from recorded outings and family history."),
            ("outing", "Plan time together", "Choose an outing, destination, participants, and date."),
            ("dashboard", "Review the household together", "Open the household dashboard from inside the conversation."),
            ("meal", "Suggest eating together", "Gather the available household around a usable table."),
        ]
        if is_spouse and getattr(self.state, "children", None):
            options.insert(4, ("children", "Talk about the children", "Compare what each of you has noticed and what the children may need."))
        if is_spouse and bool(getattr(self.state, "pregnancy_active", False)):
            options.append(("pregnancy", "Check in about the pregnancy", "Discuss the current month and household preparations."))
        if is_spouse and bool(getattr(self.state, "spouse_moved_to_farm", False)):
            options.append(("support", "Reconsider how you support each other", "Review the spouse's current household support role."))
        options.append(("back", "Talk about something else", "Return to the conversation."))
        choice = self.dialogue_choose(actor, "What should the household discuss?", "household", options, transcript)
        if not choice or choice == "back":
            return True
        household_context = self.dialogue_household_content_context(actor, kind)
        if choice in {"plans", "home", "needs", "affection", "children", "safety", "finances", "memory"}:
            line = spouse_household_line(
                choice,
                household_context,
                f"{self.dialogue_day_key()}:{actor.get('id')}:{choice}",
                self.dialogue_spouse_stage(),
            )
            if choice == "safety":
                self.dialogue_set_mood(actor, kind, "worried", "the danger surrounding your travels", 1, 2)
        elif choice == "outing":
            result = self.family_outing_menu() if hasattr(self, "family_outing_menu") else None
            line = "The plan is on our calendar now." if result and str(result) != "__BACK__" else "We can decide on the outing later."
        elif choice == "dashboard":
            result = self.family_world_dashboard_menu() if hasattr(self, "family_world_dashboard_menu") else None
            line = "Everything looks manageable for now." if result != "changed" else "Good. The new plan should work better."
        elif choice == "meal":
            result = self.family_meal_menu() if hasattr(self, "family_meal_menu") else None
            line = "I'm glad we ate together." if result == "changed" else str(getattr(self.state, "message", "We can eat together another time."))
        elif choice == "pregnancy":
            changed = bool(self.complete_pregnancy_checkup(actor)) if hasattr(self, "complete_pregnancy_checkup") else False
            line = "The checkup went well. Thank you for coming with me." if changed else f"The pregnancy is in month {self.pregnancy_month_number()}; the due date is {self.pregnancy_due_date_label()}."
        else:
            result = self.spouse_support_menu() if hasattr(self, "spouse_support_menu") else None
            line = "The new arrangement should help." if result == "changed" else "We can keep the current arrangement for now."
        slot = self.dialogue_social_slot(actor, kind)
        today = self.dialogue_absolute_day()
        if int(slot.get("last_household_checkin_day", 0) or 0) != today:
            slot["last_household_checkin_day"] = today
            gained = self.dialogue_adjust_actor_relationship(actor, kind, 1)
            if gained and hasattr(self, "add_hud_activity"):
                self.add_hud_activity(
                    f"Relationship with {self.dialogue_actor_name(actor)} {gained:+}.", "social"
                )
        return self.dialogue_say(actor, line, "household", transcript)

    def dialogue_handle_wedding_plan(
        self,
        actor: Dict[str, object],
        transcript: List[Dict[str, str]],
    ) -> bool:
        if not hasattr(self, "ensure_family_world_state"):
            return self.dialogue_say(actor, "We can look at the calendar together later.", "wedding", transcript)
        plan = self.ensure_family_world_state()["wedding_plan"]
        topic = self.dialogue_choose(
            actor,
            "What part of the wedding do you want to decide together?",
            "wedding planning",
            [
                ("review", "Review what we have planned", "Hear the current date, venue, style, and guest plan."),
                ("venue", "Choose where the ceremony happens", str(plan.get("venue", "Town Hall"))),
                ("style", "Choose the character of the day", str(plan.get("style", "Community"))),
                ("guest_focus", "Choose who should be invited", str(plan.get("guest_focus", "Friends and family"))),
                ("back", "Leave the plan as it is", "Return to the conversation."),
            ],
            transcript,
        )
        if not topic or topic == "back":
            return True
        if topic == "review":
            return self.dialogue_say(
                actor,
                f"We marry on {self.wedding_date_label()} at {plan.get('venue', 'Town Hall')}. "
                f"We chose a {str(plan.get('style', 'Community')).lower()} ceremony with "
                f"{str(plan.get('guest_focus', 'friends and family')).lower()}.",
                "wedding planning",
                transcript,
            )
        option_rows = {
            "venue": [
                ("Town Hall", "Town Hall", "A civil ceremony centered on the town and household ledger."),
                ("Farm Meadow", "Farm meadow", "An open ceremony among the land and work you are building."),
                ("Lakeside", "Lakeside", "A quieter ceremony beside the water."),
                ("Wayside Pavilion", "Wayside pavilion", "A small ceremony at a restored roadside structure."),
            ],
            "style": [
                ("Intimate", "Keep it intimate", "A restrained ceremony focused on the couple and immediate household."),
                ("Community", "Make it a community occasion", "Friends, neighbors, shared food, and a public reception."),
                ("Adventurous", "Let it reflect our travels", "A less formal day shaped by roads, weather, and shared experience."),
            ],
            "guest_focus": [
                ("Immediate household", "Invite the immediate household", "Keep the gathering small."),
                ("Friends and family", "Invite friends and family", "Bring close relationships into the ceremony."),
                ("Whole town", "Invite the whole town", "Make the wedding a broad public occasion."),
            ],
        }
        selection = self.dialogue_choose(
            actor,
            "Which choice feels right to you?",
            "wedding planning",
            [*option_rows.get(topic, []), ("back", "Keep the current choice", "Return without changing the plan.")],
            transcript,
        )
        if not selection or selection == "back":
            return True
        plan[topic] = selection
        if hasattr(self, "record_family_event"):
            self.record_family_event("Wedding Plan", f"You and {self.dialogue_actor_name(actor)} chose {selection} for the wedding.")
        if hasattr(self, "autosave_with_message"):
            self.autosave_with_message(f"Wedding plan updated: {selection}.")
        responses = {
            "venue": f"Then we will marry at {selection}. I want the place to feel like part of our story, not a backdrop.",
            "style": f"A {selection.lower()} day feels right. We can make the details serve that choice.",
            "guest_focus": f"Then we invite {selection.lower()}. I want everyone there to understand why they are part of the day.",
        }
        return self.dialogue_say(actor, responses[topic], "wedding planning", transcript)

    def dialogue_handle_relationship_topic(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        actor_id = str(actor.get("id", ""))
        supported = bool(
            actor_id
            and (
                kind in {"authored", "procedural", "spouse"}
                or self.dialogue_is_persistent_world_actor(actor, kind)
            )
            and hasattr(self, "town_npc_relationship")
        )
        if not supported:
            return self.dialogue_say(
                actor,
                "We have not spent enough time together to define this friendship yet.",
                "relationship", transcript,
            )
        relationship = int(self.town_npc_relationship(actor_id))
        marriageable = bool(hasattr(self, "is_marriageable_npc") and self.is_marriageable_npc(actor))
        heterosexual_match = bool(
            hasattr(self, "is_heterosexual_match_for_player")
            and self.is_heterosexual_match_for_player(actor)
        )
        romance_allowed = bool(marriageable and heterosexual_match)
        is_spouse = actor_id == str(getattr(self.state, "spouse_npc_id", "") or "")
        is_engaged = actor_id == str(getattr(self.state, "engaged_npc_id", "") or "")
        is_dating = actor_id in set(getattr(self.state, "dating_npc_ids", []) or [])
        romantic_context = bool(romance_allowed and (is_spouse or is_engaged or is_dating))
        conversations = int(
            getattr(self.state, "town_npc_dialogue_counts", {}).get(
                actor_id, actor.get("conversations", 0)
            ) or 0
        )
        can_flirt = bool(
            romance_allowed
            and (
                romantic_context
                or (
                    relationship >= RELATIONSHIP_DATING_REQUIRED_FRIENDSHIP
                    and conversations >= RELATIONSHIP_DATING_REQUIRED_TALKS
                )
            )
        )
        gifted_today = getattr(self.state, "town_npc_last_gift_day", {}).get(actor_id) == self.town_npc_day_key()
        bond_word = "relationship" if romantic_context else "friendship"
        options: List[DialogueOption] = [
            ("status", f"Ask how they see your {bond_word}", "Discuss the current bond and what would naturally deepen it."),
        ]
        if can_flirt:
            options.append((
                "flirt",
                "Flirt with them",
                "Choose a playful, admiring, direct, or established-partner approach; responses reflect the relationship stage.",
            ))
        if not gifted_today:
            options.append(("gift", "Offer them a gift", "Choose one carried item and return to the conversation afterward."))
        court_ok, _court_reason = self.can_court_town_npc(actor) if romance_allowed else (False, "")
        has_planned_date = bool(
            hasattr(self, "open_planned_events_for_actor")
            and self.open_planned_events_for_actor(actor_id, ("relationship_date",))
        )
        if court_ok and not has_planned_date:
            label = "Plan a date together" if is_spouse or actor_id in set(self.state.dating_npc_ids or []) else "Invite them on a personal outing"
            options.append(("courtship", label, "Choose a destination, day, and time; courtship advances only after you meet there."))
        proposal_ok, _proposal_reason = self.can_propose_to_town_npc(actor) if romance_allowed else (False, "")
        if proposal_ok:
            options.append(("proposal", "Propose marriage", "Offer your wedding ring and choose a ceremony date."))
        if is_engaged:
            options.append(("wedding", "Discuss the wedding", f"Currently scheduled for {self.wedding_date_label()}."))
        if is_spouse:
            move_ok, _move_reason = self.can_invite_spouse_to_farm(actor)
            if move_ok:
                options.append(("move_in", "Ask them to share your home", "Form a shared household while they retain their own work and identity."))
            options.append(("family", "Discuss children and family planning", "Open the existing pregnancy and family-planning decisions in context."))
            scene_key, scene_title = self.available_marriage_scene(actor)
            if scene_key:
                options.append(("marriage_scene", "Talk about something happening in your marriage", str(scene_title)))
        options.append(("back", "Talk about something else", "Return to the conversation."))
        choice = self.dialogue_choose(actor, f"What do you want to discuss about your {bond_word}?", "relationship", options, transcript)
        if not choice or choice == "back":
            return True
        if choice == "status":
            friendship = self.town_npc_friendship_label(relationship)
            planned_dates = self.open_planned_events_for_actor(actor_id, ("relationship_date",)) if hasattr(self, "open_planned_events_for_actor") else []
            readiness = ""
            if planned_dates:
                plan = planned_dates[0]
                destination = dict(plan.get("destination", {}) or {})
                readiness = (
                    f" We already have {str(plan.get('title', 'time together')).lower()} planned at "
                    f"{destination.get('label', destination.get('location', 'the agreed place'))}."
                )
            if romantic_context:
                relationship_line = romance_status_line(
                    self.dialogue_romance_stage(actor),
                    {
                        "friendship": friendship,
                        "friendship_lower": friendship.lower(),
                        "planned": readiness,
                        **self.dialogue_kinship_context(actor),
                    },
                    f"{self.dialogue_day_key()}:{actor_id}:relationship-status",
                )
            else:
                tier = (
                    self.relationship_tier_for_npc(actor)
                    if hasattr(self, "relationship_tier_for_npc")
                    else "Stranger"
                )
                friendship_lines = {
                    "Stranger": (
                        "We have only just met. I am still learning what kind of person you are.",
                        "I know your name, but not enough about you to call this a friendship yet.",
                        "This is still an introduction, really. We can see where ordinary conversation takes us.",
                    ),
                    "Acquaintance": (
                        "I would call us acquaintances. We know enough to speak comfortably, but there is still plenty we have not shared.",
                        "We are getting to know one another. I recognize you now, and I am interested in hearing more.",
                        "You are becoming a familiar face. That is a good beginning, but it is still a beginning.",
                    ),
                    "Friend": (
                        "I think of you as a friend. I enjoy our conversations and trust you with the ordinary parts of my day.",
                        "We have become friends. You have shown up often enough that seeing you no longer feels accidental.",
                        "I am glad we became friends. We know one another well enough for the conversation to feel easy now.",
                    ),
                    "Close Friend": (
                        "You are a close friend. We have enough shared history that I trust you with things I do not tell everyone.",
                        "Our friendship means a great deal to me now. That comes from what we have actually been through together.",
                        "I consider you one of my closest friends. You earned that place slowly, which is why I trust it.",
                    ),
                }
                if tier in {"Dating", "Engaged", "Spouse"}:
                    tier = "Close Friend"
                relationship_line = _stable_pick(
                    f"{self.dialogue_day_key()}:{actor_id}:platonic-status:{tier}",
                    friendship_lines.get(tier, friendship_lines["Stranger"]),
                ) + readiness
            next_step = ""
            if romance_allowed and not is_spouse:
                if not is_dating and not is_engaged:
                    dating_ok, dating_reason = self.can_start_dating_with_npc(actor)
                    if not dating_ok and any(char.isdigit() for char in dating_reason):
                        next_step = dating_reason
                    elif not dating_ok:
                        court_ok, court_reason = self.can_court_town_npc(actor)
                        if not court_ok and any(char.isdigit() for char in court_reason):
                            next_step = court_reason
                elif not is_engaged:
                    proposal_ok, proposal_reason = self.can_propose_to_town_npc(actor)
                    if not proposal_ok and any(char.isdigit() for char in proposal_reason):
                        next_step = proposal_reason
            if next_step:
                relationship_line = f"{relationship_line} [{next_step}]"
            return self.dialogue_say(
                actor,
                relationship_line,
                "relationship", transcript,
            )
        if choice == "flirt":
            return self.dialogue_handle_flirt(actor, kind, transcript)
        if choice == "gift":
            success = bool(
                self.procedural_town_resident_gift_menu(actor)
                if kind == "procedural" and hasattr(self, "procedural_town_resident_gift_menu")
                else self.give_gift_to_town_npc(actor)
            )
            response = (
                "Thank you. I'll remember this."
                if success else str(getattr(self.state, "message", "We can leave the gift for another time."))
            )
            return self.dialogue_say(actor, response, "relationship", transcript)
        if choice == "courtship":
            return self.dialogue_schedule_shared_activity(actor, kind, transcript, romantic=True)
        if choice == "proposal":
            confirmation = self.dialogue_choose(actor, "This will use your wedding ring and require a ceremony date. Continue?", "relationship", [
                ("yes", "Ask them to marry you", "Make the proposal now."),
                ("back", "Not yet", "Return without changing the relationship."),
            ], transcript)
            if confirmation != "yes":
                return True
            if not self.dialogue_say(
                self.dialogue_player_speaker(),
                f"{self.dialogue_actor_name(actor)}, will you marry me?",
                "you", transcript,
            ):
                return False
            success = bool(self.propose_to_town_npc(actor, present=False))
            response = (
                f"Yes. I want to build that life with you. We will marry on {self.wedding_date_label()}."
                if success else str(getattr(self.state, "message", "I cannot answer that proposal now."))
            )
            return self.dialogue_say(actor, response, "relationship", transcript)
        if choice == "wedding":
            return self.dialogue_handle_wedding_plan(actor, transcript)
        if choice == "move_in":
            success = bool(self.invite_spouse_to_farm(actor))
            response = (
                "Yes. I'd like to make the farmhouse our home."
                if success else str(getattr(self.state, "message", "We cannot change households right now."))
            )
            return self.dialogue_say(actor, response, "relationship", transcript)
        if choice == "family":
            self.family_planning_menu(actor)
            return self.dialogue_say(actor, "I'm glad we talked about it together.", "relationship", transcript)
        if choice == "marriage_scene":
            success = bool(self.play_marriage_scene(actor))
            return self.dialogue_say(
                actor,
                "I'm glad we stopped and acknowledged what was happening between us."
                if success else "There is nothing urgent between us that needs a separate moment right now.",
                "relationship", transcript,
            )
        return True

    def dialogue_topic_answer(
        self, actor: Dict[str, object], kind: str, topic: str,
        transcript: List[Dict[str, str]],
    ) -> Optional[str]:
        if topic == "arrangements":
            self.dialogue_handle_practical_arrangement(actor, kind, transcript)
            return None
        if topic == "relationship":
            self.dialogue_handle_relationship_topic(actor, kind, transcript)
            return None
        if topic == "thread":
            self.dialogue_handle_thread(
                actor, kind, self.dialogue_current_thread(actor, kind, create=False), transcript
            )
            return None
        if topic == "group":
            self.dialogue_handle_group_topic(actor, kind, transcript)
            return None
        if topic == "household":
            self.dialogue_handle_household_topic(actor, kind, transcript)
            return None
        if topic == "background":
            return self.dialogue_background_answer(actor, kind)
        if topic == "past":
            return self.dialogue_personal_history_answer(actor, kind)
        if topic == "ambition":
            return self.dialogue_ambition_answer(actor, kind)
        if topic == "private":
            return self.dialogue_private_answer(actor, kind)
        if topic == "family":
            return self.dialogue_family_answer(actor, kind)
        if topic == "interests":
            return self.dialogue_interest_answer(actor)
        if topic == "companions":
            return self.dialogue_companion_answer(actor)
        if topic == "player":
            self.dialogue_handle_player_disclosure(actor, kind, transcript)
            return None
        if topic == "smalltalk":
            self.dialogue_handle_smalltalk(actor, kind, transcript)
            return None
        if topic == "work":
            choice = self.dialogue_choose(actor, "What would you like to know about their work?", "questions", [
                ("job", "What do you do?", "Ask about their profession and current responsibilities."),
                ("opportunities", "Do you have any work for me?", "Ask what work this person genuinely needs done."),
                ("back", "Ask about something else", "Return to the conversation."),
            ], transcript)
            if choice == "job":
                return self.dialogue_work_answer(actor, kind, False)
            if choice == "opportunities":
                self.dialogue_handle_work_situation(actor, kind, transcript)
                return None
            return None
        if topic == "directions":
            places = self.dialogue_known_places(actor, kind)
            if not places:
                return _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:no-places",
                (
                    "I don't know the surrounding places well enough to direct you responsibly.",
                    "I do not know the country around here well enough to send you anywhere with confidence.",
                    "I would only be guessing at directions, and a bad guess costs you a day.",
                    "Ask someone who travels more than I do. I would steer you wrong.",
                ),
            )
            options = [(str(place["id"]), str(place["name"]), str(place.get("district", "A place they know"))) for place in places]
            options.append(("back", "Ask about something else", "Return to the conversation."))
            selected = self.dialogue_choose(actor, "Where are you trying to go?", "questions", options, transcript)
            place = next((value for value in places if str(value["id"]) == selected), None)
            return self.dialogue_direction_answer(actor, place) if place else None
        if topic == "people":
            people = self.dialogue_known_people(actor, kind)
            if not people:
                return _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:no-people",
                (
                    "I don't know anyone here well enough to tell you much about them.",
                    "I do not know people here well enough to say anything worth repeating.",
                    "I could not tell you much about anyone without inventing it.",
                    "I keep to myself more than is useful for a question like that.",
                ),
            )
            options = [(str(person.get("id", person.get("name"))), str(person.get("name", "Someone")), str(person.get("role", "Someone they know"))) for person in people]
            options.append(("back", "Ask about someone else later", "Return to the conversation."))
            selected = self.dialogue_choose(actor, "Who did you want to ask about?", "questions", options, transcript)
            person = next((value for value in people if str(value.get("id", value.get("name"))) == selected), None)
            if person:
                role = self.dialogue_actor_role(person).lower()
                article = "an" if role[:1] in "aeiou" else "a"
                return f"I know {person.get('name', 'them')} through family or work. They work as {article} {role}."
            return None
        return None

    def dialogue_farewell(self, actor: Dict[str, object], kind: str) -> str:
        if self.dialogue_is_family_or_companion(actor, kind):
            return ""
        tier = self.dialogue_familiarity_label(actor, kind)
        demeanor = self.dialogue_demeanor(actor, kind)
        if tier in {"Close", "Trusted"}:
            close_pools = {
                "warm": (
                    "I'm glad you stopped. Take care.", "Come back when you have more time.",
                    "That was worth the interruption. Go safely.",
                    "Do not leave it so long next time.",
                ),
                "blunt": (
                    "Good talk. You know where to find me.", "That was useful. Take care.",
                    "Right. Off you go.", "We are done, and that is a compliment.",
                ),
                "reserved": (
                    "Thank you for coming by. I mean that.", "I'll see you again.",
                    "I appreciated that. Go on, then.", "That was a good while. Quietly said.",
                ),
                "skeptical": (
                    "You gave me something to think about. Take care.",
                    "We can continue this when we know more.",
                    "You have earned some benefit of the doubt. Take care.",
                    "I will think on it. Go on.",
                ),
            }
            return _cycling_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:farewell:close:{demeanor}",
                close_pools.get(demeanor, (
                    "Take care. I mean that.",
                    "We'll continue this another time.",
                    "That deserves more thought than I can give it standing here.",
                    "Go safely. We are not finished talking.",
                )),
                actor.get("dialogue_count", 0),
            )
        pools = {
            "professional": (
                "Thank you. Let me know if you need anything else.", "Take care, and have a good day.",
                "That should cover it. Good day to you.", "I will be here if anything else comes up.",
            ),
            "warm": (
                "It was good talking with you. Take care!", "I hope we speak again soon.",
                "Go on, then. Come back soon!", "That brightened the day. Take care.",
            ),
            "skeptical": (
                "We'll leave it there for now.", "I have heard enough to think about.",
                "We will see. Take care.", "I will keep what you said in mind.",
            ),
            "blunt": (
                "That's enough for now.", "I should get back to what I was doing.",
                "Right. Go on.", "Done talking.",
            ),
            "reserved": (
                "Goodbye.", "Thank you for the conversation.",
                "Until next time.", "Mind how you go.",
            ),
            "wary": (
                "We're finished here.", "That is all I am willing to discuss.",
                "Keep to the road.", "That is enough talking.",
            ),
            "hostile": (
                "Leave me alone now.", "This conversation is over.",
                "Go.", "Do not come back today.",
            ),
            "neutral": (
                "Take care on the road.", "I'll see you around town.",
                "Take care of yourself.", "Until next time, then.",
            ),
        }
        return _cycling_pick(
            f"{self.dialogue_day_key()}:{actor.get('id')}:farewell:{demeanor}",
            pools[demeanor],
            actor.get("dialogue_count", 0),
        )

    def run_unified_npc_conversation(
        self,
        actor: Dict[str, object],
        *,
        kind: str = "authored",
        first_meeting: bool = False,
        repeated_today: bool = False,
        agenda_override: str = "",
        starting_transcript: Optional[Sequence[Dict[str, str]]] = None,
        continue_after_scene: bool = False,
    ) -> Dict[str, object]:
        actor = self.dialogue_promote_world_actor(actor, kind)
        if kind != "child" and hasattr(self, "ensure_npc_lineage_for_actor"):
            lineage_realm = "town" if kind in {"authored", "spouse"} else str(kind or "world")
            self.ensure_npc_lineage_for_actor(actor, lineage_realm)
        actor["_dialogue_kind"] = str(kind)
        active_thread = self.dialogue_current_thread(actor, kind, create=False)
        if not continue_after_scene and self.dialogue_should_begin_thread(
            actor,
            kind,
            first_meeting=first_meeting,
            repeated_today=repeated_today,
            agenda_override=agenda_override,
        ):
            active_thread = self.dialogue_current_thread(actor, kind, create=True)
            if active_thread:
                active_thread["introduced"] = True
        group_partner = self.dialogue_nearby_group_partner(actor, kind)
        if group_partner:
            actor["_dialogue_group_partner"] = group_partner
        transcript: List[Dict[str, str]] = [
            dict(entry) for entry in (starting_transcript or []) if isinstance(entry, dict)
        ][-24:]
        discussed: List[str] = []

        def finish(completed: bool) -> Dict[str, object]:
            actor["recent_conversation_topics"] = (
                list(actor.get("recent_conversation_topics", []) or []) + discussed
            )[-12:]
            actor.pop("_dialogue_kind", None)
            actor.pop("_dialogue_group_partner", None)
            self.dialogue_commit_world_actor(actor, kind, bool(completed or transcript))
            self._last_dialogue_transcript = transcript
            self.invalidate_draw_cache()
            return {"completed": completed, "topics": discussed, "transcript": transcript}

        greeting = "" if continue_after_scene else self.dialogue_greeting(actor, kind, first_meeting, repeated_today)
        if greeting and not self.dialogue_say(actor, greeting, "greeting", transcript):
            return finish(False)
        if not continue_after_scene:
            self.dialogue_prepare_initiation(actor, kind)
        initiation_slot = self.dialogue_social_slot(actor, kind)
        initiation_record = initiation_slot.get("initiation", {})
        initiation_reason = str(initiation_record.get("reason", "")) if isinstance(initiation_record, dict) else ""
        initiated = "" if continue_after_scene else self.dialogue_accept_initiation(actor, kind)
        if initiated and not self.dialogue_say(actor, initiated, "they approached you", transcript):
            return finish(False)
        invitation = initiation_slot.get("invitation", {})
        if (
            not continue_after_scene
            and initiation_reason == "invitation"
            and isinstance(invitation, dict)
            and str(invitation.get("status", "")) == "pending"
            and not self.dialogue_handle_npc_invitation(actor, kind, invitation, transcript)
        ):
            return finish(False)
        subject_present = bool(initiated) or bool(continue_after_scene)
        if not first_meeting and not subject_present:
            callback = self.dialogue_promise_callback(actor, kind)
            if callback and not self.dialogue_say(actor, callback, "follow-up", transcript):
                return finish(False)
            subject_present = bool(callback)
        if not subject_present and agenda_override:
            if not self.dialogue_say(actor, str(agenda_override), "main subject", transcript):
                return finish(False)
            subject_present = True
        elif not subject_present and active_thread and bool(active_thread.get("introduced", False)):
            agenda = self.dialogue_agenda(actor, kind)
            if agenda and not self.dialogue_say(actor, agenda, "main subject", transcript):
                return finish(False)
            subject_present = bool(agenda)
        elif not subject_present and not first_meeting:
            chitchat = self.dialogue_chitchat(actor, kind)
            if chitchat and not self.dialogue_say(actor, chitchat, "chit-chat", transcript):
                return finish(False)
            subject_present = bool(chitchat)

        initial_options: List[DialogueOption] = []
        thread_is_subject = bool(
            active_thread
            and active_thread.get("introduced", False)
            and (not agenda_override)
            and (not initiated or initiation_reason == "ongoing_thread")
        )
        if thread_is_subject:
            initial_options.append(("ask", "What's going on?", "Continue the matter they raised."))
        if self.dialogue_actor_quest_entries(actor, kind):
            initial_options.append((
                "turn_in", "I finished one of your requests.",
                "Choose which of their requests to hand in.",
            ))
        if self.dialogue_distorted_player_rumors(actor, kind):
            # Only when this NPC is actually carrying a garbled version of
            # something the player did. That is rare by construction, so the
            # option cannot become permanent furniture on the menu.
            initial_options.append((
                "set_record", "They have it wrong about me.",
                "Correct the version of events they have been repeating.",
            ))
        if not initiated:
            initial_options.append(("help", "Is there anything I can help with?", "Find out whether they have concrete work available."))
        initial_options.extend([
            ("topics", "Can I ask you something?", "Open the general question list."),
            ("goodbye", "I should get going.", "Let the exchange end here."),
        ])
        initial = self.dialogue_choose(actor, "What do you say?", "main subject", initial_options, transcript)
        if initial == "ask":
            discussed.append("agenda")
            if active_thread:
                if not self.dialogue_handle_thread(actor, kind, active_thread, transcript):
                    return finish(True)
        elif initial == "turn_in":
            discussed.append("work")
            if not self.dialogue_handle_quest_turn_in(actor, kind, transcript):
                return finish(True)
        elif initial == "set_record":
            discussed.append("player")
            if not self.dialogue_handle_rumor_correction(actor, kind, transcript):
                return finish(True)
        elif initial == "help":
            discussed.append("work")
            if not self.dialogue_handle_work_situation(actor, kind, transcript):
                return finish(True)
        elif initial == "goodbye":
            farewell = self.dialogue_farewell(actor, kind)
            if farewell:
                self.dialogue_say(actor, farewell, "closing", transcript)
            return finish(True)

        while True:
            topic = self.dialogue_choose_topic(actor, kind, transcript)
            if not topic or topic == "goodbye":
                break
            answer = self.dialogue_topic_answer(actor, kind, topic, transcript)
            if answer:
                discussed.append(topic)
                if not self.dialogue_say(actor, answer, "response", transcript):
                    break
            elif topic in {"work", "player", "smalltalk", "relationship", "arrangements", "thread", "group", "household"}:
                discussed.append(topic)
        farewell = self.dialogue_farewell(actor, kind)
        if farewell:
            self.dialogue_say(actor, farewell, "closing", transcript)
        return finish(True)

    def town_npc_conversation_menu(
        self, npc: Dict[str, object], influence_available: bool
    ) -> Dict[str, object]:
        result = self.run_unified_npc_conversation(
            npc,
            kind="spouse" if str(npc.get("id", "")) == str(getattr(self.state, "spouse_npc_id", "")) else "authored",
            first_meeting=int(getattr(self.state, "town_npc_dialogue_counts", {}).get(str(npc.get("id", "")), 0)) <= 0,
            repeated_today=not bool(influence_available),
        )
        return {"effect": 0, "style": "conversation", "topic": ",".join(result.get("topics", [])) or "conversation", **result}

    def talk_to_town_npc(self, npc: Dict[str, object]):
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        today = self.town_npc_day_key()
        first_talk_today = self.state.town_npc_last_talk_day.get(npc_id) != today
        prior_count = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        scene_played = bool(
            first_talk_today
            and self.maybe_play_scene_for_context({
                "type": "npc_talk", "npc": npc, "npc_id": npc_id,
                "first_meeting": prior_count <= 0,
            })
        )
        if scene_played and bool(getattr(self, "_last_scene_was_skipped", False)):
            self.state.town_npc_dialogue_counts[npc_id] = prior_count + 1
            self.state.town_npc_last_talk_day[npc_id] = today
            self.adjust_town_npc_relationship(npc_id, RELATIONSHIP_TALK_GAIN)
            self.autosave_with_message(self.state.message or f"Shared a moment with {npc.get('name', 'the villager')}.")
            return
        result = self.run_unified_npc_conversation(
            npc,
            kind="spouse" if npc_id == str(getattr(self.state, "spouse_npc_id", "")) else "authored",
            first_meeting=prior_count <= 0 and not scene_played,
            repeated_today=not first_talk_today,
            starting_transcript=(
                getattr(self, "_last_completed_scene_transcript", []) if scene_played else None
            ),
            continue_after_scene=scene_played,
        )
        if not result.get("completed") and not result.get("transcript"):
            self.set_message(f"Stopped talking to {npc.get('name', 'the villager')}.")
            return
        self.state.town_npc_dialogue_counts[npc_id] = prior_count + 1
        gain = 0
        suppress_gain = bool(npc.pop("_dialogue_suppress_talk_gain", False))
        if first_talk_today:
            if not suppress_gain:
                gain = self.adjust_town_npc_relationship(npc_id, RELATIONSHIP_TALK_GAIN)
            self.state.town_npc_last_talk_day[npc_id] = today
        self.autosave_with_message(
            f"Talked to {npc.get('name', 'the villager')}." + (f" Relationship +{gain}." if gain else "")
        )

    def talk_to_procedural_town_resident(
        self, resident: Dict[str, object]
    ) -> Optional[Dict[str, object]]:
        plan = self.current_procedural_town_plan()
        if not plan:
            return None
        first_meeting = not bool(resident.get("met", False))
        repeated_today = str(resident.get("last_talk_day", "")) == self.town_npc_day_key()
        seed_result = self.procedural_settlement_conversation(
            int(plan["chunk_x"]), int(plan["chunk_y"]), str(resident.get("id", "")),
            topic="chat", remember=True,
        )
        if not seed_result:
            return None
        result = self.run_unified_npc_conversation(
            resident,
            kind="procedural",
            first_meeting=first_meeting,
            repeated_today=repeated_today,
            agenda_override=str(seed_result.get("text", "")),
        )
        resident_id = str(resident.get("id", ""))
        self.state.town_npc_dialogue_counts[resident_id] = int(resident.get("dialogue_count", 0))
        self.state.town_npc_last_talk_day[resident_id] = str(resident.get("last_talk_day", self.town_npc_day_key()))
        gain = int(seed_result.get("relationship_gain", 0) or 0)
        if resident.pop("_dialogue_suppress_talk_gain", False) and gain:
            resident["relationship"] = max(-50, int(resident.get("relationship", 0) or 0) - gain)
            gain = 0
        if gain:
            self.state.town_npc_relationships[resident_id] = int(resident.get("relationship", 0))
            self.adjust_procedural_town_reputation(1, f"Conversation with {resident.get('name', 'a resident')}", plan)
        self.autosave_with_message(
            f"Talked to {resident.get('name', 'the resident')}." + (f" Relationship +{gain}." if gain else "")
        )
        return {**seed_result, **result}

    def talk_to_procedural_household_spouse(self, resident: Dict[str, object]) -> None:
        resident_id = str(resident.get("id", ""))
        today = self.town_npc_day_key()
        first_today = str(resident.get("last_talk_day", "")) != today
        result = self.run_unified_npc_conversation(
            resident,
            kind="spouse",
            first_meeting=False,
            repeated_today=not first_today,
            agenda_override=spouse_household_line(
                "plans",
                self.dialogue_household_content_context(resident, "spouse"),
                f"{today}:{resident_id}:home-agenda",
                self.dialogue_spouse_stage(),
            ),
        )
        resident["dialogue_count"] = int(resident.get("dialogue_count", 0)) + 1
        resident["last_talk_day"] = today
        self.state.town_npc_dialogue_counts[resident_id] = int(resident["dialogue_count"])
        self.state.town_npc_last_talk_day[resident_id] = today
        suppress_gain = bool(resident.pop("_dialogue_suppress_talk_gain", False))
        gain = self.adjust_town_npc_relationship(resident_id, 2) if first_today and not suppress_gain else 0
        self.autosave_with_message(
            f"Talked with {resident.get('name', 'your spouse')} at home." + (f" Relationship +{gain}." if gain else "")
        )


def _stable_pick(seed: str, values: Sequence[str]) -> str:
    choices = tuple(str(value) for value in values if str(value))
    return choices[_stable_index(seed, len(choices))] if choices else ""


def _cycling_pick(seed: str, values: Sequence[str], step: object) -> str:
    """Pick by stepping through the pool instead of resampling it.

    For lines a player can trigger several times in a row -- repeat greetings,
    farewells -- an independent pick collides with itself often enough to read
    as a bug. Seeding the starting point per NPC and per day keeps them
    distinct from each other, while the step guarantees no consecutive repeat.
    """
    choices = tuple(str(value) for value in values if str(value))
    if not choices:
        return ""
    try:
        offset = int(step or 0)
    except (TypeError, ValueError):
        offset = 0
    return choices[(_stable_index(seed, len(choices)) + offset) % len(choices)]


__all__ = ["DialogueFlowMixin", "ROLE_INTERESTS", "naturalize_spoken_dialogue"]
