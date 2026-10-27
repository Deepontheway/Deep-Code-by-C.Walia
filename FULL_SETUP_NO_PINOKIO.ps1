# Deep Code by C.Walia - Full Setup (No Pinokio)
# Installs all dependencies with REAL live progress (% complete, speed, remaining time)
param(
    [switch]$InstallOnly,
    [switch]$SkipWinget,
    [switch]$SkipModels
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

function Write-Step {
    param([string]$Msg, [string]$Color = "Cyan")
    Write-Host ""
    Write-Host "[DEEP-CODE-SETUP] $Msg" -ForegroundColor $Color
}

function Test-Command {
    param([string]$Cmd)
    $null = Get-Command $Cmd -ErrorAction SilentlyContinue
    return $?
}

function Resolve-Npm {
    $cmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $fallback = "C:\Program Files\nodejs\npm.cmd"
    if (Test-Path $fallback) { return $fallback }
    return $null
}

Clear-Host
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "    DEEP CODE BY C.WALIA - FULL SETUP (NO PINOKIO)   " -ForegroundColor Magenta
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "   Live download percentages, speed and ETA shown   " -ForegroundColor DarkGray
Write-Host ""

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin -and -not $SkipWinget) {
    Write-Host "[WARNING] Not running as Administrator. Winget may prompt for UAC." -ForegroundColor Yellow
}

Write-Step "Repo: $RepoRoot"

# ------------------------------------------------------------------
# 1) System dependencies via winget (live progress comes from winget)
# ------------------------------------------------------------------
if (-not $SkipWinget) {
    Write-Step "Installing system dependencies via winget..."
    if (Test-Command "winget") {
        Write-Host "Winget will show its own progress bar (percent, speed, ETA)." -ForegroundColor DarkGray
        Start-Sleep -Seconds 2

        Write-Host "`n[1/7] Node.js LTS" -ForegroundColor Green
        winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements

        Write-Host "`n[2/7] Git" -ForegroundColor Green
        winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements

        Write-Host "`n[3/7] Python 3.12" -ForegroundColor Green
        winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements

        Write-Host "`n[4/7] Miniconda / Anaconda" -ForegroundColor Green
        winget install --id Anaconda.Miniconda3 -e --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            winget install --id Anaconda.Anaconda3 -e --accept-package-agreements --accept-source-agreements
        }

        Write-Host "`n[5/7] SQLite" -ForegroundColor Green
        winget install --id SQLite.SQLite -e --accept-package-agreements --accept-source-agreements

        Write-Host "`n[6/7] Visual Studio 2022 Build Tools" -ForegroundColor Green
        winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-package-agreements --accept-source-agreements

        Write-Host "`n[7/7] Ollama" -ForegroundColor Green
        winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements

        Write-Host "`nWinget installs finished." -ForegroundColor Green
    } else {
        Write-Host "winget not found. Install missing tools manually." -ForegroundColor Yellow
    }
} else {
    Write-Step "Skipping winget (-SkipWinget)" "Yellow"
}

# ------------------------------------------------------------------
# 2) Refresh PATH so new tools are visible
# ------------------------------------------------------------------
Write-Step "Refreshing PATH..."
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
Start-Sleep -Seconds 2

# ------------------------------------------------------------------
# 3) Node / npm
# ------------------------------------------------------------------
Write-Step "Checking Node.js and npm..."
$npmCmd = Resolve-Npm
if (Test-Command "node") {
    Write-Host "Node: $(node -v)" -ForegroundColor Green
} else {
    Write-Host "Node not found in PATH." -ForegroundColor Yellow
}
if ($npmCmd) {
    Write-Host "npm:  $(& $npmCmd -v)" -ForegroundColor Green
} else {
    Write-Host "npm not found. Install Node.js LTS then re-run." -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 4) Python
# ------------------------------------------------------------------
Write-Step "Checking Python..."
$pythonCmd = $null
if (Test-Command "py") { $pythonCmd = "py" }
elseif (Test-Command "python") { $pythonCmd = "python" }
elseif (Test-Command "python3") { $pythonCmd = "python3" }

