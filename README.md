# OVERWATCH
**Orphan Process Terminator with AI Reasoning & Human-in-the-Loop Control**

OVERWATCH is an intelligent process monitoring and remediation system for Windows 11 that automatically detects, triages, and safely remediates orphaned, zombie, and resource-leeching processes using LLM-based decision-making with human oversight.

## Features

✨ **Intelligent Detection**
- Identifies orphaned processes (processes whose parent has terminated)
- Detects zombie/defunct processes
- Finds resource-leeching processes (excessive CPU/memory usage)
- Protects critical system processes from termination

🤖 **AI-Powered Decision Making**
- Uses Ollama LLM via secure proxy server (localhost:8081)
- Analyzes process behavior and context
- Provides risk assessment and remediation recommendations
- Includes fallback heuristics when LLM is unavailable

👤 **Human-in-the-Loop Control**
- Interactive approval system for all remediation actions
- Detailed process information and AI reasoning displayed
- Option to approve, reject, or defer decisions
- Optional auto-approve mode for automated environments

📊 **Full Audit Trail**
- Comprehensive JSON-based audit logs
- Tracks all scans, analyses, decisions, and remediations
- Daily log rotation
- Complete historical record of all actions

🛡️ **Safety First**
- Protected process list prevents critical system process termination
- Graceful termination with fallback to force kill
- Error handling and rollback capabilities
- Conservative decision-making when uncertain

## Installation

### Prerequisites

- Windows 11 Home (or higher)
- Python 3.8 or higher
- Ollama proxy server running on localhost:8081
- API key for Ollama service

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Grumpified-OGGVCT/OVERWATCH.git
cd OVERWATCH
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
```

4. Edit `.env` and add your configuration:
```bash
OLLAMA_PROXY_URL=http://localhost:8081
OLLAMA_API_KEY=your-actual-api-key
CPU_THRESHOLD=80.0
MEMORY_THRESHOLD=80.0
SCAN_INTERVAL_SECONDS=60
```

## Usage

### Single Scan Mode

Run a single scan with human approval:
```bash
python overwatch.py --mode single
```

### Continuous Monitoring Mode

Run continuous monitoring (scans every 60 seconds by default):
```bash
python overwatch.py --mode continuous
```

Customize scan interval:
```bash
python overwatch.py --mode continuous --interval 120
```

### Auto-Approve Mode (Use with Caution!)

⚠️ **WARNING**: This mode automatically executes all AI recommendations without human review. Use only in controlled environments.

```bash
python overwatch.py --mode single --auto-approve
```

### Logging Options

Adjust logging verbosity:
```bash
python overwatch.py --mode single --log-level DEBUG
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     OVERWATCH System                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                                          │
│  │   Scanner    │  Detects problematic processes           │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐                                          │
│  │ LLM Engine   │  Analyzes via Ollama (localhost:8081)    │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐                                          │
│  │   Human      │  Interactive approval interface          │
│  │   Approval   │                                          │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐                                          │
│  │ Remediator   │  Safe process termination                │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐                                          │
│  │ Audit Logger │  Full audit trail (JSON logs)            │
│  └──────────────┘                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_PROXY_URL` | URL of Ollama proxy server | `http://localhost:8081` |
| `OLLAMA_API_KEY` | API key for Ollama authentication | *Required* |
| `CPU_THRESHOLD` | CPU usage threshold (%) | `80.0` |
| `MEMORY_THRESHOLD` | Memory usage threshold (%) | `80.0` |
| `SCAN_INTERVAL_SECONDS` | Interval between scans in continuous mode | `60` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `AUDIT_LOG_PATH` | Directory for audit logs | `./audit_logs` |

### Protected Processes

The following critical Windows processes are protected from termination:
- System
- svchost.exe
- csrss.exe
- smss.exe
- wininit.exe
- services.exe
- lsass.exe
- winlogon.exe
- explorer.exe
- dwm.exe
- RuntimeBroker.exe

You can modify this list in `config.py`.

## Audit Logs

Audit logs are stored in JSON Lines format (one JSON object per line) in the `audit_logs` directory. Each day's activities are logged to a separate file.

### Event Types

- **SCAN**: Process detection scan
- **ANALYSIS**: LLM analysis results
- **HUMAN_DECISION**: Human approval/rejection
- **REMEDIATION**: Process termination action
- **ERROR**: Error events

### Example Audit Log Entry

```json
{
  "event_id": "EVT_20231105_143022_123456",
  "event_type": "REMEDIATION",
  "timestamp": "2023-11-05T14:30:22.123456",
  "pid": 1234,
  "process_name": "example.exe",
  "action": "TERMINATE",
  "success": true,
  "decision_details": {...}
}
```

## Security Considerations

1. **API Key Security**: Store your Ollama API key securely in the `.env` file, which is git-ignored
2. **Proxy Server**: Ensure your Ollama proxy server (localhost:8081) is properly secured
3. **Protected Processes**: Review and customize the protected process list for your environment
4. **Auto-Approve Mode**: Use with extreme caution - only in isolated test environments
5. **Administrator Privileges**: May require elevated privileges to terminate certain processes

## Troubleshooting

### LLM Connection Issues

If the LLM engine cannot connect to Ollama:
- Verify the proxy server is running on localhost:8081
- Check that your API key is correctly configured
- Review logs for connection errors
- System will fall back to rule-based heuristics

### Access Denied Errors

Some processes may be protected by Windows:
- Run OVERWATCH with administrator privileges
- Check Windows security settings
- Review the process ownership and permissions

### High False Positive Rate

Adjust detection thresholds in `.env`:
```bash
CPU_THRESHOLD=90.0        # Increase to reduce false positives
MEMORY_THRESHOLD=90.0     # Increase to reduce false positives
```

## Development

### Project Structure

```
OVERWATCH/
├── overwatch.py           # Main entry point and orchestrator
├── config.py              # Configuration management
├── process_detector.py    # Process detection logic
├── llm_decision.py        # LLM integration and decision engine
├── human_approval.py      # Human-in-the-loop interface
├── remediator.py          # Process remediation
├── audit_logger.py        # Audit trail logging
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment configuration
└── audit_logs/           # Audit log storage (created at runtime)
```

### Adding Custom Detection Rules

Extend `ProcessDetector` class in `process_detector.py`:

```python
def is_custom_problematic(self, proc_info: ProcessInfo) -> bool:
    """Add your custom detection logic."""
    # Your logic here
    return condition
```

## License

See LICENSE file for details.

## Contributing

Contributions are welcome! Please submit pull requests or open issues on GitHub.

## Support

For questions or issues:
- Open an issue on GitHub
- Check existing documentation
- Review audit logs for debugging

---

**⚠️ DISCLAIMER**: This tool terminates processes on your system. Always review decisions carefully before approval. The authors are not responsible for any system instability or data loss resulting from use of this software.
