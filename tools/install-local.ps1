param([switch]$Launch)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
$source = Join-Path $workspace 'dist\SeJogaCompanion'
$destination = Join-Path $env:LOCALAPPDATA 'Programs\SeJogaCompanion\current'
if (-not (Test-Path -LiteralPath (Join-Path $source 'SeJogaCompanion.exe'))) {
    throw 'Compile primeiro com .\build.ps1'
}
$installedExe = Join-Path $destination 'SeJogaCompanion.exe'
$running = @(Get-CimInstance Win32_Process -Filter "Name='SeJogaCompanion.exe'" | Where-Object { $_.ExecutablePath -eq $installedExe })
foreach ($process in $running) {
    $companion = Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    if ($companion) {
        if (-not $companion.CloseMainWindow()) { throw "Não foi possível solicitar encerramento do PID $($process.ProcessId)." }
        if (-not $companion.WaitForExit(10000)) { throw 'Feche o companion antes de atualizar a instalação.' }
    }
}
# Copy data, attributes and timestamps, never the checkout integrity label/ACL.
& robocopy $source $destination /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XD user-data /NFL /NDL /NP /NJH /NJS
if ($LASTEXITCODE -ge 8) { throw 'Falha ao instalar a distribuição local.' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\SeJoga Companion.lnk'))
$shortcut.TargetPath = Join-Path $destination 'SeJogaCompanion.exe'
$shortcut.WorkingDirectory = $destination
$shortcut.IconLocation = "$destination\SeJogaCompanion.exe,0"
$shortcut.Save()
if ($Launch) { Start-Process -FilePath $shortcut.TargetPath -WorkingDirectory $destination -WindowStyle Hidden }
Write-Output "Instalado em $destination"
