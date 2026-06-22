from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ascii_farmstead_custom_content import (
    ABILITY_EFFECTS,
    ABILITY_SHAPES,
    ABILITY_STATUSES,
    ABILITY_ZONES,
    CUSTOM_CONTENT_EXPORT_PATH,
    CUSTOM_CONTENT_PATH,
    ELEMENTS,
    ability_summary,
    class_summary,
    empty_custom_content,
    export_custom_content,
    import_custom_content,
    invalidate_custom_content_cache,
    load_custom_content,
    save_custom_content,
    sanitize_custom_ability,
    sanitize_custom_class,
)
from ascii_farmstead_ui import MenuItem, menu_select, text_entry_menu
from ascii_battle_prototype.combat.classes import class_defs as tactical_class_defs
from ascii_battle_prototype.combat.enemies import create_enemy_templates
from ascii_battle_prototype.combat.equipment import equipment_defs as tactical_equipment_defs
from ascii_battle_prototype.combat.maps import build_maps as tactical_build_maps
from ascii_battle_prototype.combat.skills import create_default_skills
from ascii_farmstead_custom_extended import (
    DUNGEON_ROOM_PATTERNS,
    DUNGEON_ROOM_THEMES,
    ENEMY_ARCHETYPES,
    EQUIPMENT_SLOTS,
    MAP_THEMES,
    custom_dungeon_room_summary,
    custom_enemy_summary,
    custom_equipment_summary,
    custom_map_summary,
    sanitize_custom_dungeon_room,
    sanitize_custom_enemy,
    sanitize_custom_equipment,
    sanitize_custom_map,
)


MENU_BACK = "__back__"


