#!/usr/bin/env python3
"""Public launcher for Elsewhere: an ASCII Life-Sim RPG."""

import sys

if sys.version_info < (3, 11):
    raise SystemExit("Elsewhere requires Python 3.11 or later.")

from ascii_farmstead_support import (
    GAME_DATA_DIRECTORY,
    GAME_DISPLAY_TITLE,
)
from ascii_farmstead_v154_item_alias_fixes import main


def run_self_check() -> int:
    from ascii_farmstead_custom_content import load_custom_content
    from ascii_farmstead_v154_item_alias_fixes import FarmGame
    from ascii_battle_prototype.combat.game import Game as BattleGame
    from ascii_battle_prototype.combat.validation import validate_all_content

    GAME_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    probe = GAME_DATA_DIRECTORY / ".elsewhere-write-test.tmp"
    try:
        probe.write_text("Elsewhere self-check\n", encoding="utf-8")
        probe.unlink()
    finally:
        probe.unlink(missing_ok=True)

    farm = FarmGame()
    if not farm.active_map() or not farm.tutorial_catalog():
        raise RuntimeError("Farmstead content did not initialize.")
    custom_content, custom_warnings = load_custom_content()
    battle = BattleGame()
    report = validate_all_content(battle)
    if not report.ok:
        errors = [
            f"{issue.code}: {issue.message}"
            for issue in report.issues
            if issue.severity == "error"
        ]
        raise RuntimeError("Combat validation failed: " + "; ".join(errors[:5]))
    custom_total = sum(
        len(custom_content.get(field, []))
        for field in ("abilities", "classes", "enemies", "equipment", "maps", "dungeon_rooms")
    )
    print("Elsewhere self-check passed.")
    print(f"Data directory: {GAME_DATA_DIRECTORY}")
    print(f"Custom content records: {custom_total}")
    for warning in custom_warnings:
        print(f"Custom content: {warning}")
    return 0


if __name__ == "__main__":
    if "--version" in sys.argv:
        print(GAME_DISPLAY_TITLE)
    elif "--data-dir" in sys.argv:
        print(GAME_DATA_DIRECTORY)
    elif "--self-check" in sys.argv:
        raise SystemExit(run_self_check())
    else:
        main()
