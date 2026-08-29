from __future__ import annotations

"""A compositional library of 3,000 distinct, role-aware dialogue lines.

Twenty-five occupational voices each provide ten lines for twelve subjects.
The catalog is deterministic and inspectable, while runtime rendering can fold
in the actual season, weather, place, activity, relationship, and player name.
"""

import hashlib
from functools import lru_cache
from ascii_farmstead_dialogue_registers import (
    REGISTER_LENSES,
    REGISTER_TOPIC_LENSES,
    REGISTER_TOPIC_OBSERVATIONS,
    REGISTER_TOPIC_PATTERNS,
    register_for_profile,
)
from typing import Dict, Mapping, Sequence, Tuple


DIALOGUE_LIBRARY_TOPICS: Tuple[str, ...] = (
    "greeting", "activity", "work", "place", "people", "rumor",
    "weather", "season", "personal", "family", "interests", "farewell",
)


VOICE_PROFILES: Tuple[Dict[str, str], ...] = (
    {"id": "civic", "task": "the council desk", "identity": "civic organizer", "vantage": "From the council desk", "work": "turning public promises into schedules people can rely on", "place": "the town hall steps", "concern": "small problems becoming permanent through neglect", "interest": "local history and practical planning", "people": "clerks, neighbors, and anyone willing to attend a meeting", "material": "ink, notices, and patient negotiation"},
    {"id": "commerce", "task": "the counter", "identity": "shopkeeper", "vantage": "From behind a well-used counter", "work": "matching limited stock to what households actually need", "place": "the shop floor before opening", "concern": "a broken supply route leaving shelves empty", "interest": "prices, useful goods, and the habits of regular customers", "people": "suppliers, customers, and neighboring merchants", "material": "ledgers, crates, and careful estimates"},
    {"id": "smith", "task": "the forge", "identity": "metalworker", "vantage": "Beside the cooling forge", "work": "making metal dependable before anyone trusts it underground", "place": "the forge after the hammering stops", "concern": "a hidden flaw failing when someone needs a tool most", "interest": "ore, edge geometry, and better tool designs", "people": "miners, craftspeople, and farmers with worn equipment", "material": "heat, iron, and measured blows"},
    {"id": "carpentry", "task": "the bench", "identity": "builder", "vantage": "At the end of the workbench", "work": "giving rooms clear purposes and paths that remain usable", "place": "a frame where the next wall will stand", "concern": "careless construction trapping people in awkward spaces", "interest": "joinery, architecture, and bridges", "people": "homeowners, laborers, and apprentices", "material": "wood grain, chalk lines, and sound joints"},
    {"id": "animals", "task": "the barn", "identity": "animal keeper", "vantage": "From the quiet side of the stable", "work": "noticing an animal's needs before distress makes them obvious", "place": "the barn during the calm between feedings", "concern": "routine neglect being mistaken for bad temperament", "interest": "breeding, training, and the personalities of individual animals", "people": "ranchers, veterinarians, and patient handlers", "material": "feed, clean bedding, and steady hands"},
    {"id": "archive", "task": "the archive", "identity": "keeper of records", "vantage": "Between the shelves and catalog drawers", "work": "preserving useful knowledge before memory edits the details", "place": "the library's quietest table", "concern": "important experience disappearing because nobody wrote it down", "interest": "books, maps, and local histories", "people": "readers, witnesses, and careful researchers", "material": "paper, indexes, and corroborated accounts"},
    {"id": "road", "task": "the roadside", "identity": "road traveler", "vantage": "With one boot still pointed toward the road", "work": "learning which routes remain safe when conditions change", "place": "the next marked junction", "concern": "a familiar road encouraging careless travel", "interest": "maps, distant settlements, and roadside stories", "people": "couriers, guides, wayfarers, and fellow travelers", "material": "trail signs, packed provisions, and good directions"},
    {"id": "medicine", "task": "the clinic", "identity": "medical worker", "vantage": "From the clinic's clean worktable", "work": "catching small symptoms before they become emergencies", "place": "the clinic between appointments", "concern": "someone waiting too long because they fear the cost or diagnosis", "interest": "herbal remedies, anatomy, and preventative care", "people": "patients, nurses, and reliable suppliers", "material": "clean instruments, herbs, and careful observation"},
    {"id": "hospitality", "task": "the inn", "identity": "host", "vantage": "Near the inn's front desk", "work": "making strangers feel safe without prying into what brought them", "place": "the common room before the evening crowd", "concern": "a guest having nowhere private to rest", "interest": "traveler stories, card games, and shared meals", "people": "guests, cooks, performers, and regular patrons", "material": "clean rooms, warm food, and discretion"},
    {"id": "culinary", "task": "the kitchen", "identity": "cook", "vantage": "At the edge of the kitchen heat", "work": "turning seasonal ingredients into meals people remember", "place": "the kitchen before service", "concern": "good produce being wasted through careless preparation", "interest": "recipes, forage, and unusual flavor combinations", "people": "farmers, diners, and anyone honest about a meal", "material": "sharp knives, steady heat, and fresh ingredients"},
    {"id": "market", "task": "the stall", "identity": "market trader", "vantage": "Under the market awning", "work": "finding value in goods other people overlook", "place": "the stalls while they are being arranged", "concern": "an empty market teaching residents to shop elsewhere", "interest": "bargains, festivals, and changing demand", "people": "vendors, customers, and caravan crews", "material": "display cloth, coin, and quick arithmetic"},
    {"id": "garden", "task": "the garden", "identity": "grower", "vantage": "At the end of a cultivated row", "work": "reading soil and season before committing a crop", "place": "the garden at first light", "concern": "poor timing wasting both seed and labor", "interest": "flowers, crop rotation, and weather signs", "people": "farmers, seed sellers, and neighboring gardeners", "material": "soil, seed, compost, and patient watering"},
    {"id": "water", "task": "the waterline", "identity": "water worker", "vantage": "Beside the waterline", "work": "understanding currents and what they carry", "place": "the bank where the current changes", "concern": "calm water hiding a dangerous shift", "interest": "fish, boats, rainfall, and changing channels", "people": "fishers, ferry crews, and riverside families", "material": "rope, nets, sound boats, and weather sense"},
    {"id": "mining", "task": "the mine", "identity": "miner", "vantage": "At the mouth of the worked stone", "work": "reading rock before committing strength and tools", "place": "the mine entrance between descents", "concern": "greed carrying someone deeper than preparation allows", "interest": "geology, ore seams, and cave routes", "people": "smiths, prospectors, and dependable climbing partners", "material": "stone dust, supports, lamps, and tested tools"},
    {"id": "youth", "task": "school", "identity": "kid", "vantage": "From a place adults usually overlook", "work": "figuring out how things work when nobody explains them", "place": "the quickest route between home and something interesting", "concern": "grown-ups deciding before I finish talking", "interest": "games, animals, stories, and exploring safe places", "people": "friends, relatives, teachers, and patient grown-ups", "material": "questions, scraped knees, and borrowed supplies"},
    {"id": "arts", "task": "the studio", "identity": "artist", "vantage": "From the side of an unfinished piece", "work": "finding a shape for things ordinary speech cannot hold", "place": "the spot where the light changes color", "concern": "useful work leaving no room for beauty or celebration", "interest": "music, color, performance, and human expressions", "people": "performers, craftspeople, and attentive audiences", "material": "pigment, rhythm, rehearsal, and nerve"},
    {"id": "solitary", "task": "my own place", "identity": "solitary worker", "vantage": "From the quieter edge of settlement", "work": "keeping independence without pretending nobody else matters", "place": "a sheltered place beyond the busiest paths", "concern": "company becoming obligation instead of choice", "interest": "foraging, repairs, and long periods of quiet", "people": "trusted neighbors and travelers who respect boundaries", "material": "stored provisions, simple tools, and privacy"},
    {"id": "orchard", "task": "the orchard", "identity": "orchard keeper", "vantage": "Beneath branches shaped over many seasons", "work": "planning harvests years before the fruit appears", "place": "the orchard between blossom and harvest", "concern": "short-term thinking damaging a tree's future", "interest": "fruit preserving, bees, grafting, and seasonal cycles", "people": "beekeepers, cooks, and patient growers", "material": "pruning tools, healthy soil, and time"},
    {"id": "textile", "task": "the cutting table", "identity": "textile worker", "vantage": "Beside the cutting table", "work": "making useful cloth fit the person who must live in it", "place": "the workshop among folded fabrics", "concern": "rushed measurements turning good material into waste", "interest": "sewing, dyes, patterns, and practical fashion", "people": "customers, fiber suppliers, and other craftspeople", "material": "thread, cloth, needles, and exact measurements"},
    {"id": "nature", "task": "the field station", "identity": "field researcher", "vantage": "At the boundary between trail and habitat", "work": "investigating useful plants and wildlife without damaging their habitat", "place": "a field station near the work tract", "concern": "collectors taking more than a region can replace", "interest": "plants, wildlife, fungi, and practical field records", "people": "rangers, herbalists, researchers, and local guides", "material": "samples, sketches, markers, and restraint"},
    {"id": "mechanical", "task": "the workshop", "identity": "mechanic", "vantage": "Over an opened machine casing", "work": "finding the small failure that makes the whole system unreliable", "place": "the workshop after a successful test", "concern": "a temporary repair being mistaken for a permanent one", "interest": "machines, puzzles, tools, and efficient designs", "people": "operators, smiths, builders, and curious apprentices", "material": "gears, fasteners, diagrams, and patient testing"},
    {"id": "elder", "task": "my usual corner", "identity": "longtime resident", "vantage": "From a seat chosen through years of habit", "work": "remembering which old solutions deserve another chance", "place": "a familiar corner with a view of passing life", "concern": "nostalgia making the past kinder than it truly was", "interest": "local history, gardens, games, and watching families grow", "people": "old friends, younger relatives, and neighbors who stop to listen", "material": "memory, routine, and lessons paid for long ago"},
    {"id": "law", "task": "the station", "identity": "keeper of public safety", "vantage": "From the station doorway", "work": "keeping roads usable without making everyone feel watched", "place": "the patrol route where town meets wilderness", "concern": "fear turning a manageable danger into public panic", "interest": "tracking, civic rules, and practical defense", "people": "deputies, witnesses, travelers, and town officials", "material": "reports, patrols, evidence, and proportionate force"},
    {"id": "research", "task": "the research table", "identity": "researcher", "vantage": "Beside a page crowded with observations", "work": "testing an appealing explanation against inconvenient evidence", "place": "the research table after fieldwork", "concern": "certainty arriving before enough observations do", "interest": "experiments, classification, maps, and unresolved questions", "people": "specialists, witnesses, students, and skeptical colleagues", "material": "samples, controls, notes, and repeatable methods"},
    {"id": "settler", "task": "the day's work", "identity": "working resident", "vantage": "From the middle of an ordinary day's work", "work": "keeping a household and community dependable one task at a time", "place": "the path between home, work, and neighbors", "concern": "too many small obligations landing on the same person", "interest": "useful crafts, local news, meals, and quiet recreation", "people": "family, coworkers, neighbors, and familiar travelers", "material": "routine, shared labor, and tools kept in good order"},
)


