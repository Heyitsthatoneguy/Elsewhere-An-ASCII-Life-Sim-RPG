from __future__ import annotations

"""Turn-by-turn, knowledge-aware conversations shared by every NPC family.

The game used to present several unrelated generated remarks at once and then
require the same social-response quiz.  This module keeps one conversational
thread on screen: opening, chit-chat, speaker agenda, questions, and closing.
"""

import hashlib
import sys
import textwrap
from typing import Dict, List, Optional, Sequence, Tuple

from ascii_farmstead_data import (
    MENU_CONFIRM_KEYS,
    RELATIONSHIP_TALK_GAIN,
    TOWN_BUILDING_DATA,
)
from ascii_farmstead_dialogue_library import contextual_dialogue_line
from ascii_farmstead_support import clear_screen, normalize_key, read_key
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
    "Naturalist": ("wildlife", "botany", "field journals"),
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
            "A route I depend on has become unreliable, and I am still working out whether the danger or the detour is worse.",
            "I have compared a few reports. The trouble is real, but so is the cost of changing everyone's route.",
            "I have a workable plan now. I need to test it against the road instead of discussing it forever.",
            "The revised route held. People are already using it without needing to know how uncertain it was at first.",
        ),
    },
    "work": {
        "title": "Pressure at Work",
        "roles": {"seller", "merchant", "vendor", "innkeeper", "chef", "blacksmith", "carpenter", "mechanic", "tailor"},
        "stages": (
            "The work has been pulling in two directions at once, and both sides belong to people who are counting on me.",
            "I have separated what is urgent from what is merely loud. That helped more than I expected.",
            "I know what I am going to change, though it may disappoint someone who preferred the old arrangement.",
            "The new arrangement is holding. The work feels like mine again instead of a list of other people's emergencies.",
        ),
    },
    "care": {
        "title": "Someone Needs Care",
        "roles": {"doctor", "nurse", "healer", "animal", "keeper", "gardener", "herbalist"},
        "stages": (
            "Someone in my care needs more than the ordinary routine, and I do not want my worry to become their burden.",
            "I have a clearer picture now. Patience is part of the treatment, even when action would feel easier.",
            "The difficult part is keeping everyone consistent after the immediate concern passes.",
            "Things have stabilized. It was not one dramatic solution; it was several people doing the dependable thing repeatedly.",
        ),
    },
    "research": {
        "title": "An Unfinished Finding",
        "roles": {"librarian", "scholar", "researcher", "naturalist", "botanist", "archivist", "artist"},
        "stages": (
            "I found a pattern that might matter, but one interesting coincidence is not enough to call a discovery.",
            "The second set of notes supports it. Now I need evidence from somewhere the first survey did not cover.",
            "The evidence is strong enough to share, which means it is also strong enough for other people to challenge.",
            "The finding survived scrutiny. More importantly, it changed what people are looking for next.",
        ),
    },
    "community": {
        "title": "A Community Decision",
        "roles": {"mayor", "clerk", "sheriff", "deputy", "retiree"},
        "stages": (
            "Two reasonable groups want incompatible things from the same public decision.",
            "I have heard enough arguments to understand that neither side is being difficult for sport.",
            "There is a compromise worth attempting, but it requires both groups to accept a result they did not design alone.",
            "The compromise held. Nobody calls it perfect, which may be the most honest sign that it belongs to everyone.",
        ),
    },
    "personal": {
        "title": "A Personal Crossroads",
        "roles": set(),
        "stages": (
            "I have been reconsidering part of my routine. Nothing is wrong exactly, but familiar is not always the same as right.",
            "Talking it through showed me which part is habit and which part I would genuinely miss.",
            "I have chosen a small change I can actually sustain instead of making a dramatic promise to myself.",
            "The change has become part of the routine now. I feel more like I chose my days instead of merely inheriting them.",
        ),
    },
}

