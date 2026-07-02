<#
.SYNOPSIS
    Build release binaries for SLIM (Stena Line Internet Monitor)

.DESCRIPTION
    Builds the Python .exe and .NET MAUI .apk, then copies them to a
    releases/ folder with versioned filenames.

.PARAMETER Version
    Version string (e.g., "1.0.9"). If omitted, reads from python/stena_internet_gui.py.

.PARAMETER SkipPython
    Skip building the Python executable.

.PARAMETER SkipMaui
    Skip building the MAUI APK.

.EXAMPLE
    .\build-release.ps1
    .\build-release.ps1 -Version "1.1.0"
    .\build-release.ps1 -SkipMaui
#>

param(
    [string]$Version,
    [switch]$SkipPython,
    [switch]$SkipMaui
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

# Extract version from Python source if not provided
if (-not $Version) {
    $pySource = Get-Content "$RepoRoot\python\stena_internet_gui.py" -Raw
    if ($pySource -match 'APP_VERSION\s*=\s*"([^"]+)"') {
        $Version = $Matches[1]
    } else {
        Write-Error "Could not extract version from stena_internet_gui.py"
        exit 1
    }
}

Write-Host "`n=== Building SLIM v$Version ===" -ForegroundColor Cyan

# Create releases folder
$ReleasesDir = "$RepoRoot\releases"
if (-not (Test-Path $ReleasesDir)) {
    New-Item -ItemType Directory -Path $ReleasesDir | Out-Null
}

# Build Python executable
if (-not $SkipPython) {
    Write-Host "`n[1/2] Building Python executable..." -ForegroundColor Yellow
    Push-Location "$RepoRoot\python"
    try {
        # Activate venv if it exists
        if (Test-Path "..\venv\Scripts\Activate.ps1") {
            & "..\venv\Scripts\Activate.ps1"
        }
        
        pyinstaller StenaInternetMonitor.spec --noconfirm
        if ($LASTEXITCODE -ne 0) {
            throw "pyinstaller failed with exit code $LASTEXITCODE"
        }

        $ExeSrc = "dist\SLIM.exe"
        $ExeDst = "$ReleasesDir\SLIM-v$Version-windows.exe"
        
        if (Test-Path $ExeSrc) {
            Copy-Item $ExeSrc $ExeDst -Force
            Write-Host "  Created: $ExeDst" -ForegroundColor Green
        } else {
            Write-Error "PyInstaller output not found: $ExeSrc"
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "`n[1/2] Skipping Python build" -ForegroundColor DarkGray
}

# Build MAUI APK
if (-not $SkipMaui) {
    Write-Host "`n[2/2] Building MAUI APK..." -ForegroundColor Yellow
    
    # Check for signing credentials
    if (-not $env:ANDROID_SIGNING_STORE_PASS -or -not $env:ANDROID_SIGNING_KEY_PASS) {
        Write-Warning "Android signing env vars not set. Build may fail or produce unsigned APK."
        Write-Host "  Set ANDROID_SIGNING_STORE_PASS and ANDROID_SIGNING_KEY_PASS" -ForegroundColor DarkGray
    }
    
    Push-Location "$RepoRoot\maui"
    try {
        dotnet publish -f net8.0-android -c Release
        if ($LASTEXITCODE -ne 0) {
            # Fail loudly instead of falling through and copying a stale
            # APK from a previous successful build (would then get shipped
            # under the new version -- happened once, don't repeat).
            throw "dotnet publish failed with exit code $LASTEXITCODE"
        }

        # Find the signed APK
        $ApkPattern = "bin\Release\net8.0-android\publish\*-Signed.apk"
        $ApkSrc = Get-ChildItem $ApkPattern -ErrorAction SilentlyContinue | Select-Object -First 1
        
        if (-not $ApkSrc) {
            # Try unsigned
            $ApkPattern = "bin\Release\net8.0-android\publish\*.apk"
            $ApkSrc = Get-ChildItem $ApkPattern -ErrorAction SilentlyContinue | Select-Object -First 1
        }
        
        if ($ApkSrc) {
            $ApkDst = "$ReleasesDir\SLIM-v$Version-android.apk"
            Copy-Item $ApkSrc.FullName $ApkDst -Force
            Write-Host "  Created: $ApkDst" -ForegroundColor Green
        } else {
            Write-Error "APK not found in bin\Release\net8.0-android\publish\"
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "`n[2/2] Skipping MAUI build" -ForegroundColor DarkGray
}

Write-Host "`n=== Build complete ===" -ForegroundColor Cyan
Write-Host "Release files in: $ReleasesDir`n"
Get-ChildItem $ReleasesDir | ForEach-Object {
    $size = "{0:N2} MB" -f ($_.Length / 1MB)
    Write-Host "  $($_.Name) ($size)"
}

Write-Host "`nTo create a GitHub release:" -ForegroundColor Yellow
Write-Host "  git tag v$Version"
Write-Host "  git push origin v$Version"
Write-Host "  gh release create v$Version releases/* --title `"SLIM v$Version`" --notes `"Release notes here`""
