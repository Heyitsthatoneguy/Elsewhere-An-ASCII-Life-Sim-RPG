# Changelog

## 0.9.0-beta.3

- Added a universal persistent container system for chests, shelves, cabinets,
  ruins, shop displays, player furniture, and defeated enemies. Container menus
  support inspection, selective transfer, deposits, and `R` to take everything
  that fits.
- Added a 200-unit backpack limit, compact material/seed stacking, unlimited
  General Store expansions, individual property storage, old-save storage
  migration, and recoverable dropped packs for rewards that do not fit.
- Rebuilt map-native dungeon combat around physical positioning, persistent HP,
  equipment skills and focus, melee/ranged attacks, tactical companions, cover,
  sound awareness, doors, concealed traps, searchable remains, and mega-dungeons.
- Expanded companion movement with adaptive formation and single-file modes,
  breadcrumb following through interiors, catch-up movement, regrouping, and
  stronger tactical positioning.
- Reworked farm animals with growth stages, affection, personalities, feeding,
  grooming, pasture routines, illness, care streaks, and species-specific product
  quality and timing.
- Greatly expanded persistent wilderness generation with seamless chunk
  presentation, connected meaningful roads, physical landmarks and interiors,
  regional travelers, environmental events, sub-biomes, expeditions, restoration,
  trade consequences, oceans, islands, currents, docks, ferries, rafts, and
  water travel.
- Integrated the starting farm, town routes, and mine into the origin wilderness
  region, with neutral boundary roads, resident commutes, wayfinding, and
  season/weather-aware terrain, forage, water, and winter ice.
- Improved generated towns, authored interiors, building variety, NPC schedules,
  crowd movement, dialogue context, naturalist residency, shops, roads, and
  enterable wilderness structures.
- Added numpad movement throughout exploration and map-native combat, including
  diagonal corner safety and numpad-5 waiting.
- Improved terminal graphics with semantic palettes, connected architecture,
  lighting, weather depth, terrain texture, actor emphasis, and clearer tactical
  overlays.
- Improved wilderness/interior performance with cached actor and occupancy
  lookups, smoother streamed rendering, bounded navigation work, and constant-time
  inventory capacity accounting.
- Fixed compact-material take-all transfers stopping behind a full-sized item,
  raft test interference from generated encounters, stale storage routing, loot
  auto-collection inconsistencies, and numerous menu, transition, NPC, building,
  weather, and cross-boundary edge cases.

- New games now wake at 7:00 AM in full daylight. Wake time can be changed from
  4:00 AM through noon in startup or in-game Settings and persists in saves.
- Replaced the farm and town's misleading compass-letter transitions with
  neutral, walkable road openings at their real boundaries, including cleanup
  for old expanded-town saves.
- Expanded the seamless origin region with a connected home road, readable
  wayfinding signs, a fenced farm precinct, and a physical mine building.
  Wilderness travelers recognize and follow the routes to Elsewhere, Home Farm,
  and Home Mine.
- Added recurring same-day resident commutes on the home road. Garrick works the
  mine route, while Cora, Rowan, and Hana make schedule-, season-, household-,
  festival-, and weather-aware farm journeys. Residents are absent from town
  while physically traveling, retain their authored dialogue and relationships,
  and can be accompanied through a smaller local `Walk together` activity.
- Wilderness terrain now responds visually to season and weather across streamed
  chunk boundaries. Inland freshwater freezes into traversable winter ice while
  coastal water remains open; thawing safely moves stranded players to shore.
- Improved seasonal forage cleanup and winter yields across persistent wilderness
  chunks.

## 0.9.0-beta.2

- Added wilderness-town sheriff offices, Sheriff/Deputy jobs, weekly bounty
  boards, active bounty tracking, overworld bounty markers, wilderness bounty
  targets, tactical bounty combat, turn-in rewards, and an Adventure >
  Bounties dashboard.
- Improved generated and player-founded town support for the new public-safety
  buildings while preserving residential population variety.
- Fixed bounty target spawning so it no longer recursively conflicts with
  wilderness animal placement.
- Improved civic exterior marker placement for more varied procedural town
  layouts.

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
