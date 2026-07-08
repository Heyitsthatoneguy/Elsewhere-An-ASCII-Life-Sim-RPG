# Building Elsewhere for Windows

The release build is a 64-bit Windows console application assembled with
PyInstaller. Build it on Windows; PyInstaller does not cross-compile.

## Requirements

- 64-bit Python 3.11 or later
- PowerShell
- The exact build dependency in `requirements-build.txt`

Use a currently maintained Python patch release for anything uploaded
publicly. `BUILD_INFO.txt` records the exact interpreter and packaging
dependencies used for each archive.

Build and test the release:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1
```

The script creates an isolated `.build-venv`, installs the pinned build tool,
runs all project verification, creates the standalone folder, copies the
project and Python licenses, launches the packaged executable with `--version`
and an isolated `--self-check`, and creates:

```text
dist\Elsewhere-0.9.0-beta.2-windows-x64.zip
dist\Elsewhere-0.9.0-beta.2-windows-x64.zip.sha256
```

Use `-SkipTests` only when iterating locally; public builds should always run
the complete verification.

Packaged saves are written to `%LOCALAPPDATA%\Elsewhere`, not into the
application folder. A portable save found beside the executable is copied
there automatically the first time a packaged build starts. Portable custom
content and its recovery copies are migrated at the same time.

See `RELEASE_CHECKLIST.md` before publishing an archive.
