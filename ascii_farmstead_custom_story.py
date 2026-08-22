from __future__ import annotations

"""Custom quest authoring and built-in dialogue override tools."""

import ast
import copy
import hashlib
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ascii_farmstead_custom_content import (
    custom_content_file_signature,
    load_custom_content,
    save_custom_content,
    sanitize_custom_quest,
    sanitize_dialogue_override,
)
from ascii_farmstead_helpers import quantity_item_phrase
from ascii_farmstead_ui import MenuItem, menu_select, text_entry_menu


MENU_BACK = "__back__"

CUSTOM_QUEST_KINDS = (
    "visit", "item", "money", "defeat", "loot", "craft", "fish", "harvest", "talk",
)
CUSTOM_QUEST_KIND_LABELS = {
    "visit": "Reach a location",
    "item": "Bring or possess an item",
    "money": "Carry a required amount of money",
    "defeat": "Defeat an enemy",
    "loot": "Recover an item from a container",
    "craft": "Craft an item",
    "fish": "Catch a fish",
    "harvest": "Harvest a crop",
    "talk": "Speak with a person",
}
CUSTOM_QUEST_CATEGORIES = (
    "General", "Personal", "Relationships", "Household", "Town",
    "Politics", "Wilderness", "Business", "Bounties",
)

DIALOGUE_VARIABLE_DESCRIPTIONS = {
    "player": "The current player character's name.",
    "npc": "The speaking character's name.",
    "role": "The speaking character's role or occupation.",
    "location": "The player's current location.",
    "season": "The current season.",
    "weather": "The current weather.",
    "time": "The current in-game time.",
    "date": "The current calendar date.",
    "money": "The player's current money.",
    "relationship": "The speaker's current relationship value when available.",
    "activity": "The speaker's current activity or routine.",
    "home": "The household's current home label.",
    "children": "The number of children in the player's household.",
}

DIALOGUE_SOURCE_NAMES = (
    "ascii_farmstead_dialogue.py",
    "ascii_farmstead_dialogue_library.py",
    "ascii_farmstead_relationship_dialogue.py",
    "ascii_farmstead_npc_dialogue.py",
    "ascii_farmstead_npcs.py",
    "ascii_farmstead_family_world.py",
    "ascii_farmstead_npc_families.py",
    "ascii_farmstead_npc_builder.py",
    "ascii_farmstead_quests.py",
)

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_CATALOG_CACHE: Optional[List[Dict[str, object]]] = None
_OVERRIDE_CACHE_SIGNATURE: object = object()
_OVERRIDE_EXACT: Dict[str, Dict[str, object]] = {}
_OVERRIDE_DYNAMIC: List[Tuple[re.Pattern[str], Dict[str, object]]] = []


class _SafeVariables(dict):
    def __missing__(self, key: str) -> str:
        return "{" + str(key) + "}"


def _normalized_text(value: object, maximum: int = 700) -> str:
    return " ".join(str(value or "").strip().split())[:maximum]


def _slug(value: object) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")
    return (result or "quest")[:64]


def dialogue_variable_context(game, actor: Optional[Mapping[str, object]] = None) -> Dict[str, str]:
    actor = actor or {}
    state = getattr(game, "state", None)
    npc_id = str(actor.get("id", "") or "")
    relationship = str(actor.get("relationship", actor.get("bond", 0)) or 0)
    if npc_id and hasattr(game, "town_npc_relationship"):
        try:
            relationship = str(game.town_npc_relationship(npc_id))
        except (TypeError, ValueError):
            pass
    if hasattr(game, "dialogue_activity"):
        try:
            activity = str(game.dialogue_activity(dict(actor), str(actor.get("_dialogue_kind", "authored"))))
        except (TypeError, ValueError):
            activity = str(actor.get("activity", "following today's routine"))
    else:
        activity = str(actor.get("activity", "following today's routine"))
    home = "the household"
    if hasattr(game, "family_household_home_label"):
        try:
            home = str(game.family_household_home_label())
        except (TypeError, ValueError):
            pass
    hour = int(getattr(state, "hour", 6) or 0)
    minute = int(getattr(state, "minute", 0) or 0)
    return {
        "player": str(getattr(state, "player_name", "Player") or "Player"),
        "npc": str(actor.get("name", "Current NPC") or "Current NPC"),
        "role": str(actor.get("role", actor.get("occupation", "Resident")) or "Resident"),
        "location": str(getattr(state, "location", "Elsewhere") or "Elsewhere"),
        "season": str(getattr(state, "season", "Spring") or "Spring"),
        "weather": str(getattr(state, "weather", "Clear") or "Clear"),
        "time": f"{hour:02d}:{minute:02d}",
        "date": f"Year {int(getattr(state, 'year', 1) or 1)}, Month {int(getattr(state, 'month', 1) or 1)}, Day {int(getattr(state, 'day', 1) or 1)}",
        "money": str(int(getattr(state, "money", 0) or 0)),
        "relationship": relationship,
        "activity": activity,
        "home": home,
        "children": str(len(getattr(state, "children", []) or [])),
    }


def render_dialogue_template(template: str, variables: Mapping[str, object]) -> str:
    values = _SafeVariables({key: str(value) for key, value in variables.items()})
    try:
        return _normalized_text(str(template).format_map(values))
    except (ValueError, KeyError):
        return _normalized_text(template)


def _expression_variable(node: ast.AST, used: set[str]) -> str:
    if isinstance(node, ast.Name):
        base = node.id
    elif isinstance(node, ast.Attribute):
        base = node.attr
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ):
        base = str(node.args[0].value)
    else:
        base = "value"
    base = re.sub(r"[^A-Za-z0-9_]", "_", base).strip("_") or "value"
    if base[0].isdigit():
        base = "value_" + base
    candidate = base
    number = 2
    while candidate in used:
        candidate = f"{base}_{number}"
        number += 1
    used.add(candidate)
    return candidate


def _node_text_template(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _normalized_text(node.value)
    if not isinstance(node, ast.JoinedStr):
        return ""
    used: set[str] = set()
    parts: List[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value))
        elif isinstance(value, ast.FormattedValue):
            parts.append("{" + _expression_variable(value.value, used) + "}")
    return _normalized_text("".join(parts))