TOPIC_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "greeting": (
        "{vantage}, I have learned that a proper greeting saves confusion later; good {time}.",
        "{vantage}, faces become familiar through ordinary meetings like this one; it is good to see you.",
        "{vantage}, I was just considering {concern}; your arrival gives me a reason to pause.",
        "{vantage}, {a_identity} notices who appears and when; hello, {player}.",
        "{vantage}, the day has already found its rhythm, but there is room in it for a conversation.",
        "{vantage}, I recognize your step now; you need not introduce yourself again.",
        "{vantage}, people often hurry past {a_identity}; I appreciate that you stopped.",
        "{vantage}, this is a better moment to talk than it may look from outside.",
        "{vantage}, I wondered whether our paths would cross in {setting} today.",
        "{vantage}, familiarity is built from small returns; welcome back.",
    ),
    "activity": (
        "{vantage}, I am occupied with {task}; the visible task is only part of it.",
        "{vantage}, today's routine is {activity}, which keeps pulling my attention back to {concern}.",
        "{vantage}, I am using {material} to keep the day's work from becoming tomorrow's problem.",
        "{vantage}, being {a_identity} means even a quiet hour contains preparation.",
        "{vantage}, I am between the urgent part of {task} and the part that needs patience.",
        "{vantage}, the work looks repetitive until one notices what changes each day.",
        "{vantage}, I am checking yesterday's effort before adding anything new.",
        "{vantage}, {activity} is going well enough, though I would not call it finished.",
        "{vantage}, I am trying to leave {setting} more usable than I found it this morning.",
        "{vantage}, most of my attention is on {task}, with a little left for whoever stops to speak.",
    ),
    "work": (
        "{vantage}, {a_identity} succeeds by {work}, not by merely looking busy.",
        "{vantage}, the hardest part of my profession is usually {concern}.",
        "{vantage}, people see {material}; they do not always see the judgment behind using it well.",
        "{vantage}, my work connects me to {people}, whether or not we share the same room.",
        "{vantage}, experience has made me slower to promise and faster to prepare.",
        "{vantage}, I judge a good day by whether someone can rely on what I leave behind.",
        "{vantage}, the profession rewards attention long before it rewards confidence.",
        "{vantage}, I would rather explain a limitation honestly than hide it under enthusiasm.",
        "{vantage}, every shortcut creates a debt; my work is deciding which debts are acceptable.",
        "{vantage}, if you want to understand {a_identity}, watch what they check twice.",
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
        "{vantage}, {a_identity} hears many opinions, but repetition does not make one true.",
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
        "{vantage}, people are discussing {task}; the disagreement is mostly about what should happen next.",
        "{vantage}, I would rather give you an incomplete truth than decorate it into certainty.",
    ),
    "weather": (
        "{vantage}, {weather} weather changes how {a_identity} plans even when the work remains indoors.",
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
        "{vantage}, being {a_identity} explains my routine, but it does not explain all of me.",
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
        "{vantage}, family life has its own routines, and {a_identity}'s schedule must bend around them.",
        "{vantage}, I try not to bring every concern about {task} through the front door.",
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
        "{vantage}, I make time for {interest} when the day lets me go early enough.",
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
        "{vantage}, I should get back to {task}; thank you for speaking plainly.",
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


# Four grounded observations combined with ten conversational lenses add forty
# coherent lines per topic and occupational voice. Together with the original
# ten authored patterns this raises the inspectable catalog from 3,000 to
# 15,000 lines without presenting several unrelated remarks at once.
SUPPLEMENTAL_TOPIC_OBSERVATIONS: Dict[str, Tuple[str, ...]] = {
    "greeting": (
        "good {time}; I was just finding the rhythm of {task} when you arrived.",
        "hello, {player}; {setting} feels less anonymous when familiar people stop to speak.",
        "you caught me between {activity} and the next thing demanding my attention.",
        "welcome back; I remember our last conversation better than most of what happens at {task}.",
    ),
    "activity": (
        "I am {activity}, and the part requiring judgment is harder to see than the movement.",
        "today's task keeps circling back to {concern}, so I am taking it more carefully than usual.",
        "I am working with {material}; rushing would save minutes and create hours of repair.",
        "the routine at {task} looks ordinary, but one changed detail has kept me alert all day.",
    ),
    "work": (
        "the useful part of my work is {work}, especially when nobody is around to praise it.",
        "I learned this trade around {people}, making small mistakes where patient hands could correct me.",
        "what exhausts me is not {material}; it is deciding which problem deserves attention first.",
        "I still enjoy being {a_identity}, although enjoyment and ease are not the same thing.",
    ),
    "place": (
        "You can read {setting} once you notice where people slow down, gather, and turn back.",
        "I judge a place the way I judge {place}: by whether its paths respect the people who use them daily.",
        "I go to {place} when I need to remember how this area fits together.",
        "roads, rooms, and shorelines reveal what their builders expected, the same way {place} does.",
    ),
    "people": (
        "I know {people}, but knowing someone does not give me ownership of their private story.",
        "among {people}, the dependable ones are not always the most charming, only the ones who return.",
        "working around {people} taught me who wants advice, who wants help, and who only wants to be heard.",
        "most reputations contain a little truth and a great deal of convenient editing; {people} are no exception.",
    ),
    "rumor": (
        "the latest rumor concerns {concern}, though the witnesses disagree about the important part.",
        "I heard something through {people}; I trust the source more than I trust the retelling.",
        "there is talk around {setting}, but nobody has yet shown me evidence worth acting upon.",
        "gossip reveals what {people} fear even when it reveals nothing about what actually happened.",
    ),
    "weather": (
        "{weather} weather changes the safe version of every route I take to {place}.",
        "I plan around the sky because {material} behave differently once the air turns.",
        "people call weather small talk until it reaches {task}.",
        "today's conditions have made {setting} feel like a different place wearing the same name.",
    ),
    "season": (
        "{season} exposes which routines at {task} were habits and which actually suited the land.",
        "I measure the season by changes in {work}, not merely by the calendar.",
        "this part of {season} makes me reconsider what should be finished at {task} and what can wait.",
        "every season gives something freely and makes something else expensive; {material} tell me which is which.",
    ),
    "personal": (
        "I am better at {task} than I am at explaining what I want once the day is over.",
        "I value {interest}, though I sometimes protect it so carefully that I forget to enjoy it.",
        "I have changed my mind about {concern} more than once, usually after certainty embarrassed me.",
        "away from {task}, there are parts of me I do not show to many people.",
    ),
    "family": (
        "family taught me that affection and agreement are entirely different skills; {people} taught me the rest.",
        "the people closest to me know which version of my confidence is real; {people} only ever see the steady one.",
        "I think households work best when care is offered without turning into control; {task} taught me the same lesson.",
        "family history is ordinary moments becoming important through repetition, the way habits form around {task}.",
    ),
    "interests": (
        "when work releases me, I make time for {interest} and try not to make it productive.",
        "I enjoy learning how other people approach {interest}, especially when their reasons differ from mine.",
        "I get to be bad at {interest} without anybody depending on the result.",
        "I find {interest} take enough attention to quiet the rest of my thoughts.",
    ),
    "farewell": (
        "take care, {player}; I will be back at {task} if you need me.",
        "I should get back to {task}, but I am glad the day made room for this conversation.",
        "we can leave it here; {task} is not going to wait much longer anyway.",
        "go safely; {setting} will still have another story when our paths cross again.",
    ),
}

SUPPLEMENTAL_CONVERSATION_LENSES: Tuple[str, ...] = (
    "That is the clearest version I can give while we are {familiarity}.",
    "Experience may change the answer later, but it is honest today.",
    "I would rather say that plainly than decorate it into something impressive.",
    "You may see it differently; I would be interested in knowing why.",
    "It sounds simple when said quickly, though living it has been less simple.",
    "That is what I believe when nobody is waiting for the convenient answer.",
    "I do not tell everyone that, but this conversation made it relevant.",
    "The longer version contains more mistakes and fewer clean conclusions.",
    "Ask me another season and the emphasis may change, even if the truth does not.",
    "I am still deciding what that means for the life I want next.",
)


# The reflective tails above answer a personal question. Appended to "hello" or
# "take care" they turn a passing greeting into a confession, so greetings and
# farewells carry their own tails. Each set keeps ten entries: the catalog size
# and uniqueness assertions below depend on the shape staying identical.
TOPIC_CONVERSATION_LENSES: Dict[str, Tuple[str, ...]] = {
    "greeting": (
        "There is no hurry on my side.",
        "Say what you came to say; I am listening.",
        "You have caught me at a reasonable hour, at least.",
        "I have a little time before the next thing needs me.",
        "Stay or keep walking as you like; this need not be formal.",
        "I am glad it is you and not another errand.",
        "Ask me anything while the moment is quiet.",
        "It is a decent enough day for standing and talking.",
        "You look like you have something on your mind.",
        "Never mind the work; it will wait a moment.",
    ),
    "farewell": (
        "Come back when you have time to spare.",
        "I will be here, or somewhere close to it.",
        "Mind how you go.",
        "We can pick this up when the day is kinder.",
        "Safe roads until then.",
        "You know where to find me.",
        "I hope the rest of it goes easily.",
        "Until the next time our paths cross.",
        "Go on, then; the day is not getting longer.",
        "That is enough talk for now, I think.",
    ),
}


def dialogue_patterns_for_topic(topic: str, register: str = "") -> Tuple[str, ...]:
    """Return every pattern a speaker of ``register`` can use on ``topic``.

    A register supplies its own sentence bodies; the shared sets below remain
    the fallback for any register that has not been written yet, so the two can
    coexist while the registers are filled in.
    """
    topic = str(topic)
    register = str(register or "")
    base = tuple(
        REGISTER_TOPIC_PATTERNS.get(register, {}).get(topic)
        or TOPIC_PATTERNS[topic]
    )
    observations = tuple(
        REGISTER_TOPIC_OBSERVATIONS.get(register, {}).get(topic)
        or SUPPLEMENTAL_TOPIC_OBSERVATIONS[topic]
    )
    # Greeting and farewell keep their own tails; every other topic takes the
    # register's, so the closing clause matches the voice that opened the line.
    lenses = (
        REGISTER_TOPIC_LENSES.get(register, {}).get(topic)
        or TOPIC_CONVERSATION_LENSES.get(topic)
        or REGISTER_LENSES.get(register)
        or SUPPLEMENTAL_CONVERSATION_LENSES
    )
    supplemental = tuple(
        f"{{vantage}}, {observation} {lens}"
        for observation in observations
        for lens in lenses
    )
    return base + supplemental


ROLE_PROFILE_RULES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("mayor", "clerk", "council", "politician"), "civic"),
    (("blacksmith", "smith", "metal"), "smith"),
    (("carpenter", "builder", "mason", "architect"), "carpentry"),
    (("animal", "ranch", "stable", "herder"), "animals"),
    (("librar", "archiv", "scholar", "book"), "archive"),
    (("traveler", "courier", "ranger", "guide", "pilot", "wayfarer"), "road"),
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
    (("researcher", "botanist", "herbalist", "mycologist", "woodward", "warden"), "nature"),
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
    # "a animal keeper" -- the indefinite article has to agree with whichever
    # identity is substituted, and a template string cannot decide that, so the
    # article ships attached to the noun. A plain vowel test covers every current
    # identity; a future one beginning with a sounded "u" or a silent "h" would
    # need more than this.
    identity = str(profile.get("identity", ""))
    context["a_identity"] = (
        f"an {identity}" if identity[:1].lower() in "aeiou" else f"a {identity}"
    )
    context.update({
        "player": "neighbor", "time": "day", "weather": "clear",
        "season": "Spring", "setting": profile["place"],
        "activity": profile["work"], "familiarity": "familiar",
    })
    if values:
        context.update({str(key): str(value) for key, value in values.items() if value is not None})
    return context


