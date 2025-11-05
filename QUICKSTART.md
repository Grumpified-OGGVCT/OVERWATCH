# OVERWATCH Quick Start Guide

## Installation & Setup (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy the example configuration
cp .env.example .env

# Edit .env with your settings
# REQUIRED: Set your Ollama API key
nano .env
```

**Important:** You must configure:
- `OLLAMA_API_KEY` - Your Ollama API key (required)
- `OLLAMA_PROXY_URL` - Should be `http://localhost:8081` (default)

### 3. Verify Ollama Proxy is Running

Before running OVERWATCH, ensure your Ollama proxy server is running:
```bash
# Check if Ollama proxy is accessible
curl http://localhost:8081/api/tags
```

If you get a connection error, start your Ollama proxy server first.

## Basic Usage

### Run a Single Scan
```bash
python overwatch.py --mode single
```

This will:
1. Scan all running processes
2. Detect orphaned, zombie, and resource-leeching processes
3. Analyze each with AI (via Ollama)
4. Ask for your approval before taking any action
5. Safely terminate approved processes
6. Log everything to audit_logs/

### Run Continuous Monitoring
```bash
# Scan every 60 seconds (default)
python overwatch.py --mode continuous

# Custom interval (e.g., every 2 minutes)
python overwatch.py --mode continuous --interval 120
```

Press `Ctrl+C` to stop continuous monitoring.

## Understanding the Output

When problematic processes are found, you'll see:

```
================================================================================
OVERWATCH - Process Remediation Review
================================================================================

Found 3 processes requiring review.

--------------------------------------------------------------------------------
Process 1/3
--------------------------------------------------------------------------------

📋 Process Information:
  • PID: 1234
  • Name: example.exe
  • Category: RESOURCE_LEECHING
  • CPU Usage: 95.2%
  • Memory Usage: 78.4%
  • Status: running
  • Executable: C:\path\to\example.exe

🤖 AI Analysis:
  • Recommendation: ❌ TERMINATE
  • Risk Level: 🟡 MEDIUM
  • Reasoning: Process consuming excessive CPU resources...

  Options:
    [a] Approve - Execute TERMINATE
    [r] Reject - Keep the process running
    [s] Skip - Review again later
    [q] Quit - Stop review process

  Your choice (a/r/s/q):
```

### Making Decisions

- **[a] Approve**: Execute the AI's recommendation
- **[r] Reject**: Keep the process running, won't ask again in this session
- **[s] Skip**: Don't decide now, will ask again in next scan
- **[q] Quit**: Stop reviewing remaining processes

## Safety Features

### Protected Processes
These critical Windows processes are **never** terminated:
- System, svchost.exe, csrss.exe, smss.exe
- wininit.exe, services.exe, lsass.exe
- winlogon.exe, explorer.exe, dwm.exe
- RuntimeBroker.exe

### Audit Trail
Every action is logged to `audit_logs/audit_YYYY-MM-DD.jsonl`:
- Process scans
- AI analysis results
- Your approval/rejection decisions
- Termination results

### Graceful Termination
OVERWATCH tries to terminate processes gracefully first, falling back to force kill only if needed.

## Advanced Usage

### Adjust Detection Sensitivity
Edit `.env` to change thresholds:
```bash
CPU_THRESHOLD=90.0       # Only flag processes using >90% CPU
MEMORY_THRESHOLD=85.0    # Only flag processes using >85% memory
```

### Enable Debug Logging
```bash
python overwatch.py --mode single --log-level DEBUG
```

### Auto-Approve Mode (⚠️ Use with Extreme Caution)
```bash
# This will automatically execute ALL AI recommendations
# without asking for approval. Only use in test environments!
python overwatch.py --mode single --auto-approve
```

## Troubleshooting

### "Configuration errors found: OLLAMA_API_KEY is not set"
- Edit your `.env` file and add your Ollama API key
- Copy from `.env.example` if you haven't created `.env` yet

### "Error calling Ollama API: Connection refused"
- Ensure Ollama proxy server is running on localhost:8081
- Check firewall settings
- The system will fall back to rule-based heuristics if Ollama is unavailable

### "Access denied to terminate process"
- Some processes require administrator privileges
- Run OVERWATCH as administrator
- Or, run from an elevated command prompt

### No Processes Detected
- This is good! It means your system is healthy
- Try lowering thresholds in `.env` if you want to test
- The system only flags processes exceeding configured thresholds

## Running Examples

To see how OVERWATCH works programmatically:
```bash
python examples.py
```

This demonstrates:
- Process detection
- LLM analysis
- Audit logging

## Need Help?

- Check the full documentation: `README.md`
- Review audit logs: `audit_logs/audit_*.jsonl`
- Check application logs: `overwatch.log`
- Open an issue on GitHub

## Best Practices

1. **Start with a single scan** before using continuous mode
2. **Review audit logs regularly** to understand system behavior
3. **Never use auto-approve in production** - always review AI decisions
4. **Test in a safe environment first** before running on critical systems
5. **Keep thresholds conservative** to avoid false positives
6. **Run with appropriate privileges** - some processes require admin access

---

**⚠️ Important**: Always review AI recommendations carefully. OVERWATCH is a powerful tool that terminates processes. While it has safety mechanisms, you are ultimately responsible for approving termination decisions.
