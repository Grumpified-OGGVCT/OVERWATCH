"""LLM-based decision engine using Ollama via proxy."""
import requests
import logging
from typing import Dict, List, Optional
from process_detector import ProcessInfo

logger = logging.getLogger(__name__)


class LLMDecisionEngine:
    """Uses Ollama LLM to make intelligent decisions about process termination."""
    
    def __init__(self, proxy_url: str, api_key: str):
        """
        Initialize LLM decision engine.
        
        Args:
            proxy_url: URL of Ollama proxy server (e.g., http://localhost:8081)
            api_key: API key for authentication
        """
        self.proxy_url = proxy_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def _call_ollama(self, prompt: str, model: str = "llama2") -> Optional[str]:
        """
        Call Ollama API through proxy.
        
        Args:
            prompt: The prompt to send to the LLM
            model: Model name to use
            
        Returns:
            LLM response text or None if error
        """
        try:
            endpoint = f"{self.proxy_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(
                endpoint,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Ollama API: {e}")
            return None
    
    def analyze_process(self, proc_info: ProcessInfo, category: str) -> Dict:
        """
        Analyze a process using LLM and recommend action.
        
        Args:
            proc_info: ProcessInfo object
            category: Category of the issue (orphaned/zombie/resource_leeching)
            
        Returns:
            Dictionary with analysis results including recommendation and reasoning
        """
        # Build context prompt for the LLM
        prompt = self._build_analysis_prompt(proc_info, category)
        
        # Get LLM response
        llm_response = self._call_ollama(prompt)
        
        if llm_response is None:
            # Fallback decision if LLM is unavailable
            return self._fallback_decision(proc_info, category)
        
        # Parse LLM response to extract decision
        decision = self._parse_llm_response(llm_response, proc_info, category)
        
        return decision
    
    def _build_analysis_prompt(self, proc_info: ProcessInfo, category: str) -> str:
        """Build a detailed prompt for process analysis."""
        prompt = f"""You are a system administrator analyzing a potentially problematic process on Windows 11.

Process Details:
- PID: {proc_info.pid}
- Name: {proc_info.name}
- Executable: {proc_info.exe}
- Command Line: {proc_info.cmdline}
- Status: {proc_info.status}
- CPU Usage: {proc_info.cpu_percent:.1f}%
- Memory Usage: {proc_info.memory_percent:.1f}%
- Threads: {proc_info.num_threads}
- Parent PID: {proc_info.parent_pid}
- Parent Name: {proc_info.parent_name}
- Username: {proc_info.username}

Issue Category: {category}

Based on this information, analyze whether this process should be terminated. Consider:
1. Is this a critical system process?
2. Could terminating it cause system instability?
3. Is the resource usage justified for this type of application?
4. Are there signs this is malicious or problematic?

Provide your recommendation in this exact format:
RECOMMENDATION: [TERMINATE|KEEP|INVESTIGATE]
RISK_LEVEL: [LOW|MEDIUM|HIGH|CRITICAL]
REASONING: [Your detailed explanation]

Be conservative - if unsure, recommend INVESTIGATE rather than TERMINATE."""
        
        return prompt
    
    def _parse_llm_response(self, response: str, proc_info: ProcessInfo, 
                           category: str) -> Dict:
        """Parse LLM response into structured decision."""
        lines = response.strip().split('\n')
        
        recommendation = "INVESTIGATE"
        risk_level = "MEDIUM"
        reasoning = response
        
        # Try to parse structured response
        for line in lines:
            if line.startswith('RECOMMENDATION:'):
                rec = line.split(':', 1)[1].strip().upper()
                if rec in ['TERMINATE', 'KEEP', 'INVESTIGATE']:
                    recommendation = rec
            elif line.startswith('RISK_LEVEL:'):
                risk = line.split(':', 1)[1].strip().upper()
                if risk in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']:
                    risk_level = risk
            elif line.startswith('REASONING:'):
                reasoning = line.split(':', 1)[1].strip()
        
        return {
            'pid': proc_info.pid,
            'name': proc_info.name,
            'category': category,
            'recommendation': recommendation,
            'risk_level': risk_level,
            'reasoning': reasoning,
            'llm_full_response': response,
            'process_details': proc_info.to_dict()
        }
    
    def _fallback_decision(self, proc_info: ProcessInfo, category: str) -> Dict:
        """
        Provide a conservative fallback decision when LLM is unavailable.
        
        This uses simple heuristics rather than AI reasoning.
        """
        # Very conservative - only recommend termination for clear cases
        recommendation = "INVESTIGATE"
        risk_level = "MEDIUM"
        
        if category == "zombie":
            recommendation = "TERMINATE"
            risk_level = "LOW"
            reasoning = "Zombie process detected. Safe to terminate (fallback decision)."
        elif category == "resource_leeching":
            if proc_info.cpu_percent > 95 and proc_info.memory_percent > 90:
                recommendation = "INVESTIGATE"
                risk_level = "HIGH"
                reasoning = "Extremely high resource usage. Requires investigation (fallback decision)."
            else:
                recommendation = "INVESTIGATE"
                risk_level = "MEDIUM"
                reasoning = "Elevated resource usage detected. Requires investigation (fallback decision)."
        elif category == "orphaned":
            recommendation = "INVESTIGATE"
            risk_level = "MEDIUM"
            reasoning = "Orphaned process detected. Requires investigation (fallback decision)."
        else:
            reasoning = f"Unknown category: {category}. Requires investigation (fallback decision)."
        
        return {
            'pid': proc_info.pid,
            'name': proc_info.name,
            'category': category,
            'recommendation': recommendation,
            'risk_level': risk_level,
            'reasoning': reasoning,
            'llm_full_response': None,
            'process_details': proc_info.to_dict(),
            'fallback': True
        }
    
    def batch_analyze(self, categorized_processes: Dict[str, List[ProcessInfo]]) -> List[Dict]:
        """
        Analyze all categorized processes and return recommendations.
        
        Args:
            categorized_processes: Dict with categories as keys, ProcessInfo lists as values
            
        Returns:
            List of decision dictionaries
        """
        all_decisions = []
        
        for category, processes in categorized_processes.items():
            logger.info(f"Analyzing {len(processes)} {category} processes...")
            
            for proc_info in processes:
                logger.info(f"Analyzing process: {proc_info}")
                decision = self.analyze_process(proc_info, category)
                all_decisions.append(decision)
        
        return all_decisions
