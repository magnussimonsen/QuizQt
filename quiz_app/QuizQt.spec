# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

SPEC_FILE = Path(sys.argv[0]).resolve()
PROJECT_ROOT = SPEC_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / 'quiz_app' / 'data'

quizqt_datas = collect_data_files('quiz_app', includes=['data/*', 'data/**/*'])

if DATA_DIR.exists():
    seen_entries = {(Path(src).resolve(), dest) for src, dest in quizqt_datas}
    for file_path in DATA_DIR.rglob('*'):
        if not file_path.is_file():
            continue
        destination_dir = str(file_path.relative_to(PROJECT_ROOT).parent)
        entry = (file_path.resolve(), destination_dir)
        if entry in seen_entries:
            continue
        quizqt_datas.append((str(file_path), destination_dir))
        seen_entries.add(entry)

a = Analysis(
    ['../app_main.py'],
    pathex=[],
    binaries=[],
    datas=quizqt_datas,
    hiddenimports=['uvicorn', 'fastapi', 'pydantic', 'quiz_app'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='QuizQt',
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
)
