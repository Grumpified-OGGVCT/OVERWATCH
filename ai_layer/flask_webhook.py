"""
OVERWATCH AI Reasoning Layer (Flask Webhook)
Receives alerts from Alertmanager, analyzes with LLM, and stores recommendations.
"""

from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
import requests
import json
import logging
import os
import sys
from datetime import datetime

# Add parent directory to path to import database module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.db_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize database
db = DatabaseManager()

# Prometheus metrics
alerts_received = Counter('overwatch_alerts_received_total', 'Total alerts received', ['category'])
alerts_processed = Counter('overwatch_alerts_processed_total', 'Total alerts processed', ['action'])
llm_calls = Counter('overwatch_llm_calls_total', 'Total LLM API calls', ['status'])
llm_latency = Histogram('overwatch_llm_latency_seconds', 'LLM API call latency')

# Configuration
OLLAMA_PROXY_URL = os.getenv('OLLAMA_PROXY_URL', 'http://localhost:8081')
OLLAMA_API_KEY = os.getenv('OLLAMA_API_KEY', '')
WEBHOOK_TOKEN = os.getenv('WEBHOOK_TOKEN', 'overwatch-secret-token')
PROMPT_VERSION = 'v1.0'

# System process deny list (pre-LLM safety check)
SYSTEM_PROCESS_DENY_LIST = {
    'System', 'svchost.exe', 'csrss.exe', 'smss.exe', 'wininit.exe',
    'services.exe', 'lsass.exe', 'winlogon.exe', 'explorer.exe',
    'dwm.exe', 'RuntimeBroker.exe', 'Registry', 'Memory Compression'
}


def verify_webhook_token():
    """Verify the webhook bearer token."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False
    token = auth_header[7:]
    return token == WEBHOOK_TOKEN


def is_system_process(pid: int, process_name: str) -> bool:
    """
    Pre-LLM safety check: is this a system process that should never be killed?
    
    Args:
        pid: Process ID
        process_name: Process name
        
    Returns:
        True if this is a protected system process
    """
    # System PIDs (Windows kernel and core services)
    if pid < 1000:
        return True
    
    # Check deny list
    if process_name in SYSTEM_PROCESS_DENY_LIST:
        return True
    
    # Check database rules
    deny_rules = db.get_process_rules('deny')
    for rule in deny_rules:
        if rule['pattern_type'] == 'name' and rule['pattern'] == process_name:
            return True
    
    return False


def build_llm_prompt(alert_data: dict, process_metadata: dict) -> str:
    """
    Build a structured LLM prompt for process analysis.
    
    Args:
        alert_data: Alert information from Prometheus
        process_metadata: Additional process metadata
        
    Returns:
        Formatted prompt string
    """
    prompt = f"""You are a Windows sysadmin AI assistant. Given the following Prometheus alert and process metadata, determine if it is safe to kill the process.

ALERT PAYLOAD:
Alert Name: {alert_data.get('alert_name')}
Severity: {alert_data.get('severity')}
Category: {alert_data.get('category')}
Description: {alert_data.get('description')}

PROCESS METADATA:
- PID: {process_metadata.get('pid')}
- Name: {process_metadata.get('process_name')}
- Parent PID: {process_metadata.get('parent_pid')}
- Command Line: {process_metadata.get('cmdline', 'N/A')}
- Start Time: {process_metadata.get('start_time', 'N/A')}
- CPU Usage: {process_metadata.get('cpu_percent', 'N/A')}%
- Memory Usage: {process_metadata.get('memory_percent', 'N/A')}%
- Owner: {process_metadata.get('owner', 'N/A')}

HEURISTICS AND SAFETY RULES:
1. Never kill system processes (PID < 1000).
2. Never kill critical services like svchost.exe, winlogon.exe, lsass.exe.
3. If the parent is missing (orphaned process) and it's >1 hour old and not a service → safe to kill.
4. If it's a dev script (python/node/powershell) and >1 hour old with high CPU/mem → likely safe.
5. If it's idle but holding >50MB RAM for >5 minutes (pseudo-zombie) → safe to kill.
6. If a user-owned process has high CPU/mem usage → may be legitimate work, recommend investigation.
7. If it's a system service → always recommend manual review.

Return ONLY a JSON object with one of the following structures (no extra text):

{{"action":"kill","pid":{process_metadata.get('pid')},"command":"Stop-Process -Id {process_metadata.get('pid')} -Force","note":"Safe to kill (orphaned/zombie/dev script)","confidence":0.95}}

{{"action":"manual","reason":"System process or critical service","confidence":1.0}}

{{"action":"safe_check","reason":"Ambiguous context, needs manual confirmation","confidence":0.5}}

The confidence score should be between 0.0 and 1.0, where:
- 1.0 = Absolutely certain (system process, never kill)
- 0.9-0.95 = Very confident (orphaned dev script, clear case)
- 0.7-0.8 = Moderately confident (likely safe but review recommended)
- 0.5-0.6 = Uncertain (needs manual review)

