-- OVERWATCH SQLite Database Schema
-- Stores alerts, decisions, and audit trail

-- Alerts table: stores all Prometheus alerts and their metadata
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    alert_name TEXT NOT NULL,
    severity TEXT,
    pid INTEGER,
    process_name TEXT,
    parent_pid INTEGER,
    cmdline TEXT,
    cpu_percent REAL,
    memory_percent REAL,
    start_time DATETIME,
    owner TEXT,
    alert_payload JSON,
    status TEXT DEFAULT 'pending', -- pending, analyzing, approved, rejected, executed
    INDEX idx_timestamp (timestamp),
    INDEX idx_pid (pid),
    INDEX idx_status (status)
);

-- Recommendations table: stores LLM analysis and recommendations
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    llm_model TEXT,
    action TEXT NOT NULL, -- 'kill', 'manual', 'safe_check'
    confidence REAL,
    reasoning TEXT,
    command TEXT,
    prompt_version TEXT,
    full_response JSON,
    fallback BOOLEAN DEFAULT 0,
    FOREIGN KEY (alert_id) REFERENCES alerts(id),
    INDEX idx_alert_id (alert_id)
);

-- Actions table: stores all executed actions
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL,
    recommendation_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    action_type TEXT NOT NULL, -- 'kill', 'skip', 'manual_review'
    pid INTEGER,
    command TEXT,
    executed BOOLEAN DEFAULT 0,
    dry_run BOOLEAN DEFAULT 0,
    success BOOLEAN,
    error_message TEXT,
    executed_by TEXT, -- username or 'system'
    FOREIGN KEY (alert_id) REFERENCES alerts(id),
    FOREIGN KEY (recommendation_id) REFERENCES recommendations(id),
    INDEX idx_alert_id (alert_id),
    INDEX idx_timestamp (timestamp)
);

-- Feedback table: stores post-action feedback for ML improvement
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    was_correct BOOLEAN,
    feedback_text TEXT,
    llm_analysis JSON,
    FOREIGN KEY (action_id) REFERENCES actions(id),
    INDEX idx_action_id (action_id)
);

-- Configuration table: stores dynamic configuration values
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Allowed/Denied processes table
CREATE TABLE IF NOT EXISTS process_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL, -- 'allow' or 'deny'
    pattern TEXT NOT NULL,
    pattern_type TEXT NOT NULL, -- 'name', 'cmdline', 'pid_range'
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    notes TEXT,
    INDEX idx_rule_type (rule_type),
    INDEX idx_enabled (enabled)
);

-- Audit log table: comprehensive audit trail
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL, -- 'scan', 'analysis', 'approval', 'execution', 'error'
    event_id TEXT,
    user TEXT,
    details JSON,
    INDEX idx_timestamp (timestamp),
    INDEX idx_event_type (event_type)
);

-- Insert default protected processes
INSERT OR IGNORE INTO process_rules (rule_type, pattern, pattern_type, created_by, notes) VALUES
    ('deny', 'System', 'name', 'system', 'Windows System process'),
    ('deny', 'svchost.exe', 'name', 'system', 'Windows Service Host'),
    ('deny', 'csrss.exe', 'name', 'system', 'Client Server Runtime'),
    ('deny', 'smss.exe', 'name', 'system', 'Session Manager'),
    ('deny', 'wininit.exe', 'name', 'system', 'Windows Initialization'),
    ('deny', 'services.exe', 'name', 'system', 'Windows Services'),
    ('deny', 'lsass.exe', 'name', 'system', 'Local Security Authority'),
    ('deny', 'winlogon.exe', 'name', 'system', 'Windows Logon'),
    ('deny', 'explorer.exe', 'name', 'system', 'Windows Explorer'),
    ('deny', 'dwm.exe', 'name', 'system', 'Desktop Window Manager'),
    ('deny', 'RuntimeBroker.exe', 'name', 'system', 'Runtime Broker');

-- Insert default configuration
INSERT OR IGNORE INTO config (key, value) VALUES
    ('cpu_threshold', '80.0'),
    ('memory_threshold', '80.0'),
    ('scan_interval_seconds', '60'),
    ('llm_confidence_threshold', '0.7'),
    ('enable_auto_kill', 'false'),
    ('prompt_version', 'v1.0');
