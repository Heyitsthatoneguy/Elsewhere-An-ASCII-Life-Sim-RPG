# Elsewhere release checklist

1. Run the complete Windows build without `-SkipTests`.
2. Confirm the packaged `--version` and `--self-check` both pass.
3. Extract the ZIP into a new empty folder and launch `Elsewhere.exe`.
4. Create a temporary game, save it, quit, and successfully continue it.
5. Open Custom Content, create one harmless test record, then remove it.
6. Verify `README.md`, `LICENSE`, `CREDITS.md`,
   `THIRD_PARTY_NOTICES.md`, `CHANGELOG.md`, `KNOWN_ISSUES.md`,
   `PYTHON_LICENSE.txt`, and `BUILD_INFO.txt` are inside the archive.
7. Upload the Windows ZIP and its `.sha256` file together.
8. Publish the checksum in the release notes and identify the executable as
   unsigned so users know a first-launch reputation warning is possible.
9. Keep an untouched copy of the exact uploaded archive and checksum.

Do not publish a build produced with `-SkipTests`.