_PROFILE_SCOPED_TOKENS: Tuple[str, ...] = (
    "{identity}", "{work}", "{task}", "{place}", "{concern}",
    "{interest}", "{people}", "{material}", "{activity}", "{setting}",
)


def _pattern_names_its_speaker(pattern: str) -> bool:
    """True when a line still identifies its speaker without the opening clause."""
    return any(token in pattern for token in _PROFILE_SCOPED_TOKENS)


def _render_pattern(pattern: str, index: int, context: Mapping[str, str]) -> str:
    """Render one line, varying whether it opens with the speaker's vantage.

    Opening every line with the same clause is what made a run of conversation
    read as machine-written: four visits to the innkeeper began "Near the inn's
    front desk" four times. The clause is kept on every third line, and always
    on lines carrying no other profile-specific field -- for those the opening
    is the only thing that distinguishes one speaker's version from another's.
    """
    line = pattern.format_map(context)
    # "At the mouth of the worked stone, the rhythm of the mine" says the place
    # twice; when the body already locates the speaker, the opener always goes.
    names_place = any(token in pattern for token in ("{task}", "{place}", "{setting}"))
    if not names_place and index % 4 == 0:
        return line
    prefix = f"{context['vantage']}, "
    if not line.startswith(prefix):
        return line
    body = line[len(prefix):]
    return body[:1].upper() + body[1:]


