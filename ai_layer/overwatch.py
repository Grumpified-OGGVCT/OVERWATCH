"""Main orchestrator for OVERWATCH system."""
import logging
import sys
from config import Config
from process_detector import ProcessDetector
from llm_decision import LLMDecisionEngine
from human_approval import HumanApproval
from remediator import ProcessRemediator
from audit_logger import AuditLogger


# Configure logging
def setup_logging(log_level: str):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('overwatch.log')
        ]
    )


logger = logging.getLogger(__name__)


class OverwatchOrchestrator:
    """Main orchestrator for the OVERWATCH system."""
    
    def __init__(self):
        """Initialize the orchestrator with all components."""
        # Validate configuration
        config_errors = Config.validate()
        if config_errors:
            logger.error("Configuration errors found:")
            for error in config_errors:
                logger.error(f"  - {error}")
            raise ValueError("Invalid configuration. Please check your .env file.")
        
        # Ensure directories exist
        Config.ensure_directories()
        
        # Initialize components
        self.detector = ProcessDetector(
            cpu_threshold=Config.CPU_THRESHOLD,
            memory_threshold=Config.MEMORY_THRESHOLD,
            protected_processes=Config.PROTECTED_PROCESSES
        )
        
        self.llm_engine = LLMDecisionEngine(
            proxy_url=Config.OLLAMA_PROXY_URL,
            api_key=Config.OLLAMA_API_KEY
        )
        
        self.human_approval = HumanApproval()
        self.remediator = ProcessRemediator()
        self.audit_logger = AuditLogger(Config.AUDIT_LOG_PATH)
        
        logger.info("OVERWATCH orchestrator initialized successfully")
    
    def run_single_scan(self, auto_approve: bool = False) -> dict:
        """
        Execute a single scan and remediation cycle.
        
        Args:
            auto_approve: If True, auto-approve all recommendations (DANGEROUS!)
            
        Returns:
            Summary dictionary of the scan results
        """
        logger.info("="*80)
        logger.info("Starting OVERWATCH scan cycle")
        logger.info("="*80)
        
        try:
            # Step 1: Detect problematic processes
            logger.info("Step 1: Detecting problematic processes...")
            categorized_processes = self.detector.detect_problematic_processes()
            scan_event_id = self.audit_logger.log_scan(categorized_processes)
            
            # Check if any problems found
            total_problems = sum(len(procs) for procs in categorized_processes.values())
            if total_problems == 0:
                logger.info("No problematic processes detected. System healthy!")
                return {
                    'scan_event_id': scan_event_id,
                    'problems_found': 0,
                    'decisions_made': 0,
                    'approved': 0,
                    'remediated': 0
                }
            
            # Step 2: Analyze with LLM
            logger.info(f"Step 2: Analyzing {total_problems} processes with LLM...")
            decisions = self.llm_engine.batch_analyze(categorized_processes)
            analysis_event_id = self.audit_logger.log_analysis(decisions)
            
            # Step 3: Human approval
            logger.info("Step 3: Requesting human approval...")
            if auto_approve:
                logger.warning("AUTO-APPROVE MODE ENABLED - Approving all decisions automatically!")
                approved_decisions = self.human_approval.batch_approve_all(decisions)
            else:
                approved_decisions = self.human_approval.request_approval(decisions)
            
            # Log human decisions
            for decision in decisions:
                approved = decision in approved_decisions
                self.audit_logger.log_human_decision(decision, approved)
            
            if not approved_decisions:
                logger.info("No decisions approved. No remediation performed.")
                return {
                    'scan_event_id': scan_event_id,
                    'analysis_event_id': analysis_event_id,
                    'problems_found': total_problems,
                    'decisions_made': len(decisions),
                    'approved': 0,
                    'remediated': 0
                }
            
            # Step 4: Execute remediation
            logger.info(f"Step 4: Executing remediation for {len(approved_decisions)} approved decisions...")
            remediation_results = self.remediator.batch_remediate(approved_decisions)
            
            # Log remediation results
            for decision, result in zip(approved_decisions, remediation_results):
                self.audit_logger.log_remediation(
                    decision,
                    success=result.get('success', False),
                    error=result.get('error')
                )
            
            # Summary
            successful_remediations = sum(1 for r in remediation_results if r.get('success'))
            
            summary = {
                'scan_event_id': scan_event_id,
                'analysis_event_id': analysis_event_id,
                'problems_found': total_problems,
                'decisions_made': len(decisions),
                'approved': len(approved_decisions),
                'remediated': successful_remediations,
                'failed': len(remediation_results) - successful_remediations
            }
            
            logger.info("="*80)
            logger.info("Scan cycle complete - Summary:")
            logger.info(f"  Problems found: {summary['problems_found']}")
            logger.info(f"  Decisions made: {summary['decisions_made']}")
            logger.info(f"  Approved: {summary['approved']}")
            logger.info(f"  Successfully remediated: {summary['remediated']}")
            logger.info(f"  Failed: {summary['failed']}")
            logger.info("="*80)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error during scan cycle: {e}", exc_info=True)
            self.audit_logger.log_error(
                error_type="SCAN_CYCLE_ERROR",
                error_message=str(e)
            )
            raise
    
    def run_continuous(self, interval_seconds: int = None, auto_approve: bool = False):
        """
        Run continuous monitoring and remediation.
        
        Args:
            interval_seconds: Seconds between scans (uses config default if None)
            auto_approve: If True, auto-approve all recommendations (DANGEROUS!)
        """
        if interval_seconds is None:
            interval_seconds = Config.SCAN_INTERVAL_SECONDS
        
        logger.info(f"Starting continuous monitoring mode (interval: {interval_seconds}s)")
        
        if auto_approve:
            logger.warning("⚠️  AUTO-APPROVE MODE ENABLED - All recommendations will be executed automatically!")
        
        import time
        
        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                logger.info(f"\n{'='*80}")
                logger.info(f"Scan Cycle #{cycle_count}")
                logger.info(f"{'='*80}")
                
                self.run_single_scan(auto_approve=auto_approve)
                
                logger.info(f"Waiting {interval_seconds} seconds until next scan...")
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("\n\nContinuous monitoring stopped by user")
            logger.info(f"Total cycles completed: {cycle_count}")
        except Exception as e:
            logger.error(f"Fatal error in continuous monitoring: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='OVERWATCH - Orphan Process Terminator with AI Reasoning'
    )
    parser.add_argument(
        '--mode',
        choices=['single', 'continuous'],
        default='single',
        help='Run mode: single scan or continuous monitoring'
    )
    parser.add_argument(
        '--interval',
        type=int,
        help='Interval between scans in continuous mode (seconds)'
    )
    parser.add_argument(
        '--auto-approve',
        action='store_true',
        help='⚠️  DANGEROUS: Auto-approve all recommendations without human review'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Display banner
    print("\n" + "="*80)
    print("OVERWATCH - Orphan Process Terminator with AI Reasoning")
    print("Windows 11 Process Monitoring and Remediation System")
    print("="*80 + "\n")
    
    if args.auto_approve:
        print("⚠️  WARNING: AUTO-APPROVE MODE ENABLED")
        print("    All AI recommendations will be executed WITHOUT human review!")
        print("    This mode should only be used in controlled environments.\n")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborting.")
            return
    
    try:
        # Initialize orchestrator
        orchestrator = OverwatchOrchestrator()
        
        # Run based on mode
        if args.mode == 'single':
            orchestrator.run_single_scan(auto_approve=args.auto_approve)
        else:
            orchestrator.run_continuous(
                interval_seconds=args.interval,
                auto_approve=args.auto_approve
            )
            
    except KeyboardInterrupt:
        print("\n\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
