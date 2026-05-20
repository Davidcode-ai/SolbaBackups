# Generar el instalador Windows (Inno Setup)

## Requisitos

- Windows 10/11 x64
- Python 3.11+ con dependencias: `pip install -r requirements_web.txt`
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) (ISCC.exe)
- `nssm.exe` en la raíz del repositorio (gestor del servicio Windows)
- Opcional para Google Drive en el instalador: `credentials.json`, `token.json` en la raíz (no se sobrescriben si ya existen)

## Build automático

```powershell
cd C:\Escritorio\BackUp-Solba
.\scripts\build_installer.ps1
```

Salida:

- `dist\SolbaBackups\` — aplicación empaquetada (PyInstaller onedir)
- `Output\SolbaSetup-3.0.0.exe` — instalador para distribuir

## Build manual

```powershell
.\venv\Scripts\python.exe -m PyInstaller solba_web.spec --noconfirm
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" SolbaSetup.iss
```

## Instalación en el equipo destino

1. Ejecutar `SolbaSetup-3.0.0.exe` como administrador.
2. Elegir inicio automático:
   - **Sesión** — acceso directo en Inicio del usuario
   - **Servicio NSSM** — recomendado en servidores (puerto 8765)
   - **Manual** — sin arranque automático
3. Abrir http://localhost:8765
4. Copiar/editar `.env` en la carpeta de instalación (`%ProgramFiles%\SolbaBackups`) con SMTP y WhatsApp.

## Subir a GitHub Releases

```bash
gh release create v3.0.0 Output/SolbaSetup-3.0.0.exe --title "SolbaBackups 3.0.0" --notes-file docs/CHANGELOG.md
```

O arrastrar el `.exe` a Releases en la web de GitHub.
