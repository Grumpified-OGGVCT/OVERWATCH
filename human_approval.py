"""Human-in-the-loop approval system."""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class HumanApproval:
    """Interactive approval system for process termination decisions."""
    
    def __init__(self):
        """Initialize human approval system."""
        self.approved_decisions = []
        self.rejected_decisions = []
    
    def request_approval(self, decisions: List[Dict]) -> List[Dict]:
        """
        Request human approval for decisions.
        
        Args:
            decisions: List of decision dictionaries from LLM
            
        Returns:
            List of approved decisions
        """
        if not decisions:
            print("\n✓ No problematic processes found requiring action.")
            return []
        
        print(f"\n{'='*80}")
        print(f"OVERWATCH - Process Remediation Review")
        print(f"{'='*80}")
        print(f"\nFound {len(decisions)} processes requiring review.\n")
        
        approved = []
        
        for i, decision in enumerate(decisions, 1):
            self._display_decision(i, len(decisions), decision)
            
            # Get user input
            choice = self._get_user_choice(decision)
            
            if choice == 'approve':
                approved.append(decision)
                self.approved_decisions.append(decision)
                print("  ✓ Approved for remediation\n")
            elif choice == 'reject':
                self.rejected_decisions.append(decision)
                print("  ✗ Rejected - process will be kept\n")
            elif choice == 'skip':
                print("  → Skipped - will be reviewed again in next scan\n")
            elif choice == 'quit':
                print("\n  Quitting review process...")
                break
        
        return approved
    
    def _display_decision(self, index: int, total: int, decision: Dict):
        """Display a decision for review."""
        print(f"\n{'-'*80}")
        print(f"Process {index}/{total}")
        print(f"{'-'*80}")
        
        # Process details
        print(f"\n📋 Process Information:")
        print(f"  • PID: {decision['pid']}")
        print(f"  • Name: {decision['name']}")
        print(f"  • Category: {decision['category'].upper()}")
        
        proc_details = decision.get('process_details', {})
        if proc_details:
            print(f"  • CPU Usage: {proc_details.get('cpu_percent', 0):.1f}%")
            print(f"  • Memory Usage: {proc_details.get('memory_percent', 0):.1f}%")
            print(f"  • Status: {proc_details.get('status', 'UNKNOWN')}")
            print(f"  • Executable: {proc_details.get('exe', 'N/A')}")
            if proc_details.get('cmdline'):
                print(f"  • Command: {proc_details.get('cmdline')[:80]}...")
        
        # LLM recommendation
        print(f"\n🤖 AI Analysis:")
        print(f"  • Recommendation: {self._format_recommendation(decision['recommendation'])}")
        print(f"  • Risk Level: {self._format_risk_level(decision['risk_level'])}")
        print(f"  • Reasoning: {decision['reasoning'][:200]}...")
        
        if decision.get('fallback'):
            print(f"\n  ⚠️  Note: LLM unavailable - using fallback heuristics")
    
    def _format_recommendation(self, recommendation: str) -> str:
        """Format recommendation with colors/symbols."""
        symbols = {
            'TERMINATE': '❌ TERMINATE',
            'KEEP': '✓ KEEP',
            'INVESTIGATE': '🔍 INVESTIGATE'
        }
        return symbols.get(recommendation, recommendation)
    
    def _format_risk_level(self, risk_level: str) -> str:
        """Format risk level with symbols."""
        symbols = {
            'LOW': '🟢 LOW',
            'MEDIUM': '🟡 MEDIUM',
            'HIGH': '🟠 HIGH',
            'CRITICAL': '🔴 CRITICAL'
        }
        return symbols.get(risk_level, risk_level)
    
    def _get_user_choice(self, decision: Dict) -> str:
        """
        Get user's choice for a decision.
        
        Returns:
            'approve', 'reject', 'skip', or 'quit'
        """
        while True:
            print(f"\n  Options:")
            print(f"    [a] Approve - Execute {decision['recommendation']}")
            print(f"    [r] Reject - Keep the process running")
            print(f"    [s] Skip - Review again later")
            print(f"    [q] Quit - Stop review process")
            
            choice = input("\n  Your choice (a/r/s/q): ").strip().lower()
            
            if choice in ['a', 'approve']:
                return 'approve'
            elif choice in ['r', 'reject']:
                return 'reject'
            elif choice in ['s', 'skip']:
                return 'skip'
            elif choice in ['q', 'quit']:
                return 'quit'
            else:
                print("  Invalid choice. Please enter 'a', 'r', 's', or 'q'.")
    
    def batch_approve_all(self, decisions: List[Dict]) -> List[Dict]:
        """
        Auto-approve all decisions (for automated mode - USE WITH CAUTION).
        
        Args:
            decisions: List of decision dictionaries
            
        Returns:
            All decisions (approved)
        """
        logger.warning("Batch approve all mode - auto-approving all decisions!")
        self.approved_decisions.extend(decisions)
        return decisions
    
    def get_approval_summary(self) -> Dict:
        """Get summary of approval session."""
        return {
            'total_approved': len(self.approved_decisions),
            'total_rejected': len(self.rejected_decisions),
            'approved_pids': [d['pid'] for d in self.approved_decisions],
            'rejected_pids': [d['pid'] for d in self.rejected_decisions]
        }
