"""Interactive archaeology and paleontology field excavation."""

from __future__ import annotations

import hashlib
import random
from typing import Dict, List, Optional, Tuple

from ascii_farmstead_data import MENU_CONFIRM_KEYS
from ascii_farmstead_inventory import add_inventory_items
from ascii_farmstead_minigame_ui import (
    minigame_controls,
    minigame_meter,
    minigame_notice,
    minigame_section,
    minigame_title,
    minigame_tool_strip,
)
from ascii_farmstead_support import (
    C,
    clear_screen,
    colorize,
    movement_delta_for_key,
    normalize_key,
    read_key,
)


EXCAVATION_FIND_DATA: Dict[str, Dict[str, object]] = {
    "Painted Pottery Sherd": {
        "discipline": "archaeology", "rarity": 1, "fragility": 2, "value": 72,
        "description": "A painted ceramic fragment whose pigments preserve a domestic scene.",
    },
    "Clay Seal": {
        "discipline": "archaeology", "rarity": 1, "fragility": 2, "value": 88,
        "description": "A fired-clay seal impressed with the mark of an old household.",
    },
    "Bronze Brooch": {
        "discipline": "archaeology", "rarity": 2, "fragility": 1, "value": 125,
        "description": "A green-patinated clasp shaped like a curling leaf.",
    },
    "Inscribed Tablet Fragment": {
        "discipline": "archaeology", "rarity": 3, "fragility": 3, "value": 190,
        "description": "A stone fragment carrying several carefully cut lines of old writing.",
    },
    "Ritual Bead Strand": {
        "discipline": "archaeology", "rarity": 2, "fragility": 3, "value": 142,
        "description": "Tiny stone and glass beads recovered together before their cord vanished.",
    },
    "Merchant Weights": {
        "discipline": "archaeology", "rarity": 2, "fragility": 1, "value": 118,
        "description": "A nested set of trade weights that reveals an older system of measures.",
    },
    "Ancient Farm Implement": {
        "discipline": "archaeology", "rarity": 2, "fragility": 1, "value": 135,
        "description": "A hand tool worn smooth by agricultural work generations ago.",
    },
    "Mosaic Tesserae": {
        "discipline": "archaeology", "rarity": 1, "fragility": 2, "value": 82,
        "description": "Several colored stone cubes whose original mosaic can only be imagined.",
    },
    "Fern Impression": {
        "discipline": "paleontology", "rarity": 1, "fragility": 3, "value": 78,
        "description": "A delicate fern frond pressed into stone by an ancient wetland.",
    },
    "Trilobite Cast": {
        "discipline": "paleontology", "rarity": 1, "fragility": 2, "value": 96,
        "description": "A complete cast of a segmented marine animal from a vanished sea.",
    },
    "Ammonite Mold": {
        "discipline": "paleontology", "rarity": 2, "fragility": 2, "value": 132,
        "description": "A spiral shell mold with chambers still sharply defined.",
    },
    "Fossilized Tooth": {
        "discipline": "paleontology", "rarity": 2, "fragility": 1, "value": 145,
        "description": "A mineralized tooth from a large and unfamiliar predator.",
    },
    "Ancient Fish Plate": {
        "discipline": "paleontology", "rarity": 3, "fragility": 3, "value": 205,
        "description": "Overlapping armored plates from a fish that lived in an ancient river.",
    },
    "Petrified Wood Sample": {
        "discipline": "paleontology", "rarity": 1, "fragility": 1, "value": 84,
        "description": "Wood grain preserved in stone, with growth rings still visible.",
    },
    "Giant Shell Fragment": {
        "discipline": "paleontology", "rarity": 2, "fragility": 2, "value": 138,
        "description": "A thick shell fragment from a creature much larger than modern relatives.",
    },
    "Trackway Slab": {
        "discipline": "paleontology", "rarity": 3, "fragility": 3, "value": 220,
        "description": "A slab preserving several footprints and the direction their maker traveled.",
    },
}

