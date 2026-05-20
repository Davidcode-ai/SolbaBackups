; SolbaSetup.iss — Instalador Windows (Inno Setup 6)
; Requiere: dist\SolbaBackups\ generado con PyInstaller (ver scripts/build_installer.ps1)

#define MyAppName "SolbaBackups"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Solba"
#define MyAppExeName "SolbaBackups.exe"

[Setup]
AppId={{A8F3C2E1-9B4D-4A2F-8E1C-5D6B7A9E0F12}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=SolbaSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
SetupIconFile=src\frontend\assets\logo_solba.ico
WizardImageFile=src\frontend\assets\logo_wizard.bmp
WizardSmallImageFile=src\frontend\assets\logo_wizard_small.bmp
UninstallDisplayIcon={app}\logo_solba.ico
DisableProgramGroupPage=no
LicenseFile=
InfoBeforeFile=
InfoAfterFile=

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Binarios PyInstaller (onedir)
Source: "dist\SolbaBackups\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NSSM — gestor del servicio Windows
Source: "nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
; Plantilla de configuración (no sobrescribe .env existente en actualizaciones)
Source: ".env.example"; DestDir: "{app}"; DestName: ".env"; Flags: onlyifdoesntexist
; Google Drive (opcional en build; no sobrescribir en actualizaciones)
Source: "credentials.json"; DestDir: "{app}"; Flags: onlyifdoesntexist skipifsourcedoesntexist
Source: "token.json"; DestDir: "{app}"; Flags: onlyifdoesntexist skipifsourcedoesntexist
; Icono para accesos directos
Source: "src\frontend\assets\logo_solba.ico"; DestDir: "{app}"; DestName: "logo_solba.ico"; Flags: ignoreversion

[Dirs]
Name: "{app}"; Permissions: users-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{win}\explorer.exe"; Parameters: "http://localhost:8765"; IconFilename: "{app}\logo_solba.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{win}\explorer.exe"; Parameters: "http://localhost:8765"; IconFilename: "{app}\logo_solba.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Iconos adicionales:"; Flags: unchecked

[Run]
; Servicio 24/7 (solo si el usuario elige Opción B en el asistente)
Filename: "{app}\nssm.exe"; Parameters: "install SolbaBackupsService ""{app}\{#MyAppExeName}"""; Flags: runhidden; Check: IsServiceSelected
Filename: "{app}\nssm.exe"; Parameters: "set SolbaBackupsService AppDirectory ""{app}"""; Flags: runhidden; Check: IsServiceSelected
Filename: "{app}\nssm.exe"; Parameters: "set SolbaBackupsService DisplayName ""SolbaBackups Service"""; Flags: runhidden; Check: IsServiceSelected
Filename: "{app}\nssm.exe"; Parameters: "set SolbaBackupsService Description ""Servicio de copias de seguridad SolbaBackups"""; Flags: runhidden; Check: IsServiceSelected
Filename: "{app}\nssm.exe"; Parameters: "start SolbaBackupsService"; Flags: runhidden; Check: IsServiceSelected
; Abrir panel tras instalar
Filename: "{cmd}"; Parameters: "/c timeout /t 3 /nobreak >nul & start http://localhost:8765"; Description: "Abrir panel de control (http://localhost:8765)"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\nssm.exe"; Parameters: "stop SolbaBackupsService"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove SolbaBackupsService confirm"; Flags: runhidden

[UninstallDelete]
Type: files; Name: "{userstartup}\SolbaBackups.lnk"

[Code]
var
  StartupPage: TInputOptionWizardPage;

function IsServiceSelected: Boolean;
begin
  Result := StartupPage.Values[1];
end;

procedure InitializeWizard;
begin
  StartupPage := CreateInputOptionPage(wpSelectTasks,
    'Inicio automático',
    '¿Cómo debe arrancar SolbaBackups?',
    'Seleccione una opción:',
    True, False);

  StartupPage.Add('Arrancar al iniciar sesión (acceso directo en Inicio)');
  StartupPage.Add('Instalar como servicio Windows 24/7 con NSSM (recomendado en servidores)');
  StartupPage.Add('No iniciar automáticamente');

  StartupPage.SelectedValueIndex := 1;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ShortcutPath, TargetPath, WorkingDir: string;
begin
  if CurStep = ssPostInstall then
  begin
    if StartupPage.Values[0] then
    begin
      ShortcutPath := ExpandConstant('{userstartup}\SolbaBackups.lnk');
      TargetPath := ExpandConstant('{app}\{#MyAppExeName}');
      WorkingDir := ExpandConstant('{app}');
      try
        CreateShellLink(ShortcutPath, '{#MyAppName}', TargetPath, '', WorkingDir, '', 0, SW_SHOWNORMAL);
      except
      end;
    end;
  end;
end;
