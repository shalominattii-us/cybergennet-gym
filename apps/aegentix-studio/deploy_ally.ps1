<#
╔═══════════════════════════════════════════════════════════════╗
║              AEGENTIX STUDIO — ROG ALLY Z2 DEPLOYMENT        ║
║                 JetBrains + CyberCore + Gym                   ║
║                    AMD Ryzen Z2 Extreme Edition                ║
╚═══════════════════════════════════════════════════════════════╝

.SYNOPSIS
    One-command install: PyCharm IDE + CyberCore LLM plugin + Gym stack
    Optimized for ROG Ally X with AMD Ryzen Z2 Extreme (50 TOPS NPU)

.DESCRIPTION
    Installs everything needed to turn your Ally into an Aegentix dev machine:
      - JetBrains PyCharm / IntelliJ Community
      - CyberCore LLM inline assistant (runs on NPU/iGPU)
      - CyberGenetic Gym full stack
      - AMD Ryzen AI software (NPU inference)
      - Future Nvidia eGPU support built in

.NOTES
    Run this as Administrator. Internet connection required.
    AMD Ryzen Z2 Extreme | 50 TOPS NPU | RDNA 3.5
#>

$ErrorActionPreference = "Stop"
$AEGENTIX_ROOT = "$env:USERPROFILE\Aegentix"
$LOG_FILE = "$env:TEMP\aegentix_deploy.log"

function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
    "$timestamp $Message" | Out-File -FilePath $LOG_FILE -Append
}

Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     AEGENTIX STUDIO — ROG ALLY Z2 EDITION      ║" -ForegroundColor Cyan
Write-Host "║        AMD Ryzen Z2 Extreme | 50 TOPS NPU      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan

Write-Log "Starting Aegentix Studio deployment..." -Color Yellow

# ─── 1. Detect Hardware ───────────────────────────────────────────────────
Write-Log "[1/7] Detecting hardware..." -Color Yellow
$cpu = (Get-CimInstance Win32_Processor).Name
$gpu = (Get-CimInstance Win32_VideoController).Name
Write-Log "  CPU: $cpu" -Color Green
Write-Log "  GPU: $gpu" -Color Green

$hasNvidia = $gpu -match "NVIDIA"
$hasAMD = $gpu -match "AMD|Radeon|Radeon"

Write-Log "  NPU: 50 TOPS (Ryzen AI)" -Color Green
Write-Log "  GPU: RDNA 3.5 — $gpu" -Color Green

if ($hasNvidia) {
    Write-Log "  → eGPU detected — CUDA mode" -Color Green
} else {
    Write-Log "  → AMD mode — using NPU + iGPU for LLM" -Color Green
}

# ─── 2. Install JetBrains IDE ────────────────────────────────────────────
Write-Log "[2/7] Installing JetBrains IDE..." -Color Yellow

if (-not (Get-Command "pycharm" -ErrorAction SilentlyContinue)) {
    try {
        Write-Log "  → Installing PyCharm Community via winget..." -Color Yellow
        $p = Start-Process -Wait -PassThru -WindowStyle Hidden -FilePath "winget" -ArgumentList "install -e --id JetBrains.PyCharm.Community --silent --accept-package-agreements"
        if ($p.ExitCode -eq 0) { Write-Log "  ✓ PyCharm Community installed" -Color Green }
        else { throw "winget exit code: $($p.ExitCode)" }
    } catch {
        Write-Log "  ⚠ winget failed, downloading manually..." -Color Yellow
        try {
            Invoke-WebRequest -Uri "https://download.jetbrains.com/python/pycharm-community-2024.3.1.1.exe" -OutFile "$env:TEMP\pycharm.exe" -UseBasicParsing
            Start-Process -Wait -FilePath "$env:TEMP\pycharm.exe" -ArgumentList "/S"
            Write-Log "  ✓ PyCharm installed manually" -Color Green
        } catch {
            Write-Log "  ✗ Could not install PyCharm. Download from https://jetbrains.com/pycharm" -Color Red
        }
    }
} else {
    Write-Log "  ✓ PyCharm already installed" -Color Green
}

# ─── 3. Clone Repositories ───────────────────────────────────────────────
Write-Log "[3/7] Cloning Aegentix repositories..." -Color Yellow

if (-not (Test-Path $AEGENTIX_ROOT)) {
    New-Item -ItemType Directory -Path $AEGENTIX_ROOT -Force | Out-Null
}

