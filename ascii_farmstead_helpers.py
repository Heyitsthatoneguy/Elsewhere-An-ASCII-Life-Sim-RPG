from __future__ import annotations

"""Pure helper functions for Elsewhere.

Helpers in this module may depend on static data and support utilities, but
should not import the main game class. That keeps future systems from forming
circular imports around FarmGame.
"""

import random
import re
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_support import C
from ascii_farmstead_data import (
    CALENDAR_EVENTS,
    CROP_DATA,
    FISH_DATA,
    FISH_ITEMS,
    FESTIVAL_DATA,
    FOOD_DATA,
    MINE_FLOOR_THEMES,
    MONTH_NAMES,
    SEASON_WEATHER_TABLES,
    SEASON_PROFILE_DATA,
    WEEKDAY_NAMES,
    WILDERNESS_BIOME_DESCRIPTIONS,
    WILDERNESS_BIOME_NAMES,
    WILDERNESS_FORAGE_DATA,
)


# Inventory keys are intentionally stable identifiers, so many are stored in a
# convenient singular form ("Copper Bar") or an established plural form
# ("Cave Herbs") regardless of stack size. Player-facing prose should not
# expose that implementation detail. Keep the grammar here so dialogue,
# quests, rewards, and menus all describe the same stack naturally.
_ITEM_MASS_OR_INVARIANT_NAMES = {
    "Animal Feed", "Any Fish", "Bait", "Basic Fertilizer", "Clay", "Coal",
    "Copper Ore", "Corn", "Equipment", "Fiber", "Flour", "Furniture", "Glass", "Gold Ore",
    "Hardwood", "Hay", "Honey", "Iron Ore", "Kale", "Lumber", "Maple",
    "Medicine", "Milk", "Oil", "Ore", "Quartz", "Rice", "Salt", "Sap",
    "Soft Fiber", "Stone", "Sugar", "Watercress", "Wheat", "Wood", "Wool",
}

_ITEM_SINGULAR_OVERRIDES = {
    "Berries": "Berry",
    "Cave Herbs": "Cave Herb",
    "Metal Fittings": "Metal Fitting",
    "Mushrooms": "Mushroom",
    "Pine Nuts": "Pine Nut",
    "Strange Spores": "Strange Spore",
    "Supplies": "Supply",
    "supplies": "supply",
    "Wagon Parts": "Wagon Part",
    "Wild Berries": "Wild Berry",
    "Wild Herbs": "Wild Herb",
    "Wildflowers": "Wildflower",
}

_ITEM_PLURAL_OVERRIDES = {
    singular: plural for plural, singular in _ITEM_SINGULAR_OVERRIDES.items()
}
_ITEM_PLURAL_OVERRIDES.update({
    "Leaf": "Leaves",
    "Knife": "Knives",
    "Loaf": "Loaves",
    # A mass noun keeps its form: "2 Winter Wheats" is not a quantity anyone says.
    "Winter Wheat": "Winter Wheat",
})


def item_name_for_quantity(item_name: object, quantity: object) -> str:
    """Return an inventory item's natural singular or plural display name.

    Unknown/custom items receive conservative English suffix handling, while
    known mass nouns, fish species, and established plural inventory keys keep
    their intended form. This changes presentation only; save-file keys remain
    untouched.
    """
    name = str(item_name or "item").strip() or "item"
    try:
        count = int(quantity)
    except (TypeError, ValueError):
        count = 1

    if count == 1:
        if name in _ITEM_SINGULAR_OVERRIDES:
            return _ITEM_SINGULAR_OVERRIDES[name]
        if name.endswith(" Seeds"):
            return name[:-1]
        return name

    if name in _ITEM_MASS_OR_INVARIANT_NAMES or (
        name in FISH_DATA and not bool(FISH_DATA.get(name, {}).get("junk", False))
    ):
        return name
    if name in _ITEM_SINGULAR_OVERRIDES:
        return name
    if name in _ITEM_PLURAL_OVERRIDES:
        return _ITEM_PLURAL_OVERRIDES[name]
    if name.endswith(" Seed"):
        return f"{name}s"

    head, separator, final_word = name.rpartition(" ")
    word = final_word if separator else name
    lower = word.lower()
    # A custom item already supplied in plural form should not gain another s.
    if lower.endswith("s") and not lower.endswith(("ss", "us")):
        plural_word = word
    elif len(word) > 1 and lower.endswith("y") and lower[-2] not in "aeiou":
        plural_word = f"{word[:-1]}ies"
    elif lower.endswith(("ch", "sh", "x", "z", "ss", "us")):
        plural_word = f"{word}es"
    else:
        plural_word = f"{word}s"
    return f"{head} {plural_word}" if separator else plural_word


