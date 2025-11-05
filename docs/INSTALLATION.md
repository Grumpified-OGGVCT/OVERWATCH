# OVERWATCH Installation Guide

## Prerequisites

### Required Software

1. **Windows 11 Home or higher**
2. **Podman Desktop** - https://podman-desktop.io/downloads
3. **Windows Exporter** - For Prometheus metrics
4. **Ollama Proxy** - Running on localhost:8081 with API key
5. **PowerShell 5.1+** - Included with Windows

### Optional (Recommended)

- **NSSM** - To run PowerShell Executor as Windows service
- **Git** - For version control
- **Visual Studio Code** - For editing configuration

---

## Step 1: Install Windows Exporter

1. Download from: https://github.com/prometheus-community/windows_exporter/releases
2. Run installer or use Chocolatey:
```powershell
choco install prometheus-windows-exporter.install
```

3. Verify it's running:
```powershell
Invoke-WebRequest http://localhost:9182/metrics
```

---

## Step 2: Set Up Ollama Proxy

1. Ensure Ollama proxy is running on `localhost:8081`
2. Test connection:
```powershell
curl http://localhost:8081/api/tags
```

3. Note your API key for configuration

---

## Step 3: Clone and Configure OVERWATCH

1. Clone repository:
```bash
git clone https://github.com/Grumpified-OGGVCT/OVERWATCH.git
cd OVERWATCH
```

2. Copy environment template:
```bash
cp .env.example .env
```

3. Edit `.env` with your settings:
```bash
# Required
OLLAMA_API_KEY=your-actual-api-key-here
OLLAMA_PROXY_URL=http://localhost:8081

# Optional (defaults provided)
WEBHOOK_TOKEN=overwatch-secret-token-123
EXECUTOR_TOKEN=executor-secret-token-456
GRAFANA_PASSWORD=admin
```

---

## Step 4: Initialize Database

```bash
cd database
python -c "from db_manager import DatabaseManager; db = DatabaseManager(); print('Database initialized')"
```

This creates `database/overwatch.db` with all tables.

---

## Step 5: Start Podman Services

1. Make sure Podman Desktop is running

2. Start all services:
```bash
podman-compose up -d
```

3. Verify services are running:
```bash
podman ps
```

You should see:
- overwatch-prometheus
- overwatch-alertmanager
- overwatch-grafana
- overwatch-ai-layer
- overwatch-ui

4. Check logs if needed:
```bash
podman-compose logs -f
```

---

## Step 6: Configure PowerShell Executor

### Option A: Run Manually (for testing)

1. Open PowerShell as Administrator

2. Set environment variable:
```powershell
$env:EXECUTOR_TOKEN = "executor-secret-token-456"
```

3. Allow URL reservation (one-time):
```powershell
netsh http add urlacl url=http://+:8080/ user=Everyone
```

4. Start executor:
```powershell
cd executor
.\executor.ps1 -Port 8080
```

### Option B: Install as Windows Service (recommended)

1. Download NSSM: https://nssm.cc/download

2. Install service:
```powershell
nssm install OverwatchExecutor "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
nssm set OverwatchExecutor AppParameters "-ExecutionPolicy Bypass -File C:\OVERWATCH\executor\executor.ps1"
nssm set OverwatchExecutor AppDirectory "C:\OVERWATCH"
nssm set OverwatchExecutor AppEnvironmentExtra EXECUTOR_TOKEN=executor-secret-token-456
nssm set OverwatchExecutor DisplayName "OVERWATCH Executor"
nssm set OverwatchExecutor Description "OVERWATCH Process Remediation Executor"
nssm set OverwatchExecutor Start SERVICE_AUTO_START
```

3. Start service:
```powershell
nssm start OverwatchExecutor
```

4. Verify:
```powershell
nssm status OverwatchExecutor
Invoke-WebRequest http://localhost:8080/health
```

---

## Step 7: Access Dashboards

### Streamlit UI (Main Interface)
- URL: http://localhost:8501
- Use this for:
  - Reviewing pending alerts
  - Approving/rejecting AI recommendations
  - Viewing alert history
  - Managing configuration

### Prometheus
- URL: http://localhost:9090
- Use this for:
  - Viewing metrics
  - Testing alert rules
  - Debugging queries

### Alertmanager
- URL: http://localhost:9093
- Use this for:
  - Viewing active alerts
  - Testing webhooks
  - Alert routing configuration

### Grafana
- URL: http://localhost:3000
- Username: admin
- Password: (from .env, default: admin)
- Use this for:
  - Process metrics dashboards
  - System health monitoring
  - Custom visualizations

---

## Step 8: Verify End-to-End

1. **Check Windows Exporter**:
```powershell
curl http://localhost:9182/metrics | Select-String "windows_process"
```

2. **Check Prometheus is scraping**:
- Go to http://localhost:9090/targets
- Verify `windows_exporter` target is UP

3. **Check AI Layer health**:
```powershell
curl http://localhost:5000/health
```

4. **Check Executor health**:
```powershell
curl http://localhost:8080/health
```

5. **Check Streamlit UI**:
- Open http://localhost:8501
- Should show "No pending alerts" if system is healthy

---

## Step 9: Test with Sample Alert (Optional)

1. Create a CPU-intensive process:
```powershell
# Start PowerShell process that uses CPU
while($true) { Get-Process | Out-Null }
```

2. Wait 2-5 minutes for alert to fire

3. Check Streamlit UI for new alert

4. Review AI recommendation

5. Test dry-run mode

6. Stop the test process manually

---

## Troubleshooting Installation

### Podman Issues
```bash
# Restart Podman machine
podman machine stop
podman machine start

# Rebuild containers
podman-compose down
podman-compose build
podman-compose up -d
```

### Database Issues
```bash
# Reset database
rm database/overwatch.db
python database/db_manager.py
```

### Executor Issues
```powershell
# Check logs
Get-Content C:\OVERWATCH\logs\executor.log -Tail 50 -Wait

# Verify URL reservation
netsh http show urlacl
```

### Network Issues
```powershell
# Verify ports are not in use
netstat -ano | findstr "5000 8080 8501 9090 9093"

# Test connectivity
Test-NetConnection -ComputerName localhost -Port 8081
```

---

## Next Steps

1. Review [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
2. Read [SECURITY.md](SECURITY.md) for security best practices
3. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
4. Customize alert rules in `monitoring/prometheus/rules/`
5. Adjust thresholds in `.env`

---

## Uninstallation

```bash
# Stop all services
podman-compose down

# Remove volumes (WARNING: deletes all data)
podman volume rm overwatch-prometheus-data
podman volume rm overwatch-alertmanager-data
podman volume rm overwatch-grafana-data

# Uninstall Windows service
nssm stop OverwatchExecutor
nssm remove OverwatchExecutor confirm

# Remove URL reservation
netsh http delete urlacl url=http://+:8080/
```

---

## Support

If you encounter issues:
1. Check logs in `podman-compose logs`
2. Check executor log in `C:\OVERWATCH\logs\executor.log`
3. Review database: `sqlite3 database/overwatch.db`
4. Open GitHub issue with logs
