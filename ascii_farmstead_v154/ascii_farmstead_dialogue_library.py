from __future__ import annotations

"""A compositional library of 3,000 distinct, role-aware dialogue lines.

Twenty-five occupational voices each provide ten lines for twelve subjects.
The catalog is deterministic and inspectable, while runtime rendering can fold
in the actual season, weather, place, activity, relationship, and player name.
"""

import hashlib
from functools import lru_cache
from typing import Dict, Mapping, Sequence, Tuple


DIALOGUE_LIBRARY_TOPICS: Tuple[str, ...] = (
    "greeting", "activity", "work", "place", "people", "rumor",
    "weather", "season", "personal", "family", "interests", "farewell",
)


VOICE_PROFILES: Tuple[Dict[str, str], ...] = (
    {"id": "civic", "identity": "civic organizer", "vantage": "From the council desk", "work": "turning public promises into schedules people can rely on", "place": "the town hall steps", "concern": "small problems becoming permanent through neglect", "interest": "local history and practical planning", "people": "clerks, neighbors, and anyone willing to attend a meeting", "material": "ink, notices, and patient negotiation"},
    {"id": "commerce", "identity": "shopkeeper", "vantage": "From behind a well-used counter", "work": "matching limited stock to what households actually need", "place": "the shop floor before opening", "concern": "a broken supply route leaving shelves empty", "interest": "prices, useful goods, and the habits of regular customers", "people": "suppliers, customers, and neighboring merchants", "material": "ledgers, crates, and careful estimates"},
    {"id": "smith", "identity": "metalworker", "vantage": "Beside the cooling forge", "work": "making metal dependable before anyone trusts it underground", "place": "the forge after the hammering stops", "concern": "a hidden flaw failing when someone needs a tool most", "interest": "ore, edge geometry, and better tool designs", "people": "miners, craftspeople, and farmers with worn equipment", "material": "heat, iron, and measured blows"},
    {"id": "carpentry", "identity": "builder", "vantage": "At the end of the workbench", "work": "giving rooms clear purposes and paths that remain usable", "place": "a frame where the next wall will stand", "concern": "careless construction trapping people in awkward spaces", "interest": "joinery, architecture, and bridges", "people": "homeowners, laborers, and apprentices", "material": "wood grain, chalk lines, and sound joints"},
    {"id": "animals", "identity": "animal keeper", "vantage": "From the quiet side of the stable", "work": "noticing an animal's needs before distress makes them obvious", "place": "the barn during the calm between feedings", "concern": "routine neglect being mistaken for bad temperament", "interest": "breeding, training, and the personalities of individual animals", "people": "ranchers, veterinarians, and patient handlers", "material": "feed, clean bedding, and steady hands"},
    {"id": "archive", "identity": "keeper of records", "vantage": "Between the shelves and catalog drawers", "work": "preserving useful knowledge before memory edits the details", "place": "the library's quietest table", "concern": "important experience disappearing because nobody wrote it down", "interest": "books, maps, and local histories", "people": "readers, witnesses, and careful researchers", "material": "paper, indexes, and corroborated accounts"},
    {"id": "road", "identity": "road traveler", "vantage": "With one boot still pointed toward the road", "work": "learning which routes remain safe when conditions change", "place": "the next marked junction", "concern": "a familiar road encouraging careless travel", "interest": "maps, distant settlements, and roadside stories", "people": "couriers, guides, pilgrims, and fellow travelers", "material": "trail signs, packed provisions, and good directions"},
    {"id": "medicine", "identity": "medical worker", "vantage": "From the clinic's clean worktable", "work": "catching small symptoms before they become emergencies", "place": "the clinic between appointments", "concern": "someone waiting too long because they fear the cost or diagnosis", "interest": "herbal remedies, anatomy, and preventative care", "people": "patients, nurses, and reliable suppliers", "material": "clean instruments, herbs, and careful observation"},
    {"id": "hospitality", "identity": "host", "vantage": "Near the inn's front desk", "work": "making strangers feel safe without prying into what brought them", "place": "the common room before the evening crowd", "concern": "a guest having nowhere private to rest", "interest": "traveler stories, card games, and shared meals", "people": "guests, cooks, performers, and regular patrons", "material": "clean rooms, warm food, and discretion"},
    {"id": "culinary", "identity": "cook", "vantage": "At the edge of the kitchen heat", "work": "turning seasonal ingredients into meals people remember", "place": "the kitchen before service", "concern": "good produce being wasted through careless preparation", "interest": "recipes, forage, and unusual flavor combinations", "people": "farmers, diners, and anyone honest about a meal", "material": "sharp knives, steady heat, and fresh ingredients"},
    {"id": "market", "identity": "market trader", "vantage": "Under the market awning", "work": "finding value in goods other people overlook", "place": "the stalls while they are being arranged", "concern": "an empty market teaching residents to shop elsewhere", "interest": "bargains, festivals, and changing demand", "people": "vendors, customers, and caravan crews", "material": "display cloth, coin, and quick arithmetic"},
    {"id": "garden", "identity": "grower", "vantage": "At the end of a cultivated row", "work": "reading soil and season before committing a crop", "place": "the garden at first light", "concern": "poor timing wasting both seed and labor", "interest": "flowers, crop rotation, and weather signs", "people": "farmers, seed sellers, and neighboring gardeners", "material": "soil, seed, compost, and patient watering"},
    {"id": "water", "identity": "water worker", "vantage": "Beside the waterline", "work": "understanding currents and what they carry", "place": "the bank where the current changes", "concern": "calm water hiding a dangerous shift", "interest": "fish, boats, rainfall, and changing channels", "people": "fishers, ferry crews, and riverside families", "material": "rope, nets, sound boats, and weather sense"},
    {"id": "mining", "identity": "miner", "vantage": "At the mouth of the worked stone", "work": "reading rock before committing strength and tools", "place": "the mine entrance between descents", "concern": "greed carrying someone deeper than preparation allows", "interest": "geology, ore seams, and cave routes", "people": "smiths, prospectors, and dependable climbing partners", "material": "stone dust, supports, lamps, and tested tools"},
    {"id": "youth", "identity": "young resident", "vantage": "From a place adults usually overlook", "work": "learning which rules protect people and which merely save adults time", "place": "the quickest route between home and something interesting", "concern": "being dismissed before getting to explain", "interest": "games, animals, stories, and exploring safe places", "people": "friends, relatives, teachers, and patient grown-ups", "material": "questions, scraped knees, and borrowed supplies"},
    {"id": "arts", "identity": "artist", "vantage": "From the side of an unfinished piece", "work": "finding a shape for things ordinary speech cannot hold", "place": "the spot where the light changes color", "concern": "useful work leaving no room for beauty or celebration", "interest": "music, color, performance, and human expressions", "people": "performers, craftspeople, and attentive audiences", "material": "pigment, rhythm, rehearsal, and nerve"},
    {"id": "solitary", "identity": "solitary worker", "vantage": "From the quieter edge of settlement", "work": "keeping independence without pretending nobody else matters", "place": "a sheltered place beyond the busiest paths", "concern": "company becoming obligation instead of choice", "interest": "foraging, repairs, and long periods of quiet", "people": "a few trusted neighbors and travelers who respect boundaries", "material": "stored provisions, simple tools, and privacy"},
    {"id": "orchard", "identity": "orchard keeper", "vantage": "Beneath branches shaped over many seasons", "work": "planning harvests years before the fruit appears", "place": "the orchard between blossom and harvest", "concern": "short-term thinking damaging a tree's future", "interest": "fruit preserving, bees, grafting, and seasonal cycles", "people": "beekeepers, cooks, and patient growers", "material": "pruning tools, healthy soil, and time"},
    {"id": "textile", "identity": "textile worker", "vantage": "Beside the cutting table", "work": "making useful cloth fit the person who must live in it", "place": "the workshop among folded fabrics", "concern": "rushed measurements turning good material into waste", "interest": "sewing, dyes, patterns, and practical fashion", "people": "customers, fiber suppliers, and other craftspeople", "material": "thread, cloth, needles, and exact measurements"},
    {"id": "nature", "identity": "field naturalist", "vantage": "At the boundary between trail and habitat", "work": "observing living systems without trampling the evidence", "place": "a field station near the survey tract", "concern": "collectors taking more than a region can replace", "interest": "plants, wildlife, fungi, and field journals", "people": "rangers, herbalists, researchers, and local guides", "material": "samples, sketches, markers, and restraint"},
    {"id": "mechanical", "identity": "mechanic", "vantage": "Over an opened machine casing", "work": "finding the small failure that makes the whole system unreliable", "place": "the workshop after a successful test", "concern": "a temporary repair being mistaken for a permanent one", "interest": "machines, puzzles, tools, and efficient designs", "people": "operators, smiths, builders, and curious apprentices", "material": "gears, fasteners, diagrams, and patient testing"},
    {"id": "elder", "identity": "longtime resident", "vantage": "From a seat chosen through years of habit", "work": "remembering which old solutions deserve another chance", "place": "a familiar corner with a view of passing life", "concern": "nostalgia making the past kinder than it truly was", "interest": "local history, gardens, games, and watching families grow", "people": "old friends, younger relatives, and neighbors who stop to listen", "material": "memory, routine, and lessons paid for long ago"},
    {"id": "law", "identity": "keeper of public safety", "vantage": "From the station doorway", "work": "keeping roads usable without making everyone feel watched", "place": "the patrol route where town meets wilderness", "concern": "fear turning a manageable danger into public panic", "interest": "tracking, civic rules, and practical defense", "people": "deputies, witnesses, travelers, and town officials", "material": "reports, patrols, evidence, and proportionate force"},
    {"id": "research", "identity": "researcher", "vantage": "Beside a page crowded with observations", "work": "testing an appealing explanation against inconvenient evidence", "place": "the research table after fieldwork", "concern": "certainty arriving before enough observations do", "interest": "experiments, classification, maps, and unresolved questions", "people": "specialists, witnesses, students, and skeptical colleagues", "material": "samples, controls, notes, and repeatable methods"},
    {"id": "settler", "identity": "working resident", "vantage": "From the middle of an ordinary day's work", "work": "keeping a household and community dependable one task at a time", "place": "the path between home, work, and neighbors", "concern": "too many small obligations landing on the same person", "interest": "useful crafts, local news, meals, and quiet recreation", "people": "family, coworkers, neighbors, and familiar travelers", "material": "routine, shared labor, and tools kept in good order"},
)


