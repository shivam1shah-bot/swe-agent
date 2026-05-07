"""
Architecture diagram analyzer service.
"""

import os
import base64
from typing import Dict, Any, List
from src.services.agents_catalogue.genspec.src.services.client_factory import get_client_class
from src.services.agents_catalogue.genspec.src.services.langchain_manager import LangChainManager
from src.providers.logger import Logger
from src.api.dependencies import get_logger
logger = get_logger("architecture-analyzer")

class ArchitectureAnalyzer:
    """
    Analyzes architecture diagrams to extract key information.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the architecture analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        ClientClass = get_client_class(config["provider"])
        self.bedrock_client = ClientClass(config)
        self.langchain_manager = LangChainManager(config)
        self.prompt_template_path = config["analysis"]["architecture_analysis_prompt_template"]
        
        logger.info("Initialized architecture analyzer")
    
    def analyze(self, architecture_diagram_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze architecture diagrams and extract key information.
        
        Args:
            architecture_diagram_paths: Paths to architecture diagram PNG files
            
        Returns:
            Dictionary containing extracted information
        """
        try:
            results = {}
            
            for diagram_path in architecture_diagram_paths:
                logger.info(f"Analyzing architecture diagram: {diagram_path}")
                
                # Read and encode the diagram
                with open(diagram_path, 'rb') as file:
                    diagram_data = file.read()
                
                base64_image = base64.b64encode(diagram_data).decode('utf-8')
                
                # Create a system prompt for architecture analysis
                system_prompt = self._get_system_prompt()
                
                # Create a user prompt with the image
                user_prompt = f"Analyze the following architecture diagram and create a Mermaid diagram that exactly replicates it:\n\n<image>{base64_image}</image>"
                
                # Generate the analysis using Bedrock
                analysis_result = self.bedrock_client.generate_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt
                )
                
                # Extract the Mermaid diagram and other information
                diagram_data = self._extract_mermaid_diagram(analysis_result)
                component_data = self._extract_component_information(analysis_result)
                
                # Add to results
                diagram_name = os.path.basename(diagram_path).split('.')[0]
                results[diagram_name] = {
                    "mermaid_diagram": diagram_data.get("diagram", ""),
                    "components": component_data.get("components", []),
                    "relationships": component_data.get("relationships", []),
                    "description": component_data.get("description", "")
                }
            
            # Combine all results
            combined_results = {
                "current_architecture_diagram": self._combine_diagrams(results),
                "current_architecture_description": self._combine_descriptions(results),
                "components": self._combine_components(results),
                "relationships": self._combine_relationships(results)
            }
            
            logger.info("Architecture analysis completed")
            return combined_results
        except Exception as e:
            logger.error(f"Error analyzing architecture diagrams: {str(e)}")
            raise
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for architecture analysis.
        
        Returns:
            System prompt string
        """
        return """
        You are analyzing an architecture diagram for a technical specification with extreme precision.

        Create a CLEAN, professional current architecture diagram using Mermaid that EXACTLY REPLICATES the architecture shown in the provided diagram. Use these styling guidelines:

        CRITICAL REQUIREMENTS:
        - EXACTLY REPLICATE the structure, components, and relationships from the original diagram
        - DO NOT add, remove, or modify ANY components from the original diagram
        - MAINTAIN the same layout and flow direction as the original diagram
        - USE the EXACT SAME component names as shown in the original diagram
        - PRESERVE all connections and relationships exactly as they appear in the original
        - Use a professional color scheme with blues (#3498db, #2980b9), grays (#95a5a6, #7f8c8d), and dark text (#2c3e50)
        - NEVER use pink, purple, or bright red colors in the diagram
        - Use clean, straight lines for connections with appropriate arrows
        - For flowcharts, use flowchart TD or LR directive based on the original orientation
        - Ensure proper spacing between components for readability
        
        After creating the Mermaid diagram, provide a detailed analysis of:
        1. All components in the diagram and their purposes
        2. All relationships and data flows between components
        3. A concise description of the overall architecture
        
        Format your response with these sections:
        
        MERMAID_DIAGRAM:
        (Your Mermaid diagram code here)
        
        COMPONENTS:
        (List all components and their purposes)
        
        RELATIONSHIPS:
        (List all relationships and data flows)
        
        DESCRIPTION:
        (Concise description of the overall architecture)
        """
    
    def _extract_mermaid_diagram(self, analysis_result: str) -> Dict[str, Any]:
        """
        Extract the Mermaid diagram from the analysis result.
        
        Args:
            analysis_result: Raw analysis result from LLM
            
        Returns:
            Dictionary containing the extracted Mermaid diagram
        """
        # Simple extraction - rely on the prompt to format correctly
        lines = analysis_result.split('\n')
        diagram_lines = []
        in_diagram = False
        
        for line in lines:
            stripped = line.strip()
            if stripped == "MERMAID_DIAGRAM:":
                in_diagram = True
                continue
            elif stripped.startswith("COMPONENTS:") or stripped.startswith("RELATIONSHIPS:") or stripped.startswith("DESCRIPTION:"):
                break
            elif in_diagram:
                diagram_lines.append(line)
        
        diagram = '\n'.join(diagram_lines).strip()
        return {"diagram": diagram}
    
    def _extract_component_information(self, analysis_result: str) -> Dict[str, Any]:
        """
        Extract component information from the analysis result.
        
        Args:
            analysis_result: Raw analysis result from LLM
            
        Returns:
            Dictionary containing extracted component information
        """
        # Simple extraction - trust the prompt formatting
        lines = analysis_result.split('\n')
        components = []
        relationships = []
        description_lines = []
        
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            
            if stripped == "COMPONENTS:":
                current_section = "components"
            elif stripped == "RELATIONSHIPS:":
                current_section = "relationships"
            elif stripped == "DESCRIPTION:":
                current_section = "description"
            elif stripped == "MERMAID_DIAGRAM:":
                current_section = None
            elif current_section == "components" and stripped:
                components.append(stripped)
            elif current_section == "relationships" and stripped:
                relationships.append(stripped)
            elif current_section == "description" and stripped:
                description_lines.append(stripped)
        
        return {
            "components": components,
            "relationships": relationships,
            "description": " ".join(description_lines)
        }
    
    def _combine_diagrams(self, results: Dict[str, Dict[str, Any]]) -> str:
        """
        Combine multiple Mermaid diagrams into one.
        
        Args:
            results: Dictionary of analysis results by diagram name
            
        Returns:
            Combined Mermaid diagram string
        """
        # For simplicity, we'll use the first diagram as the main one
        # In a real implementation, this would be more sophisticated
        if not results:
            return ""
        
        first_diagram_name = list(results.keys())[0]
        return results[first_diagram_name]["mermaid_diagram"]
    
    def _combine_descriptions(self, results: Dict[str, Dict[str, Any]]) -> str:
        """
        Combine multiple architecture descriptions into one.
        
        Args:
            results: Dictionary of analysis results by diagram name
            
        Returns:
            Combined description string
        """
        descriptions = []
        
        for diagram_name, data in results.items():
            descriptions.append(f"### {diagram_name}\n\n{data['description']}")
        
        return "\n\n".join(descriptions)
    
    def _combine_components(self, results: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Combine component lists from multiple diagrams.
        
        Args:
            results: Dictionary of analysis results by diagram name
            
        Returns:
            Combined list of components
        """
        all_components = []
        
        for data in results.values():
            all_components.extend(data["components"])
        
        # Remove duplicates while preserving order
        unique_components = []
        for component in all_components:
            if component not in unique_components:
                unique_components.append(component)
        
        return unique_components
    
    def _combine_relationships(self, results: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Combine relationship lists from multiple diagrams.
        
        Args:
            results: Dictionary of analysis results by diagram name
            
        Returns:
            Combined list of relationships
        """
        all_relationships = []
        
        for data in results.values():
            all_relationships.extend(data["relationships"])
        
        # Remove duplicates while preserving order
        unique_relationships = []
        for relationship in all_relationships:
            if relationship not in unique_relationships:
                unique_relationships.append(relationship)
        
        return unique_relationships

    def analyze_text_architecture(self, text_description: str) -> Dict[str, Any]:
        """
        Analyze text description of architecture and generate flowchart.
        
        Args:
            text_description: Text description of the architecture
            
        Returns:
            Dictionary containing analysis results and generated flowchart
        """
        try:
            logger.info("Analyzing text architecture description")
            
            # Create a system prompt for text architecture analysis
            system_prompt = self._get_text_analysis_system_prompt()
            
            # Create a user prompt with the text description
            user_prompt = f"""
            Analyze this architecture description and create a comprehensive technical analysis with a professional Mermaid flowchart:

            {text_description}

            Create a complete flowchart showing all components, databases, services, and their relationships. Include proper styling and ensure the diagram accurately represents the described architecture.
            """
            
            # Generate the analysis using Bedrock
            analysis_result = self.bedrock_client.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt
            )
            
            # Extract the Mermaid diagram and other information
            diagram_data = self._extract_mermaid_diagram(analysis_result)
            component_data = self._extract_component_information(analysis_result)
            
            result = {
                "mermaid_diagram": diagram_data.get("diagram", ""),
                "components": component_data.get("components", []),
                "relationships": component_data.get("relationships", []),
                "description": component_data.get("description", "")
            }
            
            logger.info("Text architecture analysis completed")
            return result
        except Exception as e:
            logger.error(f"Error analyzing text architecture: {str(e)}")
            raise

    def _get_text_analysis_system_prompt(self) -> str:
        """
        Get the system prompt for text architecture analysis.
        
        Returns:
            System prompt string
        """
        return """
        You are a senior technical architect who creates professional, accurate architecture diagrams from text descriptions.

        Your response must follow this EXACT format with NO deviations:

        MERMAID_DIAGRAM:
        flowchart TD
            [Complete valid Mermaid flowchart code here - MUST use 'flowchart TD' or 'flowchart LR' syntax]
            [NEVER use deprecated 'graph TD' syntax - always use 'flowchart TD']
            [Include all components with proper node shapes: [Service], (API), [(Database)], ((External))]
            [Show all relationships with arrows and clear labels]
            [Apply professional styling with classDef and class assignments]
            [Use colors: blues #3498db #2980b9, greens #27ae60 #16a085, grays #95a5a6 #7f8c8d]

        COMPONENTS:
        - Component Name: Clear description of purpose and responsibility
        - Service Name: What it does and why it exists in the architecture
        - Database Name: What data it stores and how it's accessed
        [Continue for all components mentioned in the text]

        RELATIONSHIPS:
        - Source → Target: Detailed description of data flow and interaction type
        - Component A ↔ Component B: Bidirectional relationship explanation
        [Continue for all relationships identified]

        DESCRIPTION:
        [Write 2-3 paragraphs explaining the overall architecture, including system design patterns, data flows, integration points, scalability considerations, and key technical decisions. Be comprehensive but concise.]

        CRITICAL REQUIREMENTS:
        1. Your Mermaid diagram MUST use 'flowchart TD' syntax (NOT 'graph TD')
        2. Include EVERY component mentioned in the text description
        3. Show ALL relationships and data flows clearly
        4. Use proper Mermaid node shapes for different component types
        5. Apply consistent professional styling with colors
        6. Ensure the diagram is visually clear and well-organized
        7. Your output must follow the exact format above - no extra text or explanations

        Remember: The quality of your analysis directly impacts the technical specification. Be thorough, accurate, and professional.
        """
