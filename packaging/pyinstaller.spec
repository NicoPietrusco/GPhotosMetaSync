# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for desktop releases."""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

ROOT = Path(SPECPATH).parent
PACKAGE = ROOT / "src" / "gphotometasync"

datas = [
    (str(PACKAGE / "core" / "metadata_fields.yaml"), "gphotometasync/core"),
    (str(PACKAGE / "web" / "static"), "gphotometasync/web/static"),
    (str(PACKAGE / "web" / "templates"), "gphotometasync/web/templates"),
    *copy_metadata("gphotometasync"),  # lets importlib.metadata report __version__
]

oauth_client = Path(
    os.environ.get("GOOGLE_OAUTH_CLIENT_SECRETS", ROOT / "credentials" / "client_secrets.json")
)
if oauth_client.is_file():
    datas.append((str(oauth_client), "credentials"))
else:
    print("Building without a Google OAuth client; Google Photos sign-in will be unavailable.")

a = Analysis(
    [str(PACKAGE / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Photo Meta Sync",
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Photo Meta Sync",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Photo Meta Sync.app",
        bundle_identifier="com.nicopietrusco.gphotometasync",
    )