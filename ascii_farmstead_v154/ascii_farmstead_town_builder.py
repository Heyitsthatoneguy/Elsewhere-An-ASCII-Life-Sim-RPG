from __future__ import annotations

"""Isolated wilderness-settlement planning and construction foundations.

This module deliberately does not modify the authored town or live wilderness
maps. Settlement records are save-safe blueprints which can be previewed over a
copy of terrain and eventually applied by a future procedural-town system.
"""

from collections import deque
import copy
import random
from typing import Dict, Iterable, List, Optional, Set, Tuple


Position = Tuple[int, int]
SETTLEMENT_PLAN_VERSION = 1
SETTLEMENT_STYLES = ("Crossroads", "Main Street", "Market Ring")
SETTLEMENT_ZONES = ("Civic", "Commercial", "Residential", "Industrial", "Green")
SETTLEMENT_PHASES = ("Planned", "Foundation", "Frame", "Complete")
SETTLEMENT_BLOCKING_TERRAIN = {"#", "~", "T", "o", "R", "J", "P", "K", "Q", "Y", "W", "N"}


SETTLEMENT_BUILDING_CATALOG: Dict[str, Dict[str, object]] = {
    "town_hall": {
        "name": "Town Hall",
        "zone": "Civic",
        "width": 9,
        "height": 6,
        "symbol": "H",
        "capacity": 0,
        "service": 5,
        "phases": [
            {"materials": {"Wood": 30, "Stone": 25}, "money": 500, "labor": 8},
            {"materials": {"Wood": 45, "Stone": 20, "Iron Bar": 2}, "money": 850, "labor": 12},
            {"materials": {"Wood": 20, "Stone": 10, "Cloth": 2}, "money": 650, "labor": 8},
        ],
    },
    "well": {
        "name": "Public Well",
        "zone": "Civic",
        "width": 3,
        "height": 3,
        "symbol": "O",
        "capacity": 0,
        "service": 2,
        "phases": [
            {"materials": {"Stone": 20, "Wood": 5}, "money": 120, "labor": 4},
            {"materials": {"Stone": 15, "Iron Bar": 1}, "money": 180, "labor": 5},
            {"materials": {"Wood": 5}, "money": 80, "labor": 2},
        ],
    },
    "general_store": {
        "name": "General Store",
        "zone": "Commercial",
        "width": 7,
        "height": 5,
        "symbol": "G",
        "capacity": 0,
        "service": 3,
        "phases": [
            {"materials": {"Wood": 24, "Stone": 10}, "money": 300, "labor": 6},
            {"materials": {"Wood": 32, "Iron Bar": 1}, "money": 450, "labor": 8},
            {"materials": {"Wood": 12, "Cloth": 1}, "money": 300, "labor": 5},
        ],
    },
    "carpenter": {
        "name": "Carpenter Workshop",
        "zone": "Industrial",
        "width": 7,
        "height": 5,
        "symbol": "C",
        "capacity": 0,
        "service": 3,
        "phases": [
            {"materials": {"Wood": 28, "Stone": 8}, "money": 280, "labor": 6},
            {"materials": {"Wood": 36, "Iron Bar": 2}, "money": 460, "labor": 9},
            {"materials": {"Wood": 14}, "money": 260, "labor": 4},
        ],
    },
    "clinic": {
        "name": "Clinic",
        "zone": "Civic",
        "width": 7,
        "height": 5,
        "symbol": "+",
        "capacity": 0,
        "service": 4,
        "phases": [
            {"materials": {"Wood": 22, "Stone": 14}, "money": 350, "labor": 6},
            {"materials": {"Wood": 28, "Iron Bar": 1}, "money": 500, "labor": 8},
            {"materials": {"Wood": 10, "Cloth": 3, "Cave Herbs": 2}, "money": 400, "labor": 5},
        ],
    },
    "library": {
        "name": "Library",
        "zone": "Civic",
        "width": 7,
        "height": 5,
        "symbol": "L",
        "capacity": 0,
        "service": 4,
        "phases": [
            {"materials": {"Wood": 24, "Stone": 12}, "money": 340, "labor": 6},
            {"materials": {"Wood": 34, "Iron Bar": 1}, "money": 520, "labor": 9},
            {"materials": {"Wood": 18, "Cloth": 2}, "money": 420, "labor": 6},
        ],
    },
    "inn": {
        "name": "Roadside Inn",
        "zone": "Commercial",
        "width": 9,
        "height": 6,
        "symbol": "I",
        "capacity": 4,
        "service": 3,
        "phases": [
            {"materials": {"Wood": 30, "Stone": 14}, "money": 420, "labor": 7},
            {"materials": {"Wood": 42, "Iron Bar": 2}, "money": 620, "labor": 10},
            {"materials": {"Wood": 16, "Cloth": 4}, "money": 500, "labor": 7},
        ],
    },
    "home": {
        "name": "Settler Home",
        "zone": "Residential",
        "width": 7,
        "height": 5,
        "symbol": "h",
        "capacity": 3,
        "service": 0,
        "phases": [
            {"materials": {"Wood": 18, "Stone": 6}, "money": 180, "labor": 4},
            {"materials": {"Wood": 24}, "money": 260, "labor": 6},
            {"materials": {"Wood": 8, "Cloth": 1}, "money": 160, "labor": 3},
        ],
    },
    "market_stall": {
        "name": "Market Stall",
        "zone": "Commercial",
        "width": 5,
        "height": 3,
        "symbol": "$",
        "capacity": 0,
        "service": 1,
        "phases": [
            {"materials": {"Wood": 10}, "money": 80, "labor": 2},
            {"materials": {"Wood": 8, "Cloth": 1}, "money": 100, "labor": 2},
            {"materials": {"Wood": 4}, "money": 60, "labor": 1},
        ],
    },
    "workshop": {
        "name": "Shared Workshop",
        "zone": "Industrial",
        "width": 7,
        "height": 5,
        "symbol": "W",
        "capacity": 0,
        "service": 2,
        "phases": [
            {"materials": {"Wood": 24, "Stone": 10}, "money": 260, "labor": 5},
            {"materials": {"Wood": 30, "Iron Bar": 2}, "money": 420, "labor": 8},
            {"materials": {"Wood": 12, "Copper Bar": 1}, "money": 300, "labor": 4},
        ],
    },
    "park": {
        "name": "Village Green",
        "zone": "Green",
        "width": 7,
        "height": 5,
        "symbol": "&",
        "capacity": 0,
        "service": 2,
        "phases": [
            {"materials": {"Wood": 6, "Stone": 6}, "money": 100, "labor": 3},
            {"materials": {"Wood": 8, "Wildflower": 2}, "money": 120, "labor": 3},
            {"materials": {"Wood": 4}, "money": 80, "labor": 2},
        ],
    },
}


