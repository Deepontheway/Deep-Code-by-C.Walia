# Deep Code by C.Walia - Uninstaller
# Removes the app, its shortcuts, its registration and (optionally) the
# dependencies/models that the setup downloaded.
param(
    [string]$ManifestPath,
    [string]$InstallDir,
    [switch]$Silent,
    [switch]$PurgeDependencies,
    [switch]$RemoveModels,
    [switch]$KeepInstallDir,
    [switch]$KeepData,
    [switch]$Full
)

if ($Full -or $Silent) {
    $PurgeDependencies = $true
    $RemoveModels = $true
    $KeepData = $false
    $KeepInstallDir = $false
}

$ErrorActionPreference = "Continue"

function Write-Step {
    param([string]$Msg, [string]$Color = "Cyan")
    Write-Host ""
    Write-Host "[DEEP-CODE-UNINSTALL] $Msg" -ForegroundColor $Color
}

function Test-Command {
    param([string]$Cmd)
    $null = Get-Command $Cmd -ErrorAction SilentlyContinue
    return $?
}

function Confirm-Action {
    param([string]$Question, [bool]$DefaultYes = $false)
    if ($Silent) { return $DefaultYes }
    $suffix = "[y/N]"
    if ($DefaultYes) { $suffix = "[Y/n]" }
    $answer = Read-Host "$Question $suffix"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $DefaultYes }
    return ($answer.Trim().ToLower() -in @("y", "yes"))
}

Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "     DEEP CODE BY C.WALIA - UNINSTALLER             " -ForegroundColor Magenta
Write-Host "====================================================" -ForegroundColor Magenta

if (-not $ManifestPath) {
    $candidate = Join-Path $PSScriptRoot "install-manifest.json"
    if (Test-Path -LiteralPath $candidate) { $ManifestPath = $candidate }
}

$m = $null
if ($ManifestPath -and (Test-Path -LiteralPath $ManifestPath)) {
    try {
        $m = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
    } catch {
        Write-Host "Could not read manifest, continuing with defaults: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "Install manifest not found; using default install/data locations." -ForegroundColor Yellow
}

$wingetPkgs = @()
$models = @()
$shortcuts = @()
if ($m) {
    if (-not $InstallDir) { $InstallDir = [string]$m.InstallDir }
    if ($m.WingetPackagesInstalled) { $wingetPkgs = @($m.WingetPackagesInstalled) }
    if ($m.OllamaModels) { $models = @($m.OllamaModels) }
    if ($m.Shortcuts) { $shortcuts = @($m.Shortcuts) }
}
if (-not $InstallDir) {
    $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\Deep Code by C.Walia"
}
if (-not (Test-Path -LiteralPath $InstallDir) -and $PSScriptRoot) {
    if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "app\walia")) {
        $InstallDir = $PSScriptRoot
    }
}
$DataDir = ""
if ($m) { $DataDir = [string]$m.DataDir }
if (-not $DataDir) { $DataDir = Join-Path $env:LOCALAPPDATA "Deep Code by C.Walia" }

if ($models.Count -eq 0 -and ($RemoveModels -or $Full)) {
    $models = @(
        "qwen2.5-coder:0.5b", "qwen2.5-coder:1.5b", "qwen2.5-coder:3b",
        "qwen2.5-coder:7b", "qwen2.5-coder:14b", "qwen2.5-coder:32b",
        "deepseek-coder-v2:16b", "qwen3-coder:30b"
    )
}