TOPIC_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "greeting": (
        "{vantage}, I have learned that a proper greeting saves confusion later; good {time}.",
        "{vantage}, faces become familiar through ordinary meetings like this one; it is good to see you.",
        "{vantage}, I was just considering {concern}; your arrival gives me a reason to pause.",
        "{vantage}, a {identity} notices who appears and when; hello, {player}.",
        "{vantage}, the day has already found its rhythm, but there is room in it for a conversation.",
        "{vantage}, I recognize your step now; you need not introduce yourself again.",
        "{vantage}, people often hurry past a {identity}; I appreciate that you stopped.",
        "{vantage}, this is a better moment to talk than it may look from outside.",
        "{vantage}, I wondered whether our paths would cross in {setting} today.",
        "{vantage}, familiarity is built from small returns; welcome back.",
    ),
    "activity": (
        "{vantage}, I am occupied with {work}; the visible task is only part of it.",
        "{vantage}, today's routine is {activity}, which keeps pulling my attention back to {concern}.",
        "{vantage}, I am using {material} to keep the day's work from becoming tomorrow's problem.",
        "{vantage}, being a {identity} means even a quiet hour contains preparation.",
        "{vantage}, I am between the urgent portion of {work} and the part that requires patience.",
        "{vantage}, the work looks repetitive until one notices what changes each day.",
        "{vantage}, I am checking yesterday's effort before adding anything new.",
        "{vantage}, {activity} is going well enough, though I would not call it finished.",
        "{vantage}, I am trying to leave {setting} more usable than I found it this morning.",
        "{vantage}, most of my attention is on {work}, with a little left for whoever stops to speak.",
    ),
    "work": (
        "{vantage}, a {identity} succeeds by {work}, not by merely looking busy.",
        "{vantage}, the hardest part of my profession is usually {concern}.",
        "{vantage}, people see {material}; they do not always see the judgment behind using it well.",
        "{vantage}, my work connects me to {people}, whether or not we share the same room.",
        "{vantage}, experience has made me slower to promise and faster to prepare.",
        "{vantage}, I judge a good day by whether someone can rely on what I leave behind.",
        "{vantage}, the profession rewards attention long before it rewards confidence.",
        "{vantage}, I would rather explain a limitation honestly than hide it under enthusiasm.",
        "{vantage}, every shortcut creates a debt; my work is deciding which debts are acceptable.",
        "{vantage}, if you want to understand a {identity}, watch what they check twice.",
    ),
    "place": (
        "{vantage}, {setting} makes sense once you notice how it connects to {place}.",
        "{vantage}, I navigate by useful landmarks, not by whichever road looks widest.",
        "{vantage}, a place reveals its purpose through the people who return to it.",
        "{vantage}, the safest route is the one that still works when {weather} weather changes the ground.",
        "{vantage}, I think of distance in tasks: how much can be carried, repaired, or reached before dark.",
        "{vantage}, {place} is where I regain my bearings when the rest of the settlement feels crowded.",
        "{vantage}, roads are promises made physical; a useful one should lead somewhere worth reaching.",
        "{vantage}, I remember a location by what happened there, not only by its coordinates.",
        "{vantage}, if you become lost, return to {place} and begin again from something recognizable.",
        "{vantage}, {setting} changes character by the hour, so directions should include timing as well as turns.",
    ),
    "people": (
        "{vantage}, my days bring me into contact with {people}; each notices a different part of town.",
        "{vantage}, I trust people more when their routine agrees with their promises.",
        "{vantage}, community is less about universal friendship than knowing who will actually show up.",
        "{vantage}, a {identity} hears many opinions, but repetition does not make one true.",
        "{vantage}, I try not to explain another person's private motives for them.",
        "{vantage}, most disagreements become clearer once everyone names the problem they are solving.",
        "{vantage}, people reveal priorities through what they make time for when nobody is watching.",
        "{vantage}, I know who is dependable in a crisis and who is better company afterward.",
        "{vantage}, familiarity can soften judgment, so I still look for evidence in what people do.",
        "{vantage}, the settlement works because different people notice different failures early.",
    ),
    "rumor": (
        "{vantage}, I hear things from {people}, but I separate what was witnessed from what was repeated.",
        "{vantage}, the current talk concerns {concern}; I would not call every version reliable.",
        "{vantage}, rumors travel faster than corrections, especially through {setting}.",
        "{vantage}, I can tell you what I heard, provided we keep the source attached to it.",
        "{vantage}, an interesting story is not automatically a useful report.",
        "{vantage}, when three people repeat the same phrase, I start wondering who said it first.",
        "{vantage}, local news often begins as someone noticing a change in routine.",
        "{vantage}, I take gossip seriously only when it points toward something we can verify.",
        "{vantage}, people are discussing {work}; the disagreement is mostly about what should happen next.",
        "{vantage}, I would rather give you an incomplete truth than decorate it into certainty.",
    ),
    "weather": (
        "{vantage}, {weather} weather changes how a {identity} plans even when the work remains indoors.",
        "{vantage}, I watch the sky because {concern} becomes harder to manage after conditions turn.",
        "{vantage}, weather exposes which routines were designed well and which only worked by luck.",
        "{vantage}, the air around {setting} says more about the coming hours than the calendar does.",
        "{vantage}, {material} all behave differently in {weather} conditions.",
        "{vantage}, I do not resent bad weather; I resent pretending it changes nothing.",
        "{vantage}, today calls for slower travel and more deliberate preparation.",
        "{vantage}, a clear forecast is useful, but direct observation is better.",
        "{vantage}, {weather} days change who visits, what they carry, and how long they stay.",
        "{vantage}, the safest plan leaves room for weather to prove it wrong.",
    ),
    "season": (
        "{vantage}, {season} changes the meaning of {work} even when the tools look the same.",
        "{vantage}, every season has a task that punishes people for remembering it too late.",
        "{vantage}, this is the part of {season} when I pay closest attention to {concern}.",
        "{vantage}, seasonal work is a conversation between preparation and timing.",
        "{vantage}, {setting} has a different pace in {season}; regulars adjust before visitors notice.",
        "{vantage}, I measure the season by changes in routine more than by dates.",
        "{vantage}, {season} always reveals which supplies should have been stored earlier.",
        "{vantage}, some people fight the season; I prefer to learn what it permits.",
        "{vantage}, the best part of {season} is how it makes familiar work feel specific again.",
        "{vantage}, I am already preparing for what follows {season}, though I try not to rush it away.",
    ),
    "personal": (
        "{vantage}, being a {identity} explains my routine, but it does not explain all of me.",
        "{vantage}, I return to {interest} when I need to remember that usefulness is not everything.",
        "{vantage}, I am proud of {work}, though pride can make criticism harder to hear.",
        "{vantage}, my strongest habits grew from trying not to repeat an old mistake.",
        "{vantage}, I value people who can disagree without turning every difference into a contest.",
        "{vantage}, I am more patient with uncertainty than I used to be.",
        "{vantage}, there are parts of my life I share slowly; that is caution, not hostility.",
        "{vantage}, I sometimes wonder who I would be if {concern} stopped occupying my thoughts.",
        "{vantage}, a quiet success stays with me longer than public praise.",
        "{vantage}, I want my choices to make sense when remembered years from now.",
    ),
    "family": (
        "{vantage}, family life has its own routines, and a {identity}'s schedule must bend around them.",
        "{vantage}, I try not to bring every concern about {work} through the front door.",
        "{vantage}, sharing a household means learning which small tasks matter deeply to someone else.",
        "{vantage}, relatives remember who we were before our profession became our public face.",
        "{vantage}, affection is not a substitute for keeping promises at home.",
        "{vantage}, families need privacy as much as they need help from neighbors.",
        "{vantage}, a difficult day feels different when someone expects you home.",
        "{vantage}, I measure household stability by ordinary meals, rest, and honest conversation.",
        "{vantage}, work connects me to {people}, but family determines what I make room for.",
        "{vantage}, the people closest to us deserve more than whatever attention remains at day's end.",
    ),
    "interests": (
        "{vantage}, I make time for {interest} when {work} releases me early enough.",
        "{vantage}, my interests sharpen parts of me that the workday rarely uses.",
        "{vantage}, I enjoy learning from people who care deeply about something unfamiliar to me.",
        "{vantage}, {interest} began as a distraction and became part of how I understand the world.",
        "{vantage}, a hobby becomes precious when nobody is measuring its productivity.",
        "{vantage}, I keep a few tools for {interest} separate from the ones that earn my living.",
        "{vantage}, I like pursuits that reward attention without demanding urgency.",
        "{vantage}, sometimes I follow {people} into their interests simply to see what they notice.",
        "{vantage}, {setting} offers more recreation than newcomers realize if they stop hurrying.",
        "{vantage}, I would rather be clumsy at something enjoyable than competent at nothing but work.",
    ),
    "farewell": (
        "{vantage}, I should return to {work}; thank you for speaking plainly.",
        "{vantage}, we can continue another time without pretending every subject is settled.",
        "{vantage}, take care around {setting}, especially while the weather remains {weather}.",
        "{vantage}, I will remember what mattered in this conversation and let the rest pass.",
        "{vantage}, there is work waiting, but this was not wasted time.",
        "{vantage}, if you learn anything reliable about {concern}, you know where to find me.",
        "{vantage}, safe travels, whether you are crossing town or going farther.",
        "{vantage}, give my regards to the people sharing your road today.",
        "{vantage}, we have said enough for one meeting; the next can begin from here.",
        "{vantage}, go well, {player}; familiarity is built by returning.",
    ),
}


