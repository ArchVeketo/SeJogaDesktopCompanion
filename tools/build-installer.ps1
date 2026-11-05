#Requires -Version 5.1
<#
  Monta o instalador UNICO do SeJoga Companion (canal release, escopo de maquina).
  Nao tem parametro -Channel: um unico setup com runtime embutido.

  Passos:
    1. Exigir o bundle pronto em dist\SeJogaCompanion.
    2. Compilar o launcher nativo via tools\build-launcher.ps1.
    3. Montar o layout de instalacao numa pasta temporaria:
       - runtime\current = bundle + release-info.json coerente;
       - channel-info.json neutro ({"channel":"release","scope":"machine"}).
    4. Invocar o ISCC (Inno Setup) com os defines do layout.
    5. Saida fixa dist\installer\SeJogaCompanion-Setup-windows-x64.exe + .sha256.

  Na ausencia do ISCC, falha com mensagem clara e ecoa o comando exato.
#>
param(
  [string]$Compiler = '',
  [string]$Version = ''
)
$ErrorActionPreference = 'Stop'

$workspace = Split-Path $PSScriptRoot -Parent
$bundle = Join-Path $workspace 'dist\SeJogaCompanion'
$script = Join-Path $workspace 'installer\sejoga-setup.iss'
$saida = Join-Path $workspace 'dist\installer'
$nomeSaida = 'SeJogaCompanion-Setup-windows-x64'

# 1. Bundle obrigatorio.
if (-not (Test-Path -LiteralPath (Join-Path $bundle 'SeJogaCompanion.exe'))) {
  throw "Bundle ausente: compile primeiro com .\build.ps1 (esperado em $bundle)."
}

# Versao: parametro ou pyproject.toml.
if (-not $Version) {
  $pyproject = Get-Content -LiteralPath (Join-Path $workspace 'pyproject.toml') -Raw
  $match = [regex]::Match($pyproject, '(?m)^\s*version\s*=\s*"([^"]+)"')
  if (-not $match.Success) { throw 'Nao foi possivel ler a versao do pyproject.toml; informe -Version.' }
  $Version = $match.Groups[1].Value
}

# Localiza o ISCC (Inno Setup). ScriptBlock testavel: caminho explicito > PATH > locais padrao.
$resolverCompilador = {
  param($preferido)
  if ($preferido) {
    if (Test-Path -LiteralPath $preferido) { return (Resolve-Path -LiteralPath $preferido).Path }
    return $null
  }
  $noPath = Get-Command 'iscc.exe' -ErrorAction SilentlyContinue
  if ($noPath) { return $noPath.Source }
  $candidatos = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe')
  )
  foreach ($c in $candidatos) { if ($c -and (Test-Path -LiteralPath $c)) { return $c } }
  return $null
}

$iscc = & $resolverCompilador $Compiler

# 2. Compila o launcher nativo.
$launcherDir = Join-Path $workspace '.local\bootstrapper'
$launcher = & (Join-Path $PSScriptRoot 'build-launcher.ps1') -OutputDirectory $launcherDir
$launcher = ($launcher | Select-Object -Last 1).ToString().Trim()
if (-not (Test-Path -LiteralPath $launcher)) { throw "Launcher nao gerado em $launcher." }

# 3. Monta o layout numa pasta temporaria limpa.
$staging = Join-Path $workspace '.local\installer-stage'
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
$runtime = Join-Path $staging 'runtime\current'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
& robocopy $bundle $runtime /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XD user-data /NFL /NDL /NP /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw 'Falha ao copiar o bundle para o layout de instalacao.' }

# release-info.json coerente (version/channel/build_id + version_order) via updater.
$buildId = [int64]((Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss'))
$gerarInfo = @"
import json, sys
sys.path.insert(0, r'$($workspace -replace '\\','\\')\src')
from sejoga.updater import ReleaseInfo, version_order
info = ReleaseInfo('$Version', 'release', $buildId)
json.dump({'schema_version': 1, 'architecture': 'windows-x64', 'channel': info.channel,
           'version': info.version, 'build_id': info.build_id,
           'version_order': version_order(info.version)},
          open(r'$runtime\release-info.json', 'w', encoding='utf-8'), indent=2)
"@
& python -c $gerarInfo
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar release-info.json (verifique a versao do canal release).' }

# channel-info.json neutro consumido pelo launcher.
$channelInfo = Join-Path $staging 'channel-info.json'
Set-Content -LiteralPath $channelInfo -Value '{"channel":"release","scope":"machine"}' -Encoding UTF8 -NoNewline

New-Item -ItemType Directory -Force -Path $saida | Out-Null

# Comando exato do ISCC (reutilizado na falha e na execucao).
$defines = @(
  "/DMeuVersion=$Version",
  "/DMeuRuntime=$runtime",
  "/DMeuLauncher=$launcher",
  "/DMeuChannelInfo=$channelInfo",
  "/DMeuSaida=$saida",
  "/DMeuNomeSaida=$nomeSaida"
)
$comandoExato = ('& "<ISCC.exe>" ' + ($defines -join ' ') + " `"$script`"")

# 4. ISCC ausente: falha clara ecoando o comando.
if (-not $iscc) {
  $msg = @"
Inno Setup (ISCC.exe) nao encontrado. Instale o Inno Setup 6+ ou informe o caminho com -Compiler.
Exemplo:
  .\tools\build-installer.ps1 -Compiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" -Version $Version
Comando que seria executado:
  $($comandoExato -replace '<ISCC.exe>', 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe')
"@
  throw $msg
}

# 5. Compila o instalador.
& $iscc @defines $script
if ($LASTEXITCODE -ne 0) { throw "ISCC falhou (codigo $LASTEXITCODE)." }

$exe = Join-Path $saida ($nomeSaida + '.exe')
if (-not (Test-Path -LiteralPath $exe)) { throw "Instalador nao gerado em $exe." }

# SHA256 ao lado do instalador.
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath ($exe + '.sha256') -Value "$hash  $nomeSaida.exe" -Encoding ascii
Write-Output $exe