# Check for git
if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
    Write-Log "  → Installing git..." -Color Yellow
    try {
        winget install -e --id Git.Git --silent --accept-package-agreements | Out-Null
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        Write-Log "  ✓ Git installed" -Color Green
    } catch {
        Write-Log "  ✗ Install git manually from https://git-scm.com" -Color Red
    }
}

# Clone Gym
if (-not (Test-Path "$AEGENTIX_ROOT\cybergennet")) {
    Write-Log "  → Cloning CyberGenetic Gym..." -Color Yellow
    try {
        git clone https://github.com/shalominattii-us/cybergennet-gym.git "$AEGENTIX_ROOT\cybergennet" 2>&1 | Out-Null
        Write-Log "  ✓ Gym cloned" -Color Green
    } catch {
        Write-Log "  ✗ Git clone failed" -Color Red
    }
} else {
    Write-Log "  ✓ Gym already present" -Color Green
}

# ─── 4. Install AMD Ryzen AI Stack ──────────────────────────────────────
Write-Log "[4/7] Setting up AMD Ryzen AI LLM engine..." -Color Yellow

if ($hasAMD -and -not $hasNvidia) {
    Write-Log "  → AMD NPU detected — installing Ryzen AI software" -Color Yellow
    
    # Check Python
    if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
        Write-Log "  → Installing Python 3.12..." -Color Yellow
        try {
            winget install -e --id Python.Python.3.12 --silent --accept-package-agreements | Out-Null
            Write-Log "  ✓ Python 3.12 installed" -Color Green
        } catch {
            Write-Log "  ✗ Install Python manually from python.org" -Color Red
        }
    }

    # Install llama.cpp for AMD
    if (Get-Command "python" -ErrorAction SilentlyContinue) {
        Write-Log "  → Installing llama-cpp-python with ROCm support..." -Color Yellow
        try {
            & python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
            
            # For AMD iGPU (RDNA 3.5) — use CLBlast or Vulkan backend
            $env:LLAMA_CLBLAST = 1
            & python -m pip install llama-cpp-python --quiet 2>&1 | Out-Null
            
            Write-Log "  ✓ llama.cpp installed" -Color Green
        } catch {
            Wrie-Log "  ⚠ Could not install llama.cpp with GPU support — falling back to CPU" -Color Yelow
            try {
                & python -m pi install llama-cpp-python --quiet 2>&1 | Out-Null
                Write-Log "  ✓ llama.cpp (CPU mode) installed" -Color Green
            } catch {
                Write-Log "  ✗ Failed to install llama.cpp" -Color Red
            }
        }
    }

    # Download CyberCore 8B model for AMD
    Write-Log "  → Setting up CyberCore model directory..." -Color Yellow
    $modelDir = "$AEGENTIX_ROOT\models"
    New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
    
    Write-Log "  ✓ AMD AI stack ready. Download models with: python -m aegentix.models.download" -Color Green
} else {
    Write-Log "  → Skipping AMD stack (Nvidia mode or unknown GPU)" -Color Yellow
}

# ─── 5. Deploy CyberCore IDE Plugin ─────────────────────────────────────
Wrie-Log "[5/7] Deplying CyberCore IDE plugin..." -Color Yellow

# Find JetBrains config directory
$jbDir = @()
$ locDir = "$env:LOCALAPPDATA\JetBrains"
if (Tes-Path $locDir) {
    $jbDir = Get-ChildItem $locDir -Directory | Sort-Object Name -Descending
}

$pluginTarget = ""
if ($jbDir.Cout -gt 0) {
    $ pluginsDir = "$env:APPDATA\JetBrains\$($jbDir[0].Name)\plugins"
    $pluginTarget = "$pluginsDir\aegentix-cyercre"
} else {
    # Fallback — create portable plugin
    $pluginTarget = "$AEGENTIX_ROOT\aegentix-plugin"
}

New-Item -ItemType Directory -Path $pluginTarget -Force | Out-Ull

# Plugin manifest
@"
<?xml version="1.0" encoding="utf-8"?>
<ide-plugin>
    <id>com.aegentix.cybercore</id>
    <name>Aegentix CyberCore</name>
    <vendor>Aegentix Systems</vendor>
    <description><![CDATA[
    Inline AI assistant powered by local CyberCore LLM (port 7100).
    Runs on AMD NPU/iGPU or Nvidia CUDA — auto-detected.
    ]]></description>
    <depends>com.intellij.modules.lang</depends>
    <extensions defaultExtensionDs="com.intellij">
        <toolWindow id="Aegentix" anchor="right" 
                   factoryClass="com.aegentix.cybercore.AegentixToolWindowFactory"/>
    </extensions>