ROLE_PROFILE_RULES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("mayor", "clerk", "council", "politician"), "civic"),
    (("blacksmith", "smith", "metal"), "smith"),
    (("carpenter", "builder", "mason", "architect"), "carpentry"),
    (("animal", "ranch", "stable", "herder"), "animals"),
    (("librar", "archiv", "scholar", "book"), "archive"),
    (("traveler", "courier", "ranger", "guide", "pilot", "pilgrim"), "road"),
    (("doctor", "nurse", "healer", "clinic"), "medicine"),
    (("innkeeper", "host", "bartender"), "hospitality"),
    (("chef", "cook", "baker"), "culinary"),
    (("vendor", "merchant", "shopkeeper", "stockkeeper", "trader"), "market"),
    (("gardener", "farmer", "grower", "seed seller"), "garden"),
    (("fisher", "ferry", "sailor", "water", "well keeper"), "water"),
    (("miner", "prospector", "quarry"), "mining"),
    (("kid", "child", "teen", "student"), "youth"),
    (("artist", "musician", "performer", "painter"), "arts"),
    (("recluse", "hermit", "solitary"), "solitary"),
    (("orchard", "beekeeper", "apiar"), "orchard"),
    (("tailor", "weaver", "textile", "seam"), "textile"),
    (("naturalist", "botanist", "herbalist", "mycologist", "woodward", "warden"), "nature"),
    (("mechanic", "engineer", "machin"), "mechanical"),
    (("retiree", "elder"), "elder"),
    (("sheriff", "deputy", "guard", "constable", "bounty"), "law"),
    (("researcher", "scientist", "surveyor"), "research"),
    (("store", "commerce", "sales"), "commerce"),
)