def _catalog_category(filename: str) -> str:
    if "relationship" in filename:
        return "Romance & Family"
    if "library" in filename or "npc_dialogue" in filename:
        return "General NPC Dialogue"
    if "quests" in filename:
        return "Quest & Scene Narration"
    if "family" in filename:
        return "Household & Family"
    if "npcs" in filename or "npc_builder" in filename:
        return "NPC & Household"
    return "Conversation System"


def _source_file_path(filename: str) -> Optional[Path]:
    roots = [Path(__file__).resolve().parent]
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        roots.extend([Path(frozen_root), Path(frozen_root) / "dialogue_sources"])
    for root in roots:
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return None


class _DialogueCatalogVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, broad: bool):
        self.filename = filename
        self.broad = broad
        self.scope = "module"
        self.records: List[Dict[str, object]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        previous = self.scope
        self.scope = node.name
        permitted = self.broad or any(
            word in node.name.casefold()
            for word in ("dialogue", "talk", "conversation", "scene", "family", "child", "spouse", "marriage", "planned")
        )
        if permitted:
            for index, child in enumerate(node.body):
                if index == 0 and isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant) and isinstance(child.value.value, str):
                    continue
                self.visit(child)
        self.scope = previous

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self._record(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self._record(node)

    def _record(self, node: ast.AST) -> None:
        text = _node_text_template(node)
        if len(text) < 12 or " " not in text or not any(char.isalpha() for char in text):
            return
        if text.startswith(("Type to edit", "Choose one option", "Create, inspect", "B/X/Esc")):
            return
        category = _catalog_category(self.filename)
        kind = "Narration" if any(word in self.scope.casefold() for word in ("scene", "narrat")) else "Dialogue"
        identity = f"{self.filename}:{self.scope}:{text}"
        source_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        self.records.append({
            "source_id": source_id,
            "source_text": text,
            "category": category,
            "kind": kind,
            "scope": self.scope,
            "source_file": self.filename,
            "line": int(getattr(node, "lineno", 0) or 0),
            "variables": sorted(set(_PLACEHOLDER_RE.findall(text))),
        })


def dialogue_source_catalog(refresh: bool = False) -> List[Dict[str, object]]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None and not refresh:
        return [dict(row) for row in _CATALOG_CACHE]
    records: List[Dict[str, object]] = []
    broad_names = {
        "ascii_farmstead_dialogue_library.py",
        "ascii_farmstead_relationship_dialogue.py",
        "ascii_farmstead_npc_dialogue.py",
    }
    for filename in DIALOGUE_SOURCE_NAMES:
        path = _source_file_path(filename)
        if path is None:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=filename)
        except (OSError, SyntaxError, UnicodeError):
            continue
        visitor = _DialogueCatalogVisitor(filename, filename in broad_names)
        visitor.visit(tree)
        records.extend(visitor.records)
    unique: Dict[Tuple[str, str], Dict[str, object]] = {}
    for record in records:
        key = (str(record.get("category", "")), str(record.get("source_text", "")))
        unique.setdefault(key, record)
    _CATALOG_CACHE = sorted(
        unique.values(),
        key=lambda row: (str(row.get("category")), str(row.get("kind")), str(row.get("source_text"))),
    )
    return [dict(row) for row in _CATALOG_CACHE]


def _template_pattern(template: str) -> Optional[re.Pattern[str]]:
    matches = list(_PLACEHOLDER_RE.finditer(template))
    if not matches:
        return None
    parts: List[str] = ["^"]
    cursor = 0
    seen: set[str] = set()
    for match in matches:
        parts.append(re.escape(template[cursor:match.start()]))
        name = match.group(1)
        if name in seen:
            parts.append(f"(?P={name})")
        else:
            parts.append(f"(?P<{name}>.+?)")
            seen.add(name)
        cursor = match.end()
    parts.extend([re.escape(template[cursor:]), "$"])
    try:
        return re.compile("".join(parts))
    except re.error:
        return None


def _dialogue_override_index() -> Tuple[Dict[str, Dict[str, object]], List[Tuple[re.Pattern[str], Dict[str, object]]]]:
    global _OVERRIDE_CACHE_SIGNATURE, _OVERRIDE_EXACT, _OVERRIDE_DYNAMIC
    signature = custom_content_file_signature()
    if signature == _OVERRIDE_CACHE_SIGNATURE:
        return _OVERRIDE_EXACT, _OVERRIDE_DYNAMIC
    content, _warnings = load_custom_content()
    exact: Dict[str, Dict[str, object]] = {}
    dynamic: List[Tuple[re.Pattern[str], Dict[str, object]]] = []
    for record in content.get("dialogue_overrides", []):
        if not isinstance(record, dict) or not bool(record.get("enabled", True)):
            continue
        source = _normalized_text(record.get("source_text"))
        pattern = _template_pattern(source)
        if pattern is None:
            exact[source] = record
        else:
            dynamic.append((pattern, record))
    _OVERRIDE_CACHE_SIGNATURE = signature
    _OVERRIDE_EXACT = exact
    _OVERRIDE_DYNAMIC = dynamic
    return exact, dynamic


def apply_custom_dialogue_override(text: str, variables: Mapping[str, object]) -> str:
    line = _normalized_text(text)
    exact, dynamic = _dialogue_override_index()
    record = exact.get(line)
    values = dict(variables)
    if record is None:
        for pattern, candidate in dynamic:
            match = pattern.match(line)
            if match:
                record = candidate
                values.update(match.groupdict())
                break
    if record is None:
        return line
    return render_dialogue_template(str(record.get("text", line)), values)