class CustomContentMenuMixin:
    def custom_content_data(self) -> Dict[str, object]:
        content, _warnings = load_custom_content()
        return content

    def custom_number_menu(
        self,
        title: str,
        label: str,
        minimum: int,
        maximum: int,
        default: int,
        hint_suffix: str = "",
    ) -> Optional[int]:
        items = [
            MenuItem(
                label=f"{label}: {number}",
                value=number,
                enabled=True,
                hint=f"{number}{hint_suffix}",
            )
            for number in range(minimum, maximum + 1)
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = menu_select(
            title,
            items,
            footer=f"Choose {label.lower()}. Current/default: {default}.",
        )
        if choice is None or choice.value == MENU_BACK:
            return None
        return int(choice.value)

    def custom_choice_menu(
        self,
        title: str,
        choices: Sequence[str],
        default: str = "",
        labels: Optional[Dict[str, str]] = None,
        hints: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        labels = labels or {}
        hints = hints or {}
        items = [
            MenuItem(
                label=labels.get(value, value.replace("_", " ").title() if value else "None"),
                value=value,
                enabled=True,
                hint=hints.get(value, "current" if value == default else ""),
            )
            for value in choices
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = menu_select(title, items, footer="Choose one option.")
        if choice is None or choice.value == MENU_BACK:
            return None
        return str(choice.value)

    def custom_ability_builder(
        self,
        existing: Optional[Dict[str, object]] = None,
    ) -> Optional[Dict[str, object]]:
        current = sanitize_custom_ability(existing or {"name": "New Ability"}) or {}
        original_name = str(current.get("name", ""))
        name = text_entry_menu(
            "Custom Ability",
            "Ability name?",
            original_name or "New Ability",
            24,
        )
        if name is None:
            return None
        description = text_entry_menu(
            "Custom Ability",
            "Short description?",
            str(current.get("description", "A custom combat ability.")),
            180,
        )
        if description is None:
            return None
        effect = self.custom_choice_menu(
            "Ability Type",
            ABILITY_EFFECTS,
            str(current.get("effect", "damage")),
            hints={
                "damage": "Attack enemies; supports shapes, statuses, and zones.",
                "heal": "Restore an ally's HP.",
                "guard": "Place an ally into Guard.",
                "cleanse": "Remove poison, root, and vulnerable.",
                "restore_mp": "Restore an ally's combat focus.",
            },
        )
        if effect is None:
            return None
        mp_cost = self.custom_number_menu(
            "Ability Cost",
            "MP cost",
            0,
            12,
            int(current.get("mp_cost", 4)),
        )
        if mp_cost is None:
            return None

        record: Dict[str, object] = {
            "name": name,
            "description": description,
            "effect": effect,
            "mp_cost": mp_cost,
        }
        if effect == "heal":
            power = self.custom_number_menu(
                "Healing Power", "HP restored", 1, 16, int(current.get("heal_amount", 8))
            )
            if power is None:
                return None
            record["heal_amount"] = power
        elif effect == "restore_mp":
            power = self.custom_number_menu(
                "Focus Power", "MP restored", 1, 10, int(current.get("mp_amount", 6))
            )
            if power is None:
                return None
            record["mp_amount"] = power
        elif effect == "damage":
            damage = self.custom_number_menu(
                "Ability Damage", "Damage", 1, 14, int(current.get("damage", 5))
            )
            if damage is None:
                return None
            range_max = self.custom_number_menu(
                "Ability Range", "Range", 1, 8, int(current.get("range_max", 4))
            )
            if range_max is None:
                return None
            shape = self.custom_choice_menu(
                "Attack Shape",
                ABILITY_SHAPES,
                str(current.get("shape", "point")),
                hints={
                    "point": "One target.",
                    "burst": "Circular area around the target.",
                    "strip": "Straight lane.",
                    "cone": "Widening area from the caster.",
                    "cross": "Cross-shaped area.",
                    "multishot": "Several nearby targets.",
                },
            )
            if shape is None:
                return None
            record.update({"damage": damage, "range_max": range_max, "shape": shape})
            if shape == "burst":
                radius = self.custom_number_menu(
                    "Burst Size", "Radius", 0, 2, int(current.get("aoe_radius", 1))
                )
                if radius is None:
                    return None
                record["aoe_radius"] = radius
            if shape in {"strip", "cone"}:
                width = self.custom_number_menu(
                    "Attack Width", "Width", 1, 3, int(current.get("width", 1))
                )
                if width is None:
                    return None
                record["width"] = width
            if shape == "multishot":
                shots = self.custom_number_menu(
                    "Number of Shots", "Shots", 2, 6, int(current.get("shots", 3))
                )
                if shots is None:
                    return None
                record["shots"] = shots
            status = self.custom_choice_menu(
                "Inflicted Status",
                ABILITY_STATUSES,
                str(current.get("status", "")),
            )
            if status is None:
                return None
            record["status"] = status
            if status:
                duration = self.custom_number_menu(
                    "Status Duration",
                    "Turns",
                    1,
                    3,
                    int(current.get("status_duration", 1)),
                )
                if duration is None:
                    return None
                record["status_duration"] = duration

            zone_type = self.custom_choice_menu(
                "Persistent Zone",
                ABILITY_ZONES,
                str(current.get("zone_type", "")),
            )
            if zone_type is None:
                return None
            record["zone_type"] = zone_type
            if zone_type:
                zone_duration = self.custom_number_menu(
                    "Zone Duration", "Turns", 1, 3, int(current.get("zone_duration", 2))
                )
                if zone_duration is None:
                    return None
                zone_damage = self.custom_number_menu(
                    "Zone Damage", "Damage", 0, 3, int(current.get("zone_damage", 1))
                )
                if zone_damage is None:
                    return None
                zone_status = self.custom_choice_menu(
                    "Zone Status",
                    ABILITY_STATUSES,
                    str(current.get("zone_status", "")),
                )
                if zone_status is None:
                    return None
                record.update({
                    "zone_duration": zone_duration,
                    "zone_damage": zone_damage,
                    "zone_status": zone_status,
                })
                if zone_status:
                    zone_status_duration = self.custom_number_menu(
                        "Zone Status Duration",
                        "Turns",
                        1,
                        3,
                        int(current.get("zone_status_duration", 1)),
                    )
                    if zone_status_duration is None:
                        return None
                    record["zone_status_duration"] = zone_status_duration

        record = sanitize_custom_ability(record)
        if record is None:
            return None
        preview_items = [
            MenuItem(label="Save ability", value="save", enabled=True),
            MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
        ]
        choice = menu_select(
            "Review Custom Ability",
            preview_items,
            footer="The balance estimate is guidance, not a restriction.",
            extra_lines=ability_summary(record),
        )
        return record if choice is not None and choice.value == "save" else None

    def save_custom_ability_record(
        self,
        record: Dict[str, object],
        original_name: str = "",
    ) -> str:
        content = self.custom_content_data()
        abilities = [item for item in content["abilities"] if isinstance(item, dict)]
        built_in_names = {
            skill.name.casefold()
            for skill in create_default_skills()
            if not any(
                str(custom.get("name", "")).casefold() == skill.name.casefold()
                for custom in abilities
            )
        }
        new_name = str(record["name"])
        for existing in abilities:
            existing_name = str(existing.get("name", ""))
            if existing_name.casefold() == new_name.casefold() and existing_name.casefold() != original_name.casefold():
                return f"An ability named {new_name} already exists."
        if new_name.casefold() in built_in_names:
            return f"{new_name} is a built-in ability name."
        replaced = False
        for index, existing in enumerate(abilities):
            if str(existing.get("name", "")).casefold() == original_name.casefold() and original_name:
                abilities[index] = record
                replaced = True
                break
        if not replaced:
            abilities.append(record)
        content["abilities"] = abilities
        if original_name and original_name.casefold() != new_name.casefold():
            for class_record in content["classes"]:
                if not isinstance(class_record, dict):
                    continue
                class_record["default_abilities"] = [
                    new_name if str(name).casefold() == original_name.casefold() else name
                    for name in class_record.get("default_abilities", [])
                ]
                for entry in class_record.get("progression_abilities", []):
                    if isinstance(entry, dict) and str(entry.get("name", "")).casefold() == original_name.casefold():
                        entry["name"] = new_name
                if str(class_record.get("mastery_ability", "")).casefold() == original_name.casefold():
                    class_record["mastery_ability"] = new_name
        ok, message = save_custom_content(content)
        return message if ok else message

    def custom_ability_picker(
        self,
        title: str,
        excluded: Sequence[str] = (),
        custom_only: bool = False,
    ) -> Optional[str]:
        excluded_keys = {name.casefold() for name in excluded}
        custom_names = {
            str(record.get("name", ""))
            for record in self.custom_content_data()["abilities"]
            if isinstance(record, dict)
        }
        skills = [
            skill for skill in create_default_skills()
            if skill.name.casefold() not in excluded_keys
            and (not custom_only or skill.name in custom_names)
        ]
        items = [
            MenuItem(
                label=skill.name,
                value=skill.name,
                enabled=True,
                hint=f"{skill.effect.replace('_', ' ')} | {skill.mp_cost} MP | {skill.description[:54]}",
            )
            for skill in skills
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = menu_select(title, items, footer="Choose an ability.")
        if choice is None or choice.value == MENU_BACK:
            return None
        return str(choice.value)

    def custom_class_builder(
        self,
        existing: Optional[Dict[str, object]] = None,
    ) -> Optional[Dict[str, object]]:
        current = sanitize_custom_class(existing or {"name": "New Class"}) or {}
        name = text_entry_menu(
            "Custom Class",
            "Class name?",
            str(current.get("name", "New Class")),
            24,
        )
        if name is None:
            return None
        description = text_entry_menu(
            "Custom Class",
            "Describe its combat identity?",
            str(current.get("description", "A custom combat class.")),
            220,
        )
        if description is None:
            return None

        selected: List[str] = []
        current_defaults = list(current.get("default_abilities", []))
        for index in range(3):
            default = current_defaults[index] if index < len(current_defaults) else ""
            ability = self.custom_ability_picker(
                f"Starting Ability {index + 1} of 3",
                selected,
            )
            if ability is None:
                return None
            selected.append(ability)

        count = self.custom_number_menu(
            "Class Progression",
            "Learnable abilities",
            3,
            6,
            len(current.get("progression_abilities", [])) or 5,
        )
        if count is None:
            return None
        progression: List[Dict[str, object]] = []
        for index in range(count):
            ability = self.custom_ability_picker(
                f"Progression Ability {index + 1} of {count}",
                selected + [str(item["name"]) for item in progression],
            )
            if ability is None:
                return None
            progression.append({"name": ability, "cost": min(3, 1 + index // 2)})

        mastery = self.custom_ability_picker(
            "Mastery Ability",
            selected + [str(item["name"]) for item in progression],
        )
        if mastery is None:
            return None
        first_element = self.custom_choice_menu(
            "Primary Element",
            ELEMENTS,
            (list(current.get("recommended_elements", [])) or ["Fire"])[0],
        )
        if first_element is None:
            return None
        remaining_elements = [element for element in ELEMENTS if element != first_element]
        second_element = self.custom_choice_menu(
            "Secondary Element",
            remaining_elements,
            (list(current.get("recommended_elements", [])) + ["Earth", "Light"])[1],
        )
        if second_element is None:
            return None
        record = sanitize_custom_class({
            "name": name,
            "description": description,
            "default_abilities": selected,
            "progression_abilities": progression,
            "mastery_ability": mastery,
            "recommended_elements": [first_element, second_element],
        })
        if record is None:
            return None
        choice = menu_select(
            "Review Custom Class",
            [
                MenuItem(label="Save class", value="save", enabled=True),
                MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
            ],
            footer="Class skills use the normal skill-point and mastery systems.",
            extra_lines=class_summary(record),
        )
        return record if choice is not None and choice.value == "save" else None

    def save_custom_class_record(
        self,
        record: Dict[str, object],
        original_name: str = "",
    ) -> str:
        content = self.custom_content_data()
        classes = [item for item in content["classes"] if isinstance(item, dict)]
        built_in_names = {
            name.casefold()
            for name, data in tactical_class_defs().items()
            if not bool(data.get("custom", False))
        }
        new_name = str(record["name"])
        for existing in classes:
            existing_name = str(existing.get("name", ""))
            if existing_name.casefold() == new_name.casefold() and existing_name.casefold() != original_name.casefold():
                return f"A class named {new_name} already exists."
        if new_name.casefold() in built_in_names:
            return f"{new_name} is a built-in class name."
        replaced = False
        for index, existing in enumerate(classes):
            if str(existing.get("name", "")).casefold() == original_name.casefold() and original_name:
                classes[index] = record
                replaced = True
                break
        if not replaced:
            classes.append(record)
        content["classes"] = classes
        _ok, message = save_custom_content(content)
        return message

    def custom_ability_management_menu(self):
        while True:
            content = self.custom_content_data()
            abilities = [item for item in content["abilities"] if isinstance(item, dict)]
            items = [
                MenuItem(label="Create ability", value="create", enabled=True, hint="guided combat ability maker")
            ]
            items.extend(
                MenuItem(
                    label=str(record.get("name", "Unnamed")),
                    value=f"ability:{index}",
                    enabled=True,
                    hint=str(record.get("effect", "damage")).replace("_", " "),
                )
                for index, record in enumerate(abilities)
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select(
                "Custom Abilities",
                items,
                footer="Create, inspect, edit, or remove abilities.",
                extra_lines=[f"{len(abilities)} custom abilities installed."],
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "create":
                record = self.custom_ability_builder()
                if record is not None:
                    self.state.message = self.save_custom_ability_record(record)
                continue
            try:
                index = int(str(choice.value).split(":", 1)[1])
                record = abilities[index]
            except (ValueError, IndexError):
                continue
            action = menu_select(
                str(record.get("name", "Custom Ability")),
                [
                    MenuItem(label="Inspect", value="inspect", enabled=True),
                    MenuItem(label="Edit", value="edit", enabled=True),
                    MenuItem(label="Delete", value="delete", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                footer="Changes apply to future battles immediately.",
                extra_lines=ability_summary(record),
            )
            if action is None or action.value == MENU_BACK:
                continue
            if action.value == "inspect":
                menu_select(
                    str(record.get("name", "Custom Ability")),
                    [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                    extra_lines=ability_summary(record),
                )
            elif action.value == "edit":
                updated = self.custom_ability_builder(record)
                if updated is not None:
                    self.state.message = self.save_custom_ability_record(updated, str(record.get("name", "")))
            elif action.value == "delete":
                name = str(record.get("name", ""))
                used_by = [
                    str(class_record.get("name", ""))
                    for class_record in content["classes"]
                    if isinstance(class_record, dict)
                    and name in (
                        list(class_record.get("default_abilities", []))
                        + [str(entry.get("name", "")) for entry in class_record.get("progression_abilities", []) if isinstance(entry, dict)]
                        + [str(class_record.get("mastery_ability", ""))]
                    )
                ]
                if used_by:
                    self.state.message = f"{name} is still used by: {', '.join(used_by)}."
                    continue
                confirm = menu_select(
                    "Delete Custom Ability",
                    [
                        MenuItem(label=f"Delete {name}", value="delete", enabled=True),
                        MenuItem(label="Back", value=MENU_BACK, enabled=True),
                    ],
                    footer="This cannot be undone.",
                )
                if confirm is not None and confirm.value == "delete":
                    content["abilities"] = [item for item in abilities if item is not record]
                    _ok, self.state.message = save_custom_content(content)

    def custom_class_management_menu(self):
        while True:
            content = self.custom_content_data()
            classes = [item for item in content["classes"] if isinstance(item, dict)]
            items = [
                MenuItem(label="Create class", value="create", enabled=True, hint="build a complete combat progression")
            ]
            items.extend(
                MenuItem(
                    label=str(record.get("name", "Unnamed")),
                    value=f"class:{index}",
                    enabled=True,
                    hint=", ".join(record.get("recommended_elements", [])) or "Any element",
                )
                for index, record in enumerate(classes)
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select(
                "Custom Classes",
                items,
                footer="Classes appear in character creation and Adventure > Skills.",
                extra_lines=[f"{len(classes)} custom classes installed."],
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "create":
                record = self.custom_class_builder()
                if record is not None:
                    self.state.message = self.save_custom_class_record(record)
                continue
            try:
                index = int(str(choice.value).split(":", 1)[1])
                record = classes[index]
            except (ValueError, IndexError):
                continue
            action = menu_select(
                str(record.get("name", "Custom Class")),
                [
                    MenuItem(label="Inspect", value="inspect", enabled=True),
                    MenuItem(label="Edit", value="edit", enabled=True),
                    MenuItem(label="Delete", value="delete", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                footer="Deleting a selected class safely returns affected characters to their default class.",
                extra_lines=class_summary(record),
            )
            if action is None or action.value == MENU_BACK:
                continue
            if action.value == "inspect":
                menu_select(
                    str(record.get("name", "Custom Class")),
                    [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                    extra_lines=class_summary(record),
                )
            elif action.value == "edit":
                updated = self.custom_class_builder(record)
                if updated is not None:
                    self.state.message = self.save_custom_class_record(updated, str(record.get("name", "")))
            elif action.value == "delete":
                name = str(record.get("name", ""))
                confirm = menu_select(
                    "Delete Custom Class",
                    [
                        MenuItem(label=f"Delete {name}", value="delete", enabled=True),
                        MenuItem(label="Back", value=MENU_BACK, enabled=True),
                    ],
                    footer="Existing progress records are preserved but become inactive.",
                )
                if confirm is not None and confirm.value == "delete":
                    content["classes"] = [item for item in classes if item is not record]
                    _ok, self.state.message = save_custom_content(content)

    def custom_integer_entry(
        self,
        title: str,
        prompt: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> Optional[int]:
        raw = text_entry_menu(title, prompt, str(default), 12)
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    def custom_enemy_picker(self, title: str, excluded: Sequence[str] = ()) -> Optional[str]:
        excluded_keys = {str(name).casefold() for name in excluded}
        names = []
        for enemy in create_enemy_templates({}):
            base = str(enemy.name)
            if base.casefold() not in excluded_keys and base not in names:
                names.append(base)
        items = [
            MenuItem(label=name, value=name, enabled=True)
            for name in sorted(names)
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = menu_select(title, items, footer="Choose a default enemy for this arena.")
        if choice is None or choice.value == MENU_BACK:
            return None
        return str(choice.value)

    def custom_enemy_builder(self, existing: Optional[Dict[str, object]] = None) -> Optional[Dict[str, object]]:
        current = sanitize_custom_enemy(existing or {"name": "New Enemy"}) or {}
        name = text_entry_menu("Custom Enemy", "Enemy name?", str(current.get("name", "New Enemy")), 28)
        if name is None:
            return None
        description = text_entry_menu(
            "Custom Enemy",
            "Short description?",
            str(current.get("description", "A custom tactical enemy.")),
            180,
        )
        if description is None:
            return None
        glyph = text_entry_menu("Custom Enemy", "One-character glyph?", str(current.get("glyph", "?")), 1)
        if glyph is None:
            return None
        archetype = self.custom_choice_menu(
            "Enemy Archetype",
            list(ENEMY_ARCHETYPES),
            str(current.get("archetype", "Skirmisher")),
            hints={
                name: f"{data['role']} AI; behavior package based on {data['family']}"
                for name, data in ENEMY_ARCHETYPES.items()
            },
        )
        if archetype is None:
            return None
        hp_max = 120 if archetype == "Boss" else 70
        hp = self.custom_integer_entry("Enemy Health", "HP?", int(current.get("max_hp", 24)), 8, hp_max)
        if hp is None:
            return None
        move = self.custom_number_menu("Enemy Movement", "Move", 1, 8, int(current.get("move_range", 4)))
        if move is None:
            return None
        defense = self.custom_number_menu("Enemy Defense", "Defense", 0, 4, int(current.get("defense", 0)))
        if defense is None:
            return None
        weapon_name = text_entry_menu(
            "Enemy Attack",
            "Attack name?",
            str(current.get("weapon_name", "Custom Attack")),
            28,
        )
        if weapon_name is None:
            return None
        damage_max = 12 if archetype == "Boss" else 9
        damage = self.custom_number_menu("Enemy Attack", "Damage", 1, damage_max, int(current.get("damage", 4)))
        if damage is None:
            return None
        range_max = self.custom_number_menu("Enemy Attack", "Maximum range", 1, 7, int(current.get("range_max", 1)))
        if range_max is None:
            return None
        range_min = self.custom_number_menu(
            "Enemy Attack",
            "Minimum range",
            1,
            min(4, range_max),
            min(int(current.get("range_min", 1)), range_max),
        )
        if range_min is None:
            return None
        record = sanitize_custom_enemy({
            "name": name,
            "description": description,
            "glyph": glyph,
            "archetype": archetype,
            "max_hp": hp,
            "move_range": move,
            "defense": defense,
            "weapon_name": weapon_name,
            "damage": damage,
            "range_min": range_min,
            "range_max": range_max,
        })
        if record is None:
            return None
        choice = menu_select(
            "Review Custom Enemy",
            [
                MenuItem(label="Save enemy", value="save", enabled=True),
                MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
            ],
            footer="Archetypes use tested tactical AI and special actions.",
            extra_lines=custom_enemy_summary(record),
        )
        return record if choice is not None and choice.value == "save" else None

    def custom_equipment_builder(self, existing: Optional[Dict[str, object]] = None) -> Optional[Dict[str, object]]:
        current = sanitize_custom_equipment(existing or {"name": "New Equipment"}) or {}
        name = text_entry_menu("Custom Equipment", "Equipment name?", str(current.get("name", "New Equipment")), 28)
        if name is None:
            return None
        description = text_entry_menu(
            "Custom Equipment",
            "Short description?",
            str(current.get("description", "Custom tactical equipment.")),
            180,
        )
        if description is None:
            return None
        slot = self.custom_choice_menu("Equipment Slot", EQUIPMENT_SLOTS, str(current.get("slot", "weapon")))
        if slot is None:
            return None
        values: Dict[str, int] = {}
        ranges = {
            "dmg": (-2, 4),
            "hp": (-8, 14),
            "mp": (-5, 8),
            "move": (-2, 2),
            "range_max": (0, 2),
        }
        labels = {"dmg": "Damage bonus", "hp": "HP bonus", "mp": "Focus bonus", "move": "Move bonus", "range_max": "Range bonus"}
        for key in ("dmg", "hp", "mp", "move", "range_max"):
            if key == "range_max" and slot != "weapon":
                values[key] = 0
                continue
            minimum, maximum = ranges[key]
            value = self.custom_number_menu("Equipment Bonuses", labels[key], minimum, maximum, int(current.get(key, 0)))
            if value is None:
                return None
            values[key] = value
        coin_cost = self.custom_number_menu("Crafting Cost", "Coin", 1, 99, int(current.get("coin_cost", 18)))
        if coin_cost is None:
            return None
        materials = ["", "Stone", "Hide", "Shard", "Tonic", "Fang", "Spore Cap", "Relic Fragment", "Ancient Cog"]
        material = self.custom_choice_menu("Crafting Material", materials, str(current.get("material", "")))
        if material is None:
            return None
        material_cost = 0
        if material:
            chosen_cost = self.custom_number_menu("Crafting Cost", f"{material} amount", 1, 5, int(current.get("material_cost", 1)))
            if chosen_cost is None:
                return None
            material_cost = chosen_cost
        record = sanitize_custom_equipment({
            "name": name,
            "description": description,
            "slot": slot,
            **values,
            "coin_cost": coin_cost,
            "material": material,
            "material_cost": material_cost,
        })
        if record is None:
            return None
        choice = menu_select(
            "Review Custom Equipment",
            [
                MenuItem(label="Save equipment", value="save", enabled=True),
                MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
            ],
            footer="Custom equipment must be crafted through the normal loadout menu.",
            extra_lines=custom_equipment_summary(record),
        )
        return record if choice is not None and choice.value == "save" else None

    def custom_map_builder(self, existing: Optional[Dict[str, object]] = None) -> Optional[Dict[str, object]]:
        current = sanitize_custom_map(existing or {"name": "New Arena"}) or {}
        name = text_entry_menu("Custom Combat Map", "Arena name?", str(current.get("name", "New Arena")), 32)
        if name is None:
            return None
        description = text_entry_menu(
            "Custom Combat Map",
            "Short description?",
            str(current.get("description", "A custom tactical arena.")),
            180,
        )
        if description is None:
            return None
        theme = self.custom_choice_menu("Arena Theme", MAP_THEMES, str(current.get("theme", "Meadow")))
        if theme is None:
            return None
        width = self.custom_choice_menu("Arena Width", ["16", "20", "24", "28", "32", "36"], str(current.get("width", 24)))
        if width is None:
            return None
        height = self.custom_choice_menu("Arena Height", ["10", "12", "14", "16", "18", "20"], str(current.get("height", 14)))
        if height is None:
            return None
        cover = self.custom_number_menu("Terrain Density", "Cover", 0, 4, int(current.get("cover_density", 2)))
        if cover is None:
            return None
        hazards = self.custom_number_menu("Terrain Density", "Hazards", 0, 4, int(current.get("hazard_density", 1)))
        if hazards is None:
            return None
        seed = self.custom_integer_entry("Arena Seed", "Generation seed?", int(current.get("seed", 1)), 0, 999999999)
        if seed is None:
            return None
        objective = self.custom_choice_menu(
            "Default Objective",
            ["Defeat All", "Survive", "Hold Zone", "Destroy Objects"],
            str(current.get("objective", "Defeat All")),
        )
        if objective is None:
            return None
        enemy_names: List[str] = []
        for index in range(3):
            enemy = self.custom_enemy_picker(f"Default Enemy {index + 1} of 3", enemy_names)
            if enemy is None:
                return None
            enemy_names.append(enemy)
        record = sanitize_custom_map({
            "name": name,
            "description": description,
            "theme": theme,
            "width": int(width),
            "height": int(height),
            "cover_density": cover,
            "hazard_density": hazards,
            "seed": seed,
            "enemy_names": enemy_names,
            "objective": objective,
        })
        if record is None:
            return None
        choice = menu_select(
            "Review Custom Arena",
            [
                MenuItem(label="Save arena", value="save", enabled=True),
                MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
            ],
            footer="Saved arenas become replayable Custom combat missions.",
            extra_lines=custom_map_summary(record),
        )
        return record if choice is not None and choice.value == "save" else None

    def custom_dungeon_room_builder(self, existing: Optional[Dict[str, object]] = None) -> Optional[Dict[str, object]]:
        current = sanitize_custom_dungeon_room(existing or {"name": "New Room"}) or {}
        name = text_entry_menu("Dungeon Room Template", "Template name?", str(current.get("name", "New Room")), 28)
        if name is None:
            return None
        description = text_entry_menu(
            "Dungeon Room Template",
            "Short description?",
            str(current.get("description", "A custom dungeon-room template.")),
            180,
        )
        if description is None:
            return None
        theme = self.custom_choice_menu("Dungeon Theme", DUNGEON_ROOM_THEMES, str(current.get("theme", "Any")))
        if theme is None:
            return None
        pattern = self.custom_choice_menu("Room Pattern", DUNGEON_ROOM_PATTERNS, str(current.get("pattern", "Open")))
        if pattern is None:
            return None
        density = self.custom_number_menu("Room Density", "Features", 0, 4, int(current.get("density", 2)))
        if density is None:
            return None
        seed = self.custom_integer_entry("Room Seed", "Generation seed?", int(current.get("seed", 1)), 0, 999999999)
        if seed is None:
            return None
        enabled = self.custom_choice_menu(
            "Generator Use",
            ["disabled", "enabled"],
            "enabled" if current.get("enabled", False) else "disabled",
            hints={
                "disabled": "Saved for preview; current dungeon generation is untouched.",
                "enabled": "May decorate matching ordinary rooms; topology remains procedural.",
            },
        )
        if enabled is None:
            return None
        record = sanitize_custom_dungeon_room({
            "name": name,
            "description": description,
            "theme": theme,
            "pattern": pattern,
            "density": density,
            "seed": seed,
            "enabled": enabled == "enabled",
        })
        if record is None:
            return None
        choice = menu_select(
            "Review Dungeon Room",
            [
                MenuItem(label="Save template", value="save", enabled=True),
                MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
            ],
            footer="Templates preserve procedural topology and guaranteed room paths.",
            extra_lines=custom_dungeon_room_summary(record),
        )
        return record if choice is not None and choice.value == "save" else None

    def custom_extended_record_menu(
        self,
        title: str,
        field_name: str,
        create_label: str,
        builder,
        summary,
    ):
        while True:
            content = self.custom_content_data()
            records = [item for item in content.get(field_name, []) if isinstance(item, dict)]
            items = [MenuItem(label=create_label, value="create", enabled=True)]
            items.extend(
                MenuItem(
                    label=str(record.get("name", "Unnamed")),
                    value=f"record:{index}",
                    enabled=True,
                    hint=(
                        str(record.get("archetype", ""))
                        or str(record.get("slot", ""))
                        or str(record.get("theme", ""))
                    ),
                )
                for index, record in enumerate(records)
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select(title, items, footer="Create, inspect, edit, or remove custom content.")
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "create":
                record = builder()
                if record is not None:
                    name = str(record.get("name", ""))
                    if self.custom_extended_name_conflict(field_name, record, records):
                        self.state.message = f"{name} conflicts with existing or built-in content."
                        continue
                    records.append(record)
                    content[field_name] = records
                    _ok, self.state.message = save_custom_content(content)
                continue
            try:
                index = int(str(choice.value).split(":", 1)[1])
                record = records[index]
            except (ValueError, IndexError):
                continue
            action = menu_select(
                str(record.get("name", title)),
                [
                    MenuItem(label="Inspect", value="inspect", enabled=True),
                    MenuItem(label="Edit", value="edit", enabled=True),
                    MenuItem(label="Delete", value="delete", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                extra_lines=summary(record),
            )
            if action is None or action.value == MENU_BACK:
                continue
            if action.value == "inspect":
                menu_select(
                    str(record.get("name", title)),
                    [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                    extra_lines=summary(record),
                )
            elif action.value == "edit":
                updated = builder(record)
                if updated is not None:
                    original_name = str(record.get("name", ""))
                    new_name = str(updated.get("name", ""))
                    other_records = [other for i, other in enumerate(records) if i != index]
                    if self.custom_extended_name_conflict(field_name, updated, other_records, original_name):
                        self.state.message = f"{new_name} conflicts with existing or built-in content."
                        continue
                    records[index] = updated
                    if field_name == "enemies" and original_name.casefold() != new_name.casefold():
                        for arena in content.get("maps", []):
                            if isinstance(arena, dict):
                                arena["enemy_names"] = [
                                    new_name if str(name).casefold() == original_name.casefold() else name
                                    for name in arena.get("enemy_names", [])
                                ]
                    content[field_name] = records
                    _ok, self.state.message = save_custom_content(content)
            elif action.value == "delete":
                name = str(record.get("name", ""))
                if field_name == "enemies":
                    used_by = [
                        str(arena.get("name", ""))
                        for arena in content.get("maps", [])
                        if isinstance(arena, dict) and name in arena.get("enemy_names", [])
                    ]
                    if used_by:
                        self.state.message = f"{name} is used by arenas: {', '.join(used_by)}."
                        continue
                confirm = menu_select(
                    f"Delete {name}",
                    [
                        MenuItem(label=f"Delete {name}", value="delete", enabled=True),
                        MenuItem(label="Back", value=MENU_BACK, enabled=True),
                    ],
                    footer="This cannot be undone.",
                )
                if confirm is not None and confirm.value == "delete":
                    del records[index]
                    content[field_name] = records
                    _ok, self.state.message = save_custom_content(content)

    def custom_extended_name_conflict(
        self,
        field_name: str,
        record: Dict[str, object],
        other_records: Sequence[Dict[str, object]],
        original_name: str = "",
    ) -> bool:
        name = str(record.get("name", ""))
        key = name.casefold()
        if not key:
            return True
        if any(str(other.get("name", "")).casefold() == key for other in other_records):
            return True
        current_custom_names = {
            str(other.get("name", "")).casefold()
            for other in self.custom_content_data().get(field_name, [])
            if isinstance(other, dict)
        }
        built_in_names = set()
        if field_name == "enemies":
            built_in_names = {
                enemy.name.casefold()
                for enemy in create_enemy_templates({})
                if enemy.name.casefold() not in current_custom_names
            }
        elif field_name == "equipment":
            built_in_names = {
                gear_name.casefold()
                for values in tactical_equipment_defs().values()
                for gear_name in values
                if gear_name.casefold() not in current_custom_names
            }
        elif field_name == "maps":
            built_in_names = {
                map_name.casefold()
                for map_name, _grid, _positions in tactical_build_maps()
                if map_name.casefold() not in current_custom_names
            }
        return key in built_in_names and key != original_name.casefold()

    def custom_content_help_lines(self) -> List[str]:
        return [
            "CUSTOM CONTENT",
            "",
            "Abilities",
            "- Create attacks, healing, guard, cleanse, or focus-restoration skills.",
            "- Damage abilities can use point, burst, line, cone, cross, or multishot shapes.",
            "- Optional poison, root, vulnerable, and persistent elemental zones are supported.",
            "- Values are bounded to combinations the tactical engine can resolve safely.",
            "- The balance estimate warns about unusually efficient abilities but does not forbid them.",
            "",
            "Classes",
            "- Choose three starting abilities, three to six ordered progression abilities, and a mastery art.",
            "- Progression abilities unlock in order and use the existing skill-point/rank system.",
            "- Choose two recommended elements; other elements remain usable.",
            "- Custom classes appear in new-character creation and the normal Skills menu.",
            "",
            "Enemies and Arenas",
            "- Enemy archetypes provide tested AI behavior while names, glyphs, stats, defense, and attacks remain customizable.",
            "- Arena recipes control theme, size, cover, hazards, seed, objective, and default enemies.",
            "- Saved arenas become replayable Custom contracts on the in-game Combat Mission Board.",
            "",
            "Equipment",
            "- Create weapons, armor, and charms with bounded stat tradeoffs and crafting costs.",
            "- Custom gear is available to every party member through normal tactical loadout menus.",
            "",
            "Dungeon Rooms",
            "- Room templates are disabled by default and may be individually enabled.",
            "- Enabled templates decorate ordinary room interiors only; dungeon topology, start rooms, bosses, and corridors remain procedural.",
            "- Every template preserves a walkable center cross and safely falls back to an ordinary room.",
            "",
            "Files",
            f"- Active library: {CUSTOM_CONTENT_PATH}",
            f"- Share/import file: {CUSTOM_CONTENT_EXPORT_PATH}",
            "- Export creates a human-readable JSON file that another player can place at the import path.",
            "- Import replaces the active custom library only after confirmation.",
            "- Built-in content cannot be overwritten or deleted.",
        ]

    def startup_custom_content_menu(self):
        while True:
            content, warnings = load_custom_content()
            ability_count = len(content["abilities"])
            class_count = len(content["classes"])
            enemy_count = len(content["enemies"])
            equipment_count = len(content["equipment"])
            map_count = len(content["maps"])
            room_count = len(content["dungeon_rooms"])
            total_count = ability_count + class_count + enemy_count + equipment_count + map_count + room_count
            items = [
                MenuItem(label="Abilities", value="abilities", enabled=True, hint=f"{ability_count} installed"),
                MenuItem(label="Classes", value="classes", enabled=True, hint=f"{class_count} installed"),
                MenuItem(label="Enemies", value="enemies", enabled=True, hint=f"{enemy_count} installed"),
                MenuItem(label="Equipment", value="equipment", enabled=True, hint=f"{equipment_count} installed"),
                MenuItem(label="Combat Maps", value="maps", enabled=True, hint=f"{map_count} installed"),
                MenuItem(label="Dungeon Rooms", value="dungeon_rooms", enabled=True, hint=f"{room_count} installed | opt-in"),
                MenuItem(label="How it works", value="help", enabled=True, hint="rules, sharing, and safety"),
                MenuItem(label="Export library", value="export", enabled=bool(total_count), hint="create shareable JSON"),
                MenuItem(label="Import library", value="import", enabled=True, hint="load custom_content_export.json"),
                MenuItem(label="Reload from disk", value="reload", enabled=True, hint="validate external edits"),
                MenuItem(label="Remove all custom content", value="reset", enabled=bool(total_count)),
                MenuItem(label="Back", value=MENU_BACK, enabled=True),
            ]
            choice = menu_select(
                "Custom Content",
                items,
                footer="Custom content is shared by all saves.",
                extra_lines=[
                    f"{total_count} records across six custom-content types",
                    *(warnings[:2]),
                ],
            )
            if choice is None or choice.value == MENU_BACK:
                return
            if choice.value == "abilities":
                self.custom_ability_management_menu()
            elif choice.value == "classes":
                self.custom_class_management_menu()
            elif choice.value == "enemies":
                self.custom_extended_record_menu(
                    "Custom Enemies", "enemies", "Create enemy",
                    self.custom_enemy_builder, custom_enemy_summary,
                )
            elif choice.value == "equipment":
                self.custom_extended_record_menu(
                    "Custom Equipment", "equipment", "Create equipment",
                    self.custom_equipment_builder, custom_equipment_summary,
                )
            elif choice.value == "maps":
                self.custom_extended_record_menu(
                    "Custom Combat Maps", "maps", "Create combat map",
                    self.custom_map_builder, custom_map_summary,
                )
            elif choice.value == "dungeon_rooms":
                self.custom_extended_record_menu(
                    "Dungeon Room Templates", "dungeon_rooms", "Create room template",
                    self.custom_dungeon_room_builder, custom_dungeon_room_summary,
                )
            elif choice.value == "help":
                menu_select(
                    "Custom Content Guide",
                    [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                    extra_lines=self.custom_content_help_lines(),
                )
            elif choice.value == "export":
                _ok, self.state.message = export_custom_content(content)
            elif choice.value == "reload":
                invalidate_custom_content_cache()
                _reloaded, reload_warnings = load_custom_content()
                self.state.message = (
                    "Custom content reloaded and validated."
                    if not reload_warnings
                    else " ".join(reload_warnings)
                )
            elif choice.value == "import":
                imported, message = import_custom_content()
                if imported is None:
                    self.state.message = message
                    continue
                confirm = menu_select(
                    "Import Custom Library",
                    [
                        MenuItem(label="Replace active library", value="replace", enabled=True),
                        MenuItem(label="Back", value=MENU_BACK, enabled=True),
                    ],
                    footer="Export your current library first if you want a backup.",
                    extra_lines=[message],
                )
                if confirm is not None and confirm.value == "replace":
                    _ok, self.state.message = save_custom_content(imported)
            elif choice.value == "reset":
                confirm = menu_select(
                    "Remove All Custom Content",
                    [
                        MenuItem(label="Remove everything", value="reset", enabled=True),
                        MenuItem(label="Back", value=MENU_BACK, enabled=True),
                    ],
                    footer="Built-in content is unaffected. This cannot be undone.",
                )
                if confirm is not None and confirm.value == "reset":
                    _ok, self.state.message = save_custom_content(empty_custom_content())

    def choose_player_starting_class_menu(self) -> Optional[str]:
        definitions = tactical_class_defs()
        items = [
            MenuItem(
                label=f"{name}{' [Custom]' if data.get('custom') else ''}",
                value=name,
                enabled=True,
                hint=str(data.get("desc", ""))[:70],
            )
            for name, data in definitions.items()
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = menu_select(
            "Starting Combat Class",
            items,
            footer="Classes can be changed later from Adventure > Skills.",
        )
        if choice is None or choice.value == MENU_BACK:
            return None
        return str(choice.value)