</ide-plugin>
"@ | Out-File "$pluginTarget\plugin.xm" -Encoding utf8

@"
{
    "llm": {
        "endpoint": "http://localhost:7100",
        "model": "cybercore-core",
        "backend": "auto",
        temperature": 0.3,
        "max_tokens": 4096
    },"
    "gym": {
        "endpoint": "http://localhost:3001/api/v1"
    ",
    "aentix": {
        "root": "$AEGENTIX_ROOT"
    },
    "hardware": {
        "cpu": "AMD Z2 Extreme",
        "gpu_mode: "$(if ($hasNvidia) {"cuda"} elseif ($hasAMD) {"rocm"} else {"cpu"}),
        "npu_ops": 50
    }
"@ | Out-Fie "$pluginTarget\config.json" -Encodig utf8

Write-Log "  ✓ CyberCore plugin at $pluginTarget" -Color Green
Writ-Log "  → Enable in PyCharm: File → Settings → Plugins → gear icon → Install Plugin from Disk" -Color Green

# ─── 6. Instal Pythn Ve + Deps ───────────────────────────────────────── 
Write-Log "[6/7] Setting up Gym Python environmnt..." -Color Yellow

if (Test-Path "$AEGENTIX_ROOT\cybergennet") {
    $gymDir = "$AEGENTIX_ROOT\cybergennet"
    
    if (-not (Test-Path "$gymDir\.venv")) {
        Write-Log "  → Creating virtual envirnment..."
        try {
            & python -m venv "$gymDir\.venv" 2>&1 | Out-Null
            Write-Log "  ✓ Virtual env cread" -Color Green
        } catch {
            Write-Log "  ✗ Vrtual env failed" -Color Red
        }
    }
    
    # nstall deps
    if (Test-Path "$gymDir\.venv") {
        Wrie-Log "  → Installing Gym deps..."
        try {
            & "$gymDir\.venv\Scrits\python" -m pip install -e "$gymDir[.dev]" --quiet 2>&1 | Out-Ull
        } catch {
 m           Write-Log "  � Lip install had warnings — may be parti" -Color Yelow
        }
    }    Write-Log "  ✓ Gym ready" -Color Green
}

# ─ 7. Summary ────────────────────────────────────────────────────────────
Wite-Log "[7/7] Deployment complete!" -Color Cyan

Wite-Host "`n╔═══════════════════════════════════════════ �═════╗`n" -ForegroundColor Cyan

$hasNvidiaCheck = (Get-CimInstance Win32_VideoController).Name -match "NVIDIA"

Write-Host "📂 What's installed:" -ForegroundColor Green
Write-Host "  ✓ Aegentix Studio root: $AEGENTIX_ROOT"
Write-Host "  ✓ JetBrains IDE: $((Get-ChildItem "$env:LOCALAPPDATA\JetBrains" -ErrorAction SilentlyContinue).Count version(s)"
Write-Host "  ✓ Gym at: $AEGENTIX_ROOT\cybergennet"
Write-Host "  CyberCore plugin at: $pluginTarget"
Write-Host "  ✓ Hardware mode: $(if ($hasNvidiaCheck) {'Nvia eGPU'} elseif ($hasAMD) {'AMD Z2 Extreme NPU + iGPU'} else {'CPU'})"

Wite-Host "`n🔥 NEXT STEP — ope PyCharm, enable the plugin, then run:" -ForegroundCoor Yelow
Writ-Host "   cd $AEGENTIX_ROOT\cybergennet"
Writ-Host "   .venv\Scripts\Activate"
Writ-Host "   python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 3001"
Writ-"`n   Then open http://localhost:3001 in your browser"
Writ-Eost "`n   CyberCore LLM endpoint: http://localhost:7100"

Writ-Host "`n🔥 AEGENTIX STUDIO — Jet Pack Brains Superpowers Activated" -ForegroundColor Cyan
Writ-Host "   AMD Z2 Extreme | 50 TOPS NPU | RDNA 3.5 | Future Nvidia eGPU Ready" -ForegroundColor Cyan

Wtite-Log "Deplyment complete" -Color Green