_PRONOUN_SETS = {
    "female": ("she", "her", "her", "hers", "herself"),
    "male": ("he", "him", "his", "his", "himself"),
}
_NEUTRAL_PRONOUNS = ("they", "them", "their", "theirs", "themselves")


_KINSHIP_TERMS = {
    "spouse": ("wife", "husband", "spouse"),
    "child": ("daughter", "son", "child"),
    "sibling": ("sister", "brother", "sibling"),
    "parent": ("mother", "father", "parent"),
    "grandparent": ("grandmother", "grandfather", "grandparent"),
    "grandchild": ("granddaughter", "grandson", "grandchild"),
    "nibling": ("niece", "nephew", "niece or nephew"),
    "pibling": ("aunt", "uncle", "aunt or uncle"),
}


def kinship_term(relation: object, sex: object) -> str:
    """Return the gendered word for a family relation, or the neutral fallback.

    "My wife" reads as a person; "my spouse" reads as a form. Use this wherever a
    specific known relative is being referred to. Keep the neutral word where no
    such person exists yet ("I don't have a spouse") or where the text states a
    rule rather than describing someone ("a pregnancy requires a spouse").
    """
    female, male, neutral = _KINSHIP_TERMS.get(
        str(relation or "").strip().casefold(), ("", "", str(relation or "")),
    )
    folded = str(sex or "").strip().casefold()
    if folded == "female" and female:
        return female
    if folded == "male" and male:
        return male
    return neutral


def pronouns_for_sex(sex: object) -> Dict[str, str]:
    """Return the pronoun set for a character whose sex the game knows.

    Anything unset or unrecognised falls back to they/them, which is both
    correct English and the right answer when the game genuinely does not know.

    Callers must mind verb agreement when substituting: the neutral set takes
    plural forms ("they were", "they have") while the gendered sets take
    singular ("she was", "he has"). A template that hard-codes one or the other
    cannot simply swap the pronoun.
    """
    forms = _PRONOUN_SETS.get(str(sex or "").strip().casefold(), _NEUTRAL_PRONOUNS)
    subject, obj, possessive, possessive_pronoun, reflexive = forms
    return {
        "subject": subject,
        "object": obj,
        "possessive": possessive,
        "possessive_pronoun": possessive_pronoun,
        "reflexive": reflexive,
        "plural_agreement": forms is _NEUTRAL_PRONOUNS,
    }


def clause_from_sentence(text: object) -> str:
    """Return a standalone task line as a clause that can sit mid-sentence.

    Objective descriptions are stored capitalised and full-stopped because they
    are shown as their own row in a quest list ("Catch 3 freshwater fish."). The
    same string is also spoken inside a longer sentence, where that shape reads
    as "waiting for you to Catch 3 freshwater fish." Only the leading character
    is lowered, so proper nouns further along ("Bring 2 Berries to Mara") keep
    their capitals.
    """
    line = " ".join(str(text or "").split()).rstrip(".")
    if not line:
        return ""
    return line[:1].lower() + line[1:]


def quantity_item_phrase(item_name: object, quantity: object) -> str:
    """Format a stack count without changing its canonical inventory key."""
    try:
        count = int(quantity)
    except (TypeError, ValueError):
        count = 0
    return f"{count} {item_name_for_quantity(item_name, count)}"


def naturalize_item_quantity_text(text: object, item_name: object, quantity: object) -> str:
    """Repair a legacy saved sentence containing a raw count plus item key."""
    rendered = str(text or "")
    name = str(item_name or "item").strip() or "item"
    try:
        count = int(quantity)
    except (TypeError, ValueError):
        count = 0
    return rendered.replace(f"{count} {name}", quantity_item_phrase(name, count))