Write-Host ""
Write-Host "App:         $($m.AppName) $($m.Version)" -ForegroundColor White
Write-Host "Install dir: $InstallDir" -ForegroundColor White
Write-Host "App data:    $DataDir" -ForegroundColor White
Write-Host "Model:       $($m.ModelProvider)" -ForegroundColor White
Write-Host "Installed:   $($m.InstalledAt)" -ForegroundColor White
Write-Host ""
if ($wingetPkgs.Count -gt 0) {
    Write-Host "Dependencies downloaded by setup:" -ForegroundColor Yellow
    foreach ($p in $wingetPkgs) { Write-Host "  - $p" -ForegroundColor Yellow }
}
if ($models.Count -gt 0) {
    Write-Host "AI models downloaded by setup:" -ForegroundColor Yellow
    foreach ($model in $models) { Write-Host "  - $model" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "Dependencies only listed above were installed by this setup and" -ForegroundColor DarkGray
Write-Host "were not already on the system. Shared tools can still be used by" -ForegroundColor DarkGray
Write-Host "other apps, so you will be asked before removing them." -ForegroundColor DarkGray
Write-Host ""

$removeModelsChoice = $RemoveModels
$removeDepsChoice = $PurgeDependencies
$removeDataChoice = -not $KeepData

if (-not $Silent) {
    if ($models.Count -gt 0) {
        $removeModelsChoice = Confirm-Action "Remove the AI models this setup downloaded?" $true
    }
    if ($wingetPkgs.Count -gt 0) {
        $removeDepsChoice = Confirm-Action "Also uninstall system dependencies it downloaded (Node, Python, Git, etc.)? May affect other apps" $false
    }
    $removeDataChoice = Confirm-Action "Remove chat history, settings, and the saved API key in $DataDir?" $true
    $proceed = Confirm-Action "Continue uninstalling Deep Code by C.Walia?" $true
    if (-not $proceed) {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# ------------------------------------------------------------------
# 1) Stop running app processes from this install
# ------------------------------------------------------------------
Write-Step "Stopping running app processes..."
try {
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -in @("node.exe", "python.exe", "pythonw.exe") -and
            $_.CommandLine -and $_.CommandLine -like "*$InstallDir*"
        }
    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "  Stopped process $($p.ProcessId)" -ForegroundColor DarkGray
        } catch {}
    }
} catch {
    Write-Host "  Could not enumerate processes." -ForegroundColor DarkGray
}

# ------------------------------------------------------------------
# 2) Remove AI models
# ------------------------------------------------------------------
if ($removeModelsChoice -and $models.Count -gt 0) {
    Write-Step "Removing AI models..."
    if (Test-Command "ollama") {
        foreach ($model in $models) {
            Write-Host "  Removing $model ..." -ForegroundColor Yellow
            & ollama rm $model
        }
    } else {
        Write-Host "  Ollama not found. Skipping model removal." -ForegroundColor Yellow
    }
} elseif ($models.Count -gt 0) {
    Write-Step "Keeping AI models" "Yellow"
}

# ------------------------------------------------------------------
# 2b) Remove saved API key
# ------------------------------------------------------------------
if ($removeDataChoice) {
    Write-Step "Removing saved API key..."
    $venvPy = Join-Path $InstallDir "venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPy) -and $m.PythonVenv) {
        $candidate = Join-Path ([string]$m.PythonVenv) "Scripts\python.exe"
        if (Test-Path -LiteralPath $candidate) { $venvPy = $candidate }
    }
    if (Test-Path -LiteralPath $venvPy) {
        $pyCode = "import keyring`ntry:`n    keyring.delete_password('walia-code', 'provider_api_key')`nexcept Exception:`n    pass"
        try { & $venvPy -c $pyCode 2>$null } catch {}
        Write-Host "  Windows Credential Manager entry cleared (if present)." -ForegroundColor DarkGray
    }
    try {
        if ([Environment]::GetEnvironmentVariable("WALIACODE_API_KEY", "User")) {
            [Environment]::SetEnvironmentVariable("WALIACODE_API_KEY", $null, "User")
            Write-Host "  Removed WALIACODE_API_KEY user environment variable." -ForegroundColor DarkGray
        }
    } catch {}
} else {
    Write-Step "Keeping saved API key" "Yellow"
}

