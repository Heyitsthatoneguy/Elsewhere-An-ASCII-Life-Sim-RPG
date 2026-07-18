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
from ascii_farmstead_data import MENU_CONFIRM_KEYS
from ascii_farmstead_support import C, clear_screen, colorize, normalize_key, read_key
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
    BUILDING_TEMPLATE_HEIGHT,
    BUILDING_TEMPLATE_COLOR_KEYS,
    BUILDING_TEMPLATE_COLOR_LABELS,
    BUILDING_TEMPLATE_MAX_COLOR_MARKS,
    BUILDING_TEMPLATE_MAX_SPAWNS,
    BUILDING_TEMPLATE_MAX_FLOORS,
    BUILDING_TEMPLATE_TYPE_LABELS,
    BUILDING_TEMPLATE_TYPES,
    BUILDING_TEMPLATE_WIDTH,
    BUILDING_TEMPLATE_ZONE_KINDS,
    BUILDING_TEMPLATE_ZONE_LABELS,
    custom_dungeon_room_summary,
    custom_enemy_summary,
    custom_equipment_summary,
    custom_building_template_summary,
    default_custom_building_template_rows,
    custom_map_summary,
    sanitize_custom_building_template,
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

    def custom_ability_pattern_editor(
        self,
        existing: Sequence[Sequence[int]] = (),
    ) -> Optional[List[List[int]]]:
        """Draw an arbitrary attack footprint on a caster/target-relative grid."""
        radius = 6
        selected = {
            (max(-radius, min(radius, int(point[0]))), max(-radius, min(radius, int(point[1]))))
            for point in existing
            if isinstance(point, (list, tuple)) and len(point) == 2
        }
        if not selected:
            selected.add((0, 0))
        cursor_x = cursor_y = 0
        notice = "The center @ is the selected anchor. The drawing is authored facing right."
        while True:
            clear_screen()
            print("Custom Attack Pattern")
            print("=" * 48)
            print("Draw every tile affected when the ability is used.")
            print("Rotation and whether @ follows the caster or target are chosen next.")
            print()
            print("+" + "-" * (radius * 2 + 1) + "+")
            for y in range(-radius, radius + 1):
                row = []
                for x in range(-radius, radius + 1):
                    point = (x, y)
                    if point == (cursor_x, cursor_y):
                        glyph = "X" if point in selected else "+"
                    elif point == (0, 0):
                        glyph = "@" if point not in selected else "O"
                    else:
                        glyph = "#" if point in selected else "."
                    row.append(glyph)
                print("|" + "".join(row) + "|")
            print("+" + "-" * (radius * 2 + 1) + "+")
            print(f"Cursor: {cursor_x:+d},{cursor_y:+d} | Affected tiles: {len(selected)}/169")
            print(notice)
            print("WASD/arrows move | Z/Space toggle | C clear | R reset | Enter accept | X/Esc cancel")
            key = normalize_key(read_key())
            if key in {"\x1b", "x", "q", "b"}:
                return None
            if key in {"w", "UP"}:
                cursor_y = max(-radius, cursor_y - 1)
            elif key in {"s", "DOWN"}:
                cursor_y = min(radius, cursor_y + 1)
            elif key in {"a", "LEFT"}:
                cursor_x = max(-radius, cursor_x - 1)
            elif key in {"d", "RIGHT"}:
                cursor_x = min(radius, cursor_x + 1)
            elif key in {"z", " "}:
                point = (cursor_x, cursor_y)
                if point in selected:
                    selected.remove(point)
                else:
                    selected.add(point)
                notice = "Tile removed." if point not in selected else "Tile added."
            elif key == "c":
                selected.clear()
                notice = "Pattern cleared. Add at least one affected tile."
            elif key == "r":
                selected = {(0, 0)}
                cursor_x = cursor_y = 0
                notice = "Pattern reset to the anchor tile."
            elif key in {"\r", "\n"}:
                if not selected:
                    notice = "The pattern needs at least one affected tile."
                    continue
                return [[x, y] for x, y in sorted(selected, key=lambda point: (point[1], point[0]))]

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
            20,
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
                "Ability Damage", "Damage", 1, 24, int(current.get("damage", 5))
            )
            if damage is None:
                return None
            range_max = self.custom_number_menu(
                "Ability Range", "Range", 1, 12, int(current.get("range_max", 4))
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
                    "custom": "Draw an entirely new area tile by tile.",
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
            if shape == "custom":
                pattern = self.custom_ability_pattern_editor(current.get("custom_pattern", [[0, 0]]))
                if pattern is None:
                    return None
                anchor = self.custom_choice_menu(
                    "Pattern Anchor",
                    ["target", "caster"],
                    str(current.get("pattern_anchor", "target")),
                    hints={
                        "target": "The drawn @ moves to the target cursor.",
                        "caster": "The drawn @ remains on the ability user.",
                    },
                )
                if anchor is None:
                    return None
                rotate = self.custom_choice_menu(
                    "Pattern Rotation",
                    ["yes", "no"],
                    "yes" if bool(current.get("pattern_rotate", True)) else "no",
                    hints={
                        "yes": "Rotate the right-facing drawing toward the cursor.",
                        "no": "Keep the drawing fixed in world orientation.",
                    },
                )
                if rotate is None:
                    return None
                record.update({
                    "custom_pattern": pattern,
                    "pattern_anchor": anchor,
                    "pattern_rotate": rotate == "yes",
                })
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

            armor_pierce = self.custom_number_menu(
                "Attack Properties", "Armor pierced", 0, 8, int(current.get("armor_pierce", 0))
            )
            if armor_pierce is None:
                return None
            displacement = self.custom_choice_menu(
                "Attack Movement",
                [str(value) for value in range(-3, 4)],
                str(current.get("displacement", 0)),
                labels={
                    **{str(value): f"Pull {abs(value)} tile{'s' if abs(value) != 1 else ''}" for value in range(-3, 0)},
                    "0": "No forced movement",
                    **{str(value): f"Push {value} tile{'s' if value != 1 else ''}" for value in range(1, 4)},
                },
            )
            if displacement is None:
                return None
            life_steal = self.custom_number_menu(
                "Attack Properties", "Maximum HP drained", 0, 12, int(current.get("life_steal", 0))
            )
            if life_steal is None:
                return None
            record.update({
                "armor_pierce": armor_pierce,
                "displacement": int(displacement),
                "life_steal": life_steal,
            })

            combo_trigger = self.custom_choice_menu(
                "Conditional Combo",
                ["", "poison", "root", "vulnerable", "any_status", "caster_guarded"],
                (
                    str(current.get("combo_status", ""))
                    or ("any_status" if current.get("combo_any_status") else "")
                    or ("caster_guarded" if current.get("combo_guarded") else "")
                ),
                labels={"": "No combo", "any_status": "Target has any status", "caster_guarded": "Caster is guarding"},
                hints={
                    "poison": "Bonus when the target is poisoned.",
                    "root": "Bonus when the target is rooted.",
                    "vulnerable": "Bonus when the target is vulnerable.",
                    "any_status": "Bonus when any supported status is present.",
                    "caster_guarded": "Bonus while the ability user is guarding.",
                },
            )
            if combo_trigger is None:
                return None
            if combo_trigger:
                combo_damage = self.custom_number_menu(
                    "Combo Rewards", "Bonus damage", 0, 10, int(current.get("combo_damage_bonus", 3))
                )
                if combo_damage is None:
                    return None
                combo_ap = self.custom_number_menu(
                    "Combo Rewards", "AP refunded", 0, 1, int(current.get("combo_ap_gain", 0))
                )
                if combo_ap is None:
                    return None
                combo_mp = self.custom_number_menu(
                    "Combo Rewards", "MP restored", 0, 8, int(current.get("combo_mp_gain", 0))
                )
                if combo_mp is None:
                    return None
                record.update({
                    "combo_status": combo_trigger if combo_trigger in ABILITY_STATUSES else "",
                    "combo_any_status": combo_trigger == "any_status",
                    "combo_guarded": combo_trigger == "caster_guarded",
                    "combo_damage_bonus": combo_damage,
                    "combo_ap_gain": combo_ap,
                    "combo_mp_gain": combo_mp,
                })

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
        while True:
            custom_names = {
                str(record.get("name", "")).casefold()
                for record in self.custom_content_data()["abilities"]
                if isinstance(record, dict)
            }
            skills = [
                skill for skill in create_default_skills()
                if skill.name.casefold() not in excluded_keys
                and (not custom_only or skill.name.casefold() in custom_names)
            ]
            items = [
                MenuItem(
                    label="Create a new ability...",
                    value="__create_ability__",
                    enabled=True,
                    hint="Open the complete attack/effect and hand-drawn pattern designer, then use the result here.",
                )
            ]
            items.extend(
                MenuItem(
                    label=("[Custom] " if skill.name.casefold() in custom_names else "") + skill.name,
                    value=skill.name,
                    enabled=True,
                    hint=f"{skill.effect.replace('_', ' ')} | {skill.mp_cost} MP | {skill.description[:54]}",
                )
                for skill in skills
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select(
                title,
                items,
                footer="Choose an ability, or design a new one without leaving the class builder.",
            )
            if choice is None or choice.value == MENU_BACK:
                return None
            if choice.value == "__create_ability__":
                record = self.custom_ability_builder()
                if record is None:
                    continue
                self.state.message = self.save_custom_ability_record(record)
                created_name = str(record.get("name", ""))
                if any(
                    str(saved.get("name", "")).casefold() == created_name.casefold()
                    for saved in self.custom_content_data()["abilities"]
                    if isinstance(saved, dict)
                ):
                    return created_name
                continue
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

    def custom_building_rows_from_boundary(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        building_type: str,
        floor_index: int = 0,
    ) -> List[str]:
        left = max(1, min(BUILDING_TEMPLATE_WIDTH - 2, min(x1, x2)))
        right = min(BUILDING_TEMPLATE_WIDTH - 2, max(1, max(x1, x2)))
        top = max(1, min(BUILDING_TEMPLATE_HEIGHT - 1, min(y1, y2)))
        bottom = min(BUILDING_TEMPLATE_HEIGHT - 1, max(1, max(y1, y2)))
        if right - left < 7:
            if left + 7 <= BUILDING_TEMPLATE_WIDTH - 2:
                right = left + 7
            else:
                left = max(1, right - 7)
        if bottom - top < 5:
            if top + 5 <= BUILDING_TEMPLATE_HEIGHT - 1:
                bottom = top + 5
            else:
                top = max(1, bottom - 5)
        grid = [[" " for _ in range(BUILDING_TEMPLATE_WIDTH)] for _ in range(BUILDING_TEMPLATE_HEIGHT)]
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                grid[y][x] = "#" if y in {top, bottom} or x in {left, right} else "."
        door_x = (left + right) // 2
        if floor_index <= 0:
            grid[bottom][door_x] = "D"
        else:
            grid[max(top + 1, bottom - 2)][door_x] = ">"
        if bottom > top and floor_index <= 0:
            grid[bottom - 1][door_x] = "."
        if floor_index > 0:
            return ["".join(row) for row in grid]
        record = sanitize_custom_building_template({
            "name": "Boundary Preview",
            "building_type": building_type,
            "rows": ["".join(row) for row in grid],
            "enabled": True,
        })
        return list(record["rows"]) if record else ["".join(row) for row in grid]

    def custom_building_color_code(self, color_key: str) -> str:
        return {
            "white": C.PLAYER,
            "brown": C.WOOD,
            "red": C.HOSTILE,
            "orange": C.SOIL_WET,
            "yellow": C.CROP_READY,
            "green": C.GRASS,
            "blue": C.WATER,
            "purple": C.BIN,
            "gray": C.STONE,
        }.get(str(color_key), "")

    def custom_building_floor_color_map(
        self,
        colors: Sequence[Dict[str, object]],
        floor_index: int,
    ) -> Dict[tuple, str]:
        color_map: Dict[tuple, str] = {}
        for record in colors:
            if not isinstance(record, dict):
                continue
            if int(record.get("floor", 0) or 0) != int(floor_index):
                continue
            color = str(record.get("color", "default"))
            if color not in BUILDING_TEMPLATE_COLOR_KEYS or color == "default":
                continue
            color_map[(int(record.get("x", 0) or 0), int(record.get("y", 0) or 0))] = color
        return color_map

    def custom_building_floor_spawn_points(
        self,
        spawns: Sequence[Dict[str, object]],
        floor_index: int,
    ) -> List[tuple]:
        points: List[tuple] = []
        for record in spawns:
            if not isinstance(record, dict):
                continue
            if int(record.get("floor", 0) or 0) != int(floor_index):
                continue
            points.append((int(record.get("x", 0) or 0), int(record.get("y", 0) or 0)))
        return points

    def draw_custom_building_template_canvas(
        self,
        title: str,
        rows: Sequence[str],
        cursor_x: int,
        cursor_y: int,
        anchor: Optional[tuple] = None,
        selected_rect: Optional[tuple] = None,
        footer: str = "",
        color_overlays: Optional[Dict[tuple, str]] = None,
        spawn_points: Optional[Sequence[tuple]] = None,
    ) -> None:
        clear_screen()
        print(title)
        print("=" * min(BUILDING_TEMPLATE_WIDTH, max(8, len(title))))
        rect = set()
        if anchor is not None:
            ax, ay = anchor
            x1, x2 = sorted((ax, cursor_x))
            y1, y2 = sorted((ay, cursor_y))
            rect = {
                (x, y)
                for y in range(y1, y2 + 1)
                for x in range(x1, x2 + 1)
                if x in {x1, x2} or y in {y1, y2}
            }
        if selected_rect is not None:
            x1, y1, x2, y2 = selected_rect
            rect |= {
                (x, y)
                for y in range(y1, y2 + 1)
                for x in range(x1, x2 + 1)
                if x in {x1, x2} or y in {y1, y2}
            }
        color_overlays = color_overlays or {}
        spawn_set = set(spawn_points or [])
        for y in range(BUILDING_TEMPLATE_HEIGHT):
            raw = str(rows[y]) if y < len(rows) else ""
            line = []
            for x in range(BUILDING_TEMPLATE_WIDTH):
                ch = raw[x] if x < len(raw) else " "
                if x == cursor_x and y == cursor_y:
                    line.append(colorize("@", C.PLACEMENT))
                elif (x, y) in rect:
                    line.append(colorize("*", C.PLACEMENT))
                elif (x, y) in spawn_set:
                    line.append(colorize("N", C.PLACEMENT))
                elif (x, y) in color_overlays:
                    line.append(colorize(ch, self.custom_building_color_code(color_overlays[(x, y)]) or C.WOOD))
                else:
                    line.append(ch)
            print("".join(line))
        print(footer)

    def custom_building_boundary_editor(
        self,
        rows: Sequence[str],
        building_type: str,
        floor_index: int = 0,
    ) -> Optional[List[str]]:
        cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT - 2
        anchor: Optional[tuple] = None
        while True:
            self.draw_custom_building_template_canvas(
                f"Building Boundary - Floor {floor_index + 1}",
                rows,
                cursor_x,
                cursor_y,
                anchor=anchor,
                footer=(
                    "WASD/Arrows move | Z set first/second corner | C clear | Q/Esc keep current\n"
                    +
                    (
                        "Draw the outer rectangle of the building. A door is added to the bottom wall."
                        if floor_index <= 0
                        else "Draw this upper floor. Add stairs with the fixture brush if you need more links."
                    )
                ),
            )
            key = normalize_key(read_key())
            key = key.lower() if len(key) == 1 and key.isalpha() else key
            if key in ["q", "b", "\t", "\x1b"]:
                return list(rows)
            if key == "c":
                anchor = None
                continue
            dx, dy = 0, 0
            if key in ["w", "UP"]:
                dy = -1
            elif key in ["s", "DOWN"]:
                dy = 1
            elif key in ["a", "LEFT"]:
                dx = -1
            elif key in ["d", "RIGHT"]:
                dx = 1
            if dx or dy:
                cursor_x = max(0, min(BUILDING_TEMPLATE_WIDTH - 1, cursor_x + dx))
                cursor_y = max(0, min(BUILDING_TEMPLATE_HEIGHT - 1, cursor_y + dy))
                continue
            if key in MENU_CONFIRM_KEYS:
                if anchor is None:
                    anchor = (cursor_x, cursor_y)
                    continue
                ax, ay = anchor
                return self.custom_building_rows_from_boundary(
                    ax,
                    ay,
                    cursor_x,
                    cursor_y,
                    building_type,
                    floor_index,
                )

    def custom_building_rect_selector(
        self,
        title: str,
        rows: Sequence[str],
    ) -> Optional[Dict[str, int]]:
        cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT // 2
        anchor: Optional[tuple] = None
        while True:
            self.draw_custom_building_template_canvas(
                title,
                rows,
                cursor_x,
                cursor_y,
                anchor=anchor,
                footer="WASD/Arrows move | Z set first/second corner | C clear | Q/Esc cancel",
            )
            key = normalize_key(read_key())
            key = key.lower() if len(key) == 1 and key.isalpha() else key
            if key in ["q", "b", "\t", "\x1b"]:
                return None
            if key == "c":
                anchor = None
                continue
            dx, dy = 0, 0
            if key in ["w", "UP"]:
                dy = -1
            elif key in ["s", "DOWN"]:
                dy = 1
            elif key in ["a", "LEFT"]:
                dx = -1
            elif key in ["d", "RIGHT"]:
                dx = 1
            if dx or dy:
                cursor_x = max(0, min(BUILDING_TEMPLATE_WIDTH - 1, cursor_x + dx))
                cursor_y = max(0, min(BUILDING_TEMPLATE_HEIGHT - 1, cursor_y + dy))
                continue
            if key in MENU_CONFIRM_KEYS:
                if anchor is None:
                    anchor = (cursor_x, cursor_y)
                    continue
                ax, ay = anchor
                x1, x2 = sorted((ax, cursor_x))
                y1, y2 = sorted((ay, cursor_y))
                return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    def custom_building_point_selector(
        self,
        title: str,
        rows: Sequence[str],
        *,
        footer: str = "WASD/Arrows move | Z select point | Q/Esc cancel",
        color_overlays: Optional[Dict[tuple, str]] = None,
        spawn_points: Optional[Sequence[tuple]] = None,
    ) -> Optional[Dict[str, int]]:
        cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT // 2
        while True:
            self.draw_custom_building_template_canvas(
                title,
                rows,
                cursor_x,
                cursor_y,
                footer=footer,
                color_overlays=color_overlays,
                spawn_points=spawn_points,
            )
            key = normalize_key(read_key())
            key = key.lower() if len(key) == 1 and key.isalpha() else key
            if key in ["q", "b", "\t", "\x1b"]:
                return None
            dx, dy = 0, 0
            if key in ["w", "UP"]:
                dy = -1
            elif key in ["s", "DOWN"]:
                dy = 1
            elif key in ["a", "LEFT"]:
                dx = -1
            elif key in ["d", "RIGHT"]:
                dx = 1
            if dx or dy:
                cursor_x = max(0, min(BUILDING_TEMPLATE_WIDTH - 1, cursor_x + dx))
                cursor_y = max(0, min(BUILDING_TEMPLATE_HEIGHT - 1, cursor_y + dy))
                continue
            if key in MENU_CONFIRM_KEYS:
                return {"x": cursor_x, "y": cursor_y}

    def custom_building_zone_menu(
        self,
        rows: Sequence[str],
        zones: Sequence[Dict[str, object]],
        floor_index: int = 0,
    ) -> List[Dict[str, object]]:
        current_zones = [dict(zone) for zone in zones if isinstance(zone, dict)]
        while True:
            items = [
                MenuItem(label="Add functional zone", value="add", enabled=len(current_zones) < 16),
            ]
            items.extend(
                MenuItem(
                    label=f"F{int(zone.get('floor', 0)) + 1} {BUILDING_TEMPLATE_ZONE_LABELS.get(str(zone.get('kind')), str(zone.get('kind')))} "
                    f"{zone.get('x1')},{zone.get('y1')}-{zone.get('x2')},{zone.get('y2')}",
                    value=f"zone:{index}",
                    enabled=True,
                    hint="inspect/delete",
                )
                for index, zone in enumerate(current_zones)
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select(
                "Building Zones",
                items,
                footer="Zones describe room functions for NPC schedules. They do not place furniture.",
            )
            if choice is None or choice.value == MENU_BACK:
                return current_zones
            if choice.value == "add":
                kind = self.custom_choice_menu(
                    "Zone Function",
                    BUILDING_TEMPLATE_ZONE_KINDS,
                    "bedroom",
                    labels=BUILDING_TEMPLATE_ZONE_LABELS,
                )
                if kind is None:
                    continue
                rect = self.custom_building_rect_selector(
                    f"Draw {BUILDING_TEMPLATE_ZONE_LABELS.get(kind, kind)} Zone",
                    rows,
                )
                if rect:
                    rect["kind"] = kind
                    rect["floor"] = floor_index
                    current_zones.append(rect)
                continue
            try:
                index = int(str(choice.value).split(":", 1)[1])
                zone = current_zones[index]
            except (ValueError, IndexError):
                continue
            action = menu_select(
                "Zone",
                [
                    MenuItem(label="Delete zone", value="delete", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                extra_lines=[
                    BUILDING_TEMPLATE_ZONE_LABELS.get(str(zone.get("kind")), str(zone.get("kind"))),
                    f"Floor {int(zone.get('floor', 0)) + 1}",
                    f"{zone.get('x1')},{zone.get('y1')} to {zone.get('x2')},{zone.get('y2')}",
                ],
            )
            if action is not None and action.value == "delete":
                del current_zones[index]

    def custom_building_fixture_brushes(self) -> List[tuple]:
        return [
            ("Floor", ".", "open walkable floor"),
            ("Wall", "#", "outer or heavy interior wall"),
            ("Horizontal Partition", "-", "thin divider/room boundary"),
            ("Open Door / Vertical Partition", "|", "passable vertical doorway or divider"),
            ("Closed Room Door", "_", "closed interior door that can be opened"),
            ("Door", "D", "exit door"),
            ("Stairs Up", "<", "stairs to the floor above"),
            ("Stairs Down", ">", "stairs to the floor below"),
            ("Service Counter", "&", "shopkeeper/service interaction"),
            ("Shop Shelf", "$", "shop stock"),
            ("Clinic Supplies", "+", "clinic utility"),
            ("Bookcase", "l", "library stacks"),
            ("Workbench", "w", "crafting/workshop bench"),
            ("Tool Rack", "a", "tool display"),
            ("Materials Bench", "x", "materials bench"),
            ("Bed", "b", "bedroom/inn bed"),
            ("Table", "t", "table"),
            ("Chair", "c", "chair"),
            ("Storage", "s", "shelf/storage"),
            ("Hearth/Kitchen", "f", "hearth or kitchen utility"),
            ("Records/Desk", "P", "records, notice, or public desk"),
            ("Writing Desk", "d", "office/civic desk"),
            ("Planter/Decor", "p", "decoration"),
            ("Rug", ",", "soft decoration"),
            ("Erase Outside", " ", "empty exterior void"),
        ]

    def custom_building_fixture_palette(self, current_brush: str) -> Optional[str]:
        brushes = self.custom_building_fixture_brushes()
        items = [
            MenuItem(
                label=f"{label} ({symbol if symbol != ' ' else 'space'})",
                value=symbol,
                enabled=True,
                hint=f"{hint}{' | current' if symbol == current_brush else ''}",
            )
            for label, symbol, hint in brushes
        ]
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = menu_select("Fixture Brush", items, footer="Choose what Z/Enter paints on the template.")
        if choice is None or choice.value == MENU_BACK:
            return None
        return str(choice.value)

    def custom_building_inspect_tile(
        self,
        rows: Sequence[str],
        cursor_x: int,
        cursor_y: int,
        brush: str,
    ) -> None:
        tile = " "
        if 0 <= cursor_y < len(rows):
            row = str(rows[cursor_y])
            if 0 <= cursor_x < len(row):
                tile = row[cursor_x]
        brush_lookup = {
            str(symbol): (str(label), str(hint))
            for label, symbol, hint in self.custom_building_fixture_brushes()
        }
        label, hint = brush_lookup.get(tile, ("Unknown", "this tile will be repaired or replaced during validation"))
        symbol = tile if tile != " " else "space"
        self.draw_custom_building_template_canvas(
            "Inspect Template Tile",
            rows,
            cursor_x,
            cursor_y,
            footer=(
                f"Cursor: {cursor_x},{cursor_y} | Tile: {symbol} | {label}\n"
                f"{hint}.\n"
                f"Current brush: {brush if brush != ' ' else 'space'} | Press any key to return to the editor."
            ),
        )
        read_key()

    def custom_building_fixture_editor(self, rows: Sequence[str], floor_index: int = 0) -> List[str]:
        grid = [list(str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH]) for row in rows]
        while len(grid) < BUILDING_TEMPLATE_HEIGHT:
            grid.append([" " for _ in range(BUILDING_TEMPLATE_WIDTH)])
        cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT // 2
        brush = "."
        while True:
            self.draw_custom_building_template_canvas(
                f"Place Fixtures and Decorations - Floor {floor_index + 1}",
                ["".join(row) for row in grid],
                cursor_x,
                cursor_y,
                footer=(
                    f"Brush: {brush if brush != ' ' else 'space'} | "
                    "WASD move | Z paint | P palette | I inspect | Q/Esc done"
                ),
            )
            key = normalize_key(read_key())
            key = key.lower() if len(key) == 1 and key.isalpha() else key
            if key in ["q", "b", "\t", "\x1b"]:
                return ["".join(row) for row in grid]
            if key == "p":
                selected = self.custom_building_fixture_palette(brush)
                if selected is not None:
                    brush = selected
                continue
            if key == "i":
                self.custom_building_inspect_tile(
                    ["".join(row) for row in grid],
                    cursor_x,
                    cursor_y,
                    brush,
                )
                continue
            dx, dy = 0, 0
            if key in ["w", "UP"]:
                dy = -1
            elif key in ["s", "DOWN"]:
                dy = 1
            elif key in ["a", "LEFT"]:
                dx = -1
            elif key in ["d", "RIGHT"]:
                dx = 1
            if dx or dy:
                cursor_x = max(0, min(BUILDING_TEMPLATE_WIDTH - 1, cursor_x + dx))
                cursor_y = max(0, min(BUILDING_TEMPLATE_HEIGHT - 1, cursor_y + dy))
                continue
            if key in MENU_CONFIRM_KEYS:
                grid[cursor_y][cursor_x] = brush

    def custom_building_color_palette(self, current_color: str) -> Optional[str]:
        items = []
        for color_key in BUILDING_TEMPLATE_COLOR_KEYS:
            label = BUILDING_TEMPLATE_COLOR_LABELS.get(color_key, color_key.title())
            code = self.custom_building_color_code(color_key)
            sample = colorize("██", code) if code else "  "
            items.append(
                MenuItem(
                    label=f"{sample} {label}",
                    value=color_key,
                    enabled=True,
                    hint="current" if color_key == current_color else "",
                )
            )
        items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
        choice = menu_select("Paint Color", items, footer="Default removes custom color from the tile.")
        if choice is None or choice.value == MENU_BACK:
            return None
        return str(choice.value)

    def set_custom_building_color_mark(
        self,
        colors: Sequence[Dict[str, object]],
        floor_index: int,
        x: int,
        y: int,
        color_key: str,
    ) -> List[Dict[str, object]]:
        updated = [
            dict(record)
            for record in colors
            if isinstance(record, dict)
            and not (
                int(record.get("floor", 0) or 0) == int(floor_index)
                and int(record.get("x", 0) or 0) == int(x)
                and int(record.get("y", 0) or 0) == int(y)
            )
        ]
        if color_key != "default" and len(updated) < BUILDING_TEMPLATE_MAX_COLOR_MARKS:
            updated.append({
                "floor": int(floor_index),
                "x": int(x),
                "y": int(y),
                "color": str(color_key),
            })
        return updated

    def custom_building_color_editor(
        self,
        rows: Sequence[str],
        colors: Sequence[Dict[str, object]],
        floor_index: int = 0,
    ) -> List[Dict[str, object]]:
        painted = [dict(record) for record in colors if isinstance(record, dict)]
        cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT // 2
        brush = "brown"
        while True:
            color_map = self.custom_building_floor_color_map(painted, floor_index)
            brush_label = BUILDING_TEMPLATE_COLOR_LABELS.get(brush, brush.title())
            self.draw_custom_building_template_canvas(
                f"Paint Tile Colors - Floor {floor_index + 1}",
                rows,
                cursor_x,
                cursor_y,
                footer=(
                    f"Color: {brush_label} | WASD move | Z paint | E erase | P palette | Q/Esc done\n"
                    "Paint changes color only; it does not change what the tile does."
                ),
                color_overlays=color_map,
            )
            key = normalize_key(read_key())
            key = key.lower() if len(key) == 1 and key.isalpha() else key
            if key in ["q", "b", "\t", "\x1b"]:
                return painted
            if key == "p":
                selected = self.custom_building_color_palette(brush)
                if selected is not None:
                    brush = selected
                continue
            if key == "e":
                painted = self.set_custom_building_color_mark(
                    painted,
                    floor_index,
                    cursor_x,
                    cursor_y,
                    "default",
                )
                continue
            dx, dy = 0, 0
            if key in ["w", "UP"]:
                dy = -1
            elif key in ["s", "DOWN"]:
                dy = 1
            elif key in ["a", "LEFT"]:
                dx = -1
            elif key in ["d", "RIGHT"]:
                dx = 1
            if dx or dy:
                cursor_x = max(0, min(BUILDING_TEMPLATE_WIDTH - 1, cursor_x + dx))
                cursor_y = max(0, min(BUILDING_TEMPLATE_HEIGHT - 1, cursor_y + dy))
                continue
            if key in MENU_CONFIRM_KEYS:
                painted = self.set_custom_building_color_mark(
                    painted,
                    floor_index,
                    cursor_x,
                    cursor_y,
                    brush,
                )

    def custom_building_spawn_menu(
        self,
        rows: Sequence[str],
        spawns: Sequence[Dict[str, object]],
        floor_index: int,
        colors: Sequence[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        current_spawns = [dict(spawn) for spawn in spawns if isinstance(spawn, dict)]
        while True:
            floor_spawns = [
                spawn
                for spawn in current_spawns
                if int(spawn.get("floor", 0) or 0) == int(floor_index)
            ]
            items = [
                MenuItem(
                    label="Add NPC spawn point",
                    value="add",
                    enabled=len(current_spawns) < BUILDING_TEMPLATE_MAX_SPAWNS,
                    hint=f"{len(current_spawns)}/{BUILDING_TEMPLATE_MAX_SPAWNS}",
                )
            ]
            items.extend(
                MenuItem(
                    label=f"F{int(spawn.get('floor', 0)) + 1} spawn at {spawn.get('x')},{spawn.get('y')}",
                    value=f"spawn:{index}",
                    enabled=True,
                    hint="delete",
                )
                for index, spawn in enumerate(current_spawns)
            )
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            choice = menu_select(
                "NPC Spawn Points",
                items,
                footer="Spawn points guide where residents stand or begin routines inside this template.",
                extra_lines=[
                    f"Editing floor {floor_index + 1}",
                    f"Visible on this floor: {len(floor_spawns)}",
                ],
            )
            if choice is None or choice.value == MENU_BACK:
                return current_spawns
            if choice.value == "add":
                point = self.custom_building_point_selector(
                    f"Place NPC Spawn - Floor {floor_index + 1}",
                    rows,
                    footer="WASD/Arrows move | Z place NPC spawn | Q/Esc cancel",
                    color_overlays=self.custom_building_floor_color_map(colors, floor_index),
                    spawn_points=self.custom_building_floor_spawn_points(current_spawns, floor_index),
                )
                if point:
                    new_spawn = {
                        "floor": int(floor_index),
                        "x": int(point["x"]),
                        "y": int(point["y"]),
                    }
                    duplicate = any(
                        int(spawn.get("floor", 0) or 0) == new_spawn["floor"]
                        and int(spawn.get("x", 0) or 0) == new_spawn["x"]
                        and int(spawn.get("y", 0) or 0) == new_spawn["y"]
                        for spawn in current_spawns
                    )
                    if not duplicate:
                        current_spawns.append(new_spawn)
                continue
            try:
                index = int(str(choice.value).split(":", 1)[1])
            except (ValueError, IndexError):
                continue
            if 0 <= index < len(current_spawns):
                del current_spawns[index]

    def custom_building_template_builder(self, existing: Optional[Dict[str, object]] = None) -> Optional[Dict[str, object]]:
        current = sanitize_custom_building_template(existing or {
            "name": "New Building",
            "building_type": "home",
            "enabled": True,
        }) or {}
        name = text_entry_menu("Building Template", "Template name?", str(current.get("name", "New Building")), 32)
        if name is None:
            return None
        description = text_entry_menu(
            "Building Template",
            "Short description?",
            str(current.get("description", "A custom procedural-town building template.")),
            220,
        )
        if description is None:
            return None
        building_type = self.custom_choice_menu(
            "Building Type",
            BUILDING_TEMPLATE_TYPES,
            str(current.get("building_type", "home")),
            labels=BUILDING_TEMPLATE_TYPE_LABELS,
            hints={key: "joins this procedural building pool" for key in BUILDING_TEMPLATE_TYPES},
        )
        if building_type is None:
            return None
        default_occupancy = int(current.get("max_occupancy", 4 if building_type in {"home", "inn"} else 0))
        if existing is None and building_type != str(current.get("building_type", "home")):
            default_occupancy = 4 if building_type in {"home", "inn"} else 0
        occupancy = self.custom_number_menu(
            "Maximum Occupancy",
            "Occupancy",
            0,
            24,
            default_occupancy,
        )
        if occupancy is None:
            return None
        enabled = self.custom_choice_menu(
            "Generator Use",
            ["enabled", "disabled"],
            "enabled" if current.get("enabled", True) else "disabled",
            hints={
                "enabled": "May appear in generated towns for this building type.",
                "disabled": "Saved for editing/export but not used by generation.",
            },
        )
        if enabled is None:
            return None
        floors = [
            {
                "name": str(floor.get("name", "Ground Floor" if index == 0 else f"Floor {index + 1}")),
                "rows": list(floor.get("rows", [])) or default_custom_building_template_rows(building_type, index),
            }
            for index, floor in enumerate(current.get("floors", []) or [])
            if isinstance(floor, dict)
        ]
        if not floors:
            floors = [{
                "name": "Ground Floor",
                "rows": list(current.get("rows", [])) or default_custom_building_template_rows(building_type),
            }]
        zones = [dict(zone) for zone in current.get("zones", []) if isinstance(zone, dict)]
        spawns = [dict(spawn) for spawn in current.get("spawns", []) if isinstance(spawn, dict)]
        colors = [dict(color) for color in current.get("colors", []) if isinstance(color, dict)]
        current_floor = 0
        if existing is None:
            floors[0]["rows"] = self.custom_building_boundary_editor(
                floors[0]["rows"],
                building_type,
                0,
            ) or floors[0]["rows"]
        while True:
            draft = sanitize_custom_building_template({
                "name": name,
                "description": description,
                "building_type": building_type,
                "max_occupancy": occupancy,
                "enabled": enabled == "enabled",
                "floors": floors,
                "zones": zones,
                "spawns": spawns,
                "colors": colors,
            })
            if draft is None:
                return None
            floors = [
                {
                    "name": str(floor.get("name", "Ground Floor" if index == 0 else f"Floor {index + 1}")),
                    "rows": list(floor.get("rows", [])),
                }
                for index, floor in enumerate(draft.get("floors", []) or [])
                if isinstance(floor, dict)
            ] or floors
            zones = [dict(zone) for zone in draft.get("zones", []) if isinstance(zone, dict)]
            spawns = [dict(spawn) for spawn in draft.get("spawns", []) if isinstance(spawn, dict)]
            colors = [dict(color) for color in draft.get("colors", []) if isinstance(color, dict)]
            current_floor = max(0, min(current_floor, len(floors) - 1))
            current_floor_name = str(floors[current_floor].get("name", f"Floor {current_floor + 1}"))
            choice = menu_select(
                "Building Template",
                [
                    MenuItem(label="Switch floor", value="floor", enabled=len(floors) > 1, hint=f"editing F{current_floor + 1}: {current_floor_name}"),
                    MenuItem(label="Add upper floor", value="add_floor", enabled=len(floors) < BUILDING_TEMPLATE_MAX_FLOORS, hint=f"{len(floors)}/{BUILDING_TEMPLATE_MAX_FLOORS} floors"),
                    MenuItem(label="Remove current upper floor", value="remove_floor", enabled=len(floors) > 1 and current_floor > 0, hint="keeps ground floor"),
                    MenuItem(label="Redraw current-floor boundary", value="boundary", enabled=True, hint=f"F{current_floor + 1} cursor rectangle"),
                    MenuItem(label="Designate functional zones", value="zones", enabled=True, hint=f"{len(zones)} zones"),
                    MenuItem(label="Designate NPC spawn points", value="spawns", enabled=True, hint=f"{len(spawns)} spawns"),
                    MenuItem(label="Place fixtures and decorations", value="fixtures", enabled=True, hint=f"F{current_floor + 1} cursor paint mode"),
                    MenuItem(label="Paint tile colors", value="colors", enabled=True, hint=f"{len(colors)} painted tiles"),
                    MenuItem(label="Preview template", value="preview", enabled=True),
                    MenuItem(label="Save template", value="save", enabled=True),
                    MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
                ],
                footer="Draw rooms, place fixtures/doors, assign zones/spawns, paint colors, then save. Stairs: < up, > down.",
                extra_lines=[f"Editing F{current_floor + 1}: {current_floor_name}", ""] + custom_building_template_summary(draft)[:12],
            )
            if choice is None or choice.value == MENU_BACK:
                return None
            if choice.value == "floor":
                floor_choice = menu_select(
                    "Select Floor",
                    [
                        MenuItem(
                            label=f"F{index + 1}: {floor.get('name', 'Floor')}",
                            value=index,
                            enabled=True,
                            hint="current" if index == current_floor else "",
                        )
                        for index, floor in enumerate(floors)
                    ] + [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                    footer="Choose which floor the boundary, zone, and fixture tools edit.",
                )
                if floor_choice is not None and floor_choice.value != MENU_BACK:
                    current_floor = int(floor_choice.value)
            elif choice.value == "add_floor":
                new_index = len(floors)
                floors.append({
                    "name": f"Floor {new_index + 1}",
                    "rows": default_custom_building_template_rows(building_type, new_index),
                })
                current_floor = new_index
            elif choice.value == "remove_floor":
                removed_floor = current_floor
                floors.pop(removed_floor)
                updated_zones = []
                for zone in zones:
                    zone_floor = int(zone.get("floor", 0) or 0)
                    if zone_floor == removed_floor:
                        continue
                    if zone_floor > removed_floor:
                        zone["floor"] = zone_floor - 1
                    updated_zones.append(zone)
                zones = updated_zones
                updated_spawns = []
                for spawn in spawns:
                    spawn_floor = int(spawn.get("floor", 0) or 0)
                    if spawn_floor == removed_floor:
                        continue
                    if spawn_floor > removed_floor:
                        spawn["floor"] = spawn_floor - 1
                    updated_spawns.append(spawn)
                spawns = updated_spawns
                updated_colors = []
                for color in colors:
                    color_floor = int(color.get("floor", 0) or 0)
                    if color_floor == removed_floor:
                        continue
                    if color_floor > removed_floor:
                        color["floor"] = color_floor - 1
                    updated_colors.append(color)
                colors = updated_colors
                current_floor = max(0, min(removed_floor - 1, len(floors) - 1))
            elif choice.value == "boundary":
                floors[current_floor]["rows"] = self.custom_building_boundary_editor(
                    floors[current_floor]["rows"],
                    building_type,
                    current_floor,
                ) or floors[current_floor]["rows"]
            elif choice.value == "zones":
                zones = self.custom_building_zone_menu(
                    floors[current_floor]["rows"],
                    zones,
                    current_floor,
                )
            elif choice.value == "spawns":
                spawns = self.custom_building_spawn_menu(
                    floors[current_floor]["rows"],
                    spawns,
                    current_floor,
                    colors,
                )
            elif choice.value == "fixtures":
                floors[current_floor]["rows"] = self.custom_building_fixture_editor(
                    floors[current_floor]["rows"],
                    current_floor,
                )
            elif choice.value == "colors":
                colors = self.custom_building_color_editor(
                    floors[current_floor]["rows"],
                    colors,
                    current_floor,
                )
            elif choice.value == "preview":
                menu_select(
                    str(draft.get("name", "Building Template")),
                    [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                    extra_lines=custom_building_template_summary(draft),
                )
            elif choice.value == "save":
                return draft

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
                        or str(record.get("building_type", ""))
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
            "- Damage abilities can use standard shapes or a hand-drawn 13x13 area-of-effect pattern.",
            "- Drawn patterns may follow the target or caster and may rotate toward the aiming cursor.",
            "- Attacks can pierce armor, push or pull enemies, drain HP, and trigger conditional combo rewards.",
            "- Optional poison, root, vulnerable, and persistent elemental zones are supported.",
            "- Long builder lists scroll automatically; W/S moves by row and A/D pages.",
            "- Values are bounded to combinations the tactical engine can resolve safely.",
            "- The balance estimate includes drawn coverage and advanced attack properties but does not forbid them.",
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
            "Building Templates",
            "- Create procedural town/city interiors for homes, shops, inns, clinics, libraries, workshops, and town halls.",
            "- The builder starts with a cursor-drawn boundary, then lets you designate room zones and paint fixtures/decor.",
            "- Enabled templates join the matching building-type pool; missing essentials such as doors and service counters are repaired safely.",
            "- Max occupancy can change how many generated residents the chosen building can house.",
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
            building_template_count = len(content.get("building_templates", []))
            total_count = (
                ability_count
                + class_count
                + enemy_count
                + equipment_count
                + map_count
                + room_count
                + building_template_count
            )
            items = [
                MenuItem(label="Abilities", value="abilities", enabled=True, hint=f"{ability_count} installed"),
                MenuItem(label="Classes", value="classes", enabled=True, hint=f"{class_count} installed"),
                MenuItem(label="Enemies", value="enemies", enabled=True, hint=f"{enemy_count} installed"),
                MenuItem(label="Equipment", value="equipment", enabled=True, hint=f"{equipment_count} installed"),
                MenuItem(label="Combat Maps", value="maps", enabled=True, hint=f"{map_count} installed"),
                MenuItem(label="Dungeon Rooms", value="dungeon_rooms", enabled=True, hint=f"{room_count} installed | opt-in"),
                MenuItem(label="Building Templates", value="building_templates", enabled=True, hint=f"{building_template_count} installed | towns/cities"),
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
                    f"{total_count} records across seven custom-content types",
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
            elif choice.value == "building_templates":
                self.custom_extended_record_menu(
                    "Building Templates", "building_templates", "Create building template",
                    self.custom_building_template_builder, custom_building_template_summary,
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
