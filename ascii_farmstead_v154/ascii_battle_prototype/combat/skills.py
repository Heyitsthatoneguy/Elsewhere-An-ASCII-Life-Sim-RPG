from __future__ import annotations

from typing import List

from .models import Skill


def create_default_skills() -> List[Skill]:
    skills = [
        # Core attacks/status
        Skill("Spark Shot", mp_cost=2, damage=5, range_max=4, shape="point", description="Efficient single-target strike."),
        Skill("Venom Dart", mp_cost=3, damage=3, range_max=5, shape="point", status="poison", status_duration=3, description="Light shot that poisons one enemy."),
        Skill("Marking Shot", mp_cost=3, damage=2, range_max=5, shape="point", status="vulnerable", status_duration=2, description="Marks one enemy, making follow-up hits stronger."),
        Skill("Pinning Line", mp_cost=5, damage=4, range_max=6, shape="strip", width=1, status="root", status_duration=1, description="Linear shot that pins enemies in place."),
        Skill("Toxic Cloud", mp_cost=6, damage=2, range_max=5, aoe_radius=1, shape="burst", status="poison", status_duration=2, description="Small poison cloud for clustered enemies."),

        # Support/action economy
        Skill("Coordinate", mp_cost=0, damage=0, range_max=99, shape="support", description="End this unit's turn and transfer all remaining AP to an ally.", effect="transfer_ap", ap_amount=0, target_team="ally"),
        Skill("Field Aid", mp_cost=4, damage=0, range_max=99, shape="support", description="Restore 8 HP to one ally.", effect="heal", heal_amount=8, target_team="ally"),
        Skill("Cleanse Pulse", mp_cost=3, damage=0, range_max=99, shape="support", description="Remove poison, root, and vulnerable from one ally.", effect="cleanse", target_team="ally"),
        Skill("Guarding Call", mp_cost=3, damage=0, range_max=99, shape="support", description="Put one ally into Guard without using their AP.", effect="guard", target_team="ally"),
        Skill("Mana Channel", mp_cost=4, damage=0, range_max=99, shape="support", description="Restore 6 MP to one ally.", effect="restore_mp", mp_amount=6, target_team="ally"),

        # Area/terrain/barrel-friendly attacks
        Skill("Flame Burst", mp_cost=4, damage=7, range_max=5, aoe_radius=1, shape="burst", description="Compact explosive burst."),
        Skill("Shatter Shot", mp_cost=3, damage=2, range_max=6, aoe_radius=1, shape="burst", description="Low-damage burst built for detonating barrels and clearing clustered objects."),
        Skill("Cinder Sweep", mp_cost=5, damage=5, range_max=4, shape="cone", width=3, description="Wide cone that punishes enemies near chokepoints."),
        Skill("Frost Line", mp_cost=5, damage=5, range_max=6, shape="strip", width=1, status="root", status_duration=1, description="Freezing line attack that roots enemies in lanes."),
        Skill("Breaker Strike", mp_cost=6, damage=9, range_max=2, shape="point", status="vulnerable", status_duration=2, description="Close-range elite/boss pressure that leaves the target vulnerable."),
        Skill("Thorn Snare", mp_cost=6, damage=3, range_max=5, shape="cross", status="root", status_duration=1, description="Cross-shaped snare for holding enemies in hazardous terrain."),
        Skill("Shock Net", mp_cost=7, damage=4, range_max=5, aoe_radius=1, shape="burst", status="vulnerable", status_duration=1, description="Burst that exposes grouped enemies for follow-up attacks."),

        # Core class revamp skills
        Skill("Battle Standard", mp_cost=3, damage=0, range_max=99, shape="support", effect="guard", target_team="ally",
              description="Command support. Put one ally into Guard and anchor the front line."),
        Skill("Commander's Challenge", mp_cost=4, damage=4, range_max=4, shape="point", status="vulnerable", status_duration=2,
              description="Vanguard challenge. Exposes a priority target for the party."),
        Skill("Linebreaker", mp_cost=6, damage=6, range_max=4, shape="strip", width=1, status="root", status_duration=1,
              description="Vanguard lane breaker. Drives through a line and roots enemies."),
        Skill("Snare Trap", mp_cost=5, damage=2, range_max=5, aoe_radius=1, shape="burst", status="root", status_duration=1,
              description="Ranger trap. Roots a cluster and leaves a short-lived snare zone.",
              zone_type="earth", zone_duration=2, zone_damage=1, zone_status="root", zone_status_duration=1),
        Skill("Hailshot", mp_cost=6, damage=4, range_max=6, shape="multishot", shots=4, status="vulnerable", status_duration=1,
              description="Ranger volley. Hits up to four enemies near the target and exposes survivors."),
        Skill("Aegis Mend", mp_cost=5, damage=0, range_max=99, shape="support", effect="heal", heal_amount=10, target_team="ally",
              description="Guardian healing. Strong single-target mend that improves on guarded allies.",
              combo_target_guarded=True, combo_heal_bonus=4, combo_note="combo: guarded ally -> +healing"),
        Skill("Warden's Grasp", mp_cost=6, damage=4, range_max=5, shape="cross", status="root", status_duration=1,
              description="Guardian control. Cross-shaped root that creates rough earth under its targets.",
              zone_type="earth", zone_duration=2, zone_damage=1, zone_status="root", zone_status_duration=1),
        Skill("Runic Flare", mp_cost=5, damage=5, range_max=5, aoe_radius=1, shape="burst",
              description="Mystic fire rune. Creates a burning field that keeps punishing clustered enemies.",
              zone_type="fire", zone_duration=2, zone_damage=2),
        Skill("Rime Field", mp_cost=5, damage=3, range_max=5, aoe_radius=1, shape="burst", status="root", status_duration=1,
              description="Mystic frost field. Roots enemies and leaves a chilling zone.",
              zone_type="frost", zone_duration=2, zone_damage=1, zone_status="root", zone_status_duration=1),
        Skill("Storm Seal", mp_cost=5, damage=3, range_max=5, aoe_radius=1, shape="burst", status="vulnerable", status_duration=1,
              description="Mystic storm seal. Exposes enemies and leaves a static zone.",
              zone_type="storm", zone_duration=2, zone_damage=1, zone_status="vulnerable", zone_status_duration=1),

        # Class-specific synergy skills
        Skill("Opening Command", mp_cost=4, damage=5, range_max=4, shape="point", status="vulnerable", status_duration=1,
              description="Vanguard setup attack. If the target is already vulnerable, deals extra damage and refunds 1 AP.",
              combo_status="vulnerable", combo_damage_bonus=3, combo_ap_gain=1, combo_note="combo: vulnerable target -> +damage, +1 AP"),
        Skill("Shield Rush", mp_cost=4, damage=6, range_max=2, shape="point", status="root", status_duration=1,
              description="Vanguard guard combo. If the caster is guarding, deals extra damage.",
              combo_guarded=True, combo_damage_bonus=4, combo_note="combo: caster guarding -> +damage"),
        Skill("Predator Shot", mp_cost=5, damage=5, range_max=6, shape="point",
              description="Ranger finisher. Deals extra damage to poisoned, rooted, or vulnerable enemies.",
              combo_any_status=True, combo_damage_bonus=5, combo_note="combo: any enemy status -> +damage"),
        Skill("Venom Detonator", mp_cost=6, damage=4, range_max=5, aoe_radius=1, shape="burst", status="vulnerable", status_duration=1,
              description="Ranger poison combo. Deals extra damage to poisoned enemies and makes survivors vulnerable.",
              combo_status="poison", combo_damage_bonus=4, combo_note="combo: poisoned target -> +damage"),
        Skill("Bulwark Mend", mp_cost=5, damage=0, range_max=99, shape="support", effect="heal", heal_amount=6, target_team="ally",
              description="Guardian support combo. Heals more if the target is already guarding.",
              combo_target_guarded=True, combo_heal_bonus=6, combo_note="combo: guarded ally -> +healing"),
        Skill("Sentinel Bash", mp_cost=5, damage=5, range_max=2, shape="point", status="root", status_duration=1,
              description="Guardian guard combo. If the caster is guarding, deals extra damage and roots the enemy.",
              combo_guarded=True, combo_damage_bonus=4, combo_note="combo: caster guarding -> +damage"),
        Skill("Arcane Echo", mp_cost=4, damage=4, range_max=5, shape="point",
              description="Mystic echo attack. Hitting a statused enemy restores MP.",
              combo_any_status=True, combo_mp_gain=3, combo_note="combo: any enemy status -> +3 MP"),
        Skill("Conductive Burst", mp_cost=6, damage=5, range_max=5, aoe_radius=1, shape="burst", status="vulnerable", status_duration=1,
              description="Mystic control combo. Deals extra damage to rooted enemies and makes enemies vulnerable.",
              combo_status="root", combo_damage_bonus=4, combo_note="combo: rooted target -> +damage"),

        # Duelist class skills
        Skill("Lunge", mp_cost=3, damage=6, range_max=3, shape="point",
              description="Duelist opener. A precise thrust with slightly extended reach."),
        Skill("Feint", mp_cost=3, damage=4, range_max=2, shape="point", status="vulnerable", status_duration=1,
              description="Duelist setup. Light strike that makes the target vulnerable."),
        Skill("Disarming Feint", mp_cost=4, damage=5, range_max=2, shape="point", status="vulnerable", status_duration=2,
              description="Duelist control setup that exposes a key enemy for follow-up attacks."),
        Skill("Riposte", mp_cost=4, damage=7, range_max=2, shape="point",
              description="Duelist guard combo. Hits harder while the caster is guarding.",
              combo_guarded=True, combo_damage_bonus=5, combo_note="combo: caster guarding -> +damage"),
        Skill("Cross Cut", mp_cost=5, damage=5, range_max=2, shape="cross",
              description="Duelist close-range cross slash for clustered enemies."),
        Skill("Finisher Thrust", mp_cost=6, damage=6, range_max=3, shape="point",
              description="Duelist finisher. Deals heavy bonus damage to statused enemies.",
              combo_any_status=True, combo_damage_bonus=7, combo_note="combo: any enemy status -> +damage"),
        Skill("Flash Step", mp_cost=4, damage=0, range_max=99, shape="support", effect="guard", target_team="ally",
              description="Duelist support stance. Put an ally into Guard before a dangerous exchange."),
        Skill("Blade Waltz", mp_cost=7, damage=5, range_max=4, shape="multishot", shots=4,
              description="Duelist finisher. Hits up to four enemies near the target."),

        # Alchemist class skills
        Skill("Acid Flask", mp_cost=4, damage=4, range_max=5, aoe_radius=1, shape="burst", status="poison", status_duration=2,
              description="Alchemist starter. Small poison flask for clustered enemies."),
        Skill("Rooting Resin", mp_cost=5, damage=3, range_max=5, aoe_radius=1, shape="burst", status="root", status_duration=1,
              description="Alchemist control flask that roots enemies in a small burst."),
        Skill("Smoke Bomb", mp_cost=4, damage=2, range_max=4, shape="cone", width=2, status="vulnerable", status_duration=1,
              description="Alchemist cone that exposes enemies for follow-up attacks."),
        Skill("Catalyst Brew", mp_cost=4, damage=0, range_max=99, shape="support", effect="restore_mp", mp_amount=8, target_team="ally",
              description="Alchemist support brew that restores MP to one ally."),
        Skill("Panacea", mp_cost=4, damage=0, range_max=99, shape="support", effect="cleanse", target_team="ally",
              description="Alchemist cure-all that removes poison, root, and vulnerable."),
        Skill("Volatile Flask", mp_cost=6, damage=7, range_max=5, aoe_radius=1, shape="burst",
              description="Alchemist burst. Deals bonus damage to poisoned targets.",
              combo_status="poison", combo_damage_bonus=5, combo_note="combo: poisoned target -> +damage"),
        Skill("Philosopher Flask", mp_cost=7, damage=5, range_max=5, aoe_radius=2, shape="burst", status="poison", status_duration=2,
              description="Alchemist advanced flask. Wide poison burst for grouped enemies."),

        # Class mastery arts
        Skill("Rallying Breaker", mp_cost=7, damage=8, range_max=4, aoe_radius=1, shape="burst", status="vulnerable", status_duration=2,
              description="Vanguard mastery art. Burst command strike that exposes enemies and refunds AP against vulnerable targets.",
              combo_status="vulnerable", combo_damage_bonus=4, combo_ap_gain=1, combo_note="mastery: vulnerable target -> +damage, +1 AP"),
        Skill("Arrowstorm", mp_cost=8, damage=5, range_max=6, shape="multishot", shots=5,
              description="Ranger mastery art. Fires up to five precision shots near the target."),
        Skill("Last Bastion", mp_cost=5, damage=0, range_max=99, shape="support", effect="guard", target_team="ally",
              description="Guardian mastery art. Put any ally into Guard; ideal for saving a threatened unit."),
        Skill("Starfall", mp_cost=9, damage=9, range_max=6, aoe_radius=2, shape="burst", status="vulnerable", status_duration=2,
              description="Mystic mastery art. Large falling-star burst that exposes survivors."),
        Skill("Grand Flourish", mp_cost=8, damage=6, range_max=5, shape="multishot", shots=6, status="vulnerable", status_duration=1,
              description="Duelist mastery art. Six elegant strikes that expose survivors."),
        Skill("Magnum Opus", mp_cost=9, damage=7, range_max=6, aoe_radius=2, shape="burst", status="vulnerable", status_duration=2,
              description="Alchemist mastery art. Grand explosive flask that exposes enemies and detonates poisoned targets.",
              combo_status="poison", combo_damage_bonus=5, combo_note="mastery: poisoned target -> +damage"),

        # Elemental subclass zone skills
        Skill("Ignite Field", mp_cost=5, damage=3, range_max=5, aoe_radius=1, shape="burst",
              description="Fire subclass skill. Creates a burning zone for 3 turns.",
              zone_type="fire", zone_duration=3, zone_damage=2),
        Skill("Glacial Patch", mp_cost=5, damage=2, range_max=5, aoe_radius=1, shape="burst", status="root", status_duration=1,
              description="Frost subclass skill. Creates a chilling root zone for 3 turns.",
              zone_type="frost", zone_duration=3, zone_damage=1, zone_status="root", zone_status_duration=1),
        Skill("Static Field", mp_cost=5, damage=2, range_max=5, aoe_radius=1, shape="burst", status="vulnerable", status_duration=1,
              description="Storm subclass skill. Creates a static zone that exposes enemies.",
              zone_type="storm", zone_duration=3, zone_damage=1, zone_status="vulnerable", zone_status_duration=1),
        Skill("Quake Field", mp_cost=5, damage=3, range_max=4, aoe_radius=1, shape="burst", status="root", status_duration=1,
              description="Earth subclass skill. Creates rough earth that roots enemies.",
              zone_type="earth", zone_duration=3, zone_damage=1, zone_status="root", zone_status_duration=1),
        Skill("Venom Pool", mp_cost=5, damage=2, range_max=5, aoe_radius=1, shape="burst", status="poison", status_duration=2,
              description="Poison subclass skill. Creates a toxic pool for 3 turns.",
              zone_type="poison", zone_duration=3, zone_damage=1, zone_status="poison", zone_status_duration=2),
        Skill("Radiant Seal", mp_cost=5, damage=2, range_max=5, aoe_radius=1, shape="burst", status="vulnerable", status_duration=1,
              description="Light subclass skill. Creates a radiant debuff zone.",
              zone_type="light", zone_duration=2, zone_damage=1, zone_status="vulnerable", zone_status_duration=1),
        Skill("Umbral Mire", mp_cost=5, damage=3, range_max=5, aoe_radius=1, shape="burst", status="vulnerable", status_duration=2,
              description="Shadow subclass skill. Creates a dark vulnerable zone.",
              zone_type="shadow", zone_duration=3, zone_damage=2, zone_status="vulnerable", zone_status_duration=1),

        # Elemental subclass multi-target attacks
        Skill("Flame Fan", mp_cost=6, damage=5, range_max=4, shape="cone", width=3,
              description="Fire subclass attack. Wide flame cone for clustered enemies."),
        Skill("Frost Shards", mp_cost=6, damage=4, range_max=5, shape="multishot", shots=3, status="root", status_duration=1,
              description="Frost subclass attack. Three shard shots that can root several enemies."),
        Skill("Chain Lightning", mp_cost=6, damage=3, range_max=5, shape="multishot", shots=4, status="vulnerable", status_duration=1,
              description="Storm subclass attack. Arcing bolts that expose multiple enemies."),
        Skill("Seismic Wave", mp_cost=6, damage=5, range_max=5, shape="strip", width=1, status="root", status_duration=1,
              description="Earth subclass attack. A straight shockwave that roots enemies in a lane."),
        Skill("Toxic Bloom", mp_cost=6, damage=3, range_max=5, aoe_radius=1, shape="burst", status="poison", status_duration=2,
              description="Poison subclass attack. Poison burst for clustered enemies."),
        Skill("Solar Flare", mp_cost=6, damage=4, range_max=5, aoe_radius=1, shape="burst", status="vulnerable", status_duration=1,
              description="Light subclass attack. Radiant burst that exposes grouped foes."),
        Skill("Umbral Barrage", mp_cost=6, damage=4, range_max=5, shape="multishot", shots=3, status="vulnerable", status_duration=1,
              description="Shadow subclass attack. Dark bolts for picking off exposed targets."),

        # Existing heavy/multi-target finishers
        Skill("Snare Burst", mp_cost=5, damage=4, range_max=4, aoe_radius=2, shape="burst", status="root", status_duration=1, description="Wide snaring blast that roots."),
        Skill("Stonebreak", mp_cost=7, damage=10, range_max=3, aoe_radius=1, shape="burst", description="Heavy close-range impact."),
        Skill("Meteor Volley", mp_cost=10, damage=11, range_max=6, aoe_radius=2, shape="burst", description="Expensive large-area finisher."),
        Skill("Blinding Flash", mp_cost=5, damage=2, range_max=4, shape="cone", width=2, status="vulnerable", status_duration=1, description="Cone flash that exposes clustered foes."),
        Skill("Piercing Line", mp_cost=6, damage=6, range_max=6, shape="strip", width=1, description="Long piercing line through lanes."),
        Skill("Sweeping Arc", mp_cost=4, damage=6, range_max=2, shape="cross", description="Cross-shaped close-range sweep."),
        Skill("Triple Shot", mp_cost=6, damage=4, range_max=5, shape="multishot", shots=3, description="Hits up to 3 enemies near the target."),
    ]
    try:
        from ascii_farmstead_custom_content import create_custom_skills

        skills.extend(create_custom_skills(skill.name for skill in skills))
    except (ImportError, OSError, ValueError, TypeError):
        # Tactical combat remains fully playable if optional custom content is
        # unavailable or malformed.
        pass
    return skills
