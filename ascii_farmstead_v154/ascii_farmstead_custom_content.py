from __future__ import annotations

import json
import copy
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ascii_farmstead_support import GAME_DATA_DIRECTORY
from ascii_battle_prototype.combat.models import Skill


CUSTOM_CONTENT_VERSION = 1
CUSTOM_CONTENT_BACKUP_COUNT = 3
CUSTOM_CONTENT_PATH = GAME_DATA_DIRECTORY / "custom_content.json"
CUSTOM_CONTENT_EXPORT_PATH = GAME_DATA_DIRECTORY / "custom_content_export.json"

ABILITY_EFFECTS = ("damage", "heal", "guard", "cleanse", "restore_mp")
ABILITY_SHAPES = ("point", "burst", "strip", "cone", "cross", "multishot")
ABILITY_STATUSES = ("", "poison", "root", "vulnerable")
ABILITY_ZONES = ("", "fire", "frost", "storm", "earth", "poison", "light", "shadow")
ELEMENTS = ("Fire", "Frost", "Storm", "Earth", "Poison", "Light", "Shadow")

_CONTENT_CACHE_PATH: Optional[Path] = None
_CONTENT_CACHE_SIGNATURE: Optional[Tuple[int, int]] = None
_CONTENT_CACHE_VALUE: Optional[Dict[str, object]] = None


def invalidate_custom_content_cache() -> None:
    global _CONTENT_CACHE_PATH, _CONTENT_CACHE_SIGNATURE, _CONTENT_CACHE_VALUE
    _CONTENT_CACHE_PATH = None
    _CONTENT_CACHE_SIGNATURE = None
    _CONTENT_CACHE_VALUE = None
    try:
        from ascii_battle_prototype.combat.classes import invalidate_class_defs_cache

        invalidate_class_defs_cache()
    except ImportError:
        pass
    try:
        from ascii_battle_prototype.combat.equipment import invalidate_equipment_defs_cache

        invalidate_equipment_defs_cache()
    except ImportError:
        pass


def empty_custom_content() -> Dict[str, object]:
    return {
        "version": CUSTOM_CONTENT_VERSION,
        "abilities": [],
        "classes": [],
        "enemies": [],
        "equipment": [],
        "maps": [],
        "dungeon_rooms": [],
    }


def custom_content_backup_path(path: Path, number: int) -> Path:
    number = max(1, int(number))
    return path.with_name(f"{path.stem}.backup{number}{path.suffix}")


def custom_content_backup_paths(path: Path) -> List[Path]:
    return [
        custom_content_backup_path(path, number)
        for number in range(1, CUSTOM_CONTENT_BACKUP_COUNT + 1)
    ]


def legacy_custom_content_backup_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".backup")


def atomic_write_custom_content(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def rotate_custom_content_backups(path: Path) -> None:
    if not path.exists():
        return
    oldest = custom_content_backup_path(path, CUSTOM_CONTENT_BACKUP_COUNT)
    oldest.unlink(missing_ok=True)
    for number in range(CUSTOM_CONTENT_BACKUP_COUNT, 1, -1):
        source = custom_content_backup_path(path, number - 1)
        if source.exists():
            os.replace(source, custom_content_backup_path(path, number))
    first = custom_content_backup_path(path, 1)
    temporary = first.with_name(f"{first.name}.tmp")
    try:
        shutil.copy2(path, temporary)
        os.replace(temporary, first)
    finally:
        temporary.unlink(missing_ok=True)


def quarantine_broken_custom_content(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.stem}.broken-{timestamp}{path.suffix}")
    counter = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}.broken-{timestamp}-{counter}{path.suffix}")
        counter += 1
    path.replace(candidate)
    return candidate


def _read_custom_content_document(path: Path) -> Tuple[Dict[str, object], bool]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    clean = sanitize_custom_content(raw)
    return clean, clean != raw


def _clean_text(value: object, max_length: int) -> str:
    return " ".join(str(value or "").strip().split())[:max_length]


def _clean_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _clean_name_list(value: object, maximum: int) -> List[str]:
    if not isinstance(value, (list, tuple)):
        return []
    names: List[str] = []
    seen = set()
    for raw_name in value:
        name = _clean_text(raw_name, 24)
        key = name.casefold()
        if not name or key in seen:
            continue
        names.append(name)
        seen.add(key)
        if len(names) >= maximum:
            break
    return names