if ($pythonCmd) {
    Write-Host "Python: $(& $pythonCmd --version)" -ForegroundColor Green
    try { & $pythonCmd -m pip install --upgrade pip } catch {}
} else {
    Write-Host "Python not found." -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 5) Python dependencies (app/requirements.txt or root requirements.txt)
# ------------------------------------------------------------------
$pyReq = $null
$pyVenv = $null
if (Test-Path "app\requirements.txt") {
    $pyReq = "app\requirements.txt"
    $pyVenv = "app\venv"
} elseif (Test-Path "requirements.txt") {
    $pyReq = "requirements.txt"
    $pyVenv = "venv"
}

if ($pyReq -and $pythonCmd) {
    Write-Step "Installing Python dependencies from $pyReq (live progress below)..."
    if (-not (Test-Path $pyVenv)) {
        Write-Host "Creating virtual environment at $pyVenv ..." -ForegroundColor Yellow
        try { & $pythonCmd -m venv $pyVenv } catch {}
    }
    $venvPy = Join-Path $pyVenv "Scripts\python.exe"
    if (Test-Path $venvPy) {
        & $venvPy -m pip install --upgrade pip
        & $venvPy -m pip install -r $pyReq
    } else {
        & $pythonCmd -m pip install -r $pyReq
    }
    Write-Host "Python dependencies installed." -ForegroundColor Green
}

# ------------------------------------------------------------------
# 6) npm install (live progress: fetching / reifying / adding %)
# ------------------------------------------------------------------
Write-Step "Installing npm dependencies (live progress below)..."
Write-Host "This can take 5-15 minutes. npm shows download/reify progress." -ForegroundColor DarkGray
Start-Sleep -Seconds 2

if ($npmCmd) {
    & $npmCmd config set progress true | Out-Null
    & $npmCmd config set loglevel notice | Out-Null
    & $npmCmd install --legacy-peer-deps --no-audit --no-fund
    Write-Host "`nnpm install completed." -ForegroundColor Green
} else {
    Write-Host "Skipping npm install because npm was not found." -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 7) Ollama models (live progress: pulling / downloading % / ETA)
# ------------------------------------------------------------------
if (-not $SkipModels) {
    Write-Step "Pulling recommended Ollama models (live progress below)..."
    if (Test-Command "ollama") {
        Write-Host "Model 1/3: qwen3-coder:14b" -ForegroundColor Yellow
        ollama pull qwen3-coder:14b
        Write-Host "Model 2/3: qwen2.5-coder:32b" -ForegroundColor Yellow
        ollama pull qwen2.5-coder:32b
        Write-Host "Model 3/3: deepseek-coder-v2:16b" -ForegroundColor Yellow
        ollama pull deepseek-coder-v2:16b
        Write-Host "Ollama models ready." -ForegroundColor Green
    } else {
        Write-Host "Ollama not found. Pull models later with: ollama pull <model>" -ForegroundColor Yellow
    }
} else {
    Write-Step "Skipping Ollama models (-SkipModels)" "Yellow"
}

# ------------------------------------------------------------------
# 8) Desktop shortcut
# ------------------------------------------------------------------
Write-Step "Creating desktop shortcut..."
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $Desktop "Deep Code by C.Walia.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = Join-Path $RepoRoot "RUN_DEEP_CODE_NO_PINOKIO.bat"
    $Shortcut.WorkingDirectory = $RepoRoot
    if (Test-Path (Join-Path $RepoRoot "icon.png")) {
        $Shortcut.IconLocation = (Join-Path $RepoRoot "icon.png") + ",0"
    }
    $Shortcut.Description = "Start Deep Code by C.Walia (No Pinokio)"
    $Shortcut.Save()
    Write-Host "Shortcut created: $ShortcutPath" -ForegroundColor Green
} catch {
    Write-Host "Failed to create shortcut: $_" -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------
Write-Host ""
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "                 SETUP COMPLETE                     " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "Launch anytime with the desktop shortcut:" -ForegroundColor Cyan
Write-Host "  Deep Code by C.Walia.lnk" -ForegroundColor Cyan

if ($InstallOnly) {
    Write-Host "`nInstallOnly specified. Exiting."
    exit 0
}

Write-Step "Starting Deep Code by C.Walia..."
if ($npmCmd) {
    & $npmCmd run dev
}
