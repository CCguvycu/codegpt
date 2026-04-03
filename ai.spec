# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for CodeGPT -> ai.exe

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['ai_cli/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('chat.py', '.'),
        ('CLAUDE.md', '.'),
    ],
    hiddenimports=[
        'requests',
        'rich',
        'rich.console',
        'rich.markdown',
        'rich.panel',
        'rich.table',
        'rich.text',
        'rich.live',
        'rich.rule',
        'rich.align',
        'prompt_toolkit',
        'prompt_toolkit.history',
        'prompt_toolkit.completion',
        'prompt_toolkit.styles',
        'ai_cli',
        'ai_cli.__main__',
        'ai_cli.updater',
        'ai_cli.doctor',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'textual',
        'telegram',
        'flask',
        'groq',
        'flet',
        'tkinter',
        'unittest',
        'xmlrpc',
        'pydoc',
        'doctest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ai',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
