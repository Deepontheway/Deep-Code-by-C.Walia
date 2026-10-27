# Deep Code by C.Walia - Full Setup (No Pinokio)
# Installs into its own Programs folder, shows a live overall percentage with
# elapsed/remaining time, creates shortcuts, registers an uninstaller and
# writes a manifest so Uninstall.cmd can remove only what this setup installed.
param(
    [switch]$InstallOnly,
    [switch]$SkipWinget,
    [switch]$SkipModels,
    [switch]$SkipPython,
    [switch]$SkipNpm,
    [switch]$NoCopy,
    [string]$InstallDir
)

$ErrorActionPreference = "Continue"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script:ManifestPath = $null

# ------------------------------------------------------------------
# Progress helpers
# ------------------------------------------------------------------
function Set-OverallProgress {
    param([int]$Pct, [string]$Status)
    if ($Pct -lt 0) { $Pct = 0 }
    if ($Pct -gt 100) { $Pct = 100 }
    Write-Progress -Id 1 -Activity "Deep Code by C.Walia Setup" -Status $Status -PercentComplete $Pct
}

function Format-Duration {
    param([double]$Seconds)
    if ($Seconds -lt 0) { $Seconds = 0 }
    $ts = [TimeSpan]::FromSeconds([int]$Seconds)
    if ($ts.TotalHours -ge 1) { return ("{0}:{1:mm\:ss}" -f [int]$ts.TotalHours, $ts) }
    return ("{0:mm\:ss}" -f $ts)
}

# Runs an external command, keeps its real output visible, and animates the
# overall progress bar with percent + elapsed + remaining time while it runs.
function Invoke-ProgressCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Label,
        [int]$StartPct,
        [int]$EndPct,
        [int]$ExpectedSeconds = 60,
        [switch]$IgnoreExitCode
    )

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Set-OverallProgress $StartPct $Label

    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments -NoNewWindow -PassThru -ErrorAction Stop
    } catch {
        Write-Host "  Could not start $FilePath : $_" -ForegroundColor Yellow
        return 1
    }

    while (-not $proc.HasExited) {
        $elapsed = $sw.Elapsed.TotalSeconds
        $ratio = $elapsed / [double][Math]::Max(1, $ExpectedSeconds)
        if ($ratio -gt 0.97) { $ratio = 0.97 }
        $pct = [int]($StartPct + (($EndPct - $StartPct) * $ratio))
        $remaining = $ExpectedSeconds - $elapsed
        $status = "$Label  |  elapsed $(Format-Duration $elapsed)  |  remaining ~$(Format-Duration $remaining)"
        Set-OverallProgress $pct $status
        Start-Sleep -Milliseconds 500
    }

    $code = $proc.ExitCode
    Set-OverallProgress $EndPct $Label
    if ($code -ne 0 -and -not $IgnoreExitCode) {
        Write-Host "  $Label exited with code $code (continuing)" -ForegroundColor Yellow
    }
    return $code
}

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