def settlement_chunk_key(chunk_x: int, chunk_y: int) -> str:
    return f"{int(chunk_x)},{int(chunk_y)}"


def settlement_coord_key(x: int, y: int) -> str:
    return f"{int(x)},{int(y)}"


def parse_settlement_coord(value: object) -> Optional[Position]:
    try:
        x_text, y_text = str(value).split(",", 1)
        return int(x_text), int(y_text)
    except Exception:
        return None


def settlement_rect_tiles(x: int, y: int, width: int, height: int) -> Set[Position]:
    return {
        (xx, yy)
        for yy in range(int(y), int(y) + max(0, int(height)))
        for xx in range(int(x), int(x) + max(0, int(width)))
    }


def settlement_rects_overlap(first: Dict[str, object], second: Dict[str, object]) -> bool:
    return bool(
        settlement_rect_tiles(
            int(first.get("x", 0)),
            int(first.get("y", 0)),
            int(first.get("width", 0)),
            int(first.get("height", 0)),
        )
        & settlement_rect_tiles(
            int(second.get("x", 0)),
            int(second.get("y", 0)),
            int(second.get("width", 0)),
            int(second.get("height", 0)),
        )
    )


def settlement_building_phase(building: Dict[str, object]) -> str:
    try:
        index = max(0, min(3, int(building.get("phase_index", 0))))
    except Exception:
        index = 0
    return SETTLEMENT_PHASES[index]


def settlement_phase_requirements(building: Dict[str, object]) -> Dict[str, object]:
    type_id = str(building.get("type_id", ""))
    catalog = SETTLEMENT_BUILDING_CATALOG.get(type_id, {})
    phases = catalog.get("phases", []) if isinstance(catalog, dict) else []
    try:
        phase_index = max(0, int(building.get("phase_index", 0)))
    except Exception:
        phase_index = 0
    if not isinstance(phases, list) or phase_index >= len(phases):
        return {"materials": {}, "money": 0, "labor": 0}
    raw = phases[phase_index] if isinstance(phases[phase_index], dict) else {}
    materials: Dict[str, int] = {}
    raw_materials = raw.get("materials", {}) if isinstance(raw.get("materials"), dict) else {}
    for name, amount in raw_materials.items():
        try:
            clean_amount = max(0, int(amount))
        except Exception:
            continue
        if str(name) and clean_amount:
            materials[str(name)] = clean_amount
    return {
        "materials": materials,
        "money": max(0, int(raw.get("money", 0))),
        "labor": max(0, int(raw.get("labor", 0))),
    }


