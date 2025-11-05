# OVERWATCH v2.1 Installation Script
# Run this script as Administrator

param(
    [switch]$SkipWindowsExporter,
    [switch]$SkipExecutor,
    [switch]$SkipPodman
)

$ErrorActionPreference = "Stop"

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "OVERWATCH v2.1 Installation" -ForegroundColor Cyan
Write-Host "Enterprise-Grade Process Monitoring & Remediation" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    exit 1
}

# Step 1: Install Windows Exporter
if (-not $SkipWindowsExporter) {
    Write-Host "[1/5] Installing Windows Exporter..." -ForegroundColor Yellow
    
    $exporterPath = "$env:ProgramFiles\windows_exporter"
    if (-not (Test-Path $exporterPath)) {
        New-Item -ItemType Directory -Path $exporterPath -Force | Out-Null
    }
    
    $exporterUrl = "https://github.com/prometheus-community/windows_exporter/releases/download/v0.25.1/windows_exporter-0.25.1-amd64.exe"
    $exporterExe = "$exporterPath\windows_exporter.exe"
    
    Write-Host "  Downloading windows_exporter..."
    Invoke-WebRequest -Uri $exporterUrl -OutFile $exporterExe -UseBasicParsing
    
    Write-Host "  Installing as Windows service..."
    sc.exe create windows_exporter `
        binPath= "`"$exporterExe`" --collectors.enabled `"cpu,cs,logical_disk,net,os,process,system`" --collector.process.include=`".+`"" `
        start= auto `
        DisplayName= "Windows Exporter for Prometheus"
    
    sc.exe start windows_exporter
    
    Write-Host "  ✓ Windows Exporter installed and started" -ForegroundColor Green
} else {
    Write-Host "[1/5] Skipping Windows Exporter installation" -ForegroundColor Gray
}

# Step 2: Check Podman
if (-not $SkipPodman) {
    Write-Host "[2/5] Checking Podman installation..." -ForegroundColor Yellow
    
    try {
        $podmanVersion = podman --version
        Write-Host "  ✓ Podman found: $podmanVersion" -ForegroundColor Green
    }
    catch {
        Write-Host "  ERROR: Podman not found!" -ForegroundColor Red
        Write-Host "  Please install Podman Desktop from: https://podman-desktop.io/downloads" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "[2/5] Skipping Podman check" -ForegroundColor Gray
}

# Step 3: Configure OVERWATCH
Write-Host "[3/5] Configuring OVERWATCH..." -ForegroundColor Yellow

$overwatchPath = $PSScriptRoot
Set-Location $overwatchPath

if (-not (Test-Path ".env")) {
    Write-Host "  Creating .env from template..."
    Copy-Item ".env.example" ".env"
    
    Write-Host ""
    Write-Host "  IMPORTANT: Edit .env file and set:" -ForegroundColor Yellow
    Write-Host "    - OLLAMA_API_KEY (required)" -ForegroundColor Yellow
    Write-Host "    - WEBHOOK_TOKEN (recommended)" -ForegroundColor Yellow
    Write-Host "    - EXECUTOR_TOKEN (recommended)" -ForegroundColor Yellow
    Write-Host ""
    
    $continue = Read-Host "Have you configured .env? (yes/no)"
    if ($continue -ne "yes") {
        Write-Host "  Please configure .env and run the script again." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "  ✓ Configuration ready" -ForegroundColor Green

# Step 4: Start Podman services
if (-not $SkipPodman) {
    Write-Host "[4/5] Starting Podman services..." -ForegroundColor Yellow
    
    Write-Host "  Building Docker images..."
    podman-compose build
    
    Write-Host "  Starting containers..."
    podman-compose up -d
    
    Write-Host "  Waiting for services to start..."
    Start-Sleep -Seconds 15
    
    # Verify services
    $services = @("overwatch-prometheus", "overwatch-alertmanager", "overwatch-grafana", "overwatch-ai-layer", "overwatch-ui")
    foreach ($service in $services) {
        $status = podman ps --filter "name=$service" --format "{{.Status}}"
        if ($status -match "Up") {
            Write-Host "  ✓ $service is running" -ForegroundColor Green
        } else {
            Write-Host "  ✗ $service failed to start" -ForegroundColor Red
        }
    }
} else {
    Write-Host "[4/5] Skipping Podman services" -ForegroundColor Gray
}

# Step 5: Install PowerShell Executor
if (-not $SkipExecutor) {
    Write-Host "[5/5] Installing PowerShell Executor..." -ForegroundColor Yellow
    
    # Check for NSSM
    $nssmPath = "C:\nssm\nssm.exe"
    if (-not (Test-Path $nssmPath)) {
        Write-Host "  NSSM not found. Installing..."
        
        $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
        $nssmZip = "$env:TEMP\nssm.zip"
        
        Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing
        Expand-Archive -Path $nssmZip -DestinationPath "$env:TEMP\nssm" -Force
        
        New-Item -ItemType Directory -Path "C:\nssm" -Force | Out-Null
        Copy-Item "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" $nssmPath
        
        Remove-Item $nssmZip -Force
        Remove-Item "$env:TEMP\nssm" -Recurse -Force
    }
    
    # Load .env to get executor token
    $envContent = Get-Content ".env"
    $executorToken = ($envContent | Where-Object { $_ -match "^EXECUTOR_TOKEN=" }) -replace "^EXECUTOR_TOKEN=", ""
    
    if (-not $executorToken) {
        $executorToken = "executor-secret-token-456"
        Write-Host "  WARNING: Using default EXECUTOR_TOKEN" -ForegroundColor Yellow
    }
    
    # Install service
    $svcName = "OverwatchExecutor"
    $scriptPath = Join-Path $overwatchPath "executor\executor.ps1"
    
    # Remove existing service if present
    $existingService = Get-Service -Name $svcName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Host "  Removing existing service..."
        & $nssmPath stop $svcName
        & $nssmPath remove $svcName confirm
    }
    
    Write-Host "  Installing service..."
    & $nssmPath install $svcName "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
        "-ExecutionPolicy Bypass -NoProfile -File `"$scriptPath`""
    
    & $nssmPath set $svcName AppDirectory "$overwatchPath"
    & $nssmPath set $svcName AppEnvironmentExtra "EXECUTOR_TOKEN=$executorToken"
    & $nssmPath set $svcName DisplayName "OVERWATCH Executor"
    & $nssmPath set $svcName Description "OVERWATCH Process Remediation Executor"
    & $nssmPath set $svcName Start SERVICE_AUTO_START
    & $nssmPath set $svcName AppStdout "$overwatchPath\logs\executor-stdout.log"
    & $nssmPath set $svcName AppStderr "$overwatchPath\logs\executor-stderr.log"
    
    # Allow URL reservation
    Write-Host "  Configuring URL reservation..."
    netsh http delete urlacl url=http://+:8080/ 2>$null
    netsh http add urlacl url=http://+:8080/ user=Everyone
    
    # Start service
    & $nssmPath start $svcName
    
    Start-Sleep -Seconds 5
    
    $svcStatus = (Get-Service -Name $svcName).Status
    if ($svcStatus -eq "Running") {
        Write-Host "  ✓ PowerShell Executor service installed and running" -ForegroundColor Green
    } else {
        Write-Host "  ✗ PowerShell Executor service failed to start: $svcStatus" -ForegroundColor Red
    }
} else {
    Write-Host "[5/5] Skipping PowerShell Executor installation" -ForegroundColor Gray
}

# Final summary
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access Points:" -ForegroundColor Yellow
Write-Host "  • Streamlit UI:  http://localhost:8501" -ForegroundColor White
Write-Host "  • Prometheus:    http://localhost:9090" -ForegroundColor White
Write-Host "  • Alertmanager:  http://localhost:9093" -ForegroundColor White
Write-Host "  • Grafana:       http://localhost:3000 (admin/admin)" -ForegroundColor White
Write-Host "  • AI Layer:      http://localhost:5000/health" -ForegroundColor White
Write-Host "  • Executor:      http://localhost:8080/health" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Verify all services are running" -ForegroundColor White
Write-Host "  2. Check Streamlit UI for pending alerts" -ForegroundColor White
Write-Host "  3. Review Grafana dashboards" -ForegroundColor White
Write-Host "  4. Test with a sample process (see docs)" -ForegroundColor White
Write-Host ""
Write-Host "Documentation: docs/INSTALLATION.md" -ForegroundColor White
Write-Host "Logs: .\logs\" -ForegroundColor White
Write-Host ""
