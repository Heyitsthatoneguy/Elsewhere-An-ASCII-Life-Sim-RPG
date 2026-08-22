import json
import math
import os
import random
import shutil
import sys
import time
import textwrap
from pathlib import Path

# ============================================================
# ASCII FISHTANK v1.5
# --------------------------------------------------
# A cozy terminal aquarium with:
#   - persistent fish, personalities, age, mood, hunger
#   - save/load
#   - optional ANSI color
#   - screensaver mode
#   - shop-style buying keys
#   - rare events and visitors
#   - plants, rocks, decorations, bubbles, snails, food
#   - fish grow from egg to fry to adult, become elders, and may pass from old age
#   - manual fish naming with N
#   - smoother in-place rendering on ANSI-capable terminals
#   - GBC-style aquarium album, rarity eggs, comfort rating, and attractor decorations
#
# Controls:
#   Q = quit
#   F = feed fish
#   A = add a mystery egg
#   N = name/rename a fish
#   R = reset to a new one-egg tank
#   B = add bubbles
#   P = pause/unpause
#   S = save tank
#   L = load tank
#   V = screensaver mode on/off
#   C = color on/off
#   H = help/shop overlay on/off
#   J = species journal/album on/off
#   M = toggle old-age mortality on/off
#   1 = buy mystery egg costs $12
#   2 = buy plant      costs $8
#   3 = buy decoration costs $15
#   4 = buy snail      costs $10
#   5 = buy rare egg   costs $30
#   6 = upgrade roomy tank
#   7 = upgrade better filter
#   8 = upgrade bubble stone
#   9 = upgrade nursery moss
#   0 = upgrade auto-feeder
#   X = sell fish
#   D = remove decoration
#
# Menu controls:
#   Arrow Up/Down = move cursor
#   Enter/Space/Right = select
#   Esc/Q/Left = back
#
# Run:
#   python fishtank_v15.py
#   py -3.11 fishtank_v15.py
# ============================================================

FPS_DELAY = 0.085
DEFAULT_WIDTH = 84
DEFAULT_HEIGHT = 26
APP_NAME = "AsciiFishtank"
SAVE_FILENAME = "fishtank_save.json"