EXCAVATION_TOOLS: Tuple[Tuple[str, str], ...] = (
    ("survey", "Survey Probe"),
    ("brush", "Brush"),
    ("pick", "Rock Pick"),
    ("stabilize", "Stabilize"),
    ("recover", "Recover"),
)


def excavation_find_records(discipline: Optional[str] = None) -> List[Tuple[str, Dict[str, object]]]:
    rows = list(EXCAVATION_FIND_DATA.items())
    if discipline:
        rows = [row for row in rows if row[1].get("discipline") == discipline]
    return rows


class ExcavationMixin:
    """Shared persistent grid minigame for cultural and fossil fieldwork."""

    EXCAVATION_WIDTH = 7
    EXCAVATION_HEIGHT = 5

    def ensure_excavation_state(self) -> None:
        if not isinstance(getattr(self.state, "excavation_sites", None), dict):
            self.state.excavation_sites = {}
        if not isinstance(getattr(self.state, "excavation_discoveries", None), list):
            self.state.excavation_discoveries = []
        for field in ("excavation_exp", "archaeology_finds", "paleontology_finds"):
            try:
                setattr(self.state, field, max(0, int(getattr(self.state, field, 0) or 0)))
            except (TypeError, ValueError):
                setattr(self.state, field, 0)

    def excavation_level(self) -> int:
        self.ensure_excavation_state()
        return min(10, 1 + int(self.state.excavation_exp) // 120)

    def excavation_rank_name(self) -> str:
        level = self.excavation_level()
        if level >= 9:
            return "Master Field Researcher"
        if level >= 7:
            return "Senior Excavator"
        if level >= 5:
            return "Field Specialist"
        if level >= 3:
            return "Practiced Surveyor"
        return "Volunteer Excavator"

    def excavation_site_id(self, discipline: str, x: int, y: int, source: str) -> str:
        cx = int(getattr(self.state, "wilderness_chunk_x", 0))
        cy = int(getattr(self.state, "wilderness_chunk_y", 0))
        return f"{discipline}:{source}:{cx},{cy}:{int(x)},{int(y)}"

    def _excavation_seed(self, site_id: str, week: str) -> int:
        text = f"{int(getattr(self.state, 'wilderness_seed', 0))}|{site_id}|{week}"
        return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)

    def _new_excavation_site(self, site_id: str, discipline: str, week: str) -> Dict[str, object]:
        rng = random.Random(self._excavation_seed(site_id, week))
        level = self.excavation_level()
        cells: List[Dict[str, object]] = []
        for _ in range(self.EXCAVATION_WIDTH * self.EXCAVATION_HEIGHT):
            if discipline == "paleontology":
                layers = rng.choices((2, 3, 4), weights=(3, 5, 2), k=1)[0]
                hardness = rng.choices((1, 2, 3), weights=(2, 5, 3), k=1)[0]
            else:
                layers = rng.choices((1, 2, 3), weights=(4, 5, 2), k=1)[0]
                hardness = rng.choices((1, 2), weights=(4, 2), k=1)[0]
            cells.append({
                "layers": layers,
                "hardness": hardness,
                "find_id": "",
                "condition": 100,
                "surveyed": False,
                "stabilized": False,
                "recovered": False,
            })

        candidates = excavation_find_records(discipline)
        find_count = 4 if discipline == "paleontology" else 5
        selected_cells = rng.sample(range(len(cells)), find_count)
        weighted_names: List[str] = []
        for name, data in candidates:
            weighted_names.extend([name] * max(1, 5 - int(data.get("rarity", 1))))
        used_names = set()
        for cell_index in selected_cells:
            available = [name for name in weighted_names if name not in used_names]
            if not available:
                available = list(weighted_names)
            find_name = rng.choice(available)
            used_names.add(find_name)
            cells[cell_index]["find_id"] = find_name

        care = (30 if discipline == "paleontology" else 27) + level * 2
        return {
            "id": site_id,
            "discipline": discipline,
            "week": week,
            "cells": cells,
            "care_remaining": care,
            "care_total": care,
            "actions": 0,
            "recovered_count": 0,
            "entry_fee_paid": False,
            "completed": False,
            "last_report": "Choose a square and survey before removing its layers.",
        }

    def excavation_site(self, discipline: str, x: int, y: int, source: str) -> Dict[str, object]:
        self.ensure_excavation_state()
        site_id = self.excavation_site_id(discipline, x, y, source)
        week = str(self.stronghold_cache_week_key())
        site = self.state.excavation_sites.get(site_id)
        if not isinstance(site, dict) or str(site.get("week")) != week:
            site = self._new_excavation_site(site_id, discipline, week)
            self.state.excavation_sites[site_id] = site
        return site

    def _excavation_cell(self, site: Dict[str, object], x: int, y: int) -> Optional[Dict[str, object]]:
        if not (0 <= x < self.EXCAVATION_WIDTH and 0 <= y < self.EXCAVATION_HEIGHT):
            return None
        cells = site.get("cells")
        if not isinstance(cells, list):
            return None
        index = y * self.EXCAVATION_WIDTH + x
        return cells[index] if index < len(cells) and isinstance(cells[index], dict) else None

    def excavation_site_finished(self, site: Dict[str, object]) -> bool:
        cells = site.get("cells") if isinstance(site.get("cells"), list) else []
        finds = [cell for cell in cells if isinstance(cell, dict) and cell.get("find_id")]
        return bool(finds) and all(bool(cell.get("recovered")) for cell in finds)

    def _excavation_survey_report(self, site: Dict[str, object], x: int, y: int) -> str:
        cell = self._excavation_cell(site, x, y)
        if not cell:
            return "The probe cannot read this square."
        if cell.get("find_id"):
            depth = int(cell.get("layers", 0))
            if self.excavation_level() >= 4:
                return f"Strong response: a find lies {depth} layer{'s' if depth != 1 else ''} down."
            return "Strong response directly beneath the probe."
        nearby = 0
        nearest_depth = 9
        for yy in range(max(0, y - 1), min(self.EXCAVATION_HEIGHT, y + 2)):
            for xx in range(max(0, x - 1), min(self.EXCAVATION_WIDTH, x + 2)):
                other = self._excavation_cell(site, xx, yy)
                if other and other.get("find_id") and not other.get("recovered"):
                    nearby += 1
                    nearest_depth = min(nearest_depth, int(other.get("layers", 0)))
        if nearby:
            depth_text = f"; shallowest response is {nearest_depth} layer(s) down" if self.excavation_level() >= 3 else ""
            return f"The probe detects {nearby} nearby response{'s' if nearby != 1 else ''}{depth_text}."
        return "No significant response in this square or its immediate neighbors."

    def _record_excavation_find(
        self, site: Dict[str, object], find_name: str, condition: int, context_score: int = 0,
    ) -> int:
        data = EXCAVATION_FIND_DATA.get(find_name, {})
        discipline = str(site.get("discipline", "archaeology"))
        rarity = max(1, int(data.get("rarity", 1)))
        context_bonus = min(18, max(0, int(context_score)) * 2) if discipline == "archaeology" else 0
        xp = 12 + rarity * 8 + max(0, int(condition)) // 10 + context_bonus
        add_inventory_items(self.state.inventory, {find_name: 1})
        self.state.excavation_exp += xp
        counter_name = f"{discipline}_finds"
        setattr(self.state, counter_name, int(getattr(self.state, counter_name, 0) or 0) + 1)
        self.state.excavation_discoveries.append({
            "item": find_name,
            "discipline": discipline,
            "condition": max(0, min(100, int(condition))),
            "quality": self.excavation_condition_label(condition),
            "context_score": max(0, int(context_score)),
            "site_id": str(site.get("id", "")),
            "week": str(site.get("week", "")),
            "year": int(getattr(self.state, "year", 1)),
            "season": str(getattr(self.state, "season", "")),
        })
        self.state.excavation_discoveries = self.state.excavation_discoveries[-200:]
        return xp

    @staticmethod
    def excavation_condition_label(condition: int) -> str:
        condition = int(condition)
        if condition >= 90:
            return "Museum-grade"
        if condition >= 70:
            return "Well preserved"
        if condition >= 45:
            return "Weathered"
        return "Fragmentary"

    def excavation_apply_action(
        self, site: Dict[str, object], x: int, y: int, action: str,
    ) -> Dict[str, object]:
        """Apply one testable excavation action without reading input or advancing time."""
        self.ensure_excavation_state()
        result: Dict[str, object] = {"success": False, "minutes": 0, "message": ""}
        if bool(site.get("completed")) or int(site.get("care_remaining", 0)) <= 0:
            result["message"] = "This week's field session is complete."
            return result
        cell = self._excavation_cell(site, x, y)
        if not cell:
            result["message"] = "That square is outside the excavation grid."
            return result

        cost = 1
        message = ""
        action = str(action)
        if action == "survey":
            cell["surveyed"] = True
            message = self._excavation_survey_report(site, x, y)
        elif action == "brush":
            layers = int(cell.get("layers", 0))
            if layers <= 0:
                result["message"] = "The square is already exposed; stabilize or recover any find."
                return result
            cell["layers"] = layers - 1
            if int(cell["layers"]) == 0 and cell.get("find_id"):
                message = f"Brushwork reveals {cell['find_id']} in good condition."
            elif int(cell["layers"]) == 0:
                message = "The cleared square contains only ordinary matrix."
            else:
                message = f"Removed one layer carefully; {cell['layers']} remain."
        elif action == "pick":
            layers = int(cell.get("layers", 0))
            if layers <= 0:
                result["message"] = "There is no covering matrix left to pick through."
                return result
            removed = min(2, layers)
            cell["layers"] = layers - removed
            damage = 0
            if int(cell["layers"]) == 0 and cell.get("find_id") and not cell.get("stabilized"):
                fragility = int(EXCAVATION_FIND_DATA.get(str(cell["find_id"]), {}).get("fragility", 1))
                protection = min(12, (self.excavation_level() - 1) * 2)
                if cell.get("surveyed"):
                    protection += 5
                damage = max(0, 9 + fragility * 7 + int(cell.get("hardness", 1)) * 3 - protection)
                cell["condition"] = max(20, int(cell.get("condition", 100)) - damage)
            if int(cell["layers"]) == 0 and cell.get("find_id"):
                message = f"The pick exposes {cell['find_id']}."
                if damage:
                    message += f" Fast work reduced its condition by {damage}%."
            elif int(cell["layers"]) == 0:
                message = "The pick clears the square; no find is present."
            else:
                message = f"The pick removes {removed} layers; {cell['layers']} remain."
        elif action == "stabilize":
            if int(cell.get("layers", 0)) > 0 or not cell.get("find_id") or cell.get("recovered"):
                result["message"] = "Only an exposed, unrecovered find can be stabilized."
                return result
            if cell.get("stabilized"):
                result["message"] = "This find is already stabilized."
                return result
            cell["stabilized"] = True
            message = f"Stabilized {cell['find_id']} for a safer recovery."
        elif action == "recover":
            if int(cell.get("layers", 0)) > 0 or not cell.get("find_id"):
                result["message"] = "There is no exposed find to recover here."
                return result
            if cell.get("recovered"):
                result["message"] = "That find has already been recovered."
                return result
            condition = int(cell.get("condition", 100))
            if not cell.get("stabilized"):
                fragility = int(EXCAVATION_FIND_DATA.get(str(cell["find_id"]), {}).get("fragility", 1))
                condition = max(20, condition - max(3, fragility * 5 - self.excavation_level()))
                cell["condition"] = condition
            cell["recovered"] = True
            site["recovered_count"] = int(site.get("recovered_count", 0)) + 1
            context_score = 0
            if str(site.get("discipline", "")) == "archaeology":
                for yy in range(max(0, y - 1), min(self.EXCAVATION_HEIGHT, y + 2)):
                    for xx in range(max(0, x - 1), min(self.EXCAVATION_WIDTH, x + 2)):
                        nearby = self._excavation_cell(site, xx, yy)
                        if nearby and nearby.get("surveyed"):
                            context_score += 1
            xp = self._record_excavation_find(
                site, str(cell["find_id"]), condition, context_score,
            )
            message = (
                f"Recovered {cell['find_id']} ({self.excavation_condition_label(condition)}, "
                f"{condition}%): +{xp} field XP."
            )
            if context_score:
                message += f" Context record: {context_score}/9 surveyed squares."
        else:
            result["message"] = "Unknown excavation action."
            return result

        remaining = max(0, int(site.get("care_remaining", 0)) - cost)
        site["care_remaining"] = remaining
        site["actions"] = int(site.get("actions", 0)) + 1
        site["last_report"] = message
        site["completed"] = self.excavation_site_finished(site) or remaining <= 0
        result.update({"success": True, "minutes": 5 * cost, "message": message})
        return result

    def excavation_cell_glyph(self, cell: Dict[str, object]) -> str:
        if cell.get("recovered"):
            return " . "
        layers = int(cell.get("layers", 0))
        if layers <= 0 and cell.get("find_id"):
            return " ! " if not cell.get("stabilized") else " + "
        if layers <= 0:
            return " _ "
        if cell.get("surveyed"):
            return f"?{min(9, layers)}?"
        return f"[{min(9, layers)}]"

    def excavation_status_lines(self) -> List[str]:
        self.ensure_excavation_state()
        discoveries = self.state.excavation_discoveries
        best = max((int(row.get("condition", 0)) for row in discoveries if isinstance(row, dict)), default=0)
        next_level = min(1200, self.excavation_level() * 120)
        return [
            "FIELD RESEARCH",
            "",
            f"Rank: {self.excavation_rank_name()} (level {self.excavation_level()})",
            f"Experience: {self.state.excavation_exp}/{next_level if self.excavation_level() < 10 else 'MAX'}",
            f"Archaeological finds: {self.state.archaeology_finds}",
            f"Paleontological finds: {self.state.paleontology_finds}",
            f"Best recovered condition: {best}%" if discoveries else "Best recovered condition: no finds yet",
            "",
            "Recovered finds can be sold, stored, or donated to the Museum.",
            "Sites refresh weekly, while unfinished work persists when you leave.",
        ]

    def excavation_journal_lines(self) -> List[str]:
        lines = self.excavation_status_lines()
        current_week = str(self.stronghold_cache_week_key())
        active_sites = [
            site
            for site in self.state.excavation_sites.values()
            if isinstance(site, dict)
            and str(site.get("week", "")) == current_week
            and not bool(site.get("completed"))
            and int(site.get("care_remaining", 0) or 0) > 0
            and bool(site.get("entry_fee_paid"))
        ]
        lines.extend(["", f"Active trenches this week: {len(active_sites)}", "", "Recent finds:"])
        discoveries = [
            row for row in self.state.excavation_discoveries
            if isinstance(row, dict)
        ]
        if not discoveries:
            lines.append("- No field discoveries recorded yet.")
            return lines
        donated = set(self.museum_donated_record_ids())
        for row in reversed(discoveries[-12:]):
            item_name = str(row.get("item", "Unknown find"))
            discipline = str(row.get("discipline", "archaeology"))
            record_id = self.museum_record_id(discipline, item_name)
            museum_text = "donated" if record_id in donated else "not donated"
            lines.append(
                f"- {item_name}: {int(row.get('condition', 0) or 0)}% "
                f"({row.get('quality', 'recorded')}; {museum_text})"
            )
            if discipline == "archaeology" and int(row.get("context_score", 0) or 0) > 0:
                lines.append(f"  Context: {int(row.get('context_score', 0) or 0)}/9 nearby squares surveyed.")
        return lines

    def _draw_excavation(
        self, site: Dict[str, object], cursor_x: int, cursor_y: int, tool_index: int,
    ) -> None:
        discipline = str(site.get("discipline", "archaeology"))
        title = "ARCHAEOLOGICAL EXCAVATION" if discipline == "archaeology" else "PALEONTOLOGICAL DIG"
        clear_screen()
        minigame_title(
            title,
            f"{self.excavation_rank_name()} | Finds recovered {site.get('recovered_count', 0)}",
        )
        print(minigame_meter(
            "Field care",
            int(site.get("care_remaining", 0)),
            int(site.get("care_total", 1)),
            width=24,
        ))
        minigame_section("Excavation grid", "depth numbers | ? surveyed | ! exposed | + stabilized")
        for y in range(self.EXCAVATION_HEIGHT):
            row: List[str] = []
            for x in range(self.EXCAVATION_WIDTH):
                cell = self._excavation_cell(site, x, y) or {}
                glyph = self.excavation_cell_glyph(cell)
                if x == cursor_x and y == cursor_y:
                    glyph = colorize(f">{glyph[1]}<", "\033[7m")
                elif cell.get("recovered"):
                    glyph = colorize(glyph, C.UI_MUTED)
                elif int(cell.get("layers", 0)) <= 0 and cell.get("find_id"):
                    glyph = colorize(glyph, C.LANDMARK_RESEARCH)
                elif cell.get("surveyed"):
                    glyph = colorize(glyph, C.UI_SELECTED)
                row.append(glyph)
            print("  " + " ".join(row))
        tool_name = EXCAVATION_TOOLS[tool_index][1]
        cell = self._excavation_cell(site, cursor_x, cursor_y) or {}
        layers = int(cell.get("layers", 0))
        if cell.get("recovered"):
            cell_state = "recovered"
            recommendation = "Move to another square"
        elif layers <= 0 and cell.get("find_id") and cell.get("stabilized"):
            cell_state = "stabilized find"
            recommendation = "Recover"
        elif layers <= 0 and cell.get("find_id"):
            cell_state = "exposed find"
            recommendation = "Stabilize"
        elif not cell.get("surveyed"):
            cell_state = f"unsurveyed, depth {layers}"
            recommendation = "Survey Probe"
        else:
            cell_state = f"surveyed, depth {layers}"
            recommendation = "Brush" if layers <= 2 else "Rock Pick"
        minigame_section("Field tools", f"selected: {tool_name}")
        minigame_tool_strip([label for _value, label in EXCAVATION_TOOLS], tool_index)
        minigame_notice(
            f"({cursor_x + 1},{cursor_y + 1}) {cell_state} | Suggested: {recommendation}",
            prefix="CURSOR",
        )
        minigame_notice(site.get("last_report", ""))
        minigame_controls(
            "WASD/arrows/numpad: move",
            "Q/E: cycle tool",
            "1-5: choose tool",
            "R: suggested tool",
            "Z/Enter/Space: use",
            "H: field guide",
            "B/X/Esc/Tab: leave",
        )

    def _show_excavation_help(self, discipline: str) -> None:
        clear_screen()
        title = "ARCHAEOLOGY FIELD GUIDE" if discipline == "archaeology" else "PALEONTOLOGY FIELD GUIDE"
        print(colorize(title, C.UI_TITLE))
        print("")
        print("Survey Probe: reads the selected square and nearby responses.")
        print("Brush: removes one layer safely.")
        print("Rock Pick: removes two layers, but may damage a fragile find when exposed.")
        print("Stabilize: protects an exposed find before recovery.")
        print("Recover: adds an exposed find to your backpack and field journal.")
        print("")
        if discipline == "archaeology":
            print("Archaeological layers are usually shallow. Surveying helps preserve the")
            print("relationship between household objects, trade goods, and old structures.")
        else:
            print("Fossils lie in deeper, harder stone. Picks conserve field time, while")
            print("brushes and stabilizer protect delicate impressions and trackways.")
        print("")
        print("Higher field-research levels improve surveys and reduce pick damage.")
        print("Use 1-5 to choose tools directly. R selects the recommended tool for")
        print("the current square; confirm with Z, Enter, or Space.")
        print("Press any key to return.")
        read_key()

    def launch_excavation_minigame(
        self, discipline: str, x: int, y: int, source: str,
    ) -> bool:
        site = self.excavation_site(discipline, x, y, source)
        if bool(site.get("completed")) or int(site.get("care_remaining", 0)) <= 0:
            self.set_message("This site's safe fieldwork is complete until next week's survey cycle.")
            return False
        if not bool(site.get("entry_fee_paid")):
            stamina_cost = 5 if discipline == "paleontology" else 4
            if not self.spend_stamina(stamina_cost):
                return False
            site["entry_fee_paid"] = True

        cursor_x = self.EXCAVATION_WIDTH // 2
        cursor_y = self.EXCAVATION_HEIGHT // 2
        tool_index = 0
        changed = False
        elapsed_minutes = 0
        while True:
            self._draw_excavation(site, cursor_x, cursor_y, tool_index)
            key = normalize_key(read_key())
            delta = movement_delta_for_key(key)
            if delta:
                cursor_x = max(0, min(self.EXCAVATION_WIDTH - 1, cursor_x + delta[0]))
                cursor_y = max(0, min(self.EXCAVATION_HEIGHT - 1, cursor_y + delta[1]))
                continue
            if key == "q":
                tool_index = (tool_index - 1) % len(EXCAVATION_TOOLS)
                continue
            if key == "e":
                tool_index = (tool_index + 1) % len(EXCAVATION_TOOLS)
                continue
            if key in {"1", "2", "3", "4", "5"}:
                tool_index = int(key) - 1
                continue
            if key == "r":
                cell = self._excavation_cell(site, cursor_x, cursor_y) or {}
                layers = int(cell.get("layers", 0))
                action = (
                    "recover" if layers <= 0 and cell.get("find_id") and cell.get("stabilized")
                    else "stabilize" if layers <= 0 and cell.get("find_id")
                    else "survey" if not cell.get("surveyed")
                    else "brush" if layers <= 2
                    else "pick"
                )
                tool_index = next(
                    index for index, (value, _label) in enumerate(EXCAVATION_TOOLS)
                    if value == action
                )
                continue
            if key == "h":
                self._show_excavation_help(discipline)
                continue
            if key in {"b", "x", "\x1b", "\t"}:
                break
            if key in MENU_CONFIRM_KEYS:
                action = EXCAVATION_TOOLS[tool_index][0]
                result = self.excavation_apply_action(site, cursor_x, cursor_y, action)
                if result.get("success"):
                    changed = True
                    elapsed_minutes += int(result.get("minutes", 5))
                else:
                    site["last_report"] = str(result.get("message", "That action cannot be used here."))
                if bool(site.get("completed")):
                    break

        if changed:
            self.advance_time(elapsed_minutes)
            complete_text = (
                " The field session is complete for this week."
                if bool(site.get("completed"))
                else " You can resume this trench later in the week."
            )
            self.autosave_with_message(
                f"Fieldwork recovered {site.get('recovered_count', 0)} find(s).{complete_text}"
            )
        else:
            self.set_message("Left the excavation site without disturbing it.")
        return changed
