; Instalador unico do SeJoga Companion (canal release, escopo de maquina).
; Embute o runtime completo em {app}\runtime\current e o launcher nativo em {app}.
; Nao ramifica por canal: um unico setup, uma unica AppId. A primeira execucao abre
; o mascote direto do runtime embutido, sem depender de feed publicado.
;
; Defines esperados do tools\build-installer.ps1:
;   MeuVersion   -> versao exibida (ex.: 1.0.0)
;   MeuRuntime   -> pasta com o bundle PyInstaller ja montado (runtime/current)
;   MeuLauncher  -> caminho do SeJogaLauncher.exe compilado
;   MeuChannelInfo -> caminho do channel-info.json neutro
;   MeuSaida     -> pasta de saida do .exe do setup
;   MeuNomeSaida -> nome base do .exe (sem extensao)

#ifndef MeuVersion
  #define MeuVersion "0.0.0"
#endif
#ifndef MeuNomeSaida
  #define MeuNomeSaida "SeJogaCompanion-Setup-windows-x64"
#endif

#define MeuNome "SeJoga Companion"
#define MeuPublisher "SeJogaNoArmario"
#define MeuExeLauncher "SeJogaLauncher.exe"

[Setup]
; AppId fixo: casa com o GUID release que o launcher usa para atualizar a versao no registro.
AppId={{27AD0F68-F575-45DB-B24A-C94954679DA1}
AppName={#MeuNome}
AppVersion={#MeuVersion}
AppPublisher={#MeuPublisher}
DefaultDirName={autopf}\SeJogaCompanion
DefaultGroupName={#MeuNome}
DisableProgramGroupPage=yes
; Instalacao para todos os usuarios, com elevacao do Windows.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
OutputDir={#MeuSaida}
OutputBaseFilename={#MeuNomeSaida}
SetupIconFile={#SourcePath}\..\assets\brand\companion.ico
UninstallDisplayIcon={app}\{#MeuExeLauncher}
UninstallDisplayName={#MeuNome}
MinVersion=10.0.17763

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
; Runtime completo embutido (bundle PyInstaller) -> {app}\runtime\current.
Source: "{#MeuRuntime}\*"; DestDir: "{app}\runtime\current"; Flags: recursesubdirs createallsubdirs ignoreversion
; Launcher/updater nativo ao lado do runtime.
Source: "{#MeuLauncher}"; DestDir: "{app}"; Flags: ignoreversion
; Metadado de canal neutro consumido pelo launcher.
Source: "{#MeuChannelInfo}"; DestDir: "{app}"; DestName: "channel-info.json"; Flags: ignoreversion

[Icons]
; Todos os atalhos apontam para o launcher, nunca direto para o SeJogaCompanion.exe.
Name: "{group}\{#MeuNome}"; Filename: "{app}\{#MeuExeLauncher}"; WorkingDir: "{app}"
Name: "{group}\Desinstalar {#MeuNome}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MeuNome}"; Filename: "{app}\{#MeuExeLauncher}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Oferece abrir o mascote ao final da instalacao.
Filename: "{app}\{#MeuExeLauncher}"; Description: "Abrir o {#MeuNome}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove apenas artefatos gerados pelo proprio runtime/updater, nunca o perfil do usuario no AppData.
Type: filesandordirs; Name: "{app}\runtime"
Type: files; Name: "{app}\update-last-error.txt"
Type: files; Name: "{app}\prepared-payload.zip"
Type: files; Name: "{app}\.bootstrap-payload.zip"

; Observacao: os perfis do usuario vivem em %AppData%\SeJogaCompanion* e NAO sao tocados
; por atualizacao ou desinstalacao. O setup nunca grava nem apaga nada em AppData.
