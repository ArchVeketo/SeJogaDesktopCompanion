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
Write-Output (Join-Path $OutputDirectory 'SeJogaLauncher.exe')