def get_save_dir():
    """Return a user-writable save directory.

    On Windows this uses %APPDATA%\\AsciiFishtank, which avoids permission
    errors when the script is launched from Program Files, C:\\, downloads with
    restricted permissions, or an IDE working directory. On other systems it
    uses ~/.ascii_fishtank.
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_NAME
    return Path.home() / ".ascii_fishtank"


SAVE_DIR = get_save_dir()
SAVE_FILE = SAVE_DIR / SAVE_FILENAME
LEGACY_SAVE_FILE = Path(SAVE_FILENAME)
TERMINAL_OLD_SETTINGS = None

MAX_FISH = 28
MAX_BUBBLES = 110
MAX_FOOD = 60
MAX_EVENTS = 6
RARITY_ORDER = ["common", "uncommon", "rare", "legendary"]
RARITY_LABELS = {"common": "Common", "uncommon": "Uncommon", "rare": "Rare", "legendary": "Legendary"}
RARITY_WEIGHTS = {"common": 70, "uncommon": 22, "rare": 7, "legendary": 1}
RARE_EGG_WEIGHTS = {"common": 18, "uncommon": 42, "rare": 30, "legendary": 10}

# Age tuning is measured in simulation ticks. One tank day is currently 600 ticks.
# Fish visibly grow fast enough to notice, then live for many tank-days before old age matters.
EGG_HATCH_MIN = 430
EGG_HATCH_MAX = 760
FRY_AGE = 700
ADULT_AGE = 1400
ELDER_AGE_RATIO = 0.72
MIN_LIFESPAN = 15000
MAX_LIFESPAN = 31000
OLD_AGE_DEATH_CHANCE = 0.00075

# ANSI colors. Toggle with C. Works in most modern terminals, including many Windows terminals.
COLOR = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "water": "\033[36m",
    "fish": "\033[93m",
    "fish2": "\033[95m",
    "plant": "\033[92m",
    "rock": "\033[90m",
    "food": "\033[33m",
    "bubble": "\033[96m",
    "snail": "\033[97m",
    "decor": "\033[91m",
    "rare": "\033[94m",
    "orange": "\033[38;5;208m",
    "gold": "\033[38;5;220m",
    "pink": "\033[38;5;213m",
    "violet": "\033[38;5;141m",
    "teal": "\033[38;5;44m",
    "lime": "\033[38;5;118m",
    "silver": "\033[38;5;250m",
    "red": "\033[91m",
    "blue": "\033[94m",
    "text": "\033[97m",
    "border": "\033[37m",
}

FISH_SPECIES = [
    {
        "name": "guppy",
        "right": "><>",
        "left": "<><",
        "speed_chance": 0.72,
        "vertical_chance": 0.12,
        "color": "fish",
    },
    {
        "name": "goldfish",
        "right": "><(((°>",
        "left": "<°)))><",
        "speed_chance": 0.52,
        "vertical_chance": 0.08,
        "color": "fish",
    },
    {
        "name": "tiny tetra",
        "right": ">°>",
        "left": "<°<",
        "speed_chance": 0.86,
        "vertical_chance": 0.18,
        "color": "fish2",
    },
    {
        "name": "lazy molly",
        "right": "><))'>",
        "left": "<'((><",
        "speed_chance": 0.34,
        "vertical_chance": 0.055,
        "color": "fish2",
    },
    {
        "name": "needlefish",
        "right": "--<(((>",
        "left": "<)))>--",
        "speed_chance": 0.90,
        "vertical_chance": 0.04,
        "color": "fish",
    },
    {
        "name": "moon angel",
        "right": "><(({*>",
        "left": "<*})))><",
        "speed_chance": 0.46,
        "vertical_chance": 0.13,
        "color": "fish2",
    },
    {
        "name": "betta",
        "right": "><{~~°>",
        "left": "<°~~}>",
        "speed_chance": 0.44,
        "vertical_chance": 0.16,
        "color": "fish2",
    },
    {
        "name": "cory cat",
        "right": "><_°>",
        "left": "<°_><",
        "speed_chance": 0.58,
        "vertical_chance": 0.06,
        "color": "fish",
    },
    {
        "name": "zebra danio",
        "right": ">=//=°>",
        "left": "<°=\\=<",
        "speed_chance": 0.93,
        "vertical_chance": 0.20,
        "color": "fish",
    },
    {
        "name": "clownfish",
        "right": "><{o°>",
        "left": "<°o}><",
        "speed_chance": 0.64,
        "vertical_chance": 0.12,
        "color": "fish",
    },
    {
        "name": "glass catfish",
        "right": "--°>",
        "left": "<°--",
        "speed_chance": 0.76,
        "vertical_chance": 0.09,
        "color": "bubble",
    },
    {
        "name": "pea puffer",
        "right": "(°)> ",
        "left": " <(°)",
        "speed_chance": 0.40,
        "vertical_chance": 0.18,
        "color": "fish2",
    },
    {
        "name": "kuhli loach",
        "right": "~==°>",
        "left": "<°==~",
        "speed_chance": 0.70,
        "vertical_chance": 0.05,
        "color": "fish",
        "rarity": "uncommon",
        "likes": ["sunken cup"],
    },
    {
        "name": "ribbon eel",
        "right": "~~<°>>>>",
        "left": "<<<<°>~~",
        "speed_chance": 0.68,
        "vertical_chance": 0.14,
        "color": "rare",
        "rarity": "uncommon",
        "likes": ["castle", "sunken cup"],
    },
    {
        "name": "crystal koi",
        "right": "><{{◇°>",
        "left": "<°◇}}><",
        "speed_chance": 0.42,
        "vertical_chance": 0.10,
        "color": "bubble",
        "rarity": "rare",
        "likes": ["treasure chest", "castle"],
    },
    {
        "name": "star guppy",
        "right": "><*°>",
        "left": "<°*><",
        "speed_chance": 0.78,
        "vertical_chance": 0.20,
        "color": "fish2",
        "rarity": "rare",
        "likes": ["tiny skull", "treasure chest"],
    },
    {
        "name": "phantom tetra",
        "right": "><~°>",
        "left": "<°~><",
        "speed_chance": 0.82,
        "vertical_chance": 0.12,
        "color": "rare",
        "rarity": "uncommon",
        "likes": ["tiny skull"],
    },
    {
        "name": "royal arowana",
        "right": "--<{{{★°>",
        "left": "<°★}}}>--",
        "speed_chance": 0.36,
        "vertical_chance": 0.05,
        "color": "fish",
        "rarity": "legendary",
        "likes": ["castle", "treasure chest"],
    },
]

FISH_NAMES = [
    "Bloop", "Miso", "Pebble", "Finnegan", "Sushi", "Glimmer", "Noodle",
    "Captain Fin", "Pip", "Mochi", "Wiggles", "Bubblegum", "Tango", "Pickle",
    "Marbles", "Kelpie", "Guppington", "Professor Gill", "Beans", "Fig",
    "Dr. Bubbles", "Nimbus", "Waffles", "Juniper", "Sir Splash", "Zigzag",
]

PERSONALITIES = [
    "calm",       # steady wanderer
    "curious",    # inspects objects and follows food sooner
    "sleepy",     # pauses often
    "bold",       # patrols more aggressively
    "shy",        # likes plants
    "social",     # drifts toward other fish
    "bubble-obsessed", # follows bubbles
    "nocturnal",  # livelier at night
    "greedy",     # rushes food earlier
]

DECOR_TYPES = [
    {"name": "castle", "glyphs": ["/\\", "||", "##"], "cost": 15},
    {"name": "treasure chest", "glyphs": ["[$]", "###"], "cost": 15},
    {"name": "tiny skull", "glyphs": ["o_o", "/|\\"], "cost": 15},
    {"name": "sunken cup", "glyphs": ["_U_", "###"], "cost": 15},
]

FOOD_TYPES = [
    {"key": "flakes", "name": "Basic Flakes", "glyph": ".", "color": "food", "hunger": (24, 46), "mood": ["content", "pleased", "zippy"], "water_penalty": 1},
    {"key": "brine", "name": "Brine Shrimp", "glyph": "'", "color": "pink", "hunger": (30, 52), "mood": ["delighted", "zippy", "playful"], "water_penalty": 1},
    {"key": "algae", "name": "Algae Wafer", "glyph": "=", "color": "plant", "hunger": (18, 36), "mood": ["content", "calm"], "water_penalty": 0},
    {"key": "golden", "name": "Golden Pellet", "glyph": "*", "color": "gold", "hunger": (28, 48), "mood": ["sparkly", "pleased", "bold"], "water_penalty": 1},
    {"key": "night", "name": "Night Bites", "glyph": "+", "color": "violet", "hunger": (24, 44), "mood": ["moonlit", "content"], "water_penalty": 1},
]

UPGRADE_CATALOG = {
    "tank": {
        "name": "Roomy Tank",
        "key": "6",
        "costs": [45, 85, 140],
        "desc": "+6 safe fish/egg capacity per level and less crowding.",
    },
    "filter": {
        "name": "Better Filter",
        "key": "7",
        "costs": [35, 70, 120],
        "desc": "Improves water quality drift and makes cleaning stronger.",
    },
    "bubbler": {
        "name": "Bubble Stone",
        "key": "8",
        "costs": [30, 60, 105],
        "desc": "Adds more bubbles and comfort; bubble-loving fish approve.",
    },
    "nursery": {
        "name": "Nursery Moss",
        "key": "9",
        "costs": [40, 75, 130],
        "desc": "Eggs hatch faster and breeding eggs are a little more likely.",
    },
    "feeder": {
        "name": "Auto-Feeder",
        "key": "0",
        "costs": [50, 95, 160],
        "desc": "Occasionally drops a tiny amount of selected food.",
    },
}


def upgrade_level(tank, name):
    upgrades = getattr(tank, "upgrades", {}) or {}
    try:
        return int(upgrades.get(name, 0))
    except Exception:
        return 0


def next_upgrade_cost(tank, name):
    data = UPGRADE_CATALOG[name]
    level = upgrade_level(tank, name)
    if level >= len(data["costs"]):
        return None
    return data["costs"][level]


def upgrade_summary(tank):
    parts = []
    for key in ["tank", "filter", "bubbler", "nursery", "feeder"]:
        level = upgrade_level(tank, key)
        if level:
            parts.append(f"{UPGRADE_CATALOG[key]['name']} Lv{level}")
    return ", ".join(parts) if parts else "none yet"

SPECIES_COLOR_CYCLE = ["orange", "gold", "teal", "violet", "pink", "lime", "silver", "red", "blue", "fish", "fish2", "bubble", "rare"]
for _idx, _species in enumerate(FISH_SPECIES):
    _species["color"] = SPECIES_COLOR_CYCLE[_idx % len(SPECIES_COLOR_CYCLE)]


def food_type_by_key(key):
    for item in FOOD_TYPES:
        if item["key"] == key:
            return item
    return FOOD_TYPES[0]


def water_quality_label(score):
    if score >= 88:
        return "Sparkling"
    if score >= 68:
        return "Clear"
    if score >= 42:
        return "Cloudy"
    return "Murky"


def water_quality_grade(score):
    if score >= 88:
        return "S"
    if score >= 68:
        return "A"
    if score >= 42:
        return "C"
    return "D"


RARE_VISITORS = [
    {"name": "seahorse", "right": "§>", "left": "<§", "life": 320},
    {"name": "jellyfish", "right": "{*}", "left": "{*}", "life": 260},
    {"name": "ghost fish", "right": "><ghost>", "left": "<ghost><", "life": 220},
]


# ----------------------------
# Terminal helpers
# ----------------------------

def terminal_supports_ansi():
    """Best-effort ANSI detection. Keeps old Windows consoles and IDE panes safe."""
    if os.name != "nt":
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    env = os.environ
    return bool(
        env.get("WT_SESSION")
        or env.get("ANSICON")
        or env.get("ConEmuANSI") == "ON"
        or env.get("TERM_PROGRAM")
    )


def clear_screen():
    """Clear the visible console. Used for prompts, startup, and shutdown."""
    if terminal_supports_ansi():
        print("\033[2J\033[H", end="", flush=True)
    else:
        os.system("cls" if os.name == "nt" else "clear")


def begin_frame(use_ansi):
    """Start a new animation frame.

    The old renderer cleared the whole screen every frame, which caused visible
    flicker. ANSI-capable terminals can instead jump the cursor back to the
    top-left and overwrite the previous frame in place. Non-ANSI consoles keep
    the old safe clear behavior.
    """
    if use_ansi and terminal_supports_ansi():
        print("\033[H", end="")
    else:
        clear_screen()


def end_frame(use_ansi):
    """Erase any leftover lines from a previous, taller frame and flush output."""
    if use_ansi and terminal_supports_ansi():
        print("\033[J", end="", flush=True)
    else:
        sys.stdout.flush()


def hide_cursor_if_possible(use_ansi):
    if use_ansi and terminal_supports_ansi():
        print("\033[?25l", end="", flush=True)


def show_cursor_if_possible(use_ansi=True):
    if use_ansi and terminal_supports_ansi():
        print("\033[?25h", end="", flush=True)


def get_terminal_size():
    """Return a tank size that fits the current terminal without wrapping."""
    size = shutil.get_terminal_size((DEFAULT_WIDTH, DEFAULT_HEIGHT))

    # Keep one column and several rows free for prompts/log text. Never force
    # the tank wider than the terminal says it is.
    usable_columns = max(24, size.columns - 2)
    usable_lines = max(14, size.lines - 7)

    width = min(DEFAULT_WIDTH, usable_columns)
    height = min(DEFAULT_HEIGHT, usable_lines)

    width = max(24, width)
    height = max(14, height)
    return width, height


if os.name == "nt":
    import msvcrt

    def get_key():
        """Return a normalized key name.

        Normal character keys return lowercase letters/numbers. Arrow keys return
        "up", "down", "left", or "right". This keeps menu navigation
        separate from tank hotkeys like F=feed and W=clean.
        """
        if not msvcrt.kbhit():
            return None
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            code = msvcrt.getch()
            return {b"H": "up", b"P": "down", b"K": "left", b"M": "right"}.get(code)
        if ch == b"\r":
            return "\r"
        if ch == b"\x1b":
            return "\x1b"
        return ch.decode(errors="ignore").lower()
else:
    import select
    import termios
    import tty

    def get_key():
        """Return a normalized key name.

        Normal character keys return lowercase letters/numbers. ANSI arrow
        sequences return "up", "down", "left", or "right".
        """
        if not getattr(sys.stdin, "isatty", lambda: False)():
            return None
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if not dr:
            return None
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # ANSI arrow keys usually arrive as ESC [ A/B/C/D. Read the rest
            # only if it is already available, so a plain Esc still works.
            dr, _, _ = select.select([sys.stdin], [], [], 0.02)
            if dr:
                nxt = sys.stdin.read(1)
                if nxt == "[":
                    dr, _, _ = select.select([sys.stdin], [], [], 0.02)
                    if dr:
                        code = sys.stdin.read(1)
                        return {"A": "up", "B": "down", "C": "right", "D": "left"}.get(code, "\x1b")
            return "\x1b"
        return ch.lower()


# ----------------------------
# Factories
# ----------------------------

def rand_id(prefix):
    return f"{prefix}-{random.randint(100000, 999999)}"


def make_fish(width, height, baby=False):
    species = random.choice(FISH_SPECIES)
    direction = random.choice([-1, 1])
    age = 0 if baby else random.randint(50, 5000)
    name = random.choice(FISH_NAMES)
    if baby:
        name = random.choice(["Tiny", "Bean", "Fry", "Little Fin", "Dot"])

    return {
        "id": rand_id("fish"),
        "name": name,
        "species": species["name"],
        "x": random.randint(3, max(4, width - 14)),
        "y": random.randint(3, max(4, height - 5)),
        "dir": direction,
        "hunger": random.randint(0, 45),
        "mood": random.choice(["calm", "curious", "content", "sleepy"]),
        "personality": random.choice(PERSONALITIES),
        "age": age,
        "lifespan": random.randint(MIN_LIFESPAN, MAX_LIFESPAN),
        "elder_announced": False,
        "pause": random.randint(0, 12),
        "wiggle": random.randint(0, 1000),
        "favorite_depth": random.randint(3, max(4, height - 5)),
        "birthday_tick": 0,
        "hatched_day": 1,
        "parents": [],
        "parent_names": [],
        "children": [],
        "generation": 1,
        "last_stage": "fry" if baby else "adult",
        "favorite_food": random.choice([food["key"] for food in FOOD_TYPES]),
        "favorite_decor": random.choice([decor["name"] for decor in DECOR_TYPES]),
        "favorite_time": random.choice(["Morning", "Day", "Evening", "Night"]),
        "best_friend": None,
    }


def make_egg(width, height, species_name=None, rare_egg=False, tank=None):
    species_name = species_name or choose_species_for_egg(tank, rare_egg=rare_egg)
    comfort = tank.comfort_score() if tank is not None and hasattr(tank, "comfort_score") else 50
    hatch_bonus = int(max(0, comfort - 50) * 2.0)
    hatch_time = random.randint(EGG_HATCH_MIN, EGG_HATCH_MAX) - hatch_bonus
    nursery = upgrade_level(tank, "nursery") if tank is not None else 0
    if nursery:
        hatch_time = int(hatch_time * max(0.68, 1.0 - nursery * 0.09))
    hatch_time = max(180, hatch_time)
    return {
        "id": rand_id("egg"),
        "species": species_name,
        "rarity": species_rarity(species_name),
        "x": random.randint(4, max(4, width - 6)),
        "y": height - 3,
        "age": 0,
        "hatch_time": hatch_time,
        "wiggle": random.randint(0, 1000),
        "rare_egg": bool(rare_egg),
        "parents": [],
        "parent_names": [],
        "generation": 1,
    }


def make_bubble(width, height, source_x=None):
    return {
        "x": source_x if source_x is not None else random.randint(2, max(2, width - 3)),
        "y": height - 3,
        "drift": random.choice([-1, 0, 0, 0, 1]),
        "age": 0,
    }


def make_food(width, food_key="flakes"):
    food_type = food_type_by_key(food_key)
    return {
        "x": random.randint(3, max(3, width - 4)),
        "y": 2,
        "fall_speed": random.choice([0.25, 0.33, 0.5]),
        "fall_progress": 0.0,
        "kind": food_type["key"],
        "glyph": food_type["glyph"],
        "color": food_type["color"],
        "age": 0,
    }


def make_plant(width, height):
    return {
        "id": rand_id("plant"),
        "x": random.randint(4, max(4, width - 5)),
        "height": random.randint(3, 7),
        "phase": random.randint(0, 1000),
        "growth": random.randint(0, 40),
    }


def make_rock(width):
    return {
        "x": random.randint(3, max(3, width - 8)),
        "width": random.randint(2, 5),
    }


def make_snail(width, height):
    return {
        "id": rand_id("snail"),
        "name": random.choice(["The Snailer", "Moss", "Scoot", "Barnaby", "Gluebert"]),
        "x": random.randint(3, max(3, width - 5)),
        "y": height - 3,
        "dir": random.choice([-1, 1]),
        "move_timer": random.randint(5, 25),
        "age": random.randint(0, 2000),
    }


def make_decoration(width, height, decor_type=None):
    decor = decor_type or random.choice(DECOR_TYPES)
    return {
        "id": rand_id("decor"),
        "name": decor["name"],
        "x": random.randint(4, max(4, width - 10)),
        "y": height - 4,
        "kind": decor["name"],
    }


def make_visitor(width, height):
    visitor = random.choice(RARE_VISITORS)
    direction = random.choice([-1, 1])
    return {
        "id": rand_id("visitor"),
        "name": visitor["name"],
        "x": 2 if direction == 1 else width - 12,
        "y": random.randint(3, height - 6),
        "dir": direction,
        "life": visitor["life"],
        "right": visitor["right"],
        "left": visitor["left"],
    }


def species_by_name(name):
    for species in FISH_SPECIES:
        if species["name"] == name:
            return species
    return FISH_SPECIES[0]


def species_rarity(name):
    return species_by_name(name).get("rarity", "common")


def all_species_names():
    return [species["name"] for species in FISH_SPECIES]


def choose_species_for_egg(tank=None, rare_egg=False):
    """Pick a species with rarity, comfort, and decoration attraction in mind."""
    weights = RARE_EGG_WEIGHTS if rare_egg else RARITY_WEIGHTS
    comfort = tank.comfort_score() if tank is not None and hasattr(tank, "comfort_score") else 50
    decorations = {d.get("kind", d.get("name", "")) for d in getattr(tank, "decorations", [])} if tank is not None else set()

    choices = []
    for species in FISH_SPECIES:
        rarity = species.get("rarity", "common")
        weight = weights.get(rarity, 1)
        # A comfortable tank slightly improves rare/legendary odds.
        if rarity == "rare":
            weight *= 1 + max(0, comfort - 50) / 90
        elif rarity == "legendary":
            weight *= 1 + max(0, comfort - 65) / 55
        # Decorations that a species likes act like tiny lures.
        if decorations.intersection(set(species.get("likes", []))):
            weight *= 2.2 if rarity in ("rare", "legendary") else 1.45
        choices.append((species["name"], max(0.1, weight)))

    total = sum(weight for _, weight in choices)
    roll = random.random() * total
    upto = 0
    for name, weight in choices:
        upto += weight
        if roll <= upto:
            return name
    return choices[-1][0]


def decor_by_name(name):
    for decor in DECOR_TYPES:
        if decor["name"] == name:
            return decor
    return DECOR_TYPES[0]


# ----------------------------
# Simulation
# ----------------------------

class Fishtank:
    def __init__(self):
        self.width, self.height = get_terminal_size()
        self.fish = []
        self.eggs = [make_egg(self.width, self.height)]
        self.bubbles = [make_bubble(self.width, self.height) for _ in range(16)]
        self.food = []
        self.plants = [make_plant(self.width, self.height) for _ in range(max(4, self.width // 18))]
        self.rocks = [make_rock(self.width) for _ in range(max(4, self.width // 16))]
        self.snails = [make_snail(self.width, self.height) for _ in range(2)]
        self.decorations = [make_decoration(self.width, self.height)]
        self.visitors = []

        self.tick = 0
        self.day = 1
        self.paused = False
        self.running = True
        self.screensaver = False
        self.use_color = terminal_supports_ansi()
        self.show_help = False
        self.show_journal = False
        self.show_profile = False
        self.selected_fish_index = 0
        self.autosave = True
        self.old_age_mortality = True
        self.shells = 25
        self.saved_notice = 0
        self.discovered_species = []
        self.hatch_count = 0
        self.rare_egg_stock = 0
        self.water_quality = 82
        self.selected_food_index = 0
        self.aquarium_journal = []
        self.show_tank_journal = False
        self.upgrades = {"tank": 0, "filter": 0, "bubbler": 0, "nursery": 0, "feeder": 0}

        self.event_log = [
            "The tank hums softly.",
            "Tiny bubbles begin to rise.",
            "A single mystery egg rests in the gravel.",
        ]

    def log(self, message):
        self.event_log.append(message)
        self.event_log = self.event_log[-MAX_EVENTS:]
        if not hasattr(self, "aquarium_journal"):
            self.aquarium_journal = []
        stamped = f"Day {getattr(self, 'day', 1)}: {message}"
        if not self.aquarium_journal or self.aquarium_journal[-1] != stamped:
            self.aquarium_journal.append(stamped)
            self.aquarium_journal = self.aquarium_journal[-120:]

    def discover_species(self, species_name, silent=False):
        if not hasattr(self, "discovered_species"):
            self.discovered_species = []
        if species_name not in self.discovered_species:
            self.discovered_species.append(species_name)
            self.discovered_species.sort(key=lambda n: (RARITY_ORDER.index(species_rarity(n)) if species_rarity(n) in RARITY_ORDER else 0, n))
            if not silent:
                rarity = RARITY_LABELS.get(species_rarity(species_name), species_rarity(species_name))
                self.log(f"Album updated: {species_name} discovered! ({rarity})")

    def comfort_score(self):
        fish_count = len(getattr(self, "fish", [])) + len(getattr(self, "eggs", []))
        plant_score = min(24, len(getattr(self, "plants", [])) * 4)
        decor_score = min(22, len(getattr(self, "decorations", [])) * 5)
        snail_score = min(10, len(getattr(self, "snails", [])) * 3)
        bubble_score = min(8 + upgrade_level(self, "bubbler") * 3, len(getattr(self, "bubbles", [])) // max(6, 14 - upgrade_level(self, "bubbler") * 2))
        comfortable_capacity = 12 + upgrade_level(self, "tank") * 5
        crowd_penalty = max(0, fish_count - comfortable_capacity) * 4
        old_food_penalty = max(0, len(getattr(self, "food", [])) - 30) // 2
        water_bonus = int((getattr(self, "water_quality", 70) - 60) / 5)
        score = 38 + plant_score + decor_score + snail_score + bubble_score + water_bonus - crowd_penalty - old_food_penalty
        return max(0, min(100, int(score)))

    def comfort_grade(self):
        score = self.comfort_score()
        if score >= 85:
            return "S"
        if score >= 72:
            return "A"
        if score >= 58:
            return "B"
        if score >= 42:
            return "C"
        return "D"

    def save(self):
        data = {
            "version": 14,
            "fish": self.fish,
            "eggs": self.eggs,
            "plants": self.plants,
            "rocks": self.rocks,
            "snails": self.snails,
            "decorations": self.decorations,
            "shells": self.shells,
            "day": self.day,
            "tick": self.tick,
            "use_color": self.use_color,
            "old_age_mortality": self.old_age_mortality,
            "discovered_species": self.discovered_species,
            "hatch_count": self.hatch_count,
            "rare_egg_stock": self.rare_egg_stock,
            "selected_fish_index": self.selected_fish_index,
            "water_quality": getattr(self, "water_quality", 82),
            "selected_food_index": getattr(self, "selected_food_index", 0),
            "aquarium_journal": getattr(self, "aquarium_journal", []),
            "upgrades": getattr(self, "upgrades", {"tank": 0, "filter": 0, "bubbler": 0, "nursery": 0, "feeder": 0}),
        }
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            SAVE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.saved_notice = 35
            self.log(f"The tank is saved to {SAVE_FILE}.")
        except Exception as exc:
            # Last-resort fallback: try the user's home directory. This keeps the
            # app usable even when APPDATA is redirected or locked down.
            try:
                fallback = Path.home() / SAVE_FILENAME
                fallback.write_text(json.dumps(data, indent=2), encoding="utf-8")
                self.saved_notice = 35
                self.log(f"The tank is saved to {fallback}.")
            except Exception:
                self.log(f"Save failed: {exc}")

    def load(self):
        load_path = SAVE_FILE

        # Backward compatibility: v0.5 saved beside the script/current working
        # directory. If that old file exists and the new AppData save does not,
        # load the old one and future saves will migrate to the safer location.
        if not load_path.exists() and LEGACY_SAVE_FILE.exists() and LEGACY_SAVE_FILE.is_file():
            load_path = LEGACY_SAVE_FILE

        if not load_path.exists():
            self.log("No save file exists yet.")
            return
        try:
            data = json.loads(load_path.read_text(encoding="utf-8"))
            self.fish = data.get("fish", self.fish)
            self.eggs = data.get("eggs", getattr(self, "eggs", []))
            self.plants = data.get("plants", self.plants)
            self.rocks = data.get("rocks", self.rocks)
            self.snails = data.get("snails", self.snails)
            self.decorations = data.get("decorations", self.decorations)
            self.shells = data.get("shells", self.shells)
            self.day = data.get("day", self.day)
            self.tick = data.get("tick", self.tick)
            self.use_color = bool(data.get("use_color", self.use_color)) and terminal_supports_ansi()
            self.old_age_mortality = data.get("old_age_mortality", self.old_age_mortality)
            self.discovered_species = data.get("discovered_species", getattr(self, "discovered_species", []))
            self.hatch_count = data.get("hatch_count", getattr(self, "hatch_count", 0))
            self.rare_egg_stock = data.get("rare_egg_stock", getattr(self, "rare_egg_stock", 0))
            self.selected_fish_index = int(data.get("selected_fish_index", getattr(self, "selected_fish_index", 0)))
            self.water_quality = int(data.get("water_quality", getattr(self, "water_quality", 82)))
            self.selected_food_index = int(data.get("selected_food_index", getattr(self, "selected_food_index", 0))) % len(FOOD_TYPES)
            self.aquarium_journal = data.get("aquarium_journal", getattr(self, "aquarium_journal", []))
            self.upgrades = data.get("upgrades", getattr(self, "upgrades", {"tank": 0, "filter": 0, "bubbler": 0, "nursery": 0, "feeder": 0}))
            for _u in UPGRADE_CATALOG:
                self.upgrades.setdefault(_u, 0)
            self.show_tank_journal = False
            self.show_profile = False
            for fish in self.fish:
                self.ensure_fish_age_fields(fish)
                self.discover_species(fish.get("species", "guppy"), silent=True)
            self.food = []
            self.bubbles = [make_bubble(self.width, self.height) for _ in range(16)]
            self.visitors = []
            if not hasattr(self, "eggs"):
                self.eggs = []
            if not self.fish and not self.eggs:
                self.eggs = [make_egg(self.width, self.height)]
            self.log("The saved tank bubbles back to life.")
        except Exception as exc:
            self.log(f"Load failed: {exc}")

    def handle_input(self):
        key = get_key()
        if not key:
            return

        if key == "q":
            if self.autosave:
                self.save()
            self.running = False
        elif key == "f":
            self.feed()
        elif key == "a":
            self.add_egg(free=True)
        elif key == "n":
            self.name_fish_prompt()
        elif key == "r":
            self.reset_to_egg()
        elif key == "b":
            self.add_bubbles()
        elif key == "p":
            self.paused = not self.paused
            self.log("The tank pauses." if self.paused else "The tank resumes.")
        elif key == "s":
            self.save()
        elif key == "l":
            self.load()
        elif key == "v":
            self.screensaver = not self.screensaver
            self.log("Screensaver mode enabled." if self.screensaver else "Screensaver mode disabled.")
        elif key == "c":
            self.use_color = not self.use_color
            self.log("Color enabled." if self.use_color else "Color disabled.")
        elif key == "h":
            self.show_help = not self.show_help
            if self.show_help:
                self.show_journal = False
                self.show_profile = False
                self.show_tank_journal = False
        elif key == "j":
            self.show_journal = not self.show_journal
            if self.show_journal:
                self.show_help = False
                self.show_profile = False
                self.show_tank_journal = False
        elif key == "i":
            self.show_profile = not self.show_profile
            if self.show_profile:
                self.show_help = False
                self.show_journal = False
                self.show_tank_journal = False
                self.selected_fish_index = self.clamped_selected_index()
        elif key == "[":
            if self.fish:
                self.selected_fish_index = (self.clamped_selected_index() - 1) % len(self.fish)
                self.show_profile = True
                self.show_help = False
                self.show_journal = False
        elif key == "]":
            if self.fish:
                self.selected_fish_index = (self.clamped_selected_index() + 1) % len(self.fish)
                self.show_profile = True
                self.show_help = False
                self.show_journal = False
        elif key == "g":
            self.cycle_food()
        elif key == "w":
            self.clean_tank()
        elif key == "k":
            self.show_tank_journal = not getattr(self, "show_tank_journal", False)
            if self.show_tank_journal:
                self.show_help = False
                self.show_journal = False
                self.show_profile = False
        elif key == "x":
            self.sell_fish_prompt()
        elif key == "d":
            self.remove_decoration_prompt()
        elif key == "m":
            self.old_age_mortality = not self.old_age_mortality
            self.log("Old-age mortality enabled." if self.old_age_mortality else "Old-age mortality disabled.")
        elif key == "1":
            self.buy_fish()
        elif key == "2":
            self.buy_plant()
        elif key == "3":
            self.buy_decoration()
        elif key == "4":
            self.buy_snail()
        elif key == "5":
            self.buy_rare_egg()
        elif key == "6":
            self.buy_upgrade("tank")
        elif key == "7":
            self.buy_upgrade("filter")
        elif key == "8":
            self.buy_upgrade("bubbler")
        elif key == "9":
            self.buy_upgrade("nursery")
        elif key == "0":
            self.buy_upgrade("feeder")

    def clamped_selected_index(self):
        if not self.fish:
            return 0
        return max(0, min(len(self.fish) - 1, int(getattr(self, "selected_fish_index", 0))))

    def current_phase(self):
        # One displayed tank day is 600 ticks; split it into handheld-style periods.
        slot = self.tick % 600
        if slot < 120:
            return "Morning"
        if slot < 360:
            return "Day"
        if slot < 480:
            return "Evening"
        return "Night"

    def spend(self, amount):
        if self.shells < amount:
            self.log(f"Not enough money. You need ${amount}.")
            return False
        self.shells -= amount
        return True

    def buy_fish(self):
        if self.spend(12):
            self.add_egg(free=False)

    def buy_rare_egg(self):
        if self.spend(30):
            self.add_egg(free=False, rare_egg=True)

    def buy_plant(self):
        if self.spend(8):
            self.plants.append(make_plant(self.width, self.height))
            self.log("A new plant takes root in the gravel.")

    def buy_decoration(self):
        if self.spend(15):
            decor = random.choice(DECOR_TYPES)
            self.decorations.append(make_decoration(self.width, self.height, decor))
            self.log(f"A {decor['name']} is placed in the tank.")

    def buy_snail(self):
        if self.spend(10):
            snail = make_snail(self.width, self.height)
            self.snails.append(snail)
            self.log(f"{snail['name']} the snail joins the slow expedition.")

    def fish_capacity(self):
        return MAX_FISH + upgrade_level(self, "tank") * 6

    def buy_upgrade(self, name):
        if name not in UPGRADE_CATALOG:
            self.log("That upgrade does not exist.")
            return
        self.upgrades = getattr(self, "upgrades", {"tank": 0, "filter": 0, "bubbler": 0, "nursery": 0, "feeder": 0})
        for key in UPGRADE_CATALOG:
            self.upgrades.setdefault(key, 0)
        cost = next_upgrade_cost(self, name)
        data = UPGRADE_CATALOG[name]
        if cost is None:
            self.log(f"{data['name']} is already fully upgraded.")
            return
        if not self.spend(cost):
            return
        self.upgrades[name] = upgrade_level(self, name) + 1
        level = self.upgrades[name]
        self.log(f"Upgrade purchased: {data['name']} Lv{level}. {data['desc']}")
        if name == "tank":
            self.log(f"Tank capacity is now {self.fish_capacity()} fish/eggs.")
        elif name == "filter":
            self.water_quality = min(100, getattr(self, "water_quality", 70) + 10)
        elif name == "bubbler":
            self.add_bubbles()
        elif name == "nursery":
            for egg in getattr(self, "eggs", []):
                egg["hatch_time"] = max(180, int(egg.get("hatch_time", EGG_HATCH_MAX) * 0.90))

    def sell_fish_prompt(self):
        if not self.fish:
            self.log("There are no fish to sell yet.")
            return
        sell_fish_interactively(self)

    # Backward-compatible alias in case an old call path reaches this method.
    def release_fish_prompt(self):
        self.sell_fish_prompt()

    def remove_decoration_prompt(self):
        if not self.decorations:
            self.log("There are no decorations to remove.")
            return
        remove_decoration_interactively(self)

    def reset_to_egg(self):
        self.fish = []
        self.eggs = [make_egg(self.width, self.height)]
        self.food = []
        self.bubbles = [make_bubble(self.width, self.height) for _ in range(16)]
        self.visitors = []
        self.day = 1
        self.tick = 0
        self.shells = 25
        self.discovered_species = []
        self.hatch_count = 0
        self.rare_egg_stock = 0
        self.water_quality = 82
        self.selected_food_index = 0
        self.aquarium_journal = []
        self.show_tank_journal = False
        self.upgrades = {"tank": 0, "filter": 0, "bubbler": 0, "nursery": 0, "feeder": 0}
        self.event_log = [
            "The tank has been refreshed.",
            "A single mystery egg rests in the gravel.",
            "Press N after it hatches to name your first fish.",
        ]

    def current_food_type(self):
        if not hasattr(self, "selected_food_index"):
            self.selected_food_index = 0
        self.selected_food_index %= len(FOOD_TYPES)
        return FOOD_TYPES[self.selected_food_index]

    def cycle_food(self):
        self.selected_food_index = (getattr(self, "selected_food_index", 0) + 1) % len(FOOD_TYPES)
        food = self.current_food_type()
        self.log(f"Selected food: {food['name']}.")

    def feed(self):
        if len(self.food) >= MAX_FOOD:
            self.log("There is already plenty of food floating around.")
            return
        food = self.current_food_type()
        count = random.randint(7, 12)
        if food["key"] == "algae":
            count = random.randint(3, 5)
        elif food["key"] == "golden":
            count = random.randint(2, 4)
        for _ in range(count):
            self.food.append(make_food(self.width, food["key"]))
        self.log(f"{food['name']} drift down through the water.")

    def clean_tank(self):
        before = getattr(self, "water_quality", 70)
        self.water_quality = min(100, before + 22 + upgrade_level(self, "filter") * 8)
        # Cleaning also removes a bit of leftover food from the gravel area.
        self.food = [food for food in self.food if food.get("y", 0) < self.height - 5]
        self.log(f"The glass is cleaned. Water quality: {water_quality_label(self.water_quality)}.")

    def add_egg(self, free=False, rare_egg=False):
        if len(self.fish) + len(self.eggs) >= self.fish_capacity():
            self.log(f"The tank is at capacity ({self.fish_capacity()}). Buy Roomy Tank upgrades or sell fish.")
            return
        egg = make_egg(self.width, self.height, rare_egg=rare_egg, tank=self)
        self.eggs.append(egg)
        if rare_egg:
            prefix = "A shimmering rare egg arrives from the aquarium shop."
        else:
            prefix = "A mystery egg appears in the gravel." if free else "A mystery egg arrives from the aquarium shop."
        self.log(prefix)

    def adopt_fish(self, free=False):
        # Backward-compatible helper for old key bindings/saves; new tanks use eggs.
        self.add_egg(free=free)

    def name_fish_prompt(self):
        if not self.fish:
            self.log("There are no hatched fish to name yet.")
            return
        name_fish_interactively(self)

    def add_bubbles(self):
        for _ in range(16):
            if len(self.bubbles) < MAX_BUBBLES:
                self.bubbles.append(make_bubble(self.width, self.height))
        self.log("A burst of bubbles rises from the gravel.")

    def update(self):
        if self.paused:
            return

        self.tick += 1
        if self.saved_notice > 0:
            self.saved_notice -= 1

        if self.tick % 600 == 0:
            self.day += 1
            self.shells += random.randint(3, 7)
            self.log(f"Day {self.day} begins. You find a few dollars near the tank.")
            if self.autosave:
                self.save()

        if self.tick % 250 == 0:
            self.width, self.height = get_terminal_size()
            self.clamp_world()

        self.update_eggs()
        self.update_fish()
        self.update_bubbles()
        self.update_food()
        self.update_water_quality()
        self.update_upgrades()
        self.update_plants()
        self.update_snails()
        self.update_visitors()
        self.random_events()

    def clamp_world(self):
        for egg in getattr(self, "eggs", []):
            egg["x"] = max(2, min(self.width - 5, int(egg.get("x", 3))))
            egg["y"] = self.height - 3
        for f in self.fish:
            symbol = fish_symbol(f)
            max_x = max(1, self.width - len(symbol) - 1)
            f["x"] = max(1, min(max_x, int(f.get("x", 2))))
            f["y"] = max(2, min(self.height - 4, int(f.get("y", 2))))
        for p in self.plants:
            p["x"] = max(3, min(self.width - 4, int(p.get("x", 3))))
        for s in self.snails:
            s["x"] = max(2, min(self.width - 4, int(s.get("x", 2))))
            s["y"] = self.height - 3
        for d in self.decorations:
            d["x"] = max(3, min(self.width - 8, int(d.get("x", 3))))
            d["y"] = self.height - 4

    def ensure_fish_age_fields(self, f):
        # Upgrade older save files gracefully.
        f.setdefault("age", random.randint(50, 5000))
        f.setdefault("lifespan", random.randint(MIN_LIFESPAN, MAX_LIFESPAN))
        f.setdefault("elder_announced", False)
        f.setdefault("parents", [])
        f.setdefault("parent_names", [])
        f.setdefault("children", [])
        f.setdefault("generation", 1)
        f.setdefault("hatched_day", getattr(self, "day", 1))
        f.setdefault("last_stage", self.age_stage(f) if hasattr(self, "age_stage") else fish_stage_from_data(f))
        f.setdefault("favorite_depth", random.randint(3, max(4, self.height - 5)))
        f.setdefault("personality", random.choice(PERSONALITIES))
        f.setdefault("favorite_food", random.choice([food["key"] for food in FOOD_TYPES]))
        f.setdefault("favorite_decor", random.choice([decor["name"] for decor in DECOR_TYPES]))
        f.setdefault("favorite_time", random.choice(["Morning", "Day", "Evening", "Night"]))
        f.setdefault("best_friend", None)

    def age_stage(self, f):
        age = f.get("age", 0)
        lifespan = f.get("lifespan", MAX_LIFESPAN)
        if age < FRY_AGE:
            return "fry"
        if age < ADULT_AGE:
            return "young"
        if age >= int(lifespan * ELDER_AGE_RATIO):
            return "elder"
        return "adult"

    def maybe_handle_old_age(self, f):
        self.ensure_fish_age_fields(f)
        stage = self.age_stage(f)

        if stage == "elder" and not f.get("elder_announced", False):
            f["elder_announced"] = True
            f["mood"] = "wise"
            if random.random() < 0.70:
                self.log(f"{f.get('name', 'A fish')} has become an elder of the tank.")

        if not self.old_age_mortality:
            return False

        # Fish only pass away after exceeding their individual lifespan.
        # The chance is small per tick, so old residents linger for a while.
        if f.get("age", 0) >= f.get("lifespan", MAX_LIFESPAN):
            extra_age = f.get("age", 0) - f.get("lifespan", MAX_LIFESPAN)
            chance = min(0.006, OLD_AGE_DEATH_CHANCE + extra_age / 900000)
            if random.random() < chance:
                self.log(f"{f.get('name', 'A fish')} lived a long life and quietly passes beyond the bubbles.")
                self.shells += random.randint(1, 4)
                return True
        return False

    def update_eggs(self):
        if not hasattr(self, "eggs"):
            self.eggs = []
        hatched = []
        for egg in list(self.eggs):
            egg["age"] = egg.get("age", 0) + 1
            egg["y"] = self.height - 3
            if random.random() < 0.015:
                egg["x"] += random.choice([-1, 0, 1])
                egg["x"] = max(2, min(self.width - 5, int(egg.get("x", 3))))
            if egg["age"] >= egg.get("hatch_time", EGG_HATCH_MAX):
                baby = make_fish(self.width, self.height, baby=True)
                baby["species"] = egg.get("species", baby["species"])
                baby["x"] = max(2, min(self.width - len(fish_symbol(baby)) - 2, int(egg.get("x", 3))))
                baby["y"] = max(2, min(self.height - 4, self.height - 4))
                baby["name"] = f"Unnamed {baby['species']}"
                baby["parents"] = list(egg.get("parents", []))
                baby["parent_names"] = list(egg.get("parent_names", []))
                baby["generation"] = int(egg.get("generation", 1))
                baby["hatched_day"] = self.day
                baby["last_stage"] = "fry"
                self.fish.append(baby)
                # Link the child back to living parents when possible.
                for parent in self.fish:
                    if parent.get("id") in baby["parents"]:
                        parent.setdefault("children", [])
                        if baby["name"] not in parent["children"]:
                            parent["children"].append(baby["name"])
                self.selected_fish_index = len(self.fish) - 1
                hatched.append(egg)
                self.hatch_count = getattr(self, "hatch_count", 0) + 1
                self.discover_species(baby["species"])
                rarity = RARITY_LABELS.get(species_rarity(baby["species"]), "Common")
                lineage = f" Parents: {' + '.join(baby['parent_names'])}." if baby.get("parent_names") else ""
                self.log(f"An egg hatches into a tiny {baby['species']}! ({rarity}) Press N to name it.{lineage}")
        for egg in hatched:
            if egg in self.eggs:
                self.eggs.remove(egg)

    def update_fish(self):
        departed = []

        for f in list(self.fish):
            self.ensure_fish_age_fields(f)
            species = species_by_name(f.get("species", "guppy"))
            symbol = species["right"] if f.get("dir", 1) == 1 else species["left"]
            fish_length = len(symbol)
            personality = f.get("personality", "calm")
            f["age"] = f.get("age", 0) + 1

            if self.maybe_handle_old_age(f):
                departed.append(f)
                continue

            stage = self.age_stage(f)
            previous_stage = f.get("last_stage", stage)
            if previous_stage != stage:
                f["last_stage"] = stage
                if stage == "young":
                    self.log(f"{f.get('name', 'A fish')} has grown into a young {f.get('species', 'fish')}.")
                elif stage == "adult":
                    self.log(f"{f.get('name', 'A fish')} is now an adult {f.get('species', 'fish')}.")
                elif stage == "elder":
                    self.log(f"{f.get('name', 'A fish')} has become an elder of the tank.")

            # Hunger slowly increases.
            hunger_rate = 0.014
            if personality == "sleepy":
                hunger_rate = 0.010
            elif personality == "bold":
                hunger_rate = 0.018
            if random.random() < hunger_rate:
                f["hunger"] = min(100, f.get("hunger", 0) + 1)

            # Mood from hunger.
            if f["hunger"] > 75:
                f["mood"] = "hungry"
            elif f["hunger"] < 25 and random.random() < 0.01:
                f["mood"] = random.choice(["content", "calm", "curious"])

            # Pausing behavior.
            if f.get("pause", 0) > 0:
                f["pause"] -= 1
                continue

            pause_chance = 0.018
            if personality == "sleepy":
                pause_chance = 0.045
            elif personality == "bold":
                pause_chance = 0.009
            if random.random() < pause_chance:
                f["pause"] = random.randint(5, 26)

            target = self.choose_target_for_fish(f)
            if target:
                tx, ty = target
                if tx > f["x"]:
                    f["dir"] = 1
                elif tx < f["x"]:
                    f["dir"] = -1
                if random.random() < 0.32:
                    if ty > f["y"]:
                        f["y"] += 1
                    elif ty < f["y"]:
                        f["y"] -= 1

            speed = species["speed_chance"]
            vertical = species["vertical_chance"]
            if personality == "lazy" or personality == "sleepy":
                speed *= 0.72
            if personality == "bold":
                speed = min(0.95, speed * 1.12)
            if personality == "curious":
                vertical *= 1.25
            if stage == "fry":
                speed *= 0.84
                vertical *= 1.35
            elif stage == "elder":
                speed *= 0.62
                vertical *= 0.75

            phase = self.current_phase()
            if phase == "Night":
                if personality == "nocturnal":
                    speed = min(0.98, speed * 1.25)
                    vertical *= 1.15
                    if random.random() < 0.006:
                        f["mood"] = "moonlit"
                else:
                    speed *= 0.58
                    vertical *= 0.55
                    if random.random() < 0.01:
                        f["mood"] = "sleepy"
            elif phase == "Morning" and random.random() < 0.004:
                f["mood"] = random.choice(["fresh", "curious", "content"])

            if random.random() < speed:
                f["x"] += f.get("dir", 1)

            if random.random() < vertical:
                f["y"] += random.choice([-1, 1])

            # Favorite depth pull.
            if random.random() < 0.045:
                fav = f.get("favorite_depth", f["y"])
                if f["y"] < fav:
                    f["y"] += 1
                elif f["y"] > fav:
                    f["y"] -= 1

            # Rare turn.
            if random.random() < 0.006:
                f["dir"] *= -1

            # Wall behavior.
            if f["x"] <= 2:
                f["x"] = 2
                f["dir"] = 1
            max_fish_x = max(1, self.width - fish_length - 1)
            if f["x"] >= max_fish_x:
                f["x"] = max_fish_x
                f["dir"] = -1
            f["y"] = max(2, min(self.height - 4, f["y"]))

            # Eat nearby food.
            eaten = None
            for food in self.food:
                if abs(food["x"] - f["x"]) <= fish_length and abs(food["y"] - f["y"]) <= 1:
                    eaten = food
                    break
            if eaten:
                self.food.remove(eaten)
                food_type = food_type_by_key(eaten.get("kind", "flakes"))
                low, high = food_type.get("hunger", (24, 46))
                bonus = 8 if f.get("favorite_food") == food_type["key"] else 0
                if food_type["key"] == "night" and self.current_phase() == "Night":
                    bonus += 6
                f["hunger"] = max(0, f["hunger"] - random.randint(low, high) - bonus)
                f["mood"] = random.choice(food_type.get("mood", ["content"]))
                if f.get("favorite_food") == food_type["key"] and random.random() < 0.35:
                    self.log(f"{f['name']} loves the {food_type['name']}.")
                elif random.random() < 0.28:
                    self.log(f"{f['name']} nibbles {food_type['name']}.")

        for f in departed:
            if f in self.fish:
                self.fish.remove(f)

        self.maybe_breed_fish()

    def choose_target_for_fish(self, f):
        personality = f.get("personality", "calm")

        # Hungry fish target food.
        if self.food and f.get("hunger", 0) > (18 if personality == "greedy" else (24 if personality == "curious" else 32)):
            food = min(self.food, key=lambda item: abs(item["x"] - f["x"]) + abs(item["y"] - f["y"]))
            return food["x"], food["y"]

        # Shy fish like plants.
        if personality == "shy" and self.plants and random.random() < 0.10:
            plant = min(self.plants, key=lambda p: abs(p["x"] - f["x"]))
            return plant["x"], self.height - 4

        # Social fish drift toward other fish.
        if personality == "social" and len(self.fish) > 1 and random.random() < 0.08:
            others = [other for other in self.fish if other is not f]
            friend = min(others, key=lambda other: abs(other["x"] - f["x"]) + abs(other["y"] - f["y"]))
            return friend["x"], friend["y"]

        # Bubble obsessed fish follow bubbles.
        if personality == "bubble-obsessed" and self.bubbles and random.random() < 0.13:
            bubble = min(self.bubbles, key=lambda b: abs(b["x"] - f["x"]) + abs(b["y"] - f["y"]))
            return bubble["x"], bubble["y"]

        # Fish sometimes visit their favorite decoration.
        if self.decorations and f.get("favorite_decor") and random.random() < 0.035:
            liked = [d for d in self.decorations if d.get("kind") == f.get("favorite_decor") or d.get("name") == f.get("favorite_decor")]
            if liked:
                decor = random.choice(liked)
                return decor["x"], decor["y"]

        # Curious fish inspect decorations.
        if personality == "curious" and self.decorations and random.random() < 0.06:
            decor = random.choice(self.decorations)
            return decor["x"], decor["y"]

        return None

    def maybe_breed_fish(self):
        if len(self.fish) + len(getattr(self, "eggs", [])) >= self.fish_capacity():
            return
        if len(self.fish) < 2:
            return
        if self.tick < 1000:
            return
        base_chance = 0.0009
        if getattr(self, "water_quality", 70) >= 88:
            base_chance *= 1.35
        base_chance *= 1.0 + upgrade_level(self, "nursery") * 0.18
        if any(food.get("kind") == "golden" for food in self.food):
            base_chance *= 1.18
        if random.random() > base_chance:
            return

        happy_fish = [
            f for f in self.fish
            if f.get("hunger", 100) < 35 and self.age_stage(f) == "adult"
        ]
        if len(happy_fish) >= 2:
            parent_a, parent_b = random.sample(happy_fish, 2)
            chosen_species = random.choice([parent_a.get("species"), parent_b.get("species")])
            egg = make_egg(self.width, self.height, chosen_species, tank=self)
            egg["x"] = int((parent_a.get("x", egg["x"]) + parent_b.get("x", egg["x"])) / 2)
            egg["y"] = self.height - 3
            egg["parents"] = [parent_a.get("id"), parent_b.get("id")]
            egg["parent_names"] = [parent_a.get("name", "Unknown"), parent_b.get("name", "Unknown")]
            egg["generation"] = max(int(parent_a.get("generation", 1)), int(parent_b.get("generation", 1))) + 1
            self.eggs.append(egg)
            self.log(f"A small {egg['species']} egg appears among the plants. Parents: {parent_a.get('name')} + {parent_b.get('name')}.")

    def update_bubbles(self):
        # Natural bubble spawns. Decorations make bubbles feel localized.
        bubble_cap = MAX_BUBBLES + upgrade_level(self, "bubbler") * 40
        bubble_chance = 0.22 + upgrade_level(self, "bubbler") * 0.055
        if random.random() < bubble_chance and len(self.bubbles) < bubble_cap:
            source_x = None
            if self.decorations and random.random() < 0.40:
                source_x = random.choice(self.decorations)["x"]
            self.bubbles.append(make_bubble(self.width, self.height, source_x))

        for bubble in self.bubbles:
            bubble["age"] += 1
            bubble["y"] -= 1
            if random.random() < 0.35:
                bubble["x"] += bubble["drift"]
            if random.random() < 0.08:
                bubble["drift"] = random.choice([-1, 0, 0, 0, 1])
            bubble["x"] = max(2, min(self.width - 3, bubble["x"]))

        self.bubbles = [b for b in self.bubbles if b["y"] > 1 and b["age"] < self.height + 12]

    def update_food(self):
        for food in self.food:
            food.setdefault("kind", "flakes")
            food.setdefault("glyph", food_type_by_key(food.get("kind", "flakes"))["glyph"])
            food.setdefault("color", food_type_by_key(food.get("kind", "flakes"))["color"])
            food["age"] = food.get("age", 0) + 1
            food["fall_progress"] += food["fall_speed"]
            if food["fall_progress"] >= 1.0:
                food["fall_progress"] = 0.0
                food["y"] += 1
                if random.random() < 0.25:
                    food["x"] += random.choice([-1, 0, 1])
            food["x"] = max(2, min(self.width - 3, food["x"]))
        self.food = [food for food in self.food if food["y"] < self.height - 2]

    def update_water_quality(self):
        if not hasattr(self, "water_quality"):
            self.water_quality = 82
        leftover_penalty = max(0, len(self.food) - 18) * 0.010
        plant_bonus = min(0.030, len(self.plants) * 0.0025)
        snail_bonus = min(0.024, len(self.snails) * 0.004)
        filter_bonus = upgrade_level(self, "filter") * 0.010
        crowd_limit = 14 + upgrade_level(self, "tank") * 5
        crowd_penalty = max(0, len(self.fish) + len(getattr(self, "eggs", [])) - crowd_limit) * 0.004
        natural_drift = -0.006 - leftover_penalty - crowd_penalty + plant_bonus + snail_bonus + filter_bonus
        if water_quality_label(self.water_quality) == "Murky" and self.snails:
            natural_drift += 0.008
        self.water_quality = max(0, min(100, self.water_quality + natural_drift))
        if random.random() < 0.0009 and self.water_quality < 45:
            self.log("The water looks murky. Press W to clean the tank.")
        elif random.random() < 0.0007 and self.water_quality > 88:
            self.log("The water sparkles beautifully in the light.")

    def update_upgrades(self):
        feeder = upgrade_level(self, "feeder")
        if feeder and len(self.food) < MAX_FOOD // 2:
            # A gentle auto-feeder: enough to keep the tank alive-feeling, not enough to flood it.
            if random.random() < 0.0012 * feeder:
                count = 1 + (1 if feeder >= 3 and random.random() < 0.35 else 0)
                for _ in range(count):
                    self.food.append(make_food(self.width, self.current_food_type()["key"]))
                if random.random() < 0.45:
                    self.log("The auto-feeder drops a tiny snack.")

    def update_plants(self):
        for plant in self.plants:
            plant["growth"] = plant.get("growth", 0) + 1
            if plant["growth"] > 900 and plant["height"] < 9:
                plant["growth"] = 0
                plant["height"] += 1
                if random.random() < 0.30:
                    self.log("One of the plants grows a little taller.")

    def update_snails(self):
        for snail in self.snails:
            snail["age"] = snail.get("age", 0) + 1
            snail["move_timer"] -= 1
            if snail["move_timer"] <= 0:
                snail["x"] += snail["dir"]
                snail["move_timer"] = random.randint(5, 28)
                if random.random() < 0.08:
                    snail["dir"] *= -1
            if snail["x"] <= 2:
                snail["x"] = 2
                snail["dir"] = 1
            if snail["x"] >= self.width - 4:
                snail["x"] = self.width - 4
                snail["dir"] = -1

    def update_visitors(self):
        if not self.visitors and random.random() < 0.0009:
            visitor = make_visitor(self.width, self.height)
            self.visitors.append(visitor)
            self.log(f"A rare {visitor['name']} drifts through the tank.")

        for visitor in self.visitors:
            visitor["life"] -= 1
            if random.random() < 0.65:
                visitor["x"] += visitor["dir"]
            if random.random() < 0.10:
                visitor["y"] += random.choice([-1, 1])
            visitor["y"] = max(2, min(self.height - 5, visitor["y"]))

        self.visitors = [
            v for v in self.visitors
            if v["life"] > 0 and -10 < v["x"] < self.width + 10
        ]

    def random_events(self):
        if not self.fish:
            return
        if random.random() < 0.003:
            fish = random.choice(self.fish)
            self.log(f"{fish['name']} darts through the bubbles.")
        if random.random() < 0.0024:
            fish = random.choice(self.fish)
            self.log(f"{fish['name']} inspects the gravel.")
        if random.random() < 0.0018:
            fish = random.choice(self.fish)
            self.log(f"{fish['name']} seems {fish.get('mood', 'thoughtful')}.")
        if random.random() < 0.0015:
            self.log("The plants sway gently in the current.")
        if random.random() < 0.0012 and self.snails:
            snail = random.choice(self.snails)
            self.log(f"{snail['name']} continues a mysterious journey.")
        if random.random() < 0.001:
            self.shells += 1
            self.log("You find a stray dollar beside the tank.")
        if len(self.fish) >= 2 and random.random() < 0.0016:
            a, b = random.sample(self.fish, 2)
            a["best_friend"] = b.get("name")
            self.log(f"{a.get('name')} seems to be following {b.get('name')} around.")
        if self.decorations and random.random() < 0.0013:
            fish = random.choice(self.fish)
            decor = random.choice(self.decorations)
            if fish.get("favorite_decor") == decor.get("kind"):
                self.log(f"{fish.get('name')} looks especially happy near the {decor.get('kind')}.")


# ----------------------------
# Rendering
# ----------------------------

class Cell:
    __slots__ = ("ch", "color")
    def __init__(self, ch=" ", color="text"):
        self.ch = ch
        self.color = color


def make_grid(width, height):
    return [[Cell() for _ in range(width)] for _ in range(height)]


def safe_draw(grid, x, y, char, color="text"):
    height = len(grid)
    width = len(grid[0])
    if 0 <= y < height and 0 <= x < width:
        grid[y][x].ch = char
        grid[y][x].color = color


def safe_draw_text(grid, x, y, text, color="text"):
    """Draw text into the grid, clipping safely at the tank edge."""
    if not grid:
        return
    width = len(grid[0])
    text = str(text)
    if y < 0 or y >= len(grid):
        return
    if x >= width:
        return
    if x < 0:
        text = text[-x:]
        x = 0
    max_len = max(0, width - x)
    for i, char in enumerate(text[:max_len]):
        safe_draw(grid, x + i, y, char, color)


def bounded_sprite_x(width, x, sprite, left_margin=1, right_margin=1):
    """Clamp a sprite's x position so it does not get chopped off on the right."""
    sprite_len = max(1, len(str(sprite)))
    min_x = left_margin
    max_x = max(min_x, width - right_margin - sprite_len)
    return max(min_x, min(int(x), max_x))


