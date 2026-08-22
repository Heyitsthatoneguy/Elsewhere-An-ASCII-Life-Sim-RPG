from __future__ import annotations

from typing import Dict, Iterable, List, Set

from .models import Pos, Unit, Weapon


def create_enemy_templates(start_positions: Dict[str, Pos]) -> List[Unit]:
    templates = [
        # Tutorial target: stationary and harmless.
        Unit("Training Dummy", "d", start_positions.get("Training Dummy", (14, 7)), 30, 30, 0, 0, 0, Weapon("Padded Post", 0), "enemy",
             role="dummy", cooldowns={}),
        # Skirmisher: annoying, mobile, lower damage.
        Unit("Crow", "c", start_positions.get("Crow", (16, 1)), 18, 18, 0, 0, 6, Weapon("Claw", 3), "enemy",
             role="skirmisher", cooldowns={"Poison Claw": 0, "Evasive Hop": 0}),

        # Brute: battlefield anchor. High HP, scary cooldowns, slow pressure.
        Unit("Boar", "b", start_positions.get("Boar", (15, 8)), 34, 34, 0, 0, 4, Weapon("Tusk Rush", 5), "enemy",
             role="brute", cooldowns={"Brutal Charge": 1, "War Cry": 0}),

        # Controller: lower HP, creates bad positions instead of raw damage.
        Unit("Vine", "v", start_positions.get("Vine", (9, 5)), 24, 24, 0, 0, 2, Weapon("Barbed Lash", 4, 1, 3), "enemy",
             role="controller", cooldowns={"Binding Roots": 1, "Toxic Burst": 2}),

        # New natural/wilderness enemies.
        Unit("Slime", "s", start_positions.get("Slime", (17, 3)), 22, 22, 0, 0, 2, Weapon("Acid Bump", 3), "enemy",
             role="blighter", cooldowns={"Poison Claw": 0, "Ooze Mire": 1}),
        Unit("Wolf", "w", start_positions.get("Wolf", (16, 4)), 20, 20, 0, 0, 6, Weapon("Fang", 4), "enemy",
             role="pouncer", cooldowns={"Evasive Hop": 0}),
        Unit("Bandit", "r", start_positions.get("Bandit", (17, 2)), 22, 22, 0, 0, 4, Weapon("Shortbow", 4, 2, 5), "enemy",
             role="ranged", cooldowns={"Evasive Hop": 0}),
        Unit("Shield Guard", "g", start_positions.get("Shield Guard", (15, 6)), 30, 30, 0, 0, 3, Weapon("Shield Bash", 4), "enemy",
             role="guardian", cooldowns={"War Cry": 0, "Shield Wall": 1}),
        Unit("Sporeling", "p", start_positions.get("Sporeling", (14, 4)), 18, 18, 0, 0, 3, Weapon("Spore Tap", 2, 1, 3), "enemy",
             role="controller", cooldowns={"Binding Roots": 0, "Toxic Burst": 1}),
        Unit("Wisp", "i", start_positions.get("Wisp", (17, 5)), 16, 16, 0, 0, 5, Weapon("Frost Spark", 4, 1, 4), "enemy",
             role="ranged", cooldowns={"Evasive Hop": 0, "Phase Shot": 1}),
        Unit("Rockback", "k", start_positions.get("Rockback", (15, 4)), 42, 42, 0, 0, 2, Weapon("Stone Slam", 6), "enemy",
             role="brute", cooldowns={"Brutal Charge": 2, "War Cry": 0, "Shield Wall": 2}),
        Unit("Marsh Toad", "t", start_positions.get("Marsh Toad", (16, 7)), 26, 26, 0, 0, 3, Weapon("Tongue Lash", 3, 1, 3), "enemy",
             role="blighter", cooldowns={"Poison Claw": 0, "Evasive Hop": 0, "Ooze Mire": 1}),
        Unit("Razor Hare", "h", start_positions.get("Razor Hare", (17, 4)), 16, 16, 0, 0, 7, Weapon("Needle Kick", 3), "enemy",
             role="pouncer", cooldowns={"Needle Dash": 0, "Evasive Hop": 0}),
        Unit("Ember Imp", "e", start_positions.get("Ember Imp", (17, 3)), 20, 20, 0, 0, 4, Weapon("Ember Flick", 3, 2, 4), "enemy",
             role="ranged", cooldowns={"Cinder Toss": 1, "Evasive Hop": 0}),
        Unit("Frost Moth", "f", start_positions.get("Frost Moth", (16, 3)), 18, 18, 0, 0, 5, Weapon("Chill Dust", 2, 1, 4), "enemy",
             role="controller", cooldowns={"Frost Cloud": 1, "Binding Roots": 2}),
        Unit("Crystal Spider", "c", start_positions.get("Crystal Spider", (16, 5)), 22, 22, 0, 0, 6, Weapon("Glass Bite", 4), "enemy",
             role="pouncer", cooldowns={"Needle Dash": 1, "Phase Shot": 2, "Evasive Hop": 0}),
        Unit("Cave Lynx", "l", start_positions.get("Cave Lynx", (17, 6)), 26, 26, 0, 0, 6, Weapon("Hooking Claw", 5), "enemy",
             role="skirmisher", cooldowns={"Harrier Dive": 1, "Evasive Hop": 0}),
        Unit("Gloomcap", "g", start_positions.get("Gloomcap", (14, 5)), 30, 30, 0, 0, 2, Weapon("Heavy Spores", 3, 1, 3), "enemy",
             role="blighter", cooldowns={"Spore Patch": 1, "Ooze Mire": 2, "Toxic Burst": 2}),
        Unit("Burrower", "u", start_positions.get("Burrower", (15, 5)), 28, 28, 0, 0, 3, Weapon("Tunnel Claw", 5), "enemy",
             role="brute", cooldowns={"Burrow Ambush": 1, "War Cry": 1}),
        Unit("Thornback", "q", start_positions.get("Thornback", (15, 6)), 32, 32, 0, 0, 3, Weapon("Quill Bash", 4, 1, 2), "enemy",
             role="guardian", cooldowns={"Quill Volley": 1, "War Cry": 0, "Shield Wall": 2}),
        # Ruin/dungeon enemies used by wilderness dungeons.
        Unit("Dustling", "d", start_positions.get("Dustling", (16, 4)), 18, 18, 0, 0, 5, Weapon("Dust Bite", 3), "enemy",
             role="blighter", cooldowns={"Ooze Mire": 1, "Evasive Hop": 0}),
        Unit("Ruin Bat", "a", start_positions.get("Ruin Bat", (17, 3)), 16, 16, 0, 0, 7, Weapon("Wing Slash", 3), "enemy",
             role="pouncer", cooldowns={"Needle Dash": 1, "Evasive Hop": 0}),
        Unit("Moss Haunt", "m", start_positions.get("Moss Haunt", (15, 5)), 24, 24, 0, 0, 3, Weapon("Moss Grip", 4, 1, 3), "enemy",
             role="controller", cooldowns={"Binding Roots": 0, "Toxic Burst": 2}),
        Unit("Shardling", "j", start_positions.get("Shardling", (17, 4)), 20, 20, 0, 0, 5, Weapon("Shard Flick", 4, 1, 4), "enemy",
             role="ranged", cooldowns={"Phase Shot": 1, "Evasive Hop": 0}),
        Unit("Clockwork Beetle", "b", start_positions.get("Clockwork Beetle", (14, 6)), 34, 34, 0, 0, 3, Weapon("Gear Mandibles", 5), "enemy",
             role="guardian", cooldowns={"Shield Wall": 1, "War Cry": 1}),
        Unit("Relic Archer", "r", start_positions.get("Relic Archer", (17, 5)), 24, 24, 0, 0, 4, Weapon("Crystal Arrow", 5, 2, 6), "enemy",
             role="ranged", cooldowns={"Phase Shot": 1, "Evasive Hop": 0}),
        Unit("Hollow Sentinel", "n", start_positions.get("Hollow Sentinel", (15, 6)), 40, 40, 0, 0, 2, Weapon("Relic Halberd", 6, 1, 2), "enemy",
             role="guardian", cooldowns={"Shield Wall": 1, "War Cry": 0}),
        # Boss: test-only by default. Add from Encounter Maker.
        Unit("Old Briarthorn", "O", start_positions.get("Old Briarthorn", (15, 5)), 72, 72, 0, 0, 2, Weapon("Briar Maul", 7, 1, 3), "enemy",
             role="boss", cooldowns={"Binding Roots": 0, "Toxic Burst": 1, "War Cry": 0, "Briar Heart": 0}, boss=True),
    ]
    try:
        from ascii_farmstead_custom_extended import create_custom_enemy_templates

        templates.extend(
            create_custom_enemy_templates(
                start_positions,
                existing_names=(enemy.name for enemy in templates),
            )
        )
    except (ImportError, OSError, TypeError, ValueError):
        pass
    return templates



