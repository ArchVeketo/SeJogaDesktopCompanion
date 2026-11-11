param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
# Do not let Codex's private runtime DLLs enter the application bundle.
# PyInstaller replaces the onedir output. Preserve the user's portable profile.
$profileSource = Join-Path $PSScriptRoot 'dist\SeJogaCompanion\user-data'
$profileBackup = Join-Path $PSScriptRoot '.local\user-data'
if (Test-Path -LiteralPath $profileSource) {
    New-Item -ItemType Directory -Force -Path $profileBackup | Out-Null
    Copy-Item -Path (Join-Path $profileSource '*') -Destination $profileBackup -Recurse -Force
}
# CodexPrimaryRuntime also ships Poppler's ICU. Its icuuc.dll exports versioned
# symbols and cannot replace Windows ICU, which Qt uses (e.g. ucnv_open).
$env:PATH = (($env:PATH -split ';' | Where-Object { $_ -notmatch 'codex-runtimes|OpenAI\.CodexPrimaryRuntime' }) -join ';')
$panda3dDir = & $Python -c 'import pathlib, panda3d; print(pathlib.Path(panda3d.__file__).parent)'
if ($LASTEXITCODE -ne 0) { throw 'O Python escolhido não possui Panda3D.' }

& $Python -m PyInstaller `
    --paths src `
    --clean `
    --name SeJogaCompanion `
    --icon "assets\brand\companion.ico" `
    --version-file "assets\brand\version_info.txt" `
    --windowed `
    --onedir `
    --add-data "assets;assets" `
    --collect-all simplepbr `
    --add-binary "$panda3dDir\libpandagl.dll;panda3d" `
    --add-binary "$panda3dDir\libp3windisplay.dll;panda3d" `
    --add-binary "$panda3dDir\libp3tinydisplay.dll;panda3d" `
    --hidden-import=simplepbr `
    --hidden-import=gltf `
    --hidden-import=pymunk `
    --collect-all soundcard `
    --hidden-import=pystray `
    --hidden-import=PIL `
    --hidden-import=winrt.windows.media.control `
    --hidden-import=winrt.windows.foundation `
    --hidden-import=winrt.windows.foundation.collections `
    --hidden-import=winrt.windows.media `
    --hidden-import=winrt.windows.storage.streams `
    --hidden-import=winrt `
    --hidden-import=win32gui `
    --hidden-import=win32con `
    --hidden-import=win32api `
    --hidden-import=win32process `
    --hidden-import=comtypes `
    --hidden-import=comtypes.client `
    --hidden-import=ctypes `
    --hidden-import=PySide6.QtCore `
    --hidden-import=PySide6.QtWidgets `
    --hidden-import=PySide6.QtGui `
    run_companion.py -y

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
if (Test-Path -LiteralPath $profileBackup) {
    New-Item -ItemType Directory -Force -Path $profileSource | Out-Null
    Copy-Item -Path (Join-Path $profileBackup '*') -Destination $profileSource -Recurse -Force
}