function Resolve-Winget {
    $cmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Test-ToolPresent {
    param([string]$Id)
    switch ($Id) {
        "OpenJS.NodeJS.LTS"       { return (Test-Command "node") }
        "Git.Git"                 { return (Test-Command "git") }
        "Python.Python.3.12"      { return ((Test-Command "python") -or (Test-Command "py")) }
        "Anaconda.Miniconda3"     { return (Test-Command "conda") }
        "Anaconda.Anaconda3"      { return (Test-Command "conda") }
        "SQLite.SQLite"           { return (Test-Command "sqlite3") }
        "Ollama.Ollama"           { return (Test-Command "ollama") }
        default                   { return $false }
    }
}

function Test-WingetPackage {
    param([string]$Id)
    $out = & winget list --id $Id -e --accept-source-agreements 2>$null | Out-String
    return ($out -match [regex]::Escape($Id))
}

function Install-WingetManaged {
    param(
        [string]$Id,
        [string]$Label,
        [int]$StartPct,
        [int]$EndPct,
        [int]$ExpectedSeconds
    )
    $already = ((Test-ToolPresent $Id) -or (Test-WingetPackage $Id))
    if ($already) {
        Write-Host "  $Label already installed - skipping" -ForegroundColor DarkGray
        Set-OverallProgress $EndPct "$Label already installed"
        return $false
    }

    $winget = Resolve-Winget
    if (-not $winget) { return $false }

    Write-Host "  Installing $Label ..." -ForegroundColor Green
    $args = @("install", "--id", $Id, "-e", "--accept-package-agreements", "--accept-source-agreements")
    Invoke-ProgressCommand -FilePath $winget -Arguments $args -Label "Installing $Label" -StartPct $StartPct -EndPct $EndPct -ExpectedSeconds $ExpectedSeconds | Out-Null

    $now = ((Test-ToolPresent $Id) -or (Test-WingetPackage $Id))
    if ((-not $already) -and $now) { return $true }
    return $false
}

function New-AppShortcut {
    param(
        [string]$Path,
        [string]$TargetPath,
        [string]$Arguments = "",
        [string]$WorkDir,
        [string]$IconPath,
        [string]$Description
    )
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($Path)
    $sc.TargetPath = $TargetPath
    if ($Arguments) { $sc.Arguments = $Arguments }
    $sc.WorkingDirectory = $WorkDir
    if ($IconPath -and (Test-Path $IconPath)) { $sc.IconLocation = "$IconPath,0" }
    $sc.Description = $Description
    $sc.Save()
}

function Merge-Unique {
    param($First, $Second)
    $list = New-Object System.Collections.Generic.List[string]
    foreach ($item in @($First)) {
        if ($item -and -not $list.Contains([string]$item)) { $list.Add([string]$item) }
    }
    foreach ($item in @($Second)) {
        if ($item -and -not $list.Contains([string]$item)) { $list.Add([string]$item) }
    }
    return ,$list.ToArray()
}

# ------------------------------------------------------------------
# Banner + install folder
# ------------------------------------------------------------------
Clear-Host
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "    DEEP CODE BY C.WALIA - FULL SETUP (NO PINOKIO)   " -ForegroundColor Magenta
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "   Live percentage + elapsed/remaining time shown    " -ForegroundColor DarkGray
Write-Host ""

Set-OverallProgress 0 "Starting setup..."

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $InstallDir) {
    if ($isAdmin) {
        $InstallDir = Join-Path $env:ProgramFiles "Deep Code by C.Walia"
    } else {
        $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\Deep Code by C.Walia"
    }
}

Write-Step "Source repo: $RepoRoot"
Write-Step "Install folder: $InstallDir"

if (-not $isAdmin -and $InstallDir -like "*Program Files*") {
    Write-Host "[WARNING] Writing to Program Files needs Administrator. Re-run as Admin." -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 1) Copy app into its own install folder