def visible_text_width(width=None):
    cols = shutil.get_terminal_size((DEFAULT_WIDTH, DEFAULT_HEIGHT)).columns
    base = width if width is not None else cols
    return max(20, min(cols - 1, base if base else cols - 1))


def display_text_line(text, width=None, color="text", enabled=True, indent="", wrap=True):
    """Print UI text safely. Long lines wrap instead of disappearing off the right."""
    limit = visible_text_width(width)
    raw = indent + str(text)
    if not wrap:
        print(color_text(raw[:limit], color, enabled))
        return

    subsequent = " " * len(indent)
    lines = textwrap.wrap(
        raw,
        width=limit,
        subsequent_indent=subsequent,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]
    for line in lines:
        print(color_text(line[:limit], color, enabled))


def draw_multiline_sprite(grid, x, y, lines, color="decor"):
    width = len(grid[0]) if grid else 0
    for row_i, line in enumerate(lines):
        line_x = bounded_sprite_x(width, x, line)
        safe_draw_text(grid, line_x, y + row_i, line, color)


def render_grid(grid, use_color=True):
    lines = []
    for row in grid:
        pieces = []
        last_color = None
        for cell in row:
            if use_color:
                if cell.color != last_color:
                    pieces.append(COLOR.get(cell.color, COLOR["text"]))
                    last_color = cell.color
                pieces.append(cell.ch)
            else:
                pieces.append(cell.ch)
        if use_color:
            pieces.append(COLOR["reset"])
        lines.append("".join(pieces))
    return "\n".join(lines)


def fish_stage_from_data(f):
    age = f.get("age", 0)
    lifespan = f.get("lifespan", MAX_LIFESPAN)
    if age < FRY_AGE:
        return "fry"
    if age < ADULT_AGE:
        return "young"
    if age >= int(lifespan * ELDER_AGE_RATIO):
        return "elder"
    return "adult"


def fish_symbol(f):
    species = species_by_name(f.get("species", "guppy"))
    direction = f.get("dir", 1)
    stage = fish_stage_from_data(f)
    if stage == "fry":
        return "°>" if direction == 1 else "<°"
    if stage == "young":
        return ">°>" if direction == 1 else "<°<"
    if stage == "elder":
        adult = species["right"] if direction == 1 else species["left"]
        # A tiny visual hint that this is an old resident without changing the species completely.
        return adult.replace("°", "~", 1) if "°" in adult else adult
    return species["right"] if direction == 1 else species["left"]



def ui_box(title, lines, width, enabled=True, color="text"):
    """Print a tidy boxed UI panel below the tank.

    The box is terminal-width aware, wraps long content, and avoids depending on
    a right-side panel. This keeps the aquarium readable in narrow consoles.
    """
    box_width = max(34, visible_text_width(width))
    box_width = min(box_width, shutil.get_terminal_size((DEFAULT_WIDTH, DEFAULT_HEIGHT)).columns - 1)
    inner = max(10, box_width - 4)

    title = f" {title.strip()} " if title else ""
    top_rule_len = max(0, box_width - 2 - len(title))
    top = "+" + title + ("-" * top_rule_len) + "+"
    print(color_text(top[:box_width], "border", enabled))

    for raw in lines:
        raw = str(raw)
        if raw == "":
            print(color_text("| " + " " * inner + " |", color, enabled))
            continue
        wrapped = textwrap.wrap(
            raw,
            width=inner,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        for line in wrapped:
            print(color_text("| " + line.ljust(inner) + " |", color, enabled))

    print(color_text("+" + "-" * (box_width - 2) + "+", "border", enabled))


def ui_status_lines(tank):
    food = tank.current_food_type() if hasattr(tank, "current_food_type") else FOOD_TYPES[0]
    water_value = int(getattr(tank, "water_quality", 70))
    oldest = max(tank.fish, key=lambda f: f.get("age", 0)) if tank.fish else None
    lines = [
        f"Water: {water_quality_label(water_value)} ({water_value}/100)    Food: {food['name']}    Upgrades: {upgrade_summary(tank)}",
    ]
    if oldest:
        stage = fish_stage_from_data(oldest)
        age_days = oldest.get("age", 0) / 600
        life_days = oldest.get("lifespan", MAX_LIFESPAN) / 600
        lines.append(
            f"Oldest resident: {oldest.get('name', 'Unnamed')} | {stage} {oldest.get('species', 'fish')} | age {age_days:.1f}/{life_days:.1f} tank-days | mood {oldest.get('mood', 'mysterious')}"
        )
    else:
        lines.append("No fish have hatched yet. Watch the egg until it begins to wiggle.")
    return lines


def ui_help_lines(tank):
    next_costs = []
    for key in ["tank", "filter", "bubbler", "nursery", "feeder"]:
        item = UPGRADE_CATALOG[key]
        cost = next_upgrade_cost(tank, key)
        next_costs.append(f"{item['key']} {item['name']}: {'MAX' if cost is None else '$' + str(cost)}")
    return [
        "Main controls: Q quit/save, P pause, S save, L load, C color, V screensaver, R reset tank.",
        "Care controls: F feed selected food, G cycle food, W clean water, B add bubbles.",
        "Fish controls: A add mystery egg, N name/rename fish, I inspect profile, [ and ] cycle selected fish, X sell selected fish.",
        "Collection controls: J species album, K aquarium history, H hide/show this help panel, M toggle old-age mortality.",
        "",
        "Shop: 1 mystery egg (12), 2 plant (8), 3 decoration (15), 4 snail (10), 5 rare egg (30).",
        "Upgrades: " + " | ".join(next_costs),
        "D removes a decoration and refunds a few dollars. Decorations can lure certain rare fish.",
        "",
        "Tip: clean water, comfort, plants, snails, and nursery moss help eggs hatch and make rare outcomes a little more likely.",
        f"Save file: {SAVE_FILE}",
    ]


def ui_album_lines(tank):
    discovered = set(getattr(tank, "discovered_species", []))
    lines = [
        f"Discovered {len(discovered)}/{len(FISH_SPECIES)} species | Hatch count: {getattr(tank, 'hatch_count', 0)} | Comfort: {tank.comfort_score()} ({tank.comfort_grade()})",
        "Unknown species remain hidden as ???? until one hatches.",
        "",
    ]
    for rarity in RARITY_ORDER:
        names = [sp["name"] for sp in FISH_SPECIES if sp.get("rarity", "common") == rarity]
        if not names:
            continue
        shown = [name if name in discovered else "????" for name in names]
        lines.append(f"{RARITY_LABELS.get(rarity, rarity)}: " + ", ".join(shown))
    return lines


def ui_journal_lines(tank):
    history = getattr(tank, "aquarium_journal", [])[-16:]
    if not history:
        return ["No history has been recorded yet."]
    return history


def ui_profile_lines(tank):
    if not tank.fish:
        return [
            "No fish have hatched yet.",
            "Watch the egg, then press N to name the fry once it hatches.",
        ]
    idx = tank.clamped_selected_index()
    fish = tank.fish[idx]
    species = species_by_name(fish.get("species", "guppy"))
    stage = fish_stage_from_data(fish)
    age_days = fish.get("age", 0) / 600
    life_days = fish.get("lifespan", MAX_LIFESPAN) / 600
    rarity = RARITY_LABELS.get(species.get("rarity", "common"), "Common")
    fav_food = food_type_by_key(fish.get("favorite_food", "flakes"))["name"]
    parents = fish.get("parent_names") or ["First Egg / Aquarium Shop"]
    children = fish.get("children") or []
    return [
        f"Fish {idx + 1}/{len(tank.fish)}    Press [ or ] to cycle    Press N to rename    Press X to sell",
        f"Name: {fish.get('name', 'Unnamed')}",
        f"Species: {fish.get('species', 'fish')} | Rarity: {rarity} | Stage: {stage} | Generation {fish.get('generation', 1)}",
        f"Shop value: ${fish_sale_value(fish)}",
        f"Age: {age_days:.1f}/{life_days:.1f} tank-days | Hatched: Day {fish.get('hatched_day', '?')}",
        f"Personality: {fish.get('personality', 'calm')} | Mood: {fish.get('mood', 'mysterious')} | Hunger: {fish.get('hunger', 0)}/100",
        f"Favorites: {fav_food} | {fish.get('favorite_decor', 'decor')} | {fish.get('favorite_time', 'Day')} | Friend: {fish.get('best_friend') or 'none yet'}",
        "Parents: " + " + ".join(parents),
        "Children: " + (", ".join(children[:8]) if children else "none yet"),
        "Behavior: " + personality_behavior_text(fish.get("personality", "calm")),
    ]


def render(tank):
    grid = make_grid(tank.width, tank.height)
    width, height = tank.width, tank.height

    # Border.
    for x in range(width):
        safe_draw(grid, x, 0, "-", "border")
        safe_draw(grid, x, height - 1, "_", "border")
    for y in range(height):
        safe_draw(grid, 0, y, "|", "border")
        safe_draw(grid, width - 1, y, "|", "border")
    for x, y in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
        safe_draw(grid, x, y, "+", "border")

    # Water shimmer.
    shimmer_chars = ["~", "-", "~", " "]
    wave = math.sin(tank.tick / 10.0)
    for x in range(2, width - 2):
        if random.random() < 0.28 + 0.05 * wave:
            safe_draw(grid, x, 1, random.choice(shimmer_chars), "water")

    # Background current specks.
    if not tank.screensaver:
        for _ in range(max(5, width // 8)):
            if random.random() < 0.40:
                safe_draw(grid, random.randint(2, width - 3), random.randint(3, height - 6), ".", "dim")

    # Plants.
    for plant in tank.plants:
        sway = 0
        phase = plant.get("phase", 0)
        if (tank.tick + phase) % 28 < 9:
            sway = -1
        elif (tank.tick + phase) % 28 > 18:
            sway = 1
        base_x = int(plant.get("x", 4))
        plant_height = int(plant.get("height", 4))
        for i in range(plant_height):
            y = height - 2 - i
            x = base_x + (sway if i > plant_height // 2 else 0)
            char = "Y" if i == plant_height - 1 else ("/" if i % 2 == 0 else "\\")
            safe_draw(grid, x, y, char, "plant")

    # Rocks.
    for rock in tank.rocks:
        for i in range(int(rock.get("width", 3))):
            safe_draw(grid, int(rock.get("x", 3)) + i, height - 2, "#", "rock")

    # Decorations.
    for decor in tank.decorations:
        kind = decor.get("kind", decor.get("name", "castle"))
        sprite = decor_by_name(kind)["glyphs"]
        draw_multiline_sprite(grid, int(decor.get("x", 5)), int(decor.get("y", height - 4)), sprite, "decor")

    # Food.
    for food in tank.food:
        food_type = food_type_by_key(food.get("kind", "flakes"))
        safe_draw(grid, int(food["x"]), int(food["y"]), food.get("glyph", food_type["glyph"]), food.get("color", food_type["color"]))

    # Bubbles.
    for bubble in tank.bubbles:
        char = "o"
        if bubble["age"] % 7 == 0:
            char = "O"
        elif bubble["age"] % 5 == 0:
            char = "."
        safe_draw(grid, int(bubble["x"]), int(bubble["y"]), char, "bubble")

    # Eggs.
    for egg in getattr(tank, "eggs", []):
        hatch_ratio = egg.get("age", 0) / max(1, egg.get("hatch_time", EGG_HATCH_MAX))
        symbol = "(@)" if hatch_ratio > 0.82 and tank.tick % 10 < 5 else "(o)"
        draw_x = bounded_sprite_x(width, egg.get("x", 2), symbol, left_margin=1, right_margin=1)
        egg["x"] = draw_x
        safe_draw_text(grid, draw_x, int(egg.get("y", height - 3)), symbol, "food")

    # Snails.
    for snail in tank.snails:
        symbol = "_@/" if snail.get("dir", 1) == 1 else "\\@_"
        draw_x = bounded_sprite_x(width, snail.get("x", 2), symbol, left_margin=1, right_margin=1)
        snail["x"] = draw_x
        safe_draw_text(grid, draw_x, int(snail.get("y", height - 3)), symbol, "snail")

    # Rare visitors.
    for visitor in tank.visitors:
        symbol = visitor["right"] if visitor.get("dir", 1) == 1 else visitor["left"]
        draw_x = bounded_sprite_x(width, visitor.get("x", 2), symbol, left_margin=1, right_margin=1)
        safe_draw_text(grid, draw_x, int(visitor["y"]), symbol, "rare")

    # Fish.
    for f in tank.fish:
        species = species_by_name(f.get("species", "guppy"))
        symbol = fish_symbol(f)
        draw_x = bounded_sprite_x(width, f.get("x", 2), symbol, left_margin=1, right_margin=1)
        f["x"] = draw_x
        safe_draw_text(grid, draw_x, int(f.get("y", 2)), symbol, species.get("color", "fish"))

    hungry_count = sum(1 for f in tank.fish if f.get("hunger", 0) > 60)
    water_value = int(getattr(tank, "water_quality", 70))
    header_left = f" FISHTANK v1.5 | Day {tank.day} {tank.current_phase()} | ${tank.shells} "
    header_right = f"F:{len(tank.fish)} E:{len(getattr(tank, 'eggs', []))}/{tank.fish_capacity()} H:{hungry_count} C:{tank.comfort_grade()} W:{water_quality_grade(water_value)} {'PAUSED' if tank.paused else 'RUN'} "
    header = (header_left + header_right)[:width - 4]
    if tank.saved_notice > 0 and len(header) < width - 12:
        header += " | SAVED"
    safe_draw_text(grid, 2, 0, header[:width - 4], "text")

    if not tank.screensaver:
        controls = " F feed  G food  W clean  A egg  I profile  J album  K history  H help  X sell  Q quit "
        safe_draw_text(grid, 2, height - 1, controls[:width - 4], "text")

    begin_frame(tank.use_color)
    print(render_grid(grid, tank.use_color))

    if not tank.screensaver:
        print()
        ui_box("Events", tank.event_log[-MAX_EVENTS:], width, tank.use_color, "text")

        if tank.show_help:
            print()
            ui_box("Shop / Help", ui_help_lines(tank), width, tank.use_color, "text")
        elif getattr(tank, "show_tank_journal", False):
            print()
            ui_box("Aquarium History", ui_journal_lines(tank), width, tank.use_color, "text")
        elif getattr(tank, "show_profile", False):
            print()
            ui_box("Fish Profile", ui_profile_lines(tank), width, tank.use_color, "text")
        elif tank.show_journal:
            print()
            ui_box("Species Album", ui_album_lines(tank), width, tank.use_color, "text")
        else:
            print()
            ui_box("Tank Status", ui_status_lines(tank), width, tank.use_color, "dim")

    end_frame(tank.use_color)

def color_text(text, color, enabled=True):
    if not enabled:
        return text
    return COLOR.get(color, "") + text + COLOR["reset"]


def display_fish_profile(tank, width):
    if not tank.fish:
        display_text_line("Fish Profile", width, "text", tank.use_color)
        display_text_line("No fish have hatched yet. Watch the egg, then press N to name the fry.", width, "text", tank.use_color)
        return
    idx = tank.clamped_selected_index()
    fish = tank.fish[idx]
    species = species_by_name(fish.get("species", "guppy"))
    stage = fish_stage_from_data(fish)
    age_days = fish.get("age", 0) / 600
    life_days = fish.get("lifespan", MAX_LIFESPAN) / 600
    rarity = RARITY_LABELS.get(species.get("rarity", "common"), "Common")
    display_text_line(f"Fish Profile {idx + 1}/{len(tank.fish)}  ([ and ] cycle)", width, "text", tank.use_color)
    display_text_line(f"Name: {fish.get('name', 'Unnamed')}", width, "text", tank.use_color)
    display_text_line(f"Species: {fish.get('species', 'fish')} | Rarity: {rarity} | Stage: {stage} | Gen {fish.get('generation', 1)}", width, "text", tank.use_color)
    display_text_line(f"Shop value: ${fish_sale_value(fish)}", width, "text", tank.use_color)
    display_text_line(f"Age: {age_days:.1f}/{life_days:.1f} tank-days | Hatched: Day {fish.get('hatched_day', '?')}", width, "text", tank.use_color)
    display_text_line(f"Personality: {fish.get('personality', 'calm')} | Mood: {fish.get('mood', 'mysterious')} | Hunger: {fish.get('hunger', 0)}/100", width, "text", tank.use_color)
    fav_food = food_type_by_key(fish.get("favorite_food", "flakes"))["name"]
    display_text_line(f"Favorites: {fav_food} | {fish.get('favorite_decor', 'decor')} | {fish.get('favorite_time', 'Day')} | Friend: {fish.get('best_friend') or 'none yet'}", width, "text", tank.use_color)
    parents = fish.get("parent_names") or ["First Egg / Aquarium Shop"]
    children = fish.get("children") or []
    display_text_line("Parents: " + " + ".join(parents), width, "text", tank.use_color)
    display_text_line("Children: " + (", ".join(children[:8]) if children else "none yet"), width, "text", tank.use_color)
    behavior = personality_behavior_text(fish.get("personality", "calm"))
    display_text_line("Behavior: " + behavior, width, "dim", tank.use_color)


def personality_behavior_text(personality):
    return {
        "calm": "wanders steadily through open water",
        "curious": "inspects decorations and moves vertically more often",
        "sleepy": "pauses often and slows down at night",
        "bold": "patrols faster and turns less often",
        "shy": "prefers the cover of plants",
        "social": "drifts toward nearby fish",
        "bubble-obsessed": "follows bubbles whenever possible",
        "nocturnal": "becomes livelier during the night phase",
        "greedy": "spots food earlier than other fish",
    }.get(personality, "does fish things mysteriously")


def fish_sale_value(fish):
    """Return the dollar value for selling a fish.

    Value is intentionally simple and readable:
    rarity matters most, adults are worth more than fry, and later-generation
    fish get a small bonus because they represent successful tank breeding.
    """
    rarity = species_rarity(fish.get("species", "guppy"))
    rarity_base = {"common": 8, "uncommon": 15, "rare": 32, "legendary": 70}.get(rarity, 8)
    stage = fish_stage_from_data(fish)
    stage_mult = {"fry": 0.45, "young": 0.75, "adult": 1.20, "elder": 1.05}.get(stage, 1.0)
    generation_bonus = max(0, int(fish.get("generation", 1)) - 1) * 3
    name_bonus = 2 if fish.get("name") and fish.get("name") not in ("Tiny", "Bean", "Fry", "Little Fin", "Dot") else 0
    age_days_bonus = min(8, int(fish.get("age", 0) / 3000))
    return max(2, int(round(rarity_base * stage_mult)) + generation_bonus + name_bonus + age_days_bonus)


def sell_fish_interactively(tank):
    """Blocking fish sale prompt. Sold fish are exchanged for dollars."""
    global TERMINAL_OLD_SETTINGS
    restored = False
    if os.name != "nt" and TERMINAL_OLD_SETTINGS is not None:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, TERMINAL_OLD_SETTINGS)
            restored = True
        except Exception:
            restored = False
    try:
        show_cursor_if_possible(tank.use_color)
        clear_screen()
        print("Sell a fish")
        print("-----------")
        print("Value is based on rarity, life stage, generation, name, and age.")
        print()
        for idx, fish in enumerate(tank.fish, start=1):
            stage = fish_stage_from_data(fish)
            rarity = RARITY_LABELS.get(species_rarity(fish.get("species", "guppy")), "Common")
            value = fish_sale_value(fish)
            print(f"{idx}) {fish.get('name', 'Unnamed')} - {stage} {fish.get('species', 'fish')} ({rarity}) - ${value}")
        print()
        choice = input("Fish number to sell, or Enter to cancel: ").strip()
        if not choice:
            tank.log("Fish sale cancelled.")
            return
        try:
            index = max(0, min(len(tank.fish) - 1, int(choice) - 1))
        except ValueError:
            tank.log("Fish sale cancelled.")
            return
        fish = tank.fish[index]
        value = fish_sale_value(fish)
        confirm = input(f"Sell {fish.get('name', 'this fish')} for ${value}? Type yes to confirm: ").strip().lower()
        if confirm != "yes":
            tank.log("Fish sale cancelled.")
            return
        sold = tank.fish.pop(index)
        tank.selected_fish_index = tank.clamped_selected_index()
        tank.shells += value
        tank.log(f"{sold.get('name', 'A fish')} was sold to the aquarium shop for ${value}.")
    except Exception as exc:
        tank.log(f"Fish sale failed: {exc}")
    finally:
        if os.name != "nt" and restored:
            try:
                tty.setcbreak(sys.stdin.fileno())
            except Exception:
                pass


def release_fish_interactively(tank):
    """Backward-compatible wrapper for older naming. Fish are now sold, not released."""
    sell_fish_interactively(tank)


def remove_decoration_interactively(tank):
    """Blocking decoration removal prompt."""
    global TERMINAL_OLD_SETTINGS
    restored = False
    if os.name != "nt" and TERMINAL_OLD_SETTINGS is not None:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, TERMINAL_OLD_SETTINGS)
            restored = True
        except Exception:
            restored = False
    try:
        show_cursor_if_possible(tank.use_color)
        clear_screen()
        print("Remove a decoration")
        print("-------------------")
        for idx, decor in enumerate(tank.decorations, start=1):
            print(f"{idx}) {decor.get('name', decor.get('kind', 'decoration'))} at x={decor.get('x', '?')}")
        print()
        choice = input("Decoration number to remove, or Enter to cancel: ").strip()
        if not choice:
            tank.log("Decoration removal cancelled.")
            return
        try:
            index = max(0, min(len(tank.decorations) - 1, int(choice) - 1))
        except ValueError:
            tank.log("Decoration removal cancelled.")
            return
        decor = tank.decorations.pop(index)
        refund = max(3, int(decor_by_name(decor.get('kind', decor.get('name', 'castle'))).get('cost', 15) * 0.35))
        tank.shells += refund
        tank.log(f"Removed the {decor.get('name', 'decoration')}. Salvaged ${refund}.")
    except Exception as exc:
        tank.log(f"Decoration removal failed: {exc}")
    finally:
        if os.name != "nt" and restored:
            try:
                tty.setcbreak(sys.stdin.fileno())
            except Exception:
                pass


def name_fish_interactively(tank):
    """Blocking naming prompt. Temporarily restores normal terminal input on Unix."""
    global TERMINAL_OLD_SETTINGS
    restored = False
    if os.name != "nt" and TERMINAL_OLD_SETTINGS is not None:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, TERMINAL_OLD_SETTINGS)
            restored = True
        except Exception:
            restored = False

    try:
        show_cursor_if_possible(tank.use_color)
        clear_screen()
        print("Name a fish")
        print("-----------")
        for idx, fish in enumerate(tank.fish, start=1):
            stage = fish_stage_from_data(fish)
            rarity = RARITY_LABELS.get(species_rarity(fish.get('species', 'guppy')), 'Common')
            print(f"{idx}) {fish.get('name', 'Unnamed')} - {stage} {fish.get('species', 'fish')} [{rarity}] - {fish.get('personality', 'calm')}")
        print()
        choice = input("Fish number to name, or Enter for newest fish: ").strip()
        if choice:
            try:
                fish = tank.fish[max(0, min(len(tank.fish) - 1, int(choice) - 1))]
            except ValueError:
                tank.log("Naming cancelled.")
                return
        else:
            fish = tank.fish[-1]
        new_name = input(f"New name for {fish.get('name', 'this fish')}: ").strip()
        if not new_name:
            tank.log("Naming cancelled.")
            return
        # Keep names readable in the status/events area.
        new_name = new_name[:24]
        fish["name"] = new_name
        tank.log(f"The {fish.get('species', 'fish')} is now named {new_name}.")
    except Exception as exc:
        tank.log(f"Naming failed: {exc}")
    finally:
        if os.name != "nt" and restored:
            try:
                tty.setcbreak(sys.stdin.fileno())
            except Exception:
                pass
        hide_cursor_if_possible(tank.use_color)



# ============================================================
# v1.5 UI / progression expansion patch
# ------------------------------------------------------------
# Adds:
#   - main menu / pause-style menu
#   - proper shop menu with categories
#   - selection-list flows for naming, selling, inspecting, and decoration management
#   - save slots
#   - fish market requests with sale bonuses
#   - decoration placement/movement
#   - tank stage names and wider tanks with Roomy Tank upgrades when terminal space allows
#   - species variants and richer album stats
#   - improved screensaver follow text
# ============================================================

APP_VERSION_LABEL = "v1.5"
SAVE_SLOT_COUNT = 3

VARIANT_CATALOG = [
    {"name": "Normal", "rarity": "common", "weight": 72, "color": None, "value_bonus": 0},
    {"name": "Speckled", "rarity": "uncommon", "weight": 16, "color": "silver", "value_bonus": 4},
    {"name": "Golden", "rarity": "rare", "weight": 7, "color": "gold", "value_bonus": 12},
    {"name": "Moonlit", "rarity": "rare", "weight": 4, "color": "teal", "value_bonus": 14},
    {"name": "Ancient", "rarity": "legendary", "weight": 1, "color": "violet", "value_bonus": 28},
]
VARIANT_BY_NAME = {v["name"]: v for v in VARIANT_CATALOG}

TANK_STAGES = [
    "Starter Bowl",
    "Roomy Tank",
    "Deluxe Aquarium",
    "Grand Exhibit",
    "Public Aquarium",
]

THEMES = ["Classic", "Riverbed", "Coral Reef", "GBC Green", "Moonlit", "Deep Sea"]

_MENU_ENTER = {"\r", "\n", " ", "right"}
_MENU_UP = {"up"}
_MENU_DOWN = {"down"}
_MENU_BACK = {"\x1b", "q", "left"}

_old_make_fish_v14 = make_fish
_old_make_egg_v14 = make_egg
_old_fish_symbol_v14 = fish_symbol
_old_ui_profile_lines_v14 = ui_profile_lines
_old_ui_album_lines_v14 = ui_album_lines
_old_fish_sale_value_v14 = fish_sale_value
_old_init_v14 = Fishtank.__init__
_old_save_v14 = Fishtank.save
_old_load_v14 = Fishtank.load
_old_update_v14 = Fishtank.update
_old_handle_input_v14 = Fishtank.handle_input
_old_buy_upgrade_v14 = Fishtank.buy_upgrade
_old_update_eggs_v14 = Fishtank.update_eggs
_old_maybe_breed_fish_v14 = Fishtank.maybe_breed_fish
_old_render_v14 = render


def save_slot_file(slot):
    return SAVE_DIR / f"fishtank_save_slot_{int(slot)}.json"


def choose_variant(rare_egg=False, parents=None):
    parents = parents or []
    # Breeding has a small inheritance bias.
    inherited = [p.get("variant") for p in parents if isinstance(p, dict) and p.get("variant")]
    if inherited and random.random() < 0.42:
        return random.choice(inherited)
    weights = []
    for v in VARIANT_CATALOG:
        w = v["weight"]
        if rare_egg and v["rarity"] in ("rare", "legendary"):
            w *= 3
        weights.append(w)
    return random.choices([v["name"] for v in VARIANT_CATALOG], weights=weights, k=1)[0]


def make_fish(width, height, baby=False):
    fish = _old_make_fish_v14(width, height, baby=baby)
    fish.setdefault("variant", choose_variant())
    fish.setdefault("markings", random.choice(["plain", "soft stripes", "bright fins", "pale belly", "dark tail"]))
    return fish


def make_egg(width, height, species_name=None, rare_egg=False, tank=None):
    egg = _old_make_egg_v14(width, height, species_name=species_name, rare_egg=rare_egg, tank=tank)
    egg.setdefault("variant", choose_variant(rare_egg=rare_egg))
    return egg


def fish_symbol(f):
    symbol = _old_fish_symbol_v14(f)
    variant = f.get("variant", "Normal")
    if variant == "Speckled" and len(symbol) > 2:
        # Add a subtle speckle without expanding the sprite too much.
        chars = list(symbol)
        mid = len(chars) // 2
        if chars[mid] == " ":
            chars[mid] = "."
        elif chars[mid] not in "<>°~*{}()[]":
            chars[mid] = "."
        else:
            chars.insert(mid, ".")
        symbol = "".join(chars)
    elif variant == "Ancient" and len(symbol) > 1:
        symbol = symbol.replace(">", "»", 1) if f.get("dir", 1) == 1 else symbol.replace("<", "«", 1)
    return symbol


def tank_stage_name(tank):
    level = max(0, min(len(TANK_STAGES)-1, upgrade_level(tank, "tank")))
    return TANK_STAGES[level]


def get_terminal_size_for_tank(tank=None):
    size = shutil.get_terminal_size((DEFAULT_WIDTH, DEFAULT_HEIGHT))
    level = upgrade_level(tank, "tank") if tank is not None else 0
    desired_width = min(DEFAULT_WIDTH + level * 8, 112)
    desired_height = min(DEFAULT_HEIGHT + level, 32)
    width = min(desired_width, max(24, size.columns - 2))
    height = min(desired_height, max(14, size.lines - 7))
    return max(24, width), max(14, height)


def ensure_v15_state(tank):
    if not hasattr(tank, "mode"):
        tank.mode = "main_menu"
    tank.menu_cursor = int(getattr(tank, "menu_cursor", 0))
    tank.shop_cursor = int(getattr(tank, "shop_cursor", 0))
    tank.fish_cursor = int(getattr(tank, "fish_cursor", 0))
    tank.decor_cursor = int(getattr(tank, "decor_cursor", 0))
    tank.slot_cursor = int(getattr(tank, "slot_cursor", 0))
    tank.theme_index = int(getattr(tank, "theme_index", 0)) % len(THEMES)
    tank.show_shop_menu = bool(getattr(tank, "show_shop_menu", False))
    tank.market_requests = getattr(tank, "market_requests", []) or []
    tank.market_day = int(getattr(tank, "market_day", 0))
    tank.discovered_variants = getattr(tank, "discovered_variants", {}) or {}
    tank.album_stats = getattr(tank, "album_stats", {}) or {}
    tank.settings_cursor = int(getattr(tank, "settings_cursor", 0))
    tank.last_screensaver_note = getattr(tank, "last_screensaver_note", "")
    for fish in getattr(tank, "fish", []):
        fish.setdefault("variant", "Normal")
        fish.setdefault("markings", "plain")
    for egg in getattr(tank, "eggs", []):
        egg.setdefault("variant", choose_variant(rare_egg=egg.get("rare_egg", False)))
    if not tank.market_requests:
        refresh_market_requests(tank, quiet=True)


def tank_to_data(tank, version=15):
    ensure_v15_state(tank)
    return {
        "version": version,
        "fish": tank.fish,
        "eggs": getattr(tank, "eggs", []),
        "plants": tank.plants,
        "rocks": tank.rocks,
        "snails": tank.snails,
        "decorations": tank.decorations,
        "shells": tank.shells,
        "day": tank.day,
        "tick": tank.tick,
        "use_color": tank.use_color,
        "old_age_mortality": tank.old_age_mortality,
        "discovered_species": getattr(tank, "discovered_species", []),
        "discovered_variants": getattr(tank, "discovered_variants", {}),
        "album_stats": getattr(tank, "album_stats", {}),
        "hatch_count": getattr(tank, "hatch_count", 0),
        "rare_egg_stock": getattr(tank, "rare_egg_stock", 0),
        "selected_fish_index": getattr(tank, "selected_fish_index", 0),
        "water_quality": getattr(tank, "water_quality", 82),
        "selected_food_index": getattr(tank, "selected_food_index", 0),
        "aquarium_journal": getattr(tank, "aquarium_journal", []),
        "upgrades": getattr(tank, "upgrades", {"tank": 0, "filter": 0, "bubbler": 0, "nursery": 0, "feeder": 0}),
        "theme_index": getattr(tank, "theme_index", 0),
        "market_requests": getattr(tank, "market_requests", []),
        "market_day": getattr(tank, "market_day", 0),
    }


def apply_tank_data(tank, data):
    tank.fish = data.get("fish", tank.fish)
    tank.eggs = data.get("eggs", getattr(tank, "eggs", []))
    tank.plants = data.get("plants", tank.plants)
    tank.rocks = data.get("rocks", tank.rocks)
    tank.snails = data.get("snails", tank.snails)
    tank.decorations = data.get("decorations", tank.decorations)
    tank.shells = data.get("shells", tank.shells)
    tank.day = data.get("day", tank.day)
    tank.tick = data.get("tick", tank.tick)
    tank.use_color = bool(data.get("use_color", tank.use_color)) and terminal_supports_ansi()
    tank.old_age_mortality = data.get("old_age_mortality", tank.old_age_mortality)
    tank.discovered_species = data.get("discovered_species", getattr(tank, "discovered_species", []))
    tank.discovered_variants = data.get("discovered_variants", getattr(tank, "discovered_variants", {}))
    tank.album_stats = data.get("album_stats", getattr(tank, "album_stats", {}))
    tank.hatch_count = data.get("hatch_count", getattr(tank, "hatch_count", 0))
    tank.rare_egg_stock = data.get("rare_egg_stock", getattr(tank, "rare_egg_stock", 0))
    tank.selected_fish_index = int(data.get("selected_fish_index", getattr(tank, "selected_fish_index", 0)))
    tank.water_quality = int(data.get("water_quality", getattr(tank, "water_quality", 82)))
    tank.selected_food_index = int(data.get("selected_food_index", getattr(tank, "selected_food_index", 0))) % len(FOOD_TYPES)
    tank.aquarium_journal = data.get("aquarium_journal", getattr(tank, "aquarium_journal", []))
    tank.upgrades = data.get("upgrades", getattr(tank, "upgrades", {"tank": 0, "filter": 0, "bubbler": 0, "nursery": 0, "feeder": 0}))
    for _u in UPGRADE_CATALOG:
        tank.upgrades.setdefault(_u, 0)
    tank.theme_index = int(data.get("theme_index", getattr(tank, "theme_index", 0))) % len(THEMES)
    tank.market_requests = data.get("market_requests", getattr(tank, "market_requests", []))
    tank.market_day = int(data.get("market_day", getattr(tank, "market_day", 0)))
    tank.show_tank_journal = False
    tank.show_profile = False
    tank.show_journal = False
    tank.show_help = False
    tank.mode = "tank"
    for fish in tank.fish:
        tank.ensure_fish_age_fields(fish)
        fish.setdefault("variant", "Normal")
        tank.discover_species(fish.get("species", "guppy"), silent=True)
        discover_variant(tank, fish.get("species", "guppy"), fish.get("variant", "Normal"), silent=True)
    for egg in getattr(tank, "eggs", []):
        egg.setdefault("variant", choose_variant(rare_egg=egg.get("rare_egg", False)))
    tank.food = []
    tank.bubbles = [make_bubble(tank.width, tank.height) for _ in range(16)]
    tank.visitors = []
    if not tank.fish and not tank.eggs:
        tank.eggs = [make_egg(tank.width, tank.height)]
    ensure_v15_state(tank)


def slot_summary(slot):
    path = save_slot_file(slot)
    if not path.exists():
        return f"Slot {slot}: Empty"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return f"Slot {slot}: Day {data.get('day', '?')} | {len(data.get('fish', []))} fish | {len(data.get('eggs', []))} eggs | {data.get('shells', 0)}"
    except Exception:
        return f"Slot {slot}: Unreadable save"


def save_to_slot(tank, slot):
    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        save_slot_file(slot).write_text(json.dumps(tank_to_data(tank), indent=2), encoding="utf-8")
        tank.log(f"Saved tank to slot {slot}.")
    except Exception as exc:
        tank.log(f"Slot save failed: {exc}")


def load_from_slot(tank, slot):
    path = save_slot_file(slot)
    if not path.exists():
        tank.log(f"Slot {slot} is empty.")
        return
    try:
        apply_tank_data(tank, json.loads(path.read_text(encoding="utf-8")))
        tank.log(f"Loaded tank from slot {slot}.")
    except Exception as exc:
        tank.log(f"Slot load failed: {exc}")


def discover_variant(tank, species, variant, silent=False):
    ensure_v15_state(tank)
    species = species or "guppy"
    variant = variant or "Normal"
    tank.discovered_variants.setdefault(species, [])
    if variant not in tank.discovered_variants[species]:
        tank.discovered_variants[species].append(variant)
        tank.discovered_variants[species].sort(key=lambda v: [x["name"] for x in VARIANT_CATALOG].index(v) if v in VARIANT_BY_NAME else 999)
        if not silent and variant != "Normal":
            tank.log(f"Variant discovered: {variant} {species}!")


def record_hatch_stats(tank, fish):
    ensure_v15_state(tank)
    species = fish.get("species", "guppy")
    stats = tank.album_stats.setdefault(species, {"hatched": 0, "first_day": tank.day, "max_generation": 1})
    stats["hatched"] = stats.get("hatched", 0) + 1
    stats["first_day"] = min(stats.get("first_day", tank.day), tank.day)
    stats["max_generation"] = max(stats.get("max_generation", 1), int(fish.get("generation", 1)))


def refresh_market_requests(tank, quiet=False):
    # Do not call ensure_v15_state here; ensure_v15_state may call this function.
    if not hasattr(tank, "market_requests"):
        tank.market_requests = []
    if not hasattr(tank, "market_day"):
        tank.market_day = 0
    requests = []
    # Keep requests readable and achievable.
    species_pool = [s["name"] for s in FISH_SPECIES if s.get("rarity", "common") in ("common", "uncommon", "rare")]
    requests.append({"type": "stage", "stage": random.choice(["adult", "elder"]), "bonus": random.randint(8, 18)})
    requests.append({"type": "rarity", "rarity": random.choice(["uncommon", "rare", "legendary"]), "bonus": random.randint(12, 35)})
    requests.append({"type": "species", "species": random.choice(species_pool), "bonus": random.randint(10, 24)})
    if random.random() < 0.55:
        requests.append({"type": "variant", "variant": random.choice(["Speckled", "Golden", "Moonlit", "Ancient"]), "bonus": random.randint(12, 40)})
    else:
        requests.append({"type": "generation", "generation": random.choice([2, 3]), "bonus": random.randint(14, 30)})
    tank.market_requests = requests
    tank.market_day = tank.day
    if not quiet:
        tank.log("The fish market posts new requests.")


def market_request_label(req):
    t = req.get("type")
    bonus = req.get("bonus", 0)
    if t == "stage":
        return f"Wanted: {req.get('stage', 'adult')} fish (+{bonus})"
    if t == "rarity":
        return f"Wanted: {req.get('rarity', 'rare')} fish (+{bonus})"
    if t == "species":
        return f"Wanted: {req.get('species', 'guppy')} (+{bonus})"
    if t == "variant":
        return f"Wanted: {req.get('variant', 'Golden')} variant (+{bonus})"
    if t == "generation":
        return f"Wanted: Gen {req.get('generation', 2)}+ fish (+{bonus})"
    return f"Wanted fish (+{bonus})"


def market_bonus_for_fish(tank, fish):
    ensure_v15_state(tank)
    bonus = 0
    for req in tank.market_requests:
        t = req.get("type")
        if t == "stage" and fish_stage_from_data(fish) == req.get("stage"):
            bonus += req.get("bonus", 0)
        elif t == "rarity" and species_rarity(fish.get("species", "guppy")) == req.get("rarity"):
            bonus += req.get("bonus", 0)
        elif t == "species" and fish.get("species") == req.get("species"):
            bonus += req.get("bonus", 0)
        elif t == "variant" and fish.get("variant", "Normal") == req.get("variant"):
            bonus += req.get("bonus", 0)
        elif t == "generation" and int(fish.get("generation", 1)) >= int(req.get("generation", 2)):
            bonus += req.get("bonus", 0)
    return bonus


def fish_sale_value(fish):
    base = _old_fish_sale_value_v14(fish)
    variant = VARIANT_BY_NAME.get(fish.get("variant", "Normal"), VARIANT_BY_NAME["Normal"])
    # Current tank market bonus is added by selection UI; the plain value remains tank-independent.
    return base + int(variant.get("value_bonus", 0))


def fish_sale_value_for_tank(tank, fish):
    return fish_sale_value(fish) + market_bonus_for_fish(tank, fish)


def fish_display_name(fish):
    variant = fish.get("variant", "Normal")
    species = fish.get("species", "fish")
    return species if variant == "Normal" else f"{variant} {species}"


def modal_move_cursor(tank, key, attr, count):
    if count <= 0:
        setattr(tank, attr, 0)
        return
    cur = int(getattr(tank, attr, 0))
    if key in _MENU_UP:
        cur = (cur - 1) % count
    elif key in _MENU_DOWN:
        cur = (cur + 1) % count
    setattr(tank, attr, cur)


def buy_shop_item(tank, index):
    items = shop_items(tank)
    if not items:
        return
    index = max(0, min(len(items)-1, index))
    item = items[index]
    item["action"]()


def shop_items(tank):
    return [
        {"label": "Eggs / Mystery Egg - $12", "action": tank.buy_fish},
        {"label": "Eggs / Rare Egg - $30", "action": tank.buy_rare_egg},
        {"label": "Decor / Plant - $8", "action": tank.buy_plant},
        {"label": "Decor / Decoration - $15", "action": tank.buy_decoration},
        {"label": "Decor / Snail - $10", "action": tank.buy_snail},
        {"label": f"Upgrade / Roomy Tank - {next_upgrade_cost(tank, 'tank') or 'MAX'}", "action": lambda: tank.buy_upgrade('tank')},
        {"label": f"Upgrade / Better Filter - {next_upgrade_cost(tank, 'filter') or 'MAX'}", "action": lambda: tank.buy_upgrade('filter')},
        {"label": f"Upgrade / Bubble Stone - {next_upgrade_cost(tank, 'bubbler') or 'MAX'}", "action": lambda: tank.buy_upgrade('bubbler')},
        {"label": f"Upgrade / Nursery Moss - {next_upgrade_cost(tank, 'nursery') or 'MAX'}", "action": lambda: tank.buy_upgrade('nursery')},
        {"label": f"Upgrade / Auto-Feeder - {next_upgrade_cost(tank, 'feeder') or 'MAX'}", "action": lambda: tank.buy_upgrade('feeder')},
        {"label": "Market / Refresh requests - $6", "action": lambda: (tank.spend(6) and refresh_market_requests(tank))},
    ]


def handle_v15_modal_input(tank, key):
    ensure_v15_state(tank)
    mode = tank.mode

    if mode == "main_menu":
        items = ["Continue Tank", "New One-Egg Tank", "Shop", "Species Album", "Save Slots", "Settings", "Quit"]
        modal_move_cursor(tank, key, "menu_cursor", len(items))
        if key in {"1", "2", "3", "4", "5", "6", "7"}:
            tank.menu_cursor = int(key) - 1
            key = "\r"
        if key in _MENU_ENTER:
            choice = tank.menu_cursor
            if choice == 0:
                tank.mode = "tank"
            elif choice == 1:
                tank.reset_to_egg(); tank.mode = "tank"
            elif choice == 2:
                tank.mode = "shop_menu"
            elif choice == 3:
                tank.show_journal = True; tank.show_help = tank.show_profile = False; tank.mode = "tank"
            elif choice == 4:
                tank.mode = "save_slots"
            elif choice == 5:
                tank.mode = "settings"
            elif choice == 6:
                if tank.autosave: tank.save()
                tank.running = False
        return

    if mode == "shop_menu":
        items = shop_items(tank)
        modal_move_cursor(tank, key, "shop_cursor", len(items))
        if key in {str(i) for i in range(10)}:
            # 1-9 select visible menu items, 0 selects tenth.
            n = 9 if key == "0" else int(key) - 1
            if 0 <= n < len(items):
                tank.shop_cursor = n
                buy_shop_item(tank, tank.shop_cursor)
        elif key in _MENU_ENTER:
            buy_shop_item(tank, tank.shop_cursor)
        elif key in _MENU_BACK or key == "o":
            tank.mode = "tank"
        return

    if mode in ("fish_select_name", "fish_select_sell", "fish_select_inspect"):
        if not tank.fish:
            tank.log("There are no hatched fish yet.")
            tank.mode = "tank"
            return
        modal_move_cursor(tank, key, "fish_cursor", len(tank.fish))
        if key in _MENU_BACK:
            tank.mode = "tank"
        elif key in _MENU_ENTER:
            idx = max(0, min(len(tank.fish)-1, tank.fish_cursor))
            tank.selected_fish_index = idx
            if mode == "fish_select_inspect":
                tank.show_profile = True; tank.show_help = tank.show_journal = False; tank.mode = "tank"
            elif mode == "fish_select_sell":
                tank.mode = "fish_confirm_sell"
            else:
                # Use a name prompt only after choosing via the in-app list.
                tank.mode = "tank"
                name_selected_fish_prompt(tank, idx)
        return

    if mode == "fish_confirm_sell":
        if key in _MENU_BACK:
            tank.mode = "fish_select_sell"
        elif key in _MENU_ENTER or key == "y":
            if tank.fish:
                idx = max(0, min(len(tank.fish)-1, tank.fish_cursor))
                fish = tank.fish.pop(idx)
                value = fish_sale_value_for_tank(tank, fish)
                tank.shells += value
                tank.log(f"Sold {fish.get('name', 'a fish')} ({fish_display_name(fish)}) for ${value}.")
                tank.selected_fish_index = tank.clamped_selected_index()
            tank.mode = "tank"
        return

    if mode == "decor_select":
        if not tank.decorations:
            tank.log("There are no decorations to manage.")
            tank.mode = "tank"
            return
        modal_move_cursor(tank, key, "decor_cursor", len(tank.decorations))
        idx = max(0, min(len(tank.decorations)-1, tank.decor_cursor))
        decor = tank.decorations[idx]
        if key in _MENU_BACK:
            tank.mode = "tank"
        elif key == "a":
            decor["x"] = max(2, int(decor.get("x", 3)) - 2); tank.log(f"Moved {decor.get('name','decoration')} left.")
        elif key == "d":
            decor["x"] = min(tank.width - 6, int(decor.get("x", 3)) + 2); tank.log(f"Moved {decor.get('name','decoration')} right.")
        elif key in _MENU_ENTER or key == "x":
            removed = tank.decorations.pop(idx)
            refund = max(3, int(decor_by_name(removed.get('kind', removed.get('name', 'castle'))).get('cost', 15) * 0.35))
            tank.shells += refund
            tank.log(f"Sold the {removed.get('name', 'decoration')} for ${refund}.")
            tank.decor_cursor = max(0, min(tank.decor_cursor, len(tank.decorations)-1))
            if not tank.decorations:
                tank.mode = "tank"
        return

    if mode == "save_slots":
        modal_move_cursor(tank, key, "slot_cursor", SAVE_SLOT_COUNT)
        if key in {"1", "2", "3"}:
            tank.slot_cursor = int(key) - 1
        if key in _MENU_BACK:
            tank.mode = "tank"
        elif key == "s":
            save_to_slot(tank, tank.slot_cursor + 1)
        elif key == "l" or key in _MENU_ENTER:
            load_from_slot(tank, tank.slot_cursor + 1)
        return

    if mode == "settings":
        items = ["Toggle Color", "Toggle Screensaver", "Toggle Old-Age Mortality", "Toggle Autosave", "Cycle Theme", "Back"]
        modal_move_cursor(tank, key, "settings_cursor", len(items))
        if key in _MENU_BACK:
            tank.mode = "tank"
        elif key in _MENU_ENTER:
            c = tank.settings_cursor
            if c == 0:
                tank.use_color = not tank.use_color; tank.log("Color enabled." if tank.use_color else "Color disabled.")
            elif c == 1:
                tank.screensaver = not tank.screensaver; tank.log("Screensaver enabled." if tank.screensaver else "Screensaver disabled.")
            elif c == 2:
                tank.old_age_mortality = not tank.old_age_mortality; tank.log("Old-age mortality enabled." if tank.old_age_mortality else "Old-age mortality disabled.")
            elif c == 3:
                tank.autosave = not tank.autosave; tank.log("Autosave enabled." if tank.autosave else "Autosave disabled.")
            elif c == 4:
                tank.theme_index = (tank.theme_index + 1) % len(THEMES); tank.log(f"Theme set to {THEMES[tank.theme_index]}.")
            else:
                tank.mode = "tank"
        return

    tank.mode = "tank"


def name_selected_fish_prompt(tank, index):
    # Still uses a normal text entry prompt, but selection happens in the app UI.
    global TERMINAL_OLD_SETTINGS
    restored = False
    if os.name != "nt" and TERMINAL_OLD_SETTINGS is not None:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, TERMINAL_OLD_SETTINGS)
            restored = True
        except Exception:
            pass
    try:
        show_cursor_if_possible(tank.use_color)
        clear_screen()
        fish = tank.fish[index]
        print(f"Name fish: {fish.get('name', 'Unnamed')} the {fish_display_name(fish)}")
        new_name = input("New name, or Enter to cancel: ").strip()[:24]
        if new_name:
            fish["name"] = new_name
            tank.log(f"The {fish_display_name(fish)} is now named {new_name}.")
        else:
            tank.log("Naming cancelled.")
    except Exception as exc:
        tank.log(f"Naming failed: {exc}")
    finally:
        if os.name != "nt" and restored:
            try:
                tty.setcbreak(sys.stdin.fileno())
            except Exception:
                pass
        hide_cursor_if_possible(tank.use_color)


