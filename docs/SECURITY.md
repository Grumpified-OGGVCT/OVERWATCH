# OVERWATCH Security Hardening Guide

## Overview

This guide covers security best practices for deploying and operating OVERWATCH in production environments.

---

## 🔐 Core Security Principles

1. **Defense in Depth**: Multiple layers of security controls
2. **Least Privilege**: Minimal permissions for all components
3. **Secure by Default**: Strong security settings out of the box
4. **Audit Everything**: Complete logging of all actions
5. **Principle of Least Astonishment**: Predictable, safe behavior

---

## 🛡️ Component-Level Security

### 1. PowerShell Executor

**Threat Model:**
- Unauthorized process termination
- Privilege escalation
- Command injection

**Mitigations:**

#### A. Bearer Token Authentication
```powershell
# Generate a strong token
$token = [System.Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
$env:EXECUTOR_TOKEN = $token
```

Store in Windows Credential Manager:
```powershell
cmdkey /generic:OVERWATCH_EXECUTOR_TOKEN /user:overwatch /pass:$token
```

#### B. Command Validation
The executor **only** accepts:
```powershell
Stop-Process -Id <PID> -Force
```

Any other command is **rejected**.

#### C. Process Protection List
Maintain a strict deny-list in `database/process_rules`:
```sql
INSERT INTO process_rules (rule_type, pattern, pattern_type, notes)
VALUES ('deny', 'svchost.exe', 'name', 'Critical Windows service');
```

#### D. Run as Least-Privilege Service Account
```powershell
# Create dedicated service account
$password = ConvertTo-SecureString "ComplexPassword123!" -AsPlainText -Force
New-LocalUser -Name "OverwatchExec" -Password $password -Description "OVERWATCH Executor Service"

# Grant only necessary privileges
secedit /export /cfg C:\secconfig.cfg
# Edit secconfig.cfg to add SeDebugPrivilege to OverwatchExec
secedit /configure /db secedit.sdb /cfg C:\secconfig.cfg

# Configure service to run as this user
sc.exe config OverwatchExecutor obj= ".\OverwatchExec" password= "ComplexPassword123!"
```

---

### 2. AI Layer (Flask Webhook)

**Threat Model:**
- Unauthorized alert injection
- LLM prompt injection
- Data exfiltration

**Mitigations:**

#### A. TLS/HTTPS
Generate self-signed certificate:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

Update Flask to use HTTPS:
```python
app.run(host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'))
```

#### B. Webhook Token Validation
All incoming webhooks must include:
```http
Authorization: Bearer <WEBHOOK_TOKEN>
```

Reject any request without valid token.

#### C. Input Validation
Validate all alert payloads against schema:
```python
from jsonschema import validate

alert_schema = {
    "type": "object",
    "required": ["alerts"],
    "properties": {
        "alerts": {
            "type": "array",
            "items": {"type": "object"}
        }
    }
}

validate(instance=payload, schema=alert_schema)
```

#### D. Rate Limiting
Implement rate limiting to prevent DoS:
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.headers.get('Authorization'))

@app.route('/webhook/alert', methods=['POST'])
@limiter.limit("100 per minute")
def receive_alert():
    # ...
```

---

### 3. Ollama LLM Proxy

**Threat Model:**
- API key theft
- Prompt injection
- Model manipulation

**Mitigations:**

#### A. Secure API Key Storage
**Never** commit API keys to Git. Use:

**Option 1: Windows Credential Manager**
```powershell
cmdkey /generic:OLLAMA_API_KEY /user:overwatch /pass:"your-api-key"
```

Retrieve in code:
```python
import keyring
api_key = keyring.get_password("OLLAMA_API_KEY", "overwatch")
```

**Option 2: HashiCorp Vault**
```bash
vault kv put secret/overwatch ollama_api_key="your-api-key"
```

Retrieve:
```python
import hvac
client = hvac.Client(url='http://localhost:8200', token=os.getenv('VAULT_TOKEN'))
secret = client.secrets.kv.v2.read_secret_version(path='overwatch')
api_key = secret['data']['data']['ollama_api_key']
```

#### B. Network Isolation
Run Ollama proxy on `localhost` only. Do **not** expose to public internet.

#### C. Response Validation
Always validate LLM responses against JSON schema:
```python
import jsonschema

schema = json.load(open('ai_layer/prompts/schema.json'))
jsonschema.validate(instance=llm_response, schema=schema)
```

Reject any response that doesn't conform.

---

### 4. Streamlit UI

**Threat Model:**
- Unauthorized access to dashboard
- CSRF attacks
- Session hijacking

**Mitigations:**

#### A. Authentication
Enable OAuth2 with Microsoft Entra ID:
```python
# In streamlit_dashboard.py
import streamlit_authenticator as stauth

authenticator = stauth.Authenticate(
    credentials,
    'overwatch_cookie',
    'overwatch_key',
    cookie_expiry_days=1
)

name, authentication_status, username = authenticator.login('Login', 'main')

if not authentication_status:
    st.error('Please log in')
    st.stop()
