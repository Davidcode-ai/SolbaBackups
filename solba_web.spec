# solba_web.spec — PyInstaller spec file para SolbaBackups Web
#
# Uso:
#   pyinstaller solba_web.spec --noconfirm
#
# Genera: dist/SolbaBackups/SolbaBackups.exe (modo onedir)

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------------
# Archivos de datos adicionales
# ---------------------------------------------------------------------------
added_files = [
    ("src/frontend", "src/frontend"),
]
added_files += collect_data_files("certifi")

# No empaquetar .env ni OAuth en el ejecutable: en builds locales incluiría secretos.
# Tras instalar, el usuario copia credentials.json / token.json al directorio de la app y edita .env.

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.interval",
    "apscheduler.schedulers.background",
    "apscheduler.executors.pool",
    "apscheduler.jobstores.memory",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.orm",
    "cryptography.hazmat.backends.openssl",
    "google.auth.transport.requests",
    "google_auth_oauthlib.flow",
    "googleapiclient.discovery",
]

a = Analysis(
    ["solba_web.py"],
    pathex=["."],
    binaries=[],
    datas=added_files,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "pylint",
        "flake8",
        "black",
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
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
    [],
    exclude_binaries=True,
    name="SolbaBackups",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="src/frontend/assets/logo_solba.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SolbaBackups",
)