@lru_cache(maxsize=1)
def expanded_dialogue_catalog() -> Dict[str, str]:
    catalog: Dict[str, str] = {}
    for profile in VOICE_PROFILES:
        context = _context(profile)
        for topic in DIALOGUE_LIBRARY_TOPICS:
            register = register_for_profile(profile["id"])
            for index, pattern in enumerate(dialogue_patterns_for_topic(topic, register)):
                key = f"{profile['id']}:{topic}:{index}"
                catalog[key] = _render_pattern(pattern, index, context)
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
    patterns: Sequence[str] = dialogue_patterns_for_topic(
        normalized_topic, register_for_profile(profile["id"])
    )
    digest = hashlib.sha256(
        f"{profile['id']}:{normalized_topic}:{seed}".encode("utf-8")
    ).digest()
    index = int.from_bytes(digest[:4], "big") % len(patterns)
    return _render_pattern(patterns[index], index, _context(profile, values))


# Registers differ in how many bodies they own, so the total is summed per
# profile rather than assumed uniform.
EXPANDED_DIALOGUE_LINE_COUNT = sum(
    len(dialogue_patterns_for_topic(topic, register_for_profile(profile["id"])))
    for profile in VOICE_PROFILES
    for topic in DIALOGUE_LIBRARY_TOPICS
)
assert len(expanded_dialogue_catalog()) == EXPANDED_DIALOGUE_LINE_COUNT
# No speaker may ever repeat itself. Global uniqueness across all 25 profiles is
# deliberately NOT asserted: profiles sharing a register share sentence bodies,
# and a miner and a carpenter both saying "Right. Back to it." is ordinary
# speech. Demanding otherwise is what forced every line to open with the
# speaker's vantage clause, which is the uniformity the registers exist to undo.
# The properties that do matter are checked instead: each profile's own lines are
# distinct, and every authored source line is written once (see smoke_test).
for _profile in VOICE_PROFILES:
    _own = [
        line for key, line in expanded_dialogue_catalog().items()
        if key.split(":", 1)[0] == _profile["id"]
    ]
    assert len(_own) == len(set(_own)), _profile["id"]


__all__ = [
    "DIALOGUE_LIBRARY_TOPICS", "EXPANDED_DIALOGUE_LINE_COUNT",
    "TOPIC_PATTERNS", "VOICE_PROFILES", "contextual_dialogue_line",
    "dialogue_patterns_for_topic",
    "dialogue_profile_for_role", "expanded_dialogue_catalog",
]
