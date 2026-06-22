from __future__ import annotations

"""Pure helper functions for Elsewhere.

Helpers in this module may depend on static data and support utilities, but
should not import the main game class. That keeps future systems from forming
circular imports around FarmGame.
"""

import random
from typing import List, Optional

from ascii_farmstead_support import C
from ascii_farmstead_data import (
    CALENDAR_EVENTS,
    FISH_DATA,
    FISH_ITEMS,
    FOOD_DATA,
    MINE_FLOOR_THEMES,
    MONTH_NAMES,
    SEASON_WEATHER_TABLES,
    WEEKDAY_NAMES,
    WILDERNESS_BIOME_DESCRIPTIONS,
    WILDERNESS_BIOME_NAMES,
    WILDERNESS_FORAGE_DATA,
)


def calendar_events_for(month: int, day: int, year: int) -> List[str]:
    events = list(CALENDAR_EVENTS.get((month, day), []))
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
