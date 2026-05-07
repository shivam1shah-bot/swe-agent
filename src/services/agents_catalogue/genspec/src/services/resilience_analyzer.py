"""
Resilience analyzer service.
"""

from typing import Dict, Any
from src.services.agents_catalogue.genspec.src.services.client_factory import get_client_class
from src.services.agents_catalogue.genspec.src.services.langchain_manager import LangChainManager
from src.providers.logger import Logger
from src.api.dependencies import get_logger
logger = get_logger("resilience-analyzer")

class ResilienceAnalyzer:
    """
    Analyzes system resilience requirements and provides recommendations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the resilience analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        ClientClass = get_client_class(config["provider"])
        self.bedrock_client = ClientClass(config)
        self.langchain_manager = LangChainManager(config)
        self.prompt_template_path = config["analysis"]["resilience_analysis_prompt_template"]
        
        logger.info("Initialized resilience analyzer")
    
    def analyze(self, spec_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze resilience requirements and provide recommendations.
        
        Args:
            spec_data: Specification data collected so far
            
        Returns:
            Dictionary containing resilience analysis and recommendations
        """
        try:
            # Extract relevant information from spec_data
            problem_statement = spec_data.get("problem_statement", "")
            introduction = spec_data.get("introduction", "")
            scope = spec_data.get("scope", "")
            
            # Combine all available information for analysis
            combined_input = f"""
            PROBLEM STATEMENT:
            {problem_statement}
            
            INTRODUCTION:
            {introduction}
            
            SCOPE:
            {scope}
            """
            
            # Add architecture information if available
            if "components" in spec_data:
                components_text = "\n".join(spec_data["components"])
                combined_input += f"\nCOMPONENTS:\n{components_text}"
            
            if "relationships" in spec_data:
                relationships_text = "\n".join(spec_data["relationships"])
                combined_input += f"\nRELATIONSHIPS:\n{relationships_text}"
            
            # Add database information if available
            if "database_changes" in spec_data:
                combined_input += f"\nDATABASE INFORMATION:\n{spec_data['database_changes']}"
            
            # Create system prompt for resilience analysis
            system_prompt = self._get_system_prompt()
            
            # Generate the analysis using Bedrock
            analysis_result = self.bedrock_client.generate_text(
                prompt=combined_input,
                system_prompt=system_prompt
            )
            
            # Parse the result into structured data
            resilience_analysis = self._parse_analysis_result(analysis_result)
            
            logger.info("Resilience analysis completed")
            return resilience_analysis
        except Exception as e:
            logger.error(f"Error analyzing resilience requirements: {str(e)}")
            raise
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for resilience analysis.
        
        Returns:
            System prompt string
        """
        return """
        You are a senior software architect with expertise in distributed systems, resilience engineering, and failure analysis.
        
        Based on the provided requirements and architecture, identify potential failure points and provide comprehensive resilience recommendations.
        
        Your analysis should include:
        
        1. QUEUE_USAGE: Whether the system uses or should use message queues/event streaming
        2. IDEMPOTENCY_REQUIREMENTS: Requirements for idempotent processing
        3. MESSAGE_ORDERING: Requirements for message ordering
        4. FAILURE_POINTS: Identification of potential failure points in the system
        5. CIRCUIT_BREAKER: Recommendations for circuit breaker pattern implementation
        6. RETRY_STRATEGIES: Recommendations for retry strategies
        7. TRANSACTION_BOUNDARIES: Recommendations for transaction boundaries
        8. RESILIENCE_PATTERNS: Specific resilience patterns that should be implemented
        9. MONITORING_RECOMMENDATIONS: Specific monitoring recommendations for resilience
        
        Format your response with these clear section headers.
        """
    
    def _parse_analysis_result(self, result: str) -> Dict[str, Any]:
        """
        Parse the analysis result into structured data.
        
        Args:
            result: Raw analysis result from LLM
            
        Returns:
            Structured data extracted from the analysis
        """
        sections = {
            "QUEUE_USAGE": "queue_usage",
            "IDEMPOTENCY_REQUIREMENTS": "idempotency_requirements",
            "MESSAGE_ORDERING": "message_ordering",
            "FAILURE_POINTS": "failure_points",
            "CIRCUIT_BREAKER": "circuit_breaker",
            "RETRY_STRATEGIES": "retry_strategies",
            "TRANSACTION_BOUNDARIES": "transaction_boundaries",
            "RESILIENCE_PATTERNS": "resilience_patterns",
            "MONITORING_RECOMMENDATIONS": "monitoring_recommendations"
        }
        
        parsed_data = {}
        current_section = None
        section_content = []
        
        # Split the result into lines and process each line
        for line in result.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Check if this line is a section header
            found_section = False
            for marker, key in sections.items():
                if line.startswith(marker + ":") or line == marker:
                    # Save the previous section if there was one
                    if current_section and section_content:
                        parsed_data[current_section] = "\n".join(section_content)
                    
                    # Start a new section
                    current_section = key
                    section_content = []
                    found_section = True
                    break
            
            # If not a section header, add to the current section content
            if not found_section and current_section:
                section_content.append(line)
        
        # Don't forget to save the last section
        if current_section and section_content:
            parsed_data[current_section] = "\n".join(section_content)
        
        # Format the resilience information for the template
        parsed_data.update(self._format_resilience_data(parsed_data))
        
        return parsed_data
    
    def _format_resilience_data(self, parsed_data: Dict[str, str]) -> Dict[str, str]:
        """
        Format resilience data for the template.
        
        Args:
            parsed_data: Parsed data from the analysis result
            
        Returns:
            Dictionary with formatted resilience data
        """
        # Format reliability section
        reliability_sections = [
            ("Failure Points", "failure_points"),
            ("Circuit Breaker Pattern", "circuit_breaker"),
            ("Retry Strategies", "retry_strategies"),
            ("Resilience Patterns", "resilience_patterns")
        ]
        
        reliability_content = []
        for title, key in reliability_sections:
            if key in parsed_data and parsed_data[key]:
                reliability_content.append(f"### {title}\n\n{parsed_data[key]}")
        
        reliability = "\n\n".join(reliability_content) if reliability_content else "No specific reliability requirements identified."
        
        # Format monitoring section
        monitoring_content = parsed_data.get("monitoring_recommendations", "")
        monitoring_logging = f"### Monitoring Recommendations\n\n{monitoring_content}" if monitoring_content else "No specific monitoring recommendations identified."
        
        return {
            "reliability": reliability,
            "monitoring_logging": monitoring_logging
        } 