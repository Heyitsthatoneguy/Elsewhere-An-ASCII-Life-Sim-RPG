# Changelog

## 0.9.0-beta.4

- Added persistent world abilities: learned built-in and custom skills can use
  their combat range and area shapes to ignite or extinguish vegetation, water
  crops, freeze water into ice bridges, raise temporary stone crossings, clear
  loose obstacles, restore scorched ground, and produce other elemental terrain
  effects. Effects react to weather and seasons, remain visible across seamless
  wilderness chunks, affect traversal, persist in saves, and protect actors,
  structures, furniture, landmarks, crops, and dropped items from invalid casts.
- Added V/Adventure > World abilities, universal Water Weave, level-gated Trail
  Gust and Verdant Touch field techniques, no-effect/no-MP safeguards, terrain
  inspection details, tutorials, and explicit world affinities in the custom
  ability builder.
- Expanded world abilities with four-rank affinity mastery, duration and MP-cost
  progression, steam/mud/electricity/flash-freeze/overgrowth reactions, direct
  Z/Enter effect management, crop-safe casting, and temporary crossings that
  cannot expire beneath the player.
- Added bounded physical wilderness-fire spread with deterministic propagation,
  wet and nonflammable firebreaks, rain suppression, strict generation/quantity
  limits, and complete town/farm-spread protection.
- Made field casting seamless across loaded neighboring wilderness chunks, with
  full area-shape previews, correct remote terrain/effect mutation, neighboring
  actor and town protection, saved last-ability memory, and Y quick-casting.
- Embedded the complete starting town, expandable farm, and physical mine into
  the persistent wilderness at their original scale. A real ravine passage,
  outward roads, spatially matched doors, global coordinates, and save migration
  replace exterior Farm/Town transitions and miniature hub representations.
- Overhauled player households for the seamless world. Spouses retain careers,
  identity colors, public routines, and residence-aware schedules; children move
  between home, farm, town, library, and market according to age, time, weather,
  and weekday. Added household priorities, weekly check-ins, planned outings,
  richer wedding choices, persistent memories, and a household dashboard.
- Added dynamic family lives for generated residents, including relationships,
  marriage before cohabitation, children, household growth, aging, and persistent
  family records across procedural settlements.
- Added Legacy Permadeath and True Permadeath settings. Legacy mode can continue
  through an eligible child, while existing ageless and ordinary lifespan modes
  remain available.
- Unified the player ability menu across exploration and combat. Learned combat
  skills remain visible outside encounters, support abilities gain field uses,
  nearby hostiles restore tactical engagement, and several common abilities now
  have stronger tactical identities and persistent battlefield effects.
- Added traditional dungeon exploration memory: rooms remain hidden until entered
  or opened, current visibility stays distinct from mapped terrain, and hidden
  enemies, loot, traps, and descriptions no longer leak through darkness.
- Rebuilt traps into concealed mechanisms with perception-based discovery,
  bounded searching, distinct effects, real disarming consequences, recovered
  materials, and enemy interaction.
- Completed physical containers across authored and procedural interiors,
  wilderness sites, outposts, player residences, combat remains, and dungeons.
  Added semantic fixture contents, persistent relocation/depletion, bulk storage,
  continuous take/inspect browsing, recovered valuables and utility items, and
  local-only property storage access.
- Gave each regional wilderness specialist one persistent physical home, daily
  field routine, journal, relationship memory, lessons, specimen work, and route
  development, while reducing excessive generic traveler populations.
- Improved founded-town performance with bounded resident pathfinding and cached
  occupancy lookups, substantially reducing slowdowns in populated interiors and
  player-built settlements.
- Fixed false wilderness-structure and dungeon transitions caused by shared
  building glyphs, restoring safe collision with authored and generated facades.
- Repaired seamless farming synchronization. Tilling, planting, watering,
  harvesting, fertilizer, debris clearing, overnight weather, sprinklers,
  automation, area tools, area sowing, livestock movement, and Grand Farm
  cross-boundary behavior now share canonical farm coordinates.

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
