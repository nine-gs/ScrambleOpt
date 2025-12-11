# PowerShell build script for ScrambleOpt
# Usage: Run inside project root. Prefer running in the `scrambleEnv` virtualenv.

$ErrorActionPreference = 'Stop'
$project = (Get-Location).Path
$venvPython = Join-Path $project "scrambleEnv\Scripts\python.exe"
if (-Not (Test-Path $venvPython)) {
    Write-Error "Python executable not found at $venvPython. Activate your virtualenv or adjust path."; exit 1
}

# Clean previous builds
Write-Host "Cleaning dist/, build/, and existing spec..."
foreach ($p in @("$project\dist", "$project\build", "$project\ScrambleOpt.spec")) {
    if (Test-Path $p) {
        Remove-Item -Recurse -Force -LiteralPath $p -ErrorAction SilentlyContinue
    }
}

# Sanitize PATH to avoid system Qt/GDAL conflicts (OSGeo4W/QGIS)
Write-Host "Sanitizing PATH to avoid external Qt/GDAL interference..."
$filtered = ($env:PATH -split ';' | Where-Object {$_ -and ($_ -notmatch 'OSGeo4W') -and ($_ -notmatch 'osgeo') -and ($_ -notmatch 'QGIS') -and ($_ -notmatch 'GDAL') -and ($_ -notmatch 'OSGEO')}) -join ';'

# Prepend venv PySide6 and other binary folders when present
$maybePaths = @(
    (Join-Path $project 'scrambleEnv\Lib\site-packages\PySide6'),
    (Join-Path $project 'scrambleEnv\Lib\site-packages\rasterio.libs'),
    (Join-Path $project 'scrambleEnv\Lib\site-packages\numpy.libs')
)
$finalPath = $filtered
foreach ($p in $maybePaths) {
    if (Test-Path $p) { $finalPath = $p + ';' + $finalPath }
}
$env:PATH = $finalPath
Write-Host "Using python: $venvPython"

# Build command
$pyInstallerArgs = @(
    '--clean',
    '--noconfirm',
    '--onedir',
    '--windowed',
    '--name','ScrambleOpt',
    '--collect-all','PySide6',
    '--collect-all','numpy',
    '--collect-all','rasterio',
    '--collect-all','affine',
    '--collect-all','rendercanvas',
    '--hidden-import','rasterio.sample',
    '--hidden-import','rasterio._io',
    '--hidden-import','rasterio._base',
    '--add-data','solvers;solvers',
    '--add-data','perturbers;perturbers',
    '--add-data','viewer;viewer',
    '--runtime-hook','pyinstaller_runtime_hook_pyside.py',
    'main.py'
)

Write-Host "Running PyInstaller (this can take several minutes)..."
& $venvPython -m PyInstaller @pyInstallerArgs

Write-Host "Build finished. Output directory: $project\dist\ScrambleOpt"
Write-Host "If you see Qt DLL import errors when running the EXE, try launching with the generated wrapper 'run_scrambleopt.bat' or run the EXE from a sanitized shell as shown in the repository README."