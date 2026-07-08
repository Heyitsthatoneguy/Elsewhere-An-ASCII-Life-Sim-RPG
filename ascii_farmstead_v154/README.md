# Elsewhere: an ASCII Life-Sim RPG

Elsewhere is a free terminal life-sim RPG about farming, relationships,
families, exploration, tactical combat, wilderness settlements, business,
politics, and lives that can continue across generations.

Current release: `0.9.0-beta.2`

## Windows download

Download the latest verified Windows archive from the
[GitHub Releases page](https://github.com/Heyitsthatoneguy/Elsewhere-An-ASCII-Life-Sim-RPG/releases).

The standalone Windows release does not require Python. Extract the complete
zip archive, then run:

```text
Elsewhere.exe
```

Do not remove the `_internal` folder beside the executable.

The release page also provides a `.sha256` file for verifying the downloaded
ZIP before extraction.

## Running from source

Elsewhere requires Python 3.11 or later and uses only the Python standard
library.

On Windows, double-click:

```text
run_elsewhere.bat
```

Or run:

```text
python elsewhere.py
```

For best results, use Windows Terminal or another modern terminal with UTF-8
and ANSI color support.

## Main controls

```text
WASD / arrows   Move
F               Use selected tool
Q / E           Cycle tools
1 / 2           Cycle owned seed types
Z / Enter       Interact, confirm, or place
I               Inspect target
L               Look cursor
Tab             Player menu
K               Calendar
H               Help
S               Save
Esc twice       Quit
```

Menus use arrows or WASD to move, Z/Enter to confirm, and X/Esc/Q to go back.
The in-game Help and Tutorials screens contain more detailed instructions.

## Saving

The game autosaves during important actions and supports a current save plus
three manual save slots. The internal filenames retain the old
`ascii_farmstead_*` prefix so existing development saves remain compatible
after the project rename.

Every save is committed atomically. Before replacing an existing save,
Elsewhere keeps three rolling recovery copies and automatically tries them if
the current file becomes unreadable.

Custom content uses the same safeguards: atomic writes, three rolling recovery
copies, automatic restoration, and preservation of an unreadable file for
diagnosis.

Standalone Windows builds store saves and crash reports in:

```text
%LOCALAPPDATA%\Elsewhere
```

Source builds retain portable saves beside the source files. Set the
`ELSEWHERE_DATA_DIR` environment variable to use a custom location.

Use `Tab > System > Save Manager` to save, load, copy, delete, or inspect save
locations.

## Custom combat content

Choose `Custom Content` on the title menu to create original tactical
abilities and classes. The guided editor supports attacks, support abilities,
statuses, attack shapes, elemental zones, class skill trees, mastery arts,
recommended elemental subclasses, enemies, craftable equipment, and combat
maps. Custom maps become playable contracts on the in-game Combat Mission
Board.

Optional dungeon-room templates can also be created. They are disabled by
default and only decorate ordinary room interiors when enabled. The procedural
dungeon layout, corridors, entrances, boss rooms, and safe fallback generation
remain intact.

Custom content is shared by all saves and stored as readable JSON:

```text
custom_content.json
```

Use the editor's export and import options to share a complete custom library.
Imported values are validated and bounded before combat can use them.
Built-in classes and abilities cannot be overwritten.

If the game will not reach the title menu, open a terminal in the extracted
folder and run:

```text
Elsewhere.exe --self-check
```

This checks data-folder access, farm initialization, custom-content recovery,
and tactical-content validity without starting a play session.

## Beta status

This is a large public-beta project. Keep backups of important saves and
include the crash report and relevant log when reporting a bug.

Please report reproducible problems through
[GitHub Issues](https://github.com/Heyitsthatoneguy/Elsewhere-An-ASCII-Life-Sim-RPG/issues).
See `CONTRIBUTING.md` before submitting code changes.

Useful verification commands for contributors:

```text
python smoke_test.py
python -m ascii_battle_prototype.combat.smoke_tests
python -m ascii_battle_prototype.combat.main --validate-content
```

## License

Elsewhere is available under the Zero-Clause BSD License (`0BSD`). You may
use, copy, modify, and redistribute it for any purpose, with or without a fee
and without requesting additional permission.

See:

- `LICENSE`
- `CREDITS.md`
- `THIRD_PARTY_NOTICES.md`

Some portions of the project were created with generative AI assistance from
OpenAI Codex.

Release builders should see `BUILDING.md`.
