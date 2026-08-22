# Known issues

- Elsewhere is a large public beta. Keep a manual save-slot copy of especially
  important dynasties before updating between beta versions.
- The game is designed for a modern terminal. Very small terminal windows may
  make panels harder to read; enlarging the window restores the intended
  layout.
- Antivirus tools can occasionally inspect or delay unsigned independently
  distributed executables. The source release remains available as an
  alternative.
- Existing saves retain legacy filenames beginning with
  `ascii_farmstead_` for compatibility.
- The Windows executable is not digitally signed. Windows or antivirus tools
  may therefore show a reputation warning on first launch. Verify that the
  archive came from the project's official release location.

When reporting a problem, include the game version, what you were doing, and
the generated crash report or debug log. The in-game Save Location screen
shows where these files are stored.

If startup fails before that screen appears, run `Elsewhere.exe --self-check`
from a terminal. Custom content and save data are stored under
`%LOCALAPPDATA%\Elsewhere` in the Windows build.