def sanitize_custom_ability(raw: object) -> Optional[Dict[str, object]]:
    if not isinstance(raw, dict):
        return None
    name = _clean_text(raw.get("name"), 24)
    if not name:
        return None
    effect = str(raw.get("effect", "damage") or "damage")
    if effect not in ABILITY_EFFECTS:
        effect = "damage"
    shape = str(raw.get("shape", "point") or "point")
    if shape not in ABILITY_SHAPES:
        shape = "point"
    status = str(raw.get("status", "") or "")
    if status not in ABILITY_STATUSES:
        status = ""
    zone_type = str(raw.get("zone_type", "") or "")
    if zone_type not in ABILITY_ZONES:
        zone_type = ""
    zone_status = str(raw.get("zone_status", "") or "")
    if zone_status not in ABILITY_STATUSES:
        zone_status = ""

    ability: Dict[str, object] = {
        "name": name,
        "description": _clean_text(raw.get("description"), 180) or "A custom combat ability.",
        "effect": effect,
        "mp_cost": _clean_int(raw.get("mp_cost"), 4, 0, 12),
        "damage": _clean_int(raw.get("damage"), 0, 0, 14),
        "range_max": _clean_int(raw.get("range_max"), 4, 1, 8),
        "shape": shape,
        "aoe_radius": _clean_int(raw.get("aoe_radius"), 0, 0, 2),
        "width": _clean_int(raw.get("width"), 1, 1, 3),
        "shots": _clean_int(raw.get("shots"), 1, 1, 6),
        "status": status,
        "status_duration": _clean_int(raw.get("status_duration"), 0, 0, 3),
        "heal_amount": _clean_int(raw.get("heal_amount"), 0, 0, 16),
        "mp_amount": _clean_int(raw.get("mp_amount"), 0, 0, 10),
        "zone_type": zone_type,
        "zone_duration": _clean_int(raw.get("zone_duration"), 0, 0, 3),
        "zone_damage": _clean_int(raw.get("zone_damage"), 0, 0, 3),
        "zone_status": zone_status,
        "zone_status_duration": _clean_int(raw.get("zone_status_duration"), 0, 0, 3),
    }

    if effect != "damage":
        ability.update({
            "damage": 0,
            "shape": "point",
            "aoe_radius": 0,
            "width": 1,
            "shots": 1,
            "status": "",
            "status_duration": 0,
            "zone_type": "",
            "zone_duration": 0,
            "zone_damage": 0,
            "zone_status": "",
            "zone_status_duration": 0,
        })
        ability["range_max"] = 8
    if effect != "heal":
        ability["heal_amount"] = 0
    if effect != "restore_mp":
        ability["mp_amount"] = 0
    if effect == "damage" and int(ability["damage"]) <= 0:
        ability["damage"] = 1
    if status and int(ability["status_duration"]) <= 0:
        ability["status_duration"] = 1
    if not zone_type:
        ability["zone_duration"] = 0
        ability["zone_damage"] = 0
        ability["zone_status"] = ""
        ability["zone_status_duration"] = 0
    elif int(ability["zone_duration"]) <= 0:
        ability["zone_duration"] = 1
    if zone_status and int(ability["zone_status_duration"]) <= 0:
        ability["zone_status_duration"] = 1
    return ability


