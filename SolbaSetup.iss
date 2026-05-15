[Setup]
AppName=SolbaBackups
AppVersion=1.0
DefaultDirName={autopf}\SolbaBackups
DefaultGroupName=SolbaBackups
OutputDir=Output
OutputBaseFilename=SolbaSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
SetupIconFile=src\frontend\assets\logo_solba.ico
WizardImageFile=src\frontend\assets\logo_wizard.bmp
WizardSmallImageFile=src\frontend\assets\logo_wizard_small.bmp

[Files]
Source: "dist\SolbaBackups\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NSSM es requerido para instalar el servicio
Source: "nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
; Archivo de configuración de variables de entorno
Source: "C:\Escritorio\BackUp-Solba\.env"; DestDir: "{app}"; Flags: ignoreversion; Permissions: users-modify
; Credenciales de Google Drive (no se sobreescriben si ya existen)
Source: "C:\Escritorio\BackUp-Solba\credentials.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
; Token de sesión OAuth2 de Google Drive (demo pre-autorizada, no sobreescribir)
Source: "C:\Escritorio\BackUp-Solba\token.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
; Icono de Solba para accesos directos
Source: "src\frontend\assets\logo_solba.ico"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Otorgar permisos de escritura a todos los usuarios sobre la carpeta de instalación.
; Esto evita el error 'Acceso denegado' al escribir la BD SQLite y el .env desde Program Files
; sin necesidad de ejecutar la app como Administrador.
Name: "{app}"; Permissions: users-modify

[Icons]
Name: "{group}\SolbaBackups"; Filename: "{win}\explorer.exe"; Parameters: "http://localhost:8765"; IconFilename: "{app}\logo_solba.ico"
Name: "{userdesktop}\SolbaBackups"; Filename: "{win}\explorer.exe"; Parameters: "http://localhost:8765"; IconFilename: "{app}\logo_solba.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
; Instalar el servicio (siempre, sin condición)
Filename: "{app}\nssm.exe"; Parameters: "install SolbaBackupsService ""{app}\SolbaBackups.exe"""; Flags: runhidden
; Configurar el directorio de trabajo (CRÍTICO: sin esto el servicio no encuentra .env ni la BD)
Filename: "{app}\nssm.exe"; Parameters: "set SolbaBackupsService AppDirectory ""{app}"""; Flags: runhidden
; Arrancar el servicio
Filename: "{app}\nssm.exe"; Parameters: "start SolbaBackupsService"; Flags: runhidden
; Esperar 3 segundos y abrir el navegador (checkbox marcado por defecto)
Filename: "{cmd}"; Parameters: "/c timeout /t 3 & start http://localhost:8765"; Description: "Abrir Panel de Control de SolbaBackups"; Flags: postinstall nowait runhidden

[UninstallRun]
; Detener y eliminar el servicio al desinstalar
Filename: "{app}\nssm.exe"; Parameters: "stop SolbaBackupsService"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove SolbaBackupsService confirm"; Flags: runhidden

[UninstallDelete]
; Eliminar el acceso directo de inicio automático en caso de que exista (Opción A)
Type: files; Name: "{userstartup}\SolbaBackups.lnk"

[Code]
var
  StartupPage: TInputOptionWizardPage;

procedure InitializeWizard;
begin
  StartupPage := CreateInputOptionPage(wpSelectTasks,
    'Opciones de Inicio Automático',
    '¿Cómo desea que se inicie SolbaBackups?',
    'Por favor, seleccione el comportamiento de arranque:',
    True, False);

  StartupPage.Add('Opción A: Arrancar SolbaBackups al iniciar sesión (Usuario actual)');
  StartupPage.Add('Opción B: Instalar como Servicio 24/7 usando NSSM (Recomendado para servidores)');
  StartupPage.Add('Opción C: No iniciar automáticamente');
  
  // Seleccionar la Opción A por defecto
  StartupPage.Values[0] := True;
end;

function IsServiceSelected: Boolean;
begin
  Result := StartupPage.Values[1];
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ShortcutPath, TargetPath, WorkingDir: string;
begin
  // Ejecutamos esto justo después de que se copien los archivos (ssPostInstall)
  if CurStep = ssPostInstall then
  begin
    if StartupPage.Values[0] then
    begin
      // Opción A seleccionada: Crear acceso directo en la carpeta de Inicio
      ShortcutPath := ExpandConstant('{userstartup}\SolbaBackups.lnk');
      TargetPath := ExpandConstant('{app}\SolbaBackups.exe');
      WorkingDir := ExpandConstant('{app}');
      
      try
        CreateShellLink(ShortcutPath, 'SolbaBackups Server', TargetPath, '', WorkingDir, '', 0, SW_SHOWNORMAL);
      except
        // Capturar y silenciar errores en caso de fallo de permisos o ruta
      end;
    end;
  end;
end;
