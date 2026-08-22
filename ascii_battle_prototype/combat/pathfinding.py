from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set, Tuple

from .models import Pos, Unit
from .utils import manhattan, neighbors4

WalkableFn = Callable[[Pos], bool]
PassableFn = Callable[[Pos], bool]
CostFn = Callable[[Pos], int]


def reachable_tiles(unit: Unit, is_walkable: WalkableFn, movement_cost: CostFn) -> Dict[Pos, int]:
    frontier: List[Tuple[int, Pos]] = [(0, unit.pos)]
    seen: Dict[Pos, int] = {unit.pos: 0}

    while frontier:
        frontier.sort(reverse=True)
        cost, cur = frontier.pop()
        if cost != seen.get(cur, cost):
            continue
        for nxt in neighbors4(cur):
            if not is_walkable(nxt):
                continue
            new_cost = cost + movement_cost(nxt)
            if new_cost > unit.move_range:
                continue
            if nxt in seen and seen[nxt] <= new_cost:
                continue
            seen[nxt] = new_cost
            frontier.append((new_cost, nxt))

    return seen


def path_cost(path: List[Pos], movement_cost: CostFn) -> int:
    if not path:
        return 0
    return sum(movement_cost(p) for p in path[1:])


def find_path(unit: Unit, goal: Pos, reachable: Dict[Pos, int], movement_cost: CostFn) -> List[Pos]:
    if goal not in reachable:
        return []

    frontier: List[Tuple[int, Pos]] = [(0, unit.pos)]
    came: Dict[Pos, Optional[Pos]] = {unit.pos: None}
    cost_so_far: Dict[Pos, int] = {unit.pos: 0}

    while frontier:
        frontier.sort(reverse=True)
        cost, cur = frontier.pop()
        if cur == goal:
            break
        for nxt in sorted(neighbors4(cur), key=lambda p: manhattan(p, goal)):
            if nxt not in reachable:
                continue
            new_cost = cost + movement_cost(nxt)
            if new_cost > unit.move_range:
                continue
            if nxt in cost_so_far and cost_so_far[nxt] <= new_cost:
                continue
            cost_so_far[nxt] = new_cost
            came[nxt] = cur
            frontier.append((new_cost, nxt))

    if goal not in came:
        return []

    path: List[Pos] = []
    cur: Optional[Pos] = goal
    while cur is not None:
        path.append(cur)
        cur = came[cur]
    return list(reversed(path))


def tile_path_distance(
    start: Pos,
    goals: Set[Pos],
    is_passable: PassableFn,
    is_walkable: WalkableFn,
    max_search: int = 80,
    ignore_units: bool = True,
) -> int:
    if not goals:
        return 999
    if start in goals:
        return 0

    frontier: List[Tuple[int, Pos]] = [(0, start)]
    seen: Set[Pos] = {start}
    while frontier:
        frontier.sort(reverse=True)
        dist, cur = frontier.pop()
        if dist >= max_search:
            continue
        for nxt in neighbors4(cur):
            if not is_passable(nxt):
                continue
            if not ignore_units and not is_walkable(nxt):
                continue
            if nxt in seen:
                continue
            if nxt in goals:
                return dist + 1
            seen.add(nxt)
            frontier.append((dist + 1, nxt))
    return 999


def attack_goal_tiles_for_unit(
    map_rows: List[List[str]],
    is_passable: PassableFn,
    unit: Unit,
    target: Unit,
    preferred_min: Optional[int] = None,
    preferred_max: Optional[int] = None,
) -> Set[Pos]:
    preferred_min = unit.weapon.range_min if preferred_min is None else preferred_min
    preferred_max = unit.weapon.range_max if preferred_max is None else preferred_max
    goals: Set[Pos] = set()
    for y, row in enumerate(map_rows):
        for x, _tile in enumerate(row):
            pos = (x, y)
            if not is_passable(pos):
                continue
            d = manhattan(pos, target.pos)
            if preferred_min <= d <= preferred_max:
                goals.add(pos)
    return goals


def progress_to_attack_band(
    map_rows: List[List[str]],
    is_passable: PassableFn,
    is_walkable: WalkableFn,
    unit: Unit,
    pos: Pos,
    target: Optional[Unit],
    preferred_min: Optional[int] = None,
    preferred_max: Optional[int] = None,
) -> int:
    if not target:
        return 0
    goals = attack_goal_tiles_for_unit(map_rows, is_passable, unit, target, preferred_min, preferred_max)
    return tile_path_distance(pos, goals, is_passable, is_walkable, max_search=80, ignore_units=True)


def movement_progress_bonus(
    map_rows: List[List[str]],
    is_passable: PassableFn,
    is_walkable: WalkableFn,
    unit: Unit,
    pos: Pos,
    target: Optional[Unit],
    preferred_min: Optional[int] = None,
    preferred_max: Optional[int] = None,
) -> int:
    if not target:
        return 0
    current_dist = progress_to_attack_band(map_rows, is_passable, is_walkable, unit, unit.pos, target, preferred_min, preferred_max)
    new_dist = progress_to_attack_band(map_rows, is_passable, is_walkable, unit, pos, target, preferred_min, preferred_max)
    if new_dist >= 999:
        return -120
    improvement = current_dist - new_dist
    return improvement * 26 - new_dist * 3