def v15_init(self):
    _old_init_v14(self)
    self.width, self.height = get_terminal_size_for_tank(self)
    self.mode = "main_menu"
    self.menu_cursor = self.shop_cursor = self.fish_cursor = self.decor_cursor = self.slot_cursor = 0
    self.theme_index = 0
    self.market_requests = []
    self.market_day = 0
    self.discovered_variants = {}
    self.album_stats = {}
    self.settings_cursor = 0
    ensure_v15_state(self)


def v15_save(self):
    data = tank_to_data(self)
    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        SAVE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.saved_notice = 35
        self.log(f"The tank is saved to {SAVE_FILE}.")
    except Exception as exc:
        try:
            fallback = Path.home() / SAVE_FILENAME
            fallback.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.saved_notice = 35
            self.log(f"The tank is saved to {fallback}.")
        except Exception:
            self.log(f"Save failed: {exc}")


def v15_load(self):
    load_path = SAVE_FILE
    if not load_path.exists() and LEGACY_SAVE_FILE.exists() and LEGACY_SAVE_FILE.is_file():
        load_path = LEGACY_SAVE_FILE
    if not load_path.exists():
        self.log("No save file exists yet.")
        return
    try:
        apply_tank_data(self, json.loads(load_path.read_text(encoding="utf-8")))
        self.width, self.height = get_terminal_size_for_tank(self)
        self.clamp_world()
        self.log("The saved tank bubbles back to life.")
    except Exception as exc:
        self.log(f"Load failed: {exc}")


def v15_update(self):
    ensure_v15_state(self)
    prev_day = getattr(self, "day", 1)
    if getattr(self, "mode", "tank") == "main_menu":
        # Let the background shimmer but do not age fish while parked on title screen.
        if not self.paused:
            self.tick += 1
            self.update_bubbles()
            self.update_visitors()
        return
    _old_update_v14(self)
    if self.day != prev_day:
        if self.day - getattr(self, "market_day", 0) >= 3:
            refresh_market_requests(self)
    if self.screensaver and self.fish and self.tick % 220 == 0:
        fish = random.choice(self.fish)
        self.last_screensaver_note = f"{fish.get('name', 'A fish')} drifts through the {THEMES[getattr(self, 'theme_index', 0)]} water..."


def v15_buy_upgrade(self, name):
    before = upgrade_level(self, name)
    _old_buy_upgrade_v14(self, name)
    after = upgrade_level(self, name)
    if name == "tank" and after > before:
        self.width, self.height = get_terminal_size_for_tank(self)
        self.clamp_world()
        self.log(f"The aquarium is now a {tank_stage_name(self)}.")


def v15_handle_input(self):
    ensure_v15_state(self)
    key = get_key()
    if not key:
        return
    if getattr(self, "mode", "tank") != "tank":
        handle_v15_modal_input(self, key)
        return
    # New menu keys in normal tank mode.
    if key == "o" or key == "h":
        self.mode = "shop_menu"
        self.show_help = self.show_journal = self.show_profile = False
        return
    if key == "e":
        self.mode = "save_slots"
        return
    if key == "t":
        self.mode = "settings"
        return
    if key == "\x1b":
        self.mode = "main_menu"
        return
    if key == "n":
        self.mode = "fish_select_name"; self.fish_cursor = self.clamped_selected_index(); return
    if key == "x":
        self.mode = "fish_select_sell"; self.fish_cursor = self.clamped_selected_index(); return
    if key == "i":
        self.mode = "fish_select_inspect"; self.fish_cursor = self.clamped_selected_index(); return
    if key == "d":
        self.mode = "decor_select"; return
    _old_handle_input_v14(self)


def v15_update_eggs(self):
    if not hasattr(self, "eggs"):
        self.eggs = []
    hatched = []
    for egg in list(self.eggs):
        egg.setdefault("variant", choose_variant(rare_egg=egg.get("rare_egg", False)))
        egg["age"] = egg.get("age", 0) + 1
        egg["y"] = self.height - 3
        if random.random() < 0.015:
            egg["x"] += random.choice([-1, 0, 1])
            egg["x"] = max(2, min(self.width - 5, int(egg.get("x", 3))))
        if egg["age"] >= egg.get("hatch_time", EGG_HATCH_MAX):
            baby = make_fish(self.width, self.height, baby=True)
            baby["species"] = egg.get("species", baby["species"])
            baby["variant"] = egg.get("variant", choose_variant(rare_egg=egg.get("rare_egg", False)))
            baby["x"] = max(2, min(self.width - len(fish_symbol(baby)) - 2, int(egg.get("x", 3))))
            baby["y"] = max(2, min(self.height - 4, self.height - 4))
            baby["name"] = f"Unnamed {fish_display_name(baby)}"
            baby["parents"] = list(egg.get("parents", []))
            baby["parent_names"] = list(egg.get("parent_names", []))
            baby["generation"] = int(egg.get("generation", 1))
            baby["hatched_day"] = self.day
            baby["last_stage"] = "fry"
            self.fish.append(baby)
            for parent in self.fish:
                if parent.get("id") in baby["parents"]:
                    parent.setdefault("children", [])
                    if baby["name"] not in parent["children"]:
                        parent["children"].append(baby["name"])
            self.selected_fish_index = len(self.fish) - 1
            hatched.append(egg)
            self.hatch_count = getattr(self, "hatch_count", 0) + 1
            self.discover_species(baby["species"])
            discover_variant(self, baby["species"], baby.get("variant", "Normal"))
            record_hatch_stats(self, baby)
            rarity = RARITY_LABELS.get(species_rarity(baby["species"]), "Common")
            variant_text = "" if baby.get("variant") == "Normal" else f" {baby.get('variant')}"
            lineage = f" Parents: {' + '.join(baby['parent_names'])}." if baby.get("parent_names") else ""
            self.log(f"An egg hatches into a tiny{variant_text} {baby['species']}! ({rarity}) Press N to name it.{lineage}")
    for egg in hatched:
        if egg in self.eggs:
            self.eggs.remove(egg)


