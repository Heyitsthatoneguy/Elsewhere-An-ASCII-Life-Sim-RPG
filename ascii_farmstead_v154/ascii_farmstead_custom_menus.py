from __future__ import annotations

import copy
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ascii_farmstead_custom_content import (
    ABILITY_EFFECTS,
    ABILITY_SHAPES,
    ABILITY_STATUSES,
    ABILITY_ZONES,
    CUSTOM_CONTENT_EXPORT_PATH,
    CUSTOM_CONTENT_PATH,
    ELEMENTS,
    WORLD_ABILITY_ELEMENTS,
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
from ascii_farmstead_data import AUTHORED_TOWN_RESIDENCE_DATA, MENU_CONFIRM_KEYS
from ascii_farmstead_support import (
    C,
    clear_screen,
    colorize,
    normalize_key,
    read_key,
    read_key_or_mouse,
)
from ascii_farmstead_ui import MenuItem, menu_select, text_entry_menu
from ascii_farmstead_visuals import interior_tile_color
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
    BUILDING_TEMPLATE_FURNISHING_DATA,
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
    custom_building_template_override,
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

BUILT_IN_AUTHORED_BUILDING_PRESETS = (
    ("Farmhouse", "home", "make_house_map", 6),
    ("General Store", "general_store", "make_general_store_map", 0),
    ("Blacksmith", "workshop", "make_blacksmith_interior_map", 0),
    ("Library", "library", "make_library_interior_map", 0),
    ("Mayor's House", "home", "make_mayor_house_map", 4),
    ("Mae's Inn", "inn", "make_inn_interior_map", 8),
    ("Museum", "library", "make_museum_interior_map", 0),
    ("Furniture Store", "general_store", "make_furniture_store_map", 0),
    ("Carpenter Store", "carpenter", "make_carpenter_store_map", 0),
    ("Animal Store", "general_store", "make_animal_store_map", 0),
    ("Clinic", "clinic", "make_clinic_map", 0),
    ("Town Hall", "town_hall", "make_town_hall_map", 0),
    ("Market Row", "market_stall", "make_market_row_map", 0),
)


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
            mouse_enabled=True,
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
        choice = menu_select(
            title,
            items,
            footer="Choose one option.",
            mouse_enabled=True,
        )
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
            print("WASD/arrows move | Z/Space toggle | C clear | R reset | Enter accept | B/X/Esc/Q/Tab cancel")
            key = normalize_key(read_key())
            if key in {"\x1b", "x", "q", "b", "\t"}:
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
        world_element = self.custom_choice_menu(
            "World Affinity",
            WORLD_ABILITY_ELEMENTS,
            str(current.get("world_element", "")),
            labels={"": "Automatic / combat only"},
            hints={
                "": "Infer safe world behavior from the ability name or elemental zone when possible.",
                "Fire": "Ignite wilderness vegetation and melt temporary ice.",
                "Water": "Extinguish fires, soak soil, and water crops.",
                "Frost": "Freeze water into temporary ice bridges.",
                "Earth": "Raise stepping stones, till soil, and clear loose obstacles.",
                "Storm": "Charge open ground and scatter brush.",
                "Wind": "Disperse weeds, wet ground, and weak fire.",
                "Nature": "Restore scorched ground and encourage crop growth.",
                "Poison": "Wither weeds and invasive vegetation.",
                "Light": "Purify damaged ground and nurture crops.",
                "Shadow": "Veil exposed terrain temporarily.",
            },
        )
        if world_element is None:
            return None

        record: Dict[str, object] = {
            "name": name,
            "description": description,
            "effect": effect,
            "mp_cost": mp_cost,
            "world_element": world_element,
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

    @staticmethod
    def custom_building_mouse_canvas_point(
        event: Dict[str, object],
    ) -> Optional[tuple]:
        """Translate a screen-space mouse event into template coordinates."""
        if event.get("kind") != "mouse":
            return None
        try:
            x = int(event.get("x", -1))
            y = int(event.get("y", -1)) - 2
        except (TypeError, ValueError):
            return None
        if (
            0 <= x < BUILDING_TEMPLATE_WIDTH
            and 0 <= y < BUILDING_TEMPLATE_HEIGHT
        ):
            return x, y
        return None

    @staticmethod
    def custom_building_line_points(
        start: tuple,
        end: tuple,
    ) -> List[tuple]:
        """Return an unbroken Bresenham stroke between two cursor positions."""
        x1, y1 = int(start[0]), int(start[1])
        x2, y2 = int(end[0]), int(end[1])
        points: List[tuple] = []
        dx = abs(x2 - x1)
        sx = 1 if x1 < x2 else -1
        dy = -abs(y2 - y1)
        sy = 1 if y1 < y2 else -1
        error = dx + dy
        while True:
            if (
                0 <= x1 < BUILDING_TEMPLATE_WIDTH
                and 0 <= y1 < BUILDING_TEMPLATE_HEIGHT
            ):
                points.append((x1, y1))
            if (x1, y1) == (x2, y2):
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x1 += sx
            if doubled <= dx:
                error += dx
                y1 += sy
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
        zone_overlays: Optional[Dict[tuple, str]] = None,
        preview_tiles: Optional[Dict[tuple, tuple]] = None,
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
        zone_overlays = zone_overlays or {}
        preview_tiles = preview_tiles or {}
        for y in range(BUILDING_TEMPLATE_HEIGHT):
            raw = str(rows[y]) if y < len(rows) else ""
            line = []
            for x in range(BUILDING_TEMPLATE_WIDTH):
                ch = raw[x] if x < len(raw) else " "
                if x == cursor_x and y == cursor_y:
                    line.append(colorize("@", C.PLACEMENT))
                elif (x, y) in rect:
                    line.append(colorize("*", C.PLACEMENT))
                elif (x, y) in preview_tiles:
                    preview_glyph, overwrites = preview_tiles[(x, y)]
                    line.append(colorize(
                        str(preview_glyph)[:1],
                        C.PLACEMENT if bool(overwrites) else C.UI_SELECTED,
                    ))
                elif (x, y) in spawn_set:
                    line.append(colorize("N", C.PLACEMENT))
                elif (x, y) in zone_overlays:
                    line.append(colorize(str(zone_overlays[(x, y)])[:1], C.INFRA))
                elif (x, y) in color_overlays:
                    line.append(colorize(ch, self.custom_building_color_code(color_overlays[(x, y)]) or C.WOOD))
                else:
                    line.append(colorize(
                        ch,
                        interior_tile_color(
                            ch,
                            context="public",
                            ambient=False,
                        ),
                    ))
            print("".join(line))
        print(f"Cursor: {cursor_x},{cursor_y}")
        print(footer)

    def custom_building_boundary_editor(
        self,
        rows: Sequence[str],
        building_type: str,
        floor_index: int = 0,
    ) -> Optional[List[str]]:
        cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT - 2
        anchor: Optional[tuple] = None
        mouse_left_down = False
        while True:
            self.draw_custom_building_template_canvas(
                f"Building Boundary - Floor {floor_index + 1}",
                rows,
                cursor_x,
                cursor_y,
                anchor=anchor,
                footer=(
                    "Left-drag draw | Right-click/C clear | WASD/Arrows move | Z corners | B/Q/Esc/Tab keep current\n"
                    +
                    (
                        "Draw the outer rectangle of the building. A door is added to the bottom wall."
                        if floor_index <= 0
                        else "Draw this upper floor. Add stairs with the fixture brush if you need more links."
                    )
                ),
            )
            event = read_key_or_mouse()
            if event.get("kind") == "mouse":
                point = self.custom_building_mouse_canvas_point(event)
                raw_left = bool(event.get("left", False))
                moved = bool(event.get("moved", False))
                left = raw_left and (mouse_left_down or not moved)
                if bool(event.get("right", False)):
                    anchor = None
                    mouse_left_down = False
                    continue
                if point is not None and left:
                    cursor_x, cursor_y = point
                    if not mouse_left_down:
                        anchor = point
                    mouse_left_down = True
                    continue
                if mouse_left_down and not raw_left:
                    mouse_left_down = False
                    if point is not None and anchor is not None:
                        cursor_x, cursor_y = point
                        ax, ay = anchor
                        return self.custom_building_rows_from_boundary(
                            ax,
                            ay,
                            cursor_x,
                            cursor_y,
                            building_type,
                            floor_index,
                        )
                continue
            key = normalize_key(str(event.get("key", "")))
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
        *,
        initial_rect: Optional[tuple] = None,
    ) -> Optional[Dict[str, int]]:
        cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT // 2
        anchor: Optional[tuple] = None
        mouse_left_down = False
        while True:
            self.draw_custom_building_template_canvas(
                title,
                rows,
                cursor_x,
                cursor_y,
                anchor=anchor,
                selected_rect=initial_rect if anchor is None else None,
                footer=(
                    "Left-drag draw new boundaries | Right-click/C clear selection | "
                    "WASD/Arrows move | Z corners | B/Q/Esc/Tab cancel"
                ),
            )
            event = read_key_or_mouse()
            if event.get("kind") == "mouse":
                point = self.custom_building_mouse_canvas_point(event)
                raw_left = bool(event.get("left", False))
                moved = bool(event.get("moved", False))
                left = raw_left and (mouse_left_down or not moved)
                if bool(event.get("right", False)):
                    anchor = None
                    mouse_left_down = False
                    continue
                if point is not None and left:
                    cursor_x, cursor_y = point
                    if not mouse_left_down:
                        anchor = point
                    mouse_left_down = True
                    continue
                if mouse_left_down and not raw_left:
                    mouse_left_down = False
                    if point is not None and anchor is not None:
                        cursor_x, cursor_y = point
                        ax, ay = anchor
                        x1, x2 = sorted((ax, cursor_x))
                        y1, y2 = sorted((ay, cursor_y))
                        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
                continue
            key = normalize_key(str(event.get("key", "")))
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
        footer: str = "WASD/Arrows move | Z select point | B/Q/Esc/Tab cancel",
        color_overlays: Optional[Dict[tuple, str]] = None,
        spawn_points: Optional[Sequence[tuple]] = None,
        initial_point: Optional[tuple] = None,
    ) -> Optional[Dict[str, int]]:
        if initial_point is None:
            cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT // 2
        else:
            cursor_x = max(0, min(BUILDING_TEMPLATE_WIDTH - 1, int(initial_point[0])))
            cursor_y = max(0, min(BUILDING_TEMPLATE_HEIGHT - 1, int(initial_point[1])))
        if "Left-click" not in footer:
            footer = f"Left-click select | Right-click cancel | {footer}"
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
            event = read_key_or_mouse()
            if event.get("kind") == "mouse":
                if bool(event.get("right", False)):
                    return None
                point = self.custom_building_mouse_canvas_point(event)
                if (
                    point is not None
                    and bool(event.get("left", False))
                    and not bool(event.get("moved", False))
                ):
                    cursor_x, cursor_y = point
                    return {"x": cursor_x, "y": cursor_y}
                continue
            key = normalize_key(str(event.get("key", "")))
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

        def choose_zone(title: str, indices: Sequence[int]) -> Optional[int]:
            choice = menu_select(
                title,
                [
                    MenuItem(
                        label=(
                            f"F{int(current_zones[index].get('floor', 0)) + 1} "
                            f"{BUILDING_TEMPLATE_ZONE_LABELS.get(str(current_zones[index].get('kind')), str(current_zones[index].get('kind')))}"
                        ),
                        value=index,
                        enabled=True,
                        hint=(
                            f"{current_zones[index].get('x1')},{current_zones[index].get('y1')} to "
                            f"{current_zones[index].get('x2')},{current_zones[index].get('y2')}"
                        ),
                    )
                    for index in indices
                ] + [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                footer="Choose the zone you want to change.",
                mouse_enabled=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return None
            try:
                return int(choice.value)
            except (TypeError, ValueError):
                return None

        while True:
            floor_indices = [
                index
                for index, zone in enumerate(current_zones)
                if int(zone.get("floor", 0) or 0) == int(floor_index)
            ]
            items = [
                MenuItem(
                    label="Draw a new zone",
                    value="add",
                    enabled=len(current_zones) < 16,
                    hint="choose a function, then drag its boundaries",
                ),
                MenuItem(
                    label="Redraw a zone",
                    value="redraw",
                    enabled=bool(floor_indices),
                    hint="replace an existing zone's boundaries",
                ),
                MenuItem(
                    label="Change a zone's function",
                    value="kind",
                    enabled=bool(current_zones),
                ),
                MenuItem(
                    label="Delete one zone",
                    value="delete",
                    enabled=bool(current_zones),
                ),
                MenuItem(
                    label="Delete all zones on this floor",
                    value="delete_floor",
                    enabled=bool(floor_indices),
                    hint=f"{len(floor_indices)} zone{'s' if len(floor_indices) != 1 else ''}",
                ),
            ]
            items.append(MenuItem(label="Back", value=MENU_BACK, enabled=True))
            floor_zone_lines = [
                (
                    f"- {BUILDING_TEMPLATE_ZONE_LABELS.get(str(current_zones[index].get('kind')), str(current_zones[index].get('kind')))}: "
                    f"{current_zones[index].get('x1')},{current_zones[index].get('y1')} to "
                    f"{current_zones[index].get('x2')},{current_zones[index].get('y2')}"
                )
                for index in floor_indices
            ]
            choice = menu_select(
                f"Functional Zones - Floor {floor_index + 1}",
                items,
                footer="Draw, redraw, rename, or delete zones here. Zones guide NPC schedules and never place furniture.",
                extra_lines=[
                    f"{len(floor_indices)} zone{'s' if len(floor_indices) != 1 else ''} on this floor",
                    *(floor_zone_lines or ["- No zones drawn yet."]),
                ],
                mouse_enabled=True,
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
            if choice.value == "redraw":
                index = choose_zone("Redraw Zone", floor_indices)
                if index is None:
                    continue
                zone = current_zones[index]
                rect = self.custom_building_rect_selector(
                    f"Redraw {BUILDING_TEMPLATE_ZONE_LABELS.get(str(zone.get('kind')), str(zone.get('kind')))} Zone",
                    rows,
                    initial_rect=(
                        int(zone.get("x1", 0)),
                        int(zone.get("y1", 0)),
                        int(zone.get("x2", 0)),
                        int(zone.get("y2", 0)),
                    ),
                )
                if rect is not None:
                    current_zones[index].update(rect)
            elif choice.value == "kind":
                index = choose_zone("Change Zone Function", list(range(len(current_zones))))
                if index is None:
                    continue
                zone = current_zones[index]
                new_kind = self.custom_choice_menu(
                    "Zone Function",
                    BUILDING_TEMPLATE_ZONE_KINDS,
                    str(zone.get("kind", "bedroom")),
                    labels=BUILDING_TEMPLATE_ZONE_LABELS,
                )
                if new_kind is not None:
                    current_zones[index]["kind"] = new_kind
            elif choice.value == "delete":
                index = choose_zone("Delete Zone", list(range(len(current_zones))))
                if index is None:
                    continue
                del current_zones[index]
            elif choice.value == "delete_floor":
                confirm = menu_select(
                    "Delete Floor Zones",
                    [
                        MenuItem(label="Delete all zones on this floor", value="delete", enabled=True),
                        MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
                    ],
                    footer="This only removes schedule zones; it does not erase the map or furniture.",
                    mouse_enabled=True,
                )
                if confirm is not None and confirm.value == "delete":
                    current_zones = [
                        zone
                        for zone in current_zones
                        if int(zone.get("floor", 0) or 0) != int(floor_index)
                    ]

    def custom_building_fixture_brushes(self) -> List[tuple]:
        brushes = [
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
            ("Kitchen", "k", "kitchen fixture"),
            ("Pantry/Medicine", "m", "contextual supplies"),
            ("Notice", "n", "posted notice"),
            ("Rug/Records", "r", "contextual rug or records"),
            ("Wardrobe/Utility", "u", "contextual household fixture"),
            ("Produce Display", "v", "market produce"),
            ("Examination Fixture", "e", "clinic examination equipment"),
            ("Animal Fixture", "h", "animal-store fixture"),
            ("Forge", "q", "smithing or quenching fixture"),
            ("Ore Storage", "o", "smithing material storage"),
            ("Large Bed", "B", "authored bedroom fixture"),
            ("Display A", "A", "contextual authored display"),
            ("Display C", "C", "contextual authored display"),
            ("Display E", "E", "contextual authored display"),
            ("Display F", "F", "contextual authored display"),
            ("Display G", "G", "contextual authored display"),
            ("Lamp", "L", "interior lamp"),
            ("Display M", "M", "contextual authored display"),
            ("Display S", "S", "contextual authored display"),
            ("Large Table", "T", "authored table fixture"),
            ("Catalog/Notice", "!", "catalog or warning fixture"),
            ("Blackjack Table", "1", "playable game table"),
            ("Hold'em Table", "2", "playable game table"),
            ("Hearts Table", "3", "playable game table"),
            ("Solitaire Table", "4", "playable game table"),
            ("Checkers Table", "5", "playable game table"),
            ("Chess Table", "6", "playable game table"),
            ("Mancala Board", "7", "playable game table"),
            ("Royal Game of Ur", "8", "playable game table"),
            ("Rug", ",", "soft decoration"),
            ("Erase to Blank", " ", "remove the tile completely, leaving empty space"),
        ]
        brushes.extend(
            (
                str(record["name"]),
                str(symbol),
                str(record["hint"]),
            )
            for symbol, record in BUILDING_TEMPLATE_FURNISHING_DATA.items()
        )
        return brushes

    def custom_building_fixture_brush_groups(self) -> List[tuple]:
        brushes = self.custom_building_fixture_brushes()
        by_symbol = {str(symbol): (label, str(symbol), hint) for label, symbol, hint in brushes}
        groups = [
            ("Architecture", (".", "#", "-", "|", "_", "D", "<", ">")),
            ("Services & Work", ("&", "$", "+", "w", "a", "x", "P", "d", "f", "k", "m", "n", "e", "h", "q", "o", "v")),
            ("Beds", ("b", "B", "I", "J", "K")),
            ("Tables & Seating", ("t", "T", "c", "C", "O", "Q", "R")),
            ("Storage & Containers", ("s", "u", "j", "g", "W", "y", "z", "N", "X", "Y", "Z")),
            ("Books & Displays", ("l", "L", "H", "i", "V", "p", ",", "r", "!")),
            ("Displays", ("A", "E", "F", "G", "M", "S")),
            ("Game Tables", ("1", "2", "3", "4", "5", "6", "7", "8")),
            ("Erase", (" ",)),
        ]
        return [
            (group_name, [by_symbol[symbol] for symbol in symbols if symbol in by_symbol])
            for group_name, symbols in groups
        ]

    def custom_building_fixture_palette(self, current_brush: str) -> Optional[str]:
        groups = self.custom_building_fixture_brush_groups()
        current_group = next(
            (
                group_name
                for group_name, brushes in groups
                if any(str(symbol) == str(current_brush) for _label, symbol, _hint in brushes)
            ),
            "",
        )
        group_choice = menu_select(
            "Fixture Categories",
            [
                MenuItem(
                    label=group_name,
                    value=group_name,
                    enabled=True,
                    hint=f"{len(brushes)} brushes{' | current' if group_name == current_group else ''}",
                )
                for group_name, brushes in groups
            ] + [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
            footer="Choose a compact fixture category.",
            mouse_enabled=True,
        )
        if group_choice is None or group_choice.value == MENU_BACK:
            return None
        brushes = next(
            brushes
            for group_name, brushes in groups
            if group_name == str(group_choice.value)
        )
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
        choice = menu_select(
            "Fixture Brush",
            items,
            footer="Choose what Z/Enter or left-drag paints on the template.",
            mouse_enabled=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return None
        return str(choice.value)

    @staticmethod
    def custom_building_flood_points(
        rows: Sequence[str],
        start_x: int,
        start_y: int,
    ) -> List[tuple]:
        """Return the connected four-way region matching the selected tile."""
        if not (
            0 <= int(start_y) < len(rows)
            and 0 <= int(start_x) < len(str(rows[int(start_y)]))
        ):
            return []
        start_x, start_y = int(start_x), int(start_y)
        target = str(rows[start_y])[start_x]
        pending = [(start_x, start_y)]
        seen = set()
        points: List[tuple] = []
        while pending:
            x, y = pending.pop()
            if (x, y) in seen:
                continue
            seen.add((x, y))
            if not (
                0 <= y < len(rows)
                and 0 <= x < len(str(rows[y]))
                and str(rows[y])[x] == target
            ):
                continue
            points.append((x, y))
            pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
        return points

    @staticmethod
    def custom_building_extract_clipboard(
        rows: Sequence[str],
        rect: Dict[str, int],
    ) -> List[str]:
        x1, x2 = sorted((int(rect["x1"]), int(rect["x2"])))
        y1, y2 = sorted((int(rect["y1"]), int(rect["y2"])))
        return [
            str(rows[y]).ljust(BUILDING_TEMPLATE_WIDTH)[x1:x2 + 1]
            for y in range(max(0, y1), min(len(rows), y2 + 1))
        ]

    @staticmethod
    def custom_building_transform_clipboard(
        clipboard: Sequence[str],
        transform: str,
    ) -> List[str]:
        rows = [str(row) for row in clipboard]
        if not rows:
            return []
        width = max(len(row) for row in rows)
        grid = [list(row.ljust(width)) for row in rows]
        if transform == "horizontal":
            return ["".join(reversed(row)) for row in grid]
        if transform == "vertical":
            return ["".join(row) for row in reversed(grid)]
        if transform == "clockwise":
            return [
                "".join(grid[y][x] for y in range(len(grid) - 1, -1, -1))
                for x in range(width)
            ]
        return ["".join(row) for row in grid]

    @staticmethod
    def custom_building_paste_clipboard(
        rows: Sequence[str],
        clipboard: Sequence[str],
        start_x: int,
        start_y: int,
        *,
        transparent: bool = False,
    ) -> List[str]:
        grid = [
            list(str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH])
            for row in rows[:BUILDING_TEMPLATE_HEIGHT]
        ]
        while len(grid) < BUILDING_TEMPLATE_HEIGHT:
            grid.append([" " for _ in range(BUILDING_TEMPLATE_WIDTH)])
        for local_y, clipboard_row in enumerate(clipboard):
            y = int(start_y) + local_y
            if not 0 <= y < BUILDING_TEMPLATE_HEIGHT:
                continue
            for local_x, tile in enumerate(str(clipboard_row)):
                x = int(start_x) + local_x
                if not 0 <= x < BUILDING_TEMPLATE_WIDTH:
                    continue
                if transparent and tile == " ":
                    continue
                grid[y][x] = tile
        return ["".join(row) for row in grid]

    @staticmethod
    def custom_building_clipboard_preview(
        rows: Sequence[str],
        clipboard: Sequence[str],
        start_x: int,
        start_y: int,
        *,
        transparent: bool = False,
    ) -> Dict[str, object]:
        tiles: Dict[tuple, tuple] = {}
        clipped = 0
        overwritten = 0
        for local_y, clipboard_row in enumerate(clipboard):
            for local_x, tile in enumerate(str(clipboard_row)):
                if transparent and tile == " ":
                    continue
                x, y = int(start_x) + local_x, int(start_y) + local_y
                if not (
                    0 <= x < BUILDING_TEMPLATE_WIDTH
                    and 0 <= y < BUILDING_TEMPLATE_HEIGHT
                ):
                    clipped += 1
                    continue
                source_row = str(rows[y]) if y < len(rows) else ""
                existing = source_row[x] if x < len(source_row) else " "
                overwrites = existing not in {" ", "."} and existing != tile
                if overwrites:
                    overwritten += 1
                tiles[(x, y)] = (
                    tile if tile != " " else "\u00b7",
                    overwrites,
                )
        return {
            "tiles": tiles,
            "clipped": clipped,
            "overwritten": overwritten,
            "width": max((len(str(row)) for row in clipboard), default=0),
            "height": len(clipboard),
        }

    def custom_building_clipboard_placement_selector(
        self,
        title: str,
        rows: Sequence[str],
        clipboard: Sequence[str],
        *,
        transparent: bool = False,
        initial_point: Optional[tuple] = None,
    ) -> Optional[Dict[str, int]]:
        if not clipboard:
            return None
        if initial_point is None:
            cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT // 2
        else:
            cursor_x = max(0, min(BUILDING_TEMPLATE_WIDTH - 1, int(initial_point[0])))
            cursor_y = max(0, min(BUILDING_TEMPLATE_HEIGHT - 1, int(initial_point[1])))
        while True:
            preview = self.custom_building_clipboard_preview(
                rows,
                clipboard,
                cursor_x,
                cursor_y,
                transparent=transparent,
            )
            warnings = []
            if int(preview["clipped"]):
                warnings.append(f"{preview['clipped']} clipped")
            if int(preview["overwritten"]):
                warnings.append(f"{preview['overwritten']} overwrite")
            status = ", ".join(warnings) if warnings else "clear placement"
            self.draw_custom_building_template_canvas(
                title,
                rows,
                cursor_x,
                cursor_y,
                preview_tiles=preview["tiles"],
                footer=(
                    f"Preview: {preview['width']}x{preview['height']} | {status}\n"
                    "Left-click/Z place | Right-click/B/Q/Esc/Tab cancel | WASD/Arrows move"
                ),
            )
            event = read_key_or_mouse()
            if event.get("kind") == "mouse":
                if bool(event.get("right", False)):
                    return None
                point = self.custom_building_mouse_canvas_point(event)
                if point is not None:
                    cursor_x, cursor_y = point
                    if bool(event.get("left", False)):
                        return {"x": cursor_x, "y": cursor_y}
                continue
            key = normalize_key(str(event.get("key", "")))
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

    @staticmethod
    def custom_building_room_shell(
        rows: Sequence[str],
        rect: Dict[str, int],
    ) -> List[str]:
        grid = [
            list(str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH])
            for row in rows[:BUILDING_TEMPLATE_HEIGHT]
        ]
        while len(grid) < BUILDING_TEMPLATE_HEIGHT:
            grid.append([" " for _ in range(BUILDING_TEMPLATE_WIDTH)])
        x1, x2 = sorted((int(rect["x1"]), int(rect["x2"])))
        y1, y2 = sorted((int(rect["y1"]), int(rect["y2"])))
        for y in range(max(0, y1), min(BUILDING_TEMPLATE_HEIGHT - 1, y2) + 1):
            for x in range(max(0, x1), min(BUILDING_TEMPLATE_WIDTH - 1, x2) + 1):
                grid[y][x] = "#" if x in {x1, x2} or y in {y1, y2} else "."
        return ["".join(row) for row in grid]

    @staticmethod
    def custom_building_move_selection(
        rows: Sequence[str],
        rect: Dict[str, int],
        destination_x: int,
        destination_y: int,
    ) -> List[str]:
        clipboard = CustomContentMenuMixin.custom_building_extract_clipboard(rows, rect)
        grid = [
            list(str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH])
            for row in rows[:BUILDING_TEMPLATE_HEIGHT]
        ]
        while len(grid) < BUILDING_TEMPLATE_HEIGHT:
            grid.append([" " for _ in range(BUILDING_TEMPLATE_WIDTH)])
        x1, x2 = sorted((int(rect["x1"]), int(rect["x2"])))
        y1, y2 = sorted((int(rect["y1"]), int(rect["y2"])))
        for y in range(max(0, y1), min(BUILDING_TEMPLATE_HEIGHT - 1, y2) + 1):
            for x in range(max(0, x1), min(BUILDING_TEMPLATE_WIDTH - 1, x2) + 1):
                grid[y][x] = " "
        return CustomContentMenuMixin.custom_building_paste_clipboard(
            ["".join(row) for row in grid],
            clipboard,
            int(destination_x),
            int(destination_y),
        )

    @staticmethod
    def custom_building_room_kits() -> List[Dict[str, object]]:
        return [
            {
                "name": "Simple Bedroom",
                "zone": "bedroom",
                "hint": "bed, wardrobe, lamp, and a small table",
                "rows": [
                    "#########",
                    "#I....YN#",
                    "#.......#",
                    "#..t.cL.#",
                    "#.......#",
                    "####_####",
                ],
            },
            {
                "name": "Inn Guest Room",
                "zone": "bedroom",
                "hint": "one bed per private inn room",
                "rows": [
                    "#######",
                    "#b...N#",
                    "#.....#",
                    "#.t.c.#",
                    "###_###",
                ],
            },
            {
                "name": "Kitchen and Dining",
                "zone": "kitchen",
                "hint": "one compact kitchen with pantry and dining space",
                "rows": [
                    "###########",
                    "#k.W.Z..f.#",
                    "#.........#",
                    "#..c.t.c..#",
                    "#.........#",
                    "#####_#####",
                ],
            },
            {
                "name": "Shop Counter Room",
                "zone": "shopping_counter",
                "hint": "stock wall, continuous counter, and an open service lane",
                "rows": [
                    "#############",
                    "#VVV.zz.....#",
                    "#...........#",
                    "#&&&&&&&....#",
                    "#...........#",
                    "######_######",
                ],
            },
            {
                "name": "Office",
                "zone": "office",
                "hint": "desk, records, chair, and visitor table",
                "rows": [
                    "#########",
                    "#d.P...g#",
                    "#.c.....#",
                    "#...t.c.#",
                    "#.......#",
                    "####_####",
                ],
            },
            {
                "name": "Library Reading Room",
                "zone": "library_stacks",
                "hint": "bookcases around a clear reading area",
                "rows": [
                    "###########",
                    "#HHH...iii#",
                    "#.........#",
                    "#.c.t.t.c.#",
                    "#.........#",
                    "#####_#####",
                ],
            },
            {
                "name": "Empty Hallway Segment",
                "zone": "",
                "hint": "clear three-wide circulation lane with doors at both ends",
                "rows": [
                    "###_###",
                    "#.....#",
                    "#.....#",
                    "#.....#",
                    "###_###",
                ],
            },
            {
                "name": "Bedroom Suite Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "bedroom",
                "hint": "double bed, dresser, nightstand, seating, and table",
                "rows": [
                    "I.....YN.",
                    ".........",
                    ".R..t..Q.",
                    ".........",
                ],
            },
            {
                "name": "Bunk Room Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "bedroom",
                "hint": "two bunk beds with separate nightstands and benches",
                "rows": [
                    "J.N...J.N",
                    ".........",
                    ".O..t..O.",
                    ".........",
                ],
            },
            {
                "name": "Reading Nook Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "library_stacks",
                "hint": "mixed bookcases, armchair, table, and lamp",
                "rows": [
                    "HHi....",
                    ".......",
                    ".R.t.L.",
                    ".......",
                ],
            },
            {
                "name": "Living Room Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "public_hall",
                "hint": "sofa, armchair, side table, and chair",
                "rows": [
                    "Q.......R",
                    ".........",
                    "...t.c...",
                    ".........",
                ],
            },
            {
                "name": "Dining Set Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "dining",
                "hint": "shared benches, dining table, and chairs",
                "rows": [
                    "..O...O..",
                    ".........",
                    ".c..T..c.",
                    ".c.....c.",
                    ".........",
                ],
            },
            {
                "name": "Storage Wall Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "storage",
                "hint": "ten distinct book and storage fixtures",
                "rows": [
                    "HigWjyzXYZ",
                    "..........",
                ],
            },
            {
                "name": "Clinic Bay Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "clinic_ward",
                "hint": "cot, medical storage, waiting chair, and cabinet",
                "rows": [
                    "K..+..W..",
                    ".........",
                    ".c...g...",
                ],
            },
            {
                "name": "Shop Display Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "shopping_counter",
                "hint": "display cases, crates, and a staffed counter",
                "rows": [
                    "VVV...zz...",
                    "...........",
                    "&&&&&&.....",
                    "...........",
                ],
            },
            {
                "name": "Workshop Storage Arrangement",
                "group": "Furnishing Arrangements",
                "zone": "workshop",
                "hint": "tools, workbenches, cabinet, crates, barrel, and chest",
                "rows": [
                    "a.w.x.W..",
                    ".........",
                    "z..X..y..",
                ],
            },
        ]

    def custom_building_room_kit_palette(self) -> Optional[List[str]]:
        kits = self.custom_building_room_kits()
        items: List[MenuItem] = []
        groups = ("Complete Rooms", "Furnishing Arrangements")
        for group in groups:
            items.append(MenuItem(
                label=f"-- {group} --",
                value=f"group:{group}",
                enabled=False,
            ))
            items.extend(
                MenuItem(
                    label=str(kit["name"]),
                    value=index,
                    enabled=True,
                    hint=f"{len(kit['rows'][0])}x{len(kit['rows'])} | {kit['hint']}",
                )
                for index, kit in enumerate(kits)
                if str(kit.get("group", "Complete Rooms")) == group
            )
        choice = menu_select(
            "Room and Furnishing Kit Library",
            items + [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
            footer="The selected room is loaded into the clipboard. Use V to place it, or transform it first.",
            mouse_enabled=True,
        )
        if choice is None or choice.value == MENU_BACK:
            return None
        try:
            return [str(row) for row in kits[int(choice.value)]["rows"]]
        except (IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def custom_building_floor_zone_overlay(
        zones: Sequence[Dict[str, object]],
        floor_index: int,
    ) -> Dict[tuple, str]:
        overlay: Dict[tuple, str] = {}
        for zone in zones:
            if not isinstance(zone, dict) or int(zone.get("floor", 0) or 0) != int(floor_index):
                continue
            x1, x2 = sorted((int(zone.get("x1", 0)), int(zone.get("x2", 0))))
            y1, y2 = sorted((int(zone.get("y1", 0)), int(zone.get("y2", 0))))
            label = BUILDING_TEMPLATE_ZONE_LABELS.get(
                str(zone.get("kind", "")),
                str(zone.get("kind", "Zone")),
            )
            marker = str(label).strip()[:1].upper() or "Z"
            for y in range(max(0, y1), min(BUILDING_TEMPLATE_HEIGHT - 1, y2) + 1):
                for x in range(max(0, x1), min(BUILDING_TEMPLATE_WIDTH - 1, x2) + 1):
                    if x not in {x1, x2} and y not in {y1, y2}:
                        continue
                    overlay[(x, y)] = marker if (x, y) not in overlay else "+"
        return overlay

    @staticmethod
    def custom_building_smart_door(
        rows: Sequence[str],
        x: int,
        y: int,
        *,
        exterior: bool = False,
    ) -> tuple:
        grid = [
            list(str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH])
            for row in rows[:BUILDING_TEMPLATE_HEIGHT]
        ]
        while len(grid) < BUILDING_TEMPLATE_HEIGHT:
            grid.append([" " for _ in range(BUILDING_TEMPLATE_WIDTH)])
        x, y = int(x), int(y)
        if not (0 <= x < BUILDING_TEMPLATE_WIDTH and 0 <= y < BUILDING_TEMPLATE_HEIGHT):
            return ["".join(row) for row in grid], False
        if grid[y][x] not in {"#", "-", "|", "_", "D"}:
            return ["".join(row) for row in grid], False
        if exterior:
            grid[y][x] = "D"
            return ["".join(row) for row in grid], True
        horizontal_access = (
            0 < x < BUILDING_TEMPLATE_WIDTH - 1
            and grid[y][x - 1] in {".", ","}
            and grid[y][x + 1] in {".", ","}
        )
        vertical_access = (
            0 < y < BUILDING_TEMPLATE_HEIGHT - 1
            and grid[y - 1][x] in {".", ","}
            and grid[y + 1][x] in {".", ","}
        )
        if not horizontal_access and not vertical_access:
            return ["".join(row) for row in grid], False
        grid[y][x] = "|" if horizontal_access and not vertical_access else "_"
        return ["".join(row) for row in grid], True

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
        read_key_or_mouse()

    def custom_building_fixture_editor(
        self,
        rows: Sequence[str],
        floor_index: int = 0,
        *,
        zones: Sequence[Dict[str, object]] = (),
        spawns: Sequence[Dict[str, object]] = (),
        colors: Sequence[Dict[str, object]] = (),
    ) -> List[str]:
        grid = [list(str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH]) for row in rows]
        while len(grid) < BUILDING_TEMPLATE_HEIGHT:
            grid.append([" " for _ in range(BUILDING_TEMPLATE_WIDTH)])
        cursor_x, cursor_y = BUILDING_TEMPLATE_WIDTH // 2, BUILDING_TEMPLATE_HEIGHT // 2
        brush = "."
        mouse_left_down = False
        mouse_right_down = False
        last_mouse_point: Optional[tuple] = None
        undo_stack: List[List[str]] = []
        redo_stack: List[List[str]] = []
        clipboard: List[str] = []
        transparent_paste = False
        metadata_overlay = True

        def snapshot() -> List[str]:
            return ["".join(row) for row in grid]

        def remember_change() -> None:
            current = snapshot()
            if not undo_stack or undo_stack[-1] != current:
                undo_stack.append(current)
                if len(undo_stack) > 50:
                    del undo_stack[0]
            redo_stack.clear()

        while True:
            brush_data = {
                str(symbol): (str(label), str(hint))
                for label, symbol, hint in self.custom_building_fixture_brushes()
            }
            brush_label = brush_data.get(brush, ("Unknown tile", ""))[0]
            clipboard_label = (
                f"{max((len(row) for row in clipboard), default=0)}x{len(clipboard)}"
                if clipboard
                else "empty"
            )
            self.draw_custom_building_template_canvas(
                f"Building Map Canvas - Floor {floor_index + 1}",
                ["".join(row) for row in grid],
                cursor_x,
                cursor_y,
                color_overlays=(
                    self.custom_building_floor_color_map(colors, floor_index)
                    if metadata_overlay
                    else None
                ),
                spawn_points=(
                    self.custom_building_floor_spawn_points(spawns, floor_index)
                    if metadata_overlay
                    else None
                ),
                zone_overlays=(
                    self.custom_building_floor_zone_overlay(zones, floor_index)
                    if metadata_overlay
                    else None
                ),
                footer=(
                    f"Brush: {brush if brush != ' ' else 'space'} ({brush_label}) | "
                    "Left-drag draw | Right-drag erase to blank | Wheel change brush\n"
                    "P choose tile | Middle-click/G pick tile | U/Y undo/redo | "
                    f"Overlay: {'on' if metadata_overlay else 'off'} | Clipboard: {clipboard_label}\n"
                    "? all tools | B/Q/Esc/Tab return to template menu"
                ),
            )
            event = read_key_or_mouse()
            if event.get("kind") == "mouse":
                wheel = int(event.get("wheel", 0) or 0)
                if wheel:
                    symbols = [str(symbol) for _label, symbol, _hint in self.custom_building_fixture_brushes()]
                    brush_index = symbols.index(brush) if brush in symbols else 0
                    brush = symbols[(brush_index - wheel) % len(symbols)]
                    mouse_left_down = False
                    mouse_right_down = False
                    last_mouse_point = None
                    continue
                point = self.custom_building_mouse_canvas_point(event)
                raw_left = bool(event.get("left", False))
                raw_right = bool(event.get("right", False))
                moved = bool(event.get("moved", False))
                left = raw_left and (mouse_left_down or not moved)
                right = raw_right and (mouse_right_down or not moved)
                middle = bool(int(event.get("buttons", 0) or 0) & 0x0004)
                if point is not None and middle:
                    cursor_x, cursor_y = point
                    brush = grid[cursor_y][cursor_x]
                    mouse_left_down = False
                    mouse_right_down = False
                    last_mouse_point = None
                    continue
                if point is not None and (left or right):
                    cursor_x, cursor_y = point
                    same_stroke = (
                        (left and mouse_left_down)
                        or (right and mouse_right_down)
                    )
                    if not same_stroke:
                        remember_change()
                    start = last_mouse_point if same_stroke and last_mouse_point is not None else point
                    paint_tile = brush if left else " "
                    for paint_x, paint_y in self.custom_building_line_points(start, point):
                        grid[paint_y][paint_x] = paint_tile
                    last_mouse_point = point
                elif not raw_left and not raw_right:
                    last_mouse_point = None
                mouse_left_down = left
                mouse_right_down = right
                continue
            key = normalize_key(str(event.get("key", "")))
            key = key.lower() if len(key) == 1 and key.isalpha() else key
            if key in ["q", "b", "\t", "\x1b"]:
                return ["".join(row) for row in grid]
            if key == "?":
                menu_select(
                    "Map Canvas Controls",
                    [MenuItem(label="Return to canvas", value=MENU_BACK, enabled=True)],
                    extra_lines=[
                        "BASIC DRAWING",
                        "Left-drag or Z: draw with the current tile",
                        "Right-drag: erase completely to blank space",
                        "Mouse wheel: change tile",
                        "P: open the categorized tile palette",
                        "Middle-click or G: pick the tile under the cursor",
                        "WASD/arrows: move the cursor",
                        "U / Y: undo / redo",
                        "",
                        "ROOMS AND SHAPES",
                        "O: draw an empty room shell",
                        "F: flood fill",
                        "L: draw a straight line",
                        "R: draw a filled rectangle",
                        "K: replace every matching tile",
                        "[: place a correctly oriented room door",
                        "]: place the ground-floor exterior exit",
                        "",
                        "SELECTIONS",
                        "C / X: copy / cut a rectangle",
                        "M: move a rectangle",
                        "V: paste with a placement preview",
                        "E: choose a room or furnishing kit",
                        "H / J / T: mirror horizontal / mirror vertical / rotate clipboard",
                        "N: toggle transparent paste",
                        "",
                        "INFORMATION",
                        "I: inspect the current tile",
                        "9: show or hide zones, NPC positions, and paint",
                        "Q / Esc: return to the template menu",
                    ],
                    footer="The canvas is edited freely; saving happens from the template menu.",
                    mouse_enabled=True,
                )
                continue
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
            if key == "u":
                if undo_stack:
                    redo_stack.append(snapshot())
                    grid = [list(row) for row in undo_stack.pop()]
                continue
            if key == "y":
                if redo_stack:
                    undo_stack.append(snapshot())
                    grid = [list(row) for row in redo_stack.pop()]
                continue
            if key == "g":
                brush = grid[cursor_y][cursor_x]
                continue
            if key == "e":
                selected_kit = self.custom_building_room_kit_palette()
                if selected_kit is not None:
                    clipboard = selected_kit
                continue
            if key == "9":
                metadata_overlay = not metadata_overlay
                continue
            if key in {"c", "x"}:
                rect = self.custom_building_rect_selector(
                    "Copy Area" if key == "c" else "Cut Area",
                    snapshot(),
                )
                if rect is None:
                    continue
                clipboard = self.custom_building_extract_clipboard(snapshot(), rect)
                if key == "x":
                    remember_change()
                    for edit_y in range(int(rect["y1"]), int(rect["y2"]) + 1):
                        for edit_x in range(int(rect["x1"]), int(rect["x2"]) + 1):
                            grid[edit_y][edit_x] = " "
                cursor_x, cursor_y = int(rect["x1"]), int(rect["y1"])
                continue
            if key == "m":
                rect = self.custom_building_rect_selector(
                    "Select Area to Move",
                    snapshot(),
                )
                if rect is None:
                    continue
                clipboard = self.custom_building_extract_clipboard(snapshot(), rect)
                move_preview_grid = [list(row) for row in snapshot()]
                for preview_y in range(int(rect["y1"]), int(rect["y2"]) + 1):
                    for preview_x in range(int(rect["x1"]), int(rect["x2"]) + 1):
                        move_preview_grid[preview_y][preview_x] = " "
                destination = self.custom_building_clipboard_placement_selector(
                    "Move Selection - Choose New Top-Left Corner",
                    ["".join(row) for row in move_preview_grid],
                    clipboard,
                    initial_point=(int(rect["x1"]), int(rect["y1"])),
                )
                if destination is not None:
                    remember_change()
                    moved = self.custom_building_move_selection(
                        snapshot(),
                        rect,
                        int(destination["x"]),
                        int(destination["y"]),
                    )
                    grid = [list(row) for row in moved]
                    cursor_x, cursor_y = int(destination["x"]), int(destination["y"])
                continue
            if key == "v":
                if clipboard:
                    destination = self.custom_building_clipboard_placement_selector(
                        "Place Clipboard",
                        snapshot(),
                        clipboard,
                        transparent=transparent_paste,
                        initial_point=(cursor_x, cursor_y),
                    )
                    if destination is not None:
                        remember_change()
                        pasted = self.custom_building_paste_clipboard(
                            snapshot(),
                            clipboard,
                            int(destination["x"]),
                            int(destination["y"]),
                            transparent=transparent_paste,
                        )
                        grid = [list(row) for row in pasted]
                        cursor_x, cursor_y = int(destination["x"]), int(destination["y"])
                continue
            if key == "h":
                clipboard = self.custom_building_transform_clipboard(
                    clipboard,
                    "horizontal",
                )
                continue
            if key == "j":
                clipboard = self.custom_building_transform_clipboard(
                    clipboard,
                    "vertical",
                )
                continue
            if key == "t":
                clipboard = self.custom_building_transform_clipboard(
                    clipboard,
                    "clockwise",
                )
                continue
            if key == "n":
                transparent_paste = not transparent_paste
                continue
            if key in {"[", "]"}:
                if key == "]" and floor_index != 0:
                    continue
                door_rows, door_placed = self.custom_building_smart_door(
                    snapshot(),
                    cursor_x,
                    cursor_y,
                    exterior=key == "]",
                )
                if door_placed:
                    remember_change()
                    grid = [list(row) for row in door_rows]
                continue
            if key == "o":
                rect = self.custom_building_rect_selector(
                    "Draw Room Shell",
                    snapshot(),
                )
                if rect is not None:
                    remember_change()
                    grid = [
                        list(row)
                        for row in self.custom_building_room_shell(snapshot(), rect)
                    ]
                    cursor_x, cursor_y = int(rect["x2"]), int(rect["y2"])
                continue
            if key == "k":
                target = grid[cursor_y][cursor_x]
                replace_count = sum(row.count(target) for row in grid)
                if target == brush or replace_count <= 0:
                    continue
                replace_choice = menu_select(
                    "Replace Tiles",
                    [
                        MenuItem(
                            label=f"Replace {replace_count} '{target if target != ' ' else 'space'}' tiles",
                            value="replace",
                            enabled=True,
                            hint=f"with '{brush if brush != ' ' else 'space'}'",
                        ),
                        MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
                    ],
                    footer="Undo remains available after replacement.",
                    mouse_enabled=True,
                )
                if replace_choice is not None and replace_choice.value == "replace":
                    remember_change()
                    for edit_y, row in enumerate(grid):
                        for edit_x, tile in enumerate(row):
                            if tile == target:
                                grid[edit_y][edit_x] = brush
                continue
            if key == "f":
                points = self.custom_building_flood_points(
                    snapshot(),
                    cursor_x,
                    cursor_y,
                )
                if points and any(grid[y][x] != brush for x, y in points):
                    remember_change()
                    for paint_x, paint_y in points:
                        grid[paint_y][paint_x] = brush
                continue
            if key == "l":
                first = self.custom_building_point_selector(
                    "Line Start",
                    snapshot(),
                    footer="Left-click/Z select line start | B/Q/Esc/Tab cancel",
                    initial_point=(cursor_x, cursor_y),
                )
                if first is None:
                    continue
                second = self.custom_building_point_selector(
                    "Line End",
                    snapshot(),
                    footer="Left-click/Z select line end | B/Q/Esc/Tab cancel",
                    initial_point=(int(first["x"]), int(first["y"])),
                )
                if second is None:
                    continue
                remember_change()
                for paint_x, paint_y in self.custom_building_line_points(
                    (int(first["x"]), int(first["y"])),
                    (int(second["x"]), int(second["y"])),
                ):
                    grid[paint_y][paint_x] = brush
                cursor_x, cursor_y = int(second["x"]), int(second["y"])
                continue
            if key == "r":
                rect = self.custom_building_rect_selector(
                    "Filled Fixture Rectangle",
                    snapshot(),
                )
                if rect is None:
                    continue
                remember_change()
                for paint_y in range(int(rect["y1"]), int(rect["y2"]) + 1):
                    for paint_x in range(int(rect["x1"]), int(rect["x2"]) + 1):
                        grid[paint_y][paint_x] = brush
                cursor_x, cursor_y = int(rect["x2"]), int(rect["y2"])
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
                remember_change()
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
        choice = menu_select(
            "Paint Color",
            items,
            footer="Default removes custom color from the tile.",
            mouse_enabled=True,
        )
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
        mouse_left_down = False
        mouse_right_down = False
        last_mouse_point: Optional[tuple] = None
        undo_stack: List[List[Dict[str, object]]] = []
        redo_stack: List[List[Dict[str, object]]] = []

        def paint_snapshot() -> List[Dict[str, object]]:
            return [dict(record) for record in painted]

        def remember_paint_change() -> None:
            current = paint_snapshot()
            if not undo_stack or undo_stack[-1] != current:
                undo_stack.append(current)
                if len(undo_stack) > 50:
                    del undo_stack[0]
            redo_stack.clear()

        while True:
            color_map = self.custom_building_floor_color_map(painted, floor_index)
            brush_label = BUILDING_TEMPLATE_COLOR_LABELS.get(brush, brush.title())
            self.draw_custom_building_template_canvas(
                f"Paint Tile Colors - Floor {floor_index + 1}",
                rows,
                cursor_x,
                cursor_y,
                footer=(
                    f"Color: {brush_label} | Left-drag paint | Right-drag erase | Wheel color | "
                    "WASD move | Z paint | E erase | P palette | G pick | U/Y undo/redo\n"
                    "F fill region | L line | R filled rectangle | B/Q/Esc/Tab done"
                ),
                color_overlays=color_map,
            )
            event = read_key_or_mouse()
            if event.get("kind") == "mouse":
                wheel = int(event.get("wheel", 0) or 0)
                if wheel:
                    color_keys = list(BUILDING_TEMPLATE_COLOR_KEYS)
                    color_index = color_keys.index(brush) if brush in color_keys else 0
                    brush = color_keys[(color_index - wheel) % len(color_keys)]
                    mouse_left_down = False
                    mouse_right_down = False
                    last_mouse_point = None
                    continue
                point = self.custom_building_mouse_canvas_point(event)
                raw_left = bool(event.get("left", False))
                raw_right = bool(event.get("right", False))
                moved = bool(event.get("moved", False))
                left = raw_left and (mouse_left_down or not moved)
                right = raw_right and (mouse_right_down or not moved)
                middle = bool(int(event.get("buttons", 0) or 0) & 0x0004)
                if point is not None and middle:
                    cursor_x, cursor_y = point
                    brush = color_map.get(point, "default")
                    mouse_left_down = False
                    mouse_right_down = False
                    last_mouse_point = None
                    continue
                if point is not None and (left or right):
                    cursor_x, cursor_y = point
                    same_stroke = (
                        (left and mouse_left_down)
                        or (right and mouse_right_down)
                    )
                    if not same_stroke:
                        remember_paint_change()
                    start = last_mouse_point if same_stroke and last_mouse_point is not None else point
                    color_key = brush if left else "default"
                    for paint_x, paint_y in self.custom_building_line_points(start, point):
                        painted = self.set_custom_building_color_mark(
                            painted,
                            floor_index,
                            paint_x,
                            paint_y,
                            color_key,
                        )
                    last_mouse_point = point
                elif not raw_left and not raw_right:
                    last_mouse_point = None
                mouse_left_down = left
                mouse_right_down = right
                continue
            key = normalize_key(str(event.get("key", "")))
            key = key.lower() if len(key) == 1 and key.isalpha() else key
            if key in ["q", "b", "\t", "\x1b"]:
                return painted
            if key == "p":
                selected = self.custom_building_color_palette(brush)
                if selected is not None:
                    brush = selected
                continue
            if key == "e":
                remember_paint_change()
                painted = self.set_custom_building_color_mark(
                    painted,
                    floor_index,
                    cursor_x,
                    cursor_y,
                    "default",
                )
                continue
            if key == "u":
                if undo_stack:
                    redo_stack.append(paint_snapshot())
                    painted = [dict(record) for record in undo_stack.pop()]
                continue
            if key == "y":
                if redo_stack:
                    undo_stack.append(paint_snapshot())
                    painted = [dict(record) for record in redo_stack.pop()]
                continue
            if key == "g":
                brush = self.custom_building_floor_color_map(
                    painted,
                    floor_index,
                ).get((cursor_x, cursor_y), "default")
                continue
            if key == "f":
                points = self.custom_building_flood_points(rows, cursor_x, cursor_y)
                if points:
                    remember_paint_change()
                    for paint_x, paint_y in points:
                        painted = self.set_custom_building_color_mark(
                            painted,
                            floor_index,
                            paint_x,
                            paint_y,
                            brush,
                        )
                continue
            if key == "l":
                overlays = self.custom_building_floor_color_map(painted, floor_index)
                first = self.custom_building_point_selector(
                    "Color Line Start",
                    rows,
                    footer="Left-click/Z select line start | B/Q/Esc/Tab cancel",
                    color_overlays=overlays,
                    initial_point=(cursor_x, cursor_y),
                )
                if first is None:
                    continue
                second = self.custom_building_point_selector(
                    "Color Line End",
                    rows,
                    footer="Left-click/Z select line end | B/Q/Esc/Tab cancel",
                    color_overlays=overlays,
                    initial_point=(int(first["x"]), int(first["y"])),
                )
                if second is None:
                    continue
                remember_paint_change()
                for paint_x, paint_y in self.custom_building_line_points(
                    (int(first["x"]), int(first["y"])),
                    (int(second["x"]), int(second["y"])),
                ):
                    painted = self.set_custom_building_color_mark(
                        painted,
                        floor_index,
                        paint_x,
                        paint_y,
                        brush,
                    )
                cursor_x, cursor_y = int(second["x"]), int(second["y"])
                continue
            if key == "r":
                rect = self.custom_building_rect_selector(
                    "Filled Color Rectangle",
                    rows,
                )
                if rect is None:
                    continue
                remember_paint_change()
                for paint_y in range(int(rect["y1"]), int(rect["y2"]) + 1):
                    for paint_x in range(int(rect["x1"]), int(rect["x2"]) + 1):
                        painted = self.set_custom_building_color_mark(
                            painted,
                            floor_index,
                            paint_x,
                            paint_y,
                            brush,
                        )
                cursor_x, cursor_y = int(rect["x2"]), int(rect["y2"])
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
                remember_paint_change()
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
                    hint="move or delete",
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
                mouse_enabled=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return current_spawns
            if choice.value == "add":
                point = self.custom_building_point_selector(
                    f"Place NPC Spawn - Floor {floor_index + 1}",
                    rows,
                    footer="WASD/Arrows move | Z place NPC spawn | B/Q/Esc/Tab cancel",
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
                spawn = current_spawns[index]
            except (ValueError, IndexError):
                continue
            action = menu_select(
                "NPC Spawn Point",
                [
                    MenuItem(
                        label="Move spawn point",
                        value="move",
                        enabled=int(spawn.get("floor", 0) or 0) == int(floor_index),
                        hint="switch to that floor first" if int(spawn.get("floor", 0) or 0) != int(floor_index) else "",
                    ),
                    MenuItem(label="Delete spawn point", value="delete", enabled=True),
                    MenuItem(label="Back", value=MENU_BACK, enabled=True),
                ],
                footer=f"F{int(spawn.get('floor', 0)) + 1} at {spawn.get('x')},{spawn.get('y')}",
                mouse_enabled=True,
            )
            if action is None or action.value == MENU_BACK:
                continue
            if action.value == "move":
                point = self.custom_building_point_selector(
                    f"Move NPC Spawn - Floor {floor_index + 1}",
                    rows,
                    footer="WASD/Arrows move | Z place NPC spawn | B/Q/Esc/Tab cancel",
                    color_overlays=self.custom_building_floor_color_map(colors, floor_index),
                    spawn_points=self.custom_building_floor_spawn_points(current_spawns, floor_index),
                    initial_point=(int(spawn.get("x", 0)), int(spawn.get("y", 0))),
                )
                if point is not None:
                    duplicate = any(
                        other_index != index
                        and int(other.get("floor", 0) or 0) == int(floor_index)
                        and int(other.get("x", 0) or 0) == int(point["x"])
                        and int(other.get("y", 0) or 0) == int(point["y"])
                        for other_index, other in enumerate(current_spawns)
                    )
                    if not duplicate:
                        current_spawns[index].update({
                            "x": int(point["x"]),
                            "y": int(point["y"]),
                        })
            elif action.value == "delete":
                del current_spawns[index]

    @staticmethod
    def custom_building_preset_rows(grid: Sequence[Sequence[str]]) -> List[str]:
        rows = []
        for y in range(BUILDING_TEMPLATE_HEIGHT):
            source = grid[y] if y < len(grid) else ()
            row = "".join(str(tile)[:1] if str(tile) else " " for tile in source)
            rows.append(row.ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH])
        return rows

    @staticmethod
    def custom_building_preset_zones(
        floors: Sequence[Dict[str, object]],
        building_type: str,
    ) -> List[Dict[str, object]]:
        """Infer schedule zones from actual rooms instead of fixture radii."""
        zones: List[Dict[str, object]] = []

        def add_zone(kind: str, floor: int, rect: Tuple[int, int, int, int]) -> None:
            if len(zones) >= 16:
                return
            x1, y1, x2, y2 = rect
            candidate = {
                "kind": kind,
                "floor": floor,
                "x1": max(0, min(x1, x2)),
                "y1": max(0, min(y1, y2)),
                "x2": min(BUILDING_TEMPLATE_WIDTH - 1, max(x1, x2)),
                "y2": min(BUILDING_TEMPLATE_HEIGHT - 1, max(y1, y2)),
            }
            signature = (
                candidate["kind"], candidate["floor"], candidate["x1"],
                candidate["y1"], candidate["x2"], candidate["y2"],
            )
            if not any(
                (
                    zone["kind"], zone["floor"], zone["x1"],
                    zone["y1"], zone["x2"], zone["y2"],
                ) == signature
                for zone in zones
            ):
                zones.append(candidate)

        for floor_index, floor in enumerate(floors):
            rows = [
                str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH]
                for row in floor.get("rows", [])
            ]
            rows.extend(
                [" " * BUILDING_TEMPLATE_WIDTH]
                * max(0, BUILDING_TEMPLATE_HEIGHT - len(rows))
            )
            rows = rows[:BUILDING_TEMPLATE_HEIGHT]
            positions: Dict[str, List[tuple]] = {}
            for y, row in enumerate(rows):
                for x, tile in enumerate(row):
                    positions.setdefault(tile, []).append((x, y))

            def tile_at(x: int, y: int) -> str:
                if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
                    return rows[y][x]
                return " "

            structural = {"#", "-"}
            excluded = {" ", "#", "-", "D", "|", "_"}
            room_cells: Set[Tuple[int, int]] = {
                (x, y)
                for y, row in enumerate(rows)
                for x, tile in enumerate(row)
                if tile not in excluded
            }
            # A plain floor gap through a one-cell wall is an architectural
            # doorway even when the author deliberately leaves it doorless.
            # Removing those choke cells before flood filling separates rooms
            # from halls without requiring visible door furniture.
            separators: Set[Tuple[int, int]] = set()
            for x, y in room_cells:
                if tile_at(x, y) not in {".", ":", ","}:
                    continue
                horizontal_wall = (
                    tile_at(x - 1, y) in structural
                    and tile_at(x + 1, y) in structural
                    and tile_at(x, y - 1) not in excluded
                    and tile_at(x, y + 1) not in excluded
                )
                vertical_wall = (
                    tile_at(x, y - 1) in structural
                    and tile_at(x, y + 1) in structural
                    and tile_at(x - 1, y) not in excluded
                    and tile_at(x + 1, y) not in excluded
                )
                if horizontal_wall or vertical_wall:
                    separators.add((x, y))
            room_cells -= separators

            components: List[Dict[str, object]] = []
            component_by_point: Dict[Tuple[int, int], int] = {}
            unseen = set(room_cells)
            while unseen:
                start = unseen.pop()
                cells = {start}
                pending = [start]
                while pending:
                    x, y = pending.pop()
                    for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if point in unseen:
                            unseen.remove(point)
                            cells.add(point)
                            pending.append(point)
                xs = [point[0] for point in cells]
                ys = [point[1] for point in cells]
                index = len(components)
                component = {
                    "cells": cells,
                    "rect": (min(xs), min(ys), max(xs), max(ys)),
                    "symbols": {tile_at(x, y) for x, y in cells},
                }
                components.append(component)
                for point in cells:
                    component_by_point[point] = index

            def component_groups(points: Sequence[Tuple[int, int]]) -> List[Tuple[int, Dict[str, object], List[Tuple[int, int]]]]:
                grouped: Dict[int, List[Tuple[int, int]]] = {}
                for point in points:
                    component_index = component_by_point.get(point)
                    if component_index is not None:
                        grouped.setdefault(component_index, []).append(point)
                return [
                    (index, components[index], grouped[index])
                    for index in sorted(grouped)
                ]

            def cluster_rect(
                component: Dict[str, object],
                points: Sequence[Tuple[int, int]],
                padding_x: int = 1,
                padding_y: int = 1,
            ) -> Tuple[int, int, int, int]:
                cx1, cy1, cx2, cy2 = component["rect"]
                return (
                    max(cx1, min(point[0] for point in points) - padding_x),
                    max(cy1, min(point[1] for point in points) - padding_y),
                    min(cx2, max(point[0] for point in points) + padding_x),
                    min(cy2, max(point[1] for point in points) + padding_y),
                )

            bed_points = (
                [
                    point
                    for symbol in ("b", "B", "I", "J", "K")
                    for point in positions.get(symbol, [])
                ]
                if str(building_type) in {"home", "inn"}
                else []
            )
            claimed_room_components: Set[int] = set()
            for component_index, component, _points in component_groups(bed_points):
                add_zone("bedroom", floor_index, component["rect"])
                claimed_room_components.add(component_index)

            kind_symbols = {
                "kitchen": ("f", "k", "Z"),
                "shopping_counter": ("&",),
                "stockroom": ("s", "H", "i", "j", "g", "W", "y", "z", "V", "X"),
                "clinic_ward": ("+", "e", "K"),
                "library_stacks": ("l", "H", "i"),
                "workshop": ("w", "a", "x", "q", "o", "X"),
                "office": ("d", "P"),
                "dining": ("t", "T", "c", "C", "O"),
                "storage": ("s", "m", "u", "g", "W", "y", "z", "Y", "Z"),
            }
            preferred_kinds = {
                "home": ("kitchen", "dining", "storage", "office"),
                "general_store": ("shopping_counter", "stockroom", "storage", "office"),
                "market_stall": ("shopping_counter", "stockroom", "storage", "dining"),
                "inn": ("shopping_counter", "kitchen", "dining", "storage"),
                "clinic": ("shopping_counter", "clinic_ward", "storage", "office"),
                "sheriff_office": ("shopping_counter", "office", "storage"),
                "library": ("shopping_counter", "library_stacks", "office", "dining"),
                "carpenter": ("shopping_counter", "workshop", "storage", "office"),
                "workshop": ("shopping_counter", "workshop", "storage", "office"),
                "town_hall": ("shopping_counter", "office", "dining", "storage"),
            }.get(str(building_type), ("office", "storage"))
            for kind in preferred_kinds:
                if kind == "kitchen" and str(building_type) not in {"home", "inn"}:
                    continue
                anchors = [
                    point
                    for symbol in kind_symbols[kind]
                    for point in positions.get(symbol, [])
                ]
                for component_index, component, grouped_points in component_groups(anchors):
                    rect = component["rect"]
                    rect_area = (rect[2] - rect[0] + 1) * (rect[3] - rect[1] + 1)
                    # Whole-room zones are preferable for enclosed bedrooms,
                    # stockrooms, wards, stacks, workshops, and offices. In a
                    # shared public room, counters and dining sets get compact
                    # work areas instead of claiming the entire hall.
                    if kind in {"shopping_counter", "kitchen", "dining"} and rect_area > 48:
                        rect = cluster_rect(
                            component,
                            grouped_points,
                            2 if kind != "shopping_counter" else 1,
                            2 if kind == "dining" else 1,
                        )
                    elif component_index in claimed_room_components:
                        continue
                    add_zone(kind, floor_index, rect)
                    if kind not in {"shopping_counter", "kitchen", "dining"}:
                        claimed_room_components.add(component_index)

            if components:
                # Prefer the room immediately inside the exterior door. This
                # identifies the actual lobby/common room even when a side
                # workshop or gallery happens to have more floor area.
                entrance_component = None
                for door_x, door_y in positions.get("D", []):
                    for point in (
                        (door_x, door_y - 1),
                        (door_x - 1, door_y - 1),
                        (door_x + 1, door_y - 1),
                        (door_x, door_y - 2),
                    ):
                        component_index = component_by_point.get(point)
                        if component_index is not None:
                            entrance_component = components[component_index]
                            break
                    if entrance_component is not None:
                        break
                hall_component = entrance_component or max(
                    components,
                    key=lambda component: len(component["cells"]),
                )
                add_zone("public_hall", floor_index, hall_component["rect"])

        return zones[:16]

    @staticmethod
    def custom_building_preset_spawns(
        floors: Sequence[Dict[str, object]],
        building_type: str,
    ) -> List[Dict[str, int]]:
        spawns: List[Dict[str, int]] = []
        preferred = ("&", "P", "b", "B") if building_type in {"home", "inn"} else ("&", "P")
        for floor_index, floor in enumerate(floors):
            rows = [str(row) for row in floor.get("rows", [])]
            for symbol in preferred:
                for y, row in enumerate(rows):
                    for x, tile in enumerate(row):
                        if tile != symbol:
                            continue
                        landing = None
                        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                            nx, ny = x + dx, y + dy
                            if (
                                0 <= ny < len(rows)
                                and 0 <= nx < len(rows[ny])
                                and rows[ny][nx] in {".", ","}
                            ):
                                landing = (nx, ny)
                                break
                        spawn_x, spawn_y = landing or (x, y)
                        record = {"floor": floor_index, "x": spawn_x, "y": spawn_y}
                        if record not in spawns:
                            spawns.append(record)
                        if len(spawns) >= 12:
                            return spawns
        return spawns

    def custom_building_builtin_record(
        self,
        *,
        preset_id: str,
        name: str,
        description: str,
        building_type: str,
        max_occupancy: int,
        floors: Sequence[Dict[str, object]],
        group: str,
        origin: str,
    ) -> Optional[Dict[str, object]]:
        normalized_floors = [
            {
                "name": str(floor.get("name", "Ground Floor")),
                "rows": self.custom_building_preset_rows(floor.get("rows", [])),
            }
            for floor in floors
        ]
        record = sanitize_custom_building_template({
            "name": name,
            "description": description,
            "building_type": building_type,
            "max_occupancy": max_occupancy,
            "enabled": False,
            "builtin_preset_id": preset_id,
            "floors": normalized_floors,
            "zones": [],
            "spawns": [],
            "colors": [],
        })
        if record is not None:
            # Validation may add a missing service, bed, or utility fixture.
            # Infer schedule metadata from that final editable layout.
            record = sanitize_custom_building_template({
                **record,
                "zones": self.custom_building_preset_zones(record.get("floors", []), building_type),
                "spawns": self.custom_building_preset_spawns(record.get("floors", []), building_type),
            })
        if record is not None:
            record["_preset_group"] = group
            record["_preset_origin"] = origin
        return record

    def built_in_building_template_presets(self) -> List[Dict[str, object]]:
        """Expose stable source records for direct, reversible map overrides."""
        presets: List[Dict[str, object]] = []
        authored_group = "Starting Town & Farm"
        for label, building_type, factory_name, occupancy in BUILT_IN_AUTHORED_BUILDING_PRESETS:
            factory = getattr(self, factory_name, None)
            if not callable(factory):
                continue
            grid = factory()
            record = self.custom_building_builtin_record(
                preset_id=f"authored:{factory_name}",
                name=f"Built-in {label}",
                description=(
                    f"Editable layout for the authored {label} interior."
                ),
                building_type=building_type,
                max_occupancy=occupancy,
                floors=[{"name": "Ground Floor", "rows": grid}],
                group=authored_group,
                origin="authored",
            )
            if record is not None:
                presets.append(record)

        for residence_id, residence in AUTHORED_TOWN_RESIDENCE_DATA.items():
            label = str(residence.get("label", residence_id.replace("_", " ").title()))
            grid = self.make_authored_town_residence_map(str(residence_id))
            record = self.custom_building_builtin_record(
                preset_id=f"residence:{residence_id}",
                name=f"Built-in {label}",
                description=f"Editable layout for the authored {label} residence.",
                building_type="home",
                max_occupancy=max(1, len(residence.get("residents", ()) or ())),
                floors=[{"name": "Ground Floor", "rows": grid}],
                group=authored_group,
                origin="authored",
            )
            if record is not None:
                presets.append(record)

        procedural_group = "Procedural Town Layouts"
        for building_type in BUILDING_TEMPLATE_TYPES:
            label = BUILDING_TEMPLATE_TYPE_LABELS.get(building_type, building_type.replace("_", " ").title())
            for layout_variant in range(4):
                floor_count = 2 if building_type in {"home", "inn"} else 1
                plan = {
                    "id": "built-in-template-browser",
                    "seed": 7301,
                    "buildings": {},
                }
                building = {
                    "id": f"preset:{building_type}:{layout_variant}",
                    "type_id": building_type,
                    "name": label,
                }
                ground = self.procedural_town_generated_ground_floor_map(
                    plan,
                    building,
                    floor_count,
                    None,
                    None,
                    {},
                    layout_variant,
                    layout_variant,
                )
                floors: List[Dict[str, object]] = [{"name": "Ground Floor", "rows": ground}]
                if floor_count > 1:
                    floors.append({
                        "name": "Upper Floor",
                        "rows": self.procedural_town_generated_upper_floor_map(
                            plan,
                            building,
                            1,
                            floor_count,
                            layout_variant,
                        ),
                    })
                variant_name = chr(ord("A") + layout_variant)
                record = self.custom_building_builtin_record(
                    preset_id=f"procedural:{building_type}:{layout_variant}",
                    name=f"{label} Layout {variant_name}",
                    description=(
                        f"Editable built-in procedural {label.lower()} layout {variant_name}."
                    ),
                    building_type=building_type,
                    max_occupancy=12 if building_type == "inn" else (6 if building_type == "home" else 0),
                    floors=floors,
                    group=procedural_group,
                    origin="procedural",
                )
                if record is not None:
                    presets.append(record)
        return presets

    @staticmethod
    def custom_building_editable_preset_copy(
        preset: Dict[str, object],
        existing_records: Sequence[Dict[str, object]],
    ) -> Optional[Dict[str, object]]:
        existing_names = {
            str(record.get("name", "")).casefold()
            for record in existing_records
            if isinstance(record, dict)
        }
        source_name = str(preset.get("name", "Building")).replace("Built-in ", "", 1).strip()
        number = 1
        while True:
            suffix = " Copy" if number == 1 else f" Copy {number}"
            candidate_name = f"{source_name[:max(1, 32 - len(suffix))]}{suffix}"
            if candidate_name.casefold() not in existing_names:
                break
            number += 1
        draft = copy.deepcopy(preset)
        draft["name"] = candidate_name
        draft["enabled"] = False
        draft.pop("_preset_group", None)
        draft.pop("_preset_origin", None)
        return sanitize_custom_building_template(draft)

    def custom_building_builtin_preset_menu(self) -> bool:
        presets = self.built_in_building_template_presets()
        groups = list(dict.fromkeys(str(record.get("_preset_group", "Built-in")) for record in presets))
        while True:
            content = self.custom_content_data()
            records = [
                record
                for record in content.get("building_templates", [])
                if isinstance(record, dict)
            ]
            overrides = {
                str(record.get("builtin_preset_id", "")): record
                for record in records
                if record.get("overrides_builtin") and record.get("builtin_preset_id")
            }
            group_choice = menu_select(
                "Edit Existing Building Maps",
                [
                    MenuItem(
                        label=group,
                        value=group,
                        enabled=True,
                        hint=(
                            f"{sum(1 for record in presets if record.get('_preset_group') == group)} maps | "
                            f"{sum(1 for record in presets if record.get('_preset_group') == group and record.get('builtin_preset_id') in overrides)} edited"
                        ),
                    )
                    for group in groups
                ] + [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                footer="Choose a group, then choose a map. It opens directly on the editable canvas.",
                mouse_enabled=True,
            )
            if group_choice is None or group_choice.value == MENU_BACK:
                return False
            group = str(group_choice.value)
            while True:
                group_presets = [record for record in presets if record.get("_preset_group") == group]
                modified_presets = [
                    record
                    for record in group_presets
                    if str(record.get("builtin_preset_id", "")) in overrides
                ]
                preset_choice = menu_select(
                    group,
                    [
                        MenuItem(
                            label=str(record.get("name", "Built-in Interior")),
                            value=index,
                            enabled=True,
                            hint=BUILDING_TEMPLATE_TYPE_LABELS.get(
                                str(record.get("building_type", "")),
                                str(record.get("building_type", "")),
                            ) + (
                                " | EDITED"
                                if str(record.get("builtin_preset_id", "")) in overrides
                                else ""
                            ),
                        )
                        for index, record in enumerate(group_presets)
                    ] + [
                        MenuItem(
                            label="Restore an edited map to its original",
                            value="restore",
                            enabled=bool(modified_presets),
                            hint=f"{len(modified_presets)} edited",
                        ),
                        MenuItem(label="Back", value=MENU_BACK, enabled=True),
                    ],
                    footer="Selecting a map immediately displays it for editing. Saved edits replace that built-in layout.",
                    mouse_enabled=True,
                )
                if preset_choice is None or preset_choice.value == MENU_BACK:
                    break
                if preset_choice.value == "restore":
                    restore_choice = menu_select(
                        "Restore Original Map",
                        [
                            MenuItem(
                                label=str(record.get("name", "Built-in Interior")),
                                value=str(record.get("builtin_preset_id", "")),
                                enabled=True,
                                hint="remove saved edits",
                            )
                            for record in modified_presets
                        ] + [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                        footer="Choose an edited map to restore its original game layout.",
                        mouse_enabled=True,
                    )
                    if restore_choice is None or restore_choice.value == MENU_BACK:
                        continue
                    restore_id = str(restore_choice.value)
                    confirm = menu_select(
                        "Restore Original Map",
                        [
                            MenuItem(label="Restore original", value="restore", enabled=True),
                            MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
                        ],
                        footer="Your edited override will be removed. The original built-in map remains available.",
                        mouse_enabled=True,
                    )
                    if confirm is None or confirm.value != "restore":
                        continue
                    records = [
                        record
                        for record in records
                        if not (
                            record.get("overrides_builtin")
                            and str(record.get("builtin_preset_id", "")) == restore_id
                        )
                    ]
                    content["building_templates"] = records
                    saved, message = save_custom_content(content)
                    self.state.message = "Restored the original building map." if saved else message
                    if saved:
                        self.custom_building_refresh_runtime_maps()
                    break
                try:
                    preset = group_presets[int(preset_choice.value)]
                except (ValueError, TypeError, IndexError):
                    continue
                preset_id = str(preset.get("builtin_preset_id", ""))
                source = overrides.get(preset_id, preset)
                draft = sanitize_custom_building_template({
                    **copy.deepcopy(source),
                    "name": str(preset.get("name", "Built-in Interior")),
                    "builtin_preset_id": preset_id,
                    "overrides_builtin": True,
                    "manual_layout": True,
                    "enabled": True,
                })
                updated = (
                    self.custom_building_template_builder(draft, open_canvas=True)
                    if draft is not None
                    else None
                )
                if updated is None:
                    continue
                updated["builtin_preset_id"] = preset_id
                updated["overrides_builtin"] = True
                updated["manual_layout"] = True
                updated["enabled"] = True
                updated["building_type"] = str(preset.get("building_type", "home"))
                records = [
                    record
                    for record in records
                    if not (
                        record.get("overrides_builtin")
                        and str(record.get("builtin_preset_id", "")) == preset_id
                    )
                ]
                records.append(updated)
                content["building_templates"] = records
                saved, message = save_custom_content(content)
                self.state.message = (
                    f"Saved edits to {updated.get('name', 'Building')}."
                    if saved
                    else message
                )
                if saved:
                    self.custom_building_refresh_runtime_maps()
                break

    @staticmethod
    def custom_building_builtin_override_grid(preset_id: str) -> Optional[List[List[str]]]:
        override = custom_building_template_override(preset_id)
        if override is None or not override.get("enabled", True):
            return None
        floors = override.get("floors", [])
        if not isinstance(floors, list) or not floors:
            return None
        return [list(str(row)) for row in floors[0].get("rows", [])]

    def custom_building_refresh_runtime_maps(self) -> None:
        """Make saved map edits visible without requiring a restart."""
        if hasattr(self, "_procedural_town_interior_cache"):
            self._procedural_town_interior_cache = {}
        if hasattr(self, "_procedural_town_room_lookup_cache"):
            self._procedural_town_room_lookup_cache = {}
        if hasattr(self, "_authored_town_residence_maps"):
            self._authored_town_residence_maps = {}
        refresh = getattr(self, "refresh_town_interior_maps", None)
        if callable(refresh):
            refresh()
        if hasattr(self, "house_map"):
            house_override = self.custom_building_builtin_override_grid(
                "authored:make_house_map"
            )
            if house_override is not None:
                self.house_map = house_override

    def custom_building_template_validation(
        self,
        record: Dict[str, object],
    ) -> Dict[str, object]:
        template = sanitize_custom_building_template(record)
        if template is None:
            return {
                "critical": ["The template data could not be validated."],
                "advisories": [],
                "lines": ["INVALID TEMPLATE", "", "The template data could not be validated."],
            }
        critical: List[str] = []
        advisories: List[str] = []
        # Closed room doors are traversable after opening, so readiness treats
        # them as connective architecture rather than permanent walls.
        passable_tiles = {".", ",", "|", "_", ":"}
        floor_reachable: Dict[int, set] = {}
        floors = list(template.get("floors", []) or [])
        for floor_index, floor in enumerate(floors):
            rows = [str(row) for row in floor.get("rows", [])]
            all_passable = {
                (x, y)
                for y, row in enumerate(rows)
                for x, tile in enumerate(row)
                if tile in passable_tiles
            }
            if not all_passable:
                critical.append(f"Floor {floor_index + 1} has no walkable space.")
                floor_reachable[floor_index] = set()
                continue
            entry_symbols = {"D"} if floor_index == 0 else {">"}
            entries = [
                (x, y)
                for y, row in enumerate(rows)
                for x, tile in enumerate(row)
                if tile in entry_symbols
            ]
            if not entries:
                critical.append(
                    f"Floor {floor_index + 1} needs an {'exterior door' if floor_index == 0 else 'arrival stair'}."
                )
                floor_reachable[floor_index] = set()
                continue
            starts = []
            for entry_x, entry_y in entries:
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    point = (entry_x + dx, entry_y + dy)
                    if point in all_passable:
                        starts.append(point)
            if not starts:
                critical.append(f"Floor {floor_index + 1}'s entrance has no walkable landing.")
                floor_reachable[floor_index] = set()
                continue
            reached = set()
            pending = list(starts)
            while pending:
                point = pending.pop()
                if point in reached or point not in all_passable:
                    continue
                reached.add(point)
                x, y = point
                pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
            floor_reachable[floor_index] = reached
            disconnected = len(all_passable - reached)
            if disconnected:
                advisories.append(
                    f"Floor {floor_index + 1} has {disconnected} walkable tile{'s' if disconnected != 1 else ''} disconnected from its entrance."
                )
            if floor_index < len(floors) - 1 and not any("<" in row for row in rows):
                critical.append(f"Floor {floor_index + 1} needs stairs leading up.")

        zone_kinds = {
            str(zone.get("kind", ""))
            for zone in template.get("zones", [])
            if isinstance(zone, dict)
        }
        recommended_zones = {
            "home": {"bedroom", "kitchen"},
            "general_store": {"shopping_counter", "stockroom"},
            "market_stall": {"shopping_counter", "stockroom"},
            "inn": {"bedroom", "kitchen", "dining", "shopping_counter"},
            "clinic": {"clinic_ward", "office"},
            "sheriff_office": {"office", "public_hall"},
            "library": {"library_stacks", "public_hall"},
            "carpenter": {"workshop", "storage"},
            "workshop": {"workshop", "storage"},
            "town_hall": {"office", "public_hall"},
        }.get(str(template.get("building_type", "")), set())
        missing_zones = sorted(recommended_zones - zone_kinds)
        if missing_zones:
            advisories.append(
                "Recommended schedule zones missing: "
                + ", ".join(BUILDING_TEMPLATE_ZONE_LABELS.get(kind, kind) for kind in missing_zones)
                + "."
            )
        if not template.get("zones"):
            advisories.append("No NPC schedule zones are designated.")
        for zone_index, zone in enumerate(template.get("zones", []), start=1):
            floor_index = int(zone.get("floor", 0) or 0)
            rows = [str(row) for row in floors[floor_index].get("rows", [])] if 0 <= floor_index < len(floors) else []
            has_walkable = any(
                0 <= y < len(rows)
                and 0 <= x < len(rows[y])
                and rows[y][x] in passable_tiles
                for y in range(int(zone.get("y1", 0)), int(zone.get("y2", 0)) + 1)
                for x in range(int(zone.get("x1", 0)), int(zone.get("x2", 0)) + 1)
            )
            if not has_walkable:
                advisories.append(f"Zone {zone_index} contains no walkable tile.")

        if not template.get("spawns"):
            advisories.append("No preferred NPC spawn points are designated.")
        for spawn_index, spawn in enumerate(template.get("spawns", []), start=1):
            floor_index = int(spawn.get("floor", 0) or 0)
            point = (int(spawn.get("x", 0) or 0), int(spawn.get("y", 0) or 0))
            reached = floor_reachable.get(floor_index, set())
            near_reached = point in reached or any(
                (point[0] + dx, point[1] + dy) in reached
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
            )
            if not near_reached:
                advisories.append(f"NPC spawn {spawn_index} is not beside an entrance-reachable tile.")

        bedroom_count = sum(
            1
            for zone in template.get("zones", [])
            if isinstance(zone, dict) and str(zone.get("kind")) == "bedroom"
        )
        if int(template.get("max_occupancy", 0) or 0) > 0 and bedroom_count <= 0:
            advisories.append("Occupancy is above zero, but no bedroom zone is designated.")

        status = (
            "Blocked: repair critical issues before saving."
            if critical
            else "Ready to save."
            if not advisories
            else "Ready to save with advisories."
        )
        lines = [
            "TEMPLATE READINESS",
            "",
            (
                f"Floors: {len(floors)} | Zones: {len(template.get('zones', []))} | "
                f"NPC spawns: {len(template.get('spawns', []))} | "
                f"Painted tiles: {len(template.get('colors', []))}"
            ),
            status,
            "",
            "Critical:",
            *([f"- {message}" for message in critical] or ["- None."]),
            "",
            "Advisories:",
            *([f"- {message}" for message in advisories] or ["- None."]),
        ]
        return {
            "critical": critical,
            "advisories": advisories,
            "lines": lines,
        }

    @staticmethod
    def custom_building_duplicate_floor_data(
        floors: Sequence[Dict[str, object]],
        zones: Sequence[Dict[str, object]],
        spawns: Sequence[Dict[str, object]],
        colors: Sequence[Dict[str, object]],
        source_floor: int,
    ) -> tuple:
        copied_floors = [
            {
                "name": str(floor.get("name", f"Floor {index + 1}")),
                "rows": list(floor.get("rows", [])),
            }
            for index, floor in enumerate(floors)
            if isinstance(floor, dict)
        ]
        copied_zones = [dict(zone) for zone in zones if isinstance(zone, dict)]
        copied_spawns = [dict(spawn) for spawn in spawns if isinstance(spawn, dict)]
        copied_colors = [dict(color) for color in colors if isinstance(color, dict)]
        if not (0 <= int(source_floor) < len(copied_floors)):
            return copied_floors, copied_zones, copied_spawns, copied_colors, -1
        source_floor = int(source_floor)
        new_floor = len(copied_floors)
        source_name = str(copied_floors[source_floor].get("name", f"Floor {source_floor + 1}"))
        copy_suffix = " Copy"
        copied_floors.append({
            "name": f"{source_name[:max(1, 28 - len(copy_suffix))]}{copy_suffix}",
            "rows": list(copied_floors[source_floor].get("rows", [])),
        })
        copied_zones.extend(
            {
                **dict(zone),
                "floor": new_floor,
            }
            for zone in list(copied_zones)
            if (
                len(copied_zones) < 16
                and int(zone.get("floor", 0) or 0) == source_floor
            )
        )
        copied_zones = copied_zones[:16]
        copied_spawns.extend(
            {
                **dict(spawn),
                "floor": new_floor,
            }
            for spawn in list(copied_spawns)
            if (
                len(copied_spawns) < BUILDING_TEMPLATE_MAX_SPAWNS
                and int(spawn.get("floor", 0) or 0) == source_floor
            )
        )
        copied_spawns = copied_spawns[:BUILDING_TEMPLATE_MAX_SPAWNS]
        copied_colors.extend(
            {
                **dict(color),
                "floor": new_floor,
            }
            for color in list(copied_colors)
            if (
                len(copied_colors) < BUILDING_TEMPLATE_MAX_COLOR_MARKS
                and int(color.get("floor", 0) or 0) == source_floor
            )
        )
        copied_colors = copied_colors[:BUILDING_TEMPLATE_MAX_COLOR_MARKS]
        return copied_floors, copied_zones, copied_spawns, copied_colors, new_floor

    @staticmethod
    def custom_building_transform_floor_data(
        floors: Sequence[Dict[str, object]],
        zones: Sequence[Dict[str, object]],
        spawns: Sequence[Dict[str, object]],
        colors: Sequence[Dict[str, object]],
        floor_index: int,
        transform: str,
    ) -> tuple:
        transformed_floors = [
            {
                "name": str(floor.get("name", f"Floor {index + 1}")),
                "rows": list(floor.get("rows", [])),
            }
            for index, floor in enumerate(floors)
            if isinstance(floor, dict)
        ]
        transformed_zones = [dict(zone) for zone in zones if isinstance(zone, dict)]
        transformed_spawns = [dict(spawn) for spawn in spawns if isinstance(spawn, dict)]
        transformed_colors = [dict(color) for color in colors if isinstance(color, dict)]
        if not (0 <= int(floor_index) < len(transformed_floors)):
            return transformed_floors, transformed_zones, transformed_spawns, transformed_colors
        floor_index = int(floor_index)
        rows = [
            str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH]
            for row in transformed_floors[floor_index].get("rows", [])
        ]
        rows = (rows + [" " * BUILDING_TEMPLATE_WIDTH] * BUILDING_TEMPLATE_HEIGHT)[:BUILDING_TEMPLATE_HEIGHT]

        def point(x: int, y: int) -> tuple:
            if transform == "horizontal":
                return BUILDING_TEMPLATE_WIDTH - 1 - int(x), int(y)
            if transform == "vertical":
                return int(x), BUILDING_TEMPLATE_HEIGHT - 1 - int(y)
            if transform == "rotate_180":
                return (
                    BUILDING_TEMPLATE_WIDTH - 1 - int(x),
                    BUILDING_TEMPLATE_HEIGHT - 1 - int(y),
                )
            return int(x), int(y)

        if transform == "horizontal":
            transformed_floors[floor_index]["rows"] = [row[::-1] for row in rows]
        elif transform == "vertical":
            transformed_floors[floor_index]["rows"] = list(reversed(rows))
        elif transform == "rotate_180":
            transformed_floors[floor_index]["rows"] = [row[::-1] for row in reversed(rows)]
        else:
            return transformed_floors, transformed_zones, transformed_spawns, transformed_colors

        for zone in transformed_zones:
            if int(zone.get("floor", 0) or 0) != floor_index:
                continue
            corners = [
                point(int(zone.get("x1", 0)), int(zone.get("y1", 0))),
                point(int(zone.get("x2", 0)), int(zone.get("y2", 0))),
            ]
            zone.update({
                "x1": min(x for x, _y in corners),
                "y1": min(y for _x, y in corners),
                "x2": max(x for x, _y in corners),
                "y2": max(y for _x, y in corners),
            })
        for records in (transformed_spawns, transformed_colors):
            for record in records:
                if int(record.get("floor", 0) or 0) != floor_index:
                    continue
                x, y = point(
                    int(record.get("x", 0) or 0),
                    int(record.get("y", 0) or 0),
                )
                record.update({"x": x, "y": y})
        return transformed_floors, transformed_zones, transformed_spawns, transformed_colors

    @staticmethod
    def custom_building_link_stair_floors(
        floors: Sequence[Dict[str, object]],
        lower_floor: int,
        x: int,
        y: int,
    ) -> tuple:
        linked = [
            {
                "name": str(floor.get("name", f"Floor {index + 1}")),
                "rows": list(floor.get("rows", [])),
            }
            for index, floor in enumerate(floors)
            if isinstance(floor, dict)
        ]
        lower_floor = int(lower_floor)
        upper_floor = lower_floor + 1
        x, y = int(x), int(y)
        if not (
            0 <= lower_floor < len(linked) - 1
            and 0 <= x < BUILDING_TEMPLATE_WIDTH
            and 0 <= y < BUILDING_TEMPLATE_HEIGHT
        ):
            return linked, False
        grids = [
            [
                list(str(row).ljust(BUILDING_TEMPLATE_WIDTH)[:BUILDING_TEMPLATE_WIDTH])
                for row in floor.get("rows", [])
            ]
            for floor in linked
        ]
        for grid in grids:
            while len(grid) < BUILDING_TEMPLATE_HEIGHT:
                grid.append([" " for _ in range(BUILDING_TEMPLATE_WIDTH)])
        if grids[lower_floor][y][x] not in {".", ","} or grids[upper_floor][y][x] not in {".", ","}:
            return linked, False
        for row in grids[lower_floor]:
            for tile_x, tile in enumerate(row):
                if tile == "<":
                    row[tile_x] = "."
        for row in grids[upper_floor]:
            for tile_x, tile in enumerate(row):
                if tile == ">":
                    row[tile_x] = "."
        grids[lower_floor][y][x] = "<"
        grids[upper_floor][y][x] = ">"
        linked[lower_floor]["rows"] = ["".join(row) for row in grids[lower_floor]]
        linked[upper_floor]["rows"] = ["".join(row) for row in grids[upper_floor]]
        return linked, True

    def custom_building_template_builder(
        self,
        existing: Optional[Dict[str, object]] = None,
        *,
        open_canvas: bool = False,
    ) -> Optional[Dict[str, object]]:
        current = sanitize_custom_building_template(existing or {
            "name": "New Building",
            "building_type": "home",
            "enabled": True,
        }) or {}
        name = str(current.get("name", "New Building"))
        description = str(current.get("description", "A custom procedural-town building template."))
        building_type = str(current.get("building_type", "home"))
        occupancy = int(current.get("max_occupancy", 4 if building_type in {"home", "inn"} else 0))
        generation_weight = int(current.get("generation_weight", 5) or 5)
        enabled = "enabled" if current.get("enabled", True) else "disabled"
        builtin_preset_id = str(current.get("builtin_preset_id", ""))
        overrides_builtin = bool(current.get("overrides_builtin", False))
        manual_layout = bool(current.get("manual_layout", False))

        if existing is None:
            name = text_entry_menu("Building Template", "Template name?", name, 32)
            if name is None:
                return None
            description = text_entry_menu(
                "Building Template",
                "Short description?",
                description,
                220,
            )
            if description is None:
                return None
            chosen_type = self.custom_choice_menu(
                "Building Type",
                BUILDING_TEMPLATE_TYPES,
                building_type,
                labels=BUILDING_TEMPLATE_TYPE_LABELS,
                hints={key: "joins this procedural building pool" for key in BUILDING_TEMPLATE_TYPES},
            )
            if chosen_type is None:
                return None
            building_type = chosen_type
            occupancy = self.custom_number_menu(
                "Maximum Occupancy",
                "Occupancy",
                0,
                24,
                4 if building_type in {"home", "inn"} else 0,
            )
            if occupancy is None:
                return None
            generation_weight = self.custom_number_menu(
                "Procedural Pool Weight",
                "Weight",
                1,
                10,
                generation_weight,
                hint_suffix="/10",
            )
            if generation_weight is None:
                return None
            chosen_enabled = self.custom_choice_menu(
                "Generator Use",
                ["enabled", "disabled"],
                enabled,
                hints={
                    "enabled": "May appear in generated towns for this building type.",
                    "disabled": "Saved for editing/export but not used by generation.",
                },
            )
            if chosen_enabled is None:
                return None
            enabled = chosen_enabled
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
            manual_layout = True
            open_canvas = True
        if open_canvas:
            floors[current_floor]["rows"] = self.custom_building_fixture_editor(
                floors[current_floor]["rows"],
                current_floor,
                zones=zones,
                spawns=spawns,
                colors=colors,
            )
            manual_layout = True
        while True:
            draft = sanitize_custom_building_template({
                "name": name,
                "description": description,
                "building_type": building_type,
                "max_occupancy": occupancy,
                "generation_weight": generation_weight,
                "enabled": enabled == "enabled",
                "manual_layout": manual_layout,
                "builtin_preset_id": builtin_preset_id,
                "overrides_builtin": overrides_builtin,
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
            readiness = self.custom_building_template_validation(draft)
            readiness_count = len(readiness["critical"]) + len(readiness["advisories"])
            choice = menu_select(
                f"Edit {name}",
                [
                    MenuItem(
                        label="Open map canvas",
                        value="fixtures",
                        enabled=True,
                        hint=f"F{current_floor + 1}: {current_floor_name} | draw freely",
                    ),
                    MenuItem(
                        label="Template settings",
                        value="settings",
                        enabled=True,
                        hint=f"{BUILDING_TEMPLATE_TYPE_LABELS.get(building_type, building_type)} | occupancy {occupancy}",
                    ),
                    MenuItem(label="Switch floor", value="floor", enabled=len(floors) > 1, hint=f"editing F{current_floor + 1}: {current_floor_name}"),
                    MenuItem(label="Rename current floor", value="rename_floor", enabled=True, hint=current_floor_name),
                    MenuItem(label="Duplicate current floor", value="duplicate_floor", enabled=len(floors) < BUILDING_TEMPLATE_MAX_FLOORS, hint="copies layout, zones, spawns, and paint"),
                    MenuItem(label="Add upper floor", value="add_floor", enabled=len(floors) < BUILDING_TEMPLATE_MAX_FLOORS, hint=f"{len(floors)}/{BUILDING_TEMPLATE_MAX_FLOORS} floors"),
                    MenuItem(label="Remove current upper floor", value="remove_floor", enabled=len(floors) > 1 and current_floor > 0, hint="keeps ground floor"),
                    MenuItem(label="Transform current floor", value="transform_floor", enabled=True, hint="mirrors layout, zones, spawns, and paint"),
                    MenuItem(label="Align stairs between floors", value="link_stairs", enabled=len(floors) > 1, hint="places matching < and > at one coordinate"),
                    MenuItem(label="Redraw current-floor boundary", value="boundary", enabled=True, hint=f"F{current_floor + 1} cursor rectangle"),
                    MenuItem(
                        label="Edit functional zones",
                        value="zones",
                        enabled=True,
                        hint=f"{len(zones)} zones | draw, redraw, change, or delete",
                    ),
                    MenuItem(
                        label="Rebuild zones from rooms",
                        value="infer_zones",
                        enabled=True,
                        hint="replace zones with room-aware suggestions",
                    ),
                    MenuItem(label="Designate NPC spawn points", value="spawns", enabled=True, hint=f"{len(spawns)} spawns"),
                    MenuItem(label="Paint tile colors", value="colors", enabled=True, hint=f"{len(colors)} painted tiles"),
                    MenuItem(label="Review readiness", value="readiness", enabled=True, hint=f"{readiness_count} issue{'s' if readiness_count != 1 else ''}"),
                    MenuItem(label="Preview template", value="preview", enabled=True),
                    MenuItem(label="Save and exit", value="save", enabled=True),
                    MenuItem(label="Discard changes", value=MENU_BACK, enabled=True),
                ],
                footer="Open map canvas is the main editor. Left-click paints, right-click erases, P chooses a tile, ? shows controls.",
                extra_lines=[
                    f"Editing F{current_floor + 1}: {current_floor_name}",
                    "Saved built-in edits replace that exact game layout." if overrides_builtin else "This template can be used by generated towns.",
                    "",
                ] + custom_building_template_summary(draft)[:10],
                mouse_enabled=True,
            )
            if choice is None or choice.value == MENU_BACK:
                return None
            if choice.value == "settings":
                updated_name = text_entry_menu("Template Settings", "Template name?", name, 32)
                if updated_name is None:
                    continue
                updated_description = text_entry_menu(
                    "Template Settings",
                    "Short description?",
                    description,
                    220,
                )
                if updated_description is None:
                    continue
                updated_type = self.custom_choice_menu(
                    "Building Type",
                    BUILDING_TEMPLATE_TYPES,
                    building_type,
                    labels=BUILDING_TEMPLATE_TYPE_LABELS,
                    hints={key: "building role and procedural pool" for key in BUILDING_TEMPLATE_TYPES},
                )
                if updated_type is None:
                    continue
                updated_occupancy = self.custom_number_menu(
                    "Maximum Occupancy",
                    "Occupancy",
                    0,
                    24,
                    occupancy,
                )
                if updated_occupancy is None:
                    continue
                updated_weight = self.custom_number_menu(
                    "Procedural Pool Weight",
                    "Weight",
                    1,
                    10,
                    generation_weight,
                    hint_suffix="/10",
                )
                if updated_weight is None:
                    continue
                updated_enabled = self.custom_choice_menu(
                    "Generator Use",
                    ["enabled", "disabled"],
                    enabled,
                    hints={
                        "enabled": "Use this layout in the game.",
                        "disabled": "Keep it saved without using it.",
                    },
                )
                if updated_enabled is None:
                    continue
                name = updated_name
                description = updated_description
                building_type = updated_type
                occupancy = updated_occupancy
                generation_weight = updated_weight
                enabled = "enabled" if overrides_builtin else updated_enabled
            elif choice.value == "floor":
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
                    mouse_enabled=True,
                )
                if floor_choice is not None and floor_choice.value != MENU_BACK:
                    current_floor = int(floor_choice.value)
            elif choice.value == "rename_floor":
                renamed = text_entry_menu(
                    "Rename Floor",
                    "Floor name?",
                    current_floor_name,
                    28,
                )
                if renamed is not None:
                    floors[current_floor]["name"] = renamed
            elif choice.value == "duplicate_floor":
                floors, zones, spawns, colors, new_floor = self.custom_building_duplicate_floor_data(
                    floors,
                    zones,
                    spawns,
                    colors,
                    current_floor,
                )
                if new_floor >= 0:
                    current_floor = new_floor
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
            elif choice.value == "transform_floor":
                transform_choice = menu_select(
                    "Transform Floor",
                    [
                        MenuItem(label="Mirror horizontally", value="horizontal", enabled=True, hint="safe for every floor"),
                        MenuItem(
                            label="Mirror vertically",
                            value="vertical",
                            enabled=current_floor > 0,
                            hint="ground-floor exterior doors must remain on the bottom edge",
                        ),
                        MenuItem(
                            label="Rotate 180 degrees",
                            value="rotate_180",
                            enabled=current_floor > 0,
                            hint="ground-floor exterior doors must remain on the bottom edge",
                        ),
                        MenuItem(label="Back", value=MENU_BACK, enabled=True),
                    ],
                    footer="The matching zones, NPC spawns, and paint marks transform with the floor.",
                    mouse_enabled=True,
                )
                if transform_choice is not None and transform_choice.value != MENU_BACK:
                    floors, zones, spawns, colors = self.custom_building_transform_floor_data(
                        floors,
                        zones,
                        spawns,
                        colors,
                        current_floor,
                        str(transform_choice.value),
                    )
            elif choice.value == "link_stairs":
                lower_floor = current_floor if current_floor < len(floors) - 1 else current_floor - 1
                point = self.custom_building_point_selector(
                    f"Align Floors {lower_floor + 1} and {lower_floor + 2}",
                    floors[lower_floor]["rows"],
                    footer="Select a floor tile that is open at the same coordinate on both floors.",
                )
                if point is not None:
                    floors, linked = self.custom_building_link_stair_floors(
                        floors,
                        lower_floor,
                        int(point["x"]),
                        int(point["y"]),
                    )
                    self.state.message = (
                        f"Aligned stairs at {point['x']},{point['y']}."
                        if linked
                        else "That coordinate must be ordinary floor on both levels."
                    )
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
            elif choice.value == "infer_zones":
                suggested_zones = self.custom_building_preset_zones(
                    floors,
                    building_type,
                )
                confirm = menu_select(
                    "Rebuild Functional Zones",
                    [
                        MenuItem(
                            label="Replace current zones",
                            value="replace",
                            enabled=bool(suggested_zones),
                            hint=f"{len(suggested_zones)} room-aware zones",
                        ),
                        MenuItem(label="Cancel", value=MENU_BACK, enabled=True),
                    ],
                    footer="This analyzes enclosed rooms and functional furniture. It does not alter the map, furniture, paint, or NPC spawns.",
                    extra_lines=[
                        "Existing hand-drawn zones will be replaced only if you confirm.",
                        "You can still redraw or delete any suggestion afterward.",
                    ],
                    mouse_enabled=True,
                )
                if confirm is not None and confirm.value == "replace":
                    zones = suggested_zones
                    self.state.message = f"Rebuilt {len(zones)} functional zones from the room layout."
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
                    zones=zones,
                    spawns=spawns,
                    colors=colors,
                )
            elif choice.value == "colors":
                colors = self.custom_building_color_editor(
                    floors[current_floor]["rows"],
                    colors,
                    current_floor,
                )
            elif choice.value == "readiness":
                menu_select(
                    "Template Readiness",
                    [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                    extra_lines=list(readiness["lines"]),
                    mouse_enabled=True,
                )
            elif choice.value == "preview":
                menu_select(
                    str(draft.get("name", "Building Template")),
                    [MenuItem(label="Back", value=MENU_BACK, enabled=True)],
                    extra_lines=custom_building_template_summary(draft),
                    mouse_enabled=True,
                )
            elif choice.value == "save":
                review = self.custom_building_template_validation(draft)
                save_choice = menu_select(
                    "Review and Save",
                    [
                        MenuItem(
                            label="Save template",
                            value="save",
                            enabled=not bool(review["critical"]),
                            hint="repair critical issues first" if review["critical"] else "write this template to the custom library",
                        ),
                        MenuItem(label="Return to editor", value=MENU_BACK, enabled=True),
                    ],
                    extra_lines=list(review["lines"]),
                    mouse_enabled=True,
                )
                if save_choice is not None and save_choice.value == "save":
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
            if field_name == "building_templates":
                items.append(
                    MenuItem(
                        label="Edit existing game maps",
                        value="built_in_presets",
                        enabled=True,
                        hint="open and edit the maps used by the game",
                    )
                )
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
                    saved, self.state.message = save_custom_content(content)
                    if saved and field_name == "building_templates":
                        self.custom_building_refresh_runtime_maps()
                continue
            if choice.value == "built_in_presets" and field_name == "building_templates":
                self.custom_building_builtin_preset_menu()
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
                    MenuItem(
                        label="Edit map" if field_name == "building_templates" else "Edit",
                        value="edit",
                        enabled=True,
                        hint="opens directly on the canvas" if field_name == "building_templates" else "",
                    ),
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
                updated = (
                    self.custom_building_template_builder(record, open_canvas=True)
                    if field_name == "building_templates"
                    else builder(record)
                )
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
                    saved, self.state.message = save_custom_content(content)
                    if saved and field_name == "building_templates":
                        self.custom_building_refresh_runtime_maps()
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
                    saved, self.state.message = save_custom_content(content)
                    if saved and field_name == "building_templates":
                        self.custom_building_refresh_runtime_maps()

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
            "- A world affinity lets the ability ignite, freeze, soak, grow, clear, bridge, or purify terrain outside combat.",
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
            "- Create procedural town/city interiors for every generated building type, including markets and sheriff offices.",
            "- Choose Edit existing game maps to open any authored or procedural layout directly on the canvas.",
            "- Saved built-in edits replace that exact game layout; Restore Original removes the override safely.",
            "- New templates start with a cursor-drawn boundary and then open directly on the same free-drawing canvas.",
            "- Mouse editing supports click-drag rectangles, continuous fixture/color strokes, right-drag erasing, and wheel brush selection; keyboard controls remain available.",
            "- Fixture and color tools support undo/redo, flood fill, straight lines, filled rectangles, and eyedropper sampling.",
            "- Rectangular fixture selections can be copied, cut, pasted, mirrored, rotated, or pasted transparently without replacing existing tiles with blank space.",
            "- A selected fixture area can be moved in one undoable operation, and the room-kit library loads furnished bedrooms, kitchens, shops, offices, libraries, and halls into the clipboard.",
            "- Clipboard paste and selection movement use a movable ghost preview; clean cells are highlighted separately from overwritten fixtures, and edge clipping is counted before placement.",
            "- The kit library also provides bedroom, bunk-room, reading, living-room, dining, storage, clinic, shop, and workshop furnishing arrangements without automatically changing zones.",
            "- Room shell drawing creates a clean walled room from one rectangle; replace-all quickly exchanges every matching fixture on a floor.",
            "- Smart Door chooses the correct horizontal or vertical room-door glyph from surrounding floor access; ground floors can also place an explicit exterior exit.",
            "- Optional canvas overlays show functional-zone edges, NPC spawn points, and paint colors while fixtures are edited.",
            "- Fixture brushes are grouped by architecture, services, furniture, displays, games, and erasing instead of one oversized list.",
            "- The furnishing catalog includes distinct beds, seating, bookcases, cabinets, shelves, chests, crates, barrels, dressers, pantry cupboards, nightstands, and display cases.",
            "- Container furnishings remain functional in generated interiors, with contents and ownership rules suited to homes, shops, clinics, inns, libraries, workshops, and civic buildings.",
            "- Existing zones and spawn points can be changed or moved; floors can be renamed or duplicated with their metadata.",
            "- Whole floors can be mirrored or rotated together with their zones, spawn points, and color marks.",
            "- The stair-link assistant places a matched up/down pair at the same walkable coordinate on neighboring floors.",
            "- Readiness review reports disconnected rooms, unusable zones/spawns, and missing schedule designations before saving.",
            "- Existing starting-town, farmhouse, residence, and procedural maps can be edited in place without creating copy records.",
            "- Enabled templates join the matching building-type pool; missing essentials such as doors and service counters are repaired safely.",
            "- Procedural Pool Weight controls how often an enabled custom template is selected relative to other custom templates of its type.",
            "- Max occupancy can change how many generated residents the chosen building can house.",
            "",
            "Files",
            f"- Active library: {CUSTOM_CONTENT_PATH}",
            f"- Share/import file: {CUSTOM_CONTENT_EXPORT_PATH}",
            "- Export creates a human-readable JSON file that another player can place at the import path.",
            "- Import replaces the active custom library only after confirmation.",
            "- Built-in source definitions remain recoverable through Restore Original even after a map is edited.",
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
