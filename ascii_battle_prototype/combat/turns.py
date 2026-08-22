from __future__ import annotations

import time
from typing import List

from .constants import PASSABLE, TILE_DIRT, TILE_FLOOR, TILE_GRASS, TILE_ICE, TILE_MUD, TILE_THORNS
from .models import Zone


def run_enemy_turn(game: object) -> None:
    events: List[str] = []

    for enemy in game.enemies_alive():
        game.tick_cooldowns(enemy)
        game.apply_start_of_turn_status(enemy, events)
        if not enemy.alive:
            events.append(f"{enemy.name} falls")
            continue

        enemy.action_points = game.enemy_ap_budget(enemy)

        while enemy.alive and enemy.action_points > 0 and game.heroes_alive():
            action = game.choose_enemy_action(enemy)

            if not action:
                enemy.guard = True
                events.append(f"{enemy.name} guards")
                enemy.action_points = 0
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
                break

            kind = action[0]
            spent = game.enemy_action_cost(enemy, kind)
            old_pos = enemy.pos

            if kind == "attack":
                _, target = action
                game.enemy_basic_attack(enemy, target, events)
            elif kind == "barrel":
                _, barrel_pos, _targets, _allies, _score = action
                game.enemy_attack_barrel(enemy, barrel_pos, events)
            elif kind == "poison":
                _, target = action
                game.enemy_poison_peck(enemy, target, events)
            elif kind == "pack_pounce":
                _, target, damage = action
                game.flash_effect([target.pos], "combo")
                dmg = target.take_damage(damage)
                game.combat_stats["enemy_damage"] += dmg
                game.record_damage_taken(target, dmg)
                target.vulnerable = max(target.vulnerable, 2)
                enemy.cooldowns["Pack Pounce"] = 3
                pack = game.nearby_enemy_family_count(enemy, "Wolf", radius=4)
                events.append(f"{enemy.name} pack-pounces {target.name} {dmg} +vuln ({pack} nearby)")
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "harry":
                _, target, retreat = action
                game.flash_effect([target.pos], "hit")
                dmg = target.take_damage(2 + (1 if target.hp <= target.max_hp * 0.5 else 0))
                game.combat_stats["enemy_damage"] += dmg
                game.record_damage_taken(target, dmg)
                target.vulnerable = max(target.vulnerable, 2)
                enemy.cooldowns["Harrier Dive"] = 3
                events.append(f"{enemy.name} harries {target.name} {dmg} +vuln")
                if retreat != enemy.pos and enemy.alive:
                    game.move_enemy_to(enemy, retreat, events)
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "needle_dash":
                _, target, destination, damage = action
                if game.move_enemy_to(enemy, destination, events) and target.alive:
                    game.flash_effect([target.pos], "hit")
                    dmg = target.take_damage(damage)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.rooted = max(target.rooted, 1)
                    enemy.cooldowns["Needle Dash"] = 3
                    events.append(f"{enemy.name} needle-dashes {target.name} {dmg} +root")
                    game.render()
                    if game.frame_delay > 0:
                        time.sleep(game.frame_delay)
            elif kind == "cinder_toss":
                _, center, targets, barrels = action
                game.flash_effect(game.aoe_tiles(center, 1), "fire")
                parts = []
                for target in targets:
                    dmg = target.take_damage(3)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.vulnerable = max(target.vulnerable, 2)
                    parts.append(f"{target.name} {dmg}+vuln")
                for barrel in barrels:
                    result = game.explode_barrel(barrel, enemy)
                    if result:
                        parts.append("barrel")
                enemy.cooldowns["Cinder Toss"] = 4
                events.append(f"{enemy.name} tosses cinders: " + (", ".join(parts) if parts else "scorches ground"))
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "frost_cloud":
                _, center, targets, ice_tiles = action
                game.flash_effect(game.aoe_tiles(center, 1), "ice")
                for tile in ice_tiles:
                    game.set_tile(tile, TILE_ICE)
                zone_tiles = {p for p in game.aoe_tiles(center, 1) if game.in_bounds(p) and game.tile_at(p) in PASSABLE}
                if zone_tiles:
                    game.zones.append(Zone("Frost Cloud", zone_tiles, "frost", 2, damage=1, status="root", status_duration=1, owner_team=enemy.team))
                    game.combat_stats["zones_created"] = game.combat_stats.get("zones_created", 0) + 1
                    game.combat_stats["zone_frost"] = game.combat_stats.get("zone_frost", 0) + 1
                parts = []
                for target in targets:
                    dmg = target.take_damage(1)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.rooted = max(target.rooted, 1)
                    parts.append(f"{target.name} {dmg}+root")
                enemy.cooldowns["Frost Cloud"] = 5
                events.append(f"{enemy.name} chills the field: " + ", ".join(parts))
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "burrow_ambush":
                _, target, destination, damage = action
                old_burrow = enemy.pos
                enemy.pos = destination
                game.flash_effect([old_burrow, destination, target.pos], "root")
                if target.alive:
                    dmg = target.take_damage(damage)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.vulnerable = max(target.vulnerable, 2)
                    events.append(f"{enemy.name} burrows under {target.name} {dmg} +vuln")
                enemy.cooldowns["Burrow Ambush"] = 5
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "quill_volley":
                _, center, targets = action
                game.flash_effect(game.aoe_tiles(center, 1), "vulnerable")
                parts = []
                for target in targets:
                    dmg = target.take_damage(2)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.vulnerable = max(target.vulnerable, 2)
                    parts.append(f"{target.name} {dmg}+vuln")
                enemy.cooldowns["Quill Volley"] = 4
                events.append(f"{enemy.name} fires quills: " + ", ".join(parts))
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "retreat":
                _, destination = action
                if game.move_enemy_to(enemy, destination, events):
                    enemy.cooldowns["Evasive Hop"] = 2
                    events.append(f"{enemy.name} hops away")
                    game.render()
                    if game.frame_delay > 0:
                        time.sleep(game.frame_delay)
            elif kind == "charge":
                _, target, destination = action
                if game.move_enemy_to(enemy, destination, events) and enemy.alive and target.alive:
                    game.flash_effect([target.pos], "hit")
                    dmg = target.take_damage(6)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.vulnerable = max(target.vulnerable, 2)
                    enemy.cooldowns["Brutal Charge"] = 4
                    events.append(f"{enemy.name} charges {target.name} {dmg} +vuln")
                    game.render()
                    if game.frame_delay > 0:
                        time.sleep(game.frame_delay)
            elif kind == "intimidate":
                _, target = action
                game.flash_effect([target.pos], "vulnerable")
                target.vulnerable = max(target.vulnerable, 2)
                enemy.cooldowns["War Cry"] = 3
                events.append(f"{enemy.name} intimidates {target.name}")
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "root":
                _, target = action
                game.flash_effect([target.pos], "root")
                dmg = target.take_damage(2)
                game.combat_stats["enemy_damage"] += dmg
                game.record_damage_taken(target, dmg)
                target.rooted = max(target.rooted, 1)
                enemy.cooldowns["Binding Roots"] = 4
                events.append(f"{enemy.name} roots {target.name} {dmg}")
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "spore":
                _, center, targets = action
                game.flash_effect([target.pos for target in targets], "poison")
                parts = []
                for target in targets:
                    dmg = target.take_damage(2)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.vulnerable = max(target.vulnerable, 2)
                    parts.append(f"{target.name} {dmg}")
                enemy.cooldowns["Toxic Burst"] = 5
                events.append(f"{enemy.name} spores: " + ", ".join(parts))
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "spore_patch":
                _, center, targets, patch_tiles = action
                game.flash_effect(game.aoe_tiles(center, 1), "poison")
                for tile in patch_tiles:
                    game.set_tile(tile, TILE_MUD)
                parts = []
                for target in targets:
                    dmg = target.take_damage(1)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.poison = max(target.poison, 2)
                    target.vulnerable = max(target.vulnerable, 2)
                    parts.append(f"{target.name} {dmg}+poison")
                enemy.cooldowns["Spore Patch"] = 5
                events.append(f"{enemy.name} spreads spores: " + ", ".join(parts))
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "briar_bloom":
                _, center, targets, thorn_tiles = action
                game.flash_effect(game.aoe_tiles(center, 1), "root")
                for tile in thorn_tiles:
                    game.set_tile(tile, TILE_THORNS)
                parts = []
                for target in targets:
                    dmg = target.take_damage(2)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.rooted = max(target.rooted, 1)
                    parts.append(f"{target.name} {dmg}+root")
                enemy.cooldowns["Briar Bloom"] = 6
                events.append(f"{enemy.name} blooms briars: " + ", ".join(parts))
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "ooze_mire":
                _, center, targets, mire_tiles = action
                game.flash_effect(game.aoe_tiles(center, 1), "poison")
                zone = Zone("Ooze Mire", set(mire_tiles), "poison", 3, damage=1, status="poison", status_duration=2, owner_team=enemy.team)
                game.zones.append(zone)
                game.combat_stats["zones_created"] = game.combat_stats.get("zones_created", 0) + 1
                game.combat_stats["zone_poison"] = game.combat_stats.get("zone_poison", 0) + 1
                for tile in mire_tiles:
                    if game.tile_at(tile) in (TILE_FLOOR, TILE_DIRT, TILE_GRASS):
                        game.set_tile(tile, TILE_MUD)
                parts = []
                for target in targets:
                    dmg = target.take_damage(1)
                    game.combat_stats["enemy_damage"] += dmg
                    game.record_damage_taken(target, dmg)
                    target.poison = max(target.poison, 2)
                    parts.append(f"{target.name} {dmg}+poison")
                enemy.cooldowns["Ooze Mire"] = 4
                events.append(f"{enemy.name} spreads ooze: " + (", ".join(parts) if parts else "poison zone"))
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "shield_wall":
                _, allies = action
                game.flash_effect([unit.pos for unit in allies], "guard")
                parts = []
                for ally in allies:
                    ally.guard = True
                    if ally.vulnerable > 0:
                        ally.vulnerable = max(0, ally.vulnerable - 1)
                    parts.append(ally.name)
                enemy.cooldowns["Shield Wall"] = 4
                events.append(f"{enemy.name} forms shield wall: " + ", ".join(parts))
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "phase_shot":
                _, destination, target = action
                old = enemy.pos
                enemy.pos = destination
                game.flash_effect([old, destination, target.pos], "ice")
                dmg = target.take_damage(3)
                game.combat_stats["enemy_damage"] += dmg
                game.record_damage_taken(target, dmg)
                target.rooted = max(target.rooted, 1)
                enemy.cooldowns["Phase Shot"] = 4
                events.append(f"{enemy.name} phase-shots {target.name} {dmg}+root")
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "briar_heart":
                _, thorn_tiles = action
                heal = min(10, enemy.max_hp - enemy.hp)
                enemy.hp += heal
                enemy.guard = True
                enemy.vulnerable = 0
                game.flash_effect([enemy.pos, *thorn_tiles], "root")
                for tile in thorn_tiles:
                    if game.tile_at(tile) in (TILE_FLOOR, TILE_DIRT, TILE_GRASS, TILE_MUD):
                        game.set_tile(tile, TILE_THORNS)
                zone = Zone("Briar Heart", set(thorn_tiles), "earth", 3, damage=1, status="root", status_duration=1, owner_team=enemy.team)
                game.zones.append(zone)
                game.combat_stats["zones_created"] = game.combat_stats.get("zones_created", 0) + 1
                game.combat_stats["zone_earth"] = game.combat_stats.get("zone_earth", 0) + 1
                enemy.cooldowns["Briar Heart"] = 99
                events.append(f"{enemy.name} reveals Briar Heart (+{heal} HP, thorn zone)")
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "elite_drive":
                heal = min(5, enemy.max_hp - enemy.hp)
                enemy.hp += heal
                enemy.guard = True
                enemy.vulnerable = 0
                enemy.rooted = 0
                enemy.cooldowns["Elite Drive"] = 99
                game.flash_effect([enemy.pos], "guard")
                events.append(f"{enemy.name} uses Elite Drive (+{heal} HP, guard)")
                game.render()
                if game.frame_delay > 0:
                    time.sleep(game.frame_delay)
            elif kind == "move":
                _, destination = action
                if destination == enemy.pos:
                    enemy.guard = True
                    events.append(f"{enemy.name} holds")
                    enemy.action_points = 0
                    game.render()
                    if game.frame_delay > 0:
                        time.sleep(game.frame_delay)
                    break
                if game.move_enemy_to(enemy, destination, events):
                    events.append(f"{enemy.name} moves")
                    game.render()
                    if game.frame_delay > 0:
                        time.sleep(game.frame_delay)

            enemy.action_points = max(0, enemy.action_points - spent)

            # If Overwatch or an action killed the enemy, stop its turn.
            if not enemy.alive:
                break

            # Do not allow repeated attacks/specials. Extra AP is mostly for
            # move + act, or retreat + possible follow-up if still relevant.
            if game.enemy_action_ends_sequence(kind):
                enemy.action_points = 0
                break

            # If movement failed to change position, avoid loops.
            if kind in {"move", "retreat"} and enemy.pos == old_pos:
                enemy.action_points = 0
                break

        enemy.action_points = 0

    expired_overwatch = game.clear_all_overwatch()
    game.turn = "hero"
    game.round_no += 1
    game.combat_stats["rounds"] = game.round_no
    status_events: List[str] = []
    if expired_overwatch:
        status_events.append("Overwatch expires")
    game.apply_party_start_statuses(status_events)
    game.tick_zones(status_events)
    game.tick_objective_progress(status_events)
    for h in game.heroes_alive():
        h.action_points = 2
        h.guard = False
        h.mp = min(h.max_mp, h.mp + 1)
    game.state = "command"
    game.advance_to_next_ready_hero()
    game.cursor = game.selected_hero.pos
    summary = ("; ".join(events) if events else "Enemies hesitate.")
    if status_events:
        summary += " | " + "; ".join(status_events)
    game.push(summary + " Your turn.")