def expand_enemy_roster(base_enemies: Iterable[Unit], enemy_max_count: int = 5, boss_enemy_names: Set[str] | None = None) -> List[Unit]:
    base_enemies = list(base_enemies)
    boss_enemy_names = set(boss_enemy_names or {enemy.name for enemy in base_enemies if enemy.role == "boss" or enemy.boss})
    expanded_enemies: List[Unit] = []
    for template in base_enemies:
        normal_max = 1 if template.name in boss_enemy_names else enemy_max_count

        for copy_index in range(1, normal_max + 1):
            copy_name = template.name if copy_index == 1 else f"{template.name} {copy_index}"
            expanded_enemies.append(
                Unit(
                    copy_name,
                    template.glyph,
                    template.pos,
                    template.max_hp,
                    template.max_hp,
                    template.max_mp,
                    template.max_mp,
                    template.move_range,
                    Weapon(template.weapon.name, template.weapon.damage, template.weapon.range_min, template.weapon.range_max),
                    template.team,
                    ai_controlled=template.ai_controlled,
                    role=template.role,
                    cooldowns=dict(template.cooldowns),
                    inventory=dict(template.inventory),
                    boss=template.name in boss_enemy_names,
                    defense=template.defense,
                )
            )

        if template.name in boss_enemy_names:
            continue

        for copy_index in range(1, enemy_max_count + 1):
            copy_name = f"Elite {template.name}" if copy_index == 1 else f"Elite {template.name} {copy_index}"
            elite_hp = int(template.max_hp * 1.5)
            expanded_enemies.append(
                Unit(
                    copy_name,
                    template.glyph.upper(),
                    template.pos,
                    elite_hp,
                    elite_hp,
                    template.max_mp,
                    template.max_mp,
                    template.move_range,
                    Weapon("Elite " + template.weapon.name, template.weapon.damage + 2, template.weapon.range_min, template.weapon.range_max),
                    template.team,
                    ai_controlled=template.ai_controlled,
                    role=template.role,
                    cooldowns=dict(template.cooldowns),
                    inventory=dict(template.inventory),
                    elite=True,
                    defense=template.defense + 1,
                )
            )
    return expanded_enemies