```

#### B. HTTPS Only
Run Streamlit behind a reverse proxy (Traefik/Nginx) with TLS:
```yaml
# docker-compose.yml
services:
  traefik:
    image: traefik:latest
    ports:
      - "443:443"
    volumes:
      - ./certs:/certs
    command:
      - "--entrypoints.websecure.address=:443"
      - "--providers.docker=true"
```

#### C. RBAC
Implement role-based access control:
```python
ROLES = {
    'admin': ['view', 'approve', 'configure'],
    'operator': ['view', 'approve'],
    'viewer': ['view']
}

def check_permission(user, action):
    return action in ROLES.get(user.role, [])
```

---

### 5. Database (SQLite)

**Threat Model:**
- SQL injection
- Data corruption
- Unauthorized access

**Mitigations:**

#### A. Parameterized Queries
**Always** use parameterized queries:
```python
# Good
cursor.execute("SELECT * FROM alerts WHERE pid = ?", (pid,))

# Bad - NEVER DO THIS
cursor.execute(f"SELECT * FROM alerts WHERE pid = {pid}")
```

#### B. File Permissions
Restrict database file access:
```bash
chmod 600 database/overwatch.db
chown overwatch:overwatch database/overwatch.db
```

#### C. Backups with Encryption
Encrypt backups:
```bash
sqlite3 database/overwatch.db ".backup backup.db"
openssl enc -aes-256-cbc -salt -in backup.db -out backup.db.enc -k "your-password"
rm backup.db
```

---

## 🔒 Network Security

### 1. Firewall Rules

Block all unnecessary ports:
```powershell
# Allow only necessary ports
New-NetFirewallRule -DisplayName "OVERWATCH Prometheus" -Direction Inbound -Protocol TCP -LocalPort 9090 -Action Allow
New-NetFirewallRule -DisplayName "OVERWATCH Streamlit" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow
New-NetFirewallRule -DisplayName "OVERWATCH Executor" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -RemoteAddress LocalSubnet

# Block all other inbound
New-NetFirewallRule -DisplayName "OVERWATCH Block" -Direction Inbound -Action Block
```

### 2. Network Segmentation

Use Docker networks to isolate components:
```yaml
networks:
  frontend:
    internal: false  # Exposed to host
  backend:
    internal: true   # Isolated
```

### 3. TLS Everywhere

Enable TLS for all HTTP endpoints:
- Prometheus: `--web.config.file=/etc/prometheus/web-config.yml`
- Alertmanager: `--web.config.file=/etc/alertmanager/web-config.yml`
- Flask: `app.run(ssl_context=('cert.pem', 'key.pem'))`
- Streamlit: Behind Traefik with TLS

---

## 📜 Audit & Compliance

### 1. Comprehensive Logging

All actions are logged to:
1. **SQLite Database** - Queryable audit trail
2. **Windows Event Log** - System-level audit
3. **File Logs** - executor.log, flask.log

### 2. Log Retention

Configure log retention:
```sql
-- Delete logs older than 90 days
DELETE FROM audit_log WHERE timestamp < datetime('now', '-90 days');
```

### 3. SIEM Integration

Ship logs to SIEM (ELK/Splunk):
```bash
# Install Filebeat
# Configure to ship logs to Elasticsearch
filebeat.inputs:
  - type: log
    paths:
      - /app/logs/*.log
    fields:
      service: overwatch

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
```

---

## 🧪 Security Testing

### 1. Penetration Testing

Test attack scenarios:
- Unauthorized API calls
- Command injection attempts
- Privilege escalation
- Data exfiltration

### 2. Vulnerability Scanning

Scan Docker images:
```bash
trivy image overwatch-ai-layer
trivy image overwatch-ui
```

### 3. Dependency Scanning

Check for vulnerable dependencies:
```bash
pip install safety
safety check -r requirements.txt
```

---

## 🚨 Incident Response

### 1. Detection

Monitor for:
- Unexpected process terminations
- Failed authentication attempts
- Unusual LLM API usage
- Database corruption

### 2. Response Playbook

**If unauthorized access detected:**
1. Immediately stop all services
2. Rotate all tokens and API keys
3. Review audit logs
4. Investigate root cause
5. Patch vulnerability
6. Restart services with new credentials

### 3. Backup & Recovery

Maintain hourly backups:
```powershell
# Scheduled task to backup database
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-File C:\OVERWATCH\scripts\backup.ps1'
$trigger = New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "OVERWATCH Backup" -Action $action -Trigger $trigger
```

---

## ✅ Security Checklist

- [ ] All tokens are strong (32+ random characters)
- [ ] Tokens stored in credential manager (not .env)
- [ ] TLS enabled on all HTTP endpoints
- [ ] Firewall rules configured
- [ ] Executor running as least-privilege account
- [ ] Database file permissions restricted
- [ ] Audit logging enabled
- [ ] Log retention policy configured
- [ ] Backup schedule configured
- [ ] Vulnerability scanning enabled
- [ ] Incident response plan documented
- [ ] Team trained on security procedures

---

## 📚 References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Microsoft Security Best Practices](https://docs.microsoft.com/en-us/security/)

---

**⚠️ Remember: Security is a process, not a product. Regularly review and update these controls.**
