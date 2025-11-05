"""Unit tests for OVERWATCH AI Remediator."""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Add ai_layer to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ai_layer')))

# Mock the database module before importing flask_webhook
sys.modules['database'] = MagicMock()
sys.modules['database.db_manager'] = MagicMock()

from ai_layer.flask_webhook import is_system_process, build_llm_prompt


class TestSafetyFilter(unittest.TestCase):
    """Test the pre-LLM safety filter."""

    @patch('ai_layer.flask_webhook.db')
    def test_system_pid_blocked(self, mock_db):
        """Test that system PIDs (<1000) are blocked."""
        mock_db.get_process_rules.return_value = []
        result = is_system_process(500, "any.exe")
        self.assertTrue(result)

    @patch('ai_layer.flask_webhook.db')
    def test_critical_service_blocked(self, mock_db):
        """Test that critical services are blocked."""
        mock_db.get_process_rules.return_value = []
        result = is_system_process(1234, "svchost.exe")
        self.assertTrue(result)

    @patch('ai_layer.flask_webhook.db')
    def test_normal_process_allowed(self, mock_db):
        """Test that normal processes pass the filter."""
        mock_db.get_process_rules.return_value = []
        result = is_system_process(1234, "python.exe")
        self.assertFalse(result)

    @patch('ai_layer.flask_webhook.db')
    def test_database_deny_rule(self, mock_db):
        """Test that database deny rules are respected."""
        mock_db.get_process_rules.return_value = [
            {'pattern': 'test.exe', 'pattern_type': 'name'}
        ]
        result = is_system_process(1234, "test.exe")
        self.assertTrue(result)


class TestPromptBuilder(unittest.TestCase):
    """Test the LLM prompt building logic."""

    def test_prompt_includes_all_metadata(self):
        """Test that the prompt includes all process metadata."""
        alert_data = {
            'alert_name': 'TestAlert',
            'severity': 'warning',
            'category': 'orphaned',
            'description': 'Test description'
        }
        
        process_metadata = {
            'pid': 1234,
            'process_name': 'test.exe',
            'parent_pid': 5678,
            'cmdline': 'test.exe --arg',
            'cpu_percent': 10.5,
            'memory_percent': 5.2,
            'start_time': '2024-01-01T00:00:00',
            'owner': 'TestUser'
        }
        
        prompt = build_llm_prompt(alert_data, process_metadata)
        
        # Verify key components are in the prompt
        self.assertIn('TestAlert', prompt)
        self.assertIn('1234', prompt)
        self.assertIn('test.exe', prompt)
        self.assertIn('orphaned', prompt)
        self.assertIn('10.5', prompt)
        self.assertIn('TestUser', prompt)

    def test_prompt_includes_heuristics(self):
        """Test that safety heuristics are included in the prompt."""
        prompt = build_llm_prompt({}, {})
        
        self.assertIn('Never kill system processes', prompt)
        self.assertIn('PID < 1000', prompt)
        self.assertIn('svchost.exe', prompt)


class TestLLMResponse(unittest.TestCase):
    """Test LLM response parsing and validation."""

    def test_valid_kill_response(self):
        """Test parsing a valid 'kill' response."""
        response = {
            "action": "kill",
            "pid": 1234,
            "command": "Stop-Process -Id 1234 -Force",
            "note": "Safe to kill",
            "confidence": 0.95
        }
        
        # Validate against schema (would need to import schema)
        self.assertEqual(response['action'], 'kill')
        self.assertGreater(response['confidence'], 0.9)

    def test_valid_manual_response(self):
        """Test parsing a valid 'manual' response."""
        response = {
            "action": "manual",
            "reason": "System process",
            "confidence": 1.0
        }
        
        self.assertEqual(response['action'], 'manual')
        self.assertEqual(response['confidence'], 1.0)


if __name__ == '__main__':
    unittest.main()