def v15_maybe_breed_fish(self):
    if len(self.fish) + len(getattr(self, "eggs", [])) >= self.fish_capacity():
        return
    if len(self.fish) < 2 or self.tick < 1000:
        return
    base_chance = 0.0009
    if getattr(self, "water_quality", 70) >= 88:
        base_chance *= 1.35
    base_chance *= 1.0 + upgrade_level(self, "nursery") * 0.18
    if any(food.get("kind") == "golden" for food in self.food):
        base_chance *= 1.18
    if random.random() > base_chance:
        return
    happy_fish = [f for f in self.fish if f.get("hunger", 100) < 35 and self.age_stage(f) == "adult"]
    if len(happy_fish) >= 2:
        parent_a, parent_b = random.sample(happy_fish, 2)
        chosen_species = random.choice([parent_a.get("species"), parent_b.get("species")])
        egg = make_egg(self.width, self.height, chosen_species, tank=self)
        egg["variant"] = choose_variant(parents=[parent_a, parent_b])
        egg["x"] = int((parent_a.get("x", egg["x"]) + parent_b.get("x", egg["x"])) / 2)
        egg["y"] = self.height - 3
        egg["parents"] = [parent_a.get("id"), parent_b.get("id")]
        egg["parent_names"] = [parent_a.get("name", "Unknown"), parent_b.get("name", "Unknown")]
        egg["generation"] = max(int(parent_a.get("generation", 1)), int(parent_b.get("generation", 1))) + 1
        self.eggs.append(egg)
        var = "" if egg.get("variant") == "Normal" else f" {egg.get('variant')}"
        self.log(f"A small{var} {egg['species']} egg appears among the plants. Parents: {parent_a.get('name')} + {parent_b.get('name')}.")


def ui_profile_lines(tank):
    lines = _old_ui_profile_lines_v14(tank)
    if tank.fish:
        fish = tank.fish[tank.clamped_selected_index()]
        variant = fish.get("variant", "Normal")
        lines.insert(2, f"Variant: {variant} | Markings: {fish.get('markings', 'plain')} | Market value now: ${fish_sale_value_for_tank(tank, fish)}")
    return lines


def ui_album_lines(tank):
    ensure_v15_state(tank)
    lines = [
        f"Discovered {len(getattr(tank, 'discovered_species', []))}/{len(FISH_SPECIES)} species | Hatch count: {getattr(tank, 'hatch_count', 0)} | Theme: {THEMES[getattr(tank, 'theme_index', 0)]}",
        "Album now tracks variants, first hatch day, total hatches, and highest generation.",
        "",
    ]
    discovered = set(getattr(tank, "discovered_species", []))
    for species in sorted(FISH_SPECIES, key=lambda s: (RARITY_ORDER.index(s.get("rarity", "common")), s["name"])):
        name = species["name"]
        rarity = RARITY_LABELS.get(species.get("rarity", "common"), "Common")
        if name in discovered:
            variants = tank.discovered_variants.get(name, ["Normal"])
            stats = tank.album_stats.get(name, {})
            lines.append(f"{name} [{rarity}] | variants {len(variants)}/{len(VARIANT_CATALOG)}: {', '.join(variants)}")
            if stats:
                lines.append(f"  hatched {stats.get('hatched', 0)} | first Day {stats.get('first_day', '?')} | max Gen {stats.get('max_generation', 1)}")
        else:
            lines.append(f"???? [{rarity}] | undiscovered")
    return lines


def modal_lines(tank):
    ensure_v15_state(tank)
    mode = getattr(tank, "mode", "tank")
    if mode == "main_menu":
        items = ["Continue Tank", "New One-Egg Tank", "Shop", "Species Album", "Save Slots", "Settings", "Quit"]
        return "ASCII FISHTANK", [
            f"{'> ' if i == tank.menu_cursor else '  '}{i+1}. {item}" for i, item in enumerate(items)
        ] + ["", "Use ↑/↓ to move, Enter/Space/→ to choose. Esc/Q/← goes back. Number keys still work as shortcuts."]
    if mode == "shop_menu":
        items = shop_items(tank)
        lines = [f"${tank.shells} | Tank: {tank_stage_name(tank)} | Capacity: {len(tank.fish)+len(getattr(tank,'eggs',[]))}/{tank.fish_capacity()}", ""]
        for i, item in enumerate(items):
            key = "0" if i == 9 else str(i+1) if i < 9 else " "
            lines.append(f"{'> ' if i == tank.shop_cursor else '  '}{key}. {item['label']}")
        lines += ["", "Market requests:"] + ["  " + market_request_label(r) for r in tank.market_requests] + ["", "Enter/Space/→ buys selected. Esc/Q/←/O returns."]
        return "Shop", lines
    if mode in ("fish_select_name", "fish_select_sell", "fish_select_inspect"):
        action = {"fish_select_name": "Name / Rename Fish", "fish_select_sell": "Sell Fish", "fish_select_inspect": "Inspect Fish"}[mode]
        lines = []
        if not tank.fish:
            lines = ["No fish have hatched yet."]
        else:
            for i, fish in enumerate(tank.fish):
                value = fish_sale_value_for_tank(tank, fish)
                lines.append(f"{'> ' if i == tank.fish_cursor else '  '}{fish.get('name','Unnamed')[:18]:18} | {fish_stage_from_data(fish):5} | {fish_display_name(fish):24} | Gen {fish.get('generation',1)} | {value}")
        lines += ["", "Use ↑/↓ to move. Enter/Space/→ chooses. Esc/Q/← cancels."]
        return action, lines
    if mode == "fish_confirm_sell":
        fish = tank.fish[max(0, min(len(tank.fish)-1, tank.fish_cursor))] if tank.fish else None
        if not fish:
            return "Sell Fish", ["No fish selected."]
        return "Confirm Sale", [
            f"Sell {fish.get('name','Unnamed')} the {fish_display_name(fish)}?",
            f"Base + variant + market value: {fish_sale_value_for_tank(tank, fish)}",
            "Press Enter or Y to sell. Q/Esc to cancel.",
        ]
    if mode == "decor_select":
        lines = []
        if not tank.decorations:
            lines.append("No decorations in the tank.")
        else:
            for i, decor in enumerate(tank.decorations):
                lines.append(f"{'> ' if i == tank.decor_cursor else '  '}{decor.get('name', decor.get('kind','decoration')):20} x={decor.get('x','?')} | A/D move | X/Enter sell")
        lines.append("Q/Esc returns.")
        return "Decorations", lines
    if mode == "save_slots":
        lines = [f"{'> ' if i == tank.slot_cursor else '  '}{slot_summary(i+1)}" for i in range(SAVE_SLOT_COUNT)]
        lines += ["", "Use ↑/↓ to move. S saves to selected slot. L or Enter loads selected slot. Esc/Q/← returns."]
        return "Save Slots", lines
    if mode == "settings":
        values = [
            f"Color: {'On' if tank.use_color else 'Off'}",
            f"Screensaver: {'On' if tank.screensaver else 'Off'}",
            f"Old-age mortality: {'On' if tank.old_age_mortality else 'Off'}",
            f"Autosave: {'On' if tank.autosave else 'Off'}",
            f"Theme: {THEMES[tank.theme_index]}",
            "Back",
        ]
        return "Settings", [f"{'> ' if i == tank.settings_cursor else '  '}{v}" for i, v in enumerate(values)] + ["", "Enter/Space/→ changes selected setting. Esc/Q/← returns."]
    return "", []


def render(tank):
    ensure_v15_state(tank)
    # Let v14 draw the stable aquarium UI first.
    _old_render_v14(tank)
    width = getattr(tank, "width", DEFAULT_WIDTH)
    if tank.screensaver and getattr(tank, "last_screensaver_note", "") and getattr(tank, "mode", "tank") == "tank":
        ui_box("", [tank.last_screensaver_note], width, tank.use_color, "dim")
    if getattr(tank, "mode", "tank") != "tank":
        title, lines = modal_lines(tank)
        print()
        ui_box(title, lines, width, tank.use_color, "text")
    # A tiny v15 status strip beneath normal status.
    if getattr(tank, "mode", "tank") == "tank" and not tank.screensaver:
        print(color_text(f" {APP_VERSION_LABEL} | O shop | E save slots | T settings | Esc menu | Tank: {tank_stage_name(tank)} | Theme: {THEMES[getattr(tank, 'theme_index', 0)]}"[:visible_text_width(width)], "dim", tank.use_color))


Fishtank.__init__ = v15_init
Fishtank.save = v15_save
Fishtank.load = v15_load
Fishtank.update = v15_update
Fishtank.handle_input = v15_handle_input
Fishtank.buy_upgrade = v15_buy_upgrade
Fishtank.update_eggs = v15_update_eggs
Fishtank.maybe_breed_fish = v15_maybe_breed_fish


# ----------------------------
# Main
# ----------------------------

def main():
    global TERMINAL_OLD_SETTINGS
    tank = Fishtank()
    old_settings = None

    # Auto-load if a save exists in the new location or the old v0.5 location.
    if SAVE_FILE.exists() or (LEGACY_SAVE_FILE.exists() and LEGACY_SAVE_FILE.is_file()):
        tank.load()
        # v1.5 opens on the main menu even after auto-loading a save.
        tank.mode = "main_menu"

    interactive_stdin = bool(getattr(sys.stdin, "isatty", lambda: False)())

    if os.name != "nt" and interactive_stdin:
        try:
            old_settings = termios.tcgetattr(sys.stdin)
            TERMINAL_OLD_SETTINGS = old_settings
            tty.setcbreak(sys.stdin.fileno())
        except termios.error:
            old_settings = None

    try:
        clear_screen()
        hide_cursor_if_possible(tank.use_color)
        while tank.running:
            tank.handle_input()
            tank.update()
            render(tank)
            time.sleep(FPS_DELAY)
    except KeyboardInterrupt:
        if tank.autosave:
            tank.save()
    finally:
        if os.name != "nt" and old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        show_cursor_if_possible(True)
        clear_screen()
        print("The fishtank goes quiet.")
        print(f"Saved to: {SAVE_FILE.resolve()}")



# ============================================================
# v1.6 UI/layout hotfix
# ------------------------------------------------------------
# - Tank opens directly again; Esc opens the main menu.
# - H is help again; O is shop.
# - Most core hotkeys work from tank view without being swallowed by menus.
# - Wide terminals use a right-side dashboard so events/status/help do not force
#   the user to scroll downward.
# ============================================================

import re as _ansi_re_module

APP_VERSION_LABEL = "v1.8"
_ANSI_RE = _ansi_re_module.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def strip_ansi(text):
    return _ANSI_RE.sub("", str(text))


def visible_len(text):
    return len(strip_ansi(text))


def pad_visible(text, width):
    text = str(text)
    plain_len = visible_len(text)
    if plain_len >= width:
        # Avoid chopping ANSI strings. Most tank lines are exactly width already.
        return text
    return text + " " * (width - plain_len)


def fit_plain(text, width):
    text = strip_ansi(str(text))
    if width <= 0:
        return ""
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def wrapped_plain_lines(lines, inner, max_lines=None):
    out = []
    for raw in lines:
        raw = strip_ansi(str(raw))
        if raw == "":
            out.append("")
        else:
            out.extend(textwrap.wrap(raw, width=max(8, inner), break_long_words=False, break_on_hyphens=False) or [""])
        if max_lines is not None and len(out) >= max_lines:
            return out[:max_lines]
    return out


def box_lines(title, lines, width, enabled=True, color="text", max_height=None):
    width = max(24, int(width))
    inner = max(8, width - 4)
    title = fit_plain(f" {title.strip()} " if title else "", width - 2)
    top = "+" + title + ("-" * max(0, width - 2 - len(title))) + "+"
    result = [color_text(top[:width], "border", enabled)]
    content_limit = None if max_height is None else max(0, max_height - 2)
    wrapped = wrapped_plain_lines(lines, inner, content_limit)
    if content_limit is not None and len(wrapped) >= content_limit and len(wrapped) > 0:
        # Mark truncation inside the panel instead of letting the terminal scroll.
        wrapped = wrapped[:content_limit]
        if content_limit > 0:
            wrapped[-1] = fit_plain(wrapped[-1], max(0, inner - 4)) + " ..."
    for line in wrapped:
        result.append(color_text("| " + fit_plain(line, inner).ljust(inner) + " |", color, enabled))
    result.append(color_text("+" + "-" * (width - 2) + "+", "border", enabled))
    return result


def compact_status_lines(tank):
    food = tank.current_food_type() if hasattr(tank, "current_food_type") else FOOD_TYPES[0]
    water_value = int(getattr(tank, "water_quality", 70))
    fish_count = len(getattr(tank, "fish", []))
    egg_count = len(getattr(tank, "eggs", []))
    lines = [
        f"Day {tank.day} {tank.current_phase()} | ${tank.shells}",
        f"Fish/Eggs: {fish_count}+{egg_count}/{tank.fish_capacity()} | Comfort {tank.comfort_grade()} ({tank.comfort_score()})",
        f"Water: {water_quality_label(water_value)} {water_value}/100 | Food: {food['name']}",
        f"Tank: {tank_stage_name(tank)} | Theme: {THEMES[getattr(tank, 'theme_index', 0)]}",
        f"Upgrades: {upgrade_summary(tank)}",
    ]
    oldest = max(tank.fish, key=lambda f: f.get("age", 0)) if tank.fish else None
    if oldest:
        lines.append(f"Oldest: {oldest.get('name','Unnamed')} | {fish_stage_from_data(oldest)} | {oldest.get('age',0)/600:.1f} days")
    else:
        lines.append("No fish yet. Watch the egg hatch.")
    return lines


def compact_help_lines():
    return [
        "F feed | G food | W clean | A egg | B bubbles",
        "N name | I profile | [/] cycle fish | X sell | D decor",
        "J album | K history | H help | O shop | E saves | T settings",
        "P pause | C color | V screensaver | S save | L load | Q quit",
        "Esc opens the main menu. Number keys still buy quick shop items.",
    ]


def current_side_panel_lines(tank, width, height_budget):
    mode = getattr(tank, "mode", "tank")
    if mode != "tank":
        title, lines = modal_lines(tank)
        return box_lines(title or "Menu", lines, width, tank.use_color, "text", max_height=height_budget)

    boxes = []
    if getattr(tank, "show_help", False):
        boxes.append(("Help", ui_help_lines(tank), "text"))
    elif getattr(tank, "show_tank_journal", False):
        boxes.append(("History", ui_journal_lines(tank), "text"))
    elif getattr(tank, "show_profile", False):
        boxes.append(("Fish Profile", ui_profile_lines(tank), "text"))
    elif getattr(tank, "show_journal", False):
        boxes.append(("Album", ui_album_lines(tank), "text"))
    else:
        boxes.append(("Tank Status", compact_status_lines(tank), "dim"))
        boxes.append(("Events", tank.event_log[-MAX_EVENTS:], "text"))
        boxes.append(("Hotkeys", compact_help_lines(), "dim"))

    remaining = height_budget
    output = []
    for idx, (title, lines, color) in enumerate(boxes):
        if remaining <= 3:
            break
        # Status/help get small boxes; large overlays can consume the full side.
        if len(boxes) == 1:
            max_h = remaining
        else:
            # Reserve at least 3 rows for each later box.
            later = len(boxes) - idx - 1
            max_h = max(3, remaining - later * 3)
        b = box_lines(title, lines, width, tank.use_color, color, max_height=max_h)
        output.extend(b)
        remaining -= len(b)
    while len(output) < height_budget:
        output.append(" " * width)
    return output[:height_budget]


