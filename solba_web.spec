# solba_web.spec — PyInstaller spec file para SolbaBackups Web
#
# Uso:
#   pyinstaller solba_web.spec
#
# Genera: dist/SolbaBackups/SolbaBackups.exe (modo onedir, más rápido al arrancar)
# Para un solo archivo: cambiar onefile=True (arranque más lento, ~10-15s en Windows)

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------------
# Archivos de datos adicionales a incluir en el bundle
# Formato: (origen_en_disco, destino_dentro_del_bundle)
# ---------------------------------------------------------------------------
added_files = [
    # Frontend completo
    ('src/frontend', 'src/frontend'),
    # Certificados SSL (necesarios para requests HTTPS de google-auth)
    ('venv/Lib/site-packages/certifi/cacert.pem', 'certifi'),
    # Archivo de configuración de variables de entorno
    ('.env', '.'),
    # Credenciales de Google Drive (OAuth2 / Service Account)
    ('credentials.json', '.'),
    # Token de sesión OAuth2 de Google Drive (demo pre-autorizada)
    ('token.json', '.'),
]

# ---------------------------------------------------------------------------
# Hidden imports (módulos que PyInstaller no detecta automáticamente)
# ---------------------------------------------------------------------------
hidden_imports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'apscheduler.triggers.cron',
    'apscheduler.triggers.interval',
    'apscheduler.schedulers.background',
    'apscheduler.executors.pool',
    'apscheduler.jobstores.memory',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.orm',
    'cryptography.hazmat.backends.openssl',
    'google.auth.transport.requests',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
]

a = Analysis(
    ['solba_web.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Excluir módulos de test y desarrollo para reducir tamaño
        'pytest', 'pylint', 'flake8', 'black',
        'tkinter', 'matplotlib', 'numpy', 'pandas',
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
    name='SolbaBackups',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Sin ventana de consola (app GUI/web)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/frontend/assets/logo_solba.ico',  # Icono añadido
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SolbaBackups',
)