def custom_quest_runtime_record(record: Mapping[str, object]) -> Dict[str, object]:
    clean = sanitize_custom_quest(dict(record))
    if clean is None:
        return {}
    objectives = []
    for index, source in enumerate(clean["objectives"]):
        objective = dict(source)
        objective.update({
            "id": str(source.get("id", f"objective_{index + 1}")),
            "current": 0,
            "complete": False,
            "destination": dict(source.get("destination", {}) or {}),
        })
        objectives.append(objective)
    return {
        "id": f"custom:{clean['id']}",
        "title": str(clean["name"]),
        "category": str(clean["category"]),
        "description": str(clean["description"]),
        "status": "offered",
        "giver_name": str(clean.get("giver_name", "Custom Quest Board")),
        "offer_text": str(clean.get("offer_text", "")),
        "completion_text": str(clean.get("completion_text", "")),
        "objectives": objectives,
        "turn_in": dict(clean.get("turn_in", {}) or {}),
        "require_turn_in": bool(clean.get("turn_in")),
        "completion_mode": str(clean.get("completion_mode", "claim")),
        "repeatable": bool(clean.get("repeatable", False)),
        "cooldown_days": int(clean.get("cooldown_days", 7) or 7),
        "prerequisite_ids": [f"custom:{value}" for value in clean.get("prerequisite_ids", [])],
        "rewards": dict(clean["rewards"]),
        "consume_items": {},
        "custom_managed": True,
        "custom_source_id": str(clean["id"]),
        "journal": [str(clean.get("offer_text") or "This quest was created through the Custom Content editor.")],
    }


def custom_quest_summary(record: Mapping[str, object]) -> List[str]:
    objectives = [row for row in record.get("objectives", []) if isinstance(row, dict)]
    rewards = dict(record.get("rewards", {}) or {})
    lines = [
        str(record.get("description", "")), "",
        f"Category: {record.get('category', 'General')}",
        f"Enabled: {'Yes' if record.get('enabled', True) else 'No'}",
        f"Quest giver: {record.get('giver_name', 'Custom Quest Board')}",
        f"Completion: {str(record.get('completion_mode', 'claim')).title()}",
        f"Repeatable: {'Yes' if record.get('repeatable') else 'No'}",
        "", f"Objectives ({len(objectives)}):",
    ]
    for index, objective in enumerate(objectives, 1):
        destination = dict(objective.get("destination", {}) or {})
        lines.extend([
            f"{index}. {objective.get('description', 'Complete the objective.')}",
            f"   {CUSTOM_QUEST_KIND_LABELS.get(str(objective.get('kind')), str(objective.get('kind', 'visit')).title())} x{objective.get('target', 1)}",
            f"   At: {destination.get('label', destination.get('location', 'Anywhere'))}",
        ])
    turn_in = dict(record.get("turn_in", {}) or {})
    lines.extend([
        "", f"Turn in: {turn_in.get('label', turn_in.get('location', 'Anywhere')) if turn_in else 'Anywhere'}",
        "", "Rewards:", f"- {int(rewards.get('money', 0) or 0)}g",
        f"- {int(rewards.get('xp', 0) or 0)} combat XP",
        f"- Reputation {int(rewards.get('reputation', 0) or 0):+d}",
    ])
    lines.extend(f"- {quantity_item_phrase(name, quantity)}" for name, quantity in dict(rewards.get("items", {}) or {}).items())
    return lines


