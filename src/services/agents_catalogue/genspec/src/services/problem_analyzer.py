"""
Problem statement analyzer service.
"""

import os
from typing import Dict, Any
from src.services.agents_catalogue.genspec.src.services.client_factory import get_client_class
from src.services.agents_catalogue.genspec.src.services.langchain_manager import LangChainManager
from src.providers.logger import Logger
from src.api.dependencies import get_logger
logger = get_logger("problem-analyzer")

class ProblemAnalyzer:
    """
    Analyzes problem statements to extract key information.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the problem statement analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        ClientClass = get_client_class(config["provider"])
        self.bedrock_client = ClientClass(config)
        self.langchain_manager = LangChainManager(config)
        self.prompt_template_path = config["analysis"]["problem_statement_prompt_template"]
        
        logger.info("Initialized problem statement analyzer")
    
    def analyze(self, problem_statement_path: str) -> Dict[str, Any]:
        """
        Analyze a problem statement and extract key information.
        
        Args:
            problem_statement_path: Path to the problem statement file
            
        Returns:
            Dictionary containing extracted information
        """
        try:
            # Read the problem statement
            with open(problem_statement_path, 'r') as file:
                problem_statement_text = file.read()
            
            logger.info(f"Read problem statement from {problem_statement_path}")
            
            # Check if the problem statement has markdown-style headers
            if "## " in problem_statement_text:
                logger.info("Detected Markdown-style headers in problem statement, parsing directly")
                analysis_data = self._parse_markdown_problem_statement(problem_statement_text)
            else:
                # Create an improved prompt for the LangChain
                improved_prompt = """
                You are analyzing a problem statement for a technical specification.
                
                Problem Statement:
                {problem_statement}
                
                Extract and organize the following information from the problem statement:
                
                PROJECT_NAME: The name of the project mentioned or implied in the problem statement
                BUSINESS_CONTEXT: The business context surrounding the problem
                CURRENT_CHALLENGES: Current challenges or pain points being addressed
                ADDITIONAL_CONTEXT: Any other relevant context
                SCOPE: The scope of the project if mentioned
                GOALS: The goals of the project if mentioned
                NON_GOALS: Any non-goals or exclusions if mentioned
                ASSUMPTIONS: Any assumptions made if mentioned
                
                Format your response with these exact section headers, followed by the extracted information.
                """
                
                # Create LangChain with the improved prompt
                chain = self.langchain_manager.create_chain(
                    improved_prompt,
                    output_key="problem_analysis"
                )
                
                # Run the analysis
                result = chain.run(problem_statement=problem_statement_text)
                
                # Parse the result into structured data
                analysis_data = self._parse_analysis_result(result)
            
            # Add the original problem statement
            analysis_data["problem_statement"] = problem_statement_text
            
            # Ensure all required fields exist with default empty values
            required_fields = [
                "project_name", "business_context", "current_challenges", "additional_context",
                "scope", "goals", "non_goals", "assumptions", "out_of_scope", "futuristic_scope",
                "dependencies", "testing_plan", "go_live_plan", "monitoring_logging", "milestones_timelines"
            ]
            
            for field in required_fields:
                if field not in analysis_data:
                    analysis_data[field] = ""
            
            logger.info("Problem statement analysis completed")
            return analysis_data
        except Exception as e:
            logger.error(f"Error analyzing problem statement: {str(e)}")
            # Return basic structure with problem statement to prevent template errors
            return {
                "problem_statement": problem_statement_text,
                "project_name": "",
                "business_context": "",
                "current_challenges": "",
                "additional_context": "",
                "scope": "",
                "goals": "",
                "non_goals": "",
                "assumptions": "",
                "out_of_scope": "",
                "futuristic_scope": "",
                "dependencies": "",
                "testing_plan": "",
                "go_live_plan": "",
                "monitoring_logging": "",
                "milestones_timelines": ""
            }
    
    def _parse_markdown_problem_statement(self, text: str) -> Dict[str, Any]:
        """
        Parse a problem statement with Markdown-style headers.
        
        Args:
            text: Problem statement text with Markdown headers
            
        Returns:
            Dictionary with extracted sections
        """
        # Define the mapping of markdown headers to our internal field names
        header_mapping ={
            "## Current Challenges": "current_challenges",
            "## Business Context": "business_context",
            "## Additional Context": "additional_context"
        }
        
        # Extract the project name from the first line or paragraph
        project_name = ""
        first_line = text.strip().split('\n')[0]
        if first_line.startswith('# '):
            project_name = first_line[2:].strip()
        else:
            # Try to extract from the first sentence
            first_sentence = text.split('.')[0]
            words = first_sentence.split()
            if len(words) >= 2:
                project_name = " ".join(words[:2])
        
        # Initialize result dictionary
        result = {
            "project_name": project_name
        }
        
        # Split the text by markdown headers (##)
        parts = text.split('##')
        
        # Process each part
        for i, part in enumerate(parts):
            if i == 0:  # Skip the first part (before any headers)
                continue
                
            # Get the header and content
            lines = part.strip().split('\n')
            if not lines:
                continue
                
            header = "## " + lines[0].strip()
            content = '\n'.join(lines[1:]).strip()
            
            # Map the header to our field name
            for md_header, field_name in header_mapping.items():
                if header.lower().startswith(md_header.lower()):
                    result[field_name] = content
                    break
        
        return result
    
    def _parse_analysis_result(self, result: str) -> Dict[str, Any]:
        """
        Parse the analysis result into structured data.
        
        Args:
            result: Raw analysis result from LLM
            
        Returns:
            Structured data extracted from the analysis
        """
        # This is a simplified parser that assumes the LLM returns sections with specific headers
        
        sections = {
            "PROJECT_NAME": "project_name",
            "BUSINESS_CONTEXT": "business_context",
            "CURRENT_CHALLENGES": "current_challenges",
            "ADDITIONAL_CONTEXT": "additional_context",
            "INTRODUCTION": "introduction",
            "SCOPE": "scope",
            "GOALS": "goals",
            "NON_GOALS": "non_goals",
            "ASSUMPTIONS": "assumptions",
            "OUT_OF_SCOPE": "out_of_scope",
            "FUTURISTIC_SCOPE": "futuristic_scope"
        }
        
        # Add markdown-style headers to the sections dictionary
        markdown_sections = {
            "## Current Challenges": "current_challenges",
            "## Business Context": "business_context",
            "## Additional Context": "additional_context",
            "## Introduction": "introduction",
            "## Scope": "scope",
            "## Goals": "goals",
            "## Non-Goals": "non_goals",
            "## Assumptions": "assumptions",
            "## Out of Scope": "out_of_scope",
            "## Futuristic Scope": "futuristic_scope"
        }
        
        # Merge the two dictionaries
        sections.update(markdown_sections)
        
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
        
        # Extract project name from the first paragraph if not found
        if "project_name" not in parsed_data and "problem_statement" in parsed_data:
            first_paragraph = parsed_data["problem_statement"].split('.')[0]
            if first_paragraph:
                # Try to extract a project name from the first sentence
                words = first_paragraph.split()
                if len(words) >= 2:
                    parsed_data["project_name"] = " ".join(words[:2])
        
        # If current_challenges is not found, try to extract from the second paragraph
        if "current_challenges" not in parsed_data and "problem_statement" in parsed_data:
            paragraphs = parsed_data["problem_statement"].split('\n\n')
            if len(paragraphs) >= 2:
                parsed_data["current_challenges"] = paragraphs[1]
        
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
        list_sections = ["goals", "non_goals", "assumptions", "out_of_scope", "futuristic_scope"]
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