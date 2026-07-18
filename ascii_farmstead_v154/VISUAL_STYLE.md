# Elsewhere visual language

Elsewhere uses a semantic ASCII style: characters communicate function first,
while color communicates material, environment, state, and atmosphere. Collision
and interaction logic must never be inferred from decorative color alone.

## Core glyphs

- `.` clear ground or ordinary floor
- `,` textured ground, vegetation, or carpet according to context
- `:` prepared path or subtle room trim
- `=` major road, bridge, or engineered crossing
- `~` water
- `#` solid wall, cliff, or impassable structure
- `D`, `+`, `_`, `|` entrances and door states
- `<`, `>` vertical travel
- `@` player or individual actor
- `&` traveling group, merchant, or caravan
- `$`, `P` commerce and staffed services
- `◆` major natural landmark anchor
- `≡` dock, pier, or water-travel anchor

Special landmarks and resources may use additional glyphs, but should not
replace these meanings inside the same context.

When detailed map glyphs are enabled, stored `#` architecture is shaped at
render time with box-drawing corners, joins, and straight wall segments. Sparse
`o` windows may replace straight exterior wall segments visually. The stored
tile remains `#`, so movement, inspection, editing, and saves are unchanged.
Natural cliffs continue to use rough `#` glyphs rather than architectural lines.

## Palette rules

- Floors are neutral white, warm cream, or gray. Brown is reserved for wood.
- Roads are neutral gray or muted ochre; gold identifies services and commerce.
- Green identifies ordinary vegetation, with distinct forest and wetland hues.
- Cyan and blue identify water; animated variation changes hue, not collision.
- Red is reserved for immediate danger, hostility, or invalid placement.
- Violet identifies fungi, unusual ecology, or magical phenomena.
- Doors remain brown so entrances are recognizable in otherwise neutral rooms.
- Lamps and occupied fires use warm light.

## Rendering layers

The current terminal renderer draws in this conceptual order:

1. Terrain and architecture
2. Decorative and civic overlays
3. Furniture and functional objects
4. Creatures, NPCs, followers, and the player
5. Weather and temporary effects when a cell is otherwise unobstructed
6. Interface and contextual guidance

Decorative additions must not create collision or duplicate interactions.

## Actor hierarchy

Actors use foreground contrast above terrain. The player remains bright white;
active companions use bright cyan and may use `&`; spouses and children use a
warm family tone; ordinary residents retain profession colors with stronger
contrast; regional travelers use blue, green, violet, stone, or gold according
to their work. Wildlife remains quieter than people. Hostiles remain red, while
elite and bounty targets use uppercase silhouettes and bounty targets receive a
distinct magenta-red role. Color-free play still distinguishes the main groups
through `@`, `&`, species letters, and uppercase danger silhouettes.

## Landmark hierarchy

The terrain surrounding a landmark communicates its physical form. Its central
anchor communicates use: `◆` marks a major natural destination, `≡` marks water
travel, `D` marks an enterable wilderness building, and the existing camp,
ruin, overlook, shelter, and station letters retain their meanings with stronger
semantic colors. These are display substitutions only; interaction continues to
read the original saved marker.

## Authored town exteriors

The authored town's stored service letters remain authoritative for collision,
inspection, restoration, and entrances. The renderer presents each connected
letter footprint as a complete building instead: outlined roof edges, patterned
roof fields, a lower façade, warm windows, and an emphasized `D` entrance.
Shops use light trim, forge and carpentry buildings use heavy trim, and civic or
cultural buildings use formal double-line trim. Roof material and texture vary
across shops, homes, the clinic, inn, library, museum, workshops, market, and
Town Hall. Unrestored buildings are dim, their windows use solid shutters, and
the three `Q` entrance markers display as continuous wooden planks. Disabling Detailed map
glyphs restores the original footprint letters.

## Farm presentation

The fixed farmhouse uses the same render-only massing principle as town
architecture, with a warm residential roof, lower façade, lit window, and clear
door; a deluxe farmhouse receives its own roof material. Player-placed Storage
Sheds, Wells, Chicken Coops, Animal Pens, Tool Sheds, and Fish Ponds render as
coherent multi-cell structures while retaining one central functional letter.
Their stored object name, anchor, footprint, collision, and interaction remain
unchanged, so they can still be moved normally in build mode.

Adjacent player-built Fences, Stone Paths, and Pipe Segments connect visually
with straights, corners, branches, and crossings. Isolated pieces retain their
ordinary symbol. The fixed farm boundary is also line-shaped, and farm pond
water shares the restrained ambient water surface used by the wilderness.
Disabling Detailed map glyphs restores the farmhouse `H` footprint, repeated
farm-building symbols, and original one-cell network symbols.

## Underground presentation

Mines, natural caves, and constructed dungeons share navigation conventions but
not architecture. Mine and cave walls use rough stone faces; dungeon walls use
connected masonry. Floors remain neutral gray and receive only sparse texture,
so resources and functional objects stay legible. Underground water may alternate
between `~` and `≈` without changing collision.