# ------------------------------------------------------------------
# 3) Remove shortcuts
# ------------------------------------------------------------------
Write-Step "Removing shortcuts..."
foreach ($s in $shortcuts) {
    try {
        if ($s -and (Test-Path -LiteralPath $s)) {
            Remove-Item -LiteralPath $s -Force -ErrorAction SilentlyContinue
            Write-Host "  Removed $s" -ForegroundColor DarkGray
        }
    } catch {}
}
try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    foreach ($name in @("Deep Code by C.Walia.lnk", "Uninstall Deep Code by C.Walia.lnk")) {
        $p = Join-Path $desktop $name
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue }
    }
    if ($m.StartMenuFolder -and (Test-Path -LiteralPath $m.StartMenuFolder)) {
        Remove-Item -LiteralPath $m.StartMenuFolder -Recurse -Force -ErrorAction SilentlyContinue
    }
} catch {}

# ------------------------------------------------------------------
# 4) Remove Windows Apps & Features registration
# ------------------------------------------------------------------
Write-Step "Removing Apps & Features registration..."
try {
    $regPath = $m.RegistryKey
    if (-not $regPath) { $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepCodeByCWalia" }
    if (Test-Path $regPath) {
        Remove-Item -Path $regPath -Recurse -Force
        Write-Host "  Registry entry removed." -ForegroundColor DarkGray
    }
} catch {
    Write-Host "  Could not remove registry entry." -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 5) Uninstall system dependencies (only those recorded as installed here)
# ------------------------------------------------------------------
if ($removeDepsChoice -and $wingetPkgs.Count -gt 0) {
    Write-Step "Uninstalling system dependencies..."
    if (Test-Command "winget") {
        foreach ($pkg in $wingetPkgs) {
            Write-Host "  Uninstalling $pkg ..." -ForegroundColor Yellow
            & winget uninstall --id $pkg -e --silent --accept-source-agreements
        }
    } else {
        Write-Host "  winget not found. Remove dependencies manually if needed." -ForegroundColor Yellow
    }
} elseif ($wingetPkgs.Count -gt 0) {
    Write-Step "Keeping system dependencies" "Yellow"
}

# ------------------------------------------------------------------
# 5b) Remove app data (chats, config) unless kept
# ------------------------------------------------------------------
if ($removeDataChoice -and $DataDir -and (Test-Path -LiteralPath $DataDir) -and ($DataDir -ne $InstallDir)) {
    Write-Step "Removing app data..."
    try {
        Remove-Item -LiteralPath $DataDir -Recurse -Force -ErrorAction Stop
        Write-Host "  Removed $DataDir" -ForegroundColor DarkGray
    } catch {
        Write-Host "  Could not remove $DataDir - close the app and delete it manually." -ForegroundColor Yellow
    }
} elseif ($DataDir -and (Test-Path -LiteralPath $DataDir)) {
    Write-Step "Keeping app data" "Yellow"
}

if ($removeDataChoice) {
    $extraData = @(
        (Join-Path $env:APPDATA "Deep Code by C.Walia"),
        (Join-Path $HOME ".deepcode"),
        (Join-Path $env:LOCALAPPDATA "DeepCode")
    )
    foreach ($path in $extraData) {
        if ($path -and (Test-Path -LiteralPath $path) -and ($path -ne $InstallDir)) {
            try {
                Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
                Write-Host "  Removed $path" -ForegroundColor DarkGray
            } catch {
                Write-Host "  Could not remove $path" -ForegroundColor Yellow
            }
        }
    }
}

# ------------------------------------------------------------------
# 6) Remove install folder (delayed so current script files are unlockable)
# ------------------------------------------------------------------
if ($KeepInstallDir) {
    Write-Step "Keeping install folder (-KeepInstallDir)" "Yellow"
} else {
    Write-Step "Removing install folder..."
    Set-Location $env:TEMP
    $safeDir = $InstallDir.Replace("'", "''")
    $cleanup = "Start-Sleep -Seconds 2; Remove-Item -LiteralPath '$safeDir' -Recurse -Force -ErrorAction SilentlyContinue"
    try {
        Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cleanup) -WindowStyle Hidden | Out-Null
        Write-Host "  Install folder will be removed in a moment." -ForegroundColor DarkGray
    } catch {
        Write-Host "  Could not schedule folder removal. Delete manually: $InstallDir" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "             UNINSTALL COMPLETE                     " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Magenta

if (-not $Silent) {
    Write-Host "Press Enter to close"
    Read-Host | Out-Null
}