def enemy_loadout_for_map(map_name: str) -> List[str]:
    """Theme each arena with a distinct non-cult enemy mix."""
    loadouts = {
        "Training Yard": ["Training Dummy", "Slime"],
        "Advanced Training Yard": ["Training Dummy", "Shield Guard", "Frost Moth", "Razor Hare"],
        "Riverwatch Ford": ["Crow", "Boar", "Slime", "Razor Hare"],
        "Stonewater Crossing": ["Bandit", "Shield Guard", "Marsh Toad", "Ember Imp"],
        "Broken Gate Ruins": ["Wisp", "Rockback", "Frost Moth", "Crystal Spider"],
        "Twinlane Grove": ["Wolf", "Sporeling", "Vine", "Razor Hare"],
        "Spring Bloomfield": ["Slime", "Sporeling", "Wolf", "Thornback"],
        "Highsummer Channel": ["Bandit", "Ember Imp", "Marsh Toad", "Crow"],
        "Amber Harvest": ["Wolf", "Boar", "Thornback", "Razor Hare"],
        "Frostpine Crossing": ["Wisp", "Rockback", "Frost Moth", "Wolf"],
        "Moonlit Quarry": ["Cave Lynx", "Burrower", "Shield Guard", "Rockback", "Wisp"],
        "Flooded Causeway": ["Marsh Toad", "Frost Moth", "Gloomcap", "Shield Guard", "Sporeling"],
        "Briarfall Basin": ["Vine", "Gloomcap", "Thornback", "Razor Hare", "Marsh Toad"],
        "Emberglass Works": ["Ember Imp", "Shield Guard", "Rockback", "Burrower", "Crystal Spider"],
        "Snowmelt Terrace": ["Frost Moth", "Rockback", "Gloomcap", "Razor Hare", "Thornback"],
        "Gatehouse Bastion": ["Shield Guard", "Bandit", "Ember Imp", "Thornback", "Burrower"],
        "Inner Bailey Keep": ["Shield Guard", "Bandit", "Thornback", "Razor Hare", "Burrower"],
        "Rampart Arsenal": ["Bandit", "Ember Imp", "Shield Guard", "Burrower", "Thornback"],
        "Floodgate Citadel": ["Marsh Toad", "Frost Moth", "Wisp", "Clockwork Beetle", "Burrower"],
        "Frostwall Redoubt": ["Frost Moth", "Rockback", "Relic Archer", "Thornback", "Crystal Spider"],
    }
    try:
        from ascii_farmstead_custom_extended import custom_map_loadout

        custom = custom_map_loadout(map_name)
        if custom:
            return custom
    except (ImportError, OSError, TypeError, ValueError):
        pass
    return loadouts.get(map_name, ["Crow", "Boar", "Vine"])

