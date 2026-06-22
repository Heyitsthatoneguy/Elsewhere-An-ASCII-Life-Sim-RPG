# Changelog

## 0.9.0-beta.1

First public beta of **Elsewhere: an ASCII Life-Sim RPG**.

- Farming, crafting, automation, animals, town restoration, and exploration.
- Tactical combat, mines, wilderness dungeons, and strongholds.
- Authored and procedurally generated towns with residents, dialogue, shops,
  politics, businesses, housing, and trade.
- Romance, marriage, children, followers, households, aging, succession, and
  multi-generational play.
- Wrapped menu guidance now appears outside selectable sidebar rows.
- Marriage now uses store-bought rings, engagements, scheduled wedding dates,
  full ceremonies, widowhood records, and remarriage after a spouse's death.
- Maximum stamina now rises by 5 per player level, with primary-home comfort
  and family support contributing additional persistent capacity.
- The farmhouse and library now provide 40 in-depth, categorized guides
  covering every major activity, progression system, and configuration option.
- Added a title-menu Custom Content workshop for creating, validating,
  exporting, importing, and using original tactical abilities and classes.
- Expanded Custom Content with enemy archetypes, craftable tactical equipment,
  generated combat arenas, playable custom mission contracts, and opt-in safe
  dungeon-room templates.
- Fixed custom-content descriptions being silently truncated to the
  16-character player-name limit.
- Hardened save recovery against malformed collection, calendar, position,
  inventory, tool, festival, mail, and mine-progression fields.
- Calendar weekday calculation is now constant-time even for very old
  multi-generational dynasties.
- Fixed a corrupted snow glyph and clamped out-of-bounds saved player
  positions back inside the active map.
- Fixed removed custom abilities lingering as invalid class skills after a
  library replacement.
- Atomic saves, three rolling recovery copies, save-schema metadata, and
  automatic recovery from interrupted or corrupted saves.
- Custom-content libraries now use atomic writes, three rolling recovery
  copies, automatic restoration, and timestamped quarantine of damaged files.
- Portable packaged saves and custom-content files migrate into the normal
  per-user data directory on first launch.
- Added `Elsewhere.exe --self-check` to verify writable data storage, core
  startup, custom content, and tactical content without entering the game.
- Release builds now run the packaged self-check before archiving and produce
  a matching SHA-256 checksum file.
- Added a concise release checklist and clearer guidance for unsigned Windows
  builds and data recovery.

This beta prioritizes save compatibility and stability. Later beta releases
may rebalance progression and expand existing systems.
