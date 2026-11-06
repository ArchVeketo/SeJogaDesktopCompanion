param([string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $workspace '.local\bootstrapper' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework 4.x SDK/compiler nao encontrado.' }
$framework = Split-Path $compiler -Parent
$arguments = @('/nologo', '/target:winexe', '/platform:x64', '/optimize+',
    ('/out:' + (Join-Path $OutputDirectory 'SeJogaLauncher.exe')),
    ('/win32icon:' + (Join-Path $workspace 'assets\brand\companion.ico')),
    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
    ("/reference:$framework\System.Web.Extensions.dll"),
    ("/reference:$framework\System.IO.Compression.dll"),
    ("/reference:$framework\System.IO.Compression.FileSystem.dll"),
    (Join-Path $workspace 'installer\SeJogaLauncher.cs'))
& $compiler @arguments
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar o launcher/updater nativo.' }

# VERSION_INFO (produto "Se Joga Desktop Companion" / empresa "Se Joga no Armário"):
# vem dos atributos [assembly: AssemblyProduct/AssemblyCompany/...] no topo de
# installer\SeJogaLauncher.cs. Sem /win32res, o csc gera o recurso Win32 de versao
# a partir deles, e e esse recurso que o UAC le para exibir o editor.

# ASSINATURA DE CODIGO (gancho futuro) -- NAO executado por decisao do usuario.
# Sem certificado, o Windows continua exibindo o aviso de editor desconhecido no UAC.
# Quando houver um certificado (.pfx) e for desejado assinar, descomente e ajuste:
#   $signtool = 'C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe'
#   $exe = Join-Path $OutputDirectory 'SeJogaLauncher.exe'
#   & $signtool sign /fd SHA256 /f $env:SEJOGA_CERT_PFX /p $env:SEJOGA_CERT_SENHA `
#       /tr http://timestamp.digicert.com /td SHA256 $exe
#   if ($LASTEXITCODE -ne 0) { throw 'Falha ao assinar o launcher.' }

Write-Output (Join-Path $OutputDirectory 'SeJogaLauncher.exe')
