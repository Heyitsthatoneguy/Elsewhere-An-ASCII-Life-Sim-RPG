from __future__ import annotations

from typing import Dict


_VALID_SKILL_NAMES_CACHE = None
_CLASS_DEFS_CACHE = None


def invalidate_class_defs_cache() -> None:
    global _CLASS_DEFS_CACHE
    _CLASS_DEFS_CACHE = None


def class_defs() -> Dict[str, Dict[str, object]]:
    global _CLASS_DEFS_CACHE
    if _CLASS_DEFS_CACHE is not None:
        return _CLASS_DEFS_CACHE
    definitions = {
        "Vanguard": {
            "desc": "Frontline commander: command support, guard setup, vulnerable targets, and lane-breaking pressure.",
            "default": ["Spark Shot", "Battle Standard", "Coordinate"],
            "mastery": "Rallying Breaker",
            "tree": [
                ("Guarding Call", 1, "Protect an ally without using their AP."),
                ("Commander's Challenge", 1, "Expose a priority target for party follow-up."),
                ("Breaker Strike", 1, "Close-range vulnerable setup for elites/bosses."),
                ("Opening Command", 1, "Combo attack that refunds AP against vulnerable targets."),
                ("Shield Rush", 2, "Guard combo that roots and hits harder while guarding."),
                ("Linebreaker", 2, "Root enemies through a lane."),
                ("Cinder Sweep", 2, "Wide cone for chokepoints."),
            ],
            "prereqs": {
                "Opening Command": ["Commander's Challenge", "Breaker Strike"],
                "Shield Rush": ["Guarding Call"],
                "Linebreaker": ["Shield Rush"],
                "Cinder Sweep": ["Linebreaker"],
            },
        },
        "Ranger": {
            "desc": "Ranged controller: traps, marks, roots, poison detonations, and precision volleys.",
            "default": ["Spark Shot", "Venom Dart", "Marking Shot"],
            "mastery": "Arrowstorm",
            "tree": [
                ("Snare Trap", 1, "Root clustered enemies and leave a snare zone."),
                ("Pinning Line", 1, "Root enemies in a lane."),
                ("Predator Shot", 1, "Finisher that hits statused enemies harder."),
                ("Venom Detonator", 1, "Poison combo burst that makes enemies vulnerable."),
                ("Hailshot", 2, "Multishot volley that exposes survivors."),
                ("Shatter Shot", 1, "Detonate barrels and pressure clusters."),
                ("Piercing Line", 2, "Reliable long lane damage."),
            ],
            "prereqs": {
                "Pinning Line": ["Snare Trap"],
                "Predator Shot": ["Pinning Line"],
                "Venom Detonator": ["Predator Shot"],
                "Hailshot": ["Predator Shot"],
                "Piercing Line": ["Pinning Line"],
            },
        },
        "Guardian": {
            "desc": "Tank-support controller: guard, cleanse, guarded healing, roots, and durable frontline pressure.",
            "default": ["Spark Shot", "Field Aid", "Guarding Call"],
            "mastery": "Last Bastion",
            "tree": [
                ("Cleanse Pulse", 1, "Remove poison/root/vulnerable from one ally."),
                ("Aegis Mend", 1, "Strong heal that improves on guarded allies."),
                ("Bulwark Mend", 1, "Efficient guarded-ally combo heal."),
                ("Thorn Snare", 1, "Cross-shaped root for terrain control."),
                ("Warden's Grasp", 2, "Root enemies and leave rough earth."),
                ("Sentinel Bash", 2, "Guard combo bash that roots the enemy."),
                ("Stonebreak", 2, "Heavy impact for tough enemies."),
            ],
            "prereqs": {
                "Aegis Mend": ["Cleanse Pulse"],
                "Bulwark Mend": ["Aegis Mend"],
                "Warden's Grasp": ["Thorn Snare"],
                "Sentinel Bash": ["Bulwark Mend"],
                "Stonebreak": ["Warden's Grasp"],
            },
        },
        "Mystic": {
            "desc": "Elemental caster: fire/frost/storm zones, MP support, status combos, and large finishers.",
            "default": ["Spark Shot", "Mana Channel", "Runic Flare"],
            "mastery": "Starfall",
            "tree": [
                ("Runic Flare", 1, "Fire burst that leaves a burning zone."),
                ("Rime Field", 1, "Frost burst that roots and leaves a frost zone."),
                ("Storm Seal", 1, "Storm burst that exposes enemies and leaves a static zone."),
                ("Arcane Echo", 1, "Status combo attack that restores MP."),
                ("Conductive Burst", 2, "Burst that hits rooted enemies harder."),
                ("Toxic Cloud", 2, "Poison grouped enemies."),
                ("Meteor Volley", 3, "Expensive large-area finisher."),
            ],
            "prereqs": {
                "Arcane Echo": ["Storm Seal"],
                "Conductive Burst": ["Rime Field"],
                "Toxic Cloud": ["Runic Flare"],
                "Meteor Volley": ["Conductive Burst", "Runic Flare"],
            },
        },
        "Duelist": {
            "desc": "Mobile striker: feints, guarded ripostes, single-target pressure, and elegant finishers.",
            "default": ["Spark Shot", "Lunge", "Feint"],
            "mastery": "Grand Flourish",
            "tree": [
                ("Disarming Feint", 1, "Longer vulnerable setup for priority targets."),
                ("Riposte", 1, "Guard combo strike for duel turns."),
                ("Cross Cut", 1, "Close cross slash for clustered melee fights."),
                ("Finisher Thrust", 2, "Status finisher with high single-target payoff."),
                ("Flash Step", 2, "Guard an ally before a dangerous exchange."),
                ("Blade Waltz", 3, "Multihit finisher for crowded fights."),
            ],
            "prereqs": {"Riposte": ["Disarming Feint"], "Finisher Thrust": ["Riposte"], "Flash Step": ["Disarming Feint"], "Blade Waltz": ["Cross Cut"]},
        },
        "Alchemist": {
            "desc": "Battlefield utility: poison, root, smoke, cleanse, MP support, and explosive flask combos.",
            "default": ["Spark Shot", "Acid Flask", "Field Aid"],
            "mastery": "Magnum Opus",
            "tree": [
                ("Rooting Resin", 1, "Root enemies with a sticky control flask."),
                ("Smoke Bomb", 1, "Cone setup that makes enemies vulnerable."),
                ("Catalyst Brew", 1, "Restore MP to keep skill-heavy allies active."),
                ("Panacea", 1, "Cleanse status effects from one ally."),
                ("Volatile Flask", 2, "Burst that punishes poisoned enemies."),
                ("Philosopher Flask", 3, "Wide poison burst for grouped enemies."),
            ],
            "prereqs": {"Volatile Flask": ["Rooting Resin"], "Philosopher Flask": ["Volatile Flask"], "Panacea": ["Catalyst Brew"], "Smoke Bomb": ["Rooting Resin"]},
        },
    }
    try:
        from ascii_farmstead_custom_content import custom_ability_records, custom_class_defs
        from .skills import create_default_skills

        global _VALID_SKILL_NAMES_CACHE
        custom_records = custom_ability_records()
        current_custom_names = {
            str(record.get("name", "")).casefold()
            for record in custom_records
            if str(record.get("name", ""))
        }
        if _VALID_SKILL_NAMES_CACHE is None:
            _VALID_SKILL_NAMES_CACHE = tuple(
                skill.name
                for skill in create_default_skills()
                if skill.name.casefold() not in current_custom_names
            )
        valid_skill_names = list(_VALID_SKILL_NAMES_CACHE)
        valid_skill_names.extend(
            str(record.get("name", ""))
            for record in custom_records
            if str(record.get("name", ""))
        )
        definitions.update(
            custom_class_defs(
                existing_class_names=definitions,
                valid_skill_names=valid_skill_names,
            )
        )
    except (ImportError, OSError, ValueError, TypeError):
        # Built-in classes remain available if optional custom content cannot
        # be loaded.
        pass
    _CLASS_DEFS_CACHE = definitions
    return definitions