def sanitize_custom_class(raw: object) -> Optional[Dict[str, object]]:
    if not isinstance(raw, dict):
        return None
    name = _clean_text(raw.get("name"), 24)
    if not name:
        return None
    progression_raw = raw.get("progression_abilities", [])
    progression: List[Dict[str, object]] = []
    seen = set()
    if isinstance(progression_raw, (list, tuple)):
        for index, entry in enumerate(progression_raw):
            if isinstance(entry, dict):
                ability_name = _clean_text(entry.get("name"), 24)
                cost = _clean_int(entry.get("cost"), 1 + index // 2, 1, 3)
            else:
                ability_name = _clean_text(entry, 24)
                cost = _clean_int(1 + index // 2, 1, 1, 3)
            key = ability_name.casefold()
            if not ability_name or key in seen:
                continue
            progression.append({"name": ability_name, "cost": cost})
            seen.add(key)
            if len(progression) >= 6:
                break
    elements = [
        element
        for element in _clean_name_list(raw.get("recommended_elements"), 4)
        if element in ELEMENTS
    ]
    return {
        "name": name,
        "description": _clean_text(raw.get("description"), 220) or "A custom combat class.",
        "default_abilities": _clean_name_list(raw.get("default_abilities"), 3),
        "progression_abilities": progression,
        "mastery_ability": _clean_text(raw.get("mastery_ability"), 24),
        "recommended_elements": elements,
    }


def sanitize_custom_content(raw: object) -> Dict[str, object]:
    from ascii_farmstead_custom_extended import (
        sanitize_custom_dungeon_room,
        sanitize_custom_enemy,
        sanitize_custom_equipment,
        sanitize_custom_map,
    )

    clean = empty_custom_content()
    if not isinstance(raw, dict):
        return clean
    ability_names = set()
    for raw_ability in raw.get("abilities", []) if isinstance(raw.get("abilities"), list) else []:
        ability = sanitize_custom_ability(raw_ability)
        if ability is None or str(ability["name"]).casefold() in ability_names:
            continue
        clean["abilities"].append(ability)
        ability_names.add(str(ability["name"]).casefold())
    class_names = set()
    for raw_class in raw.get("classes", []) if isinstance(raw.get("classes"), list) else []:
        class_record = sanitize_custom_class(raw_class)
        if class_record is None or str(class_record["name"]).casefold() in class_names:
            continue
        clean["classes"].append(class_record)
        class_names.add(str(class_record["name"]).casefold())
    for field_name, sanitizer in (
        ("enemies", sanitize_custom_enemy),
        ("equipment", sanitize_custom_equipment),
        ("maps", sanitize_custom_map),
        ("dungeon_rooms", sanitize_custom_dungeon_room),
    ):
        names = set()
        values = raw.get(field_name, [])
        for raw_record in values if isinstance(values, list) else []:
            record = sanitizer(raw_record)
            if record is None or str(record["name"]).casefold() in names:
                continue
            clean[field_name].append(record)
            names.add(str(record["name"]).casefold())
    return clean


def load_custom_content(path: Optional[Path] = None) -> Tuple[Dict[str, object], List[str]]:
    path = path or CUSTOM_CONTENT_PATH
    global _CONTENT_CACHE_PATH, _CONTENT_CACHE_SIGNATURE, _CONTENT_CACHE_VALUE
    if path.exists():
        try:
            stat = path.stat()
            signature = (int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            signature = None
        if (
            signature is not None
            and _CONTENT_CACHE_PATH == path
            and _CONTENT_CACHE_SIGNATURE == signature
            and _CONTENT_CACHE_VALUE is not None
        ):
            return copy.deepcopy(_CONTENT_CACHE_VALUE), []
        try:
            clean, normalized = _read_custom_content_document(path)
            warnings = (
                ["Custom content contained invalid fields and was safely normalized."]
                if normalized
                else []
            )
            if signature is not None:
                _CONTENT_CACHE_PATH = path
                _CONTENT_CACHE_SIGNATURE = signature
                _CONTENT_CACHE_VALUE = copy.deepcopy(clean)
            return clean, warnings
        except (OSError, ValueError, TypeError):
            pass

    recovery_candidates = [
        *custom_content_backup_paths(path),
        legacy_custom_content_backup_path(path),
    ]
    for backup_path in recovery_candidates:
        if not backup_path.exists():
            continue
        try:
            clean, _normalized = _read_custom_content_document(backup_path)
            broken_path = quarantine_broken_custom_content(path) if path.exists() else None
            serialized = json.dumps(clean, indent=2, sort_keys=True) + "\n"
            atomic_write_custom_content(path, serialized)
            stat = path.stat()
            _CONTENT_CACHE_PATH = path
            _CONTENT_CACHE_SIGNATURE = (int(stat.st_mtime_ns), int(stat.st_size))
            _CONTENT_CACHE_VALUE = copy.deepcopy(clean)
            detail = f" Broken file preserved as {broken_path.name}." if broken_path else ""
            return clean, [f"Recovered custom content from {backup_path.name}.{detail}"]
        except (OSError, ValueError, TypeError):
            continue

    if path.exists():
        try:
            broken_path = quarantine_broken_custom_content(path)
            detail = f" Preserved as {broken_path.name}." if broken_path else ""
        except OSError:
            detail = ""
        invalidate_custom_content_cache()
        return empty_custom_content(), [f"Custom content was unreadable and no valid recovery copy was found.{detail}"]
    return empty_custom_content(), []


def save_custom_content(content: object, path: Optional[Path] = None) -> Tuple[bool, str]:
    path = path or CUSTOM_CONTENT_PATH
    clean = sanitize_custom_content(content)
    try:
        if path.exists():
            try:
                _read_custom_content_document(path)
                rotate_custom_content_backups(path)
            except (OSError, ValueError, TypeError):
                quarantine_broken_custom_content(path)
        serialized = json.dumps(clean, indent=2, sort_keys=True) + "\n"
        json.loads(serialized)
        atomic_write_custom_content(path, serialized)
        global _CONTENT_CACHE_PATH, _CONTENT_CACHE_SIGNATURE, _CONTENT_CACHE_VALUE
        stat = path.stat()
        _CONTENT_CACHE_PATH = path
        _CONTENT_CACHE_SIGNATURE = (int(stat.st_mtime_ns), int(stat.st_size))
        _CONTENT_CACHE_VALUE = copy.deepcopy(clean)
        try:
            from ascii_battle_prototype.combat.classes import invalidate_class_defs_cache

            invalidate_class_defs_cache()
        except ImportError:
            pass
        try:
            from ascii_battle_prototype.combat.equipment import invalidate_equipment_defs_cache

            invalidate_equipment_defs_cache()
        except ImportError:
            pass
        total = sum(
            len(clean[field])
            for field in ("abilities", "classes", "enemies", "equipment", "maps", "dungeon_rooms")
        )
        return True, f"Saved {total} custom content records."
    except (OSError, ValueError, TypeError) as exc:
        return False, f"Could not save custom content: {exc}"


def export_custom_content(content: object) -> Tuple[bool, str]:
    ok, message = save_custom_content(content, CUSTOM_CONTENT_EXPORT_PATH)
    if not ok:
        return False, message
    return True, f"Exported to {CUSTOM_CONTENT_EXPORT_PATH}."


def import_custom_content() -> Tuple[Optional[Dict[str, object]], str]:
    if not CUSTOM_CONTENT_EXPORT_PATH.exists():
        return None, f"No import file found at {CUSTOM_CONTENT_EXPORT_PATH}."
    content, warnings = load_custom_content(CUSTOM_CONTENT_EXPORT_PATH)
    suffix = f" {' '.join(warnings)}" if warnings else ""
    total = sum(
        len(content[field])
        for field in ("abilities", "classes", "enemies", "equipment", "maps", "dungeon_rooms")
    )
    return content, f"Imported {total} custom content records.{suffix}"


def custom_ability_records() -> List[Dict[str, object]]:
    content, _warnings = load_custom_content()
    return [dict(record) for record in content["abilities"] if isinstance(record, dict)]


def custom_class_records() -> List[Dict[str, object]]:
    content, _warnings = load_custom_content()
    return [dict(record) for record in content["classes"] if isinstance(record, dict)]


def ability_to_skill(record: Dict[str, object]) -> Skill:
    ability = sanitize_custom_ability(record) or sanitize_custom_ability({"name": "Custom Strike"})
    assert ability is not None
    effect = str(ability["effect"])
    return Skill(
        name=str(ability["name"]),
        mp_cost=int(ability["mp_cost"]),
        damage=int(ability["damage"]),
        range_max=99 if effect != "damage" else int(ability["range_max"]),
        aoe_radius=int(ability["aoe_radius"]),
        shape="support" if effect != "damage" else str(ability["shape"]),
        width=int(ability["width"]),
        shots=int(ability["shots"]),
        status=str(ability["status"]),
        status_duration=int(ability["status_duration"]),
        description=str(ability["description"]),
        effect=effect,
        heal_amount=int(ability["heal_amount"]),
        mp_amount=int(ability["mp_amount"]),
        target_team="ally" if effect != "damage" else "enemy",
        zone_type=str(ability["zone_type"]),
        zone_duration=int(ability["zone_duration"]),
        zone_damage=int(ability["zone_damage"]),
        zone_status=str(ability["zone_status"]),
        zone_status_duration=int(ability["zone_status_duration"]),
    )


def create_custom_skills(existing_names: Iterable[str] = ()) -> List[Skill]:
    reserved = {str(name).casefold() for name in existing_names}
    skills: List[Skill] = []
    for record in custom_ability_records():
        name = str(record.get("name", ""))
        if not name or name.casefold() in reserved:
            continue
        skill = ability_to_skill(record)
        skills.append(skill)
        reserved.add(skill.name.casefold())
    return skills


def custom_class_defs(
    existing_class_names: Iterable[str] = (),
    valid_skill_names: Iterable[str] = (),
) -> Dict[str, Dict[str, object]]:
    reserved_classes = {str(name).casefold() for name in existing_class_names}
    valid_skills = {str(name).casefold(): str(name) for name in valid_skill_names}
    definitions: Dict[str, Dict[str, object]] = {}
    for record in custom_class_records():
        name = str(record.get("name", ""))
        if not name or name.casefold() in reserved_classes:
            continue
        defaults = [
            valid_skills[ability.casefold()]
            for ability in record.get("default_abilities", [])
            if str(ability).casefold() in valid_skills
        ][:3]
        tree = []
        prereqs: Dict[str, List[str]] = {}
        previous = ""
        for entry in record.get("progression_abilities", []):
            if not isinstance(entry, dict):
                continue
            ability_name = valid_skills.get(str(entry.get("name", "")).casefold(), "")
            if not ability_name or ability_name in defaults or any(row[0] == ability_name for row in tree):
                continue
            tree.append((
                ability_name,
                _clean_int(entry.get("cost"), 1, 1, 3),
                f"Custom class ability: {ability_name}.",
            ))
            if previous:
                prereqs[ability_name] = [previous]
            previous = ability_name
        mastery = valid_skills.get(str(record.get("mastery_ability", "")).casefold(), "")
        if len(defaults) < 1 or len(tree) < 1:
            continue
        definitions[name] = {
            "desc": str(record.get("description", "A custom combat class.")),
            "default": defaults,
            "mastery": mastery,
            "tree": tree,
            "prereqs": prereqs,
            "recommended_elements": list(record.get("recommended_elements", [])),
            "custom": True,
        }
        reserved_classes.add(name.casefold())
    return definitions


def ability_balance_score(record: Dict[str, object]) -> int:
    ability = sanitize_custom_ability(record)
    if ability is None:
        return 0
    score = int(ability["damage"])
    score += int(ability["heal_amount"])
    score += int(ability["mp_amount"])
    score += int(ability["aoe_radius"]) * 3
    score += max(0, int(ability["shots"]) - 1) * 2
    score += max(0, int(ability["width"]) - 1)
    score += int(ability["status_duration"]) * (2 if ability["status"] else 0)
    score += int(ability["zone_duration"]) + int(ability["zone_damage"]) * 2
    score += int(ability["zone_status_duration"]) * (2 if ability["zone_status"] else 0)
    if ability["effect"] in {"guard", "cleanse"}:
        score += 7
    score -= int(ability["mp_cost"])
    return score


def ability_balance_label(record: Dict[str, object]) -> str:
    score = ability_balance_score(record)
    if score <= 5:
        return "Conservative"
    if score <= 10:
        return "Standard"
    if score <= 15:
        return "Strong"
    return "Very strong"


def ability_summary(record: Dict[str, object]) -> List[str]:
    ability = sanitize_custom_ability(record)
    if ability is None:
        return ["Invalid custom ability."]
    effect = str(ability["effect"])
    lines = [
        str(ability["name"]).upper(),
        "",
        str(ability["description"]),
        "",
        f"Effect: {effect.replace('_', ' ').title()}",
        f"MP cost: {ability['mp_cost']}",
        f"Balance estimate: {ability_balance_label(ability)}",
    ]
    if effect == "damage":
        lines.extend([
            f"Damage: {ability['damage']} | Range: {ability['range_max']}",
            f"Shape: {ability['shape']} | Radius: {ability['aoe_radius']} | Width: {ability['width']} | Shots: {ability['shots']}",
            f"Status: {ability['status'] or 'none'} ({ability['status_duration']} turns)",
            f"Zone: {ability['zone_type'] or 'none'} ({ability['zone_duration']} turns, {ability['zone_damage']} damage)",
            f"Zone status: {ability['zone_status'] or 'none'} ({ability['zone_status_duration']} turns)",
        ])
    elif effect == "heal":
        lines.append(f"Healing: {ability['heal_amount']}")
    elif effect == "restore_mp":
        lines.append(f"Focus restored: {ability['mp_amount']}")
    return lines


def class_summary(record: Dict[str, object]) -> List[str]:
    class_record = sanitize_custom_class(record)
    if class_record is None:
        return ["Invalid custom class."]
    progression = class_record["progression_abilities"]
    return [
        str(class_record["name"]).upper(),
        "",
        str(class_record["description"]),
        "",
        f"Starting abilities: {', '.join(class_record['default_abilities']) or 'none'}",
        f"Progression: {', '.join(str(entry['name']) for entry in progression) or 'none'}",
        f"Mastery: {class_record['mastery_ability'] or 'none'}",
        f"Recommended elements: {', '.join(class_record['recommended_elements']) or 'Any'}",
        "",
        "Progression abilities unlock in the listed order and can be ranked up normally.",
    ]