def sanitize_wilderness_settlements(value: object) -> Dict[str, Dict[str, object]]:
    if not isinstance(value, dict):
        return {}
    clean: Dict[str, Dict[str, object]] = {}
    for raw_key, raw_plan in value.items():
        if not isinstance(raw_plan, dict):
            continue
        try:
            cx_text, cy_text = str(raw_key).split(",", 1)
            chunk_x, chunk_y = int(cx_text), int(cy_text)
        except Exception:
            try:
                chunk_x = int(raw_plan.get("chunk_x", 0))
                chunk_y = int(raw_plan.get("chunk_y", 0))
            except Exception:
                continue
        key = settlement_chunk_key(chunk_x, chunk_y)
        try:
            width = max(32, min(160, int(raw_plan.get("width", 86))))
            height = max(22, min(100, int(raw_plan.get("height", 38))))
            seed = int(raw_plan.get("seed", 0))
        except Exception:
            width, height, seed = 86, 38, 0
        style = str(raw_plan.get("style", "Crossroads") or "Crossroads")
        if style not in SETTLEMENT_STYLES:
            style = "Crossroads"
        entrance = raw_plan.get("entrance", {})
        if not isinstance(entrance, dict):
            entrance = {}
        entrance_x = max(1, min(width - 2, int(entrance.get("x", width // 2))))
        entrance_y = max(1, min(height - 2, int(entrance.get("y", height - 2))))

        road_tiles: List[str] = []
        seen_roads: Set[str] = set()
        for raw_coord in raw_plan.get("roads", []) if isinstance(raw_plan.get("roads"), list) else []:
            position = parse_settlement_coord(raw_coord)
            if not position:
                continue
            x, y = position
            coord = settlement_coord_key(x, y)
            if 1 <= x < width - 1 and 1 <= y < height - 1 and coord not in seen_roads:
                road_tiles.append(coord)
                seen_roads.add(coord)

        lots: Dict[str, Dict[str, object]] = {}
        for raw_lot_id, raw_lot in (
            raw_plan.get("lots", {}).items()
            if isinstance(raw_plan.get("lots"), dict)
            else []
        ):
            if not isinstance(raw_lot, dict):
                continue
            lot_id = str(raw_lot_id or "").strip()
            if not lot_id:
                continue
            try:
                x = int(raw_lot.get("x", 1))
                y = int(raw_lot.get("y", 1))
                lot_width = max(3, int(raw_lot.get("width", 7)))
                lot_height = max(3, int(raw_lot.get("height", 5)))
            except Exception:
                continue
            if x < 1 or y < 1 or x + lot_width >= width or y + lot_height >= height:
                continue
            zone = str(raw_lot.get("zone", "Residential") or "Residential")
            if zone not in SETTLEMENT_ZONES:
                zone = "Residential"
            lots[lot_id] = {
                "id": lot_id,
                "name": str(raw_lot.get("name", lot_id.replace("_", " ").title())),
                "x": x,
                "y": y,
                "width": lot_width,
                "height": lot_height,
                "zone": zone,
                "building_id": str(raw_lot.get("building_id", "") or ""),
            }

        buildings: Dict[str, Dict[str, object]] = {}
        for raw_building_id, raw_building in (
            raw_plan.get("buildings", {}).items()
            if isinstance(raw_plan.get("buildings"), dict)
            else []
        ):
            if not isinstance(raw_building, dict):
                continue
            building_id = str(raw_building_id or "").strip()
            type_id = str(raw_building.get("type_id", "") or "")
            lot_id = str(raw_building.get("lot_id", "") or "")
            if not building_id or type_id not in SETTLEMENT_BUILDING_CATALOG or lot_id not in lots:
                continue
            catalog = SETTLEMENT_BUILDING_CATALOG[type_id]
            try:
                x = int(raw_building.get("x", lots[lot_id]["x"]))
                y = int(raw_building.get("y", lots[lot_id]["y"]))
                phase_index = max(0, min(3, int(raw_building.get("phase_index", 0))))
                labor_done = max(0, int(raw_building.get("labor_done", 0)))
                money_contributed = max(0, int(raw_building.get("money_contributed", 0)))
            except Exception:
                continue
            material_contributions = {}
            raw_materials = raw_building.get("material_contributions", {})
            if isinstance(raw_materials, dict):
                for name, amount in raw_materials.items():
                    try:
                        amount_int = max(0, int(amount))
                    except Exception:
                        continue
                    if str(name) and amount_int:
                        material_contributions[str(name)] = amount_int
            width_value = int(catalog["width"])
            height_value = int(catalog["height"])
            if not settlement_rect_tiles(
                x,
                y,
                width_value,
                height_value,
            ) <= settlement_rect_tiles(
                int(lots[lot_id]["x"]),
                int(lots[lot_id]["y"]),
                int(lots[lot_id]["width"]),
                int(lots[lot_id]["height"]),
            ):
                continue
            door_x = max(x, min(x + width_value - 1, int(raw_building.get("door_x", x + width_value // 2))))
            door_y = max(y, min(y + height_value - 1, int(raw_building.get("door_y", y + height_value - 1))))
            access_x = max(1, min(width - 2, int(raw_building.get("access_x", door_x))))
            access_y = max(1, min(height - 2, int(raw_building.get("access_y", door_y + 1))))
            buildings[building_id] = {
                "id": building_id,
                "type_id": type_id,
                "name": str(raw_building.get("name", catalog["name"])),
                "lot_id": lot_id,
                "x": x,
                "y": y,
                "width": width_value,
                "height": height_value,
                "door_x": door_x,
                "door_y": door_y,
                "access_x": access_x,
                "access_y": access_y,
                "phase_index": phase_index,
                "status": "complete" if phase_index >= 3 else str(raw_building.get("status", "planned")),
                "material_contributions": material_contributions,
                "money_contributed": money_contributed,
                "labor_done": labor_done,
                "priority": max(0, int(raw_building.get("priority", len(buildings)))),
            }
            lots[lot_id]["building_id"] = building_id

        queue = [
            str(building_id)
            for building_id in (
                raw_plan.get("construction_queue", [])
                if isinstance(raw_plan.get("construction_queue"), list)
                else []
            )
            if str(building_id) in buildings and int(buildings[str(building_id)]["phase_index"]) < 3
        ]
        queue = list(dict.fromkeys(queue))
        clean[key] = {
            "version": SETTLEMENT_PLAN_VERSION,
            "id": str(raw_plan.get("id", f"settlement:{key}")),
            "name": str(raw_plan.get("name", f"Wilderness Settlement {key}")),
            "chunk_x": chunk_x,
            "chunk_y": chunk_y,
            "width": width,
            "height": height,
            "seed": seed,
            "style": style,
            "status": str(raw_plan.get("status", "planning") or "planning"),
            "source": str(raw_plan.get("source", "manual") or "manual"),
            "auto_generated": bool(raw_plan.get("auto_generated", False)),
            "map_applied": bool(raw_plan.get("map_applied", False)),
            "discovered": bool(raw_plan.get("discovered", False)),
            "discovered_day": str(raw_plan.get("discovered_day", "") or ""),
            "runtime_version": max(0, int(raw_plan.get("runtime_version", 0) or 0)),
            "specialty": str(raw_plan.get("specialty", "") or ""),
            "sign_x": int(raw_plan.get("sign_x", -1) or -1),
            "sign_y": int(raw_plan.get("sign_y", -1) or -1),
            "service_state": copy.deepcopy(
                raw_plan.get("service_state", {})
                if isinstance(raw_plan.get("service_state"), dict)
                else {}
            ),
            "revision": max(1, int(raw_plan.get("revision", 1))),
            "entrance": {"x": entrance_x, "y": entrance_y},
            "roads": road_tiles,
            "road_surface": str(raw_plan.get("road_surface", "Dirt") or "Dirt"),
            "lots": lots,
            "buildings": buildings,
            "construction_queue": queue,
            "treasury": max(0, int(raw_plan.get("treasury", 0))),
            "labor_pool": max(0, int(raw_plan.get("labor_pool", 0))),
            "notes": [
                str(note)
                for note in (
                    raw_plan.get("notes", [])
                    if isinstance(raw_plan.get("notes"), list)
                    else []
                )
                if str(note or "").strip()
            ][-20:],
        }
    return clean


class WildernessTownBuilder:
    """Pure settlement planner operating on serializable dictionaries."""

    def create_plan(
        self,
        chunk_x: int,
        chunk_y: int,
        seed: int,
        name: str = "",
        style: str = "Crossroads",
        width: int = 86,
        height: int = 38,
        starter_layout: bool = True,
    ) -> Dict[str, object]:
        width = max(50, int(width))
        height = max(28, int(height))
        style = style if style in SETTLEMENT_STYLES else "Crossroads"
        key = settlement_chunk_key(chunk_x, chunk_y)
        plan: Dict[str, object] = {
            "version": SETTLEMENT_PLAN_VERSION,
            "id": f"settlement:{key}",
            "name": str(name or self.generated_name(seed, chunk_x, chunk_y)),
            "chunk_x": int(chunk_x),
            "chunk_y": int(chunk_y),
            "width": width,
            "height": height,
            "seed": int(seed),
            "style": style,
            "status": "planning",
            "source": "manual",
            "auto_generated": False,
            "map_applied": False,
            "discovered": False,
            "discovered_day": "",
            "runtime_version": 0,
            "specialty": "",
            "sign_x": -1,
            "sign_y": -1,
            "service_state": {},
            "revision": 1,
            "entrance": {"x": width // 2, "y": height - 2},
            "roads": [],
            "road_surface": "Dirt",
            "lots": {},
            "buildings": {},
            "construction_queue": [],
            "treasury": 0,
            "labor_pool": 0,
            "notes": ["Blueprint created. No live wilderness map has been changed."],
        }
        if starter_layout:
            self.generate_starter_layout(plan)
        return plan

    def generated_name(self, seed: int, chunk_x: int, chunk_y: int) -> str:
        rng = random.Random(int(seed) + int(chunk_x) * 92821 + int(chunk_y) * 68917)
        first = ["Amber", "Briar", "Cedar", "Clear", "Fern", "Hearth", "Juniper", "Moss", "River", "Stone"]
        second = ["cross", "field", "ford", "gate", "grove", "hollow", "rest", "stead", "watch", "wick"]
        return f"{rng.choice(first)}{rng.choice(second)}"

    def add_road_line(
        self,
        plan: Dict[str, object],
        start: Position,
        end: Position,
    ) -> int:
        width, height = int(plan["width"]), int(plan["height"])
        x, y = int(start[0]), int(start[1])
        end_x, end_y = int(end[0]), int(end[1])
        roads = list(plan.get("roads", []) or [])
        seen = set(str(value) for value in roads)
        added = 0
        while x != end_x:
            if 1 <= x < width - 1 and 1 <= y < height - 1:
                key = settlement_coord_key(x, y)
                if key not in seen:
                    roads.append(key)
                    seen.add(key)
                    added += 1
            x += 1 if end_x > x else -1
        while y != end_y:
            if 1 <= x < width - 1 and 1 <= y < height - 1:
                key = settlement_coord_key(x, y)
                if key not in seen:
                    roads.append(key)
                    seen.add(key)
                    added += 1
            y += 1 if end_y > y else -1
        if 1 <= x < width - 1 and 1 <= y < height - 1:
            key = settlement_coord_key(x, y)
            if key not in seen:
                roads.append(key)
                added += 1
        plan["roads"] = roads
        if added:
            plan["revision"] = int(plan.get("revision", 1)) + 1
        return added

    def add_lot(
        self,
        plan: Dict[str, object],
        lot_id: str,
        x: int,
        y: int,
        width: int,
        height: int,
        zone: str,
        name: str = "",
    ) -> bool:
        lot_id = str(lot_id or "").strip()
        zone = zone if zone in SETTLEMENT_ZONES else "Residential"
        if not lot_id or lot_id in plan.get("lots", {}):
            return False
        lot = {
            "id": lot_id,
            "name": str(name or lot_id.replace("_", " ").title()),
            "x": int(x),
            "y": int(y),
            "width": max(3, int(width)),
            "height": max(3, int(height)),
            "zone": zone,
            "building_id": "",
        }
        if (
            lot["x"] < 1
            or lot["y"] < 1
            or int(lot["x"]) + int(lot["width"]) >= int(plan["width"])
            or int(lot["y"]) + int(lot["height"]) >= int(plan["height"])
        ):
            return False
        if any(settlement_rects_overlap(lot, other) for other in plan.get("lots", {}).values()):
            return False
        plan.setdefault("lots", {})[lot_id] = lot
        plan["revision"] = int(plan.get("revision", 1)) + 1
        return True

    def place_building(
        self,
        plan: Dict[str, object],
        lot_id: str,
        type_id: str,
        building_id: str = "",
        name: str = "",
    ) -> str:
        lots = plan.get("lots", {})
        if lot_id not in lots or type_id not in SETTLEMENT_BUILDING_CATALOG:
            return ""
        lot = lots[lot_id]
        if str(lot.get("building_id", "")):
            return ""
        catalog = SETTLEMENT_BUILDING_CATALOG[type_id]
        building_width = int(catalog["width"])
        building_height = int(catalog["height"])
        if building_width > int(lot["width"]) or building_height > int(lot["height"]):
            return ""
        if str(lot.get("zone")) != str(catalog["zone"]):
            compatible = (
                type_id == "well" and str(lot.get("zone")) in {"Civic", "Green"}
            )
            if not compatible:
                return ""
        building_id = str(building_id or f"{type_id}:{len(plan.get('buildings', {})) + 1}")
        if building_id in plan.get("buildings", {}):
            return ""
        x = int(lot["x"]) + (int(lot["width"]) - building_width) // 2
        y = int(lot["y"]) + (int(lot["height"]) - building_height) // 2
        plan_center_y = int(plan["height"]) // 2
        door_x = x + building_width // 2
        if y < plan_center_y:
            door_y = y + building_height - 1
            access_y = door_y + 1
        else:
            door_y = y
            access_y = door_y - 1
        access_x = door_x
        building = {
            "id": building_id,
            "type_id": type_id,
            "name": str(name or catalog["name"]),
            "lot_id": lot_id,
            "x": x,
            "y": y,
            "width": building_width,
            "height": building_height,
            "door_x": door_x,
            "door_y": door_y,
            "access_x": access_x,
            "access_y": access_y,
            "phase_index": 0,
            "status": "planned",
            "material_contributions": {},
            "money_contributed": 0,
            "labor_done": 0,
            "priority": len(plan.get("buildings", {})),
        }
        plan.setdefault("buildings", {})[building_id] = building
        lot["building_id"] = building_id
        self.connect_access_to_roads(plan, (access_x, access_y))
        plan["revision"] = int(plan.get("revision", 1)) + 1
        return building_id

    def connect_access_to_roads(self, plan: Dict[str, object], access: Position) -> None:
        roads = [position for value in plan.get("roads", []) if (position := parse_settlement_coord(value))]
        if not roads:
            entrance = plan.get("entrance", {})
            roads = [(int(entrance.get("x", 1)), int(entrance.get("y", 1)))]
        nearest = min(roads, key=lambda pos: abs(pos[0] - access[0]) + abs(pos[1] - access[1]))
        self.add_road_line(plan, access, nearest)

    def generate_starter_layout(self, plan: Dict[str, object]) -> None:
        width, height = int(plan["width"]), int(plan["height"])
        center_x, center_y = width // 2, height // 2
        entrance = (center_x, height - 2)
        plan["entrance"] = {"x": entrance[0], "y": entrance[1]}
        self.add_road_line(plan, entrance, (center_x, 3))
        self.add_road_line(plan, (4, center_y), (width - 5, center_y))
        if str(plan.get("style")) == "Main Street":
            self.add_road_line(plan, (4, center_y - 2), (width - 5, center_y - 2))
        elif str(plan.get("style")) == "Market Ring":
            for y in range(center_y - 2, center_y + 3):
                self.add_road_line(plan, (center_x - 3, y), (center_x + 3, y))

        lot_width, lot_height = 9, 6
        columns = [5, 17, 29, width - 38, width - 26, width - 14]
        top_y, bottom_y = 4, height - 10
        zones = [
            "Residential",
            "Civic",
            "Civic",
            "Commercial",
            "Commercial",
            "Residential",
            "Residential",
            "Residential",
            "Commercial",
            "Industrial",
            "Green",
            "Residential",
        ]
        lot_ids: List[str] = []
        for row_index, y in enumerate([top_y, bottom_y]):
            for column_index, x in enumerate(columns):
                lot_id = f"lot_{row_index + 1}_{column_index + 1}"
                if self.add_lot(
                    plan,
                    lot_id,
                    x,
                    y,
                    lot_width,
                    lot_height,
                    zones[row_index * 6 + column_index],
                ):
                    lot_ids.append(lot_id)

        starter_assignments = [
            ("lot_1_1", "home", "Northwest Home"),
            ("lot_1_2", "clinic", "Founders Clinic"),
            ("lot_1_3", "town_hall", "Founders Hall"),
            ("lot_1_4", "general_store", "Crossroads General"),
            ("lot_1_5", "inn", "Wayfarer Inn"),
            ("lot_1_6", "home", "Northeast Home"),
            ("lot_2_1", "home", "Southwest Home"),
            ("lot_2_2", "home", "Garden Home"),
            ("lot_2_3", "market_stall", "Founders Market"),
            ("lot_2_4", "carpenter", "Settlement Carpenter"),
            ("lot_2_5", "well", "Founders Well"),
            ("lot_2_6", "home", "Southeast Home"),
        ]
        for lot_id, type_id, name in starter_assignments:
            self.place_building(plan, lot_id, type_id, name=name)
        plan["revision"] = max(1, int(plan.get("revision", 1)))

    def queue_building(self, plan: Dict[str, object], building_id: str) -> bool:
        building = plan.get("buildings", {}).get(str(building_id))
        if not isinstance(building, dict) or int(building.get("phase_index", 0)) >= 3:
            return False
        queue = plan.setdefault("construction_queue", [])
        if building_id not in queue:
            queue.append(str(building_id))
        building["status"] = "queued"
        plan["status"] = "construction"
        return True

    def contribute(
        self,
        plan: Dict[str, object],
        building_id: str,
        materials: Optional[Dict[str, int]] = None,
        money: int = 0,
    ) -> Dict[str, object]:
        building = plan.get("buildings", {}).get(str(building_id))
        if not isinstance(building, dict) or int(building.get("phase_index", 0)) >= 3:
            return {"materials": {}, "money": 0}
        requirements = settlement_phase_requirements(building)
        needed_materials = requirements["materials"]
        contributed = building.setdefault("material_contributions", {})
        accepted: Dict[str, int] = {}
        for item, amount in (materials or {}).items():
            if item not in needed_materials:
                continue
            remaining = max(0, int(needed_materials[item]) - int(contributed.get(item, 0)))
            used = min(remaining, max(0, int(amount)))
            if used:
                contributed[item] = int(contributed.get(item, 0)) + used
                accepted[item] = used
        remaining_money = max(0, int(requirements["money"]) - int(building.get("money_contributed", 0)))
        accepted_money = min(remaining_money, max(0, int(money)))
        building["money_contributed"] = int(building.get("money_contributed", 0)) + accepted_money
        return {"materials": accepted, "money": accepted_money}

    def phase_funded(self, building: Dict[str, object]) -> bool:
        requirements = settlement_phase_requirements(building)
        contributed = building.get("material_contributions", {})
        return (
            all(int(contributed.get(item, 0)) >= int(amount) for item, amount in requirements["materials"].items())
            and int(building.get("money_contributed", 0)) >= int(requirements["money"])
        )

    def apply_labor(self, plan: Dict[str, object], labor: int) -> List[str]:
        remaining_labor = max(0, int(labor))
        completed: List[str] = []
        queue = list(plan.get("construction_queue", []) or [])
        for building_id in queue:
            if remaining_labor <= 0:
                break
            building = plan.get("buildings", {}).get(building_id)
            if not isinstance(building, dict) or int(building.get("phase_index", 0)) >= 3:
                continue
            if not self.phase_funded(building):
                continue
            requirements = settlement_phase_requirements(building)
            needed = max(0, int(requirements["labor"]) - int(building.get("labor_done", 0)))
            used = min(needed, remaining_labor)
            building["labor_done"] = int(building.get("labor_done", 0)) + used
            remaining_labor -= used
            if int(building["labor_done"]) >= int(requirements["labor"]):
                building["phase_index"] = int(building.get("phase_index", 0)) + 1
                building["material_contributions"] = {}
                building["money_contributed"] = 0
                building["labor_done"] = 0
                phase = settlement_building_phase(building)
                building["status"] = "complete" if phase == "Complete" else "queued"
                completed.append(f"{building.get('name', building_id)} reached {phase}")
        plan["construction_queue"] = [
            building_id
            for building_id in queue
            if int(plan.get("buildings", {}).get(building_id, {}).get("phase_index", 3)) < 3
        ]
        if not plan["construction_queue"] and all(
            int(building.get("phase_index", 0)) >= 3
            for building in plan.get("buildings", {}).values()
        ):
            plan["status"] = "established"
        return completed

    def road_positions(self, plan: Dict[str, object]) -> Set[Position]:
        return {
            position
            for value in plan.get("roads", [])
            if (position := parse_settlement_coord(value)) is not None
        }

    def connected_road_positions(self, plan: Dict[str, object]) -> Set[Position]:
        roads = self.road_positions(plan)
        entrance_data = plan.get("entrance", {})
        entrance = (int(entrance_data.get("x", 0)), int(entrance_data.get("y", 0)))
        if entrance not in roads:
            return set()
        reached = {entrance}
        queue = deque([entrance])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                neighbor = (x + dx, y + dy)
                if neighbor in roads and neighbor not in reached:
                    reached.add(neighbor)
                    queue.append(neighbor)
        return reached

    def terrain_conflicts(
        self,
        plan: Dict[str, object],
        base_grid: Optional[List[List[str]]],
    ) -> List[Position]:
        if not base_grid:
            return []
        occupied = set(self.road_positions(plan))
        for building in plan.get("buildings", {}).values():
            occupied.update(
                settlement_rect_tiles(
                    int(building["x"]),
                    int(building["y"]),
                    int(building["width"]),
                    int(building["height"]),
                )
            )
        conflicts = []
        for x, y in occupied:
            if not (0 <= y < len(base_grid) and 0 <= x < len(base_grid[y])):
                conflicts.append((x, y))
            elif str(base_grid[y][x]) in SETTLEMENT_BLOCKING_TERRAIN:
                conflicts.append((x, y))
        return sorted(conflicts, key=lambda pos: (pos[1], pos[0]))

    def validate(
        self,
        plan: Dict[str, object],
        base_grid: Optional[List[List[str]]] = None,
    ) -> Dict[str, List[str]]:
        errors: List[str] = []
        warnings: List[str] = []
        width, height = int(plan.get("width", 0)), int(plan.get("height", 0))
        roads = self.road_positions(plan)
        connected = self.connected_road_positions(plan)
        entrance_data = plan.get("entrance", {})
        entrance = (int(entrance_data.get("x", -1)), int(entrance_data.get("y", -1)))
        if entrance not in roads:
            errors.append("The settlement entrance is not connected to a road.")
        if roads and connected != roads:
            errors.append(f"{len(roads - connected)} road tile(s) are disconnected from the entrance.")
        lots = list(plan.get("lots", {}).values())
        for index, lot in enumerate(lots):
            if (
                int(lot["x"]) < 1
                or int(lot["y"]) < 1
                or int(lot["x"]) + int(lot["width"]) >= width
                or int(lot["y"]) + int(lot["height"]) >= height
            ):
                errors.append(f"Lot {lot.get('name', lot.get('id'))} is outside settlement bounds.")
            for other in lots[index + 1:]:
                if settlement_rects_overlap(lot, other):
                    errors.append(f"Lots {lot.get('id')} and {other.get('id')} overlap.")
        occupied: Set[Position] = set()
        for building in plan.get("buildings", {}).values():
            tiles = settlement_rect_tiles(
                int(building["x"]),
                int(building["y"]),
                int(building["width"]),
                int(building["height"]),
            )
            if occupied & tiles:
                errors.append(f"Building {building.get('name')} overlaps another building.")
            occupied.update(tiles)
            access = (int(building.get("access_x", -1)), int(building.get("access_y", -1)))
            if access not in connected:
                errors.append(f"Building {building.get('name')} has no connected road access.")
        type_ids = [str(building.get("type_id", "")) for building in plan.get("buildings", {}).values()]
        if "town_hall" not in type_ids:
            warnings.append("No Town Hall is planned.")
        if "well" not in type_ids:
            warnings.append("No public well is planned.")
        if type_ids.count("home") < 2:
            warnings.append("Fewer than two homes are planned.")
        conflicts = self.terrain_conflicts(plan, base_grid)
        if conflicts:
            warnings.append(f"Blueprint intersects {len(conflicts)} blocking wilderness tile(s).")
        return {"errors": errors, "warnings": warnings}

    def summary(self, plan: Dict[str, object]) -> Dict[str, object]:
        buildings = list(plan.get("buildings", {}).values())
        complete = [
            building
            for building in buildings
            if int(building.get("phase_index", 0)) >= 3
        ]
        capacity = sum(
            int(SETTLEMENT_BUILDING_CATALOG.get(str(building.get("type_id")), {}).get("capacity", 0))
            for building in complete
        )
        services = sum(
            int(SETTLEMENT_BUILDING_CATALOG.get(str(building.get("type_id")), {}).get("service", 0))
            for building in complete
        )
        completed_count = len(complete)
        if completed_count >= 10 and capacity >= 12 and services >= 12:
            tier = "Town"
        elif completed_count >= 6 and capacity >= 6:
            tier = "Village"
        elif completed_count >= 3:
            tier = "Hamlet"
        elif completed_count:
            tier = "Roadstead"
        else:
            tier = "Survey Camp"
        return {
            "tier": tier,
            "buildings_planned": len(buildings),
            "buildings_complete": completed_count,
            "housing_capacity": capacity,
            "service_score": services,
            "road_tiles": len(self.road_positions(plan)),
            "lots": len(plan.get("lots", {})),
            "queued": len(plan.get("construction_queue", [])),
        }

    def preview(
        self,
        plan: Dict[str, object],
        base_grid: Optional[List[List[str]]] = None,
        show_lots: bool = True,
    ) -> List[List[str]]:
        width, height = int(plan["width"]), int(plan["height"])
        if base_grid:
            grid = [list(row[:width]) + ["."] * max(0, width - len(row)) for row in base_grid[:height]]
            while len(grid) < height:
                grid.append(["." for _ in range(width)])
        else:
            grid = [["." for _ in range(width)] for _ in range(height)]
            for x in range(width):
                grid[0][x] = "#"
                grid[height - 1][x] = "#"
            for y in range(height):
                grid[y][0] = "#"
                grid[y][width - 1] = "#"
        if show_lots:
            for lot in plan.get("lots", {}).values():
                for x, y in settlement_rect_tiles(
                    int(lot["x"]),
                    int(lot["y"]),
                    int(lot["width"]),
                    int(lot["height"]),
                ):
                    if 0 <= y < height and 0 <= x < width and grid[y][x] not in {"#", "~"}:
                        grid[y][x] = ","
        for x, y in self.road_positions(plan):
            if 0 <= y < height and 0 <= x < width:
                grid[y][x] = ":"
        phase_symbols = {0: "p", 1: "f", 2: "b"}
        for building in plan.get("buildings", {}).values():
            phase_index = max(0, min(3, int(building.get("phase_index", 0))))
            catalog = SETTLEMENT_BUILDING_CATALOG[str(building["type_id"])]
            symbol = str(catalog["symbol"]) if phase_index >= 3 else phase_symbols[phase_index]
            for x, y in settlement_rect_tiles(
                int(building["x"]),
                int(building["y"]),
                int(building["width"]),
                int(building["height"]),
            ):
                if 0 <= y < height and 0 <= x < width:
                    grid[y][x] = symbol
            door_x, door_y = int(building["door_x"]), int(building["door_y"])
            if 0 <= door_y < height and 0 <= door_x < width:
                grid[door_y][door_x] = "D"
        entrance = plan.get("entrance", {})
        entrance_x, entrance_y = int(entrance.get("x", 0)), int(entrance.get("y", 0))
        if 0 <= entrance_y < height and 0 <= entrance_x < width:
            grid[entrance_y][entrance_x] = "S"
        if base_grid:
            for x, y in self.terrain_conflicts(plan, base_grid):
                if 0 <= y < height and 0 <= x < width:
                    grid[y][x] = "!"
        return grid


class TownBuilderMixin:
    """FarmGame integration helpers; no authored or live map mutation."""

    def wilderness_town_builder(self) -> WildernessTownBuilder:
        builder = getattr(self, "_wilderness_town_builder", None)
        if not isinstance(builder, WildernessTownBuilder):
            builder = WildernessTownBuilder()
            self._wilderness_town_builder = builder
        return builder

    def ensure_wilderness_settlements(self) -> Dict[str, Dict[str, object]]:
        settlements = getattr(self.state, "wilderness_settlements", None)
        if not isinstance(settlements, dict):
            settlements = sanitize_wilderness_settlements(settlements)
            self.state.wilderness_settlements = settlements
        return settlements

    def create_wilderness_settlement_plan(
        self,
        chunk_x: int,
        chunk_y: int,
        style: str = "Crossroads",
        name: str = "",
        replace: bool = False,
    ) -> Dict[str, object]:
        settlements = self.ensure_wilderness_settlements()
        key = settlement_chunk_key(chunk_x, chunk_y)
        if key in settlements and not replace:
            return settlements[key]
        seed = int(getattr(self.state, "wilderness_seed", 1337)) + int(chunk_x) * 92821 + int(chunk_y) * 68917
        plan = self.wilderness_town_builder().create_plan(
            chunk_x,
            chunk_y,
            seed,
            name=name,
            style=style,
        )
        settlements[key] = plan
        return plan

    def wilderness_settlement_plan(
        self,
        chunk_x: int,
        chunk_y: int,
    ) -> Optional[Dict[str, object]]:
        return self.ensure_wilderness_settlements().get(settlement_chunk_key(chunk_x, chunk_y))

    def wilderness_settlement_preview(
        self,
        chunk_x: int,
        chunk_y: int,
        over_wilderness: bool = False,
    ) -> List[List[str]]:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            return []
        base_grid = None
        if over_wilderness:
            base_grid = copy.deepcopy(self.get_wilderness_chunk_map(chunk_x, chunk_y))
        return self.wilderness_town_builder().preview(plan, base_grid=base_grid)

    def wilderness_settlement_validation(
        self,
        chunk_x: int,
        chunk_y: int,
        check_terrain: bool = True,
    ) -> Dict[str, List[str]]:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            return {"errors": ["No settlement blueprint exists for this chunk."], "warnings": []}
        base_grid = (
            copy.deepcopy(self.get_wilderness_chunk_map(chunk_x, chunk_y))
            if check_terrain
            else None
        )
        return self.wilderness_town_builder().validate(plan, base_grid=base_grid)

    def wilderness_settlement_report_lines(self, chunk_x: int, chunk_y: int) -> List[str]:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            return ["No wilderness settlement blueprint exists here."]
        summary = self.wilderness_town_builder().summary(plan)
        validation = self.wilderness_settlement_validation(chunk_x, chunk_y, check_terrain=True)
        lines = [
            "WILDERNESS SETTLEMENT BLUEPRINT",
            "",
            f"Name: {plan.get('name')}",
            f"Chunk: {settlement_chunk_key(chunk_x, chunk_y)}",
            f"Style: {plan.get('style')}",
            f"Status: {plan.get('status')}",
            f"Development: {summary['tier']}",
            f"Buildings: {summary['buildings_complete']}/{summary['buildings_planned']} complete",
            f"Housing capacity: {summary['housing_capacity']}",
            f"Service score: {summary['service_score']}",
            f"Roads: {summary['road_tiles']} tiles",
            f"Lots: {summary['lots']}",
            f"Construction queue: {summary['queued']}",
            "",
            "Validation:",
        ]
        lines.extend(f"- ERROR: {message}" for message in validation["errors"])
        lines.extend(f"- Warning: {message}" for message in validation["warnings"])
        if not validation["errors"] and not validation["warnings"]:
            lines.append("- Blueprint is structurally valid and terrain-clear.")
        lines.extend([
            "",
            "Isolation:",
            "- This is a saved blueprint only.",
            "- The authored town and live wilderness maps are unchanged.",
        ])
        return lines

    def plan_wilderness_settlement_road(
        self,
        chunk_x: int,
        chunk_y: int,
        start: Position,
        end: Position,
    ) -> int:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            return 0
        return self.wilderness_town_builder().add_road_line(plan, start, end)

    def zone_wilderness_settlement_lot(
        self,
        chunk_x: int,
        chunk_y: int,
        lot_id: str,
        x: int,
        y: int,
        width: int,
        height: int,
        zone: str,
        name: str = "",
    ) -> bool:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        return bool(
            plan
            and self.wilderness_town_builder().add_lot(
                plan,
                lot_id,
                x,
                y,
                width,
                height,
                zone,
                name=name,
            )
        )

    def place_wilderness_settlement_building(
        self,
        chunk_x: int,
        chunk_y: int,
        lot_id: str,
        type_id: str,
        building_id: str = "",
        name: str = "",
    ) -> str:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            return ""
        return self.wilderness_town_builder().place_building(
            plan,
            lot_id,
            type_id,
            building_id=building_id,
            name=name,
        )

    def show_wilderness_settlement_blueprint(self, chunk_x: int, chunk_y: int):
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            self.set_message("No settlement blueprint exists for that wilderness chunk.")
            return None
        preview = self.wilderness_settlement_preview(chunk_x, chunk_y, over_wilderness=False)
        lines = self.wilderness_settlement_report_lines(chunk_x, chunk_y)
        lines.extend([
            "",
            "Blueprint legend:",
            "- : road, D door, S settlement entrance",
            "- p planned, f foundation, b frame",
            "- completed buildings use their catalog symbol",
            "",
            "Map:",
        ])
        lines.extend("".join(row) for row in preview)
        return self.vertical_panel_view(
            f"{plan.get('name', 'Settlement')} Blueprint",
            lines,
            max(88, int(plan.get("width", 86)) + 2),
            max(38, int(plan.get("height", 38)) + 12),
        )

    def queue_wilderness_settlement_building(
        self,
        chunk_x: int,
        chunk_y: int,
        building_id: str,
    ) -> bool:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        return bool(plan and self.wilderness_town_builder().queue_building(plan, building_id))

    def contribute_to_wilderness_settlement(
        self,
        chunk_x: int,
        chunk_y: int,
        building_id: str,
        use_available: bool = True,
    ) -> Dict[str, object]:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            return {"materials": {}, "money": 0}
        building = plan.get("buildings", {}).get(str(building_id))
        if not isinstance(building, dict):
            return {"materials": {}, "money": 0}
        requirements = settlement_phase_requirements(building)
        existing = building.get("material_contributions", {})
        offered: Dict[str, int] = {}
        if use_available:
            for item, amount in requirements["materials"].items():
                needed = max(0, int(amount) - int(existing.get(item, 0)))
                offered[item] = min(needed, int(self.state.inventory.get(item, 0)))
        money_needed = max(0, int(requirements["money"]) - int(building.get("money_contributed", 0)))
        money_offered = min(money_needed, int(self.state.money)) if use_available else 0
        accepted = self.wilderness_town_builder().contribute(
            plan,
            building_id,
            materials=offered,
            money=money_offered,
        )
        for item, amount in accepted["materials"].items():
            self.state.inventory[item] = max(0, int(self.state.inventory.get(item, 0)) - int(amount))
            if self.state.inventory[item] <= 0:
                self.state.inventory.pop(item, None)
        self.state.money = max(0, int(self.state.money) - int(accepted["money"]))
        return accepted

    def advance_wilderness_settlement_construction(
        self,
        chunk_x: int,
        chunk_y: int,
        labor: int,
    ) -> List[str]:
        plan = self.wilderness_settlement_plan(chunk_x, chunk_y)
        if not plan:
            return []
        return self.wilderness_town_builder().apply_labor(plan, labor)


__all__ = [
    "SETTLEMENT_BLOCKING_TERRAIN",
    "SETTLEMENT_BUILDING_CATALOG",
    "SETTLEMENT_PHASES",
    "SETTLEMENT_PLAN_VERSION",
    "SETTLEMENT_STYLES",
    "SETTLEMENT_ZONES",
    "TownBuilderMixin",
    "WildernessTownBuilder",
    "parse_settlement_coord",
    "sanitize_wilderness_settlements",
    "settlement_building_phase",
    "settlement_chunk_key",
    "settlement_coord_key",
    "settlement_phase_requirements",
]