Respond with ONLY the JSON object, no additional text."""

    return prompt


def call_ollama_llm(prompt: str, model: str = "llama2") -> dict:
    """
    Call Ollama LLM via proxy with structured output.
    
    Args:
        prompt: The prompt to send
        model: Model name
        
    Returns:
        Parsed JSON response or fallback decision
    """
    try:
        with llm_latency.time():
            endpoint = f"{OLLAMA_PROXY_URL}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",  # Request JSON format
                "options": {
                    "temperature": 0.0,  # Deterministic
                    "top_p": 0.9
                }
            }
            
            headers = {
                'Authorization': f'Bearer {OLLAMA_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                # Parse JSON response
                try:
                    decision = json.loads(response_text)
                    llm_calls.labels(status='success').inc()
                    logger.info(f"LLM decision: {decision}")
                    return {
                        'success': True,
                        'decision': decision,
                        'full_response': response_text,
                        'fallback': False
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM JSON response: {e}")
                    logger.error(f"Raw response: {response_text}")
                    llm_calls.labels(status='parse_error').inc()
                    return get_fallback_decision(None, "LLM JSON parse error")
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                llm_calls.labels(status='error').inc()
                return get_fallback_decision(None, f"API error: {response.status_code}")
                
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API: {e}")
        llm_calls.labels(status='connection_error').inc()
        return get_fallback_decision(None, f"Connection error: {e}")


def get_fallback_decision(process_metadata: dict, reason: str) -> dict:
    """
    Provide a conservative fallback decision when LLM is unavailable.
    
    Args:
        process_metadata: Process information
        reason: Reason for fallback
        
    Returns:
        Fallback decision dictionary
    """
    return {
        'success': True,
        'decision': {
            'action': 'safe_check',
            'reason': f'LLM unavailable ({reason}). Manual review required.',
            'confidence': 0.0
        },
        'full_response': None,
        'fallback': True
    }


def extract_process_info_from_alert(alert: dict) -> dict:
    """Extract process information from Prometheus alert."""
    annotations = alert.get('annotations', {})
    labels = alert.get('labels', {})
    
    return {
        'alert_name': labels.get('alertname', 'Unknown'),
        'severity': labels.get('severity', 'unknown'),
        'category': labels.get('category', 'unknown'),
        'pid': int(annotations.get('pid', 0)),
        'process_name': annotations.get('process_name', 'unknown'),
        'parent_pid': annotations.get('parent_pid'),
        'cmdline': annotations.get('cmdline'),
        'cpu_percent': annotations.get('cpu_percent'),
        'memory_percent': annotations.get('memory_percent'),
        'description': annotations.get('description', ''),
        'alert_payload': alert
    }


@app.route('/webhook/alert', methods=['POST'])
def receive_alert():
    """Receive and process alerts from Alertmanager."""
    # Verify token (simplified for demo, use proper auth in production)
    # if not verify_webhook_token():
    #     return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        payload = request.json
        logger.info(f"Received webhook payload: {json.dumps(payload, indent=2)}")
        
        # Alertmanager sends multiple alerts in one payload
        alerts = payload.get('alerts', [])
        
        processed_alerts = []
        
        for alert in alerts:
            status = alert.get('status', 'firing')
            
            # Only process firing alerts
            if status != 'firing':
                logger.info(f"Skipping resolved alert: {alert.get('labels', {}).get('alertname')}")
                continue
            
            # Extract process information
            process_info = extract_process_info_from_alert(alert)
            category = process_info['category']
            pid = process_info['pid']
            process_name = process_info['process_name']
            
            alerts_received.labels(category=category).inc()
            
            # Pre-LLM safety check
            if is_system_process(pid, process_name):
                logger.warning(f"Blocked by safety filter: PID {pid} ({process_name}) is a system process")
                
                # Store alert with manual recommendation
                alert_id = db.create_alert(process_info)
                rec_id = db.create_recommendation(alert_id, {
                    'llm_model': 'safety_filter',
                    'action': 'manual',
                    'confidence': 1.0,
                    'reasoning': 'Blocked by local safety filter - system process',
                    'command': None,
                    'prompt_version': PROMPT_VERSION,
                    'full_response': {'filter': 'system_process'},
                    'fallback': False
                })
                
                alerts_processed.labels(action='manual').inc()
                processed_alerts.append({
                    'alert_id': alert_id,
                    'recommendation_id': rec_id,
                    'action': 'manual'
                })
                continue
            
            # Create alert in database
            alert_id = db.create_alert(process_info)
            
            # Build LLM prompt
            prompt = build_llm_prompt(process_info, process_info)
            
            # Call LLM
            llm_result = call_ollama_llm(prompt)
            
            decision = llm_result['decision']
            action = decision.get('action', 'safe_check')
            
            # Store recommendation
            recommendation = {
                'llm_model': 'llama2',
                'action': action,
                'confidence': decision.get('confidence', 0.0),
                'reasoning': decision.get('reason', decision.get('note', '')),
                'command': decision.get('command'),
                'prompt_version': PROMPT_VERSION,
                'full_response': llm_result.get('full_response'),
                'fallback': llm_result.get('fallback', False)
            }
            
            rec_id = db.create_recommendation(alert_id, recommendation)
            
            alerts_processed.labels(action=action).inc()
            
            logger.info(f"Processed alert {alert_id}: action={action}, confidence={decision.get('confidence')}")
            
            processed_alerts.append({
                'alert_id': alert_id,
                'recommendation_id': rec_id,
                'action': action,
                'confidence': decision.get('confidence')
            })
        
        return jsonify({
            'status': 'ok',
            'processed': len(processed_alerts),
            'alerts': processed_alerts
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(REGISTRY), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ollama_url': OLLAMA_PROXY_URL,
        'database': str(db.db_path)
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Index endpoint."""
    return jsonify({
        'service': 'OVERWATCH AI Reasoning Layer',
        'version': '2.1',
        'endpoints': {
            '/webhook/alert': 'POST - Receive alerts from Alertmanager',
            '/metrics': 'GET - Prometheus metrics',
            '/health': 'GET - Health check'
        }
    }), 200


if __name__ == '__main__':
    # Initialize database
    logger.info("Initializing OVERWATCH AI Layer...")
    logger.info(f"Database: {db.db_path}")
    logger.info(f"Ollama Proxy: {OLLAMA_PROXY_URL}")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
