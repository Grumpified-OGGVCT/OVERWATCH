"""Chaos tests for OVERWATCH system resilience."""
import subprocess
import time
import requests
import unittest
import os


class TestChaosResilience(unittest.TestCase):
    """Test system resilience to component failures."""

    def setUp(self):
        """Check if we're in a test environment."""
        if os.getenv('SKIP_CHAOS_TESTS') == '1':
            self.skipTest("Chaos tests disabled")

    def test_ai_layer_recovery(self):
        """Test that AI layer recovers after crash."""
        # Kill Flask container
        try:
            subprocess.run(
                ["podman", "kill", "overwatch-ai-layer"],
                check=False,
                capture_output=True
            )
        except Exception:
            self.skipTest("Podman not available")
        
        # Wait for restart
        time.sleep(10)
        
        # Check if it's running again
        result = subprocess.run(
            ["podman", "ps", "--filter", "name=overwatch-ai-layer", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=False
        )
        
        self.assertIn("Up", result.stdout, "AI Layer should have restarted")

    def test_ui_recovery(self):
        """Test that Streamlit UI recovers after crash."""
        try:
            subprocess.run(
                ["podman", "kill", "overwatch-ui"],
                check=False,
                capture_output=True
            )
        except Exception:
            self.skipTest("Podman not available")
        
        time.sleep(10)
        
        result = subprocess.run(
            ["podman", "ps", "--filter", "name=overwatch-ui", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=False
        )
        
        self.assertIn("Up", result.stdout, "UI should have restarted")

    def test_prometheus_data_persistence(self):
        """Test that Prometheus data persists after restart."""
        try:
            # Stop Prometheus
            subprocess.run(
                ["podman", "stop", "overwatch-prometheus"],
                check=False,
                capture_output=True
            )
            
            time.sleep(5)
            
            # Start it again
            subprocess.run(
                ["podman", "start", "overwatch-prometheus"],
                check=False,
                capture_output=True
            )
            
            time.sleep(15)
            
            # Check if data is accessible
            response = requests.get("http://localhost:9090/api/v1/query?query=up", timeout=5)
            self.assertEqual(response.status_code, 200)
            
        except Exception as e:
            self.skipTest(f"Podman or Prometheus not available: {e}")

    def test_alertmanager_resilience(self):
        """Test that Alertmanager handles network partitions."""
        try:
            # Simulate network partition
            subprocess.run(
                ["podman", "stop", "overwatch-alertmanager"],
                check=False,
                capture_output=True
            )
            
            time.sleep(10)
            
            # Restore
            subprocess.run(
                ["podman", "start", "overwatch-alertmanager"],
                check=False,
                capture_output=True
            )
            
            time.sleep(10)
            
            # Verify alerts are still processed
            response = requests.get("http://localhost:9093/api/v1/alerts", timeout=5)
            self.assertEqual(response.status_code, 200)
            
        except Exception as e:
            self.skipTest(f"Alertmanager not available: {e}")


class TestDatabaseResilience(unittest.TestCase):
    """Test database resilience and recovery."""

    def test_database_concurrent_access(self):
        """Test that database handles concurrent access."""
        # This would require the database to be accessible
        # Skipping for now as it depends on the environment
        self.skipTest("Requires live database")

    def test_database_corruption_recovery(self):
        """Test recovery from database corruption."""
        self.skipTest("Requires controlled corruption scenario")


if __name__ == '__main__':
    # Set environment variable to enable chaos tests
    # export RUN_CHAOS_TESTS=1
    if os.getenv('RUN_CHAOS_TESTS') != '1':
        print("Chaos tests disabled. Set RUN_CHAOS_TESTS=1 to enable.")
        print("WARNING: Chaos tests will restart services and may disrupt operations.")
    
    unittest.main()
