param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [string]$CertThumbprint = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root     = $PSScriptRoot
$DistDir  = Join-Path $Root "dist\DisplayGuard"
$OutDir   = Join-Path $Root "Output"
$SetupExe = Join-Path $OutDir "DisplayGuard-Setup-$Version.exe"

# ── 버전 주입 ──────────────────────────────────────────────────────────────
Write-Host "[1/5] Injecting version $Version ..." -ForegroundColor Cyan

$VerFile = Join-Path $Root "version_info.txt"
$VerContent = Get-Content $VerFile -Raw
$VerContent = $VerContent -replace "filevers=\(\d+, \d+, \d+, \d+\)", "filevers=($($Version -replace '\.', ', '), 0)"
$VerContent = $VerContent -replace "prodvers=\(\d+, \d+, \d+, \d+\)", "prodvers=($($Version -replace '\.', ', '), 0)"
$VerContent = $VerContent -replace "'FileVersion',\s*u'[^']*'", "'FileVersion',      u'$Version.0'"
$VerContent = $VerContent -replace "'ProductVersion',\s*u'[^']*'", "'ProductVersion',   u'$Version.0'"
$VerContent | Set-Content $VerFile -Encoding utf8

# ── 이전 빌드 정리 ─────────────────────────────────────────────────────────
Write-Host "[2/5] Cleaning previous build ..." -ForegroundColor Cyan
if (Test-Path (Join-Path $Root "dist"))  { Remove-Item (Join-Path $Root "dist")  -Recurse -Force }
if (Test-Path (Join-Path $Root "build")) { Remove-Item (Join-Path $Root "build") -Recurse -Force }
if (Test-Path $OutDir)                   { Remove-Item $OutDir -Recurse -Force }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

# icon.ico 가 없으면 Python으로 미리 생성
$IcoPath = Join-Path $Root "icon.ico"
if (-not (Test-Path $IcoPath)) {
    Write-Host "  Generating icon.ico ..." -ForegroundColor DarkCyan
    python -c "import sys; sys.path.insert(0, r'$Root'); from display_guard import ensure_ico; ensure_ico()"
}

# ── PyInstaller ────────────────────────────────────────────────────────────
Write-Host "[3/5] Running PyInstaller ..." -ForegroundColor Cyan
Push-Location $Root
python -m PyInstaller DisplayGuard.spec --noconfirm
Pop-Location

if (-not (Test-Path (Join-Path $DistDir "DisplayGuard.exe"))) {
    Write-Error "PyInstaller failed — DisplayGuard.exe not found in dist\DisplayGuard\"
    exit 1
}

# ── 코드 서명 (exe) ────────────────────────────────────────────────────────
if ($CertThumbprint) {
    Write-Host "[3b] Signing exe with cert $CertThumbprint ..." -ForegroundColor Cyan
    $signtool = "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
    & $signtool sign /sha1 $CertThumbprint /tr http://timestamp.sectigo.com /td sha256 /fd sha256 `
        (Join-Path $DistDir "DisplayGuard.exe")
    if ($LASTEXITCODE -ne 0) { Write-Error "signtool failed on exe"; exit 1 }
}

# ── Inno Setup ─────────────────────────────────────────────────────────────
Write-Host "[4/5] Building installer with Inno Setup ..." -ForegroundColor Cyan

$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    # PATH 에서도 탐색
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iscc = $cmd.Source }
}
if (-not $iscc) {
    Write-Error "Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php"
    exit 1
}

& $iscc (Join-Path $Root "installer.iss") /DMyAppVersion=$Version /O"$OutDir"
if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup failed"; exit 1 }

# ── 코드 서명 (인스톨러) ───────────────────────────────────────────────────
if ($CertThumbprint) {
    Write-Host "[4b] Signing installer ..." -ForegroundColor Cyan
    & $signtool sign /sha1 $CertThumbprint /tr http://timestamp.sectigo.com /td sha256 /fd sha256 $SetupExe
    if ($LASTEXITCODE -ne 0) { Write-Error "signtool failed on installer"; exit 1 }
}

# ── 완료 ───────────────────────────────────────────────────────────────────
Write-Host "[5/5] Done!" -ForegroundColor Green
Write-Host "  Output: $SetupExe" -ForegroundColor Green

$hash = (Get-FileHash $SetupExe -Algorithm SHA256).Hash
Write-Host "  SHA256: $hash" -ForegroundColor DarkGray