class CustomStoryMenuMixin:
    def custom_story_number_entry(self, title: str, prompt: str, default: int, minimum: int, maximum: int) -> Optional[int]:
        raw = text_entry_menu(title, prompt, str(default), 12)
        if raw is None:
            return None
        try:
            value = int(raw)
        except ValueError:
            value = int(default)
        return max(int(minimum), min(int(maximum), value))

    def custom_quest_destination_menu(self, existing: Optional[Mapping[str, object]] = None) -> Optional[Dict[str, object]]:
        options = [
            MenuItem(label="Anywhere", value="anywhere", enabled=True, hint="objective progress is not restricted to one place"),
            MenuItem(label="Current player position", value="current", enabled=True, hint="capture the exact tile where the editor is opened"),
            MenuItem(label="Farm entrance", value="farm", enabled=hasattr(self, "home_world_destination_world_positions")),
            MenuItem(label="Starting town entrance", value="town", enabled=hasattr(self, "home_world_destination_world_positions")),
            MenuItem(label="Mine entrance", value="mine", enabled=hasattr(self, "home_world_destination_world_positions")),
            MenuItem(label="Wilderness chunk", value="chunk", enabled=hasattr(self, "wilderness_world_coords"), hint="enter persistent chunk coordinates"),
        ]
        if existing:
            options.append(MenuItem(label="Keep existing target", value="keep", enabled=True, hint=str(existing.get("label", "Marked location"))))
        options.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = menu_select("Quest Target Location", options, footer="Every custom quest has a physical tracked destination.", mouse_enabled=True)
        if choice is None or choice.value == MENU_BACK:
            return None
        if choice.value == "keep":
            return dict(existing or {})
        if choice.value == "anywhere":
            return {"label": "Anywhere"}
        if choice.value == "current":
            destination = dict(self.quest_capture_current_destination()) if hasattr(self, "quest_capture_current_destination") else {
                "location": str(getattr(self.state, "location", "Wilderness")),
                "x": int(getattr(self.state, "player_x", 0)), "y": int(getattr(self.state, "player_y", 0)),
            }
            destination["label"] = "Custom quest destination"
            return destination
        if choice.value in {"farm", "town", "mine"}:
            world = self.home_world_destination_world_positions().get(str(choice.value))
            if not world:
                return None
            return {
                "location": "Wilderness", "world_x": int(world[0]), "world_y": int(world[1]),
                "label": {"farm": "Farm entrance", "town": "Starting town entrance", "mine": "Mine entrance"}[str(choice.value)],
            }
        chunk_x = self.custom_story_number_entry("Wilderness Destination", "Chunk X coordinate?", 0, -999, 999)
        if chunk_x is None:
            return None
        chunk_y = self.custom_story_number_entry("Wilderness Destination", "Chunk Y coordinate?", 0, -999, 999)
        if chunk_y is None:
            return None
        world_x, world_y = self.wilderness_world_coords(int(chunk_x), int(chunk_y), 43, 19)
        return {
            "location": "Wilderness", "chunk_x": int(chunk_x), "chunk_y": int(chunk_y),
            "world_x": int(world_x), "world_y": int(world_y),
            "label": f"Wilderness chunk ({chunk_x}, {chunk_y})",
        }

    def custom_quest_objective_builder(
        self, existing: Optional[Mapping[str, object]] = None, index: int = 0,
    ) -> Optional[Dict[str, object]]:
        current = dict(existing or {})
        kind = self.custom_choice_menu(
            "Objective Type", CUSTOM_QUEST_KINDS, str(current.get("kind", "visit")),
            labels=CUSTOM_QUEST_KIND_LABELS,
        )
        if kind is None:
            return None
        target_name = ""
        target_tag = ""
        item = ""
        if kind == "item":
            item = text_entry_menu("Objective Target", "Required item name?", str(current.get("item", "Field Snack")), 80)
            if item is None:
                return None
            target_name = item
        elif kind not in {"visit", "money"}:
            match_mode = self.custom_choice_menu(
                "Target Matching", ("name", "tag"),
                "tag" if current.get("target_tag") and not current.get("target_name") else "name",
                labels={"name": "Exact target name", "tag": "Target category/tag"},
                hints={"name": "match one named NPC, enemy, item, crop, recipe, or fish", "tag": "match a gameplay category such as boss, crop, or fish"},
            )
            if match_mode is None:
                return None
            target_value = text_entry_menu(
                "Objective Target",
                "Exact name?" if match_mode == "name" else "Target tag/category?",
                str(current.get("target_name" if match_mode == "name" else "target_tag", "")), 80,
            )
            if target_value is None:
                return None
            if match_mode == "name":
                target_name = target_value
            else:
                target_tag = target_value
        target = 1 if kind == "visit" else self.custom_story_number_entry(
            "Objective Amount",
            "Required money?" if kind == "money" else "How many are required?",
            int(current.get("target", 1) or 1), 1, 999999,
        )
        if target is None:
            return None
        destination = self.custom_quest_destination_menu(dict(current.get("destination", {}) or {}))
        if destination is None:
            return None
        require_destination = str(destination.get("label", "")).casefold() != "anywhere"
        radius = int(current.get("destination_radius", 2) or 2)
        if require_destination:
            chosen_radius = self.custom_story_number_entry(
                "Objective Area", "How close must the player get, in tiles?", radius, 0, 20,
            )
            if chosen_radius is None:
                return None
            radius = chosen_radius
        consume = False
        if kind == "item":
            consume_choice = self.custom_choice_menu(
                "Required Item", ("keep", "consume"), "consume" if current.get("consume") else "keep",
                labels={"keep": "Player keeps the item", "consume": "Consume it when quest completes"},
            )
            if consume_choice is None:
                return None
            consume = consume_choice == "consume"
        default_description = {
            "visit": f"Reach {destination.get('label', 'the marked location')}.",
            "item": f"Bring {target} {item} to {destination.get('label', 'the marked location')}.",
            "money": f"Carry {target}g at {destination.get('label', 'the marked location')}.",
        }.get(kind, f"{CUSTOM_QUEST_KIND_LABELS[kind]}: {target_name or target_tag} ({target}).")
        description = text_entry_menu(
            "Objective Text", "Objective shown in the Quest Log?",
            str(current.get("description", default_description)), 220,
        )
        if description is None:
            return None
        return {
            "id": str(current.get("id", f"objective_{index + 1}")), "kind": kind,
            "description": description, "target": int(target), "target_name": target_name,
            "target_tag": target_tag, "item": item, "consume": consume,
            "destination": destination, "require_destination": require_destination,
            "destination_radius": radius,
        }

    def custom_quest_objectives_menu(self, objectives: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
        rows = [dict(row) for row in objectives if isinstance(row, Mapping)]
        while True:
            items = [MenuItem(label="Add objective", value="add", enabled=len(rows) < 12, hint="up to 12 sequential stages")]
            items.extend(
                MenuItem(
                    label=f"{index + 1}. {row.get('description', 'Objective')}", value=f"row:{index}", enabled=True,
                    hint=f"{CUSTOM_QUEST_KIND_LABELS.get(str(row.get('kind')), str(row.get('kind', '')).title())} | {dict(row.get('destination', {}) or {}).get('label', 'Anywhere')}",
                )
                for index, row in enumerate(rows)
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select("Quest Objectives", items, footer="Objectives are completed in this order.", extra_lines=[f"{len(rows)} of 12 stages"], mouse_enabled=True)
            if choice is None or choice.value == MENU_BACK:
                return rows
            if choice.value == "add":
                objective = self.custom_quest_objective_builder(index=len(rows))
                if objective is not None:
                    rows.append(objective)
                continue
            try:
                index = int(str(choice.value).split(":", 1)[1])
                objective = rows[index]
            except (ValueError, IndexError):
                continue
            action = menu_select(
                f"Objective {index + 1}",
                [
                    MenuItem(label="Edit", value="edit", enabled=True),
                    MenuItem(label="Move earlier", value="up", enabled=index > 0),
                    MenuItem(label="Move later", value="down", enabled=index + 1 < len(rows)),
                    MenuItem(label="Duplicate", value="duplicate", enabled=len(rows) < 12),
                    MenuItem(label="Delete", value="delete", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ], extra_lines=[str(objective.get("description", ""))], mouse_enabled=True,
            )
            if action is None or action.value == MENU_BACK:
                continue
            if action.value == "edit":
                updated = self.custom_quest_objective_builder(objective, index)
                if updated is not None:
                    rows[index] = updated
            elif action.value == "up" and index > 0:
                rows[index - 1], rows[index] = rows[index], rows[index - 1]
            elif action.value == "down" and index + 1 < len(rows):
                rows[index + 1], rows[index] = rows[index], rows[index + 1]
            elif action.value == "duplicate" and len(rows) < 12:
                clone = copy.deepcopy(objective)
                clone["id"] = f"objective_{len(rows) + 1}"
                rows.insert(index + 1, clone)
            elif action.value == "delete":
                del rows[index]

    def custom_quest_rewards_menu(self, rewards: Mapping[str, object]) -> Dict[str, object]:
        result = {
            "money": int(rewards.get("money", 0) or 0),
            "xp": int(rewards.get("xp", 0) or 0),
            "reputation": int(rewards.get("reputation", 0) or 0),
            "items": dict(rewards.get("items", {}) or {}),
        }
        while True:
            items = [
                MenuItem(label=f"Money: {result['money']}g", value="money", enabled=True),
                MenuItem(label=f"Combat XP: {result['xp']}", value="xp", enabled=True),
                MenuItem(label=f"Social reputation: {result['reputation']:+d}", value="reputation", enabled=True),
                MenuItem(label="Add reward item", value="add", enabled=len(result["items"]) < 8),
            ]
            items.extend(MenuItem(label=quantity_item_phrase(name, quantity), value=f"item:{name}", enabled=True, hint="edit or remove") for name, quantity in result["items"].items())
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select("Quest Rewards", items, footer="Reward bundles may contain up to eight item types.", mouse_enabled=True)
            if choice is None or choice.value == MENU_BACK:
                return result
            if choice.value in {"money", "xp", "reputation"}:
                limits = {"money": (0, 1000000), "xp": (0, 100000), "reputation": (-100, 100)}
                minimum, maximum = limits[str(choice.value)]
                value = self.custom_story_number_entry("Quest Rewards", f"{str(choice.value).title()} reward?", int(result[str(choice.value)]), minimum, maximum)
                if value is not None:
                    result[str(choice.value)] = value
            elif choice.value == "add":
                name = text_entry_menu("Reward Item", "Item name?", "Field Snack", 80)
                if name:
                    quantity = self.custom_story_number_entry("Reward Item", "Quantity?", 1, 1, 999)
                    if quantity is not None:
                        result["items"][name] = quantity
            elif str(choice.value).startswith("item:"):
                name = str(choice.value).split(":", 1)[1]
                action = menu_select("Reward Item", [
                    MenuItem(label="Change quantity", value="edit", enabled=True),
                    MenuItem(label="Remove", value="remove", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ], extra_lines=[f"{result['items'].get(name, 0)} {name}"], mouse_enabled=True)
                if action and action.value == "edit":
                    quantity = self.custom_story_number_entry("Reward Item", "Quantity?", int(result["items"].get(name, 1)), 1, 999)
                    if quantity is not None:
                        result["items"][name] = quantity
                elif action and action.value == "remove":
                    result["items"].pop(name, None)

    def custom_quest_prerequisite_menu(self, quest_id: str, selected: Sequence[str]) -> List[str]:
        records = [row for row in self.custom_content_data().get("quests", []) if isinstance(row, dict) and str(row.get("id", "")) != quest_id]
        chosen = {str(value) for value in selected}
        while True:
            items = [
                MenuItem(
                    label=("[Required] " if str(row.get("id")) in chosen else "[Optional] ") + str(row.get("name", "Quest")),
                    value=str(row.get("id", "")), enabled=True,
                ) for row in records
            ]
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select("Quest Prerequisites", items, footer="Toggle quests that must already be completed before this offer appears.", mouse_enabled=True)
            if choice is None or choice.value == MENU_BACK:
                return sorted(chosen)
            value = str(choice.value)
            if value in chosen:
                chosen.remove(value)
            elif len(chosen) < 8:
                chosen.add(value)

    def custom_quest_validation_lines(self, record: Mapping[str, object]) -> List[str]:
        errors: List[str] = []
        warnings: List[str] = []
        objectives = [row for row in record.get("objectives", []) if isinstance(row, Mapping)]
        if not str(record.get("name", "")).strip():
            errors.append("Quest title is missing.")
        if not str(record.get("description", "")).strip():
            errors.append("Quest description is missing.")
        if not objectives:
            errors.append("Add at least one objective.")
        for index, objective in enumerate(objectives, 1):
            if not str(objective.get("description", "")).strip():
                errors.append(f"Objective {index} has no player-facing text.")
            if str(objective.get("kind", "")) not in CUSTOM_QUEST_KINDS:
                errors.append(f"Objective {index} has an unsupported type.")
            destination = dict(objective.get("destination", {}) or {})
            if not destination:
                errors.append(f"Objective {index} has no target location.")
            if str(objective.get("kind", "")) == "visit" and str(destination.get("label", "")).casefold() == "anywhere":
                errors.append(f"Objective {index} is a visit objective and therefore needs a physical destination.")
        rewards = dict(record.get("rewards", {}) or {})
        if not any((int(rewards.get("money", 0) or 0), int(rewards.get("xp", 0) or 0), int(rewards.get("reputation", 0) or 0), bool(rewards.get("items")))):
            warnings.append("The quest currently has no reward.")
        if record.get("repeatable") and record.get("prerequisite_ids"):
            warnings.append("A repeatable quest retains its prerequisites on every cycle.")
        if str(record.get("completion_mode", "claim")) == "automatic" and record.get("turn_in"):
            warnings.append("Automatic completion still waits until the configured turn-in location is reached.")
        lines = ["QUEST READINESS", ""]
        lines.extend(["Errors:", *[f"- {line}" for line in errors], ""] if errors else ["No blocking errors.", ""])
        lines.extend(["Warnings:", *[f"- {line}" for line in warnings]] if warnings else ["No warnings."])
        return lines

    def custom_quest_builder(self, existing: Optional[Mapping[str, object]] = None) -> Optional[Dict[str, object]]:
        clean = sanitize_custom_quest(dict(existing or {})) if existing else None
        draft: Dict[str, object] = copy.deepcopy(clean) if clean else {
            "id": "new_quest", "name": "New Quest", "description": "A player-created quest.",
            "category": "General", "enabled": True, "giver_name": "Custom Quest Board",
            "offer_text": "", "completion_text": "", "objectives": [], "turn_in": {},
            "completion_mode": "claim", "repeatable": False, "cooldown_days": 7,
            "prerequisite_ids": [], "rewards": {"money": 0, "xp": 0, "reputation": 0, "items": {}},
        }
        original_id = str(draft.get("id", "")) if existing else ""
        while True:
            validation = self.custom_quest_validation_lines(draft)
            has_errors = "No blocking errors." not in validation
            objectives = [row for row in draft.get("objectives", []) if isinstance(row, dict)]
            rewards = dict(draft.get("rewards", {}) or {})
            choice = menu_select(
                "Quest Designer",
                [
                    MenuItem(label=f"Title: {draft.get('name', 'New Quest')}", value="title", enabled=True),
                    MenuItem(label="Description", value="description", enabled=True, hint=str(draft.get("description", ""))[:60]),
                    MenuItem(label=f"Category: {draft.get('category', 'General')}", value="category", enabled=True),
                    MenuItem(label=f"Quest giver: {draft.get('giver_name', 'Custom Quest Board')}", value="giver", enabled=True),
                    MenuItem(label=f"Objectives: {len(objectives)}", value="objectives", enabled=True, hint="add, edit, reorder, duplicate, or remove stages"),
                    MenuItem(label=f"Rewards: {rewards.get('money', 0)}g / {rewards.get('xp', 0)} XP / {len(dict(rewards.get('items', {}) or {}))} items", value="rewards", enabled=True),
                    MenuItem(label=f"Turn-in: {dict(draft.get('turn_in', {}) or {}).get('label', 'Anywhere')}", value="turn_in", enabled=True),
                    MenuItem(label=f"Completion: {str(draft.get('completion_mode', 'claim')).title()}", value="completion", enabled=True),
                    MenuItem(label=f"Repeatable: {'Yes' if draft.get('repeatable') else 'No'}", value="repeatable", enabled=True),
                    MenuItem(label=f"Prerequisites: {len(draft.get('prerequisite_ids', []) or [])}", value="prerequisites", enabled=True),
                    MenuItem(label="Offer and completion text", value="text", enabled=True),
                    MenuItem(label=f"Availability: {'Enabled' if draft.get('enabled', True) else 'Disabled'}", value="enabled", enabled=True),
                    MenuItem(label="Preview quest", value="preview", enabled=True),
                    MenuItem(label="Readiness review", value="validate", enabled=True, hint="blocking errors" if has_errors else "ready to save"),
                    MenuItem(label="Save quest", value="save", enabled=not has_errors),
                    MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
                ],
                footer="Edit fields in any order; nothing is written until Save Quest.",
                extra_lines=[f"{len(objectives)} sequential objectives | schema v5", "Fix readiness errors before saving." if has_errors else "Quest is ready to save."],
                mouse_enabled=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return None
            if choice.value == "title":
                value = text_entry_menu("Quest Title", "Title?", str(draft.get("name", "New Quest")), 80)
                if value:
                    draft["name"] = value
                    if not original_id:
                        draft["id"] = _slug(value)
            elif choice.value == "description":
                value = text_entry_menu("Quest Description", "Journal description?", str(draft.get("description", "")), 400)
                if value is not None:
                    draft["description"] = value
            elif choice.value == "category":
                value = self.custom_choice_menu("Quest Category", CUSTOM_QUEST_CATEGORIES, str(draft.get("category", "General")))
                if value is not None:
                    draft["category"] = value
            elif choice.value == "giver":
                value = text_entry_menu("Quest Giver", "Name shown in the Quest Log?", str(draft.get("giver_name", "Custom Quest Board")), 80)
                if value:
                    draft["giver_name"] = value
            elif choice.value == "objectives":
                draft["objectives"] = self.custom_quest_objectives_menu(objectives)
            elif choice.value == "rewards":
                draft["rewards"] = self.custom_quest_rewards_menu(rewards)
            elif choice.value == "turn_in":
                turn_choice = self.custom_choice_menu("Quest Turn-In", ("anywhere", "location"), "location" if draft.get("turn_in") else "anywhere", labels={"anywhere": "Claim anywhere", "location": "Require a location"})
                if turn_choice == "anywhere":
                    draft["turn_in"] = {}
                elif turn_choice == "location":
                    destination = self.custom_quest_destination_menu(dict(draft.get("turn_in", {}) or {}))
                    if destination is not None and str(destination.get("label", "")).casefold() != "anywhere":
                        draft["turn_in"] = destination
            elif choice.value == "completion":
                value = self.custom_choice_menu("Quest Completion", ("claim", "automatic"), str(draft.get("completion_mode", "claim")), labels={"claim": "Claim rewards from Quest Log", "automatic": "Complete automatically"})
                if value is not None:
                    draft["completion_mode"] = value
            elif choice.value == "repeatable":
                draft["repeatable"] = not bool(draft.get("repeatable", False))
                if draft["repeatable"]:
                    cooldown = self.custom_story_number_entry("Repeatable Quest", "Cooldown in days?", int(draft.get("cooldown_days", 7) or 7), 1, 112)
                    if cooldown is not None:
                        draft["cooldown_days"] = cooldown
            elif choice.value == "prerequisites":
                draft["prerequisite_ids"] = self.custom_quest_prerequisite_menu(str(draft.get("id", "")), draft.get("prerequisite_ids", []) or [])
            elif choice.value == "text":
                offer = text_entry_menu("Quest Offer Text", "Optional opening journal text?", str(draft.get("offer_text", "")), 400)
                if offer is not None:
                    draft["offer_text"] = offer
                completion = text_entry_menu("Quest Completion Text", "Optional completion message?", str(draft.get("completion_text", "")), 400)
                if completion is not None:
                    draft["completion_text"] = completion
            elif choice.value == "enabled":
                draft["enabled"] = not bool(draft.get("enabled", True))
            elif choice.value == "preview":
                self.vertical_panel_view("Quest Preview", custom_quest_summary(draft), 70, 26)
            elif choice.value == "validate":
                self.vertical_panel_view("Quest Readiness", validation, 70, 26)
            elif choice.value == "save" and not has_errors:
                return sanitize_custom_quest(draft)

    def custom_quest_management_menu(self) -> None:
        search = ""
        while True:
            content = self.custom_content_data()
            records = [row for row in content.get("quests", []) if isinstance(row, dict)]
            visible = [row for row in records if not search or search in (str(row.get("name", "")) + " " + str(row.get("description", "")) + " " + str(row.get("category", ""))).casefold()]
            items = [
                MenuItem(label="Create quest", value="create", enabled=True, hint="open the stage-based quest designer"),
                MenuItem(label="Search / clear search", value="search", enabled=True, hint=search or "show matching titles, descriptions, and categories"),
            ]
            items.extend(
                MenuItem(
                    label=("[On] " if row.get("enabled", True) else "[Off] ") + str(row.get("name", "Quest")),
                    value=f"record:{records.index(row)}", enabled=True,
                    hint=f"{row.get('category', 'General')} | {len(row.get('objectives', []) or [])} stages | {'repeatable' if row.get('repeatable') else 'once'}",
                ) for row in visible
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select("Custom Quests", items, footer="Search, preview, validate, duplicate, enable, or edit quests.", extra_lines=[f"{len(records)} installed | {len(visible)} shown"], mouse_enabled=True)
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "search":
                value = text_entry_menu("Search Quests", "Title, description, or category? Leave blank to clear.", search, 60)
                if value is not None:
                    search = value.casefold()
                continue
            if choice.value == "create":
                record = self.custom_quest_builder()
                if record is not None:
                    if any(str(row.get("name", "")).casefold() == str(record.get("name", "")).casefold() for row in records):
                        self.state.message = f"A quest named {record.get('name')} already exists."
                    else:
                        records.append(record)
                        content["quests"] = records
                        _saved, self.state.message = save_custom_content(content)
                continue
            try:
                index = int(str(choice.value).split(":", 1)[1])
                record = records[index]
            except (ValueError, IndexError):
                continue
            action = menu_select(
                str(record.get("name", "Custom Quest")),
                [
                    MenuItem(label="Preview", value="preview", enabled=True),
                    MenuItem(label="Edit in Quest Designer", value="edit", enabled=True),
                    MenuItem(label="Readiness review", value="validate", enabled=True),
                    MenuItem(label="Disable" if record.get("enabled", True) else "Enable", value="toggle", enabled=True),
                    MenuItem(label="Duplicate", value="duplicate", enabled=True),
                    MenuItem(label="Delete", value="delete", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ], extra_lines=custom_quest_summary(record), mouse_enabled=True,
            )
            if action is None or action.value == MENU_BACK:
                continue
            if action.value == "preview":
                self.vertical_panel_view("Quest Preview", custom_quest_summary(record), 70, 26)
            elif action.value == "validate":
                self.vertical_panel_view("Quest Readiness", self.custom_quest_validation_lines(record), 70, 26)
            elif action.value == "edit":
                updated = self.custom_quest_builder(record)
                if updated is not None:
                    records[index] = updated
                    content["quests"] = records
                    _saved, self.state.message = save_custom_content(content)
            elif action.value == "toggle":
                record["enabled"] = not bool(record.get("enabled", True))
                content["quests"] = records
                _saved, self.state.message = save_custom_content(content)
            elif action.value == "duplicate":
                clone = copy.deepcopy(record)
                base = f"{record.get('name', 'Quest')} Copy"
                name = base
                number = 2
                used = {str(row.get("name", "")).casefold() for row in records}
                while name.casefold() in used:
                    name = f"{base} {number}"
                    number += 1
                clone["name"] = name
                clone["id"] = _slug(name)
                clone["enabled"] = False
                records.append(clone)
                content["quests"] = records
                _saved, self.state.message = save_custom_content(content)
            elif action.value == "delete":
                confirm = menu_select("Delete Quest", [MenuItem(label=f"Delete {record.get('name')}", value="delete", enabled=True), MenuItem(label="Back", value=MENU_BACK, enabled=True)], footer="Accepted save-specific copies remain intact.", mouse_enabled=True)
                if confirm and confirm.value == "delete":
                    del records[index]
                    content["quests"] = records
                    _saved, self.state.message = save_custom_content(content)

    def custom_dialogue_variable_lines(self, entry: Optional[Mapping[str, object]] = None) -> List[str]:
        values = dialogue_variable_context(self)
        lines = ["DIALOGUE VARIABLES", "", "Insert a variable as {variable}. Its current value is shown below.", ""]
        entry_variables = set(entry.get("variables", []) if entry else [])
        for name, description in DIALOGUE_VARIABLE_DESCRIPTIONS.items():
            lines.extend([f"{{{name}}} = {values.get(name, '')}", f"  {description}", ""])
        extra = sorted(entry_variables.difference(DIALOGUE_VARIABLE_DESCRIPTIONS))
        if extra:
            lines.extend(["Variables captured from this built-in line:", ""])
            for name in extra:
                lines.append(f"{{{name}}} = the value used by the original line at runtime")
        return lines

    def custom_dialogue_insert_variable(self, text: str, entry: Mapping[str, object]) -> str:
        variable_names = list(DIALOGUE_VARIABLE_DESCRIPTIONS)
        for name in entry.get("variables", []) or []:
            if str(name) not in variable_names:
                variable_names.append(str(name))
        values = dialogue_variable_context(self)
        choice = menu_select(
            "Insert Variable",
            [
                MenuItem(label=f"{{{name}}}", value=name, enabled=True, hint=values.get(name, "value captured from the original line"))
                for name in variable_names
            ] + [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
            footer="The placeholder is replaced with live game text when the line appears.", mouse_enabled=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return text
        token = "{" + str(choice.value) + "}"
        placement = menu_select(
            "Variable Placement",
            [
                MenuItem(label="At beginning", value="start", enabled=True),
                MenuItem(label="At end", value="end", enabled=True),
                MenuItem(label="Before a phrase", value="before", enabled=bool(text)),
                MenuItem(label="After a phrase", value="after", enabled=bool(text)),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ], footer="Choose where the variable is inserted.", mouse_enabled=True,
        )
        if placement is None or placement.value == MENU_BACK:
            return text
        if placement.value == "start":
            return _normalized_text(f"{token} {text}")
        if placement.value == "end":
            return _normalized_text(f"{text} {token}")
        phrase = text_entry_menu("Variable Placement", "Exact phrase to place the variable beside?", "", 100)
        if not phrase or phrase not in text:
            self.state.message = "That phrase was not found; the dialogue text was unchanged."
            return text
        replacement = f"{token} {phrase}" if placement.value == "before" else f"{phrase} {token}"
        return _normalized_text(text.replace(phrase, replacement, 1))

    def custom_dialogue_save_entry(self, entry: Mapping[str, object], text: str, enabled: bool = True) -> bool:
        content, _warnings = load_custom_content()
        records = [row for row in content.get("dialogue_overrides", []) if isinstance(row, dict)]
        source_id = str(entry.get("source_id", ""))
        records = [row for row in records if str(row.get("source_id", "")) != source_id]
        record = sanitize_dialogue_override({
            "source_id": source_id,
            "source_text": str(entry.get("source_text", "")),
            "text": text,
            "category": str(entry.get("category", "Dialogue")),
            "scope": str(entry.get("scope", "")),
            "enabled": enabled,
        })
        if record is not None:
            records.append(record)
        content["dialogue_overrides"] = records
        saved, self.state.message = save_custom_content(content)
        return bool(saved)

    def custom_dialogue_edit_entry(self, entry: Mapping[str, object]) -> None:
        while True:
            content, _warnings = load_custom_content()
            override = next((
                row for row in content.get("dialogue_overrides", [])
                if isinstance(row, dict) and str(row.get("source_id", "")) == str(entry.get("source_id", ""))
            ), None)
            original = str(entry.get("source_text", ""))
            edited = str(override.get("text", original)) if override else original
            enabled = bool(override.get("enabled", True)) if override else True
            preview_values = dialogue_variable_context(self)
            for name in entry.get("variables", []) or []:
                preview_values.setdefault(str(name), f"<{name}>")
            choice = menu_select(
                f"{entry.get('kind', 'Dialogue')} Editor",
                [
                    MenuItem(label="Edit complete text", value="edit", enabled=True),
                    MenuItem(label="Insert variable", value="variable", enabled=True, hint="choose a live value and its insertion point"),
                    MenuItem(label="View variables and values", value="variables", enabled=True),
                    MenuItem(label="Disable override" if enabled else "Enable override", value="toggle", enabled=override is not None),
                    MenuItem(label="Restore original", value="restore", enabled=override is not None),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                footer=f"{entry.get('source_file', '')}:{entry.get('line', 0)} | {entry.get('scope', '')}",
                extra_lines=[
                    "Original:", original, "", "Current:", edited, "", "Preview:",
                    render_dialogue_template(edited, preview_values),
                ], mouse_enabled=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "edit":
                replacement = text_entry_menu("Edit Dialogue", "Replacement text?", edited, 700)
                if replacement:
                    self.custom_dialogue_save_entry(entry, replacement, enabled)
            elif choice.value == "variable":
                replacement = self.custom_dialogue_insert_variable(edited, entry)
                if replacement != edited:
                    self.custom_dialogue_save_entry(entry, replacement, enabled)
            elif choice.value == "variables":
                self.vertical_panel_view("Dialogue Variables", self.custom_dialogue_variable_lines(entry), 70, 26)
            elif choice.value == "toggle" and override is not None:
                self.custom_dialogue_save_entry(entry, edited, not enabled)
            elif choice.value == "restore" and override is not None:
                content["dialogue_overrides"] = [
                    row for row in content.get("dialogue_overrides", [])
                    if not isinstance(row, dict) or str(row.get("source_id", "")) != str(entry.get("source_id", ""))
                ]
                _saved, self.state.message = save_custom_content(content)

    def custom_dialogue_browse(self, records: Sequence[Mapping[str, object]], title: str) -> None:
        while True:
            choices = [
                MenuItem(
                    label=str(row.get("source_text", "Dialogue"))[:72], value=str(index), enabled=True,
                    hint=f"{row.get('kind', 'Dialogue')} | {row.get('scope', '')}",
                )
                for index, row in enumerate(records)
            ]
            choices.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select(title, choices, footer=f"{len(records)} built-in text entries. Select one to inspect or edit.", mouse_enabled=True)
            if choice is None or choice.value == MENU_BACK:
                return
            try:
                self.custom_dialogue_edit_entry(records[int(choice.value)])
            except (ValueError, IndexError):
                continue

    def custom_dialogue_editor_menu(self) -> None:
        catalog = dialogue_source_catalog()
        while True:
            content, warnings = load_custom_content()
            overrides = [row for row in content.get("dialogue_overrides", []) if isinstance(row, dict)]
            categories = sorted({str(row.get("category", "Dialogue")) for row in catalog})
            items = [
                MenuItem(label="Browse all text", value="all", enabled=bool(catalog), hint=f"{len(catalog)} dialogue and narration entries"),
                MenuItem(label="Search text", value="search", enabled=bool(catalog), hint="find words, speakers, source functions, or categories"),
                MenuItem(label="Edited entries", value="edited", enabled=bool(overrides), hint=f"{len(overrides)} custom replacements"),
                MenuItem(label="Variable reference", value="variables", enabled=True, hint="view every insertable variable and its current value"),
            ]
            items.extend(MenuItem(label=category, value=f"category:{category}", enabled=True) for category in categories)
            items.append(MenuItem(label="Rebuild text catalog", value="refresh", enabled=True, hint="rescan the installed game text sources"))
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select(
                "Dialogue & Narration Editor", items,
                footer="Edits are shared by all saves and can be exported with the custom-content library.",
                extra_lines=[f"Indexed {len(catalog)} built-in entries.", *warnings[:2]], mouse_enabled=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "all":
                self.custom_dialogue_browse(catalog, "All Dialogue & Narration")
            elif choice.value == "search":
                query = text_entry_menu("Search Dialogue", "Text, function, source, or category?", "", 60)
                if query:
                    needle = query.casefold()
                    matches = [
                        row for row in catalog
                        if needle in " ".join(str(row.get(key, "")) for key in ("source_text", "scope", "source_file", "category", "kind")).casefold()
                    ]
                    self.custom_dialogue_browse(matches, f"Search: {query}")
            elif choice.value == "edited":
                by_id = {str(row.get("source_id", "")): row for row in catalog}
                edited_entries = [by_id[str(row.get("source_id", ""))] for row in overrides if str(row.get("source_id", "")) in by_id]
                self.custom_dialogue_browse(edited_entries, "Edited Dialogue")
            elif choice.value == "variables":
                self.vertical_panel_view("Dialogue Variables", self.custom_dialogue_variable_lines(), 70, 26)
            elif choice.value == "refresh":
                catalog = dialogue_source_catalog(refresh=True)
                self.state.message = f"Rebuilt the dialogue catalog with {len(catalog)} entries."
            elif str(choice.value).startswith("category:"):
                category = str(choice.value).split(":", 1)[1]
                self.custom_dialogue_browse([row for row in catalog if str(row.get("category")) == category], category)


__all__ = [
    "CustomStoryMenuMixin", "apply_custom_dialogue_override", "custom_quest_runtime_record",
    "custom_quest_summary", "dialogue_source_catalog", "dialogue_variable_context",
    "render_dialogue_template",
]