Exits and stairs use the brightest warm navigation role. Dungeon doors remain
brown, treasure and gold use gold, traps use danger red, and shrines or final
chambers use a violet relic role. Copper, iron, coal, crystal, gem, clay, fungi,
and herbs retain separate material colors. Crystals, shrines, and final chambers
may cast a small stable light accent on nearby floor cells; this is atmosphere,
not a visibility or stealth mechanic.

Detailed glyphs may show crystal deposits and relic markers as diamonds, natural
stone as shaded faces, architectural walls as box drawing, and water as `≈`.
The stored letters remain authoritative for inspection and interaction. Turning
Detailed map glyphs off restores those original letters and `#` walls.

## Tactical combat presentation

Combat terrain is quieter than actors and previews. Open ground uses a muted
neutral value; dirt, grass, mud, bridge timber, stone, walls, trees, water, ice,
thorns, springs, crystals, crates, and barrels use material-specific colors.
Stored walls may become connected line segments, and detailed mode may show
water, bridge, cover, spring, and crystal display glyphs without changing the
battle map or its movement and cover rules.

Heroes retain their chosen party colors. Enemies use danger red, with elites and
bosses receiving stronger roles. Guard, poison, root, and vulnerability may tint
the unit cell, and protected allies receive an objective background. Movement,
the chosen path, projected enemy movement, likely danger, attack reach, skill
range, area of effect, overwatch, and units that will actually be hit must remain
visually distinct from one another even without explanatory text.

Escape, hold, and destroy objectives use different glyphs. Elemental zones use
effect-specific glyphs as well as color. Detailed glyphs can be disabled to
restore simple ASCII markers, and combat launched from Elsewhere inherits both
Detailed map glyphs and High contrast preferences. Color-free mode continues to
communicate teams, routes, danger, targets, and objectives through characters.

## Exploration interface

The exploration HUD groups information by purpose instead of joining every value
into one prose line. World chips communicate date, place, season, weather, time,
and lighting. Player chips communicate identity, stamina, persistent combat
health, money, and the active tool. Context chips appear only when needed for map
size or overworld cursor, mail, mine progression, explored chunks, and buffs.

Health and stamina use fixed-width meters plus exact numbers. Low values must
change color but never rely on color alone; brackets, labels, meter fill, and
numbers remain visible in color-free mode. Detailed glyphs use solid/shaded meter
cells, while classic mode uses `#` and `-`.

Footer rows begin with stable purpose labels: `MESSAGE`, `STATUS`, `TARGET`,
`TOOL`, `ACTION`, and `CONTROLS`. Long content wraps under the available height
budget rather than overlapping the map. Menus place hints and controls below a
divider, outside selectable rows. Full-screen and compact menus share the same
border, selected state, unavailable state, and ANSI-aware width rules.

## Cartography

The wilderness overworld is a map, not a miniature simulation frame. Each chunk
occupies a fixed three-cell mark so selection brackets, the persistent current
position, and organic-region boundaries remain readable without color. Known
members of the selected variable-sized region use a dotted footprint; unknown
chunks retain an opaque fog mark and never reveal terrain early.

Map symbols communicate category before detail: homes and towns are shelter and
service anchors, roads are horizontal route strokes, water systems share a blue
family but distinguish sources, deltas, basins, open water, and ports by shape,
and claims, surveys, danger, objectives, caves, and dungeons retain strong unique
marks. The 54-column view always reserves space for destination details, the
regional key, the general legend, and controls. Detailed glyphs may be replaced
by original ASCII symbols, and High contrast strengthens categories without
changing knowledge, travel, or generation rules.

## Motion and atmosphere

Ambient animation is intentionally slow. Water changes between related blue
hues and occasionally alternates `~` with `≈`; sparse ground texture varies the
visual surface without creating objects. Fires and lamps flicker between warm
tones, nearby interior floors receive a restrained nighttime light pool, and
precipitation moves as a stable world-space field. Players can disable ambient
visuals in Settings.

Precipitation uses bright near and dim far layers. It can pass over ordinary
terrain but never replaces crops, architecture, doors, services, or functional
wilderness anchors, keeping severe weather atmospheric without hiding actions.

Time-of-day tint preserves the underlying semantic hue. Streetlamps and other
light sources remain warm and readable while surrounding outdoor tiles dim.
The default 7:00 AM wake time begins after this dawn tint; players can choose an
earlier or later start without changing the lighting rules.

Wilderness materials follow the calendar as well as the biome. Meadows, woods,
fungal hollows, wetlands, ridges, trees, and low vegetation shift through fresh,
mature, autumnal, and dormant palettes. Rain and storms cool exposed ground;
snow and blizzards lay a pale visual cover across natural terrain. Winter inland
freshwater uses a solid ice stroke and pale color, while salt coasts remain open
blue water. These treatments are render-only except for winter freshwater
traversal and seasonal forage availability.

## Accessibility

Color can be disabled entirely. High-contrast mode emphasizes terrain, water,
routes, walls, entrances, and services with brighter role-based colors. Critical
information must always remain identifiable through glyphs and text. Detailed
map glyphs can also be disabled independently, restoring the original single
character wall and terrain presentation for terminals with limited glyph support.
