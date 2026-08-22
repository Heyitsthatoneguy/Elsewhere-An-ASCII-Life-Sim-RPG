# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ["elsewhere.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("ascii_farmstead_dialogue.py", "dialogue_sources"),
        ("ascii_farmstead_dialogue_library.py", "dialogue_sources"),
        ("ascii_farmstead_relationship_dialogue.py", "dialogue_sources"),
        ("ascii_farmstead_npc_dialogue.py", "dialogue_sources"),
        ("ascii_farmstead_npcs.py", "dialogue_sources"),
        ("ascii_farmstead_family_world.py", "dialogue_sources"),
        ("ascii_farmstead_npc_families.py", "dialogue_sources"),
        ("ascii_farmstead_npc_builder.py", "dialogue_sources"),
        ("ascii_farmstead_quests.py", "dialogue_sources"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Elsewhere",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Elsewhere",
)
