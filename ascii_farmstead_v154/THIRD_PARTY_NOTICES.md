# Third-party notices

Elsewhere's source code uses only the Python standard library. No external
Python packages, third-party game engines, fonts, music, images, or other
assets are currently vendored in this repository.

## Python

Running the source requires Python 3.11 or later. Python is distributed under
the Python Software Foundation License Version 2 and includes components under
additional compatible licenses:

https://docs.python.org/3/license.html

The source release does not redistribute Python itself.

A standalone executable build may bundle a Python runtime. Every such binary
release must include the complete license and acknowledgements supplied with
the exact Python version used to build it. The official Windows build script
copies that file into the release as `PYTHON_LICENSE.txt`.

## PyInstaller

PyInstaller may be used as release tooling to create standalone executable
bundles. It is not part of the source runtime. PyInstaller's license exception
allows generated bundles to be distributed under the project's chosen
license and does not require PyInstaller attribution:

https://pyinstaller.org/en/stable/license.html

The reproducible beta build currently uses PyInstaller 6.19.0.

## Generative AI

Some portions of this project were created with generative AI assistance from
OpenAI Codex. OpenAI is not represented as an author, publisher, sponsor, or
endorser of the project.
