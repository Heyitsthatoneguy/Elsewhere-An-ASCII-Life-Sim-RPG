from __future__ import annotations

"""NPC, relationship, family, dialogue, and NPC-scene behavior.

NpcMixin expects a FarmGame-like object that provides maps, UI panels, item
helpers, errands, birthday helpers, and persistence. Keeping this large cluster
here gives future NPC work a dedicated surface while preserving the legacy
entry point and save behavior.
"""

import random
import textwrap
import heapq
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import *  # noqa: F403
from ascii_farmstead_helpers import *  # noqa: F403
from ascii_farmstead_inventory import *  # noqa: F403
from ascii_farmstead_state import GameState
from ascii_farmstead_support import (
    C,
    VALID_GAME_LOCATIONS,
    append_debug_log,
    clear_screen,
    colorize,
    normalize_key,
    read_key,
)
from ascii_farmstead_ui import MenuItem, pad_to, text_entry_menu
from ascii_farmstead_visuals import actor_style
from ascii_battle_prototype.combat.classes import class_defs as tactical_class_defs


AUTHORED_TOWN_INTERIOR_MAP_ATTRS = {
    "GeneralStoreInterior": "general_store_map",
    "BlacksmithInterior": "blacksmith_interior_map",
    "LibraryInterior": "library_interior_map",
    "MayorHouseInterior": "mayor_house_map",
    "InnInterior": "inn_interior_map",
    "FurnitureStoreInterior": "furniture_store_map",
    "CarpenterStoreInterior": "carpenter_store_map",
    "AnimalStoreInterior": "animal_store_map",
    "ClinicInterior": "clinic_map",
    "TownHallInterior": "town_hall_map",
    "MarketRowInterior": "market_row_map",
    "MuseumInterior": "museum_interior_map",
}

AUTHORED_TOWN_SERVICE_SPECS = {
    "mira_seed": ("GeneralStoreInterior", "Shop", "buy_menu", "General Store closed."),
    "brom_smith": ("BlacksmithInterior", "Forge service", "blacksmith_menu", "Blacksmith closed."),
    "tess_reader": ("LibraryInterior", "Library services", "library_menu", "Library closed."),
    "eli_carpenter": ("CarpenterStoreInterior", "Building service", "carpenter_menu", "Carpenter closed."),
    "poppy_rancher": ("AnimalStoreInterior", "Animal store", "animal_store_menu", "Animal Store closed."),
    "dr_ivy": ("ClinicInterior", "Clinic services", "clinic_menu", "Clinic closed."),
    "mae_innkeeper": ("InnInterior", "Inn services", "inn_menu", "Inn services closed."),
    "vera_vendor": ("MarketRowInterior", "Market stall", "market_row_menu", "Market Row closed."),
    "mayor_ruth": ("TownHallInterior", "Town services", "town_hall_menu", "Town Hall closed."),
}

AUTHORED_TOWN_SERVICE_HOURS = {
    "GeneralStoreInterior": "08:00-12:00, 14:00-17:00",
    "BlacksmithInterior": "08:00-12:00, 14:00-17:00",
    "LibraryInterior": "08:00-12:00, 14:00-17:00",
    "CarpenterStoreInterior": "08:00-12:00, 14:00-17:00",
    "AnimalStoreInterior": "08:00-12:00, 14:00-17:00",
    "ClinicInterior": "08:00-12:00, 14:00-17:00",
    "TownHallInterior": "08:00-12:00, 14:00-17:00",
    "MarketRowInterior": "08:00-17:00",
    "InnInterior": "06:00-12:00, 14:00-23:00",
}

REGIONAL_TOWN_VISITOR_ARCHETYPES = (
    {"id": "elowen_maps", "name": "Elowen", "role": "Cartographer", "origin": "the western survey road", "purpose": "updating regional maps and exchanging route notes"},
    {"id": "kaspar_trade", "name": "Kaspar", "role": "Traveling Merchant", "origin": "a northern caravan circuit", "purpose": "trading compact goods and comparing town prices"},
    {"id": "suri_herbs", "name": "Suri", "role": "Herbalist", "origin": "the floodplain settlements", "purpose": "looking for remedies, seeds, and local plant knowledge"},
    {"id": "oren_road", "name": "Oren", "role": "Pilgrim", "origin": "the eastern shrine road", "purpose": "walking between old waystones and recording acts of kindness"},
    {"id": "lark_song", "name": "Lark", "role": "Performer", "origin": "the southern inn circuit", "purpose": "finding an audience and collecting regional songs"},
    {"id": "vale_ranger", "name": "Vale", "role": "Ranger", "origin": "a distant field station", "purpose": "checking road safety and exchanging wilderness reports"},
    {"id": "nadia_field", "name": "Nadia", "role": "Researcher", "origin": "the lakeside research route", "purpose": "documenting seasonal changes and interviewing residents"},
    {"id": "bram_stone", "name": "Bram", "role": "Prospector", "origin": "the highland road", "purpose": "buying supplies and comparing geological finds"},
    {"id": "iona_post", "name": "Iona", "role": "Courier", "origin": "the regional postal route", "purpose": "delivering letters and carrying news between settlements"},
)

# These are not generic profession slogans. They are concrete subjects an NPC
# can expand on when the player asks about their work. Location, schedule,
# weather, relationships, and recent events are layered on separately at
# runtime, so a conversation can remain specific without becoming a giant set
# of brittle pre-composed combinations.
NPC_ROLE_CONVERSATION_INSIGHTS = {
    "Mayor": (
        "A town works when the clinic, roads, shops, and homes support one another instead of competing for the same attention.",
        "I keep two lists: what residents ask for, and what their daily routes show they actually need.",
        "Opening a building is easy compared with keeping it staffed, supplied, and worth visiting.",
    ),
    "Seed Seller": (
        "I watch what people can water before I recommend what they should plant. A cheap seed is expensive if it dies in the ground.",
        "Seed stock tells you what kind of season people expect, but their purchases tell you what they are afraid of.",
        "I separate quick crops from long commitments so a farmer can plan around travel instead of abandoning a field halfway through.",
    ),
    "Blacksmith": (
        "A good tool should save effort on the hundredth swing, not merely look impressive on the first.",
        "Most broken tools arrive with the same problem: somebody kept working after the handle or edge started warning them.",
        "Mine gear needs balance more than decoration. Fatigue causes more accidents than dull metal does.",
    ),
    "Carpenter": (
        "I start with how people enter, turn, carry supplies, and leave. Walls come after the route makes sense.",
        "A room earns its size by what happens inside it. Empty corners and blocked hallways are both failed measurements.",
        "Repairs last longer when the building sheds water and foot traffic before either reaches the weak joints.",
    ),
    "Animal Keeper": (
        "Animals settle into routines faster than people do, which makes changes in appetite or movement worth noticing early.",
        "Feed, shelter, clean space, and calm handling matter every day. Affection works best when those basics are already reliable.",
        "I match animals to the care a household can sustain, not merely to what looks appealing at the counter.",
    ),
    "Librarian": (
        "A useful archive records why something changed, not only the date somebody approved it.",
        "I compare schedules, maps, and firsthand accounts because official records have a habit of leaving ordinary people out.",
        "The best reference is the one a tired person can still find quickly when the answer matters.",
    ),
    "Traveler": (
        "A route is more than distance. Shelter, water, road condition, and who expects you at the other end all change its real cost.",
        "I remember roads by decisions: where you turn before the floodplain, where you rest, and where pride makes people walk too far.",
        "The safest shortcut is usually local knowledge somebody bothered to share.",
    ),
    "Doctor": (
        "I ask what somebody was doing before they felt unwell. Work, sleep, weather, and food often explain more than the first symptom.",
        "Recovery is part of the treatment. People keep treating an empty stamina bar like a moral challenge.",
        "A clinic is strongest when it prevents emergencies instead of becoming very efficient at surviving them.",
    ),
    "Innkeeper": (
        "A good inn gives strangers privacy without making them feel unwelcome in the common room.",
        "You learn the state of the roads from wet boots, late arrivals, and which meals people order twice.",
        "Rooms, meals, gossip, and directions are all forms of hospitality, but each needs a different kind of discretion.",
    ),
    "Chef": (
        "I build a meal around what is fresh, what will keep, and what people need after the work they actually did.",
        "A recipe is a starting agreement. Weather, harvest quality, and who is eating decide the final version.",
        "Good farm food should taste deliberate without wasting the ingredient that took longest to produce.",
    ),
    "Market Vendor": (
        "A fair price has to respect the producer and still leave the buyer able to return next week.",
        "Market stock is a map of the roads: shortages tell me which route failed before a courier confirms it.",
        "I keep rare goods visible and necessities reachable. Making people hunt for basics is poor business.",
    ),
    "Gardener": (
        "Public plantings have to survive feet, shade, weather, and people forgetting that roots extend past the pretty part.",
        "I plant for the next season as much as this one. A garden should not collapse the moment the flowers finish.",
        "The healthiest patch is often where insects, soil, and people are all allowed a little room.",
    ),
    "Fisher": (
        "Water temperature, wind, shade, and current tell me where fish may be long before the first bite does.",
        "A quiet bank is useful, but a safe landing and a route home matter more when the weather turns.",
        "Taking every good catch is how a good fishing place becomes a story about the past.",
    ),
    "Miner": (
        "Stone changes before a tunnel fails. Dust, sound, seepage, and a new crack all deserve more respect than bravado.",
        "I decide my return point before I descend. Ore has a way of moving the goal when you are already tired.",
        "The mine rewards preparation, but it punishes anyone who mistakes one easy floor for a promise.",
    ),
    "Kid": (
        "Adults name streets after destinations. I name them after the loose board, the echo, and the place nobody can tag you.",
        "You can tell who really knows town by whether they use the long path around the benches.",
        "I keep track of hiding places, interesting bugs, and which grown-ups notice when something changes.",
    ),
    "Courier": (
        "A delivery route is a chain of promises. One blocked road changes every stop after it.",
        "I sort by urgency, distance, and whether the recipient will still be where the address says.",
        "People think speed matters most. Reliability is what makes them trust the next letter to you.",
    ),
    "Artist": (
        "I sketch the light first because buildings and faces both become different subjects when the hour changes.",
        "Public art has to belong to the place without pretending everybody sees the place the same way.",
        "I keep failed studies. They show which detail I was forcing instead of actually observing.",
    ),
    "Recluse": (
        "Quiet places are not empty. They are where you can finally hear which road, animal, or person is approaching.",
        "I watch the edge of town because changes arrive there before the center gives them a name.",
        "Solitude is useful. Isolation is what happens when pride starts choosing it for you.",
    ),
    "Orchardist": (
        "An orchard is a long agreement with soil, shade, and whoever will still be here for the harvest.",
        "I prune for air and future weight, not for how full the branch looks today.",
        "Young trees need protection from impatience almost as much as they need water.",
    ),
    "Tailor": (
        "Work clothes should bend where the wearer bends and reinforce where their routine wears the cloth thin.",
        "I notice pockets, hems, and shoulders. People reveal their real work by what they repeatedly repair.",
        "Color is personal, but fit is a conversation between the fabric and the life wearing it.",
    ),
    "Musician": (
        "Every place has a rhythm before anybody writes a song for it: hammers, wheels, rain, doors, and conversation.",
        "I change a tune when the room stops listening. Performance is attention moving in both directions.",
        "The songs people request tell me what they miss, even when they never say it plainly.",
    ),
    "Beekeeper": (
        "A hive tells you about every flowering route nearby, but only if you notice what the bees stop bringing home.",
        "Calm handling matters. Panic spreads through a hive faster than smoke settles it.",
        "Honey is the visible harvest; pollination is the larger work people forget to count.",
    ),
    "Botanist": (
        "A plant record needs habitat, weather, and neighboring growth. A pressed leaf alone loses most of the story.",
        "I compare common plants carefully because ordinary species reveal environmental change first.",
        "Useful harvesting leaves enough root, seed, or stem for the patch to remain useful next season.",
    ),
    "Mechanic": (
        "A machine should fail visibly and safely. Hidden wear is more dangerous than an honest broken part.",
        "I measure whether a device saves total work, including the time spent feeding, clearing, and repairing it.",
        "The cleanest mechanism is usually the one with fewer moving parts and a better access panel.",
    ),
    "Scholar": (
        "I compare policy with routine. A rule that nobody can follow in an ordinary week is only ceremonial writing.",
        "Town history becomes useful when it explains present arguments instead of merely naming former officials.",
        "I distrust a tidy conclusion until I know which inconvenient account was left outside it.",
    ),
    "Retiree": (
        "After enough years, you learn which urgent problems disappear and which quiet ones become expensive.",
        "Benches teach you plenty. People speak differently when they think nobody is conducting business.",
        "I am retired from paid work, not from noticing when somebody is about to repeat an old mistake.",
    ),
}

NPC_ROLE_CONVERSATION_INSIGHTS.update({
    "Cartographer": (
        "A map should record uncertainty honestly. A blank edge is safer than a confident road that no longer exists.",
        "I compare travelers' accounts with terrain and travel time before I ink a route as dependable.",
        "The useful part of a chart is not the paper; it is knowing which choices the terrain will ask you to make.",
    ),
    "Traveling Merchant": (
        "I carry goods that survive the road and information that helps me decide whether the return journey is worth making.",
        "A trade route becomes reliable when both ends expect one another, not when one lucky caravan arrives.",
        "Prices tell me about shortages, but conversations tell me whether those shortages will last.",
    ),
    "Herbalist": (
        "I harvest the part I need and leave the patch able to recover. Medicine that destroys its source is poor practice.",
        "The same plant can change strength with soil, rain, and season, so I record where every bundle came from.",
        "I ask how a remedy will be used before recommending it. A useful herb is not automatically the right treatment.",
    ),
    "Pilgrim": (
        "I walk between places slowly enough to learn which acts of care never reach official records.",
        "A pilgrimage is partly destination and partly the discipline of noticing who shares the road.",
        "Old shrines survive because travelers keep giving them meaning, not because stone remembers by itself.",
    ),
    "Performer": (
        "I listen to a room before choosing the first song. Every audience arrives carrying a different kind of silence.",
        "Regional songs change on the road; each town keeps the verse that sounds most like its own life.",
        "A performance is successful when people leave with something to repeat, not merely when they applaud.",
    ),
    "Ranger": (
        "I compare fresh tracks, damaged markers, weather, and traveler reports before calling a route safe.",
        "A patrol should leave the next traveler better information, not merely proof that I walked through first.",
        "Wildlife and people often need the same corridor at different hours. Good trail work respects both.",
    ),
    "Researcher": (
        "I repeat observations because one remarkable day can hide the ordinary pattern that actually shapes a region.",
        "Field notes need location, weather, time, and method or they become anecdotes wearing numbers.",
        "I ask residents what changed before I decide what my instruments say changed.",
    ),
    "Prospector": (
        "A responsible survey marks unstable ground and what should remain untouched along with anything valuable.",
        "Rock tells a long story, but greed has a habit of skipping directly to the price of the final page.",
        "I carry samples small enough to study and leave enough behind that the place still exists afterward.",
    ),
    "Naturalist": (
        "I revisit habitats through the season because relationships between species matter more than a list of names.",
        "An unusual sighting matters most when you know what ordinarily belongs there.",
        "Good fieldwork changes how carefully you walk, not only how many notes you bring home.",
    ),
})

NPC_DIALOGUE_RESPONSE_PREFERENCES = {
    "empathetic": {"Doctor", "Animal Keeper", "Innkeeper", "Gardener", "Kid", "Beekeeper", "Retiree"},
    "curious": {"Librarian", "Traveler", "Fisher", "Artist", "Musician", "Botanist", "Scholar", "Recluse"},
    "practical": {"Mayor", "Seed Seller", "Blacksmith", "Carpenter", "Chef", "Market Vendor", "Miner", "Courier", "Orchardist", "Tailor", "Mechanic"},
}

class NpcMixin:
    def town_npc_safe_tile_label(self, x: int, y: int) -> str:
        tile = self.town_map[y][x] if 0 <= y < len(self.town_map) and 0 <= x < len(self.town_map[y]) else "#"
        return {
            "=": "road",
            ":": "plaza path",
            ",": "park grass",
            ".": "grass",
        }.get(tile, "town")

    def town_npc_mood(self, npc: Dict[str, object]) -> str:
        friendship = self.town_npc_relationship(str(npc.get("id", "")))
        period = self.town_time_period()
        if friendship >= 100:
            return "trusting"
        if friendship >= 60:
            return "friendly"
        if self.town_weather_is_severe_for_routines():
            return "tense"
        if self.town_weather_is_bad_for_routines():
            return "weather-wary"
        if friendship < 0:
            return "guarded"
        if period == "morning":
            return "busy"
        if period == "evening":
            return "winding down"
        return "available"

    def town_npc_role_color(self, npc: Dict[str, object]) -> str:
        role = str(npc.get("role", "Villager"))
        friendship = self.town_npc_relationship(str(npc.get("id", "")))
        if friendship < 0:
            return C.DIM
        if friendship >= 100:
            return C.PLAYER
        role_colors = {
            "Mayor": C.CROP_READY,
            "Seed Seller": C.SPRING_GRASS,
            "Blacksmith": C.STONE,
            "Carpenter": C.WOOD,
            "Animal Keeper": C.HOUSE,
            "Librarian": C.SNOW,
            "Traveler": C.WATER,
            "Doctor": C.RAIN,
            "Innkeeper": C.LAMP,
            "Chef": C.FALL_GRASS,
            "Market Vendor": C.SHOP,
            "Gardener": C.GRASS,
            "Fisher": C.WATER,
            "Miner": C.STONE,
            "Kid": C.PLAYER,
            "Courier": C.LAMP,
            "Artist": C.PLACEMENT,
            "Recluse": C.NIGHT,
            "Orchardist": C.FALL_GRASS,
            "Tailor": C.PLACEMENT,
            "Musician": C.LAMP,
            "Beekeeper": C.CROP_READY,
            "Botanist": C.SPRING_GRASS,
            "Mechanic": C.INFRA,
            "Scholar": C.SNOW,
            "Retiree": C.WOOD,
            "Newborn": C.CROP_READY,
            "Infant": C.CROP_READY,
            "Toddler": C.CROP_MID,
            "Young Child": C.SPRING_GRASS,
            "Child": C.PLAYER,
            "Teen": C.WATER,
            "Young Adult": C.PLAYER,
        }
        return role_colors.get(role, C.SHOP)

    def town_npc_near_player(self, npc: Dict[str, object], distance: int = 3) -> bool:
        if not self.on_town() or self.town_npc_is_indoor(npc):
            return False
        try:
            return abs(int(npc.get("x", 0)) - self.state.player_x) + abs(int(npc.get("y", 0)) - self.state.player_y) <= distance
        except Exception:
            return False

    def town_npc_face_player(self, npc: Dict[str, object]):
        try:
            if self.on_house() and str(npc.get("id", "")) == self.state.spouse_npc_id:
                npc_x, npc_y = self.spouse_farmhouse_position()
            elif self.on_town_interior():
                npc_pos = self.town_indoor_npc_positions().get(str(npc.get("id", "")))
                if not npc_pos:
                    return
                npc_x, npc_y = npc_pos
            else:
                npc_x, npc_y = int(npc.get("x", 0)), int(npc.get("y", 0))
            dx = self.state.player_x - npc_x
            dy = self.state.player_y - npc_y
        except Exception:
            return
        if abs(dx) > abs(dy):
            npc["facing"] = "RIGHT" if dx > 0 else "LEFT"
        elif dy:
            npc["facing"] = "DOWN" if dy > 0 else "UP"

    def town_npc_activity_label(self, npc: Dict[str, object]) -> str:
        if self.is_household_child_npc(npc):
            child = self.child_record_from_npc(npc)
            return self.household_child_activity_label(child) if child else "growing up at home"
        if (
            str(npc.get("social_partner_id", ""))
            and str(npc.get("social_day_key", "")) == self.town_npc_day_key()
            and str(npc.get("social_phase", "")) == str(npc.get("routine_phase", "") or self.town_routine_phase())
            and str(npc.get("social_activity", ""))
        ):
            return str(npc.get("social_activity"))
        role = str(npc.get("role", "Villager"))
        phase = self.town_npc_current_routine_phase(npc)
        entry = self.town_npc_schedule_raw_value(npc)
        entry_activity = str(entry.get("activity", "")) if isinstance(entry, dict) else ""
        if entry_activity:
            if self.town_npc_is_indoor(npc):
                place = self.town_npc_indoor_location(npc)
                if place and place.lower() not in entry_activity.lower():
                    return f"{entry_activity} inside {place}"
            return entry_activity
        if self.town_npc_is_indoor(npc):
            place = self.town_npc_indoor_location(npc)
            if str(place).lower() == "farmhouse":
                return "settling into farmhouse life"
            indoor_work = {
                "Mayor": "reviewing town requests",
                "Seed Seller": "sorting seed stock",
                "Blacksmith": "checking tool orders",
                "Carpenter": "drafting build plans",
                "Animal Keeper": "checking animal-care notes",
                "Librarian": "cataloguing records",
                "Doctor": "preparing clinic supplies",
                "Innkeeper": "keeping the inn running",
                "Chef": "testing pantry recipes",
                "Market Vendor": "counting market stock",
                "Tailor": "sorting fabric samples",
                "Mechanic": "tuning a small mechanism",
                "Scholar": "checking civic records",
            }
            return f"{indoor_work.get(role, 'working')} inside {place}"
        if self.town_weather_is_severe_for_routines():
            return "moving carefully between gusts"
        if self.town_weather_is_bad_for_routines():
            return "keeping to sheltered paths"
        routine_activity = self.town_npc_role_activity(npc, phase)
        if routine_activity and routine_activity != "following their routine":
            return routine_activity
        period = self.town_time_period()
        activities = {
            "Mayor": {"morning": "checking civic routes", "midday": "listening for town concerns", "evening": "heading back to review notes"},
            "Seed Seller": {"morning": "opening the seed ledger", "midday": "watching what farmers buy", "evening": "counting tomorrow's packets"},
            "Blacksmith": {"morning": "hauling coal and scrap", "midday": "testing tool balance", "evening": "letting the forge cool"},
            "Carpenter": {"morning": "measuring service paths", "midday": "studying building footprints", "evening": "checking road grades"},
            "Animal Keeper": {"morning": "checking feed orders", "midday": "watching animal store traffic", "evening": "planning tomorrow's care route"},
            "Librarian": {"morning": "opening the records", "midday": "cross-checking town notes", "evening": "taking field observations"},
            "Traveler": {"morning": "testing shortcuts", "midday": "mapping park routes", "evening": "watching the east road"},
            "Doctor": {"morning": "checking clinic stock", "midday": "making wellness rounds", "evening": "looking for quiet air"},
            "Innkeeper": {"morning": "preparing the common room", "midday": "collecting town gossip", "evening": "welcoming travelers"},
            "Chef": {"morning": "planning meals", "midday": "searching for fresh ingredients", "evening": "thinking about specials"},
            "Market Vendor": {"morning": "checking stall space", "midday": "pricing small goods", "evening": "watching customer flow"},
            "Gardener": {"morning": "tending park edges", "midday": "checking seasonal growth", "evening": "listening to the grass"},
            "Fisher": {"morning": "reading the water", "midday": "tracking fish movement", "evening": "checking river shadows"},
            "Miner": {"morning": "testing stone chips", "midday": "talking shop by the forge", "evening": "counting old mine stories"},
            "Kid": {"morning": "looking for shortcuts", "midday": "making up park rules", "evening": "racing the streetlamps home"},
            "Courier": {"morning": "running delivery loops", "midday": "checking road timing", "evening": "making one last circuit"},
            "Artist": {"morning": "sketching light", "midday": "studying park color", "evening": "planning banners"},
            "Recluse": {"morning": "watching the north road", "midday": "keeping to quiet edges", "evening": "counting wilderness sounds"},
            "Orchardist": {"morning": "checking park soil", "midday": "planning orchard rows", "evening": "noting where shade falls"},
            "Tailor": {"morning": "cutting fabric samples", "midday": "studying work-worn clothes", "evening": "matching colors to people"},
            "Musician": {"morning": "warming up scales", "midday": "listening to road rhythms", "evening": "saving melodies for the inn"},
            "Beekeeper": {"morning": "checking flower routes", "midday": "watching pollinators work", "evening": "counting jars and frames"},
            "Botanist": {"morning": "pressing plant samples", "midday": "comparing wild growth", "evening": "looking for cave notes"},
            "Mechanic": {"morning": "tightening small gears", "midday": "studying sprinkler pressure", "evening": "sketching tool ideas"},
            "Scholar": {"morning": "reading old town maps", "midday": "tracking civic changes", "evening": "writing careful notes"},
            "Retiree": {"morning": "checking the south benches", "midday": "pretending not to gossip", "evening": "heading home slowly"},
        }
        return activities.get(role, {}).get(period, "following their routine")

    def town_npc_dialogue_data(self, npc_or_id) -> Dict[str, object]:
        npc_id = str(npc_or_id.get("id", "")) if isinstance(npc_or_id, dict) else str(npc_or_id)
        data = TOWN_NPC_DIALOGUE_DATA.get(npc_id, {})
        if isinstance(data, dict) and data:
            return data
        npc = (
            npc_or_id
            if isinstance(npc_or_id, dict)
            else self.npc_record_by_id(npc_id)
        )
        if isinstance(npc, dict) and self.is_procedural_npc(npc):
            return {
                "profile": str(
                    npc.get(
                        "friend_secret",
                        "They are building a life where roads and households are still new.",
                    )
                ),
                "motivation": str(
                    npc.get(
                        "goal",
                        "They want their wilderness town to become a lasting home.",
                    )
                ),
                "rumor": str(
                    npc.get(
                        "rumor",
                        "Caravans carry more stories than their manifests admit.",
                    )
                ),
                "secret": str(
                    npc.get(
                        "friend_secret",
                        "They are still deciding what home means here.",
                    )
                ),
                "courtship": (
                    f"You and {npc.get('name', 'the resident')} step away from "
                    "the town road and trade stories about the lives you are each trying to build."
                ),
            }
        return {}

    def town_npc_profile_lines(self, npc: Dict[str, object]) -> List[str]:
        data = self.town_npc_dialogue_data(npc)
        profile = str(data.get("profile", "They are finding their place in town one ordinary day at a time."))
        motivation = str(data.get("motivation", "They want the town to work a little better than it did yesterday."))
        rumor = str(data.get("rumor", "People are still learning the shape of the expanded town."))
        lines = [
            f"{npc.get('name')} - {npc.get('role')}",
            "",
            f"Character: {profile}",
            f"Mood: {self.town_npc_mood(npc)}",
            f"Birthday: {self.npc_birthday_label(npc)}",
            f"Activity: {self.town_npc_activity_label(npc)}",
            f"Purpose: {motivation}",
            "",
            f"Current location: {self.town_npc_location_label(npc)}",
            f"Routine: {self.town_npc_routine_brief(npc)}",
            self.town_npc_next_routine_line(npc),
            f"Rumor: {rumor}",
        ]
        reactivity = self.town_npc_reactivity_lines(npc, limit=3)
        if reactivity:
            lines.extend(["", "What they notice:"])
            lines.extend(f"- {line}" for line in reactivity)
        if self.is_marriageable_npc(npc):
            lines.append("")
            lines.extend(self.town_npc_romance_lines(npc))
        return lines

    def town_npc_rumor_lines(self, npc: Dict[str, object]) -> List[str]:
        data = self.town_npc_dialogue_data(npc)
        rumor = str(data.get("rumor", "The town is changing quickly, and people are still choosing what to keep."))
        secret = str(data.get("secret", "There is more happening in town than the notice boards say."))
        friendship = self.town_npc_relationship(str(npc.get("id", "")))
        lines = [f"{npc.get('name')} shares a rumor:", "", rumor]
        if friendship >= 60:
            lines.extend(["", "Because you know each other well, they add:", secret])
        reactivity = self.town_npc_reactivity_lines(npc, limit=1)
        if reactivity:
            lines.extend(["", "They also notice:", reactivity[0]])
        return lines

    def town_npc_reactivity_lines(self, npc: Dict[str, object], limit: int = 3) -> List[str]:
        lines: List[str] = []
        reactive_categories = self.town_npc_reactive_categories()
        for category in self.dialogue_categories_for_npc(npc):
            if category not in reactive_categories:
                continue
            entries = self.contextual_dialogue_entries_for_category(npc, category)
            if not entries:
                continue
            text = str(entries[0].get("text", "")).strip()
            if text and text not in lines:
                lines.append(text)
            if len(lines) >= int(limit):
                break
        return lines

    def town_npc_context_line(self, npc: Dict[str, object]) -> str:
        mood = self.town_npc_mood(npc)
        activity = self.town_npc_activity_label(npc)
        if self.town_npc_is_indoor(npc):
            return f"{npc.get('name', 'They')} is {activity} and seems {mood}."
        ax, ay = self.town_npc_schedule_anchor(npc)
        area = self.town_npc_safe_tile_label(ax, ay)
        return f"{npc.get('name', 'They')} is {activity} by the {area} near {ax},{ay}; mood: {mood}."

    def town_npc_relationship_note(self, npc: Dict[str, object]) -> str:
        points = self.town_npc_relationship(str(npc.get("id", "")))
        if points >= 200:
            return "They trust you with the parts of life that are not easy to explain."
        if points >= 150:
            return "They trust you with decisions and worries that stay out of ordinary conversation."
        if points >= 100:
            return "They trust you enough to drop the town politeness and speak plainly."
        if points >= 60:
            return "They are comfortable when you stop to talk."
        if points >= 25:
            return "They recognize you and remember that you show up."
        if points < 0:
            return "They are careful around you and need a reason to relax."
        return "You are still getting to know each other."

    def procedural_resident_by_id(
        self,
        npc_id: str,
    ) -> Optional[Dict[str, object]]:
        populations = getattr(
            self.state,
            "procedural_settlement_populations",
            {},
        )
        if not isinstance(populations, dict):
            return None
        for population in populations.values():
            if not isinstance(population, dict):
                continue
            residents = population.get("residents", {})
            if not isinstance(residents, dict):
                continue
            resident = residents.get(str(npc_id))
            if isinstance(resident, dict):
                resident["procedural_resident"] = True
                return resident
        return None

    def npc_record_by_id(
        self,
        npc_id: str,
    ) -> Optional[Dict[str, object]]:
        npc_id = str(npc_id)
        authored = next(
            (
                npc
                for npc in getattr(self.state, "town_npcs", []) or []
                if str(npc.get("id", "")) == npc_id
            ),
            None,
        )
        if authored:
            return authored
        elder = next(
            (
                record
                for record in getattr(self.state, "dynasty_elders", []) or []
                if isinstance(record, dict)
                and str(record.get("id", "")) == npc_id
            ),
            None,
        )
        if elder:
            elder["dynasty_elder"] = True
            return elder
        kin = next(
            (
                record
                for record in getattr(self.state, "dynasty_kin", []) or []
                if isinstance(record, dict)
                and str(record.get("id", "")) == npc_id
            ),
            None,
        )
        if kin:
            kin["dynasty_kin"] = True
            return kin
        return self.procedural_resident_by_id(npc_id)

    def is_procedural_npc(self, npc_or_id: object) -> bool:
        if isinstance(npc_or_id, dict):
            return bool(
                npc_or_id.get("procedural_resident")
                or str(npc_or_id.get("id", "")).startswith("proc:")
            )
        return str(npc_or_id).startswith("proc:")

    def town_npc_name(self, npc_id: str) -> str:
        definition = self.town_npc_definition(str(npc_id))
        if isinstance(definition, dict) and definition:
            return str(definition.get("name", npc_id))
        npc = self.npc_record_by_id(str(npc_id))
        return str(npc.get("name", npc_id)) if npc else str(npc_id)

    def npc_sex(self, npc_or_id: object) -> str:
        npc_id = str(npc_or_id.get("id", "")) if isinstance(npc_or_id, dict) else str(npc_or_id)
        npc = (
            npc_or_id
            if isinstance(npc_or_id, dict)
            else self.npc_record_by_id(npc_id)
        )
        if isinstance(npc, dict) and str(npc.get("sex", "")) in VALID_PLAYER_SEXES:
            return str(npc.get("sex"))
        return NPC_SEX_BY_ID.get(npc_id, "Unknown")

    def is_romance_candidate_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        if (
            bool(npc.get("deceased", False))
            or npc_id in set(
                getattr(self.state, "deceased_spouse_npc_ids", []) or []
            )
        ):
            return False
        if npc_id in ROMANCE_NPC_DATA:
            return True
        return bool(
            self.is_procedural_npc(npc)
            and npc.get("romanceable")
            and str(npc.get("age_group", "")) in {"Adult", "Elder"}
        )

    def is_heterosexual_match_for_player(self, npc: Dict[str, object]) -> bool:
        player_sex = str(getattr(self.state, "player_sex", "Female"))
        npc_sex = self.npc_sex(npc)
        return player_sex in VALID_PLAYER_SEXES and npc_sex in VALID_PLAYER_SEXES and player_sex != npc_sex

    def is_marriageable_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        if not self.is_romance_candidate_npc(npc):
            return False
        return self.state.spouse_npc_id == npc_id or self.is_heterosexual_match_for_player(npc)

    def romance_data_for_npc(self, npc: Dict[str, object]) -> Dict[str, str]:
        data = ROMANCE_NPC_DATA.get(str(npc.get("id", "")), {})
        if isinstance(data, dict) and data:
            return data
        if self.is_procedural_npc(npc):
            traits = [
                str(trait)
                for trait in npc.get("personality_traits", []) or []
            ]
            style = (
                ", ".join(traits[:2]).lower()
                if traits
                else str(npc.get("personality", "quiet and practical")).lower()
            )
            proposal_item = "Wildflower Honey"
            likes = [str(item) for item in npc.get("likes", []) or []]
            for preferred in (
                "Wildflower Honey",
                "Ancient Preserves",
                "Berry Jam",
                "Mushroom Preserve",
                "Wildflowers",
            ):
                if preferred in likes:
                    proposal_item = preferred
                    break
            return {
                "style": style,
                "proposal_item": proposal_item,
                "vow": (
                    f"{npc.get('name', 'They')} promises that wherever the road "
                    "leads, neither of you will have to build a home alone."
                ),
            }
        return {}

    def proposal_item_for_npc(self, npc: Dict[str, object]) -> str:
        return str(self.romance_data_for_npc(npc).get("proposal_item", "Wildflower Honey"))

    def town_npc_dialogue_count(self, npc_id: str) -> int:
        npc_id = str(npc_id)
        recorded = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        procedural = self.procedural_resident_by_id(npc_id)
        if procedural:
            recorded = max(
                recorded,
                int(procedural.get("dialogue_count", 0)),
            )
            self.state.town_npc_dialogue_counts[npc_id] = recorded
        return recorded

    def romance_label_for_npc(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        if not self.is_romance_candidate_npc(npc):
            return "Not romanceable"
        if self.state.spouse_npc_id == npc_id:
            return "Spouse"
        if str(getattr(self.state, "engaged_npc_id", "")) == npc_id:
            return "Engaged"
        if not self.is_heterosexual_match_for_player(npc):
            return "Unavailable"
        points = self.town_npc_relationship(npc_id)
        if npc_id in set(self.state.dating_npc_ids or []):
            return "Ready to propose" if points >= RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP else "Dating"
        if points >= RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP:
            return "Ready to propose"
        if points >= 150:
            return "Trusted"
        if points >= 100:
            return "Close bond"
        if points >= 60:
            return "Courtship ready"
        if points >= 25:
            return "Interested"
        return "New connection"

    def romance_note_for_npc(self, npc: Dict[str, object]) -> str:
        if not self.is_romance_candidate_npc(npc):
            return "They are part of town life, but not a romance candidate."
        npc_id = str(npc.get("id", ""))
        points = self.town_npc_relationship(npc_id)
        if self.state.spouse_npc_id == npc_id:
            return "You are married; the relationship is now about showing up in ordinary ways."
        if self.state.spouse_npc_id:
            return f"You are already married to {self.town_npc_name(self.state.spouse_npc_id)}."
        if str(getattr(self.state, "engaged_npc_id", "")) == npc_id:
            return (
                f"You are engaged. The wedding is scheduled for "
                f"{self.wedding_date_label()}."
            )
        if str(getattr(self.state, "engaged_npc_id", "")):
            return (
                f"You are already engaged to "
                f"{self.town_npc_name(self.state.engaged_npc_id)}."
            )
        if not self.is_heterosexual_match_for_player(npc):
            return "This character is not romantically interested in you."
        if npc_id in set(self.state.dating_npc_ids or []):
            return "You are dating. Daily talks, useful gifts, and time together still matter."
        if points >= 60:
            return "They trust you enough to spend intentional time together."
        return "Build trust through daily conversations, useful gifts, and errands."

    def town_npc_romance_lines(self, npc: Dict[str, object]) -> List[str]:
        if not self.is_marriageable_npc(npc):
            return []
        data = self.romance_data_for_npc(npc)
        npc_id = str(npc.get("id", ""))
        item = self.proposal_item_for_npc(npc)
        points = self.town_npc_relationship(npc_id)
        talks = self.town_npc_dialogue_count(npc_id)
        today = self.town_npc_day_key()
        court_today = self.state.town_npc_last_court_day.get(npc_id) == today
        lines = [
            f"Romance: {self.romance_label_for_npc(npc)}",
            f"Courtship style: {data.get('style', 'warm')}",
            self.romance_note_for_npc(npc),
            f"Wedding ring: {self.state.inventory.get(WEDDING_RING_ITEM, 0)} owned",
            f"Personal proposal touch: {item} ({self.state.inventory.get(item, 0)} owned; optional)",
            f"Proposal: needs {RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP} friendship, {RELATIONSHIP_PROPOSAL_REQUIRED_TALKS} talks, {RELATIONSHIP_PROPOSAL_REQUIRED_COURTSHIP} courtship, and a ring.",
            f"Current: {points} friendship, {talks} talks.",
            f"Courtship time: {self.town_npc_courtship_count(npc_id)}",
            "Courtship: already spent time today" if court_today else "Courtship: available today",
        ]
        return lines

    def can_court_town_npc(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.is_marriageable_npc(npc):
            return False, f"{npc.get('name', 'They')} is not a romance candidate."
        if self.state.spouse_npc_id and self.state.spouse_npc_id != npc_id:
            return False, f"You are already married to {self.town_npc_name(self.state.spouse_npc_id)}."
        if (
            str(getattr(self.state, "engaged_npc_id", "") or "")
            and str(self.state.engaged_npc_id) != npc_id
        ):
            return False, (
                f"You are engaged to "
                f"{self.town_npc_name(self.state.engaged_npc_id)}."
            )
        today = self.town_npc_day_key()
        if self.state.town_npc_last_court_day.get(npc_id) == today:
            return False, f"You already spent courtship time with {npc.get('name', 'them')} today."
        if self.town_npc_relationship(npc_id) < RELATIONSHIP_COURTSHIP_REQUIRED_FRIENDSHIP:
            return False, "Get to know them a little better before courtship."
        return True, "Courtship available."

    def can_start_dating_with_npc(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.is_marriageable_npc(npc):
            return False, f"{npc.get('name', 'They')} is not a romance candidate."
        if self.state.spouse_npc_id:
            return False, f"You are already married to {self.town_npc_name(self.state.spouse_npc_id)}."
        if npc_id in set(self.state.dating_npc_ids or []):
            return False, "You are already dating."
        points = self.town_npc_relationship(npc_id)
        if points < RELATIONSHIP_DATING_REQUIRED_FRIENDSHIP:
            return False, f"Dating needs {RELATIONSHIP_DATING_REQUIRED_FRIENDSHIP} friendship. Current: {points}."
        talks = self.town_npc_dialogue_count(npc_id)
        if talks < RELATIONSHIP_DATING_REQUIRED_TALKS:
            return False, f"Dating needs more conversations: {talks}/{RELATIONSHIP_DATING_REQUIRED_TALKS}."
        courtships = self.town_npc_courtship_count(npc_id)
        if courtships < RELATIONSHIP_DATING_REQUIRED_COURTSHIP:
            return False, f"Dating needs more courtship time: {courtships}/{RELATIONSHIP_DATING_REQUIRED_COURTSHIP}."
        return True, "Ready to start dating."

    def town_npc_courtship_scene_line(self, npc: Dict[str, object]) -> str:
        data = self.town_npc_dialogue_data(npc)
        scene = data.get("courtship")
        if scene:
            return str(scene)
        return f"You spend quiet time with {npc.get('name')}, away from the usual errands."

    def court_town_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        ok, reason = self.can_court_town_npc(npc)
        if not ok:
            self.vertical_panel_view(f"{npc.get('name', 'Villager')} Courtship", self.town_npc_romance_lines(npc) + ["", reason], LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            self.set_message(reason)
            return False

        before = self.town_npc_relationship(npc_id)
        gain = RELATIONSHIP_SPOUSE_COURTSHIP_GAIN if self.state.spouse_npc_id == npc_id else (RELATIONSHIP_DATING_COURTSHIP_GAIN if npc_id in set(self.state.dating_npc_ids or []) else RELATIONSHIP_COURTSHIP_GAIN)
        actual_gain = self.adjust_town_npc_relationship(npc_id, gain)
        after = self.town_npc_relationship(npc_id)
        self.state.town_npc_last_court_day[npc_id] = self.town_npc_day_key()
        self.increment_town_npc_courtship_count(npc_id)
        started_dating = False
        dating_ok, _dating_reason = self.can_start_dating_with_npc(npc)
        if dating_ok:
            self.state.dating_npc_ids.append(npc_id)
            started_dating = True

        rows = [
            f"{npc.get('name')} Courtship",
            "",
            self.town_npc_courtship_scene_line(npc),
            f"Relationship: {before} -> {after} ({actual_gain:+})",
            "",
            self.romance_note_for_npc(npc),
        ]
        if started_dating:
            rows.extend(["", f"{npc.get('name')} is now dating you."])
        if self.state.spouse_npc_id == npc_id:
            rows.extend(["", "It feels less like impressing each other and more like keeping the home fires noticed."])
        self.vertical_panel_view(f"{npc.get('name')} Courtship", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Spent time with {npc.get('name')}. Relationship {actual_gain:+}.")
        return True

    def can_propose_to_town_npc(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.is_marriageable_npc(npc):
            return False, f"{npc.get('name', 'They')} is not a romance candidate."
        if self.state.spouse_npc_id == npc_id:
            return False, f"You are already married to {npc.get('name', 'them')}."
        if self.state.spouse_npc_id:
            return False, f"You are already married to {self.town_npc_name(self.state.spouse_npc_id)}."
        if str(getattr(self.state, "engaged_npc_id", "") or ""):
            return False, (
                f"You are engaged to "
                f"{self.town_npc_name(self.state.engaged_npc_id)}."
            )
        if str(getattr(self.state, "engaged_npc_id", "")) == npc_id:
            return False, f"You are already engaged to {npc.get('name', 'them')}."
        if str(getattr(self.state, "engaged_npc_id", "")):
            return False, (
                f"You are already engaged to "
                f"{self.town_npc_name(self.state.engaged_npc_id)}."
            )
        points = self.town_npc_relationship(npc_id)
        if points < RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP:
            return False, f"Relationship needs to reach {RELATIONSHIP_PROPOSAL_REQUIRED_FRIENDSHIP} before proposing. Current: {points}."
        talks = self.town_npc_dialogue_count(npc_id)
        if talks < RELATIONSHIP_PROPOSAL_REQUIRED_TALKS:
            return False, f"Talk with them more before proposing. Current talks: {talks}/{RELATIONSHIP_PROPOSAL_REQUIRED_TALKS}."
        courtships = self.town_npc_courtship_count(npc_id)
        if courtships < RELATIONSHIP_PROPOSAL_REQUIRED_COURTSHIP:
            return False, f"Spend more courtship time before proposing. Current: {courtships}/{RELATIONSHIP_PROPOSAL_REQUIRED_COURTSHIP}."
        if self.is_sample_milestone_npc(npc_id) and not self.has_relationship_milestone(npc_id, "trusted"):
            return False, "A trust milestone needs to happen before proposing."
        if self.state.inventory.get(WEDDING_RING_ITEM, 0) <= 0:
            return False, (
                f"You need 1 {WEDDING_RING_ITEM}. "
                f"The General Store sells one for ${WEDDING_RING_PRICE}."
            )
        return True, "Ready to propose."

    def proposal_status_lines(self, npc: Dict[str, object]) -> List[str]:
        ok, reason = self.can_propose_to_town_npc(npc)
        lines = self.town_npc_romance_lines(npc)
        lines.extend(["", "Proposal:", reason])
        if ok:
            lines.append("Choose Propose again from their menu when you are ready.")
        return lines

    def can_purchase_wedding_ring(self) -> Tuple[bool, str]:
        if int(self.state.inventory.get(WEDDING_RING_ITEM, 0)) > 0:
            return False, "You already own a wedding ring."
        if str(getattr(self.state, "engaged_npc_id", "") or ""):
            return False, "Your engagement ring has already been offered."
        if str(getattr(self.state, "spouse_npc_id", "") or ""):
            return False, "You are already married."
        if int(self.state.money) < WEDDING_RING_PRICE:
            return False, f"Costs ${WEDDING_RING_PRICE}."
        return True, f"Costs ${WEDDING_RING_PRICE}; required for a proposal."

    def purchase_wedding_ring(self) -> bool:
        ok, reason = self.can_purchase_wedding_ring()
        if not ok:
            self.set_message(reason)
            return False
        self.state.money -= WEDDING_RING_PRICE
        self.state.inventory[WEDDING_RING_ITEM] = 1
        self.autosave_with_message(
            f"Bought a {WEDDING_RING_ITEM} for ${WEDDING_RING_PRICE}."
        )
        return True

    def date_after_days(self, days: int) -> Tuple[int, int, int]:
        month = int(self.state.month)
        day = int(self.state.day)
        year = int(self.state.year)
        for _ in range(max(0, int(days))):
            month, day, year = advance_date(month, day, year)
        return month, day, year

    def wedding_date_label(self) -> str:
        return self.family_date_label(
            self.state.wedding_month,
            self.state.wedding_day,
            self.state.wedding_year,
        )

    def choose_scheduled_wedding_date(
        self,
        npc: Dict[str, object],
    ) -> Optional[Tuple[int, int, int]]:
        options = [
            (7, "One week"),
            (14, "Two weeks"),
            (28, "Four weeks"),
        ]
        items = []
        for days, label in options:
            month, day, year = self.date_after_days(days)
            items.append(
                MenuItem(
                    label=label,
                    value=days,
                    enabled=True,
                    hint=format_date(month, day, year),
                )
            )
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(
            f"Wedding Date with {npc.get('name', 'Partner')}",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return None
        return self.date_after_days(int(choice.value))

    def propose_to_town_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        ok, reason = self.can_propose_to_town_npc(npc)
        if not ok:
            self.vertical_panel_view(f"Proposal to {npc.get('name', 'Villager')}", self.proposal_status_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            self.set_message(reason)
            return False

        wedding_date = self.choose_scheduled_wedding_date(npc)
        if wedding_date is None:
            self.set_message("Proposal cancelled before setting a wedding date.")
            return False

        personal_item = self.proposal_item_for_npc(npc)
        self.state.inventory[WEDDING_RING_ITEM] = max(
            0,
            int(self.state.inventory.get(WEDDING_RING_ITEM, 0)) - 1,
        )
        self.state.engaged_npc_id = npc_id
        (
            self.state.engagement_month,
            self.state.engagement_day,
            self.state.engagement_year,
        ) = (
            int(self.state.month),
            int(self.state.day),
            int(self.state.year),
        )
        (
            self.state.wedding_month,
            self.state.wedding_day,
            self.state.wedding_year,
        ) = wedding_date
        self.state.dating_npc_ids = [npc_id]
        engagement_relationship = min(
            RELATIONSHIP_MAX,
            max(self.town_npc_relationship(npc_id), 205),
        )
        self.state.town_npc_relationships[npc_id] = engagement_relationship
        procedural = self.procedural_resident_by_id(npc_id)
        if procedural:
            procedural["relationship"] = engagement_relationship
            memories = list(procedural.get("memories", []) or [])
            memories.append(
                f"{getattr(self.state, 'date_label', '')} - Became engaged to "
                f"{getattr(self.state, 'player_name', 'the farmer')}."
            )
            procedural["memories"] = memories[-16:]
        self.state.town_npc_last_proposal_day[npc_id] = self.town_npc_day_key()

        vow = self.romance_data_for_npc(npc).get("vow", f"{npc.get('name')} promises to build a life beside you.")
        rows = [
            f"Proposal to {npc.get('name')}",
            "",
            f"You offer the {WEDDING_RING_ITEM}.",
            "",
            str(vow),
            "",
            f"{npc.get('name')} accepts.",
            "",
            f"Wedding date: {self.wedding_date_label()}",
            "The date has been marked on the calendar. The marriage begins when the ceremony occurs.",
        ]
        if self.state.inventory.get(personal_item, 0) > 0:
            rows.append(
                f"You also have {personal_item}, something especially meaningful to them."
            )
        self.record_family_event(
            "Engagement",
            f"Became engaged to {npc.get('name')}; wedding scheduled for "
            f"{self.wedding_date_label()}.",
            flag=(
                f"engagement:{npc_id}:{self.state.year}:"
                f"{self.state.month}:{self.state.day}"
            ),
        )
        self.vertical_panel_view(f"Proposal to {npc.get('name')}", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(
            f"{npc.get('name')} accepted. Wedding: {self.wedding_date_label()}."
        )
        return True

    def wedding_ceremony_lines(
        self,
        npc: Dict[str, object],
    ) -> List[str]:
        name = str(npc.get("name", "your partner"))
        vow = str(
            self.romance_data_for_npc(npc).get(
                "vow",
                f"{name} promises to build a life beside you.",
            )
        )
        weather = str(getattr(self.state, "weather", "Clear"))
        setting = (
            "Rain taps against the Town Hall windows while neighbors crowd warmly inside."
            if weather in {"Rainy", "Stormy"}
            else "Snow softens the town outside while the ceremony gathers indoors."
            if weather in {"Snowy", "Blizzard"}
            else "The town gathers beneath clear light, with the Town Hall doors left open."
        )
        family_names = [
            str(child.get("name", "your child"))
            for child in getattr(self.state, "children", []) or []
        ]
        family_line = (
            f"Your household gathers close: {', '.join(family_names[:4])}."
            if family_names
            else "Friends and neighbors fill the front rows."
        )
        return [
            f"Wedding of {self.state.player_name} and {name}",
            "",
            setting,
            family_line,
            "",
            "The town clerk asks each of you to speak plainly about the life you are choosing.",
            vow,
            "",
            "You exchange vows and sign the household ledger.",
            "The room breaks into applause, conversation, and the practical chaos of shared food.",
            "",
            f"Marriage recorded: {format_date(self.state.month, self.state.day, self.state.year)}",
        ]

    def initialize_spouse_lifespan(
        self,
        npc: Dict[str, object],
    ) -> None:
        if int(getattr(self.state, "spouse_lifespan_age", 0) or 0) > 0:
            return
        npc_id = str(npc.get("id", "spouse"))
        try:
            age = int(npc.get("age_years", 0) or 0)
        except Exception:
            age = 0
        if age <= 0:
            seed = sum(
                (index + 1) * ord(character)
                for index, character in enumerate(npc_id)
            )
            age = 24 + seed % 26
        birthday_month, birthday_day = self.npc_birthday(npc)
        birthday_passed = (
            int(self.state.month),
            int(self.state.day),
        ) >= (int(birthday_month), int(birthday_day))
        birth_year = int(self.state.year) - age - (0 if birthday_passed else 1)
        self.state.spouse_birth_year = birth_year
        if hasattr(self, "dynasty_lifespan_for_identity"):
            lifespan = self.dynasty_lifespan_for_identity(
                str(npc.get("name", npc_id)),
                birth_year,
                int(getattr(self.state, "player_generation", 1)),
            )
        else:
            lifespan = 88 + (
                sum(ord(character) for character in npc_id) % 14
            )
        self.state.spouse_lifespan_age = max(
            70,
            min(115, max(age + 5, int(lifespan))),
        )

    def complete_scheduled_wedding(
        self,
        interactive: bool = True,
    ) -> str:
        npc_id = str(getattr(self.state, "engaged_npc_id", "") or "")
        if not npc_id:
            return ""
        npc = self.npc_record_by_id(npc_id)
        if not npc or bool(npc.get("deceased", False)):
            self.state.engaged_npc_id = ""
            self.state.wedding_month = 0
            self.state.wedding_day = 0
            self.state.wedding_year = 0
            return " The scheduled wedding could not proceed."

        self.state.spouse_npc_id = npc_id
        self.state.spouse_moved_to_farm = False
        self.state.marriage_month = int(self.state.month)
        self.state.marriage_day = int(self.state.day)
        self.state.marriage_year = int(self.state.year)
        self.state.engaged_npc_id = ""
        self.state.wedding_month = 0
        self.state.wedding_day = 0
        self.state.wedding_year = 0
        self.state.town_npc_relationships[npc_id] = min(
            RELATIONSHIP_MAX,
            max(self.town_npc_relationship(npc_id), 220),
        )
        self.state.family_bond = min(
            999,
            int(getattr(self.state, "family_bond", 0)) + 10,
        )
        self.state.spouse_birth_year = 0
        self.state.spouse_lifespan_age = 0
        self.state.spouse_frozen_age = 0
        self.initialize_spouse_lifespan(npc)
        self.state.marriage_history.append({
            "spouse_npc_id": npc_id,
            "spouse_name": str(npc.get("name", npc_id)),
            "marriage_month": int(self.state.month),
            "marriage_day": int(self.state.day),
            "marriage_year": int(self.state.year),
            "status": "married",
        })
        self.state.marriage_history = self.state.marriage_history[-12:]

        procedural = self.procedural_resident_by_id(npc_id)
        if procedural:
            procedural["relationship"] = self.state.town_npc_relationships[npc_id]
            memories = list(procedural.get("memories", []) or [])
            memories.append(
                f"{getattr(self.state, 'date_label', '')} - Married "
                f"{getattr(self.state, 'player_name', 'the farmer')}."
            )
            procedural["memories"] = memories[-16:]

        self.record_family_event(
            "Wedding",
            f"Married {npc.get('name')} in a Town Hall ceremony.",
            flag=(
                f"wedding:{npc_id}:{self.state.year}:"
                f"{self.state.month}:{self.state.day}"
            ),
        )
        if interactive:
            self.vertical_panel_view(
                "Wedding Day",
                self.wedding_ceremony_lines(npc),
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
            )
        return f" Wedding day: you married {npc.get('name')}."

    def process_scheduled_wedding_overnight(
        self,
        interactive: bool = True,
    ) -> str:
        if not str(getattr(self.state, "engaged_npc_id", "") or ""):
            return ""
        if not (
            int(getattr(self.state, "wedding_month", 0) or 0)
            and int(getattr(self.state, "wedding_day", 0) or 0)
            and int(getattr(self.state, "wedding_year", 0) or 0)
        ):
            return ""
        if not date_reached(
            self.state.month,
            self.state.day,
            self.state.year,
            self.state.wedding_month,
            self.state.wedding_day,
            self.state.wedding_year,
        ):
            return ""
        return self.complete_scheduled_wedding(interactive=interactive)

    def spouse_age_years(self, npc: Optional[Dict[str, object]] = None) -> int:
        npc = npc or self.npc_record_by_id(self.state.spouse_npc_id)
        if not npc:
            return 0
        if (
            not self.aging_and_death_active()
            and int(getattr(self.state, "spouse_frozen_age", 0) or 0) > 0
        ):
            return int(self.state.spouse_frozen_age)
        self.initialize_spouse_lifespan(npc)
        birthday_month, birthday_day = self.npc_birthday(npc)
        age = int(self.state.year) - int(self.state.spouse_birth_year)
        if (
            int(self.state.month),
            int(self.state.day),
        ) < (int(birthday_month), int(birthday_day)):
            age -= 1
        return max(0, age)

    def handle_spouse_death(
        self,
        reason: str = "old age",
        interactive: bool = True,
    ) -> str:
        npc_id = str(getattr(self.state, "spouse_npc_id", "") or "")
        if not npc_id:
            return ""
        npc = self.npc_record_by_id(npc_id) or {"id": npc_id}
        name = str(npc.get("name") or self.town_npc_name(npc_id))
        age = self.spouse_age_years(npc)
        npc["deceased"] = True
        npc["death_year"] = int(self.state.year)
        npc["death_age"] = age
        npc["activity"] = "remembered by the household"
        if npc_id not in self.state.deceased_spouse_npc_ids:
            self.state.deceased_spouse_npc_ids.append(npc_id)
        for record in reversed(self.state.marriage_history):
            if (
                str(record.get("spouse_npc_id", "")) == npc_id
                and str(record.get("status", "married")) == "married"
            ):
                record["status"] = "widowed"
                record["death_month"] = int(self.state.month)
                record["death_day"] = int(self.state.day)
                record["death_year"] = int(self.state.year)
                record["death_age"] = age
                record["death_reason"] = str(reason)
                break
        else:
            self.state.marriage_history.append({
                "spouse_npc_id": npc_id,
                "spouse_name": name,
                "marriage_month": int(self.state.marriage_month),
                "marriage_day": int(self.state.marriage_day),
                "marriage_year": int(self.state.marriage_year),
                "status": "widowed",
                "death_month": int(self.state.month),
                "death_day": int(self.state.day),
                "death_year": int(self.state.year),
                "death_age": age,
                "death_reason": str(reason),
            })

        follower_id = ""
        if hasattr(self, "travel_follower_identity_for_npc_id"):
            follower_id = str(
                self.travel_follower_identity_for_npc_id(npc_id) or ""
            )
        if follower_id:
            self.state.travel_follower_ids = [
                value
                for value in self.state.travel_follower_ids
                if str(value) != follower_id
            ]
            self.state.travel_follower_states.pop(follower_id, None)

        self.state.dating_npc_ids = [
            value
            for value in self.state.dating_npc_ids
            if str(value) != npc_id
        ]
        self.state.spouse_npc_id = ""
        self.state.spouse_moved_to_farm = False
        self.state.marriage_month = 0
        self.state.marriage_day = 0
        self.state.marriage_year = 0
        self.state.spouse_birth_year = 0
        self.state.spouse_lifespan_age = 0
        self.state.spouse_frozen_age = 0
        self.record_family_event(
            "Spouse Passing",
            f"{name} died peacefully from {reason} at age {age}.",
            flag=f"spouse_death:{npc_id}:{self.state.year}",
        )
        if interactive:
            self.vertical_panel_view(
                "A Family Passing",
                [
                    f"{name} died peacefully from {reason} at age {age}.",
                    "",
                    "The household enters a period of mourning.",
                    "The marriage remains in the family record.",
                    "In time, you may court and marry again if you choose.",
                ],
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
            )
        return f" {name}, your spouse, died peacefully from {reason} at age {age}."

    def process_spouse_lifespan_overnight(
        self,
        interactive: bool = True,
    ) -> str:
        if not str(getattr(self.state, "spouse_npc_id", "") or ""):
            return ""
        if not self.aging_and_death_active():
            return ""
        npc = self.npc_record_by_id(self.state.spouse_npc_id)
        if not npc:
            return ""
        self.initialize_spouse_lifespan(npc)
        if self.npc_birthday(npc) != (
            int(self.state.month),
            int(self.state.day),
        ):
            return ""
        if self.spouse_age_years(npc) < int(self.state.spouse_lifespan_age):
            return ""
        return self.handle_spouse_death(
            "old age",
            interactive=interactive,
        )

    def spouse_lives_on_farm(self) -> bool:
        return bool(self.state.spouse_npc_id and self.state.spouse_moved_to_farm)

    def family_date_label(self, month: int, day: int, year: int) -> str:
        if int(month) <= 0 or int(day) <= 0 or int(year) <= 0:
            return "not recorded"
        return format_date(int(month), int(day), int(year))

    def marriage_date_label(self) -> str:
        return self.family_date_label(self.state.marriage_month, self.state.marriage_day, self.state.marriage_year)

    def has_family_event_flag(self, flag: str) -> bool:
        return str(flag) in set(getattr(self.state, "family_event_flags", []) or [])

    def mark_family_event_flag(self, flag: str):
        flag = str(flag or "").strip()
        if not flag:
            return
        if not isinstance(self.state.family_event_flags, list):
            self.state.family_event_flags = []
        if flag not in self.state.family_event_flags:
            self.state.family_event_flags.append(flag)

    def record_family_event(self, title: str, detail: str = "", flag: str = ""):
        if not isinstance(self.state.family_event_log, list):
            self.state.family_event_log = []
        date = format_date(self.state.month, self.state.day, self.state.year)
        line = f"{date} - {title}"
        if detail:
            line += f": {detail}"
        self.state.family_event_log.append(line)
        self.state.family_event_log = [str(row) for row in self.state.family_event_log if row is not None][-30:]
        if flag:
            self.mark_family_event_flag(flag)

    def family_event_log_lines(self) -> List[str]:
        lines = ["FAMILY MEMORIES", ""]
        if not self.state.family_event_log:
            lines.append("No family milestones recorded yet.")
            return lines
        lines.extend(f"- {line}" for line in self.state.family_event_log[-18:])
        return lines

    def family_bond_score(self) -> int:
        try:
            return max(0, min(999, int(getattr(self.state, "family_bond", 0))))
        except Exception:
            return 0

    def family_bond_rank(self) -> str:
        score = self.family_bond_score()
        if score >= 300:
            return "Deeply Rooted"
        if score >= 180:
            return "Close-Knit"
        if score >= 90:
            return "Comfortable"
        if score >= 35:
            return "Settling In"
        return "New Household"

    def adjust_family_bond(self, amount: int) -> int:
        before = self.family_bond_score()
        after = max(0, min(999, before + int(amount)))
        self.state.family_bond = after
        return after - before

    def family_bond_lines(self) -> List[str]:
        return [
            "Household bond",
            f"- Rank: {self.family_bond_rank()}",
            f"- Score: {self.family_bond_score()}/999",
            f"- Last shared meal: {self.state.family_last_meal or 'none recorded'}",
            f"- Sleep stamina bonus: +{self.family_sleep_bonus()}",
        ]

    def family_sleep_bonus(self) -> int:
        if self.family_member_count() <= 1:
            return 0
        score = self.family_bond_score()
        if score >= 300:
            return 8
        if score >= 180:
            return 6
        if score >= 90:
            return 4
        if score >= 35:
            return 2
        return 0

    def family_today_lines(self) -> List[str]:
        lines = [
            "TODAY AT HOME",
            "",
            f"Date: {format_date(self.state.month, self.state.day, self.state.year)}",
            f"Household residence: {self.household_residence_label() if hasattr(self, 'household_residence_label') else 'the farmhouse'}",
            f"Household bond: {self.family_bond_rank()} ({self.family_bond_score()})",
            "",
            "Available today:",
        ]
        meal_ok, meal_reason = self.family_meal_available()
        lines.append(f"- Family meal: {'ready' if meal_ok else meal_reason}")
        if self.spouse_lives_on_farm():
            lines.append(f"- Spouse support: {self.spouse_support_mode()}")
        elif str(getattr(self.state, "engaged_npc_id", "") or ""):
            lines.append(
                f"- Wedding: {self.wedding_date_label()} with "
                f"{self.town_npc_name(self.state.engaged_npc_id)}"
            )
        if self.state.pregnancy_active:
            lines.append(f"- Pregnancy: month {self.pregnancy_month_number()} of 9")
            lines.append(f"- Check-in: {'ready' if self.pregnancy_checkup_available() else 'not ready or completed'}")
        spouse = self.npc_record_by_id(self.state.spouse_npc_id)
        if spouse:
            scene_key, scene_title = self.available_marriage_scene(spouse)
            lines.append(f"- Marriage event: {scene_title if scene_key else 'none ready'}")
        if self.state.children:
            lines.extend(["", "Children:"])
        for child in self.state.children:
            child = self.ensure_child_profile_fields(child)
            key = self.child_key(child)
            gift_done = self.state.child_last_gift_day.get(key) == self.town_npc_day_key() if isinstance(self.state.child_last_gift_day, dict) else False
            lesson_done = self.state.child_last_lesson_day.get(key) == self.town_npc_day_key() if isinstance(self.state.child_last_lesson_day, dict) else False
            birthday = " birthday" if self.is_child_birthday(child) else ""
            lines.append(
                f"- {child.get('name', 'Child')}: {self.household_child_stage(child)}{birthday}; "
                f"gift {'done' if gift_done else 'open'}, lesson {'done' if lesson_done else 'open'}, "
                f"chore {self.child_chore_assignment(child)}"
            )
        if not self.state.children and not self.state.spouse_npc_id:
            lines.append("- No spouse or children in the household yet.")
        return lines

    def family_growth_report_lines(self) -> List[str]:
        lines = [
            "FAMILY GROWTH",
            "",
            f"Household bond: {self.family_bond_rank()} ({self.family_bond_score()})",
            f"Children: {len(self.state.children)}",
        ]
        if not self.state.children:
            lines.extend([
                "",
                f"No children are living in {self.household_residence_label() if hasattr(self, 'household_residence_label') else 'the farmhouse'} yet.",
            ])
            return lines
        for child in self.state.children:
            child = self.ensure_child_profile_fields(child)
            age_months = self.household_child_age_months(child)
            stage = self.household_child_stage(child)
            next_stage_line = "fully grown for the current system"
            for next_stage, month_mark in self.child_stage_months().items():
                if age_months < month_mark:
                    next_stage_line = f"{next_stage} in {month_mark - age_months} month(s)"
                    break
            top_topic, top_points = self.child_top_learning_topic(child)
            lines.extend([
                "",
                f"{child.get('name', 'Child')} - {stage}",
                f"- {self.household_child_age_display_line(child)}",
                f"- Next stage: {next_stage_line}",
                f"- Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
                f"- Path: {child.get('apprentice_path', 'Helper')}",
                f"- Learning: {top_topic if top_topic else 'none yet'}{f' ({top_points})' if top_topic else ''}",
                f"- Chore: {self.child_chore_assignment(child)}",
            ])
        return lines

    def family_member_count(self) -> int:
        elder_count = sum(
            1
            for elder in getattr(self.state, "dynasty_elders", []) or []
            if isinstance(elder, dict) and elder.get("active", True)
        )
        resident_kin_count = sum(
            1
            for kin in getattr(self.state, "dynasty_kin", []) or []
            if isinstance(kin, dict)
            and kin.get("active", True)
            and not kin.get("linked_existing_npc")
            and str(kin.get("residence", "")) == "Farmhouse"
        )
        return (
            1
            + (1 if self.spouse_lives_on_farm() else 0)
            + len(getattr(self.state, "children", []) or [])
            + elder_count
            + resident_kin_count
        )

    def family_meal_candidates(self) -> List[Tuple[str, int, int]]:
        if hasattr(self, "edible_items_in_inventory"):
            return list(self.edible_items_in_inventory())
        rows: List[Tuple[str, int, int]] = []
        for item_name, qty in sorted(self.state.inventory.items()):
            if int(qty) > 0 and is_food_item(str(item_name)):
                rows.append((str(item_name), int(qty), food_stamina_value(str(item_name))))
        return rows

    def family_meal_available(self) -> Tuple[bool, str]:
        if self.family_member_count() <= 1:
            return False, "Family meals need a spouse or child in the household."
        if self.state.family_meal_last_day == self.town_npc_day_key():
            return False, "The household already shared a meal today."
        if not self.family_meal_candidates():
            return False, "You are not carrying any food to share."
        return True, "Share food with the household."

    def share_family_meal(self, item_name: str) -> bool:
        item_name = str(item_name)
        ok, reason = self.family_meal_available()
        if not ok:
            self.set_message(reason)
            return False
        if self.state.inventory.get(item_name, 0) <= 0 or not is_food_item(item_name):
            self.set_message(f"You do not have a shareable {item_name}.")
            return False

        self.state.inventory[item_name] -= 1
        if self.state.inventory[item_name] <= 0:
            self.state.inventory.pop(item_name, None)

        participants = self.family_member_count()
        stamina_value = max(1, food_stamina_value(item_name))
        bond_gain = min(18, 4 + participants + max(1, stamina_value // 12))
        self.adjust_family_bond(bond_gain)
        if self.spouse_lives_on_farm():
            self.adjust_town_npc_relationship(self.state.spouse_npc_id, min(5, 2 + stamina_value // 25))
        for child in self.state.children:
            self.adjust_child_affection(child, 3 + (1 if item_name == str(self.ensure_child_profile_fields(child).get("favorite_gift", "")) else 0))

        recovered = min(10, max(2, stamina_value // 4))
        recovered = self.restore_stamina(recovered)
        self.state.family_meal_last_day = self.town_npc_day_key()
        self.state.family_last_meal = item_name
        self.record_family_event("Family Meal", f"Shared {item_name} with the household.")
        self.autosave_with_message(f"Shared {item_name} at home. Household bond +{bond_gain}. Stamina +{recovered}.")
        return True

    def family_meal_lines(self) -> List[str]:
        ok, reason = self.family_meal_available()
        lines = [
            "FAMILY MEAL",
            "",
            f"Household: {self.family_member_count()} member(s)",
            f"Status: {'ready' if ok else reason}",
            f"Last meal: {self.state.family_last_meal or 'none'}",
            "",
            *self.family_bond_lines(),
            "",
            "Carried food:",
        ]
        meals = self.family_meal_candidates()
        if meals:
            for item_name, qty, stamina in meals[:14]:
                lines.append(f"- {item_name} x{qty}: +{stamina} stamina food")
        else:
            lines.append("- No food carried.")
        return lines

    def family_meal_menu(self):
        while True:
            ok, reason = self.family_meal_available()
            items: List[MenuItem] = []
            for item_name, qty, stamina in self.family_meal_candidates():
                items.append(MenuItem(label=item_name, value=item_name, enabled=ok, hint=f"x{qty}; +{stamina}"))
            items.append(MenuItem(label="Meal notes", value="notes", enabled=True, hint=reason if not ok else "household bond"))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Family Meal", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed family meal menu.")
                return MENU_BACK
            if choice.value == "notes":
                self.vertical_panel_view("Family Meal", self.family_meal_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if self.share_family_meal(str(choice.value)):
                return "changed"

    def spouse_support_modes(self) -> Dict[str, Dict[str, str]]:
        return {
            "Balanced": {"label": "Balanced", "note": "A little food, a little tidying, and no strong priority."},
            "Meals": {"label": "Meals", "note": "Your spouse tries to keep simple food ready overnight."},
            "Farm": {"label": "Farm", "note": "Your spouse focuses on seeds, small supplies, and farm prep."},
            "Forage": {"label": "Forage", "note": "Your spouse keeps an eye out for useful wild goods."},
            "Rest": {"label": "Rest", "note": "Your spouse keeps the house quiet instead of producing items."},
        }

    def spouse_support_mode(self) -> str:
        mode = str(getattr(self.state, "spouse_support_mode", "Balanced") or "Balanced")
        if mode not in self.spouse_support_modes():
            mode = "Balanced"
            self.state.spouse_support_mode = mode
        return mode

    def spouse_support_mode_lines(self) -> List[str]:
        lines = [
            "SPOUSE SUPPORT",
            "",
            f"Current focus: {self.spouse_support_mode()}",
            f"Household help: {'enabled' if self.state.family_help_enabled else 'disabled'}",
            "",
            "Focus options:",
        ]
        for mode, data in self.spouse_support_modes().items():
            marker = "*" if mode == self.spouse_support_mode() else "-"
            lines.append(f"{marker} {mode}: {data['note']}")
        lines.extend(["", "Support happens overnight when household help is enabled."])
        return lines

    def set_spouse_support_mode(self, mode: str) -> bool:
        mode = str(mode)
        if mode not in self.spouse_support_modes():
            self.set_message("Unknown spouse support focus.")
            return False
        self.state.spouse_support_mode = mode
        self.record_family_event("Spouse Support", f"Household support focus set to {mode}.")
        self.autosave_with_message(f"Spouse support focus set to {mode}.")
        return True

    def spouse_support_menu(self):
        if not self.spouse_lives_on_farm():
            self.set_message("Spouse support is available after your spouse moves onto the farm.")
            return MENU_BACK
        while True:
            items = [
                MenuItem(label=mode, value=mode, enabled=True, hint=data["note"])
                for mode, data in self.spouse_support_modes().items()
            ]
            items.append(MenuItem(label="Support notes", value="notes", enabled=True, hint=self.spouse_support_mode()))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Spouse Support", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed spouse support menu.")
                return MENU_BACK
            if choice.value == "notes":
                self.vertical_panel_view("Spouse Support", self.spouse_support_mode_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if self.set_spouse_support_mode(str(choice.value)):
                return "changed"

    def spouse_help_drop(self) -> Tuple[str, int, str]:
        mode = self.spouse_support_mode()
        if mode == "Meals":
            if self.has_kitchen_access():
                return "Field Snack", 2, "packed simple food for the household"
            return "Berries", 2, "set aside berries for the household"
        if mode == "Farm":
            return "Mixed Seeds", 2, "sorted useful farm supplies before bed"
        if mode == "Forage":
            return "Wildflower", 1, "brought in a useful wildflower from the path"
        if mode == "Rest":
            return "", 0, "kept the farmhouse quiet so everyone could recover"
        item = "Field Snack" if self.has_kitchen_access() else "Berries"
        return item, 1, f"prepared {item}"

    def marriage_days_elapsed(self) -> int:
        if not (self.state.marriage_month and self.state.marriage_day and self.state.marriage_year):
            return 0
        return max(
            0,
            self.absolute_game_day()
            - self.absolute_game_day(self.state.marriage_month, self.state.marriage_day, self.state.marriage_year),
        )

    def marriage_anniversary_today(self) -> bool:
        return bool(
            self.state.spouse_npc_id
            and self.state.marriage_month == self.state.month
            and self.state.marriage_day == self.state.day
            and self.state.year > self.state.marriage_year
        )

    def available_marriage_scene(self, npc: Dict[str, object]) -> Tuple[str, str]:
        npc_id = str(npc.get("id", ""))
        if self.state.spouse_npc_id != npc_id:
            return "", ""
        if self.marriage_anniversary_today():
            key = f"anniversary:{self.state.year}:{npc_id}"
            if not self.has_family_event_flag(key):
                return key, "Anniversary"
        if self.state.spouse_moved_to_farm and self.marriage_days_elapsed() >= 7:
            key = f"first_household_conflict:{npc_id}"
            if not self.has_family_event_flag(key):
                return key, "First Household Conflict"
        if self.state.spouse_moved_to_farm and self.marriage_days_elapsed() >= 14:
            key = f"shared_household_goal:{npc_id}"
            if not self.has_family_event_flag(key):
                return key, "Shared Household Goal"
        return "", ""

    def marriage_scene_lines(self, npc: Dict[str, object], scene_key: str, scene_title: str) -> List[str]:
        name = str(npc.get("name", "your spouse"))
        if scene_key.startswith("anniversary:"):
            return [
                "Anniversary",
                "",
                f"You and {name} pause long enough to remember that the household began as a choice, not a checklist.",
                f"{name} marks the calendar and asks what kind of year you want to build next.",
                "",
                "Relationship: the marriage feels steadier for being noticed.",
            ]
        if scene_key.startswith("first_household_conflict:"):
            return [
                "First Household Conflict",
                "",
                f"The first real household disagreement with {name} is not dramatic. That almost makes it harder to ignore.",
                "You talk through chores, space, sleep, and the small expectations neither of you said out loud.",
                "",
                "Outcome: the farmhouse feels more honest afterward.",
            ]
        return [
            "Shared Household Goal",
            "",
            f"You and {name} sit with the farm ledger and choose a shared priority for the season.",
            "The goal is simple: keep the home useful, keep meals stocked, and make room for family life before it becomes urgent.",
            "",
            "Outcome: household help and family planning are easier to track from the family status page.",
        ]

    def play_marriage_scene(self, npc: Dict[str, object]) -> bool:
        scene_key, scene_title = self.available_marriage_scene(npc)
        if not scene_key:
            self.set_message("No new marriage scene is ready.")
            return False
        rows = self.marriage_scene_lines(npc, scene_key, scene_title)
        self.record_family_event(scene_title, f"Shared with {npc.get('name', 'your spouse')}.", flag=scene_key)
        self.adjust_town_npc_relationship(str(npc.get("id", "")), 3)
        self.vertical_panel_view(scene_title, rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Shared a marriage scene with {npc.get('name', 'your spouse')}.")
        return True

    def marriage_status_lines(self) -> List[str]:
        if not self.state.spouse_npc_id:
            if str(getattr(self.state, "engaged_npc_id", "") or ""):
                return [
                    "Engagement",
                    "",
                    f"Fiance: {self.town_npc_name(self.state.engaged_npc_id)}",
                    f"Wedding date: {self.wedding_date_label()}",
                    "The ceremony will occur when that date arrives.",
                ]
            history = [
                record
                for record in getattr(self.state, "marriage_history", []) or []
                if isinstance(record, dict)
            ]
            if history and str(history[-1].get("status", "")) == "widowed":
                last = history[-1]
                return [
                    "Marriage: widowed",
                    "",
                    f"Late spouse: {last.get('spouse_name', 'remembered spouse')}",
                    f"Married: {self.family_date_label(last.get('marriage_month', 0), last.get('marriage_day', 0), last.get('marriage_year', 0))}",
                    f"Died: {self.family_date_label(last.get('death_month', 0), last.get('death_day', 0), last.get('death_year', 0))}",
                    "Remarriage: available whenever you are ready to court someone again.",
                ]
            return ["Marriage: none"]
        spouse_name = self.town_npc_name(self.state.spouse_npc_id)
        spouse = self.npc_record_by_id(self.state.spouse_npc_id)
        spouse_age = self.spouse_age_years(spouse) if spouse else 0
        age_line = (
            f"Spouse life stage: {self.player_life_stage(spouse_age)}"
            if not self.aging_and_death_active()
            else f"Spouse age: {spouse_age}"
        )
        lines = [
            "Marriage",
            "",
            f"Spouse: {spouse_name}",
            age_line,
            f"Wedding date: {self.marriage_date_label()}",
            f"Days married: {self.marriage_days_elapsed()}",
            "Anniversary: today" if self.marriage_anniversary_today() else f"Anniversary: {self.marriage_date_label()}",
            "Household: spouse lives at the farmhouse" if self.state.spouse_moved_to_farm else "Household: spouse has not moved in",
            f"Household help: {'enabled' if self.state.family_help_enabled else 'disabled'}",
        ]
        if spouse:
            _key, scene = self.available_marriage_scene(spouse)
            lines.append(f"Next marriage scene: {scene if scene else 'none ready'}")
        previous_marriages = max(
            0,
            len(getattr(self.state, "marriage_history", []) or []) - 1,
        )
        if previous_marriages:
            lines.append(f"Earlier marriages remembered: {previous_marriages}")
        return lines

    def can_invite_spouse_to_farm(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.state.spouse_npc_id or self.state.spouse_npc_id != npc_id:
            return False, "Only your spouse can move onto the farm."
        if self.state.spouse_moved_to_farm:
            return False, f"{npc.get('name', 'Your spouse')} already lives at the farmhouse."
        return True, "Invite them to move into the farmhouse."

    def invite_spouse_to_farm(self, npc: Dict[str, object]) -> bool:
        ok, reason = self.can_invite_spouse_to_farm(npc)
        if not ok:
            self.set_message(reason)
            return False
        self.state.spouse_moved_to_farm = True
        npc["indoors"] = True
        npc["indoor_location"] = "Farmhouse"
        npc["activity"] = "settling into farmhouse life"
        rows = [
            f"{npc.get('name')} Moves In",
            "",
            f"{npc.get('name')} agrees to move into the farmhouse with you.",
            "They will now appear at home, and you can keep talking, gifting, and spending courtship time together there.",
        ]
        self.record_family_event("Move-In", f"{npc.get('name')} moved into the farmhouse.", flag=f"move_in:{npc_id}")
        self.vertical_panel_view("Farmhouse Move-In", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"{npc.get('name')} moved into the farmhouse.")
        return True

    def pregnancy_due_date_label(self) -> str:
        if not self.state.pregnancy_active:
            return "No due date"
        return format_date(self.state.pregnancy_due_month, self.state.pregnancy_due_day, self.state.pregnancy_due_year)

    def pregnancy_start_date_label(self) -> str:
        if not self.state.pregnancy_active:
            return "No pregnancy"
        return format_date(self.state.pregnancy_start_month, self.state.pregnancy_start_day, self.state.pregnancy_start_year)

    def pregnancy_month_number(self) -> int:
        if not self.state.pregnancy_active:
            return 0
        elapsed = months_between_dates(
            self.state.pregnancy_start_month,
            self.state.pregnancy_start_day,
            self.state.pregnancy_start_year,
            self.state.month,
            self.state.day,
            self.state.year,
        )
        return max(1, min(9, elapsed + 1))

    def pregnancy_gestational_parent_name(self) -> str:
        if self.state.pregnancy_gestational_parent == "player":
            return self.state.player_name
        if self.state.pregnancy_parent_npc_id:
            return self.town_npc_name(self.state.pregnancy_parent_npc_id)
        return "the household"

    def family_planning_discussed_with_spouse(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        return self.has_family_event_flag(f"family_planning_discussed:{npc_id}")

    def family_planning_discussion_lines(self, npc: Dict[str, object]) -> List[str]:
        pregnant_parent = self.state.player_name if self.player_sex == "Female" else str(npc.get("name", "your spouse"))
        return [
            "Family Planning",
            "",
            f"You and {npc.get('name', 'your spouse')} talk about whether you want kids or not.",
            "You discuss space, money, field work, sleep, and whether the house is ready to become louder.",
            "",
            f"If you try for a baby, {pregnant_parent} would carry the pregnancy.",
            "Pregnancy lasts 9 in-game months and the due date is marked on the calendar.",
            "",
            "This conversation unlocks the Try for Baby option when the romance requirements are met.",
        ]

    def discuss_family_planning(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        if self.state.spouse_npc_id != npc_id:
            self.set_message("Family planning is only available with your spouse.")
            return False
        self.state.family_planning_last_discussion_day = self.town_npc_day_key()
        self.mark_family_event_flag(f"family_planning_discussed:{npc_id}")
        self.record_family_event("Family Planning", f"Talked with {npc.get('name', 'your spouse')} about children.")
        self.adjust_town_npc_relationship(npc_id, 2)
        self.vertical_panel_view("Family Planning", self.family_planning_discussion_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Talked with {npc.get('name', 'your spouse')} about family planning.")
        return True

    def family_planning_menu(self, npc: Dict[str, object]):
        while True:
            pregnancy_ok, pregnancy_reason = self.can_start_pregnancy_with_spouse(npc)
            discussed = self.family_planning_discussed_with_spouse(npc)
            items = [
                MenuItem(label="Talk about children", value="talk", enabled=True, hint="required" if not discussed else "discussed"),
                MenuItem(label="Try for baby", value="try", enabled=pregnancy_ok, hint=pregnancy_reason),
                MenuItem(label="Pregnancy status", value="status", enabled=True, hint="active" if self.state.pregnancy_active else "none"),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select("Family Planning", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed family planning.")
                return MENU_BACK
            if choice.value == "talk":
                self.discuss_family_planning(npc)
                continue
            if choice.value == "try":
                if self.start_pregnancy_with_spouse(npc):
                    return "changed"
                continue
            if choice.value == "status":
                self.vertical_panel_view("Family", self.family_status_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue

    def pregnancy_checkup_key(self) -> str:
        if not self.state.pregnancy_active:
            return ""
        return f"{self.state.pregnancy_parent_npc_id}:{self.pregnancy_month_number()}"

    def pregnancy_checkup_available(self) -> bool:
        key = self.pregnancy_checkup_key()
        return bool(key and key not in set(getattr(self.state, "pregnancy_checkup_months_seen", []) or []))

    def pregnancy_checkup_lines(self, npc: Dict[str, object]) -> List[str]:
        month = self.pregnancy_month_number()
        notes = {
            1: "The household is mostly planning: space, food, work pace, and what not to put off.",
            2: "The early routine is becoming real. Gentle meals and reliable sleep matter more.",
            3: "The pregnancy is visible in the calendar now: not urgent, but no longer abstract.",
            4: "The farmhouse starts feeling smaller. Paths, storage, and rest spots matter.",
            5: "Everyone has advice. Some of it is even useful.",
            6: "The household starts preparing a proper nursery corner.",
            7: "Travel and heavy chores need more planning. The due date feels close now.",
            8: "The house moves carefully. The calendar is checked more than once.",
            9: "The baby is due soon. Sleep will trigger the birth once the due date arrives.",
        }
        clinic = "Clinic support is available." if self.is_town_building_unlocked("clinic") else "The Clinic is not restored yet, so the household keeps the check-in simple."
        return [
            "Pregnancy Check-In",
            "",
            f"Month: {month} of 9",
            f"Due date: {self.pregnancy_due_date_label()}",
            f"Pregnant: {self.pregnancy_gestational_parent_name()}",
            "",
            notes.get(month, "The household keeps checking in and adjusting."),
            clinic,
            "",
            f"{npc.get('name', 'Your spouse')} stays close to the practical details: meals, rest, and enough room to move.",
        ]

    def complete_pregnancy_checkup(self, npc: Dict[str, object]) -> bool:
        if not self.state.pregnancy_active:
            self.set_message("No pregnancy is active.")
            return False
        key = self.pregnancy_checkup_key()
        if not key:
            self.set_message("Pregnancy record is incomplete.")
            return False
        if not isinstance(self.state.pregnancy_checkup_months_seen, list):
            self.state.pregnancy_checkup_months_seen = []
        if key not in self.state.pregnancy_checkup_months_seen:
            self.state.pregnancy_checkup_months_seen.append(key)
            self.record_family_event("Pregnancy Check-In", f"Month {self.pregnancy_month_number()} check-in with {npc.get('name', 'your spouse')}.")
            self.adjust_town_npc_relationship(str(npc.get("id", "")), 1)
        self.vertical_panel_view("Pregnancy Check-In", self.pregnancy_checkup_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Completed pregnancy month {self.pregnancy_month_number()} check-in.")
        return True

    def family_planning_progress(self, npc: Dict[str, object]) -> Tuple[int, int, int]:
        npc_id = str(npc.get("id", ""))
        friendship = self.town_npc_relationship(npc_id)
        talks = self.town_npc_dialogue_count(npc_id)
        courtships = self.town_npc_courtship_count(npc_id)
        return friendship, talks, courtships

    def family_planning_progress_lines(self, npc: Dict[str, object]) -> List[str]:
        friendship, talks, courtships = self.family_planning_progress(npc)
        return [
            "Family planning readiness:",
            f"- Friendship: {friendship}/{FAMILY_PLANNING_REQUIRED_FRIENDSHIP}",
            f"- Talks: {talks}/{FAMILY_PLANNING_REQUIRED_TALKS}",
            f"- Courtship time: {courtships}/{FAMILY_PLANNING_REQUIRED_COURTSHIP}",
        ]

    def can_start_pregnancy_with_spouse(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        if not self.state.spouse_npc_id or self.state.spouse_npc_id != npc_id:
            return False, "Family planning is only available with your spouse."
        if not self.state.spouse_moved_to_farm:
            return False, "Invite your spouse to move in with you first."
        if self.state.pregnancy_active:
            return False, f"A pregnancy is already underway. Due: {self.pregnancy_due_date_label()}."
        friendship, talks, courtships = self.family_planning_progress(npc)
        if friendship < FAMILY_PLANNING_REQUIRED_FRIENDSHIP:
            return False, f"Needs deeper romance: friendship {friendship}/{FAMILY_PLANNING_REQUIRED_FRIENDSHIP}."
        if talks < FAMILY_PLANNING_REQUIRED_TALKS:
            return False, f"Needs more shared history: talks {talks}/{FAMILY_PLANNING_REQUIRED_TALKS}."
        if courtships < FAMILY_PLANNING_REQUIRED_COURTSHIP:
            return False, f"Needs more spouse time: courtship {courtships}/{FAMILY_PLANNING_REQUIRED_COURTSHIP}."
        if not self.family_planning_discussed_with_spouse(npc):
            return False, "Talk about children together first."
        if self.player_sex == "Female" and self.npc_sex(npc) == "Male":
            return True, "Plan for the player to carry a child."
        if self.player_sex == "Male" and self.npc_sex(npc) == "Female":
            return True, f"Plan for {npc.get('name', 'your spouse')} to carry a child."
        return False, "Pregnancy requires a male and female spouse pair."

    @property
    def player_sex(self) -> str:
        return str(getattr(self.state, "player_sex", "Female"))

    def start_pregnancy_with_spouse(self, npc: Dict[str, object]) -> bool:
        ok, reason = self.can_start_pregnancy_with_spouse(npc)
        if not ok:
            self.set_message(reason)
            return False

        due_month, due_day, due_year = add_months_to_date(self.state.month, self.state.day, self.state.year, 9)
        self.state.pregnancy_active = True
        self.state.pregnancy_parent_npc_id = str(npc.get("id", ""))
        self.state.pregnancy_gestational_parent = "player" if self.player_sex == "Female" else "spouse"
        self.state.pregnancy_start_month = self.state.month
        self.state.pregnancy_start_day = self.state.day
        self.state.pregnancy_start_year = self.state.year
        self.state.pregnancy_due_month = due_month
        self.state.pregnancy_due_day = due_day
        self.state.pregnancy_due_year = due_year

        rows = [
            "Family Planning",
            "",
            f"You and {npc.get('name', 'your spouse')} talk honestly about building a family.",
            "The household begins preparing for a baby.",
            "",
            "Pregnancy:",
            f"Start date: {self.pregnancy_start_date_label()}",
            f"Due date: {self.pregnancy_due_date_label()}",
            "Length: 9 in-game months",
            f"Pregnant: {self.pregnancy_gestational_parent_name()}",
        ]
        rows.extend([""] + self.family_planning_progress_lines(npc))
        self.record_family_event("Pregnancy", f"Pregnancy started with {npc.get('name', 'your spouse')}; due {self.pregnancy_due_date_label()}.", flag=f"pregnancy_started:{self.state.year}:{self.state.month}:{self.state.day}")
        self.vertical_panel_view("Family Planning", rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.autosave_with_message(f"Your household is expecting a baby. Due: {self.pregnancy_due_date_label()}.")
        return True

    def child_name_pool(self, sex: str) -> List[str]:
        if sex == "Male":
            return ["Milo", "Owen", "Noel", "Toby", "Leo", "Reed", "Cal", "Emmett"]
        return ["Lina", "Clara", "June", "Ada", "Nell", "Rose", "Mara", "Elin"]

    def next_child_name(self, sex: str) -> str:
        pool = self.child_name_pool(sex)
        used = {str(child.get("name", "")) for child in self.state.children}
        for offset in range(len(pool)):
            name = pool[(int(self.state.next_child_id) - 1 + offset) % len(pool)]
            if name not in used:
                return name
        return f"Child {self.state.next_child_id}"

    def child_trait_catalog(self) -> List[Dict[str, str]]:
        return [
            {"trait": "Curious", "favorite": "Wildflower", "path": "Scholar", "note": "asks careful questions about ordinary things."},
            {"trait": "Outdoorsy", "favorite": "Berries", "path": "Forager", "note": "wants the door open and pockets full of leaves."},
            {"trait": "Studious", "favorite": "Cave Herbs", "path": "Archivist", "note": "likes labels, lists, and being read to twice."},
            {"trait": "Practical", "favorite": "Wood", "path": "Builder", "note": "turns every corner into a small project."},
            {"trait": "Gentle", "favorite": "Honey", "path": "Caretaker", "note": "notices moods before anyone names them."},
            {"trait": "Bold", "favorite": "Stone", "path": "Explorer", "note": "steps forward first and asks questions second."},
            {"trait": "Musical", "favorite": "Jam Toast", "path": "Artist", "note": "finds rhythm in spoons, rain, and footsteps."},
            {"trait": "Tinkering", "favorite": "Crystal Shard", "path": "Mechanic", "note": "wants to know what every hinge is hiding."},
        ]

    def child_starting_class_catalog(self) -> Dict[str, str]:
        try:
            defs = tactical_class_defs()
        except Exception:
            defs = {}
        catalog: Dict[str, str] = {}
        for class_name in ["Vanguard", "Ranger", "Guardian", "Mystic", "Duelist", "Alchemist"]:
            data = defs.get(class_name, {}) if isinstance(defs, dict) else {}
            catalog[class_name] = str(data.get("desc", "") or "A balanced combat training path.")
        if not catalog:
            catalog = {
                "Vanguard": "Frontline command and reliable pressure.",
                "Ranger": "Ranged control, traps, and precision.",
                "Guardian": "Protection, healing, and steady defense.",
                "Mystic": "Elemental casting and status control.",
                "Duelist": "Mobile single-target pressure.",
                "Alchemist": "Utility, flasks, poison, and support.",
            }
        return catalog

    def child_starting_class_for_path(self, path: str) -> str:
        return {
            "Scholar": "Mystic",
            "Forager": "Ranger",
            "Archivist": "Mystic",
            "Builder": "Guardian",
            "Caretaker": "Guardian",
            "Explorer": "Ranger",
            "Artist": "Duelist",
            "Mechanic": "Alchemist",
            "Farmer": "Vanguard",
            "Cook": "Alchemist",
            "Helper": "Vanguard",
        }.get(str(path or ""), "Vanguard")

    def choose_child_birth_options(self, default_name: str, sex: str, profile_fields: Dict[str, str]) -> Tuple[str, str]:
        child_name = text_entry_menu(
            "New Baby",
            f"Name your {str(sex).lower()} child.",
            default_name,
            16,
        )
        if child_name is None or not str(child_name).strip():
            child_name = default_name

        class_catalog = self.child_starting_class_catalog()
        default_class = str(profile_fields.get("starting_class") or self.child_starting_class_for_path(profile_fields.get("apprentice_path", "")))
        items = [
            MenuItem(
                label=class_name,
                value=class_name,
                enabled=True,
                hint=("suggested" if class_name == default_class else str(desc)[:64]),
            )
            for class_name, desc in class_catalog.items()
        ]
        choice = self.vertical_panel_select("Starting Class", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=False)
        starting_class = str(choice.value) if choice and str(choice.value) in class_catalog else default_class
        return str(child_name), starting_class

    def spouse_trait_bias_for_child(self, parent_npc_id: str) -> Optional[str]:
        data = ROMANCE_NPC_DATA.get(str(parent_npc_id), {})
        style = str(data.get("style", "") if isinstance(data, dict) else "")
        return {
            "curious": "Curious",
            "inventive": "Tinkering",
            "thoughtful": "Studious",
            "adventurous": "Bold",
            "gentle": "Gentle",
            "tender": "Gentle",
            "steady": "Practical",
            "patient": "Outdoorsy",
            "expressive": "Musical",
            "passionate": "Musical",
        }.get(style)

    def child_profile_fields(self, child_id: int, sex: str, parent_npc_id: str, seed: int) -> Dict[str, str]:
        catalog = self.child_trait_catalog()
        rng = random.Random(int(seed) + int(child_id) * 131)
        biased_trait = self.spouse_trait_bias_for_child(parent_npc_id)
        if biased_trait and rng.random() < 0.45:
            entry = next((row for row in catalog if row["trait"] == biased_trait), catalog[0])
        else:
            entry = catalog[rng.randrange(len(catalog))]
        return {
            "personality_trait": entry["trait"],
            "favorite_gift": entry["favorite"],
            "apprentice_path": entry["path"],
            "starting_class": self.child_starting_class_for_path(entry["path"]),
        }

    def ensure_child_profile_fields(self, child: Dict[str, object]) -> Dict[str, object]:
        seed = int(child.get("personality_seed", int(child.get("id", 1)) * 97) or 97)
        fields = self.child_profile_fields(
            int(child.get("id", 1)),
            str(child.get("sex", "Female")),
            str(child.get("parent_npc_id", self.state.spouse_npc_id)),
            seed,
        )
        changed = False
        for key, value in fields.items():
            if not str(child.get(key, "") or ""):
                child[key] = value
                changed = True
        return child

    def child_trait_note(self, child: Dict[str, object]) -> str:
        child = self.ensure_child_profile_fields(child)
        trait = str(child.get("personality_trait", "Curious"))
        entry = next((row for row in self.child_trait_catalog() if row["trait"] == trait), None)
        note = entry["note"] if entry else "is still becoming themselves."
        return f"{child.get('name', 'Your child')} is {trait.lower()} and {note}"

    def child_key(self, child: Dict[str, object]) -> str:
        return str(child.get("id", child.get("name", "child"))).strip() or "child"

    def child_affection_score(self, child: Dict[str, object]) -> int:
        if not isinstance(self.state.child_affection, dict):
            self.state.child_affection = {}
        try:
            return max(0, int(self.state.child_affection.get(self.child_key(child), 0)))
        except Exception:
            return 0

    def child_affection_rank(self, child: Dict[str, object]) -> str:
        score = self.child_affection_score(child)
        if score >= 180:
            return "Devoted"
        if score >= 100:
            return "Attached"
        if score >= 45:
            return "Comfortable"
        if score >= 12:
            return "Warming Up"
        return "New Bond"

    def adjust_child_affection(self, child: Dict[str, object], amount: int) -> int:
        if not isinstance(self.state.child_affection, dict):
            self.state.child_affection = {}
        key = self.child_key(child)
        before = self.child_affection_score(child)
        after = max(0, min(999, before + int(amount)))
        self.state.child_affection[key] = after
        return after - before

    def child_gift_value(self, child: Dict[str, object], item_name: str) -> Tuple[int, str]:
        child = self.ensure_child_profile_fields(child)
        item_name = str(item_name)
        favorite = str(child.get("favorite_gift", "Wildflower"))
        if item_name == favorite:
            return 14, "favorite"
        if is_food_item(item_name):
            return 7, "snack"
        if item_name in ["Wildflower", "Wildflowers", "Berries", "Soft Fiber", "Wood", "Stone", "Cave Herbs", "Crystal Shard", "Honey"]:
            return 5, "liked"
        return 3, "accepted"

    def give_child_gift(self, child: Dict[str, object], item_name: str) -> bool:
        child = self.ensure_child_profile_fields(child)
        key = self.child_key(child)
        today = self.town_npc_day_key()
        if not isinstance(self.state.child_last_gift_day, dict):
            self.state.child_last_gift_day = {}
        if self.state.child_last_gift_day.get(key) == today:
            self.set_message(f"You already gave {child.get('name', 'your child')} a gift today.")
            return False
        item_name = str(item_name)
        if self.state.inventory.get(item_name, 0) <= 0:
            self.set_message(f"You are not carrying {item_name}.")
            return False

        gain, reaction = self.child_gift_value(child, item_name)
        birthday_bonus = 6 if self.is_child_birthday(child) else 0
        gain += birthday_bonus
        self.state.inventory[item_name] -= 1
        if self.state.inventory[item_name] <= 0:
            self.state.inventory.pop(item_name, None)
        actual = self.adjust_child_affection(child, gain)
        self.adjust_family_bond(max(1, actual // 3))
        self.state.child_last_gift_day[key] = today
        if reaction == "favorite":
            detail = f"{child.get('name', 'Your child')} loved receiving {item_name}."
        elif reaction == "snack":
            detail = f"{child.get('name', 'Your child')} happily shared {item_name} as a snack."
        else:
            detail = f"{child.get('name', 'Your child')} accepted {item_name}."
        if birthday_bonus:
            detail += " The birthday timing made it special."
        self.record_family_event("Child Gift", detail)
        self.autosave_with_message(f"Gave {item_name} to {child.get('name', 'your child')}. Affection +{actual}.")
        return True

    def child_gift_menu(self, child: Dict[str, object]):
        child = self.ensure_child_profile_fields(child)
        items: List[MenuItem] = []
        for item_name, qty in sorted(self.state.inventory.items()):
            if int(qty) <= 0:
                continue
            gain, reaction = self.child_gift_value(child, str(item_name))
            items.append(MenuItem(label=str(item_name), value=str(item_name), enabled=True, hint=f"x{qty}; {reaction}; +{gain}"))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        if len(items) == 1:
            self.set_message("You are not carrying anything to give.")
            return False
        choice = self.vertical_panel_select(f"Gift to {child.get('name', 'Child')}", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Child gift cancelled.")
            return False
        return self.give_child_gift(child, str(choice.value))

    def child_lesson_topic_data(self) -> Dict[str, Dict[str, str]]:
        return {
            "Farming": {"path": "Farmer", "note": "soil, seasons, watering, and watching plants closely"},
            "Foraging": {"path": "Forager", "note": "safe wild foods, weather signs, and careful walking"},
            "Crafting": {"path": "Builder", "note": "tools, repairs, storage, and useful little builds"},
            "Cooking": {"path": "Cook", "note": "pantry sense, simple meals, and sharing food"},
            "Mining": {"path": "Explorer", "note": "stone, ore, safety, and when to turn back"},
            "Reading": {"path": "Scholar", "note": "letters, ledgers, maps, and patient attention"},
            "Music": {"path": "Artist", "note": "rhythm, memory, and making the house feel alive"},
            "Care": {"path": "Caretaker", "note": "noticing needs, kindness, and steady routines"},
        }

    def child_lesson_topics(self, child: Dict[str, object]) -> Dict[str, Dict[str, str]]:
        stage = self.household_child_stage(child)
        all_topics = self.child_lesson_topic_data()
        if stage in ["Newborn", "Infant"]:
            return {}
        if stage == "Toddler":
            return {key: all_topics[key] for key in ["Care", "Music", "Reading"]}
        if stage == "Young Child":
            return {key: all_topics[key] for key in ["Farming", "Foraging", "Reading", "Music", "Care"]}
        return all_topics

    def child_learning_map(self, child: Dict[str, object]) -> Dict[str, int]:
        if not isinstance(self.state.child_learning_points, dict):
            self.state.child_learning_points = {}
        key = self.child_key(child)
        raw = self.state.child_learning_points.get(key)
        if not isinstance(raw, dict):
            raw = {}
            self.state.child_learning_points[key] = raw
        clean: Dict[str, int] = {}
        for topic, points in raw.items():
            try:
                clean[str(topic)] = max(0, int(points))
            except Exception:
                continue
        self.state.child_learning_points[key] = clean
        return clean

    def child_top_learning_topic(self, child: Dict[str, object]) -> Tuple[str, int]:
        learning = self.child_learning_map(child)
        if not learning:
            return "", 0
        topic, points = max(learning.items(), key=lambda row: (row[1], row[0]))
        return topic, int(points)

    def update_child_apprentice_path_from_learning(self, child: Dict[str, object]):
        topic, points = self.child_top_learning_topic(child)
        if not topic or points < 3:
            return
        topic_data = self.child_lesson_topic_data().get(topic, {})
        if topic_data.get("path"):
            child["apprentice_path"] = topic_data["path"]

    def teach_child_lesson(self, child: Dict[str, object], topic: str) -> bool:
        child = self.ensure_child_profile_fields(child)
        topics = self.child_lesson_topics(child)
        topic = str(topic)
        if topic not in topics:
            self.set_message(f"{child.get('name', 'Your child')} is not ready for that lesson yet.")
            return False
        key = self.child_key(child)
        today = self.town_npc_day_key()
        if not isinstance(self.state.child_last_lesson_day, dict):
            self.state.child_last_lesson_day = {}
        if self.state.child_last_lesson_day.get(key) == today:
            self.set_message(f"You already spent lesson time with {child.get('name', 'your child')} today.")
            return False
        learning = self.child_learning_map(child)
        learning[topic] = int(learning.get(topic, 0)) + 1
        self.state.child_last_lesson_day[key] = today
        self.adjust_child_affection(child, 5)
        self.adjust_family_bond(2)
        self.update_child_apprentice_path_from_learning(child)
        self.record_family_event("Child Lesson", f"Taught {child.get('name', 'your child')} about {topic.lower()}.")
        self.autosave_with_message(f"Taught {child.get('name', 'your child')} a {topic.lower()} lesson.")
        return True

    def child_learning_lines(self, child: Dict[str, object]) -> List[str]:
        child = self.ensure_child_profile_fields(child)
        topic, points = self.child_top_learning_topic(child)
        lines = [
            f"{child.get('name', 'Child')} Learning",
            "",
            f"Stage: {self.household_child_stage(child)}",
            f"Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
            f"Current path: {child.get('apprentice_path', 'Helper')}",
            f"Starting class: {child.get('starting_class', 'Vanguard')}",
            f"Strongest interest: {topic if topic else 'none yet'}{f' ({points})' if topic else ''}",
            "",
            "Lesson record:",
        ]
        learning = self.child_learning_map(child)
        if learning:
            for lesson_topic, lesson_points in sorted(learning.items(), key=lambda row: (-row[1], row[0])):
                lines.append(f"- {lesson_topic}: {lesson_points}")
        else:
            lines.append("- No lessons recorded yet.")
        lines.extend(["", "Available lessons:"])
        topics = self.child_lesson_topics(child)
        if topics:
            for lesson_topic, data in topics.items():
                lines.append(f"- {lesson_topic}: {data['note']}")
        else:
            lines.append("- Too young for lessons; care and routine matter most.")
        return lines

    def child_lesson_menu(self, child: Dict[str, object]):
        topics = self.child_lesson_topics(child)
        items = [
            MenuItem(label=topic, value=topic, enabled=True, hint=data["path"])
            for topic, data in topics.items()
        ]
        items.append(MenuItem(label="Learning record", value="record", enabled=True, hint=self.household_child_stage(child)))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(f"Lesson with {child.get('name', 'Child')}", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Lesson cancelled.")
            return False
        if choice.value == "record":
            self.vertical_panel_view(f"{child.get('name', 'Child')} Learning", self.child_learning_lines(child), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return False
        return self.teach_child_lesson(child, str(choice.value))

    def child_chore_options(self, child: Dict[str, object]) -> Dict[str, str]:
        stage = self.household_child_stage(child)
        if stage in ["Newborn", "Infant", "Toddler"]:
            return {"Rest and play": "Too young for chores; this keeps the expectation gentle."}
        options = {
            "Set table": "Small household routine.",
            "Sort pantry": "Light organizing and simple food prep.",
            "Rest and play": "No contribution; preserves affection and keeps pressure low.",
        }
        if stage in ["Child", "Teen", "Young Adult"]:
            options.update({
                "Gather forage": "Small berries or flowers from safe nearby paths.",
                "Collect kindling": "A little wood for household supplies.",
                "Study": "Learning-focused help with notes and labels.",
            })
        if stage in ["Teen", "Young Adult"]:
            options.update({
                "Farm rounds": "Light farm prep and seed sorting.",
                "Tinker": "Careful work with odd parts and small repairs.",
            })
        return options

    def assign_child_chore(self, child: Dict[str, object], chore: str) -> bool:
        child = self.ensure_child_profile_fields(child)
        chore = str(chore)
        options = self.child_chore_options(child)
        if chore not in options:
            self.set_message(f"{child.get('name', 'Your child')} is not ready for that chore.")
            return False
        if not isinstance(self.state.child_chore_assignments, dict):
            self.state.child_chore_assignments = {}
        key = self.child_key(child)
        self.state.child_chore_assignments[key] = chore
        if chore == "Rest and play":
            self.adjust_child_affection(child, 2)
        else:
            self.adjust_family_bond(1)
        self.record_family_event("Child Chore", f"{child.get('name', 'Your child')} was assigned: {chore}.")
        self.autosave_with_message(f"{child.get('name', 'Your child')} will focus on {chore.lower()}.")
        return True

    def child_chore_assignment(self, child: Dict[str, object]) -> str:
        if not isinstance(self.state.child_chore_assignments, dict):
            self.state.child_chore_assignments = {}
        return str(self.state.child_chore_assignments.get(self.child_key(child), "Rest and play") or "Rest and play")

    def child_chore_lines(self, child: Dict[str, object]) -> List[str]:
        child = self.ensure_child_profile_fields(child)
        lines = [
            f"{child.get('name', 'Child')} Chores",
            "",
            f"Stage: {self.household_child_stage(child)}",
            f"Current focus: {self.child_chore_assignment(child)}",
            "",
            "Available choices:",
        ]
        for chore, note in self.child_chore_options(child).items():
            marker = "*" if chore == self.child_chore_assignment(child) else "-"
            lines.append(f"{marker} {chore}: {note}")
        lines.extend(["", "Chores only create small overnight help. Automation still handles serious farm labor."])
        return lines

    def child_chore_menu(self, child: Dict[str, object]):
        items = [
            MenuItem(label=chore, value=chore, enabled=True, hint=note)
            for chore, note in self.child_chore_options(child).items()
        ]
        items.append(MenuItem(label="Chore notes", value="notes", enabled=True, hint=self.child_chore_assignment(child)))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select(f"Chores for {child.get('name', 'Child')}", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Chore assignment cancelled.")
            return False
        if choice.value == "notes":
            self.vertical_panel_view(f"{child.get('name', 'Child')} Chores", self.child_chore_lines(child), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
            return False
        return self.assign_child_chore(child, str(choice.value))

    def child_stage_months(self) -> Dict[str, int]:
        return {
            "Infant": 2,
            "Toddler": 12,
            "Young Child": 36,
            "Child": 72,
            "Teen": 144,
            "Young Adult": 216,
        }

    def household_child_raw_age_months(self, child: Dict[str, object]) -> int:
        return months_between_dates(
            int(child.get("birth_month", self.state.month)),
            int(child.get("birth_day", self.state.day)),
            int(child.get("birth_year", self.state.year)),
            self.state.month,
            self.state.day,
            self.state.year,
        )

    def household_child_age_months(self, child: Dict[str, object]) -> int:
        raw_months = self.household_child_raw_age_months(child)
        if (
            bool(getattr(self.state, "aging_and_death_enabled", True))
            or raw_months < 216
        ):
            return raw_months
        return max(216, int(child.get("aging_frozen_months", 216) or 216))

    def household_child_age_display_line(
        self,
        child: Dict[str, object],
    ) -> str:
        age_months = self.household_child_age_months(child)
        if (
            not bool(getattr(self.state, "aging_and_death_enabled", True))
            and age_months >= 216
        ):
            return f"Life stage: {self.household_child_stage(child)}"
        return f"Age: {age_months} month(s)"

    def household_child_stage(self, child: Dict[str, object]) -> str:
        age_months = self.household_child_age_months(child)
        if age_months < 2:
            return "Newborn"
        if age_months < 12:
            return "Infant"
        if age_months < 36:
            return "Toddler"
        if age_months < 72:
            return "Young Child"
        if age_months < 144:
            return "Child"
        if age_months < 216:
            return "Teen"
        return "Young Adult"

    def household_child_activity_label(self, child: Dict[str, object]) -> str:
        self.ensure_child_profile_fields(child)
        stage = self.household_child_stage(child)
        trait = str(child.get("personality_trait", "Curious")).lower()
        return {
            "Newborn": "sleeping in the farmhouse nursery",
            "Infant": f"watching the household with {trait} attention",
            "Toddler": "toddling between furniture and safe edges",
            "Young Child": "playing near the farmhouse table",
            "Child": f"learning household routines with a {trait} streak",
            "Teen": f"testing a {trait} sense of independence",
            "Young Adult": f"helping around the farmhouse as a {trait} young adult",
        }.get(stage, "growing up at home")

    def pregnancy_status_lines(self) -> List[str]:
        if not self.state.pregnancy_active:
            return ["Pregnancy: none active."]
        checkups = len(getattr(self.state, "pregnancy_checkup_months_seen", []) or [])
        return [
            "Pregnancy",
            "",
            f"Month: {self.pregnancy_month_number()} of 9",
            f"Start date: {self.pregnancy_start_date_label()}",
            f"Due date: {self.pregnancy_due_date_label()}",
            f"Pregnant: {self.pregnancy_gestational_parent_name()}",
            f"Monthly check-ins: {checkups}/9",
            "Current check-in: ready" if self.pregnancy_checkup_available() else "Current check-in: completed or not ready",
            "",
            "Birth happens after sleeping once the due date arrives.",
        ]

    def household_child_status_lines(self, child: Dict[str, object]) -> List[str]:
        child = self.ensure_child_profile_fields(child)
        age_months = self.household_child_age_months(child)
        stage = self.household_child_stage(child)
        birth = format_date(int(child.get("birth_month", 1)), int(child.get("birth_day", 1)), int(child.get("birth_year", 1)))
        next_lines = []
        for next_stage, month_mark in self.child_stage_months().items():
            if age_months < month_mark:
                next_lines.append(f"Next stage: {next_stage} at {month_mark} month(s)")
                next_lines.append(f"Time until next stage: {month_mark - age_months} month(s)")
                break
        if not next_lines:
            next_lines.append("Next stage: fully grown for the current system")
        top_topic, top_points = self.child_top_learning_topic(child)
        chore = self.child_chore_assignment(child)
        return [
            f"{child.get('name', 'Child')} - {stage}",
            "",
            f"Sex: {child.get('sex', 'Unknown')}",
            self.household_child_age_display_line(child),
            f"Birthday: {self.child_birthday_label(child)}",
            (
                f"Born: {birth}"
                if (
                    bool(
                        getattr(
                            self.state,
                            "aging_and_death_enabled",
                            True,
                        )
                    )
                    or age_months < 216
                )
                else "Birth record: preserved in the family ledger"
            ),
            f"Other parent: {self.town_npc_name(str(child.get('parent_npc_id', self.state.spouse_npc_id)))}",
            f"Trait: {child.get('personality_trait', 'Curious')}",
            f"Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
            f"Favorite gift: {child.get('favorite_gift', 'Wildflower')}",
            f"Possible path: {child.get('apprentice_path', 'Helper')}",
            f"Starting class: {child.get('starting_class', 'Vanguard')}",
            f"Learning: {top_topic if top_topic else 'none yet'}{f' ({top_points})' if top_topic else ''}",
            f"Chore focus: {chore}",
            *next_lines,
            "",
            f"Activity: {self.household_child_activity_label(child)}.",
            self.child_trait_note(child),
        ]

    def family_status_lines(self) -> List[str]:
        self.normalize_town_npcs()
        lines = ["Family", ""]
        lines.append(f"Player: {self.state.player_name}")
        lines.append(self.player_birth_display_line())
        lines.append(self.player_age_display_line())
        lines.append(f"Generation: {self.state.player_generation}")
        lines.append(f"Health outlook: {self.player_health_outlook()}")
        lines.append("")
        lines.extend(self.marriage_status_lines())
        lines.extend(["", *self.family_bond_lines()])
        lines.append("")
        if self.state.spouse_npc_id:
            lines.append(f"Spouse: {self.town_npc_name(self.state.spouse_npc_id)}")
            lines.append("Household: spouse lives at the farmhouse" if self.state.spouse_moved_to_farm else "Household: spouse has not moved in")
            lines.append(f"Support focus: {self.spouse_support_mode()}")
            spouse = self.npc_record_by_id(self.state.spouse_npc_id)
            if spouse:
                lines.extend([""] + self.family_planning_progress_lines(spouse))
        elif str(getattr(self.state, "engaged_npc_id", "") or ""):
            lines.append(
                f"Fiance: {self.town_npc_name(self.state.engaged_npc_id)}"
            )
            lines.append(f"Wedding: {self.wedding_date_label()}")
        else:
            lines.append("Spouse: none")
        lines.append("")
        lines.extend(self.pregnancy_status_lines())
        lines.extend(["", f"Children: {len(self.state.children)}"])
        for child in self.state.children:
            child = self.ensure_child_profile_fields(child)
            top_topic, top_points = self.child_top_learning_topic(child)
            child_age = self.household_child_age_months(child)
            stage = self.household_child_stage(child)
            adult_age_hidden = (
                not bool(
                    getattr(
                        self.state,
                        "aging_and_death_enabled",
                        True,
                    )
                )
                and child_age >= 216
            )
            age_detail = "" if adult_age_hidden else f", {child_age} month(s)"
            lines.append(
                f"- {child.get('name', 'Child')}: {stage}{age_detail}, "
                f"{child.get('personality_trait')} "
                f"(likes {child.get('favorite_gift')}; affection {self.child_affection_rank(child)}; "
                f"class {child.get('starting_class', 'Vanguard')}; "
                f"{top_topic or 'no lesson focus'}{f' {top_points}' if top_topic else ''})"
            )
        if not self.state.children:
            lines.append("- None yet")
        active_elders = [
            elder
            for elder in getattr(self.state, "dynasty_elders", []) or []
            if isinstance(elder, dict) and elder.get("active", True)
        ]
        lines.extend(["", f"Retired family elders: {len(active_elders)}"])
        for elder in active_elders:
            lines.append(
                f"- {elder.get('name')}: Generation {elder.get('generation')}, "
                f"{self.dynasty_person_age_phrase(elder)}, "
                f"{elder.get('activity', 'keeping family history')}"
            )
        active_kin = [
            kin
            for kin in getattr(self.state, "dynasty_kin", []) or []
            if isinstance(kin, dict) and kin.get("active", True)
        ]
        lines.extend(["", f"Extended family: {len(active_kin)}"])
        for kin in active_kin:
            lines.append(
                f"- {self.dynasty_relation_for_generation(kin)} "
                f"{kin.get('name')}: {self.dynasty_person_age_phrase(kin)}, "
                f"{kin.get('occupation', 'family')}; "
                f"{kin.get('residence', 'Farmhouse')}"
            )
        lines.extend(["", *self.home_region_journey_lines()])
        lines.extend(["", "Household help:", f"- {'Enabled' if self.state.family_help_enabled else 'Disabled'}"])
        candidates = self.household_help_candidate_children()
        helper_count = (1 if self.spouse_lives_on_farm() else 0) + len(candidates)
        lines.append(f"- Potential helpers: {helper_count}")
        recent = list(getattr(self.state, "family_event_log", []) or [])[-6:]
        lines.extend(["", "Recent family memories:"])
        lines.extend(f"- {row}" for row in recent) if recent else lines.append("- No family memories recorded yet.")
        return lines

    def pregnancy_due_reached(self) -> bool:
        return bool(
            self.state.pregnancy_active
            and date_reached(
                self.state.month,
                self.state.day,
                self.state.year,
                self.state.pregnancy_due_month,
                self.state.pregnancy_due_day,
                self.state.pregnancy_due_year,
            )
        )

    def child_milestone_key(self, child: Dict[str, object], stage: Optional[str] = None) -> str:
        return f"child:{child.get('id', '?')}:{stage or self.household_child_stage(child)}"

    def record_child_milestones_overnight(self) -> str:
        if not isinstance(self.state.child_milestone_flags, list):
            self.state.child_milestone_flags = []
        notes: List[str] = []
        for child in self.state.children:
            self.ensure_child_profile_fields(child)
            stage = self.household_child_stage(child)
            key = self.child_milestone_key(child, stage)
            if key in self.state.child_milestone_flags:
                continue
            self.state.child_milestone_flags.append(key)
            if stage == "Newborn":
                continue
            name = str(child.get("name", "Your child"))
            self.record_family_event("Child Milestone", f"{name} reached the {stage} stage.", flag=key)
            notes.append(f" {name} is now a {stage}.")
        return "".join(notes)

    def update_family_overnight(self, interactive: bool = False) -> str:
        if not self.pregnancy_due_reached():
            return self.record_child_milestones_overnight()

        rng = random.Random(self.state.year * 10000 + self.state.month * 100 + self.state.day + int(self.state.next_child_id) * 37)
        sex = "Female" if rng.random() < 0.5 else "Male"
        child_name = self.next_child_name(sex)
        parent_id = self.state.pregnancy_parent_npc_id or self.state.spouse_npc_id
        personality_seed = rng.randint(1000, 999999)
        profile_fields = self.child_profile_fields(int(self.state.next_child_id), sex, parent_id, personality_seed)
        if interactive:
            try:
                child_name, starting_class = self.choose_child_birth_options(child_name, sex, profile_fields)
                profile_fields["starting_class"] = starting_class
            except Exception as exc:
                append_debug_log(f"Child birth options fallback: {type(exc).__name__}: {exc}")
        child = {
            "id": int(self.state.next_child_id),
            "name": child_name,
            "sex": sex,
            "birth_month": self.state.month,
            "birth_day": self.state.day,
            "birth_year": self.state.year,
            "parent_npc_id": parent_id,
            "personality_seed": personality_seed,
            **profile_fields,
        }
        self.state.children.append(child)
        self.record_family_event(
            "Birth",
            f"{child_name} was born. Trait: {profile_fields['personality_trait']}. Starting class: {profile_fields.get('starting_class', 'Vanguard')}. Birthday: {format_birthday(self.state.month, self.state.day)}.",
            flag=f"birth:{child.get('id')}",
        )
        self.mark_family_event_flag(self.child_milestone_key(child, "Newborn"))
        self.state.next_child_id = int(self.state.next_child_id) + 1
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
        return f" {child_name} was born and now lives in the farmhouse. Starting class: {profile_fields.get('starting_class', 'Vanguard')}."

    def household_help_candidate_children(self) -> List[Dict[str, object]]:
        helpers: List[Dict[str, object]] = []
        for child in self.state.children:
            stage = self.household_child_stage(child)
            if stage in ["Young Child", "Child", "Teen", "Young Adult"]:
                helpers.append(self.ensure_child_profile_fields(child))
        return helpers

    def child_help_drop(self, child: Dict[str, object]) -> Tuple[str, int, str]:
        chore = self.child_chore_assignment(child)
        chore_table = {
            "Set table": ("Field Snack", 1, "set the table and saved a simple bite"),
            "Sort pantry": ("Field Snack", 1, "sorted pantry shelves and found a spare snack"),
            "Gather forage": ("Berries", 2, "brought in berries from a careful nearby walk"),
            "Collect kindling": ("Wood", 3, "stacked a little kindling by the door"),
            "Study": ("Cave Herbs", 1, "copied useful herb notes into the family ledger"),
            "Farm rounds": ("Mixed Seeds", 2, "checked the yard and sorted seeds for tomorrow"),
            "Tinker": ("Crystal Shard", 1, "found a small useful shard while checking odd corners"),
            "Rest and play": ("", 0, "rested, played, and kept the house feeling lighter"),
        }
        if chore in chore_table:
            return chore_table[chore]
        trait = str(child.get("personality_trait", "Curious"))
        table = {
            "Curious": ("Wildflower", 1, "pressed a wildflower into the family ledger"),
            "Outdoorsy": ("Berries", 2, "brought in berries from a careful morning walk"),
            "Studious": ("Cave Herbs", 1, "sorted useful herbs from the pantry notes"),
            "Practical": ("Wood", 3, "stacked a little kindling by the door"),
            "Gentle": ("Honey", 1, "saved a small jar of honey for the household"),
            "Bold": ("Stone", 3, "cleared stones from a safe corner of the yard"),
            "Musical": ("Jam Toast", 1, "made a simple breakfast before anyone asked"),
            "Tinkering": ("Crystal Shard", 1, "found a small shard while checking odd corners"),
        }
        return table.get(trait, ("Wildflower", 1, "helped with a small household task"))

    def apply_family_household_help_overnight(self) -> str:
        if not bool(getattr(self.state, "family_help_enabled", True)):
            return ""
        today = self.town_npc_day_key()
        if self.state.family_last_help_day == today:
            return ""
        helpers: List[str] = []
        drops: Dict[str, int] = {}
        if self.spouse_lives_on_farm():
            spouse_name = self.town_npc_name(self.state.spouse_npc_id)
            item, qty, note = self.spouse_help_drop()
            if item and qty > 0:
                drops[item] = drops.get(item, 0) + int(qty)
            helpers.append(f"{spouse_name} {note}")
        for child in self.household_help_candidate_children()[:2]:
            item, qty, note = self.child_help_drop(child)
            if item and qty > 0:
                drops[item] = drops.get(item, 0) + int(qty)
            helpers.append(f"{child.get('name', 'Your child')} {note}")
        if not drops and not helpers:
            return ""
        if drops:
            add_inventory_items(self.state.inventory, drops)
        if self.spouse_support_mode() == "Rest" and self.spouse_lives_on_farm():
            self.adjust_family_bond(2)
        self.state.family_last_help_day = today
        detail = "; ".join(helpers[:3])
        self.record_family_event("Household Help", detail)
        if drops:
            return f" Household help: {format_drops(drops)}."
        return " Household help: the farmhouse felt calmer overnight."

    def toggle_family_help(self) -> bool:
        self.state.family_help_enabled = not bool(getattr(self.state, "family_help_enabled", True))
        self.autosave_with_message(f"Household help {'enabled' if self.state.family_help_enabled else 'disabled'}.")
        return self.state.family_help_enabled

    def family_help_lines(self) -> List[str]:
        lines = [
            "HOUSEHOLD HELP",
            "",
            f"Status: {'enabled' if self.state.family_help_enabled else 'disabled'}",
            "",
            "When enabled, family members may add a small overnight contribution.",
            "This is intentionally light support, not a replacement for farm automation.",
            "",
            "Possible helpers:",
        ]
        if self.spouse_lives_on_farm():
            item, qty, note = self.spouse_help_drop()
            reward = f" ({qty} {item})" if item and qty > 0 else ""
            lines.append(f"- {self.town_npc_name(self.state.spouse_npc_id)}: {note}{reward}")
        for child in self.household_help_candidate_children():
            item, qty, note = self.child_help_drop(child)
            reward = f" ({qty} {item})" if item and qty > 0 else ""
            lines.append(f"- {child.get('name', 'Child')}: {note}{reward}")
        if len(lines) <= 8:
            lines.append("- No older child helpers yet.")
        return lines

    def town_npc_day_key(self) -> str:
        return f"{self.state.year}-{self.state.month}-{self.state.day}"

    def absolute_game_day(self, month: Optional[int] = None, day: Optional[int] = None, year: Optional[int] = None) -> int:
        month = self.state.month if month is None else int(month)
        day = self.state.day if day is None else int(day)
        year = self.state.year if year is None else int(year)
        total = 0
        for y in range(1, max(1, year)):
            total += 366 if is_leap_year(y) else 365
        return total + day_of_year(month, day, year)

    def regional_town_life_state(self) -> Dict[str, object]:
        if not isinstance(getattr(self.state, "regional_town_life", None), dict):
            self.state.regional_town_life = {}
        life = self.state.regional_town_life
        life.setdefault("day_key", "")
        life.setdefault("occasion_id", "")
        life.setdefault("visitors", [])
        life.setdefault("visitor_bonds", {})
        life.setdefault("visitor_last_talk_day", {})
        life.setdefault("visitor_memories", {})
        life.setdefault("visitor_purchase_counts", {})
        life.setdefault("npc_social_links", {})
        life.setdefault("journeys", {})
        life.setdefault("resident_trips", {})
        life.setdefault("event_log", [])
        return life

    def regional_real_destinations(self) -> List[Dict[str, object]]:
        discovered = self.discovered_procedural_town_plans() if hasattr(self, "discovered_procedural_town_plans") else []
        signature = (
            int(getattr(self.state, "wilderness_seed", 0)),
            tuple(sorted((int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))) for plan in discovered)),
            self.wilderness_road_state_signature() if hasattr(self, "wilderness_road_state_signature") else (),
        )
        cache = getattr(self, "_regional_real_destination_cache", None)
        if isinstance(cache, tuple) and cache[0] == signature:
            return [dict(record) for record in cache[1]]
        destinations: Dict[str, Dict[str, object]] = {}
        for plan in discovered:
            cx, cy = int(plan.get("chunk_x", 0)), int(plan.get("chunk_y", 0))
            identity = self.procedural_town_identity(plan) if hasattr(self, "procedural_town_identity") else {}
            profile = self.procedural_town_market_profile(plan) if hasattr(self, "procedural_town_market_profile") else {}
            world_x, world_y = self.wilderness_world_coords(cx, cy, 43, 19)
            destination_id = f"town:{cx},{cy}"
            destinations[destination_id] = {
                "id": destination_id,
                "name": str(plan.get("name", "Wilderness Town")),
                "kind": "port_city" if str((plan.get("geography") or {}).get("water_access", "")) == "waterfront" else "town",
                "chunk_x": cx, "chunk_y": cy, "world_x": world_x, "world_y": world_y,
                "known": True,
                "industry": str(identity.get("industry", plan.get("specialty", "regional trade"))),
                "exports": [str(item) for item in list(identity.get("exports", ()))[:8]],
                "demand": str(profile.get("demand", "")),
                "region": str((plan.get("geography") or {}).get("region_name", self.wilderness_region_profile(cx, cy).get("name", "the region"))),
            }
        if hasattr(self, "wilderness_road_destinations_for_chunk"):
            for node in self.wilderness_road_destinations_for_chunk(0, 0):
                node_id = str(node.get("id", ""))
                # Home Farm and Home Mine are useful physical destinations for
                # road travelers, but they are not settlements that originate
                # the town's rotating regional visitor population.
                if not node_id or node_id in {"main-town", "home-farm", "home-mine"} or node_id in destinations:
                    continue
                cx, cy = int(node.get("chunk_x", 0)), int(node.get("chunk_y", 0))
                kind = str(node.get("kind", "road_service"))
                default_exports = {
                    "port": ["Sunfish", "Marsh Reed"], "port_city": ["Sunfish", "Sea Glass"],
                    "outpost": ["Field Snack", "Fiber"], "road_service": ["Wild Herbs", "Wood"],
                    "reclaimed_stronghold": ["Stone", "Coal"], "founded_town": ["Wood", "Stone"],
                }.get(kind, ["Wood", "Wild Herbs"])
                destinations[node_id] = {
                    **dict(node),
                    "known": bool(self.wilderness_chunk_known(cx, cy)) if hasattr(self, "wilderness_chunk_known") else False,
                    "industry": kind.replace("_", " "),
                    "exports": default_exports,
                    "demand": "Field Snack",
                    "region": str(self.wilderness_region_profile(cx, cy).get("name", "the region")),
                }
        records = sorted(destinations.values(), key=lambda record: (not bool(record.get("known")), str(record.get("name", ""))))
        self._regional_real_destination_cache = (signature, [dict(record) for record in records])
        return [dict(record) for record in records]

    def regional_destination_for_identity(self, identity: str, day_number: Optional[int] = None) -> Dict[str, object]:
        destinations = self.regional_real_destinations()
        if not destinations:
            return {
                "id": "road:origin", "name": "Origin Crossroads", "kind": "road_service",
                "chunk_x": 0, "chunk_y": -1, "world_x": 43, "world_y": -19,
                "known": False, "industry": "road services", "exports": ["Field Snack"],
                "demand": "Wood", "region": "the home region",
            }
        day_number = self.absolute_game_day() if day_number is None else int(day_number)
        known = [record for record in destinations if record.get("known")]
        pool = known or destinations
        seed = sum((index + 1) * ord(ch) for index, ch in enumerate(str(identity))) + day_number * 37
        return dict(pool[seed % len(pool)])

    def regional_route_profile(self, destination: Dict[str, object], identity: str = "") -> Dict[str, object]:
        cx, cy = int(destination.get("chunk_x", 0)), int(destination.get("chunk_y", 0))
        distance = max(1, abs(cx) + abs(cy))
        points, vitality = self.wilderness_region_vitality(cx, cy) if hasattr(self, "wilderness_region_vitality") else (0, "Untended")
        severe = str(getattr(self.state, "weather", "Sunny")) in {"Storm", "Stormy", "Blizzard"}
        hazard_roll = (sum(ord(ch) for ch in f"{identity}:{cx},{cy}:{self.absolute_game_day()}") % 11) == 0
        if severe:
            condition, delay = "Weather Delayed", 1
        elif int(points) >= 50:
            condition, delay = "Well Maintained", 0
        elif int(points) >= 20:
            condition, delay = "Reliable", 0
        elif hazard_roll:
            condition, delay = "Hazardous", 1
        else:
            condition, delay = "Open", 0
        travel_days = max(1, min(5, (distance + 4) // 5 + delay))
        return {
            "distance_chunks": distance,
            "vitality": vitality,
            "route_condition": condition,
            "delay_days": delay,
            "travel_days": travel_days,
            "arrival_hour": min(18, 8 + min(6, distance // 2) + delay * 2),
        }

    def regional_destination_news(self, destination: Dict[str, object]) -> str:
        name = str(destination.get("name", "a regional settlement"))
        industry = str(destination.get("industry", "regional trade"))
        demand = str(destination.get("demand", "supplies") or "supplies")
        exports = list(destination.get("exports", []) or [])
        export_text = ", ".join(str(item) for item in exports[:2]) or "local goods"
        return f"{name} reports active {industry}; it is sending {export_text} and looking for {demand}."

    def regional_return_date_label(self, travel_days: int) -> str:
        month, day, year = int(self.state.month), int(self.state.day), int(self.state.year)
        for _ in range(max(1, int(travel_days))):
            month, day, year = advance_date(month, day, year)
        return format_date(month, day, year)

    def regional_circulation_calendar_events_for_date(self, month: int, day: int, year: int) -> List[str]:
        target_day = self.absolute_game_day(month, day, year)
        events = []
        for npc_id, trip in self.regional_town_life_state().get("resident_trips", {}).items():
            if not isinstance(trip, dict):
                continue
            npc_name = self.town_npc_name(str(npc_id))
            destination = str(trip.get("destination_name", "a regional destination"))
            if target_day == int(trip.get("depart_day_number", -1)):
                events.append(f"Regional departure: {npc_name} leaves for {destination}")
            if target_day == int(trip.get("return_day_number", -1)):
                events.append(f"Expected regional return: {npc_name} from {destination}")
        return events

    def town_public_occasion_for_date(
        self,
        month: Optional[int] = None,
        day: Optional[int] = None,
        year: Optional[int] = None,
    ) -> Dict[str, object]:
        month = int(self.state.month if month is None else month)
        day = int(self.state.day if day is None else day)
        year = int(self.state.year if year is None else year)
        festival_id = self.festival_id_for_date(month, day, year)
        if festival_id:
            festival = dict(self.festival_catalog().get(festival_id, {}))
            return {
                "id": f"festival:{festival_id}",
                "kind": "festival",
                "name": str(festival.get("name", "Town Festival")),
                "summary": str(festival.get("description", "The town gathers for a seasonal festival.")),
                "location": str(festival.get("location", "Central Park")),
                "visitor_count": 5,
            }
        weekday = weekday_for_date(month, day, year)
        if weekday in {"Wednesday", "Saturday"}:
            return {
                "id": f"market:{weekday.lower()}",
                "kind": "market",
                "name": f"{weekday} Regional Market",
                "summary": "Traveling vendors and nearby households gather along Market Promenade.",
                "location": "Market Promenade",
                "visitor_count": 4 if weekday == "Saturday" else 3,
            }
        if weekday == "Friday":
            return {
                "id": "music:friday",
                "kind": "music",
                "name": "Friday Inn Music Night",
                "summary": "Travelers trade road news while local and visiting musicians share the inn floor.",
                "location": "Town Inn",
                "visitor_count": 3,
            }
        if day in {1, 15}:
            return {
                "id": f"supply:{day}",
                "kind": "supply",
                "name": "Regional Supply Exchange",
                "summary": "Couriers and suppliers refresh long-distance orders at Market Row.",
                "location": "Market Row",
                "visitor_count": 2,
            }
        return {}

    def todays_town_public_occasion(self) -> Dict[str, object]:
        return self.town_public_occasion_for_date()

    def public_occasion_calendar_label_for_date(self, month: int, day: int, year: int) -> Optional[str]:
        occasion = self.town_public_occasion_for_date(month, day, year)
        if not occasion:
            return None
        return f"Public occasion: {occasion['name']} at {occasion['location']}. {occasion['summary']}"

    def town_public_event_features(self) -> Dict[Tuple[int, int], Dict[str, object]]:
        occasion = self.todays_town_public_occasion()
        if not occasion:
            return {}
        kind = str(occasion.get("kind", ""))
        features: Dict[Tuple[int, int], Dict[str, object]] = {}
        if kind in {"market", "supply", "festival"}:
            stall_names = ("Produce Stall", "Road Goods Stall", "Maps and Remedies Stall")
            for position, name in zip(((82, 28), (86, 28), (90, 28)), stall_names):
                features[position] = {
                    "symbol": "$", "color": C.SHOP, "name": name,
                    "description": f"{name} is active for {occasion['name']}.", "action": "market",
                }
            for position in ((84, 27), (88, 27), (92, 27), (84, 33), (88, 33), (92, 33)):
                features[position] = {
                    "symbol": "*", "color": C.CROP_READY, "name": "Market Bunting",
                    "description": f"Bunting marks today's {occasion['name']}.", "action": "notice",
                }
        if kind == "festival":
            features[(49, 29)] = {
                "symbol": "*", "color": C.PLACEMENT, "name": "Festival Gathering Point",
                "description": f"The main gathering point for {occasion['name']}.", "action": "festival",
            }
            for position in ((43, 29), (46, 29), (52, 29), (55, 29)):
                features[position] = {
                    "symbol": "t", "color": C.WOOD, "name": "Community Table",
                    "description": "A shared table set for residents, families, and travelers.", "action": "notice",
                }
        if kind == "music":
            features[(25, 22)] = {
                "symbol": "!", "color": C.LAMP, "name": "Music Night Sign",
                "description": "The inn hosts music and road stories tonight.", "action": "notice",
            }
        return features

    def town_public_event_feature_at(self, x: int, y: int) -> Dict[str, object]:
        return self.town_public_event_features().get((int(x), int(y)), {})

    def interact_town_public_event_feature(self, feature: Dict[str, object]):
        action = str(feature.get("action", "notice"))
        if action == "market":
            self.market_row_menu()
            return
        if action == "festival":
            self.festival_menu()
            return
        occasion = self.todays_town_public_occasion()
        lines = [
            str(feature.get("name", "Public Occasion")), "",
            str(feature.get("description", "The town has prepared this space for today's gathering.")), "",
            f"Occasion: {occasion.get('name', 'Town gathering')}",
            f"Location: {occasion.get('location', 'Town')}",
            "Residents and regional visitors follow this occasion through their real schedules.",
        ]
        self.vertical_panel_view(str(feature.get("name", "Public Occasion")), lines, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
        self.set_message(str(feature.get("description", "You inspect the public gathering.")))

    def ensure_regional_town_visitors(self) -> List[Dict[str, object]]:
        life = self.regional_town_life_state()
        day_key = self.town_npc_day_key()
        if str(life.get("day_key", "")) == day_key and isinstance(life.get("visitors"), list):
            return life["visitors"]
        occasion = self.todays_town_public_occasion()
        absolute_day = self.absolute_game_day()
        journeys = life.setdefault("journeys", {})
        for old_visitor in list(life.get("visitors", []) or []):
            visitor_id = str(old_visitor.get("id", ""))
            journey = journeys.get(visitor_id)
            if not visitor_id or not isinstance(journey, dict):
                continue
            travel_days = max(1, min(5, int(old_visitor.get("travel_days", 1) or 1)))
            journey["status"] = "returning"
            journey["return_start_day_number"] = absolute_day
            journey["return_end_day_number"] = absolute_day + travel_days
        count = int(occasion.get("visitor_count", 0) or 0)
        if not count and absolute_day % 3 == 0:
            count = 1
        discovered_links = len(self.discovered_procedural_town_plans()) if hasattr(self, "discovered_procedural_town_plans") else 0
        active_trade_links = sum(
            bool(record.get("active", True))
            for record in (getattr(self.state, "player_trade_routes", {}) or {}).values()
            if isinstance(record, dict)
        )
        if occasion and discovered_links + active_trade_links >= 2:
            count = min(6, count + 1)
        rng = random.Random(absolute_day * 7919 + int(self.state.year) * 131)
        archetypes = list(REGIONAL_TOWN_VISITOR_ARCHETYPES)
        rng.shuffle(archetypes)
        visitors: List[Dict[str, object]] = []
        for template in archetypes:
            if len(visitors) >= count:
                break
            visitor_id = f"regional_visitor:{template['id']}"
            old_journey = journeys.get(visitor_id, {})
            if (
                isinstance(old_journey, dict)
                and str(old_journey.get("status", "")) == "returning"
                and int(old_journey.get("return_end_day_number", 0) or 0) >= absolute_day
            ):
                continue
            index = len(visitors)
            origin = self.regional_destination_for_identity(str(template["id"]), absolute_day + index)
            route = self.regional_route_profile(origin, str(template["id"]))
            arrival_hour = min(14 if occasion else 17, int(route["arrival_hour"]))
            visitor = {
                **template,
                "id": visitor_id,
                "origin": str(origin.get("name", template.get("origin", "the regional roads"))),
                "symbol": "@",
                "regional_visitor": True,
                "x": 56 + (index % 4),
                "y": 1,
                "interior_x": 27,
                "interior_y": 18,
                "runtime_location": "InTransit" if int(self.state.hour) < arrival_hour else "Town",
                "activity": f"traveling from {origin.get('name', 'the regional roads')} toward Elsewhere",
                "facing": "DOWN",
                "route_slot": index,
                "origin_id": str(origin.get("id", "")),
                "origin_kind": str(origin.get("kind", "road_service")),
                "origin_chunk_x": int(origin.get("chunk_x", 0)),
                "origin_chunk_y": int(origin.get("chunk_y", 0)),
                "origin_world_x": int(origin.get("world_x", 0)),
                "origin_world_y": int(origin.get("world_y", 0)),
                "distance_chunks": int(route["distance_chunks"]),
                "route_condition": str(route["route_condition"]),
                "delay_days": int(route["delay_days"]),
                "travel_days": int(route["travel_days"]),
                "arrival_hour": arrival_hour,
                "origin_exports": [str(item) for item in list(origin.get("exports", []))[:8]],
                "origin_demand": str(origin.get("demand", "")),
                "regional_news": self.regional_destination_news(origin),
            }
            visitors.append(visitor)
            journeys[visitor_id] = {
                "visitor_id": visitor_id,
                "name": str(visitor["name"]), "role": str(visitor["role"]),
                "origin_id": str(visitor["origin_id"]), "origin_name": str(visitor["origin"]),
                "origin_kind": str(visitor["origin_kind"]),
                "origin_chunk_x": int(visitor["origin_chunk_x"]), "origin_chunk_y": int(visitor["origin_chunk_y"]),
                "arrival_day_number": absolute_day, "arrival_hour": arrival_hour,
                "return_start_day_number": 0, "return_end_day_number": 0,
                "status": "visiting", "route_condition": str(visitor["route_condition"]),
            }
        life["day_key"] = day_key
        life["occasion_id"] = str(occasion.get("id", ""))
        life["visitors"] = visitors
        life["journeys"] = journeys
        traveler_cache = getattr(self, "_wilderness_travelers", None)
        if isinstance(traveler_cache, dict):
            traveler_cache.clear()
        if occasion:
            log = life.setdefault("event_log", [])
            log.append(f"{day_key}: {occasion['name']} brought {len(visitors)} regional visitors.")
            life["event_log"] = log[-24:]
        return visitors

    def regional_circulation_route_chunks(self, origin_x: int, origin_y: int, identity: str = "") -> List[Tuple[int, int]]:
        x, y = int(origin_x), int(origin_y)
        path = [(x, y)]
        horizontal_first = sum(ord(ch) for ch in str(identity)) % 2 == 0
        axes = ("x", "y") if horizontal_first else ("y", "x")
        for axis in axes:
            while (x if axis == "x" else y) != 0 and len(path) < 1200:
                if axis == "x":
                    x += -1 if x > 0 else 1
                else:
                    y += -1 if y > 0 else 1
                path.append((x, y))
        return path

    def home_region_commute_band(self, hour: Optional[int] = None, minute: Optional[int] = None) -> str:
        """Stable time bands used to refresh short authored-NPC road journeys."""
        hour = int(self.state.hour if hour is None else hour)
        minute = int(self.state.minute if minute is None else minute)
        clock = hour + minute / 60.0
        if 8.0 <= clock < 10.0:
            return "outbound"
        if 10.0 <= clock < 15.0:
            return "working"
        if 15.0 <= clock < 17.0:
            return "returning"
        return "off"

    def home_region_commute_specs(self) -> Dict[str, Dict[str, object]]:
        return {
            "garrick_miner": {
                "weekdays": {"Monday", "Wednesday", "Friday"},
                "destination_id": "home-mine", "destination_name": "Home Mine",
                "destination_kind": "mine",
                "purpose": "checking supports, ore carts, and the day's mine conditions",
                "work_activity": "working the safe upper approach and checking mine supports",
                "allow_bad_weather": True,
            },
            "cora_courier": {
                "weekdays": {"Tuesday", "Thursday", "Saturday"},
                "destination_id": "home-farm", "destination_name": "Home Farm",
                "destination_kind": "farm",
                "purpose": "carrying farm orders, letters, and market delivery notes",
                "work_activity": "sorting farm deliveries and collecting outgoing market notes",
            },
            "rowan_orchard": {
                "weekdays": {"Wednesday", "Saturday"},
                "seasons": {"Spring", "Summer", "Fall"},
                "destination_id": "home-farm", "destination_name": "Home Farm",
                "destination_kind": "farm",
                "purpose": "checking orchard growth and seasonal grafting conditions",
                "work_activity": "examining the farm lane's trees and orchard conditions",
            },
            "hana_botanist": {
                "weekdays": {"Thursday"},
                "seasons": {"Spring", "Summer", "Fall"},
                "destination_id": "home-farm", "destination_name": "Home Farm",
                "destination_kind": "farm",
                "purpose": "recording field growth and plants along the farm boundary",
                "work_activity": "cataloguing field-edge plants near the farm approach",
            },
        }

    def home_region_commute_plan(self, npc: Dict[str, object], active_only: bool = True) -> Dict[str, object]:
        """Return today's local farm/mine journey for an authored resident."""
        npc_id = str(npc.get("id", ""))
        if not npc_id or (active_only and self.home_region_commute_band() == "off"):
            return {}
        if npc_id == str(getattr(self.state, "spouse_npc_id", "")) or self.is_household_child_npc(npc):
            return {}
        active_trip = self.regional_town_life_state().setdefault("resident_trips", {}).get(npc_id, {})
        if isinstance(active_trip, dict) and active_trip:
            return {}
        occasion = self.todays_town_public_occasion()
        if str(occasion.get("kind", "")) == "festival":
            return {}
        spec = self.home_region_commute_specs().get(npc_id)
        if not spec or str(self.state.weekday) not in spec["weekdays"]:
            return {}
        if spec.get("seasons") and str(self.state.season) not in spec["seasons"]:
            return {}
        if self.town_weather_is_severe_for_routines():
            return {}
        if self.town_weather_is_bad_for_routines() and not bool(spec.get("allow_bad_weather", False)):
            return {}
        return {**spec, "npc_id": npc_id, "band": self.home_region_commute_band()}

    def home_region_route_points(self, destination_id: str) -> List[Tuple[int, int]]:
        """Ordered local-road cells from Elsewhere to a home-district endpoint."""
        gateways = self.origin_world_gateway_positions()
        start_x, start_y = gateways["town"]
        gateway_key = "mine" if str(destination_id) == "home-mine" else "farm"
        end_x, end_y = gateways[gateway_key]
        points = [(start_x, y) for y in range(start_y, 37)]
        points.extend((x, 36) for x in range(start_x + 1, end_x + 1))
        points.extend((end_x, y) for y in range(35, end_y - 1, -1))
        return points

    def home_region_commuters_for_chunk(self, chunk_x: int, chunk_y: int) -> List[Dict[str, object]]:
        if (int(chunk_x), int(chunk_y)) != (0, 0):
            return []
        band = self.home_region_commute_band()
        # During the work window these residents have crossed the gateway and
        # are represented by ordinary NPC actors inside the farm or mine.
        if band in {"off", "working"}:
            return []
        clock = int(self.state.hour) + int(self.state.minute) / 60.0
        travelers: List[Dict[str, object]] = []
        for definition in TOWN_NPC_DEFINITIONS:
            npc = self.npc_record_by_id(str(definition.get("id", "")))
            if not npc:
                continue
            plan = self.home_region_commute_plan(npc)
            if not plan:
                continue
            path = self.home_region_route_points(str(plan["destination_id"]))
            if len(path) < 3:
                continue
            # Keep workers beside entrances rather than occupying transition tiles.
            usable_path = path[1:-1]
            if band == "outbound":
                progress = max(0.0, min(1.0, (clock - 8.0) / 2.0))
                path_index = int(progress * (len(usable_path) - 1))
                target_id = str(plan["destination_id"])
                target_name = str(plan["destination_name"])
                target_kind = str(plan["destination_kind"])
                activity = f"walking the home road to {target_name} to {plan['purpose']}"
            elif band == "returning":
                progress = max(0.0, min(1.0, (clock - 15.0) / 2.0))
                path_index = (len(usable_path) - 1) - int(progress * (len(usable_path) - 1))
                target_id, target_name, target_kind = "main-town", "Elsewhere", "main_town"
                activity = f"returning to Elsewhere after {plan['purpose']}"
            else:
                path_index = len(usable_path) - 1
                target_id = str(plan["destination_id"])
                target_name = str(plan["destination_name"])
                target_kind = str(plan["destination_kind"])
                activity = str(plan["work_activity"])
            # Coworkers on the same route walk a few paces apart and use nearby
            # approach cells while working instead of occupying one actor cell.
            path_index = max(0, path_index - len(travelers) * 2)
            preferred_x, preferred_y = usable_path[max(0, min(len(usable_path) - 1, path_index))]
            target_gateway = "town" if target_id == "main-town" else ("mine" if target_id == "home-mine" else "farm")
            target_x, target_y = self.origin_world_gateway_positions()[target_gateway]
            travelers.append({
                "id": str(npc.get("id", "")), "name": str(npc.get("name", "Town Resident")),
                "role": str(npc.get("role", "Resident")), "regional_circulation": True,
                "authored_resident_trip": True, "home_region_commute": True,
                "road_route": True, "fixed_road_route": True, "static_actor": band == "working",
                "preferred_x": preferred_x, "preferred_y": preferred_y,
                "home_route_points": list(usable_path),
                "route_destination_id": target_id, "route_destination_name": target_name,
                "route_destination_kind": target_kind, "route_destination_chunk_x": 0,
                "route_destination_chunk_y": 0, "route_destination_world_x": target_x,
                "route_destination_world_y": target_y, "route_condition": "Local Maintained Road",
                "activity": activity, "commute_purpose": str(plan["purpose"]),
            })
        return travelers

    def invalidate_home_region_commuter_cache(self) -> None:
        cache = getattr(self, "_wilderness_travelers", None)
        if isinstance(cache, dict):
            cache.pop(self.wilderness_traveler_cache_key(0, 0), None)

    def home_region_destination_for_current_location(self) -> str:
        if self.on_farm():
            return "home-farm"
        if self.on_mine() and int(getattr(self.state, "mine_floor", 1)) == 1:
            return "home-mine"
        return ""

    def home_region_destination_tile_open(self, x: int, y: int, used: set) -> bool:
        if not self.in_active_bounds(x, y) or (int(x), int(y)) in used:
            return False
        if (int(x), int(y)) == (int(self.state.player_x), int(self.state.player_y)):
            return False
        tile = self.active_map()[int(y)][int(x)]
        if self.on_farm():
            if tile in {"#", "~", "H", "T", "o", "*", "<"}:
                return False
            if self.get_placed_object(int(x), int(y)) or self.get_crop(int(x), int(y)):
                return False
            if self.farm_animal_at(int(x), int(y)) or self.travel_follower_at(int(x), int(y)):
                return False
            return True
        if self.on_mine():
            if tile not in {".", ":"}:
                return False
            if self.mine_enemy_at(int(x), int(y)) or self.travel_follower_at(int(x), int(y)):
                return False
            return True
        return False

    def home_region_destination_position(self, npc_id: str, used: set) -> Tuple[int, int]:
        if self.on_farm():
            anchors = {
                "cora_courier": (max(3, self.active_map_width() - 9), 10),
                "rowan_orchard": (max(3, self.active_map_width() - 14), 15),
                "hana_botanist": (max(3, self.active_map_width() - 18), 13),
            }
            anchor = anchors.get(str(npc_id), (max(3, self.active_map_width() - 10), 12))
        else:
            anchor = (24, 14)
        ax, ay = int(anchor[0]), int(anchor[1])
        for radius in range(0, 10):
            candidates = []
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if radius and max(abs(dx), abs(dy)) != radius:
                        continue
                    candidates.append((ax + dx, ay + dy))
            candidates.sort(key=lambda point: (abs(point[0] - ax) + abs(point[1] - ay), point[1], point[0]))
            for x, y in candidates:
                if self.home_region_destination_tile_open(x, y, used):
                    return int(x), int(y)
        return max(1, min(self.active_map_width() - 2, ax)), max(1, min(self.active_map_height() - 2, ay))

    def home_region_destination_npc_positions(self) -> Dict[Tuple[int, int], Dict[str, object]]:
        destination_id = self.home_region_destination_for_current_location()
        if not destination_id or self.home_region_commute_band() != "working":
            return {}
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        used = {(int(self.state.player_x), int(self.state.player_y))}
        for definition in TOWN_NPC_DEFINITIONS:
            npc = self.npc_record_by_id(str(definition.get("id", "")))
            if not npc or self.travel_follower_identity_for_npc_id(str(npc.get("id", ""))):
                continue
            plan = self.home_region_commute_plan(npc)
            if not plan or str(plan.get("destination_id", "")) != destination_id:
                continue
            position = self.home_region_destination_position(str(npc.get("id", "")), used)
            npc["home_region_destination_worker"] = True
            npc["home_region_activity"] = str(plan.get("work_activity", "handling local work"))
            npc["runtime_activity"] = str(plan.get("work_activity", "handling local work"))
            lookup[position] = npc
            used.add(position)
        return lookup

    def home_region_work_record(self) -> Dict[str, object]:
        if not isinstance(self.state.wilderness_poi_state, dict):
            self.state.wilderness_poi_state = {}
        record = self.state.wilderness_poi_state.setdefault("home_region_work", {})
        if not isinstance(record, dict):
            record = {}
            self.state.wilderness_poi_state["home_region_work"] = record
        record.setdefault("completed_days", {})
        return record

    def home_region_local_work_status(self, npc: Dict[str, object]) -> Tuple[bool, str]:
        npc_id = str(npc.get("id", ""))
        plan = self.home_region_commute_plan(npc)
        if (
            not plan
            or self.home_region_commute_band() != "working"
            or str(plan.get("destination_id", "")) != self.home_region_destination_for_current_location()
        ):
            return False, "available while working locally"
        completed = self.home_region_work_record().setdefault("completed_days", {})
        if str(completed.get(npc_id, "")) == self.town_npc_day_key():
            return False, "completed today"
        return True, "small practical daily benefit"

    def home_region_local_work_lines(self, npc: Dict[str, object]) -> List[str]:
        npc_id = str(npc.get("id", ""))
        benefits = {
            "garrick_miner": "Review mine supports: today's Pickaxe stamina costs are reduced by 2.",
            "cora_courier": "Sort the farm delivery: receive a Field Snack and 25g delivery credit.",
            "rowan_orchard": "Review the fields: the next crop harvested today yields one extra item.",
            "hana_botanist": "Complete the field survey: receive useful herbs and improve origin-region vitality.",
        }
        return [
            f"LOCAL WORK WITH {npc.get('name', 'RESIDENT').upper()}", "",
            str(getattr(npc, "home_region_activity", "") or npc.get("home_region_activity", "Local destination work.")),
            "", benefits.get(npc_id, "Help with today's local work."), "",
            "Cost: 3 stamina and 30 minutes", "Relationship: +2", "Available once per workday.",
        ]

    def complete_home_region_local_work(self, npc: Dict[str, object]) -> bool:
        available, reason = self.home_region_local_work_status(npc)
        if not available:
            self.set_message(f"Local work is not available: {reason}.")
            return False
        if not self.spend_stamina(3):
            return False
        npc_id = str(npc.get("id", ""))
        record = self.home_region_work_record()
        record.setdefault("completed_days", {})[npc_id] = self.town_npc_day_key()
        drops: Dict[str, int] = {}
        money = 0
        vitality = 0
        if npc_id == "garrick_miner":
            drops = {"Coal": 1}
            record["mine_safety_day"] = self.town_npc_day_key()
        elif npc_id == "cora_courier":
            drops = {"Field Snack": 1}
            money = 25
        elif npc_id == "rowan_orchard":
            drops = {"Wild Apple": 1}
            record["crop_bonus_day"] = self.town_npc_day_key()
            record["crop_bonus_used"] = False
        elif npc_id == "hana_botanist":
            drops = {"Wild Herbs": 1, "Cave Herbs": 1}
            vitality = 1
        add_inventory_items(self.state.inventory, drops)
        self.state.money += money
        relationship = self.adjust_town_npc_relationship(npc_id, 2)
        if vitality:
            self.add_wilderness_region_vitality(0, 0, vitality, "completed Hana's home-field survey")
        self.advance_time(30)
        log = self.regional_town_life_state().setdefault("event_log", [])
        log.append(f"{self.town_npc_day_key()}: Helped {npc.get('name', 'a resident')} with local work at {self.home_region_destination_for_current_location()}.")
        self.regional_town_life_state()["event_log"] = log[-24:]
        reward_parts = []
        if drops:
            reward_parts.append(format_drops(drops))
        if money:
            reward_parts.append(f"{money}g")
        reward_text = ", ".join(reward_parts) or "local progress"
        self.autosave_with_message(
            f"Helped {npc.get('name', 'the resident')} with local work: {reward_text}, relationship +{relationship}."
        )
        return True

    def home_region_journey_lines(self) -> List[str]:
        lines = ["Today's local journeys:"]
        rows = []
        band = self.home_region_commute_band()
        status_labels = {"outbound": "on the road", "working": "at destination", "returning": "returning", "off": "scheduled 8:00-17:00"}
        for definition in TOWN_NPC_DEFINITIONS:
            npc = self.npc_record_by_id(str(definition.get("id", "")))
            if not npc:
                continue
            plan = self.home_region_commute_plan(npc, active_only=False)
            if plan:
                rows.append(f"- {npc.get('name')}: {plan.get('destination_name')} ({status_labels.get(band, band)})")
        lines.extend(rows or ["- None scheduled under today's conditions."])
        return lines

    def regional_circulation_travelers_for_chunk(self, chunk_x: int, chunk_y: int) -> List[Dict[str, object]]:
        self.ensure_regional_town_visitors()
        life = self.regional_town_life_state()
        current_day, hour = self.absolute_game_day(), int(self.state.hour)
        results: List[Dict[str, object]] = []
        for journey in list(life.get("journeys", {}).values()):
            if not isinstance(journey, dict):
                continue
            status = str(journey.get("status", ""))
            path = self.regional_circulation_route_chunks(
                int(journey.get("origin_chunk_x", 0)), int(journey.get("origin_chunk_y", 0)),
                str(journey.get("visitor_id", "")),
            )
            if not path:
                continue
            progress: Optional[float] = None
            inbound = status == "visiting" and current_day == int(journey.get("arrival_day_number", -1)) and hour < int(journey.get("arrival_hour", 8))
            if inbound:
                start_hour, arrival_hour = 6, max(7, int(journey.get("arrival_hour", 8)))
                progress = max(0.0, min(0.98, (hour - start_hour) / float(max(1, arrival_hour - start_hour))))
            elif status == "returning":
                start = int(journey.get("return_start_day_number", 0))
                end = max(start + 1, int(journey.get("return_end_day_number", start + 1)))
                if current_day > end:
                    journey["status"] = "completed"
                    continue
                if current_day >= start:
                    elapsed = (current_day - start) + max(0, hour - 6) / 18.0
                    progress = 1.0 - max(0.0, min(1.0, elapsed / float(end - start)))
            if progress is None:
                continue
            index = min(len(path) - 1, max(0, int(progress * len(path))))
            if path[index] != (int(chunk_x), int(chunk_y)):
                continue
            destination_name = "Elsewhere" if inbound else str(journey.get("origin_name", "their home route"))
            results.append({
                "id": str(journey.get("visitor_id", "regional_visitor")),
                "name": str(journey.get("name", "Traveler")),
                "role": str(journey.get("role", "Traveler")),
                "regional_circulation": True,
                "road_route": True,
                "route_destination_id": "main-town" if inbound else str(journey.get("origin_id", "")),
                "route_destination_name": destination_name,
                "route_destination_kind": "main_town" if inbound else str(journey.get("origin_kind", "road_service")),
                "route_destination_chunk_x": 0 if inbound else int(journey.get("origin_chunk_x", 0)),
                "route_destination_chunk_y": 0 if inbound else int(journey.get("origin_chunk_y", 0)),
                "activity": f"following the regional road toward {destination_name}",
                "route_condition": str(journey.get("route_condition", "Open")),
            })
        for npc_id, trip in list(life.get("resident_trips", {}).items()):
            if not isinstance(trip, dict):
                continue
            depart = int(trip.get("depart_day_number", 0) or 0)
            returning = max(depart + 1, int(trip.get("return_day_number", depart + 1) or depart + 1))
            if not (depart <= current_day < returning):
                continue
            duration = float(returning - depart)
            elapsed = (current_day - depart) + max(0, hour - 6) / 18.0
            journey_progress = max(0.0, min(0.999, elapsed / duration))
            path = self.regional_circulation_route_chunks(
                int(trip.get("chunk_x", 0)), int(trip.get("chunk_y", 0)), str(npc_id),
            )
            if journey_progress < 0.45:
                road_progress = 1.0 - journey_progress / 0.45
                destination_name = str(trip.get("destination_name", "a regional destination"))
            elif journey_progress > 0.55:
                road_progress = (journey_progress - 0.55) / 0.45
                destination_name = "Elsewhere"
            else:
                continue
            index = min(len(path) - 1, max(0, int(road_progress * len(path))))
            if path[index] != (int(chunk_x), int(chunk_y)):
                continue
            npc = self.npc_record_by_id(str(npc_id))
            if not npc:
                continue
            destination_chunk_x = int(trip.get("chunk_x", 0)) if destination_name != "Elsewhere" else 0
            destination_chunk_y = int(trip.get("chunk_y", 0)) if destination_name != "Elsewhere" else 0
            results.append({
                "id": str(npc_id), "name": str(npc.get("name", "Town Resident")),
                "role": str(npc.get("role", "Traveler")),
                "regional_circulation": True, "authored_resident_trip": True, "road_route": True,
                "route_destination_id": str(trip.get("destination_id", "")) if destination_name != "Elsewhere" else "main-town",
                "route_destination_name": destination_name,
                "route_destination_kind": str(trip.get("destination_kind", "road_service")) if destination_name != "Elsewhere" else "main_town",
                "route_destination_chunk_x": destination_chunk_x,
                "route_destination_chunk_y": destination_chunk_y,
                "activity": f"traveling for town business toward {destination_name}",
                "route_condition": str(trip.get("route_condition", "Open")),
            })
        results.extend(self.home_region_commuters_for_chunk(chunk_x, chunk_y))
        return results

    def regional_town_visitors(self) -> List[Dict[str, object]]:
        return self.ensure_regional_town_visitors()

    def regional_visitor_desired_location(self, visitor: Dict[str, object]) -> str:
        phase = self.town_routine_phase()
        occasion = self.todays_town_public_occasion()
        if phase == "late":
            return "GuestLodging"
        if phase == "evening" and str(occasion.get("kind", "")) != "festival":
            return "InnInterior"
        if phase == "wake":
            return "InnInterior"
        return "Town"

    def regional_visitor_town_target(self, visitor: Dict[str, object]) -> Tuple[int, int]:
        occasion = self.todays_town_public_occasion()
        kind = str(occasion.get("kind", ""))
        offset = int(visitor.get("route_slot", 0) or 0) % 6
        if kind in {"market", "supply"}:
            return ((81, 30), (85, 30), (89, 30), (93, 30), (81, 34), (89, 34))[offset]
        if kind == "festival":
            return ((42, 29), (45, 29), (51, 29), (54, 29), (48, 25), (58, 29))[offset]
        return ((57, 10), (49, 22), (73, 22), (88, 35), (39, 10), (25, 22))[offset]

    def town_public_gathering_anchor(self, npc: Dict[str, object], kind: str) -> Tuple[int, int]:
        npc_id = str(npc.get("id", ""))
        ordered_ids = [str(record.get("id", "")) for record in TOWN_NPC_DEFINITIONS]
        if npc_id in ordered_ids:
            slot = ordered_ids.index(npc_id)
        else:
            slot = len(ordered_ids) + sum(ord(ch) for ch in npc_id)
        if kind == "festival":
            bounds = (35, 21, 65, 35)
        else:
            bounds = (79, 25, 96, 39)
        x0, y0, x1, y1 = bounds
        candidates = [
            (x, y)
            for y in range(y0, y1 + 1)
            for x in range(x0, x1 + 1)
            if self.town_map[y][x] in {".", "=", ":", ","}
            and (x + y) % 2 == 0
        ]
        return candidates[slot % len(candidates)] if candidates else (49, 29)

    def update_regional_town_visitors(self):
        if not (self.on_town() or self.on_town_interior()):
            return
        for index, visitor in enumerate(self.regional_town_visitors()):
            desired = self.regional_visitor_desired_location(visitor)
            actual = str(visitor.get("runtime_location", "Town"))
            if actual == "InTransit":
                if int(self.state.hour) < int(visitor.get("arrival_hour", 8)):
                    visitor["activity"] = (
                        f"delayed along the {visitor.get('route_condition', 'open').lower()} road "
                        f"from {visitor.get('origin', 'the region')}"
                    )
                    continue
                visitor["runtime_location"] = "Town"
                visitor["x"], visitor["y"] = 56 + (index % 4), 1
                visitor["activity"] = "arriving through the north road"
                actual = "Town"
            if desired == "GuestLodging":
                visitor["runtime_location"] = desired
                visitor["activity"] = "resting in an assigned private guest room"
                continue
            if actual == "GuestLodging":
                visitor["runtime_location"] = "Town"
                visitor["x"], visitor["y"] = 56 + (index % 4), 1
                actual = "Town"
            if desired == "InnInterior":
                if actual == "InnInterior":
                    visitor["activity"] = "sharing road news in the inn before retiring to a private room"
                    continue
                target = self.town_npc_exterior_access("InnInterior", str(visitor.get("id", "")))
                visitor["activity"] = "following the road toward the inn"
                if self.town_npc_move_town_toward(visitor, target):
                    visitor["runtime_location"] = "InnInterior"
                    visitor["interior_x"], visitor["interior_y"] = (22 + index * 3, 16)
                continue
            if actual == "InnInterior":
                visitor["runtime_location"] = "Town"
                visitor["x"], visitor["y"] = self.town_npc_exterior_access("InnInterior", str(visitor.get("id", "")))
            target = self.regional_visitor_town_target(visitor)
            occasion = self.todays_town_public_occasion()
            visitor["activity"] = (
                f"taking part in {occasion['name']}"
                if occasion else str(visitor.get("purpose", "walking the regional roads"))
            )
            self.town_npc_move_town_toward(visitor, target)
        if self.town_routine_phase() not in {"lunch", "evening"}:
            return
        local_npcs = [
            npc for npc in self.active_town_npcs()
            if self.town_npc_actual_location(npc) == "Town" and not str(npc.get("runtime_transition", ""))
        ]
        for visitor in self.regional_town_visitors():
            if str(visitor.get("runtime_location", "")) != "Town":
                continue
            vx, vy = int(visitor.get("x", 0)), int(visitor.get("y", 0))
            nearby = sorted(
                (
                    abs(vx - int(npc.get("x", 0))) + abs(vy - int(npc.get("y", 0))),
                    str(npc.get("id", "")),
                    npc,
                )
                for npc in local_npcs
            )
            if not nearby or nearby[0][0] > 5:
                continue
            local = nearby[0][2]
            self.record_town_npc_social_link(visitor, local)
            visitor["local_contact_id"] = str(local.get("id", ""))
            visitor["activity"] = f"exchanging regional news with {local.get('name', 'a local resident')}"

    def regional_visitor_position_lookup(self) -> Dict[Tuple[int, int], Dict[str, object]]:
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}
        if self.on_town():
            for visitor in self.regional_town_visitors():
                if str(visitor.get("runtime_location", "")) == "Town":
                    lookup[(int(visitor.get("x", -1)), int(visitor.get("y", -1)))] = visitor
            return lookup
        if self.state.location != "InnInterior":
            return lookup
        used = set(self.town_indoor_npc_positions(normalize=False).values())
        anchors = ((23, 15), (29, 15), (34, 15), (24, 9), (30, 9))
        for index, visitor in enumerate(self.regional_town_visitors()):
            if str(visitor.get("runtime_location", "")) != "InnInterior":
                continue
            anchor = anchors[index % len(anchors)]
            position = self.town_npc_nearest_interior_tile("InnInterior", anchor[0], anchor[1], used)
            visitor["interior_x"], visitor["interior_y"] = position
            used.add(position)
            lookup[position] = visitor
        return lookup

    def town_npc_public_schedule_entry(self, npc: Dict[str, object]) -> Dict[str, object]:
        npc_id = str(npc.get("id", ""))
        phase = self.town_routine_phase()
        life = self.regional_town_life_state()
        trips = life.setdefault("resident_trips", {})
        active_trip = trips.get(npc_id, {})
        current_day = self.absolute_game_day()
        if isinstance(active_trip, dict) and active_trip:
            if current_day < int(active_trip.get("return_day_number", 0) or 0):
                npc["regional_destination"] = str(active_trip.get("destination_name", "Regional Roads"))
                npc["regional_destination_id"] = str(active_trip.get("destination_id", ""))
                npc["regional_destination_kind"] = str(active_trip.get("destination_kind", "road_service"))
                npc["regional_destination_chunk_x"] = int(active_trip.get("chunk_x", 0))
                npc["regional_destination_chunk_y"] = int(active_trip.get("chunk_y", 0))
                npc["regional_expected_return"] = str(active_trip.get("expected_return", ""))
                return {
                    "away": str(active_trip.get("destination_name", "the regional roads")),
                    "activity": (
                        f"{active_trip.get('purpose', 'handling a regional errand')} at "
                        f"{active_trip.get('destination_name', 'a mapped destination')}; "
                        f"expected back {active_trip.get('expected_return', 'soon')}"
                    ),
                }
            trips.pop(npc_id, None)
            log = life.setdefault("event_log", [])
            log.append(f"{self.town_npc_day_key()}: {npc.get('name', 'A resident')} returned from {active_trip.get('destination_name', 'a regional trip')}.")
            life["event_log"] = log[-24:]
        occasion = self.todays_town_public_occasion()
        kind = str(occasion.get("kind", ""))
        seed = sum(ord(ch) for ch in npc_id)
        family_member = bool(
            self.is_household_child_npc(npc)
            or npc_id == str(getattr(self.state, "spouse_npc_id", ""))
        )
        if kind == "festival" and phase in {"lunch", "work_afternoon", "evening"}:
            return {
                "at": self.town_public_gathering_anchor(npc, "festival"),
                "activity": f"attending {occasion['name']} with neighbors and visiting travelers",
            }
        if kind in {"market", "supply"} and phase == "work_afternoon":
            participates = family_member or seed % 3 != 0 or str(npc.get("role", "")) in {"Market Vendor", "Courier", "Seed Seller", "Chef"}
            if str(npc.get("role", "")) in TOWN_INDOOR_WORK_ROLES and str(npc.get("role", "")) not in {"Market Vendor"}:
                participates = False
            if participates:
                return {
                    "at": self.town_public_gathering_anchor(npc, "market"),
                    "activity": f"browsing stalls and exchanging news at {occasion['name']}",
                }
        if kind == "music" and phase == "evening":
            participates = family_member or seed % 2 == 0 or str(npc.get("role", "")) in {"Musician", "Innkeeper", "Chef", "Traveler"}
            if participates:
                return {
                    "inside": "Town Inn",
                    "activity": "listening to music and exchanging road stories at the inn",
                }
        local_commute = self.home_region_commute_plan(npc)
        if local_commute:
            npc["regional_destination"] = str(local_commute["destination_name"])
            npc["regional_destination_id"] = str(local_commute["destination_id"])
            npc["regional_destination_kind"] = str(local_commute["destination_kind"])
            npc["regional_destination_chunk_x"] = 0
            npc["regional_destination_chunk_y"] = 0
            npc["regional_expected_return"] = "this evening"
            band = str(local_commute.get("band", "working"))
            if band == "outbound":
                activity = f"walking the home road to {local_commute['destination_name']} to {local_commute['purpose']}"
            elif band == "returning":
                activity = f"returning from {local_commute['destination_name']} after {local_commute['purpose']}"
            else:
                activity = str(local_commute["work_activity"])
            return {"away": str(local_commute["destination_name"]), "activity": activity}
        trip_ids = {
            "finn_fisher", "theo_miner", "silas_recluse", "niko_orchard",
            "hana_botanist", "marisol_artist", "otto_scholar", "aria_musician",
            "cora_tailor", "jules_mechanic",
        }
        if (
            npc_id in trip_ids
            and phase == "work_afternoon"
            and str(self.state.weekday) in {"Tuesday", "Thursday"}
            and (seed + self.absolute_game_day()) % 3 == 0
            and not self.town_weather_is_bad_for_routines()
        ):
            destination = self.regional_destination_for_identity(npc_id, current_day)
            route = self.regional_route_profile(destination, npc_id)
            purpose = {
                "Fisher": "checking waterfront prices and ferry conditions",
                "Miner": "comparing ore reports and supply needs",
                "Scholar": "exchanging records and civic news",
                "Artist": "visiting public spaces and gathering new motifs",
                "Musician": "following a regional performance invitation",
                "Botanist": "surveying seasonal plants with regional workers",
                "Mechanic": "inspecting infrastructure and repair requests",
                "Tailor": "sourcing regional cloth and taking measurements",
            }.get(str(npc.get("role", "")), "handling a scheduled regional errand")
            expected_return = self.regional_return_date_label(int(route["travel_days"]))
            trips[npc_id] = {
                "destination_id": str(destination.get("id", "")),
                "destination_name": str(destination.get("name", "Regional Roads")),
                "destination_kind": str(destination.get("kind", "road_service")),
                "chunk_x": int(destination.get("chunk_x", 0)),
                "chunk_y": int(destination.get("chunk_y", 0)),
                "depart_day_number": current_day,
                "return_day_number": current_day + int(route["travel_days"]),
                "expected_return": expected_return,
                "purpose": purpose,
                "route_condition": str(route["route_condition"]),
            }
            npc["regional_destination"] = str(destination.get("name", "Regional Roads"))
            npc["regional_destination_id"] = str(destination.get("id", ""))
            npc["regional_destination_kind"] = str(destination.get("kind", "road_service"))
            npc["regional_destination_chunk_x"] = int(destination.get("chunk_x", 0))
            npc["regional_destination_chunk_y"] = int(destination.get("chunk_y", 0))
            npc["regional_expected_return"] = expected_return
            return {
                "away": str(destination.get("name", "the regional roads")),
                "activity": f"traveling to {destination.get('name', 'a mapped destination')} to {purpose}; expected back {expected_return}",
            }
        return {}

    def town_weather_is_bad_for_routines(self) -> bool:
        return str(self.state.weather) in ["Rain", "Rainy", "Storm", "Stormy", "Snow", "Snowy", "Blizzard"]

    def town_weather_is_severe_for_routines(self) -> bool:
        return str(self.state.weather) in ["Storm", "Stormy", "Blizzard"]

    def town_routine_phase(self, hour: Optional[int] = None) -> str:
        h = int(getattr(self.state, "hour", 6) if hour is None else hour)
        if 6 <= h < 8:
            return "wake"
        if 8 <= h < 12:
            return "work_morning"
        if 12 <= h < 14:
            return "lunch"
        if 14 <= h < 17:
            return "work_afternoon"
        if 17 <= h < 21:
            return "evening"
        return "late"

    def town_routine_phase_label(self, phase: Optional[str] = None) -> str:
        return TOWN_ROUTINE_PHASE_LABELS.get(str(phase or self.town_routine_phase()), "Routine")

    def town_time_period(self) -> str:
        phase = self.town_routine_phase()
        if phase in ["wake", "work_morning"]:
            return "morning"
        if phase in ["lunch", "work_afternoon"]:
            return "midday"
        return "evening"

    def town_npc_definition(self, npc_id: str) -> Dict[str, object]:
        for definition in TOWN_NPC_DEFINITIONS:
            if definition.get("id") == npc_id:
                return definition
        return {}

    def town_npc_routine_entry(self, value, activity: str = "") -> Dict[str, object]:
        if isinstance(value, dict):
            entry = dict(value)
            if activity and not entry.get("activity"):
                entry["activity"] = activity
            return entry
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            entry = {"at": (int(value[0]), int(value[1]))}
            if activity:
                entry["activity"] = activity
            return entry
        entry = {"at": (0, 0)}
        if activity:
            entry["activity"] = activity
        return entry

    def town_npc_sleep_home_name(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        overrides = {
            "mayor_ruth": "Mayor's House",
            "lulu_child": "Mayor's House",
        }
        residence_id = AUTHORED_TOWN_RESIDENCE_ID_BY_NPC.get(npc_id, "")
        if residence_id:
            return str(AUTHORED_TOWN_RESIDENCE_DATA[residence_id]["label"])
        home = str(overrides.get(npc_id, npc.get("home", "")))
        # The authored inn has three separate guest rooms. Keep those rooms
        # one-person spaces instead of using the inn as a fallback residence
        # for most of town.
        if home == "Inn" and npc_id not in {"mae_innkeeper", "chef_basil", "aria_musician"}:
            return "Private Home"
        if self.town_interior_location_for_name(home):
            return home
        return "Private Home"

    def town_npc_home_routine_value(self, npc: Dict[str, object]):
        home = self.town_npc_sleep_home_name(npc)
        if self.town_interior_location_for_name(home) or home.strip().lower() in AUTHORED_TOWN_RESIDENCE_ID_BY_NAME:
            return {"inside": home}
        return {"inside": "Private Home"}

    def town_npc_residence_runtime_location(self, residence_id: str) -> str:
        return f"TownResidence:{str(residence_id)}"

    def town_npc_residence_id_from_runtime(self, location: str) -> str:
        prefix = "TownResidence:"
        location = str(location)
        residence_id = location[len(prefix):] if location.startswith(prefix) else ""
        return residence_id if residence_id in AUTHORED_TOWN_RESIDENCE_DATA else ""

    def town_npc_is_authored_interior_location(self, location: str) -> bool:
        return bool(
            str(location) in AUTHORED_TOWN_INTERIOR_MAP_ATTRS
            or self.town_npc_residence_id_from_runtime(str(location))
        )

    def town_npc_authored_location_label(self, location: str) -> str:
        residence_id = self.town_npc_residence_id_from_runtime(location)
        if residence_id:
            return str(AUTHORED_TOWN_RESIDENCE_DATA[residence_id]["label"])
        return TOWN_INTERIOR_NAME_BY_LOCATION.get(str(location), "Building")

    def town_npc_role_activity(self, npc: Dict[str, object], phase: Optional[str] = None) -> str:
        role = str(npc.get("role", "Villager"))
        phase_key = str(phase or self.town_npc_current_routine_phase(npc))
        if phase_key == "wake":
            return "waking up in their bedroom"
        if phase_key == "late":
            return "sleeping in their bedroom"
        activities = TOWN_NPC_ROUTINE_ACTIVITIES.get(role, {})
        if phase_key in activities:
            return str(activities[phase_key])
        if phase_key == "bad_weather":
            return "keeping to a weather-safe routine"
        if phase_key == "wake":
            return "starting the day near home"
        if phase_key == "lunch":
            return "taking a midday break"
        if phase_key == "late":
            return "turning in for the night"
        return "following their routine"

    def town_npc_evening_routine_value(self, npc: Dict[str, object], scheduled, home):
        npc_id = str(npc.get("id", ""))
        residence_id = AUTHORED_TOWN_RESIDENCE_ID_BY_NPC.get(npc_id, "")
        if not residence_id:
            return scheduled
        weekday = str(getattr(self.state, "weekday", ""))
        if weekday == "Saturday" and sum(ord(ch) for ch in npc_id) % 2 == 0:
            residence_ids = list(AUTHORED_TOWN_RESIDENCE_DATA)
            visit_id = residence_ids[(residence_ids.index(residence_id) + 1) % len(residence_ids)]
            visit_label = str(AUTHORED_TOWN_RESIDENCE_DATA[visit_id]["label"])
            return {
                "inside": visit_label,
                "activity": f"visiting {visit_label} for a shared supper",
            }
        if weekday in {"Monday", "Wednesday", "Friday", "Saturday", "Sunday"}:
            return {
                "inside": str(AUTHORED_TOWN_RESIDENCE_DATA[residence_id]["label"]),
                "activity": "sharing the evening meal with their household",
            }
        return scheduled

    def town_npc_routine_plan(self, npc: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        definition = self.town_npc_definition(str(npc.get("id", "")))
        schedule = definition.get("schedule", {}) if isinstance(definition, dict) else {}
        role = str(npc.get("role", "Villager"))
        home = self.town_npc_home_routine_value(npc)
        morning = schedule.get("morning", home)
        midday = schedule.get("midday", morning)
        evening = self.town_npc_evening_routine_value(npc, schedule.get("evening", home), home)
        rain = schedule.get("rain", morning if role in TOWN_INDOOR_WORK_ROLES else home)
        afternoon = schedule.get("afternoon", morning if role in TOWN_INDOOR_WORK_ROLES else midday)

        return {
            "wake": self.town_npc_routine_entry(home, self.town_npc_role_activity(npc, "wake")),
            "work_morning": self.town_npc_routine_entry(morning, self.town_npc_role_activity(npc, "work_morning")),
            "lunch": self.town_npc_routine_entry(schedule.get("lunch", midday), self.town_npc_role_activity(npc, "lunch")),
            "work_afternoon": self.town_npc_routine_entry(afternoon, self.town_npc_role_activity(npc, "work_afternoon")),
            "evening": self.town_npc_routine_entry(evening, self.town_npc_role_activity(npc, "evening")),
            "late": self.town_npc_routine_entry(home, self.town_npc_role_activity(npc, "late")),
            "bad_weather": self.town_npc_routine_entry(rain, self.town_npc_role_activity(npc, "bad_weather")),
        }

    def town_npc_current_routine_phase(self, npc: Dict[str, object]) -> str:
        phase = self.town_routine_phase()
        if phase not in ["late"] and self.town_weather_is_bad_for_routines():
            plan = self.town_npc_routine_plan_without_phase_check(npc)
            if "bad_weather" in plan:
                return "bad_weather"
        return phase

    def town_npc_routine_plan_without_phase_check(self, npc: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        definition = self.town_npc_definition(str(npc.get("id", "")))
        schedule = definition.get("schedule", {}) if isinstance(definition, dict) else {}
        role = str(npc.get("role", "Villager"))
        home = self.town_npc_home_routine_value(npc)
        morning = schedule.get("morning", home)
        midday = schedule.get("midday", morning)
        evening = self.town_npc_evening_routine_value(npc, schedule.get("evening", home), home)
        rain = schedule.get("rain", morning if role in TOWN_INDOOR_WORK_ROLES else home)
        afternoon = schedule.get("afternoon", morning if role in TOWN_INDOOR_WORK_ROLES else midday)
        return {
            "wake": self.town_npc_routine_entry(home, self.town_npc_role_activity(npc, "wake")),
            "work_morning": self.town_npc_routine_entry(morning, self.town_npc_role_activity(npc, "work_morning")),
            "lunch": self.town_npc_routine_entry(schedule.get("lunch", midday), self.town_npc_role_activity(npc, "lunch")),
            "work_afternoon": self.town_npc_routine_entry(afternoon, self.town_npc_role_activity(npc, "work_afternoon")),
            "evening": self.town_npc_routine_entry(evening, self.town_npc_role_activity(npc, "evening")),
            "late": self.town_npc_routine_entry(home, self.town_npc_role_activity(npc, "late")),
            "bad_weather": self.town_npc_routine_entry(rain, self.town_npc_role_activity(npc, "bad_weather")),
        }

    def town_npc_schedule_raw_value(self, npc: Dict[str, object]):
        public_entry = self.town_npc_public_schedule_entry(npc)
        if public_entry:
            return public_entry
        if self.spouse_lives_on_farm() and str(npc.get("id", "")) == self.state.spouse_npc_id:
            return {"inside": "Farmhouse", "activity": self.spouse_household_activity_label(npc)}
        plan = self.town_npc_routine_plan(npc)
        phase = self.town_npc_current_routine_phase(npc)
        return plan.get(phase) or plan.get(self.town_routine_phase()) or plan.get("lunch") or (npc.get("home_x", npc.get("x", 0)), npc.get("home_y", npc.get("y", 0)))

    def normalize_town_npc_schedule_value(self, value):
        if isinstance(value, dict):
            if "away" in value:
                return {"away": str(value.get("away", "the regional roads"))}
            if "inside" in value:
                return {"inside": str(value.get("inside", "Building"))}
            if "at" in value:
                value = value.get("at")
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return (int(value[0]), int(value[1]))
        return (0, 0)

    def town_npc_routine_location_label_for_entry(self, entry) -> str:
        raw = self.normalize_town_npc_schedule_value(entry)
        if isinstance(raw, dict) and "away" in raw:
            return f"away at {raw.get('away', 'the regional roads')}"
        if isinstance(raw, dict) and "inside" in raw:
            return f"inside {raw.get('inside', 'Building')}"
        try:
            ax, ay = int(raw[0]), int(raw[1])
        except Exception:
            return "somewhere in town"
        return f"near {ax},{ay}"

    def town_npc_routine_activity_for_entry(self, npc: Dict[str, object], phase: str, entry) -> str:
        if isinstance(entry, dict) and entry.get("activity"):
            return str(entry.get("activity"))
        return self.town_npc_role_activity(npc, phase)

    def town_npc_routine_brief(self, npc: Dict[str, object], phase: Optional[str] = None) -> str:
        phase_key = str(phase or self.town_npc_current_routine_phase(npc))
        plan = self.town_npc_routine_plan(npc)
        entry = plan.get(phase_key) or plan.get(self.town_routine_phase()) or {}
        activity = self.town_npc_routine_activity_for_entry(npc, phase_key, entry)
        location = self.town_npc_routine_location_label_for_entry(entry)
        return f"{self.town_routine_phase_label(phase_key)}: {activity} ({location})"

    def town_npc_next_routine_phase(self, npc: Dict[str, object]) -> Tuple[str, str]:
        current = self.town_routine_phase()
        try:
            index = TOWN_ROUTINE_PHASE_ORDER.index(current)
        except ValueError:
            index = 0
        next_phase = TOWN_ROUTINE_PHASE_ORDER[(index + 1) % len(TOWN_ROUTINE_PHASE_ORDER)]
        return next_phase, TOWN_ROUTINE_PHASE_STARTS.get(next_phase, "")

    def town_npc_next_routine_line(self, npc: Dict[str, object]) -> str:
        next_phase, starts = self.town_npc_next_routine_phase(npc)
        prefix = f"Next at {starts}" if starts else "Next"
        return f"{prefix}: {self.town_npc_routine_brief(npc, next_phase)}"

    def town_npc_routine_lines(self, npc: Dict[str, object]) -> List[str]:
        plan = self.town_npc_routine_plan(npc)
        lines: List[str] = []
        for phase in TOWN_ROUTINE_PHASE_ORDER:
            entry = plan.get(phase)
            if not entry:
                continue
            start = TOWN_ROUTINE_PHASE_STARTS.get(phase, "")
            label = self.town_routine_phase_label(phase)
            activity = self.town_npc_routine_activity_for_entry(npc, phase, entry)
            location = self.town_npc_routine_location_label_for_entry(entry)
            lines.append(f"{start} {label}: {activity} ({location})")
        if self.town_weather_is_bad_for_routines() and plan.get("bad_weather"):
            entry = plan["bad_weather"]
            activity = self.town_npc_routine_activity_for_entry(npc, "bad_weather", entry)
            location = self.town_npc_routine_location_label_for_entry(entry)
            lines.append(f"Bad weather: {activity} ({location})")
        return lines

    def town_npc_desired_location(self, npc: Dict[str, object]) -> str:
        raw = self.normalize_town_npc_schedule_value(self.town_npc_schedule_raw_value(npc))
        if isinstance(raw, dict) and "away" in raw:
            npc["regional_destination"] = str(raw.get("away", "the regional roads"))
            return "RegionalTravel"
        if isinstance(raw, dict) and "inside" in raw:
            place = str(raw.get("inside", ""))
            if place.lower() == "farmhouse":
                return "HouseInterior"
            if place.lower() == "private home":
                return "PrivateResidence"
            residence_id = AUTHORED_TOWN_RESIDENCE_ID_BY_NAME.get(place.strip().lower(), "")
            if residence_id:
                return self.town_npc_residence_runtime_location(residence_id)
            return self.town_interior_location_for_name(place) or "PrivateResidence"
        return "Town"

    def town_npc_actual_location(self, npc: Dict[str, object]) -> str:
        location = str(npc.get("runtime_location", ""))
        valid = {"Town", "HouseInterior", "PrivateResidence", "RegionalTravel", *AUTHORED_TOWN_INTERIOR_MAP_ATTRS.keys()}
        if location not in valid and not self.town_npc_residence_id_from_runtime(location):
            location = self.town_npc_desired_location(npc)
            npc["runtime_location"] = location
        return location

    def town_npc_is_indoor(self, npc: Dict[str, object]) -> bool:
        return self.town_npc_actual_location(npc) != "Town"

    def town_npc_indoor_location(self, npc: Dict[str, object]) -> str:
        location = self.town_npc_actual_location(npc)
        if location == "HouseInterior":
            return "Farmhouse"
        if location == "PrivateResidence":
            return "Private Home"
        if location == "RegionalTravel":
            return str(npc.get("regional_destination", "Regional Roads"))
        if self.town_npc_is_authored_interior_location(location):
            return self.town_npc_authored_location_label(location)
        return ""

    def town_npc_location_label(self, npc: Dict[str, object]) -> str:
        actual = self.town_npc_actual_location(npc)
        desired = self.town_npc_desired_location(npc)
        if actual == "PrivateResidence":
            return "at home"
        if actual == "RegionalTravel":
            expected = str(npc.get("regional_expected_return", ""))
            suffix = f"; expected back {expected}" if expected else ""
            return f"away at {npc.get('regional_destination', 'the regional roads')}{suffix}"
        if actual == "HouseInterior":
            return "inside the Farmhouse"
        if self.town_npc_is_authored_interior_location(actual):
            return f"inside {self.town_npc_authored_location_label(actual)}"
        if self.town_npc_is_authored_interior_location(desired):
            return f"walking to {self.town_npc_authored_location_label(desired)}"
        if desired == "PrivateResidence":
            return "heading home"
        if desired == "RegionalTravel":
            return f"heading toward {npc.get('regional_destination', 'the regional roads')}"
        return f"near {int(npc.get('x', 0))},{int(npc.get('y', 0))}"

    def town_npc_is_available(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        if not npc_id:
            return False
        if (
            bool(npc.get("deceased", False))
            or npc_id in set(
                getattr(self.state, "deceased_spouse_npc_ids", []) or []
            )
        ):
            return False
        if self.is_household_child_npc(npc):
            return True
        if npc_id == getattr(self.state, "spouse_npc_id", ""):
            return True
        try:
            stage = int(getattr(self.state, "town_development_stage", 0))
        except Exception:
            stage = 0
        if stage >= 3:
            return True
        required_building = TOWN_NPC_REQUIRED_BUILDINGS.get(npc_id, "")
        if required_building:
            return bool(self.is_town_building_unlocked(required_building))
        if stage <= 0:
            return npc_id in set(TOWN_STAGE0_NPC_IDS)
        return True

    def active_town_npcs(self) -> List[Dict[str, object]]:
        self.normalize_town_npcs()
        return [
            npc
            for npc in self.state.town_npcs
            if self.town_npc_is_available(npc)
        ]

    def inactive_town_npcs(self) -> List[Dict[str, object]]:
        self.normalize_town_npcs()
        return [
            npc
            for npc in self.state.town_npcs
            if (
                not bool(npc.get("deceased", False))
                and str(npc.get("id", "")) not in set(
                    getattr(self.state, "deceased_spouse_npc_ids", []) or []
                )
                and not self.town_npc_is_available(npc)
            )
        ]

    def visible_town_npcs(self) -> List[Dict[str, object]]:
        self.normalize_town_npcs()
        return [npc for npc in self.active_town_npcs() if not self.town_npc_is_indoor(npc)]

    def town_npc_schedule_anchor(self, npc: Dict[str, object]) -> Tuple[int, int]:
        raw = self.normalize_town_npc_schedule_value(self.town_npc_schedule_raw_value(npc))
        if isinstance(raw, dict) and "inside" in raw:
            # Indoor NPCs keep their last known map position but do not render on the town map.
            return int(npc.get("current_anchor_x", npc.get("home_x", npc.get("x", 0)))), int(npc.get("current_anchor_y", npc.get("home_y", npc.get("y", 0))))

        try:
            ax, ay = int(raw[0]), int(raw[1])
        except Exception:
            ax, ay = int(npc.get("home_x", npc.get("x", 0))), int(npc.get("home_y", npc.get("y", 0)))

        safe_tiles = [".", "=", ":", ",", "?", "!"]
        if 0 <= ax < TOWN_WIDTH and 0 <= ay < TOWN_HEIGHT and self.town_map[ay][ax] in safe_tiles:
            return ax, ay

        best: Optional[Tuple[int, int]] = None
        best_dist = 9999
        for radius in range(1, 5):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = ax + dx, ay + dy
                    if not (0 <= nx < TOWN_WIDTH and 0 <= ny < TOWN_HEIGHT):
                        continue
                    if self.town_map[ny][nx] not in safe_tiles:
                        continue
                    dist = abs(dx) + abs(dy)
                    if dist < best_dist:
                        best = (nx, ny)
                        best_dist = dist
            if best is not None:
                return best

        return int(npc.get("home_x", npc.get("x", 0))), int(npc.get("home_y", npc.get("y", 0)))

    def town_npc_relationship(self, npc_id: str) -> int:
        procedural = self.procedural_resident_by_id(str(npc_id))
        if procedural:
            try:
                return int(procedural.get("relationship", 0))
            except Exception:
                return 0
        try:
            return int(self.state.town_npc_relationships.get(str(npc_id), 0))
        except Exception:
            return 0

    def town_npc_courtship_count(self, npc_id: str) -> int:
        if not isinstance(self.state.town_npc_courtship_counts, dict):
            self.state.town_npc_courtship_counts = {}
        try:
            return max(0, int(self.state.town_npc_courtship_counts.get(str(npc_id), 0)))
        except Exception:
            return 0

    def increment_town_npc_courtship_count(self, npc_id: str):
        npc_id = str(npc_id)
        self.state.town_npc_courtship_counts[npc_id] = self.town_npc_courtship_count(npc_id) + 1

    def relationship_milestones_for_npc(self, npc_id: str) -> set:
        if not isinstance(self.state.town_npc_relationship_milestones, dict):
            self.state.town_npc_relationship_milestones = {}
        milestones = self.state.town_npc_relationship_milestones.get(str(npc_id), [])
        if not isinstance(milestones, list):
            milestones = []
        clean = {str(flag) for flag in milestones if flag is not None}
        self.state.town_npc_relationship_milestones[str(npc_id)] = sorted(clean)
        return clean

    def has_relationship_milestone(self, npc_id: str, milestone: str) -> bool:
        return str(milestone) in self.relationship_milestones_for_npc(str(npc_id))

    def set_relationship_milestone(self, npc_id: str, milestone: str):
        npc_id = str(npc_id)
        milestones = self.relationship_milestones_for_npc(npc_id)
        milestones.add(str(milestone))
        self.state.town_npc_relationship_milestones[npc_id] = sorted(milestones)

    def is_sample_milestone_npc(self, npc_id: str) -> bool:
        return str(npc_id) in RELATIONSHIP_MILESTONE_SAMPLE_NPCS

    def relationship_gain_cap_for_npc(self, npc_id: str) -> int:
        npc_id = str(npc_id)
        cap = RELATIONSHIP_MAX
        if not self.is_sample_milestone_npc(npc_id):
            return cap
        talks = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        if talks < 3:
            cap = min(cap, 59)
        if not self.has_relationship_milestone(npc_id, "close_friend"):
            cap = min(cap, 99)
        if not self.has_relationship_milestone(npc_id, "trusted"):
            cap = min(cap, 149)
        return cap

    def relationship_gate_hint_for_npc(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        if not self.is_sample_milestone_npc(npc_id):
            return ""
        talks = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        if talks < 3:
            return f"Needs more conversations before friendship can deepen ({talks}/3 talks)."
        if not self.has_relationship_milestone(npc_id, "close_friend"):
            return "Needs a personal moment before becoming a Close Friend."
        if not self.has_relationship_milestone(npc_id, "trusted"):
            return "Needs a trust moment before becoming Trusted."
        return "Major friendship gates cleared."

    def relationship_is_waiting_on_gate(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", ""))
        cap = self.relationship_gain_cap_for_npc(npc_id)
        return cap < RELATIONSHIP_MAX and self.town_npc_relationship(npc_id) >= cap

    def recent_gifts_for_npc(self, npc_id: str) -> List[Dict[str, object]]:
        if not isinstance(self.state.town_npc_recent_gifts, dict):
            self.state.town_npc_recent_gifts = {}
        npc_id = str(npc_id)
        gifts = self.state.town_npc_recent_gifts.get(npc_id, [])
        if not isinstance(gifts, list):
            gifts = []
        today = self.absolute_game_day()
        clean: List[Dict[str, object]] = []
        for gift in gifts:
            if not isinstance(gift, dict):
                continue
            try:
                day_number = int(gift.get("day_number", today))
            except Exception:
                day_number = today
            if today - day_number <= 7:
                clean.append({
                    "item": str(gift.get("item", "")),
                    "day": str(gift.get("day", "")),
                    "day_number": day_number,
                })
        self.state.town_npc_recent_gifts[npc_id] = clean[-10:]
        return self.state.town_npc_recent_gifts[npc_id]

    def remember_recent_gift_for_npc(self, npc_id: str, item: str):
        npc_id = str(npc_id)
        gifts = self.recent_gifts_for_npc(npc_id)
        gifts.append({
            "item": str(item),
            "day": self.town_npc_day_key(),
            "day_number": self.absolute_game_day(),
        })
        self.state.town_npc_recent_gifts[npc_id] = gifts[-10:]

    def repeated_gift_count_for_npc(self, npc_id: str, item: str) -> int:
        canonical_item = str(item)
        return sum(1 for gift in self.recent_gifts_for_npc(str(npc_id)) if str(gift.get("item", "")) == canonical_item)

    def apply_gift_fatigue(self, npc_id: str, item: str, amount: int, birthday: bool = False) -> Tuple[int, str]:
        if birthday or amount <= 0:
            return amount, ""
        repeats = self.repeated_gift_count_for_npc(npc_id, item)
        if repeats <= 0:
            return amount, ""
        if amount <= 2:
            return 1, "familiar gift"
        reduced = max(1, int(round(amount * 0.5)))
        return reduced, "familiar gift"

    def birthday_gift_bonus(self, base_amount: int) -> int:
        if base_amount >= 8:
            return 6
        if base_amount >= 4:
            return 4
        if base_amount > 0:
            return 2
        return 0

    def town_npc_friendship_label(self, points: int) -> str:
        if points >= 200:
            return "Deep Bond"
        if points >= 150:
            return "Trusted"
        if points >= 100:
            return "Close Friend"
        if points >= 60:
            return "Friend"
        if points >= 25:
            return "Acquaintance"
        if points >= 0:
            return "Stranger"
        return "Strained"

    def adjust_town_npc_relationship(self, npc_id: str, amount: int) -> int:
        current = self.town_npc_relationship(npc_id)
        amount = int(amount)
        target = current + amount
        if amount > 0:
            cap = self.relationship_gain_cap_for_npc(npc_id)
            if current >= cap:
                target = current
            else:
                target = min(target, cap)
        target = max(RELATIONSHIP_MIN, min(RELATIONSHIP_MAX, target))
        self.state.town_npc_relationships[npc_id] = target
        procedural = self.procedural_resident_by_id(str(npc_id))
        if procedural:
            procedural["relationship"] = target
        return target - current

    def best_gift_item_for_npc(self, npc: Dict[str, object]) -> Optional[str]:
        definition = self.town_npc_definition(str(npc.get("id", "")))
        likes = list(definition.get("likes", [])) if isinstance(definition, dict) else []
        fallback_items = [
            "Ancient Preserves", "Wildflower Honey", "Berry Jam", "Mushroom Preserve",
            "Wildflower", "Berries", "Bird Egg", "Duck Egg", "Milk",
            "Carrot", "Tomato", "Corn", "Watercress", "Cave Herbs",
        ]
        candidates = []
        for item in list(likes) + fallback_items + list(self.state.inventory.keys()):
            if item in candidates:
                continue
            if self.state.inventory.get(item, 0) <= 0:
                continue
            amount, reaction = self.gift_quality_for_npc(npc, item)
            if amount > 0:
                candidates.append((amount, reaction, item))
        if not candidates:
            return None
        candidates.sort(key=lambda row: (row[0], 1 if row[1] == "loved" else 0, row[2]), reverse=True)
        return candidates[0][2]

    def is_giftable_inventory_item(self, item_name: str) -> bool:
        if self.state.inventory.get(item_name, 0) <= 0:
            return False
        if item_name in INFRASTRUCTURE_DATA:
            return False
        if item_name.endswith(" Seeds"):
            return False
        return True

    def gift_reaction_label(self, amount: int, reaction: str) -> str:
        if reaction == "loved":
            return "loved"
        if amount < 0:
            return "disliked"
        if amount >= 8:
            return "liked"
        if amount >= 4:
            return "appreciated"
        return "neutral"

    def gift_menu_items_for_npc(self, npc: Dict[str, object]) -> List[MenuItem]:
        items: List[MenuItem] = []
        birthday_today = self.is_npc_birthday(npc)
        for item_name, qty in sorted(self.state.inventory.items()):
            if not self.is_giftable_inventory_item(item_name):
                continue
            amount, reaction = self.gift_quality_for_npc(npc, item_name)
            display_amount, fatigue_note = self.apply_gift_fatigue(str(npc.get("id", "")), item_name, amount, birthday=birthday_today)
            if birthday_today and amount > 0:
                display_amount += self.birthday_gift_bonus(amount)
            reaction_label = self.gift_reaction_label(amount, reaction)
            hint = f"x{qty}; {reaction_label}; relationship {display_amount:+}"
            if fatigue_note:
                hint = f"{fatigue_note}; {hint}"
            if birthday_today and amount > 0:
                hint = f"birthday; {hint}"
            items.append(MenuItem(
                label=item_name,
                value=item_name,
                enabled=True,
                hint=hint,
            ))
        return items

    def artisan_goods(self) -> List[str]:
        return [
            "Berry Jam",
            "Pickled Turnips",
            "Pickled Carrots",
            "Tomato Preserve",
            "Corn Relish",
            "Mushroom Preserve",
            "Wildflower Honey",
            "Ancient Preserves",
        ]

    def is_artisan_good(self, item_name: str) -> bool:
        return item_name in set(self.artisan_goods())

    def artisan_good_lines(self, item_name: str) -> List[str]:
        if not self.is_artisan_good(item_name):
            return []
        lines = [
            "Artisan good:",
            "Made with a Preserves Jar.",
            "Good for shipping, gifting, eating, and pantry recipes.",
        ]
        uses = self.ingredient_usage_lines(item_name)
        if uses:
            lines.extend(["", "Pantry recipe uses:"])
            lines.extend(uses)
        return lines

    def gift_quality_for_npc(self, npc: Dict[str, object], item: str) -> Tuple[int, str]:
        definition = self.town_npc_definition(str(npc.get("id", "")))
        likes = list(definition.get("likes", [])) if isinstance(definition, dict) else []
        dislikes = list(definition.get("dislikes", [])) if isinstance(definition, dict) else []
        try:
            canonical_item = self.canonical_item_name(item)
            canonical_likes = [self.canonical_item_name(name) for name in likes]
            canonical_dislikes = [self.canonical_item_name(name) for name in dislikes]
        except Exception:
            canonical_item = item
            canonical_likes = likes
            canonical_dislikes = dislikes
        if item in likes or canonical_item in canonical_likes:
            return 8, "loved"
        if item in dislikes or canonical_item in canonical_dislikes:
            return -5, "disliked"
        if self.is_artisan_good(item):
            return 5, "liked artisan gift"
        role = str(npc.get("role", "Villager"))
        role_affinity = {
            "Seed Seller": ["Seeds", "Turnip", "Carrot", "Tomato", "Corn", "Wildflower", "Watercress"],
            "Blacksmith": ["Ore", "Coal", "Bar", "Stone", "Crystal", "Quartz", "Amethyst", "Topaz"],
            "Miner": ["Ore", "Coal", "Bar", "Stone", "Crystal", "Quartz", "Amethyst", "Topaz"],
            "Carpenter": ["Wood", "Hardwood", "Fiber", "Stone Path", "Fence"],
            "Animal Keeper": ["Egg", "Milk", "Fiber", "Animal Medicine"],
            "Doctor": ["Cave Herbs", "Honey", "Watercress", "Animal Medicine", "Milk"],
            "Fisher": ["Minnow", "Sunfish", "Carp", "Chub", "Fish"],
            "Chef": ["Carrot", "Tomato", "Corn", "Turnip", "Salad", "Stew", "Jam", "Preserve"],
            "Innkeeper": ["Salad", "Egg", "Milk", "Berries", "Honey"],
            "Gardener": ["Wildflower", "Watercress", "Maple", "Lettuce"],
            "Artist": ["Wildflower", "Fiber", "Maple", "Honey"],
            "Recluse": ["Cave", "Spores", "Mushroom", "Chub"],
            "Orchardist": ["Maple", "Honey", "Jam", "Berries", "Wildflower", "Fruit"],
            "Tailor": ["Fiber", "Soft Fiber", "Wildflower", "Honey", "Maple"],
            "Musician": ["Jam", "Toast", "Honey", "Sunfish", "Wildflower"],
            "Beekeeper": ["Honey", "Wildflower", "Flowers", "Maple", "Jam"],
            "Botanist": ["Cave Herbs", "Spores", "Mushroom", "Watercress", "Wildflower"],
            "Mechanic": ["Bar", "Crystal", "Sprinkler", "Coal", "Ore", "Quartz"],
            "Scholar": ["Cave Herbs", "Maple", "Preserves", "Honey", "Quartz"],
            "Retiree": ["Toast", "Milk", "Berries", "Chub", "Maple"],
        }
        if any(token in item for token in role_affinity.get(role, [])):
            return 4, "appreciated role gift"
        if item in FOOD_DATA or item in FISH_DATA or item in RESOURCE_ITEMS:
            return 2, "accepted"
        return 1, "accepted"

    def give_selected_gift_to_town_npc(self, npc: Dict[str, object], item: str) -> bool:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        today = self.town_npc_day_key()
        if self.state.town_npc_last_gift_day.get(npc_id) == today:
            self.set_message(f"You already gave {npc.get('name', 'them')} a gift today.")
            return False
        if not self.is_giftable_inventory_item(item):
            self.set_message(f"You cannot give {item}.")
            return False
        self.state.inventory[item] -= 1
        amount, reaction = self.gift_quality_for_npc(npc, item)
        base_amount = amount
        gift_dialogue_category = self.gift_reaction_dialogue_category(base_amount, reaction)
        fatigue_note = ""
        birthday_today = self.is_npc_birthday(npc)
        amount, fatigue_note = self.apply_gift_fatigue(npc_id, item, amount, birthday=birthday_today)
        birthday_bonus = 0
        if birthday_today and base_amount > 0:
            birthday_bonus = self.birthday_gift_bonus(base_amount)
            amount += birthday_bonus
        actual_gain = self.adjust_town_npc_relationship(npc_id, amount)
        self.state.town_npc_last_gift_day[npc_id] = today
        self.state.town_npc_last_gift_reactions[npc_id] = {
            "day": today,
            "item": item,
            "reaction": reaction,
            "category": gift_dialogue_category,
            "relationship": int(actual_gain),
            "fatigue": fatigue_note,
        }
        self.remember_recent_gift_for_npc(npc_id, item)

        if reaction == "loved":
            response = f"{npc.get('name')} accepts {item} with a look that says you understood them exactly."
        elif reaction == "liked artisan gift":
            response = f"{npc.get('name')} studies the work on {item} and seems genuinely impressed."
        elif reaction == "appreciated role gift":
            response = f"{npc.get('name')} turns {item} over, already imagining where it fits into their work."
        elif reaction == "liked":
            response = f"{npc.get('name')} thanks you for {item}; it will not go to waste."
        elif reaction == "disliked":
            response = f"{npc.get('name')} accepts {item} politely, but the pause gives them away."
        else:
            response = f"{npc.get('name')} accepts {item} and tucks it away with a small thanks."
        if fatigue_note and actual_gain > 0:
            response += " The repeated gift feels familiar, so it means a little less this week."
        if birthday_bonus:
            response += " Remembering their birthday makes the gift mean more."
        gift_line = self.choose_npc_dialogue(npc, immediate_category=gift_dialogue_category).get("text", "")
        if gift_line:
            response += f' "{gift_line}"'
        if actual_gain > 0:
            gain_text = f" Relationship +{actual_gain}."
        elif actual_gain < 0:
            gain_text = f" Relationship {actual_gain}."
        else:
            gain_text = " Relationship unchanged."
        self.autosave_with_message(f"Gave {item} to {npc.get('name')}. {response}{gain_text}")
        return True

    def give_gift_to_town_npc(self, npc: Dict[str, object]) -> bool:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        if self.state.town_npc_last_gift_day.get(npc_id) == self.town_npc_day_key():
            self.set_message(f"You already gave {npc.get('name', 'them')} a gift today.")
            return False

        items = self.gift_menu_items_for_npc(npc)
        if not items:
            self.set_message("You are not carrying anything suitable to give.")
            return False
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))

        choice = self.vertical_panel_select(
            f"Gift to {npc.get('name', 'Villager')}",
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if choice is None or choice.value == MENU_BACK:
            self.set_message("Gift cancelled.")
            return False
        return self.give_selected_gift_to_town_npc(npc, str(choice.value))

    def town_npc_status_lines(self, npc: Dict[str, object]) -> List[str]:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        points = self.town_npc_relationship(npc_id)
        definition = self.town_npc_definition(npc_id)
        likes = ", ".join(definition.get("likes", [])[:5]) if isinstance(definition, dict) else "Unknown"
        dislikes = ", ".join(definition.get("dislikes", [])[:4]) if isinstance(definition, dict) else "Unknown"
        lines = [
            f"{npc.get('name')} - {npc.get('role')}",
            "",
            f"Friendship: {self.town_npc_friendship_label(points)} ({points})",
            f"Relationship tier: {self.relationship_tier_for_npc(npc)}",
            self.town_npc_relationship_note(npc),
            f"Milestone: {self.relationship_gate_hint_for_npc(npc)}" if self.relationship_gate_hint_for_npc(npc) else "Milestone: none",
            f"Sex: {self.npc_sex(npc)}",
            f"Birthday: {self.npc_birthday_label(npc)}",
            f"Mood: {self.town_npc_mood(npc)}",
            f"District: {npc.get('district')}",
            f"Home: {npc.get('home')}",
            f"Current location: {self.town_npc_location_label(npc)}",
            f"Routine: {self.town_npc_routine_brief(npc)}",
            self.town_npc_next_routine_line(npc),
            f"Times spoken to: {self.state.town_npc_dialogue_counts.get(npc_id, 0)}",
            "",
            f"Likes: {likes or 'Unknown'}",
            f"Dislikes: {dislikes or 'Unknown'}",
            "",
        ]
        if self.state.spouse_npc_id == npc_id:
            lines.insert(8, "Household: lives at the farmhouse" if self.state.spouse_moved_to_farm else "Household: can be invited to move onto the farm")
        lines.extend(self.town_npc_profile_lines(npc)[2:])
        lines.extend(["", "Tip:", "NPCs can be indoors during work hours or bad weather. Check the directory if someone is not visible outside."])
        return lines

    def town_npc_route_hint(self, npc: Dict[str, object]) -> str:
        if self.town_npc_is_indoor(npc):
            place = self.town_npc_indoor_location(npc)
            door_hints = {
                "Farmhouse": "Farmhouse: Use your farm door.",
                "General Store": "General Store: Use the North Market Street door at 10,8.",
                "Blacksmith": "Blacksmith: Use the North Market Street door at 25,8.",
                "Library": "Library: Use the North Market Street door at 41,8.",
                "Mayor's House": "Mayor's House: Use the Civic Boulevard door at 10,20.",
                "Inn": "Inn: Use the Civic Boulevard door at 25,20.",
                "Town Hall": "Town Hall: Use the Civic Boulevard door at 41,20.",
                "Furniture Store": "Furniture Store: Use the Civic Boulevard door at 57,20.",
                "Carpenter": "Carpenter: Use the Civic Boulevard door at 73,20.",
                "Animal Store": "Animal Store: Use the Civic Boulevard door at 89,20.",
                "Clinic": "Clinic: Use the South Civic Walk door at 10,32.",
                "Market Row": "Market Row: Use the market promenade door at 73,32.",
            }
            return door_hints.get(place, f"Look inside {place}.")
        ax, ay = self.town_npc_schedule_anchor(npc)
        if ay <= 13:
            district = "North Market Street"
        elif 14 <= ay <= 23:
            district = "Civic Boulevard"
        elif ax >= 92 and 24 <= ay <= 43:
            district = "East Commons"
        elif ay >= 44:
            district = "South Canal Walk"
        elif 24 <= ay <= 36 and 36 <= ax <= 68:
            district = "Central Park"
        elif ay >= 34:
            district = "South Civic Walk"
        elif ax >= 64:
            district = "Market Promenade"
        else:
            district = "grid road loop"
        return f"Look around the {district} near {ax},{ay}."

    def town_npc_whereabouts_lines(self, npc: Dict[str, object]) -> List[str]:
        npc_id = str(npc.get("id", ""))
        lines = [
            f"WHERE IS {str(npc.get('name', 'NPC')).upper()}?",
            "",
            f"Role: {npc.get('role')}",
            f"Friendship: {self.town_npc_friendship_label(self.town_npc_relationship(npc_id))} ({self.town_npc_relationship(npc_id)})",
            f"Mood: {self.town_npc_mood(npc)}",
            f"Current location: {self.town_npc_location_label(npc)}",
            f"Routine: {self.town_npc_routine_brief(npc)}",
            self.town_npc_next_routine_line(npc),
            "",
            "How to find them:",
            self.town_npc_route_hint(npc),
            "",
        ]
        if self.is_marriageable_npc(npc):
            lines.insert(4, f"Romance: {self.romance_label_for_npc(npc)}")
        if self.town_npc_is_indoor(npc):
            lines.append("They are currently indoors and will not appear on the outdoor town map.")
        else:
            ax, ay = self.town_npc_schedule_anchor(npc)
            lines.append(f"They should be visible outdoors near {ax},{ay}, unless they wander a few tiles away.")
        lines.extend([
            "",
            "Today's routine:",
        ])
        lines.extend(self.town_npc_routine_lines(npc))
        lines.extend([
            "",
            "Tip:",
            "NPC locations change with time of day and weather.",
        ])
        return lines

    def find_town_npc_menu(self):
        self.normalize_town_npcs()
        while True:
            items: List[MenuItem] = []
            for npc in self.active_town_npcs():
                npc_id = str(npc.get("id", ""))
                hint = f"{self.town_routine_phase_label(self.town_npc_current_routine_phase(npc))}; {self.town_npc_location_label(npc)}"
                friendship = self.town_npc_friendship_label(self.town_npc_relationship(npc_id))
                items.append(MenuItem(
                    label=f"{npc.get('name')} - {npc.get('role')}",
                    value=npc_id,
                    enabled=True,
                    hint=f"{friendship}; {self.romance_label_for_npc(npc)}; {hint}" if self.is_marriageable_npc(npc) else f"{friendship}; {hint}",
                ))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = self.vertical_panel_select("Find NPC", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message("Closed Find NPC.")
                return
            npc = next((n for n in self.active_town_npcs() if str(n.get("id", "")) == str(choice.value)), None)
            if npc:
                self.vertical_panel_view(f"Find {npc.get('name')}", self.town_npc_whereabouts_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue

    def town_npc_directory_lines(self) -> List[str]:
        self.normalize_town_npcs()
        active_npcs = self.active_town_npcs()
        inactive_count = len(self.inactive_town_npcs())
        lines = ["TOWN NPC DIRECTORY", "", f"Active residents: {len(active_npcs)}", f"Away until restoration: {inactive_count}", ""]
        for npc in active_npcs:
            npc_id = str(npc.get("id", ""))
            points = self.town_npc_relationship(npc_id)
            lines.append(f"{npc.get('name')} - {npc.get('role')}")
            lines.append(f"  {self.town_npc_friendship_label(points)} ({points}) | {self.town_npc_mood(npc)}")
            if self.is_marriageable_npc(npc):
                lines.append(f"  Romance: {self.romance_label_for_npc(npc)}")
            lines.append(f"  {self.town_npc_routine_brief(npc)}")
            lines.append(f"  {self.town_npc_location_label(npc)} | {self.town_npc_route_hint(npc)}")
        if inactive_count:
            lines.extend(["", "Later arrivals are tied to closed services such as the Clinic, Blacksmith, Library, Animal Store, and Market Row."])
        lines.extend(["", "Use Town Hall's Find NPC service for full daily schedules.", "NPCs can be outdoors, indoors, or sheltering from bad weather."])
        return lines

    def make_default_town_npcs(self) -> List[Dict[str, object]]:
        npcs: List[Dict[str, object]] = []
        for npc in TOWN_NPC_DEFINITIONS:
            birthday_month, birthday_day = NPC_BIRTHDAY_BY_ID.get(str(npc["id"]), (3, 1))
            npcs.append({
                "id": npc["id"],
                "name": npc["name"],
                "symbol": "@",
                "sex": NPC_SEX_BY_ID.get(str(npc["id"]), "Unknown"),
                "birthday_month": birthday_month,
                "birthday_day": birthday_day,
                "role": npc["role"],
                "home": npc["home"],
                "x": int(npc["x"]),
                "y": int(npc["y"]),
                "home_x": int(npc["x"]),
                "home_y": int(npc["y"]),
                "district": npc["district"],
                "wander_radius": int(npc["wander_radius"]),
                "current_anchor_x": int(npc["x"]),
                "current_anchor_y": int(npc["y"]),
                "indoors": False,
                "indoor_location": "",
                "facing": "DOWN",
                "activity": "",
                "routine_phase": "",
                "routine_label": "",
                "routine_day_key": "",
                "routine_weather": "",
                "steps_today": 0,
                "runtime_location": "",
                "runtime_target_location": "",
                "runtime_transition": "",
                "interior_x": 27,
                "interior_y": 18,
                "route_blocked": False,
                "social_partner_id": "",
                "social_activity": "",
                "social_day_key": "",
                "social_phase": "",
            })
        return npcs

    def normalize_town_npcs(self):
        if not isinstance(self.state.town_npcs, list) or not self.state.town_npcs:
            self.state.town_npcs = self.make_default_town_npcs()
        if not isinstance(self.state.town_npc_dialogue_counts, dict):
            self.state.town_npc_dialogue_counts = {}

        definitions = {npc["id"]: npc for npc in TOWN_NPC_DEFINITIONS}
        existing_ids = set()
        clean: List[Dict[str, object]] = []
        for npc in self.state.town_npcs:
            if not isinstance(npc, dict):
                continue
            npc_id = str(npc.get("id", ""))
            if npc_id not in definitions:
                continue
            base = definitions[npc_id]
            birthday_month, birthday_day = NPC_BIRTHDAY_BY_ID.get(npc_id, (3, 1))
            existing_ids.add(npc_id)
            try:
                x = int(npc.get("x", base["x"]))
                y = int(npc.get("y", base["y"]))
            except Exception:
                x, y = int(base["x"]), int(base["y"])
            if not (0 <= x < TOWN_WIDTH and 0 <= y < TOWN_HEIGHT):
                x, y = int(base["x"]), int(base["y"])
            if hasattr(self, "town_map") and 0 <= x < TOWN_WIDTH and 0 <= y < TOWN_HEIGHT:
                if self.town_map[y][x] not in [".", "=", ":", ","]:
                    x, y = self.nearest_town_passable_tile(int(base["x"]), int(base["y"]))
            npc.update({
                "id": npc_id,
                "name": str(npc.get("name", base["name"])),
                "symbol": "@",
                "sex": NPC_SEX_BY_ID.get(npc_id, "Unknown"),
                "birthday_month": birthday_month,
                "birthday_day": birthday_day,
                "role": str(npc.get("role", base["role"])),
                "home": str(npc.get("home", base["home"])),
                "x": x,
                "y": y,
                "home_x": int(npc.get("home_x", base["x"])),
                "home_y": int(npc.get("home_y", base["y"])),
                "district": str(npc.get("district", base["district"])),
                "wander_radius": int(npc.get("wander_radius", base["wander_radius"])),
                "current_anchor_x": int(npc.get("current_anchor_x", base["x"])),
                "current_anchor_y": int(npc.get("current_anchor_y", base["y"])),
                "indoors": bool(npc.get("indoors", False)),
                "indoor_location": str(npc.get("indoor_location", "")),
                "facing": str(npc.get("facing", "DOWN")),
                "activity": str(npc.get("activity", "")),
                "routine_phase": str(npc.get("routine_phase", "")),
                "routine_label": str(npc.get("routine_label", "")),
                "routine_day_key": str(npc.get("routine_day_key", "")),
                "routine_weather": str(npc.get("routine_weather", "")),
                "steps_today": int(npc.get("steps_today", 0)) if str(npc.get("steps_today", 0)).isdigit() else 0,
                "runtime_location": str(npc.get("runtime_location", "")),
                "runtime_target_location": str(npc.get("runtime_target_location", "")),
                "runtime_transition": str(npc.get("runtime_transition", "")),
                "interior_x": int(npc.get("interior_x", 27)),
                "interior_y": int(npc.get("interior_y", 18)),
                "route_blocked": bool(npc.get("route_blocked", False)),
                "social_partner_id": str(npc.get("social_partner_id", "")),
                "social_activity": str(npc.get("social_activity", "")),
                "social_day_key": str(npc.get("social_day_key", "")),
                "social_phase": str(npc.get("social_phase", "")),
            })
            clean.append(npc)
        for npc_id, base in definitions.items():
            if npc_id not in existing_ids:
                birthday_month, birthday_day = NPC_BIRTHDAY_BY_ID.get(npc_id, (3, 1))
                clean.append({
                    "id": base["id"], "name": base["name"], "symbol": "@",
                    "sex": NPC_SEX_BY_ID.get(str(base["id"]), "Unknown"),
                    "birthday_month": birthday_month, "birthday_day": birthday_day,
                    "role": base["role"], "home": base["home"],
                    "x": int(base["x"]), "y": int(base["y"]),
                    "home_x": int(base["x"]), "home_y": int(base["y"]),
                    "district": base["district"], "wander_radius": int(base["wander_radius"]),
                    "current_anchor_x": int(base["x"]), "current_anchor_y": int(base["y"]),
                    "indoors": False, "indoor_location": "",
                    "facing": "DOWN",
                    "activity": "",
                    "routine_phase": "",
                    "routine_label": "",
                    "routine_day_key": "",
                    "routine_weather": "",
                    "steps_today": 0,
                    "runtime_location": "",
                    "runtime_target_location": "",
                    "runtime_transition": "",
                    "interior_x": 27,
                    "interior_y": 18,
                    "route_blocked": False,
                    "social_partner_id": "",
                    "social_activity": "",
                    "social_day_key": "",
                    "social_phase": "",
                })
        self.state.town_npcs = clean
        if not isinstance(self.state.town_npc_relationships, dict):
            self.state.town_npc_relationships = {}
        if not isinstance(self.state.town_npc_last_talk_day, dict):
            self.state.town_npc_last_talk_day = {}
        if not isinstance(self.state.town_npc_last_gift_day, dict):
            self.state.town_npc_last_gift_day = {}
        if not isinstance(self.state.town_npc_last_gift_reactions, dict):
            self.state.town_npc_last_gift_reactions = {}
        if not isinstance(self.state.town_npc_recent_gifts, dict):
            self.state.town_npc_recent_gifts = {}
        if not isinstance(self.state.town_npc_last_court_day, dict):
            self.state.town_npc_last_court_day = {}
        if not isinstance(self.state.town_npc_courtship_counts, dict):
            self.state.town_npc_courtship_counts = {}
        if not isinstance(self.state.town_npc_relationship_milestones, dict):
            self.state.town_npc_relationship_milestones = {}
        if not isinstance(self.state.town_npc_recent_dialogue_ids, dict):
            self.state.town_npc_recent_dialogue_ids = {}
        if not isinstance(self.state.town_npc_last_proposal_day, dict):
            self.state.town_npc_last_proposal_day = {}
        if not isinstance(self.state.dating_npc_ids, list):
            self.state.dating_npc_ids = []
        self.state.dating_npc_ids = [
            str(npc_id)
            for npc_id in self.state.dating_npc_ids
            if (
                str(npc_id) in definitions
                or self.procedural_resident_by_id(str(npc_id)) is not None
            )
        ]
        if (
            str(self.state.spouse_npc_id or "")
            and str(self.state.spouse_npc_id or "") not in definitions
            and self.procedural_resident_by_id(
                str(self.state.spouse_npc_id or "")
            )
            is None
        ):
            self.state.spouse_npc_id = ""
            self.state.spouse_moved_to_farm = False
        if (
            str(getattr(self.state, "engaged_npc_id", "") or "")
            and str(self.state.engaged_npc_id) not in definitions
            and self.procedural_resident_by_id(
                str(self.state.engaged_npc_id)
            )
            is None
        ):
            self.state.engaged_npc_id = ""
            self.state.wedding_month = 0
            self.state.wedding_day = 0
            self.state.wedding_year = 0
        for npc in self.state.town_npcs:
            npc_id = str(npc.get("id", ""))
            self.state.town_npc_relationships.setdefault(npc_id, 0)
            try:
                self.state.town_npc_courtship_counts[npc_id] = max(0, int(self.state.town_npc_courtship_counts.get(npc_id, 0)))
            except Exception:
                self.state.town_npc_courtship_counts[npc_id] = 0
            recent = self.state.town_npc_recent_dialogue_ids.get(npc_id, [])
            if not isinstance(recent, list):
                recent = []
            self.state.town_npc_recent_dialogue_ids[npc_id] = [str(line_id) for line_id in recent[-8:] if line_id is not None]
            reaction = self.state.town_npc_last_gift_reactions.get(npc_id, {})
            if not isinstance(reaction, dict):
                reaction = {}
            if reaction and str(reaction.get("day", "")) != self.town_npc_day_key():
                reaction = {}
            self.state.town_npc_last_gift_reactions[npc_id] = reaction
            gifts = self.state.town_npc_recent_gifts.get(npc_id, [])
            if not isinstance(gifts, list):
                gifts = []
            clean_gifts: List[Dict[str, object]] = []
            today_number = self.absolute_game_day()
            for gift in gifts:
                if not isinstance(gift, dict):
                    continue
                try:
                    day_number = int(gift.get("day_number", today_number))
                except Exception:
                    day_number = today_number
                if today_number - day_number > 7:
                    continue
                clean_gifts.append({
                    "item": str(gift.get("item", "")),
                    "day": str(gift.get("day", "")),
                    "day_number": day_number,
                })
            self.state.town_npc_recent_gifts[npc_id] = clean_gifts[-10:]
            milestones = self.state.town_npc_relationship_milestones.get(npc_id, [])
            if not isinstance(milestones, list):
                milestones = []
            self.state.town_npc_relationship_milestones[npc_id] = sorted({str(flag) for flag in milestones if flag is not None})

    def town_interior_location_for_name(self, name: str) -> str:
        return TOWN_INTERIOR_LOCATION_BY_NAME.get(str(name or "").strip().lower(), "")

    def current_town_interior_name(self) -> str:
        return TOWN_INTERIOR_NAME_BY_LOCATION.get(self.state.location, self.location_label())

    def town_npc_indoor_state(self, npc: Dict[str, object]) -> str:
        location = self.town_npc_actual_location(npc)
        if self.town_npc_residence_id_from_runtime(location):
            return "TownResidenceInterior"
        if location in {"HouseInterior", *AUTHORED_TOWN_INTERIOR_MAP_ATTRS.keys()}:
            return location
        return ""

    def town_npc_matches_current_interior(self, npc: Dict[str, object]) -> bool:
        location = self.town_npc_actual_location(npc)
        if self.state.location == "TownResidenceInterior":
            return self.town_npc_residence_id_from_runtime(location) == str(
                getattr(self.state, "current_authored_residence_id", "")
            )
        return self.town_npc_indoor_state(npc) == self.state.location

    def town_npc_observed_runtime_location(self) -> str:
        if self.state.location == "TownResidenceInterior":
            return self.town_npc_residence_runtime_location(
                str(getattr(self.state, "current_authored_residence_id", ""))
            )
        return str(self.state.location)

    def is_household_child_npc(self, npc: Dict[str, object]) -> bool:
        return str(npc.get("id", "")).startswith("household_child:")

    def child_record_from_npc(self, npc: Dict[str, object]) -> Optional[Dict[str, object]]:
        npc_id = str(npc.get("id", ""))
        if not npc_id.startswith("household_child:"):
            return None
        child_id_text = npc_id.split(":", 1)[1]
        for child in self.state.children:
            if str(child.get("id", "")) == child_id_text:
                return child
        return None

    def spouse_farmhouse_position(self) -> Tuple[int, int]:
        min_x, min_y, max_x, max_y = self.house_floor_bounds()
        center_x = (min_x + max_x) // 2
        phase = self.town_routine_phase()
        if phase == "wake":
            preferred = [(min_x + 6, min_y + 2), (min_x + 9, min_y + 3), (center_x, min_y + 4)]
        elif phase == "lunch":
            preferred = [(center_x + 1, min_y + 7), (max_x - 8, min_y + 4), (center_x, max_y - 5)]
        elif phase == "work_afternoon":
            preferred = [(min_x + 5, max_y - 4), (max_x - 6, min_y + 4), (center_x, max_y - 5)]
        elif phase == "evening":
            preferred = [(center_x - 2, max_y - 5), (max_x - 4, max_y - 4), (center_x + 2, max_y - 4)]
        elif phase == "late":
            preferred = [(min_x + 6, min_y + 2), (min_x + 9, min_y + 3), (center_x, min_y + 4)]
        else:
            preferred = [
                (min_x + 9, min_y + 3),
                (max_x - 5, min_y + 4),
                (center_x, min_y + 7),
                (max_x - 4, max_y - 4),
            ]
        for x, y in preferred:
            if self.in_house_bounds_for_npc(x, y):
                return x, y
        return min_x + 1, min_y + 1

    def spouse_household_activity_label(self, npc: Dict[str, object]) -> str:
        mode = self.spouse_support_mode().lower()
        home = (
            self.household_residence_label()
            if hasattr(self, "household_residence_label")
            else "the farmhouse"
        )
        if self.state.pregnancy_active:
            if self.state.pregnancy_gestational_parent == "spouse" and self.state.pregnancy_parent_npc_id == str(npc.get("id", "")):
                return f"moving carefully through pregnancy month {self.pregnancy_month_number()} with a {mode} household focus"
            return f"preparing {home} for pregnancy month {self.pregnancy_month_number()} with a {mode} household focus"
        if self.state.children:
            youngest = min(self.state.children, key=lambda child: self.household_child_age_months(child))
            return f"keeping an eye on {youngest.get('name', 'the child')} and the household's {mode} focus"
        phase = self.town_routine_phase()
        return {
            "wake": f"starting the morning in {home}",
            "work_morning": "checking household chores before town errands",
            "lunch": f"setting out a simple meal in {home}",
            "work_afternoon": f"using the desk in {home} for shared plans",
            "evening": f"winding down in {home}",
            "late": "getting ready for sleep",
            "bad_weather": f"keeping close to {home} during bad weather",
        }.get(phase, f"settling into life in {home}")

    def in_house_bounds_for_npc(self, x: int, y: int) -> bool:
        if not (0 <= y < len(self.house_map) and 0 <= x < len(self.house_map[y])):
            return False
        if self.house_map[y][x] not in self.house_floor_tiles():
            return False
        if x == self.state.player_x and y == self.state.player_y:
            return False
        for key, obj_name in self.state.placed_objects.items():
            parsed = self.parse_object_key(str(key))
            if not parsed:
                continue
            location, ax, ay = parsed
            if location == "HouseInterior" and (x, y) in self.object_footprint_tiles(str(obj_name), ax, ay):
                return False
        return True

    def household_child_positions(self) -> Dict[int, Tuple[int, int]]:
        min_x, min_y, max_x, max_y = self.house_floor_bounds()
        center_x = (min_x + max_x) // 2
        preferred = [
            (min_x + 3, min_y + 5),
            (min_x + 5, min_y + 5),
            (min_x + 7, min_y + 6),
            (center_x - 2, max_y - 4),
            (center_x + 2, max_y - 4),
            (max_x - 6, max_y - 5),
            (max_x - 4, max_y - 3),
            (min_x + 4, max_y - 3),
        ]
        used = set()
        if self.spouse_lives_on_farm():
            used.add(self.spouse_farmhouse_position())
        positions: Dict[int, Tuple[int, int]] = {}

        for child in self.state.children:
            try:
                child_id = int(child.get("id", 0))
            except Exception:
                continue
            assigned: Optional[Tuple[int, int]] = None
            for x, y in preferred:
                if (x, y) in used:
                    continue
                if self.in_house_bounds_for_npc(x, y):
                    assigned = (x, y)
                    break
            if assigned is None:
                for y in range(min_y, max_y + 1):
                    for x in range(min_x, max_x + 1):
                        if (x, y) in used:
                            continue
                        if self.in_house_bounds_for_npc(x, y):
                            assigned = (x, y)
                            break
                    if assigned is not None:
                        break
            if assigned is None:
                assigned = (min_x, min_y)
            positions[child_id] = assigned
            used.add(assigned)
        return positions

    def household_child_npcs(self) -> List[Dict[str, object]]:
        positions = self.household_child_positions()
        npcs: List[Dict[str, object]] = []
        for child in self.state.children:
            try:
                child_id = int(child.get("id", 0))
            except Exception:
                continue
            x, y = positions.get(child_id, self.spouse_farmhouse_position())
            stage = self.household_child_stage(child)
            npcs.append({
                "id": f"household_child:{child_id}",
                "name": str(child.get("name", f"Child {child_id}")),
                "symbol": "@",
                "sex": str(child.get("sex", "Unknown")),
                "role": stage,
                "home": "Farmhouse",
                "x": x,
                "y": y,
                "district": "Farmhouse",
                "facing": "DOWN",
                "activity": self.household_child_activity_label(child),
            })
        return npcs

    def household_child_talk_lines(self, child: Dict[str, object], topic: str = "feelings") -> List[str]:
        stage = self.household_child_stage(child)
        name = str(child.get("name", "Your child"))
        profile = self.ensure_child_profile_fields(child)
        personality = str(profile.get("personality_trait", "Curious"))
        activity = self.household_child_activity_label(child)
        top_topic, top_points = self.child_top_learning_topic(child)
        chore = self.child_chore_assignment(child)
        lines = [f"{name} is {activity}.", ""]
        if self.is_child_birthday(child):
            lines.extend([f"Today is {name}'s birthday, and they keep noticing every sign that the household remembered.", ""])
        if stage == "Newborn":
            lines.append(f"{name} settles at the sound of your voice, one small hand relaxing against the blanket.")
        elif stage == "Infant":
            lines.append(f'"Ba," {name} answers seriously, then points toward whatever currently holds their whole attention.')
        elif stage == "Toddler":
            toddler_lines = {
                "learning": f'"I know {str(top_topic or "things").lower()}," {name} announces, with the confidence of somebody still assembling the explanation.',
                "chores": f'"I help {str(chore or "at home").lower()}," {name} says. The scale of that help remains open to interpretation.',
                "family": f'"Everybody home?" {name} asks, looking past you for the rest of the household.',
                "activity": f'"I doing {activity.replace("their ", "my ")}," {name} reports.',
            }
            lines.append(toddler_lines.get(topic, f'"Stay here," {name} says, apparently deciding that your company is the answer.'))
        elif stage == "Young Child":
            young_lines = {
                "learning": f'"Can you show me more about {str(top_topic or "the farm").lower()}? I want to know why it works, not just the rule."',
                "chores": f'"I can do {str(chore or "a real chore").lower()} by myself. Mostly by myself. You can stand nearby."',
                "family": '"Can we all do something together soon? Not an errand that adults secretly call an outing."',
                "activity": f'"I was {activity.replace("their ", "my ")}, but I made a better story for what was happening."',
            }
            lines.append(young_lines.get(topic, f'"Do you have time to listen all the way to the end?" {name} asks.'))
        elif stage == "Child":
            child_lines = {
                "learning": f'"I think {str(top_topic or "learning").lower()} might be the thing I am best at, but I want to try it somewhere outside the house too."',
                "chores": f'"I understand why {str(chore or "chores").lower()} matters. I just think knowing why should count for part of the work."',
                "family": '"Everyone has a schedule now. Could we put something on the calendar that belongs to all of us?"',
                "activity": f'"I was {activity.replace("their ", "my ")}. There is more to it than it looks like."',
            }
            lines.append(child_lines.get(topic, f'"Can I tell you something without it turning into a lesson?" {name} asks.'))
        elif stage == "Teen":
            teen_lines = {
                "learning": f'"I keep coming back to {str(top_topic or "what I want to learn").lower()}. I would rather get good enough to use it than collect another beginner lesson."',
                "chores": f'"If {str(chore or "household work").lower()} is my responsibility, let me decide how to fit it around the rest of my day."',
                "family": '"I still want family time. I just do not want every family plan chosen as if I were six."',
                "activity": f'"I was {activity.replace("their ", "my ")}. I am trying to have a life outside this room, you know."',
            }
            lines.append(teen_lines.get(topic, f'"I do want your opinion," {name} says, "but let me finish before you give it."'))
        else:
            adult_lines = {
                "learning": f'"What I learned about {str(top_topic or "the world").lower()} here is becoming part of the path I choose next."',
                "chores": f'"Doing {str(chore or "household work").lower()} taught me more about reliability than the task itself."',
                "family": '"I am building my own direction, but I do not want independence to mean becoming a stranger to this household."',
                "activity": f'"I was {activity.replace("their ", "my ")}. It feels good to choose how I contribute now."',
            }
            lines.append(adult_lines.get(topic, f'"I have been thinking about what comes next," {name} says. "I wanted you to know before it became a decision."'))
        lines.extend([
            "",
            f"Personality: {personality}",
            f"Bond: {self.child_affection_rank(child)}",
            f"Current focus: {top_topic if top_topic else 'discovering what interests them'}{f' ({top_points})' if top_topic else ''}",
        ])
        return lines

    def household_child_menu(self, npc: Dict[str, object]):
        child = self.child_record_from_npc(npc)
        if not child:
            self.set_message("The household record for this child is missing.")
            return
        while True:
            items = [
                MenuItem(label="Check In", value="talk", enabled=True),
                MenuItem(label="Status", value="status", enabled=True, hint=self.household_child_stage(child)),
                MenuItem(label="Traits", value="traits", enabled=True, hint=str(self.ensure_child_profile_fields(child).get("personality_trait", ""))),
                MenuItem(label="Give Gift", value="gift", enabled=True, hint=str(child.get("favorite_gift", "favorite"))),
                MenuItem(label="Lesson", value="lesson", enabled=True, hint="daily"),
                MenuItem(label="Chore", value="chore", enabled=True, hint=self.child_chore_assignment(child)),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = self.vertical_panel_select(str(child.get("name", "Child")), items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message(f"Stopped checking on {child.get('name', 'the child')}.")
                return
            if choice.value == "talk":
                topic_items = [
                    MenuItem(label="Ask How They're Feeling", value="feelings", enabled=True, hint=self.child_affection_rank(child)),
                    MenuItem(label="Ask What They're Doing", value="activity", enabled=True, hint=self.household_child_activity_label(child)),
                    MenuItem(label="Ask What They're Learning", value="learning", enabled=True, hint=self.child_top_learning_topic(child)[0] or "No focus yet"),
                    MenuItem(label="Ask About Their Chore", value="chores", enabled=True, hint=self.child_chore_assignment(child)),
                    MenuItem(label="Ask About the Family", value="family", enabled=True, hint="Home, outings, and time together"),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ]
                topic_choice = self.vertical_panel_select(
                    f"Talk with {child.get('name', 'Child')}",
                    topic_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if not topic_choice or topic_choice.value == MENU_BACK:
                    continue
                self.vertical_panel_view(
                    str(child.get("name", "Child")),
                    self.household_child_talk_lines(child, str(topic_choice.value)),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                today = self.town_npc_day_key()
                influence_available = str(child.get("last_conversation_day", "")) != today
                child_npc = {
                    "name": str(child.get("name", "Child")),
                    "role": self.household_child_stage(child),
                    "personality": str(self.ensure_child_profile_fields(child).get("personality_trait", "Curious")),
                }
                response = self.npc_dialogue_response_choice(
                    child_npc,
                    influence_available=influence_available,
                    title=f"Respond to {child.get('name', 'Them')}",
                )
                response_effect = int(response.get("effect", 0) or 0) if influence_available else 0
                total_gain = 0
                if influence_available:
                    child["last_conversation_day"] = today
                    total_gain += self.adjust_child_affection(child, 1)
                    total_gain += self.adjust_child_affection(child, response_effect)
                self.vertical_panel_view(
                    str(child.get("name", "Child")),
                    [
                        str(response.get("reaction", "The moment settles into the household's day.")),
                        "",
                        f"Bond influence: {total_gain:+}"
                        if influence_available and total_gain
                        else "You already made time for a meaningful check-in today."
                        if not influence_available
                        else "No bond change.",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                self.autosave_with_message(
                    f"Checked in on {child.get('name', 'the child')}."
                    + (f" Bond {total_gain:+}." if total_gain else "")
                )
                return
            if choice.value == "status":
                self.vertical_panel_view(str(child.get("name", "Child")), self.household_child_status_lines(child), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "traits":
                child = self.ensure_child_profile_fields(child)
                rows = [
                    f"{child.get('name', 'Child')} Traits",
                    "",
                    f"Trait: {child.get('personality_trait', 'Curious')}",
                    f"Favorite gift: {child.get('favorite_gift', 'Wildflower')}",
                    f"Possible path: {child.get('apprentice_path', 'Helper')}",
                    f"Starting class: {child.get('starting_class', 'Vanguard')}",
                    f"Affection: {self.child_affection_rank(child)} ({self.child_affection_score(child)})",
                    "",
                    self.child_trait_note(child),
                    "",
                    f"Current chore: {self.child_chore_assignment(child)}",
                ]
                self.vertical_panel_view(str(child.get("name", "Child")), rows, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "gift":
                if self.child_gift_menu(child):
                    return
                continue
            if choice.value == "lesson":
                if self.child_lesson_menu(child):
                    return
                continue
            if choice.value == "chore":
                if self.child_chore_menu(child):
                    return
                continue

    def authored_town_interior_grid(self, location: str) -> List[List[str]]:
        residence_id = self.town_npc_residence_id_from_runtime(location)
        if residence_id:
            return self.authored_town_residence_map(residence_id)
        map_attr = AUTHORED_TOWN_INTERIOR_MAP_ATTRS.get(str(location), "")
        grid = getattr(self, map_attr, None) if map_attr else None
        return grid if isinstance(grid, list) else []

    def authored_town_interior_passable(self, location: str, x: int, y: int) -> bool:
        grid = self.authored_town_interior_grid(location)
        return bool(
            0 <= y < len(grid)
            and 0 <= x < len(grid[y])
            and grid[y][x] in {".", ":", ",", "D"}
        )

    def town_npc_nearest_interior_tile(
        self,
        location: str,
        x: int,
        y: int,
        used: Optional[set] = None,
        radius_limit: int = 10,
    ) -> Tuple[int, int]:
        used = used or set()
        for radius in range(0, radius_limit + 1):
            candidates = [(x, y)] if radius == 0 else []
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) == radius:
                        candidates.append((x + dx, y + dy))
            for tx, ty in candidates:
                if (tx, ty) in used:
                    continue
                if self.authored_town_interior_passable(location, tx, ty):
                    return tx, ty
        return 27, 18

    def town_npc_fixture_approaches(self, location: str, symbols: set) -> List[Tuple[int, int]]:
        grid = self.authored_town_interior_grid(location)
        approaches: List[Tuple[int, int]] = []
        for y, row in enumerate(grid):
            for x, tile in enumerate(row):
                if tile not in symbols:
                    continue
                for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    point = (x + dx, y + dy)
                    if self.authored_town_interior_passable(location, *point) and point not in approaches:
                        approaches.append(point)
        return approaches

    def town_npc_fixture_room_anchors(self, location: str, symbols: set) -> List[Tuple[int, int]]:
        """Choose one walkable anchor per fixture, preserving separate rooms."""
        grid = self.authored_town_interior_grid(location)
        anchors: List[Tuple[int, int]] = []
        for y, row in enumerate(grid):
            for x, tile in enumerate(row):
                if tile not in symbols:
                    continue
                for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)):
                    point = (x + dx, y + dy)
                    if self.authored_town_interior_passable(location, *point):
                        anchors.append(point)
                        break
        return anchors

    def town_npc_interior_anchor(self, npc: Dict[str, object], location: str) -> Tuple[int, int]:
        phase = self.town_npc_current_routine_phase(npc)
        npc_id = str(npc.get("id", ""))
        occupants = sorted(
            str(other.get("id", ""))
            for other in getattr(self.state, "town_npcs", [])
            if isinstance(other, dict) and self.town_npc_actual_location(other) == location
        )
        occupant_index = occupants.index(npc_id) if npc_id in occupants else 0

        if phase in {"wake", "late"}:
            bed_approaches = self.town_npc_fixture_room_anchors(location, {"B"})
            if bed_approaches:
                return bed_approaches[occupant_index % len(bed_approaches)]

        if self.town_npc_residence_id_from_runtime(location) and phase in {"evening", "bad_weather"}:
            shared_room = self.town_npc_fixture_approaches(location, {"t", "k"})
            if shared_room:
                return shared_room[occupant_index % len(shared_room)]

        service = AUTHORED_TOWN_SERVICE_SPECS.get(npc_id)
        if service and service[0] == location:
            approaches = self.town_npc_fixture_approaches(location, {"&"})
            if approaches:
                return approaches[0]

        if npc_id == "chef_basil" and location == "InnInterior":
            kitchen = self.town_npc_fixture_approaches(location, {"k", "p"})
            if kitchen:
                return kitchen[0]

        preferred = self.indoor_npc_base_position(location)
        return self.town_npc_nearest_interior_tile(location, preferred[0], preferred[1])

    def town_npc_path_step(
        self,
        start: Tuple[int, int],
        target: Tuple[int, int],
        passable,
        max_nodes: int = 1800,
    ) -> Optional[Tuple[int, int]]:
        if start == target:
            return start
        frontier = [(abs(start[0] - target[0]) + abs(start[1] - target[1]), 0, start)]
        previous = {start: None}
        costs = {start: 0}
        while frontier and len(previous) <= max_nodes:
            _priority, cost, current = heapq.heappop(frontier)
            if cost != costs.get(current):
                continue
            x, y = current
            options = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
            options.sort(key=lambda point: abs(point[0] - target[0]) + abs(point[1] - target[1]))
            for point in options:
                if not passable(*point):
                    continue
                next_cost = cost + 1
                if next_cost >= costs.get(point, 10 ** 9):
                    continue
                costs[point] = next_cost
                previous[point] = current
                if point == target:
                    cursor = point
                    while previous.get(cursor) not in {None, start}:
                        cursor = previous[cursor]
                    return cursor
                heuristic = abs(point[0] - target[0]) + abs(point[1] - target[1])
                heapq.heappush(frontier, (next_cost + heuristic, next_cost, point))
        return None

    def town_npc_set_facing_for_step(self, npc: Dict[str, object], old: Tuple[int, int], new: Tuple[int, int]):
        dx, dy = new[0] - old[0], new[1] - old[1]
        if dx > 0:
            npc["facing"] = "RIGHT"
        elif dx < 0:
            npc["facing"] = "LEFT"
        elif dy > 0:
            npc["facing"] = "DOWN"
        elif dy < 0:
            npc["facing"] = "UP"

    def indoor_npc_base_position(self, location: str) -> Tuple[int, int]:
        if self.town_routine_phase() in ["wake", "late"]:
            return {
                "HouseInterior": self.spouse_farmhouse_position(),
                "GeneralStoreInterior": (27, 9),
                "BlacksmithInterior": (27, 9),
                "LibraryInterior": (27, 9),
                "MayorHouseInterior": (27, 9),
                "InnInterior": (27, 9),
                "FurnitureStoreInterior": (27, 9),
                "CarpenterStoreInterior": (27, 9),
                "AnimalStoreInterior": (27, 9),
                "ClinicInterior": (27, 9),
                "TownHallInterior": (27, 9),
                "MarketRowInterior": (27, 9),
                "MuseumInterior": (27, 9),
            }.get(location, (27, 9))
        return {
            "HouseInterior": self.spouse_farmhouse_position(),
            "GeneralStoreInterior": (27, 8),
            "BlacksmithInterior": (27, 8),
            "LibraryInterior": (27, 9),
            "MayorHouseInterior": (27, 10),
            "InnInterior": (24, 9),
            "FurnitureStoreInterior": (27, 9),
            "CarpenterStoreInterior": (27, 9),
            "AnimalStoreInterior": (27, 9),
            "ClinicInterior": (27, 9),
            "TownHallInterior": (27, 9),
            "MarketRowInterior": (27, 12),
            "MuseumInterior": (27, 9),
        }.get(location, (27, 9))

    def town_indoor_npc_positions(self, normalize: bool = True) -> Dict[str, Tuple[int, int]]:
        if not self.on_town_interior():
            return {}
        if normalize:
            self.normalize_town_npcs()
        npcs = [
            npc for npc in self.active_town_npcs()
            if self.town_npc_is_indoor(npc) and self.town_npc_matches_current_interior(npc)
        ]
        npcs.sort(key=lambda npc: str(npc.get("id", "")))
        positions: Dict[str, Tuple[int, int]] = {}
        used = set()
        interior_location = self.town_npc_observed_runtime_location()

        for npc in npcs:
            npc_id = str(npc.get("id", ""))
            current = (int(npc.get("interior_x", 27)), int(npc.get("interior_y", 18)))
            if (
                current in used
                or current == (self.state.player_x, self.state.player_y)
                or not self.authored_town_interior_passable(interior_location, *current)
            ):
                anchor = self.town_npc_interior_anchor(npc, interior_location)
                current = self.town_npc_nearest_interior_tile(
                    interior_location,
                    anchor[0],
                    anchor[1],
                    used | {(self.state.player_x, self.state.player_y)},
                )
                npc["interior_x"], npc["interior_y"] = current
            positions[npc_id] = current
            used.add(current)
        return positions

    def town_npc_position_lookup(self) -> Dict[Tuple[int, int], Dict[str, object]]:
        if (
            hasattr(self, "procedural_town_resident_position_lookup")
            and (
                (hasattr(self, "on_wilderness") and self.on_wilderness())
                or (
                    hasattr(self, "on_procedural_town_interior")
                    and self.on_procedural_town_interior()
                )
            )
        ):
            procedural_lookup = self.procedural_town_resident_position_lookup()
            if procedural_lookup:
                return procedural_lookup
        if self.on_farm() or self.on_mine():
            return self.home_region_destination_npc_positions()
        if not (self.on_town() or self.on_town_interior() or self.on_house()):
            return {}
        self.normalize_town_npcs()
        lookup: Dict[Tuple[int, int], Dict[str, object]] = {}

        if self.on_house():
            if self.spouse_lives_on_farm():
                spouse = self.npc_record_by_id(self.state.spouse_npc_id)
                if spouse and not self.travel_follower_identity_for_npc_id(str(spouse.get("id", ""))):
                    lookup[self.spouse_farmhouse_position()] = spouse
            for child_npc in self.household_child_npcs():
                try:
                    if self.travel_follower_identity_for_npc_id(str(child_npc.get("id", ""))):
                        continue
                    lookup[(int(child_npc.get("x", 0)), int(child_npc.get("y", 0)))] = child_npc
                except Exception:
                    continue
            if hasattr(self, "dynasty_elder_npcs"):
                for elder in self.dynasty_elder_npcs():
                    position = (
                        int(elder.get("x", 12)),
                        int(elder.get("y", 9)),
                    )
                    if position in lookup:
                        position = (
                            min(34, position[0] + 2),
                            min(16, position[1] + 1),
                        )
                    lookup[position] = elder
            if hasattr(self, "dynasty_kin_npcs"):
                for relative in self.dynasty_kin_npcs():
                    position = (
                        int(relative.get("x", 18)),
                        int(relative.get("y", 9)),
                    )
                    while position in lookup:
                        position = (
                            min(34, position[0] + 1),
                            min(16, position[1] + 1),
                        )
                    lookup[position] = relative
            return lookup

        if self.on_town_interior():
            positions = self.town_indoor_npc_positions(normalize=False)
            for npc in self.active_town_npcs():
                npc_id = str(npc.get("id", ""))
                if self.travel_follower_identity_for_npc_id(npc_id):
                    continue
                position = positions.get(npc_id)
                if position:
                    lookup[position] = npc
            for position, visitor in self.regional_visitor_position_lookup().items():
                if position not in lookup:
                    lookup[position] = visitor
            return lookup

        for npc in self.active_town_npcs():
            if self.travel_follower_identity_for_npc_id(str(npc.get("id", ""))):
                continue
            if self.town_npc_is_indoor(npc):
                continue
            try:
                lookup[(int(npc.get("x", -1)), int(npc.get("y", -1)))] = npc
            except Exception:
                continue
        for position, visitor in self.regional_visitor_position_lookup().items():
            if position not in lookup:
                lookup[position] = visitor
        return lookup

    def town_npc_at(self, x: int, y: int) -> Optional[Dict[str, object]]:
        return self.town_npc_position_lookup().get((int(x), int(y)))

    def render_town_npc(self, npc: Dict[str, object]) -> str:
        if npc.get("procedural_caravan"):
            symbol, color = actor_style("visitor", "C", "Traveling Merchant", detailed=bool(getattr(self.state, "detailed_glyphs_enabled", True)), high_contrast=bool(getattr(self.state, "high_contrast_enabled", False)))
            return colorize(symbol, color)
        if npc.get("regional_visitor"):
            symbol, color = actor_style("visitor", "@", str(npc.get("role", "Traveler")), high_contrast=bool(getattr(self.state, "high_contrast_enabled", False)))
            return colorize(symbol, color)
        symbol, color = actor_style("npc", "@", str(npc.get("role", "Villager")), self.town_npc_role_color(npc), high_contrast=bool(getattr(self.state, "high_contrast_enabled", False)))
        return colorize(symbol, color)

    def town_npc_passable_tile(self, x: int, y: int, ignore_npc_id: Optional[str] = None) -> bool:
        if not self.on_town():
            return False
        if not self.in_active_bounds(x, y):
            return False
        if x == self.state.player_x and y == self.state.player_y:
            return False
        if self.travel_follower_at(x, y):
            return False
        for other in self.active_town_npcs():
            if str(other.get("id", "")) == str(ignore_npc_id or ""):
                continue
            if self.travel_follower_identity_for_npc_id(str(other.get("id", ""))):
                continue
            if self.town_npc_is_indoor(other):
                continue
            try:
                if int(other.get("x", -1)) == int(x) and int(other.get("y", -1)) == int(y):
                    return False
            except Exception:
                continue
        for other in self.regional_town_visitors():
            if str(other.get("id", "")) == str(ignore_npc_id or ""):
                continue
            if str(other.get("runtime_location", "")) != "Town":
                continue
            if (int(other.get("x", -1)), int(other.get("y", -1))) == (int(x), int(y)):
                return False
        tile = self.active_map()[y][x]
        return tile in [".", "=", ":", ",", "?", "!"]

    def nearest_town_npc_passable_tile(self, x: int, y: int, ignore_npc_id: Optional[str] = None, radius_limit: int = 8) -> Tuple[int, int]:
        if self.town_npc_passable_tile(x, y, ignore_npc_id):
            return x, y
        for radius in range(1, radius_limit + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = x + dx, y + dy
                    if self.town_npc_passable_tile(nx, ny, ignore_npc_id):
                        return nx, ny
        return self.nearest_town_passable_tile(x, y)

    def town_npc_town_static_tile(self, x: int, y: int) -> bool:
        if not (0 <= x < TOWN_WIDTH and 0 <= y < TOWN_HEIGHT):
            return False
        if self.town_map[y][x] not in {".", "=", ":", ","}:
            return False
        return True

    def town_npc_town_route_tile(self, x: int, y: int, npc_id: str = "") -> bool:
        if not self.town_npc_town_static_tile(x, y):
            return False
        if self.on_town() and (x, y) == (self.state.player_x, self.state.player_y):
            return False
        for other in getattr(self.state, "town_npcs", []):
            if not isinstance(other, dict) or str(other.get("id", "")) == str(npc_id):
                continue
            if self.town_npc_actual_location(other) != "Town":
                continue
            if (int(other.get("x", -1)), int(other.get("y", -1))) == (x, y):
                return False
        return True

    def town_npc_nearest_town_route_tile(self, x: int, y: int, npc_id: str = "") -> Tuple[int, int]:
        for radius in range(0, 10):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) != radius:
                        continue
                    point = (x + dx, y + dy)
                    if self.town_npc_town_route_tile(*point, npc_id):
                        return point
        return int(x), int(y)

    def town_npc_exterior_access(self, location: str, npc_id: str = "") -> Tuple[int, int]:
        residence_id = self.town_npc_residence_id_from_runtime(location)
        if residence_id:
            door_x, door_y = AUTHORED_TOWN_RESIDENCE_DATA[residence_id]["door"]
        else:
            building_id = TOWN_BUILDING_ID_BY_LOCATION.get(str(location), "")
            door_x, door_y = TOWN_DOORS.get(building_id, (27, 18))
        return self.town_npc_nearest_town_route_tile(door_x, door_y + 1, npc_id)

    def town_npc_private_home_anchor(self, npc: Dict[str, object]) -> Tuple[int, int]:
        return self.town_npc_nearest_town_route_tile(
            int(npc.get("home_x", npc.get("x", 0))),
            int(npc.get("home_y", npc.get("y", 0))),
            str(npc.get("id", "")),
        )

    def town_npc_interior_route_tile(self, location: str, x: int, y: int, npc_id: str) -> bool:
        if not self.authored_town_interior_passable(location, x, y):
            return False
        if self.state.location == location and (x, y) == (self.state.player_x, self.state.player_y):
            return False
        for other in getattr(self.state, "town_npcs", []):
            if not isinstance(other, dict) or str(other.get("id", "")) == str(npc_id):
                continue
            if self.town_npc_actual_location(other) != location:
                continue
            if (int(other.get("interior_x", -1)), int(other.get("interior_y", -1))) == (x, y):
                return False
        return True

    def town_npc_move_interior_toward(self, npc: Dict[str, object], location: str, target: Tuple[int, int]) -> bool:
        npc_id = str(npc.get("id", ""))
        start = (int(npc.get("interior_x", 27)), int(npc.get("interior_y", 18)))
        if start == target:
            npc["route_blocked"] = False
            return True
        step = self.town_npc_path_step(
            start,
            target,
            lambda x, y: self.authored_town_interior_passable(location, x, y),
            max_nodes=700,
        )
        if step is None:
            npc["route_blocked"] = True
            return False
        if step != start and not self.town_npc_interior_route_tile(location, step[0], step[1], npc_id):
            alternatives = [
                point for point in ((start[0] + 1, start[1]), (start[0] - 1, start[1]), (start[0], start[1] + 1), (start[0], start[1] - 1))
                if self.town_npc_interior_route_tile(location, point[0], point[1], npc_id)
            ]
            alternatives.sort(key=lambda point: abs(point[0] - target[0]) + abs(point[1] - target[1]))
            if not alternatives:
                npc["route_blocked"] = True
                return False
            step = alternatives[0]
        self.town_npc_set_facing_for_step(npc, start, step)
        npc["interior_x"], npc["interior_y"] = step
        npc["steps_today"] = int(npc.get("steps_today", 0)) + 1
        npc["route_blocked"] = False
        return step == target

    def town_npc_move_town_toward(self, npc: Dict[str, object], target: Tuple[int, int]) -> bool:
        npc_id = str(npc.get("id", ""))
        start = (int(npc.get("x", 0)), int(npc.get("y", 0)))
        if start == target:
            npc["route_blocked"] = False
            return True
        step = self.town_npc_path_step(
            start,
            target,
            self.town_npc_town_static_tile,
        )
        if step is None:
            npc["route_blocked"] = True
            return False
        if step != start and not self.town_npc_town_route_tile(step[0], step[1], npc_id):
            alternatives = [
                point for point in ((start[0] + 1, start[1]), (start[0] - 1, start[1]), (start[0], start[1] + 1), (start[0], start[1] - 1))
                if self.town_npc_town_route_tile(point[0], point[1], npc_id)
            ]
            alternatives.sort(key=lambda point: abs(point[0] - target[0]) + abs(point[1] - target[1]))
            if not alternatives:
                npc["route_blocked"] = True
                return False
            step = alternatives[0]
        self.town_npc_set_facing_for_step(npc, start, step)
        npc["x"], npc["y"] = step
        npc["steps_today"] = int(npc.get("steps_today", 0)) + 1
        npc["route_blocked"] = False
        return step == target

    def town_npc_place_at_destination(self, npc: Dict[str, object], desired: str):
        npc_id = str(npc.get("id", ""))
        if desired == "Town":
            target = self.town_npc_schedule_anchor(npc)
            npc["x"], npc["y"] = self.town_npc_nearest_town_route_tile(*target, npc_id)
        elif desired in {"PrivateResidence", "RegionalTravel"}:
            pass
        elif self.town_npc_is_authored_interior_location(desired):
            npc["interior_x"], npc["interior_y"] = self.town_npc_interior_anchor(npc, desired)
        npc["runtime_location"] = desired
        npc["runtime_transition"] = ""
        npc["runtime_target_location"] = desired
        npc["route_blocked"] = False

    def reset_town_npc_daily_routines(self):
        self.normalize_town_npcs()
        self.invalidate_home_region_commuter_cache()
        for npc in self.state.town_npcs:
            npc["steps_today"] = 0
            npc["routine_phase"] = ""
            npc["routine_label"] = ""
            npc["routine_day_key"] = self.town_npc_day_key()
            npc["routine_weather"] = str(self.state.weather)

    def record_town_npc_social_link(self, first: Dict[str, object], second: Dict[str, object]) -> Dict[str, object]:
        first_id, second_id = sorted((str(first.get("id", "")), str(second.get("id", ""))))
        pair_id = f"{first_id}|{second_id}"
        links = self.regional_town_life_state().setdefault("npc_social_links", {})
        record = links.setdefault(pair_id, {"score": 0, "last_day": "", "meetings": 0})
        day_key = self.town_npc_day_key()
        if str(record.get("last_day", "")) != day_key:
            affinity = sum(ord(ch) for ch in pair_id) % 7
            change = -1 if affinity == 0 else 1
            record["score"] = max(-20, min(20, int(record.get("score", 0)) + change))
            record["meetings"] = int(record.get("meetings", 0)) + 1
            record["last_day"] = day_key
        return record

    def town_npc_social_link_label(self, first_id: str, second_id: str) -> str:
        pair_id = "|".join(sorted((str(first_id), str(second_id))))
        record = self.regional_town_life_state().get("npc_social_links", {}).get(pair_id, {})
        score = int(record.get("score", 0) or 0) if isinstance(record, dict) else 0
        if score >= 8:
            return "close friends"
        if score >= 3:
            return "friends"
        if score <= -5:
            return "rivals"
        if score < 0:
            return "frequent debaters"
        return "acquaintances"

    def update_town_npc_social_encounters(self):
        phase = self.town_routine_phase()
        day_key = self.town_npc_day_key()
        npcs = self.active_town_npcs()
        for npc in npcs:
            if str(npc.get("social_day_key", "")) != day_key or str(npc.get("social_phase", "")) != phase:
                npc["social_partner_id"] = ""
                npc["social_activity"] = ""
                npc["social_day_key"] = ""
                npc["social_phase"] = ""
        if phase not in {"lunch", "evening"}:
            return

        grouped: Dict[str, List[Dict[str, object]]] = {}
        for npc in npcs:
            if str(npc.get("runtime_transition", "")):
                continue
            location = self.town_npc_actual_location(npc)
            if location in {"HouseInterior", "PrivateResidence"}:
                continue
            grouped.setdefault(location, []).append(npc)

        for location, residents in grouped.items():
            residents.sort(key=lambda record: str(record.get("id", "")))
            available = list(residents)
            while len(available) >= 2:
                npc = available.pop(0)
                x1, y1 = (
                    (int(npc.get("x", 0)), int(npc.get("y", 0)))
                    if location == "Town"
                    else (int(npc.get("interior_x", 0)), int(npc.get("interior_y", 0)))
                )
                nearby = []
                for other in available:
                    x2, y2 = (
                        (int(other.get("x", 0)), int(other.get("y", 0)))
                        if location == "Town"
                        else (int(other.get("interior_x", 0)), int(other.get("interior_y", 0)))
                    )
                    distance = abs(x1 - x2) + abs(y1 - y2)
                    if distance <= (5 if location == "Town" else 8):
                        nearby.append((distance, str(other.get("id", "")), other))
                if not nearby:
                    continue
                nearby.sort(key=lambda item: (item[0], item[1]))
                other = nearby[0][2]
                pair_seed = sum(ord(ch) for ch in f"{day_key}:{phase}:{npc.get('id')}:{other.get('id')}")
                if location == "Town" and pair_seed % 3 != 0:
                    continue
                available.remove(other)
                at_home = bool(self.town_npc_residence_id_from_runtime(location))
                social_link = self.record_town_npc_social_link(npc, other)
                first_name = str(npc.get("name", "a neighbor"))
                second_name = str(other.get("name", "a neighbor"))
                if not at_home and int(social_link.get("score", 0)) < 0:
                    activity_a = f"debating town news with {second_name}"
                    activity_b = f"debating town news with {first_name}"
                else:
                    activity_a = (
                        f"sharing supper and household news with {second_name}"
                        if at_home else f"stopped along the route to talk with {second_name}"
                    )
                    activity_b = (
                        f"sharing supper and household news with {first_name}"
                        if at_home else f"stopped along the route to talk with {first_name}"
                    )
                for subject, partner, activity in ((npc, other, activity_a), (other, npc, activity_b)):
                    subject["social_partner_id"] = str(partner.get("id", ""))
                    subject["social_activity"] = activity
                    subject["social_day_key"] = day_key
                    subject["social_phase"] = phase

    def update_town_npcs(self, force_reanchor: bool = False):
        if not (self.on_town() or self.on_town_interior()):
            return
        self.normalize_town_npcs()
        for npc in self.active_town_npcs():
            try:
                npc_id = str(npc.get("id", ""))
                phase = self.town_npc_current_routine_phase(npc)
                npc["routine_phase"] = phase
                npc["routine_label"] = self.town_routine_phase_label(phase)
                npc["routine_weather"] = str(self.state.weather)
                npc["routine_day_key"] = self.town_npc_day_key()
                desired = self.town_npc_desired_location(npc)
                actual = self.town_npc_actual_location(npc)
                npc["runtime_target_location"] = desired
                npc["activity"] = self.town_npc_activity_label(npc)

                if actual == "HouseInterior":
                    npc["indoors"] = True
                    npc["indoor_location"] = "Farmhouse"
                    continue

                # Locations outside the map the player is currently observing
                # can advance immediately. Visible exits and entrances still
                # happen one tile at a time on the current map.
                observed_location = self.town_npc_observed_runtime_location()
                if self.on_town_interior() and actual not in {observed_location, "Town"}:
                    self.town_npc_place_at_destination(npc, desired)
                    actual = desired

                if self.on_town_interior() and actual == "Town":
                    if desired == observed_location:
                        npc["runtime_location"] = desired
                        npc["interior_x"], npc["interior_y"] = self.town_npc_nearest_interior_tile(desired, 27, 18)
                        npc["runtime_transition"] = "entering_building"
                        anchor = self.town_npc_interior_anchor(npc, desired)
                        self.town_npc_move_interior_toward(npc, desired, anchor)
                    else:
                        self.town_npc_place_at_destination(npc, desired)
                    continue

                if actual == "PrivateResidence":
                    if desired == "PrivateResidence":
                        npc["indoors"] = True
                        npc["indoor_location"] = "Private Home"
                        npc["runtime_transition"] = ""
                        continue
                    npc["runtime_location"] = "Town"
                    npc["x"], npc["y"] = self.town_npc_private_home_anchor(npc)
                    npc["runtime_transition"] = "leaving_home"
                    actual = "Town"

                if actual == "RegionalTravel":
                    if desired == "RegionalTravel":
                        npc["indoors"] = True
                        npc["indoor_location"] = str(npc.get("regional_destination", "Regional Roads"))
                        npc["runtime_transition"] = ""
                        continue
                    npc["runtime_location"] = "Town"
                    npc["x"], npc["y"] = (58, 1)
                    npc["runtime_transition"] = "returning_from_region"
                    actual = "Town"

                if self.town_npc_is_authored_interior_location(actual):
                    if desired == actual:
                        npc["indoors"] = True
                        npc["indoor_location"] = self.town_npc_indoor_location(npc)
                        anchor = self.town_npc_interior_anchor(npc, actual)
                        if observed_location == actual:
                            npc["runtime_transition"] = "walking_inside"
                            self.town_npc_move_interior_toward(npc, actual, anchor)
                        else:
                            npc["interior_x"], npc["interior_y"] = anchor
                        if (int(npc.get("interior_x", -1)), int(npc.get("interior_y", -1))) == anchor:
                            npc["runtime_transition"] = ""
                        continue

                    landing = self.town_npc_nearest_interior_tile(actual, 27, 18)
                    if observed_location == actual:
                        npc["runtime_transition"] = "leaving_building"
                        if not self.town_npc_move_interior_toward(npc, actual, landing):
                            continue
                    npc["runtime_location"] = "Town"
                    npc["x"], npc["y"] = self.town_npc_exterior_access(actual, npc_id)
                    npc["runtime_transition"] = "outside_door"
                    actual = "Town"
                    if not self.on_town():
                        continue

                if actual != "Town":
                    continue

                npc["indoors"] = False
                npc["indoor_location"] = ""
                if desired == "HouseInterior":
                    self.town_npc_place_at_destination(npc, desired)
                    continue
                if desired == "PrivateResidence":
                    target = self.town_npc_private_home_anchor(npc)
                    npc["runtime_transition"] = "going_home"
                    if self.town_npc_move_town_toward(npc, target):
                        self.town_npc_place_at_destination(npc, desired)
                    continue
                if desired == "RegionalTravel":
                    npc["runtime_transition"] = "leaving_for_region"
                    if self.town_npc_move_town_toward(npc, (58, 1)):
                        self.town_npc_place_at_destination(npc, desired)
                    continue
                if self.town_npc_is_authored_interior_location(desired):
                    target = self.town_npc_exterior_access(desired, npc_id)
                    npc["runtime_transition"] = "going_to_door"
                    if self.town_npc_move_town_toward(npc, target):
                        npc["runtime_location"] = desired
                        npc["interior_x"], npc["interior_y"] = self.town_npc_nearest_interior_tile(desired, 27, 18)
                        npc["runtime_transition"] = "entering_building"
                    continue

                x = int(npc.get("x", 0))
                y = int(npc.get("y", 0))
                ax, ay = self.town_npc_schedule_anchor(npc)
                npc["current_anchor_x"] = ax
                npc["current_anchor_y"] = ay
                travel_radius = max(3, int(npc.get("wander_radius", 5)) // 2 + 2)
                distance_to_anchor = abs(x - ax) + abs(y - ay)
                completing_route = str(npc.get("runtime_transition", "")) in {
                    "outside_door", "leaving_home", "walking_to_routine"
                }
                if distance_to_anchor > 0 and (completing_route or distance_to_anchor > travel_radius):
                    npc["runtime_transition"] = "walking_to_routine"
                    self.town_npc_move_town_toward(npc, (ax, ay))
                    continue
                npc["runtime_transition"] = ""

                if self.town_npc_near_player(npc, distance=2):
                    self.town_npc_face_player(npc)
                    if random.random() > 0.12:
                        continue

                role = str(npc.get("role", "Villager"))
                move_chance = 0.28
                if role in ["Courier", "Kid", "Traveler", "Musician"]:
                    move_chance = 0.48
                elif role in ["Orchardist", "Beekeeper", "Botanist"]:
                    move_chance = 0.34
                elif role in ["Recluse", "Librarian", "Mayor", "Scholar", "Retiree"]:
                    move_chance = 0.18
                if phase == "lunch":
                    move_chance *= 1.2
                elif phase in ["work_morning", "work_afternoon"] and role in TOWN_INDOOR_WORK_ROLES:
                    move_chance *= 0.65
                elif phase == "late":
                    move_chance *= 0.45
                if self.town_weather_is_bad_for_routines():
                    move_chance *= 0.55
                if self.town_weather_is_severe_for_routines():
                    move_chance *= 0.25
                if self.town_time_period() == "evening":
                    move_chance *= 0.75

                if random.random() > move_chance:
                    continue

                radius = travel_radius
                options = [(1,0),(-1,0),(0,1),(0,-1)]
                random.shuffle(options)

                if abs(x - ax) + abs(y - ay) > radius:
                    options = sorted(options, key=lambda d: abs((x + d[0]) - ax) + abs((y + d[1]) - ay))

                for dx, dy in options:
                    nx, ny = x + dx, y + dy
                    if abs(nx - ax) + abs(ny - ay) > radius + 2:
                        continue
                    if self.town_npc_passable_tile(nx, ny, npc_id):
                        npc["x"], npc["y"] = nx, ny
                        npc["steps_today"] = int(npc.get("steps_today", 0)) + 1
                        if dx > 0:
                            npc["facing"] = "RIGHT"
                        elif dx < 0:
                            npc["facing"] = "LEFT"
                        elif dy > 0:
                            npc["facing"] = "DOWN"
                        elif dy < 0:
                            npc["facing"] = "UP"
                        break
            except Exception as exc:
                append_debug_log(f"Authored town NPC update skipped for {npc.get('id', '?')}: {type(exc).__name__}: {exc}")
                continue
        self.update_town_npc_social_encounters()
        self.update_regional_town_visitors()

    def town_npc_role_dialogue_lines(self, npc: Dict[str, object]) -> List[str]:
        first = self.choose_npc_dialogue(npc)
        second = self.choose_npc_dialogue(npc)
        lines = [f'"{first.get("text", "Good to see you.")}"']
        if second.get("id") != first.get("id"):
            lines.append(f'"{second.get("text", "Good to see you.")}"')
        return lines

    def npc_dialogue_preferred_response_style(self, npc: Dict[str, object]) -> str:
        role = str(npc.get("role") or npc.get("profession") or "Villager")
        for style, roles in NPC_DIALOGUE_RESPONSE_PREFERENCES.items():
            if role in roles:
                return style
        personality_text = " ".join(
            [
                str(npc.get("personality", "")),
                *(str(value) for value in npc.get("personality_traits", []) or []),
            ]
        ).lower()
        if any(word in personality_text for word in ("kind", "warm", "gentle", "caring", "patient")):
            return "empathetic"
        if any(word in personality_text for word in ("curious", "scholar", "thoughtful", "observant", "creative")):
            return "curious"
        return "practical"

    def npc_dialogue_response_choice(
        self,
        npc: Dict[str, object],
        influence_available: bool = True,
        title: str = "Your Response",
    ) -> Dict[str, object]:
        """Let the player answer an NPC and return a bounded social effect."""
        preference = self.npc_dialogue_preferred_response_style(npc)
        availability_hint = "Can influence your standing" if influence_available else "No further influence today"
        items = [
            MenuItem(
                label="Listen Without Interrupting",
                value="empathetic",
                enabled=True,
                hint=availability_hint,
            ),
            MenuItem(
                label="Ask a Thoughtful Follow-Up",
                value="curious",
                enabled=True,
                hint=availability_hint,
            ),
            MenuItem(
                label="Suggest a Concrete Next Step",
                value="practical",
                enabled=True,
                hint=availability_hint,
            ),
            MenuItem(
                label="Brush It Aside",
                value="dismissive",
                enabled=True,
                hint="May damage trust" if influence_available else "No further influence today",
            ),
            MenuItem(label="Leave the Conversation There", value="leave", enabled=True),
        ]
        choice = self.vertical_panel_select(
            title,
            items,
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        style = str(choice.value) if choice else "leave"
        if style == MENU_BACK:
            style = "leave"
        if not influence_available or style == "leave":
            effect = 0
        elif style == "dismissive":
            effect = -3
        elif style == preference:
            effect = 2
        else:
            effect = 1
        name = str(npc.get("name", "They"))
        if style == "leave":
            reaction = f"{name} lets the subject rest without taking offense."
        elif style == "dismissive":
            reaction = f"{name}'s expression closes. They clearly expected the subject to be taken more seriously."
        elif style == preference:
            reaction = {
                "empathetic": f"{name} relaxes when you give them room to finish the thought in their own way.",
                "curious": f"{name} considers your follow-up carefully and answers with more detail than before.",
                "practical": f"{name} tests your suggestion against the problem and nods at the part that might actually work.",
            }.get(style, f"{name} appreciates the response.")
        else:
            reaction = f"{name} considers your response. It was not quite their instinct, but the effort feels sincere."
        return {
            "style": style,
            "preferred_style": preference,
            "effect": effect,
            "reaction": reaction,
        }

    def town_npc_work_insight(self, npc: Dict[str, object]) -> str:
        role = str(npc.get("role", "Villager"))
        choices = list(NPC_ROLE_CONVERSATION_INSIGHTS.get(role, ()))
        if not choices:
            data = self.town_npc_dialogue_data(npc)
            return str(data.get("motivation", "The work changes according to who needs it and what the day allows."))
        return self.town_npc_daily_pick(npc, "work_insight", choices)

    def town_npc_first_person_statement(self, npc: Dict[str, object], text: object) -> str:
        statement = " ".join(str(text or "").strip().split())
        name = str(npc.get("name", ""))
        replacements = {
            f"{name} wants": "I want",
            f"{name} keeps": "I keep",
            f"{name} says": "I think",
            f"{name} worries": "I worry",
            f"{name} hopes": "I hope",
            f"{name} believes": "I believe",
        }
        for source, replacement in replacements.items():
            if source and statement.startswith(source):
                return replacement + statement[len(source):]
        return statement

    def town_npc_known_person_line(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        partner_id = str(npc.get("social_partner_id", ""))
        if partner_id:
            partner = self.npc_record_by_id(partner_id)
            if partner:
                link = self.town_npc_social_link_label(npc_id, partner_id)
                activity = str(npc.get("social_activity", "spending time together") or "spending time together")
                return (
                    f"{partner.get('name', 'A neighbor')} and I are {link}. "
                    f"You learn a surprising amount about somebody while {activity}."
                )
        links = self.regional_town_life_state().get("npc_social_links", {})
        candidates: List[Tuple[int, str]] = []
        if isinstance(links, dict):
            for pair_id, record in links.items():
                ids = str(pair_id).split("|", 1)
                if len(ids) != 2 or npc_id not in ids or not isinstance(record, dict):
                    continue
                other_id = ids[1] if ids[0] == npc_id else ids[0]
                candidates.append((abs(int(record.get("score", 0) or 0)), other_id))
        if candidates:
            _weight, other_id = sorted(candidates, reverse=True)[0]
            other = self.npc_record_by_id(other_id)
            if other:
                return (
                    f"{other.get('name', 'A neighbor')} and I are "
                    f"{self.town_npc_social_link_label(npc_id, other_id)}. "
                    "Town gets smaller once you know which disagreements are permanent and which only needed lunch."
                )
        rumor = self.town_npc_dialogue_data(npc).get("rumor", "")
        if rumor:
            return self.town_npc_first_person_statement(npc, rumor)
        return "I know people by their routines more than by their introductions."

    def town_npc_conversation_topic_items(self, npc: Dict[str, object]) -> List[MenuItem]:
        relationship = self.town_npc_relationship(str(npc.get("id", "")))
        return [
            MenuItem(label="Ask What's on Their Mind", value="mind", enabled=True, hint=self.town_npc_mood(npc).title()),
            MenuItem(label="Ask What They're Doing", value="activity", enabled=True, hint=self.town_npc_activity_label(npc)),
            MenuItem(label="Ask About Their Work", value="work", enabled=True, hint=str(npc.get("role", "Villager"))),
            MenuItem(label="Ask About This Place", value="place", enabled=True, hint=self.town_npc_location_label(npc)),
            MenuItem(label="Ask About Someone They Know", value="people", enabled=True, hint="Friends, family, and neighbors"),
            MenuItem(
                label="Ask Something Personal",
                value="personal",
                enabled=relationship >= 25,
                hint="Requires Acquaintance" if relationship < 25 else self.relationship_tier_for_npc(npc),
            ),
            MenuItem(label="Back", value=MENU_BACK, enabled=True),
        ]

    def town_npc_conversation_topic_lines(
        self,
        npc: Dict[str, object],
        topic: str,
    ) -> List[str]:
        topic = str(topic or "mind")
        name = str(npc.get("name", "Villager"))
        role = str(npc.get("role", "Villager"))
        activity = self.town_npc_activity_label(npc)
        location = self.town_npc_location_label(npc)
        first_person_activity = activity.replace("their ", "my ")
        place_phrase = f"life {location}" if location.lower().startswith("inside ") else location
        data = self.town_npc_dialogue_data(npc)
        lines: List[str] = [self.town_npc_context_line(npc), ""]

        if topic == "activity":
            lines.extend([
                f'"I am {first_person_activity}. It is one of those tasks that looks simpler from across the room."',
                "",
                f'"{self.town_npc_work_insight(npc)}"',
            ])
        elif topic == "work":
            lines.extend([
                f'"{self.town_npc_work_insight(npc)}"',
                "",
                f"{name} explains how the work of a {role.lower()} fits into the routines of {place_phrase}.",
            ])
        elif topic == "place":
            context_category = self.weather_dialogue_category()
            entry = self.choose_npc_dialogue(npc, immediate_category=context_category)
            occasion = self.todays_town_public_occasion()
            lines.append(f'"{entry.get("text", "The place changes with the day.")}"')
            lines.extend([
                "",
                f'"Right now I am thinking about {place_phrase}, {self.state.weather.lower()} weather, and what {self.state.season.lower()} asks of this town."',
            ])
            if occasion:
                lines.extend(["", f'"{occasion.get("name", "Today’s gathering")} changes who passes through {occasion.get("location", "town")} and what they notice."'])
        elif topic == "people":
            lines.extend([f'"{self.town_npc_known_person_line(npc)}"'])
            if self.town_npc_relationship(str(npc.get("id", ""))) >= 60 and data.get("secret"):
                lines.extend(["", f'"{self.town_npc_first_person_statement(npc, data.get("secret"))}"'])
        elif topic == "personal":
            relationship_category = self.relationship_dialogue_category_for_tier(self.relationship_tier_for_npc(npc))
            entry = self.choose_npc_dialogue(npc, immediate_category=relationship_category)
            lines.append(f'"{entry.get("text", "I am still deciding how much of that answer to share.")}"')
            personal = data.get("secret") if self.town_npc_relationship(str(npc.get("id", ""))) >= 60 else data.get("motivation")
            if personal:
                lines.extend(["", f'"{self.town_npc_first_person_statement(npc, personal)}"'])
        else:
            first = self.choose_npc_dialogue(npc)
            second = self.choose_npc_dialogue(npc)
            lines.append(f'"{first.get("text", "Good to see you.")}"')
            if second.get("id") != first.get("id"):
                lines.extend(["", f'"{second.get("text", self.town_npc_work_insight(npc))}"'])
            lines.extend(["", f'"{self.town_npc_work_insight(npc)}"'])
        return lines

    def town_npc_conversation_menu(
        self,
        npc: Dict[str, object],
        influence_available: bool,
    ) -> Dict[str, object]:
        topic_choice = self.vertical_panel_select(
            f"Talk with {npc.get('name', 'Villager')}",
            self.town_npc_conversation_topic_items(npc),
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
            return_back=True,
        )
        if not topic_choice or topic_choice.value == MENU_BACK:
            return {"effect": 0, "style": "leave", "topic": ""}
        topic = str(topic_choice.value)
        self.vertical_panel_view(
            str(npc.get("name", "Villager")),
            self.town_npc_conversation_topic_lines(npc, topic),
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )
        response = self.npc_dialogue_response_choice(
            npc,
            influence_available=influence_available,
            title=f"Respond to {npc.get('name', 'Them')}",
        )
        response["topic"] = topic
        self.vertical_panel_view(
            str(npc.get("name", "Villager")),
            [
                str(response.get("reaction", "The conversation settles.")),
                "",
                (
                    f"Relationship influence: {int(response.get('effect', 0)):+}"
                    if influence_available and int(response.get("effect", 0))
                    else "You have already had your meaningful conversation today."
                    if not influence_available
                    else "No relationship change."
                ),
            ],
            LEFT_PANEL_WIDTH,
            LEFT_PANEL_HEIGHT,
        )
        return response

    def authored_town_service_spec(self, npc: Dict[str, object]):
        return AUTHORED_TOWN_SERVICE_SPECS.get(str(npc.get("id", "")))

    def town_npc_work_service_available(self, npc: Dict[str, object]) -> bool:
        spec = self.authored_town_service_spec(npc)
        return bool(
            spec
            and self.state.location == spec[0]
            and self.town_npc_actual_location(npc) == spec[0]
            and self.is_town_building_unlocked(TOWN_BUILDING_ID_BY_LOCATION.get(spec[0], ""))
        )

    def open_town_npc_work_service(self, npc: Dict[str, object]) -> bool:
        spec = self.authored_town_service_spec(npc)
        if not spec or not self.town_npc_work_service_available(npc):
            self.set_message(f"{npc.get('name', 'They')} is not currently on duty here.")
            return False
        _location, _label, method_name, fallback = spec
        method = getattr(self, method_name, None)
        if not callable(method):
            self.set_message("That service is not available right now.")
            return False
        if method_name in {"buy_menu", "blacksmith_menu", "carpenter_menu"}:
            callback = lambda: method(auto_opened=False)
        else:
            callback = method
        self.safe_menu(callback, fallback)
        return True

    def authored_town_service_hours(self, location: str) -> str:
        return AUTHORED_TOWN_SERVICE_HOURS.get(str(location), "By appointment")

    def authored_town_staff_names(self, location: str, present_only: bool = True) -> List[str]:
        names: List[str] = []
        for npc in self.active_town_npcs():
            spec = self.authored_town_service_spec(npc)
            if not spec or spec[0] != str(location):
                continue
            if present_only and self.town_npc_actual_location(npc) != str(location):
                continue
            names.append(str(npc.get("name", "Staff")))
        return names

    def authored_town_building_detail(self, building_id: str) -> str:
        data = TOWN_BUILDING_DATA.get(str(building_id), {})
        location = str(data.get("location", ""))
        if not location:
            return ""
        hours = self.authored_town_service_hours(location)
        assigned = self.authored_town_staff_names(location, present_only=False)
        present = self.authored_town_staff_names(location, present_only=True)
        if present:
            staffing = f"on duty: {', '.join(present)}"
        elif assigned:
            staffing = f"staff away: {', '.join(assigned)}"
        else:
            staffing = "self-service counter"
        return f"Hours: {hours}; {staffing}."

    def town_npc_weather_dialogue_line(self, npc: Dict[str, object]) -> str:
        choices = self.curated_dialogue_lines_for_category(npc, self.weather_dialogue_category())
        note = choices[0] if choices else "They keep one eye on the weather before committing to plans."
        return f"Weather: {note} ({self.state.weather} today.)"

    def town_npc_season_dialogue_line(self, npc: Dict[str, object]) -> str:
        choices = self.curated_dialogue_lines_for_category(npc, str(self.state.season).lower())
        note = choices[0] if choices else f"{self.state.season} is shaping today's routine."
        return f"Season: {note}"

    def town_npc_memory_lines(self, npc: Dict[str, object], already_talked: bool) -> List[str]:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        friendship = self.town_npc_relationship(npc_id)
        count = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        lines: List[str] = []
        if count >= 12:
            lines.append("They start talking before you have fully stepped into view.")
        elif count >= 5:
            lines.append("They have started to recognize your usual route through town.")
        if friendship >= 100:
            lines.append("They no longer spend energy making every sentence sound proper.")
        elif friendship >= 60:
            lines.append("They seem genuinely glad you stopped.")
        elif friendship < 0:
            lines.append("They keep the conversation short enough to escape if needed.")
        if already_talked:
            lines.append("You already talked today, so this is more of a quick check-in.")
        return lines

    def town_npc_errand_hint_line(self, npc: Dict[str, object]) -> str:
        errand = self.errand_for_npc(npc)
        if errand.get("completed"):
            return "Their errand is already complete today."
        if self.can_complete_errand(errand):
            return f"You have what they need today: {errand.get('qty')} {errand.get('item')}."
        return f"Today's errand: {errand.get('qty')} {errand.get('item')}."

    def town_npc_daily_pick(self, npc: Dict[str, object], category: str, choices: List[str]) -> str:
        if not choices:
            return ""
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        seed_text = f"{self.town_npc_day_key()}:{npc_id}:{category}:{self.state.season}:{self.state.weather}:{self.town_time_period()}"
        index = sum(ord(ch) for ch in seed_text) % len(choices)
        return choices[index]

    def relationship_tier_for_npc(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        if self.state.spouse_npc_id == npc_id:
            return "Spouse"
        if npc_id in set(self.state.dating_npc_ids or []):
            return "Dating"
        points = self.town_npc_relationship(npc_id)
        if points >= 200:
            return "Deep Bond"
        if points >= 150:
            return "Trusted"
        if points >= 100:
            return "Close Friend"
        if points >= 60:
            return "Friend"
        if points >= 25:
            return "Acquaintance"
        return "Stranger"

    def relationship_dialogue_category_for_tier(self, tier: str) -> str:
        if tier in ["Spouse", "Dating", "Deep Bond"]:
            return "deep_bond"
        if tier in ["Trusted", "Close Friend"]:
            return "high_friendship"
        if tier in ["Friend", "Acquaintance"]:
            return "medium_friendship"
        return "low_friendship"

    def weather_dialogue_category(self) -> str:
        weather = str(self.state.weather).strip().lower()
        return {
            "rain": "rainy",
            "rainy": "rainy",
            "storm": "stormy",
            "stormy": "stormy",
            "snow": "snowy",
            "snowy": "snowy",
            "blizzard": "blizzard",
            "cloud": "cloudy",
            "cloudy": "cloudy",
            "sun": "sunny",
            "sunny": "sunny",
        }.get(weather, weather if weather else "sunny")

    def time_dialogue_category(self) -> str:
        phase = self.town_routine_phase()
        if phase in ["wake", "work_morning"]:
            return "morning"
        if phase in ["lunch", "work_afternoon"]:
            return "midday"
        if phase == "evening":
            return "evening"
        return "late"

    def gift_reaction_dialogue_category(self, amount: int, reaction: str) -> str:
        reaction = str(reaction)
        if amount < 0 or reaction == "disliked":
            return "after_disliked_gift"
        if amount >= 4 or reaction in ["loved", "liked artisan gift", "appreciated role gift", "liked"]:
            return "after_liked_gift"
        return "after_neutral_gift"

    def last_gift_dialogue_category_for_npc(self, npc: Dict[str, object]) -> str:
        npc_id = str(npc.get("id", ""))
        reaction = self.state.town_npc_last_gift_reactions.get(npc_id, {}) if isinstance(self.state.town_npc_last_gift_reactions, dict) else {}
        if not isinstance(reaction, dict) or str(reaction.get("day", "")) != self.town_npc_day_key():
            return ""
        return str(reaction.get("category", ""))

    def town_npc_reactivity_voice(self, npc: Dict[str, object]) -> str:
        role = str(npc.get("role", "Villager"))
        return {
            "Mayor": "civic",
            "Seed Seller": "farm",
            "Blacksmith": "forge",
            "Carpenter": "builder",
            "Animal Keeper": "care",
            "Librarian": "records",
            "Traveler": "travel",
            "Doctor": "medical",
            "Innkeeper": "hospitality",
            "Chef": "food",
            "Market Vendor": "market",
            "Gardener": "nature",
            "Fisher": "water",
            "Miner": "mine",
            "Kid": "child",
            "Courier": "routes",
            "Artist": "art",
            "Recluse": "wild",
            "Orchardist": "orchard",
            "Tailor": "tailor",
            "Musician": "music",
            "Beekeeper": "pollinator",
            "Botanist": "botany",
            "Mechanic": "mechanic",
            "Scholar": "records",
            "Retiree": "elder",
        }.get(role, "town")

    def town_npc_reactive_categories(self) -> set:
        return {
            "player_married",
            "spouse_at_home",
            "marriage_anniversary",
            "pregnancy_checkup_due",
            "pregnancy_early",
            "pregnancy_mid",
            "pregnancy_late",
            "child_birthday_today",
            "child_newborn",
            "child_young",
            "child_school_age",
            "child_teen",
            "family_bond_high",
            "family_meal_recent",
            "land_claim_owned",
            "land_claim_many",
            "automation_active",
            "house_comfortable",
            "combat_victory",
            "combat_level",
            "mine_depth",
            "mine_deep",
            "mine_hazard_day",
            "combat_contract_day",
            "market_day",
            "storm_warning",
            "town_work_completed",
        }

    def land_claim_dialogue_context(self) -> Dict[str, object]:
        claims = self.state.owned_wilderness_claims if isinstance(getattr(self.state, "owned_wilderness_claims", None), dict) else {}
        summary: Dict[str, object] = {
            "owned_claim_count": len(claims),
            "claim_name": "",
            "claim_type": "",
            "claim_traits": "",
            "claim_key": "",
        }
        if not claims:
            return summary
        claim_key = sorted(str(key) for key in claims.keys())[0]
        claim = claims.get(claim_key, {})
        if not isinstance(claim, dict):
            return summary
        try:
            if hasattr(self, "ensure_wilderness_claim_identity"):
                claim = self.ensure_wilderness_claim_identity(claim_key, claim)
        except Exception:
            pass
        summary.update({
            "claim_name": str(claim.get("name", f"Claim {claim_key}")),
            "claim_type": str(claim.get("farm_type") or claim.get("type") or "farm claim"),
            "claim_traits": str(claim.get("traits") or claim.get("identity") or "raw land"),
            "claim_key": claim_key,
        })
        return summary

    def child_dialogue_context(self) -> Dict[str, object]:
        children = list(getattr(self.state, "children", []) or [])
        summary: Dict[str, object] = {
            "children_count": len(children),
            "youngest_child_name": "",
            "youngest_child_stage": "",
            "child_birthday_today": False,
        }
        if not children:
            return summary
        try:
            youngest = min(children, key=lambda child: self.household_child_age_months(child))
            self.ensure_child_profile_fields(youngest)
            summary["youngest_child_name"] = str(youngest.get("name", "your child"))
            summary["youngest_child_stage"] = self.household_child_stage(youngest)
            summary["child_birthday_today"] = any(self.is_child_birthday(child) for child in children)
        except Exception:
            summary["youngest_child_name"] = str(children[0].get("name", "your child")) if isinstance(children[0], dict) else "your child"
            summary["youngest_child_stage"] = "Child"
        return summary

    def calendar_dialogue_context(self) -> Dict[str, object]:
        summary = {
            "market_day": False,
            "mine_hazard": "",
            "seasonal_contract": "",
            "storm_warning": self.town_weather_is_severe_for_routines(),
        }
        try:
            events = self.selected_calendar_events_text(self.state.month, self.state.day, self.state.year)
            event_text = " ".join(str(row).lower() for row in events)
            summary["market_day"] = "market day" in event_text
            summary["storm_warning"] = bool(summary["storm_warning"] or "storm warning" in event_text)
        except Exception:
            pass
        try:
            summary["mine_hazard"] = str(self.mine_hazard_label_for_date(self.state.month, self.state.day, self.state.year) or "")
        except Exception:
            summary["mine_hazard"] = ""
        try:
            summary["seasonal_contract"] = str(self.seasonal_combat_contract_label_for_date(self.state.month, self.state.day, self.state.year) or "")
        except Exception:
            summary["seasonal_contract"] = ""
        return summary

    def npc_reactive_format_values(self, npc: Dict[str, object], context: Dict[str, object]) -> Dict[str, object]:
        spouse_name = self.town_npc_name(str(getattr(self.state, "spouse_npc_id", ""))) if getattr(self.state, "spouse_npc_id", "") else "your spouse"
        last_meal = str(getattr(self.state, "family_last_meal", "") or "a shared meal")
        return {
            "player": str(getattr(self.state, "player_name", "you")),
            "npc": str(npc.get("name", "they")),
            "spouse": spouse_name,
            "family_rank": self.family_bond_rank() if hasattr(self, "family_bond_rank") else "steady",
            "support_mode": self.spouse_support_mode() if hasattr(self, "spouse_support_mode") else "Balanced",
            "meal": last_meal,
            "pregnancy_month": context.get("pregnancy_month", 0),
            "pregnancy_due": context.get("pregnancy_due", "the due date"),
            "child": context.get("youngest_child_name", "your child"),
            "child_stage": context.get("youngest_child_stage", "Child"),
            "children_count": context.get("children_count", 0),
            "claim_name": context.get("claim_name", "your land claim"),
            "claim_type": context.get("claim_type", "farm claim"),
            "claim_traits": context.get("claim_traits", "raw land"),
            "claim_count": context.get("owned_claim_count", 0),
            "automation_count": context.get("automation_count", 0),
            "house_rank": context.get("house_comfort_rank", "comfortable"),
            "combat_level": context.get("combat_level", 1),
            "deepest_floor": context.get("deepest_mine_floor", 1),
            "victories": context.get("mine_combat_victories", 0),
            "hazard": context.get("mine_hazard", "today's mine hazard"),
            "contract": context.get("seasonal_contract", "the seasonal mine contract"),
            "season": str(getattr(self.state, "season", "the season")).lower(),
            "weather": str(getattr(self.state, "weather", "weather")).lower(),
        }

    def dialogue_role_focus(self, npc: Dict[str, object]) -> str:
        return {
            "Mayor": "town services",
            "Seed Seller": "seed stock",
            "Blacksmith": "tools and mine gear",
            "Carpenter": "paths and building plans",
            "Animal Keeper": "feed and animal care",
            "Librarian": "records and research",
            "Traveler": "routes",
            "Doctor": "rest and supplies",
            "Innkeeper": "meals and visitors",
            "Chef": "seasonal food",
            "Market Vendor": "market stock",
            "Gardener": "public plantings",
            "Fisher": "water and weather",
            "Miner": "mine safety",
            "Kid": "shortcuts",
            "Courier": "delivery routes",
            "Artist": "color and light",
            "Recluse": "the north road",
            "Orchardist": "slow growth",
            "Tailor": "work clothes",
            "Musician": "music nights",
            "Beekeeper": "flowers and hives",
            "Botanist": "wild plants",
            "Mechanic": "machines",
            "Scholar": "town records",
            "Retiree": "benches and routines",
        }.get(str(npc.get("role", "Villager")), "daily work")

    def curated_dialogue_lines_for_category(self, npc: Dict[str, object], category: str) -> List[str]:
        category = str(category or "")
        focus = self.dialogue_role_focus(npc)
        try:
            context = self.dialogue_context_for_npc(npc)
            values = self.npc_reactive_format_values(npc, context)
        except Exception:
            values = {
                "spouse": "your spouse",
                "child": "your child",
                "claim_name": "your land claim",
                "claim_count": 0,
                "automation_count": 0,
                "deepest_floor": 1,
                "hazard": "today's mine hazard",
                "contract": "the posted mine contract",
            }

        table: Dict[str, List[str]] = {
            "spring": [
                f"Spring changes {focus} faster than the ledger can keep up.",
                "Fresh growth is useful, but it still needs planning.",
                "This is a good season to set habits before the busy months hit.",
            ],
            "summer": [
                f"Summer makes {focus} depend on shade, water, and timing.",
                "Work early if you can; the afternoon makes everything heavier.",
                "Hot weather rewards short routes and prepared supplies.",
            ],
            "fall": [
                f"Fall is good for finishing {focus} before winter slows the town down.",
                "Everything feels more deliberate once the air cools.",
                "Good season for storage, repairs, and last big outdoor pushes.",
            ],
            "winter": [
                f"Winter makes {focus} slower, but not less important.",
                "Cold days are good for planning, repairs, cooking, and town work.",
                "Watch your routes when snow or ice starts building up.",
            ],
            "sunny": [
                f"Clear weather makes {focus} easier to read.",
                "Good day to travel, harvest, or handle errands before conditions change.",
                "Bright days are useful. Do not spend all of it in menus.",
            ],
            "cloudy": [
                f"Cloud cover keeps {focus} a little easier on the eyes.",
                "Weather might turn, so finish outdoor plans while the roads are steady.",
                "Not every productive day has to be pretty.",
            ],
            "rainy": [
                "Rain helps crops, but it can make roads and wilderness trips messy.",
                f"Rain changes the rhythm of {focus}; plan for slower movement.",
                "If the fields are watered for you, use the saved time well.",
            ],
            "stormy": [
                "Storms are not worth gambling with unless you are prepared.",
                f"Bad weather puts {focus} second to getting home safely.",
                "Keep trips short and bring recovery items if you leave town.",
            ],
            "snowy": [
                "Snow slows the town down, but quiet days can still be useful.",
                f"Snow makes {focus} depend on warm rooms and short routes.",
                "Careful footing matters more than speed today.",
            ],
            "blizzard": [
                "This is shelter weather. Travel only if the reason is worth the risk.",
                f"Blizzards make {focus} wait its turn.",
                "If you must go out, keep the route short and come back early.",
            ],
            "quest_or_story_flag_related": [
                "That job you finished changed more than the checklist.",
                "People noticed the work, even if they do not all know who to thank.",
                "A completed repair makes the town feel less temporary.",
            ],
            "town_work_completed": [
                "Seeing a closed place open again changes the whole route through town.",
                "The town feels more useful when its services actually work.",
                "That repair gave people another reason to leave the house.",
            ],
            "player_married": [
                "I heard about the wedding. That changes the shape of home, doesn't it?",
                "Marriage makes ordinary routines carry more weight.",
                "I hope you and {spouse} are making the farm feel like a shared place.",
            ],
            "spouse_at_home": [
                "{spouse} moving to the farm must change the mornings.",
                "A second person in the farmhouse means the place has to work for both of you.",
                "Shared space is practical work as much as romance.",
            ],
            "marriage_anniversary": [
                "Anniversaries are easy to miss when chores get loud. Do something deliberate.",
                "Happy anniversary. Even a small gift counts if you meant it.",
                "A remembered day can hold a household together better than a speech.",
            ],
            "child_related": [
                "{child} must be changing the farmhouse schedule.",
                "Children make small routines matter more than people expect.",
                "A quiet house is useful, but a lived-in house has its own kind of luck.",
            ],
            "family_bond_high": [
                "Your household sounds steadier lately.",
                "A family that eats, rests, and plans together can handle more than it thinks.",
                "The farm feels different when home is working too.",
            ],
            "family_meal_recent": [
                "A shared meal is one of the better uses for farm food.",
                "Cooking for the household turns inventory into memory.",
                "Dinner does more work than people give it credit for.",
            ],
            "land_claim_owned": [
                "{claim_name} sounds like raw land with real potential.",
                "A purchased claim is not a finished farm. That is the point.",
                "Fast travel helps, but the land still needs your hands on it.",
            ],
            "land_claim_many": [
                "{claim_count} claims is a lot of land to remember. Keep notes.",
                "More claims mean more freedom, but also more places to leave unfinished work.",
                "Separate farms work best when each one has a clear purpose.",
            ],
            "automation_active": [
                "Automation helps most when the farm still has clear paths.",
                "{automation_count} machine setup can save time if you keep it fed and accessible.",
                "A good machine should remove chores, not make the farm harder to walk through.",
            ],
            "house_comfortable": [
                "Your farmhouse looks more like a home now.",
                "Comfort is not just decoration if it helps you recover.",
                "A better room changes how the whole day starts.",
            ],
            "combat_victory": [
                "You made it back from a fight. Recover before you chase the next one.",
                "HP and MP matter after the battle too, so sleep or use supplies before pushing on.",
                "Winning once is not a reason to enter the next room hurt.",
            ],
            "combat_level": [
                "You are getting stronger, but supplies still decide long trips.",
                "Skill does not replace health potions, mana potions, or a way home.",
                "A better fighter still needs a plan.",
            ],
            "mine_depth": [
                "Floor {deepest_floor} is deep enough that preparation starts to matter.",
                "The mine is easier to leave safely if you decide your limit before going down.",
                "Bring food or potions before treating the mine like a quick errand.",
            ],
            "mine_deep": [
                "Floor {deepest_floor} is not casual work anymore.",
                "Deep mining is party work if you have companions ready.",
                "Do not let ore tempt you past your recovery supplies.",
            ],
            "mine_hazard_day": [
                "{hazard} is on the calendar. Read it before going underground.",
                "Mine hazard days reward caution more than courage.",
                "If you go during a hazard, bring healing and leave early.",
            ],
            "combat_contract_day": [
                "{contract} is posted today. Check the mission board before you commit.",
                "Seasonal contracts pay better when you prepare for the target.",
                "A contract is optional. Gear up before making it your problem.",
            ],
            "market_day": [
                "Market Row rotates stock on market days, so check it before spending elsewhere.",
                "Limited stock goes faster when the town is busy.",
                "Market days are good for rare goods, not impulse buying everything.",
            ],
            "storm_warning": [
                "The warning is there for a reason. Finish errands early.",
                "Storm warnings make long wilderness routes a bad bargain.",
                "If tomorrow looks rough, handle travel today or prepare to stay close.",
            ],
        }
        lines = table.get(category, [])
        formatted: List[str] = []
        for line in lines:
            try:
                formatted.append(line.format(**values))
            except Exception:
                formatted.append(line)
        return formatted

    def low_quality_dialogue_text(self, text: str) -> bool:
        clean = " ".join(str(text or "").strip().split())
        if not clean:
            return True
        lowered = clean.lower()
        exact = {
            "mud everywhere.",
            "too hot today.",
            "good weather today.",
            "nice out.",
            "rain started.",
            "bad weather today.",
            "kids keep a house busy.",
            "they were asking about you.",
            "you bought land, right?",
            "how many claims do you have now?",
            "i saw something moving on your farm.",
            "your spouse moved in, right?",
            "i heard you got married.",
            "you made it back.",
            "heard about the mine.",
            "you went deeper?",
            "mine hazard today, right?",
            "prices will be weird.",
        }
        if lowered in exact:
            return True
        fragments = [
            "placeholder",
            "not implemented",
            "coming soon",
            "combat stamina",
            "battle stamina",
            "???",
            "lorem ipsum",
        ]
        return any(fragment in lowered for fragment in fragments)

    def dynamic_reactive_dialogue_templates(self) -> Dict[str, Dict[str, str]]:
        # Dialogue now comes from TOWN_NPC_CONTEXTUAL_DIALOGUE_DATA.
        # Keeping these old generated templates disabled prevents generic
        # reactive lines from slipping into otherwise hand-written conversations.
        return {}

    def dynamic_contextual_dialogue_entries_for_category(self, npc: Dict[str, object], category: str) -> List[Dict[str, str]]:
        category = str(category)
        if category not in self.town_npc_reactive_categories():
            return []
        context = self.dialogue_context_for_npc(npc)
        templates = self.dynamic_reactive_dialogue_templates().get(category, {})
        if not templates:
            return []
        voice = self.town_npc_reactivity_voice(npc)
        template = templates.get(voice) or templates.get("default", "")
        if not template:
            return []
        try:
            text = template.format(**self.npc_reactive_format_values(npc, context))
        except Exception:
            text = template
        entry = self.dialogue_entry_from_raw(str(npc.get("id", "")), category, 0, text)
        return [entry] if entry else []

    def dialogue_context_for_npc(self, npc: Dict[str, object]) -> Dict[str, object]:
        festival_name = ""
        try:
            festival = self.todays_festival()
            if festival:
                festival_name = str(festival.get("name", "Festival"))
        except Exception:
            festival_name = ""
        tier = self.relationship_tier_for_npc(npc)
        claim_context = self.land_claim_dialogue_context()
        child_context = self.child_dialogue_context()
        calendar_context = self.calendar_dialogue_context()
        pregnancy_month = self.pregnancy_month_number() if bool(self.state.pregnancy_active) else 0
        try:
            house_rank = self.house_comfort_rank()
        except Exception:
            house_rank = ""
        context = {
            "npc_id": str(npc.get("id", "")),
            "season": str(self.state.season).lower(),
            "weather": self.weather_dialogue_category(),
            "time": self.time_dialogue_category(),
            "location": str(getattr(self.state, "location", "")),
            "relationship_tier": tier,
            "relationship_category": self.relationship_dialogue_category_for_tier(tier),
            "dating": str(npc.get("id", "")) in set(self.state.dating_npc_ids or []),
            "spouse": self.state.spouse_npc_id == str(npc.get("id", "")),
            "pregnancy": bool(self.state.pregnancy_active),
            "children": bool(self.state.children),
            "npc_birthday": self.is_npc_birthday(npc),
            "player_birthday": self.is_player_birthday(),
            "festival": bool(festival_name),
            "festival_name": festival_name,
            "gift_category": self.last_gift_dialogue_category_for_npc(npc),
            "story_flag": bool(self.state.completed_town_project_ids or self.state.completed_bulletin_job_ids),
            "player_married": bool(self.state.spouse_npc_id),
            "spouse_at_home": bool(self.spouse_lives_on_farm()),
            "marriage_anniversary": self.marriage_anniversary_today(),
            "pregnancy_month": pregnancy_month,
            "pregnancy_due": self.pregnancy_due_date_label() if bool(self.state.pregnancy_active) else "",
            "pregnancy_checkup_due": bool(self.state.pregnancy_active and self.pregnancy_checkup_available()),
            "family_bond_score": self.family_bond_score() if hasattr(self, "family_bond_score") else 0,
            "family_last_meal": str(getattr(self.state, "family_last_meal", "") or ""),
            "automation_count": len(getattr(self.state, "automation_machines", {}) or {}) if isinstance(getattr(self.state, "automation_machines", {}), dict) else 0,
            "house_comfort_rank": house_rank,
            "house_comfortable": bool(house_rank in ["Cozy", "Deluxe"] or getattr(self.state, "house_upgrades", [])),
            "combat_level": int(getattr(self.state, "combat_level", 1) or 1),
            "deepest_mine_floor": int(getattr(self.state, "deepest_mine_floor", 1) or 1),
            "mine_combat_victories": int(getattr(self.state, "mine_combat_victories", 0) or 0),
            "town_work_completed": bool(
                getattr(self.state, "completed_town_project_ids", [])
                or getattr(self.state, "completed_bulletin_job_ids", [])
                or getattr(self.state, "completed_resident_request_ids", [])
            ),
        }
        context.update(claim_context)
        context.update(child_context)
        context.update(calendar_context)
        return context

    def dialogue_categories_for_npc(self, npc: Dict[str, object], immediate_category: str = "") -> List[str]:
        context = self.dialogue_context_for_npc(npc)
        categories: List[str] = []

        def add(category: str):
            if category and category not in categories:
                categories.append(category)

        add(immediate_category)
        add(str(context.get("gift_category", "")))
        if context.get("npc_birthday"):
            add("birthday")
        if context.get("player_birthday"):
            add("player_birthday")
        if context.get("festival"):
            add("festival_day")
        if context.get("spouse"):
            add("spouse")
        elif context.get("dating"):
            add("dating")
        if context.get("marriage_anniversary"):
            add("marriage_anniversary")
        if context.get("player_married") and not context.get("spouse"):
            add("player_married")
        if context.get("spouse_at_home") and not context.get("spouse"):
            add("spouse_at_home")
        if context.get("pregnancy"):
            if context.get("pregnancy_checkup_due"):
                add("pregnancy_checkup_due")
            month = int(context.get("pregnancy_month", 0) or 0)
            if month >= 7:
                add("pregnancy_late")
            elif month >= 4:
                add("pregnancy_mid")
            else:
                add("pregnancy_early")
            add("pregnancy")
        if context.get("children"):
            if context.get("child_birthday_today"):
                add("child_birthday_today")
            stage = str(context.get("youngest_child_stage", ""))
            if stage in ["Newborn", "Infant"]:
                add("child_newborn")
            elif stage in ["Toddler", "Young Child"]:
                add("child_young")
            elif stage in ["Child"]:
                add("child_school_age")
            elif stage in ["Teen", "Young Adult"]:
                add("child_teen")
            add("child_related")
        if int(context.get("family_bond_score", 0) or 0) >= 90:
            add("family_bond_high")
        if context.get("family_last_meal"):
            add("family_meal_recent")
        if int(context.get("owned_claim_count", 0) or 0) >= 1:
            add("land_claim_many" if int(context.get("owned_claim_count", 0) or 0) >= 2 else "land_claim_owned")
        if int(context.get("automation_count", 0) or 0) >= 1:
            add("automation_active")
        if context.get("house_comfortable"):
            add("house_comfortable")
        if int(context.get("mine_combat_victories", 0) or 0) >= 1:
            add("combat_victory")
        if int(context.get("combat_level", 1) or 1) >= 3:
            add("combat_level")
        deepest_floor = int(context.get("deepest_mine_floor", 1) or 1)
        if deepest_floor >= 10:
            add("mine_deep")
        elif deepest_floor >= 3:
            add("mine_depth")
        combat_started = bool(
            int(context.get("deepest_mine_floor", 1) or 1) >= 3
            or int(context.get("mine_combat_victories", 0) or 0) >= 1
            or int(context.get("combat_level", 1) or 1) >= 2
        )
        if context.get("mine_hazard") and combat_started:
            add("mine_hazard_day")
        if context.get("seasonal_contract") and combat_started:
            add("combat_contract_day")
        if context.get("market_day"):
            add("market_day")
        if context.get("storm_warning"):
            add("storm_warning")
        if context.get("story_flag"):
            add("quest_or_story_flag_related")
        if context.get("town_work_completed"):
            add("town_work_completed")
        add(str(context.get("relationship_category", "")))
        add(str(context.get("weather", "")))
        add(str(context.get("season", "")))
        add(str(context.get("time", "")))
        add("daily_generic")
        add("legacy_talk")
        return categories

    def stable_dialogue_line_id(self, npc_id: str, category: str, text: str) -> str:
        clean = []
        for ch in str(text).lower():
            clean.append(ch if ch.isalnum() else "_")
        slug = "_".join("".join(clean).split("_"))[:40] or "line"
        checksum = sum((index + 1) * ord(ch) for index, ch in enumerate(str(text))) % 100000
        return f"{npc_id}:{category}:{checksum}:{slug}"

    def dialogue_entry_from_raw(self, npc_id: str, category: str, index: int, raw: object) -> Optional[Dict[str, str]]:
        try:
            if isinstance(raw, dict):
                text = str(raw.get("text", "")).strip()
                line_id = str(raw.get("id", "")).strip()
            else:
                text = str(raw).strip()
                line_id = ""
            if not text:
                return None
            if not line_id:
                line_id = self.stable_dialogue_line_id(npc_id, category, text)
            return {"id": line_id, "text": text, "category": category}
        except Exception:
            return None

    def contextual_dialogue_entries_for_category(self, npc: Dict[str, object], category: str) -> List[Dict[str, str]]:
        npc_id = str(npc.get("id", ""))
        data = TOWN_NPC_CONTEXTUAL_DIALOGUE_DATA.get(npc_id, {})
        if not isinstance(data, dict):
            data = {}
        curated_pool = self.curated_dialogue_lines_for_category(npc, category)
        authored_pool = data.get(category, [])
        if isinstance(authored_pool, (str, dict)):
            authored_pool = [authored_pool]
        if not isinstance(authored_pool, list):
            authored_pool = []
        # Character-specific writing must win. The shared contextual pool is a
        # fallback only; it previously replaced authored lines for every common
        # season/weather/story category, making all 26 residents sound alike
        # despite their large individual dialogue catalogs.
        raw_pool = list(authored_pool) if authored_pool else list(curated_pool)
        if category == "legacy_talk":
            legacy_data = self.town_npc_dialogue_data(npc)
            raw_pool = legacy_data.get("talk", [])
        if isinstance(raw_pool, (str, dict)):
            raw_pool = [raw_pool]
        if not isinstance(raw_pool, list):
            return []
        entries: List[Dict[str, str]] = []
        for index, raw in enumerate(raw_pool):
            entry = self.dialogue_entry_from_raw(npc_id, category, index, raw)
            if entry and not self.low_quality_dialogue_text(str(entry.get("text", ""))):
                entries.append(entry)
        dynamic_entries = self.dynamic_contextual_dialogue_entries_for_category(npc, category)
        for entry in dynamic_entries:
            if entry and entry.get("id") not in {existing.get("id") for existing in entries}:
                entries.append(entry)
        return entries

    def recent_dialogue_ids_for_npc(self, npc_id: str) -> List[str]:
        if not isinstance(self.state.town_npc_recent_dialogue_ids, dict):
            self.state.town_npc_recent_dialogue_ids = {}
        recent = self.state.town_npc_recent_dialogue_ids.get(str(npc_id), [])
        if not isinstance(recent, list):
            recent = []
        recent = [str(line_id) for line_id in recent[-8:] if line_id is not None]
        self.state.town_npc_recent_dialogue_ids[str(npc_id)] = recent
        return recent

    def remember_npc_dialogue_line(self, npc_id: str, line_id: str):
        npc_id = str(npc_id)
        line_id = str(line_id or "")
        if not line_id:
            return
        recent = [existing for existing in self.recent_dialogue_ids_for_npc(npc_id) if existing != line_id]
        recent.append(line_id)
        self.state.town_npc_recent_dialogue_ids[npc_id] = recent[-8:]

    def choose_npc_dialogue(self, npc: Dict[str, object], immediate_category: str = "", remember: bool = True) -> Dict[str, str]:
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        try:
            categories = self.dialogue_categories_for_npc(npc, immediate_category)
            recent = set(self.recent_dialogue_ids_for_npc(npc_id))
            first_any: Optional[Dict[str, str]] = None
            for category in categories:
                entries = self.contextual_dialogue_entries_for_category(npc, category)
                if not entries:
                    continue
                if first_any is None:
                    first_any = entries[0]
                fresh = [entry for entry in entries if entry["id"] not in recent]
                if not fresh:
                    continue
                candidates = fresh
                seed_text = f"{self.town_npc_day_key()}:{npc_id}:{category}:{self.state.hour}:{self.state.minute}:{len(recent)}"
                index = sum(ord(ch) for ch in seed_text) % len(candidates)
                chosen = candidates[index]
                if remember:
                    self.remember_npc_dialogue_line(npc_id, chosen["id"])
                return chosen
            if first_any:
                if remember:
                    self.remember_npc_dialogue_line(npc_id, first_any["id"])
                return first_any
        except Exception as exc:
            append_debug_log(f"Dialogue selection fallback for {npc_id}: {type(exc).__name__}: {exc}")

        activity = self.town_npc_activity_label(npc)
        fallback = str(self.town_npc_daily_pick(npc, "fallback_talk", [
            f"I am {activity.replace('their ', 'my ')}. What did you want to ask about?",
            self.town_npc_work_insight(npc),
            f"This part of the day usually finds me {activity.replace('their ', 'my ')}.",
            f"You caught me near {self.town_npc_location_label(npc)}. I have a moment to talk.",
        ]) or "I have a moment to talk.")
        line_id = self.stable_dialogue_line_id(npc_id, "fallback", fallback)
        if remember:
            self.remember_npc_dialogue_line(npc_id, line_id)
        return {"id": line_id, "text": fallback, "category": "fallback"}

    def eligible_relationship_milestone_event(self, npc: Dict[str, object]) -> Tuple[str, Dict[str, object]]:
        npc_id = str(npc.get("id", ""))
        events = RELATIONSHIP_MILESTONE_EVENTS.get(npc_id, {})
        if not isinstance(events, dict):
            return "", {}
        points = self.town_npc_relationship(npc_id)
        talks = int(self.state.town_npc_dialogue_counts.get(npc_id, 0))
        for milestone in ["close_friend", "trusted"]:
            event = events.get(milestone, {})
            if not isinstance(event, dict):
                continue
            if self.has_relationship_milestone(npc_id, milestone):
                continue
            if points < int(event.get("requires_points", 0)):
                continue
            if talks < int(event.get("requires_talks", 0)):
                continue
            return milestone, event
        return "", {}

    def try_relationship_milestone_event(self, npc: Dict[str, object]) -> List[str]:
        npc_id = str(npc.get("id", ""))
        try:
            milestone, event = self.eligible_relationship_milestone_event(npc)
            if not milestone or not event:
                return []
            self.set_relationship_milestone(npc_id, milestone)
            bonus = int(event.get("bonus", 0) or 0)
            actual_bonus = self.adjust_town_npc_relationship(npc_id, bonus) if bonus else 0
            title = str(event.get("title", "Relationship Moment"))
            lines = [title, ""]
            raw_lines = event.get("lines", [])
            if isinstance(raw_lines, list):
                lines.extend(str(line) for line in raw_lines if str(line).strip())
            if actual_bonus > 0:
                lines.extend(["", f"Relationship +{actual_bonus}."])
            if milestone == "close_friend":
                lines.append("Close Friend tier can now be reached.")
            elif milestone == "trusted":
                lines.append("Trusted and deeper tiers can now be reached.")
            return lines
        except Exception as exc:
            append_debug_log(f"Relationship milestone fallback for {npc_id}: {type(exc).__name__}: {exc}")
            return []

    def scene_catalog(self) -> Dict[str, Dict[str, object]]:
        scenes: Dict[str, Dict[str, object]] = {}
        for npc_id, milestone_events in RELATIONSHIP_MILESTONE_EVENTS.items():
            if not isinstance(milestone_events, dict):
                continue
            npc_name = self.town_npc_name(npc_id)
            for milestone, event in milestone_events.items():
                if not isinstance(event, dict):
                    continue
                scene_id = f"npc_milestone:{npc_id}:{milestone}"
                required_milestones = ["close_friend"] if milestone == "trusted" else []
                raw_lines = event.get("lines", [])
                narrator_steps = [
                    {"type": "narration", "text": str(line)}
                    for line in raw_lines
                    if str(line).strip()
                ]
                quote = RELATIONSHIP_MILESTONE_SCENE_QUOTES.get((npc_id, str(milestone)), "")
                steps: List[Dict[str, object]] = narrator_steps
                if quote:
                    steps.append({"type": "dialogue", "speaker": npc_name, "text": quote})
                theme_flag = RELATIONSHIP_MILESTONE_THEME_FLAGS.get((npc_id, str(milestone)), "")
                steps.append(
                    {"type": "set_npc_milestone", "npc_id": npc_id, "milestone": str(milestone)},
                )
                if theme_flag:
                    steps.extend([
                        {"type": "set_npc_milestone", "npc_id": npc_id, "milestone": theme_flag},
                        {"type": "set_flag", "flag": f"npc_milestone:{npc_id}:{theme_flag}"},
                    ])
                steps.extend([
                    {"type": "relationship", "npc_id": npc_id, "amount": int(event.get("bonus", 0) or 0)},
                    {"type": "set_flag", "flag": f"scene_flag:{scene_id}"},
                    {"type": "message", "text": f"{npc_name}'s relationship milestone advanced."},
                ])
                scenes[scene_id] = {
                    "id": scene_id,
                    "title": f"{npc_name}: {event.get('title', 'Relationship Moment')}",
                    "completion_flag": scene_id,
                    "repeatable": False,
                    "priority": 120 if milestone == "trusted" else 110,
                    "trigger": {
                        "npc_id": npc_id,
                        "min_relationship": int(event.get("requires_points", 0) or 0),
                        "min_talks": int(event.get("requires_talks", 0) or 0),
                        "required_milestones": required_milestones,
                        "blocked_milestones": [str(milestone)],
                    },
                    "steps": steps,
                }
        scenes.update(self.life_event_scene_catalog())
        return scenes

    def life_event_scene_catalog(self) -> Dict[str, Dict[str, object]]:
        scenes: Dict[str, Dict[str, object]] = {}

        def add_scene(
            key: str,
            title: str,
            trigger: Dict[str, object],
            steps: List[Dict[str, object]],
            priority: int = 125,
        ):
            scene_id = f"life:{key}"
            final_steps = list(steps)
            final_steps.extend([
                {"type": "set_flag", "flag": f"scene_flag:{scene_id}"},
                {"type": "message", "text": f"{title} recorded."},
            ])
            scenes[scene_id] = {
                "id": scene_id,
                "title": title,
                "completion_flag": scene_id,
                "repeatable": False,
                "priority": priority,
                "trigger": trigger,
                "steps": final_steps,
            }

        spouse_id = str(getattr(self.state, "spouse_npc_id", "") or "")
        spouse_name = self.town_npc_name(spouse_id) if spouse_id else "your spouse"

        if spouse_id:
            add_scene(
                "spouse_move_in",
                "A Home Shared",
                {"npc_id": spouse_id, "spouse": True, "spouse_moved_to_farm": True},
                [
                    {
                        "type": "narration",
                        "text": "The farmhouse feels different once another daily route begins and ends at the same door.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "I moved my things in, but I do not want this to feel like I arrived finished. We can decide what home becomes from here.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 5},
                ],
                priority=150,
            )
            add_scene(
                "first_family_meal",
                "The First Shared Table",
                {"npc_id": spouse_id, "spouse": True, "spouse_moved_to_farm": True, "family_last_meal": True},
                [
                    {
                        "type": "narration",
                        "text": "A meal at home turns the room from useful shelter into a place with memory.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "This is small, but it matters. Food, a table, and a minute where nothing needs fixing immediately.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 4},
                ],
                priority=145,
            )
            add_scene(
                "expecting_household",
                "Planning Room For More",
                {"npc_id": spouse_id, "spouse": True, "pregnancy": True},
                [
                    {
                        "type": "narration",
                        "text": "The farmhouse ledger gains a new kind of entry: space, time, care, and all the ordinary logistics of becoming a larger household.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "Nine months is a long promise. I want us to use it well, not rush through it because the calendar says we can.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 5},
                ],
                priority=148,
            )
            add_scene(
                "first_child_home",
                "A New Voice At Home",
                {"npc_id": spouse_id, "spouse": True, "children": True},
                [
                    {
                        "type": "narration",
                        "text": "The farmhouse sounds different now: softer footsteps, new schedules, and the small gravity of a child living under the same roof.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "We are going to learn this one day at a time. That is probably the only honest way to do it.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 6},
                ],
                priority=152,
            )
            add_scene(
                "rooted_household",
                "A Rooted Household",
                {"npc_id": spouse_id, "spouse": True, "min_family_bond": 90},
                [
                    {
                        "type": "narration",
                        "text": "After enough shared routines, home stops being a project and starts becoming something that catches everyone when the day is heavy.",
                    },
                    {
                        "type": "dialogue",
                        "speaker": spouse_name,
                        "text": "I can feel it now. The house is not just where we recover from work. It is part of why the work feels worth doing.",
                    },
                    {"type": "relationship", "npc_id": spouse_id, "amount": 5},
                ],
                priority=135,
            )

        add_scene(
            "first_land_claim",
            "The First Deed",
            {"npc_id": "eli_carpenter", "min_owned_claims": 1},
            [
                {
                    "type": "dialogue",
                    "speaker": "Eli",
                    "text": "A raw claim is not a farm yet. Good. That means it is still yours to shape instead of something you are forced to inherit.",
                },
                {
                    "type": "narration",
                    "text": "Eli sketches a rough access line and marks where a workshop crew could deliver materials without taking over the land.",
                },
                {"type": "relationship", "npc_id": "eli_carpenter", "amount": 4},
            ],
            priority=132,
        )
        add_scene(
            "first_mine_victory",
            "After The First Fight",
            {"npc_id": "brom_smith", "min_mine_combat_victories": 1},
            [
                {
                    "type": "dialogue",
                    "speaker": "Brom",
                    "text": "You came back breathing and with your head still on. That is the first useful combat lesson. The second is learning why it worked.",
                },
                {
                    "type": "narration",
                    "text": "Brom checks your gear for cracked edges and notes which repairs should be routine after mine fights.",
                },
                {"type": "relationship", "npc_id": "brom_smith", "amount": 4},
            ],
            priority=131,
        )
        add_scene(
            "first_automation_machine",
            "A Machine Joins The Farm",
            {"npc_id": "jules_mechanic", "min_automation_machines": 1},
            [
                {
                    "type": "dialogue",
                    "speaker": "Jules",
                    "text": "That is the good kind of machine: boring when it works, obvious when it needs attention, and never mysterious on purpose.",
                },
                {
                    "type": "narration",
                    "text": "Jules draws a maintenance mark in the corner of the plan, then circles the part that should stay reachable.",
                },
                {"type": "relationship", "npc_id": "jules_mechanic", "amount": 4},
            ],
            priority=130,
        )
        add_scene(
            "deep_mine_report",
            "The Mine Gets Serious",
            {"npc_id": "garrick_miner", "min_deepest_mine_floor": 5},
            [
                {
                    "type": "dialogue",
                    "speaker": "Garrick",
                    "text": "Past the first few floors, the mine stops testing whether you are brave and starts testing whether you pay attention.",
                },
                {
                    "type": "narration",
                    "text": "Garrick marks a few danger signs in your route notes: fresh cracks, echo changes, and floors that sound hollow under a boot.",
                },
                {"type": "relationship", "npc_id": "garrick_miner", "amount": 4},
            ],
            priority=129,
        )
        return scenes

    def scene_by_id(self, scene_id: str) -> Dict[str, object]:
        scene = self.scene_catalog().get(str(scene_id), {})
        return scene if isinstance(scene, dict) else {}

    def scene_is_completed(self, scene_or_id: object) -> bool:
        scene = self.scene_by_id(str(scene_or_id)) if isinstance(scene_or_id, str) else scene_or_id
        if not isinstance(scene, dict) or not scene:
            return False
        if bool(scene.get("repeatable", False)):
            return False
        scene_id = str(scene.get("id", ""))
        completion_flag = str(scene.get("completion_flag", scene_id))
        completed = set(str(x) for x in (self.state.completed_scene_ids or []))
        return scene_id in completed or completion_flag in completed

    def mark_scene_seen(self, scene_id: str):
        scene_id = str(scene_id)
        if scene_id and scene_id not in set(self.state.seen_scene_ids or []):
            self.state.seen_scene_ids.append(scene_id)

    def mark_scene_completed(self, scene: Dict[str, object]):
        scene_id = str(scene.get("id", ""))
        completion_flag = str(scene.get("completion_flag", scene_id))
        for value in [scene_id, completion_flag]:
            if value and value not in set(self.state.completed_scene_ids or []):
                self.state.completed_scene_ids.append(value)

    def scene_conditions_met(self, scene: Dict[str, object], context: Optional[Dict[str, object]] = None) -> bool:
        context = context or {}
        try:
            if not isinstance(scene, dict) or not scene.get("id"):
                return False
            if self.scene_is_completed(scene):
                return False
            trigger = scene.get("trigger", {}) or {}
            if not isinstance(trigger, dict):
                return False
            completed_scenes = set(str(x) for x in (self.state.completed_scene_ids or []))
            scene_flags = set(str(x) for x in (self.state.scene_flags or [])) | completed_scenes
            completed_projects = set(str(x) for x in (self.state.completed_town_project_ids or []))

            npc_id = str(trigger.get("npc_id", ""))
            context_npc_id = str(context.get("npc_id", ""))
            if npc_id and context_npc_id and npc_id != context_npc_id:
                return False

            locations = trigger.get("locations", trigger.get("location", None))
            if isinstance(locations, str):
                locations = [locations]
            if isinstance(locations, list) and locations and self.state.location not in [str(location) for location in locations]:
                return False

            seasons = trigger.get("seasons", trigger.get("season", None))
            if isinstance(seasons, str):
                seasons = [seasons]
            if isinstance(seasons, list) and seasons and self.state.season not in [str(season) for season in seasons]:
                return False

            weather = trigger.get("weather", None)
            if isinstance(weather, str):
                weather = [weather]
            if isinstance(weather, list) and weather and str(self.state.weather) not in [str(value) for value in weather]:
                return False

            times = trigger.get("time", trigger.get("times", None))
            if isinstance(times, str):
                times = [times]
            if isinstance(times, list) and times and self.time_dialogue_category() not in [str(value) for value in times]:
                return False

            months = trigger.get("months", trigger.get("month", None))
            if months is not None:
                if not isinstance(months, (list, tuple, set)):
                    months = [months]
                if int(self.state.month) not in [int(value) for value in months]:
                    return False
            days = trigger.get("days", trigger.get("day", None))
            if days is not None:
                if not isinstance(days, (list, tuple, set)):
                    days = [days]
                if int(self.state.day) not in [int(value) for value in days]:
                    return False
            dates = trigger.get("dates", trigger.get("date", None))
            if dates is not None:
                if not isinstance(dates, (list, tuple, set)):
                    dates = [dates]
                today_values = {
                    f"{int(self.state.month)}-{int(self.state.day)}",
                    f"{int(self.state.month)}/{int(self.state.day)}",
                    f"{int(self.state.year)}-{int(self.state.month)}-{int(self.state.day)}",
                    format_date(int(self.state.month), int(self.state.day), int(self.state.year)),
                }
                if not any(str(value) in today_values for value in dates):
                    return False

            if "festival" in trigger and bool(trigger.get("festival")) != bool(self.todays_festival_id()):
                return False
            festival_ids = trigger.get("festival_ids", trigger.get("festival_id", None))
            if festival_ids is not None:
                if not isinstance(festival_ids, (list, tuple, set)):
                    festival_ids = [festival_ids]
                if str(self.todays_festival_id() or "") not in [str(value) for value in festival_ids]:
                    return False

            if npc_id:
                npc = context.get("npc")
                if not isinstance(npc, dict):
                    npc = next((n for n in self.state.town_npcs if str(n.get("id", "")) == npc_id), {})
                if int(trigger.get("min_relationship", -999999)) > self.town_npc_relationship(npc_id):
                    return False
                if int(trigger.get("min_talks", 0)) > int(self.state.town_npc_dialogue_counts.get(npc_id, 0)):
                    return False
                tier = str(trigger.get("relationship_tier", ""))
                if tier and isinstance(npc, dict) and self.relationship_tier_for_npc(npc) != tier:
                    return False
                for milestone in trigger.get("required_milestones", []) or []:
                    if not self.has_relationship_milestone(npc_id, str(milestone)):
                        return False
                for milestone in trigger.get("blocked_milestones", []) or []:
                    if self.has_relationship_milestone(npc_id, str(milestone)):
                        return False
                if "dating" in trigger and bool(trigger.get("dating")) != (npc_id in set(self.state.dating_npc_ids or [])):
                    return False
                if "spouse" in trigger and bool(trigger.get("spouse")) != (self.state.spouse_npc_id == npc_id):
                    return False

            for flag in trigger.get("required_flags", []) or []:
                if str(flag) not in scene_flags:
                    return False
            for flag in trigger.get("blocked_flags", []) or []:
                if str(flag) in scene_flags:
                    return False

            for scene_id in trigger.get("required_completed_scenes", trigger.get("completed_scenes", [])) or []:
                if str(scene_id) not in completed_scenes:
                    return False
            for scene_id in trigger.get("blocked_completed_scenes", trigger.get("unfinished_scenes", [])) or []:
                if str(scene_id) in completed_scenes:
                    return False

            for project_id in trigger.get("required_town_projects", trigger.get("completed_town_projects", [])) or []:
                if str(project_id) not in completed_projects:
                    return False
            for project_id in trigger.get("blocked_town_projects", trigger.get("unfinished_town_projects", [])) or []:
                if str(project_id) in completed_projects:
                    return False

            if "pregnancy" in trigger and bool(trigger.get("pregnancy")) != bool(self.state.pregnancy_active):
                return False
            if "children" in trigger and bool(trigger.get("children")) != bool(self.state.children):
                return False
            if "spouse_moved_to_farm" in trigger and bool(trigger.get("spouse_moved_to_farm")) != bool(getattr(self.state, "spouse_moved_to_farm", False)):
                return False
            if int(trigger.get("min_children", 0) or 0) > len(getattr(self.state, "children", []) or []):
                return False
            if int(trigger.get("min_family_bond", 0) or 0) > self.family_bond_score():
                return False
            claims = getattr(self.state, "owned_wilderness_claims", {}) or {}
            claim_count = len(claims) if isinstance(claims, dict) else 0
            if int(trigger.get("min_owned_claims", 0) or 0) > claim_count:
                return False
            automation = getattr(self.state, "automation_machines", {}) or {}
            automation_count = len(automation) if isinstance(automation, dict) else 0
            if int(trigger.get("min_automation_machines", 0) or 0) > automation_count:
                return False
            if int(trigger.get("min_mine_combat_victories", 0) or 0) > int(getattr(self.state, "mine_combat_victories", 0) or 0):
                return False
            if int(trigger.get("min_deepest_mine_floor", 0) or 0) > int(getattr(self.state, "deepest_mine_floor", 1) or 1):
                return False
            if trigger.get("family_last_meal") and not str(getattr(self.state, "family_last_meal", "") or ""):
                return False

            inventory = trigger.get("inventory_contains", {}) or {}
            if isinstance(inventory, dict):
                for item, qty in inventory.items():
                    if int(self.state.inventory.get(str(item), 0)) < int(qty):
                        return False
            elif isinstance(inventory, str):
                if int(self.state.inventory.get(inventory, 0)) <= 0:
                    return False
            elif isinstance(inventory, (list, tuple, set)):
                for item in inventory:
                    if int(self.state.inventory.get(str(item), 0)) <= 0:
                        return False
            return True
        except Exception as exc:
            append_debug_log(f"Scene condition fallback: {type(exc).__name__}: {exc}")
            return False

    def eligible_scenes_for_context(self, context: Optional[Dict[str, object]] = None) -> List[Dict[str, object]]:
        context = context or {}
        scenes: List[Dict[str, object]] = []
        for scene in self.scene_catalog().values():
            if self.scene_conditions_met(scene, context):
                scenes.append(scene)
        scenes.sort(key=lambda scene: int(scene.get("priority", 0)), reverse=True)
        return scenes

    def validate_active_scene_state(self):
        if not self.state.active_scene_id:
            self.state.active_scene_step_index = 0
            return
        scene = self.scene_by_id(self.state.active_scene_id)
        steps = scene.get("steps", []) if isinstance(scene, dict) else []
        if not scene or not isinstance(steps, list) or self.state.active_scene_step_index >= len(steps):
            append_debug_log(f"Cancelled invalid active scene: {self.state.active_scene_id}")
            self.state.active_scene_id = ""
            self.state.active_scene_step_index = 0

    def start_scene(self, scene_or_id: object) -> bool:
        scene = self.scene_by_id(str(scene_or_id)) if isinstance(scene_or_id, str) else scene_or_id
        if not isinstance(scene, dict) or not scene.get("id"):
            append_debug_log(f"Invalid scene start request: {scene_or_id}")
            return False
        if self.scene_is_completed(scene):
            append_debug_log(f"Scene already completed: {scene.get('id')}")
            return False
        steps = scene.get("steps", [])
        if not isinstance(steps, list) or not steps:
            append_debug_log(f"Scene has no valid steps: {scene.get('id')}")
            return False
        self.state.active_scene_id = str(scene.get("id", ""))
        self.state.active_scene_step_index = 0
        self.mark_scene_seen(self.state.active_scene_id)
        append_debug_log(f"Starting scene: {self.state.active_scene_id}")
        return True

    def current_scene(self) -> Dict[str, object]:
        self.validate_active_scene_state()
        return self.scene_by_id(self.state.active_scene_id) if self.state.active_scene_id else {}

    def current_scene_step(self) -> Dict[str, object]:
        scene = self.current_scene()
        steps = scene.get("steps", []) if scene else []
        try:
            step = steps[int(self.state.active_scene_step_index)]
            return step if isinstance(step, dict) else {}
        except Exception:
            return {}

    def step_is_visible_scene_text(self, step: Dict[str, object]) -> bool:
        return str(step.get("type", "")) in ["dialogue", "narration", "text"]

    def advance_scene_to_visible_step(self) -> bool:
        while self.state.active_scene_id:
            step = self.current_scene_step()
            if step and self.step_is_visible_scene_text(step):
                return True
            if not self.advance_scene() and not self.state.active_scene_id:
                return False
        return False

    def apply_scene_step_effect(self, scene: Dict[str, object], step: Dict[str, object]):
        step_type = str(step.get("type", ""))
        try:
            if step_type == "relationship":
                self.adjust_town_npc_relationship(str(step.get("npc_id", "")), int(step.get("amount", 0)))
            elif step_type == "give_item":
                item = str(step.get("item", ""))
                qty = int(step.get("qty", 1))
                if item and qty > 0:
                    self.state.inventory[item] = int(self.state.inventory.get(item, 0)) + qty
            elif step_type == "remove_item":
                item = str(step.get("item", ""))
                qty = int(step.get("qty", 1))
                if item and qty > 0:
                    self.state.inventory[item] = max(0, int(self.state.inventory.get(item, 0)) - qty)
            elif step_type == "set_flag":
                flag = str(step.get("flag", ""))
                if flag and flag not in set(self.state.scene_flags or []):
                    self.state.scene_flags.append(flag)
            elif step_type == "set_npc_milestone":
                npc_id = str(step.get("npc_id", ""))
                milestone = str(step.get("milestone", ""))
                if npc_id and milestone:
                    self.set_relationship_milestone(npc_id, milestone)
            elif step_type == "unlock_recipe":
                recipe_id = str(step.get("recipe_id", ""))
                if recipe_id and recipe_id not in set(self.state.learned_recipe_ids or []):
                    self.state.learned_recipe_ids.append(recipe_id)
            elif step_type == "message":
                self.state.message = str(step.get("text", self.state.message))
            elif step_type == "position":
                location = str(step.get("location", ""))
                if location in VALID_GAME_LOCATIONS:
                    self.state.location = location
                if "x" in step and "y" in step:
                    self.state.player_x = int(step.get("x", self.state.player_x))
                    self.state.player_y = int(step.get("y", self.state.player_y))
        except Exception as exc:
            append_debug_log(f"Scene step effect skipped for {scene.get('id', '')}: {type(exc).__name__}: {exc}")

    def complete_scene(self, scene: Dict[str, object]):
        self.mark_scene_completed(scene)
        append_debug_log(f"Completed scene: {scene.get('id', '')}")
        self.state.active_scene_id = ""
        self.state.active_scene_step_index = 0

    def advance_scene(self) -> bool:
        scene = self.current_scene()
        if not scene:
            return False
        steps = scene.get("steps", [])
        if not isinstance(steps, list):
            self.complete_scene(scene)
            return False
        while self.state.active_scene_step_index < len(steps):
            step = steps[self.state.active_scene_step_index]
            if isinstance(step, dict):
                self.apply_scene_step_effect(scene, step)
            self.state.active_scene_step_index += 1
            if self.state.active_scene_step_index >= len(steps):
                self.complete_scene(scene)
                return False
            next_step = steps[self.state.active_scene_step_index]
            if isinstance(next_step, dict) and self.step_is_visible_scene_text(next_step):
                return True
        self.complete_scene(scene)
        return False

    def draw_scene(self):
        if not self.advance_scene_to_visible_step():
            return
        scene = self.current_scene()
        step = self.current_scene_step()
        self.invalidate_draw_cache()
        clear_screen()
        title = str(scene.get("title", "Scene"))
        step_type = str(step.get("type", "narration"))
        speaker = str(step.get("speaker", "Narrator" if step_type != "dialogue" else ""))
        text = str(step.get("text", ""))
        width = 68
        self.centered_print("+" + "-" * width + "+", width + 2)
        self.centered_print("|" + pad_to(title.center(width), width) + "|", width + 2)
        self.centered_print("+" + "-" * width + "+", width + 2)
        if speaker:
            self.centered_print("|" + pad_to(speaker, width) + "|", width + 2)
            self.centered_print("+" + "-" * width + "+", width + 2)
        for line in textwrap.wrap(text, width=width - 4) or [""]:
            self.centered_print("|" + pad_to("  " + line, width) + "|", width + 2)
        self.centered_print("+" + "-" * width + "+", width + 2)
        self.centered_print("|" + pad_to("Enter/Space/E/Z continue", width) + "|", width + 2)
        self.centered_print("+" + "-" * width + "+", width + 2)

    def handle_scene_key(self, key: str) -> bool:
        key = normalize_key(key)
        if key in MENU_CONFIRM_KEYS:
            return self.advance_scene()
        return True

    def play_scene(self, scene_or_id: object) -> bool:
        if not self.start_scene(scene_or_id):
            return False
        while self.state.active_scene_id:
            if not self.advance_scene_to_visible_step():
                continue
            self.draw_scene()
            self.handle_scene_key(read_key())
        self.invalidate_draw_cache()
        return True

    def maybe_play_scene_for_context(self, context: Dict[str, object]) -> bool:
        try:
            scenes = self.eligible_scenes_for_context(context)
            if not scenes:
                return False
            return self.play_scene(scenes[0])
        except Exception as exc:
            append_debug_log(f"Scene context fallback: {type(exc).__name__}: {exc}")
            return False

    def town_npc_dialogue_lines(self, npc: Dict[str, object], first_talk_today: Optional[bool] = None) -> List[str]:
        conversation = self.town_npc_role_dialogue_lines(npc)
        if not conversation:
            conversation = [f'"{self.town_npc_work_insight(npc)}"']
        context_lines: List[str] = []
        occasion = self.todays_town_public_occasion()
        if occasion:
            context_lines.append(f'"Today everyone is adjusting around {occasion["name"]} at {occasion["location"]}."')
        partner_id = str(npc.get("social_partner_id", ""))
        if partner_id:
            partner = self.npc_record_by_id(partner_id)
            if partner:
                link = self.town_npc_social_link_label(str(npc.get("id", "")), partner_id)
                context_lines.append(f'"{partner.get("name", "A neighbor")} and I have become {link} through our repeated meetings."')
        return [
            self.town_npc_context_line(npc),
            "",
            *conversation,
            *(["", *context_lines] if context_lines else []),
            "",
            f'"{self.town_npc_work_insight(npc)}"',
        ]

    def regional_visitor_bond_label(self, value: int) -> str:
        if value >= 12:
            return "Trusted Route Friend"
        if value >= 6:
            return "Familiar Traveler"
        if value >= 2:
            return "Recognized Visitor"
        return "New Arrival"

    def regional_visitor_stock(self, visitor: Dict[str, object]) -> List[Dict[str, object]]:
        role = str(visitor.get("role", "Traveler"))
        items = list(visitor.get("origin_exports", []) or [])
        items.extend({
            "Traveling Merchant": ["Field Snack", "Wild Herbs"],
            "Herbalist": ["Wild Herbs", "Cave Herbs"],
            "Prospector": ["Stone", "Coal"],
            "Performer": ["Honey"],
            "Ranger": ["Field Snack", "Fiber"],
        }.get(role, []))
        stock = []
        for item in list(dict.fromkeys(str(item) for item in items if str(item or "").strip()))[:5]:
            base = int(self.shippable_unit_price(item)) if hasattr(self, "shippable_unit_price") else 0
            price = max(20, base * 2 if base else 45)
            stock.append({"item": item, "price": price, "note": f"Carried from {visitor.get('origin', 'the region')}"})
        return stock

    def regional_visitor_purchase_key(self, visitor: Dict[str, object], item: str) -> str:
        return f"{self.town_npc_day_key()}:{visitor.get('id', 'visitor')}:{item}"

    def regional_visitor_goods_menu(self, visitor: Dict[str, object]):
        stock = self.regional_visitor_stock(visitor)
        life = self.regional_town_life_state()
        counts = life.setdefault("visitor_purchase_counts", {})
        items = []
        for record in stock:
            key = self.regional_visitor_purchase_key(visitor, str(record["item"]))
            sold = int(counts.get(key, 0) or 0) >= 1
            items.append(MenuItem(
                label=f"{record['item']} - {record['price']}g",
                value=str(record["item"]), enabled=not sold and int(self.state.money) >= int(record["price"]),
                hint="Sold today" if sold else str(record["note"]),
            ))
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = self.vertical_panel_select("Origin Goods", items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
        if not choice or choice.value == MENU_BACK:
            return
        record = next((row for row in stock if str(row["item"]) == str(choice.value)), None)
        if not record:
            return
        price = int(record["price"])
        key = self.regional_visitor_purchase_key(visitor, str(record["item"]))
        if int(self.state.money) < price or int(counts.get(key, 0) or 0) >= 1:
            self.set_message("That origin good is no longer available today.")
            return
        self.state.money -= price
        add_inventory_items(self.state.inventory, {str(record["item"]): 1})
        counts[key] = 1
        self.autosave_with_message(f"Bought {record['item']} from {visitor.get('name', 'the traveler')} for {price}g.")

    def regional_origin_chart_unknown_count(self, visitor: Dict[str, object]) -> int:
        cx, cy = int(visitor.get("origin_chunk_x", 0)), int(visitor.get("origin_chunk_y", 0))
        return sum(not self.wilderness_chunk_known(x, y) for x, y in self.wilderness_region_chunks(cx, cy))

    def purchase_regional_visitor_origin_chart(self, visitor: Dict[str, object]) -> bool:
        unknown = self.regional_origin_chart_unknown_count(visitor)
        if unknown <= 0:
            self.set_message(f"You already know the region around {visitor.get('origin', 'that origin')}.")
            return False
        price = 160 + min(240, int(visitor.get("distance_chunks", 0)) * 5)
        if int(self.state.money) < price:
            self.set_message(f"The origin chart costs {price}g.")
            return False
        cx, cy = int(visitor.get("origin_chunk_x", 0)), int(visitor.get("origin_chunk_y", 0))
        record = self.wilderness_region_record(cx, cy)
        mapped = record.setdefault("mapped_chunks", [])
        added = 0
        for x, y in self.wilderness_region_chunks(cx, cy):
            key = f"{x},{y}"
            if key not in mapped:
                mapped.append(key)
                added += 1
        self.state.money -= price
        self.autosave_with_message(f"Bought a chart of {visitor.get('origin', 'the origin region')} for {price}g; mapped {added} chunk(s).")
        return True

    def talk_to_regional_circulation_traveler(self, traveler: Dict[str, object]) -> bool:
        visitor_id = str(traveler.get("id", "regional_visitor"))
        if traveler.get("authored_resident_trip"):
            today = self.town_npc_day_key()
            if self.state.town_npc_last_talk_day.get(visitor_id) == today:
                self.set_message(f"{traveler.get('name', 'The resident')} has already caught up with you today.")
                return False
            self.state.town_npc_last_talk_day[visitor_id] = today
            gain = self.adjust_town_npc_relationship(visitor_id, RELATIONSHIP_TALK_GAIN)
            self.autosave_with_message(f"Met {traveler.get('name', 'a town resident')} on their regional errand. Relationship +{gain}.")
            return True
        life = self.regional_town_life_state()
        today = self.town_npc_day_key()
        last_talk = life.setdefault("visitor_last_talk_day", {}).get(visitor_id, "")
        if last_talk == today:
            self.set_message(f"{traveler.get('name', 'The traveler')} has already shared today's road news.")
            return False
        bonds = life.setdefault("visitor_bonds", {})
        bonds[visitor_id] = min(250, int(bonds.get(visitor_id, 0) or 0) + 1)
        life["visitor_last_talk_day"][visitor_id] = today
        memories = life.setdefault("visitor_memories", {}).setdefault(visitor_id, [])
        memories.append(f"{today}: Met on the road toward {traveler.get('route_destination_name', 'a regional destination')}.")
        life["visitor_memories"][visitor_id] = memories[-8:]
        self.autosave_with_message(f"Met {traveler.get('name', 'a familiar traveler')} on the regional road. Connection +1.")
        return True

    def assist_regional_circulation_traveler(self, traveler: Dict[str, object]) -> bool:
        traveler_id = str(traveler.get("id", "regional_visitor"))
        life = self.regional_town_life_state()
        assistance = life.setdefault("visitor_purchase_counts", {})
        key = f"assist:{self.town_npc_day_key()}:{traveler_id}"
        if int(assistance.get(key, 0) or 0) >= 1:
            self.set_message(f"You already helped {traveler.get('name', 'this traveler')} along the route today.")
            return False
        local_commute = bool(traveler.get("home_region_commute"))
        stamina_cost = 2 if local_commute else 4
        minutes = 20 if local_commute else 40
        reward = 20 if local_commute else 45
        vitality_gain = 1 if local_commute else 2
        if not self.spend_stamina(stamina_cost):
            return False
        self.advance_time(minutes)
        assistance[key] = 1
        traveler["route_condition"] = "Traveler Assisted"
        if traveler.get("authored_resident_trip"):
            gain = self.adjust_town_npc_relationship(traveler_id, 2)
            trip = life.setdefault("resident_trips", {}).get(traveler_id, {})
            if isinstance(trip, dict):
                trip["route_condition"] = "Traveler Assisted"
            connection_text = f"relationship +{gain}"
        else:
            bonds = life.setdefault("visitor_bonds", {})
            bonds[traveler_id] = min(250, int(bonds.get(traveler_id, 0) or 0) + 2)
            journey = life.setdefault("journeys", {}).get(traveler_id, {})
            if isinstance(journey, dict):
                journey["route_condition"] = "Traveler Assisted"
                if int(journey.get("arrival_hour", 8)) > int(self.state.hour):
                    journey["arrival_hour"] = max(int(self.state.hour) + 1, int(journey["arrival_hour"]) - 2)
            memories = life.setdefault("visitor_memories", {}).setdefault(traveler_id, [])
            memories.append(f"{self.town_npc_day_key()}: Escorted safely along the road toward {traveler.get('route_destination_name', 'the next stop')}.")
            life["visitor_memories"][traveler_id] = memories[-8:]
            connection_text = "route connection +2"
        if hasattr(self, "add_wilderness_region_vitality"):
            self.add_wilderness_region_vitality(
                int(self.state.wilderness_chunk_x), int(self.state.wilderness_chunk_y), vitality_gain,
                f"escorted {traveler.get('name', 'a regional traveler')}",
            )
        self.state.money += reward
        action = "Walked the local route with" if local_commute else "Escorted"
        self.autosave_with_message(
            f"{action} {traveler.get('name', 'the traveler')}: "
            f"+{reward}g, +{vitality_gain} vitality, {connection_text}."
        )
        return True

    def inn_guest_register_lines(self) -> List[str]:
        visitors = self.regional_town_visitors()
        lines = ["INN GUEST REGISTER", "", f"Date: {self.state.date_label}"]
        if visitors:
            for index, visitor in enumerate(visitors, 1):
                lines.extend([
                    "",
                    f"Room {index}: {visitor.get('name', 'Traveler')} - {visitor.get('role', 'Traveler')}",
                    f"Origin: {visitor.get('origin', 'Regional roads')} at chunk ({visitor.get('origin_chunk_x', 0)},{visitor.get('origin_chunk_y', 0)})",
                    f"Route: {visitor.get('distance_chunks', 0)} chunks; {visitor.get('route_condition', 'Open')}",
                    f"Arrival: {int(visitor.get('arrival_hour', 8)):02d}:00 | Status: {visitor.get('runtime_location', 'Traveling')}",
                ])
        else:
            lines.extend(["", "No regional guests are registered today."])
        returning = [
            journey for journey in self.regional_town_life_state().get("journeys", {}).values()
            if isinstance(journey, dict) and str(journey.get("status", "")) == "returning"
        ]
        if returning:
            lines.extend(["", "Recently departed:"])
            lines.extend(f"- {row.get('name', 'Traveler')} returning to {row.get('origin_name', 'their home route')}" for row in returning[:6])
        return lines

    def regional_visitor_conversation_lines(
        self,
        visitor: Dict[str, object],
        topic: str,
        bond: int,
    ) -> List[str]:
        role = str(visitor.get("role", "Traveler"))
        origin = str(visitor.get("origin", "the regional roads"))
        purpose = str(visitor.get("purpose", "visiting town"))
        activity = str(visitor.get("activity", "visiting town"))
        if topic == "origin":
            text = (
                f"I came from {origin}. The journey is {visitor.get('distance_chunks', 0)} chunks by the route I used, "
                f"and it is currently {str(visitor.get('route_condition', 'open')).lower()}."
            )
        elif topic == "town":
            occasion = self.todays_town_public_occasion()
            text = (
                f"I notice {occasion.get('name', 'ordinary town life')} first because visitors follow movement before they learn names. "
                "A useful town makes its roads, services, and gathering places explain one another."
            )
        elif topic == "news":
            text = str(visitor.get(
                "regional_news",
                "The roads are carrying merchants, field workers, letters, and settlement news more reliably than they did last season.",
            ))
        elif topic == "personal":
            text = (
                f"You have remembered me across several visits, so I will answer plainly: being a {role.lower()} lets me belong to several places without pretending any one road is home."
                if bond >= 6
                else f"For now, know that I am {purpose}. Familiarity takes more than recognizing the same coat at the inn."
            )
        else:
            insight = self.town_npc_work_insight(visitor)
            text = f"I am {activity} because I am {purpose}. {insight}"
        return [
            f'"{text}"',
            "",
            f"Role: {role}",
            f"Origin: {origin}",
            f"Current activity: {activity}",
            f"Connection: {self.regional_visitor_bond_label(bond)} ({bond})",
        ]

    def regional_town_visitor_menu(self, visitor: Dict[str, object]):
        visitor_id = str(visitor.get("id", "regional_visitor"))
        while True:
            life = self.regional_town_life_state()
            bond = int(life.setdefault("visitor_bonds", {}).get(visitor_id, 0) or 0)
            items = [
                MenuItem(label="Talk", value="talk", enabled=True, hint=self.regional_visitor_bond_label(bond)),
                MenuItem(label="Ask About Their Journey", value="journey", enabled=True),
                MenuItem(label="Ask for Regional News", value="news", enabled=True),
            ]
            if self.regional_visitor_stock(visitor):
                items.append(MenuItem(label="Browse Origin Goods", value="goods", enabled=True, hint=str(visitor.get("origin", "Regional stock"))))
            if str(visitor.get("role", "")) == "Cartographer":
                unknown = self.regional_origin_chart_unknown_count(visitor)
                price = 160 + min(240, int(visitor.get("distance_chunks", 0)) * 5)
                items.append(MenuItem(label="Purchase Origin Chart", value="origin_chart", enabled=unknown > 0 and int(self.state.money) >= price, hint=f"{price}g; maps {unknown} unknown chunks" if unknown else "Region already known"))
            items.extend([
                MenuItem(label="Visitor Profile", value="profile", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(
                str(visitor.get("name", "Traveler")),
                items,
                LEFT_PANEL_WIDTH,
                LEFT_PANEL_HEIGHT,
                return_back=True,
            )
            if not choice or choice.value == MENU_BACK:
                return
            if choice.value == "talk":
                today = self.town_npc_day_key()
                last_talk = life.setdefault("visitor_last_talk_day", {}).get(visitor_id, "")
                gain = 0
                topic_items = [
                    MenuItem(label="Ask What They're Doing", value="work", enabled=True, hint=str(visitor.get("activity", "Visiting town"))),
                    MenuItem(label="Ask About Their Origin", value="origin", enabled=True, hint=str(visitor.get("origin", "Regional roads"))),
                    MenuItem(label="Ask What They Notice Here", value="town", enabled=True, hint="Elsewhere through a visitor's eyes"),
                    MenuItem(label="Ask for Regional News", value="news", enabled=True, hint=str(visitor.get("route_condition", "Open route"))),
                    MenuItem(label="Ask Something Personal", value="personal", enabled=bond >= 2, hint="Requires Recognized Visitor" if bond < 2 else self.regional_visitor_bond_label(bond)),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ]
                topic_choice = self.vertical_panel_select(
                    f"Talk with {visitor.get('name', 'Traveler')}",
                    topic_items,
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                    return_back=True,
                )
                if not topic_choice or topic_choice.value == MENU_BACK:
                    continue
                influence_available = last_talk != today
                if last_talk != today:
                    gain = 1
                    life["visitor_bonds"][visitor_id] = min(250, bond + gain)
                    life["visitor_last_talk_day"][visitor_id] = today
                    memory = f"{today}: Spoke during {self.todays_town_public_occasion().get('name', 'a town visit')}."
                    memories = life.setdefault("visitor_memories", {}).setdefault(visitor_id, [])
                    memories.append(memory)
                    life["visitor_memories"][visitor_id] = memories[-8:]
                current_bond = int(life["visitor_bonds"].get(visitor_id, bond + gain) or 0)
                self.vertical_panel_view(
                    str(visitor.get("name", "Traveler")),
                    self.regional_visitor_conversation_lines(visitor, str(topic_choice.value), current_bond),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                response = self.npc_dialogue_response_choice(
                    visitor,
                    influence_available=influence_available,
                    title=f"Respond to {visitor.get('name', 'Them')}",
                )
                response_effect = int(response.get("effect", 0) or 0) if influence_available else 0
                if response_effect:
                    life["visitor_bonds"][visitor_id] = max(
                        0,
                        min(250, int(life["visitor_bonds"].get(visitor_id, 0) or 0) + response_effect),
                    )
                self.vertical_panel_view(
                    str(visitor.get("name", "Traveler")),
                    [
                        str(response.get("reaction", "The visitor turns back toward town.")),
                        "",
                        f"Connection influence: {response_effect:+}"
                        if response_effect
                        else "No further connection influence today."
                        if not influence_available
                        else "No connection change.",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                self.autosave_with_message(
                    f"Talked with {visitor.get('name', 'a regional visitor')}."
                    + (f" Connection {gain + response_effect:+}." if influence_available else "")
                )
                continue
            if choice.value == "journey":
                self.vertical_panel_view(
                    f"{visitor.get('name', 'Traveler')}'s Journey",
                    [
                        f"Origin: {visitor.get('origin', 'the regional roads')}",
                        f"Origin coordinates: ({visitor.get('origin_chunk_x', 0)},{visitor.get('origin_chunk_y', 0)})",
                        f"Road distance: {visitor.get('distance_chunks', 0)} chunks",
                        f"Route condition: {visitor.get('route_condition', 'Open')}",
                        f"Purpose: {visitor.get('purpose', 'visiting town')}",
                        f"Current activity: {visitor.get('activity', 'visiting town')}",
                        "Tonight they will use an assigned private guest room rather than crowding another guest.",
                    ],
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "news":
                occasion = self.todays_town_public_occasion()
                news = [
                    f"Road report from {visitor.get('origin', 'the region')}:",
                    str(visitor.get("regional_news", "Purposeful roads are carrying merchants, field workers, mail, and settlement news.")),
                    f"The route is currently {str(visitor.get('route_condition', 'open')).lower()}.",
                    f"Town today: {occasion.get('name', 'ordinary road traffic')}",
                    "Repeated visits are remembered, so familiar travelers may recognize you later.",
                ]
                self.vertical_panel_view("Regional News", news, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "goods":
                self.regional_visitor_goods_menu(visitor)
                continue
            if choice.value == "origin_chart":
                self.purchase_regional_visitor_origin_chart(visitor)
                continue
            if choice.value == "profile":
                memories = life.setdefault("visitor_memories", {}).get(visitor_id, [])
                lines = [
                    f"Name: {visitor.get('name', 'Traveler')}",
                    f"Role: {visitor.get('role', 'Traveler')}",
                    f"Origin: {visitor.get('origin', 'Regional roads')}",
                    f"Origin coordinates: ({visitor.get('origin_chunk_x', 0)},{visitor.get('origin_chunk_y', 0)})",
                    f"Route: {visitor.get('distance_chunks', 0)} chunks - {visitor.get('route_condition', 'Open')}",
                    f"Connection: {self.regional_visitor_bond_label(bond)} ({bond})",
                    "", "Shared memories:",
                ]
                lines.extend(f"- {row}" for row in memories[-5:])
                if not memories:
                    lines.append("- None yet")
                self.vertical_panel_view("Visitor Profile", lines, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue

    def town_npc_menu(self, npc: Dict[str, object]):
        if npc.get("regional_visitor"):
            self.regional_town_visitor_menu(npc)
            return
        if self.is_household_child_npc(npc):
            self.household_child_menu(npc)
            return
        if (
            hasattr(self, "is_dynasty_elder_npc")
            and self.is_dynasty_elder_npc(npc)
        ):
            self.dynasty_elder_menu(npc)
            return
        if (
            hasattr(self, "is_dynasty_kin_npc")
            and self.is_dynasty_kin_npc(npc)
        ):
            self.dynasty_kin_menu(npc)
            return
        if (
            self.is_procedural_npc(npc)
            and str(npc.get("id", ""))
            == str(getattr(self.state, "spouse_npc_id", ""))
            and hasattr(self, "procedural_household_spouse_menu")
        ):
            self.procedural_household_spouse_menu(npc)
            return
        while True:
            npc_id = str(npc.get("id", npc.get("name", "npc")))
            today = self.town_npc_day_key()
            talked_today = self.state.town_npc_last_talk_day.get(npc_id) == today
            gifted_today = self.state.town_npc_last_gift_day.get(npc_id) == today
            errand = self.errand_for_npc(npc)
            errand_hint = "done" if errand.get("completed") else ("ready" if self.can_complete_errand(errand) else f"needs {errand.get('item')}")
            court_ok, _court_reason = self.can_court_town_npc(npc) if self.is_marriageable_npc(npc) else (False, "not romanceable")
            proposal_ok, proposal_reason = self.can_propose_to_town_npc(npc) if self.is_marriageable_npc(npc) else (False, "not romanceable")
            court_menu_hint = "Available" if court_ok else "Build friendship first"
            proposal_menu_hint = "Ready" if proposal_ok else proposal_reason
            items = [
                MenuItem(label="Talk", value="talk", enabled=True),
                MenuItem(label="Give Gift", value="gift", enabled=not gifted_today, hint="Choose a carried item" if not gifted_today else "Already gave a gift today"),
                MenuItem(label="Ask Rumor", value="rumor", enabled=True),
                MenuItem(label="Errand", value="errand", enabled=True, hint=errand_hint),
            ]
            service_spec = self.authored_town_service_spec(npc)
            if service_spec and self.town_npc_work_service_available(npc):
                items.append(
                    MenuItem(
                        label=str(service_spec[1]),
                        value="work_service",
                        enabled=True,
                        hint="on duty",
                    )
                )
            if npc.get("home_region_destination_worker"):
                local_work_ok, local_work_reason = self.home_region_local_work_status(npc)
                items.append(
                    MenuItem(
                        label="Help with local work",
                        value="local_work",
                        enabled=local_work_ok,
                        hint=local_work_reason,
                    )
                )
            if self.is_marriageable_npc(npc):
                items.append(
                    MenuItem(
                        label="Courtship",
                        value="courtship",
                        enabled=True,
                        hint=court_menu_hint,
                    )
                )
                if str(getattr(self.state, "engaged_npc_id", "")) == npc_id:
                    items.append(
                        MenuItem(
                            label="Wedding plans",
                            value="wedding_plans",
                            enabled=True,
                            hint=self.wedding_date_label(),
                        )
                    )
                else:
                    items.append(
                        MenuItem(
                            label="Propose",
                            value="proposal",
                            enabled=True,
                            hint=proposal_menu_hint,
                        )
                    )
            if self.state.spouse_npc_id == npc_id:
                move_ok, move_reason = self.can_invite_spouse_to_farm(npc)
                family_ok, family_reason = self.can_start_pregnancy_with_spouse(npc)
                scene_key, scene_title = self.available_marriage_scene(npc)
                items.append(MenuItem(
                    label="Move to farm",
                    value="move_spouse",
                    enabled=move_ok,
                    hint=move_reason,
                ))
                items.append(MenuItem(
                    label="Marriage event",
                    value="marriage_scene",
                    enabled=bool(scene_key),
                    hint=scene_title if scene_title else "none ready",
                ))
                items.append(MenuItem(label="Family memories", value="family_memories", enabled=True, hint=f"{len(self.state.family_event_log or [])} logged"))
                items.append(MenuItem(
                    label="Plan family",
                    value="plan_family",
                    enabled=True,
                    hint=family_reason,
                ))
                if self.state.pregnancy_active:
                    items.append(MenuItem(
                        label="Pregnancy check-in",
                        value="pregnancy_checkup",
                        enabled=True,
                        hint="ready" if self.pregnancy_checkup_available() else "view",
                    ))
                family_hint = "pregnancy active" if self.state.pregnancy_active else f"{len(self.state.children)} child(ren)"
                items.append(MenuItem(label="Family status", value="family_status", enabled=True, hint=family_hint))
                meal_ok, meal_reason = self.family_meal_available()
                items.append(MenuItem(
                    label="Family meal",
                    value="family_meal",
                    enabled=True,
                    hint="ready" if meal_ok else meal_reason,
                ))
                items.append(MenuItem(
                    label="Spouse support",
                    value="spouse_support",
                    enabled=self.state.spouse_moved_to_farm,
                    hint=self.spouse_support_mode(),
                ))
                items.append(MenuItem(
                    label="Household help",
                    value="household_help",
                    enabled=True,
                    hint="enabled" if self.state.family_help_enabled else "disabled",
                ))
            items.extend([
                MenuItem(label="Profile", value="profile", enabled=True),
                MenuItem(label="Status", value="status", enabled=True),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ])
            choice = self.vertical_panel_select(str(npc.get("name", "Villager")), items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
            if choice is None or choice.value == MENU_BACK:
                self.set_message(f"Stopped talking to {npc.get('name', 'the villager')}.")
                return
            if choice.value == "talk":
                self.talk_to_town_npc(npc)
                return
            if choice.value == "gift":
                self.give_gift_to_town_npc(npc)
                return
            if choice.value == "rumor":
                self.vertical_panel_view(f"{npc.get('name')} Rumor", self.town_npc_rumor_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                self.set_message(f"Asked {npc.get('name')} about rumors.")
                continue
            if choice.value == "errand":
                errand = self.errand_for_npc(npc)
                if self.can_complete_errand(errand):
                    self.complete_errand(errand)
                    return
                self.vertical_panel_view(f"{npc.get('name')} Errand", self.errand_lines(errand), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                self.set_message(f"{npc.get('name')} needs {errand.get('qty')} {errand.get('item')}.")
                continue
            if choice.value == "work_service":
                self.open_town_npc_work_service(npc)
                return
            if choice.value == "local_work":
                self.vertical_panel_view(
                    "Local Work",
                    self.home_region_local_work_lines(npc),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                if self.complete_home_region_local_work(npc):
                    return
                continue
            if choice.value == "courtship":
                if self.court_town_npc(npc):
                    return
                continue
            if choice.value == "proposal":
                if self.propose_to_town_npc(npc):
                    return
                continue
            if choice.value == "wedding_plans":
                self.vertical_panel_view(
                    "Wedding Plans",
                    self.marriage_status_lines(),
                    LEFT_PANEL_WIDTH,
                    LEFT_PANEL_HEIGHT,
                )
                continue
            if choice.value == "move_spouse":
                if self.invite_spouse_to_farm(npc):
                    return
                continue
            if choice.value == "marriage_scene":
                if self.play_marriage_scene(npc):
                    return
                continue
            if choice.value == "family_memories":
                self.vertical_panel_view("Family Memories", self.family_event_log_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "plan_family":
                if self.family_planning_menu(npc) == "changed":
                    return
                continue
            if choice.value == "pregnancy_checkup":
                if self.complete_pregnancy_checkup(npc):
                    return
                continue
            if choice.value == "family_status":
                self.vertical_panel_view("Family", self.family_status_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                self.set_message("Reviewed family status.")
                continue
            if choice.value == "family_meal":
                if self.family_meal_menu() == "changed":
                    return
                continue
            if choice.value == "spouse_support":
                if self.spouse_support_menu() == "changed":
                    return
                continue
            if choice.value == "household_help":
                self.vertical_panel_view("Household Help", self.family_help_lines(), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                toggle_items = [
                    MenuItem(label="Toggle household help", value="toggle", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ]
                toggle_choice = self.vertical_panel_select("Household Help", toggle_items, LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT, return_back=True)
                if toggle_choice and toggle_choice.value == "toggle":
                    self.toggle_family_help()
                    return
                continue
            if choice.value == "profile":
                self.vertical_panel_view(f"{npc.get('name')} Profile", self.town_npc_profile_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue
            if choice.value == "status":
                self.vertical_panel_view(str(npc.get("name", "Villager")), self.town_npc_status_lines(npc), LEFT_PANEL_WIDTH, LEFT_PANEL_HEIGHT)
                continue

    def talk_to_town_npc(self, npc: Dict[str, object]):
        npc_id = str(npc.get("id", npc.get("name", "npc")))
        today = self.town_npc_day_key()
        first_talk_today = self.state.town_npc_last_talk_day.get(npc_id) != today
        self.state.town_npc_dialogue_counts[npc_id] = int(self.state.town_npc_dialogue_counts.get(npc_id, 0)) + 1
        actual_gain = 0
        if first_talk_today:
            actual_gain = self.adjust_town_npc_relationship(npc_id, RELATIONSHIP_TALK_GAIN)
            self.state.town_npc_last_talk_day[npc_id] = today
            if self.maybe_play_scene_for_context({"type": "npc_talk", "npc": npc, "npc_id": npc_id}):
                message = self.state.message or f"Shared a moment with {npc.get('name', 'the villager')}."
                self.autosave_with_message(message)
                return
        response = self.town_npc_conversation_menu(
            npc,
            influence_available=first_talk_today,
        )
        if not response.get("topic"):
            if first_talk_today:
                if actual_gain:
                    self.adjust_town_npc_relationship(npc_id, -actual_gain)
                if self.state.town_npc_last_talk_day.get(npc_id) == today:
                    self.state.town_npc_last_talk_day.pop(npc_id, None)
            self.state.town_npc_dialogue_counts[npc_id] = max(
                0,
                int(self.state.town_npc_dialogue_counts.get(npc_id, 1)) - 1,
            )
            self.set_message(f"Stopped talking to {npc.get('name', 'the villager')}.")
            return
        if first_talk_today:
            actual_gain += self.adjust_town_npc_relationship(
                npc_id,
                int(response.get("effect", 0) or 0),
            )
        bonus = f" Relationship +{actual_gain}." if actual_gain > 0 else ""
        if actual_gain < 0:
            bonus = f" Relationship {actual_gain}."
        self.autosave_with_message(f"Talked to {npc.get('name', 'the villager')}.{bonus}")



__all__ = ["NpcMixin"]