# "'ve" is licensed only before a past participle, however many adverbs sit
# between: "I've never quite finished" is fine, "I've a horse" is not. The
# naturalizer contracts on sight, so this is the check that keeps its guards
# honest -- it is what "do you've a few minutes to spare?" would trip today.
_PAST_PARTICIPLES = (
    "been|seen|gone|done|had|got|gotten|made|taken|given|come|found|said|told|known|become|"
    "left|put|kept|heard|brought|thought|run|won|lost|met|read|written|spoken|eaten|forgotten|"
    "chosen|driven|ridden|fallen|grown|drawn|flown|worn|torn|sworn|borne|shown|sown|blown|thrown|"
    "begun|drunk|sung|sunk|swum|rung|hung|held|felt|meant|sent|spent|built|burnt|learnt|dealt|"
    "slept|swept|wept|crept|leapt|dreamt|paid|laid|sold|stood|understood|withstood|caught|taught|"
    "fought|sought|bought|beaten|bitten|hidden|risen|struck|stuck|swung|dug|clung|spun|stung|shot|"
    "hit|cut|set|let|cost|quit|split|spread|shut|burst|"
    r"\w+ed"
)
_PARTICIPLE_ADVERBS = (
    r"(?:never|already|always|just|still|ever|recently|finally|nearly|almost|barely|hardly|only|"
    r"often|since|long|yet|simply|actually|really|certainly|probably|apparently|clearly|mostly|"
    r"largely|quietly|slowly|quickly|happily|gladly|not|no|about|quite|rather|fully|"
    r"entirely|honestly|genuinely|somehow|definitely|surely|truly|well|once|scarcely|"
    r"seldom|rarely|generally|usually|occasionally|thoroughly|properly|briefly|lately)\s+"
)
_LICENSED_VE = re.compile(
    r"'ve\s+(?:%s)*(?:%s)\b" % (_PARTICIPLE_ADVERBS, _PAST_PARTICIPLES), re.I
)
_ANY_VE = re.compile(r"\b\w+'ve\b", re.I)


def overcontraction_warnings(spoken: object) -> Tuple[str, ...]:
    """Flag contractions English does not license, in already-naturalized text.

    Pass the output of ``naturalize_spoken_dialogue``: the source line is always
    written out in full, so a bad contraction can only appear after that pass.
    """
    text = str(spoken or "")
    if "'ve" not in text and "'VE" not in text.upper():
        return ()
    found = []
    for match in _ANY_VE.finditer(text):
        tail = text[match.start():]
        contraction_start = tail.lower().index("'ve")
        if not _LICENSED_VE.match(tail[contraction_start:]):
            found.append(
                "%s: 've needs a past participle after it, not %r"
                % (match.group(0), tail.split()[1] if len(tail.split()) > 1 else "")
            )
    return tuple(found)


# An activity phrase is shown third-person ("Rowan is mending the fence") and
# spoken first-person after a plain .replace("their ", "my "). Any other
# third-person marker survives that swap and mixes the two persons, which is how
# "protecting the deliberate change they added to my routine" happened. Written
# without backslash escapes on purpose.
_THIRD_PERSON_MARKERS = re.compile(
    "(?<![a-zA-Z])(they|them|their|theirs|themselves)(?![a-zA-Z])", re.I
)


def first_person_warnings(activity: object) -> Tuple[str, ...]:
    """Flag an activity phrase that cannot survive being spoken in first person.

    The safe style is pronoun-free, which is what most authored activities
    already are; "their" alone is fine because the swap handles it.
    """
    text = str(activity or "")
    if not text:
        return ()
    spoken = text.replace("their ", "my ").replace("Their ", "My ")
    return tuple(
        "%s survives the first-person swap: 'I am %s'" % (match.group(1), spoken)
        for match in _THIRD_PERSON_MARKERS.finditer(spoken)
    )


# Placeholders whose rendered value changes with a count: a joined name list is
# singular with one child and plural with two, and a raw count is 1 as often as
# it is 5.  A verb or noun written straight after one of these has to agree with
# something the template cannot see, so each has an agreement key beside it that
# the context builder fills using quantity_agreement.
COUNT_VARYING_PLACEHOLDERS: Dict[str, Tuple[str, ...]] = {
    "children": ("children_are", "children_have"),
    "child_count": (),
    "claim_count": ("claim_label",),
    "property_count": ("property_label",),
    "automation_count": ("automation_label",),
}