def dialogue_profile_for_role(role: object) -> Dict[str, str]:
    normalized = " ".join(str(role or "resident").lower().replace("-", " ").split())
    profiles = {profile["id"]: profile for profile in VOICE_PROFILES}
    for needles, profile_id in ROLE_PROFILE_RULES:
        if any(needle in normalized for needle in needles):
            return profiles[profile_id]
    return profiles["settler"]


def _context(profile: Mapping[str, str], values: Mapping[str, object] | None = None) -> Dict[str, str]:
    context = dict(profile)
    context.update({
        "player": "neighbor", "time": "day", "weather": "clear",
        "season": "Spring", "setting": profile["place"],
        "activity": profile["work"], "familiarity": "familiar",
    })
    if values:
        context.update({str(key): str(value) for key, value in values.items() if value is not None})
    return context


@lru_cache(maxsize=1)
def expanded_dialogue_catalog() -> Dict[str, str]:
    catalog: Dict[str, str] = {}
    for profile in VOICE_PROFILES:
        context = _context(profile)
        for topic in DIALOGUE_LIBRARY_TOPICS:
            for index, pattern in enumerate(TOPIC_PATTERNS[topic]):
                key = f"{profile['id']}:{topic}:{index}"
                catalog[key] = pattern.format_map(context)
    return catalog


