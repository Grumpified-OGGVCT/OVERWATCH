# 🧠 OVERWATCH v2.1 - Enterprise-Grade Process Monitoring & Remediation

**Automatically detect, intelligently triage, and safely remediate orphaned, pseudo-zombie, and resource-leeching processes on Windows 11 Home with full audit trail, human approval, and LLM-based decisioning.**

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  WINDOWS 11 HOST                            │
│  ┌──────────────────┐                                       │
│  │ windows_exporter │ ← Exposes process metrics             │
│  └────────┬─────────┘                                       │
│           │                                                  │
│  ┌────────▼─────────┐                                       │
│  │ PowerShell       │ ← Executes kill commands              │
│  │ Executor Service │                                       │
│  └──────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
           │                          ▲
           │ Metrics                  │ HTTP API
           ▼                          │
┌─────────────────────────────────────────────────────────────┐
│              PODMAN CONTAINERS                              │
│                                                             │
│  ┌──────────────┐     ┌────────────────┐                  │
│  │  Prometheus  │────▶│  Alertmanager  │                  │
│  │              │     │                │                  │
│  │ - Scrapes    │     │ - Routes alerts│                  │
│  │ - Evaluates  │     │ - Fires webhook│                  │
│  └──────────────┘     └────────┬───────┘                  │
│                                 │                           │
│                                 ▼                           │
│                      ┌──────────────────┐                  │
│                      │   AI Layer       │                  │
│                      │   (Flask)        │                  │
│                      │                  │                  │
│                      │ - Ollama LLM     │                  │
│                      │ - Safety checks  │                  │
│                      │ - SQLite storage │                  │
│                      └────────┬─────────┘                  │
│                               │                             │
│                               ▼                             │
│                      ┌──────────────────┐                  │
│                      │  Streamlit UI    │                  │
│                      │                  │                  │
│                      │ - Human approval │                  │
│                      │ - History view   │                  │
│                      │ - Config mgmt    │                  │
│                      └──────────────────┘                  │
│                                                             │
│  ┌──────────────┐                                          │
│  │   Grafana    │ ← Dashboards & visualization            │
│  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Features

### ✅ **Enterprise-Grade Architecture**
- **Prometheus**: Metrics collection and alert evaluation
- **Alertmanager**: Intelligent alert routing and grouping
- **Flask AI Layer**: Structured LLM reasoning with safety checks
- **Streamlit Dashboard**: Beautiful, interactive human-in-the-loop UI
- **SQLite Database**: Complete audit trail and history
- **PowerShell Executor**: Safe, validated process termination

### ✅ **AI-Powered Decision Making**
- **Structured Prompts**: Context-aware analysis with full process metadata
- **Safety-First**: Pre-LLM safety checks prevent dangerous actions
- **Confidence Scoring**: LLM returns confidence levels for each decision
- **Fallback Heuristics**: Conservative decisions when LLM unavailable
- **Tool Calling**: Enforced JSON responses from Ollama

### ✅ **Human-in-the-Loop Control**
- **Interactive Dashboard**: Review all AI recommendations
- **Dry-Run Mode**: Test commands before executing
- **Manual Override**: Skip, reject, or manually review alerts
- **Full Context**: See complete process details and AI reasoning
- **Approve/Reject**: Simple, clear action buttons

### ✅ **Complete Audit Trail**
- **SQLite Database**: All alerts, decisions, and actions logged
- **Windows Event Log**: Critical actions logged to system
- **Queryable History**: Filter and search past events
- **Compliance Ready**: Full chain of custody for all actions

### ✅ **Security & Safety**
- **Bearer Token Auth**: Secure API endpoints
- **Protected Processes**: System-critical processes never terminated
- **Command Validation**: Only whitelisted commands allowed
- **PID Range Protection**: System PIDs (<1000) blocked
- **Graceful Termination**: Try close before force kill

---

## 🚀 Quick Start

### Prerequisites

1. **Windows 11 Home** (or higher)
2. **Podman Desktop** installed
3. **Windows Exporter** running on port 9182
4. **Ollama Proxy** running on localhost:8081
5. **PowerShell** 5.1 or higher

### Installation Steps

1. **Clone Repository**
```bash
git clone https://github.com/Grumpified-OGGVCT/OVERWATCH.git
cd OVERWATCH
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Start Podman Services**
```bash
podman-compose up -d
```

4. **Start PowerShell Executor**
```powershell
$env:EXECUTOR_TOKEN = "your-secret-token"
.\executor\executor.ps1 -Port 8080
```

5. **Access Interfaces**
- **Streamlit UI**: http://localhost:8501
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **AI Layer**: http://localhost:5000/health

---

## 📖 Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Architecture Deep Dive](docs/ARCHITECTURE.md)
- [Security Best Practices](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

---

## 🛡️ Security

All actions are logged, validated, and require human approval. See [SECURITY.md](docs/SECURITY.md) for details.

---

## ⚠️ Disclaimer

This tool terminates processes. Always review AI recommendations carefully and test in a safe environment first.

---

## 📜 License

See LICENSE file for details.
