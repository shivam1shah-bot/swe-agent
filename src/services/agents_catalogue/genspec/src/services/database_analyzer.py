"""
Database analyzer service.
"""

from typing import Dict, Any
from src.services.agents_catalogue.genspec.src.services.client_factory import get_client_class
from src.services.agents_catalogue.genspec.src.services.langchain_manager import LangChainManager
from src.providers.logger import Logger
from src.api.dependencies import get_logger

logger = get_logger("database-analyzer")

class DatabaseAnalyzer:
    """
    Analyzes database requirements and provides recommendations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the database analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        ClientClass = get_client_class(config["provider"])
        self.bedrock_client = ClientClass(config)
        self.langchain_manager = LangChainManager(config)
        self.prompt_template_path = config["analysis"]["database_analysis_prompt_template"]
        
        logger.info("Initialized database analyzer")
    
    def analyze(self, spec_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze database requirements and provide recommendations.
        
        Args:
            spec_data: Specification data collected so far
            
        Returns:
            Dictionary containing database analysis and recommendations
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
            
            # Create system prompt for database analysis
            system_prompt = self._get_system_prompt()
            
            # Generate the analysis using Bedrock
            analysis_result = self.bedrock_client.generate_text(
                prompt=combined_input,
                system_prompt=system_prompt
            )
            
            # Parse the result into structured data
            database_analysis = self._parse_analysis_result(analysis_result)
            
            logger.info("Database analysis completed")
            return database_analysis
        except Exception as e:
            logger.error(f"Error analyzing database requirements: {str(e)}")
            raise
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for database analysis.
        
        Returns:
            System prompt string
        """
        return """
        You are a senior database architect with expertise in database selection, schema design, and data architecture.
        
        Based on the provided requirements, provide comprehensive database recommendations and schema design guidance.
        
        Your analysis should include:
        
        1. DATABASE_NEEDS: Whether the project requires database changes (Yes/No)
        2. WORKLOAD_TYPE: Analysis of workload characteristics (read-heavy, write-heavy, balanced)
        3. JOIN_COMPLEXITY: Assessment of JOIN complexity (simple, moderate, complex)
        4. ACID_REQUIREMENTS: ACID compliance needs (full, partial, not required)
        5. TRANSACTION_BOUNDARIES: Identification of transaction boundaries
        6. NORMALIZATION: Recommendations for normalization/denormalization
        7. ARCHIVAL_POLICY: Recommendations for data archival (time-based or other)
        8. COMPLIANCE_REQUIREMENTS: International compliance handling needs
        9. SCHEMA_CHANGES: Detailed schema changes required (tables, columns, relationships)
        10. DATABASE_RECOMMENDATIONS: Specific database technology recommendations with justifications
        
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
            "DATABASE_NEEDS": "database_needs",
            "WORKLOAD_TYPE": "workload_type",
            "JOIN_COMPLEXITY": "join_complexity",
            "ACID_REQUIREMENTS": "acid_requirements",
            "TRANSACTION_BOUNDARIES": "transaction_boundaries",
            "NORMALIZATION": "normalization",
            "ARCHIVAL_POLICY": "archival_policy",
            "COMPLIANCE_REQUIREMENTS": "compliance_requirements",
            "SCHEMA_CHANGES": "schema_changes",
            "DATABASE_RECOMMENDATIONS": "database_recommendations"
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
        
        # Combine all database-related information into a single field for the template
        parsed_data["database_changes"] = self._format_database_changes(parsed_data)
        
        return parsed_data
    
    def _format_database_changes(self, parsed_data: Dict[str, str]) -> str:
        """
        Format all database-related information into a single markdown section.
        
        Args:
            parsed_data: Parsed data from the analysis result
            
        Returns:
            Formatted markdown string
        """
        if parsed_data.get("database_needs", "").lower().strip() in ["no", "none", "n/a"]:
            return "No database changes required."
        
        sections = [
            ("Workload Type", "workload_type"),
            ("JOIN Complexity", "join_complexity"),
            ("ACID Requirements", "acid_requirements"),
            ("Transaction Boundaries", "transaction_boundaries"),
            ("Normalization Strategy", "normalization"),
            ("Archival Policy", "archival_policy"),
            ("Compliance Requirements", "compliance_requirements"),
            ("Schema Changes", "schema_changes"),
            ("Database Recommendations", "database_recommendations")
        ]
        
        formatted_content = []
        
        for title, key in sections:
            if key in parsed_data and parsed_data[key]:
                formatted_content.append(f"### {title}\n\n{parsed_data[key]}")
        
        return "\n\n".join(formatted_content) 