# ------------------------------------------------------------------
$srcFull = (Resolve-Path -LiteralPath $RepoRoot).Path.TrimEnd('\')
$dstFull = $InstallDir.TrimEnd('\')

if (-not $NoCopy -and ($srcFull -ne $dstFull)) {
    Set-OverallProgress 1 "Copying application files"
    Write-Step "Copying application files into install folder..."
    if (-not (Test-Path -LiteralPath $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }
    $rcArgs = @(
        $RepoRoot, $InstallDir,
        "/E", "/MT:8", "/R:2", "/W:2",
        "/XD", ".git", "node_modules", ".venv", "venv", "dist", "references", "__pycache__",
        "/XF", "*.log",
        "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
    )
    & robocopy @rcArgs | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host "robocopy reported errors (code $LASTEXITCODE). Continuing..." -ForegroundColor Yellow
    } else {
        Write-Host "Application files copied." -ForegroundColor Green
    }
    Set-OverallProgress 5 "Application files copied"
} else {
    Write-Host "Running directly from install folder - skipping copy." -ForegroundColor DarkGray
    Set-OverallProgress 5 "Using existing install folder"
}

Set-Location -LiteralPath $InstallDir

# ------------------------------------------------------------------
# Load old manifest (reinstall keeps uninstall knowledge)
# ------------------------------------------------------------------
$Script:ManifestPath = Join-Path $InstallDir "install-manifest.json"
$oldWinget = @()
$oldModels = @()
$oldShortcuts = @()
if (Test-Path -LiteralPath $Script:ManifestPath) {
    try {
        $old = Get-Content -Raw -LiteralPath $Script:ManifestPath | ConvertFrom-Json
        if ($old.WingetPackagesInstalled) { $oldWinget = @($old.WingetPackagesInstalled) }
        if ($old.OllamaModels) { $oldModels = @($old.OllamaModels) }
        if ($old.Shortcuts) { $oldShortcuts = @($old.Shortcuts) }
    } catch {}
}

$newWinget = New-Object System.Collections.Generic.List[string]
$newModels = New-Object System.Collections.Generic.List[string]
$newShortcuts = New-Object System.Collections.Generic.List[string]

# ------------------------------------------------------------------
# 2) System dependencies via winget (real winget progress + our bar)
# ------------------------------------------------------------------
if (-not $SkipWinget) {
    Write-Step "Installing system dependencies via winget..."
    $winget = Resolve-Winget
    if ($winget) {
        Write-Host "Winget also prints its own download progress below." -ForegroundColor DarkGray
        Start-Sleep -Seconds 1

        Write-Host "`n[1/7] Node.js LTS" -ForegroundColor Green
        if (Install-WingetManaged "OpenJS.NodeJS.LTS" "Node.js LTS" 5 11 120) { $newWinget.Add("OpenJS.NodeJS.LTS") }

        Write-Host "`n[2/7] Git" -ForegroundColor Green
        if (Install-WingetManaged "Git.Git" "Git" 11 15 90) { $newWinget.Add("Git.Git") }

        Write-Host "`n[3/7] Python 3.12" -ForegroundColor Green
        if (Install-WingetManaged "Python.Python.3.12" "Python 3.12" 15 20 120) { $newWinget.Add("Python.Python.3.12") }

        Write-Host "`n[4/7] Miniconda / Anaconda" -ForegroundColor Green
        $condaInstalled = Install-WingetManaged "Anaconda.Miniconda3" "Miniconda" 20 28 300
        if ($condaInstalled) {
            $newWinget.Add("Anaconda.Miniconda3")
        } else {
            $condaAlready = ((Test-ToolPresent "Anaconda.Miniconda3") -or (Test-WingetPackage "Anaconda.Miniconda3"))
            if (-not $condaAlready) {
                if (Install-WingetManaged "Anaconda.Anaconda3" "Anaconda" 28 36 420) { $newWinget.Add("Anaconda.Anaconda3") }
            }
        }

        Write-Host "`n[5/7] SQLite" -ForegroundColor Green
        if (Install-WingetManaged "SQLite.SQLite" "SQLite" 36 38 45) { $newWinget.Add("SQLite.SQLite") }

        Write-Host "`n[6/7] Visual Studio 2022 Build Tools" -ForegroundColor Green
        if (Install-WingetManaged "Microsoft.VisualStudio.2022.BuildTools" "VS 2022 Build Tools" 38 44 900) {
            $newWinget.Add("Microsoft.VisualStudio.2022.BuildTools")
        }

        Write-Host "`n[7/7] Ollama" -ForegroundColor Green
        if (Install-WingetManaged "Ollama.Ollama" "Ollama" 44 48 180) { $newWinget.Add("Ollama.Ollama") }

        Write-Host "`nWinget installs finished." -ForegroundColor Green
    } else {
        Write-Host "winget not found. Install missing tools manually." -ForegroundColor Yellow
    }
} else {
    Write-Step "Skipping winget (-SkipWinget)" "Yellow"
}
Set-OverallProgress 48 "System dependencies done"

# ------------------------------------------------------------------
# 3) Refresh PATH
# ------------------------------------------------------------------
Write-Step "Refreshing PATH..."
Set-OverallProgress 49 "Refreshing PATH"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
Start-Sleep -Seconds 2

# ------------------------------------------------------------------
# 4) Node / npm
# ------------------------------------------------------------------
Write-Step "Checking Node.js and npm..."
Set-OverallProgress 50 "Checking Node.js and npm"
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
# 5) Python
# ------------------------------------------------------------------
Write-Step "Checking Python..."
Set-OverallProgress 52 "Checking Python"
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
# 6) Python dependencies
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

$venvPath = $null
if ($SkipPython) {
    Write-Step "Skipping Python dependencies (-SkipPython)" "Yellow"
} elseif ($pyReq -and $pythonCmd) {
    Write-Step "Installing Python dependencies from $pyReq..."
    Set-OverallProgress 54 "Preparing Python environment"
    if (-not (Test-Path $pyVenv)) {
        Write-Host "Creating virtual environment at $pyVenv ..." -ForegroundColor Yellow
        try { & $pythonCmd -m venv $pyVenv } catch {}
    }
    $venvPy = Join-Path $pyVenv "Scripts\python.exe"
    if (-not (Test-Path $venvPy)) { $venvPy = $pythonCmd }

    & $venvPy -m pip install --upgrade pip | Out-Null
    Invoke-ProgressCommand -FilePath $venvPy -Arguments @("-m", "pip", "install", "-r", $pyReq) -Label "Installing Python packages" -StartPct 54 -EndPct 62 -ExpectedSeconds 180 | Out-Null
    if (Test-Path (Join-Path $pyVenv "Scripts\python.exe")) {
        $venvPath = (Resolve-Path -LiteralPath $pyVenv).Path
    }
    Write-Host "Python dependencies installed." -ForegroundColor Green
}
Set-OverallProgress 62 "Python dependencies done"

# ------------------------------------------------------------------
# 7) npm install (npm shows its own real progress too)
# ------------------------------------------------------------------
Write-Step "Installing npm dependencies..."
Write-Host "This can take 5-15 minutes. npm shows download/reify progress below." -ForegroundColor DarkGray
Start-Sleep -Seconds 1

if ($SkipNpm) {
    Write-Host "Skipping npm install (-SkipNpm)." -ForegroundColor Yellow
} elseif ($npmCmd) {
    & $npmCmd config set progress true | Out-Null
    & $npmCmd config set loglevel notice | Out-Null
    Invoke-ProgressCommand -FilePath $npmCmd -Arguments @("install", "--legacy-peer-deps", "--no-audit", "--no-fund") -Label "Installing npm packages" -StartPct 62 -EndPct 85 -ExpectedSeconds 480 | Out-Null
    Write-Host "`nnpm install completed." -ForegroundColor Green
} else {
    Write-Host "Skipping npm install because npm was not found." -ForegroundColor Yellow
}
Set-OverallProgress 85 "npm dependencies done"

# ------------------------------------------------------------------
# 8) Ollama models (ollama shows its own real download % too)
# ------------------------------------------------------------------
$models = @("qwen3-coder:14b", "qwen2.5-coder:32b", "deepseek-coder-v2:16b")
$existingModels = @()
if (Test-Command "ollama") {
    $listOut = & ollama list 2>$null | Out-String
    $existingModels = @($models | Where-Object { $listOut -match [regex]::Escape($_) })
}

if (-not $SkipModels) {
    Write-Step "Pulling recommended Ollama models..."
    if (Test-Command "ollama") {
        $modelStart = 85
        $modelSpan = 8
        $per = [int]($modelSpan / $models.Count)
        $i = 0
        foreach ($model in $models) {
            $i++
            $start = $modelStart + (($i - 1) * $per)
            $end = $start + $per
            if ($existingModels -contains $model) {
                Write-Host "Model $i/$($models.Count): $model already present - skipping" -ForegroundColor DarkGray
                Set-OverallProgress $end "$model already present"
                continue
            }
            Write-Host "Model $i/$($models.Count): $model" -ForegroundColor Yellow
            $rc = Invoke-ProgressCommand -FilePath "ollama.exe" -Arguments @("pull", $model) -Label "Downloading $model" -StartPct $start -EndPct $end -ExpectedSeconds 300
            if ($rc -eq 0) { $newModels.Add($model) }
        }
        Write-Host "Ollama models ready." -ForegroundColor Green
    } else {
        Write-Host "Ollama not found. Pull models later with: ollama pull <model>" -ForegroundColor Yellow
    }
} else {
    Write-Step "Skipping Ollama models (-SkipModels)" "Yellow"
}
Set-OverallProgress 93 "AI models done"

# ------------------------------------------------------------------
# 9) Shortcuts (Desktop + Start Menu)
# ------------------------------------------------------------------
Write-Step "Creating shortcuts..."
Set-OverallProgress 94 "Creating shortcuts"
$runBat = Join-Path $InstallDir "RUN_DEEP_CODE_NO_PINOKIO.bat"
$uninstallCmd = Join-Path $InstallDir "Uninstall.cmd"
$iconPath = Join-Path $InstallDir "icon.png"
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenuPrograms = [Environment]::GetFolderPath("Programs")
$startMenuFolder = Join-Path $startMenuPrograms "Deep Code by C.Walia"

if (-not (Test-Path -LiteralPath $startMenuFolder)) {
    New-Item -ItemType Directory -Path $startMenuFolder -Force | Out-Null
}

$desktopStart = Join-Path $desktop "Deep Code by C.Walia.lnk"
$desktopUninstall = Join-Path $desktop "Uninstall Deep Code by C.Walia.lnk"
$startStart = Join-Path $startMenuFolder "Deep Code by C.Walia.lnk"
$startUninstall = Join-Path $startMenuFolder "Uninstall Deep Code by C.Walia.lnk"

try {
    New-AppShortcut -Path $desktopStart -TargetPath $runBat -WorkDir $InstallDir -IconPath $iconPath -Description "Start Deep Code by C.Walia"
    New-AppShortcut -Path $desktopUninstall -TargetPath $uninstallCmd -WorkDir $InstallDir -IconPath $iconPath -Description "Uninstall Deep Code by C.Walia"
    New-AppShortcut -Path $startStart -TargetPath $runBat -WorkDir $InstallDir -IconPath $iconPath -Description "Start Deep Code by C.Walia"
    New-AppShortcut -Path $startUninstall -TargetPath $uninstallCmd -WorkDir $InstallDir -IconPath $iconPath -Description "Uninstall Deep Code by C.Walia"
    foreach ($s in @($desktopStart, $desktopUninstall, $startStart, $startUninstall)) { $newShortcuts.Add($s) }
    Write-Host "Desktop and Start Menu shortcuts created." -ForegroundColor Green
} catch {
    Write-Host "Shortcut creation failed: $_" -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 10) Register in Windows Apps & Features
# ------------------------------------------------------------------
Write-Step "Registering app in Windows Apps & Features..."
Set-OverallProgress 96 "Registering app"
try {
    $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepCodeByCWalia"
    $sizeKb = 0
    try {
        $sizeKb = [int]((Get-ChildItem -LiteralPath $InstallDir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1KB)
    } catch {}

    if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }
    Set-ItemProperty -Path $regPath -Name "DisplayName" -Value "Deep Code by C.Walia"
    Set-ItemProperty -Path $regPath -Name "DisplayVersion" -Value "0.1.0"
    Set-ItemProperty -Path $regPath -Name "Publisher" -Value "C.Walia"
    Set-ItemProperty -Path $regPath -Name "InstallLocation" -Value $InstallDir
    Set-ItemProperty -Path $regPath -Name "DisplayIcon" -Value $iconPath
    Set-ItemProperty -Path $regPath -Name "UninstallString" -Value "`"$uninstallCmd`""
    Set-ItemProperty -Path $regPath -Name "QuietUninstallString" -Value "powershell.exe -ExecutionPolicy Bypass -NoProfile -File `"$InstallDir\uninstall.ps1`" -Silent"
    Set-ItemProperty -Path $regPath -Name "EstimatedSize" -Value $sizeKb -Type DWord
    Set-ItemProperty -Path $regPath -Name "NoModify" -Value 1 -Type DWord
    Set-ItemProperty -Path $regPath -Name "NoRepair" -Value 1 -Type DWord
    Write-Host "Registered in Apps & Features." -ForegroundColor Green
} catch {
    Write-Host "Registry registration failed: $_" -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 11) Write install manifest (used by Uninstall.cmd)
# ------------------------------------------------------------------
Write-Step "Writing install manifest..."
Set-OverallProgress 99 "Writing install manifest"
$manifest = [ordered]@{
    AppName                  = "Deep Code by C.Walia"
    Version                  = "0.1.0"
    InstalledAt              = (Get-Date).ToString("o")
    InstallDir               = $InstallDir
    InstallerSource          = $RepoRoot
    WingetPackagesInstalled  = (Merge-Unique $oldWinget $newWinget)
    OllamaModels             = (Merge-Unique $oldModels $newModels)
    Shortcuts                = (Merge-Unique $oldShortcuts $newShortcuts)
    StartMenuFolder          = $startMenuFolder
    PythonVenv               = $venvPath
    RegistryKey              = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepCodeByCWalia"
}

$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Script:ManifestPath -Encoding UTF8
Write-Host "Manifest saved: $Script:ManifestPath" -ForegroundColor Green

Set-OverallProgress 100 "Setup complete"
Start-Sleep -Milliseconds 300

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------
Write-Host ""
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "                 SETUP COMPLETE                     " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "Installed at: $InstallDir" -ForegroundColor Cyan
Write-Host "Start:      Deep Code by C.Walia.lnk (Desktop / Start Menu)" -ForegroundColor Cyan
Write-Host "Uninstall:  Uninstall.cmd in the install folder, Start Menu," -ForegroundColor Cyan
Write-Host "            or Windows Settings > Apps" -ForegroundColor Cyan
Write-Host ""
Write-Host "Uninstall removes the app plus only the models/packages this" -ForegroundColor DarkGray
Write-Host "setup downloaded (it asks before removing anything shared)." -ForegroundColor DarkGray

if ($InstallOnly) {
    Write-Host "`nInstallOnly specified. Exiting."
    exit 0
}

Write-Step "Starting Deep Code by C.Walia..."
if ($npmCmd) {
    & $npmCmd run dev
}
