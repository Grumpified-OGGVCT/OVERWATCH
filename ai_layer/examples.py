"""
Example usage script for OVERWATCH.

This demonstrates how to use the OVERWATCH system programmatically.
"""

from config import Config
from process_detector import ProcessDetector
from llm_decision import LLMDecisionEngine
from audit_logger import AuditLogger
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_single_scan():
    """Example: Run a single scan with all components."""
    
    print("\n" + "="*80)
    print("OVERWATCH - Example Single Scan")
    print("="*80 + "\n")
    
    # Initialize components
    detector = ProcessDetector(
        cpu_threshold=Config.CPU_THRESHOLD,
        memory_threshold=Config.MEMORY_THRESHOLD,
        protected_processes=Config.PROTECTED_PROCESSES
    )
    
    # Detect problematic processes
    print("Step 1: Scanning for problematic processes...")
    categorized = detector.detect_problematic_processes()
    
    total = sum(len(procs) for procs in categorized.values())
    print(f"Found {total} problematic processes:")
    print(f"  - Orphaned: {len(categorized['orphaned'])}")
    print(f"  - Zombie: {len(categorized['zombie'])}")
    print(f"  - Resource Leeching: {len(categorized['resource_leeching'])}")
    
    if total == 0:
        print("\nNo problems detected! System is healthy.")
        return
    
    # Show details of detected processes
    print("\nDetailed process information:")
    for category, processes in categorized.items():
        if processes:
            print(f"\n{category.upper()}:")
            for proc in processes[:3]:  # Show first 3 of each category
                print(f"  - PID {proc.pid}: {proc.name} "
                      f"(CPU: {proc.cpu_percent:.1f}%, Mem: {proc.memory_percent:.1f}%)")


def example_llm_analysis():
    """Example: Analyze processes using LLM."""
    
    print("\n" + "="*80)
    print("OVERWATCH - Example LLM Analysis")
    print("="*80 + "\n")
    
    # Initialize components
    detector = ProcessDetector(
        cpu_threshold=80.0,
        memory_threshold=80.0,
        protected_processes=Config.PROTECTED_PROCESSES
    )
    
    llm_engine = LLMDecisionEngine(
        proxy_url=Config.OLLAMA_PROXY_URL,
        api_key=Config.OLLAMA_API_KEY
    )
    
    # Detect and analyze
    categorized = detector.detect_problematic_processes()
    
    # For demonstration, only analyze first process of each category
    sample_processes = {}
    for category, processes in categorized.items():
        if processes:
            sample_processes[category] = [processes[0]]
    
    if not any(sample_processes.values()):
        print("No processes to analyze.")
        return
    
    print("Analyzing sample processes with LLM...\n")
    decisions = llm_engine.batch_analyze(sample_processes)
    
    for decision in decisions:
        print(f"\nProcess: {decision['name']} (PID {decision['pid']})")
        print(f"Category: {decision['category']}")
        print(f"Recommendation: {decision['recommendation']}")
        print(f"Risk Level: {decision['risk_level']}")
        print(f"Reasoning: {decision['reasoning'][:150]}...")


def example_audit_logging():
    """Example: Demonstrate audit logging."""
    
    print("\n" + "="*80)
    print("OVERWATCH - Example Audit Logging")
    print("="*80 + "\n")
    
    Config.ensure_directories()
    audit_logger = AuditLogger(Config.AUDIT_LOG_PATH)
    
    # Create sample events
    print("Creating sample audit events...")
    
    # Log a scan
    scan_id = audit_logger.log_scan({
        'orphaned': [],
        'zombie': [],
        'resource_leeching': []
    })
    print(f"✓ Logged scan event: {scan_id}")
    
    # Log an error
    error_id = audit_logger.log_error(
        error_type="EXAMPLE_ERROR",
        error_message="This is a test error",
        context={'test': True}
    )
    print(f"✓ Logged error event: {error_id}")
    
    # Retrieve recent events
    print("\nRecent audit events:")
    recent = audit_logger.get_recent_events(limit=5)
    for event in recent:
        print(f"  - {event['event_type']}: {event['event_id']} "
              f"at {event['timestamp']}")


def main():
    """Run all examples."""
    
    print("\n" + "="*80)
    print("OVERWATCH - Usage Examples")
    print("="*80)
    
    print("\nThese examples demonstrate OVERWATCH functionality.")
    print("Note: Some examples require Ollama proxy to be running.\n")
    
    try:
        # Example 1: Simple scan
        example_single_scan()
        
        # Example 2: LLM analysis (may fail if Ollama not available)
        try:
            example_llm_analysis()
        except Exception as e:
            print(f"\nLLM analysis example skipped (Ollama may not be available): {e}")
        
        # Example 3: Audit logging
        example_audit_logging()
        
        print("\n" + "="*80)
        print("Examples complete!")
        print("="*80 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == '__main__':
    main()