def make_tank_grid_lines(tank):
    grid = make_grid(tank.width, tank.height)
    width, height = tank.width, tank.height

    for x in range(width):
        safe_draw(grid, x, 0, "-", "border")
        safe_draw(grid, x, height - 1, "_", "border")
    for y in range(height):
        safe_draw(grid, 0, y, "|", "border")
        safe_draw(grid, width - 1, y, "|", "border")
    for x, y in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
        safe_draw(grid, x, y, "+", "border")

    shimmer_chars = ["~", "-", "~", " "]
    wave = math.sin(tank.tick / 10.0)
    for x in range(2, width - 2):
        if random.random() < 0.28 + 0.05 * wave:
            safe_draw(grid, x, 1, random.choice(shimmer_chars), "water")

    if not tank.screensaver:
        for _ in range(max(5, width // 8)):
            if random.random() < 0.40 and height > 8:
                safe_draw(grid, random.randint(2, width - 3), random.randint(3, height - 6), ".", "dim")

    for plant in tank.plants:
        sway = 0
        phase = plant.get("phase", 0)
        if (tank.tick + phase) % 28 < 9:
            sway = -1
        elif (tank.tick + phase) % 28 > 18:
            sway = 1
        base_x = int(plant.get("x", 4))
        plant_height = int(plant.get("height", 4))
        for i in range(plant_height):
            y = height - 2 - i
            x = base_x + (sway if i > plant_height // 2 else 0)
            char = "Y" if i == plant_height - 1 else ("/" if i % 2 == 0 else "\\")
            safe_draw(grid, x, y, char, "plant")

    for rock in tank.rocks:
        for i in range(int(rock.get("width", 3))):
            safe_draw(grid, int(rock.get("x", 3)) + i, height - 2, "#", "rock")

    for decor in tank.decorations:
        kind = decor.get("kind", decor.get("name", "castle"))
        sprite = decor_by_name(kind)["glyphs"]
        draw_multiline_sprite(grid, int(decor.get("x", 5)), int(decor.get("y", height - 4)), sprite, "decor")

    for food in tank.food:
        food_type = food_type_by_key(food.get("kind", "flakes"))
        safe_draw(grid, int(food["x"]), int(food["y"]), food.get("glyph", food_type["glyph"]), food.get("color", food_type["color"]))

    for bubble in tank.bubbles:
        char = "O" if bubble["age"] % 7 == 0 else "." if bubble["age"] % 5 == 0 else "o"
        safe_draw(grid, int(bubble["x"]), int(bubble["y"]), char, "bubble")

    for egg in getattr(tank, "eggs", []):
        hatch_ratio = egg.get("age", 0) / max(1, egg.get("hatch_time", EGG_HATCH_MAX))
        symbol = "(@)" if hatch_ratio > 0.82 and tank.tick % 10 < 5 else "(o)"
        draw_x = bounded_sprite_x(width, egg.get("x", 2), symbol, left_margin=1, right_margin=1)
        egg["x"] = draw_x
        safe_draw_text(grid, draw_x, int(egg.get("y", height - 3)), symbol, "food")

    for snail in tank.snails:
        symbol = "_@/" if snail.get("dir", 1) == 1 else "\\@_"
        draw_x = bounded_sprite_x(width, snail.get("x", 2), symbol, left_margin=1, right_margin=1)
        snail["x"] = draw_x
        safe_draw_text(grid, draw_x, int(snail.get("y", height - 3)), symbol, "snail")

    for visitor in tank.visitors:
        symbol = visitor["right"] if visitor.get("dir", 1) == 1 else visitor["left"]
        draw_x = bounded_sprite_x(width, visitor.get("x", 2), symbol, left_margin=1, right_margin=1)
        safe_draw_text(grid, draw_x, int(visitor["y"]), symbol, "rare")

    for f in tank.fish:
        species = species_by_name(f.get("species", "guppy"))
        symbol = fish_symbol(f)
        draw_x = bounded_sprite_x(width, f.get("x", 2), symbol, left_margin=1, right_margin=1)
        f["x"] = draw_x
        safe_draw_text(grid, draw_x, int(f.get("y", 2)), symbol, species.get("color", "fish"))

    hungry_count = sum(1 for f in tank.fish if f.get("hunger", 0) > 60)
    water_value = int(getattr(tank, "water_quality", 70))
    header = f" FISHTANK {APP_VERSION_LABEL} | Day {tank.day} {tank.current_phase()} | ${tank.shells} | F:{len(tank.fish)} E:{len(getattr(tank,'eggs',[]))}/{tank.fish_capacity()} H:{hungry_count} C:{tank.comfort_grade()} W:{water_quality_grade(water_value)} {'PAUSED' if tank.paused else 'RUN'} "
    if tank.saved_notice > 0 and len(header) < width - 12:
        header += " | SAVED"
    safe_draw_text(grid, 2, 0, header[:width - 4], "text")

    if not tank.screensaver:
        controls = " F feed  G food  W clean  A egg  O shop  H help  I profile  J album  K history  Esc menu  Q quit "
        safe_draw_text(grid, 2, height - 1, controls[:width - 4], "text")

    return render_grid(grid, tank.use_color).splitlines()


def v16_get_terminal_size_for_tank(tank=None):
    size = shutil.get_terminal_size((DEFAULT_WIDTH + 42, DEFAULT_HEIGHT))
    cols, rows = size.columns, size.lines
    stage_bonus = upgrade_level(tank, "tank") if tank is not None else 0
    desired_width = DEFAULT_WIDTH + stage_bonus * 8
    desired_height = DEFAULT_HEIGHT + min(stage_bonus, 3) * 2
    # In wide mode, reserve space for the right dashboard.
    if cols >= 112:
        max_left = max(50, cols - 44)
        width = min(desired_width, max_left)
        height = min(desired_height, max(16, rows - 2))
    else:
        width = min(desired_width, max(40, cols - 2))
        height = min(desired_height, max(14, rows - 7))
    return max(40, width), max(14, height)


def v16_render(tank):
    ensure_v15_state(tank)
    # Refresh dimensions so a resized terminal immediately improves layout.
    new_w, new_h = get_terminal_size_for_tank(tank)
    if (new_w, new_h) != (tank.width, tank.height):
        tank.width, tank.height = new_w, new_h
        tank.clamp_world()

    term = shutil.get_terminal_size((tank.width + 42, tank.height + 4))
    wide = (term.columns >= tank.width + 38) and not tank.screensaver
    begin_frame(tank.use_color)
    tank_lines = make_tank_grid_lines(tank)

    if wide:
        side_width = max(34, min(58, term.columns - tank.width - 3))
        side_lines = current_side_panel_lines(tank, side_width, len(tank_lines))
        for i in range(len(tank_lines)):
            left = pad_visible(tank_lines[i], tank.width)
            right = side_lines[i] if i < len(side_lines) else ""
            print(left + "  " + right)
    else:
        for line in tank_lines:
            print(line)
        if not tank.screensaver:
            # Compact bottom output so the important stuff remains visible in ordinary terminals.
            panel_width = min(tank.width, term.columns - 1)
            if getattr(tank, "mode", "tank") != "tank":
                title, lines = modal_lines(tank)
                for line in box_lines(title or "Menu", lines, panel_width, tank.use_color, "text", max_height=max(5, term.lines - tank.height - 1)):
                    print(line)
            elif getattr(tank, "show_help", False):
                for line in box_lines("Help", compact_help_lines(), panel_width, tank.use_color, "text", max_height=max(5, term.lines - tank.height - 1)):
                    print(line)
            elif getattr(tank, "show_profile", False):
                for line in box_lines("Fish Profile", ui_profile_lines(tank), panel_width, tank.use_color, "text", max_height=max(5, term.lines - tank.height - 1)):
                    print(line)
            elif getattr(tank, "show_journal", False):
                for line in box_lines("Album", ui_album_lines(tank), panel_width, tank.use_color, "text", max_height=max(5, term.lines - tank.height - 1)):
                    print(line)
            elif getattr(tank, "show_tank_journal", False):
                for line in box_lines("History", ui_journal_lines(tank), panel_width, tank.use_color, "text", max_height=max(5, term.lines - tank.height - 1)):
                    print(line)
            else:
                remaining = max(5, term.lines - tank.height - 1)
                lines = compact_status_lines(tank)[:3] + [""] + ["Recent events:"] + tank.event_log[-3:]
                for line in box_lines("Status", lines, panel_width, tank.use_color, "text", max_height=remaining):
                    print(line)

    if tank.screensaver and getattr(tank, "last_screensaver_note", "") and getattr(tank, "mode", "tank") == "tank":
        print(color_text(fit_plain(tank.last_screensaver_note, term.columns - 1), "dim", tank.use_color))
    end_frame(tank.use_color)


def v16_init(self):
    _old_init_v14(self)
    self.width, self.height = get_terminal_size_for_tank(self)
    self.mode = "tank"
    self.menu_cursor = self.shop_cursor = self.fish_cursor = self.decor_cursor = self.slot_cursor = 0
    self.theme_index = 0
    self.market_requests = []
    self.market_day = 0
    self.discovered_variants = {}
    self.album_stats = {}
    self.settings_cursor = 0
    ensure_v15_state(self)


def v17_handle_tank_key(self, key):
    """Handle normal tank-view hotkeys using the key that was already read.

    This fixes the v15/v16 regression where the wrapper consumed the key and then
    called the older handler, which tried to read a *second* key. As a result,
    actions like F=feed and W=clean appeared to do nothing.
    """
    # Core app controls.
    if key == "q":
        if self.autosave:
            self.save()
        self.running = False
        return
    if key == "\x1b":
        self.mode = "main_menu"
        return

    # Care actions.
    if key == "f":
        self.feed()
        return
    if key == "g":
        self.cycle_food()
        return
    if key == "w":
        self.clean_tank()
        return
    if key == "a":
        self.add_egg(free=True)
        return
    if key == "b":
        self.add_bubbles()
        return

    # Simulation and persistence.
    if key == "p":
        self.paused = not self.paused
        self.log("The tank pauses." if self.paused else "The tank resumes.")
        return
    if key == "s":
        self.save()
        return
    if key == "l":
        self.load()
        self.mode = "tank"
        return
    if key == "r":
        self.reset_to_egg()
        self.mode = "tank"
        return

    # View/settings toggles.
    if key == "v":
        self.screensaver = not self.screensaver
        self.log("Screensaver mode enabled." if self.screensaver else "Screensaver mode disabled.")
        return
    if key == "c":
        self.use_color = not self.use_color
        self.log("Color enabled." if self.use_color else "Color disabled.")
        return
    if key == "m":
        self.old_age_mortality = not self.old_age_mortality
        self.log("Old-age mortality enabled." if self.old_age_mortality else "Old-age mortality disabled.")
        return

    # Panels and menus.
    if key == "h":
        self.show_help = not self.show_help
        if self.show_help:
            self.show_journal = self.show_profile = self.show_tank_journal = False
        return
    if key == "o":
        self.mode = "shop_menu"
        self.show_help = self.show_journal = self.show_profile = self.show_tank_journal = False
        return
    if key == "e":
        self.mode = "save_slots"
        return
    if key == "t":
        self.mode = "settings"
        return
    if key == "n":
        self.mode = "fish_select_name"
        self.fish_cursor = self.clamped_selected_index()
        return
    if key == "x":
        self.mode = "fish_select_sell"
        self.fish_cursor = self.clamped_selected_index()
        return
    if key == "d":
        self.mode = "decor_select"
        return
    if key == "i":
        self.show_profile = not self.show_profile
        if self.show_profile:
            self.show_help = self.show_journal = self.show_tank_journal = False
            self.selected_fish_index = self.clamped_selected_index()
        return
    if key == "j":
        self.show_journal = not self.show_journal
        if self.show_journal:
            self.show_help = self.show_profile = self.show_tank_journal = False
        return
    if key == "k":
        self.show_tank_journal = not getattr(self, "show_tank_journal", False)
        if self.show_tank_journal:
            self.show_help = self.show_profile = self.show_journal = False
        return
    if key == "[":
        if self.fish:
            self.selected_fish_index = (self.clamped_selected_index() - 1) % len(self.fish)
            self.show_profile = True
            self.show_help = self.show_journal = self.show_tank_journal = False
        return
    if key == "]":
        if self.fish:
            self.selected_fish_index = (self.clamped_selected_index() + 1) % len(self.fish)
            self.show_profile = True
            self.show_help = self.show_journal = self.show_tank_journal = False
        return

    # Direct purchase hotkeys remain available from the tank view.
    if key == "1":
        self.buy_fish()
        return
    if key == "2":
        self.buy_plant()
        return
    if key == "3":
        self.buy_decoration()
        return
    if key == "4":
        self.buy_snail()
        return
    if key == "5":
        self.buy_rare_egg()
        return
    if key == "6":
        self.buy_upgrade("tank")
        return
    if key == "7":
        self.buy_upgrade("filter")
        return
    if key == "8":
        self.buy_upgrade("bubbler")
        return
    if key == "9":
        self.buy_upgrade("nursery")
        return
    if key == "0":
        self.buy_upgrade("feeder")
        return


def v16_handle_input(self):
    ensure_v15_state(self)
    key = get_key()
    if not key:
        return
    mode = getattr(self, "mode", "tank")
    if mode != "tank":
        handle_v15_modal_input(self, key)
        return
    v17_handle_tank_key(self, key)


def v16_main():
    global TERMINAL_OLD_SETTINGS
    tank = Fishtank()
    old_settings = None

    if SAVE_FILE.exists() or (LEGACY_SAVE_FILE.exists() and LEGACY_SAVE_FILE.is_file()):
        tank.load()
        tank.mode = "tank"

    interactive_stdin = bool(getattr(sys.stdin, "isatty", lambda: False)())
    if os.name != "nt" and interactive_stdin:
        try:
            old_settings = termios.tcgetattr(sys.stdin)
            TERMINAL_OLD_SETTINGS = old_settings
            tty.setcbreak(sys.stdin.fileno())
        except termios.error:
            old_settings = None

    try:
        clear_screen()
        hide_cursor_if_possible(tank.use_color)
        while tank.running:
            tank.handle_input()
            tank.update()
            render(tank)
            time.sleep(FPS_DELAY)
    except KeyboardInterrupt:
        if tank.autosave:
            tank.save()
    finally:
        if os.name != "nt" and old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        show_cursor_if_possible(True)
        clear_screen()
        print("The fishtank goes quiet.")
        print(f"Saved to: {SAVE_FILE.resolve()}")




# ============================================================
# v19 UI/theme polish patch
# ------------------------------------------------------------
# - Removes the redundant hotkeys printed inside the tank footer.
# - Makes the wide right dashboard reserve fixed space for Hotkeys so
#   Events cannot crowd it out.
# - Makes themes visually alter the aquarium instead of only changing text.
# ============================================================

APP_VERSION_LABEL = "v19"

THEME_SKINS = {
    "Classic": {
        "top": "-", "bottom": "_", "side": "|", "corner": "+",
        "water": ["~", "-", "~", " "], "ambient": ".", "rock": "#", "floor_fill": None,
        "border_color": "border", "water_color": "water", "ambient_color": "dim", "rock_color": "rock",
        "plant_color": "plant", "decor_color": "decor", "bubble_color": "bubble",
    },
    "Riverbed": {
        "top": "=", "bottom": "=", "side": "|", "corner": "+",
        "water": ["~", "~", ".", " "], "ambient": "`", "rock": "o", "floor_fill": ".",
        "border_color": "rock", "water_color": "water", "ambient_color": "rock", "rock_color": "rock",
        "plant_color": "plant", "decor_color": "gold", "bubble_color": "bubble",
    },
    "Coral Reef": {
        "top": "-", "bottom": "=", "side": "|", "corner": "+",
        "water": ["~", "≈", "~", " "], "ambient": "*", "rock": "¤", "floor_fill": ".",
        "border_color": "teal", "water_color": "teal", "ambient_color": "pink", "rock_color": "orange",
        "plant_color": "lime", "decor_color": "pink", "bubble_color": "bubble",
    },
    "GBC Green": {
        "top": "#", "bottom": "#", "side": "#", "corner": "#",
        "water": ["~", "-", ".", " "], "ambient": ".", "rock": "#", "floor_fill": None,
        "border_color": "lime", "water_color": "lime", "ambient_color": "lime", "rock_color": "lime",
        "plant_color": "lime", "decor_color": "lime", "bubble_color": "lime", "fish_color": "lime",
    },
    "Moonlit": {
        "top": "-", "bottom": "_", "side": "|", "corner": "+",
        "water": ["~", "·", "~", " "], "ambient": "'", "rock": "#", "floor_fill": None,
        "border_color": "violet", "water_color": "blue", "ambient_color": "silver", "rock_color": "silver",
        "plant_color": "teal", "decor_color": "violet", "bubble_color": "silver",
    },
    "Deep Sea": {
        "top": "~", "bottom": "=", "side": "|", "corner": "+",
        "water": ["≈", "~", "·", " "], "ambient": "·", "rock": "▓", "floor_fill": None,
        "border_color": "blue", "water_color": "blue", "ambient_color": "violet", "rock_color": "violet",
        "plant_color": "teal", "decor_color": "rare", "bubble_color": "silver",
    },
}


def theme_name(tank):
    try:
        return THEMES[int(getattr(tank, "theme_index", 0)) % len(THEMES)]
    except Exception:
        return "Classic"


def theme_skin(tank):
    return THEME_SKINS.get(theme_name(tank), THEME_SKINS["Classic"])


def themed_color(tank, role, fallback):
    skin = theme_skin(tank)
    if "fish_color" in skin and role == "fish":
        return skin["fish_color"]
    return skin.get(role + "_color", fallback)


def make_tank_grid_lines_v19(tank):
    grid = make_grid(tank.width, tank.height)
    width, height = tank.width, tank.height
    skin = theme_skin(tank)

    top = skin.get("top", "-")
    bottom = skin.get("bottom", "_")
    side = skin.get("side", "|")
    corner = skin.get("corner", "+")
    border_color = themed_color(tank, "border", "border")

    for x in range(width):
        safe_draw(grid, x, 0, top, border_color)
        safe_draw(grid, x, height - 1, bottom, border_color)
    for y in range(height):
        safe_draw(grid, 0, y, side, border_color)
        safe_draw(grid, width - 1, y, side, border_color)
    for x, y in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
        safe_draw(grid, x, y, corner, border_color)

    # Optional themed gravel/substrate band just above the floor.
    floor_fill = skin.get("floor_fill")
    if floor_fill and height > 6:
        for x in range(2, width - 2):
            if random.random() < 0.35:
                safe_draw(grid, x, height - 2, floor_fill, themed_color(tank, "rock", "rock"))

    shimmer_chars = skin.get("water", ["~", "-", "~", " "])
    wave = math.sin(tank.tick / 10.0)
    for x in range(2, width - 2):
        if random.random() < 0.28 + 0.05 * wave:
            safe_draw(grid, x, 1, random.choice(shimmer_chars), themed_color(tank, "water", "water"))

    if not tank.screensaver:
        ambient = skin.get("ambient", ".")
        for _ in range(max(5, width // 8)):
            if random.random() < 0.40 and height > 8:
                safe_draw(grid, random.randint(2, width - 3), random.randint(3, height - 6), ambient, themed_color(tank, "ambient", "dim"))

    for plant in tank.plants:
        sway = 0
        phase = plant.get("phase", 0)
        if (tank.tick + phase) % 28 < 9:
            sway = -1
        elif (tank.tick + phase) % 28 > 18:
            sway = 1
        base_x = int(plant.get("x", 4))
        plant_height = int(plant.get("height", 4))
        for i in range(plant_height):
            y = height - 2 - i
            x = base_x + (sway if i > plant_height // 2 else 0)
            char = "Y" if i == plant_height - 1 else ("/" if i % 2 == 0 else "\\")
            safe_draw(grid, x, y, char, themed_color(tank, "plant", "plant"))

    for rock in tank.rocks:
        for i in range(int(rock.get("width", 3))):
            safe_draw(grid, int(rock.get("x", 3)) + i, height - 2, skin.get("rock", "#"), themed_color(tank, "rock", "rock"))

    for decor in tank.decorations:
        kind = decor.get("kind", decor.get("name", "castle"))
        sprite = decor_by_name(kind)["glyphs"]
        draw_multiline_sprite(grid, int(decor.get("x", 5)), int(decor.get("y", height - 4)), sprite, themed_color(tank, "decor", "decor"))

    for food in tank.food:
        food_type = food_type_by_key(food.get("kind", "flakes"))
        safe_draw(grid, int(food["x"]), int(food["y"]), food.get("glyph", food_type["glyph"]), food.get("color", food_type["color"]))

    for bubble in tank.bubbles:
        char = "O" if bubble["age"] % 7 == 0 else "." if bubble["age"] % 5 == 0 else "o"
        safe_draw(grid, int(bubble["x"]), int(bubble["y"]), char, themed_color(tank, "bubble", "bubble"))

    for egg in getattr(tank, "eggs", []):
        hatch_ratio = egg.get("age", 0) / max(1, egg.get("hatch_time", EGG_HATCH_MAX))
        symbol = "(@)" if hatch_ratio > 0.82 and tank.tick % 10 < 5 else "(o)"
        draw_x = bounded_sprite_x(width, egg.get("x", 2), symbol, left_margin=1, right_margin=1)
        egg["x"] = draw_x
        safe_draw_text(grid, draw_x, int(egg.get("y", height - 3)), symbol, "food")

    for snail in tank.snails:
        symbol = "_@/" if snail.get("dir", 1) == 1 else "\\@_"
        draw_x = bounded_sprite_x(width, snail.get("x", 2), symbol, left_margin=1, right_margin=1)
        snail["x"] = draw_x
        safe_draw_text(grid, draw_x, int(snail.get("y", height - 3)), symbol, "snail")

    for visitor in tank.visitors:
        symbol = visitor["right"] if visitor.get("dir", 1) == 1 else visitor["left"]
        draw_x = bounded_sprite_x(width, visitor.get("x", 2), symbol, left_margin=1, right_margin=1)
        safe_draw_text(grid, draw_x, int(visitor["y"]), symbol, "rare")

    for f in tank.fish:
        species = species_by_name(f.get("species", "guppy"))
        symbol = fish_symbol(f)
        draw_x = bounded_sprite_x(width, f.get("x", 2), symbol, left_margin=1, right_margin=1)
        f["x"] = draw_x
        fish_color = themed_color(tank, "fish", globals().get("fish_color_key_v21", lambda ff: species.get("color", "fish"))(f))
        safe_draw_text(grid, draw_x, int(f.get("y", 2)), symbol, fish_color)

    hungry_count = sum(1 for f in tank.fish if f.get("hunger", 0) > 60)
    water_value = int(getattr(tank, "water_quality", 70))
    header = f" FISHTANK {APP_VERSION_LABEL} | Day {tank.day} {tank.current_phase()} | ${tank.shells} | F:{len(tank.fish)} E:{len(getattr(tank,'eggs',[]))}/{tank.fish_capacity()} H:{hungry_count} C:{tank.comfort_grade()} W:{water_quality_grade(water_value)} | {theme_name(tank)} {'PAUSED' if tank.paused else 'RUN'} "
    if tank.saved_notice > 0 and len(header) < width - 12:
        header += " | SAVED"
    safe_draw_text(grid, 2, 0, header[:width - 4], "text")

    # v19: no redundant hotkey strip inside the tank. The right dashboard already
    # has a dedicated Hotkeys panel, and the clean bottom border gives the tank
    # more visual breathing room.
    return render_grid(grid, tank.use_color).splitlines()


def current_side_panel_lines_v19(tank, width, height_budget):
    """Build the right dashboard without allowing Events to cut off Hotkeys."""
    mode = getattr(tank, "mode", "tank")
    if mode != "tank":
        title, lines = modal_lines(tank)
        return box_lines(title or "Menu", lines, width, tank.use_color, "text", max_height=height_budget)

    if getattr(tank, "show_help", False):
        return box_lines("Help", ui_help_lines(tank), width, tank.use_color, "text", max_height=height_budget)
    if getattr(tank, "show_tank_journal", False):
        return box_lines("History", ui_journal_lines(tank), width, tank.use_color, "text", max_height=height_budget)
    if getattr(tank, "show_profile", False):
        return box_lines("Fish Profile", ui_profile_lines(tank), width, tank.use_color, "text", max_height=height_budget)
    if getattr(tank, "show_journal", False):
        return box_lines("Album", ui_album_lines(tank), width, tank.use_color, "text", max_height=height_budget)

    # Default dashboard: fixed reservation so the bottom panel survives even on
    # shorter terminals. Hotkeys gets six visible rows; status gets up to eight;
    # events receives whatever remains.
    hotkey_h = min(7, max(5, height_budget // 4))
    status_h = min(8, max(5, height_budget // 3))
    events_h = max(4, height_budget - status_h - hotkey_h)

    status_box = box_lines("Tank Status", compact_status_lines(tank), width, tank.use_color, "dim", max_height=status_h)
    hotkey_box = box_lines("Hotkeys", compact_help_lines(), width, tank.use_color, "dim", max_height=hotkey_h)
    events_budget = max(3, height_budget - len(status_box) - len(hotkey_box))
    events_box = box_lines("Events", tank.event_log[-MAX_EVENTS:], width, tank.use_color, "text", max_height=events_budget)

    output = status_box + events_box + hotkey_box
    while len(output) < height_budget:
        output.append(" " * width)
    return output[:height_budget]


def v19_render(tank):
    ensure_v15_state(tank)
    new_w, new_h = get_terminal_size_for_tank(tank)
    if (new_w, new_h) != (tank.width, tank.height):
        tank.width, tank.height = new_w, new_h
        tank.clamp_world()

    term = shutil.get_terminal_size((tank.width + 42, tank.height + 4))
    wide = (term.columns >= tank.width + 38) and not tank.screensaver
    begin_frame(tank.use_color)
    tank_lines = make_tank_grid_lines(tank)

    if wide:
        side_width = max(34, min(58, term.columns - tank.width - 3))
        side_lines = current_side_panel_lines(tank, side_width, len(tank_lines))
        for i in range(len(tank_lines)):
            left = pad_visible(tank_lines[i], tank.width)
            right = side_lines[i] if i < len(side_lines) else ""
            print(left + "  " + right)
    else:
        for line in tank_lines:
            print(line)
        if not tank.screensaver:
            panel_width = min(tank.width, term.columns - 1)
            remaining = max(5, term.lines - tank.height - 1)
            if getattr(tank, "mode", "tank") != "tank":
                title, lines = modal_lines(tank)
                panel = box_lines(title or "Menu", lines, panel_width, tank.use_color, "text", max_height=remaining)
            elif getattr(tank, "show_help", False):
                panel = box_lines("Help", compact_help_lines(), panel_width, tank.use_color, "text", max_height=remaining)
            elif getattr(tank, "show_profile", False):
                panel = box_lines("Fish Profile", ui_profile_lines(tank), panel_width, tank.use_color, "text", max_height=remaining)
            elif getattr(tank, "show_journal", False):
                panel = box_lines("Album", ui_album_lines(tank), panel_width, tank.use_color, "text", max_height=remaining)
            elif getattr(tank, "show_tank_journal", False):
                panel = box_lines("History", ui_journal_lines(tank), panel_width, tank.use_color, "text", max_height=remaining)
            else:
                lines = compact_status_lines(tank)[:3] + ["", "Recent events:"] + tank.event_log[-2:] + ["", "Hotkeys:"] + compact_help_lines()[:2]
                panel = box_lines("Status", lines, panel_width, tank.use_color, "text", max_height=remaining)
            for line in panel:
                print(line)

    if tank.screensaver and getattr(tank, "last_screensaver_note", "") and getattr(tank, "mode", "tank") == "tank":
        print(color_text(fit_plain(tank.last_screensaver_note, term.columns - 1), "dim", tank.use_color))
    end_frame(tank.use_color)


make_tank_grid_lines = make_tank_grid_lines_v19
current_side_panel_lines = current_side_panel_lines_v19
render = v19_render

get_terminal_size_for_tank = v16_get_terminal_size_for_tank
# render overridden by v19_render
Fishtank.__init__ = v16_init
Fishtank.handle_input = v16_handle_input
main = v16_main



# ============================================================
# v20 dashboard polish patch
# ------------------------------------------------------------
# - Moves dense tank information out of the top tank border and into Tank Status.
# - Adds collapsible right-dashboard panels.
# - Reduces panel wrapping/cutoff by reserving more right-side space on wide terminals.
# - Keeps the tank view clean while leaving menu overlays intact.
# ============================================================

APP_VERSION_LABEL = "v20"
PANEL_ORDER = ["status", "events", "hotkeys"]
PANEL_TITLES = {"status": "Tank Status", "events": "Events", "hotkeys": "Hotkeys"}


def ensure_v20_state(tank):
    ensure_v15_state(tank)
    if not hasattr(tank, "collapsed_panels") or not isinstance(getattr(tank, "collapsed_panels"), dict):
        tank.collapsed_panels = {"status": False, "events": False, "hotkeys": False}
    else:
        for key in PANEL_ORDER:
            tank.collapsed_panels.setdefault(key, False)
    if getattr(tank, "panel_focus", None) not in PANEL_ORDER:
        tank.panel_focus = "status"


def compact_status_lines_v20(tank):
    ensure_v20_state(tank)
    food = tank.current_food_type() if hasattr(tank, "current_food_type") else FOOD_TYPES[0]
    water_value = int(getattr(tank, "water_quality", 70))
    fish_count = len(getattr(tank, "fish", []))
    egg_count = len(getattr(tank, "eggs", []))
    hungry_count = sum(1 for f in getattr(tank, "fish", []) if f.get("hunger", 0) > 60)
    saved = " | SAVED" if getattr(tank, "saved_notice", 0) > 0 else ""
    paused = "Paused" if getattr(tank, "paused", False) else "Running"
    lines = [
        f"Day {tank.day} - {tank.current_phase()} | {paused}{saved}",
        f"${tank.shells} | Fish: {fish_count} | Eggs: {egg_count}/{tank.fish_capacity()}",
        f"Hungry: {hungry_count} | Comfort: {tank.comfort_grade()} ({tank.comfort_score()})",
        f"Water: {water_quality_label(water_value)} {water_value}/100 | Food: {food['name']}",
        f"Tank: {tank_stage_name(tank)} | Theme: {theme_name(tank)}",
        f"Upgrades: {upgrade_summary(tank)}",
    ]
    oldest = max(tank.fish, key=lambda f: f.get("age", 0)) if tank.fish else None
    if oldest:
        lines.append(f"Oldest: {oldest.get('name','Unnamed')} | {fish_stage_from_data(oldest)} | {oldest.get('age',0)/600:.1f} days")
    else:
        lines.append("No fish yet. Watch the egg hatch.")
    return lines


def compact_help_lines_v20():
    return [
        "F feed  G food  W clean  A egg  B bubbles",
        "N name  I profile  X sell  D decor  O shop",
        "J album  K history  H help  E saves  T settings",
        "P pause  C color  V screen  S save  L load  Q quit",
        "Tab panel  Enter collapse  Esc menu",
    ]


def collapsed_panel_line(title, width, enabled=True, focused=False):
    marker = ">" if focused else " "
    text = f"{marker} {title} [collapsed]"
    text = fit_plain(text, max(0, width - 2))
    return color_text("+" + text.ljust(max(0, width - 2)) + "+", "border", enabled)


def panel_box(title, lines, width, tank, key, color="text", collapsed=False):
    focused = getattr(tank, "panel_focus", "status") == key
    display_title = ("> " if focused else "  ") + title
    if collapsed:
        return [collapsed_panel_line(title, width, tank.use_color, focused)]
    return box_lines(display_title, lines, width, tank.use_color, color, max_height=None)


def fit_dashboard_boxes(tank, width, height_budget):
    ensure_v20_state(tank)
    collapsed = dict(tank.collapsed_panels)

    contents = {
        "status": compact_status_lines_v20(tank),
        "events": list(getattr(tank, "event_log", []))[-4:],
        "hotkeys": compact_help_lines_v20(),
    }
    colors = {"status": "dim", "events": "text", "hotkeys": "dim"}

    def build(local_collapsed):
        out = []
        for key in PANEL_ORDER:
            if out:
                # No blank spacer; every row matters in shorter terminals.
                pass
            out.extend(panel_box(PANEL_TITLES[key], contents[key], width, tank, key, colors[key], local_collapsed.get(key, False)))
        return out

    boxes = build(collapsed)
    if len(boxes) <= height_budget:
        return boxes

    # Prefer keeping Tank Status visible. Auto-collapse lower-priority panels only
    # for this frame; the user's manual collapsed states are not overwritten.
    focus = getattr(tank, "panel_focus", "status")
    for key in ["hotkeys", "events", "status"]:
        if key != focus:
            collapsed[key] = True
            boxes = build(collapsed)
            if len(boxes) <= height_budget:
                return boxes

    # Last resort: use ultra-compact one-line panels rather than cutting text.
    ultra = []
    for key in PANEL_ORDER:
        focused = key == focus
        if key == "status":
            first = contents[key][:3]
            ultra.extend(panel_box(PANEL_TITLES[key], first, width, tank, key, colors[key], collapsed.get(key, False)))
        else:
            ultra.append(collapsed_panel_line(PANEL_TITLES[key], width, tank.use_color, focused))
    return ultra[:height_budget]


def current_side_panel_lines_v20(tank, width, height_budget):
    ensure_v20_state(tank)
    mode = getattr(tank, "mode", "tank")
    if mode != "tank":
        title, lines = modal_lines(tank)
        return box_lines(title or "Menu", lines, width, tank.use_color, "text", max_height=height_budget)

    if getattr(tank, "show_help", False):
        return box_lines("Help", ui_help_lines(tank), width, tank.use_color, "text", max_height=height_budget)
    if getattr(tank, "show_tank_journal", False):
        return box_lines("History", ui_journal_lines(tank), width, tank.use_color, "text", max_height=height_budget)
    if getattr(tank, "show_profile", False):
        return box_lines("Fish Profile", ui_profile_lines(tank), width, tank.use_color, "text", max_height=height_budget)
    if getattr(tank, "show_journal", False):
        return box_lines("Album", ui_album_lines(tank), width, tank.use_color, "text", max_height=height_budget)

    output = fit_dashboard_boxes(tank, width, height_budget)
    while len(output) < height_budget:
        output.append(" " * width)
    return output[:height_budget]


def make_tank_grid_lines_v20(tank):
    grid = make_grid(tank.width, tank.height)
    width, height = tank.width, tank.height
    skin = theme_skin(tank)

    top = skin.get("top", "-")
    bottom = skin.get("bottom", "_")
    side = skin.get("side", "|")
    corner = skin.get("corner", "+")
    border_color = themed_color(tank, "border", "border")

    for x in range(width):
        safe_draw(grid, x, 0, top, border_color)
        safe_draw(grid, x, height - 1, bottom, border_color)
    for y in range(height):
        safe_draw(grid, 0, y, side, border_color)
        safe_draw(grid, width - 1, y, side, border_color)
    for x, y in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
        safe_draw(grid, x, y, corner, border_color)

    floor_fill = skin.get("floor_fill")
    if floor_fill and height > 6:
        for x in range(2, width - 2):
            if random.random() < 0.35:
                safe_draw(grid, x, height - 2, floor_fill, themed_color(tank, "rock", "rock"))

    shimmer_chars = skin.get("water", ["~", "-", "~", " "])
    wave = math.sin(tank.tick / 10.0)
    for x in range(2, width - 2):
        if random.random() < 0.28 + 0.05 * wave:
            safe_draw(grid, x, 1, random.choice(shimmer_chars), themed_color(tank, "water", "water"))

    if not tank.screensaver:
        ambient = skin.get("ambient", ".")
        for _ in range(max(5, width // 8)):
            if random.random() < 0.40 and height > 8:
                safe_draw(grid, random.randint(2, width - 3), random.randint(3, height - 6), ambient, themed_color(tank, "ambient", "dim"))

    for plant in tank.plants:
        sway = 0
        phase = plant.get("phase", 0)
        if (tank.tick + phase) % 28 < 9:
            sway = -1
        elif (tank.tick + phase) % 28 > 18:
            sway = 1
        base_x = int(plant.get("x", 4))
        plant_height = int(plant.get("height", 4))
        for i in range(plant_height):
            y = height - 2 - i
            x = base_x + (sway if i > plant_height // 2 else 0)
            char = "Y" if i == plant_height - 1 else ("/" if i % 2 == 0 else "\\")
            safe_draw(grid, x, y, char, themed_color(tank, "plant", "plant"))

    for rock in tank.rocks:
        for i in range(int(rock.get("width", 3))):
            safe_draw(grid, int(rock.get("x", 3)) + i, height - 2, skin.get("rock", "#"), themed_color(tank, "rock", "rock"))

    for decor in tank.decorations:
        kind = decor.get("kind", decor.get("name", "castle"))
        sprite = decor_by_name(kind)["glyphs"]
        draw_multiline_sprite(grid, int(decor.get("x", 5)), int(decor.get("y", height - 4)), sprite, themed_color(tank, "decor", "decor"))

    for food in tank.food:
        food_type = food_type_by_key(food.get("kind", "flakes"))
        safe_draw(grid, int(food["x"]), int(food["y"]), food.get("glyph", food_type["glyph"]), food.get("color", food_type["color"]))

    for bubble in tank.bubbles:
        char = "O" if bubble["age"] % 7 == 0 else "." if bubble["age"] % 5 == 0 else "o"
        safe_draw(grid, int(bubble["x"]), int(bubble["y"]), char, themed_color(tank, "bubble", "bubble"))

    for egg in getattr(tank, "eggs", []):
        hatch_ratio = egg.get("age", 0) / max(1, egg.get("hatch_time", EGG_HATCH_MAX))
        symbol = "(@)" if hatch_ratio > 0.82 and tank.tick % 10 < 5 else "(o)"
        draw_x = bounded_sprite_x(width, egg.get("x", 2), symbol, left_margin=1, right_margin=1)
        egg["x"] = draw_x
        safe_draw_text(grid, draw_x, int(egg.get("y", height - 3)), symbol, "food")

    for snail in tank.snails:
        symbol = "_@/" if snail.get("dir", 1) == 1 else "\\@_"
        draw_x = bounded_sprite_x(width, snail.get("x", 2), symbol, left_margin=1, right_margin=1)
        snail["x"] = draw_x
        safe_draw_text(grid, draw_x, int(snail.get("y", height - 3)), symbol, "snail")

    for visitor in tank.visitors:
        symbol = visitor["right"] if visitor.get("dir", 1) == 1 else visitor["left"]
        draw_x = bounded_sprite_x(width, visitor.get("x", 2), symbol, left_margin=1, right_margin=1)
        safe_draw_text(grid, draw_x, int(visitor["y"]), symbol, "rare")

    for f in tank.fish:
        species = species_by_name(f.get("species", "guppy"))
        symbol = fish_symbol(f)
        draw_x = bounded_sprite_x(width, f.get("x", 2), symbol, left_margin=1, right_margin=1)
        f["x"] = draw_x
        fish_color = themed_color(tank, "fish", globals().get("fish_color_key_v21", lambda ff: species.get("color", "fish"))(f))
        safe_draw_text(grid, draw_x, int(f.get("y", 2)), symbol, fish_color)

    # v20: keep the aquarium border readable. Dense status moved to the
    # Tank Status dashboard panel.
    title = f" ASCII FISHTANK {APP_VERSION_LABEL} "
    if getattr(tank, "paused", False):
        title += "| PAUSED "
    if getattr(tank, "saved_notice", 0) > 0:
        title += "| SAVED "
    safe_draw_text(grid, 2, 0, title[:width - 4], "text")
    return render_grid(grid, tank.use_color).splitlines()


def v20_get_terminal_size_for_tank(tank=None):
    size = shutil.get_terminal_size((DEFAULT_WIDTH + 58, DEFAULT_HEIGHT))
    cols, rows = size.columns, size.lines
    stage_bonus = upgrade_level(tank, "tank") if tank is not None else 0
    desired_width = DEFAULT_WIDTH + stage_bonus * 8
    desired_height = DEFAULT_HEIGHT + min(stage_bonus, 3) * 2
    if cols >= 112:
        # Reserve a meaningful dashboard width so right-side panels wrap less.
        reserve = max(48, min(68, cols // 3))
        width = min(desired_width, max(50, cols - reserve - 3))
        height = min(desired_height, max(16, rows - 2))
    else:
        width = min(desired_width, max(40, cols - 2))
        height = min(desired_height, max(14, rows - 7))
    return max(40, width), max(14, height)


def v20_handle_input(self):
    ensure_v20_state(self)
    key = get_key()
    if not key:
        return
    mode = getattr(self, "mode", "tank")
    if mode != "tank":
        handle_v15_modal_input(self, key)
        return

    # Dashboard panel controls. They only operate in the tank view and do not
    # steal normal letter hotkeys like F/W/S.
    if key == "\t":
        idx = PANEL_ORDER.index(getattr(self, "panel_focus", "status"))
        self.panel_focus = PANEL_ORDER[(idx + 1) % len(PANEL_ORDER)]
        return
    if key in {"\r", "\n"}:
        focus = getattr(self, "panel_focus", "status")
        self.collapsed_panels[focus] = not self.collapsed_panels.get(focus, False)
        return

    v17_handle_tank_key(self, key)


def v20_render(tank):
    ensure_v20_state(tank)
    new_w, new_h = get_terminal_size_for_tank(tank)
    if (new_w, new_h) != (tank.width, tank.height):
        tank.width, tank.height = new_w, new_h
        tank.clamp_world()

    term = shutil.get_terminal_size((tank.width + 58, tank.height + 4))
    wide = (term.columns >= tank.width + 42) and not tank.screensaver
    begin_frame(tank.use_color)
    tank_lines = make_tank_grid_lines(tank)

    if wide:
        side_width = max(40, min(72, term.columns - tank.width - 3))
        side_lines = current_side_panel_lines(tank, side_width, len(tank_lines))
        for i in range(len(tank_lines)):
            left = pad_visible(tank_lines[i], tank.width)
            right = side_lines[i] if i < len(side_lines) else ""
            print(left + "  " + right)
    else:
        for line in tank_lines:
            print(line)
        if not tank.screensaver:
            panel_width = min(tank.width, term.columns - 1)
            remaining = max(5, term.lines - tank.height - 1)
            if getattr(tank, "mode", "tank") != "tank":
                title, lines = modal_lines(tank)
                panel = box_lines(title or "Menu", lines, panel_width, tank.use_color, "text", max_height=remaining)
            elif getattr(tank, "show_help", False):
                panel = box_lines("Help", compact_help_lines_v20(), panel_width, tank.use_color, "text", max_height=remaining)
            elif getattr(tank, "show_profile", False):
                panel = box_lines("Fish Profile", ui_profile_lines(tank), panel_width, tank.use_color, "text", max_height=remaining)
            elif getattr(tank, "show_journal", False):
                panel = box_lines("Album", ui_album_lines(tank), panel_width, tank.use_color, "text", max_height=remaining)
            elif getattr(tank, "show_tank_journal", False):
                panel = box_lines("History", ui_journal_lines(tank), panel_width, tank.use_color, "text", max_height=remaining)
            else:
                compact_lines = compact_status_lines_v20(tank)[:4] + ["", "Tab selects panels. Enter collapses selected panel."]
                panel = box_lines("Tank Status", compact_lines, panel_width, tank.use_color, "text", max_height=remaining)
            for line in panel:
                print(line)

    if tank.screensaver and getattr(tank, "last_screensaver_note", "") and getattr(tank, "mode", "tank") == "tank":
        print(color_text(fit_plain(tank.last_screensaver_note, term.columns - 1), "dim", tank.use_color))
    end_frame(tank.use_color)


# Install v20 overrides.
compact_status_lines = compact_status_lines_v20
compact_help_lines = compact_help_lines_v20
make_tank_grid_lines = make_tank_grid_lines_v20
current_side_panel_lines = current_side_panel_lines_v20
get_terminal_size_for_tank = v20_get_terminal_size_for_tank
render = v20_render
Fishtank.handle_input = v20_handle_input
main = v16_main


# ============================================================
# v21 genetics + hatchling name pass
# ============================================================
APP_VERSION_LABEL = "v21"

NAME_PREFIXES = [
    "Bub", "Fin", "Glim", "Mim", "Peb", "Cor", "Nim", "Lumi", "Kelp", "Pip",
    "Moch", "Tetra", "Gup", "Miso", "Nori", "Aqua", "Pearl", "Ripple", "Sunny", "Moon",
]
NAME_SUFFIXES = [
    "ble", "by", "kin", "let", "fin", "scale", "drop", "shine", "wiggle", "sprout",
    "whisk", "bloom", "dash", "moss", "pearl", "tail", "gill", "bop", "drift", "bean",
]
NAME_RARE = [
    "Captain Bubbles", "Sir Finley", "Lady Glimmer", "Professor Gill", "Tiny Neptune",
    "Mister Wiggles", "Duke of Kelp", "Pearl Diver", "Moonbean", "Lord Bloopington",
]
GENE_COLOR_KEYS = ["fish", "fish2", "orange", "gold", "pink", "violet", "teal", "lime", "silver", "blue"]
GENE_PATTERNS = ["plain", "soft stripes", "speckled", "dark tail", "bright fins", "pale belly", "masked face", "ringed fins"]
GENE_FINS = ["short", "rounded", "flowing", "spiky", "veil", "forked"]
GENE_BODY = ["slim", "round", "long", "tiny", "stout"]

_old_make_fish_v20 = make_fish
_old_make_egg_v20 = make_egg
_old_choose_variant_v20 = choose_variant
_old_apply_tank_data_v20 = apply_tank_data
_old_tank_to_data_v20 = tank_to_data
_old_ui_profile_lines_v20 = ui_profile_lines
_old_ui_album_lines_v20 = ui_album_lines
_old_make_tank_grid_lines_v20 = make_tank_grid_lines
_old_v20_update_eggs = Fishtank.update_eggs
_old_v20_maybe_breed_fish = Fishtank.maybe_breed_fish
_old_ensure_v20_state = ensure_v20_state


def generated_fish_name(species=None, variant="Normal", parents=None):
    """Generate a cozy hatchling name, with a small nod to parents/variant."""
    parents = [p for p in (parents or []) if p]
    if parents and random.random() < 0.28:
        # A tiny inheritance joke: borrow a syllable from a parent name.
        base = random.choice(parents).split()[0]
        stem = ''.join(ch for ch in base if ch.isalpha())[:5] or random.choice(NAME_PREFIXES)
        return (stem + random.choice(NAME_SUFFIXES)).title()[:24]
    if variant in ("Golden", "Moonlit", "Ancient") and random.random() < 0.20:
        return random.choice({"Golden": ["Sunny", "Goldie", "Marigold"], "Moonlit": ["Luna", "Moonbean", "Nyx"], "Ancient": ["Relic", "Fossil", "Oldscale"]}[variant])
    if random.random() < 0.08:
        return random.choice(NAME_RARE)
    return (random.choice(NAME_PREFIXES) + random.choice(NAME_SUFFIXES)).title()[:24]


def new_gene_set(species_name=None, variant="Normal"):
    species = species_by_name(species_name or "guppy")
    base_color = species.get("color", random.choice(GENE_COLOR_KEYS))
    if variant == "Golden":
        base_color = "gold"
    elif variant == "Moonlit":
        base_color = random.choice(["blue", "violet", "silver"])
    elif variant == "Ancient":
        base_color = random.choice(["silver", "teal", "violet"])
    elif variant == "Speckled":
        base_color = random.choice([base_color, "pink", "teal", "lime"])
    return {
        "color": base_color,
        "pattern": "speckled" if variant == "Speckled" else random.choice(GENE_PATTERNS),
        "fin": "veil" if variant in ("Moonlit", "Ancient") else random.choice(GENE_FINS),
        "body": random.choice(GENE_BODY),
        "temperament": random.choice(PERSONALITIES),
        "lifespan_bias": random.randint(-2500, 3500),
        "rare_affinity": round(random.uniform(0.85, 1.22), 2),
    }


def inherit_gene_value(parent_genes, key, fallback_values, mutation_chance=0.10):
    values = [g.get(key) for g in parent_genes if isinstance(g, dict) and g.get(key)]
    if values and random.random() > mutation_chance:
        return random.choice(values)
    return random.choice(fallback_values)


def inherited_gene_set(parents, species_name=None, variant="Normal"):
    parent_genes = [p.get("genes", {}) for p in parents if isinstance(p, dict)]
    if not parent_genes:
        return new_gene_set(species_name, variant)
    genes = {
        "color": inherit_gene_value(parent_genes, "color", GENE_COLOR_KEYS, 0.12),
        "pattern": inherit_gene_value(parent_genes, "pattern", GENE_PATTERNS, 0.14),
        "fin": inherit_gene_value(parent_genes, "fin", GENE_FINS, 0.12),
        "body": inherit_gene_value(parent_genes, "body", GENE_BODY, 0.12),
        "temperament": inherit_gene_value(parent_genes, "temperament", PERSONALITIES, 0.14),
        "lifespan_bias": int(sum(g.get("lifespan_bias", 0) for g in parent_genes) / max(1, len(parent_genes)) + random.randint(-900, 900)),
        "rare_affinity": round(sum(float(g.get("rare_affinity", 1.0)) for g in parent_genes) / max(1, len(parent_genes)) + random.uniform(-0.06, 0.06), 2),
    }
    # Variants visibly tug genes.
    if variant == "Golden":
        genes["color"] = "gold"
    elif variant == "Moonlit":
        genes["color"] = random.choice([genes["color"], "blue", "violet", "silver"])
        genes["fin"] = random.choice([genes["fin"], "flowing", "veil"])
    elif variant == "Ancient":
        genes["pattern"] = random.choice([genes["pattern"], "ringed fins", "masked face"])
    elif variant == "Speckled":
        genes["pattern"] = "speckled"
    return genes


def choose_variant_v21(rare_egg=False, parents=None):
    parents = parents or []
    inherited = [p.get("variant") for p in parents if isinstance(p, dict) and p.get("variant")]
    if inherited:
        # More explicit genetics: variants are fairly heritable, but mutations still happen.
        same = inherited[0] if len(set(inherited)) == 1 else random.choice(inherited)
        chance = 0.58 if len(set(inherited)) == 1 else 0.40
        affinity = sum(float(p.get("genes", {}).get("rare_affinity", 1.0)) for p in parents) / max(1, len(parents))
        if same in ("Golden", "Moonlit", "Ancient"):
            chance *= min(1.25, affinity)
        if random.random() < min(0.72, chance):
            return same
    return _old_choose_variant_v20(rare_egg=rare_egg, parents=parents)


def ensure_genetics_for_fish(fish):
    variant = fish.get("variant", "Normal")
    if not isinstance(fish.get("genes"), dict):
        fish["genes"] = new_gene_set(fish.get("species", "guppy"), variant)
    genes = fish["genes"]
    genes.setdefault("color", species_by_name(fish.get("species", "guppy")).get("color", "fish"))
    genes.setdefault("pattern", fish.get("markings", "plain"))
    genes.setdefault("fin", random.choice(GENE_FINS))
    genes.setdefault("body", random.choice(GENE_BODY))
    genes.setdefault("temperament", fish.get("personality", random.choice(PERSONALITIES)))
    genes.setdefault("lifespan_bias", 0)
    genes.setdefault("rare_affinity", 1.0)
    fish.setdefault("lineage_note", "wild / mystery egg")
    return fish


def ensure_genetics_for_egg(egg):
    variant = egg.get("variant", "Normal")
    if not isinstance(egg.get("genes"), dict):
        egg["genes"] = new_gene_set(egg.get("species", "guppy"), variant)
    egg.setdefault("name_seed", None)
    return egg


def make_fish(width, height, baby=False):
    fish = _old_make_fish_v20(width, height, baby=baby)
    fish.setdefault("variant", choose_variant_v21())
    fish["genes"] = new_gene_set(fish.get("species", "guppy"), fish.get("variant", "Normal"))
    fish["personality"] = fish["genes"].get("temperament", fish.get("personality", random.choice(PERSONALITIES)))
    fish["lifespan"] = max(MIN_LIFESPAN, min(MAX_LIFESPAN + 5000, int(fish.get("lifespan", random.randint(MIN_LIFESPAN, MAX_LIFESPAN)) + fish["genes"].get("lifespan_bias", 0))))
    return fish


def make_egg(width, height, species_name=None, rare_egg=False, tank=None):
    egg = _old_make_egg_v20(width, height, species_name=species_name, rare_egg=rare_egg, tank=tank)
    egg["variant"] = choose_variant_v21(rare_egg=rare_egg)
    egg["genes"] = new_gene_set(egg.get("species", species_name or "guppy"), egg.get("variant", "Normal"))
    egg["name_seed"] = generated_fish_name(egg.get("species"), egg.get("variant", "Normal"))
    return egg


def tank_to_data(tank, version=21):
    data = _old_tank_to_data_v20(tank, version=version)
    data["version"] = version
    return data


def apply_tank_data(tank, data):
    _old_apply_tank_data_v20(tank, data)
    for fish in getattr(tank, "fish", []):
        ensure_genetics_for_fish(fish)
    for egg in getattr(tank, "eggs", []):
        ensure_genetics_for_egg(egg)


def ensure_v21_state(tank):
    _old_ensure_v20_state(tank)
    for fish in getattr(tank, "fish", []):
        ensure_genetics_for_fish(fish)
    for egg in getattr(tank, "eggs", []):
        ensure_genetics_for_egg(egg)


def v21_update_eggs(self):
    if not hasattr(self, "eggs"):
        self.eggs = []
    hatched = []
    for egg in list(self.eggs):
        ensure_genetics_for_egg(egg)
        egg["age"] = egg.get("age", 0) + 1
        egg["y"] = self.height - 3
        if random.random() < 0.015:
            egg["x"] += random.choice([-1, 0, 1])
            egg["x"] = max(2, min(self.width - 5, int(egg.get("x", 3))))
        if egg["age"] >= egg.get("hatch_time", EGG_HATCH_MAX):
            baby = make_fish(self.width, self.height, baby=True)
            baby["species"] = egg.get("species", baby["species"])
            baby["variant"] = egg.get("variant", choose_variant_v21(rare_egg=egg.get("rare_egg", False)))
            baby["genes"] = dict(egg.get("genes", new_gene_set(baby["species"], baby["variant"])))
            baby["personality"] = baby["genes"].get("temperament", baby.get("personality", random.choice(PERSONALITIES)))
            baby["markings"] = baby["genes"].get("pattern", baby.get("markings", "plain"))
            baby["lifespan"] = max(MIN_LIFESPAN, min(MAX_LIFESPAN + 5000, int(baby.get("lifespan", random.randint(MIN_LIFESPAN, MAX_LIFESPAN)) + baby["genes"].get("lifespan_bias", 0))))
            baby["x"] = max(2, min(self.width - len(fish_symbol(baby)) - 2, int(egg.get("x", 3))))
            baby["y"] = max(2, min(self.height - 4, self.height - 4))
            baby["parents"] = list(egg.get("parents", []))
            baby["parent_names"] = list(egg.get("parent_names", []))
            baby["generation"] = int(egg.get("generation", 1))
            baby["hatched_day"] = self.day
            baby["last_stage"] = "fry"
            if egg.get("name_seed"):
                baby["name"] = egg["name_seed"]
            else:
                baby["name"] = generated_fish_name(baby["species"], baby["variant"], baby.get("parent_names", []))
            baby["lineage_note"] = "bred in tank" if baby.get("parents") else "mystery egg"
            self.fish.append(baby)
            for parent in self.fish:
                if parent.get("id") in baby["parents"]:
                    parent.setdefault("children", [])
                    if baby["name"] not in parent["children"]:
                        parent["children"].append(baby["name"])
            self.selected_fish_index = len(self.fish) - 1
            hatched.append(egg)
            self.hatch_count = getattr(self, "hatch_count", 0) + 1
            self.discover_species(baby["species"])
            discover_variant(self, baby["species"], baby.get("variant", "Normal"))
            record_hatch_stats(self, baby)
            rarity = RARITY_LABELS.get(species_rarity(baby["species"]), "Common")
            variant_text = "" if baby.get("variant") == "Normal" else f" {baby.get('variant')}"
            lineage = f" Parents: {' + '.join(baby['parent_names'])}." if baby.get("parent_names") else ""
            self.log(f"{baby['name']} hatched: a tiny{variant_text} {baby['species']}! ({rarity}){lineage}")
            if hasattr(self, "journal"):
                pass
    for egg in hatched:
        if egg in self.eggs:
            self.eggs.remove(egg)


def v21_maybe_breed_fish(self):
    if len(self.fish) + len(getattr(self, "eggs", [])) >= self.fish_capacity():
        return
    if len(self.fish) < 2 or self.tick < 1000:
        return
    base_chance = 0.0009
    if getattr(self, "water_quality", 70) >= 88:
        base_chance *= 1.35
    base_chance *= 1.0 + upgrade_level(self, "nursery") * 0.18
    if any(food.get("kind") == "golden" for food in self.food):
        base_chance *= 1.18
    if random.random() > base_chance:
        return
    happy_fish = [ensure_genetics_for_fish(f) for f in self.fish if f.get("hunger", 100) < 35 and self.age_stage(f) == "adult"]
    if len(happy_fish) >= 2:
        parent_a, parent_b = random.sample(happy_fish, 2)
        # Same-species parents strongly preserve species. Cross-species pairs produce one parent's species with a tiny surprise chance.
        if parent_a.get("species") == parent_b.get("species") or random.random() < 0.94:
            chosen_species = random.choice([parent_a.get("species"), parent_b.get("species")])
        else:
            chosen_species = choose_species_for_egg(self, rare_egg=False)
        inherited_variant = choose_variant_v21(parents=[parent_a, parent_b])
        egg = make_egg(self.width, self.height, chosen_species, tank=self)
        egg["variant"] = inherited_variant
        egg["genes"] = inherited_gene_set([parent_a, parent_b], chosen_species, inherited_variant)
        egg["name_seed"] = generated_fish_name(chosen_species, inherited_variant, [parent_a.get("name"), parent_b.get("name")])
        egg["x"] = int((parent_a.get("x", egg["x"]) + parent_b.get("x", egg["x"])) / 2)
        egg["y"] = self.height - 3
        egg["parents"] = [parent_a.get("id"), parent_b.get("id")]
        egg["parent_names"] = [parent_a.get("name", "Unknown"), parent_b.get("name", "Unknown")]
        egg["generation"] = max(int(parent_a.get("generation", 1)), int(parent_b.get("generation", 1))) + 1
        self.eggs.append(egg)
        var = "" if egg.get("variant") == "Normal" else f" {egg.get('variant')}"
        trait = egg.get("genes", {}).get("pattern", "plain")
        self.log(f"A small{var} {egg['species']} egg appears. Parents: {parent_a.get('name')} + {parent_b.get('name')}. Trait: {trait}.")


def ui_profile_lines(tank):
    lines = _old_ui_profile_lines_v20(tank)
    if tank.fish:
        fish = ensure_genetics_for_fish(tank.fish[tank.clamped_selected_index()])
        genes = fish.get("genes", {})
        genetics = (
            f"Genes: color {genes.get('color','?')} | pattern {genes.get('pattern','?')} | "
            f"fins {genes.get('fin','?')} | body {genes.get('body','?')}"
        )
        inherited = f"Temperament gene: {genes.get('temperament', fish.get('personality','?'))} | Rare affinity: {genes.get('rare_affinity',1.0)}x"
        lineage = f"Lineage: {fish.get('lineage_note','unknown')} | Gen {fish.get('generation', 1)}"
        # Put genetics near the top, after name/species lines if possible.
        insert_at = min(4, len(lines))
        lines[insert_at:insert_at] = [genetics, inherited, lineage]
    return lines


def ui_album_lines(tank):
    lines = _old_ui_album_lines_v20(tank)
    lines.insert(2, "v21: hatchlings receive generated names; breeding inherits variant, color, pattern, fins, temperament, and lifespan bias.")
    return lines


def fish_color_key_v21(fish):
    ensure_genetics_for_fish(fish)
    return fish.get("genes", {}).get("color") or species_by_name(fish.get("species", "guppy")).get("color", "fish")


def make_tank_grid_lines_v21(tank):
    # Mostly v20's renderer, with one key change: fish color can now come from genetics.
    # This duplicates the final fish draw pass safely by rebuilding through v20 then only if colors are off/on no change?
    # For simplicity and reliability, use v20 renderer. Genetic colors are shown in profile and offspring traits.
    return _old_make_tank_grid_lines_v20(tank)


def v21_handle_input(self):
    ensure_v21_state(self)
    v20_handle_input(self)


# Install v21 overrides.
choose_variant = choose_variant_v21
ensure_v20_state = ensure_v21_state
make_fish = make_fish
make_egg = make_egg
tank_to_data = tank_to_data
apply_tank_data = apply_tank_data
ui_profile_lines = ui_profile_lines
ui_album_lines = ui_album_lines
Fishtank.update_eggs = v21_update_eggs
Fishtank.maybe_breed_fish = v21_maybe_breed_fish
Fishtank.handle_input = v21_handle_input


# ============================================================
# v2.2 Tank customization and plant ecology pass
# ------------------------------------------------------------
# - D now opens a tank object manager.
# - Decorations can be selected and manually moved with Left/Right.
# - Plants can be selected, moved, trimmed, or sold.
# - Snails can be selected and sold.
# - Fish occasionally nibble tall plant tops so plants do not grow endlessly.
# ============================================================

APP_VERSION_LABEL = "v2.2"

_old_handle_v15_modal_input_v21 = handle_v15_modal_input
_old_modal_lines_v21 = modal_lines
_old_v20_handle_input_v21 = v20_handle_input
_old_v17_handle_tank_key_v21 = v17_handle_tank_key
_old_update_plants_v21 = Fishtank.update_plants


def object_menu_items(tank):
    return [
        f"Decorations ({len(getattr(tank, 'decorations', []))})",
        f"Plants ({len(getattr(tank, 'plants', []))})",
        f"Snails ({len(getattr(tank, 'snails', []))})",
        "Back",
    ]


def clamp_decor_position(tank, decor):
    decor["x"] = max(2, min(tank.width - 8, int(decor.get("x", 4))))
    decor["y"] = max(2, min(tank.height - 3, int(decor.get("y", tank.height - 4))))
    return decor


def clamp_plant_position(tank, plant):
    plant["x"] = max(2, min(tank.width - 3, int(plant.get("x", 4))))
    plant["height"] = max(2, min(9, int(plant.get("height", 4))))
    return plant


def clamp_snail_position(tank, snail):
    snail["x"] = max(2, min(tank.width - 5, int(snail.get("x", 4))))
    snail["y"] = tank.height - 3
    return snail


def selected_index(tank, attr, count):
    if count <= 0:
        setattr(tank, attr, 0)
        return 0
    idx = max(0, min(count - 1, int(getattr(tank, attr, 0))))
    setattr(tank, attr, idx)
    return idx


def object_modal_move_cursor(tank, key, attr, count):
    if count <= 0:
        setattr(tank, attr, 0)
        return
    cur = selected_index(tank, attr, count)
    if key == "up":
        cur = (cur - 1) % count
    elif key == "down":
        cur = (cur + 1) % count
    setattr(tank, attr, cur)


def sell_selected_decoration(tank):
    if not getattr(tank, "decorations", []):
        tank.log("There are no decorations to sell.")
        tank.mode = "object_menu"
        return
    idx = selected_index(tank, "decor_cursor", len(tank.decorations))
    removed = tank.decorations.pop(idx)
    kind = removed.get("kind", removed.get("name", "castle"))
    try:
        base_cost = int(decor_by_name(kind).get("cost", 15))
    except Exception:
        base_cost = 15
    refund = max(3, int(base_cost * 0.40))
    tank.shells += refund
    tank.log(f"Sold the {removed.get('name', kind)} for ${refund}.")
    selected_index(tank, "decor_cursor", len(tank.decorations))
    if not tank.decorations:
        tank.mode = "object_menu"


def sell_selected_plant(tank):
    if not getattr(tank, "plants", []):
        tank.log("There are no plants to sell.")
        tank.mode = "object_menu"
        return
    idx = selected_index(tank, "plant_cursor", len(tank.plants))
    plant = tank.plants.pop(idx)
    height = int(plant.get("height", 4))
    refund = max(2, min(8, 2 + height // 2))
    tank.shells += refund
    tank.log(f"Sold a tank plant for ${refund}.")
    selected_index(tank, "plant_cursor", len(tank.plants))
    if not tank.plants:
        tank.mode = "object_menu"


def sell_selected_snail(tank):
    if not getattr(tank, "snails", []):
        tank.log("There are no snails to sell.")
        tank.mode = "object_menu"
        return
    idx = selected_index(tank, "snail_cursor", len(tank.snails))
    snail = tank.snails.pop(idx)
    refund = 5 + min(5, int(snail.get("age", 0)) // 2500)
    tank.shells += refund
    tank.log(f"Sold {snail.get('name', 'a snail')} the snail for ${refund}.")
    selected_index(tank, "snail_cursor", len(tank.snails))
    if not tank.snails:
        tank.mode = "object_menu"


def v22_handle_modal_input(tank, key):
    ensure_v21_state(tank)
    mode = getattr(tank, "mode", "tank")

    if mode == "object_menu":
        items = object_menu_items(tank)
        tank.object_cursor = int(getattr(tank, "object_cursor", 0))
        object_modal_move_cursor(tank, key, "object_cursor", len(items))
        if key in {"1", "2", "3", "4"}:
            tank.object_cursor = int(key) - 1
            key = "\r"
        if key in _MENU_BACK:
            tank.mode = "tank"
        elif key in _MENU_ENTER:
            choice = selected_index(tank, "object_cursor", len(items))
            if choice == 0:
                tank.mode = "decor_select"
                tank.decor_cursor = selected_index(tank, "decor_cursor", len(getattr(tank, "decorations", [])))
            elif choice == 1:
                tank.mode = "plant_select"
                tank.plant_cursor = selected_index(tank, "plant_cursor", len(getattr(tank, "plants", [])))
            elif choice == 2:
                tank.mode = "snail_select"
                tank.snail_cursor = selected_index(tank, "snail_cursor", len(getattr(tank, "snails", [])))
            else:
                tank.mode = "tank"
        return

    if mode == "decor_select":
        if not getattr(tank, "decorations", []):
            tank.log("There are no decorations to manage.")
            tank.mode = "object_menu"
            return
        object_modal_move_cursor(tank, key, "decor_cursor", len(tank.decorations))
        idx = selected_index(tank, "decor_cursor", len(tank.decorations))
        decor = clamp_decor_position(tank, tank.decorations[idx])
        step = 1
        if key in {"left", "a"}:
            decor["x"] = max(2, int(decor.get("x", 4)) - step)
            tank.log(f"Moved {decor.get('name','decoration')} left.")
        elif key in {"right", "d"}:
            decor["x"] = min(tank.width - 8, int(decor.get("x", 4)) + step)
            tank.log(f"Moved {decor.get('name','decoration')} right.")
        elif key == "x":
            sell_selected_decoration(tank)
        elif key in _MENU_ENTER:
            tank.log("Use Left/Right to move this decoration, or X to sell it.")
        elif key in _MENU_BACK:
            tank.mode = "object_menu"
        return

    if mode == "plant_select":
        if not getattr(tank, "plants", []):
            tank.log("There are no plants to manage.")
            tank.mode = "object_menu"
            return
        object_modal_move_cursor(tank, key, "plant_cursor", len(tank.plants))
        idx = selected_index(tank, "plant_cursor", len(tank.plants))
        plant = clamp_plant_position(tank, tank.plants[idx])
        if key in {"left", "a"}:
            plant["x"] = max(2, int(plant.get("x", 4)) - 1)
            tank.log("Moved the selected plant left.")
        elif key in {"right", "d"}:
            plant["x"] = min(tank.width - 3, int(plant.get("x", 4)) + 1)
            tank.log("Moved the selected plant right.")
        elif key in _MENU_ENTER or key == "t":
            if int(plant.get("height", 4)) > 2:
                plant["height"] = int(plant.get("height", 4)) - 1
                plant["growth"] = 0
                tank.log("You trim the top of the selected plant.")
            else:
                tank.log("That plant is already trimmed short.")
        elif key == "x":
            sell_selected_plant(tank)
        elif key in _MENU_BACK:
            tank.mode = "object_menu"
        return

    if mode == "snail_select":
        if not getattr(tank, "snails", []):
            tank.log("There are no snails to manage.")
            tank.mode = "object_menu"
            return
        object_modal_move_cursor(tank, key, "snail_cursor", len(tank.snails))
        idx = selected_index(tank, "snail_cursor", len(tank.snails))
        snail = clamp_snail_position(tank, tank.snails[idx])
        if key in {"left", "a"}:
            snail["x"] = max(2, int(snail.get("x", 4)) - 1)
            tank.log(f"Moved {snail.get('name','the snail')} left.")
        elif key in {"right", "d"}:
            snail["x"] = min(tank.width - 5, int(snail.get("x", 4)) + 1)
            tank.log(f"Moved {snail.get('name','the snail')} right.")
        elif key in _MENU_ENTER or key == "x":
            sell_selected_snail(tank)
        elif key in _MENU_BACK:
            tank.mode = "object_menu"
        return

    _old_handle_v15_modal_input_v21(tank, key)


def v22_modal_lines(tank):
    mode = getattr(tank, "mode", "tank")
    if mode == "object_menu":
        items = object_menu_items(tank)
        cur = selected_index(tank, "object_cursor", len(items))
        lines = [f"{'> ' if i == cur else '  '}{i+1}. {item}" for i, item in enumerate(items)]
        lines += ["", "Choose a category. Esc/Q/Left returns to the tank."]
        return "Tank Objects", lines

    if mode == "decor_select":
        if not getattr(tank, "decorations", []):
            return "Decorations", ["No decorations yet.", "Buy some in the shop, then manage them here."]
        cur = selected_index(tank, "decor_cursor", len(tank.decorations))
        lines = []
        for i, decor in enumerate(tank.decorations):
            kind = decor.get("kind", decor.get("name", "decoration"))
            lines.append(f"{'> ' if i == cur else '  '}{decor.get('name', kind):20} x={int(decor.get('x', 0)):2} y={int(decor.get('y', tank.height-4)):2}")
        lines += ["", "Up/Down select. Left/Right move. X sell. Esc back."]
        return "Place Decorations", lines

    if mode == "plant_select":
        if not getattr(tank, "plants", []):
            return "Plants", ["No plants yet.", "Buy plants in the shop, then place or trim them here."]
        cur = selected_index(tank, "plant_cursor", len(tank.plants))
        lines = []
        for i, plant in enumerate(tank.plants):
            lines.append(f"{'> ' if i == cur else '  '}Plant {i+1:<2} x={int(plant.get('x', 0)):2} height={int(plant.get('height', 0))}")
        lines += ["", "Up/Down select. Left/Right move. Enter/T trim. X sell. Esc back."]
        return "Place Plants", lines

    if mode == "snail_select":
        if not getattr(tank, "snails", []):
            return "Snails", ["No snails in the tank.", "Buy snails in the shop if you want cleanup helpers."]
        cur = selected_index(tank, "snail_cursor", len(tank.snails))
        lines = []
        for i, snail in enumerate(tank.snails):
            age_days = int(snail.get("age", 0)) / 600
            lines.append(f"{'> ' if i == cur else '  '}{snail.get('name','Snail'):16} x={int(snail.get('x',0)):2} age={age_days:.1f}d")
        lines += ["", "Up/Down select. Left/Right nudge. Enter/X sell. Esc back."]
        return "Snails", lines

    return _old_modal_lines_v21(tank)


def compact_help_lines_v22():
    return [
        "F feed  G food  W clean  A egg  B bubbles",
        "N name  I profile  X sell fish  D objects  O shop",
        "J album  K history  H help  E saves  T settings",
        "P pause  C color  V screen  S save  L load  Q quit",
        "Tab panel  Enter collapse  Esc menu",
    ]


def v22_handle_tank_key(self, key):
    # Same as v17, except D now opens the broader object manager.
    if key == "d":
        self.mode = "object_menu"
        self.object_cursor = int(getattr(self, "object_cursor", 0))
        return
    return _old_v17_handle_tank_key_v21(self, key)


def v22_handle_input(self):
    ensure_v21_state(self)
    key = get_key()
    if not key:
        return
    mode = getattr(self, "mode", "tank")
    if mode != "tank":
        v22_handle_modal_input(self, key)
        return

    # Keep v20 dashboard controls intact.
    if key == "\t":
        idx = PANEL_ORDER.index(getattr(self, "panel_focus", "status"))
        self.panel_focus = PANEL_ORDER[(idx + 1) % len(PANEL_ORDER)]
        return
    if key in {"\r", "\n"}:
        focus = getattr(self, "panel_focus", "status")
        self.collapsed_panels[focus] = not self.collapsed_panels.get(focus, False)
        return

    v22_handle_tank_key(self, key)


def fish_nibble_plant_tops(tank):
    plants = getattr(tank, "plants", [])
    fish_list = getattr(tank, "fish", [])
    if not plants or not fish_list:
        return
    # Keep it occasional. Tall plants are more likely to be nibbled.
    for plant in plants:
        height = int(plant.get("height", 4))
        if height < 6:
            continue
        if random.random() > 0.0018 * max(1, height - 4):
            continue
        top_y = tank.height - 2 - (height - 1)
        nearby = [
            f for f in fish_list
            if abs(int(f.get("x", 0)) - int(plant.get("x", 0))) <= 4
            and abs(int(f.get("y", 0)) - top_y) <= 3
            and tank.age_stage(f) in {"young", "adult", "elder"}
        ]
        # If nobody is right on top of the plant, an algae/grazing fish can still do it sometimes.
        if not nearby and random.random() < 0.35:
            nearby = [f for f in fish_list if tank.age_stage(f) in {"young", "adult", "elder"}]
        if nearby:
            fish = random.choice(nearby)
            plant["height"] = max(2, height - 1)
            plant["growth"] = 0
            fish["hunger"] = max(0, int(fish.get("hunger", 0)) - random.randint(3, 8))
            if random.random() < 0.45:
                tank.log(f"{fish.get('name', 'A fish')} nibbles the top of a plant.")


def v22_update_plants(self):
    _old_update_plants_v21(self)
    fish_nibble_plant_tops(self)


def v22_buy_plant(self):
    if self.spend(8):
        plant = make_plant(self.width, self.height)
        plant["x"] = random.randint(4, max(4, self.width - 5))
        self.plants.append(plant)
        self.log("A new plant takes root. Use D > Plants to place or trim it.")


def v22_buy_decoration(self):
    if self.spend(15):
        decor = random.choice(DECOR_TYPES)
        item = make_decoration(self.width, self.height, decor)
        item["x"] = random.randint(4, max(4, self.width - 10))
        self.decorations.append(item)
        self.log(f"A {decor['name']} is placed. Use D > Decorations to move it.")


def v22_buy_snail(self):
    if self.spend(10):
        snail = make_snail(self.width, self.height)
        self.snails.append(snail)
        self.log(f"{snail['name']} the snail joins. Use D > Snails if you want to sell it later.")


# Install v22 overrides.
handle_v15_modal_input = v22_handle_modal_input
modal_lines = v22_modal_lines
compact_help_lines_v20 = compact_help_lines_v22
Fishtank.handle_input = v22_handle_input
Fishtank.update_plants = v22_update_plants
Fishtank.buy_plant = v22_buy_plant
Fishtank.buy_decoration = v22_buy_decoration
Fishtank.buy_snail = v22_buy_snail
main = v16_main


# ============================================================
# v24 decoration placement / tank expansion polish
# ------------------------------------------------------------
# - Decoration bounds now use the actual sprite width instead of a hardcoded
#   old-tank margin.
# - Multi-line decorations are drawn as a single anchored sprite so rows no
#   longer shift independently near the right edge.
# - Decorations are bottom-aligned correctly after tank height changes.
# - New decorations can spawn across the full upgraded tank area.
# - D > Decorations now supports R to jump the selected decoration to a random
#   valid spot, which makes large upgraded tanks easier to decorate.
# ============================================================
APP_VERSION_LABEL = "v24"

_old_v22_make_decoration = make_decoration
_old_v22_buy_decoration = Fishtank.buy_decoration
_old_v22_buy_upgrade = Fishtank.buy_upgrade
_old_v22_modal_lines = modal_lines
_old_v22_handle_modal_input = handle_v15_modal_input


def decor_sprite_for(decor_or_kind):
    """Return glyph lines for a decoration safely."""
    try:
        if isinstance(decor_or_kind, dict):
            kind = decor_or_kind.get("kind", decor_or_kind.get("name", "castle"))
        else:
            kind = decor_or_kind or "castle"
        return decor_by_name(kind).get("glyphs", ["??"])
    except Exception:
        return ["??"]


def sprite_width(lines):
    return max(1, max(len(str(line)) for line in (lines or [""])))


def sprite_height(lines):
    return max(1, len(lines or [""]))


def decoration_bounds(tank, decor):
    """Return safe x/y ranges for a bottom-placed decoration."""
    lines = decor_sprite_for(decor)
    sw = sprite_width(lines)
    sh = sprite_height(lines)
    min_x = 2
    max_x = max(min_x, int(tank.width) - sw - 1)
    # Bottom align so the last sprite row sits on the gravel row, not the border.
    floor_y = int(tank.height) - 2
    min_y = 1
    max_y = max(min_y, floor_y - sh + 1)
    return min_x, max_x, min_y, max_y


def clamp_decor_position_v24(tank, decor):
    min_x, max_x, min_y, max_y = decoration_bounds(tank, decor)
    decor["x"] = max(min_x, min(max_x, int(decor.get("x", min_x))))
    # Decorations are floor objects in this version, so height changes should
    # keep them visually seated on the bottom of the tank.
    decor["y"] = max_y
    return decor


# Replace the older hardcoded clamp helper globally so v22 menus and future
# code paths all share the same bounds.
clamp_decor_position = clamp_decor_position_v24


def draw_multiline_sprite(grid, x, y, lines, color="decor"):
    """Draw a multi-line sprite without row-by-row right-edge shifting.

    Earlier versions bounded each row independently. That made decorations look
    broken near the right edge of an upgraded tank because short/long rows could
    slide to different x positions. This anchors the whole sprite first.
    """
    if not grid:
        return
    width = len(grid[0])
    height = len(grid)
    lines = [str(line) for line in (lines or [])]
    if not lines:
        return
    sw = sprite_width(lines)
    sh = sprite_height(lines)
    x = max(1, min(max(1, width - sw - 1), int(x)))
    y = max(1, min(max(1, height - sh - 1), int(y)))
    for row_offset, line in enumerate(lines):
        safe_draw_text(grid, x, y + row_offset, line, color)


def make_decoration(width, height, decor_type=None):
    decor_def = decor_type or random.choice(DECOR_TYPES)
    lines = decor_def.get("glyphs", ["??"])
    sw = sprite_width(lines)
    sh = sprite_height(lines)
    max_x = max(2, int(width) - sw - 2)
    return {
        "id": rand_id("decor"),
        "name": decor_def["name"],
        "x": random.randint(2, max_x),
        "y": max(1, int(height) - sh - 1),
        "kind": decor_def["name"],
    }


def full_width_decor_x(tank, decor):
    min_x, max_x, _, _ = decoration_bounds(tank, decor)
    return random.randint(min_x, max_x)


def v24_buy_decoration(self):
    if self.spend(15):
        decor_def = random.choice(DECOR_TYPES)
        item = make_decoration(self.width, self.height, decor_def)
        self.decorations.append(item)
        self.log(f"A {decor_def['name']} is placed. Use D > Decorations to move it across the full tank.")


def v24_clamp_world(self):
    # This intentionally replaces the older clamp_world instead of calling it,
    # because the older version hard-clipped decorations to width-8 every time.
    for egg in getattr(self, "eggs", []):
        egg["x"] = max(2, min(self.width - 5, int(egg.get("x", 3))))
        egg["y"] = self.height - 3
    for f in getattr(self, "fish", []):
        symbol = fish_symbol(f)
        max_x = max(1, self.width - len(symbol) - 1)
        f["x"] = max(1, min(max_x, int(f.get("x", 2))))
        f["y"] = max(2, min(self.height - 4, int(f.get("y", 2))))
    for p in getattr(self, "plants", []):
        p["x"] = max(2, min(self.width - 3, int(p.get("x", 3))))
        p["height"] = max(2, min(9, int(p.get("height", 4))))
    for r in getattr(self, "rocks", []):
        rw = int(r.get("width", 3))
        r["x"] = max(2, min(max(2, self.width - rw - 1), int(r.get("x", 3))))
    for s in getattr(self, "snails", []):
        s["x"] = max(2, min(self.width - 4, int(s.get("x", 2))))
        s["y"] = self.height - 3
    for d in getattr(self, "decorations", []):
        clamp_decor_position_v24(self, d)
    for b in getattr(self, "bubbles", []):
        b["x"] = max(2, min(self.width - 3, int(b.get("x", 2))))
        b["y"] = max(1, min(self.height - 3, int(b.get("y", self.height - 3))))
    for food in getattr(self, "food", []):
        food["x"] = max(2, min(self.width - 3, int(food.get("x", 2))))
        food["y"] = max(2, min(self.height - 3, int(food.get("y", 2))))


def seed_expanded_floor(self, old_width, new_width):
    """Add a little visual life in newly unlocked width without moving user decor."""
    if new_width <= old_width + 3:
        return
    # Add a couple of rocks in the newly visible region so expansion feels real.
    added = 0
    for _ in range(2):
        if random.random() < 0.75:
            rock = make_rock(new_width)
            rock["x"] = random.randint(max(3, old_width - 2), max(3, new_width - int(rock.get("width", 3)) - 2))
            self.rocks.append(rock)
            added += 1
    if added:
        self.log("New gravel and rocks settle into the expanded tank area.")


def v24_buy_upgrade(self, name):
    old_width = int(getattr(self, "width", DEFAULT_WIDTH))
    before = upgrade_level(self, name)
    _old_v22_buy_upgrade(self, name)
    after = upgrade_level(self, name)
    if name == "tank" and after > before:
        # v15/v20 already resize; this ensures new decoration-safe clamping and
        # gives the extended region floor detail.
        new_w, new_h = get_terminal_size_for_tank(self)
        self.width, self.height = new_w, new_h
        seed_expanded_floor(self, old_width, self.width)
        self.clamp_world()
        self.log("Decorations now use the full upgraded tank width.")


def v24_handle_modal_input(tank, key):
    mode = getattr(tank, "mode", "tank")
    if mode == "decor_select":
        if not getattr(tank, "decorations", []):
            tank.log("There are no decorations to manage.")
            tank.mode = "object_menu"
            return
        object_modal_move_cursor(tank, key, "decor_cursor", len(tank.decorations))
        idx = selected_index(tank, "decor_cursor", len(tank.decorations))
        decor = clamp_decor_position_v24(tank, tank.decorations[idx])
        min_x, max_x, _, _ = decoration_bounds(tank, decor)
        if key in {"left", "a"}:
            decor["x"] = max(min_x, int(decor.get("x", min_x)) - 1)
            tank.log(f"Moved {decor.get('name','decoration')} left.")
        elif key in {"right", "d"}:
            decor["x"] = min(max_x, int(decor.get("x", min_x)) + 1)
            tank.log(f"Moved {decor.get('name','decoration')} right.")
        elif key == "r":
            decor["x"] = full_width_decor_x(tank, decor)
            clamp_decor_position_v24(tank, decor)
            tank.log(f"Moved {decor.get('name','decoration')} to a random open spot.")
        elif key == "x":
            sell_selected_decoration(tank)
        elif key in _MENU_ENTER:
            tank.log("Use Left/Right to move, R to jump to an open spot, or X to sell.")
        elif key in _MENU_BACK:
            tank.mode = "object_menu"
        return
    _old_v22_handle_modal_input(tank, key)


def v24_modal_lines(tank):
    if getattr(tank, "mode", "tank") == "decor_select":
        if not getattr(tank, "decorations", []):
            return "Decorations", ["No decorations yet.", "Buy some in the shop, then manage them here."]
        cur = selected_index(tank, "decor_cursor", len(tank.decorations))
        lines = []
        for i, decor in enumerate(tank.decorations):
            decor = clamp_decor_position_v24(tank, decor)
            kind = decor.get("kind", decor.get("name", "decoration"))
            min_x, max_x, _, _ = decoration_bounds(tank, decor)
            lines.append(
                f"{'> ' if i == cur else '  '}{decor.get('name', kind):20} "
                f"x={int(decor.get('x', 0)):2}/{max_x:<2} y={int(decor.get('y', tank.height-4)):2}"
            )
        lines += ["", "Up/Down select. Left/Right move. R random spot. X sell. Esc back."]
        return "Place Decorations", lines
    return _old_v22_modal_lines(tank)


# Install v24 overrides.
Fishtank.buy_decoration = v24_buy_decoration
Fishtank.buy_upgrade = v24_buy_upgrade
Fishtank.clamp_world = v24_clamp_world
handle_v15_modal_input = v24_handle_modal_input
modal_lines = v24_modal_lines
main = v16_main

# ============================================================
# v2.5 Expanded-tank coordinate stability patch
# ------------------------------------------------------------
# v24 fixed decoration placement bounds, but the inherited base update loop
# still recalculated the tank size with the original non-upgrade-aware helper
# every few seconds. That shrank self.width back to the starter width and then
# clamp_world snapped moved decorations/plants back into the old boundary.
# This update loop keeps all periodic resizing upgrade-aware.
# ============================================================

APP_VERSION_LABEL = "v2.5"


def v25_update(self):
    ensure_v21_state(self)
    prev_day = getattr(self, "day", 1)

    # Keep title/menu background lightly animated without aging the aquarium.
    if getattr(self, "mode", "tank") == "main_menu":
        if not getattr(self, "paused", False):
            self.tick += 1
            if getattr(self, "saved_notice", 0) > 0:
                self.saved_notice -= 1
            if self.tick % 250 == 0:
                self.width, self.height = get_terminal_size_for_tank(self)
                self.clamp_world()
            self.update_bubbles()
            self.update_visitors()
        return

    if getattr(self, "paused", False):
        return

    self.tick += 1
    if getattr(self, "saved_notice", 0) > 0:
        self.saved_notice -= 1

    if self.tick % 600 == 0:
        self.day += 1
        self.shells += random.randint(3, 7)
        self.log(f"Day {self.day} begins. You find a few dollars near the tank.")
        if getattr(self, "autosave", False):
            self.save()

    # Critical fix: use the upgrade-aware tank sizing helper here. The old base
    # loop called get_terminal_size(), which ignored Roomy Tank upgrades.
    if self.tick % 250 == 0:
        self.width, self.height = get_terminal_size_for_tank(self)
        self.clamp_world()

    self.update_eggs()
    self.update_fish()
    self.update_bubbles()
    self.update_food()
    self.update_water_quality()
    self.update_upgrades()
    self.update_plants()
    self.update_snails()
    self.update_visitors()
    self.random_events()

    if getattr(self, "day", 1) != prev_day:
        if self.day - getattr(self, "market_day", 0) >= 3:
            refresh_market_requests(self)

    if getattr(self, "screensaver", False) and getattr(self, "fish", []) and self.tick % 220 == 0:
        fish = random.choice(self.fish)
        self.last_screensaver_note = f"{fish.get('name', 'A fish')} drifts through the {THEMES[getattr(self, 'theme_index', 0)]} water..."


def clamp_plant_position_v25(tank, plant):
    # Mirrors the upgraded tank width, so manually placed plants in expanded
    # space remain there after periodic clamping/resizing.
    plant["x"] = max(2, min(int(tank.width) - 3, int(plant.get("x", 4))))
    plant["height"] = max(2, min(9, int(plant.get("height", 4))))
    return plant


clamp_plant_position = clamp_plant_position_v25
Fishtank.update = v25_update


# ============================================================
# v2.6 Shop placement/load-width consistency patch
# ------------------------------------------------------------
# v25 fixed the periodic resize clamp, but a loaded upgraded tank could still
# start the session with starter-width coordinates until the next resize tick.
# If the player bought a decoration before that tick, the purchase path used
# the stale starter width. This patch forces upgrade-aware dimensions before
# shop placement and immediately after loading save data.
# ============================================================

APP_VERSION_LABEL = "v2.6"

_old_v25_load = Fishtank.load
_old_apply_tank_data_v21 = apply_tank_data
_old_v24_buy_decoration_v25 = Fishtank.buy_decoration
_old_v22_buy_plant_v25 = Fishtank.buy_plant
_old_v22_buy_snail_v25 = Fishtank.buy_snail
_old_add_egg_v25 = Fishtank.add_egg


def refresh_upgrade_dimensions(tank):
    """Synchronize tank width/height with current tank upgrades and terminal."""
    try:
        tank.width, tank.height = get_terminal_size_for_tank(tank)
        if hasattr(tank, "clamp_world"):
            tank.clamp_world()
    except Exception:
        # Keep the app playable even if a weird terminal reports bad dimensions.
        pass


def v26_load(self):
    _old_v25_load(self)
    refresh_upgrade_dimensions(self)


def apply_tank_data(tank, data):
    _old_apply_tank_data_v21(tank, data)
    refresh_upgrade_dimensions(tank)


def v26_buy_decoration(self):
    refresh_upgrade_dimensions(self)
    if self.spend(15):
        decor_def = random.choice(DECOR_TYPES)
        item = make_decoration(self.width, self.height, decor_def)
        # Explicitly use the full upgraded valid x-range. This avoids any stale
        # placement bounds and makes newly bought decorations able to appear in
        # the expanded area immediately after loading or upgrading.
        item["x"] = full_width_decor_x(self, item)
        clamp_decor_position_v24(self, item)
        self.decorations.append(item)
        self.log(f"A {decor_def['name']} is placed somewhere in the full tank. Use D > Decorations to move it.")


def v26_buy_plant(self):
    refresh_upgrade_dimensions(self)
    if self.spend(8):
        plant = make_plant(self.width, self.height)
        plant["x"] = random.randint(4, max(4, int(self.width) - 5))
        clamp_plant_position_v25(self, plant)
        self.plants.append(plant)
        self.log("A new plant takes root in the tank.")


def v26_buy_snail(self):
    refresh_upgrade_dimensions(self)
    if self.spend(12):
        snail = make_snail(self.width, self.height)
        snail["x"] = random.randint(3, max(3, int(self.width) - 5))
        clamp_snail_position(self, snail)
        self.snails.append(snail)
        self.log("A snail joins the cleanup crew.")


def v26_add_egg(self, free=False, rare_egg=False):
    refresh_upgrade_dimensions(self)
    return _old_add_egg_v25(self, free=free, rare_egg=rare_egg)


Fishtank.load = v26_load
Fishtank.buy_decoration = v26_buy_decoration
Fishtank.buy_plant = v26_buy_plant
Fishtank.buy_snail = v26_buy_snail
Fishtank.add_egg = v26_add_egg



# ============================================================
# v2.7 Save/load expanded-object coordinate patch
# ------------------------------------------------------------
# v26 fixed most live placement paths, but some reload paths could still clamp
# decorations/plants using starter dimensions during the load sequence. This
# patch makes save/load explicitly upgrade-aware before any object validation.
# ============================================================

APP_VERSION_LABEL = "v2.7"

_old_v26_save = Fishtank.save
_old_v26_load = Fishtank.load
_old_v26_apply_tank_data = apply_tank_data
_old_v26_save_to_slot = save_to_slot
_old_v26_load_from_slot = load_from_slot


def set_upgrade_dimensions_without_clamp(tank):
    """Apply the current upgrade-aware tank dimensions without moving objects."""
    try:
        tank.width, tank.height = get_terminal_size_for_tank(tank)
    except Exception:
        # Fall back to the current dimensions if the terminal reports something odd.
        tank.width = int(getattr(tank, "width", DEFAULT_WIDTH))
        tank.height = int(getattr(tank, "height", DEFAULT_HEIGHT))


def refresh_upgrade_dimensions_preserving_saved_bounds(tank):
    """Upgrade-aware refresh used after load/save data has been assigned."""
    set_upgrade_dimensions_without_clamp(tank)
    if hasattr(tank, "clamp_world"):
        tank.clamp_world()


def apply_tank_data(tank, data):
    """Load save data with upgrades applied before object positions are clamped.

    The important detail is order:
      1. read upgrades from the save
      2. calculate the upgraded tank width/height
      3. assign saved decorations/plants/snails/fish
      4. clamp them against the upgraded dimensions
    """
    # Apply upgrades first so all later coordinate handling sees the expanded tank.
    saved_upgrades = data.get("upgrades", getattr(tank, "upgrades", {"tank": 0, "filter": 0, "bubbler": 0, "nursery": 0, "feeder": 0}))
    tank.upgrades = dict(saved_upgrades)
    for _u in UPGRADE_CATALOG:
        tank.upgrades.setdefault(_u, 0)

    # Make width/height upgrade-aware before the older loader creates bubbles or clamps anything.
    set_upgrade_dimensions_without_clamp(tank)

    # Now let the previous loader populate every field.
    _old_v26_apply_tank_data(tank, data)

    # Final authoritative pass. This is the only point where positions should be validated.
    refresh_upgrade_dimensions_preserving_saved_bounds(tank)


def v27_save(self):
    # Ensure the saved file captures coordinates in the upgraded coordinate space.
    refresh_upgrade_dimensions_preserving_saved_bounds(self)
    data = tank_to_data(self)
    data["tank_width_at_save"] = int(getattr(self, "width", DEFAULT_WIDTH))
    data["tank_height_at_save"] = int(getattr(self, "height", DEFAULT_HEIGHT))
    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        SAVE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.saved_notice = 35
        self.log(f"The tank is saved to {SAVE_FILE}.")
    except Exception as exc:
        try:
            fallback = Path.home() / SAVE_FILENAME
            fallback.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.saved_notice = 35
            self.log(f"The tank is saved to {fallback}.")
        except Exception:
            self.log(f"Save failed: {exc}")


def v27_load(self):
    load_path = SAVE_FILE
    if not load_path.exists() and LEGACY_SAVE_FILE.exists() and LEGACY_SAVE_FILE.is_file():
        load_path = LEGACY_SAVE_FILE
    if not load_path.exists():
        self.log("No save file exists yet.")
        return
    try:
        data = json.loads(load_path.read_text(encoding="utf-8"))
        apply_tank_data(self, data)
        self.log("The saved tank bubbles back to life.")
    except Exception as exc:
        self.log(f"Load failed: {exc}")


def save_to_slot(tank, slot):
    try:
        refresh_upgrade_dimensions_preserving_saved_bounds(tank)
        data = tank_to_data(tank)
        data["tank_width_at_save"] = int(getattr(tank, "width", DEFAULT_WIDTH))
        data["tank_height_at_save"] = int(getattr(tank, "height", DEFAULT_HEIGHT))
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        save_slot_file(slot).write_text(json.dumps(data, indent=2), encoding="utf-8")
        tank.log(f"Saved tank to slot {slot}.")
    except Exception as exc:
        tank.log(f"Slot save failed: {exc}")


def load_from_slot(tank, slot):
    path = save_slot_file(slot)
    if not path.exists():
        tank.log(f"Slot {slot} is empty.")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        apply_tank_data(tank, data)
        tank.log(f"Loaded tank from slot {slot}.")
    except Exception as exc:
        tank.log(f"Slot load failed: {exc}")


Fishtank.save = v27_save
Fishtank.load = v27_load



# ============================================================
# v2.8 First-launch window-size preservation patch
# ------------------------------------------------------------
# Some terminals report a small width for the first few frames when an app is
# launched or when a packaged .exe window is still settling. Older load/clamp
# code used that temporary visible width as the hard object boundary. That made
# decorations/plants saved in the upgraded area snap back into the starter area
# only on first launch. v28 separates "logical tank width" from "visible tank
# width": objects are clamped to the upgraded tank's intended design width, and
# rendering simply clips anything that is temporarily off-screen until the
# window is wide enough again.
# ============================================================

APP_VERSION_LABEL = "v2.8"


def logical_tank_width(tank=None):
    """Return the upgraded design width independent of the current terminal."""
    level = upgrade_level(tank, "tank") if tank is not None else 0
    return max(40, min(DEFAULT_WIDTH + level * 8, 112))


def logical_tank_height(tank=None):
    """Return the upgraded design height independent of the current terminal."""
    level = upgrade_level(tank, "tank") if tank is not None else 0
    return max(14, min(DEFAULT_HEIGHT + min(level, 3) * 2, 32))


def decoration_bounds(tank, decor):
    """Return safe decoration bounds using logical width, not startup viewport."""
    lines = decor_sprite_for(decor)
    sw = sprite_width(lines)
    sh = sprite_height(lines)
    min_x = 2
    # Critical v28 detail: use the upgraded logical width for x bounds so a
    # momentarily narrow startup window does not rewrite saved placement.
    max_x = max(min_x, logical_tank_width(tank) - sw - 1)
    floor_y = int(getattr(tank, "height", DEFAULT_HEIGHT)) - 2
    min_y = 1
    max_y = max(min_y, floor_y - sh + 1)
    return min_x, max_x, min_y, max_y


def clamp_decor_position_v28(tank, decor):
    min_x, max_x, min_y, max_y = decoration_bounds(tank, decor)
    decor["x"] = max(min_x, min(max_x, int(decor.get("x", min_x))))
    decor["y"] = max_y
    return decor


clamp_decor_position = clamp_decor_position_v28
clamp_decor_position_v24 = clamp_decor_position_v28


def full_width_decor_x(tank, decor):
    min_x, max_x, _, _ = decoration_bounds(tank, decor)
    return random.randint(min_x, max_x)


def clamp_plant_position_v28(tank, plant):
    plant["x"] = max(2, min(logical_tank_width(tank) - 3, int(plant.get("x", 4))))
    plant["height"] = max(2, min(9, int(plant.get("height", 4))))
    return plant


clamp_plant_position = clamp_plant_position_v28
clamp_plant_position_v25 = clamp_plant_position_v28


def clamp_snail_position_v28(tank, snail):
    snail["x"] = max(2, min(logical_tank_width(tank) - 5, int(snail.get("x", 4))))
    snail["y"] = int(getattr(tank, "height", DEFAULT_HEIGHT)) - 3
    return snail


clamp_snail_position = clamp_snail_position_v28


def v28_clamp_world(self):
    # Fish, eggs, food, bubbles, and visitors are active animation objects, so
    # they stay clamped to the currently visible water. User-placed floor objects
    # use logical upgraded bounds to preserve off-screen/expanded placements.
    for egg in getattr(self, "eggs", []):
        egg["x"] = max(2, min(int(getattr(self, "width", DEFAULT_WIDTH)) - 5, int(egg.get("x", 3))))
        egg["y"] = int(getattr(self, "height", DEFAULT_HEIGHT)) - 3
    for f in getattr(self, "fish", []):
        symbol = fish_symbol(f)
        max_x = max(1, int(getattr(self, "width", DEFAULT_WIDTH)) - len(symbol) - 1)
        f["x"] = max(1, min(max_x, int(f.get("x", 2))))
        f["y"] = max(2, min(int(getattr(self, "height", DEFAULT_HEIGHT)) - 4, int(f.get("y", 2))))
    for p in getattr(self, "plants", []):
        clamp_plant_position_v28(self, p)
    for r in getattr(self, "rocks", []):
        rw = int(r.get("width", 3))
        r["x"] = max(2, min(max(2, logical_tank_width(self) - rw - 1), int(r.get("x", 3))))
    for s in getattr(self, "snails", []):
        clamp_snail_position_v28(self, s)
    for d in getattr(self, "decorations", []):
        clamp_decor_position_v28(self, d)
    for b in getattr(self, "bubbles", []):
        b["x"] = max(2, min(int(getattr(self, "width", DEFAULT_WIDTH)) - 3, int(b.get("x", 2))))
        b["y"] = max(1, min(int(getattr(self, "height", DEFAULT_HEIGHT)) - 3, int(b.get("y", int(getattr(self, "height", DEFAULT_HEIGHT)) - 3))))
    for food in getattr(self, "food", []):
        food["x"] = max(2, min(int(getattr(self, "width", DEFAULT_WIDTH)) - 3, int(food.get("x", 2))))
        food["y"] = max(2, min(int(getattr(self, "height", DEFAULT_HEIGHT)) - 3, int(food.get("y", 2))))


Fishtank.clamp_world = v28_clamp_world


def set_upgrade_dimensions_without_clamp(tank):
    """Refresh visible size only; never shrink logical saved object bounds."""
    try:
        tank.width, tank.height = get_terminal_size_for_tank(tank)
    except Exception:
        tank.width = int(getattr(tank, "width", DEFAULT_WIDTH))
        tank.height = int(getattr(tank, "height", DEFAULT_HEIGHT))


def refresh_upgrade_dimensions_preserving_saved_bounds(tank):
    set_upgrade_dimensions_without_clamp(tank)
    if hasattr(tank, "clamp_world"):
        tank.clamp_world()


def v28_buy_decoration(self):
    refresh_upgrade_dimensions_preserving_saved_bounds(self)
    if self.spend(15):
        decor_def = random.choice(DECOR_TYPES)
        item = make_decoration(logical_tank_width(self), self.height, decor_def)
        item["x"] = full_width_decor_x(self, item)
        clamp_decor_position_v28(self, item)
        self.decorations.append(item)
        self.log(f"A {decor_def['name']} is placed somewhere in the full tank. Use D > Decorations to move it.")


def v28_buy_plant(self):
    refresh_upgrade_dimensions_preserving_saved_bounds(self)
    if self.spend(8):
        plant = make_plant(logical_tank_width(self), self.height)
        plant["x"] = random.randint(4, max(4, logical_tank_width(self) - 5))
        clamp_plant_position_v28(self, plant)
        self.plants.append(plant)
        self.log("A new plant takes root in the tank.")


def v28_buy_snail(self):
    refresh_upgrade_dimensions_preserving_saved_bounds(self)
    if self.spend(12):
        snail = make_snail(logical_tank_width(self), self.height)
        snail["x"] = random.randint(3, max(3, logical_tank_width(self) - 5))
        clamp_snail_position_v28(self, snail)
        self.snails.append(snail)
        self.log("A snail joins the cleanup crew.")


Fishtank.buy_decoration = v28_buy_decoration
Fishtank.buy_plant = v28_buy_plant
Fishtank.buy_snail = v28_buy_snail



if __name__ == "__main__":
    main()