def contextual_dialogue_line(
    role: object,
    topic: str,
    seed: object,
    values: Mapping[str, object] | None = None,
) -> str:
    profile = dialogue_profile_for_role(role)
    normalized_topic = str(topic or "personal").lower()
    if normalized_topic not in TOPIC_PATTERNS:
        normalized_topic = "personal"
    patterns: Sequence[str] = TOPIC_PATTERNS[normalized_topic]
    digest = hashlib.sha256(
        f"{profile['id']}:{normalized_topic}:{seed}".encode("utf-8")
    ).digest()
    index = int.from_bytes(digest[:4], "big") % len(patterns)
    return patterns[index].format_map(_context(profile, values))


EXPANDED_DIALOGUE_LINE_COUNT = len(VOICE_PROFILES) * len(DIALOGUE_LIBRARY_TOPICS) * 10
assert EXPANDED_DIALOGUE_LINE_COUNT == 3000
assert len(expanded_dialogue_catalog()) == 3000
assert len(set(expanded_dialogue_catalog().values())) == 3000


__all__ = [
    "DIALOGUE_LIBRARY_TOPICS", "EXPANDED_DIALOGUE_LINE_COUNT",
    "TOPIC_PATTERNS", "VOICE_PROFILES", "contextual_dialogue_line",
    "dialogue_profile_for_role", "expanded_dialogue_catalog",
]
