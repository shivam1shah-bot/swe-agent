"""
PRD analyzer service.
"""

import os
from typing import Dict, Any
from src.services.agents_catalogue.genspec.src.services.client_factory import get_client_class
from src.services.agents_catalogue.genspec.src.services.langchain_manager import LangChainManager
from src.providers.logger import Logger
from src.api.dependencies import get_logger
logger = get_logger("prd-analyzer")

class PRDAnalyzer:
    """
    Analyzes Product Requirement Documents (PRDs) to extract key information.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the PRD analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        ClientClass = get_client_class(config["provider"])
        self.bedrock_client = ClientClass(config)
        self.langchain_manager = LangChainManager(config)
        self.prompt_template_path = config["analysis"]["prd_analysis_prompt_template"]
        
        logger.info("Initialized PRD analyzer")
    
    def analyze(self, prd_path: str) -> Dict[str, Any]:
        """
        Analyze a PRD document and extract key information.
        
        Args:
            prd_path: Path to the PRD document
            
        Returns:
            Dictionary containing extracted information
        """
        try:
            # Read the PRD document
            with open(prd_path, 'r') as file:
                prd_text = file.read()
            
            logger.info(f"Read PRD from {prd_path}")
            
            # Create LangChain for analysis
            chain = self.langchain_manager.create_chain_from_file(
                self.prompt_template_path,
                output_key="prd_analysis"
            )
            
            # Run the analysis
            result = chain.run(prd=prd_text)
            
            # Parse the result into structured data
            analysis_data = self._parse_analysis_result(result)
            
            logger.info("PRD analysis completed")
            return analysis_data
        except Exception as e:
            logger.error(f"Error analyzing PRD: {str(e)}")
            raise
    
    def _parse_analysis_result(self, result: str) -> Dict[str, Any]:
        """
        Parse the analysis result into structured data.
        
        Args:
            result: Raw analysis result from LLM
            
        Returns:
            Structured data extracted from the analysis
        """
        # This is a simplified parser that assumes the LLM returns JSON-like sections
        # In a real implementation, this would be more robust
        
        sections = {
            "PROJECT_NAME": "project_name",
            "INTRODUCTION": "introduction",
            "SCOPE": "scope",
            "GOALS": "goals",
            "NON_GOALS": "non_goals",
            "ASSUMPTIONS": "assumptions",
            "OUT_OF_SCOPE": "out_of_scope",
            "FUTURISTIC_SCOPE": "futuristic_scope",
            "RELEVANT_RESOURCES": "relevant_resources_raw",
            "USER_STORIES": "user_stories",
            "BUSINESS_RULES": "business_rules",
            "CONSTRAINTS": "constraints"
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
                        parsed_data[current_section] = self._process_section_content(section_content, current_section)
                    
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
            parsed_data[current_section] = self._process_section_content(section_content, current_section)
        
        # Process relevant resources into structured format
        if "relevant_resources_raw" in parsed_data:
            parsed_data["relevant_resources"] = self._parse_relevant_resources(parsed_data["relevant_resources_raw"])
        
        return parsed_data
    
    def _process_section_content(self, content: list, section_key: str) -> Any:
        """
        Process the content of a section based on its type.
        
        Args:
            content: List of content lines for the section
            section_key: The key of the section being processed
            
        Returns:
            Processed section content
        """
        # Join all lines into a single string
        full_content = ' '.join(content)
        
        # Process list-type sections
        list_sections = ["goals", "non_goals", "assumptions", "out_of_scope", "futuristic_scope", "user_stories", "business_rules", "constraints"]
        if section_key in list_sections:
            # Extract list items (lines starting with - or *)
            items = []
            for line in content:
                line = line.strip()
                if line.startswith('- ') or line.startswith('* '):
                    items.append(line[2:])
                else:
                    # If not a list item, see if it contains multiple items
                    for item in line.split('. '):
                        if item:
                            items.append(item)
            
            return items
        
        # For text sections, return the full content
        return full_content
    
    def _parse_relevant_resources(self, resources_text: Any) -> list:
        """
        Parse relevant resources into structured format.
        
        Args:
            resources_text: Raw resources text or list
            
        Returns:
            List of resource dictionaries
        """
        resources = []
        
        # If already a list, process each item
        if isinstance(resources_text, list):
            for item in resources_text:
                # Try to extract name and URL from each item
                if "[" in item and "]" in item and "(" in item and ")" in item:
                    # Markdown link format: [name](url)
                    name = item.split("[")[1].split("]")[0]
                    url = item.split("(")[1].split(")")[0]
                    resources.append({"name": name, "url": url})
                else:
                    # Just use the item as the name
                    resources.append({"name": item, "url": "#"})
        else:
            # If a string, split by lines and process each line
            for line in str(resources_text).split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Check for markdown link format
                if "[" in line and "]" in line and "(" in line and ")" in line:
                    # Markdown link format: [name](url)
                    name = line.split("[")[1].split("]")[0]
                    url = line.split("(")[1].split(")")[0]
                    resources.append({"name": name, "url": url})
                elif line.startswith("- ") or line.startswith("* "):
                    # List item without link
                    resources.append({"name": line[2:], "url": "#"})
                else:
                    # Just use the line as the name
                    resources.append({"name": line, "url": "#"})
        
        return resources 