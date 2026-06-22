from __future__ import annotations

from .rendering import Style, c, clear_screen, clip, wrap_labeled, wrap_plain


def render_main_menu(game: object) -> None:
    clear_screen()
    width = 96
    if game.text_entry_target:
        game.render_name_entry(width)
        return
    if game.main_menu_mode == "home":
        game.render_home_menu(width)
        return

    print(c("ASCII Tactical Combat Prototype v113", Style.BOLD, Style.BRIGHT_WHITE))
    print(c("SETUP / " + game.main_menu_mode.upper(), Style.BOLD, Style.BRIGHT_YELLOW))
    print("-" * width)
    print("X/Esc: Back | Home: Home | H: Help | Q: Quit")
    msg = game.main_menu_message()
    if msg and "Command menu active" not in msg:
        for line in wrap_labeled("Note: ", msg, width):
            print(c(line[:6], Style.BOLD) + line[6:] if line.startswith("Note: ") else line)
    print("-" * width)

    if game.main_menu_mode == "missions":
        if game.mission_page_index == 0:
            print(c("Mission Presets", Style.BOLD, Style.BRIGHT_CYAN))
            presets = game.mission_presets()
            if not presets:
                print("No mission presets.")
                return
            for i, preset in enumerate(presets):
                selected = i == game.mission_menu_index % len(presets)
                name = str(preset.get("name", "Mission"))
                prefix = "> " if selected else "  "
                if selected:
                    print(c(prefix + clip(name, 36), Style.BLACK, Style.BG_SELECT, Style.BOLD))
                else:
                    print(prefix + clip(name, 36))
            preset = presets[game.mission_menu_index % len(presets)]
            print()
            for line in game.compact_mission_summary(preset):
                for wrapped in wrap_plain(line, width - 4, subsequent_indent="  "):
                    print("  " + wrapped)
            print()
            print("Up/Down choose | Z/Enter select | Right/B builder | X/Esc back")
        else:
            draft = game.mission_builder_draft()
            print(c("Mission Builder", Style.BOLD, Style.BRIGHT_MAGENTA))
            fields = game.mission_builder_fields()
            values = {
                "Name": str(draft["name"]) + ("  (custom)" if game.mission_builder_custom_name else ""),
                "Map": draft["map"],
                "Enemy Theme": draft["theme"],
                "Objective": draft["objective"],
                "Parameter": game.objective_parameter_text_for_draft(draft),
            }
            for i, field in enumerate(fields):
                selected = i == game.mission_builder_field_index % len(fields)
                row = f"{field}: {values[field]}"
                prefix = "> " if selected else "  "
                if selected:
                    print(c(prefix + clip(row, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
                else:
                    print(prefix + clip(row, width - 2))
            print()
            for wrapped in wrap_labeled("Enemies: ", ", ".join(draft['enemies']), width):
                print(wrapped)
            print(f"Threat: {game.threat_difficulty_name(game.mission_threat_value(draft))} ({game.mission_threat_value(draft)})")
            print()
            print("Up/Down field | Left/Right edit | Z/Enter name/select | V save | X/Esc presets")
        return

    if game.main_menu_mode == "tutorial":
        print(c("Tutorials", Style.BOLD, Style.BRIGHT_GREEN))
        modes = game.tutorial_modes()
        for i, (mode, title, map_name, desc) in enumerate(modes):
            selected = i == game.tutorial_menu_index % len(modes)
            prefix = "> " if selected else "  "
            row = f"{title:<20} {map_name}"
            if selected:
                print(c(prefix + clip(row, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
            else:
                print(prefix + clip(row, width - 2))
        mode, title, training, desc = modes[game.tutorial_menu_index % len(modes)]
        print()
        for line in wrap_labeled("Info: ", desc, width):
            print(line)
        for line in wrap_labeled("Steps: ", ", ".join(step_title for _key, step_title, _desc in game.tutorial_steps_for_mode(mode)), width):
            print(line)
        print("Up/Down choose | Z/Enter start | X/Esc back")
        return

    if game.main_menu_mode == "companions":
        print(c("Companion Editor", Style.BOLD, Style.BRIGHT_CYAN))
        draft = game.companion_draft_summary()
        fields = game.companion_editor_fields()
        values = {
            "Name": str(draft["name"]) + ("  (custom)" if game.companion_editor_custom_name else ""),
            "Color": c("@", game.companion_color_style(str(draft["color"])), Style.BOLD) + f" {draft['color']}",
            "Archetype": draft["archetype"],
            "Class": draft["class"],
            "Element": draft["subclass"],
            "Weapon": draft["weapon"],
            "Add to Party": "yes" if draft["add_to_party"] else "reserve",
            "Manual Control": "manual" if draft["manual"] else "AI",
        }
        for i, field in enumerate(fields):
            selected = i == game.companion_editor_field_index
            row = f"{field:<16} {values[field]}"
            prefix = "> " if selected else "  "
            if selected:
                print(c(prefix + clip(row, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
            else:
                print(prefix + clip(row, width - 2))
        stats = draft["stats"]
        print()
        print(f"Preview: HP {stats['max_hp']} | MP {stats['max_mp']} | DMG {stats['weapon_damage']} | Move {stats['move_range']}")
        for line in wrap_labeled("Build: ", f"{draft['class']} / {draft['subclass']} | {game.build_synergy_rating(str(draft['class']), str(draft['subclass']))}", width):
            print(line)
        custom_names = [h.name for h in game.heroes if h.name in game.custom_companion_names]
        for line in wrap_labeled("Created: ", (", ".join(custom_names) if custom_names else "none"), width):
            print(line)
        print("Up/Down field | Left/Right edit | Z/Enter name/create | Backspace delete | X/Esc back")
        return

    if game.main_menu_mode == "party":
        print(c("Party", Style.BOLD, Style.BRIGHT_CYAN))
        active_line = ", ".join(game.active_party_names_list())
        print(f"Current Party ({len(game.active_party_names_list())}/{game.party_limit}): {active_line}")
        print()
        for i, hero in enumerate(game.heroes):
            selected = i == game.party_menu_index
            if hero.name == "Rook":
                state = "Leader  "
            elif hero.name in game.active_party_names:
                state = "Selected"
            else:
                state = "Reserve "
            control = game.companion_control_label(hero) if hero.name != "Rook" else "required"
            row = f"{state:<8} {hero.name:<12} {game.hero_class(hero):<9} {control}"
            prefix = "> " if selected else "  "
            if selected:
                print(c(prefix + clip(row, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
            else:
                print(prefix + clip(row, width - 2))

        hero = game.heroes[game.party_menu_index % len(game.heroes)]
        progress = game.ensure_progress_entry(hero)
        mods = game.equipment_total_mods(hero)
        hp = game.base_hero_stat(hero.name, "max_hp") + int(progress.get("hp_bonus", 0)) + mods["hp"]
        mp = game.base_hero_stat(hero.name, "max_mp") + int(progress.get("mp_bonus", 0)) + mods["mp"]
        dmg = game.base_hero_stat(hero.name, "weapon_damage") + int(progress.get("damage_bonus", 0)) + mods["dmg"]
        move = game.base_hero_stat(hero.name, "move_range") + mods["move"]
        status = "Required Leader" if hero.name == "Rook" else ("Selected for battle" if hero.name in game.active_party_names else "In reserve")
        control = game.companion_control_label(hero) if hero.name != "Rook" else "Leader"
        skills = [skill.name for skill in game.available_skills(hero)]
        skill_text = ", ".join(skills[:5]) if skills else "none"
        if len(skills) > 5:
            skill_text += f", +{len(skills) - 5}"

        print()
        print(c("Highlighted Companion", Style.BOLD, Style.BRIGHT_YELLOW))
        print(f"{hero.name}: {status}")
        for line in wrap_labeled("Role: ", f"{game.party_role_label(hero.name)} | Control: {control} | Color: {game.hero_color_name(hero)}", width):
            print(line)
        for line in wrap_labeled("Build: ", f"Lv {int(progress['level'])} {game.hero_class(hero)} / {game.hero_subclass(hero)} | {game.build_synergy_label(hero)}", width):
            print(line)
        print(f"Stats: HP {hp} | MP {mp} | DMG {dmg} | Move {move}")
        for line in wrap_labeled("Gear: ", game.hero_equipment_summary(hero), width):
            print(line)
        for line in wrap_labeled("Skills: ", skill_text, width):
            print(line)
        print()
        print("Up/Down choose | Z/Enter select/reserve | C color | X/Esc back")
        return

    if game.main_menu_mode == "loadout":
        print(c("Loadout", Style.BOLD, Style.BRIGHT_MAGENTA))
        hero = game.current_loadout_hero()
        slot = game.current_loadout_slot()
        print(f"{hero.name} / {slot.upper()} | Equipped: {game.hero_equipment_summary(hero)}")
        print()
        options = game.loadout_options()
        for i, option in enumerate(options):
            selected = i == game.loadout_menu_index
            affordable = game.can_afford(dict(option["cost"]))
            row = f"{option['label']:<28} {game.loadout_status_for_option(option)}"
            prefix = "> " if selected else "  "
            if selected:
                style = (Style.BLACK, Style.BG_SELECT, Style.BOLD) if affordable else (Style.BRIGHT_YELLOW, Style.BG_SELECT, Style.BOLD)
                print(c(prefix + clip(row, width - 2), *style))
            else:
                print(prefix + clip(row, width - 2))
        current = options[game.loadout_menu_index % len(options)]
        print()
        for line in wrap_labeled("Info: ", str(current["desc"]), width):
            print(line)
        for line in wrap_labeled("Cost: ", game.cost_text(dict(current["cost"])) + " | Inventory: " + game.inventory_text(game.campaign_inventory), width):
            print(line)
        print("Up/Down option | Left/Right hero | C slot | Z/Enter apply | X/Esc back")
        return

    if game.main_menu_mode == "classes":
        print(c("Classes / Skills", Style.BOLD, Style.BRIGHT_BLUE))
        hero = game.current_class_hero()
        progress = game.ensure_progress_entry(hero)
        class_names = game.class_names()

        if game.class_screen_depth == 0:
            print("Choose a character.")
            print()
            for i, candidate in enumerate(game.heroes):
                selected = i == game.class_menu_hero_index % len(game.heroes)
                row = f"{candidate.name:<12} {game.hero_class(candidate):<10} {game.class_slot_summary(candidate):<24} SP {int(game.ensure_progress_entry(candidate).get('skill_points', 0))}"
                prefix = "> " if selected else "  "
                if selected:
                    print(c(prefix + clip(row, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
                else:
                    print(prefix + clip(row, width - 2))
            print()
            for line in wrap_labeled("Info: ", game.class_screen_selected_hero_summary(hero), width):
                print(line)
            print("Up/Down character | Z/Enter classes | X/Esc back")
            return

        if game.class_screen_depth == 1:
            print(f"{hero.name} | {game.class_screen_selected_hero_summary(hero)}")
            print("Choose a class. Unmastered selected classes are capped at 3.")
            print()
            game.class_menu_class_index %= len(class_names)
            for i, class_name in enumerate(class_names):
                selected = i == game.class_menu_class_index
                mastered, total = game.class_mastery_progress(hero, class_name)
                status = game.class_status_label(hero, class_name)
                row = f"{class_name:<12} {status:<14} {mastered}/{total}"
                prefix = "> " if selected else "  "
                if selected:
                    print(c(prefix + clip(row, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
                else:
                    print(prefix + clip(row, width - 2))
            selected_class = class_names[game.class_menu_class_index]
            print()
            for line in wrap_labeled("Info: ", str(game.class_defs().get(selected_class, {}).get("desc", "")), width):
                print(line)
            print(f"Mastery: {game.class_mastery_label(hero, selected_class)}")
            print("Up/Down class | Z/Enter abilities/select | Left/X/Esc characters | V element")
            return

        # Ability list for focused class.
        class_name = game.hero_class(hero)
        tree = game.class_tree_for(class_name)
        subclass = game.hero_subclass(hero)
        print(f"{hero.name} | {class_name} / {subclass} | Lv {int(progress['level'])} | SP {int(progress.get('skill_points', 0))}")
        print(f"{game.class_slot_summary(hero)} | {game.class_mastery_label(hero, class_name)}")
        print()
        if not tree:
            print("  No unlocks.")
        for i, (skill_name, base_cost, desc) in enumerate(tree):
            selected = i == game.class_skill_index
            status = game.unlock_status_for_skill(hero, skill_name, class_name)
            rank = game.skill_rank(hero, skill_name, class_name)
            max_rank = game.skill_max_rank(skill_name, class_name)
            if status == "locked":
                action_text = f"{base_cost}SP"
            elif status.startswith("needs "):
                action_text = status
            elif rank < max_rank:
                action_text = f"{game.skill_upgrade_cost(base_cost, rank)}SP"
            else:
                action_text = "max"
            row = f"{skill_name:<20} R{rank}/{max_rank:<3} {action_text}"
            prefix = "> " if selected else "  "
            if selected:
                print(c(prefix + clip(row, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
            else:
                print(prefix + clip(row, width - 2))
        print()
        if tree:
            skill_name, base_cost, desc = tree[game.class_skill_index % len(tree)]
            skill = game.skill_by_name(skill_name)
            detail = game.skill_power_label(skill) if skill else ""
            prereqs = game.class_prereqs(class_name, skill_name)
            req = f" | Requires: {', '.join(prereqs)}" if prereqs else ""
            for line in wrap_labeled("Info: ", f"{desc} {detail}{req}", width):
                print(line)
        for line in wrap_labeled("Element skills: ", game.subclass_skill_label(subclass), width):
            print(line)
        print("Up/Down ability | Z/Enter upgrade | Left/X/Esc classes | R respec | V element")
        return

    if game.main_menu_mode == "bestiary":
        roster = game.bestiary_filtered_roster()
        if roster:
            game.bestiary_enemy_index %= len(roster)
        selected_name = roster[game.bestiary_enemy_index] if roster else ""
        selected_enemy = game.enemy_by_name(selected_name) if selected_name else None
        print(c("Bestiary", Style.BOLD, Style.BRIGHT_RED))
        print(f"Filter: {game.current_bestiary_filter()}")
        print()
        if not roster:
            print("  No enemies in this filter.")
        for i, name in enumerate(roster):
            enemy = game.enemy_by_name(name)
            selected = i == game.bestiary_enemy_index
            role = enemy.role if enemy else "?"
            row = f"{name:<18} {role}"
            prefix = "> " if selected else "  "
            if selected:
                print(c(prefix + clip(row, 42), Style.BLACK, Style.BG_SELECT, Style.BOLD))
            else:
                print(prefix + clip(row, 42))
        print()
        if selected_enemy:
            lines = game.enemy_inspection_lines(selected_enemy, include_live=False)
            shown = 0
            for line in lines:
                for wrapped in wrap_plain(line, width - 4, subsequent_indent="  "):
                    print("  " + wrapped)
                    shown += 1
                    if shown >= 8:
                        break
                if shown >= 8:
                    break
        print("Up/Down enemy | F filter | Z/Enter encounter | X/Esc back")
        return

    if game.main_menu_mode == "objectives":
        print(c("Objectives", Style.BOLD, Style.BRIGHT_CYAN))
        modes = game.objective_modes()
        for i, mode in enumerate(modes):
            selected = mode == game.objective_mode
            prefix = "> " if selected else "  "
            label = mode + ("  (default)" if mode == "Defeat All" else "")
            if selected:
                print(c(prefix + clip(label, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
            else:
                print(prefix + clip(label, width - 2))
        print()
        print("Parameter: " + game.objective_parameter_text())
        for line in wrap_labeled("Info: ", game.objective_setup_description(), width):
            print(line)
        print("Left/Right objective | Up/Down parameter | R reset | Z/Enter start | X/Esc back")
        return

    if game.main_menu_mode == "encounter":
        selected = game.selected_custom_enemy_names()
        print(c("Encounter Builder", Style.BOLD, Style.BRIGHT_RED))
        print(f"Map: {game.selected_map_name()}   Count: {len(selected)}/{game.custom_enemy_total_cap}   Threat: {game.encounter_threat_label()}")
        if selected:
            for line in wrap_labeled("Selected: ", game.selected_custom_enemy_summary(), width):
                print(line)
        else:
            print("Selected: None")
        print()
        rows = game.encounter_builder_rows()
        game.encounter_enemy_index %= len(rows)
        for i, (row_key, label) in enumerate(rows):
            selected_row = i == game.encounter_enemy_index
            prefix = "> " if selected_row else "  "
            if row_key == "action:start":
                row = "Start Encounter"
            elif row_key == "action:map":
                row = f"Map: {game.selected_map_name()}"
            elif row_key == "action:defaults":
                row = "Use Map Defaults"
            elif row_key == "action:clear":
                row = "Clear All"
            else:
                count = game.custom_enemy_counts.get(label, 0)
                row = f"{label:<22} x{count}"
            if selected_row:
                print(c(prefix + clip(row, width - 2), Style.BLACK, Style.BG_SELECT, Style.BOLD))
            else:
                print(prefix + clip(row, width - 2))
        enemy_name = game.encounter_selected_enemy_name()
        print()
        if enemy_name:
            for line in wrap_labeled("Info: ", game.selected_enemy_brief_line(enemy_name), width):
                print(line)
        else:
            row_key, _label = game.current_encounter_row()
            hints = {
                "action:start": "Start the custom encounter with the selected enemies.",
                "action:map": "Left/Right changes the map. Enter opens the full map selector.",
                "action:defaults": "Replace the enemy counts with this map's default encounter.",
                "action:clear": "Set every enemy count to zero.",
            }
            for line in wrap_labeled("Info: ", hints.get(row_key, ""), width):
                print(line)
        print("Up/Down choose | Left/Right change count/map | Z/Enter add/activate | X/Esc back")
        return

    if game.main_menu_mode == "maps":
        game.render_map_selector(width)
        return

    game.main_menu_mode = "home"
    game.render_home_menu(width)


def handle_main_menu_key(game: object, key: str, reader: object) -> None:
    if game.text_entry_target:
        game.handle_name_entry_key(key)
        return
    if key == "q":
        game.should_quit = True
        return
    if key == "h":
        game.help(reader)
        return
    if key == "u":
        game.toggle_ui_mode()
        return
    if key == "TAB":
        return
    if game.main_menu_mode == "home":
        if key in ("UP", "w"):
            game.home_menu_index = (game.home_menu_index - 1) % len(game.home_menu_options())
            return
        if key in ("DOWN", "s"):
            game.home_menu_index = (game.home_menu_index + 1) % len(game.home_menu_options())
            return
        if key in ("ENTER", "SPACE", "z"):
            game.activate_home_option(reader)
            return
    if key == "i":
        game.main_menu_mode = "missions"
        return
    if key == "o":
        game.main_menu_mode = "tutorial"
        return
    if key == "p":
        game.main_menu_mode = "party"
        return
    if key == "j":
        game.main_menu_mode = "companions"
        return
    if key == "l":
        game.main_menu_mode = "loadout"
        return
    if key == "e":
        game.main_menu_mode = "encounter"
        game.clear_custom_encounter()
        return
    if key == "g":
        game.main_menu_mode = "objectives"
        return
    if key == "k":
        game.main_menu_mode = "classes"
        return
    if key == "HOME":
        game.main_menu_mode = "home"
        return
    if key == "m":
        game.main_menu_mode = "maps"
        game.map_detail_open = False
        return
    if key == "b" and game.main_menu_mode not in ("encounter", "missions"):
        game.main_menu_mode = "bestiary"
        return

    if game.main_menu_mode == "missions":
        if key in ("ESC", "c", "m"):
            game.main_menu_mode = "home"
            return
        if key == "x":
            if game.mission_page_index == 1:
                game.mission_page_index = 0
            else:
                game.main_menu_mode = "home"
            return
        if key == "b":
            game.mission_page_index = 1 - game.mission_page_index
            return
        if game.mission_page_index == 0:
            presets = game.mission_presets()
            if key in ("UP", "w") and presets:
                game.mission_menu_index = (game.mission_menu_index - 1) % len(presets)
                return
            if key in ("DOWN", "s") and presets:
                game.mission_menu_index = (game.mission_menu_index + 1) % len(presets)
                return
            if key in ("RIGHT", "d"):
                game.mission_page_index = 1
                return
            if key in ("ENTER", "SPACE", "z") and presets:
                game.select_mission_without_starting(presets[game.mission_menu_index % len(presets)])
                return
            return
        else:
            if key in ("LEFT", "a") and game.mission_builder_field_index == 0:
                game.mission_page_index = 0
                return
            if key in ("UP", "w"):
                game.mission_builder_field_index = (game.mission_builder_field_index - 1) % len(game.mission_builder_fields())
                return
            if key in ("DOWN", "s"):
                game.mission_builder_field_index = (game.mission_builder_field_index + 1) % len(game.mission_builder_fields())
                return
            if key in ("LEFT", "a"):
                game.cycle_mission_builder_field(-1)
                return
            if key in ("RIGHT", "d"):
                game.cycle_mission_builder_field(1)
                return
            if key == "v":
                game.save_mission_builder_preset()
                game.mission_page_index = 0
                return
            if key in ("ENTER", "SPACE", "z"):
                if game.mission_builder_fields()[game.mission_builder_field_index % len(game.mission_builder_fields())] == "Name":
                    game.begin_name_entry("mission")
                else:
                    game.select_mission_without_starting(game.mission_builder_draft())
                return
            if key == "r":
                game.mission_builder_field_index = 0
                game.mission_builder_name_index = 0
                game.mission_builder_custom_name = ""
                game.mission_builder_map_index = game.main_menu_index
                game.mission_builder_theme_index = 0
                game.mission_builder_objective_index = 0
                game.mission_builder_parameter = 3
                game.messages = ["Mission builder reset."]
                return
            return

    if game.main_menu_mode == "tutorial":
        modes = game.tutorial_modes()
        if key in ("ESC", "c", "m", "x"):
            game.main_menu_mode = "home"
            return
        if key in ("UP", "w", "LEFT", "a"):
            game.tutorial_menu_index = (game.tutorial_menu_index - 1) % len(modes)
            return
        if key in ("DOWN", "s", "RIGHT", "d"):
            game.tutorial_menu_index = (game.tutorial_menu_index + 1) % len(modes)
            return
        if key in ("ENTER", "SPACE", "z"):
            game.start_tutorial_from_main_menu()
            return
        return

    if game.main_menu_mode == "bestiary":
        roster = game.bestiary_filtered_roster()
        if key in ("ESC", "c", "x"):
            game.main_menu_mode = "home"
            return
        if key == "f":
            game.cycle_bestiary_filter(1)
            return
        if key in ("UP", "w", "LEFT", "a") and roster:
            game.bestiary_enemy_index = (game.bestiary_enemy_index - 1) % len(roster)
            return
        if key in ("DOWN", "s", "RIGHT", "d") and roster:
            game.bestiary_enemy_index = (game.bestiary_enemy_index + 1) % len(roster)
            return
        if key in ("ENTER", "SPACE", "z") and roster:
            selected_name = roster[game.bestiary_enemy_index % len(roster)]
            full_roster = game.enemy_roster_names()
            game.encounter_enemy_index = full_roster.index(selected_name) if selected_name in full_roster else 0
            game.main_menu_mode = "encounter"
            return
        return

    if game.main_menu_mode == "companions":
        if key in ("ESC", "m", "x"):
            game.main_menu_mode = "home"
            return
        if key in ("UP", "w"):
            game.companion_editor_field_index = (game.companion_editor_field_index - 1) % len(game.companion_editor_fields())
            return
        if key in ("DOWN", "s"):
            game.companion_editor_field_index = (game.companion_editor_field_index + 1) % len(game.companion_editor_fields())
            return
        if key in ("LEFT", "a"):
            game.cycle_companion_editor_field(-1)
            return
        if key in ("RIGHT", "d"):
            game.cycle_companion_editor_field(1)
            return
        if key in ("ENTER", "SPACE", "z"):
            if game.companion_editor_fields()[game.companion_editor_field_index % len(game.companion_editor_fields())] == "Name":
                game.begin_name_entry("companion")
            else:
                game.create_custom_companion()
            return
        if key in ("BACKSPACE", "\b", "\x7f"):
            game.delete_last_custom_companion()
            return
        if key == "r":
            game.companion_editor_field_index = 0
            game.companion_editor_name_index = 0
            game.companion_editor_custom_name = ""
            game.companion_editor_glyph_index = 0
            game.companion_editor_color_index = 0
            game.companion_editor_archetype_index = 0
            game.companion_editor_class_index = 0
            game.companion_editor_subclass_index = 0
            game.companion_editor_weapon_index = 0
            game.companion_editor_add_to_party = True
            game.companion_editor_manual_control = False
            game.messages = ["Companion editor draft reset."]
            return
        return

    if game.main_menu_mode == "party":
        if key in ("ESC", "x"):
            game.main_menu_mode = "home"
            return
        if key in ("UP", "w", "LEFT", "a"):
            game.party_menu_index = (game.party_menu_index - 1) % len(game.heroes)
            return
        if key in ("DOWN", "s", "RIGHT", "d"):
            game.party_menu_index = (game.party_menu_index + 1) % len(game.heroes)
            return
        if key == "c":
            hero = game.heroes[game.party_menu_index % len(game.heroes)]
            game.cycle_hero_color(hero, 1)
            return
        if key in ("ENTER", "SPACE", "z"):
            game.toggle_party_member()
            return
        return

    if game.main_menu_mode == "loadout":
        if key in ("ESC", "x"):
            game.main_menu_mode = "home"
            return
        if key in ("LEFT", "a"):
            game.loadout_hero_index = (game.loadout_hero_index - 1) % len(game.heroes)
            game.loadout_menu_index = 0
            return
        if key in ("RIGHT", "d"):
            game.loadout_hero_index = (game.loadout_hero_index + 1) % len(game.heroes)
            game.loadout_menu_index = 0
            return
        if key == "c":
            game.loadout_slot_index = (game.loadout_slot_index + 1) % len(game.equipment_slots())
            game.loadout_menu_index = 0
            return
        options = game.loadout_options()
        if key in ("UP", "w"):
            game.loadout_menu_index = (game.loadout_menu_index - 1) % len(options)
            return
        if key in ("DOWN", "s"):
            game.loadout_menu_index = (game.loadout_menu_index + 1) % len(options)
            return
        if key in ("ENTER", "SPACE", "z"):
            game.apply_loadout_option()
            return
        return

    if game.main_menu_mode == "objectives":
        if key in ("ESC", "c", "m", "x"):
            game.main_menu_mode = "home"
            return
        if key in ("LEFT", "a"):
            game.cycle_objective_mode(-1)
            return
        if key in ("RIGHT", "d"):
            game.cycle_objective_mode(1)
            return
        if key in ("UP", "w"):
            game.adjust_objective_parameter(1)
            return
        if key in ("DOWN", "s"):
            game.adjust_objective_parameter(-1)
            return
        if key == "r":
            game.objective_mode = "Defeat All"
            game.messages = ["Objective reset to Defeat All."]
            return
        if key in ("ENTER", "SPACE", "z"):
            game.start_battle_from_main_menu()
            return
        return

    if game.main_menu_mode == "encounter":
        if key in ("ESC", "c", "x"):
            game.main_menu_mode = "home"
            return
        rows = game.encounter_builder_rows()
        if key in ("UP", "w"):
            game.encounter_enemy_index = (game.encounter_enemy_index - 1) % len(rows)
            return
        if key in ("DOWN", "s"):
            game.encounter_enemy_index = (game.encounter_enemy_index + 1) % len(rows)
            return
        if key in ("LEFT", "a"):
            game.encounter_adjust_selected(-1)
            return
        if key in ("RIGHT", "d"):
            game.encounter_adjust_selected(1)
            return
        if key in ("ENTER", "SPACE", "z"):
            game.encounter_activate_selected()
            return
        return

    if game.main_menu_mode == "classes":
        if key in ("ESC", "c", "x"):
            if game.class_screen_depth > 0:
                game.class_screen_depth -= 1
            else:
                game.main_menu_mode = "home"
            return
        if key in ("LEFT", "a"):
            if game.class_screen_depth > 0:
                game.class_screen_depth -= 1
            else:
                game.main_menu_mode = "home"
            return
        if key in ("RIGHT", "d"):
            if game.class_screen_depth == 0:
                game.sync_class_menu_to_current_hero()
                game.class_screen_depth = 1
            elif game.class_screen_depth == 1:
                hero = game.current_class_hero()
                class_name = game.selected_class_for_class_screen()
                if game.focus_class_for_hero(hero, class_name):
                    game.class_screen_depth = 2
            return
        if key == "v":
            game.cycle_current_hero_subclass(1)
            return

        if game.class_screen_depth == 0:
            if key in ("UP", "w"):
                game.class_menu_hero_index = (game.class_menu_hero_index - 1) % len(game.heroes)
                game.sync_class_menu_to_current_hero()
                return
            if key in ("DOWN", "s"):
                game.class_menu_hero_index = (game.class_menu_hero_index + 1) % len(game.heroes)
                game.sync_class_menu_to_current_hero()
                return
            if key in ("ENTER", "SPACE", "z"):
                game.sync_class_menu_to_current_hero()
                game.class_screen_depth = 1
                return
            return

        if game.class_screen_depth == 1:
            names = game.class_names()
            if key in ("UP", "w") and names:
                game.class_menu_class_index = (game.class_menu_class_index - 1) % len(names)
                return
            if key in ("DOWN", "s") and names:
                game.class_menu_class_index = (game.class_menu_class_index + 1) % len(names)
                return
            if key in ("ENTER", "SPACE", "z") and names:
                hero = game.current_class_hero()
                class_name = game.selected_class_for_class_screen()
                if game.focus_class_for_hero(hero, class_name):
                    game.class_screen_depth = 2
                return
            return

        tree = game.class_tree_for(game.hero_class(game.current_class_hero()))
        if key in ("UP", "w") and tree:
            game.class_skill_index = (game.class_skill_index - 1) % len(tree)
            return
        if key in ("DOWN", "s") and tree:
            game.class_skill_index = (game.class_skill_index + 1) % len(tree)
            return
        if key == "r":
            game.respec_current_class()
            return
        if key in ("ENTER", "SPACE", "z"):
            game.unlock_current_class_skill()
            return
        return

    if game.main_menu_mode == "maps":
        if key in ("ESC", "c", "x"):
            if game.map_detail_open:
                game.map_detail_open = False
            else:
                game.main_menu_mode = "home"
            return
        if key in ("UP", "w", "LEFT", "a"):
            game.main_menu_index = (game.main_menu_index - 1) % len(game.maps)
            game.map_detail_open = False
            return
        if key in ("DOWN", "s", "RIGHT", "d"):
            game.main_menu_index = (game.main_menu_index + 1) % len(game.maps)
            game.map_detail_open = False
            return
        if key in ("ENTER", "SPACE", "z"):
            if game.map_detail_open:
                game.select_map_without_starting()
            else:
                game.map_detail_open = True
            return
        return

    game.main_menu_mode = "home"
    return


