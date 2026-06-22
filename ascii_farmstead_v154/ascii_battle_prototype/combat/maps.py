from __future__ import annotations

from typing import Dict, List, Tuple

from .constants import (
    MAP_W, TILE_BARREL, TILE_BRIDGE, TILE_CRATE, TILE_CRYSTAL, TILE_DIRT,
    TILE_FLOOR, TILE_GRASS, TILE_ICE, TILE_MUD, TILE_SPRING, TILE_STONE,
    TILE_THORNS, TILE_TREE, TILE_WALL, TILE_WATER,
)
from .models import Pos

def build_maps() -> List[Tuple[str, List[List[str]], Dict[str, Pos]]]:
    """Return tactical arenas.

    Legend:
        . open ground
        , dirt path
        " tall grass / soft cover
        : mud / passable rough-looking ground
        = bridge / ford
        ^ stones / cover-like blocking-adjacent visual terrain
        # fence/wall
        ~ water
        T tree
    """
    t = TILE_TREE

    def rows_to_map(rows: List[str]) -> List[List[str]]:
        normalized = []
        width = max(len(row) for row in rows) if rows else MAP_W
        for row in rows:
            row = row.replace("T", t)
            # v65 supports variable-size arenas. Existing maps remain 20x12,
            # while newer arenas can be wider/taller.
            row = row[:width].ljust(width, TILE_FLOOR)
            normalized.append(list(row))
        return normalized

    def grid_rows(width: int, height: int, fill: str = TILE_FLOOR) -> List[str]:
        return ["".join([fill] * width) for _ in range(height)]

    def rows_from_grid(grid: List[List[str]]) -> List[str]:
        return ["".join(row) for row in grid]

    def fortress_grid(width: int = 34, height: int = 18) -> List[List[str]]:
        grid = [list(row) for row in grid_rows(width, height)]
        for x in range(width):
            grid[0][x] = TILE_WALL
            grid[height - 1][x] = TILE_WALL
        for y in range(height):
            grid[y][0] = TILE_WALL
            grid[y][width - 1] = TILE_WALL
        # Southern entry keeps heroes inside the arena while still reading as a gate.
        for x in range(width // 2 - 2, width // 2 + 3):
            grid[height - 1][x] = TILE_BRIDGE
        return grid

    def hline(grid: List[List[str]], y: int, x1: int, x2: int, tile: str = TILE_WALL) -> None:
        if 0 <= y < len(grid):
            for x in range(max(0, x1), min(len(grid[y]), x2 + 1)):
                grid[y][x] = tile

    def vline(grid: List[List[str]], x: int, y1: int, y2: int, tile: str = TILE_WALL) -> None:
        for y in range(max(0, y1), min(len(grid), y2 + 1)):
            if 0 <= x < len(grid[y]):
                grid[y][x] = tile

    def rect(grid: List[List[str]], x1: int, y1: int, x2: int, y2: int, tile: str) -> None:
        for y in range(max(0, y1), min(len(grid), y2 + 1)):
            for x in range(max(0, x1), min(len(grid[y]), x2 + 1)):
                grid[y][x] = tile

    def wall_rect(grid: List[List[str]], x1: int, y1: int, x2: int, y2: int) -> None:
        hline(grid, y1, x1, x2)
        hline(grid, y2, x1, x2)
        vline(grid, x1, y1, y2)
        vline(grid, x2, y1, y2)

    def set_tiles(grid: List[List[str]], placements: Dict[Pos, str]) -> None:
        for (x, y), tile in placements.items():
            if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
                grid[y][x] = tile

    meadow_rows = [
        '......"""....."".....',
        '..,,,,,"".....""..T..',
        '..,..T..,,..###......',
        '..,.....,,....#..""..',
        '..,,,,,,....~~=~~....',
        '......"...T.~~=~~....',
        '..T..."""...~~=~~....',
        '......###.....,,.....',
        '..""....#.....,,..T..',
        '..""....#..T..,,.....',
        '....,,,,,,,,,,,......',
        '....................',
    ]
    meadow_pos = {
        "Rook": (2, 9),
        "Mira": (3, 10),
        "Brom": (1, 10),
        "Aria": (5, 10),
        "Crow": (16, 1),
        "Boar": (15, 8),
        "Vine": (9, 5),
    }

    canal_rows = [
        '....""".........T....',
        '..,,,,,,....###......',
        '..,..T.,....#........',
        '..,....,~~~~=~~~~....',
        '..,....,~~~~=~~~~....',
        '..,,,,,,....=....T...',
        '......""....=........',
        '..T...""..###..""....',
        '..........#....""....',
        '....,,,,,,#,,,,,,....',
        '....,.........T.,....',
        '....................',
    ]
    canal_pos = {
        "Rook": (2, 9),
        "Mira": (4, 10),
        "Brom": (2, 10),
        "Aria": (5, 9),
        "Crow": (17, 1),
        "Boar": (15, 9),
        "Vine": (11, 2),
    }

    ruins_rows = [
        '....................',
        '..,,,....^...^...T..',
        '..,T,....###........',
        '..,,,."..#.#..""....',
        '......"..#.#..""....',
        '..###....#.#........',
        '..#......=.=....T...',
        '..#..""..=.=........',
        '.....""..###..,,,...',
        '..T.........,..,....',
        '....,,,,,,,,..,.....',
        '....................',
    ]
    ruins_pos = {
        "Rook": (2, 10),
        "Mira": (4, 9),
        "Brom": (3, 10),
        "Aria": (5, 10),
        "Crow": (16, 2),
        "Boar": (15, 8),
        "Vine": (8, 3),
    }

    orchard_rows = [
        '..T..T..T..T..T.....',
        '....................',
        '..",,,,,"...,,,,,...',
        '.."..T.."..T..T.,...',
        '.."....."...,,,,,...',
        '..""".."""....~~=~~.',
        '.............~~=~~..',
        '..###....T...~~=~~..',
        '..#.#..,,,,,,.......',
        '..###..,....,..T....',
        '.......,,,,,,.......',
        '....................',
    ]
    orchard_pos = {
        "Rook": (3, 8),
        "Mira": (3, 10),
        "Brom": (1, 8),
        "Aria": (5, 10),
        "Crow": (15, 0),
        "Boar": (14, 8),
        "Vine": (10, 3),
    }

    spring_rows = [
        '..""..""....T...""..',
        '..,,,,,,....""......',
        '..,....,....###..T..',
        '..,....,""..#.......',
        '..,,,,,,....#..""...',
        '.....T....~~=~~.....',
        '..""".....~~=~~.....',
        '..""...###~~=~~..T..',
        '.......#....,,......',
        '..T....#....,,..""..',
        '...,,,,,,,,,,,......',
        '....................',
    ]
    spring_pos = {
        "Rook": (2, 10),
        "Mira": (4, 10),
        "Brom": (1, 10),
        "Aria": (5, 9),
        "Crow": (16, 1),
        "Boar": (14, 8),
        "Vine": (9, 4),
    }

    summer_rows = [
        '"""....T....."""....',
        '..,,,,,,....###.....',
        '..,....,....#....T..',
        '..,....,~~~~=~~~~...',
        '..,....,~~~~=~~~~...',
        '..,,,,,,....=...""..',
        '....."".....=...""..',
        '..T..""..###=.......',
        '.........#..=..T....',
        '..,,,,...#..=.......',
        '..,....,,,,,,,......',
        '....................',
    ]
    summer_pos = {
        "Rook": (2, 9),
        "Mira": (3, 10),
        "Brom": (1, 9),
        "Aria": (5, 10),
        "Crow": (17, 1),
        # v66: avoid the crate placed at (15, 8).
        "Boar": (15, 9),
        "Vine": (10, 2),
    }

    autumn_rows = [
        '....T....""....T....',
        '..,,,,,,......""....',
        '..,..T.,..###.......',
        '..,....,..#.#..""...',
        '..,,,,,,.#.#..""....',
        '....""...#.#........',
        '..T.""...=.=...T....',
        '........###.........',
        '..,,,........,,,,...',
        '..,....T.....,..,...',
        '..,,,,,,,,,,,,..""..',
        '....................',
    ]
    autumn_pos = {
        "Rook": (2, 10),
        "Mira": (4, 9),
        "Brom": (3, 10),
        "Aria": (5, 9),
        "Crow": (16, 0),
        "Boar": (14, 8),
        "Vine": (9, 3),
    }

    winter_rows = [
        '...^....T....^......',
        '..,,,,,,....###.....',
        '..,....,....#...T...',
        '..,....,...^#^......',
        '..,,,,,,...^=^......',
        '......^....~~=~~....',
        '..T...^....~~=~~....',
        '..###......~~=~~....',
        '..#.#..,,,,,,.......',
        '..###..,....,..T....',
        '.......,,,,,,.......',
        '....................',
    ]
    winter_pos = {
        "Rook": (6, 9),
        "Mira": (4, 10),
        "Brom": (5, 9),
        "Aria": (5, 10),
        "Crow": (15, 1),
        "Boar": (14, 8),
        "Vine": (10, 4),
    }

    quarry_rows = [
        '....TT....^^^.....,,,,,.....',
        '..,,,,....^#^.....,...".....',
        '..,........#...~~~~=~~~~....',
        '..,..TT....#...~~~~=~~~~....',
        '..,,,,,,...###.....=.....T..',
        '......"".....#..^^^=^^^.....',
        '..T...""..B..#.....=....C...',
        '......"""....#..,,,,,,,,,...',
        '..,,,,..###..#..,......,....',
        '..,.....#.#.....,.."T"..,....',
        '..,.....###..C..,......,....',
        '..,,,,,,,,,,,,,,,,,,,,,,....',
        '....T....^^^^....""....T....',
        '..........^^.................',
        '..""..............TT.........',
        '............................',
    ]
    quarry_pos = {
        "Rook": (2, 13),
        "Mira": (3, 14),
        "Brom": (4, 13),
        "Aria": (3, 12),
        "Wolf": (24, 1),
        "Bandit": (22, 7),
        "Shield Guard": (24, 10),
        "Rockback": (18, 5),
    }

    causeway_rows = [
        '~~~~~~=~~~~~~~~~~~~~....T...',
        '~~~~~~=~~~~~~,,,,~~~...."...',
        '.....,=,,,,,,,..,~~~..C.....',
        '..T..,=....""...,,,,,,,,....',
        '.....,=...."".....~~~..,....',
        '.....,======~~====~~~..,....',
        '..""......,~~,.....~~..,....',
        '..""..B...,~~,..T..~~..,....',
        '..,,,,,,,,,~~,,,,,,~~,,,,...',
        '.........,~~~~.....~~....,...',
        '..T......,~~~~..C..~~....,...',
        '.....,,,,,====,,,,,==,,,,,...',
        '.....,....~~~~.....~~........',
        '..T..,....~~~~..""..~~..T....',
        '.....,,,,,,,,,,,,,,,,........',
        '............................',
    ]
    causeway_pos = {
        "Rook": (2, 14),
        "Mira": (3, 13),
        "Brom": (4, 14),
        "Aria": (5, 13),
        "Marsh Toad": (21, 3),
        "Wisp": (23, 8),
        "Bandit": (18, 11),
        "Shield Guard": (24, 12),
    }

    basin_rows = [
        '....T....****....T..........',
        '..,,,,,..*..*..,,,,,,.......',
        '..,.."..,*..*..,....,.."T...',
        '..,.."..,****..,..T.,.......',
        '..,,,,,,,,,,,,,,....,.......',
        '......~~~=~~~......,,,...C..',
        '..T...~~~=~~~..B....,,......',
        '......~~~=~~~....****,,.....',
        '..,,,,,,,=,,,,,,,,..*,......',
        '..,.....~~~.....,....*..T...',
        '..,.....~~~..C..,****,......',
        '..,,,,,,,,,,,,,,,,,,,,......',
        '....""....T....""...........',
        '...."".........""....T......',
        '..T........****.............',
        '............................',
    ]
    basin_pos = {
        "Rook": (3, 14),
        "Mira": (3, 13),
        "Brom": (4, 14),
        "Aria": (5, 13),
        "Vine": (17, 2),
        "Sporeling": (23, 5),
        "Boar": (20, 9),
        "Wolf": (24, 12),
    }

    forge_rows = [
        '....^^^^.....C.....^^^^.....',
        '..,,,,^^..B..#..B..^^,,,,...',
        '..,..T.....###.....T..,.....',
        '..,....,,,,,#,,,,,....,.....',
        '..,,,,,,...#.#...,,,,,,.....',
        '......""...#.#..."".........',
        '..T...""...#.#...""...T.....',
        '......,,,,,###,,,,,.........',
        '..,,,,,..B.....B..,,,,,.....',
        '..,.....~~~~=~~~~.....,.....',
        '..,..C..~~~~=~~~~..C..,.....',
        '..,,,,,,~~~~=~~~~,,,,,,.....',
        '....T.....^^=^^.....T.......',
        '..........^^=^^.............',
        '..""..........""............',
        '............................',
    ]
    forge_pos = {
        "Rook": (2, 14),
        "Mira": (3, 13),
        "Brom": (4, 14),
        "Aria": (5, 13),
        "Bandit": (21, 2),
        "Shield Guard": (22, 7),
        "Rockback": (20, 11),
        "Wisp": (24, 13),
    }

    terrace_rows = [
        '...^....T....____....^......',
        '..,,,,,,...._~~~~_...^..T...',
        '..,....,...._~==~_...,,,,...',
        '..,....,...^_~==~_^..,.."..',
        '..,,,,,,...^_~~~~_^..,.."..',
        '......^....___==___..,,,,...',
        '..T...^........=.......,,...',
        '..###......____=____....,...',
        '..#.#..,,,,_~~=~~_,,,..,...',
        '..###..,...._~~=~~_..T.,....',
        '.......,,,,,____=__,,,,,....',
        '..T.............=......T....',
        '....""....^^^^..=..^^^^.....',
        '....""..........=...........',
        '..T.......C.....=....C......',
        '............................',
    ]
    terrace_pos = {
        "Rook": (3, 14),
        "Mira": (3, 13),
        "Brom": (4, 14),
        "Aria": (5, 13),
        "Wisp": (22, 2),
        "Rockback": (20, 6),
        "Vine": (18, 10),
        "Wolf": (24, 12),
    }

    # ----- fortress / stronghold arenas -----
    gatehouse_grid = fortress_grid(34, 18)
    # Twin towers and a central gate lane.
    wall_rect(gatehouse_grid, 3, 2, 10, 8)
    wall_rect(gatehouse_grid, 23, 2, 30, 8)
    hline(gatehouse_grid, 5, 10, 23)
    for x in range(15, 19):
        gatehouse_grid[5][x] = TILE_BRIDGE
    rect(gatehouse_grid, 15, 1, 18, 16, TILE_DIRT)
    rect(gatehouse_grid, 11, 9, 22, 13, TILE_DIRT)
    hline(gatehouse_grid, 13, 5, 28)
    for x in range(15, 19):
        gatehouse_grid[13][x] = TILE_BRIDGE
    set_tiles(gatehouse_grid, {
        (6, 4): TILE_CRATE, (27, 4): TILE_CRATE, (12, 6): TILE_BARREL, (21, 6): TILE_BARREL,
        (8, 10): TILE_STONE, (25, 10): TILE_STONE, (13, 12): TILE_CRATE, (20, 12): TILE_CRATE,
        (16, 8): TILE_CRYSTAL, (17, 15): TILE_SPRING, (5, 14): TILE_GRASS, (28, 14): TILE_GRASS,
    })
    gatehouse_rows = rows_from_grid(gatehouse_grid)
    gatehouse_pos = {
        "Rook": (16, 15), "Mira": (15, 15), "Brom": (17, 15), "Aria": (18, 15),
        "Shield Guard": (16, 7), "Bandit": (8, 3), "Ember Imp": (25, 3),
        "Thornback": (18, 10), "Burrower": (12, 11),
    }

    bailey_grid = fortress_grid(36, 18)
    rect(bailey_grid, 2, 2, 33, 15, TILE_DIRT)
    wall_rect(bailey_grid, 11, 2, 24, 7)
    for x in range(16, 20):
        bailey_grid[7][x] = TILE_BRIDGE
    wall_rect(bailey_grid, 5, 9, 12, 14)
    wall_rect(bailey_grid, 23, 9, 30, 14)
    rect(bailey_grid, 14, 9, 21, 14, TILE_GRASS)
    hline(bailey_grid, 10, 13, 22, TILE_STONE)
    hline(bailey_grid, 12, 13, 22, TILE_STONE)
    set_tiles(bailey_grid, {
        (17, 4): TILE_CRYSTAL, (18, 11): TILE_SPRING, (8, 11): TILE_CRATE, (27, 11): TILE_CRATE,
        (7, 13): TILE_BARREL, (28, 13): TILE_BARREL, (15, 13): TILE_THORNS, (20, 13): TILE_THORNS,
        (3, 5): TILE_STONE, (32, 5): TILE_STONE, (4, 15): TILE_GRASS, (31, 15): TILE_GRASS,
    })
    bailey_rows = rows_from_grid(bailey_grid)
    bailey_pos = {
        "Rook": (17, 16), "Mira": (16, 15), "Brom": (18, 16), "Aria": (19, 15),
        "Shield Guard": (17, 8), "Bandit": (8, 10), "Thornback": (26, 11),
        "Razor Hare": (14, 10), "Burrower": (21, 10),
    }

    arsenal_grid = fortress_grid(36, 18)
    rect(arsenal_grid, 2, 2, 33, 15, TILE_DIRT)
    wall_rect(arsenal_grid, 4, 2, 13, 7)
    wall_rect(arsenal_grid, 22, 2, 31, 7)
    wall_rect(arsenal_grid, 4, 10, 13, 15)
    wall_rect(arsenal_grid, 22, 10, 31, 15)
    rect(arsenal_grid, 15, 2, 20, 15, TILE_DIRT)
    hline(arsenal_grid, 8, 4, 31, TILE_STONE)
    for x in range(16, 20):
        arsenal_grid[8][x] = TILE_BRIDGE
    # Lots of volatile cover.
    for pos in [(7, 4), (10, 5), (25, 4), (28, 5), (7, 12), (10, 13), (25, 12), (28, 13), (17, 6), (18, 12)]:
        arsenal_grid[pos[1]][pos[0]] = TILE_BARREL
    for pos in [(5, 5), (12, 4), (23, 5), (30, 4), (5, 13), (12, 12), (23, 13), (30, 12)]:
        arsenal_grid[pos[1]][pos[0]] = TILE_CRATE
    set_tiles(arsenal_grid, {(18, 4): TILE_CRYSTAL, (18, 14): TILE_SPRING, (16, 9): TILE_STONE, (20, 9): TILE_STONE})
    arsenal_rows = rows_from_grid(arsenal_grid)
    arsenal_pos = {
        "Rook": (18, 16), "Mira": (17, 15), "Brom": (19, 16), "Aria": (20, 15),
        "Bandit": (8, 4), "Ember Imp": (28, 4), "Shield Guard": (18, 9),
        "Burrower": (9, 12), "Thornback": (26, 12),
    }

    floodgate_grid = fortress_grid(36, 18)
    rect(floodgate_grid, 2, 2, 33, 15, TILE_DIRT)
    # Waterworks channels and bridge controls.
    rect(floodgate_grid, 4, 3, 12, 14, TILE_WATER)
    rect(floodgate_grid, 23, 3, 31, 14, TILE_WATER)
    for y in range(3, 15):
        floodgate_grid[y][8] = TILE_BRIDGE
        floodgate_grid[y][27] = TILE_BRIDGE
    for x in range(13, 23):
        floodgate_grid[8][x] = TILE_BRIDGE
    wall_rect(floodgate_grid, 14, 3, 21, 6)
    wall_rect(floodgate_grid, 14, 10, 21, 14)
    for x in (17, 18):
        floodgate_grid[6][x] = TILE_BRIDGE
        floodgate_grid[10][x] = TILE_BRIDGE
    set_tiles(floodgate_grid, {
        (17, 4): TILE_CRYSTAL, (18, 13): TILE_SPRING, (13, 8): TILE_CRATE, (22, 8): TILE_CRATE,
        (15, 9): TILE_MUD, (16, 9): TILE_MUD, (19, 9): TILE_MUD, (20, 9): TILE_MUD,
        (8, 12): TILE_BARREL, (27, 12): TILE_BARREL, (17, 15): TILE_GRASS, (18, 15): TILE_GRASS,
    })
    floodgate_rows = rows_from_grid(floodgate_grid)
    floodgate_pos = {
        "Rook": (18, 16), "Mira": (17, 15), "Brom": (19, 16), "Aria": (20, 15),
        "Marsh Toad": (8, 4), "Frost Moth": (18, 7), "Wisp": (27, 4),
        "Shield Guard": (18, 10), "Burrower": (18, 13),
    }

    redoubt_grid = fortress_grid(36, 18)
    rect(redoubt_grid, 2, 2, 33, 15, TILE_DIRT)
    wall_rect(redoubt_grid, 5, 3, 30, 13)
    for x in range(16, 20):
        redoubt_grid[13][x] = TILE_BRIDGE
    rect(redoubt_grid, 7, 5, 28, 11, TILE_FLOOR)
    rect(redoubt_grid, 14, 4, 21, 12, TILE_ICE)
    hline(redoubt_grid, 8, 7, 28, TILE_STONE)
    for x in range(16, 20):
        redoubt_grid[8][x] = TILE_ICE
    set_tiles(redoubt_grid, {
        (10, 6): TILE_CRATE, (25, 6): TILE_CRATE, (11, 10): TILE_BARREL, (24, 10): TILE_BARREL,
        (17, 6): TILE_CRYSTAL, (18, 11): TILE_SPRING, (8, 4): TILE_THORNS, (27, 4): TILE_THORNS,
        (7, 14): TILE_GRASS, (28, 14): TILE_GRASS, (16, 15): TILE_ICE, (19, 15): TILE_ICE,
    })
    redoubt_rows = rows_from_grid(redoubt_grid)
    redoubt_pos = {
        "Rook": (18, 16), "Mira": (17, 15), "Brom": (19, 16), "Aria": (20, 15),
        "Frost Moth": (18, 5), "Rockback": (12, 8), "Wisp": (24, 8),
        "Thornback": (18, 12), "Razor Hare": (27, 10),
    }

    tutorial_rows = [
        "##########################",
        "#....^......,......^....#",
        "#..m........,.......+...#",
        "#..........,,,..........#",
        "#....C.....,.....B......#",
        "#..........,............#",
        "#....,,,,,,,,,,,,,,.....#",
        "#..........,............#",
        "#.....^....,....^.......#",
        "#..........,............#",
        "#..........,.....C......#",
        "#....+.....,......m.....#",
        "#..........,............#",
        "###########=====##########",
    ]
    tutorial_pos = {
        "Rook": (12, 12),
        "Mira": (11, 12),
        "Brom": (13, 12),
        "Aria": (14, 12),
        "Luma": (15, 12),
        "Training Dummy": (14, 7),
        "Slime": (10, 7),
        "Crow": (16, 5),
        "Wolf": (9, 5),
    }

    advanced_tutorial_rows = [
        "##############################",
        "#....^....C....,....C....^..#",
        "#..m.....#####.,.#####....+.#",
        "#........#...#.,.#...#......#",
        "#..B.....#...#.,.#...#...B..#",
        "#........##=##,,,##=##......#",
        "#............,,,,............#",
        "#....+...^^..,....ii...+....#",
        "#............,...............#",
        "#..C....B....,....B....C....#",
        "#...........,,,.............#",
        "#....m......,......^........#",
        "#............,..............#",
        "#############====###########",
    ]
    advanced_tutorial_pos = {
        "Rook": (14, 12),
        "Mira": (13, 12),
        "Brom": (15, 12),
        "Aria": (16, 12),
        "Luma": (17, 12),
        "Training Dummy": (14, 7),
        "Shield Guard": (14, 5),
        "Frost Moth": (20, 7),
        "Razor Hare": (10, 5),
    }

    arenas = [
        ("Training Yard", rows_to_map(tutorial_rows), tutorial_pos),
        ("Advanced Training Yard", rows_to_map(advanced_tutorial_rows), advanced_tutorial_pos),
        ("Riverwatch Ford", rows_to_map(meadow_rows), meadow_pos),
        ("Stonewater Crossing", rows_to_map(canal_rows), canal_pos),
        ("Broken Gate Ruins", rows_to_map(ruins_rows), ruins_pos),
        ("Twinlane Grove", rows_to_map(orchard_rows), orchard_pos),
        ("Spring Bloomfield", rows_to_map(spring_rows), spring_pos),
        ("Highsummer Channel", rows_to_map(summer_rows), summer_pos),
        ("Amber Harvest", rows_to_map(autumn_rows), autumn_pos),
        ("Frostpine Crossing", rows_to_map(winter_rows), winter_pos),
        ("Moonlit Quarry", rows_to_map(quarry_rows), quarry_pos),
        ("Flooded Causeway", rows_to_map(causeway_rows), causeway_pos),
        ("Briarfall Basin", rows_to_map(basin_rows), basin_pos),
        ("Emberglass Works", rows_to_map(forge_rows), forge_pos),
        ("Snowmelt Terrace", rows_to_map(terrace_rows), terrace_pos),
        ("Gatehouse Bastion", rows_to_map(gatehouse_rows), gatehouse_pos),
        ("Inner Bailey Keep", rows_to_map(bailey_rows), bailey_pos),
        ("Rampart Arsenal", rows_to_map(arsenal_rows), arsenal_pos),
        ("Floodgate Citadel", rows_to_map(floodgate_rows), floodgate_pos),
        ("Frostwall Redoubt", rows_to_map(redoubt_rows), redoubt_pos),
    ]

    def stamp(arena_index: int, placements: Dict[Pos, str]) -> None:
        _name, grid, _positions = arenas[arena_index]
        for (x, y), tile in placements.items():
            if 0 <= y < len(grid) and 0 <= x < len(grid[y]) and grid[y][x] != TILE_WALL:
                grid[y][x] = tile

    stamp(0, {(4, 8): TILE_MUD, (5, 8): TILE_MUD, (6, 8): TILE_MUD,
              (8, 10): TILE_SPRING, (12, 7): TILE_GRASS, (13, 7): TILE_GRASS,
              (11, 5): TILE_BARREL, (15, 6): TILE_CRATE})
    stamp(1, {(5, 8): TILE_MUD, (6, 8): TILE_MUD, (8, 7): TILE_CRATE,
              (11, 6): TILE_BARREL, (13, 5): TILE_BARREL, (15, 8): TILE_CRATE,
              (9, 9): TILE_CRYSTAL})
    stamp(2, {(6, 6): TILE_CRATE, (7, 6): TILE_BARREL, (12, 4): TILE_CRATE,
              (13, 4): TILE_BARREL, (10, 8): TILE_THORNS, (11, 8): TILE_THORNS,
              (16, 6): TILE_CRYSTAL})
    stamp(3, {(7, 4): TILE_THORNS, (8, 4): TILE_THORNS, (10, 5): TILE_THORNS,
              (11, 6): TILE_THORNS, (5, 8): TILE_SPRING, (13, 7): TILE_CRYSTAL,
              (15, 5): TILE_GRASS, (16, 5): TILE_GRASS})
    stamp(4, {(6, 7): TILE_GRASS, (7, 7): TILE_GRASS, (8, 7): TILE_GRASS,
              (10, 6): TILE_CRYSTAL, (12, 8): TILE_SPRING,
              (14, 5): TILE_THORNS, (15, 5): TILE_THORNS})
    stamp(5, {(5, 9): TILE_MUD, (6, 9): TILE_MUD, (10, 7): TILE_BARREL,
              (12, 7): TILE_BARREL, (14, 8): TILE_CRATE, (15, 8): TILE_CRATE,
              (9, 5): TILE_CRYSTAL})
    stamp(6, {(6, 6): TILE_GRASS, (7, 6): TILE_GRASS, (8, 6): TILE_GRASS,
              (10, 7): TILE_BARREL, (11, 7): TILE_CRATE, (13, 8): TILE_BARREL,
              (15, 5): TILE_THORNS})
    stamp(7, {(5, 8): TILE_ICE, (6, 8): TILE_ICE, (7, 8): TILE_ICE,
              (9, 7): TILE_ICE, (10, 7): TILE_ICE, (12, 6): TILE_CRYSTAL,
              (14, 7): TILE_THORNS, (15, 7): TILE_THORNS, (16, 6): TILE_CRATE})

    stamp(8, {(10, 6): TILE_BARREL, (20, 6): TILE_CRATE, (24, 9): TILE_BARREL,
              (17, 12): TILE_CRYSTAL, (6, 13): TILE_SPRING, (15, 10): TILE_THORNS,
              (16, 10): TILE_THORNS})
    stamp(9, {(14, 7): TILE_BARREL, (22, 10): TILE_CRATE, (24, 4): TILE_CRYSTAL,
              (6, 12): TILE_SPRING, (18, 2): TILE_MUD, (19, 2): TILE_MUD})
    stamp(10, {(7, 1): TILE_THORNS, (8, 1): TILE_THORNS, (18, 7): TILE_THORNS,
               (22, 5): TILE_CRATE, (13, 10): TILE_CRYSTAL, (6, 6): TILE_SPRING})
    stamp(11, {(10, 1): TILE_BARREL, (17, 1): TILE_BARREL, (10, 8): TILE_BARREL,
               (18, 8): TILE_BARREL, (6, 10): TILE_CRATE, (21, 10): TILE_CRATE,
               (14, 12): TILE_CRYSTAL})
    stamp(12, {(12, 1): TILE_ICE, (13, 1): TILE_ICE, (14, 1): TILE_ICE,
               (12, 8): TILE_ICE, (13, 8): TILE_ICE, (14, 8): TILE_ICE,
               (21, 14): TILE_CRATE, (10, 14): TILE_CRATE, (17, 10): TILE_CRYSTAL})

    # Additional finishing touches for stronghold arenas.
    stamp(13, {(15, 5): TILE_BRIDGE, (16, 5): TILE_BRIDGE, (17, 5): TILE_BRIDGE, (18, 5): TILE_BRIDGE,
               (6, 6): TILE_STONE, (27, 6): TILE_STONE, (16, 11): TILE_MUD, (17, 11): TILE_MUD})
    stamp(14, {(12, 8): TILE_BARREL, (23, 8): TILE_BARREL, (17, 2): TILE_BRIDGE, (18, 2): TILE_BRIDGE,
               (16, 6): TILE_BRIDGE, (19, 6): TILE_BRIDGE, (18, 9): TILE_CRYSTAL})
    stamp(15, {(15, 5): TILE_CRATE, (20, 5): TILE_CRATE, (15, 12): TILE_CRATE, (20, 12): TILE_CRATE,
               (18, 8): TILE_BARREL, (16, 8): TILE_BRIDGE, (19, 8): TILE_BRIDGE})
    stamp(16, {(8, 7): TILE_BRIDGE, (27, 7): TILE_BRIDGE, (17, 8): TILE_BRIDGE, (18, 8): TILE_BRIDGE,
               (14, 12): TILE_MUD, (21, 12): TILE_MUD, (17, 3): TILE_CRYSTAL})
    stamp(17, {(14, 7): TILE_ICE, (15, 7): TILE_ICE, (20, 7): TILE_ICE, (21, 7): TILE_ICE,
               (9, 10): TILE_THORNS, (26, 10): TILE_THORNS, (18, 5): TILE_CRYSTAL})

    def move_units(arena_index: int, updates: Dict[str, Pos]) -> None:
        _name, _grid, positions = arenas[arena_index]
        positions.update(updates)

    # ----- v96 old-map revamp pass -----
    # These compact early/mid arenas were still readable, but many had
    # similar "single middle lane plus scattered cover" pacing. Add clearer
    # identities: flanks, risk/reward objects, objective-friendly clearings,
    # and stronger enemy starts that use the terrain.
    stamp(2, {
        # Riverwatch Ford: a safer north ford, a volatile central crossing,
        # and a muddy south flank.
        (5, 3): TILE_MUD, (6, 3): TILE_MUD, (7, 3): TILE_MUD,
        (10, 2): TILE_GRASS, (11, 2): TILE_GRASS,
        (14, 3): TILE_BRIDGE, (15, 3): TILE_BRIDGE,
        (14, 4): TILE_WATER, (15, 4): TILE_WATER,
        (12, 5): TILE_STONE, (16, 5): TILE_STONE,
        (13, 6): TILE_BARREL, (17, 6): TILE_CRATE,
        (6, 8): TILE_MUD, (7, 8): TILE_MUD, (8, 8): TILE_MUD,
        (11, 9): TILE_SPRING, (15, 9): TILE_THORNS,
        (16, 9): TILE_THORNS, (18, 10): TILE_GRASS,
    })
    move_units(2, {"Crow": (18, 1), "Boar": (16, 8), "Vine": (12, 4)})

    stamp(3, {
        # Stonewater Crossing: split the bridge fight into top/bottom approaches.
        (4, 2): TILE_GRASS, (5, 2): TILE_GRASS, (8, 2): TILE_STONE,
        (9, 3): TILE_MUD, (10, 3): TILE_MUD,
        (12, 4): TILE_BRIDGE, (13, 4): TILE_BRIDGE,
        (7, 5): TILE_CRATE, (14, 5): TILE_BARREL,
        (5, 6): TILE_SPRING, (16, 6): TILE_GRASS,
        (17, 6): TILE_GRASS, (6, 8): TILE_MUD,
        (7, 8): TILE_MUD, (13, 8): TILE_STONE,
        (15, 9): TILE_CRATE, (17, 10): TILE_THORNS,
    })
    move_units(3, {"Crow": (18, 2), "Boar": (16, 8), "Vine": (12, 3)})

    stamp(4, {
        # Broken Gate Ruins: make the "gate" read as a ruined courtyard
        # with two breaches and a dangerous crystal/barrel pocket.
        (4, 2): TILE_STONE, (5, 2): TILE_STONE,
        (11, 2): TILE_CRATE, (15, 2): TILE_GRASS,
        (5, 4): TILE_GRASS, (6, 4): TILE_GRASS,
        (13, 4): TILE_BARREL, (15, 5): TILE_THORNS,
        (16, 5): TILE_THORNS, (10, 6): TILE_BRIDGE,
        (12, 6): TILE_BRIDGE, (14, 6): TILE_CRYSTAL,
        (6, 7): TILE_MUD, (7, 7): TILE_MUD,
        (13, 8): TILE_STONE, (16, 9): TILE_SPRING,
        (8, 10): TILE_GRASS, (9, 10): TILE_GRASS,
    })
    move_units(4, {"Crow": (17, 2), "Boar": (15, 9), "Vine": (10, 4)})

    stamp(5, {
        # Twinlane Grove: distinguish the twin lanes with thorny orchard
        # cover on one side and muddy explosive pressure on the other.
        (4, 1): TILE_GRASS, (5, 1): TILE_GRASS,
        (9, 2): TILE_THORNS, (10, 2): TILE_THORNS,
        (13, 2): TILE_GRASS, (14, 2): TILE_GRASS,
        (6, 4): TILE_CRATE, (11, 4): TILE_STONE,
        (15, 5): TILE_BRIDGE, (16, 5): TILE_BRIDGE,
        (4, 6): TILE_MUD, (5, 6): TILE_MUD,
        (8, 7): TILE_BARREL, (12, 7): TILE_BARREL,
        (15, 8): TILE_CRYSTAL, (17, 9): TILE_SPRING,
        (11, 10): TILE_THORNS, (12, 10): TILE_THORNS,
    })
    move_units(5, {"Crow": (16, 1), "Boar": (15, 7), "Vine": (10, 3)})

    stamp(6, {
        # Spring Bloomfield: more soft-cover pockets and clearer flower-field flanks.
        (3, 2): TILE_GRASS, (4, 2): TILE_GRASS,
        (8, 2): TILE_CRATE, (12, 2): TILE_STONE,
        (6, 4): TILE_MUD, (7, 4): TILE_MUD,
        (10, 5): TILE_GRASS, (11, 5): TILE_GRASS,
        (14, 5): TILE_THORNS, (15, 5): TILE_THORNS,
        (5, 7): TILE_SPRING, (9, 7): TILE_BARREL,
        (13, 8): TILE_CRYSTAL, (16, 8): TILE_CRATE,
        (7, 10): TILE_GRASS, (8, 10): TILE_GRASS,
    })
    move_units(6, {"Crow": (17, 2), "Boar": (15, 8), "Vine": (10, 4)})

    stamp(7, {
        # Highsummer Channel: turn the channel into a heat/ice hazard puzzle,
        # with risky bridges and better ranged sightlines.
        (3, 1): TILE_GRASS, (4, 1): TILE_GRASS,
        (8, 2): TILE_STONE, (9, 2): TILE_STONE,
        (12, 3): TILE_BRIDGE, (13, 3): TILE_BRIDGE,
        (15, 4): TILE_CRATE, (17, 4): TILE_BARREL,
        (6, 6): TILE_ICE, (7, 6): TILE_ICE,
        (11, 6): TILE_CRYSTAL, (14, 7): TILE_THORNS,
        (15, 7): TILE_THORNS, (4, 8): TILE_MUD,
        (5, 8): TILE_MUD, (17, 9): TILE_SPRING,
    })
    move_units(7, {"Crow": (17, 1), "Boar": (15, 9), "Vine": (11, 3)})

    stamp(8, {
        # Amber Harvest: more harvest rows, wagon-cover, and a dangerous
        # central harvest-lane explosive.
        (5, 1): TILE_GRASS, (6, 1): TILE_GRASS,
        (12, 1): TILE_GRASS, (13, 1): TILE_GRASS,
        (8, 3): TILE_STONE, (12, 3): TILE_CRATE,
        (14, 4): TILE_BARREL, (16, 4): TILE_GRASS,
        (5, 6): TILE_MUD, (6, 6): TILE_MUD,
        (10, 6): TILE_BRIDGE, (12, 6): TILE_BRIDGE,
        (13, 7): TILE_CRYSTAL, (16, 8): TILE_THORNS,
        (17, 8): TILE_THORNS, (9, 10): TILE_SPRING,
    })
    move_units(8, {"Crow": (17, 1), "Boar": (15, 8), "Vine": (10, 3)})

    stamp(9, {
        # Frostpine Crossing: stronger frozen river identity with risky ice
        # lanes, a safer stone flank, and a healing pocket.
        (5, 1): TILE_ICE, (6, 1): TILE_ICE,
        (10, 2): TILE_STONE, (11, 2): TILE_STONE,
        (15, 3): TILE_CRATE, (16, 3): TILE_GRASS,
        (12, 4): TILE_BRIDGE, (14, 4): TILE_BRIDGE,
        (10, 5): TILE_ICE, (11, 5): TILE_ICE,
        (15, 6): TILE_ICE, (16, 6): TILE_ICE,
        (12, 7): TILE_BARREL, (17, 7): TILE_CRYSTAL,
        (6, 8): TILE_SPRING, (13, 9): TILE_THORNS,
        (14, 9): TILE_THORNS, (18, 10): TILE_MUD,
    })
    move_units(9, {"Crow": (16, 1), "Boar": (15, 8), "Vine": (11, 4)})

    # v96 validation fixes: older advanced tutorial had one enemy on a
    # wall tile after previous terrain tweaks, and Broken Gate needed a
    # little more destructible cover for the new objective/object gameplay.
    move_units(1, {"Razor Hare": (10, 6)})
    stamp(4, {
        (5, 1): TILE_CRATE,
        (7, 2): TILE_CRATE,
        (12, 3): TILE_CRATE,
        (13, 6): TILE_CRATE,
        (6, 8): TILE_BARREL,
    })
    move_units(2, {"Crow": (17, 1), "Vine": (12, 5)})
    move_units(6, {"Crow": (16, 2)})
    stamp(6, {
        (9, 2): TILE_STONE,
        (10, 2): TILE_STONE,
        (15, 3): TILE_CRATE,
        (16, 6): TILE_THORNS,
        (17, 6): TILE_THORNS,
    })
    move_units(7, {"Vine": (12, 3)})
    move_units(8, {"Vine": (9, 3)})
    stamp(8, {
        (6, 2): TILE_CRATE,
        (12, 2): TILE_CRATE,
        (13, 3): TILE_STONE,
        (15, 5): TILE_CRATE,
        (17, 6): TILE_BARREL,
        (18, 7): TILE_SPRING,
    })

    try:
        from ascii_farmstead_custom_extended import custom_combat_maps

        arenas.extend(custom_combat_maps(name for name, _grid, _positions in arenas))
    except (ImportError, OSError, TypeError, ValueError):
        pass
    return arenas

