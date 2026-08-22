param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PythonVersionOk = python -c "import sys; print(int(sys.version_info >= (3, 11)))"
if ($PythonVersionOk -ne "1") {
    throw "Elsewhere requires Python 3.11 or later."
}

$BuildEnvironment = Join-Path $ProjectRoot ".build-venv"
$BuildPython = Join-Path $BuildEnvironment "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $BuildPython)) {
    python -m venv $BuildEnvironment
    if ($LASTEXITCODE -ne 0) { throw "Could not create the isolated build environment." }
}

& $BuildPython -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    $PyInstallerVersion = ""
} else {
    $PyInstallerVersion = & $BuildPython -c "import PyInstaller; print(PyInstaller.__version__)"
}

if ($PyInstallerVersion -ne "6.19.0") {
    & $BuildPython -m pip install --disable-pip-version-check -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw "Could not install the isolated build dependency." }
    $PyInstallerVersion = & $BuildPython -c "import PyInstaller; print(PyInstaller.__version__)"
}
if ($PyInstallerVersion -ne "6.19.0") {
    throw "Expected PyInstaller 6.19.0, found $PyInstallerVersion."
}

if (-not $SkipTests) {
    & $BuildPython smoke_test.py
    if ($LASTEXITCODE -ne 0) { throw "Farmstead smoke tests failed." }
    & $BuildPython -m ascii_battle_prototype.combat.smoke_tests
    if ($LASTEXITCODE -ne 0) { throw "Combat smoke tests failed." }
    & $BuildPython -m ascii_battle_prototype.combat.main --validate-content
    if ($LASTEXITCODE -ne 0) { throw "Combat content validation failed." }
}

& $BuildPython -m PyInstaller --clean --noconfirm elsewhere.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$ReleaseDirectory = Join-Path $ProjectRoot "dist\Elsewhere"
foreach ($Document in @(
    "README.md",
    "LICENSE",
    "CREDITS.md",
    "THIRD_PARTY_NOTICES.md",
    "CHANGELOG.md",
    "KNOWN_ISSUES.md"
)) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Document) -Destination $ReleaseDirectory
}

$PythonLicense = & $BuildPython -c "import sys; from pathlib import Path; print(Path(sys.base_prefix) / 'LICENSE.txt')"
if (-not (Test-Path -LiteralPath $PythonLicense)) {
    throw "Could not locate the bundled Python runtime license."
}
Copy-Item -LiteralPath $PythonLicense -Destination (Join-Path $ReleaseDirectory "PYTHON_LICENSE.txt")

$Version = & $BuildPython -c "from ascii_farmstead_support import GAME_VERSION; print(GAME_VERSION)"
$PythonRuntimeVersion = & $BuildPython -c "import platform; print(platform.python_version())"
$BuildDependencies = & $BuildPython -m pip freeze
$BuildInformation = @(
    "Elsewhere $Version",
    "Built: $([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))",
    "Platform: Windows x64",
    "Python: $PythonRuntimeVersion",
    "PyInstaller: $PyInstallerVersion",
    "",
    "Build environment:",
    $BuildDependencies
)
Set-Content -LiteralPath (Join-Path $ReleaseDirectory "BUILD_INFO.txt") -Value $BuildInformation -Encoding UTF8

$ArchivePath = Join-Path $ProjectRoot "dist\Elsewhere-$Version-windows-x64.zip"
& (Join-Path $ReleaseDirectory "Elsewhere.exe") --version
if ($LASTEXITCODE -ne 0) { throw "Packaged executable launch check failed." }
$SelfCheckData = Join-Path $ProjectRoot "build\self-check-data"
$PreviousDataOverride = $env:ELSEWHERE_DATA_DIR
try {
    if (Test-Path -LiteralPath $SelfCheckData) {
        Remove-Item -LiteralPath $SelfCheckData -Recurse
    }
    $env:ELSEWHERE_DATA_DIR = $SelfCheckData
    & (Join-Path $ReleaseDirectory "Elsewhere.exe") --self-check
    if ($LASTEXITCODE -ne 0) { throw "Packaged executable self-check failed." }
} finally {
    if ($null -eq $PreviousDataOverride) {
        Remove-Item Env:ELSEWHERE_DATA_DIR -ErrorAction SilentlyContinue
    } else {
        $env:ELSEWHERE_DATA_DIR = $PreviousDataOverride
    }
    if (Test-Path -LiteralPath $SelfCheckData) {
        Remove-Item -LiteralPath $SelfCheckData -Recurse
    }
}

if (Test-Path -LiteralPath $ArchivePath) {
    Remove-Item -LiteralPath $ArchivePath
}
Compress-Archive -Path (Join-Path $ReleaseDirectory "*") -DestinationPath $ArchivePath
$ChecksumPath = "$ArchivePath.sha256"
$ArchiveHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $ChecksumPath -Value "$ArchiveHash  $(Split-Path -Leaf $ArchivePath)" -Encoding ASCII

Write-Host ""
Write-Host "Build complete:"
Write-Host $ReleaseDirectory
Write-Host $ArchivePath
Write-Host $ChecksumPath