STORY_AFTERMATH_PROFILES: Dict[str, Dict[str, str]] = {
    "roads": {
        "summary": "The revised route held under real travel and is becoming part of local habit.",
        "activity": "checking the revised route and comparing travelers' reports",
        "follow_up": "The route is holding. People are already using the change without needing to know how uncertain it felt at first.",
    },
    "work": {
        "summary": "The new work order separated genuine priorities from constant emergencies.",
        "activity": "testing a steadier work order and protecting its priorities",
        "follow_up": "The work change survived its first real pressure. I am still adjusting it, but the day no longer belongs entirely to whoever shouts first.",
    },
    "care": {
        "summary": "A dependable care routine replaced the cycle of reacting only when something became urgent.",
        "activity": "maintaining the care routine that the household helped stabilize",
        "follow_up": "The care routine is holding because it became ordinary. That is less dramatic than a miracle and much more dependable.",
    },
    "research": {
        "summary": "The finding survived a second field test and changed what evidence people seek next.",
        "activity": "organizing the verified finding and planning the next survey",
        "follow_up": "The finding survived scrutiny. The useful result is not that I was right; it is that people are asking better questions now.",
    },
    "community": {
        "summary": "The compromise held long enough to become a shared public arrangement rather than one person's proposal.",
        "activity": "checking how the new community arrangement is working in practice",
        "follow_up": "The compromise is holding. Nobody received everything, but people have started treating the result as something they share.",
    },
    "personal": {
        "summary": "A small deliberate change became part of the routine instead of fading after one ambitious day.",
        "activity": "protecting the deliberate change they added to their routine",
        "follow_up": "The change has lasted long enough to feel chosen rather than experimental. I notice the difference most on ordinary days.",
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


class DialogueFlowMixin:
    """A FarmGame mixin for coherent, advancing NPC conversations."""

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
        if kind in {"authored", "spouse"} and actor_id and hasattr(self, "town_npc_relationship"):
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
        values = [
            actor.get("personality", ""), actor.get("disposition", ""),
            *traits,
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
            "neutral": "As I see it",
        }[self.dialogue_demeanor(actor, kind)]

    def _draw_dialogue_frame(
        self,
        actor: Dict[str, object],
        text: str,
        phase: str,
        transcript: Sequence[Dict[str, str]],
        options: Sequence[DialogueOption] = (),
        selected: int = 0,
    ) -> None:
        width = max(42, min(72, terminal_width() - 4))
        name = self.dialogue_actor_name(actor)
        role = self.dialogue_actor_role(actor)
        familiarity = self.dialogue_familiarity_label(actor, str(actor.get("_dialogue_kind", "authored")))
        title = f"{name} — {role}"
        panel = [
            "+" + "-" * width + "+",
            "|" + pad_to(fit_text(title, width), width) + "|",
            "|" + pad_to(fit_text(f"{phase.title()} · {familiarity}", width), width) + "|",
            "+" + "-" * width + "+",
        ]
        for line in (textwrap.wrap(str(text), width=width - 4) or [""])[:3]:
            panel.append("|" + pad_to("  " + line, width) + "|")
        panel.append("+" + "-" * width + "+")
        if options:
            visible_count = 5
            start = max(
                0,
                min(int(selected) - visible_count // 2, max(0, len(options) - visible_count)),
            )
            end = min(len(options), start + visible_count)
            if start > 0:
                panel.append("|" + pad_to("  ^ more choices above", width) + "|")
            for index in range(start, end):
                _value, label, hint = options[index]
                prefix = "> " if index == selected else "  "
                line = f"{prefix}{index + 1}. {label}"
                panel.append("|" + pad_to(fit_text(line, width), width) + "|")
                if index == selected and hint:
                    for wrapped in textwrap.wrap(str(hint), width=width - 6)[:1]:
                        panel.append("|" + pad_to("      " + wrapped, width) + "|")
            if end < len(options):
                panel.append("|" + pad_to("  v more choices below", width) + "|")
            controls = "Up/Down choose · Z/Enter confirm · H history · B/X/Esc/Q/Tab leave"
        else:
            controls = "Z/Enter/Space continue · H history · B/X/Esc/Q/Tab leave"
        panel.extend([
            "+" + "-" * width + "+",
            "|" + pad_to(fit_text(controls, width), width) + "|",
            "+" + "-" * width + "+",
        ])

        clear_screen()
        if hasattr(self, "render_frame_text"):
            try:
                base_lines = self.render_frame_text().splitlines()
                world_rows = max(6, terminal_height() - len(panel) - 1)
                for line in base_lines[:world_rows]:
                    print(line)
            except Exception:
                pass
        for line in panel:
            self.centered_print(line, width + 2)
        try:
            sys.stdout.flush()
        except Exception:
            pass

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
        line = " ".join(str(text or "").strip().split())
        if not line:
            return True
        speaker = self.dialogue_actor_name(actor)
        transcript.append({"speaker": speaker, "text": line, "phase": phase})
        if hasattr(self, "add_hud_activity"):
            self.add_hud_activity(f"{speaker}: {line}", "dialogue")
        while True:
            self._draw_dialogue_frame(actor, line, phase, transcript)
            key = normalize_key(self.dialogue_read_key())
            if key in MENU_CONFIRM_KEYS:
                return True
            if key == "h":
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
        choices = list(options)
        if not choices:
            return ""
        selected = 0
        while True:
            self._draw_dialogue_frame(actor, prompt, phase, transcript, choices, selected)
            key = normalize_key(self.dialogue_read_key())
            if key in {"UP", "w", "NUM8"}:
                selected = (selected - 1) % len(choices)
            elif key in {"DOWN", "s", "NUM2"}:
                selected = (selected + 1) % len(choices)
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
                "professional": ("Was there something else I can help with?", "Welcome back. What else did you need?"),
                "warm": ("Back again? Good. What did you forget to ask?", "Oh, hello again! What is it?"),
                "skeptical": ("You are back already. What changed?", "Another question? Go ahead."),
                "blunt": ("Again? What is it?", "You came back quickly. Speak."),
                "reserved": ("Hello again. Was there something else?", "You are back. I am listening."),
                "wary": ("What do you need this time?", "You again. Keep it brief."),
                "hostile": ("We already spoke. What now?", "Make this quick."),
                "neutral": ("Did you need something else?", "Was there something you forgot to ask?"),
            }
            return _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:again",
                repeat_pools[demeanor],
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
                "warm": ("There you are! I am glad you stopped.", "Good, I was hoping I would see you."),
                "blunt": ("There you are. I can speak plainly with you.", "Good. You are someone I do not have to perform for."),
                "reserved": ("I'm glad you came by.", "It is good to see someone familiar."),
                "skeptical": ("I trust you enough to skip the polite version.", "Good. I wanted your honest opinion."),
            }
            base = _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:close:{demeanor}",
                pools.get(demeanor, ("There you are. It is good to see you.", "I was hoping our paths would cross.")),
            )
        else:
            pools = {
                "professional": (f"Good {period}. How can I help?", "Welcome back. What did you need?"),
                "warm": ("Hello again! How have you been?", "There you are. It is good to see a familiar face."),
                "skeptical": ("Hello again. What is on your mind?", "You have another question, I assume."),
                "blunt": ("There you are. What is it?", "Hello. Speak plainly and we will get along."),
                "reserved": ("Hello again.", "Good to see you. Was there something you wanted to discuss?"),
                "wary": ("What do you want?", "I suppose we can speak for a moment."),
                "hostile": ("What is it now?", "I have little patience for this, but speak."),
                "neutral": (f"Good {period}.", "Hello again. Was there something you needed?"),
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
            source = (
                "something they personally witnessed"
                if source_kind == "firsthand"
                else "public notice" if source_kind == "public"
                else source_name
            )
            packet = {
                "text": str(knowledge.get("text", "")),
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
                    heard.append({"text": rumor, "source": str(partner.get("name", "a neighbor")), "day": self.dialogue_day_key()})
        actor["heard_rumors"] = heard[-8:]
        return actor["heard_rumors"]

    def dialogue_chitchat(self, actor: Dict[str, object], kind: str) -> str:
        witnessed = self.dialogue_witness_callback(actor, kind, "conversation")
        if witnessed:
            return witnessed
        mood_line = self.dialogue_mood_context_line(actor, kind)
        if mood_line:
            return mood_line
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
                return f"I was speaking with {source}. They mentioned that {text[:1].lower() + text[1:]}{uncertainty}"
            if source in {"something they witnessed around town", "something they personally witnessed"}:
                return text
            return f"People have been talking. {text}"
        topic = "weather" if _stable_index(f"{self.dialogue_day_key()}:{actor.get('id')}:smalltalk", 2) == 0 else "season"
        return self.dialogue_library_line(actor, topic, "smalltalk")

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

    def dialogue_agenda(self, actor: Dict[str, object], kind: str) -> str:
        name = self.dialogue_actor_name(actor)
        thread = self.dialogue_current_thread(actor, kind, create=True)
        if thread:
            return (
                f"There is something I have been carrying forward: "
                f"{thread.get('title', 'an ongoing matter')}. "
                f"{self.dialogue_thread_line(actor, kind, thread)}"
            )
        aftermath = self.dialogue_story_aftermath(actor, kind)
        if aftermath and int(aftermath.get("last_agenda_day", 0) or 0) != self.dialogue_absolute_day():
            aftermath["last_agenda_day"] = self.dialogue_absolute_day()
            return str(aftermath.get("follow_up", aftermath.get("summary", "")))
        activity = self.dialogue_activity(actor, kind).replace("their ", "my ")
        if kind == "authored" and hasattr(self, "town_npc_work_insight"):
            insight = self.town_npc_work_insight(actor)
        else:
            insight = str(actor.get("goal", "I am trying to keep today's work from becoming tomorrow's problem."))
        insight = _first_person(insight, name)
        reflection = self.dialogue_library_line(actor, "activity", activity)
        return f"I've been {activity}. {insight} {reflection}"

    def dialogue_topic_options(
        self, actor: Dict[str, object], kind: str
    ) -> List[DialogueOption]:
        options: List[DialogueOption] = [
            ("directions", "Ask for directions", "Only places this person knows will be listed."),
            ("background", "Ask where they are from", "Home, origin, and how they came to be here."),
            ("family", "Ask about their family", "Answers reflect their actual household and trust."),
            ("work", "Ask about work or opportunities", "Profession, current task, requests, and quests."),
            ("interests", "Ask about hobbies and interests", "Things they do when work is finished."),
            ("people", "Ask about someone they know", "Family, coworkers, friends, and traveling companions."),
            ("player", "Tell them about yourself", "Share your background, deeds, travels, possessions, family, companions, or ancestry."),
            ("smalltalk", "Make small talk", "Chat casually, offer a sincere compliment, or deliberately insult them."),
            ("arrangements", "Make a practical arrangement", "Introductions, messages, meetings, maps, travel, and family plans use real world systems."),
            ("companions", "Talk about companions", "Your traveling party and people seeking company."),
        ]
        if str(actor.get("id", "")) and kind in {"authored", "procedural", "spouse"}:
            options.append(("relationship", "Talk about your relationship", "Gifts, affection, courtship, proposals, and household decisions appear only when they make sense."))
        if self.dialogue_current_thread(actor, kind, create=False):
            options.append(("thread", "Return to the ongoing matter", "Continue the personal situation across conversations."))
        if actor.get("_dialogue_group_partner"):
            options.append(("group", "Address everyone nearby", "Bring the nearby participant into the same conversation."))
        actor_id = str(actor.get("id", ""))
        if kind in {"spouse", "child"} or actor_id.startswith(("spouse:", "child:")):
            options.append(("household", "Talk about your household", "Plans, safety, finances, memories, and family outings."))
        options.append(("goodbye", "Finish the conversation", "Leave the conversation naturally."))
        return options

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
        for prefix, label in (("home_name", "Home"), ("destination_name", "Destination"), ("settlement_name", "Hometown")):
            value = str(actor.get(prefix, ""))
            if value and all(place["name"] != value for place in places):
                places.append({"id": f"known:{prefix}", "name": value, "kind": "known"})
        if kind in {"traveler", "outpost", "companion"}:
            state = getattr(self.state, "wilderness_poi_state", {})
            if isinstance(state, dict):
                for key, record in state.items():
                    if not isinstance(record, dict) or not record.get("name"):
                        continue
                    if not any(record.get(flag) for flag in ("discovered", "repaired", "restored", "visited")):
                        continue
                    coords = str(key).split(":")[-1].split(",")
                    if len(coords) != 2:
                        continue
                    try:
                        cx, cy = int(coords[0]), int(coords[1])
                    except ValueError:
                        continue
                    places.append({"id": f"wilderness:{cx},{cy}", "name": str(record["name"]), "x": cx, "y": cy, "kind": "wilderness"})
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
            return f"{name} is in {place.get('district', 'town')}. The town roads and signs will take you there from the central avenue. {self.dialogue_library_line(actor, 'place', name)}"
        if kind == "settlement":
            plan = self.current_procedural_town_plan() or {}
            sign_x, sign_y = int(plan.get("sign_x", 0) or 0), int(plan.get("sign_y", 0) or 0)
            dx, dy = int(place.get("x", 0)) - sign_x, int(place.get("y", 0)) - sign_y
            horizontal = "east" if dx > 0 else "west" if dx < 0 else ""
            vertical = "south" if dy > 0 else "north" if dy < 0 else ""
            direction = "-".join(part for part in (vertical, horizontal) if part) or "near the town center"
            return f"{name} is {direction} of the settlement sign. Follow the finished streets; its door opens onto the road. {self.dialogue_library_line(actor, 'place', name)}"
        if kind == "wilderness":
            cx, cy = int(place.get("x", 0)), int(place.get("y", 0))
            if hasattr(self, "map_nearby_wilderness_chunks"):
                mapped = self.wilderness_region_record(cx, cy).setdefault("mapped_chunks", [])
                coord = f"{cx},{cy}"
                if coord not in mapped:
                    mapped.append(coord)
            return f"I've been to {name}. It lies in wilderness region ({cx},{cy}); I've marked the region on your map. {self.dialogue_library_line(actor, 'place', name)}"
        return f"I know {name}, but not well enough to give you a precise route. Ask someone who travels there regularly. {self.dialogue_library_line(actor, 'place', name)}"

    def dialogue_background_answer(self, actor: Dict[str, object], kind: str) -> str:
        origin = str(actor.get("origin_name") or actor.get("settlement_name") or actor.get("home_name") or "")
        reflection = self.dialogue_library_line(actor, "personal", "background")
        if origin:
            return f"I'm from {origin}. My routines still carry habits I learned there, even when the roads take me elsewhere. {reflection}"
        if kind == "authored":
            return f"I'm from Elsewhere. I have watched the town change enough that some streets feel like memories and others still feel newly borrowed. {reflection}"
        home = str(actor.get("home", "Elsewhere"))
        return f"I've lived around {home} long enough that most of my history is tied to the people and routines here. {reflection}"

    def dialogue_family_answer(self, actor: Dict[str, object], kind: str) -> str:
        actor_id = str(actor.get("id", ""))
        reflection = self.dialogue_library_line(actor, "family", "family")
        if kind == "child":
            return f"You already know my family. What matters is whether we keep making time for one another when everyone gets busy. {reflection}"
        if kind == "procedural" and hasattr(self, "current_procedural_town_plan"):
            plan = self.current_procedural_town_plan() or {}
            population = self.procedural_settlement_population(
                int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))
            )
            members = self.procedural_npc_dialogue_builder().household_members(actor, population or {})
            if members:
                names = ", ".join(str(member.get("name", "a relative")) for member in members)
                return f"I share my household with {names}. Our work and schedules differ, but we still organize the day around coming home to one another. {reflection}"
        if actor_id and hasattr(self, "npc_family_dialogue_line"):
            line = str(self.npc_family_dialogue_line(actor)).strip().strip('"“”')
            if line:
                return f"{line} {reflection}"
        spouse = str(actor.get("spouse_name", ""))
        children = [str(value) for value in actor.get("children_names", []) or []]
        if spouse or children:
            parts = ([f"I'm married to {spouse}"] if spouse else []) + ([f"our children are {', '.join(children)}"] if children else [])
            return "; ".join(parts) + f". Family shapes nearly every part of my routine. {reflection}"
        household = str(actor.get("household_name", ""))
        if household:
            return f"I belong to the {household} household. We do not agree on everything, but we know where everyone is expected home. {reflection}"
        return f"I don't have much family life I am ready to discuss, but that may change as we know each other better. {reflection}"

    def dialogue_work_answer(
        self, actor: Dict[str, object], kind: str, opportunities: bool = False
    ) -> str:
        role = self.dialogue_actor_role(actor)
        reflection = self.dialogue_library_line(actor, "work", "profession")
        if opportunities:
            if kind == "procedural" and hasattr(self, "current_procedural_town_plan"):
                plan = self.current_procedural_town_plan() or {}
                result = self.procedural_settlement_conversation(
                    int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0)),
                    str(actor.get("id", "")), topic="request", remember=False,
                )
                if result:
                    return f"{result.get('text', 'I will let you know when work is available.')} {reflection}"
            if kind == "authored" and hasattr(self, "errand_for_npc"):
                errand = self.errand_for_npc(actor)
                if isinstance(errand, dict):
                    if errand.get("completed"):
                        return "You already helped with what I needed today. Ask again tomorrow."
                    return f"I could use {errand.get('qty', 1)} {errand.get('item', 'supplies')}. Bring them when you have them, and we can settle the work properly."
            return f"I don't have a specific job for you right now. If my routine changes or supplies run short, I will say so. {reflection}"
        if kind == "procedural" and hasattr(self, "current_procedural_town_plan"):
            plan = self.current_procedural_town_plan() or {}
            result = self.procedural_settlement_conversation(
                int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0)),
                str(actor.get("id", "")), topic="work", remember=False,
            )
            if result:
                return f"{result.get('text', f'I work as a {role.lower()}.')} {reflection}"
        insight = self.town_npc_work_insight(actor) if kind == "authored" and hasattr(self, "town_npc_work_insight") else actor.get("goal", "The work changes with the day.")
        work_intro = _stable_pick(
            f"{self.dialogue_day_key()}:{actor.get('id')}:work-intro",
            (
                "My work is less about the title and more about what people rely on me to do.",
                f"Most working days, I handle the responsibilities people associate with a {role.lower()}.",
                f"People tend to find me when they need a {role.lower()}, though the job is broader than that sounds.",
                "The practical side of my work changes enough that the title only tells part of the story.",
            ),
        )
        return f"{work_intro} {_first_person(insight, self.dialogue_actor_name(actor))} {reflection}"

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
        elif promise_type == "procedural_request":
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
        return f"You said you would {summary}. There is no need to answer again; I am only making sure we remember the same commitment."

    def dialogue_work_situation(
        self, actor: Dict[str, object], kind: str
    ) -> Optional[Dict[str, object]]:
        if kind == "authored" and hasattr(self, "errand_for_npc"):
            errand = self.errand_for_npc(actor)
            if isinstance(errand, dict) and not errand.get("completed"):
                item, qty = str(errand.get("item", "supplies")), int(errand.get("qty", 1))
                return {
                    "type": "authored_errand", "id": str(errand.get("id", "")),
                    "summary": f"bring me {qty} {item}", "record": errand,
                    "prompt": f"I need {qty} {item} before the day is over. I can pay ${errand.get('money', 0)}, and I would remember the help.",
                    "promise": True, "deadline": "today",
                    "ready": bool(self.can_complete_errand(errand)),
                }
        if kind == "procedural" and hasattr(self, "ensure_procedural_resident_request"):
            plan = self.current_procedural_town_plan() or {}
            request = self.ensure_procedural_resident_request(
                int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0)), str(actor.get("id", ""))
            )
            if isinstance(request, dict) and str(request.get("status", "")) == "active":
                item = str(request.get("item", "supplies"))
                qty = int(request.get("quantity", 1))
                return {
                    "type": "procedural_request", "id": str(request.get("id", "")),
                    "summary": f"bring me {qty} {item}", "record": request,
                    "prompt": f"I have a specific need: {qty} {item}. The work pays {int(request.get('reward_money', 0))}g and helps this household directly.",
                    "promise": True, "deadline": "until the request is completed",
                    "ready": int(self.state.inventory.get(item, 0) or 0) >= qty,
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
                requirements = f" It requires {qty} {item}." if item else ""
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
                    "prompt": "There is practical work at this site right now. If you begin it, time and stamina will pass immediately, and the site will pay its posted reward.",
                    "promise": False, "ready": True,
                }
        if kind == "outpost" and hasattr(self, "share_wilderness_outpost_sample"):
            item = self.wilderness_outpost_sample_item(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
            )
            region = self.wilderness_region_record(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y)
            )
            if (
                region.get("outpost_sample_week") != self.stronghold_cache_week_key()
                and int(self.state.inventory.get(item, 0) or 0) > 0
            ):
                return {
                    "type": "outpost_sample", "id": f"sample:{self.dialogue_day_key()}:{item}",
                    "summary": f"contribute a {item} sample", "prompt": f"A {item} sample would be useful to the outpost's current records. You have one with you, so I can catalogue it now.",
                    "promise": False, "ready": True,
                }
        return None

    def dialogue_complete_work_situation(
        self, actor: Dict[str, object], kind: str, situation: Dict[str, object]
    ) -> bool:
        situation_type = str(situation.get("type", ""))
        if situation_type == "authored_errand":
            return bool(self.complete_errand(dict(situation.get("record", {}) or {})))
        if situation_type == "procedural_request":
            return bool(self.complete_procedural_settlement_request(
                int(situation.get("chunk_x", 0)), int(situation.get("chunk_y", 0)), str(actor.get("id", ""))
            ))
        if situation_type == "traveler_assignment":
            return bool(self.complete_recurring_wilderness_traveler_assignment(actor))
        if situation_type == "caretaker_work":
            return bool(self.perform_wilderness_structure_work())
        if situation_type == "outpost_sample":
            return bool(self.share_wilderness_outpost_sample(actor))
        return False

    def dialogue_handle_work_situation(
        self,
        actor: Dict[str, object],
        kind: str,
        transcript: List[Dict[str, str]],
    ) -> bool:
        situation = self.dialogue_work_situation(actor, kind)
        if not situation:
            return self.dialogue_say(
                actor, self.dialogue_work_answer(actor, kind, True), "work", transcript
            )
        if not self.dialogue_say(actor, str(situation["prompt"]), "work", transcript):
            return False
        options: List[DialogueOption] = []
        if situation.get("ready"):
            options.append(("now", "Do the work now", "The listed items, stamina, time, and rewards apply immediately."))
        if situation.get("promise"):
            options.append((
                "promise", "Accept as a tracked quest",
                f"Adds this request to the Quest Log and records your commitment {situation.get('deadline', 'until it is resolved')}."
            ))
        options.append(("decline", "Not right now", "Makes no promise and causes no relationship penalty."))
        choice = self.dialogue_choose(actor, "What will you do?", "decision", options, transcript)
        if choice == "now":
            success = self.dialogue_complete_work_situation(actor, kind, situation)
            if success:
                self.dialogue_resolve_promise(actor, kind, "fulfilled", str(situation.get("summary", "the work")))
                if hasattr(self, "complete_dialogue_quest_for_situation"):
                    self.complete_dialogue_quest_for_situation(actor, kind, situation)
                return self.dialogue_say(actor, "That settles the matter. Thank you for handling the actual work instead of merely saying you would.", "outcome", transcript)
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
                f"All right. I added {quest.get('title', 'the request')} to your Quest Log and will remember that you promised to {situation.get('summary', 'help')}. The commitment lasts {situation.get('deadline', 'until the work is resolved')}.",
                "outcome", transcript,
            )
        return self.dialogue_say(
            actor, "That is fine. You have not promised me anything, and I will not treat an honest refusal as a betrayal.", "outcome", transcript
        )

    def dialogue_interest_answer(self, actor: Dict[str, object]) -> str:
        role = self.dialogue_actor_role(actor)
        interests = list(actor.get("hobbies", []) or actor.get("interests", []) or ROLE_INTERESTS.get(role, ()))
        if not interests:
            likes = [str(value) for value in actor.get("likes", []) or []][:2]
            interests = likes or ["walking", "local stories"]
        return f"When work allows it, I make time for {', '.join(str(value).lower() for value in interests[:3])}. {self.dialogue_library_line(actor, 'interests', 'interests')}"

    def dialogue_known_people(self, actor: Dict[str, object], kind: str) -> List[Dict[str, object]]:
        people: List[Dict[str, object]] = []
        ids: List[str] = []
        for field in ("social_partner_id", "npc_spouse_id", "courtship_partner_id"):
            value = str(actor.get(field, ""))
            if value:
                ids.append(value)
        ids.extend(str(value) for value in actor.get("child_ids", []) or [])
        ids.extend(str(value) for value in actor.get("household_member_ids", []) or [])
        if kind == "authored" and hasattr(self, "npc_family_profile"):
            profile = self.npc_family_profile(str(actor.get("id", "")))
            if isinstance(profile, dict):
                ids.extend(str(value) for value in profile.get("child_ids", []) or [])
                ids.extend(str(value) for value in profile.get("parent_ids", []) or [])
                for field in ("npc_spouse_id", "courtship_partner_id"):
                    value = str(profile.get(field, ""))
                    if value:
                        ids.append(value)
        if kind == "procedural" and hasattr(self, "current_procedural_town_plan"):
            plan = self.current_procedural_town_plan() or {}
            population = self.procedural_settlement_population(
                int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))
            )
            if isinstance(population, dict):
                members = self.procedural_npc_dialogue_builder().household_members(actor, population)
                people.extend(member for member in members if isinstance(member, dict))
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
            return f"I heard this from {source}: {_first_person(packet.get('text', ''), self.dialogue_actor_name(actor))} {self.dialogue_library_line(actor, 'rumor', source)}"
        return self.dialogue_library_line(actor, "rumor", "news")

    def dialogue_companion_answer(self, actor: Dict[str, object]) -> str:
        follower_ids = list(getattr(self.state, "travel_follower_ids", []) or [])
        if follower_ids and hasattr(self, "travel_follower_data"):
            names = [str(self.travel_follower_data(follower_id).get("name", "a companion")) for follower_id in follower_ids]
            return f"I can see you're traveling with {', '.join(names)}. People learn one another quickly when they share roads, danger, and decisions."
        if self.dialogue_actor_role(actor) in {"Traveler", "Ranger", "Hunter", "Naturalist"}:
            return "I sometimes travel with others when the route is dangerous or the work needs more hands. Trust matters more than speed in a traveling group."
        return "You're traveling alone today. If you want company, friends, family, and experienced regional travelers are the sensible people to ask."

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
        slot["witnessed_events"] = [
            row for row in witnessed if isinstance(row, dict)
        ][-8:]
        for field, limit in (
            ("knowledge", 16), ("threads", 6), ("thread_history", 12),
            ("introductions", 8), ("meetings", 6), ("invitation_history", 8),
            ("story_consequences", 8),
        ):
            rows = slot.get(field, [])
            slot[field] = [row for row in rows if isinstance(row, dict)][-limit:]
        if not isinstance(slot.get("mood", {}), dict):
            slot["mood"] = {}
        if not isinstance(slot.get("initiation", {}), dict):
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
        }
        if existing is not None:
            existing.update(packet)
            return existing
        slot["knowledge"] = (list(slot["knowledge"]) + [packet])[-16:]
        return packet

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
        self.dialogue_add_knowledge(
            listener,
            listener_kind,
            str(packet.get("text", "")),
            subject=str(packet.get("subject", "local news")),
            source_name=self.dialogue_actor_name(source_actor),
            source_kind="hearsay" if str(packet.get("source_kind")) != "public" else "public",
            confidence=confidence,
            knowledge_id=str(packet.get("id", "")),
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
        }
        slot["threads"] = (list(slot["threads"]) + [thread])[-6:]
        return thread

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
                    "description": f"{objective_text} ({quantity} {item})",
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
            return f"The practical part is still in progress: {objective.get('description', 'continue the objective')}", 0
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
        line = (
            "You did not solve my life for me. You helped me test the part that needed contact with the real world, and now I can make the decision myself. "
            + self.dialogue_thread_line(actor, kind, thread)
        )
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
                    resolution += f" Relationship {relationship:+}."
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
                f"Then let us make the help specific: {objective.get('description', 'continue the practical objective')} I added it to your Quest Log; once it is ready, speak with me so we can decide what it changed.",
                "shared undertaking", transcript,
            )
        line, relationship = self.dialogue_advance_thread(actor, kind, thread, choice)
        if relationship:
            line += f" Relationship {relationship:+}."
        return self.dialogue_say(actor, line, "ongoing matter", transcript)

    def dialogue_invitation_relationship(
        self, actor: Dict[str, object], kind: str
    ) -> int:
        actor_id = str(actor.get("id", ""))
        if kind in {"authored", "spouse", "procedural"} and actor_id and hasattr(self, "town_npc_relationship"):
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
        if any(word in role for word in ("ranger", "hunter", "naturalist", "botanist")):
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
        if not actor_id or kind not in {"authored", "procedural", "spouse", "companion"}:
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
            "ranger": ("wilderness", "station", "trail"), "naturalist": ("wilderness", "garden", "field"),
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
                return self.dialogue_say(
                    actor,
                    "Thank you for answering plainly. An invitation is a question, not an obligation; I will make other plans.",
                    "invitation declined", transcript,
                )
            return False
        return True

    def dialogue_prepare_initiation(
        self, actor: Dict[str, object], kind: str
    ) -> Dict[str, object]:
        slot = self.dialogue_social_slot(actor, kind)
        current = slot.get("initiation", {})
        if isinstance(current, dict) and current and not current.get("acknowledged"):
            return current
        reason = ""
        text = ""
        unseen = next(
            (
                row for row in reversed(slot["witnessed_events"])
                if not bool(row.get("conversation_acknowledged", False))
            ),
            None,
        )
        promise = self.dialogue_promise_store().get(self.dialogue_promise_key(actor, kind), {})
        active_promise = promise.get("active", {}) if isinstance(promise, dict) else {}
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
            text = "I saw what happened nearby, and I would like to compare what I saw with what you intended."
        elif active_promise:
            reason = "promise"
            text = "When you have a moment, I would like to check that we remember the same commitment."
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
                for traveler in traveler_cache.get(cache_key, []) or []:
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
        return str(getattr(self.state, "location", "this place") or "this place")

    def world_dialogue_event_action(self, message: object) -> str:
        """Turn a gameplay result into a clause an eyewitness can say naturally."""
        text = " ".join(strip_ansi(str(message or "")).replace("\r", " ").split()).strip(" .")
        if not text:
            return ""
        if text.lower().startswith("you "):
            return text[4:5].lower() + text[5:]
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
            ("Took", "take"), ("Cast", "cast"),
        )
        folded = text.casefold()
        for past, present in verb_forms:
            if folded == past.casefold():
                return present
            prefix = past.casefold() + " "
            if folded.startswith(prefix):
                return f"{present} {text[len(past):].lstrip()}"[:180]
        return ""

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
        folded = text.casefold()
        if resolved == "combat":
            return any(word in folded for word in ("defeat", "attack", "cast", "combat", "rescued", "cleared"))
        if resolved == "money":
            return any(word in folded for word in ("bought", "sold", "paid", "earned", "reward", "income"))
        if resolved == "gain":
            return bool(self.world_dialogue_event_action(text))
        if resolved == "social":
            return any(word in folded for word in ("relationship", "reputation", "affection", "bond", "helped"))
        if resolved == "travel":
            return "discovered" in folded
        return bool(self.world_dialogue_event_action(text))

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
            self.dialogue_add_knowledge(
                actor,
                kind,
                text,
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
        event = next(
            (
                row for row in reversed(slot.get("witnessed_events", []) or [])
                if isinstance(row, dict) and not bool(row.get(flag, False))
            ),
            None,
        )
        if not event:
            return ""
        event[flag] = True
        action = str(event.get("action", "") or "")
        place = str(event.get("location", "nearby") or "nearby")
        if action:
            core = f"I saw you {action} near {place}."
        else:
            core = f"I was nearby when that happened at {place}: {event.get('text', '')}"
        demeanor = self.dialogue_demeanor(actor, kind)
        reactions = {
            "warm": " You handled yourself well.",
            "professional": " It may affect the work people are doing here.",
            "skeptical": " I am still deciding what to make of it.",
            "blunt": " I prefer seeing what someone does to hearing what they claim.",
            "reserved": " I thought you should know that someone noticed.",
            "wary": " Do not assume that means I trust you yet.",
            "hostile": " It did not improve my opinion of you.",
            "neutral": " People tend to remember things like that.",
        }
        return core + reactions.get(demeanor, reactions["neutral"])

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
        if "storm" in weather:
            return "That storm is making every route and errand harder to judge."
        if any(word in weather for word in ("rain", "drizzle", "shower")):
            return "The rain has changed which paths people are using today."
        if any(word in weather for word in ("snow", "blizzard")):
            return "Fresh snow makes it easy to see who has already passed this way."
        if kind in {"companion", "spouse", "child"}:
            family_lines = (
                "I'm still with you. Just say the word if our plans change.",
                "We've covered a fair bit of ground together today.",
                f"I was watching while you moved through {self.world_dialogue_location_label()}.",
            )
            return _stable_pick(f"{self.dialogue_day_key()}:{name}:family:{hour}", family_lines)
        if self.dialogue_is_on_duty(actor, kind):
            return f"I'm {activity}. Let me know if you need something connected to my work."
        if hour >= 21 or hour < 6:
            return "It is late enough that every light and familiar voice matters."
        demeanor = self.dialogue_demeanor(actor, kind)
        pools = {
            "warm": (
                "Good to see someone else out and about.",
                f"I've been {activity}; it has been an interesting day for it.",
            ),
            "professional": (
                f"I'm {activity}; the day's work is still moving.",
                "The local routine has been busier than it looks.",
            ),
            "skeptical": (
                "The roads have been busy. I'm keeping an eye on who uses them.",
                f"I've been {activity}. Not everything around here is as simple as it looks.",
            ),
            "blunt": (
                f"I'm {activity}. Standing around will not finish it.",
                "If you need something, say it plainly.",
            ),
            "reserved": (
                f"I've been {activity}. Quiet work suits me.",
                "You notice more when nobody expects you to speak.",
            ),
            "wary": (
                "I don't know you well enough to explain what I'm doing.",
                "Keep to the open path and we will have no trouble.",
            ),
            "hostile": ("Keep moving.", "I have nothing to say to you."),
            "neutral": (
                f"I've been {activity}.",
                f"People around {self.world_dialogue_location_label()} are settling into today's routine.",
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
        line = self.world_dialogue_ambient_line(actor, kind)
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
        if kind in {"authored", "spouse"} and actor_id and hasattr(self, "adjust_town_npc_relationship"):
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
                names = [f"{qty} {item}" for qty, item in carried]
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
                return f"I am married to {spouse_name}, and our children are {', '.join(children)}."
            if spouse_name:
                return f"I am married to {spouse_name}."
            if children:
                return f"My children are {', '.join(children)}."
            return "I do not currently have a spouse or children, so my household is still mostly defined by the farm."
        dynasty = str(getattr(self.state, "dynasty_name", "") or f"{getattr(self.state, 'player_name', 'My')} family")
        generation = int(getattr(self.state, "player_generation", 1) or 1)
        history = list(getattr(self.state, "dynasty_history", []) or [])
        heirlooms = list(getattr(self.state, "dynasty_heirlooms", []) or [])
        return f"I am generation {generation} of the {dynasty}. Our records preserve {len(history)} earlier household head(s) and {len(heirlooms)} family heirloom(s)."

    def dialogue_disclosure_reaction(
        self, actor: Dict[str, object], kind: str, subject: str, repeated: bool
    ) -> str:
        if repeated:
            return "I remember you mentioning that before. The details matter more now that I have heard how they fit with the rest of your life."
        demeanor = self.dialogue_demeanor(actor, kind)
        subject_reactions = {
            "background": "That explains some of the habits and priorities you brought with you.",
            "deeds": "Those are concrete accomplishments. They tell me more than a title would.",
            "travels": "Travel changes what a person considers ordinary. I would be interested to hear how those places differed.",
            "loot": "Objects carry stories, though I care more about how you acquired them than their price.",
            "companions": "The company a person keeps says something about the risks and responsibilities they accept.",
            "family": "Thank you for telling me. Family changes the weight behind almost every long-term decision.",
            "ancestry": "A known lineage can provide direction, but it can also become an expectation you never chose.",
        }
        base = subject_reactions.get(subject, "That gives me a clearer sense of who you are.")
        tones = {
            "professional": "I appreciate the context. ",
            "warm": "I'm glad you told me. ",
            "skeptical": "I will take that as your account of it for now. ",
            "blunt": "That is more useful than vague boasting. ",
            "reserved": "I do not always know what to say to personal disclosures, but I listened. ",
            "wary": "I am not ready to treat every detail as proof, but I heard you. ",
            "hostile": "That does not make us friends, but it answers the question. ",
            "neutral": "I understand. ",
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
                "professional": "That is kind of you to say. I try to keep the public-facing part of the work dependable.",
                "warm": "Oh! Thank you. That genuinely made my day better.",
                "skeptical": "Thank you. I am not entirely sure what prompted that, but I will take it sincerely.",
                "blunt": "Thanks. Specific praise is more useful than flattery.",
                "reserved": "Thank you. I may not look comfortable receiving compliments, but I appreciate it.",
                "wary": "I will accept that at face value, for now.",
                "hostile": "Flattery does not erase our problems, but I heard you.",
                "neutral": "Thank you. That was thoughtful of you.",
            }[demeanor]
        return {
            "professional": "That was unnecessary. If you need a service, ask for it without abusing the person providing it.",
            "warm": "I was trying to be welcoming. There was no reason to make this cruel.",
            "skeptical": "There it is. I wondered how long the polite act would last.",
            "blunt": "If you wanted to be disliked, you could have saved time and said so immediately.",
            "reserved": "I have nothing further to say to you right now.",
            "wary": "That confirms I was right to be cautious around you.",
            "hostile": "Good. Now we understand one another. Leave me alone.",
            "neutral": "That was rude, and I am going to remember it.",
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
                    "This place feels different depending on who is passing through it.",
                ),
            )
            if not self.dialogue_say(self.dialogue_player_speaker(), observation, "you", transcript):
                return False
            return self.dialogue_say(actor, self.dialogue_library_line(actor, "weather", "player-smalltalk"), "response", transcript)
        compliment = action.startswith("compliment")
        player_line = {
            "compliment_work": "You seem to take your work seriously. I respect that.",
            "compliment_character": "You strike me as someone with qualities worth respecting.",
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
            reaction += " You have already made that attitude clear today, so repeating it changes nothing further."
        else:
            reaction += f" Relationship {relationship_change:+}; social reputation {reputation_change:+}."
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
            f"in {int(day_choice)} day{'s' if day_choice != '1' else ''}, at {due_hour:02d}:00. "
            "When you arrive, come speak with me so the time belongs to us instead of becoming another unchecked appointment.",
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
            f"You find {actor_name} at {place}. The appointment is no longer an entry in the Journal; both of you are physically here and have chosen to begin.",
            "arrival", transcript,
        ):
            return False
        opening = (
            "I'm glad you came. I would rather remember what we chose to do with this time than simply count it as courtship."
            if romantic else
            "You made it. We have enough time to do one thing deliberately instead of trying to fit an entire friendship into an afternoon."
        )
        if not self.dialogue_say(actor, opening, "date" if romantic else "outing", transcript):
            return False
        choices: List[DialogueOption] = [
            ("conversation", "Give them your full attention", "Talk honestly and listen without treating the meeting as a transaction."),
            ("exploration", "Explore the place together", "Walk the surroundings and make the destination part of the memory."),
            ("future", "Talk about future plans", "Discuss work, travel, home, and what each of you wants next."),
            ("back", "Not yet", "Return to the world without concluding the activity."),
        ]
        choice = self.dialogue_choose(
            actor,
            "How do you spend the time together?",
            "date" if romantic else "outing",
            choices,
            transcript,
        )
        if choice not in {"conversation", "exploration", "future"}:
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
            "conversation": "Thank you for being present. I feel as though you heard what I meant, not only the words I happened to choose.",
            "exploration": f"I will remember {place} differently now. A place becomes personal once someone else notices it beside you.",
            "future": "I like that we can talk about what comes next without pretending either of us already knows the entire answer.",
        }[choice]
        mood = {"conversation": "grateful", "exploration": "excited", "future": "hopeful"}[choice]
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
            response + (f" Relationship {relationship_gain:+}." if relationship_gain else ""),
            "reflection", transcript,
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
                invite_options.append(("done", "Finish the guest list", f"Invite {len(invited)} additional guest(s)."))
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
            f"The invited group has gathered at {place}: {names}. Their routes have genuinely converged here, and the ordinary versions of their schedules have yielded to this event.",
            "arrival", transcript,
        ):
            return False
        if not self.dialogue_say(
            host,
            "Everyone made time for this. Let us talk as a group instead of breaking into unrelated conversations immediately.",
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
                line = f"My next plan is to keep {self.dialogue_activity(attendee, attendee_kind)} from becoming something I only talk about doing."
            else:
                line = self.dialogue_library_line(attendee, "personal", "a story worth sharing")
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
            "That felt like time shared by a group, not several people standing in the same room. We should remember what everyone brought to it.",
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
        follower_id = self.dialogue_follower_id_for_actor(actor)
        household = kind in {"spouse", "child"} or str(actor.get("id", "")).startswith(("spouse:", "child:"))
        options: List[DialogueOption] = []
        if people:
            options.extend([
                ("introduction", "Ask for an introduction", "The selected person will recognize who sent you when you first meet."),
                ("message", "Ask them to carry a message", "Information is added to the recipient's sourced knowledge instead of teleporting the recipient."),
            ])
        if wilderness_places:
            options.append(("map", "Ask them to mark a known place", "Adds reliable map knowledge for a place this speaker has actually visited."))
        options.append(("meeting", "Arrange another meeting", "Creates a persistent follow-up for tomorrow."))
        if str(actor.get("id", "")) and kind != "child" and hasattr(self, "schedule_planned_event"):
            options.append(("walk", "Spend some time together", "The speaker temporarily accompanies you in the world for two hours."))
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
        follower_already_active = bool(
            follower_id and hasattr(self, "active_travel_follower_ids")
            and follower_id in self.active_travel_follower_ids()
        )
        if navigable_places and str(actor.get("id", "")) and not follower_already_active:
            options.append(("guide", "Ask them to guide you somewhere", "Creates a tracked journey; follow them to a place they genuinely know."))
        if follower_id and hasattr(self, "set_travel_follower"):
            options.append(("travel", "Ask them to travel with you", "Uses the existing follower eligibility, safety, and party-size rules."))
        if household and hasattr(self, "family_outing_menu"):
            options.append(("outing", "Plan a family outing", "Choose a real activity and calendar date with eligible family members."))
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
                        "purpose": "that you wanted a proper introduction instead of approaching as a complete stranger",
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
                "description": f"Travel with {self.dialogue_actor_name(actor)} to a place they know, then speak with them on arrival.",
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
                "status": "ready", "quest_id": quest_id,
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
                f"I know the way to {place.get('name', 'that place')}. Stay close; once we arrive, speak to me and we will call the journey complete.",
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
                "Good. It is on the calendar now, which means we can plan around it instead of merely hoping everyone is free."
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

    def dialogue_handle_household_topic(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        actor_id = str(actor.get("id", ""))
        is_spouse = actor_id == str(getattr(self.state, "spouse_npc_id", "") or "")
        options: List[DialogueOption] = [
            ("plans", "Compare today's plans", "Talk through routines, assigned work, and who expects to be home."),
            ("safety", "Talk about safety and travel", "Discuss active danger, expeditions, and time away from home."),
            ("finances", "Review household finances", "Discuss current money, property, and the pressure of future plans."),
            ("memory", "Recall something you shared", "Draw from recorded outings and family history."),
            ("outing", "Plan time together", "Open the real family-outing calendar."),
            ("dashboard", "Review the household together", "Open the household dashboard from inside the conversation."),
            ("meal", "Suggest eating together", "Use the real family-meal system if everyone is available."),
        ]
        if is_spouse and bool(getattr(self.state, "pregnancy_active", False)):
            options.append(("pregnancy", "Check in about the pregnancy", "Discuss the current month and household preparations."))
        if is_spouse and bool(getattr(self.state, "spouse_moved_to_farm", False)):
            options.append(("support", "Reconsider how you support each other", "Review the spouse's current household support role."))
        options.append(("back", "Talk about something else", "Return to the conversation."))
        choice = self.dialogue_choose(actor, "What should the household discuss?", "household", options, transcript)
        if not choice or choice == "back":
            return True
        if choice == "plans":
            line = f"Today I'm {self.dialogue_activity(actor, kind)}. I'd rather tell you directly than make you guess where the day took me."
        elif choice == "safety":
            follower_count = len(getattr(self.state, "travel_follower_ids", []) or [])
            line = f"I know exploration matters to you. Just remember that {follower_count} companion(s) and this household plan around whether you return safely."
            self.dialogue_set_mood(actor, kind, "worried", "the danger surrounding your travels", 1, 2)
        elif choice == "finances":
            properties = len(getattr(self.state, "player_properties", {}) or {})
            line = f"We currently have {int(getattr(self.state, 'money', 0))}g and {properties} additional property record(s). I care less about a perfect number than whether we agree what the money is for."
        elif choice == "memory":
            family_state = getattr(self.state, "family_world_state", {}) or {}
            history = family_state.get("outing_history", []) if isinstance(family_state, dict) else []
            if history:
                memory = history[-1]
                line = f"I still think about {memory.get('type', 'our outing')} at {memory.get('destination', 'that place')}. Shared time changes the household in ways chores do not."
            else:
                line = "We have not recorded a family outing yet. I would like us to make a memory that is more specific than simply getting through the week."
        elif choice == "outing":
            result = self.family_outing_menu() if hasattr(self, "family_outing_menu") else None
            line = "The plan is on our calendar now." if result and str(result) != "__BACK__" else "We can decide on the outing later."
        elif choice == "dashboard":
            result = self.family_world_dashboard_menu() if hasattr(self, "family_world_dashboard_menu") else None
            line = "It helps to look at the household as something we coordinate together." if result != "changed" else "Good. We changed the household plan together."
        elif choice == "meal":
            result = self.family_meal_menu() if hasattr(self, "family_meal_menu") else None
            line = "Sharing a meal gave us time that chores would otherwise have swallowed." if result == "changed" else str(getattr(self.state, "message", "We can eat together another time."))
        elif choice == "pregnancy":
            changed = bool(self.complete_pregnancy_checkup(actor)) if hasattr(self, "complete_pregnancy_checkup") else False
            line = "I'm glad we checked in instead of treating the pregnancy as a calendar entry." if changed else f"The pregnancy is in month {self.pregnancy_month_number()}; the due date is {self.pregnancy_due_date_label()}."
        else:
            result = self.spouse_support_menu() if hasattr(self, "spouse_support_menu") else None
            line = "Our support plan changed because we discussed what the household actually needs." if result == "changed" else "We can keep the current support arrangement for now."
        slot = self.dialogue_social_slot(actor, kind)
        today = self.dialogue_absolute_day()
        if int(slot.get("last_household_checkin_day", 0) or 0) != today:
            slot["last_household_checkin_day"] = today
            gained = self.dialogue_adjust_actor_relationship(actor, kind, 1)
            if gained:
                line += f" Relationship {gained:+}."
        return self.dialogue_say(actor, line, "household", transcript)

    def dialogue_handle_relationship_topic(
        self, actor: Dict[str, object], kind: str, transcript: List[Dict[str, str]]
    ) -> bool:
        actor_id = str(actor.get("id", ""))
        supported = bool(
            actor_id
            and kind in {"authored", "procedural", "spouse"}
            and hasattr(self, "town_npc_relationship")
        )
        if not supported:
            return self.dialogue_say(
                actor,
                "We can talk, but our connection does not use the town's courtship or household systems.",
                "relationship", transcript,
            )
        relationship = int(self.town_npc_relationship(actor_id))
        marriageable = bool(hasattr(self, "is_marriageable_npc") and self.is_marriageable_npc(actor))
        is_spouse = actor_id == str(getattr(self.state, "spouse_npc_id", "") or "")
        is_engaged = actor_id == str(getattr(self.state, "engaged_npc_id", "") or "")
        gifted_today = getattr(self.state, "town_npc_last_gift_day", {}).get(actor_id) == self.town_npc_day_key()
        options: List[DialogueOption] = [
            ("status", "Ask how they see your relationship", "Discuss the current bond and what would naturally deepen it."),
        ]
        if not gifted_today:
            options.append(("gift", "Offer them a gift", "Choose one carried item and return to the conversation afterward."))
        court_ok, _court_reason = self.can_court_town_npc(actor) if marriageable else (False, "")
        has_planned_date = bool(
            hasattr(self, "open_planned_events_for_actor")
            and self.open_planned_events_for_actor(actor_id, ("relationship_date",))
        )
        if court_ok and not has_planned_date:
            label = "Plan a date together" if is_spouse or actor_id in set(self.state.dating_npc_ids or []) else "Invite them on a personal outing"
            options.append(("courtship", label, "Choose a real destination, day, and time; courtship advances only after you meet there."))
        proposal_ok, _proposal_reason = self.can_propose_to_town_npc(actor) if marriageable else (False, "")
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
        choice = self.dialogue_choose(actor, "What do you want to discuss about your relationship?", "relationship", options, transcript)
        if not choice or choice == "back":
            return True
        if choice == "status":
            friendship = self.town_npc_friendship_label(relationship)
            romance = self.romance_label_for_npc(actor) if marriageable else "Platonic"
            readiness = ""
            planned_dates = self.open_planned_events_for_actor(actor_id, ("relationship_date",)) if hasattr(self, "open_planned_events_for_actor") else []
            if planned_dates:
                plan = planned_dates[0]
                destination = dict(plan.get("destination", {}) or {})
                readiness = (
                    f" We already have {str(plan.get('title', 'time together')).lower()} planned at "
                    f"{destination.get('label', destination.get('location', 'the agreed place'))}."
                )
            if marriageable and not is_spouse and not is_engaged:
                _ok, reason = self.can_propose_to_town_npc(actor)
                readiness += f" As for marriage: {reason}"
            return self.dialogue_say(
                actor,
                f"I would call us {friendship.lower()} right now. Our relationship is {romance.lower()}. I care more about what we consistently do than a number, but the current bond is {relationship}.{readiness}",
                "relationship", transcript,
            )
        if choice == "gift":
            success = bool(
                self.procedural_town_resident_gift_menu(actor)
                if kind == "procedural" and hasattr(self, "procedural_town_resident_gift_menu")
                else self.give_gift_to_town_npc(actor)
            )
            response = (
                "Thank you. The fact that you chose this during an actual conversation makes the gesture feel less transactional."
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
            if hasattr(self, "family_wedding_planning_menu"):
                self.family_wedding_planning_menu()
            return self.dialogue_say(actor, f"Our wedding remains part of our shared plans: {self.wedding_date_label()}.", "relationship", transcript)
        if choice == "move_in":
            success = bool(self.invite_spouse_to_farm(actor))
            response = (
                "Yes. I want the farmhouse to become our shared home, without either of us giving up the rest of who we are."
                if success else str(getattr(self.state, "message", "We cannot change households right now."))
            )
            return self.dialogue_say(actor, response, "relationship", transcript)
        if choice == "family":
            self.family_planning_menu(actor)
            return self.dialogue_say(actor, "I'm glad we treated that as a conversation between us, not a switch hidden in a household menu.", "relationship", transcript)
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
                ("opportunities", "Do you have any work for me?", "Ask about a real request or current need."),
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
                return "I don't know the surrounding places well enough to direct you responsibly."
            options = [(str(place["id"]), str(place["name"]), str(place.get("district", "A place they know"))) for place in places]
            options.append(("back", "Ask about something else", "Return to the conversation."))
            selected = self.dialogue_choose(actor, "Where are you trying to go?", "questions", options, transcript)
            place = next((value for value in places if str(value["id"]) == selected), None)
            return self.dialogue_direction_answer(actor, place) if place else None
        if topic == "people":
            people = self.dialogue_known_people(actor, kind)
            if not people:
                return "I know people through my routine, but no one I know well is a subject I should speak for today."
            options = [(str(person.get("id", person.get("name"))), str(person.get("name", "Someone")), str(person.get("role", "Someone they know"))) for person in people]
            options.append(("back", "Ask about someone else later", "Return to the conversation."))
            selected = self.dialogue_choose(actor, "Who did you want to ask about?", "questions", options, transcript)
            person = next((value for value in people if str(value.get("id", value.get("name"))) == selected), None)
            if person:
                return f"I know {person.get('name', 'them')} through family or the routines we share. {self.dialogue_actor_name(person)} works as a {self.dialogue_actor_role(person).lower()}, and I would rather let them explain the private parts of their life themselves. {self.dialogue_library_line(actor, 'people', str(person.get('id', 'person')))}"
            return None
        return None

    def dialogue_farewell(self, actor: Dict[str, object], kind: str) -> str:
        if self.dialogue_is_family_or_companion(actor, kind):
            return ""
        tier = self.dialogue_familiarity_label(actor, kind)
        demeanor = self.dialogue_demeanor(actor, kind)
        if tier in {"Close", "Trusted"}:
            close_pools = {
                "warm": ("I'm glad you stopped. Take care.", "Come back when you have more time."),
                "blunt": ("Good talk. You know where to find me.", "That was useful. Take care."),
                "reserved": ("Thank you for coming by. I mean that.", "I'll see you again."),
                "skeptical": ("You gave me something to think about. Take care.", "We can continue this when we know more."),
            }
            return _stable_pick(
                f"{self.dialogue_day_key()}:{actor.get('id')}:farewell:close:{demeanor}",
                close_pools.get(demeanor, ("Take care. I mean that.", "We'll continue this another time.")),
            )
        pools = {
            "professional": ("Thank you. Let me know if you need anything else.", "Take care, and have a good day."),
            "warm": ("It was good talking with you. Take care!", "I hope we speak again soon."),
            "skeptical": ("We'll leave it there for now.", "I have heard enough to think about."),
            "blunt": ("That's enough for now.", "I should get back to what I was doing."),
            "reserved": ("Goodbye.", "Thank you for the conversation."),
            "wary": ("We're finished here.", "That is all I am willing to discuss."),
            "hostile": ("Leave me alone now.", "This conversation is over."),
            "neutral": ("Take care on the road.", "I'll see you around town."),
        }
        return _stable_pick(
            f"{self.dialogue_day_key()}:{actor.get('id')}:farewell:{demeanor}", pools[demeanor]
        )

    def run_unified_npc_conversation(
        self,
        actor: Dict[str, object],
        *,
        kind: str = "authored",
        first_meeting: bool = False,
        repeated_today: bool = False,
        agenda_override: str = "",
    ) -> Dict[str, object]:
        actor["_dialogue_kind"] = str(kind)
        active_thread = self.dialogue_current_thread(actor, kind, create=True)
        group_partner = self.dialogue_nearby_group_partner(actor, kind)
        if group_partner:
            actor["_dialogue_group_partner"] = group_partner
        transcript: List[Dict[str, str]] = []
        discussed: List[str] = []

        def finish(completed: bool) -> Dict[str, object]:
            actor["recent_conversation_topics"] = (
                list(actor.get("recent_conversation_topics", []) or []) + discussed
            )[-12:]
            actor.pop("_dialogue_kind", None)
            actor.pop("_dialogue_group_partner", None)
            self._last_dialogue_transcript = transcript
            self.invalidate_draw_cache()
            return {"completed": completed, "topics": discussed, "transcript": transcript}

        greeting = self.dialogue_greeting(actor, kind, first_meeting, repeated_today)
        if greeting and not self.dialogue_say(actor, greeting, "greeting", transcript):
            return finish(False)
        self.dialogue_prepare_initiation(actor, kind)
        initiation_slot = self.dialogue_social_slot(actor, kind)
        initiation_record = initiation_slot.get("initiation", {})
        initiation_reason = str(initiation_record.get("reason", "")) if isinstance(initiation_record, dict) else ""
        initiated = self.dialogue_accept_initiation(actor, kind)
        if initiated and not self.dialogue_say(actor, initiated, "they approached you", transcript):
            return finish(False)
        invitation = initiation_slot.get("invitation", {})
        if (
            initiation_reason == "invitation"
            and isinstance(invitation, dict)
            and str(invitation.get("status", "")) == "pending"
            and not self.dialogue_handle_npc_invitation(actor, kind, invitation, transcript)
        ):
            return finish(False)
        if not first_meeting:
            callback = self.dialogue_promise_callback(actor, kind)
            if callback and not self.dialogue_say(actor, callback, "follow-up", transcript):
                return finish(False)
        if not first_meeting and not self.dialogue_is_family_or_companion(actor, kind):
            if not self.dialogue_say(actor, self.dialogue_chitchat(actor, kind), "chit-chat", transcript):
                return finish(False)
        agenda = str(agenda_override or self.dialogue_agenda(actor, kind))
        if agenda and not self.dialogue_say(actor, agenda, "main subject", transcript):
            return finish(False)
        initial = self.dialogue_choose(actor, "How would you like to continue?", "main subject", [
            ("ask", "Ask them to explain", "Stay with the subject they introduced."),
            ("help", "Ask whether they need help", "Find out whether the subject leads to actual work."),
            ("topics", "Ask about something else", "Open the general question list."),
            ("goodbye", "End the conversation", "Let the exchange end here."),
        ], transcript)
        if initial == "ask":
            discussed.append("agenda")
            if active_thread and not agenda_override:
                if not self.dialogue_handle_thread(actor, kind, active_thread, transcript):
                    return finish(True)
            elif not self.dialogue_say(actor, self.dialogue_work_answer(actor, kind, False), "main subject", transcript):
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
            topic = self.dialogue_choose(
                actor,
                "What would you like to ask about?",
                "questions",
                self.dialogue_topic_options(actor, kind),
                transcript,
            )
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
        if first_talk_today and self.maybe_play_scene_for_context({"type": "npc_talk", "npc": npc, "npc_id": npc_id}):
            self.state.town_npc_dialogue_counts[npc_id] = prior_count + 1
            self.state.town_npc_last_talk_day[npc_id] = today
            self.adjust_town_npc_relationship(npc_id, RELATIONSHIP_TALK_GAIN)
            self.autosave_with_message(self.state.message or f"Shared a moment with {npc.get('name', 'the villager')}.")
            return
        result = self.run_unified_npc_conversation(
            npc,
            kind="spouse" if npc_id == str(getattr(self.state, "spouse_npc_id", "")) else "authored",
            first_meeting=prior_count <= 0,
            repeated_today=not first_talk_today,
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
            agenda_override=f"I was {self.spouse_household_activity_label(resident).replace('their ', 'my ')}. I wanted to make sure we were not each carrying a different version of today's household plan.",
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


__all__ = ["DialogueFlowMixin", "ROLE_INTERESTS"]
