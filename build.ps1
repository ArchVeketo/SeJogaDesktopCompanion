# Do not let Codex's private runtime DLLs enter the application bundle.
# CodexPrimaryRuntime also ships Poppler's ICU. Its icuuc.dll exports versioned
# symbols and cannot replace Windows ICU, which Qt uses (e.g. ucnv_open).
$env:PATH = (($env:PATH -split ';' | Where-Object { $_ -notmatch 'codex-runtimes|OpenAI\.CodexPrimaryRuntime' }) -join ';')
$env:PATH += ";C:\Users\victh\AppData\Roaming\Python\Python314\Scripts"
$panda3dDir = Join-Path $env:APPDATA 'Python\Python314\site-packages\panda3d'

& "C:\Users\victh\AppData\Roaming\Python\Python314\Scripts\pyinstaller.exe" `
    --clean `
    --name SeJogaCompanion `
    --windowed `
    --onedir `
    --add-data "assets;assets" `
    --add-binary "$panda3dDir\libpandagl.dll;panda3d" `
    --add-binary "$panda3dDir\libp3windisplay.dll;panda3d" `
    --add-binary "$panda3dDir\libp3tinydisplay.dll;panda3d" `
    --hidden-import=simplepbr `
    --hidden-import=gltf `
    --hidden-import=pymunk `
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
