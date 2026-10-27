# Deep Code by C.Walia - Direct Install From GitHub (No Pinokio, No Clone)
# Downloads the latest source ZIP from GitHub with a live percentage, speed and
# remaining-time display, then runs the full setup.
#
# One-liner:
#   irm https://raw.githubusercontent.com/Deepontheway/Deep-Code-by-C.Walia/main/Install-FromGitHub.ps1 | iex
param(
    [switch]$SkipWinget,
    [switch]$SkipModels,
    [switch]$DownloadOnly,
    [switch]$NoLaunch,
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"

$RepoZipUrl = "https://github.com/Deepontheway/Deep-Code-by-C.Walia/archive/refs/heads/main.zip"
$StageDir = Join-Path $env:TEMP ("walia-github-install-" + [Guid]::NewGuid().ToString("N").Substring(0, 8))
$ZipPath = Join-Path $StageDir "repo.zip"
$ExtractDir = Join-Path $StageDir "src"

function Format-Duration {
    param([double]$Seconds)
    if ($Seconds -lt 0) { $Seconds = 0 }
    $ts = [TimeSpan]::FromSeconds([int]$Seconds)
    if ($ts.TotalHours -ge 1) { return ("{0}:{1:mm\:ss}" -f [int]$ts.TotalHours, $ts) }
    return ("{0:mm\:ss}" -f $ts)
}

function Download-WithProgress {
    param([string]$Url, [string]$OutFile)

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $request = [Net.HttpWebRequest]::Create($Url)
    $request.UserAgent = "DeepCodeInstaller"
    $request.AllowAutoRedirect = $true
    $request.Timeout = 60000

    $response = $request.GetResponse()
    $total = $response.ContentLength
    $stream = $response.GetResponseStream()
    $file = [IO.File]::Create($OutFile)
    $buffer = New-Object byte[] 1048576
    $read = [long]0
    $sw = [Diagnostics.Stopwatch]::StartNew()

    try {
        while (($count = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $file.Write($buffer, 0, $count)
            $read += $count
            $elapsed = $sw.Elapsed.TotalSeconds
            if ($elapsed -le 0) { $elapsed = 0.001 }
            $speed = $read / $elapsed

            if ($total -gt 0) {
                $pct = [int](100 * $read / $total)
                if ($pct -gt 100) { $pct = 100 }
                $remaining = ($total - $read) / $speed
                $status = "{0:N2} / {1:N2} MB  |  {2:N0} KB/s  |  remaining ~{3}" -f ($read / 1MB), ($total / 1MB), ($speed / 1KB), (Format-Duration $remaining)
                Write-Progress -Id 1 -Activity "Downloading Deep Code by C.Walia from GitHub" -Status $status -PercentComplete $pct
            } else {
                $status = "{0:N2} MB downloaded  |  {1:N0} KB/s" -f ($read / 1MB), ($speed / 1KB)
                Write-Progress -Id 1 -Activity "Downloading Deep Code by C.Walia from GitHub" -Status $status
            }
        }
    } finally {
        $file.Close()
        $stream.Close()
        $response.Close()
    }
    Write-Progress -Id 1 -Activity "Downloading Deep Code by C.Walia from GitHub" -Completed
}

function Expand-WithProgress {
    param([string]$ZipFile, [string]$Destination)

    Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null
    $zip = [IO.Compression.ZipFile]::OpenRead($ZipFile)
    try {
        $totalEntries = $zip.Entries.Count
        $done = 0
        foreach ($entry in $zip.Entries) {
            $done++
            $relative = $entry.FullName -replace '/', '\'
            $target = Join-Path $Destination $relative
            if ([string]::IsNullOrEmpty($entry.Name)) {
                if (-not (Test-Path -LiteralPath $target)) {
                    New-Item -ItemType Directory -Path $target -Force | Out-Null
                }
                continue
            }
            $parent = Split-Path -Parent $target
            if (-not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
            if ($totalEntries -gt 0) {
                $pct = [int](100 * $done / $totalEntries)
                Write-Progress -Id 1 -Activity "Extracting source files" -Status "$done / $totalEntries files" -PercentComplete $pct
            }
        }
    } finally {
        $zip.Dispose()
    }
    Write-Progress -Id 1 -Activity "Extracting source files" -Completed
}

function Invoke-Setup {
    param([string]$SetupPath, [string[]]$ForwardArgs)

    $psArgs = @("-ExecutionPolicy", "Bypass", "-NoProfile", "-File", $SetupPath) + $ForwardArgs
    & powershell.exe @psArgs 2>&1 | Out-Host
    return $LASTEXITCODE
}

# ------------------------------------------------------------------
# Start
# ------------------------------------------------------------------
Clear-Host
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "   DEEP CODE BY C.WALIA - INSTALL FROM GITHUB        " -ForegroundColor Magenta
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "   No clone, no Pinokio. Live % / speed / remaining.  " -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path -LiteralPath $StageDir)) {
    New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
}

try {
    Write-Host "[1/4] Downloading source from GitHub..." -ForegroundColor Cyan
    Write-Host "      $RepoZipUrl" -ForegroundColor DarkGray
    Download-WithProgress -Url $RepoZipUrl -OutFile $ZipPath
    $zipSize = (Get-Item -LiteralPath $ZipPath).Length
    Write-Host ("      Download complete: {0:N2} MB" -f ($zipSize / 1MB)) -ForegroundColor Green

    if ($DownloadOnly) {
        Write-Host "DownloadOnly specified. ZIP kept at: $ZipPath" -ForegroundColor Yellow
        exit 0
    }

    Write-Host ""
    Write-Host "[2/4] Extracting source..." -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $ExtractDir)) {
        New-Item -ItemType Directory -Path $ExtractDir -Force | Out-Null
    }
    Expand-WithProgress -ZipFile $ZipPath -Destination $ExtractDir

    $setup = Get-ChildItem -LiteralPath $ExtractDir -Recurse -Filter "FULL_SETUP_NO_PINOKIO.ps1" -File |
        Select-Object -First 1
    if (-not $setup) {
        throw "Could not find FULL_SETUP_NO_PINOKIO.ps1 in the downloaded source."
    }
    Write-Host "      Extracted to: $($setup.DirectoryName)" -ForegroundColor Green

    Write-Host ""
    Write-Host "[3/4] Running full setup (this installs everything)..." -ForegroundColor Cyan
    Write-Host "----------------------------------------------------" -ForegroundColor DarkGray

    $forward = @("-InstallOnly")
    if ($SkipWinget) { $forward += "-SkipWinget" }
    if ($SkipModels) { $forward += "-SkipModels" }
    if ($InstallDir) { $forward += @("-InstallDir", $InstallDir) }

    $setupExit = Invoke-Setup -SetupPath $setup.FullName -ForwardArgs $forward

    Write-Host "----------------------------------------------------" -ForegroundColor DarkGray
    if ($setupExit -ne 0) {
        Write-Host "Setup exited with code $setupExit. Check the messages above." -ForegroundColor Yellow
    } else {
        Write-Host "[4/4] Setup finished." -ForegroundColor Green
    }

    if (-not $InstallDir) {
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
        if ($isAdmin) {
            $InstallDir = Join-Path $env:ProgramFiles "Deep Code by C.Walia"
        } else {
            $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\Deep Code by C.Walia"
        }
    }

    $runBat = Join-Path $InstallDir "RUN_DEEP_CODE_NO_PINOKIO.bat"
    if (-not $NoLaunch -and (Test-Path -LiteralPath $runBat)) {
        Write-Host ""
        Write-Host "Launching Deep Code by C.Walia..." -ForegroundColor Cyan
        Start-Process -FilePath $runBat -WorkingDirectory $InstallDir | Out-Null
    } else {
        Write-Host ""
        Write-Host "Start it from the Desktop / Start Menu shortcut:" -ForegroundColor Cyan
        Write-Host "  Deep Code by C.Walia" -ForegroundColor White
        Write-Host "Installed at: $InstallDir" -ForegroundColor DarkGray
    }
} catch {
    Write-Host ""
    Write-Host "Install from GitHub failed: $_" -ForegroundColor Red
    Write-Host "You can also download the ZIP manually:" -ForegroundColor Yellow
    Write-Host "  https://github.com/Deepontheway/Deep-Code-by-C.Walia/archive/refs/heads/main.zip" -ForegroundColor Yellow
    Write-Host "then run FULL_SETUP_NO_PINOKIO.bat inside it." -ForegroundColor Yellow
    if (-not $DownloadOnly) {
        Write-Host "Press Enter to close"
        Read-Host | Out-Null
    }
    exit 1
} finally {
    if ($DownloadOnly) {
        if (Test-Path -LiteralPath $ZipPath) {
            Write-Host "ZIP kept at: $ZipPath" -ForegroundColor Yellow
        }
    } else {
        Write-Host ""
        Write-Host "Cleaning temporary files..." -ForegroundColor DarkGray
        try {
            Set-Location $env:TEMP
            Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}