# Verbs that inflect for number. "will", "could" and the rest are absent on
# purpose: a modal is safe after any subject.
_NUMBER_INFLECTED = (
    "is|are|was|were|has|have|does|do|need|needs|want|wants|keep|keeps|seem|seems|"
    "live|lives|know|knows|make|makes|take|takes|come|comes|go|goes|look|looks|"
    "feel|feels|stay|stays|grow|grows|get|gets|say|says|think|thinks|sound|sounds"
)
# After a preposition the placeholder is an object, not the subject, so the verb
# that follows belongs to something else entirely: "Watching you with {children}
# is the part..." is correct and must not be flagged.
_OBJECT_MARKERS = (
    "with|for|to|of|from|about|at|around|among|near|like|between|before|after|"
    "since|than|as|on|in|by|without|beside|behind|toward|towards|into|onto"
)
_SUBJECT_VERB = re.compile(
    r"(?<!\w)(?:(?P<prep>%s)\s+)?\{(?P<name>children)\}\s+(?P<verb>%s)\b"
    % (_OBJECT_MARKERS, _NUMBER_INFLECTED)
)
_COUNT_NOUN = re.compile(
    r"\{(?P<name>\w*count)\}\s+(?P<word>[a-z]\w*)"
)


def agreement_warnings(template: object) -> Tuple[str, ...]:
    """Flag wording that cannot agree with a count the template cannot see.

    Catches two shapes: a count-varying placeholder used as the subject of a
    number-inflected verb ("{children} are"), and a raw count followed by a
    hardcoded noun ("{property_count} properties", which reads "1 properties").
    The fix for both is the agreement key named in the warning.
    """
    text = str(template or "")
    if not text:
        return ()
    found = []
    for match in _SUBJECT_VERB.finditer(text):
        if match.group("prep"):
            continue
        keys = COUNT_VARYING_PLACEHOLDERS.get(match.group("name"), ())
        found.append(
            "{%s} %s: use an agreement key (%s) instead of a fixed verb"
            % (match.group("name"), match.group("verb"), ", ".join(keys) or "none defined")
        )
    for match in _COUNT_NOUN.finditer(text):
        word = match.group("word")
        if re.fullmatch(_NUMBER_INFLECTED, word) or word in _OBJECT_MARKERS.split("|"):
            continue        # a verb or preposition here, not a noun to pluralize
        keys = COUNT_VARYING_PLACEHOLDERS.get(match.group("name"), ())
        if not keys:
            continue
        # An adjective may sit between the count and its label, as in
        # "{property_count} outside {property_label}"; the phrase is agreeing
        # already, so only complain when no key appears before the sentence ends.
        clause = text[match.start():]
        stop = re.search(r"[.!?]", clause)
        if stop is not None:
            clause = clause[:stop.start()]
        if any(("{" + key + "}") in clause for key in keys):
            continue
        found.append(
            "{%s} %s: pluralize with %s so a count of 1 still reads"
            % (match.group("name"), word, ", ".join(keys))
        )
    return tuple(found)


def name_list(names: object) -> str:
    """Join names the way a person says them: "A", "A and B", "A, B, and C"."""
    items = [str(name).strip() for name in (names or ()) if str(name).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return "%s and %s" % (items[0], items[1])
    return "%s, and %s" % (", ".join(items[:-1]), items[-1])


def quantity_agreement(quantity: object, singular: str, plural: Optional[str] = None) -> str:
    """Choose count-aware wording, preserving the older word-only call form.

    Two arguments produce a complete phrase such as ``1 day`` or ``2 days``.
    Supplying an explicit plural retains the original behavior and returns only
    the agreeing word, which existing callers use after rendering the count.
    """
    try:
        count = int(quantity)
    except (TypeError, ValueError):
        count = 0
    if plural is None:
        return quantity_item_phrase(singular, count)
    return singular if count == 1 else plural


def calendar_events_for(month: int, day: int, year: int) -> List[str]:
    events = list(CALENDAR_EVENTS.get((month, day), []))
    events.extend(
        str(festival.get("name", "Festival"))
        for festival in FESTIVAL_DATA.values()
        if int(festival.get("month", 0)) == int(month)
        and int(festival.get("day", 0)) == int(day)
    )
    if day == 1:
        events.append("Monthly seed stock reminder")
    if day == days_in_month(month, year):
        events.append("Last day of the month")
    return events

def wilderness_biome_name(tile: str) -> str:
    return WILDERNESS_BIOME_NAMES.get(tile, "Wilderness")

def wilderness_biome_description(tile: str, season: str) -> str:
    return WILDERNESS_BIOME_DESCRIPTIONS.get(tile, {}).get(season, wilderness_biome_name(tile))

def forage_symbols_for_season(season: str) -> List[str]:
    symbols: List[str] = []
    for symbol, data in WILDERNESS_FORAGE_DATA.items():
        if season in data["seasons"]:
            symbols.extend([symbol] * int(data.get("weight", 1)))
    return symbols or ["h"]

def forage_item_for_symbol(symbol: str) -> Optional[str]:
    data = WILDERNESS_FORAGE_DATA.get(symbol)
    return data.get("item") if data else None

def forage_description_for_symbol(symbol: str) -> str:
    data = WILDERNESS_FORAGE_DATA.get(symbol)
    if not data:
        return "Wild forage."
    return data.get("description", data.get("item", "Wild forage."))

def is_fish_item(item_name: str) -> bool:
    return item_name in FISH_DATA

def fish_sell_price(item_name: str) -> int:
    return int(FISH_DATA.get(item_name, {}).get("price", 0))

def fish_stamina_value(item_name: str) -> int:
    return int(FISH_DATA.get(item_name, {}).get("stamina", 0))

def fishing_time_bucket(hour: int) -> str:
    if 6 <= hour < 12:
        return "Morning"
    if 12 <= hour < 18:
        return "Day"
    return "Night"

def mine_theme_for_floor(floor: int) -> str:
    theme = "Upper Caves"
    for min_floor, name in MINE_FLOOR_THEMES:
        if floor >= min_floor:
            theme = name
    return theme

def mine_floor_resource_weights(floor: int) -> List[str]:
    weights: List[str] = ["r"] * max(4, 10 - floor // 6)
    weights += ["O"] * (4 + floor // 5)
    if floor >= 6:
        weights += ["I"] * (2 + floor // 8)
    if floor >= 12:
        weights += ["q"] * (2 + floor // 10)
    if floor >= 18:
        weights += ["c"] * 3
    if floor >= 24:
        weights += ["G"] * (2 + floor // 12)
    if floor >= 32:
        weights += ["M"] * 2
    if floor % 5 == 0:
        weights += ["g"] * 3
    return weights

def mine_node_label(tile: str) -> str:
    return {
        "r": "loose rock",
        "O": "copper seam",
        "I": "iron seam",
        "G": "gold seam",
        "M": "deep mixed ore seam",
        "q": "coal seam",
        "c": "crystal cluster",
        "g": "gem node",
        "B": "barrel",
    }.get(tile, "mine node")

def is_food_item(item_name: str) -> bool:
    return food_stamina_value(item_name) > 0

def food_stamina_value(item_name: str) -> int:
    if item_name in FOOD_DATA:
        return int(FOOD_DATA.get(item_name, {}).get("stamina", 0))
    if item_name in FISH_DATA:
        return fish_stamina_value(item_name)
    return 0

def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def days_in_month(month: int, year: int) -> int:
    if month == 2:
        return 29 if is_leap_year(year) else 28
    if month in [4, 6, 9, 11]:
        return 30
    return 31

def season_for_month(month: int) -> str:
    if month in [3, 4, 5]:
        return "Spring"
    if month in [6, 7, 8]:
        return "Summer"
    if month in [9, 10, 11]:
        return "Fall"
    return "Winter"


def season_daylight_window(season: str) -> tuple[int, int]:
    """Return the readable whole-hour sunrise and sunset for a season."""
    profile = SEASON_PROFILE_DATA.get(str(season), SEASON_PROFILE_DATA["Spring"])
    return int(profile.get("sunrise", 6)), int(profile.get("sunset", 19))


def crop_seasons(crop: object) -> List[str]:
    """Return every season in which a crop can grow, preserving old data."""
    data = CROP_DATA.get(str(crop), {}) if not isinstance(crop, dict) else crop
    explicit = data.get("seasons", []) if isinstance(data, dict) else []
    if isinstance(explicit, (list, tuple, set)) and explicit:
        return [str(value) for value in explicit if str(value)]
    primary = str(data.get("season", "")) if isinstance(data, dict) else ""
    return [primary] if primary else []


def crop_valid_for_season(crop: object, season: str) -> bool:
    seasons = crop_seasons(crop)
    return "Any" in seasons or str(season) in seasons


def crop_season_label(crop: object) -> str:
    seasons = crop_seasons(crop)
    return "Any" if "Any" in seasons else ", ".join(seasons) or "Unknown"

def random_weather_for_season(season: str) -> str:
    options, weights = SEASON_WEATHER_TABLES.get(season, SEASON_WEATHER_TABLES["Spring"])
    return random.choices(options, weights=weights)[0]

def forecast_weather_for_date(month: int, day: int, year: int) -> str:
    """Deterministic in-game weather forecast for a calendar date."""
    season = season_for_month(month)
    options, weights = SEASON_WEATHER_TABLES.get(season, SEASON_WEATHER_TABLES["Spring"])
    rng = random.Random((year * 10000) + (month * 100) + day)
    return rng.choices(options, weights=weights)[0]

def weather_forecast_summary(weather: str) -> str:
    if weather == "Sunny":
        return "Clear skies. Crops need watering."
    if weather == "Cloudy":
        return "Mild and gray. Crops still need watering."
    if weather == "Rainy":
        return "Rain expected. Crops will be watered."
    if weather == "Stormy":
        return "Heavy storm. Crops will be watered."
    if weather == "Snowy":
        return "Snowfall expected. Winter conditions continue."
    if weather == "Blizzard":
        return "Severe snow and wind. Travel carefully."
    if weather == "Hot":
        return "Hot weather. Keep an eye on stamina."
    if weather == "Windy":
        return "Windy conditions around the farm."
    if weather == "Foggy":
        return "Low visibility in the morning."
    return "No special advisory."

def weather_waters_crops(weather: str) -> bool:
    return weather in ["Rainy", "Stormy"]

def season_tile_color(tile: str, season: str) -> str:
    """Return the color used for a base tile in a given season."""
    if tile == ".":
        return {
            "Spring": C.SPRING_GRASS,
            "Summer": C.SUMMER_GRASS,
            "Fall": C.FALL_GRASS,
            "Winter": C.WINTER_GRASS,
        }.get(season, C.GRASS)

    if tile == ",":
        return {
            "Spring": C.SPRING_SOIL_DRY,
            "Summer": C.SUMMER_SOIL_DRY,
            "Fall": C.FALL_SOIL_DRY,
            "Winter": C.WINTER_SOIL_DRY,
        }.get(season, C.SOIL_DRY)

    if tile == "w":
        return {
            "Spring": C.SPRING_SOIL_WET,
            "Summer": C.SUMMER_SOIL_WET,
            "Fall": C.FALL_SOIL_WET,
            "Winter": C.WINTER_SOIL_WET,
        }.get(season, C.SOIL_WET)

    if tile == "^":
        return {
            "Spring": C.SPRING_WEED,
            "Summer": C.SUMMER_WEED,
            "Fall": C.FALL_WEED,
            "Winter": C.WINTER_WEED,
        }.get(season, C.WEED)

    if tile == "~":
        return C.WINTER_WATER if season == "Winter" else C.WATER

    if tile == "*":
        return C.WINTER_SOIL_DRY if season == "Winter" else C.WOOD

    if tile == "o":
        return C.WINTER_GRASS if season == "Winter" else C.STONE

    return ""

def precipitation_density(weather: str) -> float:
    return {
        "Rainy": 0.08,
        "Stormy": 0.13,
        "Snowy": 0.07,
        "Blizzard": 0.16,
    }.get(weather, 0.0)

def precipitation_symbol(weather: str) -> str:
    if weather == "Rainy":
        return random.choice(["'", ".", ","])
    if weather == "Stormy":
        return random.choice(["|", "/", "!"])
    if weather == "Snowy":
        return random.choice(["*", ".", "·"])
    if weather == "Blizzard":
        return random.choice(["*", "*", ".", "+"])
    return ""

def precipitation_color(weather: str) -> str:
    if weather == "Stormy":
        return C.STORM
    if weather in ["Snowy", "Blizzard"]:
        return C.SNOW
    return C.RAIN

def weather_has_precipitation(weather: str) -> bool:
    return weather in ["Rainy", "Stormy", "Snowy", "Blizzard"]

def tile_outdoors(tile: str) -> bool:
    return tile not in ["#", "H", "$", "B", "G", "C", "L", "M", "I", "D"]

def day_of_year(month: int, day: int, year: int) -> int:
    return sum(days_in_month(m, year) for m in range(1, month)) + day

def weekday_for_date(month: int, day: int, year: int) -> str:
    # Year 1, January 1 starts on Monday for deterministic game-calendar purposes.
    completed_years = max(0, int(year) - 1)
    leap_years = (
        completed_years // 4
        - completed_years // 100
        + completed_years // 400
    )
    days_before = completed_years * 365 + leap_years
    days_before += day_of_year(month, day, year) - 1
    return WEEKDAY_NAMES[days_before % 7]

def advance_date(month: int, day: int, year: int) -> tuple[int, int, int]:
    day += 1
    if day > days_in_month(month, year):
        day = 1
        month += 1
        if month > 12:
            month = 1
            year += 1
    return month, day, year

def add_months_to_date(month: int, day: int, year: int, months: int) -> tuple[int, int, int]:
    total = (int(year) * 12) + (int(month) - 1) + int(months)
    new_year = total // 12
    new_month = (total % 12) + 1
    new_day = min(int(day), days_in_month(new_month, new_year))
    return new_month, new_day, new_year

def date_tuple(month: int, day: int, year: int) -> tuple[int, int, int]:
    return int(year), int(month), int(day)

def date_reached(month: int, day: int, year: int, target_month: int, target_day: int, target_year: int) -> bool:
    return date_tuple(month, day, year) >= date_tuple(target_month, target_day, target_year)

def months_between_dates(start_month: int, start_day: int, start_year: int, end_month: int, end_day: int, end_year: int) -> int:
    months = (int(end_year) - int(start_year)) * 12 + (int(end_month) - int(start_month))
    if int(end_day) < int(start_day):
        months -= 1
    return max(0, months)

def format_date(month: int, day: int, year: int) -> str:
    return f"{MONTH_NAMES[month]} {day}, Year {year}"

def format_birthday(month: int, day: int) -> str:
    return f"{MONTH_NAMES[int(month)]} {int(day)}"

def migrate_abstract_day_to_date(old_day: int, old_year: int, old_season: str = "Spring") -> tuple[int, int, int]:
    # Old saves used 28-day seasons. Map to the matching season-start month.
    season_start_month = {
        "Spring": 3,
        "Summer": 6,
        "Fall": 9,
        "Winter": 12,
    }.get(old_season, 3)
    year = max(1, int(old_year))
    day = max(1, min(int(old_day), days_in_month(season_start_month, year)))
    return season_start_month, day, year


__all__ = [
    'item_name_for_quantity',
    'quantity_item_phrase',
    'naturalize_item_quantity_text',
    'quantity_agreement',
    'calendar_events_for',
    'wilderness_biome_name',
    'wilderness_biome_description',
    'forage_symbols_for_season',
    'forage_item_for_symbol',
    'forage_description_for_symbol',
    'is_fish_item',
    'fish_sell_price',
    'fish_stamina_value',
    'fishing_time_bucket',
    'mine_theme_for_floor',
    'mine_floor_resource_weights',
    'mine_node_label',
    'is_food_item',
    'food_stamina_value',
    'is_leap_year',
    'days_in_month',
    'season_for_month',
    'season_daylight_window',
    'crop_seasons',
    'crop_valid_for_season',
    'crop_season_label',
    'random_weather_for_season',
    'forecast_weather_for_date',
    'weather_forecast_summary',
    'weather_waters_crops',
    'season_tile_color',
    'precipitation_density',
    'precipitation_symbol',
    'precipitation_color',
    'weather_has_precipitation',
    'tile_outdoors',
    'day_of_year',
    'weekday_for_date',
    'advance_date',
    'add_months_to_date',
    'date_tuple',
    'date_reached',
    'months_between_dates',
    'format_date',
    'format_birthday',
    'migrate_abstract_day_to_date'
]
